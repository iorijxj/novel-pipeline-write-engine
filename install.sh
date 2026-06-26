#!/usr/bin/env bash
# install.sh — ProseForge 安装器 (macOS / Linux)
# 用法: chmod +x install.sh && ./install.sh
set -e

PYTHON=${PYTHON:-python3}

echo "============================================"
VER=$(cat VERSION 2>/dev/null || echo "0.8.0")
echo "  ProseForge $VER"
echo "  proseforge-engine Plugin 安装 (Mac / Linux)"
echo "============================================"
echo ""

if ! command -v hermes >/dev/null 2>&1; then
  echo "[WARN] 'hermes' 命令未找到。请先安装 Hermes Agent:"
  echo "  https://hermes-agent.nousresearch.com/docs"
  echo ""
  echo "安装完成后重新运行本脚本。"
  exit 1
fi

echo "[STEP] 创建 writer profile（如尚未存在）..."
hermes profile create writer --clone 2>/dev/null || echo "  writer profile 已存在，跳过"

# 复制插件、写入 .project_root 标记、启用 config.yaml 等逻辑统一交给
# install_plugin.py（单一事实来源），避免 bash 重复实现且难以稳健编辑 YAML。
echo "[STEP] 安装插件到 writer profile..."
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$PYTHON" "$PROJECT_ROOT/install_plugin.py" --profile writer
