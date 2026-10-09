"""
文件名称：services.py
文件用途：提供后端支持语言和核心状态文案映射
主要职责：集中返回订单、支付、优惠券和门店状态的中英文文案
所属业务模块：国际化
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

SUPPORTED_LANGUAGES = [
    {"code": "zh-CN", "name": "简体中文"},
    {"code": "en-US", "name": "English"},
]

STATUS_TEXTS = {
    "order": {
        "pending_payment": ("待支付", "Pending Payment"),
        "paid": ("已支付", "Paid"),
        "accepted": ("已接单", "Accepted"),
        "preparing": ("制作中", "Preparing"),
        "ready": ("待取餐", "Ready for Pickup"),
        "completed": ("已完成", "Completed"),
        "canceled": ("已取消", "Canceled"),
        "refund_pending": ("退款处理中", "Refund Pending"),
        "refunded": ("已退款", "Refunded"),
    },
    "payment": {
        "pending": ("待支付", "Pending"),
        "processing": ("支付处理中", "Processing"),
        "succeeded": ("支付成功", "Succeeded"),
        "failed": ("支付失败", "Failed"),
        "canceled": ("已取消", "Canceled"),
        "expired": ("已超时", "Expired"),
    },
    "coupon": {
        "syncing": ("同步中", "Syncing"),
        "available": ("可使用", "Available"),
        "used": ("已使用", "Used"),
        "expired": ("已过期", "Expired"),
        "abnormal": ("状态异常", "Abnormal"),
    },
    "store": {
        "open": ("营业中", "Open"),
        "closed": ("已关闭", "Closed"),
        "temporarily_closed": ("临时关闭", "Temporarily Closed"),
    },
}


def list_languages() -> list[dict]:
    return SUPPORTED_LANGUAGES


def get_status_texts(language: str) -> dict:
    index = 1 if language == "en-US" else 0
    return {
        domain: {status: translations[index] for status, translations in values.items()}
        for domain, values in STATUS_TEXTS.items()
    }
