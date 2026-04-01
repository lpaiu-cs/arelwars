#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from formats import (
    decode_pzx_marker_timing_ms,
    find_zlib_streams,
    read_pzx_first_stream,
    read_pzx_frame_record_stream,
    read_pzx_meta_sections,
)
from pzx_meta import (
    group_meta_sections,
    infer_group_timing,
    infer_loop_summary,
    summarize_meta_groups,
    summarize_sequence_candidates,
)
from render_frame_meta_group_probes import choose_mapper, collect_positions, render_composite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render time-ordered timeline candidate strips for PZX tail metadata")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where timeline strips are written")
    parser.add_argument("--stems", nargs="*", help="Optional list of stems to render")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


GLOBAL_RECORD_DEFAULT_DURATION_MS = 120


def _build_event_entries(
    meta_groups: list[list],
    meta_group_summaries: list[dict[str, object]],
    sequence_summary: dict[str, object],
    frame_records: list,
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
        timing = infer_group_timing(group)
        anchor_record_markers: list[str] = []
        anchor_record_values: list[int] = []
        if anchor_frame_index is not None:
            anchor_record = frame_records[anchor_frame_index]
            anchor_record_markers = [chunk.hex() for chunk in anchor_record.control_chunks]
            anchor_record_values = [
                value
                for value in (decode_pzx_marker_timing_ms(marker_hex) for marker_hex in anchor_record_markers)
                if value is not None
            ]
        events.append(
            {
                "groupIndex": group_index,
                "eventType": event_type,
                "linkType": link_type,
                "anchorFrameIndex": anchor_frame_index,
                "relation": relation,
                "tupleCount": len(tail_items),
                "chunkIndexRange": [chunk_range[0], chunk_range[-1]] if chunk_range else None,
                "durationHintMs": timing["durationHintMs"],
                "timingMarkers": timing["markerHexes"],
                "timingValues": timing["markerValues"],
                "timingExplicitValues": timing["explicitMarkerValues"],
                "timingHasFfSentinel": timing["hasFfSentinel"],
                "anchorRecordMarkers": anchor_record_markers,
                "anchorRecordTimingValues": anchor_record_values,
                "tailItems": tail_items,
            }
        )

    events.sort(key=lambda item: int(item["groupIndex"]))
    return events


def _derive_event_playback(events: list[dict[str, object]]) -> tuple[list[dict[str, object]], int | None]:
    explicit_pool: list[int] = []
    for event in events:
        explicit_pool.extend(int(value) for value in event["timingExplicitValues"])
        explicit_pool.extend(
            int(value) for value in event["anchorRecordTimingValues"] if int(value) not in {0, 255}
        )

    stem_default = max(set(explicit_pool), key=explicit_pool.count) if explicit_pool else None

    for event in events:
        explicit_values = [int(value) for value in event["timingExplicitValues"]]
        anchor_values = [int(value) for value in event["anchorRecordTimingValues"] if int(value) not in {0, 255}]
        if explicit_values:
            event["playbackDurationMs"] = max(explicit_values)
            event["playbackSource"] = "tail-marker"
            continue
        if anchor_values:
            event["playbackDurationMs"] = max(anchor_values)
            event["playbackSource"] = "anchor-record"
            continue
        if 0 in event["timingValues"]:
            event["playbackDurationMs"] = 0
            event["playbackSource"] = "zero-marker"
            continue
        event["playbackDurationMs"] = None
        event["playbackSource"] = "unresolved"

    last_explicit: int | None = None
    for event in events:
        playback_duration = event["playbackDurationMs"]
        if isinstance(playback_duration, int) and playback_duration > 0:
            last_explicit = playback_duration
            continue
        if last_explicit is not None:
            event["playbackDurationMs"] = last_explicit
            event["playbackSource"] = "forward-fill"

    next_explicit: int | None = None
    for event in reversed(events):
        playback_duration = event["playbackDurationMs"]
        if isinstance(playback_duration, int) and playback_duration > 0:
            next_explicit = playback_duration
            continue
        if next_explicit is not None:
            event["playbackDurationMs"] = next_explicit
            event["playbackSource"] = "back-fill"

    for event in events:
        if event["playbackDurationMs"] is None and stem_default is not None:
            event["playbackDurationMs"] = stem_default
            event["playbackSource"] = "stem-default"

    for event in events:
        if event["playbackDurationMs"] is None:
            event["playbackDurationMs"] = GLOBAL_RECORD_DEFAULT_DURATION_MS
            event["playbackSource"] = "global-record-default"

    return (events, stem_default)


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
    events = _build_event_entries(meta_groups, meta_group_summaries, sequence_summary, list(frame_stream.records))
    if not events:
        return []
    events, stem_default_duration = _derive_event_playback(events)
    loop_summary = infer_loop_summary(events, sequence_summary)

    mapper_label, mapper = choose_mapper(stem, assets_root, first_stream)
    panels: list[Image.Image] = []
    event_summaries: list[dict[str, object]] = []
    event_frame_paths: list[str] = []
    event_frame_root = output_root / "frames" / stem
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
        duration_hint = event["playbackDurationMs"]
        footer = event["relation"] or event["linkType"]
        if duration_hint is not None:
            footer = f"{footer} / {duration_hint}ms"
        panels.append(_build_frame_panel(combined, label, sublabel, footer))

        event_frame_root.mkdir(parents=True, exist_ok=True)
        frame_name = f"{len(event_frame_paths):02d}-g{event['groupIndex']:02d}-{event['eventType']}.png"
        frame_path = event_frame_root / frame_name
        combined.save(frame_path)
        event_frame_paths.append(str(Path("frames") / stem / frame_name))

        event_summaries.append(
            {
                "groupIndex": event["groupIndex"],
                "eventType": event["eventType"],
                "linkType": event["linkType"],
                "anchorFrameIndex": anchor,
                "relation": event["relation"],
                "tupleCount": event["tupleCount"],
                "chunkIndexRange": event["chunkIndexRange"],
                "durationHintMs": event["durationHintMs"],
                "playbackDurationMs": event["playbackDurationMs"],
                "playbackSource": event["playbackSource"],
                "timingMarkers": event["timingMarkers"],
                "timingValues": event["timingValues"],
                "timingExplicitValues": event["timingExplicitValues"],
                "anchorRecordMarkers": event["anchorRecordMarkers"],
                "anchorRecordTimingValues": event["anchorRecordTimingValues"],
                "framePath": str(Path("frames") / stem / frame_name),
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
                "stemDefaultDurationMs": stem_default_duration,
                "loopSummary": loop_summary,
                "eventFramePaths": event_frame_paths,
                "events": event_summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return [png_path, json_path, *[output_root / path for path in event_frame_paths]]


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
