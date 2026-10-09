"""
文件名称：extensions.py
文件用途：集中声明 Flask 扩展对象
主要职责：初始化 SQLAlchemy、Alembic/Flask-Migrate、JWT 和 CORS，供应用工厂和业务模块复用
所属业务模块：后端基础设施
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
