# 产品标识头透传修复后的独立启动预检

日期：2026-10-02。范围仅为私有测试代理修复及一次新的无付费启动预检，不执行 B 对照、正式 MEASURE、真实效果 UAT 或发布。

## 实施与验证

- 分支：`codex_0915`；诊断 HEAD：`1c3ad5172bb2c01ad84825de88a52b3e917551ac`。
- 仅修改 `knowledge_rebuild_measure_startup.py` 的私有代理与直接 harness 测试。
- 上游实际返回的 `X-Elastic-Product` 单独透传；缺失时不补造，普通错误值不改写。重复、空、超过 64 字符或含控制字符的值拒绝；不转发 Cookie 或其他新增响应头。
- 路径、方法、请求/响应大小、上游固定地址、写入拒绝、调用上限、健康检查及客户端产品校验保持原边界。没有修改公共 DTO、生产配置、索引或 alias。
- 定向 pytest：`70 passed in 40.62s`，包括真实本地 HTTP 代理响应检查和危险 header 反例；没有真实 ES/BGE/模型调用。
- strict mypy：`Success: no issues found in 1 source file`；compileall、PowerShell AST、Git diff 检查通过。
- 上述为定向验证和作者自审，不是独立评审或全量 Python/Maven 回归。
- prepare 的当前 HEAD 构建通过，使用 `-DskipTests`，不代表 Maven 测试通过。

## 本次唯一预检结果

- 启动 ID：`codex-knowledge-measure-startup-cba19564f48646fa898fd1259b991dfc`。
- 原始终态：`startup_preflight_failed`，阶段 `cleanup`，固定执行错误 `knowledge.measure.startup_cleanup_failed`。
- 预检已越过先前 `es_ready` 失败位置，经 agent 启动和内存登录到达 Runtime ready；最后有限就绪观察为 Runtime HTTP 200。
- 临时 ES 日志的固定标记未再观察到 health check failed 或 missing product header。这仅说明本次观察，不证明所有未知故障都不存在。
- Runtime 正常关闭信号与客户端关闭 marker 检查已经通过；失败发生在随后自有进程清理核实。
- 原结果 `ownedProcessesStopped=false` 保持不变。结束后另行只读检查，18090、19201、19202、19203、19313 无监听，相关 Java/Python 服务进程数量 0；不能将后验状态改写为原始清理成功。
- 外部模型、embedding、rerank 均 0，runtimeKeyRead=false；没有执行查询用例或真实付费批次，没有自动重跑。
- 本次启动元数据硬上限仍为 48，search 上限为 0。但原始失败结果的 `metadataEsHttp/typedSearchEsHttp/proxyViolations` 为 null，不能报告成实际 0 或推算具体总数。

## 仍需处理的清理及证据缺口

当前 `Test-OwnedProcessesStopped` 在子进程核实未知标志为 true 或某个受控进程仍未退出时返回 false。此次实际触发哪个条件没有保存有限原因，不能仅凭后来端口空闲判定是误报，也不猜测 PID、控制台或 CIM 根因。

失败计数缺口可以从代码确认：成功进入 cleanup 前已有 `$startupCounts`；异常分支只尝试从仍存活的代理重新读取，或回退 `$proxyCounts`，没有保留此前的 `$startupCounts`。代理已停止时丢失计数，故终态出现 null。旧结果不补写、不改判。

下一步建议最小补充私有工具：记录固定枚举的清理失败原因，并保留已获得的有限计数；保持所有权、PID/创建时间检查与失败关闭，不以端口无监听替代清理契约。先 non-live 复现和验证，只有根因与修复依据成立后才进行新的独立启动预检。本次未实施该后续修复。

曾尝试追加一个纯本地合成进程拓扑观察命令，执行工具在创建进程前拒绝；未执行，未据此得出结论，也没有绕过该拒绝。此次只保留已有实际预检及只读源码观察。

## 原始产物完整性

| 文件 | SHA-256 |
|---|---|
| build-attestation.json | 267fcf46832c37bf29642aee2a9008e14a34f08a2092622e79bfb5e0eec725cc |
| startup-input.json | e0822fddfddcdaabdfb805c4c4131b67a73e41cbc22b937e537673c17eda2167 |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | e61e0800a65c5fd56ae5669d5ac532226e2a49153d9cbef388764458f7a2fa5f |

文件从本次身份核实的独立临时目录复制，复制后逐文件 SHA 相等。原始日志不保存，固定布尔标记单独保存；不保存密钥、JWT、原始模型或业务响应。旧历史资产和终态保持不变。

代码修复及本次有限证据仅本地提交，不推送，不同步主目标工作包或 UAT 状态。整次预检仍失败，不据此放行正式验证。
