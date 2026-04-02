#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export AW1 regression-stem certification report from the side-by-side comparator"
    )
    parser.add_argument("--native-truth", type=Path, required=True, help="Path to AW1.native_truth_manifest.json")
    parser.add_argument("--reference-bundle", type=Path, required=True, help="Path to AW1.original_reference_bundle.json")
    parser.add_argument("--side-by-side", type=Path, required=True, help="Path to AW1.side_by_side_report.json")
    parser.add_argument("--preview-manifest", type=Path, required=True, help="Path to preview_manifest.json")
    parser.add_argument("--runtime-blueprint", type=Path, required=True, help="Path to AW1.runtime_blueprint.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to AW1.regression_stem_certification.json")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_maps(payload: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get(key)): item
        for item in payload
        if isinstance(item, dict) and item.get(key) is not None
    }


def unique_bank_states(preview_stem: dict[str, Any]) -> list[str]:
    states = []
    for frame in preview_stem.get("eventFrames", []):
        if not isinstance(frame, dict):
            continue
        state = frame.get("bankStateId")
        if isinstance(state, str) and state and state not in states:
            states.append(state)
    return states


def unique_bank_transitions(preview_stem: dict[str, Any]) -> list[str]:
    transitions = []
    for frame in preview_stem.get("eventFrames", []):
        if not isinstance(frame, dict):
            continue
        transition = frame.get("bankTransition")
        if isinstance(transition, str) and transition and transition not in transitions:
            transitions.append(transition)
    return transitions


def native_truth_layer_map(native_truth: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in native_truth.get("frozenTruthLayers", [])
        if isinstance(item, dict) and item.get("id") is not None
    }


def allowed_heuristic_fields() -> dict[str, str]:
    return {
        "timelineKindConfidence": "timeline kind remains a heuristic classification and is explicitly waived during regression-stem certification.",
        "overlayCadenceConfidence": "overlay cadence remains a heuristic layer until original-side live traces are available.",
    }


