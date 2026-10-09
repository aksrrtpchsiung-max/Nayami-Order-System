"""
文件名称：routes.py
文件用途：定义国际化元数据 API
主要职责：提供支持语言列表和核心业务状态文案
所属业务模块：国际化
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import Blueprint, request

from app.common.responses import success_response
from app.i18n.services import get_status_texts, list_languages

i18n_bp = Blueprint("i18n", __name__)


@i18n_bp.get("/languages")
def languages():
    return success_response(list_languages())


@i18n_bp.get("/statuses")
def statuses():
    return success_response(get_status_texts(request.args.get("language") or "zh-CN"))
