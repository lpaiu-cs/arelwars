#include <jni.h>

#include <GLES2/gl2.h>
#include <android/log.h>

#include <mutex>
#include <set>
#include <sstream>
#include <string>

namespace {

constexpr const char* kLogTag = "aw2-bootstrap";

struct RuntimeState {
    std::mutex mutex;
    int width = 0;
    int height = 0;
    int frame_count = 0;
    int timer_count = 0;
    int last_event = 0;
    int last_arg0 = 0;
    int last_arg1 = 0;
    int last_arg2 = 0;
    int last_item_group = -1;
    int last_item_id = -1;
    bool surface_initialized = false;
    bool paused = false;
    bool started = false;
    bool nexus_one = false;
    std::string player_name = "oracle-shell";
    std::set<std::pair<int, int>> unlocked_items;
};

RuntimeState g_state;

void Log(const std::string& message) {
    __android_log_write(ANDROID_LOG_INFO, kLogTag, message.c_str());
}

std::string BuildPublicKeyLocked() {
    std::ostringstream builder;
    builder
            << "aw2-bootstrap:"
            << (g_state.surface_initialized ? "surface" : "cold")
            << ":"
            << (g_state.started ? "started" : "idle")
            << ":frames=" << g_state.frame_count;
    return builder.str();
}

void ClearFrame(float red, float green, float blue) {
    glViewport(0, 0, g_state.width > 0 ? g_state.width : 1, g_state.height > 0 ? g_state.height : 1);
    glClearColor(red, green, blue, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
}

}  // namespace

extern "C" JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* /* vm */, void* /* reserved */) {
    Log("JNI_OnLoad");
    return JNI_VERSION_1_6;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_InitializeJNIGlobalRef(JNIEnv* /* env */, jclass /* clazz */) {
    Log("InitializeJNIGlobalRef");
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeAsyncTimerCallBack(JNIEnv* /* env */, jclass /* clazz */, jint callback_index) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.timer_count += 1;
    g_state.last_event = callback_index;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeAsyncTimerCallBackTimeStemp(
        JNIEnv* /* env */,
        jclass /* clazz */,
        jint callback_index,
        jint timestamp) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.last_event = callback_index;
    g_state.last_arg0 = timestamp;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeDestroyClet(JNIEnv* /* env */, jclass /* clazz */) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.paused = true;
    Log("NativeDestroyClet");
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeGetPlayerName(JNIEnv* env, jclass /* clazz */, jstring player_name) {
    const char* raw = player_name != nullptr ? env->GetStringUTFChars(player_name, nullptr) : nullptr;
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.player_name = raw != nullptr ? raw : "";
    if (raw != nullptr) {
        env->ReleaseStringUTFChars(player_name, raw);
    }
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_gamevil_nexus2_Natives_NativeGetPublicKey(JNIEnv* env, jclass /* clazz */) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    const std::string value = BuildPublicKeyLocked();
    return env->NewStringUTF(value.c_str());
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeHandleInAppBiiling(
        JNIEnv* env,
        jclass /* clazz */,
        jstring product_id,
        jint request_code,
        jint result_code) {
    const char* raw = product_id != nullptr ? env->GetStringUTFChars(product_id, nullptr) : nullptr;
    std::ostringstream builder;
    builder << "NativeHandleInAppBiiling product=" << (raw != nullptr ? raw : "<null>")
            << " request=" << request_code
            << " result=" << result_code;
    Log(builder.str());
    if (raw != nullptr) {
        env->ReleaseStringUTFChars(product_id, raw);
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeInitDeviceInfo(JNIEnv* /* env */, jclass /* clazz */, jint width, jint height) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.width = width;
    g_state.height = height;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeInitWithBufferSize(
        JNIEnv* /* env */,
        jclass /* clazz */,
        jint width,
        jint height) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.width = width;
    g_state.height = height;
    g_state.surface_initialized = true;
    Log("NativeInitWithBufferSize");
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeIsNexusOne(JNIEnv* /* env */, jclass /* clazz */, jboolean enabled) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.nexus_one = enabled == JNI_TRUE;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeNetTimeOut(JNIEnv* /* env */, jclass /* clazz */) {
    Log("NativeNetTimeOut");
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativePauseClet(JNIEnv* /* env */, jclass /* clazz */) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.paused = true;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeRender(JNIEnv* /* env */, jclass /* clazz */) {
    float red = 0.08f;
    float green = 0.08f;
    float blue = 0.12f;
    int frame_count = 0;
    {
        std::lock_guard<std::mutex> lock(g_state.mutex);
        g_state.frame_count += 1;
        frame_count = g_state.frame_count;
        if (g_state.surface_initialized) {
            green = g_state.started ? 0.36f : 0.18f;
            blue = g_state.paused ? 0.15f : 0.32f;
            red = g_state.nexus_one ? 0.25f : 0.12f;
        }
    }
    if (frame_count == 1) {
        Log("NativeRender:first-frame");
    }
    ClearFrame(red, green, blue);
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeResize(JNIEnv* /* env */, jclass /* clazz */, jint width, jint height) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.width = width;
    g_state.height = height;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeResponseIAP(JNIEnv* env, jclass /* clazz */, jstring response, jint code) {
    const char* raw = response != nullptr ? env->GetStringUTFChars(response, nullptr) : nullptr;
    std::ostringstream builder;
    builder << "NativeResponseIAP code=" << code << " response=" << (raw != nullptr ? raw : "<null>");
    Log(builder.str());
    if (raw != nullptr) {
        env->ReleaseStringUTFChars(response, raw);
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_NativeResumeClet(JNIEnv* /* env */, jclass /* clazz */) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.paused = false;
}

extern "C" JNIEXPORT jint JNICALL
Java_com_gamevil_nexus2_Natives_NativeUnLockItem(JNIEnv* /* env */, jclass /* clazz */, jint group_id, jint item_id) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    const auto inserted = g_state.unlocked_items.emplace(group_id, item_id).second;
    g_state.last_item_group = group_id;
    g_state.last_item_id = item_id;
    return inserted ? 1 : 0;
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_SetCletStarted(JNIEnv* /* env */, jclass /* clazz */, jboolean started) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.started = started == JNI_TRUE;
    Log(g_state.started ? "SetCletStarted=true" : "SetCletStarted=false");
}

extern "C" JNIEXPORT void JNICALL
Java_com_gamevil_nexus2_Natives_handleCletEvent(
        JNIEnv* /* env */,
        jclass /* clazz */,
        jint event_type,
        jint arg0,
        jint arg1,
        jint arg2) {
    std::lock_guard<std::mutex> lock(g_state.mutex);
    g_state.last_event = event_type;
    g_state.last_arg0 = arg0;
    g_state.last_arg1 = arg1;
    g_state.last_arg2 = arg2;
}
