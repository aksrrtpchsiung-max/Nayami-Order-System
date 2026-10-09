"""
文件名称：models.py
文件用途：定义优惠券活动、用户优惠券和抢券落库任务 ORM 模型
主要职责：映射 coupon_activities、coupon_activity_stores、coupon_activity_products、user_coupons 和 coupon_claim_tasks 表
所属业务模块：优惠券
创建时间：2026-05-26 16:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime

from app.common.model_types import ID_TYPE
from app.extensions import db


class CouponActivity(db.Model):
    """
    类名称：CouponActivity
    类用途：保存品牌优惠券活动配置
    主要职责：提供活动名称、时间、库存、优惠金额、门槛和活动状态
    不负责的内容：不直接执行 Redis 抢券和异步落库任务
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "coupon_activities"

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    activity_name_zh = db.Column(db.String(128), nullable=False)
    activity_name_en = db.Column(db.String(128))
    description_zh = db.Column(db.Text)
    description_en = db.Column(db.Text)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    total_stock = db.Column(db.Integer, nullable=False)
    per_user_limit = db.Column(db.Integer, nullable=False, default=1)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False)
    minimum_order_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    activity_status = db.Column(db.String(32), nullable=False, default="draft")
    created_by = db.Column(ID_TYPE, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    store_links = db.relationship("CouponActivityStore", back_populates="activity", cascade="all, delete-orphan")
    product_links = db.relationship("CouponActivityProduct", back_populates="activity", cascade="all, delete-orphan")
    user_coupons = db.relationship("UserCoupon", back_populates="activity")
    claim_tasks = db.relationship("CouponClaimTask", back_populates="activity")


class CouponActivityStore(db.Model):
    """
    类名称：CouponActivityStore
    类用途：保存优惠券活动适用门店
    主要职责：限制活动适用门店范围
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "coupon_activity_stores"
    __table_args__ = (db.UniqueConstraint("activity_id", "store_id", name="uk_coupon_activity_stores_activity_store"),)

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    activity_id = db.Column(ID_TYPE, db.ForeignKey("coupon_activities.id"), nullable=False)
    store_id = db.Column(ID_TYPE, db.ForeignKey("stores.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    activity = db.relationship("CouponActivity", back_populates="store_links")
    store = db.relationship("Store")


class CouponActivityProduct(db.Model):
    """
    类名称：CouponActivityProduct
    类用途：保存优惠券活动适用商品
    主要职责：限制活动适用商品范围
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "coupon_activity_products"
    __table_args__ = (
        db.UniqueConstraint("activity_id", "product_id", name="uk_coupon_activity_products_activity_product"),
    )

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    activity_id = db.Column(ID_TYPE, db.ForeignKey("coupon_activities.id"), nullable=False)
    product_id = db.Column(ID_TYPE, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    activity = db.relationship("CouponActivity", back_populates="product_links")
    product = db.relationship("Product")


class UserCoupon(db.Model):
    """
    类名称：UserCoupon
    类用途：保存用户已领取优惠券
    主要职责：提供领取、可用、已使用、过期等优惠券状态记录
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "user_coupons"
    __table_args__ = (db.UniqueConstraint("activity_id", "user_id", name="uk_user_coupons_activity_user"),)

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    activity_id = db.Column(ID_TYPE, db.ForeignKey("coupon_activities.id"), nullable=False)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False)
    minimum_order_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    coupon_status = db.Column(db.String(32), nullable=False, default="syncing")
    claimed_at = db.Column(db.DateTime, nullable=False)
    used_order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id"))
    used_at = db.Column(db.DateTime)
    expired_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    activity = db.relationship("CouponActivity", back_populates="user_coupons")
    user = db.relationship("User")
    used_order = db.relationship("Order")


class CouponClaimTask(db.Model):
    """
    类名称：CouponClaimTask
    类用途：保存抢券异步落库任务
    主要职责：记录 Redis 成功后的数据库落库状态、重试次数和失败原因
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    __tablename__ = "coupon_claim_tasks"
    __table_args__ = (db.UniqueConstraint("activity_id", "user_id", name="uk_coupon_claim_tasks_activity_user"),)

    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)
    activity_id = db.Column(ID_TYPE, db.ForeignKey("coupon_activities.id"), nullable=False)
    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id"), nullable=False)
    user_coupon_id = db.Column(ID_TYPE, db.ForeignKey("user_coupons.id"))
    redis_success_time = db.Column(db.DateTime, nullable=False)
    task_status = db.Column(db.String(32), nullable=False, default="pending")
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text)
    next_retry_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    activity = db.relationship("CouponActivity", back_populates="claim_tasks")
    user = db.relationship("User")
    user_coupon = db.relationship("UserCoupon")
