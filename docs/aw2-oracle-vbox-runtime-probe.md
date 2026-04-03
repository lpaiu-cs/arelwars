# AW2 Oracle VBox Runtime Probe

Audit date: 2026-04-03

## Scope

This note records the local runtime-reopening work for AW2 after the official Android Emulator path failed.

The target is still the original APK:

- [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk)

## Local Runtime Shape

The current candidate runtime is:

- Oracle VirtualBox `7.2.6`
- a locally unpacked `BlueStacks Nougat32` payload
- VM config file:
  - `C:\vs\other\arelwars\$root\PD\Engine\Nougat32\Android.bstk`

Supporting local artifacts:

- `Data.vhdx -> Data.vdi` conversion completed
- BlueStacks-specific `bstdevices` hardening path removed from the VM config
- Oracle-compatible NAT port forward added for `127.0.0.1:5555 -> guest 5555`

Probe tool:

- [probe_aw2_oracle_vbox_runtime.py](/C:/vs/other/arelwars/tools/arel_wars2/probe_aw2_oracle_vbox_runtime.py)

## Variant Results

### `oracle-slim-vga`

Observed result:

- guest starts
- screen reaches Linux kernel text
- fails with `AHCI/libata` panic
- not usable for oracle work

Evidence:

- [oracle-slim-vga.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-slim-vga.json)
- ![oracle-slim-vga](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-slim-vga.png)

### `oracle-ide-vga`

Observed result:

- avoids the `AHCI` panic
- falls into an `ACPI reset` loop
- still not usable

Evidence:

- [oracle-ide-vga.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-ide-vga.json)
- ![oracle-ide-vga](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-ide-vga.png)

### `oracle-ide-primaryslave-piix3-vga`

Observed result:

- `Chipset = piix3`
- `fastboot.vdi` on `IDE 0:0`
- `Root.vhd` on `IDE 0:1`
- `Data.vdi` on `IDE 1:0`
- no `AHCI` panic in the probe log tail
- no `ACPI reset` loop in the probe log tail
- remains up for at least `180` seconds during the probe window
- screen remains black
- `adb` is still not online
- `guestproperty enumerate` exposes only `/VirtualBox/Host*` and `/VirtualBox/VMInfo/*`
- `debugvm osdetect` still fails with `VINF_DBGF_OS_NOT_DETCTED`
- UART raw-file sink stays at `0` bytes
- live storage stats show only `1024` bytes read from `fastboot.vdi`
- no reads are observed from `Root.vhd` or `Data.vdi`

This is the strongest current profile.

Evidence:

- [oracle-ide-primaryslave-piix3-vga.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-ide-primaryslave-piix3-vga.json)
- ![oracle-ide-primaryslave-piix3-vga](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-ide-primaryslave-piix3-vga.png)

### `oracle-ide-primaryslave-piix3-vga + bstdevices`

Observed result:

- the missing BlueStacks custom device path can be restored
- Oracle VBox then fails before guest startup
- `HD-Vdes-Service.dll` is rejected by VirtualBox hardening
- the exact blocker is `TrustedInstaller is not the owner`
- startup ends with `VERR_UNRESOLVED_ERROR`

Evidence:

- [oracle-ide-primaryslave-piix3-vga-bstdevices-hardening.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-ide-primaryslave-piix3-vga-bstdevices-hardening.json)
- [oracle-ide-primaryslave-piix3-vga-bstdevices-hardening.log](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle_vbox_probe/oracle-ide-primaryslave-piix3-vga-bstdevices-hardening.log)

## Interpretation

The machine is no longer blocked by total runtime absence.

Instead, it is blocked at a narrower fork:

- without `bstdevices`, the Oracle VBox guest reaches a stable black-screen candidate shape
- with `bstdevices`, Oracle VBox fails earlier because hardening rejects [HD-Vdes-Service.dll](/C:/vs/other/arelwars/$root/PF/HD-Vdes-Service.dll)
- the only observable boot progress in the stable profile is still `BIOS: Booting from Hard Disk...`
- the stable profile still never crosses into guest-detectable OS state or `adb-online`

That means:

- `Route A` is still not approved
- `Phase 1` and `Phase 2` remain blocked
- `Phase 5` through `Phase 10` remain blocked

## Practical Next Step

The next useful runtime experiment is no longer “find any ARM runtime at all.”

It is:

- push the `oracle-ide-primaryslave-piix3-vga` profile from `stable black-screen boot` to `adb-online`
- explain why `fastboot.vdi` is only read for `1024` bytes before the boot chain stalls
- determine whether the remaining gap can be solved without `bstdevices`
- or else move from stock Oracle VBox to a runtime that can legally load the BlueStacks custom device DLLs

Until that happens, packaging claims must remain blocked.

## 2026-04-03 Late Update

Two additional reopen steps now work locally:

- `BstkVMMgr.exe list vms` succeeds once `HKLM/HKCU` bootstrap keys are corrected and `C:\ProgramData\BlueStacks_nxt\Manager\BstkGlobal.xml` is seeded.
- `BstkVMMgr.exe startvm Nougat32 --type headless` no longer fails with `VERR_FILE_NOT_FOUND` after supplying a local [VBoxHeadless.exe](/C:/vs/other/arelwars/$root/PF/VBoxHeadless.exe) proxy and copying `BstkGlobal.xml -> VirtualBox.xml` in `C:\ProgramData\BlueStacks_nxt\Manager`.

That pushes the Oracle route one step farther than before:

- the `VBoxHeadless` frontend is now actually launched
- [VBoxManage.exe](/C:/Program Files/Oracle/VirtualBox/VBoxManage.exe) can see `Nougat32` as `running`
- `screenshotpng` succeeds
- but the screenshot is still a full black frame:
  - ![aw2-vm-screen](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-vm-screen.png)

The branch now has two clearly separated VM-config outcomes:

1. `stripped Oracle-safe config`
- reaches `BIOS: Booting from Hard Disk...`
- enters `VBoxHeadless: starting event loop`
- remains `running`
- still never reaches `adb-online`
- still produces an all-black frame

2. `candidate config restored from prev-with-bstitems`
- restores `ICH9 + SATA + Data.vhdx + BlueStacks-specific ExtraData`
- fails deterministically with:
  - `Configuration error: device 'bstaudio' not found!`
  - `VERR_PDM_DEVICE_NOT_FOUND`

That means the current reopen blocker is no longer “frontend missing.”

It is now:

- `Oracle VBox route without BlueStacks devices` -> stable black-screen hang
- `Oracle VBox route with BlueStacks items` -> missing custom PDM device implementations

The concrete evidence is:

- [VBoxHeadless-proxy.log](/C:/ProgramData/BlueStacks_nxt/Logs/VBoxHeadless-proxy.log)
- [VBoxSVC.log](/C:/ProgramData/BlueStacks_nxt/Manager/VBoxSVC.log)
- [VBox.log](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Logs/VBox.log)

The next useful experiment is therefore narrower:

- obtain or reconstruct a `6.1.36`-compatible `VBoxHeadless` path that can load the BlueStacks custom device stack
- or make the portable BlueStacks client path launch the same device stack without Oracle hardening
