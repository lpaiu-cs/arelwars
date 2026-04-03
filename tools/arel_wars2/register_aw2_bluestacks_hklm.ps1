$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell window."
}

$installDir = 'C:\vs\other\arelwars\$root\PF'
$dataDir = 'C:\ProgramData\BlueStacks_nxt'
$logDir = 'C:\ProgramData\BlueStacks_nxt\Logs'

$targets = @(
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
    foreach ($entry in $target.Values.GetEnumerator()) {
        New-ItemProperty -Path $target.Path -Name $entry.Key -Value $entry.Value -PropertyType String -Force | Out-Null
    }
}

Write-Host "Updated HKLM BlueStacks bootstrap keys."
Get-ItemProperty 'HKLM:\SOFTWARE\BlueStacks_nxt' |
    Select-Object InstallDir, ClientInstallDir, UserDefinedDir, DataDir, LogDir |
    Format-List
