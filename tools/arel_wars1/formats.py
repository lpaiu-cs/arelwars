from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import struct
import zlib


ZLIB_HEADERS = {0x01, 0x5E, 0x9C, 0xDA}
PZX_RESOURCE_KINDS = ("pzd", "pzf", "pza")
PZX_EFFECTEX_SELECTOR_DRAW_OPS = {
    0x65: 1,
    0x66: 1,
    0x67: 2,
    0x68: 3,
    0x69: 6,
    0x6A: 7,
    0x6B: 8,
    0x6C: 9,
    0x6D: 10,
    0x6E: 11,
    0x6F: 12,
    0x70: 13,
    0x71: 19,
    0x72: 19,
    0x73: 19,
    0x74: 19,
    0x7F: 4,
}
PZX_META_MARKERS: dict[bytes, str] = {
    bytes.fromhex("67ff000000"): "67ff000000",
    bytes.fromhex("6778000000"): "6778000000",
    bytes.fromhex("6605000000"): "6605000000",
    bytes.fromhex("660a000000"): "660a000000",
    bytes.fromhex("660c000000"): "660c000000",
}


def _is_text_char(char: str) -> bool:
    if char.isascii():
        return char.isalnum() or char in " .,!?'-:;()[]/&+\""
    return "\uac00" <= char <= "\ud7a3"


@dataclass(frozen=True)
class Zt1File:
    packed_size: int
    unpacked_size: int
    decoded: bytes


@dataclass(frozen=True)
class ZlibStreamHit:
    offset: int
    consumed: int
    decoded: bytes


@dataclass(frozen=True)
class PzxRow:
    skips: tuple[int, ...]
    run_lengths: tuple[int, ...]
    run_kinds: tuple[str, ...]
    decoded: bytes


@dataclass(frozen=True)
class PzxChunk:
    index: int
    width: int
    height: int
    magic_hex: str
    declared_payload_len: int
    reserved: int
    body: bytes
    rows: tuple[PzxRow, ...]
    prefix_marker_hex: str | None
    row_separator_hexes: tuple[str, ...]
    trailing_sentinel_hex: str | None

    @property
    def decoded_pixel_count(self) -> int:
        return sum(len(row.decoded) for row in self.rows)


@dataclass(frozen=True)
class PzxFirstStream:
    table_span: int
    offsets: tuple[int, ...]
    chunks: tuple[PzxChunk, ...]


@dataclass(frozen=True)
class PzxRowStream:
    rows: tuple[PzxRow, ...]
    prefix_marker_hex: str | None
    row_separator_hexes: tuple[str, ...]
    trailing_sentinel_hex: str | None

    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int | None:
        widths = {len(row.decoded) for row in self.rows}
        if len(widths) != 1:
            return None
        return next(iter(widths))

    @property
    def width_range(self) -> tuple[int, int]:
        widths = [len(row.decoded) for row in self.rows]
        return (min(widths), max(widths))

    @property
    def decoded_pixel_count(self) -> int:
        return sum(len(row.decoded) for row in self.rows)


@dataclass(frozen=True)
class PzxSimplePlacement:
    mode: int
    chunk_index: int
    x: int
    y: int


@dataclass(frozen=True)
class PzxFrameItem:
    chunk_index: int
    x: int
    y: int
    flag: int


@dataclass(frozen=True)
class PzxFrameRecord:
    offset: int
    item_count: int
    frame_type: int
    x: int
    y: int
    width: int
    height: int
    items: tuple[PzxFrameItem, ...]
    control_chunks: tuple[bytes, ...]


@dataclass(frozen=True)
class PzxFrameRecordStream:
    records: tuple[PzxFrameRecord, ...]
    consumed: int
    trailing: bytes


@dataclass(frozen=True)
class PzxMetaTuple:
    chunk_index: int
    x: int
    y: int
    flag: int | None


@dataclass(frozen=True)
class PzxMetaSection:
    offset: int
    marker_hex: str | None
    payload: bytes
    layout: str
    header_hex: str | None
    tuple_count: int
    valid_tuple_count: int
    tuples: tuple[PzxMetaTuple, ...]


@dataclass(frozen=True)
class PzxAnimationFrame:
    frame_index: int
    delay: int
    x: int
    y: int
    control: int


@dataclass(frozen=True)
class PzxAnimationClip:
    offset: int
    frame_count: int
    frames: tuple[PzxAnimationFrame, ...]


@dataclass(frozen=True)
class PzxAnimationClipStream:
    clips: tuple[PzxAnimationClip, ...]

    @property
    def clip_count(self) -> int:
        return len(self.clips)

    @property
    def total_frame_count(self) -> int:
        return sum(len(clip.frames) for clip in self.clips)

    @property
    def frame_index_range(self) -> tuple[int, int]:
        values = [frame.frame_index for clip in self.clips for frame in clip.frames]
        return (min(values), max(values))

    @property
    def delay_range(self) -> tuple[int, int]:
        values = [frame.delay for clip in self.clips for frame in clip.frames]
        return (min(values), max(values))

    @property
    def x_range(self) -> tuple[int, int]:
        values = [frame.x for clip in self.clips for frame in clip.frames]
        return (min(values), max(values))

    @property
    def y_range(self) -> tuple[int, int]:
        values = [frame.y for clip in self.clips for frame in clip.frames]
        return (min(values), max(values))

    @property
    def control_values(self) -> tuple[int, ...]:
        return tuple(sorted({frame.control for clip in self.clips for frame in clip.frames}))

    @property
    def nonzero_control_count(self) -> int:
        return sum(1 for clip in self.clips for frame in clip.frames if frame.control != 0)


@dataclass(frozen=True)
class PzxPzfBoundingBoxRecord:
    raw: bytes
    values: tuple[int, ...]


@dataclass(frozen=True)
class PzxPzfSubFrame:
    subframe_index: int
    x: int
    y: int
    extra_flag: int
    extra: bytes
    effectex_selector: int | None = None
    effectex_parameter: int | None = None
    effectex_draw_op: int | None = None
    effectex_module: int | None = None


