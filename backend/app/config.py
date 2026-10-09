"""
文件名称：config.py
文件用途：管理奈亚米订单系统后端运行配置
主要职责：读取服务端口、数据库、JWT、跨域、支付超时和测试环境配置
所属业务模块：后端基础设施
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path


def load_root_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
            continue
        key, value = stripped_line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_root_env_file()


class BaseConfig:
    """
    类名称：BaseConfig
    类用途：提供 Flask 应用的默认配置
    主要职责：集中声明服务端口、数据库连接、JWT 密钥、跨域来源和支付超时配置
    不负责的内容：不负责读取业务数据或执行初始化种子脚本
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5000"))
    FRONTEND_HOST = os.getenv("FRONTEND_HOST", "127.0.0.1")
    FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "5173"))
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", f"http://{FRONTEND_HOST}:{FRONTEND_PORT}")
    PAYMENT_TIMEOUT_MINUTES = int(os.getenv("PAYMENT_TIMEOUT_MINUTES", "15"))
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    COUPON_MAX_RETRIES = int(os.getenv("COUPON_MAX_RETRIES", "3"))
    COUPON_IDEMPOTENCY_TTL_SECONDS = int(os.getenv("COUPON_IDEMPOTENCY_TTL_SECONDS", "900"))
    COUPON_RESULT_TTL_SECONDS = int(os.getenv("COUPON_RESULT_TTL_SECONDS", "7200"))
    CART_TTL_SECONDS = int(os.getenv("CART_TTL_SECONDS", "2592000"))
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "zh-CN")
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "CNY")
    PAYMENT_MODE = os.getenv("PAYMENT_MODE", "simulated")
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
    COUPON_TASK_EAGER = os.getenv("COUPON_TASK_EAGER", "false").lower() == "true"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", "1800")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_SECONDS", "604800")))


class TestConfig(BaseConfig):
    """
    类名称：TestConfig
    类用途：提供 pytest 使用的轻量测试配置
    主要职责：使用 SQLite 内存数据库并关闭外部依赖
    不负责的内容：不覆盖生产或演示环境变量
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "nayami-test-jwt-secret-at-least-32-bytes"
    DEMO_MODE = True
    COUPON_TASK_EAGER = True


def get_config() -> type[BaseConfig]:
    if os.getenv("FLASK_ENV") == "testing":
        return TestConfig
    return BaseConfig
