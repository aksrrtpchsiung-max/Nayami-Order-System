"""
文件名称：models.py
文件用途：定义订单、订单明细和订单状态日志 ORM 模型
主要职责：映射 orders、order_items、order_status_logs 表，支撑下单和门店履约状态机
所属业务模块：订单
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class Order(db.Model):
    """
    类名称：Order
    类用途：保存顾客提交的订单主记录
    主要职责：承载订单金额、状态机、门店、顾客、取餐码和支付截止时间
    不负责的内容：不直接保存支付状态，支付状态由 PaymentRecord 承载
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "orders"
    __table_args__ = (db.UniqueConstraint("store_id", "pickup_date", "pickup_code", name="uq_order_store_pickup_date_code"),)

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    order_no = db.Column(db.String(64), nullable=False, unique=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    store_id = db.Column(ID_TYPE, db.ForeignKey("stores.id"), nullable=False)
    order_type = db.Column(db.String(32), nullable=False)
    order_status = db.Column(db.String(32), nullable=False, default="pending_payment")
    items_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payable_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    user_coupon_id = db.Column(ID_TYPE)
    pickup_code = db.Column(db.String(32))
    pickup_date = db.Column(db.Date)
    remark = db.Column(db.String(500))
    tableware_count = db.Column(db.Integer, nullable=False, default=0)
    payment_deadline = db.Column(db.DateTime, nullable=False)
    cancel_reason = db.Column(db.String(255))
    paid_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    user = db.relationship("User")
    store = db.relationship("Store", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = db.relationship("PaymentRecord", back_populates="order")
    status_logs = db.relationship("OrderStatusLog", back_populates="order")


class OrderItem(db.Model):
    """
    类名称：OrderItem
    类用途：保存订单商品快照
    主要职责：记录下单时商品名称、价格、数量和门店商品关联
    不负责的内容：不随商品后续改名改价而变化
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "order_items"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(ID_TYPE, db.ForeignKey("products.id"), nullable=False)
    store_product_id = db.Column(ID_TYPE, db.ForeignKey("store_products.id"), nullable=False)
    product_name_zh = db.Column(db.String(128), nullable=False)
    product_name_en = db.Column(db.String(128))
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal_amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")
    store_product = db.relationship("StoreProduct", back_populates="order_items")


class OrderStatusLog(db.Model):
    """
    类名称：OrderStatusLog
    类用途：记录订单状态变化
    主要职责：追踪下单、支付成功和门店履约每一次状态流转
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "order_status_logs"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id"), nullable=False)
    from_status = db.Column(db.String(32))
    to_status = db.Column(db.String(32), nullable=False)
    trigger_type = db.Column(db.String(32), nullable=False)
    operator_id = db.Column(ID_TYPE, db.ForeignKey("users.id"))
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    order = db.relationship("Order", back_populates="status_logs")
    operator = db.relationship("User")
