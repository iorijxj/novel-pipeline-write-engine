# src/__init__.py
# Version 单一来源：root VERSION 文件 → version.get_version()
import sys as _sys
from pathlib import Path as _Path

_REPO = _Path(__file__).resolve().parent.parent
if str(_REPO) not in _sys.path:
    _sys.path.insert(0, str(_REPO))

try:
    from version import get_version as _get_version
    __version__ = _get_version()
except Exception:
    __version__ = "unknown"
