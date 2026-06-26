"""Deterministic character-name mention matching helpers."""

_NAME_BOUNDARY = set(
    "，。！？、；：…—·　 \t\r\n"
    "“”‘’\"'「」『』（）《》〈〉【】"
    ",./!?;:()[]{}<>"
)
_NAME_FUNCTION = set(
    "的了着过也又却就便是在不没都还已能会可呢吧啊吗"
    "和与跟对把被让向比替给朝同及"
)
_NAME_VERB = set("说道想问答笑看走点伸皱叹喊叫哭喝望听站坐拿抬转摇瞪盯抱推拉踢打骂夸劝")
_NAME_PREFIX = set("老小大阿")
_NAME_CONTEXT = _NAME_BOUNDARY | _NAME_FUNCTION | _NAME_VERB | _NAME_PREFIX


def _is_single_char_mention(content: str, idx: int) -> bool:
    """Gate single-char names behind a left-anchored context check."""
    if idx == 0:
        return True
    return content[idx - 1] in _NAME_CONTEXT


def find_character_mention_positions(content: str, names: list[str]) -> dict[str, list[int]]:
    """Return valid mention start offsets for each character name.

    Matching is deterministic and zero-dependency:
    - Mode A: longest-first + span masking prevents short-name hits inside longer names.
    - Mode B: single-char names must pass a left-anchored boundary/context gate.
    """
    ordered_names: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        ordered_names.append(name)

    positions = {name: [] for name in ordered_names}
    consumed = [False] * len(content)
    scan_names = [name for name in ordered_names if name]
    scan_names.sort(key=len, reverse=True)

    for name in scan_names:
        single = len(name) == 1
        start = 0
        while True:
            idx = content.find(name, start)
            if idx < 0:
                break
            end = idx + len(name)
            if any(consumed[idx:end]):
                start = idx + 1
                continue
            if single and not _is_single_char_mention(content, idx):
                start = idx + 1
                continue
            positions[name].append(idx)
            for i in range(idx, end):
                consumed[i] = True
            start = end

    return positions


def count_character_mentions(content: str, names: list[str]) -> dict[str, int]:
    """Count valid mentions for each character name."""
    return {
        name: len(pos_list)
        for name, pos_list in find_character_mention_positions(content, names).items()
    }
