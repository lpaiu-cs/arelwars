#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any


REGRESSION_STEMS = ["082", "084", "208", "209", "215", "226", "230", "240"]

CERTAINTY_LEGEND = {
    "native-confirmed": "Matches a native field or consumer behavior already confirmed from disassembly.",
    "asset-structural": "Exact or near-exact structure recovered from APK assets, but not necessarily backed by a closed native consumer path.",
    "runtime-consistent heuristic": "Useful and stable in the remake runtime, but not yet proven as original-engine truth.",
    "donor/prototype inferred": "Filled or grouped from neighboring examples rather than closed on the target asset itself.",
}

PROVENANCE_LEGEND = {
    "native-disassembly": "Backed by the disassemble branch and native loader analysis.",
    "apk-structural-exact": "Backed by exact APK-side structural or binding evidence on main.",
    "runtime-reconstruction": "Backed by remake-side reconstruction and consistency checks, not by a closed native proof path.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the AW1 native-truth vs heuristic manifest for certification work")
    parser.add_argument("--stage-bindings", type=Path, required=True, help="Path to AW1.stage_bindings.json")
    parser.add_argument("--opcode-map", type=Path, required=True, help="Path to AW1.opcode_action_map.json")
    parser.add_argument("--render-semantics", type=Path, required=True, help="Path to AW1.render_semantics.json")
    parser.add_argument("--runtime-blueprint", type=Path, required=True, help="Path to AW1.runtime_blueprint.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to write AW1.native_truth_manifest.json")
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


