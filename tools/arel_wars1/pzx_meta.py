from __future__ import annotations

from collections import Counter
from typing import Any, Sequence


def group_meta_sections(meta_sections: Sequence[Any]) -> list[list[Any]]:
    groups: list[list[Any]] = []
    current: list[Any] = []

    for section in meta_sections:
        if section.layout == "opaque":
            if current:
                groups.append(current)
            current = [section]
            continue

        if not current:
            current = []
        current.append(section)

    if current:
        groups.append(current)

    return groups


def _build_frame_sets(frame_records: Sequence[Any]) -> tuple[list[set[tuple[int, int, int, int]]], list[set[int]], set[int]]:
    frame_item_sets = [{(item.chunk_index, item.x, item.y, item.flag) for item in record.items} for record in frame_records]
    frame_chunk_sets = [{item.chunk_index for item in record.items} for record in frame_records]
    all_frame_chunks = {item.chunk_index for record in frame_records for item in record.items}
    return (frame_item_sets, frame_chunk_sets, all_frame_chunks)


def _best_frame_matches(
    tuples: Sequence[Any],
    tuple_keys: Sequence[tuple[int, int, int, int]],
    frame_item_sets: Sequence[set[tuple[int, int, int, int]]],
    frame_chunk_sets: Sequence[set[int]],
) -> list[dict[str, int]]:
    best_frame_matches: list[dict[str, int]] = []
    for frame_index, (frame_items, frame_chunks) in enumerate(zip(frame_item_sets, frame_chunk_sets)):
        exact_overlap = sum(1 for key in tuple_keys if key in frame_items)
        chunk_overlap = sum(1 for item in tuples if item.chunk_index in frame_chunks)
        if exact_overlap == 0 and chunk_overlap == 0:
            continue
        best_frame_matches.append(
            {
                "frameIndex": frame_index,
                "exactOverlap": exact_overlap,
                "chunkOverlap": chunk_overlap,
            }
        )

    best_frame_matches.sort(
        key=lambda entry: (int(entry["exactOverlap"]), int(entry["chunkOverlap"]), -int(entry["frameIndex"])),
        reverse=True,
    )
    return best_frame_matches


def _classify_group(
    tuple_keys: Sequence[tuple[int, int, int, int]],
    unique_chunks: Sequence[int],
    tail_only_chunks: Sequence[int],
    best_frame_matches: Sequence[dict[str, int]],
) -> str:
    if not tuple_keys:
        return "opaque-only"

    best_exact = int(best_frame_matches[0]["exactOverlap"]) if best_frame_matches else 0
    best_chunk = int(best_frame_matches[0]["chunkOverlap"]) if best_frame_matches else 0
    if unique_chunks and len(tail_only_chunks) == len(unique_chunks):
        return "overlay-track"
    if best_exact * 2 >= len(tuple_keys):
        return "base-frame-delta"
    if best_chunk * 2 >= len(tuple_keys):
        return "chunk-linked-reuse"
    return "mixed-or-unknown"


def classify_group(group: Sequence[Any], frame_records: Sequence[Any]) -> tuple[str, list[dict[str, int]]]:
    frame_item_sets, frame_chunk_sets, all_frame_chunks = _build_frame_sets(frame_records)
    tuples = [item for section in group for item in section.tuples]
    tuple_keys = [(item.chunk_index, item.x, item.y, item.flag) for item in tuples]
    unique_chunks = sorted({item.chunk_index for item in tuples})
    tail_only_chunks = sorted(chunk for chunk in unique_chunks if chunk not in all_frame_chunks)
    best_frame_matches = _best_frame_matches(tuples, tuple_keys, frame_item_sets, frame_chunk_sets)
    return (_classify_group(tuple_keys, unique_chunks, tail_only_chunks, best_frame_matches), best_frame_matches[:6])


