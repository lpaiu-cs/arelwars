#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from formats import (
    find_zlib_streams,
    get_pzx_meta_effective_tuples,
    read_mpl,
    read_pzx_frame_record_stream,
    read_pzx_first_stream,
    read_pzx_meta_sections,
    read_pzx_row_stream,
    read_pzx_simple_placement_stream,
)
from pzx_meta import summarize_meta_groups, summarize_sequence_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect opaque PZX/MPL/PTC binary assets")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Path to write JSON report")
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_pzx_first_stream(table_span: int, stream: bytes) -> dict[str, object] | None:
    decoded = read_pzx_first_stream(stream, table_span)
    if decoded is None:
        return None

    chunks_preview: list[dict[str, object]] = []
    for chunk in decoded.chunks[:8]:
        row_previews = [
            {
                "index": row_index,
                "skips": list(row.skips),
                "runLengths": list(row.run_lengths),
                "runKinds": list(row.run_kinds),
                "decodedHeadHex": row.decoded[:24].hex(),
            }
            for row_index, row in enumerate(chunk.rows[:4])
        ]
        chunks_preview.append(
            {
                "index": chunk.index,
                "start": decoded.offsets[chunk.index],
                "end": decoded.offsets[chunk.index + 1] if chunk.index + 1 < len(decoded.offsets) else len(stream),
                "length": len(chunk.body) + 16,
                "width": chunk.width,
                "height": chunk.height,
                "magicHex": chunk.magic_hex,
                "declaredPayloadLen": chunk.declared_payload_len,
                "reserved": chunk.reserved,
                "decodedPixelCount": chunk.decoded_pixel_count,
                "prefixMarkerHex": chunk.prefix_marker_hex,
                "rowSeparatorCount": len(chunk.row_separator_hexes),
                "trailingSentinelHex": chunk.trailing_sentinel_hex,
                "bodyHeadHex": chunk.body[:24].hex(),
                "rowPreview": row_previews,
            }
        )

    widths = [chunk.width for chunk in decoded.chunks]
    heights = [chunk.height for chunk in decoded.chunks]
    total_payload = sum(chunk.declared_payload_len for chunk in decoded.chunks)
    total_pixels = sum(chunk.decoded_pixel_count for chunk in decoded.chunks)
    max_decoded_index = max(max(row.decoded) for chunk in decoded.chunks for row in chunk.rows)

    return {
        "tableSpan": decoded.table_span,
        "chunkCount": len(decoded.chunks),
        "chunkDimensions": [{"index": chunk.index, "width": chunk.width, "height": chunk.height} for chunk in decoded.chunks],
        "offsetsPreview": list(decoded.offsets[:12]),
        "offsetsTail": list(decoded.offsets[-6:]),
        "chunkWidthRange": [min(widths), max(widths)],
        "chunkHeightRange": [min(heights), max(heights)],
        "maxDecodedIndex": max_decoded_index,
        "chunkLengthStats": {
            "min": min(len(chunk.body) + 16 for chunk in decoded.chunks),
            "max": max(len(chunk.body) + 16 for chunk in decoded.chunks),
            "avg": (len(stream) - decoded.table_span) / len(decoded.chunks),
        },
        "decodedPixelTotal": total_pixels,
        "declaredPayloadTotal": total_payload,
        "chunksPreview": chunks_preview,
    }


def summarize_pzx_row_stream(stream: bytes) -> dict[str, object] | None:
    decoded = read_pzx_row_stream(stream)
    if decoded is None:
        return None

    width_min, width_max = decoded.width_range
    max_decoded_index = max(max(row.decoded) for row in decoded.rows if row.decoded)
    row_previews = [
        {
            "index": row_index,
            "width": len(row.decoded),
            "skips": list(row.skips),
            "runLengths": list(row.run_lengths),
            "runKinds": list(row.run_kinds),
            "decodedHeadHex": row.decoded[:24].hex(),
        }
        for row_index, row in enumerate(decoded.rows[:6])
    ]

    return {
        "width": decoded.width,
        "height": decoded.height,
        "widthRange": [width_min, width_max],
        "maxDecodedIndex": max_decoded_index,
        "decodedPixelTotal": decoded.decoded_pixel_count,
        "prefixMarkerHex": decoded.prefix_marker_hex,
        "rowSeparatorCount": len(decoded.row_separator_hexes),
        "trailingSentinelHex": decoded.trailing_sentinel_hex,
        "rowPreview": row_previews,
    }


