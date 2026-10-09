"""
文件名称：services.py
文件用途：实现后台操作日志查询服务
主要职责：按角色及账号目标隔离日志，提供筛选和快照详情，安全记录失败及越权请求
所属业务模块：审计
创建时间：2026-05-26 16:20
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app, g, has_request_context, request

from app.audit.models import OperationLog
from app.common.enums import ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN
from app.common.errors import BusinessError, ForbiddenError, NotFoundError
from app.extensions import db
from app.users.models import User
from app.common.formatters import format_datetime

BRAND_VISIBLE_MODULES = {"store", "catalog", "inventory", "coupon", "report", "account", "order"}


def list_operation_logs(user, filters: dict) -> list[dict]:
    """
    函数名称：list_operation_logs
    函数用途：查询后台操作日志
    参数说明：user 为当前后台用户，filters 包含模块、结果、操作人和时间范围
    返回值说明：返回符合权限范围的操作日志列表
    核心逻辑：系统管理员查看全系统，品牌管理员按运营模块及账号目标过滤；日期结束值涵盖整日
    异常或失败情况：非品牌或系统管理员访问时拒绝，时间格式非法时失败
    相关业务规则：日志查询不能泄露密码等敏感信息，日志内容只来自已记录摘要
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    if not user.has_any_role((ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能查看操作日志")
    query = OperationLog.query.order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
    if user.has_any_role((ROLE_BRAND_ADMIN,)) and not user.has_any_role((ROLE_SYSTEM_ADMIN,)):
        query = query.filter(OperationLog.operation_module.in_(BRAND_VISIBLE_MODULES))
    operation_module = str(filters.get("operation_module") or "").strip()
    operation_result = str(filters.get("operation_result") or "").strip()
    operation_type = str(filters.get("operation_type") or "").strip()
    operator_id = filters.get("operator_id")
    operator_role_code = str(filters.get("operator_role_code") or "").strip()
    store_id = filters.get("store_id")
    if operation_module:
        query = query.filter(OperationLog.operation_module == operation_module)
    if operation_result:
        query = query.filter(OperationLog.operation_result == operation_result)
    if operation_type:
        query = query.filter(OperationLog.operation_type == operation_type)
    if operator_id:
        query = query.filter(OperationLog.operator_id == _positive_integer(operator_id))
    if operator_role_code:
        query = query.filter(OperationLog.operator_role_code == operator_role_code)
    if store_id:
        query = query.filter(OperationLog.store_id == _positive_integer(store_id))
    start_at = _parse_datetime(filters.get("start_at"))
    end_at = _parse_datetime(filters.get("end_at"))
    if start_at:
        query = query.filter(OperationLog.created_at >= start_at)
    if end_at:
        if len(str(filters.get("end_at"))) == 10:
            query = query.filter(OperationLog.created_at < end_at + timedelta(days=1))
        else:
            query = query.filter(OperationLog.created_at <= end_at)
    if start_at and end_at and start_at > end_at:
        raise BusinessError("开始时间不能晚于结束时间", "invalid_datetime")
    limit = min(_positive_integer(filters.get("limit") or 100), 300)
    result = []
    # 先过滤敏感账号，再限制返回数，防止列表和详情采用不同权限口径。
    for log in query.yield_per(100):
        if _visible_to_user(user, log):
            result.append(serialize_operation_log(log))
            if len(result) == limit:
                break
    return result


def serialize_operation_log(log: OperationLog) -> dict:
    return {
        "id": log.id,
        "operator_id": log.operator_id,
        "operator_role_code": log.operator_role_code,
        "operation_module": log.operation_module,
        "operation_type": log.operation_type,
        "target_id": log.target_id,
        "store_id": log.store_id,
        "before_snapshot": log.before_snapshot,
        "after_snapshot": log.after_snapshot,
        "operation_result": log.operation_result,
        "failure_reason": log.failure_reason,
        "ip_address": log.ip_address,
        "created_at": format_datetime(log.created_at),
    }


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo("Asia/Singapore")).replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError as exc:
        raise BusinessError("时间格式不合法", "invalid_datetime") from exc


def get_operation_log(user, log_id: int) -> dict:
    """
    函数名称：get_operation_log
    函数用途：在列表相同权限范围内读取日志详情
    参数说明：user 为后台用户，log_id 为日志编号
    返回值说明：含前后快照的日志摘要
    核心逻辑：校验角色、模块和账号目标；不存在或不可见统一返回 404
    异常或失败情况：非管理角色返回 403，越范围详情返回 404
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if not user.has_any_role((ROLE_BRAND_ADMIN, ROLE_SYSTEM_ADMIN)):
        raise ForbiddenError("当前账号不能查看操作日志")
    log = db.session.get(OperationLog, log_id)
    if log is None or not _visible_to_user(user, log):
        raise NotFoundError("操作日志不存在")
    return serialize_operation_log(log)


def _visible_to_user(user, log: OperationLog) -> bool:
    if user.has_any_role((ROLE_SYSTEM_ADMIN,)):
        return True
    if log.operation_module not in BRAND_VISIBLE_MODULES:
        return False
    if log.operation_module != "account":
        return True
    managed_roles = {"store_staff", "store_manager"}
    recorded_roles = set()
    for snapshot in (log.before_snapshot, log.after_snapshot):
        if isinstance(snapshot, dict):
            recorded_roles.update(snapshot.get("roles") or [])
            if snapshot.get("role_code"):
                recorded_roles.add(snapshot["role_code"])
    if recorded_roles - managed_roles:
        return False
    target = db.session.get(User, log.target_id) if log.target_id else None
    current_roles = {link.role.role_code for link in target.role_links if link.role} if target else set()
    return not (current_roles - managed_roles) and bool(recorded_roles or current_roles)


def record_request_failure(code: str, status_code: int) -> None:
    """
    函数名称：record_request_failure
    函数用途：在业务回滚后独立记录登录失败、后台失败和越权拒绝
    参数说明：code 为服务端错误码，status_code 为响应状态
    返回值说明：无；审计数据库不可用时仅记录服务器错误
    核心逻辑：只保存路径模板、方法、已认证身份和错误码，不读取请求参数正文
    异常或失败情况：审计写入失败不覆盖原业务错误，失败事务再次回滚
    相关业务规则：不记录密码、令牌、卡号、验证码或 URL 查询值
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    if not has_request_context():
        return
    is_login = request.path == "/api/auth/login"
    is_backend = request.path.startswith(("/api/store/", "/api/brand/", "/api/system/", "/api/audit/"))
    if not (is_login or is_backend or status_code == 403):
        return
    module = "auth" if is_login else "security"
    operation_type = "login" if is_login else "request_rejected" if status_code in (401, 403) else "request_failed"
    try:
        db.session.add(OperationLog(
            operator_id=getattr(g, "audit_user_id", None),
            operator_role_code=getattr(g, "audit_role_code", None),
            operation_module=module, operation_type=operation_type,
            operation_result="rejected" if status_code in (401, 403) else "failed",
            failure_reason=code[:255], ip_address=request.remote_addr,
            after_snapshot={"method": request.method, "route": request.url_rule.rule if request.url_rule else "unmatched"},
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.error("Security audit persistence failed")


def _positive_integer(value) -> int:
    try:
        if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
            raise ValueError
        return int(value)
    except (ValueError, TypeError) as exc:
        raise BusinessError("筛选参数必须为正整数", "invalid_filter") from exc
