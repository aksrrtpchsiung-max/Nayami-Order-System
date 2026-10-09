"""
文件名称：20260728_0001_initial_schema.py
文件用途：建立奈亚米订单系统第一版完整数据库结构
主要职责：使用固定基线定义创建业务表，防止后续模型修改改变历史迁移
所属业务模块：数据库迁移
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from alembic import op

import sqlalchemy as sa

revision = "20260728_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    函数名称：upgrade
    函数用途：在空数据库创建第一版全部 ORM 表，并兼容已由初始化 SQL 创建的表
    参数说明：无
    返回值说明：无
    核心逻辑：使用固定基线定义兼容初始化 SQL 既有表，不提前引入未来版本字段
    异常或失败情况：数据库连接失败或结构冲突时迁移失败并回滚
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    _create_table('product_categories',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('name_zh', sa.String(length=128), nullable=False),
    sa.Column('name_en', sa.String(length=128), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('roles',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('role_code', sa.String(length=64), nullable=False),
    sa.Column('role_name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('permission_codes', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('role_code')
    )
    _create_table('stores',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('store_code', sa.String(length=64), nullable=False),
    sa.Column('name_zh', sa.String(length=128), nullable=False),
    sa.Column('name_en', sa.String(length=128), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('business_start_time', sa.Time(), nullable=False),
    sa.Column('business_end_time', sa.Time(), nullable=False),
    sa.Column('store_status', sa.String(length=32), nullable=False),
    sa.Column('temporary_close_reason', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('store_code')
    )
    _create_table('users',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('user_type', sa.String(length=32), nullable=False),
    sa.Column('default_language', sa.String(length=16), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('phone'),
    sa.UniqueConstraint('username')
    )
    _create_table('coupon_activities',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('activity_name_zh', sa.String(length=128), nullable=False),
    sa.Column('activity_name_en', sa.String(length=128), nullable=True),
    sa.Column('description_zh', sa.Text(), nullable=True),
    sa.Column('description_en', sa.Text(), nullable=True),
    sa.Column('start_at', sa.DateTime(), nullable=False),
    sa.Column('end_at', sa.DateTime(), nullable=False),
    sa.Column('total_stock', sa.Integer(), nullable=False),
    sa.Column('per_user_limit', sa.Integer(), nullable=False),
    sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('minimum_order_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('activity_status', sa.String(length=32), nullable=False),
    sa.Column('created_by', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('operation_logs',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('operator_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('operator_role_code', sa.String(length=64), nullable=True),
    sa.Column('operation_module', sa.String(length=64), nullable=False),
    sa.Column('operation_type', sa.String(length=64), nullable=False),
    sa.Column('target_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('before_snapshot', sa.JSON(), nullable=True),
    sa.Column('after_snapshot', sa.JSON(), nullable=True),
    sa.Column('operation_result', sa.String(length=32), nullable=False),
    sa.Column('failure_reason', sa.String(length=255), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('orders',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('order_no', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('order_type', sa.String(length=32), nullable=False),
    sa.Column('order_status', sa.String(length=32), nullable=False),
    sa.Column('items_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('payable_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('user_coupon_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('pickup_code', sa.String(length=32), nullable=True),
    sa.Column('remark', sa.String(length=500), nullable=True),
    sa.Column('tableware_count', sa.Integer(), nullable=False),
    sa.Column('payment_deadline', sa.DateTime(), nullable=False),
    sa.Column('cancel_reason', sa.String(length=255), nullable=True),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_no')
    )
    _create_table('products',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('category_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('name_zh', sa.String(length=128), nullable=False),
    sa.Column('name_en', sa.String(length=128), nullable=True),
    sa.Column('description_zh', sa.Text(), nullable=True),
    sa.Column('description_en', sa.Text(), nullable=True),
    sa.Column('image_url', sa.String(length=512), nullable=True),
    sa.Column('base_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('menu_status', sa.String(length=32), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['product_categories.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('user_roles',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('role_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('user_store_bindings',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('binding_type', sa.String(length=32), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('coupon_activity_products',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('activity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('product_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['coupon_activities.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activity_id', 'product_id', name='uk_coupon_activity_products_activity_product')
    )
    _create_table('coupon_activity_stores',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('activity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['coupon_activities.id'], ),
    sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activity_id', 'store_id', name='uk_coupon_activity_stores_activity_store')
    )
    _create_table('order_status_logs',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('from_status', sa.String(length=32), nullable=True),
    sa.Column('to_status', sa.String(length=32), nullable=False),
    sa.Column('trigger_type', sa.String(length=32), nullable=False),
    sa.Column('operator_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('payment_records',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('payment_no', sa.String(length=64), nullable=False),
    sa.Column('order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('payment_method', sa.String(length=32), nullable=False),
    sa.Column('card_brand', sa.String(length=32), nullable=True),
    sa.Column('masked_card_no', sa.String(length=32), nullable=True),
    sa.Column('payment_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('payment_status', sa.String(length=32), nullable=False),
    sa.Column('transaction_no', sa.String(length=128), nullable=True),
    sa.Column('idempotency_key', sa.String(length=128), nullable=True),
    sa.Column('failure_reason', sa.String(length=255), nullable=True),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key'),
    sa.UniqueConstraint('payment_no'),
    sa.UniqueConstraint('transaction_no')
    )
    _create_table('store_products',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('product_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('is_available', sa.Boolean(), nullable=False),
    sa.Column('current_stock', sa.Integer(), nullable=False),
    sa.Column('reserved_stock', sa.Integer(), nullable=False),
    sa.Column('is_sold_out', sa.Boolean(), nullable=False),
    sa.Column('last_operator_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['last_operator_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('user_coupons',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('activity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('minimum_order_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('coupon_status', sa.String(length=32), nullable=False),
    sa.Column('claimed_at', sa.DateTime(), nullable=False),
    sa.Column('used_order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('expired_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['coupon_activities.id'], ),
    sa.ForeignKeyConstraint(['used_order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activity_id', 'user_id', name='uk_user_coupons_activity_user')
    )
    _create_table('coupon_claim_tasks',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('activity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_coupon_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('redis_success_time', sa.DateTime(), nullable=False),
    sa.Column('task_status', sa.String(length=32), nullable=False),
    sa.Column('retry_count', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('next_retry_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['coupon_activities.id'], ),
    sa.ForeignKeyConstraint(['user_coupon_id'], ['user_coupons.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activity_id', 'user_id', name='uk_coupon_claim_tasks_activity_user')
    )
    _create_table('inventory_logs',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('store_product_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('change_type', sa.String(length=32), nullable=False),
    sa.Column('change_quantity', sa.Integer(), nullable=False),
    sa.Column('before_current_stock', sa.Integer(), nullable=False),
    sa.Column('after_current_stock', sa.Integer(), nullable=False),
    sa.Column('before_reserved_stock', sa.Integer(), nullable=False),
    sa.Column('after_reserved_stock', sa.Integer(), nullable=False),
    sa.Column('operator_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('remark', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
    sa.ForeignKeyConstraint(['store_product_id'], ['store_products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('order_items',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('product_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('store_product_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('product_name_zh', sa.String(length=128), nullable=False),
    sa.Column('product_name_en', sa.String(length=128), nullable=True),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('subtotal_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['store_product_id'], ['store_products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('payment_logs',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('payment_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('from_status', sa.String(length=32), nullable=True),
    sa.Column('to_status', sa.String(length=32), nullable=False),
    sa.Column('event_type', sa.String(length=32), nullable=False),
    sa.Column('idempotency_key', sa.String(length=128), nullable=True),
    sa.Column('event_payload', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['payment_id'], ['payment_records.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('refund_records',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('refund_no', sa.String(length=64), nullable=False),
    sa.Column('order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('payment_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('refund_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('refund_status', sa.String(length=32), nullable=False),
    sa.Column('refund_reason', sa.String(length=255), nullable=True),
    sa.Column('simulated_refund_no', sa.String(length=128), nullable=True),
    sa.Column('refunded_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['payment_id'], ['payment_records.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('refund_no'),
    sa.UniqueConstraint('simulated_refund_no')
    )


def downgrade() -> None:
    """第一版基线不提供批量删表降级，避免误删真实业务数据。"""

    raise RuntimeError("The initial Nayami schema cannot be downgraded automatically.")


def _create_table(name, *columns):
    """兼容已由 SQL 初始化的基线表；新字段由后续迁移处理。"""
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns)
