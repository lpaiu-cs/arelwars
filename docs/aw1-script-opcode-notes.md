# AW1 Script Opcode Notes

This note tracks variant-level findings for `ZT1` speech-prefix opcodes.
It is intentionally narrower than the overall restoration plan.

Primary data source:

- [script_event_report.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/script_event_report.json)
- [AW1.opcode_action_map.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.opcode_action_map.json)

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

### Tutorial / UI Guidance Cluster

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

- `cmd-0a(0x40)`
  - strongest current role: skill menu highlight
  - evidence:
    - tied to lines such as `Let's check your skills.`
    - appears inside the same `cmd-02 > cmd-06 > cmd-0a > cmd-02 > cmd-05` tutorial sequence in mirrored scripts

- `cmd-0c(0x40)`
  - strongest current role: item menu highlight
  - evidence:
    - tied to lines about items equipped before battle
    - appears inside the same tutorial focus sequence shape as the skill-menu case

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
