"""
文件名称：services.py
文件用途：实现系统后台账号、角色和非交易配置服务
主要职责：管理后台账号与会话撤销，维护角色和门店绑定，持久化白名单配置并记录操作日志
所属业务模块：系统管理
创建时间：2026-05-26 16:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from flask import current_app
from sqlalchemy.orm.attributes import set_committed_value

from app.audit.models import OperationLog
from app.system.models import SystemSetting
from app.system.settings import SETTING_DEFAULTS, get_setting
from app.common.enums import (
    OPERATION_RESULT_SUCCESS,
    ROLE_BRAND_ADMIN,
    ROLE_STORE_MANAGER,
    ROLE_STORE_STAFF,
    ROLE_SYSTEM_ADMIN,
    USER_TYPE_ADMIN,
    USER_TYPE_STAFF,
)
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.common.formatters import format_datetime
from app.common.security import hash_password
from app.extensions import db
from app.stores.models import Store
from app.users.models import Role, User, UserRole, UserStoreBinding

BACKEND_ROLES = (ROLE_STORE_STAFF, ROLE_STORE_MANAGER, ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)
BRAND_MANAGED_ROLES = (ROLE_STORE_STAFF, ROLE_STORE_MANAGER)
STORE_SCOPED_ROLES = (ROLE_STORE_STAFF, ROLE_STORE_MANAGER)
SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}
DEFAULT_TEMP_PASSWORD = "Admin123!"


def list_roles(user) -> list[dict]:
    """
    函数名称：list_roles
    函数用途：返回后台固定角色列表
    参数说明：user 为当前后台用户
    返回值说明：返回角色编码、名称、说明和权限点
    核心逻辑：系统管理员查看全部角色，品牌管理员仅查看可管理角色
    异常或失败情况：非品牌或系统管理员访问时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_account_viewer(user)
    query = Role.query.order_by(Role.id.asc())
    if user.has_any_role((ROLE_BRAND_ADMIN,)) and not user.has_any_role((ROLE_SYSTEM_ADMIN,)):
        query = query.filter(Role.role_code.in_(BRAND_MANAGED_ROLES))
    return [serialize_role(role) for role in query.all()]


def get_system_config(user) -> dict:
    """
    函数名称：get_system_config
    函数用途：返回实际运行配置和数据库覆盖值
    参数说明：user 为当前系统管理员
    返回值说明：配置摘要；不包含密钥、数据库地址等敏感值
    核心逻辑：校验角色后读取白名单配置和只读交易参数
    异常或失败情况：非系统管理员访问时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    _ensure_system_admin(user)
    return {
        **{key: get_setting(key) for key in SETTING_DEFAULTS},
        "supported_languages": ["zh-CN", "en-US"],
        "currency": current_app.config["DEFAULT_CURRENCY"],
        "payment_methods": ["wechat", "alipay", "bank_card"],
        "payment_mode": current_app.config["PAYMENT_MODE"],
        "payment_timeout_minutes": current_app.config["PAYMENT_TIMEOUT_MINUTES"],
        "coupon_max_retries": current_app.config["COUPON_MAX_RETRIES"],
        "config_storage": "database_overrides",
    }


def update_system_config(user, payload: dict) -> dict:
    """
    函数名称：update_system_config
    函数用途：维护允许修改的非交易配置
    参数说明：user 为系统管理员，payload 仅允许默认语言、演示模式和支付说明
    返回值说明：返回更新后的配置摘要
    核心逻辑：严格校验白名单和类型，同事务保存设置与前后快照审计
    异常或失败情况：越权、未知配置、错误类型或超长说明被拒绝
    相关业务规则：支付时限等既有交易规则不开放热修改
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    _ensure_system_admin(user)
    if not payload or set(payload) - SETTING_DEFAULTS.keys():
        raise BusinessError("包含不允许修改的配置项", "invalid_system_config")
    if "default_language" in payload and payload["default_language"] not in ("zh-CN", "en-US"):
        raise BusinessError("默认语言只支持 zh-CN 或 en-US", "invalid_language")
    if "demo_mode" in payload and type(payload["demo_mode"]) is not bool:
        raise BusinessError("演示模式必须为布尔值", "invalid_system_config")
    if "payment_description" in payload and (
        not isinstance(payload["payment_description"], str) or len(payload["payment_description"]) > 500
    ):
        raise BusinessError("支付说明必须为 500 字符以内文本", "invalid_system_config")
    # 所有系统管理员共享同一角色行锁，首次配置写入和审计快照保持串行。
    Role.query.filter_by(role_code=ROLE_SYSTEM_ADMIN).populate_existing().with_for_update().one()
    locked_settings = SystemSetting.query.populate_existing().with_for_update().all()
    before = get_system_config(user)
    for key, value in payload.items():
        setting = db.session.get(SystemSetting, key)
        if setting is None:
            setting = SystemSetting(key=key)
            db.session.add(setting)
        setting.value = value
        setting.updated_by = user.id
    db.session.add(OperationLog(
        operator_id=user.id, operator_role_code=user.first_role_code(),
        operation_module="system", operation_type="update_config",
        before_snapshot={key: before[key] for key in payload}, after_snapshot=payload,
        operation_result=OPERATION_RESULT_SUCCESS,
    ))
    db.session.commit()
    return get_system_config(user)


