# 元数据、授权、Context 与 Result Security L2 实施详细设计 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档状态 | Implemented |
| 当前版本 | v2.0 |
| 创建/最后更新日期 | 2026-07-14 |
| 适用代码基线 | `816e2c855574da5326379128bfb3e230241d2fe3` |
| 设计层级 | L2 实施详细设计 |
| 适用阶段 | P1_V2 单 Agent 内核收敛 |
| 文档路径 | `docs/design/P1_V2/03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md` |
| 权威范围 | Profile、Policy、两阶段授权、Context 安全、结果投影、密钥管理、分页继承与安全拒绝 |
| 前置阅读 | L0/L1、P1_V2/00、P1_V2/01、P1_V2/02 |
| 历史来源 | P1/D02_03、统一密钥、值级 Mask、多轮分页与权限拒绝四份设计；仅作来源留档，不再是实施前置 |

## 2. 修订历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | 将四份 P1 历史设计收敛为独立基线 | 统一安全模型、接口、数据、配置和验证门禁 |
| 2 | 2026-07-13 | 5～20、22～24 | cross-layer 评审发现 Context 时序/状态、授权复检、Mask 契约、CAS、Result Security、secret 引用和实现落点与 L0/L1 或 Java 权威类型不一致 | 重排 Planning/Execution 安全链，删除 Context 平行状态机和当前 Invocation 内重规划，冻结类型/接口/DDL/原子 CAS/密钥引用与验证清单 |
| 3 | 2026-07-13 | 第1～2、23～24节 | P1_V2/P2_V3全集终检需统一代码基线和过程状态 | 对齐统一代码基线，标记全集评审完成并保留 Approved/M0 实施边界；不新增评审轮次，不改变已通过设计结论 |
| 4 | 2026-07-14 | 第1～3、5～11、15、18～24节 | 用户授权修订；P2_V3/06 实施发现 `ExecutionScope` 缺少 Provider 外部处理所需的 classification/purpose 权威证据，无法安全实现 shared outbound decision | 新增 capability-neutral `SecurityClassificationRef`、`ExternalProcessingAuthorizationEvidence` 与 field rule；冻结 Policy/User Permission 求交、Snapshot/Execution 单调收紧、canonical digest、审计、实现和测试落点，并将状态更新为 Implementing |
| 5 | 2026-07-14 | 第1～3、10、19、23～24节 | 授权后实现、测试与评审—修正循环完成 | 完成 external-processing Policy/Permission evidence、capability scope 冻结收窄、Execution recheck、canonical digest 与失败路径验证；状态更新为 Implemented |

## 3. 文档状态说明

本文处于 **Implemented**。用户已授权按 P1_V2/P2_V3 实施代码、测试、配置、运行时契约和数据库迁移，并在本次阻断恢复中明确授权修订本文；本次 capability-neutral external-processing 授权证据已完成实现与验证。仍禁止生产访问、生产 Provider 启用、commit、push、分支和 PR。L0/L1 保持只读，不因本次外部处理授权证据扩展而修改。

## 4. 背景与目标

建立一个由 Java 内核控制的安全闭环：元数据决定可见能力，两阶段授权冻结可执行范围，Context 只保存受保护的最小状态，Result Security 在离开内核前做最后投影。统一密钥、值级 Mask、分页继承和安全错误语义属于该闭环，不再作为分散补丁维护。

## 5. 设计范围

### 5.1 范围内

- Agent Profile、Policy、Permission、当前 CHAT 中性的 Delegation Constraint seam、Capability Catalog。
- Planning/Execution 两阶段授权及 currentness 校验。
- Context envelope、版本迁移、加密、CAS、TTL、finalization、清理。
- Query、Query Preview、Aggregate、Document 结果字段级和值级安全投影。
- common-security 已有 secret material 边界与 Agent payload/JWT 用途隔离的引用、来源、轮换和脱敏；两种用途不得共享 key material。
- Query 多轮分页/排序 Context 的确定性继承与权限拒绝安全表达。
- capability-neutral Provider 外部处理授权证据：domain purpose、field classification、field Mask 与当前 Policy/Permission evidence 的不可变绑定。

### 5.2 范围外

- 多 Agent 的调度、委派执行和跨 Agent Context 共享。
- 业务域自身的 RBAC 数据建模；本设计只消费 `UserPermissionAuthorityPort`。
- KMS/Vault 厂商 SDK；通过 `SecretMaterialProvider` 预留外部实现。
- 文档候选 ACL 的领域规则，归 P2_V3/03 管理。
- Document Provider operation、Corpus、input projection、wire、activation 与 vendor transport，归 P2_V3/04～07 管理；本文不定义 Document 专用 policy factory。

## 6. 上级文档约束

| 约束 | 本文落实 |
|---|---|
| Java 是安全与执行真值源 | Runtime 仅接收已投影 schema/context，不计算权限 |
| 规划可见不等于执行授权 | Planning capture 与 Execution authorize 分离 |
| fail closed | 权威源失败、版本漂移、密钥缺失、投影器缺失均拒绝执行 |
| Context 是受保护状态 | typed payload、AEAD、版本迁移、CAS、TTL、终态清理 |
| 输出离开内核前再次裁剪 | Handler 原始结果必须经过 `ResultSecurityBoundary` |
| Multi-agent 只预留 | 共享接口保持主体/Owner/Invocation Scope 中立；当前只构造 CHAT、认证 Owner、ConversationScope 和中性 Delegation Constraint，不创建 RunScope/Task/委派存储空壳 |
| 外部处理必须显式授权 | Profile feature/Provider 配置/Safe candidate 均不能替代 Policy 与当前 User Permission；缺少 purpose、classification 或 current evidence 时必须在任何外发前 fail closed |

## 7. 关联文档与边界

| 文档 | 关系与边界 |
|---|---|
| P1_V2/01 | 提供 Context/Result/Runtime 公共契约及版本治理 |
| P1_V2/02 | 消费授权快照、Context snapshot 和安全投影完成一次 Invocation |
| P1_V2/04 | 提供 canonical domain/field/role metadata 与 adapter availability |
| P1_V2/05 | 提供 effective resource limits，不由安全模块重复计算 |
| P2_V3/03 | 细化 document candidate ACL；最终仍经过本文 Result Security 边界 |
| P2_V3/06 | 消费本文冻结在 `ExecutionScope` 的 `ExternalProcessingAuthorizationEvidence`，形成 Document purpose-specific outbound decision；不得读取 Policy/Permission 正文或另建授权事实源 |

## 8. 设计边界与约束

1. `PayloadJsonCodec` 只允许登记的 `CapabilityContextPayload` 与 `AgentResultPayload`，不得泛化为任意对象序列化器。
2. 权限字段、可排序字段、可返回字段均来自同一 canonical metadata 投影。
3. 前一轮 Context 只能缩小当前有效范围，不能恢复当前用户已失去的权限。
4. 禁止在日志、异常、Actuator、配置导出或对象 `toString()` 中输出密钥值、Token、原始敏感字段。
5. `FIELD_FORBIDDEN` 不得帮助调用者枚举字段是否存在；外部响应统一为安全措辞，内部审计保留 reason code。
6. Profile 的 OPTIONAL/REQUIRED、07 activation ACTIVE、Provider endpoint/model 配置和 Safe candidate 只表达功能或运行状态，均不构成外部处理授权。
7. 外部处理 purpose 必须由 Policy 显式允许，并与当前 User Permission 已允许的 domain/field 求交；空集合、未知 classification、未知 operation type 或证据不可 current 均为 DENY。

