"""
文件名称：routes.py
文件用途：定义认证与仿真短信验证码 API 路由
主要职责：提供验证码、顾客注册、登录、刷新、退出和当前用户查询接口
所属业务模块：认证
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from flask_jwt_extended import get_jwt_identity, jwt_required

from app.auth.services import (
    login_user,
    logout_user,
    refresh_access_token,
    register_customer,
    send_verification_code,
    serialize_user,
)
from app.common.decorators import get_current_user
from app.common.errors import BusinessError
from app.common.responses import success_response
from app.users.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password or len(username) > 64 or len(password) > 128:
        raise BusinessError("用户名和密码不能为空", "invalid_login_payload")
    return success_response(login_user(username, password))


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    return success_response(register_customer(payload), 201)


@auth_bp.post("/verification-code")
def verification_code():
    payload = request.get_json(silent=True) or {}
    return success_response(send_verification_code(payload.get("phone")), 201)


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    try:
        user_id = int(get_jwt_identity())
    except (ValueError, TypeError):
        raise BusinessError("登录状态无效", "authentication_failed", 401)
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        raise BusinessError("账号不存在", "authentication_failed", 401)
    return success_response(refresh_access_token(user))


@auth_bp.post("/logout")
def logout():
    return success_response(logout_user(get_current_user()))


@auth_bp.get("/me")
def me():
    return success_response(serialize_user(get_current_user()))
