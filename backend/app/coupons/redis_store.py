"""
文件名称：redis_store.py
文件用途：封装优惠券抢券所需的 Redis 原子操作
主要职责：库存预热、Lua 原子抢券、短期幂等、活动指标、任务状态快照和对账锁
所属业务模块：优惠券与高并发抢券
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from time import time
from uuid import uuid4

from flask import current_app

CLAIM_RESULT_SOLD_OUT = 0
CLAIM_RESULT_SUCCEEDED = 1
CLAIM_RESULT_ALREADY_CLAIMED = 2
CLAIM_RESULT_IDEMPOTENT = 3
CLAIM_RESULT_NOT_WARMED = -1


@dataclass
class InMemoryCouponRedisStore:
    """
    类名称：InMemoryCouponRedisStore
    类用途：为测试环境提供与 Redis 抢券语义一致的进程内实现
    主要职责：用线程锁保证库存判断、扣减和防重复领取的原子性
    不负责的内容：不用于生产或多进程并发演示
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    stocks: dict[int, int] = field(default_factory=dict)
    users: dict[int, set[int]] = field(default_factory=dict)
    successes: dict[int, dict[int, float]] = field(default_factory=dict)
    idempotency_results: dict[tuple[int, int, str], dict] = field(default_factory=dict)
    task_statuses: dict[int, dict] = field(default_factory=dict)
    locks: dict[int, str] = field(default_factory=dict)
    mutex: Lock = field(default_factory=Lock)

    def warmup(self, activity_id: int, stock: int, force: bool = False, claimed_user_ids: set[int] | None = None) -> int:
        with self.mutex:
            if force:
                self.users[activity_id] = set()
                self.successes[activity_id] = {}
            if force or activity_id not in self.stocks:
                known_users = self.users.setdefault(activity_id, set())
                known_users.update(claimed_user_ids or set())
                self.stocks[activity_id] = max(stock - len(known_users), 0)
                self.successes.setdefault(activity_id, {}).update({user_id: time() for user_id in known_users})
            return self.stocks[activity_id]

    def claim(self, activity_id: int, user_id: int, request_id: str) -> dict:
        with self.mutex:
            idempotency_key = (activity_id, user_id, request_id)
            if idempotency_key in self.idempotency_results:
                return dict(self.idempotency_results[idempotency_key], is_idempotent=True)
            if activity_id not in self.stocks:
                result = {"code": CLAIM_RESULT_NOT_WARMED, "remaining_stock": None}
            elif user_id in self.users.setdefault(activity_id, set()):
                result = {"code": CLAIM_RESULT_ALREADY_CLAIMED, "remaining_stock": self.stocks[activity_id]}
            elif self.stocks[activity_id] <= 0:
                result = {"code": CLAIM_RESULT_SOLD_OUT, "remaining_stock": 0}
            else:
                self.stocks[activity_id] -= 1
                self.users[activity_id].add(user_id)
                self.successes.setdefault(activity_id, {})[user_id] = time()
                result = {"code": CLAIM_RESULT_SUCCEEDED, "remaining_stock": self.stocks[activity_id]}
            self.idempotency_results[idempotency_key] = result
            return dict(result, is_idempotent=False)

    def has_successful_request(self, activity_id: int, user_id: int, request_id: str) -> bool:
        with self.mutex:
            result = self.idempotency_results.get((activity_id, user_id, request_id), {})
            return result.get("code") in (CLAIM_RESULT_SUCCEEDED, CLAIM_RESULT_IDEMPOTENT)

    def metrics(self, activity_id: int) -> dict:
        with self.mutex:
            users = self.users.get(activity_id, set())
            return {
                "remaining_stock": self.stocks.get(activity_id),
                "success_count": len(users),
                "successful_user_ids": sorted(users),
            }

    def set_task_status(self, task_id: int, values: dict) -> None:
        with self.mutex:
            self.task_statuses[task_id] = {**self.task_statuses.get(task_id, {}), **values}

    def acquire_reconcile_lock(self, activity_id: int) -> str | None:
        with self.mutex:
            if activity_id in self.locks:
                return None
            token = uuid4().hex
            self.locks[activity_id] = token
            return token

    def release_reconcile_lock(self, activity_id: int, token: str) -> None:
        with self.mutex:
            if self.locks.get(activity_id) == token:
                del self.locks[activity_id]