## 9. 总体设计

```text
Before Route:
  Profile + Policy + Current User Permission + CHAT neutral Delegation
    → AuthorizationPlanningPort.capture → PlanningAuthorizationEvidence
    → Available Capability / Route safe projection

After valid RouteDecision + Resolved Registration:
  Registration Context declaration + same evidence
    → ContextPlanningPort.load → Context Snapshot → minimal Runtime Context View
    → freeze capability-scoped Authorization Snapshot
       including Effective Capability Resource Limits
    → Plan → ExecutablePlanningResult

Lifecycle checkpoint committed → Core:
  AuthorizationExecutionPort.recheck → same or narrower ExecutionScope/limits
  → Context currentness recheck only; never reload
  → Validator → Handler candidate
  → ResultSecurityBoundary(output ContractRef + scope + same limits)
  → approved Context candidate + secured result
  → Lifecycle finalization transaction
```

共享 secret material 入口为 JWT 和 payload codec 提供用途隔离的 key set；`JWT_HMAC` 与 `AGENT_PAYLOAD` 必须使用不同 keyId namespace 和不同密钥材料。密钥仅以 `purpose + keyId` 参与配置引用和受限审计，Secret bytes 不进入 metadata digest。

## 10. 详细功能设计

### 10.1 Profile 与 EffectiveProfile

当前 `AgentProfileDefinition` 冻结为：`AgentProfileVersionKey(agentId, profileVersion)`、`ProfileBehaviorAssetRef`、`allowedCapabilityIds`、`readableContextTypes`、`writableContextTypes`、`maxRiskLevel`、`maxExecutionMode`、Route/Plan 的 `PlanningBudgetLimits(maxTotalDuration,maxRepairAttempts)`，以及按 P1_V2/05 ContractRef 类型化的 `CapabilityResourceLimitContributions`。删除 `maxPageSize/maxResultRows/maxResultBytes` 等散字段；它们属于具体 capability resource contract。Profile 不保存 `policyRef`、enabled domain、Permission、Mask 正文、Capability Definition 或 Adapter 信息。`AgentProfileRegistry.getRequired(AgentProfileRef)` 返回精确不可变版本；`EffectiveProfileCalculator.calculate(definition, policySnapshot)` 只计算 Profile ∩ Policy，输出同结构的 `EffectiveProfile`（额外绑定 policyVersion/allowedDomains），不混入 availability 或 User Permission。交集为空是明确不可用，不降级成功。

### 10.2 Policy、Permission 与 Delegation

- `AgentPolicySnapshot` 当前包含 policyVersion、profile constraints、capability constraints、domain security constraints、PlanningBudget upper bound、按 ContractRef 类型化的 capability resource limit upper bounds、global Context TTL upper bound 和 emergency revocations；`BudgetLimits` 中的 page/result 散字段迁移到 typed contribution，且不创建 future delegation 配置或 Task budget 字段。
- `DomainSecurityConstraints` 在既有 filter/display/operator/function/Mask 约束之外，新增 domain 级 `Set<CapabilityOperationType> externalProcessingPurposes`。`FieldSecurityConstraint` 新增非空 `SecurityClassificationRef classification` 与 field 级 `Set<CapabilityOperationType> externalProcessingPurposes`；两个 purpose 集合都是闭合集，缺失或空集合表示禁止外部处理，不能按 feature、Provider 配置或 classification 名称推导默认 allow。
- `UserPermissionAuthorityPort.resolveCurrent(ExecutionSubjectRef subject, Instant absoluteDeadline)` 是用户权限唯一权威端口；不得把 JWT、本地角色或“上次允许”缓存作为替代事实源。若以后启用成功快照缓存，TTL 必须短于撤权目标窗口且紧急撤权仍绕过缓存；本次 P1_V2 不新增该缓存。
- 当前 CHAT 只使用代码内中性 `DelegationConstraintRef.CHAT_ALL` 参与统一公式，不保存委派状态、Repository 或外部配置，不创建子 Agent、不转移所有权。

`PlanningEffectiveScope` 是 EffectiveProfile ∩ current UserPermission ∩ `CHAT_ALL` 的不可变结果，字段固定为 allowedCapabilityIds、allowedDomains、`Map<CanonicalFieldRef,FieldAccess>`、`ExternalProcessingAuthorizationEvidence`、readable/writableContextTypes、maxRiskLevel、maxExecutionMode、PlanningBudgetLimits 和按 ContractRef 类型化但尚未 capability-scoped freeze 的 resource limit contributions。它不包含 availability、Adapter binding 或最终执行许可。

`SecurityClassificationRef(namespace,classificationId,version)` 是 capability-neutral、不可变、不可由调用方携带 digest 的内部引用；`canonicalDigest()` 按 `SCR-1`、三个 normalized nonblank 字段、UTF-8 length-prefixed、SHA-256 lowercase 计算。classificationId 只标识权威分类，不凭名称自动产生外发许可。

`ExternalProcessingAuthorizationEvidence` 由 Planning 授权边界本地构造：

~~~java
record ExternalProcessingAuthorizationEvidence(
    Map<String, Set<CapabilityOperationType>> domainPurposes,
    Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules,
    String policyEvidenceDigest,
    String permissionEvidenceDigest,
    String canonicalDigest) {}

record ExternalProcessingFieldRule(
    CanonicalFieldRef field,
    SecurityClassificationRef classification,
    MaskType maskType,
    Set<CapabilityOperationType> allowedPurposes) {}
~~~

`domainPurposes` 只包含 EffectiveProfile 与 current User Permission 同时允许的 domain，value 来自该 domain 的 Policy closed purpose 集；`fieldRules` 只包含 current User Permission 同时允许 filter/display 且 Policy field constraint 完整的 canonical field，purpose 是 domain purpose 与 field purpose 的交集，Mask 使用既有 `MaskType` 权威值。Policy field constraint 缺失、classification 缺失、permission 不允许字段或 purpose 交集为空时，不生成对应 field rule。query-only operation 仍必须命中 domain purpose，不能以空 field view 绕过授权。

`policyEvidenceDigest` 使用 `EPP-1` 绑定 exact policyVersion、按 domain/field/operation canonical 排序的 Policy purpose/classification/Mask 事实；`permissionEvidenceDigest` 使用 `EPM-1` 绑定 current permission evidence id/version 以及实际进入 evidence 的 domain/field 集；`canonicalDigest` 使用 `EPA-1` 绑定两个 evidence digest、ordered domain purpose 与 ordered field rules。三者都采用 UTF-8 length-prefixed、SHA-256 lowercase，不接受 caller-supplied digest，不跨 Invocation 缓存。

### 10.3 两阶段授权

