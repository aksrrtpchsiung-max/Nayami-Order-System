"""
文件名称：coupon_tasks.py
文件用途：执行抢券成功后的异步落库与失败任务扫描
主要职责：消费单个落库任务、按 next_retry_at 扫描 pending/failed 任务并触发幂等处理
所属业务模块：优惠券异步任务
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from app.common.enums import COUPON_TASK_FAILED, COUPON_TASK_PENDING
from app.common.time_utils import current_time
from app.coupons.models import CouponClaimTask
from app.coupons.services import process_claim_task, synchronize_activity_statuses
from celery_runtime import celery_app


@celery_app.task(
    bind=True,
    name="nayami.persist_coupon_claim",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def persist_coupon_claim_task(self, task_id: int) -> dict:
    """执行一个落库任务；异常由 Celery 退避重试，业务状态同步写入 MySQL。"""
    return process_claim_task(task_id, raise_on_error=True)


@celery_app.task(name="nayami.coupon_retry_scan")
def scan_retryable_coupon_tasks(batch_size: int = 100) -> dict:
    """扫描到期的 pending/failed 任务并逐个执行，避免短暂投递失败造成权益丢失。"""
    now = current_time()
    tasks = (
        CouponClaimTask.query.filter(
            CouponClaimTask.task_status.in_((COUPON_TASK_PENDING, COUPON_TASK_FAILED)),
            (CouponClaimTask.next_retry_at.is_(None)) | (CouponClaimTask.next_retry_at <= now),
        )
        .order_by(CouponClaimTask.id.asc())
        .limit(batch_size)
        .all()
    )
    results = [process_claim_task(task.id) for task in tasks]
    return {"processed_count": len(results), "task_ids": [task.id for task in tasks]}


@celery_app.task(name="nayami.coupon_activity_status_scan")
def scan_coupon_activity_statuses() -> dict:
    """按时间推进活动状态；暂停活动在期限内保持暂停。"""
    return synchronize_activity_statuses()
