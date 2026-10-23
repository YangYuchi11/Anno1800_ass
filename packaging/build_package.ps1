# 构建免环境分发包：PyInstaller 打包 -> 组装 -> 压缩
# 用法（在项目根目录执行）：
#   powershell -ExecutionPolicy Bypass -File packaging\build_package.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "未找到项目虚拟环境：$python，请先创建 .venv 并安装 requirements.txt 与 pyinstaller"
}

Set-Location $root

& $python -m PyInstaller --noconfirm --clean "$root\AnnoCopilot.spec"

$distDir = Join-Path $root "dist\AnnoCopilot"
if (-not (Test-Path $distDir)) {
    throw "打包失败：未生成 $distDir"
}

Copy-Item "$root\README.md" $distDir -Force
Copy-Item "$PSScriptRoot\start_as_admin.bat" $distDir -Force
Copy-Item "$PSScriptRoot\使用说明.txt" $distDir -Force

$zip = Join-Path $root "dist\AnnoCopilot-win64.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}
Compress-Archive -Path $distDir -DestinationPath $zip -CompressionLevel Optimal

Write-Host "打包完成：$zip"
