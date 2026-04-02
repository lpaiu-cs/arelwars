#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
from typing import Any

from PIL import Image, ImageDraw

from formats import (
    find_zlib_streams,
    read_mpl,
    read_pzx_first_stream,
    read_pzx_simple_placement_stream,
    rgb565_rgba,
)


EMITTER_SIGNATURES: dict[tuple[str | None, str | None], dict[str, str]] = {
    ("048", None): {
        "semanticKey": "support-pulse",
        "family": "support",
        "blendMode": "additive-soft",
        "label": "Support pulse",
    },
    ("046", "034"): {
        "semanticKey": "burst-flare",
        "family": "burst",
        "blendMode": "additive-hot",
        "label": "Burst flare",
    },
    ("047", "043"): {
        "semanticKey": "impact-spark",
        "family": "impact",
        "blendMode": "additive-hot",
        "label": "Impact spark",
    },
    ("034", "022"): {
        "semanticKey": "utility-trail",
        "family": "utility",
        "blendMode": "alpha-trail",
        "label": "Utility trail",
    },
    ("002", "001"): {
        "semanticKey": "smoke-plume",
        "family": "utility",
        "blendMode": "alpha-smoke",
        "label": "Smoke plume",
    },
    ("042", "037"): {
        "semanticKey": "guard-ward",
        "family": "support",
        "blendMode": "additive-ward",
        "label": "Guard ward",
    },
    ("048", "039"): {
        "semanticKey": "support-ring",
        "family": "support",
        "blendMode": "additive-soft",
        "label": "Support ring",
    },
    ("048", "009"): {
        "semanticKey": "support-shimmer",
        "family": "support",
        "blendMode": "additive-soft",
        "label": "Support shimmer",
    },
    ("048", "043"): {
        "semanticKey": "support-impact",
        "family": "support",
        "blendMode": "additive-soft",
        "label": "Support impact",
    },
    ("021", "004"): {
        "semanticKey": "mana-drift",
        "family": "utility",
        "blendMode": "additive-mana",
        "label": "Mana drift",
    },
    ("049", "043"): {
        "semanticKey": "armageddon-burst",
        "family": "burst",
        "blendMode": "additive-hot",
        "label": "Armageddon burst",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export canonical AW1 render semantics for MPL/PTC/179")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to recovery/arel_wars1/apk_unzip/assets")
    parser.add_argument("--effect-runtime-links", type=Path, required=True, help="Path to AW1.effect_runtime_links.json")
    parser.add_argument("--timeline-root", type=Path, required=True, help="Path to recovery/arel_wars1/timeline_candidate_strips")
    parser.add_argument("--output", type=Path, required=True, help="Path to write AW1.render_semantics.json")
    parser.add_argument("--web-output", type=Path, help="Optional web copy for AW1.render_semantics.json")
    parser.add_argument("--web-render-root", type=Path, help="Optional public/recovery/analysis/render root for generated images")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def adjust_rgba(rgba: tuple[int, int, int, int], factor: float) -> tuple[int, int, int, int]:
    r, g, b, a = rgba
    return (
        max(0, min(255, int(round(r * factor)))),
        max(0, min(255, int(round(g * factor)))),
        max(0, min(255, int(round(b * factor)))),
        a,
    )


def build_179_mapper(mpl: Any, variant: str):
    bank_a = list(mpl.bank_a)
    bank_b = list(mpl.bank_b)
    color_count = int(mpl.color_count)
    shade_factors = [0.74, 0.9, 1.0, 1.14]

    def direct_bank(label: str):
        palette = bank_a if label == "a" else bank_b

        def mapper(value: int) -> tuple[int, int, int, int]:
            if value <= 0:
                return (0, 0, 0, 0)
            normalized = value - 1
            palette_index = normalized % color_count
            return rgb565_rgba(palette[palette_index])

        return mapper

    if variant == "bank-a":
        return direct_bank("a")
    if variant == "bank-b":
        return direct_bank("b")

    def shade_mapper(value: int) -> tuple[int, int, int, int]:
        if value <= 0:
            return (0, 0, 0, 0)

        normalized = value - 1
        palette_index = normalized % color_count
        shade_band = normalized // color_count
        if shade_band >= 4:
            rgba = rgb565_rgba(bank_a[palette_index])
            base = adjust_rgba(rgba, 1.34)
            return (
                min(255, base[0] + 20),
                min(255, base[1] + 12),
                min(255, base[2] + 6),
                base[3],
            )

        palette = bank_b if shade_band in {0, 2} else bank_a
        rgba = rgb565_rgba(palette[palette_index])
        return adjust_rgba(rgba, shade_factors[shade_band])

    return shade_mapper


def render_179_images(assets_root: Path, web_render_root: Path | None) -> dict[str, object]:
    pzx_path = assets_root / "img" / "179.pzx"
    mpl_path = assets_root / "img" / "180.mpl"
    if not pzx_path.exists() or not mpl_path.exists():
        raise FileNotFoundError("AW1 special 179 assets are missing")

    mpl = read_mpl(mpl_path.read_bytes())
    if mpl is None:
        raise ValueError("failed to decode shared 179/180 MPL")

    data = pzx_path.read_bytes()
    streams = find_zlib_streams(data)
    if len(streams) < 2:
        raise ValueError("179.pzx does not contain the expected zlib streams")

    table_span = struct.unpack("<H", data[16:18])[0] >> 6 if len(data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    if first_stream is None:
        raise ValueError("failed to decode 179 first stream")

    placements = None
    for stream in streams[1:]:
        placements = read_pzx_simple_placement_stream(stream.decoded, len(first_stream.chunks))
        if placements is not None:
            break
    if placements is None:
        raise ValueError("failed to decode 179 placement stream")

    min_x = min(item.x for item in placements)
    min_y = min(item.y for item in placements)
    max_x = max(item.x + first_stream.chunks[item.chunk_index].width for item in placements)
    max_y = max(item.y + first_stream.chunks[item.chunk_index].height for item in placements)
    width = max_x - min_x
    height = max_y - min_y

    variants = [
        ("bank-b", build_179_mapper(mpl, "bank-b")),
        ("bank-a", build_179_mapper(mpl, "bank-a")),
        ("corrected-shade", build_179_mapper(mpl, "corrected-shade")),
        ("corrected-highlight", build_179_mapper(mpl, "corrected-highlight")),
    ]

    def render_variant(mapper) -> Image.Image:
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for placement in placements:
            chunk = first_stream.chunks[placement.chunk_index]
            chunk_image = Image.new("RGBA", (chunk.width, chunk.height), (0, 0, 0, 0))
            pixels = chunk_image.load()
            for y, row in enumerate(chunk.rows):
                for x, value in enumerate(row.decoded):
                    pixels[x, y] = mapper(value)
            canvas.alpha_composite(chunk_image, (placement.x - min_x, placement.y - min_y))
        return canvas

    final_composite = render_variant(build_179_mapper(mpl, "corrected-highlight"))

    margin = 10
    label_band = 22
    probe_sheet = Image.new(
        "RGBA",
        (margin + len(variants) * (width + margin), height + label_band + margin * 2),
        (18, 20, 24, 255),
    )
    draw = ImageDraw.Draw(probe_sheet)
    draw.text((margin, 3), "179 packed-pixel corrected probes", fill=(232, 236, 240, 255))
    for index, (label, mapper) in enumerate(variants):
        canvas = render_variant(mapper)
        x = margin + index * (width + margin)
        probe_sheet.alpha_composite(canvas, (x, label_band + margin))
        draw.text((x, label_band - 16), label, fill=(214, 220, 228, 255))

    composite_path = None
    probe_sheet_path = None
    if web_render_root is not None:
        special_root = web_render_root / "special"
        special_root.mkdir(parents=True, exist_ok=True)
        composite_file = special_root / "179-composite-final.png"
        probe_file = special_root / "179-packed-pixel-probes-final.png"
        final_composite.save(composite_file)
        probe_sheet.save(probe_file)
        composite_path = "/recovery/analysis/render/special/179-composite-final.png"
        probe_sheet_path = "/recovery/analysis/render/special/179-packed-pixel-probes-final.png"

    boundary_values = [47, 94, 141, 188, 189, 199]
    boundary_histogram: dict[str, int] = {str(value): 0 for value in boundary_values}
    for chunk in first_stream.chunks:
        for row in chunk.rows:
            for value in row.decoded:
                key = str(int(value))
                if key in boundary_histogram:
                    boundary_histogram[key] += 1

    return {
        "certaintyLevel": "asset-structural",
        "stem": "179",
        "sharedMplStem": "180",
        "transparentValue": 0,
        "valueOffset": 1,
        "paletteSize": int(mpl.color_count),
        "coreBandSize": int(mpl.color_count),
        "coreBandCount": 4,
        "coreBands": [
            {"band": 0, "range": [1, 47], "bank": "bank-b", "shadeFactor": 0.74},
            {"band": 1, "range": [48, 94], "bank": "bank-a", "shadeFactor": 0.9},
            {"band": 2, "range": [95, 141], "bank": "bank-b", "shadeFactor": 1.0},
            {"band": 3, "range": [142, 188], "bank": "bank-a", "shadeFactor": 1.14},
        ],
        "highlightRange": [189, 199],
        "highlightBank": "bank-a",
        "highlightBlendMode": "additive-tail",
        "formula": "if value == 0: transparent; else normalized = value - 1; band = normalized // 47; paletteIndex = normalized % 47; bands 0..3 alternate bank-b/bank-a/bank-b/bank-a; values 189..199 use bank-a with additive highlight tail",
        "notes": [
            "This packed-pixel rule is treated as a special 179-only mapping.",
            "It is stronger than a generic preview heuristic, but it should not be generalized onto normal PZX/MPL stems.",
        ],
        "boundaryHistogram": boundary_histogram,
        "compositePath": composite_path,
        "probeSheetPath": probe_sheet_path,
    }


def summarize_bank_semantics(timeline_root: Path) -> dict[str, object]:
    state_histogram: dict[str, int] = {}
    stem_state_counts: dict[str, dict[str, int]] = {}
    exact_states = 0
    for path in sorted(timeline_root.glob("*-timeline-strip.json")):
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        stem = str(payload.get("stem", path.stem.split("-")[0]))
        for event in payload.get("events", []):
            if not isinstance(event, dict):
                continue
            state_id = str(event.get("bankStateId", "unknown"))
            state_histogram[state_id] = state_histogram.get(state_id, 0) + 1
            stem_counts = stem_state_counts.setdefault(stem, {})
            stem_counts[state_id] = stem_counts.get(state_id, 0) + 1
            exact_states += 1

    return {
        "certaintyLevel": "native-confirmed",
        "label": "flag-driven-bank-switch",
        "selectorRule": "frame and tail items with flag == 0 select MPL bank B; items with flag > 0 select MPL bank A",
        "exactStateCount": exact_states,
        "stateHistogram": dict(sorted(state_histogram.items())),
        "stemStateCounts": {stem: dict(sorted(counts.items())) for stem, counts in sorted(stem_state_counts.items())},
        "notes": [
            "Anchor and tail item flags are now exported per preview frame instead of inferred from overlay-only event labels.",
            "Runtime bank overlays now read exact flagged-item counts and bank transitions from preview frames.",
        ],
    }


def build_ptc_emitters(effect_runtime_links: dict[str, object]) -> dict[str, object]:
    emitters: list[dict[str, object]] = []
    family_representatives: dict[str, str] = {}
    for row in effect_runtime_links.get("particleRows", []):
        if not isinstance(row, dict):
            continue
        primary = row.get("primaryPtc") if isinstance(row.get("primaryPtc"), dict) else {}
        secondary = row.get("secondaryPtc") if isinstance(row.get("secondaryPtc"), dict) else {}
        primary_stem = str(primary.get("stem")) if primary else None
        secondary_stem = str(secondary.get("stem")) if secondary else None
        signature = EMITTER_SIGNATURES.get((primary_stem, secondary_stem), {
            "semanticKey": "generic-emitter",
            "family": "utility",
            "blendMode": "alpha-soft",
            "label": "Generic emitter",
        })
        timing_fields = [int(value) for value in primary.get("timingFields", [])] if primary else [0, 0, 0]
        emission_fields = [int(value) for value in primary.get("emissionFields", [])] if primary else [0, 0, 0, 0]
        ratio_fields = [float(value) for value in primary.get("ratioFieldsFloat", [])] if primary else [0.0, 0.0, 0.0, 0.0]
        delta_fields = [int(value) for value in primary.get("signedDeltaFields", [])] if primary else [0, 0, 0, 0]
        while len(timing_fields) < 3:
            timing_fields.append(0)
        while len(emission_fields) < 4:
            emission_fields.append(0)
        while len(ratio_fields) < 4:
            ratio_fields.append(0.0)
        while len(delta_fields) < 4:
            delta_fields.append(0)

        emitter_id = f"ptc-row-{int(row['index']):02d}-{signature['semanticKey']}"
        family = signature["family"]
        emitters.append(
            {
                "id": emitter_id,
                "semanticKey": signature["semanticKey"],
                "label": signature["label"],
                "family": family,
                "relationKind": str(row.get("relationKind", "unknown")),
                "blendMode": signature["blendMode"],
                "particleRowIndex": int(row["index"]),
                "primaryStem": primary_stem,
                "secondaryStem": secondary_stem,
                "warmupTicks": timing_fields[0],
                "releaseTicks": timing_fields[1],
                "lifeTicks": timing_fields[2],
                "burstCount": emission_fields[0],
                "sustainCount": emission_fields[1],
                "spreadUnits": emission_fields[2],
                "cadenceTicks": emission_fields[3],
                "radiusScale": ratio_fields[0],
                "alphaScale": ratio_fields[1],
                "sizeScale": ratio_fields[2],
                "jitterScale": ratio_fields[3],
                "driftX": delta_fields[0],
                "driftY": delta_fields[1],
                "accelX": delta_fields[2],
                "accelY": delta_fields[3],
                "rawTimingFields": timing_fields,
                "rawEmissionFields": emission_fields,
                "rawRatioFieldsFloat": ratio_fields,
                "rawSignedDeltaFields": delta_fields,
            }
        )
        if family not in family_representatives:
            family_representatives[family] = emitter_id

    return {
        "certaintyLevel": "runtime-consistent heuristic",
        "familyRepresentativeEmitters": family_representatives,
        "emitters": emitters,
    }


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    effect_runtime_links = read_json(args.effect_runtime_links.resolve())
    timeline_root = args.timeline_root.resolve()
    web_render_root = args.web_render_root.resolve() if args.web_render_root else None

    packed_179 = render_179_images(assets_root, web_render_root)
    bank_semantics = summarize_bank_semantics(timeline_root)
    ptc_emitters = build_ptc_emitters(effect_runtime_links)

    payload = {
        "summary": {
            "bankStateCount": int(bank_semantics.get("exactStateCount", 0)),
            "ptcEmitterCount": len(ptc_emitters["emitters"]),
            "packedPixelSpecialCount": 1,
        },
        "mplBankSwitching": bank_semantics,
        "packedPixel179": packed_179,
        "ptcEmitterSemantics": ptc_emitters,
        "findings": [
            "179 packed pixels are exported as a special-case structural mapping: 0 is transparent, 1..188 span four 47-value bands, and 189..199 form the additive highlight tail.",
            "MPL bank switching is exported from exact per-frame item flags instead of overlay-only labels.",
            "PTC emitter semantics remain runtime-consistent reconstructions even though they now feed the live renderer.",
        ],
    }

    output_path = args.output.resolve()
    write_json(output_path, payload)
    if args.web_output is not None:
        write_json(args.web_output.resolve(), payload)


if __name__ == "__main__":
    main()
