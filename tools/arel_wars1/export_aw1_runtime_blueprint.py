#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from typing import Any

from formats import parse_script_prefix
from runtime_heuristics import FEATURED_ARCHETYPES, RUNTIME_FEATURED_MNEMONICS, render_intensity_label


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export an engine-facing AW1 runtime blueprint that merges stage, opcode, archetype, and render findings"
    )
    parser.add_argument("--parsed-dir", type=Path, required=True, help="Path to recovery/arel_wars1/parsed_tables")
    parser.add_argument("--binary-report", type=Path, required=True, help="Path to recovery/arel_wars1/binary_asset_report.json")
    parser.add_argument("--script-root", type=Path, required=True, help="Path to recovery/arel_wars1/decoded/zt1/assets/script_eng")
    parser.add_argument("--opcode-map", type=Path, required=True, help="Path to recovery/arel_wars1/parsed_tables/AW1.opcode_action_map.json")
    parser.add_argument("--stage-map-proofs", type=Path, required=True, help="Path to recovery/arel_wars1/parsed_tables/AW1.stage_map_proofs.json")
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
    if any(label in {"tutorial-focus-anchor", "tutorial-bootstrap"} for label in opcode_labels):
        recommendations.append("special-stun")

    seen: set[str] = set()
    filtered: list[str] = []
    for archetype_id in recommendations:
        if archetype_id not in archetypes_by_id or archetype_id in seen:
            continue
        seen.add(archetype_id)
        filtered.append(archetype_id)
    return filtered


def compact_opcode(entry: dict[str, Any]) -> dict[str, Any]:
    signal_profile = entry.get("signalProfile", {})
    variant_hints = entry.get("variantHints", [])
    return {
        "mnemonic": str(entry["mnemonic"]),
        "label": str(entry.get("label", entry["mnemonic"])),
        "action": str(entry.get("action", "unknown-runtime-action")),
        "category": str(entry.get("category", "unknown")),
        "confidence": str(entry.get("confidence", "low")),
        "count": int(entry.get("count", 0)),
        "topArgs": signal_profile.get("topArgs", [])[:6],
        "topSequences": signal_profile.get("topSequences", [])[:4],
        "notes": list(entry.get("evidenceSummary", [])),
        "variantHints": [
            {
                "variant": hint.get("variant"),
                "label": hint.get("label"),
                "action": hint.get("action"),
                "confidence": hint.get("confidence"),
                "count": hint.get("count"),
            }
            for hint in variant_hints[:4]
        ],
    }


def summarize_family_opcodes(
    script_root: Path,
    family: dict[str, Any],
    opcode_actions_by_mnemonic: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
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

    cues: list[dict[str, Any]] = []
    for mnemonic, count in opcode_counter.most_common(6):
        action = opcode_actions_by_mnemonic.get(mnemonic, {})
        signal_profile = action.get("signalProfile", {})
        cues.append(
            {
                "mnemonic": mnemonic,
                "label": str(action.get("label", mnemonic)),
                "action": str(action.get("action", "unknown-runtime-action")),
                "category": str(action.get("category", "unknown")),
                "confidence": str(action.get("confidence", "low")),
                "count": count,
                "familyCount": count,
                "topArgs": signal_profile.get("topArgs", [])[:4],
                "topSequences": signal_profile.get("topSequences", [])[:3],
                "notes": list(action.get("evidenceSummary", []))[:3],
                "variantHints": [
                    {
                        "variant": hint.get("variant"),
                        "label": hint.get("label"),
                        "action": hint.get("action"),
                        "confidence": hint.get("confidence"),
                    }
                    for hint in list(action.get("variantHints", []))[:2]
                ],
            }
        )
    return cues


def build_stage_map_binding(proof: dict[str, Any] | None) -> dict[str, Any] | None:
    if proof is None:
        return None
    return {
        "templateGroupId": int(proof.get("templateGroupId", -1)),
        "mapPairIndices": list(proof.get("candidateMapBinPair", [])),
        "preferredMapIndexHeuristic": proof.get("preferredMapIndex"),
        "inlinePairBaseIndexCandidate": proof.get("inlinePairBaseIndexCandidate"),
        "inlinePairBranchIndexCandidate": proof.get("inlinePairBranchIndexCandidate"),
        "inlinePreferredMapIndexCandidate": proof.get("inlinePreferredMapIndexCandidate"),
        "confidence": str(proof.get("confidence", "weak-heuristic")),
        "proofScore": float(proof.get("proofScore", 0.0)),
        "proofType": str(proof.get("proofType", "variant-template-plus-story-branch")),
        "storyBranch": str(proof.get("storyBranch", "primary")),
        "pairGeometrySignature": str(proof.get("pairGeometrySignature", "missing")),
        "evidenceSummary": list(proof.get("evidenceSummary", []))[:4],
    }


def build_stage_blueprints(
    stage_progression: dict[str, Any],
    stage_map_proofs: dict[str, Any],
    archetypes_by_id: dict[str, dict[str, Any]],
    opcode_actions_by_mnemonic: dict[str, dict[str, Any]],
    script_root: Path,
) -> list[dict[str, Any]]:
    proofs_by_family = {
        str(item["familyId"]): item for item in stage_map_proofs.get("stageProofs", []) if isinstance(item, dict)
    }
    stage_blueprints: list[dict[str, Any]] = []

    for family in stage_progression.get("families", []):
        if not isinstance(family, dict):
            continue
        runtime_fields = family.get("runtimeFieldCandidates") if isinstance(family, dict) else None
        proof = proofs_by_family.get(str(family["familyId"]))
        map_binding_candidate = build_stage_map_binding(proof)
        opcode_cues = summarize_family_opcodes(script_root, family, opcode_actions_by_mnemonic)

        render_intent = None
        if isinstance(runtime_fields, dict):
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
    archetype_report = read_json(parsed_dir / "AW1.hero_runtime_archetypes.json")
    effect_runtime = read_json(parsed_dir / "AW1.effect_runtime_links.json")
    binary_report = read_json(args.binary_report.resolve())
    opcode_map = read_json(args.opcode_map.resolve())
    stage_map_proofs = read_json(args.stage_map_proofs.resolve())

    archetypes = archetype_report.get("archetypes", [])
    archetypes_by_id = {str(item["archetypeId"]): item for item in archetypes}
    opcode_actions = opcode_map.get("opcodeActions", [])
    opcode_actions_by_mnemonic = {
        str(item["mnemonic"]): item for item in opcode_actions if isinstance(item, dict)
    }
    stage_blueprints = build_stage_blueprints(
        stage_progression,
        stage_map_proofs,
        archetypes_by_id,
        opcode_actions_by_mnemonic,
        script_root,
    )

    heuristics = [
        compact_opcode(opcode_actions_by_mnemonic[mnemonic])
        for mnemonic in RUNTIME_FEATURED_MNEMONICS
        if mnemonic in opcode_actions_by_mnemonic
    ]

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
        "stageMapProofCount": int(stage_map_proofs.get("summary", {}).get("stageProofCount", 0)),
    }
    findings = [
        "Stage blueprints now consume an explicit stage-map proof layer instead of baking the map-pair heuristic directly into the exporter.",
        "Opcode heuristics now come from AW1.opcode_action_map.json, which separates mnemonic-wide labels from variant-level action hints.",
        "The runtime still uses heuristic stage-map bindings, but proof scores and evidence summaries are now exported alongside the preferred map index.",
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
