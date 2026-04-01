#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw


TOOLS_ROOT = Path(__file__).resolve().parents[1] / "arel_wars1"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from formats import find_zlib_streams, read_pzx_row_stream  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render pseudo-color previews for AW2 PZD row streams")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where preview PNGs are written")
    parser.add_argument("--limit", type=int, default=24, help="Maximum number of previews to render")
    parser.add_argument("--scale", type=int, default=4, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def color_for_index(value: int) -> tuple[int, int, int]:
    if value == 0:
        return (12, 14, 18)
    return ((value * 47) % 256, (value * 89) % 256, (value * 173) % 256)


def render_row_stream(row_stream, scale: int) -> Image.Image:
    if row_stream.width is None:
        raise ValueError("Inconsistent row widths")
    image = Image.new("RGB", (row_stream.width, row_stream.height), color_for_index(0))
    pixels = image.load()
    for y, row in enumerate(row_stream.rows):
        for x, value in enumerate(row.decoded):
            pixels[x, y] = color_for_index(value)
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    return image


def build_sheet(items: list[tuple[str, Image.Image]]) -> Image.Image:
    margin = 10
    label_band = 18
    columns = max(1, math.ceil(math.sqrt(len(items))))
    cell_width = max(image.width for _, image in items) + margin
    cell_height = max(image.height for _, image in items) + label_band + margin
    rows = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_width + margin, rows * cell_height + margin), (8, 10, 14))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(items):
        col = index % columns
        row = index // columns
        x = margin + col * cell_width
        y = margin + row * cell_height
        sheet.paste(image, (x, y))
        draw.text((x, y + image.height + 2), label, fill=(226, 230, 238))
    return sheet


def render_preview(path: Path, output_root: Path, scale: int) -> Path | None:
    streams = find_zlib_streams(path.read_bytes())
    items: list[tuple[str, Image.Image]] = []
    for index, hit in enumerate(streams[:20]):
        try:
            row_stream = read_pzx_row_stream(hit.decoded)
        except ValueError:
            continue
        if row_stream is None or row_stream.width is None:
            continue
        items.append((f"{index:02d} {row_stream.width}x{row_stream.height}", render_row_stream(row_stream, scale)))
    if not items:
        return None
    sheet = build_sheet(items)
    relative = path.relative_to(path.parents[3])
    stem = "-".join(relative.with_suffix("").parts[-4:])
    output_path = output_root / f"{stem}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return output_path


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    paths = sorted((assets_root / "pc").glob("**/*.pzd"))[: args.limit]
    rendered = 0
    for path in paths:
        output = render_preview(path, output_root, args.scale)
        if output is None:
            continue
        print(output)
        rendered += 1
    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
