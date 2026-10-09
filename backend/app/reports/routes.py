"""
文件名称：routes.py
文件用途：定义门店报表 API 路由
主要职责：提供门店工作台概览和基础经营报表接口
所属业务模块：报表
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.reports.services import get_store_overview, get_store_report

reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/overview")
def store_overview():
    store_id = int(request.args.get("store_id") or 0)
    return success_response(get_store_overview(get_current_user(), store_id))


@reports_bp.get("/report")
def store_report():
    store_id = int(request.args.get("store_id") or 0)
    return success_response(get_store_report(get_current_user(), store_id))
