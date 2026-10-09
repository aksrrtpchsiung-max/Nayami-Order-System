-- 文件名称：002_seed_demo_data.sql
-- 文件用途：初始化奈亚米最小交易闭环演示数据
-- 主要职责：创建演示角色、账号、三家门店、Bistro 双语菜单、门店库存和门店后台账号
-- 所属业务模块：数据库初始化
-- 创建时间：2026-05-22 14:05
-- 最近修改时间：2026-10-09 14:06
-- 修改人：Project Maintainers

USE nayami_order_system;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

INSERT INTO roles (id, role_code, role_name, description, permission_codes)
VALUES
  (1, 'store_staff', '门店员工', '处理所属门店订单履约', JSON_ARRAY('store:orders:read', 'store:orders:update')),
  (2, 'store_manager', '门店经理', '处理订单并维护所属门店运营状态', JSON_ARRAY('store:orders:read', 'store:orders:update', 'store:inventory:update')),
  (3, 'brand_admin', '品牌管理员', '管理品牌菜单、门店和运营数据', JSON_ARRAY('brand:manage')),
  (4, 'system_admin', '系统管理员', '管理账号、角色和系统配置', JSON_ARRAY('system:manage'))
ON DUPLICATE KEY UPDATE id = id;

INSERT INTO users (id, username, phone, password_hash, user_type, default_language, is_active)
VALUES
  (1, 'customer_demo', '18800000001', 'pbkdf2:sha256:600000$3RkeOwJDnrvEELzm$a062857145929b1db27853a20205580187930b87e983246b86e4d6de1507c344', 'customer', 'zh-CN', 1),
  (2, 'store_staff_demo', '18800000002', 'pbkdf2:sha256:600000$AHJXVYQ7AXXojl7f$778f66faff3bc6c826ad81670f7cd81b636b580b27ce69cf795df9f906290c06', 'staff', 'zh-CN', 1),
  (3, 'store_manager_001', '18800000003', 'pbkdf2:sha256:600000$AHJXVYQ7AXXojl7f$778f66faff3bc6c826ad81670f7cd81b636b580b27ce69cf795df9f906290c06', 'staff', 'zh-CN', 1),
  (4, 'brand_admin', '18800000004', 'pbkdf2:sha256:600000$lfpxjStUF8c2mzqo$78e4635e4b1f2d6b8b95279624bb5ca0b3d722518c4d0b6dd09ada02c8ea0357', 'admin', 'zh-CN', 1),
  (5, 'system_admin', '18800000005', 'pbkdf2:sha256:600000$lfpxjStUF8c2mzqo$78e4635e4b1f2d6b8b95279624bb5ca0b3d722518c4d0b6dd09ada02c8ea0357', 'admin', 'zh-CN', 1)
ON DUPLICATE KEY UPDATE id = id;

INSERT INTO stores (id, store_code, name_zh, name_en, address, phone, business_start_time, business_end_time, store_status, is_active)
VALUES
  (1, 'NYM-CBD-001', '奈亚米中央公园店', 'Nayami Central Park', '中央公园商业街 18 号', '021-88000001', '00:00:00', '23:59:00', 'open', 1),
  (2, 'NYM-RD-002', '奈亚米河畔店', 'Nayami Riverside', '河畔路 66 号', '021-88000002', '00:00:00', '23:59:00', 'open', 1),
  (3, 'NYM-UNI-003', '奈亚米大学城店', 'Nayami University Town', '学府大道 88 号', '021-88000003', '00:00:00', '23:59:00', 'open', 1)
ON DUPLICATE KEY UPDATE id = id;

-- 已有账号的角色与门店绑定由后台维护，重复种子不能恢复已撤销权限。
INSERT INTO user_roles (user_id, role_id)
SELECT users.id, roles.id FROM users
JOIN roles ON roles.role_code = CASE users.username
  WHEN 'store_staff_demo' THEN 'store_staff'
  WHEN 'store_manager_001' THEN 'store_manager'
  WHEN 'brand_admin' THEN 'brand_admin'
  WHEN 'system_admin' THEN 'system_admin' END
WHERE NOT EXISTS (SELECT 1 FROM user_roles existing WHERE existing.user_id = users.id);

INSERT INTO user_store_bindings (user_id, store_id, binding_type, is_active)
SELECT users.id, stores.id, IF(users.username = 'store_staff_demo', 'staff', 'manager'), 1
FROM users JOIN stores ON stores.store_code = 'NYM-CBD-001'
WHERE users.username IN ('store_staff_demo', 'store_manager_001')
AND NOT EXISTS (SELECT 1 FROM user_store_bindings existing WHERE existing.user_id = users.id);

