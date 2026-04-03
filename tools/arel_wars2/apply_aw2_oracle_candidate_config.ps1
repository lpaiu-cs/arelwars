$ErrorActionPreference = "Stop"

$instanceDir = 'C:\vs\other\arelwars\$root\PD\Engine\Nougat32'
$templatePath = Join-Path $instanceDir 'Android.bstk.prev-with-bstitems'
$targetPath = Join-Path $instanceDir 'Android.bstk'
$backupPath = Join-Path $instanceDir 'Android.bstk.oracle-candidate-backup'
$serialLog = 'C:\vs\other\arelwars\recovery\arel_wars2\native_tmp\oracle_serial\nougat32-com1.log'

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Template not found: $templatePath"
}

Copy-Item -LiteralPath $targetPath -Destination $backupPath -Force

$content = Get-Content -LiteralPath $templatePath -Raw
$content = $content -replace '<NAT localhost-reachable="true"\s*/>', @'
<NAT localhost-reachable="true">
            <Forwarding name="adb" proto="1" hostip="127.0.0.1" hostport="5555" guestport="5555"/>
          </NAT>
'@
$content = $content -replace '<UART>\s*<Port slot="0" enabled="false" IOBase="0x3f8" IRQ="4" hostMode="Disconnected"/>\s*<Port slot="1" enabled="false" IOBase="0x2f8" IRQ="3" hostMode="Disconnected"/>\s*</UART>', @"
<UART>
        <Port slot=`"0`" enabled=`"true`" IOBase=`"0x3f8`" IRQ=`"4`" path=`"$serialLog`" hostMode=`"RawFile`"/>
        <Port slot=`"1`" enabled=`"false`" IOBase=`"0x2f8`" IRQ=`"3`" hostMode=`"Disconnected`"/>
      </UART>
"@

Set-Content -LiteralPath $targetPath -Value $content -Encoding UTF8

Write-Host "Applied AW2 Oracle candidate config from prev-with-bstitems."
Get-Item $targetPath, $backupPath | Select-Object FullName, Length, LastWriteTime
