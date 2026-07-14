# 可信执行内核与 Invocation 生命周期 L2 实施详细设计 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 可信执行内核与 Invocation 生命周期 L2 实施详细设计 |
| 文档路径 | `docs/design/P1_V2/02_可信执行内核与Invocation生命周期_L2实施详细设计_v2.0.md` |
| 文档状态 | Implemented |
| 当前版本 | v2.0 |
| 创建日期 | 2026-07-13 |
| 最后更新日期 | 2026-07-14 |
| 适用代码基线 | `28e662a97110f7d3d39211f3ac841a39491fc1b8` |
| 适用范围 | Capability 注册、Validator、可信执行 Core、Invocation model/lifecycle/persistence、Planning Artifact、checkpoint、Context scope codec |
| 上级文档 | 四份当前 L0/L1 架构基线 |
| 关联文档 | P1_V2/00、01、03、04、05、06；旧 D02_00～02 仅为历史来源，不再是实施前置 |
| 是否可作为实现依据 | 是；CHAT-only Invocation、Planning Artifact、checkpoint、Core 与 Lifecycle 已完成本地实施和验证 |

## 2. 修订历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | 修正旧 D02 提前实现 D06 类型和 Planning Artifact 引用身份风险 | 新建 CHAT-only Invocation 与逻辑 Planning Artifact 迁移设计 |
| 2 | 2026-07-13 | 10.3、10.4、19、21～24 | P1_V2 跨文档复评发现 canonical encoding 与 03 不一致 | 统一为 identity-free components 经专用 PAI-1 canonicalizer 生成 identity，并关闭文档级阻塞项 |
| 3 | 2026-07-13 | 全文 | P1_V2 改为独立基线 | 合并 D02_00、D02_01、D02_02 的 Registration、Validator、Core、Lifecycle、持久化和集成门禁，不再要求回查旧文档 |
| 4 | 2026-07-13 | 4～20、22～24 | 本次 cross-layer 评审发现 Lifecycle/Core 职责倒置、资源限额冻结点错误、恢复语义越界及持久化契约不完整 | 按 L0/L1 重排 checkpoint→Core→finalization 主链，收敛 Definition/Handler/Registration 边界，补齐原子开始、Invocation 数据字典、终结事务、commit-unknown 与失败恢复规则 |
| 5 | 2026-07-13 | 第1～2节 | P1_V2/P2_V3全集终检发现01～03仍引用旧代码快照 | 仅将适用代码基线对齐统一`816e2c855574da5326379128bfb3e230241d2fe3`；不新增评审轮次，不改变已通过设计结论 |
| 6 | 2026-07-13 | 第1～2、24节 | P1_V2/P2_V3 全集终检同步终态 | 标记 P1_V2 全集评审已完成，修正任务摘要中的 Approved/M0 授权边界；不新增评审轮次，不改变 S0/S1 结论 |
| 7 | 2026-07-14 | 第1～3、23～24节 | 当前仓库可信执行主链已按设计完成实施 | 对齐代码基线，确认 Run/Task concrete seam 已删除、PAI-1/checkpoint/Core/Lifecycle/Context codec 已闭合，将状态同步为 Implemented |

## 3. 文档状态说明

| 状态 | 含义 | 是否可作为开发依据 |
|---|---|---:|
| Draft | 草稿 | 否 |
| In Review | 评审中 | 否 |
| Approved | 评审通过 | 是 |
| Implementing | 实施中 | 是 |
| Implemented | 已实施并对齐 | 是 |
| Deprecated | 已废弃 | 否 |

当前状态：Implemented。CHAT-only Invocation、逻辑 Planning Artifact identity、checkpoint 后进入 Core、原子开始/终结与 Context scope codec 已完成本地实施和验证。

## 4. 背景与目标

本文定义从 Capability 注册到 Invocation 终态的完整可信执行主链。当前代码提前固化了未启用的 Run/Task concrete type，旧设计又可能把“同一 Planning Artifact”误解为 JVM 引用相等。目标是在保持共享内核入口中立的同时，收敛为 CHAT-only concrete model、逻辑 artifact identity、注册快照与授权快照绑定，以及只把无主 PROCESSING 原子终结为失败或取消的有界恢复；当前不恢复执行、不补写成功。

## 5. 设计范围

### 5.1 范围内

- Invocation scope/origin/type 的 CHAT-only concrete model；
- `InvocationHandle` 的入口中立引用和当前构造门禁；
- `ExecutablePlanningResult` 作为当前 Planning Artifact 载体；
- `PlanningArtifactIdentity` 的 canonical digest；
- `ExecutionCommand`、checkpoint、Core 的逻辑 identity 校验；
- Context scope codec 和数据库 shape 的同步收敛。
- Capability Definition/Registration、Registry、Plan Validator、Handler 的职责和不变量；
- Execution Core 的标准执行序列、typed failure，以及 Lifecycle 终结事务边界；
- Invocation Start/checkpoint/CAS/终态/恢复和持久化模型。

### 5.2 范围外

- future Multi-Agent 的 RunScope/Task origin 最终字段；
- Planning Route/Plan 协议；
- Context payload 或业务结果结构；
- 代码实施。

## 6. 上级文档约束

1. 当前只启用 ConversationScope，不创建未使用 TASK DTO/状态/配置。
2. Planning Artifact 同一性是 Invocation 级逻辑身份，不是 JVM object identity。
3. Entry/Planning/Lifecycle/Core 保持不依赖 Conversation/Turn Entity；CHAT origin 只存在于 Entry/Handle 边界。
4. future Multi-Agent 可以扩展 sealed union，但必须先完成并评审 Multi-Agent L1。

## 7. 关联文档与边界