| 阶段 | 接口 | 输入 | 输出 | 核心校验 |
|---|---|---|---|---|
| Planning | `AuthorizationPlanningPort.capture` | `PlanningSecurityRequest` | `PlanningAuthorizationEvidence` | 用户权限、Profile、Policy、domain/field/capability 可见性 |
| Planning | `assertCurrent` | evidence | `void` | 每次 Route/Plan 请求前及 freeze 前确认同一证据链仍有效；变化终止当前 Planning |
| Planning | `freezeCapabilityScope` | evidence、`CapabilityScopeSelection` | `AuthorizationSnapshot` | 选择不得超出 evidence；按 Definition ContractRef 冻结本次唯一 Effective Capability Resource Limits |
| Execution | `AuthorizationExecutionPort.recheck` | `AuthorizationSnapshot`、`InvocationHandle` | `ExecutionScope` | 主体/Owner/ConversationScope/correlation、精确版本、撤权、当前权限、resource ContractRef/digest；结果只能保持或收紧 |

执行阶段必须重新读取紧急撤权和权限权威源；不得信任 Runtime 回传的 scope、fields 或 budget。复检后的缩小范围由 Core 继续校验 Raw Plan/Validated Plan 是否仍可执行；不能满足时当前 Invocation fail closed，不在同一 Invocation 内自动重做 Route/Plan。

`CapabilityScopeSelection` 在合法 RouteDecision、Registration 解析和 Context load 后、调用 Plan Runtime 前构造，字段固定为 ResolvedRegistration、selectedDomain、ContextSnapshots、DomainMetadataEvidence 和 optional typed request narrowing。`freezeCapabilityScope` 使用该选择和同一 evidence 解析 Definition ContractRef，形成 AuthorizationSnapshot 后才组装 PlanRequest；Runtime Raw Plan 只能在冻结 limits 内进一步给出具体 page/size/evidence 等值，不能扩大 Snapshot。

`AuthorizationSnapshot` 必须是不可变内部 Java 类型，并完整绑定：snapshotId、invocationId/requestCorrelationId、Execution Subject、Owner、ConversationScope、精确 AgentProfileRef、policyVersion、permission evidence id/version、`CHAT_ALL` delegation reference、capability/domain/field/operator/function/Context read-write 范围、risk/execution mode、result filter/mask 引用、`ExternalProcessingAuthorizationEvidence`、DomainMetadataEvidence、Effective Capability Resource Limits 的 ContractRef/canonical digest/不可变值、capturedAt 和 absoluteDeadline。Snapshot 不保存 JWT、角色表达式、Policy/Permission 正文、Context payload、Adapter 凭据或最终执行许可；classification/purpose 只保存求交后的安全引用和 closed rule，不保存 Policy 表达式正文。

`ExecutionScope` 保存本次 recheck 后同一或更严格的范围、当前 permission/policy evidence、同一或可证明更严格的 limits、`ExternalProcessingAuthorizationEvidence`、`recheckedAt` 和剩余 deadline；不得使用 `maxResultRows/maxResultBytes` 等散字段替代 P1_V2/05 的权威 limits 类型。复检必须使用 Snapshot 绑定的精确 Profile/Policy 版本，重新读取 current User Permission，重新构造 external-processing permission evidence，并证明 domain purpose、field rule、classification、Mask 和 purpose set 均为 Snapshot 的 same-or-narrower 子集；classification identity/version 变化不是收紧，必须 fail closed。权威源不可用、版本撤销、主体/Owner/Scope/correlation 不一致或无法证明单调收紧时 fail closed。

`PlanningAuthorizationEvidence.evidenceDigest()`、Authorization Snapshot digest、limits digest 和 Context binding digest 均使用版本化 canonical form + SHA-256 lowercase hex。集合按稳定业务 key 排序，禁止 `Objects.hash/hashCode`、Java 序列化字节、Map 迭代顺序或对象地址参与安全绑定；digest 只证明完整性绑定，不替代当前授权复检。

### 10.4 Capability Catalog 与 Available Capability Snapshot

`CapabilityCatalog.available(PlanningAuthorizationEvidence evidence)` 按以下唯一公式计算，不允许 capability/domain 专用分支：

```text
Available Capability
  = Capability Registry Registration set
  ∩ Effective Profile / applicable Policy
  ∩ Current User Permission
  ∩ CHAT neutral Delegation Constraint
  ∩ current Domain/Adapter availability required by Domain Mode
```

每个 `AvailableCapability` 只包含 capabilityId、planKind、Domain Mode、Definition 内 Routing Descriptor 的安全投影、当前 allowedDomains、riskLevel、executionMode 和 registrationIdentity；删除 `maxTotalDuration/maxRepairAttempts/maxPageSize/maxResultRows/maxResultBytes` 散字段，资源限额在 capability 选定后由 P1_V2/05 按 ContractRef 冻结。Domain Mode 规则固定为：`NONE` 的 allowedDomains 为空且不要求 Adapter；`OPTIONAL` 即使无可用 Domain 仍可无 Domain 执行，但携带的非空 Domain 必须来自当前 allowedDomains；`REQUIRED` 没有可用 Domain/Adapter 时不进入 Snapshot。

`AvailableCapabilitySnapshot` 绑定 requestCorrelationId、authorizationEvidenceDigest、DomainMetadataEvidence、按 capabilityId 稳定排序的不可变 entries 和 createdAt。它是当前 PlanningCommand 的请求级投影，不是静态 enabled 配置、最终执行授权或 Registration 副本。Route 选择 Snapshot 外 capability/domain 时当前 Planning 失败，不静默换到另一 capability；选定后使用同一 Registration identity 进入 Context/Plan。

### 10.5 Context 契约与版本

`ContextRecordEntity` 是持久化映射，不是跨边界 DTO，字段固定为：`contextId`、`ContextRecordKey(owner, ConversationScope, contextType)`、`ContractRef`、`recordVersion`、`ProtectedPayload(ciphertext,keyId,nonce,algorithmVersion)`、`sourceCapabilityId`、`sourceInvocationId`、可选 `sourceDomain`、`readable`、`createdAt`、`updatedAt`、`expiresAt`。不持久化 authorization/metadata digest、权限正文或候选状态；这些证据只存在于本次请求的 Authorization/Context Snapshot。Payload 类型只来自 agent-api allowlist：`QueryCapabilityContextPayload`、`AggregateCapabilityContextPayload`、`DocumentCapabilityContextPayload`。

`ContextMigrationRegistry` 只执行显式 `(sourceContract,payloadType)->(targetContract,payloadType)` 迁移，不做猜测式路径搜索。Query 历史版本通过 `QueryContextPayloadV10ToV12Migrator`、`QueryContextPayloadV11ToV12Migrator` 补齐 totals/sorts 的安全缺省值。

`ContextSnapshot` 是请求内不可变明文对象，字段固定为 contextId、requestCorrelationId、ContextRecordKey、source capability/invocation/domain、stored/effective ContractRef、recordVersion、expiresAt、profile/policy/permission evidence refs、当前 `CHAT_ALL` ref、`ExpectedContextVersion` 和 typed payload。Snapshot 不是 Entity，不跨 Invocation 缓存或发送 Runtime。`RuntimeContextView` 只保留 Plan 契约声明的最小字段和 schema/version 语义，不含 Owner、write 权限、evidence、密钥或 source audit detail。

