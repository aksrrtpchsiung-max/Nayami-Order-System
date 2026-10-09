-- 文件名称：001_create_database.sql
-- 文件用途：创建奈亚米城市连锁餐饮点餐与门店运营系统第一版 MySQL 数据库结构
-- 主要职责：创建用户权限、门店商品、订单支付、库存日志、优惠券抢券、异步落库任务和审计日志等核心表
-- 所属业务模块：数据库初始化
-- 创建时间：2026-05-21 19:17
-- 最近修改时间：2026-10-09 14:06
-- 修改人：Project Maintainers

CREATE DATABASE IF NOT EXISTS nayami_order_system
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE nayami_order_system;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户 ID',
  username VARCHAR(64) NOT NULL COMMENT '登录名或展示名',
  phone VARCHAR(32) NULL COMMENT '手机号',
  password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
  user_type VARCHAR(32) NOT NULL COMMENT '用户类型：customer、staff、admin',
  default_language VARCHAR(16) NOT NULL DEFAULT 'zh-CN' COMMENT '默认语言',
  is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  token_version INT NOT NULL DEFAULT 0 COMMENT '会话撤销版本',
  last_login_at DATETIME NULL COMMENT '最近登录时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username),
  UNIQUE KEY uk_users_phone (phone),
  KEY idx_users_user_type_active (user_type, is_active),
  CHECK (user_type IN ('customer', 'staff', 'admin')),
  CHECK (default_language IN ('zh-CN', 'en-US'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

CREATE TABLE IF NOT EXISTS roles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '角色 ID',
  role_code VARCHAR(64) NOT NULL COMMENT '角色编码',
  role_name VARCHAR(128) NOT NULL COMMENT '角色名称',
  description VARCHAR(255) NULL COMMENT '角色说明',
  permission_codes JSON NULL COMMENT '权限点集合',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_roles_role_code (role_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

CREATE TABLE IF NOT EXISTS stores (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '门店 ID',
  store_code VARCHAR(64) NOT NULL COMMENT '门店编码',
  name_zh VARCHAR(128) NOT NULL COMMENT '门店中文名称',
  name_en VARCHAR(128) NULL COMMENT '门店英文名称',
  address VARCHAR(255) NOT NULL COMMENT '门店地址',
  phone VARCHAR(32) NULL COMMENT '门店联系电话',
  business_start_time TIME NOT NULL DEFAULT '09:00:00' COMMENT '营业开始时间',
  business_end_time TIME NOT NULL DEFAULT '22:00:00' COMMENT '营业结束时间',
  store_status VARCHAR(32) NOT NULL DEFAULT 'open' COMMENT '门店状态',
  temporary_close_reason VARCHAR(255) NULL COMMENT '临时关闭原因',
  is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stores_store_code (store_code),
  KEY idx_stores_status (store_status, is_active),
  CHECK (store_status IN ('open', 'closed', 'temporarily_closed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店表';

CREATE TABLE IF NOT EXISTS user_roles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户角色关联 ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户 ID',
  role_id BIGINT UNSIGNED NOT NULL COMMENT '角色 ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_roles_user_role (user_id, role_id),
  KEY idx_user_roles_role_id (role_id),
  CONSTRAINT fk_user_roles_user_id FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_user_roles_role_id FOREIGN KEY (role_id) REFERENCES roles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

CREATE TABLE IF NOT EXISTS user_store_bindings (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户门店绑定 ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '后台用户 ID',
  store_id BIGINT UNSIGNED NOT NULL COMMENT '门店 ID',
  binding_type VARCHAR(32) NOT NULL COMMENT '绑定类型：staff、manager',
  is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否有效',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_store_bindings_user_store_type (user_id, store_id, binding_type),
  KEY idx_user_store_bindings_store_id (store_id, is_active),
  CONSTRAINT fk_user_store_bindings_user_id FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_user_store_bindings_store_id FOREIGN KEY (store_id) REFERENCES stores (id),
  CHECK (binding_type IN ('staff', 'manager'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户门店绑定表';

CREATE TABLE IF NOT EXISTS product_categories (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '商品分类 ID',
  name_zh VARCHAR(128) NOT NULL COMMENT '分类中文名称',
  name_en VARCHAR(128) NULL COMMENT '分类英文名称',
  sort_order INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '展示排序',
  is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_product_categories_sort_order (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品分类表';

CREATE TABLE IF NOT EXISTS products (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '商品 ID',
  category_id BIGINT UNSIGNED NOT NULL COMMENT '商品分类 ID',
  name_zh VARCHAR(128) NOT NULL COMMENT '商品中文名称',
  name_en VARCHAR(128) NULL COMMENT '商品英文名称',
  description_zh TEXT NULL COMMENT '商品中文描述',
  description_en TEXT NULL COMMENT '商品英文描述',
  image_url VARCHAR(512) NULL COMMENT '商品图片地址',
  base_price DECIMAL(10,2) NOT NULL COMMENT '品牌统一价格',
  pending_changes JSON NULL COMMENT '待发布变更；现有业务字段保存线上版本',
  menu_status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '菜单状态',
  sort_order INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '分类内排序',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_products_category_status_sort (category_id, menu_status, sort_order),
  CONSTRAINT fk_products_category_id FOREIGN KEY (category_id) REFERENCES product_categories (id),
  CHECK (base_price >= 0),
  CHECK (menu_status IN ('draft', 'published', 'draft_changes', 'archived'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品表';

CREATE TABLE IF NOT EXISTS store_products (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '门店商品 ID',
  store_id BIGINT UNSIGNED NOT NULL COMMENT '门店 ID',
  product_id BIGINT UNSIGNED NOT NULL COMMENT '商品 ID',
  is_available TINYINT(1) NOT NULL DEFAULT 1 COMMENT '当前门店是否可售',
  current_stock INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '当前库存数量',
  reserved_stock INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '已预占库存数量',
  is_sold_out TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否手动售罄',
  last_operator_id BIGINT UNSIGNED NULL COMMENT '最近操作人 ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_store_products_store_product (store_id, product_id),
  KEY idx_store_products_store_available (store_id, is_available, is_sold_out),
  KEY idx_store_products_product_id (product_id),
  KEY idx_store_products_last_operator_id (last_operator_id),
  CONSTRAINT fk_store_products_store_id FOREIGN KEY (store_id) REFERENCES stores (id),
  CONSTRAINT fk_store_products_product_id FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_store_products_last_operator_id FOREIGN KEY (last_operator_id) REFERENCES users (id),
  CHECK (reserved_stock <= current_stock)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店商品表';

CREATE TABLE IF NOT EXISTS coupon_activities (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '优惠券活动 ID',
  activity_name_zh VARCHAR(128) NOT NULL COMMENT '活动中文名称',
  activity_name_en VARCHAR(128) NULL COMMENT '活动英文名称',
  description_zh TEXT NULL COMMENT '活动中文说明',
  description_en TEXT NULL COMMENT '活动英文说明',
  start_at DATETIME NOT NULL COMMENT '活动开始时间',
  end_at DATETIME NOT NULL COMMENT '活动结束时间',
  total_stock INT UNSIGNED NOT NULL COMMENT '活动总库存',
  per_user_limit INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '每人限领数量',
  discount_amount DECIMAL(10,2) NOT NULL COMMENT '固定优惠金额',
  minimum_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '使用门槛',
  activity_status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '活动状态',
  created_by BIGINT UNSIGNED NULL COMMENT '创建人 ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_coupon_activities_status_time (activity_status, start_at, end_at),
  KEY idx_coupon_activities_created_by (created_by),
  CONSTRAINT fk_coupon_activities_created_by FOREIGN KEY (created_by) REFERENCES users (id),
  CHECK (end_at > start_at),
  CHECK (total_stock > 0),
  CHECK (per_user_limit >= 1),
  CHECK (discount_amount >= 0),
  CHECK (minimum_order_amount >= 0),
  CHECK (activity_status IN ('draft', 'scheduled', 'active', 'paused', 'ended', 'sold_out'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='优惠券活动表';

CREATE TABLE IF NOT EXISTS coupon_activity_stores (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '优惠券适用门店记录 ID',
  activity_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券活动 ID',
  store_id BIGINT UNSIGNED NOT NULL COMMENT '适用门店 ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_coupon_activity_stores_activity_store (activity_id, store_id),
  KEY idx_coupon_activity_stores_store_id (store_id),
  CONSTRAINT fk_coupon_activity_stores_activity_id FOREIGN KEY (activity_id) REFERENCES coupon_activities (id),
  CONSTRAINT fk_coupon_activity_stores_store_id FOREIGN KEY (store_id) REFERENCES stores (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='优惠券适用门店表';

CREATE TABLE IF NOT EXISTS coupon_activity_products (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '优惠券适用商品记录 ID',
  activity_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券活动 ID',
  product_id BIGINT UNSIGNED NOT NULL COMMENT '适用商品 ID',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_coupon_activity_products_activity_product (activity_id, product_id),
  KEY idx_coupon_activity_products_product_id (product_id),
  CONSTRAINT fk_coupon_activity_products_activity_id FOREIGN KEY (activity_id) REFERENCES coupon_activities (id),
  CONSTRAINT fk_coupon_activity_products_product_id FOREIGN KEY (product_id) REFERENCES products (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='优惠券适用商品表';

CREATE TABLE IF NOT EXISTS orders (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单 ID',
  order_no VARCHAR(64) NOT NULL COMMENT '订单编号',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '下单顾客 ID',
  store_id BIGINT UNSIGNED NOT NULL COMMENT '下单门店 ID',
  order_type VARCHAR(32) NOT NULL COMMENT '订单类型：dine_in、pickup',
  order_status VARCHAR(32) NOT NULL DEFAULT 'pending_payment' COMMENT '订单状态',
  items_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '商品总额',
  discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '优惠金额',
  payable_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '应付金额',
  user_coupon_id BIGINT UNSIGNED NULL COMMENT '使用的用户优惠券 ID',
  pickup_date DATE NULL COMMENT '取餐码所属付款自然日',
  pickup_code VARCHAR(32) NULL COMMENT '取餐码',
  remark VARCHAR(500) NULL COMMENT '订单备注',
  tableware_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '餐具数量',
  payment_deadline DATETIME NOT NULL COMMENT '支付截止时间',
  cancel_reason VARCHAR(255) NULL COMMENT '取消原因',
  paid_at DATETIME NULL COMMENT '支付成功时间',
  completed_at DATETIME NULL COMMENT '完成时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_orders_order_no (order_no),
  UNIQUE KEY uq_order_store_pickup_date_code (store_id, pickup_date, pickup_code),
  UNIQUE KEY uk_orders_store_pickup_code (store_id, pickup_code),
  KEY idx_orders_user_created_at (user_id, created_at),
  KEY idx_orders_store_status_created_at (store_id, order_status, created_at),
  KEY idx_orders_payment_deadline_status (payment_deadline, order_status),
  KEY idx_orders_user_coupon_id (user_coupon_id),
  CONSTRAINT fk_orders_user_id FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_orders_store_id FOREIGN KEY (store_id) REFERENCES stores (id),
  CHECK (order_type IN ('dine_in', 'pickup')),
  CHECK (order_status IN ('pending_payment', 'paid', 'accepted', 'preparing', 'ready', 'completed', 'canceled', 'refund_pending', 'refunded')),
  CHECK (items_amount >= 0),
  CHECK (discount_amount >= 0),
  CHECK (payable_amount >= 0),
  CHECK (payment_deadline > created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单表';

CREATE TABLE IF NOT EXISTS order_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单明细 ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '订单 ID',
  product_id BIGINT UNSIGNED NOT NULL COMMENT '商品 ID',
  store_product_id BIGINT UNSIGNED NOT NULL COMMENT '门店商品 ID',
  product_name_zh VARCHAR(128) NOT NULL COMMENT '商品中文名称快照',
  product_name_en VARCHAR(128) NULL COMMENT '商品英文名称快照',
  unit_price DECIMAL(10,2) NOT NULL COMMENT '下单时单价',
  quantity INT UNSIGNED NOT NULL COMMENT '购买数量',
  subtotal_amount DECIMAL(10,2) NOT NULL COMMENT '小计金额',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_order_items_order_id (order_id),
  KEY idx_order_items_product_created_at (product_id, created_at),
  KEY idx_order_items_store_product_id (store_product_id),
  CONSTRAINT fk_order_items_order_id FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_order_items_product_id FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_order_items_store_product_id FOREIGN KEY (store_product_id) REFERENCES store_products (id),
  CHECK (unit_price >= 0),
  CHECK (quantity > 0),
  CHECK (subtotal_amount >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单明细表';

CREATE TABLE IF NOT EXISTS payment_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '支付单 ID',
  payment_no VARCHAR(64) NOT NULL COMMENT '支付单编号',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '订单 ID',
  payment_method VARCHAR(32) NOT NULL COMMENT '支付方式',
  card_brand VARCHAR(32) NULL COMMENT '卡组织',
  masked_card_no VARCHAR(32) NULL COMMENT '脱敏卡号',
  payment_amount DECIMAL(10,2) NOT NULL COMMENT '支付金额',
  payment_status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '支付状态',
  transaction_no VARCHAR(128) NULL COMMENT '仿真交易流水号',
  idempotency_key VARCHAR(128) NULL COMMENT '支付回调幂等键',
  failure_reason VARCHAR(255) NULL COMMENT '失败原因',
  paid_at DATETIME NULL COMMENT '支付成功时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_payment_records_payment_no (payment_no),
  UNIQUE KEY uk_payment_records_transaction_no (transaction_no),
  UNIQUE KEY uk_payment_records_idempotency_key (idempotency_key),
  KEY idx_payment_records_order_id (order_id),
  KEY idx_payment_records_status_created_at (payment_status, created_at),
  CONSTRAINT fk_payment_records_order_id FOREIGN KEY (order_id) REFERENCES orders (id),
  CHECK (payment_method IN ('wechat', 'alipay', 'bank_card')),
  CHECK (payment_status IN ('pending', 'processing', 'succeeded', 'failed', 'canceled', 'expired')),
  CHECK (payment_amount >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='支付单表';

CREATE TABLE IF NOT EXISTS refund_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '退款记录 ID',
  refund_no VARCHAR(64) NOT NULL COMMENT '退款编号',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '订单 ID',
  payment_id BIGINT UNSIGNED NOT NULL COMMENT '支付单 ID',
  refund_amount DECIMAL(10,2) NOT NULL COMMENT '退款金额',
  refund_status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '退款状态',
  refund_reason VARCHAR(255) NULL COMMENT '退款原因',
  simulated_refund_no VARCHAR(128) NULL COMMENT '仿真退款流水号',
  refunded_at DATETIME NULL COMMENT '退款成功时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_refund_records_refund_no (refund_no),
  UNIQUE KEY uk_refund_records_simulated_refund_no (simulated_refund_no),
  KEY idx_refund_records_order_id (order_id),
  KEY idx_refund_records_payment_id (payment_id),
  CONSTRAINT fk_refund_records_order_id FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_refund_records_payment_id FOREIGN KEY (payment_id) REFERENCES payment_records (id),
  CHECK (refund_status IN ('pending', 'succeeded', 'failed')),
  CHECK (refund_amount >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='退款记录表';

CREATE TABLE IF NOT EXISTS user_coupons (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户优惠券 ID',
  activity_id BIGINT UNSIGNED NOT NULL COMMENT '来源活动 ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '领取用户 ID',
  discount_amount DECIMAL(10,2) NOT NULL COMMENT '优惠金额快照',
  minimum_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '使用门槛快照',
  coupon_status VARCHAR(32) NOT NULL DEFAULT 'syncing' COMMENT '用户优惠券状态',
  claimed_at DATETIME NOT NULL COMMENT '领取时间',
  used_order_id BIGINT UNSIGNED NULL COMMENT '使用订单 ID',
  used_at DATETIME NULL COMMENT '使用时间',
  expired_at DATETIME NULL COMMENT '过期时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_coupons_activity_user (activity_id, user_id),
  KEY idx_user_coupons_user_status_expired (user_id, coupon_status, expired_at),
  KEY idx_user_coupons_activity_status (activity_id, coupon_status),
  KEY idx_user_coupons_used_order_id (used_order_id),
  CONSTRAINT fk_user_coupons_activity_id FOREIGN KEY (activity_id) REFERENCES coupon_activities (id),
  CONSTRAINT fk_user_coupons_user_id FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_user_coupons_used_order_id FOREIGN KEY (used_order_id) REFERENCES orders (id),
  CHECK (discount_amount >= 0),
  CHECK (minimum_order_amount >= 0),
  CHECK (coupon_status IN ('syncing', 'available', 'used', 'expired', 'abnormal'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户优惠券表';

CREATE TABLE IF NOT EXISTS coupon_claim_tasks (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '抢券落库任务 ID',
  activity_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券活动 ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '领取用户 ID',
  user_coupon_id BIGINT UNSIGNED NULL COMMENT '落库成功后的用户优惠券 ID',
  redis_success_time DATETIME NOT NULL COMMENT 'Redis 判定成功时间',
  task_status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '任务状态',
  retry_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '重试次数',
  last_error TEXT NULL COMMENT '最近失败原因',
  next_retry_at DATETIME NULL COMMENT '下次重试时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_coupon_claim_tasks_activity_user (activity_id, user_id),
  KEY idx_coupon_claim_tasks_status_next_retry (task_status, next_retry_at),
  KEY idx_coupon_claim_tasks_activity_status (activity_id, task_status),
  KEY idx_coupon_claim_tasks_user_coupon_id (user_coupon_id),
  CONSTRAINT fk_coupon_claim_tasks_activity_id FOREIGN KEY (activity_id) REFERENCES coupon_activities (id),
  CONSTRAINT fk_coupon_claim_tasks_user_id FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_coupon_claim_tasks_user_coupon_id FOREIGN KEY (user_coupon_id) REFERENCES user_coupons (id),
  CHECK (task_status IN ('pending', 'processing', 'succeeded', 'failed', 'dead'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='抢券落库任务表';

CREATE TABLE IF NOT EXISTS inventory_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '库存日志 ID',
  store_id BIGINT UNSIGNED NOT NULL COMMENT '门店 ID',
  store_product_id BIGINT UNSIGNED NOT NULL COMMENT '门店商品 ID',
  order_id BIGINT UNSIGNED NULL COMMENT '关联订单 ID',
  change_type VARCHAR(32) NOT NULL COMMENT '库存变更类型',
  change_quantity INT UNSIGNED NOT NULL COMMENT '变更数量',
  before_current_stock INT UNSIGNED NOT NULL COMMENT '变更前当前库存',
  after_current_stock INT UNSIGNED NOT NULL COMMENT '变更后当前库存',
  before_reserved_stock INT UNSIGNED NOT NULL COMMENT '变更前预占库存',
  after_reserved_stock INT UNSIGNED NOT NULL COMMENT '变更后预占库存',
  operator_id BIGINT UNSIGNED NULL COMMENT '操作人 ID',
  remark VARCHAR(500) NULL COMMENT '备注',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_inventory_logs_store_product_created_at (store_product_id, created_at),
  KEY idx_inventory_logs_store_id (store_id, created_at),
  KEY idx_inventory_logs_order_id (order_id),
  KEY idx_inventory_logs_operator_id (operator_id),
  CONSTRAINT fk_inventory_logs_store_id FOREIGN KEY (store_id) REFERENCES stores (id),
  CONSTRAINT fk_inventory_logs_store_product_id FOREIGN KEY (store_product_id) REFERENCES store_products (id),
  CONSTRAINT fk_inventory_logs_order_id FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_inventory_logs_operator_id FOREIGN KEY (operator_id) REFERENCES users (id),
  CHECK (change_type IN ('reserve', 'confirm_deduct', 'release', 'refund_restore', 'manual_adjust')),
  CHECK (change_quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='库存日志表';

CREATE TABLE IF NOT EXISTS order_status_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单状态日志 ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '订单 ID',
  from_status VARCHAR(32) NULL COMMENT '原订单状态',
  to_status VARCHAR(32) NOT NULL COMMENT '新订单状态',
  trigger_type VARCHAR(32) NOT NULL COMMENT '触发类型',
  operator_id BIGINT UNSIGNED NULL COMMENT '操作人 ID',
  reason VARCHAR(255) NULL COMMENT '状态变化原因',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_order_status_logs_order_id (order_id),
  KEY idx_order_status_logs_operator_id (operator_id),
  CONSTRAINT fk_order_status_logs_order_id FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_order_status_logs_operator_id FOREIGN KEY (operator_id) REFERENCES users (id),
  CHECK (to_status IN ('pending_payment', 'paid', 'accepted', 'preparing', 'ready', 'completed', 'canceled', 'refund_pending', 'refunded')),
  CHECK (trigger_type IN ('customer', 'store_staff', 'store_manager', 'system', 'payment_callback'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单状态日志表';

CREATE TABLE IF NOT EXISTS payment_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '支付日志 ID',
  payment_id BIGINT UNSIGNED NOT NULL COMMENT '支付单 ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '订单 ID',
  from_status VARCHAR(32) NULL COMMENT '原支付状态',
  to_status VARCHAR(32) NOT NULL COMMENT '新支付状态',
  event_type VARCHAR(32) NOT NULL COMMENT '事件类型',
  idempotency_key VARCHAR(128) NULL COMMENT '幂等键',
  event_payload JSON NULL COMMENT '事件摘要',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_payment_logs_payment_id (payment_id),
  KEY idx_payment_logs_order_id (order_id),
  CONSTRAINT fk_payment_logs_payment_id FOREIGN KEY (payment_id) REFERENCES payment_records (id),
  CONSTRAINT fk_payment_logs_order_id FOREIGN KEY (order_id) REFERENCES orders (id),
  CHECK (to_status IN ('pending', 'processing', 'succeeded', 'failed', 'canceled', 'expired')),
  CHECK (event_type IN ('created', 'callback', 'timeout', 'retry', 'duplicate'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='支付日志表';

CREATE TABLE IF NOT EXISTS operation_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '操作日志 ID',
  operator_id BIGINT UNSIGNED NULL COMMENT '操作人 ID',
  operator_role_code VARCHAR(64) NULL COMMENT '操作时角色编码',
  operation_module VARCHAR(64) NOT NULL COMMENT '操作模块',
  operation_type VARCHAR(64) NOT NULL COMMENT '操作类型',
  target_id BIGINT UNSIGNED NULL COMMENT '操作对象 ID',
  store_id BIGINT UNSIGNED NULL COMMENT '关联门店 ID',
  before_snapshot JSON NULL COMMENT '操作前摘要',
  after_snapshot JSON NULL COMMENT '操作后摘要',
  operation_result VARCHAR(32) NOT NULL COMMENT '操作结果',
  failure_reason VARCHAR(255) NULL COMMENT '失败原因',
  ip_address VARCHAR(64) NULL COMMENT '请求来源 IP',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  PRIMARY KEY (id),
  KEY idx_operation_logs_module_created_at (operation_module, created_at),
  KEY idx_operation_logs_operator_created_at (operator_id, created_at),
  KEY idx_operation_logs_store_created_at (store_id, created_at),
  CONSTRAINT fk_operation_logs_operator_id FOREIGN KEY (operator_id) REFERENCES users (id),
  CONSTRAINT fk_operation_logs_store_id FOREIGN KEY (store_id) REFERENCES stores (id),
  CHECK (operation_result IN ('success', 'failed', 'rejected'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';


CREATE TABLE IF NOT EXISTS system_settings (
  `key` VARCHAR(64) NOT NULL,
  `value` JSON NOT NULL,
  updated_by BIGINT UNSIGNED NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`key`),
  CONSTRAINT fk_system_settings_updated_by FOREIGN KEY (updated_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统非交易配置';

SET FOREIGN_KEY_CHECKS = 1;
