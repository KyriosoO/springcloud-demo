# 新独立 B 无推理启动预检（2026-10-03）

维护者在启动与清理修复后要求继续现有目标。本目录只保存新批次的启动证明，不复用旧失败目录，不证明正式比较或质量通过。

- run：`knowledge-b-startup-20261003-01`；clean HEAD `f01540da1b3fced7881821a73703191f84059e3d`，分支 `codex_0915`。
- 终态 `ready / complete`，exitCode=0。冻结 archive 离线 Maven 构建成功（`-DskipTests`，不是测试通过证明）。
- 元数据 ES HTTP 30/30，随机独占临时 alias 写4/4；两臂 readiness 3/1，各自上限60。
- typed/physical search、query embedding、rerank、paid、JWT HTTP、retry/resume均0；proxy violations=0。未读取模型密钥，未查询题目或重算语料向量。
- 自有 Java 进程已停止，临时 alias 已移除；结束后19211、19212、19311、19312无监听。用户既有9200/8908/8909服务未停止，生产 alias 未切换。
- JAR SHA-256：`e8aeeccf5452ff9e0985e5856ecf80d1c2c1c7a52a2946901fed95d192f0d573`。

实际入口（仅作本次追溯，不可复跑本目录）：

```powershell
& 'D:/codex/agent-runtime/.venv/Scripts/python.exe' -m tests.evaluation.knowledge.rebuild_b_local_runner `
  --startup-preflight-only --run-directory 'D:/codex/knowledge-corpus-tools/evidence/knowledge-b-startup-20261003-01' `
  --baseline-port 19211 --candidate-port 19212 --baseline-proxy-port 19311 --candidate-proxy-port 19312
```

仅为执行进程设置 `JAVA_HOME=C:/Program Files/Java/jdk-25.0.2`、当前 runtime/corpus 源码 `PYTHONPATH`，并置空 `LLM_API_KEY`，不读取原值。四份原始 JSON 生成后不改写。

| 原始资产 | SHA-256 |
|---|---|
| startup-input.json | 15ea201a985a356369154010c38355738d1ef5a43080cc29ea27bda11c29305b |
| startup-attempt.json | 086c2f9572a8ad0d42e4d5f8e357775ba12dc2efcc214a8be89b1953db1a9a4d |
| startup-java-attestation.json | a326c2bb63416b8745f6cd151d25ecc84a37b163b4016fac66fb85e5fa5006bf |
| startup-result.json | 4a04dd8ad5a941bdf0c5aa9618675d9229571a10be380b5bed69767e3cac9f77 |

后续正式 B 仍须新两臂全记录扫描、新冻结及一次执行；MEASURE 使用自己独立的新构建、manifest、authorization与快照。gold、阈值和预算不变。只本地提交，不推送、不发布。
