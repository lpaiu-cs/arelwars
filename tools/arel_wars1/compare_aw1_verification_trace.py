#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a reconstructed AW1 verification trace against a legacy reference trace"
    )
    parser.add_argument("--spec", type=Path, required=True, help="Path to AW1.verification_spec.json")
    parser.add_argument("--candidate", type=Path, required=True, help="Path to a remake runtime verification export")
    parser.add_argument("--reference", type=Path, required=True, help="Path to a legacy APK reference verification export")
    parser.add_argument("--output", type=Path, help="Optional path to write the comparison report")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def token_overlap(left: str, right: str) -> float:
    left_tokens = set(normalize_text(left).split())
    right_tokens = set(normalize_text(right).split())
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def phase_sequence(trace: dict[str, Any], key: str) -> list[str]:
    sequence = trace.get(key, [])
    if not isinstance(sequence, list):
        return []
    compact: list[str] = []
    for item in sequence:
        if not isinstance(item, str):
            continue
        if compact and compact[-1] == item:
            continue
        compact.append(item)
    return compact


def stage_trace_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    traces = list(payload.get("completedTraces", []))
    current = payload.get("currentTrace")
    if isinstance(current, dict):
      traces.append(current)
    by_family: dict[str, dict[str, Any]] = {}
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        family_id = str(trace.get("familyId") or "")
        if not family_id:
            continue
        by_family[family_id] = trace
    return by_family


