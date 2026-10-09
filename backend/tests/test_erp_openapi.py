"""
文件名称：test_erp_openapi.py
文件用途：独立核查 OpenAPI 文档与真实 ERP API 契约
主要职责：核对路由覆盖、请求必填、空值、状态码、鉴权类型，并以真实 API 响应递归验证 schema
所属业务模块：接口契约回归测试
创建时间：2026-09-08 17:40
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from datetime import timedelta
import re
from urllib.parse import urlsplit

import pytest

from app.common.api_contracts import CONTRACTS
from app.common.openapi import build_openapi_spec, PATH_PARAMETER_PATTERN
from app.common.time_utils import current_time
from app.coupons import services as coupon_services
from app.extensions import db
from app.coupons.models import CouponClaimTask
from test_minimal_order_flow import app, client, login, auth_headers


def _validate(value, schema, spec, path="$", depth=0):
    """验证本项目使用的 OpenAPI 3.0 schema 子集，支持引用、组合、空值和嵌套字段。"""
    assert depth < 80, f"{path}: recursive schema"
    if "$ref" in schema:
        return _validate(value, spec["components"]["schemas"][schema["$ref"].split("/")[-1]], spec, path, depth+1)
    if value is None and schema.get("nullable"):
        return
    for child in schema.get("allOf", []):
        _validate(value, child, spec, path, depth+1)
    for combination in ("oneOf", "anyOf"):
        if combination in schema:
            matched = 0
            failures = []
            for child in schema[combination]:
                try:
                    _validate(value, child, spec, path, depth+1)
                    matched += 1
                except AssertionError as error:
                    failures.append(str(error))
            assert matched == 1 if combination == "oneOf" else matched >= 1, f"{path}: {combination} mismatch {failures}"
    kind = schema.get("type")
    if kind == "object":
        assert isinstance(value, dict), f"{path}: expected object, got {value!r}"
        assert set(schema.get("required", [])) <= value.keys(), f"{path}: missing {set(schema.get('required', []))-value.keys()}"
        assert len(value) >= schema.get("minProperties", 0), f"{path}: empty object"
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], spec, f"{path}.{key}", depth+1)
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate(item, schema["additionalProperties"], spec, f"{path}.{key}", depth+1)
            else:
                assert schema.get("additionalProperties", True), f"{path}: unexpected {key}"
    elif kind == "array":
        assert isinstance(value, list), f"{path}: expected array"
        assert len(value) >= schema.get("minItems", 0), f"{path}: too few items"
        assert len(value) <= schema.get("maxItems", float("inf")), f"{path}: too many items"
        for index, item in enumerate(value):
            _validate(item, schema["items"], spec, f"{path}[{index}]", depth+1)
    elif kind == "string":
        assert isinstance(value, str), f"{path}: expected string, got {value!r}"
        assert len(value) <= schema.get("maxLength", float("inf")), f"{path}: too long"
        assert len(value) >= schema.get("minLength", 0), f"{path}: too short"
        assert not schema.get("pattern") or re.search(schema["pattern"], value), f"{path}: pattern mismatch {value!r}"
        if schema.get("format") == "date":
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), f"{path}: invalid date"
    elif kind == "integer":
        assert type(value) is int, f"{path}: expected integer, got {value!r}"
    elif kind == "number":
        assert type(value) in (int, float), f"{path}: expected number"
    elif kind == "boolean":
        assert type(value) is bool, f"{path}: expected boolean"
    if "enum" in schema:
        assert value in schema["enum"], f"{path}: unknown enum {value!r}"
    if kind in ("integer", "number"):
        assert value >= schema.get("minimum", float("-inf")), f"{path}: too small"
        assert value <= schema.get("maximum", float("inf")), f"{path}: too large"


def _request(client, spec, method, url, **kwargs):
    rule, _ = client.application.url_map.bind("localhost").match(urlsplit(url).path, method=method, return_rule=True)
    path = PATH_PARAMETER_PATTERN.sub(lambda match: "{"+match.group("name")+"}", rule.rule)
    operation = spec["paths"][path][method.lower()]
    if "json" in kwargs and "requestBody" in operation:
        _validate(kwargs["json"], operation["requestBody"]["content"]["application/json"]["schema"], spec, path+" request")
    response = client.open(url, method=method, **kwargs)
    assert response.status_code == CONTRACTS[rule.endpoint][2], (url, response.status_code, response.get_json())
    _validate(response.get_json(), operation["responses"][str(response.status_code)]["content"]["application/json"]["schema"], spec, path+" response")
    return response.get_json()["data"]


def test_every_api_route_has_an_explicit_resolvable_contract(app):
    with app.app_context():
        spec = build_openapi_spec()
    actual = {rule.endpoint for rule in app.url_map.iter_rules() if rule.rule.startswith("/api/") and rule.rule != "/api/openapi.json"}
    assert actual == set(CONTRACTS)
    operation_ids = []
    def inspect(node):
        if isinstance(node, dict):
            if "$ref" in node:
                assert node["$ref"].split("/")[-1] in spec["components"]["schemas"]
            if node.get("type") == "object":
                assert node.get("properties") or "additionalProperties" in node, "unstructured object schema"
            for value in node.values():
                inspect(value)
        elif isinstance(node, list):
            for value in node:
                inspect(value)
    inspect(spec)
    for path, methods in spec["paths"].items():
        for operation in methods.values():
            operation_ids.append(operation["operationId"])
            assert all(parameter["required"] for parameter in operation.get("parameters", []) if parameter["in"] == "path")
    assert len(operation_ids) == len(set(operation_ids))
    assert spec["paths"]["/api/auth/refresh"]["post"]["security"] == [{"refreshToken": []}]
    assert spec["paths"]["/api/health"]["get"]["security"] == []


def test_create_and_patch_contracts_distinguish_required_and_mutable_fields(app):
    with app.app_context():
        spec = build_openapi_spec()
    schemas = spec["components"]["schemas"]
    for name, required in {"StoreRequest": {"store_code","name_zh","address"}, "CategoryRequest": {"name_zh"},
        "ProductRequest": {"category_id","name_zh","base_price"}, "ActivityRequest": {"activity_name_zh","start_at","end_at","total_stock","discount_amount"},
        "StoreProductRequest": {"store_id","product_id"}, "AccountCreateRequest": {"username","role_code"}}.items():
        assert set(schemas[name]["required"]) == required
    for name in ("StoreRequestPatch", "CategoryRequestPatch", "ProductRequestPatch", "ActivityRequestPatch", "StoreProductRequestPatch", "AccountPatchRequest"):
        assert not schemas[name].get("required")
    assert not {"username", "password"} & schemas["AccountPatchRequest"]["properties"].keys()
    assert not {"store_id", "product_id"} & schemas["StoreProductRequestPatch"]["properties"].keys()
    assert "draft_changes" not in schemas["ProductRequest"]["properties"]["menu_status"]["enum"]
    assert "draft_changes" in schemas["ProductRequestPatch"]["properties"]["menu_status"]["enum"]
    assert not schemas["RetryRequest"].get("required")
    assert not schemas["ClaimRequest"].get("required")
    assert spec["paths"]["/api/system/config"]["patch"]["requestBody"]["required"] is True
    _validate({"store_id": 1, "items": [{"store_product_id":1,"quantity":1}], "extra_client_context": "allowed"}, schemas["OrderRequest"], spec)
    with pytest.raises(AssertionError):
        _validate({"store_id": 1, "items": [{"store_product_id":1,"quantity":1.9}]}, schemas["OrderRequest"], spec)


def test_real_customer_store_and_admin_responses_match_schema(client):
    spec = client.get("/api/openapi.json").get_json()
    credentials = _request(client,spec,"POST","/api/auth/login",json={"username":"customer_demo","password":"Nayami123!"})
    customer=auth_headers(credentials["access_token"])
    manager=auth_headers(login(client,"store_manager_demo","Manager123!"))
    system=auth_headers(login(client,"system_admin","Admin123!"))
    _request(client,spec,"POST","/api/auth/refresh",headers=auth_headers(credentials["refresh_token"]))
    order=_request(client,spec,"POST","/api/orders",headers=customer,json={"store_id":1,"items":[{"store_product_id":1,"quantity":1}]})
    for url,headers in [("/api/health",{}),("/api/auth/me",customer),("/api/permissions/me",customer),("/api/i18n/languages",{}),("/api/i18n/statuses?language=en-US",{}),
        ("/api/stores",{}),("/api/catalog/stores/1/menu",{}),("/api/orders",customer),(f"/api/orders/{order['id']}",customer),
        (f"/api/payments/{order['payment']['id']}",customer),("/api/store/orders?store_id=1",manager),
        ("/api/store/inventory?store_id=1",manager),("/api/store/inventory/logs?store_id=1",manager),("/api/store/overview?store_id=1",manager),
        ("/api/store/report?store_id=1",manager),("/api/brand/overview",system),("/api/brand/report",system),
        ("/api/brand/stores",system),("/api/brand/categories",system),("/api/brand/products",system),("/api/brand/store-products",system),
        ("/api/system/roles",system),("/api/system/accounts",system),("/api/system/config",system),("/api/audit/logs",system)]:
        _request(client,spec,"GET",url,headers=headers)
    paid=_request(client,spec,"POST",f"/api/payments/{order['payment']['id']}/simulate-success",headers=customer,json={})
    refund=_request(client,spec,"POST",f"/api/payments/orders/{order['id']}/refund",headers=customer,json={"reason":"契约验收"})
    _request(client,spec,"POST",f"/api/payments/refunds/{refund['id']}/simulate-success",headers=customer)
    _request(client,spec,"POST","/api/auth/logout",headers=customer)


def test_real_crud_creation_and_partial_updates_match_schema(client):
    spec=client.get("/api/openapi.json").get_json(); headers=auth_headers(login(client,"system_admin","Admin123!"))
    category=_request(client,spec,"POST","/api/brand/categories",headers=headers,json={"name_zh":"契约分类","sort_order":-1})
    _request(client,spec,"PATCH",f"/api/brand/categories/{category['id']}",headers=headers,json={"name_en":None})
    product=_request(client,spec,"POST","/api/brand/products",headers=headers,json={"category_id":category["id"],"name_zh":"契约商品","base_price":"0.00"})
    _request(client,spec,"PATCH",f"/api/brand/products/{product['id']}",headers=headers,json={"menu_status":"published"})
    _request(client,spec,"PATCH",f"/api/brand/products/{product['id']}",headers=headers,json={"name_zh":"待发布名称","base_price":"12.50"})
    store=_request(client,spec,"POST","/api/brand/stores",headers=headers,json={"store_code":"CONTRACT","name_zh":"契约店","address":"测试路"})
    _request(client,spec,"PATCH",f"/api/brand/stores/{store['id']}",headers=headers,json={"name_en":None})
    configured=_request(client,spec,"POST","/api/brand/store-products",headers=headers,json={"store_id":store["id"],"product_id":product["id"],"current_stock":4})
    _request(client,spec,"PATCH",f"/api/brand/store-products/{configured['store_product_id']}",headers=headers,json={"current_stock":5,"reason":"补货"})
    _request(client,spec,"PATCH","/api/store/inventory/1",headers=headers,json={"current_stock":8,"reason":"契约补货"})
    account=_request(client,spec,"POST","/api/system/accounts",headers=headers,json={"username":"contract_staff","role_code":"store_staff","store_id":1})
    _request(client,spec,"PATCH",f"/api/system/accounts/{account['account']['id']}",headers=headers,json={"phone":None})
    _request(client,spec,"POST",f"/api/system/accounts/{account['account']['id']}/reset-password",headers=headers)


def test_coupon_202_and_nullable_syncing_task_contracts(client, app, monkeypatch):
    spec=client.get("/api/openapi.json").get_json(); brand=auth_headers(login(client,"brand_admin","Admin123!")); customer=auth_headers(login(client,"customer_demo","Nayami123!"))
    now=current_time(); payload={"activity_name_zh":"契约券","start_at":(now-timedelta(minutes=5)).isoformat(),"end_at":(now+timedelta(days=1)).isoformat(),"total_stock":2,"discount_amount":"0.00","activity_status":"active","store_ids":[1],"product_ids":[1]}
    activity=_request(client,spec,"POST","/api/brand/coupons",headers=brand,json=payload)
    _request(client,spec,"GET","/api/brand/coupons",headers=brand)
    _request(client,spec,"GET",f"/api/brand/coupons/{activity['id']}/metrics",headers=brand)
    _request(client,spec,"POST",f"/api/coupons/activities/{activity['id']}/warmup",headers=brand,json={})
    _request(client,spec,"GET","/api/coupons/activities")
    app.config["COUPON_TASK_EAGER"]=False;monkeypatch.setattr(coupon_services,"_dispatch_claim_task",lambda task_id:None)
    claimed=_request(client,spec,"POST",f"/api/coupons/activities/{activity['id']}/claim",headers=customer,json={})
    _request(client,spec,"GET","/api/coupons/me",headers=customer)
    _request(client,spec,"GET",f"/api/coupons/tasks/{claimed['task']['id']}",headers=brand)
    _request(client,spec,"GET",f"/api/coupons/activities/{activity['id']}/tasks",headers=brand)
    coupon_services.process_claim_task(claimed["task"]["id"])
    _request(client,spec,"GET","/api/coupons/me",headers=customer)
    _request(client,spec,"GET","/api/coupons/eligible?store_id=1&items_amount=38.00&product_ids=1",headers=customer)
    _request(client,spec,"POST",f"/api/coupons/activities/{activity['id']}/reconcile",headers=brand)
    accepted_schema=spec["paths"]["/api/coupons/activities/{activity_id}/claim"]["post"]["responses"]["202"]["content"]["application/json"]["schema"]
    _validate({"success":False,"error":{"code":"coupon_claim_task_pending","message":"领取成功，权益正在补偿同步"}},accepted_schema,spec)


def test_nullable_output_fields_and_public_registration_contract(client):
    spec = client.get("/api/openapi.json").get_json()
    verification = _request(client,spec,"POST","/api/auth/verification-code",json={"phone":"18899990001"})
    registered = _request(client,spec,"POST","/api/auth/register",json={"username":"contract_customer","phone":"18899990001",
        "password":"Contract123!","confirm_password":"Contract123!","verification_code":verification["verification_code"]})
    headers = auth_headers(registered["access_token"])
    _request(client,spec,"POST","/api/cart/items",headers=headers,json={"store_product_id":1})
    _request(client,spec,"PATCH","/api/cart/items/1",headers=headers,json={"quantity":2})
    _request(client,spec,"GET","/api/cart/items",headers=headers)
    _request(client,spec,"DELETE","/api/cart/items/1",headers=headers)
    _request(client,spec,"DELETE","/api/cart/items",headers=headers)
    nullable_values = [("NullablePaymentSummary",None),("NullableRefundSummary",None),("NullableProductContent",None)]
    for name,value in nullable_values:
        _validate(value,spec["components"]["schemas"][name],spec)
    with pytest.raises(AssertionError):
        _validate(None,spec["components"]["schemas"]["Order"],spec)
