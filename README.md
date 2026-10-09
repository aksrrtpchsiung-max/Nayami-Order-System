# Nayami Bistro Order System

奈亚米是一个面向城市内多门店连锁餐饮品牌的在线点餐、订单履约和运营管理 Web App 产品原型。项目包含顾客端、门店工作台、品牌后台、系统后台，以及 MySQL、Redis、Celery 和完整交易状态日志。


## 已实现能力

- 顾客验证码注册、用户名/手机号登录、JWT 双令牌刷新和退出；
- 三家门店、中英文菜单、购物车、结算、订单历史；
- 服务端金额重算、订单级库存预占/扣减/释放/退款恢复；
- 微信、支付宝、银联、Visa、MasterCard 支付仿真；
- 支付成功、失败、取消、超时、重试、退款和幂等回调；
- Redis Lua 原子抢券、Celery 异步落库、重试、死信和对账；
- 门店订单看板、履约状态机、库存和营业状态；
- 品牌门店/菜单/活动/报表/账号管理；
- 系统账号、角色、配置和审计日志；
- 中文/英文界面及 `/zh/...`、`/en/...` 可分享 URL；
- Docker Compose 一键启动、Alembic 迁移、演示种子和自动化测试。

## 技术栈

- 前端：React、TypeScript、Vite、Ant Design、TanStack Query、Zustand、i18next
- 后端：Flask、SQLAlchemy、Flask-JWT-Extended、Celery
- 数据：MySQL 8、Redis 7
- 部署：Docker Compose、Gunicorn、Nginx
- 测试：pytest、Vitest、React Testing Library

## 一键运行

```bash
cp .env.example .env
# 设置 .env 中的 MYSQL_ROOT_PASSWORD、DATABASE_URL、DOCKER_DATABASE_URL
# 数据库 URL 中的密码须 URL 编码；两个 URL 分别使用 127.0.0.1 和 mysql 主机名
# SECRET_KEY 和 JWT_SECRET_KEY 须分别设置为至少 32 字节的随机值
docker compose up --build -d
```

访问：

- 中文顾客端：`http://localhost/zh/stores`
- 英文顾客端：`http://localhost/en/stores`
- API 健康检查：`http://localhost/api/health`
- OpenAPI：`http://localhost/api/openapi.json`

首次启动后预热演示活动：

```bash
backend/.venv/bin/python scripts/warmup_coupon_redis.py
```

## 本地开发（一键启动前后端）

本节适用于 macOS/Linux 和 Windows PowerShell。基础页面和 API 调试需要启动 MySQL、Redis、Flask 后端和 Vite 前端；如需完整体验抢券异步落库、支付超时和对账，再额外启动 Celery Worker 与 Celery Beat。

### 1. 准备环境

| 依赖 | 建议版本 | 检查命令 |
| --- | --- | --- |
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| MySQL | 8.x | `mysql --version` |
| Redis | 7.x | `redis-server --version` |

先复制本地配置：

```bash
test -f .env || cp .env.example .env
```

打开 `.env`，至少完成以下配置：

- 将 `SECRET_KEY` 和 `JWT_SECRET_KEY` 分别替换为随机密钥，可用 `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` 生成；
- 将 `MYSQL_ROOT_PASSWORD` 替换为本机 MySQL 密码；
- 将 `DATABASE_URL` 中的密码替换为 URL 编码后的密码；密码含 `!`、`@`、`#` 等特殊字符时必须编码；
- 本地端口被占用时修改 `BACKEND_PORT`，Vite 会读取同一个值并自动更新 `/api` 代理目标。macOS 的 `5000` 端口可能被“隔空播放接收器”占用，可改为 `5001`。

可用下面的命令生成密码的 URL 编码结果：

```bash
python3 -c "from urllib.parse import quote; print(quote('替换为你的数据库密码', safe=''))"
```

### 2. 启动 MySQL 和 Redis

如果通过 Homebrew 安装：

```bash
brew services start mysql
brew services start redis
```

如果使用 MySQL 官方 macOS 安装包，可在“系统设置 → MySQL”中启动，或执行：

```bash
sudo /usr/local/mysql/support-files/mysql.server start
```

确认两个服务可用：

```bash
mysqladmin ping -h 127.0.0.1 -u root -p
redis-cli ping
```

MySQL 应返回 `mysqld is alive`，Redis 应返回 `PONG`。

