#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export an engine-facing AW1 battle model")
    parser.add_argument("--battle-catalog", type=Path, required=True, help="Path to AW1.battle_catalog.json")
    parser.add_argument("--hero-archetypes", type=Path, required=True, help="Path to AW1.hero_runtime_archetypes.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the local battle model json")
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


def classify_skill_kind(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ["heal", "grace", "natural", "defend tower", "repair", "defense stance", "mana wall"]):
        return "support"
    if any(token in lowered for token in ["armageddon", "meteor", "blizzard", "lightning", "wave", "thunder", "bomb"]):
        return "burst"
    if any(token in lowered for token in ["dispatch", "rally", "align", "encourage", "build tower"]):
        return "orders"
    if any(token in lowered for token in ["smoke", "stun", "recall", "return", "convert", "snatch"]):
        return "utility"
    return "balanced"


def classify_item_kind(name: str, category_candidate: int) -> str:
    lowered = name.lower()
    if "potion" in lowered or "healing" in lowered:
        return "heal"
    if "mana" in lowered:
        return "mana"
    if any(token in lowered for token in ["arrow", "meteor", "thunder"]):
        return "burst"
    if any(token in lowered for token in ["drum", "detector", "ward", "smoke"]):
        return "orders"
    if category_candidate == 2:
        return "support"
    return "utility"


def attack_metrics(row: dict[str, Any]) -> dict[str, float]:
    params = list(row.get("parameterBytes", []))
    while len(params) < 12:
        params.append(0)
    damage = max(int(params[7]) + (int(params[8]) << 8), 20)
    cadence = max(int(params[9]) + (int(params[10]) << 8), 8)
    reach = max(int(params[11]), 4)
    mobility = max(int(params[5]), 1)
    return {
        "damage": float(damage),
        "cadence": float(cadence),
        "reach": float(reach),
        "mobility": float(mobility),
    }


