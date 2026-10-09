"""
文件名称：routes.py
文件用途：定义门店库存后台 API 路由
主要职责：提供门店库存列表、库存调整、售罄和恢复可售接口
所属业务模块：库存
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.inventory.services import list_store_inventory, list_store_inventory_logs, update_store_inventory_item

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("")
def store_inventory():
    store_id = int(request.args.get("store_id") or 0)
    return success_response(list_store_inventory(get_current_user(), store_id))


@inventory_bp.patch("/<int:store_product_id>")
def update_inventory_item(store_product_id: int):
    return success_response(
        update_store_inventory_item(get_current_user(), store_product_id, request.get_json(silent=True) or {})
    )


@inventory_bp.get("/logs")
def inventory_logs():
    return success_response(list_store_inventory_logs(get_current_user(), request.args.get("store_id", 0, type=int),
        store_product_id=request.args.get("store_product_id", type=int), change_type=request.args.get("change_type"),
        days=request.args.get("days", 7, type=int)))
