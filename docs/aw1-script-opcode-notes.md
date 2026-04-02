# AW1 Script Opcode Notes

This note tracks variant-level findings for `ZT1` speech-prefix opcodes.
It is intentionally narrower than the overall restoration plan.

Primary data source:

- [script_event_report.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/script_event_report.json)
- [AW1.opcode_action_map.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.opcode_action_map.json)
- [AW1.tutorial_opcode_chains.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.tutorial_opcode_chains.json)

## Important Constraint

Unknown opcodes are still parsed under a simple fallback rule of `opcode + 1 byte arg`.
That is good enough for clustering and correlation, but not enough to claim the binary grammar is final.

This means:

- variant-level hints are safer than opcode-level renames
- `cmd-0a(0x10)` and `cmd-0a(0x40)` should be treated as separate clues
- global mnemonic renames should wait until the underlying argument grammar is proven

## High-Confidence Variant Hints

`AW1.opcode_action_map.json` is now the structured export that the runtime reads.
It keeps two layers separate:

- mnemonic-wide action hints
  - example: `cmd-05 -> apply-dialogue-pose`
- variant-local action hints
  - example: `cmd-0a(0x40) -> focus-skill-menu`

This keeps the runtime-facing labels stable without pretending the binary grammar is fully proven.

Current phase-6 status:

- `AW1.opcode_action_map.json` now covers all `64` currently observed non-dialogue `cmd-XX` families with `unresolvedOpcodeCount = 0`.
- The export now carries stable `commandId`, `commandType`, and `target` fields per mnemonic and per variant.
- Low-frequency families no longer fall back to `unknown-runtime-action`; they are explicitly named as scene-layout, scene-bridge, presentation, or scene-transition presets.
- The prefix sanitizer in [formats.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py) now strips ASCII spill without dropping valid tutorial raw chains such as `000d0040` and `060d0740`.

`AW1.tutorial_opcode_chains.json` adds a third layer for cases where the current parser still under-reads selector bytes.
That proof layer uses exact raw-prefix needles mirrored across tutorial families.
The Phaser recovery runtime now consumes those needles per dialogue event, so the active HUD/tutorial target shown on screen is no longer only a family-level guess.
It now also drives a ghost HUD layer, which makes the currently focused tower bar, mana bar, card tray, menu, or quest panel visible in the stage preview itself.
The runtime also derives a lightweight gameplay-state summary from the same cue, including current panel, hero mode, objective, and enabled inputs.
That state summary now also owns persistent preview-side consequences for accepted inputs, including dispatch lane selection, queued-unit count, tower-upgrade tiers, skill/item cooldown gates, quest reward claim state, and pause/resume.
Those persistent inputs now feed a small two-lane battle simulation in the recovery runtime, so tutorial cues can be observed against changing lane momentum rather than static overlay state alone.
The lane simulation is now seeded from per-stage runtime fields, map-branch hints, render intensity, and featured hero archetypes, which gives each storyboard a different favored lane and wave tempo.
Those featured archetypes now also inject concrete lane rules: Dispatch boosts allied commit size, Tower Defense reduces incoming pressure, Recall swings frontline recovery, Armageddon creates burst unit loss, and mana-linked families refund part of skill pressure.
Keyboard actions in the recovery scene now pass through that summary layer, which lets the preview accept or reject panel, quest, dispatch, production, and hero toggles according to the current tutorial state.
Dialogue changes now also emit one-shot scripted battle beats from the same cue layer, so tutorial focus lines can automatically queue units, push a lane, deploy or recall the hero, trigger skill or item bursts, and advance tower upgrades without overwriting the manual input log.
The runtime now resolves every active prefix into a full `activeSceneCommands[]` list and interprets scene-layout, focus, presentation, emphasis, and transition commands directly instead of pattern-matching one `opcodeCue.action` string.
Those resolved commands are now compiled into explicit `sceneScriptSteps[]` per storyboard, which means dialogue advancement runs a step interpreter over objective, panel, wave, dispatch, mana, and scripted-action directives instead of a cue-only switch tree.

### Tutorial / UI Guidance Cluster

- `cmd-00(0x0d)`
  - strongest current role: battle-HUD focus prelude
  - evidence:
    - repeats across `0004`, `0404`, and `0804`
    - sits directly before the own-tower HP, enemy-tower HP, unit-card, mana-bar, sortie, and return chains
    - exported as a high-confidence variant hint plus raw-chain proofs

- `cmd-06(0x0d)`
  - strongest current role: tutorial-focus prelude or tutorial overlay mode
  - evidence:
    - repeatedly appears in `0004` and `0014` tutorial scripts
    - directly precedes the target-like variants below
    - example text cues mention arrows, icons, mana, skills, and equipped items