def summarize_meta_groups(meta_sections: Sequence[Any], frame_records: Sequence[Any]) -> list[dict[str, object]]:
    groups = group_meta_sections(meta_sections)
    frame_item_sets, frame_chunk_sets, all_frame_chunks = _build_frame_sets(frame_records)

    summaries: list[dict[str, object]] = []
    for group_index, sections in enumerate(groups):
        tuples = [item for section in sections for item in section.tuples]
        tuple_keys = [(item.chunk_index, item.x, item.y, item.flag) for item in tuples]
        unique_chunks = sorted({item.chunk_index for item in tuples})
        tail_only_chunks = sorted(chunk for chunk in unique_chunks if chunk not in all_frame_chunks)
        best_frame_matches = _best_frame_matches(tuples, tuple_keys, frame_item_sets, frame_chunk_sets)
        link_type = _classify_group(tuple_keys, unique_chunks, tail_only_chunks, best_frame_matches)

        layout_counts = Counter(section.layout for section in sections)
        marker_counts = Counter(section.marker_hex or "prefix" for section in sections)
        timing_markers = [int(section.timing_ms) for section in sections if section.timing_ms is not None]
        explicit_timing_markers, _, has_ff_sentinel = _split_timing_values(timing_markers)
        summaries.append(
            {
                "groupIndex": group_index,
                "linkType": link_type,
                "sectionCount": len(sections),
                "layoutCounts": dict(sorted(layout_counts.items())),
                "markerCounts": dict(sorted(marker_counts.items())),
                "timingHintMs": max(explicit_timing_markers) if explicit_timing_markers else (255 if has_ff_sentinel else None),
                "timingMarkerValues": timing_markers,
                "timingExplicitValues": explicit_timing_markers,
                "timingHasFfSentinel": has_ff_sentinel,
                "sectionOffsets": [section.offset for section in sections[:12]],
                "tupleCount": len(tuple_keys),
                "uniqueChunkCount": len(unique_chunks),
                "chunkIndexRange": [min(unique_chunks), max(unique_chunks)] if unique_chunks else None,
                "tailOnlyChunkCount": len(tail_only_chunks),
                "tailOnlyChunkPreview": tail_only_chunks[:12],
                "bestFrameMatches": best_frame_matches[:6],
                "sectionsPreview": [
                    {
                        "offset": section.offset,
                        "markerHex": section.marker_hex,
                        "layout": section.layout,
                        "timingMs": section.timing_ms,
                        "payloadLen": len(section.payload),
                        "headerHex": section.header_hex,
                        "tupleCount": section.tuple_count,
                        "extendedLayout": section.extended_layout,
                        "extendedPrefixHex": section.extended_prefix_hex,
                        "extendedSuffixHex": section.extended_suffix_hex,
                        "extendedTupleCount": section.extended_tuple_count,
                        "tuplePreview": [
                            {
                                "chunkIndex": item.chunk_index,
                                "x": item.x,
                                "y": item.y,
                                "flag": item.flag,
                            }
                            for item in section.tuples[:4]
                        ],
                    }
                    for section in sections[:6]
                ],
            }
        )

    return summaries


