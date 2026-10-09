"""
文件名称：routes.py
文件用途：定义门店 API 路由
主要职责：提供顾客端门店列表查询和门店后台营业状态维护接口
所属业务模块：门店
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.stores.services import list_active_stores, update_store_operation_status

stores_bp = Blueprint("stores", __name__)
store_admin_bp = Blueprint("store_admin", __name__)


@stores_bp.get("")
def list_stores():
    return success_response(list_active_stores())


@store_admin_bp.patch("/status/<int:store_id>")
def update_store_status(store_id: int):
    return success_response(
        update_store_operation_status(get_current_user(), store_id, request.get_json(silent=True) or {})
    )
