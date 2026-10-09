"""
文件名称：validate_database_schema.py
文件用途：在一次性 MySQL 数据库中验证建表和演示种子 SQL
主要职责：创建唯一临时库、执行三个初始化脚本、核对表与 Bistro 菜单种子数量并删除临时库
所属业务模块：数据库测试
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from urllib.parse import quote_plus

import pymysql

from _runtime import PROJECT_ROOT, database_parts


def main() -> None:
    source_database_name = "nayami_order_system"
    temporary_database_name = f"nayami_verify_{int(time.time())}_{os.getpid()}"
    connection_values = database_parts()
    command = [
        "mysql",
        "--protocol=TCP",
        "--host",
        str(connection_values["host"]),
        "--port",
        str(connection_values["port"]),
        "--user",
        str(connection_values["user"]),
        "--default-character-set=utf8mb4",
    ]
    environment = os.environ.copy()
    environment["MYSQL_PWD"] = str(connection_values["password"])
    schema_script = PROJECT_ROOT / "database/init/001_create_database.sql"
    seed_scripts = [
        PROJECT_ROOT / "database/init/002_seed_demo_data.sql",
        PROJECT_ROOT / "database/init/003_seed_demo_coupon.sql",
    ]
    scripts = [schema_script, *seed_scripts, *seed_scripts]
    sql_payload = "\n".join(
        script.read_text(encoding="utf-8").replace(source_database_name, temporary_database_name)
        for script in scripts
    )
    try:
        subprocess.run(command, input=sql_payload.encode("utf-8"), env=environment, check=True)
        database = pymysql.connect(
            host=str(connection_values["host"]),
            port=int(connection_values["port"]),
            user=str(connection_values["user"]),
            password=str(connection_values["password"]),
            database=temporary_database_name,
            connect_timeout=5,
        )
        with database.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
                (temporary_database_name,),
            )
            table_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM stores")
            store_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM products")
            product_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM product_categories")
            category_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM store_products")
            store_product_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM products WHERE image_url LIKE '/menu-images/%'")
            local_image_product_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM coupon_activities")
            activity_count = int(cursor.fetchone()[0])
        with database.cursor() as cursor:
            cursor.execute("UPDATE store_products SET current_stock=9, reserved_stock=2 WHERE id=1")
            cursor.execute("UPDATE products SET base_price=99 WHERE id=1")
            cursor.execute("UPDATE users SET is_active=0, token_version=3 WHERE id=2")
            cursor.execute("UPDATE user_roles SET role_id=2 WHERE user_id=2")
            cursor.execute("DELETE FROM coupon_activity_products WHERE activity_id=1 AND product_id=1")
        database.commit()
        repeat_sql = "\n".join(script.read_text(encoding="utf-8").replace(source_database_name, temporary_database_name) for script in seed_scripts)
        subprocess.run(command, input=repeat_sql.encode("utf-8"), env=environment, check=True)
        with database.cursor() as cursor:
            cursor.execute("SELECT current_stock,reserved_stock FROM store_products WHERE id=1")
            assert cursor.fetchone() == (9, 2), "Repeated seed reset live inventory"
            cursor.execute("SELECT base_price FROM products WHERE id=1")
            assert int(cursor.fetchone()[0]) == 99
            cursor.execute("SELECT is_active,token_version FROM users WHERE id=2")
            assert cursor.fetchone() == (0, 3)
            cursor.execute("SELECT role_id FROM user_roles WHERE user_id=2")
            assert cursor.fetchall() == ((2,),), "Repeated seed restored revoked role"
            cursor.execute("SELECT COUNT(*) FROM coupon_activity_products WHERE activity_id=1 AND product_id=1")
            assert cursor.fetchone()[0] == 0, "Repeated seed changed coupon scope"
        database.close()
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=PROJECT_ROOT / "backend", env=_migration_environment(connection_values, temporary_database_name), check=True,
        )
        print("Repeated seed preserves inventory, menu edits, revoked sessions/roles and coupon scopes; SQL-created schema upgrades to head.")
        if (
            table_count < 19
            or store_count != 3
            or category_count != 9
            or product_count != 40
            or store_product_count != 120
            or local_image_product_count != 40
            or activity_count != 1
        ):
            raise RuntimeError(
                f"Unexpected seed result: tables={table_count}, stores={store_count}, "
                f"categories={category_count}, products={product_count}, "
                f"store_products={store_product_count}, local_image_products={local_image_product_count}, "
                f"activities={activity_count}"
            )
        print(
            f"Schema validation passed: {table_count} tables, {store_count} stores, "
            f"{category_count} categories, {product_count} products, "
            f"{store_product_count} store products, {activity_count} coupon activity."
        )
    finally:
        _drop_database(connection_values, temporary_database_name)

    migration_database_name = f"nayami_migration_verify_{int(time.time())}_{os.getpid()}"
    admin_database = _admin_database(connection_values)
    with admin_database.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE `{migration_database_name}` "
            "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"
        )
    admin_database.close()
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = (
        "mysql+pymysql://"
        f"{quote_plus(str(connection_values['user']))}:"
        f"{quote_plus(str(connection_values['password']))}@"
        f"{connection_values['host']}:{connection_values['port']}/"
        f"{migration_database_name}?charset=utf8mb4"
    )
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=PROJECT_ROOT / "backend",
            env=migration_environment,
            check=True,
        )
        migration_database = pymysql.connect(
            host=str(connection_values["host"]),
            port=int(connection_values["port"]),
            user=str(connection_values["user"]),
            password=str(connection_values["password"]),
            database=migration_database_name,
            connect_timeout=5,
        )
        with migration_database.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
                (migration_database_name,),
            )
            migrated_table_count = int(cursor.fetchone()[0])
        migration_database.close()
        if migrated_table_count < 20:
            raise RuntimeError(f"Alembic created only {migrated_table_count} tables")
        for target in ("downgrade", "upgrade"):
            subprocess.run(
                [sys.executable, "-m", "alembic", "-c", "alembic.ini", target, "20260728_0001" if target == "downgrade" else "head"],
                cwd=PROJECT_ROOT / "backend", env=migration_environment, check=True,
            )
        print(f"Alembic validation passed: {migrated_table_count} tables; head to baseline to head round trip passed.")
    finally:
        _drop_database(connection_values, migration_database_name)



def _migration_environment(connection, database_name):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        f"mysql+pymysql://{quote_plus(str(connection['user']))}:{quote_plus(str(connection['password']))}"
        f"@{connection['host']}:{connection['port']}/{database_name}?charset=utf8mb4"
    )
    return environment


def _admin_database(connection_values: dict):
    return pymysql.connect(
        host=str(connection_values["host"]),
        port=int(connection_values["port"]),
        user=str(connection_values["user"]),
        password=str(connection_values["password"]),
        connect_timeout=5,
    )


def _drop_database(connection_values: dict, database_name: str) -> None:
    admin_database = _admin_database(connection_values)
    with admin_database.cursor() as cursor:
        cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
    admin_database.close()


if __name__ == "__main__":
    main()
