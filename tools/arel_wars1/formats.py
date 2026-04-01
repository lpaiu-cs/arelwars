from __future__ import annotations

from dataclasses import dataclass
import struct
import zlib


ZLIB_HEADERS = {0x01, 0x5E, 0x9C, 0xDA}
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
    timing_ms: int | None
    extended_layout: str | None
    extended_prefix_hex: str | None
    extended_suffix_hex: str | None
    extended_tuple_stride: int | None
    extended_tuple_count: int
    extended_valid_tuple_count: int
    extended_tuples: tuple[PzxMetaTuple, ...]


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
        for prefix_len in range(0, 8):
            for suffix_len in range(0, 12):
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
                if tuple_count == 0:
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

    valid_count, tuple_count, _, _, _, layout, prefix_hex, suffix_hex, tuples = max(candidates)
    if valid_count != tuple_count:
        return None
    stride = 7 if "flagged" in layout else 6
    return (layout, prefix_hex, suffix_hex, stride, valid_count, tuples)


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
