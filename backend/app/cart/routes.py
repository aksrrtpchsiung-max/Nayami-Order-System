"""
文件名称：routes.py
文件用途：定义登录顾客会话购物车 API 路由
主要职责：提供购物车查询、加购、修改数量、删除和清空接口
所属业务模块：购物车
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.errors import BusinessError, ForbiddenError
from app.common.responses import success_response
from app.cart.services import (
    add_cart_item as add_cart_item_service,
    clear_cart_items as clear_cart_items_service,
    list_cart_items as list_cart_items_service,
    remove_cart_item as remove_cart_item_service,
    update_cart_item as update_cart_item_service,
)

cart_bp = Blueprint("cart", __name__)


@cart_bp.get("/items")
def list_cart_items():
    user = _customer()
    return success_response(list_cart_items_service(user.id))


@cart_bp.post("/items")
def add_cart_item():
    user = _customer()
    payload = request.get_json(silent=True) or {}
    store_product_id = _integer(payload.get("store_product_id"), 1)
    quantity = _integer(payload.get("quantity", 1), 1)
    if store_product_id <= 0 or quantity <= 0:
        raise BusinessError("购物车商品和数量不合法", "invalid_cart_item")
    return success_response(add_cart_item_service(user.id, store_product_id, quantity), 201)


@cart_bp.patch("/items/<int:store_product_id>")
def update_cart_item(store_product_id: int):
    user = _customer()
    payload = request.get_json(silent=True) or {}
    quantity = _integer(payload.get("quantity"), 0)
    if quantity == 0:
        return success_response(remove_cart_item_service(user.id, store_product_id))
    return success_response(update_cart_item_service(user.id, store_product_id, quantity))


@cart_bp.delete("/items/<int:store_product_id>")
def delete_cart_item(store_product_id: int):
    user = _customer()
    return success_response(remove_cart_item_service(user.id, store_product_id))


@cart_bp.delete("/items")
def clear_cart_items():
    user = _customer()
    return success_response(clear_cart_items_service(user.id))


def _integer(value, minimum):
    if type(value) is not int or not minimum <= value <= 2147483647:
        raise BusinessError("购物车商品与数量必须为范围内的整数", "invalid_cart_item")
    return value


def _customer():
    user = get_current_user()
    if user.user_type != "customer":
        raise ForbiddenError("只有顾客可以维护购物车")
    return user
