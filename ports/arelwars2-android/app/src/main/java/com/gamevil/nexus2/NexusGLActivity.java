package com.gamevil.nexus2;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.widget.FrameLayout;
import android.widget.TextView;

import com.gamevil.ArelWars2.global.Aw2TraceWriter;
import com.gamevil.ArelWars2.global.R;
import com.gamevil.lib.GvActivity;

public class NexusGLActivity extends GvActivity {
    private static final int TIMER_CALLBACK = 77;

    protected NexusGLSurfaceView mGLView;
    private TextView runtimeStatusView;
    private final Handler loopHandler = new Handler(Looper.getMainLooper());
    private int timerTicks;
    private String packageNameForNative = "";

    private final Runnable timerRunnable = new Runnable() {
        @Override
        public void run() {
            timerTicks += 1;
            int timestamp = (int) (SystemClock.elapsedRealtime() & 0x7fffffff);
            Natives.NativeAsyncTimerCallBackTimeStemp(TIMER_CALLBACK, timestamp);
            if ((timerTicks % 4) == 0) {
                Natives.NativeAsyncTimerCallBack(TIMER_CALLBACK);
                String publicKey = Natives.NativeGetPublicKey();
                updateRuntimeStatus(
                        "bootstrap=tick"
                                + " | package=" + (packageNameForNative.isEmpty() ? getPackageName() : packageNameForNative)
                                + " | publicKey=" + publicKey
                );
                Aw2TraceWriter.write(NexusGLActivity.this, NexusGLActivity.this.getClass().getSimpleName(), publicKey, null);
            }
            loopHandler.postDelayed(this, 250L);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_game);

        runtimeStatusView = findViewById(R.id.runtime_status);
        FrameLayout gameContainer = findViewById(R.id.game_container);
        mGLView = new NexusGLSurfaceView(this);
        gameContainer.addView(
                mGLView,
                new FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.MATCH_PARENT,
                        FrameLayout.LayoutParams.MATCH_PARENT
                )
        );

        DisplayMetrics metrics = new DisplayMetrics();
        getWindowManager().getDefaultDisplay().getMetrics(metrics);
        Natives.NativeInitDeviceInfo(metrics.widthPixels, metrics.heightPixels);
        Natives.NativeIsNexusOne(false);

        updateRuntimeStatus(
                "bootstrap=created"
                        + " | display=" + metrics.widthPixels + "x" + metrics.heightPixels
                        + " | package=" + getPackageName()
        );
    }

    @Override
    protected void onResume() {
        super.onResume();
        Natives.InitializeJNIGlobalRef();
        if (mGLView != null) {
            mGLView.onResume();
        }
        Natives.NativeResumeClet();
        scheduleTimer();
        onGameResume();
    }

    @Override
    protected void onPause() {
        loopHandler.removeCallbacks(timerRunnable);
        if (mGLView != null) {
            mGLView.onPause();
        }
        Natives.NativePauseClet();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        loopHandler.removeCallbacks(timerRunnable);
        Natives.NativeDestroyClet();
        super.onDestroy();
    }

    public void setPackageName(String packageName) {
        this.packageNameForNative = packageName;
    }

    @Override
    public void onGameResume() {
        String publicKey = Natives.NativeGetPublicKey();
        updateRuntimeStatus(
                "bootstrap=resume"
                        + " | package=" + (packageNameForNative.isEmpty() ? getPackageName() : packageNameForNative)
                        + " | publicKey=" + publicKey
        );
        Aw2TraceWriter.write(this, getClass().getSimpleName(), publicKey, null);
    }

    protected final void updateRuntimeStatus(String detail) {
        if (runtimeStatusView != null) {
            runtimeStatusView.setText(detail);
        }
    }

    private void scheduleTimer() {
        loopHandler.removeCallbacks(timerRunnable);
        loopHandler.post(timerRunnable);
    }
}
