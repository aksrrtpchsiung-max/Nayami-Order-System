"""
文件名称：reset_demo_data.py
文件用途：显式确认后清理交易数据并重新写入演示基础数据
主要职责：保护性执行演示环境重置，保留数据库结构
所属业务模块：数据库运维
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from _runtime import PROJECT_ROOT, load_root_env, run_mysql_script

RESET_SQL = """
USE nayami_order_system;
SET FOREIGN_KEY_CHECKS = 0;
UPDATE store_products inventory
LEFT JOIN (
  SELECT store_product_id, SUM(change_quantity) AS net_sold
  FROM inventory_logs WHERE change_type IN ('confirm_deduct', 'refund_restore')
  GROUP BY store_product_id
) ledger ON ledger.store_product_id = inventory.id
SET inventory.current_stock = inventory.current_stock - COALESCE(ledger.net_sold, 0),
    inventory.reserved_stock = 0;
TRUNCATE TABLE operation_logs;
TRUNCATE TABLE payment_logs;
TRUNCATE TABLE order_status_logs;
TRUNCATE TABLE inventory_logs;
TRUNCATE TABLE coupon_claim_tasks;
TRUNCATE TABLE user_coupons;
TRUNCATE TABLE refund_records;
TRUNCATE TABLE payment_records;
TRUNCATE TABLE order_items;
TRUNCATE TABLE orders;
SET FOREIGN_KEY_CHECKS = 1;
"""


def main() -> None:
    load_root_env()
    if os.getenv("DEMO_MODE", "true").lower() != "true":
        raise SystemExit("Reset is only available in demo mode.")
    if os.getenv("CONFIRM_RESET") != "NAYAMI":
        raise SystemExit("Refusing reset. Set CONFIRM_RESET=NAYAMI to confirm demo transaction deletion.")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".sql", encoding="utf-8", delete=False) as sql_file:
            sql_file.write(RESET_SQL)
            temporary_path = Path(sql_file.name)
        run_mysql_script(temporary_path)
        for file_name in ("002_seed_demo_data.sql", "003_seed_demo_coupon.sql"):
            run_mysql_script(PROJECT_ROOT / "database/init" / file_name)
        print("Demo transaction data reset and seed data restored.")
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


if __name__ == "__main__":
    main()
