$ErrorActionPreference = "Stop"

$instanceDir = 'C:\vs\other\arelwars\$root\PD\Engine\Nougat32'
$targetPath = Join-Path $instanceDir 'Android.bstk'
$backupPath = Join-Path $instanceDir 'Android.bstk.pre-data-vdi-backup'
$dataVdiPath = Join-Path $instanceDir 'Data.vdi'
$vboxManage = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'

if (-not (Test-Path -LiteralPath $targetPath)) {
    throw "VM config not found: $targetPath"
}
if (-not (Test-Path -LiteralPath $dataVdiPath)) {
    throw "Data.vdi not found: $dataVdiPath"
}
if (-not (Test-Path -LiteralPath $vboxManage)) {
    throw "VBoxManage.exe not found: $vboxManage"
}

foreach ($name in 'HD-Player', 'BstkSVC', 'BstkVMMgr', 'VBoxHeadless', 'VBoxSVC') {
    Stop-Process -Name $name -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

attrib -R $targetPath 2>$null | Out-Null

if (-not (Test-Path -LiteralPath $backupPath)) {
    Copy-Item -LiteralPath $targetPath -Destination $backupPath -Force
}

$mediumInfo = & $vboxManage showmediuminfo disk $dataVdiPath
if ($LASTEXITCODE -ne 0) {
    throw "VBoxManage showmediuminfo failed for $dataVdiPath"
}

$dataUuid = $null
foreach ($line in $mediumInfo) {
    if ($line -match '^UUID:\s+(.+)$') {
        $dataUuid = $Matches[1].Trim()
        break
    }
}
if (-not $dataUuid) {
    throw "Unable to resolve Data.vdi UUID"
}

[xml]$xml = Get-Content -LiteralPath $targetPath
$ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
$ns.AddNamespace('v', 'http://www.virtualbox.org/')

$hardDisks = $xml.SelectSingleNode('//v:MediaRegistry/v:HardDisks', $ns)
if (-not $hardDisks) {
    throw 'Missing MediaRegistry/HardDisks node'
}

foreach ($node in @($hardDisks.SelectNodes("v:HardDisk[@location='Data.vhdx']", $ns))) {
    [void]$hardDisks.RemoveChild($node)
}

$dataDisk = $hardDisks.SelectSingleNode("v:HardDisk[@location='Data.vdi']", $ns)
if (-not $dataDisk) {
    $dataDisk = $xml.CreateElement('HardDisk', 'http://www.virtualbox.org/')
    [void]$hardDisks.AppendChild($dataDisk)
}
$null = $dataDisk.SetAttribute('uuid', '{' + $dataUuid + '}')
$null = $dataDisk.SetAttribute('location', 'Data.vdi')
$null = $dataDisk.SetAttribute('format', 'VDI')
$null = $dataDisk.SetAttribute('type', 'Normal')

$port1 = $xml.SelectSingleNode("//v:StorageController[@name='SATA']/v:AttachedDevice[@port='1']", $ns)
if (-not $port1) {
    throw "Missing SATA port 1 attachment"
}
$port1.SetAttribute('hotpluggable', 'false')
$image = $port1.SelectSingleNode('v:Image', $ns)
if (-not $image) {
    $image = $xml.CreateElement('Image', 'http://www.virtualbox.org/')
    [void]$port1.AppendChild($image)
}
$null = $image.SetAttribute('uuid', '{' + $dataUuid + '}')

$extraData = $xml.SelectSingleNode('//v:ExtraData', $ns)
if ($extraData) {
    foreach ($item in @($extraData.SelectNodes("v:ExtraDataItem[starts-with(@name,'VBoxInternal/Devices/bst') or @name='VBoxInternal/PDM/Devices/bstdevices/Path']", $ns))) {
        [void]$extraData.RemoveChild($item)
    }
}

$uart0 = $xml.SelectSingleNode("//v:Hardware/v:UART/v:Port[@slot='0']", $ns)
if ($uart0) {
    $null = $uart0.SetAttribute('enabled', 'false')
    $null = $uart0.RemoveAttribute('path')
}

$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$writer = [System.Xml.XmlWriter]::Create($targetPath, $settings)
try {
    $xml.Save($writer)
}
finally {
    $writer.Dispose()
}

attrib +R $targetPath 2>$null | Out-Null

Write-Host 'Applied AW2 Oracle candidate config: Data.vdi + bst* removal + UART0 disabled.'
[xml]$verify = Get-Content -LiteralPath $targetPath
$verifyNs = New-Object System.Xml.XmlNamespaceManager($verify.NameTable)
$verifyNs.AddNamespace('v', 'http://www.virtualbox.org/')
$verifyMedia = $verify.SelectNodes('//v:MediaRegistry/v:HardDisks/v:HardDisk', $verifyNs) | ForEach-Object {
    [pscustomobject]@{
        Location = $_.location
        Format = $_.format
        Uuid = $_.uuid
    }
}
$verifySata = $verify.SelectNodes("//v:StorageController[@name='SATA']/v:AttachedDevice", $verifyNs) | ForEach-Object {
    $img = $_.SelectSingleNode('v:Image', $verifyNs)
    [pscustomobject]@{
        Port = $_.port
        Device = $_.device
        Hotpluggable = $_.hotpluggable
        Uuid = $img.uuid
    }
}

Get-Item -LiteralPath $targetPath | Select-Object FullName, Length, LastWriteTime, Attributes
$verifyMedia | Format-Table -AutoSize
$verifySata | Format-Table -AutoSize
