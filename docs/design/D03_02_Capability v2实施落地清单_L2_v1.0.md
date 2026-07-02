# D03_02 Capability v2实施落地清单 - L2 v1.0

> 状态：D03 代码评审通过；本地 API/UI E2E 已验证；发布前环境回归待执行
> 适用阶段：D03 提交前状态归档  
> 上位依据：`D03_Capability v2跨服务原子切换_L2实施详细设计_v1.0.md`、`D03_01_UserPermissionAuthority权限权威源契约说明_L2_v1.0.md`、`D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md`、`D02_01_Capability注册与可信执行内核_L2_v1.0.md`、`D02_02_Invocation生命周期与持久化_L2_v1.0.md`、`D02_03_元数据授权与Context安全_L2_v1.0.md`、`D04_Agent Adapter与Domain Metadata收敛_L2实施详细设计_v1.0.md`  
> 本文输出：D03 冻结前状态归档、类/方法/Bean/事务/删除/测试落地清单与恢复编码规则

## 0. 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-07-02 | 新增 D03_02 落地清单 | D03 主文档已定义目标、门禁和删除台账，但不足以直接指导当前多模块编码；本文件把已发生的 D03 diff、上位约束和剩余缺口收敛为可执行清单 |
| 2026-07-02 | 同步 D03 批次 A-H 实现后状态 | Entry、Planning、Lifecycle、Kernel、Runtime、Auth、Conversation、UI 已完成原子切换；本文状态表、阻塞项和验证命令需与当前代码一致 |
| 2026-07-02 | 同步 D03 代码评审通过状态 | D03 文档约束、架构边界、静态删除门禁、Python 注释门禁和相关测试已复审通过；真实 LLM/下游成功链路仍作为发布前环境级验证 |
| 2026-07-02 | 启动 D03 边界修订 | 三系统联动暴露 Snapshot 执行预算缺失、checkpoint 序列化依赖私有字段、本地完整联调缺少 Eureka 前置；需按本清单修复并重新评审 |
| 2026-07-02 | 恢复 D03 代码评审通过状态 | 已完成最终门禁测试、静态检查、employee/transaction API smoke 和浏览器 UI smoke；发布前仍需目标环境迁移与回归 |
| 2026-07-02 | 冻结前最终评审对齐 D03 主文档、D03_01 权限契约和验证命令语义 | 当前清单用于状态归档和后续恢复编码约束，不再描述为待编码缺口清单 |

## 1. 文档定位

D03 主文档仍是目标和退出门禁来源。本文不改变 D03 范围，不新增运行态目标，不放宽删除门禁，只补充编码顺序和方法级落点。

本文解决的问题：

1. 把 D03 主文档中的目标调用链拆成 Java、Runtime、Persistence、UI 和删除顺序。
2. 把 D02/D04 已冻结的接口约束合成到 D03 编码视图。
3. 把当前 D03 状态标记为已实现、已验证或发布前仍需回归的事项。
4. 定义冻结后若恢复编码必须遵守的签名、Bean、事务和测试门禁。
5. 给出冻结前评审、修复、复审清单，避免后续临场补设计。

本文不做以下事情：

1. 不重新设计 D01 Runtime contract。
2. 不改变 D02 Capability Kernel、Lifecycle、Authorization、Context 的职责边界。
3. 不把 JWT role、本地 `agent.intent-roles`、旧 `AgentPermissionService` 或测试替身定义为生产权限源。
4. 不保留 v1/v2 Runtime endpoint、旧 intent 路由、旧 handler registry 或 converter。
5. 不引入新的生产依赖。

## 2. 当前实现状态对齐

以下状态以 2026-07-02 当前工作区为基线。后续编码必须先更新本表再继续。

