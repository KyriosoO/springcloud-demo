# D03 Capability v2 跨服务原子切换 — L2 实施详细设计 v1.0

> 文档状态：已完成本轮评审
> 编写日期：2026-07-02
> 输入基线：`76400d6 Update legacy runtime contract model`
> 前置交付：D01 已完成；D02_00/D02_01/D02_02/D02_03 已完成设计与编码基线；D04 已实施并通过退出门禁
> 上位依据：`Agent目标架构总览_v1.0.md`、`Agent目标架构与演进设计_v1.0.md`、`Agent契约与规划架构设计_v1.0.md`、`Agent能力执行内核架构设计_v1.0.md`、`Agent元数据与上下文安全架构设计_v1.0.md`
> 关联 L2：`D01_Agent契约生成与治理_L2实施详细设计_v1.0.md`、`D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md`、`D02_01_Capability注册与可信执行内核_L2_v1.0.md`、`D02_02_Invocation生命周期与持久化_L2_v1.0.md`、`D02_03_元数据授权与Context安全_L2_v1.0.md`、`D04_Agent Adapter与Domain Metadata收敛_L2实施详细设计_v1.0.md`
> 后置交付：D05 Capability 扩展验证与遗留清理；D06 Multi-Agent 详细设计必须等待 D05 完成

---

## 0. Change List

| 日期 | 内容 | 原因 |
|---|---|---|
| 2026-07-02 | 新增 D03 L2 实施详细设计，接收 D01/D02/D04 输出，定义 Capability v2 跨服务原子切换的调用链、文件级变更、删除台账、测试门禁和评审矩阵 | D03 编码前必须有独立 L2 文档，避免直接编码造成范围扩大、半链发布或旧新双运行态 |

---

## 1. 文档目的与输入基线

### 1.1 目的

D03 的目标是在一个纵向交付单元内，将当前单 Agent CHAT 主链路一次切换到 capability-first 目标架构：

```text
Agent API CHAT
  → Invocation/Lifecycle Start
  → Planning Service
      → Runtime Route operation
      → Java RouteOutcome 校验与 Registration 解析
      → Authorization Snapshot 与 Context Read
      → Runtime Plan operation
      → Java PlanOutcome 校验与 ExecutablePlanningResult
  → Lifecycle checkpoint
  → Execution Core
      → Authorization recheck
      → Context currentness check
      → D04 Adapter Binding
      → Capability Plan Validator
      → Capability Handler
      → Result Security + Context approval
  → Lifecycle finalization
  → AgentChatResponse typed response
```

D03 结束后，仓库只保留目标契约和目标主链路，不存在 v1/v2 Runtime endpoint、双 Python model、feature flag、converter、facade、旧 intent registry 或旧 completion 路径。

### 1.2 当前代码基线

当前仓库已经存在以下目标组件基线：

- D01 target contract 包：`agent-api/src/main/java/com/dylan/agent/api/contract/runtime/**`。
- D01 target OpenAPI、fixture、Python target contract tests。
- D02 kernel、invocation、metadata、context、result security 的多数组件和模型。
- D04 `agent.domain-metadata`、`DomainMetadataPortImpl`、`AdapterRegistrationSet`、Adapter coverage tests。

当前仍存在需要 D03 原子切换删除或替换的旧主链：

- `agent-service/src/main/java/com/dylan/agent/application/AgentOrchestrator.java` 仍直接编排 conversation、Runtime 单 operation、intent route、handler 执行和 turn completion。
- `agent-service/src/main/java/com/dylan/agent/client/AgentRuntimeClient.java` 仍调用 `/runtime/v1/plans/generate`。
- `agent-runtime/app/api/runtime_api.py` 仍暴露单 operation `/plans/generate`。
- `agent-api/src/main/java/com/dylan/agent/api/enums/AgentIntent.java`、旧 `PlanGenerateRequest`/`PlanGenerateResponse`、旧 `AgentPlan` 仍被生产路径使用。
- `agent-service/src/main/java/com/dylan/agent/capability/**` 中仍有旧 `CapabilityRouter`、`AgentCapabilityHandlerRegistry`、`ClarifyCapabilityHandler`、intent handler 和旧 validated plan。
- `agent-service/src/main/resources/db/agent-p0.sql` 仍以 `agent_turn.query_context_json` 承载旧查询上下文，尚未具备目标 `agent_invocation_record`、`agent_invocation_result` 和 context 终结 schema。
- `agent-service/src/main/resources/static/agent.html` 仍需要随 typed response 最终形状同步切换。

### 1.3 D03 完成标准

D03 只有同时满足以下条件才可视为完成：

1. Java Runtime target contract 成为 Agent Service 和 Runtime 的唯一 active contract。
2. Runtime 只保留 Route/Plan 两个 operation，不保留 `/runtime/v1/plans/generate`。
3. Planning Service 是 Java 侧唯一规划入口，Planning 不调用 Handler、Adapter、业务服务或持久化终态。
4. Execution Lifecycle Service 是 Invocation Start、checkpoint、Core 调用和 finalization 的唯一协调者。
5. Execution Core 是 Handler/Adapter 前的唯一可信执行边界，执行前完成授权复检、Context currentness、D04 binding、Plan validation。
6. CLARIFY 由 Lifecycle 直接终结，不注册为 capability，不进入 Core、Handler 或 Adapter。
7. CHAT Turn 与 Agent Invocation Record 原子关联，SUCCESS/CLARIFY/FAILED/CANCELLED 都有权威终态。
8. Result 和 Context write 在同一 Agent DB 本地事务中完成 finalization，不预设 outbox。
9. Agent API/UI 使用统一 typed response，不保留 query/aggregate 并列字段或旧字段适配逻辑。
10. 旧 AgentIntent 主路径、旧 Runtime 单 operation、旧 Python generated model、旧 fixture、旧 registry/router/facade 全部删除。
11. 外部 `UserPermissionAuthorityPort` 生产 Adapter 有且仅有一个 Bean；权威源不可用时 fail closed，不回退 JWT role 或旧本地角色配置。
12. 所有 D03 验证命令和静态删除门禁通过。

---

## 2. 目标、范围与非目标

### 2.1 目标

D03 负责以下原子切换：

1. 将 D01 target Route/Plan/Clarification/Error DTO 提升为生产 active contract。
2. 将 `agent-runtime` 切换为 `/runtime/v1/route` 与 `/runtime/v1/plan` 两个独立 operation。
3. 实现 Java `PlanningService`，串联 Capability Catalog、D04 Route/Plan Projection、Runtime Route/Plan、Authorization Planning、Context Planning Read 和 `ExecutablePlanningResult`。
4. 实现 `ExecutionLifecycleService` 及 Start/checkpoint/finalization/recovery 持久化闭环。
5. 接入 D02 `ExecutionCore`、Capability Registration、Plan Validator、Handler、Result Security、Context approval 和 D04 Adapter Binding。
6. 切换 `AgentChatController`/`AgentOrchestrator` 到薄 Entry Adapter，只负责认证主体解析、输入规范化、Lifecycle+Planning+Execution 编排和响应返回。
7. 替换旧 `ConversationService` completion/query context 路径为 Invocation/Turn/Result/Context 原子终结路径。
8. 切换 `AgentChatResponse` typed result、错误、澄清和 UI 渲染。
9. 删除旧 intent registry/router、Clarify handler、旧 Runtime model/prompt/graph、旧 fixtures 和兼容代码。
10. 将 D01 target contract tests、drift gate 和 GitHub Actions 提升为 active gate。

### 2.2 非目标

D03 不做以下事情：

