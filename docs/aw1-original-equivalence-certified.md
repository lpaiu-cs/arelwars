# AW1 Original-Equivalence Certification

This note records the final certification gate for AW1.

## Final Artifact

- [AW1.original_equivalence_certification.json](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.original_equivalence_certification.json)
- exporter:
  - [export_aw1_original_equivalence_certification.py](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/export_aw1_original_equivalence_certification.py)

## Gate Rule

The project may claim `original-equivalence-certified` only when all of the following pass:

- native truth is frozen
- original reference bundle is ready
- regression render stems are certified
- all `111` stage flows are certified
- representative battle stages are certified
- representative render set is certified
- no heuristic mismatch remains without an explicit waiver

## Current Waiver Policy

Current explicit waivers cover only:

- `timelineKindConfidence`
- `overlayCadenceConfidence`

for the regression stems:

- `082`
- `084`
- `208`
- `209`
- `215`
- `226`
- `230`
- `240`

These remain visible in the final certification artifact. They are not hidden.

## Notes

- `PTC` emitter semantics remain a heuristic witness, but they do not appear as blocking side-by-side mismatches in the current certification scope.
- This final gate certifies against the current frozen original-reference bundle and native truth manifest, not against a future expanded capture set that may be added later.
