"""
文件名称：services.py
文件用途：实现库存预占、确认扣减、释放和门店库存维护服务
主要职责：封装库存数量变更、门店库存列表、人工调整和库存日志写入
所属业务模块：库存
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import timedelta

from app.common.time_utils import current_time
from app.audit.models import OperationLog
from app.catalog.models import StoreProduct
from app.common.decorators import ensure_user_can_access_store
from app.common.enums import (
    INVENTORY_CHANGE_CONFIRM_DEDUCT,
    INVENTORY_CHANGE_MANUAL_ADJUST,
    INVENTORY_CHANGE_RELEASE,
    INVENTORY_CHANGE_REFUND_RESTORE,
    INVENTORY_CHANGE_RESERVE,
    OPERATION_RESULT_SUCCESS,
    ROLE_BRAND_ADMIN,
    ROLE_STORE_MANAGER,
    ROLE_STORE_STAFF,
    ROLE_SYSTEM_ADMIN,
)
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.common.formatters import format_datetime, format_money
from app.extensions import db
from app.inventory.models import InventoryLog


def reserve_stock(store_product, quantity: int, order_id: int | None = None) -> None:
    """
    函数名称：reserve_stock
    函数用途：为待支付订单预占门店商品库存
    参数说明：store_product 为门店商品记录，quantity 为预占数量，order_id 为关联订单 ID
    返回值说明：无返回值，直接更新 ORM 对象并写库存日志
    核心逻辑：锁定并刷新库存行，校验可用库存，增加 reserved_stock，记录 reserve 日志
    异常或失败情况：可用库存不足时抛出库存不足错误
    相关业务规则：订单创建时只预占库存，支付成功后才确认扣减
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    store_product = _lock_stock(store_product, quantity)
    available_stock = store_product.current_stock - store_product.reserved_stock
    if available_stock < quantity:
        raise BusinessError("商品库存不足", "insufficient_stock")
    before_current_stock = store_product.current_stock
    before_reserved_stock = store_product.reserved_stock
    store_product.reserved_stock += quantity
    _append_inventory_log(
        store_product,
        INVENTORY_CHANGE_RESERVE,
        quantity,
        before_current_stock,
        store_product.current_stock,
        before_reserved_stock,
        store_product.reserved_stock,
        order_id,
        "订单创建预占库存",
    )


def confirm_deduct_stock(store_product, quantity: int, order_id: int) -> None:
    """
    函数名称：confirm_deduct_stock
    函数用途：支付成功后确认扣减已预占库存
    参数说明：store_product 为门店商品记录，quantity 为扣减数量，order_id 为关联订单 ID
    返回值说明：无返回值，直接更新 ORM 对象并写库存日志
    核心逻辑：锁定并刷新库存行，以当前读校验订单预占流水余额，再扣减库存并记录 confirm_deduct 日志
    异常或失败情况：预占数量不足或当前库存不足时抛出库存异常
    相关业务规则：重复支付回调不能重复扣减库存
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    store_product = _lock_stock(store_product, quantity)
    outstanding_quantity = _outstanding_reserved_quantity(store_product.id, order_id)
    if outstanding_quantity < quantity or store_product.reserved_stock < quantity or store_product.current_stock < quantity:
        raise BusinessError("库存预占记录异常，无法确认扣减", "inventory_reservation_invalid")
    before_current_stock = store_product.current_stock
    before_reserved_stock = store_product.reserved_stock
    store_product.reserved_stock -= quantity
    store_product.current_stock -= quantity
    _append_inventory_log(
        store_product,
        INVENTORY_CHANGE_CONFIRM_DEDUCT,
        quantity,
        before_current_stock,
        store_product.current_stock,
        before_reserved_stock,
        store_product.reserved_stock,
        order_id,
        "支付成功确认扣减库存",
    )


def release_reserved_stock(store_product, quantity: int, order_id: int, remark: str = "订单取消释放预占库存") -> int:
    """
    函数名称：release_reserved_stock
    函数用途：取消或支付超时后释放订单创建时预占的门店商品库存
    参数说明：store_product 为门店商品记录，quantity 为计划释放数量，order_id 为关联订单 ID，remark 为库存日志说明
    返回值说明：返回实际释放的预占库存数量；没有可释放库存时返回 0
    核心逻辑：锁定并刷新库存行，按计划数量、订单剩余预占与当前 reserved_stock 的最小值释放并记录 release 日志
    异常或失败情况：释放数量小于等于 0 时拒绝；重复释放时不会让 reserved_stock 变成负数
    相关业务规则：支付失败、顾客取消和支付超时必须释放预占库存，释放动作应具备幂等保护
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if quantity <= 0:
        raise BusinessError("释放库存数量必须大于 0", "invalid_quantity")
    store_product = _lock_stock(store_product, quantity)
    outstanding_quantity = _outstanding_reserved_quantity(store_product.id, order_id)
    release_quantity = min(quantity, outstanding_quantity, store_product.reserved_stock)
    if release_quantity <= 0:
        return 0

    before_current_stock = store_product.current_stock
    before_reserved_stock = store_product.reserved_stock
    store_product.reserved_stock -= release_quantity
    _append_inventory_log(
        store_product,
        INVENTORY_CHANGE_RELEASE,
        release_quantity,
        before_current_stock,
        store_product.current_stock,
        before_reserved_stock,
        store_product.reserved_stock,
        order_id,
        remark,
    )
    return release_quantity