INSERT INTO product_categories (id, name_zh, name_en, sort_order, is_active)
VALUES
  (1, '暖心浓汤', 'Warm Soups', 10, 1),
  (2, '清爽轻食沙拉', 'Fresh Salads', 20, 1),
  (3, '人气小食＆精致吐司', 'Popular Snacks & Toasts', 30, 1),
  (4, '元气早午餐', 'Vital Brunch', 40, 1),
  (5, '臻选主排·招牌硬菜', 'Signature Main Courses', 50, 1),
  (6, '意式烩饭·招牌意面', 'Italian Pasta & Risotto', 60, 1),
  (7, '特色菜·西班牙海鲜饭系列', 'Specialties · Spanish Seafood Paella', 70, 1),
  (8, '手工现烤披萨', 'Handmade Fresh Baked Pizza', 80, 1),
  (9, '特色帕尼尼·手工汉堡', 'Special Panini & Handmade Burgers', 90, 1)
ON DUPLICATE KEY UPDATE id = id;

INSERT INTO products (id, category_id, name_zh, name_en, description_zh, description_en, image_url, base_price, menu_status, sort_order)
VALUES
  (1, 1, '法式奶油蘑菇汤', 'French Cream of Mushroom Soup', '蘑菇慢煮成细腻奶油浓汤，口感温润醇厚。', 'Slow-cooked mushrooms blended into a smooth and comforting cream soup.', '/menu-images/french-cream-of-mushroom-soup.jpg', 38.00, 'published', 10),
  (2, 1, '奶油金瓜汤', 'Creamy Pumpkin Soup', '金瓜与奶油慢煮，呈现自然清甜与绵密口感。', 'Pumpkin and cream simmered into a naturally sweet, velvety soup.', '/menu-images/creamy-pumpkin-soup.jpg', 32.00, 'published', 20),
  (3, 1, '意大利番茄汤', 'Italian Tomato Soup', '番茄与香草慢煮，酸甜平衡、清新开胃。', 'Tomatoes and herbs simmered for a bright, balanced and appetizing soup.', '/menu-images/italian-tomato-soup.jpg', 38.00, 'published', 30),
  (4, 2, '金枪鱼尼斯沙拉', 'Tuna Niçoise Salad', '金枪鱼搭配时蔬、鸡蛋与橄榄，风味清爽丰富。', 'Tuna with vegetables, egg and olives in a fresh, satisfying Niçoise salad.', '/menu-images/tuna-ni-oise-salad.jpg', 58.00, 'published', 10),
  (5, 2, '芒果大虾牛油果沙拉', 'Mango Prawn & Avocado Salad', '鲜虾、芒果与牛油果组合，清甜鲜嫩。', 'Prawns, mango and avocado combined for a fresh and gently sweet salad.', '/menu-images/mango-prawn-avocado-salad.jpg', 78.00, 'published', 20),
  (6, 2, '蔓越莓山羊奶酪沙拉', 'Cranberry & Goat Cheese Salad', '蔓越莓与山羊奶酪搭配鲜嫩叶菜，酸甜柔和。', 'Cranberries and goat cheese served with tender greens for a mellow sweet-tart balance.', '/menu-images/cranberry-goat-cheese-salad.jpg', 58.00, 'published', 30),
  (7, 2, '芝麻菜圣达涅火腿沙拉', 'Arugula & San Daniele Ham Salad', '芝麻菜搭配圣达涅火腿，咸香清爽。', 'Peppery arugula paired with savory San Daniele ham.', '/menu-images/arugula-san-daniele-ham-salad.jpg', 68.00, 'published', 40),
  (8, 2, '培根土豆泥沙拉', 'Bacon Mashed Potato Salad', '绵密土豆泥搭配香脆培根，口感浓郁。', 'Creamy mashed potato finished with crisp, savory bacon.', '/menu-images/bacon-mashed-potato-salad.jpg', 48.00, 'published', 50),
  (9, 3, '火炙焦糖三文鱼吐司', 'Torched Caramel Salmon Toast', '火炙三文鱼铺于香烤吐司，焦香与鲜嫩交织。', 'Torched salmon on toasted bread with caramelized aroma and tender texture.', '/menu-images/torched-caramel-salmon-toast.jpg', 68.00, 'published', 10),
  (10, 3, '香煎鹅肝佐苹果泥配蔓越莓酱', 'Pan-Seared Foie Gras with Apple Purée & Cranberry Sauce', '香煎鹅肝搭配苹果泥与蔓越莓酱，丰润而不失清甜。', 'Pan-seared foie gras balanced with apple purée and cranberry sauce.', '/menu-images/pan-seared-foie-gras-with-apple-pur-e-cranberry-sauce.jpg', 78.00, 'published', 20),
  (11, 3, '金枪鱼可颂', 'Tuna Croissant', '酥香可颂夹入金枪鱼馅料，轻盈可口。', 'A flaky croissant filled with a light and savory tuna mixture.', '/menu-images/tuna-croissant.jpg', 48.00, 'published', 30),
  (12, 3, '牛油果培根滑蛋吐司', 'Avocado, Bacon & Scrambled Egg Toast', '牛油果、培根与滑蛋铺于吐司，层次丰富。', 'Avocado, bacon and soft scrambled egg layered on toasted bread.', '/menu-images/avocado-bacon-scrambled-egg-toast.jpg', 58.00, 'published', 40),
  (13, 3, '松露薯条', 'Truffle Fries', '金黄薯条拌入松露风味，外酥内软。', 'Golden fries tossed with aromatic truffle seasoning.', '/menu-images/truffle-fries.jpg', 38.00, 'published', 50),
  (14, 3, '西班牙橄榄油蒜香煎虾', 'Spanish Garlic Shrimp Sautéed in Olive Oil', '鲜虾以橄榄油和蒜香煎制，鲜香浓郁。', 'Prawns sautéed with olive oil and garlic in a Spanish-inspired style.', '/menu-images/spanish-garlic-shrimp-saut-ed-in-olive-oil.jpg', 78.00, 'published', 60),
  (15, 3, '脆炸鱿鱼须', 'Crispy Fried Squid Tentacles', '鱿鱼须酥炸至金黄，外脆里嫩。', 'Squid tentacles fried until crisp outside and tender within.', '/menu-images/crispy-fried-squid-tentacles.jpg', 58.00, 'published', 70),
  (16, 3, '火腿芝士丸', 'Ham & Cheese Balls', '火腿与芝士制成酥香小丸，咸香浓郁。', 'Crisp bite-sized balls filled with savory ham and cheese.', '/menu-images/ham-cheese-balls.jpg', 58.00, 'published', 80),
  (17, 3, '芝士焗蘑菇', 'Baked Mushrooms with Cheese', '蘑菇覆以芝士焗烤，鲜香拉丝。', 'Mushrooms baked under melted cheese for a rich savory bite.', '/menu-images/baked-mushrooms-with-cheese.jpg', 48.00, 'published', 90),
  (18, 3, '松露菌菇塔塔', 'Truffle Mushroom Tartare', '细切菌菇融入松露香气，口感细腻。', 'Finely chopped mushrooms finished with aromatic truffle.', '/menu-images/truffle-mushroom-tartare.jpg', 32.00, 'published', 100),
  (19, 4, '经典英式全日早午餐拼盘', 'Classic Full English Brunch Platter', '鸡蛋、香肠、培根、豆子、蘑菇与吐司组成经典英式拼盘。', 'Eggs, sausage, bacon, beans, mushrooms and toast in a classic full English platter.', '/menu-images/vital-brunch.jpg', 78.00, 'published', 10),
  (20, 5, '法式迷迭香煎羊排', 'Pan-Fried Lamb Chops with Rosemary', '羊排配迷迭香香煎，肉香浓郁、外焦里嫩。', 'Lamb chops pan-fried with rosemary until caramelized outside and tender within.', '/menu-images/pan-fried-lamb-chops-with-rosemary.jpg', 118.00, 'published', 10),
  (21, 5, '澳洲谷饲M3+肉眼牛排', 'Australian Grain-Fed M3+ Ribeye Steak', '澳洲谷饲M3+肉眼牛排，油花丰润、肉香饱满。', 'Australian grain-fed M3+ ribeye with rich marbling and full beef flavor.', '/menu-images/australian-grain-fed-m3-ribeye-steak.jpg', 268.00, 'published', 20),
  (22, 5, '澳洲谷饲M3+西冷牛排', 'Australian Grain-Fed M3+ Sirloin Steak', '澳洲谷饲M3+西冷牛排，肉质紧实、香气浓郁。', 'Australian grain-fed M3+ sirloin with a firm bite and pronounced beef flavor.', '/menu-images/australian-grain-fed-m3-sirloin-steak.jpg', 238.00, 'published', 30),
  (23, 5, '香煎三文鱼排', 'Pan-Seared Salmon Fillet', '三文鱼煎至表面焦香，鱼肉柔嫩多汁。', 'Salmon fillet pan-seared for a crisp surface and tender, juicy center.', '/menu-images/pan-seared-salmon-fillet.jpg', 128.00, 'published', 40),
  (24, 5, '德式风味香肠拼盘（配土豆泥、酸菜、酸黄瓜）', 'German Sausage Platter', '德式香肠搭配土豆泥、酸菜与酸黄瓜，咸香丰盛。', 'German sausages served with mashed potato, sauerkraut and pickles.', '/menu-images/german-sausage-platter.jpg', 78.00, 'published', 50),
  (25, 6, '奶油松露菌菇意面', 'Creamy Truffle Mushroom Pasta', '奶油酱包裹意面与菌菇，松露香气馥郁。', 'Pasta and mushrooms coated in a creamy, aromatic truffle sauce.', '/menu-images/creamy-truffle-mushroom-pasta.jpg', 58.00, 'published', 10),
  (26, 6, '经典肉酱意面', 'Classic Bolognese Pasta', '慢煮肉酱搭配意面，浓郁经典。', 'Pasta served with a rich, slow-cooked classic Bolognese sauce.', '/menu-images/classic-bolognese-pasta.jpg', 58.00, 'published', 20),
  (27, 6, '热那亚罗勒青酱意面', 'Genoese Basil Pesto Pasta', '罗勒青酱拌入意面，草本清香明亮。', 'Pasta tossed with fragrant Genoese basil pesto.', '/menu-images/genoese-basil-pesto-pasta.jpg', 58.00, 'published', 30),
  (28, 6, '培根菌菇芝士烩饭', 'Bacon, Mushroom & Cheese Risotto', '培根、菌菇与芝士融入奶香烩饭，绵密醇厚。', 'Creamy risotto enriched with bacon, mushrooms and cheese.', '/menu-images/bacon-mushroom-cheese-risotto.jpg', 58.00, 'published', 40),
  (29, 7, '传统西班牙海鲜饭（两人份）', 'Traditional Spanish Seafood Paella', '藏红花米饭搭配丰富海鲜，适合两人分享。', 'Saffron rice with assorted seafood, prepared as a generous two-person paella.', '/menu-images/traditional-spanish-seafood-paella.jpg', 168.00, 'published', 10),
  (30, 7, '西班牙墨鱼汁海鲜饭（两人份）', 'Spanish Squid Ink Seafood Paella', '墨鱼汁米饭搭配丰富海鲜，鲜味浓郁，适合两人分享。', 'Squid-ink rice with assorted seafood, served as a bold two-person paella.', '/menu-images/spanish-squid-ink-seafood-paella.jpg', 178.00, 'published', 20),
  (31, 8, '榴莲多多披萨', 'Durian Supreme Pizza', '榴莲果肉铺满现烤披萨，香甜浓郁。', 'Fresh-baked pizza generously topped with rich, creamy durian.', '/menu-images/durian-supreme-pizza.jpg', 68.00, 'published', 10),
  (32, 8, '意大利萨拉米披萨', 'Italian Salami Pizza', '萨拉米与芝士搭配现烤薄底，咸香浓郁。', 'Fresh-baked thin-crust pizza topped with Italian salami and cheese.', '/menu-images/italian-salami-pizza.jpg', 68.00, 'published', 20),
  (33, 8, '奶黄香芒披萨', 'Custard & Mango Pizza', '奶黄与香芒组合，香甜柔滑。', 'Creamy custard and fragrant mango on a fresh-baked pizza base.', '/menu-images/custard-mango-pizza.jpg', 68.00, 'published', 30),
  (34, 8, '榴芒披萨', 'Durian & Mango Pizza', '榴莲与芒果双重果香，甜润浓郁。', 'Durian and mango combine for a rich, fruit-forward dessert pizza.', '/menu-images/durian-mango-pizza.jpg', 68.00, 'published', 40),
  (35, 8, '墨鱼汁海鲜披萨', 'Squid Ink Seafood Pizza', '墨鱼汁饼底搭配鲜虾与鱿鱼，海味鲜明。', 'Squid-ink pizza topped with prawns and squid for a distinctive seafood flavor.', '/menu-images/squid-ink-seafood-pizza.jpg', 78.00, 'published', 50),
  (36, 8, '松露野菌火焰薄饼', 'Truffle & Wild Mushroom Flamed Flatbread', '野菌与松露铺于火焰薄饼，菌香浓郁。', 'Flamed flatbread topped with wild mushrooms and aromatic truffle.', '/menu-images/truffle-wild-mushroom-flamed-flatbread.jpg', 58.00, 'published', 60),
  (37, 8, '帕尔马火腿火焰薄饼', 'Parma Ham Flamed Flatbread', '帕尔马火腿搭配现烤火焰薄饼，咸香轻盈。', 'Fresh flamed flatbread finished with delicate Parma ham.', '/menu-images/parma-ham-flamed-flatbread.jpg', 68.00, 'published', 70),
  (38, 9, '焦糖洋葱牛肉帕尼尼', 'Caramelized Onion Beef Panini', '牛肉与焦糖洋葱夹入压烤面包，香甜咸香。', 'Pressed panini filled with beef and sweet-savory caramelized onions.', '/menu-images/caramelized-onion-beef-panini.jpg', 48.00, 'published', 10),
  (39, 9, '青酱烤鸡胸帕尼尼', 'Pesto Grilled Chicken Panini', '烤鸡胸搭配罗勒青酱，清香柔嫩。', 'Grilled chicken breast paired with fragrant basil pesto in a pressed panini.', '/menu-images/pesto-grilled-chicken-panini.jpg', 38.00, 'published', 20),
  (40, 9, '经典纯牛肉汉堡', 'Classic Beef Burger', '纯牛肉饼搭配新鲜蔬菜与柔软面包，经典满足。', 'A pure beef patty with fresh vegetables in a soft classic burger bun.', '/menu-images/classic-beef-burger.jpg', 58.00, 'published', 30)
