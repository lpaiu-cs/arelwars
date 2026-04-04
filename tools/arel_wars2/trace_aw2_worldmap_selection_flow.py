from __future__ import annotations

import json
import re
import struct
import subprocess
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_MEM, ARM_REG_PC


ROOT = Path(__file__).resolve().parents[2]
NDK_BIN = Path(
    r"C:\Users\lpaiu\AppData\Local\Android\Sdk\ndk\30.0.14904198\toolchains\llvm\prebuilt\windows-x86_64\bin"
)
LLVM_READELF = NDK_BIN / "llvm-readelf.exe"
ORIGINAL_LIB = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "original_lib_extract" / "libgameDSO.so"
REPORT_PATH = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "aw2_worldmap_selection_flow.json"


def read_symbol_addrs(lib_path: Path) -> dict[str, int]:
    out = subprocess.check_output(
        [str(LLVM_READELF), "-Ws", str(lib_path)],
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    symbols: dict[str, int] = {}
    for line in out.splitlines():
        match = re.match(r"\s*\d+:\s*([0-9a-fA-F]+)\s+(\d+)\s+FUNC\s+\w+\s+\w+\s+\d+\s+(\S+)", line)
        if not match:
            continue
        symbols[match.group(3)] = int(match.group(1), 16) & ~1
    return symbols


def read_literal_u32(blob: bytes, insn_addr: int, disp: int) -> int:
    pc = (insn_addr + 4) & ~3
    literal_addr = pc + disp
    return struct.unpack_from("<I", blob, literal_addr)[0]


def find_literal_value(blob: bytes, start: int, stop: int, target_addr: int) -> int:
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    off = start & ~1
    stop_off = stop & ~1
    thumb_addr = start | 1
    for insn in md.disasm(blob[off:stop_off], thumb_addr):
        if insn.address != target_addr:
            continue
        for operand in insn.operands:
            if operand.type == ARM_OP_MEM and operand.mem.base == ARM_REG_PC:
                return read_literal_u32(blob, insn.address, operand.mem.disp)
        raise RuntimeError(f"Instruction at {hex(target_addr)} is not a PC-relative literal load")
    raise RuntimeError(f"Instruction not found at {hex(target_addr)}")


def build_report(lib_path: Path) -> dict[str, object]:
    blob = lib_path.read_bytes()
    symbols = read_symbol_addrs(lib_path)

    touch_input_worldmap_menu = symbols["_ZN16CPdStateWorldmap22TouchInputWorldMapMenuEv"]
    do_touch_move_world_area = symbols["_ZN16CPdStateWorldmap20DoTouchMoveWorldAreaEii"]
    update_worldmap_menu = symbols["_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv"]
    init_worldmap_slot_area_ani = symbols["_ZN16CPdStateWorldmap22InitWorldmapSltAreaAniEi"]
    is_check_area_enter = symbols["_ZN16CPdStateWorldmap16IsCheckAreaEnterEi"]

    field_379c = find_literal_value(blob, do_touch_move_world_area, do_touch_move_world_area + 0x280, 0x10A4A3)
    field_362c = find_literal_value(blob, do_touch_move_world_area, do_touch_move_world_area + 0x280, 0x10A4F7)
    field_36f8 = field_379c - 0xA4
    field_100 = 0x100

    update_selected_area_field = find_literal_value(blob, update_worldmap_menu, update_worldmap_menu + 0x260, 0x10B87F)
    update_worldmap_menu_flag_379c = find_literal_value(blob, update_worldmap_menu, update_worldmap_menu + 0x260, 0x10B767)
    update_worldmap_menu_field_36f8 = find_literal_value(blob, update_worldmap_menu, update_worldmap_menu + 0x260, 0x10B7E9)

    return {
        "sourceLib": str(lib_path),
        "touchInputWorldMapMenu": {
            "symbol": "_ZN16CPdStateWorldmap22TouchInputWorldMapMenuEv",
            "reads": {
                "worldmapTransitionGate": hex(find_literal_value(blob, touch_input_worldmap_menu, touch_input_worldmap_menu + 0x50, 0x0D121F)),
                "worldmapPopupGate": hex(find_literal_value(blob, touch_input_worldmap_menu, touch_input_worldmap_menu + 0x50, 0x0D1239)),
            },
            "notes": [
                "Consumes the shared press latch and clears 0x362c when the worldmap menu path accepts input.",
                "This is a menu-layer handler, not the stage-select creator.",
            ],
        },
        "selectionFlow": {
            "symbol": "_ZN16CPdStateWorldmap20DoTouchMoveWorldAreaEii",
            "selectedAreaField": hex(field_100),
            "enterGateField": hex(field_379c),
            "popupGateField": hex(field_362c),
            "pendingAreaField": hex(field_36f8),
            "genericAreaHitSource": {
                "frameSourceField": "0xe0",
                "cameraOffsetSourceField": "0xdc",
                "helpers": [
                    "_ZN11CGxPZxFrame19GetBoundingBoxCountEi",
                    "_ZN11CGxPZxFrame14GetBoundingBoxEii",
                ],
                "notes": [
                    "The generic 0..4 / 5 area scan is driven by bounding boxes from the active worldmap frame, not by a fixed hard-coded screen rectangle table.",
                    "DoTouchMoveWorldArea also reads camera/scroll-style offsets from the object at this+0xdc before it compares the pointer coordinates against those bounding boxes.",
                ],
            },
            "newAreaBranch": {
                "range": ["0x10a459", "0x10a467"],
                "effect": [
                    f"store candidate area index into [this+{hex(field_100)}]",
                    f"call {hex(init_worldmap_slot_area_ani)}",
                ],
            },
            "sameAreaEnterableBranch": {
                "range": ["0x10a497", "0x10a4b1"],
                "effect": [
                    f"call {hex(is_check_area_enter)} on the selected area",
                    f"if enterable, set [this+{hex(field_379c)}] = 1",
                    f"copy [this+{hex(field_100)}] into [this+{hex(field_36f8)}]",
                ],
            },
            "sameAreaPopupBranch": {
                "range": ["0x10a4f7", "0x10a557"],
                "effect": [
                    f"set [this+{hex(field_362c)}] = 1",
                    "spawn the worldmap system popup instead of scheduling area entry",
                ],
            },
        },
        "updateWorldMapMenuConsumer": {
            "symbol": "_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv",
            "reads": {
                "enterGateField": hex(update_worldmap_menu_flag_379c),
                "pendingAreaField": hex(update_worldmap_menu_field_36f8),
            },
            "writes": {
                "selectedAreaMirrorField": hex(update_selected_area_field),
                "pendingStateField": "0x8",
                "currentStateSnapshotField": "0xc",
            },
            "cases": {
                "pendingArea_0_to_4": [
                    f"write selected area index into [this+{hex(update_selected_area_field)}]",
                    "set [this+0x8] = 2",
                    "copy [this+0x4] into [this+0xc]",
                    f"clear [this+{hex(update_worldmap_menu_field_36f8)}] to -1",
                ],
                "pendingArea_5": [
                    "set [this+0x8] = 0x19",
                    "copy [this+0x4] into [this+0xc]",
                    f"clear [this+{hex(update_worldmap_menu_field_36f8)}] to -1",
                ],
            },
            "notes": [
                "This function is the first confirmed consumer of the worldmap area enter latch.",
                "It still does not call CreateStageSelect directly; it schedules later state/menu work.",
            ],
        },
        "conclusion": [
            "Base worldframe selection is a two-step flow: select area first, then same-area re-tap arms 0x379c/0x36f8.",
            "Town SHOP responding while DESERT PLAIN/PVP do not is consistent with overlay/menu handlers working while the base area selection path still fails to arm or consume the pending-area latch.",
            "The next safe targets are area hit recognition and the 0x379c/0x36f8 consumer path, not direct CreateStageSelect jumps.",
        ],
    }


def main() -> int:
    if not ORIGINAL_LIB.exists():
        raise SystemExit(f"Missing original library: {ORIGINAL_LIB}")
    report = build_report(ORIGINAL_LIB)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["selectionFlow"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
