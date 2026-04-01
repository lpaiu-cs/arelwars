from __future__ import annotations

import argparse
import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG
from elftools.elf.elffile import ELFFile


DEFAULT_ELF = Path("recovery/arel_wars1/disassembly/libgameDSO.so")
DEFAULT_FUNCTIONS = (
    "_ZN9CGxPZxMgr9SetSourceEPKcjb",
    "_ZN16CGxPZxParserBase12CheckPZxTypeEP12tagPZxHeaderP9CGxStreamiPKci",
    "_ZN12CGxPZAParser12DecodeHeaderEb",
    "_ZN12CGxPZAParser4OpenEv",
    "_ZN12CGxPZAParser19DecodeAnimationDataEti",
    "_ZN16CGxPZxParserBase14SeekIndexTableEt",
    "_ZN6CGxPZA12GetAnimationEi",
    "_ZN6CGxPZA19CreateAniFrameIndexEiP9CGxPZxAnii",
    "_ZN9CGxPZAMgr7LoadAniEtP9CGxPZFMgrP9CGxPZDMgr",
    "_ZN6CGxPZF19CreateSubFrameIndexEiP11CGxPZxFramei",
    "_ZN9CGxPZFMgr11LoadFrameExEtP13CGxPZDPackageP9tagEffectPsS4_",
    "_ZN9CGxPZxAni6DoPlayEv",
    "_ZN9CGxPZxAni25GetCurrentDelayFrameCountEv",
)


@dataclass(frozen=True)
class FunctionSymbol:
    name: str
    address: int
    size: int


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Focused Thumb disassembler for libgameDSO.so",
    )
    parser.add_argument(
        "--elf",
        type=Path,
        default=DEFAULT_ELF,
        help=f"ELF path (default: {DEFAULT_ELF})",
    )
    parser.add_argument(
        "--find",
        action="append",
        default=[],
        help="List function symbols matching this substring (case-insensitive). May be repeated.",
    )
    parser.add_argument(
        "--function",
        action="append",
        default=[],
        help="Disassemble a specific function symbol. May be repeated.",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Disassemble the current default target set.",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=50,
        help="Maximum symbols to print per --find pattern.",
    )
    return parser


def load_symbols(elf: ELFFile) -> list[FunctionSymbol]:
    symtab = elf.get_section_by_name(".symtab")
    if symtab is None:
        raise SystemExit("Missing .symtab section")

    symbols: list[FunctionSymbol] = []
    for symbol in symtab.iter_symbols():
        if symbol["st_info"]["type"] != "STT_FUNC":
            continue
        if not symbol.name:
            continue
        size = int(symbol["st_size"])
        if size <= 0:
            continue
        address = int(symbol["st_value"]) & ~1
        symbols.append(FunctionSymbol(symbol.name, address, size))

    symbols.sort(key=lambda item: (item.address, item.name))
    return symbols


def build_symbol_lookup(symbols: list[FunctionSymbol]) -> tuple[list[int], list[FunctionSymbol]]:
    addresses = [symbol.address for symbol in symbols]
    return addresses, symbols


def resolve_symbol_by_address(
    address: int,
    addresses: list[int],
    symbols: list[FunctionSymbol],
) -> FunctionSymbol | None:
    index = bisect_right(addresses, address) - 1
    if index < 0:
        return None
    symbol = symbols[index]
    if symbol.address <= address < symbol.address + symbol.size:
        return symbol
    return None


def vaddr_to_offset(elf: ELFFile, address: int) -> int | None:
    for section in elf.iter_sections():
        start = int(section["sh_addr"])
        size = int(section["sh_size"])
        if size <= 0:
            continue
        end = start + size
        if start <= address < end:
            return int(section["sh_offset"]) + (address - start)
    return None


def read_u32(elf_bytes: bytes, elf: ELFFile, address: int) -> int | None:
    offset = vaddr_to_offset(elf, address)
    if offset is None or offset + 4 > len(elf_bytes):
        return None
    return int.from_bytes(elf_bytes[offset : offset + 4], "little")


def looks_ascii(data: bytes) -> bool:
    if not data:
        return False
    printable = 0
    for byte in data:
        if byte == 0:
            break
        if 32 <= byte < 127:
            printable += 1
        else:
            return False
    return printable >= 4