ON DUPLICATE KEY UPDATE id = id;

INSERT INTO store_products (id, store_id, product_id, is_available, current_stock, reserved_stock, is_sold_out)
VALUES
  (1, 1, 1, 1, 80, 0, 0),
  (2, 1, 2, 1, 60, 0, 0),
  (3, 1, 3, 1, 120, 0, 0),
  (4, 1, 4, 1, 100, 0, 0),
  (5, 2, 1, 1, 50, 0, 0),
  (6, 2, 3, 1, 80, 0, 0),
  (7, 1, 5, 1, 70, 0, 0),
  (8, 1, 6, 1, 45, 0, 0),
  (9, 1, 7, 1, 90, 0, 0),
  (10, 1, 8, 1, 65, 0, 0),
  (11, 2, 2, 1, 45, 0, 0),
  (12, 2, 4, 1, 70, 0, 0),
  (13, 2, 5, 1, 55, 0, 0),
  (14, 2, 7, 1, 85, 0, 0),
  (15, 2, 8, 1, 50, 0, 0),
  (16, 3, 1, 1, 60, 0, 0),
  (17, 3, 2, 1, 55, 0, 0),
  (18, 3, 3, 1, 100, 0, 0),
  (19, 3, 4, 1, 80, 0, 0),
  (20, 3, 5, 1, 65, 0, 0),
  (21, 3, 6, 1, 40, 0, 0),
  (22, 3, 7, 1, 90, 0, 0),
  (23, 3, 8, 1, 60, 0, 0),
  (24, 2, 6, 1, 40, 0, 0),
  (25, 1, 9, 1, 60, 0, 0),
  (26, 1, 10, 1, 40, 0, 0),
  (27, 1, 11, 1, 70, 0, 0),
  (28, 1, 12, 1, 65, 0, 0),
  (29, 1, 13, 1, 100, 0, 0),
  (30, 1, 14, 1, 55, 0, 0),
  (31, 1, 15, 1, 70, 0, 0),
  (32, 1, 16, 1, 75, 0, 0),
  (33, 1, 17, 1, 60, 0, 0),
  (34, 1, 18, 1, 65, 0, 0),
  (35, 1, 19, 1, 50, 0, 0),
  (36, 1, 20, 1, 45, 0, 0),
  (37, 1, 21, 1, 35, 0, 0),
  (38, 1, 22, 1, 35, 0, 0),
  (39, 1, 23, 1, 45, 0, 0),
  (40, 1, 24, 1, 55, 0, 0),
  (41, 1, 25, 1, 75, 0, 0),
  (42, 1, 26, 1, 75, 0, 0),
  (43, 1, 27, 1, 75, 0, 0),
  (44, 1, 28, 1, 70, 0, 0),
  (45, 1, 29, 1, 30, 0, 0),
  (46, 1, 30, 1, 30, 0, 0),
  (47, 1, 31, 1, 60, 0, 0),
  (48, 1, 32, 1, 60, 0, 0),
  (49, 1, 33, 1, 60, 0, 0),
  (50, 1, 34, 1, 60, 0, 0),
  (51, 1, 35, 1, 50, 0, 0),
  (52, 1, 36, 1, 65, 0, 0),
  (53, 1, 37, 1, 65, 0, 0),
  (54, 1, 38, 1, 70, 0, 0),
  (55, 1, 39, 1, 70, 0, 0),
  (56, 1, 40, 1, 70, 0, 0),
  (57, 2, 9, 1, 45, 0, 0),
  (58, 2, 10, 1, 30, 0, 0),
  (59, 2, 11, 1, 55, 0, 0),
  (60, 2, 12, 1, 50, 0, 0),
  (61, 2, 13, 1, 80, 0, 0),
  (62, 2, 14, 1, 40, 0, 0),
  (63, 2, 15, 1, 55, 0, 0),
  (64, 2, 16, 1, 55, 0, 0),
  (65, 2, 17, 1, 45, 0, 0),
  (66, 2, 18, 1, 50, 0, 0),
  (67, 2, 19, 1, 40, 0, 0),
  (68, 2, 20, 1, 30, 0, 0),
  (69, 2, 21, 1, 0, 0, 1),
  (70, 2, 22, 1, 25, 0, 0),
  (71, 2, 23, 1, 35, 0, 0),
  (72, 2, 24, 1, 45, 0, 0),
  (73, 2, 25, 1, 55, 0, 0),
  (74, 2, 26, 1, 55, 0, 0),
  (75, 2, 27, 1, 55, 0, 0),
  (76, 2, 28, 1, 50, 0, 0),
  (77, 2, 29, 1, 20, 0, 0),
  (78, 2, 30, 0, 15, 0, 0),
  (79, 2, 31, 1, 45, 0, 0),
  (80, 2, 32, 1, 45, 0, 0),
  (81, 2, 33, 1, 45, 0, 0),
  (82, 2, 34, 1, 45, 0, 0),
  (83, 2, 35, 1, 35, 0, 0),
  (84, 2, 36, 1, 50, 0, 0),
  (85, 2, 37, 1, 50, 0, 0),
  (86, 2, 38, 1, 55, 0, 0),
  (87, 2, 39, 1, 55, 0, 0),
  (88, 2, 40, 1, 55, 0, 0),
  (89, 3, 9, 1, 50, 0, 0),
  (90, 3, 10, 1, 35, 0, 0),
  (91, 3, 11, 1, 60, 0, 0),
  (92, 3, 12, 1, 55, 0, 0),
  (93, 3, 13, 1, 85, 0, 0),
  (94, 3, 14, 1, 45, 0, 0),
  (95, 3, 15, 1, 60, 0, 0),
  (96, 3, 16, 1, 60, 0, 0),
  (97, 3, 17, 1, 50, 0, 0),
  (98, 3, 18, 1, 55, 0, 0),
  (99, 3, 19, 1, 45, 0, 0),
  (100, 3, 20, 1, 35, 0, 0),
  (101, 3, 21, 1, 25, 0, 0),
  (102, 3, 22, 1, 25, 0, 0),
  (103, 3, 23, 1, 35, 0, 0),
  (104, 3, 24, 1, 50, 0, 0),
  (105, 3, 25, 1, 60, 0, 0),
  (106, 3, 26, 1, 60, 0, 0),
  (107, 3, 27, 1, 60, 0, 0),
  (108, 3, 28, 1, 55, 0, 0),
  (109, 3, 29, 1, 25, 0, 0),
  (110, 3, 30, 1, 25, 0, 0),
  (111, 3, 31, 1, 0, 0, 1),
  (112, 3, 32, 1, 50, 0, 0),
  (113, 3, 33, 1, 50, 0, 0),
  (114, 3, 34, 1, 50, 0, 0),
  (115, 3, 35, 1, 40, 0, 0),
  (116, 3, 36, 1, 55, 0, 0),
  (117, 3, 37, 1, 55, 0, 0),
  (118, 3, 38, 1, 60, 0, 0),
  (119, 3, 39, 1, 60, 0, 0),
  (120, 3, 40, 1, 60, 0, 0)
ON DUPLICATE KEY UPDATE id = id;

SET FOREIGN_KEY_CHECKS = 1;
