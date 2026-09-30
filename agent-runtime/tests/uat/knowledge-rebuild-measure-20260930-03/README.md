# MEASURE 独立启动预检：失败终态

本目录只保存一次构建与无推理启动预检的有限证据，不是正式效果运行。构建和启动输入绑定 `a03486e653a69c434ca18fd5cec943e0aa243881` / `codex_0915`；五个 Maven 构建成功仅证明构建范围，不代表测试或 UAT 通过。

启动标识：`codex-knowledge-measure-startup-4c13980517e24c3eabf1165e9c22036f`。终态 `startup_preflight_failed`，阶段 `proxy_start`；现场错误为 `knowledge.measure.port_owner_mismatch`。没有启动正式 case、消费模型授权或产生效果结论，不得补跑或覆盖本次结果。

模型、embedding、rerank 调用均为 0，`runtimeKeyRead=false`。绑定前检 witness 记录两个只读 ES 元数据 HTTP attempt；代理计数未能取得，`metadataEsHttp`、`typedSearchEsHttp` 和 `proxyViolations` 保持 `null`，不得补写成 0。有限结果报告自有进程已退出；执行后现场检查 18090、19201、19202、19203、19313 无监听。现场观察不等同于 JSON 的独立进程遥测。

没有正式 manifest、authorization、consumed、case journal 或模型结果。此前失败批次及历史资产保持不变。

| 资产 | SHA-256 |
|---|---|
| build-attestation.json | c6eb1a2073135f2b5f755d1495769532db7af8ad70f83979e8d4c902d9b1dc26 |
| startup-input.json | cc3e76c2207fd4afdc98bde7a2d484fa16989d43306ba219c6e3aa9e4d2c2d5e |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | 4e6dbec746d398ef687f00bb450c5643b1ee91169f08a8bb899563bbfbf87b7d |

后三项从独占 OS 临时目录精确复制，字节保持一致。大型 JAR、日志、密钥、JWT、正文和向量不进入 Git。
