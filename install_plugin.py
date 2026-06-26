#!/usr/bin/env python3
"""install_plugin.py — 一键安装 proseforge-engine 到 Hermes writer profile

用法:
    python install_plugin.py
    python install_plugin.py --profile writer

无需手动复制文件，脚本自动识别 Hermes 配置目录。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_hermes_root() -> Path:
    """自动发现 Hermes Agent 数据目录"""
    # 优先级: HERMES_DATA_DIR 环境变量 > ~/.hermes
    env = os.environ.get("HERMES_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".hermes"


def enable_plugin_in_config(config_file: Path, plugin_name: str) -> bool:
    """幂等地把 plugin_name 加入 config.yaml 的 plugins.enabled 列表。

    仅做基于行的最小改动（不走 YAML round-trip），因此保留原有注释/格式，
    且不依赖 PyYAML（安装器可能在裸 system python 下运行）。
    返回 True 表示写入了改动，False 表示无需改动。
    """
    text = config_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 已在 enabled 列表中（作为列表项出现）→ 无需改动
    item_marker = f"- {plugin_name}"
    if any(ln.strip() == item_marker for ln in lines):
        return False

    # 定位顶层 plugins: 行
    plugins_idx = next(
        (i for i, ln in enumerate(lines) if ln.rstrip() == "plugins:" or ln.startswith("plugins:")),
        None,
    )

    if plugins_idx is None:
        # 无 plugins 段 → 追加完整段落
        block = ["plugins:", "  enabled:", f"    - {plugin_name}"]
        if lines and lines[-1].strip():
            lines.append("")  # 与已有内容留一空行
        lines.extend(block)
        config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    plugins_indent = len(lines[plugins_idx]) - len(lines[plugins_idx].lstrip())

    # 在 plugins 段内查找 enabled: 子键（缩进比 plugins: 更深）
    enabled_idx = None
    for i in range(plugins_idx + 1, len(lines)):
        ln = lines[i]
        if not ln.strip():
            continue
        indent = len(ln) - len(ln.lstrip())
        if indent <= plugins_indent:
            break  # 离开 plugins 段
        if ln.strip().rstrip() in ("enabled:", "enabled: []") or ln.lstrip().startswith("enabled:"):
            enabled_idx = i
            break

    if enabled_idx is None:
        # 有 plugins: 但无 enabled: → 紧随 plugins: 之后插入 enabled 子段
        child_indent = " " * (plugins_indent + 2)
        new_lines = [f"{child_indent}enabled:", f"{child_indent}  - {plugin_name}"]
        lines[plugins_idx + 1 : plugins_idx + 1] = new_lines
        config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    # 已有 enabled: 列表 → 追加一个列表项，匹配已有列表项缩进
    enabled_indent = len(lines[enabled_idx]) - len(lines[enabled_idx].lstrip())
    item_indent = None
    insert_at = enabled_idx + 1
    for i in range(enabled_idx + 1, len(lines)):
        ln = lines[i]
        if not ln.strip():
            insert_at = i
            continue
        indent = len(ln) - len(ln.lstrip())
        if indent <= enabled_indent:
            break  # 离开 enabled 子段
        if ln.lstrip().startswith("- "):
            item_indent = indent
            insert_at = i + 1
    if item_indent is None:
        item_indent = enabled_indent + 2  # 空列表，使用默认缩进
    lines.insert(insert_at, f"{' ' * item_indent}- {plugin_name}")
    config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="安装 proseforge-engine 插件到 Hermes profile")
    parser.add_argument("--profile", default="writer", help="目标 profile 名称 (默认: writer)")
    parser.add_argument("--plugin-src", default=None, help="插件源码目录 (默认: 项目内 plugin/proseforge-Hermes)")
    args = parser.parse_args()

    # 项目根目录假定为脚本所在目录
    project_root = Path(__file__).resolve().parent
    plugin_src = Path(args.plugin_src) if args.plugin_src else project_root / "plugin" / "proseforge-Hermes"

    if not plugin_src.exists():
        print(f"[ERROR] 插件源码不存在: {plugin_src}")
        sys.exit(1)

    hermes_root = find_hermes_root()
    profile_dir = hermes_root / "profiles" / args.profile
    plugins_dir = profile_dir / "plugins"
    target_dir = plugins_dir / "proseforge-engine"

    if not profile_dir.exists():
        print(f"[ERROR] Hermes profile '{args.profile}' 不存在: {profile_dir}")
        print(f"  请先运行: hermes profile create {args.profile} --clone")
        sys.exit(1)

    # 创建 plugins 目录
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # 复制插件
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(plugin_src, target_dir)
    # 写入项目根路径标记，供 _find_proseforge_root() 读取
    (target_dir / ".project_root").write_text(str(project_root.resolve()), encoding="utf-8")
    print(f"[OK] 插件已安装到: {target_dir}")
    print(f"[OK] 已写入 .project_root: {project_root.resolve()}")

    # 确保 profile 配置加载该插件（插件名由目标目录名派生，避免硬编码）
    config_file = profile_dir / "config.yaml"
    if config_file.exists():
        if enable_plugin_in_config(config_file, target_dir.name):
            print(f"[OK] 已在 config.yaml 中启用插件: {target_dir.name}")
        else:
            print(f"[OK] config.yaml 已启用插件: {target_dir.name}")

    print(f"\n启动: hermes --profile {args.profile}")
    print(f"工具: nf_状态  nf_预写  nf_续写  nf_改写  nf_流水  nf_卷管")


if __name__ == "__main__":
    main()
