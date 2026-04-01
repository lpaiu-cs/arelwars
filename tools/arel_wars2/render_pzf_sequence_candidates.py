#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

from PIL import Image, ImageDraw


CURRENT_ROOT = Path(__file__).resolve().parent
if str(CURRENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CURRENT_ROOT))

from inspect_binary_assets import (  # noqa: E402
    describe_pzf_section_payload,
    extract_pzf_coordinate_hint,
    iter_pzf_section_payloads,
    parse_pzf,
)
from render_pzf_anchor_probes import choose_matches, load_pzd_row_streams, render_row_stream_rgba  # noqa: E402
from formats import find_zlib_streams  # noqa: E402


POINT_PALETTE = (
    (242, 99, 99),
    (255, 177, 66),
    (82, 196, 109),
    (79, 164, 255),
    (173, 112, 255),
    (88, 214, 214),
    (255, 120, 188),
    (240, 240, 120),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render AW2 PZF body-part sequence candidate sheets")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where candidate sheets are written")
    parser.add_argument("--scale", type=int, default=2, help="Canvas scale factor")
    parser.add_argument("--min-points", type=int, default=8, help="Skip PZF files with fewer compact tuples")
    return parser.parse_args()


def color_for_control(control_word: str, palette_index: dict[str, int]) -> tuple[int, int, int]:
    if control_word not in palette_index:
        palette_index[control_word] = len(palette_index)
    return POINT_PALETTE[palette_index[control_word] % len(POINT_PALETTE)]


def collect_compact_coordinates(pzf_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    entry = parse_pzf(pzf_path)
    streams = find_zlib_streams(pzf_path.read_bytes())
    if not streams:
        return entry, []
    compact = []
    for payload in iter_pzf_section_payloads(streams[0].decoded):
        if not payload:
            continue
        hint = extract_pzf_coordinate_hint(describe_pzf_section_payload(payload))
        if hint is not None:
            compact.append(hint)
    return entry, compact


def locate_pzd_path(assets_root: Path, family: str, stem: str) -> Path | None:
    candidate = assets_root / "pc" / family / "0" / f"{stem}.pzd"
    return candidate if candidate.exists() else None


def build_base_canvas(
    pzf_entry: dict[str, object],
    pzd_path: Path | None,
    compact: list[dict[str, object]],
    scale: int,
) -> tuple[Image.Image, dict[str, int], list[dict[str, object]]]:
    anchors = (pzf_entry.get("anchorBoxes") or {}).get("preview", [])
    x_values = [int(anchor["x"]) for anchor in anchors] + [int(anchor["x"]) + int(anchor["width"]) for anchor in anchors]
    y_values = [int(anchor["y"]) for anchor in anchors] + [int(anchor["y"]) + int(anchor["height"]) for anchor in anchors]
    x_values += [int(point["x"]) for point in compact]
    y_values += [int(point["y"]) for point in compact]
    if not x_values:
        x_values = [-160, 160]
        y_values = [-160, 160]
    x_min = min(x_values) - 12
    x_max = max(x_values) + 12
    y_min = min(y_values) - 12
    y_max = max(y_values) + 12
    margin = 18
    width = max(160, (x_max - x_min) * scale + margin * 2)
    height = max(160, (y_max - y_min) * scale + margin * 2)
    canvas = Image.new("RGBA", (width, height), (10, 12, 18, 255))
    translate = {"x": margin - x_min * scale, "y": margin - y_min * scale}
    matches: list[dict[str, object]] = []

    if pzd_path is not None:
        row_streams = load_pzd_row_streams(pzd_path)
        if anchors and row_streams:
            matches = choose_matches(anchors, row_streams)
            draw = ImageDraw.Draw(canvas)
            for match in matches:
                anchor = match["anchor"]
                row_stream = match["rowStream"]
                x = int(anchor["x"]) * scale + translate["x"]
                y = int(anchor["y"]) * scale + translate["y"]
                rendered = render_row_stream_rgba(row_stream["rowStream"], scale)
                canvas.alpha_composite(rendered, (x, y))
                draw.rectangle(
                    (
                        x,
                        y,
                        x + int(anchor["width"]) * scale,
                        y + int(anchor["height"]) * scale,
                    ),
                    outline=(72, 80, 96, 255),
                    width=1,
                )
    return canvas, translate, matches


def draw_points(base: Image.Image, translate: dict[str, int], points: list[dict[str, object]], scale: int) -> Image.Image:
    image = base.copy()
    draw = ImageDraw.Draw(image)
    palette_index: dict[str, int] = {}
    for point in points:
        control_word = str(point["controlWordHex"])
        color = color_for_control(control_word, palette_index)
        x = int(point["x"]) * scale + translate["x"]
        y = int(point["y"]) * scale + translate["y"]
        radius = 3 if "index" in point else 2
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, 255))
    return image


