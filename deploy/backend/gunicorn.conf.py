"""
文件名称：gunicorn.conf.py
文件用途：配置容器内 Flask 生产进程
主要职责：声明监听端口、Worker 数量、超时和访问日志
所属业务模块：部署
创建时间：2026-07-28 13:01
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

bind = "0.0.0.0:5000"
workers = 2
threads = 4
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
capture_output = True
