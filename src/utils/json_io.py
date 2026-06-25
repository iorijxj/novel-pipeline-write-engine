"""Atomic JSON file writes — temp file + os.replace, dependency-free.

放在 utils 层（不依赖 pipeline/db），供 db 与 pipeline 共用，避免 db→pipeline 反向依赖。
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def write_json_atomic(path, obj) -> None:
    """把 obj 以 UTF-8 JSON 原子写入 path（写临时文件再 os.replace，避免半写损坏）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))
