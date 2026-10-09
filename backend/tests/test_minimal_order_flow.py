"""
文件名称：test_minimal_order_flow.py
文件用途：测试最小交易闭环后端 API
主要职责：覆盖认证、菜单、下单、优惠券、支付重试、退款、库存、门店履约、多角色后台、国际化和越权拒绝
所属业务模块：后端测试
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import time, timedelta

import pytest

from app import create_app
from app.audit.models import OperationLog
from app.catalog.models import Product, ProductCategory, StoreProduct
from app.config import TestConfig
from app.coupons.models import CouponActivity, CouponClaimTask, UserCoupon
from app.extensions import db
from app.inventory.models import InventoryLog
from app.orders.models import Order
from app.orders.services import expire_pending_payment_orders
from app.payments.models import PaymentLog, PaymentRecord, RefundRecord
from app.stores.models import Store
from app.users.models import Role, User, UserRole, UserStoreBinding
from app.common.time_utils import current_time
from app.common.security import hash_password


@pytest.fixture()
def app():
    test_app = create_app(TestConfig)
    with test_app.app_context():
        db.create_all()
        seed_demo_data()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def seed_demo_data() -> None:
    customer = User(
        username="customer_demo",
        phone="18800000001",
        password_hash=hash_password("Nayami123!"),
        user_type="customer",
    )
    staff = User(
        username="store_staff_demo",
        phone="18800000002",
        password_hash=hash_password("Store123!"),
        user_type="staff",
    )
    manager = User(
        username="store_manager_demo",
        phone="18800000003",
        password_hash=hash_password("Manager123!"),
        user_type="staff",
    )
    brand_admin = User(
        username="brand_admin",
        phone="18800000004",
        password_hash=hash_password("Admin123!"),
        user_type="admin",
    )
    system_admin = User(
        username="system_admin",
        phone="18800000005",
        password_hash=hash_password("Admin123!"),
        user_type="admin",
    )
    role = Role(role_code="store_staff", role_name="门店员工")
    manager_role = Role(role_code="store_manager", role_name="门店经理")
    brand_role = Role(role_code="brand_admin", role_name="品牌管理员")
    system_role = Role(role_code="system_admin", role_name="系统管理员")
    store = Store(
        store_code="NYM-TEST-001",
        name_zh="奈亚米测试店",
        name_en="Nayami Test",
        address="测试路 1 号",
        phone="021-00000000",
        business_start_time=time(0, 0),
        business_end_time=time(23, 59),
        store_status="open",
        is_active=True,
    )
    second_store = Store(
        store_code="NYM-TEST-002",
        name_zh="奈亚米第二测试店",
        name_en="Nayami Test 2",
        address="测试路 2 号",
        phone="021-00000001",
        business_start_time=time(0, 0),
        business_end_time=time(23, 59),
        store_status="open",
        is_active=True,
    )
    category = ProductCategory(name_zh="主食", name_en="Mains", sort_order=1, is_active=True)
    product = Product(
        category=category,
        name_zh="招牌牛肉饭",
        name_en="Signature Beef Rice",
        description_zh="测试商品",
        description_en="Demo item",
        image_url="https://example.com/beef.jpg",
        base_price=38,
        menu_status="published",
        sort_order=1,
    )
    hidden_product = Product(
        category=category,
        name_zh="未发布商品",
        name_en="Draft Item",
        base_price=99,
        menu_status="draft",
        sort_order=2,
    )
    store_product = StoreProduct(store=store, product=product, is_available=True, current_stock=5, reserved_stock=0)
    hidden_store_product = StoreProduct(store=store, product=hidden_product, is_available=True, current_stock=5)
    second_store_product = StoreProduct(store=second_store, product=product, is_available=True, current_stock=5)
    db.session.add_all(
        [
            customer,
            staff,
            manager,
            brand_admin,
            system_admin,
            role,
            manager_role,
            brand_role,
            system_role,
            store,
            second_store,
            category,
            product,
            hidden_product,
            store_product,
            hidden_store_product,
            second_store_product,
        ]
    )
    db.session.flush()
    db.session.add(UserRole(user_id=staff.id, role_id=role.id))
    db.session.add(UserRole(user_id=manager.id, role_id=manager_role.id))
    db.session.add(UserRole(user_id=brand_admin.id, role_id=brand_role.id))
    db.session.add(UserRole(user_id=system_admin.id, role_id=system_role.id))
    db.session.add(UserStoreBinding(user_id=staff.id, store_id=store.id, binding_type="staff", is_active=True))
    db.session.add(UserStoreBinding(user_id=manager.id, store_id=store.id, binding_type="manager", is_active=True))
    db.session.commit()


def login(client, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.get_json()["data"]["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_customer(client, username: str = "fresh_customer", phone: str = "18800000009") -> dict:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "phone": phone, "password": "Fresh123!", "default_language": "zh-CN"},
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def create_paid_order(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    order_response = client.post(
        "/api/orders",
        headers=auth_headers(customer_token),
        json={
            "store_id": 1,
            "order_type": "pickup",
            "items": [{"store_product_id": 1, "quantity": 2}],
            "remark": "少盐",
            "tableware_count": 1,
        },
    )
    assert order_response.status_code == 201
    order_data = order_response.get_json()["data"]
    payment_id = order_data["payment"]["id"]
    payment_response = client.post(
        f"/api/payments/{payment_id}/simulate-success",
        headers=auth_headers(customer_token),
        json={"payment_method": "wechat", "idempotency_key": "test-payment-key"},
    )
    assert payment_response.status_code == 200
    return customer_token, payment_response.get_json()["data"]["order"]


def create_pending_order(client, customer_token: str, quantity: int = 1) -> dict:
    response = client.post(
        "/api/orders",
        headers=auth_headers(customer_token),
        json={"store_id": 1, "order_type": "pickup", "items": [{"store_product_id": 1, "quantity": quantity}]},
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def create_active_coupon(client, brand_token: str, total_stock: int = 3) -> dict:
    now = current_time()
    response = client.post(
        "/api/brand/coupons",
        headers=auth_headers(brand_token),
        json={
            "activity_name_zh": "测试立减券",
            "activity_name_en": "Test Discount Coupon",
            "start_at": (now - timedelta(minutes=5)).isoformat(),
            "end_at": (now + timedelta(days=1)).isoformat(),
            "total_stock": total_stock,
            "per_user_limit": 1,
            "discount_amount": "8.00",
            "minimum_order_amount": "30.00",
            "activity_status": "active",
            "store_ids": [1],
            "product_ids": [1],
        },
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_login_success_and_failure(client):
    assert client.post("/api/auth/login", json={"username": "customer_demo", "password": "Nayami123!"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "customer_demo", "password": "bad"}).status_code == 401


def test_customer_register_returns_token_and_customer_profile(client):
    result = register_customer(client)
    assert result["access_token"]
    assert result["user"]["username"] == "fresh_customer"
    assert result["user"]["phone"] == "18800000009"
    assert result["user"]["user_type"] == "customer"
    assert result["user"]["roles"] == []
    assert result["user"]["store_bindings"] == []


def test_customer_register_rejects_duplicate_username_and_phone(client):
    username_response = client.post(
        "/api/auth/register",
        json={"username": "customer_demo", "phone": "18800000009", "password": "Fresh123!"},
    )
    phone_response = client.post(
        "/api/auth/register",
        json={"username": "fresh_customer", "phone": "18800000001", "password": "Fresh123!"},
    )
    assert username_response.status_code == 400
    assert username_response.get_json()["error"]["code"] == "username_exists"
    assert phone_response.status_code == 400
    assert phone_response.get_json()["error"]["code"] == "phone_exists"


def test_registered_customer_can_create_order(client):
    result = register_customer(client)
    response = client.post(
        "/api/orders",
        headers=auth_headers(result["access_token"]),
        json={"store_id": 1, "order_type": "pickup", "items": [{"store_product_id": 1, "quantity": 1}]},
    )
    assert response.status_code == 201
    assert response.get_json()["data"]["user_id"] == result["user"]["id"]


def test_authenticated_session_cart_supports_upsert_update_delete_and_clear(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    headers = auth_headers(customer_token)

    client.post("/api/cart/items", headers=headers, json={"store_product_id": 1, "quantity": 1})
    upsert_response = client.post(
        "/api/cart/items",
        headers=headers,
        json={"store_product_id": 1, "quantity": 2},
    )
    assert upsert_response.get_json()["data"] == [{"store_product_id": 1, "quantity": 3}]

    update_response = client.patch(
        "/api/cart/items/1",
        headers=headers,
        json={"quantity": 2},
    )
    assert update_response.get_json()["data"][0]["quantity"] == 2
    assert client.delete("/api/cart/items/1", headers=headers).get_json()["data"] == []

    client.post("/api/cart/items", headers=headers, json={"store_product_id": 1})
    assert client.delete("/api/cart/items", headers=headers).get_json()["data"] == []


def test_menu_only_returns_published_available_products(client):
    response = client.get("/api/catalog/stores/1/menu")
    assert response.status_code == 200
    products = response.get_json()["data"]["categories"][0]["products"]
    assert len(products) == 1
    assert products[0]["name_zh"] == "招牌牛肉饭"


def test_create_order_reserves_stock(client):
    token = login(client, "customer_demo", "Nayami123!")
    response = client.post(
        "/api/orders",
        headers=auth_headers(token),
        json={"store_id": 1, "order_type": "pickup", "items": [{"store_product_id": 1, "quantity": 2}]},
    )
    assert response.status_code == 201
    store_product = db.session.get(StoreProduct, 1)
    assert store_product.current_stock == 5
    assert store_product.reserved_stock == 2


def test_order_creation_rejects_insufficient_stock(client):
    token = login(client, "customer_demo", "Nayami123!")
    response = client.post(
        "/api/orders",
        headers=auth_headers(token),
        json={"store_id": 1, "order_type": "pickup", "items": [{"store_product_id": 1, "quantity": 6}]},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "insufficient_stock"


def test_payment_success_confirms_stock_and_is_idempotent(client):
    token = login(client, "customer_demo", "Nayami123!")
    order_response = client.post(
        "/api/orders",
        headers=auth_headers(token),
        json={"store_id": 1, "order_type": "pickup", "items": [{"store_product_id": 1, "quantity": 2}]},
    )
    payment_id = order_response.get_json()["data"]["payment"]["id"]
    first_response = client.post(
        f"/api/payments/{payment_id}/simulate-success",
        headers=auth_headers(token),
        json={"idempotency_key": "same-key"},
    )
    second_response = client.post(f"/api/payments/{payment_id}/simulate-success", headers=auth_headers(token), json={})
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    store_product = db.session.get(StoreProduct, 1)
    assert store_product.current_stock == 3
    assert store_product.reserved_stock == 0
    assert first_response.get_json()["data"]["order"]["order_status"] == "paid"


def test_customer_cancel_pending_order_releases_reserved_stock(client):
    token = login(client, "customer_demo", "Nayami123!")
    order_data = create_pending_order(client, token, quantity=2)

    response = client.post(f"/api/orders/{order_data['id']}/cancel", headers=auth_headers(token))

    assert response.status_code == 200
    result = response.get_json()["data"]
    assert result["order_status"] == "canceled"
    assert result["payment"]["payment_status"] == "canceled"
    store_product = db.session.get(StoreProduct, 1)
    payment = db.session.get(PaymentRecord, order_data["payment"]["id"])
    assert store_product.current_stock == 5
    assert store_product.reserved_stock == 0
    assert payment.payment_status == "canceled"
    assert InventoryLog.query.filter_by(order_id=order_data["id"], change_type="release").count() == 1
    assert PaymentLog.query.filter_by(order_id=order_data["id"], event_type="callback").count() == 1


def test_customer_cannot_cancel_other_customer_order(client):
    owner_token = login(client, "customer_demo", "Nayami123!")
    order_data = create_pending_order(client, owner_token)
    other_customer = register_customer(client, username="other_customer", phone="18800000010")

    response = client.post(
        f"/api/orders/{order_data['id']}/cancel",
        headers=auth_headers(other_customer["access_token"]),
    )

    assert response.status_code == 403
    assert db.session.get(StoreProduct, 1).reserved_stock == 1
    assert db.session.get(Order, order_data["id"]).order_status == "pending_payment"


def test_paid_order_cannot_be_canceled_as_pending_payment(client):
    customer_token, paid_order = create_paid_order(client)

    response = client.post(f"/api/orders/{paid_order['id']}/cancel", headers=auth_headers(customer_token))

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "order_status_not_cancelable"
    store_product = db.session.get(StoreProduct, 1)
    assert store_product.current_stock == 3
    assert store_product.reserved_stock == 0


def test_payment_timeout_scan_cancels_order_and_releases_stock(client):
    token = login(client, "customer_demo", "Nayami123!")
    order_data = create_pending_order(client, token, quantity=2)
    order = db.session.get(Order, order_data["id"])
    order.payment_deadline = current_time() - timedelta(minutes=1)
    db.session.commit()

    result = expire_pending_payment_orders()

    assert result["expired_count"] == 1
    assert result["order_ids"] == [order_data["id"]]
    assert db.session.get(Order, order_data["id"]).order_status == "canceled"
    assert db.session.get(PaymentRecord, order_data["payment"]["id"]).payment_status == "expired"
    assert db.session.get(StoreProduct, 1).reserved_stock == 0
    assert InventoryLog.query.filter_by(order_id=order_data["id"], change_type="release").count() == 1
    assert PaymentLog.query.filter_by(order_id=order_data["id"], event_type="timeout").count() == 1


def test_expired_order_cannot_simulate_payment_success(client):
    token = login(client, "customer_demo", "Nayami123!")
    order_data = create_pending_order(client, token)
    order = db.session.get(Order, order_data["id"])
    order.payment_deadline = current_time() - timedelta(minutes=1)
    db.session.commit()

    response = client.post(
        f"/api/payments/{order_data['payment']['id']}/simulate-success",
        headers=auth_headers(token),
        json={"idempotency_key": "expired-payment-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "payment_expired"
    assert db.session.get(Order, order_data["id"]).order_status == "canceled"
    assert db.session.get(PaymentRecord, order_data["payment"]["id"]).payment_status == "expired"
    store_product = db.session.get(StoreProduct, 1)
    assert store_product.current_stock == 5
    assert store_product.reserved_stock == 0


def test_duplicate_cancel_and_scan_do_not_release_stock_twice(client):
    token = login(client, "customer_demo", "Nayami123!")
    canceled_order = create_pending_order(client, token, quantity=2)

    first_cancel_response = client.post(f"/api/orders/{canceled_order['id']}/cancel", headers=auth_headers(token))
    second_cancel_response = client.post(f"/api/orders/{canceled_order['id']}/cancel", headers=auth_headers(token))

    assert first_cancel_response.status_code == 200
    assert second_cancel_response.status_code == 400
    assert db.session.get(StoreProduct, 1).reserved_stock == 0
    assert InventoryLog.query.filter_by(order_id=canceled_order["id"], change_type="release").count() == 1

    expired_order = create_pending_order(client, token, quantity=1)
    order = db.session.get(Order, expired_order["id"])
    order.payment_deadline = current_time() - timedelta(minutes=1)
    db.session.commit()

    first_scan_result = expire_pending_payment_orders()
    second_scan_result = expire_pending_payment_orders()

    assert first_scan_result["expired_count"] == 1
    assert second_scan_result["expired_count"] == 0
    assert db.session.get(StoreProduct, 1).reserved_stock == 0
    assert InventoryLog.query.filter_by(order_id=expired_order["id"], change_type="release").count() == 1


def test_store_fulfillment_rejects_invalid_transition_and_allows_normal_flow(client):
    _, paid_order = create_paid_order(client)
    staff_token = login(client, "store_staff_demo", "Store123!")
    invalid_response = client.post(
        f"/api/store/orders/{paid_order['id']}/status",
        headers=auth_headers(staff_token),
        json={"target_status": "completed", "pickup_code": paid_order["pickup_code"]},
    )
    assert invalid_response.status_code == 400

    for target_status in ["accepted", "preparing", "ready"]:
        response = client.post(
            f"/api/store/orders/{paid_order['id']}/status",
            headers=auth_headers(staff_token),
            json={"target_status": target_status},
        )
        assert response.status_code == 200
    complete_response = client.post(
        f"/api/store/orders/{paid_order['id']}/status",
        headers=auth_headers(staff_token),
        json={"target_status": "completed", "pickup_code": paid_order["pickup_code"]},
    )
    assert complete_response.status_code == 200
    assert complete_response.get_json()["data"]["order_status"] == "completed"


def test_store_scope_rejects_unbound_customer(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    response = client.get("/api/store/orders?store_id=1", headers=auth_headers(customer_token))
    assert response.status_code == 403


def test_registered_customer_cannot_update_store_order_status(client):
    _, paid_order = create_paid_order(client)
    result = register_customer(client)
    response = client.post(
        f"/api/store/orders/{paid_order['id']}/status",
        headers=auth_headers(result["access_token"]),
        json={"target_status": "accepted"},
    )
    assert response.status_code == 403


def test_store_inventory_view_and_manager_update_permissions(client):
    staff_token = login(client, "store_staff_demo", "Store123!")
    manager_token = login(client, "store_manager_demo", "Manager123!")

    list_response = client.get("/api/store/inventory?store_id=1", headers=auth_headers(staff_token))
    staff_update_response = client.patch(
        "/api/store/inventory/1",
        headers=auth_headers(staff_token),
        json={"current_stock": 8},
    )
    manager_update_response = client.patch(
        "/api/store/inventory/1",
        headers=auth_headers(manager_token),
        json={"current_stock": 8, "is_sold_out": True},
    )

    assert list_response.status_code == 200
    assert staff_update_response.status_code == 403
    assert manager_update_response.status_code == 200
    result = manager_update_response.get_json()["data"]
    assert result["current_stock"] == 8
    assert result["is_sold_out"] is True


def test_store_inventory_update_rejects_stock_below_reserved(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    manager_token = login(client, "store_manager_demo", "Manager123!")
    order_response = client.post(
        "/api/orders",
        headers=auth_headers(customer_token),
        json={"store_id": 1, "order_type": "pickup", "items": [{"store_product_id": 1, "quantity": 2}]},
    )
    assert order_response.status_code == 201

    response = client.patch(
        "/api/store/inventory/1",
        headers=auth_headers(manager_token),
        json={"current_stock": 1},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "current_stock_less_than_reserved"


def test_store_status_update_controls_customer_ordering(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    manager_token = login(client, "store_manager_demo", "Manager123!")
    status_response = client.patch(
        "/api/store/status/1",
        headers=auth_headers(manager_token),
        json={"store_status": "temporarily_closed", "temporary_close_reason": "设备检修"},
    )
    order_response = client.post(
        "/api/orders",
        headers=auth_headers(customer_token),
        json={"store_id": 1, "order_type": "pickup", "items": [{"store_product_id": 1, "quantity": 1}]},
    )

    assert status_response.status_code == 200
    assert status_response.get_json()["data"]["store_status"] == "temporarily_closed"
    assert order_response.status_code == 400
    assert order_response.get_json()["error"]["code"] == "store_not_orderable"


def test_customer_cannot_access_store_workspace_apis(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    inventory_response = client.get("/api/store/inventory?store_id=1", headers=auth_headers(customer_token))
    report_response = client.get("/api/store/report?store_id=1", headers=auth_headers(customer_token))

    assert inventory_response.status_code == 403
    assert report_response.status_code == 403


def test_brand_admin_can_manage_brand_workspace_resources(client):
    brand_token = login(client, "brand_admin", "Admin123!")
    overview_response = client.get("/api/brand/overview", headers=auth_headers(brand_token))
    store_response = client.post(
        "/api/brand/stores",
        headers=auth_headers(brand_token),
        json={
            "store_code": "NYM-BRAND-003",
            "name_zh": "奈亚米品牌测试店",
            "name_en": "Nayami Brand Test",
            "address": "品牌路 3 号",
            "phone": "021-00000003",
            "business_start_time": "08:00",
            "business_end_time": "22:00",
            "store_status": "open",
            "is_active": True,
        },
    )
    category_response = client.post(
        "/api/brand/categories",
        headers=auth_headers(brand_token),
        json={"name_zh": "套餐", "name_en": "Combos", "sort_order": 9, "is_active": True},
    )
    category_id = category_response.get_json()["data"]["id"]
    product_response = client.post(
        "/api/brand/products",
        headers=auth_headers(brand_token),
        json={
            "category_id": category_id,
            "name_zh": "测试套餐",
            "name_en": "Test Combo",
            "base_price": "48.00",
            "menu_status": "published",
            "sort_order": 1,
        },
    )
    product_id = product_response.get_json()["data"]["id"]
    store_product_response = client.post(
        "/api/brand/store-products",
        headers=auth_headers(brand_token),
        json={"store_id": 1, "product_id": product_id, "current_stock": 20, "is_available": True, "is_sold_out": False},
    )
    coupon_response = client.post(
        "/api/brand/coupons",
        headers=auth_headers(brand_token),
        json={
            "activity_name_zh": "品牌满减券",
            "activity_name_en": "Brand Coupon",
            "start_at": "2026-05-26 10:00:00",
            "end_at": "2026-05-31 22:00:00",
            "total_stock": 100,
            "per_user_limit": 1,
            "discount_amount": "8.00",
            "minimum_order_amount": "30.00",
            "activity_status": "scheduled",
            "store_ids": [1],
            "product_ids": [product_id],
        },
    )
    report_response = client.get("/api/brand/report", headers=auth_headers(brand_token))

    assert overview_response.status_code == 200
    assert store_response.status_code == 201
    assert category_response.status_code == 201
    assert product_response.status_code == 201
    assert store_product_response.status_code == 201
    assert coupon_response.status_code == 201
    assert report_response.status_code == 200
    assert OperationLog.query.filter_by(operation_module="catalog").count() >= 2


def test_brand_admin_account_scope_rejects_system_admin_role(client):
    brand_token = login(client, "brand_admin", "Admin123!")
    create_staff_response = client.post(
        "/api/brand/accounts",
        headers=auth_headers(brand_token),
        json={
            "username": "brand_created_staff",
            "phone": "18800000021",
            "role_code": "store_staff",
            "store_id": 1,
            "default_language": "zh-CN",
        },
    )
    create_system_response = client.post(
        "/api/brand/accounts",
        headers=auth_headers(brand_token),
        json={
            "username": "brand_bad_system",
            "phone": "18800000022",
            "role_code": "system_admin",
            "default_language": "zh-CN",
        },
    )

    assert create_staff_response.status_code == 201
    assert create_staff_response.get_json()["data"]["temporary_password"] == "Admin123!"
    assert create_system_response.status_code == 403


def test_system_admin_can_manage_accounts_roles_config_and_logs(client):
    system_token = login(client, "system_admin", "Admin123!")
    roles_response = client.get("/api/system/roles", headers=auth_headers(system_token))
    config_response = client.get("/api/system/config", headers=auth_headers(system_token))
    missing_store_response = client.post(
        "/api/system/accounts",
        headers=auth_headers(system_token),
        json={
            "username": "missing_store_staff",
            "phone": "18800000031",
            "role_code": "store_staff",
            "default_language": "zh-CN",
        },
    )
    create_admin_response = client.post(
        "/api/system/accounts",
        headers=auth_headers(system_token),
        json={
            "username": "created_brand_admin",
            "phone": "18800000032",
            "role_code": "brand_admin",
            "default_language": "zh-CN",
        },
    )
    account_id = create_admin_response.get_json()["data"]["account"]["id"]
    disable_response = client.patch(
        f"/api/system/accounts/{account_id}",
        headers=auth_headers(system_token),
        json={"role_code": "brand_admin", "is_active": False},
    )
    logs_response = client.get("/api/audit/logs", headers=auth_headers(system_token))

    assert roles_response.status_code == 200
    assert len(roles_response.get_json()["data"]) == 4
    assert config_response.status_code == 200
    assert missing_store_response.status_code == 400
    assert missing_store_response.get_json()["error"]["code"] == "store_binding_required"
    assert create_admin_response.status_code == 201
    assert disable_response.status_code == 200
    assert disable_response.get_json()["data"]["is_active"] is False
    assert logs_response.status_code == 200
    assert any(log["operation_module"] == "account" for log in logs_response.get_json()["data"])


def test_customer_and_store_staff_cannot_access_brand_or_system_admin_apis(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    staff_token = login(client, "store_staff_demo", "Store123!")

    customer_brand_response = client.get("/api/brand/overview", headers=auth_headers(customer_token))
    staff_system_response = client.get("/api/system/accounts", headers=auth_headers(staff_token))
    staff_audit_response = client.get("/api/audit/logs", headers=auth_headers(staff_token))

    assert customer_brand_response.status_code == 403
    assert staff_system_response.status_code == 403
    assert staff_audit_response.status_code == 403


def test_verification_phone_login_refresh_and_customer_order_list(client):
    verification_response = client.post(
        "/api/auth/verification-code",
        json={"phone": "18800000041"},
    )
    assert verification_response.status_code == 201
    assert verification_response.get_json()["data"]["verification_code"] == "123456"

    register_response = client.post(
        "/api/auth/register",
        json={
            "username": "phone_login_customer",
            "phone": "18800000041",
            "verification_code": "123456",
            "password": "Phone123!",
            "confirm_password": "Phone123!",
            "default_language": "en-US",
        },
    )
    assert register_response.status_code == 201
    register_data = register_response.get_json()["data"]
    assert register_data["refresh_token"]

    phone_login_response = client.post(
        "/api/auth/login",
        json={"username": "18800000041", "password": "Phone123!"},
    )
    assert phone_login_response.status_code == 200
    login_data = phone_login_response.get_json()["data"]
    refresh_response = client.post(
        "/api/auth/refresh",
        headers=auth_headers(login_data["refresh_token"]),
    )
    assert refresh_response.status_code == 200
    assert refresh_response.get_json()["data"]["access_token"]

    create_pending_order(client, login_data["access_token"])
    order_list_response = client.get(
        "/api/orders",
        headers=auth_headers(login_data["access_token"]),
    )
    assert order_list_response.status_code == 200
    assert len(order_list_response.get_json()["data"]) == 1
    assert order_list_response.get_json()["data"][0]["user_id"] == register_data["user"]["id"]


def test_coupon_claim_order_discount_payment_and_reconciliation(client):
    brand_token = login(client, "brand_admin", "Admin123!")
    customer_token = login(client, "customer_demo", "Nayami123!")
    activity = create_active_coupon(client, brand_token)

    warmup_response = client.post(
        f"/api/coupons/activities/{activity['id']}/warmup",
        headers=auth_headers(brand_token),
    )
    assert warmup_response.status_code == 200
    assert warmup_response.get_json()["data"]["remaining_stock"] == 3

    claim_response = client.post(
        f"/api/coupons/activities/{activity['id']}/claim",
        headers=auth_headers(customer_token),
        json={"request_id": "coupon-e2e-claim"},
    )
    assert claim_response.status_code == 202
    assert claim_response.get_json()["data"]["task"]["task_status"] == "succeeded"

    duplicate_response = client.post(
        f"/api/coupons/activities/{activity['id']}/claim",
        headers=auth_headers(customer_token),
        json={"request_id": "coupon-e2e-duplicate"},
    )
    assert duplicate_response.status_code == 400
    assert duplicate_response.get_json()["error"]["code"] in {
        "coupon_already_claimed",
        "coupon_already_available",
    }

    my_coupon_response = client.get("/api/coupons/me", headers=auth_headers(customer_token))
    user_coupon = my_coupon_response.get_json()["data"][0]
    eligible_response = client.get(
        "/api/coupons/eligible?store_id=1&items_amount=38.00&product_ids=1",
        headers=auth_headers(customer_token),
    )
    assert eligible_response.status_code == 200
    assert eligible_response.get_json()["data"][0]["id"] == user_coupon["id"]

    order_response = client.post(
        "/api/orders",
        headers=auth_headers(customer_token),
        json={
            "store_id": 1,
            "order_type": "pickup",
            "items": [{"store_product_id": 1, "quantity": 1}],
            "user_coupon_id": user_coupon["id"],
        },
    )
    assert order_response.status_code == 201
    order_data = order_response.get_json()["data"]
    assert order_data["items_amount"] == "38.00"
    assert order_data["discount_amount"] == "8.00"
    assert order_data["payable_amount"] == "30.00"

    payment_response = client.post(
        f"/api/payments/{order_data['payment']['id']}/simulate",
        headers=auth_headers(customer_token),
        json={"payment_method": "alipay", "result": "success", "idempotency_key": "coupon-payment"},
    )
    assert payment_response.status_code == 200
    assert payment_response.get_json()["data"]["order"]["order_status"] == "paid"
    assert db.session.get(UserCoupon, user_coupon["id"]).coupon_status == "used"

    reconcile_response = client.post(
        f"/api/coupons/activities/{activity['id']}/reconcile",
        headers=auth_headers(brand_token),
    )
    metrics = reconcile_response.get_json()["data"]
    assert reconcile_response.status_code == 200
    assert metrics["redis_success_count"] == 1
    assert metrics["database_count"] == 1
    assert metrics["difference_count"] == 0
    assert metrics["used_count"] == 1
    assert CouponClaimTask.query.filter_by(activity_id=activity["id"], task_status="succeeded").count() == 1


def test_coupon_requires_warmup_and_enforces_order_scope(client):
    brand_token = login(client, "brand_admin", "Admin123!")
    customer_token = login(client, "customer_demo", "Nayami123!")
    activity = create_active_coupon(client, brand_token)

    claim_response = client.post(
        f"/api/coupons/activities/{activity['id']}/claim",
        headers=auth_headers(customer_token),
    )
    assert claim_response.status_code == 400
    assert claim_response.get_json()["error"]["code"] == "coupon_not_warmed"

    client.post(
        f"/api/coupons/activities/{activity['id']}/warmup",
        headers=auth_headers(brand_token),
    )
    client.post(
        f"/api/coupons/activities/{activity['id']}/claim",
        headers=auth_headers(customer_token),
        json={"request_id": "scope-check"},
    )
    user_coupon = UserCoupon.query.filter_by(activity_id=activity["id"]).one()

    second_store_product_id = StoreProduct.query.filter_by(store_id=2, product_id=1).one().id
    wrong_store_response = client.post(
        "/api/orders",
        headers=auth_headers(customer_token),
        json={
            "store_id": 2,
            "items": [{"store_product_id": second_store_product_id, "quantity": 1}],
            "user_coupon_id": user_coupon.id,
        },
    )
    assert wrong_store_response.status_code == 400
    assert wrong_store_response.get_json()["error"]["code"] == "coupon_not_eligible"
    assert db.session.get(UserCoupon, user_coupon.id).coupon_status == "available"


def test_failed_payment_releases_only_its_stock_and_retry_can_succeed(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    first_order = create_pending_order(client, customer_token)
    second_order = create_pending_order(client, customer_token)
    assert db.session.get(StoreProduct, 1).reserved_stock == 2

    failure_response = client.post(
        f"/api/payments/{first_order['payment']['id']}/simulate",
        headers=auth_headers(customer_token),
        json={"payment_method": "wechat", "result": "failure", "idempotency_key": "failed-attempt"},
    )
    assert failure_response.status_code == 200
    assert failure_response.get_json()["data"]["payment_status"] == "failed"
    assert db.session.get(StoreProduct, 1).reserved_stock == 1

    retry_response = client.post(
        f"/api/payments/orders/{first_order['id']}/retry",
        headers=auth_headers(customer_token),
        json={"payment_method": "alipay"},
    )
    assert retry_response.status_code == 201
    retry_data = retry_response.get_json()["data"]
    assert retry_data["id"] != first_order["payment"]["id"]
    assert db.session.get(StoreProduct, 1).reserved_stock == 2

    success_response = client.post(
        f"/api/payments/{retry_data['id']}/simulate",
        headers=auth_headers(customer_token),
        json={"payment_method": "alipay", "result": "success", "idempotency_key": "retry-success"},
    )
    assert success_response.status_code == 200
    assert success_response.get_json()["data"]["order"]["order_status"] == "paid"
    store_product = db.session.get(StoreProduct, 1)
    assert store_product.current_stock == 4
    assert store_product.reserved_stock == 1

    cancel_second_response = client.post(
        f"/api/orders/{second_order['id']}/cancel",
        headers=auth_headers(customer_token),
    )
    assert cancel_second_response.status_code == 200
    assert db.session.get(StoreProduct, 1).reserved_stock == 0


def test_bank_card_masking_and_failure_does_not_store_sensitive_values(client):
    customer_token = login(client, "customer_demo", "Nayami123!")
    order_data = create_pending_order(client, customer_token)
    card_number = "4000000000000002"
    response = client.post(
        f"/api/payments/{order_data['payment']['id']}/simulate",
        headers=auth_headers(customer_token),
        json={
            "payment_method": "bank_card",
            "result": "success",
            "card_number": card_number,
            "cardholder_name": "Demo Customer",
            "expiry": "12/30",
            "cvv": "123",
            "billing_country": "CN",
            "billing_address": "Shanghai",
            "postal_code": "200000",
        },
    )
    assert response.status_code == 200
    payment_data = response.get_json()["data"]
    assert payment_data["payment_status"] == "failed"
    assert payment_data["card_brand"] == "visa"
    assert payment_data["masked_card_no"] == "4000 **** **** 0002"
    assert card_number not in str(payment_data)
    payment = db.session.get(PaymentRecord, order_data["payment"]["id"])
    assert payment.masked_card_no == "4000 **** **** 0002"
    assert card_number not in str(payment.__dict__)


def test_refund_success_is_idempotent_and_restores_inventory(client):
    customer_token, paid_order = create_paid_order(client)
    assert db.session.get(StoreProduct, 1).current_stock == 3

    refund_response = client.post(
        f"/api/payments/orders/{paid_order['id']}/refund",
        headers=auth_headers(customer_token),
        json={"reason": "顾客行程变更"},
    )
    assert refund_response.status_code == 201
    refund_data = refund_response.get_json()["data"]
    assert refund_data["refund_status"] == "pending"
    assert refund_data["order"]["order_status"] == "refund_pending"

    refund_success_response = client.post(
        f"/api/payments/refunds/{refund_data['id']}/simulate-success",
        headers=auth_headers(customer_token),
    )
    assert refund_success_response.status_code == 200
    assert refund_success_response.get_json()["data"]["order"]["order_status"] == "refunded"
    assert db.session.get(StoreProduct, 1).current_stock == 5

    duplicate_response = client.post(
        f"/api/payments/refunds/{refund_data['id']}/simulate-success",
        headers=auth_headers(customer_token),
    )
    assert duplicate_response.status_code == 200
    assert db.session.get(StoreProduct, 1).current_stock == 5
    assert RefundRecord.query.filter_by(order_id=paid_order["id"]).count() == 1


def test_i18n_and_permission_metadata_endpoints(client):
    language_response = client.get("/api/i18n/languages")
    english_status_response = client.get("/api/i18n/statuses?language=en-US")
    staff_token = login(client, "store_staff_demo", "Store123!")
    permission_response = client.get("/api/permissions/me", headers=auth_headers(staff_token))

    assert language_response.status_code == 200
    assert {item["code"] for item in language_response.get_json()["data"]} == {"zh-CN", "en-US"}
    assert english_status_response.status_code == 200
    assert english_status_response.get_json()["data"]["order"]["paid"] == "Paid"
    assert permission_response.status_code == 200
    permission_data = permission_response.get_json()["data"]
    assert permission_data["role_codes"] == ["store_staff"]
    assert permission_data["store_ids"] == [1]


def test_health_and_openapi_discovery(client):
    health_response = client.get("/api/health")
    openapi_response = client.get("/api/openapi.json")

    assert health_response.status_code == 200
    assert health_response.get_json()["data"]["status"] == "ok"
    assert openapi_response.status_code == 200
    specification = openapi_response.get_json()
    assert specification["openapi"] == "3.0.3"
    assert "/api/orders" in specification["paths"]
    assert {"get", "post"}.issubset(specification["paths"]["/api/orders"])

    protected_response = client.get("/api/orders")
    assert protected_response.status_code == 401
    assert protected_response.get_json()["error"]["code"] == "authentication_required"