- 不修改 L0/L1 架构、不重新定义 Capability、Profile、Policy、Domain、Context 或 Multi-Agent 概念。
- 不新增 D06 Multi-Agent 编排、Run/Task/Attempt 状态机、CoordinationPlanner、TaskRunner 或 ResultRef。
- 不新增代表性 capability；该验证属于 D05。
- 不修改 D04 Canonical Domain Field Catalog 算法、Adapter Role 语义或 AdapterRegistration 数据来源。
- 不把用户权限、领域事实、字段事实复制到 Profile、Policy、Prompt 或 Runtime。
- 不新增 v1/v2 兼容层、feature flag、converter、facade、双 endpoint、双 Python model 或双 CI 真相。
- 不让 Runtime 执行权限判断、业务调用、Context 持久化、Result 过滤或最终问题渲染。
- 不让 Handler 做授权决策、Invocation/Context 持久化、adapter 二次路由或返回新 capabilityId/planKind。
- 不在 D03 内设计外部权限系统协议；D03 只消费已评审的 `UserPermissionAuthorityPort` 生产实现。若外部协议缺失，D03 编码不得开始。

---

## 3. 上位约束追踪

| 来源 | D03 必须满足的约束 | 本文落点 |
|---|---|---|
| L0：Java 是唯一契约源 | target DTO/OpenAPI/Python model 单向生成，无手工补丁和双 model | 第 6、10、11 节 |
| L0：纵向原子交付 | Java/API/Runtime/Persistence/UI/删除旧路径同一交付单元完成 | 第 8、9、11 节 |
| L0：新增 capability/domain 不侵入主流程 | Registration/Catalog/Binding 通用算法，禁止 capabilityId/domain 分支 | 第 5、6、10 节 |
| 契约与规划 L1 | Route/Plan 两 operation、PlanningResult 边界、Runtime 不可信 | 第 4、5、6、7 节 |
| 能力执行内核 L1 | Registry 类型桥唯一、Core 执行前复检、Handler 只收 ValidatedPlan | 第 5、7、8 节 |
| 元数据与上下文安全 L1 | Profile/Policy/Permission 交集、Context 两阶段、ResultSecurity、D04 binding | 第 5、6、7 节 |
| D01 | 接收 target contract、fixtures、drift scripts，并提升为 active | 第 6、9、11 节 |
| D02_00 | 删除旧 intent 主路径，不保留半链 | 第 9、11 节 |
| D02_01 | 接入 Capability Registration、ExecutionCore、Validator、Handler | 第 5、7、8 节 |
| D02_02 | 接入 Lifecycle、Invocation Record、Turn/Result finalization、recovery | 第 5、6、7、8 节 |
| D02_03 | 接入 Authorization、Context、Result Security、UserPermission SPI | 第 5、6、7、12 节 |
| D04 | 使用唯一 Domain metadata 和 AdapterRegistration，不恢复旧 metadata 来源 | 第 5、6、9、11 节 |

---

## 4. 当前调用链与目标调用链

### 4.1 当前调用链

```text
AgentChatController.chat
  → AgentUserContextResolver.resolve(jwt)
  → AgentOrchestrator.chat
      → AgentPermissionService.requireAgentAccess
      → ConversationService.openConversation
      → ConversationService.startTurn
      → ConversationService.loadRecentTurns(conversationId,userId,limit)
      → ConversationService.loadLatestQueryContext
      → RuntimeDomainSchemaProjection.createAll
      → CapabilityDescriptorFactory.createForRuntimeRequest
      → AgentRuntimeClient.generate(/runtime/v1/plans/generate)
      → CapabilityRouteResolver.resolve(AgentIntent)
      → AgentPermissionService.checkIntent
      → CapabilityRouter.route(AgentIntent)
      → AgentCapabilityHandler.validate
      → AgentCapabilityHandler.execute
      → ConversationService.completeSuccess/completeFailure
      → AgentChatResponse old fields
```

主要问题：

- Planning、authorization、handler routing、execution、turn completion 都集中在 `AgentOrchestrator`。
- Runtime 单 operation 返回旧 `AgentPlan`，Route/Plan 审计和 budget 边界不独立。
- `AgentIntent` 仍是主路径路由依据。
- CLARIFY 作为 capability handler 存在，违背“澄清不进入 Core/Handler/Adapter”边界。
- 旧 query context 写在 `agent_turn.query_context_json`，不是 Capability Context。
- 成功结果过滤和 Context write 不在 Lifecycle finalization 同一事务闭环。

### 4.2 目标调用链

```text
AgentChatController.chat
  → AgentUserContextResolver.resolve(jwt)
  → AgentOrchestrator.chat
      → StartChatCommandFactory.create(request,userContext)
      → ExecutionLifecycleService.startChat(command)
      → ConversationService.loadRecentTurns(handle,20)
      → PlanningService.plan(command)
          → AuthorizationPlanningPort.capture
          → CapabilityCatalog.available
          → DomainMetadataPort.availability
          → DomainMetadataPort.routeProjection
          → AgentRuntimeClient.route(RouteRequest)
          → RouteOutcomeValidator.validate
          → CapabilityRegistry.resolve(capabilityId)
          → DomainMetadataPort.planSchema
          → ContextPlanningPort.load
          → AgentRuntimeClient.plan(PlanRequest)
          → PlanOutcomeValidator.validate
          → ExecutablePlanningResult or ResolvedClarification
      → if ResolvedClarification:
          ExecutionLifecycleService.finalizeClarification
      → if ExecutablePlanningResult:
          ExecutionLifecycleService.checkpoint
          → ExecutionLifecycleService.executeAndFinalize
              → ExecutionCore.execute
                  → AuthorizationExecutionPort.recheck
                  → ContextExecutionPort.assertCurrent
                  → DomainExecutionPort.resolve
                  → CapabilityPlanValidator.validate
                  → TypedRegistrationInvoker.invoke
                  → ResultSecurityPort.secure
                  → ContextApprovalPort.approve
              → FinalizationTxService.commitSuccess/commitExecutionFailure
      → AgentChatResponseAssembler.fromFinalizedResult
```

### 4.3 调用链不变量

1. Entry 层不得直接调用 Runtime、Handler、Adapter、ResultSecurity 或 Context repository。
2. Planning 层不得持久化 Invocation/Turn/Result/Context，不调用 Handler/Adapter。
3. Lifecycle 层不得重新验证 Raw Plan，不修改 Core outcome，不自行过滤 result。
4. Core 不调用 Runtime、不持久化、不构建 API response。
5. Handler 不调用 `DomainMetadataPort`、`AuthorizationPlanningPort`、`AuthorizationExecutionPort` 或 persistence mapper。
6. Adapter 只由 D04 `AdapterExecutionBinding` 注入给 Handler，不按 domain 二次查找。
7. `ResolvedClarification` 只进入 Lifecycle finalization，不进入 Core/Handler/Adapter。
8. 同一 Invocation 共享一个 absoluteDeadline 和 CancellationToken。

---

## 5. 模块、文件、类与方法清单

### 5.1 `agent-api`

| 路径 | 动作 | D03 要求 |
|---|---|---|
| `com/dylan/agent/api/contract/runtime/**` | PROMOTE | D01 target contract 提升为生产 Runtime contract |
| `com/dylan/agent/api/request/AgentChatRequest.java` | KEEP/MODIFY | 保持 CHAT 输入；新增字段必须先走 Java 契约，不携带权限事实 |
| `com/dylan/agent/api/response/AgentChatResponse.java` | MODIFY | 只保留 conversationId、turnId、type、message、summary、result、errorCode 等统一响应字段 |
| `com/dylan/agent/api/response/AgentResultPayload.java` | KEEP/MODIFY | sealed result 单一扩展点，SUCCESS 时 result 非空 |
| `com/dylan/agent/api/response/QueryAgentResultPayload.java` | MODIFY | 只表达过滤后的查询结果和查询参数 |
| `com/dylan/agent/api/response/AggregateAgentResultPayload.java` | MODIFY | 只表达过滤后的聚合结果 |
| `com/dylan/agent/api/enums/AgentResponseType.java` | MODIFY | 目标值只允许 `RESULT`、`CLARIFY`、`ERROR` |
| `com/dylan/agent/api/enums/AgentIntent.java` | DELETE | D03 完成后生产代码不得依赖 intent |
| `com/dylan/agent/api/plan/**` | DELETE | 旧 `AgentPlan`/`ClarifySpec` 由 target contract 替代 |
| `com/dylan/agent/api/request/PlanGenerateRequest.java` | DELETE | Runtime 单 operation 请求删除 |
| `com/dylan/agent/api/response/PlanGenerateResponse.java` | DELETE | Runtime 单 operation 响应删除 |
| `com/dylan/agent/api/runtime/**` | DELETE | 旧 Runtime DTO 包由 target contract `api/contract/runtime/**` 替代 |