def restore_refunded_stock(store_product, quantity: int, order_id: int, operator_id: int | None = None) -> int:
    """
    函数名称：restore_refunded_stock
    函数用途：仿真退款成功后恢复此前已确认扣减的门店商品库存
    参数说明：store_product 为门店商品，quantity 为计划恢复数量，order_id 为订单 ID，operator_id 为操作人
    返回值说明：返回实际恢复数量，重复退款调用返回 0
    核心逻辑：按订单库存日志计算尚未恢复的确认扣减量，增加 current_stock 并写 refund_restore 日志
    异常或失败情况：数量小于等于 0 时拒绝；不存在已确认扣减记录时不重复恢复
    相关业务规则：退款恢复必须以订单维度幂等，不能影响其他订单库存
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if quantity <= 0:
        raise BusinessError("退款恢复库存数量必须大于 0", "invalid_quantity")
    store_product = _lock_stock(store_product, quantity)
    confirmed_quantity = _sum_order_inventory_change(
        store_product.id,
        order_id,
        INVENTORY_CHANGE_CONFIRM_DEDUCT,
    )
    restored_quantity = _sum_order_inventory_change(
        store_product.id,
        order_id,
        INVENTORY_CHANGE_REFUND_RESTORE,
    )
    restore_quantity = min(quantity, max(confirmed_quantity - restored_quantity, 0))
    if restore_quantity <= 0:
        return 0
    before_current_stock = store_product.current_stock
    before_reserved_stock = store_product.reserved_stock
    store_product.current_stock += restore_quantity
    _append_inventory_log(
        store_product,
        INVENTORY_CHANGE_REFUND_RESTORE,
        restore_quantity,
        before_current_stock,
        store_product.current_stock,
        before_reserved_stock,
        store_product.reserved_stock,
        order_id,
        "仿真退款成功恢复已扣减库存",
        operator_id,
    )
    return restore_quantity


def _append_inventory_log(
    store_product,
    change_type: str,
    quantity: int,
    before_current_stock: int,
    after_current_stock: int,
    before_reserved_stock: int,
    after_reserved_stock: int,
    order_id: int | None,
    remark: str,
    operator_id: int | None = None,
) -> None:
    db.session.add(
        InventoryLog(
            store_id=store_product.store_id,
            store_product_id=store_product.id,
            order_id=order_id,
            change_type=change_type,
            change_quantity=quantity,
            before_current_stock=before_current_stock,
            after_current_stock=after_current_stock,
            before_reserved_stock=before_reserved_stock,
            after_reserved_stock=after_reserved_stock,
            operator_id=operator_id,
            remark=remark,
        )
    )


def _outstanding_reserved_quantity(store_product_id: int, order_id: int) -> int:
    reserved_quantity = _sum_order_inventory_change(
        store_product_id,
        order_id,
        INVENTORY_CHANGE_RESERVE,
    )
    confirmed_quantity = _sum_order_inventory_change(
        store_product_id,
        order_id,
        INVENTORY_CHANGE_CONFIRM_DEDUCT,
    )
    released_quantity = _sum_order_inventory_change(
        store_product_id,
        order_id,
        INVENTORY_CHANGE_RELEASE,
    )
    return max(reserved_quantity - confirmed_quantity - released_quantity, 0)


def _sum_order_inventory_change(store_product_id: int, order_id: int, change_type: str) -> int:
    # MySQL 可重复读下必须使用当前读，不能在等待库存锁后复用旧快照中的流水余额。
    rows = InventoryLog.query.filter_by(store_product_id=store_product_id, order_id=order_id, change_type=change_type).with_entities(InventoryLog.change_quantity).with_for_update().all()
    return sum(row.change_quantity for row in rows)


def list_store_inventory(user, store_id: int) -> list[dict]:
    """
    函数名称：list_store_inventory
    函数用途：查询门店后台库存维护列表
    参数说明：user 为当前后台用户，store_id 为门店 ID
    返回值说明：返回当前门店商品的库存、售罄和可售状态列表
    核心逻辑：校验门店数据范围和门店后台角色，按分类和商品排序返回门店商品快照
    异常或失败情况：账号无门店权限或无后台角色时拒绝访问
    相关业务规则：门店库存维护必须按门店数据范围隔离
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_store_workspace_viewer(user, store_id)
    store_products = (
        StoreProduct.query.join(StoreProduct.product)
        .filter(StoreProduct.store_id == store_id)
        .order_by(StoreProduct.id.asc())
        .all()
    )
    return [serialize_store_inventory_item(store_product) for store_product in store_products]


