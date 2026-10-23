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

# 清理运行时产生的本机状态，避免把校准/扫描数据打进分发包
Remove-Item (Join-Path $distDir "anno_coords_config.json") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $distDir "anno_islands_data.json") -Force -ErrorAction SilentlyContinue

$zip = Join-Path $root "dist\AnnoCopilot-win64.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}

$zipped = $false
for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
        Compress-Archive -Path $distDir -DestinationPath $zip -CompressionLevel Optimal -ErrorAction Stop
        $zipped = $true
        break
    } catch {
        Write-Warning "压缩失败（第 $attempt 次）：$($_.Exception.Message)"
        if (Test-Path $zip) {
            Remove-Item $zip -Force
        }
        Start-Sleep -Seconds 3
    }
}
if (-not $zipped) {
    throw "压缩失败：$zip（请检查是否有进程占用 dist 目录中的文件）"
}

Write-Host "打包完成：$zip"
