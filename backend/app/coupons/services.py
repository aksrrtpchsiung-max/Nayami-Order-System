"""
文件名称：services.py
文件用途：实现优惠券活动、抢券、异步落库、使用校验和活动对账
主要职责：协调 Redis 原子判定、MySQL 最终落库、失败补偿、用户优惠券与订单核销
所属业务模块：优惠券与高并发抢券
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.audit.models import OperationLog
from app.common.enums import (
    COUPON_STATUS_AVAILABLE,
    COUPON_STATUS_ABNORMAL,
    COUPON_STATUS_EXPIRED,
    COUPON_STATUS_SYNCING,
    COUPON_STATUS_USED,
    COUPON_TASK_DEAD,
    COUPON_TASK_FAILED,
    COUPON_TASK_PENDING,
    COUPON_TASK_PROCESSING,
    COUPON_TASK_SUCCEEDED,
    OPERATION_RESULT_SUCCESS,
    ROLE_BRAND_ADMIN,
    ROLE_SYSTEM_ADMIN,
    USER_TYPE_CUSTOMER,
)
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.common.formatters import format_datetime, format_money
from app.common.time_utils import current_time
from app.coupons.models import CouponActivity, CouponClaimTask, UserCoupon
from app.coupons.redis_store import (
    CLAIM_RESULT_ALREADY_CLAIMED,
    CLAIM_RESULT_IDEMPOTENT,
    CLAIM_RESULT_NOT_WARMED,
    CLAIM_RESULT_SOLD_OUT,
    CLAIM_RESULT_SUCCEEDED,
    get_coupon_redis_store,
)
from app.extensions import db
from app.system.settings import get_setting

ACTIVE_ACTIVITY_STATUSES = {"scheduled", "active", "paused", "ended", "sold_out"}


def list_public_activities() -> list[dict]:
    """返回顾客可见的已配置优惠券活动，并附加 Redis 库存口径。"""
    activities = (
        CouponActivity.query.filter(CouponActivity.activity_status.in_(ACTIVE_ACTIVITY_STATUSES))
        .order_by(CouponActivity.start_at.desc())
        .all()
    )
    return [serialize_activity(activity, include_metrics=True) for activity in activities]


def warmup_activity(user, activity_id: int, force: bool = False) -> dict:
    """
    函数名称：warmup_activity
    函数用途：将活动总库存写入 Redis 抢券库存 Key
    参数说明：user 为后台操作人，activity_id 为活动 ID，force 表示是否重置已有抢券结果
    返回值说明：返回活动 ID、Redis 剩余库存和是否强制重置
    核心逻辑：校验管理员并锁活动；库存缺失时从已落库券和任务恢复已领取用户集合，再扣除已领数量并记录日志
    异常或失败情况：活动不存在、无权限或 Redis 不可用时失败
    相关业务规则：强制重置仅允许演示模式未开放的无权益草稿；普通预热不得补回已领取库存
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_coupon_admin(user)
    activity = CouponActivity.query.filter_by(id=activity_id).with_for_update().first()
    if activity is None:
        raise NotFoundError("优惠券活动不存在")
    if force and not get_setting("demo_mode"):
        raise ForbiddenError("只有演示模式允许强制重置抢券库存")
    if force and activity.activity_status != "draft":
        raise BusinessError("只有未开放领取的活动草稿允许强制重置", "coupon_terms_locked")
    if force:
        if UserCoupon.query.filter_by(activity_id=activity.id).first() or CouponClaimTask.query.filter_by(activity_id=activity.id).first():
            raise BusinessError("已有领取权益的活动不能重置库存", "coupon_terms_locked")
        try:
            has_claims = get_coupon_redis_store().metrics(activity.id)["success_count"] > 0
        except Exception as exc:
            raise BusinessError("Redis 暂不可用，活动预热失败", "coupon_redis_unavailable", 503) from exc
        if has_claims:
            raise BusinessError("已有领取权益的活动不能重置库存", "coupon_terms_locked")
    known_users = {row.user_id for row in UserCoupon.query.filter_by(activity_id=activity.id).with_entities(UserCoupon.user_id).all()}
    known_users.update(row.user_id for row in CouponClaimTask.query.filter_by(activity_id=activity.id).with_entities(CouponClaimTask.user_id).all())
    try:
        remaining_stock = get_coupon_redis_store().warmup(activity.id, activity.total_stock, force=force, claimed_user_ids=known_users)
    except Exception as exc:
        raise BusinessError("Redis 暂不可用，活动预热失败", "coupon_redis_unavailable", 503) from exc
    db.session.add(
        _operation_log(
            user,
            "warmup",
            activity.id,
            {"total_stock": activity.total_stock, "force": force},
        )
    )
    db.session.commit()
    return {"activity_id": activity.id, "remaining_stock": remaining_stock, "force": force}


