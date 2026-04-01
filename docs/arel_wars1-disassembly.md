# Arel Wars 1 Native Disassembly

이 브랜치는 `.pzx`의 후반 메타데이터를 데이터 패턴만으로 추론하는 대신, `arel_wars1/arel_wars_1.apk` 안의 `lib/armeabi/libgameDSO.so`를 직접 추적해서 원본 디코더 경로를 찾는 데 집중한다.

## Entry Point

`libgameDSO.so`는 APK 안에 그대로 들어 있다.

```powershell
powershell -ExecutionPolicy Bypass -File tools/arel_wars1/inspect_libgameDSO.ps1
```

위 스크립트는 다음을 자동으로 수행한다.

- APK에서 `lib/armeabi/libgameDSO.so` 추출
- ELF32 section / symbol table 파싱
- `PZX`, `PZA`, `PZF`, `MPL`, `Animation`, `inflate`, `ZT1` 관련 함수 추출
- Thumb `BL` immediate call-site를 스캔해서 함수 간 call edge 구성
- 결과를 `recovery/arel_wars1/disassembly/` 아래 JSON/TSV로 저장

생성 산출물은 `.gitignore`에 추가되어 있으므로 브랜치를 오염시키지 않는다.
전체 call-edge 스캔까지 포함하면 실행 시간은 환경에 따라 수 분 걸릴 수 있다.

함수 바디를 직접 볼 때는 아래 파이썬 디스어셈블러를 사용한다.

```powershell
python tools/arel_wars1/disassemble_libgameDSO.py --defaults
python tools/arel_wars1/disassemble_libgameDSO.py --find DecodeAnimation
python tools/arel_wars1/disassemble_libgameDSO.py --function _ZN12CGxPZAParser19DecodeAnimationDataEti
```

이 스크립트는 `capstone`과 `pyelftools`를 사용해 Thumb 코드를 디스어셈블하고, branch target을 심볼명으로 주석 처리한다.

## Current Native Findings

- `libgameDSO.so`는 `ELF32 little-endian / EM_ARM (0x0028)`이다.
- 심볼이 충분히 남아 있어서, 함수명만으로도 네이티브 로더 계층을 추적할 수 있다.
- APK asset table에는 `.pza` / `.pzf` 파일이 따로 없고, 실제 이미지 자산은 `.pzx`, `.mpl`, `.ptc`, `.zt1`만 존재한다.
- 그런데 네이티브 호출축은 `PZX` 매니저가 내부적으로 `PZA` / `PZF` 서브매니저를 여는 구조를 보인다.
  - `CGxPZxMgr::Open -> CGxPZAMgr::Open + CGxPZFMgr::Open`
  - `CGxPZxMgr::LoadAni -> CGxPZAMgr::LoadAni / LoadAniEx`
  - `CGxPZxMgr::LoadFrame -> CGxPZFMgr::LoadFrameEx`
- 즉 `.pzx` 후반 stream은 "정체불명의 tail"이라기보다, 네이티브 런타임에서 `PZA`(animation) / `PZF`(frame) parser가 소비하는 서브영역일 가능성이 크다.
- `CGxPZxParserBase::CheckPZxType`는 이 구조를 직접 드러낸다.
  - 현재 스트림 머리가 원하는 타입이 아니고 루트 `PZX\x01` 헤더라면
  - 파일 시작 16바이트의 `field4/field8/field12`를 `type * 4` offset table로 보고
  - 원하는 typed subresource 위치로 다시 seek 한다.
- tiny getter 기준 타입 코드는 고정된다.
  - `CGxPZD::GetContentsType = 0`
  - `CGxPZF::GetContentsType = 1`
  - `CGxPZA::GetContentsType = 2`
  - `CGxMPL::GetContentsType = 4`
- `PZX` 쪽 로더/렌더러 축은 다음 이름들로 드러난다.
  - `CGsPzxResourceMgr::Load`
  - `CGsPzxResource::Load`
  - `CGxPZxMgr::Open`
  - `CGxPZxMgr::LoadFrame`
  - `CGxPZxMgr::LoadAni`
  - `CGxPZxAni::Play`
  - `CGxPZxAni::DoPlay`
  - `CGxPZxAni::GetCurrentDelayFrameCount`
- 시간축 애니메이션 메타데이터 쪽의 핵심 후보는 `PZX` 전용 함수보다 오히려 다음 축이다.
  - `CGxPZAMgr::LoadAni`
  - `CGxPZAMgr::LoadAniAll`
  - `CGxPZA::GetAnimation`
  - `CGxPZAParser::Open`
  - `CGxPZAParser::DecodeHeader`
  - `CGxPZAParser::DecodeAnimationData`
- call xref 기준으로 `CGxPZA::GetAnimation -> CGxPZAParser::DecodeAnimationData`가 직접 연결된다.
- 재생 루프 쪽은 `CSpriteIns::DoAnimate -> CGxPZxAni::DoPlay`, `CSpriteIns::GetAniProcessCount -> CGxPZxAni::GetCurrentDelayFrameCount`로 이어진다.
- 즉 현재까지의 네이티브 구조상, "조각 배치"와 "시간축 재생"은 같은 계층이 아닐 가능성이 높다.
  - `PZX` 계층은 프레임/이미지 조각 로딩
  - `PZA` 계층은 애니메이션 인덱스/프레임 진행 메타데이터
