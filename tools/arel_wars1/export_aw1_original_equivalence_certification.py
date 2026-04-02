#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export AW1 final original-equivalence certification gate report"
    )
    parser.add_argument("--native-truth", type=Path, required=True, help="Path to AW1.native_truth_manifest.json")
    parser.add_argument(
        "--reference-bundle",
        type=Path,
        required=True,
        help="Path to AW1.original_reference_bundle.json",
    )
    parser.add_argument("--side-by-side", type=Path, required=True, help="Path to AW1.side_by_side_report.json")
    parser.add_argument(
        "--regression-certification",
        type=Path,
        required=True,
        help="Path to AW1.regression_stem_certification.json",
    )
    parser.add_argument(
        "--stage-flow-certification",
        type=Path,
        required=True,
        help="Path to AW1.stage_flow_certification.json",
    )
    parser.add_argument(
        "--battle-render-certification",
        type=Path,
        required=True,
        help="Path to AW1.battle_render_certification.json",
    )
    parser.add_argument("--output", type=Path, required=True, help="Path to AW1.original_equivalence_certification.json")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_side_by_side_heuristics(side_by_side: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for comparison in side_by_side.get("regressionComparisons", []):
        stem = str(comparison.get("stem"))
        for record in comparison.get("comparisons", []):
            if not isinstance(record, dict):
                continue
            if record.get("status") != "mismatch" or record.get("mismatchClass") != "heuristic":
                continue
            records.append(
                {
                    "stem": stem,
                    "category": record.get("category"),
                    "field": record.get("field"),
                    "note": record.get("note"),
                }
            )
    return records


def regression_waiver_map(regression_certification: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    mapping: dict[tuple[str, str], dict[str, Any]] = {}
    for stem_record in regression_certification.get("stems", []):
        stem = str(stem_record.get("stem"))
        for waiver in stem_record.get("heuristicWaivers", []):
            if not isinstance(waiver, dict):
                continue
            field = str(waiver.get("field"))
            mapping[(stem, field)] = waiver
    return mapping


def main() -> None:
    args = parse_args()
    native_truth = read_json(args.native_truth.resolve())
    reference_bundle = read_json(args.reference_bundle.resolve())
    side_by_side = read_json(args.side_by_side.resolve())
    regression_certification = read_json(args.regression_certification.resolve())
    stage_flow_certification = read_json(args.stage_flow_certification.resolve())
    battle_render_certification = read_json(args.battle_render_certification.resolve())

    side_by_side_summary = side_by_side.get("summary") or {}
    regression_summary = regression_certification.get("summary") or {}
    stage_flow_summary = stage_flow_certification.get("summary") or {}
    battle_render_summary = battle_render_certification.get("summary") or {}
    native_truth_summary = native_truth.get("summary") or {}
    reference_bundle_summary = reference_bundle.get("summary") or {}

    heuristic_records = collect_side_by_side_heuristics(side_by_side)
    waiver_lookup = regression_waiver_map(regression_certification)
    covered_heuristics = []
    uncovered_heuristics = []
    for record in heuristic_records:
        waiver = waiver_lookup.get((record["stem"], str(record["field"])))
        combined = {
            **record,
            "waiverReason": waiver.get("reason") if waiver else None,
        }
        if waiver is None:
            uncovered_heuristics.append(combined)
        else:
            covered_heuristics.append(combined)

    gate_checks = {
        "nativeTruthFrozen": {
            "passed": int(native_truth_summary.get("frozenTruthLayerCount") or 0) >= 5,
            "detail": {
                "frozenTruthLayerCount": native_truth_summary.get("frozenTruthLayerCount"),
                "heuristicLayerCount": native_truth_summary.get("heuristicLayerCount"),
            },
        },
        "referenceBundleReady": {
            "passed": int(reference_bundle_summary.get("stageReferenceCount") or 0) == 111,
            "detail": {
                "stageReferenceCount": reference_bundle_summary.get("stageReferenceCount"),
                "uniqueScriptFileCount": reference_bundle_summary.get("uniqueScriptFileCount"),
                "regressionStemCount": reference_bundle_summary.get("regressionStemCount"),
            },
        },
        "regressionCertified": {
            "passed": (
                int(regression_summary.get("certifiedStemCount") or 0)
                == int(regression_summary.get("regressionStemCount") or 0)
                and int(regression_summary.get("blockedStemCount") or 0) == 0
                and int(regression_summary.get("unresolvedStructuralMismatchCount") or 0) == 0
            ),
            "detail": regression_summary,
        },
        "stageFlowCertified": {
            "passed": (
                int(stage_flow_summary.get("certifiedStageCount") or 0)
                == int(stage_flow_summary.get("stageCount") or 0)
                and int(stage_flow_summary.get("blockedStageCount") or 0) == 0
                and int(stage_flow_summary.get("unresolvedStructuralMismatchCount") or 0) == 0
            ),
            "detail": stage_flow_summary,
        },
        "battleRepresentativeCertified": {
            "passed": (
                int(battle_render_summary.get("battleCertifiedCount") or 0)
                == int(battle_render_summary.get("representativeBattleStageCount") or 0)
                and int(battle_render_summary.get("battleBlockedCount") or 0) == 0
                and int(battle_render_summary.get("exactBattleMismatchCount") or 0) == 0
                and int(battle_render_summary.get("tolerantBattleMismatchCount") or 0) == 0
            ),
            "detail": {
                "representativeBattleStageCount": battle_render_summary.get("representativeBattleStageCount"),
                "battleCertifiedCount": battle_render_summary.get("battleCertifiedCount"),
                "routeCoverage": battle_render_summary.get("routeCoverage"),
                "effectIntensityCoverage": battle_render_summary.get("effectIntensityCoverage"),
                "archetypeCoverage": battle_render_summary.get("archetypeCoverage"),
            },
        },
        "renderRepresentativeCertified": {
            "passed": (
                int(battle_render_summary.get("renderCertifiedStemCount") or 0)
                == int(battle_render_summary.get("representativeRenderStemCount") or 0)
                and int(battle_render_summary.get("renderBlockedStemCount") or 0) == 0
                and int(battle_render_summary.get("nativeRenderMismatchCount") or 0) == 0
            ),
            "detail": {
                "representativeRenderStemCount": battle_render_summary.get("representativeRenderStemCount"),
                "renderCertifiedStemCount": battle_render_summary.get("renderCertifiedStemCount"),
                "heuristicRenderWaiverCount": battle_render_summary.get("heuristicRenderWaiverCount"),
            },
        },
        "heuristicMismatchCoverage": {
            "passed": len(uncovered_heuristics) == 0,
            "detail": {
                "sideBySideHeuristicMismatchCount": len(heuristic_records),
                "coveredByExplicitWaiverCount": len(covered_heuristics),
                "uncoveredHeuristicMismatchCount": len(uncovered_heuristics),
            },
        },
    }

    overall_passed = all(check["passed"] for check in gate_checks.values())

    payload = {
        "specVersion": "aw1-original-equivalence-certification-v1",
        "generatedAtIso": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "certificationVerdict": "original-equivalence-certified" if overall_passed else "not-yet-certified",
        "certificationScope": {
            "referenceApkPath": ((reference_bundle.get("sourceApk") or {}).get("path")),
            "referenceApkSha256": ((reference_bundle.get("sourceApk") or {}).get("sha256")),
            "stageCount": reference_bundle_summary.get("stageReferenceCount"),
            "regressionStemCount": reference_bundle_summary.get("regressionStemCount"),
        },
        "gateChecks": gate_checks,
        "waiverRegistry": {
            "explicitHeuristicWaivers": covered_heuristics,
            "uncoveredHeuristicMismatches": uncovered_heuristics,
            "notes": [
                "Heuristic-only mismatches are allowed at the final gate only when they appear in an explicit waiver record.",
                "Current explicit waivers cover regression-stem timeline-kind and overlay-cadence labels only.",
                "PTC emitter semantics remain a heuristic witness but do not appear as side-by-side mismatches in the current certification set.",
            ],
        },
        "inputs": {
            "nativeTruthManifest": str(args.native_truth.resolve()),
            "referenceBundle": str(args.reference_bundle.resolve()),
            "sideBySideReport": str(args.side_by_side.resolve()),
            "regressionCertification": str(args.regression_certification.resolve()),
            "stageFlowCertification": str(args.stage_flow_certification.resolve()),
            "battleRenderCertification": str(args.battle_render_certification.resolve()),
        },
        "findings": [
            "The final gate passes only if every prior certification layer passes and every heuristic mismatch is explicitly waived.",
            "This certification is limited to the current original-reference bundle and native/disassemble truth frozen in the manifest.",
        ],
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
