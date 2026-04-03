#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SERIAL = "emulator-5554"
DEFAULT_PACKAGE = "com.gamevil.ArelWars2.global"
DEFAULT_BOOTSTRAP_PACKAGE = "com.gamevil.ArelWars2.global.bootstrap"
DEFAULT_ACTIVITY = f"{DEFAULT_PACKAGE}/com.gamevil.ArelWars2.global.DRMLicensing"


def run(command: list[str], *, timeout: int = 30, check: bool = True) -> str:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        timeout=timeout,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def adb(serial: str, *args: str, timeout: int = 30, check: bool = True) -> str:
    return run(["adb", "-s", serial, *args], timeout=timeout, check=check)


def adb_shell(serial: str, command: str, *, timeout: int = 30, check: bool = True) -> str:
    return adb(serial, "shell", command, timeout=timeout, check=check)


def capture_ui(serial: str, target: Path) -> str:
    xml = adb(serial, "exec-out", "uiautomator", "dump", "/dev/tty", timeout=30)
    target.write_text(xml, encoding="utf-8")
    return xml


def capture_png(serial: str, target: Path) -> None:
    with target.open("wb") as handle:
        subprocess.run(
            ["adb", "-s", serial, "exec-out", "screencap", "-p"],
            cwd=REPO_ROOT,
            timeout=30,
            check=True,
            stdout=handle,
        )


def read_resumed_activity(serial: str) -> str:
    output = adb_shell(
        serial,
        "dumpsys activity activities",
        timeout=30,
    )
    for line in output.splitlines():
        if "mResumedActivity" in line:
            return line.strip()
    return ""


def read_focus(serial: str) -> str:
    output = adb_shell(
        serial,
        "dumpsys window windows",
        timeout=30,
    )
    for line in output.splitlines():
        if "mCurrentFocus=" in line:
            return line.strip()
    return ""


def parse_texts(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    texts: list[str] = []
    for node in root.iter("node"):
        text = node.attrib.get("text")
        if text:
            texts.append(text)
    return texts


def has_text(xml_text: str, needle: str) -> bool:
    return any(needle in text for text in parse_texts(xml_text))


def tap(serial: str, x: int, y: int) -> None:
    adb_shell(serial, f"input tap {x} {y}", timeout=15)


def swipe(serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
    adb_shell(serial, f"input swipe {x1} {y1} {x2} {y2} {duration_ms}", timeout=15)


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def maybe_disable_bootstrap(serial: str, bootstrap_package: str, disable: bool) -> str:
    if not disable:
        return "left-enabled"
    return adb_shell(serial, f"pm disable-user --user 0 {bootstrap_package}", timeout=30, check=False).strip()


def maybe_enable_bootstrap(serial: str, bootstrap_package: str, disable: bool) -> str:
    if not disable:
        return "left-enabled"
    return adb_shell(serial, f"pm enable {bootstrap_package}", timeout=30, check=False).strip()


def dump_step(serial: str, output_dir: Path, name: str) -> dict[str, str]:
    ui_path = output_dir / f"{name}.xml"
    png_path = output_dir / f"{name}.png"
    xml_text = capture_ui(serial, ui_path)
    capture_png(serial, png_path)
    return {
        "name": name,
        "uiPath": str(ui_path),
        "pngPath": str(png_path),
        "resumedActivity": read_resumed_activity(serial),
        "focusedWindow": read_focus(serial),
        "texts": parse_texts(xml_text),
    }


def choose_original_if_needed(serial: str) -> bool:
    xml = adb(serial, "exec-out", "uiautomator", "dump", "/dev/tty", timeout=30)
    if "Open with" not in xml:
        return False
    tap(serial, 360, 1133)
    sleep(0.8)
    tap(serial, 506, 1228)
    sleep(2.5)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the original AW2 first scene after DRM.")
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--activity", default=DEFAULT_ACTIVITY)
    parser.add_argument("--bootstrap-package", default=DEFAULT_BOOTSTRAP_PACKAGE)
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "recovery" / "arel_wars2" / "native_tmp" / "oracle" / "first-scene-v1"),
    )
    parser.add_argument(
        "--disable-bootstrap",
        action="store_true",
        help="Temporarily disable the bootstrap package to avoid the chooser.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    adb(args.serial, "logcat", "-c")
    disable_result = maybe_disable_bootstrap(args.serial, args.bootstrap_package, args.disable_bootstrap)
    adb(args.serial, "shell", "am", "force-stop", args.package)
    adb(args.serial, "shell", "am", "start", "-W", "-n", args.activity, timeout=60)
    sleep(2.0)

    steps: list[dict[str, str]] = []
    steps.append(dump_step(args.serial, output_dir, "01_initial_drm"))

    for _ in range(6):
        swipe(args.serial, 360, 950, 360, 380, 250)
        sleep(0.5)
    steps.append(dump_step(args.serial, output_dir, "02_scrolled_drm"))

    tap(args.serial, 360, 1216)
    sleep(1.0)
    steps.append(dump_step(args.serial, output_dir, "03_terms_dialog"))

    if has_text(Path(steps[-1]["uiPath"]).read_text(encoding="utf-8"), "약관 동의"):
        tap(args.serial, 361, 723)
        sleep(0.8)

    tap(args.serial, 54, 1112)
    sleep(0.5)
    tap(args.serial, 360, 1216)
    sleep(1.0)
    steps.append(dump_step(args.serial, output_dir, "04_start_dialog"))

    if has_text(Path(steps[-1]["uiPath"]).read_text(encoding="utf-8"), "감사합니다."):
        tap(args.serial, 360, 772)
        sleep(1.5)

    chooser_seen = choose_original_if_needed(args.serial)
    sleep(3.0)
    steps.append(dump_step(args.serial, output_dir, "05_post_start"))

    activity = read_resumed_activity(args.serial)
    focus = read_focus(args.serial)
    logcat_path = output_dir / "logcat.txt"
    logcat = adb(args.serial, "logcat", "-d", "-v", "time", timeout=60)
    logcat_path.write_text(logcat, encoding="utf-8")
    enable_result = maybe_enable_bootstrap(args.serial, args.bootstrap_package, args.disable_bootstrap)

    session = {
        "serial": args.serial,
        "package": args.package,
        "activity": args.activity,
        "bootstrapPackage": args.bootstrap_package,
        "disableBootstrap": args.disable_bootstrap,
        "disableBootstrapResult": disable_result,
        "enableBootstrapResult": enable_result,
        "chooserSeen": chooser_seen,
        "finalResumedActivity": activity,
        "finalFocusedWindow": focus,
        "steps": steps,
        "logcatPath": str(logcat_path),
    }
    (output_dir / "session.json").write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(session, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
