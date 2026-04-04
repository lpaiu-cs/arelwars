#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APK_PATH = ROOT / "arel_wars2" / "arel_wars_2.apk"
DEXDUMP_DIR = ROOT / "recovery" / "arel_wars2" / "dexdump"
NATIVE_TMP = ROOT / "recovery" / "arel_wars2" / "native_tmp"
BUILD_DIR = NATIVE_TMP / "offline_hook_build"
REPORT_PATH = NATIVE_TMP / "aw2_offline_hook_report.json"
TOOLING_DIR = NATIVE_TMP / "tooling"

ANDROID_SDK = Path(os.environ.get("ANDROID_SDK_ROOT", Path.home() / "AppData" / "Local" / "Android" / "Sdk"))
BUILD_TOOLS = ANDROID_SDK / "build-tools" / "36.1.0"
ZIPALIGN = BUILD_TOOLS / "zipalign.exe"
APKSIGNER = BUILD_TOOLS / "apksigner.bat"
DEBUG_KEYSTORE = Path.home() / ".android" / "debug.keystore"
LLVM_READELF = ANDROID_SDK / "ndk" / "30.0.14904198" / "toolchains" / "llvm" / "prebuilt" / "windows-x86_64" / "bin" / "llvm-readelf.exe"
JAVA = shutil.which("java") or "java"
TOOLING_DOWNLOADS = {
    "smali-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/smali/2.5.2/smali-2.5.2.jar",
    "baksmali-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/baksmali/2.5.2/baksmali-2.5.2.jar",
    "util-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/util/2.5.2/util-2.5.2.jar",
    "dexlib2-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/dexlib2/2.5.2/dexlib2-2.5.2.jar",
    "jcommander-1.64.jar": "https://repo1.maven.org/maven2/com/beust/jcommander/1.64/jcommander-1.64.jar",
    "guava-27.1-android.jar": "https://repo1.maven.org/maven2/com/google/guava/guava/27.1-android/guava-27.1-android.jar",
    "antlr-3.5.2.jar": "https://repo1.maven.org/maven2/org/antlr/antlr/3.5.2/antlr-3.5.2.jar",
    "antlr-runtime-3.5.2.jar": "https://repo1.maven.org/maven2/org/antlr/antlr-runtime/3.5.2/antlr-runtime-3.5.2.jar",
    "stringtemplate-3.2.1.jar": "https://repo1.maven.org/maven2/org/antlr/stringtemplate/3.2.1/stringtemplate-3.2.1.jar",
    "jsr305-3.0.2.jar": "https://repo1.maven.org/maven2/com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar",
}


def ensure_tooling() -> None:
    TOOLING_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in TOOLING_DOWNLOADS.items():
        target = TOOLING_DIR / filename
        if target.exists():
            continue
        urllib.request.urlretrieve(url, target)


def tooling_classpath() -> str:
    return str(TOOLING_DIR / "*")


