# AW2 Network Dependency Scope

Audit date: 2026-04-04

## Decision

Treat the original AW2 network dependency as an external blocker, not as the core reverse-engineering target.

For current development:

- `DRMLicensing -> ArelWars2Launcher` is in scope
- the first post-DRM launcher state is in scope
- dead online handshake, GV news/update gating, terms gating, and launcher startup interstitial are bypassed in the offline-hook build
- remote server recovery itself is still out of scope for now

## Why

The unmodified original runtime reaches:

- `com.gamevil.ArelWars2.global/.DRMLicensing`
- `com.gamevil.ArelWars2.global/.ArelWars2Launcher`

The first post-DRM observable scene is a launcher-owned modal:

- title: `Network Error`
- message: `Cannot run the program. Please try again after checking your network settings.`

That means the current hard stop is no longer missing runtime access. It is a dead or unreachable server-side dependency outside the packaged asset/runtime graph.

The current offline-hook build now bypasses these startup blockers and reaches the original launcher activity directly:

- `com.gamevil.ArelWars2.global/.ArelWars2Launcher`

The offline hook currently suppresses:

- GV live/login bootstrap calls
- GV news/update bootstrap calls
- Tapjoy/gift session bootstrap calls
- DRM `accept_terms` gating
- `Natives.updateDialogue()` abnormal-file startup popup

The current scope line is narrower than “patch every network callback to no-op”. In particular, worldmap-local handlers such as `CPdStateWorldmap::OnNetError` and `CPdStateWorldmap::OnNetReceive` are no longer treated as safe blanket no-op targets, because static analysis indicates they likely participate in post-popup/post-fade state cleanup for worldmap-local flags (`0x379c`, `0x362c`, `0x36f8`) as well as network UI.

Static inspection also confirms that this dependency is real and not just a local UI stub. The original APK contains both the launcher error strings and live service endpoints in `classes.dex`, including:

- `advance-service.gamevil.com/gv_connect?put=`
- `live.gamevil.com/login/`
- `liveapi.gamevil.com/friends_list/`

## Evidence

Automated capture:

- [capture_aw2_original_first_scene.py](/C:/vs/other/arelwars/tools/arel_wars2/capture_aw2_original_first_scene.py)
- [first-scene-v1/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/session.json)
- [offline-hook-first-scene-v7/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/offline-hook-first-scene-v7/session.json)

Key artifacts:

- [05_post_start.xml](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/05_post_start.xml)
- [05_post_start.png](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/05_post_start.png)
- [logcat.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/logcat.txt)
- [aw2_offline_hook_report.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2_offline_hook_report.json)
- [build_aw2_offline_hook_apk.py](/C:/vs/other/arelwars/tools/arel_wars2/build_aw2_offline_hook_apk.py)
- [offline-hook-first-scene-v7/logcat.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/offline-hook-first-scene-v7/logcat.txt)

## Practical Consequence

Do not block bootstrap/state-alignment work on live server recovery.

Immediate allowed work:

- bootstrap trace semantic population
- stage bootstrap binding
- asset/runtime alignment against static tables and original pre-network scenes
- offline differential work at and beyond the launcher boundary, using the offline-hook build as the current executable oracle substitute
- worldmap state cleanup recovery without reintroducing dead-service dependence

Deferred work:

- reproducing original online handshake
- restoring dead service endpoints
- claiming full original-equivalence past the network gate
