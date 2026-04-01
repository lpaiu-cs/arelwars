#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys


TOOLS_ROOT = Path(__file__).resolve().parents[1] / "arel_wars1"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from formats import find_zlib_streams, read_ptc, read_pzx_first_stream, read_pzx_row_stream  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect opaque AW2 binary assets")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Path to write JSON report")
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_row_stream(decoded: bytes) -> dict[str, object] | None:
    try:
        row_stream = read_pzx_row_stream(decoded)
    except ValueError:
        return None
    if row_stream is None:
        return None
    return {
        "width": row_stream.width,
        "height": row_stream.height,
        "widthRange": list(row_stream.width_range),
        "decodedPixelTotal": row_stream.decoded_pixel_count,
        "maxDecodedIndex": max(max(row.decoded) for row in row_stream.rows if row.decoded),
        "headHex": decoded[:32].hex(),
    }


def parse_aw2_pzx(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    streams = find_zlib_streams(data)
    field16 = struct.unpack("<H", data[16:18])[0] if len(data) >= 18 else 0
    table_span = field16 >> 6
    first_stream = read_pzx_first_stream(streams[0].decoded, table_span) if streams else None
    row_streams = [
        {"index": index, **summary}
        for index, hit in enumerate(streams[:16])
        for summary in [summarize_row_stream(hit.decoded)]
        if summary is not None
    ]
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
        },
        "zlibStreamCount": len(streams),
        "firstStreamChunkTable": (
            {
                "chunkCount": len(first_stream.chunks),
                "tableSpan": first_stream.table_span,
                "maxDecodedIndex": max(max(row.decoded) for chunk in first_stream.chunks for row in chunk.rows),
            }
            if first_stream is not None
            else None
        ),
        "rowStreams": row_streams[:12],
    }


def summarize_be_offset_table(data: bytes, stop: int) -> dict[str, object]:
    values = [struct.unpack(">I", data[index : index + 4])[0] for index in range(8, stop, 4) if index + 4 <= stop]
    good: list[int] = []
    prev = -1
    for value in values:
        if value < prev or value > stop:
            break
        good.append(value)
        prev = value
    diffs = [later - earlier for earlier, later in zip(good, good[1:])]
    diff_counts = Counter(diffs)
    packed_values = values[len(good) :]
    packed_refs = [(value >> 24, value & 0xFFFFFF) for value in packed_values]
    group_counts = Counter(group for group, _offset in packed_refs)
    group_ranges: dict[int, list[int]] = {}
    for group in sorted(group_counts):
        offsets = [offset for current_group, offset in packed_refs if current_group == group]
        if offsets:
            group_ranges[group] = [min(offsets), max(offsets)]
    common_diff = diff_counts.most_common(1)[0][0] if diff_counts else None
    return {
        "entryCount": len(good),
        "entriesPreview": good[:24],
        "tailPreview": good[-12:],
        "diffCounts": dict(sorted(diff_counts.items())),
        "commonDiff": common_diff,
        "candidateBlockCount": len(good) + 1 if good else 0,
        "packedRefCount": len(packed_refs),
        "packedRefPreview": [
            {
                "group": group,
                "offset": offset,
            }
            for group, offset in packed_refs[:24]
        ],
        "packedRefGroupCounts": dict(sorted(group_counts.items())),
        "packedRefGroupRanges": {str(group): value_range for group, value_range in group_ranges.items()},
    }


