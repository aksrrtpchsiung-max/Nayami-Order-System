"""
文件名称：services.py
文件用途：实现支付与退款仿真业务服务
主要职责：处理支付单查询、成功/失败/取消/超时、银行卡识别、重新支付、退款和幂等回调
所属业务模块：支付
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from uuid import uuid4

from app.audit.models import OperationLog
from app.catalog.models import StoreProduct
from app.stores.models import Store
from app.common.decorators import ensure_user_can_access_store
from app.common.enums import (
    OPERATION_RESULT_SUCCESS,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_PAID,
    ORDER_STATUS_PENDING_PAYMENT,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_REFUNDED,
    ORDER_STATUS_REFUND_PENDING,
    ORDER_TRIGGER_CUSTOMER,
    ORDER_TRIGGER_PAYMENT_CALLBACK,
    ORDER_TRIGGER_STORE_MANAGER,
    ORDER_TRIGGER_STORE_STAFF,
    PAYMENT_EVENT_CALLBACK,
    PAYMENT_EVENT_CANCELED,
    PAYMENT_EVENT_DUPLICATE,
    PAYMENT_EVENT_FAILED,
    PAYMENT_EVENT_REFUND,
    PAYMENT_EVENT_RETRY,
    PAYMENT_METHOD_ALIPAY,
    PAYMENT_METHOD_BANK_CARD,
    PAYMENT_METHOD_WECHAT,
    PAYMENT_STATUS_CANCELED,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_PROCESSING,
    PAYMENT_STATUS_SUCCEEDED,
    ROLE_STORE_MANAGER,
    ROLE_STORE_STAFF,
    USER_TYPE_CUSTOMER,
)
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.common.formatters import format_datetime, format_money
from app.common.time_utils import current_time
from app.extensions import db
from app.inventory.services import (
    confirm_deduct_stock,
    release_reserved_stock,
    reserve_stock,
    restore_refunded_stock,
)
from app.orders.models import Order, OrderStatusLog
from app.payments.models import PaymentLog, PaymentRecord, RefundRecord

SUPPORTED_PAYMENT_METHODS = {PAYMENT_METHOD_WECHAT, PAYMENT_METHOD_ALIPAY, PAYMENT_METHOD_BANK_CARD}
TEST_CARD_RESULTS = {
    "6222020000000000": "success",
    "4111111111111111": "success",
    "5555555555554444": "success",
    "4000000000000002": "failure",
    "4000000000009995": "timeout",
}


def get_payment_detail(user, payment_id: int) -> dict:
    payment = db.session.get(PaymentRecord, payment_id)
    if payment is None:
        raise NotFoundError("支付单不存在")
    from app.orders.services import _ensure_user_can_view_order

    _ensure_user_can_view_order(user, payment.order)
    order = Order.query.filter_by(id=payment.order_id).populate_existing().with_for_update().one()
    payment = PaymentRecord.query.filter_by(id=payment_id).populate_existing().with_for_update().one()
    if (
        payment.payment_status in (PAYMENT_STATUS_PENDING, PAYMENT_STATUS_PROCESSING)
        and payment.order.order_status == ORDER_STATUS_PENDING_PAYMENT
        and payment.order.payment_deadline <= current_time()
    ):
        from app.orders.services import expire_pending_order_for_payment

        expire_pending_order_for_payment(payment.order)
        payment = db.session.get(PaymentRecord, payment_id)
    return serialize_payment_with_order(payment)


def simulate_payment(user, payment_id: int, payload: dict) -> dict:
    """
    函数名称：simulate_payment
    函数用途：统一处理微信、支付宝与银行卡的仿真支付结果
    参数说明：payload 包含 payment_method、result、银行卡表单字段和 idempotency_key
    返回值说明：返回当前支付尝试与订单快照
    核心逻辑：银行卡先识别卡组织与测试卡结果，再分派成功、失败、取消或超时处理
    异常或失败情况：支付方式、卡组织、支付状态、订单归属或敏感表单字段不合法时失败
    相关业务规则：不保存完整卡号、CVV、验证码和支付密码
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    payment_method = str(payload.get("payment_method") or PAYMENT_METHOD_WECHAT)
    if not isinstance(payment_method, str) or payment_method not in SUPPORTED_PAYMENT_METHODS:
        raise BusinessError("支付方式不支持", "unsupported_payment_method")
    normalized_payload = dict(payload)
    normalized_payload["payment_method"] = payment_method
    result = str(payload.get("result") or "success")
    if payment_method == PAYMENT_METHOD_BANK_CARD:
        card_number = _normalize_card_number(payload.get("card_number"))
        card_brand = identify_card_brand(card_number)
        _validate_bank_card_payload(card_brand, payload)
        result = TEST_CARD_RESULTS.get(card_number, result)
        normalized_payload["card_brand"] = card_brand
        normalized_payload["masked_card_no"] = mask_card_number(card_number)

    if result == "success":
        return simulate_payment_success(user, payment_id, normalized_payload)
    if result in {"failure", "failed"}:
        return _finalize_unsuccessful_payment(
            user,
            payment_id,
            normalized_payload,
            PAYMENT_STATUS_FAILED,
            PAYMENT_EVENT_FAILED,
            "仿真支付失败",
        )
    if result in {"cancel", "canceled"}:
        return _finalize_unsuccessful_payment(
            user,
            payment_id,
            normalized_payload,
            PAYMENT_STATUS_CANCELED,
            PAYMENT_EVENT_CANCELED,
            "顾客取消仿真支付",
        )
    if result in {"timeout", "expired"}:
        payment = _locked_owned_payment(user, payment_id)
        from app.orders.services import expire_pending_order_for_payment

        expire_pending_order_for_payment(payment.order)
        return serialize_payment_with_order(db.session.get(PaymentRecord, payment_id))
    raise BusinessError("仿真支付结果不支持", "unsupported_payment_result")