| 区域 | 当前状态 | 结论 |
| --- | --- | --- |
| D01 active contract | `agent-api/src/main/resources/openapi/agent-runtime-openapi.json` 已切换 active contract，fixture 迁入 active 目录，Runtime generated models 与 OpenAPI hash 对齐 | 已验证，contract tests 与 drift gate 通过 |
| Runtime Route/Plan | `agent-runtime/app/core/runtime_planning.py` 承载 active Route/Plan；旧 `graph.py`、`planning.py`、`prompt_builder.py`、`route_models.py` 已删除 | 已验证，Python tests 与 drift gate 通过 |
| Java Runtime Client | `AgentRuntimeClient.route/plan` 为唯一 Runtime 调用；旧 `generate(PlanGenerateRequest)` 与 `/runtime/v1/plans/generate` 已删除 | 已完成 |
| PlanningService | `PlanningService.plan(PlanningCommand, CancellationToken)` 已对齐 D02_00；取消和 deadline 检查覆盖 Route、Context、Plan、freeze 关键点 | 已完成 |
| Orchestrator | `AgentOrchestrator` 为薄 Entry；history limit 来自 `AgentProperties.conversation.recentTurnLimit`，deadline 来自 `AgentProperties.runtime.readTimeout`，同一 token 传递到 Planning/Execution | 已完成 |
| Lifecycle | `ExecutionLifecycleService`、`StartTxService`、`CheckpointTxService`、`FinalizationTxService`、`InvocationRecoveryService` 已形成分层；checkpoint JSON 必须通过专用审计 DTO 序列化，不依赖领域模型私有字段 | 已修订并通过专项测试 |
| Invocation persistence | `agent_invocation_record`、`agent_invocation_result`、`agent_turn.invocation_id` 已写入 SQL 和 Mapper；旧 Turn finalization 方法已移除 | 已验证，schema/mapper/finalization 测试通过 |
| Context persistence | `MyBatisContextRepository`、`ContextRecordMapper`、`agent_context_record` 已实现；Context 只通过 Planning/Execution/Finalization Port 进入主链 | 已完成，真实数据库集成仍作为后续环境验证 |
| Metadata Store | `DefaultAgentMetadataBootstrap` 已提供生产 bootstrap，metadata/security 配置已有装配测试 | 已验证 |
| UserPermission authority | `auth-service` 内部权限投影 API、服务 token 安全门禁、`AuthServiceUserPermissionAuthorityAdapter` 已实现；`AuthorizationSnapshot` 必须冻结 `ExecutionBudget` 并由 Execution recheck 原样带入 `ExecutionScope` | 已修订并通过专项测试 |
| Execution Core wiring | `CapabilityKernelConfiguration` 装配 `ExecutionCore`、Registry、Query/Aggregate registration；旧 handler registry/router 不再参与生产 | 已验证 |
| Agent API typed response | CHAT response 已消费 D02 typed result；旧 `PlanGenerateRequest/Response`、旧 `AgentIntent`、旧 `agent-api/plan/AgentPlan` 已删除 | 已完成 |
| 旧 capability 链 | `AgentCapabilityHandlerRegistry`、`CapabilityRouter`、`CapabilityRouteResolver`、Clarify handler、descriptor factory 已删除；Query/Aggregate 迁入 Kernel handler | 已完成 |
| Conversation history | `ConversationService.loadRecentTurns(InvocationHandle,int)` 为唯一历史读取入口；旧 `query_context_json` 生产读写路径已删除 | 已完成 |
| UI | `agent.html` 已按 typed `result.resultKind` 渲染 RESULT/CLARIFY/ERROR，不再依赖旧并列字段 | 已完成 |
| Tests | Contract、Runtime、Planning、Lifecycle、Kernel、Metadata/Auth、Auth-service、静态删除门禁、Python 注释门禁、API smoke、浏览器 UI smoke 已执行 | 代码评审门禁已通过；本地真实下游成功链路已验证；目标环境仍需发布前回归 |

## 3. D03 目标调用链

D03 完成后 CHAT 主链只能是：

```text
AgentChatController
  -> AgentOrchestrator.chat(userContext, request)
     -> StartChatCommandFactory.create(userContext, request, absoluteDeadline)
     -> ExecutionLifecycleService.startChat(startCommand)
     -> ConversationService.loadRecentTurns(handle, recentTurnLimit)
     -> PlanningCommandFactory.create(handle, message, history)
     -> PlanningService.plan(planningCommand, cancellationToken)
        -> AuthorizationPlanningPort.capture
        -> CapabilityCatalog.available
        -> AgentRuntimeClient.route
        -> RouteOutcomeValidator.validate
        -> CapabilityRegistry.resolve
        -> ContextPlanningPort.load / toRuntimeView
        -> AgentRuntimeClient.plan
        -> PlanOutcomeValidator.validate
        -> AuthorizationPlanningPort.freezeCapabilityScope
     -> if ResolvedClarification:
          ExecutionLifecycleService.finalizeClarification
     -> if ExecutablePlanningResult:
          ExecutionLifecycleService.executeAndFinalize
             -> CheckpointTxService.write
             -> ExecutionCore.execute
             -> FinalizationTxService.commit*
     -> AgentChatResponseAssembler.fromFinalizedResult
```

禁止路径：

1. Entry 不得调用 `AgentRuntimeClient.generate`。
2. Entry 不得解析 `AgentIntent`。
3. Entry 不得路由 `AgentCapabilityHandler`。
4. Entry 不得直接写 `agent_turn` 成功、失败或澄清终态。
5. Planning 不得调用 handler、adapter 业务执行或 finalization。
6. Execution Core 不得调用 Runtime Route/Plan。
7. Response Assembler 不得重新执行 result projector 或读取未过滤结果。

## 4. 类与方法落地清单

### 4.1 Entry

| 文件 | 动作 | 目标签名/职责 |
| --- | --- | --- |
| `agent-service/src/main/java/com/dylan/agent/controller/AgentChatController.java` | MODIFY | 只负责认证上下文、请求 DTO 和 `AgentOrchestrator.chat` 调用；不出现 Runtime、Intent、Handler、PlanGenerate 类型 |
| `agent-service/src/main/java/com/dylan/agent/application/AgentOrchestrator.java` | MODIFY | `AgentChatResponse chat(AgentUserContext userContext, AgentChatRequest request)`；薄 Entry Adapter；只串联 Start、history、Planning、Lifecycle finalization、Response assembler |
| `agent-service/src/main/java/com/dylan/agent/application/StartChatCommandFactory.java` | KEEP/MODIFY | `StartChatCommand create(AgentUserContext userContext, AgentChatRequest request, Instant absoluteDeadline)`；输入规范化、subject/profile/scope/deadline 绑定 |
| `agent-service/src/main/java/com/dylan/agent/application/PlanningCommandFactory.java` | KEEP/MODIFY | `PlanningCommand create(InvocationHandle handle, String userMessage, List<RuntimeTurnProjection> history)`；不得重新读取用户、profile 或权限 |
| `agent-service/src/main/java/com/dylan/agent/application/AgentChatResponseAssembler.java` | KEEP/MODIFY | `AgentChatResponse fromFinalizedResult(FinalizedInvocationResult result)`；唯一 CHAT API response 映射 |

