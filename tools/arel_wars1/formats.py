from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Sequence
import zlib


ZLIB_HEADERS = {0x01, 0x5E, 0x9C, 0xDA}
SCRIPT_PREFIX_MNEMONICS: dict[int, str] = {
    0x01: "set-right-portrait",
    0x03: "set-left-portrait",
    0x04: "set-expression",
    0x05: "cmd-05",
    0x06: "cmd-06",
    0x07: "cmd-07",
    0x08: "cmd-08",
    0x09: "cmd-09",
    0x0A: "cmd-0a",
    0x0B: "cmd-0b",
}
SCRIPT_PREFIX_ARG_COUNTS: dict[int, int] = {
    0x01: 2,
    0x03: 2,
}
PZX_META_MARKERS: dict[bytes, str] = {
    bytes.fromhex("67ff000000"): "67ff000000",
    bytes.fromhex("6778000000"): "6778000000",
    bytes.fromhex("6605000000"): "6605000000",
    bytes.fromhex("6607000000"): "6607000000",
    bytes.fromhex("6608000000"): "6608000000",
    bytes.fromhex("660a000000"): "660a000000",
    bytes.fromhex("660c000000"): "660c000000",
    bytes.fromhex("6764000000"): "6764000000",
    bytes.fromhex("6796000000"): "6796000000",
    bytes.fromhex("67b4000000"): "67b4000000",
    bytes.fromhex("67be000000"): "67be000000",
    bytes.fromhex("67c8000000"): "67c8000000",
    bytes.fromhex("6700000000"): "6700000000",
}
MAX_PZX_META_PREFIX_LEN = 20
MAX_PZX_META_SUFFIX_LEN = 12


def _is_text_char(char: str) -> bool:
    if char.isascii():
        return char.isalnum() or char in " .,!?'-:;()[]/&+\""
    return "\uac00" <= char <= "\ud7a3"


def u16_to_i16(value: int) -> int:
    return struct.unpack("<h", struct.pack("<H", value & 0xFFFF))[0]


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
class MplFile:
    header_words: tuple[int, int, int, int, int, int]
    color_count: int
    bank_a: tuple[int, ...]
    bank_b: tuple[int, ...]

    @property
    def actual_word_count(self) -> int:
        return len(self.header_words) + len(self.bank_a) + len(self.bank_b)

    @property
    def expected_header_word3(self) -> int:
        return self.color_count * 2 + 11

    @property
    def expected_header_word5(self) -> int:
        return 7936 + self.color_count

    @property
    def header_matches_current_model(self) -> bool:
        return (
            self.header_words[0] == 560
            and self.header_words[1] == 10
            and self.header_words[2] == 0
            and self.header_words[3] == self.expected_header_word3
            and self.header_words[4] == 0
            and self.header_words[5] == self.expected_header_word5
        )

    def bank(self, label: str) -> tuple[int, ...]:
        if label.lower() == "b":
            return self.bank_b
        return self.bank_a


@dataclass(frozen=True)
class ScriptEvent:
    offset: int
    kind: str
    prefix_hex: str
    speaker: str | None
    speaker_tag: int | None
    text: str
    byte_length: int


@dataclass(frozen=True)
class ScriptPrefixCommand:
    opcode: int
    args: tuple[int, ...]
    mnemonic: str


@dataclass(frozen=True)
class ScriptPrefixParse:
    commands: tuple[ScriptPrefixCommand, ...]
    trailing_hex: str | None


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
    timing_ms: int | None
    extended_layout: str | None
    extended_prefix_hex: str | None
    extended_suffix_hex: str | None
    extended_tuple_stride: int | None
    extended_tuple_count: int
    extended_valid_tuple_count: int
    extended_tuples: tuple[PzxMetaTuple, ...]


@dataclass(frozen=True)
class PtcFile:
    fields_u16: tuple[int, ...]
    fields_i16: tuple[int, ...]
    trailer_bytes: bytes


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


def read_mpl(data: bytes) -> MplFile | None:
    if len(data) < 16 or len(data) % 2 != 0:
        return None

    words = [struct.unpack("<H", data[index : index + 2])[0] for index in range(0, len(data), 2)]
    if len(words) < 8 or (len(words) - 6) % 2 != 0:
        return None

    color_count = (len(words) - 6) // 2
    return MplFile(
        header_words=tuple(int(word) for word in words[:6]),  # type: ignore[arg-type]
        color_count=color_count,
        bank_a=tuple(int(word) for word in words[6 : 6 + color_count]),
        bank_b=tuple(int(word) for word in words[6 + color_count : 6 + 2 * color_count]),
    )


