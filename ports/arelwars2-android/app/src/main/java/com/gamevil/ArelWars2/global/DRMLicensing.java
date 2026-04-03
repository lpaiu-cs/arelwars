package com.gamevil.ArelWars2.global;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Button;
import android.widget.TextView;

import com.gamevil.lib.GvDrmActivity;

import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

import org.json.JSONException;
import org.json.JSONObject;

public final class DRMLicensing extends GvDrmActivity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean continued;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_drm);

        TextView subtitle = findViewById(R.id.drm_subtitle);
        WebView webView = findViewById(R.id.drm_webview);
        Button continueButton = findViewById(R.id.drm_continue);

        subtitle.setText(buildSubtitle());
        configureWebView(webView);
        continueButton.setOnClickListener(view -> continueToLauncher());
        Aw2TraceWriter.write(this, "DRMLicensing", null, buildTraceExtra());

        if (savedInstanceState == null) {
            handler.postDelayed(this::continueToLauncher, 1200L);
        }
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private void configureWebView(WebView webView) {
        WebSettings settings = webView.getSettings();
        settings.setAllowFileAccess(true);
        settings.setJavaScriptEnabled(false);
        webView.loadUrl("file:///android_asset/auth_terms.html");
    }

    private String buildSubtitle() {
        long originalApkSize = probeAssetSize("arm_runner/arel_wars_2.apk");
        long armGameDsoSize = probeAssetSize("arm_runner/libgameDSO.so");
        long authTermsSize = probeAssetSize("auth_terms.html");
        return String.format(
                Locale.US,
                "package=%s | originalApk=%d | armGameDSO=%d | authTerms=%d",
                getPackageName(),
                originalApkSize,
                armGameDsoSize,
                authTermsSize
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
            extra.put("originalApkSize", probeAssetSize("arm_runner/arel_wars_2.apk"));
            extra.put("armGameDsoSize", probeAssetSize("arm_runner/libgameDSO.so"));
            extra.put("authTermsSize", probeAssetSize("auth_terms.html"));
        } catch (JSONException ignored) {
        }
        return extra;
    }

    private void continueToLauncher() {
        if (continued) {
            return;
        }
        continued = true;
        Intent intent = new Intent(this, ArelWars2Launcher.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        finish();
        overridePendingTransition(0, 0);
    }
}
