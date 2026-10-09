"""
文件名称：verify_coupon_task_concurrency.py
文件用途：在独立临时 MySQL 中重现旧事务快照和重复消费的抢券落库交错
主要职责：验证同任务重复执行只发一张券，任务始终返回成功且失败计数不增长，执行后删除临时库
所属业务模块：优惠券验收
创建时间：2026-09-08 18:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
from threading import Barrier, Event
import time

import pymysql
from sqlalchemy.engine import URL, make_url

from _runtime import PROJECT_ROOT, database_parts


def main():
    """
    函数名称：main
    函数用途：验证 MySQL 可重复读旧快照与多执行者重复消费同任务的幂等性
    参数说明：environment 可选，只取连接服务器凭据；rounds 指每类交错轮数，concurrency 为重复执行数
    返回值说明：成功输出脱敏 JSON；失败记录阶段和异常类型并返回非零
    核心逻辑：创建唯一临时库，使用真实独立事务交错执行最新业务服务，最后强制删除临时库
    异常或失败情况：断言或连接失败时停止；从不输出数据库凭据或操作来源业务库
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--output", default="tests/artifacts/erp_coupon_task_concurrency.json")
    options = parser.parse_args()
    assert 1 <= options.rounds <= 20 and 2 <= options.concurrency <= 40
    if options.environment:
        source_url = make_url(json.loads(Path(options.environment).read_text())["DATABASE_URL"])
        connection = {"host": source_url.host, "port": source_url.port or 3306,
            "user": source_url.username, "password": source_url.password}
    else:
        connection = database_parts()
    database_name = f"nayami_coupon_verify_{int(time.time())}_{os.getpid()}"
    admin_connection = pymysql.connect(host=str(connection["host"]), port=int(connection["port"]),
        user=str(connection["user"]), password=str(connection["password"]), autocommit=True)
    database_url = URL.create("mysql+pymysql", username=str(connection["user"]), password=str(connection["password"]),
        host=str(connection["host"]), port=int(connection["port"]), database=database_name, query={"charset": "utf8mb4"})
    report = {"status": "running", "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "python_executable": sys.executable, "database": "real MySQL", "isolation": "REPEATABLE READ",
        "temporary_database": database_name, "cache": "in-memory status cache; no broker or existing worker",
        "rounds": options.rounds, "concurrency": options.concurrency, "checks": {}}
    stage = "bootstrap"
    app = None
    try:
        with admin_connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from app import create_app
        from app.config import TestConfig
        from app.common.time_utils import current_time
        from app.coupons.models import CouponActivity, CouponClaimTask, UserCoupon
        from app.coupons.redis_store import get_coupon_redis_store
        from app.coupons.services import process_claim_task, reconcile_activity
        from app.extensions import db
        from app.users.models import Role, User, UserRole

        class VerificationConfig(TestConfig):
            SQLALCHEMY_DATABASE_URI = database_url
            SQLALCHEMY_ENGINE_OPTIONS = {"isolation_level": "REPEATABLE READ", "pool_size": 42, "max_overflow": 0}

        app = create_app(VerificationConfig)
        with app.app_context():
            db.create_all()
            user = User(username="concurrency_customer", password_hash="unused-no-login", user_type="customer")
            db.session.add(user)
            administrator = User(username="concurrency_admin", password_hash="unused-no-login", user_type="admin")
            role = Role(role_code="brand_admin", role_name="品牌管理员")
            db.session.add_all([administrator, role])
            db.session.flush()
            db.session.add(UserRole(user_id=administrator.id, role_id=role.id))
            db.session.commit()
            user_id, administrator_id = user.id, administrator.id

        def create_task():
            with app.app_context():
                now = current_time()
                activity = CouponActivity(activity_name_zh="并发落库验收", activity_status="active",
                    start_at=now-timedelta(hours=1), end_at=now+timedelta(days=1), total_stock=1,
                    per_user_limit=1, discount_amount=1, minimum_order_amount=0)
                db.session.add(activity)
                db.session.flush()
                task = CouponClaimTask(activity_id=activity.id, user_id=user_id, redis_success_time=now,
                    task_status="pending", retry_count=0)
                db.session.add(task)
                db.session.commit()
                return task.id, activity.id

        def verify_result(task_id, activity_id, responses):
            with app.app_context():
                task = db.session.get(CouponClaimTask, task_id)
                assert task.task_status == "succeeded" and task.retry_count == 0 and task.last_error is None
                assert UserCoupon.query.filter_by(activity_id=activity_id, user_id=user_id).count() == 1
                assert all(result["task_status"] == "succeeded" and result["retry_count"] == 0 for result in responses)
                return {"coupon_count": 1, "task_status": task.task_status, "retry_count": task.retry_count,
                    "successful_executions": len(responses)}

        stage = "stale_repeatable_read_snapshot"
        stale_results = []
        for _ in range(options.rounds):
            task_id, activity_id = create_task()
            snapshot_ready, executor_finished = Event(), Event()

            def stale_executor():
                with app.app_context():
                    cached_task = db.session.get(CouponClaimTask, task_id)
                    assert cached_task.task_status == "pending"
                    assert UserCoupon.query.filter_by(activity_id=activity_id, user_id=user_id).first() is None
                    snapshot_ready.set()
                    assert executor_finished.wait(20)
                    assert cached_task.task_status == "pending"
                    return process_claim_task(task_id, raise_on_error=True)

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(stale_executor)
                assert snapshot_ready.wait(20)
                try:
                    with app.app_context():
                        first_result = process_claim_task(task_id, raise_on_error=True)
                finally:
                    executor_finished.set()
                second_result = future.result(timeout=20)
            stale_results.append(verify_result(task_id, activity_id, [first_result, second_result]))
        report["checks"][stage] = stale_results

        stage = "simultaneous_duplicate_delivery"
        concurrent_results = []
        for _ in range(options.rounds):
            task_id, activity_id = create_task()
            preloaded = Barrier(options.concurrency)

            def concurrent_executor(_index):
                with app.app_context():
                    cached_task = db.session.get(CouponClaimTask, task_id)
                    assert cached_task.task_status == "pending"
                    assert UserCoupon.query.filter_by(activity_id=activity_id, user_id=user_id).first() is None
                    preloaded.wait(timeout=20)
                    return process_claim_task(task_id, raise_on_error=True)

            with ThreadPoolExecutor(max_workers=options.concurrency) as pool:
                responses = list(pool.map(concurrent_executor, range(options.concurrency)))
            concurrent_results.append(verify_result(task_id, activity_id, responses))
        report["checks"][stage] = concurrent_results

        stage = "reconcile_during_worker_completion"
        reconciliation_results = []
        for _ in range(options.rounds):
            task_id, activity_id = create_task()
            with app.app_context():
                task = db.session.get(CouponClaimTask, task_id)
                task.task_status = "failed"
                db.session.commit()
                redis_store = get_coupon_redis_store()
                redis_store.warmup(activity_id, 1)
                redis_store.claim(activity_id, user_id, f"verification-{activity_id}")
            snapshot_ready, executor_finished = Event(), Event()

            def stale_reconciliation():
                with app.app_context():
                    cached_task = db.session.get(CouponClaimTask, task_id)
                    assert cached_task.task_status == "failed"
                    assert UserCoupon.query.filter_by(activity_id=activity_id, user_id=user_id).first() is None
                    snapshot_ready.set()
                    assert executor_finished.wait(20)
                    return reconcile_activity(db.session.get(User, administrator_id), activity_id)

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(stale_reconciliation)
                assert snapshot_ready.wait(20)
                try:
                    with app.app_context():
                        response = process_claim_task(task_id, raise_on_error=True)
                finally:
                    executor_finished.set()
                metrics = future.result(timeout=20)
            assert metrics["pending_count"] == 0 and metrics["failed_count"] == 0 and metrics["succeeded_task_count"] == 1
            reconciliation_results.append(verify_result(task_id, activity_id, [response]))
        report["checks"][stage] = reconciliation_results
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="failed", failed_stage=stage, error_type=type(exc).__name__)
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        with admin_connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
            cursor.execute("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=%s", (database_name,))
            report["temporary_database_removed"] = cursor.fetchone()[0] == 0
        admin_connection.close()
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        output = PROJECT_ROOT / options.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" and report["temporary_database_removed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
