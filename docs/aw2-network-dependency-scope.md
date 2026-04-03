# AW2 Network Dependency Scope

Audit date: 2026-04-04

## Decision

Treat the original AW2 network dependency as an external blocker, not as the core reverse-engineering target.

For current development:

- `DRMLicensing -> ArelWars2Launcher` is in scope
- the first post-DRM launcher state is in scope
- the remote server dependency behind the original launcher `Network Error` dialog is out of scope for now

## Why

The live original runtime now reaches:

- `com.gamevil.ArelWars2.global/.DRMLicensing`
- `com.gamevil.ArelWars2.global/.ArelWars2Launcher`

The first post-DRM observable scene is a launcher-owned modal:

- title: `Network Error`
- message: `Cannot run the program. Please try again after checking your network settings.`

That means the current hard stop is no longer missing runtime access. It is a dead or unreachable server-side dependency outside the packaged asset/runtime graph.

Static inspection also confirms that this dependency is real and not just a local UI stub. The original APK contains both the launcher error strings and live service endpoints in `classes.dex`, including:

- `advance-service.gamevil.com/gv_connect?put=`
- `live.gamevil.com/login/`
- `liveapi.gamevil.com/friends_list/`

## Evidence

Automated capture:

- [capture_aw2_original_first_scene.py](/C:/vs/other/arelwars/tools/arel_wars2/capture_aw2_original_first_scene.py)
- [first-scene-v1/session.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/session.json)

Key artifacts:

- [05_post_start.xml](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/05_post_start.xml)
- [05_post_start.png](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/05_post_start.png)
- [logcat.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/oracle/first-scene-v1/logcat.txt)

## Practical Consequence

Do not block bootstrap/state-alignment work on live server recovery.

Immediate allowed work:

- bootstrap trace semantic population
- stage bootstrap binding
- asset/runtime alignment against static tables and original pre-network scenes
- offline differential work up to the launcher boundary

Deferred work:

- reproducing original online handshake
- restoring dead service endpoints
- claiming full original-equivalence past the network gate
