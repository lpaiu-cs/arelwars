# AW1 Release Packaging Gate

## Goal

Phase 10 makes packaging a downstream consequence of equivalence, not a parallel track.

The rule is simple:

- no `signed x86_64 APK` is accepted unless the Phase 9 gate says `go`

## Tool

- gate script: [guard_aw1_release_packaging.py](/C:/vs/other/arelwars/tools/arel_wars1/guard_aw1_release_packaging.py)
- latest report: [phase10-packaging-gate.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/phase10-packaging-gate.json)

Inputs:

- [phase9-gate.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/go_no_go_gate/phase9-gate.json)
- unsigned release APK from the Android Studio project
- optional keystore + signing credentials

## Behavior

If Phase 9 verdict is `no-go`:

- signing is blocked
- the script writes a report explaining why
- any already existing signed APK is treated as provisional only

If Phase 9 verdict is `go`:

- signing is allowed
- the script can sign the unsigned release APK through `apksigner`
- the output report records the signed artifact hash and verification output

## Current Status

Current Phase 9 verdict is `no-go`.

Therefore Phase 10 is blocked.

The current signed artifact in the Android Studio project is not accepted as final equivalence evidence:

- [app-release-signed.apk](/C:/Users/lpaiu/AndroidStudioProjects/arelwars1/app/build/outputs/apk/release/app-release-signed.apk)

It may still be useful as a provisional build artifact, but it is not a valid Phase 10 deliverable.

## Command

```powershell
python tools/arel_wars1/guard_aw1_release_packaging.py
```

The script will refuse packaging until the go/no-go gate turns green.