@dataclass(frozen=True)
class PzxPzfFrame:
    offset: int
    length: int
    subframe_count: int
    bbox_token0: int
    bbox_token1: int
    bbox_total_count: int
    bboxes: tuple[PzxPzfBoundingBoxRecord, ...]
    subframes: tuple[PzxPzfSubFrame, ...]


@dataclass(frozen=True)
class PzxPzfFrameStream:
    format_variant: int
    frames: tuple[PzxPzfFrame, ...]
    subframe_layout: str = "base"

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def total_subframe_count(self) -> int:
        return sum(frame.subframe_count for frame in self.frames)

    @property
    def frame_length_range(self) -> tuple[int, int]:
        lengths = [frame.length for frame in self.frames]
        return (min(lengths), max(lengths))

    @property
    def subframe_count_range(self) -> tuple[int, int]:
        counts = [frame.subframe_count for frame in self.frames]
        return (min(counts), max(counts))

    @property
    def bbox_total_range(self) -> tuple[int, int]:
        counts = [frame.bbox_total_count for frame in self.frames]
        return (min(counts), max(counts))

    @property
    def subframe_index_range(self) -> tuple[int, int] | None:
        values = [subframe.subframe_index for frame in self.frames for subframe in frame.subframes]
        if not values:
            return None
        return (min(values), max(values))

    @property
    def x_range(self) -> tuple[int, int] | None:
        values = [subframe.x for frame in self.frames for subframe in frame.subframes]
        if not values:
            return None
        return (min(values), max(values))

    @property
    def y_range(self) -> tuple[int, int] | None:
        values = [subframe.y for frame in self.frames for subframe in frame.subframes]
        if not values:
            return None
        return (min(values), max(values))

    @property
    def extra_flag_values(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                {
                    subframe.extra_flag
                    for frame in self.frames
                    for subframe in frame.subframes
                    if subframe.extra_flag != 0
                }
            )
        )

    @property
    def nonzero_extra_count(self) -> int:
        return sum(1 for frame in self.frames for subframe in frame.subframes if subframe.extra)

    @property
    def max_extra_len(self) -> int:
        lengths = [len(subframe.extra) for frame in self.frames for subframe in frame.subframes]
        if not lengths:
            return 0
        return max(lengths)

    @property
    def subframe_stride(self) -> int:
        if self.subframe_layout == "effectex":
            return 0x18
        return 0x10


@dataclass(frozen=True)
class PzxEmbeddedResource:
    kind: str
    offset: int
    header: int
    storage_mode: int
    format_variant: int
    content_count: int
    index_offsets: tuple[int, ...]
    packed_size: int | None
    unpacked_size: int
    payload_offset: int
    payload: bytes


@dataclass(frozen=True)
class PzxPzdZlibStream:
    index: int
    offset: int
    consumed: int
    decoded_len: int


@dataclass(frozen=True)
class PzxPzdImageRecord:
    index: int
    index_offset: int
    block_offset: int
    descriptor_offset: int
    payload_offset: int
    palette_count: int | None
    width: int
    height: int
    mode: int
    extra_flag: int
    unpacked_size: int
    packed_size: int


@dataclass(frozen=True)
class PzxPzdResource:
    offset: int
    end_offset: int
    type_code: int
    content_count: int
    flags: int
    palette_probe: int | None
    table_start: int | None
    index_offset_mode: str | None
    index_offsets: tuple[int, ...]
    global_palette_count: int | None
    packed_size: int | None
    unpacked_size: int | None
    payload_offset: int | None
    zlib_streams: tuple[PzxPzdZlibStream, ...]
    row_streams: tuple[PzxRowStream, ...]
    first_stream: PzxFirstStream | None
    image_records: tuple[PzxPzdImageRecord, ...]

    @property
    def layout(self) -> str:
        if self.type_code == 7:
            return "row-stream-list"
        if self.type_code == 8:
            return "first-stream-sheet"
        return "unknown"

    @property
    def image_count(self) -> int:
        if self.first_stream is not None:
            return len(self.first_stream.chunks)
        return len(self.row_streams)


def read_zt1(data: bytes) -> Zt1File:
    if len(data) < 8:
        raise ValueError("ZT1 payload is too short")

    packed_size, unpacked_size = struct.unpack("<II", data[:8])
    decoded = zlib.decompress(data[8:])
    if unpacked_size != len(decoded):
        raise ValueError(
            f"ZT1 unpacked size mismatch: header={unpacked_size}, decoded={len(decoded)}"
        )
    return Zt1File(packed_size=packed_size, unpacked_size=unpacked_size, decoded=decoded)


def find_zlib_streams(data: bytes, *, min_out: int = 8, min_consumed: int = 8) -> list[ZlibStreamHit]:
    hits: list[ZlibStreamHit] = []
    seen: set[tuple[int, int, int]] = set()

    for offset in range(len(data) - 2):
        if data[offset] != 0x78 or data[offset + 1] not in ZLIB_HEADERS:
            continue
        try:
            obj = zlib.decompressobj()
            decoded = obj.decompress(data[offset:])
            consumed = len(data[offset:]) - len(obj.unused_data)
        except zlib.error:
            continue

        if consumed < min_consumed or len(decoded) < min_out:
            continue

        key = (offset, consumed, len(decoded))
        if key in seen:
            continue
        seen.add(key)
        hits.append(ZlibStreamHit(offset=offset, consumed=consumed, decoded=decoded))

    return hits