def list_accounts(user) -> list[dict]:
    """
    函数名称：list_accounts
    函数用途：查询后台账号列表
    参数说明：user 为当前品牌或系统管理员
    返回值说明：返回后台账号、角色、门店绑定和启用状态
    核心逻辑：系统管理员查看全部后台账号，品牌管理员仅查看门店员工和经理
    异常或失败情况：非后台管理角色访问时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_account_viewer(user)
    accounts = User.query.filter(User.user_type.in_((USER_TYPE_STAFF, USER_TYPE_ADMIN))).order_by(User.id.asc()).all()
    if _is_brand_only(user):
        accounts = [account for account in accounts if _has_only_brand_managed_roles(account)]
    return [serialize_account(account) for account in accounts]


def create_account(user, payload: dict) -> dict:
    """
    函数名称：create_account
    函数用途：创建后台账号并分配角色和门店范围
    参数说明：user 为操作人，payload 包含 username、phone、role_code、store_id、password 等字段
    返回值说明：返回账号摘要和一次性临时密码
    核心逻辑：校验角色管理范围、账号唯一性、门店绑定要求，写入用户、角色、门店绑定和操作日志
    异常或失败情况：账号重复、角色非法、缺少门店绑定或权限不足时失败
    相关业务规则：品牌管理员不能创建系统管理员，门店角色必须绑定门店
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_account_viewer(user)
    username = str(payload.get("username") or "").strip()
    phone = str(payload.get("phone") or "").strip() or None
    password = str(payload.get("password") or DEFAULT_TEMP_PASSWORD)
    role_code = str(payload.get("role_code") or "").strip()
    default_language = str(payload.get("default_language") or "zh-CN").strip()
    store_id = payload.get("store_id")
    if not username or len(username) > 64 or (phone and len(phone) > 32) or not role_code:
        raise BusinessError("用户名和角色不能为空", "invalid_account_payload")
    if len(password) < 8 or len(password) > 128:
        raise BusinessError("密码长度不能少于 8 位", "weak_password")
    if default_language not in SUPPORTED_LANGUAGES:
        raise BusinessError("默认语言只支持 zh-CN 或 en-US", "invalid_language")
    _ensure_role_can_be_managed(user, role_code)
    if User.query.filter_by(username=username).first() is not None:
        raise BusinessError("用户名已存在", "username_exists")
    if phone and User.query.filter_by(phone=phone).first() is not None:
        raise BusinessError("手机号已注册", "phone_exists")
    role = _get_role(role_code)
    store = _validate_store_binding(role_code, store_id)

    account = User(
        username=username,
        phone=phone,
        password_hash=hash_password(password),
        user_type=_user_type_for_role(role_code),
        default_language=default_language,
        is_active=_strict_active(payload.get("is_active", True)),
    )
    db.session.add(account)
    db.session.flush()
    db.session.add(UserRole(user_id=account.id, role_id=role.id))
    if store:
        db.session.add(
            UserStoreBinding(
                user_id=account.id,
                store_id=store.id,
                binding_type=_binding_type_for_role(role_code),
                is_active=True,
            )
        )
    db.session.add(
        _build_account_log(
            user,
            "create_account",
            account.id,
            None,
            {"username": username, "role_code": role_code, "store_id": store.id if store else None},
        )
    )
    db.session.commit()
    return {"account": serialize_account(account), "temporary_password": password}


