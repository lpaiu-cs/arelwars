#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import (
    find_zlib_streams,
    get_pzx_meta_effective_tuples,
    MplFile,
    mpl_index_to_rgba,
    read_mpl,
    read_pzx_first_stream,
    read_pzx_frame_record_stream,
    read_pzx_meta_sections,
)
from pzx_meta import classify_group, group_meta_sections


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render frame/tail-group composite probes for PZX metadata")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where probe PNGs are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of stems to render")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def pseudo_color(value: int, *, tail: bool = False) -> tuple[int, int, int, int]:
    if value == 0:
        return (0, 0, 0, 0)
    if tail:
        return ((value * 73) % 256, (96 + value * 29) % 256, (160 + value * 11) % 256, 220)
    return ((value * 53) % 256, (40 + value * 97) % 256, (120 + value * 17) % 256, 255)


def build_mpl_bank_mapper(mpl: MplFile, mode: str = "flag-bank") -> tuple[str, callable]:
    if mode == "bank-a":
        return ("mpl-bank-a", lambda value, **_kwargs: mpl_index_to_rgba(value, mpl.bank_a))
    if mode == "bank-b":
        return ("mpl-bank-b", lambda value, **_kwargs: mpl_index_to_rgba(value, mpl.bank_b))
    if mode == "flag-invert":
        return (
            "mpl-flag-invert",
            lambda value, flag=None, **_kwargs: mpl_index_to_rgba(
                value,
                mpl.bank_a if int(flag or 0) > 0 else mpl.bank_b,
            ),
        )
    return (
        "mpl-flag-bank",
        lambda value, flag=None, **_kwargs: mpl_index_to_rgba(
            value,
            mpl.bank_b if int(flag or 0) > 0 else mpl.bank_a,
        ),
    )


def choose_mapper(stem: str, assets_root: Path, first_stream) -> tuple[str, callable]:
    mpl_path = assets_root / "img" / f"{stem}.mpl"
    max_value = max(max(row.decoded) for chunk in first_stream.chunks for row in chunk.rows)

    if mpl_path.exists():
        mpl = read_mpl(mpl_path.read_bytes())
        if mpl is not None and max_value < mpl.color_count:
            return build_mpl_bank_mapper(mpl, mode="flag-invert")

    return ("pseudo", lambda value, _tail=False: pseudo_color(value, tail=_tail))


def render_chunk(chunk, mapper, scale: int, *, tail: bool = False, flag: int | None = None) -> Image.Image:
    image = Image.new("RGBA", (chunk.width, chunk.height), (0, 0, 0, 0))
    pixels = image.load()
    for y, row in enumerate(chunk.rows):
        for x, value in enumerate(row.decoded):
            try:
                pixels[x, y] = mapper(value, tail=tail, flag=flag)
            except TypeError:
                pixels[x, y] = mapper(value)
    if scale > 1:
        image = image.resize((chunk.width * scale, chunk.height * scale), Image.Resampling.NEAREST)
    return image


def collect_positions(base_items, tail_items, chunks) -> tuple[int, int, int, int]:
    items = [*base_items, *tail_items]
    min_x = min(item.x for item in items)
    min_y = min(item.y for item in items)
    max_x = max(item.x + chunks[item.chunk_index].width for item in items)
    max_y = max(item.y + chunks[item.chunk_index].height for item in items)
    return (min_x, min_y, max_x, max_y)


def render_composite(items, chunks, mapper, scale: int, *, tail: bool = False, bounds=None) -> Image.Image:
    if not items:
        if bounds is None:
            return Image.new("RGBA", (8 * scale, 8 * scale), (0, 0, 0, 0))
        min_x, min_y, max_x, max_y = bounds
        return Image.new("RGBA", ((max_x - min_x) * scale, (max_y - min_y) * scale), (0, 0, 0, 0))

    if bounds is None:
        bounds = collect_positions(items, [], chunks)
    min_x, min_y, max_x, max_y = bounds
    canvas = Image.new("RGBA", ((max_x - min_x) * scale, (max_y - min_y) * scale), (0, 0, 0, 0))

    for item in items:
        chunk = chunks[item.chunk_index]
        chunk_image = render_chunk(chunk, mapper, scale, tail=tail, flag=getattr(item, "flag", None))
        canvas.alpha_composite(chunk_image, ((item.x - min_x) * scale, (item.y - min_y) * scale))

    return canvas


def build_triptych(base_image: Image.Image, tail_image: Image.Image, combined_image: Image.Image, caption: str) -> Image.Image:
    panel_padding = 12
    caption_band = 28
    width = base_image.width + tail_image.width + combined_image.width + panel_padding * 4
    height = max(base_image.height, tail_image.height, combined_image.height) + caption_band + panel_padding * 2
    sheet = Image.new("RGBA", (width, height), (20, 20, 24, 255))
    draw = ImageDraw.Draw(sheet)

    labels = [("base", base_image), ("tail", tail_image), ("combined", combined_image)]
    x = panel_padding
    for label, image in labels:
        y = panel_padding
        sheet.alpha_composite(image, (x, y))
        draw.text((x, y + image.height + 4), label, fill=(240, 240, 240, 255))
        x += image.width + panel_padding

    draw.text((panel_padding, height - 18), caption, fill=(200, 200, 210, 255))
    return sheet


def render_stem(stem: str, assets_root: Path, output_root: Path, scale: int) -> list[Path]:
    pzx_path = assets_root / "img" / f"{stem}.pzx"
    if not pzx_path.exists():
        return []

    data = pzx_path.read_bytes()
    streams = find_zlib_streams(data)
    if len(streams) < 2:
        return []

    table_span = struct.unpack("<H", data[16:18])[0] >> 6 if len(data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    if first_stream is None:
        return []

    frame_stream = read_pzx_frame_record_stream(streams[1].decoded, len(first_stream.chunks))
    if frame_stream is None:
        return []

    mapper_label, mapper = choose_mapper(stem, assets_root, first_stream)
    meta_groups = group_meta_sections(read_pzx_meta_sections(frame_stream.trailing, len(first_stream.chunks)))

    outputs: list[Path] = []
    for group_index, group in enumerate(meta_groups):
        link_type, best_matches = classify_group(group, frame_stream.records)
        if link_type not in {"base-frame-delta", "overlay-track", "chunk-linked-reuse"}:
            continue

        tail_items = [item for section in group for item in get_pzx_meta_effective_tuples(section)]
        if not tail_items:
            continue

        anchor_index = best_matches[0]["frameIndex"] if best_matches else None
        base_items = list(frame_stream.records[anchor_index].items) if anchor_index is not None else []
        bounds = collect_positions(base_items or tail_items, tail_items if base_items else [], first_stream.chunks)
        base_image = render_composite(base_items, first_stream.chunks, mapper, scale, bounds=bounds)
        tail_image = render_composite(tail_items, first_stream.chunks, mapper, scale, tail=True, bounds=bounds)
        combined_image = render_composite([*base_items, *tail_items], first_stream.chunks, mapper, scale, bounds=bounds)

        chunk_range = sorted({item.chunk_index for item in tail_items})
        chunk_label = f"{chunk_range[0]}-{chunk_range[-1]}" if chunk_range else "none"
        caption = f"{stem} group={group_index} type={link_type} anchor={anchor_index} mapper={mapper_label} chunks={chunk_label}"
        sheet = build_triptych(base_image, tail_image, combined_image, caption)
        output_path = output_root / f"{stem}-group{group_index:02d}-{link_type}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path)
        outputs.append(output_path)

    return outputs


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
