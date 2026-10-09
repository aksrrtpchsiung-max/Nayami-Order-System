"""
文件名称：services.py
文件用途：实现订单创建、查询、取消和门店履约业务服务
主要职责：处理订单金额重算、库存预占与释放、支付单创建、订单状态机和门店数据范围校验
所属业务模块：订单
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import case, or_
from uuid import uuid4

from flask import current_app

from app.audit.models import OperationLog
from app.catalog.models import StoreProduct
from app.common.decorators import ensure_user_can_access_store
from app.common.enums import (
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_CANCELED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_PAID,
    ORDER_STATUS_PENDING_PAYMENT,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_READY,
    ORDER_STATUS_REFUND_PENDING,
    ORDER_STATUS_REFUNDED,
    ROLE_BRAND_ADMIN,
    ROLE_SYSTEM_ADMIN,
    ORDER_TRIGGER_CUSTOMER,
    ORDER_TRIGGER_SYSTEM,
    ORDER_TRIGGER_STORE_MANAGER,
    ORDER_TRIGGER_STORE_STAFF,
    PAYMENT_EVENT_CANCELED,
    PAYMENT_EVENT_CREATED,
    PAYMENT_EVENT_EXPIRED,
    PAYMENT_METHOD_WECHAT,
    PAYMENT_STATUS_CANCELED,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_PENDING,
    ROLE_STORE_MANAGER,
    ROLE_STORE_STAFF,
    STORE_STATUS_OPEN,
    USER_TYPE_CUSTOMER,
)
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.common.formatters import format_datetime, format_money
from app.common.time_utils import build_payment_deadline, current_time, is_time_in_business_range
from app.extensions import db
from app.inventory.services import release_reserved_stock, reserve_stock
from app.orders.models import Order, OrderItem, OrderStatusLog
from app.payments.models import PaymentLog, PaymentRecord
from app.stores.models import Store

ALLOWED_STORE_TRANSITIONS = {
    ORDER_STATUS_PAID: ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ACCEPTED: ORDER_STATUS_PREPARING,
    ORDER_STATUS_PREPARING: ORDER_STATUS_READY,
    ORDER_STATUS_READY: ORDER_STATUS_COMPLETED,
}


def create_order(user, payload: dict) -> dict:
    """
    函数名称：create_order
    函数用途：创建待支付订单并预占库存
    参数说明：user 为当前顾客，payload 包含 store_id、items、order_type、remark、tableware_count、user_coupon_id
    返回值说明：返回订单详情和待支付支付单
    核心逻辑：校验顾客、门店、商品和库存，服务端重算金额，在事务中写订单、明细、支付单和日志
    异常或失败情况：未登录顾客、门店不可下单、购物车为空、商品不可售或库存不足时失败
    相关业务规则：订单创建时只预占库存，支付成功后才确认扣减库存
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if user.user_type != USER_TYPE_CUSTOMER:
        raise ForbiddenError("只有顾客账号可以创建订单")
    if not isinstance(payload, dict):
        raise BusinessError("订单参数必须是对象", "invalid_order_payload")
    store_id = _strict_integer(payload.get("store_id"), "invalid_store_id", minimum=1)
    order_type = payload.get("order_type", "pickup")
    items_payload = payload.get("items") or []
    if order_type not in ("dine_in", "pickup"):
        raise BusinessError("订单类型不合法", "invalid_order_type")
    if not isinstance(items_payload, list) or not items_payload or len(items_payload) > 100:
        raise BusinessError("购物车不能为空", "empty_cart")
    remark = str(payload.get("remark") or "").strip()
    if len(remark) > 100:
        raise BusinessError("订单备注不能超过 100 个字符", "remark_too_long")
    tableware_count = _strict_integer(payload.get("tableware_count", 0), "invalid_tableware_count", maximum=10)
    normalized_items = []
    for item_payload in items_payload:
        if not isinstance(item_payload, dict):
            raise BusinessError("订单商品格式不合法", "invalid_order_item")
        normalized_items.append({
            "store_product_id": _strict_integer(item_payload.get("store_product_id"), "store_product_not_found", minimum=1),
            "quantity": _strict_integer(item_payload.get("quantity"), "invalid_quantity", minimum=1),
        })
    user_coupon_id = payload.get("user_coupon_id")
    if user_coupon_id is not None:
        user_coupon_id = _strict_integer(user_coupon_id, "invalid_user_coupon_id", minimum=1)

    store = db.session.get(Store, store_id)
    if store is None or not store.is_active:
        raise NotFoundError("门店不存在或已停用")
    _ensure_store_can_order(store)

    order = Order(
        order_no=_build_business_no("NO"),
        user_id=user.id,
        store_id=store_id,
        order_type=order_type,
        order_status=ORDER_STATUS_PENDING_PAYMENT,
        items_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        payable_amount=Decimal("0.00"),
        remark=remark,
        tableware_count=tableware_count,
        payment_deadline=build_payment_deadline(int(current_app.config["PAYMENT_TIMEOUT_MINUTES"])),
    )
    db.session.add(order)
    db.session.flush()

    items_amount = Decimal("0.00")
    seen_store_product_ids: set[int] = set()
    for item_payload in sorted(normalized_items, key=lambda item: item["store_product_id"]):
        store_product_id = item_payload["store_product_id"]
        quantity = item_payload["quantity"]
        if quantity <= 0:
            raise BusinessError("商品数量必须大于 0", "invalid_quantity")
        if store_product_id in seen_store_product_ids:
            raise BusinessError("同一商品请合并数量后提交", "duplicated_order_item")
        seen_store_product_ids.add(store_product_id)

        store_product = (
            StoreProduct.query.filter_by(id=store_product_id, store_id=store_id)
            .populate_existing().with_for_update()
            .first()
        )
        _ensure_store_product_can_order(store_product)
        subtotal_amount = Decimal(store_product.product.base_price) * quantity
        items_amount += subtotal_amount
        if items_amount > Decimal("99999999.99"):
            raise BusinessError("订单金额超过允许上限", "order_amount_too_large")
        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=store_product.product_id,
                store_product_id=store_product.id,
                product_name_zh=store_product.product.name_zh,
                product_name_en=store_product.product.name_en,
                unit_price=store_product.product.base_price,
                quantity=quantity,
                subtotal_amount=subtotal_amount,
            )
        )
        reserve_stock(store_product, quantity, order.id)

    from app.coupons.services import reserve_coupon_for_order

    discount_amount = reserve_coupon_for_order(
        user,
        user_coupon_id,
        order,
        items_amount,
        {item.product_id for item in order.items},
    )
    order.items_amount = items_amount
    order.discount_amount = discount_amount
    order.payable_amount = max(items_amount - discount_amount, Decimal("0.00"))
    payment = PaymentRecord(
        payment_no=_build_business_no("PAY"),
        order_id=order.id,
        payment_method=PAYMENT_METHOD_WECHAT,
        payment_amount=order.payable_amount,
        payment_status=PAYMENT_STATUS_PENDING,
    )
    db.session.add(payment)
    db.session.flush()
    db.session.add(
        PaymentLog(
            payment_id=payment.id,
            order_id=order.id,
            from_status=None,
            to_status=PAYMENT_STATUS_PENDING,
            event_type=PAYMENT_EVENT_CREATED,
            event_payload={"source": "order_created"},
        )
    )
    db.session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=None,
            to_status=ORDER_STATUS_PENDING_PAYMENT,
            trigger_type=ORDER_TRIGGER_CUSTOMER,
            operator_id=user.id,
            reason="顾客提交订单",
        )
    )
    db.session.commit()
    return serialize_order(order)


