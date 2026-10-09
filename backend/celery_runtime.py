"""
文件名称：celery_runtime.py
文件用途：创建供 Worker 与 Beat 共用的 Celery 应用
主要职责：加载 Flask 配置、绑定应用上下文、注册定时任务和任务模块
所属业务模块：异步任务基础设施
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

from celery import Celery, Task

from app import create_app

flask_app = create_app()


def create_celery_app() -> Celery:
    """
    函数名称：create_celery_app
    函数用途：创建共享 Flask 上下文的 Celery 实例
    参数说明：无
    返回值说明：返回已配置 broker、result backend 和 beat schedule 的 Celery 应用
    核心逻辑：自定义 Task 在 Flask app_context 内执行，自动发现任务模块
    异常或失败情况：Redis 不可用时 Worker/Beat 启动或投递任务失败
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    class FlaskContextTask(Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(
        flask_app.import_name,
        broker=flask_app.config["CELERY_BROKER_URL"],
        backend=flask_app.config["CELERY_RESULT_BACKEND"],
        task_cls=FlaskContextTask,
        include=[
            "app.tasks.coupon_tasks",
            "app.tasks.payment_tasks",
            "app.tasks.reconciliation_tasks",
        ],
    )
    celery.conf.update(
        timezone="Asia/Singapore",
        enable_utc=False,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        beat_schedule={
            "coupon-activity-status-every-30-seconds": {
                "task": "nayami.coupon_activity_status_scan",
                "schedule": 30.0,
            },
            "payment-timeout-scan-every-minute": {
                "task": "nayami.payment_timeout_scan",
                "schedule": 60.0,
            },
            "coupon-claim-retry-every-30-seconds": {
                "task": "nayami.coupon_retry_scan",
                "schedule": 30.0,
            },
            "coupon-ended-activity-reconcile-every-five-minutes": {
                "task": "nayami.coupon_ended_activity_reconcile",
                "schedule": 300.0,
            },
        },
    )
    return celery


celery_app = create_celery_app()