def simulate_payment_success(user, payment_id: int, payload: dict) -> dict:
    """
    函数名称：simulate_payment_success
    函数用途：模拟支付成功回调并推进订单到已支付
    参数说明：user 为当前顾客，payment_id 为支付单 ID，payload 可包含 payment_method 和 idempotency_key
    返回值说明：返回支付单和订单快照
    核心逻辑：校验支付单、订单、支付截止时间和金额，确认扣减预占库存，更新支付单和订单状态，生成取餐码并写日志
    异常或失败情况：非本人支付单、支付已超时、订单非待支付、库存预占异常或支付单终态非法时失败
    相关业务规则：重复支付回调不能重复扣减库存，支付成功必须通过仿真回调更新订单
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    payment = _locked_owned_payment(user, payment_id)
    order = payment.order

    idempotency_key = payload.get("idempotency_key") or f"PAY-CALLBACK-{uuid4().hex}"
    if not isinstance(idempotency_key, str) or len(idempotency_key) > 128:
        raise BusinessError("支付幂等键格式不合法", "invalid_idempotency_key")
    duplicate_key = PaymentRecord.query.filter(PaymentRecord.idempotency_key == idempotency_key, PaymentRecord.id != payment.id).first()
    if duplicate_key is not None:
        raise BusinessError("支付幂等键已用于其他支付单", "payment_idempotency_conflict")
    if payment.payment_status == PAYMENT_STATUS_SUCCEEDED:
        db.session.add(
            PaymentLog(
                payment_id=payment.id,
                order_id=order.id,
                from_status=PAYMENT_STATUS_SUCCEEDED,
                to_status=PAYMENT_STATUS_SUCCEEDED,
                event_type=PAYMENT_EVENT_DUPLICATE,
                idempotency_key=idempotency_key,
                event_payload={"message": "重复回调已忽略"},
            )
        )
        db.session.commit()
        return serialize_payment_with_order(payment)

    if payment.payment_status not in (PAYMENT_STATUS_PENDING, PAYMENT_STATUS_PROCESSING):
        raise BusinessError("当前支付单状态不可支付", "payment_status_not_payable")
    if order.order_status != ORDER_STATUS_PENDING_PAYMENT:
        raise BusinessError("当前订单状态不可支付", "order_status_not_payable")
    now = current_time()
    if order.payment_deadline <= now:
        from app.orders.services import expire_pending_order_for_payment

        expire_pending_order_for_payment(order)
        raise BusinessError("支付已超时，请重新下单", "payment_expired")

    payment_method = payload.get("payment_method") or payment.payment_method
    if not isinstance(payment_method, str) or payment_method not in SUPPORTED_PAYMENT_METHODS:
        raise BusinessError("支付方式不支持", "unsupported_payment_method")

    if payload.get("payment_amount") is not None and str(payload.get("payment_amount")) != format_money(payment.payment_amount):
        raise BusinessError("支付金额与订单应付金额不一致", "payment_amount_mismatch")
    if payment.payment_amount != order.payable_amount:
        raise BusinessError("支付金额与订单应付金额不一致", "payment_amount_mismatch")
    if payment_method == PAYMENT_METHOD_BANK_CARD:
        card_number = _normalize_card_number(payload.get("card_number"))
        card_brand = identify_card_brand(card_number)
        _validate_bank_card_payload(card_brand, payload)
        if TEST_CARD_RESULTS.get(card_number, "success") != "success":
            raise BusinessError("测试卡不能产生成功支付结果", "invalid_bank_card_payload")
        card_details = (card_brand, mask_card_number(card_number))
    else:
        card_details = (None, None)
    order.pickup_date = now.date()
    pickup_code = _generate_pickup_code(order)
    from app.coupons.services import mark_coupon_used

    from_payment_status = payment.payment_status
    for order_item in sorted(order.items, key=lambda item: item.store_product_id):
        confirm_deduct_stock(order_item.store_product, order_item.quantity, order.id)
    mark_coupon_used(order)

    payment.payment_method = payment_method
    payment.card_brand, payment.masked_card_no = card_details
    payment.payment_status = PAYMENT_STATUS_SUCCEEDED
    payment.transaction_no = f"SIM{now:%Y%m%d%H%M%S}{uuid4().hex[:8].upper()}"
    payment.idempotency_key = idempotency_key
    payment.paid_at = now
    from_order_status = order.order_status
    order.order_status = ORDER_STATUS_PAID
    order.paid_at = now
    order.pickup_code = pickup_code

    db.session.add(
        PaymentLog(
            payment_id=payment.id,
            order_id=order.id,
            from_status=from_payment_status,
            to_status=PAYMENT_STATUS_SUCCEEDED,
            event_type=PAYMENT_EVENT_CALLBACK,
            idempotency_key=idempotency_key,
            event_payload={
                "payment_method": payment_method,
                "card_brand": payment.card_brand,
                "masked_card_no": payment.masked_card_no,
                "result": "success",
            },
        )
    )
    db.session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=from_order_status,
            to_status=ORDER_STATUS_PAID,
            trigger_type=ORDER_TRIGGER_PAYMENT_CALLBACK,
            operator_id=user.id,
            reason="仿真支付成功回调",
        )
    )
    db.session.commit()
    return serialize_payment_with_order(payment)


def retry_payment(user, order_id: int, payload: dict) -> dict:
    """
    函数名称：retry_payment
    函数用途：为支付失败或取消的待支付订单创建新的支付尝试
    参数说明：order_id 为订单 ID，payload 可指定新的 payment_method
    返回值说明：返回新支付单和订单快照
    核心逻辑：重新校验截止时间、商品可售库存和优惠券，重新预占后创建 pending 支付记录
    异常或失败情况：订单已超时、已支付、库存不足或优惠券已不可用时失败
    相关业务规则：历史失败支付单保持终态，新尝试使用新支付单
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    order = Order.query.filter_by(id=order_id).populate_existing().with_for_update().first()
    if order is None:
        raise NotFoundError("订单不存在")
    if user.user_type != USER_TYPE_CUSTOMER or order.user_id != user.id:
        raise ForbiddenError("只有顾客本人可以重新支付订单")
    if order.order_status != ORDER_STATUS_PENDING_PAYMENT:
        raise BusinessError("当前订单状态不可重新支付", "order_status_not_payable")
    if order.payment_deadline <= current_time():
        from app.orders.services import expire_pending_order_for_payment

        expire_pending_order_for_payment(order)
        raise BusinessError("支付已超时，请重新下单", "payment_expired")
    latest_payment = PaymentRecord.query.filter_by(order_id=order.id).order_by(PaymentRecord.id.desc()).first()
    if latest_payment and latest_payment.payment_status in (PAYMENT_STATUS_PENDING, PAYMENT_STATUS_PROCESSING):
        return serialize_payment_with_order(latest_payment)
    if latest_payment and latest_payment.payment_status not in (PAYMENT_STATUS_FAILED, PAYMENT_STATUS_CANCELED):
        raise BusinessError("当前支付尝试不允许重试", "payment_status_not_retryable")

    from app.coupons.services import ensure_coupon_reserved_for_retry

    from app.orders.services import _ensure_store_can_order, _ensure_store_product_can_order

    if not order.store.is_active:
        raise BusinessError("当前门店不可下单", "store_not_orderable")
    _ensure_store_can_order(order.store)
    for order_item in sorted(order.items, key=lambda item: item.store_product_id):
        store_product = order_item.store_product
        store_product = StoreProduct.query.filter_by(id=store_product.id).populate_existing().with_for_update().one()
        _ensure_store_product_can_order(store_product)
        reserve_stock(store_product, order_item.quantity, order.id)
    ensure_coupon_reserved_for_retry(order)

    payment_method = payload.get("payment_method") or PAYMENT_METHOD_WECHAT
    if not isinstance(payment_method, str) or payment_method not in SUPPORTED_PAYMENT_METHODS:
        raise BusinessError("支付方式不支持", "unsupported_payment_method")
    payment = PaymentRecord(
        payment_no=_build_business_no("PAY"),
        order_id=order.id,
        payment_method=payment_method,
        payment_amount=order.payable_amount,
        payment_status=PAYMENT_STATUS_PENDING,
    )
    db.session.add(payment)
    db.session.flush()
    db.session.add(
        PaymentLog(
            payment_id=payment.id,
            order_id=order.id,
            from_status=latest_payment.payment_status if latest_payment else None,
            to_status=PAYMENT_STATUS_PENDING,
            event_type=PAYMENT_EVENT_RETRY,
            event_payload={"source_payment_id": latest_payment.id if latest_payment else None},
        )
    )
    db.session.commit()
    return serialize_payment_with_order(payment)


