#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import struct
from typing import Any

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
MAX_DONOR_SCORE = 210


@dataclass
class StemRenderCandidate:
    stem: str
    first_stream: Any
    frame_stream: Any
    meta_group_summaries: list[dict[str, object]]
    sequence_summary: dict[str, object]
    events: list[dict[str, object]]
    stem_default_duration_ms: int | None
    loop_summary: dict[str, object] | None
    mapper_label: str
    mapper: Any


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


def _has_local_timing(events: list[dict[str, object]]) -> bool:
    for event in events:
        if _event_has_explicit_local_timing(event):
            return True
    return False


def _event_has_explicit_local_timing(event: dict[str, object]) -> bool:
    if event["timingExplicitValues"]:
        return True
    return any(int(value) not in {0, 255} for value in event["anchorRecordTimingValues"])


def _dominant_duration(values: list[int]) -> int | None:
    positives = [int(value) for value in values if int(value) > 0]
    if not positives:
        return None
    return max(set(positives), key=positives.count)


def _normalized_index(length: int, index: int, target_length: int) -> int:
    if length <= 1 or target_length <= 1:
        return 0
    return round(index * (length - 1) / (target_length - 1))


def _event_signature_distance(target_event: dict[str, object], donor_event: dict[str, object]) -> int:
    distance = 0
    if str(target_event["eventType"]) != str(donor_event["eventType"]):
        distance += 24
    if str(target_event.get("relation")) != str(donor_event.get("relation")):
        distance += 10

    target_tuple_count = int(target_event.get("tupleCount") or 0)
    donor_tuple_count = int(donor_event.get("tupleCount") or 0)
    distance += abs(target_tuple_count - donor_tuple_count)

    target_chunk_range = target_event.get("chunkIndexRange")
    donor_chunk_range = donor_event.get("chunkIndexRange")
    if isinstance(target_chunk_range, list) and isinstance(donor_chunk_range, list):
        target_width = int(target_chunk_range[1]) - int(target_chunk_range[0]) + 1
        donor_width = int(donor_chunk_range[1]) - int(donor_chunk_range[0]) + 1
        distance += abs(target_width - donor_width) * 3
        distance += min(abs(int(target_chunk_range[0]) - int(donor_chunk_range[0])), 12)
    elif target_chunk_range != donor_chunk_range:
        distance += 6

    return distance


def _timing_donor_score(target: StemRenderCandidate, donor: StemRenderCandidate) -> int | None:
    target_timeline_kind = str(target.sequence_summary.get("timelineKind"))
    donor_timeline_kind = str(donor.sequence_summary.get("timelineKind"))
    if target_timeline_kind != donor_timeline_kind:
        return None

    target_events = target.events
    donor_events = donor.events
    if not target_events or not donor_events:
        return None

    if target_timeline_kind == "overlay-track-only":
        score = abs(len(target_events) - len(donor_events)) * 10
        comparison_count = max(len(target_events), len(donor_events))
        for index in range(comparison_count):
            target_index = _normalized_index(len(target_events), index, comparison_count)
            donor_index = _normalized_index(len(donor_events), index, comparison_count)
            target_event = target_events[target_index]
            donor_event = donor_events[donor_index]
            score += abs(int(target_event.get("tupleCount") or 0) - int(donor_event.get("tupleCount") or 0))

            target_chunk_range = target_event.get("chunkIndexRange")
            donor_chunk_range = donor_event.get("chunkIndexRange")
            if isinstance(target_chunk_range, list) and isinstance(donor_chunk_range, list):
                target_width = int(target_chunk_range[1]) - int(target_chunk_range[0]) + 1
                donor_width = int(donor_chunk_range[1]) - int(donor_chunk_range[0]) + 1
                score += abs(target_width - donor_width) * 2
        return score

    score = abs(len(target_events) - len(donor_events)) * 8
    comparison_count = max(len(target_events), len(donor_events))
    for index in range(comparison_count):
        target_index = _normalized_index(len(target_events), index, comparison_count)
        donor_index = _normalized_index(len(donor_events), index, comparison_count)
        score += _event_signature_distance(target_events[target_index], donor_events[donor_index])
    return score