### 5.2 `agent-service` Entry 与 Runtime Client

| 路径 | 动作 | 目标方法 |
|---|---|---|
| `controller/AgentChatController.java` | MODIFY | `AgentChatResponse chat(Jwt jwt, AgentChatRequest request)` 只做认证主体解析和委托 |
| `application/AgentOrchestrator.java` | MODIFY | `AgentChatResponse chat(AgentUserContext userContext, AgentChatRequest request)` 变为薄 Entry Adapter |
| `application/StartChatCommandFactory.java` | NEW | `StartChatCommand create(AgentUserContext userContext, AgentChatRequest request, Instant absoluteDeadline)` |
| `application/PlanningCommandFactory.java` | NEW | `PlanningCommand create(InvocationHandle handle, String userMessage, List<RuntimeTurnProjection> history)` |
| `application/AgentChatResponseAssembler.java` | NEW | `AgentChatResponse fromFinalizedResult(FinalizedInvocationResult result)` |
| `client/AgentRuntimeClient.java` | MODIFY | `RouteOutcome route(RouteRequest request)`；`PlanOutcome plan(PlanRequest request)` |
| `client/RuntimeOperationException.java` | NEW | 区分 transport/protocol/auth/provider/timeout，携带 `RuntimeOperationType` 和 `PlanningOperationAudit` |
| `client/AgentRuntimeErrorMapper.java` | NEW | `PlanningFailure map(RuntimeOperationException exception, InvocationHandle handle)` |
| `exception/AgentRuntimeException.java` | DELETE | typed `RuntimeOperationException` 和 `PlanningFailure` 替代 |
| `config/AgentProperties.java` | MODIFY | 删除 `intentRoles` 和旧单 operation only 配置；保留 runtime、conversation、query/aggregate 仍被目标 handler 使用的运行参数 |
| `config/AgentPropertiesValidator.java` | MODIFY | 不再校验 intent role 或 handler intent 覆盖；只校验运行参数 |
| `agent-service/pom.xml` | MODIFY | 增加 ArchUnit test dependency，保留既有 Testcontainers/MySQL 验证能力 |

`AgentOrchestrator.chat` 目标算法：

1. 解析和规范化 message。
2. 计算 absoluteDeadline。
3. 调用 `ExecutionLifecycleService.startChat`。
4. 用 `ConversationService.loadRecentTurns(InvocationHandle handle, int maxMessages)` 读取历史。
5. 构造 `PlanningCommand` 并调用 `PlanningService.plan`。
6. 对 `ResolvedClarification` 调用 `finalizeClarification`。
7. 对 `ExecutablePlanningResult` 先 `checkpoint`，再 `executeAndFinalize`。
8. 用 `AgentChatResponseAssembler` 返回 typed response。

### 5.3 `agent-service` Planning

| 路径 | 动作 | 目标方法 |
|---|---|---|
| `planning/PlanningService.java` | NEW | `PlanningResult plan(PlanningCommand command)` |
| `planning/RouteOutcomeValidator.java` | NEW | `ValidatedRouteDecision validate(RouteOutcome outcome, PlanningCommand command, AvailableCapabilitySnapshot available)` |
| `planning/PlanOutcomeValidator.java` | NEW | `AgentPlan validate(PlanOutcome outcome, PlanningCommand command, ResolvedRegistration registration)` |
| `planning/RuntimeRequestFactory.java` | NEW | `RouteRequest routeRequest(PlanningCommand command, AvailableCapabilitySnapshot available, List<RuntimeDomainRoutingProjection> domains, RuntimeProfileBehaviorProjection profile)`；`PlanRequest planRequest(PlanningCommand command, ResolvedRegistration registration, RuntimeDomainSchema schema, List<RuntimeContextView> contextViews)` |
| `planning/CapabilitySelectionResolver.java` | NEW | `ResolvedRegistration resolve(ValidatedRouteDecision decision, AvailableCapabilitySnapshot available)` |
| `planning/ClarificationResolver.java` | NEW | `ResolvedClarification fromRoute(ClarificationRequired clarification, PlanningOperationAudit routeAudit, InvocationHandle handle)`；`ResolvedClarification fromPlan(ClarificationRequired clarification, PlanningOperationAudit routeAudit, PlanningOperationAudit planAudit, ResolvedRegistration registration, InvocationHandle handle)` |
| `planning/filter/QueryMergeEngine.java` | MODIFY | 只在 Planning 阶段合并 query raw plan；Validator 只看合并后结果 |
| `planning/RuntimeDomainSchemaProjection.java` | DELETE | D04 `DomainMetadataPort.routeProjection`/`planSchema` 替代 |

`PlanningService.plan` 顺序：

1. 检查 command handle deadline/cancellation。
2. 调用 `AuthorizationPlanningPort.capture(PlanningSecurityRequest)`。
3. 调用 `CapabilityCatalog.available(evidence)`。
4. 调用 `DomainMetadataPort.availability` 和 `routeProjection`。
5. 构造 `RouteRequest`，调用 `AgentRuntimeClient.route`。
6. Java 校验 `RouteOutcome`，产生 `ValidatedRouteDecision` 或 `ResolvedClarification`。
7. 通过 `CapabilityRegistry.resolve(capabilityId)` 获取 `ResolvedRegistration`。
8. 按选定 capability/domain 调用 `ContextPlanningPort.load`。
9. 调用 `DomainMetadataPort.planSchema`。
10. 构造 `PlanRequest`，调用 `AgentRuntimeClient.plan`。
11. Java 校验 `PlanOutcome`，产生 `ExecutablePlanningResult` 或 `ResolvedClarification`。

### 5.4 `agent-service` Lifecycle 与 Persistence