PATCHES = [
    {
        "label": "billing-supported-always-true",
        "file": "com/gamevil/ArelWars2/global/BillingService.smali",
        "signature": ".method public checkBillingSupported()Z",
        "body": """
.method public checkBillingSupported()Z
    .registers 2

    const/4 v0, 0x1

    return v0
.end method
""".strip(),
    },
    {
        "label": "gamevil-live-check-login-noop",
        "file": "com/gamevil/nexus2/live/GamevilLive.smali",
        "signature": ".method public checkLogin()V",
        "body": """
.method public checkLogin()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gamevil-gift-connect-noop",
        "file": "com/gamevil/nexus2/cpi/GamevilGift.smali",
        "signature": ".method public static connect(Landroid/content/Context;Ljava/lang/String;III)V",
        "body": """
.method public static connect(Landroid/content/Context;Ljava/lang/String;III)V
    .registers 5

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-connect-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static connect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V",
        "body": """
.method public static connect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V
    .registers 5

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-banner-address-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static addNewsBannerAddressId(Landroid/app/Activity;III)V",
        "body": """
.method public static addNewsBannerAddressId(Landroid/app/Activity;III)V
    .registers 4

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-end-session-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static endSession()V",
        "body": """
.method public static endSession()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-hide-all-banners-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static hideAllNewsBanners()V",
        "body": """
.method public static hideAllNewsBanners()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "tapjoy-connect-noop",
        "file": "com/tapjoy/TapjoyConnect.smali",
        "signature": ".method public static requestTapjoyConnect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)V",
        "body": """
.method public static requestTapjoyConnect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)V
    .registers 3

    return-void
.end method
""".strip(),
    },
    {
        "label": "gamevil-gift-end-session-noop",
        "file": "com/gamevil/nexus2/cpi/GamevilGift.smali",
        "signature": ".method public static endSession()V",
        "body": """
.method public static endSession()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvutils-is-dl-runtime-false",
        "file": "com/gamevil/lib/utils/GvUtils.smali",
        "signature": ".method public static isDLRuntime()Z",
        "body": """
.method public static isDLRuntime()Z
    .registers 2

    const/4 v0, 0x0

    return v0
.end method
""".strip(),
    },
    {
        "label": "gvprofile-is-terms-accepted-true",
        "file": "com/gamevil/lib/profile/GvProfileData.smali",
        "signature": ".method public static isTermsAccepted(Landroid/content/Context;)I",
        "body": """
.method public static isTermsAccepted(Landroid/content/Context;)I
    .registers 2
    .param p0, "_context"    # Landroid/content/Context;

    .prologue
    const/4 v0, 0x1

    return v0
.end method
""".strip(),
    },
    {
        "label": "natives-ccgxisfileexist-asset-first",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method public static ccgxIsFileExist(Ljava/lang/String;)I",
        "body": """
.method public static ccgxIsFileExist(Ljava/lang/String;)I
    .registers 11
    .param p0, "strFile"    # Ljava/lang/String;

    invoke-static {p0}, Lcom/gamevil/nexus2/Natives;->isAssetExist(Ljava/lang/String;)I

    move-result v0

    if-nez v0, :cond_34

    invoke-static {}, Lcom/gamevil/nexus2/Natives;->ccgxGetPath()Ljava/io/File;

    move-result-object v1

    new-instance v2, Ljava/io/File;

    invoke-virtual {v1}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v3

    invoke-direct {v2, v3, p0}, Ljava/io/File;-><init>(Ljava/lang/String;Ljava/lang/String;)V

    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v3

    if-eqz v3, :cond_1d

    invoke-virtual {v2}, Ljava/io/File;->canRead()Z

    move-result v3

    if-eqz v3, :cond_1d

    invoke-virtual {v2}, Ljava/io/File;->length()J

    move-result-wide v4

    long-to-int v0, v4

    goto :cond_34

    :cond_1d
    invoke-static {p0}, Lcom/gamevil/nexus2/Natives;->isDownloadFileExist(Ljava/lang/String;)I

    move-result v0

    if-nez v0, :cond_34

    const-string v6, "eng/table/"

    invoke-virtual {p0, v6}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v6

    if-nez v6, :cond_26

    const-string v6, "kor/table/"

    invoke-virtual {p0, v6}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v6

    if-eqz v6, :cond_34

    :cond_26
    const/16 v6, 0xa

    invoke-virtual {p0, v6}, Ljava/lang/String;->substring(I)Ljava/lang/String;

    move-result-object v6

    new-instance v7, Ljava/lang/StringBuilder;

    const-string v8, "table/"

    invoke-direct {v7, v8}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v7, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v7

    invoke-virtual {v7}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v6

    invoke-static {v6}, Lcom/gamevil/nexus2/Natives;->ccgxIsFileExist(Ljava/lang/String;)I

    move-result v0

    :cond_34
    return v0
.end method
""".strip(),
    },
    {
        "label": "natives-ccgxloaddata-asset-first",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method public static ccgxLoadDataFromFile(Ljava/lang/String;)[B",
        "body": """
.method public static ccgxLoadDataFromFile(Ljava/lang/String;)[B
    .registers 13
    .param p0, "strFile"    # Ljava/lang/String;

    invoke-static {p0}, Lcom/gamevil/nexus2/Natives;->readAssete(Ljava/lang/String;)[B

    move-result-object v0

    if-nez v0, :cond_4f

    invoke-static {}, Lcom/gamevil/nexus2/Natives;->ccgxGetPath()Ljava/io/File;

    move-result-object v1

    new-instance v2, Ljava/io/File;

    invoke-virtual {v1}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v3

    invoke-direct {v2, v3, p0}, Ljava/io/File;-><init>(Ljava/lang/String;Ljava/lang/String;)V

    invoke-virtual {v2}, Ljava/io/File;->exists()Z

    move-result v3

    if-eqz v3, :cond_35

    invoke-virtual {v2}, Ljava/io/File;->canRead()Z

    move-result v3

    if-eqz v3, :cond_35

    :try_start_1f
    new-instance v3, Ljava/io/FileInputStream;

    invoke-direct {v3, v2}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    invoke-virtual {v2}, Ljava/io/File;->length()J

    move-result-wide v4

    long-to-int v6, v4

    new-array v0, v6, [B

    new-instance v7, Ljava/io/BufferedInputStream;

    invoke-direct {v7, v3}, Ljava/io/BufferedInputStream;-><init>(Ljava/io/InputStream;)V

    invoke-virtual {v7, v0}, Ljava/io/BufferedInputStream;->read([B)I

    move-result v8

    invoke-virtual {v7}, Ljava/io/BufferedInputStream;->close()V

    if-ne v6, v8, :cond_35
    :try_end_34
    .catch Ljava/lang/Exception; {:try_start_1f .. :try_end_34} :catch_35

    goto :cond_4f

    :catch_35
    :cond_35
    invoke-static {p0}, Lcom/gamevil/nexus2/Natives;->loadFileFromStorage(Ljava/lang/String;)[B

    move-result-object v0

    if-nez v0, :cond_4f

    const-string v9, "eng/table/"

    invoke-virtual {p0, v9}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v9

    if-nez v9, :cond_41

    const-string v9, "kor/table/"

    invoke-virtual {p0, v9}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v9

    if-eqz v9, :cond_4f

    :cond_41
    const/16 v9, 0xa

    invoke-virtual {p0, v9}, Ljava/lang/String;->substring(I)Ljava/lang/String;

    move-result-object v9

    new-instance v10, Ljava/lang/StringBuilder;

    const-string v11, "table/"

    invoke-direct {v10, v11}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v10, v9}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v10

    invoke-virtual {v10}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v9

    invoke-static {v9}, Lcom/gamevil/nexus2/Natives;->ccgxLoadDataFromFile(Ljava/lang/String;)[B

    move-result-object v0

    :cond_4f
    return-object v0
.end method
""".strip(),
    },
    {
        "label": "cocos-openassetfile-asset-cache-fallback",
        "file": "org/cocos2dx/lib/Cocos2dxActivity.smali",
        "signature": ".method public static ccOpenAssetFile(Ljava/lang/String;)Z",
        "body": """
.method public static ccOpenAssetFile(Ljava/lang/String;)Z
    .registers 10
    .param p0, "fileName"    # Ljava/lang/String;

    invoke-static {p0}, Lcom/gamevil/nexus2/Natives;->ccgxLoadDataFromFile(Ljava/lang/String;)[B

    move-result-object v0

    if-eqz v0, :cond_3b

    array-length v1, v0

    if-lez v1, :cond_3b

    sget-object v1, Lorg/cocos2dx/lib/Cocos2dxActivity;->asIStream:Ljava/io/FileInputStream;

    if-eqz v1, :cond_14

    :try_start_c
    sget-object v1, Lorg/cocos2dx/lib/Cocos2dxActivity;->asIStream:Ljava/io/FileInputStream;

    invoke-virtual {v1}, Ljava/io/FileInputStream;->close()V

    const/4 v1, 0x0

    sput-object v1, Lorg/cocos2dx/lib/Cocos2dxActivity;->asIStream:Ljava/io/FileInputStream;
    :try_end_14
    .catch Ljava/io/IOException; {:try_start_c .. :try_end_14} :catch_15

    :catch_15
    :cond_14
    :try_start_14
    sget-object v1, Lorg/cocos2dx/lib/Cocos2dxActivity;->myActivity:Lcom/gamevil/lib/GvActivity;

    invoke-virtual {v1}, Lcom/gamevil/lib/GvActivity;->getFilesDir()Ljava/io/File;

    move-result-object v1

    new-instance v2, Ljava/io/File;

    const-string v3, "__aw2_asset_cache.bin"

    invoke-direct {v2, v1, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    new-instance v3, Ljava/io/FileOutputStream;

    invoke-direct {v3, v2}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V

    invoke-virtual {v3, v0}, Ljava/io/FileOutputStream;->write([B)V

    invoke-virtual {v3}, Ljava/io/FileOutputStream;->close()V

    new-instance v3, Ljava/io/FileInputStream;

    invoke-direct {v3, v2}, Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V

    sput-object v3, Lorg/cocos2dx/lib/Cocos2dxActivity;->asIStream:Ljava/io/FileInputStream;

    const/4 v4, 0x1

    return v4
    :try_end_39
    .catch Ljava/lang/Exception; {:try_start_14 .. :try_end_39} :catch_3b

    :catch_3b
    :cond_3b
    invoke-static {}, Lcom/gamevil/lib/downloader/GvDownloadHelper;->shared()Lcom/gamevil/lib/downloader/GvDownloadHelper;

    move-result-object v4

    sget-object v5, Lorg/cocos2dx/lib/Cocos2dxActivity;->myActivity:Lcom/gamevil/lib/GvActivity;

    invoke-virtual {v4, v5, p0}, Lcom/gamevil/lib/downloader/GvDownloadHelper;->ccOpenFileFromExpansion(Landroid/content/Context;Ljava/lang/String;)Z

    move-result v4

    return v4
.end method
""".strip(),
    },
    {
        "label": "aw2-drm-oncreate-explicit-launcher",
        "file": "com/gamevil/ArelWars2/global/DRMLicensing.smali",
        "signature": ".method public onCreate(Landroid/os/Bundle;)V",
        "body": """
.method public onCreate(Landroid/os/Bundle;)V
    .registers 5
    .param p1, "icicle"    # Landroid/os/Bundle;

    const/4 v2, 0x1
    const/4 v1, 0x0

    invoke-super {p0, p1}, Lcom/gamevil/lib/GvDrmActivity;->onCreate(Landroid/os/Bundle;)V

    invoke-static {v2}, Lcom/gamevil/lib/utils/GvUtils;->setDebugLogEnable(Z)V

    const-string v0, "com.gamevil.ArelWars2.global.ArelWars2Launcher"
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setComponentName(Ljava/lang/String;)V

    const/16 v0, 0x73ae
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setGid(I)V

    const/4 v0, 0x5
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setCompany(B)V

    const/16 v0, 0xe
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setSale_cd(B)V

    const-string v0, "TJN9VGMBJ7PX6K4DXTT2"
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setFlurryApiKey(Ljava/lang/String;)V

    const-string v0, "1190b8e5574bb4c67a033fd4a6b53e90"
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setCihEmbers(Ljava/lang/String;)V

    invoke-static {v1}, Lcom/gamevil/lib/profile/GvProfileData;->setUsingNetworkEncryption(Z)V
    invoke-static {v1}, Lcom/gamevil/lib/profile/GvProfileData;->setNeedToCheckSIM(Z)V
    invoke-static {v1}, Lcom/gamevil/lib/profile/GvProfileData;->setUseTestServer(Z)V

    invoke-static {v2}, Lcom/gamevil/lib/profile/GvProfileData;->setServerType(B)V
    invoke-static {}, Lcom/gamevil/lib/profile/GvProfileData;->makeProfileBundleData()V

    new-instance v0, Landroid/content/Intent;
    invoke-direct {v0}, Landroid/content/Intent;-><init>()V

    const-string v1, "com.gamevil.ArelWars2.global"
    const-string v2, "com.gamevil.ArelWars2.global.ArelWars2Launcher"
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;

    const-string v1, "profileBundle"
    invoke-static {}, Lcom/gamevil/lib/profile/GvProfileData;->getProfileBundle()Landroid/os/Bundle;
    move-result-object v2
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Bundle;)Landroid/content/Intent;

    invoke-virtual {p0, v0}, Lcom/gamevil/ArelWars2/global/DRMLicensing;->startActivity(Landroid/content/Intent;)V
    invoke-virtual {p0}, Lcom/gamevil/ArelWars2/global/DRMLicensing;->finish()V
    return-void
.end method
""".strip(),
    },
    {
        "label": "natives-update-dialogue-noop",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method public static updateDialogue()V",
        "body": """
.method public static updateDialogue()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "natives-change-ui-status-skip-news",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method private static changeUIStatus(I)V",
        "body": """
.method private static changeUIStatus(I)V
    .registers 2
    .param p0, "_status"    # I

    .prologue
    const/16 v0, 0xe

    if-eq p0, v0, :goto_title

    const/16 v0, 0x13

    if-eq p0, v0, :goto_title

    const/16 v0, 0x14

    if-eq p0, v0, :goto_title

    const/16 v0, 0x15

    if-eq p0, v0, :goto_title

    goto :goto_dispatch

    :goto_title
    const/4 p0, 0x1

    :goto_dispatch
    sget-object v0, Lcom/gamevil/nexus2/NexusGLActivity;->uiViewControll:Lcom/gamevil/nexus2/ui/NeoUIControllerView;

    invoke-virtual {v0, p0}, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->changeUIStatus(I)V

    return-void
.end method
""".strip(),
    },
    {
        "label": "natives-net-connect-always-true",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method private static netConnect()I",
        "body": """
.method private static netConnect()I
    .registers 1

    .prologue
    const/4 v0, 0x1

    return v0
.end method
""".strip(),
    },
    {
        "label": "neo-change-ui-status-skip-news",
        "file": "com/gamevil/nexus2/ui/NeoUIControllerView.smali",
        "signature": ".method public changeUIStatus(I)V",
        "body": """
.method public changeUIStatus(I)V
    .registers 3
    .param p1, "_status"    # I

    .prologue
    const/16 v0, 0xe

    if-eq p1, v0, :goto_fulltouch

    const/16 v0, 0x13

    if-eq p1, v0, :goto_fulltouch

    const/16 v0, 0x14

    if-eq p1, v0, :goto_fulltouch

    const/16 v0, 0x15

    if-eq p1, v0, :goto_fulltouch

    goto :goto_dispatch

    :goto_fulltouch
    const/4 p1, 0x1

    :goto_dispatch
    iput p1, p0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->uiStatus:I

    const/4 v0, 0x1

    iput-boolean v0, p0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->isStatusChanging:Z

    invoke-virtual {p0}, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->hideAllUI()V

    return-void
.end method
""".strip(),
    },
    {
        "label": "aw2-ui-set-state-skip-news",
        "file": "com/gamevil/ArelWars2/ui/ArelWars2UIControllerView.smali",
        "signature": ".method public setUIState()V",
        "body": """
.method public setUIState()V
    .registers 4

    .prologue
    const/4 v2, 0x0

    .line 275
    iget v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->uiStatus:I

    const/16 v1, 0xe
    if-eq v0, v1, :force_fulltouch

    const/16 v1, 0x13
    if-eq v0, v1, :force_fulltouch

    const/16 v1, 0x14
    if-eq v0, v1, :force_fulltouch

    const/16 v1, 0x15
    if-eq v0, v1, :force_fulltouch

    goto :dispatch

    :force_fulltouch
    const/4 v0, 0x1
    iput v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->uiStatus:I

    :dispatch
    sparse-switch v0, :sswitch_data_aa

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->fullTouch:Lcom/gamevil/ArelWars2/ui/UIFullTouch;
    invoke-virtual {v0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->setIsHidden(Z)V
    goto :goto_end

    :sswitch_logo
    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->fullTouch:Lcom/gamevil/ArelWars2/ui/UIFullTouch;
    invoke-virtual {v0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->setIsHidden(Z)V
    goto :goto_end

    :sswitch_help
    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->fullTouch:Lcom/gamevil/ArelWars2/ui/UIFullTouch;
    invoke-virtual {v0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->setIsHidden(Z)V

    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, ">>>>>>> UI_STATUS_HELP"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->mHandler:Landroid/os/Handler;
    new-instance v1, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$5;
    invoke-direct {v1, p0}, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$5;-><init>(Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;)V
    invoke-virtual {v0, v1}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z
    goto :goto_end

    :sswitch_title
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, ">>>>>>> UI_STATUS_TITLE"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->fullTouch:Lcom/gamevil/ArelWars2/ui/UIFullTouch;
    invoke-virtual {v0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->setIsHidden(Z)V
    goto :goto_end

    :sswitch_fulltouch
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, ">>>>>>> UI_STATUS_FULLTOUCH"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->fullTouch:Lcom/gamevil/ArelWars2/ui/UIFullTouch;
    invoke-virtual {v0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->setIsHidden(Z)V

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->mHandler:Landroid/os/Handler;
    new-instance v1, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$6;
    invoke-direct {v1, p0}, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$6;-><init>(Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;)V
    invoke-virtual {v0, v1}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z
    goto :goto_end

    :sswitch_exit
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "===== Native : exit ====="
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    sget-object v0, Lcom/gamevil/nexus2/NexusGLActivity;->myActivity:Lcom/gamevil/lib/GvActivity;
    invoke-virtual {v0}, Lcom/gamevil/lib/GvActivity;->finish()V
    goto :goto_end

    :sswitch_edit_text
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, ">>>>>>> UI_STATUS_EDIT_MY_INPUT_VISIBLE"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    invoke-direct {p0}, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->setTextInputVisible()V

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->mHandler:Landroid/os/Handler;
    new-instance v1, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$7;
    invoke-direct {v1, p0}, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$7;-><init>(Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;)V
    invoke-virtual {v0, v1}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->fullTouch:Lcom/gamevil/ArelWars2/ui/UIFullTouch;
    invoke-virtual {v0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->setIsHidden(Z)V

    invoke-static {}, Lcom/gamevil/nexus2/Natives;->HideLoadingDialog()V
    goto :goto_end

    :sswitch_edit_number
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "[DEBUG BB UIController] Call UI_STATUS_EDIT_NUMBER_INPUT_VISIBLE :::: "
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    invoke-direct {p0}, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->setNumberInputVisible()V

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->mHandler:Landroid/os/Handler;
    new-instance v1, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$8;
    invoke-direct {v1, p0}, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView$8;-><init>(Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;)V
    invoke-virtual {v0, v1}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z

    iget-object v0, p0, Lcom/gamevil/ArelWars2/ui/ArelWars2UIControllerView;->fullTouch:Lcom/gamevil/ArelWars2/ui/UIFullTouch;
    invoke-virtual {v0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->setIsHidden(Z)V

    invoke-static {}, Lcom/gamevil/nexus2/Natives;->HideLoadingDialog()V

    :goto_end
    return-void

    :sswitch_data_aa
    .sparse-switch
        0x0 -> :sswitch_logo
        0x1 -> :sswitch_title
        0x4 -> :sswitch_help
        0xe -> :sswitch_fulltouch
        0x10 -> :sswitch_edit_text
        0x1a -> :sswitch_edit_number
        0x68 -> :sswitch_exit
    .end sparse-switch
.end method
""".strip(),
    },
    {
        "label": "aw2-ui-news-runnable-2-noop",
        "file": "com/gamevil/ArelWars2/ui/ArelWars2UIControllerView$2.smali",
        "signature": ".method public run()V",
        "body": """
.method public run()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "aw2-ui-news-runnable-3-noop",
        "file": "com/gamevil/ArelWars2/ui/ArelWars2UIControllerView$3.smali",
        "signature": ".method public run()V",
        "body": """
.method public run()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "aw2-ui-news-runnable-4-noop",
        "file": "com/gamevil/ArelWars2/ui/ArelWars2UIControllerView$4.smali",
        "signature": ".method public run()V",
        "body": """
.method public run()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "neoui-touch-restore-original-forward",
        "file": "com/gamevil/nexus2/ui/NeoUIControllerView.smali",
        "signature": ".method public onTouchEvent(Landroid/view/MotionEvent;)Z",
        "body": """
.method public onTouchEvent(Landroid/view/MotionEvent;)Z
    .registers 7
    .param p1, "ev"    # Landroid/view/MotionEvent;

    .prologue
    sget-object v3, Ljava/lang/System;->out:Ljava/io/PrintStream;

    const-string v4, "AW2 NEO TOUCH"

    invoke-virtual {v3, v4}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    .line 157
    sget-object v1, Lorg/cocos2dx/lib/Cocos2dxGLSurfaceView;->mainView:Lorg/cocos2dx/lib/Cocos2dxGLSurfaceView;

    if-eqz v1, :cond_9

    .line 160
    sget-object v1, Lorg/cocos2dx/lib/Cocos2dxGLSurfaceView;->mainView:Lorg/cocos2dx/lib/Cocos2dxGLSurfaceView;

    invoke-virtual {v1, p1}, Lorg/cocos2dx/lib/Cocos2dxGLSurfaceView;->onTouchEvent(Landroid/view/MotionEvent;)Z

    .line 164
    :cond_9
    iget-object v1, p0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->mDetector:Lcom/gamevil/nexus2/ui/NeoTouchDetector;

    invoke-virtual {v1, p1}, Lcom/gamevil/nexus2/ui/NeoTouchDetector;->onTouchEvent(Landroid/view/MotionEvent;)Z

    .line 166
    iget-object v1, p0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->mContext:Landroid/content/Context;

    check-cast v1, Lcom/gamevil/nexus2/NexusGLActivity;

    iget-boolean v1, v1, Lcom/gamevil/nexus2/NexusGLActivity;->isMessageCome:Z

    if-eqz v1, :cond_1d

    .line 169
    iget-object v1, p0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->mContext:Landroid/content/Context;

    check-cast v1, Lcom/gamevil/nexus2/NexusGLActivity;

    invoke-virtual {v1}, Lcom/gamevil/nexus2/NexusGLActivity;->finish()V

    .line 174
    :cond_1d
    const-wide/16 v1, 0x23

    :try_start_1f
    invoke-static {v1, v2}, Ljava/lang/Thread;->sleep(J)V
    :try_end_22
    .catch Ljava/lang/InterruptedException; {:try_start_1f .. :try_end_22} :catch_24

    .line 179
    :goto_22
    const/4 v1, 0x1

    return v1

    .line 175
    :catch_24
    move-exception v0

    .line 177
    .local v0, "e":Ljava/lang/InterruptedException;
    invoke-virtual {v0}, Ljava/lang/InterruptedException;->printStackTrace()V

    goto :goto_22
.end method
""".strip(),
    },
    {
        "label": "aw2-uifulltouch-restore-safe-original",
        "file": "com/gamevil/ArelWars2/ui/UIFullTouch.smali",
        "signature": ".method public onAction(IFFI)V",
        "body": """
.method public onAction(IFFI)V
    .registers 10
    .param p1, "_uiAreaAction"    # I
    .param p2, "_px"    # F
    .param p3, "_py"    # F
    .param p4, "_pointerId"    # I

    .prologue
    .line 51
    float-to-int v2, p2

    invoke-virtual {p0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->convertScreenX(I)I

    move-result v0

    .line 52
    .local v0, "_x":I
    float-to-int v2, p3

    invoke-virtual {p0, v2}, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->convertScreenY(I)I

    move-result v1

    .line 63
    .local v1, "_y":I
    const/16 v2, 0x65

    if-ne p1, v2, :cond_17

    sget-object v3, Ljava/lang/System;->out:Ljava/io/PrintStream;

    const-string v4, "AW2 UIFULL DOWN"

    invoke-virtual {v3, v4}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    .line 68
    const/16 v2, 0x17

    invoke-static {v2, v0, v1, p4}, Lorg/cocos2dx/lib/Cocos2dxRenderer;->setTouchEvent(IIII)V

    .line 72
    const/4 v2, 0x1

    iput v2, p0, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->mStatus:I

    .line 94
    :cond_16
    :goto_16
    return-void

    .line 74
    :cond_17
    const/16 v2, 0x66

    if-ne p1, v2, :cond_21

    sget-object v3, Ljava/lang/System;->out:Ljava/io/PrintStream;

    const-string v4, "AW2 UIFULL MOVE"

    invoke-virtual {v3, v4}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    .line 77
    const/16 v2, 0x19

    invoke-static {v2, v0, v1, p4}, Lorg/cocos2dx/lib/Cocos2dxRenderer;->setTouchEvent(IIII)V

    goto :goto_16

    .line 82
    :cond_21
    const/16 v2, 0x64

    if-ne p1, v2, :cond_16

    sget-object v3, Ljava/lang/System;->out:Ljava/io/PrintStream;

    const-string v4, "AW2 UIFULL UP"

    invoke-virtual {v3, v4}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    .line 87
    const/16 v2, 0x18

    invoke-static {v2, v0, v1, p4}, Lorg/cocos2dx/lib/Cocos2dxRenderer;->setTouchEvent(IIII)V

    .line 92
    const/4 v2, 0x0

    iput v2, p0, Lcom/gamevil/ArelWars2/ui/UIFullTouch;->mStatus:I

    goto :goto_16
.end method
""".strip(),
    },
    {
        "label": "ccgx-glsurface-restore-original-native-touch",
        "file": "org/gamevil/CCGXNative/CCGXGLSurfaceView.smali",
        "signature": ".method public onTouchEvent(Landroid/view/MotionEvent;)Z",
        "body": """
.method public onTouchEvent(Landroid/view/MotionEvent;)Z
    .registers 30
    .param p1, "event"    # Landroid/view/MotionEvent;

    .prologue
    sget-object v26, Ljava/lang/System;->out:Ljava/io/PrintStream;

    const-string v27, "AW2 GLSURFACE TOUCH"

    invoke-virtual/range {v26 .. v27}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    .line 60
    invoke-virtual/range {p1 .. p1}, Landroid/view/MotionEvent;->getAction()I

    move-result v2

    .line 62
    .local v2, "action":I
    and-int/lit16 v0, v2, 0xff

    move/from16 v25, v0

    packed-switch v25, :pswitch_data_e0

    .line 160
    :cond_b
    :goto_b
    :pswitch_b
    invoke-super/range {p0 .. p1}, Lorg/cocos2dx/lib/Cocos2dxGLSurfaceView;->onTouchEvent(Landroid/view/MotionEvent;)Z

    move-result v25

    return v25

    .line 69
    :pswitch_10
    const v25, 0xff00

    and-int v25, v25, v2

    shr-int/lit8 v11, v25, 0x8

    .line 70
    .local v11, "ptIndexDown":I
    move-object/from16 v0, p1

    invoke-virtual {v0, v11}, Landroid/view/MotionEvent;->getX(I)F

    move-result v13

    .line 71
    .local v13, "xD":F
    move-object/from16 v0, p1

    invoke-virtual {v0, v11}, Landroid/view/MotionEvent;->getY(I)F

    move-result v19

    .line 72
    .local v19, "yD":F
    move-object/from16 v0, p1

    invoke-virtual {v0, v11}, Landroid/view/MotionEvent;->getPointerId(I)I

    move-result v9

    .line 75
    .local v9, "ptIdDown":I
    move/from16 v0, v19

    invoke-static {v9, v13, v0}, Lorg/gamevil/CCGXNative/CCGXNative;->ccgxNativeOnTouchBegin(IFF)V

    goto :goto_b

    .line 84
    .end local v9    # "ptIdDown":I
    .end local v11    # "ptIndexDown":I
    .end local v13    # "xD":F
    .end local v19    # "yD":F
    :pswitch_2f
    const/16 v25, 0x0

    move-object/from16 v0, p1

    move/from16 v1, v25

    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->getX(I)F

    move-result v14

    .line 85
    .local v14, "xDown":F
    const/16 v25, 0x0

    move-object/from16 v0, p1

    move/from16 v1, v25

    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->getY(I)F

    move-result v20

    .line 86
    .local v20, "yDown":F
    const/16 v25, 0x0

    move-object/from16 v0, p1

    move/from16 v1, v25

    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->getPointerId(I)I

    move-result v4

    .line 89
    .local v4, "idDown":I
    move/from16 v0, v20

    invoke-static {v4, v14, v0}, Lorg/gamevil/CCGXNative/CCGXNative;->ccgxNativeOnTouchBegin(IFF)V

    goto :goto_b

    .line 99
    .end local v4    # "idDown":I
    .end local v14    # "xDown":F
    .end local v20    # "yDown":F
    :pswitch_53
    invoke-virtual/range {p1 .. p1}, Landroid/view/MotionEvent;->getPointerCount()I

    move-result v8

    .line 100
    .local v8, "pointerNumber":I
    const/4 v3, 0x0

    .local v3, "i":I
    :goto_58
    if-ge v3, v8, :cond_b

    .line 102
    move-object/from16 v0, p1

    invoke-virtual {v0, v3}, Landroid/view/MotionEvent;->getPointerId(I)I

    move-result v6

    .line 103
    .local v6, "idPointerMove":I
    move-object/from16 v0, p1

    invoke-virtual {v0, v3}, Landroid/view/MotionEvent;->getX(I)F

    move-result v16

    .line 104
    .local v16, "xPointerMove":F
    move-object/from16 v0, p1

    invoke-virtual {v0, v3}, Landroid/view/MotionEvent;->getY(I)F

    move-result v22

    .line 107
    .local v22, "yPointerMove":F
    move/from16 v0, v16

    move/from16 v1, v22

    invoke-static {v6, v0, v1}, Lorg/gamevil/CCGXNative/CCGXNative;->ccgxNativeOnTouchMove(IFF)V

    .line 100
    add-int/lit8 v3, v3, 0x1

    goto :goto_58

    .line 118
    .end local v3    # "i":I
    .end local v6    # "idPointerMove":I
    .end local v8    # "pointerNumber":I
    .end local v16    # "xPointerMove":F
    .end local v22    # "yPointerMove":F
    :pswitch_76
    const v25, 0xff00

    and-int v25, v25, v2

    shr-int/lit8 v12, v25, 0x8

    .line 119
    .local v12, "ptIndexUp":I
    move-object/from16 v0, p1

    invoke-virtual {v0, v12}, Landroid/view/MotionEvent;->getX(I)F

    move-result v17

    .line 120
    .local v17, "xU":F
    move-object/from16 v0, p1

    invoke-virtual {v0, v12}, Landroid/view/MotionEvent;->getY(I)F

    move-result v23

    .line 121
    .local v23, "yU":F
    move-object/from16 v0, p1

    invoke-virtual {v0, v12}, Landroid/view/MotionEvent;->getPointerId(I)I

    move-result v10

    .line 124
    .local v10, "ptIdUp":I
    move/from16 v0, v17

    move/from16 v1, v23

    invoke-static {v10, v0, v1}, Lorg/gamevil/CCGXNative/CCGXNative;->ccgxNativeOnTouchEnd(IFF)V

    goto/16 :goto_b

    .line 133
    .end local v10    # "ptIdUp":I
    .end local v12    # "ptIndexUp":I
    .end local v17    # "xU":F
    .end local v23    # "yU":F
    :pswitch_98
    const/16 v25, 0x0

    move-object/from16 v0, p1

    move/from16 v1, v25

    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->getPointerId(I)I

    move-result v7

    .line 134
    .local v7, "idUp":I
    const/16 v25, 0x0

    move-object/from16 v0, p1

    move/from16 v1, v25

    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->getX(I)F

    move-result v18

    .line 135
    .local v18, "xUp":F
    const/16 v25, 0x0

    move-object/from16 v0, p1

    move/from16 v1, v25

    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->getY(I)F

    move-result v24

    .line 138
    .local v24, "yUp":F
    move/from16 v0, v18

    move/from16 v1, v24

    invoke-static {v7, v0, v1}, Lorg/gamevil/CCGXNative/CCGXNative;->ccgxNativeOnTouchEnd(IFF)V

    goto/16 :goto_b

    .line 147
    .end local v7    # "idUp":I
    .end local v18    # "xUp":F
    .end local v24    # "yUp":F
    :pswitch_bf
    invoke-virtual/range {p1 .. p1}, Landroid/view/MotionEvent;->getPointerCount()I

    move-result v8

    .line 148
    .restart local v8    # "pointerNumber":I
    const/4 v3, 0x0

    .restart local v3    # "i":I
    :goto_c4
    if-ge v3, v8, :cond_b

    .line 150
    move-object/from16 v0, p1

    invoke-virtual {v0, v3}, Landroid/view/MotionEvent;->getPointerId(I)I

    move-result v5

    .line 151
    .local v5, "idPointerCancel":I
    move-object/from16 v0, p1

    invoke-virtual {v0, v3}, Landroid/view/MotionEvent;->getX(I)F

    move-result v15

    .line 152
    .local v15, "xPointerCancel":F
    move-object/from16 v0, p1

    invoke-virtual {v0, v3}, Landroid/view/MotionEvent;->getY(I)F

    move-result v21

    .line 153
    .local v21, "yPointerCancel":F
    move/from16 v0, v21

    invoke-static {v5, v15, v0}, Lorg/gamevil/CCGXNative/CCGXNative;->ccgxNativeOnTouchCancel(IFF)V

    .line 148
    add-int/lit8 v3, v3, 0x1

    goto :goto_c4

    .line 62
    :pswitch_data_e0
    .packed-switch 0x0
        :pswitch_2f
        :pswitch_98
        :pswitch_53
        :pswitch_bf
        :pswitch_b
        :pswitch_10
        :pswitch_76
    .end packed-switch
.end method
""".strip(),
    },
    {
        "label": "cocos2dx-settouch-forward-eventqueue",
        "file": "org/cocos2dx/lib/Cocos2dxRenderer.smali",
        "signature": ".method public static setTouchEvent(IIII)V",
        "body": """
.method public static setTouchEvent(IIII)V
    .registers 5
    .param p0, "action"    # I
    .param p1, "_param1"    # I
    .param p2, "_param2"    # I
    .param p3, "_param3"    # I

    .prologue
    sget-object v0, Lcom/gamevil/nexus2/NexusGLActivity;->uiViewControll:Lcom/gamevil/nexus2/ui/NeoUIControllerView;

    if-eqz v0, :goto_17

    iget-object v0, v0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->eventQueue:Lcom/gamevil/nexus2/ui/EventQueue;

    invoke-virtual {v0}, Lcom/gamevil/nexus2/ui/EventQueue;->IsFull()Z

    move-result v0

    if-eqz v0, :cond_18

    sget-object v0, Lcom/gamevil/nexus2/NexusGLActivity;->uiViewControll:Lcom/gamevil/nexus2/ui/NeoUIControllerView;

    iget-object v0, v0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->eventQueue:Lcom/gamevil/nexus2/ui/EventQueue;

    invoke-virtual {v0}, Lcom/gamevil/nexus2/ui/EventQueue;->ClearEvent()V

    sget-object v0, Lcom/gamevil/nexus2/NexusGLActivity;->uiViewControll:Lcom/gamevil/nexus2/ui/NeoUIControllerView;

    iget-object v0, v0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->eventQueue:Lcom/gamevil/nexus2/ui/EventQueue;

    invoke-virtual {v0, p0, p1, p2, p3}, Lcom/gamevil/nexus2/ui/EventQueue;->Enqueue(IIII)V

    :goto_17
    return-void

    :cond_18
    sget-object v0, Lcom/gamevil/nexus2/NexusGLActivity;->uiViewControll:Lcom/gamevil/nexus2/ui/NeoUIControllerView;

    iget-object v0, v0, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->eventQueue:Lcom/gamevil/nexus2/ui/EventQueue;

    invoke-virtual {v0, p0, p1, p2, p3}, Lcom/gamevil/nexus2/ui/EventQueue;->Enqueue(IIII)V

    goto :goto_17
.end method
""".strip(),
    },
    {
        "label": "ccgx-activity-force-window-focus",
        "file": "org/gamevil/CCGXNative/CCGXActivity.smali",
        "signature": ".method protected onResume()V",
        "body": """
.method protected onResume()V
    .registers 4

    .prologue
    .line 47
    invoke-super {p0}, Lorg/cocos2dx/lib/Cocos2dxActivity;->onResume()V

    invoke-virtual {p0}, Lorg/gamevil/CCGXNative/CCGXActivity;->getWindow()Landroid/view/Window;

    move-result-object v0

    if-eqz v0, :done

    const/16 v1, 0x18

    invoke-virtual {v0, v1}, Landroid/view/Window;->clearFlags(I)V

    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;

    move-result-object v1

    if-eqz v1, :done

    const/4 v2, 0x1

    invoke-virtual {v1, v2}, Landroid/view/View;->setFocusable(Z)V

    invoke-virtual {v1, v2}, Landroid/view/View;->setFocusableInTouchMode(Z)V

    invoke-virtual {v1}, Landroid/view/View;->requestFocus()Z

    invoke-virtual {v1}, Landroid/view/View;->requestFocusFromTouch()Z

    :done
    return-void
.end method
""".strip(),
    },
    {
        "label": "gvactivity-onresume-bypass-forceclose",
        "file": "com/gamevil/lib/GvActivity.smali",
        "signature": ".method protected onResume()V",
        "body": """
.method protected onResume()V
    .registers 3

    .prologue
    invoke-super {p0}, Landroid/app/Activity;->onResume()V

    const/4 v0, 0x0

    sput-boolean v0, Lcom/gamevil/lib/GvActivity;->isForceToClose:Z

    sput-boolean v0, Lcom/gamevil/lib/GvActivity;->mPause:Z

    const/4 v1, 0x1

    iput-boolean v1, p0, Lcom/gamevil/lib/GvActivity;->isFirst:Z

    sput-boolean v1, Lcom/gamevil/lib/GvActivity;->pend:Z

    invoke-virtual {p0}, Lcom/gamevil/lib/GvActivity;->onGameResume()V

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvactivity-do-jellybeen-noop",
        "file": "com/gamevil/lib/GvActivity.smali",
        "signature": ".method public doJellyBeen()V",
        "body": """
.method public doJellyBeen()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvactivity-do-torchwood-noop",
        "file": "com/gamevil/lib/GvActivity.smali",
        "signature": ".method public doTorchwood()V",
        "body": """
.method public doTorchwood()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvdrm-start-launcher-explicit",
        "file": "com/gamevil/lib/GvDrmActivity.smali",
        "signature": ".method private startLauncherActivity()V",
        "body": """
.method private startLauncherActivity()V
    .registers 4

    new-instance v0, Landroid/content/Intent;

    invoke-direct {v0}, Landroid/content/Intent;-><init>()V

    const-string v1, "com.gamevil.ArelWars2.global"

    const-string v2, "com.gamevil.ArelWars2.global.ArelWars2Launcher"

    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;

    const-string v1, "profileBundle"

    invoke-static {}, Lcom/gamevil/lib/profile/GvProfileData;->getProfileBundle()Landroid/os/Bundle;

    move-result-object v2

    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Bundle;)Landroid/content/Intent;

    invoke-virtual {p0, v0}, Lcom/gamevil/lib/GvDrmActivity;->startActivity(Landroid/content/Intent;)V

    invoke-virtual {p0}, Lcom/gamevil/lib/GvDrmActivity;->finish()V

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvprofile-show-net-error-noop",
        "file": "com/gamevil/lib/profile/GvProfileSender.smali",
        "signature": ".method public showNetError1()V",
        "body": """
.method public showNetError1()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-show-banner-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static showNewsBanner(I)V",
        "body": """
.method public static showNewsBanner(I)V
    .registers 1
    .param p0, "_addressId"    # I

    .prologue
    return-void
.end method
""".strip(),
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=True,
    )


def ensure_disassembly(classes_dex: Path, smali_root: Path, force: bool) -> None:
    if smali_root.exists() and not force:
        return
    if smali_root.exists():
        shutil.rmtree(smali_root)
    smali_root.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            JAVA,
            "-cp",
            tooling_classpath(),
            "org.jf.baksmali.Main",
            "disassemble",
            str(classes_dex),
            "-o",
            str(smali_root),
        ]
    )


def replace_method(text: str, signature: str, body: str) -> tuple[str, bool]:
    pattern = re.compile(rf"^{re.escape(signature)}\n.*?^\.end method$", re.MULTILINE | re.DOTALL)
    replacement = body.replace("\n", "\n")
    new_text, count = pattern.subn(replacement, text, count=1)
    return new_text, count == 1


def patch_smali_tree(smali_root: Path) -> list[dict[str, str]]:
    applied: list[dict[str, str]] = []
    for patch in PATCHES:
        target = smali_root / patch["file"]
        text = target.read_text(encoding="utf-8")
        new_text, ok = replace_method(text, patch["signature"], patch["body"])
        if not ok:
            raise RuntimeError(f"Failed to patch {patch['label']} in {target}")
        target.write_text(new_text, encoding="utf-8", newline="\n")
        applied.append({"label": patch["label"], "file": str(target)})
    return applied


def find_symbol_value(binary: Path, symbol: str) -> int:
    result = run([str(LLVM_READELF), "-Ws", str(binary)])
    pattern = re.compile(rf"^\s*\d+:\s*([0-9a-fA-F]+)\s+\d+\s+FUNC\s+GLOBAL\s+DEFAULT\s+\d+\s+{re.escape(symbol)}\s*$")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            return int(match.group(1), 16)
    raise RuntimeError(f"Symbol not found in {binary}: {symbol}")


def encode_thumb_b_w(src_addr: int, dst_addr: int) -> bytes:
    delta = dst_addr - (src_addr + 4)
    if delta % 2 != 0:
        raise RuntimeError(f"Unaligned Thumb branch from 0x{src_addr:x} to 0x{dst_addr:x}")
    imm25 = (delta >> 1) & ((1 << 24) - 1)
    sign = (imm25 >> 23) & 0x1
    i1 = (imm25 >> 22) & 0x1
    i2 = (imm25 >> 21) & 0x1
    imm10 = (imm25 >> 11) & 0x3FF
    imm11 = imm25 & 0x7FF
    j1 = ((~i1) & 0x1) ^ sign
    j2 = ((~i2) & 0x1) ^ sign
    first_halfword = (0b11110 << 11) | (sign << 10) | imm10
    second_halfword = (0b10 << 14) | (j1 << 13) | (1 << 12) | (j2 << 11) | imm11
    return first_halfword.to_bytes(2, "little") + second_halfword.to_bytes(2, "little")


def encode_thumb_bl(src_addr: int, dst_addr: int) -> bytes:
    delta = dst_addr - (src_addr + 4)
    if delta % 2 != 0:
        raise RuntimeError(f"Unaligned Thumb BL from 0x{src_addr:x} to 0x{dst_addr:x}")
    imm25 = (delta >> 1) & ((1 << 24) - 1)
    sign = (imm25 >> 23) & 0x1
    i1 = (imm25 >> 22) & 0x1
    i2 = (imm25 >> 21) & 0x1
    imm10 = (imm25 >> 11) & 0x3FF
    imm11 = imm25 & 0x7FF
    j1 = ((~i1) & 0x1) ^ sign
    j2 = ((~i2) & 0x1) ^ sign
    first_halfword = (0b11110 << 11) | (sign << 10) | imm10
    second_halfword = (0b11 << 14) | (j1 << 13) | (1 << 12) | (j2 << 11) | imm11
    return first_halfword.to_bytes(2, "little") + second_halfword.to_bytes(2, "little")


def patch_native_branch_to_symbol(
    lib_path: Path,
    *,
    label: str,
    symbol: str,
    target_symbol: str,
    expected: bytes,
) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, symbol)
    target_symbol_value = find_symbol_value(lib_path, target_symbol)
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    patched = encode_thumb_b_w(symbol_value & ~1, target_symbol_value & ~1)
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} "
            f"(expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": label,
        "file": str(lib_path),
        "symbol": symbol,
        "targetSymbol": target_symbol,
        "symbolValue": symbol_value,
        "targetSymbolValue": target_symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_socket_fail_open(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "MC_netSocketConnect")
    file_offset = (symbol_value & ~1) + 0x6E
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x19\xdb"
    patched = b"\x00\xbf"
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-socket-fail-open",
        "file": str(lib_path),
        "symbol": "MC_netSocketConnect",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_socket_write_stub(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "MC_netSocketWrite")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\x2d\xe9\xf0\x47"
    patched = b"\x10\x46\x70\x47"  # mov r0, r2 ; bx lr
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-socket-write-stub",
        "file": str(lib_path),
        "symbol": "MC_netSocketWrite",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_sendcb_negative_ignore(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN10CGsNetCore6SendCBEllPv")
    file_offset = (symbol_value & ~1) + 0x8
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x0a\xdb"
    patched = b"\x09\xdb"  # blt -> just return, skip Exception(-93)
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-sendcb-negative-ignore",
        "file": str(lib_path),
        "symbol": "_ZN10CGsNetCore6SendCBEllPv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_onconnectdone_skip_bootstrap_send(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet13OnConnectDoneEv")
    file_offset = (symbol_value & ~1) + 0x22
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\xc5\x21"
    patched = b"\x02\xe0"  # b -> epilogue, skip default send(0x314)
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-onconnectdone-skip-bootstrap-send",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet13OnConnectDoneEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_setdrawconnecting_always_off(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet17SetDrawConnectingEbb")
    file_offset = (symbol_value & ~1) + 0x4
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\x0d\x1c\x16\x1c\x00\x29"
    patched = b"\x00\x25\x00\x26\x00\x21"  # r5=0, r6=0, r1=0 => always hide / clear flags
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-setdrawconnecting-always-off",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet17SetDrawConnectingEbb",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_connect_disable_input_lock(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet7ConnectE15EnumNetLinkType")
    file_offset = (symbol_value & ~1) + 0x28
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x01\x21"
    patched = b"\x00\x21"  # movs r1, #0 before CPdSharing::SetInputLock
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-connect-disable-input-lock",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet7ConnectE15EnumNetLinkType",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_connect_shortcircuit_done(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet7ConnectE15EnumNetLinkType")
    file_offset = (symbol_value & ~1) + 0x72
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xcb\xf0\x13\xf9"  # bl CGsNetCore::Connect
    patched = b"\xff\xf7\x93\xff"  # bl OnConnectDone
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-connect-shortcircuit-done",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet7ConnectE15EnumNetLinkType",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_bootstrap_force_receive23(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu17UpdateMainMenuAniEv")
    patch_addr = (symbol_value & ~1) + 0x10A
    resume_addr = (symbol_value & ~1) + 0x9A
    file_offset = patch_addr
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 20])
    expected = bytes.fromhex("0e4beb581868835d002bc1d11721e8f7c0fdbde7")
    patched = (
        b"\x01\x21\x84\x23\x5b\x00\xe1\x54"
        + encode_thumb_b_w(patch_addr + 8, resume_addr)
        + b"\x00\xbf\x00\xbf\x00\xbf\x00\xbf"
    )
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} "
            f"(expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 20] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-bootstrap-force-receive23",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu17UpdateMainMenuAniEv",
        "targetAddr": resume_addr,
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_handlecletevent_touch_exitintro(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "handleCletEvent")
    exit_symbol = find_symbol_value(lib_path, "_ZN13CPdStateIntro9ExitIntroEv")
    patch_addr = (symbol_value & ~1) + 0x70
    file_offset = patch_addr
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 8])
    expected = bytes.fromhex("784400681a680023")
    patched = encode_thumb_bl(patch_addr, exit_symbol & ~1) + b"\xdd\xe7" + b"\x00\xbf"
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} "
            f"(expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 8] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-handlecletevent-touch-exitintro",
        "file": str(lib_path),
        "symbol": "handleCletEvent",
        "targetSymbol": "_ZN13CPdStateIntro9ExitIntroEv",
        "symbolValue": symbol_value,
        "targetSymbolValue": exit_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_onconnecterror_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet14OnConnectErrorEi")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x47\x46"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-onconnecterror-noop",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet14OnConnectErrorEi",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_onerror_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet7OnErrorEii")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x47\x46"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-onerror-noop",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet7OnErrorEii",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_intro_touch_exit(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN13CPdStateIntro14OnPointerPressEP12GxPointerPos")
    exit_symbol = find_symbol_value(lib_path, "_ZN13CPdStateIntro9ExitIntroEv")
    patch_addr = (symbol_value & ~1) + 0x30
    file_offset = patch_addr
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\x04\x23\x83\x64\x30\xbd"
    patched = encode_thumb_bl(patch_addr, exit_symbol & ~1) + b"\x30\xbd"
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-intro-touch-exit",
        "file": str(lib_path),
        "symbol": "_ZN13CPdStateIntro14OnPointerPressEP12GxPointerPos",
        "targetSymbol": "_ZN13CPdStateIntro9ExitIntroEv",
        "symbolValue": symbol_value,
        "targetSymbolValue": exit_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_pointerpress_direct_newgame(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu14OnPointerPressEP12GxPointerPos")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\x10\xb5\x0c\x4b"
    patched = b"\x00\xf0\xd0\xbc"  # b.w StartNewGame
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-pointerpress-direct-newgame",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu14OnPointerPressEP12GxPointerPos",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_ignore_touch_block(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu14UpdateMainMenuEv")
    file_offset = (symbol_value & ~1) + 0x40
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x54\xd1"  # bne -> return when touch-block flag (this+0x10b) is set
    patched = b"\x00\xbf"  # nop, allow title-shell update path to continue
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-ignore-touch-block",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu14UpdateMainMenuEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_ignore_bootstrap_gate(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu14UpdateMainMenuEv")
    file_offset = (symbol_value & ~1) + 0x38
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x58\xd0"  # beq -> return when bootstrap-ready flag (this+0x10a) is still 0
    patched = b"\x00\xbf"  # nop, allow main-menu control updates even when bootstrap flag never flips
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-ignore-bootstrap-gate",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu14UpdateMainMenuEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_onpointerpress_openmenu0(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu14OnPointerPressEP12GxPointerPos")
    openmenu_symbol = find_symbol_value(lib_path, "_ZN12CPdStateMenu8OpenMenuEi")
    file_offset = symbol_value & ~1
    patch_addr = symbol_value & ~1
    branch_addr = patch_addr + 2
    branch = encode_thumb_b_w(branch_addr, openmenu_symbol & ~1)
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\x10\xb5\x0c\x4b\x0a\x88"
    patched = b"\x00\x21" + branch  # movs r1, #0 ; b.w OpenMenu
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-onpointerpress-openmenu0",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu14OnPointerPressEP12GxPointerPos",
        "targetSymbol": "_ZN12CPdStateMenu8OpenMenuEi",
        "symbolValue": symbol_value,
        "targetSymbolValue": openmenu_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchcontinue_direct_newgame(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu13TouchContinueEv")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x5f\x46"
    patched = b"\xfd\xf7\x56\xbc"  # b.w StartNewGame
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchcontinue-direct-newgame",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu13TouchContinueEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchcontinue_any_touch_select_slot0(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu13TouchContinueEv")
    file_offset = (symbol_value & ~1) + 0x6A
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x37\xd0"  # beq -> ignore touch when IsSelectSaveSlot misses
    patched = b"\x00\xbf"  # nop -> keep default slot index 0 from StartContinue on any touch
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchcontinue-any-touch-select-slot0",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu13TouchContinueEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_startnewgame_default_slot1(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu12StartNewGameEv")
    file_offset = (symbol_value & ~1) + 0x8
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = bytes.fromhex("0564")
    patched = bytes.fromhex("0664")
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-startnewgame-default-slot1",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu12StartNewGameEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_callbackpop_emptyslot_force_state5(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu21CallbackPop_EmptySlotEPKvs")
    file_offset = (symbol_value & ~1) + 0x18
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = bytes.fromhex("04d0")
    patched = bytes.fromhex("00bf")
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-callbackpop-emptyslot-force-state5",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu21CallbackPop_EmptySlotEPKvs",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_updatenewgame_auto_accept_empty_slot(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu13UpdateNewGameEv")
    callback_symbol = find_symbol_value(lib_path, "_ZN12CPdStateMenu21CallbackPop_EmptySlotEPKvs")
    patch_addr = (symbol_value & ~1) + 0x10
    branch_addr = patch_addr + 0x4
    file_offset = patch_addr
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 18])
    expected = bytes.fromhex("000c022801d0002010bd6368a060e360f9e7")
    patched = (
        bytes.fromhex("201c0121")
        + encode_thumb_bl(branch_addr, callback_symbol & ~1)
        + bytes.fromhex("002010bd00bf00bf00bf")
    )
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 18] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-updatenewgame-auto-accept-empty-slot",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu13UpdateNewGameEv",
        "targetSymbol": "_ZN12CPdStateMenu21CallbackPop_EmptySlotEPKvs",
        "symbolValue": symbol_value,
        "targetSymbolValue": callback_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchcontinue_openmenu0(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu13TouchContinueEv")
    openmenu_symbol = find_symbol_value(lib_path, "_ZN12CPdStateMenu8OpenMenuEi")
    file_offset = symbol_value & ~1
    patch_addr = symbol_value & ~1
    branch_addr = patch_addr + 2
    branch = encode_thumb_b_w(branch_addr, openmenu_symbol & ~1)
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\xf0\xb5\x5f\x46\x56\x46"
    patched = b"\x00\x21" + branch  # movs r1, #0 ; b.w OpenMenu
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchcontinue-openmenu0",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu13TouchContinueEv",
        "targetSymbol": "_ZN12CPdStateMenu8OpenMenuEi",
        "symbolValue": symbol_value,
        "targetSymbolValue": openmenu_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchmainmenu_openmenu0(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu13TouchMainMenuEv")
    openmenu_symbol = find_symbol_value(lib_path, "_ZN12CPdStateMenu8OpenMenuEi")
    file_offset = symbol_value & ~1
    patch_addr = symbol_value & ~1
    branch_addr = patch_addr + 2
    branch = encode_thumb_b_w(branch_addr, openmenu_symbol & ~1)
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\xf0\xb5\x5f\x46\x56\x46"
    patched = b"\x00\x21" + branch  # movs r1, #0 ; b.w OpenMenu
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchmainmenu-openmenu0",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu13TouchMainMenuEv",
        "targetSymbol": "_ZN12CPdStateMenu8OpenMenuEi",
        "symbolValue": symbol_value,
        "targetSymbolValue": openmenu_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_updatestylenotice_direct_newgame(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-updatestylenotice-direct-newgame",
        symbol="_ZN12CPdStateMenu17UpdateStyleNoticeEv",
        target_symbol="_ZN12CPdStateMenu12StartNewGameEv",
        expected=b"\x10\xb5\xd8\x23",
    )


def patch_native_updatestylenotice_openmenu0(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu17UpdateStyleNoticeEv")
    openmenu_symbol = find_symbol_value(lib_path, "_ZN12CPdStateMenu8OpenMenuEi")
    file_offset = symbol_value & ~1
    patch_addr = symbol_value & ~1
    branch_addr = patch_addr + 2
    branch = encode_thumb_b_w(branch_addr, openmenu_symbol & ~1)
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\x10\xb5\xd8\x23\x04\x1c"
    patched = b"\x00\x21" + branch  # movs r1, #0 ; b.w OpenMenu
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-updatestylenotice-openmenu0",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu17UpdateStyleNoticeEv",
        "targetSymbol": "_ZN12CPdStateMenu8OpenMenuEi",
        "symbolValue": symbol_value,
        "targetSymbolValue": openmenu_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_updatepreloading_direct_newgame(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-updatepreloading-direct-newgame",
        symbol="_ZN12CPdStateMenu16UpdatePreLoadingEv",
        target_symbol="_ZN12CPdStateMenu12StartNewGameEv",
        expected=b"\x10\xb5\xc8\x23",
    )


def patch_native_exitintro_openmenu0(lib_path: Path) -> dict[str, str | int]:
    exit_symbol = find_symbol_value(lib_path, "_ZN13CPdStateIntro9ExitIntroEv")
    openmenu_symbol = find_symbol_value(lib_path, "_ZN13CPdStateIntro8OpenMenuEi")
    patch_addr = (exit_symbol & ~1) + 0x20
    file_offset = patch_addr
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\x70\x47\xc0\x46"  # bx lr ; mov r8, r8
    branch_addr = patch_addr + 2
    branch_pc = branch_addr + 4
    delta = (openmenu_symbol & ~1) - branch_pc
    if delta % 2 != 0:
        raise RuntimeError(f"Unaligned thumb branch from 0x{branch_addr:x} to 0x{(openmenu_symbol & ~1):x}")
    imm11 = delta // 2
    if not (-1024 <= imm11 <= 1023):
        raise RuntimeError(
            f"Thumb short branch out of range from 0x{branch_addr:x} to 0x{(openmenu_symbol & ~1):x} (delta {delta})"
        )
    branch = (0xE000 | (imm11 & 0x7FF)).to_bytes(2, "little")
    patched = b"\x00\x21" + branch  # movs r1, #0 ; b OpenMenu
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-exitintro-openmenu0",
        "file": str(lib_path),
        "symbol": "_ZN13CPdStateIntro9ExitIntroEv",
        "targetSymbol": "_ZN13CPdStateIntro8OpenMenuEi",
        "symbolValue": exit_symbol,
        "targetSymbolValue": openmenu_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_afterintro_skip_popup(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN13CPdStateIntro25CallbackScript_AfterIntroEPKvs")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x07\x23"  # movs r3, #7
    patched = b"\x06\x23"  # movs r3, #6 -> UpdateIntro case that calls ExitIntro
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-afterintro-skip-popup",
        "file": str(lib_path),
        "symbol": "_ZN13CPdStateIntro25CallbackScript_AfterIntroEPKvs",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_updateintro_exitintro(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-updateintro-exitintro",
        symbol="_ZN13CPdStateIntro11UpdateIntroEv",
        target_symbol="_ZN13CPdStateIntro9ExitIntroEv",
        expected=b"\xf0\xb5\x89\xb0",
    )


def patch_native_callbackpop_intro_force_exit(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN13CPdStateIntro17CallbackPop_IntroEPKvs")
    patch_addr = (symbol_value & ~1) + 0x18
    file_offset = patch_addr
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 8])
    expected = bytes.fromhex("99424bd0022949dc")
    patched = encode_thumb_b_w(patch_addr, 0x000CBA50) + b"\x00\xbf\x00\xbf"
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} "
            f"(expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 8] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-callbackpop-intro-force-exit",
        "file": str(lib_path),
        "symbol": "_ZN13CPdStateIntro17CallbackPop_IntroEPKvs",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_evappstart_boot_menu(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdApp10EvAppStartEv")
    base = symbol_value & ~1
    patch_specs = [
        (base + 0x378, b"\x03\x21", b"\x05\x21"),
        (base + 0x4D4, b"\x03\x22", b"\x05\x22"),
    ]
    data = bytearray(lib_path.read_bytes())
    patch_records: list[dict[str, str | int]] = []
    for patch_addr, expected, patched in patch_specs:
        original = bytes(data[patch_addr : patch_addr + len(expected)])
        if original not in (expected, patched):
            raise RuntimeError(
                f"Unexpected bytes at {lib_path} + 0x{patch_addr:x}: {original.hex()} "
                f"(expected {expected.hex()} or {patched.hex()})"
            )
        data[patch_addr : patch_addr + len(expected)] = patched
        patch_records.append(
            {
                "fileOffset": patch_addr,
                "original": original.hex(),
                "patched": patched.hex(),
            }
        )
    lib_path.write_bytes(data)
    return {
        "label": "native-evappstart-boot-menu",
        "file": str(lib_path),
        "symbol": "_ZN6CPdApp10EvAppStartEv",
        "symbolValue": symbol_value,
        "patches": patch_records,
    }


def patch_native_gamevillogo_force_menu_state2(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu17UpdateGamevilLogoEv")
    file_offset = (symbol_value & ~1) + 0x74
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x21\xd0"  # beq state-1 path
    patched = b"\x00\xbf"  # nop -> always fall through to state-2 path
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-gamevillogo-force-menu-state2",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu17UpdateGamevilLogoEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_gamevillogo_state2_to_state3(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu17UpdateGamevilLogoEv")
    file_offset = (symbol_value & ~1) + 0x76
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x02\x23"  # movs r3, #2
    patched = b"\x03\x23"  # movs r3, #3 -> let DoChangeState/OpenMenu take the StartNewGame path
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-gamevillogo-state2-to-state3",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu17UpdateGamevilLogoEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_updategamevillogo_openmenu0(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu17UpdateGamevilLogoEv")
    openmenu_symbol = find_symbol_value(lib_path, "_ZN12CPdStateMenu8OpenMenuEi")
    file_offset = symbol_value & ~1
    patch_addr = symbol_value & ~1
    branch_addr = patch_addr + 2
    branch = encode_thumb_b_w(branch_addr, openmenu_symbol & ~1)
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\x70\xb5\xb8\x23\xc3\x58"
    patched = b"\x00\x21" + branch  # movs r1, #0 ; b.w OpenMenu
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-updategamevillogo-openmenu0",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu17UpdateGamevilLogoEv",
        "targetSymbol": "_ZN12CPdStateMenu8OpenMenuEi",
        "symbolValue": symbol_value,
        "targetSymbolValue": openmenu_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchmainmenu_startnewgame(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-touchmainmenu-startnewgame",
        symbol="_ZN12CPdStateMenu13TouchMainMenuEv",
        target_symbol="_ZN12CPdStateMenu12StartNewGameEv",
        expected=b"\xf0\xb5\x5f\x46",
    )


def patch_native_touchmainmenu_openmenu3(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu13TouchMainMenuEv")
    openmenu_symbol = find_symbol_value(lib_path, "_ZN12CPdStateMenu8OpenMenuEi")
    file_offset = symbol_value & ~1
    branch_addr = file_offset + 2
    branch = encode_thumb_b_w(branch_addr, openmenu_symbol & ~1)
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\xf0\xb5\x5f\x46\x56\x46"
    patched = b"\x03\x21" + branch
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchmainmenu-openmenu3",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu13TouchMainMenuEv",
        "targetSymbol": "_ZN12CPdStateMenu8OpenMenuEi",
        "symbolValue": symbol_value,
        "targetSymbolValue": openmenu_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchnewgame_any_touch_select_slot0(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu12TouchNewGameEv")
    file_offset = (symbol_value & ~1) + 0x54
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x1e\xd0"  # beq -> skip selected-slot path when hit test misses
    patched = b"\x00\xbf"  # nop -> StartNewGame's default slot index 0 becomes active on any touch
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchnewgame-any-touch-select-slot0",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu12TouchNewGameEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchnewgame_force_state5(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu12TouchNewGameEv")
    file_offset = (symbol_value & ~1) + 0x7E
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x17\xd1"  # bne -> state 5 path only when global gate is already set
    patched = b"\x17\xe0"  # b -> always take the local state-5 path, skip CPdNet::Connect
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchnewgame-force-state5",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu12TouchNewGameEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchnewgame_skip_yes_popup(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu12TouchNewGameEv")
    file_offset = (symbol_value & ~1) + 0x106
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 26])
    expected = bytes.fromhex("104b4146e35818685df06dfde3595c21002218686423f1f7c2fa")
    patched = bytes.fromhex(
        "4046036940690121984700bf00bf00bf00bf00bf00bf00bf00bf"
    )
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 26] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchnewgame-skip-yes-popup",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu12TouchNewGameEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchselectrace_any_touch_default(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu15TouchSelectRaceEv")
    file_offset = (symbol_value & ~1) + 0x84
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x4a\xd0"  # beq -> ignore touch when IsSelectRace misses
    patched = b"\x00\xbf"  # nop -> accept any touch and continue with the current default race
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchselectrace-any-touch-default",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu15TouchSelectRaceEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchselectrace_skip_yes_popup(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu15TouchSelectRaceEv")
    file_offset = (symbol_value & ~1) + 0x100
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 28])
    expected = bytes.fromhex("1a4b5146e35818685ff02aff4246a3585c21002218686423f3f77efc")
    patched = bytes.fromhex(
        "5046036940690121984700bf00bf00bf00bf00bf00bf00bf00bf00bf"
    )
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 28] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchselectrace-skip-yes-popup",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu15TouchSelectRaceEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_slotopenpopup_any_touch_select_first_slot(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN14CSlotOpenPopup10TouchEventEP8TGXPOINT")
    click_symbol = find_symbol_value(lib_path, "_ZN10CUIControl5ClickEv")
    patch_addr = (symbol_value & ~1) + 0x10
    branch_click_addr = patch_addr + 0x6
    branch_return_addr = patch_addr + 0xA
    return_addr = (symbol_value & ~1) + 0xC2
    file_offset = patch_addr
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 14])
    expected = bytes.fromhex("89460a881420195e586b83b00328")
    patched = (
        bytes.fromhex("00233363f069")
        + encode_thumb_bl(branch_click_addr, click_symbol & ~1)
        + encode_thumb_b_w(branch_return_addr, return_addr)
    )
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 14] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-slotopenpopup-any-touch-select-first-slot",
        "file": str(lib_path),
        "symbol": "_ZN14CSlotOpenPopup10TouchEventEP8TGXPOINT",
        "targetSymbol": "_ZN10CUIControl5ClickEv",
        "symbolValue": symbol_value,
        "targetSymbolValue": click_symbol,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_onneterror_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu10OnNetErrorEii")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x4f\x46"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-onneterror-noop",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu10OnNetErrorEii",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_onnetreceive_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu12OnNetReceiveEi")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x9b\x4c"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-onnetreceive-noop",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu12OnNetReceiveEi",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_state_noop(lib_path: Path, label: str, symbol: str, expected: bytes) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, symbol)
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": label,
        "file": str(lib_path),
        "symbol": symbol,
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_game_onneterror_noop(lib_path: Path) -> dict[str, str | int]:
    return patch_native_state_noop(
        lib_path,
        "native-game-onneterror-noop",
        "_ZN12CPdStateGame10OnNetErrorEii",
        b"\xf0\xb5\x47\x46",
    )


