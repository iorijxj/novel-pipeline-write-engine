import sqlite3

# 上下文提取已统一到 chapter_context.py（ingest 通过 import 复用），故从权威源测试
from src.pipeline.chapter_context import _build_context_injection, _ensure_chapter_contexts_table


def test_context_injection_handles_legacy_database_without_table():
    conn = sqlite3.connect(":memory:")
    try:
        assert _build_context_injection(conn.cursor(), 1, 2) is None
    finally:
        conn.close()


def test_ensure_chapter_contexts_table_upgrades_legacy_database():
    conn = sqlite3.connect(":memory:")
    try:
        _ensure_chapter_contexts_table(conn.cursor())
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chapter_contexts'"
        ).fetchone()
        assert row == ("chapter_contexts",)
    finally:
        conn.close()
