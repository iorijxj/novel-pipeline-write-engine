"""test_semantic_contract.py — 语义保全契约 / 词级预检 / 回执评估"""
import json
import sqlite3

import pytest

from src.db import init_db
from src.pipeline._base import App
from src.pipeline.rewrite import run_accept
from src.pipeline.semantic_contract import (
    build_preservation_contract,
    lexical_precheck,
    read_verdict,
    evaluate_preservation,
    write_review_request,
)


def _clean_orchestrator(monkeypatch):
    """让 guard 复跑返回无问题，隔离出语义保全信号。"""
    monkeypatch.setattr("src.pipeline.guard_orchestrator.run_orchestrated",
                        lambda *a, **k: {"warnings": [], "executed_guards": [], "warning_count": 0})


def _seed_chapter_and_verdict(app, chapters_dir, broken=True):
    """写章文件 + 小改改稿 + host 回执（标某承诺 broken），返回 promise_id。"""
    chapter_file = chapters_dir / "第1章_开端.txt"
    chapter_file.write_text(_SRC, encoding="utf-8")
    revised = _SRC.replace("谁都没有说话", "谁也没有开口")     # 极小改动，角色名保留
    (chapter_file.parent / "chapter_001_revised.txt").write_text(revised, encoding="utf-8")
    contract = build_preservation_contract(app, 1, _SRC)
    promise_id = next(it["id"] for it in contract["items"] if it["dimension"] == "reader_promise")
    verdict = {"chapter_no": 1, "items": [{"id": promise_id,
               "verdict": "broken" if broken else "preserved"}]}
    (chapter_file.parent / "chapter_001_semantic_review.json").write_text(
        json.dumps(verdict, ensure_ascii=False), encoding="utf-8")
    return promise_id


_SRC = (
    "林轩走进大殿，苏瑶站在他身侧。\n\n"
    "他这一战突破金丹，气息陡然不同。\n\n"
    "两人对视一眼，谁都没有说话。"
)