def decode_pzx_row(body: bytes, cursor: int, width: int) -> tuple[PzxRow, int]:
    decoded = bytearray()
    skips: list[int] = []
    run_lengths: list[int] = []
    run_kinds: list[str] = []

    while len(decoded) < width:
        if cursor + 2 > len(body):
            raise ValueError("PZX row ended mid-opcode")
        word = struct.unpack("<H", body[cursor : cursor + 2])[0]

        if word < 0x8000:
            decoded.extend(b"\x00" * word)
            skips.append(word)
            cursor += 2
            continue

        if 0x8000 <= word < 0xC000:
            literal_len = word & 0x3FFF
            cursor += 2
            literal = body[cursor : cursor + literal_len]
            if len(literal) != literal_len:
                raise ValueError("PZX row ended mid-literal")
            decoded.extend(literal)
            run_lengths.append(literal_len)
            run_kinds.append("literal")
            cursor += literal_len
        elif 0xC000 <= word < 0xFDFF:
            repeat_len = word & 0x3FFF
            cursor += 2
            if cursor >= len(body):
                raise ValueError("PZX row ended mid-repeat")
            value = body[cursor]
            decoded.extend(bytes([value]) * repeat_len)
            run_lengths.append(repeat_len)
            run_kinds.append("repeat")
            cursor += 1
        else:
            raise ValueError(f"Unknown PZX opcode family: {word:#06x}")

        if len(decoded) > width:
            raise ValueError(f"PZX row width overflow: decoded={len(decoded)} expected={width}")

    if len(decoded) != width:
        raise ValueError(f"PZX row width mismatch: decoded={len(decoded)} expected={width}")

    return (
        PzxRow(
            skips=tuple(skips),
            run_lengths=tuple(run_lengths),
            run_kinds=tuple(run_kinds),
            decoded=bytes(decoded),
        ),
        cursor,
    )


def decode_pzx_row_until_marker(body: bytes, cursor: int) -> tuple[PzxRow, int, int]:
    decoded = bytearray()
    skips: list[int] = []
    run_lengths: list[int] = []
    run_kinds: list[str] = []

    while True:
        if cursor + 2 > len(body):
            raise ValueError("PZX row ended before a row separator")
        word = struct.unpack("<H", body[cursor : cursor + 2])[0]
        if word in (0xFFFE, 0xFFFF):
            return (
                PzxRow(
                    skips=tuple(skips),
                    run_lengths=tuple(run_lengths),
                    run_kinds=tuple(run_kinds),
                    decoded=bytes(decoded),
                ),
                cursor,
                word,
            )

        if word < 0x8000:
            decoded.extend(b"\x00" * word)
            skips.append(word)
            cursor += 2
            continue

        if 0x8000 <= word < 0xC000:
            literal_len = word & 0x3FFF
            cursor += 2
            literal = body[cursor : cursor + literal_len]
            if len(literal) != literal_len:
                raise ValueError("PZX row ended mid-literal")
            decoded.extend(literal)
            run_lengths.append(literal_len)
            run_kinds.append("literal")
            cursor += literal_len
            continue

        if 0xC000 <= word < 0xFDFF:
            repeat_len = word & 0x3FFF
            cursor += 2
            if cursor >= len(body):
                raise ValueError("PZX row ended mid-repeat")
            value = body[cursor]
            decoded.extend(bytes([value]) * repeat_len)
            run_lengths.append(repeat_len)
            run_kinds.append("repeat")
            cursor += 1
            continue

        raise ValueError(f"Unknown PZX opcode family: {word:#06x}")


def read_pzx_row_stream(body: bytes) -> PzxRowStream | None:
    if not body:
        return None

    cursor = 0
    rows: list[PzxRow] = []
    prefix_marker_hex: str | None = None
    row_separator_hexes: list[str] = []
    trailing_sentinel_hex: str | None = None

    if body[:2] in (b"\xfd\xff", b"\xfe\xff"):
        prefix_marker_hex = body[:2].hex()
        cursor = 2

    while cursor < len(body):
        row, cursor, marker = decode_pzx_row_until_marker(body, cursor)

        if marker == 0xFFFE:
            rows.append(row)
            row_separator_hexes.append("feff")
            cursor += 2
            continue

        if row.decoded:
            rows.append(row)
        trailing_sentinel_hex = "ffff"
        cursor += 2
        break

    if cursor != len(body):
        raise ValueError(f"Unexpected trailing PZX bytes: {body[cursor:].hex()}")
    if not rows:
        return None

    return PzxRowStream(
        rows=tuple(rows),
        prefix_marker_hex=prefix_marker_hex,
        row_separator_hexes=tuple(row_separator_hexes),
        trailing_sentinel_hex=trailing_sentinel_hex,
    )


def read_pzx_simple_placement_stream(stream: bytes, chunk_count: int) -> tuple[PzxSimplePlacement, ...] | None:
    if chunk_count <= 0 or len(stream) != chunk_count * 10:
        return None

    placements: list[PzxSimplePlacement] = []
    seen_indices: set[int] = set()

    for cursor in range(0, len(stream), 10):
        record = stream[cursor : cursor + 10]
        if record[1] != 0 or record[2] != 0 or record[4] != 0 or record[9] != 0:
            return None

        chunk_index = record[3]
        if chunk_index >= chunk_count or chunk_index in seen_indices:
            return None

        placements.append(
            PzxSimplePlacement(
                mode=record[0],
                chunk_index=chunk_index,
                x=struct.unpack("<h", record[5:7])[0],
                y=struct.unpack("<h", record[7:9])[0],
            )
        )
        seen_indices.add(chunk_index)

    if len(placements) != chunk_count:
        return None

    return tuple(placements)


def _looks_like_pzx_frame_record(stream: bytes, offset: int) -> bool:
    if offset + 11 > len(stream):
        return False

    item_count = struct.unpack("<H", stream[offset : offset + 2])[0]
    frame_type = stream[offset + 2]
    x = struct.unpack("<h", stream[offset + 3 : offset + 5])[0]
    y = struct.unpack("<h", stream[offset + 5 : offset + 7])[0]
    width = struct.unpack("<H", stream[offset + 7 : offset + 9])[0]
    height = struct.unpack("<H", stream[offset + 9 : offset + 11])[0]

    return (
        1 <= item_count <= 64
        and frame_type == 1
        and -128 <= x <= 64
        and -128 <= y <= 64
        and 1 <= width <= 128
        and 1 <= height <= 128
    )


def _looks_like_pzx_frame_item(stream: bytes, offset: int, chunk_count: int) -> bool:
    if offset + 7 > len(stream):
        return False

    chunk_index = struct.unpack("<H", stream[offset : offset + 2])[0]
    x = struct.unpack("<h", stream[offset + 2 : offset + 4])[0]
    y = struct.unpack("<h", stream[offset + 4 : offset + 6])[0]
    flag = stream[offset + 6]

    return (
        0 <= chunk_index < chunk_count
        and -128 <= x <= 64
        and -128 <= y <= 64
        and flag <= 4
    )


