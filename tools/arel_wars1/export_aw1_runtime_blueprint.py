#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from typing import Any

from formats import parse_script_prefix


OPCODE_HEURISTIC_OVERRIDES: dict[str, dict[str, Any]] = {
    "cmd-02": {
        "label": "tutorial-focus",
        "category": "ui-focus",
        "confidence": "medium",
        "notes": [
            "Clusters around tutorial scripts and explicit touch or HUD instructions.",
            "Best current reading is a guided focus or highlight opcode.",
        ],
    },
    "cmd-05": {
        "label": "dialogue-pose-helper",
        "category": "presentation",
        "confidence": "medium",
        "notes": [
            "Usually follows portrait selection and is usually closed by cmd-08.",
            "Best current reading is a dialogue pose, mouth, or focus helper.",
        ],
    },
    "cmd-06": {
        "label": "tutorial-focus-submode",
        "category": "ui-focus",
        "confidence": "medium",
        "notes": [
            "Appears heavily in tutorial scripts with arrows, cards, and menu references.",
            "Best current reading is a submode or target selector for tutorial focus.",
        ],
    },
    "cmd-08": {
        "label": "presentation-close",
        "category": "presentation",
        "confidence": "medium",
        "notes": [
            "Frequently terminates pose-helper sequences that include cmd-05.",
            "Best current reading is a close or release presentation command.",
        ],
    },
    "cmd-0a": {
        "label": "emphasis-start",
        "category": "emphasis",
        "confidence": "medium",
        "notes": [
            "Often clusters with cmd-0b around surprise or impact lines.",
            "Best current reading is emphasis, shake, or dramatic-start markup.",
        ],
    },
    "cmd-0b": {
        "label": "emphasis-end",
        "category": "emphasis",
        "confidence": "medium",
        "notes": [
            "Pairs strongly with cmd-0a and appears on shocked or shouted lines.",
            "Best current reading is a complementary emphasis or shock helper.",
        ],
    },
    "cmd-0c": {
        "label": "tutorial-target-anchor",
        "category": "ui-focus",
        "confidence": "medium",
        "notes": [
            "Appears in tutorial and scripted explanation contexts with cmd-02 and cmd-00.",
            "Best current reading is a tutorial anchor or focus target opcode.",
        ],
    },
    "cmd-10": {
        "label": "scene-entry-preset",
        "category": "scene-bootstrap",
        "confidence": "low",
        "notes": [
            "Frequently appears at scene openings before portrait or pose helpers.",
            "Best current reading is a scene-entry layout or camera preset.",
        ],
    },
    "cmd-18": {
        "label": "scene-entry-preset",
        "category": "scene-bootstrap",
        "confidence": "low",
        "notes": [
            "Clusters with scene starts and portrait setup.",
            "Best current reading is another scene-entry preset variant.",
        ],
    },
    "cmd-43": {
        "label": "tutorial-bootstrap",
        "category": "scene-bootstrap",
        "confidence": "medium",
        "notes": [
            "Appears at tutorial openings before chained focus helpers.",
            "Best current reading is a tutorial bootstrap or narrator mode switch.",
        ],
    },
}

FEATURED_ARCHETYPES = [
    "dispatch",
    "tower-defense",
    "naturalhealing",
    "recall",
    "hpup",
    "returntonature",
    "manawall",
    "armageddon",
    "managain",
    "special-stun",
    "special-smoke",
    "special-armageddonbuff",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export an engine-facing AW1 runtime blueprint that merges stage, opcode, archetype, and render findings"
    )
    parser.add_argument("--parsed-dir", type=Path, required=True, help="Path to recovery/arel_wars1/parsed_tables")
    parser.add_argument("--binary-report", type=Path, required=True, help="Path to recovery/arel_wars1/binary_asset_report.json")
    parser.add_argument("--script-report", type=Path, required=True, help="Path to recovery/arel_wars1/script_event_report.json")
    parser.add_argument("--script-root", type=Path, required=True, help="Path to recovery/arel_wars1/decoded/zt1/assets/script_eng")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the local blueprint json")
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


def map_group_for_variant(variant_candidate: int) -> int:
    if variant_candidate <= 1:
        return 0
    if variant_candidate == 2:
        return 1
    if variant_candidate == 3:
        return 2
    if variant_candidate == 4:
        return 3
    return 4


def render_intensity_label(region_candidate: int, tier_candidate: int, story_flag_candidate: int) -> str:
    if tier_candidate >= 50 or region_candidate >= 9:
        return "high"
    if story_flag_candidate == 1:
        return "medium"
    return "low"


