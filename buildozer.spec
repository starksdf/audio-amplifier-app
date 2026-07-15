[app]

# App 信息
title = Audio Booster
package.name = audiobooster
package.domain = com.audiobooster
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

# 依赖
requirements = python3,
    kivy==2.3.0,
    pydub,
    numpy,
    scipy,
    soundfile,
    cffi,
    plyer

# Android 配置
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

# 界面
orientation = portrait
fullscreen = 0

# 图标和启动画面
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png

# 构建
android.release_artifact = apk
# android.debug_artifact = aab  # 如果要 Play Store 用 AAB

# 包含 ffmpeg（pydub 依赖）
android.add_libs_arm64-v8a = libs/arm64-v8a/*
android.add_libs_armeabi-v7a = libs/armeabi-v7a/*

# 日志级别
log_level = 2

[buildozer]
warn_on_root = 0