| 文档 | 本文职责 | 对方职责 | 边界 |
|---|---|---|---|
| P1_V2/01 | 提供 Route/Plan/Result/错误公共契约 | 本文只消费 generated/validated plan | Runtime 不注册或执行 capability |
| P1_V2/03 | 提供授权、Context、Result Security | 本文编排安全端口 | Core 不实现权限规则 |
| P1_V2/04 | 提供 adapter registration/domain projection | 本文使用快照和 validated model | Core 不依赖业务域类 |
| P1_V2/05 | 提供 Effective Capability Resource Limits 权威类型及 local port operation context | 本文只复检并向 Validator/Handler/Provider/Result Security 传递 Authorization Snapshot 已冻结的同一或可证明更严格的值 | Core 不冻结、不重算限额，不读取 capability 私有配置 |
| P1_V2/06 | 提供原子迁移顺序与门禁 | 本文提供目标签名与算法 | 不重复维护第二份设计 |

## 8. 设计边界与约束

- 不将 `PlanningArtifactIdentity` 暴露为 HTTP DTO。
- 不持久化完整 Raw Plan 或 Snapshot payload。
- 不保留 `RunScope`/`TaskInvocationOrigin` deprecated facade。
- `scope_type`/`origin_type` 数据库列可保留为演进 seam，但当前 CHECK 只接受 `CONVERSATION`/`CHAT`。
- `InvocationType` 当前可删除并由 Handle 的唯一 CHAT factory 隐含；若保留枚举以服务审计，唯一合法值只能是 `CHAT`。
- 唯一持久化状态机是 Invocation 的 `PROCESSING → COMPLETED|FAILED|CANCELLED`；Context 仅有 CAS currentness，Planning/Authorization/Context snapshot 与 artifact identity 都是不可变值，不建立平行生命周期。

## 9. 总体设计

```text
StartChatCommand
  → Lifecycle atomic Start: Turn + Invocation(PROCESSING) → InvocationHandle
  → Planning: Resolved Registration + Authorization Snapshot/effective limits
              + capability-scoped Context Snapshot → ExecutablePlanningResult
  → Lifecycle checkpoint CAS committed
  → ExecutionCommand(handle, same immutable planning artifact, cancellation)
  → Core: currentness/binding/validation/handler/output security → ExecutionOutcome
  → Lifecycle finalization transaction: safe result + approved Context
                                      + Invocation/Turn terminal CAS
```

## 10. 详细功能设计

### 10.0 Capability 注册、校验与可信执行主链

`CapabilityDefinition` 只声明 capabilityId、planKind、Capability Routing Descriptor、input/output ContractRef、Context read/write ContractRef 与声明、capability resource limit ContractRef 及适用维度、risk level、execution mode、Domain Mode，以及 Domain Mode 非 `NONE` 时所需的 Adapter Role。Definition 不保存 Profile/Policy/Permission、请求级限额、幂等策略或终结参与者。`CapabilityRegistration<R,V,O>` 不可变绑定 Definition、Raw Plan 类型、唯一 Validator、Validated Plan 类型、唯一 Handler、output type/ContractRef、受控类型桥与 registration identity；`CapabilityRegistry` 构建不可变 snapshot，同 capabilityId 重复、契约不闭合、类型桥不一致、角色声明不合法或组件缺失时启动失败。

Validator 只接收 Registration 类型桥提供的 Raw Plan 与最小 `ExecutionValidationContext`，执行纯校验和 canonical binding，输出构造路径受限的 typed `ValidatedCapabilityPlan`；不得调用外部系统、写 Context 或返回最终结果。Handler 只接收 Registration 类型桥提供的 Validated Plan 与最小 `ExecutionContext`；后者携带已验证主体/范围引用、同一 absolute deadline/cancellation、Authorization Snapshot 已冻结的同一或可证明更严格的 Effective Capability Resource Limits，以及可选的一次解析 Adapter Execution Binding。Handler 不接收 `ExecutionCommand`，不得重新解析 Raw Plan、重新计算权限/资源或二次选择 Adapter。

Lifecycle 必须先完成 Planning checkpoint，再把 `ExecutionCommand` 交给 Core；checkpoint 不属于 Core。Core 不重新查询 Registry、不重新加载 Context、不冻结资源限额、不持久化，也不执行 finalization。Core 固定执行序列如下，任何步骤失败均停止后续步骤并返回 typed failure/cancellation：

1. 校验 Invocation Handle、absolute deadline、cancellation 与 Planning Artifact 逻辑身份。
2. 校验 PlanningResult 已携带的同一 `ResolvedRegistration` identity、不可变性，以及 capabilityId/planKind/Raw subtype 绑定；不查询 Registry 二次路由。
3. 通过授权边界复检 Authorization Snapshot 与当前权限，只接受同一或可证明更严格的执行范围和 Effective Capability Resource Limits。
4. 通过 Context Boundary 复检 Planning 已消费 Context Snapshot 的 request correlation、Owner、Scope、schema/ContractRef、record version 与 TTL；变化即 fail closed，不加载另一份 Context 继续执行。
5. Domain Mode 非 `NONE` 时由 metadata 边界一次解析授权的 Adapter Execution Binding，并校验其与 Registration/Domain/当前可用性一致。
6. 构造携带同一 limits 和安全 binding 投影的 `ExecutionValidationContext`，经 Registration 受控类型桥调用 Validator，得到不可变 Validated Plan。
7. 构造 `ExecutionContext`，经同一 Registration 类型桥把 Validated Plan 交给 Handler；Handler 可通过已绑定 Adapter 或 capability-local port 执行，但不得自动重试。
8. 校验候选 output runtime type/ContractRef、Context write 声明与同一 limits，经 Result Security 完成字段过滤和 mask，形成 `ExecutionOutcome`。
9. 把候选结果返回 Lifecycle；只有 Lifecycle 的本地终结事务可以提交安全结果、批准的 Context、Invocation 与 Turn 终态。