def read_ptc(data: bytes) -> PtcFile | None:
    if len(data) < 50:
        return None

    even_size = len(data) - (len(data) % 2)
    fields_u16 = tuple(struct.unpack("<H", data[index : index + 2])[0] for index in range(0, even_size, 2))
    return PtcFile(
        fields_u16=fields_u16,
        fields_i16=tuple(u16_to_i16(value) for value in fields_u16),
        trailer_bytes=data[even_size:],
    )


def parse_script_prefix(prefix: bytes | str) -> ScriptPrefixParse:
    if isinstance(prefix, str):
        prefix_bytes = bytes.fromhex(prefix) if prefix else b""
    else:
        prefix_bytes = prefix

    commands: list[ScriptPrefixCommand] = []
    cursor = 0

    while cursor < len(prefix_bytes):
        if prefix_bytes[cursor] == 0x00 and cursor == len(prefix_bytes) - 1:
            cursor += 1
            break

        opcode = prefix_bytes[cursor]
        arg_count = SCRIPT_PREFIX_ARG_COUNTS.get(opcode, 1)
        next_cursor = cursor + 1 + arg_count
        if next_cursor > len(prefix_bytes):
            break
        commands.append(
            ScriptPrefixCommand(
                opcode=opcode,
                args=tuple(prefix_bytes[cursor + 1 : next_cursor]),
                mnemonic=SCRIPT_PREFIX_MNEMONICS.get(opcode, f"cmd-{opcode:02x}"),
            )
        )
        cursor = next_cursor

    trailing = prefix_bytes[cursor:].hex() if cursor < len(prefix_bytes) else None
    return ScriptPrefixParse(commands=tuple(commands), trailing_hex=trailing or None)


def rgb565_rgba(word: int, *, alpha: int = 255) -> tuple[int, int, int, int]:
    r = ((word >> 11) & 0x1F) * 255 // 31
    g = ((word >> 5) & 0x3F) * 255 // 63
    b = (word & 0x1F) * 255 // 31
    return (r, g, b, alpha)


def mpl_index_to_rgba(index: int, palette_words: Sequence[int]) -> tuple[int, int, int, int]:
    if index <= 0 or index >= len(palette_words):
        return (0, 0, 0, 0)
    return rgb565_rgba(int(palette_words[index]))


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


def decode_pzx_marker_timing_ms(marker_hex: str | None) -> int | None:
    if marker_hex is None:
        return None

    marker = bytes.fromhex(marker_hex)
    if len(marker) != 5:
        return None
    if marker[0] == 0x66:
        return marker[1] * 10
    if marker[0] == 0x67:
        return marker[1]
    return None


def _find_extended_pzx_meta_candidate(
    payload: bytes,
    chunk_count: int,
) -> tuple[str, str | None, str | None, int, int, tuple[PzxMetaTuple, ...]] | None:
    candidates: list[tuple[int, int, int, int, int, str, str | None, str | None, tuple[PzxMetaTuple, ...]]] = []
    for stride, layout_name in ((7, "flagged-tuples"), (6, "plain-tuples")):
        for prefix_len in range(0, MAX_PZX_META_PREFIX_LEN + 1):
            for suffix_len in range(0, MAX_PZX_META_SUFFIX_LEN + 1):
                if len(payload) < prefix_len + suffix_len + stride:
                    continue
                parsed = _parse_pzx_meta_tuples(
                    payload,
                    chunk_count,
                    start=prefix_len,
                    stride=stride,
                )
                if parsed is None:
                    continue
                valid_count, tuples = parsed
                tuple_count = len(tuples)
                if tuple_count == 0 or valid_count != tuple_count:
                    continue
                covered = prefix_len + tuple_count * stride + suffix_len
                if covered != len(payload):
                    continue
                prefix_hex = payload[:prefix_len].hex() if prefix_len > 0 else None
                suffix_hex = payload[len(payload) - suffix_len :].hex() if suffix_len > 0 else None
                layout = layout_name
                if prefix_len > 0:
                    layout = f"prefix{prefix_len}+{layout}"
                if suffix_len > 0:
                    layout = f"{layout}+suffix{suffix_len}"
                candidates.append(
                    (
                        valid_count,
                        tuple_count,
                        1 if stride == 7 else 0,
                        -prefix_len,
                        -suffix_len,
                        layout,
                        prefix_hex,
                        suffix_hex,
                        tuples,
                    )
                )

    if not candidates:
        return None

    valid_count, _, _, _, _, layout, prefix_hex, suffix_hex, tuples = max(candidates)
    stride = 7 if "flagged" in layout else 6
    return (layout, prefix_hex, suffix_hex, stride, valid_count, tuples)


