"""
文件名称：models.py
文件用途：定义门店 ORM 模型
主要职责：映射 stores 表，保存门店基础资料、营业时间和营业状态
所属业务模块：门店
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class Store(db.Model):
    """
    类名称：Store
    类用途：保存城市内门店基础资料
    主要职责：提供下单门店、营业时间、营业状态和门店数据范围基础
    不负责的内容：不负责商品库存扣减和订单履约状态流转
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "stores"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    store_code = db.Column(db.String(64), nullable=False, unique=True)
    name_zh = db.Column(db.String(128), nullable=False)
    name_en = db.Column(db.String(128))
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(32))
    business_start_time = db.Column(db.Time, nullable=False)
    business_end_time = db.Column(db.Time, nullable=False)
    store_status = db.Column(db.String(32), nullable=False, default="open")
    temporary_close_reason = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    store_products = db.relationship("StoreProduct", back_populates="store")
    orders = db.relationship("Order", back_populates="store")
    user_bindings = db.relationship("UserStoreBinding", back_populates="store")