### 10.1 Invocation Scope 与 Origin

目标 Java 结构：

```java
public sealed interface InvocationScope permits ConversationScope {
    String scopeId();
}

public sealed interface InvocationOrigin permits ChatInvocationOrigin {
}
```

`ConversationScope`、`ChatInvocationOrigin` 保持不可变。删除：

- `RunScope.java`；
- `TaskInvocationOrigin.java`；
- `InvocationType.TASK`；
- `ContextBindingSupport` 的 `RUN` 分支；
- 所有“当前阶段不创建但后续阶段直接复用”的空壳注释和测试。

为了保持未来扩展能力，future Multi-Agent 在其 L1 冻结字段后通过修改 permits 列表新增 subtype；这属于编译期显式变化，不需要当前空类型。

### 10.2 InvocationHandle

推荐以命名工厂收紧构造：

```java
public static InvocationHandle forChat(
    String invocationId,
    ChatInvocationOrigin origin,
    String requestCorrelationId,
    ExecutionSubjectRef subject,
    ContextOwnerRef owner,
    ConversationScope scope,
    AgentProfileRef agentProfileRef,
    Instant absoluteDeadline)
```

Handle 字段继续使用中立类型 `InvocationOrigin`、`InvocationScope`，Core/Planning 不依赖 Conversation Entity。当前 factory 强制：origin conversationId 等于 scopeId，subject/owner 与 Start 已认证主体闭合。

### 10.3 PlanningArtifactIdentity

新增 Java 内部值：

```java
public record PlanningArtifactIdentity(
    String invocationId,
    String requestCorrelationId,
    String registrationIdentity,
    String authorizationSnapshotRef,
    String contextSnapshotSetDigest,
    Instant absoluteDeadline,
    String bindingDigest) {}
```

`bindingDigest` 使用版本化 canonical 算法计算：

```text
PAI-1
  + invocationId
  + requestCorrelationId
  + capabilityId/domain/planKind
  + registrationIdentity
  + rawPlan canonical contract digest
  + authorizationSnapshot safe reference
  + sorted context snapshot safe references
  + route/plan operation metadata safe digest
  + absoluteDeadline
```

canonical encoding 由本文定义、P1_V2/06 迁移门禁冻结的专用 `PlanningArtifactCanonicalizer` 唯一负责：对强类型 `PlanningArtifactCanonicalForm` 进行稳定 canonical JSON 序列化，集合按稳定业务 key 排序，再计算 SHA-256。digest 不包含 Java class name、对象地址、capturedAt 非语义字段、完整 payload 或凭据；不得复用受限根类型的 `PayloadJsonCodec`，也不得使用自由 Map。

### 10.4 ExecutablePlanningResult

`ExecutablePlanningResult` 继续作为当前进程内 Planning Artifact 载体，新增：

- `String invocationId`；
- `PlanningArtifactIdentity artifactIdentity`；
- `PlanningArtifactIdentity artifactIdentity()`。

Builder 先形成不含 identity 的强类型 `PlanningArtifactComponents`，再调用 canonicalizer 生成 identity 并构造最终结果，不接受调用方传入自由 digest。`invocationId` 必须等于 Handle；由于 PlanningService 已持有 Handle，构造时从 Handle 派生。

### 10.5 ExecutionCommand、Registration 绑定与 Core

`ExecutionCommand` 仍只聚合 Handle、`ExecutablePlanningResult`、CancellationToken。构造器验证：

1. invocationId/correlation/deadline 相同；
2. artifact identity 中 invocation/correlation/registration 与 result 相同；
3. 重新计算 binding digest 与冻结值相同；
4. 不执行 `==`、`System.identityHashCode` 或对象地址相关校验。

Core 先执行 `validatePlanningArtifactIdentity()`，再对 `ExecutablePlanningResult` 已携带的 `ResolvedRegistration` 执行 `validateIdentity()`；二者分别证明 artifact 绑定完整性和 Planning 解析出的 Registration 未被替换。Core 不调用 `CapabilityRegistry.resolve(...)`，也不按 capabilityId/planKind 二次选择 Registration、Validator 或 Handler。Registration 受控类型桥负责 Raw Plan 类型校验、Validator 调用以及 Validated Plan 到 Handler 的唯一桥接；Core 不执行 unchecked Handler cast。

### 10.6 Checkpoint

`PlanningCheckpoint` 保存 `planningArtifactBindingDigest`，checkpoint hash 覆盖该字段。Commit unknown 后仍不恢复 Core，因为数据库不保存 Raw Plan；digest 只用于审计/防替换，不赋予恢复能力。

### 10.7 Context Scope Codec

`ContextBindingSupport.scopeType` 只接受 `ConversationScope` 并返回 `CONVERSATION`；`scope` 只解析 `CONVERSATION`。读取到 `RUN` 或未知值 fail closed。当前无生产数据兼容责任，不保留 RUN 解析。

### 10.8 Invocation Lifecycle 与持久化

`InvocationLifecyclePort.start(StartInvocationCommand)` 在同一事务中创建/校验 Conversation，并原子插入 Turn 与 Invocation(PROCESSING)；任一步失败整体回滚且不调用 Planning。`requestCorrelationId` 在当前 CHAT 入口由服务端随 invocationId 一次生成并保持全链唯一，只有 Start 事务确认提交后才返回不可变 `InvocationHandle` 并允许 Entry 调用 Planning。当前 Agent Chat HTTP 契约没有客户端幂等键，因此网络层重试明确创建新 Invocation，不把 correlation 误当外部幂等键；当前 P1_V2 只允许只读 capability。未来写操作、审批或外部副作用必须通过独立 ADR 和公共契约评审定义业务幂等键/outbox/补偿，本文不预设。

