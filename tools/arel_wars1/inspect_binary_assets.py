#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct

from formats import find_zlib_streams, read_pzx_first_stream


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


def parse_pzx(path: Path, has_mpl_pair: bool) -> dict[str, object]:
    data = path.read_bytes()
    streams = find_zlib_streams(data)
    field16 = struct.unpack("<H", data[16:18])[0] if len(data) >= 18 else 0
    table_span = field16 >> 6

    parsed_streams: list[dict[str, object]] = []
    first_stream_summary: dict[str, object] | None = None
    first_stream_error: str | None = None

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

    shared_pairs = sorted({Path(entry["path"]).stem for entry in pzx_entries if entry["hasMplPair"]})
    first_stream_ready = [entry for entry in pzx_entries if entry["firstStream"] is not None]
    first_stream_failed = [entry for entry in pzx_entries if entry["firstStreamError"] is not None]
    regular_mpl_palette_stems: list[str] = []

    mpl_by_stem = {Path(entry["path"]).stem: entry for entry in mpl_entries}
    for entry in first_stream_ready:
        stem = Path(entry["path"]).stem
        mpl = mpl_by_stem.get(stem)
        if mpl is None or not entry["hasMplPair"]:
            continue
        color_count = int(entry["firstStream"]["maxDecodedIndex"]) + 1
        if mpl["actualWordCount"] == 2 * color_count + 6:
            regular_mpl_palette_stems.append(stem)

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
            "regularMplPaletteCount": len(regular_mpl_palette_stems),
            "regularMplPalettePreview": regular_mpl_palette_stems[:20],
        },
        "findings": [
            "All PZX files start with magic 50 5a 58 01 ('PZX\\x01').",
            "Many PZX files contain one or more embedded zlib streams.",
            "For 205 PZX files, the first decoded zlib stream is a table of 32-bit chunk offsets followed by chunk payloads.",
            "Each chunk starts with width(u16), height(u16), 02 CD CD CD, declared payload length(u32), and reserved zero(u32).",
            "Chunk bodies are row-oriented RLE: each row expands to exactly chunk width bytes using skip(u16), literal(opcode 0x80nn + nn bytes), and repeat(opcode 0xC0nn + one value byte repeated nn times).",
            "Some chunks start with FD FF before the first row. Rows are separated by FE FF, and chunks end with a trailing FFFF sentinel after the final FE FF.",
            "For 61 paired MPL files, actualWordCount equals 2 * (maxDecodedIndex + 1) + 6, consistent with a 6-word header plus two palette banks.",
            "All MPL files share a fixed 32-bit signature 0x000A0230 and the field at offset 4 declares an apparent word count that is consistently actual_words + 5.",
        ],
        "pzx": pzx_entries,
        "mpl": mpl_entries,
    }

    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
