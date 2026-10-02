# 清理原因诊断后的独立无付费启动预检

日期：2026-10-02。仅执行一次新的独立启动预检，不执行 B、MEASURE、效果 UAT 或发布，不复用历史失败目录。

## 基线与执行

- 分支 `codex_0915`，诊断 HEAD `d9f3a3b9a0924a07b16b08a811364a3661522254`，起始工作树干净，18090、19201、19202、19203、19313 无监听。
- 使用版本化 `knowledge_rebuild_measure_prepare build` 生成本次构建证明，再运行 `run-knowledge-rebuild-measure-v1.ps1 -StartupPreflightOnly`。
- 构建使用 `-DskipTests`，只证明构建成功，不代表 Maven 测试通过。
- 子执行环境清空模型密钥；未读取真实密钥，未执行题目、模型、embedding 或 rerank。
- 此次没有修改生产代码、配置、索引或 alias，也未更新主目标计划与验收状态。

## 唯一终态与已确认结论

- 启动 ID：`codex-knowledge-measure-startup-f3ae13d7443f4a66b553d65e8843506e`。
- 原始终态 `startup_preflight_failed`，阶段 `cleanup`，执行器报 `knowledge.measure.startup_cleanup_failed`。
- Runtime 就绪观察为 ready，HTTP 200；此次不再是 es_ready 超时。
- `cleanupIssues=["unexpected_child"]`，`ownedProcessesStopped=false`。这证明清理枚举发现至少一个未通过 `Test-ExpectedPythonChild` 的直属子进程；并未证明其真实类型或具体身份失败原因。
- 代理已停止后成功保留计数，`proxyCountsSource=last_validated_snapshot`。原结果报告 `metadataEsHttp=9`，这是最后一次已验证快照（含启动绑定计数），不是独立证实的最终总数。
- `typedSearchEsHttp=0`、`proxyViolations=0`、`modelHttp=0`、`embeddingHttp=0`、`rerankHttp=0`、`runtimeKeyRead=false`。
- 预检结束后只读核查五个目标端口均无监听；不能据此改写原始清理失败结论。

## 尚未确认与后续建议

当前不能判定该子进程属于 Windows 控制台辅助进程、Python 身份差异或其他情况。不得忽略未知子进程、扩大 Kill 范围，或把事后端口空闲代替所有权证明。

下一步最小诊断应区分 proxy/runtime 角色和身份不符的固定原因（例如父关系、可执行文件、命令标记、创建时间或元数据缺失）；不保存 PID、完整路径、命令行和异常全文。先 non-live 验证，之后另行执行新的独立无付费预检。此次未实施或执行该后续步骤，也未放行正式验证。

## 原始有限资产完整性

| 文件 | SHA-256 |
|---|---|
| build-attestation.json | 9fb9d4568080a8f72799b8a6533578413cd095d89de8c27526a6292232906d8e |
| startup-input.json | 35829069644ccf4a0c15730a76c0e90bba375f0b9364b26f3568c806f2db193d |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | 54bec4a1dc8ab3fdf164cc25b3445592d9c2e56482253c85fa3cfb7995c272bd |

启动输入、attempt 和结果从本次明确身份的临时目录复制，逐文件 hash 一致；不提交原始服务日志、密钥、JWT、正文、向量或模型响应。历史资产字节及终态保持不变。本次仅本地提交，不推送。