- `inflate*` 심볼이 외부 import가 아니라 라이브러리 내부에 정적으로 들어 있으므로, zlib 호출자를 직접 따라가면 실제 디코더 함수를 좁힐 수 있다.
- 실제로 `inflateInit / inflate / inflateEnd`는 모두 `uncompress` 내부에서만 보이고, parser 계층은 `GxUncompress`를 통해 zlib를 우회 호출한다.
  - `GxUncompress` caller: `CGxPZFParser::UncompressAllDataFromBAR`, `CGxPZFParser::UncompressAllDataFromFILE`, `CGxPZDParser::DecodeImageData`
  - `GxUncompressZT1` caller: `LoadResource`, `LoadFile`
- 따라서 `.zt1` 복호 경로와 `.pzx`/`.pza`/`.pzf` 복호 경로는 네이티브에서도 이미 분리되어 있다.
- `CGxPZxResource::AttachResource`는 parser에 APK 전체 파일 handle을 넘기는 게 아니라, 메모리로 적재한 `.pzx` blob을 `CGxStream` memory stream으로 감싼다.
  - `CGxStream::Attach` / `SeekMem` 기준으로 parser seek는 이 memory blob 안의 relative offset이다.
  - 따라서 root `field4/field8/field12`와 `PZA/PZF` index table entry는 `.pzx` file-local offset으로 읽는 쪽이 맞다.

## Current Structure

- `CGxPZAParser::DecodeHeader`는 사실상 `3-byte` PZA 헤더를 읽는다.
  - `header[0]`: storage / parser mode flag
  - `header[1..2]`: animation count (`u16`)
- `CGxPZAParser::Open`는 이 animation count를 바탕으로 `count * 4` 바이트짜리 index table을 준비한다.
  - storage flag에 따라 raw seek path와 `UncompressAllDataFromBAR/FILE` path로 갈린다.
  - 즉 `PZA`의 index table entry는 `4-byte offset`이다.
- `CGxPZxParserBase::SeekIndexTable(index)`는:
  - index table 시작점으로 이동
  - `index * 4` 위치의 `u32 offset`를 읽고
  - 그 offset으로 다시 seek 한다.
- 따라서 `DecodeAnimationData(index, ...)`는 "animation index -> offset table -> animation blob" 흐름으로 동작한다.

## Animation Layout

- `CGxPZA::GetAnimation(index)`는 `CGxPZAParser::DecodeAnimationData`를 호출해 `CGxPZxAni*`를 만든다.
- 동시에 `frameIndex` 목록은 `CGxPZxAni` 안에 넣지 않고, 별도 `u16` 배열로 받아서 `CGxPZA::CreateAniFrameIndex`가 animation index별 캐시로 복제한다.
- `CGxPZAMgr::LoadAni*`는 그 별도 `frameIndex` 배열을 이용해 `CGxPZFMgr::LoadFrameEx`를 호출하고, 결과 frame pointer를 `CGxPZxAni` 내부 frame record에 꽂는다.
- 즉 현재 구조는 명확히 분리된다.
  - `PZA`: timeline / frame index / per-frame offset-delay 메타데이터
  - `PZF`: 실제 frame payload
- `CreateAniFrameIndex`는 실제로 `frameCount * 2` 바이트를 할당해서 `u16[]`를 복사한다.
- `LoadAni`는 animation object의 `frameCount`만큼 순회하면서:
  - manager 쪽 `u16 frameIndex[]`를 읽고
  - `CGxPZFMgr` virtual call을 통해 frame pointer를 로드하고
  - `CGxPZxAni` frame record array(`stride = 0x0C`)의 첫 필드에 저장한다.
- `PZF`도 동일한 구조를 반복한다.
  - `CGxPZF::CreateSubFrameIndex`는 `subFrameCount * 2` 바이트 `u16[]`를 캐시한다.
  - `CGxPZFMgr::LoadFrameEx`는 그 `subFrameIndex[]`를 따라가며 `CGxPZDPackage` loader를 호출하고, 결과 subframe/resource pointer를 `CGxPZxFrame` 내부 array(`stride = 0x10`)에 저장한다.
- 따라서 현재 네이티브 계층은 다음처럼 읽히는 편이 가장 자연스럽다.
  - `PZA clip -> PZF frame index -> PZD subframe index -> 실제 리소스 pointer`
- `CGxPZxMgr::SetSource`도 같은 결론을 준다.
  - 표준 `.pzx` 경로에서는 `CGxPZxResource` 하나를 먼저 만들고
  - 그 resource를 `PZFMgr`와 `PZAMgr`에 각각 `SetResource`한다.
  - 즉 `PZF`와 `PZA`는 서로 다른 파일이 아니라, 같은 `.pzx` 안의 typed subresource다.

