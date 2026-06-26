---
name: proseforge-hermes
description: ProseForge 长篇小说工程化系统 — 写作流水线 + 项目管理。通过 2 个 Hermes 工具覆盖完整写作工作流。
---

# ProseForge — Hermes 写作引擎

ProseForge 是一个 AI Agent 辅助长篇小说创作系统，跑在 Hermes Agent 上。
核心思路不是"怎么写"，而是"怎么保证写对"——通过 registry 10 门禁（+ human_texture 平行路径 11 门禁）强制执行写作纪律。

## 可用工具

插件注册了 2 个工具：

### nf_pipeline — 写作流水线

```json
{
  "name": "nf_pipeline",
  "description": "Writing pipeline. action=pre/post/review(agent review)/batch(from_ch~to_ch)/volume/rewrite(产改写卡)/accept(diff+可选入库)",
  "parameters": {
    "type": "object",
    "properties": {
      "action":     {"type": "string", "enum": ["pre", "post", "review", "batch", "volume", "rewrite", "accept"], "description": "Pipeline action. 必填。"},
      "slug":       {"type": "string", "description": "小说 slug。pre/post/review/batch/volume 必填。"},
      "title":      {"type": "string", "description": "小说中文标题。pre/post/review/batch/volume 必填。"},
      "vol_no":     {"type": "integer", "description": "卷号。pre/post/review/batch/volume 必填。"},
      "chapter_no": {"type": "integer", "description": "章号。pre/post/review/rewrite/accept 必填。"},
      "chapter_type": {"type": "string", "enum": ["normal", "key", "climax"], "description": "章节类型。pre/post/batch 使用，默认 normal。"},
      "mode":         {"type": "string", "enum": ["light", "full"], "description": "审读模式。review 使用，默认 full。"},
      "from_ch":      {"type": "integer", "description": "batch 起始章号。"},
      "to_ch":        {"type": "integer", "description": "batch 结束章号。"},
      "ingest":       {"type": "boolean", "description": "accept: 经门禁(diff+guard复跑+语义保全)后入库，默认 false。"},
      "enforce_preservation": {"type": "boolean", "description": "accept: 语义保全 broken 时硬阻入库（默认 false = 仅告警）。"},
      "min_confidence": {"type": "number", "description": "rewrite: 最低置信度阈值，默认 0.70。"},
      "max_tasks":     {"type": "integer", "description": "rewrite: 最大改写任务数，默认 5。"}
    },
    "required": ["action"]
  }
}
```

### nf_project — 项目管理

```json
{
  "name": "nf_project",
  "description": "项目管理。action=init(初始化工作区)/create(创建小说槽位)/list(槽位列表)/status(工作区状态)/outline(大纲管理 add/list/switch)/export(导出小说)",
  "parameters": {
    "type": "object",
    "properties": {
      "action":     {"type": "string", "enum": ["init", "create", "list", "status", "outline", "export"], "description": "项目操作。必填。"},
      "slot_name":  {"type": "string", "description": "槽位标识（英文，如 'gwdz'）。create 必填。"},
      "title":      {"type": "string", "description": "小说中文名。create 必填。"},
      "sub_action": {"type": "string", "enum": ["add", "list", "switch"], "description": "outline 子操作。outline 必填。"},
      "file_path":  {"type": "string", "description": "大纲 JSON 文件路径。outline add 必填。"},
      "outline_id": {"type": "string", "description": "大纲 ID。outline switch 必填。"},
      "slug":       {"type": "string", "description": "小说 slug。export 使用（默认当前激活槽位）。"},
      "format":     {"type": "string", "enum": ["txt", "md"], "description": "导出格式。export 使用，默认 txt。"},
      "output":     {"type": "string", "description": "输出路径。export 使用（默认自动生成）。"}
    },
    "required": ["action"]
  }
}
```

## 写作工作流

### 第 1 次写新小说

```
1. nf_project action=init                                            → 初始化 workspace/
2. nf_project action=create slot_name=xxx title=小说名               → 创建槽位
3. nf_project action=outline sub_action=add file_path=...            → 导入大纲 JSON
4. nf_pipeline  action=pre   slug=... title=... vol_no=1 chapter_no=1 → 准备上下文
5. AI 写第 1 章 → 写入 D:\作品\小说\<书名>\
6. nf_pipeline  action=post  slug=... title=... vol_no=1 chapter_no=1 → 门禁+入库
7. 重复 4~6 写完一卷
8. nf_pipeline  action=volume slug=... title=... vol_no=1            → 卷级后处理
```

### 后续章节 (已有槽位)

```
1. nf_project action=status                    → 确认当前激活槽位
2. nf_pipeline  action=pre   ... ch=N          → 上下文准备
3. AI 写第 N 章 → 写入 TXT
4. nf_pipeline  action=post  ... ch=N          → 门禁+入库
```

### 质量问题处理

```
审读:           nf_pipeline action=review slug=... vol_no=1 chapter_no=N mode=full
批量后处理:     nf_pipeline action=batch from_ch=1 to_ch=5 ...
```

### 改写闭环（rewrite / accept）

```
1. nf_pipeline action=rewrite ... chapter_no=N min_confidence=0.7 max_tasks=5
                                              → 产改写卡 outputs/rewrite_cards/
2. AI 按卡只改问题段 → 写 chapter_NNN_revised.txt
3. nf_pipeline action=accept ... chapter_no=N ingest=true
   （可选 enforce_preservation=true 硬阻语义保全失败）
   → diff + 入库（不覆盖原稿）
```

## 重要规则

1. **pre → AI写 → post** 三步必须完整走，不能跳过 pre 直接写
2. **chapter_type** 默认 normal。高潮/关键情节用 key/climax（字数标准不同）
3. **review mode**: light（3 agents）≈ 快速检查，full（6 agents）≈ 完整审读，默认 full
4. `review` 只做审读出报告；改写走 `rewrite`（产卡）+ `accept`（diff/门禁/入库）闭环，内核不调 LLM
5. **字数标准** 按 chapter_type 不同，参见 config.example.json 的 word_count 段
6. **作品输出目录**：D:\作品\小说\<小说名>\ 每章独立 TXT
7. **零引号文学**：对话融入叙述，禁用所有引号
