# 🔊 Audio Booster - 批量音频放大器

Python + Kivy 安卓 App，支持批量放大音频音量，智能防失真。
1
## 功能特性

| 功能 | 说明 |
|------|------|
| 🎵 批量处理 | 选择整个文件夹，一键处理所有音频 |
| 🔢 倍数放大 | 0.5x ~ 10x 自由调节 |
| 🛡️ 智能防失真 | 软限幅 + 动态压缩，保证音质 |
| 📊 多种模式 | 智能/倍数/峰值归一化 三种策略 |
| 📁 多格式支持 | MP3, WAV, FLAC, OGG, M4A, AAC 等 |
| 📋 处理报告 | 每个文件的峰值/RMS 变化一目了然 |

## 三种处理模式

### 🛡️ 智能模式（推荐）
```
自动检测 → 如果直接放大会失真 → 先压缩动态 → 再放大
结果：响度提升明显，音质保持良好
```

### 🔢 倍数模式
```
直接按倍数放大 → 软限幅保护
结果：最直观，但大倍数时可能有轻微压缩感
```

### 📊 峰值归一化
```
找到音频峰值 → 对齐到目标值（-1 dBFS）→ 可选额外倍数
结果：充分利用动态范围，适合已有混音的音频
```

## 核心算法

### 软限幅器（Soft Clipper）
使用 `tanh` 曲线代替硬削波，过渡平滑，不产生高频谐波失真：

```python
# 超出阈值的部分用 tanh 压缩
threshold = 0.95
knee = 0.1
x = (|sample| - threshold) / knee
output = sign * (threshold + knee * tanh(x))
```

### 真峰值检测
过采样 4 倍检测采样点之间的实际峰值（ITU-R BS.1770 标准）。

## 构建 APK

### 前置条件
```bash
# 安装 Buildozer
pip install buildozer

# 安装 Android SDK/NDK（Buildozer 会自动下载）
# 需要 Java JDK 17+
sudo apt install openjdk-17-jdk

# Linux 系统依赖
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
```

### 构建步骤
```bash
cd audio-amplifier-app

# 首次构建（会下载 Android SDK/NDK，耗时较长）
buildozer android debug

# 安装到手机
buildozer android debug deploy run

# 生成 release APK（需要签名）
buildozer android release
```

### 构建时间
- 首次：30~60 分钟（下载 SDK/NDK + 编译）
- 后续：5~15 分钟（增量编译）

## 桌面测试

不需要 Android 也能测试 UI：

```bash
pip install kivy numpy scipy pydub soundfile
python main.py
```

桌面模式下会弹出文件夹选择对话框。

## 项目结构

```
audio-amplifier-app/
├── main.py              # Kivy UI 主程序
├── audio_processor.py   # 核心音频处理引擎
├── buildozer.spec       # Android 构建配置
├── assets/
│   ├── icon.png         # App 图标 (512x512)
│   └── presplash.png    # 启动画面 (512x512)
└── README.md
```

## 注意事项

1. **ffmpeg 依赖**：pydub 需要 ffmpeg 来处理 MP3/M4A 等格式。Android 上需要交叉编译 ffmpeg 并放入 `libs/` 目录。
2. **存储权限**：Android 6.0+ 需要运行时权限申请，App 已内置处理。
3. **大文件处理**：使用流式处理，内存占用可控。但超大文件（>100MB）可能较慢。
4. **输出位置**：处理后的文件保存在输入目录下的 `amplified_output/` 子文件夹。
