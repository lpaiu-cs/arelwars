#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export canonical AW1 engine-input schema from parsed GXL tables")
    parser.add_argument("--parsed-dir", type=Path, required=True, help="Directory containing parsed AW1 GXL tables")
    parser.add_argument(
        "--effect-runtime-links",
        type=Path,
        required=True,
        help="Path to AW1.effect_runtime_links.json for PTC bridge enrichment",
    )
    parser.add_argument("--output", type=Path, required=True, help="Path to write AW1.engine_schema.json")
    parser.add_argument("--web-output", type=Path, help="Optional path under public/ to copy the same json")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def classify_unit_role(name: str, description: str) -> str:
    lowered = f"{name} {description}".lower()
    if any(token in lowered for token in ["thief", "steal", "sneak", "hide"]):
        return "stealth"
    if any(token in lowered for token in ["glider", "flying", "air"]):
        return "airborne"
    if any(token in lowered for token in ["panzer", "siege", "cannon", "catapult", "tank"]):
        return "siege"
    if any(token in lowered for token in ["hunter", "archer", "spearman", "range"]):
        return "ranged"
    if any(token in lowered for token in ["shield", "defense", "guard"]):
        return "defender"
    if any(token in lowered for token in ["heal", "support", "mana"]):
        return "support"
    if any(token in lowered for token in ["cavalry", "charge", "rush"]):
        return "flanker"
    return "frontline"


def mana_tier(description: str) -> str:
    lowered = description.lower()
    if "little mana" in lowered or "consumes little" in lowered:
        return "low"
    if "a lot of mana" in lowered or "consumes a lot" in lowered or "high mana" in lowered:
        return "high"
    return "medium"


def summarize_priority(values: list[int]) -> dict[str, float]:
    cleaned = [value for value in values if value != 255]
    if not cleaned:
        return {
            "aggression": 0.4,
            "support": 0.35,
            "burst": 0.4,
        }
    return {
        "aggression": round(min(max(cleaned) / 10, 1), 3),
        "support": round(min(cleaned[0] / 10, 1), 3),
        "burst": round(min(sum(cleaned) / len(cleaned) / 10, 1), 3),
    }


