#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct


STRING_RE = re.compile(rb"[ -~]{3,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump GXL rows from a decoded .zt1.bin payload")
    parser.add_argument("--input", type=Path, required=True, help="Path to decoded GXL .bin file")
    parser.add_argument("--output", type=Path, required=True, help="Path to write JSON row dump")
    parser.add_argument("--max-rows", type=int, default=128, help="Maximum number of rows to dump")
    return parser.parse_args()


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


def u16_words(blob: bytes) -> list[int]:
    end = len(blob) - (len(blob) % 2)
    return [struct.unpack("<H", blob[index : index + 2])[0] for index in range(0, end, 2)]


def i16_words(blob: bytes) -> list[int]:
    end = len(blob) - (len(blob) % 2)
    return [struct.unpack("<h", blob[index : index + 2])[0] for index in range(0, end, 2)]


def u32_words(blob: bytes) -> list[int]:
    end = len(blob) - (len(blob) % 4)
    return [struct.unpack("<I", blob[index : index + 4])[0] for index in range(0, end, 4)]


def main() -> None:
    args = parse_args()
    data = args.input.resolve().read_bytes()
    if len(data) < 10 or not data.startswith(b"GXL\x01"):
        raise ValueError("input is not a decoded GXL payload")

    field1 = struct.unpack("<H", data[4:6])[0]
    header_extra_size = struct.unpack("<H", data[6:8])[0]
    field3 = struct.unpack("<H", data[8:10])[0]
    row_size = field1
    row_count = field3
    header_size = 10 + header_extra_size
    payload = data[header_size:]

    rows: list[dict[str, object]] = []
    for index in range(min(row_count, args.max_rows)):
        start = index * row_size
        end = start + row_size
        row = payload[start:end]
        if len(row) != row_size:
            break
        rows.append(
            {
                "index": index,
                "hex": row.hex(),
                "u8": list(row),
                "u16le": u16_words(row),
                "i16le": i16_words(row),
                "u32le": u32_words(row),
                "asciiStrings": extract_ascii_strings(row, limit=8),
            }
        )

    payload_ascii = extract_ascii_strings(payload, limit=64)
    report = {
        "path": str(args.input.resolve()),
        "field1": field1,
        "headerExtraSize": header_extra_size,
        "field3": field3,
        "rowSizeGuess": row_size,
        "rowCountGuess": row_count,
        "headerHex": data[:header_size].hex(),
        "headerAsciiStrings": extract_ascii_strings(data[10:header_size], limit=32),
        "payloadAsciiStrings": payload_ascii,
        "rows": rows,
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
