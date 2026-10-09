"""
文件名称：20260908_0004_system_security.py
文件用途：持久化系统设置及会话撤销版本
主要职责：为现有账号添加令牌版本并创建非交易配置表
所属业务模块：数据库迁移
创建时间：2026-09-08 17:18
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0004"
down_revision = "20260908_0003"
branch_labels = None
depends_on = None


def upgrade():
    """为既有令牌设置初始版本零，兼容先执行 SQL 初始化的数据库。"""
    inspector = sa.inspect(op.get_bind())
    if "token_version" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    if not inspector.has_table("system_settings"):
        user_id_type = next(column["type"] for column in inspector.get_columns("users") if column["name"] == "id")
        op.create_table(
            "system_settings",
            sa.Column("key", sa.String(64), primary_key=True),
            sa.Column("value", sa.JSON(), nullable=False),
            sa.Column("updated_by", user_id_type, sa.ForeignKey("users.id")),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )


def downgrade():
    """删除本版本配置表及令牌版本；降级需要重新登录所有账号。"""
    op.drop_table("system_settings")
    op.drop_column("users", "token_version")