def recommend_archetypes(
    archetypes_by_id: dict[str, dict[str, Any]],
    runtime_fields: dict[str, Any] | None,
    opcode_labels: list[str],
) -> list[str]:
    recommendations: list[str] = ["dispatch"]
    if not runtime_fields:
        return [item for item in recommendations if item in archetypes_by_id]

    region = int(runtime_fields.get("regionCandidate", 0))
    variant = int(runtime_fields.get("variantCandidate", 0))
    story_flag = int(runtime_fields.get("storyFlagCandidate", 0))
    tier = int(runtime_fields.get("tierCandidate", 0))

    if variant in {1, 2, 3}:
        recommendations.append("tower-defense")
    if variant in {1, 2}:
        recommendations.append("hpup")
    if story_flag == 1:
        recommendations.append("naturalhealing")
    if region >= 6:
        recommendations.append("recall")
        recommendations.append("returntonature")
    if region >= 9 or variant >= 4:
        recommendations.append("manawall")
    if tier >= 20 or variant >= 5:
        recommendations.append("armageddon")
    if region >= 9:
        recommendations.append("managain")
    if any(label in {"tutorial-focus", "tutorial-bootstrap"} for label in opcode_labels):
        recommendations.append("special-stun")

    seen: set[str] = set()
    filtered: list[str] = []
    for archetype_id in recommendations:
        if archetype_id not in archetypes_by_id or archetype_id in seen:
            continue
        seen.add(archetype_id)
        filtered.append(archetype_id)
    return filtered


def compact_opcode(profile: dict[str, Any]) -> dict[str, Any]:
    mnemonic = str(profile["mnemonic"])
    override = OPCODE_HEURISTIC_OVERRIDES.get(mnemonic, {})
    return {
        "mnemonic": mnemonic,
        "label": override.get("label", mnemonic),
        "category": override.get("category", "unknown"),
        "confidence": override.get("confidence", "low"),
        "count": int(profile["count"]),
        "topArgs": profile.get("topArgs", [])[:6],
        "topSequences": profile.get("topSequences", [])[:4],
        "notes": override.get("notes", []),
    }


def summarize_family_opcodes(script_root: Path, family: dict[str, Any]) -> list[dict[str, Any]]:
    opcode_counter: Counter[str] = Counter()
    for script_name in family.get("scriptFiles", []):
        path = script_root / str(script_name)
        if not path.exists():
            continue
        events = read_json(path)
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            prefix_hex = str(event.get("prefixHex") or "")
            if not prefix_hex:
                continue
            parsed = parse_script_prefix(prefix_hex)
            for command in parsed.commands:
                if command.mnemonic.startswith("cmd-"):
                    opcode_counter.update([command.mnemonic])

    return [
        {"mnemonic": mnemonic, "count": count, **OPCODE_HEURISTIC_OVERRIDES.get(mnemonic, {})}
        for mnemonic, count in opcode_counter.most_common(6)
    ]


def build_stage_blueprints(
    stage_progression: dict[str, Any],
    map_binding: dict[str, Any],
    archetypes_by_id: dict[str, dict[str, Any]],
    script_root: Path,
) -> list[dict[str, Any]]:
    group_candidates = {
        int(group["groupId"]): group for group in map_binding["mapGroupSummary"]["groupCandidates"]
    }
    stage_blueprints: list[dict[str, Any]] = []

    for family in stage_progression.get("families", []):
        runtime_fields = family.get("runtimeFieldCandidates") if isinstance(family, dict) else None
        map_binding_candidate = None
        render_intent = None
        opcode_cues = summarize_family_opcodes(script_root, family)

        if isinstance(runtime_fields, dict):
            variant = int(runtime_fields.get("variantCandidate", 0))
            story_flag = int(runtime_fields.get("storyFlagCandidate", 0))
            group_id = map_group_for_variant(variant)
            group = group_candidates.get(group_id)
            pair = list(group["candidateMapBinPair"]) if group else []
            preferred_map_index = None
            confidence = "low"
            rationale = "No concrete map pointer yet; this is the strongest current variant-to-template heuristic."
            if pair:
                preferred_map_index = pair[1] if story_flag == 1 and len(pair) > 1 else pair[0]
                confidence = "medium" if bool(group and group.get("hasNonZeroMetric")) else "low"
            map_binding_candidate = {
                "templateGroupId": group_id,
                "mapPairIndices": pair,
                "preferredMapIndexHeuristic": preferred_map_index,
                "confidence": confidence,
                "rationale": rationale,
            }
            render_intent = {
                "effectIntensity": render_intensity_label(
                    int(runtime_fields.get("regionCandidate", 0)),
                    int(runtime_fields.get("tierCandidate", 0)),
                    int(runtime_fields.get("storyFlagCandidate", 0)),
                ),
                "bankRule": "default-bank-b-flagged-bank-a",
                "packedPixelHint": "Use 179 shade-band rule when paired with stem 179.",
            }

        opcode_labels = [str(item.get("label", "")) for item in opcode_cues]
        recommended_archetypes = recommend_archetypes(archetypes_by_id, runtime_fields, opcode_labels)

        stage_blueprints.append(
            {
                "familyId": family["familyId"],
                "aiIndexCandidate": family.get("aiIndexCandidate"),
                "title": family.get("aiTitleCandidate"),
                "rewardText": family.get("aiRewardCandidate"),
                "hintText": family.get("aiHintCandidate"),
                "scriptFiles": family.get("scriptFiles", []),
                "scriptFileCount": family.get("scriptFileCount"),
                "eventCount": family.get("eventCount"),
                "topSpeakers": family.get("topSpeakers", []),
                "runtimeFields": runtime_fields,
                "mapBinding": map_binding_candidate,
                "opcodeCues": opcode_cues,
                "recommendedArchetypeIds": recommended_archetypes,
                "renderIntent": render_intent,
            }
        )

    return stage_blueprints


