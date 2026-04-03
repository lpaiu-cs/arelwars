#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPT_ROOT = REPO_ROOT / "recovery" / "arel_wars2" / "decoded" / "zt1" / "assets" / "eng" / "script"
DEFAULT_TABLE_ROOT = REPO_ROOT / "recovery" / "arel_wars2" / "decoded" / "zt1" / "assets" / "table"
DEFAULT_OUTPUT = REPO_ROOT / "recovery" / "arel_wars2" / "aw2_bootstrap_stage_candidates.json"


@dataclass
class GxlTable:
    row_size: int
    row_count: int
    rows: list[bytes]


def read_gxl_table(path: Path) -> GxlTable:
    data = path.read_bytes()
    if data[:4] != b"GXL\x01":
        raise ValueError(f"unexpected header: {path}")
    row_size = struct.unpack_from("<H", data, 4)[0]
    extra_size = struct.unpack_from("<H", data, 6)[0]
    row_count = struct.unpack_from("<H", data, 8)[0]
    header_size = 10 + extra_size
    payload = data[header_size:]
    rows = [
        payload[index * row_size:(index + 1) * row_size]
        for index in range(row_count)
    ]
    return GxlTable(row_size=row_size, row_count=row_count, rows=rows)


def read_lines(path: Path) -> list[str]:
    return path.read_text("utf-8", errors="replace").splitlines()


def decode_title_from_ai_row(row: bytes) -> str:
    end = 2
    while end + 1 < len(row):
        if row[end] == 0 and row[end + 1] == 0:
            break
        end += 1
    raw = row[2:end]
    return raw.decode("cp949", errors="replace")


def parse_script_events(path: Path) -> list[dict]:
    return json.loads(path.read_text("utf-8"))


def first_speech(events: list[dict]) -> dict | None:
    return next((event for event in events if event.get("kind") == "speech"), None)


def route_label(route_slot: int) -> str:
    return "primary" if route_slot == 0 else "alternate" if route_slot == 1 else f"slot-{route_slot}"


def build_candidates(script_root: Path, table_root: Path) -> dict:
    xls_ai = read_gxl_table(table_root / "XlsAi.zt1.bin")
    xls_map = read_gxl_table(table_root / "XlsMap.zt1.bin")
    xls_ai_strings = read_lines(table_root / "XlsAi.zt1.strings.txt")[1:]

    numeric_scripts = sorted(
        path for path in script_root.glob("*.zt1.events.json")
        if re.fullmatch(r"\d{3}\.zt1\.events\.json", path.name)
    )

    candidates: list[dict] = []
    for script_path in numeric_scripts:
        stem = script_path.name.split(".")[0]
        stage_number = int(stem)
        family_id = stage_number // 10
        route_slot = stage_number % 10
        ai_index = family_id * 2 + route_slot

        events = parse_script_events(script_path)
        opening = first_speech(events)
        ai_row = xls_ai.rows[ai_index] if ai_index < len(xls_ai.rows) else None
        map_row = xls_map.rows[ai_index] if ai_index < len(xls_map.rows) else None

        if ai_row is None:
            continue

        title = decode_title_from_ai_row(ai_row)
        title_string = xls_ai_strings[ai_index] if ai_index < len(xls_ai_strings) else None
        map_family = struct.unpack_from("<H", map_row, 0)[0] if map_row else None
        preferred_map_index = struct.unpack_from("<H", map_row, 2)[0] if map_row else None
        secondary_map_index = struct.unpack_from("<H", map_row, 4)[0] if map_row else None
        map_opcode = map_row[6] if map_row and len(map_row) > 6 else None

        candidates.append(
            {
                "scriptStem": stem,
                "familyIdCandidate": family_id,
                "routeSlotCandidate": route_slot,
                "routeLabelCandidate": route_label(route_slot),
                "aiIndexCandidate": ai_index,
                "preferredMapIndexCandidate": preferred_map_index,
                "secondaryMapWord": secondary_map_index,
                "mapFamilyWord": map_family,
                "mapOpcodeByte": map_opcode,
                "stageTitleCandidate": title,
                "titleDecodedFromRow": title,
                "titleLineFromStringsTxt": title_string,
                "confidence": "structural-candidate" if route_slot in (0, 1) and map_row is not None else "weak-candidate",
                "openingSpeaker": opening.get("speaker") if opening else None,
                "openingText": opening.get("text") if opening else None,
                "scriptPath": str(script_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            }
        )

    return {
        "specVersion": "aw2-bootstrap-stage-candidates-v1",
        "scriptRoot": str(script_root),
        "tableRoot": str(table_root),
        "candidateCount": len(candidates),
        "xslAiRowSize": xls_ai.row_size,
        "xslMapRowSize": xls_map.row_size,
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export AW2 bootstrap stage candidate bindings.")
    parser.add_argument("--script-root", type=Path, default=DEFAULT_SCRIPT_ROOT)
    parser.add_argument("--table-root", type=Path, default=DEFAULT_TABLE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_candidates(args.script_root, args.table_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
