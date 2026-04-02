#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import find_zlib_streams, read_mpl, read_pzx_first_stream, read_pzx_simple_placement_stream, rgb565_rgba


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render special packed-pixel probe sheets for unresolved PZX stems")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where probe PNGs are written")
    parser.add_argument("--stems", nargs="*", default=["179"], help="Packed-pixel stems to render")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def adjust_rgba(rgba: tuple[int, int, int, int], factor: float) -> tuple[int, int, int, int]:
    r, g, b, a = rgba
    return (
        max(0, min(255, int(round(r * factor)))),
        max(0, min(255, int(round(g * factor)))),
        max(0, min(255, int(round(b * factor)))),
        a,
    )


def build_special_179_mapper(mpl, variant: str):
    bank_a = list(mpl.bank_a)
    bank_b = list(mpl.bank_b)
    color_count = mpl.color_count

    def direct_bank(label: str):
        palette = bank_a if label == "a" else bank_b

        def mapper(value: int) -> tuple[int, int, int, int]:
            if value <= 0:
                return (0, 0, 0, 0)
            normalized = value - 1
            index = normalized % color_count
            return rgb565_rgba(palette[index])

        return mapper

    if variant == "mod47-bank-a":
        return direct_bank("a")
    if variant == "mod47-bank-b":
        return direct_bank("b")

    def shade_mapper(value: int) -> tuple[int, int, int, int]:
        if value == 0:
            return (0, 0, 0, 0)
        normalized = value - 1
        index = normalized % color_count

        shade_band = min(normalized // color_count, 4)
        palette = bank_b if shade_band in (0, 2) else bank_a
        rgba = rgb565_rgba(palette[index])

        if variant == "mod47-shade":
            factor = [0.74, 0.9, 1.0, 1.14, 1.34][shade_band]
            return adjust_rgba(rgba, factor)

        if variant == "mod47-highlight":
            factor = [0.7, 0.88, 1.0, 1.12, 1.34][shade_band]
            if shade_band == 4:
                base = adjust_rgba(rgba, factor)
                return (
                    min(255, base[0] + 18),
                    min(255, base[1] + 10),
                    min(255, base[2] + 4),
                    base[3],
                )
            return adjust_rgba(rgba, factor)

        return rgba

    return shade_mapper


def render_stem(stem: str, assets_root: Path, output_root: Path, scale: int) -> Path | None:
    pzx_path = assets_root / "img" / f"{stem}.pzx"
    mpl_path = assets_root / "img" / f"{stem}.mpl"
    if not pzx_path.exists() or not mpl_path.exists():
        return None

    mpl = read_mpl(mpl_path.read_bytes())
    if mpl is None:
        return None

    data = pzx_path.read_bytes()
    streams = find_zlib_streams(data)
    if len(streams) < 2:
        return None

    table_span = struct.unpack("<H", data[16:18])[0] >> 6 if len(data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    if first_stream is None:
        return None

    placements = None
    for stream in streams[1:]:
        placements = read_pzx_simple_placement_stream(stream.decoded, len(first_stream.chunks))
        if placements is not None:
            break
    if placements is None:
        return None

    min_x = min(item.x for item in placements)
    min_y = min(item.y for item in placements)
    max_x = max(item.x + first_stream.chunks[item.chunk_index].width for item in placements)
    max_y = max(item.y + first_stream.chunks[item.chunk_index].height for item in placements)
    width = (max_x - min_x) * scale
    height = (max_y - min_y) * scale

    variants = [
        ("mod47-bank-b", build_special_179_mapper(mpl, "mod47-bank-b")),
        ("mod47-bank-a", build_special_179_mapper(mpl, "mod47-bank-a")),
        ("mod47-shade", build_special_179_mapper(mpl, "mod47-shade")),
        ("mod47-highlight", build_special_179_mapper(mpl, "mod47-highlight")),
    ]

    margin = 10
    label_band = 22
    sheet = Image.new("RGBA", (margin + len(variants) * (width + margin), height + label_band + margin * 2), (18, 20, 24, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 3), f"{stem} packed-pixel probes", fill=(232, 236, 240, 255))

    for index, (label, mapper) in enumerate(variants):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for placement in placements:
            chunk = first_stream.chunks[placement.chunk_index]
            chunk_image = Image.new("RGBA", (chunk.width, chunk.height), (0, 0, 0, 0))
            pixels = chunk_image.load()
            for y, row in enumerate(chunk.rows):
                for x, value in enumerate(row.decoded):
                    pixels[x, y] = mapper(value)
            if scale > 1:
                chunk_image = chunk_image.resize((chunk.width * scale, chunk.height * scale), Image.Resampling.NEAREST)
            canvas.alpha_composite(chunk_image, ((placement.x - min_x) * scale, (placement.y - min_y) * scale))

        x = margin + index * (width + margin)
        sheet.alpha_composite(canvas, (x, label_band + margin))
        draw.text((x, label_band - 16), label, fill=(214, 220, 228, 255))

    output_path = output_root / f"{stem}-packed-pixel-probes.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return output_path


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    rendered = 0
    for stem in args.stems:
        output = render_stem(stem, assets_root, output_root, args.scale)
        if output is None:
            continue
        print(output)
        rendered += 1

    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
