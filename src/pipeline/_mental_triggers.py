"""Per-slot 精神状态触发词配置加载。

通用引擎不内置任何具体小说的触发词。需要该功能的作品，在自己的 slot 目录放一个
``mental_triggers.json``，引擎才会启用；缺省则相关检测整段 no-op。

文件格式（均为可选，给出默认值）::

    {
      "label": "创伤触发",
      "triggers": ["关键词1", "关键词2"],
      "state_threshold": 2,        # >= 则写入 pipeline_state 并提示
      "advise_threshold": 4,       # >= 则建议加一段解离/解压戏
      "window": 5,                 # 跨章窗口长度（章）
      "window_total_threshold": 8  # 窗口内累计命中 >= 则提示
    }
"""
from __future__ import annotations

import json
from typing import Any, Optional

from src.utils.error_handling import log_optional_failure

_DEFAULTS = {
    "label": "精神触发",
    "state_threshold": 2,
    "advise_threshold": 4,
    "window": 5,
    "window_total_threshold": 8,
}


def load_mental_triggers(app) -> Optional[dict[str, Any]]:
    """读取当前 slot 的 mental_triggers.json。

    返回归一化后的 dict（含默认阈值）；文件不存在、无 active slot、或 triggers 为空时
    返回 None，调用方据此跳过整段逻辑。
    """
    active_slot = getattr(app, "active_slot", None)
    workspace_root = getattr(app, "workspace_root", None)
    if not active_slot or workspace_root is None:
        return None

    cfg_path = workspace_root / active_slot / "mental_triggers.json"
    if not cfg_path.exists():
        return None

    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        log_optional_failure("load_mental_triggers", exc)
        return None

    if not isinstance(raw, dict):
        return None
    triggers = raw.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        return None

    cfg = dict(_DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
    cfg["triggers"] = [str(t) for t in triggers if str(t).strip()]
    if not cfg["triggers"]:
        return None
    return cfg