def update_store_inventory_item(user, store_product_id: int, payload: dict) -> dict:
    """
    函数名称：update_store_inventory_item
    函数用途：门店经理维护本店商品库存、可售状态和售罄状态
    参数说明：user 为当前后台用户，store_product_id 为门店商品 ID，payload 包含 current_stock、is_available、is_sold_out 和 reason
    返回值说明：返回更新后的门店商品库存快照
    核心逻辑：校验门店数据范围和经理权限，锁定门店商品，校验库存下限，写库存日志和操作日志
    异常或失败情况：越权、商品不存在、当前库存小于预占库存或参数非法时失败
    相关业务规则：人工库存维护不能破坏已预占库存，售罄和恢复可售都必须留痕
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    store_product = StoreProduct.query.filter_by(id=store_product_id).populate_existing().with_for_update().first()
    if store_product is None:
        raise NotFoundError("门店商品不存在")
    _ensure_store_inventory_manager(user, store_product.store_id)

    reason = str(payload.get("reason") or "门店后台人工调整库存").strip()
    if not reason or len(reason) > 500:
        raise BusinessError("库存调整原因必须为 1 到 500 个字符", "invalid_inventory_reason")
    before_snapshot = _build_inventory_snapshot(store_product)
    before_current_stock = store_product.current_stock
    before_reserved_stock = store_product.reserved_stock

    if "current_stock" in payload:
        next_current_stock = payload.get("current_stock")
        if type(next_current_stock) is not int or not 0 <= next_current_stock <= 2147483647:
            raise BusinessError("当前库存不能小于 0", "invalid_current_stock")
        if next_current_stock < store_product.reserved_stock:
            raise BusinessError("当前库存不能小于已预占库存", "current_stock_less_than_reserved")
        store_product.current_stock = next_current_stock
    for field_name in ("is_available", "is_sold_out"):
        if field_name in payload:
            if type(payload[field_name]) is not bool:
                raise BusinessError("可售与售罄状态必须为布尔值", "invalid_inventory_flag")
            setattr(store_product, field_name, payload[field_name])
    if payload.get("is_available") is True or payload.get("is_sold_out") is False:
        if store_product.product.menu_status not in ("published", "draft_changes"):
            raise BusinessError("草稿或归档商品不能恢复可售", "product_not_available")

    store_product.last_operator_id = user.id
    after_snapshot = {**_build_inventory_snapshot(store_product), "reason": reason}
    if before_current_stock != store_product.current_stock:
        _append_inventory_log(
            store_product,
            INVENTORY_CHANGE_MANUAL_ADJUST,
            abs(store_product.current_stock - before_current_stock),
            before_current_stock,
            store_product.current_stock,
            before_reserved_stock,
            store_product.reserved_stock,
            None,
            reason,
            user.id,
        )
    db.session.add(
        OperationLog(
            operator_id=user.id,
            operator_role_code=user.first_role_code(),
            operation_module="inventory",
            operation_type="update_store_product",
            target_id=store_product.id,
            store_id=store_product.store_id,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            operation_result=OPERATION_RESULT_SUCCESS,
        )
    )
    db.session.commit()
    return serialize_store_inventory_item(store_product)


def serialize_store_inventory_item(store_product: StoreProduct) -> dict:
    product = store_product.product
    available_stock = max(store_product.current_stock - store_product.reserved_stock, 0)
    return {
        "store_product_id": store_product.id,
        "store_id": store_product.store_id,
        "product_id": product.id,
        "category_id": product.category_id,
        "category_name_zh": product.category.name_zh if product.category else None,
        "category_name_en": product.category.name_en if product.category else None,
        "name_zh": product.name_zh,
        "name_en": product.name_en,
        "image_url": product.image_url,
        "base_price": format_money(product.base_price),
        "menu_status": product.menu_status,
        "is_available": bool(store_product.is_available),
        "current_stock": store_product.current_stock,
        "reserved_stock": store_product.reserved_stock,
        "available_stock": available_stock,
        "is_sold_out": bool(store_product.is_sold_out),
        "can_add_to_cart": bool(product.menu_status == "published" and store_product.is_available and not store_product.is_sold_out and available_stock > 0),
    }


def _ensure_store_workspace_viewer(user, store_id: int) -> None:
    ensure_user_can_access_store(user, store_id)
    if not user.has_any_role((ROLE_STORE_STAFF, ROLE_STORE_MANAGER, ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能访问门店工作台")


def _ensure_store_inventory_manager(user, store_id: int) -> None:
    ensure_user_can_access_store(user, store_id)
    if not user.has_any_role((ROLE_STORE_MANAGER, ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("只有门店经理可以维护门店库存")


def _build_inventory_snapshot(store_product: StoreProduct) -> dict:
    return {
        "current_stock": store_product.current_stock,
        "reserved_stock": store_product.reserved_stock,
        "is_available": bool(store_product.is_available),
        "is_sold_out": bool(store_product.is_sold_out),
    }


def _lock_stock(store_product, quantity: int):
    """
    函数名称：_lock_stock
    函数用途：锁定并刷新库存行，防止不同订单间覆盖库存更新
    参数说明：store_product 为库存行，quantity 为正整数变更量
    返回值说明：返回数据库当前库存对象
    核心逻辑：校验数量后通过 SELECT FOR UPDATE 读取最新值；调用者须按商品 ID 顺序锁定
    异常或失败情况：非法数量或不存在的门店商品时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if type(quantity) is not int or quantity <= 0 or quantity > 2147483647:
        raise BusinessError("库存变更数量必须是正整数", "invalid_quantity")
    locked = StoreProduct.query.filter_by(id=store_product.id).populate_existing().with_for_update().first()
    if locked is None:
        raise NotFoundError("门店商品不存在")
    return locked


