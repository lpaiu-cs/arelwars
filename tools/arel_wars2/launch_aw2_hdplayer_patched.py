from __future__ import annotations

import argparse
import ctypes
import os
import struct
import sys
import time
from ctypes import wintypes
from pathlib import Path


CREATE_SUSPENDED = 0x00000004
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
INFINITE = 0xFFFFFFFF
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll", use_last_error=True)

CreateProcessW = kernel32.CreateProcessW
CreateProcessW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.BOOL,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW),
    ctypes.POINTER(PROCESS_INFORMATION),
]
CreateProcessW.restype = wintypes.BOOL

VirtualAllocEx = kernel32.VirtualAllocEx
VirtualAllocEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
    wintypes.DWORD,
]
VirtualAllocEx.restype = wintypes.LPVOID

WriteProcessMemory = kernel32.WriteProcessMemory
WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
WriteProcessMemory.restype = wintypes.BOOL

VirtualProtectEx = kernel32.VirtualProtectEx
VirtualProtectEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
VirtualProtectEx.restype = wintypes.BOOL

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
ReadProcessMemory.restype = wintypes.BOOL

ResumeThread = kernel32.ResumeThread
ResumeThread.argtypes = [wintypes.HANDLE]
ResumeThread.restype = wintypes.DWORD

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

WaitForSingleObject = kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
WaitForSingleObject.restype = wintypes.DWORD

GetExitCodeProcess = kernel32.GetExitCodeProcess
GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
GetExitCodeProcess.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
CreateToolhelp32Snapshot.restype = wintypes.HANDLE

Module32FirstW = kernel32.Module32FirstW
Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
Module32FirstW.restype = wintypes.BOOL

Module32NextW = kernel32.Module32NextW
Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
Module32NextW.restype = wintypes.BOOL


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", wintypes.LPVOID),
        ("PebBaseAddress", wintypes.LPVOID),
        ("Reserved2_0", wintypes.LPVOID),
        ("Reserved2_1", wintypes.LPVOID),
        ("UniqueProcessId", wintypes.LPVOID),
        ("Reserved3", wintypes.LPVOID),
    ]


