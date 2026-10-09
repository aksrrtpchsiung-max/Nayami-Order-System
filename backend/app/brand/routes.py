"""
文件名称：routes.py
文件用途：定义品牌后台 API 路由
主要职责：提供品牌概览、门店、菜单、门店商品、优惠券、报表和品牌账号接口
所属业务模块：品牌管理
创建时间：2026-05-26 16:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from flask import Blueprint, request

from app.brand.services import (
    create_brand_store,
    create_category,
    create_coupon_activity,
    create_product,
    get_brand_overview,
    get_brand_report,
    get_coupon_activity_metrics,
    list_brand_store_products,
    list_brand_stores,
    list_categories,
    list_coupon_activities,
    list_products,
    update_brand_store,
    update_brand_store_product,
    update_category,
    update_coupon_activity,
    update_product,
    upsert_store_product,
)
from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.system.services import create_account, list_accounts, reset_account_password, update_account

brand_bp = Blueprint("brand", __name__)


@brand_bp.get("/overview")
def overview():
    return success_response(get_brand_overview(get_current_user()))


@brand_bp.get("/report")
def report():
    return success_response(get_brand_report(get_current_user()))


@brand_bp.get("/stores")
def stores():
    return success_response(list_brand_stores(get_current_user()))


@brand_bp.post("/stores")
def create_store():
    return success_response(create_brand_store(get_current_user(), request.get_json(silent=True) or {}), 201)


@brand_bp.patch("/stores/<int:store_id>")
def update_store(store_id: int):
    return success_response(update_brand_store(get_current_user(), store_id, request.get_json(silent=True) or {}))


@brand_bp.get("/categories")
def categories():
    return success_response(list_categories(get_current_user()))


@brand_bp.post("/categories")
def create_product_category():
    return success_response(create_category(get_current_user(), request.get_json(silent=True) or {}), 201)


@brand_bp.patch("/categories/<int:category_id>")
def update_product_category(category_id: int):
    return success_response(update_category(get_current_user(), category_id, request.get_json(silent=True) or {}))


@brand_bp.get("/products")
def products():
    return success_response(list_products(get_current_user()))


@brand_bp.post("/products")
def create_brand_product():
    return success_response(create_product(get_current_user(), request.get_json(silent=True) or {}), 201)


@brand_bp.patch("/products/<int:product_id>")
def update_brand_product(product_id: int):
    return success_response(update_product(get_current_user(), product_id, request.get_json(silent=True) or {}))


@brand_bp.get("/store-products")
def store_products():
    store_id = request.args.get("store_id", type=int)
    return success_response(list_brand_store_products(get_current_user(), store_id))


@brand_bp.post("/store-products")
def create_store_product():
    return success_response(upsert_store_product(get_current_user(), request.get_json(silent=True) or {}), 201)


@brand_bp.patch("/store-products/<int:store_product_id>")
def update_store_product(store_product_id: int):
    return success_response(update_brand_store_product(get_current_user(), store_product_id, request.get_json(silent=True) or {}))


@brand_bp.get("/coupons")
def coupons():
    return success_response(list_coupon_activities(get_current_user()))


@brand_bp.post("/coupons")
def create_coupon():
    return success_response(create_coupon_activity(get_current_user(), request.get_json(silent=True) or {}), 201)


@brand_bp.patch("/coupons/<int:activity_id>")
def update_coupon(activity_id: int):
    return success_response(update_coupon_activity(get_current_user(), activity_id, request.get_json(silent=True) or {}))


@brand_bp.get("/coupons/<int:activity_id>/metrics")
def coupon_metrics(activity_id: int):
    return success_response(get_coupon_activity_metrics(get_current_user(), activity_id))


@brand_bp.get("/accounts")
def brand_accounts():
    return success_response(list_accounts(get_current_user()))


@brand_bp.post("/accounts")
def create_brand_account():
    return success_response(create_account(get_current_user(), request.get_json(silent=True) or {}), 201)


@brand_bp.patch("/accounts/<int:account_id>")
def update_brand_account(account_id: int):
    return success_response(update_account(get_current_user(), account_id, request.get_json(silent=True) or {}))


@brand_bp.post("/accounts/<int:account_id>/reset-password")
def reset_brand_account_password(account_id: int):
    return success_response(reset_account_password(get_current_user(), account_id))