`CGxPZxAni` 객체 레이아웃은 현재까지 다음처럼 보인다.

```text
CGxPZxAni (size 0x18)
  +0x08  clip state pointer
  +0x0C  owns clip state flag
  +0x10  frame record array pointer
  +0x14  frame count
```

`CreateAniClip`이 만드는 clip state는 `4-byte` 구조다.

```text
clip state (size 4)
  +0  current frame index
  +1  current delay position
  +2  playback flags
  +3  signed global delay bias
```

- `CreateAniClip`는 이 4-byte state를 `00 00 01 00`으로 초기화한다.
  - `flags bit0 = stopped`
  - `flags bit1 = playing`
  - `flags bit2 = wrapped/end-reached`
  - `flags bit3 = paused`
  - `flags bit4 = loop-on-wrap`
- `Play(loop)`는 `bit0/bit4`를 정리하고 `bit1`을 세운다.
  - `Play(false)`는 non-loop play
  - `Play(true)`는 `bit4`까지 세워 wrap 시 0번 frame으로 계속 돈다.
- `Pause(true/false)`는 `bit3`만 토글한다.
- `Stop(reset)`는 `bit1/bit3`를 내리고 `bit0`을 세운다.
  - `Stop(true)`는 current frame index도 `0`으로 돌린다.
  - `Stop(false)`는 current frame을 유지한 채 멈춘다.

`DecodeAnimationData`가 채우는 per-frame record는 `12-byte` 구조다.

```text
frame record (size 0x0C)
  +0x00  frame pointer (later filled by PZF manager)
  +0x04  x offset (s16)
  +0x06  y offset (s16)
  +0x08  local delay (u8)
  +0x09..0x0B  padding / unused in current reading
```

애니메이션 blob의 현재 working decode는 다음과 같다.

```text
animation:
  frameCount:u8
  repeat frameCount times:
    frameIndex:u16
    delay:u8
    x:s16
    y:s16
    control:u8
```

- `frameIndex`는 `CGxPZxAni` frame record에 저장되지 않는다.
- 대신 별도 `u16[]`로 빠져서 `CGxPZAMgr::LoadAni*`가 `PZF` frame 로딩에 사용한다.
- `control:u8`는 `CGxPZxAni`에 저장되지 않는다.
- 대신 0이 아닐 때 stream callback을 한 번 더 치는 구조라서, runtime 재생 플래그보다는 container / separator 계층일 가능성이 높다.
- `DoPlay`가 실제로 소비하는 시간축은 간단하다.
  - effective per-frame delay = `frame.localDelay + clipState.globalDelayBias`
  - effective delay가 `0`이면 그 tick에서 바로 다음 frame으로 넘어간다.
  - effective delay가 양수면 `delayPos = (delayPos + 1) % effectiveDelay`를 수행하고, remainder가 `0`일 때만 다음 frame으로 진행한다.
  - frame advance 자체는 `currentFrame = (currentFrame + 1) % frameCount`다.
  - wrap가 발생하면 `bit2`를 세우고, `bit4(loop)`가 꺼져 있으면 current frame을 `frameCount - 1`로 되돌린 뒤 `Stop(false)`로 멈춘다.
- helper도 이 state machine과 맞물린다.
  - `GetCurrentDelayFrameCount`는 current frame 직전까지의 누적 delay + 현재 `delayPos`를 돌려준다.
  - `GetTotalDelayFrameCount`는 전체 frame을 순회하면서 `delay == 0`인 frame만 `1` tick으로 보정한 합을 돌려준다.
  - 즉 runtime advance는 zero-delay frame을 즉시 소모하지만, total-count helper는 zero-delay frame을 최소 `1` tick으로 세는 비대칭이 있다.
- clip state `+3`의 `globalDelayBias`는 현재 build 기준 dormant field로 보는 쪽이 맞다.
  - `CreateAniClip`만 이 바이트를 `0`으로 초기화한다.
  - whole-binary scan 기준 `CGxPZxAni + 0x08` clip-state 포인터를 따라 `+3`에 store 하는 경로를 찾지 못했다.
  - symbolized consumer는 `DoPlay`와 delay helper뿐이므로, 현재 APK의 embedded `PZA` timeline에는 외부 signed-bias writer가 없다고 보는 편이 자연스럽다.
- `DecodeAnimationData` 내부의 두 갈래는 서로 다른 animation 포맷이 아니라 `CGxStream` backend 차이로 보인다.
  - direct memory buffer path
  - callback-based stream path
- 같은 방식으로 `PZF` frame decode도 두 단계로 보인다.
  - `BeginDecodeFrame`가 `subFrameCount`와 bounding-box 관련 count byte를 먼저 읽고
  - count가 0이 아닐 때는 `DecodeBoundingBoxFromBAR/FILE` 계열이 먼저 stream을 소비한 뒤
  - 마지막에 `EndDecodeFrameFromBAR/FILE`가 subframe list를 읽는 구조로 보인다.
