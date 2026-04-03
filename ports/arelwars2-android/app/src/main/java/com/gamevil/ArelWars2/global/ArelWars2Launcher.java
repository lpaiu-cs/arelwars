package com.gamevil.ArelWars2.global;

import android.os.Bundle;

import com.gamevil.nexus2.Natives;

import org.gamevil.CCGXNative.CCGXActivity;

import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

import org.json.JSONException;
import org.json.JSONObject;

public final class ArelWars2Launcher extends CCGXActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Natives.SetCletStarted(true);
        updateRuntimeStatus(buildLauncherStatus());
        Aw2TraceWriter.write(this, "ArelWars2Launcher", Natives.NativeGetPublicKey(), buildTraceExtra());
    }

    private String buildLauncherStatus() {
        return String.format(
                Locale.US,
                "launcher=%s | pza000=%d | originalApk=%d",
                getClass().getSimpleName(),
                probeAssetSize("pc/000.pza"),
                probeAssetSize("arm_runner/arel_wars_2.apk")
        );
    }

    private long probeAssetSize(String path) {
        try (InputStream stream = getAssets().open(path)) {
            return stream.available();
        } catch (IOException ignored) {
            return -1L;
        }
    }

    private JSONObject buildTraceExtra() {
        JSONObject extra = new JSONObject();
        try {
            extra.put("pza000Size", probeAssetSize("pc/000.pza"));
            extra.put("originalApkSize", probeAssetSize("arm_runner/arel_wars_2.apk"));
        } catch (JSONException ignored) {
        }
        return extra;
    }
}
