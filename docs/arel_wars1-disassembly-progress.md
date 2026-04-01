# Arel Wars 1 Disassembly Progress

이 파일은 `disassemble` 브랜치의 중간 진행 보고용 메모다. 세부 근거와 함수 단위 reverse 결과는 [arel_wars1-disassembly.md](/C:/vs/other/arelwars/docs/arel_wars1-disassembly.md)에 누적하고, 여기에는 이번 세션의 checkpoint만 적는다.

## 2026-04-01 Session

### Confirmed

- `CGxPZAParser::DecodeHeader`
  - `3-byte` 헤더
  - `header[1..2] = animation count`
- `CGxPZAParser::Open`
  - `count * 4` index table 준비
  - `SeekIndexTable(index)`를 통해 `u32 offset` 기반 animation blob seek
- `CGxPZAParser::DecodeAnimationData`
  - clip blob 형식은 `frameCount:u8 + frameCount * 8-byte frame`
  - frame = `frameIndex:u16`, `delay:u8`, `x:s16`, `y:s16`, `control:u8`
- `CGxPZxAni`
  - 런타임 frame record는 `12-byte`
  - `delay/x/y/frame pointer`만 저장
  - `frameIndex`는 별도 `u16[]`로 분리
- `CGxPZAMgr::LoadAni*`
  - 분리된 `frameIndex[]`를 사용해 `CGxPZFMgr::LoadFrameEx` 호출
  - 결과 frame pointer를 `CGxPZxAni` frame record에 주입
- `CGxPZF19CreateSubFrameIndex` / `CGxPZFMgr::LoadFrameEx`
  - `PZF`도 같은 방식으로 `u16 subFrameIndex[]` 캐시를 가짐
  - `LoadFrameEx`는 그 배열을 따라 `CGxPZDPackage` loader를 돌고, 결과 pointer를 `CGxPZxFrame` 내부 array에 저장
  - 즉 네이티브 계층이 `PZA -> PZF -> PZD`로 이어진다는 점이 더 강해졌다.
- `CGxPZxParserBase::CheckPZxType`
  - 루트 `PZX\x01` 헤더를 special-case 한다.
  - 파일 시작 16바이트의 `field4/field8/field12`를 typed subresource offset table로 취급한다.
  - 타입 코드는 `PZD=0`, `PZF=1`, `PZA=2`로 고정된다.
- `CGxPZxMgr::SetSource`
  - `CGxPZxResource` 하나를 만든 뒤 `PZFMgr`와 `PZAMgr`에 공유한다.
  - 따라서 `PZF/PZA`는 별도 파일이 아니라 같은 `.pzx` 내부 typed subresource다.
- `CGxPZxFrameBB::GetTotalBoundingBoxCount / GetBoundingBoxCount / GetBoundingBox`
  - bbox count byte는 frame `+0x20/+0x21`
  - bbox format variant는 frame `+0x22`
  - bbox record array는 frame `+0x1c`
  - variant `1/3` bbox record는 `x, y, w, h` 4-word shape로 소비된다.

### Asset-side Validation

- `tools/arel_wars1/inspect_binary_assets.py`에 animation clip stream 파서를 추가했다.
- exact-fit 조건으로 다시 스캔했을 때:
  - `144` stems에서 animation clip stream 검출
  - 검출된 stream index는 모두 `2`
  - 즉 다수 `.pzx`에서 세 번째 zlib stream이 `PZA` animation blob으로 보인다.
- 현재 관찰 범위:
  - `frameIndex = 0..85`
  - `delay = 0..32`
  - `x = 0`
  - `y = -80..10`
  - `control = 0`
- raw `PZA` subresource까지 직접 파싱하면:
  - `159` stems에서 `PZA` index table + payload가 clip 구조로 정확히 읽힌다.
  - `145` stems는 raw `PZA` payload가 zlib stream index `2`와 byte-identical 하다.
  - `PZF` raw header의 `frameCount`는 `PZA frameIndex`가 가리키는 실제 frame pool 크기다.
  - 집계상 `143` stems는 `max(frameIndex)+1 == PZF frameCount`, 나머지 `16` stems도 in-range sparse reference다.
