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

- `BstkVMMgr.exe list vms` fails with `REGDB_E_CLASSNOTREG`
- that means the BlueStacks-flavored VirtualBox COM server is not registered in this session
- `HD-Player.exe --instance Nougat32 --hidden` exits by the end of the probe window
- latest probe exit code is `3221225477`
- no `adb` device comes online through either `HD-Adb.exe` or SDK `adb`
- `127.0.0.1:5555` stays closed
- no real guest runtime process appears; only baseline `VBoxSDS.exe` is present

## Additional Manual Observation

`HD-ComRegistrar.exe` is not a practical non-interactive fix in this environment.

Manual probe showed:

- it triggers `consent.exe`
- that implies an interactive UAC path
- the current automation session cannot complete that registration step

## Interpretation

The portable client route is not a hidden shortcut around the Oracle VBox blocker.

It is blocked independently:

- `BstkVMMgr` cannot initialize its COM backend
- `HD-Player` does not bootstrap a live guest by itself
- `HD-ComRegistrar` needs interactive elevation

So this route does not reopen `Phase 1` or `Phase 2` yet.
