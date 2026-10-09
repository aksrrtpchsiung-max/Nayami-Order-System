"""
文件名称：models.py
文件用途：定义支付单、退款单和支付日志 ORM 模型
主要职责：映射 payment_records、refund_records、payment_logs 表，支撑支付仿真和幂等日志
所属业务模块：支付
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class PaymentRecord(db.Model):
    """
    类名称：PaymentRecord
    类用途：保存订单支付过程和仿真支付结果
    主要职责：承载支付金额、支付方式、支付状态、幂等键和仿真流水号
    不负责的内容：不直接替代订单履约状态
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "payment_records"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    payment_no = db.Column(db.String(64), nullable=False, unique=True)
    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id"), nullable=False)
    payment_method = db.Column(db.String(32), nullable=False)
    card_brand = db.Column(db.String(32))
    masked_card_no = db.Column(db.String(32))
    payment_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_status = db.Column(db.String(32), nullable=False, default="pending")
    transaction_no = db.Column(db.String(128), unique=True)
    idempotency_key = db.Column(db.String(128), unique=True)
    failure_reason = db.Column(db.String(255))
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    order = db.relationship("Order", back_populates="payments")
    logs = db.relationship("PaymentLog", back_populates="payment")


class RefundRecord(db.Model):
    """
    类名称：RefundRecord
    类用途：保存退款仿真记录
    主要职责：记录退款申请、退款原因、金额及仿真成功结果，支撑订单退款恢复库存闭环
    不负责的内容：不执行真实资金支付或退款
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "refund_records"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    refund_no = db.Column(db.String(64), nullable=False, unique=True)
    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id"), nullable=False)
    payment_id = db.Column(ID_TYPE, db.ForeignKey("payment_records.id"), nullable=False)
    refund_amount = db.Column(db.Numeric(10, 2), nullable=False)
    refund_status = db.Column(db.String(32), nullable=False, default="pending")
    refund_reason = db.Column(db.String(255))
    simulated_refund_no = db.Column(db.String(128), unique=True)
    refunded_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class PaymentLog(db.Model):
    """
    类名称：PaymentLog
    类用途：记录支付状态变化和回调事件
    主要职责：记录支付创建、仿真回调和重复回调幂等处理结果
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "payment_logs"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    payment_id = db.Column(ID_TYPE, db.ForeignKey("payment_records.id"), nullable=False)
    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id"), nullable=False)
    from_status = db.Column(db.String(32))
    to_status = db.Column(db.String(32), nullable=False)
    event_type = db.Column(db.String(32), nullable=False)
    idempotency_key = db.Column(db.String(128))
    event_payload = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    payment = db.relationship("PaymentRecord", back_populates="logs")
    order = db.relationship("Order")