def get_pzx_meta_effective_tuples(section: PzxMetaSection) -> tuple[PzxMetaTuple, ...]:
    if section.tuples:
        return section.tuples
    if section.extended_tuples and section.extended_valid_tuple_count == section.extended_tuple_count:
        return section.extended_tuples
    return ()


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
        extended_layout: str | None = None
        extended_prefix_hex: str | None = None
        extended_suffix_hex: str | None = None
        extended_tuple_stride: int | None = None
        extended_tuple_count = 0
        extended_valid_tuple_count = 0
        extended_tuples: tuple[PzxMetaTuple, ...] = ()

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

        extended = _find_extended_pzx_meta_candidate(payload, chunk_count)
        if extended is not None:
            (
                extended_layout,
                extended_prefix_hex,
                extended_suffix_hex,
                extended_tuple_stride,
                extended_valid_tuple_count,
                extended_tuples,
            ) = extended
            extended_tuple_count = len(extended_tuples)

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
                timing_ms=decode_pzx_marker_timing_ms(marker_hex),
                extended_layout=extended_layout,
                extended_prefix_hex=extended_prefix_hex,
                extended_suffix_hex=extended_suffix_hex,
                extended_tuple_stride=extended_tuple_stride,
                extended_tuple_count=extended_tuple_count,
                extended_valid_tuple_count=extended_valid_tuple_count,
                extended_tuples=extended_tuples,
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


def _decode_script_text(data: bytes, encoding: str) -> str | None:
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        return None

    if not text:
        return None

    printable = sum(1 for char in text if char.isprintable() and char not in "\x0b\x0c")
    if printable / len(text) < 0.95:
        return None
    return text


