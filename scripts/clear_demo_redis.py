"""
文件名称：clear_demo_redis.py
文件用途：清理演示环境中由本系统创建的短期 Redis 数据
主要职责：仅删除 coupon:*、cart:* 与 auth:sms:* 命名空间，不执行 FLUSHDB
所属业务模块：Redis 运维
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import os

from _runtime import load_root_env


def main() -> None:
    import redis

    load_root_env()
    client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    deleted_count = 0
    for pattern in ("coupon:*", "cart:*", "auth:sms:*"):
        batch: list[bytes] = []
        for key in client.scan_iter(match=pattern, count=500):
            batch.append(key)
            if len(batch) >= 500:
                deleted_count += client.delete(*batch)
                batch.clear()
        if batch:
            deleted_count += client.delete(*batch)
    print(f"Deleted {deleted_count} Nayami demo Redis keys.")


if __name__ == "__main__":
    main()
