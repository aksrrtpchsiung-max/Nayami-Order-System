#!/usr/bin/env bash
# 文件名称：init_dev.sh
# 文件用途：初始化 macOS/Linux 本地开发环境
# 主要职责：安装依赖、创建数据库结构并写入演示数据
# 所属业务模块：本地开发脚本
# 创建时间：2026-07-28 13:01
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "${project_root}/backend/.venv" ]]; then
  python3 -m venv "${project_root}/backend/.venv"
fi

"${project_root}/backend/.venv/bin/python" -m pip install -r "${project_root}/backend/requirements.txt"
npm --prefix "${project_root}/frontend" ci
"${project_root}/backend/.venv/bin/python" "${project_root}/scripts/upgrade_database.py"
"${project_root}/backend/.venv/bin/python" "${project_root}/scripts/seed_demo_data.py"

echo "Development environment initialized. Start backend, Redis, Celery and frontend as described in README.md."
