#!/usr/bin/env python3
"""demo_character.py — 角色管理模块全流程演示 v0.6.6

运行: python demo/demo_character.py
输出: demo/demo_character_output.txt
"""

import sys
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOVEL = [sys.executable, str(ROOT / "novel.py")]

def run(cmd: str, label: str = ""):
    """运行 novel.py 命令并返回输出。"""
    args = cmd.split()
    r = subprocess.run(NOVEL + args, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    out = r.stdout + r.stderr
    return out

def section(title: str):
    print()
    print("=" * 68)
    print(f"  {title}")
    print("=" * 68)
    print()

def cmd(c: str):
    print(f"$ python novel.py {c}")
    out = run(c)
    print(out)
    return out

# ════════════════════════════════════════════
#  DEMO: 角色综合管理
# ════════════════════════════════════════════

section("STEP 1: 创建角色卡")

cmd("character create 韩烈")
cmd("character create 苏晚晴")
cmd("character create 张天师")

section("STEP 2: 填写性格字段")

cmd("character edit 韩烈 core 沉稳")
cmd("character edit 韩烈 decision_style 深思熟虑")
cmd("character edit 韩烈 action_tendency 主动")
cmd("character edit 韩烈 social_style 随和")
cmd("character edit 韩烈 stress_response 冷静")
cmd("character edit 韩烈 habits 抿嘴唇,握拳,眯眼睛")

section("STEP 3: 填写身份与关系")

cmd("character edit 韩烈 role 主角")
cmd("character edit 韩烈 identity 外门弟子")
cmd("character edit 韩烈 ability 灵根异变")
cmd("character edit 韩烈 alias 阿烈")
cmd("character edit 韩烈 relationship 苏晚晴:知己,张天师:对立")
cmd("character edit 韩烈 arc 从自卑到自信")
cmd("character edit 韩烈 motivation 寻玉佩身世")
cmd("character edit 韩烈 tags 修仙,外门,玉佩")

section("STEP 4: 填写声纹")

cmd("character edit 韩烈 dialect 东北话")
cmd("character edit 韩烈 common_words 应该,可能,大概")
cmd("character edit 韩烈 sentence_length_preference 短句")

section("STEP 5: 查看完整角色卡")

cmd("character show 韩烈")

section("STEP 6: 编辑苏晚晴角色")

cmd("character edit 苏晚晴 core 温和")
cmd("character edit 苏晚晴 social_style 热情")
cmd("character edit 苏晚晴 role 女主角")
cmd("character edit 苏晚晴 identity 内门弟子")
cmd("character edit 苏晚晴 ability 医术")
cmd("character edit 苏晚晴 relationship 韩烈:知己")
cmd("character edit 苏晚晴 arc 从柔弱到坚强")

section("STEP 7: 列出所有角色卡")

cmd("character list")

section("STEP 8: 从大纲检查角色卡")

out = cmd("character outline-check")
if "无角色卡" in out or "尚未创建" in out:
    section("STEP 9: 自动创建缺失卡")
    cmd("character outline-check --create")

section("STEP 10: 声纹卡组管理")

cmd("voice set list")
cmd("voice set use default")

section("STEP 11: 最终所有角色卡")

cmd("character list")

section("完成")

print("  Demo 角色管理演示完成")
print(f"  输出文件: {__file__}")
