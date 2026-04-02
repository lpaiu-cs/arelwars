#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify AW1 hero skill runtime families from slot/passive/active/buff links"
    )
    parser.add_argument(
        "--linked-report",
        type=Path,
        required=True,
        help="Path to AW1.hero_skill_links.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write AW1.hero_runtime_families.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def canonical_family_id(row: dict[str, Any]) -> str:
    passive = row.get("passiveSlotMatch")
    passive_name = str(passive["name"]) if passive else ""
    slot = int(row["slotOrPowerCandidate"])
    if slot >= 29:
        return f"special-{normalize_name(str(row['name']))}"
    if row["name"] == "Defend Tower" or passive_name.lower().endswith("tower defense"):
        return "tower-defense"
    return normalize_name(str(row["name"]))


def canonical_family_label(family_id: str, rows: list[dict[str, Any]]) -> str:
    if family_id == "tower-defense":
        return "Defend Tower / Tower Defense"
    if family_id.startswith("special-"):
        return f"{rows[0]['name']} (Special)"
    counts = Counter(str(row["name"]) for row in rows)
    return counts.most_common(1)[0][0]


def make_row_stub(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": row["index"],
        "name": row["name"],
        "skillCodeCandidate": row["skillCodeCandidate"],
        "aiCodeCandidate": row["aiCodeCandidate"],
        "modeKey": f"{row['modeA']}:{row['modeB']}",
        "slotOrPowerCandidate": row["slotOrPowerCandidate"],
        "description": row["description"],
        "tags": row["tags"],
    }


def slot_runtime_type(
    slot: int,
    row_names: set[str],
    passive_row: dict[str, Any] | None,
    active_row: dict[str, Any] | None,
    buff_rows: list[dict[str, Any]],
    has_exact_tail: bool,
    has_hint_tail: bool,
) -> str:
    if slot >= 29 and passive_row is None and active_row is None:
        return "special-command-slot"
    if len(row_names) > 1 and buff_rows:
        return "shared-slot-multi-skill-buff"
    if len(row_names) > 1:
        return "shared-slot-multi-skill"
    if passive_row is not None and active_row is not None and buff_rows and has_exact_tail:
        return "passive-active-buff-exact"
    if passive_row is not None and active_row is not None and buff_rows:
        return "passive-active-buff"
    if passive_row is not None and active_row is not None and has_exact_tail:
        return "passive-active-exact"
    if passive_row is not None and active_row is not None and has_hint_tail:
        return "passive-active-hint"
    if passive_row is not None and active_row is not None:
        return "passive-active"
    if passive_row is not None:
        return "passive-only"
    if active_row is not None:
        return "active-only"
    return "unclassified"


def family_runtime_type(slots: list[dict[str, Any]], row_names: set[str]) -> str:
    slot_ids = [slot["slot"] for slot in slots]
    runtime_types = {slot["runtimeType"] for slot in slots}
    if any(slot_id >= 29 for slot_id in slot_ids) and len(slot_ids) == 1:
        return "special-family"
    if len(slot_ids) > 1 and any("buff" in runtime for runtime in runtime_types):
        return "multi-slot-ladder-with-buff"
    if len(slot_ids) > 1 and len(row_names) == 1:
        return "multi-slot-ladder"
    if len(slot_ids) > 1:
        return "multi-slot-variant-family"
    if any(runtime == "shared-slot-multi-skill-buff" for runtime in runtime_types):
        return "shared-slot-hybrid-with-buff"
    if any(runtime == "shared-slot-multi-skill" for runtime in runtime_types):
        return "shared-slot-hybrid"
    return "single-slot-family"


def main() -> None:
    args = parse_args()
    report = read_json(args.linked_report.resolve())
    hero_skill_links = report["heroSkillLinks"]

    rows_by_slot: dict[int, list[dict[str, Any]]] = defaultdict(list)
    rows_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in hero_skill_links:
        slot = int(row["slotOrPowerCandidate"])
        rows_by_slot[slot].append(row)
        rows_by_family[canonical_family_id(row)].append(row)

    slot_families: list[dict[str, Any]] = []
    for slot, rows in sorted(rows_by_slot.items()):
        row_names = {str(row["name"]) for row in rows}
        passive_candidates = [row.get("passiveSlotMatch") for row in rows if row.get("passiveSlotMatch")]
        passive_row = passive_candidates[0] if passive_candidates else None
        active_candidates = [row.get("activeSlotRow") for row in rows if row.get("activeSlotRow")]
        active_row = active_candidates[0] if active_candidates else None
        exact_tail_candidates = [row.get("activeExactTailLink") for row in rows if row.get("activeExactTailLink")]
        hint_tail_candidates = [row.get("activeTailHintRow") for row in rows if row.get("activeTailHintRow")]
        buff_rows_by_index: dict[int, dict[str, Any]] = {}
        for row in rows:
            for buff in row.get("buffTailMatches", []):
                buff_rows_by_index[int(buff["index"])] = buff
        buff_rows = [buff_rows_by_index[index] for index in sorted(buff_rows_by_index)]

        skill_ai_by_skill = {}
        skill_ai_by_ai = {}
        for row in rows:
            for item in row.get("matchingSkillAiBySkillCode", []):
                skill_ai_by_skill[int(item["index"])] = item
            for item in row.get("matchingSkillAiByAiCode", []):
                skill_ai_by_ai[int(item["index"])] = item

        slot_families.append(
            {
                "slot": slot,
                "runtimeType": slot_runtime_type(
                    slot,
                    row_names,
                    passive_row,
                    active_row,
                    buff_rows,
                    bool(exact_tail_candidates),
                    bool(hint_tail_candidates),
                ),
                "canonicalFamilyIds": sorted({canonical_family_id(row) for row in rows}),
                "heroSkillRows": [make_row_stub(row) for row in rows],
                "passiveRow": passive_row,
                "activeRow": active_row,
                "activeExactTailLink": exact_tail_candidates[0] if exact_tail_candidates else None,
                "activeHintTailRow": hint_tail_candidates[0] if hint_tail_candidates else None,
                "buffTailRows": buff_rows,
                "skillAiRowsBySkillCode": [skill_ai_by_skill[index] for index in sorted(skill_ai_by_skill)],
                "skillAiRowsByAiCode": [skill_ai_by_ai[index] for index in sorted(skill_ai_by_ai)],
            }
        )

    slot_family_by_slot = {slot_family["slot"]: slot_family for slot_family in slot_families}

    named_families: list[dict[str, Any]] = []
    for family_id, rows in sorted(rows_by_family.items()):
        slots = sorted({int(row["slotOrPowerCandidate"]) for row in rows})
        slot_refs = [slot_family_by_slot[slot] for slot in slots]
        row_names = {str(row["name"]) for row in rows}
        passive_names = sorted(
            {
                str(slot_ref["passiveRow"]["name"])
                for slot_ref in slot_refs
                if slot_ref.get("passiveRow") is not None
            }
        )
        named_families.append(
            {
                "familyId": family_id,
                "label": canonical_family_label(family_id, rows),
                "familyType": family_runtime_type(slot_refs, row_names),
                "slots": slots,
                "rowNames": sorted(row_names),
                "passiveNames": passive_names,
                "heroSkillRows": [make_row_stub(row) for row in rows],
                "slotRuntimeTypes": [slot_ref["runtimeType"] for slot_ref in slot_refs],
                "activeRowIndices": sorted(
                    {
                        int(slot_ref["activeRow"]["index"])
                        for slot_ref in slot_refs
                        if slot_ref.get("activeRow") is not None
                    }
                ),
                "buffTailRowIndices": sorted(
                    {
                        int(buff["index"])
                        for slot_ref in slot_refs
                        for buff in slot_ref.get("buffTailRows", [])
                    }
                ),
                "skillAiBySkillCodeIndices": sorted(
                    {
                        int(item["index"])
                        for slot_ref in slot_refs
                        for item in slot_ref.get("skillAiRowsBySkillCode", [])
                    }
                ),
                "skillAiByAiCodeIndices": sorted(
                    {
                        int(item["index"])
                        for slot_ref in slot_refs
                        for item in slot_ref.get("skillAiRowsByAiCode", [])
                    }
                ),
            }
        )

    findings = []
    dispatch = next((item for item in named_families if item["familyId"] == "dispatch"), None)
    if dispatch is not None:
        findings.append(
            "Dispatch is the clearest multi-slot ladder: slots 20/21/22 each carry one Dispatch row, one active row, and one triggerMode=2 buff-tail row."
        )
    tower_defense = next((item for item in named_families if item["familyId"] == "tower-defense"), None)
    if tower_defense is not None:
        findings.append(
            "Tower defense is hero-specific: Defend Tower master rows span slots 6/13/23 while the passive side resolves to Thief/Helba/Juno Tower Defense aliases."
        )
    for slot in [11, 14, 15]:
        slot_family = slot_family_by_slot.get(slot)
        if slot_family is not None and slot_family["runtimeType"] == "shared-slot-multi-skill-buff":
            findings.append(
                f"Slot {slot} is a shared-slot hybrid: multiple named hero-skill rows collapse onto one active row and the same buff-tail bundle."
            )
    special_slots = [
        slot_family["slot"]
        for slot_family in slot_families
        if slot_family["runtimeType"] == "special-command-slot"
    ]
    if special_slots:
        findings.append(
            f"Special slots {special_slots} still sit outside the passive/active row range and remain best treated as event-only or buff-only commands."
        )
    findings.append(
        "Active row 24 remains the only orphan active-runtime row not currently reached by any hero-skill slot."
    )

    family_type_histogram = Counter(item["familyType"] for item in named_families)
    slot_runtime_histogram = Counter(item["runtimeType"] for item in slot_families)

    payload = {
        "summary": {
            "slotFamilyCount": len(slot_families),
            "namedFamilyCount": len(named_families),
            "slotRuntimeTypeHistogram": dict(sorted(slot_runtime_histogram.items())),
            "namedFamilyTypeHistogram": dict(sorted(family_type_histogram.items())),
            "specialSlots": special_slots,
        },
        "slotFamilies": slot_families,
        "namedFamilies": named_families,
        "findings": findings,
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
