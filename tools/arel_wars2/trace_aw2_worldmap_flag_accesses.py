from __future__ import annotations

import json
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import (
    ARM_INS_LDR,
    ARM_INS_LDRB,
    ARM_INS_STR,
    ARM_INS_STRB,
    ARM_OP_IMM,
    ARM_OP_REG,
    ARM_OP_MEM,
    ARM_REG_PC,
)


ROOT = Path(__file__).resolve().parents[2]
NDK_BIN = Path(
    r"C:\Users\lpaiu\AppData\Local\Android\Sdk\ndk\30.0.14904198\toolchains\llvm\prebuilt\windows-x86_64\bin"
)
LLVM_READELF = NDK_BIN / "llvm-readelf.exe"
ORIGINAL_LIB = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "original_lib_extract" / "libgameDSO.so"
REPORT_PATH = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2_worldmap_flag_accesses.json"

TEXT_VA = 0x0009E7D0
TEXT_OFF = 0x09E7D0
TEXT_SIZE = 0x130E4C

TARGETS = {
    0x58: "shared_touch_latch_byte",
    0x1068: "global_input_gate_off",
    0x106C: "global_input_gate_mode",
    0x3628: "this_last_family_or_route",
    0x362C: "this_worldmap_commit_flag",
    0x3630: "this_worldmap_aux_word",
    0x36F8: "this_worldmap_menu_state",
    0x379C: "this_stage_select_visible_or_fade_flag",
    0x4054: "this_other_ui_ptr",
    0x4058: "this_ui_list_ptr",
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


def literal_value(blob: bytes, literal_addr: int) -> int:
    off = TEXT_OFF + (literal_addr - TEXT_VA)
    return struct.unpack_from("<I", blob, off)[0]


def classify_access(insn_id: int) -> str | None:
    if insn_id in {ARM_INS_LDR, ARM_INS_LDRB}:
        return "read"
    if insn_id in {ARM_INS_STR, ARM_INS_STRB}:
        return "write"
    return None


def scan_accesses(lib_path: Path, symbols: list[FuncSymbol]) -> dict[str, object]:
    blob = lib_path.read_bytes()
    text = blob[TEXT_OFF : TEXT_OFF + TEXT_SIZE]
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True

    by_target: dict[str, dict[str, list[dict[str, str]]]] = {
        label: {"readers": [], "writers": []} for label in TARGETS.values()
    }
    by_function: dict[str, list[dict[str, str]]] = {}

    for sym in symbols:
        if not (TEXT_VA <= sym.addr < TEXT_VA + TEXT_SIZE):
            continue
        start = sym.addr & ~1
        code = text[start - TEXT_VA : start - TEXT_VA + sym.size]
        insns = list(md.disasm(code, start))
        matches: list[dict[str, str]] = []
        reg_targets: dict[int, tuple[int, str, int]] = {}
        for idx, insn in enumerate(insns):
            # Track literal loads like "ldr r3, [pc, #imm]" where the literal cell contains 0x1068 etc.
            access = classify_access(insn.id)
            if access is not None and len(insn.operands) >= 2:
                mem_op = insn.operands[1]
                if mem_op.type == ARM_OP_MEM:
                    target_value: int | None = None
                    target_label: str | None = None

                    if mem_op.mem.disp in TARGETS:
                        target_value = mem_op.mem.disp
                        target_label = TARGETS[target_value]
                    elif mem_op.mem.index in reg_targets:
                        target_value, target_label, _ = reg_targets[mem_op.mem.index]

                    if target_label is not None and target_value is not None:
                        entry = {
                            "insn": hex(insn.address),
                            "mnemonic": insn.mnemonic,
                            "opStr": insn.op_str,
                            "access": access,
                            "targetValue": hex(target_value),
                            "targetLabel": target_label,
                        }
                        matches.append(entry)
                        bucket = "writers" if access == "write" else "readers"
                        by_target[target_label][bucket].append({"function": sym.name, **entry})

            _, regs_written = insn.regs_access()
            for reg in regs_written:
                reg_targets.pop(reg, None)

            if insn.id == ARM_INS_LDR and len(insn.operands) >= 2:
                dst = insn.operands[0]
                src = insn.operands[1]
                if dst.type == ARM_OP_REG and src.type == ARM_OP_MEM and src.mem.base == ARM_REG_PC:
                    literal_addr = (insn.address + 4 + src.mem.disp) & 0xFFFFFFFF
                    if TEXT_VA <= literal_addr < TEXT_VA + TEXT_SIZE:
                        value = literal_value(blob, literal_addr)
                        label = TARGETS.get(value)
                        if label is not None:
                            reg_targets[dst.reg] = (value, label, insn.address)

        if matches:
            by_function[sym.name] = matches

    summary = {}
    for label, buckets in by_target.items():
        summary[label] = {
            "readerCount": len({entry["function"] for entry in buckets["readers"]}),
            "writerCount": len({entry["function"] for entry in buckets["writers"]}),
        }

    notes = [
        "Only concrete memory reads/writes are recorded here; pure literal loads without a following memory access are ignored.",
        "PC-literal offsets like 0x1068/0x379c are tracked through the register they were loaded into and then matched against subsequent LDR/LDRB/STR/STRB memory operands.",
        "This report is intended to identify setters/clearers for the worldmap input gates, not to serve as full dataflow proof.",
    ]

    return {
        "sourceLib": str(lib_path),
        "functionCount": len(symbols),
        "summary": summary,
        "byTarget": by_target,
        "byFunction": by_function,
        "notes": notes,
    }


def main() -> int:
    if not ORIGINAL_LIB.exists():
        raise SystemExit(f"Missing original library: {ORIGINAL_LIB}")
    symbols = read_symbols(ORIGINAL_LIB)
    report = scan_accesses(ORIGINAL_LIB, symbols)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
