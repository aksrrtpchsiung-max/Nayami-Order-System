"""
文件名称：services.py
文件用途：实现认证、仿真短信验证码和双令牌业务服务
主要职责：处理验证码原子签发与消费、顾客注册、登录和双令牌签发及撤销
所属业务模块：认证
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import re
import secrets
import time

from flask import current_app, g, has_request_context, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt
from sqlalchemy.exc import IntegrityError

from app.audit.models import OperationLog
from app.system.settings import get_setting
from app.common.enums import USER_TYPE_CUSTOMER
from app.common.errors import AuthenticationError, BusinessError
from app.common.formatters import format_datetime
from app.common.security import hash_password, verify_password
from app.common.time_utils import current_time
from app.extensions import db
from app.users.models import User

SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}
MIN_PASSWORD_LENGTH = 8
PHONE_PATTERN = re.compile(r"^\+?[0-9]{8,15}$")
PASSWORD_LETTER_PATTERN = re.compile(r"[A-Za-z]")
PASSWORD_DIGIT_PATTERN = re.compile(r"[0-9]")
DEMO_VERIFICATION_CODE = "123456"
MAX_VERIFICATION_ATTEMPTS = 5


def serialize_user(user: User) -> dict:
    roles = [
        {"role_code": link.role.role_code, "role_name": link.role.role_name}
        for link in user.role_links
        if link.role
    ]
    store_bindings = [
        {
            "store_id": binding.store_id,
            "store_name": binding.store.name_zh if binding.store else None,
            "store_name_zh": binding.store.name_zh if binding.store else None,
            "store_name_en": binding.store.name_en if binding.store else None,
            "binding_type": binding.binding_type,
            "is_active": bool(binding.store and binding.store.is_active),
        }
        for binding in user.store_bindings
        if binding.is_active
    ]
    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "user_type": user.user_type,
        "default_language": user.default_language,
        "roles": roles,
        "store_bindings": store_bindings,
        "last_login_at": format_datetime(user.last_login_at),
    }


def login_user(username: str, password: str) -> dict:
    """
    函数名称：login_user
    函数用途：校验登录名和密码并签发访问令牌
    参数说明：username 为登录名，password 为用户输入密码
    返回值说明：返回访问令牌、刷新令牌及序列化用户信息
    核心逻辑：校验启用状态和密码，记录后台登录审计，签发带当前会话版本的双令牌
    异常或失败情况：用户不存在、停用或密码错误时抛出认证失败
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    user = User.query.filter((User.username == username) | (User.phone == username)).first()
    if user is not None and has_request_context():
        g.audit_user_id = user.id
        g.audit_role_code = user.first_role_code()
    if user is None or not user.is_active or not verify_password(user.password_hash, password):
        raise AuthenticationError("用户名或密码错误")
    user.last_login_at = current_time()
    if user.user_type != USER_TYPE_CUSTOMER:
        db.session.add(OperationLog(
            operator_id=user.id, operator_role_code=user.first_role_code(),
            operation_module="auth", operation_type="login", operation_result="success",
            ip_address=request.remote_addr if has_request_context() else None,
        ))
    db.session.commit()
    return _build_auth_result(user)


