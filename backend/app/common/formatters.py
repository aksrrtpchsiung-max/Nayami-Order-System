"""
文件名称：formatters.py
文件用途：提供 API 输出格式化工具
主要职责：统一金额、时间和布尔值输出，避免 Decimal 直接进入 JSON
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations


def format_money(value) -> str:
    return f"{value:.2f}" if value is not None else "0.00"


def format_datetime(value) -> str | None:
    return value.isoformat(sep=" ", timespec="seconds") if value else None


def format_time(value) -> str | None:
    return value.strftime("%H:%M") if value else None
