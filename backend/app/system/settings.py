"""
文件名称：settings.py
文件用途：提供跨进程一致的非交易配置读取
主要职责：优先读取数据库白名单覆盖值，未配置时使用真实运行环境默认值
所属业务模块：系统管理
创建时间：2026-09-08 17:56
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from flask import current_app

from app.extensions import db
from app.system.models import SystemSetting

SETTING_DEFAULTS = {
    "default_language": ("DEFAULT_LANGUAGE", "zh-CN"),
    "demo_mode": ("DEMO_MODE", True),
    "payment_description": ("PAYMENT_DESCRIPTION", "Simulated payments; no real funds are transferred."),
}


def get_setting(key: str):
    """
    函数名称：get_setting
    函数用途：读取可由系统后台维护的当前配置
    参数说明：key 为 SETTING_DEFAULTS 中的白名单键
    返回值说明：数据库覆盖值，或应用环境默认值
    核心逻辑：在当前事务内读取设置表，不维护进程级缓存；未设置时回退环境配置
    异常或失败情况：非白名单键抛出 KeyError，数据库错误交由调用方处理
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    config_key, default = SETTING_DEFAULTS[key]
    setting = db.session.get(SystemSetting, key)
    return setting.value if setting is not None else current_app.config.get(config_key, default)
