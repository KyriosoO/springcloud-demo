# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 1 |
| 依据文档数量 | 8 |
| 评审代码范围 | `agent-service` Invocation model、Planning Artifact、Execution Core、Start/checkpoint/finalization/recovery 生命周期、MyBatis/SQL 持久化、Context scope codec 及直接相关测试 |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 通过；4 项生命周期、一致性及取消语义问题已修复，无剩余可处理问题 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `02_可信执行内核与Invocation生命周期_L2实施详细设计_v2.0.md` | detailed_design | 0 | 是 | 已读取 | 当前主文档 |
| `01_Agent契约生成与治理_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取边界 | Runtime/Planning 契约前置 |
| `03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取边界 | Authorization/Context/Result Security 参与者 |
| `06_原子迁移扩展验证与清理门禁_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取边界 | 迁移与门禁约束 |
| `../Agent契约与规划架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | Planning Artifact 与契约 L1 |
| `../Agent能力执行内核架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | 主要执行内核 L1 |
| `../Agent元数据与上下文安全架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | 安全参与者 L1 |
| `../Agent目标架构总览_v1.0.md` | architecture | 3 | 否 | 已读取相关约束 | L0 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | 第 6、10.1 节 | 当前仅允许 CHAT origin、ConversationScope 和单一 Invocation 状态机 | `invocation/model/**`、`StartTxService`、`agent-p0.sql` | 符合 |
| DOC-C-002 | 第 8、10.4～10.6 节 | Planning Artifact 使用 PAI-1 逻辑 identity；checkpoint 确认提交后才可进入 Core | `PlanningArtifactCanonicalizer`、`ExecutionCommand`、`CheckpointTxService`、`ExecutionLifecycleService` | 修复后符合 |
| DOC-C-003 | 第 8、10.5 节 | Core 必须检查 absolute deadline/cancellation、artifact identity 和 Registration identity，失败后停止后续阶段 | `CancellationSource`、`ExecutionCore` | 修复后符合 |
| DOC-C-004 | 第 10.8、13、14 节 | 终结只能由 PROCESSING 经 CAS 进入一个终态；CAS 输家和 commit unknown 必须重读权威原子单元 | `FinalizationTxService`、`ExecutionLifecycleService` | 修复后符合 |
| DOC-C-005 | 第 10.8、14、16 节 | Recovery 仅原子终结 Invocation/Turn，不重执行，并使用有界批次 | `InvocationRecoveryService`、`AgentInvocationRecordMapper` | 修复后符合 |
| DOC-C-006 | 第 10.7、12 节 | Context scope 仅接受 CONVERSATION；数据库 shape、checkpoint sequence/hash 和 rowVersion 同步闭合 | `ContextBindingSupport`、`agent-p0.sql`、`PlanningCheckpoint` | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|---|
| CR-001 | high | concurrency_consistency | `CancellationSource.java`、`ExecutionCore.java` | 第 8、10.5 节 | `token()` 返回不可变快照，令牌分发后再调用 `cancel()` 对旧令牌不可见；Core 只检查 deadline，未主动检查 cancellation | 已取消请求仍可能进入授权、Context、Validator 或 Handler，形成无效下游调用和错误终态 | 改为共享的原子取消状态；Core 在 preflight 和阶段门禁统一返回 typed cancellation，并增加回归测试 |
| CR-002 | high | transaction_consistency | `FinalizationTxService.java`、`ExecutionLifecycleService.java` | 第 10.8、14 节 | 终结 CAS 失败直接抛错，事务提交结果未知也没有独立事务重读；SUCCESS 路径在 CAS 前先插结果/Context | 并发终结输家无法服从权威终态；提交响应丢失时可能向调用方伪报失败，且本地候选工作在确认 CAS 所有权前发生 | SUCCESS 改为先 CAS 再写同事务参与者；CAS 输家重建权威终态；Lifecycle 捕获提交异常后用 `REQUIRES_NEW` 对账 |
| CR-003 | medium | state_consistency | `ExecutionLifecycleService.java`、`ExecutionCore.java`、`ExecutionCommand.java` | 第 10.5、10.6 节 | `ExecutionCommand` 原在 checkpoint 提交后才构造，Core 也未再次校验 artifact identity | 无效或被替换的 Planning Artifact 可能先写入权威 checkpoint，随后才在内存中失败 | 将命令完整性校验前移到 checkpoint 之前，并在 Core preflight 再次复算 PAI-1 digest |
| CR-004 | medium | resource_control | `InvocationRecoveryService.java` | 第 14、16 节 | `batchSize` 只要求正数，没有硬上限 | 错误配置可在一个事务内扫描并锁定过多 PROCESSING 行，放大恢复任务对在线流量的影响 | 增加 1～1000 硬上限及负向测试 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | medium | 当前主文档第 12.2 节 | 数据字典不一致 | 文档写为单字段 `output_contract_schema`，实际 SQL/实体按 `output_contract_namespace`、`output_contract_name`、`output_contract_version` 保存完整 ContractRef | 后续迁移或审计实现可能误建字段，丢失 namespace/name 语义 | 获得文档修改授权后，以当前 SQL 的三字段 ContractRef 分解为准修正文档 |
| DOC-002 | low | 当前主文档第 19 节 | 测试路径漂移 | 列出的 `architecture/SingleAgentSeamArchitectureTest` 和 `CapabilityRegistrationTest` 不存在；仓库实际由 `LifecycleSeamArchitectureTest`、`CapabilityRegistryTest`、`KernelCapabilityRegistrationTest` 覆盖对应约束 | 按文档逐路径执行会漏报“文件不存在”，但现有等价门禁仍有效 | 获得文档修改授权后更新为当前测试类名 |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | `CancellationSource.java`、`InvocationModelTest.java` | 已分发 token 共享原子取消状态，取消单向且线程可见 | CR-001 | 已修复 |
| 1 | `ExecutionCore.java`、`ExecutionCoreTest.java` | preflight/阶段门禁检查 cancellation；Core 复算 Planning Artifact identity | CR-001、CR-003 | 已修复 |
| 1 | `ExecutionLifecycleService.java`、`ExecutionCommand.java`、`ExecutionLifecycleServiceTest.java` | artifact 校验前移至 checkpoint 前；增加 commit-unknown 权威对账 | CR-002、CR-003 | 已修复 |
| 1 | `FinalizationTxService.java`、`FinalizationTxServiceTest.java` | CAS 先行；输家丢弃候选并重建权威终态；独立事务提供提交结果未知重读 | CR-002 | 已修复 |
| 1 | `InvocationRecoveryService.java`、`InvocationRecoveryServiceTest.java` | 恢复批次增加 1～1000 安全边界 | CR-004 | 已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-service -am '-Dtest=InvocationModelTest,ExecutionCoreTest,FinalizationTxServiceTest,ExecutionLifecycleServiceTest' '-Dsurefire.failIfNoSpecifiedTests=false' test` | 通过 | 20 passed |
| 1 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-service -am '-Dtest=InvocationModelTest,ExecutablePlanningResultTest,ExecutionCoreTest,PlanningCheckpointTest,ContextBindingSupportTest,LifecycleSeamArchitectureTest,StartTxServiceTest,ExecutionLifecycleServiceTest,FinalizationTxServiceTest,InvocationRecoveryServiceTest,InvocationSchemaTest,CapabilityRegistryTest,KernelCapabilityRegistrationTest' '-Dsurefire.failIfNoSpecifiedTests=false' test` | 通过 | 48 passed；含 ArchUnit、schema、CAS/recovery 与 Core 定向门禁 |
| 1 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-service -am test` | 通过 | Reactor 共 559 passed，其中 `agent-service` 438 passed |
| 1 | `python agent-runtime/scripts/check_contract_drift.py` | 通过 | active Python codegen 可重复且 provenance 有效 |
| 1 | `git diff --check` | 通过 | 无空白错误；仅已有 CRLF/LF 转换告警 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | CAS 输家及 commit-unknown 目前由 mock 单测验证，未进行真实 MySQL 双事务故障注入 | 本仓库现有测试未提供可复现的提交响应丢失或并发事务容器夹具 | 在发布门禁中补 MySQL/Testcontainers 并发终结、commit-unknown 和整体回滚集成测试 |
| RISK-002 | low | recovery 只有硬上限，实际调度频率和常用 batchSize 仍由未来调用方决定 | 当前仓库未发现 recovery scheduler 或独立配置入口 | 接入调度器时增加显式配置校验、指标和连续失败告警，并保持值不超过 1000 |
| RISK-003 | low | Maven 测试存在 Mockito 动态 agent 的 JDK 未来兼容告警 | 当前 JDK 仍允许 Byte Buddy 动态加载，测试本次全部通过 | 依赖统一升级时按 Mockito 官方方式配置测试 agent，不为本次修复引入生产依赖 |

## 9. 结论

最终结论：
- 通过。

说明：
- 4 项问题均在第一轮完成修复并通过再评审。
- 未修改主详细设计、L0/L1 或关联文档；仅在本报告记录两项文档漂移，等待单独授权。
- 未扩展 Invocation 类型、外部协议或数据库字段，也未引入生产依赖。
