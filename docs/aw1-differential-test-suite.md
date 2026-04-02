# AW1 Differential Test Suite

## Goal

Phase 8 adds an automated differential runner that:

- drives the current x86_64 package on-device through fixed scenarios
- loads the latest `origin/main` replay corpora
- aligns comparisons to the same field family used by:
  - `AW1.golden_capture_suite.json`
  - `AW1.candidate_replay_suite.json`
  - `aw1-verification-protocol.md`

The suite is not a parser-truth source. It is a regression/oracle comparison harness.

## Tool

- runner: [run_aw1_differential_suite.py](/C:/vs/other/arelwars/tools/arel_wars1/run_aw1_differential_suite.py)

Default output:

- session: [phase8-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/differential_suite/phase8-session.json)
- scenario UI/XML/PNG artifacts under:
  [differential_suite](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/differential_suite)

## Reference Alignment

The runner loads `origin/main` reference corpora from:

- `recovery/arel_wars1/parsed_tables/AW1.golden_capture_suite.json`
- `recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json`

If those files are absent in the current worktree, it falls back to `git show origin/main:...`.

Current default reference trace:

- `000-run-1`

Aligned reference fields copied into the session:

- `familyId`
- `stageTitle`
- `storyboardIndex`
- `routeLabel`
- `preferredMapIndex`
- `scenePhaseSequence`
- `objectivePhaseSequence`
- `result`
- `unlockRevealLabel`

Protocol-side bridge fields used in scenario comparisons:

- `saveSlotIdentity`
- `resumeTargetScene`

## Automated Scenarios

The runner executes these scenarios in order:

1. `boot`
2. `menu_save_load`
3. `title_continue`
4. `battle_30s`
5. `retreat`
6. `orientation`
7. `home_resume`

Each scenario captures:

- UI XML
- screenshot hash
- inferred scene phase
- comparison block with expected vs actual values

## Current Run Result

Latest run summary from [phase8-session.json](/C:/vs/other/arelwars/recovery/arel_wars1/native_tmp/differential_suite/phase8-session.json):

- passed scenarios: `4 / 7`
- passing:
  - `boot`
  - `menu_save_load`
  - `title_continue`
  - `retreat`
- failing:
  - `battle_30s`
  - `orientation`
  - `home_resume`

Current detected divergences:

- `battle_30s`
  - reference expects scene still in `battle` at 30s
  - current port reaches `result` early
- `orientation`
  - rotating to landscape/portrait leaves the battle scene and lands on `title`
- `home_resume`
  - returning from home resumes into `result`, not active `battle`

## Approval Meaning

Phase 8 approval means:

- the differential suite exists
- the seven required scenarios are automated
- comparison output is structured
- the comparison fields are explicitly aligned to `golden/candidate` trace fields where available
- protocol-only fields such as save/resume are recorded separately instead of being invented as replay-corpus truth

It does not mean the current x86_64 runtime already passes equivalence. The current run proves the opposite for three scenarios, which is exactly the value of the suite.
