-- 文件名称：claim_coupon.lua
-- 文件用途：原子完成优惠券库存判断、扣减、防重复领取和短期幂等记录
-- 修改人：Project Maintainers
-- 最近修改时间：2026-10-09 14:06

local stock_key = KEYS[1]
local users_key = KEYS[2]
local success_key = KEYS[3]
local stats_key = KEYS[4]
local idempotency_key = KEYS[5]
local result_key = KEYS[6]

local user_id = ARGV[1]
local success_time = ARGV[2]
local idempotency_ttl = tonumber(ARGV[3])
local result_ttl = tonumber(ARGV[4])

local previous_result = redis.call("GET", idempotency_key)
if previous_result then
    local current_stock = redis.call("GET", stock_key)
    if previous_result == "succeeded" then
        return {3, current_stock or ""}
    elseif previous_result == "not_warmed" then
        return {-1, ""}
    elseif previous_result == "sold_out" then
        return {0, 0}
    elseif previous_result == "already_claimed" then
        return {2, current_stock or ""}
    end
end

redis.call("SET", idempotency_key, "processing", "EX", idempotency_ttl)

if redis.call("EXISTS", stock_key) == 0 then
    redis.call("SET", idempotency_key, "not_warmed", "EX", idempotency_ttl)
    return {-1, ""}
end

if redis.call("SISMEMBER", users_key, user_id) == 1 then
    redis.call("HINCRBY", stats_key, "already_claimed_count", 1)
    redis.call("SET", idempotency_key, "already_claimed", "EX", idempotency_ttl)
    return {2, redis.call("GET", stock_key)}
end

local stock = tonumber(redis.call("GET", stock_key))
if stock == nil or stock <= 0 then
    redis.call("HINCRBY", stats_key, "sold_out_count", 1)
    redis.call("SET", idempotency_key, "sold_out", "EX", idempotency_ttl)
    return {0, 0}
end

local remaining_stock = redis.call("DECR", stock_key)
redis.call("SADD", users_key, user_id)
redis.call("ZADD", success_key, success_time, user_id)
redis.call("HINCRBY", stats_key, "success_count", 1)
redis.call("HSET", stats_key, "last_claim_time", success_time)
redis.call("HSET", result_key, "result", "succeeded", "redis_success_time", success_time)
redis.call("EXPIRE", result_key, result_ttl)
redis.call("SET", idempotency_key, "succeeded", "EX", idempotency_ttl)
return {1, remaining_stock}
