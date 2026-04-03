#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pywintypes
import win32file
import win32pipe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipe-name", default="launcher_bridge")
    parser.add_argument(
        "--log",
        default=r"C:\ProgramData\BlueStacks_nxt\Logs\launcher_bridge_stub.log",
    )
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--read-size", type=int, default=4096)
    return parser.parse_args()


def append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def main() -> int:
    args = parse_args()
    log_path = Path(args.log)
    pipe_path = rf"\\.\pipe\{args.pipe_name}"
    append_log(log_path, f"SERVER_START pipe={pipe_path} timeout={args.timeout_seconds}")

    pipe = win32pipe.CreateNamedPipe(
        pipe_path,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
        1,
        args.read_size,
        args.read_size,
        0,
        None,
    )
    try:
        try:
            win32pipe.ConnectNamedPipe(pipe, None)
            append_log(log_path, "CONNECTED")
        except pywintypes.error as exc:
            if exc.winerror != 535:
                append_log(log_path, f"CONNECT_ERROR winerror={exc.winerror} func={exc.func} msg={exc.strerror}")
                return 1
            append_log(log_path, "CONNECTED_ALREADY")

        deadline = time.time() + args.timeout_seconds
        while time.time() < deadline:
            try:
                _, data = win32file.ReadFile(pipe, args.read_size, None)
            except pywintypes.error as exc:
                if exc.winerror in (109, 232):
                    append_log(log_path, f"DISCONNECTED winerror={exc.winerror}")
                    return 0
                if exc.winerror == 121:
                    time.sleep(0.05)
                    continue
                append_log(log_path, f"READ_ERROR winerror={exc.winerror} func={exc.func} msg={exc.strerror}")
                return 1
            if data:
                append_log(log_path, f"READ len={len(data)} hex={data.hex()}")
        append_log(log_path, "TIMEOUT")
        return 0
    finally:
        try:
            win32file.CloseHandle(pipe)
        except Exception:
            pass
        append_log(log_path, "SERVER_END")


if __name__ == "__main__":
    raise SystemExit(main())