def claim_coupon(user, activity_id: int, payload: dict) -> dict:
    """
    函数名称：claim_coupon
    函数用途：处理顾客对限量优惠券活动的抢券请求
    参数说明：user 为当前顾客，activity_id 为活动 ID，payload 包含 request_id
    返回值说明：返回 Redis 判定结果、剩余库存和落库任务状态
    核心逻辑：校验活动后执行 Lua 原子脚本，成功时创建幂等落库任务并投递后台任务
    异常或失败情况：活动未开始、暂停、结束、未预热、售罄或重复领取时返回明确业务错误
    相关业务规则：Redis 成功即代表领取成功；MySQL 通过任务最终一致地写入用户优惠券
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if user.user_type != USER_TYPE_CUSTOMER:
        raise ForbiddenError("只有顾客账号可以领取优惠券")
    activity = db.session.get(CouponActivity, activity_id)
    if activity is None:
        raise NotFoundError("优惠券活动不存在")
    request_id = str(payload.get("request_id") or uuid4().hex).strip()
    if not request_id or len(request_id) > 128:
        raise BusinessError("抢券请求编号不合法", "invalid_request_id")
    try:
        _ensure_activity_claimable(activity)
    except BusinessError:
        # 已成功请求在活动随后暂停、售罄或结束后仍须恢复同一权益，不能变成一次新领取。
        if not get_coupon_redis_store().has_successful_request(activity.id, user.id, request_id):
            raise
    try:
        redis_result = get_coupon_redis_store().claim(activity.id, user.id, request_id)
    except Exception as exc:
        raise BusinessError("抢券服务繁忙，请稍后重试", "coupon_redis_unavailable", 503) from exc

    result_code = redis_result["code"]
    if result_code == CLAIM_RESULT_NOT_WARMED:
        raise BusinessError("活动库存尚未预热，请稍后重试", "coupon_not_warmed")
    if result_code == CLAIM_RESULT_SOLD_OUT:
        if activity.activity_status != "sold_out":
            activity.activity_status = "sold_out"
            db.session.commit()
        raise BusinessError("优惠券已抢完", "coupon_sold_out")
    if result_code == CLAIM_RESULT_ALREADY_CLAIMED:
        existing = UserCoupon.query.filter_by(activity_id=activity.id, user_id=user.id).first()
        raise BusinessError(
            "已领取该活动优惠券",
            "coupon_already_claimed" if existing is None else "coupon_already_available",
        )
    if result_code not in (CLAIM_RESULT_SUCCEEDED, CLAIM_RESULT_IDEMPOTENT):
        raise BusinessError("抢券结果无法识别，请稍后重试", "coupon_claim_unknown")

    task = CouponClaimTask.query.filter_by(activity_id=activity.id, user_id=user.id).first()
    if task is None:
        task = CouponClaimTask(
            activity_id=activity.id,
            user_id=user.id,
            redis_success_time=current_time(),
            task_status=COUPON_TASK_PENDING,
            retry_count=0,
        )
        db.session.add(task)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            task = CouponClaimTask.query.filter_by(activity_id=activity.id, user_id=user.id).first()
    if task is None:
        raise BusinessError("领取成功，权益正在补偿同步", "coupon_claim_task_pending", 202)

    _sync_task_status_cache(task)
    if current_app.config.get("COUPON_TASK_EAGER"):
        process_claim_task(task.id)
        task = db.session.get(CouponClaimTask, task.id)
    else:
        _dispatch_claim_task(task.id)
    return {
        "result": "succeeded",
        "message_code": "coupon_claim_succeeded",
        "activity_id": activity.id,
        "remaining_stock": redis_result.get("remaining_stock"),
        "task": {key: value for key, value in serialize_claim_task(task).items() if key != "last_error"},
    }


def list_user_coupons(user, status: str | None = None) -> list[dict]:
    """
    函数名称：list_user_coupons
    函数用途：返回本人优惠券和尚未落库的领取权益
    参数说明：user 为顾客，status 可筛选可用、使用、过期、同步中和异常
    返回值说明：持久化券 id 为整数；未落库权益 id 为 null 并带 task_id
    核心逻辑：合并用户券和未关联的领取任务，以活动 ID 去重，避免泄露其他用户及内部错误
    异常或失败情况：非顾客或未知状态拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if user.user_type != USER_TYPE_CUSTOMER:
        raise ForbiddenError("只有顾客账号可以查看我的优惠券")
    if status and status not in {COUPON_STATUS_AVAILABLE, COUPON_STATUS_SYNCING, COUPON_STATUS_USED, COUPON_STATUS_EXPIRED, COUPON_STATUS_ABNORMAL}:
        raise BusinessError("优惠券状态筛选不合法", "invalid_coupon_filter")
    _expire_user_coupons(user.id)
    coupons = UserCoupon.query.filter_by(user_id=user.id).order_by(UserCoupon.claimed_at.desc()).all()
    result = [serialize_user_coupon(coupon) for coupon in coupons]
    activity_ids = {coupon.activity_id for coupon in coupons}
    for task in CouponClaimTask.query.filter_by(user_id=user.id).order_by(CouponClaimTask.id.desc()).all():
        if task.activity_id in activity_ids:
            continue
        activity = task.activity
        result.append({
            "id": None, "task_id": task.id, "task_status": task.task_status,
            "activity_id": task.activity_id,
            "activity_name_zh": activity.activity_name_zh, "activity_name_en": activity.activity_name_en,
            "discount_amount": format_money(activity.discount_amount),
            "minimum_order_amount": format_money(activity.minimum_order_amount),
            "coupon_status": COUPON_STATUS_ABNORMAL if task.task_status in (COUPON_TASK_FAILED, COUPON_TASK_DEAD) else COUPON_STATUS_SYNCING,
            "claimed_at": format_datetime(task.redis_success_time), "expired_at": format_datetime(activity.end_at),
            "used_order_id": None, "used_at": None, **_serialize_coupon_scope(activity),
        })
    result = [coupon for coupon in result if not status or coupon["coupon_status"] == status]
    return sorted(result, key=lambda coupon: coupon["claimed_at"] or "", reverse=True)