### 3. 首次初始化

在项目根目录运行：

```bash
bash ./scripts/init_dev.sh
```

Windows PowerShell 使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\init_dev.ps1
```

脚本会创建 `backend/.venv`、安装前后端依赖、执行 Alembic 数据库迁移并写入演示数据。修改依赖或迁移文件后也可以重新执行；演示种子脚本可重复运行。

### 4. 一键启动后端和前端

完成首次初始化后，只需在项目根目录打开一个终端。

macOS/Linux：

```bash
bash ./scripts/start_dev.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1
```

该入口会同时启动 Flask 后端和 Vite 前端，并在同一个终端中使用 `[backend]`、`[frontend]` 前缀展示日志。任一服务启动失败时，另一个服务也会自动停止；调试结束时按一次 `Ctrl+C` 即可同时关闭前后端。

如需只检查虚拟环境、前端依赖和启动命令，不实际占用端口，可追加 `--check`：

```bash
bash ./scripts/start_dev.sh --check
```

启动成功后访问：

- 中文顾客端：`http://127.0.0.1:5173/zh/stores`
- 英文顾客端：`http://127.0.0.1:5173/en/stores`
- 经前端代理的健康检查：`http://127.0.0.1:5173/api/health`
- 后端直连健康检查：`http://127.0.0.1:<BACKEND_PORT>/api/health`
- OpenAPI：`http://127.0.0.1:<BACKEND_PORT>/api/openapi.json`

其中 `<BACKEND_PORT>` 替换为 `.env` 中的实际端口，例如 `5000` 或 `5001`。

### 5. 启动完整异步任务

需要测试抢券、支付超时、重试和对账时，再打开两个终端：

终端 3——Celery Worker：

```bash
cd backend
.venv/bin/celery -A celery_runtime.celery_app worker --loglevel=INFO
```

终端 4——Celery Beat：

```bash
cd backend
.venv/bin/celery -A celery_runtime.celery_app beat --loglevel=INFO
```

首次使用演示优惠券活动时，在项目根目录预热 Redis：

```bash
backend/.venv/bin/python scripts/warmup_coupon_redis.py
```

### 6. 启动检查与停止

将命令中的端口改成 `.env` 的 `BACKEND_PORT`：

```bash
curl http://127.0.0.1:5000/api/health
NAYAMI_HEALTH_URL=http://127.0.0.1:5000/api/health \
  backend/.venv/bin/python scripts/check_demo_environment.py
```

正常情况下，健康检查会返回 `"status": "ok"`，环境检查中的 `api`、`mysql` 和 `redis` 均为 `"ok": true`。

通过一键调试入口启动的前后端，在同一终端按一次 `Ctrl+C` 即可同时停止。Worker 和 Beat 仍在各自终端按 `Ctrl+C` 停止。通过 Homebrew 启动的基础服务可执行：

```bash
brew services stop mysql
brew services stop redis
```

常见问题：

- `Address already in use`：修改 `.env` 中的 `BACKEND_PORT` 或 `FRONTEND_PORT`，然后重启对应服务；
- `Can't connect to MySQL server`：确认 MySQL 已启动，并检查 `DATABASE_URL` 的主机、端口、密码及 URL 编码；
- `Error connecting to Redis`：确认 Redis 已启动，且 `REDIS_URL`、`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND` 指向同一可用实例；
- 页面能打开但没有业务数据：先执行 `bash ./scripts/init_dev.sh` 完成迁移和演示数据初始化。

## 测试

```bash
cd backend
PYTHONPYCACHEPREFIX=/tmp/nayami-pycache .venv/bin/python -m pytest -q

cd ../frontend
npm run test
npm run build
```

## 演示账号

| 用户名 | 密码 | 角色 | 默认入口 |
| --- | --- | --- | --- |
| `customer_demo` | `Nayami123!` | 顾客 | `/zh/stores` |
| `store_staff_demo` | `Store123!` | 门店员工 | `/zh/store/workspace` |
| `store_manager_001` | `Store123!` | 门店经理 | `/zh/store/workspace` |
| `brand_admin` | `Admin123!` | 品牌管理员 | `/zh/brand/workspace` |
| `system_admin` | `Admin123!` | 系统管理员 | `/zh/system/workspace` |

演示密码只用于本地和演示环境。

第一版明确不接入真实支付、真实短信、配送、复杂会员积分和生产级营销风控。
