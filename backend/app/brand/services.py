"""
文件名称：services.py
文件用途：实现品牌后台门店、菜单、门店商品、优惠券和报表服务
主要职责：提供品牌范围的基础运营数据维护、汇总报表和优惠券活动 MVP 管理
所属业务模块：品牌管理
创建时间：2026-05-26 16:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func

from app.audit.models import OperationLog
from app.catalog.models import Product, ProductCategory, StoreProduct
from app.catalog.services import LIVE_MENU_STATUSES
from app.common.enums import (
    MENU_STATUS_PUBLISHED,
    MENU_STATUS_DRAFT,
    MENU_STATUS_DRAFT_CHANGES,
    MENU_STATUS_ARCHIVED,
    OPERATION_RESULT_SUCCESS,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_CANCELED,
    ORDER_STATUS_REFUNDED,
    ORDER_STATUS_REFUND_PENDING,
    ORDER_STATUS_PAID,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_READY,
    PAYMENT_STATUS_SUCCEEDED,
    ROLE_BRAND_ADMIN,
    ROLE_SYSTEM_ADMIN,
    STORE_STATUS_CLOSED,
    STORE_STATUS_OPEN,
    STORE_STATUS_TEMPORARILY_CLOSED,
)
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.common.formatters import format_datetime, format_money, format_time
from app.common.time_utils import current_time
from app.coupons.models import CouponActivity, CouponActivityProduct, CouponActivityStore, CouponClaimTask, UserCoupon
from app.extensions import db
from app.inventory.services import serialize_store_inventory_item
from app.inventory.models import InventoryLog
from app.orders.models import Order, OrderItem
from app.payments.models import PaymentRecord
from app.stores.models import Store
from app.stores.services import serialize_store

STORE_STATUS_VALUES = {STORE_STATUS_OPEN, STORE_STATUS_CLOSED, STORE_STATUS_TEMPORARILY_CLOSED}
MENU_STATUS_VALUES = {MENU_STATUS_DRAFT, MENU_STATUS_PUBLISHED, MENU_STATUS_DRAFT_CHANGES, MENU_STATUS_ARCHIVED}
PRODUCT_CONTENT_FIELDS = ("category_id", "name_zh", "name_en", "description_zh", "description_en", "image_url", "base_price", "sort_order")
COUPON_STATUS_VALUES = {"draft", "scheduled", "active", "paused", "ended", "sold_out"}
EFFECTIVE_ORDER_STATUSES = (
    ORDER_STATUS_PAID,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_READY,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_REFUND_PENDING,
)


def get_brand_overview(user) -> dict:
    """
    函数名称：get_brand_overview
    函数用途：返回品牌后台首页关键指标
    参数说明：user 为当前品牌或系统管理员
    返回值说明：返回门店、商品、活动、今日订单和销售额等指标
    核心逻辑：校验品牌后台角色后聚合门店、商品、订单、库存和优惠券数据
    异常或失败情况：非品牌或系统管理员访问时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    today_start, today_end = _today_range()
    today_orders = _orders_in_range(today_start, today_end)
    store_rows = [serialize_store(store) for store in Store.query.order_by(Store.id).all()]
    task_counts = dict(db.session.query(CouponClaimTask.task_status, func.count(CouponClaimTask.id)).group_by(CouponClaimTask.task_status).all())
    return {
        "stores": store_rows,
        "open_store_count": sum(store["can_order"] for store in store_rows),
        "temporarily_closed_store_count": sum(store["is_active"] and store["store_status"] == STORE_STATUS_TEMPORARILY_CLOSED for store in store_rows),
        "closed_store_count": sum(store["is_active"] and not store["can_order"] and store["store_status"] != STORE_STATUS_TEMPORARILY_CLOSED for store in store_rows),
        "coupon_sync_pending_count": task_counts.get("pending", 0) + task_counts.get("processing", 0),
        "coupon_sync_failed_count": task_counts.get("failed", 0),
        "coupon_sync_dead_count": task_counts.get("dead", 0),
        "store_count": Store.query.count(),
        "active_store_count": Store.query.filter_by(is_active=True).count(),
        "published_product_count": Product.query.filter(Product.menu_status.in_(LIVE_MENU_STATUSES)).count(),
        "active_coupon_count": CouponActivity.query.filter(CouponActivity.activity_status.in_(("scheduled", "active"))).count(),
        "today_order_count": today_orders.count(),
        "today_revenue": _summarize_orders(today_start, today_end)["revenue"],
        "low_stock_count": _low_stock_query().count(),
        "pending_order_count": Order.query.filter(Order.order_status.in_((ORDER_STATUS_PAID, ORDER_STATUS_ACCEPTED, ORDER_STATUS_PREPARING, ORDER_STATUS_READY))).count(),
    }


