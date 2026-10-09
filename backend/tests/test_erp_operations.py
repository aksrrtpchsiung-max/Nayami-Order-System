"""
文件名称：test_erp_operations.py
文件用途：传统 ERP 菜单、营销和品牌运营回归测试
主要职责：验证发布版本隔离、归档、分类禁用、异步权益展示、并发落库幂等、活动冻结与正确报表口径
所属业务模块：后端测试
创建时间：2026-09-08 17:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update

from app.brand.services import get_brand_overview, get_brand_report, update_coupon_activity, update_product, upsert_store_product
from app.catalog.models import Product, ProductCategory, StoreProduct
from app.catalog.services import list_store_menu
from app.common.errors import BusinessError, ForbiddenError
from app.common.time_utils import current_time
from app.coupons.models import CouponActivity, CouponActivityProduct, CouponActivityStore, CouponClaimTask, UserCoupon
from app.coupons.redis_store import get_coupon_redis_store
from app.coupons.services import claim_coupon, get_claim_task, list_public_activities, list_user_coupons, process_claim_task, retry_claim_task, synchronize_activity_statuses
from app.extensions import db
from app.inventory.models import InventoryLog
from app.orders.models import Order, OrderItem
from app.payments.models import PaymentRecord
from app.stores.models import Store
from app.users.models import User
from test_minimal_order_flow import app, client, auth_headers, login


def admin():
    return User.query.filter_by(username="brand_admin").one()


def customer():
    return User.query.filter_by(username="customer_demo").one()


def activity(status="active", future=False):
    now = current_time()
    row = CouponActivity(activity_name_zh="回归券", activity_name_en="Regression coupon",
        start_at=now + timedelta(hours=1) if future else now - timedelta(hours=1),
        end_at=now + timedelta(days=2), total_stock=3, per_user_limit=1,
        discount_amount=5, minimum_order_amount=10, activity_status=status)
    db.session.add(row)
    db.session.flush()
    db.session.add_all([CouponActivityStore(activity_id=row.id, store_id=1), CouponActivityProduct(activity_id=row.id, product_id=1)])
    db.session.commit()
    return row


def test_published_edits_keep_menu_and_price_until_publish(app):
    changed = update_product(admin(), 1, {"name_zh": "新品名", "base_price": "49.00", "menu_status": "published"})
    assert changed["menu_status"] == "draft_changes"
    assert changed["base_price"] == "49.00"
    assert changed["published_content"]["base_price"] == "38.00"
    menu_item = list_store_menu(1)["categories"][0]["products"][0]
    assert menu_item["name_zh"] == "招牌牛肉饭"
    assert menu_item["base_price"] == "38.00"
    published = update_product(admin(), 1, {"menu_status": "published"})
    assert published["pending_changes"] is None
    assert list_store_menu(1)["categories"][0]["products"][0]["base_price"] == "49.00"


def test_archiving_removes_pending_version_and_cannot_restore(app):
    update_product(admin(), 1, {"name_zh": "待发布"})
    update_product(admin(), 1, {"menu_status": "archived"})
    assert list_store_menu(1)["categories"] == []
    assert db.session.get(Product, 1).pending_changes is None
    with pytest.raises(BusinessError):
        update_product(admin(), 1, {"menu_status": "published"})


def test_disabled_category_hidden_and_closed_store_cannot_add(app):
    category = db.session.get(ProductCategory, 1)
    category.is_active = False
    db.session.commit()
    assert list_store_menu(1)["categories"] == []
    category.is_active = True
    db.session.get(Store, 1).store_status = "closed"
    db.session.commit()
    menu = list_store_menu(1)
    item = menu["categories"][0]["products"][0]
    assert menu["store"]["can_order"] is False
    assert item["can_add_to_cart"] is False
    assert not {"current_stock", "reserved_stock", "available_stock"}.intersection(item)


@pytest.mark.parametrize("status", ["draft", "archived"])
def test_cannot_sell_unpublished_products(app, status):
    db.session.get(Product, 2).menu_status = status
    db.session.commit()
    with pytest.raises(BusinessError):
        upsert_store_product(admin(), {"store_id": 2, "product_id": 2, "is_available": True})
    db.session.rollback()


def test_brand_stock_update_preserves_reservations_and_records_trace(app):
    store_product = db.session.get(StoreProduct, 1)
    store_product.reserved_stock = 2
    db.session.commit()
    with pytest.raises(BusinessError):
        upsert_store_product(admin(), {"store_id": 1, "product_id": 1, "current_stock": 1})
    db.session.rollback()
    upsert_store_product(admin(), {"store_id": 1, "product_id": 1, "current_stock": 8, "reason": "盘点更正"})
    log = InventoryLog.query.filter_by(store_product_id=1).one()
    assert (log.before_current_stock, log.after_current_stock, log.before_reserved_stock, log.remark) == (5, 8, 2, "盘点更正")


@pytest.mark.parametrize("payload", [{"base_price": None}, {"base_price": "NaN"}, {"base_price": "Infinity"}, {"sort_order": 1.9}, {"category_id": True}, {"image_url": "javascript:alert(1)"}])
def test_invalid_product_payloads_are_business_errors(app, payload):
    with pytest.raises(BusinessError):
        update_product(admin(), 1, payload)


def test_scheduled_activity_claimable_at_start_and_scan_keeps_pause(app):
    campaign = activity("scheduled")
    get_coupon_redis_store().warmup(campaign.id, 3)
    public = list_public_activities()[0]
    assert public["effective_status"] == "active"
    assert claim_coupon(customer(), campaign.id, {"request_id": "schedule-test"})["result"] == "succeeded"
    paused = activity("paused")
    result = synchronize_activity_statuses()
    db.session.expire_all()
    assert result["started_count"] == 1
    assert db.session.get(CouponActivity, campaign.id).activity_status == "active"
    assert db.session.get(CouponActivity, paused.id).activity_status == "paused"


@pytest.mark.parametrize("payload", [{"store_ids": [2]}, {"product_ids": []}, {"discount_amount": 100}, {"minimum_order_amount": 100}, {"total_stock": 100}, {"activity_status": "draft"}])
def test_started_coupon_terms_cannot_change(app, payload):
    campaign = activity()
    with pytest.raises(BusinessError):
        update_coupon_activity(admin(), campaign.id, payload)


def test_started_coupon_allows_equal_form_submission_and_pause(app):
    campaign = activity()
    result = update_coupon_activity(admin(), campaign.id, {"discount_amount": "5.00", "store_ids": [1], "product_ids": [1], "activity_status": "paused"})
    assert result["activity_status"] == "paused"


def test_prestart_claim_task_also_protects_coupon_terms(app):
    campaign = activity("scheduled", future=True)
    db.session.add(CouponClaimTask(activity_id=campaign.id, user_id=customer().id, redis_success_time=current_time(), task_status="pending"))
    db.session.commit()
    with pytest.raises(BusinessError):
        update_coupon_activity(admin(), campaign.id, {"store_ids": [2]})


def test_pending_and_failed_claims_appear_once_and_do_not_leak_errors(app):
    campaign = activity()
    task = CouponClaimTask(activity_id=campaign.id, user_id=customer().id, redis_success_time=current_time(), task_status="pending", retry_count=0)
    db.session.add(task)
    db.session.commit()
    row = list_user_coupons(customer())[0]
    assert row["id"] is None and row["task_id"] == task.id and row["coupon_status"] == "syncing"
    assert row["scope_stores"][0]["id"] == 1
    task.task_status = "failed"
    task.last_error = "mysql password secret"
    db.session.commit()
    row = list_user_coupons(customer(), "abnormal")[0]
    assert "last_error" not in row
    assert get_claim_task(admin(), task.id)["last_error"] == "mysql password secret"
    with pytest.raises(ForbiddenError):
        get_claim_task(customer(), task.id)
    process_claim_task(task.id)
    rows = list_user_coupons(customer())
    assert len(rows) == 1 and rows[0]["id"] is not None and rows[0]["coupon_status"] == "available"


def test_dead_task_needs_explicit_manual_retry(app):
    campaign = activity()
    task = CouponClaimTask(activity_id=campaign.id, user_id=customer().id, redis_success_time=current_time(), task_status="dead", retry_count=3)
    db.session.add(task)
    db.session.commit()
    assert process_claim_task(task.id)["task_status"] == "dead"
    assert UserCoupon.query.count() == 0
    assert retry_claim_task(admin(), task.id)["task_status"] == "succeeded"


def test_claim_task_refreshes_cached_pending_state_before_retrying(app):
    campaign = activity()
    task = CouponClaimTask(activity_id=campaign.id, user_id=customer().id,
        redis_success_time=current_time(), task_status="pending", retry_count=0)
    coupon = UserCoupon(activity_id=campaign.id, user_id=customer().id, discount_amount=5,
        minimum_order_amount=10, coupon_status="expired", claimed_at=current_time(), expired_at=campaign.end_at)
    db.session.add_all([task, coupon])
    db.session.commit()
    task_id, coupon_id = task.id, coupon.id
    assert task.task_status == "pending"
    db.session.execute(update(CouponClaimTask).where(CouponClaimTask.id == task_id).values(
        task_status="succeeded", user_coupon_id=coupon_id).execution_options(synchronize_session=False))
    assert task.task_status == "pending"
    result = process_claim_task(task_id)
    assert result["task_status"] == "succeeded"
    assert result["retry_count"] == 0
    assert result["user_coupon_id"] == coupon_id
    assert UserCoupon.query.count() == 1
    assert db.session.get(UserCoupon, coupon_id).coupon_status == "expired"


def test_claim_failure_cannot_overwrite_another_executor_success(app, monkeypatch):
    campaign = activity()
    task = CouponClaimTask(activity_id=campaign.id, user_id=customer().id,
        redis_success_time=current_time(), task_status="pending", retry_count=0)
    db.session.add(task)
    db.session.commit()
    task_id, campaign_id, user_id, expires = task.id, campaign.id, task.user_id, campaign.end_at
    original_flush, original_rollback = db.session.flush, db.session.rollback
    failed_once = False

    def failing_flush(*args, **kwargs):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("injected database failure before concurrent completion")
        return original_flush(*args, **kwargs)

    def rollback_after_other_executor_finishes():
        original_rollback()
        coupon = UserCoupon(activity_id=campaign_id, user_id=user_id, discount_amount=5,
            minimum_order_amount=10, coupon_status="available", claimed_at=current_time(), expired_at=expires)
        db.session.add(coupon)
        original_flush()
        db.session.execute(update(CouponClaimTask).where(CouponClaimTask.id == task_id).values(
            task_status="succeeded", user_coupon_id=coupon.id).execution_options(synchronize_session=False))
        db.session.commit()

    monkeypatch.setattr(db.session, "flush", failing_flush)
    monkeypatch.setattr(db.session, "rollback", rollback_after_other_executor_finishes)
    result = process_claim_task(task_id, raise_on_error=True)
    assert result["task_status"] == "succeeded"
    assert result["retry_count"] == 0
    assert result["last_error"] is None
    assert UserCoupon.query.count() == 1


def test_brand_reports_count_all_orders_and_deduplicate_payment_attempts(app, client):
    now = current_time()
    for index, state in enumerate(("pending_payment", "canceled", "completed", "refunded")):
        order = Order(order_no=f"REPORT-{index}", user_id=customer().id, store_id=1, order_type="pickup",
            order_status=state, items_amount=38, payable_amount=38, payment_deadline=now + timedelta(minutes=15),
            paid_at=now if state in ("completed", "refunded") else None)
        db.session.add(order)
        db.session.flush()
        if state in ("completed", "refunded"):
            for attempt in range(2):
                db.session.add(PaymentRecord(order_id=order.id, payment_no=f"PAY-{index}-{attempt}", payment_amount=38,
                    payment_method="wechat", payment_status="failed" if attempt == 0 else "succeeded"))
        if state == "completed":
            for item_index, title in enumerate(("旧名称", "新名称")):
                db.session.add(OrderItem(order_id=order.id, product_id=1, store_product_id=1,
                    product_name_zh=title, product_name_en=title, unit_price=19, quantity=1, subtotal_amount=19))
    db.session.commit()
    report = get_brand_report(admin())
    assert report["today"]["order_count"] == 4
    for period in ("today", "last_7_days", "last_30_days"):
        assert report[period]["canceled_order_count"] == 2
    assert report["metric_definitions"]["canceled_order_count"] == "orders_created_in_period_currently_canceled_or_refunded"
    assert report["today"]["revenue"] == "38.00"
    assert report["last_30_days"]["order_count"] == 4
    assert report["payment_success_rate"] == "100.0%"
    assert len(report["popular_products"]) == 1
    assert report["popular_products"][0]["sold_quantity"] == 2
    overview = get_brand_overview(admin())
    assert overview["today_order_count"] == 4
    assert overview["open_store_count"] == 2
    response = client.get("/api/brand/report", headers=auth_headers(login(client, "brand_admin", "Admin123!")))
    assert response.status_code == 200
    for period in ("today", "last_7_days", "last_30_days"):
        assert response.get_json()["data"][period]["canceled_order_count"] == 2


def test_revenue_uses_payment_date_independently_of_order_date(app):
    now = current_time()
    order = Order(order_no="CROSS-DAY", user_id=customer().id, store_id=1, order_type="pickup",
        order_status="paid", items_amount=38, payable_amount=38, created_at=now-timedelta(days=1),
        paid_at=now, payment_deadline=now+timedelta(minutes=15))
    db.session.add(order)
    db.session.commit()
    report = get_brand_report(admin())
    assert report["today"]["order_count"] == 0
    assert report["today"]["revenue"] == "38.00"
    assert report["store_rankings"][0]["revenue"] == "38.00"


def test_successful_claim_remains_idempotent_after_activity_ends(app):
    campaign = activity()
    get_coupon_redis_store().warmup(campaign.id, 3)
    first = claim_coupon(customer(), campaign.id, {"request_id": "success-before-end"})
    campaign.activity_status = "ended"
    db.session.commit()
    repeated = claim_coupon(customer(), campaign.id, {"request_id": "success-before-end"})
    assert first["task"]["id"] == repeated["task"]["id"]
    assert UserCoupon.query.filter_by(activity_id=campaign.id).count() == 1
    assert get_coupon_redis_store().metrics(campaign.id)["remaining_stock"] == 2


def test_even_demo_warmup_cannot_erase_existing_claims(app):
    from app.coupons.services import warmup_activity
    campaign = activity()
    get_coupon_redis_store().warmup(campaign.id, 3)
    claim_coupon(customer(), campaign.id, {"request_id": "preserved-claim"})
    with pytest.raises(BusinessError):
        warmup_activity(admin(), campaign.id, force=True)


@pytest.mark.parametrize("separate_executor", [False, True])
def test_demo_history_is_repeatable_without_stock_or_log_duplication(app, monkeypatch, separate_executor):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from seed_demo_history import seed_demo_history
    from app.payments.models import PaymentLog, RefundRecord
    if separate_executor:
        app.config["COUPON_TASK_EAGER"] = False

        def dispatch_in_another_session(task_id):
            with app.app_context():
                process_claim_task(task_id)

        monkeypatch.setattr("app.coupons.services._dispatch_claim_task", dispatch_in_another_session)
    first = seed_demo_history()
    assert first["created_order_count"] == 8
    for state, order_id in first["order_ids"].items():
        assert db.session.get(Order, order_id).order_status == state
    assert {db.session.get(UserCoupon, coupon_id).coupon_status for coupon_id in first["coupon_ids"].values()} == {"available", "used", "expired"}
    store_product = db.session.get(StoreProduct, 1)
    before = (store_product.current_stock, store_product.reserved_stock, InventoryLog.query.count(),
        PaymentRecord.query.count(), PaymentLog.query.count(), RefundRecord.query.count(), CouponClaimTask.query.count())
    second = seed_demo_history()
    assert second["created_order_count"] == 0
    assert second["order_ids"] == first["order_ids"]
    after = (store_product.current_stock, store_product.reserved_stock, InventoryLog.query.count(),
        PaymentRecord.query.count(), PaymentLog.query.count(), RefundRecord.query.count(), CouponClaimTask.query.count())
    assert before == after
    assert {task.task_status for task in CouponClaimTask.query.all()} == {"succeeded"}
    assert all(task.retry_count == 0 and task.last_error is None for task in CouponClaimTask.query.all())


def test_demo_history_disabled_outside_demo_mode(app):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from seed_demo_history import seed_demo_history
    app.config["DEMO_MODE"] = False
    with pytest.raises(BusinessError):
        seed_demo_history()
    assert Order.query.count() == 0


def test_warmup_recovers_missing_redis_stock_without_reissuing_claimed_stock(app):
    from app.coupons.services import warmup_activity
    campaign = activity()
    store = get_coupon_redis_store()
    store.warmup(campaign.id, 3)
    claim_coupon(customer(), campaign.id, {"request_id": "before-redis-recovery"})
    store.stocks.pop(campaign.id)
    store.users.pop(campaign.id)
    assert warmup_activity(admin(), campaign.id)["remaining_stock"] == 2
    assert store.metrics(campaign.id)["success_count"] == 1
    assert store.claim(campaign.id, customer().id, "after-redis-recovery")["code"] == 2