### 10.6 Context 读写算法

1. 合法 RouteDecision 且 Resolved Registration 确定后，Planning 调用 `ContextPlanningPort.load`，按 Registration read declaration 和 `ContextRecordKey` 读取记录并校验 owner、ConversationScope、readable、ContractRef/version 和 TTL；Route 前禁止读取 capability Context。
2. codec 使用 envelope AAD 解密；registry 将历史 payload 迁移到当前 contract。
3. `ContextBoundary` 根据同一 `PlanningAuthorizationEvidence` 形成不可变 `ContextSnapshot`；`toRuntimeView` 只生成 Plan 所需最小投影，不把 Snapshot/Envelope 发送给 Runtime。
4. Handler 只产生 `ContextWriteCandidate`，不得直接写库。
5. Core 基于同一 ExecutionScope/limits 校验 candidate 的 owner、ConversationScope、payload type、ContractRef、字段集合、source identity、expected version 与最严 TTL，形成 `ApprovedContextWrite`。
6. Lifecycle 仅在 SUCCESS finalization 本地事务内调用 `ContextFinalizationParticipant.persist(approvedWrites)`；participant 负责序列化、加密和 repository 原子 CAS。candidate 不预写库，不存在“提交/废弃候选”的 Context 状态。
7. repository 对 absent 使用普通 `INSERT` 并把 duplicate key 映射为 `CONTEXT_CONFLICT`；对 existing 使用单条 `UPDATE ... WHERE logical_key=? AND record_version=? AND readable=1`，affected rows 必须为 1。禁止先 SELECT 再无条件 upsert 冒充 CAS。
8. Core 在 Validator 前通过 `ContextExecutionPort.revalidateAll` 只复检已消费 Snapshot 的 correlation、Owner、Scope、ContractRef/schema、record version 与 TTL；变化时终止当前 Invocation，不加载另一份 Context。

```text
Effective Context Read Scope
  = Registration read declaration ∩ Planning Effective Scope
  ∩ Owner ∩ ConversationScope ∩ compatible ContractRef/version ∩ unexpired TTL

Effective Context Write Scope
  = Registration write declaration ∩ Effective Execution Scope
  ∩ Owner ∩ ConversationScope ∩ declared ContractRef/version
  ∩ Effective Capability Resource Limits / strictest TTL
```

任一适用层缺失、拒绝或无法确认均 fail closed。可选 Context 不存在时 Planning 显式使用空 View，并仍通过 `findByKey` 冻结写 baseline；必需 Context 缺失/不可读时不调用 Plan。

### 10.7 Query 多轮分页与排序继承

`QueryContextMode` 的 Java 权威枚举当前只有 `REPLACE/MERGE`。`REPLACE` 不读取上一轮：filters 必须来自当前 Plan 且非空，selectFields/sorts/page/size 缺省时使用当前 capability/domain 默认值，`removeFields` 非空即拒绝。`MERGE` 必须存在上一轮 Query Context：filters 由 `QueryMergeEngine` 按当前 changes + removeFields 合并；selectFields 为 null/空时继承；sorts 为 null 时继承、空列表时清除用户排序并恢复 domain 默认、非空时替换；page/size 未显式提供时继承上一轮。对于“下一页/上一页/最后一页”，Runtime 必须依据 Context View 显式给出 `previous.page±1` 或在 `totalExact=true` 时给出 `totalPages`，Java 不从自然语言意图自行递增。合并后的字段/operator/sorts/page/size 必须在 Validator 中再次经过当前 metadata、ExecutionScope 与 Effective Capability Resource Limits 校验。仅 SUCCESS 响应和新 Context 保存 `page,size,total,totalExact,totalPages,sorts`；`totalExact=false` 时 `totalPages` 必须为空且不得推断最终页。

### 10.8 Result Security

`ResultSecurityProjectorRegistry` 以 output `ContractRef` 精确选择唯一 projector；ContractRef 无法解析、projector 缺失/重复或 Java result type 不匹配时启动或执行 fail closed。`ResultSecurityPort.secure(Object candidate, ContractRef outputContract, ExecutionScope scope, EffectiveCapabilityResourceLimits limits)` 返回 `SecuredResult`，并验证传入 limits 与 Authorization Snapshot 绑定值相同或可证明更严格：

- Query/Preview：裁剪行字段、queryParameters.filters/selectFields/sorts，并对配置字段执行值级 Mask。
- Aggregate：裁剪 group/metric/orderBy 字段，禁止通过标签泄露不可读字段。
- Document：消费 P2_V3/03 产生的候选 ACL evidence，在统一边界复检 Owner/subject/field/citation 归属，安全裁剪 snippet 和 metadata；本文不复制文档 ACL 领域规则。
- 所有 projector 必须处理嵌套 Map/List；未知结构 fail closed，不原样透传。

值级 Mask 由 `ResultValueMaskingSupport` 按 ExecutionScope 中已解析的 `MaskType` 执行；Java 权威枚举当前只有 `NONE/ID_CARD/MOBILE/EMAIL/ADDRESS`，具体实现由 `FieldMaskerRegistry` 唯一注册。不得在文档、配置或 projector 自建 `FULL/PARTIAL/HASH` 平行枚举，也禁止 projector 直接读取散落配置。required 字段过滤后不满足 output ContractRef 时整体失败，不返回原始候选。

Generated Text Candidate 不是最终文本。Result Security 必须同时校验 output ContractRef 明确允许、evidence/citation reference 属于当前已授权候选、citation 完整、生成 operation metadata 合法、字段权限与 mask 已应用、输入/输出/证据数量不超过同一 limits；失败时按契约降级为安全模板/省略或整体失败，绝不原样透传自由文本。

### 10.9 安全拒绝语义

| 内部错误 | 外部语义 | HTTP/业务处理 |
|---|---|---|
| `FIELD_FORBIDDEN` / `FIELD_UNKNOWN` | “请求包含当前不可用字段，请调整条件” | 不透露字段是否存在 |
| `PERMISSION_AUTHORITY_UNAVAILABLE` | “权限校验暂不可用” | 可安全重试，不降级允许 |
| `AUTHORIZATION_STALE` | “授权状态已变化，请重新发起” | 当前 Invocation 终结失败；调用方可新建 Invocation，不在原 Invocation 重规划 |
| `CONTEXT_CONFLICT` | “上下文已更新，请重试” | 当前成功终结事务回滚，不覆盖写、不重执行 Handler；调用方可新建 Invocation |
| `SECRET_KEY_UNAVAILABLE` | 通用内部错误 | 告警，禁止输出 key/value |

### 10.10 统一密钥与多注入源

`SecretPurpose` 当前含 `JWT_HMAC`、`AGENT_PAYLOAD`；`SecretKeyRef(purpose,keyId)` 只描述用途和标识，不得携带 `configValue`、Secret bytes 或可打印值。source-specific binding 独立保存 env/config locator。`SecretMaterialProvider.requireSecret(ref)` 返回禁止 `toString` 暴露并可在使用后清零的 `SecretMaterial`；`CompositeSecretMaterialProvider` 当前只按受控 source order 选择 `ENVIRONMENT` 或仅 dev/test 可用的 `CONFIG`。未实现 provider 的 `EXTERNAL` enum/分支不在当前保留；未来必须把 enum、provider、失败语义和测试同一变更引入。相同 keyId 在不同 purpose 下不得解析为同一材料。