def patch_native_game_onnetreceive_noop(lib_path: Path) -> dict[str, str | int]:
    return patch_native_state_noop(
        lib_path,
        "native-game-onnetreceive-noop",
        "_ZN12CPdStateGame12OnNetReceiveEi",
        b"\xf0\xb5\x4f\x46",
    )


def patch_native_worldmap_onneterror_noop(lib_path: Path) -> dict[str, str | int]:
    return patch_native_state_noop(
        lib_path,
        "native-worldmap-onneterror-noop",
        "_ZN16CPdStateWorldmap10OnNetErrorEii",
        b"\xf0\xb5\x5f\x46",
    )


def patch_native_worldmap_onnetreceive_noop(lib_path: Path) -> dict[str, str | int]:
    return patch_native_state_noop(
        lib_path,
        "native-worldmap-onnetreceive-noop",
        "_ZN16CPdStateWorldmap12OnNetReceiveEi",
        b"\xf0\xb5\x5f\x46",
    )


def patch_native_worldmap_onpointerpress_ignore_touch_gate(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN16CPdStateWorldmap14OnPointerPressEP12GxPointerPos")
    file_offset = (symbol_value & ~1) + 0x1C
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x2b\xd1"
    patched = b"\x00\xbf"
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-onpointerpress-ignore-touch-gate",
        "file": str(lib_path),
        "symbol": "_ZN16CPdStateWorldmap14OnPointerPressEP12GxPointerPos",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_worldmap_release_expand_tap_slop(lib_path: Path) -> dict[str, str | int]:
    data = bytearray(lib_path.read_bytes())
    first_offset = 0x10A366
    second_offset = 0x10A37A
    expected = b"\x09\x2b"  # cmp r3, #9
    patched = b"\x20\x2b"   # cmp r3, #32
    originals = [
        bytes(data[first_offset : first_offset + 2]),
        bytes(data[second_offset : second_offset + 2]),
    ]
    for index, original in enumerate(originals):
        if original not in (expected, patched):
            raise RuntimeError(
                f"Unexpected bytes at {lib_path} + 0x{[first_offset, second_offset][index]:x}: "
                f"{original.hex()} (expected {expected.hex()} or {patched.hex()})"
            )
    data[first_offset : first_offset + 2] = patched
    data[second_offset : second_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-release-expand-tap-slop",
        "file": str(lib_path),
        "fileOffsets": [first_offset, second_offset],
        "original": [item.hex() for item in originals],
        "patched": patched.hex(),
    }


def patch_native_worldmap_touchworldmapmenu_ignore_global_gate(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN16CPdStateWorldmap22TouchInputWorldMapMenuEv")
    file_offset = (symbol_value & ~1) + 0x10
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x11\xd1"  # bne -> early return when global 0x1068 gate is set
    patched = b"\x00\xbf"   # nop -> let the official worldmap-menu handler continue
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-touchworldmapmenu-ignore-global-gate",
        "file": str(lib_path),
        "symbol": "_ZN16CPdStateWorldmap22TouchInputWorldMapMenuEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_worldmap_touchstageselect_ignore_global_gate(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN16CPdStateWorldmap21TouchInputStageSelectEv")
    file_offset = (symbol_value & ~1) + 0x20
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x00\xd0"  # beq continue; otherwise fall into return branch
    patched = b"\x00\xe0"   # unconditional branch to the same continue target
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-touchstageselect-ignore-global-gate",
        "file": str(lib_path),
        "symbol": "_ZN16CPdStateWorldmap21TouchInputStageSelectEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_worldmap_touchworldframe_ignore_global_gate(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN16CPdStateWorldmap20TouchInputWorldFrameEii")
    file_offset = (symbol_value & ~1) + 0x12
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x06\xd1"  # bne -> early return when global 0x1068 gate is set
    patched = b"\x00\xbf"   # nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-touchworldframe-ignore-global-gate",
        "file": str(lib_path),
        "symbol": "_ZN16CPdStateWorldmap20TouchInputWorldFrameEii",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_worldmap_touchworldframe_ignore_popup_gate(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN16CPdStateWorldmap20TouchInputWorldFrameEii")
    file_offset = (symbol_value & ~1) + 0x20
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x01\xdb"  # blt continue; otherwise falls into early return
    patched = b"\x01\xe0"   # unconditional branch to the same continue target
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-touchworldframe-ignore-popup-gate",
        "file": str(lib_path),
        "symbol": "_ZN16CPdStateWorldmap20TouchInputWorldFrameEii",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_worldmap_gamevillive_popup_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN16CPdStateWorldmap28CallbackPop_GameVilLiveLoginEPKvs")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\x10\xb5\x01\x29"
    patched = b"\x00\x20\x70\x47"  # movs r0, #0 ; bx lr
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-gamevillive-popup-noop",
        "file": str(lib_path),
        "symbol": "_ZN16CPdStateWorldmap28CallbackPop_GameVilLiveLoginEPKvs",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_worldmap_updatemenu_auto_local_branch(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv")
    file_offset = (symbol_value & ~1) + 0x106
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = bytes.fromhex("00d1")  # bne -> skip the existing local worldmap branch when no icon click is reported
    patched = bytes.fromhex("00bf")   # nop -> always fall through to the existing branch at +0x108
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-worldmap-updatemenu-auto-local-branch",
        "file": str(lib_path),
        "symbol": "_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_worldmap_touchworldmapmenu_create_stage_select(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-worldmap-touchworldmapmenu-create-stage-select",
        symbol="_ZN16CPdStateWorldmap22TouchInputWorldMapMenuEv",
        target_symbol="_ZN16CPdStateWorldmap17CreateStageSelectEv",
        expected=b"\x10\xb5\x0e\x4b",
    )


def patch_native_worldmap_select_worldmapmain_create_stage_select(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-worldmap-select-worldmapmain-create-stage-select",
        symbol="_ZN16CPdStateWorldmap19Select_WorldMapMainEv",
        target_symbol="_ZN16CPdStateWorldmap17CreateStageSelectEv",
        expected=b"\x70\xb5\x00\x23",
    )


def patch_native_worldmap_touchgamestart_create_stage_select(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-worldmap-touchgamestart-create-stage-select",
        symbol="_ZN16CPdStateWorldmap19TouchInputGamestartEv",
        target_symbol="_ZN16CPdStateWorldmap17CreateStageSelectEv",
        expected=b"\xf0\xb5\x5f\x46",
    )


def patch_native_worldmap_touchstageselect_create_stage_info(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-worldmap-touchstageselect-create-stage-info",
        symbol="_ZN16CPdStateWorldmap21TouchInputStageSelectEv",
        target_symbol="_ZN16CPdStateWorldmap15CreateStageInfoEv",
        expected=b"\xf0\xb5\x5f\x46",
    )


def patch_native_worldmap_touchstageinfo_create_gamestart(lib_path: Path) -> dict[str, str | int]:
    return patch_native_branch_to_symbol(
        lib_path,
        label="native-worldmap-touchstageinfo-create-gamestart",
        symbol="_ZN16CPdStateWorldmap19TouchInputStageInfoEv",
        target_symbol="_ZN16CPdStateWorldmap15CreateGameStartEv",
        expected=b"\xf0\xb5\x5f\x46",
    )


def patch_native_openurl_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "openUrl")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf8\xb5\x05\x1c"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-openurl-noop",
        "file": str(lib_path),
        "symbol": "openUrl",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_libs(unpacked_dir: Path) -> list[dict[str, str | int]]:
    applied: list[dict[str, str | int]] = []
    for rel in [
        Path("lib/armeabi/libgameDSO.so"),
        Path("lib/armeabi-v7a/libgameDSO.so"),
    ]:
        lib_path = unpacked_dir / rel
        if lib_path.exists():
            applied.append(patch_native_socket_fail_open(lib_path))
            applied.append(patch_native_socket_write_stub(lib_path))
            applied.append(patch_native_sendcb_negative_ignore(lib_path))
            applied.append(patch_native_onconnectdone_skip_bootstrap_send(lib_path))
            applied.append(patch_native_setdrawconnecting_always_off(lib_path))
            applied.append(patch_native_connect_disable_input_lock(lib_path))
            applied.append(patch_native_connect_shortcircuit_done(lib_path))
            applied.append(patch_native_onconnecterror_noop(lib_path))
            applied.append(patch_native_onerror_noop(lib_path))
            applied.append(patch_native_intro_touch_exit(lib_path))
            applied.append(patch_native_exitintro_openmenu0(lib_path))
            applied.append(patch_native_afterintro_skip_popup(lib_path))
            applied.append(patch_native_callbackpop_intro_force_exit(lib_path))
            applied.append(patch_native_gamevillogo_force_menu_state2(lib_path))
            applied.append(patch_native_gamevillogo_state2_to_state3(lib_path))
            applied.append(patch_native_menu_bootstrap_force_receive23(lib_path))
            applied.append(patch_native_menu_ignore_bootstrap_gate(lib_path))
            applied.append(patch_native_menu_ignore_touch_block(lib_path))
            applied.append(patch_native_startnewgame_default_slot1(lib_path))
            applied.append(patch_native_callbackpop_emptyslot_force_state5(lib_path))
            applied.append(patch_native_updatenewgame_auto_accept_empty_slot(lib_path))
            applied.append(patch_native_touchcontinue_any_touch_select_slot0(lib_path))
            applied.append(patch_native_touchselectrace_any_touch_default(lib_path))
            applied.append(patch_native_touchselectrace_skip_yes_popup(lib_path))
            applied.append(patch_native_slotopenpopup_any_touch_select_first_slot(lib_path))
            applied.append(patch_native_menu_onneterror_noop(lib_path))
            applied.append(patch_native_game_onneterror_noop(lib_path))
            applied.append(patch_native_game_onnetreceive_noop(lib_path))
            applied.append(patch_native_worldmap_gamevillive_popup_noop(lib_path))
            # Debug-only worldmap input reopening:
            # keep official worldmap handlers intact, but ignore stale global gates
            # that currently suppress pointer latching and world-frame hit-testing.
            applied.append(patch_native_worldmap_onpointerpress_ignore_touch_gate(lib_path))
            applied.append(patch_native_worldmap_release_expand_tap_slop(lib_path))
            applied.append(patch_native_worldmap_touchworldmapmenu_ignore_global_gate(lib_path))
            applied.append(patch_native_worldmap_touchstageselect_ignore_global_gate(lib_path))
            applied.append(patch_native_worldmap_touchworldframe_ignore_global_gate(lib_path))
            applied.append(patch_native_worldmap_touchworldframe_ignore_popup_gate(lib_path))
            # Do not force UpdateWorldMapMenu through the local branch.
            # Static trace shows that path sets both 0x379c and 0x362c to 1,
            # which are the same worldmap gate bytes consumed by touch handlers.
            # Keep worldmap OnNetError/OnNetReceive intact for now.
            # They appear to participate in state cleanup for 0x362c/0x379c/0x36f8.
            # The remaining blocker is an input/state gate, not missing scene creation.
            applied.append(patch_native_openurl_noop(lib_path))
    return applied


