# AW2 BlueStacks Admin Bootstrap

Audit date: 2026-04-03

## Purpose

This is the first `privileged` recovery step for the AW2 packaging track.

The current local evidence says the portable BlueStacks payload is no longer blocked by missing COM registration alone.

It is now blocked by missing `machine-level install context`:

- `BstkVMMgr.exe` reaches `VirtualBoxWrap`
- object creation fails at `Could not create the VirtualBox home directory '' (VERR_NO_TMP_MEMORY)`
- `HD-Player.exe` still crashes before a guest comes online

The current follow-up blocker is narrower:

- `BstkVMMgr startvm Nougat32 --type headless` now reaches actual VM launch
- the guest then dies at `Unable to load R3 module ... HD-Vdes-Service.dll (bstdevices)`
- `VBox.log` shows VirtualBox hardening rejecting the module because it is not owned by `NT SERVICE\TrustedInstaller`

So the next useful action is not another non-admin probe.

It is an elevated bootstrap that recreates the minimum `BlueStacks 5` install footprint expected by the portable payload.

## Prepared Script

Use:

- [enable_aw2_bluestacks_admin_bootstrap.ps1](/C:/vs/other/arelwars/tools/arel_wars2/enable_aw2_bluestacks_admin_bootstrap.ps1)

Run it from an elevated PowerShell window:

```powershell
powershell -ExecutionPolicy Bypass -File C:\vs\other\arelwars\tools\arel_wars2\enable_aw2_bluestacks_admin_bootstrap.ps1
```

## What The Script Does

- ensures `C:\ProgramData\BlueStacks_nxt` points at the unpacked portable `PD` tree
- tries to ensure `C:\Program Files\BlueStacks_nxt` points at the unpacked portable `PF` tree
- writes `HKLM\SOFTWARE\BlueStacks` and `HKLM\SOFTWARE\BlueStacksServices`
- writes machine environment variables:
  - `HOME`
  - `VBOX_USER_HOME`
  - `VBOX_APP_HOME`
- registers and starts the kernel driver service:
  - `BlueStacksDrv_nxt`
  - binary: [BstkDrv_nxt.sys](/C:/vs/other/arelwars/$root/PF/BstkDrv_nxt.sys)
- re-registers the Oracle VBox COM service
- re-registers `BstkProxyStub.dll`
- sets [HD-Vdes-Service.dll](/C:/vs/other/arelwars/$root/PF/HD-Vdes-Service.dll) owner to `NT SERVICE\TrustedInstaller`
- prints a compact verification summary at the end

## Why Admin Is Required

The non-admin session can no longer move the state meaningfully.

The remaining blocked writes are all privileged:

- `HKLM\SOFTWARE\BlueStacks*`
- `C:\Program Files\BlueStacks_nxt`
- machine-level environment variables
- `SCM` kernel-driver registration for `BlueStacksDrv_nxt`
- file ownership change for `HD-Vdes-Service.dll` so Oracle/VirtualBox hardening accepts the custom `bstdevices` module

Those are exactly the pieces the current portable payload still lacks.

## After Running It

The next immediate checks are:

```powershell
& 'C:\vs\other\arelwars\$root\PF\BstkVMMgr.exe' --nologo list vms
& 'C:\vs\other\arelwars\$root\PF\HD-Player.exe' --instance Nougat32 --hidden
& 'C:\vs\other\arelwars\$root\PF\HD-Adb.exe' devices -l
```

If that yields a live guest or `127.0.0.1:5555`, `Phase 1` can reopen.
