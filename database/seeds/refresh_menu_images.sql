-- 文件名称：refresh_menu_images.sql
-- 文件用途：将演示菜单分类合照替换为对应菜品单品图
-- 主要职责：仅更新名称与旧图片均匹配的演示商品图片，保留自定义图片
-- 所属业务模块：菜单数据维护
-- 创建时间：2026-09-09 11:12
-- 最近修改时间：2026-10-09 14:06
-- 修改人：Project Maintainers

USE nayami_order_system;
SET NAMES utf8mb4;
START TRANSACTION;
UPDATE products SET image_url = '/menu-images/french-cream-of-mushroom-soup.jpg' WHERE id = 1 AND name_zh = '法式奶油蘑菇汤' AND image_url = '/menu-images/warm-soups.jpg';
UPDATE products SET image_url = '/menu-images/creamy-pumpkin-soup.jpg' WHERE id = 2 AND name_zh = '奶油金瓜汤' AND image_url = '/menu-images/warm-soups.jpg';
UPDATE products SET image_url = '/menu-images/italian-tomato-soup.jpg' WHERE id = 3 AND name_zh = '意大利番茄汤' AND image_url = '/menu-images/warm-soups.jpg';
UPDATE products SET image_url = '/menu-images/tuna-ni-oise-salad.jpg' WHERE id = 4 AND name_zh = '金枪鱼尼斯沙拉' AND image_url = '/menu-images/fresh-salads.jpg';
UPDATE products SET image_url = '/menu-images/mango-prawn-avocado-salad.jpg' WHERE id = 5 AND name_zh = '芒果大虾牛油果沙拉' AND image_url = '/menu-images/fresh-salads.jpg';
UPDATE products SET image_url = '/menu-images/cranberry-goat-cheese-salad.jpg' WHERE id = 6 AND name_zh = '蔓越莓山羊奶酪沙拉' AND image_url = '/menu-images/fresh-salads.jpg';
UPDATE products SET image_url = '/menu-images/arugula-san-daniele-ham-salad.jpg' WHERE id = 7 AND name_zh = '芝麻菜圣达涅火腿沙拉' AND image_url = '/menu-images/fresh-salads.jpg';
UPDATE products SET image_url = '/menu-images/bacon-mashed-potato-salad.jpg' WHERE id = 8 AND name_zh = '培根土豆泥沙拉' AND image_url = '/menu-images/fresh-salads.jpg';
UPDATE products SET image_url = '/menu-images/torched-caramel-salmon-toast.jpg' WHERE id = 9 AND name_zh = '火炙焦糖三文鱼吐司' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/pan-seared-foie-gras-with-apple-pur-e-cranberry-sauce.jpg' WHERE id = 10 AND name_zh = '香煎鹅肝佐苹果泥配蔓越莓酱' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/tuna-croissant.jpg' WHERE id = 11 AND name_zh = '金枪鱼可颂' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/avocado-bacon-scrambled-egg-toast.jpg' WHERE id = 12 AND name_zh = '牛油果培根滑蛋吐司' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/truffle-fries.jpg' WHERE id = 13 AND name_zh = '松露薯条' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/spanish-garlic-shrimp-saut-ed-in-olive-oil.jpg' WHERE id = 14 AND name_zh = '西班牙橄榄油蒜香煎虾' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/crispy-fried-squid-tentacles.jpg' WHERE id = 15 AND name_zh = '脆炸鱿鱼须' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/ham-cheese-balls.jpg' WHERE id = 16 AND name_zh = '火腿芝士丸' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/baked-mushrooms-with-cheese.jpg' WHERE id = 17 AND name_zh = '芝士焗蘑菇' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/truffle-mushroom-tartare.jpg' WHERE id = 18 AND name_zh = '松露菌菇塔塔' AND image_url = '/menu-images/snacks-toasts.jpg';
UPDATE products SET image_url = '/menu-images/pan-fried-lamb-chops-with-rosemary.jpg' WHERE id = 20 AND name_zh = '法式迷迭香煎羊排' AND image_url = '/menu-images/signature-mains.jpg';
UPDATE products SET image_url = '/menu-images/australian-grain-fed-m3-ribeye-steak.jpg' WHERE id = 21 AND name_zh = '澳洲谷饲M3+肉眼牛排' AND image_url = '/menu-images/signature-mains.jpg';
UPDATE products SET image_url = '/menu-images/australian-grain-fed-m3-sirloin-steak.jpg' WHERE id = 22 AND name_zh = '澳洲谷饲M3+西冷牛排' AND image_url = '/menu-images/signature-mains.jpg';
UPDATE products SET image_url = '/menu-images/pan-seared-salmon-fillet.jpg' WHERE id = 23 AND name_zh = '香煎三文鱼排' AND image_url = '/menu-images/signature-mains.jpg';
UPDATE products SET image_url = '/menu-images/german-sausage-platter.jpg' WHERE id = 24 AND name_zh = '德式风味香肠拼盘（配土豆泥、酸菜、酸黄瓜）' AND image_url = '/menu-images/signature-mains.jpg';
UPDATE products SET image_url = '/menu-images/creamy-truffle-mushroom-pasta.jpg' WHERE id = 25 AND name_zh = '奶油松露菌菇意面' AND image_url = '/menu-images/pasta-risotto.jpg';
UPDATE products SET image_url = '/menu-images/classic-bolognese-pasta.jpg' WHERE id = 26 AND name_zh = '经典肉酱意面' AND image_url = '/menu-images/pasta-risotto.jpg';
UPDATE products SET image_url = '/menu-images/genoese-basil-pesto-pasta.jpg' WHERE id = 27 AND name_zh = '热那亚罗勒青酱意面' AND image_url = '/menu-images/pasta-risotto.jpg';
UPDATE products SET image_url = '/menu-images/bacon-mushroom-cheese-risotto.jpg' WHERE id = 28 AND name_zh = '培根菌菇芝士烩饭' AND image_url = '/menu-images/pasta-risotto.jpg';
UPDATE products SET image_url = '/menu-images/traditional-spanish-seafood-paella.jpg' WHERE id = 29 AND name_zh = '传统西班牙海鲜饭（两人份）' AND image_url = '/menu-images/spanish-paella.jpg';
UPDATE products SET image_url = '/menu-images/spanish-squid-ink-seafood-paella.jpg' WHERE id = 30 AND name_zh = '西班牙墨鱼汁海鲜饭（两人份）' AND image_url = '/menu-images/spanish-paella.jpg';
UPDATE products SET image_url = '/menu-images/durian-supreme-pizza.jpg' WHERE id = 31 AND name_zh = '榴莲多多披萨' AND image_url = '/menu-images/fresh-baked-pizza.jpg';
UPDATE products SET image_url = '/menu-images/italian-salami-pizza.jpg' WHERE id = 32 AND name_zh = '意大利萨拉米披萨' AND image_url = '/menu-images/fresh-baked-pizza.jpg';
UPDATE products SET image_url = '/menu-images/custard-mango-pizza.jpg' WHERE id = 33 AND name_zh = '奶黄香芒披萨' AND image_url = '/menu-images/fresh-baked-pizza.jpg';
UPDATE products SET image_url = '/menu-images/durian-mango-pizza.jpg' WHERE id = 34 AND name_zh = '榴芒披萨' AND image_url = '/menu-images/fresh-baked-pizza.jpg';
UPDATE products SET image_url = '/menu-images/squid-ink-seafood-pizza.jpg' WHERE id = 35 AND name_zh = '墨鱼汁海鲜披萨' AND image_url = '/menu-images/fresh-baked-pizza.jpg';
UPDATE products SET image_url = '/menu-images/truffle-wild-mushroom-flamed-flatbread.jpg' WHERE id = 36 AND name_zh = '松露野菌火焰薄饼' AND image_url = '/menu-images/fresh-baked-pizza.jpg';
UPDATE products SET image_url = '/menu-images/parma-ham-flamed-flatbread.jpg' WHERE id = 37 AND name_zh = '帕尔马火腿火焰薄饼' AND image_url = '/menu-images/fresh-baked-pizza.jpg';
UPDATE products SET image_url = '/menu-images/caramelized-onion-beef-panini.jpg' WHERE id = 38 AND name_zh = '焦糖洋葱牛肉帕尼尼' AND image_url = '/menu-images/panini-burgers.jpg';
UPDATE products SET image_url = '/menu-images/pesto-grilled-chicken-panini.jpg' WHERE id = 39 AND name_zh = '青酱烤鸡胸帕尼尼' AND image_url = '/menu-images/panini-burgers.jpg';
UPDATE products SET image_url = '/menu-images/classic-beef-burger.jpg' WHERE id = 40 AND name_zh = '经典纯牛肉汉堡' AND image_url = '/menu-images/panini-burgers.jpg';
COMMIT;