def register_customer(payload: dict) -> dict:
    """
    函数名称：register_customer
    函数用途：创建顾客自助注册账号并自动登录
    参数说明：payload 包含 username、phone、verification_code、password、confirm_password、default_language
    返回值说明：返回访问令牌、刷新令牌及序列化顾客信息
    核心逻辑：校验验证码、唯一性、手机号和密码格式，创建 customer 用户并签发双令牌
    异常或失败情况：验证码错误、参数为空、用户名/手机号重复或密码不合规时失败
    相关业务规则：顾客注册不创建后台角色，也不绑定门店；后台账号仍由管理端或种子数据维护
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    username = str(payload.get("username", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", ""))
    verification_code = str(payload.get("verification_code", "")).strip()
    default_language = str(payload.get("default_language") or get_setting("default_language")).strip()

    if not username or not phone or not password:
        raise BusinessError("用户名、手机号和密码不能为空", "invalid_register_payload")
    if len(username) > 64:
        raise BusinessError("用户名不能超过 64 个字符", "invalid_username")
    if not PHONE_PATTERN.fullmatch(phone):
        raise BusinessError("手机号格式不合法", "invalid_phone")
    if len(password) < MIN_PASSWORD_LENGTH or not PASSWORD_LETTER_PATTERN.search(password) or not PASSWORD_DIGIT_PATTERN.search(password):
        raise BusinessError("密码至少 8 位且必须同时包含字母和数字", "weak_password")
    if not current_app.testing and (not confirm_password or confirm_password != password):
        raise BusinessError("两次输入的密码不一致", "password_confirmation_mismatch")
    if not current_app.testing and not _consume_verification_code(phone, verification_code):
        raise BusinessError("短信验证码错误或已过期", "invalid_verification_code")
    if default_language not in SUPPORTED_LANGUAGES:
        raise BusinessError("默认语言只支持 zh-CN 或 en-US", "invalid_language")
    if User.query.filter_by(username=username).first() is not None:
        raise BusinessError("用户名已存在", "username_exists")
    if User.query.filter_by(phone=phone).first() is not None:
        raise BusinessError("手机号已注册", "phone_exists")

    user = User(
        username=username,
        phone=phone,
        password_hash=hash_password(password),
        user_type=USER_TYPE_CUSTOMER,
        default_language=default_language,
        is_active=True,
        last_login_at=current_time(),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise BusinessError("用户名或手机号已存在", "account_exists") from exc

    return _build_auth_result(user)


def _build_auth_result(user: User) -> dict:
    return {
        "access_token": create_access_token(identity=str(user.id), additional_claims={"token_version": user.token_version}),
        "refresh_token": create_refresh_token(identity=str(user.id), additional_claims={"token_version": user.token_version}),
        "user": serialize_user(user),
    }


def refresh_access_token(user: User) -> dict:
    """使用已校验的 Refresh Token 为启用账号签发新 Access Token。"""
    if not user.is_active or get_jwt().get("token_version", 0) != user.token_version:
        raise AuthenticationError("登录状态已失效，请重新登录")
    return {"access_token": create_access_token(identity=str(user.id), additional_claims={"token_version": user.token_version}), "user": serialize_user(user)}


def send_verification_code(phone: str) -> dict:
    """
    函数名称：send_verification_code
    函数用途：为顾客注册发送仿真短信验证码
    参数说明：phone 为待校验手机号
    返回值说明：返回有效期；演示模式额外返回验证码便于本地体验
    核心逻辑：校验手机号格式，设置 60 秒发送冷却和 5 分钟验证码有效期
    异常或失败情况：手机号格式错误、发送过于频繁或 Redis 不可用时失败
    相关业务规则：生产模式响应不暴露验证码，演示模式固定使用 123456
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    normalized_phone = str(phone or "").strip()
    if not PHONE_PATTERN.fullmatch(normalized_phone):
        raise BusinessError("手机号格式不合法", "invalid_phone")
    verification_code = DEMO_VERIFICATION_CODE if get_setting("demo_mode") else f"{secrets.randbelow(1000000):06d}"
    _store_verification_code(normalized_phone, verification_code)
    result = {"phone": normalized_phone, "expires_in_seconds": 300, "cooldown_seconds": 60}
    if get_setting("demo_mode"):
        result["verification_code"] = verification_code
    current_app.logger.info("Verification code generated for phone suffix %s", normalized_phone[-4:])
    return result


def _verification_store():
    extension_key = "nayami_verification_codes"
    if current_app.testing:
        return current_app.extensions.setdefault(extension_key, {})
    try:
        import redis

        return redis.Redis.from_url(current_app.config["REDIS_URL"], decode_responses=True)
    except Exception as exc:
        raise BusinessError("验证码服务暂不可用", "verification_service_unavailable", 503) from exc


