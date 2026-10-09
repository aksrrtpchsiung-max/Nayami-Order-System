"""
文件名称：test_erp_commerce.py
文件用途：传统 ERP 交易、门店工作台和经营报表的回归验证
主要职责：验证数值边界、敏感支付权限、终态履约、每日取餐码约束、日志和报表统计
所属业务模块：后端测试
创建时间：2026-09-08 17:30
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.catalog.models import Product, ProductCategory, StoreProduct
from app.common.time_utils import current_time
from app.extensions import db
from app.orders.models import Order
from app.payments.models import PaymentRecord
from app.payments.services import _generate_pickup_code
from test_minimal_order_flow import app, client, login, auth_headers, create_pending_order, create_paid_order


@pytest.mark.parametrize("field,value", [("quantity", 1.9), ("quantity", True), ("quantity", "1"), ("quantity", 1.0),
    ("tableware_count", 1.9), ("tableware_count", True), ("tableware_count", -1), ("tableware_count", 11)])
def test_order_rejects_non_integer_and_out_of_range_values(client, field, value):
    token = login(client, "customer_demo", "Nayami123!")
    payload = {"store_id": 1, "items": [{"store_product_id": 1, "quantity": 1}], "tableware_count": 1}
    if field == "quantity":
        payload["items"][0]["quantity"] = value
    else:
        payload[field] = value
    response = client.post("/api/orders", headers=auth_headers(token), json=payload)
    assert response.status_code == 400
    assert Order.query.count() == 0
    assert db.session.get(StoreProduct, 1).reserved_stock == 0


def test_staff_cannot_pay_retry_or_read_another_store_payment(client):
    customer = login(client, "customer_demo", "Nayami123!")
    staff = login(client, "store_staff_demo", "Store123!")
    order = create_pending_order(client, customer)
    payment_id = order["payment"]["id"]
    assert client.post(f"/api/payments/{payment_id}/simulate-success", headers=auth_headers(staff), json={}).status_code == 403
    assert client.post(f"/api/payments/orders/{order['id']}/retry", headers=auth_headers(staff), json={}).status_code == 403
    order = client.post("/api/orders", headers=auth_headers(customer), json={"store_id": 2,
        "items": [{"store_product_id": StoreProduct.query.filter_by(store_id=2).first().id, "quantity": 1}]}).get_json()["data"]
    assert client.get(f"/api/payments/{order['payment']['id']}", headers=auth_headers(staff)).status_code == 403


def test_terminated_order_without_target_cannot_be_reopened(client):
    customer = login(client, "customer_demo", "Nayami123!")
    staff = login(client, "store_staff_demo", "Store123!")
    order = create_pending_order(client, customer)
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=auth_headers(customer)).status_code == 200
    response = client.post(f"/api/store/orders/{order['id']}/status", headers=auth_headers(staff), json={})
    assert response.status_code == 400
    assert db.session.get(Order, order["id"]).order_status == "canceled"


def test_manager_preparing_refund_requires_explicit_reason(client):
    customer, order = create_paid_order(client)
    manager = login(client, "store_manager_demo", "Manager123!")
    for target in ("accepted", "preparing"):
        assert client.post(f"/api/store/orders/{order['id']}/status", headers=auth_headers(manager), json={"target_status": target}).status_code == 200
    response = client.post(f"/api/payments/orders/{order['id']}/refund", headers=auth_headers(manager), json={})
    assert response.status_code == 400
    response = client.post(f"/api/payments/orders/{order['id']}/refund", headers=auth_headers(manager), json={"reason": "设备故障无法继续制作"})
    assert response.status_code == 201
    assert response.get_json()["data"]["order"]["cancel_reason"] == "设备故障无法继续制作"


def test_order_details_preserve_status_payment_history_and_mask_phone(client):
    customer, order = create_paid_order(client)
    details = client.get(f"/api/orders/{order['id']}", headers=auth_headers(customer)).get_json()["data"]
    assert [entry["to_status"] for entry in details["status_logs"]] == ["pending_payment", "paid"]
    assert [entry["event_type"] for entry in details["payment_logs"]] == ["created", "callback"]
    assert details["payments"][0]["payment_status"] == "succeeded"
    assert details["pickup_date"] == current_time().date().isoformat()
    assert details["customer_phone_masked"] == "188****0001"


def test_store_orders_default_today_with_history_search_and_priority(client):
    customer, paid = create_paid_order(client)
    staff = login(client, "store_staff_demo", "Store123!")
    older = create_pending_order(client, customer)
    pending = create_pending_order(client, customer)
    db_order = db.session.get(Order, older["id"])
    db_order.created_at = current_time() - timedelta(days=1)
    db_order.order_status = "completed"
    db.session.commit()
    response = client.get("/api/store/orders?store_id=1", headers=auth_headers(staff))
    assert [order["id"] for order in response.get_json()["data"]] == [paid["id"]]
    history = client.get("/api/store/orders?store_id=1&view=history&days=7", headers=auth_headers(staff)).get_json()["data"]
    assert [order["id"] for order in history] == [older["id"]]
    found = client.get(f"/api/store/orders?store_id=1&search={paid['pickup_code']}", headers=auth_headers(staff)).get_json()["data"]
    assert [order["id"] for order in found] == [paid["id"]]
    assert client.get("/api/store/orders?store_id=2", headers=auth_headers(staff)).status_code == 403


def test_pickup_codes_reuse_other_dates_and_enforce_unique_store_date(client):
    customer, paid = create_paid_order(client)
    old_order = db.session.get(Order, paid["id"])
    old_order.pickup_date = current_time().date() - timedelta(days=1)
    old_order.pickup_code = "A002"
    db.session.commit()
    pending = create_pending_order(client, customer)
    current_order = db.session.get(Order, pending["id"])
    current_order.pickup_date = current_time().date()
    current_order.pickup_code = _generate_pickup_code(current_order)
    assert current_order.pickup_code == "A002"
    db.session.commit()
    old_order.pickup_date = current_order.pickup_date
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_inventory_adjustment_records_reason_and_enforces_read_permissions(client):
    manager = login(client, "store_manager_demo", "Manager123!")
    staff = login(client, "store_staff_demo", "Store123!")
    result = client.patch("/api/store/inventory/1", headers=auth_headers(manager), json={"current_stock": 7, "reason": "午市补货"})
    assert result.status_code == 200
    records = client.get("/api/store/inventory/logs?store_id=1&change_type=manual_adjust", headers=auth_headers(manager)).get_json()["data"]
    assert len(records) == 1
    assert (records[0]["before_current_stock"], records[0]["after_current_stock"], records[0]["remark"]) == (5, 7, "午市补货")
    assert client.get("/api/store/inventory/logs?store_id=1", headers=auth_headers(staff)).status_code == 403
    assert client.get("/api/store/inventory/logs?store_id=2", headers=auth_headers(manager)).status_code == 403
    assert client.patch("/api/store/inventory/1", headers=auth_headers(manager), json={"current_stock": 1.9}).status_code == 400
    assert client.patch("/api/store/inventory/1", headers=auth_headers(manager), json={"is_available": "false"}).status_code == 400


def test_store_reports_count_all_orders_and_use_payment_time(client):
    customer, paid = create_paid_order(client)
    manager = login(client, "store_manager_demo", "Manager123!")
    staff = login(client, "store_staff_demo", "Store123!")
    create_pending_order(client, customer)
    canceled = create_pending_order(client, customer)
    assert client.post(f"/api/orders/{canceled['id']}/cancel", headers=auth_headers(customer)).status_code == 200
    paid_order = db.session.get(Order, paid["id"])
    paid_order.created_at = current_time() - timedelta(days=10)
    db.session.commit()
    assert client.get("/api/store/report?store_id=1", headers=auth_headers(staff)).status_code == 403
    assert client.get("/api/store/overview?store_id=1", headers=auth_headers(staff)).status_code == 200
    report = client.get("/api/store/report?store_id=1", headers=auth_headers(manager)).get_json()["data"]
    assert report["today"]["order_count"] == 2
    assert report["today"]["canceled_order_count"] == 1
    assert report["today"]["revenue"] == "76.00"
    assert report["last_30_days"]["order_count"] == 3
    assert report["popular_products"][0]["sold_quantity"] == 2


def test_payment_retry_rejects_disabled_category(client):
    customer = login(client, "customer_demo", "Nayami123!")
    order = create_pending_order(client, customer)
    assert client.post(f"/api/payments/{order['payment']['id']}/simulate", headers=auth_headers(customer), json={"result": "failure"}).status_code == 200
    db.session.get(ProductCategory, 1).is_active = False
    db.session.commit()
    assert client.post(f"/api/payments/orders/{order['id']}/retry", headers=auth_headers(customer), json={}).status_code == 400
    assert db.session.get(StoreProduct, 1).reserved_stock == 0


def test_order_uses_live_published_values_while_product_has_pending_changes(client):
    customer = login(client, "customer_demo", "Nayami123!")
    db.session.get(Product, 1).menu_status = "draft_changes"
    db.session.commit()
    order = create_pending_order(client, customer)
    assert order["items"][0]["unit_price"] == "38.00"


def test_non_card_failure_discards_injected_card_fields(client):
    token = login(client, "customer_demo", "Nayami123!")
    order = create_pending_order(client, token)
    response = client.post(f"/api/payments/{order['payment']['id']}/simulate", headers=auth_headers(token),
        json={"payment_method": "wechat", "result": "failure", "masked_card_no": "4111111111111111", "card_brand": "visa"})
    assert response.status_code == 200
    payment = db.session.get(PaymentRecord, order["payment"]["id"])
    assert payment.masked_card_no is None
    assert payment.card_brand is None


def test_refund_request_is_idempotent_after_status_changed(client):
    token, order = create_paid_order(client)
    first = client.post(f"/api/payments/orders/{order['id']}/refund", headers=auth_headers(token), json={"reason": "取消"})
    repeated = client.post(f"/api/payments/orders/{order['id']}/refund", headers=auth_headers(token), json={"reason": "取消"})
    assert first.status_code == repeated.status_code == 201
    assert first.get_json()["data"]["id"] == repeated.get_json()["data"]["id"]
