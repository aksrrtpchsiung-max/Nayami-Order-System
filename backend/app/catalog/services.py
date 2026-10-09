"""
文件名称：services.py
文件用途：实现菜单查询业务服务
主要职责：按门店返回有效发布商品，隐藏停用分类和库存数量，并结合营业状态决定可加购
所属业务模块：商品与菜单
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from collections import OrderedDict

from app.catalog.models import Product, ProductCategory, StoreProduct
from app.common.enums import MENU_STATUS_PUBLISHED, MENU_STATUS_DRAFT_CHANGES
from app.common.errors import NotFoundError
from app.common.formatters import format_money
from app.extensions import db
from app.stores.models import Store
from app.stores.services import serialize_store

LIVE_MENU_STATUSES = (MENU_STATUS_PUBLISHED, MENU_STATUS_DRAFT_CHANGES)


def list_store_menu(store_id: int) -> dict:
    """
    函数名称：list_store_menu
    函数用途：查询顾客菜单及当前可加购状态
    参数说明：store_id 为门店标识
    返回值说明：门店信息和有效分类商品，不返回内部库存数量
    核心逻辑：使用线上发布字段，过滤停用分类；营业中且未售罄且有可用库存才能加购
    异常或失败情况：门店不存在或停用时拒绝
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    store = db.session.get(Store, store_id)
    if store is None or not store.is_active:
        raise NotFoundError("门店不存在或已停用")

    store_products = (
        StoreProduct.query.join(StoreProduct.product)
        .filter(StoreProduct.store_id == store_id)
        .filter(StoreProduct.is_available.is_(True))
        .filter(Product.menu_status.in_(LIVE_MENU_STATUSES))
        .filter(Product.category.has(ProductCategory.is_active.is_(True)))
        .order_by(StoreProduct.id.asc())
        .all()
    )
    store_data = serialize_store(store)
    categories: OrderedDict[int, dict] = OrderedDict()
    for store_product in sorted(
        store_products,
        key=lambda item: (item.product.category.sort_order, item.product.sort_order, item.id),
    ):
        product = store_product.product
        category = product.category
        available_stock = max(store_product.current_stock - store_product.reserved_stock, 0)
        category_data = categories.setdefault(
            category.id,
            {
                "id": category.id,
                "name_zh": category.name_zh,
                "name_en": category.name_en,
                "products": [],
            },
        )
        category_data["products"].append(
            {
                "store_product_id": store_product.id,
                "product_id": product.id,
                "name_zh": product.name_zh,
                "name_en": product.name_en,
                "description_zh": product.description_zh,
                "description_en": product.description_en,
                "image_url": product.image_url,
                "base_price": format_money(product.base_price),
                "is_available": bool(store_product.is_available),
                "is_sold_out": bool(store_product.is_sold_out or available_stock == 0),
                "can_add_to_cart": store_data["can_order"] and available_stock > 0 and not store_product.is_sold_out,
            }
        )
    return {"store": store_data, "categories": list(categories.values())}
