"""
文件名称：verify_erp_commerce_concurrency.py
文件用途：在一次性 MySQL 库实测 ERP 交易竞争及锁一致性
主要职责：验证库存防超卖、短码并发唯一、重复付款、取消付款竞争、履约退款竞争与退款幂等并保存 JSON 证据
所属业务模块：验收脚本
创建时间：2026-09-08 17:30
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from threading import Barrier
from uuid import uuid4

import pymysql
from sqlalchemy.engine import URL

from _runtime import PROJECT_ROOT, database_parts

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "backend/tests"))

from app import create_app
from app.common.errors import BusinessError
from app.config import TestConfig
from app.extensions import db
from app.catalog.models import StoreProduct
from app.inventory.models import InventoryLog
from app.orders.models import Order
from app.orders.services import create_order, cancel_pending_order, update_store_order_status
from app.payments.models import PaymentRecord, RefundRecord
from app.payments.services import simulate_payment_success, request_refund, simulate_refund_success
from app.users.models import User, Role, UserRole
from app.system.services import reset_account_password, update_system_config
from app.auth.services import logout_user
from app.audit.models import OperationLog
from test_minimal_order_flow import seed_demo_data


def main() -> None:
    """
    函数名称：main
    函数用途：隔离运行真实 MySQL 并发用例并保存证据
    参数说明：从项目环境读取连接，固定新建随机临时数据库
    返回值说明：测试成功时输出证据路径，失败时抛出断言
    核心逻辑：每个场景重置临时库，线程各自使用独立 Flask 上下文与数据库会话，最终删除临时库
    异常或失败情况：连接失败或任何业务/库存断言不满足即失败；不修改配置中的业务库
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    values = database_parts()
    database_name = f"nayami_commerce_verify_{os.getpid()}_{uuid4().hex[:8]}"
    admin = pymysql.connect(host=values["host"], port=int(values["port"]), user=values["user"], password=values["password"], autocommit=True)
    with admin.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    database_uri = URL.create("mysql+pymysql", username=str(values["user"]), password=str(values["password"]), host=str(values["host"]), port=int(values["port"]), database=database_name)

    class ConcurrencyConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = database_uri
        SQLALCHEMY_ENGINE_OPTIONS = {"pool_size": 24, "max_overflow": 4, "pool_pre_ping": True}

    application = create_app(ConcurrencyConfig)
    results = []

    def reset(stock=20):
        with application.app_context():
            db.drop_all()
            db.create_all()
            seed_demo_data()
            db.session.get(StoreProduct, 1).current_stock = stock
            db.session.commit()

    def pending():
        with application.app_context():
            return create_order(db.session.get(User, 1), {"store_id": 1, "items": [{"store_product_id": 1, "quantity": 1}]})

    def parallel(actions):
        barrier = Barrier(len(actions))

        def worker(action):
            with application.app_context():
                barrier.wait(timeout=15)
                try:
                    value = action()
                    return {"result": "ok", "value": value}
                except BusinessError as error:
                    db.session.rollback()
                    return {"result": "rejected", "code": error.code}
                finally:
                    db.session.remove()

        with ThreadPoolExecutor(max_workers=len(actions)) as executor:
            return list(executor.map(worker, actions))

    def payment(payment_id):
        return simulate_payment_success(db.session.get(User, 1), payment_id, {})

    def stock_state():
        with application.app_context():
            row = db.session.get(StoreProduct, 1)
            return {"current_stock": row.current_stock, "reserved_stock": row.reserved_stock}

    try:
        reset(stock=5)
        actions = [lambda: create_order(db.session.get(User, 1), {"store_id": 1, "items": [{"store_product_id": 1, "quantity": 1}]}) for _ in range(20)]
        outcomes = parallel(actions)
        assert sum(value["result"] == "ok" for value in outcomes) == 5
        assert stock_state() == {"current_stock": 5, "reserved_stock": 5}
        results.append({"scenario": "20_concurrent_orders_stock_5", "succeeded": 5, "rejected": 15, **stock_state()})
        print("PASS 20 concurrent orders for stock 5", flush=True)

        reset()
        orders = [pending() for _ in range(12)]
        outcomes = parallel([lambda payment_id=order["payment"]["id"]: payment(payment_id) for order in orders])
        assert all(value["result"] == "ok" for value in outcomes)
        codes = [value["value"]["order"]["pickup_code"] for value in outcomes]
        assert len(set(codes)) == 12
        assert stock_state() == {"current_stock": 8, "reserved_stock": 0}
        results.append({"scenario": "12_parallel_payments", "unique_pickup_codes": 12, **stock_state()})
        print("PASS 12 parallel payments and unique pickup codes", flush=True)

        reset()
        order = pending()
        outcomes = parallel([lambda: payment(order["payment"]["id"]) for _ in range(12)])
        assert all(value["result"] == "ok" for value in outcomes)
        assert stock_state() == {"current_stock": 19, "reserved_stock": 0}
        with application.app_context():
            assert InventoryLog.query.filter_by(change_type="confirm_deduct").count() == 1
        results.append({"scenario": "12_duplicate_payment_callbacks", "stock_deductions": 1, **stock_state()})
        print("PASS duplicate payment callbacks", flush=True)

        race_outcomes = []
        for _ in range(8):
            reset()
            order = pending()
            outcomes = parallel([lambda: payment(order["payment"]["id"]), lambda: cancel_pending_order(db.session.get(User, 1), order["id"])])
            assert sum(value["result"] == "ok" for value in outcomes) == 1
            with application.app_context():
                status = db.session.get(Order, order["id"]).order_status
                payment_status = db.session.get(PaymentRecord, order["payment"]["id"]).payment_status
            assert status in {"paid", "canceled"}
            assert payment_status == ("succeeded" if status == "paid" else "canceled")
            assert stock_state() == {"current_stock": 19 if status == "paid" else 20, "reserved_stock": 0}
            race_outcomes.append(status)
        results.append({"scenario": "payment_vs_cancellation", "iterations": 8, "final_states": race_outcomes, "consistent": True})
        print("PASS payment vs cancellation races", flush=True)

        race_outcomes = []
        for _ in range(8):
            reset()
            order = pending()
            with application.app_context():
                payment(order["payment"]["id"])
                update_store_order_status(db.session.get(User, 3), order["id"], {"target_status": "accepted"})
            outcomes = parallel([
                lambda: update_store_order_status(db.session.get(User, 3), order["id"], {"target_status": "preparing"}),
                lambda: request_refund(db.session.get(User, 1), order["id"], {"reason": "顾客取消"}),
            ])
            assert sum(value["result"] == "ok" for value in outcomes) == 1
            with application.app_context():
                status = db.session.get(Order, order["id"]).order_status
                assert RefundRecord.query.count() == (1 if status == "refund_pending" else 0)
            assert status in {"preparing", "refund_pending"}
            race_outcomes.append(status)
        results.append({"scenario": "fulfillment_vs_customer_refund", "iterations": 8, "final_states": race_outcomes, "consistent": True})
        print("PASS fulfillment vs refund races", flush=True)

        reset()
        order = pending()
        with application.app_context():
            payment(order["payment"]["id"])
            refund = request_refund(db.session.get(User, 1), order["id"], {"reason": "重复退款验收"})
        outcomes = parallel([lambda: simulate_refund_success(db.session.get(User, 1), refund["id"]) for _ in range(12)])
        assert all(value["result"] == "ok" for value in outcomes)
        assert stock_state() == {"current_stock": 20, "reserved_stock": 0}
        with application.app_context():
            assert InventoryLog.query.filter_by(change_type="refund_restore").count() == 1
            assert db.session.get(Order, order["id"]).order_status == "refunded"
        results.append({"scenario": "12_duplicate_refund_callbacks", "stock_restorations": 1, **stock_state()})
        print("PASS duplicate refund callbacks", flush=True)


        reset()
        actions = [lambda: reset_account_password(db.session.get(User, 5), 2) for _ in range(6)]
        actions += [lambda: logout_user(db.session.get(User, 2)) for _ in range(6)]
        outcomes = parallel(actions)
        assert all(value["result"] == "ok" for value in outcomes)
        with application.app_context():
            token_version = db.session.get(User, 2).token_version
            assert token_version == 12
        results.append({"scenario": "6_password_resets_and_6_logouts", "expected_token_version": 12, "actual_token_version": token_version})
        print("PASS concurrent password resets and logouts", flush=True)

        reset()
        with application.app_context():
            second_admin = User(username="second_system_admin", password_hash="unusable-for-login", user_type="admin")
            db.session.add(second_admin)
            db.session.flush()
            second_admin_id = second_admin.id
            db.session.add(UserRole(user_id=second_admin_id, role_id=Role.query.filter_by(role_code="system_admin").one().id))
            db.session.commit()
        outcomes = parallel([
            lambda: update_system_config(db.session.get(User, 5), {"payment_description": "First administrator description"}),
            lambda: update_system_config(db.session.get(User, second_admin_id), {"payment_description": "Second administrator description"}),
        ])
        assert all(value["result"] == "ok" for value in outcomes)
        with application.app_context():
            logs = OperationLog.query.filter_by(operation_type="update_config").order_by(OperationLog.id).all()
            assert len(logs) == 2
            assert logs[1].before_snapshot == logs[0].after_snapshot
        results.append({"scenario": "2_system_admins_first_config_write", "succeeded": 2, "audit_snapshots_form_serial_chain": True})
        print("PASS concurrent administrators configuration writes", flush=True)
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()
        with admin.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
        admin.close()
    artifact = PROJECT_ROOT / "tests/artifacts/erp_commerce_concurrency.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"checked_at": datetime.now().isoformat(), "database": "isolated_mysql_temporary_database", "business_database_modified": False, "results": results}, ensure_ascii=False, indent=2) + "\n")
    print(f"Evidence saved: {artifact}")


if __name__ == "__main__":
    main()