`checkpoint(handle, checkpoint, expectedRowVersion)` 使用期望 row version 和递增 `checkpointSequence` CAS。相同 sequence/hash 的已提交 checkpoint 可幂等确认；相同 sequence 不同 hash、sequence 回退或跳号均为安全冲突。Checkpoint 只有确认提交后才能进入 Core；确认未提交时保持 PROCESSING 交给 recovery，commit 结果未知时必须重读且本次 Invocation 永不进入 Core。

`executeAndFinalize(handle, result, cancellation)` 协调 checkpoint、Core 和终结事务；`finalizeClarification/finalizePlanningFailure/finalizeCancelled` 处理不进入 Core 的分支。所有终结都只允许从 PROCESSING 经 CAS 进入一个终态。CAS 输家丢弃本地候选并重读权威原子单元；终结确认回滚时保持 PROCESSING，commit 结果未知时重读，不在内存中伪称成功或失败。

成功终结事务按一个本地原子单元提交：已过滤 `agent_invocation_result`、已批准且满足 P1_V2/03 加密/TTL/清理约束的 Context writes、Invocation `COMPLETED/SUCCESS` CAS、关联 Turn 成功 CAS。Clarification 只提交 Invocation `COMPLETED/CLARIFY` 与 Turn 成功，不写业务结果或 Context；failure/cancellation 只提交安全错误、Invocation `FAILED/CANCELLED` 与 Turn 对应终态，不写业务结果或可继承 Context。

恢复任务只扫描超过 absolute deadline 或恢复阈值的无主 PROCESSING CHAT Invocation，并在同一 Agent DB 本地事务中 CAS 原子终结 Invocation 与关联 Turn 为 FAILED 或 CANCELLED。Recovery 不恢复 finalization、不补写 SUCCESS/Context/业务结果、不重新执行 Planning/Handler/Adapter；事务未提交时两者继续保持原权威状态。当前阶段不引入 Task lease、Attempt 或 worker 恢复协议。

`agent_invocation_record` 保存 invocation/correlation、CHAT/CONVERSATION scope、subject/owner refs、planning artifact digest、Registration/metadata/authorization/context snapshot 安全引用或版本、checkpoint sequence/hash、状态、安全失败字段、timestamps 和 row version；不保存 Raw Plan、完整权限、Token、prompt、Context payload 或 provider 原始结果。详细字段见第 12 节。

## 11. 接口设计

本设计不改变外部 HTTP API。内部签名变更如下：

| 接口/类 | 方法 | 变更 |
|---|---|---|
| `InvocationHandle` | `forChat(...)` | 新增唯一当前 factory；删除通用 public `create` 或收为 package-private |
| `ExecutablePlanningResult` | `artifactIdentity()` | 新增逻辑 identity 访问器 |
| `PlanningCheckpoint` | `from(handle,result)` | 加入 artifact binding digest |
| `ExecutionCommand` | 构造器 | 验证逻辑 identity，不验证引用相等 |
| `InvocationLifecyclePort` | `start(StartInvocationCommand)` | 原子创建 Turn + Invocation(PROCESSING)；提交后返回唯一 `InvocationHandle` |
| `ExecutionLifecycleService` | `executeAndFinalize(handle,result,cancellation)` | 先 checkpoint，确认提交后调用 Core，再按 outcome 进入唯一终结事务 |
| `ExecutionLifecycleService` | `finalizeClarification/finalizePlanningFailure/finalizeCancelled` | 不进入 Core；提交对应安全终态 |
| `CapabilityRegistration` | `validateRaw(rawPlan,validationContext)` / `executeValidated(validatedPlanHandle,executionContext)` / `validateOutput(output)` | Registration 内完成唯一受控类型桥；Validated Plan Handle 不可由调用方伪造，Handler 仅接收 Validated Plan + Execution Context |
| `InvocationRecoveryService` | `recoverExpiredProcessing(now,batchSize)` | 在同一事务/CAS 中把 Invocation 与 Turn 原子终结为 FAILED/CANCELLED；不恢复执行 |

## 12. 数据设计

### 12.1 `agent_invocation_record`

目标表继续保持 `conversation_id`/`turn_id` 非空；下表是本次原子迁移后的完整 L2 字段基线，未列字段不得由实现临时扩展为第二事实源。