def list_store_inventory_logs(user, store_id: int, *, store_product_id: int | None = None, change_type: str | None = None, days: int = 7) -> list[dict]:
    """
    函数名称：list_store_inventory_logs
    函数用途：为门店经理查询有原因和前后库存快照的调整流水
    参数说明：store_id 为门店；商品、变更类型可筛选；days 为 1/7/30
    返回值说明：返回按时间倒序的库存流水数组
    核心逻辑：先校验门店经理及数据范围，再查询指定自然日范围中的流水
    异常或失败情况：员工、跨店访问和无效时间或变更类型时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    _ensure_store_inventory_manager(user, store_id)
    allowed_types = {INVENTORY_CHANGE_RESERVE, INVENTORY_CHANGE_CONFIRM_DEDUCT, INVENTORY_CHANGE_RELEASE, INVENTORY_CHANGE_MANUAL_ADJUST, INVENTORY_CHANGE_REFUND_RESTORE}
    if days not in {1, 7, 30} or (change_type and change_type not in allowed_types):
        raise BusinessError("库存记录筛选参数不合法", "invalid_inventory_filter")
    start = current_time().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    query = InventoryLog.query.filter(InventoryLog.store_id == store_id, InventoryLog.created_at >= start, InventoryLog.created_at < start + timedelta(days=days))
    if store_product_id is not None:
        query = query.filter(InventoryLog.store_product_id == store_product_id)
    if change_type:
        query = query.filter(InventoryLog.change_type == change_type)
    return [{"id": entry.id, "store_id": entry.store_id, "store_product_id": entry.store_product_id,
        "order_id": entry.order_id, "change_type": entry.change_type, "change_quantity": entry.change_quantity,
        "before_current_stock": entry.before_current_stock, "after_current_stock": entry.after_current_stock,
        "before_reserved_stock": entry.before_reserved_stock, "after_reserved_stock": entry.after_reserved_stock,
        "operator_id": entry.operator_id, "remark": entry.remark, "created_at": format_datetime(entry.created_at)}
        for entry in query.order_by(InventoryLog.created_at.desc(), InventoryLog.id.desc()).all()]
