"""
文件名称：reconciliation_tasks.py
文件用途：定时发现已结束优惠券活动并执行系统对账
主要职责：比较 Redis 成功集合与 MySQL 长期记录，生成缺失补偿任务
所属业务模块：优惠券异步任务
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from app.common.time_utils import current_time
from app.coupons.models import CouponActivity
from app.coupons.services import reconcile_activity
from app.users.models import Role, User, UserRole
from celery_runtime import celery_app


@celery_app.task(name="nayami.coupon_ended_activity_reconcile")
def reconcile_ended_activities(batch_size: int = 20) -> dict:
    """使用系统管理员身份对到期活动执行补偿对账；没有管理员时跳过并返回原因。"""
    system_admin = (
        User.query.join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(Role.role_code == "system_admin")
        .filter(User.is_active.is_(True))
        .first()
    )
    if system_admin is None:
        return {"reconciled_count": 0, "reason": "system_admin_not_found"}
    activities = (
        CouponActivity.query.filter(
            CouponActivity.end_at <= current_time(),
            CouponActivity.activity_status.in_(("active", "ended", "sold_out")),
        )
        .order_by(CouponActivity.end_at.asc())
        .limit(batch_size)
        .all()
    )
    results = [reconcile_activity(system_admin, activity.id) for activity in activities]
    return {"reconciled_count": len(results), "activity_ids": [activity.id for activity in activities]}