| 路径 | 动作 | 目标方法 |
|---|---|---|
| `lifecycle/ExecutionLifecycleService.java` | NEW | `InvocationHandle startChat(StartChatCommand command)`；`CheckpointResult checkpoint(InvocationHandle handle, ExecutablePlanningResult result)`；`FinalizedInvocationResult executeAndFinalize(InvocationHandle handle, ExecutablePlanningResult result, CancellationToken token)`；`FinalizedInvocationResult finalizeClarification(InvocationHandle handle, ResolvedClarification clarification)`；`FinalizedInvocationResult finalizePlanningFailure(InvocationHandle handle, PlanningFailure failure)`；`FinalizedInvocationResult finalizeCancelled(InvocationHandle handle, PlanningCancellation cancellation)` |
| `lifecycle/StartTxService.java` | NEW | `StartWriteResult createOrVerify(StartChatCommand command)` |
| `lifecycle/CheckpointTxService.java` | NEW | `CheckpointResult write(InvocationHandle handle, ExecutablePlanningResult result)` |
| `lifecycle/FinalizationTxService.java` | NEW | `FinalizedInvocationResult commitSuccess(InvocationHandle handle, CheckpointResult checkpoint, ExecutionSuccess success)`；`FinalizedInvocationResult commitClarification(InvocationHandle handle, ResolvedClarification clarification)`；`FinalizedInvocationResult commitPlanningFailure(InvocationHandle handle, PlanningFailure failure)`；`FinalizedInvocationResult commitPlanningCancellation(InvocationHandle handle, PlanningCancellation cancellation)`；`FinalizedInvocationResult commitExecutionFailure(InvocationHandle handle, CheckpointResult checkpoint, ExecutionFailure failure)`；`FinalizedInvocationResult commitExecutionCancelled(InvocationHandle handle, CheckpointResult checkpoint, ExecutionFailure failure)` |
| `lifecycle/InvocationRecoveryService.java` | NEW | `int recoverExpiredProcessing(Instant now, int batchSize)` |
| `lifecycle/InvocationAuditJsonCodec.java` | NEW | 只序列化 PlanningOperationAudit、PlanningCheckpoint.ContextSnapshotRef、ContextWriteCommitRef |
| `persistence/entity/AgentInvocationRecordEntity.java` | NEW | 映射 `agent_invocation_record` |
| `persistence/entity/AgentInvocationResultEntity.java` | NEW | 映射 `agent_invocation_result` |
| `persistence/mapper/AgentInvocationRecordMapper.java` | NEW | insert/checkpoint/finalize/select/recovery CAS |
| `persistence/mapper/AgentInvocationResultMapper.java` | NEW | insert/select result payload |
| `conversation/ConversationService.java` | MODIFY | `loadRecentTurns(InvocationHandle handle, int maxMessages)`；移除旧 completion/query context 权威职责 |
| `conversation/ConversationCleanupJob.java` | MODIFY | cleanup 前调用 `ContextScopeRetirementParticipant.retire`，不能直接删除仍可读 Context |
| `persistence/entity/AgentTurnEntity.java` | MODIFY | 增加 `invocationId`；移除生产依赖 `query_context_json` |
| `persistence/mapper/AgentTurnMapper.java` | MODIFY | Start 与 Invocation 原子关联；finalization CAS；历史读取只读 SUCCEEDED turn |

事务边界：

- `ExecutionLifecycleService` 类和 public 方法不标注 `@Transactional`。
- `StartTxService`、`CheckpointTxService`、`FinalizationTxService` 是三个独立 Spring Bean。
- Start、checkpoint、finalization 均使用短事务；commit unknown 通过权威重读处理。
- SUCCESS finalization 在同一事务内写 Invocation terminal、Turn terminal、filtered result、approved Context writes。
- CLARIFY/FAILED/CANCELLED 不写业务 Context。

### 5.5 `agent-service` Kernel 与 Capability

| 路径 | 动作 | D03 要求 |
|---|---|---|
| `kernel/registration/CapabilityRegistration.java` | VERIFY/MODIFY | Registration 不可变绑定 Definition、Raw Plan、Validator、ValidatedPlan、Handler、output type |
| `kernel/registration/CapabilityRegistry.java` | VERIFY/MODIFY | 只按 capabilityId 解析，不按 planKind/domain/intent 路由 |
| `kernel/registration/TypedRegistrationInvoker.java` | VERIFY/MODIFY | 唯一允许 unchecked bridge 的位置 |
| `kernel/core/ExecutionCore.java` | VERIFY/MODIFY | 执行 D02_01 13 步；不调用 Runtime/Persistence/API assembler |
| `capability/query/QueryCapabilityConfiguration.java` | MODIFY | 注册 `query.search` CapabilityRegistration |
| `capability/query/QueryPlanValidator.java` | MODIFY | 实现 `CapabilityPlanValidator<QueryAgentPlan, ValidatedQueryPlan>` |
| `capability/query/QueryCapabilityHandler.java` | MODIFY | 实现 `CapabilityHandler<ValidatedQueryPlan, QueryAgentResultPayload>` |
| `capability/query/QueryMessages.java` | DELETE | summary/message 只能由过滤后 result 生成 |
| `capability/query/QueryParameterMapper.java` | MODIFY | 作为 query validator/handler 内部工具，只消费 `ExecutionValidationProjection` |
| `capability/query/QueryRuntimeContextFactory.java` | DELETE | D02_03 ContextBoundary + Planning Context View 替代 |
| `capability/aggregate/AggregateCapabilityConfiguration.java` | MODIFY | 注册 `aggregate.compute` CapabilityRegistration |
| `capability/aggregate/AggregatePlanValidator.java` | MODIFY | 实现 `CapabilityPlanValidator<AggregateAgentPlan, ValidatedAggregatePlan>` |
| `capability/aggregate/AggregateCapabilityHandler.java` | MODIFY | 实现 `CapabilityHandler<ValidatedAggregatePlan, AggregateAgentResultPayload>` |
| `capability/aggregate/AggregateMessages.java` | DELETE | summary/message 只能由过滤后 result 生成 |
| `capability/clarify/**` | DELETE | Clarification 不再是 capability |
| `capability/model/ValidatedQueryPlan.java` | MODIFY | 实现 D02_01 `ValidatedPlan`，不可变且不可伪造 |
| `capability/model/ValidatedAggregatePlan.java` | MODIFY | 实现 D02_01 `ValidatedPlan`，不可变且不可伪造 |
| `capability/model/ValidatedCapabilityPlan.java` | DELETE | D02_01 `ValidatedPlan` marker 替代 |
| `planning/filter/OperatorSemantics.java` | MODIFY | 仅服务 query validator/merge，不保存权限或 catalog 事实 |
| `planning/filter/FilterNormalizer.java` | MODIFY | 仅服务 query validator/merge，不保存权限或 catalog 事实 |
| `planning/filter/FieldFilterSet.java` | MODIFY | 仅服务 query validator/merge，不保存权限或 catalog 事实 |
| `planning/filter/FieldConstraintValidator.java` | MODIFY | 只消费 `ExecutionValidationProjection` 和 D01 enum |
| `capability/CapabilityRouter.java` | DELETE | Registry+Planning 替代 |
| `capability/CapabilityRouteResolver.java` | DELETE | RouteOutcomeValidator 替代 |
| `capability/AgentCapabilityHandler.java` | DELETE | D02_01 `CapabilityHandler` 替代 |
| `capability/AgentCapabilityHandlerRegistry.java` | DELETE | D02_01 `CapabilityRegistry` 替代 |
| `capability/CapabilityDescriptorFactory.java` | DELETE | Definition routing descriptor + CapabilityCatalog 替代 |
| `capability/CapabilityExecutionContext.java` | DELETE | D02_01 `ExecutionContext` 替代 |
| `capability/CapabilityExecutionResult.java` | DELETE | D02_01 `HandlerResult`/`ExecutionOutcome` 替代 |
| `capability/CapabilityValidationContext.java` | DELETE | D02_01 `ExecutionValidationContext` 替代 |

### 5.6 `agent-service` Metadata/Security/Context/Result

| 路径 | 动作 | D03 要求 |
|---|---|---|
| `metadata/authorization/port/UserPermissionAuthorityPort.java` | KEEP | D03 必须装配唯一生产实现 |
| `metadata/authorization/internal/AuthorizationPlanningPortImpl.java` | VERIFY/MODIFY | Planning 捕获授权证据，不读 JWT role |
| `metadata/authorization/internal/AuthorizationExecutionPortImpl.java` | VERIFY/MODIFY | Execution 当前复检，只能保持或缩小 scope |
| `security/AgentUserContextResolver.java` | MODIFY | 只解析认证主体，不能输出 capability/field 授权结论 |
| `security/AgentPermissionService.java` | DELETE | UserPermission/Authorization 边界替代 |
| `metadata/context/internal/ContextBoundary.java` | VERIFY/MODIFY | Planning read、Execution currentness、write approval |
| `metadata/context/internal/ContextFinalizationParticipantImpl.java` | VERIFY/MODIFY | 只在 Lifecycle SUCCESS finalization 事务内持久化 |
| `metadata/result/ResultSecurityBoundary.java` | VERIFY/MODIFY | Core 输出进入持久化和 API 前唯一过滤边界 |
| `result/AgentResultProcessor.java` | DELETE | ResultSecurityProjector 替代 |
| `result/AggregateResultProcessor.java` | DELETE | ResultSecurityProjector 替代 |
| `metadata/domain/internal/DomainMetadataPortImpl.java` | KEEP | D04 唯一 Domain metadata production source |
| `metadata/domain/internal/AdapterPortResolver.java` | DELETE | D03 后旧 handler 不得通过 legacy resolver 适配 |

