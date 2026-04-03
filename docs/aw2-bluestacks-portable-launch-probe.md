# AW2 BlueStacks Portable Launch Probe

Audit date: 2026-04-03

## Scope

This note captures the local `BlueStacks portable client` reopening attempt separate from the Oracle VBox path.

Probe tool:

- [probe_aw2_bluestacks_portable_launch.py](/C:/vs/other/arelwars/tools/arel_wars2/probe_aw2_bluestacks_portable_launch.py)

Evidence bundle:

- [portable-launch-probe.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/bluestacks_portable_probe/portable-launch-probe.json)

## Result

The portable client path is still blocked.

## Concrete Findings

- the original `REGDB_E_CLASSNOTREG` blocker is gone after manual COM repair
- `HKCR\VirtualBox.VirtualBox` now resolves to `BstkSVC.exe`
- `HKCR\VirtualBox.VirtualBoxClient` now resolves to `BstkC.dll`
- `BstkVMMgr.exe` now reaches `VirtualBoxWrap`
- but object creation still fails with:
  - `Could not create the VirtualBox home directory '' (VERR_NO_TMP_MEMORY)`
- direct `BstkSVC.exe --logfile ... --registervbox` reproduces the same failure in `BstkServer.log`
- `HD-Player.exe --instance Nougat32 --hidden` still exits with `3221225477`
- Windows Error Reporting records `APPCRASH`
  - app: `HD-Player.exe`
  - exception: `0xc0000005`
  - fault offset: `0x00000000004fa32c`
- no `adb` device comes online through either `HD-Adb.exe` or SDK `adb`
- `127.0.0.1:5555` stays closed

## Additional Manual Observation

The `missing COM registration` diagnosis is obsolete now.

Manual repair already moved the state forward:

- `VBoxSVC.exe /reregserver`
- `regsvr32 /s BstkProxyStub.dll`

After that:

- `BstkVMMgr` no longer fails immediately with `REGDB_E_CLASSNOTREG`
- the failure moved deeper into BlueStacks / VBox home resolution

Additional non-admin experiments were attempted:

- `HKCU\Software\BlueStacks*` skeleton keys
- `HKCU\Environment` values for `HOME`, `VBOX_USER_HOME`, `VBOX_APP_HOME`
- a per-user `HKCU\Software\Classes\CLSID\{b584...}\LocalServer32` wrapper
  - helper file: [run_bstksvc_with_env.cmd](/C:/vs/other/arelwars/tools/arel_wars2/run_bstksvc_with_env.cmd)

Those do not clear the blocker.

## Interpretation

The portable client route is still blocked, but the reason is now narrower and more useful.

This is no longer a generic “portable BlueStacks cannot launch” failure.

The current blocker is:

- the BlueStacks-flavored VirtualBox stack still lacks a valid `machine-level install context`
- `BstkSVC` cannot resolve a usable VirtualBox home directory
- `HD-Player` still crashes before guest bootstrap

That means the next meaningful step is an elevated bootstrap, not another non-admin launch retry.

Prepared next-step material:

- [aw2-bluestacks-admin-bootstrap.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-admin-bootstrap.md)
- [enable_aw2_bluestacks_admin_bootstrap.ps1](/C:/vs/other/arelwars/tools/arel_wars2/enable_aw2_bluestacks_admin_bootstrap.ps1)

## 2026-04-03 Late Update

The portable-client route is no longer a single failure bucket.

New concrete findings:

- the `VBoxHeadless.exe - Application Error` popup seen during testing belongs to the Oracle `bstdevices` path and [HD-Vdes-Service.dll](/C:/vs/other/arelwars/$root/PF/HD-Vdes-Service.dll), not the current portable-client blocker
- direct PowerShell launch of [HD-Player.exe](/C:/vs/other/arelwars/$root/PF/HD-Player.exe) is still not a valid path
  - it either exits with `3011`
  - or corrupts the heap when parent spoofing is attempted
- the actual launcher path is [HD-MultiInstanceManager.exe](/C:/vs/other/arelwars/$root/PF/HD-MultiInstanceManager.exe)
  - it creates the `launcher_bridge` pipe
  - it can launch [HD-Player.exe](/C:/Program Files/BlueStacks_nxt/HD-Player.exe) with `--instance Nougat32`

Another blocker was removed from the VM config side:

- [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk) contained a baked-in NAT forwarding rule for `adb`
- BlueStacks tried to add the same redirect again and failed with `AddRedirect failed`
- removing the baked-in `adb` forwarding entry clears that `configureMachine()` failure

Current best portable-launch shape:

- start [HD-MultiInstanceManager.exe](/C:/vs/other/arelwars/$root/PF/HD-MultiInstanceManager.exe)
- press the visible `Start` button for `Nougat32`
- [HD-Player.exe](/C:/Program Files/BlueStacks_nxt/HD-Player.exe) stays alive for at least `60+` seconds
- top-level UI shows:
  - `BlueStacks`
  - nested `Optimizing before launch`
- named pipes include:
  - `launcher_bridge`
  - `bst_plr_Nougat32_nxt`

What is still missing:

- no `adb` device becomes visible yet
- no `127.0.0.1:5555` listener appears on this path
- no `VBoxHeadless` child is observed yet
- the UI remains stalled at `Optimizing before launch`

This makes the blocker much tighter:

- the correct launcher path is now known
- the duplicate NAT redirect bug is now known and removable
- the remaining portable-client gap is the `Optimizing before launch` plateau after a valid player attach

Automation helper:

- [start_aw2_via_mim.py](/C:/vs/other/arelwars/tools/arel_wars2/start_aw2_via_mim.py)

## 2026-04-03 Deep Night Update

The portable path now has a stricter diagnosis than the earlier `Optimizing before launch` note.

New facts:

- the live VM definition used by the portable path is [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk)
- [BstkGlobal.xml](/C:/ProgramData/BlueStacks_nxt/Manager/BstkGlobal.xml) points to that repo path directly
- BlueStacks rewrites that file on launch and regenerates [Data.vdi](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Data.vdi)

The regenerated file is not the original BlueStacks template shape.

It is a stripped runtime shape:

- `PIIX3`
- `fastboot.vdi + Root.vhd + Data.vdi`
- no `bstdevices`
- no extra BlueStacks PCI device declarations

That shape is enough for:

- `HD-Player` survival
- `127.0.0.1:5555` listener
- `emulator-5554 offline`

But it is not enough for guest handoff:

- [BstkCore.log](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Logs/BstkCore.log) stalls at `Booting from ...`
- [BstkCore.log.1](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Logs/BstkCore.log.1) shows the previous session eventually powering off from early boot
- boot statistics show only `1024` bytes read from `fastboot.vdi`

So the current portable blocker is no longer just a UI plateau.

It is:

- `BlueStacks rewrites the VM into a reduced bootable-but-not-boot-complete shape`

That makes the next experiment concrete:

- regenerate [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk) from [Android.bstk.in](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk.in)
- use installed [HD-Vdes-Service.dll](/C:/Program Files/BlueStacks_nxt/HD-Vdes-Service.dll)
- relaunch through MIM

Prepared helper:

- [restore_aw2_bluestacks_template_config.ps1](/C:/vs/other/arelwars/tools/arel_wars2/restore_aw2_bluestacks_template_config.ps1)