Entry 必修正项：

1. `AgentOrchestrator.absoluteDeadline()` 不得固定 `30s`；必须来自 D03/D02 确认的配置源，优先复用 `AgentProperties.runtime.readTimeout` 或新增明确的 invocation deadline 配置。
2. `ConversationService.loadRecentTurns(handle, 6)` 不得固定 `6`；必须来自 `AgentProperties.conversation.recentTurnLimit` 或同等配置。
3. `AgentOrchestrator` 必须创建并传递同一 `CancellationToken` 给 Planning 和 Execution；取消/超时不能只覆盖 execution。
4. `AgentOrchestratorTest` 必须改为新薄 Entry 测试，删除旧 Runtime generate 和 handler 断言。

### 4.2 Planning

| 文件 | 动作 | 目标签名/职责 |
| --- | --- | --- |
| `agent-service/src/main/java/com/dylan/agent/planning/PlanningService.java` | MODIFY | `PlanningResult plan(PlanningCommand command, CancellationToken cancellation)`；唯一 Route -> Plan 编排 |
| `agent-service/src/main/java/com/dylan/agent/planning/model/PlanningCommand.java` | MODIFY/KEEP | 必须携带 committed `InvocationHandle`、message、history、profileRef、delegationConstraintRef；不得携带未冻结权限快照 |
| `agent-service/src/main/java/com/dylan/agent/planning/RuntimePlanningRequestFactory.java` | KEEP | 生成最小 Route/Plan request；使用 D04 Domain projection 和 Profile behavior projection |
| `agent-service/src/main/java/com/dylan/agent/planning/RouteOutcomeValidator.java` | KEEP | 校验 RouteOutcome discriminator、metadata、capabilityId、domain、clarification；不执行 fallback |
| `agent-service/src/main/java/com/dylan/agent/planning/PlanOutcomeValidator.java` | KEEP | 校验 PlanOutcome discriminator、metadata、ExecutablePlan、clarification、planKind 和 Registration 绑定 |
| `agent-service/src/main/java/com/dylan/agent/planning/CapabilitySelectionResolver.java` | KEEP | 把合法 RouteDecision 解析成 `ResolvedRegistration`；不得按旧 intent 路由 |
| `agent-service/src/main/java/com/dylan/agent/planning/PlanningClarificationResolver.java` | KEEP | 只渲染安全 clarification；不得暴露 chain-of-thought 或未授权候选 |
| `agent-service/src/main/java/com/dylan/agent/planning/PlanningConfiguration.java` | MODIFY | 生产 Bean 装配；必须显式依赖所有 Port，不允许静默缺失后半链启动 |

Planning 必修正项：

1. 将 `PlanningService.plan(PlanningCommand)` 调整为 `plan(PlanningCommand, CancellationToken)`，并在 Route 前、Route 后、Context 前、Plan 前、freeze 前检查 token/deadline。
2. `RuntimeOperationException` 中 CANCELLED/DEADLINE_EXCEEDED 必须映射为 `PlanningCancellationException`，不能全部进入 `PlanningFailureException`。
3. `PlanningConfiguration` 中 `AgentMetadataStore` 没有生产 Bean 时不得让 Entry 装配成半链；必须补 production bootstrap 或启动失败测试。
4. `PlanningService` 只能通过 `ContextPlanningPort.toRuntimeView` 生成 context view，不能按 context type 自行组装。
5. Route 前不得加载 Context；只有合法 RouteDecision 和 Registration 解析后才能加载 Context。

### 4.3 Lifecycle 与 Persistence

| 文件 | 动作 | 目标签名/职责 |
| --- | --- | --- |
| `agent-service/src/main/java/com/dylan/agent/lifecycle/ExecutionLifecycleService.java` | KEEP/MODIFY | 非事务外层 coordinator；公开 `startChat`、`checkpoint`、`executeAndFinalize`、`finalizeClarification`、`finalizePlanningFailure`、`finalizeCancelled` |
| `agent-service/src/main/java/com/dylan/agent/lifecycle/StartTxService.java` | KEEP/MODIFY | `StartWriteResult createOrVerify(StartChatCommand command)`；独立事务；创建 Turn + Invocation |
| `agent-service/src/main/java/com/dylan/agent/lifecycle/CheckpointTxService.java` | KEEP/MODIFY | `CheckpointResult write(InvocationHandle handle, ExecutablePlanningResult result)`；独立事务；写 planning checkpoint |
| `agent-service/src/main/java/com/dylan/agent/lifecycle/FinalizationTxService.java` | KEEP/MODIFY | commit success/clarification/planning failure/planning cancellation/execution failure/execution cancellation |
| `agent-service/src/main/java/com/dylan/agent/lifecycle/InvocationRecoveryService.java` | KEEP/MODIFY | 恢复遗留 PROCESSING；不得恢复业务执行 |
| `agent-service/src/main/java/com/dylan/agent/lifecycle/InvocationAuditJsonCodec.java` | KEEP/MODIFY | checkpoint/result audit JSON；使用专用审计 DTO，不得写权限正文、raw plan、用户 token 或敏感 payload |
| `agent-service/src/main/java/com/dylan/agent/persistence/mapper/AgentInvocationRecordMapper.java` | KEEP/MODIFY | Invocation 状态 CAS、按 correlation/owner/scope 权威重读 |
| `agent-service/src/main/java/com/dylan/agent/persistence/mapper/AgentInvocationResultMapper.java` | KEEP/MODIFY | 存储 filtered result、clarification 或 error envelope |
| `agent-service/src/main/java/com/dylan/agent/persistence/mapper/AgentTurnMapper.java` | MODIFY | 新主链只通过 Lifecycle finalization 更新终态；旧 completeSuccess/completeFailure 需删除或转为 package-private 旧测试不可见前再删除 |

