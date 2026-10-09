# 文件名称：run_backend_tests.ps1
# 文件用途：运行奈亚米订单系统后端测试
# 主要职责：设置测试环境变量并执行 pytest
# 所属业务模块：测试脚本
# 创建时间：2026-05-22 14:05
# 最近修改时间：2026-10-09 14:06
# 修改人：Project Maintainers

$ErrorActionPreference = "Stop"
$env:FLASK_ENV = "testing"
Set-Location backend
py -m pytest
