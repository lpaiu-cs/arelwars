#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

from formats import (
    find_zlib_streams,
    mpl_index_to_rgba,
    read_mpl,
    read_pzx_first_stream,
    read_pzx_row_stream,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render heuristic MPL palette probes for paired PZX assets")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where probe PNGs are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of paired stems to render")
    parser.add_argument("--limit", type=int, help="Optional limit on rendered stems")
    parser.add_argument("--scale", type=int, default=2, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def render_rows(rows, width: int, height: int, palette_words: list[int], scale: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = image.load()
    for y, row in enumerate(rows):
        for x, value in enumerate(row.decoded):
            pixels[x, y] = mpl_index_to_rgba(value, palette_words)
    if scale > 1:
        image = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    return image


def build_sheet(stem: str, frames, palette_label: str, scale: int) -> Image.Image:
    margin = 8
    label_band = 18
    columns = max(1, math.ceil(math.sqrt(len(frames))))
    rendered = [
        render_rows(frame["rows"], frame["width"], frame["height"], palette_words, scale)
        for frame, palette_words in frames
    ]
    cell_width = max(image.width for image in rendered) + margin
    cell_height = max(image.height for image in rendered) + margin + label_band
    rows = math.ceil(len(rendered) / columns)

    sheet = Image.new("RGBA", (columns * cell_width + margin, rows * cell_height + margin), (18, 20, 24, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 2), f"{stem} palette {palette_label} (RGB565 heuristic)", fill=(232, 236, 240, 255))

    for index, ((frame, _palette_words), image) in enumerate(zip(frames, rendered, strict=True)):
        col = index % columns
        row = index // columns
        x = margin + col * cell_width
        y = margin + 16 + row * cell_height
        sheet.alpha_composite(image, (x, y))
        draw.text((x, y + image.height + 2), frame["label"], fill=(230, 230, 230, 255))

    return sheet


def read_mpl_palettes(path: Path) -> tuple[int, dict[str, list[int]]] | None:
    mpl = read_mpl(path.read_bytes())
    if mpl is None:
        return None

    return (
        mpl.color_count,
        {
            "a": list(mpl.bank_a),
            "b": list(mpl.bank_b),
        },
    )


def render_pair(stem: str, assets_root: Path, output_root: Path, scale: int) -> list[Path]:
    pzx_path = assets_root / "img" / f"{stem}.pzx"
    mpl_path = assets_root / "img" / f"{stem}.mpl"
    if not pzx_path.exists() or not mpl_path.exists():
        return []

    pzx_data = pzx_path.read_bytes()
    streams = find_zlib_streams(pzx_data)
    if not streams:
        return []

    table_span = struct.unpack("<H", pzx_data[16:18])[0] >> 6 if len(pzx_data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    frames: list[dict[str, object]] = []
    used_max_index: int | None = None

    if first_stream is not None:
        used_max_index = max(max(row.decoded) for chunk in first_stream.chunks for row in chunk.rows)
        frames = [
            {
                "label": f"{chunk.index:02d} {chunk.width}x{chunk.height}",
                "width": chunk.width,
                "height": chunk.height,
                "rows": chunk.rows,
            }
            for chunk in first_stream.chunks
        ]
    else:
        raw_row_streams = []
        for index, item in enumerate(streams):
            try:
                row_stream = read_pzx_row_stream(item.decoded)
            except ValueError:
                continue
            if row_stream is None or row_stream.width is None:
                continue
            raw_row_streams.append(
                {
                    "label": f"s{index:02d} {row_stream.width}x{row_stream.height}",
                    "width": row_stream.width,
                    "height": row_stream.height,
                    "rows": row_stream.rows,
                    "maxDecodedIndex": max(max(row.decoded) for row in row_stream.rows if row.decoded),
                }
            )
        if raw_row_streams:
            frames = raw_row_streams
            used_max_index = max(int(frame["maxDecodedIndex"]) for frame in raw_row_streams)

    if not frames or used_max_index is None:
        return []

    palette_info = read_mpl_palettes(mpl_path)
    if palette_info is None:
        return []
    color_count, palettes = palette_info
    if used_max_index >= color_count:
        return []

    output_paths: list[Path] = []
    for label, palette_words in palettes.items():
        frame_inputs = [(frame, palette_words) for frame in frames]
        sheet = build_sheet(stem, frame_inputs, label, scale)
        output_path = output_root / f"{stem}-{label}-rgb565.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path)
        output_paths.append(output_path)

    return output_paths


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    stems = set(args.stems or [])
    mpl_paths = sorted((assets_root / "img").glob("*.mpl"))
    if stems:
        mpl_paths = [path for path in mpl_paths if path.stem in stems]
    if args.limit is not None:
        mpl_paths = mpl_paths[: args.limit]

    rendered = 0
    for path in mpl_paths:
        outputs = render_pair(path.stem, assets_root, output_root, args.scale)
        for output in outputs:
            print(output)
            rendered += 1

    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
