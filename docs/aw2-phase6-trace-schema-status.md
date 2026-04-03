# AW2 Phase 6 Trace Schema Status

Audit date: 2026-04-03

This note records the first bootstrap-side trace schema emission for the AW2 packaging track.

## What Was Added

The bootstrap project now writes a machine-readable trace snapshot to:

- `/sdcard/Android/data/com.gamevil.ArelWars2.global.bootstrap/files/aw2_bootstrap_trace.json`

The writer lives in:

- [Aw2TraceWriter.java](/C:/vs/other/arelwars/ports/arelwars2-android/app/src/main/java/com/gamevil/ArelWars2/global/Aw2TraceWriter.java)

Current integration points:

- [DRMLicensing.java](/C:/vs/other/arelwars/ports/arelwars2-android/app/src/main/java/com/gamevil/ArelWars2/global/DRMLicensing.java)
- [ArelWars2Launcher.java](/C:/vs/other/arelwars/ports/arelwars2-android/app/src/main/java/com/gamevil/ArelWars2/global/ArelWars2Launcher.java)
- [NexusGLActivity.java](/C:/vs/other/arelwars/ports/arelwars2-android/app/src/main/java/com/gamevil/nexus2/NexusGLActivity.java)

## Verification

The trace file was pulled successfully to:

- [aw2-bootstrap-trace.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-trace.json)

The bootstrap run also produced:

- [aw2-bootstrap-trace-logcat.txt](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-trace-logcat.txt)

The current trace already exposes the protocol-compatible key set:

- `specVersion`
- `packageName`
- `sceneLabel`
- `publicKey`
- `focusedComponent`
- `verificationTrace.traceId`
- `verificationTrace.familyId`
- `verificationTrace.aiIndex`
- `verificationTrace.stageTitle`
- `verificationTrace.storyboardIndex`
- `verificationTrace.routeLabel`
- `verificationTrace.preferredMapIndex`
- `verificationTrace.scriptEventCountExpected`
- `verificationTrace.dialogueEventsSeen`
- `verificationTrace.dialogueAnchorsSeen`
- `verificationTrace.sceneCommandIdsSeen`
- `verificationTrace.sceneDirectiveKindsSeen`
- `verificationTrace.scenePhaseSequence`
- `verificationTrace.objectivePhaseSequence`
- `verificationTrace.resultType`
- `verificationTrace.unlockTarget`
- `verificationTrace.saveSlotIdentity`
- `verificationTrace.resumeTargetScene`
- `verificationTrace.resumeTargetStageBinding`

## Current Status

This is enough to say:

- the bootstrap runtime now emits a stable trace file
- the emitted trace uses the same verification field names as the oracle protocol
- the trace can be pulled without root through external app storage

But Phase 6 is not fully closed yet.

The unresolved fields were previously:

- `familyId`
- `aiIndex`
- `preferredMapIndex`
- the rest of the actual stage-bootstrap semantics

That changed for the offline launcher bootstrap path.

The launcher trace now pulls the repo-generated stage candidate report:

- [aw2_bootstrap_stage_candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/aw2_bootstrap_stage_candidates.json)

Current emitted launcher fields now include:

- `verificationTrace.familyId = 0`
- `verificationTrace.aiIndex = 0`
- `verificationTrace.routeLabel = primary`
- `verificationTrace.preferredMapIndex = 226`
- `verificationTrace.resumeTargetScene = stage:000`
- `verificationTrace.resumeTargetStageBinding = 000`

Evidence:

- [aw2-bootstrap-trace.json](/C:/vs/other/arelwars/recovery/arel_wars2/native_tmp/aw2-bootstrap-trace.json)
- [Aw2BootstrapStageResolver.java](/C:/vs/other/arelwars/ports/arelwars2-android/app/src/main/java/com/gamevil/ArelWars2/global/Aw2BootstrapStageResolver.java)

So the accurate status is:

- `Phase 6 schema scaffold implemented`
- `Phase 6 field names fixed`
- `Phase 6 initial offline bootstrap semantics populated`
- `Phase 6 original-runtime values beyond the launcher network gate still pending`