生产环境禁用配置文件明文 key。Agent payload 使用 AES-256-GCM、每次加密 96-bit CSPRNG nonce、128-bit tag；AAD canonical 绑定 purpose、contextId、logical key、ContractRef、target recordVersion 与 source invocation，任一变化解密失败。JWT 签发写 active `kid`，验签接受 active 与保留窗口内 previous keys；payload 加密写 active key id，解密按记录 key id 获取同 purpose 历史 key。轮换先部署“新 active + 旧 previous”，等待 Token/Context 各自最大 TTL 后再按 purpose 移除旧 key，不以 JWT TTL 推导 payload key 窗口。

### 10.11 配置与启动校验

配置事实源固定如下：

| 配置前缀/对象 | 唯一负责内容 | 禁止重复 |
|---|---|---|
| metadata bundle `AgentPolicySnapshot.globalContextTtlUpperBound` | Context 授权 TTL 上限，进入 Snapshot/ExecutionScope 单调收紧 | `AgentSecuritySettings` 再声明第二 TTL 上限 |
| `agent.context.cleanup-delay/cleanup-batch-size` | 纯运维清理节奏；batch size 取 1～1000 | 影响 Context 可读授权或延长 expiry |
| `common.security.secrets.source-order/allow-config-values/fail-fast` | secret 来源策略 | 各服务自建 source order |
| `common.security.secrets.jwt.*` | JWT active/previous key refs | Agent payload key 复用 |
| `common.security.secrets.agent-payload.*` | payload active/previous key refs | metadata bundle 再保存 active keyId |

`SecretProperties.KeyProperties` 可以保存 env locator；`.value` 只允许 dev/test 且必须由 sanitizer 处理，生产 `allow-config-values=false` 并禁止 `CONFIG` source。`SecretKeyRef` 本身不得复制 `.value`。`AgentMetadataPropertiesValidator` 校验 Profile/Policy/Context/Result Security 引用闭合；`SecretPropertiesValidator` 校验来源策略、purpose/keyId 唯一性、active/previous 闭合、Base64 和长度（payload 解码后恰为 32 bytes，JWT HMAC 不低于 32 bytes）；Actuator `env/configprops` 必须应用 `SecretSanitizingConfiguration`。任何 active key、projector、permission authority、context codec、ContractRef 或 mask registry 未装配均启动失败。

## 11. 接口设计

| 接口/类 | 方法签名 | 结果与约束 |
|---|---|---|
| `AgentProfileRegistry` | `getRequired(AgentProfileRef ref)` | `AgentProfileDefinition`；Invocation 开始后 ref 必须含精确版本，不解析 latest 替换 |
| `AgentPolicyConfiguration` | `requireVersion(String version)` / `current()` | 解析精确版本；current 只供新 Planning capture，不替换已绑定版本 |
| `UserPermissionAuthorityPort` | `resolveCurrent(ExecutionSubjectRef subject, Instant absoluteDeadline)` | 当前 `UserPermission` 或 typed authority failure；失败封闭 |
| `AuthorizationPlanningPort` | `capture(PlanningSecurityRequest request)` | `PlanningAuthorizationEvidence` |
| `AuthorizationPlanningPort` | `assertCurrent(PlanningAuthorizationEvidence evidence)` | Route/Plan/freeze 前 currentness 门禁，不混合新旧版本 |
| `AuthorizationPlanningPort` | `freezeCapabilityScope(evidence, CapabilityScopeSelection selection)` | capability-scoped `AuthorizationSnapshot`，内部冻结 P1_V2/05 limits |
| `AuthorizationExecutionPort` | `recheck(AuthorizationSnapshot snapshot, InvocationHandle handle)` | 同一或更严格 `ExecutionScope`；权威源/绑定不可确认则失败 |
| `ExternalProcessingAuthorizationEvidenceFactory` | `create(policyVersion,permission,allowedDomains,fieldAccess,domainSecurityConstraints)` | Planning/Execution 共用的纯函数；返回 capability-neutral purpose/classification evidence，无 I/O |
| `ExternalProcessingAuthorizationEvidence` | `allowsDomain(domain,purpose)` / `requireFieldRule(field,purpose)` / `canonicalDigest()` | 只读 closed evidence；missing/unknown 返回拒绝，不读取配置或 Provider 状态 |
| `CapabilityCatalog` | `available(PlanningAuthorizationEvidence evidence)` | 通用公式生成 `AvailableCapabilitySnapshot`；entries 按 capabilityId 稳定排序 |
| `ContextPlanningPort` | `load(ContextReadRequest request)` | `ContextSnapshot`；返回已迁移/已投影视图 |
| `ContextPlanningPort` | `toRuntimeView(snapshot,declaration,evidence)` | 最小 `RuntimeContextView`；不发送 Snapshot/Envelope |
| `ContextExecutionPort` | `revalidateAll(snapshots,handle,resolvedRegistration,executionScope)` | 只复检，不重新加载或持久化 |
| `ContextApprovalPort` | `approve(candidates,ContextApprovalRequest)` | `List<ApprovedContextWrite>`；绑定同一 scope/limits/TTL |
| `ContextRepository` | `findCurrent/findByKey/insertApproved/updateApprovedCas/markConversationUnreadable/deleteExpired` | insert/update 使用数据库原子条件；禁止 SELECT + 无条件 upsert |
| `ContextFinalizationParticipant` | `persist(List<ApprovedContextWrite> writes)` | `MANDATORY` 加入 Lifecycle SUCCESS 事务；其他终态不调用 |
| `ProtectedPayloadCodec` | `encrypt/decrypt(PayloadProtectionContext, ...)` | AEAD，AAD 绑定 owner/type/version |
| `ResultSecurityPort` | `secure(candidate,outputContract,executionScope,effectiveLimits)` | `SecuredResult`；ContractRef/type/scope/mask/limits 统一校验 |
| `SecretMaterialProvider` | `requireSecret(SecretKeyRef(purpose,keyId))` | 不可日志化且用途隔离的 `SecretMaterial` |

## 12. 数据设计

### 12.1 `agent_context_record` 完整字段

| 字段 | 类型/空值 | 约束与语义 |
|---|---|---|
| `context_id` | `VARCHAR(128) NOT NULL` | 主键；每次成功写生成新安全 ID |
| `owner_type` / `owner_id` | `VARCHAR(32/128) NOT NULL` | `ContextOwnerRef`；当前为认证 Owner |
| `scope_type` / `scope_id` | `VARCHAR(32/128) NOT NULL` | 当前只允许 `CONVERSATION` 与 conversationId |
| `context_type` | `VARCHAR(64) NOT NULL` | Java `RuntimeContextType` 权威枚举 |
| `contract_schema` / `contract_version` | `VARCHAR(128/64) NOT NULL` | Java `ContractRef` |
| `record_version` | `BIGINT NOT NULL` | 初始 0，成功 CAS 后逐次 +1，不回退 |
| `protected_payload_json` | `JSON NOT NULL` | 仅含 Base64 ciphertext、keyId、nonce、algorithmVersion；不含明文/AAD/Secret |
| `source_capability_id` | `VARCHAR(128) NOT NULL` | 当前 Registration capabilityId |
| `source_invocation_id` | `VARCHAR(64) NOT NULL` | 产生该版本的成功 Invocation |
| `source_domain` | `VARCHAR(128) NULL` | Domain Mode `NONE` 时为空 |
| `readable` | `TINYINT(1) NOT NULL DEFAULT 1` | 单调清理标志；不是业务状态机，清理后置 0，不由普通 write 重新开放 |
| `expires_at` | `DATETIME(3) NOT NULL` | 当次最严 TTL 形成的绝对过期时间 |
| `created_at` / `updated_at` | `DATETIME(3) NOT NULL` | 逻辑记录首次创建/最新版本提交时间 |

