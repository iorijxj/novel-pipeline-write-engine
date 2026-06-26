---
name: nf-pipeline
description: Use when running ProseForge chapter or volume pipeline actions such as pre, post, review, batch, volume, rewrite, or accept without MCP.
---

# nf_pipeline

Use this skill when the user wants to run the ProseForge writing pipeline from
Codex and the task maps to one of these actions:

- `pre`
- `post`
- `review`
- `batch`
- `volume`
- `rewrite`
- `accept`

This plugin does not expose MCP tools. Instead, call the local wrapper script:

```powershell
python <plugin-root>/scripts/nf_pipeline.py --action <action> ...
```

## Action mapping

- `pre`: prepare chapter context before writing.
- `post`: run post-write processing for a chapter.
- `review`: run the multi-agent review flow.
- `batch`: run `post` for a chapter range.
- `volume`: build the volume-level summary.
- `rewrite`: read the post deduplicated report, generate the rewrite card under `outputs/rewrite_cards/` plus `revision_tasks.json`, and let an agent produce `chapter_NNN_revised.txt`. The kernel does not call an LLM here.
- `accept`: compare source vs revised, produce diff + recommendation, and optionally ingest with `--ingest` after review passes.

## Current behavior notes

- These wrappers call the live repo code under `src/`, not a copied pipeline implementation.
- `accept` may return both `verification` and `preservation`.
- `verification` is only deterministic guard-category regression output such as `resolved`, `persisted`, and `regressed`.
- `verification` does not imply semantic fidelity.
- `preservation` is the separate semantic-preservation evaluation block when the repo enables that flow.

## Required arguments

- `pre`: `--slug --title --vol-no --chapter-no`
- `post`: `--slug --title --vol-no --chapter-no`
- `review`: `--slug --vol-no --chapter-no`
- `batch`: `--slug --title --vol-no --from-ch --to-ch`
- `volume`: `--slug --title --vol-no`
- `rewrite`: `--slug --title --vol-no --chapter-no`
- `accept`: `--slug --title --vol-no --chapter-no` (`--ingest` optional)

## Optional arguments

- `--chapter-type normal|key|climax`
- `--mode light|full` for `review`
- `--project-root <repo-root>` or `PROSEFORGE_PROJECT_ROOT=<repo-root>` when running outside the repository
- `--config-path <path>` when the config is not the default location

## Examples

```powershell
python <plugin-root>/scripts/nf_pipeline.py --action pre --slug demo_novel --title "Demo Novel" --vol-no 1 --chapter-no 3
python <plugin-root>/scripts/nf_pipeline.py --action review --slug demo_novel --vol-no 1 --chapter-no 3 --mode full
python <plugin-root>/scripts/nf_pipeline.py --action batch --slug demo_novel --title "Demo Novel" --vol-no 1 --from-ch 1 --to-ch 5
```

Print the returned JSON back to the user in summarized form instead of pasting
raw command output unless the user explicitly asks for it.
