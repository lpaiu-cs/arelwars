# AW2 Phase 1 / Phase 2 Oracle Status

Audit date: 2026-04-03

## Result

- `Phase 1 = still blocked`
- `Phase 2 = still blocked`

## Updated Blocker Shape

The reason is no longer simply “there is no candidate Android runtime on this machine.”

There is now a local candidate:

- `Oracle VBox`
- `unpacked BlueStacks Nougat32`
- best current profile: `oracle-ide-primaryslave-piix3-vga`

That candidate reaches a stable no-reset boot window, but it still fails the actual oracle threshold:

- no usable `adb-online` device
- no successful install of the original APK
- no live original process to capture
- only host/VM guestproperties are visible
- `debugvm osdetect` still cannot identify a guest OS
- serial capture is empty
- boot-disk reads stop at `1024` bytes

The alternative portable-client path is also blocked:

- `BstkVMMgr.exe` still fails with `REGDB_E_CLASSNOTREG`
- `HD-Player.exe` exits without opening `127.0.0.1:5555`
- no client-side launch path yields a live guest

So Phase 1 and Phase 2 remain blocked, but by `candidate-runtime incompleteness`, not by total runtime absence.

## What Was Completed Anyway

The AW2 oracle tooling remains ready:

- [capture_aw2_oracle_trace.py](/C:/vs/other/arelwars/tools/arel_wars2/capture_aw2_oracle_trace.py)
- [aw2-verification-protocol.md](/C:/vs/other/arelwars/docs/aw2-verification-protocol.md)

The local runtime reopening work also now has a concrete probe path:

- [probe_aw2_oracle_vbox_runtime.py](/C:/vs/other/arelwars/tools/arel_wars2/probe_aw2_oracle_vbox_runtime.py)
- [aw2-oracle-vbox-runtime-probe.md](/C:/vs/other/arelwars/docs/aw2-oracle-vbox-runtime-probe.md)
- [probe_aw2_bluestacks_portable_launch.py](/C:/vs/other/arelwars/tools/arel_wars2/probe_aw2_bluestacks_portable_launch.py)
- [aw2-bluestacks-portable-launch-probe.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-portable-launch-probe.md)

## Immediate Consequence

Until the local Oracle VBox candidate yields a live original process, Phase 1 cannot approve a true oracle environment and Phase 2 cannot capture real original runtime evidence.

So the only approved work remains:

- Oracle VBox runtime bring-up
- AW2 static bootstrap and asset-truth freezing
- packaging-track gate hardening
