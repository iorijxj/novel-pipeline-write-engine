#!/usr/bin/env python3
"""src/cli/commands_character.py — 角色综合管理 v0.6.6

管理角色的声纹、性格、做事风格三个维度。

命令:
  python novel.py character list                   列出所有角色卡
  python novel.py character show <角色名>           查看完整角色卡
  python novel.py character create <角色名>         创建默认角色卡
  python novel.py character delete <角色名>         删除角色卡
  python novel.py character edit <角色名> <字段> <值>  编辑指定字段
  python novel.py character outline-check          从大纲检查角色卡状态
  python novel.py character outline-check --create  检查 + 自动创建缺失卡
"""

import sys
import json
import re
from pathlib import Path
from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR
from src.cli.commands_voice import _resolve_chapter_path
from src.guards.human_texture.voice_diversity_guard import (
    get_character_card, list_character_cards, save_character_card,
    delete_voice_card,
    get_active_voice_card_set, set_active_voice_card_set, list_voice_card_sets,
    get_char_db_row, save_char_db_field, delete_char_db_row, _ensure_char_db_row,
    get_focus_state, set_focus_state, FOCUS_STATE_CHOICES,
    set_relation, delete_relation, list_relations, get_relations_for,
    export_char_card, import_char_card,
    VOICE_CARD_FIELDS, PERSONALITY_FIELDS, BEHAVIOR_FIELDS, PERSONALITY_CHOICES,
    DB_CHAR_FIELDS, DB_CHAR_FIELD_NAMES_EXT,
)


def _new_empty_card(name: str) -> dict:
    """创建默认空白角色卡."""
    return {
        "name": name,
        "voice": {k: "" for k in VOICE_CARD_FIELDS},
        "personality": {k: "" for k in PERSONALITY_FIELDS},
        "behavior": {k: ([] if k == "habits" else "") for k in BEHAVIOR_FIELDS},
    }


def _get_outline_content() -> tuple[str, str, int]:
    """获取当前活跃大纲内容，返回 (title, content, chapter_count)."""
    mgr = __import__("scripts.outline.outline_manager", fromlist=["OutlineManager"])
    OM = getattr(mgr, "OutlineManager")
    om = OM(PROJECT_ROOT)
    outline = om.current_outline()
    if not outline:
        return ("", "", 0)
    content = outline.get("content", "")
    title = outline.get("title", "未命名大纲")
    cc = outline.get("chapter_count", 0)
    return (title, content, cc)