def get_order_detail(user, order_id: int) -> dict:
    order = db.session.get(Order, order_id)
    if order is None:
        raise NotFoundError("订单不存在")
    _ensure_user_can_view_order(user, order)
    return serialize_order(order)


def list_customer_orders(user, status: str | None = None) -> list[dict]:
    """
    函数名称：list_customer_orders
    函数用途：查询当前顾客本人的历史订单
    参数说明：user 为当前登录顾客，status 为可选订单状态筛选
    返回值说明：返回按创建时间倒序排列的订单详情列表
    核心逻辑：强制使用当前用户 ID 过滤，避免顾客越权读取其他订单
    异常或失败情况：后台账号调用时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if user.user_type != USER_TYPE_CUSTOMER:
        raise ForbiddenError("只有顾客账号可以查看我的订单")
    query = Order.query.filter_by(user_id=user.id)
    if status:
        query = query.filter_by(order_status=status)
    return [serialize_order(order) for order in query.order_by(Order.created_at.desc()).all()]


def cancel_pending_order(user, order_id: int) -> dict:
    """
    函数名称：cancel_pending_order
    函数用途：顾客主动取消本人待支付订单
    参数说明：user 为当前登录顾客，order_id 为订单 ID
    返回值说明：返回取消后的订单详情
    核心逻辑：校验订单归属和待支付状态，订单改为 canceled，支付单改为 canceled，释放订单所有商品预占库存并写日志
    异常或失败情况：订单不存在、非本人订单或订单不是 pending_payment 状态时失败
    相关业务规则：只有未支付订单允许顾客主动取消；取消必须释放创建订单时预占的库存
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    order = Order.query.filter_by(id=order_id).populate_existing().with_for_update().first()
    if order is None:
        raise NotFoundError("订单不存在")
    if order.user_id != user.id:
        raise ForbiddenError("只能取消本人订单")
    if order.order_status != ORDER_STATUS_PENDING_PAYMENT:
        raise BusinessError("当前订单状态不可取消", "order_status_not_cancelable")

    _cancel_pending_order(
        order,
        payment_status=PAYMENT_STATUS_CANCELED,
        payment_event_type=PAYMENT_EVENT_CANCELED,
        trigger_type=ORDER_TRIGGER_CUSTOMER,
        operator_id=user.id,
        order_reason="顾客主动取消订单",
        payment_message="顾客主动取消待支付订单",
        inventory_remark="顾客取消订单释放预占库存",
    )
    db.session.commit()
    return serialize_order(order)


