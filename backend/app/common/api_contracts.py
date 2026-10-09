"""
文件名称：api_contracts.py
文件用途：声明 ERP API 的请求、响应和查询参数契约
主要职责：为交易、后台维护、审计和异步任务提供可复用 OpenAPI schema
所属业务模块：接口文档
创建时间：2026-09-08 17:26
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def obj(properties, required=()):
    result = {"type": "object", "properties": properties, "additionalProperties": True}
    if required:
        result["required"] = list(required)
    return result


def array(schema):
    return {"type": "array", "items": ref(schema) if isinstance(schema, str) else schema}


def text(maximum=None, values=None):
    result = {"type": "string"}
    if maximum:
        result["maxLength"] = maximum
    if values:
        result["enum"] = values.split()
    return result


ID = {"type": "integer", "minimum": 1}
COUNT = {"type": "integer", "minimum": 0, "maximum": 2147483647}
BOOL = {"type": "boolean"}
DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", "description": "Asia/Singapore local time, YYYY-MM-DD HH:mm:ss (no timezone suffix)", "example": "2026-09-08 17:30:00"}
DATE_INPUT = {"type": "string", "description": "ISO 8601 date/time; offset-aware values are converted to Asia/Singapore; local values are accepted", "example": "2026-09-08T09:30:00+08:00"}
SIGNED_INTEGER = {"type": "integer", "minimum": -2147483648, "maximum": 2147483647}
ACTIVITY_STATUS = text(values="draft scheduled active paused ended sold_out")
INVENTORY_CHANGE = text(values="reserve confirm_deduct release manual_adjust refund_restore")
MONEY = {"type": "string", "pattern": r"^\d+\.\d{2}$", "example": "38.00"}
MONEY_INPUT = {"oneOf": [MONEY, {"type": "number", "minimum": 0, "maximum": 99999999.99}]}
LANG = text(values="zh-CN en-US")
METHOD = text(values="wechat alipay bank_card")
ORDER_STATUS = text(values="pending_payment paid accepted preparing ready completed canceled refund_pending refunded")
PAYMENT_STATUS = text(values="pending processing succeeded failed canceled expired")
ROLE = text(values="store_staff store_manager brand_admin system_admin")
SCHEMAS = {
    "Error": obj({"success": {"type": "boolean", "enum": [False]}, "error": obj({"code": text(), "message": text()}, ["code", "message"])}, ["success", "error"]),
    "LoginRequest": obj({"username": text(64), "password": text(128)}, ["username", "password"]),
    "RegisterRequest": obj({"username": text(64), "phone": text(32), "password": text(128), "confirm_password": text(128), "verification_code": text(6), "default_language": LANG}, ["username", "phone", "password", "confirm_password", "verification_code"]),
    "VerificationRequest": obj({"phone": text(32)}, ["phone"]),
    "Verification": obj({"phone": text(), "expires_in_seconds": COUNT, "cooldown_seconds": COUNT, "verification_code": text(6)}),
    "Role": obj({"id": ID, "role_code": ROLE, "role_name": text(), "description": text(), "permission_codes": array(text())}),
    "StoreBinding": obj({"store_id": ID, "store_name": text(), "store_name_zh": text(), "store_name_en": text(), "binding_type": text(), "is_active": BOOL}),
    "User": obj({"id": ID, "username": text(), "phone": text(), "user_type": text(values="customer staff admin"), "default_language": LANG, "roles": array("Role"), "store_bindings": array("StoreBinding"), "last_login_at": DATE}),
    "Auth": obj({"access_token": text(), "refresh_token": text(), "user": ref("User")}),
    "Refresh": obj({"access_token": text(), "user": ref("User")}),
    "Logout": obj({"logged_out": BOOL}),
    "Store": obj({"id": ID, "store_code": text(64), "name_zh": text(128), "name_en": text(128), "address": text(255), "phone": text(32), "business_start_time": text(), "business_end_time": text(), "store_status": text(values="open closed temporarily_closed"), "temporary_close_reason": text(255), "is_active": BOOL, "can_order": BOOL}),
    "Category": obj({"id": ID, "name_zh": text(128), "name_en": text(128), "sort_order": COUNT, "is_active": BOOL}),
    "Product": obj({"id": ID, "category_id": ID, "name_zh": text(128), "name_en": text(128), "description_zh": text(2000), "description_en": text(2000), "image_url": text(500), "base_price": MONEY_INPUT, "menu_status": text(values="draft published draft_changes archived"), "sort_order": COUNT, "pending_changes": {"type": "object", "nullable": True}, "published_content": {"type": "object"}, "missing_translations": array(text())}),
    "StoreProduct": obj({"id": ID, "store_id": ID, "product_id": ID, "current_stock": COUNT, "reserved_stock": COUNT, "available_stock": COUNT, "is_available": BOOL, "is_sold_out": BOOL, "reason": text(500)}),
    "MenuItem": obj({"store_product_id": ID, "product_id": ID, "category_id": ID, "name_zh": text(), "name_en": text(), "description_zh": text(), "description_en": text(), "base_price": MONEY, "image_url": text(), "is_available": BOOL, "is_sold_out": BOOL, "can_add_to_cart": BOOL}),
    "Menu": obj({"store": ref("Store"), "categories": array(obj({"id": ID, "name_zh": text(), "name_en": text(), "products": array("MenuItem")}))}),
    "CartItem": obj({"store_product_id": ID, "quantity": {"type": "integer", "minimum": 1}}, ["store_product_id", "quantity"]),
    "CartQuantity": obj({"quantity": {**COUNT, "minimum": 1}}, ["quantity"]),
    "OrderRequest": obj({"store_id": ID, "order_type": text(values="dine_in pickup"), "items": {**array("CartItem"), "minItems": 1, "maxItems": 100}, "user_coupon_id": {**ID, "nullable": True}, "remark": text(100), "tableware_count": {"type": "integer", "minimum": 0, "maximum": 10}}, ["store_id", "items"]),
    "OrderItem": obj({"id": ID, "product_id": ID, "store_product_id": ID, "product_name_zh": text(), "product_name_en": text(), "unit_price": MONEY, "quantity": COUNT, "subtotal_amount": MONEY}),
    "StatusLog": obj({"id": ID, "from_status": text(), "to_status": text(), "trigger_type": text(), "event_type": text(), "operator_id": ID, "reason": text(), "created_at": DATE}),
    "PaymentSummary": obj({"id": ID, "payment_no": text(), "payment_method": METHOD, "payment_amount": MONEY, "payment_status": PAYMENT_STATUS, "transaction_no": text(), "card_brand": text(), "masked_card_no": text(), "failure_reason": text(), "created_at": DATE, "paid_at": DATE}),
    "RefundSummary": obj({"id": ID, "refund_no": text(), "refund_status": text(values="pending succeeded failed"), "refund_amount": MONEY, "refund_reason": text(), "simulated_refund_no": text(), "refunded_at": DATE}),
    "Order": obj({"id": ID, "order_no": text(), "store_id": ID, "store_name_zh": text(), "store_name_en": text(), "store_address": text(), "store_phone": text(), "customer_name": text(), "customer_phone_masked": text(), "order_type": text(values="dine_in pickup"), "order_status": ORDER_STATUS, "items_amount": MONEY, "discount_amount": MONEY, "payable_amount": MONEY, "user_coupon_id": ID, "pickup_code": text(), "pickup_date": {"type": "string", "format": "date"}, "remark": text(), "cancel_reason": text(), "tableware_count": COUNT, "created_at": DATE, "updated_at": DATE, "paid_at": DATE, "completed_at": DATE, "payment_deadline": DATE, "items": array("OrderItem"), "payment": ref("PaymentSummary"), "payments": array("PaymentSummary"), "refund": ref("RefundSummary"), "status_logs": array("StatusLog"), "payment_logs": array("StatusLog")}),
    "Payment": {"allOf": [ref("PaymentSummary"), obj({"order": ref("Order")})]},
    "Refund": {"allOf": [ref("RefundSummary"), obj({"order_id": ID, "payment_id": ID, "order": ref("Order")})]},
    "SimulateRequest": obj({"payment_method": METHOD, "result": text(values="success failure failed cancel canceled timeout expired"), "idempotency_key": text(128), "card_number": {**text(), "writeOnly": True, "description": "12–19 digits; spaces and separators are accepted and removed"}, "cardholder_name": text(128), "expiry": text(7), "cvv": {**text(4), "writeOnly": True}, "phone": text(32), "verification_code": {**text(6), "writeOnly": True}, "payment_password": {**text(6), "writeOnly": True}, "billing_country": text(128), "billing_address": text(255), "postal_code": text(32)}),
    "RetryRequest": obj({"payment_method": {**METHOD, "default": "wechat"}}),
    "RefundRequest": obj({"reason": text(255)}),
    "StatusRequest": obj({"target_status": text(values="accepted preparing ready completed"), "pickup_code": text(4)}, ["target_status"]),
    "Activity": obj({"id": ID, "activity_name_zh": text(128), "activity_name_en": text(128), "description_zh": text(), "description_en": text(), "start_at": DATE, "end_at": DATE, "total_stock": COUNT, "per_user_limit": {"type": "integer", "enum": [1]}, "discount_amount": MONEY_INPUT, "minimum_order_amount": MONEY_INPUT, "activity_status": ACTIVITY_STATUS, "effective_status": text(), "store_ids": array(ID), "product_ids": array(ID)}),
    "UserCoupon": obj({"id": {**ID, "nullable": True}, "task_id": ID, "task_status": text(), "activity_id": ID, "activity_name_zh": text(), "activity_name_en": text(), "discount_amount": MONEY, "minimum_order_amount": MONEY, "coupon_status": text(values="syncing available used expired abnormal"), "claimed_at": DATE, "expired_at": DATE, "used_at": DATE, "used_order_id": ID, "store_ids": array(ID), "product_ids": array(ID), "scope_stores": array("ScopeItem"), "scope_products": array("ScopeItem")}),
    "ClaimTask": obj({"id": ID, "activity_id": ID, "user_id": ID, "user_coupon_id": ID, "task_status": text(values="pending processing succeeded failed dead"), "redis_success_time": DATE, "retry_count": COUNT, "last_error": text(), "next_retry_at": DATE}),
    "ClaimRequest": obj({"request_id": {**text(128), "description": "Optional client idempotency key; the server generates a key when omitted"}}),
    "ClaimResult": obj({"result": text(), "message_code": text(), "activity_id": ID, "remaining_stock": COUNT, "task": ref("ClaimTask")}),
    "CouponMetrics": obj({"activity_id": ID, "remaining_stock": COUNT, "claimed_count": COUNT, "used_count": COUNT, "usage_rate": text(), "redis_success_count": COUNT, "database_coupon_count": COUNT, "missing_user_ids": array(ID), "database_only_user_ids": array(ID), "task_counts": obj({key: COUNT for key in ("pending", "processing", "succeeded", "failed", "dead")})}),
    "AccountRequest": obj({"username": text(64), "phone": text(32), "password": {**text(128), "writeOnly": True}, "role_code": ROLE, "store_id": ID, "default_language": LANG, "is_active": BOOL}),
    "Account": {"allOf": [ref("User"), obj({"is_active": BOOL, "created_at": DATE, "updated_at": DATE})]},
    "AccountMutation": obj({"account": ref("Account"), "temporary_password": text()}),
    "SystemConfig": obj({"demo_mode": BOOL, "default_language": LANG, "payment_description": text(500), "supported_languages": array(LANG), "currency": text(), "payment_methods": array(METHOD), "payment_mode": text(), "payment_timeout_minutes": COUNT, "coupon_max_retries": COUNT, "config_storage": text()}),
    "ConfigRequest": {**obj({"demo_mode": BOOL, "default_language": LANG, "payment_description": text(500)}), "additionalProperties": False, "minProperties": 1},
    "AuditLog": obj({"id": ID, "operator_id": ID, "operator_role_code": ROLE, "operation_module": text(), "operation_type": text(), "target_id": ID, "store_id": ID, "before_snapshot": {"type": "object", "nullable": True}, "after_snapshot": {"type": "object", "nullable": True}, "operation_result": text(values="success failed rejected"), "failure_reason": text(), "ip_address": text(), "created_at": DATE}),
    "InventoryLog": obj({"id": ID, "store_id": ID, "store_product_id": ID, "change_type": INVENTORY_CHANGE, "change_quantity": {"type": "integer"}, "before_current_stock": COUNT, "after_current_stock": COUNT, "before_reserved_stock": COUNT, "after_reserved_stock": COUNT, "operator_id": ID, "remark": text(), "created_at": DATE}),
    "ReportSummary": obj({"order_count": COUNT, "completed_order_count": COUNT, "canceled_order_count": COUNT, "coupon_used_count": COUNT, "revenue": MONEY}),
    "PopularProduct": obj({"product_id": ID, "product_name_zh": text(), "product_name_en": text(), "sold_quantity": COUNT, "sales_amount": MONEY}),
    "Report": obj({"store_id": ID, "today": ref("ReportSummary"), "last_7_days": ref("ReportSummary"), "last_30_days": ref("ReportSummary"), "popular_products": array("PopularProduct"), "store_rankings": array(obj({"store_id": ID, "store_name_zh": text(), "store_name_en": text(), "order_count": COUNT, "revenue": MONEY})), "coupon_summary": obj({"claimed_count": COUNT, "used_count": COUNT, "usage_rate": text()}), "payment_success_rate": text(), "metric_definitions": {"type": "object", "additionalProperties": text()}}),
    "Overview": obj({key: COUNT for key in ("store_id", "store_count", "active_store_count", "open_store_count", "closed_store_count", "temporarily_closed_store_count", "published_product_count", "active_coupon_count", "today_order_count", "active_order_count", "paid_order_count", "preparing_order_count", "ready_order_count", "low_stock_count", "pending_order_count", "coupon_sync_pending_count", "coupon_sync_failed_count", "coupon_sync_dead_count")}),
}
SCHEMAS["Overview"]["properties"]["today_revenue"] = MONEY

# endpoint -> (请求 schema、返回 schema、成功状态)；None 表示没有请求体。
CONTRACTS = {
    "auth.login": ("LoginRequest", "Auth", 200), "auth.register": ("RegisterRequest", "Auth", 201),
    "auth.verification_code": ("VerificationRequest", "Verification", 201), "auth.refresh": (None, "Refresh", 200),
    "auth.logout": (None, "Logout", 200), "auth.me": (None, "User", 200),
    "stores.list_stores": (None, array("Store"), 200), "catalog.store_menu": (None, "Menu", 200),
    "orders.create_customer_order": ("OrderRequest", "Order", 201), "orders.order_detail": (None, "Order", 200),
    "orders.customer_orders": (None, array("Order"), 200), "orders.cancel_order": (None, "Order", 200),
    "orders.store_orders": (None, array("Order"), 200), "orders.update_status": ("StatusRequest", "Order", 200),
    "payments.payment_detail": (None, "Payment", 200), "payments.simulate": ("SimulateRequest", "Payment", 200),
    "payments.simulate_success": ("SimulateRequest", "Payment", 200), "payments.retry": ("RetryRequest", "Payment", 201),
    "payments.create_refund": ("RefundRequest", "Refund", 201), "payments.refund_success": (None, "Refund", 200),
    "cart.list_cart_items": (None, array("CartItem"), 200), "cart.add_cart_item": ("CartItem", array("CartItem"), 201),
    "cart.update_cart_item": ("CartQuantity", array("CartItem"), 200), "cart.delete_cart_item": (None, array("CartItem"), 200), "cart.clear_cart_items": (None, array("CartItem"), 200),
    "coupons.activities": (None, array("Activity"), 200), "coupons.claim": ("ClaimRequest", "ClaimResult", 202),
    "coupons.my_coupons": (None, array("UserCoupon"), 200), "coupons.eligible_coupons": (None, array("UserCoupon"), 200),
    "coupons.warmup": (obj({"force": BOOL}), "CouponMetrics", 200), "coupons.activity_tasks": (None, array("ClaimTask"), 200),
    "coupons.claim_task_detail": (None, "ClaimTask", 200), "coupons.retry_task": (None, "ClaimTask", 200), "coupons.reconcile": (None, "CouponMetrics", 200),
    "inventory.store_inventory": (None, array("StoreProduct"), 200), "inventory.update_inventory_item": ("StoreProduct", "StoreProduct", 200), "inventory.inventory_logs": (None, array("InventoryLog"), 200),
    "store_admin.update_store_status": (obj({"store_status": text(values="open closed temporarily_closed"), "temporary_close_reason": text(255)}, ["store_status"]), "Store", 200),
    "reports.store_overview": (None, "Overview", 200), "reports.store_report": (None, "Report", 200),
    "system.roles": (None, array("Role"), 200), "system.system_config": (None, "SystemConfig", 200), "system.edit_system_config": ("ConfigRequest", "SystemConfig", 200),
    "audit.operation_logs": (None, array("AuditLog"), 200), "audit.operation_log_detail": (None, "AuditLog", 200),
    "brand.overview": (None, "Overview", 200), "brand.report": (None, "Report", 200),
    "brand.stores": (None, array("Store"), 200), "brand.create_store": ("Store", "Store", 201), "brand.update_store": ("Store", "Store", 200),
    "brand.categories": (None, array("Category"), 200), "brand.create_product_category": ("Category", "Category", 201), "brand.update_product_category": ("Category", "Category", 200),
    "brand.products": (None, array("Product"), 200), "brand.create_brand_product": ("Product", "Product", 201), "brand.update_brand_product": ("Product", "Product", 200),
    "brand.store_products": (None, array("StoreProduct"), 200), "brand.create_store_product": ("StoreProduct", "StoreProduct", 201), "brand.update_store_product": ("StoreProduct", "StoreProduct", 200),
    "brand.coupons": (None, array("Activity"), 200), "brand.create_coupon": ("Activity", "Activity", 201), "brand.update_coupon": ("Activity", "Activity", 200), "brand.coupon_metrics": (None, "CouponMetrics", 200),
}
for prefix, names in {"system": ("accounts", "create_backend_account", "update_backend_account", "reset_backend_account_password"), "brand": ("brand_accounts", "create_brand_account", "update_brand_account", "reset_brand_account_password")}.items():
    for name, contract in zip(names, [(None, array("Account"), 200), ("AccountRequest", "AccountMutation", 201), ("AccountRequest", "Account", 200), (None, "AccountMutation", 200)]):
        CONTRACTS[f"{prefix}.{name}"] = contract

QUERIES = {
    "orders.customer_orders": {"status": ORDER_STATUS},
    "orders.store_orders": {"store_id": ID, "status": ORDER_STATUS, "view": text(values="active history all"), "days": {"type": "integer", "enum": [1, 7, 30]}, "search": text(64)},
    "brand.store_products": {"store_id": ID},
    "reports.store_overview": {"store_id": ID}, "reports.store_report": {"store_id": ID},
    "inventory.store_inventory": {"store_id": ID}, "inventory.inventory_logs": {"store_id": ID, "store_product_id": ID, "change_type": INVENTORY_CHANGE, "days": {"type": "integer", "enum": [1, 7, 30]}},
    "coupons.my_coupons": {"status": text()}, "coupons.activity_tasks": {"status": text()},
    "coupons.eligible_coupons": {"store_id": ID, "items_amount": MONEY, "product_ids": {"type": "string", "description": "Comma-separated product IDs"}},
    "audit.operation_logs": {"operation_module": text(), "operation_type": text(), "operation_result": text(values="success failed rejected"), "operator_id": ID, "operator_role_code": ROLE, "store_id": ID, "start_at": {**DATE_INPUT, "description": "Date or ISO timestamp; date starts at local midnight"}, "end_at": {**DATE_INPUT, "description": "Date or ISO timestamp; a date includes the entire local day"}, "limit": {"type": "integer", "minimum": 1, "maximum": 300}},
    "i18n.statuses": {"language": LANG},
}
PUBLIC_ENDPOINTS = {"health_check", "auth.login", "auth.register", "auth.verification_code", "stores.list_stores", "catalog.store_menu", "coupons.activities", "i18n.languages", "i18n.statuses"}

SCHEMAS["Permission"] = obj({"user_id": ID, "role_codes": array(ROLE), "permission_codes": array(text()), "store_ids": array(ID)})
CONTRACTS.update({
    "health_check": (None, obj({"status": text(), "service": text()}), 200),
    "permissions.my_permissions": (None, "Permission", 200),
    "i18n.languages": (None, array(obj({"code": LANG, "name": text()})), 200),
    "i18n.statuses": (None, {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": text()}}, 200),
})
for name, source, fields, required in [
    ("StoreRequest", "Store", "store_code name_zh name_en address phone business_start_time business_end_time store_status temporary_close_reason is_active", "store_code name_zh address"),
    ("CategoryRequest", "Category", "name_zh name_en sort_order is_active", "name_zh"),
    ("ProductRequest", "Product", "category_id name_zh name_en description_zh description_en image_url base_price menu_status sort_order", "category_id name_zh base_price"),
    ("StoreProductRequest", "StoreProduct", "store_id product_id current_stock is_available is_sold_out reason", "store_id product_id"),
    ("InventoryRequest", "StoreProduct", "current_stock is_available is_sold_out reason", ""),
    ("ActivityRequest", "Activity", "activity_name_zh activity_name_en description_zh description_en start_at end_at total_stock per_user_limit discount_amount minimum_order_amount activity_status store_ids product_ids", "activity_name_zh start_at end_at total_stock discount_amount"),
]:
    SCHEMAS[name] = obj({field: SCHEMAS[source]["properties"][field] for field in fields.split()}, required.split())
    SCHEMAS[name + "Patch"] = obj(dict(SCHEMAS[name]["properties"]))
for endpoint, (request, response, status) in list(CONTRACTS.items()):
    if endpoint.startswith("brand.") and request in ("Store", "Category", "Product", "StoreProduct", "Activity"):
        CONTRACTS[endpoint] = (request + "Request" + ("Patch" if "update" in endpoint else ""), response, status)
CONTRACTS["inventory.update_inventory_item"] = ("InventoryRequest", "StoreProduct", 200)


# 有固定字段的对象提供可检查的结构；业务日志快照允许模块自定义 JSON 字段。
def nullable(schema):
    result = {**schema, "nullable": True}
    if "enum" in schema:
        result["enum"] = [*schema["enum"], None]
    return result


def mark_nullable(schema_name, field_names):
    properties = SCHEMAS[schema_name]["properties"]
    for field_name in field_names.split():
        properties[field_name] = nullable(properties[field_name])


def require_fields(schema_name, field_names=None):
    schema = SCHEMAS[schema_name]
    schema["required"] = field_names.split() if field_names else list(schema["properties"])


SCHEMAS["ScopeItem"] = obj({"id": ID, "name_zh": text(), "name_en": nullable(text())}, ["id", "name_zh", "name_en"])
SCHEMAS["UserRole"] = obj({"role_code": ROLE, "role_name": text()}, ["role_code", "role_name"])
SCHEMAS["User"]["properties"]["roles"] = array("UserRole")
SCHEMAS["Order"]["properties"].update({"user_id": ID, "store_name": nullable(text()), "customer_name": nullable(text())})
SCHEMAS["PaymentLog"] = obj({"id": ID, "payment_id": ID, "from_status": nullable(PAYMENT_STATUS), "to_status": PAYMENT_STATUS,
    "event_type": text(values="created callback duplicate timeout retry"), "created_at": DATE})
SCHEMAS["Order"]["properties"]["payment_logs"] = array("PaymentLog")
SCHEMAS["StatusLog"]["properties"]["from_status"] = nullable(ORDER_STATUS)
SCHEMAS["StatusLog"]["properties"]["to_status"] = ORDER_STATUS
SCHEMAS["StatusLog"]["properties"].pop("event_type")
SCHEMAS["StoreProduct"]["properties"].pop("id")
SCHEMAS["StoreProduct"]["properties"].pop("reason")
SCHEMAS["StoreProduct"]["properties"].update({"store_product_id": ID, "category_id": ID,
    "category_name_zh": nullable(text()), "category_name_en": nullable(text()), "name_zh": text(), "name_en": nullable(text()),
    "image_url": nullable(text()), "base_price": MONEY, "menu_status": text(values="draft published draft_changes archived"), "can_add_to_cart": BOOL,
    "store_name": nullable(text()), "store_name_zh": nullable(text()), "store_name_en": nullable(text()), "store_code": nullable(text())})
SCHEMAS["ProductContent"] = obj({key: SCHEMAS["Product"]["properties"][key] for key in
    "category_id name_zh name_en description_zh description_en image_url base_price sort_order".split()})
SCHEMAS["ProductContent"]["properties"]["base_price"] = MONEY
SCHEMAS["ProductContent"]["properties"]["sort_order"] = SIGNED_INTEGER
SCHEMAS["Product"]["properties"].update({"base_price": MONEY, "sort_order": SIGNED_INTEGER, "category_name_zh": nullable(text()),
    "category_name_en": nullable(text()), "created_at": DATE, "updated_at": DATE})
SCHEMAS["Category"]["properties"].update({"sort_order": SIGNED_INTEGER, "created_at": DATE, "updated_at": DATE})
SCHEMAS["InventoryLog"]["properties"]["order_id"] = nullable(ID)
SCHEMAS["ClaimTask"]["properties"].update({"activity_name_zh": text(), "activity_name_en": nullable(text()), "created_at": DATE, "updated_at": DATE})
SCHEMAS["UserCoupon"]["properties"]["task_status"] = nullable(text(values="pending processing succeeded failed dead"))
SCHEMAS["Activity"]["properties"].update({"discount_amount": MONEY, "minimum_order_amount": MONEY,
    "remaining_stock": nullable(COUNT), "claimed_count": COUNT, "metrics": ref("BrandCouponMetrics"), "created_by": nullable(ID), "created_at": DATE, "updated_at": DATE})
SCHEMAS["WarmupResult"] = obj({"activity_id": ID, "remaining_stock": COUNT, "force": BOOL})
SCHEMAS["CouponMetrics"] = obj({"activity_id": ID, "total_stock": COUNT, "redis_remaining_stock": nullable(COUNT),
    "redis_success_count": COUNT, "database_count": COUNT, "pending_count": COUNT, "failed_count": COUNT, "dead_count": COUNT,
    "succeeded_task_count": COUNT, "difference_count": COUNT, "database_only_count": COUNT, "used_count": COUNT, "redemption_rate": text()})
SCHEMAS["BrandCouponMetrics"] = obj({"claimed_count": COUNT, "used_count": COUNT, "remaining_stock": COUNT, "usage_rate": text(),
    "redis_success_count": COUNT, "database_count": COUNT, "difference_count": COUNT, "failed_count": COUNT, "dead_count": COUNT,
    "task_counts": obj({key: COUNT for key in ("pending", "processing", "succeeded", "failed", "dead")}, ["pending", "processing", "succeeded", "failed", "dead"])})
SCHEMAS["Overview"]["properties"].update({"stores": array("Store"), "completed_order_count": COUNT, "canceled_order_count": COUNT})
SCHEMAS["ReportSummary"]["properties"]["refund_pending_order_count"] = COUNT
SCHEMAS["Report"]["properties"].update({"popular_products_last_7_days": array("PopularProduct"), "popular_products_last_30_days": array("PopularProduct")})
SCHEMAS["CartAddRequest"] = obj({"store_product_id": ID, "quantity": {"type": "integer", "minimum": 1, "default": 1}}, ["store_product_id"])
SCHEMAS["AccountCreateRequest"] = obj(SCHEMAS["AccountRequest"]["properties"], ["username", "role_code"])
SCHEMAS["AccountPatchRequest"] = obj({key: SCHEMAS["AccountRequest"]["properties"][key] for key in "phone role_code store_id default_language is_active".split()})
SCHEMAS["PaymentSuccessRequest"] = obj({key: value for key, value in SCHEMAS["SimulateRequest"]["properties"].items() if key != "result"})
for name in ("SimulateRequest", "PaymentSuccessRequest"):
    SCHEMAS[name]["properties"]["payment_amount"] = {**MONEY, "description": "Optional amount check; must match the server amount exactly"}
for name in ("StoreRequest", "StoreRequestPatch"):
    for field in ("business_start_time", "business_end_time"):
        SCHEMAS[name]["properties"][field] = {"type": "string", "pattern": r"^\d{2}:\d{2}(:\d{2})?$", "example": "09:00"}
for name in ("CategoryRequest", "CategoryRequestPatch", "ProductRequest", "ProductRequestPatch"):
    SCHEMAS[name]["properties"]["sort_order"] = SIGNED_INTEGER
for name in ("ActivityRequest", "ActivityRequestPatch"):
    SCHEMAS[name]["properties"].update({"start_at": DATE_INPUT, "end_at": DATE_INPUT, "total_stock": {**COUNT, "minimum": 1}})
SCHEMAS["ProductRequest"]["properties"]["menu_status"] = text(values="draft published archived")
SCHEMAS["StoreProductRequestPatch"]["properties"] = SCHEMAS["InventoryRequest"]["properties"]
for name, fields in {
    "Role": "description", "User": "phone last_login_at", "StoreBinding": "store_name store_name_zh store_name_en",
    "Store": "name_en phone temporary_close_reason", "Category": "name_en",
    "Product": "name_en description_zh description_en image_url", "ProductContent": "name_en description_zh description_en image_url",
    "MenuItem": "name_en description_zh description_en image_url", "OrderItem": "product_name_en",
    "StatusLog": "operator_id reason", "PaymentSummary": "transaction_no card_brand masked_card_no failure_reason paid_at",
    "RefundSummary": "refund_reason simulated_refund_no refunded_at",
    "Order": "store_name_zh store_name_en store_address store_phone customer_phone_masked user_coupon_id pickup_code pickup_date remark cancel_reason paid_at completed_at",
    "UserCoupon": "activity_name_en task_id used_at used_order_id", "ClaimTask": "user_coupon_id last_error next_retry_at",
    "ClaimResult": "remaining_stock", "Activity": "activity_name_en description_zh description_en",
    "InventoryLog": "operator_id remark", "PopularProduct": "product_name_en",
    "AuditLog": "operator_id operator_role_code target_id store_id failure_reason ip_address",
}.items():
    mark_nullable(name, fields)
for name in ("StoreRequest", "StoreRequestPatch", "CategoryRequest", "CategoryRequestPatch", "ProductRequest", "ProductRequestPatch", "ActivityRequest", "ActivityRequestPatch", "AccountCreateRequest", "AccountPatchRequest"):
    fields = set(SCHEMAS[name]["properties"]) & {"name_en", "activity_name_en", "description_zh", "description_en", "image_url", "phone", "temporary_close_reason", "store_id"}
    for field in fields:
        if field not in SCHEMAS[name].get("required", []):
            SCHEMAS[name]["properties"][field] = nullable(SCHEMAS[name]["properties"][field])
for name in ("PaymentSummary", "RefundSummary", "ProductContent"):
    SCHEMAS["Nullable" + name] = nullable({**SCHEMAS[name]})
SCHEMAS["Order"]["properties"]["payment"] = ref("NullablePaymentSummary")
SCHEMAS["Order"]["properties"]["refund"] = ref("NullableRefundSummary")
SCHEMAS["Product"]["properties"]["published_content"] = ref("NullableProductContent")
SCHEMAS["Product"]["properties"]["pending_changes"] = ref("NullableProductContent")
for field in ("before_snapshot", "after_snapshot"):
    SCHEMAS["AuditLog"]["properties"][field] = {"type": "object", "nullable": True, "additionalProperties": True,
        "description": "Module-specific before/after snapshot; password and payment secrets are never included"}
for name in ("User", "UserRole", "StoreBinding", "Store", "Category", "Product", "Order", "OrderItem", "StatusLog", "PaymentLog", "PaymentSummary", "RefundSummary",
             "UserCoupon", "WarmupResult", "CouponMetrics", "BrandCouponMetrics", "AuditLog", "InventoryLog", "PopularProduct", "SystemConfig", "Permission", "Logout", "Refresh"):
    require_fields(name)
require_fields("PaymentSummary", "id payment_no payment_method payment_amount payment_status transaction_no card_brand masked_card_no failure_reason paid_at")
SCHEMAS["Payment"]["allOf"][1]["required"] = ["order"]
SCHEMAS["Refund"]["allOf"][1]["required"] = ["order_id", "payment_id", "order"]
SCHEMAS["Account"]["allOf"][1]["required"] = ["is_active", "created_at", "updated_at"]
menu_category_schema = SCHEMAS["Menu"]["properties"]["categories"]["items"]
menu_category_schema["properties"]["name_en"] = nullable(text())
menu_category_schema["required"] = ["id", "name_zh", "name_en", "products"]
require_fields("Auth", "access_token refresh_token user")
require_fields("Role", "id role_code role_name description permission_codes")
require_fields("Verification", "phone expires_in_seconds cooldown_seconds")
require_fields("StoreProduct", "store_product_id store_id product_id category_id category_name_zh category_name_en name_zh name_en image_url base_price menu_status is_available current_stock reserved_stock available_stock is_sold_out can_add_to_cart")
require_fields("Activity", "id activity_name_zh activity_name_en description_zh description_en start_at end_at total_stock per_user_limit discount_amount minimum_order_amount activity_status store_ids product_ids")
require_fields("ClaimTask", "id activity_id activity_name_zh activity_name_en user_id user_coupon_id redis_success_time task_status retry_count next_retry_at created_at updated_at")
require_fields("ClaimResult", "result message_code activity_id remaining_stock task")
require_fields("ReportSummary", "order_count completed_order_count canceled_order_count coupon_used_count revenue")
require_fields("Report", "today last_7_days last_30_days popular_products metric_definitions")
require_fields("Menu", "store categories")
require_fields("MenuItem", "store_product_id product_id name_zh name_en description_zh description_en base_price image_url is_sold_out can_add_to_cart")
require_fields("AccountMutation", "account temporary_password")
# nullable 专用组件与原对象共享字段、分别保留必填约束，null 本身仍然合法。
for name in ("PaymentSummary", "RefundSummary"):
    SCHEMAS["Nullable" + name]["required"] = SCHEMAS[name]["required"]
CONTRACTS["cart.add_cart_item"] = ("CartAddRequest", array("CartItem"), 201)
CONTRACTS["payments.simulate_success"] = ("PaymentSuccessRequest", "Payment", 200)
CONTRACTS["coupons.warmup"] = (obj({"force": {**BOOL, "default": False}}), "WarmupResult", 200)
CONTRACTS["brand.coupon_metrics"] = (None, "BrandCouponMetrics", 200)
for endpoint, (request_schema, response_schema, success_status) in list(CONTRACTS.items()):
    if request_schema == "AccountRequest":
        CONTRACTS[endpoint] = ("AccountCreateRequest" if success_status == 201 else "AccountPatchRequest", response_schema, success_status)
QUERIES["coupons.my_coupons"]["status"] = text(values="syncing available used expired abnormal")
QUERIES["coupons.activity_tasks"]["status"] = text(values="pending processing succeeded failed dead")
ALTERNATE_SUCCESS_SCHEMAS = {"coupons.claim": ref("Error")}

SCHEMAS["AccountCreateRequest"]["allOf"] = [{"oneOf": [
    obj({"role_code": text(values="store_staff store_manager"), "store_id": ID}, ["role_code", "store_id"]),
    obj({"role_code": text(values="brand_admin system_admin")}, ["role_code"]),
]}]
SCHEMAS["RefundRequest"]["properties"]["reason"]["description"] = "Required when a store manager cancels an order already preparing; otherwise optional"
SCHEMAS["PaymentSuccessRequest"]["description"] = "Customer-owned successful callback; bank-card requests must include and validate the card form. Terminal failed/canceled/expired attempts cannot succeed."
SCHEMAS["SimulateRequest"]["description"] = "Customer-owned simulated payment; bank cards require card_number/cardholder_name plus UnionPay or international-card form fields. Only masked card details are stored."
SCHEMAS["RegisterRequest"]["properties"]["password"].update({"minLength": 8, "description": "Must contain a letter and a digit"})
SCHEMAS["AccountCreateRequest"]["properties"]["password"].update({"minLength": 8, "description": "Optional; the server supplies the demo temporary password when omitted"})
SCHEMAS["StoreProductRequest"]["description"] = "Creates or updates one store/product configuration; the response status remains 201 for either outcome."
