#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan AW1 decoded GXL tables for columns that reuse XlsAi runtime field value sets"
    )
    parser.add_argument(
        "--gxl-report",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/gxl_table_report.json",
    )
    parser.add_argument(
        "--map-binding-report",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.map_binding_candidates.json",
    )
    parser.add_argument(
        "--recovery-root",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the reuse scan JSON",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalized_sets(binding_report: dict[str, Any]) -> dict[str, set[int]]:
    fields = list(binding_report["stageRuntimeFieldsByAiIndex"].values())
    return {
        "tierCandidate": {int(item["tierCandidate"]) for item in fields},
        "variantCandidate": {int(item["variantCandidate"]) for item in fields},
        "regionCandidate": {int(item["regionCandidate"]) for item in fields},
        "storyFlagCandidate": {int(item["storyFlagCandidate"]) for item in fields},
    }


def score_column(values: list[int], targets: set[int]) -> dict[str, Any]:
    uniq = set(values)
    overlap = uniq & targets
    if not overlap:
        return {
            "score": 0.0,
            "uniqueValues": sorted(uniq),
            "targetOverlap": [],
            "targetCoverage": 0.0,
            "purity": 0.0,
        }
    target_coverage = len(overlap) / len(targets)
    purity = len(overlap) / len(uniq)
    score = round((target_coverage * 0.7) + (purity * 0.3), 4)
    return {
        "score": score,
        "uniqueValues": sorted(uniq),
        "targetOverlap": sorted(overlap),
        "targetCoverage": round(target_coverage, 4),
        "purity": round(purity, 4),
    }


def main() -> None:
    args = parse_args()
    gxl_report = read_json(args.gxl_report.resolve())
    binding_report = read_json(args.map_binding_report.resolve())
    recovery_root = args.recovery_root.resolve()
    target_sets = normalized_sets(binding_report)

    table_results: list[dict[str, Any]] = []
    best_hits: list[dict[str, Any]] = []

    for rec in gxl_report["tables"]:
        if rec["locale"] != "en":
            continue
        if rec["path"].endswith("XlsAi.zt1"):
            continue
        decoded_path = recovery_root / rec["decodedPath"]
        blob = decoded_path.read_bytes()
        row_size = int(rec["rowSizeGuess"])
        row_count = int(rec["rowCountGuess"])
        header_size = int(rec["headerSize"])
        payload = blob[header_size : header_size + row_size * row_count]
        rows = [payload[index * row_size : (index + 1) * row_size] for index in range(row_count)]

        column_hits: list[dict[str, Any]] = []
        for offset in range(row_size):
            values = [row[offset] for row in rows]
            for field_name, targets in target_sets.items():
                hit = score_column(values, targets)
                if hit["score"] < 0.45:
                    continue
                entry = {
                    "offset": offset,
                    "fieldCandidate": field_name,
                    **hit,
                    "topCounts": dict(Counter(values).most_common(10)),
                }
                column_hits.append(entry)
                best_hits.append(
                    {
                        "table": rec["path"],
                        "rowSize": row_size,
                        "rowCount": row_count,
                        **entry,
                    }
                )

        if column_hits:
            table_results.append(
                {
                    "table": rec["path"],
                    "rowSize": row_size,
                    "rowCount": row_count,
                    "hits": sorted(column_hits, key=lambda item: (-item["score"], item["offset"])),
                }
            )

    best_hits.sort(key=lambda item: (-item["score"], item["table"], item["offset"]))
    report = {
        "targetSets": {key: sorted(values) for key, values in target_sets.items()},
        "tableHitCount": len(table_results),
        "tables": table_results,
        "bestHits": best_hits[:120],
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
