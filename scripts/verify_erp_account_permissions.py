"""
文件名称：verify_erp_account_permissions.py
文件用途：在独立 MySQL 库复现并验证后台账号权限与绑定的旧快照竞争
主要职责：验证角色升级后的品牌权限隔离、部分更新保留最新角色、门店切换及审计一致性
所属业务模块：账号安全验收
创建时间：2026-09-08 18:14
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import sys
from uuid import uuid4

import pymysql
from sqlalchemy import text
from sqlalchemy.engine import URL

from _runtime import PROJECT_ROOT, database_parts

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "backend/tests"))

from app import create_app
from app.audit.models import OperationLog
from app.common.decorators import get_current_user
from app.common.errors import BusinessError
from app.common.security import verify_password
from app.config import TestConfig
from app.extensions import db
from app.system.services import DEFAULT_TEMP_PASSWORD, reset_account_password, update_account
from app.users.models import User
from flask_jwt_extended import create_access_token
from test_minimal_order_flow import seed_demo_data


def main() -> None:
    """
    函数名称：main
    函数用途：记录实际 MySQL 可重复读下的修前和修后账号安全结果
    参数说明：--phase before 记录待修代码行为；默认 after 必须满足所有安全断言
    返回值说明：写入 tests/artifacts/erp_account_permissions.json 的对应阶段
    核心逻辑：当前请求先认证建立快照，另一连接提交角色或门店变化，当前请求再执行业务服务
    异常或失败情况：连接或安全断言失败则非零退出，最终始终移除随机临时数据库
    相关业务规则：仅读取项目数据库连接配置，绝不访问或修改业务数据库
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), default="after")
    phase = parser.parse_args().phase
    values = database_parts()
    database_name = f"nayami_account_verify_{os.getpid()}_{uuid4().hex[:8]}"
    admin = pymysql.connect(host=values["host"], port=int(values["port"]), user=values["user"], password=values["password"], autocommit=True)
    application = None
    results = []
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        database_uri = URL.create("mysql+pymysql", username=str(values["user"]), password=str(values["password"]), host=str(values["host"]), port=int(values["port"]), database=database_name)

        class AccountConcurrencyConfig(TestConfig):
            SQLALCHEMY_DATABASE_URI = database_uri
            SQLALCHEMY_ENGINE_OPTIONS = {"isolation_level": "REPEATABLE READ", "pool_size": 4, "pool_pre_ping": True}

        application = create_app(AccountConcurrencyConfig)

        def reset():
            with application.app_context():
                db.drop_all()
                db.create_all()
                seed_demo_data()

        def change_in_other_request(payload):
            with application.app_context():
                update_account(db.session.get(User, 5), 2, payload)
                db.session.remove()

        def interleave(actor_id, concurrent_change, requested_action):
            with application.app_context():
                token = create_access_token(identity=str(actor_id), additional_claims={"token_version": 0})
            with application.test_request_context("/api/system/accounts/2", headers={"Authorization": f"Bearer {token}"}):
                actor = get_current_user()
                isolation = db.session.execute(text("SELECT @@transaction_isolation")).scalar_one()
                assert isolation == "REPEATABLE-READ"
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(change_in_other_request, concurrent_change).result(timeout=20)
                try:
                    requested_action(actor)
                    return {"status": 200}
                except BusinessError as error:
                    db.session.rollback()
                    return {"status": error.status_code, "error_code": error.code}
                finally:
                    db.session.remove()

        def state():
            with application.app_context():
                target = db.session.get(User, 2)
                logs = OperationLog.query.filter_by(operation_module="account", target_id=2).order_by(OperationLog.id).all()
                result = {
                    "roles": sorted(link.role.role_code for link in target.role_links),
                    "active_store_ids": sorted(binding.store_id for binding in target.store_bindings if binding.is_active),
                    "token_version": target.token_version,
                    "password_was_reset": verify_password(target.password_hash, DEFAULT_TEMP_PASSWORD),
                    "reset_log_count": sum(log.operation_type == "reset_password" for log in logs),
                    "last_audit_roles_before": (logs[-1].before_snapshot or {}).get("roles", []) if logs else [],
                    "last_audit_roles_after": (logs[-1].after_snapshot or {}).get("roles", []) if logs else [],
                    "last_audit_stores_before": sorted(binding["store_id"] for binding in (logs[-1].before_snapshot or {}).get("store_bindings", [])) if logs else [],
                    "last_audit_stores_after": sorted(binding["store_id"] for binding in (logs[-1].after_snapshot or {}).get("store_bindings", [])) if logs else [],
                }
                return result

        reset()
        outcome = interleave(4, {"role_code": "system_admin"}, lambda actor: reset_account_password(actor, 2))
        result = {"scenario": "brand_reset_after_system_promotion", **outcome, **state()}
        result["passed"] = result["status"] == 403 and not result["password_was_reset"] and result["reset_log_count"] == 0 and result["roles"] == ["system_admin"]
        results.append(result)

        reset()
        outcome = interleave(4, {"role_code": "system_admin"}, lambda actor: update_account(actor, 2, {"phone": "18899700002"}))
        result = {"scenario": "brand_update_after_system_promotion", **outcome, **state()}
        result["passed"] = result["status"] == 403 and result["roles"] == ["system_admin"]
        results.append(result)

        reset()
        outcome = interleave(5, {"role_code": "store_manager", "store_id": 2}, lambda actor: update_account(actor, 2, {"phone": "18899700002"}))
        result = {"scenario": "partial_update_retains_latest_role_and_store", **outcome, **state()}
        result["passed"] = result["status"] == 200 and result["roles"] == ["store_manager"] and result["active_store_ids"] == [2] and result["last_audit_roles_before"] == ["store_manager"] and result["last_audit_roles_after"] == ["store_manager"] and result["last_audit_stores_before"] == [2] and result["last_audit_stores_after"] == [2] and result["token_version"] == 1
        results.append(result)

        reset()
        outcome = interleave(5, {"store_id": 2}, lambda actor: update_account(actor, 2, {"store_id": 1}))
        result = {"scenario": "explicit_rebind_uses_latest_binding", **outcome, **state()}
        result["passed"] = result["status"] == 200 and result["roles"] == ["store_staff"] and result["active_store_ids"] == [1] and result["last_audit_stores_before"] == [2] and result["last_audit_stores_after"] == [1] and result["token_version"] == 2
        results.append(result)
    finally:
        if application is not None:
            with application.app_context():
                db.session.remove()
                db.engine.dispose()
        with admin.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
        admin.close()

    artifact = PROJECT_ROOT / "tests/artifacts/erp_account_permissions.json"
    evidence = json.loads(artifact.read_text()) if artifact.exists() else {}
    evidence[phase] = {"checked_at": datetime.now().isoformat(), "python_version": sys.version.split()[0], "database": "isolated_mysql_temporary_database", "isolation_level": "REPEATABLE-READ", "business_database_modified": False, "temporary_database_removed": True, "results": results}
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": phase, "results": [{"scenario": result["scenario"], "status": result["status"], "passed": result["passed"]} for result in results]}, ensure_ascii=False, indent=2))
    print(f"Evidence saved: {artifact}")
    if phase == "after":
        assert all(result["passed"] for result in results), "Account concurrency safety regression"


if __name__ == "__main__":
    main()
