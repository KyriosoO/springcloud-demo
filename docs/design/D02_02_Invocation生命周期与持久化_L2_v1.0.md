# D02_02 Invocation 生命周期与持久化 — L2 v1.0

> 文档层级：L2 实施详细设计  
> 文档状态：已实施（D01 退出门禁通过，D02 基线复核完成，代码已提交；2026-07-04 已按授权补充字段越权安全提示终结规则；2026-07-05 已补充 Runtime 输出修复失败的安全终结规则）
> 上位文档：`Agent目标架构总览_v1.0.md`、`Agent契约与规划架构设计_v1.0.md`、`Agent能力执行内核架构设计_v1.0.md`、`Agent元数据与上下文安全架构设计_v1.0.md`  
> 集成权威：`D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md`  
> 关联 L2：`D02_01_Capability注册与可信执行内核_L2_v1.0.md`、`D02_03_元数据授权与Context安全_L2_v1.0.md`  
> 交付阶段：D02 详细设计评审门禁；本文不实施代码/SQL  
> 适用代码基线：`4ce5ac3` 及其同源后续提交

---

## 0. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-04 | 授权恢复 / 第 2、3、4、11～13 节 | 用户授权修订关联设计文档 | 在授权范围内补充 `FIELD_FORBIDDEN` 错误码、`ExecutionFailure.safeMessage` 终结规则、`commitExecutionFailure` 安全提示来源和测试门禁。 |
| 2 | 2026-07-05 | 授权恢复 / 第 3～4、13 节 | UAT 修复后同步设计 | 明确 `OUTPUT_REPAIR_EXHAUSTED`/`RUNTIME_OUTPUT_INVALID` 仍走 Planning failure 安全提示，Lifecycle 不暴露 Runtime 原始输出或 repair 内容。 |

---

## 1. 文档定位

### 1.1 唯一负责

本文唯一负责：

- Invocation Scope、Handle、Record 和状态/阶段；
- `ExecutionLifecycleService` 的 Start、checkpoint、clarification、execute/finalize 接口；
- Turn、Invocation、filtered result 和 Context write 的同库原子终结协调；
- checkpoint/finalization 的 CAS、rollback confirmed、commit unknown 和 CAS loser 语义；
- PROCESSING recovery；
- absolute deadline 和 cancellation token 传播；
- Agent DB 目标 schema、Mapper/Repository 和事务测试。

本文不定义 Registration/Core 算法，不计算权限，不实现 Context 加密/CAS，不定义 D04 Metadata，不创建 ResultRef/Task State Boundary。

### 1.2 决策映射

| 决策 | 落点 |
|---|---|
| EK-06、EK-07 | 第 4、7 节 |
| EK-09、EK-17、EK-18 | 第 6～8 节 |
| EK-10、EK-12、EK-15 | 第 2～5、8 节 |
| CP-10、CP-15 | `ExecutablePlanningResult` checkpoint，不接受 D01 ExecutablePlan |
| MS-11、MS-12 | Context participant 只在 finalization transaction 内持久化 |

---

## 2. Invocation 值对象

本节基础值对象位于`com.dylan.agent.invocation.model`，不依赖Planning、Lifecycle service、Mapper、kernel或metadata。第3节持久化/终结读模型位于`com.dylan.agent.lifecycle.model`，从而避免Planning model与invocation model形成反向依赖。

### 2.1 Subject、Owner 与 Scope

```java
public record ExecutionSubjectRef(String type, String id) {}
public record ContextOwnerRef(String type, String id) {}

public sealed interface InvocationScope permits ConversationScope, RunScope {
    String scopeId();
}
public record ConversationScope(String scopeId) implements InvocationScope {}
public record RunScope(String scopeId) implements InvocationScope {}
```

构造器拒绝空值。CHAT 使用 subject=user、owner=认证用户、ConversationScope；D06 TASK 使用稳定 Execution Subject、Run Owner 和 RunScope。调用方不能用自由 `scopeRef` 混淆 scope 类型。

`InvocationOrigin`是封闭接口，只有`ChatInvocationOrigin(conversationId,turnId)`和`TaskInvocationOrigin(runId,taskId,attemptId)`。所有标识非空；CHAT只允许Chat origin+ConversationScope，TASK只允许Task origin+RunScope。D03只创建Chat origin，Task origin由D06复用，不包含Task状态或调度语义。

### 2.2 `InvocationHandle.java`

| 字段 | 类型 |
|---|---|
| `invocationId` | `String` |
| `invocationType` | `InvocationType` |
| `origin` | `InvocationOrigin` |
| `requestCorrelationId` | `String` |
| `subject` | `ExecutionSubjectRef` |
| `owner` | `ContextOwnerRef` |
| `scope` | `InvocationScope` |
| `agentProfileRef` | `AgentProfileRef` |
| `absoluteDeadline` | `Instant` |

公开方法：全参构造器、九个访问器、`Duration remaining(Clock)`、`boolean isExpired(Clock)`。构造器强制type/origin/scope闭合。Handle只在Start事务提交后创建，不保存JWT、权限、PlanningResult或可变状态。

### 2.3 状态与阶段

`InvocationType`：`CHAT`、`TASK`；D03 只创建 CHAT，TASK 由 D06 激活。

`InvocationState`：`PROCESSING`、`COMPLETED`、`FAILED`、`CANCELLED`。

`KernelErrorCode`是内部唯一安全错误enum，至少包含：`PROFILE_INVALID`、`POLICY_INVALID`、`PERMISSION_UNAVAILABLE`、`AUTH_EVIDENCE_CHANGED`、`AUTHORIZATION_REVOKED`、`CATALOG_INCONSISTENT`、`RUNTIME_CONTRACT_INVALID`、`RUNTIME_AUTHENTICATION_FAILED`、`RUNTIME_OUTPUT_INVALID`、`RUNTIME_UNAVAILABLE`、`REGISTRATION_MISMATCH`、`CONTEXT_REQUIRED_MISSING`、`CONTEXT_DECRYPT_FAILED`、`CONTEXT_STALE`、`CONTEXT_WRITE_CONFLICT`、`DOMAIN_BINDING_UNAVAILABLE`、`PLAN_VALIDATION_FAILED`、`FIELD_FORBIDDEN`、`HANDLER_FAILED`、`DOWNSTREAM_FAILED`、`OUTPUT_INVALID`、`RESULT_SECURITY_FAILED`、`PERSISTENCE_FAILED`、`DEADLINE_EXCEEDED`、`CANCELLED`、`INTERNAL_ERROR`。D03 Entry层以穷尽switch映射到现有Agent API `AgentErrorCode`，不得透传未知字符串；`FIELD_FORBIDDEN`必须映射到`AGENT_FIELD_FORBIDDEN`，不得落入`AGENT_PLAN_INVALID`。

`ExecutionStage`：