Lifecycle 必修正项：

1. `ExecutionLifecycleService` 类和 public 方法不得标注 `@Transactional`。
2. 只有 Tx service 方法持有事务。
3. Start 必须原子创建 Turn + Invocation，并共享 `invocationId`；不得事务后补关联。
4. commit success 必须在同一 finalization transaction 中提交 filtered result、Context finalization、Invocation terminal state 和 Turn terminal state。
5. planning failure、planning cancellation、execution failure、execution cancellation 都必须形成终态；不得留下 PROCESSING 等待异步补偿。
6. Recovery 只终结遗留状态，不重新执行 Runtime、Handler 或 Adapter。

### 4.4 Kernel 与 Capability

| 文件/目录 | 动作 | 目标 |
| --- | --- | --- |
| `agent-service/src/main/java/com/dylan/agent/kernel/core/ExecutionCore.java` | KEEP/MODIFY | 唯一执行核心；`ExecutionOutcome execute(ExecutionCommand command)` |
| `agent-service/src/main/java/com/dylan/agent/kernel/config/CapabilityKernelConfiguration.java` | MODIFY | 注册 `ExecutionCore`；不得依赖旧 handler registry |
| `agent-service/src/main/java/com/dylan/agent/capability/query/*` | MODIFY/DELETE | 迁移到 D02_01 Registration/Validator/Handler 模式；删除旧 `AgentIntent` 依赖 |
| `agent-service/src/main/java/com/dylan/agent/capability/aggregate/*` | MODIFY/DELETE | 同上 |
| `agent-service/src/main/java/com/dylan/agent/capability/clarify/*` | DELETE | Clarification 由 Runtime Route/Plan typed clarification + `ResolvedClarification` 表达，不再是 capability handler |
| `agent-service/src/main/java/com/dylan/agent/capability/AgentCapabilityHandler*.java` | DELETE | 旧 intent handler SPI 和 registry 不得保留在生产主链 |
| `agent-service/src/main/java/com/dylan/agent/capability/CapabilityRouter.java` | DELETE | 旧 intent router 不得保留 |
| `agent-service/src/main/java/com/dylan/agent/capability/CapabilityRouteResolver.java` | DELETE | RouteOutcomeValidator 替代 |
| `agent-service/src/main/java/com/dylan/agent/capability/CapabilityDescriptorFactory.java` | DELETE | D04 DomainMetadataPort + CapabilityCatalog 替代 |

Kernel 必修正项：

1. Query/Aggregate 只能通过 `CapabilityRegistration` 进入 Registry。
2. Plan validator 只接受 D01 typed plan，不接受旧 `PlanGenerateResponse`。
3. Handler 执行返回 `ExecutionOutcome` 所需的 filtered result 和 context writes，不写 `query_context_json`。
4. `ClarifyCapabilityHandler` 必须删除，不能用 clarify capability 兼容新 typed clarification。

### 4.5 Metadata、Authorization、Context、Result Security

| 文件/目录 | 动作 | 目标 |
| --- | --- | --- |
| `metadata/authorization/internal/AuthServiceUserPermissionAuthorityAdapter.java` | KEEP | 唯一生产 `UserPermissionAuthorityPort` Adapter |
| `metadata/authorization/internal/AuthorizationSecurityConfiguration.java` | KEEP/MODIFY | 生产上下文恰好一个 `UserPermissionAuthorityPort` |
| `metadata/config/AgentMetadataSecurityConfiguration.java` | MODIFY | 装配 Payload、ResultSecurity、DomainExecution、AuthorizationPlanning/Execution |
| `metadata/config/AgentMetadataStore.java` | KEEP | 唯一 active metadata bundle store |
| `metadata/config/AgentMetadataBootstrap.java` | IMPLEMENT | 必须有生产 bootstrap Bean 或显式启动失败门禁 |
| `metadata/profile/internal/ProfileBehaviorProjectionBoundary.java` | KEEP | Planning request 使用，不复制 profile 事实 |
| `metadata/context/internal/MyBatisContextRepository.java` | KEEP/MODIFY | 生产 ContextRepository |
| `metadata/context/internal/ContextSecurityConfiguration.java` | KEEP/MODIFY | `ContextBoundary` 同时提供 Planning/Execution/Approval port；不得注册多个同实现同接口 Bean |
| `metadata/result/internal/*` | KEEP/MODIFY | Result projector 只能在 Execution Core 内执行 |

Metadata 必修正项：

1. 若没有 `AgentMetadataStore` 生产 bootstrap，`PlanningService`、`AuthorizationPlanningPort`、Profile behavior projection 不能被视为投产就绪。
2. 生产上下文必须恰好一个 `UserPermissionAuthorityPort` Bean，且为 `AuthServiceUserPermissionAuthorityAdapter`。
3. `UserPermissionAuthorityPort` 失败必须 fail closed，不回退 JWT role 或 `agent.intent-roles`。
4. Context required read 失败必须进入 planning failure/cancellation，不得忽略。
5. Payload key 缺失或非法必须启动失败或解密失败，不得明文降级。

