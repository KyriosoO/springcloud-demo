# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：是；目标文档已通过品审，但 P1_V2/P2_V3 全集仍为 In Review，尚未由用户确认 Approved，且 P1_V2/06 M0 实施授权未完成
- 审查类型：cross_layer
- 目标文档：`docs/design/P1_V2/05_有效资源预算与CapabilityLocalPort收敛_L2实施详细设计_v2.0.md`
- 上级文档：L0、契约与规划 L1、能力执行内核 L1、元数据与上下文安全 L1
- 关联文档：P1_V2/00～04、06，P2_V3/02、04～06
- 实际审查轮次：3
- 主要风险摘要：多 Contract 容器、资源与 Planning budget 混层、Provider 只拿摘要无法执行限额、Execution recheck 无单调证明、跨模块反向依赖、不可观测 retry、候选安全 binding 和清理矩阵不闭合等问题均已修复；当前无 S0/S1 遗留

## 2. 文档识别结果

- 识别文档类型：L2 实施详细设计
- 识别依据：文档定义 resource limit Java 类型、求交算法、Snapshot/recheck、四边界传递、capability-local operation SPI、配置迁移和测试门禁
- 文档状态：In Review；用户已授权修改目标文档
- 是否包含修订历史：是，已追加三轮评审修订原因、位置和内容
- 是否存在上级文档：是，四份 L0/L1 作为只读权威基线
- 是否存在关联文档缺失：否；本轮未修改上级或关联文档

## 3. 审查范围

| 序号 | 文档/代码 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---:|---|
| 1 | `P1_V2/05` | 目标 L2 | 是，全文 | 评审并修复资源限额和 capability-local port 通用设计 |
| 2 | L0 与三份单 Agent L1 | 上级架构 | 是，相关章节 | 核对同源限额、absolute deadline、Provider port 和 CHAT-only 演进约束 |
| 3 | `P1_V2/00～04、06`、`P2_V3/02、04～06` | 关联 L2 | 是，相关边界 | 核对 Definition、Authorization、Adapter SPI、Document limit/provider/candidate 边界 |
| 4 | `agent-api`、`agent-adapter-api`、`agent-service` 当前模块依赖与相关配置/代码路径 | 实现基线 | 是，相关文件 | 验证 Spring-free SPI 依赖方向和旧散预算/Runtime rewrite 迁移落点 |

## 4. S0 阻断问题

复审后未发现遗留 S0。首轮关闭 2 项：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 10、11 节 | Provider Operation Context 只有 `ResourceLimitReference`，没有可读取的实际 typed limits | Provider 无法按 Authorization Snapshot 冻结值裁剪输入/输出，只能重新读配置或忽略限额，破坏 L1 的四边界同源安全不变量 | 增加 Spring-free `CapabilityResourceLimitView.require`；Context 携带同一 Effective 对象的只读 view，reference 仅用于绑定核验 |
| 2 | 原第 10、13 节 | Contract 未定义逐维 `isSameOrStricter`，Execution recheck 也没有可执行的单调证明算法 | Permission/Policy 变化后可能接受扩大值，或仅比较 digest/对象身份产生授权绕过 | 冻结 contract property、逐维收紧证明、source-aware 交集、exact-version recheck 和无法证明即 fail closed |

## 5. S1 严重问题

