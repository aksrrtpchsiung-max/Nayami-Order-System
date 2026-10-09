# 文件名称：init_dev.ps1
# 文件用途：初始化奈亚米订单系统本地 MySQL 演示数据
# 主要职责：安装依赖并顺序执行建库、演示基础数据和优惠券活动 SQL
# 所属业务模块：本地开发脚本
# 创建时间：2026-05-22 14:05
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Set-Location (Join-Path $projectRoot "backend")
if (-not (Test-Path ".venv")) {
    py -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

Set-Location (Join-Path $projectRoot "frontend")
npm.cmd ci

Set-Location $projectRoot
& "backend\.venv\Scripts\python.exe" "scripts\upgrade_database.py"
& "backend\.venv\Scripts\python.exe" "scripts\seed_demo_data.py"

Write-Host "Nayami development environment initialized."
