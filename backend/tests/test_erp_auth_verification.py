"""
文件名称：test_erp_auth_verification.py
文件用途：保证短信验证码测试存储与真实 Redis 的有效期、冷却和消费规则一致
主要职责：验证一次性消费、五次失败锁定、过期拒绝和重发次数重置
所属业务模块：认证安全回归测试
创建时间：2026-09-08 17:50
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

import pytest

from app.auth import services
from app.common.errors import BusinessError
from test_minimal_order_flow import app


def _assert_cooldown(phone):
    with pytest.raises(BusinessError) as rejected:
        services.send_verification_code(phone)
    assert rejected.value.status_code == 429
    assert rejected.value.code == "verification_code_too_frequent"


def test_successful_consumption_retains_independent_send_cooldown(app, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(services.time, "monotonic", lambda: clock[0])
    phone = "18899600001"
    code = services.send_verification_code(phone)["verification_code"]
    assert services._consume_verification_code(phone, code) is True
    assert services._consume_verification_code(phone, code) is False
    assert services._consume_verification_code(phone, "None") is False
    _assert_cooldown(phone)
    clock[0] += 60
    assert services.send_verification_code(phone)["expires_in_seconds"] == 300


def test_fifth_failure_invalidates_code_and_keeps_send_cooldown(app):
    phone = "18899600002"
    code = services.send_verification_code(phone)["verification_code"]
    store = services._verification_store()
    for count in range(1, 6):
        assert services._consume_verification_code(phone, "000000") is False
        if count < 5:
            assert store[phone]["code"] == code
    assert services._consume_verification_code(phone, code) is False
    _assert_cooldown(phone)


def test_expired_code_is_rejected_and_can_be_reissued(app, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(services.time, "monotonic", lambda: clock[0])
    phone = "18899600003"
    code = services.send_verification_code(phone)["verification_code"]
    clock[0] += 300
    assert services._consume_verification_code(phone, code) is False
    assert services.send_verification_code(phone)["verification_code"] == code
    assert services._consume_verification_code(phone, code) is True


def test_reissue_resets_old_failed_attempts(app, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(services.time, "monotonic", lambda: clock[0])
    phone = "18899600004"
    services.send_verification_code(phone)
    for _ in range(4):
        assert services._consume_verification_code(phone, "000000") is False
    clock[0] += 60
    code = services.send_verification_code(phone)["verification_code"]
    assert services._consume_verification_code(phone, "000000") is False
    assert services._verification_store()[phone]["attempts"] == 1
    assert services._consume_verification_code(phone, code) is True