def summarize_simple_placement_stream(stream: bytes, chunk_count: int, chunk_sizes: dict[int, tuple[int, int]]) -> dict[str, object] | None:
    placements = read_pzx_simple_placement_stream(stream, chunk_count)
    if placements is None:
        return None

    min_x = min(placement.x for placement in placements)
    min_y = min(placement.y for placement in placements)
    max_x = max(placement.x + chunk_sizes[placement.chunk_index][0] for placement in placements)
    max_y = max(placement.y + chunk_sizes[placement.chunk_index][1] for placement in placements)

    return {
        "recordCount": len(placements),
        "modeValues": sorted({placement.mode for placement in placements}),
        "chunkIndexRange": [min(placement.chunk_index for placement in placements), max(placement.chunk_index for placement in placements)],
        "bbox": {"minX": min_x, "minY": min_y, "maxX": max_x, "maxY": max_y},
        "placementsPreview": [
            {
                "chunkIndex": placement.chunk_index,
                "mode": placement.mode,
                "x": placement.x,
                "y": placement.y,
                "chunkWidth": chunk_sizes[placement.chunk_index][0],
                "chunkHeight": chunk_sizes[placement.chunk_index][1],
            }
            for placement in placements[:8]
        ],
    }


def summarize_frame_record_stream(stream: bytes, chunk_count: int, chunk_sizes: dict[int, tuple[int, int]]) -> dict[str, object] | None:
    decoded = read_pzx_frame_record_stream(stream, chunk_count)
    if decoded is None or len(decoded.records) < 2:
        return None

    all_items = [item for record in decoded.records for item in record.items]
    all_control_chunks = [chunk for record in decoded.records for chunk in record.control_chunks]
    meta_sections = read_pzx_meta_sections(decoded.trailing, chunk_count) if decoded.trailing else ()
    meta_groups = summarize_meta_groups(meta_sections, decoded.records)
    meta_sequence_summary = summarize_sequence_candidates(meta_groups)
    meta_marker_counts = Counter(section.marker_hex or "prefix" for section in meta_sections)
    meta_layout_counts = Counter(section.layout for section in meta_sections)
    meta_group_link_counts = Counter(group["linkType"] for group in meta_groups)
    meta_timing_values = [int(section.timing_ms) for section in meta_sections if section.timing_ms is not None]
    min_item_x = min(item.x for item in all_items)
    min_item_y = min(item.y for item in all_items)
    max_item_x = max(item.x + chunk_sizes[item.chunk_index][0] for item in all_items)
    max_item_y = max(item.y + chunk_sizes[item.chunk_index][1] for item in all_items)

    return {
        "recordCount": len(decoded.records),
        "consumed": decoded.consumed,
        "trailingLen": len(decoded.trailing),
        "frameTypeValues": sorted({record.frame_type for record in decoded.records}),
        "frameOriginRange": {
            "x": [min(record.x for record in decoded.records), max(record.x for record in decoded.records)],
            "y": [min(record.y for record in decoded.records), max(record.y for record in decoded.records)],
        },
        "frameSizeRange": {
            "width": [min(record.width for record in decoded.records), max(record.width for record in decoded.records)],
            "height": [min(record.height for record in decoded.records), max(record.height for record in decoded.records)],
        },
        "itemCountRange": [
            min(record.item_count for record in decoded.records),
            max(record.item_count for record in decoded.records),
        ],
        "itemChunkIndexRange": [min(item.chunk_index for item in all_items), max(item.chunk_index for item in all_items)],
        "itemPlacementBbox": {"minX": min_item_x, "minY": min_item_y, "maxX": max_item_x, "maxY": max_item_y},
        "flagValues": sorted({item.flag for item in all_items}),
        "controlChunkCount": len(all_control_chunks),
        "controlChunkLengths": sorted({len(chunk) for chunk in all_control_chunks}),
        "metaSectionCount": len(meta_sections),
        "metaMarkerCounts": dict(sorted(meta_marker_counts.items())),
        "metaLayoutCounts": dict(sorted(meta_layout_counts.items())),
        "metaGroupCount": len(meta_groups),
        "metaLinkedGroupCount": sum(
            1 for group in meta_groups if any(int(match["exactOverlap"]) > 0 for match in group["bestFrameMatches"])
        ),
        "metaTailOnlyGroupCount": sum(
            1
            for group in meta_groups
            if int(group["uniqueChunkCount"]) > 0 and int(group["tailOnlyChunkCount"]) == int(group["uniqueChunkCount"])
        ),
        "metaGroupLinkCounts": dict(sorted(meta_group_link_counts.items())),
        "metaTimingMarkerCount": len(meta_timing_values),
        "metaTimingValues": meta_timing_values[:96],
        "metaTimingValueHistogram": dict(sorted(Counter(meta_timing_values).items())),
        "metaSequenceSummary": meta_sequence_summary,
        "recordOffsetsPreview": [record.offset for record in decoded.records[:12]],
        "recordPreview": [
            {
                "offset": record.offset,
                "itemCount": record.item_count,
                "frameType": record.frame_type,
                "x": record.x,
                "y": record.y,
                "width": record.width,
                "height": record.height,
                "controlChunkHex": [chunk.hex() for chunk in record.control_chunks[:4]],
                "itemsPreview": [
                    {
                        "chunkIndex": item.chunk_index,
                        "x": item.x,
                        "y": item.y,
                        "flag": item.flag,
                    }
                    for item in record.items[:8]
                ],
            }
            for record in decoded.records[:4]
        ],
        "metaSectionsPreview": [
            {
                "offset": section.offset,
                "markerHex": section.marker_hex,
                "payloadLen": len(section.payload),
                "layout": section.layout,
                "headerHex": section.header_hex,
                "timingMs": section.timing_ms,
                "tupleCount": section.tuple_count,
                "validTupleCount": section.valid_tuple_count,
                "extendedLayout": section.extended_layout,
                "extendedPrefixHex": section.extended_prefix_hex,
                "extendedSuffixHex": section.extended_suffix_hex,
                "extendedTupleStride": section.extended_tuple_stride,
                "extendedTupleCount": section.extended_tuple_count,
                "extendedValidTupleCount": section.extended_valid_tuple_count,
                "payloadHeadHex": section.payload[:24].hex(),
                "tuplePreview": [
                    {
                        "chunkIndex": item.chunk_index,
                        "x": item.x,
                        "y": item.y,
                        "flag": item.flag,
                    }
                    for item in get_pzx_meta_effective_tuples(section)[:6]
                ],
                "extendedTuplePreview": [
                    {
                        "chunkIndex": item.chunk_index,
                        "x": item.x,
                        "y": item.y,
                        "flag": item.flag,
                    }
                    for item in section.extended_tuples[:6]
                ],
            }
            for section in meta_sections[:8]
        ],
        "metaGroupsPreview": meta_groups[:8],
    }


