-keepattributes *Annotation*
-keep class com.getcapacitor.** { *; }
-keep class org.apache.cordova.** { *; }
-keep class androidx.webkit.** { *; }
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keep class * extends com.getcapacitor.Plugin {
    *;
}
-keep @com.getcapacitor.annotation.CapacitorPlugin class * {
    *;
}
-dontwarn org.apache.cordova.**
-dontwarn androidx.webkit.**
