#!/usr/bin/env bash
# 文件名称：start_dev.sh
# 文件用途：从 macOS/Linux 一键启动奈亚米前后端调试服务
# 主要职责：定位项目虚拟环境并调用跨平台调试编排器
# 所属业务模块：本地开发脚本
# 创建时间：2026-08-06 11:49
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_python="${project_root}/backend/.venv/bin/python"

if [[ ! -x "${backend_python}" ]]; then
  echo "启动失败：未找到 backend/.venv，请先执行 bash ./scripts/init_dev.sh。" >&2
  exit 1
fi

exec "${backend_python}" "${project_root}/scripts/start_dev.py" "$@"