def _extract_chinese_names(text: str) -> set:
    """从文本中提取中文人名（复用 commands_voice 逻辑）."""
    surnames_str = ("李王张刘陈杨赵黄周吴徐孙马胡朱郭何林高罗"
                    "郑梁谢宋唐许邓韩冯曹彭曾肖田董潘袁蔡蒋余"
                    "于杜叶程苏魏吕丁任卢姚沈姜崔钟谭陆汪范金"
                    "石廖贾夏韦傅方白邹孟熊秦邱江尹薛阎段雷侯"
                    "龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")
    surnames = set(surnames_str)
    reliable_names = set()
    heuristic_names = set()

    # 方法1（优先）：角色字段后提取
    for pattern in [r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[：:]\s*([^\n，。]{2,4})',
                    r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[是为叫作叫做称呼]\s*([^\n，。]{2,4})']:
        for m in re.finditer(pattern, text):
            name = m.group(1).strip()
            if 2 <= len(name) <= 4:
                reliable_names.add(name)

    # 方法2：姓氏启发式 — 仅提取 2 字名
    _punct_chars = set("，。！？、；：''（）《》…— \t,./!?;:()[]{}")
    _bad_endings = {"场", "上", "下", "里", "前", "后", "中", "的", "了",
                    "和", "与", "在", "把", "被", "将", "对", "为",
                    "都", "也", "还", "就", "已", "能", "会", "可",
                    "来", "去", "出", "进", "到", "从", "以"}
    for i, ch in enumerate(text):
        if ch in surnames and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt not in _punct_chars:
                candidate2 = text[i:i + 2]
                if candidate2[1] not in _bad_endings:
                    heuristic_names.add(candidate2)

    # 合并
    result = set(reliable_names)
    for hn in heuristic_names:
        if any(hn in rn or rn in hn for rn in reliable_names):
            continue
        _stop = {"时候", "地方", "这里", "那里", "这边", "那边", "怎么", "什么",
                 "没有", "已经", "可以", "需要", "知道", "看见", "告诉", "开始",
                 "继续", "回到", "来到", "走出", "进入", "拿起", "放下"}
        if hn in _stop:
            continue
        result.add(hn)

    return {n for n in result if 2 <= len(n) <= 4}


def _get_db_characters() -> list[dict]:
    """从当前 slot 的 characters 表获取所有已注册角色."""
    try:
        ws_dir = PROJECT_ROOT / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return []
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return []
        db_path = ws_dir / active / "novel.db"
        if not db_path.exists():
            return []
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT name, alias, role, identity FROM characters WHERE status='active'")
        rows = cur.fetchall()
        conn.close()
        result = []
        for r in rows:
            char = {"name": r[0]}
            if r[1]:
                char["alias"] = r[1]
            if r[2]:
                char["role"] = r[2]
            if r[3]:
                char["identity"] = r[3]
            result.append(char)
        return result
    except Exception:
        return []


# ── 展示工具 ──

def _render_field(field: str, val) -> str:
    """将字段值渲染为可读字符串."""
    if isinstance(val, list):
        if not val:
            return "无"
        return ", ".join(val[:5])
    if isinstance(val, dict):
        if not val:
            return "无"
        return json.dumps(val, ensure_ascii=False)[:40]
    return str(val) if val else "无"


def _print_char_table(cards: list[dict]):
    """打印角色卡表格."""
    if not cards:
        print("  当前小说无角色卡")
        return
    print(f"  角色卡 ({len(cards)} 个):")
    print(f"  {'角色':8s} {'性格':6s} {'决策':8s} {'社交':6s} {'方言':6s}")
    print(f"  {'-'*8} {'-'*6} {'-'*8} {'-'*6} {'-'*6}")
    for c in cards:
        name = c.get("name", "?")
        p = c.get("personality", {})
        b = c.get("behavior", {})
        v = c.get("voice", {})
        core = p.get("core", "") or "无"
        decision = p.get("decision_style", "") or "无"
        social = b.get("social_style", "") or "无"
        dialect = v.get("dialect", "") or "无"
        print(f"  {name:8s} {core:6s} {decision:8s} {social:6s} {dialect:6s}")


# ── 子命令处理 ──

def _char_list():
    """列出所有角色卡."""
    cards = list_character_cards(PROJECT_ROOT)
    _print_char_table(cards)
    print()
    current_set = get_active_voice_card_set(PROJECT_ROOT)
    print(f"  卡组: {current_set}")
    print(f"  详情: python novel.py character show <角色名>")


def _char_show(name: str):
    """显示完整角色卡（JSON 角色卡 + DB 数据合并）."""
    card = get_character_card(PROJECT_ROOT, name)
    if not card:
        print(f"  未找到角色「{name}」")
        return

    # 获取 DB 行
    db_row = get_char_db_row(PROJECT_ROOT, name)

    print(f"  ╔══ 角色卡 ── {name} ═══")
    print()

    # ── 身份 ──
    role_v = db_row.get("role", "") if db_row else ""
    identity_v = db_row.get("identity", "") if db_row else ""
    ability_v = db_row.get("ability", "") if db_row else ""
    alias_v = db_row.get("alias", "") if db_row else ""
    has_identity = any([role_v, identity_v, ability_v])

    # ── 性格 ──
    personality = card.get("personality", {})
    desc_v = db_row.get("personality_info", "") if db_row else ""
    has_personality = any(personality.get(f) for f in PERSONALITY_FIELDS) or bool(desc_v)

    # ── 做事风格 ──
    behavior = card.get("behavior", {})
    has_behavior = any(behavior.get(f) for f in BEHAVIOR_FIELDS if behavior.get(f))

    # ── 声纹 ──
    voice = card.get("voice", {})
    has_voice = any(voice.get(f) for f in VOICE_CARD_FIELDS)

    # ── 关系 ──
    rel_v = db_row.get("relationship", "") if db_row else ""
    has_rel = bool(rel_v)

    # ── 成长弧 ──
    arc_v = db_row.get("arc", "") if db_row else ""
    mot_v = db_row.get("motivation", "") if db_row else ""
    has_arc = bool(arc_v or mot_v)

    # ── 元数据 ──
    tags_v = db_row.get("tags", "") if db_row else ""
    has_meta = bool(alias_v or tags_v)

    # 计算所有可见段
    sections = []
    if has_identity:
        sections.append("identity")
    if has_personality:
        sections.append("personality")
    if has_behavior:
        sections.append("behavior")
    if has_voice:
        sections.append("voice")
    if has_rel:
        sections.append("relationship")
    if has_arc:
        sections.append("arc")
    if has_meta:
        sections.append("meta")

    if not sections:
        print(f"  └─ (空白角色卡)")
        print()
        print(f"  ╚═══")
        print()
        print(f"  编辑: python novel.py character edit {name} <字段> <值>")
        print(f"  例如: python novel.py character edit {name} core 沉稳")
        print(f"        python novel.py character edit {name} identity 外门弟子")
        print(f"        python novel.py character edit {name} relationship 苏晚晴:知己")
        return

    idx = 0
    for sec in sections:
        is_first = (idx == 0)
        is_last = (idx == len(sections) - 1)
        prefix = "  ┌─ " if is_first else ("  └─ " if is_last else "  ├─ ")
        idx += 1

        if sec == "identity":
            print(f"{prefix}【身份】")
            if role_v:
                print(f"  │  定位: {role_v}")
            if identity_v:
                print(f"  │  身份: {identity_v}")
            if ability_v:
                print(f"  │  能力: {ability_v}")

        elif sec == "personality":
            print(f"{prefix}【性格】")
            for f in PERSONALITY_FIELDS:
                val = personality.get(f, "")
                if val:
                    print(f"  │  {f}: {val}")
            if desc_v:
                print(f"  │  描述: {desc_v}")

        elif sec == "behavior":
            print(f"{prefix}【做事风格】")
            for f in BEHAVIOR_FIELDS:
                val = behavior.get(f, "")
                if isinstance(val, list):
                    if val:
                        print(f"  │  {f}: {', '.join(val)}")
                elif val:
                    print(f"  │  {f}: {val}")

        elif sec == "voice":
            print(f"{prefix}【声纹】")
            for f in VOICE_CARD_FIELDS:
                val = voice.get(f, "")
                if val:
                    print(f"  │  {f}: {_render_field(f, val)}")

        elif sec == "relationship":
            print(f"{prefix}【关系】")
            for pair in rel_v.split(","):
                pair = pair.strip()
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    print(f"  │  {k.strip()}: {v.strip()}")
                else:
                    print(f"  │  {pair}")

        elif sec == "arc":
            print(f"{prefix}【成长弧】")
            if arc_v:
                print(f"  │  弧线: {arc_v}")
            if mot_v:
                print(f"  │  动机: {mot_v}")

        elif sec == "meta":
            print(f"{prefix}【元数据】")
            if alias_v:
                print(f"     别名: {alias_v}")
            if tags_v:
                print(f"     标签: {tags_v}")

    print()
    print(f"  ╚═══")
    print()
    print(f"  编辑: python novel.py character edit {name} <字段> <值>")
    print(f"  例如: python novel.py character edit {name} core 沉稳")
    print(f"        python novel.py character edit {name} identity 外门弟子")
    print(f"        python novel.py character edit {name} relationship 苏晚晴:知己")


def _char_create(name: str):
    """创建默认角色卡（JSON + DB 同步创建）."""
    card = get_character_card(PROJECT_ROOT, name)
    if card:
        print(f"  角色「{name}」已存在，将被覆盖")
    card = _new_empty_card(name)
    ok = save_character_card(PROJECT_ROOT, name, card)
    # 同时确保 DB 行存在
    _ensure_char_db_row(PROJECT_ROOT, name)
    if ok:
        print(f"  ✅ 已创建角色卡「{name}」")
        print(f"  查看: python novel.py character show {name}")
        print(f"  编辑: python novel.py character edit {name} <字段> <值>")
    else:
        print(f"  ❌ 创建失败（无法确定当前 slot）")


def _char_delete(name: str):
    """删除角色卡（JSON + DB 同步删除）."""
    card = get_character_card(PROJECT_ROOT, name)
    if not card:
        print(f"  未找到角色「{name}」")
        return
    ok = delete_voice_card(PROJECT_ROOT, name)
    delete_char_db_row(PROJECT_ROOT, name)  # 标记 DB 行删除
    if ok:
        print(f"  ✅ 已删除角色卡「{name}」")
    else:
        print(f"  ❌ 删除失败")


def _char_edit(name: str, field: str, value: str):
    """编辑角色卡指定字段（自动路由到 JSON 或 DB）."""
    card = get_character_card(PROJECT_ROOT, name)
    if not card:
        print(f"  未找到角色「{name}」")
        print(f"  先创建: python novel.py character create {name}")
        return

    # 检查是否为 DB 字段
    if field in DB_CHAR_FIELD_NAMES_EXT:
        ok = save_char_db_field(PROJECT_ROOT, name, field, value)
        if ok:
            print(f"  ✅ 已更新「{name}」的 {field} = {value}")
        else:
            print(f"  ❌ 保存失败（DB 不可用）")
        return

    # 解析字段路径: core, voice.dialect, personality.decision_style 等
    parts = field.split(".")
    if len(parts) == 1:
        # 自动匹配所属分组
        sub_field = parts[0]
        found = False
        for group_name, group_fields in [("voice", VOICE_CARD_FIELDS),
                                          ("personality", PERSONALITY_FIELDS),
                                          ("behavior", BEHAVIOR_FIELDS)]:
            if sub_field in group_fields:
                if sub_field == "habits":
                    card[group_name][sub_field] = [v.strip() for v in value.split(",") if v.strip()]
                else:
                    card[group_name][sub_field] = value
                found = True
                break
        if not found:
            print(f"  ❌ 未知字段「{field}」")
            all_fields = VOICE_CARD_FIELDS + PERSONALITY_FIELDS + BEHAVIOR_FIELDS + DB_CHAR_FIELD_NAMES_EXT
            print(f"  可用字段: {' '.join(all_fields)}")
            return
    elif len(parts) == 2:
        group, sub_field = parts
        if group not in card or sub_field not in card[group]:
            print(f"  ❌ 未知字段路径「{field}」")
            return
        if sub_field == "habits":
            card[group][sub_field] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            card[group][sub_field] = value
    else:
        print(f"  ❌ 字段路径格式不正确: {field}")
        return

    ok = save_character_card(PROJECT_ROOT, name, card)
    if ok:
        print(f"  ✅ 已更新「{name}」的 {field} = {value}")
    else:
        print(f"  ❌ 保存失败")


def _char_outline_check(create_missing: bool = False):
    """从大纲检查所有角色的角色卡状态."""
    title, content, ch_count = _get_outline_content()
    if not title:
        print("  ⛔ 当前没有激活的大纲")
        return

    print(f"  📋 大纲: {title} ({ch_count} 章)")
    print()

    # 提取角色名
    extracted_names = _extract_chinese_names(content)
    db_chars = _get_db_characters()
    db_names = {c["name"] for c in db_chars}
    for c in db_chars:
        alias = c.get("alias", "")
        if alias:
            for a in alias.split(","):
                a = a.strip()
                if a:
                    db_names.add(a)

    all_chars = extracted_names | db_names
    if not all_chars:
        print("  ⚠️  大纲中未检测到角色名")
        return

    # 获取现有角色卡
    cards = list_character_cards(PROJECT_ROOT)
    card_map = {c.get("name", ""): c for c in cards}
    card_set = set(card_map.keys())

    has_card = sorted(all_chars & card_set)
    missing = sorted(all_chars - card_set)

    print(f"  🎭 检测到 {len(all_chars)} 个角色:")
    print()

    for name in sorted(all_chars):
        source = []
        if name in extracted_names:
            source.append("大纲")
        if name in db_names:
            source.append("DB")
        src_tag = f"[{'/'.join(source)}]"

        if name in card_set:
            cc = card_map[name]
            p = cc.get("personality", {})
            b = cc.get("behavior", {})
            core = p.get("core", "") or "未设"
            soc = b.get("social_style", "") or "未设"
            has_personality = bool(p.get("core") or p.get("decision_style"))
            has_behavior = bool(b.get("social_style") or b.get("stress_response"))
            tags = []
            if has_personality:
                tags.append("性格")
            if has_behavior:
                tags.append("做事")
            tag_str = f"({'/'.join(tags)})" if tags else "(仅声纹)"
            print(f"    ✅ {name:8s} {src_tag:12s} 性格:{core:6s} 社交:{soc:6s} {tag_str}")
        else:
            print(f"    ❌ {name:8s} {src_tag:12s} 无角色卡")

    print()

    if missing:
        print(f"  ⚠️  {len(missing)} 个角色尚未创建:")
        for name in missing:
            print(f"     python novel.py character create {name}")
        print()

        if create_missing:
            created = 0
            for name in missing:
                ok = save_character_card(PROJECT_ROOT, name, _new_empty_card(name))
                if ok:
                    created += 1
            print(f"  ✅ 已自动创建 {created}/{len(missing)} 个角色的默认卡")
            # 重新计算
            cards = list_character_cards(PROJECT_ROOT)
            card_map = {c.get("name", ""): c for c in cards}
            card_set = set(card_map.keys())
            has_card = sorted(all_chars & card_set)
            missing = sorted(all_chars - card_set)
        else:
            print(f"  💡 加 --create 自动创建默认角色卡")
    else:
        print("  ✅ 所有角色均已配置角色卡")

    extra = db_names - extracted_names
    if extra:
        print()
        print(f"  📌 DB 中有但大纲中未出现的角色（可能已过时）:")
        for name in sorted(extra):
            print(f"     {name}")

    print()
    current_set = get_active_voice_card_set(PROJECT_ROOT)
    print(f"  📁 当前卡组: {current_set}")
    cov = round(len(has_card) / len(all_chars) * 100) if all_chars else 0
    print(f"  📊 角色卡覆盖率: {len(has_card)}/{len(all_chars)} ({cov}%)")


# ── 关系管理 ──

def _char_relate(a: str, b: str, rel_type: str):
    ok = set_relation(PROJECT_ROOT, a, b, rel_type)
    if ok:
        print(f"  ✅ {a} — {b} : {rel_type}")
    else:
        print(f"  ❌ 设置失败（DB 不可用）")


def _char_unrelate(a: str, b: str):
    ok = delete_relation(PROJECT_ROOT, a, b)
    if ok:
        print(f"  ✅ 已删除 {a} — {b} 的关系")
    else:
        print(f"  ❌ 未找到该关系")


def _char_relation_graph():
    rels = list_relations(PROJECT_ROOT)
    if not rels:
        print("  当前小说无角色关系数据")
        print("  设置: python novel.py character relate <角色A> <角色B> <关系>")
        return
    chars = set()
    for r in rels:
        chars.add(r["char_a"])
        chars.add(r["char_b"])
    print(f"  📊 角色关系图谱（{len(rels)} 条关系，{len(chars)} 个角色）")
    print()
    print(f"  {'角色':8s} {'关系数':6s} {'关系列表'}")
    print(f"  {'-'*8} {'-'*6} {'-'*40}")
    for c in sorted(chars):
        my_rels = [r for r in rels if r["char_a"] == c or r["char_b"] == c]
        other = [(r["char_b"] if r["char_a"] == c else r["char_a"], r["type"]) for r in my_rels]
        parts = [f"{o[0]}({o[1]})" for o in other]
        print(f"  {c:8s} {len(my_rels):6d} {' '.join(parts)}")


# ── 导入导出 ──

def _char_export(name: str, output_path: str = ""):
    card = get_character_card(PROJECT_ROOT, name)
    if not card:
        print(f"  未找到角色「{name}」")
        return
    if not output_path:
        output_path = f"{name}.json"
    ok = export_char_card(PROJECT_ROOT, name, output_path)
    if ok:
        print(f"  ✅ 已导出「{name}」到 {output_path}")
    else:
        print(f"  ❌ 导出失败")


def _char_import(input_path: str):
    if not Path(input_path).exists():
        print(f"  ❌ 文件不存在: {input_path}")
        return
    ok = import_char_card(PROJECT_ROOT, input_path)
    if ok:
        print(f"  ✅ 已导入角色卡: {input_path}")
    else:
        print(f"  ❌ 导入失败（格式不正确或角色名缺失）")


# ── 聚焦状态 ──

def _char_focus(name: str, state: str):
    if state not in FOCUS_STATE_CHOICES:
        print(f"  ❌ 状态必须是 {'/'.join(FOCUS_STATE_CHOICES)}")
        return
    ok = set_focus_state(PROJECT_ROOT, name, state)
    if ok:
        print(f"  ✅ 「{name}」聚焦状态 → {state}")
    else:
        print(f"  ❌ 设置失败")


# ── 弧线进度检查 ──

def _char_arc_check():
    import sqlite3
    ws_dir = PROJECT_ROOT / "workspace"
    reg_f = ws_dir / "registry.json"
    if not reg_f.exists():
        print("  没有活跃工作区")
        return
    reg = json.loads(reg_f.read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    if not active:
        print("  没有活跃 slot")
        return
    slot_db = ws_dir / active / "novel.db"
    if not slot_db.exists():
        print("  数据库不存在")
        return
    conn = sqlite3.connect(str(slot_db))
    ch_count = conn.execute("SELECT COUNT(*) FROM chapters WHERE status='ingested'").fetchone()[0]
    chars = conn.execute(
        "SELECT name, arc, motivation, focus_state FROM characters "
        "WHERE status='active' AND (arc != '' OR motivation != '')"
    ).fetchall()
    conn.close()
    if not chars:
        print("  没有角色设置弧线或动机")
        return
    print(f"  📊 弧线进度检查（已写 {ch_count} 章）")
    for c in chars:
        name = c[0]; arc = c[1] or ""; mot = c[2] or ""; foc = c[3] or "活跃"
        progress = "✓" if arc else "—"
        mot_ok = "✓" if mot else "—"
        ftag = f" [{foc}]" if foc != "活跃" else ""
        arc_short = (arc[:40] + "…") if len(arc) > 40 else arc
        mot_short = (mot[:30] + "…") if len(mot) > 30 else mot
        print(f"  {name:8s} 弧:{progress} 动机:{mot_ok}{ftag}")
        if arc: print(f"         弧线: {arc_short}")
        if mot: print(f"         动机: {mot_short}")


# ── 故事合同同步 ──

def _char_sync_story():
    cards = list_character_cards(PROJECT_ROOT)
    if not cards:
        print("  当前小说无角色卡")
        return
    ws_dir = PROJECT_ROOT / "workspace"
    reg = json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    story_dir = (ws_dir / active / ".story") if active else (PROJECT_ROOT / ".story")
    mem_dir = story_dir / "memory"
    if not mem_dir.exists():
        print(f"  ⚠️  故事合同未初始化，请先运行: python novel.py story init")
        return
    char_list = []
    for c in cards:
        name = c.get("name", "")
        db_row = get_char_db_row(PROJECT_ROOT, name)
        entry = {"name": name}
        p = c.get("personality", {})
        if p.get("core"):
            entry["personality"] = p["core"]
        if db_row:
            for f in ["role", "identity", "ability", "relationship",
                       "arc", "motivation", "alias"]:
                v = db_row.get(f, "")
                if v:
                    entry[f] = v
        char_list.append(entry)
    char_file = mem_dir / "characters.json"
    char_file.write_text(json.dumps(char_list, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"  ✅ 已同步 {len(char_list)} 个角色到故事合同")
    print(f"     路径: {char_file}")


# ── 综合风格检查 ──

def _char_style_check(chapter_no: str, intensity: str = "normal"):
    """运行综合角色风格检测（6项弹性检查）。"""
    # 找章节文件
    ch_path = _resolve_chapter_path(chapter_no)
    if not ch_path:
        print(f"  ❌ 找不到第{chapter_no}章文件")
        return
    content = Path(ch_path).read_text(encoding="utf-8")
    from src.guards.human_texture.voice_diversity_guard import run_character_style_check
    result = run_character_style_check(content, int(chapter_no), PROJECT_ROOT, intensity)
    print(f"  📊 角色风格检测 — 第{chapter_no}章 [{intensity}]")
    print(f"     评分: {result['score']}/100 | 状态: {result['status']}")
    print()
    for f in result.get("findings", []):
        lvl = f.get("level", "INFO")
        chk = f.get("check", "")
        msg = f.get("message", "")
        sug = f.get("suggestion", "")
        icon = {"WARN": "⚠️ ", "INFO": "💡", "FAIL": "❌ "}.get(lvl, "   ")
        print(f"  {icon}[{chk}] {msg}")
        if sug:
            print(f"         → {sug}")

def _char_chapters(name: str):
    """查角色在哪些章节出场了。"""
    import sqlite3
    ws_dir = PROJECT_ROOT / "workspace"
    reg_f = ws_dir / "registry.json"
    if not reg_f.exists():
        print("  没有活跃工作区")
        return
    reg = json.loads(reg_f.read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    if not active:
        return
    slot_db = ws_dir / active / "novel.db"
    if not slot_db.exists():
        print("  数据库不存在")
        return
    conn = sqlite3.connect(str(slot_db))
    results = []

    # 1. 从 chapter_plans.character_focus 查
    focus_rows = conn.execute(
        "SELECT DISTINCT chapter_no FROM chapter_plans "
        "WHERE character_focus LIKE ? ORDER BY chapter_no",
        (f"%{name}%",)
    ).fetchall()

    # 2. 从 chapters.content 全文搜索
    content_rows = conn.execute(
        "SELECT DISTINCT chapter_no FROM chapters WHERE content LIKE ? ORDER BY chapter_no",
        (f"%{name}%",)
    ).fetchall()

    conn.close()

    focus_chs = {r[0] for r in focus_rows}
    content_chs = {r[0] for r in content_rows}
    all_chs = sorted(focus_chs | content_chs)

    if not all_chs:
        print(f"  「{name}」在所有已入库章节中均未出场")
        return

    print(f"  📖 「{name}」出场章节（共 {len(all_chs)} 章）:")
    print()
    for ch in all_chs:
        tags = []
        if ch in focus_chs:
            tags.append("聚焦")
        if ch in content_chs:
            tags.append("出现")
        print(f"    第{ch}章  {'/'.join(tags)}")


def cmd_character(args):
    """Dispatch character subcommands."""
    action = getattr(args, "character_action", None)

    if action == "list":
        _char_list()

    elif action == "show":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py character show <角色名>")
            return
        _char_show(name)

    elif action == "create":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py character create <角色名>")
            return
        _char_create(name)

    elif action == "delete":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py character delete <角色名>")
            return
        _char_delete(name)

    elif action == "edit":
        name = getattr(args, "character_name", "")
        field = getattr(args, "field", "")
        value = getattr(args, "value", "")
        if not name or not field or value is None:
            print("  用法: python novel.py character edit <角色名> <字段> <值>")
            print()
            print("  声纹字段:", " ".join(VOICE_CARD_FIELDS))
            print("  性格字段:", " ".join(PERSONALITY_FIELDS))
            print("  做事字段:", " ".join(BEHAVIOR_FIELDS))
            print()
            print("  示例: python novel.py character edit 韩烈 core 沉稳")
            print("        python novel.py character edit 韩烈 habits 咬嘴唇,搓手指")
            return
        _char_edit(name, field, value)

    elif action == "outline-check":
        create_flag = getattr(args, "create_missing", False)
        _char_outline_check(create_missing=create_flag)

    elif action == "relate":
        a = getattr(args, "char_a", "")
        b = getattr(args, "char_b", "")
        t = getattr(args, "relation_type", "")
        if a and b and t:
            _char_relate(a, b, t)
        else:
            print("  用法: python novel.py character relate <角色A> <角色B> <关系>")

    elif action == "unrelate":
        a = getattr(args, "char_a", "")
        b = getattr(args, "char_b", "")
        if a and b:
            _char_unrelate(a, b)
        else:
            print("  用法: python novel.py character unrelate <角色A> <角色B>")

    elif action == "relation-graph":
        _char_relation_graph()

    elif action == "export":
        name = getattr(args, "character_name", "")
        out = getattr(args, "output_path", "")
        if name:
            _char_export(name, out)
        else:
            print("  用法: python novel.py character export <角色名> [文件路径]")

    elif action == "import":
        fp = getattr(args, "input_path", "")
        if fp:
            _char_import(fp)
        else:
            print("  用法: python novel.py character import <文件路径>")

    elif action == "focus":
        name = getattr(args, "character_name", "")
        state = getattr(args, "focus_state", "")
        if name and state:
            _char_focus(name, state)
        else:
            print(f"  用法: python novel.py character focus <角色名> {'/'.join(FOCUS_STATE_CHOICES)}")

    elif action == "arc-check":
        _char_arc_check()

    elif action == "sync-story":
        _char_sync_story()

    elif action == "chapters":
        name = getattr(args, "character_name", "")
        if name:
            _char_chapters(name)
        else:
            print("  用法: python novel.py character chapters <角色名>")

    elif action == "check":
        ch = getattr(args, "chapter_no", "")
        inten = getattr(args, "intensity", "normal")
        if ch:
            _char_style_check(ch, inten)
        else:
            print("  用法: python novel.py character check <章节号> [--intensity light|normal|strict]")

    else:
        print("用法: python novel.py character {list|show|create|delete|edit|"
              "relate|unrelate|relation-graph|export|import|focus|arc-check|outline-check}")
        print()
        print("  list                    — 列出所有角色卡")
        print("  show <角色名>            — 查看完整角色卡")
        print("  create <角色名>          — 创建默认角色卡")
        print("  delete <角色名>          — 删除角色卡")
        print("  edit <角色名> <字段> <值>  — 编辑角色字段")
        print("  relate <A> <B> <关系>    — 设置角色关系")
        print("  unrelate <A> <B>         — 删除角色关系")
        print("  relation-graph           — 文本关系图谱")
        print("  export <角色名> [文件路径] — 导出角色卡")
        print("  import <文件路径>         — 导入角色卡")
        print("  focus <角色名> <状态>     — 设置聚焦状态")
        print("  arc-check                — 弧线进度检查")
        print("  outline-check            — 从大纲检查角色卡状态")
        print("  outline-check --create   — 检查 + 自动创建缺失角色卡")
        print("  chapters <角色名>        — 查角色出场章节")
        print()
        print("  字段列表:")
        print("    声纹:", " ".join(VOICE_CARD_FIELDS))
        print("    性格:", " ".join(PERSONALITY_FIELDS))
        print("    做事:", " ".join(BEHAVIOR_FIELDS))
        print("    身份:", " ".join(DB_CHAR_FIELD_NAMES_EXT))
