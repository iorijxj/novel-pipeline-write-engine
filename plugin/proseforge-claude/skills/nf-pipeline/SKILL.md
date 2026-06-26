---
name: nf-pipeline
description: Run the ProseForge writing pipeline for chapter and volume workflows. Use when the user asks to prepare a chapter, run write-after gates, do multi-agent review, batch-process chapters, or build a volume summary.
---

# nf_pipeline

Use this skill when the user wants Claude Code to drive the ProseForge
writing pipeline and the task maps to one of these actions:

- `pre`
- `post`
- `review`
- `batch`
- `volume`
- `rewrite`
- `accept`

This plugin does not expose MCP tools. Instead, call the **shared wrapper
script** that ships with the Codex plugin (the Claude and Codex plugins
deliberately reuse the same scripts so all surfaces stay in sync):

```powershell
python plugin/proseforge-codex/scripts/nf_pipeline.py --action <action> ...
```

Always invoke from the **repo root** so the wrapper resolves `src/` imports
correctly. Running from elsewhere? Pass `--project-root <repo-root>` or set
`PROSEFORGE_PROJECT_ROOT=<repo-root>`; otherwise the wrapper auto-discovers the
root by walking up from the current directory.

## Action mapping

- `pre`: prepare chapter context before writing (task card + context pack + pipeline state).
- `post`: run post-write processing — word-count gate, Guard registry, human texture, ingest.
- `review`: run the 6-agent review flow (`light` or `full` mode).
- `batch`: run `post` for a chapter range `from-ch..to-ch`.
- `volume`: build the volume-level summary + bridge report.
- `rewrite`: 读 post 产出的去重报告，生成**章节尺度**「改写卡」到 `outputs/rewrite_cards/`（按问题类别给 must_keep/avoid + 问题/指令 + 可选 evidence 例句，不再逐段引原文）+ `revision_tasks.json`，由 Agent 据卡改写并写 `chapter_NNN_revised.txt`。同时附产**语义保全清单**：`exports/reports/chapter_NNN_semantic_review_request.json` + host 卡 `outputs/rewrite_cards/chapter_NNN_semantic_review.md`。内核不调 LLM。
- `accept`: 原稿 vs `chapter_NNN_revised.txt` 出字级 diff + 风险标记 + recommendation；加 `--ingest` 时审核通过则入库（追加版本快照，不覆盖原稿）。返回可能含 `verification` 与 `preservation` 块（见下方 Current behavior notes）。

## Current behavior notes

- These wrappers call the live repo code under `src/`, not a copied pipeline implementation.
- `accept` may return both `verification` and `preservation`.
- `verification` is only deterministic guard-category regression output (`resolved` / `persisted` / `regressed`) from re-running the guards on the revised draft; it does **not** imply semantic fidelity.
- `preservation` is the separate semantic-preservation block (开放读者承诺 / 活跃伏笔 / 角色关系 / canon 硬事实 / 结尾钩). 内核只产契约 + 零-LLM 词级预检，真正的语义判断由 host 据 `chapter_NNN_semantic_review.md` 卡写回执 `chapter_NNN_semantic_review.json`（schema: `{"chapter_no": N, "items": [{"id", "verdict": "preserved|broken|uncertain", "note"}]}`），`accept` 读它评估。
- 保全门禁默认 **advisory**：判定 broken 仅勝告（封顶 `REVIEW_CAREFULLY` + 加 risk_flag），不阻断入库。要硬阻断，在 config 设 `semantic_preservation.enforce: true`（此时 broken → `REVISION_REJECTED` 且不入库）。

## Required arguments

| action   | required |
|----------|----------|
| `pre`    | `--slug --title --vol-no --chapter-no` |
| `post`   | `--slug --title --vol-no --chapter-no` |
| `review` | `--slug --vol-no --chapter-no` |
| `batch`  | `--slug --title --vol-no --from-ch --to-ch` |
| `volume` | `--slug --title --vol-no` |
| `rewrite`| `--slug --title --vol-no --chapter-no` |
| `accept` | `--slug --title --vol-no --chapter-no` (`--ingest` 可选) |

## Optional arguments

- `--chapter-type normal|key|climax`
- `--mode light|full` for `review` — light 跑 3 个 agent（continuity/prose/plot），full 跑 6 个（额外加 character/reader/detail）；两者审稿阈值相同，区别只在覆盖范围
- `--project-root <path>` and `--config-path <path>` when the default repo/config location is not correct

## Examples

```powershell
python plugin/proseforge-codex/scripts/nf_pipeline.py --action pre --slug demo_novel --title "Demo Novel" --vol-no 1 --chapter-no 3
python plugin/proseforge-codex/scripts/nf_pipeline.py --action review --slug demo_novel --vol-no 1 --chapter-no 3 --mode full
python plugin/proseforge-codex/scripts/nf_pipeline.py --action batch --slug demo_novel --title "Demo Novel" --vol-no 1 --from-ch 1 --to-ch 5
```

## Output handling

The wrapper prints the result as JSON on stdout. Summarize the JSON back to the
user in a few sentences (status, key counts, any error). Do not paste raw
multi-screen JSON unless the user explicitly asks for it. Exit code is non-zero
when `status == "error"`; surface that clearly when it happens.
