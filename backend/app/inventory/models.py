"""
文件名称：models.py
文件用途：定义库存日志 ORM 模型
主要职责：映射 inventory_logs 表，追踪预占、确认扣减和释放库存行为
所属业务模块：库存
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class InventoryLog(db.Model):
    """
    类名称：InventoryLog
    类用途：记录库存关键变化
    主要职责：保存预占库存、确认扣减、释放库存和人工调整的前后数量
    不负责的内容：不作为当前库存唯一来源
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "inventory_logs"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    store_id = db.Column(ID_TYPE, db.ForeignKey("stores.id"), nullable=False)
    store_product_id = db.Column(ID_TYPE, db.ForeignKey("store_products.id"), nullable=False)
    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id"))
    change_type = db.Column(db.String(32), nullable=False)
    change_quantity = db.Column(db.Integer, nullable=False)
    before_current_stock = db.Column(db.Integer, nullable=False)
    after_current_stock = db.Column(db.Integer, nullable=False)
    before_reserved_stock = db.Column(db.Integer, nullable=False)
    after_reserved_stock = db.Column(db.Integer, nullable=False)
    operator_id = db.Column(ID_TYPE, db.ForeignKey("users.id"))
    remark = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
