from __future__ import annotations

import argparse
import ctypes
import importlib.util
import struct
from ctypes import wintypes
from pathlib import Path


DEBUG_ONLY_THIS_PROCESS = 0x00000002
INFINITE = 0xFFFFFFFF
DBG_CONTINUE = 0x00010002
EXCEPTION_DEBUG_EVENT = 1
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_PROCESS_DEBUG_EVENT = 5
LOAD_DLL_DEBUG_EVENT = 6
OUTPUT_DEBUG_STRING_EVENT = 8
EXCEPTION_BREAKPOINT = 0x80000003
STATUS_ACCESS_VIOLATION = 0xC0000005
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010


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


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [
        ("ExceptionCode", wintypes.DWORD),
        ("ExceptionFlags", wintypes.DWORD),
        ("ExceptionRecord", wintypes.LPVOID),
        ("ExceptionAddress", wintypes.LPVOID),
        ("NumberParameters", wintypes.DWORD),
        ("ExceptionInformation", ctypes.c_uint64 * 15),
    ]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("ExceptionRecord", EXCEPTION_RECORD),
        ("dwFirstChance", wintypes.DWORD),
    ]


class CREATE_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hFile", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("lpBaseOfImage", wintypes.LPVOID),
        ("dwDebugInfoFileOffset", wintypes.DWORD),
        ("nDebugInfoSize", wintypes.DWORD),
        ("lpThreadLocalBase", wintypes.LPVOID),
        ("lpStartAddress", wintypes.LPVOID),
        ("lpImageName", wintypes.LPVOID),
        ("fUnicode", wintypes.WORD),
    ]


class EXIT_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("dwExitCode", wintypes.DWORD)]


class LOAD_DLL_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hFile", wintypes.HANDLE),
        ("lpBaseOfDll", wintypes.LPVOID),
        ("dwDebugInfoFileOffset", wintypes.DWORD),
        ("nDebugInfoSize", wintypes.DWORD),
        ("lpImageName", wintypes.LPVOID),
        ("fUnicode", wintypes.WORD),
    ]


class OUTPUT_DEBUG_STRING_INFO(ctypes.Structure):
    _fields_ = [
        ("lpDebugStringData", wintypes.LPVOID),
        ("fUnicode", wintypes.WORD),
        ("nDebugStringLength", wintypes.WORD),
    ]


class DEBUG_EVENT_UNION(ctypes.Union):
    _fields_ = [
        ("Exception", EXCEPTION_DEBUG_INFO),
        ("CreateProcessInfo", CREATE_PROCESS_DEBUG_INFO),
        ("ExitProcess", EXIT_PROCESS_DEBUG_INFO),
        ("LoadDll", LOAD_DLL_DEBUG_INFO),
        ("DebugString", OUTPUT_DEBUG_STRING_INFO),
    ]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
        ("u", DEBUG_EVENT_UNION),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

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

WaitForDebugEvent = kernel32.WaitForDebugEvent
WaitForDebugEvent.argtypes = [ctypes.POINTER(DEBUG_EVENT), wintypes.DWORD]
WaitForDebugEvent.restype = wintypes.BOOL

ContinueDebugEvent = kernel32.ContinueDebugEvent
ContinueDebugEvent.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
ContinueDebugEvent.restype = wintypes.BOOL

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
ReadProcessMemory.restype = wintypes.BOOL

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


