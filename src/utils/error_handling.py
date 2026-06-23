"""统一的错误处理辅助函数。

两类语义清晰的 helper：

- log_optional_failure(step, exc):
    Optional 步骤（如可选依赖、cache 加载、非关键统计）失败。
    打印一行简洁 WARN，并在 logger.debug 留 traceback。
    用户日常运行**不**应被它打扰。

- log_recoverable_failure(step, exc):
    可恢复但用户必须看见的失败（如 voice_context 加载、报告写入失败、
    数据库统计更新失败）。打印 ERROR 行，logger.warning 留完整 traceback。

这样 pre/post/ingest 里的 50+ try/except 不再每处重复"print + 吞掉"模板，
失败原因也至少存在 logger 里，便于诊断。
"""
from __future__ import annotations

import logging

logger = logging.getLogger("proseforge")


def log_optional_failure(step: str, exc: BaseException) -> None:
    """记录 optional 步骤失败，不中断流程。用户日常看不到 traceback。"""
    print(f"  [WARN] {step}: {type(exc).__name__}: {exc}")
    logger.debug("optional step '%s' failed", step, exc_info=True)


def log_recoverable_failure(step: str, exc: BaseException) -> None:
    """记录可恢复失败，用户**应当**看到。"""
    print(f"  [ERROR] {step}: {type(exc).__name__}: {exc}")
    logger.warning("recoverable step '%s' failed", step, exc_info=True)
