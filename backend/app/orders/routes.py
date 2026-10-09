"""
文件名称：routes.py
文件用途：定义订单 API 路由
主要职责：提供创建订单、订单详情、顾客取消订单、门店订单看板和门店履约状态更新接口
所属业务模块：订单
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.orders.services import (
    cancel_pending_order,
    create_order,
    get_order_detail,
    list_customer_orders,
    list_store_orders,
    update_store_order_status,
)

orders_bp = Blueprint("orders", __name__)


@orders_bp.post("/orders")
def create_customer_order():
    return success_response(create_order(get_current_user(), request.get_json(silent=True) or {}), 201)


@orders_bp.get("/orders/<int:order_id>")
def order_detail(order_id: int):
    return success_response(get_order_detail(get_current_user(), order_id))


@orders_bp.get("/orders")
def customer_orders():
    return success_response(list_customer_orders(get_current_user(), request.args.get("status")))


@orders_bp.post("/orders/<int:order_id>/cancel")
def cancel_order(order_id: int):
    return success_response(cancel_pending_order(get_current_user(), order_id))


@orders_bp.get("/store/orders")
def store_orders():
    store_id = int(request.args.get("store_id") or 0)
    status = request.args.get("status")
    return success_response(list_store_orders(get_current_user(), store_id, status,
        view=request.args.get("view", "active"), days=request.args.get("days", 1, type=int),
        search=request.args.get("search", "")))


@orders_bp.post("/store/orders/<int:order_id>/status")
def update_status(order_id: int):
    return success_response(update_store_order_status(get_current_user(), order_id, request.get_json(silent=True) or {}))
