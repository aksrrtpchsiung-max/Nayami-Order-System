"""
文件名称：_runtime.py
文件用途：为本地运维脚本提供共享环境和 MySQL 执行能力
主要职责：加载根目录环境变量、解析数据库地址并安全调用 mysql 客户端
所属业务模块：本地开发与部署脚本
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_root_env() -> None:
    """加载项目根目录 .env，且不覆盖调用方已经设置的环境变量。"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def database_parts() -> dict[str, str | int]:
    """从 DATABASE_URL 或 MYSQL_* 变量解析 mysql 客户端连接参数。"""
    load_root_env()
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        parsed = urlparse(database_url.replace("mysql+pymysql://", "mysql://", 1))
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or "root"),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/") or os.getenv("MYSQL_DATABASE", "nayami_order_system"),
        }
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_ROOT_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "nayami_order_system"),
    }


def run_mysql_script(script_path: Path) -> None:
    """
    函数名称：run_mysql_script
    函数用途：通过 mysql 客户端执行一个受版本控制的 SQL 文件
    参数说明：script_path 为项目内 SQL 文件绝对路径
    返回值说明：成功无返回，失败抛出 CalledProcessError
    核心逻辑：密码只通过 MYSQL_PWD 子进程环境传递，避免出现在进程参数和日志中
    异常或失败情况：mysql 客户端缺失、连接失败或 SQL 失败时终止脚本
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    connection = database_parts()
    command = [
        "mysql",
        "--protocol=TCP",
        "--host",
        str(connection["host"]),
        "--port",
        str(connection["port"]),
        "--user",
        str(connection["user"]),
        "--default-character-set=utf8mb4",
    ]
    environment = os.environ.copy()
    environment["MYSQL_PWD"] = str(connection["password"])
    database_name = str(connection["database"])
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", database_name):
        raise ValueError("Database name must contain only letters, digits or underscores")
    sql = script_path.read_text(encoding="utf-8").replace("nayami_order_system", database_name)
    subprocess.run(command, input=sql.encode("utf-8"), env=environment, check=True)
