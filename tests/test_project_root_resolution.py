"""
test_project_root_resolution.py — 防止"硬链路"回归。

历史 bug：src/pipeline 下用 Path(__file__).parent.parent 推断根，落到 src/ 而非
仓库根。src/ 没有 workspace/registry.json，导致 slot 感知的解析器静默回退、
绕过工作区隔离（story commits、声纹卡）。这些用例锁定正确行为。
"""
import json
import types

from src.story import resolve_story_dir


def _make_slot_root(tmp_path, slot="slotA"):
    ws = tmp_path / "workspace"
    (ws / slot / ".story").mkdir(parents=True)
    (ws / "registry.json").write_text(
        json.dumps({"active_slot": slot}), encoding="utf-8"
    )
    return tmp_path, ws / slot / ".story"


def test_resolve_story_dir_honors_active_slot(tmp_path):
    root, slot_story = _make_slot_root(tmp_path)
    # 给定真正的仓库根 → 解析到活跃 slot 的 .story
    assert resolve_story_dir(root) == slot_story


def test_resolve_story_dir_wrong_root_misses_slot(tmp_path):
    """传入 src/（无 workspace/）会回退到 <root>/.story，错过活跃 slot。
    这正是旧 parent.parent 写法造成的隔离失效。"""
    _make_slot_root(tmp_path)
    fake_src = tmp_path / "src"
    fake_src.mkdir()
    assert resolve_story_dir(fake_src) == fake_src / ".story"  # 非 slot 目录


def test_post_human_texture_passes_runtime_project_root(tmp_path, monkeypatch):
    """_post_run_human_texture 必须把 app.project_root（运行时根）传给质量层，
    而不是模块级写死的 src/ 根。"""
    from src.pipeline import post

    recorded = {}

    def _fake_guards(content, chapter_no, project_root=None, genre=None, pace_level=None, **kw):
        recorded["project_root"] = project_root
        return {"scores": {}, "status": "ok"}

    # 函数内部 from src.guards.human_texture import run_human_texture_guards
    monkeypatch.setattr(
        "src.guards.human_texture.run_human_texture_guards", _fake_guards
    )

    app = types.SimpleNamespace(project_root=tmp_path)
    args = types.SimpleNamespace(pace=None)
    post._post_run_human_texture(app, "正文", 1, "xianxia", args, {}, tmp_path)

    assert recorded["project_root"] == str(tmp_path)
