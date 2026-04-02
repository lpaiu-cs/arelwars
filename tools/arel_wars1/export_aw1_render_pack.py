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
    parser.add_argument("--bank-probe-root", type=Path, required=True, help="Path to mpl_bank_composite_probes/")
    parser.add_argument("--special-root", type=Path, required=True, help="Path to special PZX preview root")
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
    sample_rows = render_profile.get("ptcBridgeSummary", {}).get("sampleParticleRows", [])
    if not isinstance(sample_rows, list):
        sample_rows = []

    support_row = select_emitter_preset(sample_rows, primary_stem="048")
    burst_row = select_emitter_preset(sample_rows, relation_kind="dual-ptc", primary_stem="046")
    impact_row = select_emitter_preset(sample_rows, relation_kind="dual-ptc", secondary_stem="043")
    utility_row = select_emitter_preset(sample_rows, relation_kind="dual-ptc", primary_stem="034")
    emitter_presets = [
        preset
        for preset in [
            build_emitter_preset("support-048", "Support pulse", support_row),
            build_emitter_preset("burst-046-034", "Burst flare", burst_row),
            build_emitter_preset("impact-047-043", "Impact spark", impact_row),
            build_emitter_preset("utility-034", "Utility trail", utility_row),
        ]
        if preset is not None
    ]

    packed_specials: list[dict[str, object]] = []
    for entry in render_profile.get("specialPackedPixelStems", []):
        if not isinstance(entry, dict):
            continue
        stem = str(entry.get("stem", ""))
        composite_name = f"{stem}-composite-mod47.png"
        composite_src = args.special_root.resolve() / composite_name
        probe_sheet_src = args.special_root.resolve().parent / "special_pzx_probes" / f"{stem}-packed-pixel-probes.png"
        composite_path = None
        probe_sheet_path = None
        if composite_src.exists():
            copy_file(composite_src, special_target_root / composite_name)
            composite_path = f"/recovery/analysis/render/special/{composite_name}"
        if probe_sheet_src.exists():
            copy_file(probe_sheet_src, special_target_root / probe_sheet_src.name)
            probe_sheet_path = f"/recovery/analysis/render/special/{probe_sheet_src.name}"
        packed_specials.append(
            {
                "stem": stem,
                "heuristic": str(entry.get("heuristic", "")),
                "confidence": str(entry.get("confidence", "")),
                "compositePath": composite_path,
                "probeSheetPath": probe_sheet_path,
            }
        )

    effect_emitter_assignments = {
        "support": next((preset["id"] for preset in emitter_presets if preset["id"] == "support-048"), None),
        "impact": next((preset["id"] for preset in emitter_presets if preset["id"] == "impact-047-043"), None),
        "burst": next((preset["id"] for preset in emitter_presets if preset["id"] == "burst-046-034"), None),
        "utility": next((preset["id"] for preset in emitter_presets if preset["id"] == "utility-034"), None),
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
    }

    write_json(args.output.resolve(), pack)
    write_json(web_root / "aw1_render_pack.json", pack)


if __name__ == "__main__":
    main()
