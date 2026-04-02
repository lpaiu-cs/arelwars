#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from compare_aw1_verification_trace import list_overlap, phase_sequence, stage_trace_map, token_overlap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare original APK-derived AW1 references against remake traces side-by-side"
    )
    parser.add_argument("--reference-bundle", type=Path, required=True, help="Path to AW1.original_reference_bundle.json")
    parser.add_argument("--candidate-suite", type=Path, required=True, help="Path to remake candidate verification suite JSON")
    parser.add_argument("--reference-suite", type=Path, help="Optional normalized original trace suite, e.g. AW1.golden_capture_suite.json")
    parser.add_argument("--runtime-blueprint", type=Path, required=True, help="Path to AW1.runtime_blueprint.json")
    parser.add_argument("--preview-manifest", type=Path, required=True, help="Path to preview_manifest.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to write AW1.side_by_side_report.json")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_record(
    *,
    category: str,
    mismatch_class: str,
    field: str,
    status: str,
    original: Any,
    remake: Any,
    reference_trace: Any = None,
    note: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "category": category,
        "mismatchClass": mismatch_class,
        "field": field,
        "status": status,
        "original": original,
        "remake": remake,
    }
    if reference_trace is not None:
        payload["referenceTrace"] = reference_trace
    if note:
        payload["note"] = note
    return payload


def parse_unlock_index(label: str | None) -> int | None:
    if not label:
        return None
    match = re.search(r"Node\s+(\d+)\s+unlocked", label)
    return int(match.group(1)) if match else None


def stage_blueprint_map(runtime_blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("familyId")): item
        for item in runtime_blueprint.get("stageBlueprints", [])
        if isinstance(item, dict) and item.get("familyId") is not None
    }


def preview_stem_map(preview_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("stem")): item
        for item in preview_manifest.get("stems", [])
        if isinstance(item, dict) and item.get("stem") is not None
    }


def comparison_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "exactMismatchCount": sum(
            1 for item in records if item["status"] == "mismatch" and item["mismatchClass"] == "exact"
        ),
        "tolerantMismatchCount": sum(
            1 for item in records if item["status"] == "mismatch" and item["mismatchClass"] == "tolerant"
        ),
        "heuristicMismatchCount": sum(
            1 for item in records if item["status"] == "mismatch" and item["mismatchClass"] == "heuristic"
        ),
    }


def verdict_from_records(records: list[dict[str, Any]]) -> str:
    counts = comparison_counts(records)
    if counts["exactMismatchCount"] > 0:
        return "fail"
    if counts["tolerantMismatchCount"] > 0:
        return "warn"
    return "pass"


def stage_unlock_expectation(stage_reference: dict[str, Any]) -> int | None:
    for check in stage_reference.get("comparisonChecks", []):
        if not isinstance(check, dict):
            continue
        if check.get("criterionId") != "result-and-unlock-exact":
            continue
        value = check.get("expectedValue")
        if isinstance(value, dict) and value.get("nextUnlockNodeIndex") is not None:
            return int(value["nextUnlockNodeIndex"])
    return None


