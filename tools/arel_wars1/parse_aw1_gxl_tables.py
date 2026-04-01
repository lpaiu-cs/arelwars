#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse tentative AW1 GXL gameplay tables")
    parser.add_argument(
        "--assets-root",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/decoded/zt1/assets",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write parsed table JSON files into",
    )
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cstring(blob: bytes) -> str:
    head = blob.split(b"\x00", 1)[0]
    if not head:
        return ""
    return head.decode("ascii", errors="ignore")


def u16_words(blob: bytes) -> list[int]:
    usable = len(blob) - (len(blob) % 2)
    return [struct.unpack("<H", blob[index : index + 2])[0] for index in range(0, usable, 2)]


def u32_words(blob: bytes) -> list[int]:
    usable = len(blob) - (len(blob) % 4)
    return [struct.unpack("<I", blob[index : index + 4])[0] for index in range(0, usable, 4)]


def read_gxl(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 10 or not data.startswith(b"GXL\x01"):
        raise ValueError(f"{path} is not a decoded GXL payload")

    row_size = struct.unpack("<H", data[4:6])[0]
    header_extra_size = struct.unpack("<H", data[6:8])[0]
    row_count = struct.unpack("<H", data[8:10])[0]
    header_size = 10 + header_extra_size
    payload = data[header_size:]
    if len(payload) != row_size * row_count:
        raise ValueError(
            f"{path} payload size mismatch: got={len(payload)} expected={row_size * row_count}"
        )

    rows = [payload[index * row_size : (index + 1) * row_size] for index in range(row_count)]
    return {
        "path": str(path),
        "rowSize": row_size,
        "headerExtraSize": header_extra_size,
        "rowCount": row_count,
        "rows": rows,
    }


def parse_xls_ai_eng(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        title_slot = row[2:32]
        numeric_block = row[32:141]
        reward_slot = row[141:279]
        hint_slot = row[279:469]
        tail_slot = row[469:501]
        records.append(
            {
                "index": index,
                "unknownHeaderU16": struct.unpack("<H", row[:2])[0],
                "title": cstring(title_slot),
                "rewardText": cstring(reward_slot),
                "hintText": cstring(hint_slot),
                "numericBlockHex": numeric_block.hex(),
                "numericBlockU16": u16_words(numeric_block),
                "tailHex": tail_slot.hex(),
                "tailU8": list(tail_slot),
                "tailLastByte": tail_slot[-1] if tail_slot else None,
                "hasHint": bool(cstring(hint_slot)),
            }
        )
    return {
        "table": "XlsAi",
        "locale": "eng",
        "rowSize": 501,
        "rowCount": len(records),
        "slotModel": {
            "headerU16": [0, 2],
            "titleSlot": [2, 32],
            "numericBlock": [32, 141],
            "rewardSlot": [141, 279],
            "hintSlot": [279, 469],
            "tailSlot": [469, 501],
        },
        "records": records,
    }


def parse_xls_worldmap(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        slots = list(row)
        neighbors = [value for value in slots if value != 0xFF]
        records.append(
            {
                "index": index,
                "slots": slots,
                "neighbors": neighbors,
                "isLinearChainNode": neighbors in ([index - 1], [index + 1], [index - 1, index + 1]),
            }
        )
    return {
        "table": "XlsWorldmap",
        "rowSize": 4,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_map(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "groupId": row[0],
                "reserved": row[1],
                "valueU16": struct.unpack("<H", row[2:4])[0],
                "tailByte": row[4],
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsMap",
        "rowSize": 5,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_level_design(rows: list[bytes]) -> dict[str, Any]:
    records = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "valueU32": struct.unpack("<I", row)[0],
            }
        )
    return {
        "table": "XlsLevelDesign",
        "rowSize": 4,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_hero_eng(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        name = cstring(row[6:])
        name_end = 6 + len(name.encode("ascii", errors="ignore")) + 1
        body = row[name_end:]
        records.append(
            {
                "index": index,
                "rawPrefixU8": list(row[:6]),
                "candidateHeroId": row[2],
                "candidateGroup": row[3],
                "candidatePortraitId": row[4],
                "name": name,
                "bodyHex": body.hex(),
                "bodyU16": u16_words(body),
                "tailAssetIds": list(row[-17:-1]),
            }
        )
    return {
        "table": "XlsHero",
        "locale": "eng",
        "rowSize": 65,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_unit_eng(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        name = cstring(row[1:77])
        name_end = 1 + len(name.encode("ascii", errors="ignore")) + 1
        pre_description_block = row[name_end:77]
        description = cstring(row[77:])
        records.append(
            {
                "index": index,
                "unknownLeadByte": row[0],
                "name": name,
                "description": description,
                "preDescriptionHex": pre_description_block.hex(),
                "preDescriptionU16": u16_words(pre_description_block),
                "rawPrefixU16": u16_words(row[:77])[:20],
                "rawTailU16": u16_words(row[77:])[:20],
            }
        )
    return {
        "table": "XlsUnit",
        "locale": "eng",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "slotModel": {
            "unknownLeadByte": [0, 1],
            "nameSlot": [1, 77],
            "descriptionSlot": [77, len(rows[0]) if rows else 0],
        },
        "records": records,
    }


def parse_xls_tower(rows: list[bytes]) -> dict[str, Any]:
    records = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "pair": list(row),
            }
        )
    return {
        "table": "XlsTower",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def build_summary(
    ai_report: dict[str, Any],
    worldmap_report: dict[str, Any],
    map_report: dict[str, Any],
    level_design_report: dict[str, Any],
    hero_report: dict[str, Any],
    unit_report: dict[str, Any],
    tower_report: dict[str, Any],
) -> dict[str, Any]:
    ai_records = ai_report["records"]
    map_records = map_report["records"]
    group_pairs: dict[int, list[int]] = {}
    for record in map_records:
        group_pairs.setdefault(int(record["groupId"]), []).append(int(record["valueU16"]))

    return {
        "ai": {
            "rowCount": ai_report["rowCount"],
            "titledRowCount": sum(1 for record in ai_records if record["title"]),
            "hintRowCount": sum(1 for record in ai_records if record["hintText"]),
            "firstTitles": [record["title"] for record in ai_records[:24]],
            "tailLastByteHistogram": {
                str(value): sum(1 for record in ai_records if record["tailLastByte"] == value)
                for value in sorted({record["tailLastByte"] for record in ai_records})
            },
        },
        "worldmap": {
            "rowCount": worldmap_report["rowCount"],
            "isLinearChain": all(record["isLinearChainNode"] for record in worldmap_report["records"]),
            "neighbors": [record["neighbors"] for record in worldmap_report["records"]],
        },
        "map": {
            "rowCount": map_report["rowCount"],
            "groupPairs": {str(group): values for group, values in sorted(group_pairs.items())},
        },
        "levelDesign": {
            "rowCount": level_design_report["rowCount"],
            "firstValues": [record["valueU32"] for record in level_design_report["records"][:16]],
        },
        "hero": {
            "rowCount": hero_report["rowCount"],
            "heroes": [
                {
                    "index": record["index"],
                    "candidateHeroId": record["candidateHeroId"],
                    "candidatePortraitId": record["candidatePortraitId"],
                    "name": record["name"],
                    "tailAssetIds": record["tailAssetIds"],
                }
                for record in hero_report["records"]
            ],
        },
        "unit": {
            "rowCount": unit_report["rowCount"],
            "firstNames": [record["name"] for record in unit_report["records"][:16]],
        },
        "tower": {
            "rowCount": tower_report["rowCount"],
            "pairs": [record["pair"] for record in tower_report["records"]],
        },
    }


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_dir = args.output_dir.resolve()

    ai = read_gxl(assets_root / "data_eng" / "XlsAi.zt1.bin")
    worldmap = read_gxl(assets_root / "data_eng" / "XlsWorldmap.zt1.bin")
    map_table = read_gxl(assets_root / "data_eng" / "XlsMap.zt1.bin")
    level_design = read_gxl(assets_root / "data_eng" / "XlsLevelDesign.zt1.bin")
    hero = read_gxl(assets_root / "data_eng" / "XlsHero.zt1.bin")
    unit = read_gxl(assets_root / "data_eng" / "XlsUnit.zt1.bin")
    tower = read_gxl(assets_root / "data_eng" / "XlsTower.zt1.bin")

    ai_report = parse_xls_ai_eng(ai["rows"])
    worldmap_report = parse_xls_worldmap(worldmap["rows"])
    map_report = parse_xls_map(map_table["rows"])
    level_design_report = parse_xls_level_design(level_design["rows"])
    hero_report = parse_xls_hero_eng(hero["rows"])
    unit_report = parse_xls_unit_eng(unit["rows"])
    tower_report = parse_xls_tower(tower["rows"])

    write_json(output_dir / "XlsAi.eng.parsed.json", ai_report)
    write_json(output_dir / "XlsWorldmap.eng.parsed.json", worldmap_report)
    write_json(output_dir / "XlsMap.eng.parsed.json", map_report)
    write_json(output_dir / "XlsLevelDesign.eng.parsed.json", level_design_report)
    write_json(output_dir / "XlsHero.eng.parsed.json", hero_report)
    write_json(output_dir / "XlsUnit.eng.parsed.json", unit_report)
    write_json(output_dir / "XlsTower.eng.parsed.json", tower_report)
    write_json(
        output_dir / "AW1.gxl.summary.json",
        build_summary(
            ai_report,
            worldmap_report,
            map_report,
            level_design_report,
            hero_report,
            unit_report,
            tower_report,
        ),
    )


if __name__ == "__main__":
    main()
