"""
文件名称：models.py
文件用途：定义商品分类、品牌商品和门店商品 ORM 模型
主要职责：映射 product_categories、products、store_products 表，支撑菜单浏览和库存校验
所属业务模块：商品与菜单
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class ProductCategory(db.Model):
    """
    类名称：ProductCategory
    类用途：保存品牌一级商品分类
    主要职责：按排序和语言展示顾客端菜单分类
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "product_categories"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    name_zh = db.Column(db.String(128), nullable=False)
    name_en = db.Column(db.String(128))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    """
    类名称：Product
    类用途：保存品牌统一商品资料
    主要职责：保存线上商品内容、独立待发布修改和菜单发布状态
    不负责的内容：不负责不同门店的库存和售罄状态
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "products"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    category_id = db.Column(ID_TYPE, db.ForeignKey("product_categories.id"), nullable=False)
    name_zh = db.Column(db.String(128), nullable=False)
    name_en = db.Column(db.String(128))
    description_zh = db.Column(db.Text)
    description_en = db.Column(db.Text)
    image_url = db.Column(db.String(512))
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    menu_status = db.Column(db.String(32), nullable=False, default="draft")
    pending_changes = db.Column(db.JSON)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    category = db.relationship("ProductCategory", back_populates="products")
    store_products = db.relationship("StoreProduct", back_populates="product")


class StoreProduct(db.Model):
    """
    类名称：StoreProduct
    类用途：保存商品在门店维度的可售和库存状态
    主要职责：支持顾客菜单展示、下单库存预占和支付成功确认扣减
    不负责的内容：不保存历史订单商品快照
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "store_products"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    store_id = db.Column(ID_TYPE, db.ForeignKey("stores.id"), nullable=False)
    product_id = db.Column(ID_TYPE, db.ForeignKey("products.id"), nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    current_stock = db.Column(db.Integer, nullable=False, default=0)
    reserved_stock = db.Column(db.Integer, nullable=False, default=0)
    is_sold_out = db.Column(db.Boolean, nullable=False, default=False)
    last_operator_id = db.Column(ID_TYPE, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    store = db.relationship("Store", back_populates="store_products")
    product = db.relationship("Product", back_populates="store_products")
    order_items = db.relationship("OrderItem", back_populates="store_product")