def list_eligible_user_coupons(
    user,
    store_id: int,
    items_amount: Decimal,
    product_ids: set[int],
) -> list[dict]:
    """返回满足顾客归属、状态、门店、商品、有效期和最低消费规则的可用券。"""
    if user.user_type != USER_TYPE_CUSTOMER:
        raise ForbiddenError("只有顾客账号可以查看我的优惠券")
    if store_id <= 0 or not items_amount.is_finite() or items_amount < 0:
        raise BusinessError("优惠券筛选参数不合法", "invalid_coupon_filter")
    eligible: list[dict] = []
    for coupon in UserCoupon.query.filter_by(user_id=user.id, coupon_status=COUPON_STATUS_AVAILABLE).all():
        if _coupon_is_eligible(coupon, store_id, items_amount, product_ids):
            eligible.append(serialize_user_coupon(coupon))
    return eligible


def reserve_coupon_for_order(
    user,
    user_coupon_id: int | None,
    order,
    items_amount: Decimal,
    product_ids: set[int],
) -> Decimal:
    """
    函数名称：reserve_coupon_for_order
    函数用途：在创建订单事务中锁定并占用一张用户优惠券
    参数说明：user_coupon_id 可空，order 为新订单，items_amount 和 product_ids 为服务端重算结果
    返回值说明：返回实际优惠金额
    核心逻辑：行锁校验券归属与适用范围，以 syncing + used_order_id 表达待支付占用
    异常或失败情况：券不可用、已过期、不满足门店/商品/门槛时失败并回滚订单
    相关业务规则：一张优惠券同一时刻只能被一个待支付订单占用
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if not user_coupon_id:
        return Decimal("0.00")
    coupon = UserCoupon.query.filter_by(id=int(user_coupon_id)).with_for_update().first()
    if coupon is None or coupon.user_id != user.id:
        raise BusinessError("优惠券不存在或不属于当前顾客", "coupon_not_owned")
    if coupon.coupon_status != COUPON_STATUS_AVAILABLE:
        raise BusinessError("优惠券当前不可使用", "coupon_not_available")
    if not _coupon_is_eligible(coupon, order.store_id, items_amount, product_ids):
        raise BusinessError("优惠券不满足当前订单使用条件", "coupon_not_eligible")
    discount_amount = min(Decimal(coupon.discount_amount), items_amount)
    coupon.coupon_status = COUPON_STATUS_SYNCING
    coupon.used_order_id = order.id
    coupon.used_at = None
    order.user_coupon_id = coupon.id
    return discount_amount


def ensure_coupon_reserved_for_retry(order) -> None:
    """重新支付前重新锁定先前因支付失败而释放的优惠券。"""
    if not order.user_coupon_id:
        return
    coupon = UserCoupon.query.filter_by(id=order.user_coupon_id).with_for_update().first()
    if coupon is None or coupon.user_id != order.user_id:
        raise BusinessError("订单优惠券不存在", "coupon_not_available")
    if coupon.coupon_status == COUPON_STATUS_SYNCING and coupon.used_order_id == order.id:
        return
    product_ids = {item.product_id for item in order.items}
    if coupon.coupon_status != COUPON_STATUS_AVAILABLE or not _coupon_is_eligible(
        coupon,
        order.store_id,
        Decimal(order.items_amount),
        product_ids,
    ):
        raise BusinessError("订单优惠券已不可用，请重新下单", "coupon_not_available")
    coupon.coupon_status = COUPON_STATUS_SYNCING
    coupon.used_order_id = order.id


def release_coupon_for_order(order) -> None:
    """支付失败、取消或超时时释放该订单尚未核销的优惠券占用。"""
    if not order.user_coupon_id:
        return
    coupon = UserCoupon.query.filter_by(id=order.user_coupon_id).with_for_update().first()
    if coupon and coupon.used_order_id == order.id and coupon.coupon_status == COUPON_STATUS_SYNCING:
        coupon.coupon_status = COUPON_STATUS_AVAILABLE
        coupon.used_order_id = None
        coupon.used_at = None


def mark_coupon_used(order) -> None:
    """支付成功时将订单占用券核销为 used。"""
    if not order.user_coupon_id:
        return
    coupon = UserCoupon.query.filter_by(id=order.user_coupon_id).with_for_update().first()
    if coupon is None or coupon.used_order_id != order.id or coupon.coupon_status != COUPON_STATUS_SYNCING:
        raise BusinessError("优惠券占用状态异常，无法完成支付", "coupon_reservation_invalid")
    coupon.coupon_status = COUPON_STATUS_USED
    coupon.used_at = current_time()


def process_claim_task(task_id: int, raise_on_error: bool = False) -> dict:
    """
    函数名称：process_claim_task
    函数用途：幂等执行一次抢券成功记录的 MySQL 最终落库
    参数说明：task_id 为落库任务 ID，raise_on_error 控制失败时是否向 Celery 抛出异常
    返回值说明：返回任务序列化结果
    核心逻辑：锁定并刷新任务与用户券的当前状态，创建缺失券后关联成功；重复执行保留已完成结果
    异常或失败情况：数据库异常后重新加锁，仅未完成任务累加失败次数，避免覆盖其他执行者的成功结果
    相关业务规则：重复执行不得重复发券，Redis 成功权益必须保留并可重试
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    # FOR UPDATE 使用当前读；populate_existing 同时替换本会话可能缓存的旧 pending 状态。
    task = CouponClaimTask.query.filter_by(id=task_id).populate_existing().with_for_update().first()
    if task is None:
        raise NotFoundError("抢券落库任务不存在")
    if task.task_status in (COUPON_TASK_SUCCEEDED, COUPON_TASK_DEAD):
        result = serialize_claim_task(task)
        db.session.commit()
        return result
    task.task_status = COUPON_TASK_PROCESSING
    task.last_error = None
    try:
        db.session.flush()
        coupon = UserCoupon.query.filter_by(activity_id=task.activity_id, user_id=task.user_id).populate_existing().with_for_update().first()
        if coupon is None:
            activity = task.activity
            coupon = UserCoupon(
                activity_id=task.activity_id,
                user_id=task.user_id,
                discount_amount=activity.discount_amount,
                minimum_order_amount=activity.minimum_order_amount,
                coupon_status=COUPON_STATUS_AVAILABLE,
                claimed_at=task.redis_success_time,
                expired_at=activity.end_at,
            )
            db.session.add(coupon)
            db.session.flush()
        task.user_coupon_id = coupon.id
        task.task_status = COUPON_TASK_SUCCEEDED
        task.next_retry_at = None
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        task = CouponClaimTask.query.filter_by(id=task_id).populate_existing().with_for_update().first()
        if task is None:
            raise
        if task.task_status in (COUPON_TASK_SUCCEEDED, COUPON_TASK_DEAD):
            result = serialize_claim_task(task)
            db.session.commit()
            _sync_task_status_cache(task)
            return result
        task.retry_count += 1
        task.last_error = str(exc)[:1000]
        max_retries = int(current_app.config.get("COUPON_MAX_RETRIES", 3))
        task.task_status = COUPON_TASK_DEAD if task.retry_count >= max_retries else COUPON_TASK_FAILED
        task.next_retry_at = None if task.task_status == COUPON_TASK_DEAD else current_time() + timedelta(seconds=30 * task.retry_count)
        db.session.commit()
        _sync_task_status_cache(task)
        if raise_on_error:
            raise
        return serialize_claim_task(task)
    _sync_task_status_cache(task)
    return serialize_claim_task(task)