def load_patch_module():
    patch_path = Path(__file__).with_name("launch_aw2_hdplayer_patched.py")
    spec = importlib.util.spec_from_file_location("launch_aw2_hdplayer_patched", patch_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def quote_arg(arg: str) -> str:
    if not arg or any(ch.isspace() or ch == '"' for ch in arg):
        return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return arg


def find_module_for_address(pid: int, address: int) -> tuple[str, int, int] | None:
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == wintypes.HANDLE(-1).value:
        return None
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = Module32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
            size = int(entry.modBaseSize)
            if base <= address < base + size:
                return entry.szModule, base, size
            ok = Module32NextW(snapshot, ctypes.byref(entry))
    finally:
        CloseHandle(snapshot)
    return None


def read_bytes(process: wintypes.HANDLE, address: int, size: int) -> bytes:
    buf = (ctypes.c_ubyte * size)()
    read = ctypes.c_size_t()
    ok = ReadProcessMemory(process, ctypes.c_void_p(address), ctypes.byref(buf), size, ctypes.byref(read))
    if not ok:
        return b""
    return bytes(buf[: read.value])


def query_process_exit(process: wintypes.HANDLE) -> int | None:
    state = WaitForSingleObject(process, 0)
    if state != 0:
        return None
    code = wintypes.DWORD()
    if not GetExitCodeProcess(process, ctypes.byref(code)):
        return None
    return ctypes.c_int32(code.value).value


def patch_bootstrap_state(patch_module, process: wintypes.HANDLE, base: int) -> None:
    patch_module.write_memory(process, base + 0x1A02540, (0).to_bytes(4, "little"), change_protection=False)
    patch_module.write_memory(process, base + 0x1A02568, (0).to_bytes(4, "little"), change_protection=False)


def patch_datadir_to_installdir(patch_module, process: wintypes.HANDLE, base: int) -> None:
    src = base + 0x4FA240
    dst = base + 0x4FFDA0
    rel = dst - (src + 5)
    payload = b"\xE9" + struct.pack("<i", rel)
    patch_module.write_memory(process, src, payload, change_protection=True)


def patch_datadir_skip_init(patch_module, process: wintypes.HANDLE, base: int) -> None:
    src = base + 0x4FA398
    dst = base + 0x4FA29F
    rel = dst - (src + 5)
    payload = b"\xE9" + struct.pack("<i", rel) + b"\x90" * 4
    patch_module.write_memory(process, src, payload, change_protection=True)


def run(args: argparse.Namespace) -> int:
    patch = load_patch_module()
    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    procinfo = PROCESS_INFORMATION()
    cmdline = " ".join([quote_arg(args.exe), *(quote_arg(arg) for arg in args.arg)])
    cmd_buf = ctypes.create_unicode_buffer(cmdline)
    ok = CreateProcessW(
        args.exe,
        cmd_buf,
        None,
        None,
        False,
        DEBUG_ONLY_THIS_PROCESS,
        None,
        args.cwd,
        ctypes.byref(startup),
        ctypes.byref(procinfo),
    )
    if not ok:
        raise OSError(ctypes.get_last_error(), "CreateProcessW failed")

    patch_handle = None
    base = None
    first_breakpoint_seen = False
    values = {
        0x1A02520: args.install_dir,
        0x1A02548: args.data_dir,
        0x1A025F8: args.common_app_data,
    }
    try:
        while True:
            event = DEBUG_EVENT()
            if not WaitForDebugEvent(ctypes.byref(event), args.timeout_ms):
                last_error = ctypes.get_last_error()
                exit_code = query_process_exit(procinfo.hProcess)
                if exit_code is not None:
                    print(f"TIMEOUT_EXIT code={exit_code}")
                    return exit_code
                print(f"TIMEOUT_NO_EVENT winerr={last_error}")
                return 2

            status = DBG_CONTINUE
            try:
                if event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT:
                    base = ctypes.cast(event.u.CreateProcessInfo.lpBaseOfImage, ctypes.c_void_p).value
                    patch_handle = patch.open_patch_process(event.dwProcessId)
                    patch.patch_globals(patch_handle, base, values)
                    patch_bootstrap_state(patch, patch_handle, base)
                    if args.patch_datadir_to_installdir:
                        patch_datadir_to_installdir(patch, patch_handle, base)
                    if args.patch_datadir_skip_init:
                        patch_datadir_skip_init(patch, patch_handle, base)
                    print(f"CREATE_PROCESS pid={event.dwProcessId} base=0x{base:x}")
                    if event.u.CreateProcessInfo.hFile:
                        CloseHandle(event.u.CreateProcessInfo.hFile)
                elif event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
                    code = event.u.Exception.ExceptionRecord.ExceptionCode
                    address = ctypes.cast(event.u.Exception.ExceptionRecord.ExceptionAddress, ctypes.c_void_p).value
                    if code == EXCEPTION_BREAKPOINT and not first_breakpoint_seen:
                        first_breakpoint_seen = True
                        if patch_handle and base:
                            patch.patch_globals(patch_handle, base, values)
                            patch_bootstrap_state(patch, patch_handle, base)
                            if args.patch_datadir_to_installdir:
                                patch_datadir_to_installdir(patch, patch_handle, base)
                            if args.patch_datadir_skip_init:
                                patch_datadir_skip_init(patch, patch_handle, base)
                        print(f"INITIAL_BREAKPOINT addr=0x{address:x}")
                    elif code == STATUS_ACCESS_VIOLATION:
                        print(f"ACCESS_VIOLATION addr=0x{address:x}")
                        module = find_module_for_address(event.dwProcessId, address)
                        if module is None:
                            print("faultModule=<unknown>")
                        else:
                            module_name, module_base, module_size = module
                            print(
                                f"faultModule={module_name} base=0x{module_base:x} "
                                f"offset=0x{address - module_base:x} size=0x{module_size:x}"
                            )
                        info = event.u.Exception.ExceptionRecord.ExceptionInformation
                        print(
                            "exceptionInfo="
                            f"{int(info[0])},{int(info[1])},"
                            f"{int(info[2])},{int(info[3])}"
                        )
                        if patch_handle and base:
                            for offset, name in (
                                (0x1A02520, "installDir"),
                                (0x1A02548, "dataDir"),
                                (0x1A025F8, "commonAppData"),
                            ):
                                raw = read_bytes(patch_handle, base + offset, 32)
                                print(f"{name}@0x{base + offset:x}={raw.hex()}")
                            for offset, name in (
                                (0x1A02540, "installDirState"),
                                (0x1A02568, "dataDirState"),
                            ):
                                raw = read_bytes(patch_handle, base + offset, 4)
                                print(f"{name}@0x{base + offset:x}={raw.hex()}")
                        return 1
                elif event.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT:
                    if patch_handle and base and args.repatch_on_load_dll:
                        patch.patch_globals(patch_handle, base, values)
                        patch_bootstrap_state(patch, patch_handle, base)
                        if args.patch_datadir_to_installdir:
                            patch_datadir_to_installdir(patch, patch_handle, base)
                        if args.patch_datadir_skip_init:
                            patch_datadir_skip_init(patch, patch_handle, base)
                    if event.u.LoadDll.hFile:
                        CloseHandle(event.u.LoadDll.hFile)
                elif event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
                    print(f"EXIT_PROCESS code={ctypes.c_int32(event.u.ExitProcess.dwExitCode).value}")
                    return ctypes.c_int32(event.u.ExitProcess.dwExitCode).value
                elif patch_handle and base and args.repatch_each_event:
                    patch.patch_globals(patch_handle, base, values)
                    patch_bootstrap_state(patch, patch_handle, base)
                    if args.patch_datadir_to_installdir:
                        patch_datadir_to_installdir(patch, patch_handle, base)
                    if args.patch_datadir_skip_init:
                        patch_datadir_skip_init(patch, patch_handle, base)
            finally:
                if not ContinueDebugEvent(event.dwProcessId, event.dwThreadId, status):
                    raise OSError(ctypes.get_last_error(), "ContinueDebugEvent failed")
    finally:
        if patch_handle:
            CloseHandle(patch_handle)
        if procinfo.hThread:
            CloseHandle(procinfo.hThread)
        if procinfo.hProcess:
            CloseHandle(procinfo.hProcess)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug-launch AW2 HD-Player and inspect early bootstrap crashes.")
    parser.add_argument("--exe", default=r"C:\vs\other\arelwars\$root\PF\HD-Player.exe")
    parser.add_argument("--cwd", default=r"C:\vs\other\arelwars\$root\PF")
    parser.add_argument("--arg", action="append", default=["--instance", "Nougat32", "--hidden"])
    parser.add_argument("--install-dir", default=r"C:\vs\other\arelwars\$root\PF")
    parser.add_argument("--data-dir", default=r"C:\ProgramData\BlueStacks_nxt")
    parser.add_argument("--common-app-data", default=r"C:\ProgramData")
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--repatch-each-event", action="store_true")
    parser.add_argument("--repatch-on-load-dll", action="store_true")
    parser.add_argument("--patch-datadir-to-installdir", action="store_true")
    parser.add_argument("--patch-datadir-skip-init", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
