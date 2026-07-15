[app]

# App info
title = Audio Booster
package.name = audiobooster
package.domain = com.audiobooster
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0

# Requirements (minimal, avoid problematic packages)
requirements = python3,
    kivy==2.3.0,
    numpy,
    pillow

# Android config
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET,MANAGE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

# Interface
orientation = portrait
fullscreen = 0

# Icon and splash
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png

# Build
android.release_artifact = apk

# Log level
log_level = 2

[buildozer]
warn_on_root = 0
