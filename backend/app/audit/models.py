"""
文件名称：models.py
文件用途：定义后台操作日志 ORM 模型
主要职责：映射 operation_logs 表，记录门店履约等后台关键操作
所属业务模块：审计
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class OperationLog(db.Model):
    """
    类名称：OperationLog
    类用途：保存后台关键操作审计记录
    主要职责：记录操作人、模块、动作、对象、结果和前后摘要
    不负责的内容：不保存明文密码、完整银行卡号或验证码
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "operation_logs"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    operator_id = db.Column(ID_TYPE, db.ForeignKey("users.id"))
    operator_role_code = db.Column(db.String(64))
    operation_module = db.Column(db.String(64), nullable=False)
    operation_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(ID_TYPE)
    store_id = db.Column(ID_TYPE, db.ForeignKey("stores.id"))
    before_snapshot = db.Column(db.JSON)
    after_snapshot = db.Column(db.JSON)
    operation_result = db.Column(db.String(32), nullable=False)
    failure_reason = db.Column(db.String(255))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
