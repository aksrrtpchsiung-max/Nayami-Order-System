#!/bin/sh
# 文件名称：entrypoint.sh
# 文件用途：在 API 启动前升级数据库，兼容既有演示数据卷
# 主要职责：执行 Alembic 迁移后启动服务，不删除业务数据
# 所属业务模块：部署
# 创建时间：2026-09-08 17:40
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers
set -eu

if [ "$1" = "gunicorn" ]; then
  python -m alembic upgrade head
fi

exec "$@"
