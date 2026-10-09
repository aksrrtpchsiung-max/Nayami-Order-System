"""
文件名称：__init__.py
文件用途：创建奈亚米订单系统 Flask 应用
主要职责：初始化应用和模型、注册蓝图、验证请求格式、统一错误响应与失败审计
所属业务模块：后端应用入口
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from flask import Flask, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.common.errors import BusinessError
from app.common.responses import error_response, success_response
from app.config import get_config
from app.extensions import cors, db, jwt, migrate


def create_app(config_object=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    register_models()
    register_blueprints(app)
    register_error_handlers(app)

    @app.get("/api/health")
    def health_check():
        return success_response({"status": "ok", "service": "nayami-order-system"})

    @app.get("/api/openapi.json")
    def openapi_document():
        from app.common.openapi import build_openapi_spec

        return jsonify(build_openapi_spec())

    @app.before_request
    def validate_json_object():
        """
        函数名称：validate_json_object
        函数用途：在业务入口统一拒绝错误JSON正文和非法数值筛选
        参数说明：从当前API请求读取正文类型与公共查询参数
        返回值说明：校验通过后继续请求分发
        核心逻辑：限制公共整数参数的字符和长度，写入正文必须为JSON对象
        异常或失败情况：非法输入统一抛出400业务错误，不进入数据库业务
        最近修改时间：2026-10-09 14:06
        修改人：Project Maintainers
        """
        if request.path.startswith("/api/"):
            for key in ("store_id", "product_id", "store_product_id", "operator_id", "limit", "days"):
                value = request.args.get(key)
                if value and (not value.isascii() or not value.isdigit() or len(value) > 10 or not 0 < int(value) <= 2147483647):
                    raise BusinessError("查询参数必须为正整数", "invalid_filter")
        if request.path.startswith("/api/") and request.method in {"POST", "PATCH", "PUT"} and request.get_data():
            if not request.is_json or not isinstance(request.get_json(silent=True), dict):
                raise BusinessError("请求正文必须为有效 JSON 对象", "invalid_json")

    return app


def register_models() -> None:
    from app.audit import models as audit_models  # noqa: F401
    from app.catalog import models as catalog_models  # noqa: F401
    from app.coupons import models as coupons_models  # noqa: F401
    from app.inventory import models as inventory_models  # noqa: F401
    from app.orders import models as orders_models  # noqa: F401
    from app.payments import models as payments_models  # noqa: F401
    from app.stores import models as stores_models  # noqa: F401
    from app.system import models as system_models  # noqa: F401
    from app.users import models as users_models  # noqa: F401


def register_blueprints(app: Flask) -> None:
    from app.audit.routes import audit_bp
    from app.auth.routes import auth_bp
    from app.brand.routes import brand_bp
    from app.cart.routes import cart_bp
    from app.catalog.routes import catalog_bp
    from app.coupons.routes import coupons_bp
    from app.inventory.routes import inventory_bp
    from app.i18n.routes import i18n_bp
    from app.orders.routes import orders_bp
    from app.payments.routes import payments_bp
    from app.permissions.routes import permissions_bp
    from app.reports.routes import reports_bp
    from app.stores.routes import store_admin_bp
    from app.stores.routes import stores_bp
    from app.system.routes import system_bp

    app.register_blueprint(audit_bp, url_prefix="/api/audit")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(brand_bp, url_prefix="/api/brand")
    app.register_blueprint(stores_bp, url_prefix="/api/stores")
    app.register_blueprint(store_admin_bp, url_prefix="/api/store")
    app.register_blueprint(catalog_bp, url_prefix="/api/catalog")
    app.register_blueprint(coupons_bp, url_prefix="/api/coupons")
    app.register_blueprint(cart_bp, url_prefix="/api/cart")
    app.register_blueprint(orders_bp, url_prefix="/api")
    app.register_blueprint(payments_bp, url_prefix="/api/payments")
    app.register_blueprint(permissions_bp, url_prefix="/api/permissions")
    app.register_blueprint(inventory_bp, url_prefix="/api/store/inventory")
    app.register_blueprint(i18n_bp, url_prefix="/api/i18n")
    app.register_blueprint(reports_bp, url_prefix="/api/store")
    app.register_blueprint(system_bp, url_prefix="/api/system")


def register_error_handlers(app: Flask) -> None:
    from app.audit.services import record_request_failure
    @jwt.unauthorized_loader
    def handle_missing_token(reason):
        record_request_failure("authentication_required", 401)
        return error_response("authentication_required", "请先登录后再执行该操作", 401)

    @jwt.invalid_token_loader
    def handle_invalid_token(reason):
        record_request_failure("invalid_token", 401)
        return error_response("invalid_token", "登录凭证无效，请重新登录", 401)

    @jwt.expired_token_loader
    def handle_expired_token(jwt_header, jwt_payload):
        record_request_failure("token_expired", 401)
        return error_response("token_expired", "登录凭证已过期，请刷新或重新登录", 401)

    @app.errorhandler(BusinessError)
    def handle_business_error(error: BusinessError):
        db.session.rollback()
        record_request_failure(error.code, error.status_code)
        return error_response(error.code, error.message, error.status_code)

    @app.errorhandler(404)
    def handle_not_found(error):
        return error_response("not_found", "接口不存在", 404)

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        db.session.rollback()
        record_request_failure("database_error", 500)
        return error_response("database_error", "数据库访问失败，请确认 MySQL 已启动并完成初始化", 500)

    @app.errorhandler(500)
    def handle_internal_error(error):
        db.session.rollback()
        return error_response("internal_error", "系统内部错误", 500)