def expire_pending_payment_orders(now=None, batch_size: int = 100) -> dict:
    """
    函数名称：expire_pending_payment_orders
    函数用途：扫描并自动取消已超过支付截止时间的待支付订单
    参数说明：now 为扫描基准时间，batch_size 为单次最多处理订单数量
    返回值说明：返回处理数量和被取消订单 ID 列表
    核心逻辑：筛选 pending_payment 且 payment_deadline 小于等于当前时间的订单，逐单改为 canceled，支付单改为 expired，并释放预占库存
    异常或失败情况：数据库写入失败时由上层统一回滚；已不处于待支付状态的订单不会被扫描处理
    相关业务规则：支付超时后订单不能继续支付，需要重新下单，且预占库存必须释放
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    scan_time = now or current_time()
    orders = (
        Order.query.filter(Order.order_status == ORDER_STATUS_PENDING_PAYMENT, Order.payment_deadline <= scan_time)
        .order_by(Order.payment_deadline.asc())
        .limit(batch_size)
        .populate_existing().with_for_update()
        .all()
    )
    expired_order_ids: list[int] = []
    for order in orders:
        _expire_single_pending_order(order)
        expired_order_ids.append(order.id)
    db.session.commit()
    return {"expired_count": len(expired_order_ids), "order_ids": expired_order_ids}


def expire_pending_order_for_payment(order: Order) -> dict:
    """
    函数名称：expire_pending_order_for_payment
    函数用途：支付成功前发现订单已超时时，同步关闭订单并释放库存
    参数说明：order 为支付单关联订单
    返回值说明：返回取消后的订单详情
    核心逻辑：仅处理 pending_payment 订单，将订单置为 canceled、支付单置为 expired、释放预占库存并提交事务
    异常或失败情况：订单已不是待支付状态时不重复处理
    相关业务规则：旧支付页不能在支付截止时间后继续模拟支付成功
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if order.order_status == ORDER_STATUS_PENDING_PAYMENT:
        _expire_single_pending_order(order)
        db.session.commit()
    return serialize_order(order)


