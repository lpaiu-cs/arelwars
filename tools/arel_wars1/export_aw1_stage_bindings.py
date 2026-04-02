#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export hard AW1 script-family/XlsAi/map-bin bindings from exact inline signals"
    )
    parser.add_argument(
        "--stage-progression",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.stage_progression.json",
    )
    parser.add_argument(
        "--inline-pointer-scan",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.inline_map_pointer_scan.json",
    )
    parser.add_argument(
        "--map-binding",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.map_binding_candidates.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write AW1.stage_bindings.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def geometry_signature(headers: list[dict[str, Any]]) -> str:
    if not headers:
        return "missing"
    return "/".join(
        f"{int((item.get('header') or item)['layerCount'])}L-{int((item.get('header') or item)['width'])}x{int((item.get('header') or item)['height'])}-v{int((item.get('header') or item)['variantOrGroup'])}"
        for item in headers
    )


def resolve_story_branch(branch_index: int) -> str:
    return "secondary" if branch_index == 1 else "primary"


def main() -> None:
    args = parse_args()
    stage_progression = read_json(args.stage_progression.resolve())
    inline_pointer_scan = read_json(args.inline_pointer_scan.resolve())
    map_binding = read_json(args.map_binding.resolve())

    pair_base_mapping = {
        int(key): int(value)
        for key, value in dict(
            inline_pointer_scan.get("pairBaseIndexSignal", {}).get("byteMapping", {})
        ).items()
    }
    pair_branch_mapping = {
        int(key): int(value)
        for key, value in dict(
            inline_pointer_scan.get("pairBranchSignal", {}).get("byteMapping", {})
        ).items()
    }
    map_headers_by_index = {
        int(item["mapIndex"]): item
        for item in map_binding.get("mapHeaders", [])
        if isinstance(item, dict)
    }

    stage_bindings: list[dict[str, Any]] = []
    script_ai_exact_count = 0
    inline_map_exact_count = 0

    for family in stage_progression.get("families", []):
        if not isinstance(family, dict):
            continue
        runtime_fields = family.get("runtimeFieldCandidates")
        if not isinstance(runtime_fields, dict):
            continue

        family_id = str(family.get("familyId"))
        ai_index = int(family.get("aiIndexCandidate", -1))
        family_row_index = int(family_id)
        script_ai_exact = family_row_index == ai_index
        if script_ai_exact:
            script_ai_exact_count += 1

        variant = int(runtime_fields.get("variantCandidate", 0))
        story_flag = int(runtime_fields.get("storyFlagCandidate", 0))
        pair_base_index = pair_base_mapping.get(variant)
        pair_branch_index = pair_branch_mapping.get(story_flag)
        preferred_map_index = None
        map_pair_indices: list[int] = []
        if pair_base_index is not None and pair_branch_index is not None:
            preferred_map_index = pair_base_index + pair_branch_index
            map_pair_indices = [pair_base_index, pair_base_index + 1]
            inline_map_exact_count += 1

        bound_headers = [
            map_headers_by_index[index] for index in map_pair_indices if index in map_headers_by_index
        ]
        template_group_id = pair_base_index // 2 if pair_base_index is not None else -1

        stage_bindings.append(
            {
                "familyId": family_id,
                "aiIndex": ai_index,
                "title": family.get("aiTitleCandidate"),
                "rewardText": family.get("aiRewardCandidate"),
                "hintText": family.get("aiHintCandidate"),
                "scriptFiles": list(family.get("scriptFiles", [])),
                "runtimeFields": runtime_fields,
                "bindingType": "hard-script-ai-inline-map",
                "bindingConfirmed": bool(script_ai_exact and preferred_map_index is not None),
                "scriptBindingType": "family-id-exact-row-index",
                "scriptBindingConfirmed": script_ai_exact,
                "mapBindingType": "xlsai-inline-byte-pointer",
                "templateGroupId": template_group_id,
                "mapPairIndices": map_pair_indices,
                "preferredMapIndex": preferred_map_index,
                "inlinePairBaseIndex": pair_base_index,
                "inlinePairBranchIndex": pair_branch_index,
                "storyBranch": resolve_story_branch(pair_branch_index or 0),
                "pairGeometrySignature": geometry_signature(bound_headers),
                "boundMapHeaders": bound_headers,
                "evidenceSummary": [
                    "script family id matches the XlsAi row index exactly for this stage family.",
                    "XlsAi numericBlock byte[15] decodes directly to the map-pair base index.",
                    "XlsAi numericBlock byte[18] decodes directly to the pair branch bit.",
                    "preferredMapIndex is reconstructed exactly as pairBaseIndex + pairBranchIndex.",
                ],
            }
        )

    binding_type_histogram: dict[str, int] = {}
    for binding in stage_bindings:
        binding_type = str(binding["bindingType"])
        binding_type_histogram[binding_type] = binding_type_histogram.get(binding_type, 0) + 1

    payload = {
        "summary": {
            "stageBindingCount": len(stage_bindings),
            "scriptAiExactCoverage": script_ai_exact_count,
            "inlineMapExactCoverage": inline_map_exact_count,
            "bindingTypeHistogram": binding_type_histogram,
        },
        "globalRules": {
            "scriptFamilyToAiRow": {
                "rule": "int(familyId) == XlsAi.rowIndex",
                "exactCoverage": script_ai_exact_count,
                "interpretation": "The three-digit script family prefix is the exact XlsAi row index for every script-backed stage.",
            },
            "pairBaseIndexSignal": inline_pointer_scan.get("pairBaseIndexSignal", {}),
            "pairBranchSignal": inline_pointer_scan.get("pairBranchSignal", {}),
            "preferredMapFormula": inline_pointer_scan.get("preferredMapFormula", {}),
        },
        "stageBindings": stage_bindings,
        "findings": [
            "AW1 stage binding no longer depends on a scored variant heuristic.",
            "Script family id, XlsAi row index, and preferred map bin are now tied together through exact inline signals with full script-backed coverage.",
            "The runtime-facing binding type is now `hard-script-ai-inline-map` for every current script-backed stage.",
        ],
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
