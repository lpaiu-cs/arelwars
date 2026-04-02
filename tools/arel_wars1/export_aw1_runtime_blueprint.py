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
    parser.add_argument("--stage-bindings", type=Path, required=True, help="Path to recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json")
    parser.add_argument("--tutorial-chains", type=Path, required=True, help="Path to recovery/arel_wars1/parsed_tables/AW1.tutorial_opcode_chains.json")
    parser.add_argument("--render-semantics", type=Path, required=True, help="Path to recovery/arel_wars1/parsed_tables/AW1.render_semantics.json")
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
        "commandId": str(entry.get("commandId", entry.get("label", entry["mnemonic"]))),
        "commandType": str(entry.get("commandType", "scene-transition")),
        "target": str(entry.get("target", "scene-transition")),
        "count": int(entry.get("count", 0)),
        "topArgs": signal_profile.get("topArgs", [])[:6],
        "topSequences": signal_profile.get("topSequences", [])[:4],
        "notes": list(entry.get("evidenceSummary", [])),
        "variantHints": [
            {
                "variant": hint.get("variant"),
                "label": hint.get("label"),
                "action": hint.get("action"),
                "commandId": hint.get("commandId"),
                "commandType": hint.get("commandType"),
                "target": hint.get("target"),
                "confidence": hint.get("confidence"),
                "count": hint.get("count"),
            }
            for hint in variant_hints
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
                "commandId": str(action.get("commandId", action.get("label", mnemonic))),
                "commandType": str(action.get("commandType", "scene-transition")),
                "target": str(action.get("target", "scene-transition")),
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
                        "commandId": hint.get("commandId"),
                        "commandType": hint.get("commandType"),
                        "target": hint.get("target"),
                        "confidence": hint.get("confidence"),
                    }
                    for hint in list(action.get("variantHints", []))[:2]
                ],
            }
        )
    return cues


def build_stage_map_binding(binding: dict[str, Any] | None) -> dict[str, Any] | None:
    if binding is None:
        return None
    return {
        "templateGroupId": int(binding.get("templateGroupId", -1)),
        "mapPairIndices": list(binding.get("mapPairIndices", [])),
        "preferredMapIndex": binding.get("preferredMapIndex"),
        "inlinePairBaseIndex": binding.get("inlinePairBaseIndex"),
        "inlinePairBranchIndex": binding.get("inlinePairBranchIndex"),
        "bindingType": str(binding.get("bindingType", "hard-script-ai-inline-map")),
        "bindingConfirmed": bool(binding.get("bindingConfirmed", False)),
        "scriptBindingType": str(binding.get("scriptBindingType", "family-id-exact-row-index")),
        "mapBindingType": str(binding.get("mapBindingType", "xlsai-inline-byte-pointer")),
        "storyBranch": str(binding.get("storyBranch", "primary")),
        "pairGeometrySignature": str(binding.get("pairGeometrySignature", "missing")),
        "evidenceSummary": list(binding.get("evidenceSummary", []))[:4],
    }


def build_stage_blueprints(
    stage_progression: dict[str, Any],
    stage_bindings: dict[str, Any],
    tutorial_chains: dict[str, Any],
    archetypes_by_id: dict[str, dict[str, Any]],
    opcode_actions_by_mnemonic: dict[str, dict[str, Any]],
    script_root: Path,
) -> list[dict[str, Any]]:
    bindings_by_family = {
        str(item["familyId"]): item for item in stage_bindings.get("stageBindings", []) if isinstance(item, dict)
    }
    tutorial_chains_by_family = {
        str(item["familyId"]): item for item in tutorial_chains.get("familyHits", []) if isinstance(item, dict)
    }
    stage_blueprints: list[dict[str, Any]] = []

    for family in stage_progression.get("families", []):
        if not isinstance(family, dict):
            continue
        runtime_fields = family.get("runtimeFieldCandidates") if isinstance(family, dict) else None
        binding = bindings_by_family.get(str(family["familyId"]))
        tutorial_family_hit = tutorial_chains_by_family.get(str(family["familyId"]))
        map_binding_candidate = build_stage_map_binding(binding)
        opcode_cues = summarize_family_opcodes(script_root, family, opcode_actions_by_mnemonic)
        tutorial_chain_cues = []
        if isinstance(tutorial_family_hit, dict):
            tutorial_chain_cues = [
                {
                    "chainId": item.get("chainId"),
                    "label": item.get("label"),
                    "action": item.get("action"),
                    "category": item.get("category"),
                    "confidence": item.get("confidence"),
                    "groupId": item.get("groupId"),
                    "prefixNeedle": item.get("prefixNeedle"),
                }
                for item in tutorial_family_hit.get("chains", [])
                if isinstance(item, dict)
            ]

        render_intent = None
        if isinstance(runtime_fields, dict):
            render_intent = {
                "effectIntensity": render_intensity_label(
                    int(runtime_fields.get("regionCandidate", 0)),
                    int(runtime_fields.get("tierCandidate", 0)),
                    int(runtime_fields.get("storyFlagCandidate", 0)),
                ),
                "bankRule": "flag-driven-bank-switch",
                "packedPixelHint": "Use 179 offset-normalized 47-value shade bands with a 189..199 additive highlight tail.",
            }

        opcode_labels = [str(item.get("label", "")) for item in opcode_cues]
        recommended_archetypes = recommend_archetypes(archetypes_by_id, runtime_fields, opcode_labels)

        stage_blueprints.append(
            {
                "familyId": family["familyId"],
                "aiIndex": family.get("aiIndexCandidate"),
                "scriptBindingType": binding.get("scriptBindingType") if isinstance(binding, dict) else None,
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
                "tutorialChainCues": tutorial_chain_cues,
                "recommendedArchetypeIds": recommended_archetypes,
                "renderIntent": render_intent,
            }
        )

    return stage_blueprints


