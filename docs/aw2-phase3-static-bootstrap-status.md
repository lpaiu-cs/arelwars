# AW2 Phase 3 Static Bootstrap Status

Audit date: 2026-04-03

## Result

- `Phase 3 = approved`

## Inputs

- APK:
  - [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk)
- bootstrap note:
  - [arel_wars2-bootstrap.md](/C:/vs/other/arelwars/docs/arel_wars2-bootstrap.md)

## Artifacts Produced

- inventory:
  - [apk_inventory.json](/C:/vs/other/arelwars/recovery/arel_wars2/apk_inventory.json)
- extraction catalog:
  - [catalog.json](/C:/vs/other/arelwars/recovery/arel_wars2/catalog.json)
- binary format report:
  - [binary_asset_report.json](/C:/vs/other/arelwars/recovery/arel_wars2/binary_asset_report.json)
- script event summary:
  - [script_event_report.json](/C:/vs/other/arelwars/recovery/arel_wars2/script_event_report.json)
- GXL table summary:
  - [gxl_table_report.json](/C:/vs/other/arelwars/recovery/arel_wars2/gxl_table_report.json)
- anchor probes:
  - [armor-000-anchor-probe.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_anchor_probes/armor-000-anchor-probe.png)
  - [effect-000-anchor-probe.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_anchor_probes/effect-000-anchor-probe.png)
  - [head-000-anchor-probe.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_anchor_probes/head-000-anchor-probe.png)
  - [weapon-000-anchor-probe.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_anchor_probes/weapon-000-anchor-probe.png)
  - [weapon2-000-anchor-probe.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_anchor_probes/weapon2-000-anchor-probe.png)
- compact marker scatter:
  - [effect-000-marker-scatter.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_marker_scatter/effect-000-marker-scatter.png)
  - [effect-001-marker-scatter.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_marker_scatter/effect-001-marker-scatter.png)
  - [effect-002-marker-scatter.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_marker_scatter/effect-002-marker-scatter.png)
  - [weapon2-000-marker-scatter.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_marker_scatter/weapon2-000-marker-scatter.png)
  - [weapon2-001-marker-scatter.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_marker_scatter/weapon2-001-marker-scatter.png)
  - [weapon2-002-marker-scatter.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_marker_scatter/weapon2-002-marker-scatter.png)
  - [weapon2-003-marker-scatter.png](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_marker_scatter/weapon2-003-marker-scatter.png)
- sequence candidates:
  - [effect-000-sequence-candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_sequence_candidates/effect-000-sequence-candidates.json)
  - [effect-001-sequence-candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_sequence_candidates/effect-001-sequence-candidates.json)
  - [effect-002-sequence-candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_sequence_candidates/effect-002-sequence-candidates.json)
  - [weapon2-000-sequence-candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_sequence_candidates/weapon2-000-sequence-candidates.json)
  - [weapon2-001-sequence-candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_sequence_candidates/weapon2-001-sequence-candidates.json)
  - [weapon2-002-sequence-candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_sequence_candidates/weapon2-002-sequence-candidates.json)
  - [weapon2-003-sequence-candidates.json](/C:/vs/other/arelwars/recovery/arel_wars2/pzf_sequence_candidates/weapon2-003-sequence-candidates.json)

## Validated Facts

From the generated reports:

- inventory:
  - `530` `.zt1`
  - `393` `.pzx`
  - `63` `.pzd`
  - `16` `.pzf`
  - `107` `.mpl`
  - `51` `.ptc`
  - `10` `.so`
- script extraction:
  - `312` recovered script files
  - `3242` recovered script events
- shared table family:
  - `42 / 42` decoded `GXL` tables satisfy a stable fixed-row payload layout
- binary format split:
  - `pzxRowReadyCount = 279`
  - `pzxChunkTableReadyCount = 24`
  - `pzfVariantHistogram = { anchor+marker: 8, anchor-only: 5, marker-only: 2, opaque: 1 }`

## Interpretation

The AW2 static truth layer is now frozen enough for future work.

What is solid:

- `ZT1` extraction works
- `PZD` row streams preview correctly
- `PZF` families split into stable variants
- `PTC` and `GXL` tables are machine-readable

What is still not solved:

- packaging feasibility
- original runtime oracle capture
- x64 equivalence

Those remain blocked by the earlier runtime-environment result, not by missing static format coverage.