### 4.6 Runtime 与 Contract

| 文件/目录 | 动作 | 目标 |
| --- | --- | --- |
| `agent-api/src/main/java/com/dylan/agent/api/contract/runtime/**` | KEEP | active Route/Plan contract 唯一来源 |
| `agent-api/src/main/java/com/dylan/agent/api/request/PlanGenerateRequest.java` | DELETE | 旧 Runtime generate request 删除 |
| `agent-api/src/main/java/com/dylan/agent/api/response/PlanGenerateResponse.java` | DELETE | 旧 Runtime generate response 删除 |
| `agent-api/src/main/java/com/dylan/agent/api/enums/AgentIntent.java` | DELETE | intent 不再是生产契约 |
| `agent-api/src/main/java/com/dylan/agent/api/plan/AgentPlan.java` | DELETE | D01 typed plan 替代 |
| `agent-api/src/main/java/com/dylan/agent/api/capability/AgentCapabilityDescriptor.java` | DELETE | CapabilityCatalog/Runtime projection 替代 |
| `agent-runtime/app/api/runtime_api.py` | MODIFY | 只暴露 active Route/Plan endpoints |
| `agent-runtime/app/core/runtime_planning.py` | KEEP/MODIFY | Route/Plan typed runtime operations |
| `agent-runtime/app/contracts/generated_models.py` | KEEP | Java OpenAPI 生成结果，不手写语义 |
| `agent-runtime/scripts/check_contract_drift.py` | KEEP/MODIFY | active contract drift gate |

Runtime 必修正项：

1. 删除 `/runtime/v1/plans/generate`。
2. 删除 Java `AgentRuntimeClient.generate`。
3. 删除旧 Python graph/planning/prompt_builder/route_models 后，测试不得再引用。
4. active OpenAPI、Java fixture、Python generated model 必须一致。

### 4.7 UI

| 文件 | 动作 | 目标 |
| --- | --- | --- |
| `agent-service/src/main/resources/static/agent.html` | MODIFY | 只消费 D02_01 `AgentChatResponse` typed result；RESULT/CLARIFY/ERROR 三态渲染 |

UI 必修正项：

1. 不再依赖旧 `queryParameters`、`queryResult`、`aggregateResult` 并列字段。
2. RESULT 根据 `result.kind` 渲染 Query/Aggregate payload。
3. CLARIFY 只显示 safe question。
4. ERROR 显示安全 message/errorCode，不显示内部 diagnostic。

## 5. 生产 Bean 装配矩阵

| Bean/interface | 唯一生产实现 | 装配条件 | 门禁 |
| --- | --- | --- | --- |
| `UserPermissionAuthorityPort` | `AuthServiceUserPermissionAuthorityAdapter` | auth-service base-url、service token supplier、RestClient | `UserPermissionAuthorityProductionWiringTest` |
| `UserPermissionBoundary` | `AuthorizationSecurityConfiguration.userPermissionBoundary` | 恰好一个 `UserPermissionAuthorityPort`、UTC Clock | 零个或多个启动失败 |
| `AgentMetadataStore` | D03 需新增 production bootstrap Bean | `AgentMetadataBootstrap.bootstrap()` 成功 | `AgentMetadataProductionBootstrapTest` |
| `AuthorizationPlanningPort` | `AuthorizationPlanningPortImpl` | `AgentMetadataStore`、`UserPermissionBoundary`、DomainMetadataPort | `AuthorizationPlanningPortTest` |
| `AuthorizationExecutionPort` | `AuthorizationExecutionPortImpl` | DomainMetadataPort、Clock | `AuthorizationExecutionPortTest` |
| `DomainMetadataPort` | `DomainMetadataPortImpl` | D04 AdapterRegistration + DomainFieldCatalog | `DomainMetadataPortContractTest` |
| `CapabilityRegistry` | `CapabilityKernelConfiguration.capabilityRegistry` | Query/Aggregate registrations | `CapabilityRegistryTest` |
| `CapabilityCatalog` | `PlanningConfiguration.capabilityCatalog` | CapabilityRegistry + DomainMetadataPort | `CapabilityCatalogTest` |
| `ProfileBehaviorProjectionBoundary` | `PlanningConfiguration.profileBehaviorProjectionBoundary` | AgentMetadataStore | `ProfileBehaviorProjectionBoundaryTest` |
| `ContextRepository` | `MyBatisContextRepository` | MyBatis mapper、ObjectMapper、Clock | `ContextRepositoryIT` |
| `ContextPlanningPort` | `ContextBoundary` | ContextRepository、PayloadJsonCodec、ProtectedPayloadCodec、Clock | `ContextRuntimeViewTest` |
| `ContextExecutionPort` | `ContextBoundary` | 同上 | `ExecutionCoreTest` |
| `ContextApprovalPort` | `ContextBoundary` | 同上 | `ExecutionCoreTest` |
| `ContextFinalizationParticipant` | `ContextFinalizationParticipantImpl` | ContextRepository、PayloadJsonCodec、ProtectedPayloadCodec、settings | `ContextFinalizationIT` |
| `ResultSecurityPort` | `ResultSecurityBoundary` | ResultSecurityProjectorRegistry | `ResultSecurityBoundaryTest` |
| `ExecutionCore` | `CapabilityKernelConfiguration.executionCore` | AuthorizationExecutionPort、ContextExecutionPort、DomainExecutionPort、ContextApprovalPort、ResultSecurityPort、Clock | `ExecutionCoreTest` |
| `ExecutionLifecycleService` | Spring `@Service` | StartTxService、CheckpointTxService、FinalizationTxService、ExecutionCore | `LifecycleArchitectureTest` |
| `PlanningService` | `PlanningConfiguration.planningService` | 所有 Planning ports/helper/client | `PlanningArchitectureTest` |

