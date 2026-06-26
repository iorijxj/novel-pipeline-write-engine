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

echo "[STEP] 安装插件到 writer profile..."
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_SRC="$PROJECT_ROOT/plugin/proseforge-Hermes"
PROFILE_DIR="$HOME/.hermes/profiles/writer"
PLUGIN_DST="$PROFILE_DIR/plugins/proseforge-engine"

mkdir -p "$PLUGIN_DST"
cp -r "$PLUGIN_SRC/"* "$PLUGIN_DST/"

# 写入项目根路径标记，供插件 _find_proseforge_root() 在仓库外定位项目
echo "$PROJECT_ROOT" > "$PLUGIN_DST/.project_root"
echo "[OK] 已写入 .project_root: $PROJECT_ROOT"

# 确保 profile 配置加载该插件（与 install_plugin.py 一致：在已有 plugins: 行后注入）
CONFIG_FILE="$PROFILE_DIR/config.yaml"
if [ -f "$CONFIG_FILE" ] && ! grep -q "proseforge-engine" "$CONFIG_FILE" && grep -q "^plugins:" "$CONFIG_FILE"; then
  awk '/^plugins:/{print; print "  enabled:"; print "    - proseforge-engine"; next} {print}' \
    "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
  echo "[OK] 已在 config.yaml 中启用插件"
fi

echo "[OK] 插件已安装到: $PLUGIN_DST"
echo ""
echo "============================================"
echo "  安装完成。"
echo ""
echo "  启动: hermes --profile writer"
echo "  工具: nf_状态  nf_预写  nf_续写  nf_改写 ..."
echo "============================================"