def build_truth_layers(
    stage_bindings: dict[str, Any], opcode_map: dict[str, Any], render_semantics: dict[str, Any], runtime_blueprint: dict[str, Any]
) -> dict[str, Any]:
    binding_summary = stage_bindings.get("summary", {})
    opcode_summary = opcode_map.get("summary", {})
    render_summary = render_semantics.get("summary", {})
    runtime_summary = runtime_blueprint.get("summary", {})
    mpl = render_semantics.get("mplBankSwitching", {})
    ptc = render_semantics.get("ptcEmitterSemantics", {})
    packed_179 = render_semantics.get("packedPixel179", {})

    truth_layers = [
        {
            "id": "pzx-root-subresource-typing",
            "label": "PZX root typed subresources",
            "domain": "render-stack",
            "certaintyLevel": "native-confirmed",
            "provenance": "native-disassembly",
            "certificationRole": "base render truth",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md",
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-native-branch-alignment.md",
            ],
            "proofSummary": [
                "PZX root offsets are typed as field4->PZD, field8->PZF, field12->PZA.",
                "Certification should treat the stack as PZA -> PZF -> PZD rather than grouped tail cadence alone.",
            ],
        },
        {
            "id": "pza-base-clip-timing",
            "label": "PZA base clip timing",
            "domain": "animation-timing",
            "certaintyLevel": "native-confirmed",
            "provenance": "native-disassembly",
            "certificationRole": "timing truth",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md",
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-original-equivalence-certification-plan.md",
            ],
            "proofSummary": [
                "Embedded PZA delay is the authoritative base-clip timing when present.",
                "Main-branch playbackDurationMs must not be treated as a substitute for native PZA delay.",
            ],
            "regressionStemSet": REGRESSION_STEMS,
        },
        {
            "id": "pzf-frame-composition",
            "label": "PZF frame composition",
            "domain": "render-stack",
            "certaintyLevel": "native-confirmed",
            "provenance": "native-disassembly",
            "certificationRole": "frame assembly truth",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md",
            ],
            "proofSummary": [
                "PZF owns frame composition and sub-frame placement.",
                "Grouped tail overlays must not replace PZF frame-order truth in certification work.",
            ],
        },
        {
            "id": "pzd-image-pool-layout",
            "label": "PZD image-pool layout",
            "domain": "render-stack",
            "certaintyLevel": "native-confirmed",
            "provenance": "native-disassembly",
            "certificationRole": "bitmap indexing truth",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md",
            ],
            "proofSummary": [
                "PZD type 8 aligns to chunk-indexed pools; type 7 aligns to row-stream image indexes.",
                "This is the canonical source for image-pool identity during certification.",
            ],
        },
        {
            "id": "stage-family-ai-map-binding",
            "label": "Script family to AI row to map bin binding",
            "domain": "stage-binding",
            "certaintyLevel": "asset-structural",
            "provenance": "apk-structural-exact",
            "certificationRole": "stage identity truth",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.stage_bindings.json",
            ],
            "proofSummary": [
                "Every current script-backed stage binds exactly as familyId == XlsAi rowIndex with inline pair-base and pair-branch map pointers.",
                "Main runtime no longer depends on scored map heuristics for stage identity.",
            ],
            "counts": {
                "stageBindingCount": int(binding_summary.get("stageBindingCount", 0)),
                "scriptAiExactCoverage": int(binding_summary.get("scriptAiExactCoverage", 0)),
                "inlineMapExactCoverage": int(binding_summary.get("inlineMapExactCoverage", 0)),
            },
        },
        {
            "id": "mpl-flag-bank-switching",
            "label": "MPL flag-driven bank switching",
            "domain": "render-stack",
            "certaintyLevel": str(mpl.get("certaintyLevel", "native-confirmed")),
            "provenance": "native-disassembly",
            "certificationRole": "palette state truth",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.render_semantics.json",
            ],
            "selectorRule": str(mpl.get("selectorRule", "")),
            "counts": {
                "exactStateCount": int(mpl.get("exactStateCount", 0)),
                "bankStateCount": int(render_summary.get("bankStateCount", 0)),
            },
            "proofSummary": list(mpl.get("notes", []))[:3],
        },
        {
            "id": "packed-pixel-179-special",
            "label": "179 packed-pixel special case",
            "domain": "render-stack",
            "certaintyLevel": str(packed_179.get("certaintyLevel", "asset-structural")),
            "provenance": "apk-structural-exact",
            "certificationRole": "special render handling",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.render_semantics.json",
            ],
            "proofSummary": list(packed_179.get("notes", []))[:3],
            "notes": [
                "Treat 179 as an isolated structural special case.",
                "Do not generalize its packed-pixel mapping onto normal stems during certification.",
            ],
        },
    ]

    heuristic_layers = [
        {
            "id": "grouped-tail-overlay-cadence",
            "label": "Grouped tail overlay cadence",
            "domain": "animation-timing",
            "certaintyLevel": "runtime-consistent heuristic",
            "provenance": "runtime-reconstruction",
            "certificationRole": "secondary runtime playback layer",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md",
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-native-branch-alignment.md",
            ],
            "proofSummary": [
                "Grouped tail sections remain useful for the remake runtime but are not proven native timing fields.",
                "They should be compared separately from PZA base timing during certification.",
            ],
        },
        {
            "id": "timeline-kind-classification",
            "label": "Timeline kind classification",
            "domain": "animation-timing",
            "certaintyLevel": "runtime-consistent heuristic",
            "provenance": "runtime-reconstruction",
            "certificationRole": "debug taxonomy only",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md",
            ],
            "proofSummary": [
                "timelineKind is useful for grouping runtime playback behavior.",
                "It must not be treated as a native enum in certification reports.",
            ],
        },
        {
            "id": "playback-duration-ms",
            "label": "playbackDurationMs overlay sheet",
            "domain": "animation-timing",
            "certaintyLevel": "runtime-consistent heuristic",
            "provenance": "runtime-reconstruction",
            "certificationRole": "preview tempo layer only",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/docs/aw1-disassemble-branch-review.md",
            ],
            "proofSummary": [
                "Current main playbackDurationMs values do not directly overlap native PZA delay values on the regression set.",
                "Use them only as remake playback scaffolding until native-equivalence replacement is in place.",
            ],
            "regressionStemSet": REGRESSION_STEMS,
        },
        {
            "id": "opcode-scene-command-registry",
            "label": "Opcode scene-command registry",
            "domain": "scene-scripting",
            "certaintyLevel": "runtime-consistent heuristic",
            "provenance": "runtime-reconstruction",
            "certificationRole": "scene interpreter scaffolding",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.opcode_action_map.json",
            ],
            "counts": {
                "opcodeActionCount": int(opcode_summary.get("opcodeActionCount", 0)),
                "featuredOpcodeCount": int(opcode_summary.get("featuredOpcodeCount", 0)),
                "curatedVariantCount": int(opcode_summary.get("curatedVariantCount", 0)),
            },
            "proofSummary": [
                "Opcode registry is complete enough for runtime interpretation, but it is not yet a native-disassembly command table.",
                "Original-equivalence work should keep room for renaming or splitting commands when native evidence improves.",
            ],
        },
        {
            "id": "ptc-emitter-semantics",
            "label": "PTC emitter semantics",
            "domain": "effects",
            "certaintyLevel": str(ptc.get("certaintyLevel", "runtime-consistent heuristic")),
            "provenance": "runtime-reconstruction",
            "certificationRole": "effect-behavior approximation",
            "supportingDocs": [
                "/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.render_semantics.json",
            ],
            "counts": {
                "ptcEmitterCount": int(render_summary.get("ptcEmitterCount", 0)),
            },
            "proofSummary": [
                "Emitter families and names are useful runtime labels.",
                "Field semantics should still be treated as reconstructed until matched to original-side behavior.",
            ],
        },
    ]

    dormant_native_paths = [
        {
            "id": "global-delay-bias",
            "label": "CGxPZxAni global delay bias",
            "provenance": "native-disassembly",
            "status": "dormant-in-current-apk",
            "notes": [
                "Native playback code carries a signed globalDelayBias field.",
                "Current APK appears not to exercise it in the active asset set.",
            ],
        },
        {
            "id": "reference-point-mode",
            "label": "Reference-point bounding mode",
            "provenance": "native-disassembly",
            "status": "dormant-in-current-apk",
            "notes": [
                "Bounding-box and reference-point machinery exists natively.",
                "Current APK coverage suggests the mode is dormant for live content.",
            ],
        },
        {
            "id": "effectex-zeroeffectex-paths",
            "label": "EffectEx and ZeroEffectEx selector paths",
            "provenance": "native-disassembly",
            "status": "mostly-dormant-in-current-apk",
            "notes": [
                "Selector tables and draw-op routing are substantially understood.",
                "Do not force remake runtime behavior to mirror dormant native paths unless live APK evidence appears.",
            ],
        },
    ]

    policy = {
        "certificationUsesNativeTruthFor": [
            "PZA base timing",
            "PZF frame composition",
            "PZD image-pool indexing",
            "MPL flag-driven bank switching",
        ],
        "certificationUsesAssetStructuralTruthFor": [
            "script family to AI row to map bin binding",
            "179 special packed-pixel handling",
        ],
        "requiresExplicitWaiverIfUsedAsProof": [
            "timelineKind",
            "playbackDurationMs",
            "grouped tail cadence",
            "opcode action mnemonics",
            "PTC emitter semantics",
        ],
        "runtimeSummary": {
            "stageBlueprintCount": int(runtime_summary.get("stageBlueprintCount", 0)),
            "opcodeHeuristicCount": int(runtime_summary.get("opcodeHeuristicCount", 0)),
            "tutorialChainCount": int(runtime_summary.get("tutorialChainCount", 0)),
        },
    }

    return {
        "summary": {
            "frozenTruthLayerCount": len(truth_layers),
            "heuristicLayerCount": len(heuristic_layers),
            "dormantNativePathCount": len(dormant_native_paths),
            "regressionStemCount": len(REGRESSION_STEMS),
        },
        "certaintyLegend": CERTAINTY_LEGEND,
        "provenanceLegend": PROVENANCE_LEGEND,
        "regressionStemSet": REGRESSION_STEMS,
        "certificationPolicy": policy,
        "frozenTruthLayers": truth_layers,
        "heuristicLayers": heuristic_layers,
        "dormantNativePaths": dormant_native_paths,
        "findings": [
            "Certification must treat PZA base timing and grouped tail cadence as separate layers.",
            "Main runtime timing sheets remain valid for playback scaffolding, but not as direct native timing proof.",
            "Stage binding is exact enough to serve as certification truth even though it is asset-structural rather than disassembly-derived.",
        ],
    }


def main() -> None:
    args = parse_args()
    stage_bindings = read_json(args.stage_bindings.resolve())
    opcode_map = read_json(args.opcode_map.resolve())
    render_semantics = read_json(args.render_semantics.resolve())
    runtime_blueprint = read_json(args.runtime_blueprint.resolve())

    payload = build_truth_layers(stage_bindings, opcode_map, render_semantics, runtime_blueprint)
    write_json(args.output.resolve(), payload)
    if args.web_output:
        copy_file(args.output.resolve(), args.web_output.resolve())


if __name__ == "__main__":
    main()
