# Knowledge Corpus Tools

离线、失败关闭的 Knowledge 阶段 A 工具。它只负责审计、官方资产获取、解析/OCR、结构切片、embedding、候选索引和受控 alias 发布；不进入 `knowledge.query` 在线链路，不生成查询 DSL，不调用外部 LLM。

所有有状态命令都必须显式传入外部 workspace。正式阶段 A workspace 为 `D:\codex-data\knowledge-corpus-stage-a`，原始附件和完整解析内容不提交 Git。

```powershell
python -m venv D:\codex-data\knowledge-corpus-stage-a\.venv
D:\codex-data\knowledge-corpus-stage-a\.venv\Scripts\python.exe -m pip install -e D:\codex\knowledge-corpus-tools[dev]
D:\codex-data\knowledge-corpus-stage-a\.venv\Scripts\knowledge-corpus.exe --help
```

发布命令要求调用方同时给出当前 alias、精确旧索引、精确旧 UUID 和精确候选索引。任何前置不一致都会停止；工具从不删除旧索引。
