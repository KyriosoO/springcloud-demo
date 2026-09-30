# B 表示对照：候选构建成功，真实比较未形成有效测量

- run ID：`knowledge-b-body-20260930-01`。
- frozen HEAD：`88fee30537616b0722de7334141952036048f309`，分支 `codex_0915`。
- 范围：四份既有附件的 738 条 chunk，正文和 chunk 身份不变；完整 15521 条竞争池保留。
- 变量：`policy-title-section-body-v1` → `body-only-v2`；模型和查询方案不变。
- 维护者已在本次对话明确确认执行窗口内没有其他目标 Knowledge 索引或 alias 修改。该声明不是机器锁或质量通过证明。

## 实际执行

准备器 7 次只读 ES 请求；source/candidate 身份及完整指纹扫描各 64 次。构建使用 363/366 次 ES 请求、24/24 批本地 embedding，更新 738 条向量；候选总数 15521。外部模型、自动重试、续跑和线上 alias 写入均为 0。

候选索引 `agent-doc-tax-policy-v6-20260930-body-b1`，UUID `g4eIYXTkQQik49TaOqJZ6A`，指纹 `e9ccca316b295fa8ca258034dd8fd625517586c3b462ba5274d5d44e98f51691`。构建与扫描证明它是只读、未发布的候选，不证明召回改善。

一次双臂比较已消费，但在首次查询前未通过本地运行/身份准入；终态 `not_assessed / local_execution_or_identity_failed`。typed/query embedding/rerank 调用均为 0，10 题均未执行。比较 metadata ES 请求 12 次，两个临时只读 alias 的添加和移除合计 4 次；终态记录 `ownedProcessesStopped=true`、`aliasesRemoved=true`、`proxyViolations=0`。无人工盲标或质量指标。

该比较不补跑、不续跑、不改判。候选保持未发布，现行只读 alias 未切换；A 仍为 Not assessed。失败原因需要 non-live 诊断，不能由此推断候选召回效果好或差。

## 证据边界

本目录仅保存冻结绑定、模型/文件身份、完整源 ID/hash 映射、调用计数和有限终态；不保存正文、向量、API Key、JWT 或原始模型响应。`binding.json`/`assessment-intent.json` 与 SHA 文件及扫描结果共同绑定候选。source/candidate 映射用于证明完整竞争池和稳定身份，不能代替人工原文或回答评价。

准备阶段在同名的隔离 staging 目录执行；本目录中的 preparation/selection 和准备结果为首次逐字复制，hash 保持不变。历史 b2 及其他运行资产未改写。