def _resample_durations(durations: list[int], count: int) -> list[int]:
    if not durations or count <= 0:
        return []
    if count == 1:
        return [int(durations[0])]
    return [int(durations[_normalized_index(len(durations), index, count)]) for index in range(count)]


def _median_duration(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(int(value) for value in values)
    center = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[center]
    return round((ordered[center - 1] + ordered[center]) / 2)


def _build_overlay_prototypes(candidates: list[StemRenderCandidate]) -> dict[tuple[int, int], int]:
    buckets: dict[tuple[int, int], list[int]] = {}
    for candidate in candidates:
        for event in candidate.events:
            if str(event["eventType"]) != "overlay" or not _event_has_explicit_local_timing(event):
                continue
            key = (int(event.get("tupleCount") or 0), len(event.get("timingMarkers") or []))
            buckets.setdefault(key, []).append(int(event["playbackDurationMs"]))

    prototypes: dict[tuple[int, int], int] = {}
    for key, durations in buckets.items():
        if not durations:
            continue
        spread = max(durations) - min(durations)
        if spread > 20:
            continue
        median = _median_duration(durations)
        if median is not None:
            prototypes[key] = median
    return prototypes


def _apply_overlay_prototypes(candidates: list[StemRenderCandidate]) -> None:
    prototypes = _build_overlay_prototypes(candidates)
    for candidate in candidates:
        for event in candidate.events:
            if str(event["eventType"]) != "overlay":
                continue
            if _event_has_explicit_local_timing(event):
                continue
            if str(event["playbackSource"]) not in {"global-record-default", "stem-default"}:
                continue

            key = (int(event.get("tupleCount") or 0), len(event.get("timingMarkers") or []))
            duration = prototypes.get(key)
            if duration is None or int(event["playbackDurationMs"]) == duration:
                continue

            event["playbackDurationMs"] = duration
            event["playbackSource"] = "overlay-prototype"
            event["playbackPrototypeKey"] = f"{key[0]}x{key[1]}"


def _apply_opaque_timing_cues(candidates: list[StemRenderCandidate]) -> None:
    for candidate in candidates:
        cues: list[tuple[int, int]] = []
        for group in candidate.meta_group_summaries:
            if str(group.get("linkType")) != "opaque-only":
                continue
            explicit_values = [int(value) for value in group.get("timingExplicitValues", [])]
            if not explicit_values:
                continue
            cues.append((int(group["groupIndex"]), max(explicit_values)))

        if not cues:
            continue

        for event in candidate.events:
            if str(event["playbackSource"]) not in {"global-record-default", "stem-default"}:
                continue
            preceding = [
                (int(event["groupIndex"]) - cue_group_index, cue_duration)
                for cue_group_index, cue_duration in cues
                if cue_group_index < int(event["groupIndex"])
            ]
            if not preceding:
                continue
            preceding.sort(key=lambda item: item[0])
            gap, cue_duration = preceding[0]
            if gap > 2:
                continue

            event["playbackDurationMs"] = cue_duration
            event["playbackSource"] = "opaque-cue"


def _apply_donor_timings(candidates: list[StemRenderCandidate]) -> None:
    donors = [candidate for candidate in candidates if _has_local_timing(candidate.events)]
    for candidate in candidates:
        if _has_local_timing(candidate.events):
            continue

        scored_donors: list[tuple[int, StemRenderCandidate]] = []
        for donor in donors:
            score = _timing_donor_score(candidate, donor)
            if score is None:
                continue
            scored_donors.append((score, donor))

        if not scored_donors:
            continue

        scored_donors.sort(key=lambda item: (item[0], item[1].stem))
        best_score, best_donor = scored_donors[0]
        if best_score > MAX_DONOR_SCORE:
            continue

        donor_durations = [int(event["playbackDurationMs"]) for event in best_donor.events if event["playbackDurationMs"] is not None]
        proposed_durations = _resample_durations(donor_durations, len(candidate.events))
        current_durations = [int(event["playbackDurationMs"]) for event in candidate.events]
        if not proposed_durations or proposed_durations == current_durations:
            continue

        for event, duration in zip(candidate.events, proposed_durations):
            event["playbackDurationMs"] = duration
            event["playbackSource"] = "donor-stem"
            event["playbackDonorStem"] = best_donor.stem
            event["playbackDonorScore"] = best_score

        if candidate.stem_default_duration_ms is None:
            candidate.stem_default_duration_ms = best_donor.stem_default_duration_ms or _dominant_duration(proposed_durations)


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


def build_stem_candidate(stem: str, assets_root: Path) -> StemRenderCandidate | None:
    pzx_path = assets_root / "img" / f"{stem}.pzx"
    if not pzx_path.exists():
        return None

    data = pzx_path.read_bytes()
    streams = find_zlib_streams(data)
    if len(streams) < 2:
        return None

    table_span = struct.unpack("<H", data[16:18])[0] >> 6 if len(data) >= 18 else 0
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span)
    if first_stream is None:
        return None

    frame_stream = read_pzx_frame_record_stream(streams[1].decoded, len(first_stream.chunks))
    if frame_stream is None:
        return None

    meta_groups = group_meta_sections(read_pzx_meta_sections(frame_stream.trailing, len(first_stream.chunks)))
    meta_group_summaries = summarize_meta_groups(
        read_pzx_meta_sections(frame_stream.trailing, len(first_stream.chunks)),
        frame_stream.records,
    )
    sequence_summary = summarize_sequence_candidates(meta_group_summaries)
    events = _build_event_entries(meta_groups, meta_group_summaries, sequence_summary, list(frame_stream.records))
    if not events:
        return None
    events, stem_default_duration = _derive_event_playback(events)
    loop_summary = infer_loop_summary(events, sequence_summary)

    mapper_label, mapper = choose_mapper(stem, assets_root, first_stream)
    return StemRenderCandidate(
        stem=stem,
        first_stream=first_stream,
        frame_stream=frame_stream,
        meta_group_summaries=meta_group_summaries,
        sequence_summary=sequence_summary,
        events=events,
        stem_default_duration_ms=stem_default_duration,
        loop_summary=loop_summary,
        mapper_label=mapper_label,
        mapper=mapper,
    )