| 字段 | 类型/空值 | 写入时点 | 语义与约束 |
|---|---|---|---|
| `id` | `VARCHAR(64) NOT NULL` | Start | invocationId，主键 |
| `invocation_type` | `VARCHAR(32) NOT NULL` | Start | 当前固定 `CHAT` |
| `origin_type` | `VARCHAR(32) NOT NULL` | Start | 当前固定 `CHAT` |
| `conversation_id` / `turn_id` | `VARCHAR(64) NOT NULL` | Start | 当前 CHAT origin；`turn_id` 唯一并外键关联 `agent_turn` |
| `subject_type` / `subject_id` | `VARCHAR(32/128) NOT NULL` | Start | 稳定 Execution Subject 引用，不保存 JWT |
| `owner_type` / `owner_id` | `VARCHAR(32/128) NOT NULL` | Start | Context/结果 owner 引用 |
| `scope_type` / `scope_id` | `VARCHAR(32/128) NOT NULL` | Start | 当前固定 `CONVERSATION` 及 conversationId |
| `agent_id` / `profile_version` | `VARCHAR(128) NOT NULL` | Start | 本次 CHAT 使用的 Agent Profile 精确引用 |
| `request_correlation_id` | `VARCHAR(64) NOT NULL` | Start | 服务端生成的全链关联标识，唯一但不是客户端重放幂等键 |
| `state` | `VARCHAR(32) NOT NULL` | Start/终结 | `PROCESSING/COMPLETED/FAILED/CANCELLED` |
| `response_type` | `VARCHAR(32) NULL` | 终结 | `SUCCESS/CLARIFY/FAILURE/CANCELLED`；PROCESSING 时为空 |
| `capability_id` / `plan_kind` | `VARCHAR(128/32) NULL` | Checkpoint | Planning 选择结果；checkpoint 前为空 |
| `registration_identity` | `VARCHAR(256) NULL` | Checkpoint | 同一 Resolved Registration 的安全身份引用 |
| `authorization_snapshot_ref` | `VARCHAR(256) NULL` | Checkpoint | 版本化安全引用，包含已冻结 Effective Capability Resource Limits 的可校验绑定，不保存权限正文 |
| `context_snapshot_set_digest` | `VARCHAR(128) NULL` | Checkpoint | 已消费 Context Snapshot 集合的 canonical digest；空集合也使用固定 digest |
| `metadata_version` | `VARCHAR(128) NULL` | Checkpoint | 本次 Planning 使用的 metadata/Catalog 版本引用 |
| `planning_artifact_binding_digest` | `VARCHAR(128) NULL` | Checkpoint | PAI-1 binding digest，审计和防替换用途，不用于恢复执行 |
| `checkpoint_json` | `JSON NULL` | Checkpoint | 只含安全引用、Route/Plan operation metadata 与 effective deadline，不含 Raw Plan/Context/权限正文 |
| `checkpoint_hash` | `VARCHAR(128) NULL` | Checkpoint | checkpoint canonical 内容 SHA-256 |
| `checkpoint_sequence` | `BIGINT NOT NULL DEFAULT 0` | Checkpoint | Start 为 0；首次且当前唯一 Planning checkpoint 为 1，禁止跳号/回退 |
| `error_code` / `safe_message` / `diagnostic_id` | `VARCHAR(64) NULL` / `TEXT NULL` / `VARCHAR(128) NULL` | 终结 | 只保存安全失败信息；内部异常和下游原文不得落表 |
| `deadline_at` / `created_at` | `DATETIME(3) NOT NULL` | Start | absolute deadline 与创建时间 |
| `checkpointed_at` / `completed_at` | `DATETIME(3) NULL` | Checkpoint/终结 | 权威提交时间 |
| `row_version` | `BIGINT NOT NULL DEFAULT 0` | 每次 CAS | 乐观锁版本，只增不减 |

索引保持最小集合：`UNIQUE(turn_id)`、`UNIQUE(request_correlation_id)`、`INDEX(state,deadline_at)`、`INDEX(subject_id,created_at)`；当前容量下不为 digest、capabilityId 或 responseType 建索引。CHECK 至少包括：

```sql
CHECK (invocation_type = 'CHAT' AND origin_type = 'CHAT'
       AND scope_type = 'CONVERSATION'),
CHECK ((state = 'PROCESSING' AND response_type IS NULL AND completed_at IS NULL)
    OR (state <> 'PROCESSING' AND response_type IS NOT NULL AND completed_at IS NOT NULL)),
CHECK ((checkpoint_sequence = 0 AND checkpoint_hash IS NULL
        AND planning_artifact_binding_digest IS NULL)
    OR (checkpoint_sequence = 1 AND checkpoint_hash IS NOT NULL
        AND planning_artifact_binding_digest IS NOT NULL))
```

`checkpoint_json` 增加 `planningArtifactBindingDigest`；`checkpoint_hash` 随 canonical 内容变化。系统未投产，不提供旧 checkpoint 兼容读取。

### 12.2 `agent_invocation_result` 与 Context write

`agent_invocation_result` 只在 `COMPLETED/SUCCESS` 终结事务中插入一行，字段固定为 `id`、唯一 `invocation_id`、`output_contract_schema`、`output_contract_version`、过滤后的 `payload_json`、`safe_message`、`safe_summary`、`created_at`。CLARIFY/FAILED/CANCELLED 不创建结果行。`payload_json` 必须已通过 output ContractRef、同一 limits、字段授权和 mask 校验；表中不保存 raw Handler/provider output。

Context 表结构、加密和 TTL 由 P1_V2/03 唯一定义；本文只要求成功终结事务通过 Context 持久化边界提交已批准 candidate，并与 result/Invocation/Turn CAS 同一事务。Context candidate 校验失败或写入失败时整个成功终结事务回滚。

## 13. 状态流转设计

Invocation 只有以下持久化流转：

```text
[*] → PROCESSING                 Start 事务提交
PROCESSING → COMPLETED/SUCCESS   结果 + Context + Invocation + Turn 原子提交
PROCESSING → COMPLETED/CLARIFY   Clarification + Invocation + Turn 原子提交
PROCESSING → FAILED              safe failure + Invocation + Turn 原子提交
PROCESSING → CANCELLED           cancel/deadline + Invocation + Turn 原子提交
```

Checkpoint 只补充 PROCESSING 的不可变 Planning facts，不增加状态。禁止终态回到 PROCESSING、终态互转或同一 invocationId 并发执行多个 Handler。非法 scope/origin 在 Start 前拒绝；Start 已提交后的 artifact/authorization/context/binding/validation 错误必须经 Lifecycle 尝试终结 FAILED。只有 CAS/事务确认提交后才可声称终态；确认未提交或 commit unknown 不得在内存中伪造状态。

## 14. 幂等、事务与一致性设计

