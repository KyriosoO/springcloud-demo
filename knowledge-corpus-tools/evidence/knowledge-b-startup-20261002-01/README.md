# B 独立启动预检有限失败证据（2026-10-02）

本目录记录维护者新授权的一次无付费启动预检，不能复用、补跑、续跑或作为 B 质量对照证据。旧失败批次保持不变。

- run：`knowledge-b-startup-20261002-01`
- 起始分支：`codex_0915`；frozen HEAD：`7f0eacb54824b45eb20fe19e0ba177ec5609b19d`；启动时工作树干净。
- 唯一终态：`not_ready`；阶段 `java_readiness`；有限原因 `java_exited`；退出码 1。
- 冻结 Git archive 的离线 Maven 构建成功（`-DskipTests`，不是 Maven 测试通过证明）。JAR SHA-256：`ad0c966148485c37121ee2e7a18836f97bcf37bcfa3a3ed8f490861377ae1028`。
- ES 元数据 HTTP：12/30；本次随机临时 alias 写操作：4/4；两臂 readiness 请求：1、0（各上限60）。生产 alias 未切换。
- typed/physical search、query embedding、rerank、paid、JWT HTTP、retry、resume 均为 0；proxy violations 为 0。
- 两个自有 Java 进程已停止，临时 alias 已移除；结束后现场核查九个计划隔离端口均无监听。未停止用户已有服务。
- 本批没有读取 `LLM_API_KEY`，没有运行题目、扫描全记录、正式 B 冻结、MEASURE 构建/预检/冻结或授权消费。没有新候选索引或语料写入。

## 根因核查边界

退出后只读检查确认：当前 PATH 的 `java` 为 Java `1.8.0_503`，而 `JAVA_HOME` 指向 JDK `25.0.2`；`serviceCenter/pom.xml` 要求 Java 25。冻结 runner 使用裸 `java` 启动，并原样传递 PATH；离线 Maven 使用 `JAVA_HOME`。这是已证实的编译/启动 Java 选择不一致，Java 8 不能运行该项目的 Spring Boot 3.5/Java 25 产物。

原始 Java stderr 未保存，不能补造其异常文本或声称取得了具体 JVM 错误栈。后续私有工具修复只以 fake、类型及源码复核验证，不改本批终态，不通过重新启动来补证本批。MEASURE launcher 已显式选择并检查 `JAVA_HOME/bin/java.exe`，无需为此修改其代码。

## 实际启动命令

在 `D:/codex/agent-runtime` 中，为该验证进程指定当前源码路径，并将子进程的模型密钥变量置空（不读取原值）：

```powershell
$env:PYTHONPATH = 'D:/codex/agent-runtime/src;D:/codex/knowledge-corpus-tools/src;D:/codex/agent-runtime'
$env:LLM_API_KEY = ''
& 'D:/codex/agent-runtime/.venv/Scripts/python.exe' -m tests.evaluation.knowledge.rebuild_b_local_runner `
  --startup-preflight-only `
  --run-directory 'D:/codex/knowledge-corpus-tools/evidence/knowledge-b-startup-20261002-01' `
  --baseline-port 19211 --candidate-port 19212 `
  --baseline-proxy-port 19311 --candidate-proxy-port 19312
```

命令只执行一次，返回上述失败终态。不要再次执行这个目录。

## 原始有限资产 SHA-256

| 文件 | SHA-256 |
|---|---|
| startup-input.json | 3a7ec382af2f3c899d617dcbce05410ba16179748d3ef2ffc395d3c4f8ca84cf |
| startup-attempt.json | 43ba1a0c4d31c4690ce34338ed2052c1de7a412697fee7dbb92617e04ff00691 |
| startup-java-attestation.json | f6e422c48423915a820364bd8312c77ea47afbf6c9b90f99193ed256b2425667 |
| startup-result.json | 5444f0c38fd81e74c6d85de3d3801e51b08c23fa58df8880d12d81d9f35b5bd9 |

四份 JSON 均为该次版本化工具生成的有限资产，创建后不修改。本说明不代表功能、安全、召回、回答或发布验收通过。
