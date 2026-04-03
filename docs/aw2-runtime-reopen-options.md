# AW2 Runtime Reopen Options

Audit date: 2026-04-03

## Current Situation

The official Android Emulator path is still exhausted on this host:

- the existing `x86_64` AVD rejects the original APK with `INSTALL_FAILED_NO_MATCHING_ABIS`
- the current emulator build cannot boot `ARMv7`
- the current emulator build cannot boot `ARM64`

That part has not changed.

## Leading Reopen Path

The strongest reopen path is now still the local `BlueStacks Nougat32` payload, but the route split is clearer:

- `Oracle VBox` can boot the guest into a stable black-screen state
- `BlueStacks portable client` is still the only path that could load BlueStacks custom device DLLs without Oracle VBox hardening

Prepared bootstrap materials:

- [aw2-bluestacks-admin-bootstrap.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-admin-bootstrap.md)
- [enable_aw2_bluestacks_admin_bootstrap.ps1](/C:/vs/other/arelwars/tools/arel_wars2/enable_aw2_bluestacks_admin_bootstrap.ps1)

The concrete Oracle VBox probe path is documented in [aw2-oracle-vbox-runtime-probe.md](/C:/vs/other/arelwars/docs/aw2-oracle-vbox-runtime-probe.md).

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
- official `adb` now sees `emulator-5554` but it remains `offline`

The new critical finding is that restoring the BlueStacks custom device path does not fix this under stock Oracle VBox.

It fails earlier:

- `HD-Vdes-Service.dll` is rejected by VirtualBox hardening
- the specific message is `TrustedInstaller is not the owner`
- startup aborts with `VERR_UNRESOLVED_ERROR`

That means the Oracle VBox route is currently trapped between two failure modes:

- `no bstdevices` -> stable black-screen boot candidate
- `with bstdevices` -> hardening rejection before guest startup

## Portable Client Path

The unpacked BlueStacks client binaries are present locally and the diagnosis is now sharper.

Current facts:

- COM registration is no longer the primary failure
- `BstkVMMgr.exe` now reaches `VirtualBoxWrap`
- direct `BstkSVC.exe --registervbox` still fails at `Could not create the VirtualBox home directory ''`
- `HD-Player.exe --instance Nougat32 --hidden` still crashes with `0xc0000005`
- no `adb-online` guest appears

So the portable path is now the only reopening route that might bypass the Oracle hardening block, but it is still not close enough to approve `Phase 1`.

## What This Means

The packaging track is no longer blocked by “no possible reopen path exists”.

It is now blocked by a narrower problem:

- the local Oracle VBox runtime has not yet reached `live original APK installability / adb-online observability`
- and the portable BlueStacks client path is still blocked by missing machine-level install context and non-bootstrapping player startup

That keeps `Route A` closed for now, even though the machine is much closer than before.

## Secondary Fallback

`BlueStacks 5` full install remains a fallback reopen path if the prepared elevated bootstrap script is not sufficient.

It is no longer the primary path because the Oracle VBox route is already partially working and locally reproducible.

## 2026-04-03 Late Update

The Oracle VBox route has improved further since the earlier black-screen note.

New facts:

- `BstkVMMgr list vms` is now stable
- `BstkVMMgr startvm Nougat32 --type headless` no longer dies at `VERR_FILE_NOT_FOUND`
- this works by providing a local `VBoxHeadless.exe` proxy and a `VirtualBox.xml` copy beside `BstkGlobal.xml`
- Oracle `VBoxManage` can now see `Nougat32` as `running`

But the runtime is still not approved because the route splits again at the VM config layer:

- `stripped Oracle-safe config` -> black screen, no `adb`, no guest OS detection
- `candidate config with BlueStacks items restored` -> startup fails with `device 'bstaudio' not found` / `VERR_PDM_DEVICE_NOT_FOUND`

This is a better blocker than before because it proves:

- the missing piece is no longer generic runtime absence
- the remaining gap is specifically the BlueStacks custom device implementation layer

So the reopen priority has shifted again.

New leading task:

- find a `6.1.36`-compatible frontend path that can load the BlueStacks custom PDM devices

This is now a higher-value next step than general `adb` polling on the black-screen profile.

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

## 2026-04-03 Night Update

The portable-client route also moved forward after the Oracle `bstaudio` split.

New facts:

- the patched [HD-Player.exe](/C:/vs/other/arelwars/$root/PF/HD-Player.exe) launch no longer dies with the earlier `0xc0000005`
- the immediate AV was caused by page-edge remote string placement in the patch helper
- the patched launcher can now keep `HD-Player` resident
- but that resident process still does not bring up `BstkVMMgr`, `VBoxHeadless`, guest logs, or `adb-online`

The strongest portable-path blocker is now more specific:

- `BlueStacksDrv_nxt` is not installed as a kernel service
- [BstkDrv_nxt.sys](/C:/vs/other/arelwars/$root/PF/BstkDrv_nxt.sys) is present and validly signed
- `sc.exe query BlueStacksDrv_nxt` returns `1060`

That makes the next privileged reopen step concrete:

- rerun [enable_aw2_bluestacks_admin_bootstrap.ps1](/C:/vs/other/arelwars/tools/arel_wars2/enable_aw2_bluestacks_admin_bootstrap.ps1) after its new driver-service registration step
- confirm `BlueStacksDrv_nxt` exists and starts
- retry the patched `HD-Player` launch and inspect whether the BlueStacks VBox stack finally comes online