def request_refund(user, order_id: int, payload: dict) -> dict:
    """
    函数名称：request_refund
    函数用途：取消已支付或履约中订单并创建仿真退款单
    参数说明：order_id 为订单 ID，payload 包含退款原因
    返回值说明：返回退款单及 refund_pending 订单快照
    核心逻辑：锁定订单并校验角色与状态，重复申请返回已有退款单，新申请写退款单、状态日志和后台审计
    异常或失败情况：终态、ready/completed、顾客取消 preparing 或门店员工取消 preparing 时拒绝
    相关业务规则：顾客可取消 paid/accepted；门店经理可取消 paid/accepted/preparing
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    order = Order.query.filter_by(id=order_id).populate_existing().with_for_update().first()
    if order is None:
        raise NotFoundError("订单不存在")
    is_customer = user.user_type == USER_TYPE_CUSTOMER
    if is_customer:
        if order.user_id != user.id:
            raise ForbiddenError("不能取消其他顾客的订单")
        allowed_statuses = {ORDER_STATUS_PAID, ORDER_STATUS_ACCEPTED}
        trigger_type = ORDER_TRIGGER_CUSTOMER
    else:
        ensure_user_can_access_store(user, order.store_id)
        if not user.has_any_role((ROLE_STORE_STAFF, ROLE_STORE_MANAGER)):
            raise ForbiddenError("只有门店人员可以取消履约订单")
        allowed_statuses = {ORDER_STATUS_PAID, ORDER_STATUS_ACCEPTED}
        if user.has_any_role((ROLE_STORE_MANAGER,)):
            allowed_statuses.add(ORDER_STATUS_PREPARING)
            trigger_type = ORDER_TRIGGER_STORE_MANAGER
        else:
            trigger_type = ORDER_TRIGGER_STORE_STAFF
    existing = RefundRecord.query.filter_by(order_id=order.id).order_by(RefundRecord.id.desc()).populate_existing().with_for_update().first()
    if existing and existing.refund_status in ("pending", "succeeded") and order.order_status in (ORDER_STATUS_REFUND_PENDING, ORDER_STATUS_REFUNDED):
        return serialize_refund(existing)
    if order.order_status not in allowed_statuses:
        raise BusinessError("当前订单状态不可申请退款", "order_status_not_refundable")
    reason = str(payload.get("reason") or "").strip()
    if order.order_status == ORDER_STATUS_PREPARING and not reason:
        raise BusinessError("制作中订单取消必须填写原因", "refund_reason_required")
    if len(reason) > 255:
        raise BusinessError("退款原因不能超过 255 个字符", "refund_reason_too_long")
    reason = reason or "订单取消退款"

    payment = (
        PaymentRecord.query.filter_by(order_id=order.id, payment_status=PAYMENT_STATUS_SUCCEEDED)
        .order_by(PaymentRecord.id.desc())
        .first()
    )
    if payment is None:
        raise BusinessError("订单没有可退款的成功支付单", "succeeded_payment_not_found")
    from_status = order.order_status
    order.order_status = ORDER_STATUS_REFUND_PENDING
    order.cancel_reason = reason
    refund = RefundRecord(
        refund_no=_build_business_no("REF"),
        order_id=order.id,
        payment_id=payment.id,
        refund_amount=payment.payment_amount,
        refund_status="pending",
        refund_reason=reason,
    )
    db.session.add(refund)
    db.session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=from_status,
            to_status=ORDER_STATUS_REFUND_PENDING,
            trigger_type=trigger_type,
            operator_id=user.id,
            reason=reason,
        )
    )
    if not is_customer:
        db.session.add(
            OperationLog(
                operator_id=user.id,
                operator_role_code=user.first_role_code(),
                operation_module="order",
                operation_type="request_refund",
                target_id=order.id,
                store_id=order.store_id,
                before_snapshot={"order_status": from_status},
                after_snapshot={"order_status": ORDER_STATUS_REFUND_PENDING, "reason": reason},
                operation_result=OPERATION_RESULT_SUCCESS,
            )
        )
    db.session.commit()
    return serialize_refund(refund)


def simulate_refund_success(user, refund_id: int) -> dict:
    """
    函数名称：simulate_refund_success
    函数用途：完成仿真退款并恢复已确认扣减库存
    参数说明：user 为顾客本人或有门店范围权限的后台账号，refund_id 为退款单 ID
    返回值说明：返回成功退款单和 refunded 订单快照
    核心逻辑：幂等更新退款单与订单状态，按订单库存日志恢复库存并记录支付/订单日志
    异常或失败情况：退款单不存在、越权或订单非 refund_pending 时失败
    相关业务规则：不恢复已使用优惠券，重复退款不能重复恢复库存
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    refund = db.session.get(RefundRecord, refund_id)
    if refund is None:
        raise NotFoundError("退款单不存在")
    order = Order.query.filter_by(id=refund.order_id).populate_existing().with_for_update().one()
    refund = RefundRecord.query.filter_by(id=refund_id).populate_existing().with_for_update().one()
    if user.user_type == USER_TYPE_CUSTOMER:
        if order.user_id != user.id:
            raise ForbiddenError("不能查看或操作其他顾客的退款")
    else:
        ensure_user_can_access_store(user, order.store_id)
    if refund.refund_status == "succeeded":
        return serialize_refund(refund)
    if refund.refund_status != "pending" or order.order_status != ORDER_STATUS_REFUND_PENDING:
        raise BusinessError("当前退款状态不可处理", "refund_status_not_processable")

    now = current_time()
    for order_item in sorted(order.items, key=lambda item: item.store_product_id):
        store_product = order_item.store_product
        restore_refunded_stock(store_product, order_item.quantity, order.id, user.id)
    refund.refund_status = "succeeded"
    refund.simulated_refund_no = _build_business_no("SIMREF")
    refund.refunded_at = now
    order.order_status = ORDER_STATUS_REFUNDED
    db.session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=ORDER_STATUS_REFUND_PENDING,
            to_status=ORDER_STATUS_REFUNDED,
            trigger_type=ORDER_TRIGGER_PAYMENT_CALLBACK,
            operator_id=user.id,
            reason="仿真退款成功",
        )
    )
    db.session.add(
        PaymentLog(
            payment_id=refund.payment_id,
            order_id=order.id,
            from_status=PAYMENT_STATUS_SUCCEEDED,
            to_status=PAYMENT_STATUS_SUCCEEDED,
            event_type=PAYMENT_EVENT_REFUND,
            event_payload={"refund_id": refund.id, "result": "succeeded"},
        )
    )
    db.session.commit()
    return serialize_refund(refund)


