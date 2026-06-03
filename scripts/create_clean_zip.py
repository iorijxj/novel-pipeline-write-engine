"""create_clean_zip.py — Package Novel Forge as clean release zip"""
import zipfile, os
from pathlib import Path

src = Path(".")
dst = Path("D:/引擎备份/小说引擎_v0.6.7.zip")

EXCLUDE_DIRS = {"workspace", "exports", "outputs", "novels", "data", "tmp",
                "reports", "node_modules", "__pycache__", ".git", ".pytest_cache",
                "frontend", "api", ".story", "voice_cards"}
EXCLUDE_FILES = {"config.json", "一键启动.bat", "requirements-api.txt", "requirements-rag.txt"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

count = 0
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(str(src)):
        rp = Path(root)
        rel = rp.relative_to(src)
        # 只排除根目录一级的目录，不杀子目录（如 demo/novels 保留）
        if rel == Path("."):
            pass  # root dir, never skip
        elif rel.parent == Path(".") and rel.name in EXCLUDE_DIRS:
            dirs[:] = []
            continue
        # 隐藏目录跳过（.git 已在上层排除）
        dirs[:] = [d for d in dirs if not d.startswith(".") or d == ".github"]
        for file in files:
            if file in EXCLUDE_FILES:
                continue
            if any(file.endswith(sfx) for sfx in EXCLUDE_SUFFIXES):
                continue
            fp = rp / file
            arcname = str(fp.relative_to(src))
            zf.write(str(fp), arcname)
            count += 1

sz = dst.stat().st_size
print(f"Done: {count} files, {sz//1024} KB")