- raw `PZF` head가 샘플마다 달라 보이는 이유도 방향이 잡혔다.
  - `BeginDecodeFrame`가 먼저 bounding-box count byte를 읽고
  - count가 nonzero인 프레임은 `DecodeBoundingBoxFromBAR/FILE`가 먼저 stream을 소비한 뒤
  - `EndDecodeFrameFromBAR/FILE`가 subframe list를 읽는 구조로 보인다.
  - 그래서 `010`처럼 count가 0인 샘플은 record head가 바로 보이지만, `082` 같은 샘플은 payload head만 보고는 subframe index가 안 보일 수 있다.
- raw `PZF` frame parser도 자산측에 내렸다.
  - `253/253` stems에서 raw embedded `PZF`가 frame 단위로 exact-fit 된다.
  - `216` stems는 raw `PZF` payload가 zlib stream index `1`과 byte-identical 하다.
  - `51` stems는 old frame-record parser의 `recordOffsetsPreview`가 raw `PZF` frame offset table prefix와 정확히 맞는다.
  - 즉 stream `1`과 frame-record heuristic은 native `PZF`의 partial/misaligned read로 보는 쪽이 맞다.
- `PZF` subframe record의 현재 working shape:
  - `subFrameIndex:u16`, `x:s16`, `y:s16`, `extraFlag:u8`, `extraPayload`
  - `extraPayload`는 자산 exact-fit 기준으로 `extraFlag` 또는 `extraFlag + 4` 바이트로 닫힌다.
  - marker형 payload는 `66 xx 00 00 00` / `67 xx 00 00 00`가 우세하다.
  - 이 hybrid rule은 asset 쪽 exact-fit은 주지만, 아직 `EndDecodeFrame*` 디스어셈블만으로는 설명이 완전히 닫히지 않았다.

### Resolved

- 이전 negative result였던 "`frameIndex max < visible frame-record count` 불성립"은 이제 설명된다.
- 원인은 visible frame-record stream을 실제 `PZF` frame pool로 착각한 데 있었다.
- 예: `082.pzx`
  - raw `PZF frameCount = 86`
  - raw `PZA frameIndex range = 0..85`
  - 즉 native `frameIndex`는 frame-record stream 길이가 아니라 raw `PZF` subresource count를 가리킨다.

### Next Focus

1. `CGxPZDPackage / CGxPZDMgr::LoadImage*`를 따라 `subFrameIndex[] -> PZD image -> first-stream chunk` 연결을 확정한다.
2. `CGxPZxFrame::Draw`와 `CGxPZxFrameBB::*` consumer를 더 따라가서 `extraPayload(66/67...)`와 bbox group 의미를 런타임 동작에 붙인다.
3. `082/083/084`와 `198/208/240`을 기준 샘플로, old frame-record/tail heuristic이 native `PZF`의 어느 subset을 잘못 읽은 것인지 정리한다.

## 2026-04-02 Session

### Confirmed

- `CGxPZFParser::EndDecodeFrameFromBAR/FILE`
  - asset-side exact-fit parser가 맞았다.
  - native도 실제로 per-subframe에 `u16 subFrameIndex`, `x:s16`, `y:s16`, `extraLen:u8`, `extraPtr`를 읽어 넣는다.
  - `subFrameIndex`는 caller가 준 별도 `u16[]`로 빠지고, `CGxPZxFrame` 내부 subframe record는 `stride = 0x10`이다.
- `GsPZxSubFrame` / `CGxPZxFrame::Draw`
  - plain draw path는 `bitmap pointer + x/y`만 소비한다.
  - `extraPtr/extraLen`은 normal render path에서 직접 쓰이지 않는다.
