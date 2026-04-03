# AW2 Runtime Reopen Options

Audit date: 2026-04-03

## Current Situation

The official Android Emulator path is still exhausted on this host:

- the existing `x86_64` AVD rejects the original APK with `INSTALL_FAILED_NO_MATCHING_ABIS`
- the current emulator build cannot boot `ARMv7`
- the current emulator build cannot boot `ARM64`

That part has not changed.

## Leading Reopen Path

The strongest reopen path is now a two-step BlueStacks route:

- local unpacked `BlueStacks Nougat32` payload
- plus an elevated bootstrap that recreates the missing machine-level install context

Prepared bootstrap materials:

- [aw2-bluestacks-admin-bootstrap.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-admin-bootstrap.md)
- [enable_aw2_bluestacks_admin_bootstrap.ps1](/C:/vs/other/arelwars/tools/arel_wars2/enable_aw2_bluestacks_admin_bootstrap.ps1)

The Oracle VBox path remains valuable, but it is no longer the clearest immediate reopen path.

The concrete probe path is documented in [aw2-oracle-vbox-runtime-probe.md](/C:/vs/other/arelwars/docs/aw2-oracle-vbox-runtime-probe.md).

The companion portable-client probe is documented in [aw2-bluestacks-portable-launch-probe.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-portable-launch-probe.md).

## What Exists Locally Now

The machine now has a real candidate runtime stack:

- `C:\Program Files\Oracle\VirtualBox\VBoxManage.exe`
- `C:\vs\other\arelwars\$root\PD\Engine\Nougat32\Android.bstk`
- `C:\vs\other\arelwars\$root\PD\Engine\Nougat32\Data.vdi`

The best current probe profile is:

- `oracle-ide-primaryslave-piix3-vga`

That profile:

- avoids the earlier `AHCI/libata` panic
- avoids the earlier `ACPI reset` loop
- stays up for at least `180` seconds in the probe window
- still does **not** bring `adb` online

So this is a `candidate runtime`, not an approved oracle environment.

More precise current state:

- `guestproperty enumerate` exposes only host/VM metadata
- `debugvm osdetect` still cannot detect a guest OS
- UART raw-file capture remains empty
- live storage statistics show only `1024` bytes read from the boot disk

That points to a stall before meaningful guest userspace startup.

## Portable Client Path

The unpacked BlueStacks client binaries are present locally and the diagnosis is now sharper.

Current facts:

- COM registration is no longer the primary failure
- `BstkVMMgr.exe` now reaches `VirtualBoxWrap`
- object creation still fails at `Could not create the VirtualBox home directory ''`
- direct `BstkSVC.exe --registervbox` reproduces the same empty-home failure in `BstkServer.log`
- `HD-Player.exe --instance Nougat32 --hidden` still crashes with `0xc0000005`
- no `adb-online` guest appears

So the portable path is close enough to justify one elevated bootstrap attempt, but not close enough to approve `Phase 1`.

## What This Means

The packaging track is no longer blocked by “no possible reopen path exists”.

It is now blocked by a narrower problem:

- the local Oracle VBox runtime has not yet reached `live original APK installability / adb-online observability`
- and the portable BlueStacks client path is still blocked by missing machine-level install context and non-bootstrapping player startup

That keeps `Route A` closed for now, even though the machine is much closer than before.

## Secondary Fallback

`BlueStacks 5` full install remains a fallback reopen path if the prepared elevated bootstrap script is not sufficient.

It is no longer the primary path because the Oracle VBox route is already partially working and locally reproducible.

## Local Regeneration

Refresh the reopen summary with:

```powershell
python tools/arel_wars2/probe_aw2_runtime_reopen_options.py
```

Refresh the strongest current Oracle probe with:

```powershell
python tools/arel_wars2/probe_aw2_oracle_vbox_runtime.py --variant oracle-ide-primaryslave-piix3-vga --wait-seconds 180
```

Run the prepared privileged BlueStacks bootstrap with:

```powershell
powershell -ExecutionPolicy Bypass -File C:\vs\other\arelwars\tools\arel_wars2\enable_aw2_bluestacks_admin_bootstrap.ps1
```
