package com.gamevil.nexus2;

import android.content.Context;
import android.opengl.GLSurfaceView;
import android.util.AttributeSet;
import android.view.MotionEvent;

public final class NexusGLSurfaceView extends GLSurfaceView {
    private final NexusGLRenderer renderer = new NexusGLRenderer();

    public NexusGLSurfaceView(Context context) {
        super(context);
        init();
    }

    public NexusGLSurfaceView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    private void init() {
        setEGLContextClientVersion(2);
        setPreserveEGLContextOnPause(true);
        setRenderer(renderer);
        setRenderMode(RENDERMODE_CONTINUOUSLY);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        final int action = event.getActionMasked();
        final int index = event.getActionIndex();
        final int x = Math.round(event.getX(index));
        final int y = Math.round(event.getY(index));
        Natives.handleCletEvent(3000 + action, x, y, event.getPointerId(index));
        return true;
    }
}