禁止通过 `@ConditionalOnMissingBean` 或测试替身让生产上下文静默降级。条件 Bean 缺失时必须通过启动测试暴露，而不是回退旧链。

## 6. 数据库与事务边界

### 6.1 DDL 目标

| 表/列 | 目标 |
| --- | --- |
| `agent_turn.invocation_id` | 与 Invocation 原子关联；D03 新写入必填 |
| `agent_invocation_record` | Invocation 状态、subject、origin、scope、profile、deadline、audit checkpoint |
| `agent_invocation_result` | filtered result、clarification、failure/cancellation envelope |
| `agent_context_record` | typed/versioned/encrypted context record |
| `agent_turn.query_context_json` | 可为历史兼容列，但 D03 生产代码不得读写 |

### 6.2 事务规则

| 阶段 | 事务 owner | 允许写入 | 禁止 |
| --- | --- | --- | --- |
| Start | `StartTxService` | Turn PROCESSING、Invocation PROCESSING | 调 Runtime、加载 Context、写结果 |
| Planning checkpoint | `CheckpointTxService` | Invocation planning checkpoint | 写 Turn terminal、执行业务 |
| Success finalization | `FinalizationTxService` | Invocation SUCCESS、Turn SUCCESS、InvocationResult、Context writes | 再次调用 Runtime、再次执行 handler |
| Clarification finalization | `FinalizationTxService` | Invocation CLARIFY、Turn CLARIFY、safe question result | 写业务 result、Context writes |
| Planning failure | `FinalizationTxService` | Invocation FAILED、Turn FAILED、safe error | 留 PROCESSING |
| Cancellation | `FinalizationTxService` | Invocation CANCELLED、Turn CANCELLED、safe error | 映射成 FAILED |
| Recovery | Recovery Tx service | 将超时或不完整 PROCESSING 终结 | 恢复业务执行 |

## 7. 删除顺序

D03 是原子交付，但编码顺序必须先接通目标链，再删除旧链。

| 顺序 | 动作 | 证明 |
| --- | --- | --- |
| 1 | 修正 `PlanningService.plan` 签名、取消传播和 tests | `PlanningServiceTest`、`DeadlineCancellationTest` |
| 2 | 补齐 `AgentMetadataStore` production bootstrap 与生产 Bean 门禁 | `AgentMetadataProductionBootstrapTest`、`PlanningArchitectureTest` |
| 3 | 修正 `AgentOrchestrator` 配置来源、CancellationToken、薄 Entry tests | `AgentOrchestratorTest` |
| 4 | 补齐 Lifecycle IT、schema IT、Recovery tests | lifecycle test group |
| 5 | 迁移 Query/Aggregate 到 Registration/Kernel，不再引用 `AgentIntent`/`PlanGenerateResponse` | `ExecutionCoreTest`、capability tests |
| 6 | 删除 `AgentRuntimeClient.generate` 和旧 Runtime endpoint | contract/runtime tests |
| 7 | 删除旧 agent-api intent/generate/plan/descriptor 类型 | Java compile + static gate |
| 8 | 删除旧 capability router/registry/clarify handler/factory | Java compile + static gate |
| 9 | 删除 `AgentPermissionService` 和 `agent.intent-roles` 配置 | metadata/auth tests + static gate |
| 10 | 收敛 `ConversationService`，删除旧 `query_context_json` 生产读写 | history projection tests + static gate |
| 11 | 更新 UI typed response | UI smoke/static check |
| 12 | 运行 D03 全部门禁 | 第 9 节命令 |

任一步无法通过时，不允许保留兼容 facade 或 feature flag；必须回到对应设计条目修正。

## 8. 测试补强清单

### 8.1 必须新增或修正

| 测试 | 目标 | 当前状态 |
| --- | --- | --- |
| `AgentOrchestratorTest` | 新薄 Entry：start、history、planning、clarification finalization、execute finalization、planning failure、planning cancellation | 已实现 |
| `PlanningServiceTest` | Route/Plan 正常、Route clarification、Plan clarification、runtime failure、deadline/cancel、Context after Route | 已实现 |
| `RouteOutcomeValidatorTest` | RouteOutcome discriminator、capability/domain、clarification 安全校验 | 已实现 |
| `PlanOutcomeValidatorTest` | PlanOutcome discriminator、planKind、registration binding、clarification 安全校验 | 已实现 |
| `AgentMetadataProductionBootstrapTest` | 生产 `AgentMetadataStore` 存在且 profile/policy/security 可读 | 已实现 |
| `UserPermissionAuthorityProductionWiringTest` | 恰好一个生产 Adapter | 已实现 |
| `AuthServiceUserPermissionAuthorityAdapterTest` | Adapter 超时、非法响应、subject mismatch、version/evidence 缺失 fail closed | 已实现 |
| `AgentPermissionServiceTokenSecurityTest` | auth-service 内部权限接口只接受 agent-service 服务 token 和必需 scope | 已实现 |
| `ExecutionLifecycleServiceTest` | 非事务 coordinator、checkpoint 后 execute、failure/cancel mapping | 已实现 |
| `PlanningCheckpointTest` | checkpoint 专用审计 DTO 可序列化核心字段，不依赖领域模型私有字段 | 已通过 |
| `AuthorizationExecutionPortTest` | Execution recheck 不扩大 Snapshot，并保留 Snapshot 冻结的执行预算 | 已通过 |
| `StartTxServiceTest` | Turn + Invocation 原子创建、幂等 correlation、冲突拒绝 | 已实现 |
| `FinalizationTxServiceTest` | success/clarify/failure/cancel 原子终结 | 已实现 |
| `InvocationRecoveryServiceTest` | 不恢复业务执行，只终结遗留 PROCESSING | 已实现 |
| `InvocationSchemaTest` | DDL、索引、非空和唯一约束 | 已实现 |
| `ConversationServiceTest` | 只投影当前 invocation 前的成功历史，不读旧 query context | 已实现 |
| `ExecutionCoreTest` | Registration binding、authorization/domain/context/result security | 已实现 |
| `KernelArchitectureTest` | 旧 handler registry/router 不被 Core 引用 | 已实现 |
| `AgentResultPayloadContractTest` | Query/Aggregate typed payload 兼容 | 已实现 |
| `AgentRuntimeContractArchitectureTest` | active contract 无 candidate/v1 残留 | 已实现 |

