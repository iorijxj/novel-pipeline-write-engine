"""test_revision_diff.py — revision_diff_report 字级 diff / 风险 / 推荐"""
from src.pipeline.revision_diff_report import (
    compute_diff_summary,
    generate_risk_flags,
    generate_diff_report,
    split_paragraphs,
)


_P1 = "清晨的阳光穿过窗棂，他站在门口想了很久才迈出第一步走向远方。"
_P2 = "他握紧手里那枚旧铜钥匙，知道这一趟回不了头了。"
_P3 = "傍晚他推开屋门，屋里空无一人，只剩桌上一封没有署名的信。"
_P4 = "他攥紧拳头，明天会更难。"
_SRC = f"{_P1}\n\n{_P2}\n\n{_P3}\n\n{_P4}"


def test_small_edit_vs_full_rewrite_differ_in_char_ratio():
    # 改 3 字：只把 P1 里"很久"改成"良久"，其余不动
    small = _SRC.replace("想了很久", "想了良久")
    big = "完全不同的开头段落内容。\n\n第二段也整段重写过了。\n\n第三段同样换掉。\n\n第四段也改光。"

    s_small = compute_diff_summary(split_paragraphs(_SRC), split_paragraphs(small))
    s_big = compute_diff_summary(split_paragraphs(_SRC), split_paragraphs(big))

    assert s_small["char_change_ratio"] < 0.1
    assert s_big["char_change_ratio"] > 0.5
    assert s_small["char_change_ratio"] < s_big["char_change_ratio"]
    assert s_small["unchanged_ratio"] > s_big["unchanged_ratio"]


def test_zero_quote_source_emits_no_dialogue_loss_flag():
    revised = _SRC.replace("旧铜钥匙", "铜钥匙")
    summary = compute_diff_summary(split_paragraphs(_SRC), split_paragraphs(revised))
    flags = generate_risk_flags(split_paragraphs(_SRC), split_paragraphs(revised), summary)
    assert all("对白" not in f for f in flags)        # 零引号风格不产对白噪音


def test_quoted_source_losing_dialogue_flags():
    src_q = "「你想好了吗？」她问。\n\n「我想好了。」他答。\n\n两人沉默了很久。"
    rev_q = "她问了一句。\n\n他点头答应。\n\n两人沉默了很久。"
    summary = compute_diff_summary(split_paragraphs(src_q), split_paragraphs(rev_q))
    flags = generate_risk_flags(split_paragraphs(src_q), split_paragraphs(rev_q), summary)
    assert any("对白" in f for f in flags)


def test_recommendation_no_change():
    rep = generate_diff_report(_SRC, _SRC, {"changed_ranges": []}, tasks=[])
    assert rep["recommendation"] == "NO_CHANGE_DETECTED"


def test_recommendation_small_change_review_before_accept():
    small = _SRC.replace("想了很久", "想了良久")
    rep = generate_diff_report(_SRC, small, {"changed_ranges": []}, tasks=[])
    assert rep["recommendation"] == "REVIEW_BEFORE_ACCEPT"


def test_recommendation_full_rewrite_rejected_without_verification():
    big = "完全不同的开头。\n\n第二段重写。\n\n第三段换掉。\n\n第四段改光彻底。"
    rep = generate_diff_report(_SRC, big, {"changed_ranges": []}, tasks=[])
    assert rep["recommendation"] == "REVISION_REJECTED"