- `CGxPZxFrameBB::GetTotalBoundingBoxCount / GetBoundingBoxCount / GetBoundingBox`가 이 bbox block 해석을 다시 확인해 준다.
  - frame `+0x20/+0x21`은 bbox group count byte
  - frame `+0x22`는 bbox format variant
  - frame `+0x1c`는 bbox record array
  - variant `1/3` bbox record는 사실상 `x:s16, y:s16, w:u16, h:u16`
  - variant `0`은 packed 4-byte form을 8-byte record로 확장하고, variant `3`은 두 group count를 합산한다.
  - public type selector도 정리된다.
    - `GetBoundingBoxCount(0)` / `GetBoundingBox(..., 0, index)` = attack box group
    - `GetBoundingBoxCount(1)` / `GetBoundingBox(..., 1, index)` = damage box group
    - other type 값은 두 그룹의 union bounding box를 만든다.
- 따라서 raw `PZF` payload는 "항상 frame header 직후에 subframe record가 온다"고 가정하면 안 된다.
  - `010.pzx`처럼 bbox count가 0인 샘플은 바로 subframe list가 시작되지만
  - `004.pzx` 같은 variant `1` 샘플은 bbox record가 먼저 나오고
  - `082.pzx` 같은 variant `3` 샘플은 bbox 이후 subframe record 중간에 control-like extra payload가 섞여 보인다.

## Asset Cross-check

네이티브에서 복원한 위 레이아웃을 실제 `.pzx` zlib stream에 대입하면, asset 쪽에서도 꽤 강하게 닫힌다.

- 루트 `.pzx` 헤더의 앞 16바이트는 현재 다음처럼 읽는 편이 가장 타당하다.

```text
0x00  "PZX\x01"
0x04  PZD subresource offset
0x08  PZF subresource offset
0x0C  PZA subresource offset
```

- raw subresource를 직접 따라가면 `PZF/PZA` 쪽도 네이티브와 같은 단위로 읽힌다.
  - `field8`의 `PZF` segment는 `header:u8`, `frameCount:u16`, `u32 frameOffset[frameCount]`를 가진다.
  - `field12`의 `PZA` segment는 `header:u8`, `clipCount:u16`, `u32 clipOffset[clipCount]`를 가진다.
  - compressed mode일 때는 index table 뒤에 `unpackedSize:u32`, `packedSize:u32`, 그리고 하나의 zlib blob이 붙는다.
- `field4`의 `PZD` segment는 `PZF/PZA`처럼 하나의 generic reader로 닫히지 않고, 실제로 두 가지 native layout으로 갈린다.
  - `type 8` (`header[0] = 0x08`): `205/205` stems에서 `PZD` 구간 내부 zlib stream이 정확히 하나만 나오고, 그 decoded payload는 `first-stream`이며 chunk count가 항상 `contentCount`와 같다.
  - `type 7` (`header[0] = 0x07`): `48/48` stems에서 `PZD` 구간 내부 zlib stream이 정확히 `contentCount`개 나오고, 각 decoded payload는 standalone `row-stream`이다.
  - 즉 asset-side runtime equivalence 기준으로는 `PZD` image pool이 이제 닫힌다.
    - `type 8`: `subFrameIndex == first-stream chunk index`
    - `type 7`: `subFrameIndex == PZD region 안의 N번째 row-stream`
  - sample:
    - `010/082/208/004.pzx`: `type 8`
    - `000/020/030/041/107/180.pzx`: `type 7`
  - raw byte layout도 이제 native parser 기준으로 정리된다.
    - `type 7 flags=0`: root `field4` 바로 뒤에 `u32 imageOffset[contentCount]`가 오고, 각 entry는 `.pzx` file-local absolute offset으로 per-image block 시작을 가리킨다.
      - block = `localPaletteCount:u8`, `localPalette16[count]:u16`, `width:u16`, `height:u16`, `mode:u8`, `rawExtra:u8`, `0xCDCD:u16`, `unpackedSize:u32`, `packedSize:u32`, `zlib rowstream`
    - `type 7 flags=1`: root header 뒤에 `globalPaletteCount:u8 + globalPalette16[count]:u16`가 먼저 오고, 그 다음 `u32 imageOffset[contentCount]`가 온다.
      - 각 entry는 역시 `.pzx` file-local absolute offset이고, 이번에는 바로 `16-byte descriptor + zlib rowstream`을 가리킨다.
    - `type 8`: root header 뒤에 optional `globalPaletteCount:u8 + globalPalette16[count]:u16`, `unpackedSize:u32`, `packedSize:u32`, zlib blob이 붙는다.
      - inflate된 memory stream의 시작은 decoded-relative `u32 imageOffset[contentCount]` table이고, 첫 entry는 항상 `contentCount * 4`다.
      - 각 entry는 `width:u16`, `height:u16`, `mode:u8`, `rawExtra:u8`, `0xCDCD:u16`, `payloadLen:u32`, `reserved:u32`, `rowstream body`로 시작하는 chunk header를 가리킨다.
      - `rawExtra`는 raw header에서는 `0xCD`로 보이지만, `CGxZeroPZDParser::DecodeImageData`는 `1`이 아닌 값을 모두 `0`으로 정규화한다.
