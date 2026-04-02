#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from formats import (
    read_pzx_embedded_resource,
    read_pzx_indexed_animation_clip_stream,
    read_pzx_indexed_pzf_frame_stream,
    read_pzx_pzd_resource,
    read_pzx_root_segments,
)

DEFAULT_REGRESSION_STEMS: dict[str, str] = {
    "082": "Sanity-check native PZF frameCount against native PZA frameIndex range.",
    "084": "Mixed anchor and overlay stem with explicit zero-duration cue and loop hypothesis.",
    "208": "Base-frame-delta sample for separating frame-linked reuse from secondary envelopes.",
    "209": "Single-anchor-with-overlays sample for repeated overlay cadence against native PZA delays.",
    "215": "Single-anchor cadence sample with repeated same-frame timing and minimal pose churn.",
    "226": "Mixed anchor and overlay donor stem for long overlay-run comparison.",
    "230": "Late-frame contiguous loop candidate for native hold and wrap behavior.",
    "240": "Overlay-heavy sample for separating base timing from secondary effect cadence.",
}
DIRECT_PLAYBACK_SOURCES = {"tail-marker", "anchor-record", "zero-marker"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare selected origin/main heuristic timeline artifacts against native-equivalent PZA/PZF parsing."
    )
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Path to write JSON report")
    parser.add_argument("--main-ref", default="origin/main", help="Git ref to read main-branch artifacts from")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root used for git show calls",
    )
    parser.add_argument(
        "--stems",
        nargs="*",
        default=list(DEFAULT_REGRESSION_STEMS),
        help="Three-digit AW1 image stems to compare",
    )
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_stem(stem: str) -> str:
    value = stem.strip()
    if not value:
        raise ValueError("Empty stem is not allowed")
    if value.isdigit():
        return f"{int(value):03d}"
    return value