def list_store_orders(user, store_id: int, status: str | None = None, *, view: str = "active", days: int = 1, search: str = "") -> list[dict]:
    """
    函数名称：list_store_orders
    函数用途：按门店、自然日范围、履约分区和搜索词查询订单看板
    参数说明：view 为 active/history/all，days 为 1/7/30，search 为订单号或取餐码
    返回值说明：返回优先处理已支付、随后按支付时间升序的完整订单快照
    核心逻辑：校验角色和门店范围，默认仅当天已支付履约订单，历史分区包含取消与退款
    异常或失败情况：越权、无效视图或日期范围时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    ensure_user_can_access_store(user, store_id)
    if not user.has_any_role((ROLE_STORE_STAFF, ROLE_STORE_MANAGER, ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能查看门店订单")
    if view not in {"active", "history", "all"} or days not in {1, 7, 30}:
        raise BusinessError("订单查询范围不合法", "invalid_order_filter")
    active_statuses = tuple(ALLOWED_STORE_TRANSITIONS)
    history_statuses = (ORDER_STATUS_COMPLETED, ORDER_STATUS_CANCELED, ORDER_STATUS_REFUND_PENDING, ORDER_STATUS_REFUNDED)
    start = current_time().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    end = start + timedelta(days=days)
    query = Order.query.filter(Order.store_id == store_id, Order.created_at >= start, Order.created_at < end)
    if status:
        if status not in (*active_statuses, *history_statuses, ORDER_STATUS_PENDING_PAYMENT):
            raise BusinessError("订单状态筛选不合法", "invalid_order_filter")
        query = query.filter(Order.order_status == status)
    elif view != "all":
        query = query.filter(Order.order_status.in_(active_statuses if view == "active" else history_statuses))
    search = search.strip()
    if len(search) > 64:
        raise BusinessError("搜索内容过长", "invalid_order_filter")
    if search:
        query = query.filter(or_(Order.order_no.contains(search, autoescape=True), Order.pickup_code == search.upper()))
    priority = case({value: index for index, value in enumerate((*active_statuses, *history_statuses))}, value=Order.order_status, else_=99)
    orders = query.order_by(priority, Order.paid_at.asc(), Order.created_at.asc(), Order.id.asc()).all()
    return [serialize_order(order) for order in orders]


def update_store_order_status(user, order_id: int, payload: dict) -> dict:
    """
    函数名称：update_store_order_status
    函数用途：门店人员推进订单履约状态
    参数说明：user 为当前后台用户，order_id 为订单 ID，payload 包含 target_status 和可选 pickup_code
    返回值说明：返回更新后的订单详情
    核心逻辑：锁定并刷新订单，校验门店绑定、状态机目标、取餐码，更新状态并记录状态和操作日志
    异常或失败情况：越权、跳状态、取餐码错误或终态订单继续操作时失败
    相关业务规则：履约流转只允许 paid -> accepted -> preparing -> ready -> completed
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    order = Order.query.filter_by(id=order_id).populate_existing().with_for_update().first()
    if order is None:
        raise NotFoundError("订单不存在")
    ensure_user_can_access_store(user, order.store_id)
    if not user.has_any_role((ROLE_STORE_STAFF, ROLE_STORE_MANAGER)):
        raise ForbiddenError("只有门店人员可以处理订单")

    target_status = payload.get("target_status")
    expected_status = ALLOWED_STORE_TRANSITIONS.get(order.order_status)
    if expected_status is None or target_status != expected_status:
        raise BusinessError("订单状态流转不合法", "invalid_order_status_transition")
    if target_status == ORDER_STATUS_COMPLETED and payload.get("pickup_code") != order.pickup_code:
        raise BusinessError("取餐码不正确", "invalid_pickup_code")

    from_status = order.order_status
    order.order_status = target_status
    if target_status == ORDER_STATUS_COMPLETED:
        order.completed_at = current_time()
    trigger_type = ORDER_TRIGGER_STORE_MANAGER if user.has_any_role((ROLE_STORE_MANAGER,)) else ORDER_TRIGGER_STORE_STAFF
    db.session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=from_status,
            to_status=target_status,
            trigger_type=trigger_type,
            operator_id=user.id,
            reason="门店履约状态更新",
        )
    )
    db.session.add(
        OperationLog(
            operator_id=user.id,
            operator_role_code=user.first_role_code(),
            operation_module="order",
            operation_type="update_status",
            target_id=order.id,
            store_id=order.store_id,
            before_snapshot={"order_status": from_status},
            after_snapshot={"order_status": target_status},
            operation_result="success",
        )
    )
    db.session.commit()
    return serialize_order(order)