- 즉 later zlib stream 일부는 독립 포맷이 아니라, raw `PZF/PZA` subresource payload가 다시 노출된 결과일 가능성이 높다.
- 실제로 raw `PZF` frame parser를 자산측에 내리면:
  - `253/253` stems에서 raw embedded `PZF`가 frame 단위로 exact-parse 된다.
  - `216` stems는 raw `PZF` payload가 zlib stream index `1`과 byte-identical 하다.
  - 즉 다수 stem에서 두 번째 zlib stream은 “frame-record 후보”가 아니라 native `PZF` payload 그 자체다.
- 현재 working `PZF` frame shape는 다음과 같다.

```text
frame:
  subFrameCount:u8
  bboxCount0:u8
  bboxCount1:u8?   // formatVariant == 3 only
  bboxRecords[...] // formatVariant dependent
  repeat subFrameCount times:
    subFrameIndex:u16
    x:s16
    y:s16
    extraFlag:u8
    extraPayload: variable
```

- 여기서 `extraPayload`는 자산측 exact-fit inference다.
  - 일부 record는 `extraFlag` 바이트만큼 short payload를 붙인다. 예: `... 01 03`
  - 일부 record는 `extraFlag + 4` 바이트 payload를 붙이며, 흔한 모양은 `66 xx 00 00 00` / `67 xx 00 00 00`
  - 전체 집계상 nonzero `extraPayload`는 `6004`개 subframe에 나타나고, dominant family는 `67+u32` / `66+u32` marker형이다.
  - 이 hybrid length rule은 asset exact-fit 기준으로는 닫히고, `EndDecodeFrameFromBAR/FILE`가 실제로 `extraLen:u8`와 heap-allocated `extraPtr`를 native frame record에 저장한다.
- `EndDecodeFrameFromBAR/FILE`는 normal path에서 정확히 다음을 수행한다.
  - caller가 넘긴 별도 `u16 subFrameIndex[]` 배열에 image index를 저장
  - frame-local `subframe[0x10]` record에 `bitmap*=0`, `x:s16`, `y:s16`, `extraPtr`, `extraLen`를 채움
  - 즉 `extraPayload`는 parser artifact가 아니라, native runtime이 보존하는 정식 per-subframe field다.
- `PZD` image count를 `PZF` parser의 subframe bound로 다시 넣으면 asset-side ambiguity도 줄어든다.
  - raw `PZF` parser에 `max_subframe_index = PZD.contentCount - 1` 제약을 주면 `253/253` stems 모두 parse를 유지한다.
  - relation 집계는 `exact-max-plus-one = 244`, `in-range = 7`, `empty = 2`, `out-of-range = 0`이다.
  - 이전 `255/511/65296`류 outlier는 native `extraPayload` backtracking이 너무 느슨해서 생긴 잘못된 분기였다.
- bbox token도 native getter 기준으로 해석이 닫혔다.
  - `CGxPZFParser::GetAttCount`는 raw token의 high nibble, `GetDamCount`는 low nibble을 그대로 꺼낸다.
  - `CGxPZxFrameBB`의 mode는 `PZF formatVariant`와 대응한다.
    - mode `0`: packed attack/damage counts + compact 4-byte box (`x:i8, y:i8, w:u8, h:u8`)
    - mode `1`: explicit generic count + compact 4-byte box
    - mode `2`: reference point list (`x:s16, y:s16`)
    - mode `3`: explicit attack count/token0 + damage count/token1 + full 8-byte box (`x:s16, y:s16, w:u16, h:u16`)
  - 현재 parsed asset set에서는 `explicit-att-dam`이 `251` stems, `compact-box-list`가 `2` stems이고, reference-point mode는 아직 보이지 않는다.
  - 집계 총량은 attack `1468`, damage `1260`, generic `11`, reference `0`이다.
  - collision filter mask도 의미가 보인다.
    - rect collision (`CollisionDetect(rect, filter)`)는 low byte만 쓴다.
      - `0x01 = attack boxes`
      - `0x02 = damage boxes`
      - `0x03 = both`
    - frame-vs-frame collision (`CollisionDetect(other, ..., filter)`)는 low nibble이 self 쪽, high nibble이 other 쪽이다.
      - self: `0x01 attack`, `0x02 damage`, `0x03 both`
      - other: `0x10 attack`, `0x20 damage`, `0x30 both`
    - `filter & 0xFF00 == 0xFF00`이면 type-specific result를 버리고 generic hit `1`만 돌려준다.
  - type-specific collision return code도 정리된다.
    - rect collision: `2 = attack box hit`, `3 = damage box hit`
    - frame-vs-frame collision: `4 = self attack vs other damage`, `5 = self damage vs other attack`, `6 = attack vs attack`, `7 = damage vs damage`
    - `1 = generic collision` 또는 caller가 upper byte로 type 구분을 무시하게 한 경우