### 5.7 `agent-runtime`

| 路径 | 动作 | D03 要求 |
|---|---|---|
| `app/api/runtime_api.py` | MODIFY | 删除 `/plans/generate`；新增 `/route` 和 `/plan` |
| `app/contracts/generated_models.py` | REGENERATE | 由 D01 active OpenAPI 生成，不手工补丁 |
| `app/contracts/models.py` | MODIFY | 只 re-export active generated model 与 semantic validators |
| `app/contracts/semantic_validators.py` | MODIFY | 分别校验 RouteRequest/RouteOutcome/PlanRequest/PlanOutcome |
| `app/core/route_models.py` | DELETE | 不维护平行 RouteDecision 结构；使用 generated model |
| `app/core/graph.py` | MODIFY | 拆分 route graph 与 plan graph；不得含具体 capabilityId/domain 分支 |
| `app/core/planning.py` | MODIFY | 不再使用旧 AgentIntent/PlanGenerateRequest；拆分 route/plan parser |
| `app/core/prompt_builder.py` | MODIFY | Prompt 不枚举 capability/domain/field/operator 固定清单；从请求投影组装 |
| `app/prompts/route_system.md` | MODIFY | 只描述 route 行为和输出 schema，不复制结构 enum |
| `app/prompts/query_system.md` | MODIFY | 只描述 query plan 行为 |
| `app/prompts/aggregate_system.md` | MODIFY | 只描述 aggregate plan 行为 |

### 5.8 `agent-service` UI

| 路径 | 动作 | D03 要求 |
|---|---|---|
| `src/main/resources/static/agent.html` | MODIFY | 使用 `data.type` 和 `data.result.resultKind` 渲染 RESULT/CLARIFY/ERROR |
| `src/main/resources/static/agent.html` | MODIFY | 查询显示 summary、queryParameters、rows；聚合显示 summary、metrics/rows；错误显示 errorCode/message |
| `src/main/resources/static/agent.html` | VERIFY | 不依赖旧 `queryResult`、`aggregateResult`、`intent`、`plan` 字段 |

### 5.9 CI 与脚本

| 路径 | 动作 | D03 要求 |
|---|---|---|
| `.github/workflows/**` | MODIFY | 将 D01 target contract gate 提升为 active Agent Contract CI；不保留 candidate/active 双 gate |
| `agent-runtime/scripts/check_contract_drift.py` | MODIFY | 只检查 active OpenAPI 到 active generated model |
| `agent-runtime/scripts/target_contract/**` | DELETE | target contract gate 提升 active 后删除阶段性隔离目录 |
| `agent-api/src/test/resources/contract/candidate/**` | DELETE | candidate artifact 提升 active 后删除阶段性隔离目录 |

---

## 6. 契约、配置、数据库与生成产物设计

### 6.1 Runtime contract active 切换

D03 将 D01 target contract 从 candidate 提升为 active：

```text
agent-api/src/main/java/com/dylan/agent/api/contract/runtime/**
  → agent-api/src/main/resources/openapi/agent-runtime-openapi.json
  → agent-runtime/app/contracts/generated_models.py
  → agent-runtime/app/contracts/models.py
  → agent-runtime/tests/*
```

规则：

- 不保留旧 `app/contracts/generated_models.py` 与 target generated model 并行。
- 不保留 `scripts/target_contract` 与 active scripts 双路径；提升后只有一个 drift check。
- 不保留 `tests/target_contract` 与 active tests 双真相；提升后 target tests 成为 active contract tests。
- 不通过 Python 手工 alias、monkey patch、post-process 脚本修补结构。

### 6.2 Runtime HTTP endpoint

目标 endpoint：

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/runtime/v1/route` | `RouteRequest` | `RouteOutcome` |
| POST | `/runtime/v1/plan` | `PlanRequest` | `PlanOutcome` |

删除：

| Method | Path | 删除原因 |
|---|---|---|
| POST | `/runtime/v1/plans/generate` | 单 operation 不能表达 Route/Plan audit、budget 与 context 隔离 |

认证仍使用 `X-Agent-Runtime-Key` 内部共享密钥；禁止转发用户 JWT。

### 6.3 Agent service 配置

`agent.runtime` 目标配置：

```yaml
agent:
  runtime:
    base-url: http://localhost:9230
    connect-timeout: 2s
    read-timeout: 45s
    max-response-bytes: 65536
    shared-key: replace-with-at-least-16-characters
    route-path: /runtime/v1/route
    plan-path: /runtime/v1/plan
    max-repair-attempts: 1
```

删除或停止生产消费：

- `agent.intent-roles`。
- `agent.query` 中仅服务旧 PlanGenerateRequest 的配置项。
- `agent.aggregate` 中仅服务旧 handler routing 的配置项。
- 旧 `conversation.recent-turn-limit=6` 语义；Entry 固定传入 D02_02 要求的偶数 message limit，默认 20。

D03 不修改 `agent.domain-metadata` 语义，只消费 D04 输出。

### 6.4 Agent DB schema

D03 目标 schema 至少包含：

1. `agent_turn.invocation_id`，与 `agent_invocation_record.invocation_id` 一一关联。
2. `agent_invocation_record`：保存 invocation 状态、origin、scope、profile、subject、owner、deadline、capability/domain/planKind、operation audit、checkpoint hash、context snapshot refs、context write refs、terminal state。
3. `agent_invocation_result`：保存 filtered/secured typed result payload，使用 `ProtectedPayloadCodec` 加密。
4. `agent_context_record`：由 D02_03 context repository 使用，包含 owner/scope/contextType/contract/version/ttl/readable/protected payload/binding digest。

旧字段：

- `agent_turn.query_context_json` 不再作为生产 Context 来源。
- 迁移期可保留列以支持历史只读或回滚审计，但 D03 完成后生产代码不得读写该列。

事务规则：

- Start 事务同时创建/校验 Conversation、Turn、Invocation。
- Checkpoint 事务只写 planning checkpoint，不进入 Core。
- SUCCESS finalization 事务同时 CAS Invocation、CAS Turn、写 secured result、持久化 approved context writes。
- CLARIFY/FAILED/CANCELLED finalization 不写业务 Context。

### 6.5 UserPermissionAuthorityPort 生产 Adapter

D03 投产前必须存在且只存在一个生产 Bean：

```java
UserPermission resolveCurrent(
        ExecutionSubjectRef subject,
        Instant absoluteDeadline) throws UserPermissionAuthorityException;
```

当前 `auth-service` 只提供登录和 JWT role，不提供字段级、domain 级、capability 级的权限权威 API。因此：

- D03 文档不把 JWT role、本地 `agent.intent-roles` 或测试替身定义为生产权限源。
- D03 编码前必须由权限权威系统提供已评审的外部协议或本仓库内已评审的生产实现。
- 若需要新增 `auth-service` API，必须由对应服务所有者确认契约后再实施；D03 只在 Agent 侧实现 Adapter 和 contract tests。
- 权威源失败、超时、主体不匹配、版本缺失或字段闭合失败一律 fail closed。

---

## 7. 正常、失败、权限、deadline/cancel 调用链

### 7.1 正常 SUCCESS

```text
Start committed
  → Planning returns ExecutablePlanningResult
  → Checkpoint committed
  → Core validates and executes
  → ResultSecurity returns SecuredResult
  → ContextApproval returns ApprovedContextWrite list
  → FinalizationTxService.commitSuccess
  → AgentChatResponse type=RESULT
