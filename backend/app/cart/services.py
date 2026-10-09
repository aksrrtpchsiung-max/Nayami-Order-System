"""
文件名称：services.py
文件用途：实现登录顾客的轻量服务端购物车存取
主要职责：通过 Redis 保存、更新、删除和清空用户购物车，测试环境使用应用内存替身
所属业务模块：购物车
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import json

from flask import current_app

from app.common.errors import BusinessError


def list_cart_items(user_id: int) -> list[dict]:
    """读取指定顾客的购物车条目。"""
    return _read_cart(user_id)


def add_cart_item(user_id: int, store_product_id: int, quantity: int) -> list[dict]:
    """新增商品；同一门店商品已存在时累加数量。"""
    cart_items = _read_cart(user_id)
    existing_item = next(
        (item for item in cart_items if item["store_product_id"] == store_product_id),
        None,
    )
    if existing_item:
        existing_item["quantity"] += quantity
    else:
        cart_items.append({"store_product_id": store_product_id, "quantity": quantity})
    _write_cart(user_id, cart_items)
    return cart_items


def update_cart_item(user_id: int, store_product_id: int, quantity: int) -> list[dict]:
    """更新既有条目数量；不存在的条目保持不变。"""
    cart_items = _read_cart(user_id)
    for item in cart_items:
        if item["store_product_id"] == store_product_id:
            item["quantity"] = quantity
    _write_cart(user_id, cart_items)
    return cart_items


def remove_cart_item(user_id: int, store_product_id: int) -> list[dict]:
    """移除指定门店商品。"""
    cart_items = [
        item for item in _read_cart(user_id)
        if item["store_product_id"] != store_product_id
    ]
    _write_cart(user_id, cart_items)
    return cart_items


def clear_cart_items(user_id: int) -> list[dict]:
    """清空当前顾客购物车。"""
    storage = _cart_storage()
    if isinstance(storage, dict):
        storage.pop(user_id, None)
    else:
        try:
            storage.delete(_cart_key(user_id))
        except Exception as exc:
            raise BusinessError("购物车服务暂不可用", "cart_service_unavailable", 503) from exc
    return []


def _read_cart(user_id: int) -> list[dict]:
    storage = _cart_storage()
    if isinstance(storage, dict):
        return [dict(item) for item in storage.get(user_id, [])]
    try:
        raw_value = storage.get(_cart_key(user_id))
        return json.loads(raw_value) if raw_value else []
    except Exception as exc:
        raise BusinessError("购物车服务暂不可用", "cart_service_unavailable", 503) from exc


def _write_cart(user_id: int, cart_items: list[dict]) -> None:
    storage = _cart_storage()
    if isinstance(storage, dict):
        storage[user_id] = [dict(item) for item in cart_items]
        return
    try:
        storage.set(
            _cart_key(user_id),
            json.dumps(cart_items, ensure_ascii=False),
            ex=int(current_app.config["CART_TTL_SECONDS"]),
        )
    except Exception as exc:
        raise BusinessError("购物车服务暂不可用", "cart_service_unavailable", 503) from exc


def _cart_storage():
    extension_key = "nayami_cart_storage"
    if extension_key in current_app.extensions:
        return current_app.extensions[extension_key]
    if current_app.testing:
        storage = {}
    else:
        try:
            import redis

            storage = redis.Redis.from_url(current_app.config["REDIS_URL"], decode_responses=True)
        except Exception as exc:
            raise BusinessError("购物车服务暂不可用", "cart_service_unavailable", 503) from exc
    current_app.extensions[extension_key] = storage
    return storage


def _cart_key(user_id: int) -> str:
    return f"cart:user:{user_id}"
