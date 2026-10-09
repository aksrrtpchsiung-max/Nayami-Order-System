"""
文件名称：routes.py
文件用途：定义当前账号权限快照 API
主要职责：返回角色、权限点和门店绑定，不允许客户端修改权限
所属业务模块：权限
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint

from app.common.decorators import get_current_user
from app.common.responses import success_response
from app.permissions.services import get_permission_snapshot

permissions_bp = Blueprint("permissions", __name__)


@permissions_bp.get("/me")
def my_permissions():
    return success_response(get_permission_snapshot(get_current_user()))
