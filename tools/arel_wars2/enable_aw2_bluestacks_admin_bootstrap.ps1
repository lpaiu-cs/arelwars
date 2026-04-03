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
    $regNativePath = $RegistryPath -replace '^([A-Z]+):\\', '$1\'
    & reg.exe add $regNativePath /v $Name /t REG_SZ /d $Value /f /reg:64 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to set registry value $RegistryPath::$Name"
    }
}

function Get-StringValueSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RegistryPath,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    try {
        $value = Get-ItemPropertyValue -Path $RegistryPath -Name $Name -ErrorAction Stop
        if ($null -eq $value) {
            return $null
        }
        return [string]$value
    }
    catch {
        return $null
    }
}

function Ensure-KernelService {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$BinaryPath
    )

    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $service) {
        & sc.exe create $Name type= kernel start= demand error= normal binPath= $BinaryPath | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create service $Name"
        }
    }

    & sc.exe config $Name start= demand binPath= $BinaryPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to configure service $Name"
    }

    $state = (& sc.exe query $Name) -join "`n"
    if ($state -notmatch "RUNNING") {
        & sc.exe start $Name | Out-Null
        Start-Sleep -Seconds 1
    }
}

function Ensure-TrustedInstallerOwner {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Path not found: $Path"
    }

    $owner = (Get-Acl -LiteralPath $Path).Owner
    if ($owner -eq "NT SERVICE\TrustedInstaller") {
        return
    }

    & icacls.exe $Path /setowner "NT SERVICE\TrustedInstaller" /C | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to set TrustedInstaller owner on $Path"
    }

    $owner = (Get-Acl -LiteralPath $Path).Owner
    if ($owner -ne "NT SERVICE\TrustedInstaller") {
        throw "TrustedInstaller owner did not stick on $Path (owner=$owner)"
    }
}

Assert-Admin

$repoRoot = "C:\vs\other\arelwars"
$portableRoot = Join-Path $repoRoot '$root'
$portablePf = Join-Path $portableRoot 'PF'
$portablePd = Join-Path $portableRoot 'PD'
$machinePf = "C:\Program Files\BlueStacks_nxt"
$machinePd = "C:\ProgramData\BlueStacks_nxt"
$bstkTmp = "C:\bstk"
$driverName = "BlueStacksDrv_nxt"
$driverBinary = Join-Path $machinePf "BstkDrv_nxt.sys"
$vdesModule = Join-Path $portablePf "HD-Vdes-Service.dll"

Ensure-Directory -Path $bstkTmp
Ensure-Junction -Path $machinePd -Target $portablePd
Ensure-Junction -Path $machinePf -Target $portablePf

$blueStacksKey = "HKLM:\SOFTWARE\BlueStacks"
$blueStacksServicesKey = "HKLM:\SOFTWARE\BlueStacksServices"
$blueStacksNxtKey = "HKLM:\SOFTWARE\BlueStacks_nxt"
$userBlueStacksKey = "HKCU:\Software\BlueStacks"
$userBlueStacksServicesKey = "HKCU:\Software\BlueStacksServices"

foreach ($key in @(
    $blueStacksKey,
    $blueStacksServicesKey,
    $blueStacksNxtKey,
    $userBlueStacksKey,
    $userBlueStacksServicesKey
)) {
    Set-StringValue -RegistryPath $key -Name "InstallDir" -Value $machinePf
    Set-StringValue -RegistryPath $key -Name "ClientInstallDir" -Value $machinePf
    Set-StringValue -RegistryPath $key -Name "UserDefinedDir" -Value $machinePd
    Set-StringValue -RegistryPath $key -Name "DataDir" -Value $machinePd
    Set-StringValue -RegistryPath $key -Name "LogDir" -Value (Join-Path $machinePd "Logs")
}

[Environment]::SetEnvironmentVariable("HOME", $env:USERPROFILE, "Machine")
[Environment]::SetEnvironmentVariable("VBOX_USER_HOME", (Join-Path $machinePd "Engine\Manager"), "Machine")
[Environment]::SetEnvironmentVariable("VBOX_APP_HOME", $machinePd, "Machine")
[Environment]::SetEnvironmentVariable("HOME", $env:USERPROFILE, "User")
[Environment]::SetEnvironmentVariable("VBOX_USER_HOME", (Join-Path $machinePd "Engine\Manager"), "User")
[Environment]::SetEnvironmentVariable("VBOX_APP_HOME", $machinePd, "User")

Ensure-KernelService -Name $driverName -BinaryPath $driverBinary
Ensure-TrustedInstallerOwner -Path $vdesModule

& "C:\Program Files\Oracle\VirtualBox\VBoxSVC.exe" /reregserver
& "C:\Windows\System32\regsvr32.exe" /s (Join-Path $portablePf "BstkProxyStub.dll")

$summary = [pscustomobject]@{
    programFilesPath = $machinePf
    programFilesExists = Test-Path -LiteralPath $machinePf
    programDataPath = $machinePd
    programDataExists = Test-Path -LiteralPath $machinePd
    blueStacksInstallDir = Get-StringValueSafe -RegistryPath $blueStacksKey -Name "InstallDir"
    blueStacksDataDir = Get-StringValueSafe -RegistryPath $blueStacksKey -Name "DataDir"
    blueStacksServicesInstallDir = Get-StringValueSafe -RegistryPath $blueStacksServicesKey -Name "InstallDir"
    blueStacksServicesDataDir = Get-StringValueSafe -RegistryPath $blueStacksServicesKey -Name "DataDir"
    blueStacksNxtInstallDir = Get-StringValueSafe -RegistryPath $blueStacksNxtKey -Name "InstallDir"
    blueStacksNxtDataDir = Get-StringValueSafe -RegistryPath $blueStacksNxtKey -Name "DataDir"
    userBlueStacksInstallDir = Get-StringValueSafe -RegistryPath $userBlueStacksKey -Name "InstallDir"
    userBlueStacksDataDir = Get-StringValueSafe -RegistryPath $userBlueStacksKey -Name "DataDir"
    userBlueStacksServicesInstallDir = Get-StringValueSafe -RegistryPath $userBlueStacksServicesKey -Name "InstallDir"
    userBlueStacksServicesDataDir = Get-StringValueSafe -RegistryPath $userBlueStacksServicesKey -Name "DataDir"
    machineHome = [Environment]::GetEnvironmentVariable("HOME", "Machine")
    machineVBoxUserHome = [Environment]::GetEnvironmentVariable("VBOX_USER_HOME", "Machine")
    machineVBoxAppHome = [Environment]::GetEnvironmentVariable("VBOX_APP_HOME", "Machine")
    userHome = [Environment]::GetEnvironmentVariable("HOME", "User")
    userVBoxUserHome = [Environment]::GetEnvironmentVariable("VBOX_USER_HOME", "User")
    userVBoxAppHome = [Environment]::GetEnvironmentVariable("VBOX_APP_HOME", "User")
    driverService = $driverName
    driverBinary = $driverBinary
    driverServiceState = ((& sc.exe query $driverName) -join "`n")
    vdesModule = $vdesModule
    vdesModuleOwner = (Get-Acl -LiteralPath $vdesModule).Owner
}

$summary | ConvertTo-Json -Depth 4
