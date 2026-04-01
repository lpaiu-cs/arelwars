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
        summaries.append(
            {
                "groupIndex": group_index,
                "linkType": link_type,
                "sectionCount": len(sections),
                "layoutCounts": dict(sorted(layout_counts.items())),
                "markerCounts": dict(sorted(marker_counts.items())),
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
                        "payloadLen": len(section.payload),
                        "headerHex": section.header_hex,
                        "tupleCount": section.tuple_count,
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

    link_type_counts = Counter(str(candidate["linkType"]) for candidate in linked_candidates)
    link_type_counts.update({"overlay-track": len(overlay_candidates)})

    return {
        "sequenceKind": sequence_kind,
        "linkedGroupCount": len(linked_candidates),
        "overlayGroupCount": len(overlay_candidates),
        "linkTypeCounts": dict(sorted(link_type_counts.items())),
        "anchorFrameSequence": anchor_sequence,
        "anchorFrameDeltas": anchor_deltas,
        "distinctAnchorFrames": distinct_anchor_frames,
        "anchorFrameSpan": [min(anchor_sequence), max(anchor_sequence)] if anchor_sequence else None,
        "strictLoopCycle": strict_cycle,
        "bestContiguousRun": best_run,
        "linkedGroupIndices": [int(candidate["groupIndex"]) for candidate in linked_candidates],
        "overlayGroupIndices": [int(candidate["groupIndex"]) for candidate in overlay_candidates],
        "overlayChunkRanges": [candidate["chunkIndexRange"] for candidate in overlay_candidates],
        "linkedCandidatesPreview": linked_candidates[:12],
        "overlayCandidatesPreview": overlay_candidates[:12],
    }
