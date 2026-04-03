package org.cocos2dx.lib;

import android.os.Build;
import android.os.Bundle;

import com.gamevil.nexus2.NexusGLActivity;

public class Cocos2dxActivity extends NexusGLActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT > 8) {
            try {
                System.loadLibrary("openslaudio");
            } catch (UnsatisfiedLinkError ignored) {
                // The bootstrap shell tolerates missing audio payloads during bring-up.
            }
        }
    }
}

