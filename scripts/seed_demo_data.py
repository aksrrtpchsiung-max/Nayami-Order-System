"""
文件名称：seed_demo_data.py
文件用途：写入可重复执行的奈亚米演示基础数据
主要职责：创建演示账号、三家门店、菜单、库存和优惠券活动
所属业务模块：数据库运维
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from _runtime import PROJECT_ROOT, run_mysql_script


def main() -> None:
    for file_name in ("002_seed_demo_data.sql", "003_seed_demo_coupon.sql"):
        run_mysql_script(PROJECT_ROOT / "database/init" / file_name)
    print("Demo data seeded.")


if __name__ == "__main__":
    main()