- `cmd-07(0x40)`
  - strongest current role: tower upgrade menu highlight
  - evidence:
    - clustered around lines about touching icons in the Tower
    - strongest English tokens: `icons`, `tower`, `stronger`
    - example scripts:
      - `assets/script_eng/0014.zt1`
      - `assets/script_eng/0414.zt1`

- `cmd-08(0x40)`
  - strongest current role: mana upgrade highlight
  - evidence:
    - clustered around `Upgrade Mana increases your Mana Regeneration Speed and Max Mana`
    - mirrored across `0014`, `0414`, `0814`

- `cmd-09(0x40)`
  - strongest current role: population upgrade highlight
  - evidence:
    - clustered around max-population warnings and production-capacity lines
    - mirrored across `0014`, `0414`, `0814`

- `cmd-0a(0x40)`
  - strongest current role: skill menu highlight
  - evidence:
    - tied to lines such as `Let's check your skills.`
    - appears inside the same `cmd-02 > cmd-06 > cmd-0a > cmd-02 > cmd-05` tutorial sequence in mirrored scripts

- `cmd-0b(0x40)`
  - strongest current role: skill window / skill slot highlight
  - evidence:
    - tied to `Touch a skill in the window to use`
    - mirrored across `0014`, `0414`, `0814`

- `cmd-0c(0x40)`
  - strongest current role: item menu highlight
  - evidence:
    - tied to lines about items equipped before battle
    - appears inside the same tutorial focus sequence shape as the skill-menu case

- `cmd-0d(0x40)`
  - strongest current role: system menu highlight
  - evidence:
    - tied to lines about pause, resume, and settings
    - mirrored across `0014`, `0414`, `0814`

- `cmd-0e(0x40)`
  - strongest current role: quest panel highlight
  - evidence:
    - tied to lines about upper-right quest rewards
    - mirrored across `0014`, `0414`, `0814`

## Exact Tutorial Chain Proofs

The current prefix parser still flattens some selector bytes into existing command families.
For that reason, `AW1.tutorial_opcode_chains.json` tracks raw-prefix needles that stay stable across mirrored tutorial scripts.

- battle HUD family
  - `000d0040` -> own tower HP / loss-condition highlight
  - `000d0140` -> enemy tower HP / victory-condition highlight
  - `060d0240` -> dispatch arrows
  - `000d0340` -> unit production card
  - `000d0440` -> mana bar
  - `000d0540` -> hero sortie button
  - `000d0640` -> return-to-tower button

- menu training family
  - `060d0740` -> tower menu
  - `060d0840` -> mana upgrade
  - `060d0940` -> population upgrade
  - `060d0a40` -> skill menu
  - `060d0b40` -> skill window
  - `060d0c40` -> item menu
  - `060d0d40` -> system menu
  - `060d0e40` -> quest panel

### Presentation / Emphasis Cluster

- `cmd-0a(0x10)`
  - strongest current role: emphasis or impact cue
  - evidence:
    - often paired with `cmd-0b(0x10)`
    - appears around pain, surprise, threat, or forceful lines
    - example scripts:
      - `assets/script_eng/0053.zt1`
      - `assets/script_eng/0092.zt1`

- `cmd-0b(0x10)`
  - strongest current role: paired emphasis / shock cue
  - evidence:
    - often precedes or follows `cmd-0a(0x10)`
    - appears around `What?!`, damage cries, and abrupt reactions

- `cmd-05(0x03)`
  - strongest current role: dialogue presentation state applied after portrait setup
  - evidence:
    - commonly follows `set-left-portrait`
    - commonly followed by `cmd-08(0x00)`
    - appears in introductory dialogue and tutorial narration without obvious gameplay-state meaning

- `cmd-08(0x00)`
  - strongest current role: presentation terminator or secondary pose toggle
  - evidence:
    - overwhelmingly follows `cmd-05`
    - overwhelmingly ends the prefix sequence

## Medium-Confidence Variant Hints

- `cmd-02(0x05)`
  - strongest current role: tutorial-context selector or highlighted subject anchor
  - evidence:
    - heavily concentrated in tutorial scripts
    - strongest English tokens: `mana`, `tower`, `skills`, `produce`
  - caution:
    - still too broad to rename safely

- `cmd-10(0x00)`
  - strongest current role: scene-entry preset
  - evidence:
    - common at the first spoken line of a scene
    - often followed by portrait setup and presentation commands
  - caution:
    - could still be camera, layout, or battle-state bootstrap rather than a pure scene marker

## Next Targets

1. Compare tutorial script prefixes against actual on-screen reference footage.
2. Check whether the `0x40` family is always a UI-target mode and whether the preceding opcode selects the target class.
3. Determine whether `cmd-05/cmd-08` affect portrait pose, speech bubble mode, or camera focus.
4. Test whether `cmd-0a/cmd-0b` correlate with shake, flash, damage, or expression changes in recovered stage playback.
