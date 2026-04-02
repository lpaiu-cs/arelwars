#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


FAMILY_HINTS: dict[str, dict[str, Any]] = {
    "dispatch": {
        "archetypeKind": "respawn-redeploy-cooldown-ladder",
        "mechanicHints": [
            "multi-tier reduction of hero redispatch or respawn delay",
            "each tier has its own active cadence and triggerMode=2 buff row",
            "best current engine model is a progression ladder, not three unrelated skills",
        ],
        "confidence": "high",
    },
    "tower-defense": {
        "archetypeKind": "tower-defense-stance-ladder",
        "mechanicHints": [
            "hero-specific tower-defense variants share the same master family",
            "slot 23 carries the clearest buff bridge, which suggests a hero-variant overlay rather than a separate mechanic family",
            "best current engine model is a tower-stance attack channel with hero-specific projectile or range tuning",
        ],
        "confidence": "high",
    },
    "naturalhealing": {
        "archetypeKind": "shared-heal-channel",
        "mechanicHints": [
            "shares slot 11 with Recall",
            "best current engine model is a shared runtime channel whose mode changes the outcome from heal-over-time to relocation",
            "slot 11 has the densest buff bundle in the current data",
        ],
        "confidence": "medium",
    },
    "recall": {
        "archetypeKind": "shared-relocation-channel",
        "mechanicHints": [
            "shares slot 11 with Natural Healing",
            "mode 1:0 differentiates it from the passive-flavored Natural Healing row",
            "best current engine model is a relocation or regroup command layered on the same runtime slot",
        ],
        "confidence": "medium",
    },
    "hpup": {
        "archetypeKind": "stat-ladder-with-shared-channel",
        "mechanicHints": [
            "three HP Up rows span slots 0, 7, and 14",
            "slot 14 is shared with Return to Nature and already carries buff rows",
            "best current engine model is a stat ladder that later shares its channel with an active conversion skill",
        ],
        "confidence": "medium",
    },
    "returntonature": {
        "archetypeKind": "shared-resource-conversion-channel",
        "mechanicHints": [
            "shares slot 14 with HP Up",
            "description and skill-ai linkage both point to mana conversion instead of a pure passive stat change",
            "best current engine model is an active conversion skill layered on the HP Up channel",
        ],
        "confidence": "medium",
    },
    "manawall": {
        "archetypeKind": "shared-defensive-barrier-channel",
        "mechanicHints": [
            "shares slot 15 with Armageddon",
            "passive row, active timing, and buff row all live on the same slot",
            "best current engine model is a defensive barrier channel that can be repurposed by a stronger hero skill mode",
        ],
        "confidence": "medium",
    },
    "armageddon": {
        "archetypeKind": "shared-meteor-buff-channel",
        "mechanicHints": [
            "shares slot 15 with Mana Wall",
            "description points to a meteor attack followed by mana regeneration",
            "best current engine model is a burst attack over the same shared channel that also emits a buff side effect",
        ],
        "confidence": "medium",
    },
    "managain": {
        "archetypeKind": "reactive-mana-proc",
        "mechanicHints": [
            "single-slot passive-active-buff family on slot 19",
            "description points to mana gain on being hit, which matches a reactive trigger model",
            "best current engine model is a passive proc with its own active timing gate and buff trigger row",
        ],
        "confidence": "high",
    },
    "special-stun": {
        "archetypeKind": "special-command",
        "mechanicHints": [
            "special slot outside the passive and active runtime tables",
            "current best treatment is as an event-only command or status opcode payload",
        ],
        "confidence": "low",
    },
    "special-smoke": {
        "archetypeKind": "special-command",
        "mechanicHints": [
            "special slot outside the passive and active runtime tables",
            "shares aiCode 8 lineage with Armageddon Buff, which suggests effect-script usage rather than a normal hero-skill row",
        ],
        "confidence": "low",
    },
    "special-armageddonbuff": {
        "archetypeKind": "special-command",
        "mechanicHints": [
            "special slot outside the passive and active runtime tables",
            "best current treatment is a follow-up buff command tied to Armageddon rather than a standalone learnable skill",
        ],
        "confidence": "low",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export engine-facing AW1 hero runtime archetype candidates"
    )
    parser.add_argument(
        "--family-report",
        type=Path,
        required=True,
        help="Path to AW1.hero_runtime_families.json",
    )
    parser.add_argument(
        "--effect-report",
        type=Path,
        required=True,
        help="Path to AW1.effect_runtime_links.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write AW1.hero_runtime_archetypes.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def non_ff_values(values: list[int]) -> list[int]:
    return [int(value) for value in values if int(value) != 255]


def compact_active_row(row: dict[str, Any] | None, tail_link: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    payload = {
        "index": int(row["index"]),
        "headerBytes": row["headerBytes"],
        "timingWindowA": row["timingWindowA"],
        "timingWindowB": row["timingWindowB"],
        "timingWindowACompact": non_ff_values(row["timingWindowA"]),
        "timingWindowBCompact": non_ff_values(row["timingWindowB"]),
        "tailPairBE": row["tailPairBE"],
    }
    if tail_link is not None:
        payload["tailLink"] = tail_link
    return payload


def default_archetype_kind(family_type: str) -> str:
    return {
        "multi-slot-ladder-with-buff": "multi-tier-runtime-ladder",
        "multi-slot-ladder": "multi-tier-runtime-ladder",
        "shared-slot-hybrid-with-buff": "shared-runtime-channel",
        "shared-slot-hybrid": "shared-runtime-channel",
        "single-slot-family": "single-slot-runtime",
        "special-family": "special-command",
    }.get(family_type, "runtime-family")


def default_confidence(family_type: str) -> str:
    return {
        "multi-slot-ladder-with-buff": "high",
        "multi-slot-ladder": "medium",
        "shared-slot-hybrid-with-buff": "medium",
        "shared-slot-hybrid": "medium",
        "single-slot-family": "medium",
        "special-family": "low",
    }.get(family_type, "low")


def generic_hints(family: dict[str, Any]) -> list[str]:
    slot_runtime_types = family["slotRuntimeTypes"]
    hints: list[str] = []
    if any("buff" in item for item in slot_runtime_types):
        hints.append("family includes explicit buff-tail rows and should remain two-phase in the remake runtime")
    if len(family["slots"]) > 1:
        hints.append("family spans multiple slots, so upgrade tier or hero variant should be modeled as indexed runtime rows")
    if len(family["activeRowIndices"]) > 1:
        hints.append("multiple active rows exist, so the remake engine should not collapse them into a single timing profile")
    if not hints:
        hints.append("family currently behaves like one compact runtime row with limited slot variance")
    return hints


def main() -> None:
    args = parse_args()
    family_report = read_json(args.family_report.resolve())
    effect_report = read_json(args.effect_report.resolve())

    effect_links_by_active_index = {
        int(item["index"]): item for item in effect_report["heroActiveTailLinks"]
    }
    slot_family_by_slot = {
        int(item["slot"]): item for item in family_report["slotFamilies"]
    }

    archetypes: list[dict[str, Any]] = []
    for family in family_report["namedFamilies"]:
        family_id = str(family["familyId"])
        overrides = FAMILY_HINTS.get(family_id, {})
        slot_payloads = []
        active_rows = []
        buff_rows_by_index: dict[int, dict[str, Any]] = {}
        skill_ai_skill_by_index: dict[int, dict[str, Any]] = {}
        skill_ai_ai_by_index: dict[int, dict[str, Any]] = {}
        passive_rows_by_index: dict[int, dict[str, Any]] = {}

        for slot in family["slots"]:
            slot_family = slot_family_by_slot[int(slot)]
            active_row = slot_family.get("activeRow")
            tail_link = None
            if active_row is not None:
                tail_link = effect_links_by_active_index.get(int(active_row["index"]))
                active_rows.append(compact_active_row(active_row, tail_link))
            if slot_family.get("passiveRow") is not None:
                passive_rows_by_index[int(slot_family["passiveRow"]["index"])] = slot_family["passiveRow"]
            for buff in slot_family.get("buffTailRows", []):
                buff_rows_by_index[int(buff["index"])] = buff
            for item in slot_family.get("skillAiRowsBySkillCode", []):
                skill_ai_skill_by_index[int(item["index"])] = item
            for item in slot_family.get("skillAiRowsByAiCode", []):
                skill_ai_ai_by_index[int(item["index"])] = item
            slot_payloads.append(
                {
                    "slot": int(slot),
                    "runtimeType": slot_family["runtimeType"],
                    "passiveRowIndex": (
                        int(slot_family["passiveRow"]["index"])
                        if slot_family.get("passiveRow") is not None
                        else None
                    ),
                    "activeRowIndex": (
                        int(slot_family["activeRow"]["index"])
                        if slot_family.get("activeRow") is not None
                        else None
                    ),
                    "buffTailRowIndices": sorted(
                        int(item["index"]) for item in slot_family.get("buffTailRows", [])
                    ),
                }
            )

        exact_tail_hit = any(
            any(
                report["projectileExactMatches"] or report["effectExactMatches"] or report["particleExactMatches"]
                for report in active_row["tailLink"]["pairReports"]
            )
            for active_row in active_rows
            if active_row is not None and active_row.get("tailLink") is not None
        )
        hint_tail_hit = any(
            any(report["projectileIdHints"] for report in active_row["tailLink"]["pairReports"])
            for active_row in active_rows
            if active_row is not None and active_row.get("tailLink") is not None
        )

        evidence = []
        if exact_tail_hit:
            evidence.append("has exact projectile or effect hits in XlsHeroActiveSkill.tailPairBE")
        elif hint_tail_hit:
            evidence.append("has projectile or effect hints in XlsHeroActiveSkill.tailPairBE")
        if buff_rows_by_index:
            evidence.append("has explicit XlsHeroBuffSkill tail-link rows")
        if len(family["slots"]) > 1:
            evidence.append("spans multiple slots, which is consistent with tier ladders or hero variants")
        if len(family["rowNames"]) > 1:
            evidence.append("multiple hero-skill names collapse into one runtime channel")

        archetypes.append(
            {
                "archetypeId": family_id,
                "label": family["label"],
                "archetypeKind": overrides.get("archetypeKind", default_archetype_kind(family["familyType"])),
                "familyType": family["familyType"],
                "confidence": overrides.get("confidence", default_confidence(family["familyType"])),
                "slots": family["slots"],
                "rowNames": family["rowNames"],
                "passiveNames": family["passiveNames"],
                "heroSkillRows": family["heroSkillRows"],
                "slotPayloads": slot_payloads,
                "passiveRows": [passive_rows_by_index[index] for index in sorted(passive_rows_by_index)],
                "activeRows": active_rows,
                "buffRows": [buff_rows_by_index[index] for index in sorted(buff_rows_by_index)],
                "skillAiBySkillCode": [
                    skill_ai_skill_by_index[index] for index in sorted(skill_ai_skill_by_index)
                ],
                "skillAiByAiCode": [
                    skill_ai_ai_by_index[index] for index in sorted(skill_ai_ai_by_index)
                ],
                "mechanicHints": overrides.get("mechanicHints", generic_hints(family)),
                "evidence": evidence,
            }
        )

    summary = {
        "archetypeCount": len(archetypes),
        "archetypeKindHistogram": dict(
            sorted(Counter(item["archetypeKind"] for item in archetypes).items())
        ),
        "confidenceHistogram": dict(
            sorted(Counter(item["confidence"] for item in archetypes).items())
        ),
    }

    findings = [
        "Dispatch, Tower Defense, HP Up, and other repeated hero-skill names now resolve to engine-facing runtime archetypes rather than only raw slot links.",
        "Shared-slot hybrids on 11, 14, and 15 are now explicit archetypes, which means the remake runtime can model them as channel-sharing skills instead of unrelated rows.",
        "Special slots 29, 30, and 31 remain outside the passive and active tables and should still be treated as command or effect-script payloads until stronger evidence appears.",
    ]

    write_json(
        args.output.resolve(),
        {
            "summary": summary,
            "archetypes": archetypes,
            "findings": findings,
        },
    )


if __name__ == "__main__":
    main()
