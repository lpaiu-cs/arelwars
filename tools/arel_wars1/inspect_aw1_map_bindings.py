#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import struct
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build provisional AW1 stage-to-map binding candidates from parsed tables and map payloads"
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/parsed_tables",
    )
    parser.add_argument(
        "--map-root",
        type=Path,
        required=True,
        help="Path to recovery/arel_wars1/decoded/zt1/assets/map",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the binding candidate JSON",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_map_headers(map_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(map_root.glob("*.zt1.bin")):
        data = path.read_bytes()
        if len(data) < 32:
            continue
        header_words = [struct.unpack_from("<I", data, offset)[0] for offset in range(0, 32, 4)]
        map_index = int(path.name.split(".", 1)[0])
        layer_count = header_words[1]
        width = header_words[2]
        height = header_words[3]
        tile_payload_guess = 2 * layer_count * width * height
        records.append(
            {
                "mapIndex": map_index,
                "file": path.name,
                "fileSize": len(data),
                "header": {
                    "version": header_words[0],
                    "layerCount": layer_count,
                    "width": width,
                    "height": height,
                    "reserved0": header_words[4],
                    "reserved1": header_words[5],
                    "variantOrGroup": header_words[6],
                    "reserved2": header_words[7],
                },
                "tilePayloadGuessBytes": tile_payload_guess,
                "headerAndMetaGuessBytes": len(data) - tile_payload_guess,
            }
        )
    return records


def classify_story_backed_ai_rows(stage_progression: dict[str, Any]) -> set[int]:
    backed: set[int] = set()
    for family in stage_progression.get("families", []):
        if not isinstance(family, dict):
            continue
        ai_index = family.get("aiIndexCandidate")
        if isinstance(ai_index, int):
            backed.add(ai_index)
    return backed


def stage_runtime_field(record: dict[str, Any]) -> dict[str, Any]:
    blob = bytes.fromhex(str(record["numericBlockHex"]))
    field_u32_0 = struct.unpack_from("<I", blob, 0)[0]
    field_u32_1 = struct.unpack_from("<I", blob, 4)[0]
    field_u32_2 = struct.unpack_from("<I", blob, 8)[0]
    return {
        "blobPrefixHex": blob[:20].hex(),
        "stageScalarCandidate": field_u32_2,
        "tierCandidate": blob[13],
        "variantCandidate": blob[15],
        "regionCandidate": blob[16],
        "constantMarkerCandidate": blob[17],
        "storyFlagCandidate": blob[18],
        "prefixControlA": field_u32_0,
        "prefixControlB": field_u32_1,
    }


def build_cluster_summary(ai_records: list[dict[str, Any]], stage_backed_rows: set[int]) -> dict[str, Any]:
    cluster_by_region_variant: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    cluster_by_tier_region: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    field_histograms: dict[str, Counter[int]] = {
        "tierCandidate": Counter(),
        "variantCandidate": Counter(),
        "regionCandidate": Counter(),
        "constantMarkerCandidate": Counter(),
        "storyFlagCandidate": Counter(),
    }

    for record in ai_records:
        index = int(record["index"])
        if index not in stage_backed_rows:
            continue
        fields = stage_runtime_field(record)
        for key in field_histograms:
            field_histograms[key][int(fields[key])] += 1
        cluster_by_region_variant[(fields["regionCandidate"], fields["variantCandidate"])].append(
            {
                "index": index,
                "title": record["title"],
                "variantCandidate": fields["variantCandidate"],
                "regionCandidate": fields["regionCandidate"],
                "storyFlagCandidate": fields["storyFlagCandidate"],
                "tierCandidate": fields["tierCandidate"],
            }
        )
        cluster_by_tier_region[(fields["tierCandidate"], fields["regionCandidate"])].append(
            {
                "index": index,
                "title": record["title"],
                "tierCandidate": fields["tierCandidate"],
                "regionCandidate": fields["regionCandidate"],
                "variantCandidate": fields["variantCandidate"],
                "storyFlagCandidate": fields["storyFlagCandidate"],
            }
        )

    def summarize_cluster(items: list[dict[str, Any]]) -> dict[str, Any]:
        variant_hist = Counter(
            int(item["variantCandidate"])
            for item in items
            if "variantCandidate" in item and item["variantCandidate"] is not None
        )
        tier_hist = Counter(
            int(item["tierCandidate"])
            for item in items
            if "tierCandidate" in item and item["tierCandidate"] is not None
        )
        return {
            "count": len(items),
            "indexRange": [items[0]["index"], items[-1]["index"]],
            "indices": [item["index"] for item in items],
            "titlePreview": [item["title"] for item in items[:8]],
            "storyFlagHistogram": dict(
                sorted(Counter(int(item["storyFlagCandidate"]) for item in items).items())
            ),
            "tierHistogram": dict(sorted(tier_hist.items())),
            "variantHistogram": dict(sorted(variant_hist.items())),
        }

    return {
        "fieldHistograms": {
            key: dict(sorted(counter.items())) for key, counter in field_histograms.items()
        },
        "clustersByRegionVariant": [
            {
                "regionCandidate": region,
                "variantCandidate": variant,
                **summarize_cluster(items),
            }
            for (region, variant), items in sorted(cluster_by_region_variant.items())
        ],
        "clustersByTierRegion": [
            {
                "tierCandidate": tier,
                "regionCandidate": region,
                **summarize_cluster(items),
            }
            for (tier, region), items in sorted(cluster_by_tier_region.items())
        ],
    }


def build_map_group_summary(
    map_headers: list[dict[str, Any]], map_records: list[dict[str, Any]]
) -> dict[str, Any]:
    nonzero_rows = [record for record in map_records if int(record["valueU16"]) > 0]
    active_pair_count = len(nonzero_rows) // 2
    grouped_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in map_records:
        grouped_rows[int(record["groupId"])].append(record)

    candidate_pairs = []
    for group_id, rows in sorted(grouped_rows.items()):
        pair_index = group_id * 2
        pair_headers = [item for item in map_headers if pair_index <= item["mapIndex"] <= pair_index + 1]
        candidate_pairs.append(
            {
                "groupId": group_id,
                "rows": rows,
                "candidateMapBinPair": [item["mapIndex"] for item in pair_headers],
                "candidateMapHeaders": [
                    {
                        "mapIndex": item["mapIndex"],
                        "layerCount": item["header"]["layerCount"],
                        "width": item["header"]["width"],
                        "height": item["header"]["height"],
                        "variantOrGroup": item["header"]["variantOrGroup"],
                        "fileSize": item["fileSize"],
                        "headerAndMetaGuessBytes": item["headerAndMetaGuessBytes"],
                    }
                    for item in pair_headers
                ],
                "hasNonZeroMetric": any(int(row["valueU16"]) > 0 for row in rows),
            }
        )

    return {
        "activeNonZeroRowCount": len(nonzero_rows),
        "activeTemplatePairCount": active_pair_count,
        "groupCandidates": candidate_pairs,
    }


def main() -> None:
    args = parse_args()
    parsed_dir = args.parsed_dir.resolve()
    map_root = args.map_root.resolve()

    ai_report = read_json(parsed_dir / "XlsAi.eng.parsed.json")
    map_report = read_json(parsed_dir / "XlsMap.eng.parsed.json")
    worldmap_report = read_json(parsed_dir / "XlsWorldmap.eng.parsed.json")
    stage_progression = read_json(parsed_dir / "AW1.stage_progression.json")

    ai_records = ai_report["records"]
    map_records = map_report["records"]
    map_headers = parse_map_headers(map_root)
    stage_backed_rows = classify_story_backed_ai_rows(stage_progression)

    runtime_fields = {
        str(record["index"]): stage_runtime_field(record)
        for record in ai_records
        if int(record["index"]) in stage_backed_rows
    }

    report = {
        "scriptBackedStageCount": len(stage_backed_rows),
        "worldmapNodeCount": len(worldmap_report["records"]),
        "mapBinCount": len(map_headers),
        "mapHeaders": map_headers,
        "mapGroupSummary": build_map_group_summary(map_headers, map_records),
        "stageRuntimeFieldSummary": build_cluster_summary(ai_records, stage_backed_rows),
        "stageRuntimeFieldsByAiIndex": runtime_fields,
        "hypotheses": [
            {
                "field": "numericBlock[13]",
                "nameCandidate": "tierCandidate",
                "confidence": "medium",
                "notes": "Clusters into 10/20/30/50 and cleanly splits late-game arcs, so it is likely a world progression tier or mission tier bucket.",
            },
            {
                "field": "numericBlock[15]",
                "nameCandidate": "variantCandidate",
                "confidence": "medium",
                "notes": "Small bounded range 1..6 and strong reuse inside a region; likely a local scenario or map-variant selector rather than a global stage id.",
            },
            {
                "field": "numericBlock[16]",
                "nameCandidate": "regionCandidate",
                "confidence": "high",
                "notes": "Clusters story stages into large contiguous groups 5/6/7/9, making it the strongest candidate for chapter or region bucket.",
            },
            {
                "field": "numericBlock[18]",
                "nameCandidate": "storyFlagCandidate",
                "confidence": "medium",
                "notes": "Binary 0/1 field that flips between adjacent stage rows and likely marks intro/outro or story-enabled stage variants.",
            },
            {
                "field": "map/*.zt1.bin header",
                "nameCandidate": "layeredMapHeader",
                "confidence": "high",
                "notes": "First 32 bytes read as version, layerCount, width, height, reserved, reserved, variantOrGroup, reserved; file sizes roughly follow 2 * layerCount * width * height + meta.",
            },
            {
                "field": "XlsMap rows",
                "nameCandidate": "activeTemplatePairs",
                "confidence": "medium",
                "notes": "Only the first 10 rows carry non-zero metrics, which strongly suggests five active map template pairs aligned with map bin pairs 000/001 .. 008/009.",
            },
        ],
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