- `CGxPZxFrame::Draw`와 `GsPZxSubFrame`는 이 `0x10-byte` record의 앞쪽만 쓴다.
  - `+0x00` bitmap pointer
  - `+0x04/+0x06` local x/y
  - `+0x08/+0x0C` extra pointer/length은 plain draw path에서 소비되지 않는다.
- 실제 consumer는 effect-aware `PZD` loader다.
  - `CGxEffectPZDMgr::LoadImage` / `CGxEffectExPZDMgr::LoadImage`는 cache miss 시 `subframe + 0x08`을 그대로 `tagEffect*`로 넘겨 `CGxEffectPZD::GetBitmap`을 호출한다.
  - `CGxEffectPZD::GetBitmap`은 그 `tagEffect*`를 다시 `ApplyEffect`로 그대로 넘긴다.
  - 즉 asset parser가 보는 `extraPtr + extraLen` 구조가 runtime effect bytecode input과 직접 대응된다.
  - `CGxEffectPZDMgr::FindEffectedImage` / `CGxEffectExPZDMgr::FindEffectedImage`는 두 subframe의 `extraPtr/extraLen`을 비교할 때 바이트값 `<= 4`만 opcode로 취급한다.
  - 현재 전체 asset 집계에서 이 filtered cache-key histogram은 `0:13746, 1:4, 2:24, 3:2278, 4:68`다.
  - 즉 `extraPayload`는 cache/reuse key로도 쓰이지만, 이 집계는 "실행되는 effect bytecode" 전체와는 다르다.
- `HasFlipEffect`는 같은 payload를 별도로 훑되 `3/4`만 flip-class opcode로 취급한다.
  - 결과는 `0 = no flip opcode`, `1 = all effective opcodes are 3/4`, `2 = 3/4와 다른 executable opcode가 섞여 있음`으로 정리된다.
  - normal frame access에서는 `stride = 0x10`, effect-style access에서는 `stride = 0x18`을 쓴다.
- 실제 effect 실행은 `CGxEffectPZD::ApplyEffect`가 담당한다.
  - 이 함수는 바이트값 `1..100`만 effect opcode로 실행한다.
  - `0`은 무시되고, `>= 101` (`0x65`, `0x66`, `0x67`, `0x70`, `0x7f` 등)은 실행되지 않는다.
  - `CGxEffectPZDC1/C2` constructor가 handler 슬롯을 채우는 순서를 따라가면 exact mapping도 닫힌다.
    - `1 = ROTATE_CW90`
    - `2 = ROTATE_CCW90`
    - `3 = FLIP_LR`
    - `4 = FLIP_UD`
    - `5..100 = ChangePalette program id`
  - `CGxEffectPZD::DoEffect_ChangePalette`는 실제로 `effectType - 5`를 `CGxMPLParser::GetChangePalette(...)`에 넘긴다.
- 따라서 현재 asset 전체에서 보는 runtime opcode histogram은 다음이다.
  - `1:4, 2:24, 3:2278, 4:68, 5:261, 6:11, 7:280, 8:68, 9:4, 10:93, 11:14, 12:43, 13:7, 14:16, 15:9, 20:4, 24:1, 28:1, 30:6, 40:8, 44:7, 50:14, 57:1, 60:4, 70:20, 72:4, 80:31, 86:1, 89:7, 99:15, 100:89`
  - 대표 sequence는 `(3)`, `(7)`, `(5)`, `(10)`, `(100)`, `(4,3)`, `(3,7)`, `(44,99)`, `(3,100)`이다.
- 별도 fast path도 보인다.
  - `CGxEffectPZDMgr::LoadImage*`는 `extraLen == 1`이고 그 1-byte 값이 `0x65..0x74`이면 effected-bitmap 생성 경로 대신 normal image load 쪽으로 빠진다.
  - 하지만 `PZD.contentCount` bound를 다시 넣은 corrected parse 기준으로는 이 single-byte family가 실제 asset에서 더 이상 남지 않는다.
  - 즉 이전 `66:15, 67:57, 71:1`은 base `PZF` exact-fit 관점에서는 parse artifact였고, native fast path 자체만 남아 있는 상태다.
  - 다만 selector semantics 자체가 artifact는 아니다. `EffectEx` family parser는 `0x65..0x74`와 `0x7f`를 별도 draw selector로 승격한다.
- cache node 쪽도 확인됐다.
  - `CGxEffectPZDMgr::AddNewEFFECTED_BITMAP` / `CGxEffectExPZDMgr::AddNewEFFECTED_BITMAP`는 effect mode flag가 켜진 경우 source subframe의 `extraLen + extraPtr`를 새 cache entry에 통째로 복제한다.
  - 반면 cache lookup(`FindEffectedImage`)은 여전히 `<= 4` 바이트만 비교한다.
  - 따라서 non-executed envelope byte는 runtime cache object에는 남지만, 적어도 primary cache-match key는 아니다.
