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
- official `adb` sees only `emulator-5554 offline`
- no successful install of the original APK
- no live original process to capture
- only host/VM guestproperties are visible
- `debugvm osdetect` still cannot identify a guest OS
- serial capture is empty
- boot-disk reads stop at `1024` bytes

The remaining Oracle VBox blocker is now sharper.

When the BlueStacks custom device path is restored, startup does not improve.

It fails earlier because Oracle VBox hardening rejects [HD-Vdes-Service.dll](/C:/vs/other/arelwars/$root/PF/HD-Vdes-Service.dll):

- `TrustedInstaller is not the owner`
- `Unable to load R3 module ... HD-Vdes-Service.dll (bstdevices)`
- `VERR_UNRESOLVED_ERROR`

So the Oracle candidate is currently boxed in between:

- `no bstdevices` -> stable black screen
- `with bstdevices` -> hardening failure before guest startup

The alternative portable-client path is also still blocked, but not for the old reason.

Current portable-client state:

- COM registration is repaired
- `BstkVMMgr.exe` now reaches `VirtualBoxWrap`
- creation fails at `Could not create the VirtualBox home directory ''`
- direct `BstkSVC.exe --registervbox` produces the same empty-home error in its own release log
- a patched `HD-Player.exe` launch no longer crashes with `0xc0000005`
- the patched player can stay resident without reaching `adb-online`
- the current strongest portable-path blocker is the missing kernel service `BlueStacksDrv_nxt`
- no client-side launch path yields a live guest

So Phase 1 and Phase 2 remain blocked, but by `candidate-runtime incompleteness`, not by total runtime absence.

## 2026-04-03 Midnight Update

Phase 1 and Phase 2 are still blocked, but the reopen stack is more mature than the earlier late-night status.

New positive result:

- the correct BlueStacks launcher path is now known and reproducible
- [HD-MultiInstanceManager.exe](/C:/vs/other/arelwars/$root/PF/HD-MultiInstanceManager.exe) can launch [HD-Player.exe](/C:/Program Files/BlueStacks_nxt/HD-Player.exe) for `Nougat32`
- that player survives for `60+` seconds and exposes a live `BlueStacks` window with nested `Optimizing before launch`
- a per-instance pipe `bst_plr_Nougat32_nxt` appears

Another concrete blocker was also removed:

- [Android.bstk](/C:/vs/other/arelwars/$root/PD/Engine/Nougat32/Android.bstk) contained a persistent `adb` NAT forwarding rule
- BlueStacks attempted to add the same redirect dynamically and failed at `AddRedirect failed`
- removing the baked-in rule clears that specific `configureMachine()` failure

What remains insufficient for Phase 1 / Phase 2 approval:

- no original APK process is running
- no `adb-online` device exists
- SDK `adb devices` is still empty on the valid launcher path
- no installable oracle session can yet be captured
- the player is stuck at `Optimizing before launch`

So the practical blocker is no longer “can the player launch at all.”

It is now:

- `can the valid MIM-driven player launch transition past Optimizing-before-launch into actual guest bring-up`

## 2026-04-03 Late Night Update

The Oracle candidate improved again, but not enough to approve Phase 1 or Phase 2.

Current strongest runtime facts:

- the persisted VM shape is now `PIIX3 + VBoxVGA + IDE(primary/master fastboot, primary/slave Root, secondary/master Data.vdi)`
- the VM can stay alive for `5+` minutes under [BstkServer.log](/C:/ProgramData/BlueStacks_nxt/Manager/BstkServer.log)
- the NAT forward on `127.0.0.1:5555` stays open
- BlueStacks-side adb can see `emulator-5554`

But the oracle threshold is still not crossed:

- `emulator-5554` remains `offline`
- the guest still never becomes `adb-online`
- Oracle `debugvm osdetect` still fails
- no live original APK install or capture session can start

The player/bridge failure is also more specific now.

Launching raw [HD-Player.exe](/C:/vs/other/arelwars/$root/PF/HD-Player.exe) no longer AVs, but it exits with:

- `bridgeOnInstanceStateUpdatedRpc: ipcSendToServer command failed, opcode = 3011`
- `coreSvcErr: 0`

That means the remaining gap is no longer “can the player process start at all.”

It is:

- `can the running VM and BlueStacks bridge agree on instance state well enough to attach the player and complete guest bring-up`

Another sub-experiment also closed out one false lead.

Restoring only:

- `VBoxInternal/PDM/Devices/bstdevices/Path = ...HD-Vdes-Service.dll`

while keeping all BlueStacks PCI assignment items removed still crashes immediately inside [HD-Vdes-Service.dll](/C:/vs/other/arelwars/$root/PF/HD-Vdes-Service.dll).

So the blocker is not specific to `bstaudio` or another single custom device.

It is broader:

- Oracle `7.2.6` cannot safely load the BlueStacks custom device runtime

The extracted official Oracle `6.1.36` frontend also does not reopen the route, because it fails its own hardening / build-certificate checks before the VM launches.

So Phase 1 and Phase 2 remain blocked by a now very narrow condition:

- no BlueStacks-compatible headless frontend is available on this machine

## What Was Completed Anyway

The AW2 oracle tooling remains ready:

- [capture_aw2_oracle_trace.py](/C:/vs/other/arelwars/tools/arel_wars2/capture_aw2_oracle_trace.py)
- [aw2-verification-protocol.md](/C:/vs/other/arelwars/docs/aw2-verification-protocol.md)

The local runtime reopening work also now has a concrete probe path:

- [probe_aw2_oracle_vbox_runtime.py](/C:/vs/other/arelwars/tools/arel_wars2/probe_aw2_oracle_vbox_runtime.py)
- [aw2-oracle-vbox-runtime-probe.md](/C:/vs/other/arelwars/docs/aw2-oracle-vbox-runtime-probe.md)
- [probe_aw2_bluestacks_portable_launch.py](/C:/vs/other/arelwars/tools/arel_wars2/probe_aw2_bluestacks_portable_launch.py)
- [aw2-bluestacks-portable-launch-probe.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-portable-launch-probe.md)
- [aw2-bluestacks-admin-bootstrap.md](/C:/vs/other/arelwars/docs/aw2-bluestacks-admin-bootstrap.md)
- [enable_aw2_bluestacks_admin_bootstrap.ps1](/C:/vs/other/arelwars/tools/arel_wars2/enable_aw2_bluestacks_admin_bootstrap.ps1)

## Immediate Consequence

Until the local Oracle VBox candidate yields a live original process, Phase 1 cannot approve a true oracle environment and Phase 2 cannot capture real original runtime evidence.

So the only approved work remains:

- Oracle VBox runtime bring-up
- elevated BlueStacks bootstrap
- AW2 static bootstrap and asset-truth freezing
- packaging-track gate hardening