def compare_anchor_sets(reference: list[dict[str, Any]], candidate: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    candidate_by_id = {
        str(item.get("anchorId")): item
        for item in candidate
        if isinstance(item, dict) and item.get("anchorId") is not None
    }
    findings: list[dict[str, Any]] = []
    for anchor in reference:
        if not isinstance(anchor, dict):
            continue
        anchor_id = str(anchor.get("anchorId"))
        target = candidate_by_id.get(anchor_id)
        if not target:
            findings.append(
                {
                    "severity": "error",
                    "criterionId": "dialogue-anchor-token-overlap",
                    "message": f"Missing candidate anchor `{anchor_id}`.",
                }
            )
            continue
        overlap = token_overlap(str(anchor.get("text") or ""), str(target.get("text") or ""))
        if overlap < threshold:
            findings.append(
                {
                    "severity": "error",
                    "criterionId": "dialogue-anchor-token-overlap",
                    "message": f"Anchor `{anchor_id}` token overlap {overlap:.2f} below threshold {threshold:.2f}.",
                }
            )
    return findings


def compare_stage(
    spec: dict[str, Any],
    reference: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    if candidate.get("preferredMapIndex") != spec.get("preferredMapIndex") or reference.get("preferredMapIndex") != spec.get("preferredMapIndex"):
        findings.append(
            {
                "severity": "error",
                "criterionId": "stage-binding-exact",
                "message": "preferredMapIndex does not match the stage binding spec.",
            }
        )
    if candidate.get("routeLabel") != reference.get("routeLabel"):
        findings.append(
            {
                "severity": "error",
                "criterionId": "stage-binding-exact",
                "message": "routeLabel differs between candidate and reference traces.",
            }
        )
    if candidate.get("dialogueEventsSeen") != spec.get("scriptEventCount"):
        findings.append(
            {
                "severity": "error",
                "criterionId": "dialogue-count-exact",
                "message": f"candidate dialogueEventsSeen={candidate.get('dialogueEventsSeen')} expected {spec.get('scriptEventCount')}.",
            }
        )
    if reference.get("dialogueEventsSeen") != spec.get("scriptEventCount"):
        findings.append(
            {
                "severity": "error",
                "criterionId": "dialogue-count-exact",
                "message": f"reference dialogueEventsSeen={reference.get('dialogueEventsSeen')} expected {spec.get('scriptEventCount')}.",
            }
        )

    findings.extend(
        compare_anchor_sets(
            list(reference.get("dialogueAnchorsSeen", [])),
            list(candidate.get("dialogueAnchorsSeen", [])),
            0.75,
        )
    )

    expected_phase_sequence = (
        spec.get("expectedVictoryPhaseSequence")
        if candidate.get("result") == "victory"
        else spec.get("expectedDefeatPhaseSequence")
    )
    candidate_phase_sequence = phase_sequence(candidate, "scenePhaseSequence")
    if expected_phase_sequence != candidate_phase_sequence[: len(expected_phase_sequence)]:
        findings.append(
            {
                "severity": "error",
                "criterionId": "victory-phase-sequence" if candidate.get("result") == "victory" else "defeat-phase-sequence",
                "message": f"candidate scenePhaseSequence {candidate_phase_sequence} does not match expected {expected_phase_sequence}.",
            }
        )

    if phase_sequence(reference, "objectivePhaseSequence") != phase_sequence(candidate, "objectivePhaseSequence"):
        findings.append(
            {
                "severity": "warn",
                "criterionId": "objective-phase-sequence",
                "message": "objectivePhaseSequence differs between reference and candidate.",
            }
        )

    for metric in ("enemyWavesDispatched", "alliedWavesDispatched"):
        reference_value = float(reference.get(metric, 0))
        candidate_value = float(candidate.get(metric, 0))
        if abs(reference_value - candidate_value) > 1:
            findings.append(
                {
                    "severity": "warn",
                    "criterionId": "wave-count-tolerance",
                    "message": f"{metric} differs by more than one wave ({reference_value} vs {candidate_value}).",
                }
            )

    for metric in ("spawnCount", "projectileCount", "effectCount", "heroDeployCount"):
        reference_value = float(reference.get(metric, 0))
        candidate_value = float(candidate.get(metric, 0))
        if reference_value <= 0:
            continue
        drift_ratio = abs(reference_value - candidate_value) / max(reference_value, 1)
        if drift_ratio > 0.35:
            findings.append(
                {
                    "severity": "warn",
                    "criterionId": "battle-metric-tolerance",
                    "message": f"{metric} drift ratio {drift_ratio:.2f} exceeds 0.35 ({reference_value} vs {candidate_value}).",
                }
            )

    if candidate.get("result") != reference.get("result"):
        findings.append(
            {
                "severity": "error",
                "criterionId": "result-and-unlock-exact",
                "message": f"result differs between candidate ({candidate.get('result')}) and reference ({reference.get('result')}).",
            }
        )
    if candidate.get("unlockRevealLabel") != reference.get("unlockRevealLabel"):
        findings.append(
            {
                "severity": "warn",
                "criterionId": "result-and-unlock-exact",
                "message": "unlockRevealLabel differs between candidate and reference.",
            }
        )

    verdict = "pass" if not any(item["severity"] == "error" for item in findings) else "fail"
    return {
        "familyId": spec.get("familyId"),
        "title": spec.get("title"),
        "verdict": verdict,
        "findingCount": len(findings),
        "findings": findings,
    }


def main() -> None:
    args = parse_args()
    spec = read_json(args.spec.resolve())
    candidate = read_json(args.candidate.resolve())
    reference = read_json(args.reference.resolve())

    spec_by_family = {
        str(item.get("familyId")): item
        for item in spec.get("stageChecks", [])
        if isinstance(item, dict)
    }
    candidate_by_family = stage_trace_map(candidate)
    reference_by_family = stage_trace_map(reference)

    comparisons: list[dict[str, Any]] = []
    for family_id, spec_stage in spec_by_family.items():
        candidate_trace = candidate_by_family.get(family_id)
        reference_trace = reference_by_family.get(family_id)
        if not candidate_trace or not reference_trace:
            continue
        comparisons.append(compare_stage(spec_stage, reference_trace, candidate_trace))

    payload = {
        "summary": {
            "comparedStageCount": len(comparisons),
            "passCount": sum(1 for item in comparisons if item["verdict"] == "pass"),
            "failCount": sum(1 for item in comparisons if item["verdict"] == "fail"),
        },
        "stages": comparisons,
        "findings": [
            "This report is only as strong as the supplied legacy reference trace.",
            "Exact failures should be handled before tuning tolerant battle-density metrics.",
        ],
    }
    if args.output:
        write_json(args.output.resolve(), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