- parallel family도 닫혔다.
  - standalone loader `GsLoadPzf` / `GsLoadPzfPart`는 실제로 `CGxZeroEffectExPZDMgr`와 `CGxZeroEffectExPZFMgr`를 직접 생성한다.
  - `CGxEffectExPZFParser::EndDecodeFrameFromBAR/FILE`는 `stride = 0x18` subframe record를 만들고:
    - raw `extraLen + extraPtr`를 `+0x08/+0x0c`에 저장하고
    - `extra`를 읽는 동안 마지막 `0x65..0x74` 또는 `0x7f`를 `+0x10` selector byte로 저장하고
    - 그 selector를 볼 때마다 stream에서 추가 `u32`를 읽어 `+0x14` parameter로 저장한다.
  - `CGxPZxEffectExFrame::__Draw`는 plain draw path에서 이 `+0x10/+0x14`를 실제로 소비한다.
    - selector가 `0x65..0x74` 또는 `0x7f`이면 16-entry table lookup을 거쳐 module/draw mode를 고르고
    - selector-associated `u32` parameter를 함께 bitmap draw call로 넘긴다.
    - exact rodata map은 `0x65->1(Blend)`, `0x66->1(Blend)`, `0x67->2(Add)`, `0x68->3(Sub)`, `0x69->6(Lighten)`, `0x6a->7(Darken)`, `0x6b->8(Different)`, `0x6c->9(Negative)`, `0x6d->10(Gray)`, `0x6e->11(RGB)`, `0x6f->12(RGBHalf)`, `0x70->13(RGBAdd)`, `0x71..0x74->19(Fx)`, `0x7f->4(Void)`다.
    - 이 이름은 `SetBlendFunc(enumDrawOP, ...)`가 채우는 `g_funcBlend / g_funcAdd / g_funcVoid / g_funcLighten / g_funcDarken / g_funcRGBAdd / g_funcFx` slot과 `DrawNative` jump table case가 같은 GOT entry를 쓰는지로 교차검증했다.
    - zero family도 같은 번호계를 쓴다. `SetZeroBlendFunc(enumDrawOP, zero, clipZero)` 기준으로 selector가 실제로 쓰는 op들은 `g_funcZeroBlend/Add/Void/Lighten/Darken/RGBAdd/Fx`와 대응하는 `g_funcClipZero*` pair로 내려간다.
    - `0x71..0x74`는 전부 `drawOp 19 (0x13)`으로 collapse되고, 이 경우 parser가 읽은 trailing `u32`는 버려진 채 `selector - 0x71`이 runtime parameter로 들어간다.
    - 이 special family는 `CGxZeroEffectExPZFMgr::ChangeModule`이 쓰는 module slot (`0..3`)과 맞물린다.
    - current APK asset set에서는 실제로 `0x71/0x72`만 관측되고, module histogram은 `0:171, 1:32`다.
    - `__DrawFast`는 이 special branch를 타지 않는다.
  - 따라서 `66/67/70/71/7f`는 `EffectEx` family에서는 executable opcode가 아니라 draw/module selector이고, `CGxEffectPZD::ApplyEffect`가 실행하는 `1..100` opcode 계층과 별개다.
- 현재 APK의 extracted asset table에는 standalone `.pzf/.pzd` 파일이 없다.
  - 그리고 embedded `.pzx` set은 `253/253`이 base `PZF`의 `0x10-byte` subframe layout으로 exact-fit 된다.
  - 그래서 이번 브랜치에서 이미 닫은 current-game path는 `CGxPZxMgr -> CGxPZFMgr/PZAMgr` base family이고, `EffectEx/ZeroEffectEx`는 parallel native family로 정리하는 편이 맞다.
- asset-side 교차검증도 이 해석을 지지한다.
  - runtime sequence `(3)`은 실제 raw payload `19`종에서 나온다. 대표형은 `03`, `0367ff000000`, `6603000000`, `67ff00000003`, `037100000000`이다.
  - runtime sequence `(4,3)`도 `8`종 payload(`0403`, `040367ff000000`, `660400000003`, `67eb0000000403`, ...)에서 공통으로 나온다.
  - 반대로 `(7) -> 6607000000`, `(10) -> 660a000000`, `(100) -> 6764000000`, `(44,99) -> 702c630000`처럼 특정 envelope family에만 묶인 opcode sequence도 있다.
  - 즉 envelope byte는 effect semantics를 바꾸는 실행 opcode는 아니지만, payload family 구분에는 계속 남아 있다.
- raw `PZD type 7`도 한 단계 더 보인다.
  - `SeekIndexTable`가 읽는 entry는 subresource-relative가 아니라 `.pzx` file-local absolute offset이다.
  - 그래서 `type 7 flags=0`의 table 값 `64`는 `field4` 안에서의 `64`가 아니라, 파일 절대 offset `0x40`을 가리킨다.
  - 이 관점으로 다시 읽으면 `020/029/033/000` 계열의 local palette block과 `180` 계열의 global palette + direct descriptor block이 모두 네이티브 `DecodeImageData`와 맞는다.
  - `type 8`은 raw region 안에 table이 보이지 않는 이유가 whole-stream compressed `CGxZeroPZDParser` path였기 때문이다.
    - raw region에서는 `unpackedSize + packedSize + zlib`
    - inflate 이후 memory stream에서는 decoded-relative index table
  - 즉 raw `PZD` index / descriptor encoding 자체는 이제 닫혔다.
