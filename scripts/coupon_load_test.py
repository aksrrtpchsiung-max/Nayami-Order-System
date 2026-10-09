"""
文件名称：coupon_load_test.py
文件用途：对演示优惠券领取 API 执行并发压力测试
主要职责：创建独立演示顾客、并发抢券并汇总成功、售罄、重复和失败指标
所属业务模块：优惠券压测
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request_json(url: str, method: str = "GET", payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def create_customer(api_base: str, sequence: int, run_id: int) -> str:
    phone = f"19{run_id % 100000:05d}{sequence:04d}"
    username = f"load_{run_id}_{sequence}"
    request_json(f"{api_base}/auth/verification-code", "POST", {"phone": phone})
    status, result = request_json(
        f"{api_base}/auth/register",
        "POST",
        {
            "username": username,
            "phone": phone,
            "verification_code": "123456",
            "password": "LoadTest123!",
            "confirm_password": "LoadTest123!",
            "default_language": "zh-CN",
        },
    )
    if status != 201:
        raise RuntimeError(f"Failed to create load-test customer: {result}")
    return result["data"]["access_token"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:5000/api")
    parser.add_argument("--activity-id", type=int, required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=20)
    arguments = parser.parse_args()
    api_base = arguments.api_base.rstrip("/")
    run_id = int(time.time()) % 100000
    tokens = [create_customer(api_base, index, run_id) for index in range(arguments.requests)]

    started_at = time.perf_counter()
    results: list[tuple[int, dict]] = []
    with ThreadPoolExecutor(max_workers=arguments.concurrency) as executor:
        futures = [
            executor.submit(
                request_json,
                f"{api_base}/coupons/activities/{arguments.activity_id}/claim",
                "POST",
                {"request_id": f"load-{run_id}-{index}"},
                token,
            )
            for index, token in enumerate(tokens)
        ]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.perf_counter() - started_at
    error_codes = [
        result.get("error", {}).get("code", "unknown")
        for status, result in results
        if status >= 400
    ]
    summary = {
        "requests": len(results),
        "concurrency": arguments.concurrency,
        "elapsed_seconds": round(elapsed, 3),
        "requests_per_second": round(len(results) / elapsed, 2) if elapsed else None,
        "accepted": sum(status == 202 for status, _ in results),
        "sold_out": error_codes.count("coupon_sold_out"),
        "duplicates": sum(code in {"coupon_already_claimed", "coupon_already_available"} for code in error_codes),
        "other_failures": len(error_codes)
        - error_codes.count("coupon_sold_out")
        - sum(code in {"coupon_already_claimed", "coupon_already_available"} for code in error_codes),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