- Start 保证 Turn + Invocation 原子创建和 invocationId/request correlation 唯一，但不宣称当前 HTTP 请求具备客户端重放幂等；网络重试是新 Invocation。
- Checkpoint 同值重入同时比较 artifact binding digest。
- 不同 digest 的重复 checkpoint 是安全冲突。
- Checkpoint/终结确认未提交时保持 PROCESSING；commit unknown 必须重读权威原子单元，且不得重执行 Core/Handler/Adapter。
- 成功 finalization 在同一 Agent DB 本地事务中提交结果、Context、Invocation 和 Turn；失败/取消/recovery 在同一事务中提交 Invocation 与 Turn，禁止半终结。
- CAS 输家服从权威已提交终态并丢弃候选；只读业务已执行但终结失败时不补写成功。
- 删除 TASK 类型与 Context codec 必须同一发布单元完成。

## 15. 权限、风控与审计设计

Planning Artifact identity 只保存安全引用/digest，不保存权限正文。日志只记录 invocationId、registrationIdentity、bindingDigest 前缀和 diagnosticId；digest 不作为授权结论，Core 仍执行当前权限复检。safe message 必须由已评审模板/typed failure 产生。

## 16. 性能与容量设计

每次 Planning 计算一次 PAI-1 SHA-256，checkpoint/Core 可复算，输入为小型安全引用。不得缓存 artifact identity 跨 Invocation。Recovery 使用 `(state, deadline_at)` 有界分页和稳定主键顺序扫描，每批 `batchSize` 必须配置上限，逐条或小批 CAS，禁止长事务锁住所有 PROCESSING 行；不增加 digest 索引。

## 17. 兼容性与扩展性设计

系统未投产，删除 TASK 类型是破坏性目标切换。future Multi-Agent 若新增 RunScope：

1. 先完成 Multi-Agent L1；
2. 扩展 sealed union 和 Handle factory；
3. 新增 Task persistence shape；
4. 定义 artifact identity 在 Attempt 中的逻辑身份；
5. 不修改 Planning/Execution 主算法。

## 18. 日志、监控与告警

增加 `planning_artifact_identity_mismatch_total`、`unsupported_invocation_scope_total`、`invocation_start_total{result}`、`invocation_checkpoint_total{result}`、`invocation_finalization_total{result,responseType}`、`invocation_recovery_total{terminal}` 与各阶段耗时。`result` 使用低基数枚举（committed/cas_lost/unknown/failed）；标签只使用 stage/type/result，不使用 userId、scopeId、correlationId 或 digest 全值。PROCESSING 超过恢复阈值数量和 recovery 连续失败必须告警。

## 19. 实现落点清单

### 19.1 Java 实现落点

| 序号 | 路径 | 类名 | 方法名 | 入参类型 | 返回类型 | 动作 | 说明 |
|---:|---|---|---|---|---|---|---|
| 1 | `agent-service/src/main/java/com/dylan/agent/invocation/model/RunScope.java` | `RunScope` | 全部 | — | — | 删除 | 当前不实现 future Multi-Agent subtype |
| 2 | `agent-service/src/main/java/com/dylan/agent/invocation/model/TaskInvocationOrigin.java` | `TaskInvocationOrigin` | 全部 | — | — | 删除 | 当前不固化 run/task/attempt |
| 3 | `agent-service/src/main/java/com/dylan/agent/invocation/model/InvocationScope.java` | `InvocationScope` | permits | — | — | 修改 | 仅 permits ConversationScope |
| 4 | `agent-service/src/main/java/com/dylan/agent/invocation/model/InvocationOrigin.java` | `InvocationOrigin` | permits | — | — | 修改 | 仅 permits ChatInvocationOrigin |
| 5 | `agent-service/src/main/java/com/dylan/agent/invocation/model/InvocationType.java` | `InvocationType` | enum | — | — | 修改/删除 | 只保留 CHAT；若无必要则移除字段 |
| 6 | `agent-service/src/main/java/com/dylan/agent/invocation/model/InvocationHandle.java` | `InvocationHandle` | `forChat(...)` | 见 10.2 | `InvocationHandle` | 修改 | 唯一 CHAT factory |
| 7 | `agent-service/src/main/java/com/dylan/agent/planning/model/PlanningArtifactIdentity.java` | `PlanningArtifactIdentity` | record accessors | — | `PlanningArtifactIdentity` | 新增 | 内部逻辑 identity；只由 canonicalizer 生产 |
| 8 | `agent-service/src/main/java/com/dylan/agent/planning/model/PlanningArtifactCanonicalizer.java` | `PlanningArtifactCanonicalizer` | `identify(...)` | `InvocationHandle, PlanningArtifactComponents` | `PlanningArtifactIdentity` | 新增 | PAI-1 唯一生产入口 |
| 9 | `agent-service/src/main/java/com/dylan/agent/planning/model/ExecutablePlanningResult.java` | `ExecutablePlanningResult` | `artifactIdentity()` | 无 | `PlanningArtifactIdentity` | 修改 | 冻结 identity |
| 10 | `agent-service/src/main/java/com/dylan/agent/kernel/core/ExecutionCommand.java` | `ExecutionCommand` | 构造器 | `InvocationHandle, ExecutablePlanningResult, CancellationToken` | — | 修改 | 校验逻辑 identity |
| 11 | `agent-service/src/main/java/com/dylan/agent/kernel/core/ExecutionCore.java` | `ExecutionCore` | `validatePlanningArtifactIdentity` | `ExecutionCommand` | `void` | 修改 | 替代引用语义 |
| 12 | `agent-service/src/main/java/com/dylan/agent/lifecycle/model/PlanningCheckpoint.java` | `PlanningCheckpoint` | `from` | `InvocationHandle, ExecutablePlanningResult` | `PlanningCheckpoint` | 修改 | 保存 binding digest |
| 13 | `agent-service/src/main/java/com/dylan/agent/metadata/context/internal/ContextBindingSupport.java` | `ContextBindingSupport` | `scopeType/scope` | `InvocationScope` / strings | string/scope | 修改 | 删除 RUN 分支 |
| 14 | `agent-service/src/main/java/com/dylan/agent/lifecycle/StartTxService.java` | `StartTxService` | `start/createOrVerify` | `StartInvocationCommand` 或等价 CHAT command | `InvocationHandle` | 修改 | 原子创建 Turn/Invocation；只在提交后返回 Handle |
| 15 | `agent-service/src/main/java/com/dylan/agent/lifecycle/ExecutionLifecycleService.java` | `ExecutionLifecycleService` | `executeAndFinalize` 及三个 pre-Core finalize 方法 | 见第 11 节 | `FinalizedInvocationResult` 或 typed safe error | 修改 | Lifecycle 唯一协调 checkpoint/Core/finalization |
| 16 | `agent-service/src/main/java/com/dylan/agent/lifecycle/FinalizationTxService.java` | `FinalizationTxService` | `commitSuccess/commitClarification/commit*Failure/commit*Cancelled` | typed outcome | `FinalizedInvocationResult` | 修改 | 明确各终态原子参与者与 commit-unknown 重读 |
| 17 | `agent-service/src/main/java/com/dylan/agent/lifecycle/InvocationRecoveryService.java` | `InvocationRecoveryService` | `recoverExpiredProcessing` | `Instant, int` | `int` | 修改 | 仅原子 FAILED/CANCELLED，不恢复 finalization |
| 18 | `agent-service/src/main/java/com/dylan/agent/persistence/mapper/AgentInvocationRecordMapper.java` | `AgentInvocationRecordMapper` | `insert/checkpoint/finalize/findAtomicUnit` | entity/CAS 参数 | affected row/record | 修改 | 覆盖 Planning/checkpoint sequence/hash、rowVersion 与权威重读 |
| 19 | `agent-service/src/main/java/com/dylan/agent/kernel/registration/CapabilityRegistration.java` | `CapabilityRegistration` | `validateRaw/executeValidated/validateOutput` | Raw Plan/Validated Plan Handle + 受控 context | typed handle/candidate/void | 修改 | Validator→Validated Plan→Handler 的唯一桥 |