def serialize_payment_with_order(payment: PaymentRecord) -> dict:
    from app.orders.services import serialize_order

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
        "paid_at": format_datetime(payment.paid_at),
        "order": serialize_order(payment.order),
    }


def serialize_refund(refund: RefundRecord) -> dict:
    from app.orders.services import serialize_order

    return {
        "id": refund.id,
        "refund_no": refund.refund_no,
        "order_id": refund.order_id,
        "payment_id": refund.payment_id,
        "refund_amount": format_money(refund.refund_amount),
        "refund_status": refund.refund_status,
        "refund_reason": refund.refund_reason,
        "simulated_refund_no": refund.simulated_refund_no,
        "refunded_at": format_datetime(refund.refunded_at),
        "order": serialize_order(db.session.get(Order, refund.order_id)),
    }


def _generate_pickup_code(order) -> str:
    """
    函数名称：_generate_pickup_code
    函数用途：分配同门店付款自然日唯一且可跨日复用的取餐短码
    参数说明：order 为已锁定订单，pickup_date 为支付所属日期
    返回值说明：返回 A000 至 Z999 范围中的空闲短码
    核心逻辑：先锁定门店以串行化当天分配，再读取当天已占用码，数据库复合唯一约束兜底
    异常或失败情况：当日 26000 个码全部占用时拒绝，事务回滚保留待支付订单
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    Store.query.filter_by(id=order.store_id).populate_existing().with_for_update().one()
    pickup_date = order.pickup_date or current_time().date()
    used_codes = {row.pickup_code for row in Order.query.filter(
        Order.store_id == order.store_id, Order.pickup_date == pickup_date, Order.pickup_code.isnot(None), Order.id != order.id,
    ).with_entities(Order.pickup_code).with_for_update().all()}
    for offset in range(26000):
        number = (order.id + offset) % 26000
        code = f"{chr(65 + number // 1000)}{number % 1000:03d}"
        if code not in used_codes:
            return code
    raise BusinessError("取餐码生成失败，请重试", "pickup_code_generation_failed")


def identify_card_brand(card_number: str) -> str:
    """按需求约定的卡 BIN 范围识别 UnionPay、Visa 或 MasterCard。"""
    if card_number.startswith("62"):
        return "unionpay"
    if card_number.startswith("4"):
        return "visa"
    if len(card_number) >= 4:
        prefix_two = int(card_number[:2])
        prefix_four = int(card_number[:4])
        if 51 <= prefix_two <= 55 or 2221 <= prefix_four <= 2720:
            return "mastercard"
    raise BusinessError("暂不支持该银行卡组织", "unsupported_card_brand")


def mask_card_number(card_number: str) -> str:
    """仅保留银行卡号首四位和末四位，避免敏感信息落库。"""
    return f"{card_number[:4]} **** **** {card_number[-4:]}"


def _normalize_card_number(value) -> str:
    card_number = "".join(character for character in str(value or "") if character.isdigit())
    if not 12 <= len(card_number) <= 19:
        raise BusinessError("银行卡号格式不合法", "invalid_card_number")
    return card_number


def _validate_bank_card_payload(card_brand: str, payload: dict) -> None:
    common_required = ("cardholder_name",)
    if any(not str(payload.get(field_name) or "").strip() for field_name in common_required):
        raise BusinessError("请填写持卡人姓名", "invalid_bank_card_payload")
    if card_brand == "unionpay":
        required_fields = ("phone", "verification_code", "payment_password")
        if any(not str(payload.get(field_name) or "").strip() for field_name in required_fields):
            raise BusinessError("请完整填写银联仿真表单", "invalid_bank_card_payload")
        if len(str(payload.get("payment_password"))) != 6:
            raise BusinessError("仿真支付密码必须为 6 位", "invalid_payment_password")
    else:
        required_fields = ("expiry", "cvv", "billing_country", "billing_address", "postal_code")
        if any(not str(payload.get(field_name) or "").strip() for field_name in required_fields):
            raise BusinessError("请完整填写国际卡仿真表单", "invalid_bank_card_payload")


def _locked_owned_payment(user, payment_id: int) -> PaymentRecord:
    """
    函数名称：_locked_owned_payment
    函数用途：按订单、支付单的固定顺序取得顾客本人的支付锁
    参数说明：user 为当前用户，payment_id 为支付单编号
    返回值说明：返回刷新后的支付单
    核心逻辑：拒绝后台付款，锁订单后再锁支付单，使取消、超时和支付在同一订单上串行化
    异常或失败情况：支付单不存在或非本人顾客操作时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if user.user_type != USER_TYPE_CUSTOMER:
        raise ForbiddenError("只有顾客本人可以发起支付")
    payment = db.session.get(PaymentRecord, payment_id)
    if payment is None:
        raise NotFoundError("支付单不存在")
    order = Order.query.filter_by(id=payment.order_id).populate_existing().with_for_update().one()
    if order.user_id != user.id:
        raise ForbiddenError("不能支付其他顾客的订单")
    return PaymentRecord.query.filter_by(id=payment_id).populate_existing().with_for_update().one()


