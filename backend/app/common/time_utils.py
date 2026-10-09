"""
文件名称：time_utils.py
文件用途：处理订单系统时间相关逻辑
主要职责：提供当前时间、支付截止时间和门店营业时间判断
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime, timedelta


def current_time() -> datetime:
    return datetime.now()


def build_payment_deadline(minutes: int) -> datetime:
    return current_time() + timedelta(minutes=minutes)


def is_time_in_business_range(now_time, start_time, end_time) -> bool:
    if start_time <= end_time:
        return start_time <= now_time <= end_time
    return now_time >= start_time or now_time <= end_time