唯一键为 `(owner_type,owner_id,scope_type,scope_id,context_type)`；索引为 `(expires_at,readable)` 和 `source_invocation_id`。CHECK 至少限制 `scope_type='CONVERSATION'`、`record_version>=0`、`readable IN (0,1)`。不保存 `status`、authorization digest、metadata digest、JWT、Raw/Validated Plan 或完整业务结果。

### 12.2 原子 CAS SQL 语义

- 期望不存在：`INSERT` 初始 `record_version=0`；唯一键冲突即 `CONTEXT_CONFLICT`，不得 `ON DUPLICATE KEY UPDATE`。
- 期望版本 `v`：单条 `UPDATE` 设置新 contextId/payload/source/expiry、`record_version=v+1`、`updated_at`，条件必须包含完整 logical key、`record_version=v`、`readable=1`；affected rows 不为 1 即冲突。
- Planning 即使不读取过期 payload，也必须通过 `findByKey` 得到写入 baseline version，避免过期行被误判为物理不存在；`findCurrent` 只返回 `readable=1 AND expires_at>now` 的可读记录。
- 同一 finalization 内按 contextType 稳定排序；同一 Invocation 对同一 contextType 最多一个 candidate。任何一条 CAS/加密失败使结果、全部 Context write、Invocation 和 Turn一起回滚。
- DDL 与 mapper 在 P1_V2/06 同一发布单元切换；系统未投产，不提供旧表双写或兼容 facade。

## 13. 状态流转设计

本文不建立 Context 持久状态机。`ContextWriteCandidate/ApprovedContextWrite` 只在内存中存在；SUCCESS finalization 提交后直接成为 `readable=1` 的权威记录，失败/澄清/取消没有记录变化。记录在 `expiresAt<=now` 或 `readable=0` 时不可读；Conversation 清理先幂等置 `readable=0`，后台再物理删除。Authorization evidence/Snapshot 不可更新，只能由新 Invocation 重新 capture；metadata reload 仅原子替换完整已验证 bundle。Key ring 的 active/previous/retired 是 common-security 配置生命周期，不进入 Agent DB 状态机。

## 14. 幂等、事务与一致性设计

同一 Invocation checkpoint 重放由 P1_V2/02 以 invocationId/checkpoint sequence/hash 处理，本文不复制 checkpoint 状态。Context 写按第 12.2 节执行数据库原子 CAS；SUCCESS finalization 在同一事务提交 secured result、全部 Context writes、Invocation 与 Turn CAS，外部只读业务调用不纳入本地事务。权限、metadata 或 Context currentness 不一致时当前 Invocation fail closed；只有新的 Invocation 可以重新规划。finalization rollback/commit unknown/CAS loser/recovery 完全服从 P1_V2/02，不补写 SUCCESS、不重执行 Handler/Adapter。

## 15. 权限、风控与审计设计

安全审计记录受访问控制的 `subjectRef/evidenceRef`、agentId/profileVersion、invocationId、capabilityId、domain、decision、reasonCode、policy/permission/metadata version 和 `purpose+keyId`；普通应用日志不记录原始 userId/tenantId。两者均禁止 Token、Secret、明文/密文 payload、完整权限表达式、未过滤结果或被 Mask 前的值。安全拒绝、紧急撤权、unknown kid、解密/AAD 失败为强制审计事件；最小 decision/reason/evidence 引用写入同一 Invocation checkpoint/finalization 审计事实，外部审计导出不进入同步主链。必要本地审计提交失败时不得返回未审计 SUCCESS。

## 16. 性能与容量设计

Profile/Policy/canonical metadata 只按 immutable version 缓存并原子发布完整 bundle；当前 P1_V2 不新增 User Permission 允许缓存。Context 单条明文/密文大小、TTL、每 owner 数量及 Result rows/bytes/evidence/generation 上限均消费 P1_V2/05 同一 Effective Capability Resource Limits，不从本地配置重算。Mask/projector 必须按候选节点数线性处理，嵌套深度和集合大小有界，禁止二次外部查询；Context cleanup 使用 `(expires_at,readable)` 索引稳定分页和 1～1000 的 batch 上限。

## 17. 兼容性与扩展性设计

新增 Context/Result 类型必须同时新增 agent-api contract、Definition declaration、codec allowlist、projector/显式迁移器和测试；旧版本只通过精确 source→target migrator 兼容。当前只实现认证 Owner + ConversationScope + `CHAT_ALL`，不创建 RunScope、Task owner、委派 Repository 或跨 Agent Context。future Multi-Agent 必须先由其 L1 定义具体 Owner/RunScope/Delegation 语义，再扩展封闭 Java 类型和 schema；Context 隔离算法仍保持 Owner + InvocationScope + contextType，不用“最近 Context”传 Task 数据。

## 18. 日志、监控与告警

指标至少包括授权允许/拒绝/权威源失败、Context read/write/CAS/迁移/解密/AAD/cleanup 失败、Result projector 拒绝/Mask 次数、limits 超限、secret lookup/unknown kid。标签只使用 stage、result、reasonCode、contextType、projectorType、secretPurpose 等受控低基数枚举；不得使用 userId、subjectRef、invocationId、keyId、版本全值、查询原文或敏感字段。连续 authority failure、unknown kid、解密/AAD 失败、cleanup backlog 和 metadata reload gate 失败必须告警。

## 19. 实现落点清单

### 19.1 Java 实现落点