@pytest.fixture
def sem_env(tmp_path, project_root, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {
        "db_path": str(tmp_path / "data" / "test.db"),
        "novels_root": str(tmp_path / "novels"),
        "exports_root": str(tmp_path / "exports"),
        "outputs_root": str(tmp_path / "outputs"),
    }
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    schema = project_root / "database" / "schema.sql"
    init_db.init_db(cfg["db_path"], str(schema), [])

    conn = sqlite3.connect(cfg["db_path"])
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS character_relationships (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             novel_id INTEGER NOT NULL,
             char_a TEXT NOT NULL, char_b TEXT NOT NULL,
             relation_type TEXT DEFAULT '', detail TEXT DEFAULT '',
             UNIQUE(novel_id, char_a, char_b));""")
    conn.execute("INSERT INTO novels(slug, title, genre, status) VALUES(?,?,?,?)",
                 ("demo_novel", "Demo", "fantasy", "writing"))
    nid = conn.execute("SELECT id FROM novels WHERE slug='demo_novel'").fetchone()[0]
    conn.execute("INSERT INTO characters(novel_id, name) VALUES(?,?)", (nid, "林轩"))
    conn.execute("INSERT INTO characters(novel_id, name) VALUES(?,?)", (nid, "苏瑶"))
    conn.execute(
        "INSERT INTO reader_promises(novel_id, promise_title, promise_detail, status, importance) "
        "VALUES(?,?,?,?,?)", (nid, "林轩的身世之谜", "他的来历将在后文揭晓", "open", 5))
    conn.execute(
        "INSERT INTO plot_threads(novel_id, title, thread_type, status, importance) "
        "VALUES(?,?,?,?,?)", (nid, "金丹大会的阴谋", "伏笔", "active", 4))
    conn.execute(
        "INSERT INTO character_relationships(novel_id, char_a, char_b, relation_type, detail) "
        "VALUES(?,?,?,?,?)", (nid, "林轩", "苏瑶", "同盟", "并肩作战"))
    conn.execute(
        """INSERT INTO chapter_plans(novel_id, volume_no, chapter_no, planned_title,
           conflict_point, ending_hook_direction, updated_at)
           VALUES(?,?,?,?,?,?,?)""",
        (nid, 1, 1, "开端", "突破之险", "强敌将至", "2025-01-01 00:00:00"))
    conn.commit()
    conn.close()

    chapters_dir = tmp_path / "novels" / "demo_novel" / "第01卷"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    app = App(cfg, "demo_novel", "Demo", 1, str(chapters_dir),
              project_root=str(tmp_path), config_path=str(tmp_path / "config.json"))
    return {"app": app, "tmp_path": tmp_path, "chapters_dir": chapters_dir}


def test_contract_covers_four_dimensions(sem_env):
    contract = build_preservation_contract(sem_env["app"], 1, _SRC)
    assert contract["available"] is True
    dims = {it["dimension"] for it in contract["items"]}
    assert "reader_promise" in dims
    assert "plot_thread" in dims
    assert "character_relationship" in dims
    assert "canon_fact" in dims          # 突破金丹 → hard claim
    assert "ending_hook" in dims


def test_lexical_precheck_flags_removed_character(sem_env):
    contract = build_preservation_contract(sem_env["app"], 1, _SRC)
    # 改稿删掉两个角色名 → 关系锚点全缺 → likely_broken
    revised = "众人走进大殿。\n\n这一战突破金丹，气息陡然不同。\n\n谁都没有说话。"
    pc = lexical_precheck(contract, revised)
    rel_ids = [it["id"] for it in contract["items"] if it["dimension"] == "character_relationship"]
    assert rel_ids and pc[rel_ids[0]]["likely_broken"] is True


def test_lexical_precheck_clean_when_anchors_kept(sem_env):
    contract = build_preservation_contract(sem_env["app"], 1, _SRC)
    pc = lexical_precheck(contract, _SRC)        # 原样保留
    rel_ids = [it["id"] for it in contract["items"] if it["dimension"] == "character_relationship"]
    assert not pc[rel_ids[0]]["likely_broken"]


def test_evaluate_with_llm_verdict_broken(sem_env):
    contract = build_preservation_contract(sem_env["app"], 1, _SRC)
    pc = lexical_precheck(contract, _SRC)
    promise_id = next(it["id"] for it in contract["items"] if it["dimension"] == "reader_promise")
    verdict = {"chapter_no": 1, "items": [{"id": promise_id, "verdict": "broken"}]}
    ev = evaluate_preservation(contract, pc, verdict, enforce=True)
    assert ev["available"] is True and ev["source"] == "llm"
    assert promise_id in ev["broken"]
    assert ev["enforced"] is True


def test_evaluate_empty_contract_unavailable():
    ev = evaluate_preservation({"items": []}, {}, None)
    assert ev["available"] is False
    assert ev["broken"] == []


def test_build_contract_fail_open_on_missing_novel(tmp_path, project_root, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {"db_path": str(tmp_path / "data" / "t.db"),
           "novels_root": str(tmp_path / "n"), "exports_root": str(tmp_path / "e"),
           "outputs_root": str(tmp_path / "o")}
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    init_db.init_db(cfg["db_path"], str(project_root / "database" / "schema.sql"), [])
    app = App(cfg, "missing_slug", "X", 1, str(tmp_path / "ch"),
              project_root=str(tmp_path), config_path=str(tmp_path / "config.json"))
    contract = build_preservation_contract(app, 1, "正文无硬事实。")
    # 没有 novel_id → DB 维度为空，但 canon 抽取仍跑；不崩
    assert "items" in contract


def test_write_review_request_emits_card_and_template(sem_env, tmp_path):
    contract = build_preservation_contract(sem_env["app"], 1, _SRC)
    pc = lexical_precheck(contract, _SRC)
    jp = tmp_path / "req.json"
    mp = tmp_path / "card.md"
    vp = tmp_path / "verdict.json"
    write_review_request(contract, pc, jp, mp, vp)
    assert jp.exists() and mp.exists()
    payload = json.loads(jp.read_text(encoding="utf-8"))
    assert payload["verdict_template"]["items"]
    assert "verdict" in payload["verdict_template"]["items"][0]
    card = mp.read_text(encoding="utf-8")
    assert "语义保全清单" in card and "preserved|broken|uncertain" in card


def test_read_verdict_handles_missing_and_bad(tmp_path):
    assert read_verdict(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert read_verdict(bad) is None
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"items": [{"id": "x", "verdict": "preserved"}]}), encoding="utf-8")
    assert read_verdict(ok)["items"][0]["id"] == "x"


def test_run_accept_enforce_rejects_on_broken(sem_env, monkeypatch):
    _clean_orchestrator(monkeypatch)
    app = sem_env["app"]
    _seed_chapter_and_verdict(app, sem_env["chapters_dir"], broken=True)
    res = run_accept(1, novel_slug="demo_novel", novel_title="Demo", volume_no=1,
                     ingest=True, enforce_preservation=True, context=app)
    assert res["preservation"]["available"] is True
    assert res["preservation"]["broken"]
    assert res["recommendation"] == "REVISION_REJECTED"
    assert res["ingested"] is False


def test_run_accept_advisory_warns_but_allows(sem_env, monkeypatch):
    _clean_orchestrator(monkeypatch)
    app = sem_env["app"]
    _seed_chapter_and_verdict(app, sem_env["chapters_dir"], broken=True)
    res = run_accept(1, novel_slug="demo_novel", novel_title="Demo", volume_no=1,
                     ingest=False, enforce_preservation=False, context=app)
    # advisory：不因保全破坏而 REJECTED，但带勝告 risk_flag
    assert res["recommendation"] != "REVISION_REJECTED"
    assert any("语义保全" in f for f in res["risk_flags"])
