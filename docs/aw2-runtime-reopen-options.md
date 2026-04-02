# AW2 Runtime Reopen Options

Audit date: 2026-04-03

## Current Situation

The official Android Emulator path is still exhausted on this host:

- the existing `x86_64` AVD rejects the original APK with `INSTALL_FAILED_NO_MATCHING_ABIS`
- the current emulator build cannot boot `ARMv7`
- the current emulator build cannot boot `ARM64`

That part has not changed.

## Leading Reopen Path

The strongest local reopen path is no longer a hypothetical `BlueStacks 5` desktop install.

It is now:

- `Oracle VirtualBox`
- plus a locally unpacked `BlueStacks Nougat32` payload
- with the guest config patched into an Oracle-compatible shape

The concrete probe path is documented in [aw2-oracle-vbox-runtime-probe.md](/C:/vs/other/arelwars/docs/aw2-oracle-vbox-runtime-probe.md).

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

## What This Means

The packaging track is no longer blocked by “no possible reopen path exists”.

It is now blocked by a narrower problem:

- the local Oracle VBox runtime has not yet reached `live original APK installability / adb-online observability`

That keeps `Route A` closed for now, even though the machine is much closer than before.

## Secondary Fallback

`BlueStacks 5` full install remains a fallback reopen path if a privileged or UI-assisted install becomes available later.

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