NtQueryInformationProcess = ntdll.NtQueryInformationProcess
NtQueryInformationProcess.argtypes = [
    wintypes.HANDLE,
    wintypes.ULONG,
    wintypes.LPVOID,
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
NtQueryInformationProcess.restype = wintypes.LONG


def fail(message: str) -> None:
    raise RuntimeError(f"{message} (winerr={ctypes.get_last_error()})")


def create_process_suspended(exe_path: str, argv: list[str], cwd: str) -> PROCESS_INFORMATION:
    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    procinfo = PROCESS_INFORMATION()
    cmdline = " ".join([quote_arg(exe_path), *(quote_arg(arg) for arg in argv)])
    cmd_buf = ctypes.create_unicode_buffer(cmdline)
    ok = CreateProcessW(
        exe_path,
        cmd_buf,
        None,
        None,
        False,
        CREATE_SUSPENDED,
        None,
        cwd,
        ctypes.byref(startup),
        ctypes.byref(procinfo),
    )
    if not ok:
        fail("CreateProcessW failed")
    return procinfo


def quote_arg(arg: str) -> str:
    if not arg or any(ch.isspace() or ch == '"' for ch in arg):
        return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return arg


def find_module_base(pid: int, module_name: str) -> tuple[int, str]:
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot != wintypes.HANDLE(-1).value:
        try:
            entry = MODULEENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            ok = Module32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                if entry.szModule.lower() == module_name.lower():
                    return ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value, entry.szExePath
                ok = Module32NextW(snapshot, ctypes.byref(entry))
        finally:
            CloseHandle(snapshot)
    raise RuntimeError(f"module {module_name!r} not found in pid {pid}")


def read_process(process: wintypes.HANDLE, address: int, size: int) -> bytes:
    buf = (ctypes.c_byte * size)()
    read = ctypes.c_size_t()
    ok = ReadProcessMemory(
        process,
        ctypes.c_void_p(address),
        ctypes.byref(buf),
        size,
        ctypes.byref(read),
    )
    if not ok or read.value != size:
        fail(f"ReadProcessMemory failed at 0x{address:x}")
    return bytes(buf)


def find_image_base_from_peb(process: wintypes.HANDLE, exe_path: str) -> tuple[int, str]:
    pbi = PROCESS_BASIC_INFORMATION()
    retlen = wintypes.ULONG()
    status = NtQueryInformationProcess(
        process,
        0,
        ctypes.byref(pbi),
        ctypes.sizeof(pbi),
        ctypes.byref(retlen),
    )
    if status != 0:
        raise RuntimeError(f"NtQueryInformationProcess failed (status=0x{status & 0xFFFFFFFF:08x})")
    peb = ctypes.cast(pbi.PebBaseAddress, ctypes.c_void_p).value
    image_base = int.from_bytes(read_process(process, peb + 0x10, ctypes.sizeof(ctypes.c_void_p)), "little")
    return image_base, exe_path


def open_patch_process(pid: int) -> wintypes.HANDLE:
    handle = OpenProcess(
        PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
        False,
        pid,
    )
    if not handle:
        fail(f"OpenProcess failed for pid {pid}")
    return handle


def write_memory(process: wintypes.HANDLE, address: int, payload: bytes, *, change_protection: bool) -> None:
    old_protect = wintypes.DWORD()
    if change_protection and not VirtualProtectEx(
        process,
        ctypes.c_void_p(address),
        len(payload),
        PAGE_EXECUTE_READWRITE,
        ctypes.byref(old_protect),
    ):
        fail(f"VirtualProtectEx failed at 0x{address:x}")
    written = ctypes.c_size_t()
    src = ctypes.create_string_buffer(payload)
    try:
        ok = WriteProcessMemory(
            process,
            ctypes.c_void_p(address),
            ctypes.byref(src),
            len(payload),
            ctypes.byref(written),
        )
        if not ok or written.value != len(payload):
            fail(f"WriteProcessMemory failed at 0x{address:x}")
    finally:
        if change_protection:
            restored = wintypes.DWORD()
            if not VirtualProtectEx(
                process,
                ctypes.c_void_p(address),
                len(payload),
                old_protect.value,
                ctypes.byref(restored),
            ):
                fail(f"VirtualProtectEx restore failed at 0x{address:x}")


def alloc_remote_string(process: wintypes.HANDLE, value: str) -> int:
    raw = value.encode("utf-16le") + b"\x00\x00"
    remote = VirtualAllocEx(process, None, len(raw), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not remote:
        fail("VirtualAllocEx failed")
    write_memory(process, ctypes.cast(remote, ctypes.c_void_p).value, raw, change_protection=False)
    return ctypes.cast(remote, ctypes.c_void_p).value


def make_wstring_blob(process: wintypes.HANDLE, value: str) -> bytes:
    encoded = value.encode("utf-16le")
    length = len(value)
    if length <= 7:
        inline = (encoded + b"\x00\x00").ljust(16, b"\x00")
        return inline + length.to_bytes(8, "little") + (7).to_bytes(8, "little")
    remote = alloc_remote_string(process, value)
    return (
        remote.to_bytes(8, "little")
        + b"\x00" * 8
        + length.to_bytes(8, "little")
        + length.to_bytes(8, "little")
    )


def patch_globals(process: wintypes.HANDLE, base: int, values: dict[int, str]) -> None:
    for offset, value in values.items():
        blob = make_wstring_blob(process, value)
        write_memory(process, base + offset, blob, change_protection=False)


def patch_datadir_skip_init(process: wintypes.HANDLE, base: int) -> None:
    src = base + 0x4FA398
    dst = base + 0x4FA29F
    rel = dst - (src + 5)
    payload = b"\xE9" + struct.pack("<i", rel) + b"\x90" * 4
    write_memory(process, src, payload, change_protection=True)


def wait_exit_code(process: wintypes.HANDLE, timeout_ms: int) -> int | None:
    state = WaitForSingleObject(process, timeout_ms)
    if state == WAIT_TIMEOUT:
        return None
    if state != WAIT_OBJECT_0:
        fail("WaitForSingleObject failed")
    code = wintypes.DWORD()
    if not GetExitCodeProcess(process, ctypes.byref(code)):
        fail("GetExitCodeProcess failed")
    return ctypes.c_int32(code.value).value


def run(args: argparse.Namespace) -> int:
    os.environ["HOME"] = args.home
    os.environ["VBOX_APP_HOME"] = args.vbox_app_home
    os.environ["VBOX_USER_HOME"] = args.vbox_user_home
    os.environ["TEMP"] = args.temp_dir
    os.environ["TMP"] = args.temp_dir

    procinfo = create_process_suspended(args.exe, args.arg, args.cwd)
    patch_process = None
    try:
        try:
            base, exe_path = find_module_base(procinfo.dwProcessId, Path(args.exe).name)
        except RuntimeError:
            base, exe_path = find_image_base_from_peb(procinfo.hProcess, args.exe)
        patch_process = open_patch_process(procinfo.dwProcessId)
        values = {
            0x1A02520: args.install_dir,
            0x1A02548: args.data_dir,
            0x1A025F8: args.common_app_data,
        }
        patch_globals(patch_process, base, values)
        if args.patch_datadir_skip_init:
            patch_datadir_skip_init(patch_process, base)

        if ResumeThread(procinfo.hThread) == 0xFFFFFFFF:
            fail("ResumeThread failed")

        deadline = time.time() + args.repump_seconds
        while time.time() < deadline:
            code = wait_exit_code(procinfo.hProcess, 0)
            if code is not None:
                print(f"EXIT pid={procinfo.dwProcessId} code={code}")
                print(f"base=0x{base:x}")
                print(f"exe={exe_path}")
                return code
            patch_globals(patch_process, base, values)
            if args.patch_datadir_skip_init:
                patch_datadir_skip_init(patch_process, base)
            if args.repump_interval_ms > 0:
                time.sleep(args.repump_interval_ms / 1000.0)

        code = wait_exit_code(procinfo.hProcess, args.wait_ms)
        if code is None:
            print(f"RUNNING pid={procinfo.dwProcessId}")
            print(f"base=0x{base:x}")
            print(f"exe={exe_path}")
            return 0
        print(f"EXIT pid={procinfo.dwProcessId} code={code}")
        print(f"base=0x{base:x}")
        print(f"exe={exe_path}")
        return code
    finally:
        if patch_process:
            CloseHandle(patch_process)
        if procinfo.hThread:
            CloseHandle(procinfo.hThread)
        if procinfo.hProcess:
            CloseHandle(procinfo.hProcess)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch HD-Player suspended and patch AW2 BlueStacks dir globals before resume."
    )
    parser.add_argument(
        "--exe",
        default=r"C:\vs\other\arelwars\$root\PF\HD-Player.exe",
    )
    parser.add_argument(
        "--cwd",
        default=r"C:\vs\other\arelwars\$root\PF",
    )
    parser.add_argument(
        "--arg",
        action="append",
        default=["--instance", "Nougat32", "--hidden"],
        help="repeatable process arguments",
    )
    parser.add_argument(
        "--install-dir",
        default=r"C:\vs\other\arelwars\$root\PF",
    )
    parser.add_argument(
        "--data-dir",
        default=r"C:\ProgramData\BlueStacks_nxt",
    )
    parser.add_argument(
        "--common-app-data",
        default=r"C:\ProgramData",
    )
    parser.add_argument(
        "--home",
        default=r"C:\Users\lpaiu",
    )
    parser.add_argument(
        "--vbox-user-home",
        default=r"C:\ProgramData\BlueStacks_nxt\Manager",
    )
    parser.add_argument(
        "--vbox-app-home",
        default=r"C:\ProgramData\BlueStacks_nxt",
    )
    parser.add_argument(
        "--temp-dir",
        default=r"C:\Users\lpaiu\AppData\Local\Temp",
    )
    parser.add_argument(
        "--repump-seconds",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--wait-ms",
        type=int,
        default=10000,
    )
    parser.add_argument(
        "--repump-interval-ms",
        type=float,
        default=100.0,
    )
    parser.add_argument(
        "--patch-datadir-skip-init",
        action="store_true",
    )
    return parser


if __name__ == "__main__":
    try:
        raise SystemExit(run(build_parser().parse_args()))
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise
