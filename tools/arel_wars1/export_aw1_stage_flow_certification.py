#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export AW1 full stage-flow certification report from the side-by-side comparator"
    )
    parser.add_argument("--reference-bundle", type=Path, required=True, help="Path to AW1.original_reference_bundle.json")
    parser.add_argument("--side-by-side", type=Path, required=True, help="Path to AW1.side_by_side_report.json")
    parser.add_argument("--candidate-suite", type=Path, required=True, help="Path to AW1.candidate_replay_suite.json")
    parser.add_argument("--reference-suite", type=Path, required=True, help="Path to AW1.golden_capture_suite.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to AW1.stage_flow_certification.json")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def by_key(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get(key)): item
        for item in items
        if isinstance(item, dict) and item.get(key) is not None
    }


def comparison_buckets(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        buckets.setdefault(str(record.get("category") or "unknown"), []).append(record)
    return buckets


def main() -> None:
    args = parse_args()
    reference_bundle = read_json(args.reference_bundle.resolve())
    side_by_side = read_json(args.side_by_side.resolve())
    candidate_suite = read_json(args.candidate_suite.resolve())
    reference_suite = read_json(args.reference_suite.resolve())

    reference_by_family = by_key(reference_bundle.get("stageReferences", []), "familyId")
    comparison_by_family = by_key(side_by_side.get("stageComparisons", []), "familyId")
    candidate_by_family = by_key(candidate_suite.get("completedTraces", []), "familyId")
    reference_trace_by_family = by_key(reference_suite.get("completedTraces", []), "familyId")

    stage_results: list[dict[str, Any]] = []
    route_histogram: dict[str, int] = {}
    for family_id in sorted(reference_by_family.keys(), key=lambda value: int(value)):
        reference = reference_by_family[family_id]
        comparison = comparison_by_family.get(family_id, {})
        candidate_trace = candidate_by_family.get(family_id, {})
        reference_trace = reference_trace_by_family.get(family_id, {})
        records = [
            record
            for record in comparison.get("comparisons", [])
            if isinstance(record, dict)
        ]
        buckets = comparison_buckets(records)
        structural_mismatches = [
            record
            for record in records
            if record.get("status") == "mismatch" and record.get("mismatchClass") in {"exact", "tolerant"}
        ]
        route_label = str(reference.get("routeLabel") or "unknown")
        route_histogram[route_label] = route_histogram.get(route_label, 0) + 1

        stage_results.append(
            {
                "familyId": family_id,
                "title": reference.get("title"),
                "stageIndex": reference.get("stageIndex"),
                "routeLabel": route_label,
                "certificationVerdict": "certified" if not structural_mismatches else "blocked",
                "structuralMismatchCount": len(structural_mismatches),
                "proofs": {
                    "binding": {
                        "preferredMapIndex": {
                            "original": reference.get("preferredMapIndex"),
                            "remake": candidate_trace.get("preferredMapIndex"),
                        },
                        "aiIndex": {
                            "original": reference.get("aiIndex"),
                            "remake": (((comparison.get("remake") or {}).get("stageBlueprint") or {}).get("aiIndex")),
                        },
                    },
                    "dialogue": {
                        "eventCount": {
                            "original": reference.get("scriptEventCount"),
                            "remake": candidate_trace.get("dialogueEventsSeen"),
                        },
                        "anchorCount": {
                            "original": len(reference.get("dialogueAnchors", [])),
                            "remake": len(candidate_trace.get("dialogueAnchorsSeen", [])),
                        },
                        "anchorIds": [item.get("anchorId") for item in reference.get("dialogueAnchors", []) if isinstance(item, dict)],
                    },
                    "scenePhases": {
                        "victoryExpected": reference.get("expectedVictoryPhaseSequence"),
                        "defeatExpected": reference.get("expectedDefeatPhaseSequence"),
                        "remakeSequence": candidate_trace.get("scenePhaseSequence"),
                    },
                    "objectiveFlow": {
                        "referenceSequence": reference_trace.get("objectivePhaseSequence"),
                        "remakeSequence": candidate_trace.get("objectivePhaseSequence"),
                    },
                    "resultAndUnlock": {
                        "referenceResult": reference_trace.get("result"),
                        "remakeResult": candidate_trace.get("result"),
                        "referenceUnlockLabel": reference_trace.get("unlockRevealLabel"),
                        "remakeUnlockLabel": candidate_trace.get("unlockRevealLabel"),
                    },
                },
                "mismatchBuckets": {
                    key: [
                        {
                            "field": record.get("field"),
                            "mismatchClass": record.get("mismatchClass"),
                            "status": record.get("status"),
                            "note": record.get("note"),
                        }
                        for record in value
                        if record.get("status") == "mismatch"
                    ]
                    for key, value in buckets.items()
                },
                "structuralMismatches": structural_mismatches,
            }
        )

    payload = {
        "specVersion": "aw1-stage-flow-certification-v1",
        "generatedAtIso": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "summary": {
            "stageCount": len(stage_results),
            "certifiedStageCount": sum(1 for item in stage_results if item["certificationVerdict"] == "certified"),
            "blockedStageCount": sum(1 for item in stage_results if item["certificationVerdict"] != "certified"),
            "unresolvedStructuralMismatchCount": sum(item["structuralMismatchCount"] for item in stage_results),
            "routeHistogram": route_histogram,
        },
        "certificationRule": {
            "requiredCategories": ["binding", "dialogue", "timing", "result", "unlock"],
            "blockingMismatchClasses": ["exact", "tolerant"],
            "nonBlockingMismatchClasses": ["heuristic"],
        },
        "stages": stage_results,
        "findings": [
            "A stage is certified only if its structural flow comparison has zero exact and tolerant mismatches.",
            "This report widens certification from the regression stems to all 111 stage families.",
        ],
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