| 序号 | 路径 | 类/接口 | 方法/动作 | 目标 |
|---:|---|---|---|---|
| 1 | `agent-service/src/main/java/com/dylan/agent/metadata/profile` | `AgentProfileDefinition`、`EffectiveProfile`、`AgentProfileRegistry`、`EffectiveProfileCalculator` | `getRequired/calculate`；散 page/result 字段迁移为 typed contributions | 精确不可变 Profile；只计算 Profile∩Policy |
| 2 | `agent-service/src/main/java/com/dylan/agent/metadata/policy` | `AgentPolicyConfiguration`、`AgentPolicySnapshot`、`ProfileConstraints`、`CapabilityConstraints`、`DomainSecurityConstraints`、`SecurityClassificationRef` | 增加 domain/field external-processing purpose 与 classification；拆分 PlanningBudget 与 typed resource contributions | Policy 是 purpose/classification 唯一静态事实源；缺失即拒绝 |
| 3 | `agent-service/src/main/java/com/dylan/agent/metadata/authorization` | `AuthorizationPlanningPort/Impl`、`PlanningAuthorizationEvidence`、`PlanningEffectiveScope`、`ExternalProcessingAuthorizationEvidenceFactory` | `capture/assertCurrent/freezeCapabilityScope`；构造 `EPP-1/EPM-1/EPA-1`；移除散资源字段 | 同一证据链，冻结 capability scope、limits 和外部处理授权证据 |
| 4 | 同上 | `AuthorizationExecutionPortImpl`、`AuthorizationSnapshot`、`ExecutionScope`、`ExternalProcessingAuthorizationEvidence`、`ExternalProcessingFieldRule` | `recheck(snapshot,handle)`；external-processing evidence same-or-narrower compare | 补齐 Owner/Scope/correlation/limits/classification/purpose，变化不可证明则拒绝 |
| 5 | 同上 | `DelegationConstraintRef` | 只保留 `CHAT_ALL` 中性引用；删除 `DelegationBoundary` map 与可配置 `DelegationConstraint` | 不建立委派状态/Registry |
| 6 | 同上 | `UserPermissionAuthorityPort`、`AuthServiceUserPermissionAuthorityAdapter` | `resolveCurrent(subject,deadline)` | 唯一权限权威 SPI，typed failure/fail closed |
| 7 | `agent-service/src/main/java/com/dylan/agent/metadata/catalog` | `CapabilityCatalog`、`AvailableCapability`、`AvailableCapabilitySnapshot` | `available(evidence)`，删除 entries 中散预算字段 | 通用公式、稳定排序、无专用分支 |
| 8 | `agent-service/src/main/java/com/dylan/agent/metadata/context` | `ContextBoundary` | `load/toRuntimeView/revalidateAll/approve` | Planning 读取、Core 复检/批准；不终结 Invocation |
| 9 | 同上 | `ContextRepository`、`MyBatisContextRepository`、`ContextRecordMapper` | 拆分 `insertApproved/updateApprovedCas` | 删除 SELECT + `ON DUPLICATE KEY UPDATE` 竞态 |
| 10 | 同上 | `ContextFinalizationParticipantImpl`、`ContextScopeRetirementParticipantImpl`、`ContextCleanupJob` | `persist/markConversationUnreadable/deleteExpired` | 仅 SUCCESS 持久化；Conversation 先不可读，清理幂等 |
| 11 | 同上 | `CapabilityContextEnvelope` | 删除 | 未被消费且与 Snapshot/Entity 重复 |
| 12 | `agent-service/src/main/java/com/dylan/agent/metadata/context/migration` | `ContextMigrationRegistry`、Query migrators | 精确 source→target 注册 | 禁止猜测路径和隐式缺省 |
| 13 | `agent-service/src/main/java/com/dylan/agent/metadata/crypto` | `AeadProtectedPayloadCodec`、`SecretMaterialPayloadKeyProvider`、`PayloadJsonCodec` | AES-256-GCM/AAD、purpose key lookup、typed allowlist | 删除 active key/TTL 的重复 metadata 配置读取 |
| 14 | `agent-service/src/main/java/com/dylan/agent/metadata/config` | `AgentSecuritySettings/Registry` | 删除并由 `ContextStorageProperties` 替代纯 cleanup 配置 | Policy 拥有 TTL，SecretProperties 拥有 active keyId |
| 15 | `agent-service/src/main/java/com/dylan/agent/metadata/result` | `ResultSecurityBoundary`、四类 projector、registry、`ResultValueMaskingSupport` | `secure(...,limits)` | ContractRef/scope/mask/limits/Generated Text Candidate 统一校验 |
| 16 | `common-security/src/main/java/com/dylan/common/security` | `SecretKeyRef`、`SecretMaterialProvider`、`SecretMaterial`、`SecretSourceType`、validators/sanitizer | ref 删除 `configValue`；删除未实现 `EXTERNAL`；用途隔离、受控 material 生命周期 | shared prerequisite，不修改 auth 业务模型 |
| 17 | `agent-service/src/main/java/com/dylan/agent/capability/query` | `QueryPlanValidator`、`QueryCapabilityHandler` | REPLACE/MERGE、removeFields、sorts、page/size、Context candidate | 确定性继承，最终 Validator 复检 |
| 18 | `agent-api/src/main/java/com/dylan/agent/api/context` 与 `.../response` | Context/Result sealed root 与 payload | 与 P1_V2/01 生成门禁共同校验 | Java 权威结构，不在本文复制 schema |

### 19.2 配置、SQL 与脚本落点

| 路径 | 动作 |
|---|---|
| `agent-service/src/main/resources/application.yml` | 仅配置 metadata bundle 来源、Context cleanup 与 `common.security.secrets.agent-payload` 引用；删除平行 TTL/active-key/mask 清单 |
| `auth-service/src/main/resources/application.yml` | 仅消费 `common.security.secrets.jwt` active/previous refs；不共享 payload material |
| `scripts/security/verify-secret-inputs.ps1` | 部署前验证所需 key 和来源策略，不打印 value |
| `agent-service/src/main/resources/db/agent-p0.sql` | 按第 12 节切换字段、CHECK、索引和原子 CAS 所需 schema；系统未投产直接重建 |

### 19.3 测试落点

| 路径/测试 | 关键用例 |
|---|---|
| `agent-service/src/test/java/com/dylan/agent/metadata` | Profile/Policy/Auth、Context、Result Security 全边界 |
| `AuthorizationPlanningPortTest`、`AuthorizationExecutionPortTest`、`ExternalProcessingAuthorizationEvidenceTest` | 同证据链、精确版本、撤权、范围收紧、limits 同源、purpose/classification/Mask 求交与 canonical、权威源失败；当前 Invocation 不重规划 |
| `ContextRepositoryIT`、`ContextFinalizationIT` | 并发 insert/update 原子 CAS、过期 baseline、四方事务 rollback/unknown、无平行状态机 |
| `ResultValueMaskingSupportTest`、四类 projector test | Java MaskType 全覆盖、nested value mask、ContractRef/limits、Generated Text Candidate、未知类型拒绝 |
| `common-security/src/test/java/com/dylan/common/security` | purpose 隔离、ref 不含 value、无未实现 source、prod 明文拒绝、kid 轮换、日志/Actuator 脱敏 |
| Query validator/handler tests | REPLACE/MERGE、缺 Context、removeFields、显式页码、page/size/sorts 继承/清除/覆盖、totalExact=false、撤权后继承拒绝 |
| architecture tests | 无 `DelegationLimits/DelegationBoundary/CapabilityContextEnvelope/AgentSecuritySettings`；ResultSecurity 签名携带 limits；mapper 无无条件 upsert |

## 20. 测试设计