def get_brand_report(user) -> dict:
    """
    函数名称：get_brand_report
    函数用途：返回品牌基础经营报表
    参数说明：user 为当前品牌或系统管理员
    返回值说明：返回今日、近 7 日、近 30 日、取消数、门店排行、热销商品和去重订单支付成功率
    核心逻辑：订单数统计全部状态；销售额排除未支付、取消和已退款订单；热门商品按 ID 聚合；支付重试按订单去重
    异常或失败情况：非品牌或系统管理员访问时拒绝
    相关业务规则：取消指标包含 canceled/refunded；退款处理中仍计收入，退款成功后扣除；订单指标按创建时间，券核销率按领取批次
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    today_start, today_end = _today_range()
    seven_day_start = today_start - timedelta(days=6)
    return {
        "today": _summarize_orders(today_start, today_end),
        "last_7_days": _summarize_orders(seven_day_start, today_end),
        "last_30_days": _summarize_orders(today_start - timedelta(days=29), today_end),
        "metric_definitions": {
            "order_count": "all_orders_by_created_at",
            "canceled_order_count": "orders_created_in_period_currently_canceled_or_refunded",
            "revenue": "paid_unless_refunded_by_paid_at_including_refund_pending",
            "payment_success_rate": "distinct_successful_payment_orders_over_distinct_attempted_orders_by_payment_created_at",
            "popular_products": "product_id_quantity_by_paid_at_from_order_snapshots_latest_name",
            "coupon_used_count": "user_coupons_by_used_at",
            "coupon_summary": "claim_cohort_by_claimed_at_used_count_from_same_cohort",
            "timezone": "Asia/Singapore",
        },
        "store_rankings": _store_rankings(seven_day_start, today_end),
        "popular_products": _popular_products(seven_day_start, today_end),
        "coupon_summary": _coupon_summary(seven_day_start, today_end),
        "payment_success_rate": _payment_success_rate(seven_day_start, today_end),
    }


def list_brand_stores(user) -> list[dict]:
    _ensure_brand_admin(user)
    return [serialize_store(store) for store in Store.query.order_by(Store.id.asc()).all()]


def create_brand_store(user, payload: dict) -> dict:
    """
    函数名称：create_brand_store
    函数用途：品牌后台创建门店
    参数说明：user 为操作人，payload 包含门店编码、中英文名称、地址、电话、营业时间和状态
    返回值说明：返回创建后的门店摘要
    核心逻辑：校验品牌角色、唯一编码和必填字段后写入门店并记录操作日志
    异常或失败情况：参数缺失、编码重复或状态非法时失败
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    store_code = str(payload.get("store_code") or "").strip()
    name_zh = str(payload.get("name_zh") or "").strip()
    address = str(payload.get("address") or "").strip()
    if not store_code or not name_zh or not address:
        raise BusinessError("门店编码、中文名称和地址不能为空", "invalid_store_payload")
    if Store.query.filter_by(store_code=store_code).first() is not None:
        raise BusinessError("门店编码已存在", "store_code_exists")
    store = Store(
        store_code=store_code,
        name_zh=name_zh,
        name_en=str(payload.get("name_en") or "").strip() or None,
        address=address,
        phone=str(payload.get("phone") or "").strip() or None,
        business_start_time=_parse_time(payload.get("business_start_time")) or time(9, 0),
        business_end_time=_parse_time(payload.get("business_end_time")) or time(22, 0),
        store_status=_validate_store_status(payload.get("store_status") or STORE_STATUS_OPEN),
        temporary_close_reason=str(payload.get("temporary_close_reason") or "").strip() or None,
        is_active=_strict_bool(payload.get("is_active", True)),
    )
    db.session.add(store)
    db.session.flush()
    db.session.add(_build_log(user, "store", "create_store", store.id, store.id, None, serialize_store(store)))
    db.session.commit()
    return serialize_store(store)


def update_brand_store(user, store_id: int, payload: dict) -> dict:
    """
    函数名称：update_brand_store
    函数用途：品牌后台编辑门店基础资料
    参数说明：user 为操作人，store_id 为门店 ID，payload 为门店可更新字段
    返回值说明：返回更新后的门店摘要
    核心逻辑：校验品牌角色和状态值后更新门店字段并记录操作日志
    异常或失败情况：门店不存在、编码重复或状态非法时失败
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    store = db.session.get(Store, store_id)
    if store is None:
        raise NotFoundError("门店不存在")
    before_snapshot = serialize_store(store)
    if "store_code" in payload:
        store_code = str(payload.get("store_code") or "").strip()
        if not store_code:
            raise BusinessError("门店编码不能为空", "invalid_store_code")
        if Store.query.filter(Store.store_code == store_code, Store.id != store.id).first() is not None:
            raise BusinessError("门店编码已存在", "store_code_exists")
        store.store_code = store_code
    for field in ("name_zh", "name_en", "address", "phone", "temporary_close_reason"):
        if field in payload:
            value = str(payload.get(field) or "").strip()
            if field in ("name_zh", "address") and not value:
                raise BusinessError("门店中文名称和地址不能为空", "invalid_store_payload")
            setattr(store, field, value or None)
    if "business_start_time" in payload:
        store.business_start_time = _parse_time(payload.get("business_start_time")) or store.business_start_time
    if "business_end_time" in payload:
        store.business_end_time = _parse_time(payload.get("business_end_time")) or store.business_end_time
    if "store_status" in payload:
        store.store_status = _validate_store_status(payload.get("store_status"))
    if "is_active" in payload:
        store.is_active = _strict_bool(payload.get("is_active"))
    after_snapshot = serialize_store(store)
    db.session.add(_build_log(user, "store", "update_store", store.id, store.id, before_snapshot, after_snapshot))
    db.session.commit()
    return serialize_store(store)


def list_categories(user) -> list[dict]:
    _ensure_brand_admin(user)
    return [serialize_category(category) for category in ProductCategory.query.order_by(ProductCategory.sort_order.asc(), ProductCategory.id.asc()).all()]


def create_category(user, payload: dict) -> dict:
    """
    函数名称：create_category
    函数用途：品牌后台创建商品分类
    参数说明：user 为操作人，payload 包含中英文名称、排序和启用状态
    返回值说明：返回创建后的分类
    核心逻辑：校验中文名称后写入分类并记录操作日志
    异常或失败情况：中文名称为空时失败
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    name_zh = str(payload.get("name_zh") or "").strip()
    if not name_zh:
        raise BusinessError("分类中文名称不能为空", "invalid_category_payload")
    category = ProductCategory(
        name_zh=name_zh,
        name_en=str(payload.get("name_en") or "").strip() or None,
        sort_order=_strict_integer(payload.get("sort_order", 0), "排序必须为整数", "invalid_sort_order"),
        is_active=_strict_bool(payload.get("is_active", True)),
    )
    db.session.add(category)
    db.session.flush()
    db.session.add(_build_log(user, "catalog", "create_category", category.id, None, None, serialize_category(category)))
    db.session.commit()
    return serialize_category(category)


