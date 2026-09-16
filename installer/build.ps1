param(
    [switch]$SkipFreeze
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

if (-not $SkipFreeze) {
    Push-Location $Root
    try {
        & $Python setup.py build_exe
        if ($LASTEXITCODE -ne 0) { throw "cx_Freeze 构建失败" }
    }
    finally {
        Pop-Location
    }
}

$AppDir = Get-ChildItem (Join-Path $Root "build") -Directory -Filter "exe.*" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $AppDir) { throw "未找到 cx_Freeze 输出目录，请先运行 setup.py build_exe" }
if (-not (Test-Path (Join-Path $AppDir.FullName "AutoDrive.exe"))) {
    throw "未找到 AutoDrive.exe。请重新运行 setup.py build_exe，确保 setup.py 为主入口设置 target_name=AutoDrive.exe。"
}

$WixCommand = Get-Command wix -ErrorAction SilentlyContinue
$WixExe = if ($WixCommand) { $WixCommand.Source } else { Join-Path $env:ProgramFiles 'WiX Toolset v7.0\bin\wix.exe' }
if (-not (Test-Path -LiteralPath $WixExe)) {
    throw "未找到 WiX Toolset。请安装 WiX v7，并确保 wix.exe 已加入 PATH。"
}

$Dist = Join-Path $Root "dist"
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

$WixArgs = @(
    "build",
    "-acceptEula", "wix7",
    (Join-Path $PSScriptRoot "AutoDrive.wxs"),
    "-arch", "x64",
    "-ext", "WixToolset.UI.wixext",
    "-ext", "WixToolset.Util.wixext",
    "-loc", (Join-Path $PSScriptRoot "AutoDrive.wxl"),
    "-d", "AppDir=$($AppDir.FullName)",
    "-d", "IconPath=$(Join-Path $Root 'icon.ico')",
    "-d", "DialogPath=$(Join-Path $PSScriptRoot 'dialog.bmp')",
    "-o", (Join-Path $Dist "AutoDrive-Setup.msi")
)

Write-Host "WiX 源文件: $($WixArgs[3])"
Write-Host "WiX 输出文件: $($WixArgs[$WixArgs.Count - 1])"
& $WixExe @WixArgs
if ($LASTEXITCODE -ne 0) { throw "WiX MSI 构建失败" }

Write-Host "已生成: $(Join-Path $Dist 'AutoDrive-Setup.msi')"
