# 独立 MEASURE：已消费，技术失败停止

## 身份与范围

- run ID：`knowledge-rebuild-measure-20261003-01`。
- 分支及冻结 HEAD：`codex_0915` / `0e9e47345def6db376f4b2e9af481d445d8d707c`。
- authorization reference：`UAT_02:KNOWLEDGE_REBUILD_MEASURE_20261003_01`。
- manifest SHA-256：`47dee2d00fdd980fb0280c269b5f390d4ba3febc9bfc7bdcd4dcf69190d5fcd8`。
- 维护者已确认本次 B／MEASURE 窗口无其他任务修改目标索引或切换相关 alias。
- 使用现行 b2：`agent-doc-tax-policy-v5-20260907-vector-b2`，UUID `jJ5Ww3LCRWWycfDkUZvmdw`；不是未发布 body-b1 候选的回答证明。
- 运行绑定为 `deepseek-flash`、action-selection-v4、意图12、Summary9、minimal-v1；沿用既定12题、gold、阈值及单次预算。

## 实际执行

clean HEAD 构建及冻结使用版本化 `knowledge_rebuild_measure_prepare build/freeze`；构建的五个Maven命令带 `-DskipTests`，不作为Maven测试证明。build/freeze子进程将 `LLM_API_KEY` 置空，不读取原密钥。正式执行仅由以下launcher在启动、身份及新鲜索引快照前检后读取进程级密钥；未输出或持久化密钥：

```powershell
$env:JAVA_HOME = 'C:/Program Files/Java/jdk-25.0.2'
$env:PYTHONPATH = 'D:/codex/agent-runtime/src;D:/codex/knowledge-corpus-tools/src;D:/codex/agent-runtime'
& 'C:/Users/zhoud/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe' -NoProfile -File 'D:/codex/agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1' -RepositoryRoot 'D:/codex' -ManifestPath 'D:/codex/agent-runtime/tests/uat/knowledge-rebuild-measure-20261003-01/manifest.json' -AuthorizationPath 'D:/codex/agent-runtime/tests/uat/knowledge-rebuild-measure-20261003-01/authorization.json' -ExpectedManifestSha256 '47dee2d00fdd980fb0280c269b5f390d4ba3febc9bfc7bdcd4dcf69190d5fcd8'
```

正式命令仅执行一次，exit code=1。原始 [failure.json](../results/knowledge-rebuild-measure-20261003-01/failure.json) 为 `failed_consumed`、`case_technical_failure`、completedCases=4；按UAT执行完整性口径为 `invalid_run`，不是有效完整测量。没有生成 `measurement.json` 或成功 `result.json`，不另造成功终态。

## 实际调用与停止

| 调用 | 实际 | 本批上限 |
|---|---:|---:|
| 外部模型HTTP | 13 | 36 |
| typed Knowledge search | 8 | 48 |
| query embedding | 4 | 12 |
| online rerank | 4 | 24 |
| 正式只读ES元数据HTTP | 27 | 72 |
| 完成题数 | 4 | 12 |

`attempts.jsonl` 共58行，29个started均有29个terminal completed；模型数包含selector、意图及Summary。第005题有selector、意图、embedding、两路search、rerank及Summary的完成记录，随后触发终态检查失败。HTTP传输完成不表示模型输出、引用或公开结果合同有效。

原始代理见证为 `live_proxy`：typed=8、metadata=27，其中health=1、alias=12、indexDefinition=10；completed alias checks=10（每题前后各一次，每次两个HTTP）。settings/mapping初始化各2次包含在metadata中；proxyViolations=0。freeze绑定读取2和全记录快照前检预算67单独管理，不借用正式72预算。失败后未执行完整快照postflight，也不声称前后全记录证明已闭合。

自动retry/resume=0；Business、旧answer及额外批次为0。首个模型outbound已消费授权；第005题失败后没有补跑或续跑，006～012未执行。自有进程清理见证为true、cleanupIssues为空，退出后18090/19201/19202/19203/19313均无监听；未停止用户9200/8908/8909服务。未切换生产alias、发布候选或修改现行索引。

## 逐题有限事实

| Case | 公开状态 | 模型/search/embed/rerank | 必要来源及预期差异 |
|---|---|---|---|
| UAT-KM-001 | HTTP200 / success | 3/2/1/1 | 必要来源进入top20；3条引用。不是人工回答通过 |
| UAT-KM-002 | HTTP200 / success | 3/2/1/1 | 必要来源进入top20；1条引用。不是人工回答通过 |
| UAT-KM-003 | HTTP200 / no_result | 3/2/1/1 | small_2022未进入top20；与冻结success不同 |
| UAT-KM-004 | HTTP422 / unsupported | 1/0/0/0 | `core.no_supported_capability_candidate`；与冻结no_result不同 |
| UAT-KM-005 | 未保存终态响应 | 3/2/1/1 | Summary传输完成后批次技术失败；不补造status/errorCode |
| UAT-KM-006～012 | 未执行 | 0/0/0/0 | 停止条件触发后不再调用 |

失败题的公开响应及errorCode未进入有限证据，临时服务日志按既有launcher清理。因此不能仅从最后一条Summary transport completed断定具体解码、引用、摘要校验或回传根因；保留这一证据缺口，不重跑去补证。四条已完成公开结果仅在受控本地 `.tmp/knowledge-measure-review/knowledge-rebuild-measure-20261003-01/public-review.jsonl` 供人工阅读，不提交其引文正文、完整服务响应或模型原始响应。

Functional/Safety完整验收未完成；Retrieval/Answer不形成有效整批结论，人工四项为Not assessed。KM003/004预期差异不能通过改gold、删题或更改阈值消除。B对照另有recall未改善及盲标缺口，因此本次不满足发布条件，现行b2保持。

## 原始资产 SHA-256

| 资产 | SHA-256 |
|---|---|
| build-attestation.json | c2ee3e8fd3d9bd0006447fdca4233e1a784d9e71c946b7774981d4b596e8c091 |
| manifest.json | 47dee2d00fdd980fb0280c269b5f390d4ba3febc9bfc7bdcd4dcf69190d5fcd8 |
| authorization.json | 7e8ad1b20fddd068f407b1e43c7229cc1d8eb2cfdefc8a25f5f240183f1df580 |
| authorization.consumed.json | 906508cf47793351714709125638f4701ebf7a9a805c62df743a9c35f4881998 |
| attempts.jsonl | 176bbdcc530113cd0c4067529e2ae3957963b2de690d9ddb8b4025bf7cd067aa |
| cases.jsonl | ae1fc5c5eca2bdb6215b5534f00a7921fa3d60bce0e79c391eb22d6e41efeefe |
| es-proxy-witness.json | 0e8843c86817b30399fc5a9819a93f195512a0eec30a173c7c2edb45918cbcf6 |
| failure.json | 3ff109f150f7dd5ac9262defabc863270228829ed3b68895699981e7aae30bc4 |

运行后27项冻结asset hash均匹配；原始JSON/JSONL保持append-only。本README是事后交接说明，不补造运行见证、成功终态或人评。仅本地Git提交，不push或部署。
