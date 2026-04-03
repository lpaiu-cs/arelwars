# AW2 Phase 5 To Phase 10 Status

Audit date: 2026-04-03

## Result

- `Phase 5 = blocked`
- `Phase 6 = blocked`
- `Phase 7 = blocked`
- `Phase 8 = blocked`
- `Phase 9 = blocked`
- `Phase 10 = blocked`

## Why They Are Still Blocked

These phases still require a live original-runtime oracle.

That has not been approved yet.

The blocker is narrower than before:

- a local Oracle VBox candidate runtime now exists
- but it still does not expose a usable `adb-online` original process
- official `adb` reaches only `emulator-5554 offline`
- the original APK is therefore still not installable/observable inside a validated oracle environment
- the Oracle guest still stalls before OS detection, serial output, or real root/data disk activity
- restoring the BlueStacks custom device path under Oracle VBox fails earlier because hardening rejects [HD-Vdes-Service.dll](/C:/vs/other/arelwars/$root/PF/HD-Vdes-Service.dll)
- the portable BlueStacks client path is blocked separately by `Could not create the VirtualBox home directory ''` and a crashing `HD-Player.exe`

The current best evidence is in:

- [aw2-oracle-vbox-runtime-probe.md](/C:/vs/other/arelwars/docs/aw2-oracle-vbox-runtime-probe.md)
- [aw2-bluestacks-portable-launch-probe.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-portable-launch-probe.md)

## What Improved

The machine is no longer at a pure “no runtime exists” dead end.

A real local candidate now exists:

- `Oracle VBox + unpacked BlueStacks Nougat32`
- best profile: `oracle-ide-primaryslave-piix3-vga`
- stable `180s` window without `AHCI` panic or `ACPI` reset loop

But this is still below the threshold needed for Phases `5` through `10` because:

- `adb` is not online
- the original APK cannot yet be installed and traced there
- no oracle-backed differential or packaging evidence can be produced

## Practical Meaning

From the packaging-track perspective:

- do not claim x64 runtime bootstrap is approved
- do not claim runtime trace schema equivalence is in progress
- do not claim representative scenario equivalence
- do not claim save/load equivalence
- do not treat any signed APK as valid AW2 packaging evidence

## Reopen Condition

Phases `5` through `10` reopen only if the local Oracle VBox candidate crosses into a true oracle environment.

That requires at least:

- `adb-online` guest visibility
- successful install of the original [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk)
- stable capture of live original runtime evidence