### 8.2 不允许的测试修法

1. 不删除失败测试来获得绿色。
2. 不把旧链预期改成“兼容存在”。
3. 不通过 mock 旧 `AgentRuntimeClient.generate` 维持 Orchestrator 测试。
4. 不放宽 static gate。
5. 不用 `@MockBean UserPermissionAuthorityPort` 证明 production wiring。

## 9. 验证命令

Maven 命令均在 `D:\codex\serviceCenter` 执行；Python、`rg`、`git` 命令均在 `D:\codex` 执行。第 9.1 到 9.4 是目标门禁命令，若目标模块中的测试类不存在，必须先按第 8 节补齐测试。命令中的 `surefire.failIfNoSpecifiedTests=false` 仅用于避免聚合依赖模块无同名测试时误报，不得作为跳过 `agent-api`、`agent-service`、`auth-service` 目标测试的豁免。

### 9.1 Java contract

```powershell
.\mvnw.cmd -pl "..\agent-api" -am "-Dtest=AgentRuntimeContractOpenApiGenerationTest,AgentRuntimeContractFixtureTest,AgentRuntimeContractArchitectureTest,AgentResultPayloadContractTest" test --batch-mode
```

### 9.2 Java planning/entry/client

```powershell
.\mvnw.cmd -pl "..\common-security,..\agent-api,..\agent-adapter-api,..\agent-adapter-employee,..\agent-adapter-transaction,..\agent-service" -am "-Dtest=AgentOrchestratorTest,PlanningServiceTest,AgentRuntimeClientContractTest,AgentRuntimeErrorMapperTest,RouteOutcomeValidatorTest,PlanOutcomeValidatorTest" "-Dsurefire.failIfNoSpecifiedTests=false" test --batch-mode
```

### 9.3 Java lifecycle/kernel/metadata

```powershell
.\mvnw.cmd -pl "..\common-security,..\agent-api,..\agent-adapter-api,..\agent-adapter-employee,..\agent-adapter-transaction,..\agent-service" -am "-Dtest=ExecutionLifecycleServiceTest,StartTxServiceTest,FinalizationTxServiceTest,InvocationRecoveryServiceTest,InvocationSchemaTest,ConversationServiceTest,ExecutionCoreTest,KernelArchitectureTest,CapabilityRegistryTest,CapabilityExtensionTest,AgentMetadataProductionBootstrapTest,AgentMetadataSecurityConfigurationTest,UserPermissionAuthorityProductionWiringTest,AuthServiceUserPermissionAuthorityAdapterTest" "-Dsurefire.failIfNoSpecifiedTests=false" test --batch-mode
```

### 9.4 Auth-service permission

```powershell
.\mvnw.cmd -pl "..\auth-service" -am "-Dtest=AgentPermissionProjectionServiceTest,AgentPermissionInternalControllerTest,AgentPermissionServiceTokenSecurityTest" "-Dsurefire.failIfNoSpecifiedTests=false" test --batch-mode
```

### 9.5 Python Runtime

```powershell
python -m pytest agent-runtime/tests
```

```powershell
python agent-runtime/scripts/check_contract_drift.py
```

### 9.6 静态删除门禁

以下搜索在 D03 完成后必须为空；DB DDL 历史列、active `com.dylan.agent.api.contract.runtime.plan.AgentPlan` typed union 和 Runtime provider 内部 generate helper 除外。

```powershell
rg --files agent-api/src/main/java agent-service/src/main/java | rg "agent-api[/\\]src[/\\]main[/\\]java[/\\]com[/\\]dylan[/\\]agent[/\\]api[/\\](enums[/\\]AgentIntent|request[/\\]PlanGenerateRequest|response[/\\]PlanGenerateResponse|plan[/\\]AgentPlan|capability[/\\]AgentCapabilityDescriptor)\\.java"
```

```powershell
rg -n "com\\.dylan\\.agent\\.api\\.(enums\\.AgentIntent|request\\.PlanGenerateRequest|response\\.PlanGenerateResponse|plan\\.AgentPlan|capability\\.AgentCapabilityDescriptor)|\\b(PlanGenerateRequest|PlanGenerateResponse|AgentCapabilityDescriptor)\\b" agent-api/src/main/java agent-service/src/main/java -S
```

