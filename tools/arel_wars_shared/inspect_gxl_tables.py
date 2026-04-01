#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct


STRING_RE = re.compile(rb"[ -~]{3,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect decoded GXL table payloads from catalog.json")
    parser.add_argument("--catalog", type=Path, required=True, help="Path to recovery catalog.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the report JSON")
    return parser.parse_args()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_ascii_strings(blob: bytes, limit: int = 12) -> list[str]:
    values: list[str] = []
    for match in STRING_RE.finditer(blob):
        values.append(match.group().decode("ascii", errors="ignore"))
        if len(values) >= limit:
            break
    return values


def inspect_gxl_blob(data: bytes) -> dict[str, object] | None:
    if len(data) < 10 or not data.startswith(b"GXL\x01"):
        return None

    _magic, row_count, header_extra_size, row_size = struct.unpack("<4sHHH", data[:10])
    header_size = 10 + header_extra_size
    if header_size > len(data):
        return {
            "rowCount": row_count,
            "headerExtraSize": header_extra_size,
            "rowSize": row_size,
            "headerSize": header_size,
            "valid": False,
            "error": "header exceeds file size",
        }

    payload_size = len(data) - header_size
    expected_payload_size = row_count * row_size
    row_data = data[header_size:]
    sample_rows: list[dict[str, object]] = []
    for index in range(min(row_count, 3)):
        start = index * row_size
        end = start + row_size
        if end > len(row_data):
            break
        row = row_data[start:end]
        sample_rows.append(
            {
                "index": index,
                "hex": row.hex(),
                "asciiStrings": extract_ascii_strings(row, limit=6),
            }
        )

    return {
        "rowCount": row_count,
        "headerExtraSize": header_extra_size,
        "rowSize": row_size,
        "headerSize": header_size,
        "payloadSize": payload_size,
        "expectedPayloadSize": expected_payload_size,
        "payloadMatchesRowLayout": payload_size == expected_payload_size,
        "headerHex": data[:header_size].hex(),
        "headerAsciiStrings": extract_ascii_strings(data[10:header_size], limit=16),
        "sampleRows": sample_rows,
        "valid": True,
    }


def main() -> None:
    args = parse_args()
    catalog_path = args.catalog.resolve()
    catalog = read_json(catalog_path)
    if not isinstance(catalog, dict):
        raise ValueError("catalog must be a JSON object")

    catalog_root = catalog_path.parent
    entries = catalog.get("zt1Entries", [])
    if not isinstance(entries, list):
        raise ValueError("catalog is missing zt1Entries")

    reports: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        decoded_path = entry.get("decodedPath")
        if not isinstance(decoded_path, str):
            continue
        full_path = catalog_root / decoded_path
        if not full_path.exists():
            continue
        data = full_path.read_bytes()
        inspected = inspect_gxl_blob(data)
        if inspected is None:
            continue
        reports.append(
            {
                "path": entry.get("path"),
                "kind": entry.get("kind"),
                "locale": entry.get("locale"),
                "decodedPath": decoded_path,
                **inspected,
            }
        )

    summary = {
        "tableCount": len(reports),
        "validCount": sum(1 for item in reports if item.get("valid")),
        "payloadLayoutMatchCount": sum(
            1 for item in reports if item.get("payloadMatchesRowLayout") is True
        ),
        "headerExtraSizes": sorted(
            {int(item["headerExtraSize"]) for item in reports if isinstance(item.get("headerExtraSize"), int)}
        ),
        "rowSizes": sorted({int(item["rowSize"]) for item in reports if isinstance(item.get("rowSize"), int)}),
    }

    write_json(
        args.output.resolve(),
        {
            "summary": summary,
            "tables": reports,
        },
    )


if __name__ == "__main__":
    main()
