#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image

from formats import find_zlib_streams, read_pzx_first_stream, read_pzx_simple_placement_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render composite probes for simple PZX placement streams")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where composite probe PNGs are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of stems to render")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def rgb565(word: int) -> tuple[int, int, int, int]:
    r = ((word >> 11) & 0x1F) * 255 // 31
    g = ((word >> 5) & 0x3F) * 255 // 63
    b = (word & 0x1F) * 255 // 31
    return (r, g, b, 0 if word == 0 else 255)


def read_mpl_palettes(path: Path) -> tuple[int, dict[str, list[int]]] | None:
    words = [struct.unpack("<H", path.read_bytes()[index : index + 2])[0] for index in range(0, path.stat().st_size, 2)]
    if len(words) < 8 or (len(words) - 6) % 2 != 0:
        return None
    color_count = (len(words) - 6) // 2
    return (
        color_count,
        {
            "a": words[6 : 6 + color_count],
            "b": words[6 + color_count : 6 + 2 * color_count],
        },
    )


def choose_transforms(max_value: int, palette_capacity: int) -> dict[str, callable]:
    if max_value < palette_capacity:
        return {"direct": lambda value: value}
    return {
        "mask1f": lambda value: min(value & 0x1F, palette_capacity - 1),
        "mask3fclip": lambda value: min(value & 0x3F, palette_capacity - 1),
        "modcap": lambda value: value % palette_capacity,
        "clamp": lambda value: min(value, palette_capacity - 1),
    }


def render_chunk(chunk, palette_words: list[int], transform, scale: int) -> Image.Image:
    image = Image.new("RGBA", (chunk.width, chunk.height), (0, 0, 0, 0))
    pixels = image.load()
    for y, row in enumerate(chunk.rows):
        for x, value in enumerate(row.decoded):
            pixels[x, y] = rgb565(palette_words[transform(value)])
    if scale > 1:
        image = image.resize((chunk.width * scale, chunk.height * scale), Image.Resampling.NEAREST)
    return image


def render_stem(stem: str, assets_root: Path, output_root: Path, scale: int) -> list[Path]:
    pzx_path = assets_root / "img" / f"{stem}.pzx"
    mpl_path = assets_root / "img" / f"{stem}.mpl"
    if not pzx_path.exists() or not mpl_path.exists():
        return []

    pzx_data = pzx_path.read_bytes()
    streams = find_zlib_streams(pzx_data)
    if len(streams) < 2:
        return []

    table_span = struct.unpack("<H", pzx_data[16:18])[0] >> 6 if len(pzx_data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    if first_stream is None:
        return []

    placements = None
    for item in streams[1:]:
        placements = read_pzx_simple_placement_stream(item.decoded, len(first_stream.chunks))
        if placements is not None:
            break
    if placements is None:
        return []

    palette_info = read_mpl_palettes(mpl_path)
    if palette_info is None:
        return []
    palette_capacity, palettes = palette_info

    max_value = max(max(row.decoded) for chunk in first_stream.chunks for row in chunk.rows)
    transforms = choose_transforms(max_value, palette_capacity)

    min_x = min(placement.x for placement in placements)
    min_y = min(placement.y for placement in placements)
    max_x = max(placement.x + first_stream.chunks[placement.chunk_index].width for placement in placements)
    max_y = max(placement.y + first_stream.chunks[placement.chunk_index].height for placement in placements)

    output_paths: list[Path] = []
    for palette_label, palette_words in palettes.items():
        for transform_label, transform in transforms.items():
            canvas = Image.new("RGBA", ((max_x - min_x) * scale, (max_y - min_y) * scale), (0, 0, 0, 0))
            for placement in placements:
                chunk = first_stream.chunks[placement.chunk_index]
                chunk_image = render_chunk(chunk, palette_words, transform, scale)
                canvas.alpha_composite(chunk_image, ((placement.x - min_x) * scale, (placement.y - min_y) * scale))

            output_path = output_root / f"{stem}-{palette_label}-{transform_label}.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(output_path)
            output_paths.append(output_path)

    return output_paths


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    stems = set(args.stems or [])
    pzx_paths = sorted((assets_root / "img").glob("*.pzx"))
    if stems:
        pzx_paths = [path for path in pzx_paths if path.stem in stems]

    rendered = 0
    for path in pzx_paths:
        outputs = render_stem(path.stem, assets_root, output_root, args.scale)
        for output in outputs:
            print(output)
            rendered += 1

    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