### 19.2 Python 实现落点

无。Planning Artifact 和 Invocation Scope 是 Java 内部契约，不生成 Python model。

### 19.3 脚本、SQL 与配置落点

| 序号 | 路径 | 动作 | 效果 |
|---:|---|---|---|
| 1 | `agent-service/src/main/resources/db/agent-p0.sql` | 修改 | 按第 12 节增加 Planning/checkpoint 字段、sequence、rowVersion 和 CHECK；当前只允许 CHAT/CONVERSATION |

### 19.4 测试落点

| 序号 | 路径 | 测试类 | 测试方法/用例 | 动作 |
|---:|---|---|---|---|
| 1 | `agent-service/src/test/java/com/dylan/agent/invocation/model/InvocationModelTest.java` | `InvocationModelTest` | `createsChatOnlyHandle`、`hasNoTaskOrRunSubtype` | 修改 |
| 2 | `agent-service/src/test/java/com/dylan/agent/planning/model/ExecutablePlanningResultTest.java` | 同名 | `buildsStableLogicalArtifactIdentity`、`changesDigestWhenBindingChanges` | 修改 |
| 3 | `agent-service/src/test/java/com/dylan/agent/kernel/core/ExecutionCoreTest.java` | 同名 | `rejectsArtifactIdentityMismatch`、`doesNotDependOnObjectIdentity` | 修改 |
| 4 | `agent-service/src/test/java/com/dylan/agent/lifecycle/model/PlanningCheckpointTest.java` | 同名 | `checkpointBindsPlanningArtifactDigest` | 修改 |
| 5 | `agent-service/src/test/java/com/dylan/agent/metadata/context/internal/ContextBindingSupportTest.java` | 同名 | `rejectsRunScopeEncoding` | 新增/修改 |
| 6 | `agent-service/src/test/java/com/dylan/agent/architecture/SingleAgentSeamArchitectureTest.java` | 同名 | `currentBuildContainsNoTaskRuntimeTypes` | 新增 |
| 7 | `agent-service/src/test/java/com/dylan/agent/lifecycle/StartTxServiceTest.java` | 同名 | Turn/Invocation 原子提交、失败整体回滚、提交前不返回 Handle | 修改 |
| 8 | `agent-service/src/test/java/com/dylan/agent/lifecycle/ExecutionLifecycleServiceTest.java` | 同名 | checkpoint 确认提交后才进 Core；rollback/unknown/CAS loser 不进 Core | 修改 |
| 9 | `agent-service/src/test/java/com/dylan/agent/lifecycle/FinalizationTxServiceTest.java` | 同名 | SUCCESS 四方原子提交、其他终态不写 result/context、commit unknown 权威重读 | 修改 |
| 10 | `agent-service/src/test/java/com/dylan/agent/lifecycle/InvocationRecoveryServiceTest.java` | 同名 | Invocation/Turn 同事务失败或取消、不恢复执行、不补写成功 | 修改 |
| 11 | `agent-service/src/test/java/com/dylan/agent/lifecycle/InvocationSchemaTest.java` | 同名 | 字段、索引、CHECK、外键和非法状态组合 | 修改 |
| 12 | `agent-service/src/test/java/com/dylan/agent/kernel/registration/CapabilityRegistrationTest.java` | 同名 | Handler 只能接收 Validator 构造的 Validated Plan，Core 无 Registry 二次查询 | 修改 |

