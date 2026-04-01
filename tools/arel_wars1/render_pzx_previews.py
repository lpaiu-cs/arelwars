#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import find_zlib_streams, read_pzx_first_stream, read_pzx_row_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render chunk previews for partially decoded PZX files")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where preview PNGs are written")
    parser.add_argument("--limit", type=int, help="Optional limit on the number of previews to render")
    parser.add_argument("--scale", type=int, default=4, help="Nearest-neighbor scale for chunk previews")
    parser.add_argument("--stems", nargs="*", help="Optional list of PZX stems to render")
    return parser.parse_args()


def color_for_index(value: int) -> tuple[int, int, int]:
    if value == 0:
        return (14, 16, 20)
    return ((value * 53) % 256, (value * 97) % 256, (value * 193) % 256)


def render_chunk(chunk, scale: int) -> Image.Image:
    image = Image.new("RGB", (chunk.width, chunk.height), color_for_index(0))
    pixels = image.load()
    for y, row in enumerate(chunk.rows):
        for x, value in enumerate(row.decoded):
            pixels[x, y] = color_for_index(value)
    if scale > 1:
        image = image.resize((chunk.width * scale, chunk.height * scale), Image.Resampling.NEAREST)
    return image


def render_row_stream(row_stream, scale: int) -> Image.Image:
    width = row_stream.width
    if width is None:
        raise ValueError("Cannot render row stream with inconsistent row widths")

    image = Image.new("RGB", (width, row_stream.height), color_for_index(0))
    pixels = image.load()
    for y, row in enumerate(row_stream.rows):
        for x, value in enumerate(row.decoded):
            pixels[x, y] = color_for_index(value)
    if scale > 1:
        image = image.resize((width * scale, row_stream.height * scale), Image.Resampling.NEAREST)
    return image


def build_sheet(items: list[tuple[str, Image.Image]]) -> Image.Image:
    margin = 12
    label_band = 20
    columns = max(1, math.ceil(math.sqrt(len(items))))

    cell_width = max(image.width for _, image in items) + margin
    cell_height = max(image.height for _, image in items) + margin + label_band
    rows = math.ceil(len(items) / columns)

    sheet = Image.new("RGB", (columns * cell_width + margin, rows * cell_height + margin), (10, 12, 16))
    draw = ImageDraw.Draw(sheet)

    for index, (label, image) in enumerate(items):
        col = index % columns
        row = index // columns
        x = margin + col * cell_width
        y = margin + row * cell_height

        draw.rectangle((x - 1, y - 1, x + image.width, y + image.height), outline=(44, 52, 68))
        sheet.paste(image, (x, y))
        draw.text((x, y + image.height + 4), label, fill=(220, 224, 232))

    return sheet


def render_preview(path: Path, output_root: Path, scale: int) -> Path | None:
    data = path.read_bytes()
    streams = find_zlib_streams(data)
    if not streams:
        return None

    table_span = struct.unpack("<H", data[16:18])[0] >> 6 if len(data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    if first_stream is not None:
        items = [
            (f"{chunk.index:02d} {chunk.width}x{chunk.height}", render_chunk(chunk, scale))
            for chunk in first_stream.chunks
        ]
        sheet = build_sheet(items)
        output_path = output_root / f"{path.stem}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path)
        return output_path

    row_stream_items: list[tuple[str, Image.Image]] = []
    for item in streams[:32]:
        try:
            row_stream = read_pzx_row_stream(item.decoded)
        except ValueError:
            continue
        if row_stream is None or row_stream.width is None:
            continue
        row_stream_items.append(
            (
                f"s{item.offset:04d} {row_stream.width}x{row_stream.height}",
                render_row_stream(row_stream, scale),
            )
        )

    if not row_stream_items:
        return None

    sheet = build_sheet(row_stream_items)
    output_path = output_root / f"{path.stem}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return output_path


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    stems = set(args.stems or [])
    pzx_paths = sorted((assets_root / "img").glob("*.pzx"))
    if stems:
        pzx_paths = [path for path in pzx_paths if path.stem in stems]
    if args.limit is not None:
        pzx_paths = pzx_paths[: args.limit]

    rendered = 0
    for path in pzx_paths:
        output = render_preview(path, output_root, args.scale)
        if output is None:
            continue
        rendered += 1
        print(output)

    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