def render_candidate(candidate: StemRenderCandidate, output_root: Path, scale: int) -> list[Path]:
    stem = candidate.stem
    panels: list[Image.Image] = []
    event_summaries: list[dict[str, object]] = []
    event_frame_paths: list[str] = []
    event_frame_root = output_root / "frames" / stem
    for event in candidate.events:
        tail_items = list(event["tailItems"])
        anchor = event["anchorFrameIndex"]
        base_items = list(candidate.frame_stream.records[anchor].items) if anchor is not None else []
        bounds = collect_positions(base_items or tail_items, tail_items if base_items else [], candidate.first_stream.chunks)
        combined = render_composite([*base_items, *tail_items], candidate.first_stream.chunks, candidate.mapper, scale, bounds=bounds)

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

        summary = {
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
        if event.get("playbackDonorStem") is not None:
            summary["playbackDonorStem"] = event["playbackDonorStem"]
        if event.get("playbackDonorScore") is not None:
            summary["playbackDonorScore"] = event["playbackDonorScore"]
        event_summaries.append(summary)

    output_root.mkdir(parents=True, exist_ok=True)
    title = f"{stem} timeline strip ({candidate.sequence_summary['timelineKind']}, mapper={candidate.mapper_label})"
    strip = _build_strip(title, panels)
    png_path = output_root / f"{stem}-timeline-strip.png"
    strip.save(png_path)

    json_path = output_root / f"{stem}-timeline-strip.json"
    json_path.write_text(
        json.dumps(
            {
                "stem": stem,
                "timelineKind": candidate.sequence_summary["timelineKind"],
                "sequenceKind": candidate.sequence_summary["sequenceKind"],
                "eventCount": len(event_summaries),
                "stemDefaultDurationMs": candidate.stem_default_duration_ms,
                "loopSummary": candidate.loop_summary,
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

    candidates: list[StemRenderCandidate] = []
    for path in pzx_paths:
        candidate = build_stem_candidate(path.stem, assets_root)
        if candidate is not None:
            candidates.append(candidate)

    _apply_overlay_prototypes(candidates)
    _apply_opaque_timing_cues(candidates)
    _apply_donor_timings(candidates)

    rendered = 0
    for candidate in candidates:
        outputs = render_candidate(candidate, output_root, args.scale)
        for output in outputs:
            print(output)
            rendered += 1

    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