def build_render_profile(
    binary_report: dict[str, Any], effect_runtime: dict[str, Any]
) -> dict[str, Any]:
    particle_rows = effect_runtime.get("particleRows", [])
    shared_primary_groups = effect_runtime.get("sharedPrimaryGroups", [])
    pzx_findings = [
        finding
        for finding in binary_report.get("findings", [])
        if isinstance(finding, str) and ("179" in finding or "Palette index 0" in finding or "PTC" in finding)
    ]
    return {
        "defaultMplBankRule": {
            "label": "default-bank-b-flagged-bank-a",
            "notes": [
                "Bank B is the default visible sprite palette for tested stems.",
                "Flagged frame items are best explained as bank-A overlays.",
                "Palette index 0 behaves like transparency more reliably than a zero RGB565 word check.",
            ],
        },
        "specialPackedPixelStems": [
            {
                "stem": "179",
                "sharedMplStem": "180",
                "heuristic": "shadeBand*47 + paletteResidue with 188..199 as highlight tail",
                "confidence": "medium",
            }
        ],
        "ptcBridgeSummary": {
            "summary": effect_runtime.get("summary"),
            "sharedPrimaryGroups": shared_primary_groups[:4],
            "sampleParticleRows": particle_rows[:6],
        },
        "findings": pzx_findings,
    }


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()
    script_root = args.script_root.resolve()

    stage_progression = read_json(parsed_dir / "AW1.stage_progression.json")
    map_binding = read_json(parsed_dir / "AW1.map_binding_candidates.json")
    archetype_report = read_json(parsed_dir / "AW1.hero_runtime_archetypes.json")
    effect_runtime = read_json(parsed_dir / "AW1.effect_runtime_links.json")
    binary_report = read_json(args.binary_report.resolve())
    script_report = read_json(args.script_report.resolve())

    archetypes = archetype_report.get("archetypes", [])
    archetypes_by_id = {str(item["archetypeId"]): item for item in archetypes}
    stage_blueprints = build_stage_blueprints(stage_progression, map_binding, archetypes_by_id, script_root)

    opcode_profiles = script_report.get("unknownCommandProfiles", [])
    heuristics = []
    for mnemonic in OPCODE_HEURISTIC_OVERRIDES:
        profile = next((item for item in opcode_profiles if item.get("mnemonic") == mnemonic), None)
        if profile is None:
            continue
        heuristics.append(compact_opcode(profile))

    featured_archetypes = [
        archetypes_by_id[archetype_id]
        for archetype_id in FEATURED_ARCHETYPES
        if archetype_id in archetypes_by_id
    ]

    summary = {
        "stageBlueprintCount": len(stage_blueprints),
        "archetypeCount": len(archetypes),
        "featuredArchetypeCount": len(featured_archetypes),
        "opcodeHeuristicCount": len(heuristics),
    }
    findings = [
        "Stage blueprints now carry map-template candidates, opcode cue summaries, and recommended hero archetypes in one engine-facing export.",
        "The map binding still remains heuristic, but the strongest current rule is variantCandidate -> template group with storyFlag selecting the preferred map inside the pair.",
        "Opcode heuristics, hero runtime archetypes, and render findings are now unified so the Phaser runtime can consume them without reading reverse-engineering reports directly.",
    ]

    blueprint = {
        "summary": summary,
        "stageBlueprints": stage_blueprints,
        "opcodeHeuristics": heuristics,
        "featuredArchetypes": featured_archetypes,
        "renderProfile": build_render_profile(binary_report, effect_runtime),
        "findings": findings,
    }
    write_json(args.output.resolve(), blueprint)
    if args.web_output is not None:
        copy_file(args.output.resolve(), args.web_output.resolve())


if __name__ == "__main__":
    main()
