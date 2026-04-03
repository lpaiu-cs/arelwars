$ErrorActionPreference = "Stop"

$dataDir = 'C:\ProgramData\BlueStacks_nxt'
$engineDir = Join-Path $dataDir 'Engine'
$instanceName = 'Nougat32'
$instanceEngineDir = Join-Path $engineDir $instanceName
$instanceRootDir = Join-Path $dataDir $instanceName
$userDataDir = Join-Path $dataDir 'UserData'
$inputMapperDir = Join-Path $userDataDir 'InputMapper'
$confPath = Join-Path $dataDir 'bluestacks.conf'
$appImagePreferencePath = Join-Path $dataDir 'AppImagePreference.json'

foreach ($dir in @(
    $dataDir,
    (Join-Path $dataDir 'Logs'),
    (Join-Path $dataDir 'Manager'),
    $engineDir,
    $instanceEngineDir,
    $userDataDir,
    $inputMapperDir,
    (Join-Path $inputMapperDir 'UserFiles'),
    (Join-Path $inputMapperDir 'UserScripts')
)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

$guid = 'd43b53f0-7578-4956-b95e-6a4b868d2070'
$versionMachineId = '4258b20c-ce11-4710-a0d7-9a11fe62afb9'
$confLines = @(
    'bst.version="5.22.166.1003"',
    "bst.guid=`"$guid`"",
    "bst.install_id=`"$guid`"",
    "bst.machine_id=`"$guid`"",
    "bst.version_machine_id=`"$versionMachineId`"",
    "bst.instance=`"$instanceName`"",
    "bst.installed_images=`"$instanceName`"",
    'bst.locale="en-US"',
    'bst.country="KR"',
    'bst.create_desktop_shortcuts="0"',
    'bst.dns_server="8.8.8.8"',
    'bst.dns_server2="10.0.2.3"',
    'bst.enable_adb_access="1"',
    'bst.enable_adb_remote_access="0"',
    'bst.enable_navigationbar="0"',
    'bst.enable_statusbar="1"',
    'bst.feature.rooting="0"',
    'bst.force_raw_mode="0"',
    'bst.key_controls_overlay_enabled="1"',
    'bst.key_controls_overlay_opacity="80"',
    'bst.log_levels="*:I"',
    'bst.mem_opt_mode="0"',
    'bst.mem_pcd_enabled="1"',
    'bst.mem_pcd_pclimit="40"',
    'bst.mem_pcr_enabled="0"',
    'bst.mem_pcr_pclimit="96"',
    'bst.mem_swap_enabled="0"',
    'bst.next_vm_id="1"',
    'bst.prefer_dedicated_gpu="0"',
    'bst.qt_renderer="Auto"',
    'bst.shared_folders="Documents,Pictures,InputMapper,BstSharedFolder"',
    'bst.status.hypervisor="vbox"',
    'bst.status.imap_schema_version="17"',
    'bst.status.raw_mode="0"',
    'bst.status.ssse3_available="1"',
    "bst.instance.$instanceName.display_name=`"$instanceName`"",
    "bst.instance.$instanceName.abi_list=`"x86,arm`"",
    "bst.instance.$instanceName.adb_port=`"5555`"",
    "bst.instance.$instanceName.status.adb_port=`"5555`"",
    "bst.instance.$instanceName.android_id=`"53d9d36ef9542265`"",
    "bst.instance.$instanceName.astc_decoding_mode=`"software`"",
    "bst.instance.$instanceName.boot_duration=`"-1`"",
    "bst.instance.$instanceName.cpus=`"2`"",
    "bst.instance.$instanceName.device_carrier_code=`"se_23410`"",
    "bst.instance.$instanceName.device_country_code=`"410`"",
    "bst.instance.$instanceName.device_profile_code=`"optr`"",
    "bst.instance.$instanceName.dpi=`"240`"",
    "bst.instance.$instanceName.eco_mode_max_fps=`"5`"",
    "bst.instance.$instanceName.enable_fps_display=`"0`"",
    "bst.instance.$instanceName.enable_high_fps=`"0`"",
    "bst.instance.$instanceName.enable_root_access=`"0`"",
    "bst.instance.$instanceName.enable_vsync=`"0`"",
    "bst.instance.$instanceName.fb_height=`"720`"",
    "bst.instance.$instanceName.fb_width=`"1280`"",
    "bst.instance.$instanceName.gl_win_height=`"-1`"",
    "bst.instance.$instanceName.gl_win_width=`"1280`"",
    "bst.instance.$instanceName.gl_win_x=`"0`"",
    "bst.instance.$instanceName.gl_win_y=`"0`"",
    "bst.instance.$instanceName.google_login_popup_shown=`"0`"",
    "bst.instance.$instanceName.graphics_engine=`"pga`"",
    "bst.instance.$instanceName.graphics_renderer=`"gl`"",
    "bst.instance.$instanceName.grm_ignored_rules=`"`"",
    "bst.instance.$instanceName.libc_mem_allocator=`"jem`"",
    "bst.instance.$instanceName.max_fps=`"60`"",
    "bst.instance.$instanceName.pin_to_top=`"0`"",
    "bst.instance.$instanceName.ram=`"1800`"",
    "bst.instance.$instanceName.show_sidebar=`"1`""
)
Set-Content -Path $confPath -Value $confLines -Encoding Ascii

if (-not (Test-Path -LiteralPath $appImagePreferencePath)) {
    Set-Content -Path $appImagePreferencePath -Value '{}' -Encoding Ascii
}

if (-not (Test-Path -LiteralPath $instanceRootDir)) {
    New-Item -ItemType Junction -Path $instanceRootDir -Target $instanceEngineDir | Out-Null
} elseif ((Get-Item -LiteralPath $instanceRootDir).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    # keep existing junction/symlink
} else {
    Write-Warning "$instanceRootDir already exists and is not a junction; leaving it as-is."
}

Write-Host "Seeded AW2 BlueStacks runtime layout."
Get-Item $confPath, $appImagePreferencePath | Select-Object FullName, Length, LastWriteTime