def _is_reasonable_pzx_meta_tuple(chunk_index: int, x: int, y: int, chunk_count: int) -> bool:
    return 0 <= chunk_index < chunk_count and -256 <= x <= 256 and -256 <= y <= 256


def _parse_pzx_meta_tuples(
    payload: bytes,
    chunk_count: int,
    *,
    start: int,
    stride: int,
) -> tuple[int, tuple[PzxMetaTuple, ...]] | None:
    if len(payload) < start or (len(payload) - start) % stride != 0:
        return None

    tuples: list[PzxMetaTuple] = []
    valid_count = 0

    for cursor in range(start, len(payload), stride):
        chunk_index = struct.unpack("<H", payload[cursor : cursor + 2])[0]
        x = struct.unpack("<h", payload[cursor + 2 : cursor + 4])[0]
        y = struct.unpack("<h", payload[cursor + 4 : cursor + 6])[0]
        flag = payload[cursor + 6] if stride == 7 else None

        tuples.append(PzxMetaTuple(chunk_index=chunk_index, x=x, y=y, flag=flag))
        if _is_reasonable_pzx_meta_tuple(chunk_index, x, y, chunk_count) and (flag is None or flag <= 4):
            valid_count += 1

    return (valid_count, tuple(tuples))


def _iter_pzx_meta_markers(stream: bytes) -> tuple[tuple[int, str], ...]:
    hits: list[tuple[int, str]] = []
    offset = 0
    while offset + 5 <= len(stream):
        marker_hex = PZX_META_MARKERS.get(stream[offset : offset + 5])
        if marker_hex is not None:
            hits.append((offset, marker_hex))
            offset += 5
            continue
        offset += 1
    return tuple(hits)


def read_pzx_meta_sections(stream: bytes, chunk_count: int) -> tuple[PzxMetaSection, ...]:
    markers = _iter_pzx_meta_markers(stream)
    boundaries: list[tuple[int, str | None, int]] = []

    if not markers:
        boundaries.append((0, None, 0))
    else:
        first_offset = markers[0][0]
        if first_offset > 0:
            boundaries.append((0, None, 0))
        for offset, marker_hex in markers:
            boundaries.append((offset, marker_hex, 5))

    sections: list[PzxMetaSection] = []
    for index, (offset, marker_hex, marker_size) in enumerate(boundaries):
        start = offset + marker_size
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(stream)
        payload = stream[start:end]
        if not payload:
            continue

        best_layout = "opaque"
        best_header_hex: str | None = None
        best_tuple_count = 0
        best_valid_tuple_count = 0
        best_tuples: tuple[PzxMetaTuple, ...] = ()

        candidates: list[tuple[int, int, int, str, str | None, tuple[PzxMetaTuple, ...]]] = []
        for start_offset, stride, layout in (
            (0, 7, "flagged-tuples"),
            (3, 7, "header3+flagged-tuples"),
            (0, 6, "plain-tuples"),
            (3, 6, "header3+plain-tuples"),
        ):
            parsed = _parse_pzx_meta_tuples(payload, chunk_count, start=start_offset, stride=stride)
            if parsed is None:
                continue
            valid_count, tuples = parsed
            header_hex = payload[:3].hex() if start_offset == 3 and len(payload) >= 3 else None
            candidates.append((valid_count, len(tuples), -start_offset, layout, header_hex, tuples))

        if candidates:
            valid_count, tuple_count, _, layout, header_hex, tuples = max(candidates)
            if tuple_count > 0 and valid_count == tuple_count:
                best_layout = layout
                best_header_hex = header_hex
                best_tuple_count = tuple_count
                best_valid_tuple_count = valid_count
                best_tuples = tuples

        sections.append(
            PzxMetaSection(
                offset=offset,
                marker_hex=marker_hex,
                payload=payload,
                layout=best_layout,
                header_hex=best_header_hex,
                tuple_count=best_tuple_count,
                valid_tuple_count=best_valid_tuple_count,
                tuples=best_tuples,
            )
        )

    return tuple(sections)


def read_pzx_frame_record_stream(stream: bytes, chunk_count: int) -> PzxFrameRecordStream | None:
    if chunk_count <= 0 or not _looks_like_pzx_frame_record(stream, 0):
        return None

    cursor = 0
    records: list[PzxFrameRecord] = []

    while _looks_like_pzx_frame_record(stream, cursor):
        item_count = struct.unpack("<H", stream[cursor : cursor + 2])[0]
        frame_type = stream[cursor + 2]
        x = struct.unpack("<h", stream[cursor + 3 : cursor + 5])[0]
        y = struct.unpack("<h", stream[cursor + 5 : cursor + 7])[0]
        width = struct.unpack("<H", stream[cursor + 7 : cursor + 9])[0]
        height = struct.unpack("<H", stream[cursor + 9 : cursor + 11])[0]

        items: list[PzxFrameItem] = []
        control_chunks: list[bytes] = []
        next_cursor = cursor + 11
        valid = True

        while len(items) < item_count:
            if _looks_like_pzx_frame_item(stream, next_cursor, chunk_count):
                record = stream[next_cursor : next_cursor + 7]
                chunk_index = struct.unpack("<H", record[:2])[0]
                items.append(
                    PzxFrameItem(
                        chunk_index=chunk_index,
                        x=struct.unpack("<h", record[2:4])[0],
                        y=struct.unpack("<h", record[4:6])[0],
                        flag=record[6],
                    )
                )
                next_cursor += 7
                continue

            if next_cursor + 5 <= len(stream) and _looks_like_pzx_frame_item(stream, next_cursor + 5, chunk_count):
                control_chunks.append(stream[next_cursor : next_cursor + 5])
                next_cursor += 5
                continue

            valid = False
            break

        if not valid:
            break

        while next_cursor + 5 <= len(stream) and not _looks_like_pzx_frame_record(stream, next_cursor):
            if _looks_like_pzx_frame_record(stream, next_cursor + 5):
                control_chunks.append(stream[next_cursor : next_cursor + 5])
                next_cursor += 5
                continue
            break

        record_continues = next_cursor < len(stream) and _looks_like_pzx_frame_record(stream, next_cursor)

        records.append(
            PzxFrameRecord(
                offset=cursor,
                item_count=item_count,
                frame_type=frame_type,
                x=x,
                y=y,
                width=width,
                height=height,
                items=tuple(items),
                control_chunks=tuple(control_chunks),
            )
        )
        if not record_continues:
            cursor = next_cursor
            break
        cursor = next_cursor

    if not records:
        return None

    return PzxFrameRecordStream(records=tuple(records), consumed=cursor, trailing=stream[cursor:])


