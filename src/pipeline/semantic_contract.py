#!/usr/bin/env python3
"""semantic_contract.py — 语义保全契约（host 契约环，内核零-LLM）

内核产『保全契约』（开放读者承诺 / 活跃伏笔 / 角色关系 / canon 硬事实 / 结尾钩）+ 零-LLM 词级预检；
host LLM 据卡写回执 `chapter_NNN_semantic_review.json`；`run_accept` 读回执评估并按策略门禁。

内核 NEVER 调 LLM——语义判断的*正确性*由 host 负责，这里只做确定性的契约生成 / 词级预检 / 回执消费。
整体 fail-open：任何异常 → 空契约 / available False，绝不阻断 diff 或入库主流程。
"""
import json
from contextlib import closing

from src.pipeline._base import connect, _get_novel_id


# ── 契约构建 ──

def _promise_items(cur, nid) -> list:
    rows = cur.execute(
        "SELECT id, promise_title, promise_detail, importance "
        "FROM reader_promises WHERE novel_id=? AND status='open' "
        "ORDER BY importance DESC", (nid,)).fetchall()
    return [{
        "id": f"promise_{r['id']}", "dimension": "reader_promise",
        "assertion": r["promise_title"], "evidence": r["promise_detail"] or "",
        "anchor": [], "importance": r["importance"] or 3,
    } for r in rows]


def _thread_items(cur, nid) -> list:
    rows = cur.execute(
        "SELECT id, title, thread_type, importance FROM plot_threads "
        "WHERE novel_id=? AND status IN ('open','active') "
        "ORDER BY importance DESC", (nid,)).fetchall()
    return [{
        "id": f"thread_{r['id']}", "dimension": "plot_thread",
        "assertion": r["title"], "evidence": r["thread_type"] or "",
        "anchor": [], "importance": r["importance"] or 3,
    } for r in rows]


def _relation_items(cur, nid, source_text) -> list:
    from src.pipeline.ingest import _count_character_appearances
    all_chars = [r["name"] for r in cur.execute(
        "SELECT name FROM characters WHERE novel_id=?", (nid,)).fetchall()]
    onstage = {n for n, c in _count_character_appearances(source_text, all_chars).items() if c > 0}
    rows = cur.execute(
        "SELECT id, char_a, char_b, relation_type, detail FROM character_relationships "
        "WHERE novel_id=?", (nid,)).fetchall()
    items = []
    for r in rows:
        a, b = r["char_a"], r["char_b"]
        if a in onstage or b in onstage:
            items.append({
                "id": f"rel_{r['id']}", "dimension": "character_relationship",
                "assertion": f"{a}—{r['relation_type'] or '关系'}—{b}",
                "evidence": r["detail"] or "", "anchor": [a, b], "importance": 3,
            })
    return items


def _hook_items(cur, nid, chapter_no) -> list:
    row = cur.execute(
        "SELECT conflict_point, ending_hook_direction FROM chapter_plans "
        "WHERE novel_id=? AND chapter_no=?", (nid, chapter_no)).fetchone()
    if not row:
        return []
    conflict, hook = row["conflict_point"], row["ending_hook_direction"]
    if not (hook or conflict):
        return []
    return [{
        "id": "hook", "dimension": "ending_hook",
        "assertion": hook or conflict, "evidence": conflict or "",
        "anchor": [], "importance": 4,
    }]


def _canon_items(source_text) -> list:
    """canon 硬事实直接从原文抽（自包含，不依赖可能缺失的 evidence_map 文件）。"""
    from src.guards.canon_evidence_guard import extract_claims
    items = []
    seen = set()
    for i, c in enumerate(extract_claims(source_text)):
        claim = (c.get("claim") or "").strip()
        if claim and claim not in seen:
            seen.add(claim)
            items.append({
                "id": f"canon_{i}", "dimension": "canon_fact",
                "assertion": claim, "evidence": c.get("context", ""),
                "anchor": [claim], "importance": 4,
            })
    return items


def build_preservation_contract(app, chapter_no, source_text) -> dict:
    """汇集 4 维待保全项 → 统一 item 列表。整体 fail-open。"""
    items = []
    try:
        with closing(connect(app)) as conn:
            cur = conn.cursor()
            nid = _get_novel_id(cur, app)
            if nid is not None:
                for fn in (_promise_items, _thread_items):
                    try:
                        items += fn(cur, nid)
                    except Exception:
                        pass
                try:
                    items += _relation_items(cur, nid, source_text)
                except Exception:
                    pass
                try:
                    items += _hook_items(cur, nid, chapter_no)
                except Exception:
                    pass
    except Exception as e:
        return {"available": False, "reason": str(e), "chapter_no": chapter_no, "items": []}

    try:
        items += _canon_items(source_text)
    except Exception:
        pass

    return {"available": True, "chapter_no": chapter_no, "items": items}


