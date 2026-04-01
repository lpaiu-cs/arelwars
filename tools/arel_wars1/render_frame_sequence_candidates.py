#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import find_zlib_streams, read_pzx_first_stream, read_pzx_frame_record_stream, read_pzx_meta_sections
from pzx_meta import group_meta_sections, summarize_meta_groups, summarize_sequence_candidates
from render_frame_meta_group_probes import choose_mapper, collect_positions, render_composite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render sequence candidate sheets from frame-linked PZX tail groups")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where sequence probe sheets are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of stems to render")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


LINK_COLORS = {
    "base-frame-delta": (96, 210, 150, 255),
    "chunk-linked-reuse": (120, 180, 255, 255),
    "overlay-track": (255, 184, 88, 255),
    "mixed-or-unknown": (200, 140, 240, 255),
}


def build_candidate_panel(
    base_image: Image.Image,
    combined_image: Image.Image,
    *,
    label: str,
    sublabel: str,
    border_color: tuple[int, int, int, int],
) -> Image.Image:
    margin = 8
    gap = 6
    text_band = 30
    width = max(base_image.width, combined_image.width) + margin * 2
    height = base_image.height + combined_image.height + gap + margin * 2 + text_band
    panel = Image.new("RGBA", (width, height), (20, 20, 24, 255))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=8, outline=border_color, width=2)

    x_base = (width - base_image.width) // 2
    x_combined = (width - combined_image.width) // 2
    y = margin
    panel.alpha_composite(base_image, (x_base, y))
    y += base_image.height + gap
    panel.alpha_composite(combined_image, (x_combined, y))

    draw.text((margin, height - text_band + 2), label, fill=(238, 238, 242, 255))
    draw.text((margin, height - 14), sublabel, fill=(186, 188, 194, 255))
    return panel


def build_sheet(title: str, panels: list[Image.Image]) -> Image.Image:
    margin = 10
    title_band = 20
    columns = max(1, math.ceil(math.sqrt(len(panels))))
    cell_width = max(panel.width for panel in panels) + margin
    cell_height = max(panel.height for panel in panels) + margin
    rows = math.ceil(len(panels) / columns)

    sheet = Image.new(
        "RGBA",
        (columns * cell_width + margin, rows * cell_height + margin + title_band),
        (16, 18, 22, 255),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 2), title, fill=(232, 236, 240, 255))

    for index, panel in enumerate(panels):
        col = index % columns
        row = index // columns
        x = margin + col * cell_width
        y = margin + title_band + row * cell_height
        sheet.alpha_composite(panel, (x, y))

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
    meta_group_summaries = summarize_meta_groups(
        read_pzx_meta_sections(frame_stream.trailing, len(first_stream.chunks)),
        frame_stream.records,
    )
    sequence_summary = summarize_sequence_candidates(meta_group_summaries)

    linked_panels: list[Image.Image] = []
    linked_meta: list[dict[str, object]] = []
    overlay_panels: list[Image.Image] = []
    overlay_meta: list[dict[str, object]] = []

    for group, group_summary in zip(meta_groups, meta_group_summaries):
        group_index = int(group_summary["groupIndex"])
        link_type = str(group_summary["linkType"])
        best_matches = list(group_summary["bestFrameMatches"])
        if link_type not in {"base-frame-delta", "chunk-linked-reuse", "overlay-track"}:
            continue

        tail_items = [item for section in group for item in section.tuples]
        if not tail_items:
            continue

        anchor_index = best_matches[0]["frameIndex"] if best_matches else None
        base_items = list(frame_stream.records[anchor_index].items) if anchor_index is not None else []
        bounds = collect_positions(base_items or tail_items, tail_items if base_items else [], first_stream.chunks)
        base_image = render_composite(base_items, first_stream.chunks, mapper, scale, bounds=bounds)
        combined_image = render_composite([*base_items, *tail_items], first_stream.chunks, mapper, scale, bounds=bounds)

        tail_chunks = sorted({item.chunk_index for item in tail_items})
        label = f"g{group_index:02d} {link_type}"
        sublabel = f"anchor={anchor_index} chunks={tail_chunks[0]}-{tail_chunks[-1]} mapper={mapper_label}"
        panel = build_candidate_panel(
            base_image,
            combined_image,
            label=label,
            sublabel=sublabel,
            border_color=LINK_COLORS[link_type],
        )

        metadata = {
            "groupIndex": group_index,
            "linkType": link_type,
            "anchorFrameIndex": anchor_index,
            "tailChunkRange": [tail_chunks[0], tail_chunks[-1]],
            "tupleCount": len(tail_items),
            "bestFrameMatches": best_matches,
        }
        if link_type == "overlay-track":
            overlay_panels.append(panel)
            overlay_meta.append(metadata)
        else:
            linked_panels.append(panel)
            linked_meta.append(metadata)

    outputs: list[Path] = []
    output_root.mkdir(parents=True, exist_ok=True)

    if linked_panels:
        title = f"{stem} linked frame candidates ({sequence_summary['sequenceKind']}, {sequence_summary['timelineKind']})"
        sheet = build_sheet(title, linked_panels)
        output_path = output_root / f"{stem}-linked-sequence.png"
        sheet.save(output_path)
        outputs.append(output_path)
        (output_root / f"{stem}-linked-sequence.json").write_text(
            json.dumps(linked_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        outputs.append(output_root / f"{stem}-linked-sequence.json")

    if overlay_panels:
        title = f"{stem} overlay sequence candidates ({sequence_summary['timelineKind']})"
        sheet = build_sheet(title, overlay_panels)
        output_path = output_root / f"{stem}-overlay-sequence.png"
        sheet.save(output_path)
        outputs.append(output_path)
        (output_root / f"{stem}-overlay-sequence.json").write_text(
            json.dumps(overlay_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        outputs.append(output_root / f"{stem}-overlay-sequence.json")

    summary_path = output_root / f"{stem}-sequence-summary.json"
    summary_path.write_text(json.dumps(sequence_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    outputs.append(summary_path)

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
