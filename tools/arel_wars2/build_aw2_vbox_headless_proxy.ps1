$ErrorActionPreference = "Stop"

$source = "C:\vs\other\arelwars\tools\arel_wars2\VBoxHeadlessProxy.cs"
$output = "C:\vs\other\arelwars\tools\arel_wars2\VBoxHeadless.exe"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

& $csc /nologo /target:exe /out:$output $source
if ($LASTEXITCODE -ne 0) {
    throw "csc.exe failed with exit code $LASTEXITCODE"
}

Write-Output $output
