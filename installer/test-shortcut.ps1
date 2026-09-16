$ErrorActionPreference = 'Stop'
$testRoot = Join-Path $PSScriptRoot ('shortcut-test-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot | Out-Null
$app = Join-Path $env:WINDIR 'notepad.exe'
$linkPath = Join-Path $testRoot 'AutoDrive.lnk'
$shell = New-Object -ComObject WScript.Shell
try {
    & "$PSScriptRoot\shortcut.ps1" -Action Create -AppPath $app -DesktopPath $testRoot
    $link = $shell.CreateShortcut($linkPath)
    if ($link.TargetPath -ne $app) { throw 'Shortcut target mismatch' }
    if ($link.IconLocation -notlike '*icon.ico,0') { throw 'Shortcut icon mismatch' }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($link)
    & "$PSScriptRoot\shortcut.ps1" -Action Remove -AppPath (Join-Path $env:WINDIR 'other.exe') -DesktopPath $testRoot
    if (-not (Test-Path -LiteralPath $linkPath)) { throw 'Unrelated shortcut was deleted' }
    & "$PSScriptRoot\shortcut.ps1" -Action Remove -AppPath $app -DesktopPath $testRoot
    if (Test-Path -LiteralPath $linkPath) { throw 'Owned shortcut was not removed' }
    & "$PSScriptRoot\shortcut.ps1" -Action Remove -AppPath $app -DesktopPath $testRoot
    Write-Host 'SHORTCUT_TESTS_OK'
} finally {
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)
    if (Test-Path -LiteralPath $linkPath) { Remove-Item -LiteralPath $linkPath -Force }
    Remove-Item -LiteralPath $testRoot
}
