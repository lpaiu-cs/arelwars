[CmdletBinding()]
param(
    [string]$ApkPath = "arel_wars1/arel_wars_1.apk",
    [string]$LibraryEntry = "lib/armeabi/libgameDSO.so",
    [string]$OutputRoot = "recovery/arel_wars1/disassembly",
    [string[]]$InterestingPattern = @(
        "PZx",
        "PZA",
        "PZF",
        "MPL",
        "Animation",
        "inflate",
        "ZT1"
    ),
    [string[]]$GraphRoots = @(
        "_ZN17CGsPzxResourceMgr4LoadEiPKcbb",
        "_ZN14CGsPzxResource4LoadEPKcbbiii",
        "_ZN9CGxPZxMgr4OpenEv",
        "_ZN9CGxPZxMgr7LoadAniEt",
        "_ZN9CGxPZxMgr9LoadFrameEt",
        "_ZN9CGxPZAMgr7LoadAniEtP9CGxPZFMgrP9CGxPZDMgr",
        "_ZN9CGxPZAMgr10LoadAniAllEP9CGxPZFMgrP9CGxPZDMgr",
        "_ZN12CGxPZAParser19DecodeAnimationDataEti",
        "_ZN9CGxPZxAni6DoPlayEv",
        "_ZN9CGxPZxAni25GetCurrentDelayFrameCountEv",
        "_Z9GsLoadPzxPKcbbiiii",
        "_Z12GsLoadPzxPalPKcS0_ibbiiii",
        "GxUncompressZT1"
    ),
    [switch]$SkipExtraction,
    [switch]$PassThru
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-U16 {
    param([byte[]]$Bytes, [int]$Offset)
    [BitConverter]::ToUInt16($Bytes, $Offset)
}

function Get-U32 {
    param([byte[]]$Bytes, [int]$Offset)
    [BitConverter]::ToUInt32($Bytes, $Offset)
}

function Get-CString {
    param([byte[]]$Bytes, [uint32]$Offset)

    $end = [int]$Offset
    while ($end -lt $Bytes.Length -and $Bytes[$end] -ne 0) {
        $end++
    }

    [System.Text.Encoding]::ASCII.GetString($Bytes, [int]$Offset, $end - [int]$Offset)
}

function Resolve-AbsolutePath {
    param([string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        $candidate = [System.IO.Path]::GetFullPath($Path)
    }
    else {
        $candidate = [System.IO.Path]::GetFullPath((Join-Path -Path ([string](Get-Location)) -ChildPath $Path))
    }
    if (Test-Path -LiteralPath $candidate) {
        return (Resolve-Path -LiteralPath $candidate).Path
    }
    return $candidate
}

function Ensure-Directory {
    param([string]$Path)

    $resolved = Resolve-AbsolutePath -Path $Path
    [System.IO.Directory]::CreateDirectory($resolved) | Out-Null
    $resolved
}

function Extract-LibraryFromApk {
    param(
        [string]$Apk,
        [string]$EntryName,
        [string]$DestinationRoot
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $destinationRoot = Ensure-Directory -Path $DestinationRoot
    $destination = Join-Path $destinationRoot ([System.IO.Path]::GetFileName($EntryName))

    $zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-AbsolutePath -Path $Apk))
    try {
        $entry = $zip.GetEntry($EntryName)
        if ($null -eq $entry) {
            throw "APK entry not found: $EntryName"
        }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $true)
    }
    finally {
        $zip.Dispose()
    }

    $destination
}

