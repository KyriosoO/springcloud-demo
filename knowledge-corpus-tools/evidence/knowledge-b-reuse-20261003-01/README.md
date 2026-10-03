# 新独立 B 表示对照：完整运行，待人工盲标

## 运行身份与范围

- run ID：`knowledge-b-reuse-20261003-01`。
- 分支及冻结 HEAD：`codex_0915` / `781690c0a932a50fb898918d699b2c18ac41647d`。
- 维护者于2026-10-03确认本次 B／MEASURE 窗口内本人及其他任务不修改目标索引、不切换相关 alias；本次只消费新批次，不复用历史失败运行。
- 复用已有只读候选；未重建索引、修改正文或重算语料向量。两臂各15521记录、全量竞争池、相同chunk/正文/模型/查询参数；既有构建来源按 `reuse-intent.json` 的Git提交及逐文件hash回链。
- 基线：`agent-doc-tax-policy-v5-20260907-vector-b2`，UUID `jJ5Ww3LCRWWycfDkUZvmdw`。
- 候选：`agent-doc-tax-policy-v6-20260930-body-b1`，UUID `g4eIYXTkQQik49TaOqJZ6A`。
- 只比较预登记的10题；A保持 `Not assessed`。

## 实际命令与终态

```powershell
$env:JAVA_HOME = 'C:/Program Files/Java/jdk-25.0.2'
$env:PYTHONPATH = 'D:/codex/agent-runtime/src;D:/codex/knowledge-corpus-tools/src;D:/codex/agent-runtime'
$env:LLM_API_KEY = ''
& 'D:/codex/agent-runtime/.venv/Scripts/python.exe' -m tests.evaluation.knowledge.rebuild_b_local_runner --execute-once --run-directory 'D:/codex/knowledge-corpus-tools/evidence/knowledge-b-reuse-20261003-01' --baseline-port 19211 --candidate-port 19212 --baseline-proxy-port 19311 --candidate-proxy-port 19312
```

命令仅影响该子进程环境；未读取原模型密钥。执行exit code=0，原始终态为 `completed_awaiting_blind_labels` / `local_verified`。这表示执行协议完整，不表示质量通过。

| 项目 | 实际数量 | 证明范围 |
|---|---:|---|
| 新双臂完整扫描 | 64+64 | 准备阶段独立分账 |
| typed search | 44 | 正式10题 |
| query embedding | 10 | 每题一次、两臂共享 |
| online rerank | 22 | 两臂有限重排 |
| 正式只读ES元数据HTTP | 30 | 身份、Profile及首尾核验 |
| 临时alias写 | 4 | 本批两个隔离alias各创建/移除一次；不是生产发布 |
| paid / retry / resume | 0 / 0 / 0 | 不调用外部模型、不重试或续跑 |

原始终态记录 `ownedProcessesStopped=true`、`aliasesRemoved=true`、`proxyViolations=0`；执行退出后四个隔离端口无监听。未停止用户的9200/8908/8909服务，未切换生产alias。冻结Git archive打包使用 `-DskipTests`，不能作为Maven测试通过证明。

## 机械指标与人工边界

既有严格离线review入口核验原始终态、来源闭环、规范请求见证及盲标池。`mechanical-metrics.json` 只从冻结必要来源和排名计算，不包含人工标签或回答质量判断：

- 两臂必要来源宏平均 `recall@20=0.85`，未严格提高；逐题核心及保留题覆盖未退化。
- 基线median检索时延约0.83653秒，候选约0.83961秒；不超过基线110%。不含共享embedding、启动、构建或元数据核验。
- 未发现评分器所检查的keyword顺序或未变law域排名混杂。
- 隐藏臂身份的候选判断共215项，目前全部未标；两臂precision为null，整体评分为 `not_assessed`，原因 `blind_labels_missing`、`recall_not_improved`。
- 未满足既定主指标改善条件，不允许发布候选，也不追加对照。当前生产b2保持；后续唯一MEASURE选择现行b2与意图12/Summary9/minimal-v1组合，不用未发布候选的排名冒充该组合回答证明。

`human-blind-labels.template.json` 是未填写模板，不是人评证据。维护者须逐项核对原文后填写 `directlyRelevant`；不能把未标项默认为false、删除候选或事后修改gold。确认值只在真实人工复核完成后填写：`maintainer_personally_reviewed_each_supplied_label_against_source_text`。模板没有正文、向量、密钥、JWT或原始模型响应。该离线review工具自身不认证reviewer是否真人，独立评价仍由维护者提供。

## 关键原始资产 SHA-256

| 资产 | SHA-256 |
|---|---|
| reuse-intent.json | a38effae6e1f8e52e9ad0b9f70e94e5fd87ee80b0beb8916dad360d492232326 |
| reuse-final.json | 7a1417b199401c3dc669caad025cda9ee2c61d0f38c207419d40cb448eccb409 |
| comparison-attempt.json | 36691d8668e01415882a256e58d5d974f9d06a4e4be581eaffe17bbb82bd2148 |
| comparison-java-attestation.json | accabc1b6ee5701449603b9598f539ccb58917d5ba7af39e7781b735984f5319 |
| comparison-result.json | 50a03b7dc8cb8e2667c0bc509346e4db12f4fc6c5ceee953ed8dbd39ac21a934 |
| comparison-blind-label-pool.json | b1233f03560859f8962ebb754df2451aed88cab953c70416e592d2d0fa6c1002 |

原始JSON保持append-only；不覆盖历史run。此证据不证明12题MEASURE、完整37项功能/安全UAT、人工回答质量、部署或发布通过。