def _finalize_unsuccessful_payment(
    user,
    payment_id: int,
    payload: dict,
    target_status: str,
    event_type: str,
    reason: str,
) -> dict:
    payment = _locked_owned_payment(user, payment_id)
    order = payment.order
    if payment.payment_status not in (PAYMENT_STATUS_PENDING, PAYMENT_STATUS_PROCESSING):
        raise BusinessError("当前支付单状态不可处理", "payment_status_not_payable")
    if order.order_status != ORDER_STATUS_PENDING_PAYMENT:
        raise BusinessError("当前订单状态不可支付", "order_status_not_payable")
    from_status = payment.payment_status
    payment.payment_method = payload.get("payment_method") or payment.payment_method
    if payment.payment_method == PAYMENT_METHOD_BANK_CARD:
        card_number = _normalize_card_number(payload.get("card_number"))
        payment.card_brand = identify_card_brand(card_number)
        payment.masked_card_no = mask_card_number(card_number)
    else:
        payment.card_brand = None
        payment.masked_card_no = None
    payment.payment_status = target_status
    payment.failure_reason = reason
    for order_item in sorted(order.items, key=lambda item: item.store_product_id):
        release_reserved_stock(
            order_item.store_product,
            order_item.quantity,
            order.id,
            f"{reason}释放预占库存",
        )
    from app.coupons.services import release_coupon_for_order

    release_coupon_for_order(order)
    db.session.add(
        PaymentLog(
            payment_id=payment.id,
            order_id=order.id,
            from_status=from_status,
            to_status=target_status,
            event_type=event_type,
            idempotency_key=payload.get("idempotency_key"),
            event_payload={
                "result": target_status,
                "card_brand": payment.card_brand,
                "masked_card_no": payment.masked_card_no,
            },
        )
    )
    db.session.commit()
    return serialize_payment_with_order(payment)


def _build_business_no(prefix: str) -> str:
    return f"{prefix}{current_time():%Y%m%d%H%M%S}{uuid4().hex[:8].upper()}"
