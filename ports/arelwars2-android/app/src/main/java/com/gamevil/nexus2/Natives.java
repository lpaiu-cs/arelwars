package com.gamevil.nexus2;

public final class Natives {
    static {
        System.loadLibrary("gameDSO");
    }

    private Natives() {
    }

    public static native void InitializeJNIGlobalRef();
    public static native void NativeAsyncTimerCallBack(int callbackIndex);
    public static native void NativeAsyncTimerCallBackTimeStemp(int callbackIndex, int timestamp);
    public static native void NativeDestroyClet();
    public static native void NativeGetPlayerName(String playerName);
    public static native String NativeGetPublicKey();
    public static native void NativeHandleInAppBiiling(String productId, int requestCode, int resultCode);
    public static native void NativeInitDeviceInfo(int width, int height);
    public static native void NativeInitWithBufferSize(int width, int height);
    public static native void NativeIsNexusOne(boolean enabled);
    public static native void NativeNetTimeOut();
    public static native void NativePauseClet();
    public static native void NativeRender();
    public static native void NativeResize(int width, int height);
    public static native void NativeResponseIAP(String response, int code);
    public static native void NativeResumeClet();
    public static native int NativeUnLockItem(int groupId, int itemId);
    public static native void SetCletStarted(boolean started);
    public static native void handleCletEvent(int eventType, int arg0, int arg1, int arg2);
}

