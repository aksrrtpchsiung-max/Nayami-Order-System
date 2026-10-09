"""
文件名称：services.py
文件用途：实现门店后台概览和基础报表服务
主要职责：按门店与角色隔离经营数据，分别按创建、支付和核销时间汇总今日、7日及30日指标
所属业务模块：报表
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func

from app.catalog.models import StoreProduct
from app.common.decorators import ensure_user_can_access_store
from app.common.enums import (
    COUPON_STATUS_USED,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_CANCELED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_PAID,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_READY,
    ORDER_STATUS_REFUNDED,
    ORDER_STATUS_REFUND_PENDING,
    ROLE_BRAND_ADMIN,
    ROLE_STORE_MANAGER,
    ROLE_STORE_STAFF,
    ROLE_SYSTEM_ADMIN,
)
from app.common.errors import ForbiddenError
from app.common.formatters import format_money
from app.common.time_utils import current_time
from app.coupons.models import UserCoupon
from app.orders.models import Order, OrderItem

ACTIVE_ORDER_STATUSES = (ORDER_STATUS_PAID, ORDER_STATUS_ACCEPTED, ORDER_STATUS_PREPARING, ORDER_STATUS_READY)
EFFECTIVE_ORDER_STATUSES = ACTIVE_ORDER_STATUSES + (ORDER_STATUS_COMPLETED, ORDER_STATUS_REFUND_PENDING)
REPORT_METRIC_DEFINITIONS = {
    "order_count": "orders_created_in_period_all_statuses",
    "revenue": "orders_paid_in_period_excluding_successful_refunds_including_refund_pending",
    "completed_order_count": "orders_created_in_period_currently_completed",
    "canceled_order_count": "orders_created_in_period_currently_canceled_or_refunded",
    "coupon_used_count": "coupons_redeemed_in_period_including_refunded_orders",
    "popular_products": "paid_in_period_nonrefunded_order_item_quantity_grouped_by_product_id",
    "timezone": "local",
}


def get_store_overview(user, store_id: int) -> dict:
    """
    函数名称：get_store_overview
    函数用途：提供允许门店员工访问的当天履约首页指标
    参数说明：user 为当前后台用户，store_id 为门店编号
    返回值说明：返回当天订单总数、销售额、履约数量及低库存数量
    核心逻辑：校验门店角色与数据范围，订单数包含所有状态，履约队列限定自然日
    异常或失败情况：顾客、无绑定或跨店访问时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    ensure_user_can_access_store(user, store_id)
    if not user.has_any_role((ROLE_STORE_STAFF, ROLE_STORE_MANAGER, ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能查看门店概览")
    today_start, today_end = _today_range()
    today_orders = _orders_in_range(store_id, today_start, today_end)
    active_orders = today_orders.filter(Order.order_status.in_(ACTIVE_ORDER_STATUSES))
    summary = _summarize_orders(store_id, today_start, today_end)
    low_stock_count = StoreProduct.query.filter(
        StoreProduct.store_id == store_id, StoreProduct.is_available.is_(True), StoreProduct.is_sold_out.is_(False),
        (StoreProduct.current_stock - StoreProduct.reserved_stock) <= 5,
    ).count()
    return {
        "store_id": store_id,
        "today_order_count": summary["order_count"],
        "today_revenue": summary["revenue"],
        "completed_order_count": summary["completed_order_count"],
        "canceled_order_count": summary["canceled_order_count"],
        "active_order_count": active_orders.count(),
        "paid_order_count": active_orders.filter(Order.order_status == ORDER_STATUS_PAID).count(),
        "preparing_order_count": active_orders.filter(Order.order_status.in_((ORDER_STATUS_ACCEPTED, ORDER_STATUS_PREPARING))).count(),
        "ready_order_count": active_orders.filter(Order.order_status == ORDER_STATUS_READY).count(),
        "low_stock_count": low_stock_count,
    }


def get_store_report(user, store_id: int) -> dict:
    """
    函数名称：get_store_report
    函数用途：为有经营权限的账号提供今日、7日及30日报表
    参数说明：user 为当前用户，store_id 为目标门店
    返回值说明：返回三个自然日期间的订单、退款扣除后收入、取消数、用券数及热门商品
    核心逻辑：订单数量以创建时间、收入和销量以支付时间、核销数量以核销时间独立汇总
    异常或失败情况：门店员工、顾客或跨店访问时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    _ensure_store_report_viewer(user, store_id)
    today_start, today_end = _today_range()
    return {
        "store_id": store_id,
        "today": _summarize_orders(store_id, today_start, today_end),
        "last_7_days": _summarize_orders(store_id, today_start - timedelta(days=6), today_end),
        "last_30_days": _summarize_orders(store_id, today_start - timedelta(days=29), today_end),
        "popular_products": _popular_products(store_id, today_start, today_end),
        "popular_products_last_7_days": _popular_products(store_id, today_start - timedelta(days=6), today_end),
        "popular_products_last_30_days": _popular_products(store_id, today_start - timedelta(days=29), today_end),
        "metric_definitions": REPORT_METRIC_DEFINITIONS,
    }


def _ensure_store_report_viewer(user, store_id: int) -> None:
    ensure_user_can_access_store(user, store_id)
    if not user.has_any_role((ROLE_STORE_MANAGER, ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能查看门店报表")


def _orders_in_range(store_id: int, start_time, end_time):
    return Order.query.filter(Order.store_id == store_id, Order.created_at >= start_time, Order.created_at < end_time)


def _paid_orders_in_range(store_id: int, start_time, end_time):
    return Order.query.filter(Order.store_id == store_id, Order.paid_at >= start_time, Order.paid_at < end_time,
                              Order.order_status.in_(EFFECTIVE_ORDER_STATUSES))


def _summarize_orders(store_id: int, start_time, end_time) -> dict:
    orders = _orders_in_range(store_id, start_time, end_time)
    revenue = _paid_orders_in_range(store_id, start_time, end_time).with_entities(func.coalesce(func.sum(Order.payable_amount), 0)).scalar()
    coupon_used_count = UserCoupon.query.join(Order, UserCoupon.used_order_id == Order.id).filter(
        Order.store_id == store_id, UserCoupon.coupon_status == COUPON_STATUS_USED,
        UserCoupon.used_at >= start_time, UserCoupon.used_at < end_time,
    ).count()
    return {
        "order_count": orders.count(),
        "completed_order_count": orders.filter(Order.order_status == ORDER_STATUS_COMPLETED).count(),
        "canceled_order_count": orders.filter(Order.order_status.in_((ORDER_STATUS_CANCELED, ORDER_STATUS_REFUNDED))).count(),
        "refund_pending_order_count": orders.filter(Order.order_status == ORDER_STATUS_REFUND_PENDING).count(),
        "coupon_used_count": coupon_used_count,
        "revenue": format_money(revenue),
    }


def _popular_products(store_id: int, start_time, end_time) -> list[dict]:
    rows = OrderItem.query.join(Order, OrderItem.order_id == Order.id).filter(
        Order.store_id == store_id, Order.paid_at >= start_time, Order.paid_at < end_time,
        Order.order_status.in_(EFFECTIVE_ORDER_STATUSES),
    ).with_entities(OrderItem.product_id, func.sum(OrderItem.quantity).label("sold_quantity"),
                    func.sum(OrderItem.subtotal_amount).label("sales_amount"), func.max(OrderItem.id).label("snapshot_id")) \
        .group_by(OrderItem.product_id).order_by(func.sum(OrderItem.quantity).desc(), OrderItem.product_id).limit(5).all()
    products = []
    for row in rows:
        snapshot = OrderItem.query.filter_by(id=row.snapshot_id).one()
        products.append({"product_id": row.product_id, "product_name_zh": snapshot.product_name_zh,
            "product_name_en": snapshot.product_name_en, "sold_quantity": int(row.sold_quantity or 0),
            "sales_amount": format_money(row.sales_amount)})
    return products


def _today_range():
    today_start = current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, today_start + timedelta(days=1)
