# B 新独立比较的有限失败证据（2026-10-02）

维护者重新授权使用修复后 HEAD 的独立批次，沿用既定预算、gold 和阈值，不复用失败目录。本目录的扫描和比较均只执行一次，不代表有效质量测量。

- run ID：`knowledge-b-reuse-20261002-01`；分支 `codex_0915`；frozen HEAD `ebd8dfd2bf8aee40ff764347fb4ed10206044f55`。冻结前工作树干净，比较结束前未修改 tracked 文件。
- 新的 B 无推理启动预检已在独立目录通过，见[启动有限证据](../knowledge-b-startup-20261002-02/README.md)。MEASURE 的独立启动失败不作为本次 B 的前置。
- 准备扫描终态 `scanned_read_only`：source/candidate 各64次 ES HTTP、各15,521记录；两个 ID/content hash 映射与原构建 Git 提交 `c9b8642e9c20765814df4b3422cfa958a2c4900c` 中对应文件的 blob 完全相同。新扫描绑定当前 UUID、mapping、完整记录 fingerprint，不复用旧比较结论。
- 没有新建索引、改写正文或重算语料向量；复用既有只读未发布候选。builder ES、embedding、writeOps 均0；生产 alias 未切换。
- 版本化入口从冻结 archive 离线构建 Java（`-DskipTests`，不是测试证明），使用绝对 `JAVA_HOME/bin/java.exe`。
- 正式10题均已调用：typed search44、query embedding10、online rerank22、元数据 ES HTTP30、随机独占临时 alias 写4；准备扫描128次独立分账。proxy witness 为12个GET/44个POST，均HTTP200；paid、retry、resume均0。
- **终态 `not_assessed / runtime_provenance_missing`；phase `postflight`；有限诊断 `canonical_requests_mismatch`。** 两臂各22条POST的规范hash多重集合不一致，不能准入或计算质量指标。调用完成不是有效对照，更不是通过。
- 原始结果不包含 traces；没有生成 blind label pool，不补算、补证、改判或续跑。没有读取模型密钥、创建正式 MEASURE 授权或执行12题端到端模型测量。
- `ownedProcessesStopped=true`、`aliasesRemoved=true`、`proxyViolations=0`；结束后19211、19212、19311、19312无监听。没有停止用户既有服务。

## 实际入口

在 runtime 项目 venv 中，仅为该进程使用当前 runtime/corpus 源码 `PYTHONPATH`，并置空 `LLM_API_KEY`（未读取原值）：

```powershell
& 'D:/codex/agent-runtime/.venv/Scripts/python.exe' -m tests.evaluation.knowledge.rebuild_b_local_runner `
  --prepare-reuse --run-directory 'D:/codex/knowledge-corpus-tools/evidence/knowledge-b-reuse-20261002-01'
& 'D:/codex/agent-runtime/.venv/Scripts/python.exe' -m tests.evaluation.knowledge.rebuild_b_local_runner `
  --execute-once --run-directory 'D:/codex/knowledge-corpus-tools/evidence/knowledge-b-reuse-20261002-01' `
  --baseline-port 19211 --candidate-port 19212 --baseline-proxy-port 19311 --candidate-proxy-port 19312
```

以上为已消费运行的追溯命令，不是复跑指令。此目录不可再次执行。

## 原始资产 SHA-256

| 文件 | SHA-256 |
|---|---|
| reuse-intent.json | 14fefd86c9996f2a119d16c5e8b92fdafba12e4b473d7a77324e71ef131e9009 |
| reuse-final.json | e24c4e24001bb52008667369bb10ec49ab2bd3b140f9080e1a7a8dcb41134e74 |
| reuse-scan-attempt.json | 828e7122c2c63b5dbdbe67cbe4744056602dccd36bc60cc59207dca1ae8a5c42 |
| reuse-scan-terminal.json | fa972d1ab01f4e8ddb469d526597ca5fc5f21053a0a1f071fe56372b18e85bb0 |
| source-scan-result.json | a82552b078321d980918496295ae239f3ee9528505754a19dae84646382bfc4e |
| candidate-scan-result.json | 8ed1a35acc83fff6f711505322fd29fbce93449b2ca447511ca4e6a10d2b5df9 |
| source-id-mapping.json | e2178b1ee9f13ce840e1a1b878cc7778e554ab1319eecb7e73b0ed1baa5a6f96 |
| candidate-id-mapping.json | 3930b68b10adc1a367190b2b4562c650e091a693b049b301553bab57f9c22350 |
| comparison-java-attestation.json | c0fe93c8683b2e3d4031c6e458573ec97548dc720d9a644b9411ea8aa9bd4513 |
| comparison-attempt.json | 29ebf4779f36daa31a6daa5d96420874b2ae3ce1ab2fe6ffde691b55cdd7678a |
| comparison-result.json | 2e545a725cde34e9d1bafdfef5f1b29b2dc8afd3553ac84b5eda599502772aff |

## 失败后的有限诊断边界

只读源码显示 `KnowledgeSearchProfile.freeze()` 使用 `Map.copyOf(sourceFields)`，而 `buildSearchBody()` 将该映射的遍历次序直接变成 `_source.includes` 数组，跨 JVM 不保证一致。新增离线测试实际复现无稳定顺序；最小修复固定字段投影升序，字段集合、条件、向量、授权及规范hash校验均不变。

此缺陷与本批每条POST规范hash不一致相符，但有限资产未保存请求正文，不能证明它是唯一差异。修复只有 non-live 证明，不修改本目录任何原始 JSON，不把本次终态改为有效，不重新运行或生成盲标。下一次真实验证必须另作独立执行决策。

修复本地提交：`3f642db283458da37847a4d210f9665bc696384e`。同一任务中未参与修改的只读执行单元检查源码、有限JSON及11项hash，定向复评无未解决Blocker/Major/Minor；未重跑主执行者测试，不冒充外部人员或人工效果评审。

实际 non-live 验证：

```text
serviceCenter/mvnw.cmd --offline --batch-mode -f serviceCenter/pom.xml -pl :es-query-service -am test
  es-query-service: 108 tests, 0 failures/errors/skips
  common-security: 21 tests, 0 failures/errors/skips

agent-runtime/.venv/Scripts/python.exe -m pytest
  tests/evaluation/knowledge/test_rebuild_b_comparator.py
  tests/evaluation/knowledge/test_rebuild_b_local_transport.py
  tests/evaluation/knowledge/test_rebuild_b_local_runner.py
  tests/evaluation/knowledge/test_rebuild_b_reuse_binding.py
  tests/evaluation/knowledge/test_rebuild_b_review.py -q
  183 passed
```

没有重新执行全量Python、其他Maven模块、真实Spring全链、人工质量评价或发布；没有新增本批之外的真实请求。
