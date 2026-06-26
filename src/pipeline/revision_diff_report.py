#!/usr/bin/env python3
"""
revision_diff_report.py — 改稿对比报告

对比 source chapter 和 revised draft，生成 diff report。
让用户知道改了什么、改了多大、是否建议采用。

用法:
  python scripts/revision_diff_report.py \\
    --source chapter.txt --revised revised.txt \\
    --rewrite-log log.json --out diff_report.json
"""
import difflib
from version import get_version


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def compute_diff_summary(source_paras: list, revised_paras: list) -> dict:
    """计算改动统计：用 difflib 做**字级**对比，区分『改 3 字』与『整段重写』。"""
    src_chars = sum(count_chinese(p) for p in source_paras)
    rev_chars = sum(count_chinese(p) for p in revised_paras)

    # 段落级：对齐段落序列，统计真正变动（replace/insert/delete）的段落数
    para_sm = difflib.SequenceMatcher(None, source_paras, revised_paras)
    changed_paragraphs = sum(
        max(i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in para_sm.get_opcodes() if tag != "equal")

    # 字级：在整章字符串上算改动字符占比 → 改 3 字 ≈ 极小，整段重写 ≈ 大
    src_full = "\n".join(source_paras)
    rev_full = "\n".join(revised_paras)
    char_sm = difflib.SequenceMatcher(None, src_full, rev_full)
    changed_chars = sum(
        max(i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in char_sm.get_opcodes() if tag != "equal")
    char_change_ratio = min(1.0, changed_chars / max(len(src_full), 1))
    unchanged_ratio = round(1.0 - char_change_ratio, 3)

    return {
        "changed_paragraphs": changed_paragraphs,
        "char_change_ratio": round(char_change_ratio, 3),
        "unchanged_ratio": unchanged_ratio,
        "source_chars": src_chars,
        "revised_chars": rev_chars,
        "added_chars": max(0, rev_chars - src_chars),
        "removed_chars": max(0, src_chars - rev_chars),
        "net_chars": rev_chars - src_chars,
    }


def compute_task_results(tasks: list, changed_ranges: list,
                         verification: dict = None) -> list:
    """合并任务和改动范围，生成每个任务的结果。

    有 guard 复跑验证（verification.available）时，按类别细化为
    RESOLVED（问题已消失）/ ATTEMPTED（仍在但有改动）/ SKIPPED（无改动）；
    否则退回二元 APPLIED/SKIPPED（向后兼容）。
    """
    range_by_task = {}
    for r in changed_ranges:
        tid = r.get("task_id", "")
        range_by_task.setdefault(tid, []).append(r)

    v = verification or {}
    verified = bool(v.get("available"))
    persisted_cats = set(v.get("persisted", []) or [])

    results = []
    for task in tasks:
        tid = task["task_id"]
        touched = bool(range_by_task.get(tid, []))
        if verified:
            cat = task.get("category", "")
            if cat and cat not in persisted_cats:
                status = "RESOLVED"
            elif touched:
                status = "ATTEMPTED"
            else:
                status = "SKIPPED"
        else:
            status = "APPLIED" if touched else "SKIPPED"
        results.append({
            "task_id": tid,
            "status": status,
            "before_problem": task.get("problem", "")[:60],
            "after_change": task.get("instruction", "")[:80] if touched else "未检出该任务区间的改动",
        })
    return results


_QUOTE_MARKS = ('"', '“', '”', '「', '」', '『', '』')


def generate_risk_flags(source_paras: list, revised_paras: list,
                        summary: dict) -> list:
    """检测改动是否过头"""
    flags = []
    ratio = summary.get("char_change_ratio")
    if ratio is None:                       # 容忍只带 unchanged_ratio 的调用
        ratio = 1.0 - summary.get("unchanged_ratio", 0.0)
    if ratio <= 0.35:
        flags.append("改动比例低于 35%，风格保持较好")
    else:
        flags.append("改动比例超过 35%，请仔细审查")

    # 对白丢失检查：仅当原文本身有引号/对白标记才比对（零引号写作风格下跳过，不产噪音）
    src_full = "\n".join(source_paras)
    if any(q in src_full for q in _QUOTE_MARKS):
        src_quotes = sum(1 for p in source_paras if any(q in p for q in _QUOTE_MARKS))
        rev_quotes = sum(1 for p in revised_paras if any(q in p for q in _QUOTE_MARKS))
        if rev_quotes < src_quotes * 0.8:
            flags.append("对白段落数量显著减少，可能丢失了角色对话")

    # 检测结尾是否被改动
    if source_paras[-2:] != revised_paras[-2:]:
        flags.append("章节结尾有改动，请确认钩子是否保留")

    return flags


def _recommend(summary: dict, risk_flags: list, verification: dict) -> str:
    """多信号推荐：字级改动量 + risk_flags + guard 复跑验证（见 rewrite.py）。

    无验证块（verification 为空/不可用）时退回纯结构信号，向后兼容。"""
    ratio = summary["char_change_ratio"]
    v = verification or {}
    available = bool(v.get("available"))
    regressed = available and bool(v.get("regressed"))
    resolved = available and bool(v.get("resolved"))
    loss_or_big = any("丢失" in f or "超过" in f for f in risk_flags)

    if ratio <= 0.001:
        return "NO_CHANGE_DETECTED"
    if regressed:
        return "REVISION_REJECTED"        # 复跑发现问题回升 → 拒绝
    if ratio > 0.50 and not resolved:
        return "REVISION_REJECTED"        # 改动过猛且未验证改善 → 拒绝
    if resolved and not loss_or_big:
        return "REVIEW_BEFORE_ACCEPT"     # 验证有改善、无重大风险
    if ratio <= 0.35 and not loss_or_big:
        return "REVIEW_BEFORE_ACCEPT"
    return "REVIEW_CAREFULLY"


def generate_diff_report(source_text: str, revised_text: str,
                         rewrite_log: dict,
                         tasks: list = None,
                         verification: dict = None) -> dict:
    """生成完整 diff report。verification 为 guard 复跑验证块（可选，见 rewrite.py）。"""
    source_paras = split_paragraphs(source_text)
    revised_paras = split_paragraphs(revised_text)

    summary = compute_diff_summary(source_paras, revised_paras)
    changed_ranges = rewrite_log.get("changed_ranges", [])
    task_results = compute_task_results(tasks or [], changed_ranges, verification)
    risk_flags = generate_risk_flags(source_paras, revised_paras, summary)
    recommendation = _recommend(summary, risk_flags, verification)

    chapter_no = rewrite_log.get("chapter_no", 0)

    return {
        "version": get_version(),
        "chapter_no": chapter_no,
        "source_file": rewrite_log.get("source", ""),
        "revised_file": rewrite_log.get("output", ""),
        "summary": summary,
        "task_results": task_results,
        "risk_flags": risk_flags,
        "verification": verification or {"available": False},
        "recommendation": recommendation,
    }


