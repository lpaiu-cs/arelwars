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
    return {
        "entryCount": len(good),
        "entriesPreview": good[:24],
        "tailPreview": good[-12:],
        "diffCounts": dict(sorted(diff_counts.items())),
        "candidateBlockCount": len(good) + 1 if good else 0,
    }


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
    return {
        "path": str(path),
        "size": len(data),
        "signatureHex": data[:4].hex(),
        "field4LE": struct.unpack("<I", data[4:8])[0] if len(data) >= 8 else None,
        "field4BE": struct.unpack(">I", data[4:8])[0] if len(data) >= 8 else None,
        "firstZlibOffset": first_zlib_offset,
        "beOffsetTable": summarize_be_offset_table(data, first_zlib_offset),
        "zlibStreamCount": len(streams),
        "metaStreamPreview": [
            {
                "offset": hit.offset,
                "consumed": hit.consumed,
                "decodedLen": len(hit.decoded),
                "headHex": hit.decoded[:40].hex(),
                "tailHex": hit.decoded[-24:].hex(),
            }
            for hit in streams[:4]
        ],
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
        },
        "findings": [
            "AW2 keeps ZT1 as the same zlib-wrapped text container used by AW1, and the recovered script parser works on sampled EN/KO/JA script files.",
            "AW2 PZD files start with magic 50 5A 44 02 ('PZD\\x02') and contain many embedded zlib streams whose decoded payloads are row-oriented RLE images compatible with the AW1 row-stream decoder.",
            "AW2 PZF files start with magic 50 5A 46 01 ('PZF\\x01'), carry a big-endian offset table in the plain header, and then switch to one large metadata zlib stream.",
            "Sampled armor/head/weapon PZF files expose regular big-endian block strides of 53, 25, and 30 bytes respectively, which strongly suggests PZF is the AW2 animation/state sidecar for PZD body-part sprites.",
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
