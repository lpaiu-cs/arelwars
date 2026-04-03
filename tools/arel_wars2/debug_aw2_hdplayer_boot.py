from __future__ import annotations

import argparse
import ctypes
import importlib.util
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

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


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


def read_bytes(process: wintypes.HANDLE, address: int, size: int) -> bytes:
    buf = (ctypes.c_ubyte * size)()
    read = ctypes.c_size_t()
    ok = ReadProcessMemory(process, ctypes.c_void_p(address), ctypes.byref(buf), size, ctypes.byref(read))
    if not ok:
        return b""
    return bytes(buf[: read.value])


def patch_bootstrap_state(patch_module, process: wintypes.HANDLE, base: int) -> None:
    patch_module.write_memory(process, base + 0x1A02540, (0).to_bytes(4, "little"), change_protection=False)
    patch_module.write_memory(process, base + 0x1A02568, (0).to_bytes(4, "little"), change_protection=False)


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
                raise OSError(ctypes.get_last_error(), "WaitForDebugEvent failed")

            status = DBG_CONTINUE
            try:
                if event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT:
                    base = ctypes.cast(event.u.CreateProcessInfo.lpBaseOfImage, ctypes.c_void_p).value
                    patch_handle = patch.open_patch_process(event.dwProcessId)
                    patch.patch_globals(patch_handle, base, values)
                    patch_bootstrap_state(patch, patch_handle, base)
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
                        print(f"INITIAL_BREAKPOINT addr=0x{address:x}")
                    elif code == STATUS_ACCESS_VIOLATION:
                        print(f"ACCESS_VIOLATION addr=0x{address:x}")
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
                    if event.u.LoadDll.hFile:
                        CloseHandle(event.u.LoadDll.hFile)
                elif event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
                    print(f"EXIT_PROCESS code={ctypes.c_int32(event.u.ExitProcess.dwExitCode).value}")
                    return ctypes.c_int32(event.u.ExitProcess.dwExitCode).value
                elif patch_handle and base and args.repatch_each_event:
                    patch.patch_globals(patch_handle, base, values)
                    patch_bootstrap_state(patch, patch_handle, base)
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
    parser.add_argument("--install-dir", default="B:\\")
    parser.add_argument("--data-dir", default="P:\\")
    parser.add_argument("--common-app-data", default="Q:\\")
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--repatch-each-event", action="store_true")
    parser.add_argument("--repatch-on-load-dll", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