def update_account(user, account_id: int, payload: dict) -> dict:
    """
    函数名称：update_account
    函数用途：更新后台账号基础信息、角色和门店绑定
    参数说明：user 为操作人，account_id 为目标账号 ID，payload 为可更新字段
    返回值说明：返回更新后的账号摘要
    核心逻辑：锁定目标账号并当前读角色和绑定，校验管理范围，保留未提交字段并撤销发生权限变化的旧会话
    异常或失败情况：账号不存在、角色非法、缺少门店绑定、越权或尝试停用/降权自身时失败
    相关业务规则：角色、启用状态和门店绑定变更后，旧访问与刷新令牌均失效
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_account_viewer(user)
    account = User.query.filter_by(id=account_id).populate_existing().with_for_update().first()
    if account is None or account.user_type not in (USER_TYPE_STAFF, USER_TYPE_ADMIN):
        raise NotFoundError("后台账号不存在")
    _load_locked_account_permissions(account)
    _ensure_target_can_be_managed(user, account)
    before_snapshot = _build_account_snapshot(account)

    if "phone" in payload:
        next_phone = str(payload.get("phone") or "").strip() or None
        if next_phone and len(next_phone) > 32:
            raise BusinessError("手机号长度不能超过 32 字符", "invalid_phone")
        if next_phone and User.query.filter(User.phone == next_phone, User.id != account.id).first() is not None:
            raise BusinessError("手机号已注册", "phone_exists")
        account.phone = next_phone
    if "default_language" in payload:
        default_language = str(payload.get("default_language") or "").strip()
        if default_language not in SUPPORTED_LANGUAGES:
            raise BusinessError("默认语言只支持 zh-CN 或 en-US", "invalid_language")
        account.default_language = default_language
    if "is_active" in payload:
        if account.id == user.id and not _strict_active(payload.get("is_active")):
            raise BusinessError("不能停用当前登录账号", "cannot_disable_self")
        account.is_active = _strict_active(payload.get("is_active"))

    role_code = str(payload.get("role_code") or _primary_role_code(account) or "").strip()
    _ensure_role_can_be_managed(user, role_code)
    role = _get_role(role_code)
    active_binding = next((binding for binding in account.store_bindings if binding.is_active), None)
    binding_id = payload.get("store_id", active_binding.store_id if active_binding else None)
    store = _validate_store_binding(role_code, binding_id)
    if account.id == user.id and role_code != _primary_role_code(account):
        raise BusinessError("不能变更当前登录账号的角色", "cannot_change_own_role")
    account.user_type = _user_type_for_role(role_code)
    _replace_user_role(account, role)
    _sync_store_binding(account, role_code, store)

    db.session.flush()
    _load_locked_account_permissions(account)
    after_snapshot = _build_account_snapshot(account)
    if any(before_snapshot[key] != after_snapshot[key] for key in ("roles", "store_bindings", "is_active")):
        account.token_version += 1
    db.session.add(_build_account_log(user, "update_account", account.id, before_snapshot, after_snapshot))
    db.session.commit()
    return serialize_account(account)


def reset_account_password(user, account_id: int) -> dict:
    """
    函数名称：reset_account_password
    函数用途：重置后台账号演示密码
    参数说明：user 为操作人，account_id 为目标后台账号 ID
    返回值说明：返回账号摘要和一次性临时密码
    核心逻辑：锁定账号并当前读角色和绑定，校验管理范围，更新密码及令牌版本并记录最新角色审计
    异常或失败情况：账号不存在或越权时失败
    相关业务规则：操作日志不保存明文密码，临时密码只在响应中返回一次
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_account_viewer(user)
    account = User.query.filter_by(id=account_id).populate_existing().with_for_update().first()
    if account is None or account.user_type not in (USER_TYPE_STAFF, USER_TYPE_ADMIN):
        raise NotFoundError("后台账号不存在")
    _load_locked_account_permissions(account)
    _ensure_target_can_be_managed(user, account)
    account.password_hash = hash_password(DEFAULT_TEMP_PASSWORD)
    account.token_version += 1
    db.session.add(
        _build_account_log(
            user,
            "reset_password",
            account.id,
            {"password_hash": "hidden", "roles": [link.role.role_code for link in account.role_links if link.role]},
            {"password_hash": "reset", "roles": [link.role.role_code for link in account.role_links if link.role]},
        )
    )
    db.session.commit()
    return {"account": serialize_account(account), "temporary_password": DEFAULT_TEMP_PASSWORD}


