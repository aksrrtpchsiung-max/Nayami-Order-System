# 文件名称：start_frontend.ps1
# 文件用途：启动奈亚米订单系统前端开发服务
# 主要职责：进入 frontend 目录并运行 Vite 开发服务
# 所属业务模块：本地开发脚本
# 创建时间：2026-05-22 14:05
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..\frontend")
npm.cmd run dev -- --host 127.0.0.1