复审后未发现遗留 S1。评审-修复循环关闭 13 项：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 6、10 节 | 当前公式提前引入 future Run/Task remaining budget，并声称由 P1_V2/06 落实 | 违反 L0/L1 的 CHAT-only 边界，把原子迁移文档变成未评审 Multi-Agent 事实源 | 当前 source 仅 Definition/Profile/Policy/Permission/optional Request；Run/Task 必须等待 future Multi-Agent L1 |
| 2 | 原第 10 节 | 单个 selected capability 仍使用 `Map<ContractRef,...>` 保存多个 Effective limits | 预留无需求层级，增加 ref/type/binding 错配和消费者遍历 | 收敛为单 Capability 单 ContractRef、单 typed immutable value |
| 3 | 原第 10.1、10.6 节 | `maxRepairAttempts` 与 rows/bytes/evidence 等执行资源混为 Execution budget | Runtime repair 与 Handler/Provider 资源所有权混乱，后续阶段可能重置或扩大预算 | 拆分 PlanningBudget、absolute deadline、capability resource limits、provider operational cap |
| 4 | 原第 10.2～10.5 节 | Declaration、contribution、dimension、source、resolver 输入和 canonical digest 不完整 | Profile/Policy/Permission/Request 无法确定性闭合，缺失来源可能被默认 unlimited | 冻结强类型 Java 结构、三个必需来源、可选 Request、稳定顺序和 canonical SHA-256 |
| 5 | 原第 10.8～10.10 节 | capability-local Port 缺少统一 typed request/outcome/metadata、deadline/cancellation/attempt 语义 | Provider 异常、迟到结果和重试次数无法被 Handler/Core 安全判断 | 冻结 Operation Context/Request/Outcome/Metadata、pre/post check、一次 attempt 和 typed failure |
| 6 | 原第 10.11 节 | Generated Text Candidate 仅为 marker，未冻结 evidence/citation/owner/operation/limit binding | 自由文本或串包 citation 可能绕过 Result Security | 增加具体 CandidateSecurityBinding、evidence/citation reference 和当前 Scope 复检规则 |
| 7 | 原第 10.12、19～20 节 | 配置/旧字段/Runtime rewrite 删除矩阵和 architecture gate 不闭合 | Validator、Handler、Projector 继续各读一份上限，形成隐式双轨 | 补齐逐路径删除、允许保留的 operational cap、零命中和原子切换门禁 |
| 8 | 第二轮第 8、19 节 | P1_V2/04 的 Adapter SPI 位于 `agent-adapter-api`，却引用 `agent-service` 的 Context/Token/Effective 类型 | 形成 `agent-adapter-api -> agent-service` 反向依赖，接口无法编译并破坏模块边界 | 将 read-only limit/context/cancellation/outcome SPI 放入 Spring-free `agent-adapter-api`；resolver/Effective 实现留在 `agent-service` |
| 9 | 第二轮第 10.9 节 | Provider attempts 使用可空/未知值，与“必须证明 0/1 次”门禁冲突 | SDK/mesh 暗中重试时可用 unknown 掩盖，计费和幂等风险无法审计 | 改为本地 client boundary 必知 `int providerAttempts`；不可观测则生产启动失败 |
| 10 | 第二轮第 10.11 节 | evidence/citation 仍为空接口，字段约束不能执行 | 实现可用任意对象满足 marker，无法检查 citation 到 evidence 的闭合关系 | 冻结具体 reference 字段、canonical digest 与同 binding 命中规则 |
| 11 | 第三轮第 10.9 节 | 通用 failure code 无法区分 provider stage timeout、absolute deadline、late result 和 security rejection | Handler 可能对安全拒绝或迟到响应执行错误 fallback，观测数据也无法判定自动重试/超时来源 | 补齐 `PROVIDER_TIMEOUT/LATE_RESULT/SECURITY_REJECTED` 等通用 code 并明确 termination 映射 |
| 12 | 第三轮第 10.11 节 | 通用 `GeneratedTextCandidate.candidateText()` 假设只有一个文本字段 | Document 的 answer/summary/bullets 被迫压扁或复制接口，通用层侵入具体输出结构 | 通用接口只暴露安全 binding；具体 output subtype 自行声明候选字段并逐字段校验 |
| 13 | 第三轮第 10.12 节 | 删除矩阵又允许 `AvailableCapability` 保留 Planning Budget 安全引用 | 与 P1_V2/03 的 AvailableCapability 固定字段冲突，并重新制造 Route 投影预算副本 | 明确 AvailableCapability 不携带任何 Planning/resource budget；Planning Budget 只属于 Planning request/checkpoint |

## 6. S2 一般问题

复审后未发现遗留 S2。关闭 3 项：初稿使用概括实现路径、Provider operation 时序容易被理解为新增持久状态机、Permission contribution 可能被误解为必须扩展 auth-service 公共 DTO。现已补齐具体类/路径/命令，明确 operation 只有不可变 metadata，并由 Authorization/metadata 内部的 contract-specific adapter 基于当前权限证据形成 contribution。

## 7. S3 建议优化

暂无当前必须修改的 S3。实现时可统一 operation type、failure reason 和 resource dimension 的低基数指标命名，但不得因此建立共享业务枚举或 Provider Orchestrator。

## 8. 架构设计审查结果