def update_category(user, category_id: int, payload: dict) -> dict:
    _ensure_brand_admin(user)
    category = db.session.get(ProductCategory, category_id)
    if category is None:
        raise NotFoundError("商品分类不存在")
    before_snapshot = serialize_category(category)
    if "name_zh" in payload:
        name_zh = str(payload.get("name_zh") or "").strip()
        if not name_zh:
            raise BusinessError("分类中文名称不能为空", "invalid_category_payload")
        category.name_zh = name_zh
    if "name_en" in payload:
        category.name_en = str(payload.get("name_en") or "").strip() or None
    if "sort_order" in payload:
        category.sort_order = _strict_integer(payload.get("sort_order"), "排序必须为整数", "invalid_sort_order")
    if "is_active" in payload:
        category.is_active = _strict_bool(payload.get("is_active"))
    after_snapshot = serialize_category(category)
    db.session.add(_build_log(user, "catalog", "update_category", category.id, None, before_snapshot, after_snapshot))
    db.session.commit()
    return serialize_category(category)


def list_products(user) -> list[dict]:
    _ensure_brand_admin(user)
    products = Product.query.order_by(Product.category_id.asc(), Product.sort_order.asc(), Product.id.asc()).all()
    return [serialize_product(product) for product in products]


def create_product(user, payload: dict) -> dict:
    """
    函数名称：create_product
    函数用途：品牌后台创建品牌商品
    参数说明：user 为操作人，payload 包含分类、名称、描述、图片、价格、发布状态和排序
    返回值说明：返回创建后的商品
    核心逻辑：校验分类、中文名称、价格和菜单状态后写入商品并记录操作日志
    异常或失败情况：分类不存在、价格非法或状态非法时失败
    相关业务规则：品牌商品不直接代表门店库存，需要通过门店商品配置上架到门店
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    category = db.session.get(ProductCategory, _positive_int(payload.get("category_id"), "商品分类 ID 不合法", "invalid_product_payload"))
    if category is None:
        raise BusinessError("商品分类不存在", "category_not_found")
    name_zh = str(payload.get("name_zh") or "").strip()
    if not name_zh:
        raise BusinessError("商品中文名称不能为空", "invalid_product_payload")
    product = Product(
        category_id=category.id,
        name_zh=name_zh,
        name_en=str(payload.get("name_en") or "").strip() or None,
        description_zh=str(payload.get("description_zh") or "").strip() or None,
        description_en=str(payload.get("description_en") or "").strip() or None,
        image_url=str(payload.get("image_url") or "").strip() or None,
        base_price=_parse_money(payload.get("base_price")),
        menu_status=_validate_menu_status(payload.get("menu_status") or "draft"),
        sort_order=_strict_integer(payload.get("sort_order", 0), "排序必须为整数", "invalid_sort_order"),
    )
    if product.menu_status == MENU_STATUS_DRAFT_CHANGES:
        raise BusinessError("新商品不能进入待发布修改状态", "invalid_menu_transition")
    for field in ("name_zh", "name_en", "description_zh", "description_en", "image_url"):
        setattr(product, field, _validated_product_text(field, getattr(product, field)))
    db.session.add(product)
    db.session.flush()
    db.session.add(_build_log(user, "catalog", "create_product", product.id, None, None, serialize_product(product)))
    db.session.commit()
    return serialize_product(product)


def update_product(user, product_id: int, payload: dict) -> dict:
    """
    函数名称：update_product
    函数用途：维护草稿、保存已发布商品的待发布修改、发布或永久归档商品
    参数说明：payload 为商品内容；单独提交 menu_status=published 表示发布
    返回值说明：编辑内容与独立已发布内容
    核心逻辑：锁商品行，校验状态与完整字段；发布前保持原线上字段；发布时原子替换
    异常或失败情况：归档商品不可恢复，未发布商品不能进入待发布修改状态
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    _ensure_brand_admin(user)
    product = Product.query.filter_by(id=product_id).with_for_update().first()
    if product is None:
        raise NotFoundError("商品不存在")
    if product.menu_status == MENU_STATUS_ARCHIVED:
        raise BusinessError("归档商品不可编辑或恢复", "product_archived")
    before_snapshot = serialize_product(product)
    requested_status = _validate_menu_status(payload.get("menu_status", product.menu_status))
    live_content = _product_content(product)
    editing_content = {**live_content, **(product.pending_changes or {})}
    updated_content = dict(editing_content)
    for field in PRODUCT_CONTENT_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if field == "category_id":
            value = _positive_int(value, "商品分类不存在", "category_not_found")
            if db.session.get(ProductCategory, value) is None:
                raise BusinessError("商品分类不存在", "category_not_found")
        elif field == "base_price":
            value = format_money(_parse_money(value))
        elif field == "sort_order":
            value = _strict_integer(value, "排序必须为整数", "invalid_product_payload")
        else:
            value = _validated_product_text(field, value)
        updated_content[field] = value
    if requested_status == MENU_STATUS_ARCHIVED:
        product.menu_status = MENU_STATUS_ARCHIVED
        product.pending_changes = None
    elif product.menu_status in LIVE_MENU_STATUSES:
        if requested_status == MENU_STATUS_DRAFT:
            raise BusinessError("已发布商品不能退回未发布草稿", "invalid_menu_transition")
        content_changed = updated_content != editing_content
        if requested_status == MENU_STATUS_PUBLISHED and not content_changed:
            _apply_product_content(product, updated_content)
            product.pending_changes = None
            product.menu_status = MENU_STATUS_PUBLISHED
        else:
            product.pending_changes = updated_content if updated_content != live_content else None
            product.menu_status = MENU_STATUS_DRAFT_CHANGES if product.pending_changes else MENU_STATUS_PUBLISHED
    else:
        if requested_status == MENU_STATUS_DRAFT_CHANGES:
            raise BusinessError("未发布商品不能进入待发布修改状态", "invalid_menu_transition")
        _apply_product_content(product, updated_content)
        product.menu_status = requested_status
    after_snapshot = serialize_product(product)
    db.session.add(_build_log(user, "catalog", "update_product", product.id, None, before_snapshot, after_snapshot))
    db.session.commit()
    return serialize_product(product)