def _find_minimal_cycle(values: Sequence[int]) -> list[int] | None:
    if len(values) < 2:
        return None

    for cycle_len in range(1, len(values) // 2 + 1):
        if len(values) % cycle_len != 0:
            continue
        pattern = list(values[:cycle_len])
        if len(set(pattern)) == 1:
            continue
        if all(values[index] == pattern[index % cycle_len] for index in range(len(values))):
            return pattern
    return None


def _longest_contiguous_anchor_run(linked_candidates: Sequence[dict[str, object]]) -> dict[str, object] | None:
    if not linked_candidates:
        return None

    current = [linked_candidates[0]]
    best = list(current)
    for candidate in linked_candidates[1:]:
        previous_anchor = int(current[-1]["anchorFrameIndex"])
        current_anchor = int(candidate["anchorFrameIndex"])
        if current_anchor == previous_anchor + 1:
            current.append(candidate)
        else:
            current = [candidate]
        if len(current) > len(best):
            best = list(current)

    return {
        "groupIndices": [int(candidate["groupIndex"]) for candidate in best],
        "anchorFrames": [int(candidate["anchorFrameIndex"]) for candidate in best],
        "length": len(best),
    }


def _summarize_linked_anchor_runs(linked_candidates: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    if not linked_candidates:
        return []

    runs: list[list[dict[str, object]]] = []
    current = [linked_candidates[0]]
    for candidate in linked_candidates[1:]:
        previous = current[-1]
        if int(candidate["groupIndex"]) == int(previous["groupIndex"]) + 1 and int(candidate["anchorFrameIndex"]) == int(
            previous["anchorFrameIndex"]
        ):
            current.append(candidate)
        else:
            runs.append(current)
            current = [candidate]
    runs.append(current)

    return [
        {
            "groupIndices": [int(candidate["groupIndex"]) for candidate in run],
            "anchorFrameIndex": int(run[0]["anchorFrameIndex"]),
            "length": len(run),
            "linkTypes": sorted({str(candidate["linkType"]) for candidate in run}),
            "chunkIndexSpans": [candidate["chunkIndexRange"] for candidate in run],
        }
        for run in runs
    ]


def _overlay_signature(candidate: dict[str, object]) -> tuple[object, int]:
    chunk_range = candidate["chunkIndexRange"]
    return (tuple(chunk_range) if chunk_range is not None else None, int(candidate["tupleCount"]))


def _summarize_overlay_runs(overlay_candidates: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    if not overlay_candidates:
        return []

    runs: list[list[dict[str, object]]] = []
    current = [overlay_candidates[0]]
    current_signature = _overlay_signature(overlay_candidates[0])
    for candidate in overlay_candidates[1:]:
        signature = _overlay_signature(candidate)
        if int(candidate["groupIndex"]) == int(current[-1]["groupIndex"]) + 1 and signature == current_signature:
            current.append(candidate)
        else:
            runs.append(current)
            current = [candidate]
            current_signature = signature
    runs.append(current)

    return [
        {
            "groupIndices": [int(candidate["groupIndex"]) for candidate in run],
            "length": len(run),
            "chunkIndexRange": run[0]["chunkIndexRange"],
            "tupleCount": int(run[0]["tupleCount"]),
            "tailOnlyChunkCount": int(run[0]["tailOnlyChunkCount"]),
        }
        for run in runs
    ]


def _summarize_overlay_attachments(
    linked_candidates: Sequence[dict[str, object]], overlay_candidates: Sequence[dict[str, object]]
) -> list[dict[str, object]]:
    attachments: list[dict[str, object]] = []
    for overlay in overlay_candidates:
        prev_linked = None
        next_linked = None
        for linked in linked_candidates:
            if int(linked["groupIndex"]) < int(overlay["groupIndex"]):
                prev_linked = linked
            elif int(linked["groupIndex"]) > int(overlay["groupIndex"]):
                next_linked = linked
                break

        relation = "unanchored"
        nearest_anchor_frame = None
        nearest_anchor_group = None
        if prev_linked is not None and next_linked is not None:
            prev_gap = int(overlay["groupIndex"]) - int(prev_linked["groupIndex"])
            next_gap = int(next_linked["groupIndex"]) - int(overlay["groupIndex"])
            if prev_gap <= next_gap:
                relation = "after-linked"
                nearest = prev_linked
            else:
                relation = "before-linked"
                nearest = next_linked
            nearest_anchor_frame = int(nearest["anchorFrameIndex"])
            nearest_anchor_group = int(nearest["groupIndex"])
        elif prev_linked is not None:
            relation = "after-linked"
            nearest_anchor_frame = int(prev_linked["anchorFrameIndex"])
            nearest_anchor_group = int(prev_linked["groupIndex"])
        elif next_linked is not None:
            relation = "before-linked"
            nearest_anchor_frame = int(next_linked["anchorFrameIndex"])
            nearest_anchor_group = int(next_linked["groupIndex"])

        attachments.append(
            {
                "groupIndex": int(overlay["groupIndex"]),
                "chunkIndexRange": overlay["chunkIndexRange"],
                "tupleCount": int(overlay["tupleCount"]),
                "relation": relation,
                "nearestAnchorFrameIndex": nearest_anchor_frame,
                "nearestAnchorGroupIndex": nearest_anchor_group,
                "previousLinkedGroupIndex": int(prev_linked["groupIndex"]) if prev_linked is not None else None,
                "nextLinkedGroupIndex": int(next_linked["groupIndex"]) if next_linked is not None else None,
            }
        )

    return attachments


def _marker_timing_values(sections: Sequence[Any]) -> list[int]:
    return [int(section.timing_ms) for section in sections if section.timing_ms is not None]


def _split_timing_values(timing_values: Sequence[int]) -> tuple[list[int], list[int], bool]:
    explicit = [int(value) for value in timing_values if int(value) not in {0, 255}]
    zero_values = [int(value) for value in timing_values if int(value) == 0]
    has_ff = any(int(value) == 255 for value in timing_values)
    return (explicit, zero_values, has_ff)


def infer_group_timing(sections: Sequence[Any]) -> dict[str, object]:
    markers = [str(section.marker_hex) for section in sections if section.marker_hex is not None]
    timing_values = _marker_timing_values(sections)
    explicit_values, zero_values, has_ff = _split_timing_values(timing_values)
    duration_hint = max(explicit_values) if explicit_values else (0 if zero_values else (255 if has_ff else None))
    return {
        "markerHexes": markers,
        "markerCount": len(markers),
        "markerValues": timing_values,
        "explicitMarkerValues": explicit_values,
        "hasFfSentinel": has_ff,
        "durationHintMs": duration_hint,
    }


def _find_event_index_by_group(events: Sequence[dict[str, object]], group_index: int) -> int | None:
    for event_index, event in enumerate(events):
        if int(event["groupIndex"]) == group_index:
            return event_index
    return None


def infer_loop_summary(events: Sequence[dict[str, object]], sequence_summary: dict[str, object]) -> dict[str, object] | None:
    if not events:
        return None

    timeline_kind = str(sequence_summary.get("timelineKind", ""))
    sequence_kind = str(sequence_summary.get("sequenceKind", ""))
    start = 0
    end = len(events) - 1
    reason = "full-sequence"
    confidence = "medium"

    if timeline_kind == "single-anchor-with-overlays" and len(events) > 1:
        start = 1
        reason = "overlay-tail"
    elif timeline_kind == "single-anchor-cadence":
        reason = "single-anchor-cadence"
    elif timeline_kind == "overlay-track-only":
        reason = "overlay-track-only"
    elif timeline_kind in {"rising-anchor-run", "rising-anchor-with-overlays"}:
        best_run = sequence_summary.get("bestContiguousRun")
        if isinstance(best_run, dict):
            group_indices = [int(value) for value in best_run.get("groupIndices", [])]
            mapped = [index for index in (_find_event_index_by_group(events, group_index) for group_index in group_indices) if index is not None]
            if mapped:
                start = min(mapped)
                end = max(mapped)
                reason = "best-contiguous-run"
                confidence = "high"
    elif sequence_kind == "strict-loop":
        reason = "strict-cycle"
        confidence = "high"
    elif timeline_kind == "linked-only-scatter":
        reason = "linked-scatter"
        confidence = "low"
    elif timeline_kind == "mixed-anchor-overlay":
        first_linked = next((index for index, event in enumerate(events) if str(event["eventType"]) == "linked"), None)
        if first_linked is not None:
            start = first_linked
            reason = "first-linked-anchor"
            confidence = "low"

    if start > end:
        return None

    return {
        "startEventIndex": start,
        "endEventIndex": end,
        "reason": reason,
        "confidence": confidence,
    }


def summarize_sequence_candidates(meta_groups: Sequence[dict[str, object]]) -> dict[str, object]:
    linked_candidates: list[dict[str, object]] = []
    overlay_candidates: list[dict[str, object]] = []

    for group in meta_groups:
        link_type = str(group["linkType"])
        best_matches = list(group.get("bestFrameMatches", []))
        chunk_range = group.get("chunkIndexRange")
        if link_type in {"base-frame-delta", "chunk-linked-reuse"} and best_matches:
            best = best_matches[0]
            linked_candidates.append(
                {
                    "groupIndex": int(group["groupIndex"]),
                    "linkType": link_type,
                    "anchorFrameIndex": int(best["frameIndex"]),
                    "exactOverlap": int(best["exactOverlap"]),
                    "chunkOverlap": int(best["chunkOverlap"]),
                    "tupleCount": int(group["tupleCount"]),
                    "chunkIndexRange": chunk_range,
                }
            )
        elif link_type == "overlay-track":
            overlay_candidates.append(
                {
                    "groupIndex": int(group["groupIndex"]),
                    "tupleCount": int(group["tupleCount"]),
                    "chunkIndexRange": chunk_range,
                    "tailOnlyChunkCount": int(group["tailOnlyChunkCount"]),
                }
            )

    anchor_sequence = [int(candidate["anchorFrameIndex"]) for candidate in linked_candidates]
    anchor_deltas = [anchor_sequence[index + 1] - anchor_sequence[index] for index in range(len(anchor_sequence) - 1)]
    distinct_anchor_frames = sorted(set(anchor_sequence))
    best_run = _longest_contiguous_anchor_run(linked_candidates)
    strict_cycle = _find_minimal_cycle(anchor_sequence)
    linked_anchor_runs = _summarize_linked_anchor_runs(linked_candidates)
    overlay_runs = _summarize_overlay_runs(overlay_candidates)
    overlay_attachments = _summarize_overlay_attachments(linked_candidates, overlay_candidates)

    if not linked_candidates and overlay_candidates:
        sequence_kind = "overlay-only"
    elif not linked_candidates and not overlay_candidates:
        sequence_kind = "no-sequence-candidates"
    elif len(distinct_anchor_frames) == 1 and len(anchor_sequence) == 1:
        sequence_kind = "single-anchor-delta"
    elif len(distinct_anchor_frames) == 1:
        sequence_kind = "single-anchor-repeat"
    elif anchor_deltas and all(delta == 1 for delta in anchor_deltas):
        sequence_kind = "contiguous-rise"
    elif best_run is not None and int(best_run["length"]) >= 3:
        sequence_kind = "has-contiguous-rise"
    elif strict_cycle is not None:
        sequence_kind = "strict-loop"
    elif len(distinct_anchor_frames) <= 3 and len(anchor_sequence) >= 5:
        sequence_kind = "multi-anchor-loop"
    else:
        sequence_kind = "linked-mixed"

    if not linked_candidates and overlay_candidates:
        timeline_kind = "overlay-track-only"
    elif len(distinct_anchor_frames) == 1 and len(linked_candidates) > 1:
        timeline_kind = "single-anchor-cadence"
    elif len(distinct_anchor_frames) == 1 and overlay_candidates:
        timeline_kind = "single-anchor-with-overlays"
    elif best_run is not None and int(best_run["length"]) >= 3 and overlay_candidates:
        timeline_kind = "rising-anchor-with-overlays"
    elif best_run is not None and int(best_run["length"]) >= 3:
        timeline_kind = "rising-anchor-run"
    elif overlay_candidates and linked_candidates:
        timeline_kind = "mixed-anchor-overlay"
    elif strict_cycle is not None:
        timeline_kind = "anchor-loop"
    elif linked_candidates:
        timeline_kind = "linked-only-scatter"
    else:
        timeline_kind = "no-timeline-candidates"

    link_type_counts = Counter(str(candidate["linkType"]) for candidate in linked_candidates)
    link_type_counts.update({"overlay-track": len(overlay_candidates)})

    return {
        "sequenceKind": sequence_kind,
        "timelineKind": timeline_kind,
        "linkedGroupCount": len(linked_candidates),
        "overlayGroupCount": len(overlay_candidates),
        "linkTypeCounts": dict(sorted(link_type_counts.items())),
        "anchorFrameSequence": anchor_sequence,
        "anchorFrameDeltas": anchor_deltas,
        "distinctAnchorFrames": distinct_anchor_frames,
        "anchorFrameSpan": [min(anchor_sequence), max(anchor_sequence)] if anchor_sequence else None,
        "strictLoopCycle": strict_cycle,
        "bestContiguousRun": best_run,
        "linkedAnchorRuns": linked_anchor_runs[:12],
        "overlayRuns": overlay_runs[:12],
        "overlayAttachmentsPreview": overlay_attachments[:16],
        "linkedGroupIndices": [int(candidate["groupIndex"]) for candidate in linked_candidates],
        "overlayGroupIndices": [int(candidate["groupIndex"]) for candidate in overlay_candidates],
        "overlayChunkRanges": [candidate["chunkIndexRange"] for candidate in overlay_candidates],
        "linkedCandidatesPreview": linked_candidates[:12],
        "overlayCandidatesPreview": overlay_candidates[:12],
    }
