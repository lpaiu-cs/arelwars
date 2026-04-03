$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell window."
}

$installDir = 'C:\Program Files\BlueStacks_nxt'
$dataDir = 'C:\ProgramData\BlueStacks_nxt'
$logDir = 'C:\ProgramData\BlueStacks_nxt\Logs'

$targets = @(
    @{
        Path = 'HKLM:\SOFTWARE\BlueStacks'
        Values = @{
            InstallDir = $installDir
            ClientInstallDir = $installDir
            UserDefinedDir = $dataDir
            DataDir = $dataDir
            LogDir = $logDir
        }
    }
    @{
        Path = 'HKLM:\SOFTWARE\BlueStacks_nxt'
        Values = @{
            InstallDir = $installDir
            ClientInstallDir = $installDir
            UserDefinedDir = $dataDir
            DataDir = $dataDir
            LogDir = $logDir
        }
    }
    @{
        Path = 'HKLM:\SOFTWARE\BlueStacksServices'
        Values = @{
            InstallDir = $installDir
            ClientInstallDir = $installDir
            UserDefinedDir = $dataDir
            DataDir = $dataDir
            LogDir = $logDir
        }
    }
)

foreach ($target in $targets) {
    New-Item -Path $target.Path -Force | Out-Null
    $regNativePath = $target.Path -replace '^([A-Z]+):\\', '$1\'
    foreach ($entry in $target.Values.GetEnumerator()) {
        & reg.exe add $regNativePath /v $entry.Key /t REG_SZ /d $entry.Value /f /reg:64 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to set $($target.Path)::$($entry.Key)"
        }
    }
}

Write-Host "Updated HKLM BlueStacks bootstrap keys."
foreach ($path in 'HKLM:\SOFTWARE\BlueStacks', 'HKLM:\SOFTWARE\BlueStacks_nxt', 'HKLM:\SOFTWARE\BlueStacksServices') {
    Write-Host "[$path]"
    Get-ItemProperty $path |
        Select-Object InstallDir, ClientInstallDir, UserDefinedDir, DataDir, LogDir |
        Format-List
}
