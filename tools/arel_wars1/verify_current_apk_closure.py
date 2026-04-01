#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from formats import read_pzx_indexed_effectex_pzf_frame_stream


DEFAULT_ASSETS_ROOT = Path("recovery/arel_wars1/native_tmp/extract/apk_unzip/assets")
DEFAULT_REPORT = Path("recovery/arel_wars1/native_tmp/binary_asset_report-session.json")
DEFAULT_CALL_EDGES = Path("recovery/arel_wars1/disassembly/libgameDSO-call-edges.json")
DEFAULT_LIB = Path("recovery/arel_wars1/disassembly/libgameDSO.so")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that the current Arel Wars 1 APK decode is fully closed for the embedded PZX path.",
    )
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--call-edges", type=Path, default=DEFAULT_CALL_EDGES)
    parser.add_argument("--lib", type=Path, default=DEFAULT_LIB)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_call_edges(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def get_inbound_callers(edges: list[dict], target: str) -> list[str]:
    callers = sorted(
        {
            edge["caller"]
            for edge in edges
            if edge.get("callee") == target and edge.get("caller")
        }
    )
    return callers


def verify_assets_root(assets_root: Path) -> None:
    pzx_paths = sorted(assets_root.rglob("*.pzx"))
    img_pzx_paths = sorted((assets_root / "img").glob("*.pzx"))
    auxiliary_pzx_paths = sorted(assets_root.glob("*.pzx"))
    pzf_paths = sorted(assets_root.rglob("*.pzf"))
    pzd_paths = sorted(assets_root.rglob("*.pzd"))
    pza_paths = sorted(assets_root.rglob("*.pza"))
    require(len(pzx_paths) == 256, f"Expected 256 .pzx files, found {len(pzx_paths)}")
    require(len(img_pzx_paths) == 253, f"Expected 253 img/*.pzx files, found {len(img_pzx_paths)}")
    require(
        sorted(path.name for path in auxiliary_pzx_paths) == ["TouchOemIME.pzx", "certi.pzx", "logo.pzx"],
        f"Unexpected auxiliary PZX set: {[path.name for path in auxiliary_pzx_paths]}",
    )
    require(not pzf_paths, f"Unexpected standalone .pzf samples: {len(pzf_paths)}")
    require(not pzd_paths, f"Unexpected standalone .pzd samples: {len(pzd_paths)}")
    require(not pza_paths, f"Unexpected standalone .pza samples: {len(pza_paths)}")


def verify_report(summary: dict) -> None:
    require(summary["pzxCount"] == 253, f"Unexpected pzxCount: {summary['pzxCount']}")
    require(summary["allPzxCount"] == 256, f"Unexpected allPzxCount: {summary['allPzxCount']}")
    require(summary["auxiliaryPzxCount"] == 3, f"Unexpected auxiliaryPzxCount: {summary['auxiliaryPzxCount']}")
    require(
        summary["auxiliaryPzxNames"] == ["certi.pzx", "logo.pzx", "TouchOemIME.pzx"],
        f"Unexpected auxiliaryPzxNames: {summary['auxiliaryPzxNames']}",
    )
    require(
        summary["auxiliaryPzxLayoutCounts"] == {"pzd-pzf-pza": 2, "pzf-pzd-no-pza": 1},
        f"Unexpected auxiliaryPzxLayoutCounts: {summary['auxiliaryPzxLayoutCounts']}",
    )
    auxiliary_preview = {entry["name"]: entry for entry in summary["auxiliaryPzxPreview"]}
    require(
        auxiliary_preview["logo.pzx"]["embeddedPzd"] == {"typeCode": 7, "contentCount": 1, "layout": "row-stream-list"},
        f"Unexpected logo.pzx PZD summary: {auxiliary_preview['logo.pzx']['embeddedPzd']}",
    )
    require(
        auxiliary_preview["logo.pzx"]["embeddedPzf"]["frameCount"] == 1,
        f"Unexpected logo.pzx frame count: {auxiliary_preview['logo.pzx']['embeddedPzf']}",
    )
    require(
        auxiliary_preview["TouchOemIME.pzx"]["embeddedPzd"] == {"typeCode": 8, "contentCount": 121, "layout": "first-stream-sheet"},
        f"Unexpected TouchOemIME.pzx PZD summary: {auxiliary_preview['TouchOemIME.pzx']['embeddedPzd']}",
    )
    require(
        auxiliary_preview["TouchOemIME.pzx"]["embeddedPzf"]["frameCount"] == 19,
        f"Unexpected TouchOemIME.pzx frame count: {auxiliary_preview['TouchOemIME.pzx']['embeddedPzf']}",
    )
    require(
        auxiliary_preview["certi.pzx"]["resourceLayout"] == "pzf-pzd-no-pza",
        f"Unexpected certi.pzx root layout: {auxiliary_preview['certi.pzx']['resourceLayout']}",
    )
    require(
        auxiliary_preview["certi.pzx"]["embeddedPzd"] == {"typeCode": 8, "contentCount": 8, "layout": "first-stream-sheet"},
        f"Unexpected certi.pzx PZD summary: {auxiliary_preview['certi.pzx']['embeddedPzd']}",
    )
    require(
        auxiliary_preview["certi.pzx"]["embeddedPzf"]["frameCount"] == 9,
        f"Unexpected certi.pzx frame count: {auxiliary_preview['certi.pzx']['embeddedPzf']}",
    )
    require(auxiliary_preview["certi.pzx"]["embeddedPza"] is None, "certi.pzx should not expose a PZA resource")
    require(summary["firstStreamDecodedCount"] == 205, "Type-8 first-stream decode count drifted")
    require(summary["firstStreamDecodeFailedCount"] == 0, "First-stream decode failures appeared")
    require(summary["pzxVariantCounts"] == {"7": 48, "8": 205}, "PZX variant distribution drifted")
    require(summary["embeddedPzdTypeCounts"] == {"7": 48, "8": 205}, "PZD type distribution drifted")
    require(
        summary["embeddedPzdLayoutCounts"] == {"first-stream-sheet": 205, "row-stream-list": 48},
        "PZD layout counts drifted",
    )
    require(summary["embeddedPzfPzxCount"] == 253, "Embedded PZF count drifted")
    require(summary["embeddedPzfParsedPzxCount"] == 253, "Embedded PZF exact-parse count drifted")
    require(summary["embeddedPzfMatchedSecondStreamCount"] == 216, "Second-stream PZF match count drifted")
    require(summary["embeddedPzfFrameRecordOffsetPrefixCount"] == 51, "Frame-record prefix overlap drifted")
    require(summary["embeddedPzfBboxReferenceTotal"] == 0, "Reference-point bbox samples appeared")
    require(summary["embeddedPzfEffectExResolvedSelectorCounts"] == {}, "Embedded PZF unexpectedly resolved as EffectEx")
    require(summary["embeddedPzfEffectExResolvedDrawOpNameCounts"] == {}, "Embedded PZF draw-op resolution unexpectedly populated")
    require(summary["embeddedPzfEffectExResolvedModuleCounts"] == {}, "Embedded PZF module resolution unexpectedly populated")
    require(
        summary["embeddedPzdPzfRelationCounts"] == {"empty": 2, "exact-max-plus-one": 244, "in-range": 7},
        "PZD/PZF relation counts drifted",
    )
    require(summary["embeddedPzaPzxCount"] == 159, "Embedded PZA count drifted")
    require(summary["embeddedPzaMatchedThirdStreamCount"] == 145, "Third-stream PZA match count drifted")
    require(
        summary["embeddedPzaPzfRelationCounts"] == {"exact-max-plus-one": 143, "in-range": 16},
        "PZA/PZF relation counts drifted",
    )


def verify_call_edges(edges: list[dict]) -> None:
    dormant_targets = {
        "_Z9GsLoadPzfPKcS0_S0_biiii": "standalone GsLoadPzf should be unreferenced in the current APK",
        "_Z13GsLoadPzfPartP9CGxPZAMgrPiPKcS3_S3_biiii": "standalone GsLoadPzfPart should be unreferenced in the current APK",
        "_ZN13CGxPZxFrameBB22GetReferencePointCountEv": "Reference-point bbox path should be unreferenced",
        "_ZN13CGxPZxFrameBB17GetReferencePointEi": "Reference-point getter should be unreferenced",
        "_ZN21CGxZeroEffectExPZFMgrC1Eh": "ZeroEffectEx PZF manager constructor should be unreferenced",
        "_ZN21CGxZeroEffectExPZFMgrC2Eh": "ZeroEffectEx PZF manager constructor should be unreferenced",
        "_ZN21CGxZeroEffectExPZFMgrC1Ev": "ZeroEffectEx PZF manager constructor should be unreferenced",
        "_ZN21CGxZeroEffectExPZFMgrC2Ev": "ZeroEffectEx PZF manager constructor should be unreferenced",
        "_ZN17CGxEffectExPZDMgrC1Ev": "EffectEx PZD manager constructor should be unreferenced",
        "_ZN17CGxEffectExPZDMgrC2Ev": "EffectEx PZD manager constructor should be unreferenced",
        "_ZN21CGxZeroEffectExPZDMgrC1Ev": "ZeroEffectEx PZD manager constructor should be unreferenced",
        "_ZN21CGxZeroEffectExPZDMgrC2Ev": "ZeroEffectEx PZD manager constructor should be unreferenced",
    }
    for target, message in dormant_targets.items():
        callers = get_inbound_callers(edges, target)
        require(not callers, f"{message}: {callers}")


def verify_lib_strings(lib_path: Path) -> None:
    blob = lib_path.read_bytes()
    require(blob.count(b".pzx") > 0, "libgameDSO.so no longer contains .pzx references")
    require(blob.count(b".pzf") == 0, "libgameDSO.so unexpectedly references .pzf literals")
    require(blob.count(b".pzd") == 0, "libgameDSO.so unexpectedly references .pzd literals")
    require(blob.count(b".pza") == 0, "libgameDSO.so unexpectedly references .pza literals")


def verify_effectex_parser() -> None:
    payload = bytes(
        [
            0x01,
            0x00,
            0x05,
            0x00,
            0x02,
            0x00,
            0xFD,
            0xFF,
            0x03,
            0x03,
            0x71,
            0x44,
            0x33,
            0x22,
            0x11,
            0x04,
        ]
    )
    decoded = read_pzx_indexed_effectex_pzf_frame_stream(payload, [0], 1, max_subframe_index=8)
    require(decoded is not None, "Synthetic EffectEx sample A failed to parse")
    subframe = decoded.frames[0].subframes[0]
    require(decoded.subframe_layout == "effectex", "Synthetic EffectEx sample A wrong layout")
    require(decoded.subframe_stride == 0x18, "Synthetic EffectEx sample A wrong stride")
    require(subframe.extra == bytes([0x03, 0x71, 0x04]), f"Unexpected logical extra A: {subframe.extra.hex()}")
    require(subframe.effectex_selector == 0x71, "Synthetic EffectEx sample A wrong selector")
    require(subframe.effectex_parameter == 0x11223344, "Synthetic EffectEx sample A wrong parameter")
    require(subframe.effectex_draw_op == 19, "Synthetic EffectEx sample A wrong draw op")
    require(subframe.effectex_module == 0, "Synthetic EffectEx sample A wrong module")

    payload = bytes(
        [
            0x01,
            0x00,
            0x09,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x03,
            0x67,
            0x04,
            0x03,
            0x02,
            0x01,
            0x72,
            0x88,
            0x77,
            0x66,
            0x55,
            0x03,
        ]
    )
    decoded = read_pzx_indexed_effectex_pzf_frame_stream(payload, [0], 1, max_subframe_index=16)
    require(decoded is not None, "Synthetic EffectEx sample B failed to parse")
    subframe = decoded.frames[0].subframes[0]
    require(subframe.extra == bytes([0x67, 0x72, 0x03]), f"Unexpected logical extra B: {subframe.extra.hex()}")
    require(subframe.effectex_selector == 0x72, "Synthetic EffectEx sample B wrong selector")
    require(subframe.effectex_parameter == 0x55667788, "Synthetic EffectEx sample B wrong parameter")
    require(subframe.effectex_draw_op == 19, "Synthetic EffectEx sample B wrong draw op")
    require(subframe.effectex_module == 1, "Synthetic EffectEx sample B wrong module")


def main() -> int:
    args = parse_args()
    verify_assets_root(args.assets_root)
    report = load_report(args.report)
    verify_report(report["summary"])
    edges = load_call_edges(args.call_edges)
    verify_call_edges(edges)
    verify_lib_strings(args.lib)
    verify_effectex_parser()
    print("Current APK closure verified: embedded PZX/PZD/PZF/PZA path is fully resolved and remaining branches are dormant.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
