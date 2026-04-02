#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_heuristics import map_group_for_variant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export structured AW1 stage-map proof candidates from current binding reports"
    )
    parser.add_argument(
        "--stage-progression",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.stage_progression.json",
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
        help="Path to write AW1.stage_map_proofs.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def rounded(value: float) -> float:
    return round(value, 3)


def confidence_label(score: float) -> str:
    if score >= 0.9:
        return "strong-heuristic"
    if score >= 0.72:
        return "supported-heuristic"
    return "weak-heuristic"


def geometry_signature(headers: list[dict[str, Any]]) -> str:
    if not headers:
        return "missing"
    return "/".join(
        f"{int(item['layerCount'])}L-{int(item['width'])}x{int(item['height'])}-v{int(item['variantOrGroup'])}"
        for item in headers
    )


def compute_pair_score(runtime_fields: dict[str, Any], group: dict[str, Any] | None) -> tuple[float, list[str]]:
    if group is None:
        return 0.18, ["template-group missing from current candidate table"]

    score = 0.0
    evidence: list[str] = []
    variant = int(runtime_fields.get("variantCandidate", 0))
    region = int(runtime_fields.get("regionCandidate", 0))
    story_flag = int(runtime_fields.get("storyFlagCandidate", 0))
    pair = list(group.get("candidateMapBinPair", []))
    headers = list(group.get("candidateMapHeaders", []))

    score += 0.34
    evidence.append("variantCandidate resolves to a stable template group under the current 1->0,2->1,3->2,4->3,5/6->4 rule")

    if len(pair) == 2:
        score += 0.18
        evidence.append("candidate map pair is concrete and contains exactly two map bins")
    else:
        evidence.append("candidate map pair is incomplete")

    if bool(group.get("hasNonZeroMetric")):
        score += 0.16
        evidence.append("paired XlsMap rows carry non-zero metrics instead of placeholder zeros")

    if story_flag in {0, 1} and len(pair) == 2:
        score += 0.1
        evidence.append("storyFlagCandidate behaves like a branch selector inside the pair")

    if headers:
        layer_counts = {int(item.get("layerCount", 0)) for item in headers}
        dimensions = {(int(item.get("width", 0)), int(item.get("height", 0))) for item in headers}
        if len(layer_counts) == 1 and len(dimensions) == 1:
            score += 0.12
            evidence.append("pair shares one geometry signature, which fits an intro/outro branch on the same battlefield")
        elif len(dimensions) == 1:
            score += 0.07
            evidence.append("pair shares map dimensions but changes layer counts, suggesting a presentation branch rather than a different stage")

        max_layer_count = max(layer_counts)
        if variant >= 5 and max_layer_count >= 4:
            score += 0.07
            evidence.append("late-game variant lands on the only heavier 4-layer pair")
        elif variant <= 4 and max_layer_count <= 3:
            score += 0.05
            evidence.append("early/mid variant lands on a lighter 2-3 layer pair")

        if region >= 9 and max_layer_count >= 4:
            score += 0.03
            evidence.append("late region bucket aligns with the heaviest map pair")

    return min(score, 0.97), evidence


def stage_bucket(runtime_fields: dict[str, Any]) -> str:
    region = int(runtime_fields.get("regionCandidate", 0))
    variant = int(runtime_fields.get("variantCandidate", 0))
    story_flag = int(runtime_fields.get("storyFlagCandidate", 0))
    tier = int(runtime_fields.get("tierCandidate", 0))
    return f"t{tier}-r{region}-v{variant}-s{story_flag}"


def main() -> None:
    args = parse_args()
    stage_progression = read_json(args.stage_progression.resolve())
    map_binding = read_json(args.map_binding.resolve())

    group_candidates = {
        int(group["groupId"]): group for group in map_binding["mapGroupSummary"]["groupCandidates"]
    }

    group_profiles: list[dict[str, Any]] = []
    for group_id, group in sorted(group_candidates.items()):
        headers = list(group.get("candidateMapHeaders", []))
        score = 0.18
        evidence: list[str] = []
        if bool(group.get("hasNonZeroMetric")):
            score += 0.34
            evidence.append("XlsMap group is active and non-zero")
        if len(group.get("candidateMapBinPair", [])) == 2:
            score += 0.22
            evidence.append("group resolves to a concrete two-map bin pair")
        if headers:
            score += 0.12
            evidence.append("pair has readable map headers")
            if len({(int(item["width"]), int(item["height"])) for item in headers}) == 1:
                score += 0.1
                evidence.append("pair shares one map footprint")
        group_profiles.append(
            {
                "groupId": group_id,
                "candidateMapBinPair": list(group.get("candidateMapBinPair", [])),
                "hasNonZeroMetric": bool(group.get("hasNonZeroMetric")),
                "pairGeometrySignature": geometry_signature(headers),
                "candidateHeaders": headers,
                "groupSupportScore": rounded(min(score, 0.96)),
                "evidenceSummary": evidence,
            }
        )

    stage_proofs: list[dict[str, Any]] = []
    for family in stage_progression.get("families", []):
        if not isinstance(family, dict):
            continue
        runtime_fields = family.get("runtimeFieldCandidates")
        if not isinstance(runtime_fields, dict):
            continue
        variant = int(runtime_fields.get("variantCandidate", 0))
        story_flag = int(runtime_fields.get("storyFlagCandidate", 0))
        group_id = map_group_for_variant(variant)
        group = group_candidates.get(group_id)
        pair = list(group.get("candidateMapBinPair", [])) if group else []
        preferred_map = None
        if len(pair) == 2:
            preferred_map = pair[1] if story_flag == 1 else pair[0]
        score, evidence = compute_pair_score(runtime_fields, group)
        stage_proofs.append(
            {
                "familyId": family.get("familyId"),
                "aiIndexCandidate": family.get("aiIndexCandidate"),
                "title": family.get("aiTitleCandidate"),
                "runtimeFields": runtime_fields,
                "stageBucket": stage_bucket(runtime_fields),
                "templateGroupId": group_id,
                "candidateMapBinPair": pair,
                "preferredMapIndex": preferred_map,
                "storyBranch": "secondary" if story_flag == 1 else "primary",
                "proofScore": rounded(score),
                "confidence": confidence_label(score),
                "proofType": "variant-template-plus-story-branch",
                "pairGeometrySignature": geometry_signature(list(group.get("candidateMapHeaders", [])) if group else []),
                "candidateHeaders": list(group.get("candidateMapHeaders", [])) if group else [],
                "evidenceSummary": evidence,
            }
        )

    stage_proofs.sort(key=lambda item: str(item["familyId"]))
    confidence_histogram: dict[str, int] = {}
    for entry in stage_proofs:
        confidence_histogram[entry["confidence"]] = confidence_histogram.get(entry["confidence"], 0) + 1

    findings = [
        "Stage-map proof export now exposes a support score and evidence list instead of only a bare preferred map index heuristic.",
        "The strongest current rule remains variantCandidate -> templateGroup and storyFlagCandidate -> primary/secondary branch inside the pair.",
        "This is still not a hard runtime pointer, but it is now an explicit proof-candidate layer that can be replaced as soon as a direct table reference is found.",
    ]
    payload = {
        "summary": {
            "stageProofCount": len(stage_proofs),
            "groupProfileCount": len(group_profiles),
            "confidenceHistogram": confidence_histogram,
        },
        "globalRules": {
            "variantToTemplateGroup": {
                "1": 0,
                "2": 1,
                "3": 2,
                "4": 3,
                "5": 4,
                "6": 4,
            },
            "storyFlagToPairBranch": {
                "0": "primary",
                "1": "secondary",
            },
        },
        "groupProfiles": group_profiles,
        "stageProofs": stage_proofs,
        "findings": findings,
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