def git_show_json(repo_root: Path, git_ref: str, path: str) -> tuple[dict[str, object] | None, str | None]:
    completed = subprocess.run(
        ["git", "show", f"{git_ref}:{path}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        return None, completed.stderr.strip() or f"git show failed for {path}"
    return json.loads(completed.stdout), None


def summarize_pza_delays(decoded) -> dict[str, object]:
    delay_histogram = Counter(frame.delay for clip in decoded.clips for frame in clip.frames)
    clip_frame_counts = [clip.frame_count for clip in decoded.clips]
    clip_delay_previews = [[frame.delay for frame in clip.frames[:12]] for clip in decoded.clips[:8]]
    clip_frame_index_previews = [[frame.frame_index for frame in clip.frames[:12]] for clip in decoded.clips[:8]]
    return {
        "clipCount": decoded.clip_count,
        "totalFrameCount": decoded.total_frame_count,
        "clipFrameCountRange": [min(clip_frame_counts), max(clip_frame_counts)],
        "frameIndexRange": list(decoded.frame_index_range),
        "delayValues": sorted(delay_histogram),
        "delayHistogram": {str(key): delay_histogram[key] for key in sorted(delay_histogram)},
        "controlValues": list(decoded.control_values),
        "nonzeroControlCount": decoded.nonzero_control_count,
        "clipFrameCountsPreview": clip_frame_counts[:12],
        "clipDelayPreview": clip_delay_previews,
        "clipFrameIndexPreview": clip_frame_index_previews,
    }


def summarize_best_clip_alignment(decoded, timeline: dict[str, object] | None) -> dict[str, object] | None:
    if timeline is None:
        return None

    anchor_frames = sorted(
        {
            int(event["anchorFrameIndex"])
            for event in timeline.get("events", [])
            if event.get("anchorFrameIndex") is not None
        }
    )
    if not anchor_frames:
        return None

    event_count = timeline.get("eventCount")
    best_summary = None
    best_score = None
    for clip_index, clip in enumerate(decoded.clips):
        clip_frame_indices = [frame.frame_index for frame in clip.frames]
        clip_frame_index_set = set(clip_frame_indices)
        anchor_set = set(anchor_frames)
        overlap = sorted(anchor_set & clip_frame_index_set)
        coverage = len(overlap) / len(anchor_set)
        clip_overlap_ratio = len(overlap) / len(clip_frame_index_set)
        frame_count_delta = None if event_count is None else abs(int(event_count) - clip.frame_count)
        score = (
            coverage,
            len(overlap),
            clip_overlap_ratio,
            -1 if frame_count_delta is None else -frame_count_delta,
            -clip_index,
        )
        if best_score is not None and score <= best_score:
            continue
        best_score = score
        best_summary = {
            "clipIndex": clip_index,
            "clipFrameCount": clip.frame_count,
            "clipFrameIndices": clip_frame_indices,
            "clipDelaySequence": [frame.delay for frame in clip.frames],
            "heuristicAnchorFrames": anchor_frames,
            "anchorOverlapFrames": overlap,
            "anchorCoverageRatio": round(coverage, 3),
            "clipOverlapRatio": round(clip_overlap_ratio, 3),
            "eventCountDelta": frame_count_delta,
        }

    return best_summary


def summarize_pzf(decoded) -> dict[str, object]:
    selector_last_byte_counts = Counter()
    extra_length_histogram = Counter()
    for frame in decoded.frames:
        for subframe in frame.subframes:
            if not subframe.extra:
                continue
            selector_last_byte_counts[f"{subframe.extra[-1]:02x}"] += 1
            extra_length_histogram[len(subframe.extra)] += 1

    return {
        "frameCount": decoded.frame_count,
        "totalSubFrameCount": decoded.total_subframe_count,
        "subFrameCountRange": list(decoded.subframe_count_range),
        "frameLengthRange": list(decoded.frame_length_range),
        "bboxTotalRange": list(decoded.bbox_total_range),
        "subFrameIndexRange": None if decoded.subframe_index_range is None else list(decoded.subframe_index_range),
        "xRange": None if decoded.x_range is None else list(decoded.x_range),
        "yRange": None if decoded.y_range is None else list(decoded.y_range),
        "extraFlagValues": list(decoded.extra_flag_values),
        "nonzeroExtraCount": decoded.nonzero_extra_count,
        "maxExtraLen": decoded.max_extra_len,
        "extraLengthHistogram": {str(key): extra_length_histogram[key] for key in sorted(extra_length_histogram)},
        "extraLastByteCounts": dict(sorted(selector_last_byte_counts.items())),
        "framePreview": [
            {
                "index": index,
                "subFrameCount": frame.subframe_count,
                "bboxTotalCount": frame.bbox_total_count,
                "subframesPreview": [
                    {
                        "subFrameIndex": subframe.subframe_index,
                        "x": subframe.x,
                        "y": subframe.y,
                        "extraFlag": subframe.extra_flag,
                        "extraHex": subframe.extra.hex(),
                    }
                    for subframe in frame.subframes[:8]
                ],
            }
            for index, frame in enumerate(decoded.frames[:6])
        ],
    }


def summarize_main_timeline(timeline: dict[str, object], stem_bank_states: dict[str, int] | None) -> dict[str, object]:
    events = timeline.get("events", [])
    playback_values = Counter()
    explicit_timing_values = Counter()
    marker_counts = Counter()
    playback_source_counts = Counter()
    event_type_counts = Counter()
    link_type_counts = Counter()
    anchor_frame_indices: list[int] = []
    bank_state_counts = Counter()

    for event in events:
        if "playbackDurationMs" in event and event["playbackDurationMs"] is not None:
            playback_values[int(event["playbackDurationMs"])] += 1
        for value in event.get("timingExplicitValues", []):
            explicit_timing_values[int(value)] += 1
        for marker in event.get("timingMarkers", []):
            marker_counts[str(marker)] += 1
        playback_source = event.get("playbackSource")
        if playback_source:
            playback_source_counts[str(playback_source)] += 1
        event_type = event.get("eventType")
        if event_type:
            event_type_counts[str(event_type)] += 1
        link_type = event.get("linkType")
        if link_type:
            link_type_counts[str(link_type)] += 1
        anchor_frame_index = event.get("anchorFrameIndex")
        if anchor_frame_index is not None:
            anchor_frame_indices.append(int(anchor_frame_index))
        bank_state_id = event.get("bankStateId")
        if bank_state_id:
            bank_state_counts[str(bank_state_id)] += 1

    return {
        "timelineKind": timeline.get("timelineKind"),
        "sequenceKind": timeline.get("sequenceKind"),
        "eventCount": timeline.get("eventCount"),
        "loopSummary": timeline.get("loopSummary"),
        "playbackDurationValues": sorted(playback_values),
        "playbackDurationHistogram": {str(key): playback_values[key] for key in sorted(playback_values)},
        "explicitTimingValues": sorted(explicit_timing_values),
        "explicitTimingHistogram": {str(key): explicit_timing_values[key] for key in sorted(explicit_timing_values)},
        "timingMarkerCounts": dict(sorted(marker_counts.items())),
        "playbackSourceCounts": dict(sorted(playback_source_counts.items())),
        "eventTypeCounts": dict(sorted(event_type_counts.items())),
        "linkTypeCounts": dict(sorted(link_type_counts.items())),
        "anchorFrameIndices": sorted(set(anchor_frame_indices)),
        "anchorFrameRange": None if not anchor_frame_indices else [min(anchor_frame_indices), max(anchor_frame_indices)],
        "eventBankStateCounts": dict(sorted(bank_state_counts.items())),
        "renderSemanticsStemStateCounts": stem_bank_states,
    }


def compare_native_vs_main(
    stem: str,
    native_summary: dict[str, object],
    main_summary: dict[str, object] | None,
) -> dict[str, object]:
    notes: list[str] = []

    native_pza = native_summary.get("pza")
    native_pzf = native_summary.get("pzf")
    if main_summary is None:
        return {
            "nativeDelayOverlapWithHeuristicPlayback": [],
            "nativeDelayOverlapWithHeuristicExplicit": [],
            "anchorFramesWithinNativePzfFramePool": None,
            "heuristicUsesNonDirectSources": None,
            "heuristicNonDirectSources": [],
            "notes": ["origin/main timeline artifact is missing for this stem."],
        }

    playback_values = {int(value) for value in main_summary["playbackDurationValues"]}
    explicit_values = {int(value) for value in main_summary["explicitTimingValues"]}
    non_direct_sources = sorted(
        source for source in main_summary["playbackSourceCounts"] if source not in DIRECT_PLAYBACK_SOURCES
    )
    heuristic_uses_non_direct_sources = bool(non_direct_sources)

    native_delay_values: set[int] = set()
    if native_pza is not None:
        native_delay_values = {int(value) for value in native_pza["delayValues"]}
        if native_delay_values:
            notes.append(
                "Native PZA delay values are "
                + ", ".join(str(value) for value in sorted(native_delay_values))
                + "."
            )
    else:
        notes.append("No embedded PZA was found, so timing comparison is limited to PZF structure and heuristic strips.")

    overlap_playback = sorted(native_delay_values & playback_values)
    overlap_explicit = sorted(native_delay_values & explicit_values)
    if overlap_explicit:
        notes.append(
            "Heuristic explicit timing markers overlap native delays at "
            + ", ".join(str(value) for value in overlap_explicit)
            + "."
        )
    elif explicit_values and native_delay_values:
        notes.append("Heuristic explicit timing markers do not directly match native PZA delays in this stem.")

    if heuristic_uses_non_direct_sources:
        notes.append(
            "Heuristic playback depends on non-direct sources: " + ", ".join(non_direct_sources) + "."
        )

    anchor_frames_within_native_pzf_pool: bool | None = None
    anchor_frame_range = main_summary.get("anchorFrameRange")
    if anchor_frame_range is not None and native_pzf is not None and native_pzf.get("frameCount") is not None:
        anchor_frames_within_native_pzf_pool = int(anchor_frame_range[1]) < int(native_pzf["frameCount"])
        if not anchor_frames_within_native_pzf_pool:
            notes.append(
                "Heuristic anchor frames reach beyond the native PZF frame pool; treat the strip as an unstable view."
            )

    render_semantics_states = main_summary.get("renderSemanticsStemStateCounts") or {}
    if render_semantics_states:
        state_labels = ", ".join(f"{key}={value}" for key, value in sorted(render_semantics_states.items()))
        notes.append("Main render semantics export state counts: " + state_labels + ".")

    best_clip_alignment = native_summary.get("bestClipAlignment")
    if best_clip_alignment is not None:
        if float(best_clip_alignment["anchorCoverageRatio"]) >= 1.0:
            notes.append(
                "Heuristic anchor frames all land inside native clip "
                f"{best_clip_alignment['clipIndex']}."
            )
        event_count_delta = best_clip_alignment.get("eventCountDelta")
        if event_count_delta is not None and int(event_count_delta) >= 3:
            notes.append(
                "Heuristic event count is much larger than the closest native clip frame count; "
                "the strip is likely subdividing a shorter native clip with overlay/effect events."
            )

    return {
        "nativeDelayOverlapWithHeuristicPlayback": overlap_playback,
        "nativeDelayOverlapWithHeuristicExplicit": overlap_explicit,
        "anchorFramesWithinNativePzfFramePool": anchor_frames_within_native_pzf_pool,
        "heuristicUsesNonDirectSources": heuristic_uses_non_direct_sources,
        "heuristicNonDirectSources": non_direct_sources,
        "notes": notes,
    }


def analyze_stem(
    assets_root: Path,
    stem: str,
    *,
    main_timeline: dict[str, object] | None,
    stem_bank_states: dict[str, int] | None,
) -> dict[str, object]:
    pzx_path = assets_root / "img" / f"{stem}.pzx"
    data = pzx_path.read_bytes()
    root_segments = read_pzx_root_segments(data)
    if root_segments is None:
        raise ValueError(f"{pzx_path} does not expose a native-recognized PZX root layout")

    pzd_summary = None
    max_subframe_index = None
    if root_segments.pzd_offset is not None and root_segments.pzd_end is not None:
        pzd_resource = read_pzx_pzd_resource(data, root_segments.pzd_offset, root_segments.pzd_end)
        if pzd_resource is not None:
            pzd_summary = {
                "typeCode": pzd_resource.type_code,
                "layout": pzd_resource.layout,
                "contentCount": pzd_resource.content_count,
                "imageCount": pzd_resource.image_count,
                "flags": pzd_resource.flags,
                "indexOffsetMode": pzd_resource.index_offset_mode,
                "zlibStreamCount": len(pzd_resource.zlib_streams),
            }
            max_subframe_index = int(pzd_resource.image_count) - 1

    pzf_summary = None
    if root_segments.pzf_offset is not None:
        pzf_resource = read_pzx_embedded_resource(data, root_segments.pzf_offset, "pzf")
        if pzf_resource is not None:
            pzf_decoded = read_pzx_indexed_pzf_frame_stream(
                pzf_resource.payload,
                pzf_resource.index_offsets,
                pzf_resource.format_variant,
                max_subframe_index=max_subframe_index,
            )
            if pzf_decoded is not None:
                pzf_summary = {
                    "storageMode": pzf_resource.storage_mode,
                    "formatVariant": pzf_resource.format_variant,
                    **summarize_pzf(pzf_decoded),
                }

    pza_summary = None
    pza_clip_alignment = None
    if root_segments.pza_offset is not None:
        pza_resource = read_pzx_embedded_resource(data, root_segments.pza_offset, "pza")
        if pza_resource is not None:
            pza_decoded = read_pzx_indexed_animation_clip_stream(pza_resource.payload, pza_resource.index_offsets)
            if pza_decoded is not None:
                pza_summary = {
                    "storageMode": pza_resource.storage_mode,
                    "formatVariant": pza_resource.format_variant,
                    **summarize_pza_delays(pza_decoded),
                }
                pza_clip_alignment = summarize_best_clip_alignment(pza_decoded, main_timeline)

    main_summary = None
    if main_timeline is not None:
        main_summary = summarize_main_timeline(main_timeline, stem_bank_states)

    native_summary = {
        "path": str(pzx_path),
        "rootLayout": root_segments.layout,
        "focus": DEFAULT_REGRESSION_STEMS.get(stem),
        "pzd": pzd_summary,
        "pzf": pzf_summary,
        "pza": pza_summary,
        "bestClipAlignment": pza_clip_alignment,
    }

    return {
        "stem": stem,
        "native": native_summary,
        "mainHeuristic": main_summary,
        "comparison": compare_native_vs_main(stem, native_summary, main_summary),
    }


def main() -> None:
    args = parse_args()
    stems = [normalize_stem(stem) for stem in args.stems]

    render_semantics, render_semantics_error = git_show_json(
        args.repo_root,
        args.main_ref,
        "recovery/arel_wars1/parsed_tables/AW1.render_semantics.json",
    )
    stem_state_counts = {}
    if render_semantics is not None:
        stem_state_counts = (
            render_semantics.get("mplBankSwitching", {}).get("stemStateCounts", {})  # type: ignore[assignment]
        )

    entries: list[dict[str, object]] = []
    missing_timelines: list[str] = []
    for stem in stems:
        timeline_path = f"recovery/arel_wars1/timeline_candidate_strips/{stem}-timeline-strip.json"
        main_timeline, timeline_error = git_show_json(args.repo_root, args.main_ref, timeline_path)
        if main_timeline is None:
            missing_timelines.append(stem)
        entry = analyze_stem(
            args.assets_root,
            stem,
            main_timeline=main_timeline,
            stem_bank_states=stem_state_counts.get(stem),
        )
        if timeline_error is not None:
            entry["mainTimelineError"] = timeline_error
        entries.append(entry)

    aggregate_native_delay_values = sorted(
        {
            int(value)
            for entry in entries
            for value in (entry.get("native", {}).get("pza", {}) or {}).get("delayValues", [])
        }
    )
    aggregate_playback_values = sorted(
        {
            int(value)
            for entry in entries
            for value in (entry.get("mainHeuristic") or {}).get("playbackDurationValues", [])
        }
    )
    aggregate_explicit_values = sorted(
        {
            int(value)
            for entry in entries
            for value in (entry.get("mainHeuristic") or {}).get("explicitTimingValues", [])
        }
    )
    stems_with_explicit_overlap = [
        entry["stem"]
        for entry in entries
        if entry["comparison"]["nativeDelayOverlapWithHeuristicExplicit"]  # type: ignore[index]
    ]
    stems_with_non_direct_sources = [
        entry["stem"]
        for entry in entries
        if entry["comparison"]["heuristicUsesNonDirectSources"]  # type: ignore[index]
    ]
    stems_with_out_of_pool_anchors = [
        entry["stem"]
        for entry in entries
        if entry["comparison"]["anchorFramesWithinNativePzfFramePool"] is False  # type: ignore[index]
    ]
    stems_with_full_anchor_clip_coverage = [
        entry["stem"]
        for entry in entries
        if entry["native"]["bestClipAlignment"] is not None
        and float(entry["native"]["bestClipAlignment"]["anchorCoverageRatio"]) >= 1.0
    ]
    stems_with_large_event_count_delta = [
        entry["stem"]
        for entry in entries
        if entry["native"]["bestClipAlignment"] is not None
        and entry["native"]["bestClipAlignment"]["eventCountDelta"] is not None
        and int(entry["native"]["bestClipAlignment"]["eventCountDelta"]) >= 3
    ]

    report = {
        "mainRef": args.main_ref,
        "renderSemanticsLoaded": render_semantics is not None,
        "renderSemanticsError": render_semantics_error,
        "stems": stems,
        "summary": {
            "missingTimelineStems": missing_timelines,
            "stemsWithNativePza": [entry["stem"] for entry in entries if entry["native"]["pza"] is not None],
            "stemsWithExplicitTimingOverlap": stems_with_explicit_overlap,
            "stemsUsingNonDirectPlaybackSources": stems_with_non_direct_sources,
            "stemsWithAnchorsOutsideNativePzfPool": stems_with_out_of_pool_anchors,
            "stemsWithFullAnchorClipCoverage": stems_with_full_anchor_clip_coverage,
            "stemsWithLargeEventCountDelta": stems_with_large_event_count_delta,
            "nativeDelayValuesAcrossSet": aggregate_native_delay_values,
            "heuristicPlaybackValuesAcrossSet": aggregate_playback_values,
            "heuristicExplicitTimingValuesAcrossSet": aggregate_explicit_values,
            "playbackVsNativeOverlapAcrossSet": sorted(set(aggregate_native_delay_values) & set(aggregate_playback_values)),
            "explicitVsNativeOverlapAcrossSet": sorted(set(aggregate_native_delay_values) & set(aggregate_explicit_values)),
        },
        "entries": entries,
    }
    write_json(args.output, report)


if __name__ == "__main__":
    main()
