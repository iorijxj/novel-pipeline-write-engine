"""
test_ingest_title.py — CODE_REVIEW #17

_resolve_chapter_title 的标题解析：正文标题优先，文件名分隔符可选，stem 兜底。
"""
from src.pipeline.ingest import _resolve_chapter_title


def test_underscore_filename():
    assert _resolve_chapter_title("第1章_山村的清晨.txt", "正文无标题行") == "山村的清晨"


def test_filename_without_underscore():
    # 无下划线也能解析（旧正则会退化到 stem）
    assert _resolve_chapter_title("第1章山村的清晨.txt", "正文无标题行") == "山村的清晨"


def test_content_title_overrides_filename():
    content = "# 第1章 真正的标题\n\n正文……"
    assert _resolve_chapter_title("第1章_文件名标题.txt", content) == "真正的标题"


def test_content_title_with_chinese_numeral():
    content = "# 第一章 玄之又玄\n正文"
    assert _resolve_chapter_title("第1章随便.txt", content) == "玄之又玄"


def test_falls_back_to_stem_when_no_title():
    # 文件名不匹配 `第N章...` 且正文无标题 → stem
    assert _resolve_chapter_title("draft_chapter.txt", "正文无标题") == "draft_chapter"


def test_padded_chapter_number_filename():
    assert _resolve_chapter_title("第01章_序幕.txt", "正文") == "序幕"