def serialize_role(role: Role) -> dict:
    return {
        "id": role.id,
        "role_code": role.role_code,
        "role_name": role.role_name,
        "description": role.description,
        "permission_codes": role.permission_codes or [],
    }


def serialize_account(account: User) -> dict:
    active_bindings = [binding for binding in account.store_bindings if binding.is_active]
    return {
        "id": account.id,
        "username": account.username,
        "phone": account.phone,
        "user_type": account.user_type,
        "default_language": account.default_language,
        "is_active": bool(account.is_active),
        "last_login_at": format_datetime(account.last_login_at),
        "created_at": format_datetime(account.created_at),
        "updated_at": format_datetime(account.updated_at),
        "roles": [
            {"role_code": link.role.role_code, "role_name": link.role.role_name}
            for link in account.role_links
            if link.role
        ],
        "store_bindings": [
            {
                "store_id": binding.store_id,
                "store_name": binding.store.name_zh if binding.store else None,
                "store_name_zh": binding.store.name_zh if binding.store else None,
                "store_name_en": binding.store.name_en if binding.store else None,
                "binding_type": binding.binding_type,
                "is_active": bool(binding.store and binding.store.is_active),
            }
            for binding in active_bindings
        ],
    }


def _ensure_system_admin(user) -> None:
    if not user.has_any_role((ROLE_SYSTEM_ADMIN,)):
        raise ForbiddenError("只有系统管理员可以访问系统后台")


