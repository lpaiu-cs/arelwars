$ErrorActionPreference = "Stop"

$source = "C:\vs\other\arelwars\tools\arel_wars2\BstkSVCEnvLauncher.cs"
$output = "C:\vs\other\arelwars\tools\arel_wars2\BstkSVCEnvLauncher.exe"

Add-Type -TypeDefinition ([IO.File]::ReadAllText($source)) -OutputAssembly $output -OutputType ConsoleApplication
Write-Output $output