def parse_pzx(path: Path, has_mpl_pair: bool) -> dict[str, object]:
    data = path.read_bytes()
    streams = find_zlib_streams(data)
    field16 = struct.unpack("<H", data[16:18])[0] if len(data) >= 18 else 0
    table_span = field16 >> 6

    parsed_streams: list[dict[str, object]] = []
    first_stream_summary: dict[str, object] | None = None
    first_stream_error: str | None = None
    simple_placement_summary: dict[str, object] | None = None
    frame_record_summaries: list[dict[str, object]] = []

    for index, item in enumerate(streams[:12]):
        entry = {
            "index": index,
            "offset": item.offset,
            "consumed": item.consumed,
            "decodedLen": len(item.decoded),
            "headHex": item.decoded[:32].hex(),
            "tailHex": item.decoded[-16:].hex(),
        }
        if index == 0:
            try:
                summary = summarize_pzx_first_stream(table_span, item.decoded)
            except ValueError as exc:
                first_stream_error = str(exc)
            else:
                if summary is not None:
                    first_stream_summary = summary
        if index > 0 and first_stream_summary is not None:
            chunk_sizes = {
                item["index"]: (item["width"], item["height"]) for item in first_stream_summary["chunkDimensions"]
            }
            if chunk_sizes:
                try:
                    placement_summary = summarize_simple_placement_stream(
                        item.decoded,
                        int(first_stream_summary["chunkCount"]),
                        chunk_sizes,
                    )
                except ValueError:
                    placement_summary = None
                if placement_summary is not None:
                    entry["simplePlacement"] = placement_summary
                    if simple_placement_summary is None:
                        simple_placement_summary = {"streamIndex": index, **placement_summary}
                try:
                    frame_record_summary = summarize_frame_record_stream(
                        item.decoded,
                        int(first_stream_summary["chunkCount"]),
                        chunk_sizes,
                    )
                except ValueError:
                    frame_record_summary = None
                if frame_record_summary is not None:
                    entry["frameRecord"] = frame_record_summary
                    frame_record_summaries.append({"streamIndex": index, **frame_record_summary})
        try:
            row_stream_summary = summarize_pzx_row_stream(item.decoded)
        except ValueError:
            row_stream_summary = None
        if row_stream_summary is not None:
            entry["rowStream"] = row_stream_summary
        parsed_streams.append(entry)

    return {
        "path": str(path),
        "size": len(data),
        "header": {
            "signatureHex": data[:4].hex(),
            "field4": struct.unpack("<I", data[4:8])[0] if len(data) >= 8 else None,
            "field8": struct.unpack("<I", data[8:12])[0] if len(data) >= 12 else None,
            "field12": struct.unpack("<I", data[12:16])[0] if len(data) >= 16 else None,
            "field16Raw": field16,
            "field16Shift6": table_span,
            "field16Low6": field16 & 0x3F,
            "field18": struct.unpack("<H", data[18:20])[0] if len(data) >= 20 else None,
        },
        "hasMplPair": has_mpl_pair,
        "zlibStreamCount": len(streams),
        "streams": parsed_streams,
        "firstStream": first_stream_summary,
        "firstStreamError": first_stream_error,
        "simplePlacementStream": simple_placement_summary,
        "frameRecordStreams": frame_record_summaries,
    }