def _product_content(product: Product) -> dict:
    return {field: format_money(product.base_price) if field == "base_price" else getattr(product, field) for field in PRODUCT_CONTENT_FIELDS}


def _apply_product_content(product: Product, content: dict) -> None:
    for field in PRODUCT_CONTENT_FIELDS:
        setattr(product, field, _parse_money(content[field]) if field == "base_price" else content[field])


def _validated_product_text(field: str, value):
    value = str(value or "").strip() or None
    if field == "name_zh" and not value:
        raise BusinessError("商品中文名称不能为空", "invalid_product_payload")
    max_length = 128 if field in ("name_zh", "name_en") else 512 if field == "image_url" else 20000
    if value and len(value) > max_length:
        raise BusinessError("商品字段超过长度限制", "invalid_product_payload")
    if field == "image_url" and value:
        from urllib.parse import urlparse
        parsed = urlparse(value)
        local_path = value.startswith("/") and not value.startswith("//") and "\\" not in value
        if not local_path and (parsed.scheme not in ("http", "https") or not parsed.netloc):
            raise BusinessError("商品图片地址必须为站内路径或 HTTP/HTTPS 链接", "invalid_product_payload")
    return value


def list_brand_store_products(user, store_id: int | None = None) -> list[dict]:
    _ensure_brand_admin(user)
    query = StoreProduct.query.order_by(StoreProduct.store_id.asc(), StoreProduct.id.asc())
    if store_id:
        query = query.filter(StoreProduct.store_id == store_id)
    return [serialize_brand_store_product(item) for item in query.all()]


def upsert_store_product(user, payload: dict) -> dict:
    """
    函数名称：upsert_store_product
    函数用途：品牌后台将品牌商品配置到门店
    参数说明：user 为操作人，payload 包含 store_id、product_id、库存和可售状态
    返回值说明：返回门店商品配置快照
    核心逻辑：存在则更新，不存在则创建，并校验库存不低于预占库存
    异常或失败情况：门店或商品不存在、库存非法时失败
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    store_id = _positive_int(payload.get("store_id"), "门店 ID 不合法", "invalid_store_id")
    product_id = _positive_int(payload.get("product_id"), "商品 ID 不合法", "invalid_product_id")
    if db.session.get(Store, store_id) is None or db.session.get(Product, product_id) is None:
        raise BusinessError("门店或商品不存在", "store_or_product_not_found")
    store_product = StoreProduct.query.filter_by(store_id=store_id, product_id=product_id).with_for_update().first()
    operation_type = "update_store_product" if store_product else "create_store_product"
    before_snapshot = serialize_brand_store_product(store_product) if store_product else None
    if store_product is None:
        store_product = StoreProduct(store_id=store_id, product_id=product_id, current_stock=0, reserved_stock=0)
        db.session.add(store_product)
        db.session.flush()
    _apply_store_product_payload(store_product, payload)
    _record_brand_stock_adjustment(user, store_product, before_snapshot, payload)
    store_product.last_operator_id = user.id
    after_snapshot = serialize_brand_store_product(store_product)
    db.session.add(_build_log(user, "inventory", operation_type, store_product.id, store_id, before_snapshot, after_snapshot))
    db.session.commit()
    return serialize_brand_store_product(store_product)


def update_brand_store_product(user, store_product_id: int, payload: dict) -> dict:
    _ensure_brand_admin(user)
    store_product = StoreProduct.query.filter_by(id=store_product_id).with_for_update().first()
    if store_product is None:
        raise NotFoundError("门店商品不存在")
    before_snapshot = serialize_brand_store_product(store_product)
    _apply_store_product_payload(store_product, payload)
    _record_brand_stock_adjustment(user, store_product, before_snapshot, payload)
    store_product.last_operator_id = user.id
    after_snapshot = serialize_brand_store_product(store_product)
    db.session.add(_build_log(user, "inventory", "update_store_product", store_product.id, store_product.store_id, before_snapshot, after_snapshot))
    db.session.commit()
    return serialize_brand_store_product(store_product)


def list_coupon_activities(user) -> list[dict]:
    _ensure_brand_admin(user)
    activities = CouponActivity.query.order_by(CouponActivity.created_at.desc(), CouponActivity.id.desc()).all()
    return [serialize_coupon_activity(activity, include_metrics=True) for activity in activities]


def create_coupon_activity(user, payload: dict) -> dict:
    """
    函数名称：create_coupon_activity
    函数用途：品牌后台创建优惠券活动
    参数说明：user 为操作人，payload 包含活动名称、时间、库存、优惠金额、门槛和适用范围
    返回值说明：返回创建后的优惠券活动摘要
    核心逻辑：校验活动基础字段、时间范围和状态后写入活动及适用门店/商品
    异常或失败情况：名称为空、时间非法、库存非法或状态非法时失败
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _ensure_brand_admin(user)
    activity = CouponActivity(
        activity_name_zh=_required_text(payload.get("activity_name_zh"), "活动中文名称不能为空", "invalid_coupon_payload"),
        activity_name_en=str(payload.get("activity_name_en") or "").strip() or None,
        description_zh=str(payload.get("description_zh") or "").strip() or None,
        description_en=str(payload.get("description_en") or "").strip() or None,
        start_at=_parse_datetime_required(payload.get("start_at"), "活动开始时间不能为空"),
        end_at=_parse_datetime_required(payload.get("end_at"), "活动结束时间不能为空"),
        total_stock=_positive_int(payload.get("total_stock"), "活动总库存必须大于 0", "invalid_coupon_stock"),
        per_user_limit=_validate_per_user_limit(payload.get("per_user_limit", 1)),
        discount_amount=_parse_money(payload.get("discount_amount")),
        minimum_order_amount=_parse_money(payload.get("minimum_order_amount") or 0),
        activity_status=_validate_coupon_status(payload.get("activity_status") or "draft"),
        created_by=user.id,
    )
    _validate_coupon_time_range(activity.start_at, activity.end_at)
    db.session.add(activity)
    db.session.flush()
    _replace_coupon_scopes(activity.id, payload)
    db.session.add(_build_log(user, "coupon", "create_coupon", activity.id, None, None, serialize_coupon_activity(activity)))
    db.session.commit()
    return serialize_coupon_activity(activity, include_metrics=True)


