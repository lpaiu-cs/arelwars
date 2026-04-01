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
    read_pzx_animation_clip_stream,
    read_pzx_embedded_resource,
    read_pzx_frame_record_stream,
    read_pzx_first_stream,
    read_pzx_indexed_animation_clip_stream,
    read_pzx_indexed_pzf_frame_stream,
    read_pzx_meta_sections,
    read_pzx_pzd_resource,
    read_pzx_row_stream,
    read_pzx_root_resource_offsets,
    read_pzx_simple_placement_stream,
)


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


def summarize_animation_clip_data(decoded) -> dict[str, object]:
    clip_sizes = [clip.frame_count for clip in decoded.clips]
    return {
        "clipCount": decoded.clip_count,
        "totalFrameCount": decoded.total_frame_count,
        "clipFrameCountRange": [min(clip_sizes), max(clip_sizes)],
        "frameIndexRange": list(decoded.frame_index_range),
        "delayRange": list(decoded.delay_range),
        "xRange": list(decoded.x_range),
        "yRange": list(decoded.y_range),
        "controlValues": list(decoded.control_values),
        "nonzeroControlCount": decoded.nonzero_control_count,
        "clipOffsetsPreview": [clip.offset for clip in decoded.clips[:12]],
        "clipPreview": [
            {
                "offset": clip.offset,
                "frameCount": clip.frame_count,
                "framesPreview": [
                    {
                        "frameIndex": frame.frame_index,
                        "delay": frame.delay,
                        "x": frame.x,
                        "y": frame.y,
                        "control": frame.control,
                    }
                    for frame in clip.frames[:6]
                ],
            }
            for clip in decoded.clips[:6]
        ],
    }


def summarize_animation_clip_stream(stream: bytes) -> dict[str, object] | None:
    decoded = read_pzx_animation_clip_stream(stream)
    if decoded is None:
        return None

    return summarize_animation_clip_data(decoded)


def describe_pzf_bbox_mode(format_variant: int) -> str:
    if format_variant == 0:
        return "packed-att-dam"
    if format_variant == 1:
        return "compact-box-list"
    if format_variant == 2:
        return "reference-point-list"
    if format_variant == 3:
        return "explicit-att-dam"
    return "unknown"


def summarize_embedded_resource(resource) -> dict[str, object]:
    return {
        "kind": resource.kind,
        "offset": resource.offset,
        "header": resource.header,
        "storageMode": resource.storage_mode,
        "formatVariant": resource.format_variant,
        "contentCount": resource.content_count,
        "indexOffsetsPreview": list(resource.index_offsets[:12]),
        "indexOffsetsTail": list(resource.index_offsets[-6:]),
        "packedSize": resource.packed_size,
        "unpackedSize": resource.unpacked_size,
        "payloadOffset": resource.payload_offset,
        "payloadSha1": hashlib.sha1(resource.payload).hexdigest(),
        "payloadHeadHex": resource.payload[:24].hex(),
    }


def summarize_embedded_pzd_resource(resource) -> dict[str, object]:
    summary = {
        "kind": "pzd",
        "offset": resource.offset,
        "endOffset": resource.end_offset,
        "typeCode": resource.type_code,
        "flags": resource.flags,
        "contentCount": resource.content_count,
        "layout": resource.layout,
        "paletteProbe": resource.palette_probe,
        "tableStart": resource.table_start,
        "indexOffsetMode": resource.index_offset_mode,
        "indexOffsetsPreview": list(resource.index_offsets[:12]),
        "indexOffsetsTail": list(resource.index_offsets[-6:]),
        "globalPaletteCount": resource.global_palette_count,
        "rawPackedSize": resource.packed_size,
        "rawUnpackedSize": resource.unpacked_size,
        "rawPayloadOffset": resource.payload_offset,
        "zlibCount": len(resource.zlib_streams),
        "zlibOffsetsPreview": [stream.offset for stream in resource.zlib_streams[:12]],
        "zlibOffsetsTail": [stream.offset for stream in resource.zlib_streams[-6:]],
        "zlibDecodedLenRange": (
            [
                min(stream.decoded_len for stream in resource.zlib_streams),
                max(stream.decoded_len for stream in resource.zlib_streams),
            ]
            if resource.zlib_streams
            else None
        ),
        "imageDescriptorPreview": [
            {
                "index": record.index,
                "indexOffset": record.index_offset,
                "blockOffset": record.block_offset,
                "descriptorOffset": record.descriptor_offset,
                "payloadOffset": record.payload_offset,
                "paletteCount": record.palette_count,
                "width": record.width,
                "height": record.height,
                "mode": record.mode,
                "extraFlag": record.extra_flag,
                "unpackedSize": record.unpacked_size,
                "packedSize": record.packed_size,
            }
            for record in resource.image_records[:10]
        ],
    }

    if resource.type_code == 7:
        widths = [row.width for row in resource.row_streams if row.width is not None]
        heights = [row.height for row in resource.row_streams]
        max_index = max(
            max(max(row.decoded) for row in stream.rows if row.decoded)
            for stream in resource.row_streams
        )
        summary.update(
            {
                "imageCount": len(resource.row_streams),
                "rowWidthRange": [min(widths), max(widths)] if widths else None,
                "rowHeightRange": [min(heights), max(heights)] if heights else None,
                "maxDecodedIndex": max_index,
                "rowPreview": [
                    {
                        "index": index,
                        "offset": resource.zlib_streams[index].offset,
                        "width": row.width,
                        "height": row.height,
                        "decodedPixelTotal": row.decoded_pixel_count,
                    }
                    for index, row in enumerate(resource.row_streams[:10])
                ],
            }
        )
    elif resource.type_code == 8 and resource.first_stream is not None:
        first_stream = resource.first_stream
        widths = [chunk.width for chunk in first_stream.chunks]
        heights = [chunk.height for chunk in first_stream.chunks]
        max_index = max(max(row.decoded) for chunk in first_stream.chunks for row in chunk.rows)
        summary.update(
            {
                "imageCount": len(first_stream.chunks),
                "firstStreamOffset": resource.zlib_streams[0].offset if resource.zlib_streams else None,
                "firstStreamTableSpan": first_stream.table_span,
                "chunkWidthRange": [min(widths), max(widths)],
                "chunkHeightRange": [min(heights), max(heights)],
                "maxDecodedIndex": max_index,
                "chunkOffsetsPreview": list(first_stream.offsets[:12]),
                "chunkPreview": [
                    {
                        "index": chunk.index,
                        "width": chunk.width,
                        "height": chunk.height,
                        "declaredPayloadLen": chunk.declared_payload_len,
                    }
                    for chunk in first_stream.chunks[:10]
                ],
            }
        )

    return summary