def parse_mpl(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    mpl = read_mpl(data)
    words = [struct.unpack("<H", data[index : index + 2])[0] for index in range(0, min(len(data), 32), 2)]
    field = struct.unpack("<I", data[4:8])[0] if len(data) >= 8 else 0
    entry = {
        "path": str(path),
        "size": len(data),
        "signatureHex": data[:4].hex(),
        "signatureU32": struct.unpack("<I", data[:4])[0] if len(data) >= 4 else None,
        "sha1": hashlib.sha1(data).hexdigest(),
        "declaredWordCount": field >> 16,
        "actualWordCount": len(data) // 2,
        "declaredMinusActual": (field >> 16) - (len(data) // 2),
        "headerWords": words,
    }
    if mpl is None:
        return entry

    entry.update(
        {
            "colorCount": mpl.color_count,
            "headerMatchesCurrentModel": mpl.header_matches_current_model,
            "expectedHeaderWord3": mpl.expected_header_word3,
            "expectedHeaderWord5": mpl.expected_header_word5,
            "bankAZeroWordCount": sum(1 for word in mpl.bank_a if word == 0),
            "bankBZeroWordCount": sum(1 for word in mpl.bank_b if word == 0),
            "bankDiffCount": sum(1 for a, b in zip(mpl.bank_a, mpl.bank_b, strict=True) if a != b),
            "bankPreview": {
                "a": [int(word) for word in mpl.bank_a[:8]],
                "b": [int(word) for word in mpl.bank_b[:8]],
            },
        }
    )
    return entry


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    img_root = assets_root / "img"

    pzx_paths = sorted(img_root.glob("*.pzx"))
    mpl_paths = sorted(img_root.glob("*.mpl"))
    mpl_stems = {path.stem for path in mpl_paths}

    pzx_entries = [parse_pzx(path, path.stem in mpl_stems) for path in pzx_paths]
    mpl_entries = [parse_mpl(path) for path in mpl_paths]
    mpl_by_stem = {Path(entry["path"]).stem: entry for entry in mpl_entries}

    shared_mpl_groups: dict[str, list[str]] = {}
    shared_mpl_by_sha1: dict[str, list[str]] = {}
    for mpl_entry in mpl_entries:
        shared_mpl_by_sha1.setdefault(str(mpl_entry["sha1"]), []).append(Path(str(mpl_entry["path"])).stem)
    for sha1, stems in shared_mpl_by_sha1.items():
        if len(stems) > 1:
            shared_mpl_groups[sha1] = sorted(stems)
    for mpl_entry in mpl_entries:
        shared = shared_mpl_groups.get(str(mpl_entry["sha1"]), [])
        mpl_entry["sharedWith"] = [stem for stem in shared if stem != Path(str(mpl_entry["path"])).stem]

    shared_pairs = sorted({Path(entry["path"]).stem for entry in pzx_entries if entry["hasMplPair"]})
    first_stream_ready = [entry for entry in pzx_entries if entry["firstStream"] is not None]
    first_stream_failed = [entry for entry in pzx_entries if entry["firstStreamError"] is not None]
    raw_row_stream_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "variant": entry["header"]["field16Low6"],
            "streamIndices": [stream["index"] for stream in entry["streams"] if stream.get("rowStream") is not None],
            "maxDecodedIndex": max(
                stream["rowStream"]["maxDecodedIndex"]
                for stream in entry["streams"]
                if stream.get("rowStream") is not None
            ),
            "dimensions": [
                {
                    "index": stream["index"],
                    "width": stream["rowStream"]["width"],
                    "height": stream["rowStream"]["height"],
                }
                for stream in entry["streams"]
                if stream.get("rowStream") is not None
            ][:6],
        }
        for entry in pzx_entries
        if any(stream.get("rowStream") is not None for stream in entry["streams"])
    ]
    simple_placement_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "variant": entry["header"]["field16Low6"],
            "streamIndex": entry["simplePlacementStream"]["streamIndex"],
            "recordCount": entry["simplePlacementStream"]["recordCount"],
            "bbox": entry["simplePlacementStream"]["bbox"],
        }
        for entry in pzx_entries
        if entry.get("simplePlacementStream") is not None
    ]
    frame_record_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "variant": entry["header"]["field16Low6"],
            "streamIndex": stream["streamIndex"],
            "recordCount": stream["recordCount"],
            "consumed": stream["consumed"],
            "trailingLen": stream["trailingLen"],
            "itemCountRange": stream["itemCountRange"],
            "flagValues": stream["flagValues"],
            "controlChunkCount": stream["controlChunkCount"],
            "controlChunkLengths": stream["controlChunkLengths"],
            "metaSectionCount": stream["metaSectionCount"],
            "metaLayoutCounts": stream["metaLayoutCounts"],
            "metaMarkerCounts": stream["metaMarkerCounts"],
            "metaGroupCount": stream["metaGroupCount"],
            "metaLinkedGroupCount": stream["metaLinkedGroupCount"],
            "metaTailOnlyGroupCount": stream["metaTailOnlyGroupCount"],
            "metaGroupLinkCounts": stream["metaGroupLinkCounts"],
            "metaSequenceSummary": stream["metaSequenceSummary"],
        }
        for entry in pzx_entries
        for stream in entry.get("frameRecordStreams", [])
    ]
    frame_record_stems = sorted({entry["stem"] for entry in frame_record_entries})
    frame_record_control_stems = sorted(
        {entry["stem"] for entry in frame_record_entries if int(entry["controlChunkCount"]) > 0}
    )
    frame_meta_section_count = sum(int(entry["metaSectionCount"]) for entry in frame_record_entries)
    frame_meta_layout_counts = Counter()
    frame_meta_marker_counts = Counter()
    for entry in frame_record_entries:
        frame_meta_layout_counts.update(entry["metaLayoutCounts"])
        frame_meta_marker_counts.update(entry["metaMarkerCounts"])
    frame_meta_group_count = sum(int(entry["metaGroupCount"]) for entry in frame_record_entries)
    frame_meta_linked_group_count = sum(int(entry["metaLinkedGroupCount"]) for entry in frame_record_entries)
    frame_meta_tail_only_group_count = sum(int(entry["metaTailOnlyGroupCount"]) for entry in frame_record_entries)
    frame_meta_group_link_counts = Counter()
    for entry in frame_record_entries:
        frame_meta_group_link_counts.update(entry["metaGroupLinkCounts"])
    frame_meta_sequence_kind_counts = Counter(
        entry["metaSequenceSummary"]["sequenceKind"] for entry in frame_record_entries
    )
    frame_meta_timeline_kind_counts = Counter(
        entry["metaSequenceSummary"]["timelineKind"] for entry in frame_record_entries
    )
    frame_meta_exact_stems = sorted(
        {
            entry["stem"]
            for entry in frame_record_entries
            if any(layout != "opaque" for layout in entry["metaLayoutCounts"])
        }
    )
    regular_mpl_palette_stems: list[str] = []
    regular_mpl_palette_set: set[str] = set()
    row_stream_regular_mpl_palette_stems: list[str] = []
    row_stream_regular_mpl_palette_set: set[str] = set()
    palette_capacity_fit_stems: list[str] = []
    palette_capacity_fit_set: set[str] = set()
    row_stream_palette_capacity_fit_stems: list[str] = []
    row_stream_palette_capacity_fit_set: set[str] = set()

    mpl_palette_capacity_by_stem: dict[str, int] = {}
    for stem, mpl in mpl_by_stem.items():
        word_count = int(mpl["actualWordCount"])
        if word_count >= 8 and (word_count - 6) % 2 == 0:
            mpl_palette_capacity_by_stem[stem] = (word_count - 6) // 2

    for entry in pzx_entries:
        row_stream_maxes = [
            stream["rowStream"]["maxDecodedIndex"] for stream in entry["streams"] if stream.get("rowStream") is not None
        ]
        if row_stream_maxes:
            entry["rowStreamMaxDecodedIndex"] = max(row_stream_maxes)

    for entry in first_stream_ready:
        stem = Path(entry["path"]).stem
        mpl = mpl_by_stem.get(stem)
        if mpl is None or not entry["hasMplPair"]:
            continue
        color_count = int(entry["firstStream"]["maxDecodedIndex"]) + 1
        palette_capacity = mpl_palette_capacity_by_stem.get(stem)
        if mpl["actualWordCount"] == 2 * color_count + 6:
            regular_mpl_palette_stems.append(stem)
            regular_mpl_palette_set.add(stem)
        if palette_capacity is not None and color_count <= palette_capacity:
            palette_capacity_fit_stems.append(stem)
            palette_capacity_fit_set.add(stem)
    for entry in pzx_entries:
        stem = Path(entry["path"]).stem
        mpl = mpl_by_stem.get(stem)
        row_stream_max = entry.get("rowStreamMaxDecodedIndex")
        if mpl is None or not entry["hasMplPair"] or row_stream_max is None:
            continue
        color_count = int(row_stream_max) + 1
        palette_capacity = mpl_palette_capacity_by_stem.get(stem)
        if mpl["actualWordCount"] == 2 * color_count + 6:
            row_stream_regular_mpl_palette_stems.append(stem)
            row_stream_regular_mpl_palette_set.add(stem)
        if palette_capacity is not None and color_count <= palette_capacity:
            row_stream_palette_capacity_fit_stems.append(stem)
            row_stream_palette_capacity_fit_set.add(stem)

    effective_regular_sources: dict[str, list[str]] = {}
    effective_regular_stems: set[str] = set(palette_capacity_fit_set | row_stream_palette_capacity_fit_set)
    for stem in effective_regular_stems:
        effective_regular_sources[stem] = [stem]
    for stems in shared_mpl_groups.values():
        donors = sorted(stem for stem in stems if stem in effective_regular_stems)
        if not donors:
            continue
        for stem in stems:
            effective_regular_stems.add(stem)
            effective_regular_sources[stem] = donors

    for entry in pzx_entries:
        stem = Path(entry["path"]).stem
        mpl = mpl_by_stem.get(stem)
        if mpl is not None:
            entry["mplPaletteColorCapacity"] = mpl_palette_capacity_by_stem.get(stem)
            entry["sharedMplWith"] = mpl.get("sharedWith", [])
            entry["mplRegularPaletteMatch"] = stem in regular_mpl_palette_set
            entry["mplPaletteCapacityFit"] = stem in palette_capacity_fit_set
            entry["rowStreamRegularPaletteMatch"] = stem in row_stream_regular_mpl_palette_set
            entry["rowStreamPaletteCapacityFit"] = stem in row_stream_palette_capacity_fit_set
            entry["effectiveMplPaletteMatch"] = stem in effective_regular_stems
            entry["effectiveMplPaletteSources"] = effective_regular_sources.get(stem, [])

    shared_mpl_group_entries: list[dict[str, object]] = []
    for sha1, stems in sorted(shared_mpl_groups.items(), key=lambda item: item[1]):
        shared_mpl_group_entries.append(
            {
                "sha1": sha1,
                "stems": stems,
                "regularPaletteStems": [stem for stem in stems if stem in regular_mpl_palette_set],
                "paletteCapacityFitStems": [stem for stem in stems if stem in palette_capacity_fit_set],
                "rowStreamRegularPaletteStems": [stem for stem in stems if stem in row_stream_regular_mpl_palette_set],
                "rowStreamPaletteCapacityFitStems": [
                    stem for stem in stems if stem in row_stream_palette_capacity_fit_set
                ],
                "effectiveRegularStems": [stem for stem in stems if stem in effective_regular_stems],
                "resolvedSources": sorted({source for stem in stems for source in effective_regular_sources.get(stem, [])}),
            }
        )

    variant_counts = Counter(entry["header"]["field16Low6"] for entry in pzx_entries)
    table_span_counts = Counter(
        entry["firstStream"]["tableSpan"] for entry in first_stream_ready if entry["firstStream"] is not None
    )

    report = {
        "summary": {
            "pzxCount": len(pzx_entries),
            "mplCount": len(mpl_entries),
            "pairedStemCount": len(shared_pairs),
            "pairedStemsPreview": shared_pairs[:20],
            "pzxVariantCounts": dict(sorted(variant_counts.items())),
            "firstStreamDecodedCount": len(first_stream_ready),
            "firstStreamDecodeFailedCount": len(first_stream_failed),
            "firstStreamTableSpanCounts": dict(sorted(table_span_counts.items())),
            "rawRowStreamPzxCount": len(raw_row_stream_entries),
            "rawRowStreamPreview": raw_row_stream_entries[:12],
            "simplePlacementPzxCount": len(simple_placement_entries),
            "simplePlacementPreview": simple_placement_entries[:12],
            "frameRecordPzxCount": len(frame_record_stems),
            "frameRecordStreamCount": len(frame_record_entries),
            "frameRecordControlPzxCount": len(frame_record_control_stems),
            "frameRecordControlPreview": frame_record_control_stems[:20],
            "frameMetaSectionCount": frame_meta_section_count,
            "frameMetaMarkerCounts": dict(sorted(frame_meta_marker_counts.items())),
            "frameMetaLayoutCounts": dict(sorted(frame_meta_layout_counts.items())),
            "frameMetaGroupCount": frame_meta_group_count,
            "frameMetaLinkedGroupCount": frame_meta_linked_group_count,
            "frameMetaTailOnlyGroupCount": frame_meta_tail_only_group_count,
            "frameMetaGroupLinkCounts": dict(sorted(frame_meta_group_link_counts.items())),
            "frameMetaSequenceKindCounts": dict(sorted(frame_meta_sequence_kind_counts.items())),
            "frameMetaTimelineKindCounts": dict(sorted(frame_meta_timeline_kind_counts.items())),
            "frameMetaExactPzxCount": len(frame_meta_exact_stems),
            "frameMetaExactPreview": frame_meta_exact_stems[:20],
            "frameMetaSequencePreview": [
                {
                    "stem": entry["stem"],
                    "sequenceKind": entry["metaSequenceSummary"]["sequenceKind"],
                    "timelineKind": entry["metaSequenceSummary"]["timelineKind"],
                    "anchorFrameSequence": entry["metaSequenceSummary"]["anchorFrameSequence"][:8],
                    "overlayChunkRanges": entry["metaSequenceSummary"]["overlayChunkRanges"][:8],
                }
                for entry in frame_record_entries[:12]
            ],
            "frameRecordPreview": frame_record_entries[:12],
            "regularMplPaletteCount": len(regular_mpl_palette_stems),
            "regularMplPalettePreview": regular_mpl_palette_stems[:20],
            "paletteCapacityFitCount": len(palette_capacity_fit_stems),
            "paletteCapacityFitPreview": palette_capacity_fit_stems[:20],
            "rowStreamRegularMplPaletteCount": len(row_stream_regular_mpl_palette_stems),
            "rowStreamRegularMplPalettePreview": row_stream_regular_mpl_palette_stems[:20],
            "rowStreamPaletteCapacityFitCount": len(row_stream_palette_capacity_fit_stems),
            "rowStreamPaletteCapacityFitPreview": row_stream_palette_capacity_fit_stems[:20],
            "effectiveRegularMplPaletteCount": len(effective_regular_stems),
            "effectiveRegularMplPalettePreview": sorted(effective_regular_stems)[:20],
            "sharedMplGroupCount": len(shared_mpl_group_entries),
            "sharedMplGroupPreview": shared_mpl_group_entries[:8],
        },
        "findings": [
            "All PZX files start with magic 50 5a 58 01 ('PZX\\x01').",
            "Many PZX files contain one or more embedded zlib streams.",
            "For 205 PZX files, the first decoded zlib stream is a table of 32-bit chunk offsets followed by chunk payloads.",
            "Decoded variant=8 chunk records start with width(u16), height(u16), a CD-CD-CD tagged mode word (usually 02 or 04), declared payload length(u32), and reserved zero(u32).",
            "Chunk bodies are row-oriented RLE: each row expands to exactly chunk width bytes using skip(u16), literal(opcode 0x80nn + nn bytes), and repeat(opcode 0xC0nn + one value byte repeated nn times).",
            "Some chunks start with FD FF before the first row. Rows are separated by FE FF, and chunks end with a trailing FFFF sentinel after the final FE FF.",
            "Variant=7 assets such as 180.pzx expose the same row-oriented RLE directly as standalone zlib streams without the outer chunk header.",
            "179.pzx stream 1 is a simple 30-record placement table: each 10-byte record selects one chunk and places it at signed x/y coordinates, covering all 30 decoded chunks exactly once.",
            "For 61 paired MPL files, actualWordCount equals 2 * (maxDecodedIndex + 1) + 6, consistent with a 6-word header plus two palette banks.",
            "All 65 MPL files now match the stronger header model 560, 10, 0, (2 * colorCount + 11), 0, (7936 + colorCount), followed by two palette banks.",
            "229.pzx uses only indices 0..38 while its MPL carries 148 colors per bank, so at least one asset family keeps oversized palette banks instead of trimming them to the exact max index.",
            "180.pzx raw row streams top out at palette index 46, which exactly fits the shared 179/180 MPL payload as a 47-color two-bank palette.",
            "179.pzx still does not map directly to the 47-color shared palette, which suggests its byte values pack extra shading or effect bits above the base color index.",
            "Palette index 0 behaves like transparency more consistently than checking for a zero RGB565 word; bank B is the default visible sprite palette for the sampled stems, while flagged frame items are best explained as bank-A overlays.",
            f"Auxiliary frame-record streams are now recognized for {len(frame_record_stems)} stems ({len(frame_record_entries)} streams), with each item encoded as chunkIndex(u16), x(i16), y(i16), flag(u8).",
            f"{len(frame_record_control_stems)} of those stems also carry embedded 5-byte control chunks inside or between frame records; observed markers include 66 05 00 00 00, 66 0A 00 00 00, 66 0C 00 00 00, 67 78 00 00 00, and 67 FF 00 00 00.",
            "198.pzx parses as a clean frame-record prefix, while 208.pzx and 240.pzx both continue into a second metadata tail after the frame-record section. 208 also inserts 66 0C 00 00 00 inside individual records.",
            "084.pzx, 208.pzx, and 240.pzx all leave trailing sections beginning with 67 FF 00 00 00, which is the current best candidate separator for a secondary animation or timeline metadata layer.",
            f"The trailing tails now split into {frame_meta_section_count} marker-delimited sections. {frame_meta_marker_counts.get('67ff000000', 0)} use 67 FF 00 00 00 and {frame_meta_marker_counts.get('6778000000', 0)} use 67 78 00 00 00.",
            f"{len(frame_meta_exact_stems)} stems already expose exact-fit tail subsections that decode as 7-byte flagged tuples or simple 6-byte tuples, so at least part of the secondary metadata is structured placement data rather than opaque blobs.",
            f"Those sections cluster into {frame_meta_group_count} opaque-led tail groups. {frame_meta_linked_group_count} groups already have an exact tuple overlap with at least one base frame record, while {frame_meta_tail_only_group_count} groups use only chunk indices that never appear in the base frame stream.",
            f"Current group classification counts are: base-frame-delta={frame_meta_group_link_counts.get('base-frame-delta', 0)}, overlay-track={frame_meta_group_link_counts.get('overlay-track', 0)}, chunk-linked-reuse={frame_meta_group_link_counts.get('chunk-linked-reuse', 0)}, mixed-or-unknown={frame_meta_group_link_counts.get('mixed-or-unknown', 0)}, opaque-only={frame_meta_group_link_counts.get('opaque-only', 0)}.",
            f"Sequence-kind counts across frame-record stems are now: {', '.join(f'{key}={value}' for key, value in sorted(frame_meta_sequence_kind_counts.items()))}.",
            f"Timeline-kind counts are now: {', '.join(f'{key}={value}' for key, value in sorted(frame_meta_timeline_kind_counts.items()))}.",
            "MPL duplicates exist across stems: 145/146 share one file, and 179/180 share another, indicating some assets reuse the same palette or metadata blob.",
            "Once palette-capacity fits and shared MPL reuse are both accounted for, all 65 paired stems are covered by the current two-bank palette hypothesis.",
            "All MPL files share a fixed 32-bit signature 0x000A0230 and the field at offset 4 declares an apparent word count that is consistently actual_words + 5.",
        ],
        "pzx": pzx_entries,
        "mpl": mpl_entries,
    }

    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
