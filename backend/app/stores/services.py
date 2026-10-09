"""
文件名称：services.py
文件用途：实现门店查询和门店后台营业状态维护业务服务
主要职责：返回可选门店列表、计算当前是否可下单并维护门店营业状态
所属业务模块：门店
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from app.audit.models import OperationLog
from app.common.decorators import ensure_user_can_access_store
from app.common.enums import (
    OPERATION_RESULT_SUCCESS,
    ROLE_BRAND_ADMIN,
    ROLE_STORE_MANAGER,
    ROLE_SYSTEM_ADMIN,
    STORE_STATUS_CLOSED,
    STORE_STATUS_OPEN,
    STORE_STATUS_TEMPORARILY_CLOSED,
)
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.common.formatters import format_time
from app.common.time_utils import current_time, is_time_in_business_range
from app.extensions import db
from app.stores.models import Store

STORE_STATUS_VALUES = {STORE_STATUS_OPEN, STORE_STATUS_CLOSED, STORE_STATUS_TEMPORARILY_CLOSED}


def serialize_store(store: Store) -> dict:
    now = current_time().time()
    is_in_business_time = is_time_in_business_range(now, store.business_start_time, store.business_end_time)
    can_order = bool(store.is_active and store.store_status == STORE_STATUS_OPEN and is_in_business_time)
    return {
        "id": store.id,
        "store_code": store.store_code,
        "name_zh": store.name_zh,
        "name_en": store.name_en,
        "address": store.address,
        "phone": store.phone,
        "business_start_time": format_time(store.business_start_time),
        "business_end_time": format_time(store.business_end_time),
        "store_status": store.store_status,
        "temporary_close_reason": store.temporary_close_reason,
        "is_active": bool(store.is_active),
        "can_order": can_order,
    }


def list_active_stores() -> list[dict]:
    stores = Store.query.filter_by(is_active=True).order_by(Store.id.asc()).all()
    return [serialize_store(store) for store in stores]


def update_store_operation_status(user, store_id: int, payload: dict) -> dict:
    """
    函数名称：update_store_operation_status
    函数用途：门店经理维护本门店营业状态
    参数说明：user 为当前后台用户，store_id 为门店 ID，payload 包含 store_status 和 temporary_close_reason
    返回值说明：返回更新后的门店摘要
    核心逻辑：校验门店数据范围和经理角色，更新营业状态并记录操作日志
    异常或失败情况：门店不存在、状态值非法或账号权限不足时失败
    相关业务规则：门店非 open 状态时顾客可以浏览但不能下单
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    ensure_user_can_access_store(user, store_id)
    if not user.has_any_role((ROLE_STORE_MANAGER, ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("只有门店经理可以维护门店营业状态")

    store = Store.query.filter_by(id=store_id).with_for_update().first()
    if store is None or not store.is_active:
        raise NotFoundError("门店不存在或已停用")

    next_status = str(payload.get("store_status") or "").strip()
    if next_status not in STORE_STATUS_VALUES:
        raise BusinessError("门店营业状态不合法", "invalid_store_status")

    before_snapshot = {
        "store_status": store.store_status,
        "temporary_close_reason": store.temporary_close_reason,
    }
    store.store_status = next_status
    store.temporary_close_reason = (payload.get("temporary_close_reason") or "")[:255] or None
    after_snapshot = {
        "store_status": store.store_status,
        "temporary_close_reason": store.temporary_close_reason,
    }
    db.session.add(
        OperationLog(
            operator_id=user.id,
            operator_role_code=user.first_role_code(),
            operation_module="store",
            operation_type="update_status",
            target_id=store.id,
            store_id=store.id,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            operation_result=OPERATION_RESULT_SUCCESS,
        )
    )
    db.session.commit()
    return serialize_store(store)
