#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.arel_wars1 import capture_aw1_oracle_trace as aw1_capture


DEFAULT_PACKAGE = "com.gamevil.ArelWars2.global"
SPEC_VERSION = "aw2-oracle-capture-v1"
DEFAULT_SAVE_ROOTS = [
    "/sdcard/Android/data/{package}",
    "/sdcard/Android/data/{package}/files",
    "/sdcard/{package}",
    "/sdcard/gamevil",
    "/sdcard/Gamevil",
]


def build_parser():
    parser = aw1_capture.build_parser()
    parser.description = "Capture AW2 oracle traces from the original APK environment."
    for action in parser._actions:
        if getattr(action, "dest", None) == "command":
            continue
        if action.dest == "package":
            action.default = DEFAULT_PACKAGE
        if action.dest == "apk":
            action.default = None
    return parser


def main() -> int:
    aw1_capture.DEFAULT_PACKAGE = DEFAULT_PACKAGE
    aw1_capture.SPEC_VERSION = SPEC_VERSION
    aw1_capture.DEFAULT_SAVE_ROOTS = DEFAULT_SAVE_ROOTS
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
