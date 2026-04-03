$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell window."
    }
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Ensure-Junction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Target
    )

    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            return
        }
        throw "Path already exists and is not a junction: $Path"
    }

    $parent = Split-Path -Parent $Path
    Ensure-Directory -Path $parent
    New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
}

function Set-StringValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RegistryPath,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )
    New-Item -Path $RegistryPath -Force | Out-Null
    New-ItemProperty -Path $RegistryPath -Name $Name -PropertyType String -Value $Value -Force | Out-Null
}

Assert-Admin

$repoRoot = "C:\vs\other\arelwars"
$portableRoot = Join-Path $repoRoot '$root'
$portablePf = Join-Path $portableRoot 'PF'
$portablePd = Join-Path $portableRoot 'PD'
$machinePf = "C:\Program Files\BlueStacks_nxt"
$machinePd = "C:\ProgramData\BlueStacks_nxt"
$bstkTmp = "C:\bstk"

Ensure-Directory -Path $bstkTmp
Ensure-Junction -Path $machinePd -Target $portablePd
Ensure-Junction -Path $machinePf -Target $portablePf

$blueStacksKey = "HKLM:\SOFTWARE\BlueStacks"
$blueStacksServicesKey = "HKLM:\SOFTWARE\BlueStacksServices"

foreach ($key in @($blueStacksKey, $blueStacksServicesKey)) {
    Set-StringValue -RegistryPath $key -Name "InstallDir" -Value $machinePf
    Set-StringValue -RegistryPath $key -Name "ClientInstallDir" -Value $machinePf
    Set-StringValue -RegistryPath $key -Name "UserDefinedDir" -Value $machinePd
    Set-StringValue -RegistryPath $key -Name "DataDir" -Value $machinePd
    Set-StringValue -RegistryPath $key -Name "LogDir" -Value (Join-Path $machinePd "Logs")
}

[Environment]::SetEnvironmentVariable("HOME", $env:USERPROFILE, "Machine")
[Environment]::SetEnvironmentVariable("VBOX_USER_HOME", (Join-Path $machinePd "Engine\Manager"), "Machine")
[Environment]::SetEnvironmentVariable("VBOX_APP_HOME", $machinePd, "Machine")

& "C:\Program Files\Oracle\VirtualBox\VBoxSVC.exe" /reregserver
& "C:\Windows\System32\regsvr32.exe" /s (Join-Path $portablePf "BstkProxyStub.dll")

$summary = [pscustomobject]@{
    programFilesPath = $machinePf
    programFilesExists = Test-Path -LiteralPath $machinePf
    programDataPath = $machinePd
    programDataExists = Test-Path -LiteralPath $machinePd
    blueStacksInstallDir = Get-ItemPropertyValue -Path $blueStacksKey -Name "InstallDir"
    blueStacksDataDir = Get-ItemPropertyValue -Path $blueStacksKey -Name "DataDir"
    blueStacksServicesInstallDir = Get-ItemPropertyValue -Path $blueStacksServicesKey -Name "InstallDir"
    blueStacksServicesDataDir = Get-ItemPropertyValue -Path $blueStacksServicesKey -Name "DataDir"
    machineHome = [Environment]::GetEnvironmentVariable("HOME", "Machine")
    machineVBoxUserHome = [Environment]::GetEnvironmentVariable("VBOX_USER_HOME", "Machine")
    machineVBoxAppHome = [Environment]::GetEnvironmentVariable("VBOX_APP_HOME", "Machine")
}

$summary | ConvertTo-Json -Depth 4
