package com.gamevil.ArelWars2.global;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

public final class Aw2BootstrapStageResolver {
    private static final String ASSET_PATH = "bootstrap/aw2_bootstrap_stage_candidates.json";
    private static final String DEFAULT_STAGE_STEM = "000";

    private Aw2BootstrapStageResolver() {
    }

    public static JSONObject buildLauncherTraceExtra(Context context) {
        JSONObject extra = new JSONObject();
        try {
            JSONObject candidate = resolveStageCandidate(context, DEFAULT_STAGE_STEM);
            extra.put("bootstrapStageStem", DEFAULT_STAGE_STEM);
            extra.put("bootstrapCandidateSource", "static-stage-candidate-report");
            extra.put("bootstrapStageCandidate", candidate == null ? JSONObject.NULL : candidate);
        } catch (JSONException ignored) {
        }
        return extra;
    }

    public static JSONObject buildLauncherVerificationPatch(Context context) {
        try {
            JSONObject candidate = resolveStageCandidate(context, DEFAULT_STAGE_STEM);
            if (candidate == null) {
                return null;
            }
            JSONObject patch = new JSONObject();
            patch.put("traceId", context.getPackageName() + ":stage:" + DEFAULT_STAGE_STEM);
            patch.put("familyId", candidate.opt("familyIdCandidate"));
            patch.put("aiIndex", candidate.opt("aiIndexCandidate"));
            patch.put("stageTitle", candidate.opt("stageTitleCandidate"));
            patch.put("routeLabel", candidate.opt("routeLabelCandidate"));
            patch.put("preferredMapIndex", candidate.opt("preferredMapIndexCandidate"));
            patch.put("resumeTargetScene", "stage:" + DEFAULT_STAGE_STEM);
            patch.put("resumeTargetStageBinding", DEFAULT_STAGE_STEM);
            patch.put("scenePhaseSequence", new JSONArray().put("ArelWars2Launcher").put("stage:" + DEFAULT_STAGE_STEM));
            return patch;
        } catch (JSONException ignored) {
            return null;
        }
    }

    private static JSONObject resolveStageCandidate(Context context, String stageStem) {
        try {
            JSONObject root = readJsonAsset(context);
            JSONArray candidates = root.optJSONArray("candidates");
            if (candidates == null) {
                return null;
            }
            for (int index = 0; index < candidates.length(); index++) {
                JSONObject candidate = candidates.optJSONObject(index);
                if (candidate == null) {
                    continue;
                }
                if (stageStem.equals(candidate.optString("scriptStem"))) {
                    return candidate;
                }
            }
            return null;
        } catch (IOException | JSONException ignored) {
            return null;
        }
    }

    private static JSONObject readJsonAsset(Context context) throws IOException, JSONException {
        try (InputStream inputStream = context.getAssets().open(ASSET_PATH)) {
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int read;
            while ((read = inputStream.read(buffer)) != -1) {
                outputStream.write(buffer, 0, read);
            }
            return new JSONObject(outputStream.toString(StandardCharsets.UTF_8.name()));
        }
    }
}