不适用；目标为 L2 详细设计。未发现必须先修改 L0/L1 的架构阻塞项。future Run/Task/Delegation budget 只作为演进说明保留，未创建当前接口、配置、存储或 source enum。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | 完整承接 Definition/Profile/Policy/Permission/Request 单调求交和四边界同源要求 |
| 唯一事实源 | 通过 | Authorization/metadata resolver 唯一计算；消费者只读同一 Effective view |
| 文件路径 | 通过 | adapter-api SPI、service resolver、contexts、security、Document 迁移和配置路径明确 |
| 类与方法 | 通过 | Declaration/Contract/Registry/Resolver/Effective/Context/Outcome/Candidate 均冻结 |
| 入参与返回类型 | 通过 | 单 Contract typed value、operation typed request/outcome、failure/metadata 完整 |
| 模块依赖 | 通过 | `agent-adapter-api` 仅依赖 `agent-api`；不反向依赖 `agent-service` |
| 校验逻辑 | 通过 | source/type/ref/dimension/strictness/digest/binding 全部 fail closed |
| 异常处理 | 通过 | disabled、unavailable、stage timeout、deadline、cancel、late、安全拒绝可区分 |
| 幂等与重试 | 通过 | operationId 只作关联；当前最多一次 outbound attempt，自动 retry 关闭 |
| 权限与风控 | 通过 | Permission adapter 在授权边界内；Provider 不接收 JWT/Scope/权限正文 |
| 候选安全 | 通过 | 文本和非文本 candidate 均需 operation/limit/evidence/current scope 校验 |
| 配置所有权 | 通过 | 业务限额迁 typed contribution；implementation config 只能进一步拒绝/缩短 |
| 测试设计 | 通过 | contract property、recheck、传播、attempt、candidate、cleanup 和架构门禁完整 |
| 可编码性 | 通过 | 无需回查 P1/D02 或上下文优化旧文档补通用资源/Provider seam |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 当前单 Agent/CHAT；future Multi-Agent 不提前落 Run/Task 类型或 ledger |
| 架构到详细设计一致性 | 通过 | L1 的 Effective limits、absolute deadline、capability-local port 和 candidate 安全均有实施结构 |
| 契约一致性 | 通过 | 单 ContractRef/type/digest/binding；公共 Runtime/API 不新增 Provider DTO |
| 授权一致性 | 通过 | Planning freeze 与 Execution currentness recheck 使用同一 contract 且只能收紧 |
| Core 边界一致性 | 通过 | Core 只传递，不 resolve、不读配置、不感知 Document 维度 |
| Adapter 边界一致性 | 通过 | Domain Adapter 延续双参数 SPI；capability-local request 内嵌唯一 Context，不互相替代 |
| Result Security 一致性 | 通过 | 最终 output 使用同一 limits、current ExecutionScope 和 candidate binding |
| 代码结构一致性 | 有条件通过 | 当前代码仍有散预算和 Runtime rewrite；由 P1_V2/06 纵向原子迁移统一关闭 |
| 扩展性一致性 | 通过 | 新 capability 只增加 subtype/contract/contribution/consumer/port，不修改 Core 算法 |

## 11. 是否建议进入后续阶段

- 是否建议继续评审下一份 L2：是，进入 `P1_V2/06`
- 是否建议进入编码实现：否；等待 P1_V2/P2_V3 全套串行评审和用户后续授权
- 是否建议先修订架构设计：否
- 是否建议先修订关联文档：否；P2_V3 的 Document 具体 subtype/DTO 将在其自身目标评审中按本文基线修正
- 是否需要用户确认：当前无需新增确认

## 12. 用户确认项

暂无。本轮只修改用户已授权的目标 L2 和评审报告。实施阶段若需要扩展 auth-service 公共权限 DTO、修改外部 Provider HTTP 合同或引入生产 SDK，须按用户规则另行取得公共契约/生产依赖变更授权。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 修订内容 | 是否阻断 |
|---:|---|---|---|---:|
| 1 | S0 | 第 10.2～10.8 节 | 让 Provider 获得同一 typed limits，并冻结逐维收紧证明 | 是，已修复 |
| 2 | S1 | 第 6、8、10.1～10.6 节 | 删除 future budget/多 Contract 预留并分离四类预算所有权 | 是，已修复 |
| 3 | S1 | 第 10.8～10.11 节 | 冻结 Spring-free operation SPI、一次 attempt、typed outcome 和 candidate binding | 是，已修复 |
| 4 | S1 | 第 10.12～10.14、19～20 节 | 闭合配置/旧路径清理、CHAT-only 与架构门禁 | 是，已修复 |
| 5 | S1 | 第 10.9～10.12、11 节 | 补齐 failure code、移除单文本假设、禁止 AvailableCapability 预算副本 | 是，已修复 |
| 6 | S2 | 第 10.2、13、19～22 节 | 澄清 Permission adapter、非持久状态语义、路径与评审记录 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | 初审并重构资源/Provider 主设计 | 11（S0=2、S1=7、S2=2） | 11 | 0 |
| 2 | 2026-07-13 | 模块依赖、attempt 可观测性和候选引用复核 | 3（S1=3） | 3 | 0 |
| 3 | 2026-07-13 | L0/L1、关联边界、failure/candidate/budget 终审并静态验证 | 4（S1=3、S2=1） | 4 | 0 |

## 15. 最终结论

> 全集终态注记（2026-07-13）：本文保留该文档逐轮评审的时点记录；P1_V2/00～06 与 P2_V3/00～07 全集评审现已完成且 S0/S1=0。当前实施状态和授权边界以目标文档第 1、3、23、24 节为准，本文不构成 Approved 或 M0 授权。

文档通过品审，不阻断继续串行评审 `P1_V2/06_原子迁移扩展验证与清理门禁_L2实施详细设计_v2.0.md`。本次执行 3 轮；最终 S0、S1 均为 0。当前实现偏差必须由 P1_V2/06 作为同一纵向原子单元关闭，禁止先删散预算/Runtime rewrite，而 Definition contract、Authorization freeze、operation SPI 或 Result Security 任一链路尚未就绪。
