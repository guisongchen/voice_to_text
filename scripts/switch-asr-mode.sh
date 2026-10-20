#!/usr/bin/env bash
# 切换 voice-to-text 的 ASR 后端: 本地 ASRCore (GPU) <-> 云端 DashScope
#
# 用法:
#   scripts/switch-asr-mode.sh cloud   # 直连云端 (需 DASHSCOPE_API_KEY)
#   scripts/switch-asr-mode.sh local   # 本地 ASRCore + GPU 模型
#   scripts/switch-asr-mode.sh status  # 查看当前模式
#
# 原理: 改写 systemd user override (~/.config/systemd/user/voice-to-text.service.d/)
# 并重启服务。API key 只从 ~/.bashrc 读取/保留在 override 中, 不写入任何仓库文件。
set -euo pipefail

OVERRIDE_DIR="$HOME/.config/systemd/user/voice-to-text.service.d"
OVERRIDE="$OVERRIDE_DIR/cloud-asr.conf"
UNIT="voice-to-text"

current_mode() {
    systemctl --user show "$UNIT" -p Environment 2>/dev/null \
        | tr ' ' '\n' | grep '^VTT_ASR_MODE=' | cut -d= -f2 || true
}

case "${1:-status}" in
    status)
        mode=$(current_mode)
        echo "当前模式: ${mode:-asrcore (默认, 无 override)}"
        systemctl --user is-active "$UNIT" | sed 's/^/服务状态: /'
        ;;
    cloud)
        key=$(systemctl --user show "$UNIT" -p Environment 2>/dev/null \
              | tr ' ' '\n' | grep '^DASHSCOPE_API_KEY=' | cut -d= -f2- || true)
        if [ -z "$key" ]; then
            key=$(grep -oP '^export DASHSCOPE_API_KEY="\K[^"]+' "$HOME/.bashrc" 2>/dev/null || true)
        fi
        if [ -z "$key" ]; then
            echo "✗ 找不到 DASHSCOPE_API_KEY (override 和 ~/.bashrc 都没有)" >&2
            exit 1
        fi
        mkdir -p "$OVERRIDE_DIR"
        printf '[Service]\nEnvironment=VTT_ASR_MODE=cloud\nEnvironment=DASHSCOPE_API_KEY=%s\n' \
            "$key" > "$OVERRIDE"
        systemctl --user daemon-reload
        systemctl --user restart "$UNIT"
        echo "✓ 已切换到云端模式 (DashScope qwen3-asr-flash)"
        ;;
    local)
        # 保留 override 里的 key 供下次切回, 只改模式
        if [ -f "$OVERRIDE" ]; then
            sed -i 's/^Environment=VTT_ASR_MODE=.*/Environment=VTT_ASR_MODE=asrcore/' "$OVERRIDE"
        fi
        systemctl --user daemon-reload
        systemctl --user restart asr-core "$UNIT"
        echo "✓ 已切换到本地模式 (ASRCore + 本地 GPU 模型)"
        ;;
    *)
        echo "用法: $0 [cloud|local|status]" >&2
        exit 1
        ;;
esac
