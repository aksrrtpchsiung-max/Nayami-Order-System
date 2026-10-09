"""
文件名称：env.py
文件用途：配置 Alembic 在线和离线数据库迁移环境
主要职责：加载 Flask 配置、注册全部 ORM 模型并向 Alembic 提供元数据
所属业务模块：数据库迁移
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import create_app
from app.extensions import db

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

flask_app = create_app()
flask_app.app_context().push()
config.set_main_option("sqlalchemy.url", flask_app.config["SQLALCHEMY_DATABASE_URI"].replace("%", "%%"))
target_metadata = db.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=flask_app.config["SQLALCHEMY_DATABASE_URI"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