def retry_claim_task(user, task_id: int) -> dict:
    """允许品牌/系统管理员手动恢复 failed 或 dead 任务并立即重试。"""
    _ensure_coupon_admin(user)
    task = CouponClaimTask.query.filter_by(id=task_id).with_for_update().first()
    if task is None:
        raise NotFoundError("抢券落库任务不存在")
    if task.task_status not in (COUPON_TASK_FAILED, COUPON_TASK_DEAD, COUPON_TASK_PENDING):
        raise BusinessError("当前任务状态不允许手动重试", "coupon_task_not_retryable")
    before_status = task.task_status
    task.task_status = COUPON_TASK_PENDING
    task.next_retry_at = current_time()
    db.session.add(_operation_log(user, "retry_claim_task", task.id, {"before_status": before_status}))
    db.session.commit()
    return process_claim_task(task.id)


def list_claim_tasks(user, activity_id: int, status: str | None = None) -> list[dict]:
    """返回后台活动落库任务列表，支持按状态筛选。"""
    _ensure_coupon_admin(user)
    if db.session.get(CouponActivity, activity_id) is None:
        raise NotFoundError("优惠券活动不存在")
    query = CouponClaimTask.query.filter_by(activity_id=activity_id)
    if status and status not in {COUPON_TASK_PENDING, COUPON_TASK_PROCESSING, COUPON_TASK_SUCCEEDED, COUPON_TASK_FAILED, COUPON_TASK_DEAD}:
        raise BusinessError("任务状态筛选不合法", "invalid_coupon_filter")
    if status:
        query = query.filter_by(task_status=status)
    return [serialize_claim_task(task) for task in query.order_by(CouponClaimTask.id.desc()).all()]


