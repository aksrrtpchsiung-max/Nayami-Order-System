"""
文件名称：routes.py
文件用途：定义系统后台 API 路由
主要职责：提供后台账号管理、角色列表和系统配置查询接口
所属业务模块：系统管理
创建时间：2026-05-26 16:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.system.services import (
    create_account,
    get_system_config,
    list_accounts,
    list_roles,
    reset_account_password,
    update_account,
    update_system_config,
)

system_bp = Blueprint("system", __name__)


@system_bp.get("/roles")
def roles():
    return success_response(list_roles(get_current_user()))


@system_bp.get("/config")
def system_config():
    return success_response(get_system_config(get_current_user()))


@system_bp.get("/accounts")
def accounts():
    return success_response(list_accounts(get_current_user()))


@system_bp.post("/accounts")
def create_backend_account():
    return success_response(create_account(get_current_user(), request.get_json(silent=True) or {}), 201)


@system_bp.patch("/accounts/<int:account_id>")
def update_backend_account(account_id: int):
    return success_response(update_account(get_current_user(), account_id, request.get_json(silent=True) or {}))


@system_bp.post("/accounts/<int:account_id>/reset-password")
def reset_backend_account_password(account_id: int):
    return success_response(reset_account_password(get_current_user(), account_id))


@system_bp.patch("/config")
def edit_system_config():
    return success_response(update_system_config(get_current_user(), request.get_json(silent=True) or {}))