def assemble_smali(smali_root: Path, output_dex: Path) -> None:
    output_dex.parent.mkdir(parents=True, exist_ok=True)
    if output_dex.exists():
        output_dex.unlink()
    run([JAVA, "-cp", tooling_classpath(), "org.jf.smali.Main", "assemble", "-o", str(output_dex), str(smali_root)])


def unpack_apk(apk: Path, unpacked_dir: Path) -> None:
    if unpacked_dir.exists():
        shutil.rmtree(unpacked_dir)
    unpacked_dir.mkdir(parents=True)
    with zipfile.ZipFile(apk) as zf:
        zf.extractall(unpacked_dir)


def read_compression_map(apk: Path) -> dict[str, int]:
    with zipfile.ZipFile(apk) as zf:
        return {info.filename: info.compress_type for info in zf.infolist()}


def repack_apk(unpacked_dir: Path, unsigned_apk: Path, compression_map: dict[str, int]) -> None:
    if unsigned_apk.exists():
        unsigned_apk.unlink()
    unsigned_apk.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(unsigned_apk, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(unpacked_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(unpacked_dir).as_posix()
            if rel.startswith("META-INF/"):
                continue
            zf.write(path, rel, compress_type=compression_map.get(rel, zipfile.ZIP_DEFLATED))


def align_and_sign(unsigned_apk: Path, aligned_apk: Path, signed_apk: Path) -> None:
    if aligned_apk.exists():
        aligned_apk.unlink()
    if signed_apk.exists():
        signed_apk.unlink()
    run([str(ZIPALIGN), "-f", "4", str(unsigned_apk), str(aligned_apk)])
    shutil.copy2(aligned_apk, signed_apk)
    run(
        [
            str(APKSIGNER),
            "sign",
            "--ks",
            str(DEBUG_KEYSTORE),
            "--ks-key-alias",
            "androiddebugkey",
            "--ks-pass",
            "pass:android",
            "--key-pass",
            "pass:android",
            str(signed_apk),
        ]
    )


def install_apk(device: str, apk: Path) -> subprocess.CompletedProcess[str]:
    try:
        return run(["adb", "-s", device, "install", "-r", str(apk)])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "") + (exc.stdout or "")
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in stderr or "INSTALL_FAILED_VERSION_DOWNGRADE" in stderr:
            run(["adb", "-s", device, "uninstall", "com.gamevil.ArelWars2.global"])
            return run(["adb", "-s", device, "install", "-r", str(apk)])
        raise


def mirror_sound_bank(device: str, unpacked_dir: Path) -> list[dict[str, str]]:
    sound_dir = unpacked_dir / "assets" / "sound"
    if not sound_dir.exists():
        return []
    run(["adb", "-s", device, "shell", "mkdir", "-p", "/sdcard/gamevil/zn4"])
    mirrored: list[dict[str, str]] = []
    for ogg_path in sorted(sound_dir.glob("*.ogg")):
        stem = ogg_path.stem
        if not stem.isdigit():
            continue
        remote = f"/sdcard/gamevil/zn4/s{int(stem):03d}.ogg"
        run(["adb", "-s", device, "push", str(ogg_path), remote])
        mirrored.append({"source": str(ogg_path), "remote": remote})
    return mirrored


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a test-only offline-hook APK for Arel Wars 2.")
    parser.add_argument("--apk", type=Path, default=APK_PATH)
    parser.add_argument("--device", default="emulator-5554")
    parser.add_argument("--force-disassembly", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    if not args.apk.exists():
        raise SystemExit(f"APK not found: {args.apk}")
    ensure_tooling()
    for path in [ZIPALIGN, APKSIGNER, DEBUG_KEYSTORE, LLVM_READELF, *[TOOLING_DIR / name for name in TOOLING_DOWNLOADS]]:
        if not Path(path).exists():
            raise SystemExit(f"Required tool missing: {path}")

    unpacked = BUILD_DIR / "unpacked"
    classes_dex = BUILD_DIR / "classes.dex"
    smali_cache = DEXDUMP_DIR / "smali"
    patched_smali = BUILD_DIR / "smali_patched"
    unsigned_apk = NATIVE_TMP / "arel_wars_2-offline-hook-unsigned.apk"
    aligned_apk = NATIVE_TMP / "arel_wars_2-offline-hook-aligned.apk"
    signed_apk = NATIVE_TMP / "arel_wars_2-offline-hook-signed.apk"

    unpack_apk(args.apk, unpacked)
    shutil.copy2(unpacked / "classes.dex", classes_dex)
    ensure_disassembly(classes_dex, smali_cache, args.force_disassembly)

    if patched_smali.exists():
        shutil.rmtree(patched_smali)
    shutil.copytree(smali_cache, patched_smali)
    applied = patch_smali_tree(patched_smali)

    rebuilt_dex = BUILD_DIR / "classes.patched.dex"
    assemble_smali(patched_smali, rebuilt_dex)
    shutil.copy2(rebuilt_dex, unpacked / "classes.dex")
    native_applied = patch_native_libs(unpacked)

    repack_apk(unpacked, unsigned_apk, read_compression_map(args.apk))
    align_and_sign(unsigned_apk, aligned_apk, signed_apk)

    install_result = None
    mirrored_sound_bank: list[dict[str, str]] = []
    if args.install:
        install_result = install_apk(args.device, signed_apk)
        mirrored_sound_bank = mirror_sound_bank(args.device, unpacked)

    report = {
        "sourceApk": str(args.apk),
        "sourceApkSha256": sha256(args.apk),
        "signedApk": str(signed_apk),
        "signedApkSha256": sha256(signed_apk),
        "patches": [*applied, *native_applied],
        "install": {
            "requested": args.install,
            "device": args.device,
            "stdout": install_result.stdout if install_result else "",
            "stderr": install_result.stderr if install_result else "",
        },
        "mirroredSoundBank": mirrored_sound_bank,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
