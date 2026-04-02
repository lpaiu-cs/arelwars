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
        description="Correlate AW1 hero-skill master rows with passive rows and skill-AI/runtime links"
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the linked hero-skill report",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def is_tower_defense_alias(hero_name: str, passive_name: str) -> bool:
    return normalize_name(hero_name) == "defendtower" and passive_name.lower().endswith("tower defense")


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()

    hero_skills = read_json(parsed_dir / "XlsHeroSkill.eng.parsed.json")["records"]
    passive_rows = read_json(parsed_dir / "XlsHeroPassiveSkill.eng.parsed.json")["records"]
    skill_ai = read_json(parsed_dir / "XlsSkill_Ai.eng.parsed.json")["records"]
    effect_runtime = read_json(parsed_dir / "AW1.effect_runtime_links.json")

    skill_ai_by_id = defaultdict(list)
    for row in skill_ai:
        skill_ai_by_id[int(row["skillIdCandidate"])].append(row)

    hero_active_rows_with_effect_hits = {
        int(row["index"]): row for row in effect_runtime["heroActiveTailLinks"]
    }

    linked_rows: list[dict[str, Any]] = []
    passive_row_coverage: dict[int, list[int]] = defaultdict(list)
    slot_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    mode_histogram: Counter[str] = Counter()

    for row in hero_skills:
        slot = int(row["slotOrPowerCandidate"])
        mode_key = f"{int(row['modeA'])}:{int(row['modeB'])}"
        mode_histogram[mode_key] += 1

        passive_slot_match = None
        if 0 <= slot < len(passive_rows):
            passive = passive_rows[slot]
            if normalize_name(str(row["name"])) == normalize_name(str(passive["name"])) or is_tower_defense_alias(
                str(row["name"]), str(passive["name"])
            ):
                passive_slot_match = {
                    "index": passive["index"],
                    "name": passive["name"],
                    "valueA": passive["valueA"],
                    "valueB": passive["valueB"],
                    "tailU16": passive["tailU16"],
                    "matchKind": (
                        "tower-defense-alias"
                        if is_tower_defense_alias(str(row["name"]), str(passive["name"]))
                        else "exact-name"
                    ),
                }
                passive_row_coverage[int(passive["index"])].append(int(row["index"]))

        exact_skill_ai_by_skill_code = [
            {
                "index": item["index"],
                "skillIdCandidate": item["skillIdCandidate"],
                "triggerWindowA": item["triggerWindowA"],
                "triggerWindowB": item["triggerWindowB"],
                "tailModeBytes": item["tailModeBytes"],
            }
            for item in skill_ai_by_id.get(int(row["skillCodeCandidate"]), [])
        ]
        exact_skill_ai_by_ai_code = [
            {
                "index": item["index"],
                "skillIdCandidate": item["skillIdCandidate"],
                "triggerWindowA": item["triggerWindowA"],
                "triggerWindowB": item["triggerWindowB"],
                "tailModeBytes": item["tailModeBytes"],
            }
            for item in skill_ai_by_id.get(int(row["aiCodeCandidate"]), [])
        ]
        active_runtime_hint = hero_active_rows_with_effect_hits.get(slot)

        tags: list[str] = [f"mode-{mode_key}"]
        if passive_slot_match is not None:
            tags.append("passive-slot-linked")
            if passive_slot_match["matchKind"] == "tower-defense-alias":
                tags.append("tower-defense-alias")
        if exact_skill_ai_by_skill_code:
            tags.append("skill-ai-skill-code")
        if exact_skill_ai_by_ai_code:
            tags.append("skill-ai-ai-code")
        if active_runtime_hint is not None:
            tags.append("active-runtime-tail-hit")
        if slot >= 29:
            tags.append("special-slot-29plus")

        linked = {
            **row,
            "passiveSlotMatch": passive_slot_match,
            "matchingSkillAiBySkillCode": exact_skill_ai_by_skill_code,
            "matchingSkillAiByAiCode": exact_skill_ai_by_ai_code,
            "activeRuntimeHint": active_runtime_hint,
            "tags": tags,
        }
        linked_rows.append(linked)
        slot_groups[slot].append(
            {
                "index": row["index"],
                "name": row["name"],
                "skillCodeCandidate": row["skillCodeCandidate"],
                "aiCodeCandidate": row["aiCodeCandidate"],
                "modeA": row["modeA"],
                "modeB": row["modeB"],
            }
        )

    passive_exact_count = sum(
        1
        for row in linked_rows
        if row["passiveSlotMatch"] is not None and row["passiveSlotMatch"]["matchKind"] == "exact-name"
    )
    passive_alias_count = sum(
        1
        for row in linked_rows
        if row["passiveSlotMatch"] is not None and row["passiveSlotMatch"]["matchKind"] == "tower-defense-alias"
    )

    slot_group_entries = []
    for slot, rows in sorted(slot_groups.items()):
        passive = passive_rows[slot] if 0 <= slot < len(passive_rows) else None
        slot_group_entries.append(
            {
                "slot": slot,
                "heroSkillRows": rows,
                "passiveRow": (
                    {
                        "index": passive["index"],
                        "name": passive["name"],
                        "valueA": passive["valueA"],
                        "valueB": passive["valueB"],
                    }
                    if passive is not None
                    else None
                ),
            }
        )

    findings = [
        f"{len(passive_row_coverage)}/{len(passive_rows)} passive rows are reachable directly by hero-skill slotOrPowerCandidate indices.",
        f"{passive_exact_count} hero-skill rows match passive rows by exact normalized name, and {passive_alias_count} more match as Defend Tower -> * Tower Defense aliases.",
        "Slots 6, 13, and 23 are the clearest alias cases: three Defend Tower master rows line up with Thief/Helba/Juno Tower Defense passive rows.",
        "Slots 29, 30, and 31 remain outside the passive-row range and currently host special mode-0:2 rows such as Stun, Smoke, and Armageddon Buff.",
    ]

    report = {
        "summary": {
            "heroSkillRowCount": len(hero_skills),
            "passiveRowCount": len(passive_rows),
            "skillAiRowCount": len(skill_ai),
            "heroActiveRowsWithEffectHits": len(hero_active_rows_with_effect_hits),
            "passiveRowsReachableBySlot": len(passive_row_coverage),
            "heroSkillExactPassiveMatchCount": passive_exact_count,
            "heroSkillTowerDefenseAliasCount": passive_alias_count,
            "modeHistogram": dict(sorted(mode_histogram.items())),
            "specialSlotValues": sorted(
                {
                    int(row["slotOrPowerCandidate"])
                    for row in linked_rows
                    if int(row["slotOrPowerCandidate"]) >= len(passive_rows)
                }
            ),
        },
        "heroSkillLinks": linked_rows,
        "slotGroups": slot_group_entries,
        "passiveRowCoverage": {
            str(key): value for key, value in sorted(passive_row_coverage.items())
        },
        "findings": findings,
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