def _is_reasonable_pzx_animation_frame(delay: int, x: int, y: int) -> bool:
    return 0 <= delay <= 32 and -256 <= x <= 256 and -256 <= y <= 256


def _read_pzx_animation_clip_exact(payload: bytes, start: int, end: int) -> PzxAnimationClip | None:
    if not (0 <= start < end <= len(payload)):
        return None

    cursor = start
    frame_count = payload[cursor]
    if frame_count == 0:
        return None
    cursor += 1

    frames: list[PzxAnimationFrame] = []
    for _ in range(frame_count):
        if cursor + 8 > end:
            return None

        frames.append(
            PzxAnimationFrame(
                frame_index=struct.unpack("<H", payload[cursor : cursor + 2])[0],
                delay=payload[cursor + 2],
                x=struct.unpack("<h", payload[cursor + 3 : cursor + 5])[0],
                y=struct.unpack("<h", payload[cursor + 5 : cursor + 7])[0],
                control=payload[cursor + 7],
            )
        )
        cursor += 8

    if cursor != end:
        return None

    return PzxAnimationClip(offset=start, frame_count=frame_count, frames=tuple(frames))


def _read_pzx_pzf_bbox_total(format_variant: int, bbox_token0: int, bbox_token1: int) -> int | None:
    if format_variant == 0:
        return (bbox_token0 >> 4) + (bbox_token0 & 0x0F)
    if format_variant in (1, 2):
        return bbox_token0
    if format_variant == 3:
        return bbox_token0 + bbox_token1
    return None


def _read_pzx_pzf_bbox_record(
    payload: bytes,
    cursor: int,
    format_variant: int,
) -> tuple[PzxPzfBoundingBoxRecord, int] | None:
    if format_variant == 0:
        if cursor + 4 > len(payload):
            return None
        raw = payload[cursor : cursor + 4]
        values = struct.unpack("<bbBB", raw)
        return (PzxPzfBoundingBoxRecord(raw=raw, values=values), cursor + 4)

    if format_variant == 2:
        if cursor + 4 > len(payload):
            return None
        raw = payload[cursor : cursor + 4]
        values = struct.unpack("<hh", raw)
        return (PzxPzfBoundingBoxRecord(raw=raw, values=values), cursor + 4)

    if format_variant in (1, 3):
        if cursor + 8 > len(payload):
            return None
        raw = payload[cursor : cursor + 8]
        values = struct.unpack("<hhhh", raw)
        return (PzxPzfBoundingBoxRecord(raw=raw, values=values), cursor + 8)

    return None


def _is_pzx_effectex_selector(value: int) -> bool:
    return value in PZX_EFFECTEX_SELECTOR_DRAW_OPS


def _read_pzx_effectex_extra(
    payload: bytes,
    body_start: int,
    end: int,
    extra_flag: int,
) -> tuple[bytes, int, int | None, int | None] | None:
    cursor = body_start
    extra = bytearray()
    last_selector: int | None = None
    last_parameter: int | None = None

    for _ in range(extra_flag):
        if cursor >= end:
            return None
        value = payload[cursor]
        cursor += 1
        extra.append(value)
        if not _is_pzx_effectex_selector(value):
            continue
        if cursor + 4 > end:
            return None
        last_selector = value
        last_parameter = struct.unpack("<I", payload[cursor : cursor + 4])[0]
        cursor += 4

    return (bytes(extra), cursor, last_selector, last_parameter)


def _read_pzx_pzf_frame_exact(
    payload: bytes,
    start: int,
    end: int,
    format_variant: int,
    *,
    subframe_layout: str = "base",
    max_subframe_index: int | None = None,
) -> PzxPzfFrame | None:
    if not (0 <= start < end <= len(payload)):
        return None

    cursor = start
    if cursor + 2 > end:
        return None

    subframe_count = payload[cursor]
    cursor += 1
    bbox_token0 = payload[cursor]
    cursor += 1
    bbox_token1 = 0

    if format_variant == 3:
        if cursor >= end:
            return None
        bbox_token1 = payload[cursor]
        cursor += 1

    bbox_total = _read_pzx_pzf_bbox_total(format_variant, bbox_token0, bbox_token1)
    if bbox_total is None:
        return None

    bboxes: list[PzxPzfBoundingBoxRecord] = []
    for _ in range(bbox_total):
        parsed_bbox = _read_pzx_pzf_bbox_record(payload, cursor, format_variant)
        if parsed_bbox is None:
            return None
        bbox, cursor = parsed_bbox
        if cursor > end:
            return None
        bboxes.append(bbox)

    @lru_cache(maxsize=None)
    def parse_subframes(index: int, position: int) -> tuple[PzxPzfSubFrame, ...] | None:
        if index == subframe_count:
            if position == end:
                return ()
            return None

        if position + 7 > end:
            return None

        subframe_index = struct.unpack("<H", payload[position : position + 2])[0]
        if max_subframe_index is not None and subframe_index > max_subframe_index:
            return None
        x = struct.unpack("<h", payload[position + 2 : position + 4])[0]
        y = struct.unpack("<h", payload[position + 4 : position + 6])[0]
        extra_flag = payload[position + 6]
        body_start = position + 7

        if subframe_layout == "effectex":
            parsed_extra = _read_pzx_effectex_extra(payload, body_start, end, extra_flag)
            if parsed_extra is None:
                return None
            extra, next_position, effectex_selector, effectex_parameter = parsed_extra
            tail = parse_subframes(index + 1, next_position)
            if tail is None:
                return None
            effectex_draw_op = None
            effectex_module = None
            if effectex_selector is not None:
                effectex_draw_op = PZX_EFFECTEX_SELECTOR_DRAW_OPS[effectex_selector]
                if 0x71 <= effectex_selector <= 0x74:
                    effectex_module = effectex_selector - 0x71
            return (
                PzxPzfSubFrame(
                    subframe_index=subframe_index,
                    x=x,
                    y=y,
                    extra_flag=extra_flag,
                    extra=extra,
                    effectex_selector=effectex_selector,
                    effectex_parameter=effectex_parameter,
                    effectex_draw_op=effectex_draw_op,
                    effectex_module=effectex_module,
                ),
                *tail,
            )

        extra_len_candidates = (0,) if extra_flag == 0 else tuple(
            sorted(
                candidate
                for candidate in {extra_flag, extra_flag + 4}
                if body_start + candidate <= end
            )
        )
        if not extra_len_candidates:
            return None

        for extra_len in extra_len_candidates:
            tail = parse_subframes(index + 1, body_start + extra_len)
            if tail is None:
                continue
            extra = payload[body_start : body_start + extra_len]
            return (
                PzxPzfSubFrame(
                    subframe_index=subframe_index,
                    x=x,
                    y=y,
                    extra_flag=extra_flag,
                    extra=extra,
                ),
                *tail,
            )

        return None

    subframes = parse_subframes(0, cursor)
    if subframes is None:
        return None

    return PzxPzfFrame(
        offset=start,
        length=end - start,
        subframe_count=subframe_count,
        bbox_token0=bbox_token0,
        bbox_token1=bbox_token1,
        bbox_total_count=bbox_total,
        bboxes=tuple(bboxes),
        subframes=subframes,
    )