```text
LIFECYCLE_START, PLANNING, PLANNING_CHECKPOINT,
EXECUTION_PREFLIGHT, AUTHORIZATION, CONTEXT_VALIDATION, BINDING,
PLAN_VALIDATION, HANDLER, ADAPTER_DOWNSTREAM,
OUTPUT_VALIDATION, RESULT_SECURITY, CONTEXT_APPROVAL,
FINALIZATION, CANCELLATION_DEADLINE, RECOVERY
```

终态不可回到 PROCESSING。deadline/caller cancellation 使用 CANCELLED；业务或安全失败使用 FAILED。

### 2.4 Cancellation

`CancellationToken`接口方法：`boolean isCancelled()`、`Optional<KernelErrorCode> reasonCode()`、`void throwIfCancelled()`。

`CancellationSource`是request-scoped final实现，公开`CancellationToken token()`和`boolean cancel(KernelErrorCode safeReasonCode)`；reason只允许CANCELLED或DEADLINE_EXCEEDED。只有Entry/Lifecycle持有source，Core/Handler/Adapter只持有token。`executeAndFinalize`必须接收入口的同一token，禁止在方法内部创建永远不会被取消的新token。

---

## 3. Invocation Record 与响应模型

本节`InvocationRecord`、`PlanningCheckpoint`、`CheckpointResult`、`FinalizedInvocationResult`、`InvocationResponseType`、`StoredInvocationResult`和`ContextWriteCommitRef`统一位于`com.dylan.agent.lifecycle.model`；它们可依赖invocation/planning model和agent-api Java值类型，但不得被Planning model反向依赖。

### 3.1 `InvocationRecord.java`

稳定字段类别：

- invocationId/type/state/version；
- requestCorrelationId、subject、owner、scope、AgentProfileRef；
- conversationId/turnId或runId/taskId/attemptId安全引用；D03只写CHAT前者，D06 TASK写后者；
- capabilityId、planKind、registrationIdentity（Route 前可空）；
- Planning outcome、Route/Plan `PlanningOperationAudit`（含REPORTED/NOT_REPORTED）；
- planning authorization/domain metadata evidence安全ref、可选authorization snapshot及按contextType排序的context snapshot安全reference/version列表；
- SUCCESS时按contextType排序的Context write commit refs；其他终态为空；
- absoluteDeadline、terminalStage、responseType；
- resultId、errorCode、diagnosticId；
- createdAt/completedAt。

不保存 Raw/Validated Plan、完整 Snapshot/Context、权限表达式、JWT、Prompt、业务凭据。

### 3.2 `PlanningCheckpoint.java`

| 字段 | 来源 |
|---|---|
| invocationId/requestCorrelationId | Handle/ExecutablePlanningResult |
| capabilityId/domain/planKind | ExecutablePlanningResult |
| registrationIdentity | ResolvedRegistration |
| routeAudit/planAudit | D02_00 `PlanningOperationAudit` 的安全 JSON；NOT_REPORTED保持缺失值而非0 |
| planning evidence refs | authorization evidence digest + DomainMetadataEvidence安全digest |
| authorizationSnapshotRef | Snapshot id + capability-scoped evidence versions 安全摘要 |
| contextSnapshotRefs | 按contextType排序的context id/sourceDomain/stored+effective schema/record version安全摘要列表 |
| absoluteDeadline | 必须等于 Handle |
| checkpointHash | 上述不可变内容的 canonical SHA-256 |

公开静态工厂 `PlanningCheckpoint from(InvocationHandle, ExecutablePlanningResult)` 和只读访问器。

`PlanningCheckpoint.ContextSnapshotRef`是nested不可变record，字段为contextId、RuntimeContextType、optional sourceDomain、stored/effective ContractRef、recordVersion；按contextType排序且不得重复。它只用于审计/currentness关联，不含payload或权限正文。

### 3.3 `FinalizedInvocationResult.java`

| 字段 | 类型 |
|---|---|
| `invocationId` | `String` |
| `origin` | `InvocationOrigin` |
| `state` | 终态 `InvocationState` |
| `responseType` | `InvocationResponseType` |
| `storedResult` | `Optional<StoredInvocationResult>` |
| `safeMessage` | `String` |
| `errorCode`/`diagnosticId` | `Optional<KernelErrorCode>` / `Optional<String>` |

`InvocationResponseType`：`SUCCESS`、`CLARIFY`、`FAILURE`、`CANCELLED`。它是内部类型，不直接替代 Agent API response enum。

`StoredInvocationResult` 字段：resultId、output ContractRef（成功时）、解密后的filtered/masked `AgentResultPayload`（成功时）、safe message、safe summary。它只用于当前API响应重建，不是Multi-Agent ResultRef，不可跨Task传播。

`FinalizedInvocationResult.safeMessage`来源规则：SUCCESS使用`SecuredResult.safeMessage`；CLARIFY使用`ResolvedClarification`渲染后的安全问题；Planning failure使用`PlanningFailure.safeMessage`或规划失败兜底；Execution failure优先使用D02_01 `ExecutionFailure.safeMessage`，为空时使用“执行失败，请稍后重试。”；CANCELLED使用取消/超时安全提示。Lifecycle不得把异常message、SQL、下游原文、权限正文、JWT、Runtime原始输出、repair前后payload或未脱敏业务值写入safeMessage。

`ContextWriteCommitRef`是不可变安全审计值，字段为contextId、RuntimeContextType、target ContractRef、targetRecordVersion和由上述规范值计算的SHA-256 digest；不含payload、Owner/Scope重复副本或密钥。SUCCESS即使没有Context write也必须持久化非null空列表`[]`，从而区分“明确零写入”和“终结数据不完整”。

---

## 4. Lifecycle 接口与算法

### 4.1 `StartChatCommand.java`

字段：requestedConversationId（可空）、authenticatedUserId、normalizedMessage、requestCorrelationId、agentProfileRef、absoluteDeadline。Lifecycle把agentProfileRef写入Invocation并绑定到Handle；它不接受调用方自报owner/scope/权限。

### 4.2 `ExecutionLifecycleService.java`

公开方法：

| 签名 | 编排/事务边界 |
|---|---|
| `InvocationHandle startChat(StartChatCommand command)` | 外层非事务；调用独立`StartTxService`，代理提交返回后才构造Handle |
| `CheckpointResult checkpoint(InvocationHandle handle, ExecutablePlanningResult result)` | 外层非事务；调用`CheckpointTxService`的REQUIRES_NEW短事务 |
| `FinalizedInvocationResult executeAndFinalize(InvocationHandle handle, ExecutablePlanningResult result, CancellationToken token)` | 外层非事务；checkpoint提交可证明后调用Core，再调用独立FinalizationTxService |
| `FinalizedInvocationResult finalizeClarification(InvocationHandle handle, ResolvedClarification clarification)` | 外层非事务；调用独立FinalizationTxService |
| `FinalizedInvocationResult finalizePlanningFailure(InvocationHandle handle, PlanningFailure failure)` | 外层非事务；调用独立FinalizationTxService |
| `FinalizedInvocationResult finalizeCancelled(InvocationHandle handle, PlanningCancellation cancellation)` | 外层非事务；调用独立FinalizationTxService；仅Planning取消入口 |
| `FinalizedInvocationResult reread(String invocationId)` | readOnly；读取完整权威原子视图 |