def projectile_metrics(row: dict[str, Any]) -> dict[str, float]:
    speed_or_range = max(int(row.get("speedOrRangeCandidate", 0)), 1)
    motion = int(row.get("motionCandidate", 0))
    return {
        "speed": round(0.045 + speed_or_range / 190, 4),
        "ttl_beats": max(3, min(10, 2 + speed_or_range // 4)),
        "strength_scale": round(0.75 + min(speed_or_range, 30) / 60 + motion * 0.08, 3),
    }


def effect_metrics(row: dict[str, Any]) -> dict[str, float]:
    duration = int(row.get("frameOrDurationCandidate", 1))
    return {
        "duration_beats": max(2, min(10, duration if duration <= 8 else round(duration / 6))),
        "intensity": round(0.6 + int(row.get("familyCandidate", 0)) * 0.08 + int(row.get("variantCandidate", 0)) * 0.03, 3),
    }


def choose_base_attack(rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    enriched: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        metrics = attack_metrics(row)
        score = metrics["damage"] + metrics["reach"] * 2 + metrics["mobility"] * 6
        if role == "screen":
            score -= metrics["reach"] * 0.8
        elif role == "push":
            score += metrics["damage"] * 0.25
        elif role == "support":
            score += metrics["reach"] * 3.5 - metrics["damage"] * 0.1
        elif role == "siege":
            score += metrics["damage"] * 0.45 + metrics["reach"] * 2.4
        elif role == "skill-window":
            score += metrics["reach"] * 4 + metrics["mobility"] * 5
        elif role == "tower-rally":
            score += metrics["cadence"] * 0.12 + metrics["mobility"] * 6
        enriched.append((score, row))

    if role == "screen":
        preferred = [row for _, row in enriched if int(row.get("attackIdCandidate", 0)) == 0]
    elif role == "push":
        preferred = [row for _, row in enriched if int(row.get("attackIdCandidate", 0)) in {0, 1}]
    elif role == "support":
        preferred = [row for _, row in enriched if int(row.get("attackIdCandidate", 0)) == 1]
    elif role == "siege":
        preferred = [row for _, row in enriched if int(row.get("attackIdCandidate", 0)) == 1]
    elif role == "skill-window":
        preferred = [row for _, row in enriched if int(row.get("attackIdCandidate", 0)) in {1, 3}]
    else:
        preferred = [row for _, row in enriched if int(row.get("attackIdCandidate", 0)) in {1, 3}]

    if preferred:
        enriched = [(next(score for score, candidate in enriched if candidate["index"] == row["index"]), row) for row in preferred]

    return max(enriched, key=lambda item: item[0])[1]


def find_matching_projectile(projectiles: list[dict[str, Any]], role: str) -> dict[str, Any]:
    candidates = list(projectiles)
    if role == "support":
        candidates = [row for row in projectiles if int(row.get("motionCandidate", 0)) in {0, 2}]
    elif role == "siege":
        candidates = [row for row in projectiles if int(row.get("speedOrRangeCandidate", 0)) >= 15]
    elif role == "skill-window":
        candidates = [row for row in projectiles if int(row.get("familyCandidate", 0)) in {1, 4, 7}]
    if not candidates:
        candidates = list(projectiles)
    return max(candidates, key=lambda row: projectile_metrics(row)["strength_scale"])


def find_matching_effect(effects: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    candidates = list(effects)
    if kind == "heal":
        candidates = [row for row in effects if int(row.get("familyCandidate", 0)) in {1, 2}]
    elif kind == "burst":
        candidates = [row for row in effects if int(row.get("familyCandidate", 0)) in {3, 0}]
    elif kind == "utility":
        candidates = [row for row in effects if int(row.get("loopFlagCandidate", 0)) == 0]
    if not candidates:
        candidates = list(effects)
    return max(candidates, key=lambda row: effect_metrics(row)["intensity"])


def derive_unit_template(
    template_id: str,
    label: str,
    role: str,
    attack_row: dict[str, Any],
    projectile_row: dict[str, Any] | None,
    effect_row: dict[str, Any] | None,
    side: str,
    hero: bool = False,
    power_scale: float = 1.0,
    durability_scale: float = 1.0,
    speed_scale: float = 1.0,
) -> dict[str, Any]:
    attack = attack_metrics(attack_row)
    projectile = projectile_metrics(projectile_row) if projectile_row else {"speed": 0.1, "ttl_beats": 4, "strength_scale": 1.0}
    max_hp = round((0.95 + attack["damage"] / 160) * durability_scale * (1.75 if hero else 1.0), 3)
    power = round((0.12 + attack["damage"] / 520) * power_scale * (1.4 if hero else 1.0), 3)
    speed = round((0.012 + attack["mobility"] / 170) * speed_scale * (1.12 if side == "allied" else 1.0), 4)
    range_value = round(0.038 + attack["reach"] / 180 + (0.03 if role in {"support", "skill-window", "siege"} else 0), 4)
    attack_period = max(1, min(7, round(attack["cadence"] / 18)))
    return {
        "id": template_id,
        "label": label,
        "side": side,
        "role": role,
        "hero": hero,
        "baseAttackIndex": int(attack_row["index"]),
        "projectileTemplateId": None if role == "screen" else (f"projectile-{int(projectile_row['index'])}" if projectile_row else None),
        "effectTemplateId": f"effect-{int(effect_row['index'])}" if effect_row else None,
        "maxHp": max_hp,
        "power": power,
        "speed": speed,
        "range": range_value,
        "attackPeriodBeats": attack_period,
        "populationCost": 0 if hero else (2 if role in {"siege", "skill-window"} else 1),
        "manaCost": 0 if hero else max(4, round(attack["damage"] / 18)),
        "projectileSpeed": projectile["speed"],
        "projectileStrengthScale": projectile["strength_scale"],
        "projectileTtlBeats": projectile["ttl_beats"],
    }


def summarize_hero_ai(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if not profiles:
        return {
            "aggression": 0.45,
            "support": 0.35,
            "burst": 0.4,
            "mana": 0.3,
            "spawnCadenceBeats": 4,
            "skillCadenceBeats": 5,
            "itemCadenceBeats": 6,
            "heroCadenceBeats": 7,
        }

    priority_values = [value for profile in profiles for value in profile.get("priorityGridU8", []) if value != 255]
    timing_values = [value for profile in profiles for value in profile.get("timingPatternU8", []) if value > 0]
    fallback_values = [value for profile in profiles for value in profile.get("fallbackPatternU8", []) if value > 0]
    mean_priority = sum(priority_values) / len(priority_values) if priority_values else 4
    mean_timing = sum(timing_values) / len(timing_values) if timing_values else 30
    mean_fallback = sum(fallback_values) / len(fallback_values) if fallback_values else 30
    return {
        "aggression": round(min(mean_priority / 10, 1), 3),
        "support": round(min((priority_values[0] if priority_values else 4) / 10, 1), 3),
        "burst": round(min((max(priority_values) if priority_values else 4) / 10, 1), 3),
        "mana": round(min(mean_fallback / 80, 1), 3),
        "spawnCadenceBeats": max(2, min(8, round(mean_timing / 18))),
        "skillCadenceBeats": max(2, min(8, round(mean_timing / 16))),
        "itemCadenceBeats": max(3, min(9, round(mean_fallback / 15))),
        "heroCadenceBeats": max(3, min(9, round((mean_timing + mean_fallback) / 24))),
    }


def main() -> None:
    args = parse_args()
    battle_catalog = read_json(args.battle_catalog.resolve())
    hero_archetypes = read_json(args.hero_archetypes.resolve())

    base_attacks = list(battle_catalog.get("baseAttacks", []))
    projectiles = list(battle_catalog.get("projectiles", []))
    effects = list(battle_catalog.get("effects", []))
    items = list(battle_catalog.get("items", []))
    heroes = list(battle_catalog.get("heroes", []))
    hero_skills = list(battle_catalog.get("heroSkills", []))
    hero_active_profiles = list(battle_catalog.get("heroActiveSkillProfiles", []))
    skill_ai_profiles = list(battle_catalog.get("skillAiProfiles", []))
    balance_rows = list(battle_catalog.get("balanceRows", []))
    correspondence_rows = list(battle_catalog.get("correspondenceRows", []))

    projectile_templates = []
    for row in projectiles:
      metrics = projectile_metrics(row)
      projectile_templates.append({
          "id": f"projectile-{int(row['index'])}",
          "label": f"Projectile {int(row['projectileIdCandidate'])}",
          "projectileIndex": int(row["index"]),
          "familyCandidate": int(row.get("familyCandidate", 0)),
          "variantCandidate": int(row.get("variantCandidate", 0)),
          "speed": metrics["speed"],
          "ttlBeats": metrics["ttl_beats"],
          "strengthScale": metrics["strength_scale"],
          "motionCandidate": int(row.get("motionCandidate", 0)),
      })

    effect_templates = []
    for row in effects:
      metrics = effect_metrics(row)
      effect_templates.append({
          "id": f"effect-{int(row['index'])}",
          "label": f"Effect {int(row['effectIdCandidate'])}",
          "effectIndex": int(row["index"]),
          "familyCandidate": int(row.get("familyCandidate", 0)),
          "variantCandidate": int(row.get("variantCandidate", 0)),
          "durationBeats": metrics["duration_beats"],
          "intensity": metrics["intensity"],
          "loop": bool(int(row.get("loopFlagCandidate", 0))),
          "blendFlagCandidate": int(row.get("blendFlagCandidate", 0)),
      })

    role_attack_rows = {
        "screen": choose_base_attack(base_attacks, "screen"),
        "push": choose_base_attack(base_attacks, "push"),
        "support": choose_base_attack(base_attacks, "support"),
        "siege": choose_base_attack(base_attacks, "siege"),
        "tower-rally": choose_base_attack(base_attacks, "tower-rally"),
        "skill-window": choose_base_attack(base_attacks, "skill-window"),
    }
    role_projectile_rows = {
        "screen": None,
        "push": find_matching_projectile(projectiles, "push"),
        "support": find_matching_projectile(projectiles, "support"),
        "siege": find_matching_projectile(projectiles, "siege"),
        "tower-rally": find_matching_projectile(projectiles, "support"),
        "skill-window": find_matching_projectile(projectiles, "skill-window"),
    }
    role_effect_rows = {
        "screen": find_matching_effect(effects, "utility"),
        "push": find_matching_effect(effects, "burst"),
        "support": find_matching_effect(effects, "heal"),
        "siege": find_matching_effect(effects, "burst"),
        "tower-rally": find_matching_effect(effects, "heal"),
        "skill-window": find_matching_effect(effects, "utility"),
    }

    unit_templates = []
    for side in ("allied", "enemy"):
        for role in ("screen", "push", "support", "siege", "tower-rally", "skill-window"):
            scale = 1.0 if side == "allied" else 1.04
            unit_templates.append(
                derive_unit_template(
                    f"{side}-{role}",
                    f"{side.title()} {role}",
                    role,
                    role_attack_rows[role],
                    role_projectile_rows[role],
                    role_effect_rows[role],
                    side,
                    hero=False,
                    power_scale=scale,
                    durability_scale=1.0 if side == "allied" else 1.06,
                )
            )

    hero_role_map = {
        "Vincent": ("push", "vanguard"),
        "Helba": ("support", "support"),
        "Juno": ("skill-window", "caster"),
        "Manos": ("siege", "breaker"),
        "Caesar": ("screen", "guardian"),
        "Rogan": ("tower-rally", "rally"),
    }
    hero_skill_lookup = {str(row["name"]).lower(): row for row in hero_skills}
    item_lookup = {str(row["name"]).lower(): row for row in items}
    hero_templates = []
    for hero in heroes:
        hero_name = str(hero["name"])
        base_role, member_role = hero_role_map.get(hero_name, ("push", "generalist"))
        unit_templates.append(
            derive_unit_template(
                f"hero-{hero_name.lower()}",
                hero_name,
                "hero",
                role_attack_rows[base_role],
                role_projectile_rows[base_role],
                role_effect_rows[base_role],
                "allied",
                hero=True,
                power_scale=1.18 if base_role in {"push", "siege"} else 1.08,
                durability_scale=1.22 if base_role in {"screen", "support"} else 1.1,
                speed_scale=1.08 if base_role in {"push", "skill-window"} else 1.0,
            )
        )
        preferred_skills_by_name = {
            "Vincent": ["shuriken", "dispatch", "snatch"],
            "Helba": ["natural healing", "defend tower", "mana wall"],
            "Juno": ["lightning", "lotus blizzard", "mana gain"],
            "Manos": ["wave", "berserk", "armageddon"],
            "Caesar": ["defense stance", "parry", "defend tower"],
            "Rogan": ["rally", "dispatch", "encourage"],
        }.get(hero_name, [])
        preferred_items_by_name = {
            "Vincent": ["arrow shower (m)", "mana spring (s)"],
            "Helba": ["healing grace (m)", "hp potion (m)"],
            "Juno": ["mana spring (m)", "judgment thunder (s)"],
            "Manos": ["meteor (m)", "marching drum (m)"],
            "Caesar": ["hp potion (l)", "healing grace (s)"],
            "Rogan": ["marching drum (s)", "mana spring (s)"],
        }.get(hero_name, [])
        hero_templates.append({
            "id": f"hero-{hero_name.lower()}",
            "heroId": int(hero["heroId"]),
            "name": hero_name,
            "memberRole": member_role,
            "unitTemplateId": f"hero-{hero_name.lower()}",
            "preferredSkillNames": [hero_skill_lookup[name]["name"] for name in preferred_skills_by_name if name in hero_skill_lookup],
            "preferredItemNames": [item_lookup[name]["name"] for name in preferred_items_by_name if name in item_lookup],
            "ai": summarize_hero_ai(list(hero.get("profiles", []))),
        })

    skill_templates = []
    for row in hero_skills:
        slot = int(row.get("slotOrPowerCandidate", 0))
        active_profile = hero_active_profiles[slot] if 0 <= slot < len(hero_active_profiles) else None
        timings = []
        if active_profile:
            timings = [int(value) for value in list(active_profile.get("timingWindowA", [])) + list(active_profile.get("timingWindowB", [])) if int(value) > 0]
        skill_kind = classify_skill_kind(str(row["name"]))
        mana_cost = max(6, min(44, (sum(timings[:3]) // max(len(timings[:3]), 1)) // 2 + (slot % 6) * 2 if timings else 10 + (slot % 5) * 2))
        cooldown_beats = max(2, min(9, round((sum(timings[:4]) / max(len(timings[:4]), 1)) / 18) if timings else 4))
        projectile_row = find_matching_projectile(projectiles, "skill-window" if skill_kind in {"burst", "utility"} else "support")
        effect_row = find_matching_effect(effects, "heal" if skill_kind == "support" else "burst" if skill_kind == "burst" else "utility")
        skill_templates.append({
            "id": f"skill-{int(row['index'])}",
            "name": str(row["name"]),
            "skillIndex": int(row["index"]),
            "skillCodeCandidate": int(row.get("skillCodeCandidate", -1)),
            "aiCodeCandidate": int(row.get("aiCodeCandidate", -1)),
            "kind": skill_kind,
            "slotCandidate": slot,
            "modeKey": f"{int(row.get('modeA', 0))}:{int(row.get('modeB', 0))}",
            "manaCost": mana_cost,
            "cooldownBeats": cooldown_beats,
            "powerScale": round(1 + max(0, min(slot, 31)) / 30, 3),
            "projectileTemplateId": f"projectile-{int(projectile_row['index'])}",
            "effectTemplateId": f"effect-{int(effect_row['index'])}",
        })

    item_templates = []
    for row in items:
        item_kind = classify_item_kind(str(row["name"]), int(row.get("categoryCandidate", 0)))
        effect_row = find_matching_effect(effects, "heal" if item_kind in {"heal", "support"} else "burst" if item_kind == "burst" else "utility")
        projectile_row = find_matching_projectile(projectiles, "support" if item_kind in {"heal", "mana"} else "skill-window")
        item_templates.append({
            "id": f"item-{int(row['index'])}",
            "name": str(row["name"]),
            "itemIndex": int(row["index"]),
            "itemCodeCandidate": int(row.get("itemCodeCandidate", -1)),
            "categoryCandidate": int(row.get("categoryCandidate", -1)),
            "kind": item_kind,
            "cost": max(0, int(row.get("costCandidate", 0))),
            "cooldownBeats": max(3, min(10, 2 + int(row.get("aiCodeCandidate", 0)) // 4)),
            "powerScale": round(1 + max(0, int(row.get("costCandidate", 0))) / 450, 3),
            "projectileTemplateId": f"projectile-{int(projectile_row['index'])}",
            "effectTemplateId": f"effect-{int(effect_row['index'])}",
        })

    scalar_a = [int(row.get("scalarA", 0)) for row in balance_rows]
    scalar_b = [int(row.get("scalarB", 0)) for row in balance_rows]
    active_slot_density = max((len(row.get("activeSlots", [])) for row in correspondence_rows), default=4)
    resource_rules = {
        "manaCapacity": 100 + (scalar_a[0] if scalar_a else 0) * 10,
        "enemyManaCapacity": 110 + (scalar_a[1] if len(scalar_a) > 1 else 0) * 10,
        "manaRegenPerBeat": round(5 + (scalar_a[0] if scalar_a else 0) * 0.6, 3),
        "enemyManaRegenPerBeat": round(4 + (scalar_a[1] if len(scalar_a) > 1 else 0) * 0.7, 3),
        "populationBase": 4 + (scalar_a[2] if len(scalar_a) > 2 else 3),
        "enemyPopulationBase": 5 + (scalar_a[3] if len(scalar_a) > 3 else 3),
        "populationPerUpgrade": 1 + active_slot_density // 2,
        "queueCapacity": 2 + active_slot_density,
        "skillCooldownBaseBeats": 4 + (scalar_b[2] if len(scalar_b) > 2 else 1),
        "itemCooldownBaseBeats": 5 + (scalar_b[3] if len(scalar_b) > 3 else 2),
    }

    model = {
        "summary": {
            "unitTemplateCount": len(unit_templates),
            "projectileTemplateCount": len(projectile_templates),
            "effectTemplateCount": len(effect_templates),
            "skillTemplateCount": len(skill_templates),
            "itemTemplateCount": len(item_templates),
            "heroTemplateCount": len(hero_templates),
        },
        "resourceRules": resource_rules,
        "unitTemplates": unit_templates,
        "projectileTemplates": projectile_templates,
        "effectTemplates": effect_templates,
        "skillTemplates": skill_templates,
        "itemTemplates": item_templates,
        "heroTemplates": hero_templates,
        "findings": [
            "Base attack parameter bytes provide the best current data-backed source for unit power, cadence, and range.",
            "Projectile speed/range candidates and effect duration candidates now feed deterministic projectile and effect templates.",
            "Hero AI timing and priority grids are compacted into runtime cadence/weight hints rather than ignored.",
            f"Featured hero archetypes available: {len(hero_archetypes.get('archetypes', []))}.",
        ],
    }

    output_path = args.output.resolve()
    write_json(output_path, model)
    if args.web_output:
        copy_file(output_path, args.web_output.resolve())


if __name__ == "__main__":
    main()
