"""
文件名称：warmup_coupon_redis.py
文件用途：通过后台 API 预热全部可进行抢券的活动库存
主要职责：登录品牌管理员、查询活动并调用受权限保护的预热接口
所属业务模块：优惠券运维
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from _runtime import load_root_env


def request_json(url: str, method: str = "GET", payload: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    load_root_env()
    api_base = os.getenv("NAYAMI_API_BASE", "http://127.0.0.1:5000/api").rstrip("/")
    username = os.getenv("NAYAMI_ADMIN_USERNAME", "brand_admin")
    password = os.getenv("NAYAMI_ADMIN_PASSWORD", "Admin123!")
    try:
        login_result = request_json(
            f"{api_base}/auth/login",
            "POST",
            {"username": username, "password": password},
        )
        token = login_result["data"]["access_token"]
        activities = request_json(f"{api_base}/brand/coupons", token=token)["data"]
        warmup_results = []
        for activity in activities:
            if activity["activity_status"] not in {"active", "scheduled"}:
                continue
            result = request_json(
                f"{api_base}/coupons/activities/{activity['id']}/warmup",
                "POST",
                {},
                token,
            )
            warmup_results.append(result["data"])
        print(json.dumps({"warmed_count": len(warmup_results), "activities": warmup_results}, ensure_ascii=False))
    except HTTPError as exc:
        raise SystemExit(f"Coupon warmup failed: HTTP {exc.code} {exc.read().decode('utf-8')}") from exc


if __name__ == "__main__":
    main()
