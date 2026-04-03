$ErrorActionPreference = "Stop"

$instanceDir = 'C:\vs\other\arelwars\$root\PD\Engine\Nougat32'
$targetPath = Join-Path $instanceDir 'Android.bstk'
$templatePath = Join-Path $instanceDir 'Android.bstk.in'
$confPath = 'C:\ProgramData\BlueStacks_nxt\bluestacks.conf'
$installedVdes = 'C:\Program Files\BlueStacks_nxt\HD-Vdes-Service.dll'

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Template not found: $templatePath"
}
if (-not (Test-Path -LiteralPath $confPath)) {
    throw "BlueStacks config not found: $confPath"
}
if (-not (Test-Path -LiteralPath $installedVdes)) {
    throw "Installed HD-Vdes-Service.dll not found: $installedVdes"
}

$running = Get-Process HD-Player, HD-MultiInstanceManager, BstkSVC, BstkVMMgr -ErrorAction SilentlyContinue
if ($running) {
    $names = ($running | Select-Object -ExpandProperty ProcessName | Sort-Object -Unique) -join ', '
    throw "BlueStacks processes must be stopped before restoring template config. Running: $names"
}

$memoryMb = '1800'
foreach ($line in Get-Content -LiteralPath $confPath) {
    if ($line -match '^bst\.instance\.Nougat32\.ram=\"(\d+)\"$') {
        $memoryMb = $Matches[1]
        break
    }
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (Test-Path -LiteralPath $targetPath) {
    Copy-Item -LiteralPath $targetPath -Destination (Join-Path $instanceDir ("Android.bstk.pre-template-restore-" + $timestamp)) -Force
    attrib -R $targetPath 2>$null | Out-Null
}

$content = Get-Content -LiteralPath $templatePath -Raw
$content = $content.Replace('@@HD_VDES_SERVICE_DLL_PATH@@', $installedVdes)
$content = $content.Replace('@@BST_VM_MEMORY_SIZE@@', $memoryMb)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($targetPath, $content, $utf8NoBom)
attrib +R $targetPath 2>$null | Out-Null

Write-Host "Restored AW2 BlueStacks template config."
Write-Host "Target: $targetPath"
Write-Host "MemoryMB: $memoryMb"
Write-Host "HDVdesPath: $installedVdes"
Get-Item -LiteralPath $targetPath | Select-Object FullName, Length, LastWriteTime, Attributes | Format-List