`ExecutionLifecycleService`不得标注类级`@Transactional`，也不得通过self-invocation调用事务方法。`StartTxService`、`CheckpointTxService`、`FinalizationTxService`必须是三个独立Spring Bean；只有Tx Bean方法持有事务。这样外层Lifecycle才能在代理已提交返回后再返回成功，并能捕获提交ACK未知异常后执行权威重读。

### 4.3 Start 事务

```text
BEGIN
  validate authenticated user, correlation and future deadline
  create or verify owned Conversation
  INSERT Turn(PROCESSING, invocation_id)
  INSERT Invocation(PROCESSING, type=CHAT, subject/owner/scope/deadline)
COMMIT
return Handle only after commit
```

`StartTxService.createOrVerify(StartChatCommand)`使用`REQUIRES_NEW`完成上述BEGIN/COMMIT范围并返回只含invocationId的`StartWriteResult`；外层`startChat`只有在该代理调用正常返回后才能读取已提交记录并构造Handle。任一写入失败整体回滚。Turn 和 Invocation 从创建时即共享 invocationId，不通过事务后补 UPDATE 建立关联。commit确认失败但ACK未知时，外层Lifecycle按requestCorrelationId读取Invocation+Turn Start原子视图：只有两者同时存在、仍为PROCESSING且subject/owner/scope/profile/message/deadline与Command完全一致时才重建并返回Handle；不存在且rollback可证明时返回安全非成功，冲突/不完整/读失败时不返回Handle并交Recovery。相同correlation的重入只允许上述完全同值幂等返回，任何字段不同均安全冲突。

### 4.4 Checkpoint

`CheckpointResult`是final不可变值，内部nested enum `Status`仅含`COMMITTED`、`ALREADY_COMMITTED_SAME`、`TERMINAL_EXISTS`、`ROLLBACK_CONFIRMED`、`COMMIT_UNKNOWN`；字段为status和optional nested `CommittedCheckpoint`。`CommittedCheckpoint`只含invocationId、requestCorrelationId、checkpointHash，且仅COMMITTED/ALREADY_COMMITTED_SAME必须存在，其余状态必须为空。公开工厂与`requireCommittedCheckpoint()`强制该约束，避免调用方传自由hash或猜recordVersion。

算法：

1. 校验 Handle/PlanningResult correlation、subject/owner/scope、deadline、registration/snapshot 绑定。
2. 生成 `PlanningCheckpoint` 和 checkpointHash。
3. `UPDATE ... WHERE invocation_id=? AND state='PROCESSING' AND checkpoint_hash IS NULL`。
4. rowCount=1 并确认提交：COMMITTED，返回绑定该hash的CommittedCheckpoint。
5. rowCount=0：重读；相同hash为ALREADY_COMMITTED_SAME并返回同值CommittedCheckpoint；终态为TERMINAL_EXISTS；不同checkpoint为安全冲突。
6. rollback confirmed：ROLLBACK_CONFIRMED，保持 PROCESSING。
7. commit ACK/连接状态未知：COMMIT_UNKNOWN；本次不得进入 Core，必须重读或交给 recovery。

### 4.5 Execute and Finalize

```text
check deadline/cancellation
checkpoint
  COMMITTED/ALREADY_COMMITTED_SAME → retain CommittedCheckpoint; Core.execute(ExecutionCommand)
  TERMINAL_EXISTS → reread and return
  ROLLBACK_CONFIRMED → safe non-success; recovery owns PROCESSING
  COMMIT_UNKNOWN → reread; never enter Core in this attempt

Core ExecutionSuccess → FinalizationTxService.commitSuccess(handle, committedCheckpoint, outcome)
Core ExecutionFailure(cancelled=true) → commitExecutionCancelled(handle, committedCheckpoint, outcome)
other ExecutionFailure → commitExecutionFailure(handle, committedCheckpoint, outcome)
normal Tx return → reread authoritative FinalizedInvocationResult; commit exception → reread/unknown rules
```

Lifecycle 不修改 Core outcome，不重新执行 Handler/Adapter，不自行过滤结果或审批 Context。

`commitPlanningFailure`必须把`PlanningFailure.safeMessage`作为规划失败响应的首选安全提示；当该值为空、blank或不符合安全文本约束时，使用固定兜底“规划失败，请稍后重试。”。Runtime `OUTPUT_REPAIR_EXHAUSTED` 经 Planning 映射为 `RUNTIME_OUTPUT_INVALID` 时仍按 Planning failure 终结，不得把 Runtime 原始输出、repair prompt、repair payload 或 provider message 写入用户提示。

`commitExecutionFailure`必须把`outcome.safeMessage()`作为失败响应的首选安全提示；当该值为空、blank或不符合安全文本约束时，使用固定兜底“执行失败，请稍后重试。”。`FIELD_FORBIDDEN`场景由Core提供字段越权安全提示，Lifecycle只负责持久化和重读，不重新判断字段权限。

---

## 5. 持久化组件

### 5.1 组件与方法

| 类 | 公开/包内方法 |
|---|---|
| `InvocationRecordMapper` | `insert`、`checkpointCas`、`finalizeSuccessCas`、`finalizeClarifyCas`、`finalizePlanningFailureCas`、`finalizePlanningCancelledCas`、`finalizeExecutionFailureCas`、`finalizeExecutionCancelledCas`、`selectByInvocationId`、`selectByCorrelationId`、`selectExpiredProcessing` |
| `InvocationResultMapper` | `insert`、`selectByInvocationId`；删除只通过Conversation→Invocation级联 |
| `TurnPersistenceAdapter` | `createWithInvocation`、`completeSuccessCas`、`completeClarifyCas`、`completeFailureCas`、`completeCancelledCas`、`selectByInvocationId`、`selectRecentSucceededBefore` |
| `ConversationPersistenceAdapter` | `openOrCreateOwned`、`touchOwned` |
| `InvocationResultRepository` | `storeSecuredResult`、`storeClarification`、`loadStoredResult`；resultId由FinalizationTxService预生成并传入，不独立删除仍有关联Invocation的结果 |
| `InvocationAtomicViewRepository` | `load(invocationId)`：一次读取Invocation+Turn+Result及Invocation内Context commit refs的终态完整性 |
| `InvocationAuditJsonCodec` | 只序列化/反序列化PlanningOperationAudit、PlanningCheckpoint.ContextSnapshotRef列表和ContextWriteCommitRef列表 |
| `StartTxService` | `createOrVerify(StartChatCommand)`：REQUIRES_NEW；返回`StartWriteResult` |
| `CheckpointTxService` | `write(InvocationHandle, ExecutablePlanningResult)`：独立事务写checkpoint；commit异常由调用方重读 |
| `FinalizationTxService` | `commitSuccess`、`commitClarification`、`commitPlanningFailure`、`commitPlanningCancellation`、`commitExecutionFailure`、`commitExecutionCancelled`：每次调用均为REQUIRES_NEW短事务，commit异常由外层Lifecycle重读 |

