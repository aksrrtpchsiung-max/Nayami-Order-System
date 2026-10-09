"""
文件名称：pagination.py
文件用途：提供基础分页工具
主要职责：解析分页参数并限制分页大小
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import request

from app.common.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


def get_pagination_params() -> tuple[int, int]:
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", DEFAULT_PAGE_SIZE)), 1), MAX_PAGE_SIZE)
    return page, page_size
