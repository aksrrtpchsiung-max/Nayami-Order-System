"""
文件名称：routes.py
文件用途：定义审计日志 API 路由
主要职责：提供品牌后台和系统后台操作日志查询接口
所属业务模块：审计
创建时间：2026-05-26 16:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from flask import Blueprint, request

from app.audit.services import get_operation_log, list_operation_logs
from app.common.decorators import get_current_user
from app.common.responses import success_response

audit_bp = Blueprint("audit", __name__)


@audit_bp.get("/logs")
def operation_logs():
    return success_response(list_operation_logs(get_current_user(), request.args.to_dict()))


@audit_bp.get("/logs/<int:log_id>")
def operation_log_detail(log_id: int):
    return success_response(get_operation_log(get_current_user(), log_id))
