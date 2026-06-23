#!/usr/bin/env python3
"""Database initialization & migration helpers for ProseForge.

Schema 权威源：``database/schema.sql``。新建 novel.db 时整份 schema 被一次性应用。

迁移流程：
- 增量改动放在 ``database/migrations/`` 下，文件名形如 ``NNNN_short_description.sql``
- 按文件名字典序逐个应用；已应用的迁移记录在 ``schema_migrations`` 表里，幂等
- 当前已有迁移：``0001_arc_character_and_relationship_tables.sql`` /
  ``0002_fix_novel_chunk_fts_schema.sql``
- 新增迁移：写一个 ``NNNN_xxx.sql`` 放进 migrations 目录即可，下一次 ``init_db``
  调用时会自动应用

入口：``init_db(db_path, schema_path, migrations)``——SlotManager 创建新 slot 时调它。
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from src.utils.config_utils import find_project_root, load_json_config
from src.db._conn import connect_sqlite


def load_config(config_path=None, project_root=None):
    return load_json_config(config_path, project_root)


def find_schema(start: str | Path | None) -> Path | None:
    project_root = find_project_root(start)
    schema = project_root / "database" / "schema.sql"
    return schema if schema.exists() else None


def find_migrations(start: str | Path | None):
    """扫描 ``database/migrations/`` 下的 ``*.sql`` 文件，返回 [(filename, path)] 列表。

    按文件名字典序排序——这意味着新增迁移**必须**按 ``NNNN_...`` 数字前缀命名以保证顺序。
    目录不存在时返回 ``[]``（首次初始化场景）。
    """
    project_root = find_project_root(start)
    migrations_dir = project_root / "database" / "migrations"
    if not migrations_dir.exists():
        return []
    return [(path.name, path) for path in sorted(migrations_dir.glob("*.sql"))]


def ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            applied_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def run_migrations(conn: sqlite3.Connection, migrations) -> bool:
    """Run pending migrations in order, tracking in schema_migrations."""
    ensure_schema_migrations(conn)
    cur = conn.cursor()
    cur.execute("SELECT filename FROM schema_migrations")
    applied = {row[0] for row in cur.fetchall()}

    for filename, filepath in migrations:
        if filename in applied:
            continue
        print(f"  [MIG] {filename}...")
        sql = Path(filepath).read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
            cur.execute("INSERT INTO schema_migrations(filename) VALUES(?)", (filename,))
            conn.commit()
            print(f"  [OK]  {filename}")
        except Exception as exc:
            conn.rollback()
            print(f"  [FAIL] {filename}: {exc}")
            return False
    return True


def init_db(db_path, schema_path, migrations=None):
    if migrations is None:
        migrations = []

    db_path = Path(db_path)
    schema_path = Path(schema_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect_sqlite(db_path)
    try:
        schema_sql = schema_path.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()

        if not run_migrations(conn, migrations):
            conn.close()
            return False

        cur = conn.cursor()
        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
              AND name NOT LIKE '%_fts_%'
            ORDER BY name
            """
        )
        tables = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts' ORDER BY name")
        fts_tables = [row[0] for row in cur.fetchall()]
        conn.close()

        print(f"\n[OK] 数据库初始化完成: {db_path}")
        print(f"  普通表 ({len(tables)}): {', '.join(tables)}")
        if fts_tables:
            print(f"  FTS5 索引 ({len(fts_tables)}): {', '.join(fts_tables)}")
        return True
    except Exception as exc:
        conn.close()
        print(f"[FAIL] 数据库初始化失败: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a ProseForge SQLite database.")
    parser.add_argument("--config")
    parser.add_argument("--db-path")
    parser.add_argument("--project-root")
    args = parser.parse_args()

    cfg = load_config(args.config, args.project_root)
    db_path = args.db_path or cfg.get("db_path")
    schema = find_schema(args.project_root or Path.cwd())
    migrations = find_migrations(args.project_root or Path.cwd())
    if schema is None:
        print("[FAIL] database/schema.sql not found")
        return 1
    return 0 if init_db(db_path, schema, migrations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
