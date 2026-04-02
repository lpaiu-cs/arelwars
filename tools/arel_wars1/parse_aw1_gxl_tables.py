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


def be16_words(blob: bytes) -> list[int]:
    usable = len(blob) - (len(blob) % 2)
    return [struct.unpack(">H", blob[index : index + 2])[0] for index in range(0, usable, 2)]


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
                "valueLoByte": row[2],
                "valueHiByte": row[3],
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


def parse_xls_hero_skill_eng(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        name = cstring(row[:17])
        metadata = list(row[17:27])
        description = cstring(row[27:])
        records.append(
            {
                "index": index,
                "name": name,
                "skillCodeCandidate": metadata[0],
                "aiCodeCandidate": metadata[1],
                "flagA": metadata[2],
                "modeA": metadata[3],
                "modeB": metadata[4],
                "slotOrPowerCandidate": metadata[5],
                "tailFlags": metadata[6:10],
                "description": description,
                "metadataU8": metadata,
            }
        )
    return {
        "table": "XlsHeroSkill",
        "locale": "eng",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "slotModel": {
            "nameSlot": [0, 17],
            "metadata": [17, 27],
            "descriptionSlot": [27, len(rows[0]) if rows else 0],
        },
        "records": records,
    }


def parse_xls_item_eng(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        name = cstring(row[1:22])
        metadata = row[22:38]
        description = cstring(row[38:])
        records.append(
            {
                "index": index,
                "unknownLeadByte": row[0],
                "name": name,
                "itemCodeCandidate": metadata[0],
                "categoryCandidate": metadata[1],
                "aiCodeCandidate": metadata[2],
                "flagA": metadata[3],
                "flagB": metadata[4],
                "modeCandidate": metadata[5],
                "flagC": metadata[6],
                "costCandidate": struct.unpack("<I", metadata[7:11])[0],
                "unknownTailValue": metadata[11],
                "description": description,
                "metadataU8": list(metadata),
            }
        )
    return {
        "table": "XlsItem",
        "locale": "eng",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "slotModel": {
            "unknownLeadByte": [0, 1],
            "nameSlot": [1, 22],
            "metadata": [22, 38],
            "descriptionSlot": [38, len(rows[0]) if rows else 0],
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


def parse_xls_hero_ai(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "heroIdCandidate": row[0],
                "profileGroupCandidate": row[1],
                "priorityGridU8": list(row[2:16]),
                "timingPatternU8": list(row[16:24]),
                "fallbackPatternU8": list(row[24:34]),
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsHero_Ai",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_skill_ai(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "skillIdCandidate": row[0],
                "triggerWindowA": list(row[1:6]),
                "triggerWindowB": list(row[6:11]),
                "tailModeBytes": list(row[11:13]),
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsSkill_Ai",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_projectile(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "familyCandidate": row[0],
                "projectileIdCandidate": row[1],
                "variantCandidate": row[2],
                "speedOrRangeCandidate": row[3],
                "motionCandidate": row[4],
                "tailBlockU8": list(row[5:13]),
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsProjectile",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_base_attack(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "familyCandidate": row[0],
                "attackIdCandidate": row[1],
                "variantCandidate": row[2],
                "flagsByte": row[3],
                "parameterBytes": list(row[4:16]),
                "rawU8": list(row),
                "rawU16LE": u16_words(row),
                "rawU16BE": be16_words(row),
            }
        )
    return {
        "table": "XlsBaseAttack",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_balance(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "scalarA": row[0],
                "scalarB": row[1],
                "sentinel": row[2],
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsBalance",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_correspondence(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        active_slots = [slot for slot, value in enumerate(row) if value == 1]
        masked_slots = [slot for slot, value in enumerate(row) if value == 0xFF]
        records.append(
            {
                "index": index,
                "activeSlots": active_slots,
                "maskedSlots": masked_slots,
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsCorrespondence",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_effect(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "familyCandidate": row[0],
                "effectIdCandidate": row[1],
                "variantCandidate": row[2],
                "frameOrDurationCandidate": row[3],
                "loopFlagCandidate": row[4],
                "blendFlagCandidate": row[5],
                "extraModeCandidate": row[6],
                "sentinelCandidate": row[7],
                "tailByte": row[8],
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsEffect",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_particle(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "particleIdCandidate": row[0],
                "variantCandidate": row[1],
                "sentinel": row[2],
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsParticle",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_hero_active_skill(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "headerBytes": list(row[:4]),
                "timingWindowA": list(row[4:8]),
                "timingWindowB": list(row[8:16]),
                "tailPairBE": be16_words(row[16:24]),
                "rawU8": list(row),
                "rawU16LE": u16_words(row),
            }
        )
    return {
        "table": "XlsHeroActiveSkill",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_hero_buff_skill(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        records.append(
            {
                "index": index,
                "familyCandidate": row[0],
                "tierCandidate": row[1],
                "triggerModeCandidate": row[2],
                "magnitudeWindowU8": list(row[3:11]),
                "skillCodeCandidate": row[10],
                "profileCandidate": row[11],
                "conditionWindowU8": list(row[11:19]),
                "tailLinkCandidate": row[24],
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsHeroBuffSkill",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "records": records,
    }


def parse_xls_hero_passive_skill(rows: list[bytes]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        name = cstring(row[:20])
        records.append(
            {
                "index": index,
                "name": name,
                "nameSlotHex": row[:20].hex(),
                "valueA": struct.unpack("<H", row[20:22])[0],
                "valueB": struct.unpack("<H", row[22:24])[0],
                "tailU16": u16_words(row[24:28]),
                "rawU8": list(row),
            }
        )
    return {
        "table": "XlsHeroPassiveSkill",
        "locale": "eng",
        "rowSize": len(rows[0]) if rows else 0,
        "rowCount": len(records),
        "slotModel": {
            "nameSlot": [0, 20],
            "valueA": [20, 22],
            "valueB": [22, 24],
            "tail": [24, 28],
        },
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
    hero_skill_report: dict[str, Any],
    item_report: dict[str, Any],
    hero_ai_report: dict[str, Any],
    skill_ai_report: dict[str, Any],
    projectile_report: dict[str, Any],
    effect_report: dict[str, Any],
    base_attack_report: dict[str, Any],
    particle_report: dict[str, Any],
    hero_active_skill_report: dict[str, Any],
    hero_buff_skill_report: dict[str, Any],
    hero_passive_skill_report: dict[str, Any],
    balance_report: dict[str, Any],
    correspondence_report: dict[str, Any],
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
        "heroSkill": {
            "rowCount": hero_skill_report["rowCount"],
            "firstNames": [record["name"] for record in hero_skill_report["records"][:16]],
            "aiCodeHistogram": {
                str(value): sum(
                    1 for record in hero_skill_report["records"] if record["aiCodeCandidate"] == value
                )
                for value in sorted(
                    {record["aiCodeCandidate"] for record in hero_skill_report["records"]}
                )
            },
        },
        "item": {
            "rowCount": item_report["rowCount"],
            "firstNames": [record["name"] for record in item_report["records"][:16]],
            "categoryHistogram": {
                str(value): sum(
                    1 for record in item_report["records"] if record["categoryCandidate"] == value
                )
                for value in sorted(
                    {record["categoryCandidate"] for record in item_report["records"]}
                )
            },
        },
        "tower": {
            "rowCount": tower_report["rowCount"],
            "pairs": [record["pair"] for record in tower_report["records"]],
        },
        "heroAi": {
            "rowCount": hero_ai_report["rowCount"],
            "heroIdCandidates": [
                record["heroIdCandidate"] for record in hero_ai_report["records"]
            ],
        },
        "skillAi": {
            "rowCount": skill_ai_report["rowCount"],
            "skillIdCandidates": [
                record["skillIdCandidate"] for record in skill_ai_report["records"][:16]
            ],
            "bestCurrentReading": "Compact item/active-skill trigger policy table; ids align more strongly with XlsItem itemCodeCandidate than with raw row indices.",
        },
        "projectile": {
            "rowCount": projectile_report["rowCount"],
            "familyHistogram": {
                str(value): sum(
                    1 for record in projectile_report["records"] if record["familyCandidate"] == value
                )
                for value in sorted(
                    {record["familyCandidate"] for record in projectile_report["records"]}
                )
            },
        },
        "effect": {
            "rowCount": effect_report["rowCount"],
            "familyHistogram": {
                str(value): sum(
                    1 for record in effect_report["records"] if record["familyCandidate"] == value
                )
                for value in sorted(
                    {record["familyCandidate"] for record in effect_report["records"]}
                )
            },
        },
        "baseAttack": {
            "rowCount": base_attack_report["rowCount"],
            "familyHistogram": {
                str(value): sum(
                    1
                    for record in base_attack_report["records"]
                    if record["familyCandidate"] == value
                )
                for value in sorted(
                    {record["familyCandidate"] for record in base_attack_report["records"]}
                )
            },
        },
        "particle": {
            "rowCount": particle_report["rowCount"],
            "particleIds": [
                record["particleIdCandidate"] for record in particle_report["records"]
            ],
        },
        "heroActiveSkill": {
            "rowCount": hero_active_skill_report["rowCount"],
            "tailPairPreview": [
                record["tailPairBE"] for record in hero_active_skill_report["records"][:8]
            ],
        },
        "heroBuffSkill": {
            "rowCount": hero_buff_skill_report["rowCount"],
            "skillCodeHistogram": {
                str(value): sum(
                    1
                    for record in hero_buff_skill_report["records"]
                    if record["skillCodeCandidate"] == value
                )
                for value in sorted(
                    {record["skillCodeCandidate"] for record in hero_buff_skill_report["records"]}
                )
            },
        },
        "heroPassiveSkill": {
            "rowCount": hero_passive_skill_report["rowCount"],
            "firstNames": [record["name"] for record in hero_passive_skill_report["records"][:16]],
        },
        "balance": {
            "rowCount": balance_report["rowCount"],
            "rows": [record["rawU8"] for record in balance_report["records"]],
        },
        "correspondence": {
            "rowCount": correspondence_report["rowCount"],
            "activeSlots": [record["activeSlots"] for record in correspondence_report["records"]],
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
    hero_skill = read_gxl(assets_root / "data_eng" / "XlsHeroSkill.zt1.bin")
    item = read_gxl(assets_root / "data_eng" / "XlsItem.zt1.bin")
    tower = read_gxl(assets_root / "data_eng" / "XlsTower.zt1.bin")
    hero_ai = read_gxl(assets_root / "data_eng" / "XlsHero_Ai.zt1.bin")
    skill_ai = read_gxl(assets_root / "data_eng" / "XlsSkill_Ai.zt1.bin")
    projectile = read_gxl(assets_root / "data_eng" / "XlsProjectile.zt1.bin")
    effect = read_gxl(assets_root / "data_eng" / "XlsEffect.zt1.bin")
    base_attack = read_gxl(assets_root / "data_eng" / "XlsBaseAttack.zt1.bin")
    particle = read_gxl(assets_root / "data_eng" / "XlsParticle.zt1.bin")
    hero_active_skill = read_gxl(assets_root / "data_eng" / "XlsHeroActiveSkill.zt1.bin")
    hero_buff_skill = read_gxl(assets_root / "data_eng" / "XlsHeroBuffSkill.zt1.bin")
    hero_passive_skill = read_gxl(assets_root / "data_eng" / "XlsHeroPassiveSkill.zt1.bin")
    balance = read_gxl(assets_root / "data_eng" / "XlsBalance.zt1.bin")
    correspondence = read_gxl(assets_root / "data_eng" / "XlsCorrespondence.zt1.bin")

    ai_report = parse_xls_ai_eng(ai["rows"])
    worldmap_report = parse_xls_worldmap(worldmap["rows"])
    map_report = parse_xls_map(map_table["rows"])
    level_design_report = parse_xls_level_design(level_design["rows"])
    hero_report = parse_xls_hero_eng(hero["rows"])
    unit_report = parse_xls_unit_eng(unit["rows"])
    hero_skill_report = parse_xls_hero_skill_eng(hero_skill["rows"])
    item_report = parse_xls_item_eng(item["rows"])
    tower_report = parse_xls_tower(tower["rows"])
    hero_ai_report = parse_xls_hero_ai(hero_ai["rows"])
    skill_ai_report = parse_xls_skill_ai(skill_ai["rows"])
    projectile_report = parse_xls_projectile(projectile["rows"])
    effect_report = parse_xls_effect(effect["rows"])
    base_attack_report = parse_xls_base_attack(base_attack["rows"])
    particle_report = parse_xls_particle(particle["rows"])
    hero_active_skill_report = parse_xls_hero_active_skill(hero_active_skill["rows"])
    hero_buff_skill_report = parse_xls_hero_buff_skill(hero_buff_skill["rows"])
    hero_passive_skill_report = parse_xls_hero_passive_skill(hero_passive_skill["rows"])
    balance_report = parse_xls_balance(balance["rows"])
    correspondence_report = parse_xls_correspondence(correspondence["rows"])

    write_json(output_dir / "XlsAi.eng.parsed.json", ai_report)
    write_json(output_dir / "XlsWorldmap.eng.parsed.json", worldmap_report)
    write_json(output_dir / "XlsMap.eng.parsed.json", map_report)
    write_json(output_dir / "XlsLevelDesign.eng.parsed.json", level_design_report)
    write_json(output_dir / "XlsHero.eng.parsed.json", hero_report)
    write_json(output_dir / "XlsUnit.eng.parsed.json", unit_report)
    write_json(output_dir / "XlsHeroSkill.eng.parsed.json", hero_skill_report)
    write_json(output_dir / "XlsItem.eng.parsed.json", item_report)
    write_json(output_dir / "XlsTower.eng.parsed.json", tower_report)
    write_json(output_dir / "XlsHero_Ai.eng.parsed.json", hero_ai_report)
    write_json(output_dir / "XlsSkill_Ai.eng.parsed.json", skill_ai_report)
    write_json(output_dir / "XlsProjectile.eng.parsed.json", projectile_report)
    write_json(output_dir / "XlsEffect.eng.parsed.json", effect_report)
    write_json(output_dir / "XlsBaseAttack.eng.parsed.json", base_attack_report)
    write_json(output_dir / "XlsParticle.eng.parsed.json", particle_report)
    write_json(output_dir / "XlsHeroActiveSkill.eng.parsed.json", hero_active_skill_report)
    write_json(output_dir / "XlsHeroBuffSkill.eng.parsed.json", hero_buff_skill_report)
    write_json(output_dir / "XlsHeroPassiveSkill.eng.parsed.json", hero_passive_skill_report)
    write_json(output_dir / "XlsBalance.eng.parsed.json", balance_report)
    write_json(output_dir / "XlsCorrespondence.eng.parsed.json", correspondence_report)
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
            hero_skill_report,
            item_report,
            hero_ai_report,
            skill_ai_report,
            projectile_report,
            effect_report,
            base_attack_report,
            particle_report,
            hero_active_skill_report,
            hero_buff_skill_report,
            hero_passive_skill_report,
            balance_report,
            correspondence_report,
        ),
    )


if __name__ == "__main__":
    main()