def update_coupon_activity(user, activity_id: int, payload: dict) -> dict:
    """
    函数名称：update_coupon_activity
    函数用途：更新未开始活动内容或暂停、结束已运行活动
    参数说明：user 为品牌管理员，activity_id 为活动 ID，payload 为更新字段
    返回值说明：更新后活动内容和过程指标
    核心逻辑：锁活动行，保护已领取权益和预热库存，再校验字段、调整范围和记录审计
    异常或失败情况：核心权益被冻结、活动已结束、时间金额或范围不合法时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    _ensure_brand_admin(user)
    activity = CouponActivity.query.filter_by(id=activity_id).with_for_update().first()
    if activity is None:
        raise NotFoundError("优惠券活动不存在")
    before_snapshot = serialize_coupon_activity(activity, include_metrics=True)
    _protect_coupon_terms(activity, payload)
    for field in ("activity_name_zh", "activity_name_en", "description_zh", "description_en"):
        if field in payload:
            value = str(payload.get(field) or "").strip()
            if field == "activity_name_zh" and not value:
                raise BusinessError("活动中文名称不能为空", "invalid_coupon_payload")
            setattr(activity, field, value or None)
    if "start_at" in payload:
        activity.start_at = _parse_datetime_required(payload.get("start_at"), "活动开始时间不能为空")
    if "end_at" in payload:
        activity.end_at = _parse_datetime_required(payload.get("end_at"), "活动结束时间不能为空")
    if "total_stock" in payload:
        activity.total_stock = _positive_int(payload.get("total_stock"), "活动总库存必须大于 0", "invalid_coupon_stock")
    if "per_user_limit" in payload:
        activity.per_user_limit = _validate_per_user_limit(payload.get("per_user_limit"))
    if "discount_amount" in payload:
        activity.discount_amount = _parse_money(payload.get("discount_amount"))
    if "minimum_order_amount" in payload:
        activity.minimum_order_amount = _parse_money(payload.get("minimum_order_amount") or 0)
    if "activity_status" in payload:
        activity.activity_status = _validate_coupon_status(payload.get("activity_status"))
    _validate_coupon_time_range(activity.start_at, activity.end_at)
    if "store_ids" in payload or "product_ids" in payload:
        _replace_coupon_scopes(activity.id, payload)
    after_snapshot = serialize_coupon_activity(activity, include_metrics=True)
    db.session.add(_build_log(user, "coupon", "update_coupon", activity.id, None, before_snapshot, after_snapshot))
    db.session.commit()
    return serialize_coupon_activity(activity, include_metrics=True)


def get_coupon_activity_metrics(user, activity_id: int) -> dict:
    _ensure_brand_admin(user)
    activity = db.session.get(CouponActivity, activity_id)
    if activity is None:
        raise NotFoundError("优惠券活动不存在")
    return build_coupon_metrics(activity)


def serialize_category(category: ProductCategory) -> dict:
    return {
        "id": category.id,
        "name_zh": category.name_zh,
        "name_en": category.name_en,
        "sort_order": category.sort_order,
        "is_active": bool(category.is_active),
        "created_at": format_datetime(category.created_at),
        "updated_at": format_datetime(category.updated_at),
    }


def serialize_product(product: Product) -> dict:
    published_content = _product_content(product)
    editing_content = {**published_content, **(product.pending_changes or {})}
    category = db.session.get(ProductCategory, editing_content["category_id"])
    return {
        "id": product.id,
        **editing_content,
        "category_name_zh": category.name_zh if category else None,
        "category_name_en": category.name_en if category else None,
        "menu_status": product.menu_status,
        "pending_changes": product.pending_changes,
        "published_content": published_content if product.menu_status in LIVE_MENU_STATUSES else None,
        "missing_translations": [field for field in ("name_en", "description_en") if not editing_content.get(field)],
        "created_at": format_datetime(product.created_at),
        "updated_at": format_datetime(product.updated_at),
    }


def serialize_brand_store_product(store_product: StoreProduct) -> dict:
    data = serialize_store_inventory_item(store_product)
    data["store_name"] = store_product.store.name_zh if store_product.store else None
    data["store_name_zh"] = store_product.store.name_zh if store_product.store else None
    data["store_name_en"] = store_product.store.name_en if store_product.store else None
    data["store_code"] = store_product.store.store_code if store_product.store else None
    return data


def serialize_coupon_activity(activity: CouponActivity, include_metrics: bool = False) -> dict:
    data = {
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
        "created_by": activity.created_by,
        "store_ids": [link.store_id for link in activity.store_links],
        "product_ids": [link.product_id for link in activity.product_links],
        "created_at": format_datetime(activity.created_at),
        "updated_at": format_datetime(activity.updated_at),
    }
    if include_metrics:
        data["metrics"] = build_coupon_metrics(activity)
    return data


def build_coupon_metrics(activity: CouponActivity) -> dict:
    from app.coupons.services import build_activity_metrics

    activity_metrics = build_activity_metrics(activity.id)
    claimed_count = activity_metrics["database_count"]
    used_count = activity_metrics["used_count"]
    task_rows = (
        CouponClaimTask.query.filter_by(activity_id=activity.id)
        .with_entities(CouponClaimTask.task_status, func.count(CouponClaimTask.id))
        .group_by(CouponClaimTask.task_status)
        .all()
    )
    task_counts = {row[0]: int(row[1]) for row in task_rows}
    remaining_stock = activity_metrics["redis_remaining_stock"]
    if remaining_stock is None:
        remaining_stock = max(activity.total_stock - claimed_count, 0)
    usage_rate = f"{(used_count / claimed_count * 100):.1f}%" if claimed_count else "0.0%"
    return {
        "claimed_count": claimed_count,
        "used_count": used_count,
        "remaining_stock": remaining_stock,
        "usage_rate": usage_rate,
        "redis_success_count": activity_metrics["redis_success_count"],
        "database_count": activity_metrics["database_count"],
        "difference_count": activity_metrics["difference_count"],
        "failed_count": activity_metrics["failed_count"],
        "dead_count": activity_metrics["dead_count"],
        "task_counts": {
            "pending": task_counts.get("pending", 0),
            "processing": task_counts.get("processing", 0),
            "succeeded": task_counts.get("succeeded", 0),
            "failed": task_counts.get("failed", 0),
            "dead": task_counts.get("dead", 0),
        },
    }


def _ensure_brand_admin(user) -> None:
    if not user.has_any_role((ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能访问品牌后台")


def _build_log(user, module: str, operation_type: str, target_id: int, store_id: int | None, before_snapshot, after_snapshot) -> OperationLog:
    return OperationLog(
        operator_id=user.id,
        operator_role_code=user.first_role_code(),
        operation_module=module,
        operation_type=operation_type,
        target_id=target_id,
        store_id=store_id,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        operation_result=OPERATION_RESULT_SUCCESS,
    )


def _today_range():
    now = current_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, today_start + timedelta(days=1)


def _orders_in_range(start_time, end_time):
    return Order.query.filter(Order.created_at >= start_time, Order.created_at < end_time)


def _effective_orders_in_range(start_time, end_time):
    return Order.query.filter(Order.paid_at >= start_time, Order.paid_at < end_time, Order.order_status.in_(EFFECTIVE_ORDER_STATUSES))


def _summarize_orders(start_time, end_time) -> dict:
    """
    函数名称：_summarize_orders
    函数用途：汇总品牌指定周期的订单、取消/退款、收入和用券指标
    参数说明：start_time、end_time 为本地时间左闭右开的统计区间
    返回值说明：品牌报表今日、7日及30日共用的指标字典
    核心逻辑：订单数按创建时间，取消计 canceled/refunded 两种终态；收入按支付时间，核销按使用时间
    异常或失败情况：数据库查询失败时由统一错误处理返回错误
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    query = _orders_in_range(start_time, end_time)
    effective = _effective_orders_in_range(start_time, end_time)
    revenue = effective.with_entities(func.coalesce(func.sum(Order.payable_amount), 0)).scalar()
    return {
        "order_count": query.count(),
        "completed_order_count": query.filter(Order.order_status == ORDER_STATUS_COMPLETED).count(),
        "canceled_order_count": query.filter(Order.order_status.in_((ORDER_STATUS_CANCELED, ORDER_STATUS_REFUNDED))).count(),
        "coupon_used_count": UserCoupon.query.filter(UserCoupon.used_at >= start_time, UserCoupon.used_at < end_time).count(),
        "revenue": format_money(revenue),
    }


