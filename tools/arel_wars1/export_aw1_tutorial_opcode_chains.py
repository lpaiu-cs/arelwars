#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from formats import parse_script_prefix


CHAIN_DEFINITIONS: list[dict[str, Any]] = [
    {
        "chainId": "battle-hud-guard-hp",
        "label": "guard-own-tower-hp",
        "action": "focus-own-tower-hp-loss-condition",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "battle-hud",
        "scripts": ["0004", "0404", "0804"],
        "prefixNeedle": "000d0040",
        "requiredTextTokens": ["drop", "hp", "lose"],
        "notes": [
            "The chain always appears immediately after the line that names the red tower-HP bar.",
            "Best current reading is an own-tower HP guard/loss-condition highlight.",
        ],
    },
    {
        "chainId": "battle-hud-goal-hp",
        "label": "focus-enemy-tower-hp",
        "action": "focus-enemy-tower-hp-win-condition",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "battle-hud",
        "scripts": ["0004", "0404", "0804"],
        "prefixNeedle": "000d0140",
        "requiredTextTokens": ["drop", "hp", "win"],
        "notes": [
            "The chain always follows the line that names the enemy tower HP bar.",
            "Best current reading is an enemy-tower HP / victory-condition highlight.",
        ],
    },
    {
        "chainId": "battle-hud-dispatch-arrows",
        "label": "dispatch-arrow-highlight",
        "action": "focus-dispatch-arrows",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "battle-hud",
        "scripts": ["0004", "0404", "0804"],
        "prefixNeedle": "060d0240",
        "requiredTextTokens": ["arrows", "dispatch"],
        "notes": [
            "The chain consistently appears on the battle-path explanation line.",
        ],
    },
    {
        "chainId": "battle-hud-unit-card",
        "label": "unit-card-highlight",
        "action": "focus-unit-production-card",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "battle-hud",
        "scripts": ["0004", "0404", "0804"],
        "prefixNeedle": "000d0340",
        "requiredTextTokens": ["unit", "card", "produce"],
        "notes": [
            "The chain is tied to the left-side unit card explanation in all three mirrored tutorials.",
        ],
    },
    {
        "chainId": "battle-hud-mana-bar",
        "label": "mana-bar-highlight",
        "action": "focus-mana-bar",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "battle-hud",
        "scripts": ["0004", "0404", "0804"],
        "prefixNeedle": "000d0440",
        "requiredTextTokens": ["mana", "regenerates"],
        "notes": [
            "The chain appears on the line that explains mana drain and regeneration.",
        ],
    },
    {
        "chainId": "battle-hud-hero-sortie",
        "label": "hero-sortie-button-highlight",
        "action": "focus-hero-sortie-button",
        "category": "ui-focus",
        "confidence": "medium",
        "groupId": "battle-hud",
        "scripts": ["0004", "0404", "0804"],
        "prefixNeedle": "000d0540",
        "requiredTextTokens": ["touch", "fight"],
        "notes": [
            "The parser still misreads the selector byte as cmd-05(0x40), but the raw chain is stable.",
        ],
    },
    {
        "chainId": "battle-hud-hero-return",
        "label": "hero-return-button-highlight",
        "action": "focus-return-to-tower-button",
        "category": "ui-focus",
        "confidence": "medium",
        "groupId": "battle-hud",
        "scripts": ["0004", "0404", "0804"],
        "prefixNeedle": "000d0640",
        "requiredTextTokens": ["return", "tower"],
        "notes": [
            "The parser still misreads the selector byte as cmd-06(0x40), but the raw chain is stable.",
        ],
    },
    {
        "chainId": "tower-menu-highlight",
        "label": "tower-menu-highlight",
        "action": "focus-tower-upgrade-menu",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0740",
        "requiredTextTokens": ["tower", "icons"],
        "notes": [
            "This chain is mirrored one-for-one across the Vincent, Helba, and Juno menu tutorials.",
        ],
    },
    {
        "chainId": "mana-upgrade-highlight",
        "label": "mana-upgrade-highlight",
        "action": "focus-mana-upgrade-slot",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0840",
        "requiredTextTokens": ["upgrade", "mana"],
        "notes": [
            "The chain is tied to the Potion icon and mana-regeneration explanation.",
        ],
    },
    {
        "chainId": "population-upgrade-highlight",
        "label": "population-upgrade-highlight",
        "action": "focus-population-upgrade-slot",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0940",
        "requiredTextTokens": ["population", "produce"],
        "notes": [
            "The chain is tied to the House icon and max-population warning.",
        ],
    },
    {
        "chainId": "skill-menu-highlight",
        "label": "skill-menu-highlight",
        "action": "focus-skill-menu",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0a40",
        "requiredTextTokens": ["check", "skills"],
        "notes": [
            "The chain appears on the scene pivot that introduces the Skill menu.",
        ],
    },
    {
        "chainId": "skill-slot-highlight",
        "label": "skill-slot-highlight",
        "action": "focus-skill-window-slot",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0b40",
        "requiredTextTokens": ["skill", "window"],
        "notes": [
            "This chain is tied to touching a skill inside the battle skill window.",
        ],
    },
    {
        "chainId": "item-menu-highlight",
        "label": "item-menu-highlight",
        "action": "focus-item-menu",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0c40",
        "requiredTextTokens": ["items", "equipped"],
        "notes": [
            "The chain appears directly after the line that introduces the Item menu.",
        ],
    },
    {
        "chainId": "system-menu-highlight",
        "label": "system-menu-highlight",
        "action": "focus-system-menu",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0d40",
        "requiredTextTokens": ["system", "menu"],
        "notes": [
            "The chain appears on the line about resume battling and configuration settings.",
        ],
    },
    {
        "chainId": "quest-panel-highlight",
        "label": "quest-panel-highlight",
        "action": "focus-quest-panel",
        "category": "ui-focus",
        "confidence": "high",
        "groupId": "menu-training",
        "scripts": ["0014", "0414", "0814"],
        "prefixNeedle": "060d0e40",
        "requiredTextTokens": ["quests", "rewards"],
        "notes": [
            "The chain is tied to the upper-right quest UI and reward explanation.",
        ],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export exact AW1 tutorial opcode chains from mirrored script families")
    parser.add_argument("--script-root", type=Path, required=True, help="Path to recovery/arel_wars1/decoded/zt1/assets/script_eng")
    parser.add_argument("--output", type=Path, required=True, help="Path to write AW1.tutorial_opcode_chains.json")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stage_family_id(script_stem: str) -> str:
    return script_stem[:3]


def normalized_text(text: str) -> str:
    return " ".join(text.lower().split())


def matches_definition(definition: dict[str, Any], event: dict[str, Any]) -> bool:
    prefix_hex = str(event.get("prefixHex") or "")
    if definition["prefixNeedle"] not in prefix_hex:
        return False
    text = normalized_text(str(event.get("text") or ""))
    required_tokens = definition.get("requiredTextTokens", [])
    return all(token in text for token in required_tokens)


def compact_sample(script_stem: str, event_index: int, event: dict[str, Any]) -> dict[str, Any]:
    prefix_hex = str(event.get("prefixHex") or "")
    parsed = parse_script_prefix(prefix_hex)
    return {
        "scriptStem": script_stem,
        "path": f"assets/script_eng/{script_stem}.zt1",
        "eventIndex": event_index,
        "speaker": event.get("speaker"),
        "speakerTag": event.get("speakerTag"),
        "text": event.get("text"),
        "prefixHex": prefix_hex,
        "sequence": " > ".join(command.mnemonic for command in parsed.commands),
    }


def load_hits(
    script_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    script_hits: dict[str, dict[str, Any]] = {}
    family_hits: dict[str, dict[str, Any]] = {}
    findings: list[str] = []

    chains: list[dict[str, Any]] = []
    for definition in CHAIN_DEFINITIONS:
        hits: list[dict[str, Any]] = []
        matched_scripts: set[str] = set()
        for script_stem in definition["scripts"]:
            path = script_root / f"{script_stem}.zt1.events.json"
            if not path.exists():
                continue
            events = read_json(path)
            if not isinstance(events, list):
                continue
            for event_index, raw_event in enumerate(events):
                if not isinstance(raw_event, dict) or not matches_definition(definition, raw_event):
                    continue
                hits.append(compact_sample(script_stem, event_index, raw_event))
                matched_scripts.add(script_stem)

        chain_entry = {
            "chainId": definition["chainId"],
            "label": definition["label"],
            "action": definition["action"],
            "category": definition["category"],
            "confidence": definition["confidence"],
            "groupId": definition["groupId"],
            "prefixNeedle": definition["prefixNeedle"],
            "expectedScriptStems": definition["scripts"],
            "matchedScriptStems": sorted(matched_scripts),
            "matchedFamilyIds": sorted({stage_family_id(script_stem) for script_stem in matched_scripts}),
            "requiredTextTokens": definition["requiredTextTokens"],
            "hitCount": len(hits),
            "notes": definition["notes"],
            "samples": hits[:6],
        }
        chains.append(chain_entry)

        for hit in hits:
            path = str(hit["path"])
            script_hit_entry = script_hits.setdefault(
                path,
                {
                    "path": path,
                    "scriptStem": hit["scriptStem"],
                    "familyId": stage_family_id(hit["scriptStem"]),
                    "chainIds": [],
                    "chains": [],
                },
            )
            script_hit_entry["chainIds"].append(definition["chainId"])
            script_hit_entry["chains"].append(
                {
                    "chainId": definition["chainId"],
                    "label": definition["label"],
                    "action": definition["action"],
                    "category": definition["category"],
                    "confidence": definition["confidence"],
                    "groupId": definition["groupId"],
                    "prefixNeedle": definition["prefixNeedle"],
                }
            )

            family_hit_entry = family_hits.setdefault(
                script_hit_entry["familyId"],
                {
                    "familyId": script_hit_entry["familyId"],
                    "scriptPaths": set(),
                    "chainIds": [],
                    "chains": [],
                },
            )
            family_hit_entry["scriptPaths"].add(path)
            family_hit_entry["chainIds"].append(definition["chainId"])
            family_hit_entry["chains"].append(
                {
                    "chainId": definition["chainId"],
                    "label": definition["label"],
                    "action": definition["action"],
                    "category": definition["category"],
                    "confidence": definition["confidence"],
                    "groupId": definition["groupId"],
                    "prefixNeedle": definition["prefixNeedle"],
                }
            )

    for chain in chains:
        if chain["hitCount"] == len(chain["expectedScriptStems"]):
            findings.append(
                f"{chain['chainId']} is mirrored across {len(chain['expectedScriptStems'])}/{len(chain['expectedScriptStems'])} expected English tutorial scripts via raw prefix `{chain['prefixNeedle']}`."
            )

    normalized_script_hits = []
    for entry in script_hits.values():
        unique_chain_ids = sorted(set(entry["chainIds"]))
        chains_by_id = {item["chainId"]: item for item in entry["chains"]}
        normalized_script_hits.append(
            {
                "path": entry["path"],
                "scriptStem": entry["scriptStem"],
                "familyId": entry["familyId"],
                "chainIds": unique_chain_ids,
                "chains": [chains_by_id[chain_id] for chain_id in unique_chain_ids],
            }
        )
    normalized_script_hits.sort(key=lambda item: item["path"])

    normalized_family_hits = []
    for entry in family_hits.values():
        unique_chain_ids = sorted(set(entry["chainIds"]))
        chains_by_id = {item["chainId"]: item for item in entry["chains"]}
        normalized_family_hits.append(
            {
                "familyId": entry["familyId"],
                "scriptPaths": sorted(entry["scriptPaths"]),
                "chainIds": unique_chain_ids,
                "chains": [chains_by_id[chain_id] for chain_id in unique_chain_ids],
            }
        )
    normalized_family_hits.sort(key=lambda item: item["familyId"])

    return chains, normalized_script_hits, normalized_family_hits, findings + [
        "The battle-HUD family still relies on raw prefix substrings because the current prefix parser under-reads some selector bytes as standard portrait or pose commands.",
        "The menu-training family is structurally cleaner: the same `cmd-02 > cmd-06 > selector(0x40) > cmd-02 > cmd-05` shape repeats across Vincent, Helba, and Juno tutorials.",
    ]


def main() -> None:
    args = parse_args()
    chains, script_hits, family_hits, findings = load_hits(args.script_root.resolve())

    payload = {
        "summary": {
            "chainDefinitionCount": len(CHAIN_DEFINITIONS),
            "matchedChainCount": sum(1 for chain in chains if int(chain["hitCount"]) > 0),
            "scriptHitCount": len(script_hits),
            "familyHitCount": len(family_hits),
            "totalHitCount": sum(int(chain["hitCount"]) for chain in chains),
        },
        "chains": chains,
        "scriptHits": script_hits,
        "familyHits": family_hits,
        "findings": findings,
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