Mapper 参数必须使用 typed entity/parameter object，避免十余个自由 `@Param` 顺序漂移。

`InvocationAuditJsonCodec`使用独立严格ObjectMapper：禁用default typing，启用FAIL_ON_UNKNOWN_PROPERTIES/FAIL_ON_INVALID_SUBTYPE/FAIL_ON_NULL_FOR_PRIMITIVES，注册JavaTimeModule，并按属性和Map key稳定排序。公开方法只有`String writeOperationAudit(PlanningOperationAudit)`、`PlanningOperationAudit readOperationAudit(String)`、`String writeContextSnapshotRefs(List<PlanningCheckpoint.ContextSnapshotRef>)`、`List<PlanningCheckpoint.ContextSnapshotRef> readContextSnapshotRefs(String)`、`String writeContextWriteCommitRefs(List<ContextWriteCommitRef>)`、`List<ContextWriteCommitRef> readContextWriteCommitRefs(String)`；不接受`Object`、Class name、自由Map或业务payload。PlanningCheckpoint hash使用该codec输出的UTF-8 canonical bytes；持久化和重读必须复用同一Bean。它不替代D02_03 `PayloadJsonCodec`，后者只处理加密前的Context/Result payload。

`ConversationService.loadRecentTurns(InvocationHandle handle,int maxMessages)`是唯一历史投影方法：只接受CHAT/ConversationScope Handle并从handle取得owner/scope/current invocationId，不接受自由conversationId/userId。maxMessages必须为2～20的偶数；它以`maxTurns=maxMessages/2`调用`TurnPersistenceAdapter.selectRecentSucceededBefore(conversationId,currentInvocationId,maxTurns)`，SQL通过当前invocationId对应turn_seq限定更早记录，读取assistant_message非空的SUCCEEDED Turn，排除PROCESSING/FAILED/CANCELLED、result payload、Context和权限事实。数据库按turnSeq倒序取最近maxTurns，Service反转为升序并把每Turn映射为USER、ASSISTANT两个D01 `RuntimeTurnProjection`；每项先经过安全文本长度门禁且不得截断出不同语义。Entry固定传20，在Start提交后构造PlanningCommand；当前userMessage只走独立字段，不重复进入history。

调用前后必须检查Handle absolute deadline；数据库/完整性/安全投影失败抛`PlanningFailureException(PlanningFailure.historyProjection(...))`，deadline抛`PlanningCancellationException(PlanningCancellation.beforePlanning(...))`。Entry还必须在调用前后检查同一个caller `CancellationToken`，取消时使用同一beforePlanning工厂；两类异常分别交给`finalizePlanningFailure`/`finalizeCancelled`。禁止把Start后历史读取异常直接返回HTTP或遗留PROCESSING记录等待Recovery。

### 5.2 Filtered Result 持久化

`InvocationResultRepository`只接受D02_03 `SecuredResult`，先重新计算canonical bytes SHA-256并与payloadDigest比较，再依赖`metadata.crypto.port.ProtectedPayloadCodec`以resultId、invocationId、responseType和output ContractRef构造不可替换的`PayloadProtectionContext`，直接加密`canonicalPayloadCopy()`；不得重新接触projector typed payload，也不得依赖`AeadProtectedPayloadCodec`实现类。未过滤候选、完整下游响应和Context payload不得进入result表；读取时必须以同一数据库绑定字段重建AAD，任一字段不符即解密失败。

写入前的严格序列化只在D02_03 ResultSecurityBoundary完成；Repository读取时使用D02_01 `ContractRegistry.require(outputContract).javaType()`取得唯一`AgentResultPayload` subtype，并调用D02_03唯一`PayloadJsonCodec`反序列化。密文或数据库不能提供Java class name；结果必须同时通过javaType、payload discriminator和ContractRef三重一致性校验，否则原子视图为安全不完整错误。

持久化 result 是为了 finalization commit unknown/CAS loser 后重建同一 typed response；它不是 D06 ResultRef，不被 Capability Context 或 Task 数据依赖消费。

### 5.3 `InvocationAtomicView`

字段：`InvocationRecord invocation`、`TurnRecord turn`、`Optional<StoredInvocationResult> result`、从Invocation canonical JSON解析并校验的`Optional<List<ContextWriteCommitRef>> contextWriteCommitRefs`。方法：`validateTerminalCompleteness()`、`toFinalizedResult()`。COMPLETED+SUCCESS必须同时存在SUCCEEDED Turn、可解密result和非null commit refs列表（允许空）；COMPLETED+CLARIFY必须存在SUCCEEDED Turn和clarification result且无commit refs；FAILED/CANCELLED不得带业务payload或commit refs。refs由FinalizationTxService从ApprovedContextWrite派生并与Context persist置于同一事务，不用于重放或读取Context payload。任何不完整组合返回安全一致性错误，不能猜测SUCCESS。

`AgentInvocationRecordEntity`、`AgentInvocationResultEntity`和`TurnRecord`提供与表列一一对应的无参构造器/getter/setter，仅供MyBatis；不得进入Core/Planning接口。

---

## 6. 原子 Finalization

### 6.1 `ContextFinalizationParticipant`

由 D02_03 实现：`void persist(List<ApprovedContextWrite> writes)`，事务传播必须是 `MANDATORY`，使用同一 Agent DataSource。它不能开始独立事务，不能形成自己的终态。

接口文件由本文创建于 `com.dylan.agent.lifecycle.port.ContextFinalizationParticipant`；实现文件由D02_03拥有。Lifecycle只依赖接口。

同包另有`ContextScopeRetirementParticipant`，唯一方法`void retire(ConversationScope scope, Instant now)`；D02_03实现使用`REQUIRES_NEW`幂等提交`readable=false`。它只服务Conversation清理的fail-closed前置，不删除Context、不处理RunScope，也不参与SUCCESS finalization。

### 6.2 SUCCESS 事务

```text
BEGIN
  1. validate Handle/CommittedCheckpoint and outcome capabilityId/planKind against persisted checkpoint;
     pre-generate resultId; CAS Invocation PROCESSING → COMPLETED(SUCCESS):
     UPDATE terminal fields + canonical context_write_refs_json derived from ApprovedContextWrites,
       record_version=record_version+1
     WHERE state=PROCESSING AND checkpoint_hash=CommittedCheckpoint.checkpointHash；该行锁持有到事务结束
  2. INSERT encrypted filtered result, obtain resultId
  3. persist ApprovedContextWrites with expected-version CAS
  4. CAS Turn PROCESSING → SUCCEEDED, bind resultId + safe assistant message
COMMIT
```

