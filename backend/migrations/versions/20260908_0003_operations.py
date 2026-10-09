"""
文件名称：20260908_0003_operations.py
文件用途：为品牌商品增加独立待发布内容
主要职责：兼容旧库和由当前 ORM 建立的新库，保留线上商品字段供菜单与订单使用
所属业务模块：数据库迁移
创建时间：2026-09-08 17:11
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0003"
down_revision = "20260908_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加可空 JSON 字段，旧商品无需数据迁移，重复初始化不会重复加列。"""
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("products")}
    if "pending_changes" not in columns:
        op.add_column("products", sa.Column("pending_changes", sa.JSON(), nullable=True))


def downgrade() -> None:
    """拒绝丢弃尚未发布的内容；清空待发布内容后可显式降级。"""
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM products WHERE menu_status = 'draft_changes' AND pending_changes IS NOT NULL")).scalar():
        raise RuntimeError("Publish or archive pending product changes before downgrading.")
    op.drop_column("products", "pending_changes")
