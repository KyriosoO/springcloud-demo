# MEASURE 新独立无付费启动预检：失败终态

本目录保存维护者新授权后的独立启动预检，不是正式12题测量，不复用任何历史失败目录。

- 分支 `codex_0915`；构建 HEAD `6e81264d89721afe1c631b544827d07e5e212343`，构建前工作树干净。五个模块的版本化 `clean` 构建成功，均为 `-DskipTests`，不是 Maven 测试证明。
- 唯一启动标识 `codex-knowledge-measure-startup-424ac4ce24354915ad8a95b9f9b07a19`；终态 `startup_preflight_failed`、阶段 `es_ready`。原始有限 reason 为 `launcher_validation_or_runtime_failure`；现场 shell 返回 `knowledge.measure.readiness_timeout`。
- 元数据 ES HTTP 48/48（绑定前检2次，代理启动/Profile及健康最多46次）；typed search、model、embedding、rerank全为0，proxy violations为0，`runtimeKeyRead=false`。未创建正式 manifest/authorization，未消费模型预算、未执行任何case。
- 原始结果的 `ownedProcessesStopped=false` 表示未通过清理核实，保持原样，不能因后续观察改写为true。执行后现场检查18090、19201、19202、19203、19313无监听，CIM亦未发现本次目标Java/Python角色；这只是后续观察，不替代原始清理遥测。
- 原始服务日志由launcher按既有敏感信息边界清理，不能补造ES健康响应或断言具体健康失败根因。仅保存有限原因、hash和计数，不包含密钥、JWT、正文、向量或原始模型响应。
- 本次 MEASURE 预检终止，不补跑、不续跑、不重新冻结本目录。B预检具有不同目录、端口和独立直接依赖，其有限成功不代替本预检，也不因本预检失败自动作废。

实际使用 `knowledge_rebuild_measure_prepare build`，然后版本化 `run-knowledge-rebuild-measure-v1.ps1 -StartupPreflightOnly -BuildAttestationPath <本目录/build-attestation.json>`。两阶段只执行一次，模型密钥变量在执行子进程置空，没有读取原值。

| 原始资产 | SHA-256 |
|---|---|
| build-attestation.json | d99f194399513abef600848c9fbf97a7a9f9ee1d89add774c834cec01c0bd40e |
| startup-input.json | f8228c5857272e8c80f1c208386721ab4f476f064cd769928db82ee7da676958 |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | ed2a948a133bbc4ea03db5735aec621574ed0c5800b7d4712e2891f75d70aa15 |

后三份从本次独占 OS 临时目录精确复制并逐项比对SHA-256，字节保持不变。没有正式效果、人工评价或发布通过结论。
