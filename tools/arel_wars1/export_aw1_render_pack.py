#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


ROLE_ASSIGNMENTS = {
    "allied": {
        "screen": "221",
        "push": "230",
        "support": "223",
        "siege": "225",
        "tower-rally": "214",
        "skill-window": "226",
        "hero": "226",
    },
    "enemy": {
        "screen": "214",
        "push": "208",
        "support": "239",
        "siege": "225",
        "tower-rally": "219",
        "skill-window": "228",
        "hero": "209",
    },
    "projectile": {
        "allied": "240",
        "enemy": "240",
    },
    "effect": {
        "support": "223",
        "impact": "214",
        "burst": "179",
        "utility": "240",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export AW1 final render pack for the runtime scene")
    parser.add_argument("--preview-manifest", type=Path, required=True, help="Path to preview_manifest.json")
    parser.add_argument("--runtime-blueprint", type=Path, required=True, help="Path to AW1.runtime_blueprint.json")
    parser.add_argument("--render-semantics", type=Path, required=True, help="Path to AW1.render_semantics.json")
    parser.add_argument("--bank-probe-root", type=Path, required=True, help="Path to mpl_bank_composite_probes/")
    parser.add_argument("--output", type=Path, required=True, help="Output AW1.render_pack.json path")
    parser.add_argument("--web-root", type=Path, required=True, help="Path to public/recovery/analysis")
    return parser.parse_args()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def select_emitter_preset(
    rows: list[dict[str, object]],
    *,
    relation_kind: str | None = None,
    primary_stem: str | None = None,
    secondary_stem: str | None = None,
) -> dict[str, object] | None:
    for row in rows:
        if relation_kind is not None and str(row.get("relationKind")) != relation_kind:
            continue
        if primary_stem is not None:
            primary = row.get("primaryPtc")
            if not isinstance(primary, dict) or str(primary.get("stem")) != primary_stem:
                continue
        if secondary_stem is not None:
            secondary = row.get("secondaryPtc")
            if not isinstance(secondary, dict) or str(secondary.get("stem")) != secondary_stem:
                continue
        return row
    return rows[0] if rows else None


def build_emitter_preset(id_value: str, label: str, row: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(row, dict):
        return None
    primary = row.get("primaryPtc") if isinstance(row.get("primaryPtc"), dict) else {}
    secondary = row.get("secondaryPtc") if isinstance(row.get("secondaryPtc"), dict) else {}
    return {
        "id": id_value,
        "label": label,
        "relationKind": str(row.get("relationKind", "unknown")),
        "primaryPtcStem": str(primary.get("stem")) if primary else None,
        "secondaryPtcStem": str(secondary.get("stem")) if secondary else None,
        "timingFields": [int(value) for value in primary.get("timingFields", [])] if primary else [],
        "emissionFields": [int(value) for value in primary.get("emissionFields", [])] if primary else [],
        "ratioFieldsFloat": [float(value) for value in primary.get("ratioFieldsFloat", [])] if primary else [],
        "signedDeltaFields": [int(value) for value in primary.get("signedDeltaFields", [])] if primary else [],
    }


def main() -> None:
    args = parse_args()
    preview_manifest = read_json(args.preview_manifest.resolve())
    runtime_blueprint = read_json(args.runtime_blueprint.resolve())
    render_semantics = read_json(args.render_semantics.resolve())

    if not isinstance(preview_manifest, dict):
        raise ValueError("preview manifest is not a JSON object")
    if not isinstance(runtime_blueprint, dict):
        raise ValueError("runtime blueprint is not a JSON object")

    web_root = args.web_root.resolve()
    render_root = web_root / "render"
    bank_target_root = render_root / "bank_probes"
    special_target_root = render_root / "special"
    bank_target_root.mkdir(parents=True, exist_ok=True)
    special_target_root.mkdir(parents=True, exist_ok=True)

    stems = preview_manifest.get("stems", [])
    if not isinstance(stems, list):
        raise ValueError("preview manifest missing stems")

    stem_assets: list[dict[str, object]] = []
    bank_probe_count = 0
    for entry in stems:
        if not isinstance(entry, dict):
            continue
        stem = str(entry.get("stem", ""))
        event_frames = entry.get("eventFrames", [])
        if not isinstance(event_frames, list):
            continue
        all_frame_paths: list[str] = []
        linked_frame_paths: list[str] = []
        overlay_frame_paths: list[str] = []
        for frame in event_frames:
            if not isinstance(frame, dict):
                continue
            frame_path = str(frame.get("framePath", ""))
            if not frame_path:
                continue
            all_frame_paths.append(frame_path)
            relation = str(frame.get("relation") or "")
            link_type = str(frame.get("linkType") or "")
            event_type = str(frame.get("eventType") or "")
            if relation.startswith("after-") or relation.startswith("before-") or link_type == "overlay-track" or event_type == "overlay":
                overlay_frame_paths.append(frame_path)
            else:
                linked_frame_paths.append(frame_path)

        bank_probe_src = args.bank_probe_root.resolve() / f"{stem}-mpl-bank-probes.png"
        bank_probe_path = None
        if bank_probe_src.exists():
            dst = bank_target_root / bank_probe_src.name
            copy_file(bank_probe_src, dst)
            bank_probe_path = f"/recovery/analysis/render/bank_probes/{bank_probe_src.name}"
            bank_probe_count += 1

        stem_assets.append(
            {
                "stem": stem,
                "sequenceKind": str(entry.get("sequenceKind", "unknown")),
                "timelineKind": str(entry.get("timelineKind", "unknown")),
                "framePaths": all_frame_paths,
                "linkedFramePaths": linked_frame_paths,
                "overlayFramePaths": overlay_frame_paths,
                "bankProbePath": bank_probe_path,
            }
        )

    render_profile = runtime_blueprint.get("renderProfile", {})
    if not isinstance(render_profile, dict):
        render_profile = {}
    raw_emitters = list(render_semantics.get("ptcEmitterSemantics", {}).get("emitters", []))
    emitter_presets = [
        {
            "id": str(entry.get("id")),
            "semanticKey": entry.get("semanticKey"),
            "label": str(entry.get("label", "Emitter")),
            "family": entry.get("family"),
            "relationKind": str(entry.get("relationKind", "unknown")),
            "blendMode": entry.get("blendMode"),
            "primaryPtcStem": entry.get("primaryStem"),
            "secondaryPtcStem": entry.get("secondaryStem"),
            "timingFields": entry.get("rawTimingFields", []),
            "emissionFields": entry.get("rawEmissionFields", []),
            "ratioFieldsFloat": entry.get("rawRatioFieldsFloat", []),
            "signedDeltaFields": entry.get("rawSignedDeltaFields", []),
            "warmupTicks": entry.get("warmupTicks"),
            "releaseTicks": entry.get("releaseTicks"),
            "lifeTicks": entry.get("lifeTicks"),
            "burstCount": entry.get("burstCount"),
            "sustainCount": entry.get("sustainCount"),
            "spreadUnits": entry.get("spreadUnits"),
            "cadenceTicks": entry.get("cadenceTicks"),
            "radiusScale": entry.get("radiusScale"),
            "alphaScale": entry.get("alphaScale"),
            "sizeScale": entry.get("sizeScale"),
            "jitterScale": entry.get("jitterScale"),
            "driftX": entry.get("driftX"),
            "driftY": entry.get("driftY"),
            "accelX": entry.get("accelX"),
            "accelY": entry.get("accelY"),
        }
        for entry in raw_emitters
        if isinstance(entry, dict)
    ]
    family_representatives = render_semantics.get("ptcEmitterSemantics", {}).get("familyRepresentativeEmitters", {})

    packed_specials: list[dict[str, object]] = []
    packed_179 = render_semantics.get("packedPixel179", {})
    if isinstance(packed_179, dict):
        packed_specials.append(
            {
                "stem": str(packed_179.get("stem", "179")),
                "heuristic": str(packed_179.get("formula", "")),
                "certaintyLevel": str(packed_179.get("certaintyLevel", "asset-structural")),
                "transparentValue": int(packed_179.get("transparentValue", 0)),
                "valueOffset": int(packed_179.get("valueOffset", 1)),
                "paletteSize": int(packed_179.get("paletteSize", 47)),
                "coreBandSize": int(packed_179.get("coreBandSize", 47)),
                "coreBandCount": int(packed_179.get("coreBandCount", 4)),
                "highlightRange": list(packed_179.get("highlightRange", [189, 199])),
                "highlightBlendMode": str(packed_179.get("highlightBlendMode", "additive-tail")),
                "compositePath": packed_179.get("compositePath"),
                "probeSheetPath": packed_179.get("probeSheetPath"),
            }
        )

    effect_emitter_assignments = {
        "support": family_representatives.get("support"),
        "impact": family_representatives.get("impact"),
        "burst": family_representatives.get("burst"),
        "utility": family_representatives.get("utility"),
    }

    pack = {
        "generatedAt": preview_manifest.get("generatedAt"),
        "summary": {
            "stemCount": len(stem_assets),
            "bankProbeCount": bank_probe_count,
            "packedSpecialCount": len(packed_specials),
            "emitterPresetCount": len(emitter_presets),
        },
        "stemAssets": stem_assets,
        "roleAssignments": ROLE_ASSIGNMENTS,
        "effectEmitterAssignments": effect_emitter_assignments,
        "packedPixelSpecials": packed_specials,
        "emitterPresets": emitter_presets,
        "semantics": {
            "mplBankSwitching": render_semantics.get("mplBankSwitching"),
            "packedPixel179": packed_179,
            "certaintyLegend": preview_manifest.get("certaintyLegend"),
        },
    }

    write_json(args.output.resolve(), pack)
    write_json(web_root / "aw1_render_pack.json", pack)


if __name__ == "__main__":
    main()
