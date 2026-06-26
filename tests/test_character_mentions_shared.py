from src.agents.character import CharacterAgent
from src.pipeline.chapter_context import (
    _extract_active_relationships,
    _extract_emotional_states,
    _extract_key_decisions,
)
from src.utils.character_mentions import find_character_mention_positions


def test_shared_matcher_applies_mode_a_and_mode_b():
    content = "王明月走来，王明点头。行李很重，李说他来拿。"
    positions = find_character_mention_positions(content, ["王明", "王明月", "李"])

    assert len(positions["王明月"]) == 1
    assert len(positions["王明"]) == 1
    assert len(positions["李"]) == 1


def test_chapter_context_ignores_single_char_collision_mentions():
    content = "他提着行李，决定离开，心里很难过。"
    mention_positions = find_character_mention_positions(content, ["李"])

    assert mention_positions["李"] == []
    assert _extract_emotional_states(content, ["李"], mention_positions=mention_positions) == {}
    assert _extract_key_decisions(content, ["李"], mention_positions=mention_positions) == []


def test_chapter_context_uses_real_character_mentions():
    content = "李决定离开。后来李很难过。"
    mention_positions = find_character_mention_positions(content, ["李"])

    emotions = _extract_emotional_states(content, ["李"], mention_positions=mention_positions)
    decisions = _extract_key_decisions(content, ["李"], mention_positions=mention_positions)

    assert emotions["李"] == "难过"
    assert len(decisions) == 1
    assert decisions[0]["character"] == "李"


def test_chapter_context_relationships_use_real_mentions():
    content = "李看见王明。"
    mention_positions = find_character_mention_positions(content, ["李", "王明"])

    relations = _extract_active_relationships(
        content,
        ["李", "王明"],
        mention_positions=mention_positions,
    )

    assert "李-王明" in relations


def test_chapter_context_relationships_ignore_collision_mentions():
    content = "他提着行李看见王明。"
    mention_positions = find_character_mention_positions(content, ["李", "王明"])

    relations = _extract_active_relationships(
        content,
        ["李", "王明"],
        mention_positions=mention_positions,
    )

    assert relations == []


def test_character_agent_segments_ignore_single_char_collisions():
    content = "行李很重。李说话。"
    segments = CharacterAgent._get_char_text_segments(
        content,
        "李",
        window=3,
        all_names=["李"],
    )

    assert "行李" not in segments
    assert "说话" in segments


def test_character_agent_segments_ignore_longer_name_overlap():
    content = "王明月走来。隔了很久。王明沉默。"
    segments = CharacterAgent._get_char_text_segments(
        content,
        "王明",
        window=4,
        all_names=["王明", "王明月"],
    )

    assert "王明月" not in segments
    assert "沉默" in segments