- `tools/arel_wars1/inspect_binary_assets.py`는 이제 exact-fit animation clip stream을 인식한다.
- 현재 휴리스틱은 다음이다.
  - stream 전체가 `frameCount:u8 + frameCount * 8-byte frame record`의 clip 연속체로 끝까지 정확히 소진될 것
  - 각 frame record는 `frameIndex:u16`, `delay:u8`, `x:s16`, `y:s16`, `control:u8`
  - `delay`와 `x/y`는 네이티브에서 보이는 runtime 범위에 맞춰 제한한다.
- 이 조건으로 APK 전체를 다시 스캔하면:
  - exact-fit animation clip stream이 `144`개 stem에서 검출된다.
  - 검출된 stream index는 전부 `2`다.
  - 즉 다수 자산에서 "세 번째 zlib stream = PZA animation blob"이 거의 확정적이다.
- 현재까지 확인된 전체 범위는 다음과 같다.
  - `frameIndex`: `0..85`
  - `delay`: `0..32`
  - `x`: 항상 `0`
  - `y`: `-80..10`
  - `control`: 확인된 exact-fit stream에서는 모두 `0`
- raw `PZA` subresource 기준으로 보면 범위는 더 넓다.
  - `159`개 stem에서 `PZA` index table + payload가 clip 구조로 정확히 읽힌다.
  - 이 중 `145`개는 decompressed payload가 zlib stream index `2`와 byte-identical 하다.
  - 즉 third stream은 “대체로 PZA”가 아니라, 상당수 stem에서 raw `PZA` subresource payload 그 자체다.
- clip 개수 분포도 자연스럽다.
  - single-clip stem이 가장 많고
  - 그 다음이 3-clip stem이다.
  - 즉 "한 sprite 안에 여러 animation clip" 구조와 잘 맞는다.
- 이전에 보이던 mismatch도 이제 설명된다.
  - `frameIndex`는 visible `frame-record stream` 길이가 아니라 raw `PZF` subresource의 `frameCount`를 가리킨다.
  - raw `PZA`가 읽히는 `159`개 stem 기준으로 `frameIndex`는 모두 `PZF` frame pool 범위 안에 있다.
  - 그 중 `143`개는 `max(frameIndex) + 1 == PZF frameCount`가 정확히 성립한다.
  - 나머지 `16`개도 sparse reference일 뿐 out-of-range는 아니다.
- 예: `082.pzx`
  - raw `PZF frameCount = 86`
  - raw `PZA frameIndex range = 0..85`
  - 즉 이전의 “visible frame-record 수보다 `frameIndex`가 크다”는 현상은 그 frame-record stream이 실제 `PZF` frame pool이 아니었기 때문에 생긴 오해다.
- 더 나아가, 예전 `frame-record` heuristic도 native `PZF` 재해석으로 정리된다.
  - `51` stems는 old frame-record parser의 `recordOffsetsPreview`가 raw `PZF` frame offset table prefix와 정확히 맞는다.
  - 즉 disassemble 브랜치 관점에서 그 stream을 별도 timeline format으로 볼 이유는 크게 줄었다.
  - 남는 문제는 “tail이 시간축인가?”가 아니라 `PZF extraPayload`와 `PZD subframe`가 각각 무엇을 의미하느냐로 바뀌었다.

## Current Status

현재 APK의 embedded `.pzx` decode는 native-equivalent 기준으로 사실상 닫혔다.

- root `PZX\x01` header는 `PZD/PZF/PZA` subresource offset table이다.
- `PZD`는 `type 7` row-stream list와 `type 8` whole-stream-compressed first-stream sheet로 닫혔다.
- `PZF`는 frame pool / bbox / subframe / `extraLen + extraPtr`까지 base family layout이 닫혔다.
- `PZA`는 clip offset table, per-frame `frameIndex/delay/x/y/control`, 그리고 `CGxPZxAni::DoPlay` state machine까지 닫혔다.
- bbox API selector와 collision return/filter도 런타임 의미가 정리됐다.
- `globalDelayBias(+3)`는 현재 build 기준 dormant signed bias field다.
- `66/67/70...` selector byte는 `EffectEx/ZeroEffectEx` parallel family에서는 draw/module selector + trailing `u32` parameter로 소비되고, current embedded `.pzx` set은 base family exact-fit path로 소비된다.

## Residual Gaps

1. `bbox variant 2` reference-point mode는 code path는 남아 있지만, current asset set에 샘플이 없고 `GetReferencePointCount/GetReferencePoint` 정적 caller도 보이지 않는다.
   - current APK 기준으로는 dormant feature 쪽에 가깝다.
2. standalone `EffectEx/ZeroEffectEx` raw parser는 native semantics가 정리됐지만, 현재 APK에는 `.pzf/.pzd` 샘플이 없어서 asset-side exact-fit parser까지는 아직 구현하지 않았다.
