"""
文件名称：wsgi.py
文件用途：提供 Gunicorn 和本地运行的 Flask 应用入口
主要职责：创建并暴露 app 对象，支持从环境变量读取本地启动地址
所属业务模块：后端应用入口
创建时间：2026-05-22 14:05
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

import os

from app import create_app

app = create_app()


if __name__ == "__main__":
    backend_host = app.config["BACKEND_HOST"]
    backend_port = app.config["BACKEND_PORT"]
    app.run(host=backend_host, port=backend_port, debug=os.getenv("FLASK_DEBUG") == "1", use_reloader=False)