def _store_rankings(start_time, end_time) -> list[dict]:
    order_counts = dict(_orders_in_range(start_time, end_time).with_entities(Order.store_id, func.count(Order.id)).group_by(Order.store_id).all())
    revenues = dict(_effective_orders_in_range(start_time, end_time).with_entities(Order.store_id, func.sum(Order.payable_amount)).group_by(Order.store_id).all())
    rows = [{
        "store_id": store.id, "store_name_zh": store.name_zh, "store_name_en": store.name_en,
        "order_count": order_counts.get(store.id, 0), "revenue": format_money(revenues.get(store.id, 0)),
    } for store in Store.query.all()]
    return sorted(rows, key=lambda row: (-Decimal(row["revenue"]), -row["order_count"], row["store_id"]))[:10]


def _popular_products(start_time, end_time) -> list[dict]:
    rows = (
        OrderItem.query.join(Order, OrderItem.order_id == Order.id)
        .filter(Order.paid_at >= start_time, Order.paid_at < end_time)
        .filter(Order.order_status.in_(EFFECTIVE_ORDER_STATUSES))
        .with_entities(OrderItem.product_id, func.max(OrderItem.id).label("latest_item_id"),
                       func.sum(OrderItem.quantity).label("sold_quantity"),
                       func.coalesce(func.sum(OrderItem.subtotal_amount), 0).label("sales_amount"))
        .group_by(OrderItem.product_id)
        .order_by(func.sum(OrderItem.quantity).desc(), OrderItem.product_id.asc())
        .limit(10).all()
    )
    result = []
    for row in rows:
        snapshot = db.session.get(OrderItem, row.latest_item_id)
        result.append({
            "product_id": row.product_id,
            "product_name_zh": snapshot.product_name_zh,
            "product_name_en": snapshot.product_name_en,
            "sold_quantity": int(row.sold_quantity or 0),
            "sales_amount": format_money(row.sales_amount),
        })
    return result