def compare_dialogue_anchors(
    reference_anchors: list[dict[str, Any]],
    candidate_anchors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    candidate_by_id = {
        str(item.get("anchorId")): item
        for item in candidate_anchors
        if isinstance(item, dict) and item.get("anchorId") is not None
    }
    for anchor in reference_anchors:
        if not isinstance(anchor, dict):
            continue
        anchor_id = str(anchor.get("anchorId") or "")
        if not anchor_id:
            continue
        candidate = candidate_by_id.get(anchor_id)
        if candidate is None:
            records.append(
                make_record(
                    category="dialogue",
                    mismatch_class="exact",
                    field=f"anchor:{anchor_id}",
                    status="mismatch",
                    original=anchor.get("text"),
                    remake=None,
                    note="Missing dialogue anchor in remake trace.",
                )
            )
            continue
        overlap = token_overlap(str(anchor.get("text") or ""), str(candidate.get("text") or ""))
        records.append(
            make_record(
                category="dialogue",
                mismatch_class="tolerant",
                field=f"anchor:{anchor_id}:token-overlap",
                status="match" if overlap >= 0.75 else "mismatch",
                original=anchor.get("text"),
                remake=candidate.get("text"),
                note=f"token overlap={overlap:.2f}",
            )
        )
    return records


def compare_stage(
    stage_reference: dict[str, Any],
    candidate_trace: dict[str, Any] | None,
    reference_trace: dict[str, Any] | None,
    stage_blueprint: dict[str, Any] | None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    family_id = str(stage_reference.get("familyId") or "")
    stage_blueprint = stage_blueprint or {}

    if candidate_trace is None:
        records.append(
            make_record(
                category="binding",
                mismatch_class="exact",
                field="trace-presence",
                status="mismatch",
                original="original-reference-present",
                remake=None,
                note="Missing remake trace for stage family.",
            )
        )
    else:
        records.append(
            make_record(
                category="binding",
                mismatch_class="exact",
                field="routeLabel",
                status="match" if candidate_trace.get("routeLabel") == stage_reference.get("routeLabel") else "mismatch",
                original=stage_reference.get("routeLabel"),
                remake=candidate_trace.get("routeLabel"),
            )
        )
        records.append(
            make_record(
                category="binding",
                mismatch_class="exact",
                field="preferredMapIndex",
                status="match"
                if candidate_trace.get("preferredMapIndex") == stage_reference.get("preferredMapIndex")
                else "mismatch",
                original=stage_reference.get("preferredMapIndex"),
                remake=candidate_trace.get("preferredMapIndex"),
            )
        )
        records.append(
            make_record(
                category="binding",
                mismatch_class="exact",
                field="aiIndex",
                status="match" if stage_blueprint.get("aiIndex") == stage_reference.get("aiIndex") else "mismatch",
                original=stage_reference.get("aiIndex"),
                remake=stage_blueprint.get("aiIndex"),
            )
        )
        records.append(
            make_record(
                category="dialogue",
                mismatch_class="exact",
                field="dialogueEventsSeen",
                status="match"
                if candidate_trace.get("dialogueEventsSeen") == stage_reference.get("scriptEventCount")
                else "mismatch",
                original=stage_reference.get("scriptEventCount"),
                remake=candidate_trace.get("dialogueEventsSeen"),
            )
        )
        records.extend(
            compare_dialogue_anchors(
                list(stage_reference.get("dialogueAnchors", [])),
                list(candidate_trace.get("dialogueAnchorsSeen", [])),
            )
        )

        scene_reference = stage_reference.get("sceneReference") or {}
        original_command_ids = list(scene_reference.get("opcodeCommandIds", []))
        remake_command_ids = list(
            dict.fromkeys(
                str(item.get("commandId"))
                for item in stage_blueprint.get("opcodeCues", [])
                if isinstance(item, dict) and item.get("commandId")
            )
        )
        command_overlap = list_overlap(original_command_ids, remake_command_ids)
        records.append(
            make_record(
                category="scene-command",
                mismatch_class="tolerant",
                field="opcodeCommandIds",
                status="match" if command_overlap >= 0.5 else "mismatch",
                original=original_command_ids,
                remake=remake_command_ids,
                note=f"overlap={command_overlap:.2f}",
            )
        )
        original_command_types = list(scene_reference.get("opcodeCommandTypes", []))
        remake_command_types = list(
            dict.fromkeys(
                str(item.get("commandType"))
                for item in stage_blueprint.get("opcodeCues", [])
                if isinstance(item, dict) and item.get("commandType")
            )
        )
        command_type_overlap = list_overlap(original_command_types, remake_command_types)
        records.append(
            make_record(
                category="scene-command",
                mismatch_class="tolerant",
                field="opcodeCommandTypes",
                status="match" if command_type_overlap >= 0.5 else "mismatch",
                original=original_command_types,
                remake=remake_command_types,
                note=f"overlap={command_type_overlap:.2f}",
            )
        )

        expected_phase_sequence = (
            stage_reference.get("expectedVictoryPhaseSequence")
            if candidate_trace.get("result") == "victory"
            else stage_reference.get("expectedDefeatPhaseSequence")
        )
        candidate_phase_sequence = phase_sequence(candidate_trace, "scenePhaseSequence")
        records.append(
            make_record(
                category="timing",
                mismatch_class="exact",
                field="scenePhaseSequence",
                status="match"
                if candidate_phase_sequence[: len(expected_phase_sequence)] == expected_phase_sequence
                else "mismatch",
                original=expected_phase_sequence,
                remake=candidate_phase_sequence,
            )
        )

        if reference_trace is not None:
            original_objective = phase_sequence(reference_trace, "objectivePhaseSequence")
            remake_objective = phase_sequence(candidate_trace, "objectivePhaseSequence")
            objective_overlap = list_overlap(original_objective, remake_objective)
            records.append(
                make_record(
                    category="timing",
                    mismatch_class="tolerant",
                    field="objectivePhaseSequence",
                    status="match" if objective_overlap >= 0.75 else "mismatch",
                    original=original_objective,
                    remake=remake_objective,
                    reference_trace=original_objective,
                    note=f"overlap={objective_overlap:.2f}",
                )
            )
            records.append(
                make_record(
                    category="battle",
                    mismatch_class="tolerant",
                    field="tempoBand",
                    status="match" if reference_trace.get("tempoBand") == candidate_trace.get("tempoBand") else "mismatch",
                    original=reference_trace.get("tempoBand"),
                    remake=candidate_trace.get("tempoBand"),
                )
            )
            reference_elapsed = float(reference_trace.get("elapsedMs") or 0)
            candidate_elapsed = float(candidate_trace.get("elapsedMs") or 0)
            elapsed_drift = abs(reference_elapsed - candidate_elapsed) / max(reference_elapsed, 1) if reference_elapsed > 0 else 0.0
            records.append(
                make_record(
                    category="battle",
                    mismatch_class="tolerant",
                    field="elapsedMs",
                    status="match" if elapsed_drift <= 0.6 else "mismatch",
                    original=reference_elapsed,
                    remake=candidate_elapsed,
                    note=f"driftRatio={elapsed_drift:.2f}",
                )
            )
            for metric in ("enemyWavesDispatched", "alliedWavesDispatched"):
                records.append(
                    make_record(
                        category="battle",
                        mismatch_class="tolerant",
                        field=metric,
                        status="match"
                        if abs(float(reference_trace.get(metric, 0)) - float(candidate_trace.get(metric, 0))) <= 1
                        else "mismatch",
                        original=reference_trace.get(metric),
                        remake=candidate_trace.get(metric),
                    )
                )
            for metric in ("spawnCount", "projectileCount", "effectCount", "heroDeployCount"):
                reference_value = float(reference_trace.get(metric, 0) or 0)
                candidate_value = float(candidate_trace.get(metric, 0) or 0)
                drift_ratio = abs(reference_value - candidate_value) / max(reference_value, 1) if reference_value > 0 else 0.0
                records.append(
                    make_record(
                        category="battle",
                        mismatch_class="tolerant",
                        field=metric,
                        status="match" if reference_value <= 0 or drift_ratio <= 0.35 else "mismatch",
                        original=reference_trace.get(metric),
                        remake=candidate_trace.get(metric),
                        note=f"driftRatio={drift_ratio:.2f}" if reference_value > 0 else "no reference metric",
                    )
                )
            records.append(
                make_record(
                    category="result",
                    mismatch_class="exact",
                    field="result",
                    status="match" if candidate_trace.get("result") == reference_trace.get("result") else "mismatch",
                    original=reference_trace.get("result"),
                    remake=candidate_trace.get("result"),
                )
            )
        else:
            records.append(
                make_record(
                    category="timing",
                    mismatch_class="heuristic",
                    field="referenceTraceMode",
                    status="mismatch",
                    original="normalized-original-trace-unavailable",
                    remake="candidate-only",
                    note="No original-side normalized trace suite supplied; stage timing and battle density checks are limited.",
                )
            )

        render_intent = (stage_reference.get("runtimeContext") or {}).get("renderIntent") or {}
        remake_render_intent = (stage_blueprint or {}).get("renderIntent") or {}
        for field in ("effectIntensity", "bankRule", "packedPixelHint"):
            if render_intent.get(field) is None:
                continue
            records.append(
                make_record(
                    category="render",
                    mismatch_class="exact",
                    field=f"renderIntent.{field}",
                    status="match" if remake_render_intent.get(field) == render_intent.get(field) else "mismatch",
                    original=render_intent.get(field),
                    remake=remake_render_intent.get(field),
                )
            )

        unlock_expected = stage_unlock_expectation(stage_reference)
        actual_unlock = parse_unlock_index(candidate_trace.get("unlockRevealLabel")) if candidate_trace is not None else None
        records.append(
            make_record(
                category="unlock",
                mismatch_class="exact",
                field="nextUnlockNodeIndex",
                status="match" if unlock_expected == actual_unlock else "mismatch",
                original=unlock_expected,
                remake=actual_unlock,
                note=str(candidate_trace.get("unlockRevealLabel") or "") if candidate_trace is not None else None,
            )
        )

    counts = comparison_counts(records)
    return {
        "familyId": family_id,
        "title": stage_reference.get("title"),
        "verdict": verdict_from_records(records),
        **counts,
        "original": {
            "stageReference": {
                "routeLabel": stage_reference.get("routeLabel"),
                "preferredMapIndex": stage_reference.get("preferredMapIndex"),
                "aiIndex": stage_reference.get("aiIndex"),
                "scriptEventCount": stage_reference.get("scriptEventCount"),
                "dialogueAnchorCount": len(stage_reference.get("dialogueAnchors", [])),
                "sceneReference": stage_reference.get("sceneReference"),
                "renderIntent": (stage_reference.get("runtimeContext") or {}).get("renderIntent"),
            },
            "referenceTrace": reference_trace,
        },
        "remake": {
            "trace": candidate_trace,
            "stageBlueprint": {
                "aiIndex": stage_blueprint.get("aiIndex"),
                "renderIntent": stage_blueprint.get("renderIntent"),
                "opcodeCueCount": len(stage_blueprint.get("opcodeCues", [])),
            },
        },
        "comparisons": records,
    }


def compare_regression_stem(
    original_reference: dict[str, Any],
    preview_stem: dict[str, Any] | None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    typed_graph = original_reference.get("typedGraph") or {}
    preview_graph = (preview_stem or {}).get("pzxResourceGraph") or {}
    original_pzd = typed_graph.get("pzd")
    original_pzf = typed_graph.get("pzf")
    original_pza = typed_graph.get("pza")
    preview_pzd = preview_graph.get("pzd") if isinstance(preview_graph, dict) else None
    preview_pzf = preview_graph.get("pzf") if isinstance(preview_graph, dict) else None
    preview_pza = preview_graph.get("pza") if isinstance(preview_graph, dict) else None

    records.append(
        make_record(
            category="render",
            mismatch_class="exact",
            field="pzd.present",
            status="match" if bool(original_pzd) == bool(preview_pzd) else "mismatch",
            original=bool(original_pzd),
            remake=bool(preview_pzd),
        )
    )
    if isinstance(original_pzd, dict) and isinstance(preview_pzd, dict):
        for field in ("typeId", "imageCount"):
            original_value = original_pzd.get(field)
            remake_value = preview_pzd.get(field)
            records.append(
                make_record(
                    category="render",
                    mismatch_class="exact",
                    field=f"pzd.{field}",
                    status="match" if original_value == remake_value else "mismatch",
                    original=original_value,
                    remake=remake_value,
                )
            )

    records.append(
        make_record(
            category="render",
            mismatch_class="exact",
            field="pzf.present",
            status="match" if bool(original_pzf) == bool(preview_pzf) else "mismatch",
            original=bool(original_pzf),
            remake=bool(preview_pzf),
        )
    )
    if isinstance(original_pzf, dict) and isinstance(preview_pzf, dict):
        records.append(
            make_record(
                category="render",
                mismatch_class="exact",
                field="pzf.frameCount",
                status="match" if original_pzf.get("itemCount") == preview_pzf.get("frameCount") else "mismatch",
                original=original_pzf.get("itemCount"),
                remake=preview_pzf.get("frameCount"),
            )
        )

    records.append(
        make_record(
            category="timing",
            mismatch_class="exact",
            field="pza.present",
            status="match" if bool(original_pza) == bool(preview_pza) else "mismatch",
            original=bool(original_pza),
            remake=bool(preview_pza),
        )
    )
    if isinstance(original_pza, dict) and isinstance(preview_pza, dict):
        records.append(
            make_record(
                category="timing",
                mismatch_class="exact",
                field="pza.clipCount",
                status="match" if original_pza.get("clipCount") == preview_pza.get("clipCount") else "mismatch",
                original=original_pza.get("clipCount"),
                remake=preview_pza.get("clipCount"),
            )
        )

    timing_model = (preview_stem or {}).get("timingModel") or {}
    if isinstance(original_pza, dict):
        records.append(
            make_record(
                category="timing",
                mismatch_class="exact",
                field="baseClipTimingSource",
                status="match"
                if timing_model.get("baseClipTimingSource") == "native-confirmed PZA delay ticks"
                and timing_model.get("baseClipTimingConfidence") == "native-confirmed"
                else "mismatch",
                original="native-confirmed PZA delay ticks",
                remake=timing_model.get("baseClipTimingSource"),
                note=str(timing_model.get("baseClipTimingConfidence")),
            )
        )

    timeline_kind_confidence = (preview_stem or {}).get("timelineKindConfidence")
    records.append(
        make_record(
            category="render",
            mismatch_class="heuristic",
            field="timelineKindConfidence",
            status="match" if timeline_kind_confidence == "native-confirmed" else "mismatch",
            original="native-confirmed preferred",
            remake=timeline_kind_confidence,
            note="timeline kind remains a heuristic layer unless explicitly proven on the native path.",
        )
    )
    overlay_cadence_confidence = timing_model.get("overlayCadenceConfidence")
    records.append(
        make_record(
            category="timing",
            mismatch_class="heuristic",
            field="overlayCadenceConfidence",
            status="match" if overlay_cadence_confidence == "native-confirmed" else "mismatch",
            original="native-confirmed preferred",
            remake=overlay_cadence_confidence,
            note="overlay cadence remains heuristic until original-side capture proves it.",
        )
    )

    counts = comparison_counts(records)
    return {
        "stem": original_reference.get("stem"),
        "verdict": verdict_from_records(records),
        **counts,
        "original": original_reference,
        "remake": preview_stem,
        "comparisons": records,
    }


def main() -> None:
    args = parse_args()
    reference_bundle = read_json(args.reference_bundle.resolve())
    candidate_suite = read_json(args.candidate_suite.resolve())
    reference_suite = read_json(args.reference_suite.resolve()) if args.reference_suite else None
    runtime_blueprint = read_json(args.runtime_blueprint.resolve())
    preview_manifest = read_json(args.preview_manifest.resolve())

    candidate_by_family = stage_trace_map(candidate_suite)
    reference_by_family = stage_trace_map(reference_suite) if isinstance(reference_suite, dict) else {}
    blueprint_by_family = stage_blueprint_map(runtime_blueprint)
    preview_by_stem = preview_stem_map(preview_manifest)

    stage_comparisons = [
        compare_stage(
            stage_reference,
            candidate_by_family.get(str(stage_reference.get("familyId") or "")),
            reference_by_family.get(str(stage_reference.get("familyId") or "")),
            blueprint_by_family.get(str(stage_reference.get("familyId") or "")),
        )
        for stage_reference in reference_bundle.get("stageReferences", [])
        if isinstance(stage_reference, dict)
    ]

    regression_comparisons = [
        compare_regression_stem(reference, preview_by_stem.get(str(reference.get("stem") or "")))
        for reference in reference_bundle.get("regressionRenderReferences", [])
        if isinstance(reference, dict)
    ]

    all_records = [
        record
        for section in (*stage_comparisons, *regression_comparisons)
        for record in section.get("comparisons", [])
        if isinstance(record, dict)
    ]
    summary = {
        "stageComparisonCount": len(stage_comparisons),
        "regressionComparisonCount": len(regression_comparisons),
        "stagePassCount": sum(1 for item in stage_comparisons if item["verdict"] == "pass"),
        "stageWarnCount": sum(1 for item in stage_comparisons if item["verdict"] == "warn"),
        "stageFailCount": sum(1 for item in stage_comparisons if item["verdict"] == "fail"),
        "regressionPassCount": sum(1 for item in regression_comparisons if item["verdict"] == "pass"),
        "regressionWarnCount": sum(1 for item in regression_comparisons if item["verdict"] == "warn"),
        "regressionFailCount": sum(1 for item in regression_comparisons if item["verdict"] == "fail"),
        "exactMismatchCount": sum(
            1 for item in all_records if item.get("status") == "mismatch" and item.get("mismatchClass") == "exact"
        ),
        "tolerantMismatchCount": sum(
            1 for item in all_records if item.get("status") == "mismatch" and item.get("mismatchClass") == "tolerant"
        ),
        "heuristicMismatchCount": sum(
            1 for item in all_records if item.get("status") == "mismatch" and item.get("mismatchClass") == "heuristic"
        ),
        "categoryMismatchCounts": {
            category: sum(
                1
                for item in all_records
                if item.get("status") == "mismatch" and item.get("category") == category
            )
            for category in ("binding", "dialogue", "scene-command", "timing", "battle", "render", "result", "unlock")
        },
    }

    payload = {
        "specVersion": "aw1-side-by-side-v1",
        "generatedAtIso": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "inputs": {
            "referenceBundle": str(args.reference_bundle.resolve()),
            "candidateSuite": str(args.candidate_suite.resolve()),
            "referenceSuite": str(args.reference_suite.resolve()) if args.reference_suite else None,
            "runtimeBlueprint": str(args.runtime_blueprint.resolve()),
            "previewManifest": str(args.preview_manifest.resolve()),
            "referenceTraceMode": (
                "normalized-original-trace-suite" if args.reference_suite else "bundle-only-bootstrap"
            ),
        },
        "summary": summary,
        "stageComparisons": stage_comparisons,
        "regressionComparisons": regression_comparisons,
        "findings": [
            "Exact mismatches indicate structural divergence from the original-side reference bundle or normalized reference trace.",
            "Tolerant mismatches indicate drift outside agreed windows for battle tempo, wave counts, or command overlap.",
            "Heuristic mismatches do not fail the comparator by themselves; they mark layers still waiting for native-side proof.",
        ],
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
