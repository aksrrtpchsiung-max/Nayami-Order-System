"""
文件名称：seed_demo_history.py
文件用途：通过业务服务补齐传统 ERP 多状态演示订单和优惠券
主要职责：仅在演示模式创建缺失样例，保证支付、退款、库存、优惠券及日志一致且重复执行不重复扣减
所属业务模块：演示初始化
创建时间：2026-09-08 17:30
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from flask import current_app

from app.catalog.models import Product, ProductCategory, StoreProduct
from app.catalog.services import LIVE_MENU_STATUSES
from app.common.errors import BusinessError
from app.common.time_utils import current_time
from app.coupons.models import CouponActivity, CouponClaimTask, UserCoupon
from app.coupons.services import claim_coupon, process_claim_task, warmup_activity
from app.extensions import db
from app.system.settings import get_setting
from app.inventory.services import update_store_inventory_item
from app.orders.models import Order
from app.orders.services import cancel_pending_order, create_order, update_store_order_status
from app.payments.services import request_refund, simulate_payment, simulate_refund_success
from app.stores.models import Store
from app.stores.services import serialize_store
from app.users.models import User, UserStoreBinding

SCENARIOS = ("pending_payment", "paid", "accepted", "preparing", "ready", "completed", "canceled", "refunded")
REMARKS = {"pending_payment": "演示：待支付自取", "paid": "演示：已支付，少辣", "accepted": "演示：已接单，无需餐具",
    "preparing": "演示：正在制作", "ready": "演示：可取餐", "completed": "演示：已完成优惠券订单",
    "canceled": "演示：顾客取消未支付订单", "refunded": "演示：支付后取消并退款"}


def _ensure_coupon(user, brand, kind):
    """
    函数名称：_ensure_coupon
    函数用途：创建或复用一张稳定标识的演示券
    参数说明：user 为顾客，brand 为品牌管理员，kind 为演示券用途
    返回值说明：已持久化用户优惠券
    核心逻辑：按活动标识查重，调用预热、原子领取和幂等落库；过期样例同步调整历史时间
    异常或失败情况：Redis 或数据库不可用时失败，已有券保持原状态
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    marker = f"erp_demo_history:coupon:{kind}"
    activity = CouponActivity.query.filter_by(description_zh=marker).first()
    if activity is None:
        activity = CouponActivity(activity_name_zh={"available":"演示可用券", "used":"演示核销券", "expired":"演示过期券"}[kind],
            activity_name_en=f"Demo {kind} coupon", description_zh=marker,
            start_at=current_time()-timedelta(hours=1), end_at=current_time()+timedelta(days=7),
            total_stock=1, discount_amount=1, minimum_order_amount=0, per_user_limit=1, activity_status="active", created_by=brand.id)
        db.session.add(activity)
        db.session.commit()
    coupon = UserCoupon.query.filter_by(activity_id=activity.id, user_id=user.id).first()
    if coupon is None:
        task = CouponClaimTask.query.filter_by(activity_id=activity.id, user_id=user.id).first()
        if task is None:
            warmup_activity(brand, activity.id)
            response = claim_coupon(user, activity.id, {"request_id": marker})
            task = db.session.get(CouponClaimTask, response["task"]["id"])
        process_claim_task(task.id)
        coupon = UserCoupon.query.filter_by(activity_id=activity.id, user_id=user.id).one()
        if kind == "expired":
            activity.start_at = current_time()-timedelta(days=3)
            activity.end_at = current_time()-timedelta(days=1)
            activity.activity_status = "ended"
            coupon.claimed_at = current_time()-timedelta(days=2)
            coupon.expired_at = activity.end_at
            coupon.coupon_status = "expired"
            task.redis_success_time = coupon.claimed_at
            db.session.commit()
    return coupon


