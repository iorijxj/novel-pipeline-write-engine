"""统一的 title → slug 派生逻辑。

全仓库唯一来源。曾在 OutlineManager / SlotManager / migrate_slot_names 各有一份
拷贝，易失同步；此处合一。

规则：保留 CJK + 字母数字 + 连字符，其余字符替换为下划线，30 字符截断，
转小写，去除首尾下划线；退化为空时返回 "novel"。
"""
from __future__ import annotations

import re

# CJK 统一表意文字 U+4E00–U+9FFF。注意 Python3 的 \w 已含 CJK，CJK 范围在此为显式冗余。
_SLUG_RE = re.compile(r"[^一-鿿\w\-]")


def title_to_slug(title: str) -> str:
    """将标题转为可用作目录名 / DB slug 的字符串。"""
    clean = _SLUG_RE.sub("_", (title or "").strip())[:30]
    return clean.strip("_").lower() or "novel"
