"""
文件名称：20260908_0002_commerce.py
文件用途：补齐订单取餐日期与门店每日取餐码唯一约束
主要职责：兼容初始化建库、回填历史付款日期并增加唯一索引
所属业务模块：数据库迁移
创建时间：2026-09-08 17:30
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from alembic import op
import sqlalchemy as sa

revision = "20260908_0002"
down_revision = "20260728_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """兼容新库已存在的日期字段，旧数据以支付日期回填，再建立复合唯一约束。"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "pickup_date" not in {column["name"] for column in inspector.get_columns("orders")}:
        op.add_column("orders", sa.Column("pickup_date", sa.Date(), nullable=True))
    connection.execute(sa.text("UPDATE orders SET pickup_date = DATE(COALESCE(paid_at, created_at)) WHERE pickup_code IS NOT NULL AND pickup_date IS NULL"))
    existing = {constraint["name"] for constraint in sa.inspect(connection).get_unique_constraints("orders")}
    if "uq_order_store_pickup_date_code" not in existing:
        with op.batch_alter_table("orders") as batch:
            batch.create_unique_constraint("uq_order_store_pickup_date_code", ["store_id", "pickup_date", "pickup_code"])


def downgrade() -> None:
    """仅移除新约束和新字段，保留全部订单、付款和短码历史。"""
    connection = op.get_bind()
    # MySQL 可能用新增复合索引替代原外键索引；先补独立索引再删除约束。
    if connection.dialect.name == "mysql":
        indexes = sa.inspect(connection).get_indexes("orders")
        if not any(index["name"] != "uq_order_store_pickup_date_code" and index["column_names"][0] == "store_id" for index in indexes):
            op.create_index("ix_orders_store_id", "orders", ["store_id"])
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("uq_order_store_pickup_date_code", type_="unique")
        batch.drop_column("pickup_date")
