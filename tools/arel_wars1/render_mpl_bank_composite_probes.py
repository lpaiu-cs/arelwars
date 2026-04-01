#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import find_zlib_streams, read_mpl, read_pzx_first_stream, read_pzx_frame_record_stream
from render_frame_meta_group_probes import build_mpl_bank_mapper, collect_positions, render_composite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render frame-record probes for MPL bank selection hypotheses")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where probe PNGs are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of stems to render")
    parser.add_argument("--limit", type=int, default=12, help="Maximum number of stems to render")
    parser.add_argument("--frames", type=int, default=8, help="Maximum number of records per stem to render")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def build_sheet(stem: str, frames, chunks, bounds, scale: int, mpl) -> Image.Image:
    mappers = [
        build_mpl_bank_mapper(mpl, mode="bank-a"),
        build_mpl_bank_mapper(mpl, mode="flag-bank"),
        build_mpl_bank_mapper(mpl, mode="flag-invert"),
        build_mpl_bank_mapper(mpl, mode="bank-b"),
    ]
    rendered = []
    for _mode_label, mapper in mappers:
        rendered.append([render_composite(record.items, chunks, mapper, scale, bounds=bounds) for record in frames])

    margin = 10
    label_band = 24
    header_band = 24
    cell_width = max(image.width for column in rendered for image in column)
    cell_height = max(image.height for column in rendered for image in column)
    width = margin + len(mappers) * (cell_width + margin)
    height = header_band + margin + len(frames) * (cell_height + label_band + margin)
    sheet = Image.new("RGBA", (width, height), (18, 20, 24, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 4), f"{stem} MPL bank probes", fill=(232, 236, 240, 255))

    for col, (mode_label, _mapper) in enumerate(mappers):
        x = margin + col * (cell_width + margin)
        draw.text((x, header_band - 16), mode_label, fill=(215, 220, 230, 255))

    for row, record in enumerate(frames):
        y = header_band + margin + row * (cell_height + label_band + margin)
        flagged_count = sum(1 for item in record.items if item.flag > 0)
        draw.text(
            (margin, y - 14),
            f"frame {row:02d} items={len(record.items)} flagged={flagged_count}",
            fill=(175, 182, 192, 255),
        )
        for col, column in enumerate(rendered):
            x = margin + col * (cell_width + margin)
            image = column[row]
            sheet.alpha_composite(image, (x, y))

    return sheet


def render_stem(stem: str, assets_root: Path, output_root: Path, frames_limit: int, scale: int) -> Path | None:
    pzx_path = assets_root / "img" / f"{stem}.pzx"
    mpl_path = assets_root / "img" / f"{stem}.mpl"
    if not pzx_path.exists() or not mpl_path.exists():
        return None

    data = pzx_path.read_bytes()
    mpl = read_mpl(mpl_path.read_bytes())
    if mpl is None:
        return None

    streams = find_zlib_streams(data)
    if len(streams) < 2:
        return None

    table_span = struct.unpack("<H", data[16:18])[0] >> 6 if len(data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    if first_stream is None:
        return None

    max_value = max(max(row.decoded) for chunk in first_stream.chunks for row in chunk.rows)
    if max_value >= mpl.color_count:
        return None

    frame_stream = read_pzx_frame_record_stream(streams[1].decoded, len(first_stream.chunks))
    if frame_stream is None or not frame_stream.records:
        return None

    frames = list(frame_stream.records[:frames_limit])
    all_items = [item for record in frames for item in record.items]
    bounds = collect_positions(all_items, [], first_stream.chunks)

    sheet = build_sheet(stem, frames, first_stream.chunks, bounds, scale, mpl)
    output_path = output_root / f"{stem}-mpl-bank-probes.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return output_path


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    stems = list(args.stems or [])
    if not stems:
        stems = [path.stem for path in sorted((assets_root / "img").glob("*.mpl"))[: args.limit]]
    elif args.limit is not None:
        stems = stems[: args.limit]

    rendered = 0
    for stem in stems:
        output = render_stem(stem, assets_root, output_root, args.frames, args.scale)
        if output is None:
            continue
        print(output)
        rendered += 1

    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