def build_render_profile(
    binary_report: dict[str, Any], effect_runtime: dict[str, Any], render_semantics: dict[str, Any]
) -> dict[str, Any]:
    particle_rows = render_semantics.get("ptcEmitterSemantics", {}).get("emitters", [])
    family_representatives = render_semantics.get("ptcEmitterSemantics", {}).get("familyRepresentativeEmitters", {})
    pzx_findings = [
        finding
        for finding in binary_report.get("findings", [])
        if isinstance(finding, str)
        and ("179" in finding or "Palette index 0" in finding or "PTC" in finding)
        and "mod-47" not in finding
        and "188..199" not in finding
    ]
    packed_179 = render_semantics.get("packedPixel179", {})
    mpl_bank = render_semantics.get("mplBankSwitching", {})
    return {
        "defaultMplBankRule": {
            "label": str(mpl_bank.get("label", "flag-driven-bank-switch")),
            "selectorRule": str(mpl_bank.get("selectorRule", "flag == 0 -> bank B, flag > 0 -> bank A")),
            "notes": list(mpl_bank.get("notes", []))[:4],
        },
        "specialPackedPixelStems": [
            {
                "stem": str(packed_179.get("stem", "179")),
                "sharedMplStem": str(packed_179.get("sharedMplStem", "180")),
                "heuristic": str(packed_179.get("formula", "")),
                "confidence": "high",
                "transparentValue": int(packed_179.get("transparentValue", 0)),
                "valueOffset": int(packed_179.get("valueOffset", 1)),
                "paletteSize": int(packed_179.get("paletteSize", 47)),
                "coreBandSize": int(packed_179.get("coreBandSize", 47)),
                "coreBandCount": int(packed_179.get("coreBandCount", 4)),
                "highlightRange": list(packed_179.get("highlightRange", [189, 199])),
                "highlightBlendMode": str(packed_179.get("highlightBlendMode", "additive-tail")),
            }
        ],
        "ptcBridgeSummary": {
            "summary": effect_runtime.get("summary"),
            "familyRepresentativeEmitters": family_representatives,
            "sharedPrimaryGroups": effect_runtime.get("sharedPrimaryGroups", [])[:4],
            "sampleParticleRows": particle_rows[:6],
        },
        "findings": [*pzx_findings, *list(render_semantics.get("findings", []))[:3]],
    }


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()
    script_root = args.script_root.resolve()

    stage_progression = read_json(parsed_dir / "AW1.stage_progression.json")
    archetype_report = read_json(parsed_dir / "AW1.hero_runtime_archetypes.json")
    effect_runtime = read_json(parsed_dir / "AW1.effect_runtime_links.json")
    render_semantics = read_json(args.render_semantics.resolve())
    binary_report = read_json(args.binary_report.resolve())
    opcode_map = read_json(args.opcode_map.resolve())
    stage_bindings = read_json(args.stage_bindings.resolve())
    tutorial_chains = read_json(args.tutorial_chains.resolve())

    archetypes = archetype_report.get("archetypes", [])
    archetypes_by_id = {str(item["archetypeId"]): item for item in archetypes}
    opcode_actions = opcode_map.get("opcodeActions", [])
    opcode_actions_by_mnemonic = {
        str(item["mnemonic"]): item for item in opcode_actions if isinstance(item, dict)
    }
    stage_blueprints = build_stage_blueprints(
        stage_progression,
        stage_bindings,
        tutorial_chains,
        archetypes_by_id,
        opcode_actions_by_mnemonic,
        script_root,
    )

    heuristics = [compact_opcode(item) for item in opcode_actions if isinstance(item, dict)]

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
        "stageMapBindingCount": int(stage_bindings.get("summary", {}).get("stageBindingCount", 0)),
        "tutorialChainCount": int(tutorial_chains.get("summary", {}).get("matchedChainCount", 0)),
        "tutorialFamilyCueCount": int(tutorial_chains.get("summary", {}).get("familyHitCount", 0)),
    }
    findings = [
        "Stage blueprints now consume a hard script-family/XlsAi/map-bin binding layer instead of a scored map-pair heuristic.",
        "Opcode heuristics now come from AW1.opcode_action_map.json, which separates mnemonic-wide labels from variant-level action hints.",
        "Tutorial UI proofs now come from AW1.tutorial_opcode_chains.json, which records exact raw-prefix needles mirrored across the tutorial scripts.",
        "The runtime now reads exact script-family/XlsAi/map-bin bindings with full current script-backed coverage.",
    ]

    blueprint = {
        "summary": summary,
        "stageBlueprints": stage_blueprints,
        "opcodeHeuristics": heuristics,
        "tutorialChains": tutorial_chains.get("chains", []),
        "featuredArchetypes": featured_archetypes,
        "renderProfile": build_render_profile(binary_report, effect_runtime, render_semantics),
        "findings": findings,
    }
    write_json(args.output.resolve(), blueprint)
    if args.web_output is not None:
        copy_file(args.output.resolve(), args.web_output.resolve())


if __name__ == "__main__":
    main()
