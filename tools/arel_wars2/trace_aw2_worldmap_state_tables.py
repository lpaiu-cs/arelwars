from __future__ import annotations

import json
import re
import struct
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NDK_BIN = Path(
    r"C:\Users\lpaiu\AppData\Local\Android\Sdk\ndk\30.0.14904198\toolchains\llvm\prebuilt\windows-x86_64\bin"
)
LLVM_READELF = NDK_BIN / "llvm-readelf.exe"
ORIGINAL_LIB = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "original_lib_extract" / "libgameDSO.so"
REPORT_PATH = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2_worldmap_state_tables.json"

TEXT_VA = 0x0009E7D0
TEXT_OFF = 0x09E7D0


def read_symbol_addrs(lib_path: Path) -> dict[str, int]:
    out = subprocess.check_output(
        [str(LLVM_READELF), "-Ws", str(lib_path)],
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    symbols: dict[str, int] = {}
    for line in out.splitlines():
        match = re.match(r"\s*\d+:\s*([0-9a-fA-F]+)\s+(\d+)\s+FUNC\s+\w+\s+\w+\s+\d+\s+(\S+)", line)
        if not match:
            continue
        symbols[match.group(3)] = int(match.group(1), 16) & ~1
    return symbols


def read_u32(blob: bytes, va: int) -> int:
    off = TEXT_OFF + (va - TEXT_VA)
    return struct.unpack_from("<I", blob, off)[0]


def thumb_literal_addr(insn_addr: int, disp: int) -> int:
    return ((insn_addr + 4) & ~3) + disp


def decode_relative_u32_table(blob: bytes, base: int, count: int) -> list[int]:
    values: list[int] = []
    for index in range(count):
        rel = read_u32(blob, base + index * 4)
        values.append((base + rel) & 0xFFFFFFFF)
    return values


def decode_tables(lib_path: Path) -> dict[str, object]:
    blob = lib_path.read_bytes()
    symbols = read_symbol_addrs(lib_path)

    draw_loading_base = 0x102898 + read_u32(blob, thumb_literal_addr(0x102894, 0x280))
    on_pointer_press_base = 0x0EB1E0 + read_u32(blob, thumb_literal_addr(0x0EB1DA, 0x174))
    on_pointer_release_base = 0x10A5D4 + read_u32(blob, thumb_literal_addr(0x10A5CC, 0x24C))

    draw_loading_targets = decode_relative_u32_table(blob, draw_loading_base, 0x2F)
    on_pointer_press_targets = decode_relative_u32_table(blob, on_pointer_press_base, 0x1F)
    on_pointer_release_targets = decode_relative_u32_table(blob, on_pointer_release_base, 0x1F)

    draw_loading_cases = {
        str(index): hex(target) for index, target in enumerate(draw_loading_targets)
    }
    press_state_cases = {
        str(5 + index): hex(target) for index, target in enumerate(on_pointer_press_targets)
    }
    release_state_cases = {
        str(5 + index): hex(target) for index, target in enumerate(on_pointer_release_targets)
    }

    create_stage_select = symbols["_ZN16CPdStateWorldmap17CreateStageSelectEv"]
    create_stage_info = symbols["_ZN16CPdStateWorldmap15CreateStageInfoEv"]
    create_game_start = symbols["_ZN16CPdStateWorldmap15CreateGameStartEv"]

    draw_loading_action_map: dict[str, str] = {}
    for index, target in enumerate(draw_loading_targets):
        if target == 0x102C92:
            draw_loading_action_map["CreateStageSelect"] = str(index)
        elif target == 0x102C88:
            draw_loading_action_map["CreateStageInfo"] = str(index)
        elif target == 0x102C10:
            draw_loading_action_map["CreateGameStart"] = str(index)

    return {
        "sourceLib": str(lib_path),
        "drawLoading": {
            "symbol": "_ZN16CPdStateWorldmap11DrawLoadingEv",
            "actionFieldOffset": "0x34",
            "jumpTableBase": hex(draw_loading_base),
            "cases": draw_loading_cases,
            "actionMap": draw_loading_action_map,
            "targetSymbols": {
                "CreateStageSelect": hex(create_stage_select),
                "CreateStageInfo": hex(create_stage_info),
                "CreateGameStart": hex(create_game_start),
            },
        },
        "onPointerPress": {
            "symbol": "_ZN16CPdStateWorldmap14OnPointerPressEP12GxPointerPos",
            "stateFieldOffset": "0x4",
            "stateBias": 5,
            "jumpTableBase": hex(on_pointer_press_base),
            "cases": press_state_cases,
            "notableCases": {
                "state5_main": press_state_cases["5"],
                "state29": press_state_cases["29"],
                "state30": press_state_cases["30"],
                "state33": press_state_cases["33"],
                "state35": press_state_cases["35"],
            },
        },
        "onPointerRelease": {
            "symbol": "_ZN16CPdStateWorldmap16OnPointerReleaseEP12GxPointerPos",
            "stateFieldOffset": "0x4",
            "stateBias": 5,
            "jumpTableBase": hex(on_pointer_release_base),
            "cases": release_state_cases,
            "notableCases": {
                "state5_main": release_state_cases["5"],
                "state29": release_state_cases["29"],
                "state30": release_state_cases["30"],
                "state33": release_state_cases["33"],
                "state35": release_state_cases["35"],
            },
        },
        "notes": [
            "DrawLoading reads the pending loading action from [this+0x34].",
            "Case 4 in DrawLoading creates stage select, case 5 creates stage info, and case 17 creates game start.",
            "OnPointerPress state 5 dispatches directly to TouchInputWorldFrame.",
            "OnPointerRelease state 5 dispatches into the mixed overlay helper DoTouchMoveWorldArea.",
        ],
    }


def main() -> int:
    if not ORIGINAL_LIB.exists():
        raise SystemExit(f"Missing original library: {ORIGINAL_LIB}")

    report = decode_tables(ORIGINAL_LIB)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["drawLoading"]["actionMap"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
