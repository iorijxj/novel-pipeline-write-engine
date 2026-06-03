#!/usr/bin/env python3
"""demo_quality.py — 质量检测模块全流程演示 v0.6.6

运行: python demo/demo_quality.py
输出: demo/demo_quality_output.txt

前置: 需要先有已写的章节（运行 python novel.py demo 之后）
"""

import sys
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOVEL = [sys.executable, str(ROOT / "novel.py")]

def run(cmd: str):
    args = cmd.split()
    r = subprocess.run(NOVEL + args, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    return r.stdout + r.stderr

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

# ════════════════════════════════════════════
#  DEMO: 质量检测
# ════════════════════════════════════════════

section("STEP 1: guards — 列出所有注册守卫")

cmd("guards")

section("STEP 2: voice check — 第1章声纹一致性")

cmd("voice check 1")

section("STEP 3: texture check — 完整质量检测")

cmd("texture check 1")

section("STEP 4: genre list — 可用题材包")

cmd("genre list")

section("STEP 5: rag status — RAG 状态")

cmd("rag status")

section("完成")

print("  Demo 质量检测演示完成")