def _ensure_account_viewer(user) -> None:
    if not user.has_any_role((ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能管理后台账号")


def _is_brand_only(user) -> bool:
    return user.has_any_role((ROLE_BRAND_ADMIN,)) and not user.has_any_role((ROLE_SYSTEM_ADMIN,))


def _ensure_role_can_be_managed(user, role_code: str) -> None:
    if role_code not in BACKEND_ROLES:
        raise BusinessError("后台角色不合法", "invalid_role")
    if _is_brand_only(user) and role_code not in BRAND_MANAGED_ROLES:
        raise ForbiddenError("品牌管理员不能授予该角色")


def _ensure_target_can_be_managed(user, account: User) -> None:
    if _is_brand_only(user) and not _has_only_brand_managed_roles(account):
        raise ForbiddenError("品牌管理员不能维护该账号")


def _has_only_brand_managed_roles(account: User) -> bool:
    """品牌管理员只能访问角色集合完全属于门店员工或经理的账号。"""
    role_codes = {link.role.role_code for link in account.role_links if link.role}
    return bool(role_codes) and role_codes <= set(BRAND_MANAGED_ROLES)


def _load_locked_account_permissions(account: User) -> None:
    """
    函数名称：_load_locked_account_permissions
    函数用途：将已锁定账号的角色和门店绑定替换为数据库当前状态
    参数说明：account 为调用方已持有行锁的目标账号
    返回值说明：无；更新 ORM 已加载的权限关联集合
    核心逻辑：按关联编号当前读角色成员关系与全部绑定，并标记为已提交集合，避免后续懒加载回到旧快照
    异常或失败情况：数据库锁或查询失败交由统一事务处理
    相关业务规则：MySQL 可重复读下，User 行锁不会使后续普通关联 SELECT 变为当前读；授权和前后审计必须共用此集合
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    role_links = UserRole.query.filter_by(user_id=account.id).order_by(UserRole.id).populate_existing().with_for_update().all()
    store_bindings = UserStoreBinding.query.filter_by(user_id=account.id).order_by(UserStoreBinding.id).populate_existing().with_for_update().all()
    set_committed_value(account, "role_links", role_links)
    set_committed_value(account, "store_bindings", store_bindings)


def _get_role(role_code: str) -> Role:
    role = Role.query.filter_by(role_code=role_code).first()
    if role is None:
        raise BusinessError("角色未初始化", "role_not_initialized")
    return role


def _validate_store_binding(role_code: str, store_id) -> Store | None:
    if role_code not in STORE_SCOPED_ROLES:
        return None
    if not store_id:
        raise BusinessError("门店员工或经理必须绑定门店", "store_binding_required")
    if type(store_id) is not int or store_id < 1:
        raise BusinessError("门店编号必须为正整数", "invalid_store_id")
    store = Store.query.filter_by(id=store_id).populate_existing().with_for_update().first()
    if store is None or not store.is_active:
        raise BusinessError("绑定门店不存在或已停用", "store_not_found")
    return store


def _user_type_for_role(role_code: str) -> str:
    return USER_TYPE_STAFF if role_code in STORE_SCOPED_ROLES else USER_TYPE_ADMIN


def _binding_type_for_role(role_code: str) -> str:
    return "manager" if role_code == ROLE_STORE_MANAGER else "staff"


def _primary_role_code(account: User) -> str | None:
    return account.first_role_code()


def _replace_user_role(account: User, role: Role) -> None:
    # 删除当前读取得的关联集合，避免可重复读旧快照漏掉另一请求刚替换的角色。
    for link in account.role_links:
        db.session.delete(link)
    db.session.flush()
    db.session.add(UserRole(user_id=account.id, role_id=role.id))


def _sync_store_binding(account: User, role_code: str, store: Store | None) -> None:
    if role_code not in STORE_SCOPED_ROLES:
        for binding in account.store_bindings:
            binding.is_active = False
        return
    binding_type = _binding_type_for_role(role_code)
    found_binding = None
    for binding in account.store_bindings:
        if binding.store_id == store.id and binding.binding_type == binding_type:
            found_binding = binding
            binding.is_active = True
        else:
            binding.is_active = False
    if found_binding is None:
        db.session.add(UserStoreBinding(user_id=account.id, store_id=store.id, binding_type=binding_type, is_active=True))


def _build_account_snapshot(account: User) -> dict:
    serialized = serialize_account(account)
    return {
        "username": serialized["username"],
        "phone": serialized["phone"],
        "user_type": serialized["user_type"],
        "is_active": serialized["is_active"],
        "roles": [role["role_code"] for role in serialized["roles"]],
        "store_bindings": serialized["store_bindings"],
    }


def _build_account_log(user, operation_type: str, target_id: int, before_snapshot: dict | None, after_snapshot: dict | None) -> OperationLog:
    return OperationLog(
        operator_id=user.id,
        operator_role_code=user.first_role_code(),
        operation_module="account",
        operation_type=operation_type,
        target_id=target_id,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        operation_result=OPERATION_RESULT_SUCCESS,
    )


def _strict_active(value) -> bool:
    if type(value) is not bool:
        raise BusinessError("启用状态必须为布尔值", "invalid_account_payload")
    return value
