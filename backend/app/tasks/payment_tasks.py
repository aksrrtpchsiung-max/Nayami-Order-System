"""
文件名称：payment_tasks.py
文件用途：提供支付超时扫描任务入口
主要职责：调用订单服务扫描超时未支付订单，自动取消订单、关闭支付单并释放预占库存
所属业务模块：异步任务
创建时间：2026-06-12 16:31
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from app.orders.services import expire_pending_payment_orders
from celery_runtime import celery_app


def run_payment_timeout_scan(batch_size: int = 100) -> dict:
    """
    函数名称：run_payment_timeout_scan
    函数用途：执行一次支付超时订单扫描
    参数说明：batch_size 为本次最多处理的待支付超时订单数量
    返回值说明：返回取消订单数量和订单 ID 列表
    核心逻辑：委托订单服务筛选 pending_payment 且 payment_deadline 已过期的订单并完成取消闭环
    异常或失败情况：数据库异常由调用方或 Flask 统一错误处理负责回滚和记录
    相关业务规则：由 Celery Beat 每分钟调度，重复扫描不得重复释放库存
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    return expire_pending_payment_orders(batch_size=batch_size)


@celery_app.task(name="nayami.payment_timeout_scan")
def payment_timeout_scan_task(batch_size: int = 100) -> dict:
    """Celery Beat 调用的支付超时扫描任务。"""
    return run_payment_timeout_scan(batch_size)
