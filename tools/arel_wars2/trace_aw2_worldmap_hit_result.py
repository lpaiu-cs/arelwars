from __future__ import annotations

import json
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_INS_LDR, ARM_INS_LDRB, ARM_INS_STR, ARM_INS_STRB
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC, ARM_REG_SP


ROOT = Path(__file__).resolve().parents[2]
NDK_BIN = Path(
    r"C:\Users\lpaiu\AppData\Local\Android\Sdk\ndk\30.0.14904198\toolchains\llvm\prebuilt\windows-x86_64\bin"
)
LLVM_READELF = NDK_BIN / "llvm-readelf.exe"
ORIGINAL_LIB = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "original_lib_extract" / "libgameDSO.so"
REPORT_PATH = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2_worldmap_hit_result_accesses.json"

TEXT_VA = 0x0009E7D0
TEXT_OFF = 0x09E7D0
TEXT_SIZE = 0x130E4C
TARGET_VALUE = 0x200


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
        name = match.group(3)
        if "CPdStateWorldmap" not in name:
            continue
        symbols.append(
            FuncSymbol(
                addr=int(match.group(1), 16),
                size=int(match.group(2)),
                name=name,
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


def update_reg_state(reg_values: dict[int, int], insn) -> None:
    ops = insn.operands
    if insn.mnemonic in {"mov", "movs"} and len(ops) >= 2:
        dst, src = ops[0], ops[1]
        if dst.type == ARM_OP_REG and src.type == ARM_OP_IMM:
            reg_values[dst.reg] = src.imm
        return

    if insn.mnemonic in {"add", "adds", "sub", "subs"} and len(ops) >= 3:
        dst, left, right = ops[0], ops[1], ops[2]
        if dst.type == ARM_OP_REG and left.type == ARM_OP_REG and right.type == ARM_OP_IMM:
            base = reg_values.get(left.reg)
            if base is not None:
                if insn.mnemonic in {"add", "adds"}:
                    reg_values[dst.reg] = base + right.imm
                else:
                    reg_values[dst.reg] = base - right.imm
        return

    if insn.mnemonic == "lsls" and len(ops) >= 3:
        dst, src, amount = ops[0], ops[1], ops[2]
        if dst.type == ARM_OP_REG and src.type == ARM_OP_REG and amount.type == ARM_OP_IMM:
            base = reg_values.get(src.reg)
            if base is not None:
                reg_values[dst.reg] = (base << amount.imm) & 0xFFFFFFFF
        return

    if insn.id == ARM_INS_LDR and len(ops) >= 2:
        dst, src = ops[0], ops[1]
        if dst.type == ARM_OP_REG and src.type == ARM_OP_MEM and src.mem.base == ARM_REG_PC:
            literal_addr = (insn.address + 4 + src.mem.disp) & 0xFFFFFFFF
            if TEXT_VA <= literal_addr < TEXT_VA + TEXT_SIZE:
                reg_values[dst.reg] = literal_value(BLOB, literal_addr)
            return

    _, regs_written = insn.regs_access()
    for reg in regs_written:
        reg_values.pop(reg, None)


def scan_accesses(lib_path: Path, symbols: list[FuncSymbol]) -> dict[str, object]:
    text = BLOB[TEXT_OFF : TEXT_OFF + TEXT_SIZE]
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True

    by_function: dict[str, list[dict[str, str]]] = {}

    for sym in symbols:
        if not (TEXT_VA <= sym.addr < TEXT_VA + TEXT_SIZE):
            continue

        start = sym.addr & ~1
        code = text[start - TEXT_VA : start - TEXT_VA + sym.size]
        reg_values: dict[int, int] = {}
        matches: list[dict[str, str]] = []

        for insn in md.disasm(code, start):
            update_reg_state(reg_values, insn)

            access = classify_access(insn.id)
            if access is None or len(insn.operands) < 2:
                continue

            mem_op = insn.operands[1]
            if mem_op.type != ARM_OP_MEM:
                continue
            if mem_op.mem.base in {ARM_REG_PC, ARM_REG_SP}:
                continue

            target_value: int | None = None
            if mem_op.mem.disp == TARGET_VALUE:
                target_value = TARGET_VALUE
            elif mem_op.mem.base in reg_values and reg_values[mem_op.mem.base] == TARGET_VALUE:
                target_value = TARGET_VALUE
            elif mem_op.mem.index in reg_values and reg_values[mem_op.mem.index] == TARGET_VALUE:
                target_value = TARGET_VALUE

            if target_value is None:
                continue

            matches.append(
                {
                    "insn": hex(insn.address),
                    "mnemonic": insn.mnemonic,
                    "opStr": insn.op_str,
                    "access": access,
                    "targetValue": hex(TARGET_VALUE),
                }
            )

        if matches:
            by_function[sym.name] = matches

    summary = {
        "readerCount": sum(
            1 for entries in by_function.values() if any(entry["access"] == "read" for entry in entries)
        ),
        "writerCount": sum(
            1 for entries in by_function.values() if any(entry["access"] == "write" for entry in entries)
        ),
    }

    notes = [
        "Target field 0x200 is the worldmap-local byte written by CPdStateWorldmap::TouchInputWorldFrame after CCommonUI::TouchInputWorldFrame returns.",
        "Manual re-read shows CCommonUI::TouchInputWorldFrame only ORs CPdSharing::ClickButtonIcon hits over up to four icon pointers.",
        "DoTouchMoveWorldArea clears 0x200 and returns before the generic world-area rectangle scan when the byte is nonzero.",
        "This makes 0x200 an overlay/button-layer hit latch, not a base-area index or stage-transition request.",
        "The scanner tracks direct displacements, simple mov/add/sub/lsl-derived immediates, and PC-literal loads that later become memory-base or memory-index operands.",
        "This report is intended to identify the minimal reader/writer set for the worldframe hit-result byte, not to prove full control flow.",
    ]

    return {
        "sourceLib": str(lib_path),
        "targetValue": hex(TARGET_VALUE),
        "summary": summary,
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


BLOB = ORIGINAL_LIB.read_bytes() if ORIGINAL_LIB.exists() else b""


if __name__ == "__main__":
    raise SystemExit(main())
