# B 独立无付费启动预检（2026-10-02）

维护者重新授权新的独立验证批次。本目录是新 run 的一次预检，不复用或续跑任何历史失败目录，不代表 B 对照或 UAT 通过。

- run：`knowledge-b-startup-20261002-02`；分支 `codex_0915`；frozen HEAD `35d108ecfcf4e3563b09b99844e1333a83c4db59`，开始时工作树干净。
- 终态 `ready / complete`，退出码 0。版本化 runner 使用修复后的绝对 `JAVA_HOME/bin/java.exe`，冻结 archive 离线 Maven 构建成功（`-DskipTests`，不是测试证明）。
- JAR SHA-256：`3a787751ab0cb92b1dd021745857c3569251dee539a27db27710080a4fa58c99`。
- ES 元数据 HTTP 30/30；随机独占临时 alias 写 4/4；baseline/candidate readiness 各 3/1，上限各60。生产 alias 未切换。
- typed/physical search、query embedding、rerank、paid、JWT HTTP、retry/resume 全为0；proxy violations 为0。没有读取模型密钥、执行题目或重算语料向量。
- 两个自有 Java 进程停止，临时 alias 移除；结束后现场检查19211、19212、19311、19312均无监听。没有停止已有用户服务。
- 构建来源10份历史有限资产及冻结配置由版本化入口核验。四份新 JSON 生成后保持字节不变；启动成功不证明正式冻结、质量、人工评价、发布或回滚。

实际入口为 `agent-runtime/tests/evaluation/knowledge/rebuild_b_local_runner.py`，在 runtime 项目 venv 中仅为该进程设置当前 runtime/corpus 源码 `PYTHONPATH`，并置空子进程 `LLM_API_KEY`（不读取原值）：

```powershell
& 'D:/codex/agent-runtime/.venv/Scripts/python.exe' -m tests.evaluation.knowledge.rebuild_b_local_runner `
  --startup-preflight-only --run-directory 'D:/codex/knowledge-corpus-tools/evidence/knowledge-b-startup-20261002-02' `
  --baseline-port 19211 --candidate-port 19212 --baseline-proxy-port 19311 --candidate-proxy-port 19312
```

| 原始资产 | SHA-256 |
|---|---|
| startup-input.json | fd504f95c8e1c904789429975ba669d30d52359889950b29b01ca50f7e84facc |
| startup-attempt.json | c8fbb4f5f1b8dc3cef2a66cc3e13630ece240f4be6a896e1b5872d876153232d |
| startup-java-attestation.json | 8ae7423273fdd46cf09ee1a0043a9bf29f2f8443f364d7e23be5946bbb050bfb |
| startup-result.json | 65cb5d3eff1b73a860690d88ac3daefbffd4431b8febb2216c07bed46ffc03db |

下一阶段仍须 MEASURE 零推理预检、当前两臂完整扫描及新正式冻结，所有 gold、阈值与预算沿用既定确认。