def _coupon_summary(start_time, end_time) -> dict:
    claimed_count = UserCoupon.query.filter(UserCoupon.claimed_at >= start_time, UserCoupon.claimed_at < end_time).count()
    used_count = UserCoupon.query.filter(UserCoupon.claimed_at >= start_time, UserCoupon.claimed_at < end_time, UserCoupon.coupon_status == "used").count()
    usage_rate = f"{(used_count / claimed_count * 100):.1f}%" if claimed_count else "0.0%"
    return {"claimed_count": claimed_count, "used_count": used_count, "usage_rate": usage_rate}


def _payment_success_rate(start_time, end_time) -> str:
    attempted_orders = PaymentRecord.query.filter(
        PaymentRecord.created_at >= start_time, PaymentRecord.created_at < end_time,
    ).with_entities(PaymentRecord.order_id).distinct()
    total_count = attempted_orders.count()
    if total_count == 0:
        return "0.0%"
    success_count = PaymentRecord.query.filter(
        PaymentRecord.order_id.in_(attempted_orders),
        PaymentRecord.payment_status == PAYMENT_STATUS_SUCCEEDED,
    ).with_entities(PaymentRecord.order_id).distinct().count()
    return f"{(success_count / total_count * 100):.1f}%"


def _low_stock_query():
    return (
        StoreProduct.query.join(StoreProduct.product).join(StoreProduct.store)
        .filter(StoreProduct.is_available.is_(True), Store.is_active.is_(True))
        .filter(Product.menu_status.in_(LIVE_MENU_STATUSES))
        .filter(Product.category.has(ProductCategory.is_active.is_(True)))
        .filter(StoreProduct.is_sold_out.is_(False))
        .filter((StoreProduct.current_stock - StoreProduct.reserved_stock) <= 5)
    )


def _apply_store_product_payload(store_product: StoreProduct, payload: dict) -> None:
    if "current_stock" in payload:
        next_stock = _strict_integer(payload.get("current_stock"), "库存必须为非负整数", "invalid_stock")
        if next_stock < 0:
            raise BusinessError("库存必须为非负整数", "invalid_stock")
        if next_stock < store_product.reserved_stock:
            raise BusinessError("当前库存不能小于已预占库存", "current_stock_less_than_reserved")
        store_product.current_stock = next_stock
    if "is_available" in payload:
        store_product.is_available = _strict_bool(payload["is_available"])
    if "is_sold_out" in payload:
        store_product.is_sold_out = _strict_bool(payload["is_sold_out"])
    if store_product.is_available and store_product.product.menu_status not in LIVE_MENU_STATUSES:
        raise BusinessError("只有已发布商品可以配置为可售", "product_not_published")


def _record_brand_stock_adjustment(user, store_product, before_snapshot, payload) -> None:
    before_stock = before_snapshot["current_stock"] if before_snapshot else 0
    if before_stock == store_product.current_stock:
        return
    reason = str(payload.get("reason") or "品牌后台库存配置").strip()
    if len(reason) > 500:
        raise BusinessError("库存调整原因不能超过 500 字", "invalid_stock_reason")
    db.session.add(InventoryLog(
        store_id=store_product.store_id, store_product_id=store_product.id,
        change_type="manual_adjust", change_quantity=store_product.current_stock - before_stock,
        before_current_stock=before_stock, after_current_stock=store_product.current_stock,
        before_reserved_stock=store_product.reserved_stock, after_reserved_stock=store_product.reserved_stock,
        operator_id=user.id, remark=reason,
    ))


