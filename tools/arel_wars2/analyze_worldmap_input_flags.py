from __future__ import annotations

import json
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_INS_LDR, ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC


ROOT = Path(__file__).resolve().parents[2]
NDK_BIN = Path(
    r"C:\Users\lpaiu\AppData\Local\Android\Sdk\ndk\30.0.14904198\toolchains\llvm\prebuilt\windows-x86_64\bin"
)
LLVM_READELF = NDK_BIN / "llvm-readelf.exe"
ORIGINAL_LIB = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "original_lib_extract" / "libgameDSO.so"
REPORT_PATH = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2_worldmap_input_flags.json"

TEXT_VA = 0x0009E7D0
TEXT_OFF = 0x09E7D0
TEXT_SIZE = 0x130E4C

TARGET_LITERALS = {
    0x1068: "global_input_gate_off",
    0x3628: "this_last_family_or_route",
    0x362C: "this_worldmap_commit_flag",
    0x3630: "this_worldmap_aux_word",
    0x379C: "this_stage_select_visible_or_fade_flag",
    0x4054: "this_other_ui_ptr",
    0x4058: "this_ui_list_ptr",
}

TARGET_FUNCS = {
    "_ZN16CPdStateWorldmap14OnPointerPressEP12GxPointerPos",
    "_ZN16CPdStateWorldmap18TouchInputMainLoopEv",
    "_ZN16CPdStateWorldmap22TouchInputWorldMapMenuEv",
    "_ZN16CPdStateWorldmap21TouchInputStageSelectEv",
    "_ZN16CPdStateWorldmap15DrawStageSelectEv",
    "_ZN16CPdStateWorldmap14CreateMainLoopEv",
    "_ZN16CPdStateWorldmap10InitializeEv",
}


@dataclass(frozen=True)
class FuncSymbol:
    addr: int
    size: int
    name: str


def read_symbols(lib_path: Path) -> list[FuncSymbol]:
    out = subprocess.check_output(
        [str(LLVM_READELF), "-Ws", str(lib_path)],
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    symbols: list[FuncSymbol] = []
    for line in out.splitlines():
        match = re.match(r"\s*\d+:\s*([0-9a-fA-F]+)\s+(\d+)\s+FUNC\s+\w+\s+\w+\s+\d+\s+(\S+)", line)
        if not match:
            continue
        symbols.append(
            FuncSymbol(
                addr=int(match.group(1), 16),
                size=int(match.group(2)),
                name=match.group(3),
            )
        )
    return sorted(symbols, key=lambda item: item.addr)


def read_text_blob(lib_path: Path) -> bytes:
    blob = lib_path.read_bytes()
    return blob[TEXT_OFF : TEXT_OFF + TEXT_SIZE]


def literal_value(blob: bytes, literal_addr: int) -> int:
    off = TEXT_OFF + (literal_addr - TEXT_VA)
    return struct.unpack_from("<I", blob, off)[0]


def decode_literal_refs(lib_path: Path, symbols: list[FuncSymbol]) -> dict[str, list[dict[str, int | str]]]:
    blob = lib_path.read_bytes()
    text = blob[TEXT_OFF : TEXT_OFF + TEXT_SIZE]
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True

    refs: dict[str, list[dict[str, int | str]]] = {}
    for sym in symbols:
        if not (TEXT_VA <= sym.addr < TEXT_VA + TEXT_SIZE):
            continue
        code = text[(sym.addr & ~1) - TEXT_VA : (sym.addr & ~1) - TEXT_VA + sym.size]
        matches: list[dict[str, int | str]] = []
        for insn in md.disasm(code, sym.addr & ~1):
            if insn.id == ARM_INS_LDR and len(insn.operands) >= 2:
                src = insn.operands[1]
                if src.type == ARM_OP_MEM and src.mem.base == ARM_REG_PC:
                    literal_addr = (insn.address + 4 + src.mem.disp) & 0xFFFFFFFF
                    if TEXT_VA <= literal_addr < TEXT_VA + TEXT_SIZE:
                        value = literal_value(blob, literal_addr)
                        if value in TARGET_LITERALS:
                            matches.append(
                                {
                                    "insn": hex(insn.address),
                                    "literalAddr": hex(literal_addr),
                                    "value": hex(value),
                                    "label": TARGET_LITERALS[value],
                                }
                            )
            for operand in insn.operands:
                if operand.type == ARM_OP_IMM and operand.imm == 0x58:
                    matches.append(
                        {
                            "insn": hex(insn.address),
                            "literalAddr": "",
                            "value": hex(operand.imm),
                            "label": "shared_touch_latch_byte",
                        }
                    )
        if matches:
            refs[sym.name] = matches
    return refs


def summarize(refs: dict[str, list[dict[str, int | str]]]) -> dict[str, object]:
    interesting = {name: refs[name] for name in refs if name in TARGET_FUNCS}
    by_literal: dict[str, list[str]] = {label: [] for label in TARGET_LITERALS.values()}
    by_literal["shared_touch_latch_byte"] = []
    for name, entries in refs.items():
        seen = set()
        for entry in entries:
            label = str(entry["label"])
            if label not in seen:
                by_literal.setdefault(label, []).append(name)
                seen.add(label)

    notes = [
        "global_input_gate_off (0x1068) is shared outside worldmap; it is consumed by scriptmgr, game, and multiple worldmap draw/touch paths.",
        "this_stage_select_visible_or_fade_flag (0x379c) is zeroed during CreateMainLoop and is checked by DrawStageSelect and TouchInputStageSelect before input/render proceeds.",
        "this_worldmap_commit_flag (0x362c) is zeroed in both CreateMainLoop and Initialize, then consumed by TouchInputWorldMapMenu, TouchInputStageSelect, StageInfo, and many popup/menu flows.",
        "shared_touch_latch_byte (0x58) is the immediate latch written during pointer handling and consumed by TouchInputMainLoop/TouchInputWorldMapMenu/TouchInputStageSelect.",
    ]

    return {
        "targetFunctions": interesting,
        "functionsByLiteral": by_literal,
        "notes": notes,
    }


def main() -> int:
    if not ORIGINAL_LIB.exists():
        raise SystemExit(f"Missing original library: {ORIGINAL_LIB}")
    symbols = read_symbols(ORIGINAL_LIB)
    refs = decode_literal_refs(ORIGINAL_LIB, symbols)
    report = {
        "sourceLib": str(ORIGINAL_LIB),
        "functionCount": len(symbols),
        "summary": summarize(refs),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
