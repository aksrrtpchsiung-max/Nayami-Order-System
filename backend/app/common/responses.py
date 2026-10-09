"""
文件名称：responses.py
文件用途：封装统一 API 响应结构
主要职责：提供成功响应、失败响应和分页响应格式
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from flask import jsonify


def success_response(data=None, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code


def error_response(code: str, message: str, status_code: int = 400):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status_code
