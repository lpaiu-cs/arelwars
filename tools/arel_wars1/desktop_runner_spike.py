#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import re
import struct
from collections import Counter
from pathlib import Path
from typing import Callable

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.arm_const import (
    UC_ARM_REG_CPSR,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_SP,
)


DEFAULT_LIB = Path("recovery/arel_wars1/native_tmp/libgameDSO.so")
DEFAULT_OUTPUT = Path("recovery/arel_wars1/native_tmp/desktop_spike/session.json")
PAGE_SIZE = 0x1000

BASE_ADDR = 0x10000000
STACK_BASE = 0x70000000
STACK_SIZE = 0x00200000
HEAP_BASE = 0x50000000
HEAP_SIZE = 0x01000000
IMPORT_BASE = 0x60000000
IMPORT_SIZE = 0x00100000
DATA_BASE = 0x61000000
DATA_SIZE = 0x00100000
NULL_PAGE_SIZE = 0x00010000


PHASE4_PASS_SHIMS = {
    "startClet": "zero",
    "glInit": "zero",
    "threadCallback": "zero",
    "glDrawFrame": "zero",
    "getGLOptionLinear": "one",
}

IMPORT_PROBE_SHIMS = {
    "startClet": "zero",
    "threadCallback": "zero",
    "glDrawFrame": "zero",
    "getGLOptionLinear": "one",
}

PHASE5_TRACE_SHIMS = {
    "startClet": "zero",
    "threadCallback": "zero",
    "glDrawFrame": "mark-render",
    "getGLOptionLinear": "one",
}