def read_c_string(elf_bytes: bytes, elf: ELFFile, address: int) -> str | None:
    offset = vaddr_to_offset(elf, address)
    if offset is None:
        return None
    end = offset
    while end < len(elf_bytes) and elf_bytes[end] != 0:
        end += 1
    candidate = elf_bytes[offset:end]
    if not looks_ascii(candidate):
        return None
    return candidate.decode("ascii")


def format_instruction_comment(
    insn,
    elf: ELFFile,
    elf_bytes: bytes,
    symbol_addresses: list[int],
    symbols: list[FunctionSymbol],
) -> str:
    comments: list[str] = []

    for operand in insn.operands:
        if operand.type == ARM_OP_IMM and insn.mnemonic.startswith("b"):
            target = operand.imm
            symbol = resolve_symbol_by_address(target, symbol_addresses, symbols)
            if symbol is None:
                comments.append(f"target=0x{target:08X}")
            elif symbol.address == target:
                comments.append(f"target={symbol.name}")
            else:
                comments.append(f"target={symbol.name}+0x{target - symbol.address:X}")

    for operand in insn.operands:
        if operand.type != ARM_OP_MEM:
            continue
        if insn.reg_name(operand.mem.base) != "pc":
            continue

        literal_address = ((insn.address + 4) & ~3) + operand.mem.disp
        value = read_u32(elf_bytes, elf, literal_address)
        if value is None:
            continue

        symbol = resolve_symbol_by_address(value, symbol_addresses, symbols)
        if symbol is not None:
            if symbol.address == value:
                comments.append(f"literal={symbol.name}")
            else:
                comments.append(f"literal={symbol.name}+0x{value - symbol.address:X}")
            continue

        string_value = read_c_string(elf_bytes, elf, value)
        if string_value is not None:
            comments.append(f'literal_string=\"{string_value}\"')
            continue

        comments.append(f"literal_u32=0x{value:08X}")

    return " ; " + " | ".join(comments) if comments else ""


def disassemble_function(
    elf: ELFFile,
    elf_bytes: bytes,
    symbol: FunctionSymbol,
    symbol_addresses: list[int],
    symbols: list[FunctionSymbol],
) -> list[str]:
    text = elf.get_section_by_name(".text")
    if text is None:
        raise SystemExit("Missing .text section")

    text_address = int(text["sh_addr"])
    offset = symbol.address - text_address
    code = text.data()[offset : offset + symbol.size]

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True

    lines = [f"===== {symbol.name} @0x{symbol.address:08X} size={symbol.size} ====="]
    for insn in md.disasm(code, symbol.address):
        comment = format_instruction_comment(insn, elf, elf_bytes, symbol_addresses, symbols)
        lines.append(f"0x{insn.address:08X}:\t{insn.mnemonic}\t{insn.op_str}{comment}")
    lines.append("")
    return lines


def find_symbols(symbols: list[FunctionSymbol], pattern: str, limit: int) -> list[str]:
    needle = pattern.lower()
    matches = [
        f"0x{symbol.address:08X}\t{symbol.size}\t{symbol.name}"
        for symbol in symbols
        if needle in symbol.name.lower()
    ]
    if limit > 0:
        matches = matches[:limit]
    return matches


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.elf.exists():
        parser.error(f"ELF file not found: {args.elf}")

    elf_bytes = args.elf.read_bytes()
    with args.elf.open("rb") as fh:
        elf = ELFFile(fh)
        symbols = load_symbols(elf)

    symbol_addresses, ordered_symbols = build_symbol_lookup(symbols)
    symbol_by_name = {symbol.name: symbol for symbol in ordered_symbols}

    for pattern in args.find:
        print(f"## matches for {pattern!r}")
        matches = find_symbols(ordered_symbols, pattern, args.max_matches)
        if not matches:
            print("(none)")
        else:
            for match in matches:
                print(match)
        print()

    requested_names: list[str] = []
    if args.defaults:
        requested_names.extend(DEFAULT_FUNCTIONS)
    requested_names.extend(args.function)

    if not requested_names:
        return 0

    missing = [name for name in requested_names if name not in symbol_by_name]
    if missing:
        for name in missing:
            print(f"Missing function symbol: {name}", file=sys.stderr)
        return 1

    with args.elf.open("rb") as fh:
        elf = ELFFile(fh)
        for name in requested_names:
            lines = disassemble_function(
                elf=elf,
                elf_bytes=elf_bytes,
                symbol=symbol_by_name[name],
                symbol_addresses=symbol_addresses,
                symbols=ordered_symbols,
            )
            print("\n".join(lines))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
