from __future__ import annotations

import argparse
import json
import os
import socket
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str], check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def maybe_run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def list_vms(vboxmanage: Path) -> str:
    return run([str(vboxmanage), "list", "vms"], timeout=60).stdout


def show_vminfo(vboxmanage: Path, vm_name: str) -> str:
    last_exc: subprocess.CalledProcessError | None = None
    for _ in range(10):
        try:
            return run([str(vboxmanage), "showvminfo", vm_name], timeout=60).stdout
        except subprocess.CalledProcessError as exc:
            last_exc = exc
            time.sleep(2)
    assert last_exc is not None
    raise last_exc


def run_retry(cmd: list[str], timeout: int = 120, retries: int = 10, delay: float = 2.0) -> subprocess.CompletedProcess[str]:
    last_exc: subprocess.CalledProcessError | None = None
    for _ in range(retries):
        try:
            return run(cmd, timeout=timeout)
        except subprocess.CalledProcessError as exc:
            last_exc = exc
            stderr = (exc.stderr or "").lower()
            stdout = (exc.stdout or "").lower()
            if "lock request pending" not in stderr + stdout and "already locked by a session" not in stderr + stdout:
                raise
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def vm_state(vboxmanage: Path, vm_name: str) -> str:
    text = show_vminfo(vboxmanage, vm_name)
    for line in text.splitlines():
        if line.startswith("State:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def poweroff_vm(vboxmanage: Path, vm_name: str) -> None:
    state = vm_state(vboxmanage, vm_name).lower()
    if state.startswith("running"):
        maybe_run([str(vboxmanage), "controlvm", vm_name, "poweroff"], timeout=60)
    deadline = time.time() + 60
    while time.time() < deadline:
        if vm_state(vboxmanage, vm_name).lower().startswith("powered off"):
            time.sleep(5)
            return
        time.sleep(2)
    raise RuntimeError(f"{vm_name} did not power off cleanly")


def ensure_registered(vboxmanage: Path, vm_name: str, vm_file: Path) -> None:
    if f'"{vm_name}"' in list_vms(vboxmanage):
        return
    run([str(vboxmanage), "registervm", str(vm_file)], timeout=60)


def ensure_data_vdi(vboxmanage: Path, vm_dir: Path) -> tuple[Path, str]:
    data_vdi = vm_dir / "Data.vdi"
    data_vhdx = vm_dir / "Data.vhdx"
    if not data_vdi.exists():
        run(
            [
                str(vboxmanage),
                "clonemedium",
                "disk",
                str(data_vhdx),
                str(data_vdi),
                "--format",
                "VDI",
            ],
            timeout=300,
        )
    info = run([str(vboxmanage), "showmediuminfo", "disk", str(data_vdi)], timeout=60).stdout
    uuid = ""
    for line in info.splitlines():
        if line.startswith("UUID:"):
            uuid = line.split(":", 1)[1].strip()
            break
    if not uuid:
        raise RuntimeError(f"Unable to resolve UUID for {data_vdi}")
    return data_vdi, uuid


def patch_vm_xml(vm_file: Path, data_uuid: str, variant: str) -> None:
    if vm_file.exists():
        os.chmod(vm_file, 0o666)
    backup = vm_file.with_name(f"{vm_file.name}.{variant}.bak")
    if not backup.exists():
        shutil.copy2(vm_file, backup)

    ns = {"v": "http://www.virtualbox.org/"}
    ET.register_namespace("", ns["v"])
    tree = ET.parse(vm_file)
    root = tree.getroot()

    machine = root.find("v:Machine", ns)
    if machine is None:
        raise RuntimeError("Missing <Machine> node")

    media = root.find(".//v:MediaRegistry/v:HardDisks", ns)
    if media is None:
        raise RuntimeError("Missing <HardDisks> node")

    for hd in list(media):
        location = hd.attrib.get("location")
        fmt = hd.attrib.get("format")
        if location == "Data.vhdx":
            media.remove(hd)
        elif location == "Data.vdi" and fmt != "VDI":
            media.remove(hd)

    if not any(hd.attrib.get("location") == "Data.vdi" for hd in media):
        media.insert(
            0,
            ET.Element(
                f"{{{ns['v']}}}HardDisk",
                {
                    "uuid": "{" + data_uuid + "}",
                    "location": "Data.vdi",
                    "format": "VDI",
                    "type": "Normal",
                },
            ),
        )
    else:
        for hd in media:
            if hd.attrib.get("location") == "Data.vdi":
                hd.attrib["uuid"] = "{" + data_uuid + "}"
                hd.attrib["format"] = "VDI"
                hd.attrib["type"] = "Normal"

    extra = root.find(".//v:ExtraData", ns)
    if extra is not None:
        remove_names = {
            "VBoxInternal/PDM/Devices/bstdevices/Path",
            "VBoxInternal/GIM/Provider",
            "VBoxInternal/TM/TSCMode",
            "VBoxInternal/CPUM/HostCPUID/00000001/ecx",
            "VBoxInternal/CPUM/IsaExts/AVX2",
        }
        for item in list(extra):
            name = item.attrib.get("name", "")
            if name.startswith("VBoxInternal/Devices/bst") or name in remove_names:
                extra.remove(item)
            elif "virtio-net" not in variant and name.startswith("VBoxInternal/Devices/virtio-net/"):
                extra.remove(item)

    display = root.find(".//v:Hardware/v:Display", ns)
    if display is not None:
        display.attrib["controller"] = "VBoxVGA"
        display.attrib["VRAMSize"] = "32"
        display.attrib["monitorCount"] = "1"
        display.attrib["accelerate3D"] = "false"
        display.attrib["accelerate2DVideo"] = "false"

    chipset = root.find(".//v:Hardware/v:Chipset", ns)
    if chipset is not None:
        chipset.attrib["type"] = "PIIX3" if "piix3" in variant else "ICH9"

    bios = root.find(".//v:Hardware/v:BIOS", ns)
    if bios is not None:
        acpi = bios.find("v:ACPI", ns)
        ioapic = bios.find("v:IOAPIC", ns)
        if acpi is not None:
            acpi.attrib["enabled"] = "false" if "noacpi" in variant else "true"
        if ioapic is not None:
            ioapic.attrib["enabled"] = "false" if "noioapic" in variant else "true"

    nic = root.find(".//v:Hardware/v:Network/v:Adapter[@slot='0']", ns)
    if nic is not None:
        nic.attrib["type"] = "Am79C973" if "pcnet" in variant else "virtio"

    ide_like = variant.startswith("oracle-ide-")
    if ide_like:
        controllers = root.find(".//v:StorageControllers", ns)
        for ctl in list(controllers):
            if ctl.attrib.get("name") == "SATA":
                controllers.remove(ctl)
        ide = root.find(".//v:StorageController[@name='IDE']", ns)
        existing = list(ide)
        for child in existing[1:]:
            ide.remove(child)
        if "primaryslave" in variant:
            layout = [
                ("0", "1", "{fca296ce-8268-4ed7-a57f-d32ec11ab304}"),
                ("1", "0", "{" + data_uuid + "}"),
            ]
        elif "rootonly" in variant:
            layout = [
                ("0", "1", "{fca296ce-8268-4ed7-a57f-d32ec11ab304}"),
            ]
        else:
            layout = [
                ("1", "0", "{fca296ce-8268-4ed7-a57f-d32ec11ab304}"),
                ("1", "1", "{" + data_uuid + "}"),
            ]
        for port, device, uuid in layout:
            attached = ET.SubElement(
                ide,
                f"{{{ns['v']}}}AttachedDevice",
                {"type": "HardDisk", "hotpluggable": "false", "port": port, "device": device},
            )
            ET.SubElement(attached, f"{{{ns['v']}}}Image", {"uuid": uuid})
    else:
        for attached in root.findall(".//v:StorageController[@name='SATA']/v:AttachedDevice", ns):
            if variant.endswith("nohotplug"):
                attached.attrib["hotpluggable"] = "false"
            if attached.attrib.get("port") == "1":
                image = attached.find("v:Image", ns)
                if image is not None:
                    image.attrib["uuid"] = "{" + data_uuid + "}"

    vm_file.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")


def ensure_nat_pf(vboxmanage: Path, vm_name: str, host_port: int = 5555, guest_port: int = 5555) -> None:
    maybe_run([str(vboxmanage), "modifyvm", vm_name, "--natpf1", "delete", "adb"], timeout=60)
    run(
        [
            str(vboxmanage),
            "modifyvm",
            vm_name,
            "--natpf1",
            f"adb,tcp,127.0.0.1,{host_port},,{guest_port}",
        ],
        timeout=60,
    )


def apply_runtime_vm_settings(vboxmanage: Path, vm_name: str, vm_dir: Path, data_vdi: Path, variant: str) -> None:
    chipset = "piix3" if "piix3" in variant else "ich9"
    if "pcnet" in variant:
        nictype = "Am79C973"
    elif "e1000" in variant:
        nictype = "82540EM"
    else:
        nictype = "virtio"
    ioapic = "off" if "noioapic" in variant else "on"
    acpi = "off" if "noacpi" in variant else "on"
    run_retry(
        [
            str(vboxmanage),
            "modifyvm",
            vm_name,
            "--chipset",
            chipset,
            "--nictype1",
            nictype,
            "--ioapic",
            ioapic,
            "--acpi",
            acpi,
            "--graphicscontroller",
            "vboxvga",
            "--vram",
            "32",
            "--audio-driver",
            "null",
            "--audio-enabled",
            "off",
        ],
        timeout=60,
    )
    fastboot = vm_dir / "fastboot.vdi"
    root_vhd = vm_dir / "Root.vhd"
    ide_like = variant.startswith("oracle-ide-")
    if ide_like:
        maybe_run([str(vboxmanage), "storagectl", vm_name, "--name", "SATA", "--remove"], timeout=60)
        maybe_run(
            [
                str(vboxmanage),
                "storagectl",
                vm_name,
                "--name",
                "IDE",
                "--add",
                "ide",
                "--controller",
                "PIIX3",
                "--portcount",
                "2",
                "--bootable",
                "on",
            ],
            timeout=60,
        )
        for port, device in [("0", "1"), ("1", "0"), ("1", "1")]:
            maybe_run(
                [
                    str(vboxmanage),
                    "storageattach",
                    vm_name,
                    "--storagectl",
                    "IDE",
                    "--port",
                    port,
                    "--device",
                    device,
                    "--type",
                    "hdd",
                    "--medium",
                    "none",
                ],
                timeout=60,
            )
        run_retry(
            [
                str(vboxmanage),
                "storageattach",
                vm_name,
                "--storagectl",
                "IDE",
                "--port",
                "0",
                "--device",
                "0",
                "--type",
                "hdd",
                "--medium",
                str(fastboot),
            ],
            timeout=60,
        )
        if "primaryslave" in variant:
            layout = [("0", "1", root_vhd)]
            if "rootonly" not in variant:
                layout.append(("1", "0", data_vdi))
        elif "rootonly" in variant:
            layout = [("0", "1", root_vhd)]
        else:
            layout = [("1", "0", root_vhd)]
            if "rootonly" not in variant:
                layout.append(("1", "1", data_vdi))
        for port, device, medium in layout:
            run_retry(
                [
                    str(vboxmanage),
                    "storageattach",
                    vm_name,
                    "--storagectl",
                    "IDE",
                    "--port",
                    port,
                    "--device",
                    device,
                    "--type",
                    "hdd",
                    "--medium",
                    str(medium),
                ],
                timeout=60,
            )
    else:
        maybe_run(
            [
                str(vboxmanage),
                "storagectl",
                vm_name,
                "--name",
                "SATA",
                "--add",
                "sata",
                "--controller",
                "IntelAHCI",
                "--portcount",
                "2",
            ],
            timeout=60,
        )
        run_retry(
            [
                str(vboxmanage),
                "storageattach",
                vm_name,
                "--storagectl",
                "IDE",
                "--port",
                "0",
                "--device",
                "0",
                "--type",
                "hdd",
                "--medium",
                str(fastboot),
            ],
            timeout=60,
        )
        run_retry(
            [
                str(vboxmanage),
                "storageattach",
                vm_name,
                "--storagectl",
                "SATA",
                "--port",
                "0",
                "--device",
                "0",
                "--type",
                "hdd",
                "--medium",
                str(root_vhd),
            ],
            timeout=60,
        )
        run_retry(
            [
                str(vboxmanage),
                "storageattach",
                vm_name,
                "--storagectl",
                "SATA",
                "--port",
                "1",
                "--device",
                "0",
                "--type",
                "hdd",
                "--medium",
                str(data_vdi),
            ],
            timeout=60,
        )


def adb_devices(adb: Path) -> str:
    return maybe_run([str(adb), "devices", "-l"], timeout=30).stdout


def guestproperty_enumerate(vboxmanage: Path, vm_name: str) -> subprocess.CompletedProcess[str]:
    return maybe_run([str(vboxmanage), "guestproperty", "enumerate", vm_name], timeout=60)


def debugvm_osdetect(vboxmanage: Path, vm_name: str) -> subprocess.CompletedProcess[str]:
    return maybe_run([str(vboxmanage), "debugvm", vm_name, "osdetect"], timeout=60)


def debugvm_osinfo(vboxmanage: Path, vm_name: str) -> subprocess.CompletedProcess[str]:
    return maybe_run([str(vboxmanage), "debugvm", vm_name, "osinfo"], timeout=60)


def debugvm_statistics(vboxmanage: Path, vm_name: str) -> subprocess.CompletedProcess[str]:
    return maybe_run(
        [
            str(vboxmanage),
            "debugvm",
            vm_name,
            "statistics",
            "--pattern",
            "/Public/Storage/*|/Public/NetAdapter/*|/TM/CPU/*",
        ],
        timeout=60,
    )


def read_serial_log(serial_log: Path) -> dict[str, object]:
    if not serial_log.exists():
        return {
            "path": str(serial_log),
            "exists": False,
            "bytes": 0,
            "head": "",
        }
    data = serial_log.read_bytes()
    return {
        "path": str(serial_log),
        "exists": True,
        "bytes": len(data),
        "head": data[:2048].decode("latin1", errors="replace"),
        "lastWriteTimeUtc": datetime.fromtimestamp(serial_log.stat().st_mtime, timezone.utc).isoformat(),
    }


def test_tcp(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
        except OSError:
            return False
        return True


def capture_variant(
    vboxmanage: Path,
    adb: Path,
    vm_name: str,
    vm_file: Path,
    out_dir: Path,
    variant: str,
    wait_seconds: int,
    serial_log: Path,
) -> dict:
    ensure_dir(out_dir)
    ensure_registered(vboxmanage, vm_name, vm_file)
    poweroff_vm(vboxmanage, vm_name)

    data_vdi, data_uuid = ensure_data_vdi(vboxmanage, vm_file.parent)
    patch_vm_xml(vm_file, data_uuid, variant)
    apply_runtime_vm_settings(vboxmanage, vm_name, vm_file.parent, data_vdi, variant)
    ensure_nat_pf(vboxmanage, vm_name)
    ensure_dir(serial_log.parent)
    serial_log.write_bytes(b"")
    time.sleep(5)

    start = run_retry([str(vboxmanage), "startvm", vm_name, "--type", "headless"], timeout=60)
    time.sleep(wait_seconds)

    screenshot = out_dir / f"{variant}.png"
    screenshot_result = maybe_run(
        [str(vboxmanage), "controlvm", vm_name, "screenshotpng", str(screenshot)],
        timeout=60,
    )
    info = show_vminfo(vboxmanage, vm_name)
    adb_text = adb_devices(adb)
    tcp_open = test_tcp("127.0.0.1", 5555)
    guestproperty = guestproperty_enumerate(vboxmanage, vm_name)
    osdetect = debugvm_osdetect(vboxmanage, vm_name)
    osinfo = debugvm_osinfo(vboxmanage, vm_name)
    statistics = debugvm_statistics(vboxmanage, vm_name)
    serial_info = read_serial_log(serial_log)
    log_text = (vm_file.parent / "Logs" / "VBox.log").read_text(encoding="utf-8", errors="replace")
    log_tail = "\n".join(log_text.splitlines()[-160:])

    result = {
        "variant": variant,
        "vmName": vm_name,
        "vmFile": str(vm_file),
        "dataVdi": str(data_vdi),
        "dataVdiUuid": data_uuid,
        "startStdout": start.stdout,
        "startStderr": start.stderr,
        "showvminfo": info,
        "adbDevices": adb_text,
        "adbTcp5555Open": tcp_open,
        "guestPropertyRc": guestproperty.returncode,
        "guestPropertyStdout": guestproperty.stdout,
        "guestPropertyStderr": guestproperty.stderr,
        "osdetectRc": osdetect.returncode,
        "osdetectStdout": osdetect.stdout,
        "osdetectStderr": osdetect.stderr,
        "osinfoRc": osinfo.returncode,
        "osinfoStdout": osinfo.stdout,
        "osinfoStderr": osinfo.stderr,
        "debugStatisticsRc": statistics.returncode,
        "debugStatisticsStdout": statistics.stdout,
        "debugStatisticsStderr": statistics.stderr,
        "serialLog": serial_info,
        "screenshotPath": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "screenshotCommandRc": screenshot_result.returncode,
        "screenshotCommandStdout": screenshot_result.stdout,
        "screenshotCommandStderr": screenshot_result.stderr,
        "vboxLogTail": log_tail,
    }
    poweroff_vm(vboxmanage, vm_name)
    result["finalState"] = vm_state(vboxmanage, vm_name)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vm-name", default="Nougat32")
    parser.add_argument(
        "--vm-file",
        default=r"C:\vs\other\arelwars\$root\PD\Engine\Nougat32\Android.bstk",
    )
    parser.add_argument(
        "--vboxmanage",
        default=r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    )
    parser.add_argument(
        "--adb",
        default=r"C:\Users\lpaiu\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    )
    parser.add_argument(
        "--output-dir",
        default=r"C:\vs\other\arelwars\recovery\arel_wars2\native_tmp\oracle_vbox_probe",
    )
    parser.add_argument(
        "--serial-log",
        default=r"C:\vs\other\arelwars\recovery\arel_wars2\native_tmp\oracle_serial\nougat32-com1.log",
    )
    parser.add_argument(
        "--variant",
        choices=[
            "oracle-slim-vga",
            "oracle-slim-vga-nohotplug",
            "oracle-slim-piix3-vga",
            "oracle-slim-piix3-pcnet-vga",
            "oracle-ide-vga",
            "oracle-ide-primaryslave-vga",
            "oracle-ide-rootonly-vga",
            "oracle-ide-piix3-vga",
            "oracle-ide-primaryslave-piix3-vga",
            "oracle-ide-primaryslave-piix3-pcnet-vga",
            "oracle-ide-primaryslave-piix3-e1000-vga",
            "oracle-ide-rootonly-piix3-vga",
            "oracle-ide-piix3-noioapic-vga",
        ],
        default="oracle-slim-vga",
    )
    parser.add_argument("--wait-seconds", type=int, default=45)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    result = capture_variant(
        vboxmanage=Path(args.vboxmanage),
        adb=Path(args.adb),
        vm_name=args.vm_name,
        vm_file=Path(args.vm_file),
        out_dir=out_dir,
        variant=args.variant,
        wait_seconds=args.wait_seconds,
        serial_log=Path(args.serial_log),
    )
    ensure_dir(out_dir)
    out_file = out_dir / f"{args.variant}.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(str(out_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