## 20. 测试设计

- 单元：canonical digest 稳定、字段变化必变、集合顺序不影响。
- 负向：伪造 correlation/registration/snapshot/digest 被拒绝。
- 架构：main source 不存在 `RunScope`、`TaskInvocationOrigin`、`InvocationType.TASK`。
- SQL：非法 `scope_type='RUN'`/`invocation_type='TASK'` 插入失败。
- 并发：同一 invocationId 只允许一个 PROCESSING 记录和一条 Handler 执行链；当前 HTTP 重试创建新 Invocation 的语义有显式测试/说明。
- 一致性：checkpoint/finalization 确认回滚、commit unknown、CAS loser 均按第 10.8/14 节处理；任何路径不伪造终态。
- 安全：Context currentness 变化时不重新加载、不调用 Validator；limits 缺失/错配/扩大时 fail closed；Handler 只接收 Validated Plan + Execution Context。
- 恢复：超时 PROCESSING 只原子终结 Invocation/Turn 为 FAILED/CANCELLED，不调用 Planning/Core/Handler/Adapter、不插入结果/Context。
- 回归：CHAT Start→Planning→checkpoint→Core→finalization 全链通过。

## 21. 风险与待确认事项

| 序号 | 类型 | 内容 | 影响 | 建议处理方式 | 是否阻塞 |
|---:|---|---|---|---|---:|
| 1 | 编译影响 | 删除 subtype 会影响 tests/imports | 需要同步修改引用 | P1_V2/06 原子清单覆盖 | 否 |
| 2 | digest 实现 | PAI-1 canonical form 未来增加语义字段 | 若不升级版本会产生不兼容摘要 | 按 P1_V2/06 显式升级 format version | 否 |
| 3 | 数据 | 尚未投产但本地可能存在 RUN 测试数据 | 测试库重建 | 使用目标 DDL 重建，不写兼容迁移 | 否 |
| 4 | 重试语义 | 当前 HTTP 契约无客户端幂等键，网络重试会创建新 Invocation | 只读调用可能重复消耗预算；未来写能力会有重复副作用风险 | 当前明确只读边界；写操作实施前独立 ADR + 公共契约评审 | 否；当前不扩展 P1_V2/01 |
| 5 | 存储 | MySQL 版本或测试数据库对 JSON/CHECK 的执行差异 | 约束可能只在测试或某环境生效 | 构建门禁执行真实目标数据库 schema 测试，并保留应用层同义校验 | 否 |

## 22. 评审记录

| 轮次 | 日期 | 评审结论 | 发现问题数 | 修正问题数 | 遗留问题 | 说明 |
|---:|---|---|---:|---:|---|---|
| 1 | 2026-07-13 | 有条件通过 | 3 | 2 | 1 | 已关闭提前 TASK 类型和 JVM identity 设计问题；canonical serializer 落点待迁移门禁复核 |
| 2 | 2026-07-13 | 通过 | 2 | 2 | 0 | 统一 canonical encoding，消除 identity 构造环；无文档级 Blocker/Major |
| 3 | 2026-07-13 | In Review | 2 | 2 | 0 | 合并 Registration/Core/Lifecycle/Persistence，修正编号与空章节；等待全集状态确认 |
| 4 | 2026-07-13 | 需修正 | 8 | 8 | 0 | cross-layer 评审发现 Core/Lifecycle 顺序、Definition/Handler 边界、limits 冻结点、开始/恢复/数据契约问题，均已修正 |
| 5 | 2026-07-13 | 通过 | 1 | 1 | 0 | 复核发现拟议客户端 correlation 幂等会越界修改 P1_V2/01 公共契约，已收回为服务端唯一关联标识与原子 Start；终审无 S0/S1 遗留 |

## 23. 实施对齐检查

| 检查项 | 设计要求 | 当前实现位置 | 是否满足 | 说明 |
|---|---|---|---|---|
| 当前 scope | ConversationScope only | invocation model | 是 | `RunScope` 已从 main source 删除 |
| 当前 origin | Chat origin only | invocation model | 是 | `TaskInvocationOrigin` 已从 main source 删除 |
| artifact identity | 逻辑 digest | Planning artifact canonicalizer / ExecutablePlanningResult | 是 | identity-free components 生成唯一逻辑 digest |
| checkpoint | 绑定 artifact digest | PlanningCheckpoint | 是 | checkpoint 与 artifact identity 已绑定 |
| Context codec | 只解析 CONVERSATION | ContextBindingSupport | 是 | 当前 concrete scope 仅为 CONVERSATION |

## 24. 任务完成摘要

| 项目 | 内容 |
|---|---|
| 目标文档 | 本文 |
| 文档状态 | Implemented |
| 是否可作为实现依据 | 是 |
| 评审轮次 | 本次 3 轮；历史记录与本次记录合计见第 22 节 |
| 主要修改内容 | CHAT-only Invocation、逻辑 Planning Artifact identity、Lifecycle→checkpoint→Core→finalization 权威主链、原子开始、完整持久化与恢复契约 |
| 是否已追加修改历史 | 是 |
| 是否已补充实现落点清单 | 是 |
| 是否存在阻塞问题 | 否；当前实现已通过 P1_V2/06 迁移门禁验证 |
| 是否存在遗留风险 | 是；生产迁移、format version 演进和真实数据清理仍需发布前验证 |
| 是否需要用户进一步授权 | 是；仅生产迁移、生产启用和发布需要独立授权 |
| 参数输入方式 | 自然语言授权 |
| 建议下一步 | 本设计继续作为 P2_V3 的稳定 P1 输入；生产迁移和发布按 P1_V2/06、P2_V3/07 独立执行 |
