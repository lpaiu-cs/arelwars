#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, UTC
import hashlib
import json
from pathlib import Path
import shutil
import struct
from typing import Any
from zipfile import ZipFile
import zlib

from formats import PzaClip, PzxIndexedResource, PzxRootResourceGraph, read_pzx_root_resource_graph


REGRESSION_STEMS = ["082", "084", "208", "209", "215", "226", "230", "240"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the APK-derived AW1 original reference trace bundle")
    parser.add_argument("--apk", type=Path, required=True, help="Path to arel_wars_1.apk")
    parser.add_argument("--verification-spec", type=Path, required=True, help="Path to AW1.verification_spec.json")
    parser.add_argument("--stage-bindings", type=Path, required=True, help="Path to AW1.stage_bindings.json")
    parser.add_argument("--runtime-blueprint", type=Path, required=True, help="Path to AW1.runtime_blueprint.json")
    parser.add_argument("--native-truth", type=Path, required=True, help="Path to AW1.native_truth_manifest.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to AW1.original_reference_bundle.json")
    parser.add_argument("--web-output", type=Path, help="Optional path under public/")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def summarize_indexed_resource(resource: PzxIndexedResource | None) -> dict[str, Any] | None:
    if resource is None:
        return None

    offsets = list(resource.item_offsets)
    item_sizes: list[int] = []
    cursor = 0
    for end in offsets:
        item_sizes.append(max(0, int(end) - cursor))
        cursor = int(end)

    return {
        "offset": resource.offset,
        "tag": resource.tag,
        "itemCount": resource.item_count,
        "reserved": resource.reserved,
        "compressedSize": resource.compressed_size,
        "decodedSize": resource.decoded_size,
        "itemOffsets": offsets,
        "itemSizes": item_sizes,
    }


def read_pzx_root_offsets(data: bytes) -> tuple[int, int, int] | None:
    if len(data) < 16 or data[:4] != b"PZX\x01":
        return None
    return struct.unpack("<III", data[4:16])


def read_embedded_resource_summary(data: bytes, offset: int, kind: str) -> dict[str, Any] | None:
    if offset < 0 or offset + 3 > len(data):
        return None

    header = data[offset]
    content_count = struct.unpack("<H", data[offset + 1 : offset + 3])[0]
    if content_count <= 0:
        return None

    table_start = offset + 3
    table_end = table_start + content_count * 4
    if table_end > len(data):
        return None

    index_offsets = [
        struct.unpack("<I", data[table_start + index * 4 : table_start + index * 4 + 4])[0]
        for index in range(content_count)
    ]
    storage_mode = header & 0x0F
    format_variant = header >> 4

    if storage_mode == 0:
        payload_offset = table_end
        payload = data[payload_offset:]
        packed_size = None
        unpacked_size = len(payload)
    else:
        if table_end + 8 > len(data):
            return None
        unpacked_size = struct.unpack("<I", data[table_end : table_end + 4])[0]
        packed_size = struct.unpack("<I", data[table_end + 4 : table_end + 8])[0]
        payload_offset = table_end + 8
        payload_end = payload_offset + packed_size
        if payload_end > len(data):
            return None
        try:
            payload = zlib.decompress(data[payload_offset:payload_end])
        except zlib.error:
            return None
        if len(payload) != unpacked_size:
            return None

    return {
        "kind": kind,
        "offset": offset,
        "header": header,
        "storageMode": storage_mode,
        "formatVariant": format_variant,
        "contentCount": content_count,
        "indexOffsets": index_offsets,
        "packedSize": packed_size,
        "unpackedSize": unpacked_size,
        "payloadOffset": payload_offset,
        "payload": payload,
        "decodeMode": "native-aligned-embedded-resource",
    }


def summarize_embedded_resource_summary(resource: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(resource, dict):
        return None
    payload = bytes(resource["payload"])
    index_offsets = list(resource["indexOffsets"])
    item_sizes: list[int] = []
    cursor = 0
    for end in index_offsets:
        item_sizes.append(max(0, int(end) - cursor))
        cursor = int(end)
    return {
        "offset": int(resource["offset"]),
        "header": int(resource["header"]),
        "storageMode": int(resource["storageMode"]),
        "formatVariant": int(resource["formatVariant"]),
        "itemCount": int(resource["contentCount"]),
        "packedSize": resource["packedSize"],
        "decodedSize": len(payload),
        "itemOffsets": index_offsets,
        "itemSizes": item_sizes,
        "decodeMode": str(resource["decodeMode"]),
    }


def summarize_pza_from_embedded(resource: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(resource, dict):
        return None

    payload = bytes(resource["payload"])
    offsets = [int(value) for value in resource["indexOffsets"]]
    if any(offset < 0 or offset > len(payload) for offset in offsets):
        return None

    clips: list[dict[str, Any]] = []
    cursor = 0
    for clip_index, end_offset in enumerate(offsets):
        if end_offset < cursor or end_offset > len(payload):
            return None
        clip_bytes = payload[cursor:end_offset]
        cursor = end_offset
        if not clip_bytes:
            clips.append({"clipIndex": clip_index, "frameCount": 0, "frameLayout": [], "delayValues": []})
            continue
        frame_count = int(clip_bytes[0])
        expected_size = 1 + frame_count * 8
        if len(clip_bytes) < expected_size:
            return None
        frames: list[dict[str, Any]] = []
        delay_histogram = Counter()
        control_histogram = Counter()
        pointer = 1
        for _ in range(frame_count):
            frame_index = struct.unpack("<H", clip_bytes[pointer : pointer + 2])[0]
            delay = int(clip_bytes[pointer + 2])
            x = struct.unpack("<h", clip_bytes[pointer + 3 : pointer + 5])[0]
            y = struct.unpack("<h", clip_bytes[pointer + 5 : pointer + 7])[0]
            control = int(clip_bytes[pointer + 7])
            frames.append(
                {
                    "frameIndex": frame_index,
                    "delay": delay,
                    "x": x,
                    "y": y,
                    "control": control,
                }
            )
            delay_histogram.update([delay])
            control_histogram.update([control])
            pointer += 8
        clips.append(
            {
                "clipIndex": clip_index,
                "frameCount": frame_count,
                "frameIndices": [frame["frameIndex"] for frame in frames],
                "delayValues": [frame["delay"] for frame in frames],
                "delayHistogram": {str(key): delay_histogram[key] for key in sorted(delay_histogram)},
                "controlHistogram": {str(key): control_histogram[key] for key in sorted(control_histogram)},
                "frameLayout": frames,
            }
        )

    return {
        "offset": int(resource["offset"]),
        "header": int(resource["header"]),
        "storageMode": int(resource["storageMode"]),
        "formatVariant": int(resource["formatVariant"]),
        "clipCount": int(resource["contentCount"]),
        "packedSize": resource["packedSize"],
        "decodedSize": len(payload),
        "decodeMode": str(resource["decodeMode"]),
        "clips": clips,
    }


def summarize_pza_clip(clip: PzaClip) -> dict[str, Any]:
    delays = [int(frame.delay) for frame in clip.frames]
    frame_indices = [int(frame.frame_index) for frame in clip.frames]
    controls = [int(frame.control) for frame in clip.frames]
    delay_histogram = Counter(delays)
    control_histogram = Counter(controls)
    return {
        "clipIndex": clip.clip_index,
        "frameCount": clip.frame_count,
        "frameIndices": frame_indices,
        "delayValues": delays,
        "uniqueDelayValues": sorted(delay_histogram),
        "delayHistogram": {str(key): delay_histogram[key] for key in sorted(delay_histogram)},
        "controlHistogram": {str(key): control_histogram[key] for key in sorted(control_histogram)},
        "frameLayout": [
            {
                "frameIndex": int(frame.frame_index),
                "delay": int(frame.delay),
                "x": int(frame.x),
                "y": int(frame.y),
                "control": int(frame.control),
            }
            for frame in clip.frames
        ],
    }


def summarize_regression_stem(stem: str, graph: PzxRootResourceGraph, raw_data: bytes) -> dict[str, Any]:
    pza = graph.pza
    offsets = None
    embedded_pzf = None
    embedded_pza = None
    if graph.pzf is None or graph.pza is None:
        # Fall back to the native-aligned embedded-resource layout used on the disassemble branch.
        # Current main-root parsing still misses these resources on the regression stems.
        offsets = read_pzx_root_offsets(raw_data)
        if offsets is not None:
            _, pzf_offset, pza_offset = offsets
            embedded_pzf = read_embedded_resource_summary(raw_data, pzf_offset, "pzf")
            embedded_pza = read_embedded_resource_summary(raw_data, pza_offset, "pza")

    clips = list(pza.clips) if pza is not None else []
    delay_histogram = Counter()
    referenced_subframes: set[int] = set()
    for clip in clips:
        for frame in clip.frames:
            delay_histogram.update([int(frame.delay)])
            referenced_subframes.add(int(frame.frame_index))

    embedded_pza_summary = summarize_pza_from_embedded(embedded_pza)
    if embedded_pza_summary is not None:
        delay_histogram = Counter()
        referenced_subframes = set()
        for clip in embedded_pza_summary["clips"]:
            for value in clip.get("delayValues", []):
                delay_histogram.update([int(value)])
            for frame_index in clip.get("frameIndices", []):
                referenced_subframes.add(int(frame_index))

    return {
        "stem": stem,
        "assetPath": f"assets/img/{stem}.pzx",
        "typedGraph": {
            "pzd": None
            if graph.pzd is None
            else {
                "offset": graph.pzd.offset,
                "typeId": graph.pzd.type_id,
                "imageCount": graph.pzd.image_count,
                "reserved": graph.pzd.reserved,
            },
            "pzf": summarize_indexed_resource(graph.pzf) or summarize_embedded_resource_summary(embedded_pzf),
            "pza": (
                {
                    "offset": pza.resource.offset,
                    "tag": pza.resource.tag,
                    "clipCount": pza.resource.item_count,
                    "compressedSize": pza.resource.compressed_size,
                    "decodedSize": pza.resource.decoded_size,
                    "clips": [summarize_pza_clip(clip) for clip in clips],
                    "decodeMode": "main-root-resource-graph",
                }
                if pza is not None
                else embedded_pza_summary
            ),
        },
        "nativeTimingReference": {
            "source": "embedded-pza-delay",
            "delayHistogram": {str(key): delay_histogram[key] for key in sorted(delay_histogram)},
            "referencedSubFrameIndices": sorted(referenced_subframes),
        },
    }


def build_stage_reference(
    stage_check: dict[str, Any],
    stage_binding: dict[str, Any] | None,
    blueprint: dict[str, Any] | None,
) -> dict[str, Any]:
    opcode_cues = list(blueprint.get("opcodeCues", [])) if isinstance(blueprint, dict) else []
    tutorial_cues = list(blueprint.get("tutorialChainCues", [])) if isinstance(blueprint, dict) else []
    map_binding = blueprint.get("mapBinding") if isinstance(blueprint, dict) else None
    return {
        "stageIndex": int(stage_check.get("stageIndex", 0)),
        "familyId": str(stage_check.get("familyId", "")),
        "title": str(stage_check.get("title", "")),
        "aiIndex": int(stage_check.get("aiIndex", -1)),
        "routeLabel": str(stage_check.get("routeLabel", "")),
        "preferredMapIndex": stage_check.get("preferredMapIndex"),
        "templateGroupId": stage_check.get("templateGroupId"),
        "scriptFiles": list(stage_check.get("scriptFiles", [])),
        "scriptEventCount": int(stage_check.get("scriptEventCount", 0)),
        "dialogueAnchors": list(stage_check.get("dialogueAnchors", [])),
        "expectedVictoryPhaseSequence": list(stage_check.get("expectedVictoryPhaseSequence", [])),
        "expectedDefeatPhaseSequence": list(stage_check.get("expectedDefeatPhaseSequence", [])),
        "comparisonChecks": list(stage_check.get("comparisonChecks", [])),
        "hardBinding": None
        if not isinstance(stage_binding, dict)
        else {
            "bindingType": str(stage_binding.get("bindingType", "")),
            "bindingConfirmed": bool(stage_binding.get("bindingConfirmed", False)),
            "scriptBindingType": str(stage_binding.get("scriptBindingType", "")),
            "mapBindingType": str(stage_binding.get("mapBindingType", "")),
            "preferredMapIndex": stage_binding.get("preferredMapIndex"),
            "inlinePairBaseIndex": stage_binding.get("inlinePairBaseIndex"),
            "inlinePairBranchIndex": stage_binding.get("inlinePairBranchIndex"),
            "storyBranch": str(stage_binding.get("storyBranch", "")),
            "pairGeometrySignature": str(stage_binding.get("pairGeometrySignature", "")),
            "boundMapHeaders": list(stage_binding.get("boundMapHeaders", [])),
            "evidenceSummary": list(stage_binding.get("evidenceSummary", [])),
        },
        "sceneReference": {
            "tutorialChainIds": [str(item.get("chainId", "")) for item in tutorial_cues if isinstance(item, dict)],
            "opcodeCommandIds": [str(item.get("commandId", "")) for item in opcode_cues if isinstance(item, dict)],
            "opcodeCommandTypes": sorted(
                {str(item.get("commandType", "")) for item in opcode_cues if isinstance(item, dict)}
            ),
        },
        "runtimeContext": None
        if not isinstance(blueprint, dict)
        else {
            "eventCount": int(blueprint.get("eventCount", 0)),
            "recommendedArchetypeIds": list(blueprint.get("recommendedArchetypeIds", [])),
            "renderIntent": blueprint.get("renderIntent"),
            "mapBinding": map_binding,
        },
        "referenceClass": "apk-derived-structural-reference",
    }


def main() -> None:
    args = parse_args()
    verification_spec = read_json(args.verification_spec.resolve())
    stage_bindings = read_json(args.stage_bindings.resolve())
    runtime_blueprint = read_json(args.runtime_blueprint.resolve())
    native_truth = read_json(args.native_truth.resolve())

    stage_bindings_by_family = {
        str(item["familyId"]): item for item in stage_bindings.get("stageBindings", []) if isinstance(item, dict)
    }
    blueprints_by_family = {
        str(item["familyId"]): item for item in runtime_blueprint.get("stageBlueprints", []) if isinstance(item, dict)
    }

    stage_references = [
        build_stage_reference(
            stage_check,
            stage_bindings_by_family.get(str(stage_check.get("familyId", ""))),
            blueprints_by_family.get(str(stage_check.get("familyId", ""))),
        )
        for stage_check in verification_spec.get("stageChecks", [])
        if isinstance(stage_check, dict)
    ]

    unique_script_files = sorted({path for item in stage_references for path in item.get("scriptFiles", [])})
    apk_path = args.apk.resolve()
    apk_sha256 = sha256_file(apk_path)
    regression_references: list[dict[str, Any]] = []
    abi_histogram: Counter[str] = Counter()

    with ZipFile(apk_path) as zf:
        for name in zf.namelist():
            if name.startswith("lib/") and name.endswith(".so"):
                parts = name.split("/")
                if len(parts) >= 3:
                    abi_histogram.update([parts[1]])

        for stem in REGRESSION_STEMS:
            asset_name = f"assets/img/{stem}.pzx"
            data = zf.read(asset_name)
            graph = read_pzx_root_resource_graph(data)
            if graph is None:
                raise ValueError(f"failed to decode typed root graph for {asset_name}")
            regression_references.append(summarize_regression_stem(stem, graph, data))

    payload = {
        "specVersion": "aw1-original-reference-bundle-v1",
        "generatedAtIso": datetime.now(UTC).isoformat(),
        "sourceApk": {
            "path": str(apk_path),
            "sha256": apk_sha256,
            "sizeBytes": apk_path.stat().st_size,
            "nativeLibAbis": dict(sorted(abi_histogram.items())),
        },
        "summary": {
            "stageReferenceCount": len(stage_references),
            "uniqueScriptFileCount": len(unique_script_files),
            "regressionStemCount": len(regression_references),
            "truthLayerCount": int(native_truth.get("summary", {}).get("frozenTruthLayerCount", 0)),
            "heuristicLayerCount": int(native_truth.get("summary", {}).get("heuristicLayerCount", 0)),
        },
        "referencePolicy": {
            "bundleKind": "apk-derived-reference-bundle",
            "scope": "original APK structural and native-aligned reference inputs",
            "limitations": [
                "This bundle is generated from original APK assets and native-aligned findings.",
                "It is not a live legacy runtime capture bundle.",
                "Live original-device or legacy-emulator traces should be added on top of this bundle during later certification stages.",
            ],
            "nativeTruthManifestPath": str(args.native_truth.resolve()),
            "regressionStemSet": REGRESSION_STEMS,
        },
        "traceSchema": {
            "stageReferenceFields": [
                "stage identity",
                "hard stage binding",
                "dialogue anchors",
                "expected victory and defeat phase sequences",
                "scene command references",
            ],
            "regressionRenderFields": [
                "typed PZX resource graph",
                "embedded PZA clip timing",
                "PZF pool summary",
                "PZD type and image count",
            ],
        },
        "stageReferences": stage_references,
        "regressionRenderReferences": regression_references,
        "nativeTruthSnapshot": {
            "summary": native_truth.get("summary", {}),
            "frozenTruthLayerIds": [item.get("id") for item in native_truth.get("frozenTruthLayers", [])],
            "heuristicLayerIds": [item.get("id") for item in native_truth.get("heuristicLayers", [])],
        },
        "findings": [
            "This bundle freezes APK-derived stage-flow references for all 111 current stages.",
            "This bundle also freezes native-aligned regression render references for the eight critical stems.",
            "Future original-equivalence work should compare remake traces against this bundle plus live legacy runtime captures when they become available.",
        ],
    }

    write_json(args.output.resolve(), payload)
    if args.web_output:
        copy_file(args.output.resolve(), args.web_output.resolve())


if __name__ == "__main__":
    main()
