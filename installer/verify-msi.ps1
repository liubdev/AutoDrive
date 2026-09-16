param([string]$Path = (Join-Path $PSScriptRoot '..\dist\AutoDrive-Setup.msi'))
$ErrorActionPreference = 'Stop'
$installer = New-Object -ComObject WindowsInstaller.Installer
$db = $installer.OpenDatabase([IO.Path]::GetFullPath($Path), 0)
function Read-Table([string]$Sql) {
    $view = $db.OpenView($Sql)
    [void]$view.Execute()
    $rows = @()
    while ($record = $view.Fetch()) {
        $values = @()
        $count = $record.GetType().InvokeMember('FieldCount', 'GetProperty', $null, $record, $null)
        for ($i = 1; $i -le $count; $i++) {
            $values += $record.GetType().InvokeMember('StringData', 'GetProperty', $null, $record, @($i))
        }
        $rows += ,$values
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($record)
    }
    [void]$view.Close()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($view)
    return ,$rows
}
try {
    $properties = @{}
    foreach ($row in (Read-Table 'SELECT `Property`, `Value` FROM `Property`')) { $properties[$row[0]] = $row[1] }
    if ($properties.AD_CREATE_DESKTOP -ne '1' -or $properties.AD_LAUNCH -ne '1') { throw 'Default choices missing' }
    if ($properties.ProductVersion -ne '1.0.1') { throw 'Unexpected product version' }
    $sequence = Read-Table 'SELECT `Action`, `Sequence` FROM `InstallUISequence`'
    if (-not ($sequence | Where-Object { $_[0] -eq 'AutoDriveExitDialog' -and $_[1] -eq '-1' })) { throw 'Completion page missing' }
    if ($sequence | Where-Object { $_[0] -eq 'ExitDialog' }) { throw 'Old completion page still scheduled' }
    $events = Read-Table 'SELECT `Dialog_`, `Control_`, `Event`, `Argument`, `Condition`, `Ordering` FROM `ControlEvent`'
    foreach ($action in @('PrepareDesktopShortcut', 'CreateDesktopShortcut', 'LaunchApplication')) {
        if (-not ($events | Where-Object { $_[0] -eq 'AutoDriveExitDialog' -and $_[3] -eq $action -and $_[4] -like '*NOT REMOVE*' })) { throw "Finish action missing: $action" }
    }
    $shortcuts = Read-Table 'SELECT `Shortcut` FROM `Shortcut`'
    if ($shortcuts | Where-Object { $_[0] -eq 'DesktopShortcut' }) { throw 'Unconditional desktop shortcut still present' }
    $execute = Read-Table 'SELECT `Action`, `Condition`, `Sequence` FROM `InstallExecuteSequence`'
    if (-not ($execute | Where-Object { $_[0] -eq 'RemoveDesktopShortcut' -and $_[1] -like '*UPGRADINGPRODUCTCODE*' })) { throw 'Uninstall cleanup missing' }
    if (-not ($events | Where-Object { $_[0] -eq 'VerifyReadyDlg' -and $_[2] -eq 'Reinstall' })) { throw 'Native repair event missing' }
    if (-not ($events | Where-Object { $_[0] -eq 'VerifyReadyDlg' -and $_[2] -eq 'Remove' })) { throw 'Native remove event missing' }
    Write-Host 'MSI_TABLES_OK: default choices, completion routing, finish actions, repair and removal'
} finally {
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($db)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer)
}