```powershell
rg -n "AgentCapabilityHandlerRegistry|CapabilityRouter|CapabilityRouteResolver|ClarifyCapabilityHandler|CapabilityDescriptorFactory|AgentPermissionService" agent-service/src/main/java -S
```

```powershell
rg -n "/plans/generate|runtime/v1/plans/generate|class PlanGenerate" agent-runtime/app agent-service/src/main/java -S
```

```powershell
rg -n "query_context_json|selectLatestSucceededQuery|completeSuccess\\(|completeFailure\\(" agent-service/src/main/java agent-api/src/main/java agent-runtime/app -S
```

```powershell
rg -n "agent.intent-roles|intentRoles|getIntentRoles|setIntentRoles" agent-service/src/main/java agent-service/src/main/resources -S
```

### 9.7 Diff hygiene

```powershell
git diff --check
git status --short --branch
```

## 10. 当前阻塞项

截至 2026-07-02 当前工作区，D03 原子切换未发现仍需阻塞编码的旧链残留。

已关闭项：

1. `PlanningService.plan` 已改为 `plan(PlanningCommand, CancellationToken)`，取消传播覆盖 Planning 主流程。
2. `AgentOrchestrator` 已移除硬编码 history limit 和固定 30s deadline。
3. `AgentOrchestratorTest` 已改为薄 Entry 主链测试。
4. `AgentMetadataStore` production bootstrap 已通过测试证明。
5. 旧 `AgentRuntimeClient.generate`、`PlanGenerateRequest/Response`、`AgentIntent`、旧 capability router/registry/handler 已删除。
6. `ConversationService` 和 `AgentTurnMapper` 已移除旧 `query_context_json` 生产读写路径。
7. Lifecycle/Persistence 已有 start、finalization、recovery、schema 级测试证明。
8. UI 已切换 typed response。

剩余风险不是 D03 阻塞项，但发布前仍需执行目标环境验证：

1. 真实 MySQL schema 初始化和迁移验证：本地 smoke 已补 `agent-p0-v1.3.sql` 并验证旧库补列，发布环境仍需按变更流程执行。
2. 目标环境完整 E2E 回归：本地已通过 Eureka 链路验证 `agent-service`、`auth-service`、`agent-runtime`、`employee-service`、`mq-procedure-service` 可协作执行；发布环境仍需按同等拓扑复验注册、Route/Plan 和真实 handler。
3. 浏览器 UI 回归：本地已通过 gateway 登录态、`agent.html` 成功结果渲染、查询参数和 20 行查询结果展示；发布环境仍需复验真实域名、Cookie 策略和网关转发配置。

## 11. 编码恢复规则

恢复编码或后续修复时仍按以下批次推进；当前批次 A-H 已完成，后续变更不得绕过对应测试和静态门禁：

1. 批次 A：修正 Entry/Planning 签名、取消传播、Orchestrator 测试。状态：完成。
2. 批次 B：补齐 Metadata bootstrap 和生产 Bean 门禁。状态：完成。
3. 批次 C：补齐 Lifecycle/Persistence schema 和事务验证。状态：完成。
4. 批次 D：迁移 Query/Aggregate 到 Kernel Registration，删除 Clarify handler。状态：完成。
5. 批次 E：删除旧 Runtime generate、旧 API 类型、旧 capability router/registry。状态：完成。
6. 批次 F：收敛 Conversation history/context，删除旧 query context 生产路径。状态：完成。
7. 批次 G：切换 UI typed response。状态：完成。
8. 批次 H：全量验证、静态删除门禁、文档状态同步。状态：完成。

若某批次需要修改公共契约、DDL 或引入生产依赖，必须先暂停评审，不能在批次内直接扩大范围。

## 12. 文档评审清单

| 编号 | 问题 | 通过标准 |
| --- | --- | --- |
| R-01 | 是否保持 D03 原目标，不扩大到 D05/D06 | 本文不引入 TASK、ResultRef、多 Agent、outbox 或外部新依赖 |
| R-02 | 是否列出完整目标调用链 | 第 3 节覆盖 Controller 到 Response assembler |
| R-03 | 是否精确到类和方法 | 第 4 节列出路径、动作、签名和职责 |
| R-04 | 是否覆盖 Bean 装配 | 第 5 节列出 interface、生产实现、条件和门禁 |
| R-05 | 是否覆盖事务边界 | 第 6 节列出 Tx owner、允许写入和禁止项 |
| R-06 | 是否给出旧链删除顺序 | 第 7 节从目标链修正到旧链删除逐步列出 |
| R-07 | 是否覆盖测试门禁 | 第 8、9 节列出测试类和命令 |
| R-08 | 是否识别当前阻塞项 | 第 10 节列出当前不能继续假装完成的缺口 |
| R-09 | 是否禁止降级和双运行态 | 第 1、3、5、7、8 节均有禁止项 |
| R-10 | 是否能直接指导下一轮编码 | 第 11 节给出批次顺序和每批验收 |

## 13. 自评结论

本文已完成 Snapshot 执行预算、checkpoint 审计 DTO 和本地联调门禁修订，并通过最终门禁测试、静态检查、API smoke 与浏览器 UI smoke。D03 代码评审通过；发布前仍需按第 10 节完成目标环境迁移和回归。

任何后续修改都必须回到第 12 节执行评审；若发现实现与本文冲突，优先修正文档或代码，不允许绕过门禁继续推进。