def _expire_single_pending_order(order: Order) -> None:
    _cancel_pending_order(
        order,
        payment_status=PAYMENT_STATUS_EXPIRED,
        payment_event_type=PAYMENT_EVENT_EXPIRED,
        trigger_type=ORDER_TRIGGER_SYSTEM,
        operator_id=None,
        order_reason="支付超时自动取消订单",
        payment_message="支付超时，系统自动关闭支付单",
        inventory_remark="支付超时释放预占库存",
    )


def _cancel_pending_order(
    order: Order,
    payment_status: str,
    payment_event_type: str,
    trigger_type: str,
    operator_id: int | None,
    order_reason: str,
    payment_message: str,
    inventory_remark: str,
) -> None:
    from_order_status = order.order_status
    order.order_status = ORDER_STATUS_CANCELED
    order.cancel_reason = order_reason

    payment = _get_latest_payment(order)
    if payment is not None:
        from_payment_status = payment.payment_status
        payment.payment_status = payment_status
        db.session.add(
            PaymentLog(
                payment_id=payment.id,
                order_id=order.id,
                from_status=from_payment_status,
                to_status=payment_status,
                event_type=payment_event_type,
                event_payload={"message": payment_message},
            )
        )

    for order_item in sorted(order.items, key=lambda item: item.store_product_id):
        store_product = StoreProduct.query.filter_by(id=order_item.store_product_id).populate_existing().with_for_update().first()
        if store_product is not None:
            release_reserved_stock(store_product, order_item.quantity, order.id, inventory_remark)
    from app.coupons.services import release_coupon_for_order

    release_coupon_for_order(order)

    db.session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=from_order_status,
            to_status=ORDER_STATUS_CANCELED,
            trigger_type=trigger_type,
            operator_id=operator_id,
            reason=order_reason,
        )
    )


def _get_latest_payment(order: Order) -> PaymentRecord | None:
    return PaymentRecord.query.filter_by(order_id=order.id).order_by(PaymentRecord.id.desc()).first()


