# 子进程身份诊断：独立无付费启动预检

日期：2026-10-03。仅执行一次新的启动预检，不执行 B、MEASURE、真实效果 UAT 或发布。

## 修订与直接验证

- 基线分支 `codex_0915`，起始工作树干净。
- 私有 launcher 新增固定字段：角色 proxy/runtime、有限进程类型和首个身份失败原因。去重仅使用固定枚举，不记录 PID、可执行文件路径、命令行或异常全文。
- `Test-ExpectedPythonChild`、PID/创建时间核实、Kill 范围、超时及失败关闭不变。进程名称分类不构成可信身份认证，不参与清理放行。
- 定向测试 `15 passed, 75 deselected in 15.65s`；完整 harness `90 passed in 40.01s`；strict mypy 1 文件、compileall、PowerShell AST 和 diff 检查通过。
- 开发时发现新诊断 switch 表达式的语法错误，修正后执行上述验证；未删除断言或弱化预期。
- 上述是私有工具定向验证及作者自审，不是独立评审或全量 Python/Maven 回归。
- 工具本地提交 `20a5cc9174978db44dea8a67eee92c504d74545e` 后，按该干净 HEAD 重新构建并执行本次唯一预检。构建使用 `-DskipTests`，不代表 Maven 测试通过。

## 本次唯一结果

- 启动 ID：`codex-knowledge-measure-startup-7e6bf46d7e5f48ce810ab3005e6e49f9`。
- 终态 `startup_preflight_failed`，阶段 cleanup，执行错误 `knowledge.measure.startup_cleanup_failed`。
- ES 和 Runtime 就绪流程已完成，最终就绪观察为 Runtime HTTP 200、ready；本次不是 es_ready 超时。
- `cleanupIssues=["unexpected_child"]`；`cleanupChildObservations=[{"role":"proxy","imageKind":"console_host","identityFailure":"executable_mismatch"}]`。
- 已确认的触发点：清理枚举发现 proxy 的直属子进程，其名称归类为 console_host，且可执行文件不符合预期 Python 路径。未保存或认证该辅助进程的完整身份，不据此允许任意同名进程。
- launcher 当前以 `Start-Process -WindowStyle Hidden` 启动 Python。上述观察支持“隐藏窗口启动产生的辅助控制台进程与只允许预期 Python 子进程的清理契约不匹配”的根因判断；不涉及检索、索引、模型或知识正文。
- `metadataEsHttp=9`，来源为 `last_validated_snapshot`，不是独立证实的最终总数。search、proxy violations、模型、embedding、rerank 均为 0，`runtimeKeyRead=false`。
- 原始 `ownedProcessesStopped=false` 保持不变。结束后只读核查 18090、19201、19202、19203、19313 无监听，不改判清理成功。

## 建议的最小修复方向

优先评估不创建独立控制台的 Python 启动方式，保留可核实 Process 对象、子进程身份、参数、环境隔离、日志重定向及取消/关闭行为。不能只按 conhost 名称放行、忽略未知进程、扩大 Kill 范围或用端口空闲代替所有权核实。

该启动方式修复尚未实施。应先完成纯本地 non-live 生命周期验证与评审，再进行新的独立无付费预检；本轮不自动追加第二次运行，不放行正式验证，也不同步主目标工作包终态。

## 原始有限证据完整性

| 文件 | SHA-256 |
|---|---|
| build-attestation.json | 0f1e236589822123282ea126b64a0cc4de9b21996d3dcfed67ae916d1449cf2d |
| startup-input.json | 41f6b390874a83f2db1a9877359a81f53be9e7b43ad6c699934431c192b0ac70 |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | 758e4de85e469243f75db547ed357d9f00a90b0b86e05c9b37fbac3378eafec9 |

原始 startup 输入、attempt 和结果从本次身份明确的临时目录复制，逐文件 hash 一致。未提交密钥、JWT、正文、向量、原始服务日志或模型响应；历史资产未修改。仅本地提交，不推送。
