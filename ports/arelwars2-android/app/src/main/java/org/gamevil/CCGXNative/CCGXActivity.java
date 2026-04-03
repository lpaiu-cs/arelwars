package org.gamevil.CCGXNative;

import android.os.Bundle;

import org.cocos2dx.lib.Cocos2dxActivity;

public class CCGXActivity extends Cocos2dxActivity {
    static {
        System.loadLibrary("cocos2d");
        System.loadLibrary("cocosdenshion");
        System.loadLibrary("gameDSO");
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setPackageName(getApplication().getPackageName());
        updateRuntimeStatus("bootstrap=ccgx | package=" + getPackageName());
    }
}

