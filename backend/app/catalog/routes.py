"""
文件名称：routes.py
文件用途：定义菜单 API 路由
主要职责：提供顾客端门店菜单查询接口
所属业务模块：商品与菜单
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint

from app.catalog.services import list_store_menu
from app.common.responses import success_response

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.get("/stores/<int:store_id>/menu")
def store_menu(store_id: int):
    return success_response(list_store_menu(store_id))