def _replace_coupon_scopes(activity_id: int, payload: dict) -> None:
    activity = db.session.get(CouponActivity, activity_id)
    for field, relationship_name, link_class, target_class, target_key in (
        ("store_ids", "store_links", CouponActivityStore, Store, "store_id"),
        ("product_ids", "product_links", CouponActivityProduct, Product, "product_id"),
    ):
        if field not in payload:
            continue
        desired = set(_normalize_id_list(payload[field]))
        links = getattr(activity, relationship_name)
        existing = {getattr(link, target_key): link for link in links}
        for target_id in desired:
            if db.session.get(target_class, target_id) is None:
                raise BusinessError("优惠券适用范围对象不存在", "invalid_scope_ids")
        for target_id in set(existing) - desired:
            links.remove(existing[target_id])
        for target_id in desired - set(existing):
            links.append(link_class(**{target_key: target_id}))


def _normalize_id_list(value) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise BusinessError("适用范围必须是 ID 数组", "invalid_scope_ids")
    return sorted({_positive_int(item, "适用范围 ID 必须为正整数", "invalid_scope_ids") for item in value})


def _validate_store_status(value) -> str:
    status = str(value or "").strip()
    if status not in STORE_STATUS_VALUES:
        raise BusinessError("门店状态不合法", "invalid_store_status")
    return status


def _validate_menu_status(value) -> str:
    status = str(value or "").strip()
    if status not in MENU_STATUS_VALUES:
        raise BusinessError("菜单状态不合法", "invalid_menu_status")
    return status


def _validate_coupon_status(value) -> str:
    status = str(value or "").strip()
    if status not in COUPON_STATUS_VALUES:
        raise BusinessError("优惠券活动状态不合法", "invalid_coupon_status")
    return status


def _parse_money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError("金额格式不合法", "invalid_money") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("99999999.99"):
        raise BusinessError("金额必须为有效的非负数且不能超过 99999999.99", "invalid_money")
    return amount.quantize(Decimal("0.01"))


def _positive_int(value, message: str, code: str) -> int:
    number = _strict_integer(value, message, code)
    if number <= 0:
        raise BusinessError(message, code)
    return number


def _required_text(value, message: str, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise BusinessError(message, code)
    return text


def _parse_time(value) -> time | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    raise BusinessError("营业时间格式不合法", "invalid_business_time")


def _parse_datetime_required(value, message: str) -> datetime:
    if not value:
        raise BusinessError(message, "invalid_datetime")
    try:
        from zoneinfo import ZoneInfo
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo("Asia/Singapore")).replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError as exc:
        raise BusinessError("时间格式不合法", "invalid_datetime") from exc


def _validate_coupon_time_range(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise BusinessError("活动结束时间必须晚于开始时间", "invalid_coupon_time_range")


def _strict_integer(value, message: str, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise BusinessError(message, code)
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise BusinessError(message, code) from exc


def _strict_bool(value) -> bool:
    if not isinstance(value, bool):
        raise BusinessError("状态字段必须为布尔值", "invalid_boolean")
    return value


def _validate_per_user_limit(value) -> int:
    if _strict_integer(value, "每人限领数量必须为 1", "invalid_coupon_limit") != 1:
        raise BusinessError("第一版每个活动每人限领一张", "invalid_coupon_limit")
    return 1


def _protect_coupon_terms(activity: CouponActivity, payload: dict) -> None:
    """
    函数名称：_protect_coupon_terms
    函数用途：活动开始或已发生领取后冻结影响已发权益的配置
    参数说明：activity 为加锁活动，payload 为更新字段
    返回值说明：无
    核心逻辑：已开始、已运行、已领券或有任务即冻结金额、门槛、期限、范围、总库存和限领数量
    异常或失败情况：保护字段变化或重新退回草稿时拒绝；允许等值提交和暂停/结束
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    protected = (current_time() >= activity.start_at or activity.activity_status not in ("draft", "scheduled")
                 or UserCoupon.query.filter_by(activity_id=activity.id).first() is not None
                 or CouponClaimTask.query.filter_by(activity_id=activity.id).first() is not None)
    for field in ("start_at", "end_at", "total_stock", "per_user_limit", "discount_amount", "minimum_order_amount", "store_ids", "product_ids"):
        if field not in payload:
            continue
        if field.endswith("_ids"):
            actual = sorted(getattr(link, "store_id" if field == "store_ids" else "product_id") for link in (activity.store_links if field == "store_ids" else activity.product_links))
            candidate = _normalize_id_list(payload[field])
        elif field.endswith("_at"):
            actual, candidate = getattr(activity, field), _parse_datetime_required(payload[field], "活动时间不能为空")
        elif field in ("discount_amount", "minimum_order_amount"):
            actual, candidate = getattr(activity, field), _parse_money(payload[field])
        else:
            actual, candidate = getattr(activity, field), _positive_int(payload[field], "活动参数必须为正整数", "invalid_coupon_payload")
        if actual != candidate and protected:
            raise BusinessError("活动已开始或产生领取，优惠权益配置不可修改", "coupon_terms_locked")
        if actual != candidate and field == "total_stock":
            from app.coupons.redis_store import get_coupon_redis_store
            try:
                warmed = get_coupon_redis_store().metrics(activity.id)["remaining_stock"] is not None
            except Exception as exc:
                raise BusinessError("无法核验预热库存，请稍后修改", "coupon_redis_unavailable", 503) from exc
            if warmed:
                raise BusinessError("活动库存已预热，不能直接修改总库存", "coupon_stock_warmed")
    if protected and payload.get("activity_status") in ("draft", "scheduled") and payload["activity_status"] != activity.activity_status:
        raise BusinessError("已运行活动不能退回草稿或待开始状态", "invalid_coupon_transition")
    if activity.activity_status == "ended" and payload.get("activity_status", "ended") != "ended":
        raise BusinessError("已结束活动不能重新开放", "invalid_coupon_transition")