function Read-Elf32 {
    param([string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 52) {
        throw "ELF file is too short: $Path"
    }
    if ($bytes[0] -ne 0x7F -or $bytes[1] -ne 0x45 -or $bytes[2] -ne 0x4C -or $bytes[3] -ne 0x46) {
        throw "Not an ELF file: $Path"
    }
    if ($bytes[4] -ne 1) {
        throw "Only ELF32 is supported by this script."
    }
    if ($bytes[5] -ne 1) {
        throw "Only little-endian ELF is supported by this script."
    }

    $eShOff = Get-U32 -Bytes $bytes -Offset 32
    $eShEntSize = Get-U16 -Bytes $bytes -Offset 46
    $eShNum = Get-U16 -Bytes $bytes -Offset 48
    $eShStrNdx = Get-U16 -Bytes $bytes -Offset 50
    $machine = Get-U16 -Bytes $bytes -Offset 18

    $sections = New-Object 'System.Collections.Generic.List[object]'
    for ($index = 0; $index -lt $eShNum; $index++) {
        $offset = [int]$eShOff + $index * $eShEntSize
        $section = [pscustomobject]@{
            Index = $index
            NameOff = Get-U32 -Bytes $bytes -Offset $offset
            Type = Get-U32 -Bytes $bytes -Offset ($offset + 4)
            Flags = Get-U32 -Bytes $bytes -Offset ($offset + 8)
            Address = Get-U32 -Bytes $bytes -Offset ($offset + 12)
            Offset = Get-U32 -Bytes $bytes -Offset ($offset + 16)
            Size = Get-U32 -Bytes $bytes -Offset ($offset + 20)
            Link = Get-U32 -Bytes $bytes -Offset ($offset + 24)
            Info = Get-U32 -Bytes $bytes -Offset ($offset + 28)
            Align = Get-U32 -Bytes $bytes -Offset ($offset + 32)
            EntSize = Get-U32 -Bytes $bytes -Offset ($offset + 36)
            Name = ""
        }
        $sections.Add($section)
    }

    $shstr = $sections[$eShStrNdx]
    $shstrBytes = $bytes[$shstr.Offset..($shstr.Offset + $shstr.Size - 1)]
    foreach ($section in $sections) {
        $section.Name = Get-CString -Bytes $shstrBytes -Offset $section.NameOff
    }

    [pscustomobject]@{
        Path = $Path
        Bytes = $bytes
        Machine = $machine
        Sections = $sections
    }
}

function Read-Elf32Symbols {
    param(
        [pscustomobject]$Elf,
        [string]$SectionName = ".symtab"
    )

    $symtab = $Elf.Sections | Where-Object Name -eq $SectionName | Select-Object -First 1
    if ($null -eq $symtab) {
        throw "Missing symbol section: $SectionName"
    }
    if ($symtab.EntSize -ne 16) {
        throw "Unexpected symbol entry size: $($symtab.EntSize)"
    }

    $strtab = $Elf.Sections[[int]$symtab.Link]
    $strBytes = $Elf.Bytes[$strtab.Offset..($strtab.Offset + $strtab.Size - 1)]
    $symbols = New-Object 'System.Collections.Generic.List[object]'

    for ($offset = [int]$symtab.Offset; $offset -lt ($symtab.Offset + $symtab.Size); $offset += $symtab.EntSize) {
        $nameOffset = Get-U32 -Bytes $Elf.Bytes -Offset $offset
        $name = if ($nameOffset -eq 0) { "" } else { Get-CString -Bytes $strBytes -Offset $nameOffset }
        $value = Get-U32 -Bytes $Elf.Bytes -Offset ($offset + 4)
        $size = Get-U32 -Bytes $Elf.Bytes -Offset ($offset + 8)
        $info = $Elf.Bytes[$offset + 12]
        $other = $Elf.Bytes[$offset + 13]
        $shndx = Get-U16 -Bytes $Elf.Bytes -Offset ($offset + 14)
        $type = $info -band 0x0F
        $bind = $info -shr 4
        $sectionNameValue = if ($shndx -lt $Elf.Sections.Count) { $Elf.Sections[[int]$shndx].Name } else { "" }

        $symbols.Add([pscustomobject]@{
            Name = $name
            Value = $value
            Address = ($value -band 0xFFFFFFFE)
            Size = $size
            Thumb = [bool]($value -band 1)
            Type = $type
            Bind = $bind
            Other = $other
            Shndx = $shndx
            Section = $sectionNameValue
            ValueHex = ('0x{0:X8}' -f $value)
            AddressHex = ('0x{0:X8}' -f ($value -band 0xFFFFFFFE))
        })
    }

    $symbols
}

function Convert-VirtualAddressToFileOffset {
    param(
        [pscustomobject]$Elf,
        [uint32]$Address
    )

    foreach ($section in $Elf.Sections) {
        if ($section.Size -eq 0) {
            continue
        }
        if ($Address -ge $section.Address -and $Address -lt ($section.Address + $section.Size)) {
            return [int]($Address - $section.Address + $section.Offset)
        }
    }

    throw ('Virtual address 0x{0:X8} is not mapped to a file section.' -f $Address)
}

function Get-ThumbBranchTarget {
    param(
        [uint32]$InstructionAddress,
        [uint16]$HalfWord1,
        [uint16]$HalfWord2
    )

    if (($HalfWord1 -band 0xF800) -ne 0xF000) {
        return $null
    }
    if (($HalfWord2 -band 0xD000) -ne 0xD000) {
        return $null
    }

    $s = ($HalfWord1 -shr 10) -band 0x1
    $j1 = ($HalfWord2 -shr 13) -band 0x1
    $j2 = ($HalfWord2 -shr 11) -band 0x1
    $i1 = ((-bnot ($j1 -bxor $s)) -band 0x1)
    $i2 = ((-bnot ($j2 -bxor $s)) -band 0x1)
    $imm10 = $HalfWord1 -band 0x03FF
    $imm11 = $HalfWord2 -band 0x07FF
    $imm25 = ($s -shl 24) -bor ($i1 -shl 23) -bor ($i2 -shl 22) -bor ($imm10 -shl 12) -bor ($imm11 -shl 1)
    if (($imm25 -band 0x1000000) -ne 0) {
        $imm25 -= 0x2000000
    }

    $resolvedTarget = [int64]$InstructionAddress + 4 + [int64]$imm25
    if ($resolvedTarget -lt 0 -or $resolvedTarget -gt [uint32]::MaxValue) {
        return $null
    }

    [uint32]$resolvedTarget
}

function Resolve-FunctionByAddress {
    param(
        [uint32]$Address,
        [object[]]$Functions
    )

    $candidate = $null
    foreach ($function in $Functions) {
        if ($function.Address -le $Address -and ($function.Address + $function.Size) -gt $Address) {
            if ($null -eq $candidate -or $function.Address -gt $candidate.Address) {
                $candidate = $function
            }
        }
    }
    $candidate
}

function Get-ThumbCallEdges {
    param(
        [pscustomobject]$Elf,
        [object[]]$Functions
    )

    $edges = New-Object 'System.Collections.Generic.List[object]'
    foreach ($function in $Functions) {
        if (-not $function.Thumb -or $function.Size -lt 4 -or $function.Section -ne ".text") {
            continue
        }

        $functionOffset = Convert-VirtualAddressToFileOffset -Elf $Elf -Address $function.Address
        for ($delta = 0; $delta -le ($function.Size - 4); $delta += 2) {
            $half1 = Get-U16 -Bytes $Elf.Bytes -Offset ($functionOffset + $delta)
            $half2 = Get-U16 -Bytes $Elf.Bytes -Offset ($functionOffset + $delta + 2)
            $target = Get-ThumbBranchTarget -InstructionAddress ([uint32]($function.Address + $delta)) -HalfWord1 $half1 -HalfWord2 $half2
            if ($null -eq $target) {
                continue
            }

            $targetFunction = Resolve-FunctionByAddress -Address $target -Functions $Functions
            $edges.Add([pscustomobject]@{
                Source = $function.Name
                SourceAddress = ('0x{0:X8}' -f $function.Address)
                InstructionAddress = ('0x{0:X8}' -f ($function.Address + $delta))
                Target = if ($null -ne $targetFunction) { $targetFunction.Name } else { "" }
                TargetAddress = ('0x{0:X8}' -f $target)
            })
        }
    }

    $edges
}

function Get-CallerIndex {
    param(
        [object[]]$Edges,
        [string[]]$Targets
    )

    $index = [ordered]@{}
    foreach ($target in $Targets) {
        $callers = $Edges |
            Where-Object { $_.Target -eq $target } |
            Group-Object Source |
            ForEach-Object { $_.Name } |
            Sort-Object
        $index[$target] = @($callers)
    }
    $index
}

function Get-FunctionSummary {
    param(
        [object[]]$Symbols,
        [string[]]$Patterns
    )

    $regex = [regex]::new(($Patterns | ForEach-Object { [regex]::Escape($_) }) -join "|", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $Symbols |
        Where-Object { $_.Type -eq 2 -and $_.Name -and $regex.IsMatch($_.Name) } |
        Sort-Object Address, Name |
        Select-Object Name, ValueHex, AddressHex, Size, Thumb, Section
}

$outputRoot = Ensure-Directory -Path $OutputRoot
$libraryPath = if ($SkipExtraction) {
    Resolve-AbsolutePath -Path (Join-Path $outputRoot "libgameDSO.so")
}
else {
    Extract-LibraryFromApk -Apk $ApkPath -EntryName $LibraryEntry -DestinationRoot $OutputRoot
}

if (-not (Test-Path -LiteralPath $libraryPath)) {
    throw "Missing extracted library: $libraryPath"
}

$elf = Read-Elf32 -Path $libraryPath
$symbols = Read-Elf32Symbols -Elf $elf -SectionName ".symtab"
$functions = $symbols | Where-Object { $_.Type -eq 2 -and $_.Size -gt 0 -and $_.Section -eq ".text" } | Sort-Object Address, Name
$interestingFunctions = Get-FunctionSummary -Symbols $symbols -Patterns $InterestingPattern
$edges = Get-ThumbCallEdges -Elf $elf -Functions $functions

$presentRoots = $GraphRoots | Where-Object { $functions.Name -contains $_ }
$callGraph = [ordered]@{}
foreach ($root in $presentRoots) {
    $callGraph[$root] = @(
        $edges |
            Where-Object Source -eq $root |
            Group-Object Target, TargetAddress |
            ForEach-Object {
                $parts = $_.Name -split ",", 2
                [pscustomobject]@{
                    Target = if ($parts[0]) { $parts[0] } else { "" }
                    TargetAddress = $parts[1]
                    CallSiteCount = $_.Count
                }
            } |
            Sort-Object TargetAddress, Target
    )
}

$callerTargets = @(
    "_ZN12CGxPZAParser19DecodeAnimationDataEti",
    "_ZN9CGxPZxAni25GetCurrentDelayFrameCountEv",
    "_ZN9CGxPZxAni6DoPlayEv",
    "_Z11inflateInitP10z_stream_si",
    "_Z7inflateP10z_stream_si",
    "_Z10inflateEndP10z_stream_s",
    "GxUncompressZT1"
) | Where-Object { $functions.Name -contains $_ }

$report = [ordered]@{
    libraryPath = $libraryPath
    machine = ('0x{0:X4}' -f $elf.Machine)
    sectionSummary = @(
        $elf.Sections | Select-Object Index, Name, Address, Offset, Size, EntSize
    )
    interestingFunctions = @($interestingFunctions)
    callersOfTargets = Get-CallerIndex -Edges $edges -Targets $callerTargets
    callGraph = $callGraph
}

$reportJson = Join-Path $outputRoot "libgameDSO-report.json"
$interestingTsv = Join-Path $outputRoot "libgameDSO-interesting-functions.tsv"
$edgesJson = Join-Path $outputRoot "libgameDSO-call-edges.json"

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportJson -Encoding UTF8
$interestingFunctions |
    ForEach-Object {
        '{0}`t{1}`t{2}`t{3}`t{4}`t{5}' -f $_.ValueHex, $_.AddressHex, $_.Size, $_.Thumb, $_.Section, $_.Name
    } |
    Set-Content -LiteralPath $interestingTsv -Encoding UTF8
$edges | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $edgesJson -Encoding UTF8

$summaryLines = @(
    "libgameDSO: $libraryPath",
    "ELF machine: $('0x{0:X4}' -f $elf.Machine)",
    "Interesting functions: $($interestingFunctions.Count)",
    "Call edges: $($edges.Count)",
    "Report: $reportJson"
)
$summaryLines | Write-Output

if ($PassThru) {
    [pscustomobject]$report
}
