param(
    [Parameter(Mandatory=$true)][ValidateSet('Create', 'Remove')][string]$Action,
    [Parameter(Mandatory=$true)][string]$AppPath,
    [string]$DesktopPath = [Environment]::GetFolderPath('DesktopDirectory')
)
$ErrorActionPreference = 'Stop'
$app = [IO.Path]::GetFullPath($AppPath)
$linkPath = Join-Path $DesktopPath 'AutoDrive.lnk'
$shell = New-Object -ComObject WScript.Shell
try {
    if ($Action -eq 'Create') {
        if (-not (Test-Path -LiteralPath $app -PathType Leaf)) { throw 'AutoDrive executable is missing.' }
        $link = $shell.CreateShortcut($linkPath)
        $link.TargetPath = $app
        $link.WorkingDirectory = Split-Path -Parent $app
        $link.IconLocation = (Join-Path $link.WorkingDirectory 'icon.ico') + ',0'
        $link.Description = 'AutoDrive - RunchTech'
        $link.Save()
    } elseif (Test-Path -LiteralPath $linkPath -PathType Leaf) {
        $link = $shell.CreateShortcut($linkPath)
        # Never remove another application's shortcut with the same display name.
        if ([string]::Equals($link.TargetPath, $app, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $linkPath -Force
        }
    }
} finally {
    if ($link) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($link) }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)
}