def main() -> None:
    args = parse_args()
    native_truth = read_json(args.native_truth.resolve())
    reference_bundle = read_json(args.reference_bundle.resolve())
    side_by_side = read_json(args.side_by_side.resolve())
    preview_manifest = read_json(args.preview_manifest.resolve())
    runtime_blueprint = read_json(args.runtime_blueprint.resolve())

    truth_layers = native_truth_layer_map(native_truth)
    reference_by_stem = build_maps(reference_bundle.get("regressionRenderReferences", []), "stem")
    comparison_by_stem = build_maps(side_by_side.get("regressionComparisons", []), "stem")
    preview_by_stem = build_maps(preview_manifest.get("stems", []), "stem")

    default_bank_rule = ((runtime_blueprint.get("renderProfile") or {}).get("defaultMplBankRule") or {})
    packed_specials = {
        str(item.get("stem")): item
        for item in ((runtime_blueprint.get("renderProfile") or {}).get("specialPackedPixelStems") or [])
        if isinstance(item, dict) and item.get("stem") is not None
    }
    heuristic_field_notes = allowed_heuristic_fields()

    stem_results: list[dict[str, Any]] = []
    for stem in native_truth.get("regressionStemSet", []):
        stem_key = str(stem)
        reference = reference_by_stem.get(stem_key, {})
        comparison = comparison_by_stem.get(stem_key, {})
        preview = preview_by_stem.get(stem_key, {})
        mismatches = [
            item
            for item in comparison.get("comparisons", [])
            if isinstance(item, dict) and item.get("status") == "mismatch"
        ]
        structural_mismatches = [
            item for item in mismatches if item.get("mismatchClass") in {"exact", "tolerant"}
        ]
        heuristic_mismatches = [
            item for item in mismatches if item.get("mismatchClass") == "heuristic"
        ]
        unresolved_heuristics = [
            item
            for item in heuristic_mismatches
            if str(item.get("field")) not in heuristic_field_notes
        ]

        typed_graph = reference.get("typedGraph") or {}
        preview_graph = preview.get("pzxResourceGraph") or {}
        original_pza = typed_graph.get("pza") or {}
        original_pzf = typed_graph.get("pzf") or {}
        original_pzd = typed_graph.get("pzd") or {}
        preview_timing = preview.get("timingModel") or {}

        heuristic_waivers = [
            {
                "field": item.get("field"),
                "original": item.get("original"),
                "remake": item.get("remake"),
                "reason": heuristic_field_notes.get(str(item.get("field")), "heuristic mismatch not yet waived"),
            }
            for item in heuristic_mismatches
        ]

        render_transition_proof = {
            "defaultBankRule": default_bank_rule.get("selectorRule"),
            "bankStateCount": len(unique_bank_states(preview)),
            "bankTransitionCount": len(unique_bank_transitions(preview)),
            "bankStates": unique_bank_states(preview),
            "bankTransitions": unique_bank_transitions(preview),
            "packedPixelSpecial": packed_specials.get(stem_key),
        }

        certification_verdict = (
            "certified"
            if not structural_mismatches and not unresolved_heuristics
            else "blocked"
        )
        stem_results.append(
            {
                "stem": stem_key,
                "certificationVerdict": certification_verdict,
                "structuralMismatchCount": len(structural_mismatches),
                "heuristicWaiverCount": len(heuristic_waivers),
                "proofs": {
                    "pzdImagePool": {
                        "truthLayerId": "pzd-image-pool-layout",
                        "nativeConfirmed": bool(original_pzd),
                        "original": {
                            "typeId": original_pzd.get("typeId"),
                            "imageCount": original_pzd.get("imageCount"),
                        },
                        "remake": {
                            "typeId": (preview_graph.get("pzd") or {}).get("typeId") if isinstance(preview_graph, dict) else None,
                            "imageCount": (preview_graph.get("pzd") or {}).get("imageCount") if isinstance(preview_graph, dict) else None,
                        },
                    },
                    "pzfFrameComposition": {
                        "truthLayerId": "pzf-frame-composition",
                        "nativeConfirmed": bool(original_pzf),
                        "originalFrameCount": original_pzf.get("itemCount"),
                        "remakeFrameCount": (preview_graph.get("pzf") or {}).get("frameCount") if isinstance(preview_graph, dict) else None,
                    },
                    "pzaBaseTiming": {
                        "truthLayerId": "pza-base-clip-timing",
                        "nativeConfirmed": bool(original_pza),
                        "originalClipCount": original_pza.get("clipCount"),
                        "originalClipDelayHistograms": [
                            clip.get("delayHistogram")
                            for clip in original_pza.get("clips", [])
                            if isinstance(clip, dict)
                        ],
                        "remakeTimingSource": preview_timing.get("baseClipTimingSource"),
                        "remakeTimingConfidence": preview_timing.get("baseClipTimingConfidence"),
                    },
                    "renderStateTransitions": render_transition_proof,
                },
                "structuralMismatches": structural_mismatches,
                "heuristicWaivers": heuristic_waivers,
                "unresolvedHeuristicMismatches": unresolved_heuristics,
                "sourceEvidence": {
                    "referenceAssetPath": reference.get("assetPath"),
                    "previewTimelineKind": preview.get("timelineKind"),
                    "previewTimelineKindConfidence": preview.get("timelineKindConfidence"),
                    "overlayCadenceConfidence": preview_timing.get("overlayCadenceConfidence"),
                },
            }
        )

    payload = {
        "specVersion": "aw1-regression-certification-v1",
        "generatedAtIso": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "summary": {
            "regressionStemCount": len(stem_results),
            "certifiedStemCount": sum(1 for item in stem_results if item["certificationVerdict"] == "certified"),
            "blockedStemCount": sum(1 for item in stem_results if item["certificationVerdict"] != "certified"),
            "unresolvedStructuralMismatchCount": sum(item["structuralMismatchCount"] for item in stem_results),
            "heuristicWaiverCount": sum(item["heuristicWaiverCount"] for item in stem_results),
            "nativeTruthLayerIds": [
                "pza-base-clip-timing",
                "pzf-frame-composition",
                "pzd-image-pool-layout",
                "mpl-flag-bank-switching",
                "packed-pixel-179-special",
            ],
        },
        "nativeTruthReferences": {
            "pzaBaseTiming": truth_layers.get("pza-base-clip-timing"),
            "pzfFrameComposition": truth_layers.get("pzf-frame-composition"),
            "pzdImagePoolLayout": truth_layers.get("pzd-image-pool-layout"),
            "mplBankSwitching": truth_layers.get("mpl-flag-bank-switching"),
            "packedPixel179Special": truth_layers.get("packed-pixel-179-special"),
        },
        "heuristicWaiverPolicy": {
            "allowedFields": heuristic_field_notes,
            "notes": [
                "Regression-stem certification blocks only on exact or tolerant structural mismatches.",
                "Heuristic-only mismatches remain visible and must be re-checked once live original traces become available.",
            ],
        },
        "stems": stem_results,
        "findings": [
            "The regression set is certified only if every stem has zero structural mismatches.",
            "Current waivers cover timeline-kind and overlay-cadence labels, not PZA/PZF/PZD structure or bank switching.",
        ],
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
