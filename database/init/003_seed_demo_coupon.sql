-- 文件名称：003_seed_demo_coupon.sql
-- 文件用途：初始化可立即预热并演示抢券的优惠券活动
-- 主要职责：创建活动、适用门店和适用商品范围
-- 所属业务模块：数据库初始化
-- 创建时间：2026-07-28 13:01
-- 最近修改时间：2026-10-09 14:06
-- 修改人：Project Maintainers

USE nayami_order_system;

SET @nayami_coupon_seed_created = NOT EXISTS (SELECT 1 FROM coupon_activities WHERE id = 1);

INSERT INTO coupon_activities (
  id,
  activity_name_zh,
  activity_name_en,
  description_zh,
  description_en,
  start_at,
  end_at,
  total_stock,
  per_user_limit,
  discount_amount,
  minimum_order_amount,
  activity_status,
  created_by
)
VALUES (
  1,
  '城市连锁开业立减券',
  'City Launch Discount',
  '满 30 元立减 8 元，每位顾客限领一张。',
  'Save CNY 8 on orders over CNY 30. One coupon per customer.',
  DATE_SUB(NOW(), INTERVAL 1 DAY),
  DATE_ADD(NOW(), INTERVAL 30 DAY),
  1000,
  1,
  8.00,
  30.00,
  'active',
  4
)
ON DUPLICATE KEY UPDATE id = id;

INSERT INTO coupon_activity_stores (activity_id, store_id)
SELECT 1, seed.store_id FROM (SELECT 1 AS store_id UNION ALL SELECT 2 UNION ALL SELECT 3) seed
WHERE @nayami_coupon_seed_created;

INSERT INTO coupon_activity_products (activity_id, product_id)
SELECT 1, seed.product_id FROM (SELECT 1 AS product_id UNION ALL SELECT 2 UNION ALL SELECT 5 UNION ALL SELECT 6) seed
WHERE @nayami_coupon_seed_created;