def seed_demo_history() -> dict:
    """
    函数名称：seed_demo_history
    函数用途：补齐八种订单和三种优惠券演示样例
    参数说明：无，读取当前 Flask 应用配置与已有种子账号
    返回值说明：本次创建数和演示订单/券标识
    核心逻辑：稳定编号和备注查重，选营业中门店；必要时通过库存服务补充样例库存，逐步调用真实业务状态机
    异常或失败情况：非 DEMO_MODE、缺少演示账号、营业门店或门店经理时拒绝；已有样例不重置状态
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if not get_setting("demo_mode"):
        raise BusinessError("仅演示模式允许补充演示历史数据", "demo_mode_required")
    user = User.query.filter_by(username="customer_demo", is_active=True).first()
    brand = User.query.filter_by(username="brand_admin", is_active=True).first()
    if user is None or brand is None or not brand.has_any_role(("brand_admin", "system_admin")):
        raise BusinessError("请先初始化演示顾客和品牌管理员", "demo_accounts_required")
    coupons = {kind: _ensure_coupon(user, brand, kind) for kind in ("available", "used", "expired")}
    existing = {state: Order.query.filter_by(order_no=f"DEMOERP-{state}").first() or
        Order.query.filter_by(user_id=user.id, remark=REMARKS[state]).first() for state in SCENARIOS}
    missing = [state for state in SCENARIOS if existing[state] is None]
    if not missing:
        return {"created_order_count": 0, "order_ids": {state: existing[state].id for state in SCENARIOS},
            "coupon_ids": {kind: coupon.id for kind, coupon in coupons.items()}}
    store_product = None
    manager = None
    candidates = StoreProduct.query.join(StoreProduct.product).join(StoreProduct.store).filter(
        Store.is_active.is_(True), StoreProduct.is_available.is_(True), StoreProduct.is_sold_out.is_(False),
        Product.menu_status.in_(LIVE_MENU_STATUSES), Product.category.has(ProductCategory.is_active.is_(True)),
    ).order_by(StoreProduct.id).all()
    for candidate in candidates:
        if not serialize_store(candidate.store)["can_order"]:
            continue
        for binding in UserStoreBinding.query.filter_by(store_id=candidate.store_id, is_active=True).all():
            bound_user = db.session.get(User, binding.user_id)
            if bound_user.is_active and bound_user.has_any_role(("store_manager",)):
                store_product, manager = candidate, bound_user
                break
        if manager:
            break
    if store_product is None:
        raise BusinessError("需要营业中的门店、可售商品和已绑定门店经理", "demo_store_required")
    available_stock = store_product.current_stock - store_product.reserved_stock
    if available_stock < len(missing):
        update_store_inventory_item(manager, store_product.id, {
            "current_stock": store_product.current_stock + len(missing) - available_stock,
            "reason": "补充演示历史订单所需库存",
        })
    for scenario in missing:
        payload = {"store_id": store_product.store_id, "order_type": "dine_in" if scenario == "preparing" else "pickup",
            "items": [{"store_product_id": store_product.id, "quantity": 1}],
            "remark": REMARKS[scenario], "tableware_count": 0 if scenario == "accepted" else 1}
        if scenario == "completed":
            payload["user_coupon_id"] = coupons["used"].id
        result = create_order(user, payload)
        order = db.session.get(Order, result["id"])
        order.order_no = f"DEMOERP-{scenario}"
        db.session.commit()
        existing[scenario] = order
        if scenario == "pending_payment":
            continue
        if scenario == "canceled":
            cancel_pending_order(user, order.id)
            continue
        simulate_payment(user, result["payment"]["id"], {
            "payment_method": "wechat", "result": "success", "idempotency_key": f"demo-history-payment-{scenario}",
        })
        if scenario == "refunded":
            refund = request_refund(user, order.id, {"reason": "演示：顾客支付后取消"})
            simulate_refund_success(user, refund["id"])
            continue
        for target in ("accepted", "preparing", "ready", "completed"):
            if scenario == "paid":
                break
            update_store_order_status(manager, order.id, {"target_status": target, "pickup_code": order.pickup_code})
            if target == scenario:
                break
    return {"created_order_count": len(missing), "order_ids": {state: existing[state].id for state in SCENARIOS},
        "coupon_ids": {kind: coupon.id for kind, coupon in coupons.items()}}


if __name__ == "__main__":
    from app import create_app
    with create_app().app_context():
        print(json.dumps(seed_demo_history(), ensure_ascii=False, indent=2))
