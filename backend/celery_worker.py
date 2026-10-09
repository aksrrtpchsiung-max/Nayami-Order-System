"""
文件名称：celery_worker.py
文件用途：暴露 Celery Worker 启动对象
主要职责：供 celery -A celery_worker.celery_app worker 命令加载任务
所属业务模块：异步任务基础设施
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from celery_runtime import celery_app

__all__ = ["celery_app"]
