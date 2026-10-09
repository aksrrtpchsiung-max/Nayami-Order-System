# 文件名称：start_dev.ps1
# 文件用途：从 Windows PowerShell 一键启动奈亚米前后端调试服务
# 主要职责：定位项目虚拟环境并调用跨平台调试编排器
# 所属业务模块：本地开发脚本
# 创建时间：2026-08-06 11:49
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendPython = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $backendPython)) {
    Write-Error "启动失败：未找到 backend\.venv，请先执行 scripts\init_dev.ps1。"
    exit 1
}

& $backendPython (Join-Path $projectRoot "scripts\start_dev.py") @args
exit $LASTEXITCODE
