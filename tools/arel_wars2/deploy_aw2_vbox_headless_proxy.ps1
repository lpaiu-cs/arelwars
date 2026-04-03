$ErrorActionPreference = "Stop"

$sourceExe = "C:\vs\other\arelwars\tools\arel_wars2\VBoxHeadless.exe"
$targetExe = "C:\vs\other\arelwars\$root\PF\VBoxHeadless.exe"

if (-not (Test-Path -LiteralPath $sourceExe)) {
    throw "Build the proxy first: $sourceExe not found."
}

Copy-Item -LiteralPath $sourceExe -Destination $targetExe -Force
Get-Item $targetExe | Select-Object FullName, Length, LastWriteTime
