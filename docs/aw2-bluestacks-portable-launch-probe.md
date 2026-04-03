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
