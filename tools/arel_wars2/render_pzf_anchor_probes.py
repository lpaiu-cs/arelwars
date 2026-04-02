#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PIL import Image, ImageDraw


CURRENT_ROOT = Path(__file__).resolve().parent
if str(CURRENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CURRENT_ROOT))

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "arel_wars1"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.append(str(TOOLS_ROOT))

from formats import find_zlib_streams, read_pzx_row_stream  # noqa: E402

from inspect_binary_assets import parse_pzf


DEFAULT_PAIRS = (
    ("armor", "000"),
    ("head", "000"),
    ("weapon", "000"),
    ("weapon2", "000"),
    ("effect", "000"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render AW2 PZF anchor probes against nearest PZD row streams")
    parser.add_argument("--assets-root", type=Path, required=True, help="Path to extracted assets directory")
    parser.add_argument("--output", type=Path, required=True, help="Directory where probe PNGs are written")
    parser.add_argument("--scale", type=int, default=3, help="Nearest-neighbor scale factor")
    return parser.parse_args()


def color_for_index(value: int) -> tuple[int, int, int]:
    if value == 0:
        return (0, 0, 0)
    return ((value * 47) % 256, (value * 89) % 256, (value * 173) % 256)


def render_row_stream_rgba(row_stream, scale: int) -> Image.Image:
    if row_stream.width is None:
        raise ValueError("Inconsistent row widths")
    image = Image.new("RGBA", (row_stream.width, row_stream.height), (0, 0, 0, 0))
    pixels = image.load()
    for y, row in enumerate(row_stream.rows):
        for x, value in enumerate(row.decoded):
            if value == 0:
                continue
            r, g, b = color_for_index(value)
            pixels[x, y] = (r, g, b, 216)
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    return image


def load_pzd_row_streams(path: Path) -> list[dict[str, object]]:
    entries = []
    for index, hit in enumerate(find_zlib_streams(path.read_bytes())):
        try:
            row_stream = read_pzx_row_stream(hit.decoded)
        except ValueError:
            continue
        if row_stream is None or row_stream.width is None:
            continue
        entries.append(
            {
                "streamIndex": index,
                "width": row_stream.width,
                "height": row_stream.height,
                "rowStream": row_stream,
            }
        )
    return entries


def choose_matches(anchor_boxes: list[dict[str, int]], row_streams: list[dict[str, object]]) -> list[dict[str, object]]:
    remaining = list(range(len(row_streams)))
    matches = []
    for anchor_index, anchor in enumerate(anchor_boxes):
        best = None
        for candidate_index in remaining:
            row_stream = row_streams[candidate_index]
            width = int(row_stream["width"])
            height = int(row_stream["height"])
            score = (
                abs(anchor["width"] - width) + abs(anchor["height"] - height),
                abs(anchor["width"] * anchor["height"] - width * height),
                candidate_index,
            )
            if best is None or score < best[0]:
                best = (score, candidate_index)
        if best is None:
            continue
        remaining.remove(best[1])
        matches.append(
            {
                "anchorIndex": anchor_index,
                "anchor": anchor,
                "rowStream": row_streams[best[1]],
                "score": list(best[0]),
            }
        )
    return matches


def render_probe(family: str, stem: str, pzf_path: Path, pzd_path: Path, output_root: Path, scale: int) -> Path | None:
    pzf_entry = parse_pzf(pzf_path)
    anchor_info = pzf_entry.get("anchorBoxes")
    if anchor_info is None:
        return None
    row_streams = load_pzd_row_streams(pzd_path)
    if not row_streams:
        return None

    matches = choose_matches(anchor_info["preview"], row_streams)
    if not matches:
        return None

    x_min = min(int(match["anchor"]["x"]) for match in matches)
    y_min = min(int(match["anchor"]["y"]) for match in matches)
    x_max = max(int(match["anchor"]["x"]) + int(match["anchor"]["width"]) for match in matches)
    y_max = max(int(match["anchor"]["y"]) + int(match["anchor"]["height"]) for match in matches)
    margin = 18
    info_band = 42
    canvas = Image.new(
        "RGBA",
        ((x_max - x_min) * scale + margin * 2, (y_max - y_min) * scale + margin * 2 + info_band),
        (10, 12, 18, 255),
    )
    draw = ImageDraw.Draw(canvas)
    translate_x = margin - x_min * scale
    translate_y = margin - y_min * scale

    for match in matches:
        anchor = match["anchor"]
        row_stream = match["rowStream"]
        x = int(anchor["x"]) * scale + translate_x
        y = int(anchor["y"]) * scale + translate_y
        box = (
            x,
            y,
            x + int(anchor["width"]) * scale,
            y + int(anchor["height"]) * scale,
        )
        draw.rectangle(box, outline=(244, 84, 84, 255), width=2)
        rendered = render_row_stream_rgba(row_stream["rowStream"], scale)
        canvas.alpha_composite(rendered, (x, y))
        label = f"a{match['anchorIndex']:02d}:s{int(row_stream['streamIndex']):02d}"
        draw.text((x + 3, y + 3), label, fill=(248, 240, 216, 255))

    header = (
        f"{family}/{stem}  variant={pzf_entry['variant']}  "
        f"anchors={anchor_info['recordCount']}  pzdStreams={len(row_streams)}"
    )
    footer = "red box = PZF anchor, overlay = nearest-size PZD row stream"
    draw.text((margin, canvas.height - info_band + 6), header, fill=(236, 238, 244, 255))
    draw.text((margin, canvas.height - info_band + 22), footer, fill=(180, 190, 204, 255))

    output_path = output_root / f"{family}-{stem}-anchor-probe.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def main() -> None:
    args = parse_args()
    assets_root = args.assets_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    rendered = 0
    for family, stem in DEFAULT_PAIRS:
        pzf_path = assets_root / "pc" / family / f"{stem}.pzf"
        pzd_path = assets_root / "pc" / family / "0" / f"{stem}.pzd"
        if not pzf_path.exists() or not pzd_path.exists():
            continue
        output_path = render_probe(family, stem, pzf_path, pzd_path, output_root, args.scale)
        if output_path is None:
            continue
        print(output_path)
        rendered += 1

    print(f"rendered={rendered}")


if __name__ == "__main__":
    main()