# ── 零-LLM 词级预检 ──

def lexical_precheck(contract, revised_text) -> dict:
    """仅对有具体 anchor 的项判 anchor 是否仍出现在 revised；全缺 → likely_broken。
    抽象项（承诺/伏笔/钩）标 anchor_checkable=False，留给 host LLM 判断。"""
    results = {}
    for item in contract.get("items", []):
        anchors = [a for a in (item.get("anchor") or []) if a]
        if not anchors:
            results[item["id"]] = {"anchor_checkable": False}
            continue
        present = [a for a in anchors if a in revised_text]
        results[item["id"]] = {
            "anchor_checkable": True,
            "present": present,
            "likely_broken": len(present) == 0,    # anchor 全部消失 → 疑似破坏
        }
    return results


# ── host 请求卡 / 回执 ──

def _verdict_template(contract) -> dict:
    return {
        "chapter_no": contract.get("chapter_no", 0),
        "items": [{"id": it["id"], "assertion": it["assertion"],
                   "verdict": "uncertain", "note": ""} for it in contract.get("items", [])],
    }


def write_review_request(contract, precheck, json_path, md_path, verdict_path):
    """写 host 用的语义保全请求：json（契约 + 预检 + 回执模板）+ md 卡（逐条 + 填写指引）。"""
    from version import get_version
    json_path = _as_path(json_path)
    md_path = _as_path(md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": get_version(),
        "chapter_no": contract.get("chapter_no", 0),
        "contract": contract,
        "lexical_precheck": precheck or {},
        "verdict_template": _verdict_template(contract),
        "verdict_expected_path": str(verdict_path),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    items = contract.get("items", [])
    lines = [
        f"# 第{contract.get('chapter_no', 0)}章 语义保全清单",
        "",
        "改写**不得破坏**下列要素。逐条判断改稿是否仍保全，把回执写到：",
        f"`{verdict_path}`",
        "",
        "回执 schema：",
        "```json",
        '{"chapter_no": N, "items": [{"id": "...", "verdict": "preserved|broken|uncertain", "note": "..."}]}',
        "```",
        "",
        f"- 待保全项: {len(items)}",
        "",
    ]
    if not items:
        lines.append("（本章无可机检的待保全项。）")
    for it in items:
        pc = (precheck or {}).get(it["id"], {})
        note = ""
        if pc.get("anchor_checkable") and pc.get("likely_broken"):
            note = "  ⚠️ 词级预检：锚点已从改稿消失，疑似破坏"
        lines.extend([
            f"### {it['id']}（{it['dimension']}，重要度 {it['importance']}）",
            f"- 要素: {it['assertion']}",
            f"- 依据: {it.get('evidence', '')}",
        ])
        if note:
            lines.append(f"-{note}")
        lines.append("")
    lines.append(f"*Generated by semantic_contract {get_version()}*")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def read_verdict(path):
    """读 host 写的回执 json；缺失/坏 JSON/结构不符 → None。"""
    path = _as_path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return None
    return data


# ── 评估 ──

def evaluate_preservation(contract, precheck, verdict, enforce=False) -> dict:
    """合并词级预检 + host 回执 → broken/uncertain/preserved。"""
    items = contract.get("items", [])
    if not items:
        return {"available": False, "source": "none", "broken": [],
                "uncertain": [], "preserved": [], "lexical_broken": [],
                "enforced": bool(enforce)}

    lexical_broken = [iid for iid, r in (precheck or {}).items() if r.get("likely_broken")]
    llm_broken, llm_uncertain, llm_preserved = [], [], []
    source = "lexical"
    if verdict and isinstance(verdict.get("items"), list):
        source = "llm"
        vmap = {v.get("id"): v.get("verdict") for v in verdict["items"] if isinstance(v, dict)}
        for it in items:
            vd = vmap.get(it["id"])
            if vd == "broken":
                llm_broken.append(it["id"])
            elif vd == "uncertain":
                llm_uncertain.append(it["id"])
            elif vd == "preserved":
                llm_preserved.append(it["id"])

    broken = sorted(set(lexical_broken) | set(llm_broken))
    return {
        "available": True,
        "source": source,
        "broken": broken,
        "uncertain": sorted(set(llm_uncertain)),
        "preserved": sorted(set(llm_preserved)),
        "lexical_broken": sorted(lexical_broken),
        "enforced": bool(enforce),
    }


def _as_path(p):
    from pathlib import Path
    return p if isinstance(p, Path) else Path(p)