def reconcile_activity(user, activity_id: int) -> dict:
    """
    函数名称：reconcile_activity
    函数用途：对比 Redis 成功用户与 MySQL 用户优惠券并生成缺失补偿任务
    参数说明：user 为后台操作人，activity_id 为活动 ID
    返回值说明：返回 Redis、MySQL、任务和差异指标
    核心逻辑：获取短期对账锁计算集合差异；按任务、用户券顺序加锁复核当前状态，只恢复仍缺失的权益
    异常或失败情况：活动不存在、无权限、Redis 不可用或同活动正在对账时失败
    相关业务规则：对账不直接删除任一侧记录，数据库多出的记录只标记统计异常
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_coupon_admin(user)
    activity = db.session.get(CouponActivity, activity_id)
    if activity is None:
        raise NotFoundError("优惠券活动不存在")
    redis_store = get_coupon_redis_store()
    reconcile_token = redis_store.acquire_reconcile_lock(activity.id)
    if not reconcile_token:
        raise BusinessError("当前活动正在对账，请稍后重试", "coupon_reconcile_in_progress", 409)
    try:
        redis_metrics = redis_store.metrics(activity.id)
        redis_users = set(redis_metrics["successful_user_ids"])
        database_users = {
            coupon.user_id for coupon in UserCoupon.query.filter_by(activity_id=activity.id).all()
        }
        missing_database_users = redis_users - database_users
        for user_id in sorted(missing_database_users):
            task = CouponClaimTask.query.filter_by(activity_id=activity.id, user_id=user_id).populate_existing().with_for_update().first()
            # Worker 可能在对账普通快照之后完成；保持与落库一致的锁顺序，以当前读再次确认。
            coupon = UserCoupon.query.filter_by(activity_id=activity.id, user_id=user_id).populate_existing().with_for_update().first()
            if coupon is not None:
                database_users.add(user_id)
                missing_database_users.discard(user_id)
                continue
            if task is None:
                db.session.add(
                    CouponClaimTask(
                        activity_id=activity.id,
                        user_id=user_id,
                        redis_success_time=current_time(),
                        task_status=COUPON_TASK_PENDING,
                    )
                )
            elif task.task_status != COUPON_TASK_SUCCEEDED:
                task.task_status = COUPON_TASK_PENDING
                task.next_retry_at = current_time()
        db.session.add(
            _operation_log(
                user,
                "reconcile",
                activity.id,
                {
                    "redis_success_count": len(redis_users),
                    "database_count": len(database_users),
                    "compensation_count": len(missing_database_users),
                },
            )
        )
        db.session.commit()
        return build_activity_metrics(activity.id, database_only_users=database_users - redis_users)
    finally:
        redis_store.release_reconcile_lock(activity.id, reconcile_token)


def build_activity_metrics(activity_id: int, database_only_users: set[int] | None = None) -> dict:
    """聚合活动的 Redis 过程数据、MySQL 长期数据与落库任务状态。"""
    activity = db.session.get(CouponActivity, activity_id)
    if activity is None:
        raise NotFoundError("优惠券活动不存在")
    try:
        redis_metrics = get_coupon_redis_store().metrics(activity.id)
    except Exception:
        redis_metrics = {"remaining_stock": None, "success_count": 0, "successful_user_ids": []}
    coupons = UserCoupon.query.filter_by(activity_id=activity.id).all()
    task_counts = {
        status: CouponClaimTask.query.filter_by(activity_id=activity.id, task_status=status).count()
        for status in (
            COUPON_TASK_PENDING,
            COUPON_TASK_PROCESSING,
            COUPON_TASK_FAILED,
            COUPON_TASK_DEAD,
            COUPON_TASK_SUCCEEDED,
        )
    }
    used_count = sum(coupon.coupon_status == COUPON_STATUS_USED for coupon in coupons)
    database_count = len(coupons)
    redis_success_count = int(redis_metrics["success_count"])
    return {
        "activity_id": activity.id,
        "total_stock": activity.total_stock,
        "redis_remaining_stock": redis_metrics["remaining_stock"],
        "redis_success_count": redis_success_count,
        "database_count": database_count,
        "pending_count": task_counts[COUPON_TASK_PENDING] + task_counts[COUPON_TASK_PROCESSING],
        "failed_count": task_counts[COUPON_TASK_FAILED],
        "dead_count": task_counts[COUPON_TASK_DEAD],
        "succeeded_task_count": task_counts[COUPON_TASK_SUCCEEDED],
        "difference_count": max(redis_success_count - database_count, 0),
        "database_only_count": len(database_only_users or set()),
        "used_count": used_count,
        "redemption_rate": f"{(used_count / database_count * 100) if database_count else 0:.2f}",
    }


def serialize_activity(activity: CouponActivity, include_metrics: bool = False) -> dict:
    now = current_time()
    effective_status = activity.activity_status
    if effective_status in {"scheduled", "active"}:
        if now < activity.start_at:
            effective_status = "scheduled"
        elif now >= activity.end_at:
            effective_status = "ended"
        else:
            effective_status = "active"
    result = {
        "id": activity.id,
        "activity_name_zh": activity.activity_name_zh,
        "activity_name_en": activity.activity_name_en,
        "description_zh": activity.description_zh,
        "description_en": activity.description_en,
        "start_at": format_datetime(activity.start_at),
        "end_at": format_datetime(activity.end_at),
        "total_stock": activity.total_stock,
        "per_user_limit": activity.per_user_limit,
        "discount_amount": format_money(activity.discount_amount),
        "minimum_order_amount": format_money(activity.minimum_order_amount),
        "activity_status": activity.activity_status,
        "effective_status": effective_status,
        "store_ids": [link.store_id for link in activity.store_links],
        "product_ids": [link.product_id for link in activity.product_links],
    }
    if include_metrics:
        metrics = build_activity_metrics(activity.id)
        result["remaining_stock"] = metrics["redis_remaining_stock"]
        result["claimed_count"] = metrics["redis_success_count"]
    return result


def serialize_user_coupon(coupon: UserCoupon) -> dict:
    return {
        "id": coupon.id,
        "activity_id": coupon.activity_id,
        "activity_name_zh": coupon.activity.activity_name_zh,
        "activity_name_en": coupon.activity.activity_name_en,
        "discount_amount": format_money(coupon.discount_amount),
        "minimum_order_amount": format_money(coupon.minimum_order_amount),
        "coupon_status": coupon.coupon_status,
        "claimed_at": format_datetime(coupon.claimed_at),
        "expired_at": format_datetime(coupon.expired_at),
        "used_order_id": coupon.used_order_id,
        "used_at": format_datetime(coupon.used_at),
        "task_id": None,
        "task_status": None,
        **_serialize_coupon_scope(coupon.activity),
    }


def _serialize_coupon_scope(activity: CouponActivity) -> dict:
    return {
        "store_ids": [link.store_id for link in activity.store_links],
        "product_ids": [link.product_id for link in activity.product_links],
        "scope_stores": [{"id": link.store_id, "name_zh": link.store.name_zh, "name_en": link.store.name_en} for link in activity.store_links],
        "scope_products": [{"id": link.product_id, "name_zh": link.product.name_zh, "name_en": link.product.name_en} for link in activity.product_links],
    }


def get_claim_task(user, task_id: int) -> dict:
    """后台管理员读取单个任务详情；顾客同步状态只能从本人优惠券查询获得。"""
    _ensure_coupon_admin(user)
    task = db.session.get(CouponClaimTask, task_id)
    if task is None:
        raise NotFoundError("抢券落库任务不存在")
    return serialize_claim_task(task)


def serialize_claim_task(task: CouponClaimTask) -> dict:
    return {
        "id": task.id,
        "activity_id": task.activity_id,
        "activity_name_zh": task.activity.activity_name_zh,
        "activity_name_en": task.activity.activity_name_en,
        "user_id": task.user_id,
        "user_coupon_id": task.user_coupon_id,
        "redis_success_time": format_datetime(task.redis_success_time),
        "task_status": task.task_status,
        "retry_count": task.retry_count,
        "last_error": task.last_error,
        "next_retry_at": format_datetime(task.next_retry_at),
        "created_at": format_datetime(task.created_at),
        "updated_at": format_datetime(task.updated_at),
    }


def _ensure_activity_claimable(activity: CouponActivity) -> None:
    now = current_time()
    if activity.activity_status == "paused":
        raise BusinessError("活动已暂停", "coupon_activity_paused")
    if activity.activity_status in {"ended", "sold_out"}:
        raise BusinessError("活动已结束或优惠券已抢完", "coupon_activity_ended")
    if now < activity.start_at:
        raise BusinessError("活动尚未开始", "coupon_activity_not_started")
    if now >= activity.end_at:
        raise BusinessError("活动已结束", "coupon_activity_ended")
    if activity.activity_status not in {"active", "scheduled"}:
        raise BusinessError("活动当前不可领取", "coupon_activity_not_active")


def _coupon_is_eligible(
    coupon: UserCoupon,
    store_id: int,
    items_amount: Decimal,
    product_ids: set[int],
) -> bool:
    now = current_time()
    if coupon.expired_at and coupon.expired_at <= now:
        return False
    if coupon.activity.end_at <= now:
        return False
    if Decimal(coupon.minimum_order_amount) > items_amount:
        return False
    store_ids = {link.store_id for link in coupon.activity.store_links}
    if store_ids and store_id not in store_ids:
        return False
    scoped_product_ids = {link.product_id for link in coupon.activity.product_links}
    if scoped_product_ids and not scoped_product_ids.intersection(product_ids):
        return False
    return True


def _expire_user_coupons(user_id: int) -> None:
    now = current_time()
    coupons = UserCoupon.query.filter_by(user_id=user_id, coupon_status=COUPON_STATUS_AVAILABLE).all()
    changed = False
    for coupon in coupons:
        if (coupon.expired_at and coupon.expired_at <= now) or coupon.activity.end_at <= now:
            coupon.coupon_status = COUPON_STATUS_EXPIRED
            changed = True
    if changed:
        db.session.commit()


def _ensure_coupon_admin(user) -> None:
    if not user.has_any_role((ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("只有品牌管理员或系统管理员可以执行该操作")


def _operation_log(user, operation_type: str, target_id: int, after_snapshot: dict) -> OperationLog:
    return OperationLog(
        operator_id=user.id,
        operator_role_code=user.first_role_code(),
        operation_module="coupon",
        operation_type=operation_type,
        target_id=target_id,
        before_snapshot=None,
        after_snapshot=after_snapshot,
        operation_result=OPERATION_RESULT_SUCCESS,
    )


def _sync_task_status_cache(task: CouponClaimTask) -> None:
    try:
        get_coupon_redis_store().set_task_status(
            task.id,
            {
                "task_id": task.id,
                "activity_id": task.activity_id,
                "user_id": task.user_id,
                "status": task.task_status,
                "retry_count": task.retry_count,
                "last_error": task.last_error,
                "updated_at": format_datetime(task.updated_at),
            },
        )
    except Exception:
        current_app.logger.warning("Failed to update coupon task Redis snapshot", exc_info=True)


def _dispatch_claim_task(task_id: int) -> None:
    try:
        from app.tasks.coupon_tasks import persist_coupon_claim_task

        persist_coupon_claim_task.delay(task_id)
    except Exception:
        current_app.logger.warning("Coupon task dispatch failed; scheduled retry will pick it up", exc_info=True)


def synchronize_activity_statuses() -> dict:
    """
    函数名称：synchronize_activity_statuses
    函数用途：定时推进活动开始与结束状态
    参数说明：无
    返回值说明：本次启用和结束活动数
    核心逻辑：条件更新 scheduled 到期活动，保留暂停状态；结束过期活动，提交同一事务
    异常或失败情况：数据库不可用时交由任务调度重试
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    now = current_time()
    started_count = CouponActivity.query.filter(
        CouponActivity.activity_status == "scheduled", CouponActivity.start_at <= now, CouponActivity.end_at > now,
    ).update({CouponActivity.activity_status: "active"}, synchronize_session=False)
    ended_count = CouponActivity.query.filter(
        CouponActivity.activity_status.in_(("scheduled", "active", "paused", "sold_out")), CouponActivity.end_at <= now,
    ).update({CouponActivity.activity_status: "ended"}, synchronize_session=False)
    db.session.commit()
    return {"started_count": started_count, "ended_count": ended_count}