def summarize_pzf_meta_sections(decoded: bytes) -> dict[str, object]:
    marker = bytes.fromhex("67ff000000")
    offsets: list[int] = []
    start = 0
    while True:
        found = decoded.find(marker, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + 1

    prefix_len = offsets[0] if offsets else len(decoded)
    section_lengths = []
    lead_byte_histogram = Counter()
    lead_word_histogram = Counter()
    section_prototypes = []
    signature_counts = Counter()
    signature_samples: dict[tuple[str | None, int], bytes] = {}
    layout_histogram = Counter()
    for index, offset in enumerate(offsets):
        next_offset = offsets[index + 1] if index + 1 < len(offsets) else len(decoded)
        payload = decoded[offset + len(marker) : next_offset]
        section_lengths.append(len(payload))
        if payload:
            lead_byte_histogram[payload[0]] += 1
            if len(payload) >= 2:
                lead_word_histogram[payload[:2].hex()] += 1
            if len(section_prototypes) < 16:
                section_prototypes.append(
                    {
                        "payloadLen": len(payload),
                        "leadByte": payload[0],
                        "leadWordHex": payload[:2].hex() if len(payload) >= 2 else None,
                        "payloadHex": payload[:32].hex(),
                    }
                )
            signature = (payload[:2].hex() if len(payload) >= 2 else None, len(payload))
            signature_counts[signature] += 1
            signature_samples.setdefault(signature, payload)
            layout_histogram[describe_pzf_section_payload(payload)["layoutKind"]] += 1
    histogram = Counter(section_lengths)
    return {
        "markerCounts": {"67ff000000": len(offsets)},
        "firstMarkerOffset": offsets[0] if offsets else None,
        "prefixLen": prefix_len,
        "sectionCount": len(section_lengths),
        "sectionLengthHistogram": dict(sorted(histogram.items())),
        "sectionLengthPreview": section_lengths[:24],
        "leadByteHistogram": {str(key): value for key, value in sorted(lead_byte_histogram.items())},
        "leadWordHistogram": dict(sorted(lead_word_histogram.items())),
        "layoutHistogram": dict(sorted(layout_histogram.items())),
        "signatureHistogram": {
            f"{lead_word or 'none'}:{payload_len}": count
            for (lead_word, payload_len), count in sorted(
                signature_counts.items(),
                key=lambda item: (item[0][0] or "", item[0][1]),
            )
        },
        "signaturePreview": [
            {
                "leadWordHex": lead_word,
                "payloadLen": payload_len,
                "count": count,
                "structure": describe_pzf_section_payload(signature_samples[(lead_word, payload_len)]),
            }
            for (lead_word, payload_len), count in sorted(
                signature_counts.items(),
                key=lambda item: (-item[1], item[0][0] or "", item[0][1]),
            )[:16]
        ],
        "sectionPrototypePreview": section_prototypes,
    }


def summarize_numeric_blob(blob: bytes) -> dict[str, object]:
    if not blob:
        return {"kind": "empty"}

    candidates = []
    for endian in ("<", ">"):
        for prefix_skip_bytes in (0, 1):
            for trim_suffix_bytes in (0, 1):
                sliced = blob[prefix_skip_bytes : len(blob) - trim_suffix_bytes if trim_suffix_bytes else len(blob)]
                if len(sliced) < 2 or len(sliced) % 2 != 0:
                    continue
                values = list(struct.unpack(endian + "h" * (len(sliced) // 2), sliced))
                score = (
                    sum(-512 <= value <= 512 for value in values),
                    sum(-2048 <= value <= 2048 for value in values),
                    -max(abs(value) for value in values),
                    -prefix_skip_bytes,
                    -trim_suffix_bytes,
                    1 if endian == "<" else 0,
                )
                candidates.append((score, endian, prefix_skip_bytes, trim_suffix_bytes, values))

    if candidates:
        _score, endian, prefix_skip_bytes, trim_suffix_bytes, values = max(candidates, key=lambda item: item[0])
        kind = []
        if prefix_skip_bytes:
            kind.append(f"u8-skip{prefix_skip_bytes}")
        kind.append("int16")
        if trim_suffix_bytes:
            kind.append(f"u8-tail{trim_suffix_bytes}")
        result: dict[str, object] = {
            "kind": "+".join(kind),
            "endianness": "le" if endian == "<" else "be",
            "prefixSkipBytes": prefix_skip_bytes,
            "trimSuffixBytes": trim_suffix_bytes,
            "int16Count": len(values),
            "int16Preview": values[:12],
            "int16Range": [min(values), max(values)],
        }
        if prefix_skip_bytes:
            result["prefixByteHex"] = blob[:prefix_skip_bytes].hex()
        if trim_suffix_bytes:
            result["tailByteHex"] = blob[-trim_suffix_bytes:].hex()
        return result

    return {
        "kind": "raw",
        "payloadHex": blob[:32].hex(),
    }


def describe_pzf_section_payload(payload: bytes) -> dict[str, object]:
    lead_word_hex = payload[:2].hex() if len(payload) >= 2 else None
    structure: dict[str, object] = {
        "payloadLen": len(payload),
        "leadWordHex": lead_word_hex,
        "payloadHex": payload[:32].hex(),
    }
    if len(payload) < 2:
        structure["layoutKind"] = "raw"
        return structure

    embedded_markers = []
    for index in range(2, len(payload) - 4):
        if payload[index] == 0x67 and payload[index + 2 : index + 5] == b"\x00\x00\x00":
            embedded_markers.append(
                {
                    "offset": index,
                    "markerHex": payload[index : index + 5].hex(),
                }
            )

    if embedded_markers:
        first_offset = embedded_markers[0]["offset"]
        structure["layoutKind"] = "control+nested-marker"
        structure["embeddedMarkers"] = embedded_markers[:8]
        prefix = payload[2:first_offset]
        suffix = payload[first_offset + 5 :]
        if prefix:
            structure["prefixLayout"] = summarize_numeric_blob(prefix)
        if suffix:
            structure["suffixLayout"] = summarize_numeric_blob(suffix)
        return structure

    value_layout = summarize_numeric_blob(payload[2:])
    structure["layoutKind"] = f"control+{value_layout['kind']}"
    structure["valueLayout"] = value_layout
    return structure


def summarize_pzf_anchor_boxes(decoded: bytes, stride: int | None) -> dict[str, object] | None:
    if stride is None or stride <= 0 or len(decoded) < 11:
        return None

    records: list[dict[str, int]] = []
    cursor = 0
    while cursor + 11 <= len(decoded):
        record = decoded[cursor : cursor + 11]
        family = record[0]
        group = struct.unpack("<H", record[1:3])[0]
        x = struct.unpack("<h", record[3:5])[0]
        y = struct.unpack("<h", record[5:7])[0]
        width = struct.unpack("<H", record[7:9])[0]
        height = struct.unpack("<H", record[9:11])[0]
        if not (
            family <= 8
            and group <= 512
            and -512 <= x <= 512
            and -512 <= y <= 512
            and 0 <= width <= 512
            and 0 <= height <= 512
        ):
            break
        records.append(
            {
                "familyCode": family,
                "group": group,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
            }
        )
        cursor += stride

    if len(records) < 3:
        return None

    return {
        "stride": stride,
        "recordCount": len(records),
        "familyCodes": sorted({record["familyCode"] for record in records}),
        "groupValues": sorted({record["group"] for record in records}),
        "xRange": [min(record["x"] for record in records), max(record["x"] for record in records)],
        "yRange": [min(record["y"] for record in records), max(record["y"] for record in records)],
        "widthRange": [min(record["width"] for record in records), max(record["width"] for record in records)],
        "heightRange": [min(record["height"] for record in records), max(record["height"] for record in records)],
        "preview": records[:12],
    }


def classify_pzf_variant(anchor_boxes: dict[str, object] | None, meta_sections: dict[str, object] | None) -> str:
    has_anchor_boxes = anchor_boxes is not None and int(anchor_boxes.get("recordCount", 0)) > 0
    section_count = int(meta_sections.get("sectionCount", 0)) if meta_sections is not None else 0
    if has_anchor_boxes and section_count:
        return "anchor+marker"
    if has_anchor_boxes:
        return "anchor-only"
    if section_count:
        return "marker-only"
    return "opaque"


def parse_pzd(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    streams = find_zlib_streams(data)
    row_streams = [
        {
            "offset": hit.offset,
            "consumed": hit.consumed,
            **summary,
        }
        for hit in streams[:48]
        for summary in [summarize_row_stream(hit.decoded)]
        if summary is not None
    ]
    widths = [int(item["width"]) for item in row_streams if item["width"] is not None]
    heights = [int(item["height"]) for item in row_streams]
    return {
        "path": str(path),
        "size": len(data),
        "signatureHex": data[:4].hex(),
        "signatureVersion": data[3] if len(data) >= 4 else None,
        "sha1": hashlib.sha1(data).hexdigest(),
        "zlibStreamCount": len(streams),
        "rowStreamCount": len(row_streams),
        "widthRange": [min(widths), max(widths)] if widths else None,
        "heightRange": [min(heights), max(heights)] if heights else None,
        "rowStreamsPreview": row_streams[:10],
    }


def parse_pzf(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    streams = find_zlib_streams(data)
    first_zlib_offset = streams[0].offset if streams else len(data)
    be_offset_table = summarize_be_offset_table(data, first_zlib_offset)
    meta_stream_preview = []
    meta_sections = None
    anchor_boxes = None
    if streams:
        for hit in streams[:4]:
            stream_entry = {
                "offset": hit.offset,
                "consumed": hit.consumed,
                "decodedLen": len(hit.decoded),
                "headHex": hit.decoded[:40].hex(),
                "tailHex": hit.decoded[-24:].hex(),
            }
            if not meta_sections:
                current_sections = summarize_pzf_meta_sections(hit.decoded)
                current_anchor_boxes = summarize_pzf_anchor_boxes(hit.decoded, be_offset_table["commonDiff"])
                if current_sections["sectionCount"] or current_anchor_boxes is not None:
                    meta_sections = current_sections
                    anchor_boxes = current_anchor_boxes
            meta_stream_preview.append(stream_entry)
    return {
        "path": str(path),
        "family": path.parent.name,
        "size": len(data),
        "signatureHex": data[:4].hex(),
        "field4LE": struct.unpack("<I", data[4:8])[0] if len(data) >= 8 else None,
        "field4BE": struct.unpack(">I", data[4:8])[0] if len(data) >= 8 else None,
        "firstZlibOffset": first_zlib_offset,
        "beOffsetTable": be_offset_table,
        "zlibStreamCount": len(streams),
        "metaSections": meta_sections,
        "anchorBoxes": anchor_boxes,
        "variant": classify_pzf_variant(anchor_boxes, meta_sections),
        "metaStreamPreview": meta_stream_preview,
    }


def parse_ptc_file(path: Path) -> dict[str, object]:
    ptc = read_ptc(path.read_bytes())
    if ptc is None:
        return {"path": str(path), "size": path.stat().st_size}
    fields = list(ptc.fields_u16)
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "fieldCount": len(fields),
        "angleRangeDeg": fields[:2],
        "ratioFieldsQ16": fields[10:17:2],
        "signedDeltaFields": list(ptc.fields_i16[18:22]),
        "timingFields": fields[22:25],
        "trailerHex": ptc.trailer_bytes.hex() or None,
    }


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()

    pzx_paths = sorted((assets_root / "img").glob("*.pzx")) + sorted((assets_root / "menu").glob("*.pzx"))
    pzd_paths = sorted((assets_root / "pc").glob("**/*.pzd"))
    pzf_paths = sorted((assets_root / "pc").glob("**/*.pzf"))
    mpl_paths = sorted((assets_root / "pc").glob("**/*.mpl"))
    ptc_paths = sorted((assets_root / "ptc").glob("*.ptc"))

    pzx_entries = [parse_aw2_pzx(path) for path in pzx_paths]
    pzd_entries = [parse_pzd(path) for path in pzd_paths]
    pzf_entries = [parse_pzf(path) for path in pzf_paths]
    mpl_entries = [
        {
            "path": str(path),
            "size": path.stat().st_size,
            "signatureHex": path.read_bytes()[:8].hex(),
        }
        for path in mpl_paths
    ]
    ptc_entries = [parse_ptc_file(path) for path in ptc_paths]

    pzd_row_counts = Counter(int(entry["rowStreamCount"]) for entry in pzd_entries)
    pzf_block_counts = Counter(int(entry["beOffsetTable"]["candidateBlockCount"]) for entry in pzf_entries)
    pzf_variant_counts = Counter(str(entry["variant"]) for entry in pzf_entries)
    pzf_stride_counts = Counter(
        int(entry["anchorBoxes"]["stride"])
        for entry in pzf_entries
        if entry.get("anchorBoxes") is not None and entry["anchorBoxes"].get("stride") is not None
    )
    pzf_marker_section_counts = Counter(
        int(entry["metaSections"]["sectionCount"])
        for entry in pzf_entries
        if entry.get("metaSections") is not None and entry["metaSections"].get("sectionCount") is not None
    )
    pzf_lead_word_counts = Counter()
    pzf_layout_counts = Counter()
    for entry in pzf_entries:
        meta_sections = entry.get("metaSections") or {}
        for lead_word, count in (meta_sections.get("leadWordHistogram") or {}).items():
            pzf_lead_word_counts[str(lead_word)] += int(count)
        for layout_kind, count in (meta_sections.get("layoutHistogram") or {}).items():
            pzf_layout_counts[str(layout_kind)] += int(count)
    pzx_row_ready = [entry for entry in pzx_entries if entry["rowStreams"]]
    pzx_chunk_table_ready = [entry for entry in pzx_entries if entry["firstStreamChunkTable"] is not None]

    report = {
        "summary": {
            "pzxCount": len(pzx_entries),
            "pzdCount": len(pzd_entries),
            "pzfCount": len(pzf_entries),
            "mplCount": len(mpl_entries),
            "ptcCount": len(ptc_entries),
            "pzxRowReadyCount": len(pzx_row_ready),
            "pzxChunkTableReadyCount": len(pzx_chunk_table_ready),
            "pzdRowStreamCountHistogram": dict(sorted(pzd_row_counts.items())),
            "pzfCandidateBlockHistogram": dict(sorted(pzf_block_counts.items())),
            "pzfVariantHistogram": dict(sorted(pzf_variant_counts.items())),
            "pzfAnchorStrideHistogram": dict(sorted(pzf_stride_counts.items())),
            "pzfMetaSectionHistogram": dict(sorted(pzf_marker_section_counts.items())),
            "pzfMarkerLeadWordHistogram": dict(sorted(pzf_lead_word_counts.items())),
            "pzfMarkerLayoutHistogram": dict(sorted(pzf_layout_counts.items())),
        },
        "findings": [
            "AW2 keeps ZT1 as the same zlib-wrapped text container used by AW1, and the recovered script parser works on sampled EN/KO/JA script files.",
            "AW2 PZD files start with magic 50 5A 44 02 ('PZD\\x02') and contain many embedded zlib streams whose decoded payloads are row-oriented RLE images compatible with the AW1 row-stream decoder.",
            "AW2 PZF files start with magic 50 5A 46 01 ('PZF\\x01'), carry a big-endian offset table in the plain header, and then switch to one large metadata zlib stream.",
            "The plain-header PZF table is not just monotonic offsets: after the initial big-endian offset run, later 32-bit words split cleanly into a high-byte group id plus a low-24-bit local offset, which looks like cross-group placement references.",
            "Sampled armor/head/weapon/effect PZF files expose category-specific common strides of 53, 25, 30, and 11 bytes, and those same strides decode repeated anchor-box records from the zlib stream.",
            "Decoded PZF metadata streams also carry dense 67ff000000-delimited sections, so PZF now looks like offset table + anchor boxes + timing/state markers rather than an opaque blob.",
            "Current PZF samples already separate into anchor-only, anchor+marker, and marker-only variants, so the AW2 body-part sidecar parser should branch by variant instead of assuming one universal record layout.",
            "Inside 67ff sections, the payloads already cluster into repeatable control-word families such as 0100, 0200, and 0401, and many of those payloads reduce cleanly to int16 fields plus an optional trailing byte.",
            "AW2 img/menu PZX files still use magic 'PZX\\x01', but many now decode directly as row streams instead of the AW1 chunk-offset-table first stream.",
            "Sampled AW2 MPL files under assets/pc are tiny sidecars rather than AW1-style two-bank palette blobs, so AW1 MPL logic must not be reused blindly.",
            "AW2 PTC remains structurally similar to AW1 compact parameter blocks and can already be summarized into angle, ratio, signed-delta, and timing fields.",
        ],
        "pzx": pzx_entries,
        "pzd": pzd_entries,
        "pzf": pzf_entries,
        "mpl": mpl_entries,
        "ptc": ptc_entries,
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