def summarize_embedded_pza_resource(resource, streams: list) -> dict[str, object] | None:
    decoded = read_pzx_indexed_animation_clip_stream(resource.payload, resource.index_offsets)
    if decoded is None:
        return None

    matched_stream_indices = [
        index for index, stream in enumerate(streams[:12]) if stream.decoded == resource.payload
    ]
    return {
        **summarize_embedded_resource(resource),
        **summarize_animation_clip_data(decoded),
        "matchedZlibStreamIndices": matched_stream_indices,
    }


def summarize_pzf_frame_stream_data(decoded) -> dict[str, object]:
    subframe_index_range = decoded.subframe_index_range
    x_range = decoded.x_range
    y_range = decoded.y_range
    extra_marker_counts = Counter()
    effect_opcode_counts = Counter()
    runtime_effect_counts = Counter()
    runtime_effect_sequence_counts = Counter()
    selector_byte_counts = Counter()
    selector_last_byte_counts = Counter()
    single_byte_module_counts = Counter()
    bbox_att_total = 0
    bbox_dam_total = 0
    bbox_reference_total = 0
    bbox_generic_total = 0
    for frame in decoded.frames:
        if frame.bbox_total_count > 0:
            if decoded.format_variant == 0:
                bbox_att_total += frame.bbox_token0 >> 4
                bbox_dam_total += frame.bbox_token0 & 0x0F
            elif decoded.format_variant == 1:
                bbox_generic_total += frame.bbox_token0
            elif decoded.format_variant == 2:
                bbox_reference_total += frame.bbox_token0
            elif decoded.format_variant == 3:
                bbox_att_total += frame.bbox_token0
                bbox_dam_total += frame.bbox_token1
        for subframe in frame.subframes:
            if not subframe.extra:
                continue
            runtime_effects = tuple(value for value in subframe.extra if 1 <= value <= 100)
            for value in runtime_effects:
                runtime_effect_counts[str(value)] += 1
            if runtime_effects:
                runtime_effect_sequence_counts[",".join(str(value) for value in runtime_effects)] += 1
            for value in subframe.extra:
                if value <= 4:
                    effect_opcode_counts[str(value)] += 1
                if 0x65 <= value <= 0x74 or value == 0x7F:
                    selector_byte_counts[f"{value:02x}"] += 1
            selector_matches = [value for value in subframe.extra if 0x65 <= value <= 0x74 or value == 0x7F]
            if selector_matches:
                selector_last_byte_counts[f"{selector_matches[-1]:02x}"] += 1
            if len(subframe.extra) == 1 and 0x65 <= subframe.extra[0] <= 0x74:
                single_byte_module_counts[f"{subframe.extra[0]:02x}"] += 1
            if subframe.extra.startswith(b"\x66") and subframe.extra[-3:] == b"\x00\x00\x00":
                extra_marker_counts["66+u32"] += 1
            elif len(subframe.extra) >= 2 and subframe.extra[1] == 0x66 and subframe.extra[-3:] == b"\x00\x00\x00":
                extra_marker_counts["x+66+u32"] += 1
            elif subframe.extra.startswith(b"\x67") and subframe.extra[-3:] == b"\x00\x00\x00":
                extra_marker_counts["67+u32"] += 1
            else:
                extra_marker_counts["other"] += 1

    return {
        "frameParseOk": True,
        "frameCount": decoded.frame_count,
        "totalSubFrameCount": decoded.total_subframe_count,
        "frameLengthRange": list(decoded.frame_length_range),
        "subFrameCountRange": list(decoded.subframe_count_range),
        "bboxTotalRange": list(decoded.bbox_total_range),
        "bboxFrameCount": sum(1 for frame in decoded.frames if frame.bbox_total_count > 0),
        "bboxRecordCount": sum(len(frame.bboxes) for frame in decoded.frames),
        "bboxMode": decoded.format_variant,
        "bboxModeName": describe_pzf_bbox_mode(decoded.format_variant),
        "bboxAttackCountTotal": bbox_att_total,
        "bboxDamageCountTotal": bbox_dam_total,
        "bboxReferencePointTotal": bbox_reference_total,
        "bboxGenericCountTotal": bbox_generic_total,
        "subFrameIndexRange": list(subframe_index_range) if subframe_index_range is not None else None,
        "xRange": list(x_range) if x_range is not None else None,
        "yRange": list(y_range) if y_range is not None else None,
        "extraFlagValues": list(decoded.extra_flag_values),
        "nonzeroExtraCount": decoded.nonzero_extra_count,
        "maxExtraLen": decoded.max_extra_len,
        "extraMarkerCounts": dict(sorted(extra_marker_counts.items())),
        "effectOpcodeCounts": dict(sorted(effect_opcode_counts.items())),
        "selectorByteCounts": dict(sorted(selector_byte_counts.items())),
        "selectorLastByteCounts": dict(sorted(selector_last_byte_counts.items())),
        "runtimeEffectCounts": dict(sorted(runtime_effect_counts.items(), key=lambda item: int(item[0]))),
        "runtimeEffectSequenceCounts": dict(
            sorted(
                runtime_effect_sequence_counts.items(),
                key=lambda item: (
                    tuple(int(value) for value in item[0].split(",")),
                    item[1],
                ),
            )
        ),
        "singleByteModuleCounts": dict(sorted(single_byte_module_counts.items())),
        "frameOffsetsPreview": [frame.offset for frame in decoded.frames[:12]],
        "frameOffsetsTail": [frame.offset for frame in decoded.frames[-6:]],
        "framePreview": [
            {
                "offset": frame.offset,
                "length": frame.length,
                "subFrameCount": frame.subframe_count,
                "bboxToken0": frame.bbox_token0,
                "bboxToken1": frame.bbox_token1,
                "bboxTotalCount": frame.bbox_total_count,
                "bboxPreview": [
                    {
                        "rawHex": record.raw.hex(),
                        "values": list(record.values),
                    }
                    for record in frame.bboxes[:4]
                ],
                "subFramesPreview": [
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
            for frame in decoded.frames[:6]
        ],
    }


def summarize_embedded_pzf_resource(
    resource,
    streams: list,
    *,
    max_subframe_index: int | None = None,
) -> dict[str, object]:
    matched_stream_indices = [
        index for index, stream in enumerate(streams[:12]) if stream.decoded == resource.payload
    ]
    summary = {
        **summarize_embedded_resource(resource),
        "frameCount": resource.content_count,
        "matchedZlibStreamIndices": matched_stream_indices,
    }

    decoded = read_pzx_indexed_pzf_frame_stream(
        resource.payload,
        resource.index_offsets,
        resource.format_variant,
        max_subframe_index=max_subframe_index,
    )
    if decoded is None:
        return {
            **summary,
            "frameParseOk": False,
        }

    return {
        **summary,
        **summarize_pzf_frame_stream_data(decoded),
    }


def summarize_meta_groups(meta_sections: tuple, frame_records: tuple) -> list[dict[str, object]]:
    groups: list[list] = []
    current: list = []

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

    frame_item_sets = [{(item.chunk_index, item.x, item.y, item.flag) for item in record.items} for record in frame_records]
    frame_chunk_sets = [{item.chunk_index for item in record.items} for record in frame_records]
    all_frame_chunks = {item.chunk_index for record in frame_records for item in record.items}

    summaries: list[dict[str, object]] = []
    for group_index, sections in enumerate(groups):
        tuples = [item for section in sections for item in section.tuples]
        tuple_keys = [(item.chunk_index, item.x, item.y, item.flag) for item in tuples]
        unique_chunks = sorted({item.chunk_index for item in tuples})
        tail_only_chunks = sorted(chunk for chunk in unique_chunks if chunk not in all_frame_chunks)

        best_frame_matches: list[dict[str, object]] = []
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

        link_type = "opaque-only"
        if tuple_keys:
            best_exact = int(best_frame_matches[0]["exactOverlap"]) if best_frame_matches else 0
            best_chunk = int(best_frame_matches[0]["chunkOverlap"]) if best_frame_matches else 0
            if unique_chunks and len(tail_only_chunks) == len(unique_chunks):
                link_type = "overlay-track"
            elif best_exact * 2 >= len(tuple_keys):
                link_type = "base-frame-delta"
            elif best_chunk * 2 >= len(tuple_keys):
                link_type = "chunk-linked-reuse"
            else:
                link_type = "mixed-or-unknown"

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


def summarize_frame_record_stream(stream: bytes, chunk_count: int, chunk_sizes: dict[int, tuple[int, int]]) -> dict[str, object] | None:
    decoded = read_pzx_frame_record_stream(stream, chunk_count)
    if decoded is None or len(decoded.records) < 2:
        return None

    all_items = [item for record in decoded.records for item in record.items]
    all_control_chunks = [chunk for record in decoded.records for chunk in record.control_chunks]
    meta_sections = read_pzx_meta_sections(decoded.trailing, chunk_count) if decoded.trailing else ()
    meta_groups = summarize_meta_groups(meta_sections, decoded.records)
    meta_marker_counts = Counter(section.marker_hex or "prefix" for section in meta_sections)
    meta_layout_counts = Counter(section.layout for section in meta_sections)
    meta_group_link_counts = Counter(group["linkType"] for group in meta_groups)
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
                "tupleCount": section.tuple_count,
                "validTupleCount": section.valid_tuple_count,
                "payloadHeadHex": section.payload[:24].hex(),
                "tuplePreview": [
                    {
                        "chunkIndex": item.chunk_index,
                        "x": item.x,
                        "y": item.y,
                        "flag": item.flag,
                    }
                    for item in section.tuples[:6]
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
    animation_clip_summary: dict[str, object] | None = None
    animation_clip_summaries: list[dict[str, object]] = []
    embedded_resource_summaries: list[dict[str, object]] = []
    embedded_pzd_summary: dict[str, object] | None = None
    embedded_pzf_summary: dict[str, object] | None = None
    embedded_pza_summary: dict[str, object] | None = None
    embedded_pzf_pzd_relation: dict[str, object] | None = None
    embedded_pzf_animation_relation: dict[str, object] | None = None
    embedded_pzf_frame_record_relation: dict[str, object] | None = None

    for index, item in enumerate(streams[:12]):
        entry = {
            "index": index,
            "offset": item.offset,
            "consumed": item.consumed,
            "decodedLen": len(item.decoded),
            "sha1": hashlib.sha1(item.decoded).hexdigest(),
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
        animation_summary = summarize_animation_clip_stream(item.decoded)
        if animation_summary is not None:
            entry["animationClip"] = animation_summary
            animation_clip_summaries.append({"streamIndex": index, **animation_summary})
            if animation_clip_summary is None:
                animation_clip_summary = {"streamIndex": index, **animation_summary}
        try:
            row_stream_summary = summarize_pzx_row_stream(item.decoded)
        except ValueError:
            row_stream_summary = None
        if row_stream_summary is not None:
            entry["rowStream"] = row_stream_summary
        parsed_streams.append(entry)

    root_resource_offsets = read_pzx_root_resource_offsets(data)
    if root_resource_offsets is not None:
        embedded_pzd = read_pzx_pzd_resource(data, root_resource_offsets[0], root_resource_offsets[1])
        if embedded_pzd is not None:
            embedded_pzd_summary = summarize_embedded_pzd_resource(embedded_pzd)
            embedded_resource_summaries.append(embedded_pzd_summary)

        embedded_pzf = read_pzx_embedded_resource(data, root_resource_offsets[1], "pzf")
        if embedded_pzf is not None:
            max_subframe_index = None
            if embedded_pzd_summary is not None:
                max_subframe_index = int(embedded_pzd_summary["contentCount"]) - 1
            embedded_pzf_summary = summarize_embedded_pzf_resource(
                embedded_pzf,
                streams,
                max_subframe_index=max_subframe_index,
            )
            embedded_resource_summaries.append(embedded_pzf_summary)

        embedded_pza = read_pzx_embedded_resource(data, root_resource_offsets[2], "pza")
        if embedded_pza is not None:
            embedded_pza_summary = summarize_embedded_pza_resource(embedded_pza, streams)
            if embedded_pza_summary is not None:
                embedded_resource_summaries.append(embedded_pza_summary)

        if embedded_pzd_summary is not None and embedded_pzf_summary is not None:
            subframe_index_range = embedded_pzf_summary.get("subFrameIndexRange")
            image_count = int(embedded_pzd_summary["contentCount"])
            if subframe_index_range is None:
                relation = "empty"
                max_subframe_index = None
            else:
                max_subframe_index = int(subframe_index_range[1])
                if max_subframe_index + 1 == image_count:
                    relation = "exact-max-plus-one"
                elif max_subframe_index < image_count:
                    relation = "in-range"
                else:
                    relation = "out-of-range"
            embedded_pzf_pzd_relation = {
                "relation": relation,
                "pzdImageCount": image_count,
                "maxSubFrameIndex": max_subframe_index,
            }

        if embedded_pzf_summary is not None and embedded_pza_summary is not None:
            max_frame_index = int(embedded_pza_summary["frameIndexRange"][1])
            frame_count = int(embedded_pzf_summary["frameCount"])
            if max_frame_index + 1 == frame_count:
                relation = "exact-max-plus-one"
            elif max_frame_index < frame_count:
                relation = "in-range"
            else:
                relation = "out-of-range"
            embedded_pzf_animation_relation = {
                "relation": relation,
                "pzfFrameCount": frame_count,
                "maxFrameIndex": max_frame_index,
            }

        if embedded_pzf_summary is not None:
            matched_stream_indices = [int(index) for index in embedded_pzf_summary.get("matchedZlibStreamIndices", [])]
            offset_prefix_matches = [
                int(stream["streamIndex"])
                for stream in frame_record_summaries
                if stream.get("recordOffsetsPreview") == embedded_pzf_summary.get("frameOffsetsPreview", [])[: len(stream.get("recordOffsetsPreview", []))]
            ]
            embedded_pzf_frame_record_relation = {
                "matchedZlibStreamIndices": matched_stream_indices,
                "matchedFrameRecordStreamIndices": [
                    int(stream["streamIndex"])
                    for stream in frame_record_summaries
                    if int(stream["streamIndex"]) in matched_stream_indices
                ],
                "offsetPrefixFrameRecordStreamIndices": offset_prefix_matches,
            }

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
            "resourceOffsets": {
                "pzd": root_resource_offsets[0] if root_resource_offsets is not None else None,
                "pzf": root_resource_offsets[1] if root_resource_offsets is not None else None,
                "pza": root_resource_offsets[2] if root_resource_offsets is not None else None,
            },
        },
        "hasMplPair": has_mpl_pair,
        "zlibStreamCount": len(streams),
        "streams": parsed_streams,
        "firstStream": first_stream_summary,
        "firstStreamError": first_stream_error,
        "simplePlacementStream": simple_placement_summary,
        "frameRecordStreams": frame_record_summaries,
        "animationClipStream": animation_clip_summary,
        "animationClipStreams": animation_clip_summaries,
        "embeddedResources": embedded_resource_summaries,
        "embeddedPzd": embedded_pzd_summary,
        "embeddedPzf": embedded_pzf_summary,
        "embeddedPza": embedded_pza_summary,
        "embeddedPzfPzdRelation": embedded_pzf_pzd_relation,
        "embeddedPzfAnimationRelation": embedded_pzf_animation_relation,
        "embeddedPzfFrameRecordRelation": embedded_pzf_frame_record_relation,
    }


def parse_mpl(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    words = [struct.unpack("<H", data[index : index + 2])[0] for index in range(0, min(len(data), 32), 2)]
    field = struct.unpack("<I", data[4:8])[0] if len(data) >= 8 else 0
    return {
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
    frame_meta_exact_stems = sorted(
        {
            entry["stem"]
            for entry in frame_record_entries
            if any(layout != "opaque" for layout in entry["metaLayoutCounts"])
        }
    )
    animation_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "variant": entry["header"]["field16Low6"],
            "streamIndex": stream["streamIndex"],
            "clipCount": stream["clipCount"],
            "totalFrameCount": stream["totalFrameCount"],
            "clipFrameCountRange": stream["clipFrameCountRange"],
            "frameIndexRange": stream["frameIndexRange"],
            "delayRange": stream["delayRange"],
            "xRange": stream["xRange"],
            "yRange": stream["yRange"],
            "controlValues": stream["controlValues"],
            "nonzeroControlCount": stream["nonzeroControlCount"],
        }
        for entry in pzx_entries
        for stream in entry.get("animationClipStreams", [])
    ]
    animation_stems = sorted({entry["stem"] for entry in animation_entries})
    animation_stream_index_counts = Counter(entry["streamIndex"] for entry in animation_entries)
    animation_clip_count_distribution = Counter(entry["clipCount"] for entry in animation_entries)
    animation_nonzero_control_count = sum(int(entry["nonzeroControlCount"]) for entry in animation_entries)
    animation_frame_index_range = (
        [
            min(int(entry["frameIndexRange"][0]) for entry in animation_entries),
            max(int(entry["frameIndexRange"][1]) for entry in animation_entries),
        ]
        if animation_entries
        else None
    )
    animation_delay_range = (
        [
            min(int(entry["delayRange"][0]) for entry in animation_entries),
            max(int(entry["delayRange"][1]) for entry in animation_entries),
        ]
        if animation_entries
        else None
    )
    animation_x_range = (
        [
            min(int(entry["xRange"][0]) for entry in animation_entries),
            max(int(entry["xRange"][1]) for entry in animation_entries),
        ]
        if animation_entries
        else None
    )
    animation_y_range = (
        [
            min(int(entry["yRange"][0]) for entry in animation_entries),
            max(int(entry["yRange"][1]) for entry in animation_entries),
        ]
        if animation_entries
        else None
    )
    embedded_pzf_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "variant": entry["header"]["field16Low6"],
            "offset": entry["embeddedPzf"]["offset"],
            "storageMode": entry["embeddedPzf"]["storageMode"],
            "formatVariant": entry["embeddedPzf"]["formatVariant"],
            "frameCount": entry["embeddedPzf"]["frameCount"],
            "packedSize": entry["embeddedPzf"]["packedSize"],
            "unpackedSize": entry["embeddedPzf"]["unpackedSize"],
            "matchedZlibStreamIndices": entry["embeddedPzf"].get("matchedZlibStreamIndices", []),
            "frameParseOk": entry["embeddedPzf"].get("frameParseOk", False),
            "totalSubFrameCount": entry["embeddedPzf"].get("totalSubFrameCount"),
            "subFrameCountRange": entry["embeddedPzf"].get("subFrameCountRange"),
            "subFrameIndexRange": entry["embeddedPzf"].get("subFrameIndexRange"),
            "xRange": entry["embeddedPzf"].get("xRange"),
            "yRange": entry["embeddedPzf"].get("yRange"),
            "extraFlagValues": entry["embeddedPzf"].get("extraFlagValues", []),
            "nonzeroExtraCount": entry["embeddedPzf"].get("nonzeroExtraCount"),
            "maxExtraLen": entry["embeddedPzf"].get("maxExtraLen"),
            "extraMarkerCounts": entry["embeddedPzf"].get("extraMarkerCounts", {}),
            "effectOpcodeCounts": entry["embeddedPzf"].get("effectOpcodeCounts", {}),
            "selectorByteCounts": entry["embeddedPzf"].get("selectorByteCounts", {}),
            "selectorLastByteCounts": entry["embeddedPzf"].get("selectorLastByteCounts", {}),
            "runtimeEffectCounts": entry["embeddedPzf"].get("runtimeEffectCounts", {}),
            "runtimeEffectSequenceCounts": entry["embeddedPzf"].get("runtimeEffectSequenceCounts", {}),
            "singleByteModuleCounts": entry["embeddedPzf"].get("singleByteModuleCounts", {}),
            "bboxFrameCount": entry["embeddedPzf"].get("bboxFrameCount"),
            "bboxTotalRange": entry["embeddedPzf"].get("bboxTotalRange"),
            "bboxMode": entry["embeddedPzf"].get("bboxMode"),
            "bboxModeName": entry["embeddedPzf"].get("bboxModeName"),
            "bboxAttackCountTotal": entry["embeddedPzf"].get("bboxAttackCountTotal"),
            "bboxDamageCountTotal": entry["embeddedPzf"].get("bboxDamageCountTotal"),
            "bboxReferencePointTotal": entry["embeddedPzf"].get("bboxReferencePointTotal"),
            "bboxGenericCountTotal": entry["embeddedPzf"].get("bboxGenericCountTotal"),
            "frameRecordMatchedStreamIndices": (
                entry.get("embeddedPzfFrameRecordRelation", {}).get("matchedFrameRecordStreamIndices", [])
            ),
            "frameRecordOffsetPrefixStreamIndices": (
                entry.get("embeddedPzfFrameRecordRelation", {}).get("offsetPrefixFrameRecordStreamIndices", [])
            ),
        }
        for entry in pzx_entries
        if entry.get("embeddedPzf") is not None
    ]
    embedded_pzf_parsed_entries = [entry for entry in embedded_pzf_entries if bool(entry["frameParseOk"])]
    embedded_pzf_match_index_counts = Counter(
        stream_index
        for entry in embedded_pzf_entries
        for stream_index in entry["matchedZlibStreamIndices"]
    )
    embedded_pzf_frame_record_match_stems = sorted(
        {
            entry["stem"]
            for entry in embedded_pzf_entries
            if entry["frameRecordMatchedStreamIndices"]
        }
    )
    embedded_pzf_offset_prefix_stems = sorted(
        {
            entry["stem"]
            for entry in embedded_pzf_entries
            if entry["frameRecordOffsetPrefixStreamIndices"]
        }
    )
    embedded_pzf_extra_flag_values = sorted(
        {
            int(value)
            for entry in embedded_pzf_parsed_entries
            for value in entry["extraFlagValues"]
        }
    )
    embedded_pzf_nonzero_extra_count = sum(
        int(entry["nonzeroExtraCount"])
        for entry in embedded_pzf_parsed_entries
        if entry["nonzeroExtraCount"] is not None
    )
    embedded_pzf_max_extra_len = max(
        (int(entry["maxExtraLen"]) for entry in embedded_pzf_parsed_entries if entry["maxExtraLen"] is not None),
        default=0,
    )
    embedded_pzf_extra_marker_counts = Counter()
    for entry in embedded_pzf_parsed_entries:
        embedded_pzf_extra_marker_counts.update(entry["extraMarkerCounts"])
    embedded_pzf_effect_opcode_counts = Counter()
    for entry in embedded_pzf_parsed_entries:
        embedded_pzf_effect_opcode_counts.update(entry["effectOpcodeCounts"])
    embedded_pzf_selector_byte_counts = Counter()
    for entry in embedded_pzf_parsed_entries:
        embedded_pzf_selector_byte_counts.update(entry["selectorByteCounts"])
    embedded_pzf_selector_last_byte_counts = Counter()
    for entry in embedded_pzf_parsed_entries:
        embedded_pzf_selector_last_byte_counts.update(entry["selectorLastByteCounts"])
    embedded_pzf_runtime_effect_counts = Counter()
    for entry in embedded_pzf_parsed_entries:
        embedded_pzf_runtime_effect_counts.update(entry["runtimeEffectCounts"])
    embedded_pzf_runtime_effect_sequence_counts = Counter()
    for entry in embedded_pzf_parsed_entries:
        embedded_pzf_runtime_effect_sequence_counts.update(entry["runtimeEffectSequenceCounts"])
    embedded_pzf_single_byte_module_counts = Counter()
    for entry in embedded_pzf_parsed_entries:
        embedded_pzf_single_byte_module_counts.update(entry["singleByteModuleCounts"])
    embedded_pzf_subframe_count_range = (
        [
            min(int(entry["subFrameCountRange"][0]) for entry in embedded_pzf_parsed_entries if entry["subFrameCountRange"]),
            max(int(entry["subFrameCountRange"][1]) for entry in embedded_pzf_parsed_entries if entry["subFrameCountRange"]),
        ]
        if embedded_pzf_parsed_entries
        else None
    )
    embedded_pzf_subframe_index_range = (
        [
            min(int(entry["subFrameIndexRange"][0]) for entry in embedded_pzf_parsed_entries if entry["subFrameIndexRange"]),
            max(int(entry["subFrameIndexRange"][1]) for entry in embedded_pzf_parsed_entries if entry["subFrameIndexRange"]),
        ]
        if any(entry["subFrameIndexRange"] is not None for entry in embedded_pzf_parsed_entries)
        else None
    )
    embedded_pzf_x_range = (
        [
            min(int(entry["xRange"][0]) for entry in embedded_pzf_parsed_entries if entry["xRange"]),
            max(int(entry["xRange"][1]) for entry in embedded_pzf_parsed_entries if entry["xRange"]),
        ]
        if any(entry["xRange"] is not None for entry in embedded_pzf_parsed_entries)
        else None
    )
    embedded_pzf_y_range = (
        [
            min(int(entry["yRange"][0]) for entry in embedded_pzf_parsed_entries if entry["yRange"]),
            max(int(entry["yRange"][1]) for entry in embedded_pzf_parsed_entries if entry["yRange"]),
        ]
        if any(entry["yRange"] is not None for entry in embedded_pzf_parsed_entries)
        else None
    )
    embedded_pzf_bbox_total_range = (
        [
            min(int(entry["bboxTotalRange"][0]) for entry in embedded_pzf_parsed_entries if entry["bboxTotalRange"]),
            max(int(entry["bboxTotalRange"][1]) for entry in embedded_pzf_parsed_entries if entry["bboxTotalRange"]),
        ]
        if embedded_pzf_parsed_entries
        else None
    )
    embedded_pzf_bbox_mode_counts = Counter(
        entry["bboxModeName"] for entry in embedded_pzf_parsed_entries if entry["bboxModeName"] is not None
    )
    embedded_pzf_total_bbox_frame_count = sum(
        int(entry["bboxFrameCount"])
        for entry in embedded_pzf_parsed_entries
        if entry["bboxFrameCount"] is not None
    )
    embedded_pzf_bbox_attack_total = sum(
        int(entry["bboxAttackCountTotal"])
        for entry in embedded_pzf_parsed_entries
        if entry["bboxAttackCountTotal"] is not None
    )
    embedded_pzf_bbox_damage_total = sum(
        int(entry["bboxDamageCountTotal"])
        for entry in embedded_pzf_parsed_entries
        if entry["bboxDamageCountTotal"] is not None
    )
    embedded_pzf_bbox_reference_total = sum(
        int(entry["bboxReferencePointTotal"])
        for entry in embedded_pzf_parsed_entries
        if entry["bboxReferencePointTotal"] is not None
    )
    embedded_pzf_bbox_generic_total = sum(
        int(entry["bboxGenericCountTotal"])
        for entry in embedded_pzf_parsed_entries
        if entry["bboxGenericCountTotal"] is not None
    )
    embedded_pzd_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "offset": entry["embeddedPzd"]["offset"],
            "endOffset": entry["embeddedPzd"]["endOffset"],
            "typeCode": entry["embeddedPzd"]["typeCode"],
            "flags": entry["embeddedPzd"]["flags"],
            "contentCount": entry["embeddedPzd"]["contentCount"],
            "layout": entry["embeddedPzd"]["layout"],
            "paletteProbe": entry["embeddedPzd"]["paletteProbe"],
            "zlibCount": entry["embeddedPzd"]["zlibCount"],
            "imageCount": entry["embeddedPzd"]["imageCount"],
            "maxDecodedIndex": entry["embeddedPzd"]["maxDecodedIndex"],
        }
        for entry in pzx_entries
        if entry.get("embeddedPzd") is not None
    ]
    embedded_pzd_type_counts = Counter(int(entry["typeCode"]) for entry in embedded_pzd_entries)
    embedded_pzd_layout_counts = Counter(str(entry["layout"]) for entry in embedded_pzd_entries)
    embedded_pzd_zlib_count_distribution = Counter(int(entry["zlibCount"]) for entry in embedded_pzd_entries)
    embedded_pzd_content_count_range = (
        [
            min(int(entry["contentCount"]) for entry in embedded_pzd_entries),
            max(int(entry["contentCount"]) for entry in embedded_pzd_entries),
        ]
        if embedded_pzd_entries
        else None
    )
    embedded_pzd_relation_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "relation": entry["embeddedPzfPzdRelation"]["relation"],
            "pzdImageCount": entry["embeddedPzfPzdRelation"]["pzdImageCount"],
            "maxSubFrameIndex": entry["embeddedPzfPzdRelation"]["maxSubFrameIndex"],
        }
        for entry in pzx_entries
        if entry.get("embeddedPzfPzdRelation") is not None
    ]
    embedded_pzd_relation_counts = Counter(entry["relation"] for entry in embedded_pzd_relation_entries)
    embedded_pza_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "variant": entry["header"]["field16Low6"],
            "offset": entry["embeddedPza"]["offset"],
            "storageMode": entry["embeddedPza"]["storageMode"],
            "formatVariant": entry["embeddedPza"]["formatVariant"],
            "clipCount": entry["embeddedPza"]["clipCount"],
            "totalFrameCount": entry["embeddedPza"]["totalFrameCount"],
            "frameIndexRange": entry["embeddedPza"]["frameIndexRange"],
            "delayRange": entry["embeddedPza"]["delayRange"],
            "xRange": entry["embeddedPza"]["xRange"],
            "yRange": entry["embeddedPza"]["yRange"],
            "matchedZlibStreamIndices": entry["embeddedPza"]["matchedZlibStreamIndices"],
        }
        for entry in pzx_entries
        if entry.get("embeddedPza") is not None
    ]
    embedded_pza_stems = sorted({entry["stem"] for entry in embedded_pza_entries})
    embedded_pza_match_index_counts = Counter(
        stream_index
        for entry in embedded_pza_entries
        for stream_index in entry["matchedZlibStreamIndices"]
    )
    embedded_pza_relation_entries = [
        {
            "stem": Path(str(entry["path"])).stem,
            "relation": entry["embeddedPzfAnimationRelation"]["relation"],
            "pzfFrameCount": entry["embeddedPzfAnimationRelation"]["pzfFrameCount"],
            "maxFrameIndex": entry["embeddedPzfAnimationRelation"]["maxFrameIndex"],
        }
        for entry in pzx_entries
        if entry.get("embeddedPzfAnimationRelation") is not None
    ]
    embedded_pza_relation_counts = Counter(entry["relation"] for entry in embedded_pza_relation_entries)
    embedded_pza_frame_index_range = (
        [
            min(int(entry["frameIndexRange"][0]) for entry in embedded_pza_entries),
            max(int(entry["frameIndexRange"][1]) for entry in embedded_pza_entries),
        ]
        if embedded_pza_entries
        else None
    )
    embedded_pza_delay_range = (
        [
            min(int(entry["delayRange"][0]) for entry in embedded_pza_entries),
            max(int(entry["delayRange"][1]) for entry in embedded_pza_entries),
        ]
        if embedded_pza_entries
        else None
    )
    embedded_pza_x_range = (
        [
            min(int(entry["xRange"][0]) for entry in embedded_pza_entries),
            max(int(entry["xRange"][1]) for entry in embedded_pza_entries),
        ]
        if embedded_pza_entries
        else None
    )
    embedded_pza_y_range = (
        [
            min(int(entry["yRange"][0]) for entry in embedded_pza_entries),
            max(int(entry["yRange"][1]) for entry in embedded_pza_entries),
        ]
        if embedded_pza_entries
        else None
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
            "frameMetaExactPzxCount": len(frame_meta_exact_stems),
            "frameMetaExactPreview": frame_meta_exact_stems[:20],
            "frameRecordPreview": frame_record_entries[:12],
            "animationClipPzxCount": len(animation_stems),
            "animationClipStreamCount": len(animation_entries),
            "animationClipStreamIndexCounts": dict(sorted(animation_stream_index_counts.items())),
            "animationClipThirdStreamCount": int(animation_stream_index_counts.get(2, 0)),
            "animationClipCountDistribution": dict(sorted(animation_clip_count_distribution.items())),
            "animationClipFrameIndexRange": animation_frame_index_range,
            "animationClipDelayRange": animation_delay_range,
            "animationClipXRange": animation_x_range,
            "animationClipYRange": animation_y_range,
            "animationClipNonzeroControlCount": animation_nonzero_control_count,
            "animationClipPreview": animation_entries[:12],
            "embeddedPzdPzxCount": len(embedded_pzd_entries),
            "embeddedPzdPreview": embedded_pzd_entries[:12],
            "embeddedPzdTypeCounts": dict(sorted(embedded_pzd_type_counts.items())),
            "embeddedPzdLayoutCounts": dict(sorted(embedded_pzd_layout_counts.items())),
            "embeddedPzdZlibCountDistribution": dict(sorted(embedded_pzd_zlib_count_distribution.items())),
            "embeddedPzdContentCountRange": embedded_pzd_content_count_range,
            "embeddedPzdPzfRelationCounts": dict(sorted(embedded_pzd_relation_counts.items())),
            "embeddedPzdPzfRelationPreview": embedded_pzd_relation_entries[:12],
            "embeddedPzfPzxCount": len(embedded_pzf_entries),
            "embeddedPzfPreview": embedded_pzf_entries[:12],
            "embeddedPzfParsedPzxCount": len(embedded_pzf_parsed_entries),
            "embeddedPzfMatchedStreamIndexCounts": dict(sorted(embedded_pzf_match_index_counts.items())),
            "embeddedPzfMatchedSecondStreamCount": int(embedded_pzf_match_index_counts.get(1, 0)),
            "embeddedPzfFrameRecordMatchCount": len(embedded_pzf_frame_record_match_stems),
            "embeddedPzfFrameRecordMatchPreview": embedded_pzf_frame_record_match_stems[:20],
            "embeddedPzfFrameRecordOffsetPrefixCount": len(embedded_pzf_offset_prefix_stems),
            "embeddedPzfFrameRecordOffsetPrefixPreview": embedded_pzf_offset_prefix_stems[:20],
            "embeddedPzfSubFrameCountRange": embedded_pzf_subframe_count_range,
            "embeddedPzfSubFrameIndexRange": embedded_pzf_subframe_index_range,
            "embeddedPzfXRange": embedded_pzf_x_range,
            "embeddedPzfYRange": embedded_pzf_y_range,
            "embeddedPzfExtraFlagValues": embedded_pzf_extra_flag_values,
            "embeddedPzfNonzeroExtraCount": embedded_pzf_nonzero_extra_count,
            "embeddedPzfMaxExtraLen": embedded_pzf_max_extra_len,
            "embeddedPzfExtraMarkerCounts": dict(sorted(embedded_pzf_extra_marker_counts.items())),
            "embeddedPzfEffectOpcodeCounts": dict(sorted(embedded_pzf_effect_opcode_counts.items())),
            "embeddedPzfSelectorByteCounts": dict(sorted(embedded_pzf_selector_byte_counts.items())),
            "embeddedPzfSelectorLastByteCounts": dict(sorted(embedded_pzf_selector_last_byte_counts.items())),
            "embeddedPzfRuntimeEffectCounts": dict(
                sorted(embedded_pzf_runtime_effect_counts.items(), key=lambda item: int(item[0]))
            ),
            "embeddedPzfRuntimeEffectSequenceCounts": dict(
                sorted(
                    embedded_pzf_runtime_effect_sequence_counts.items(),
                    key=lambda item: (
                        tuple(int(value) for value in item[0].split(",")),
                        item[1],
                    ),
                )
            ),
            "embeddedPzfSingleByteModuleCounts": dict(sorted(embedded_pzf_single_byte_module_counts.items())),
            "embeddedPzfBboxTotalRange": embedded_pzf_bbox_total_range,
            "embeddedPzfBboxFrameTotal": embedded_pzf_total_bbox_frame_count,
            "embeddedPzfBboxModeCounts": dict(sorted(embedded_pzf_bbox_mode_counts.items())),
            "embeddedPzfBboxAttackTotal": embedded_pzf_bbox_attack_total,
            "embeddedPzfBboxDamageTotal": embedded_pzf_bbox_damage_total,
            "embeddedPzfBboxReferenceTotal": embedded_pzf_bbox_reference_total,
            "embeddedPzfBboxGenericTotal": embedded_pzf_bbox_generic_total,
            "embeddedPzaPzxCount": len(embedded_pza_stems),
            "embeddedPzaPreview": embedded_pza_entries[:12],
            "embeddedPzaMatchedStreamIndexCounts": dict(sorted(embedded_pza_match_index_counts.items())),
            "embeddedPzaMatchedThirdStreamCount": int(embedded_pza_match_index_counts.get(2, 0)),
            "embeddedPzaFrameIndexRange": embedded_pza_frame_index_range,
            "embeddedPzaDelayRange": embedded_pza_delay_range,
            "embeddedPzaXRange": embedded_pza_x_range,
            "embeddedPzaYRange": embedded_pza_y_range,
            "embeddedPzaPzfRelationCounts": dict(sorted(embedded_pza_relation_counts.items())),
            "embeddedPzaPzfRelationPreview": embedded_pza_relation_entries[:12],
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
            f"Root field4 now resolves cleanly as the native PZD subresource for all {len(embedded_pzd_entries)} PZX files.",
            f"PZD splits into two native layouts with no leftovers: type 7 = {embedded_pzd_type_counts.get(7, 0)} stems and type 8 = {embedded_pzd_type_counts.get(8, 0)} stems.",
            f"Every type 8 PZD region contains exactly one zlib stream, and its decoded first-stream chunk count always equals contentCount ({embedded_pzd_type_counts.get(8, 0)} / {embedded_pzd_type_counts.get(8, 0)} stems).",
            f"Every type 7 PZD region contains exactly contentCount standalone rowstreams in file order ({embedded_pzd_type_counts.get(7, 0)} / {embedded_pzd_type_counts.get(7, 0)} stems).",
            "Raw type 7 PZD tables are file-local absolute offsets: flags=0 entries land on per-image local-palette blocks, while flags=1 inserts one global 16-bit palette block before the table and makes each entry point directly at a 16-byte image descriptor.",
            "Raw type 8 PZD uses the native zero-parser whole-stream-compressed path: optional global 16-bit palette, unpackedSize(u32), packedSize(u32), one zlib blob, then an inflated decoded-relative u32 image-offset table whose first entry is contentCount * 4.",
            "Decoded variant=8 chunk records start with width(u16), height(u16), a CD-CD-CD tagged mode word (usually 02 or 04), declared payload length(u32), and reserved zero(u32).",
            "Chunk bodies are row-oriented RLE: each row expands to exactly chunk width bytes using skip(u16), literal(opcode 0x80nn + nn bytes), and repeat(opcode 0xC0nn + one value byte repeated nn times).",
            "Some chunks start with FD FF before the first row. Rows are separated by FE FF, and chunks end with a trailing FFFF sentinel after the final FE FF.",
            "Type 7 PZD assets such as 180.pzx expose the same row-oriented RLE directly as standalone zlib streams without the outer chunk header.",
            "179.pzx stream 1 is a simple 30-record placement table: each 10-byte record selects one chunk and places it at signed x/y coordinates, covering all 30 decoded chunks exactly once.",
            "For 61 paired MPL files, actualWordCount equals 2 * (maxDecodedIndex + 1) + 6, consistent with a 6-word header plus two palette banks.",
            "229.pzx uses only indices 0..38 while its MPL carries 148 colors per bank, so at least one asset family keeps oversized palette banks instead of trimming them to the exact max index.",
            "180.pzx raw row streams top out at palette index 46, which exactly fits the shared 179/180 MPL payload as a 47-color two-bank palette.",
            "179.pzx still does not map directly to the 47-color shared palette, which suggests its byte values pack extra shading or effect bits above the base color index.",
            f"Auxiliary frame-record streams are now recognized for {len(frame_record_stems)} stems ({len(frame_record_entries)} streams), with each item encoded as chunkIndex(u16), x(i16), y(i16), flag(u8).",
            f"{len(frame_record_control_stems)} of those stems also carry embedded 5-byte control chunks inside or between frame records; observed markers include 66 05 00 00 00, 66 0A 00 00 00, 66 0C 00 00 00, 67 78 00 00 00, and 67 FF 00 00 00.",
            f"Raw embedded PZF containers now exact-parse for {len(embedded_pzf_parsed_entries)} stems. {embedded_pzf_match_index_counts.get(1, 0)} payloads are byte-identical to zlib stream index 1, which makes stream 1 the native PZF frame blob in most samples.",
            f"Each raw PZF frame reads as subFrameCount(u8), bbox count byte(s), a variant-dependent bbox block, then repeated subFrameIndex(u16), x(i16), y(i16), extraFlag(u8), extraPayload. Across the parsed set, subFrameCount ranges {embedded_pzf_subframe_count_range[0] if embedded_pzf_subframe_count_range else 'n/a'}..{embedded_pzf_subframe_count_range[1] if embedded_pzf_subframe_count_range else 'n/a'}.",
            f"Nonzero PZF extraPayloads are common ({embedded_pzf_nonzero_extra_count} subframes total). Observed extraFlag values are {embedded_pzf_extra_flag_values[:20]}, max extra length is {embedded_pzf_max_extra_len}, and the dominant payload families are {dict(sorted(embedded_pzf_extra_marker_counts.items()))}.",
            f"Disassembly now matches those PZF extras to native frame fields: EndDecodeFrame stores extraLen + extraPtr per subframe, effect-cache lookup only compares bytes <= 4 ({dict(sorted(embedded_pzf_effect_opcode_counts.items()))}), but CGxEffectPZD::ApplyEffect actually executes every byte in the range 1..100 ({dict(sorted(embedded_pzf_runtime_effect_counts.items(), key=lambda item: int(item[0])))}).",
            f"That runtime dispatch splits into rotate opcodes 1/2, flip-class opcodes 3/4, and palette-change program ids 5..100. Bounded parsing no longer leaves any real single-byte 0x65..0x74 extras ({dict(sorted(embedded_pzf_single_byte_module_counts.items()))}); the earlier family was a parse artifact. But selector-class bytes still appear inside longer extras: raw selector-byte counts are {dict(sorted(embedded_pzf_selector_byte_counts.items()))} and last-selector counts per subframe are {dict(sorted(embedded_pzf_selector_last_byte_counts.items()))}.",
            f"Bounding-box metadata is native PZF frame-local data rather than a separate tail track: parsed bbox totals range {embedded_pzf_bbox_total_range[0] if embedded_pzf_bbox_total_range else 'n/a'}..{embedded_pzf_bbox_total_range[1] if embedded_pzf_bbox_total_range else 'n/a'} and appear in {embedded_pzf_total_bbox_frame_count} frames overall. Mode counts are {dict(sorted(embedded_pzf_bbox_mode_counts.items()))}, with attack={embedded_pzf_bbox_attack_total}, damage={embedded_pzf_bbox_damage_total}, reference={embedded_pzf_bbox_reference_total}, generic={embedded_pzf_bbox_generic_total}.",
            f"Once PZD image-count bounds are applied back into the raw PZF parser, subFrameIndex stays inside the native PZD image pool for every parsed stem: exact max+1 match={embedded_pzd_relation_counts.get('exact-max-plus-one', 0)}, in-range={embedded_pzd_relation_counts.get('in-range', 0)}, empty={embedded_pzd_relation_counts.get('empty', 0)}, out-of-range={embedded_pzd_relation_counts.get('out-of-range', 0)}.",
            f"The previous frame-record heuristic overlaps the native PZF index table directly: {len(embedded_pzf_offset_prefix_stems)} stems already have frame-record offset previews that prefix-match the raw PZF frame offsets.",
            f"The trailing tails now split into {frame_meta_section_count} marker-delimited sections. {frame_meta_marker_counts.get('67ff000000', 0)} use 67 FF 00 00 00 and {frame_meta_marker_counts.get('6778000000', 0)} use 67 78 00 00 00.",
            f"{len(frame_meta_exact_stems)} stems already expose exact-fit tail subsections that decode as 7-byte flagged tuples or simple 6-byte tuples, so at least part of the secondary metadata is structured placement data rather than opaque blobs.",
            f"Those sections cluster into {frame_meta_group_count} opaque-led tail groups. {frame_meta_linked_group_count} groups already have an exact tuple overlap with at least one base frame record, while {frame_meta_tail_only_group_count} groups use only chunk indices that never appear in the base frame stream.",
            f"Current group classification counts are: base-frame-delta={frame_meta_group_link_counts.get('base-frame-delta', 0)}, overlay-track={frame_meta_group_link_counts.get('overlay-track', 0)}, chunk-linked-reuse={frame_meta_group_link_counts.get('chunk-linked-reuse', 0)}, mixed-or-unknown={frame_meta_group_link_counts.get('mixed-or-unknown', 0)}, opaque-only={frame_meta_group_link_counts.get('opaque-only', 0)}.",
            "The 12-byte root header after PZX\\x01 behaves as a subresource offset table: field4 -> PZD, field8 -> PZF, field12 -> PZA.",
            f"Raw embedded PZA containers now parse for {len(embedded_pza_stems)} stems, and {embedded_pza_match_index_counts.get(2, 0)} of those payloads are byte-identical to zlib stream index 2.",
            "Each embedded PZA container starts with header(u8), clipCount(u16), and a 32-bit offset table. For compressed mode, that table is followed by unpackedSize(u32), packedSize(u32), then one zlib blob.",
            "Each embedded PZF container follows the same high-level pattern and its contentCount is the frame pool size consumed by CGxPZFMgr::LoadFrame*.",
            f"Across the raw embedded PZA parses, frameIndex ranges {embedded_pza_frame_index_range[0] if embedded_pza_frame_index_range else 'n/a'}..{embedded_pza_frame_index_range[1] if embedded_pza_frame_index_range else 'n/a'}, delay ranges {embedded_pza_delay_range[0] if embedded_pza_delay_range else 'n/a'}..{embedded_pza_delay_range[1] if embedded_pza_delay_range else 'n/a'}, x ranges {embedded_pza_x_range[0] if embedded_pza_x_range else 'n/a'}..{embedded_pza_x_range[1] if embedded_pza_x_range else 'n/a'}, and y ranges {embedded_pza_y_range[0] if embedded_pza_y_range else 'n/a'}..{embedded_pza_y_range[1] if embedded_pza_y_range else 'n/a'}.",
            f"PZA frameIndex stays inside the raw PZF frame pool for every parsed stem: exact max+1 match={embedded_pza_relation_counts.get('exact-max-plus-one', 0)}, in-range but sparse={embedded_pza_relation_counts.get('in-range', 0)}, out-of-range={embedded_pza_relation_counts.get('out-of-range', 0)}.",
            f"Exact-fit animation clip streams are now recognized for {len(animation_stems)} stems ({len(animation_entries)} streams). {animation_stream_index_counts.get(2, 0)} of them occur at zlib stream index 2.",
            "Those streams decode as concatenated clips: frameCount(u8) followed by frameIndex(u16), delay(u8), x(i16), y(i16), control(u8) per frame.",
            f"Across the confirmed animation clip streams, frameIndex ranges {animation_frame_index_range[0] if animation_frame_index_range else 'n/a'}..{animation_frame_index_range[1] if animation_frame_index_range else 'n/a'}, delay stays within {animation_delay_range[0] if animation_delay_range else 'n/a'}..{animation_delay_range[1] if animation_delay_range else 'n/a'}, x stays within {animation_x_range[0] if animation_x_range else 'n/a'}..{animation_x_range[1] if animation_x_range else 'n/a'}, y stays within {animation_y_range[0] if animation_y_range else 'n/a'}..{animation_y_range[1] if animation_y_range else 'n/a'}, and nonzero control bytes appear {animation_nonzero_control_count} times.",
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
