"""
文件名称：model_types.py
文件用途：提供 ORM 通用字段类型
主要职责：兼容 MySQL BIGINT 主键和 SQLite 测试自增主键
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from app.extensions import db

ID_TYPE = db.BigInteger().with_variant(db.Integer, "sqlite")