步骤1是L1要求的终态CAS而不是中间claim；resultId在事务前生成并随同一CAS绑定，提交前其他事务不可见。rowCount=0立即回滚并按CAS loser重读；任一步骤失败整体回滚，Invocation恢复PROCESSING。Context CAS=0、加密失败、Turn CAS=0或result写失败均不得返回SUCCESS，不得重执行业务。

### 6.3 CLARIFY/FAILED/CANCELLED

- CLARIFY：不进入Core、不写业务Context；先按`state=PROCESSING AND checkpoint_hash IS NULL`将Invocation终态CAS为COMPLETED/CLARIFY并绑定预生成resultId，再写ResolvedClarification的Route/可选Plan audit、选定Registration安全引用、safe question result和Turn SUCCEEDED。
- FAILED：不写业务result payload/Context；Planning failure按`checkpoint_hash IS NULL`终态CAS并写0～2项operation audit（保留NOT_REPORTED），Execution failure必须携带CommittedCheckpoint并按其hash终态CAS，保留checkpoint已有audit；随后同事务CAS Turn→FAILED并保存安全errorCode/diagnosticId/message。
- CANCELLED/deadline：Planning入口通过`PlanningCancellation`按`checkpoint_hash IS NULL`终态CAS并写已完成audit；Core执行取消必须携带CommittedCheckpoint并按其hash终态CAS、复用checkpoint已有audit且不接受调用方替换。随后同事务CAS Turn→CANCELLED，丢弃迟到result/Context candidate。

### 6.4 CAS loser、rollback 和 commit unknown

- CAS loser：回滚本事务，读取 `InvocationAtomicView`，服从已提交终态。
- rollback confirmed：权威状态仍为 PROCESSING，返回安全非成功并进入 recovery。
- commit unknown：只重读；完整终态原子视图可重建响应，PROCESSING 则安全非成功并 recovery，读失败则安全非成功。
- Tx Bean正常返回后外层Lifecycle也统一调用同一`reread(invocationId)`，不从ExecutionOutcome/SecuredResult内存直接构造API响应；因此正常提交、CAS loser和commit unknown使用同一权威重建路径。
- 任何路径都不在内存中伪造 FAILED/COMPLETED，不再次调用 Core。

---

## 7. Agent DB 目标 Schema

系统未投产，D03 直接修改 `agent-service/src/main/resources/db/agent-p0.sql` 为目标基线，不编写旧表兼容迁移，不保留 query_context_json/intent 双列。该 SQL 文件由本文唯一汇总；D02_03 提供 `agent_capability_context` DDL 片段。

### 7.1 `agent_invocation_record`

