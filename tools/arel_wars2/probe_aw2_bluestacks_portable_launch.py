#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def maybe_run(cmd: list[str], timeout: int = 60, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


def maybe_run_or_timeout(cmd: list[str], timeout: int = 60, cwd: Path | None = None) -> dict[str, object]:
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timedOut": True,
            "timeoutSeconds": timeout,
        }


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def powershell_json(script: str) -> object:
    completed = maybe_run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            script,
        ],
        timeout=60,
    )
    if completed.returncode != 0:
        return {
            "error": "powershell-json-failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    text = completed.stdout.strip()
    if not text:
        return []
    return json.loads(text)


def maybe_powershell(script: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return maybe_run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            script,
        ],
        timeout=timeout,
    )


def matching_processes() -> object:
    return powershell_json(
        r"""
        Get-CimInstance Win32_Process |
          Where-Object {
            $_.Name -like 'HD-*' -or
            $_.Name -like 'Bstk*' -or
            $_.Name -like 'VBox*' -or
            $_.Name -like 'consent*'
          } |
          Select-Object Name,ProcessId,ParentProcessId,CommandLine |
          ConvertTo-Json -Depth 4
        """
    )


def stop_processes() -> None:
    maybe_powershell(
        r"""
        Stop-Process -Name BstkSVC -Force -ErrorAction SilentlyContinue
        Stop-Process -Name VBoxSVC -Force -ErrorAction SilentlyContinue
        Stop-Process -Name BstkVMMgr -Force -ErrorAction SilentlyContinue
        Stop-Process -Name HD-Player -Force -ErrorAction SilentlyContinue
        Stop-Process -Name VBoxHeadless -Force -ErrorAction SilentlyContinue
        """,
        timeout=30,
    )


