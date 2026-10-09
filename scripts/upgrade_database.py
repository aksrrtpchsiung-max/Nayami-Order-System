"""
文件名称：upgrade_database.py
文件用途：创建或升级奈亚米订单系统数据库结构
主要职责：确保数据库存在并执行 Alembic upgrade head
所属业务模块：数据库运维
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

import subprocess
import sys

from _runtime import PROJECT_ROOT, run_mysql_script


def main() -> None:
    run_mysql_script(PROJECT_ROOT / "database/init/001_create_database.sql")
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=PROJECT_ROOT / "backend",
        check=True,
    )
    print("Database schema migrated to Alembic head.")


if __name__ == "__main__":
    main()