def read_pzx_animation_clip_stream(stream: bytes) -> PzxAnimationClipStream | None:
    if len(stream) < 9:
        return None

    cursor = 0
    clips: list[PzxAnimationClip] = []

    while cursor < len(stream):
        clip_offset = cursor
        frame_count = stream[cursor]
        if frame_count == 0:
            return None
        cursor += 1

        frames: list[PzxAnimationFrame] = []
        for _ in range(frame_count):
            if cursor + 8 > len(stream):
                return None

            frame_index = struct.unpack("<H", stream[cursor : cursor + 2])[0]
            delay = stream[cursor + 2]
            x = struct.unpack("<h", stream[cursor + 3 : cursor + 5])[0]
            y = struct.unpack("<h", stream[cursor + 5 : cursor + 7])[0]
            control = stream[cursor + 7]

            if not _is_reasonable_pzx_animation_frame(delay, x, y):
                return None

            frames.append(
                PzxAnimationFrame(
                    frame_index=frame_index,
                    delay=delay,
                    x=x,
                    y=y,
                    control=control,
                )
            )
            cursor += 8

        clips.append(
            PzxAnimationClip(
                offset=clip_offset,
                frame_count=frame_count,
                frames=tuple(frames),
            )
        )

    if not clips:
        return None

    return PzxAnimationClipStream(clips=tuple(clips))


def read_pzx_indexed_animation_clip_stream(
    payload: bytes,
    clip_offsets: tuple[int, ...] | list[int],
) -> PzxAnimationClipStream | None:
    if not clip_offsets:
        return None

    offsets = tuple(int(offset) for offset in clip_offsets)
    if any(offset < 0 or offset > len(payload) for offset in offsets):
        return None
    if any(offsets[index] > offsets[index + 1] for index in range(len(offsets) - 1)):
        return None

    clips: list[PzxAnimationClip] = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(payload)
        clip = _read_pzx_animation_clip_exact(payload, start, end)
        if clip is None:
            return None
        clips.append(clip)

    return PzxAnimationClipStream(clips=tuple(clips))


def read_pzx_indexed_pzf_frame_stream(
    payload: bytes,
    frame_offsets: tuple[int, ...] | list[int],
    format_variant: int,
    *,
    subframe_layout: str = "base",
    max_subframe_index: int | None = None,
) -> PzxPzfFrameStream | None:
    if not frame_offsets:
        return None

    if subframe_layout not in {"base", "effectex"}:
        raise ValueError(f"Unsupported PZF subframe layout: {subframe_layout}")

    offsets = tuple(int(offset) for offset in frame_offsets)
    if any(offset < 0 or offset > len(payload) for offset in offsets):
        return None
    if any(offsets[index] > offsets[index + 1] for index in range(len(offsets) - 1)):
        return None

    frames: list[PzxPzfFrame] = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(payload)
        frame = _read_pzx_pzf_frame_exact(
            payload,
            start,
            end,
            format_variant,
            subframe_layout=subframe_layout,
            max_subframe_index=max_subframe_index,
        )
        if frame is None:
            return None
        frames.append(frame)

    return PzxPzfFrameStream(
        format_variant=format_variant,
        frames=tuple(frames),
        subframe_layout=subframe_layout,
    )


def read_pzx_indexed_effectex_pzf_frame_stream(
    payload: bytes,
    frame_offsets: tuple[int, ...] | list[int],
    format_variant: int,
    *,
    max_subframe_index: int | None = None,
) -> PzxPzfFrameStream | None:
    return read_pzx_indexed_pzf_frame_stream(
        payload,
        frame_offsets,
        format_variant,
        subframe_layout="effectex",
        max_subframe_index=max_subframe_index,
    )


def read_pzx_root_resource_offsets(data: bytes) -> tuple[int, int, int] | None:
    if len(data) < 16 or data[:4] != b"PZX\x01":
        return None

    return (
        struct.unpack("<I", data[4:8])[0],
        struct.unpack("<I", data[8:12])[0],
        struct.unpack("<I", data[12:16])[0],
    )


def _read_pzd_image_descriptor(
    block: bytes, descriptor_offset: int
) -> tuple[int, int, int, int, int, int] | None:
    if descriptor_offset < 0 or descriptor_offset + 16 > len(block):
        return None
    descriptor = block[descriptor_offset : descriptor_offset + 16]
    width = struct.unpack("<H", descriptor[:2])[0]
    height = struct.unpack("<H", descriptor[2:4])[0]
    mode = descriptor[4]
    extra_flag = descriptor[5]
    if struct.unpack("<H", descriptor[6:8])[0] != 0xCDCD:
        return None
    unpacked_size = struct.unpack("<I", descriptor[8:12])[0]
    packed_size = struct.unpack("<I", descriptor[12:16])[0]
    return (width, height, mode, extra_flag, unpacked_size, packed_size)


