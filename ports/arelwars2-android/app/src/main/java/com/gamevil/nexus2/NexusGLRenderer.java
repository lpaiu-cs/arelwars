package com.gamevil.nexus2;

import android.opengl.GLSurfaceView;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

public final class NexusGLRenderer implements GLSurfaceView.Renderer {
    private boolean initialized;

    @Override
    public void onSurfaceCreated(GL10 gl, EGLConfig config) {
        initialized = false;
    }

    @Override
    public void onSurfaceChanged(GL10 gl, int width, int height) {
        if (!initialized) {
            Natives.NativeInitWithBufferSize(width, height);
            initialized = true;
        }
        Natives.NativeResize(width, height);
    }

    @Override
    public void onDrawFrame(GL10 gl) {
        Natives.NativeRender();
    }
}

