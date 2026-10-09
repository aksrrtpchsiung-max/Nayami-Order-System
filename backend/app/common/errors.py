"""
文件名称：errors.py
文件用途：定义业务异常和统一错误处理
主要职责：表达登录失败、越权、库存不足、状态非法等业务错误
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations


class BusinessError(Exception):
    """
    类名称：BusinessError
    类用途：表示可预期业务错误
    主要职责：携带错误码、提示文案和 HTTP 状态码
    不负责的内容：不处理系统异常和数据库连接错误
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    def __init__(self, message: str, code: str = "business_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class AuthenticationError(BusinessError):
    def __init__(self, message: str = "认证失败") -> None:
        super().__init__(message, "authentication_failed", 401)


class ForbiddenError(BusinessError):
    def __init__(self, message: str = "无权访问该资源") -> None:
        super().__init__(message, "forbidden", 403)


class NotFoundError(BusinessError):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message, "not_found", 404)
