"""
文件名称：services.py
文件用途：汇总当前账号的角色、权限点和门店数据范围
主要职责：为前端工作台导航和后端权限排查提供可解释权限快照
所属业务模块：权限
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations


def get_permission_snapshot(user) -> dict:
    role_codes: list[str] = []
    permission_codes: set[str] = set()
    for link in user.role_links:
        if link.role:
            role_codes.append(link.role.role_code)
            permission_codes.update(link.role.permission_codes or [])
    return {
        "user_id": user.id,
        "role_codes": role_codes,
        "permission_codes": sorted(permission_codes),
        "store_ids": sorted(
            binding.store_id for binding in user.store_bindings if binding.is_active
        ),
    }