| 类别 | 必测场景 | 关键断言 |
|---|---|---|
| Profile/Policy | 精确版本、引用缺失、紧急撤权、reload candidate 部分失败 | 不切 latest；完整 bundle 原子发布或整体拒绝 |
| Catalog | NONE/OPTIONAL/REQUIRED、空 availability、同 planKind 多 capability、稳定排序 | 无专用分支；REQUIRED 不可用不投影；不携带散预算 |
| Authorization | authority timeout/null/主体错配、Planning 后撤权、范围/limits 收紧与扩大、集合重排与字段篡改 | 失败封闭；当前 Invocation 不重规划；只接受同一或更严格 limits；canonical SHA-256 稳定且变化可检出 |
| External processing authorization | domain purpose/field purpose交集、query-only空field、classification缺失/变更、Mask变化、permission撤权、集合重排、unknown operation | 仅显式Policy∩Permission形成evidence；unknown/missing/扩大拒绝；`EPP-1/EPM-1/EPA-1`稳定且变化可检出 |
| Context read | Route 前调用、Owner/Scope 不匹配、过期/retired、wrong key/AAD/ciphertext、精确 migration | Route 前禁止；不可用不读旧缓存；Snapshot 不发送 Runtime |
| Context CAS | 并发 expected absent、并发 expected version、过期记录 baseline、affected rows=0 | 仅一个提交者；无 `ON DUPLICATE KEY UPDATE`；不丢失更新 |
| Finalization | 多 Context writes 中一条失败、commit rollback/unknown、CAS loser、澄清/失败/取消 | 四方原子回滚；不返回 SUCCESS；不写/补写 Context，不重执行 Handler |
| Query 继承 | REPLACE/MERGE、未显式 page/size/sorts、显式下一/上一/末页、sorts 空列表、`totalExact=false` | MERGE 缺省继承当前 page；显式页码生效；REPLACE 不继承；不伪造 totalPages |
| Result Security | 四类 projector、嵌套 Map/List、required 字段被过滤、limits 超限、Generated Text Candidate 引用错配 | unknown/不完整 fail closed；无原始 candidate 泄漏 |
| Mask | `NONE/ID_CARD/MOBILE/EMAIL/ADDRESS` 全量、null/集合/嵌套、未登记 type | 非敏感字段不变；无文档/配置平行枚举 |
| Secret | purpose 隔离、active/previous、unknown kid、生产 config value、Actuator/toString/log | JWT/payload 不共 key；生产拒绝明文；不输出 material |
| 架构 | 禁止空壳/重复类型和配置事实源 | 无 Delegation 存储、Context 状态机、Envelope 副本、散预算或重复 key/TTL 配置 |

## 21. 风险与待确认事项

| 风险/待确认 | 触发场景 | 处理 |
|---|---|---|
| Context DDL 未审批 | 进入持久化实施 | 先确认表结构、迁移与回滚范围 |
| 权威源 SLA 不足 | auth-service 超时 | fail closed + 告警；不得缓存允许替代实时撤权 |
| Mask 策略分散 | projector 直接读配置 | 强制 canonical policy + architecture test |
| 历史 key 提前移除 | Token/Context 未过 TTL | 以最大 TTL 计算轮换窗口 |
| 多轮继承越权 | 权限变化后读取旧 Context | 每轮按当前 scope 再投影/再校验 |
| Context CAS 伪原子 | 实现先 SELECT 再无条件 upsert | mapper 拆分 insert/conditional update，并发集成测试作为门禁 |
| shared secret 契约切换 | `SecretKeyRef` 去掉 config value 影响 JWT/payload 消费方 | 仅 common-security 内部契约，P1_V2/06 同一发布单元编译/配置切换，不修改外部 API |
| 当前 HTTP 无客户端幂等键 | 调用方网络重试 | 当前只读 capability 可产生新 Invocation 和重复预算消耗；写能力前独立 ADR |
| 外部处理 Policy 未配置 | metadata bundle 未声明 domain purpose 或 field classification | 对应 Provider operation 在任何 write 前 DENY；不得用 feature/07 ACTIVE/Provider 配置替代 |

## 22. 评审记录

| 轮次 | 日期 | 结论 | 发现问题数 | 修正问题数 | 遗留问题 | 说明 |
|---:|---|---|---:|---:|---|---|
| 1 | 2026-07-13 | In Review | — | — | — | 完成四份旧设计的独立基线合并，待整体一致性复审 |
| 2 | 2026-07-13 | 需修正 | 13 | 13 | 0 | 修正 Context 时序/状态、Catalog 缺失、授权/limits/digest、Mask、CAS、secret 与实现落点 |
| 3 | 2026-07-13 | 需修正 | 1 | 1 | 0 | Java 契约复核发现误增 QueryContextMode.NEW 和隐式 page+1，已收敛为 REPLACE/MERGE 与显式页码建议 |
| 4 | 2026-07-13 | 通过 | 0 | 0 | 0 | 终审 L0/L1、P1_V2/02/05 边界、Java 权威类型、数据与测试门禁，无 S0/S1 遗留 |
| 5 | 2026-07-14 | 需修正 | 1 | 1 | 0 | 实施发现 P2_V3/06 所需 classification/purpose 未进入 P1 两阶段授权；补 `SecurityClassificationRef`、`ExternalProcessingAuthorizationEvidence`、Policy∩Permission 求交和 Snapshot/Execution 单调收紧 |
| 6 | 2026-07-14 | 通过 | 0 | 0 | 0 | 复核 L0/L1、P1_V2/02/04/05 与 P2_V3/04～07：外部处理证据保持 capability-neutral，未把 Profile feature、Provider 配置、07 state 或 Safe candidate 变成授权源 |

## 23. 实施对齐检查

- [x] 安全真值源、两阶段授权、Context、Result Security 边界明确。
- [x] 密钥、Mask、分页与安全拒绝已并入同一闭环。
- [x] 接口、数据、状态、幂等、配置和测试落点齐备。
- [x] Capability Catalog 通用公式、Domain Mode 和 Available Snapshot 已冻结。
- [x] Context 只有 CAS/readable/TTL，不建立第二持久状态机。
- [x] Result Security 消费同一 limits，Mask 与 Java 权威枚举一致。
- [x] external-processing purpose/classification 已进入 Policy∩Permission、Snapshot 与 Execution same-or-narrower 闭环。
- [x] 公开契约版本和 Context DDL 已获本地实施授权；生产迁移仍未授权。
- [x] P1_V2 全集评审已完成且 S0/S1=0。
- [x] 用户已授权 P1_V2/P2_V3 本地实现与本次阻断修订；禁止生产访问、提交、推送、分支和 PR。

## 24. 任务完成摘要

| 项目 | 内容 |
|---|---|
| 目标文档 | 本文 |
| 文档状态 | Implemented |
| 是否可作为实现依据 | 是；用户已授权本地实现和本次 P1_V2/03 修订，L0/L1 保持只读，生产启用仍不在范围内 |
| 本次评审轮次 | 2（累计6轮） |
| 主要修订 | Catalog、两阶段授权/limits、Planning Context、原子 CAS、Result Security/Mask、secret purpose 隔离，以及 capability-neutral external-processing purpose/classification 授权证据 |
| S0/S1 遗留 | 0 |
| 是否修改关联/上级文档 | 同步修订已授权目标 P2_V3/06；未修改 L0/L1 或其他关联文档 |
| 是否需要回查旧 P1 文档 | 否 |
| 下一步 | 保持生产启用关闭；如需为具体 domain 开放外部处理，必须另行提供并评审显式 Policy purpose/classification 事实 |
