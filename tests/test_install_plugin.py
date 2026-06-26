"""
test_install_plugin.py — enable_plugin_in_config 的针对性单测。

回归重点：已有 plugins.enabled 列表时，启用新插件必须 *追加* 到列表，
而不是注入第二个 enabled: 键（否则 yaml.safe_load 只保留最后一组，
导致插件静默未启用）。
"""
import yaml

from install_plugin import enable_plugin_in_config

PLUGIN = "proseforge-engine"


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def _enabled(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))["plugins"]["enabled"]


def test_appends_to_existing_enabled_list(tmp_path):
    cfg = _write(tmp_path, "plugins:\n  enabled:\n    - existing-plugin\n")
    assert enable_plugin_in_config(cfg, PLUGIN) is True
    enabled = _enabled(cfg)
    # 关键断言：两者都在，旧的没被顶掉
    assert "existing-plugin" in enabled
    assert PLUGIN in enabled


def test_plugins_present_without_enabled(tmp_path):
    cfg = _write(tmp_path, "plugins:\n  some_other_key: 1\n")
    assert enable_plugin_in_config(cfg, PLUGIN) is True
    assert PLUGIN in _enabled(cfg)


def test_no_plugins_section(tmp_path):
    cfg = _write(tmp_path, "model: gpt\nfoo: bar\n")
    assert enable_plugin_in_config(cfg, PLUGIN) is True
    loaded = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert PLUGIN in loaded["plugins"]["enabled"]
    # 既有键保留
    assert loaded["foo"] == "bar"


def test_idempotent_when_already_enabled(tmp_path):
    cfg = _write(tmp_path, f"plugins:\n  enabled:\n    - {PLUGIN}\n")
    assert enable_plugin_in_config(cfg, PLUGIN) is False
    # 内容未变、未产生重复项
    assert _enabled(cfg) == [PLUGIN]


def test_preserves_comments(tmp_path):
    cfg = _write(
        tmp_path,
        "# my hermes config\nplugins:\n  enabled:\n    - existing-plugin  # keep me\n",
    )
    enable_plugin_in_config(cfg, PLUGIN)
    text = cfg.read_text(encoding="utf-8")
    assert "# my hermes config" in text
    assert "# keep me" in text
