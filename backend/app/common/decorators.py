"""
文件名称：decorators.py
文件用途：提供认证、角色和门店数据范围校验辅助函数
主要职责：校验会话版本、账号状态、角色及有效门店绑定，并提供审计操作人上下文
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.common.enums import ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN
from app.common.errors import AuthenticationError, BusinessError, ForbiddenError
from app.extensions import db
from app.users.models import User, UserStoreBinding
from app.stores.models import Store


def get_current_user() -> User:
    """
    函数名称：get_current_user
    函数用途：验证当前访问令牌并返回有效用户
    参数说明：从请求中的 JWT 读取账号编号和会话版本
    返回值说明：启用且令牌未撤销的用户对象
    核心逻辑：验证签名和时效，读取实时账号及版本，保存审计操作人上下文
    异常或失败情况：缺少凭证、账号不存在、停用或会话版本不匹配时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    verify_jwt_in_request()
    user_id = get_jwt_identity()
    try:
        user = db.session.get(User, int(user_id)) if user_id else None
    except (TypeError, ValueError):
        user = None
    if user is not None:
        g.audit_user_id = user.id
        g.audit_role_code = user.first_role_code()
    if user is None or not user.is_active:
        raise AuthenticationError("登录状态无效，请重新登录")
    if get_jwt().get("token_version", 0) != user.token_version:
        raise AuthenticationError("登录状态已失效，请重新登录")
    return user


def require_roles(*role_codes: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user.has_any_role(role_codes):
                raise ForbiddenError("当前账号没有执行该操作的角色权限")
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def ensure_user_can_access_store(user: User, store_id: int) -> None:
    """
    函数名称：ensure_user_can_access_store
    函数用途：保证门店操作与账号的数据范围一致
    参数说明：user 为当前用户，store_id 为目标门店
    返回值说明：校验通过返回 None
    核心逻辑：全局管理员按业务接口继续校验；门店人员必须具有有效绑定且门店未停用
    异常或失败情况：跨店、缺少绑定或门店停用时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if user.has_any_role((ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        return
    binding = UserStoreBinding.query.filter_by(user_id=user.id, store_id=store_id, is_active=True).first()
    if binding is None:
        raise ForbiddenError("当前账号不能访问该门店数据")
    store = db.session.get(Store, store_id)
    if store is None or not store.is_active:
        raise BusinessError("门店已停用，请联系管理员", "store_unavailable", 403)