- `CGxEffectPZDMgr::FindEffectedImage` / `CGxEffectExPZDMgr::FindEffectedImage`
  - `extraPayload`는 effect cache key다.
  - 비교 시 모든 바이트를 쓰지 않고, `<= 4`인 값만 opcode sequence로 추출해서 비교한다.
  - corrected parse 기준 filtered cache-key histogram은 `0:13746, 1:4, 2:24, 3:2278, 4:68`이다.
- `CGxEffectPZDMgr::LoadImage*` -> `CGxEffectPZD::GetBitmap` -> `ApplyEffect`
  - cache miss 시 `subframe + 0x08`이 그대로 `tagEffect*`로 넘어간다.
  - 즉 raw subframe `extraPtr + extraLen` 구조가 runtime effect bytecode input과 직접 대응된다.
- `CGxEffectPZDMgr::LoadImage*`
  - `extraLen == 1`이고 그 1-byte 값이 `0x65..0x74`이면 effected-bitmap 경로 대신 normal image load로 빠진다.
  - longer payload는 `FindEffectedImage -> AddNewEFFECTED_BITMAP` 경로로 들어가고, 그 과정에서 subframe의 `extraPayload`가 그대로 복제된다.
- `HasFlipEffect`
  - same payload에서 `3/4`만 flip-class opcode로 취급한다.
  - return은 `0 = no flip`, `1 = pure flip`, `2 = flip + other executable opcode`로 읽힌다.
- `CGxEffectPZD::ApplyEffect`
  - 실제 실행 opcode 범위는 `1..100`이다.
  - `0`과 `>= 101`은 실행되지 않는다.
  - `CGxEffectPZDC1/C2` constructor의 handler slot 배치를 따라가면 exact mapping은 `1 = ROTATE_CW90`, `2 = ROTATE_CCW90`, `3 = FLIP_LR`, `4 = FLIP_UD`, `5..100 = ChangePalette(effectType - 5)`다.
- `PZD`
  - `field4`가 native `PZD` subresource라는 점을 자산측 parser로 완전히 닫았다.
  - `type 8` (`header[0] = 0x08`)은 `205/205` stems에서 `PZD` 구간 내부 zlib stream이 정확히 하나만 나오고, 그 decoded payload는 `first-stream`이며 chunk count가 `contentCount`와 항상 같다.
  - `type 7` (`header[0] = 0x07`)은 `48/48` stems에서 `PZD` 구간 내부 zlib stream이 정확히 `contentCount`개 나오고, 각 decoded payload는 standalone `row-stream`이다.
  - 즉 runtime-equivalent 기준으로 `subFrameIndex -> PZD image` 연결은 정리됐다.
    - `type 8`: `subFrameIndex == first-stream chunk index`
    - `type 7`: `subFrameIndex == file-order row-stream index`
  - raw byte layout도 정리됐다.
    - `type 7 flags=0`: `field4 + 4`에서 시작하는 direct `u32 imageOffset[contentCount]` table이 있고, 각 entry는 `.pzx` file-local absolute offset으로 per-image block 시작을 가리킨다.
      - block = `localPaletteCount:u8`, `localPalette16[count]:u16`, `16-byte descriptor`, `zlib rowstream`
    - `type 7 flags=1`: root header 뒤 `globalPaletteCount:u8 + globalPalette16[count]:u16`가 먼저 오고, 그 다음 `u32 imageOffset[contentCount]` table이 온다.
      - 각 entry는 `.pzx` file-local absolute offset이고, 바로 `16-byte descriptor + zlib rowstream`을 가리킨다.
    - `type 8`: root header 뒤 optional global palette, `unpackedSize:u32`, `packedSize:u32`, zlib blob이 붙는다.
      - inflate된 memory stream 안에는 decoded-relative `u32 imageOffset[contentCount]` table이 있고, 각 entry는 `16-byte chunk header + rowstream body`를 가리킨다.
      - 이 chunk header의 raw byte `+5`는 보통 `0xCD`지만, `CGxZeroPZDParser::DecodeImageData`는 `1`이 아닌 값을 모두 `0`으로 정규화한다.
