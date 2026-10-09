"""
文件名称：run_erp_acceptance_environment.py
文件用途：为浏览器验收启动可自动清理的完整隔离环境
主要职责：创建临时 MySQL 库和独立 Redis，运行 API、Worker 与前端，退出时只删除本次临时资源
所属业务模块：集成验收
创建时间：2026-09-08 17:37
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
from urllib.request import urlopen

import pymysql
from _runtime import PROJECT_ROOT, database_parts


def main():
    """
    函数名称：main
    函数用途：运行完整浏览器验收环境直到中断
    参数说明：通过命令行传入 API、Web、Redis 端口，默认使用独立高位端口
    返回值说明：正常中断退出并清理临时数据库、Redis 和子进程
    核心逻辑：从版本化 SQL 初始化唯一临时库，启动服务，输出脱敏连接地址
    异常或失败情况：依赖缺失、端口占用、初始化或服务启动失败时清理并报错
    相关业务规则：不修改环境文件所指向的现有业务库，不复用运行中的 Redis
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-port", type=int, default=15001)
    parser.add_argument("--web-port", type=int, default=15173)
    parser.add_argument("--redis-port", type=int, default=16389)
    args = parser.parse_args()
    connection = database_parts()
    name = f"nayami_browser_{int(time.time())}_{os.getpid()}"
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"mysql+pymysql://{quote(str(connection['user']), safe='')}:{quote(str(connection['password']), safe='')}@{connection['host']}:{connection['port']}/{name}?charset=utf8mb4",
        "REDIS_URL": f"redis://127.0.0.1:{args.redis_port}/0",
        "CELERY_BROKER_URL": f"redis://127.0.0.1:{args.redis_port}/1",
        "CELERY_RESULT_BACKEND": f"redis://127.0.0.1:{args.redis_port}/2",
        "BACKEND_HOST": "127.0.0.1", "BACKEND_PORT": str(args.api_port),
        "FRONTEND_PORT": str(args.web_port), "FRONTEND_HOST": "127.0.0.1",
        "VITE_BACKEND_PROXY_TARGET": f"http://127.0.0.1:{args.api_port}",
        "VITE_API_BASE_URL": "/api", "DEMO_MODE": "true", "COUPON_TASK_EAGER": "false",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": "/tmp/nayami-acceptance-pycache",
        "PYTHONUNBUFFERED": "1", "FLASK_ENV": "development",
    })
    processes = []
    with tempfile.TemporaryDirectory(prefix="nayami_browser_") as runtime:
        def start(label, command, cwd=PROJECT_ROOT / "backend"):
            logfile = open(Path(runtime) / f"{label}.log", "w")
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=logfile, stderr=subprocess.STDOUT, start_new_session=True)
            logfile.close()
            processes.append(process)
            return process

        try:
            mysql_env = dict(env, MYSQL_PWD=str(connection["password"]))
            sql = "\n".join((PROJECT_ROOT / "database/init" / file).read_text().replace("nayami_order_system", name) for file in ("001_create_database.sql", "002_seed_demo_data.sql", "003_seed_demo_coupon.sql"))
            subprocess.run(["mysql", "--protocol=TCP", "--host", str(connection["host"]), "--port", str(connection["port"]), "--user", str(connection["user"])], input=sql.encode(), env=mysql_env, check=True)
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=PROJECT_ROOT / "backend", env=env, check=True)
            start("redis", [shutil.which("redis-server"), "--bind", "127.0.0.1", "--port", str(args.redis_port), "--save", "", "--appendonly", "no", "--dir", runtime])
            start("api", [sys.executable, "wsgi.py"])
            start("worker", [sys.executable, "-m", "celery", "-A", "celery_runtime.celery_app", "worker", "--pool=solo", "--loglevel=WARNING"])
            start("web", [shutil.which("npm"), "run", "dev", "--", "--strictPort"], PROJECT_ROOT / "frontend")
            for attempt in range(100):
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError(f"A service exited; see {runtime}")
                try:
                    with urlopen(f"http://127.0.0.1:{args.api_port}/api/health", timeout=1):
                        pass
                    with urlopen(f"http://127.0.0.1:{args.web_port}", timeout=1):
                        pass
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Service startup timed out")
            metadata = {"api": f"http://127.0.0.1:{args.api_port}/api", "web": f"http://127.0.0.1:{args.web_port}/zh/stores", "database": name, "logs": runtime}
            print(json.dumps(metadata), flush=True)
            # 仅向同一临时目录写环境；不将密码打印到终端或写入版本库。
            environment_file = Path(runtime) / "environment.json"
            environment_file.touch(mode=0o600)
            environment_file.write_text(json.dumps(env))
            while all(process.poll() is None for process in processes):
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
            admin = pymysql.connect(host=str(connection["host"]), port=int(connection["port"]), user=str(connection["user"]), password=str(connection["password"]))
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{name}`")
            admin.close()
            print("Isolated acceptance resources removed.", flush=True)


if __name__ == "__main__":
    main()
