"""统一的 SQLite 连接 helper。

全仓库的 ``sqlite3.connect`` 调用走这里，确保：

- WAL 日志模式：支持读写并发（多个 pre/post/ingest 进程同时跑）
- timeout=30s：默认 5s 在批量章节流水线下会锁失败
- synchronous=NORMAL：WAL 推荐组合（耐久 vs 性能折中）
- foreign_keys=ON：让外键约束真的生效（SQLite 默认关闭）

只读连接走 URI mode=ro 路径，避免 WAL 写文件。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def connect_sqlite(
    db_path: PathLike,
    *,
    read_only: bool = False,
    timeout: float = 30.0,
) -> sqlite3.Connection:
    """打开 SQLite 连接，统一应用 WAL + timeout + 外键约束。

    Parameters
    ----------
    db_path : str | Path
        数据库文件路径。
    read_only : bool
        True 时走 URI mode=ro，连接只读。WAL pragma 不生效（只读连接不写 journal）。
    timeout : float
        锁等待秒数，默认 30s。
    """
    path_str = str(db_path)
    if read_only:
        conn = sqlite3.connect(f"file:{path_str}?mode=ro", uri=True, timeout=timeout)
        # 只读连接不需要设置 journal_mode / synchronous（不会写）
        return conn

    conn = sqlite3.connect(path_str, timeout=timeout)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.DatabaseError:
        # 极端情况下（如刚创建尚未初始化的空文件）pragma 可能不可用；忽略
        pass
    return conn
