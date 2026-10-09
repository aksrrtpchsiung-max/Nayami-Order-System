"""
文件名称：check_demo_environment.py
文件用途：检查演示所需 API、MySQL 与 Redis 是否可用
主要职责：执行只读连通性检查并返回机器可读汇总
所属业务模块：部署验收
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import json
import os
from urllib.request import urlopen

from _runtime import database_parts, load_root_env


def main() -> None:
    import pymysql
    import redis

    load_root_env()
    results: dict[str, dict] = {}
    api_host = os.getenv("BACKEND_HOST", "127.0.0.1")
    if api_host in {"0.0.0.0", "::"}:
        api_host = "127.0.0.1"
    api_url = os.getenv("NAYAMI_HEALTH_URL", f"http://{api_host}:{os.getenv('BACKEND_PORT', '5000')}/api/health")
    try:
        with urlopen(api_url, timeout=5) as response:
            results["api"] = {"ok": response.status == 200, "status": response.status}
    except Exception as exc:
        results["api"] = {"ok": False, "error": str(exc)}

    try:
        connection = database_parts()
        database = pymysql.connect(
            host=str(connection["host"]),
            port=int(connection["port"]),
            user=str(connection["user"]),
            password=str(connection["password"]),
            database=str(connection["database"]),
            connect_timeout=5,
        )
        with database.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stores")
            store_count = int(cursor.fetchone()[0])
        database.close()
        results["mysql"] = {"ok": True, "store_count": store_count}
    except Exception as exc:
        results["mysql"] = {"ok": False, "error": str(exc)}

    try:
        redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
        results["redis"] = {"ok": bool(redis_client.ping())}
    except Exception as exc:
        results["redis"] = {"ok": False, "error": str(exc)}

    print(json.dumps(results, ensure_ascii=False, indent=2))
    if not all(item.get("ok") for item in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
