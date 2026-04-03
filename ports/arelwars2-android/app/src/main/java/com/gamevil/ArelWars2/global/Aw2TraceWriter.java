package com.gamevil.ArelWars2.global;

import android.app.Activity;
import android.content.ComponentName;
import android.os.Environment;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

public final class Aw2TraceWriter {
    public static final String SPEC_VERSION = "aw2-bootstrap-trace-v1";
    public static final String FILE_NAME = "aw2_bootstrap_trace.json";

    private Aw2TraceWriter() {
    }

    public static void write(Activity activity, String sceneLabel, String publicKey, JSONObject extra) {
        try {
            JSONObject root = new JSONObject();
            root.put("specVersion", SPEC_VERSION);
            root.put("packageName", activity.getPackageName());
            root.put("updatedAtEpochMs", System.currentTimeMillis());
            root.put("sceneLabel", sceneLabel);
            root.put("publicKey", publicKey == null ? JSONObject.NULL : publicKey);

            ComponentName component = activity.getComponentName();
            root.put(
                    "focusedComponent",
                    component == null ? JSONObject.NULL : component.flattenToShortString()
            );

            if (extra != null) {
                root.put("extra", extra);
            } else {
                root.put("extra", new JSONObject());
            }

            JSONObject verificationTrace = new JSONObject();
            verificationTrace.put("traceId", activity.getPackageName() + ":" + sceneLabel);
            verificationTrace.put("familyId", JSONObject.NULL);
            verificationTrace.put("aiIndex", JSONObject.NULL);
            verificationTrace.put("stageTitle", sceneLabel);
            verificationTrace.put("storyboardIndex", JSONObject.NULL);
            verificationTrace.put("routeLabel", JSONObject.NULL);
            verificationTrace.put("preferredMapIndex", JSONObject.NULL);
            verificationTrace.put("scriptEventCountExpected", JSONObject.NULL);
            verificationTrace.put("dialogueEventsSeen", JSONObject.NULL);
            verificationTrace.put("dialogueAnchorsSeen", new JSONArray());
            verificationTrace.put("sceneCommandIdsSeen", new JSONArray());
            verificationTrace.put("sceneDirectiveKindsSeen", new JSONArray());
            verificationTrace.put("scenePhaseSequence", new JSONArray().put(sceneLabel));
            verificationTrace.put("objectivePhaseSequence", new JSONArray());
            verificationTrace.put("resultType", JSONObject.NULL);
            verificationTrace.put("unlockTarget", JSONObject.NULL);
            verificationTrace.put("saveSlotIdentity", JSONObject.NULL);
            verificationTrace.put("resumeTargetScene", sceneLabel);
            verificationTrace.put("resumeTargetStageBinding", JSONObject.NULL);
            root.put("verificationTrace", verificationTrace);

            File externalRoot = activity.getExternalFilesDir(null);
            if (externalRoot == null) {
                externalRoot = new File(Environment.getExternalStorageDirectory(), activity.getPackageName());
            }
            if (!externalRoot.exists() && !externalRoot.mkdirs()) {
                return;
            }
            File traceFile = new File(externalRoot, FILE_NAME);
            try (FileOutputStream outputStream = new FileOutputStream(traceFile, false)) {
                outputStream.write(root.toString(2).getBytes(StandardCharsets.UTF_8));
            }
        } catch (JSONException ignored) {
        } catch (Exception ignored) {
        }
    }
}

