# Nayami Bistro Order System

A restaurant ordering app with a customer storefront, a store workspace, and admin panels for managing multiple locations. Built with React, Flask, MySQL, and Redis, with English and Chinese interfaces.

Customers can browse menus, place orders, use coupons, and track their orders. Staff handle incoming orders and stock, while administrators manage stores, menus, promotions, and accounts.

This is a demo project. Payments are simulated, and SMS delivery is not connected to a real provider. Sample data includes three stores, menus, coupon campaigns, and accounts for each role.

## Features

- **Ordering:** store selection, menus, cart, checkout, and order history.
- **Payments and inventory:** simulated payment outcomes, retries, refunds, stock reservations, and stock restoration on cancellation or refund.
- **Coupons:** limited-stock claims through Redis, with Celery handling persistence, retries, and reconciliation.
- **Store operations:** order fulfillment, inventory updates, and opening status.
- **Administration:** store and menu management, promotions, reports, accounts, roles, and audit logs.

## Quick start

Install Docker with Docker Compose, then clone the repository:

```bash
git clone https://github.com/aksrrtpchsiung-max/Nayami-Order-System.git
cd Nayami-Order-System
cp .env.example .env
```

Edit `.env` before starting:

| Variable | Value |
| --- | --- |
| `SECRET_KEY` | A random secret of at least 32 characters |
| `JWT_SECRET_KEY` | A separate random secret of at least 32 characters |
| `MYSQL_ROOT_PASSWORD` | A password for the demo database |
| `DATABASE_URL` | The MySQL connection URL for local scripts, using `127.0.0.1` |
| `DOCKER_DATABASE_URL` | The same database credentials, using `mysql` as the hostname |

Replace the password placeholders in both database URLs with the URL-encoded database password. Keep the password in `MYSQL_ROOT_PASSWORD` unencoded. You can generate each application secret with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Start the app:

```bash
docker compose up --build -d
```

Compose starts MySQL, Redis, the API, a Celery worker and scheduler, and the frontend. On a fresh database volume, it also loads the sample data; the API runs database migrations at startup. The default setup uses ports 80, 5000, 3306, and 6379.

Open [the English storefront](http://localhost/en/stores) or [the Chinese storefront](http://localhost/zh/stores). The [health endpoint](http://localhost/api/health) and [OpenAPI specification](http://localhost/api/openapi.json) are served through the same host.

To try coupon claims, warm up the campaign stock after the API is ready. This helper uses Python 3 and its standard library:

```bash
python3 scripts/warmup_coupon_redis.py
```

View API logs with `docker compose logs -f backend`. Stop the stack with `docker compose down`; database and Redis data remain in Docker volumes.

## Demo accounts

| Role | Username | Password | English route |
| --- | --- | --- | --- |
| Customer | `customer_demo` | `Nayami123!` | `/en/stores` |
| Store staff | `store_staff_demo` | `Store123!` | `/en/store/workspace` |
| Store manager | `store_manager_001` | `Store123!` | `/en/store/workspace` |
| Brand administrator | `brand_admin` | `Admin123!` | `/en/brand/workspace` |
| System administrator | `system_admin` | `Admin123!` | `/en/system/workspace` |

These are seeded demo credentials. Use them only in a local or demo environment.

## Local development

You will need Python 3.11+, Node.js 22.12+ (or 20.19+ on the Node 20 line), MySQL 8, and Redis 7. The MySQL command-line client must be available on your `PATH`.

Copy `.env.example` to `.env` if you have not already done so, and set the secrets and database credentials described above. Start MySQL and Redis, then run these commands from the repository root:

```bash
bash scripts/init_dev.sh
bash scripts/start_dev.sh
```

On Windows, use PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\init_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1
```

The initialization script creates `backend/.venv`, installs dependencies, runs migrations, and seeds the database. The start script runs Flask and Vite together; press `Ctrl+C` to stop both.

Open [http://127.0.0.1:5173/en/stores](http://127.0.0.1:5173/en/stores). Vite proxies `/api` requests to Flask. If port 5000 is in use, set `BACKEND_PORT=5001` in `.env` before starting; the proxy reads the same setting. You can also change `FRONTEND_PORT` and set `FRONTEND_ORIGIN` to match.

### Background tasks

Coupon persistence, payment timeouts, and reconciliation need Celery. On macOS or Linux, run the worker and scheduler in separate terminals, each from the repository root:

```bash
cd backend
.venv/bin/celery -A celery_runtime.celery_app worker --loglevel=INFO
```

```bash
cd backend
.venv/bin/celery -A celery_runtime.celery_app beat --loglevel=INFO
```

For the full background-task setup on Windows, use Docker Compose or WSL.

Once the API is running, warm up coupon stock from the repository root:

```bash
python3 scripts/warmup_coupon_redis.py
```

If you changed the API port, set `NAYAMI_API_BASE` to the matching URL, such as `http://127.0.0.1:5001/api`, when running the helper.

## Tests

After installing dependencies, run the backend tests from `backend/`:

```bash
.venv/bin/python -m pytest -q
```

On Windows, use `.venv\Scripts\python.exe -m pytest -q`.

Run the frontend tests and production build from `frontend/`:

```bash
npm test
npm run build
```

## Project structure

```text
backend/        Flask API, Celery tasks, migrations, and pytest tests
frontend/       React and TypeScript app, built with Vite
database/init/  Database setup and sample data
scripts/        Development, seeding, and verification helpers
deploy/         Dockerfiles and Nginx, MySQL, Redis, and Gunicorn configuration
```

The frontend uses Ant Design, TanStack Query, Zustand, and i18next. The backend uses SQLAlchemy, Alembic, Flask-JWT-Extended, and Celery.
