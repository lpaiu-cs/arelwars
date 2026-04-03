import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

plugins {
    alias(libs.plugins.android.application)
}

val originalAssetsDir = file("C:/vs/other/arelwars/recovery/arel_wars2/apk_unzip/assets")
val originalApk = file("C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk")
val armLibDir = file("C:/vs/other/arelwars/recovery/arel_wars2/apk_unzip/lib/armeabi")
val bootstrapStageCandidates = file("C:/vs/other/arelwars/recovery/arel_wars2/aw2_bootstrap_stage_candidates.json")
val armRunnerAssetDir = layout.buildDirectory.dir("generated/armRunnerAssets/main")
val bootstrapMetadataAssetDir = layout.buildDirectory.dir("generated/bootstrapMetadataAssets/main")

val releaseAssetEntriesToStrip = setOf(
    "assets/dexopt/baseline.prof",
    "assets/dexopt/baseline.profm",
)

fun rewriteZipWithoutEntries(apkFile: File, entriesToStrip: Set<String>) {
    val tempFile = File(apkFile.parentFile, apkFile.name + ".tmp")
    ZipFile(apkFile).use { sourceZip ->
        ZipOutputStream(FileOutputStream(tempFile)).use { outputZip ->
            sourceZip.entries().asSequence().forEach { sourceEntry ->
                if (sourceEntry.name in entriesToStrip) {
                    return@forEach
                }
                val newEntry = ZipEntry(sourceEntry.name).apply {
                    method = sourceEntry.method
                    comment = sourceEntry.comment
                    extra = sourceEntry.extra
                    time = sourceEntry.time
                    if (sourceEntry.method == ZipEntry.STORED) {
                        size = sourceEntry.size
                        compressedSize = sourceEntry.compressedSize
                        crc = sourceEntry.crc
                    }
                }
                outputZip.putNextEntry(newEntry)
                if (!sourceEntry.isDirectory) {
                    sourceZip.getInputStream(sourceEntry).use { input ->
                        BufferedInputStream(input).copyTo(outputZip)
                    }
                }
                outputZip.closeEntry()
            }
        }
    }
    if (!apkFile.delete()) {
        throw IllegalStateException("Failed to replace release APK: ${apkFile.absolutePath}")
    }
    if (!tempFile.renameTo(apkFile)) {
        throw IllegalStateException("Failed to finalize stripped release APK: ${apkFile.absolutePath}")
    }
}

val prepareArmRunnerAssets by tasks.registering(Copy::class) {
    into(armRunnerAssetDir.map { it.dir("arm_runner") })
    from(originalApk) {
        rename { "arel_wars_2.apk" }
    }
    from(armLibDir) {
        include("libgameDSO.so", "libcocos2d.so", "libcocosdenshion.so", "libopenslaudio.so")
    }
}

val prepareBootstrapMetadataAssets by tasks.registering(Copy::class) {
    into(bootstrapMetadataAssetDir.map { it.dir("bootstrap") })
    from(bootstrapStageCandidates) {
        rename { "aw2_bootstrap_stage_candidates.json" }
    }
}

android {
    namespace = "com.gamevil.ArelWars2.global"
    compileSdk {
        version = release(36)
    }

    defaultConfig {
        applicationId = "com.gamevil.ArelWars2.global"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0-bootstrap"

        ndk {
            abiFilters += listOf("x86", "x86_64")
        }

        externalNativeBuild {
            cmake {
                cppFlags += listOf("-std=c++20", "-Wall", "-Wextra")
            }
        }
    }

    buildTypes {
        debug {
            isDebuggable = true
            applicationIdSuffix = ".bootstrap"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
        resources {
            excludes += releaseAssetEntriesToStrip
        }
    }

    sourceSets {
        getByName("main") {
            if (originalAssetsDir.isDirectory) {
                assets.srcDir(originalAssetsDir)
            }
            assets.srcDir(armRunnerAssetDir.get().asFile)
            assets.srcDir(bootstrapMetadataAssetDir.get().asFile)
        }
    }
}

tasks.matching { it.name.startsWith("merge") && it.name.endsWith("Assets") }.configureEach {
    dependsOn(prepareArmRunnerAssets)
    dependsOn(prepareBootstrapMetadataAssets)
}

tasks.matching { it.name == "packageRelease" || it.name == "assembleRelease" }.configureEach {
    doLast {
        val releaseApk = layout.buildDirectory.file("outputs/apk/release/app-release-unsigned.apk").get().asFile
        if (releaseApk.isFile) {
            rewriteZipWithoutEntries(releaseApk, releaseAssetEntriesToStrip)
        }
    }
}

dependencies {
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.constraintlayout)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
