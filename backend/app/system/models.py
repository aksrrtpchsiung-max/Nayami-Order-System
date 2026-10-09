"""
文件名称：models.py
文件用途：持久化系统允许维护的非交易配置
主要职责：存储配置值、操作人及修改时间，供 API 和 Worker 统一读取
所属业务模块：系统管理
创建时间：2026-09-08 17:56
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from app.common.model_types import ID_TYPE
from app.common.time_utils import current_time
from app.extensions import db


class SystemSetting(db.Model):
    """
    类名称：SystemSetting
    类用途：保存允许修改的系统设置
    主要职责：持久化白名单配置，不保存环境密钥或交易状态
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "system_settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.JSON, nullable=False)
    updated_by = db.Column(ID_TYPE, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime, nullable=False, default=current_time, onupdate=current_time)
