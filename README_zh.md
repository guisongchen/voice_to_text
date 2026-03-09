# 语音转文字输入工具

一款适用于 Linux 的系统级语音输入工具，可通过键盘快捷键录制音频并在任意位置插入转录文本。

## 功能特性

⌨️ **系统级语音输入** - 按 Alt+R 开始录制，再次按下以转录并插入文本
🎤 **单命令工作流** - 简单的开关脚本实现开始/停止
📝 **Whisper AI 转录** - 使用 OpenAI 的 Whisper 实现高精度语音转文字
🚀 **GPU 加速** - 支持 CUDA 的快速转录
🔒 **安全的进程间通信** - 使用 Unix 域套接字通信（无 PID 重用漏洞）
🌏 **多语言支持** - 中文、英文及多种其他语言

## 系统要求

- Python 3.10+
- 使用 X11 的 Ubuntu/Linux
- 推荐使用带 CUDA 的 NVIDIA GPU（以实现快速转录）
- xdotool（用于文本插入）
- 系统音频库（PortAudio）

## 安装

### 1. 安装系统依赖

```bash
# 安装 xdotool 用于文本插入
sudo apt install xdotool

# 安装 PortAudio 用于音频录制
sudo apt-get install portaudio19-dev
```

### 2. 验证 CUDA 安装

```bash
nvidia-smi  # 应显示您的 GPU 信息
```

### 3. 安装 Python 包

```bash
# 克隆仓库
git clone <your-repo-url>
cd voice_to_text

# 推荐使用 uv 安装
uv sync
uv pip install .
```

## 快速开始

### 桌面快捷方式设置（推荐）

设置键盘快捷键以实现免提语音输入：

**对于 GNOME 桌面环境：**

1. 打开 **设置** → **键盘** → **键盘快捷键**
2. 点击 **"+"** 添加自定义快捷键
3. 设置以下内容：
   - **名称**：`语音转文字`
   - **命令**：`/full/path/to/voice_to_text_socket_toggle.py`
   - **快捷键**：按下 `Alt+R`

**使用方法：**
- 按 `Alt+R` 开始录制
- 说出您要输入的文本
- 再次按 `Alt+R` 停止录制、转录文本并在光标处插入文本

## 工作原理

1. **按下快捷键** → 开始录制（您会听到一声提示音）
2. **说出文本** → 音频正在被捕获
3. **再次按下快捷键** → 停止录制（您会听到另一声提示音）
4. **进行转录** → Whisper AI 将语音转换为文本
5. **插入文本** → 转录的文本出现在光标位置

## 配置

### 模型大小

选择不同的 Whisper 模型以平衡速度与准确性：

```bash
# 速度更快但准确性稍低
voice-to-text --model small

# 默认（平衡型）
voice-to-text --model medium

# 准确性更高但速度较慢
voice-to-text --model large
```

可用模型大小：`tiny`、`base`、`small`、`medium`、`large`

### 保留音频文件用于调试

```bash
voice-to-text --keep-audio
```

音频文件会保存在 `/tmp/` 目录下，并带有时间戳。

## 技术细节

### 架构

- **进程间通信方法**：Unix 域套接字 (`/tmp/voice_to_text.sock`)
- **音频格式**：44.1kHz，立体声，WAV
- **转录引擎**：OpenAI Whisper（GPU 加速）
- **文本插入**：xdotool（X11）

### 安全特性

该工具使用 Unix 域套接字进行进程间通信，提供以下优势：

✅ 带有确认机制的可靠消息传递
✅ 原子套接字操作
✅ 自动清理过时套接字
✅ 更好的错误处理

### 线程安全

所有共享状态均使用适当的同步机制保护：
✅ **互斥锁保护的标志** - `stop_signal` 和 `should_exit` 使用 `threading.Lock`
✅ **线程安全的音频录制器** - 录制状态和帧缓冲区受锁保护
✅ **可重入的清理** - 使用清理标志防止资源重复释放
✅ **基于超时的线程合并** - 所有线程 join 操作都有超时，防止死锁


## 项目结构

```
voice_to_text/
├── voice_to_text.py              # 主服务（包含录制器、转录器和 IPC）
├── voice_to_text_toggle.py       # 键盘快捷键的开关脚本
├── README.md                     # 英文文档
├── README_zh.md                  # 中文文档
└── pyproject.toml                # 包配置
```

代码库有意保持精简 - 所有核心功能整合到两个文件中，便于维护。

## 故障排除

### "xdotool not found"
```bash
sudo apt install xdotool
```

### "No CUDA device found"
工具将回退到 CPU 模式，但速度会较慢。请安装 NVIDIA 驱动和 CUDA 工具包。

### 套接字 "Permission denied"
```bash
# 清理过时的套接字文件
rm /tmp/voice_to_text.sock
```

### 录制无法开始
检查日志文件：
```bash
tail -f /tmp/voice_to_text.log
```

### 文本未插入
- 确保 xdotool 已安装
- 确保目标窗口具有焦点
- 尝试在使用快捷键前点击文本框

## 开发

### 运行测试
```bash
pytest
```

### 以开发模式安装
```bash
pip install -e .
```

## 常见问题

**问：这个工具支持 Wayland 吗？**
答：当前针对 X11 进行了优化。Wayland 支持可能需要额外设置。

**问：没有 GPU 可以使用吗？**
答：可以，但转录速度会较慢。工具会自动回退到 CPU 模式。

**问：支持哪些语言？**
答：Whisper 支持多种语言，包括英语、中文、西班牙语、法语、德语、日语、韩语等。

**问：可以使用不同的键盘快捷键吗？**
答：可以！在创建桌面快捷方式时设置不同的键组合即可。

**问：音频文件保存在哪里？**
答：默认保存在 `/tmp/whisper_recording_*.wav`，转录后会自动删除。使用 `--keep-audio` 参数可以保留它们。

## 贡献

欢迎贡献！请随时提交问题或拉取请求。

## 许可证

[您的许可证信息]

## 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) 提供转录模型
- xdotool 提供文本插入功能