IMPORT_FAMILY_RULES = {
    "memory": {"malloc", "free", "memset", "memcpy", "memmove"},
    "file": {"fopen", "fclose", "fread", "fwrite", "fseek", "ftell", "access", "stat", "rename", "unlink"},
    "socket": {"socket", "connect", "send", "recv", "select", "shutdown", "close", "fcntl", "inet_addr"},
    "time": {"time", "gettimeofday", "localtime", "ceil"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a desktop ARM feasibility spike against libgameDSO.so.",
    )
    parser.add_argument("--lib", type=Path, default=DEFAULT_LIB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--profile",
        choices=("phase4-pass", "import-probe", "phase5-trace"),
        default="phase4-pass",
        help="phase4-pass forces the JNI chain to return; import-probe keeps glInit live to trace imports; phase5-trace keeps GLES1 trace-only and marks first render.",
    )
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument(
        "--watch-regex",
        action="append",
        default=[],
        help="Regex for internal symbol-entry watches. May be repeated.",
    )
    parser.add_argument(
        "--watch-stage-bootstrap",
        action="store_true",
        help="Add broad stage-bootstrap watch regexes derived from the AW1 native target map.",
    )
    parser.add_argument("--max-init-count", type=int, default=200_000)
    parser.add_argument("--max-render-count", type=int, default=600_000)
    return parser.parse_args()


def align_up(value: int, align: int = PAGE_SIZE) -> int:
    return (value + align - 1) & ~(align - 1)


class ArmRunnerSpike:
    def __init__(
        self,
        lib_path: Path,
        profile: str,
        watch_regexes: list[str],
        width: int,
        height: int,
    ) -> None:
        self.lib_path = lib_path
        self.profile = profile
        self.width = width
        self.height = height
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.import_handlers: dict[int, Callable[[int], None]] = {}
        self.import_names: dict[int, str] = {}
        self.import_calls: list[dict] = []
        self.internal_handlers: dict[int, tuple[str, Callable[[int], None]]] = {}
        self.watch_patterns = [re.compile(pattern) for pattern in watch_regexes]
        self.watch_hits: Counter[str] = Counter()
        self.code_hits: Counter[str] = Counter()
        self.gl_call_histogram: Counter[str] = Counter()
        self.first_render_symbol: str | None = None
        self.render_marker_symbol: str | None = None
        self.next_import = IMPORT_BASE
        self.next_data = DATA_BASE
        self.heap_next = HEAP_BASE
        self.return_trap = IMPORT_BASE + 0xFF00
        self.stop_requested = False
        self.last_fault: dict | None = None
        self.last_trace: list[dict] = []
        self.file_handles: dict[int, dict] = {}

        self.uc.mem_map(0, NULL_PAGE_SIZE)
        for base, size in (
            (STACK_BASE, STACK_SIZE),
            (HEAP_BASE, HEAP_SIZE),
            (IMPORT_BASE, IMPORT_SIZE),
            (DATA_BASE, DATA_SIZE),
        ):
            self.uc.mem_map(base, size)

        self.uc.mem_write(self.return_trap & ~1, b"\x70\x47\x00\xbf")
        self.errno_ptr = self.alloc_data(4)
        self.stack_guard_ptr = self.alloc_data(4)
        self.write_u32(self.stack_guard_ptr, 0xA5A55A5A)

        self.load_elf()
        self.install_internal_shims()
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self.on_invalid_memory)

    def alloc_data(self, size: int) -> int:
        addr = self.next_data
        self.next_data += align_up(size, 4)
        self.uc.mem_write(addr, b"\x00" * align_up(size, 4))
        return addr

    def read_u32(self, addr: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def write_u32(self, addr: int, value: int) -> None:
        self.uc.mem_write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def safe_mem_write(self, addr: int, data: bytes) -> bool:
        try:
            self.uc.mem_write(addr, data)
            return True
        except UcError:
            return False

    def safe_mem_read(self, addr: int, size: int) -> bytes:
        try:
            return bytes(self.uc.mem_read(addr, size))
        except UcError:
            return b"\x00" * size

    def read_cstring(self, addr: int, limit: int = 512) -> str:
        out = bytearray()
        for _ in range(limit):
            chunk = self.safe_mem_read(addr, 1)
            if chunk == b"\x00":
                break
            out.extend(chunk)
            addr += 1
        return out.decode("utf-8", errors="ignore")

    def load_elf(self) -> None:
        with self.lib_path.open("rb") as fh:
            self.elf = ELFFile(fh)
            load_segments = [seg for seg in self.elf.iter_segments() if seg["p_type"] == "PT_LOAD"]
            image_size = align_up(max(seg["p_vaddr"] + seg["p_memsz"] for seg in load_segments))
            self.uc.mem_map(BASE_ADDR, image_size)
            for seg in load_segments:
                data = seg.data()
                if data:
                    self.uc.mem_write(BASE_ADDR + seg["p_vaddr"], data)

            self.dynsym = self.elf.get_section_by_name(".dynsym")
            self.symtab = self.elf.get_section_by_name(".symtab")
            self.symbols: dict[str, int] = {}
            for section in (self.symtab, self.dynsym):
                if section is None:
                    continue
                for sym in section.iter_symbols():
                    if sym.name and sym["st_info"]["type"] == "STT_FUNC" and sym["st_value"]:
                        self.symbols.setdefault(sym.name, sym["st_value"])

            self.symbol_start_map = {
                BASE_ADDR + (value & ~1): name for name, value in self.symbols.items()
            }
            self.apply_relocations()

    def install_internal_shims(self) -> None:
        profiles = {
            "phase4-pass": PHASE4_PASS_SHIMS,
            "import-probe": IMPORT_PROBE_SHIMS,
            "phase5-trace": PHASE5_TRACE_SHIMS,
        }
        shim_table = profiles[self.profile]
        for name, mode in shim_table.items():
            if name not in self.symbols:
                continue
            if mode == "one":
                handler = self.handle_one
            elif mode == "mark-render":
                handler = self.handle_mark_render
            else:
                handler = self.handle_zero
            self.internal_handlers[BASE_ADDR + (self.symbols[name] & ~1)] = (name, handler)

    def alloc_import_stub(self, name: str, handler: Callable[[int], None] | None = None) -> int:
        addr = self.next_import
        self.next_import += 4
        self.uc.mem_write(addr, b"\x70\x47\x00\xbf")
        self.import_names[addr] = name
        self.import_handlers[addr] = handler or self.stub_zero
        return addr | 1

    def resolve_symbol(self, symbol) -> int:
        name = symbol.name
        if symbol["st_shndx"] != "SHN_UNDEF" and symbol["st_value"]:
            return BASE_ADDR + symbol["st_value"]
        if name == "__stack_chk_guard":
            return self.stack_guard_ptr
        if name.startswith("gl"):
            return self.alloc_import_stub(name, self.stub_gl)
        return self.alloc_import_stub(name, self.generic_import_handler(name))

    def apply_relocations(self) -> None:
        for secname in (".rel.dyn", ".rel.plt"):
            section = self.elf.get_section_by_name(secname)
            if section is None:
                continue
            symtab = self.elf.get_section(section["sh_link"])
            for rel in section.iter_relocations():
                rtype = rel["r_info_type"]
                offset = BASE_ADDR + rel["r_offset"]
                if rtype == 23:  # R_ARM_RELATIVE
                    self.write_u32(offset, BASE_ADDR + self.read_u32(offset))
                    continue
                symbol = symtab.get_symbol(rel["r_info_sym"])
                resolved = self.resolve_symbol(symbol)
                if rtype in (21, 22):  # GLOB_DAT / JUMP_SLOT
                    self.write_u32(offset, resolved)
                elif rtype == 2:  # ABS32
                    self.write_u32(offset, (self.read_u32(offset) + resolved) & 0xFFFFFFFF)
                else:
                    raise RuntimeError(f"Unhandled relocation type {rtype} in {secname}")

    def generic_import_handler(self, name: str) -> Callable[[int], None]:
        handlers: dict[str, Callable[[int], None]] = {
            "malloc": self.stub_malloc,
            "free": self.stub_zero,
            "memset": self.stub_memset,
            "memcpy": self.stub_memcpy,
            "memmove": self.stub_memcpy,
            "strlen": self.stub_zero,
            "strcmp": self.stub_one,
            "strncmp": self.stub_one,
            "strcpy": self.stub_passthrough,
            "strncpy": self.stub_passthrough,
            "strcat": self.stub_passthrough,
            "strncat": self.stub_passthrough,
            "strstr": self.stub_zero,
            "atoi": self.stub_zero,
            "printf": self.stub_zero,
            "vprintf": self.stub_zero,
            "putchar": self.stub_putchar,
            "vsprintf": self.stub_zero,
            "fopen": self.stub_fopen,
            "fclose": self.stub_fclose,
            "fread": self.stub_fread,
            "fwrite": self.stub_fwrite,
            "fseek": self.stub_fseek,
            "ftell": self.stub_ftell,
            "access": self.stub_access,
            "stat": self.stub_stat,
            "unlink": self.stub_zero,
            "rename": self.stub_zero,
            "close": self.stub_zero,
            "fcntl": self.stub_zero,
            "socket": self.stub_neg1,
            "connect": self.stub_neg1,
            "send": self.stub_neg1,
            "recv": self.stub_neg1,
            "select": self.stub_zero,
            "shutdown": self.stub_zero,
            "inet_addr": self.stub_zero,
            "time": self.stub_const_time,
            "gettimeofday": self.stub_zero,
            "localtime": self.stub_localtime,
            "ceil": self.stub_passthrough64,
            "__errno": self.stub_errno,
            "__cxa_guard_acquire": self.stub_one,
            "__cxa_guard_release": self.stub_zero,
            "__stack_chk_fail": self.stub_zero,
            "abort": self.stub_zero,
            "__cxa_call_unexpected": self.stub_zero,
            "__cxa_begin_cleanup": self.stub_zero,
            "__cxa_type_match": self.stub_zero,
            "__gnu_Unwind_Find_exidx": self.stub_zero,
        }
        return handlers.get(name, self.stub_zero)

    def reset_stack(self) -> None:
        self.uc.reg_write(UC_ARM_REG_SP, STACK_BASE + STACK_SIZE - 0x1000)

    def call_export(self, symbol_name: str, args: tuple[int, ...], max_count: int) -> dict:
        result: dict = {
            "symbol": symbol_name,
            "passed": False,
            "returnValue": None,
            "error": None,
        }
        self.reset_stack()
        for register, value in zip(
            (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3),
            args + (0, 0, 0, 0),
        ):
            self.uc.reg_write(register, value)
        self.uc.reg_write(UC_ARM_REG_LR, self.return_trap | 1)
        self.stop_requested = False
        self.last_fault = None
        self.last_trace.clear()
        try:
            self.uc.emu_start(BASE_ADDR + self.symbols[symbol_name], self.return_trap | 1, count=max_count)
            result["passed"] = self.stop_requested
            result["returnValue"] = self.uc.reg_read(UC_ARM_REG_R0)
            if not self.stop_requested:
                result["error"] = "return-trap-not-hit"
        except UcError as exc:
            result["error"] = str(exc)
            if self.last_fault is not None:
                result["fault"] = self.last_fault
        return result

    def on_code(self, uc: Uc, address: int, size: int, user_data) -> None:
        self.last_trace.append(
            {
                "address": hex(address),
                "symbol": self.symbol_start_map.get(address),
                "lr": hex(uc.reg_read(UC_ARM_REG_LR)),
                "r0": hex(uc.reg_read(UC_ARM_REG_R0)),
                "r1": hex(uc.reg_read(UC_ARM_REG_R1)),
                "r2": hex(uc.reg_read(UC_ARM_REG_R2)),
                "r3": hex(uc.reg_read(UC_ARM_REG_R3)),
            }
        )
        self.last_trace = self.last_trace[-48:]

        if address == (self.return_trap & ~1):
            self.stop_requested = True
            uc.emu_stop()
            return

        if address in self.internal_handlers:
            name, handler = self.internal_handlers[address]
            self.code_hits[name] += 1
            self.maybe_record_watch(name)
            handler(address)
            self.return_from_hook()
            return

        if address in self.import_handlers:
            name = self.import_names[address]
            self.import_calls.append(
                {
                    "name": name,
                    "pc": hex(address),
                    "r0": hex(uc.reg_read(UC_ARM_REG_R0)),
                    "r1": hex(uc.reg_read(UC_ARM_REG_R1)),
                    "r2": hex(uc.reg_read(UC_ARM_REG_R2)),
                    "r3": hex(uc.reg_read(UC_ARM_REG_R3)),
                }
            )
            self.import_handlers[address](address)
            self.return_from_hook()
            return

        symbol_name = self.symbol_start_map.get(address)
        if symbol_name:
            self.code_hits[symbol_name] += 1
            self.maybe_record_watch(symbol_name)

    def maybe_record_watch(self, symbol_name: str) -> None:
        if any(pattern.search(symbol_name) for pattern in self.watch_patterns):
            self.watch_hits[symbol_name] += 1

    def return_from_hook(self) -> None:
        lr = self.uc.reg_read(UC_ARM_REG_LR)
        self.uc.reg_write(UC_ARM_REG_PC, lr & ~1)
        cpsr = self.uc.reg_read(UC_ARM_REG_CPSR)
        if lr & 1:
            cpsr |= 1 << 5
        else:
            cpsr &= ~(1 << 5)
        self.uc.reg_write(UC_ARM_REG_CPSR, cpsr)

    def on_invalid_memory(self, uc: Uc, access: int, address: int, size: int, value: int, user_data) -> bool:
        self.last_fault = {
            "access": access,
            "address": hex(address),
            "size": size,
            "value": hex(value) if isinstance(value, int) else value,
            "pc": hex(uc.reg_read(UC_ARM_REG_PC)),
            "lr": hex(uc.reg_read(UC_ARM_REG_LR)),
            "recentTrace": self.last_trace[-16:],
        }
        return False

    def handle_zero(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, 0)

    def handle_one(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, 1)

    def handle_mark_render(self, _address: int) -> None:
        self.render_marker_symbol = "glDrawFrame"
        if self.first_render_symbol is None:
            self.first_render_symbol = "glDrawFrame"
        self.uc.reg_write(UC_ARM_REG_R0, 0)

    def stub_zero(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, 0)

    def stub_one(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, 1)

    def stub_neg1(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, 0xFFFFFFFF)

    def stub_passthrough(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, self.uc.reg_read(UC_ARM_REG_R0))

    def stub_malloc(self, _address: int) -> None:
        size = max(self.uc.reg_read(UC_ARM_REG_R0), 4)
        ptr = self.heap_next
        self.heap_next += align_up(size, 8)
        self.safe_mem_write(ptr, b"\x00" * min(size, 0x10000))
        self.uc.reg_write(UC_ARM_REG_R0, ptr)

    def stub_memset(self, _address: int) -> None:
        dst = self.uc.reg_read(UC_ARM_REG_R0)
        value = self.uc.reg_read(UC_ARM_REG_R1) & 0xFF
        size = min(self.uc.reg_read(UC_ARM_REG_R2), 0x10000)
        self.safe_mem_write(dst, bytes([value]) * size)
        self.uc.reg_write(UC_ARM_REG_R0, dst)

    def stub_memcpy(self, _address: int) -> None:
        dst = self.uc.reg_read(UC_ARM_REG_R0)
        src = self.uc.reg_read(UC_ARM_REG_R1)
        size = min(self.uc.reg_read(UC_ARM_REG_R2), 0x10000)
        self.safe_mem_write(dst, self.safe_mem_read(src, size))
        self.uc.reg_write(UC_ARM_REG_R0, dst)

    def stub_putchar(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, self.uc.reg_read(UC_ARM_REG_R0) & 0xFF)

    def stub_fopen(self, _address: int) -> None:
        path_ptr = self.uc.reg_read(UC_ARM_REG_R0)
        mode_ptr = self.uc.reg_read(UC_ARM_REG_R1)
        guest_path = self.read_cstring(path_ptr)
        guest_mode = self.read_cstring(mode_ptr)
        host_path = Path(guest_path)
        data = b""
        if host_path.is_file():
            try:
                data = host_path.read_bytes()
            except OSError:
                data = b""
        handle_ptr = self.alloc_data(16)
        self.file_handles[handle_ptr] = {
            "path": guest_path,
            "mode": guest_mode,
            "cursor": 0,
            "data": io.BytesIO(data),
        }
        self.uc.reg_write(UC_ARM_REG_R0, handle_ptr)

    def stub_fclose(self, _address: int) -> None:
        stream_ptr = self.uc.reg_read(UC_ARM_REG_R0)
        self.file_handles.pop(stream_ptr, None)
        self.uc.reg_write(UC_ARM_REG_R0, 0)

    def stub_fread(self, _address: int) -> None:
        dst = self.uc.reg_read(UC_ARM_REG_R0)
        size = self.uc.reg_read(UC_ARM_REG_R1)
        count = self.uc.reg_read(UC_ARM_REG_R2)
        stream_ptr = self.uc.reg_read(UC_ARM_REG_R3)
        handle = self.file_handles.get(stream_ptr)
        if not handle or size == 0 or count == 0:
            self.uc.reg_write(UC_ARM_REG_R0, 0)
            return
        chunk = handle["data"].read(size * count)
        self.safe_mem_write(dst, chunk)
        self.uc.reg_write(UC_ARM_REG_R0, len(chunk) // size if size else 0)

    def stub_fwrite(self, _address: int) -> None:
        src = self.uc.reg_read(UC_ARM_REG_R0)
        size = self.uc.reg_read(UC_ARM_REG_R1)
        count = self.uc.reg_read(UC_ARM_REG_R2)
        stream_ptr = self.uc.reg_read(UC_ARM_REG_R3)
        handle = self.file_handles.get(stream_ptr)
        total = size * count
        if handle and total:
            handle["data"].write(self.safe_mem_read(src, min(total, 0x10000)))
        self.uc.reg_write(UC_ARM_REG_R0, count)

    def stub_fseek(self, _address: int) -> None:
        stream_ptr = self.uc.reg_read(UC_ARM_REG_R0)
        offset = self.uc.reg_read(UC_ARM_REG_R1)
        whence = self.uc.reg_read(UC_ARM_REG_R2)
        handle = self.file_handles.get(stream_ptr)
        if not handle:
            self.uc.reg_write(UC_ARM_REG_R0, 0xFFFFFFFF)
            return
        handle["data"].seek(offset, whence)
        self.uc.reg_write(UC_ARM_REG_R0, 0)

    def stub_ftell(self, _address: int) -> None:
        stream_ptr = self.uc.reg_read(UC_ARM_REG_R0)
        handle = self.file_handles.get(stream_ptr)
        self.uc.reg_write(UC_ARM_REG_R0, 0 if not handle else handle["data"].tell())

    def stub_access(self, _address: int) -> None:
        guest_path = self.read_cstring(self.uc.reg_read(UC_ARM_REG_R0))
        self.uc.reg_write(UC_ARM_REG_R0, 0 if Path(guest_path).exists() else 0xFFFFFFFF)

    def stub_stat(self, _address: int) -> None:
        guest_path = self.read_cstring(self.uc.reg_read(UC_ARM_REG_R0))
        self.uc.reg_write(UC_ARM_REG_R0, 0 if Path(guest_path).exists() else 0xFFFFFFFF)

    def stub_const_time(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, 1_712_000_000)

    def stub_localtime(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, self.alloc_data(64))

    def stub_passthrough64(self, _address: int) -> None:
        return

    def stub_errno(self, _address: int) -> None:
        self.uc.reg_write(UC_ARM_REG_R0, self.errno_ptr)

    def stub_gl(self, address: int) -> None:
        name = self.import_names[address]
        self.gl_call_histogram[name] += 1
        if self.first_render_symbol is None:
            self.first_render_symbol = f"gl-import:{name}"
        if name == "glGenTextures":
            count = min(self.uc.reg_read(UC_ARM_REG_R0), 16)
            out_ptr = self.uc.reg_read(UC_ARM_REG_R1)
            for index in range(count):
                self.write_u32(out_ptr + index * 4, index + 1)
        self.uc.reg_write(UC_ARM_REG_R0, 0)

    def build_report(self, init_result: dict, render_result: dict, jni_result: dict) -> dict:
        import_histogram = dict(Counter(call["name"] for call in self.import_calls).most_common())
        import_family_status = {}
        for family, names in IMPORT_FAMILY_RULES.items():
            import_family_status[family] = {
                "implemented": sorted(names),
                "observedCalls": {name: import_histogram.get(name, 0) for name in sorted(names)},
            }
        gl_imports = sorted(name for name in self.import_names.values() if name.startswith("gl"))
        import_family_status["gles1"] = {
            "implemented": gl_imports,
            "observedCalls": {name: import_histogram.get(name, 0) for name in gl_imports},
        }
        return {
            "specVersion": "aw1-desktop-runner-spike-v1",
            "profile": self.profile,
            "lib": str(self.lib_path),
            "width": self.width,
            "height": self.height,
            "activeInternalShims": sorted(name for name, _ in self.internal_handlers.values()),
            "watchPatterns": [pattern.pattern for pattern in self.watch_patterns],
            "sequence": [jni_result, init_result, render_result],
            "passedSequence": all(step["passed"] for step in (jni_result, init_result, render_result)),
            "importCallCount": len(self.import_calls),
            "importHistogram": import_histogram,
            "importFamilies": import_family_status,
            "importSamples": self.import_calls[:32],
            "glTrace": {
                "mode": "trace-only",
                "observedImportCount": sum(self.gl_call_histogram.values()),
                "observedImports": gl_imports,
                "histogram": dict(self.gl_call_histogram.most_common()),
            },
            "firstRenderReached": self.first_render_symbol is not None,
            "firstRenderSymbol": self.first_render_symbol,
            "renderMarkerReached": self.render_marker_symbol is not None,
            "renderMarkerSymbol": self.render_marker_symbol,
            "watchHits": dict(self.watch_hits.most_common()),
            "topCodeHits": dict(self.code_hits.most_common(64)),
        }


def main() -> int:
    args = parse_args()
    watch_regexes = list(args.watch_regex)
    if args.watch_stage_bootstrap:
        watch_regexes.extend(
            [
                r"Stage",
                r"Map",
                r"Story",
                r"Script",
                r"Scenario",
                r"XlsAi",
            ]
        )

    runner = ArmRunnerSpike(
        lib_path=args.lib.resolve(),
        profile=args.profile,
        watch_regexes=watch_regexes,
        width=args.width,
        height=args.height,
    )

    jni_result = runner.call_export("JNI_OnLoad", (DATA_BASE + 0x1000, 0), max_count=20_000)
    init_result = runner.call_export(
        "Java_com_gamevil_nexus2_Natives_NativeInitWithBufferSize",
        (0, 0, args.width, args.height),
        max_count=args.max_init_count,
    )
    render_result = runner.call_export(
        "Java_com_gamevil_nexus2_Natives_NativeRender",
        (0, 0),
        max_count=args.max_render_count,
    )

    report = runner.build_report(init_result=init_result, render_result=render_result, jni_result=jni_result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"profile={args.profile} "
        f"jni={jni_result['passed']} init={init_result['passed']} render={render_result['passed']} "
        f"imports={report['importCallCount']}"
    )
    print(f"report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
