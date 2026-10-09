"""
文件名称：start_dev.py
文件用途：一键启动奈亚米订单系统前后端调试服务
主要职责：校验本地依赖、并行启动 Flask 与 Vite、汇总日志并统一停止子进程
所属业务模块：本地开发脚本
创建时间：2026-08-06 11:49
最近修改时间：2026-10-09 14:06
修改人：Project Maintainers
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Sequence, Tuple

from _runtime import PROJECT_ROOT, load_root_env


def resolve_commands() -> List[Tuple[str, Sequence[str], Path]]:
    """
    函数名称：resolve_commands
    函数用途：生成当前操作系统下的前后端启动命令
    参数说明：无
    返回值说明：返回服务名称、命令参数和工作目录组成的列表
    核心逻辑：优先使用项目虚拟环境 Python，并按平台选择 npm 或 npm.cmd
    异常或失败情况：虚拟环境、前端依赖或 npm 缺失时抛出 RuntimeError
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    backend_directory = PROJECT_ROOT / "backend"
    frontend_directory = PROJECT_ROOT / "frontend"
    if os.name == "nt":
        backend_python = backend_directory / ".venv" / "Scripts" / "python.exe"
        npm_command = "npm.cmd"
    else:
        backend_python = backend_directory / ".venv" / "bin" / "python"
        npm_command = "npm"

    missing_requirements = []
    if not backend_python.exists():
        missing_requirements.append(str(backend_python))
    if not (frontend_directory / "node_modules").is_dir():
        missing_requirements.append(str(frontend_directory / "node_modules"))
    if shutil.which(npm_command) is None:
        missing_requirements.append(npm_command)
    if missing_requirements:
        missing_list = "\n  - ".join(missing_requirements)
        raise RuntimeError(
            "调试依赖尚未准备好：\n"
            f"  - {missing_list}\n"
            "请先执行项目初始化脚本。"
        )

    return [
        ("backend", [str(backend_python), "wsgi.py"], backend_directory),
        ("frontend", [npm_command, "run", "dev"], frontend_directory),
    ]


def stream_process_output(service_name: str, process: subprocess.Popen) -> None:
    """按服务名称转发子进程输出，便于在同一终端区分前后端日志。"""
    if process.stdout is None:
        return
    for line in process.stdout:
        print(f"[{service_name}] {line.rstrip()}", flush=True)


def start_process(
    service_name: str,
    command: Sequence[str],
    working_directory: Path,
    environment: dict,
) -> subprocess.Popen:
    """
    函数名称：start_process
    函数用途：在独立进程组中启动一个调试服务
    参数说明：service_name 为日志标签，command 为启动命令，working_directory 为工作目录，environment 为环境变量
    返回值说明：返回已启动的 Popen 进程对象
    核心逻辑：合并标准错误和标准输出，并通过后台线程统一打印日志
    异常或失败情况：命令不存在或进程创建失败时向上抛出系统异常
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    process_options = {
        "cwd": str(working_directory),
        "env": environment,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
        "errors": "replace",
    }
    if os.name == "nt":
        process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        process_options["start_new_session"] = True

    process = subprocess.Popen(command, **process_options)
    output_thread = threading.Thread(
        target=stream_process_output,
        args=(service_name, process),
        name=f"{service_name}-output",
        daemon=True,
    )
    output_thread.start()
    return process


def stop_process(process: subprocess.Popen) -> None:
    """停止由本脚本创建的服务进程组，避免遗留 Flask、Vite 或 npm 子进程。"""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return


def stop_processes(processes: Sequence[subprocess.Popen]) -> None:
    """依次停止全部调试进程，并等待它们释放端口。"""
    for process in processes:
        stop_process(process)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name != "nt" and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass


def display_startup_summary() -> None:
    """显示从 .env 解析出的本地调试地址，不输出任何敏感配置。"""
    frontend_host = os.getenv("FRONTEND_HOST", "127.0.0.1")
    frontend_port = os.getenv("FRONTEND_PORT", "5173")
    backend_host = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port = os.getenv("BACKEND_PORT", "5000")
    browser_host = "127.0.0.1" if frontend_host in {"0.0.0.0", "::"} else frontend_host
    health_host = "127.0.0.1" if backend_host in {"0.0.0.0", "::"} else backend_host

    print("Nayami 调试服务正在启动：", flush=True)
    print(f"  前端：http://{browser_host}:{frontend_port}/zh/stores", flush=True)
    print(f"  后端：http://{health_host}:{backend_port}/api/health", flush=True)
    print("  停止：按一次 Ctrl+C\n", flush=True)


def run_development_services(check_only: bool = False) -> int:
    """
    函数名称：run_development_services
    函数用途：启动并持续监控前后端调试服务
    参数说明：check_only 为真时仅检查依赖和命令，不创建长期运行进程
    返回值说明：正常停止返回 0，服务异常退出返回非零状态
    核心逻辑：加载根目录环境变量、并行启动服务、监控退出状态并统一清理进程组
    异常或失败情况：依赖缺失、端口占用或服务启动失败时打印原因并返回 1
    最近修改时间：2026-10-09 14:06
    修改人：Project Maintainers
    """

    load_root_env()
    try:
        commands = resolve_commands()
    except RuntimeError as error:
        print(f"启动失败：{error}", file=sys.stderr)
        return 1

    if check_only:
        print("调试启动检查通过：后端虚拟环境、前端依赖和 npm 均可用。")
        for service_name, command, working_directory in commands:
            print(f"  {service_name}: {working_directory} -> {' '.join(command)}")
        return 0

    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    processes = []
    display_startup_summary()

    try:
        for service_name, command, working_directory in commands:
            processes.append(start_process(service_name, command, working_directory, environment))

        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"\n调试服务异常结束，退出码：{return_code}", file=sys.stderr, flush=True)
                    return return_code if return_code != 0 else 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n正在停止前端和后端……", flush=True)
        return 0
    except (OSError, subprocess.SubprocessError) as error:
        print(f"\n启动失败：{error}", file=sys.stderr, flush=True)
        return 1
    finally:
        stop_processes(processes)
        if processes:
            print("前端和后端已停止。", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="一键启动奈亚米前后端调试服务")
    parser.add_argument("--check", action="store_true", help="仅检查调试启动条件，不启动服务")
    arguments = parser.parse_args()
    return run_development_services(check_only=arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