def registry_default_value(path: str) -> dict[str, object]:
    completed = maybe_run(["reg", "query", path, "/ve"], timeout=20)
    return {
        "path": path,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def registry_key_dump(path: str) -> dict[str, object]:
    completed = maybe_run(["reg", "query", path, "/s"], timeout=20)
    return {
        "path": path,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def tail_text(path: Path, max_lines: int = 80) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-max_lines:]


def latest_vm_logs(vm_dir: Path) -> list[dict[str, object]]:
    log_dir = vm_dir / "Logs"
    if not log_dir.exists():
        return []
    items = []
    for path in sorted(log_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "fullPath": str(path),
                "size": stat.st_size,
                "lastWriteTimeUtc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return items[:20]


def adb_devices(adb: Path) -> dict[str, object]:
    completed = maybe_run([str(adb), "devices", "-l"], timeout=30)
    return {
        "path": str(adb),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def tcp_5555() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        try:
            sock.connect(("127.0.0.1", 5555))
        except OSError:
            return False
        return True


def list_vms(vmmgr: Path) -> dict[str, object]:
    completed = maybe_run_or_timeout([str(vmmgr), "list", "vms"], timeout=30, cwd=vmmgr.parent)
    return {
        "path": str(vmmgr),
        **completed,
    }


def probe_hd_player(player: Path, instance_name: str, wait_seconds: int, vm_dir: Path, hd_adb: Path | None, sdk_adb: Path | None) -> dict[str, object]:
    started_at = now_iso()
    proc = subprocess.Popen(
        [str(player), "--instance", instance_name, "--hidden"],
        cwd=str(player.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(5)
        early_processes = matching_processes()
        time.sleep(max(0, wait_seconds - 5))
        late_processes = matching_processes()
        has_exited = proc.poll() is not None
        significant_vbox = {"vboxheadless.exe", "vboxsvc.exe", "vboxmanage.exe"}
        result = {
            "startedAtUtc": started_at,
            "pid": proc.pid,
            "hasExitedByProbeEnd": has_exited,
            "exitCode": proc.poll(),
            "earlyProcesses": early_processes,
            "lateProcesses": late_processes,
            "hdAdb": adb_devices(hd_adb) if hd_adb and hd_adb.exists() else None,
            "sdkAdb": adb_devices(sdk_adb) if sdk_adb and sdk_adb.exists() else None,
            "tcp5555Open": tcp_5555(),
            "latestVmLogs": latest_vm_logs(vm_dir),
        }
        result["spawnedVBoxProcess"] = any(
            isinstance(entry, dict) and str(entry.get("Name", "")).lower() in significant_vbox
            for entry in (late_processes if isinstance(late_processes, list) else [late_processes])
        )
        return result
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)


def probe_bstksvc(pf_dir: Path, output_dir: Path) -> dict[str, object]:
    svc = pf_dir / "BstkSVC.exe"
    log_path = output_dir / "BstkServer-direct-probe.log"
    if log_path.exists():
        log_path.unlink()
    stop_processes()
    time.sleep(1)
    started_at = now_iso()
    completed = maybe_run_or_timeout(
        [str(svc), "--logfile", str(log_path), "--registervbox"],
        timeout=8,
        cwd=pf_dir,
    )
    time.sleep(2)
    processes = matching_processes()
    return {
        "startedAtUtc": started_at,
        "path": str(svc),
        "logPath": str(log_path),
        **completed,
        "logTail": tail_text(log_path),
        "postProcesses": processes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-name", default="Nougat32")
    parser.add_argument("--wait-seconds", type=int, default=25)
    parser.add_argument(
        "--portable-root",
        default=r"C:\vs\other\arelwars\$root",
    )
    parser.add_argument(
        "--sdk-adb",
        default=r"C:\Users\lpaiu\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    )
    parser.add_argument(
        "--output",
        default=r"C:\vs\other\arelwars\recovery\arel_wars2\native_tmp\bluestacks_portable_probe\portable-launch-probe.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    portable_root = Path(args.portable_root)
    pf_dir = portable_root / "PF"
    vm_dir = portable_root / "PD" / "Engine" / args.instance_name
    player = pf_dir / "HD-Player.exe"
    vmmgr = pf_dir / "BstkVMMgr.exe"
    hd_adb = pf_dir / "HD-Adb.exe"
    sdk_adb = Path(args.sdk_adb)
    output = Path(args.output)
    ensure_dir(output.parent)
    stop_processes()

    report = {
        "generatedAtUtc": now_iso(),
        "portableRoot": str(portable_root),
        "instanceName": args.instance_name,
        "paths": {
            "player": str(player),
            "vmmgr": str(vmmgr),
            "hdAdb": str(hd_adb),
            "sdkAdb": str(sdk_adb),
            "vmDir": str(vm_dir),
        },
        "exists": {
            "player": player.exists(),
            "vmmgr": vmmgr.exists(),
            "hdAdb": hd_adb.exists(),
            "sdkAdb": sdk_adb.exists(),
            "vmDir": vm_dir.exists(),
        },
        "initialProcesses": matching_processes(),
        "effectiveComServer": registry_default_value(
            r"HKCR\CLSID\{b584bac7-d01f-49cf-a766-eb4c90cd3134}\LocalServer32"
        ),
        "userBlueStacksKey": registry_key_dump(r"HKCU\Software\BlueStacks"),
        "userBlueStacksServicesKey": registry_key_dump(r"HKCU\Software\BlueStacksServices"),
        "userEnvironmentKey": registry_key_dump(r"HKCU\Environment"),
    }
    if vmmgr.exists():
        report["vmmgrListVms"] = list_vms(vmmgr)
    if (pf_dir / "BstkSVC.exe").exists():
        report["bstkSvcDirectProbe"] = probe_bstksvc(pf_dir=pf_dir, output_dir=output.parent)
    if player.exists() and vm_dir.exists():
        report["hdPlayerProbe"] = probe_hd_player(
            player=player,
            instance_name=args.instance_name,
            wait_seconds=args.wait_seconds,
            vm_dir=vm_dir,
            hd_adb=hd_adb if hd_adb.exists() else None,
            sdk_adb=sdk_adb if sdk_adb.exists() else None,
        )
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