```

SUCCESS 不变量：

- 没有 committed checkpoint 不得调用 Core。
- 没有 secured result 不得写 `agent_invocation_result`。
- Context write CAS 失败时不得返回 SUCCESS。
- Turn 和 Invocation 终态必须一致。

### 7.2 CLARIFY

```text
RouteOutcome or PlanOutcome = ClarificationRequired
  → Java ClarificationResolver creates ResolvedClarification
  → Lifecycle finalizes CLARIFY
  → AgentChatResponse type=CLARIFY
```

CLARIFY 不变量：

- 不注册 capability。
- 不进入 Core。
- 不调用 Handler/Adapter。
- 不写业务 Context。
- 最终问题由 Java renderer/assembler 根据 typed `ClarificationArgs` 生成；Runtime 不返回最终 question。

### 7.3 Planning failure

Planning failure 来源：

- Runtime transport/protocol/auth/provider/timeout。
- RouteOutcome/PlanOutcome 结构或语义校验失败。
- Authorization capture fail closed。
- CapabilityCatalog/D04 projection fail closed。
- Context planning read fail closed。
- deadline/cancellation before planning。

处理：

- 若 Start 已提交，必须通过 `finalizePlanningFailure` 或 `finalizeCancelled` 形成 Invocation/Turn 终态。
- 不调用 Core/Handler/Adapter。
- Runtime audit 中未发生的 operation 记为 `NOT_REPORTED`。

### 7.4 Execution failure

Execution failure 来源：

- Authorization recheck shrink。
- Context currentness 失败。
- Adapter binding 不可用。
- Plan validator 失败。
- Handler/Adapter/downstream 失败。
- ResultSecurity 或 ContextApproval 失败。
- finalization CAS 冲突或 commit unknown。

处理：

- Core 返回 `ExecutionFailure`，Lifecycle 用 committed checkpoint 终结。
- 不重执行业务。
- 不补写 SUCCESS。
- commit unknown 必须通过 `InvocationAtomicViewRepository` 权威重读。

### 7.5 Deadline 与取消

规则：

- Entry 计算一个 absoluteDeadline。
- Planning、Runtime Route、Runtime Plan、Lifecycle、Core、Handler、Adapter、下游 client 共享该 deadline。
- Runtime 内部 repair 受 `maxRepairAttempts` 和 absoluteDeadline 双重限制。
- 取消 token 从 Entry/Lifecycle 传入 Core/Handler/Adapter，不在内部重新创建。
- deadline 或 cancellation 触发后，迟到 result 不得覆盖终态。

---

## 8. 编码顺序

D03 是单一交付单元，但实现应按以下内部顺序推进：

1. 提升 D01 target contract 为 active，生成 OpenAPI/Python model，并让 legacy path 暂时编译失败暴露调用点。
2. 修改 `AgentRuntimeClient` 和 `agent-runtime` endpoint 为 Route/Plan 双 operation。
3. 实现 `PlanningService`、Runtime request factory、Route/Plan Java validators 和 clarification resolver。
4. 实现 `ExecutionLifecycleService`、Tx services、Invocation/Result persistence、audit codec、recovery。
5. 接入唯一 `UserPermissionAuthorityPort` 生产 Adapter，验证唯一 Bean 装配。
6. 修改 Query/Aggregate CapabilityRegistration、PlanValidator、Handler 到 D02_01 类型。
7. 接入 `ExecutionCore`、D04 `DomainMetadataPort`、ResultSecurity、ContextBoundary。
8. 将 `AgentOrchestrator` 改为薄 Entry Adapter。
9. 切换 `AgentChatResponseAssembler` 和 `agent.html`。
10. 删除旧 intent/router/handler/runtime/model/fixture/CI 双路径。
11. 执行全量 D03 验证命令和静态删除门禁。

任何步骤未完成时不得发布或合并。若中途发现上位契约不可实现，暂停并通过 ADR 或上位文档修订处理，不在 D03 内创建旁路。

---

## 9. 删除、迁移和文档同步清单

### 9.1 必删旧路径

D03 完成后以下生产路径不得存在：

- `agent-api/src/main/java/com/dylan/agent/api/enums/AgentIntent.java`
- `agent-api/src/main/java/com/dylan/agent/api/plan/**`
- `agent-api/src/main/java/com/dylan/agent/api/request/PlanGenerateRequest.java`
- `agent-api/src/main/java/com/dylan/agent/api/response/PlanGenerateResponse.java`
- `agent-service/src/main/java/com/dylan/agent/capability/CapabilityRouter.java`
- `agent-service/src/main/java/com/dylan/agent/capability/CapabilityRouteResolver.java`
- `agent-service/src/main/java/com/dylan/agent/capability/AgentCapabilityHandler.java`
- `agent-service/src/main/java/com/dylan/agent/capability/AgentCapabilityHandlerRegistry.java`
- `agent-service/src/main/java/com/dylan/agent/capability/CapabilityDescriptorFactory.java`
- `agent-service/src/main/java/com/dylan/agent/capability/clarify/**`
- `agent-service/src/main/java/com/dylan/agent/capability/CapabilityExecutionContext.java`
- `agent-service/src/main/java/com/dylan/agent/capability/CapabilityExecutionResult.java`
- `agent-service/src/main/java/com/dylan/agent/capability/CapabilityValidationContext.java`
- `agent-service/src/main/java/com/dylan/agent/capability/model/ValidatedCapabilityPlan.java`
- `agent-service/src/main/java/com/dylan/agent/capability/clarify/ClarifyPlanValidator.java`
- `agent-service/src/main/java/com/dylan/agent/capability/clarify/ClarifyCapabilityHandler.java`
- `agent-service/src/main/java/com/dylan/agent/capability/model/ValidatedClarifyPlan.java`
- `agent-service/src/main/java/com/dylan/agent/capability/query/QueryMessages.java`
- `agent-service/src/main/java/com/dylan/agent/capability/query/QueryRuntimeContextFactory.java`
- `agent-service/src/main/java/com/dylan/agent/capability/aggregate/AggregateMessages.java`
- `agent-service/src/main/java/com/dylan/agent/security/AgentPermissionService.java`
- `agent-service/src/main/java/com/dylan/agent/result/AgentResultProcessor.java`
- `agent-service/src/main/java/com/dylan/agent/result/AggregateResultProcessor.java`
- `agent-service/src/main/java/com/dylan/agent/exception/AgentRuntimeException.java`
- `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/AdapterPortResolver.java`
- `agent-runtime/app/api/runtime_api.py` 中的 `/plans/generate`
- `agent-runtime/app/core/route_models.py` 中的平行 RouteDecision model
- `agent-runtime/tests/target_contract/**` 阶段性路径；对应测试提升到 active tests 后删除该目录
- `agent-api/src/test/resources/contract/candidate/**` 阶段性路径；对应 fixtures 提升到 active fixtures 后删除该目录

D04 已删除的 `QueryableAdapterRegistry`、`AggregatableAdapterRegistry`、`RuntimeDomainSchemaFactory` 不得在 D03 中重新引入。

### 9.2 允许保留但不得作为生产事实源

- 历史数据库列 `agent_turn.query_context_json` 可短期保留以支持历史数据审计，但生产代码不得读写。
- 旧测试类名若迁移语义后保留，必须删除旧 intent/单 operation 断言。
- D04 metadata config 保持不变，D03 不复制到 Prompt 或 Policy。

### 9.3 文档同步

D03 完成编码后必须同步：

- 更新 D01 文档中 D03 交接清单状态。
- 更新 D02_00 第 8 节删除台账为实施结果。
- 更新 D04 文档说明 D03 已消费其 metadata 基线。
- 新增 D05 前置状态说明：D03 已无旧 Intent、v1 fixture 和双协议残留，允许进入代表性 capability 扩展验证。

---

## 10. 测试设计

### 10.1 Contract tests

- `AgentRuntimeContractOpenApiGenerationTest`
- `AgentRuntimeContractFixtureTest`
- `AgentRuntimeContractArchitectureTest`
- `AgentContractJsonTest`
- `agent-runtime/tests/test_contracts.py`
- `agent-runtime/tests/test_runtime_api.py`
- `agent-runtime/tests/test_runtime_auth.py`
- `agent-runtime/tests/test_prompt_contract.py`

覆盖：

1. Java target DTO 是唯一结构源。
2. OpenAPI 生成稳定。
3. Python generated model drift 为零。
4. Route/Plan positive/negative fixtures 均通过。
5. Runtime endpoint 只有 `/route` 和 `/plan`。
6. Prompt 不复制结构 enum、JSON shape、domain field/operator 固定清单。

### 10.2 Planning tests

新增或修改：

- `PlanningServiceTest`
- `PlanningOperationAuditTest`
- `AgentRuntimeClientContractTest`
- `RouteOutcomeValidatorTest`
- `PlanOutcomeValidatorTest`
- `ClarificationResolverTest`
- `QueryMergeEngineTest`
- `PlanningArchitectureTest`

覆盖：

1. Route before Plan 顺序。
2. Route CLARIFY 不进入 Plan。
3. Plan CLARIFY 不进入 Core。
4. Runtime transport failure 生成 NOT_REPORTED audit。
5. absoluteDeadline 不被 Route/Plan repair 突破。
6. PlanRequest 只携带选定 capability/domain 的 schema 和 context view。

### 10.3 Lifecycle/Persistence tests

新增或修改：

- `ExecutionLifecycleServiceTest`
- `StartTxServiceIT`
- `CheckpointTxServiceIT`
- `FinalizationTxServiceIT`
- `InvocationRecoveryServiceIT`
- `InvocationSchemaIT`
- `InvocationAuditJsonCodecTest`
- `DeadlineCancellationTest`
- `LifecycleArchitectureTest`
- `ConversationServiceHistoryProjectionTest`

覆盖：

1. Start 原子创建 Turn+Invocation。
2. checkpoint commit 前不调用 Core。
3. SUCCESS 同事务写 Turn、Invocation、secured result、Context write refs。
4. CLARIFY/FAILED/CANCELLED 不写业务 Context。
5. commit unknown/CAS loser 通过权威重读恢复。
6. `loadRecentTurns(InvocationHandle,int)` 只读取历史 SUCCEEDED turn，不读取当前 Invocation、失败 turn、Context 或 result payload。

### 10.4 Kernel/Capability tests

新增或修改：

- `CapabilityRegistryTest`
- `ExecutionCoreTest`
- `KernelArchitectureTest`
- `CapabilityExtensionTest`
- `QueryCapabilityRegistrationTest`
- `AggregateCapabilityRegistrationTest`
- `QueryPlanValidatorTest`
- `AggregatePlanValidatorTest`
- `QueryCapabilityHandlerTest`
- `AggregateCapabilityHandlerTest`

覆盖：

1. Registry 只按 capabilityId 解析。
2. unchecked bridge 只存在于 `TypedRegistrationInvoker`。
3. Core 执行前完成 authorization/context/domain binding/validator。
4. Handler 只接收 ValidatedPlan。
5. 新增同 planKind capability 不修改 Core/Lifecycle/Registry 算法。

### 10.5 Metadata/Security/Context/Result tests

新增或修改：

- `UserPermissionAuthorityWiringTest`
- `UserPermissionAuthorityContractTest`
- `AuthorizationPlanningPortTest`
- `AuthorizationExecutionPortTest`
- `CapabilityCatalogTest`
- `DomainMetadataPortContractTest`
- `ContextBoundaryTest`
- `ContextRuntimeViewTest`
- `ContextRepositoryIT`
- `ContextFinalizationIT`
- `ContextCleanupIT`
- `ProtectedPayloadCodecTest`
- `PayloadJsonCodecTest`
- `ResultSecurityBoundaryTest`
- `MetadataArchitectureTest`

覆盖：

1. 生产环境恰好一个 `UserPermissionAuthorityPort` Bean。
2. 权威源失败不回退 JWT role。
3. Authorization snapshot 与 execution recheck 只能保持或缩小 scope。
4. Context view 不包含 envelope/payload 权限事实。
5. ResultSecurity 是返回和持久化前唯一过滤边界。
6. D04 metadata 是唯一 Domain facts 来源。

### 10.6 API/UI tests

新增或修改：

- `AgentChatControllerTest`
- `AgentChatResponseAssemblerTest`
- `AgentChatIntegrationTest`
- `AgentChatContractIT`
- `AgentHtmlContractTest`

覆盖：

1. RESULT/CLARIFY/ERROR response union。
2. Query result 包含 summary、queryParameters、rows。
3. Aggregate result 包含 summary、metrics/rows。
4. UI 不引用旧 `queryResult`、`aggregateResult`、`intent`、`plan` 字段。

---

## 11. 验证命令与退出门禁

### 11.1 Java 验证

```powershell
cd D:\codex\serviceCenter
.\mvnw.cmd -pl ../agent-api,../agent-adapter-api,../agent-service -am test --batch-mode
```

### 11.2 Python Runtime 验证

```powershell
cd D:\codex\agent-runtime
.\.venv\Scripts\python.exe scripts\check_contract_drift.py
.\.venv\Scripts\python.exe -m pytest -q
```

### 11.3 D03 专项 Java 验证

```powershell
cd D:\codex\serviceCenter
.\mvnw.cmd -pl ../agent-service -am "-Dtest=PlanningServiceTest,PlanningOperationAuditTest,AgentRuntimeClientContractTest,RouteOutcomeValidatorTest,PlanOutcomeValidatorTest,ClarificationResolverTest,QueryMergeEngineTest,PlanningArchitectureTest" test --batch-mode
.\mvnw.cmd -pl ../agent-service -am "-Dtest=ExecutionLifecycleServiceTest,StartTxServiceIT,CheckpointTxServiceIT,FinalizationTxServiceIT,InvocationRecoveryServiceIT,InvocationSchemaIT,InvocationAuditJsonCodecTest,DeadlineCancellationTest,LifecycleArchitectureTest,ConversationServiceHistoryProjectionTest" test --batch-mode
.\mvnw.cmd -pl ../agent-service -am "-Dtest=CapabilityRegistryTest,ExecutionCoreTest,KernelArchitectureTest,CapabilityExtensionTest,QueryCapabilityRegistrationTest,AggregateCapabilityRegistrationTest,QueryPlanValidatorTest,AggregatePlanValidatorTest,QueryCapabilityHandlerTest,AggregateCapabilityHandlerTest" test --batch-mode
.\mvnw.cmd -pl ../agent-service -am "-Dtest=UserPermissionAuthorityWiringTest,UserPermissionAuthorityContractTest,AuthorizationPlanningPortTest,AuthorizationExecutionPortTest,CapabilityCatalogTest,DomainMetadataPortContractTest,ContextBoundaryTest,ContextRuntimeViewTest,ContextRepositoryIT,ContextFinalizationIT,ContextCleanupIT,ProtectedPayloadCodecTest,PayloadJsonCodecTest,ResultSecurityBoundaryTest,MetadataArchitectureTest" test --batch-mode
```

### 11.4 静态删除门禁

以下搜索在 D03 完成后必须为空：

```powershell
rg -n "AgentIntent|ClarifyCapabilityHandler|CapabilityRouter|CapabilityRouteResolver|AgentCapabilityHandlerRegistry|CapabilityDescriptorFactory|query_context_json|/plans/generate|PlanGenerateRequest|PlanGenerateResponse" agent-api/src/main agent-service/src/main/java agent-runtime/app
```

历史 DB 迁移文件若保留 `query_context_json` 列，只允许用于历史兼容或审计，不属于生产读写路径；生产 Java 和 Runtime app 搜索必须为空。

以下搜索只允许命中 `TypedRegistrationInvoker`：

```powershell
rg -n '@SuppressWarnings\(\{\"unchecked\"|@SuppressWarnings\(\"unchecked\"' agent-service/src/main/java
```

以下搜索必须为空：

```powershell
rg -n "switch.*capabilityId|switch.*domain|if.*capabilityId|if.*domain" agent-service/src/main/java/com/dylan/agent/kernel agent-service/src/main/java/com/dylan/agent/metadata
```

### 11.5 退出条件

1. Java、Python、contract、integration、static gates 全部通过。
2. GitHub Actions active Agent Contract CI 只保留目标 Route/Plan contract gate。
3. Runtime OpenAPI、Python generated model、fixtures、prompt tests 无 drift。
4. 旧 path 搜索为空。
5. `git diff --check` 通过。
6. `git status --short --branch` 只包含 D03 预期改动，且未 commit/push/PR，除非用户明确授权。

---

## 12. 风险、回退与阻断项

| 风险 | 触发场景 | 处理 |
|---|---|---|
| 外部权限权威源缺失 | 没有生产 `UserPermissionAuthorityPort` 实现或协议未评审 | D03 编码不得开始；不能用 JWT role、本地配置或测试替身替代 |
| 原子切换范围过大 | Java/API/Runtime/Persistence/UI 任一侧未同步 | 不合并半链；保持本地 feature diff，修复后重跑门禁 |
| DB 迁移失败 | 新 schema 与旧数据不兼容 | 不进入 Core；Start/checkpoint/finalization fail closed；按迁移脚本回滚策略处理 |
| Runtime contract drift | Python generated model 或 prompt tests 不匹配 Java | 重新从 Java 生成，不手工补丁 |
| 旧路径残留 | 搜索命中 intent/router/单 endpoint/旧 context | 不通过退出门禁 |
| D04 metadata 使用偏移 | D03 复制 domain/operator/field 到 Prompt/Policy/Profile | 删除复制源，改为 D04 projection |
| Result/Context 事务不一致 | result 成功但 Context CAS 失败 | 整体回滚，不返回 SUCCESS |

---

## 13. D05 交付接口

D03 完成后向 D05 交付：

1. 单 Agent capability-first CHAT 主链路。
2. 生产 active Route/Plan Runtime contract。
3. 可扩展 CapabilityRegistration/Validator/Handler 接入点。
4. D04 Domain metadata 和 AdapterRegistration 生产接入点。
5. Context read/write、ResultSecurity、Lifecycle finalization 闭环。
6. 删除旧 intent 和 v1 单 operation 后的静态验证结果。

D05 只能在此基础上新增代表性 capability 验证扩展不变量，不得回到旧 Intent 或兼容 facade。

---

## 14. 需求追踪矩阵

| 要求 | D03 设计 | 验证 |
|---|---|---|
| Java 唯一契约源 | target contract 提升 active | drift check、contract tests |
| 跨服务原子切换 | API/Service/Runtime/Persistence/UI 同一交付单元 | 全量 Java/Python/IT + static gates |
| 无 v1/v2 双运行态 | 删除旧 endpoint/model/fixture/facade | 删除门禁 |
| Planning/Execution 分离 | PlanningService 只产 PlanningResult；Core 执行 | PlanningArchitectureTest、ExecutionCoreTest |
| Runtime 不可信 | Java 校验 RouteOutcome/PlanOutcome | Route/Plan validator tests |
| capabilityId 主键 | CapabilityRegistry.resolve(capabilityId) | CapabilityRegistryTest |
| Clarification 不进 Core | ResolvedClarification→Lifecycle finalization | ClarificationResolverTest、Lifecycle tests |
| Context 两阶段 | Planning read、Execution currentness、SUCCESS write | ContextBoundaryTest、ContextFinalizationIT |
| Result Security | SecuredResult 是持久化/API 前置 | ResultSecurityBoundaryTest |
| D04 metadata 唯一来源 | routeProjection/planSchema/executionProjection/bind | DomainMetadataPortContractTest |
| 权限 fail closed | UserPermissionAuthorityPort 唯一生产实现 | UserPermissionAuthorityWiringTest |
| UI typed response | resultKind 驱动渲染 | AgentHtmlContractTest |

---

## 15. 本轮评审清单

评审必须逐项确认：

1. 是否服从 L0/L1/D01/D02/D04 的交付顺序、边界、调用链和禁止事项。
2. 是否存在侵入 D04 metadata、D02 authorization/context/result、D06 Multi-Agent 或外部权限系统协议的内容。
3. 是否完整接收 D01 D03 交接清单。
4. 是否完整接收 D02_00 删除台账。
5. 是否明确 current chain 和 target chain。
6. 是否给出具体模块、文件、类、方法和测试。
7. 是否所有包路径、方法签名和 Java 类型引用均已明确。
8. 是否没有 feature flag、facade、converter、双 endpoint、双 Python model。
9. 是否没有把 JWT role 或本地 role 配置作为生产权限替代。
10. 是否给出 D03 完成后的退出门禁和 D05 交付接口。

评审发现问题后必须修改本文，再按同一清单复审。复审无问题前不得进入 D03 编码。

---

## 16. 本轮评审记录

### 16.1 第一轮评审

发现问题：

1. 静态删除门禁要求 `query_context_json` 全仓库为空，但第 9.2 节允许历史 DB 列保留，存在口径冲突。
2. `agent-service/pom.xml`、CI、target contract scripts、candidate artifacts 没有文件级落点。
3. `AdapterPortResolver` 未明确 D03 后删除。
4. `AgentProperties` 和 `AgentPropertiesValidator` 对旧 intent 配置的清理范围不够明确。

处理结果：

- 静态删除门禁改为扫描生产 Java 与 Runtime app，DB 历史列只允许作为历史兼容或审计存在。
- 增加 `agent-service/pom.xml`、`.github/workflows/**`、contract scripts 和 candidate artifact 的明确动作。
- 将 `AdapterPortResolver` 明确为 DELETE。
- 补充 `AgentProperties` 和 `AgentPropertiesValidator` 的 D03 清理要求。

### 16.2 第二轮评审

发现问题：

1. 存在动作不确定的表达。
2. D02_00 删除台账未完整接收：`AgentRuntimeException`、`QueryMessages`、`AggregateMessages`、`QueryRuntimeContextFactory`、`ValidatedCapabilityPlan`、filter helper、`ConversationCleanupJob` 等缺少明确动作。
3. 评审清单中出现容易被误判为省略写法的字面量。

处理结果：

- 所有动作改为确定的 DELETE、MODIFY、KEEP、PROMOTE 或 REGENERATE。
- 补齐 D02_00 删除台账相关文件。
- 将评审清单改为要求所有包路径、方法签名和 Java 类型引用均已明确。

### 16.3 第三轮评审结论

按第 15 节清单复审：

1. 已接收 L0/L1/D01/D02/D04 的边界、调用链和禁止事项。
2. 未侵入 D04 metadata、D02 authorization/context/result、D06 Multi-Agent 或外部权限系统协议。
3. 已接收 D01 D03 交接清单。
4. 已接收 D02_00 删除台账。
5. 已明确当前调用链和目标调用链。
6. 已给出具体模块、文件、类、方法和测试。
7. 所有包路径、方法签名和 Java 类型引用均已明确。
8. 未引入 feature flag、facade、converter、双 endpoint、双 Python model。
9. 未把 JWT role 或本地 role 配置作为生产权限替代。
10. 已给出 D03 完成后的退出门禁和 D05 交付接口。

本轮评审未发现剩余问题；D03 编码仍受第 6.5 和第 12 节的外部权限权威源门禁约束。
