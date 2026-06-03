# Demo — 示例小说与大话

本目录包含示例参考文件，帮助理解 Novel Forge 的文件格式和写作风格。

## 目录结构

```
demo/
├── outlines/           ← 示例大纲（可直接用 novel.py outline add 导入）
│   └── 仙路漫漫.txt
└── novels/             ← 示例章节（展示零引号文学写法）
    └── 第1章_晨光.txt
```

## 使用方式

### 导入示例大纲

```bash
python novel.py outline add demo/outlines/仙路漫漫.txt
```

引擎会自动检测相似度，如果是不同的新小说会自动创建新的 slot。

### 查看示例章节

`demo/novels/` 下的章节展示了引擎推荐的写作风格：

- **零引号**：对话融入叙事，不使用任何引号（直引号/弯引号/直角引号均禁用）
- **低对话密度**：对话占比 ≤10%，靠动作和物件推进
- **克制叙述**：余华式写法，少氛围描写，多具体动作和物件细节
- **真实感**：补丁缝线、碗沿磕牙、草叶上的露水——不完美让场景活起来

## 自己写小说

参考格式写大纲和章节文件，按需修改后：

1. `python novel.py outline add 你的大纲.txt`
2. `python novel.py pre 1`     # 生成第1章任务卡
3. `python novel.py post 1`    # 写完后入库 + 守卫检查

详细用法见 `python novel.py menu-show`。
