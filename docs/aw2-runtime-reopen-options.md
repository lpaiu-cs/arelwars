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

## 2026-04-03 Late Night Update

The reopen priority shifted again.

What is now proven:

- the current Oracle candidate can keep the VM alive for minutes
- the strongest persisted shape is `PIIX3 + VBoxVGA + fastboot.vdi + Root.vhd + Data.vdi`
- `127.0.0.1:5555` stays open
- BlueStacks-side adb sees `emulator-5554`
- but the guest still never becomes `adb-online`

The bridge side is also clearer:

- raw [HD-Player.exe](/C:/vs/other/arelwars/$root/PF/HD-Player.exe) launch now exits cleanly, not by AV
- it fails at `bridgeOnInstanceStateUpdatedRpc ... opcode = 3011`
- `coreSvcErr` remains `0`

The biggest new negative result is this:

- adding only `VBoxInternal/PDM/Devices/bstdevices/Path`
- without any custom PCI assignment items

still crashes immediately inside [HD-Vdes-Service.dll](/C:/vs/other/arelwars/$root/PF/HD-Vdes-Service.dll).

That eliminates the idea that the remaining blocker is a specific `bstaudio` / `bstcamera` / `bstvmsg` device subset.

It points instead to a runtime ABI mismatch:

- BlueStacks control binaries are `6.1.36.156792`
- the usable Oracle frontend route is `7.2.6`
- the extracted official Oracle `6.1.36` frontend is not a drop-in replacement because hardening rejects it before launch

So the best reopen path is now:

1. find or reconstruct a BlueStacks-compatible headless frontend for the `6.1.36.156792` stack
2. only if that fails, keep the Oracle stripped profile as a limited black-screen / offline-adb probe path

## 2026-04-03 Midnight Update

The portable-client route has now crossed one more threshold.

What is newly proven:

- the `VBoxHeadless.exe - Application Error` popup seen during manual testing belongs to the Oracle `bstdevices` branch, not the valid portable-client launcher path
- the valid launcher path is:
  - [HD-MultiInstanceManager.exe](/C:/vs/other/arelwars/$root/PF/HD-MultiInstanceManager.exe)
  - visible `Start` button
  - child [HD-Player.exe](/C:/Program Files/BlueStacks_nxt/HD-Player.exe) with `--instance Nougat32`
- the stale `AddRedirect failed` branch was caused by a duplicate baked-in `adb` NAT forward inside [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk)
- removing that persistent forwarding entry clears the `configureMachine()` failure

Current strongest portable profile:

- `MIM Start` launches a live player process
- the player remains alive for `60+` seconds
- window tree shows `BlueStacks -> Optimizing before launch`
- named pipes include both:
  - `launcher_bridge`
  - `bst_plr_Nougat32_nxt`

But the route is still not reopened yet because:

- no `adb` device becomes visible
- no listener appears on `127.0.0.1:5555`
- no `VBoxHeadless` child is observed on that path
- the player stalls at `Optimizing before launch`

This changes the next-step priority.

The portable-client route is now ahead of the raw Oracle route for active debugging value.

Immediate next step:

- treat `MIM Start + no baked-in adb NAT rule` as the canonical reopen path
- debug the `Optimizing before launch` plateau instead of raw `HD-Player.exe` command-line launch
