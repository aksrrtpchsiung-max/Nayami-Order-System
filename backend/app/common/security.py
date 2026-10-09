"""
文件名称：security.py
文件用途：提供密码安全工具
主要职责：封装密码哈希生成和密码校验
所属业务模块：后端通用模块
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from werkzeug.security import check_password_hash, generate_password_hash

PASSWORD_HASH_METHOD = "pbkdf2:sha256:600000"


def hash_password(password: str) -> str:
    """使用跨 Python 运行环境稳定可用的 PBKDF2-SHA256 生成密码哈希。"""
    return generate_password_hash(password, method=PASSWORD_HASH_METHOD)


def verify_password(password_hash: str, password: str) -> bool:
    """校验 Werkzeug 格式密码哈希，并兼容数据库中已有的哈希方案。"""
    return check_password_hash(password_hash, password)