```sql
CREATE TABLE agent_invocation_record (
  invocation_id VARCHAR(64) PRIMARY KEY,
  invocation_type VARCHAR(16) NOT NULL,
  request_correlation_id VARCHAR(64) NOT NULL,
  subject_type VARCHAR(32) NOT NULL,
  subject_id VARCHAR(128) NOT NULL,
  owner_type VARCHAR(32) NOT NULL,
  owner_id VARCHAR(128) NOT NULL,
  scope_type VARCHAR(32) NOT NULL,
  scope_id VARCHAR(64) NOT NULL,
  agent_profile_id VARCHAR(128) NOT NULL,
  agent_profile_version VARCHAR(64) NULL,
  conversation_id VARCHAR(64) NULL,
  turn_id VARCHAR(64) NULL,
  run_id VARCHAR(64) NULL,
  task_id VARCHAR(64) NULL,
  attempt_id VARCHAR(64) NULL,
  capability_id VARCHAR(128) NULL,
  domain_id VARCHAR(128) NULL,
  plan_kind VARCHAR(32) NULL,
  registration_identity VARCHAR(128) NULL,
  checkpoint_hash CHAR(64) NULL,
  route_operation_audit_json JSON NULL,
  plan_operation_audit_json JSON NULL,
  planning_authorization_evidence_ref VARCHAR(256) NULL,
  domain_metadata_evidence_ref VARCHAR(256) NULL,
  authorization_snapshot_ref VARCHAR(256) NULL,
  context_snapshot_refs_json JSON NULL,
  context_write_refs_json JSON NULL,
  result_id VARCHAR(64) NULL,
  state VARCHAR(16) NOT NULL,
  response_type VARCHAR(32) NULL,
  terminal_stage VARCHAR(32) NULL,
  error_code VARCHAR(64) NULL,
  diagnostic_id VARCHAR(64) NULL,
  absolute_deadline DATETIME(3) NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL,
  completed_at DATETIME(3) NULL,
  UNIQUE KEY uk_invocation_correlation (request_correlation_id),
  KEY idx_invocation_state_deadline (state, absolute_deadline),
  KEY idx_invocation_scope (scope_type, scope_id, created_at),
  CONSTRAINT ck_invocation_origin CHECK (
    (invocation_type='CHAT' AND conversation_id IS NOT NULL AND turn_id IS NOT NULL
      AND run_id IS NULL AND task_id IS NULL AND attempt_id IS NULL)
    OR
    (invocation_type='TASK' AND conversation_id IS NULL AND turn_id IS NULL
      AND run_id IS NOT NULL AND task_id IS NOT NULL AND attempt_id IS NOT NULL)
  ),
  CONSTRAINT ck_invocation_terminal_shape CHECK (
    (state='PROCESSING' AND response_type IS NULL AND result_id IS NULL
      AND context_write_refs_json IS NULL
      AND terminal_stage IS NULL AND error_code IS NULL AND completed_at IS NULL)
    OR
    (state='COMPLETED' AND response_type='SUCCESS'
      AND result_id IS NOT NULL AND checkpoint_hash IS NOT NULL
      AND terminal_stage IS NOT NULL
      AND context_write_refs_json IS NOT NULL
      AND JSON_TYPE(context_write_refs_json)='ARRAY'
      AND error_code IS NULL AND completed_at IS NOT NULL)
    OR
    (state='COMPLETED' AND response_type='CLARIFY'
      AND result_id IS NOT NULL AND checkpoint_hash IS NULL
      AND terminal_stage IS NOT NULL
      AND context_write_refs_json IS NULL
      AND error_code IS NULL AND completed_at IS NOT NULL)
    OR
    (state='FAILED' AND response_type='FAILURE' AND result_id IS NULL
      AND context_write_refs_json IS NULL
      AND terminal_stage IS NOT NULL AND error_code IS NOT NULL
      AND completed_at IS NOT NULL)
    OR
    (state='CANCELLED' AND response_type='CANCELLED' AND result_id IS NULL
      AND context_write_refs_json IS NULL
      AND terminal_stage IS NOT NULL
      AND error_code IN ('CANCELLED','DEADLINE_EXCEEDED')
      AND completed_at IS NOT NULL)
  ),
  CONSTRAINT fk_invocation_conversation FOREIGN KEY (conversation_id)
    REFERENCES agent_conversation(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 7.2 `agent_invocation_result`

```sql
CREATE TABLE agent_invocation_result (
  result_id VARCHAR(64) PRIMARY KEY,
  invocation_id VARCHAR(64) NOT NULL,
  response_type VARCHAR(32) NOT NULL,
  output_schema VARCHAR(128) NULL,
  output_schema_version VARCHAR(32) NULL,
  encrypted_payload LONGBLOB NULL,
  encryption_key_id VARCHAR(128) NULL,
  encryption_nonce VARBINARY(12) NULL,
  algorithm_version VARCHAR(32) NULL,
  safe_message TEXT NOT NULL,
  safe_summary TEXT NULL,
  created_at DATETIME(3) NOT NULL,
  UNIQUE KEY uk_result_invocation (invocation_id),
  CONSTRAINT ck_result_response_type CHECK (response_type IN ('SUCCESS','CLARIFY')),
  CONSTRAINT ck_result_payload_shape CHECK (
    (response_type='SUCCESS' AND output_schema IS NOT NULL
      AND output_schema_version IS NOT NULL AND encrypted_payload IS NOT NULL
      AND encryption_key_id IS NOT NULL AND encryption_nonce IS NOT NULL
      AND algorithm_version IS NOT NULL)
    OR
    (response_type='CLARIFY' AND output_schema IS NULL
      AND output_schema_version IS NULL AND encrypted_payload IS NULL
      AND encryption_key_id IS NULL AND encryption_nonce IS NULL
      AND algorithm_version IS NULL)
  ),
  CONSTRAINT fk_result_invocation FOREIGN KEY (invocation_id)
    REFERENCES agent_invocation_record(invocation_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 7.3 `agent_turn` 目标变化

保留 user message、assistant message、response type 和交互终态；新增 `invocation_id`、`result_id`，删除 `intent`、`query_context_json`。Turn/Invocation数据库`response_type`统一存内部`InvocationResponseType`值SUCCESS/CLARIFY/FAILURE/CANCELLED，Entry再穷尽映射到D02_01目标API `AgentResponseType`；禁止直接持久化API enum或按result subtype建立终态。`invocation_id`唯一，Turn不复制Plan/Snapshot/result payload。

```sql
CREATE TABLE agent_turn (
  id VARCHAR(64) PRIMARY KEY,
  turn_seq BIGINT NOT NULL AUTO_INCREMENT,
  conversation_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(128) NOT NULL,
  invocation_id VARCHAR(64) NOT NULL,
  result_id VARCHAR(64) NULL,
  user_message TEXT NOT NULL,
  response_type VARCHAR(32) NULL,
  assistant_message TEXT NULL,
  status VARCHAR(32) NOT NULL,
  error_code VARCHAR(64) NULL,
  diagnostic_id VARCHAR(64) NULL,
  created_at DATETIME(3) NOT NULL,
  completed_at DATETIME(3) NULL,
  UNIQUE KEY uk_turn_seq (turn_seq),
  UNIQUE KEY uk_turn_invocation (invocation_id),
  KEY idx_turn_conversation_status_seq (conversation_id, status, turn_seq),
  CONSTRAINT ck_turn_terminal_shape CHECK (
    (status='PROCESSING' AND response_type IS NULL AND result_id IS NULL
      AND assistant_message IS NULL AND error_code IS NULL AND completed_at IS NULL)
    OR
    (status='SUCCEEDED' AND response_type IN ('SUCCESS','CLARIFY')
      AND result_id IS NOT NULL AND assistant_message IS NOT NULL
      AND error_code IS NULL AND completed_at IS NOT NULL)
    OR
    (status='FAILED' AND response_type='FAILURE' AND result_id IS NULL
      AND assistant_message IS NOT NULL AND error_code IS NOT NULL
      AND completed_at IS NOT NULL)
    OR
    (status='CANCELLED' AND response_type='CANCELLED' AND result_id IS NULL
      AND assistant_message IS NOT NULL
      AND error_code IN ('CANCELLED','DEADLINE_EXCEEDED')
      AND completed_at IS NOT NULL)
  ),
  CONSTRAINT fk_turn_conversation FOREIGN KEY (conversation_id)
    REFERENCES agent_conversation(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 8. Recovery

### 8.1 组件

- `InvocationRecoveryJob`：按固定 delay 只选择过期 PROCESSING invocationId，不能持有大事务。
- `InvocationRecoveryService`：遍历 ID，调用独立事务 bean。
- `InvocationRecoveryTxService.recoverOne(String invocationId, Instant now)`：`REQUIRES_NEW`，同事务 CAS Invocation 和 Turn 到 FAILED/CANCELLED。

### 8.2 规则

1. deadline/cancel evidence 明确时终结 CANCELLED；其他悬挂终结 FAILED/RECOVERY。
2. 已终态或 CAS loser 只重读，不覆盖。
3. 不补写 SUCCESS、Result、Context，不重做 Planning/Core/Handler/Adapter。
4. 任一 Turn CAS 不一致使 recovery 事务回滚，不允许半终结。
5. D06 后通过 Task State Boundary 将 Attempt 纳入同一 Agent DB 事务；D02 不创建相关类。

### 8.3 Conversation/Result 清理

D03修改现有`ConversationCleanupJob`和`ConversationService.cleanupExpired`：不再先独立删除Turn后猜测孤儿Conversation，而是按owned/expired Conversation批次调用`AgentStateCleanupService.cleanupConversation(conversationId)`。该方法先从同一cleanup candidate读取全局唯一conversationId并构造`ConversationScope`，调用`ContextScopeRetirementParticipant.retire`；只有retirement独立事务已提交，才调用独立Bean `AgentStateCleanupTxService.deleteConversation(conversationId)`，后者以`REQUIRES_NEW`短事务删除Conversation，由数据库级联删除Turn、CHAT Invocation、Invocation Result和以该Invocation为source的Context。retirement失败则不删除并重试；后续物理删除失败时Context已经不可读，重试不得重新开放。禁止在`AgentStateCleanupService`内用self-invocation伪造第二个事务。Context TTL即使尚未到期也不能跨已过期/删除Conversation继续读取。

`AgentStateCleanupService`方法：`int cleanupExpired(Instant cutoff,int batchSize)`、`void cleanupConversation(String conversationId)`。`AgentStateCleanupTxService`唯一方法：`void deleteConversation(String conversationId)`。D06 RunScope使用独立Task State Boundary，不复用Conversation删除SQL。

---

## 9. Deadline 与取消

所有组件只使用 Handle 的 absoluteDeadline：

| 边界 | 要求 |
|---|---|
| Start | deadline 必须晚于 now 且不超过配置上限 |
| Planning/checkpoint | 不得延长；到期直接 CANCELLED |
| Core/Validator/Handler | 每个边界前后检查同一 token/deadline |
| Adapter/downstream | timeout=min(remaining, endpoint limit) |
| finalization | 到期后未开始业务成功提交则丢弃迟到 candidate，提交 CANCELLED |

取消监听器只能设置`CancellationSource`；不得中断finalization的数据库原子提交。一旦finalization终态CAS已返回rowCount=1并进入同一事务后续步骤，结果由该CAS/事务决定，取消方只能在事务结束后重读终态。

---

## 10. 配置与观测

`InvocationLifecycleProperties`（`@ConfigurationProperties("agent.lifecycle")`）字段：`maxInvocationDuration`、`recoveryGrace`、`recoveryDelay`、`recoveryBatchSize`。Validator强制duration/delay/grace为正、batch为1～1000。Invocation Result不建立独立retention/cleanup配置，只随Invocation/Conversation外键级联删除，避免第二生命周期。

指标：start/checkpoint/finalization 成功与耗时、commit unknown、CAS loser、PROCESSING age、recovery 数、deadline/cancel、原子视图不完整错误。日志只记录 invocationId/capabilityId/stage/errorCode/diagnosticId，不记录 payload/Snapshot/JWT。

---

## 11. 测试设计

### 11.1 Lifecycle/事务

- `atomicallyCreatesConversationTurnInvocation`
- `returnsHandleOnlyAfterCommit`
- `reconstructsHandleOnlyFromCompleteMatchingStartAfterCommitUnknown`
- `rejectsCorrelationReplayWithDifferentStartCommand`
- `loadsOnlyPriorSafeSucceededHistoryByHandle`
- `finalizesHistoryProjectionFailureAfterCommittedStart`
- `finalizesHistoryDeadlineOrCallerCancelAfterCommittedStart`
- `rejectsMismatchedPlanningCorrelation`
- `doesNotEnterCoreWhenCheckpointRollbackConfirmed`
- `doesNotEnterCoreWhenCheckpointCommitUnknown`
- `acceptsIdempotentSameCheckpointOnly`
- `atomicallyCommitsResultContextInvocationAndTurn`
- `rollsBackAllWhenContextCasFails`
- `rollsBackAllWhenResultEncryptionFails`
- `rereadsCompleteResultAfterCommitUnknown`
- `reconstructsChatOriginForEveryTerminalResponse`
- `requiresExplicitContextWriteCommitRefsForSuccessAtomicView`
- `roundTripsCanonicalInvocationAuditJsonAndRejectsUnknownFields`
- `neverReturnsSuccessFromIncompleteAtomicView`
- `finalizesClarificationWithoutCoreOrContext`
- `persistsReportedAndNotReportedPlanningAudits`
- `mapsDeadlineAndCallerCancelToCancelled`
- `commitExecutionFailureUsesExecutionFailureSafeMessage`
- `commitExecutionFailureFallsBackWhenSafeMessageBlank`
- `mapsFieldForbiddenToAgentFieldForbiddenAfterReread`

### 11.2 Recovery

- `recoversOneInvocationPerRequiresNewTransaction`
- `rollsBackInvocationWhenTurnCasFails`
- `doesNotReexecuteBusiness`
- `doesNotWriteResultOrContext`
- `obeysExistingTerminalOnCasLoss`
- `conversationCleanupCascadesTurnInvocationResultAndContext`
- `conversationCleanupKeepsContextUnreadableWhenPhysicalDeleteFails`

### 11.3 Schema/架构

- Testcontainers MySQL 验证 DDL、FK、unique/CAS 和 rollback。
- ArchUnit：`invocation.model`不能依赖planning/lifecycle/kernel/metadata；Lifecycle不能依赖Runtime client/Handler/Adapter；Core不能依赖Mapper。
- `agent-p0.sql` 不得含 `intent`、`query_context_json` 或 ResultRef/Task 表。

---

## 12. 计划文件清单

路径约定：`invocation model`对应`agent-service/src/main/java/com/dylan/agent/invocation/model/<Name>.java`；`lifecycle model/service`分别对应`.../com/dylan/agent/lifecycle/model/<Name>.java`与`.../com/dylan/agent/lifecycle/<Name>.java`（Properties及Validator位于`lifecycle/config/`）；`persistence`对应`.../lifecycle/persistence/<Name>.java`；测试对应`agent-service/src/test/java/com/dylan/agent/lifecycle/`。下表中的每个名称都是独立Java文件；只有第12.1节明确的Mapper parameter record、`StartTxService.StartWriteResult`、`CheckpointResult.Status/CommittedCheckpoint`以及`PlanningCheckpoint.ContextSnapshotRef`是nested type。

| 范围 | 文件 |
|---|---|
| invocation model | `ExecutionSubjectRef`、`ContextOwnerRef`、`InvocationScope`、`ConversationScope`、`RunScope`、`InvocationOrigin`、`ChatInvocationOrigin`、`TaskInvocationOrigin`、`InvocationHandle`、`InvocationType`、`InvocationState`、`ExecutionStage`、`KernelErrorCode`、`CancellationToken`、`CancellationSource` |
| lifecycle model | `InvocationRecord`、`PlanningCheckpoint`、`CheckpointResult`、`FinalizedInvocationResult`、`InvocationResponseType`、`StoredInvocationResult`、`ContextWriteCommitRef` |
| lifecycle service | `StartChatCommand`、`ExecutionLifecycleService`、`StartTxService`、`CheckpointTxService`、`FinalizationTxService`、`InvocationRecoveryJob`、`InvocationRecoveryService`、`InvocationRecoveryTxService`、`AgentStateCleanupService`、`AgentStateCleanupTxService`、`InvocationLifecycleProperties`、`InvocationLifecyclePropertiesValidator`、`lifecycle/port/ContextFinalizationParticipant`、`lifecycle/port/ContextScopeRetirementParticipant` |
| persistence | `AgentInvocationRecordEntity`、`AgentInvocationResultEntity`、`InvocationRecordMapper`、`InvocationResultMapper`、`ConversationPersistenceAdapter`、`TurnPersistenceAdapter`、`InvocationResultRepository`、`InvocationAtomicView`、`InvocationAtomicViewRepository`、`InvocationAuditJsonCodec` |
| existing modifications | `AgentTurnEntity`、`AgentTurnMapper`、`TurnStatus`（新增CANCELLED）、`ConversationCleanupJob`、`ConversationService`、`AgentConversationMapper`、`agent-p0.sql`；`application.yml`由D02_03统一汇总所有D02配置 |
| tests | `ExecutionLifecycleServiceTest`、`FinalizationTxServiceIT`、`InvocationRecoveryServiceIT`、`AgentStateCleanupServiceIT`、`InvocationSchemaIT`、`InvocationAuditJsonCodecTest`、`DeadlineCancellationTest`、`LifecycleArchitectureTest` |

以上计划文件由D03一次实施。D02_03的Context Entity/Mapper/crypto和统一`application.yml`另由其文件清单负责，但DDL汇总到本文拥有的`agent-p0.sql`。

### 12.1 完整方法索引

值对象使用record或defensive-copy final class，除规范化构造器、只读访问器和第2、3节明确方法外无setter。其余类的方法如下：

| 类/接口 | 方法 |
|---|---|
| `ExecutionLifecycleService` | `startChat`、`checkpoint`、`executeAndFinalize`、`finalizeClarification`、`finalizePlanningFailure`、`finalizeCancelled`、`reread`（签名见§4.2） |
| `CheckpointResult` | `committed(Status,CommittedCheckpoint)`、`withoutCheckpoint(Status)`、`requireCommittedCheckpoint()`及只读访问器；nested类型见§4.4 |
| `StartTxService` | `StartWriteResult createOrVerify(StartChatCommand)`；`REQUIRES_NEW`；`StartWriteResult`为package-private nested record |
| `CheckpointTxService` | `CheckpointResult write(InvocationHandle,ExecutablePlanningResult)` |
| `FinalizationTxService` | 六个`void`方法：`commitSuccess(InvocationHandle,CommittedCheckpoint,ExecutionSuccess)`、`commitClarification(InvocationHandle,ResolvedClarification)`、`commitPlanningFailure(InvocationHandle,PlanningFailure)`、`commitPlanningCancellation(InvocationHandle,PlanningCancellation)`、`commitExecutionFailure(InvocationHandle,CommittedCheckpoint,ExecutionFailure)`、`commitExecutionCancelled(InvocationHandle,CommittedCheckpoint,ExecutionFailure)`；各方法`REQUIRES_NEW`，三个Execution方法校验token与Handle/correlation及持久化checkpoint相等，SUCCESS还校验outcome capabilityId/planKind，后两者分别要求`cancelled=false/true`并保留checkpoint audit；`commitExecutionFailure`优先持久化`ExecutionFailure.safeMessage`，为空时使用固定执行失败兜底提示 |
| `ContextFinalizationParticipant` | `persist(List<ApprovedContextWrite>)` |
| `ContextScopeRetirementParticipant` | `retire(ConversationScope,Instant)` |
| `InvocationRecordMapper` | `insert(AgentInvocationRecordEntity)`、`checkpointCas(CheckpointUpdate)`、`finalizeSuccessCas(SuccessUpdate)`、`finalizeClarifyCas(ClarifyUpdate)`、`finalizePlanningFailureCas(PlanningFailureUpdate)`、`finalizePlanningCancelledCas(PlanningCancelUpdate)`、`finalizeExecutionFailureCas(ExecutionFailureUpdate)`、`finalizeExecutionCancelledCas(ExecutionCancelUpdate)`、`selectByInvocationId(String)`、`selectByCorrelationId(String)`、`selectExpiredProcessing(Instant,int)` |
| `InvocationResultMapper` | `insert(AgentInvocationResultEntity)`、`selectByInvocationId(String)` |
| `ConversationPersistenceAdapter` | `openOrCreateOwned(String,String,Instant)`、`touchOwned(String,String,Instant)` |
| `AgentConversationMapper` | `selectExpiredIds(Instant,int)`、`deleteById(String)`；删除旧`deleteExpiredWithoutTurns` |
| `ConversationCleanupJob` | `cleanup()`，只委托`AgentStateCleanupService` |
| `ConversationService` | `loadRecentTurns(InvocationHandle,int maxMessages)`；删除旧自由conversationId/userId读取签名；旧`cleanupExpired`删除或改为package-private委托，不再直接先删Turn |
| `TurnPersistenceAdapter` | `createWithInvocation(TurnCreate)`、`completeSuccessCas(TurnSuccessUpdate)`、`completeClarifyCas(TurnClarifyUpdate)`、`completeFailureCas(TurnFailureUpdate)`、`completeCancelledCas(TurnCancelUpdate)`、`selectByInvocationId(String)`、`selectRecentSucceededBefore(String conversationId,String currentInvocationId,int maxTurns)` |
| `InvocationResultRepository` | `storeSecuredResult(String resultId,String invocationId,SecuredResult,Instant)`、`storeClarification(String resultId,String invocationId,ResolvedClarification,Instant)`、`loadStoredResult(String invocationId)` |
| `InvocationAtomicViewRepository` | `InvocationAtomicView load(String invocationId)` |
| `InvocationAuditJsonCodec` | `writeOperationAudit(PlanningOperationAudit)`、`readOperationAudit(String)`、`writeContextSnapshotRefs(List<PlanningCheckpoint.ContextSnapshotRef>)`、`readContextSnapshotRefs(String)`、`writeContextWriteCommitRefs(List<ContextWriteCommitRef>)`、`readContextWriteCommitRefs(String)` |
| `InvocationRecoveryJob` | `scan()` |
| `InvocationRecoveryService` | `recoverBatch(Instant,int)` |
| `InvocationRecoveryTxService` | `recoverOne(String,Instant)` |
| `AgentStateCleanupService` | `cleanupExpired(Instant,int)`、`cleanupConversation(String)` |
| `AgentStateCleanupTxService` | `deleteConversation(String)`；`REQUIRES_NEW` |
| `InvocationLifecyclePropertiesValidator` | `validate(InvocationLifecycleProperties)` |

`CheckpointUpdate`、`SuccessUpdate`、`ClarifyUpdate`、`PlanningFailureUpdate`、`PlanningCancelUpdate`、`ExecutionFailureUpdate`、`ExecutionCancelUpdate`及Turn更新参数均为对应Mapper内的package-private nested record，字段与第3、6、7节一一对应；不增加独立文件，也不作为跨包API。

---

## 13. 验收标准与结论

1. Lifecycle 是唯一状态协调者，Core/Context/Mapper 不自行决定终态。
2. `ExecutablePlanningResult` checkpoint 完整绑定 Registration/Snapshot/correlation/deadline。
3. deadline/cancellation 不被映射为 FAILED。
4. commit unknown/CAS loser 可通过持久化 filtered result 重建响应且不重执行业务。
5. SUCCESS 原子提交 result、Context、Invocation、Turn；任一步失败不返回 SUCCESS。
6. Recovery 原子终结 Invocation+Turn，不产生半终态。
7. Turn 不复制完整 Plan/Snapshot/result payload，Invocation Result 不是 Multi-Agent ResultRef。
8. Invocation Record预留typed TASK origin安全引用但D02/D03不创建Task表、外键或状态机。
9. 所有类、方法、SQL、配置、事务和测试已明确列出。
10. `FIELD_FORBIDDEN`可以通过Invocation终结、权威重读和API映射稳定返回为字段权限不足提示。
11. `commitExecutionFailure`不会把内部异常message作为用户提示，且不会覆盖Core给出的安全字段越权提示。
12. `commitPlanningFailure`不会把 Runtime 原始输出、repair prompt、repair payload 或 provider message 作为用户提示；`OUTPUT_REPAIR_EXHAUSTED` 只表现为安全规划失败提示和内部诊断ID。

最终评审结论（2026-06-30）：本文已与D02_00、D02_01、D02_03及上级L1交叉复审；Start、checkpoint、原子finalization、commit unknown、CAS loser、recovery、deadline/cancel和结果重建闭环完整，当前文档基线下无未决问题。D01退出后必须复核PlanningResult所引用的实际生成类型。
