"""
文件名称：openapi.py
文件用途：生成与实际 ERP 服务一致的 OpenAPI 3.0 接口文档
主要职责：检查全部路由契约映射，输出请求、查询、空值、角色令牌类型和真实响应结构
所属业务模块：后端基础设施
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import re

from flask import current_app
from app.common.api_contracts import ALTERNATE_SUCCESS_SCHEMAS, CONTRACTS, PUBLIC_ENDPOINTS, QUERIES, SCHEMAS, obj, ref

PATH_PARAMETER_PATTERN = re.compile(r"<(?:(?P<converter>[^:>]+):)?(?P<name>[^>]+)>")


def build_openapi_spec() -> dict:
    """
    函数名称：build_openapi_spec
    函数用途：生成与实际路由、业务请求和统一响应一致的 OpenAPI 文档
    参数说明：读取当前 Flask 应用路由，无参数
    返回值说明：返回 OpenAPI 3.0.3 文档
    核心逻辑：逐路由绑定显式契约、鉴权类型、必填路径/查询参数及真实成功状态码
    异常或失败情况：新增路由缺少契约时明确失败，避免静默生成空泛对象
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    paths: dict[str, dict] = {}
    for rule in sorted(current_app.url_map.iter_rules(), key=lambda item: item.rule):
        if not rule.rule.startswith("/api/") or rule.rule == "/api/openapi.json":
            continue
        parameter_names: list[str] = []

        def replace_parameter(match: re.Match) -> str:
            parameter_names.append(match.group("name"))
            return "{" + match.group("name") + "}"

        openapi_path = PATH_PARAMETER_PATTERN.sub(replace_parameter, rule.rule)
        path_item = paths.setdefault(openapi_path, {})
        tag = rule.rule.split("/")[2] if len(rule.rule.split("/")) > 2 else "system"
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            if rule.endpoint not in CONTRACTS:
                raise RuntimeError(f"Missing API contract for {rule.endpoint}")
            request_schema, response_schema, success_status = CONTRACTS[rule.endpoint]
            response_schema = ref(response_schema) if isinstance(response_schema, str) else response_schema
            success_schema = obj({"success": {"type": "boolean", "enum": [True]}, "data": response_schema}, ["success", "data"])
            if rule.endpoint in ALTERNATE_SUCCESS_SCHEMAS:
                success_schema = {"oneOf": [success_schema, ALTERNATE_SUCCESS_SCHEMAS[rule.endpoint]]}
            operation = {
                "operationId": f"{rule.endpoint}_{method.lower()}",
                "tags": [tag],
                "security": [] if rule.endpoint in PUBLIC_ENDPOINTS else [{"refreshToken": []}] if rule.endpoint == "auth.refresh" else [{"bearerAuth": []}],
                "responses": {
                    str(success_status): {
                        "description": "Success",
                        "content": {"application/json": {"schema": success_schema}},
                    },
                    **{str(status): {"description": description, "content": {"application/json": {"schema": ref("Error")}}}
                       for status, description in [(400, "Business validation error"), (401, "Authentication required or session revoked"), (403, "Role or data scope denied"), (404, "Resource unavailable"), (409, "Concurrent state conflict"), (429, "Too many requests"), (500, "Database or internal error"), (503, "Dependency unavailable")]},
                },
            }
            parameters = [{"name": name, "in": "path", "required": True, "schema": {"type": "integer", "minimum": 1}} for name in parameter_names]
            parameters.extend({"name": name, "in": "query", "required": name == "store_id" and rule.endpoint.startswith(("orders.store", "reports.", "inventory.")), "schema": schema} for name, schema in QUERIES.get(rule.endpoint, {}).items())
            if parameters:
                operation["parameters"] = parameters
            if request_schema is not None:
                resolved_request = SCHEMAS[request_schema] if isinstance(request_schema, str) else request_schema
                operation["requestBody"] = {
                    "required": bool(resolved_request.get("required") or resolved_request.get("minProperties")),
                    "content": {"application/json": {"schema": ref(request_schema) if isinstance(request_schema, str) else request_schema}},
                }
            path_item[method.lower()] = operation
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Nayami Order System API",
            "version": "1.1.0",
            "description": "Multi-store restaurant ordering, fulfillment and operations prototype.",
        },
        "servers": [{"url": "/"}],
        "components": {
            "schemas": SCHEMAS,
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT", "description": "Access token from login or refresh"},
                "refreshToken": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT", "description": "Refresh token from login; access tokens are rejected by /api/auth/refresh"}
            }
        },
        "paths": paths,
    }