def read_pzx_pzd_resource(data: bytes, offset: int, end_offset: int) -> PzxPzdResource | None:
    if offset < 0 or offset + 4 > len(data) or end_offset > len(data) or offset >= end_offset:
        return None

    type_code = data[offset]
    content_count = struct.unpack("<H", data[offset + 1 : offset + 3])[0]
    flags = data[offset + 3]
    if content_count <= 0:
        return None

    region = data[offset:end_offset]
    hits = find_zlib_streams(region, min_out=1)
    zlib_streams = tuple(
        PzxPzdZlibStream(
            index=index,
            offset=offset + hit.offset,
            consumed=hit.consumed,
            decoded_len=len(hit.decoded),
        )
        for index, hit in enumerate(hits)
    )
    palette_probe = data[offset + 4] if offset + 4 < end_offset else None

    if type_code == 7:
        global_palette_count = None
        if flags != 0:
            global_palette_count = palette_probe
            if global_palette_count is None:
                return None
            table_start = offset + 5 + global_palette_count * 2
        else:
            table_start = offset + 4
        table_end = table_start + content_count * 4
        if table_end > end_offset:
            return None

        index_offsets = tuple(
            struct.unpack("<I", data[table_start + index * 4 : table_start + index * 4 + 4])[0]
            for index in range(content_count)
        )

        row_streams: list[PzxRowStream] = []
        image_records: list[PzxPzdImageRecord] = []
        raw_zlib_streams: list[PzxPzdZlibStream] = []
        for index, index_offset in enumerate(index_offsets):
            if index_offset < offset or index_offset >= end_offset:
                return None
            block_offset = index_offset - offset
            descriptor_offset = block_offset
            palette_count: int | None = None
            if flags == 0:
                palette_count = region[block_offset]
                descriptor_offset = block_offset + 1 + palette_count * 2
            descriptor = _read_pzd_image_descriptor(region, descriptor_offset)
            if descriptor is None:
                return None
            width, height, mode, extra_flag, unpacked_size, packed_size = descriptor
            payload_offset = descriptor_offset + 16
            payload_end = payload_offset + packed_size
            if packed_size <= 0 or payload_end > len(region):
                return None
            payload = region[payload_offset:payload_end]
            try:
                decoded = zlib.decompress(payload)
            except zlib.error:
                return None
            if len(decoded) != unpacked_size:
                return None
            row_stream = read_pzx_row_stream(decoded)
            if row_stream is None:
                return None
            if row_stream.width != width or row_stream.height != height:
                return None
            row_streams.append(row_stream)
            raw_zlib_streams.append(
                PzxPzdZlibStream(
                    index=index,
                    offset=offset + payload_offset,
                    consumed=packed_size,
                    decoded_len=len(decoded),
                )
            )
            image_records.append(
                PzxPzdImageRecord(
                    index=index,
                    index_offset=index_offset,
                    block_offset=offset + block_offset,
                    descriptor_offset=offset + descriptor_offset,
                    payload_offset=offset + payload_offset,
                    palette_count=palette_count,
                    width=width,
                    height=height,
                    mode=mode,
                    extra_flag=extra_flag,
                    unpacked_size=unpacked_size,
                    packed_size=packed_size,
                )
            )
        return PzxPzdResource(
            offset=offset,
            end_offset=end_offset,
            type_code=type_code,
            content_count=content_count,
            flags=flags,
            palette_probe=palette_probe,
            table_start=table_start,
            index_offset_mode="file-absolute",
            index_offsets=index_offsets,
            global_palette_count=global_palette_count,
            packed_size=None,
            unpacked_size=None,
            payload_offset=None,
            zlib_streams=tuple(raw_zlib_streams),
            row_streams=tuple(row_streams),
            first_stream=None,
            image_records=tuple(image_records),
        )

    if type_code == 8:
        global_palette_count = None
        compressed_header_offset = offset + 4
        if flags != 0:
            global_palette_count = palette_probe
            if global_palette_count is None:
                return None
            compressed_header_offset = offset + 5 + global_palette_count * 2
        if compressed_header_offset + 8 > end_offset:
            return None
        unpacked_size = struct.unpack("<I", data[compressed_header_offset : compressed_header_offset + 4])[0]
        packed_size = struct.unpack("<I", data[compressed_header_offset + 4 : compressed_header_offset + 8])[0]
        payload_offset = compressed_header_offset + 8
        payload_end = payload_offset + packed_size
        if payload_end > end_offset or packed_size <= 0:
            return None
        payload = data[payload_offset:payload_end]
        try:
            decoded = zlib.decompress(payload)
        except zlib.error:
            return None
        if len(decoded) != unpacked_size or len(decoded) < 4:
            return None
        table_span = struct.unpack("<I", decoded[:4])[0]
        first_stream = read_pzx_first_stream(decoded, table_span)
        if first_stream is None or len(first_stream.chunks) != content_count:
            return None
        image_records_list: list[PzxPzdImageRecord] = []
        for index, (chunk_offset, chunk) in enumerate(zip(first_stream.offsets, first_stream.chunks)):
            magic = bytes.fromhex(chunk.magic_hex)
            image_records_list.append(
                PzxPzdImageRecord(
                    index=index,
                    index_offset=chunk_offset,
                    block_offset=chunk_offset,
                    descriptor_offset=chunk_offset,
                    payload_offset=chunk_offset + 16,
                    palette_count=None,
                    width=chunk.width,
                    height=chunk.height,
                    mode=magic[0],
                    extra_flag=magic[1],
                    unpacked_size=chunk.declared_payload_len,
                    packed_size=chunk.reserved,
                )
            )
        image_records = tuple(image_records_list)
        return PzxPzdResource(
            offset=offset,
            end_offset=end_offset,
            type_code=type_code,
            content_count=content_count,
            flags=flags,
            palette_probe=palette_probe,
            table_start=0,
            index_offset_mode="decoded-relative",
            index_offsets=first_stream.offsets,
            global_palette_count=global_palette_count,
            packed_size=packed_size,
            unpacked_size=unpacked_size,
            payload_offset=payload_offset,
            zlib_streams=(
                PzxPzdZlibStream(
                    index=0,
                    offset=payload_offset,
                    consumed=packed_size,
                    decoded_len=len(decoded),
                ),
            ),
            row_streams=(),
            first_stream=first_stream,
            image_records=image_records,
        )

    return None


