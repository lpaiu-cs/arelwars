#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a linked AW1 battle catalog from parsed GXL tables")
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
        help="Path to write the linked battle catalog JSON",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()

    heroes = read_json(parsed_dir / "XlsHero.eng.parsed.json")["records"]
    hero_ai = read_json(parsed_dir / "XlsHero_Ai.eng.parsed.json")["records"]
    hero_skills = read_json(parsed_dir / "XlsHeroSkill.eng.parsed.json")["records"]
    items = read_json(parsed_dir / "XlsItem.eng.parsed.json")["records"]
    skill_ai = read_json(parsed_dir / "XlsSkill_Ai.eng.parsed.json")["records"]
    projectiles = read_json(parsed_dir / "XlsProjectile.eng.parsed.json")["records"]
    effects = read_json(parsed_dir / "XlsEffect.eng.parsed.json")["records"]
    base_attacks = read_json(parsed_dir / "XlsBaseAttack.eng.parsed.json")["records"]
    particles = read_json(parsed_dir / "XlsParticle.eng.parsed.json")["records"]
    hero_active_skills = read_json(parsed_dir / "XlsHeroActiveSkill.eng.parsed.json")["records"]
    hero_buff_skills = read_json(parsed_dir / "XlsHeroBuffSkill.eng.parsed.json")["records"]
    hero_passive_skills = read_json(parsed_dir / "XlsHeroPassiveSkill.eng.parsed.json")["records"]
    balance_rows = read_json(parsed_dir / "XlsBalance.eng.parsed.json")["records"]
    correspondence_rows = read_json(parsed_dir / "XlsCorrespondence.eng.parsed.json")["records"]

    hero_by_id = {int(record["candidateHeroId"]): record for record in heroes}
    hero_ai_by_hero_id: dict[int, list[dict[str, Any]]] = {}
    for record in hero_ai:
        hero_ai_by_hero_id.setdefault(int(record["heroIdCandidate"]), []).append(record)

    hero_skill_by_skill_code: dict[int, list[dict[str, Any]]] = {}
    hero_skill_by_ai_code: dict[int, list[dict[str, Any]]] = {}
    hero_skill_by_name: dict[str, list[dict[str, Any]]] = {}
    for record in hero_skills:
        hero_skill_by_skill_code.setdefault(int(record["skillCodeCandidate"]), []).append(record)
        hero_skill_by_ai_code.setdefault(int(record["aiCodeCandidate"]), []).append(record)
        hero_skill_by_name.setdefault(normalize_name(str(record["name"])), []).append(record)

    item_by_item_code: dict[int, list[dict[str, Any]]] = {}
    item_by_ai_code: dict[int, list[dict[str, Any]]] = {}
    for record in items:
        item_by_item_code.setdefault(int(record["itemCodeCandidate"]), []).append(record)
        item_by_ai_code.setdefault(int(record["aiCodeCandidate"]), []).append(record)

    linked_skill_ai = []
    for record in skill_ai:
        skill_id = int(record["skillIdCandidate"])
        linked_skill_ai.append(
            {
                **record,
                "matchingHeroSkillsBySkillCode": [
                    {
                        "index": item["index"],
                        "name": item["name"],
                        "skillCodeCandidate": item["skillCodeCandidate"],
                        "aiCodeCandidate": item["aiCodeCandidate"],
                    }
                    for item in hero_skill_by_skill_code.get(skill_id, [])
                ],
                "matchingHeroSkillsByAiCode": [
                    {
                        "index": item["index"],
                        "name": item["name"],
                        "skillCodeCandidate": item["skillCodeCandidate"],
                        "aiCodeCandidate": item["aiCodeCandidate"],
                    }
                    for item in hero_skill_by_ai_code.get(skill_id, [])
                ],
                "matchingItemsByItemCode": [
                    {
                        "index": item["index"],
                        "name": item["name"],
                        "itemCodeCandidate": item["itemCodeCandidate"],
                        "categoryCandidate": item["categoryCandidate"],
                        "aiCodeCandidate": item["aiCodeCandidate"],
                    }
                    for item in item_by_item_code.get(skill_id, [])
                ],
                "matchingItemsByAiCode": [
                    {
                        "index": item["index"],
                        "name": item["name"],
                        "itemCodeCandidate": item["itemCodeCandidate"],
                        "categoryCandidate": item["categoryCandidate"],
                        "aiCodeCandidate": item["aiCodeCandidate"],
                    }
                    for item in item_by_ai_code.get(skill_id, [])
                ],
            }
        )

    linked_heroes = []
    for hero_id, hero in sorted(hero_by_id.items()):
        linked_heroes.append(
            {
                "heroId": hero_id,
                "name": hero["name"],
                "portraitId": hero["candidatePortraitId"],
                "profiles": hero_ai_by_hero_id.get(hero_id, []),
            }
        )

    linked_passive_skills = []
    for record in hero_passive_skills:
        matches = hero_skill_by_name.get(normalize_name(str(record["name"])), [])
        linked_passive_skills.append(
            {
                **record,
                "matchingHeroSkillsByName": [
                    {
                        "index": item["index"],
                        "name": item["name"],
                        "skillCodeCandidate": item["skillCodeCandidate"],
                        "aiCodeCandidate": item["aiCodeCandidate"],
                    }
                    for item in matches
                ],
            }
        )

    report = {
        "heroes": linked_heroes,
        "heroSkills": hero_skills,
        "heroActiveSkillProfiles": hero_active_skills,
        "heroBuffSkillProfiles": hero_buff_skills,
        "heroPassiveSkills": linked_passive_skills,
        "items": items,
        "skillAiProfiles": linked_skill_ai,
        "projectiles": projectiles,
        "effects": effects,
        "baseAttacks": base_attacks,
        "particles": particles,
        "balanceRows": balance_rows,
        "correspondenceRows": correspondence_rows,
        "notes": {
            "skillAiBestCurrentReading": "XlsSkill_Ai aligns more strongly with itemCodeCandidate and selected hero-skill ai codes than with raw row indices.",
            "heroAiBestCurrentReading": "XlsHero_Ai groups rows by heroIdCandidate and exposes compact priority/timing grids for runtime AI behavior.",
            "passiveSkillBestCurrentReading": "XlsHeroPassiveSkill carries named passive stat entries; several rows match XlsHeroSkill names directly and likely back the same runtime upgrade concepts.",
            "particleBestCurrentReading": "XlsParticle is a compact bridge table from gameplay ids to particle/effect families, likely consumed together with PTC.",
        },
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
