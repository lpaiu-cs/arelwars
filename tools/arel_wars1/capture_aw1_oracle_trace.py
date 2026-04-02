#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Any


DEFAULT_PACKAGE = "com.gamevil.eruelwars.global"
SPEC_VERSION = "aw1-oracle-capture-v1"
DEFAULT_SAVE_ROOTS = [
    "/sdcard/Android/data/{package}",
    "/sdcard/Android/data/{package}/files",
    "/sdcard/{package}",
    "/sdcard/gamevil",
    "/sdcard/Gamevil",
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_command(
    cmd: list[str],
    *,
    check: bool = True,
    text: bool = True,
    timeout: float | None = None,
    capture_output: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        text=text,
        timeout=timeout,
        capture_output=capture_output,
        input=input_text,
    )


def adb_prefix(serial: str | None) -> list[str]:
    prefix = ["adb"]
    if serial:
        prefix.extend(["-s", serial])
    return prefix


def adb(
    serial: str | None,
    *args: str,
    check: bool = True,
    text: bool = True,
    timeout: float | None = None,
    capture_output: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    return run_command(
        adb_prefix(serial) + list(args),
        check=check,
        text=text,
        timeout=timeout,
        capture_output=capture_output,
        input_text=input_text,
    )


def adb_shell(
    serial: str | None,
    command: str,
    *,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    return adb(serial, "shell", "sh", "-c", command, check=check, timeout=timeout)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dir(path: pathlib.Path) -> pathlib.Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify_remote_path(path: str) -> str:
    return path.lstrip("/").replace("/", "__").replace(":", "_")


def list_devices() -> list[dict[str, Any]]:
    proc = run_command(["adb", "devices", "-l"], check=True, text=True)
    devices: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        extras: dict[str, str] = {}
        for item in parts[2:]:
            if ":" in item:
                key, value = item.split(":", 1)
                extras[key] = value
        devices.append(
            {
                "serial": serial,
                "state": state,
                "extras": extras,
            }
        )
    return devices


def choose_serial(requested: str | None) -> str | None:
    if requested:
        return requested
    devices = [device for device in list_devices() if device["state"] == "device"]
    if len(devices) == 1:
        return devices[0]["serial"]
    if not devices:
        raise RuntimeError("No adb device is connected.")
    raise RuntimeError("Multiple adb devices are connected. Pass --serial explicitly.")


def get_prop(serial: str | None, key: str) -> str:
    return adb(serial, "shell", "getprop", key, timeout=10).stdout.strip()


def get_package_path(serial: str | None, package: str) -> str | None:
    proc = adb(serial, "shell", "pm", "path", package, check=False, timeout=10)
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            return line.replace("package:", "", 1)
    return None


def pull_installed_base_apk(
    serial: str | None,
    package: str,
    destination: pathlib.Path,
) -> dict[str, Any]:
    package_path = get_package_path(serial, package)
    if not package_path:
        return {
            "installed": False,
            "packagePath": None,
            "pulledPath": None,
            "sha256": None,
        }
    ensure_dir(destination.parent)
    adb(serial, "pull", package_path, str(destination), timeout=60)
    return {
        "installed": True,
        "packagePath": package_path,
        "pulledPath": str(destination),
        "sha256": sha256_file(destination),
    }


def detect_run_as(serial: str | None, package: str) -> dict[str, Any]:
    proc = adb(serial, "shell", "run-as", package, "id", check=False, timeout=10)
    return {
        "available": proc.returncode == 0,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def detect_su(serial: str | None) -> dict[str, Any]:
    proc = adb(serial, "shell", "su", "-c", "id", check=False, timeout=10)
    stdout = proc.stdout.strip()
    return {
        "available": proc.returncode == 0 and "uid=0" in stdout,
        "stdout": stdout,
        "stderr": proc.stderr.strip(),
    }


def detect_jni_trace_backend(serial: str | None, package: str) -> dict[str, Any]:
    command = [
        "shell",
        "cmd",
        "activity",
        "profile",
        "start",
        "--sampling",
        "1000",
        package,
        "/data/local/tmp/aw1_profile_probe.prof",
    ]
    proc = adb(serial, *command, check=False, timeout=10)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    available = proc.returncode == 0
    reason = ""
    if not available:
        combined = "\n".join(part for part in [stdout, stderr] if part)
        if "not debuggable, and not profileable by shell" in combined:
            reason = "package-is-not-debuggable-or-profileable-by-shell"
        elif combined:
            reason = combined
        else:
            reason = "unknown-profile-backend-failure"
    else:
        adb(serial, "shell", "cmd", "activity", "profile", "stop", package, check=False, timeout=10)
    return {
        "backend": "shell-profile",
        "available": available,
        "reason": reason or None,
        "stdout": stdout,
        "stderr": stderr,
    }


def candidate_save_roots(package: str) -> list[str]:
    return [root.format(package=package) for root in DEFAULT_SAVE_ROOTS]


def detect_existing_paths(serial: str | None, paths: list[str]) -> list[str]:
    found: list[str] = []
    for path in paths:
        proc = adb_shell(serial, f'if [ -e "{path}" ]; then echo "{path}"; fi', check=False, timeout=10)
        value = proc.stdout.strip()
        if value:
            found.append(value)
    return found


def list_remote_files(serial: str | None, paths: list[str]) -> list[str]:
    files: list[str] = []
    for path in paths:
        command = f'if [ -f "{path}" ]; then echo "{path}"; elif [ -d "{path}" ]; then find "{path}" -type f; fi'
        proc = adb_shell(serial, command, check=False, timeout=20)
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                files.append(line)
    return sorted(set(files))


def pull_remote_file(serial: str | None, remote_path: str, local_path: pathlib.Path) -> None:
    ensure_dir(local_path.parent)
    adb(serial, "pull", remote_path, str(local_path), timeout=60)


def snapshot_save_files(
    serial: str | None,
    package: str,
    output_dir: pathlib.Path,
) -> dict[str, Any]:
    roots = detect_existing_paths(serial, candidate_save_roots(package))
    files = list_remote_files(serial, roots)
    pulled: list[dict[str, Any]] = []
    files_dir = ensure_dir(output_dir / "files")
    for remote_path in files:
        local_path = files_dir / slugify_remote_path(remote_path)
        pull_remote_file(serial, remote_path, local_path)
        pulled.append(
            {
                "remotePath": remote_path,
                "localPath": str(local_path),
                "size": local_path.stat().st_size,
                "sha256": sha256_file(local_path),
            }
        )
    return {
        "timestamp": now_iso(),
        "backend": "external-storage",
        "available": bool(roots),
        "roots": roots,
        "files": pulled,
    }


def capture_screenshot(serial: str | None, output_path: pathlib.Path) -> dict[str, Any]:
    ensure_dir(output_path.parent)
    proc = subprocess.run(
        adb_prefix(serial) + ["exec-out", "screencap", "-p"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    data = proc.stdout
    output_path.write_bytes(data)
    return {
        "path": str(output_path),
        "sha256": sha256_bytes(data),
        "size": len(data),
    }


def capture_ui_dump(serial: str | None, output_path: pathlib.Path) -> dict[str, Any]:
    ensure_dir(output_path.parent)
    proc = subprocess.run(
        adb_prefix(serial) + ["exec-out", "uiautomator", "dump", "/dev/tty"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    data = proc.stdout
    marker = b"UI hierchary dumped to: /dev/tty"
    marker_index = data.find(marker)
    if marker_index != -1:
        data = data[:marker_index].rstrip()
    output_path.write_bytes(data)
    texts: list[str] = []
    error = None
    try:
        root = ET.fromstring(data.decode("utf-8", "replace"))
        for node in root.iter("node"):
            text = node.attrib.get("text", "")
            if text:
                texts.append(text)
    except ET.ParseError:
        error = "xml-parse-failed"
    return {
        "path": str(output_path),
        "sha256": sha256_bytes(data),
        "texts": texts[:200],
        "available": bool(data),
        "error": error,
    }


def capture_scene_state(serial: str | None, package: str) -> dict[str, Any]:
    activity_dump = adb(serial, "shell", "dumpsys", "activity", "activities", timeout=20).stdout
    resumed_match = re.search(r"topResumedActivity=ActivityRecord\{[^\}]+\s+([^/\s]+)/([^\s\}]+)", activity_dump)
    if not resumed_match:
        resumed_match = re.search(r"ResumedActivity:\s+ActivityRecord\{[^\}]+\s+([^/\s]+)/([^\s\}]+)", activity_dump)
    resumed_component = None
    if resumed_match:
        resumed_component = f"{resumed_match.group(1)}/{resumed_match.group(2)}"
    focused_component = resumed_component
    return {
        "timestamp": now_iso(),
        "focusedComponent": focused_component,
        "resumedComponent": resumed_component,
        "packageInFocus": bool(
            (focused_component and focused_component.startswith(package + "/"))
            or (resumed_component and resumed_component.startswith(package + "/"))
        ),
    }


def capture_audio_snapshot(serial: str | None, package: str, output_path: pathlib.Path) -> dict[str, Any]:
    ensure_dir(output_path.parent)
    raw = adb(serial, "shell", "dumpsys", "media.audio_flinger", timeout=20).stdout
    output_path.write_text(raw, encoding="utf-8")
    package_lines = [line for line in raw.splitlines() if package in line]
    session_ids: list[int] = []
    for line in raw.splitlines():
        match = re.match(r"\s*(\d+)\s+\d+\s+\d+\s+\d+\s+" + re.escape(package) + r"$", line)
        if match:
            session_ids.append(int(match.group(1)))
    return {
        "timestamp": now_iso(),
        "backend": "audio-flinger-session-scan",
        "path": str(output_path),
        "sessionIds": sorted(set(session_ids)),
        "matchedLineCount": len(package_lines),
        "matchedLinesPreview": package_lines[:40],
    }


def launch_package(serial: str | None, package: str) -> dict[str, Any]:
    component_proc = adb(serial, "shell", "cmd", "package", "resolve-activity", "--brief", package, check=False, timeout=20)
    component = None
    for line in component_proc.stdout.splitlines():
        line = line.strip()
        if line and "/" in line and not line.startswith("priority="):
            component = line
    if component:
        launch_proc = adb(serial, "shell", "am", "start", "-n", component, check=False, timeout=20)
        return {
            "component": component,
            "stdout": launch_proc.stdout.strip(),
            "stderr": launch_proc.stderr.strip(),
            "returncode": launch_proc.returncode,
        }
    monkey_proc = adb(
        serial,
        "shell",
        "monkey",
        "-p",
        package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
        check=False,
        timeout=20,
    )
    return {
        "component": None,
        "stdout": monkey_proc.stdout.strip(),
        "stderr": monkey_proc.stderr.strip(),
        "returncode": monkey_proc.returncode,
    }


def start_logcat(serial: str | None, output_path: pathlib.Path) -> subprocess.Popen:
    ensure_dir(output_path.parent)
    handle = output_path.open("w", encoding="utf-8", newline="\n")
    return subprocess.Popen(
        adb_prefix(serial) + ["logcat", "-v", "threadtime"],
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_logcat(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def build_verification_trace(args: argparse.Namespace) -> dict[str, Any]:
    ai_index = int(args.ai_index) if args.ai_index is not None else None
    preferred_map_index = int(args.preferred_map_index) if args.preferred_map_index is not None else None
    storyboard_index = int(args.storyboard_index) if args.storyboard_index is not None else None
    return {
        "traceId": args.capture_id,
        "familyId": args.family_id,
        "aiIndex": ai_index,
        "stageTitle": args.stage_title,
        "storyboardIndex": storyboard_index,
        "routeLabel": args.route_label,
        "preferredMapIndex": preferred_map_index,
        "scriptEventCountExpected": None,
        "dialogueEventsSeen": None,
        "dialogueAnchorsSeen": [],
        "sceneCommandIdsSeen": [],
        "sceneDirectiveKindsSeen": [],
        "scenePhaseSequence": [],
        "objectivePhaseSequence": [],
        "resultType": None,
        "unlockTarget": None,
        "saveSlotIdentity": None,
        "resumeTargetScene": None,
        "resumeTargetStageBinding": None,
    }


def probe_environment(
    serial: str | None,
    package: str,
    apk_path: pathlib.Path | None,
    artifact_dir: pathlib.Path,
) -> dict[str, Any]:
    expected_apk_sha = sha256_file(apk_path) if apk_path else None
    installed_apk_path = artifact_dir / "installed_base.apk"
    installed_info = pull_installed_base_apk(serial, package, installed_apk_path)
    native_bridge = get_prop(serial, "ro.dalvik.vm.native.bridge")
    abi_list = get_prop(serial, "ro.product.cpu.abilist")
    run_as = detect_run_as(serial, package)
    su_backend = detect_su(serial)
    jni_backend = detect_jni_trace_backend(serial, package)
    external_roots = detect_existing_paths(serial, candidate_save_roots(package))
    devices = list_devices()
    selected_device = None
    for device in devices:
        if device["serial"] == serial:
            selected_device = device
            break

    installed_matches_expected = None
    if expected_apk_sha and installed_info["sha256"]:
        installed_matches_expected = expected_apk_sha == installed_info["sha256"]

    return {
        "device": {
            "serial": serial,
            "adbEntry": selected_device,
            "abiList": [item.strip() for item in abi_list.split(",") if item.strip()],
            "nativeBridge": native_bridge or None,
        },
        "oracleTarget": {
            "packageName": package,
            "expectedApkPath": str(apk_path) if apk_path else None,
            "expectedApkSha256": expected_apk_sha,
            "installedPackagePath": installed_info["packagePath"],
            "installedPackageSha256": installed_info["sha256"],
            "installedPackagePulledPath": installed_info["pulledPath"],
            "installedMatchesExpectedApk": installed_matches_expected,
        },
        "oracleReadiness": {
            "packageIdentitySatisfied": installed_matches_expected is True,
            "jniTraceBackendSatisfied": jni_backend["available"],
            "canCaptureOriginalRunNow": installed_matches_expected is True,
            "canProduceFullyPassingOracleTraceNow": installed_matches_expected is True and jni_backend["available"],
        },
        "capabilities": {
            "runAs": run_as,
            "su": su_backend,
            "jniCallTrace": jni_backend,
            "externalSaveRoots": external_roots,
        },
    }


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def command_probe(args: argparse.Namespace) -> int:
    serial = choose_serial(args.serial)
    output_path = pathlib.Path(args.output).resolve()
    artifact_dir = ensure_dir(output_path.parent / (output_path.stem + "_artifacts"))
    apk_path = pathlib.Path(args.apk).resolve() if args.apk else None
    payload = {
        "specVersion": SPEC_VERSION,
        "captureKind": "probe",
        "generatedAt": now_iso(),
    }
    payload.update(probe_environment(serial, args.package, apk_path, artifact_dir))
    write_json(output_path, payload)
    print(output_path)
    return 0


def command_capture(args: argparse.Namespace) -> int:
    serial = choose_serial(args.serial)
    apk_path = pathlib.Path(args.apk).resolve() if args.apk else None
    output_dir = pathlib.Path(args.output_dir).resolve()
    ensure_dir(output_dir)
    artifact_dir = ensure_dir(output_dir / "artifacts")

    probe = probe_environment(serial, args.package, apk_path, artifact_dir)
    package_match = probe["oracleTarget"]["installedMatchesExpectedApk"]
    if package_match is False and not args.allow_package_mismatch:
        raise RuntimeError(
            "Installed package does not match the expected original APK. "
            "Re-run with --allow-package-mismatch only for harness smoke tests."
        )

    if args.clear_logcat:
        adb(serial, "logcat", "-c", timeout=10)
    if args.launch:
        launch_info = launch_package(serial, args.package)
    else:
        launch_info = None

    capture_started_at = now_iso()
    logcat_path = output_dir / "logcat.txt"
    logcat_process = start_logcat(serial, logcat_path)

    screenshots_dir = ensure_dir(output_dir / "screenshots")
    ui_dir = ensure_dir(output_dir / "ui")
    audio_dir = ensure_dir(output_dir / "audio")
    saves_dir = ensure_dir(output_dir / "saves")

    frame_hashes: list[dict[str, Any]] = []
    scene_transitions: list[dict[str, Any]] = []
    audio_cues: list[dict[str, Any]] = []
    ui_snapshots: list[dict[str, Any]] = []
    save_snapshots: list[dict[str, Any]] = []

    initial_save = snapshot_save_files(serial, args.package, saves_dir / "initial")
    save_snapshots.append(initial_save)

    start_monotonic = time.monotonic()
    next_frame = 0.0
    next_scene = 0.0
    next_ui = 0.0
    next_audio = 0.0

    try:
        while True:
            elapsed = time.monotonic() - start_monotonic
            if elapsed >= args.duration:
                break

            if elapsed >= next_scene:
                scene = capture_scene_state(serial, args.package)
                scene["elapsedSeconds"] = round(elapsed, 3)
                previous = scene_transitions[-1] if scene_transitions else None
                if not previous or (
                    previous.get("focusedComponent") != scene.get("focusedComponent")
                    or previous.get("resumedComponent") != scene.get("resumedComponent")
                    or previous.get("packageInFocus") != scene.get("packageInFocus")
                ):
                    scene_transitions.append(scene)
                next_scene += args.scene_interval

            if elapsed >= next_frame:
                shot_path = screenshots_dir / f"frame_{len(frame_hashes):04d}.png"
                shot = capture_screenshot(serial, shot_path)
                shot["timestamp"] = now_iso()
                shot["elapsedSeconds"] = round(elapsed, 3)
                if scene_transitions:
                    shot["focusedComponent"] = scene_transitions[-1].get("focusedComponent")
                frame_hashes.append(shot)
                next_frame += args.frame_interval

            if elapsed >= next_ui:
                ui_path = ui_dir / f"ui_{len(ui_snapshots):04d}.xml"
                ui = capture_ui_dump(serial, ui_path)
                ui["timestamp"] = now_iso()
                ui["elapsedSeconds"] = round(elapsed, 3)
                ui_snapshots.append(ui)
                next_ui += args.ui_interval

            if elapsed >= next_audio:
                audio_path = audio_dir / f"audio_{len(audio_cues):04d}.txt"
                audio = capture_audio_snapshot(serial, args.package, audio_path)
                audio["elapsedSeconds"] = round(elapsed, 3)
                audio_cues.append(audio)
                next_audio += args.audio_interval

            time.sleep(0.1)
    finally:
        stop_logcat(logcat_process)

    final_save = snapshot_save_files(serial, args.package, saves_dir / "final")
    save_snapshots.append(final_save)

    capture_finished_at = now_iso()

    session = {
        "specVersion": SPEC_VERSION,
        "captureKind": "oracle-session",
        "captureId": args.capture_id,
        "captureStartedAt": capture_started_at,
        "captureFinishedAt": capture_finished_at,
        "packageName": args.package,
        "device": probe["device"],
        "oracleTarget": probe["oracleTarget"],
        "oracleReadiness": probe["oracleReadiness"],
        "capabilities": probe["capabilities"],
        "artifacts": {
            "outputDir": str(output_dir),
            "logcatPath": str(logcat_path),
            "launchInfo": launch_info,
            "uiSnapshotCount": len(ui_snapshots),
            "frameHashCount": len(frame_hashes),
            "audioSnapshotCount": len(audio_cues),
            "saveSnapshotCount": len(save_snapshots),
        },
        "jniCallTrace": {
            "backend": probe["capabilities"]["jniCallTrace"]["backend"],
            "available": probe["capabilities"]["jniCallTrace"]["available"],
            "reason": probe["capabilities"]["jniCallTrace"]["reason"],
            "artifactPath": args.manual_jni_trace,
            "events": [],
        },
        "frameHashes": frame_hashes,
        "audioCues": audio_cues,
        "sceneTransitions": scene_transitions,
        "saveSnapshots": save_snapshots,
        "uiSnapshots": ui_snapshots,
        "verificationTrace": build_verification_trace(args),
    }
    write_json(output_dir / "session.json", session)
    print(output_dir / "session.json")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture AW1 oracle traces from the original APK environment.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="Probe device/package capabilities for oracle capture.")
    probe.add_argument("--serial", default=None)
    probe.add_argument("--package", default=DEFAULT_PACKAGE)
    probe.add_argument("--apk", default=None)
    probe.add_argument("--output", required=True)
    probe.set_defaults(func=command_probe)

    capture = subparsers.add_parser("capture", help="Capture a raw oracle session.")
    capture.add_argument("--serial", default=None)
    capture.add_argument("--package", default=DEFAULT_PACKAGE)
    capture.add_argument("--apk", default=None)
    capture.add_argument("--capture-id", required=True)
    capture.add_argument("--output-dir", required=True)
    capture.add_argument("--duration", type=float, default=20.0)
    capture.add_argument("--frame-interval", type=float, default=2.0)
    capture.add_argument("--ui-interval", type=float, default=5.0)
    capture.add_argument("--scene-interval", type=float, default=1.0)
    capture.add_argument("--audio-interval", type=float, default=2.0)
    capture.add_argument("--launch", action="store_true")
    capture.add_argument("--clear-logcat", action="store_true")
    capture.add_argument("--allow-package-mismatch", action="store_true")
    capture.add_argument("--manual-jni-trace", default=None)
    capture.add_argument("--family-id", default=None)
    capture.add_argument("--ai-index", default=None)
    capture.add_argument("--stage-title", default=None)
    capture.add_argument("--storyboard-index", default=None)
    capture.add_argument("--route-label", default=None)
    capture.add_argument("--preferred-map-index", default=None)
    capture.set_defaults(func=command_capture)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
