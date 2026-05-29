# Usage (from project root):
#     powershell -ExecutionPolicy Bypass -File .\create_shortcut.ps1

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$target    = Join-Path $scriptDir 'start.bat'
$icon      = Join-Path $scriptDir 'core\icon.ico'
$lnkPath   = Join-Path $scriptDir 'Script-U-Need.lnk'

if (-not (Test-Path $target)) { throw "Not found: $target" }
if (-not (Test-Path $icon))   { throw "Not found: $icon" }

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath       = $target
$lnk.WorkingDirectory = $scriptDir
$lnk.IconLocation     = "$icon,0"
$lnk.Description      = 'Script-U-Need'
$lnk.WindowStyle      = 1
$lnk.Save()

Write-Host "Shortcut is ready: $lnkPath"