- `PZxFrameBB`
  - `GetAttCount = token >> 4`, `GetDamCount = token & 0x0f`로 확인됐다.
  - bbox mode는 `PZF formatVariant`와 대응한다.
    - `0`: packed attack/damage counts + compact 4-byte box
    - `1`: explicit generic count + compact 4-byte box
    - `2`: reference point list
    - `3`: explicit attack/token0 + damage/token1 + full 8-byte box
  - API type selector도 의미가 닫혔다.
    - `type 0 = attack boxes`
    - `type 1 = damage boxes`
    - other type = union bounding box
  - collision filter/return code도 정리됐다.
    - rect collision low byte: `0x01 attack`, `0x02 damage`, `0x03 both`
    - frame-vs-frame collision: self low nibble `0x01/0x02/0x03`, other high nibble `0x10/0x20/0x30`
    - `filter & 0xFF00 == 0xFF00`이면 generic hit `1`
    - otherwise return `2/3` (rect attack/damage) 또는 `4/5/6/7` (atk-vs-dam / dam-vs-atk / atk-vs-atk / dam-vs-dam)
  - 현재 parsed set 기준 mode 분포는 `explicit-att-dam = 251`, `compact-box-list = 2`, `reference-point-list = 0`이다.
  - 집계 총량은 attack `1468`, damage `1260`, generic `11`, reference `0`이다.
- `CGxPZxAni` playback state
  - clip state `4-byte`는 `currentFrame`, `delayPos`, `flags`, `signed globalDelayBias`다.
  - `Play(loop)`는 `bit1=playing`을 세우고, loop 요청이면 `bit4`도 세운다.
  - `Pause`는 `bit3`, `Stop`은 `bit0`을 토글한다.
  - `DoPlay`는 frame-local `delay + globalDelayBias`를 effective delay로 쓰고, `delayPos = (delayPos + 1) % effectiveDelay`가 `0`일 때만 frame advance한다.
  - wrap 시 `bit2`를 세우고, loop가 아니면 current frame을 마지막 frame에 고정한 뒤 `Stop(false)`로 멈춘다.
  - `GetCurrentDelayFrameCount`는 current frame 이전 누적 delay + 현재 `delayPos`, `GetTotalDelayFrameCount`는 `delay==0` frame만 `1` tick으로 보정한 총합을 돌려준다.
  - whole-binary scan 기준 `clipState + 3`에 대한 external writer는 찾지 못했다.
  - 즉 current build에서 `globalDelayBias`는 init 시 `0`으로 놓이고 runtime helper가 읽기만 하는 dormant signed bias field로 보는 쪽이 맞다.
- `PZF`
  - `PZD image count`를 raw `PZF` parser의 `max_subframe_index` bound로 다시 넣으면 outlier가 사라진다.
  - 현재 집계는 `exact-max-plus-one = 244`, `in-range = 7`, `empty = 2`, `out-of-range = 0`이다.
- `EffectEx / ZeroEffectEx`
  - standalone `GsLoadPzf` / `GsLoadPzfPart`가 실제로 `CGxZeroEffectExPZDMgr`와 `CGxZeroEffectExPZFMgr`를 직접 생성한다.
  - `CGxEffectExPZFParser::EndDecodeFrameFromBAR/FILE`는 `stride = 0x18` subframe record를 만들고, raw `extraLen + extraPtr` 외에 마지막 `0x65..0x74` 또는 `0x7f`를 `selector byte(+0x10)`로 저장하며, 그 selector를 볼 때마다 trailing `u32 parameter(+0x14)`를 읽는다.
  - `CGxPZxEffectExFrame::__Draw`는 plain draw path에서 바로 이 `selector + parameter`를 소비한다.
  - 따라서 `66/67/70/71/7f`는 `EffectEx` family에서는 executable opcode가 아니라 draw/module selector다.
  - 현재 APK asset table에는 standalone `.pzf/.pzd` 샘플이 없고, embedded `.pzx` set은 전부 base `PZF` layout으로 exact-fit 된다.