def build_strip(items: list[tuple[str, Image.Image]], title: str, subtitle: str) -> Image.Image:
    margin = 12
    label_band = 18
    title_band = 34
    if not items:
        return Image.new("RGBA", (320, 80), (10, 12, 18, 255))
    columns = max(1, min(4, math.ceil(math.sqrt(len(items)))))
    cell_width = max(image.width for _, image in items)
    cell_height = max(image.height for _, image in items)
    rows = math.ceil(len(items) / columns)
    canvas = Image.new(
        "RGBA",
        (columns * (cell_width + margin) + margin, rows * (cell_height + label_band + margin) + title_band + margin),
        (10, 12, 18, 255),
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 6), title, fill=(236, 238, 244, 255))
    draw.text((margin, 20), subtitle, fill=(168, 178, 190, 255))
    for idx, (label, image) in enumerate(items):
        col = idx % columns
        row = idx // columns
        x = margin + col * (cell_width + margin)
        y = title_band + margin + row * (cell_height + label_band + margin)
        canvas.alpha_composite(image, (x, y))
        draw.text((x, y + cell_height + 2), label, fill=(214, 220, 232, 255))
    return canvas


def stack_sections(sections: list[Image.Image]) -> Image.Image:
    margin = 12
    width = max(section.width for section in sections)
    height = sum(section.height for section in sections) + margin * (len(sections) + 1)
    canvas = Image.new("RGBA", (width + margin * 2, height), (7, 9, 14, 255))
    y = margin
    for section in sections:
        x = margin + (width - section.width) // 2
        canvas.alpha_composite(section, (x, y))
        y += section.height + margin
    return canvas


def render_sequence_candidate(
    assets_root: Path,
    pzf_path: Path,
    output_root: Path,
    scale: int,
    min_points: int,
) -> tuple[Path, Path] | None:
    entry, compact = collect_compact_coordinates(pzf_path)
    if len(compact) < min_points:
        return None

    family = entry["family"]
    stem = Path(entry["path"]).stem
    pzd_path = locate_pzd_path(assets_root, family, stem)
    base_canvas, translate, matches = build_base_canvas(entry, pzd_path, compact, scale)

    indexed_groups: dict[int, list[dict[str, object]]] = defaultdict(list)
    control_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for point in compact:
        if "index" in point:
            indexed_groups[int(point["index"])].append(point)
        else:
            control_groups[str(point["controlWordHex"])].append(point)

    sections = []
    summary = {
        "path": entry["path"],
        "variant": entry["variant"],
        "compactCoordinateCount": len(compact),
        "anchorCount": len((entry.get("anchorBoxes") or {}).get("preview", [])),
        "matchedPzdPath": str(pzd_path) if pzd_path is not None else None,
        "matchCount": len(matches),
        "indexedGroupCount": len(indexed_groups),
        "controlGroupCount": len(control_groups),
        "indexedGroups": [],
        "controlGroups": [],
    }

    if indexed_groups:
        indexed_items = []
        for index in sorted(indexed_groups)[:16]:
            points = indexed_groups[index]
            indexed_items.append((f"index {index}", draw_points(base_canvas, translate, points, scale)))
            summary["indexedGroups"].append(
                {
                    "index": index,
                    "pointCount": len(points),
                    "controlHistogram": dict(sorted(Counter(point["controlWordHex"] for point in points).items())),
                }
            )
        sections.append(
            build_strip(
                indexed_items,
                f"{family}/{stem} indexed sequence",
                f"{len(indexed_groups)} groups, {sum(len(group) for group in indexed_groups.values())} indexed tuples",
            )
        )

    if control_groups:
        control_items = []
        for control_word, points in sorted(control_groups.items(), key=lambda item: (-len(item[1]), item[0]))[:12]:
            control_items.append((f"{control_word} ({len(points)})", draw_points(base_canvas, translate, points, scale)))
            summary["controlGroups"].append(
                {
                    "controlWordHex": control_word,
                    "pointCount": len(points),
                }
            )
        sections.append(
            build_strip(
                control_items,
                f"{family}/{stem} control overlays",
                f"{len(control_groups)} controls, {sum(len(group) for group in control_groups.values())} unindexed tuples",
            )
        )

    if not sections:
        return None

    sheet = stack_sections(sections)
    output_path = output_root / f"{family}-{stem}-sequence-candidates.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)

    json_path = output_root / f"{family}-{stem}-sequence-candidates.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path, json_path


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    rendered = 0
    for pzf_path in sorted((assets_root / "pc").glob("**/*.pzf")):
        result = render_sequence_candidate(assets_root, pzf_path, output_root, args.scale, args.min_points)
        if result is None:
            continue
        print(result[0])
        print(result[1])
        rendered += 1
    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
