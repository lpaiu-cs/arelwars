#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

from PIL import Image, ImageDraw


CURRENT_ROOT = Path(__file__).resolve().parent
if str(CURRENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CURRENT_ROOT))

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "arel_wars1"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.append(str(TOOLS_ROOT))

from formats import find_zlib_streams  # noqa: E402
from inspect_binary_assets import (  # noqa: E402
    describe_pzf_section_payload,
    extract_pzf_coordinate_hint,
    iter_pzf_section_payloads,
    parse_pzf,
)


PALETTE = (
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
    parser = argparse.ArgumentParser(description="Render scatter probes for compact AW2 PZF marker tuples")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where scatter probes are written")
    parser.add_argument("--scale", type=int, default=3, help="Canvas scale factor")
    parser.add_argument("--min-points", type=int, default=8, help="Only render PZF files with at least this many compact tuples")
    return parser.parse_args()


def color_for_control(control_word: str, order: dict[str, int]) -> tuple[int, int, int]:
    if control_word not in order:
        order[control_word] = len(order)
    return PALETTE[order[control_word] % len(PALETTE)]


def collect_compact_coordinates(pzf_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    entry = parse_pzf(pzf_path)
    streams = find_zlib_streams(pzf_path.read_bytes())
    if not streams:
        return entry, []
    compact: list[dict[str, object]] = []
    for payload in iter_pzf_section_payloads(streams[0].decoded):
        if not payload:
            continue
        hint = extract_pzf_coordinate_hint(describe_pzf_section_payload(payload))
        if hint is not None:
            compact.append(hint)
    return entry, compact


def render_scatter(entry: dict[str, object], compact: list[dict[str, object]], output_root: Path, scale: int) -> Path:
    anchor_boxes = (entry.get("anchorBoxes") or {}).get("preview", [])
    x_values = [int(item["x"]) for item in compact]
    y_values = [int(item["y"]) for item in compact]
    if anchor_boxes:
        x_values += [int(item["x"]) for item in anchor_boxes]
        x_values += [int(item["x"]) + int(item["width"]) for item in anchor_boxes]
        y_values += [int(item["y"]) for item in anchor_boxes]
        y_values += [int(item["y"]) + int(item["height"]) for item in anchor_boxes]

    margin = 24
    footer = 58
    x_min = min(x_values) - 6
    x_max = max(x_values) + 6
    y_min = min(y_values) - 6
    y_max = max(y_values) + 6
    image = Image.new(
        "RGBA",
        ((x_max - x_min) * scale + margin * 2, (y_max - y_min) * scale + margin * 2 + footer),
        (10, 12, 18, 255),
    )
    draw = ImageDraw.Draw(image)
    translate_x = margin - x_min * scale
    translate_y = margin - y_min * scale

    for anchor in anchor_boxes:
        box = (
            int(anchor["x"]) * scale + translate_x,
            int(anchor["y"]) * scale + translate_y,
            (int(anchor["x"]) + int(anchor["width"])) * scale + translate_x,
            (int(anchor["y"]) + int(anchor["height"])) * scale + translate_y,
        )
        draw.rectangle(box, outline=(88, 96, 112, 255), width=1)

    control_order: dict[str, int] = {}
    control_counts = Counter(item["controlWordHex"] for item in compact)
    for point in compact:
        color = color_for_control(str(point["controlWordHex"]), control_order)
        x = int(point["x"]) * scale + translate_x
        y = int(point["y"]) * scale + translate_y
        radius = 3 if "index" in point else 2
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, 255))

    title = (
        f"{entry['family']}/{Path(entry['path']).name}  variant={entry['variant']}  "
        f"compactTuples={len(compact)}"
    )
    draw.text((margin, image.height - footer + 4), title, fill=(236, 238, 244, 255))
    legend_parts = [f"{control}:{control_counts[control]}" for control in sorted(control_counts)]
    draw.text((margin, image.height - footer + 22), "  ".join(legend_parts[:8]), fill=(184, 194, 208, 255))
    draw.text((margin, image.height - footer + 38), "points = compact marker tuples, gray boxes = anchor boxes", fill=(150, 160, 176, 255))

    output_path = output_root / f"{entry['family']}-{Path(entry['path']).stem}-marker-scatter.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    rendered = 0
    for pzf_path in sorted((assets_root / "pc").glob("**/*.pzf")):
        entry, compact = collect_compact_coordinates(pzf_path)
        if len(compact) < args.min_points:
            continue
        output_path = render_scatter(entry, compact, output_root, args.scale)
        print(output_path)
        rendered += 1
    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