def serialize_order(order: Order) -> dict:
    payment = _get_latest_payment(order)
    from app.payments.models import RefundRecord

    refund = RefundRecord.query.filter_by(order_id=order.id).order_by(RefundRecord.id.desc()).first()
    return {
        "id": order.id,
        "order_no": order.order_no,
        "user_id": order.user_id,
        "store_id": order.store_id,
        "store_name": order.store.name_zh if order.store else None,
        "store_name_zh": order.store.name_zh if order.store else None,
        "store_name_en": order.store.name_en if order.store else None,
        "store_address": order.store.address if order.store else None,
        "store_phone": order.store.phone if order.store else None,
        "customer_name": order.user.username if order.user else None,
        "customer_phone_masked": _mask_phone(order.user.phone) if order.user else None,
        "order_type": order.order_type,
        "order_status": order.order_status,
        "items_amount": format_money(order.items_amount),
        "discount_amount": format_money(order.discount_amount),
        "payable_amount": format_money(order.payable_amount),
        "user_coupon_id": order.user_coupon_id,
        "pickup_code": order.pickup_code,
        "pickup_date": order.pickup_date.isoformat() if order.pickup_date else None,
        "cancel_reason": order.cancel_reason,
        "remark": order.remark,
        "tableware_count": order.tableware_count,
        "payment_deadline": format_datetime(order.payment_deadline),
        "paid_at": format_datetime(order.paid_at),
        "completed_at": format_datetime(order.completed_at),
        "created_at": format_datetime(order.created_at),
        "updated_at": format_datetime(order.updated_at),
        "status_logs": [{"id": entry.id, "from_status": entry.from_status, "to_status": entry.to_status,
            "trigger_type": entry.trigger_type, "operator_id": entry.operator_id, "reason": entry.reason,
            "created_at": format_datetime(entry.created_at)} for entry in sorted(order.status_logs, key=lambda entry: entry.id)],
        "payment_logs": [{"id": entry.id, "payment_id": entry.payment_id, "from_status": entry.from_status,
            "to_status": entry.to_status, "event_type": entry.event_type, "created_at": format_datetime(entry.created_at)}
            for entry in PaymentLog.query.filter_by(order_id=order.id).order_by(PaymentLog.id).all()],
        "payments": [_serialize_payment(attempt) for attempt in sorted(order.payments, key=lambda attempt: attempt.id)],
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "store_product_id": item.store_product_id,
                "product_name_zh": item.product_name_zh,
                "product_name_en": item.product_name_en,
                "unit_price": format_money(item.unit_price),
                "quantity": item.quantity,
                "subtotal_amount": format_money(item.subtotal_amount),
            }
            for item in order.items
        ],
        "payment": _serialize_payment(payment) if payment else None,
        "refund": {
            "id": refund.id,
            "refund_no": refund.refund_no,
            "refund_status": refund.refund_status,
            "refund_amount": format_money(refund.refund_amount),
            "refund_reason": refund.refund_reason,
            "simulated_refund_no": refund.simulated_refund_no,
            "refunded_at": format_datetime(refund.refunded_at),
        }
        if refund
        else None,
    }


def _serialize_payment(payment: PaymentRecord) -> dict:
    return {
        "id": payment.id,
        "payment_no": payment.payment_no,
        "payment_method": payment.payment_method,
        "payment_amount": format_money(payment.payment_amount),
        "payment_status": payment.payment_status,
        "transaction_no": payment.transaction_no,
        "card_brand": payment.card_brand,
        "masked_card_no": payment.masked_card_no,
        "failure_reason": payment.failure_reason,
        "created_at": format_datetime(payment.created_at),
        "paid_at": format_datetime(payment.paid_at),
    }


def _ensure_store_can_order(store: Store) -> None:
    now = current_time().time()
    if store.store_status != STORE_STATUS_OPEN or not is_time_in_business_range(
        now,
        store.business_start_time,
        store.business_end_time,
    ):
        raise BusinessError("当前门店不可下单", "store_not_orderable")


def _ensure_store_product_can_order(store_product: StoreProduct | None) -> None:
    if store_product is None:
        raise BusinessError("商品不存在或不属于当前门店", "store_product_not_found")
    product = store_product.product
    if product.menu_status not in ("published", "draft_changes") or not product.category or not product.category.is_active or not store_product.is_available or store_product.is_sold_out:
        raise BusinessError("商品当前不可售", "product_not_available")


def _ensure_user_can_view_order(user, order: Order) -> None:
    if user.user_type == USER_TYPE_CUSTOMER:
        if order.user_id != user.id:
            raise ForbiddenError("不能查看其他顾客的订单")
        return
    ensure_user_can_access_store(user, order.store_id)


def _build_business_no(prefix: str) -> str:
    return f"{prefix}{current_time():%Y%m%d%H%M%S}{uuid4().hex[:8].upper()}"


def _strict_integer(value, error_code: str, minimum: int = 0, maximum: int = 2147483647) -> int:
    """拒绝布尔值、小数、字符串及数据库整数范围之外的输入。"""
    if type(value) is not int or not minimum <= value <= maximum:
        raise BusinessError("参数必须是范围内的整数", error_code)
    return value


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 8 else "****"
