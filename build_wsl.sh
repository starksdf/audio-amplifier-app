#!/bin/bash
# WSL一键构建脚本
# 用法: bash build_wsl.sh

set -e

echo "=========================================="
echo "  Audio Booster - APK Builder"
echo "=========================================="

# 检查是否在WSL
if ! grep -qi microsoft /proc/version 2>/dev/null; then
    echo "[WARN] Not running in WSL, some features may not work"
fi

# 安装依赖
echo "[1/4] Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev

# 安装buildozer
echo "[2/4] Installing buildozer..."
pip3 install --user buildozer cython
export PATH="$HOME/.local/bin:$PATH"

# 进入项目目录
cd "$(dirname "$0")"
echo "[3/4] Building APK (this takes 30-60 min first time)..."
buildozer android debug

# 完成
APK=$(find bin -name "*.apk" | head -1)
echo ""
echo "=========================================="
echo "  BUILD SUCCESS!"
echo "  APK: $APK"
echo "=========================================="
echo ""
echo "To install on phone:"
echo "  adb install $APK"
echo "Or transfer the APK file to your phone and open it."