### Asset-side Validation

- full parsed `PZF` set 기준으로 effect-relevant extra 통계가 닫혔다.
  - filtered cache-key histogram (`<= 4`만 집계): `0:13746, 1:4, 2:24, 3:2278, 4:68`
  - runtime opcode histogram (`1..100`만 실행): `1:4, 2:24, 3:2278, 4:68, 5:261, 6:11, 7:280, 8:68, 9:4, 10:93, 11:14, 12:43, 13:7, 14:16, 15:9, 20:4, 24:1, 28:1, 30:6, 40:8, 44:7, 50:14, 57:1, 60:4, 70:20, 72:4, 80:31, 86:1, 89:7, 99:15, 100:89`
  - corrected parse 기준 single-byte `0x65..0x74` family는 `{}`로 비었다.
  - 대신 longer extra 안의 selector-byte heuristic 분포는 `67:3197, 66:930, 71:171, 69:67, 70:57, 7f:36, 72:32, 6a:25`이고, last-selector 기준 분포는 `67:3197, 66:930, 71:171, 69:67, 70:49, 7f:36, 72:32, 6a:25`다.
  - payload length 분포는 여전히 `5-byte`가 우세하고, marker family도 `67+u32 / 66+u32`가 우세하다.
  - runtime sequence `(3)`은 raw payload `19`종 (`03`, `0367ff000000`, `6603000000`, `67ff00000003`, ...)에서 나오고, `(4,3)`도 `8`종 payload에서 나온다.
  - 반면 `(7) -> 6607000000`, `(10) -> 660a000000`, `(100) -> 6764000000`, `(44,99) -> 702c630000`처럼 특정 envelope family에 고정된 sequence도 있다.
- 즉 현재 `PZF extraPayload`는 두 층으로 읽는 게 맞다.
  - outer envelope / selector bytes (`66/67/70...`, non-executed)
  - inner executable effect opcode sequence (`1..100`)
- report 쪽에도 `embeddedPzd*` summary를 추가했다.
  - `embeddedPzdTypeCounts = {7: 48, 8: 205}`
  - `embeddedPzdLayoutCounts = {row-stream-list: 48, first-stream-sheet: 205}`
  - `embeddedPzdPzfRelationCounts = {exact-max-plus-one: 244, in-range: 7, empty: 2}`

### Open

- current APK decode 관점에서 남은 핵심은 reference-point mode(`bbox variant 2`) 샘플 부재뿐이다.
  - code path는 보이지만 실제 자산이 없어 asset-side exact-fit 검증까지는 못 했다.
- `EffectEx / ZeroEffectEx` raw parser는 native semantics가 닫혔지만, 현재 APK에는 standalone `.pzf/.pzd` 샘플이 없어서 tool-side parser 구현까지는 아직 안 했다.

### Next Focus

1. reference-point mode(`bbox variant 2`)가 실제 게임 데이터에서 쓰이는지, 아니면 dormant path인지 자산/consumer 기준으로 정리한다.
2. standalone `EffectEx / ZeroEffectEx` sample을 확보할 수 있으면 `selector + trailing u32` layout까지 tool-side exact parser로 내린다.

### Refresh Commands

```powershell
python tools/arel_wars1/disassemble_libgameDSO.py --defaults
python tools/arel_wars1/extract_assets.py --apk arel_wars1/arel_wars_1.apk --output recovery/arel_wars1/native_tmp/extract
python tools/arel_wars1/inspect_binary_assets.py --assets-root recovery/arel_wars1/native_tmp/extract/apk_unzip/assets --output recovery/arel_wars1/native_tmp/binary_asset_report-session.json
```
