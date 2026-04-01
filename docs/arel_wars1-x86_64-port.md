# Arel Wars 1 x86_64 Packaging Status

이 문서는 current repo 기준으로 "x86_64 안드로이드에서 완전히 정상 실행되는 APK"가 왜 아직 닫히지 않았는지, 그리고 어떤 잔업은 이미 해결됐는지를 따로 정리한다.

## Closed

- current APK asset decode는 닫혔다.
  - embedded `PZX/PZD/PZF/PZA` path는 [verify_current_apk_closure.py](C:/vs/other/arelwars/tools/arel_wars1/verify_current_apk_closure.py)로 회귀 검증된다.
- APK runtime audit를 자동화했다.
  - [audit_apk_runtime.py](C:/vs/other/arelwars/tools/arel_wars1/audit_apk_runtime.py)
- exploded APK 재패키징과 서명을 자동화했다.
  - [package_apk.py](C:/vs/other/arelwars/tools/arel_wars1/package_apk.py)
  - current extract tree 기준으로 signed rebuild도 실제로 생성 확인했다.

## Verified Blockers

`python tools/arel_wars1/audit_apk_runtime.py --apk arel_wars1/arel_wars_1.apk --workspace-root .` 결과, x86_64 readiness는 `False`다.

근거는 명확하다.

1. APK 안 native payload가 `lib/armeabi/libgameDSO.so` 하나뿐이다.
2. 이 binary는 `ELF32 / EM_ARM`이다.
3. Java launcher가 `System.loadLibrary("gameDSO")`를 하드코딩한다.
4. 렌더러 lifecycle이 전부 native entrypoint에 묶여 있다.
   - `NativeInitWithBufferSize`
   - `NativeRender`
   - `NativeResize`
   - `NativePauseClet`
   - `NativeResumeClet`
   - `NativeDestroyClet`
5. repo에는 Android project도 없고, `libgameDSO.so`를 다시 빌드할 source tree도 없다.

즉 current workspace에서 가능한 것은 "APK repack + re-sign"까지이고, "x86_64에서 정상 실행"은 replacement native library 없이는 닫히지 않는다.

## What A Real x86_64 Port Still Needs

1. `lib/x86_64/libgameDSO.so`를 제공해야 한다.
   - 이름도 `gameDSO`여야 Java launcher patch 없이 바로 붙는다.
2. `com.gamevil.nexus2.Natives`가 기대하는 JNI surface를 맞춰야 한다.
   - direct `Java_*` export와 `JNI_OnLoad` registration path를 모두 고려해야 한다.
3. `NexusGLRenderer`가 기대하는 OpenGL lifecycle을 동일하게 재현해야 한다.
4. `Natives`가 넘기는 Android bridge 기능도 유지해야 한다.
   - device info
   - asset/file I/O
   - sound/vibrate
   - UI listener bridge
   - purchase/IAP callback

decode/recovery 관점에서는 이미 충분한 데이터가 있다. 하지만 x86_64 run 관점에서 마지막 남은 문제는 pure packaging이 아니라 native port 자체다.

## Rebuild Commands

Audit:

```powershell
python tools/arel_wars1/audit_apk_runtime.py `
  --apk arel_wars1/arel_wars_1.apk `
  --workspace-root . `
  --output recovery/arel_wars1/native_tmp/apk_runtime_audit.json
```

Repack + sign from exploded tree:

```powershell
python tools/arel_wars1/package_apk.py `
  --input-dir recovery/arel_wars1/native_tmp/extract/apk_unzip `
  --output-apk recovery/arel_wars1/native_tmp/arel_wars_1-repacked-signed.apk `
  --keystore recovery/arel_wars1/native_tmp/debug.keystore `
  --create-keystore
```

이 rebuild는 current extracted tree를 다시 서명된 APK로 만드는 데는 충분하다. 단, 여전히 ARM32 `libgameDSO.so`를 그대로 담기 때문에 x86_64 native port를 대체하지는 않는다.
