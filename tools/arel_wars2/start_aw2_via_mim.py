#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIM_EXE = ROOT / "$root" / "PF" / "HD-MultiInstanceManager.exe"
DEFAULT_CACHE = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "comtypes_cache"


def matching_processes() -> list[dict[str, object]]:
    script = r"""
Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -like 'HD-*' -or
    $_.Name -like 'Bstk*' -or
    $_.Name -like 'VBox*'
  } |
  Select-Object Name,ProcessId,ParentProcessId,CommandLine |
  ConvertTo-Json -Depth 4
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        text=True,
        capture_output=True,
        timeout=20,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    data = json.loads(completed.stdout)
    if isinstance(data, dict):
        return [data]
    return data


def ensure_mim() -> None:
    if any(proc.get("Name") == "HD-MultiInstanceManager.exe" for proc in matching_processes()):
        return
    subprocess.Popen([str(MIM_EXE)], cwd=str(MIM_EXE.parent))
    time.sleep(3)


def click_button(title: str) -> bool:
    os.environ.setdefault("COMTYPES_CACHE", str(DEFAULT_CACHE))
    DEFAULT_CACHE.mkdir(parents=True, exist_ok=True)
    from pywinauto import Desktop

    win = Desktop(backend="uia").window(title="BlueStacks Multi Instance Manager")
    if not win.exists(timeout=10):
        raise RuntimeError("BlueStacks Multi Instance Manager window not found")
    button = win.child_window(title=title, control_type="Button")
    if not button.exists(timeout=5) or not button.is_enabled():
        return False
    button.click_input()
    return True


def maybe_click_continue() -> bool:
    os.environ.setdefault("COMTYPES_CACHE", str(DEFAULT_CACHE))
    from pywinauto import Desktop

    win = Desktop(backend="uia").window(title="BlueStacks")
    if not win.exists(timeout=5):
        return False
    button = win.child_window(title="Continue", control_type="Button")
    if not button.exists(timeout=2) or not button.is_enabled():
        return False
    button.click_input()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch AW2 through BlueStacks Multi Instance Manager")
    parser.add_argument("--wait-seconds", type=int, default=20)
    parser.add_argument("--skip-continue", action="store_true")
    args = parser.parse_args()

    if not MIM_EXE.exists():
        print(f"MIM_NOT_FOUND path={MIM_EXE}")
        return 1

    ensure_mim()
    clicked_start = click_button("Start")
    time.sleep(5)
    clicked_continue = False if args.skip_continue else maybe_click_continue()
    time.sleep(max(0, args.wait_seconds - 5))

    print(f"clickedStart={clicked_start}")
    print(f"clickedContinue={clicked_continue}")
    for proc in matching_processes():
        print(
            "PROC",
            f"name={proc.get('Name')}",
            f"pid={proc.get('ProcessId')}",
            f"ppid={proc.get('ParentProcessId')}",
            f"cmd={proc.get('CommandLine')}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