def read_pzx_embedded_resource(data: bytes, offset: int, kind: str) -> PzxEmbeddedResource | None:
    if offset < 0 or offset + 3 > len(data):
        return None

    header = data[offset]
    content_count = struct.unpack("<H", data[offset + 1 : offset + 3])[0]
    if content_count <= 0:
        return None

    table_start = offset + 3
    table_end = table_start + content_count * 4
    if table_end > len(data):
        return None

    index_offsets = tuple(
        struct.unpack("<I", data[table_start + index * 4 : table_start + index * 4 + 4])[0]
        for index in range(content_count)
    )
    storage_mode = header & 0x0F
    format_variant = header >> 4

    if storage_mode == 0:
        payload_offset = table_end
        payload = data[payload_offset:]
        packed_size = None
        unpacked_size = len(payload)
    else:
        if table_end + 8 > len(data):
            return None
        unpacked_size = struct.unpack("<I", data[table_end : table_end + 4])[0]
        packed_size = struct.unpack("<I", data[table_end + 4 : table_end + 8])[0]
        payload_offset = table_end + 8
        payload_end = payload_offset + packed_size
        if payload_end > len(data):
            return None
        try:
            payload = zlib.decompress(data[payload_offset:payload_end])
        except zlib.error:
            return None
        if len(payload) != unpacked_size:
            return None

    return PzxEmbeddedResource(
        kind=kind,
        offset=offset,
        header=header,
        storage_mode=storage_mode,
        format_variant=format_variant,
        content_count=content_count,
        index_offsets=index_offsets,
        packed_size=packed_size,
        unpacked_size=unpacked_size,
        payload_offset=payload_offset,
        payload=payload,
    )


def read_pzx_embedded_resources(data: bytes) -> tuple[PzxEmbeddedResource, ...] | None:
    offsets = read_pzx_root_resource_offsets(data)
    if offsets is None:
        return None

    resources: list[PzxEmbeddedResource] = []
    for kind, offset in zip(PZX_RESOURCE_KINDS, offsets):
        resource = read_pzx_embedded_resource(data, offset, kind)
        if resource is None:
            return None
        resources.append(resource)

    return tuple(resources)


def read_pzx_first_stream(stream: bytes, table_span: int) -> PzxFirstStream | None:
    if table_span <= 0 or table_span % 4 != 0 or len(stream) < table_span:
        return None

    chunk_count = table_span // 4
    offsets = [struct.unpack("<I", stream[index : index + 4])[0] for index in range(0, table_span, 4)]

    if offsets[0] != table_span:
        return None
    if any(offset < 0 or offset > len(stream) for offset in offsets):
        return None
    if any(offsets[index] > offsets[index + 1] for index in range(len(offsets) - 1)):
        return None

    chunks: list[PzxChunk] = []

    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(stream)
        chunk = stream[start:end]
        if len(chunk) < 16:
            return None

        width = struct.unpack("<H", chunk[:2])[0]
        height = struct.unpack("<H", chunk[2:4])[0]
        body = chunk[16:]
        row_stream = read_pzx_row_stream(body)
        if row_stream is None:
            return None

        if row_stream.height != height:
            raise ValueError(f"PZX chunk row count mismatch: rows={row_stream.height} height={height}")
        if row_stream.width != width:
            raise ValueError(f"PZX chunk width mismatch: rows={row_stream.width} width={width}")
        if row_stream.decoded_pixel_count != width * height:
            raise ValueError("PZX chunk decoded pixel count mismatch")

        chunks.append(
            PzxChunk(
                index=index,
                width=width,
                height=height,
                magic_hex=chunk[4:8].hex(),
                declared_payload_len=struct.unpack("<I", chunk[8:12])[0],
                reserved=struct.unpack("<I", chunk[12:16])[0],
                body=body,
                rows=row_stream.rows,
                prefix_marker_hex=row_stream.prefix_marker_hex,
                row_separator_hexes=row_stream.row_separator_hexes,
                trailing_sentinel_hex=row_stream.trailing_sentinel_hex,
            )
        )

    return PzxFirstStream(table_span=table_span, offsets=tuple(offsets), chunks=tuple(chunks))


def _extract_runs(text: str) -> list[str]:
    runs: list[str] = []
    current: list[str] = []

    for char in text:
        if _is_text_char(char):
            current.append(char)
            continue

        if current:
            candidate = "".join(current).strip(" -")
            if len(candidate) >= 3 and any(ch.isalnum() or ("\uac00" <= ch <= "\ud7a3") for ch in candidate):
                runs.append(candidate)
            current = []

    if current:
        candidate = "".join(current).strip(" -")
        if len(candidate) >= 3 and any(ch.isalnum() or ("\uac00" <= ch <= "\ud7a3") for ch in candidate):
            runs.append(candidate)

    return runs


def extract_strings(data: bytes, preferred_encoding: str | None = None) -> tuple[str | None, list[str]]:
    encodings: list[str] = []
    if preferred_encoding is not None:
        encodings.append(preferred_encoding)
    for fallback in ("utf-8", "cp949"):
        if fallback not in encodings:
            encodings.append(fallback)

    best_encoding: str | None = None
    best_matches: list[str] = []
    best_score = 0

    for encoding in encodings:
        try:
            chunks = [chunk.decode(encoding, errors="ignore") for chunk in data.split(b"\x00") if chunk]
        except LookupError:
            continue

        matches: list[str] = []
        score = 0
        for chunk in chunks:
            for candidate in _extract_runs(chunk):
                matches.append(candidate)
                score += len(candidate)

        if score > best_score:
            best_score = score
            best_matches = matches
            best_encoding = encoding

    deduped: list[str] = []
    seen: set[str] = set()
    for item in best_matches:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)

    if best_score == 0:
        return None, []

    return best_encoding, deduped
