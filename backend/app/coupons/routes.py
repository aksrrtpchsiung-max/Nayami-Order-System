"""
文件名称：routes.py
文件用途：定义顾客优惠券和后台抢券运维 API
主要职责：提供活动列表、抢券、我的优惠券、可用券、预热、任务重试和对账接口
所属业务模块：优惠券与高并发抢券
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.errors import BusinessError
from app.common.responses import success_response
from app.coupons.services import (
    claim_coupon,
    get_claim_task,
    list_claim_tasks,
    list_eligible_user_coupons,
    list_public_activities,
    list_user_coupons,
    reconcile_activity,
    retry_claim_task,
    warmup_activity,
)

coupons_bp = Blueprint("coupons", __name__)


@coupons_bp.get("/activities")
def activities():
    return success_response(list_public_activities())


@coupons_bp.post("/activities/<int:activity_id>/claim")
def claim(activity_id: int):
    return success_response(
        claim_coupon(get_current_user(), activity_id, request.get_json(silent=True) or {}),
        202,
    )


@coupons_bp.get("/me")
def my_coupons():
    return success_response(list_user_coupons(get_current_user(), request.args.get("status")))


@coupons_bp.get("/eligible")
def eligible_coupons():
    try:
        items_amount = Decimal(request.args.get("items_amount") or "0")
        store_id = int(request.args.get("store_id") or 0)
        product_ids = {
            int(value)
            for value in (request.args.get("product_ids") or "").split(",")
            if value.strip()
        }
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError("优惠券筛选参数不合法", "invalid_coupon_filter") from exc
    return success_response(
        list_eligible_user_coupons(
            get_current_user(),
            store_id,
            items_amount,
            product_ids,
        )
    )


@coupons_bp.post("/activities/<int:activity_id>/warmup")
def warmup(activity_id: int):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("force", False), bool):
        raise BusinessError("预热强制标志必须为布尔值", "invalid_boolean")
    return success_response(warmup_activity(get_current_user(), activity_id, payload.get("force", False)))


@coupons_bp.get("/activities/<int:activity_id>/tasks")
def activity_tasks(activity_id: int):
    return success_response(list_claim_tasks(get_current_user(), activity_id, request.args.get("status")))


@coupons_bp.post("/tasks/<int:task_id>/retry")
def retry_task(task_id: int):
    return success_response(retry_claim_task(get_current_user(), task_id))


@coupons_bp.get("/tasks/<int:task_id>")
def claim_task_detail(task_id: int):
    return success_response(get_claim_task(get_current_user(), task_id))


@coupons_bp.post("/activities/<int:activity_id>/reconcile")
def reconcile(activity_id: int):
    return success_response(reconcile_activity(get_current_user(), activity_id))
