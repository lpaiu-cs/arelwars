#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import find_zlib_streams, read_pzx_first_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render heuristic MPL palette probes for paired PZX assets")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where probe PNGs are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of paired stems to render")
    parser.add_argument("--limit", type=int, help="Optional limit on rendered stems")
    parser.add_argument("--scale", type=int, default=2, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def rgb565(word: int) -> tuple[int, int, int, int]:
    r = ((word >> 11) & 0x1F) * 255 // 31
    g = ((word >> 5) & 0x3F) * 255 // 63
    b = (word & 0x1F) * 255 // 31
    return (r, g, b, 0 if word == 0 else 255)


def render_chunk(chunk, palette_words: list[int], scale: int) -> Image.Image:
    image = Image.new("RGBA", (chunk.width, chunk.height), (0, 0, 0, 0))
    pixels = image.load()
    for y, row in enumerate(chunk.rows):
        for x, value in enumerate(row.decoded):
            pixels[x, y] = rgb565(palette_words[value])
    if scale > 1:
        image = image.resize((chunk.width * scale, chunk.height * scale), Image.Resampling.NEAREST)
    return image


def build_sheet(stem: str, chunks, palette_label: str, scale: int) -> Image.Image:
    margin = 8
    label_band = 18
    columns = max(1, math.ceil(math.sqrt(len(chunks))))
    rendered = [render_chunk(chunk, palette_words, scale) for chunk, palette_words in chunks]
    cell_width = max(image.width for image in rendered) + margin
    cell_height = max(image.height for image in rendered) + margin + label_band
    rows = math.ceil(len(rendered) / columns)

    sheet = Image.new("RGBA", (columns * cell_width + margin, rows * cell_height + margin), (18, 20, 24, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 2), f"{stem} palette {palette_label} (RGB565 heuristic)", fill=(232, 236, 240, 255))

    for index, ((chunk, _palette_words), image) in enumerate(zip(chunks, rendered, strict=True)):
        col = index % columns
        row = index // columns
        x = margin + col * cell_width
        y = margin + 16 + row * cell_height
        sheet.alpha_composite(image, (x, y))
        draw.text((x, y + image.height + 2), f"{chunk.index:02d} {chunk.width}x{chunk.height}", fill=(230, 230, 230, 255))

    return sheet


def regular_mpl_palettes(path: Path, color_count: int) -> dict[str, list[int]] | None:
    words = [struct.unpack("<H", path.read_bytes()[index : index + 2])[0] for index in range(0, path.stat().st_size, 2)]
    expected_words = 2 * color_count + 6
    if len(words) != expected_words:
        return None

    return {
        "a": words[6 : 6 + color_count],
        "b": words[6 + color_count : 6 + 2 * color_count],
    }


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
    if first_stream is None:
        return []

    color_count = max(max(row.decoded) for chunk in first_stream.chunks for row in chunk.rows) + 1
    palettes = regular_mpl_palettes(mpl_path, color_count)
    if palettes is None:
        return []

    output_paths: list[Path] = []
    for label, palette_words in palettes.items():
        chunk_inputs = [(chunk, palette_words) for chunk in first_stream.chunks]
        sheet = build_sheet(stem, chunk_inputs, label, scale)
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
