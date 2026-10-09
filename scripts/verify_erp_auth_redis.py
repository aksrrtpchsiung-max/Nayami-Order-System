"""
文件名称：verify_erp_auth_redis.py
文件用途：使用独立真实 Redis 验收短信验证码安全边界
主要职责：验证发送冷却、验证码过期、五次失败失效、并发消费及重发次数重置，并清理临时服务
所属业务模块：认证安全验收
创建时间：2026-09-08 17:47
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from threading import Barrier, Event
import time

import redis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app import create_app
from app.auth import services as auth_services
from app.common.errors import BusinessError
from app.config import TestConfig
from app.extensions import db
from app.system.models import SystemSetting


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.025)
    raise AssertionError("Expected Redis state did not become visible before timeout")


def main() -> None:
    """
    函数名称：main
    函数用途：执行真实 Redis 验证码验收并保存证据
    参数说明：--probe-only 可仅输出发送/校验竞争探针；默认执行全部场景
    返回值说明：成功后写入 tests/artifacts/erp_auth_redis.json
    核心逻辑：使用随机回环端口与临时 SQLite，调用实际认证服务，最终关闭进程并删除临时目录
    异常或失败情况：连接、断言或服务失败时退出非零且仍清理全部临时资源
    相关业务规则：记录真实签发 TTL；过期分支用缩短 Redis TTL 加速，不声称等待完整 300 秒
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args()
    executable = shutil.which("redis-server") or "/opt/homebrew/bin/redis-server"
    if not Path(executable).is_file():
        raise RuntimeError("redis-server is required for this acceptance script")
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        port = candidate.getsockname()[1]
    evidence = {"checked_at": datetime.now().isoformat(), "python_version": sys.version.split()[0], "real_redis": True,
        "isolated_process": True, "business_database_modified": False, "results": []}
    process = None
    with tempfile.TemporaryDirectory(prefix="nayami_auth_redis_") as temporary:
        directory = Path(temporary)
        with (directory / "redis.log").open("w") as log:
            process = subprocess.Popen([executable, "--bind", "127.0.0.1", "--port", str(port), "--save", "", "--appendonly", "no", "--dir", str(directory), "--protected-mode", "yes"], stdout=log, stderr=subprocess.STDOUT)
        server = redis.Redis(host="127.0.0.1", port=port, decode_responses=True, socket_timeout=3, socket_connect_timeout=3)
        application = None
        original_store = auth_services._verification_store
        try:
            def ready():
                if process.poll() is not None:
                    raise RuntimeError("Temporary Redis exited before becoming ready")
                try:
                    return server.ping()
                except redis.ConnectionError:
                    return False
            wait_until(ready)
            class AuthRedisConfig(TestConfig):
                TESTING = False
                REDIS_URL = f"redis://127.0.0.1:{port}/0"
                SQLALCHEMY_DATABASE_URI = f"sqlite:///{directory / 'auth.sqlite'}"
                DEMO_MODE = True
            application = create_app(AuthRedisConfig)
            with application.app_context():
                db.create_all()
                assert not isinstance(auth_services._verification_store(), dict)

            # 在旧实现 SET code 后与清理 attempts 之间暂停；Lua 实现则在原子操作完成后暂停。
            code_written, resume_sender = Event(), Event()
            class PausedRedis:
                def __getattr__(self, name):
                    return getattr(server, name)
                def set(self, key, value, *arguments, **keywords):
                    result = server.set(key, value, *arguments, **keywords)
                    if key.endswith(":code"):
                        code_written.set()
                        assert resume_sender.wait(5)
                    return result
                def eval(self, script, *arguments):
                    result = server.eval(script, *arguments)
                    if "'SET'" in script.upper() or '"SET"' in script.upper():
                        if result:
                            code_written.set()
                            assert resume_sender.wait(5)
                    return result
            phone = "18899500001"
            code_key, attempts_key = f"auth:sms:{phone}:code", f"auth:sms:{phone}:attempts"
            server.set(code_key, "654321", ex=300)
            server.set(attempts_key, 4, ex=300)
            auth_services._verification_store = lambda: PausedRedis()
            def resend():
                with application.app_context():
                    auth_services.send_verification_code(phone)
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(resend)
                assert code_written.wait(5)
                try:
                    with application.app_context():
                        assert auth_services._consume_verification_code(phone, "000000") is False
                finally:
                    resume_sender.set()
                pending.result()
            survived = server.get(code_key) == auth_services.DEMO_VERIFICATION_CODE
            auth_services._verification_store = original_store
            if args.probe_only:
                print(json.dumps({"fresh_code_survived_resend_race": survived, "attempts_after_race": server.get(attempts_key)}))
                return
            assert survived, "Resending a code must atomically reset previous failed attempts"
            assert server.get(attempts_key) == "1"
            evidence["results"].append({"scenario": "resend_vs_fifth_old_failure", "fresh_code_survived": True, "fresh_attempt_count": 1})
            print("PASS atomic resend resets old attempt counters", flush=True)

            phone = "18899500002"
            with application.app_context():
                result = auth_services.send_verification_code(phone)
                ttl_code = server.ttl(f"auth:sms:{phone}:code")
                ttl_cooldown = server.ttl(f"auth:sms:{phone}:cooldown")
                assert 299 <= ttl_code <= 300 and 59 <= ttl_cooldown <= 60
                try:
                    auth_services.send_verification_code(phone)
                    raise AssertionError("Sending during cooldown should fail")
                except BusinessError as error:
                    assert error.status_code == 429 and error.code == "verification_code_too_frequent"
                assert auth_services._consume_verification_code(phone, result["verification_code"]) is True
                assert auth_services._consume_verification_code(phone, result["verification_code"]) is False
                assert server.ttl(f"auth:sms:{phone}:cooldown") > 0
                try:
                    auth_services.send_verification_code(phone)
                    raise AssertionError("Successful consumption must retain send cooldown")
                except BusinessError as error:
                    assert error.status_code == 429
            evidence["results"].append({"scenario": "issued_ttl_and_consumption_cooldown", "code_ttl_seconds": ttl_code, "cooldown_ttl_seconds": ttl_cooldown, "second_send_status": 429, "consumption_preserves_cooldown": True})
            print("PASS real Redis 300-second code TTL and 60-second send cooldown", flush=True)

            phone = "18899500003"
            with application.app_context():
                result = auth_services.send_verification_code(phone)
                for attempt in range(1, 6):
                    assert auth_services._consume_verification_code(phone, "000000") is False
                    if attempt < 5:
                        assert server.exists(f"auth:sms:{phone}:code") == 1
                assert server.exists(f"auth:sms:{phone}:code") == 0
                assert auth_services._consume_verification_code(phone, result["verification_code"]) is False
                assert server.ttl(f"auth:sms:{phone}:cooldown") > 0
            evidence["results"].append({"scenario": "five_failed_attempts", "failures_until_invalidated": 5, "correct_code_after_lockout": False, "cooldown_preserved": True})
            print("PASS five failures invalidate code without clearing cooldown", flush=True)

            phone = "18899500004"
            with application.app_context():
                result = auth_services.send_verification_code(phone)
            server.pexpire(f"auth:sms:{phone}:code", 120)
            wait_until(lambda: not server.exists(f"auth:sms:{phone}:code"))
            with application.app_context():
                assert auth_services._consume_verification_code(phone, result["verification_code"]) is False
            server.pexpire(f"auth:sms:{phone}:cooldown", 120)
            wait_until(lambda: not server.exists(f"auth:sms:{phone}:cooldown"))
            with application.app_context():
                auth_services.send_verification_code(phone)
            assert server.ttl(f"auth:sms:{phone}:code") >= 299
            evidence["results"].append({"scenario": "redis_expiry_and_resend", "expired_code_rejected": True, "resend_after_cooldown_expiry": True,
                "expiry_test_acceleration": "TTL shortened to 120 ms with PEXPIRE after checking issued 300/60 second TTLs"})
            print("PASS actual Redis expiration and resend after cooldown expiry", flush=True)

            phone = "18899500005"
            with application.app_context():
                result = auth_services.send_verification_code(phone)
            barrier = Barrier(24)
            def consume():
                with application.app_context():
                    barrier.wait(5)
                    return auth_services._consume_verification_code(phone, result["verification_code"])
            with ThreadPoolExecutor(max_workers=24) as executor:
                successes = list(executor.map(lambda _: consume(), range(24)))
            assert sum(successes) == 1
            evidence["results"].append({"scenario": "24_concurrent_consumers", "success_count": 1, "rejected_count": 23})
            print("PASS 24 concurrent consumers yield exactly one success", flush=True)

            phone = "18899500006"
            send_barrier = Barrier(16)
            def send():
                with application.app_context():
                    send_barrier.wait(5)
                    try:
                        auth_services.send_verification_code(phone)
                        return 201
                    except BusinessError as error:
                        return error.status_code
            with ThreadPoolExecutor(max_workers=16) as executor:
                statuses = list(executor.map(lambda _: send(), range(16)))
            assert statuses.count(201) == 1 and statuses.count(429) == 15
            evidence["results"].append({"scenario": "16_concurrent_senders", "success_count": 1, "cooldown_rejected_count": 15})
            print("PASS 16 concurrent senders yield one code issuance", flush=True)

            with application.app_context():
                db.session.add(SystemSetting(key="demo_mode", value=False))
                db.session.commit()
                result = auth_services.send_verification_code("18899500007")
                assert "verification_code" not in result
                stored = server.get("auth:sms:18899500007:code")
                assert stored and len(stored) == 6 and stored.isdigit()
            evidence["results"].append({"scenario": "production_response_redaction", "code_not_in_response": True, "six_digit_code_stored": True})
            print("PASS non-demo response does not expose verification code", flush=True)
        finally:
            auth_services._verification_store = original_store
            if application is not None:
                with application.app_context():
                    db.session.remove()
                    db.engine.dispose()
            server.close()
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    evidence["temporary_resources_removed"] = True
    target = PROJECT_ROOT / "tests/artifacts/erp_auth_redis.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+"\n")
    print(f"Evidence saved: {target}")


if __name__ == "__main__":
    main()
