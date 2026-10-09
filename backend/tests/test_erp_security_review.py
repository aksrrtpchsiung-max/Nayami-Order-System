"""
文件名称：test_erp_security_review.py
文件用途：独立审查 ERP 系统管理、认证和审计安全修复
主要职责：验证双令牌撤销、权限变更即时失效、审计快照与历史敏感账号隔离、配置白名单和失败日志脱敏
所属业务模块：安全回归测试
创建时间：2026-09-08 17:30
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

import json

from app.audit.models import OperationLog
from app.extensions import db
from app.system.models import SystemSetting
from app.users.models import User
from test_minimal_order_flow import app, client, login, auth_headers


def _tokens(client, username="store_staff_demo", password="Store123!"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.get_json()["data"]


def _assert_revoked(client, tokens):
    assert client.get("/api/auth/me", headers=auth_headers(tokens["access_token"])).status_code == 401
    assert client.post("/api/auth/refresh", headers=auth_headers(tokens["refresh_token"])).status_code == 401


def _system_headers(client):
    return auth_headers(login(client, "system_admin", "Admin123!"))


def test_logout_revokes_access_and_refresh_tokens(client):
    tokens = _tokens(client)
    assert client.post("/api/auth/logout", headers=auth_headers(tokens["access_token"])).status_code == 200
    _assert_revoked(client, tokens)


def test_password_reset_revokes_existing_sessions(client):
    tokens = _tokens(client)
    response = client.post("/api/system/accounts/2/reset-password", headers=_system_headers(client))
    assert response.status_code == 200
    _assert_revoked(client, tokens)
    new_tokens = _tokens(client, password=response.get_json()["data"]["temporary_password"])
    assert client.get("/api/auth/me", headers=auth_headers(new_tokens["access_token"])).status_code == 200


def test_role_change_requires_new_session_and_records_actual_after_snapshot(client):
    tokens = _tokens(client)
    response = client.patch("/api/system/accounts/2", headers=_system_headers(client), json={"role_code": "store_manager", "store_id": 1})
    assert response.status_code == 200
    _assert_revoked(client, tokens)
    log = OperationLog.query.filter_by(operation_type="update_account", target_id=2).one()
    assert log.before_snapshot["roles"] == ["store_staff"]
    assert log.after_snapshot["roles"] == ["store_manager"]
    assert log.after_snapshot["store_bindings"][0]["binding_type"] == "manager"
    token = login(client, "store_staff_demo", "Store123!")
    assert client.get("/api/store/report?store_id=1", headers=auth_headers(token)).status_code == 200


def test_disabling_then_reenabling_does_not_resurrect_old_tokens(client):
    tokens = _tokens(client)
    headers = _system_headers(client)
    assert client.patch("/api/system/accounts/2", headers=headers, json={"is_active": False}).status_code == 200
    _assert_revoked(client, tokens)
    assert client.patch("/api/system/accounts/2", headers=headers, json={"is_active": True}).status_code == 200
    _assert_revoked(client, tokens)
    assert client.get("/api/auth/me", headers=auth_headers(login(client, "store_staff_demo", "Store123!"))).status_code == 200


def test_store_reassignment_revokes_old_session_and_audits_new_binding(client):
    tokens = _tokens(client)
    assert client.patch("/api/system/accounts/2", headers=_system_headers(client), json={"store_id": 2}).status_code == 200
    _assert_revoked(client, tokens)
    log = OperationLog.query.filter_by(operation_type="update_account", target_id=2).one()
    assert [binding["store_id"] for binding in log.before_snapshot["store_bindings"]] == [1]
    assert [binding["store_id"] for binding in log.after_snapshot["store_bindings"]] == [2]
    token = login(client, "store_staff_demo", "Store123!")
    assert client.get("/api/store/orders?store_id=1", headers=auth_headers(token)).status_code == 403
    assert client.get("/api/store/orders?store_id=2", headers=auth_headers(token)).status_code == 200


def test_old_system_password_audit_stays_private_after_demotion(client):
    system = _system_headers(client)
    assert client.patch("/api/system/accounts/2", headers=system, json={"role_code": "system_admin"}).status_code == 200
    assert client.post("/api/system/accounts/2/reset-password", headers=system).status_code == 200
    reset_log = OperationLog.query.filter_by(operation_type="reset_password", target_id=2).one()
    assert reset_log.after_snapshot["roles"] == ["system_admin"]
    reset_log_id = reset_log.id
    assert client.patch("/api/system/accounts/2", headers=system, json={"role_code": "store_staff", "store_id": 1}).status_code == 200
    brand = auth_headers(login(client, "brand_admin", "Admin123!"))
    assert client.get(f"/api/audit/logs/{reset_log_id}", headers=brand).status_code == 404
    listed = client.get("/api/audit/logs?operation_module=account", headers=brand).get_json()["data"]
    assert reset_log_id not in [entry["id"] for entry in listed]
    assert client.get(f"/api/audit/logs/{reset_log_id}", headers=system).status_code == 200


def test_configuration_mutations_require_system_role_and_whitelisted_types(client):
    brand = auth_headers(login(client, "brand_admin", "Admin123!"))
    assert client.patch("/api/system/config", headers=brand, json={"demo_mode": False}).status_code == 403
    assert SystemSetting.query.count() == 0
    system = _system_headers(client)
    for payload in ({"JWT_SECRET_KEY": "injected"}, {"payment_timeout_minutes": 1}, {"demo_mode": "false"}, {"payment_description": ["bad"]}):
        assert client.patch("/api/system/config", headers=system, json=payload).status_code == 400
    assert SystemSetting.query.count() == 0
    response = client.patch("/api/system/config", headers=system, json={"demo_mode": False, "default_language": "en-US"})
    assert response.status_code == 200
    assert response.get_json()["data"]["demo_mode"] is False
    assert response.get_json()["data"]["default_language"] == "en-US"
    log = OperationLog.query.filter_by(operation_type="update_config").one()
    assert log.before_snapshot == {"demo_mode": True, "default_language": "zh-CN"}
    assert log.after_snapshot == {"demo_mode": False, "default_language": "en-US"}


def test_rejected_request_audit_does_not_capture_request_secrets(client):
    customer = auth_headers(login(client, "customer_demo", "Nayami123!"))
    secret = "sensitive-payment-secret-4111111111111111"
    response = client.patch("/api/system/config?private=" + secret, headers=customer, json={
        "demo_mode": False, "card_number": secret, "cvv": secret, "payment_password": secret,
        "verification_code": secret, "password": secret,
    })
    assert response.status_code == 403
    log = OperationLog.query.filter_by(operation_module="security", operation_type="request_rejected").order_by(OperationLog.id.desc()).first()
    assert log is not None
    serialized = json.dumps({"before": log.before_snapshot, "after": log.after_snapshot, "reason": log.failure_reason})
    assert secret not in serialized
    assert log.after_snapshot == {"method": "PATCH", "route": "/api/system/config"}
