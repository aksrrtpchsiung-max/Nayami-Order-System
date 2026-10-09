"""
文件名称：verify_erp_async.py
文件用途：在隔离 MySQL、Redis、Gunicorn、Celery Worker 和 Beat 中验证 ERP 异步链路
主要职责：运行并发限量领取、失败幂等、任务重启恢复、真实数据库故障重试和定时扫描
所属业务模块：部署与验收
创建时间：2026-09-08 17:30
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""
from __future__ import annotations

import argparse
import json
from importlib.metadata import version
import os
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import pymysql
import redis

from _runtime import PROJECT_ROOT, database_parts


def free_port(excluded_ports=None):
    excluded = set(excluded_ports or ())
    while True:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        if port not in excluded:
            return port


def wait_until(predicate, timeout=75):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (ConnectionError, OSError, redis.RedisError):
            pass
        time.sleep(0.3)
    raise AssertionError("isolated_async_condition_timed_out")


def request_json(base, endpoint, token=None, payload=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(base + endpoint, method="POST" if payload is not None else "GET",
        headers=headers, data=json.dumps(payload).encode() if payload is not None else None)
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=90) as response:
            return response.status, json.loads(response.read()), time.perf_counter() - started
    except HTTPError as error:
        return error.code, json.loads(error.read()), time.perf_counter() - started


def main():
    """
    函数名称：main
    函数用途：执行可重复且不接触业务库的集成验收
    参数说明：--requests/--concurrency 为负载规模；--output 为脱敏结果路径
    返回值说明：成功返回 0，任一断言失败返回非零并保留脱敏失败阶段
    核心逻辑：创建唯一临时库和私有 Redis，启动真实进程，执行场景后停止进程并删临时库
    异常或失败情况：本机依赖未安装、数据库不可连接或断言失败；从不输出数据库密码
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=500)
    parser.add_argument("--output", default="docs/ERP异步验收结果.json")
    options = parser.parse_args()
    assert 1 <= options.concurrency <= 500 and options.requests >= 100
    connection = database_parts()
    database_name = f"nayami_async_verify_{int(time.time())}_{os.getpid()}"
    admin_db = pymysql.connect(host=str(connection["host"]), port=int(connection["port"]),
        user=str(connection["user"]), password=str(connection["password"]), autocommit=True)
    redis_port = free_port({16389})
    http_port = free_port({16389, redis_port})
    temporary = tempfile.TemporaryDirectory(prefix="nayami-async-verify-")
    processes = []
    report = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "isolated": True,
        "database_kind": "MySQL", "redis_kind": "real Redis", "worker_kind": "real Celery solo worker",
        "http_kind": "Gunicorn gthread 64 threads", "beat_schedule": "production intervals 30s/60s",
        "requests": options.requests, "concurrency": options.concurrency, "checks": {}, "status": "running",
        "python_executable": sys.executable,
        "dependency_versions": {name: version(name) for name in ("Flask", "Werkzeug", "Flask-Cors", "marshmallow", "celery", "redis", "gunicorn", "PyMySQL")},
        "isolated_ports": {"redis": redis_port, "http": http_port},
        "temporary_database": database_name}
    current_stage = "bootstrap"
    environment = os.environ.copy()
    environment.update({"DATABASE_URL": f"mysql+pymysql://{quote_plus(str(connection['user']))}:{quote_plus(str(connection['password']))}@{connection['host']}:{connection['port']}/{database_name}?charset=utf8mb4",
        "REDIS_URL": f"redis://127.0.0.1:{redis_port}/0", "CELERY_BROKER_URL": f"redis://127.0.0.1:{redis_port}/1",
        "CELERY_RESULT_BACKEND": f"redis://127.0.0.1:{redis_port}/2", "FLASK_ENV": "production",
        "COUPON_TASK_EAGER": "false", "DEMO_MODE": "true", "PYTHONPYCACHEPREFIX": "/tmp/codex-python-cache",
        "PYTHONPATH": str(PROJECT_ROOT / "backend")})
    os.environ.update(environment)
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

    def launch(name, arguments):
        log = open(Path(temporary.name) / f"{name}.log", "ab")
        process = subprocess.Popen(arguments, cwd=PROJECT_ROOT / "backend", env=environment,
            stdout=log, stderr=subprocess.STDOUT)
        log.close()
        processes.append(process)
        return process

    def stop(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def scalar(sql, arguments=()):
        with admin_db.cursor() as cursor:
            cursor.execute(sql, arguments)
            return cursor.fetchone()[0]

    def start_worker():
        return launch("worker", [sys.executable, "-m", "celery", "-A", "celery_runtime:celery_app", "worker",
            "--pool=solo", "--loglevel=WARNING", "--without-gossip", "--without-mingle", "--without-heartbeat"])

    try:
        with admin_db.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE `{database_name}`")
        launch("redis", [shutil.which("redis-server") or "redis-server", "--bind", "127.0.0.1", "--port", str(redis_port),
            "--save", "", "--appendonly", "no", "--dir", temporary.name])
        redis_client = redis.Redis(host="127.0.0.1", port=redis_port, decode_responses=True)
        wait_until(redis_client.ping, 10)
        from app import create_app
        from app.common.time_utils import current_time
        from app.coupons.models import CouponActivity, CouponClaimTask
        from app.coupons.redis_store import get_coupon_redis_store
        from app.extensions import db
        from app.orders.models import Order
        from app.users.models import User
        from flask_jwt_extended import create_access_token
        sys.path.insert(0, str(PROJECT_ROOT / "backend/tests"))
        from test_minimal_order_flow import seed_demo_data
        app = create_app()
        with app.app_context():
            db.create_all()
            seed_demo_data()
            shared_hash = User.query.first().password_hash
            load_users = [User(username=f"async_load_{index}", phone=f"17{index:09d}",
                password_hash=shared_hash, user_type="customer") for index in range(options.requests)]
            db.session.add_all(load_users)
            db.session.commit()
            user_ids = [user.id for user in load_users]
            tokens = [create_access_token(identity=str(user.id)) for user in load_users]
            brand = User.query.filter_by(username="brand_admin").one()
            brand_token = create_access_token(identity=str(brand.id))
            campaign = CouponActivity(activity_name_zh="隔离并发领取", activity_name_en="Isolated claim validation",
                start_at=current_time() - timedelta(hours=1), end_at=current_time() + timedelta(hours=2),
                total_stock=50, per_user_limit=1, discount_amount=5, minimum_order_amount=10, activity_status="active")
            db.session.add(campaign)
            db.session.commit()
            campaign_id = campaign.id
            store = get_coupon_redis_store()
            # 真实 Lua 错误结果不能被相同请求 ID 重试提升为成功。
            assert store.claim(900001, 1, "missing-stock")["code"] == -1
            assert store.claim(900001, 1, "missing-stock")["code"] == -1
            store.warmup(900002, 0)
            assert store.claim(900002, 1, "empty-stock")["code"] == 0
            assert store.claim(900002, 1, "empty-stock")["code"] == 0
            lock_token = store.acquire_reconcile_lock(campaign_id)
            redis_client.set(f"coupon:activity:{campaign_id}:reconcile:lock", "successor-token")
            store.release_reconcile_lock(campaign_id, lock_token)
            assert redis_client.get(f"coupon:activity:{campaign_id}:reconcile:lock") == "successor-token"
            redis_client.delete(f"coupon:activity:{campaign_id}:reconcile:lock")
            store.warmup(campaign_id, 50)
            report["checks"]["lua_failure_idempotency_and_lock_ownership"] = "passed"
        launch("api", [sys.executable, "-m", "gunicorn", "--bind", f"127.0.0.1:{http_port}", "--workers", "1",
            "--worker-class", "gthread", "--threads", "64", "--timeout", "120", "app:create_app()"])
        base = f"http://127.0.0.1:{http_port}/api"
        wait_until(lambda: request_json(base, "/health")[0] == 200, 15)
        print("Isolated MySQL/Redis/API ready; launching concurrent requests.", flush=True)
        current_stage = "concurrent_claims_worker_stopped"
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=options.concurrency) as executor:
            outcomes = list(executor.map(lambda pair: request_json(base, f"/coupons/activities/{campaign_id}/claim", pair[1], {"request_id": f"load-{pair[0]}"}), enumerate(tokens)))
        elapsed = time.perf_counter() - started
        accepted = [index for index, row in enumerate(outcomes) if row[0] == 202]
        latencies = sorted(row[2] for row in outcomes)
        assert len(accepted) == 50
        assert all(row[0] in (202, 400) for row in outcomes)
        assert scalar("SELECT COUNT(*) FROM coupon_claim_tasks WHERE activity_id=%s", (campaign_id,)) == 50
        assert scalar("SELECT COUNT(*) FROM user_coupons WHERE activity_id=%s", (campaign_id,)) == 0
        report["load"] = {"accepted": len(accepted), "exhausted": len(outcomes) - len(accepted), "unexpected_failures": 0,
            "elapsed_seconds": round(elapsed, 3), "requests_per_second": round(len(outcomes) / elapsed, 2),
            "average_response_ms": round(statistics.mean(latencies) * 1000, 2),
            "p95_response_ms": round(latencies[int(len(latencies) * .95) - 1] * 1000, 2)}
        report["checks"][current_stage] = "passed: 50 durable tasks, 0 persisted coupons while worker stopped"
        worker = start_worker()
        current_stage = "worker_restart_queue_recovery"
        wait_until(lambda: scalar("SELECT COUNT(*) FROM user_coupons WHERE activity_id=%s", (campaign_id,)) == 50)
        assert scalar("SELECT COUNT(*) FROM coupon_claim_tasks WHERE activity_id=%s AND task_status='succeeded'", (campaign_id,)) == 50
        with app.app_context():
            metrics = get_coupon_redis_store().metrics(campaign_id)
            assert metrics["success_count"] == 50 and metrics["remaining_stock"] == 0
            store = get_coupon_redis_store()
            assert store.claim(campaign_id, user_ids[accepted[0]], "different-request")["code"] == 2
            assert store.claim(campaign_id, user_ids[accepted[0]], f"load-{accepted[0]}")["code"] == 3
        report["checks"][current_stage] = "passed: Redis=50, MySQL=50, difference=0, repeated user not reissued"
        repeated = request_json(base, f"/coupons/activities/{campaign_id}/claim", tokens[accepted[0]], {"request_id": f"load-{accepted[0]}"})
        assert repeated[0] == 202
        redis_client.delete(f"coupon:activity:{campaign_id}:stock", f"coupon:activity:{campaign_id}:users", f"coupon:activity:{campaign_id}:success")
        restored = request_json(base, f"/coupons/activities/{campaign_id}/warmup", brand_token, {})
        assert restored[0] == 200 and restored[1]["data"]["remaining_stock"] == 0
        assert redis_client.scard(f"coupon:activity:{campaign_id}:users") == 50
        report["checks"]["redis_inventory_loss_recovery"] = "passed: restored 50 claimed users from MySQL, 0 stock reissued; original successful request remains idempotent after sold out"
        print("Concurrent limit and worker queue recovery passed; injecting database write failures.", flush=True)
        current_stage = "real_database_failure_retries"
        with app.app_context():
            fault = CouponActivity(activity_name_zh="隔离故障活动", start_at=current_time()-timedelta(hours=1), end_at=current_time()+timedelta(hours=1),
                total_stock=5, discount_amount=5, minimum_order_amount=0, activity_status="active")
            db.session.add(fault)
            db.session.commit()
            fault_id = fault.id
            get_coupon_redis_store().warmup(fault_id, 5)
        with admin_db.cursor() as cursor:
            cursor.execute(f"CREATE TRIGGER isolated_coupon_failure BEFORE INSERT ON user_coupons FOR EACH ROW BEGIN IF NEW.activity_id = {fault_id} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='isolated verification failure'; END IF; END")
        response = request_json(base, f"/coupons/activities/{fault_id}/claim", tokens[0], {"request_id": "fault-injection"})
        assert response[0] == 202
        failed_task_id = response[1]["data"]["task"]["id"]
        wait_until(lambda: scalar("SELECT task_status FROM coupon_claim_tasks WHERE id=%s", (failed_task_id,)) == "dead", 45)
        assert scalar("SELECT retry_count FROM coupon_claim_tasks WHERE id=%s", (failed_task_id,)) == 3
        with admin_db.cursor() as cursor:
            cursor.execute("DROP TRIGGER isolated_coupon_failure")
        manual = request_json(base, f"/coupons/tasks/{failed_task_id}/retry", brand_token, {})
        assert manual[0] == 200 and manual[1]["data"]["task_status"] == "succeeded"
        report["checks"][current_stage] = "passed: 3 real MySQL write failures -> dead -> explicit manual retry -> succeeded"
        current_stage = "second_worker_restart_and_compensation"
        stop(worker)
        response = request_json(base, f"/coupons/activities/{fault_id}/claim", tokens[1], {"request_id": "restart-pending"})
        assert response[0] == 202
        restart_task_id = response[1]["data"]["task"]["id"]
        assert scalar("SELECT task_status FROM coupon_claim_tasks WHERE id=%s", (restart_task_id,)) == "pending"
        worker = start_worker()
        wait_until(lambda: scalar("SELECT task_status FROM coupon_claim_tasks WHERE id=%s", (restart_task_id,)) == "succeeded")
        with app.app_context():
            assert get_coupon_redis_store().claim(fault_id, user_ids[2], "redis-only")["code"] == 1
        reconciliation = request_json(base, f"/coupons/activities/{fault_id}/reconcile", brand_token, {})
        assert reconciliation[0] == 200
        assert scalar("SELECT COUNT(*) FROM coupon_claim_tasks WHERE activity_id=%s AND user_id=%s", (fault_id,user_ids[2])) == 1
        report["checks"][current_stage] = "passed: second restart recovered pending task; Redis-only success generated durable compensation task"
        current_stage = "real_beat_activity_payment_and_compensation_scans"
        with app.app_context():
            scheduled = CouponActivity(activity_name_zh="隔离定时开始", start_at=current_time()+timedelta(seconds=2),
                end_at=current_time()+timedelta(hours=1), total_stock=1, discount_amount=1, minimum_order_amount=0, activity_status="scheduled")
            db.session.add(scheduled)
            from app.orders.services import create_order
            user = db.session.get(User, user_ids[3])
            created = create_order(user, {"store_id":1, "order_type":"pickup", "items":[{"store_product_id":1,"quantity":1}]})
            order_id = created["id"]
            order = db.session.get(Order, order_id)
            order.payment_deadline = current_time()-timedelta(minutes=1)
            db.session.commit()
            scheduled_id = scheduled.id
        launch("beat", [sys.executable, "-m", "celery", "-A", "celery_runtime:celery_app", "beat", "--loglevel=WARNING",
            "--schedule", str(Path(temporary.name)/"beat-schedule")])
        print("Fault retries, manual recovery and compensation passed; awaiting actual Beat intervals (up to 75 seconds).", flush=True)
        wait_until(lambda: scalar("SELECT activity_status FROM coupon_activities WHERE id=%s",(scheduled_id,)) == "active"
            and scalar("SELECT order_status FROM orders WHERE id=%s",(order_id,)) == "canceled"
            and scalar("SELECT COUNT(*) FROM user_coupons WHERE activity_id=%s AND user_id=%s",(fault_id,user_ids[2])) == 1, 80)
        assert scalar("SELECT reserved_stock FROM store_products WHERE id=1") == 0
        report["checks"][current_stage] = "passed: scheduled activated, overdue order canceled and inventory released, compensation persisted by Beat"
        report["status"] = "passed"
        print("All isolated asynchronous checks passed.", flush=True)
    except Exception as error:
        report["status"] = "failed"
        report["failure"] = {"stage": current_stage, "type": type(error).__name__}
        print(f"Isolated verification failed at {current_stage}: {type(error).__name__}", flush=True)
        raise
    finally:
        for process in reversed(processes):
            stop(process)
        with admin_db.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
        database_removed = scalar("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=%s", (database_name,)) == 0
        admin_db.close()
        temporary.cleanup()
        ports_closed = {}
        for name, port in (("redis", redis_port), ("http", http_port)):
            with socket.socket() as probe:
                probe.settimeout(1)
                ports_closed[name] = probe.connect_ex(("127.0.0.1", port)) != 0
        report["cleanup_verified"] = {
            "database_removed": database_removed,
            "launched_processes_exited": all(process.poll() is not None for process in processes),
            "temporary_directory_removed": not Path(temporary.name).exists(),
            "redis_port_closed": ports_closed["redis"], "http_port_closed": ports_closed["http"],
        }
        if not all(report["cleanup_verified"].values()):
            report["status"] = "failed"
            report["failure"] = {"stage": "cleanup", "type": "ResourceCleanupIncomplete"}
        report["cleanup"] = "isolated processes stopped and temporary database removed" if all(report["cleanup_verified"].values()) else "cleanup incomplete"
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        (PROJECT_ROOT / options.output).write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
