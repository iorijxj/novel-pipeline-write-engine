"""
test_pre_helpers.py — CODE_REVIEW #10

run_pre 拆出的可独立测试小函数的针对性单测。随增量抽取逐步补充。
"""
import sqlite3
import types

from src.pipeline.pre import (
    _pre_load_genre,
    _pre_write_context_pack,
    _pre_print_constraints,
)


def _novels_cur(genre_value):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE novels(id INTEGER PRIMARY KEY, genre TEXT)")
    conn.execute("INSERT INTO novels(id, genre) VALUES(1, ?)", (genre_value,))
    return conn.cursor()


def test_pre_load_genre_returns_value():
    cur = _novels_cur("xianxia")
    assert _pre_load_genre(cur, 1, []) == "xianxia"


def test_pre_load_genre_empty_when_null():
    cur = _novels_cur(None)
    assert _pre_load_genre(cur, 1, []) == ""


def test_pre_load_genre_missing_row_returns_empty():
    cur = _novels_cur("scifi")
    assert _pre_load_genre(cur, 999, []) == ""  # 无此 novel_id


def test_pre_load_genre_swallows_sql_error_and_logs():
    conn = sqlite3.connect(":memory:")  # 无 novels 表 → OperationalError
    log = []
    assert _pre_load_genre(conn.cursor(), 1, log) == ""
    assert any("genre lookup failed" in e for e in log)


def _fake_app(tmp_path):
    return types.SimpleNamespace(
        exports_root=tmp_path / "exports",
        volume_no=1,
        wc_default={"best_min": 2000, "best_max": 3000, "min": 1500, "max": 4000},
    )


def test_pre_write_context_pack_writes_file_with_skeleton(tmp_path):
    app = _fake_app(tmp_path)
    vol = {"planned_title": "山河卷"}
    ch_plan = {
        "planned_title": "初遇",
        "chapter_goal": "建立目标",
        "conflict_point": "门派纷争",
        "ending_hook_direction": "悬念收束",
    }
    pack_path = _pre_write_context_pack(app, 3, vol, ch_plan)
    assert pack_path.exists()
    text = pack_path.read_text(encoding="utf-8")
    assert "写作上下文包-第3章" in text
    assert "2000-3000" in text          # best range
    assert "标题骨架" in text and "初遇" in text


def test_pre_write_context_pack_no_skeleton_when_ch_plan_none(tmp_path):
    app = _fake_app(tmp_path)
    pack_path = _pre_write_context_pack(app, 1, None, None)
    assert pack_path.exists()
    text = pack_path.read_text(encoding="utf-8")
    assert "写作上下文包-第1章" in text
    assert "标题骨架" not in text        # ch_plan 为空 → 无骨架段


def test_pre_print_constraints_maps_thresholds_and_pacing(capsys):
    preset = {
        "water_density_min": 60,
        "conflict_pressure_min": 55,
        "pacing": {"focus_deltas": ["conflict_delta", "hook_delta"]},
    }
    _pre_print_constraints("xianxia", preset)
    out = capsys.readouterr().out
    assert "写作约束 [xianxia]" in out
    assert "注水阈值=60" in out and "冲突压力=55" in out
    assert "冲突 → 钩子" in out          # focus_deltas 标签映射


def test_pre_print_constraints_empty_preset_prints_nothing(capsys):
    _pre_print_constraints("xianxia", {})
    assert capsys.readouterr().out == ""   # 空 preset → 整块跳过


def test_run_pre_threads_app_project_root_to_loaders(tmp_path, monkeypatch):
    """回归：run_pre 必须把 app.project_root（隔离/临时根）传给下游读取器，
    而不是重新用 find_project_root(__file__) 取到仓库根。"""
    from src.pipeline import pre

    recorded = {}

    def _rec_prev_chapter(cur, nid, app, ch, prev_ch, project_root, log):
        recorded["prev_chapter"] = project_root
        return ("", None)

    def _rec_story_health(ch, project_root, log):
        recorded["story_health"] = project_root
        return (None, None, None, [])

    def _rec_genre_preset(app, genre, prev_ch, project_root):
        recorded["genre_preset"] = project_root
        return (None, None)

    def _rec_relations(project_root, chars, ch):
        recorded["relations"] = project_root

    # in-memory 连接：仅需支撑末尾 novel_logs 写入
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE novel_logs(id INTEGER PRIMARY KEY, action TEXT, "
        "target_type TEXT, detail TEXT)"
    )

    # 目标读取器：记录传入的 root
    monkeypatch.setattr(pre, "_pre_load_prev_chapter", _rec_prev_chapter)
    monkeypatch.setattr(pre, "_pre_load_story_health", _rec_story_health)
    monkeypatch.setattr(pre, "_pre_load_genre_preset_texture", _rec_genre_preset)
    monkeypatch.setattr(pre, "_pre_character_relations", _rec_relations)

    # 其余重型辅助：替换为最小桩，使 run_pre 能跑完
    monkeypatch.setattr(pre, "ensure_tables", lambda app: None)
    monkeypatch.setattr(pre, "connect", lambda app: conn)
    monkeypatch.setattr(pre, "_get_novel_id", lambda cur, app: 1)
    monkeypatch.setattr(pre, "_pre_fts_health", lambda app, log: None)
    monkeypatch.setattr(pre, "_pre_load_genre", lambda cur, nid, log: "xianxia")
    monkeypatch.setattr(pre, "_pre_load_skeleton", lambda *a: ({}, {}))
    monkeypatch.setattr(pre, "_pre_check_volume_sequence", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_load_characters", lambda cur, nid, log: [])
    monkeypatch.setattr(pre, "_pre_load_voice_mental", lambda app, log: ({}, {}))
    monkeypatch.setattr(pre, "_pre_print_overview", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_worldbuilding_reminder", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_plot_thread_reminder", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_reader_promise_reminder", lambda cur, nid, op: op)
    monkeypatch.setattr(pre, "_pre_write_context_pack", lambda *a: tmp_path / "pack.json")
    monkeypatch.setattr(pre, "_build_context_injection", lambda *a, **k: "")
    monkeypatch.setattr(pre, "_pre_print_task_card", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_print_story_contract", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_print_constraints", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_print_prev_texture", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_print_mental_triggers", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_print_characters_onstage", lambda *a: None)
    monkeypatch.setattr(pre, "_pre_autofix_rules", lambda *a: None)

    app = types.SimpleNamespace(
        project_root=tmp_path,
        novel_title="T",
        state_dir=tmp_path / "state",
    )

    # chapter_no=1 → 最近3章 SELECT 循环为空，无需额外表
    pre.run_pre(1, context=app)

    assert recorded["prev_chapter"] == tmp_path
    assert recorded["story_health"] == tmp_path
    assert recorded["genre_preset"] == tmp_path
    assert recorded["relations"] == tmp_path
