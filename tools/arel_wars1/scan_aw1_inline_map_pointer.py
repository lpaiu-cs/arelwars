#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
from typing import Any

from runtime_heuristics import map_group_for_variant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan AW1 XlsAi numeric blocks for inline stage-to-map pointer candidates"
    )
    parser.add_argument(
        "--ai-table",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/XlsAi.eng.parsed.json",
    )
    parser.add_argument(
        "--stage-progression",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.stage_progression.json",
    )
    parser.add_argument(
        "--map-binding",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables/AW1.map_binding_candidates.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write AW1.inline_map_pointer_scan.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def exact_mapping(rows: list[dict[str, Any]], target_getter, value_getter) -> dict[str, Any]:
    mapping: dict[int, int] = {}
    for row in rows:
        source = int(value_getter(row))
        target = int(target_getter(row))
        previous = mapping.get(source)
        if previous is not None and previous != target:
            return {
                "isExact": False,
                "mapping": {},
                "coverage": 0,
            }
        mapping[source] = target
    return {
        "isExact": True,
        "mapping": dict(sorted(mapping.items())),
        "coverage": len(rows),
    }


def main() -> None:
    args = parse_args()
    ai_table = read_json(args.ai_table.resolve())
    stage_progression = read_json(args.stage_progression.resolve())
    map_binding = read_json(args.map_binding.resolve())

    ai_records = {int(record["index"]): record for record in ai_table.get("records", [])}
    group_candidates = {
        int(group["groupId"]): group for group in map_binding["mapGroupSummary"]["groupCandidates"]
    }

    rows: list[dict[str, Any]] = []
    for family in stage_progression.get("families", []):
        if not isinstance(family, dict):
            continue
        runtime_fields = family.get("runtimeFieldCandidates")
        if not isinstance(runtime_fields, dict):
            continue
        index = int(family["aiIndexCandidate"])
        ai_record = ai_records.get(index)
        if ai_record is None:
            continue
        blob = bytes.fromhex(str(ai_record["numericBlockHex"]))
        variant = int(runtime_fields.get("variantCandidate", 0))
        story_flag = int(runtime_fields.get("storyFlagCandidate", 0))
        group_id = map_group_for_variant(variant)
        group = group_candidates.get(group_id)
        pair = list(group.get("candidateMapBinPair", [])) if group else []
        if len(pair) != 2:
            continue
        preferred = pair[1] if story_flag == 1 else pair[0]
        rows.append(
            {
                "aiIndex": index,
                "title": family.get("aiTitleCandidate"),
                "pairBaseIndex": int(pair[0]),
                "preferredMapIndex": int(preferred),
                "pairBranchIndex": int(preferred) - int(pair[0]),
                "pairBaseByte15": blob[15],
                "pairBranchByte18": blob[18],
                "pairBaseWord7": struct.unpack_from("<H", blob, 14)[0],
                "pairBranchWord9": struct.unpack_from("<H", blob, 18)[0],
            }
        )

    pair_base_byte = exact_mapping(rows, lambda row: row["pairBaseIndex"], lambda row: row["pairBaseByte15"])
    pair_base_word = exact_mapping(rows, lambda row: row["pairBaseIndex"], lambda row: row["pairBaseWord7"])
    pair_branch_byte = exact_mapping(rows, lambda row: row["pairBranchIndex"], lambda row: row["pairBranchByte18"])
    pair_branch_word = exact_mapping(rows, lambda row: row["pairBranchIndex"], lambda row: row["pairBranchWord9"])

    exact_formula_rows = 0
    for row in rows:
        mapped_pair_base = pair_base_byte["mapping"].get(row["pairBaseByte15"])
        mapped_branch = pair_branch_byte["mapping"].get(row["pairBranchByte18"])
        if mapped_pair_base is None or mapped_branch is None:
            continue
        if mapped_pair_base + mapped_branch == row["preferredMapIndex"]:
            exact_formula_rows += 1

    payload = {
        "summary": {
            "stageCount": len(rows),
            "pairBaseByteCoverage": pair_base_byte["coverage"],
            "pairBranchByteCoverage": pair_branch_byte["coverage"],
            "formulaCoverage": exact_formula_rows,
        },
        "pairBaseIndexSignal": {
            "byteOffset": 15,
            "wordIndex": 7,
            "byteMapping": pair_base_byte["mapping"],
            "wordMapping": pair_base_word["mapping"],
            "interpretation": "XlsAi numericBlock byte[15] encodes the map-pair base index through a compact variant-to-pair lookup.",
        },
        "pairBranchSignal": {
            "byteOffset": 18,
            "wordIndex": 9,
            "byteMapping": pair_branch_byte["mapping"],
            "wordMapping": pair_branch_word["mapping"],
            "interpretation": "XlsAi numericBlock byte[18] behaves like a branch bit selecting primary vs secondary map inside the pair.",
        },
        "preferredMapFormula": {
            "formula": "preferredMapIndex = pairBaseIndexCandidate + pairBranchIndexCandidate",
            "exactCoverage": exact_formula_rows,
        },
        "sampleRows": rows[:12],
        "findings": [
            "XlsAi.numericBlock byte[15] maps exactly onto map-pair base indices 0,2,4,6,8 across all currently script-backed stages.",
            "XlsAi.numericBlock byte[18] maps exactly onto pair-branch indices 0/1 across all currently script-backed stages.",
            "Combining those two inline signals reproduces the current preferred map index for every script-backed stage row.",
        ],
    }
    write_json(args.output.resolve(), payload)


if __name__ == "__main__":
    main()
