"""
文件名称：routes.py
文件用途：定义支付与退款仿真 API 路由
主要职责：提供支付单查询、统一仿真、重新支付、申请退款和完成仿真退款接口
所属业务模块：支付
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.payments.services import (
    get_payment_detail,
    request_refund,
    retry_payment,
    simulate_payment,
    simulate_payment_success,
    simulate_refund_success,
)

payments_bp = Blueprint("payments", __name__)


@payments_bp.get("/<int:payment_id>")
def payment_detail(payment_id: int):
    return success_response(get_payment_detail(get_current_user(), payment_id))


@payments_bp.post("/<int:payment_id>/simulate-success")
def simulate_success(payment_id: int):
    return success_response(simulate_payment_success(get_current_user(), payment_id, request.get_json(silent=True) or {}))


@payments_bp.post("/<int:payment_id>/simulate")
def simulate(payment_id: int):
    return success_response(simulate_payment(get_current_user(), payment_id, request.get_json(silent=True) or {}))


@payments_bp.post("/orders/<int:order_id>/retry")
def retry(order_id: int):
    return success_response(retry_payment(get_current_user(), order_id, request.get_json(silent=True) or {}), 201)


@payments_bp.post("/orders/<int:order_id>/refund")
def create_refund(order_id: int):
    return success_response(request_refund(get_current_user(), order_id, request.get_json(silent=True) or {}), 201)


@payments_bp.post("/refunds/<int:refund_id>/simulate-success")
def refund_success(refund_id: int):
    return success_response(simulate_refund_success(get_current_user(), refund_id))