def projectile_metrics(row: dict[str, Any]) -> dict[str, float]:
    speed_or_range = max(int(row.get("speedOrRangeCandidate", 0)), 1)
    motion = int(row.get("motionCandidate", 0))
    return {
        "speed": round(0.045 + speed_or_range / 190, 4),
        "ttlBeats": max(3, min(10, 2 + speed_or_range // 4)),
        "strengthScale": round(0.75 + min(speed_or_range, 30) / 60 + motion * 0.08, 3),
    }


def effect_metrics(row: dict[str, Any]) -> dict[str, float]:
    duration = int(row.get("frameOrDurationCandidate", 1))
    return {
        "durationBeats": max(2, min(10, duration if duration <= 8 else round(duration / 6))),
        "intensity": round(0.6 + int(row.get("familyCandidate", 0)) * 0.08 + int(row.get("variantCandidate", 0)) * 0.03, 3),
    }


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()
    effect_runtime_links = read_json(args.effect_runtime_links.resolve())

    unit_rows = read_json(parsed_dir / "XlsUnit.eng.parsed.json")["records"]
    hero_rows = read_json(parsed_dir / "XlsHero.eng.parsed.json")["records"]
    hero_ai_rows = read_json(parsed_dir / "XlsHero_Ai.eng.parsed.json")["records"]
    skill_ai_rows = read_json(parsed_dir / "XlsSkill_Ai.eng.parsed.json")["records"]
    projectile_rows = read_json(parsed_dir / "XlsProjectile.eng.parsed.json")["records"]
    effect_rows = read_json(parsed_dir / "XlsEffect.eng.parsed.json")["records"]
    particle_rows = read_json(parsed_dir / "XlsParticle.eng.parsed.json")["records"]
    balance_rows = read_json(parsed_dir / "XlsBalance.eng.parsed.json")["records"]

    particle_runtime_rows = {int(row["index"]): row for row in effect_runtime_links.get("particleRows", [])}
    hero_ai_by_hero_id: dict[int, list[dict[str, Any]]] = {}
    for row in hero_ai_rows:
        hero_ai_by_hero_id.setdefault(int(row["heroIdCandidate"]), []).append(row)

    member_role_map = {
        "Vincent": "vanguard",
        "Helba": "support",
        "Juno": "caster",
        "Manos": "breaker",
        "Caesar": "guardian",
        "Rogan": "rally",
    }

    units = []
    for row in unit_rows:
        words = list(row.get("preDescriptionU16", []))
        units.append(
            {
                **row,
                "engineHints": {
                    "roleHint": classify_unit_role(str(row["name"]), str(row["description"])),
                    "manaTier": mana_tier(str(row["description"])),
                    "airborne": "glider" in str(row["name"]).lower(),
                    "stealth": "thief" in str(row["name"]).lower(),
                    "costWordCandidate": words[5] if len(words) > 5 else 0,
                    "vitalityWordCandidate": max(words[7], words[8]) if len(words) > 8 else 0,
                    "speedWordCandidate": max(words[15], words[16]) if len(words) > 16 else 0,
                    "reachWordCandidate": max(words[18], words[19]) if len(words) > 19 else 0,
                },
            }
        )

    heroes = []
    for row in hero_rows:
        linked_profiles = hero_ai_by_hero_id.get(int(row["candidateHeroId"]), [])
        heroes.append(
            {
                **row,
                "memberRoleHint": member_role_map.get(str(row["name"]), "generalist"),
                "profileIndexes": [int(profile["index"]) for profile in linked_profiles],
                "profileSummary": summarize_priority(
                    [value for profile in linked_profiles for value in profile.get("priorityGridU8", [])]
                ),
            }
        )

    hero_ai_profiles = []
    for row in hero_ai_rows:
        timings = [value for value in row.get("timingPatternU8", []) if value > 0]
        fallbacks = [value for value in row.get("fallbackPatternU8", []) if value > 0]
        hero_ai_profiles.append(
            {
                **row,
                "engineHints": {
                    **summarize_priority(list(row.get("priorityGridU8", []))),
                    "spawnCadenceBeats": max(2, min(8, round((sum(timings) / len(timings)) / 18))) if timings else 4,
                    "skillCadenceBeats": max(2, min(8, round((sum(timings) / len(timings)) / 16))) if timings else 5,
                    "fallbackCadenceBeats": max(3, min(9, round((sum(fallbacks) / len(fallbacks)) / 15))) if fallbacks else 6,
                },
            }
        )

    skill_ai_profiles = []
    for row in skill_ai_rows:
        window_a = [value for value in row.get("triggerWindowA", []) if value > 0]
        window_b = [value for value in row.get("triggerWindowB", []) if value > 0]
        tail = list(row.get("tailModeBytes", []))
        skill_ai_profiles.append(
            {
                **row,
                "engineHints": {
                    "tailModeKey": "-".join(f"{value:02x}" for value in tail),
                    "primaryTriggerBeat": max(1, round((sum(window_a) / len(window_a)) / 15)) if window_a else None,
                    "secondaryTriggerBeat": max(1, round((sum(window_b) / len(window_b)) / 15)) if window_b else None,
                    "triggerPolicy":
                        "burst"
                        if max(window_b, default=0) >= 200
                        else "late"
                        if max(window_a + window_b, default=0) >= 80
                        else "early",
                },
            }
        )

    projectiles = []
    for row in projectile_rows:
        projectiles.append(
            {
                **row,
                "engineHints": {
                    **projectile_metrics(row),
                    "movementKind": "lobbed" if int(row.get("motionCandidate", 0)) >= 2 else "linear",
                    "rangeClass":
                        "long"
                        if int(row.get("speedOrRangeCandidate", 0)) >= 18
                        else "mid"
                        if int(row.get("speedOrRangeCandidate", 0)) >= 10
                        else "short",
                },
            }
        )

    effects = []
    for row in effect_rows:
        metrics = effect_metrics(row)
        effects.append(
            {
                **row,
                "engineHints": {
                    **metrics,
                    "blendMode":
                        "additive"
                        if int(row.get("blendFlagCandidate", 0)) >= 2
                        else "alpha"
                        if int(row.get("blendFlagCandidate", 0)) == 1
                        else "opaque",
                    "looping": bool(int(row.get("loopFlagCandidate", 0))),
                },
            }
        )

    particles = []
    for row in particle_rows:
        runtime = particle_runtime_rows.get(int(row["index"]), {})
        primary_ptc = runtime.get("primaryPtc")
        secondary_ptc = runtime.get("secondaryPtc")
        particles.append(
            {
                **row,
                "ptcBridge": {
                    "relationKind": runtime.get("relationKind", "unknown"),
                    "primaryStem": primary_ptc.get("stem") if primary_ptc else None,
                    "secondaryStem": secondary_ptc.get("stem") if secondary_ptc else None,
                    "primaryTimingFields": primary_ptc.get("timingFields") if primary_ptc else [],
                    "primaryEmissionFields": primary_ptc.get("emissionFields") if primary_ptc else [],
                    "primaryRatioFieldsFloat": primary_ptc.get("ratioFieldsFloat") if primary_ptc else [],
                    "ptcBridgeConfirmed": bool(primary_ptc),
                },
                "engineHints": {
                    "emitterKind":
                        "burst"
                        if primary_ptc and max(primary_ptc.get("emissionFields", [0]), default=0) >= 8
                        else "steady"
                        if primary_ptc
                        else "unknown",
                    "intensity": round(0.7 + int(row.get("variantCandidate", 0)) * 0.08 + (0.15 if primary_ptc else 0), 3),
                },
            }
        )

    balance_label_map = {
        0: "allied-mana-baseline",
        1: "enemy-mana-baseline",
        2: "allied-population-baseline",
        3: "cooldown-and-capacity-baseline",
    }
    balance = []
    for row in balance_rows:
        balance.append(
            {
                **row,
                "engineHints": {
                    "label": balance_label_map.get(int(row["index"]), f"balance-slot-{int(row['index'])}"),
                },
            }
        )

    schema = {
        "summary": {
            "unitCount": len(units),
            "heroCount": len(heroes),
            "heroAiProfileCount": len(hero_ai_profiles),
            "skillAiProfileCount": len(skill_ai_profiles),
            "projectileCount": len(projectiles),
            "effectCount": len(effects),
            "particleCount": len(particles),
            "balanceRowCount": len(balance),
        },
        "sourceTables": {
            "units": "XlsUnit.eng.parsed.json",
            "heroes": "XlsHero.eng.parsed.json",
            "heroAiProfiles": "XlsHero_Ai.eng.parsed.json",
            "skillAiProfiles": "XlsSkill_Ai.eng.parsed.json",
            "projectiles": "XlsProjectile.eng.parsed.json",
            "effects": "XlsEffect.eng.parsed.json",
            "particles": "XlsParticle.eng.parsed.json",
            "balance": "XlsBalance.eng.parsed.json",
        },
        "units": units,
        "heroes": heroes,
        "heroAiProfiles": hero_ai_profiles,
        "skillAiProfiles": skill_ai_profiles,
        "projectiles": projectiles,
        "effects": effects,
        "particles": particles,
        "balance": balance,
        "findings": [
            "Phase-4 canonical schema now fixes XlsUnit, XlsHero, XlsHero_Ai, XlsSkill_Ai, XlsProjectile, XlsEffect, XlsParticle, and XlsBalance into one engine-input export.",
            "Each section preserves the parsed raw slots while adding stable engineHints fields for runtime consumption.",
            "XlsParticle rows are enriched with PTC bridge data from AW1.effect_runtime_links.json so particle records no longer remain detached from runtime assets.",
            "Battle-model generation can now depend on this schema instead of reading those GXL-derived tables indirectly.",
        ],
    }

    output_path = args.output.resolve()
    write_json(output_path, schema)
    if args.web_output:
        copy_file(output_path, args.web_output.resolve())


if __name__ == "__main__":
    main()
