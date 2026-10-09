# 文件名称：run_frontend_tests.ps1
# 文件用途：运行前端自动化测试与生产构建
# 主要职责：执行 Vitest 和 TypeScript/Vite 构建
# 所属业务模块：测试脚本
# 创建时间：2026-07-28 13:01
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\frontend")
npm.cmd run test
npm.cmd run build
