# Arel Wars 1 Recovery

`arel_wars1/arel_wars_1.apk`가 1편의 유일한 원본 아티팩트다. 이 브랜치는 데이터 기반 패턴 추론이나 리메이크 구현이 아니라, APK 안의 네이티브 라이브러리 `lib/armeabi/libgameDSO.so`를 직접 추적해서 원본 디코더/애니메이션 파서를 찾는 데 집중한다.

## Branch Scope

- 유지하는 입력
  - `arel_wars1/arel_wars_1.apk`
  - `recovery/arel_wars1/catalog.json`
- 유지하는 도구
  - `tools/arel_wars1/extract_assets.py`
  - `tools/arel_wars1/inspect_libgameDSO.ps1`
- 현재 브랜치에서 의도적으로 제외한 것
  - `remake/arel-wars1/` 리메이크 워크스페이스
  - 생성형 preview PNG 산출물
  - 데이터 기반 조합/렌더링을 중심으로 한 작업 흐름

## Current Hypothesis

- `.pzx`의 첫 번째 stream은 조각/프레임 데이터에 가깝다.
- 남아 있는 "시간축 재생" 메타데이터는 `PZX` tail을 하나의 불명 blob으로 보는 것보다, 네이티브 코드 안의 `PZA` / `PZF` parser 계층으로 분리해서 보는 쪽이 더 타당하다.
- `CGxPZxMgr::Open`이 내부적으로 `CGxPZAMgr::Open`과 `CGxPZFMgr::Open`을 함께 호출하고, `CGxPZxMgr::LoadAni`가 `CGxPZAMgr::*`로 위임된다는 점이 그 근거다.

## Primary Workflow

네이티브 분석 보고서는 아래 명령으로 갱신한다.

```powershell
powershell -ExecutionPolicy Bypass -File tools/arel_wars1/inspect_libgameDSO.ps1
```

자세한 호출축과 현재 reverse 방향은 [docs/arel_wars1-disassembly.md](/C:/vs/other/arelwars/docs/arel_wars1-disassembly.md)에 정리한다.