def _looks_like_script_speaker(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 24:
        return False
    allowed_punctuation = set(" .'!-&*/()")
    if not all(
        char.isalnum() or ("\uac00" <= char <= "\ud7a3") or char in allowed_punctuation for char in stripped
    ):
        return False
    alpha_count = sum(
        1 for char in stripped if char.isalnum() or ("\uac00" <= char <= "\ud7a3")
    )
    return alpha_count >= 2


def _looks_like_script_body(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if any(char.isalnum() or ("\uac00" <= char <= "\ud7a3") for char in stripped):
        return True
    return all(char in ".!?…" for char in stripped.replace(" ", ""))


def _is_ascii_printable_byte(value: int) -> bool:
    return 0x20 <= value <= 0x7E


def _ascii_runs(prefix_bytes: bytes) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(prefix_bytes):
        if _is_ascii_printable_byte(value):
            if start is None:
                start = index
            continue
        if start is not None and index - start >= 4:
            runs.append((start, index))
        start = None
    if start is not None and len(prefix_bytes) - start >= 4:
        runs.append((start, len(prefix_bytes)))
    return runs


def _sanitize_script_prefix(prefix_bytes: bytes) -> bytes:
    if not prefix_bytes:
        return prefix_bytes

    best_prefix = b""
    best_score = float("-inf")
    candidate_roots = {prefix_bytes}
    for run_start, run_end in _ascii_runs(prefix_bytes):
        candidate_roots.add(prefix_bytes[:run_start] + prefix_bytes[run_end:])

    for root in candidate_roots:
        for start in range(0, len(root) + 1):
            candidate = root[start:]
            if not candidate:
                score = 0.25
            else:
                parsed = parse_script_prefix(candidate)
                score = 0.0
                known_command_count = 0
                high_ascii_command_count = 0
                for command in parsed.commands:
                    if command.mnemonic in {"set-left-portrait", "set-right-portrait", "set-expression"}:
                        score += 5.0
                        known_command_count += 1
                    elif command.opcode <= 0x1F:
                        score += 2.0
                    elif command.opcode <= 0x43:
                        score += 1.0
                    else:
                        score -= 0.75

                    if command.args:
                        if all(arg <= 0x40 for arg in command.args):
                            score += 0.5
                        if all(_is_ascii_printable_byte(arg) for arg in command.args):
                            score -= 0.75
                            if command.opcode >= 0x20:
                                high_ascii_command_count += 1

                printable_ratio = sum(1 for byte in candidate if _is_ascii_printable_byte(byte)) / len(candidate)
                if printable_ratio >= 0.7:
                    score -= printable_ratio * 3.5
                if known_command_count == 0 and high_ascii_command_count >= max(2, len(parsed.commands) // 2):
                    score -= 6.0
                if parsed.trailing_hex:
                    score -= len(parsed.trailing_hex) / 2
                score -= start * 0.02
                score -= max(len(prefix_bytes) - len(root), 0) * 0.03

            if score > best_score:
                best_score = score
                best_prefix = candidate

    return best_prefix


def _parse_script_events_with_encoding(data: bytes, encoding: str) -> list[ScriptEvent]:
    events: list[ScriptEvent] = []
    offset = 0

    while offset < len(data):
        if data[offset] == 0xFF and offset + 3 <= len(data):
            text_len = struct.unpack("<H", data[offset + 1 : offset + 3])[0]
            text_end = offset + 3 + text_len
            if 1 <= text_len <= 800 and text_end <= len(data):
                text = _decode_script_text(data[offset + 3 : text_end], encoding)
                if text is not None and _looks_like_script_body(text):
                    event_end = text_end
                    while event_end < len(data) and data[event_end] == 0:
                        event_end += 1
                    events.append(
                        ScriptEvent(
                            offset=offset,
                            kind="caption",
                            prefix_hex="ff",
                            speaker=None,
                            speaker_tag=None,
                            text=text,
                            byte_length=event_end - offset,
                        )
                    )
                    offset = event_end
                    continue

        matched_event: ScriptEvent | None = None
        matched_end = offset + 1
        for gap in range(0, 16):
            payload_offset = offset + gap
            if payload_offset + 2 > len(data):
                break

            speaker_len = struct.unpack("<H", data[payload_offset : payload_offset + 2])[0]
            if not 2 <= speaker_len <= 16:
                continue

            speaker_start = payload_offset + 2
            speaker_end = speaker_start + speaker_len
            if speaker_end + 3 > len(data):
                continue

            speaker = _decode_script_text(data[speaker_start:speaker_end], encoding)
            if speaker is None or not _looks_like_script_speaker(speaker):
                continue

            speaker_tag = data[speaker_end]
            text_len = struct.unpack("<H", data[speaker_end + 1 : speaker_end + 3])[0]
            if not 1 <= text_len <= 800:
                continue

            text_start = speaker_end + 3
            text_end = text_start + text_len
            if text_end > len(data):
                continue

            text = _decode_script_text(data[text_start:text_end], encoding)
            if text is None or not _looks_like_script_body(text):
                continue

            matched_event = ScriptEvent(
                offset=offset,
                kind="speech",
                prefix_hex=_sanitize_script_prefix(data[offset:payload_offset]).hex(),
                speaker=speaker,
                speaker_tag=speaker_tag,
                text=text,
                byte_length=text_end - offset,
            )
            matched_end = text_end
            break

        if matched_event is not None:
            events.append(matched_event)
            offset = matched_end
            continue

        offset += 1

    return events


def extract_script_events(
    data: bytes,
    preferred_encoding: str | None = None,
) -> tuple[str | None, tuple[ScriptEvent, ...]]:
    encodings: list[str] = []
    if preferred_encoding is not None:
        encodings.append(preferred_encoding)
    for fallback in ("utf-8", "cp949"):
        if fallback not in encodings:
            encodings.append(fallback)

    best_encoding: str | None = None
    best_events: list[ScriptEvent] = []
    best_score = -1

    for encoding in encodings:
        events = _parse_script_events_with_encoding(data, encoding)
        if not events:
            continue
        score = len(events) * 100 + sum(len(event.text) for event in events)
        if score > best_score:
            best_score = score
            best_encoding = encoding
            best_events = events

    return (best_encoding, tuple(best_events))
