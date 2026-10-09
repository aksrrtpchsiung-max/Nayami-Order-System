"""
文件名称：models.py
文件用途：定义用户、角色和门店绑定 ORM 模型
主要职责：映射 users、roles、user_roles、user_store_bindings 表，支撑登录与门店数据范围校验
所属业务模块：用户与权限
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class User(db.Model):
    """
    类名称：User
    类用途：保存顾客和后台账号基础身份
    主要职责：提供登录身份、令牌失效版本、默认语言、角色关系和门店绑定关系
    不负责的内容：不负责订单、支付和库存业务状态流转
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "users"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    phone = db.Column(db.String(32), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.String(32), nullable=False)
    default_language = db.Column(db.String(16), nullable=False, default="zh-CN")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    token_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    role_links = db.relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    store_bindings = db.relationship("UserStoreBinding", back_populates="user", cascade="all, delete-orphan")

    def has_any_role(self, role_codes) -> bool:
        role_code_set = set(role_codes)
        return any(link.role and link.role.role_code in role_code_set for link in self.role_links)

    def first_role_code(self) -> str | None:
        for link in self.role_links:
            if link.role:
                return link.role.role_code
        return None


class Role(db.Model):
    """
    类名称：Role
    类用途：保存后台角色定义
    主要职责：提供门店员工、门店经理、品牌管理员和系统管理员角色编码
    不负责的内容：不负责复杂按钮级 RBAC 配置
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "roles"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    role_code = db.Column(db.String(64), nullable=False, unique=True)
    role_name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(255))
    permission_codes = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    user_links = db.relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class UserRole(db.Model):
    """
    类名称：UserRole
    类用途：保存用户与角色关联
    主要职责：让后台账号获得门店员工或门店经理等角色
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "user_roles"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    role_id = db.Column(ID_TYPE, db.ForeignKey("roles.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship("User", back_populates="role_links")
    role = db.relationship("Role", back_populates="user_links")


class UserStoreBinding(db.Model):
    """
    类名称：UserStoreBinding
    类用途：保存后台用户和门店的数据范围关系
    主要职责：限制门店人员只能查看和处理所属门店订单
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "user_store_bindings"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    store_id = db.Column(ID_TYPE, db.ForeignKey("stores.id"), nullable=False)
    binding_type = db.Column(db.String(32), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    user = db.relationship("User", back_populates="store_bindings")
    store = db.relationship("Store", back_populates="user_bindings")