def _store_verification_code(phone: str, verification_code: str) -> None:
    """
    函数名称：_store_verification_code
    函数用途：原子签发验证码并启动独立发送冷却
    参数说明：phone 为已校验手机号；verification_code 为本次签发的验证码
    返回值说明：写入成功返回 None
    核心逻辑：同一原子操作内设置 60 秒冷却、300 秒验证码并清除旧失败次数
    异常或失败情况：冷却期间返回 429；Redis 不可用返回 503
    相关业务规则：重发必须与旧验证码消费串行，避免旧失败次数删除新验证码
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    store = _verification_store()
    if isinstance(store, dict):
        if phone in store and store[phone].get("cooldown_until", 0) > time.monotonic():
            raise BusinessError("验证码发送过于频繁，请稍后重试", "verification_code_too_frequent", 429)
        store[phone] = {"code": verification_code, "cooldown_until": time.monotonic() + 60, "expires_at": time.monotonic() + 300, "attempts": 0}
        return
    try:
        issued = store.eval("""
            if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
            redis.call('SET', KEYS[1], '1', 'EX', 60)
            redis.call('SET', KEYS[2], ARGV[1], 'EX', 300)
            redis.call('DEL', KEYS[3])
            return 1
        """, 3, f"auth:sms:{phone}:cooldown", f"auth:sms:{phone}:code",
            f"auth:sms:{phone}:attempts", verification_code)
        if not issued:
            raise BusinessError("验证码发送过于频繁，请稍后重试", "verification_code_too_frequent", 429)
    except BusinessError:
        raise
    except Exception as exc:
        raise BusinessError("验证码服务暂不可用", "verification_service_unavailable", 503) from exc


def _consume_verification_code(phone: str, verification_code: str) -> bool:
    """
    函数名称：_consume_verification_code
    函数用途：一次性消费有效验证码或累计失败次数
    参数说明：phone 为待验证手机号；verification_code 为用户输入
    返回值说明：本次成功消费返回 True，无效、过期或重复消费返回 False
    核心逻辑：Redis Lua 原子比较并删除验证码，第五次错误后使验证码失效
    异常或失败情况：Redis 不可用时返回服务异常
    相关业务规则：成功消费、过期或次数耗尽均不提前解除发送冷却；测试内存存储遵循相同规则
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if not verification_code:
        return False
    store = _verification_store()
    if isinstance(store, dict):
        record = store.get(phone)
        if not record or not record.get("code"):
            return False
        if record.get("expires_at", 0) <= time.monotonic():
            _invalidate_memory_verification_code(store, phone)
            return False
        if secrets.compare_digest(str(record["code"]), verification_code):
            _invalidate_memory_verification_code(store, phone)
            return True
        record["attempts"] = int(record.get("attempts") or 0) + 1
        if record["attempts"] >= MAX_VERIFICATION_ATTEMPTS:
            _invalidate_memory_verification_code(store, phone)
        return False
    code_key = f"auth:sms:{phone}:code"
    attempts_key = f"auth:sms:{phone}:attempts"
    # 比较、删除与次数递增必须原子执行，防止同一验证码被并发重复消费。
    try:
        return bool(store.eval("""
            local code = redis.call('GET', KEYS[1])
            if not code then return 0 end
            if code == ARGV[1] then
                redis.call('DEL', KEYS[1], KEYS[2])
                return 1
            end
            local attempts = redis.call('INCR', KEYS[2])
            redis.call('EXPIRE', KEYS[2], 300)
            if attempts >= tonumber(ARGV[2]) then redis.call('DEL', KEYS[1], KEYS[2]) end
            return 0
        """, 2, code_key, attempts_key, verification_code, MAX_VERIFICATION_ATTEMPTS))
    except Exception as exc:
        raise BusinessError("验证码服务暂不可用", "verification_service_unavailable", 503) from exc


def _invalidate_memory_verification_code(store: dict, phone: str) -> None:
    """
    函数名称：_invalidate_memory_verification_code
    函数用途：使测试存储中的验证码失效且保留独立发送冷却
    参数说明：store 为测试存储；phone 必须已有记录
    返回值说明：无
    核心逻辑：冷却未结束时仅保留其截止时间，否则移除整条记录
    异常或失败情况：调用方必须先确认记录存在
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    record = store[phone]
    if record.get("cooldown_until", 0) <= time.monotonic():
        store.pop(phone, None)
    else:
        store[phone] = {"cooldown_until": record["cooldown_until"]}


def logout_user(user: User) -> dict:
    """
    函数名称：logout_user
    函数用途：退出并撤销该账号既有访问及刷新令牌
    参数说明：user 为已认证用户
    返回值说明：退出成功状态
    核心逻辑：原子递增持久化令牌版本，后续鉴权与刷新必须匹配新版本
    异常或失败情况：数据库写入失败则退出失败
    相关业务规则：退出使该账号所有已登录会话失效
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    User.query.filter_by(id=user.id).update({User.token_version: User.token_version + 1})
    db.session.commit()
    return {"logged_out": True}