class RedisCouponStore:
    """
    类名称：RedisCouponStore
    类用途：通过 redis-py 执行生产和演示环境的优惠券原子操作
    主要职责：加载 Lua 脚本并维护文档约定的 Redis Key
    不负责的内容：不写 MySQL 用户优惠券和落库任务
    关键依赖：Redis、backend/app/coupons/lua/claim_coupon.lua
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    def __init__(self, redis_url: str, idempotency_ttl: int, result_ttl: int) -> None:
        import redis

        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.idempotency_ttl = idempotency_ttl
        self.result_ttl = result_ttl
        lua_path = Path(__file__).with_name("lua") / "claim_coupon.lua"
        self.claim_script = self.client.register_script(lua_path.read_text(encoding="utf-8"))

    def warmup(self, activity_id: int, stock: int, force: bool = False, claimed_user_ids: set[int] | None = None) -> int:
        """仅初始化缺失库存；结合 MySQL 已领权益恢复去重集合，防止 Redis 丢键后超发。"""
        script = """
        if ARGV[2] == '1' then
            redis.call('DEL', KEYS[1], KEYS[2], KEYS[3], KEYS[4])
        end
        if redis.call('EXISTS', KEYS[1]) == 1 then return tonumber(redis.call('GET', KEYS[1])) end
        for position = 4, #ARGV do
            redis.call('SADD', KEYS[2], ARGV[position])
            redis.call('ZADD', KEYS[3], 'NX', ARGV[3], ARGV[position])
        end
        local remaining = math.max(tonumber(ARGV[1]) - redis.call('SCARD', KEYS[2]), 0)
        redis.call('SET', KEYS[1], remaining)
        return remaining
        """
        return int(self.client.eval(script, 4, _stock_key(activity_id), _users_key(activity_id),
            _success_key(activity_id), _stats_key(activity_id), stock, int(force), str(time()),
            *[str(user_id) for user_id in sorted(claimed_user_ids or set())]))

    def claim(self, activity_id: int, user_id: int, request_id: str) -> dict:
        result_key = _result_key(activity_id, user_id)
        raw_result = self.claim_script(
            keys=[
                _stock_key(activity_id),
                _users_key(activity_id),
                _success_key(activity_id),
                _stats_key(activity_id),
                _idempotency_key(activity_id, user_id, request_id),
                result_key,
            ],
            args=[str(user_id), str(time()), str(self.idempotency_ttl), str(self.result_ttl)],
        )
        code = int(raw_result[0])
        remaining_stock = int(raw_result[1]) if len(raw_result) > 1 and raw_result[1] not in (None, "") else None
        return {
            "code": code,
            "remaining_stock": remaining_stock,
            "is_idempotent": code == CLAIM_RESULT_IDEMPOTENT,
        }

    def has_successful_request(self, activity_id: int, user_id: int, request_id: str) -> bool:
        return self.client.get(_idempotency_key(activity_id, user_id, request_id)) == "succeeded"

    def metrics(self, activity_id: int) -> dict:
        stock = self.client.get(_stock_key(activity_id))
        users = {int(value) for value in self.client.smembers(_users_key(activity_id))}
        return {
            "remaining_stock": int(stock) if stock is not None else None,
            "success_count": len(users),
            "successful_user_ids": sorted(users),
        }

    def set_task_status(self, task_id: int, values: dict) -> None:
        key = f"coupon:claim:task:{task_id}:status"
        mapping = {field_name: "" if value is None else str(value) for field_name, value in values.items()}
        pipeline = self.client.pipeline(transaction=True)
        pipeline.hset(key, mapping=mapping)
        pipeline.expire(key, self.result_ttl)
        pipeline.execute()

    def acquire_reconcile_lock(self, activity_id: int) -> str | None:
        token = uuid4().hex
        return token if self.client.set(_reconcile_lock_key(activity_id), token, nx=True, ex=600) else None

    def release_reconcile_lock(self, activity_id: int, token: str) -> None:
        # 锁超时后可能已被其他进程取得，必须原子比较所有权再释放。
        self.client.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
            1, _reconcile_lock_key(activity_id), token,
        )


def get_coupon_redis_store():
    """
    函数名称：get_coupon_redis_store
    函数用途：获取当前 Flask 应用使用的优惠券 Redis 访问对象
    参数说明：无
    返回值说明：返回 RedisCouponStore；测试环境返回进程内原子实现
    核心逻辑：按应用实例缓存连接，避免每个请求重复创建 Redis 客户端
    异常或失败情况：非测试环境连接 Redis 失败时由调用业务返回系统繁忙
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    extension_key = "nayami_coupon_redis"
    if extension_key in current_app.extensions:
        return current_app.extensions[extension_key]
    if current_app.testing:
        store = InMemoryCouponRedisStore()
    else:
        store = RedisCouponStore(
            current_app.config["REDIS_URL"],
            current_app.config["COUPON_IDEMPOTENCY_TTL_SECONDS"],
            current_app.config["COUPON_RESULT_TTL_SECONDS"],
        )
    current_app.extensions[extension_key] = store
    return store


def _stock_key(activity_id: int) -> str:
    return f"coupon:activity:{activity_id}:stock"


def _users_key(activity_id: int) -> str:
    return f"coupon:activity:{activity_id}:users"


def _success_key(activity_id: int) -> str:
    return f"coupon:activity:{activity_id}:success"


def _stats_key(activity_id: int) -> str:
    return f"coupon:activity:{activity_id}:stats"


def _idempotency_key(activity_id: int, user_id: int, request_id: str) -> str:
    return f"coupon:claim:{activity_id}:{user_id}:idem:{request_id}"


def _result_key(activity_id: int, user_id: int) -> str:
    return f"coupon:claim:{activity_id}:{user_id}:result"


def _reconcile_lock_key(activity_id: int) -> str:
    return f"coupon:activity:{activity_id}:reconcile:lock"
