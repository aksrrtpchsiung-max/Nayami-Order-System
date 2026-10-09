"""
文件名称：test_erp_security.py
文件用途：验证 ERP 权限、安全审计、持久化配置和会话撤销
主要职责：覆盖拒绝旁路、敏感账号日志隔离、参数校验和设置生效
所属业务模块：后端测试
创建时间：2026-09-08 17:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

import pytest

from test_minimal_order_flow import app, client, login, auth_headers
from app.audit.models import OperationLog
from app.extensions import db
from app.stores.models import Store
from app.users.models import Role, User, UserRole


def test_config_reads_actual_values_and_persists_allowed_edits(app, client):
    app.config.update(DEMO_MODE=False, PAYMENT_TIMEOUT_MINUTES=23)
    headers = auth_headers(login(client, "system_admin", "Admin123!"))
    current = client.get("/api/system/config", headers=headers).json["data"]
    assert current["demo_mode"] is False
    assert current["payment_timeout_minutes"] == 23
    response = client.patch("/api/system/config", headers=headers, json={
        "default_language": "en-US", "demo_mode": True, "payment_description": "Test payments only",
    })
    assert response.status_code == 200
    db.session.remove()
    current = client.get("/api/system/config", headers=headers).json["data"]
    assert current["default_language"] == "en-US"
    assert current["demo_mode"] is True
    assert OperationLog.query.filter_by(operation_module="system", operation_type="update_config").count() == 1


@pytest.mark.parametrize("payload", [{"payment_timeout_minutes": 1}, {"demo_mode": "false"}, {"default_language": []}, {"payment_description": 99}])
def test_config_rejects_core_rules_and_invalid_types(client, payload):
    headers = auth_headers(login(client, "system_admin", "Admin123!"))
    assert client.patch("/api/system/config", headers=headers, json=payload).status_code == 400


def test_brand_cannot_write_or_read_system_config(client):
    headers = auth_headers(login(client, "brand_admin", "Admin123!"))
    assert client.get("/api/system/config", headers=headers).status_code == 403
    assert client.patch("/api/system/config", headers=headers, json={"demo_mode": False}).status_code == 403


def test_logout_revokes_access_and_refresh_tokens(client):
    credentials = client.post("/api/auth/login", json={"username": "customer_demo", "password": "Nayami123!"}).json["data"]
    headers = auth_headers(credentials["access_token"])
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.post("/api/auth/refresh", headers=auth_headers(credentials["refresh_token"])).status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers(login(client, "customer_demo", "Nayami123!"))).status_code == 200


def test_password_reset_revokes_previous_session(client):
    staff_headers = auth_headers(login(client, "store_staff_demo", "Store123!"))
    system_headers = auth_headers(login(client, "system_admin", "Admin123!"))
    staff_id = User.query.filter_by(username="store_staff_demo").one().id
    assert client.post(f"/api/system/accounts/{staff_id}/reset-password", headers=system_headers).status_code == 200
    assert client.get("/api/auth/me", headers=staff_headers).status_code == 401


def test_login_and_rejection_audits_do_not_store_credentials(client):
    client.post("/api/auth/login", json={"username": "system_admin", "password": "Secret-bad-password"})
    login(client, "system_admin", "Admin123!")
    customer_headers = auth_headers(login(client, "customer_demo", "Nayami123!"))
    assert client.get("/api/store/orders?store_id=1", headers=customer_headers).status_code == 403
    logs = OperationLog.query.all()
    assert any(log.operation_type == "login" and log.operation_result == "success" for log in logs)
    assert any(log.operation_type == "login" and log.operation_result == "rejected" for log in logs)
    assert any(log.operation_type == "request_rejected" for log in logs)
    assert "Secret-bad-password" not in str([(log.before_snapshot, log.after_snapshot, log.failure_reason) for log in logs])


def test_brand_cannot_read_system_account_audit_by_id_or_list(client):
    system_headers = auth_headers(login(client, "system_admin", "Admin123!"))
    system_id = User.query.filter_by(username="system_admin").one().id
    assert client.patch(f"/api/system/accounts/{system_id}", headers=system_headers, json={"default_language": "en-US"}).status_code == 200
    log = OperationLog.query.filter_by(operation_module="account", target_id=system_id).one()
    brand_headers = auth_headers(login(client, "brand_admin", "Admin123!"))
    assert client.get(f"/api/audit/logs/{log.id}", headers=brand_headers).status_code == 404
    assert client.get("/api/audit/logs?operation_module=account", headers=brand_headers).json["data"] == []
    assert client.get(f"/api/audit/logs/{log.id}", headers=system_headers).status_code == 200


def test_disabled_store_blocks_bound_staff_but_retains_binding(client):
    headers = auth_headers(login(client, "store_staff_demo", "Store123!"))
    db.session.get(Store, 1).is_active = False
    db.session.commit()
    response = client.get("/api/store/orders?store_id=1", headers=headers)
    assert response.status_code == 403
    assert response.json["error"]["code"] == "store_unavailable"
    assert client.get("/api/auth/me", headers=headers).json["data"]["store_bindings"][0]["is_active"] is False


@pytest.mark.parametrize("payload", [[], "invalid", 3, None])
def test_non_object_json_returns_consistent_validation_error(client, payload):
    import json
    response = client.post("/api/auth/login", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_json"


def test_account_partial_update_preserves_existing_store_binding(client):
    headers = auth_headers(login(client, "system_admin", "Admin123!"))
    manager = User.query.filter_by(username="store_manager_demo").one()
    response = client.patch(f"/api/system/accounts/{manager.id}", headers=headers, json={"default_language": "en-US"})
    assert response.status_code == 200
    assert response.json["data"]["store_bindings"][0]["store_id"] == 1
    assert client.patch(f"/api/system/accounts/{manager.id}", headers=headers, json={"is_active": "false"}).status_code == 400
    assert client.patch(f"/api/system/accounts/{manager.id}", headers=headers, json={"phone": "1" * 100}).status_code == 400


def test_invalid_audit_filter_returns_400(client):
    headers = auth_headers(login(client, "system_admin", "Admin123!"))
    assert client.get("/api/audit/logs?operator_id=abc", headers=headers).status_code == 400
    assert client.get("/api/audit/logs?limit=-1", headers=headers).status_code == 400


@pytest.mark.parametrize("value", ["²", "9" * 5000])
def test_non_ascii_or_oversized_numeric_query_returns_400(client, value):
    response = client.get("/api/stores", query_string={"store_id": value})
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_filter"


def test_brand_cannot_manage_legacy_account_with_any_system_role(client):
    target = User.query.filter_by(username="store_staff_demo").one()
    system_role = Role.query.filter_by(role_code="system_admin").one()
    db.session.add(UserRole(user_id=target.id, role_id=system_role.id))
    db.session.commit()
    headers = auth_headers(login(client, "brand_admin", "Admin123!"))
    accounts = client.get("/api/system/accounts", headers=headers).json["data"]
    assert target.id not in [account["id"] for account in accounts]
    assert client.patch(f"/api/system/accounts/{target.id}", headers=headers, json={"default_language": "en-US"}).status_code == 403
    assert client.post(f"/api/system/accounts/{target.id}/reset-password", headers=headers).status_code == 403
