#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import find_zlib_streams, read_pzx_first_stream, read_pzx_frame_record_stream, read_pzx_meta_sections
from pzx_meta import group_meta_sections, summarize_meta_groups, summarize_sequence_candidates
from render_frame_meta_group_probes import choose_mapper, collect_positions, render_composite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render time-ordered timeline candidate strips for PZX tail metadata")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where timeline strips are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of stems to render")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def _build_event_entries(
    meta_groups: list[list],
    meta_group_summaries: list[dict[str, object]],
    sequence_summary: dict[str, object],
) -> list[dict[str, object]]:
    overlay_attachment_by_group = {
        int(item["groupIndex"]): item for item in sequence_summary.get("overlayAttachmentsPreview", [])
    }
    events: list[dict[str, object]] = []
    for group, group_summary in zip(meta_groups, meta_group_summaries):
        group_index = int(group_summary["groupIndex"])
        link_type = str(group_summary["linkType"])
        tail_items = [item for section in group for item in section.tuples]
        if not tail_items:
            continue

        event_type = None
        anchor_frame_index = None
        relation = None
        if link_type in {"base-frame-delta", "chunk-linked-reuse"} and group_summary["bestFrameMatches"]:
            event_type = "linked"
            anchor_frame_index = int(group_summary["bestFrameMatches"][0]["frameIndex"])
        elif link_type == "overlay-track":
            event_type = "overlay"
            attachment = overlay_attachment_by_group.get(group_index, {})
            relation = attachment.get("relation")
            nearest_anchor = attachment.get("nearestAnchorFrameIndex")
            anchor_frame_index = int(nearest_anchor) if nearest_anchor is not None else None
        else:
            continue

        chunk_range = sorted({item.chunk_index for item in tail_items})
        events.append(
            {
                "groupIndex": group_index,
                "eventType": event_type,
                "linkType": link_type,
                "anchorFrameIndex": anchor_frame_index,
                "relation": relation,
                "tupleCount": len(tail_items),
                "chunkIndexRange": [chunk_range[0], chunk_range[-1]] if chunk_range else None,
                "tailItems": tail_items,
            }
        )

    events.sort(key=lambda item: int(item["groupIndex"]))
    return events


def _build_frame_panel(image: Image.Image, label: str, sublabel: str, footer: str) -> Image.Image:
    margin = 8
    text_height = 34
    footer_height = 14
    width = image.width + margin * 2
    height = image.height + margin * 2 + text_height + footer_height
    panel = Image.new("RGBA", (width, height), (18, 20, 24, 255))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=8, outline=(112, 154, 255, 255), width=2)
    panel.alpha_composite(image, (margin, margin))
    draw.text((margin, image.height + margin + 2), label, fill=(236, 238, 242, 255))
    draw.text((margin, image.height + margin + 16), sublabel, fill=(186, 190, 198, 255))
    draw.text((margin, height - 12), footer, fill=(142, 146, 154, 255))
    return panel


def _build_strip(title: str, panels: list[Image.Image]) -> Image.Image:
    margin = 10
    gap = 8
    title_band = 20
    width = margin * 2 + sum(panel.width for panel in panels) + gap * max(0, len(panels) - 1)
    height = title_band + margin * 2 + max(panel.height for panel in panels)
    strip = Image.new("RGBA", (width, height), (14, 16, 20, 255))
    draw = ImageDraw.Draw(strip)
    draw.text((margin, 2), title, fill=(232, 236, 240, 255))

    x = margin
    y = title_band + margin
    for panel in panels:
        strip.alpha_composite(panel, (x, y))
        x += panel.width + gap

    return strip


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

    meta_groups = group_meta_sections(read_pzx_meta_sections(frame_stream.trailing, len(first_stream.chunks)))
    meta_group_summaries = summarize_meta_groups(
        read_pzx_meta_sections(frame_stream.trailing, len(first_stream.chunks)),
        frame_stream.records,
    )
    sequence_summary = summarize_sequence_candidates(meta_group_summaries)
    events = _build_event_entries(meta_groups, meta_group_summaries, sequence_summary)
    if not events:
        return []

    mapper_label, mapper = choose_mapper(stem, assets_root, first_stream)
    panels: list[Image.Image] = []
    event_summaries: list[dict[str, object]] = []
    for event in events:
        tail_items = list(event["tailItems"])
        anchor = event["anchorFrameIndex"]
        base_items = list(frame_stream.records[anchor].items) if anchor is not None else []
        bounds = collect_positions(base_items or tail_items, tail_items if base_items else [], first_stream.chunks)
        combined = render_composite([*base_items, *tail_items], first_stream.chunks, mapper, scale, bounds=bounds)

        label = f"g{event['groupIndex']:02d} {event['eventType']}"
        if anchor is None:
            sublabel = f"anchor=None chunks={event['chunkIndexRange'][0]}-{event['chunkIndexRange'][1]}"
        else:
            sublabel = f"anchor={anchor} chunks={event['chunkIndexRange'][0]}-{event['chunkIndexRange'][1]}"
        footer = event["relation"] or event["linkType"]
        panels.append(_build_frame_panel(combined, label, sublabel, footer))

        event_summaries.append(
            {
                "groupIndex": event["groupIndex"],
                "eventType": event["eventType"],
                "linkType": event["linkType"],
                "anchorFrameIndex": anchor,
                "relation": event["relation"],
                "tupleCount": event["tupleCount"],
                "chunkIndexRange": event["chunkIndexRange"],
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    title = f"{stem} timeline strip ({sequence_summary['timelineKind']}, mapper={mapper_label})"
    strip = _build_strip(title, panels)
    png_path = output_root / f"{stem}-timeline-strip.png"
    strip.save(png_path)

    json_path = output_root / f"{stem}-timeline-strip.json"
    json_path.write_text(
        json.dumps(
            {
                "stem": stem,
                "timelineKind": sequence_summary["timelineKind"],
                "sequenceKind": sequence_summary["sequenceKind"],
                "eventCount": len(event_summaries),
                "events": event_summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return [png_path, json_path]


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
