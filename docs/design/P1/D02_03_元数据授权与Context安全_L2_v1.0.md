# D02_03 元数据授权与 Context 安全 — L2 v1.0

> 文档层级：L2 实施详细设计  
> 文档状态：已实施（D01 退出门禁通过，D02 基线复核完成，代码已提交；2026-07-04 已按授权补充Query分页Context与字段越权错误码；2026-07-05 已按授权补充 QUERY 白名单排序 Context 与迁移约束）
> 上位文档：`Agent目标架构总览_v1.0.md`、`Agent契约与规划架构设计_v1.0.md`、`Agent能力执行内核架构设计_v1.0.md`、`Agent元数据与上下文安全架构设计_v1.0.md`  
> 集成权威：`D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md`  
> 关联 L2：`D02_01_Capability注册与可信执行内核_L2_v1.0.md`、`D02_02_Invocation生命周期与持久化_L2_v1.0.md`、`统一密钥管理与多注入源支持_L2实施详细设计_v1.0.md`（专项联动，不改变 D02_03 已实施基线）
> 交付阶段：D02 详细设计评审门禁；本文不实施代码/配置/SQL  
> 适用代码基线：`4ce5ac3` 及其同源后续提交

---

## 0. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-04 | 授权恢复 / 第 8、9、13～15 节 | 用户授权修订关联设计文档 | 在授权范围内补充 `QueryCapabilityContextPayload` 分页总数字段、Runtime最小Context View、`QUERY_CONTEXT` 1.0.0→1.1.0兼容迁移、`FIELD_FORBIDDEN` 安全错误码和测试门禁。 |
| 2 | 2026-07-05 | 授权恢复 / 第 7～9、13～15 节 | 用户授权同步 `Agent与业务域白名单排序能力` 关联文档 | 补充 `ExecutionValidationProjection.sortFields`、`QueryCapabilityContextPayload.sorts`、`RuntimeQueryContextView.sorts`、`QUERY_CONTEXT` 1.0.0/1.1.0→1.2.0 精确迁移和 ResultSecurity 排序回显过滤门禁。 |

---

## 1. 文档定位

### 1.1 唯一负责

本文唯一负责：

- Agent Profile Registry、Policy、外部 User Permission 和 Delegation 的消费模型；
- Effective Profile、Planning Effective Scope、授权证据链、Authorization Snapshot、Execution Scope；
- Capability Catalog 通用交集；
- D04 Domain Metadata 的消费端口及请求级安全投影/Binding 值对象；
- Capability Context payload、Envelope、Snapshot、读取、当前性、write approval、加密、TTL、CAS、cleanup；
- result ContractRef 校验、字段过滤、mask 和安全 message/summary；
- 配置、启动/reload、缓存、错误码、观测、DDL 片段和测试设计。

本文不定义 Runtime DTO、Planning 状态机、Execution Core/Lifecycle 状态机，也不实现 Canonical Domain Field Catalog、Adapter Registration 或具体 domain metadata；后者属于 D04。

### 1.2 决策映射

| 决策 | 落点 |
|---|---|
| MS-01～MS-06 | 第 3～6 节 |
| MS-07、MS-08、MS-13 | 第 7 节 D04 seam |
| MS-09～MS-12、MS-19 | 第 8～10 节 |
| MS-14、MS-15 | 第 11 节 |
| MS-16～MS-18 | 第 12～15 节 |
| CP-15 | 第 5 节同一证据链冻结 |
| EK-09、EK-16、EK-19 | Core ports、Binding、Context currentness、approved writes |

---

## 2. 包与端口结构

```text
agent-api/.../context/
├─ CapabilityContextPayload.java
├─ QueryCapabilityContextPayload.java
└─ AggregateCapabilityContextPayload.java

agent-service/.../metadata/
├─ profile/model + profile/internal
├─ policy/model + policy/internal
├─ authorization/model + authorization/request + authorization/port + authorization/internal
├─ catalog/
├─ domain/port/
├─ context/model + context/request + context/internal
├─ result/model + result/internal
├─ crypto/port + crypto/internal
└─ config/

agent-service/.../kernel/port/model/
├─ AdapterExecutionBinding.java
├─ DomainExecutionResolution.java
├─ DomainBindingRequest.java
├─ ExecutionValidationProjection.java
├─ ContextApprovalRequest.java
├─ ApprovedContextWrite.java
└─ SecuredResult.java
```

`kernel.port` 接口由 D02_01 所有；本文提供实现。Core 只依赖端口和值对象，不依赖本文的 `@Component`、Repository 或配置类。

所有以 `Snapshot`、`Scope`、`Evidence`、`Constraint`、`Ref`、`Request`、`Write`、`Result` 结尾的模型均使用 Java record 或 defensive-copy final class；公开方法仅为规范化构造器和只读访问器，除本文明确列出的方法外无 setter/业务副作用。

---

## 3. Agent Profile

### 3.1 `AgentProfileDefinition.java`

| 字段 | 类型 | 语义 |
|---|---|---|
| `agentId` | `String` | 稳定 Profile ID |
| `version` | `String` | 不可变精确版本 |
| `capabilityIds` | `Set<String>` | 只引用 Registration，不复制 Definition |
| `promptProfileRef` | `ProfileBehaviorAssetRef` | 精确assetId+version引用，不保存Prompt正文 |
| `contextReadAllow` | `Set<RuntimeContextType>` | Profile 上限 |
| `contextWriteAllow` | `Set<RuntimeContextType>` | Profile 上限 |
| `budgetLimits` | `BudgetLimits` | deadline/repair/result size 上限 |
| `delegationLimits` | `DelegationLimits` | TASK 委派上限；CHAT 为中性值 |

公开方法：全参构造器和只读访问器。Profile 不保存 Handler、Policy、用户角色、Context schema、Catalog、mask 或权限规则正文。

`AgentProfileRef`由D02_00在`shared.ref`唯一提供，字段为agentId、可选expectedVersion；本文不重复定义。

### 3.2 `AgentProfileRegistry.java`

公开方法：`AgentProfileDefinition getRequired(AgentProfileRef)`、`AgentProfileRef defaultRef()`、`Collection<AgentProfileDefinition> activeProfiles()`、`String activeVersion(String agentId)`、`void validateReferences(CapabilityRegistry)`。`getRequired`按`AgentProfileVersionKey(agentId,version)`解析精确已发布版本；ref未指定version时只允许入口在Start前解析active version，Planning/Execution绑定后禁止省略。`defaultRef()`只读取同一bundle中已校验的defaultProfileId并返回带active exact version的引用；不存在/禁用时拒绝CHAT，不静默选第一个Profile。D06 TASK由Coordinator显式传目标Profile，不调用defaultRef。

`AgentMetadataReloader`从`AgentMetadataProperties.profiles`转换不可变Definition并校验；Registry的新请求只读取已发布bundle中的active Profile，Execution可按精确key读取retained version。配置对象不是第二运行事实源；请求只访问Registry暴露的冻结版本。

Profile、行为资产、Policy与Context/Security设置不得分别发布。`ProfileBehaviorAssetRef`是assetId+version均非空的Java record；`ProfileBehaviorAsset`字段为该精确ref、不可变instructions（1～20项、每项1～500字符）和可选BCP-47 locale。它只保存经评审的行为实例，不保存结构契约、capability/domain清单、权限、预算或完整Runtime system Prompt。`AgentSecuritySettings`字段为globalMaxContextTtl、contextCleanupDelay、contextCleanupBatchSize、activePayloadKeyId。

`AgentMetadataBundle`是一次原子发布值，聚合defaultProfileId、active profile版本映射、activePolicyVersion、当前Context/Security设置、bundleVersion和bundleDigest，并同时携带本进程已发布的不可变`Map<AgentProfileVersionKey,AgentProfileDefinition> profileVersionIndex`、`Map<ProfileBehaviorAssetRef,ProfileBehaviorAsset> behaviorAssetVersionIndex`与`Map<String,AgentPolicySnapshot> policyVersionIndex`。bundleDigest覆盖本次active Profile、candidate中全部行为资产、active Policy和Context/Security语义字段，按key/集合排序、Duration/enum规范字符串化后计算canonical UTF-8 SHA-256；不包含此前保留但本次candidate未声明的历史索引、YAML原文、Map迭代顺序或时间戳。相同Profile/行为资产/Policy精确版本若结构digest不同必须拒绝reload，禁止以同version改写历史。

package-private `AgentMetadataStore`只持有一个`AtomicReference<AgentMetadataBundle>`；Reloader把candidate与current的版本索引合并后一次CAS发布，不分别更新active值和历史索引。版本索引在进程生命周期内append-only且不得按时间驱逐，reload次数/retained版本数必须可观测。旧版本只为当前进程内已开始的Invocation提供精确Execution复检，不作为新请求active来源、不跨进程持久化；重启后遗留PROCESSING Invocation只由Recovery终结，不恢复业务执行。AgentProfileRegistry、`ProfileBehaviorProjectionBoundary`、AgentPolicyConfiguration和`AgentSecuritySettingsRegistry`是同一bundle的只读边界，不各自持有可独立替换的引用。`AuthorizationPlanningPort.capture`在请求开始只读取一次active bundle语义。

`AgentSecuritySettingsRegistry.current()`返回当前bundle中的不可变settings。ContextApproval读取一次计算strict expiry；FinalizationParticipant提交前再次确认expiry不超过当前更严globalMaxContextTtl，若已收紧则整体失败而不延长/改写candidate。AeadProtectedPayloadCodec每次encrypt读取activePayloadKeyId，decrypt只信密文keyId；ContextCleanupJob每批读取cleanup delay/batch。任何组件不得回读AgentMetadataProperties。

`ProfileBehaviorProjectionBoundary.project(PlanningAuthorizationEvidence)`要求当前bundleVersion/bundleDigest与evidence完全相同，再从该bundle的精确版本索引解析evidence绑定Profile及其`ProfileBehaviorAssetRef`，返回D01 `RuntimeProfileBehaviorProjection`的防御性副本；不得二次捕获或混入新bundle。投影不得携带agentId/asset ref、capability、Policy、权限或预算。引用缺失、Profile/asset版本不符、instruction/locale不合法均fail closed。

`EffectiveProfileCalculator.compute(AgentProfileDefinition,AgentPolicySnapshot)` 是唯一Profile/Policy交集方法；无状态、无缓存、无Permission/Delegation参数。

### 3.3 `EffectiveProfile.java`

字段与 Profile 相同，但 capability/context/budget/delegation 已被 Policy 收紧，并保留 profileVersion、policyVersion。

唯一公式：

```text
Effective Profile = Agent Profile Definition ∩ Agent Policy Configuration
```

User Permission 和 Delegation 不参与 Effective Profile 计算，二者只在请求级 Planning Effective Scope 中求交。

---

## 4. Policy、Permission 与 Delegation

### 4.1 Policy 模型

`AgentPolicySnapshot` 字段：policyVersion、`Map<agentId,ProfileConstraints>`、`Map<capabilityId,CapabilityConstraints>`、`Map<domain,DomainSecurityConstraints>`、globalBudgetUpperBound、globalContextTtlUpperBound、`Set<EmergencyRevocation>`。Capability启停只由`CapabilityConstraints.enabled`表达，不存在并列disabled集合。

约束类型：

- `ProfileConstraints`：allowedCapabilityIds、contextReadAllow、contextWriteAllow、budgetUpperBound、delegationUpperBound；
- `CapabilityConstraints`：enabled、`Set<AgentCapabilityRiskLevel> allowedRiskLevels`、`Set<AgentCapabilityExecutionMode> allowedExecutionModes`、budgetUpperBound、contextTtlUpperBound；两种enum复用D01 Java类型；
- `DomainSecurityConstraints`：`Map<CanonicalFieldRef,FieldSecurityConstraint>`；nested `FieldSecurityConstraint`字段为filterAllowed、displayAllowed、`Set<AgentOperator> allowedOperators`、`Set<String> allowedFunctions`、optional requiredMask。AgentOperator复用D01 Java enum，function字符串必须由D04引用校验。它只表达部署级静态deny/intersection/mask上限，不保存角色、主体属性或用户条件，也不复制字段类型/别名；用户差异只来自UserPermission；
- `BudgetLimits`：maxTotalDuration、maxRepairAttempts、maxResultRows、maxResultBytes；
- `DelegationLimits`：maxDepth、maxTasks、allowedTargetAgentIds。
- `EmergencyRevocation`：target、targetId、targetVersion；target使用Java enum `EmergencyRevocationTarget.PROFILE_VERSION/POLICY_VERSION`，两类均要求精确非空version。PROFILE_VERSION的targetId为agentId；POLICY_VERSION的targetId必须是固定Java常量`GLOBAL_AGENT_POLICY`，避免nullable/自由占位。当前Policy不得撤销自身版本；target必须存在于合并后的retained版本索引。它只使已绑定版本立即fail closed，不授权或自动切换到新版本。

所有集合运算只能 disable、intersection 或 min/upper bound；不存在 override grant。

### 4.2 `AgentPolicyConfiguration.java`

公开方法：`AgentPolicySnapshot current()`读取activePolicyVersion，`AgentPolicySnapshot requireVersion(String)`从同一bundle的retained精确版本索引读取；普通reload不使旧版本不可解析，只有显式EmergencyRevocation或进程重启后的Recovery边界使其停止业务执行。

`AgentMetadataBundle AgentMetadataReloader.validateAndReload(AgentMetadataProperties candidate)`使用UTC Clock按candidate.reloadValidationTimeout形成absolute deadline：先完成本地Profile/行为资产/Policy/Registration/key校验，确认candidate中每个精确Profile/行为资产/Policy版本与retained索引同version同结构或为全新version，且每个active Profile的行为资产ref必须在candidate自身精确存在，不能只依赖进程历史；再从`DomainSecurityConstraints`一次提取typed `DomainMetadataReferenceSet`并调用`DomainMetadataPort.validateReferences(refs, deadline)`取得evidence。Reloader把candidate active值与旧版本索引合并生成新AgentMetadataBundle，CAS发布前再调用`assertCurrent(evidence, deadline)`。与当前bundleVersion相同且digest相同是幂等无操作并返回current，相同version但digest不同立即拒绝；新语义必须提供不同非空version。任一步失败不发布；CAS输家重新读取current并重新执行一次同version/digest/历史索引兼容判断，只有candidate active bundleDigest已存在才视为幂等成功，否则抛并发reload冲突，不循环拼接版本。候选失败继续使用尚未撤销的上一bundle；紧急撤销通过新active Policy的typed EmergencyRevocation使对应retained版本不可继续执行；无法确认有效时fail closed。

`AgentMetadataBootstrap.initialize()`在ApplicationReady前的SmartInitializingSingleton阶段同步调用Reloader；失败阻止应用就绪。`AgentMetadataRefreshListener.onEnvironmentChange(EnvironmentChangeEvent event)`仅当changed keys存在`agent.metadata.`前缀时读取已绑定candidate并调用同一Reloader；监听器不解析YAML、不局部更新Store、不吞掉失败，重叠事件由Reloader CAS/idempotency处理。

### 4.3 User Permission

`UserPermission` 是外部权威投影，字段：subject、evidenceId、version、allowedCapabilityIds、allowedDomains、field filter/display 权限、operator/function 权限、context read/write 权限、attributes、resolvedAt。

`UserPermissionAuthorityPort` 是 D02 唯一允许的外部权限消费 SPI：

```java
public interface UserPermissionAuthorityPort {
    UserPermission resolveCurrent(
        ExecutionSubjectRef subject,
        Instant absoluteDeadline
    ) throws UserPermissionAuthorityException;
}
```

`UserPermissionAuthorityFailure` 仅包含 `UNAVAILABLE`、`DEADLINE_EXCEEDED`、`SUBJECT_NOT_FOUND`、`INVALID_RESPONSE`。`UserPermissionAuthorityException` 只携带 failure、非空 diagnosticId 和内部 cause；不得携带 JWT、权限正文、凭据或外部响应体。生产 Adapter 必须按外部权威系统的已评审协议实现该 SPI，并使用稳定 `ExecutionSubjectRef` 查询当前权限；SPI 的 Java 入参与返回值是 Agent 侧唯一消费契约，不建立 YAML 权限副本。

`UserPermissionBoundary` 是 final 内部校验边界，构造器只注入唯一 `UserPermissionAuthorityPort` 和 UTC `Clock`；公开方法 `resolve(ExecutionSubjectRef, Instant absoluteDeadline)`。它在调用前后校验 absolute deadline，要求返回 subject 精确相等、evidenceId/version 非空、resolvedAt 合法且所有集合已防御性复制。`DEADLINE_EXCEEDED` 进入统一 deadline 取消通道，其余 authority failure 或非法响应统一映射为 `PERMISSION_UNAVAILABLE` 并 fail closed；不使用“上次允许”缓存、JWT role、`AgentProperties.intentRoles/domains.*Roles` 或旧 `AgentPermissionService` 兜底。

`AuthorizationSecurityConfiguration.userPermissionBoundary(List<UserPermissionAuthorityPort>, Clock)` 必须要求生产上下文中恰好一个 SPI Bean；零个或多个均在启动期失败。测试替身只允许存在于 test source/test profile，不得进入 main classpath。D02 不定义外部系统的 HTTP/数据库协议，也不臆造 auth-service endpoint；D03 原子切换完成前，必须由部署集成提供并验证一个生产 Adapter，否则不得删除旧路径或宣称可投产。当前基线只有 JWT role 和本地角色配置，不能满足该门禁。

### 4.4 Delegation

`DelegationConstraintRef` 字段：constraintId、version；CHAT 使用 `none()`。

`DelegationConstraint` 字段：allowedCapabilityIds/domains/fields/context、targetAgentIds、maxDepth/maxTasks、version。`DelegationBoundary.resolve(ref, subject, deadline)` 只返回收紧约束，不能授予 User Permission 没有的权限。

---

## 5. 两阶段授权架构

### 5.1 不可变模型

`PlanningAuthorizationEvidence` 必须包含：

- requestCorrelationId；ExecutionSubjectRef、ContextOwnerRef、InvocationScope；
- AgentProfileRef/profileVersion、policyVersion、metadata bundleVersion/bundleDigest；
- permission evidenceId/version；
- optional delegation id/version；
- EffectiveProfile、PlanningEffectiveScope；
- 与Handle完全相同的absoluteDeadline；
- capturedAt；
- evidenceDigest。

`PlanningEffectiveScope` 包含请求当前允许的 capability、domain、field filter/display、operator/function、Context read/write、mask、risk/execution/budget 上限。

`evidenceDigest`是对request correlation、subject/owner/scope、绑定Profile/Policy/bundle版本、permission evidenceId/version及规范化权限投影、optional delegation引用及规范化约束、PlanningEffectiveScope和absoluteDeadline按固定字段顺序计算的canonical SHA-256；集合先按规范字符串排序，capturedAt不参与语义digest。`assertCurrent`必须重新解析当前Permission/Delegation并重算语义digest，同时比较精确版本引用；即使外部权威错误地复用version，只要权限投影变化也必须失败，不得只比较version字符串。

`AuthorizationSnapshot` 是 capability-scoped，不是 pre-Route 全量快照，字段：

- snapshotId、requestCorrelationId、subject、owner、scope；
- profile/policy/permission/delegation 精确引用和 evidenceDigest；
- registrationIdentity、capabilityId、planKind、optional domain；
- capability 范围内 fields/operators/functions/context read/write/mask；
- `ExecutionBudget`：`maxRepairAttempts`、`maxResultRows`、`maxResultBytes`，来源为 freeze 时刻 `PlanningEffectiveScope` 的已收敛预算；
- 与本次 `AvailableCapabilitySnapshot` 完全相同的 `DomainMetadataEvidence`；
- frozenAt。

`ExecutionScope` 字段与 capability-scoped范围一致，原样保留 Snapshot 绑定的 `DomainMetadataEvidence` 和 `ExecutionBudget`，并记录 recheckedAt/current permission evidence/current policy version。它只能等于或小于 Snapshot；执行复检不得替换为新的 Domain metadata 版本，也不得引入新的 Profile/Policy/D04 版本来扩大或重算预算。

### 5.2 `AuthorizationPlanningPort`

| 方法 | 语义 |
|---|---|
| `capture(PlanningSecurityRequest)` | Route 前解析 Profile/Policy/Permission/Delegation，形成一次证据链 |
| `assertCurrent(PlanningAuthorizationEvidence)` | 每次 Route/Plan 前及 freeze 前确认同一证据仍有效；变化即 fail closed |
| `freezeCapabilityScope(PlanningAuthorizationEvidence, CapabilityScopeSelection)` | Valid ExecutablePlan 后从同一证据链裁剪并冻结 Snapshot；禁止重新 resolve 混版本 |

`PlanningSecurityRequest`只接受Handle、与Handle绑定值相等的AgentProfileRef、DelegationConstraintRef；不相等立即拒绝。`CapabilityScopeSelection`只接受ResolvedRegistration、选定domain、按contextType唯一的ContextSnapshot references，以及与本次`AvailableCapabilitySnapshot.domainMetadataEvidence()`精确值相等的完整`DomainMetadataEvidence`；禁止依赖对象identity，也禁止拆成若干可由调用方分别替换的D04版本字段。

`AuthorizationPlanningPortImpl`是唯一实现，构造器注入同一`AgentMetadataStore`只读边界、`EffectiveProfileCalculator`、`UserPermissionBoundary`、`DelegationBoundary`和UTC Clock；三个公开方法与接口完全相同，不增加缓存、重试、fallback或第二个Profile/Policy读取路径。

### 5.3 `AuthorizationExecutionPortImpl`

实现 D02_01 `AuthorizationExecutionPort.recheck(snapshot, handle)`：

1. 校验 correlation、subject、owner、scope 与 Handle 相同。
2. 以 Handle absolute deadline 调用 `DomainMetadataPort.assertCurrent(snapshot.domainMetadataEvidence(), deadline)`；不得把绑定版本替换为 active 版本。Registration identity 只由 Core 对 Planning 携带的同一不可变引用校验，本端口不得重查 Registry。
3. 重新解析当前 UserPermission，只用于确认当前权限仍覆盖 Snapshot 冻结的 capability、domain 和 field 集合；不得用当前权限、Profile、Policy 或 Delegation 扩大 Snapshot。
4. `ExecutionScope = Snapshot ∩ Current Permission`，其中 `ExecutionBudget` 从 Snapshot 原样带入；若未来允许预算收窄，也只能在不引入新 Profile/Policy/D04 版本的前提下取更小值。
5. 若选定 capability/domain、Raw Plan 使用的 field/operator/function、必要 Context 权限被移除，fail closed。
6. 仅无关字段范围缩小时返回更窄 ExecutionScope，供 Validator/Result Security 执行；不因“发生缩小”本身自动失败，也绝不扩大。

`AuthorizationExecutionPortImpl`构造器只注入`UserPermissionBoundary`、`DomainMetadataPort`和UTC Clock；不注入`AgentMetadataStore`、`DelegationBoundary`、CapabilityRegistry、Runtime client、Context Repository或Handler，避免执行阶段混入新的 Profile/Policy/Delegation 事实。

### 5.4 禁止事项

- Snapshot 不保存 JWT、完整 Policy/Permission 表达式或凭据。
- Planning 不在 capability 选择前冻结 capability Snapshot。
- Route/Plan/freeze 不重新读取并混入另一版本链。
- Runtime/Handler/Adapter 不生成或修改 Snapshot。

---

## 6. Capability Catalog

### 6.1 模型

`AvailableCapability` 字段：capabilityId、planKind、domainMode、typed `CapabilityRoutingDescriptor` 安全投影输入、allowedDomains、risk/execution/budget limits、registrationIdentity。

`AvailableCapabilitySnapshot`字段：requestCorrelationId、authorization evidenceDigest、`DomainMetadataEvidence`、不可变capabilities、createdAt；方法：`contains`、`getRequired`、`capabilityIds`。它不是最终执行许可。

### 6.2 `CapabilityCatalog.java`

构造依赖：CapabilityRegistry、`DomainMetadataPort`。Profile/Policy/Permission/Delegation只通过同一`PlanningAuthorizationEvidence`进入，Catalog不得二次读取。

公开方法：`AvailableCapabilitySnapshot available(PlanningAuthorizationEvidence evidence)`。Catalog只使用evidence内已冻结的EffectiveProfile/PlanningEffectiveScope和absoluteDeadline，不重新读取Profile、Policy、Permission或Delegation，也不接受调用方提供第二个deadline。

唯一算法：先从不可变 Registry 视图收集本次可能使用的全部 `AdapterRole`，再且仅调用一次 `availability(roles, scope, deadline)`；不得按 Registration 循环取得多个可用性快照后自行拼接。随后执行：

```text
Registered Registration
∩ Planning Effective Scope（已唯一包含Effective Profile/Policy/Permission/Delegation）
∩ Domain availability from D04 port
= Available Capability Snapshot
```

Catalog不得再次分别应用Profile或Policy；Definition的risk/execution声明只与PlanningEffectiveScope内已收敛上限比较，不构造第二份Policy交集。

DomainMode：NONE 不要求 domain/binding；OPTIONAL 可在 allowedDomains 为空时保留无 domain 用法，仅当 Definition 语义允许；REQUIRED 在无合法 `(role,domain,port)` 时不投影。算法不得按 capabilityId/domain 写专用分支。

---

## 7. D04 Domain Metadata 消费端口

### 7.1 边界

D02 不创建 Canonical Catalog、DomainFieldCatalog 或 AdapterRegistration 实现。本文只冻结 D04 必须实现的端口：

```java
public interface DomainMetadataPort {
    Set<AdapterRole> knownRoles();

    DomainMetadataEvidence validateReferences(
        DomainMetadataReferenceSet references, Instant deadline);

    DomainAvailabilitySnapshot availability(
        Set<AdapterRole> roles, PlanningEffectiveScope scope, Instant deadline);

    void assertCurrent(
        DomainMetadataEvidence expected, Instant deadline);

    List<RuntimeDomainRoutingProjection> routeProjection(
        Set<String> domains, PlanningEffectiveScope scope,
        DomainMetadataEvidence expected, String authorizationEvidenceDigest,
        Instant deadline);

    RuntimeDomainSchema planSchema(
        AdapterRole role, String domain, PlanningEffectiveScope scope,
        DomainMetadataEvidence expected, Instant deadline);

    ExecutionValidationProjection executionProjection(
        AdapterRole role, String domain, ExecutionScope scope,
        DomainMetadataEvidence expected, Instant deadline);

    AdapterExecutionBinding bind(
        AdapterRole role, String domain, ExecutionScope scope,
        DomainMetadataEvidence expected, Instant deadline);
}
```

`CanonicalFieldRef`是只含非空规范domain与field的Java record；`CanonicalOperatorRef`包含fieldRef和D01 `AgentOperator`；`CanonicalFunctionRef`包含fieldRef和规范functionId。`DomainMetadataReferenceSet`包含三种不可变Set并提供`empty()`，构造器要求operator/function所属field同时出现在fields集合。它们只表达引用，不保存类型、别名或支持能力等Catalog事实。`validateReferences`必须在同一不可变Catalog版本一次验证全部field/operator/function引用存在且相互闭合，并返回该版本evidence；空reference set仍返回当前evidence。Route/Plan 返回类型复用 D01 Java DTO，不在 D02 重定义。D04实现必须从唯一Canonical Catalog/Adapter Registration的同一不可变版本视图投影。除首次`availability`/`validateReferences`外，`assertCurrent`、Route、Plan、execution projection和binding都必须比较完整`expected`；当前版本不一致时fail closed，禁止悄然切换到新版本。

### 7.2 值对象

`DomainMetadataEvidence`是不可变值，字段为catalogVersion、adapterRegistrationVersion、availabilityDigest、capturedAt；availabilityDigest由D04全局原子部署/健康availability快照按registration/health key排序计算，不依赖本次请求roles、Map顺序或capturedAt。`assertCurrent`比较catalogVersion、adapterRegistrationVersion和availabilityDigest，capturedAt只用于证据时序/过期判断，不要求与重新读取时间相等。`safeRef()`返回三项版本/digest和capturedAt规范UTC值的canonical SHA-256，不包含Catalog正文或Adapter实现信息，所有Planning/Invocation安全引用只能使用该方法。

`DomainAvailabilitySnapshot`：DomainMetadataEvidence、`Map<AdapterRole,Set<String>> availableDomains`。返回映射必须精确覆盖请求roles且来自同一原子版本视图；roles为空时仍返回当前evidence和空映射。缺项、额外项、重复绑定或混合版本一律失败。Route/Plan投影若当前版本与expected不一致必须fail closed，不能在当前Planning混入新版本。

`ExecutionFieldRule`是D04 canonical metadata的安全执行投影，字段为canonical field、`AgentFieldType`、allowed operators/functions、optional maxLength/precision/scale/valueFormat；所有集合不可变，约束只能比Catalog更严。它不含数据库列、Adapter实现、mask、角色或权限表达式。

`ExecutionValidationProjection`字段为optional AdapterRole、optional domain、按canonical field唯一的`Map<String,ExecutionFieldRule>`、defaultSelectFields、`Set<String> sortFields`、maxPageSize、maxResultRows、projectionVersion；role/domain必须同时存在或同时为空。`sortFields`只能来自D04 role capability与当前ExecutionScope的交集，且必须是`fieldRules.keySet()`子集；静态`none()`只允许domainless的NONE/OPTIONAL路径，返回空role/domain/map/list/set、最严零业务上限和固定内部`NO_DOMAIN`版本，不查询D04；有domain时禁止使用none。Validator只能消费该投影，不读取旧`AgentProperties.domains`或Adapter自报字段清单。

`AdapterExecutionBinding`：AdapterRole、domain、portType、`AgentAdapterPort port`、adapterRegistrationVersion、resolvedAt。port 必须与 role 预期 Java SPI 类型一致。

`DomainBindingRequest`：ResolvedRegistration、非空selected domain、ExecutionScope、expected `DomainMetadataEvidence`、absoluteDeadline。它只为OPTIONAL有domain或REQUIRED路径创建；expected evidence只能从`ExecutionScope`中原样派生，构造器必须拒绝与Scope不相等的值；Core、Handler不得替换。

`DomainExecutionResolution`字段为required AdapterExecutionBinding、required ExecutionValidationProjection和expected DomainMetadataEvidence；构造器校验binding/projection的role、domain、catalog/adapter版本与request expected evidence闭合。`DomainSecurityBoundary`实现D02_01 `DomainExecutionPort.resolve`：将request中的同一expected evidence分别传给D04 `executionProjection`与`bind`，每个Invocation各最多调用一次，在边界内部组装唯一resolution；任一调用发现版本变化均失败。Core、Validator和Handler只消费该resolution，不自行配对两个返回值。

### 7.3 D04 启动门禁

D04 必须验证 role/domain 唯一、port type、Catalog覆盖、field/operator/function与Adapter真实能力闭合。D02只规定错误必须 fail closed，不为缺失D04实现提供fallback或静态配置副本。

D04还必须先建立`AgentAdapterPort` marker并让现有Queryable/Aggregatable SPI继承，再创建AdapterRegistration；D03不得临时补这一前置类型。

---

## 8. Context Java 契约

### 8.1 Payload 单一来源

`CapabilityContextPayload` 位于 agent-api，是内部 Context payload 的 Java 单一结构源：

```java
public sealed interface CapabilityContextPayload
        permits QueryCapabilityContextPayload, AggregateCapabilityContextPayload {
    RuntimeContextType contextType();
}
```

`QueryCapabilityContextPayload` 是不可变 record，字段为 `List<AgentFilter> filters`、`List<String> selectFields`、`List<AgentSortSpec> sorts`、`int page`、`int size`、nullable `Long total`、nullable `Boolean totalExact`、nullable `Integer totalPages`；构造器 defensive copy 并验证page/size正数、`sorts`非null且字段/方向非空、`total`非负、`totalPages`为正数或null。`sorts`只保存canonical字段名与`ASC`/`DESC`方向，不保存字段值、数据库列名或权限正文。`totalPages`仅在`totalExact=true`且`total`、`size`可用时由query handler计算，规则为`max(1, ceil(total / size))`。

`AggregateCapabilityContextPayload` 是不可变 record，字段为 `List<AgentFilter> filters`、`List<AggregateMetricSpec> metrics`、`List<String> groupByFields`、`List<AggregateOrderSpec> orderBy`、`int maxRows`；构造器 defensive copy 并验证非空 metrics/正数 maxRows。

两者字段类型复用 agent-api Java Plan 类型，不保存完整业务结果、summary、权限或凭据；公开方法只有 record 访问器和固定 `contextType()`。Query的`total`、`totalExact`、`totalPages`是分页规划元数据，不是业务明细结果；它们不得包含员工姓名、证件、电话、地址等业务字段值，也不得携带权限正文或mask规则。

D01 `RuntimeContextView` 是由 payload 形成的最小 Runtime 投影，不是 Envelope/Snapshot。`RuntimeContextType` 作为唯一结构 discriminator复用，不新增 `AgentContextType` 平行 enum。

Query对应的`RuntimeQueryContextView`只投影`sourceInvocationId`、filters、selectFields、sorts、page、size、total、totalExact、totalPages。Runtime可据此把“下一页/上一页/第一页/最后一页”输出为具体page并保持上一轮排序；当`totalExact`不为true或`totalPages`为空时，Runtime不得猜测最后一页，必须返回澄清或让Java安全拒绝。`sorts`投影仍受readableFields控制，未声明可读时不得输出。

### 8.2 Owner、Key 与 Envelope

`ContextRecordKey` 字段：ContextOwnerRef、InvocationScope、RuntimeContextType；唯一标识当前逻辑记录。

`CapabilityContextEnvelope` 持久化语义字段：contextId、ContextRecordKey、ContractRef、sourceCapabilityId/sourceInvocationId、optional sourceDomain、encrypted payload metadata、expiresAt、recordVersion、createdAt/updatedAt。sourceDomain由成功ExecutionScope派生，domainless capability为空；它不进入逻辑key但用于阻止跨domain继承。Entity 与明文领域对象分离。

Context序列化/解密后反序列化只通过D02_01 `ContractRegistry.require(contractRef).javaType()`取得声明中的唯一`CapabilityContextPayload` subtype，使用与Result相同的strict ObjectMapper配置并校验payload.contextType、declaration payloadType、ContractRef三者一致；禁止Jackson default typing、持久化Java class name或根据JSON字段猜类型。

唯一`PayloadJsonCodec`位于`metadata.crypto.internal`，构造器内部创建/接收专用ObjectMapper并显式禁用default typing，启用FAIL_ON_UNKNOWN_PROPERTIES/FAIL_ON_INVALID_SUBTYPE/FAIL_ON_NULL_FOR_PRIMITIVES、SORT_PROPERTIES_ALPHABETICALLY和ORDER_MAP_ENTRIES_BY_KEYS，注册JavaTimeModule；公开`byte[] serialize(Object value,Class<?> expectedType)`、`<T> T deserialize(byte[] bytes,Class<T> expectedType)`。两方法先做expectedType实例校验并限制root为`CapabilityContextPayload`或`AgentResultPayload`，不接受调用方class name字符串；ContextBoundary、ResultSecurityBoundary和InvocationResultRepository必须共用该Bean。

### 8.3 `ContextSnapshot`

字段：

- requestCorrelationId、contextId、ContextRecordKey；
- storedContractRef、effectiveContractRef、sourceCapabilityId/sourceInvocationId、optional sourceDomain；
- exact recordVersion、expiresAt；
- profile/policy/permission/delegation evidence references；
- expectedWriteVersion（与 recordVersion 相同，或 expected-absent）；
- 当前 Invocation 内存活的 typed CapabilityContextPayload。

Snapshot 不跨 Invocation 缓存、不发送 Runtime、不允许调用方修改。

无迁移时stored/effective ContractRef必须相等；显式迁移时storedRef来自Envelope，effectiveRef必须等于当前read declaration/migrator target，typed payload属于effective type。Execution currentness同时复检数据库storedRef未变、同一精确migrator仍唯一且effectiveRef仍是Registration声明，不能只比较迁移后版本。

### 8.4 Write 模型

`ContextWriteCandidate` 只包含 RuntimeContextType、ContractRef、CapabilityContextPayload。Handler 不填 owner/scope/source capability/invocation/domain/expiry/recordVersion。

`ContextApprovalRequest`包含InvocationHandle、ResolvedRegistration、ExecutionScope、按contextType索引的不可变consumed ContextSnapshots、Clock instant。

`ExpectedContextVersion`是封闭联合：`ExpectedAbsent`或`ExpectedVersion(long recordVersion)`，禁止两个nullable字段组合；统一`long targetVersion()`在absent时返回0、existing n时返回n+1，供Entity与AAD使用并检查long overflow。

`ApprovedContextWrite`包含边界派生的contextId、ContextRecordKey、ContractRef、source capability/invocation/optional domain、payload、strict expiry和ExpectedContextVersion。已有记录沿用精确contextId，expected-absent在Approval时生成不可预测新ID；只有Core的ContextApprovalPort可以创建，Handler不能提供或替换ID。

### 8.5 版本兼容与迁移

`ContextPayloadMigrator<S extends CapabilityContextPayload,T extends CapabilityContextPayload>` 方法：`ContractRef source()`、`Class<S> sourceType()`、`ContractRef target()`、`Class<T> targetType()`、`T migrate(S sourcePayload)`。source/target Class必须分别与ContractRef结构摘要及contextType匹配，启动时验证。

`ContextMigrationRegistry` 方法：`Optional<ContextPayloadMigrator<?,?>> resolve(ContractRef source, ContractRef target)`、`void validateNoAmbiguousPathOrCycle()`。Registry按精确source/target解析，不搜索“最近版本”，不允许运行时脚本或Prompt迁移。存储ContractRef与当前声明不同时，ContextBoundary必须先解析唯一Migrator，再使用其sourceType严格反序列化和校验，迁移后验证targetType/target ContractRef；无迁移器时不得让ContractRegistry或Jackson猜类型。

v1首个D03实现只注册恒等兼容或明确列出的单跳迁移；无迁移器的必需Context fail closed，可选Context按缺失处理。读取时迁移只产生当前Invocation内的Snapshot/View，不回写记录、不延长TTL；新成功write按目标ContractRef和expected record version完成升级。

`QUERY_CONTEXT` 1.0.0 到 1.2.0 必须提供精确直接迁移：旧payload的filters/selectFields/page/size原样保留，`sorts`补为`List.of()`，total、totalExact、totalPages补为null。`QUERY_CONTEXT` 1.1.0 到 1.2.0 也必须提供精确迁移：保留filters/selectFields/page/size/total/totalExact/totalPages，`sorts`补为`List.of()`。由于`ContextMigrationRegistry`不做路径搜索，不能只依赖`1.0.0 -> 1.1.0 -> 1.2.0`链式组合。迁移只用于当前Invocation读取和Runtime View投影；只有后续成功query write才以1.2.0 ContractRef写回。禁止通过Prompt、脚本或“latest”猜测补齐分页总数或排序字段。

---

## 9. Context 端口与算法

### 9.1 Planning Read

`ContextReadRequest` 字段：Handle、ResolvedRegistration、selectedDomain、PlanningAuthorizationEvidence、ContextReadDeclaration、Clock instant。selectedDomain必须与已校验RouteDecision/Registration DomainMode一致。

`ContextBoundary.load(request)` 实现`ContextPlanningPort`：

```text
Registration read declaration
∩ Planning Effective Scope
∩ Owner
∩ exact Invocation Scope
∩ selected domain与sourceDomain一致
∩ compatible ContractRef/version
∩ unexpired TTL
```

必需 Context 缺失、sourceDomain不匹配、解密失败、schema不兼容、候选不唯一或存储不可用时 fail closed；可选缺失或domain不匹配返回empty。不得按同用户或其他domain的“最近 Context”回退。

`ContextPlanningPort.toRuntimeView(ContextSnapshot snapshot, ContextReadDeclaration declaration, PlanningAuthorizationEvidence evidence)`返回D01 `RuntimeContextView`封闭union中的最小typed投影。它复检snapshot correlation/Owner/Scope、declaration与effectiveContractRef、stored迁移证据及当前Planning scope，只投影`readableFields`交集；PlanningService不得按contextType自行组装View。新增Context type只扩展agent-api payload/View subtype及本边界投影，不修改Planning主流程。

当Context type为QUERY时，`toRuntimeView`必须按readableFields投影filters/selectFields/sorts/page/size/total/totalExact/totalPages；如果readableFields未包含`sorts`或分页总数字段，则不得输出这些字段。默认`query.search` declaration应包含这些字段，以支持排序分页继承和末页计算；`query.preview`首版只读Context且不写Context，是否使用上一轮`sorts`必须由D05明确约束，其他capability不得通过自由Map读取query payload内部字段。

### 9.2 Execution Currentness

`ContextBoundary.revalidateAll(snapshots, handle, registration, scope)`实现D02_01 `ContextExecutionPort`，必须先拒绝重复contextType，再对每个Snapshot在Validator前检查：request correlation、Owner、scope type/id、对应read declaration、stored/effective ContractRef与迁移器、source capability/invocation/domain、recordVersion、readable标志、TTL、当前context read权限。任何变化fail closed，不加载另一记录继续执行。

### 9.3 Write Approval

`ContextBoundary.approve(candidates, request)` 实现D02_01 `ContextApprovalPort`，对每个候选执行：

```text
Effective Context Write Scope
= Registration write declaration
∩ Execution Scope
∩ Owner/Invocation Scope from Handle
∩ declared ContractRef/schema
∩ payload type/field allowlist
∩ strictest TTL(Definition, Profile, Policy, global security limit)
```

source capability/invocation/domain、Owner/Scope、expiry 和 expected version全部由边界派生。重复 contextType candidate、未声明字段、完整业务结果或凭据一律拒绝。

若本次未消费同type Snapshot，Approval仍须按ContextRecordKey读取当前记录元数据：记录存在（含已过期但尚未清理）时沿用contextId并使用其精确recordVersion更新，只有确认不存在时才生成新contextId和expected-absent；不得让Handler选择insert/update，也不得无条件覆盖旧记录。

### 9.4 Finalization

`ContextFinalizationParticipantImpl.persist(List<ApprovedContextWrite>)` 使用 `Propagation.MANDATORY`，只在 Lifecycle SUCCESS transaction 内调用。每个 write 执行 expected-version CAS；任一 CAS/加密/存储失败抛出安全异常使整个 transaction 回滚。

D02_02 `FinalizationTxService`从传给本方法的同一不可变ApprovedContextWrite列表按contextType排序，派生`ContextWriteCommitRef`并写入Invocation；本实现不得接收或返回另一份可替换refs列表。commit ref只记录contextId、target ContractRef/recordVersion与安全digest，不复制payload；空write列表仍形成明确的`[]`。

---

## 10. Context Repository、加密、TTL 与清理

### 10.1 `ContextRepository`

公开/包内方法：

| 方法 | 语义 |
|---|---|
| `Optional<ContextRecordEntity> findCurrent(ContextRecordKey key)` | 精确逻辑 key；不使用 latest guess |
| `int insertExpectedAbsent(ContextRecordEntity entity)` | 仅 key 不存在时插入 |
| `int updateExpectedVersion(ContextRecordEntity entity, long expectedVersion)` | `WHERE record_version=?` CAS |
| `Optional<ContextRecordEntity> findExact(String contextId, long recordVersion)` | Execution currentness |
| `int markUnreadableByConversationScope(ConversationScope scope, Instant now)` | 物理删除前独立提交安全retirement；幂等 |
| `int deleteExpired(Instant cutoff, int limit)` | 幂等 TTL cleanup |

`ContextRecordMapper` 提供上述 SQL；Repository 不以 `ORDER BY created_at DESC LIMIT 1` 决定权威记录。

### 10.2 `ProtectedPayloadCodec`

`ProtectedPayloadCodec` 是稳定port，方法：`ProtectedPayload encrypt(byte[] plaintext, PayloadProtectionContext context)`、`byte[] decrypt(ProtectedPayload payload, PayloadProtectionContext context)`。D02_02 InvocationResultRepository只依赖此port。

`PayloadProtectionContext`是不可变AAD值，字段：`PayloadPurpose purpose`、recordId、required ContractRef、bindingDigest。只有带typed payload的Context和SUCCESS Invocation Result进入codec，CLARIFY不构造该值。Context的bindingDigest按ContextRecordKey、sourceCapabilityId/sourceInvocationId/sourceDomain和目标recordVersion生成canonical SHA-256；Invocation Result按invocationId、responseType生成。AAD由上述字段的确定性UTF-8编码产生且不随密文持久化，读取时从权威数据库列重建；任何跨record、scope、domain、schema、version或purpose替换都必须解密失败。

`ProtectedPayload` 字段：ciphertext、keyId、nonce、algorithmVersion。`AeadProtectedPayloadCodec`是唯一codec实现，构造器注入`AgentSecuritySettingsRegistry`和`PayloadKeyProvider`，使用AES-256-GCM、每次加密唯一96-bit随机nonce和完整`PayloadProtectionContext` AAD；禁止nonce复用。加密keyId只取当前不可变settings，密钥不得写入YAML/日志。解密/tag校验失败fail closed；key rotation不改变ContractRef/schema。

`PayloadKeyProvider`方法为`SecretKey requireKey(String keyId)`。密钥来源由`统一密钥管理与多注入源支持_L2实施详细设计_v1.0.md`定义的统一密钥入口负责，`EnvironmentPayloadKeyProvider`仅作为环境变量来源的初始/兼容实现之一。keyId必须匹配`[A-Za-z0-9_]{1,64}`；生产环境密钥值不得写入YAML、日志、Spring Properties或配置导出，必须通过环境变量或外部Secret来源注入；开发/演示环境如需配置文件注入，必须受统一密钥入口的profile策略和启动期校验控制。active key在启动时必须可解析，历史key按密文keyId解析以支持轮换；缺失、长度错误、算法错误或生产明文配置违规均拒绝启动/解密。未来接Vault/KMS只替换统一密钥入口实现，不修改codec、Context、Result或配置结构。

统一密钥管理专项可在后续实施中新增`SecretMaterialPayloadKeyProvider`适配统一入口；该类不属于本 D02_03 已实施基线。本文冻结的是`PayloadKeyProvider`端口、`AeadProtectedPayloadCodec`算法/AAD语义和密钥来源边界。

Invocation filtered result 和 Context 共用此保护基础设施，但使用不同purpose和记录级AAD，不能互相或跨记录解密。

### 10.3 TTL 与清理

- Context expiry 取 Definition/Profile/Policy/global security limit 的最小值；读取/merge 不能延长。
- TTL 到期即逻辑不可读，cleanup 延迟不重新开放。
- `ContextCleanupJob.tick()`使用固定30s基础触发器，每次从AgentSecuritySettingsRegistry读取cleanupDelay/batchSize，仅在`now>=nextEligibleAt`时执行一批`deleteExpired`并按当前delay推进；不把可reload delay放入`@Scheduled`占位符或回读Properties。
- Conversation 删除/过期先由D02_02 `ContextScopeRetirementParticipant`调用本文实现，在独立短事务把对应ConversationScope Context幂等标记为不可读；retirement提交成功后，`AgentStateCleanupService`才在后续事务删除Conversation，并经Conversation→Invocation→Context外键级联物理删除。物理删除失败时记录保持不可读并可重试；不再维护第二套按Scope物理删除SQL。
- D06 RunScope 清理由未来 Task State Boundary 在 D06 L2 定义并调用其拥有的同库清理事务；D02 不预建未使用的 RunScope cleanup 端口。
- 清理 job 只回收，不改变 Invocation 终态。

### 10.4 DDL 片段

由 D02_02 汇总进唯一 `agent-p0.sql`：

```sql
CREATE TABLE agent_capability_context (
  context_id VARCHAR(64) PRIMARY KEY,
  owner_type VARCHAR(32) NOT NULL,
  owner_id VARCHAR(128) NOT NULL,
  scope_type VARCHAR(32) NOT NULL,
  scope_id VARCHAR(64) NOT NULL,
  context_type VARCHAR(32) NOT NULL,
  schema_name VARCHAR(128) NOT NULL,
  schema_version VARCHAR(32) NOT NULL,
  source_capability_id VARCHAR(128) NOT NULL,
  source_invocation_id VARCHAR(64) NOT NULL,
  source_domain_id VARCHAR(128) NULL,
  encrypted_payload LONGBLOB NOT NULL,
  encryption_key_id VARCHAR(128) NOT NULL,
  encryption_nonce VARBINARY(12) NOT NULL,
  algorithm_version VARCHAR(32) NOT NULL,
  readable BOOLEAN NOT NULL DEFAULT TRUE,
  expires_at DATETIME(3) NOT NULL,
  record_version BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL,
  updated_at DATETIME(3) NOT NULL,
  UNIQUE KEY uk_context_current
    (owner_type, owner_id, scope_type, scope_id, context_type),
  KEY idx_context_expiry (readable, expires_at),
  KEY idx_context_source (source_invocation_id),
  CONSTRAINT fk_context_source_invocation FOREIGN KEY (source_invocation_id)
    REFERENCES agent_invocation_record(invocation_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 11. Result Security

### 11.1 模型与接口

`FilteredResult<O extends AgentResultPayload>`是projector内部不可变候选，字段为filtered/masked payload、safeMessage、safeSummary；只在`ResultSecurityBoundary.secure`调用栈内存活，不进入Core/Lifecycle。

`SecuredResult`字段：defensive-copy `byte[] canonicalFilteredPayload`、ContractRef、payloadDigest、safeMessage、safeSummary。它不暴露typed payload引用，`canonicalPayloadCopy()`每次返回副本；payloadDigest为canonical bytes的SHA-256。SUCCESS的API type统一为RESULT，具体结果形状由后续严格反序列化所得payload discriminator表达。

`ResultSecurityProjector<O extends AgentResultPayload>`方法：`ContractRef supports()`、`FilteredResult<O> filter(O candidate, ExecutionScope scope)`。

`ResultSecurityProjectorRegistry` 按 output ContractRef 唯一解析 projector；重复/缺失拒绝启动或执行，不按 capabilityId/domain 路由。

`ResultSecurityBoundary`实现D02_01 `ResultSecurityPort.secure(Object,ContractRef,ExecutionScope)`：先以ContractRegistry验证candidate type/ContractRef，再调用唯一projector；验证FilteredResult payload仍是对应AgentResultPayload subtype、safeMessage/summary只由filtered payload生成且大小不超ExecutionScope，随后立即通过唯一`PayloadJsonCodec`按ContractRegistry expected type严格序列化为canonical bytes并构造SecuredResult。任一不一致或序列化失败整体失败；Core/Lifecycle永远拿不到过滤后仍可变的typed引用。

### 11.2 既有输出 projector

- `QueryResultSecurityProjector`：过滤`QueryAgentResultPayload`中的rows/columns/query parameters，逐字段应用mask，再从过滤后payload生成message/summary。
- `AggregateResultSecurityProjector`：过滤`AggregateAgentResultPayload`中的group/metric fields，应用mask/visibility，再生成summary。

mask 使用 `FieldMaskerRegistry` 现有实现，但 MaskType 的唯一目标 enum保留在 Java policy模型中；D03删除重复 enum/source。任何 mask/projector异常使执行失败，不返回部分未过滤结果。

具体收敛：保留现有`com.dylan.agent.model.MaskType`作为唯一MaskType（值为NONE、ID_CARD、MOBILE、EMAIL、ADDRESS）；删除混合operator和角色事实的旧`com.dylan.agent.model.FieldPolicy`。本文`DomainSecurityConstraints`只保存访问/mask以及经D04校验的operator/function收紧引用；operator/function支持事实仍只来自D04 Canonical Catalog。

---

## 12. 配置设计

### 12.1 `AgentMetadataProperties`

`@ConfigurationProperties("agent.metadata")` 字段：bundleVersion、defaultProfileId、profiles、behaviorAssets、policy、context、security、reloadValidationTimeout。Java nested types完整映射第3、4、10节的实例数据，不定义字段类型/operator/alias等D04事实。

目标配置形状：

```yaml
agent:
  metadata:
    bundle-version: "1"
    reload-validation-timeout: 5s
    default-profile-id: default
    profiles:
      default:
        version: "1"
        capability-ids: [query.search, aggregate.compute]
        prompt-profile-ref:
          asset-id: default
          version: "1"
        context-read-allow: [QUERY, AGGREGATE]
        context-write-allow: [QUERY, AGGREGATE]
        budget-limits:
          max-total-duration: 60s
          max-repair-attempts: 2
          max-result-rows: 1000
          max-result-bytes: 1048576
        delegation-limits:
          max-depth: 0
          max-tasks: 0
          allowed-target-agent-ids: []
    behavior-assets:
      default:
        version: "1"
        instructions: ["使用简洁、可核验的中文回答"]
        locale: zh-CN
    policy:
      version: "1"
      profile-constraints: {}
      capability-limits: {}
      domain-security: {}
      global-budget-upper-bound:
        max-total-duration: 60s
        max-repair-attempts: 2
        max-result-rows: 1000
        max-result-bytes: 1048576
      global-context-ttl-upper-bound: 7d
      emergency-revocations: []
    context:
      global-max-ttl: 7d
      cleanup-delay: 1h
      cleanup-batch-size: 500
    security:
      active-key-id: ${AGENT_PAYLOAD_KEY_ID}
  lifecycle:
    max-invocation-duration: 60s
    recovery-grace: 30s
    recovery-delay: 1m
    recovery-batch-size: 100
```

密钥值不进入生产配置；部署环境必须通过统一密钥入口提供与active/历史keyId对应的Secret，环境变量来源默认使用`AGENT_PAYLOAD_KEY_<KEY_ID>`命名。开发/演示环境允许的配置文件注入、source-order和生产禁用明文策略由`统一密钥管理与多注入源支持_L2实施详细设计_v1.0.md`约束。D03删除 `agent.intent-roles`；D04/D03删除旧 `agent.domains` 中的Canonical字段事实，并将纯访问/mask限制迁入 `domain-security`。

### 12.2 现有配置文件修改

- `AgentProperties.java`：删除`intentRoles`和承载Canonical field/type/operator/alias的`domains`字段及getter/setter；保留Runtime、Conversation、Query、Aggregate和Adapter调用的纯运行参数。D04若选择配置装配Canonical Metadata，必须使用其L2定义的独立Java properties类型，不能复活旧混合结构。
- `AgentServiceApplication.java`：`@EnableConfigurationProperties`同时注册`AgentProperties`、`AgentMetadataProperties`、`InvocationLifecycleProperties`；Mapper扫描覆盖`com.dylan.agent.lifecycle.persistence`和`com.dylan.agent.metadata.context.internal`，不依赖默认偶然扫描。
- `AgentConfiguration.java`：无需修改；继续唯一提供`agentRuntimeRestClient`和UTC `Clock`。D02不得创建第二个Clock/Runtime client。
- `application.yml`：由本文唯一汇总D02 metadata/context/security和D02_02 lifecycle实例配置；D02_02不再单独拥有该文件。

### 12.3 Validator

`AgentMetadataPropertiesValidator.validate(AgentMetadataProperties,CapabilityRegistry,PayloadKeyProvider)` 必须校验：bundleVersion非空、defaultProfileId精确指向一个Profile、Profile/行为资产/Policy version和精确引用、每个promptProfileRef存在且行为资产符合D01大小/locale约束、Profile及Policy全局Budget/Context TTL上限显式存在、maxTotalDuration/rows/bytes为正、repairAttempts/delegation depth/tasks非负、只收紧运算、reloadValidationTimeout在100ms～30s、Context TTL、canonical field/operator/function引用格式与内部闭合、mask类型、生产配置无明文key、active keyId可通过统一密钥入口解析为AES-256 key、无重复事实。缺失限制不得解释为无限；显式空集合只表示deny-none或不允许委派等对应受控语义。引用在D04中是否存在只由Reloader随后调用`DomainMetadataPort.validateReferences`验证，禁止Validator另走投影接口。失败拒绝整体启动/reload。

---

## 13. 缓存、错误和观测

### 13.1 缓存

只允许按精确版本缓存不可变 Profile/Policy/D04 metadata。Permission、Evidence、Snapshot、AvailableCapabilitySnapshot、ContextSnapshot/View、Binding、ExecutionScope 都是请求级，不跨 Invocation。Context 明文只在当前 Invocation 内存活。

### 13.2 安全错误码

Metadata/Context只能使用D02_02定义的`KernelErrorCode`枚举，其中本域使用：`PROFILE_INVALID`、`POLICY_INVALID`、`PERMISSION_UNAVAILABLE`、`AUTH_EVIDENCE_CHANGED`、`AUTHORIZATION_REVOKED`、`CATALOG_INCONSISTENT`、`DOMAIN_BINDING_UNAVAILABLE`、`CONTEXT_REQUIRED_MISSING`、`CONTEXT_DECRYPT_FAILED`、`CONTEXT_STALE`、`CONTEXT_WRITE_CONFLICT`、`FIELD_FORBIDDEN`、`RESULT_SECURITY_FAILED`。外部响应只暴露穷尽映射后的安全Agent error。

`FIELD_FORBIDDEN`只表示字段存在但当前ExecutionScope无权用于filter、display、group、metric或function。字段不存在、字段类型不匹配、operator/function不支持仍属于计划校验失败，不得混用该错误码。安全提示只允许列出用户请求的字段标识或安全显示名，不输出权限正文、Policy正文、UserPermission原文或未脱敏字段值。

### 13.3 指标与日志

指标：profile/policy reload、permission latency/failure、catalog size/exclusion reason、snapshot freeze/recheck、Context read/currentness/write/CAS/cleanup、binding、result filtering/mask。

日志允许 correlation/invocation/capability/domain/stage/version reference/errorCode/diagnosticId；禁止 JWT、权限表达式、Context/result payload、密钥、未授权 metadata。

### 13.4 扩展不变量

| 场景 | 只允许新增/修改 | 不得修改 |
|---|---|---|
| 同PlanKind新capability | D02_01 Registration/实现、Profile/Policy引用、测试 | Catalog/Auth/Context/Core通用算法 |
| 新Domain | D04 Canonical Catalog、AdapterRole/Registration/Adapter、纯Policy引用、下游API和装配 | Planning/Core/Handler/Validator、D02 Domain port签名 |
| 新Profile | Profile实例、Policy收紧实例、Prompt/Context/预算/Delegation引用 | Registry/Auth/Catalog算法 |
| 新Context type | agent-api payload contract、Definition声明、必要D01 RuntimeContextView subtype、显式migrator和测试 | Context读写/currentness/CAS主流程 |

只有现有Plan/Handler无法表达新语义时才新增capability或PlanKind，不能伪装成Domain/Profile配置扩展。

---

## 14. 测试设计

### 14.1 Profile/Policy/Auth

- `effectiveProfileIsOnlyProfileIntersectPolicy`
- `planningScopeIntersectsPermissionAndDelegation`
- `policyCanOnlyTighten`
- `reloadsProfileAndPolicyAsOneAtomicBundle`
- `ordinaryReloadRetainsBoundProfileAndPolicyVersionsForInFlightExecution`
- `rejectsSameProfileOrPolicyVersionWithDifferentStructure`
- `rejectsSameBehaviorAssetVersionWithDifferentInstructions`
- `neverCapturesMixedProfilePolicyVersions`
- `capturesOneEvidenceChainBeforeRoute`
- `rejectsEvidenceChangeBeforeRoutePlanOrFreeze`
- `rejectsDomainMetadataChangeDuringMetadataReload`
- `freezesCapabilitySnapshotFromSameEvidenceOnly`
- `snapshotBindsCorrelationSubjectOwnerScopeAndRegistration`
- `executionRecheckNeverExpandsSnapshot`
- `allowsUnrelatedScopeShrinkButRejectsRequiredPermissionRemoval`
- `rejectsEmergencyRevokedBoundProfileOrPolicyVersion`
- `rejectsMissingOrMultipleUserPermissionAuthorityBeans`
- `neverFallsBackToJwtRolesOrLegacyRoleConfiguration`
- `mapsAuthorityDeadlineToCancellationAndOtherFailuresToPermissionUnavailable`
- `rejectsPermissionProjectionForDifferentSubjectOrInvalidEvidence`
- `UserPermissionAuthorityContractTest`由生产Adapter模块继承/运行，验证稳定subject查询、deadline、typed failure、无JWT透传及返回投影结构；未提供该测试实现时D03投产门禁失败。

### 14.2 Catalog/D04 seam

- NONE/OPTIONAL/REQUIRED 全组合；
- unavailable capability/domain通过不投影表达；
- D04 port 缺失/重复/版本不一致 fail closed；
- metadata reload在同一D04 evidence下验证field/operator/function全部typed引用，任一悬空即不发布；
- availability→Route→Plan→Snapshot freeze必须使用同一DomainMetadataEvidence；
- 多个AdapterRole的availability来自一次原子快照，不允许逐role拼接版本；
- execution recheck/projection/binding继续使用Snapshot绑定的同一DomainMetadataEvidence；
- `rejectsDomainMetadataChangeBetweenRouteAndPlanOrFreeze`与`rejectsDomainMetadataChangeBeforeExecutionBinding`；
- 新 capability/domain 不修改 Catalog/Authorization/Core；
- Route projection无field，Plan schema只含授权字段；
- D02没有Canonical Catalog/AdapterRegistration实现或配置副本。

### 14.3 Context

- Route前不调用ContextPlanningPort；
- Owner/Scope/sourceDomain/ContractRef/TTL/required/optional读取；
- optional跨domain Context按缺失处理，required跨domain Context fail closed且绝不合并；
- currentness逐项验证correlation、Owner、scope、sourceDomain、stored/effective schema与migrator、recordVersion、readable、TTL；
- 变化时不 reload；
- payload加密且purpose/AAD隔离；
- record/scope/schema/version/purpose任一AAD绑定变化均无法解密；nonce不复用；
- active key缺失/非法拒绝启动，历史key可按密文keyId解密；
- exact-version读取、显式单跳迁移、无迁移器/歧义路径fail closed；
- expected-absent insert、expected-version update、CAS冲突；
- encryption/CAS失败使Lifecycle事务回滚；
- strict TTL和ConversationScope cleanup；
- ConversationScope retirement先独立提交不可读状态，后续物理级联失败仍不可读且可重试；
- 缺失多个候选不按时间猜latest。

### 14.4 Result Security

- 未授权字段删除、每种mask、ContractRef/projector缺失、summary重建；
- SecuredResult只暴露canonical bytes副本，projector返回的mutable DTO后续修改不影响持久化；
- projector/mask失败不返回结果/不写Context；
- 持久化输入只可能是SecuredResult。

### 14.5 Query Context 分页与字段越权

- `readsOldQueryContextV1AsV1_1WithNullTotals`：旧QUERY Context缺少total字段时可迁移或兼容读取；
- `projectsQueryPaginationTotalsToRuntimeView`：Runtime Query Context View包含total/totalExact/totalPages且不包含业务行数据；
- `doesNotProjectQueryTotalsWhenReadableFieldsExcludeThem`：readableFields收紧时不输出分页总数字段；
- `writesQueryContextTotalsOnlyAfterSuccessfulQuery`：只有成功query write才持久化total/totalPages；
- `usesFieldForbiddenOnlyForExistingUnauthorizedFields`：存在但未授权字段使用`FIELD_FORBIDDEN`，未知字段不使用该错误码。

---

## 15. 计划文件清单

除第15.1节明确位于`agent-api/src/main/java/com/dylan/agent/api/context/`外，其余新增类路径均以`agent-service/src/main/java/com/dylan/agent/`为根；测试以`agent-service/src/test/java/com/dylan/agent/`为根。每个条目对应同名独立Java文件；D02-owned范围内未列出的实现类、DTO、Mapper、配置或脚本不得在D03临时增加。D04新增文件必须由D04 L2独立列出，不能回写或复制本文事实。

### 15.1 Agent API

- `context/CapabilityContextPayload.java`
- `context/QueryCapabilityContextPayload.java`
- `context/AggregateCapabilityContextPayload.java`

`QueryCapabilityContextPayload.java`在`QUERY_CONTEXT` 1.1.0中新增`total`、`totalExact`、`totalPages`三个nullable字段；在`QUERY_CONTEXT` 1.2.0中新增`sorts`字段，缺省为空列表。对应的D01 Runtime View generated model必须由Java契约单向生成，不允许Python手写长期漂移。

### 15.2 Profile/Policy/Authorization

- `metadata/profile/model/AgentProfileDefinition.java`
- `metadata/profile/model/AgentProfileVersionKey.java`
- `metadata/profile/model/ProfileBehaviorAsset.java`
- `metadata/profile/model/ProfileBehaviorAssetRef.java`
- `metadata/profile/internal/AgentProfileRegistry.java`
- `metadata/profile/internal/ProfileBehaviorProjectionBoundary.java`
- `metadata/profile/model/EffectiveProfile.java`
- `metadata/profile/internal/EffectiveProfileCalculator.java`
- `metadata/config/AgentMetadataBundle.java`
- `metadata/config/AgentSecuritySettings.java`
- `metadata/config/AgentSecuritySettingsRegistry.java`
- `metadata/config/AgentMetadataStore.java`
- `metadata/config/AgentMetadataReloader.java`
- `metadata/config/AgentMetadataBootstrap.java`
- `metadata/config/AgentMetadataRefreshListener.java`
- `metadata/policy/model/AgentPolicySnapshot.java`
- `metadata/policy/model/ProfileConstraints.java`
- `metadata/policy/model/CapabilityConstraints.java`
- `metadata/policy/model/DomainSecurityConstraints.java`
- `metadata/policy/model/BudgetLimits.java`
- `metadata/policy/model/DelegationLimits.java`
- `metadata/policy/model/EmergencyRevocation.java`
- `metadata/policy/model/EmergencyRevocationTarget.java`
- `metadata/policy/internal/AgentPolicyConfiguration.java`
- `metadata/authorization/model/UserPermission.java`
- `metadata/authorization/port/UserPermissionAuthorityPort.java`
- `metadata/authorization/port/UserPermissionAuthorityFailure.java`
- `metadata/authorization/port/UserPermissionAuthorityException.java`
- `metadata/authorization/internal/UserPermissionBoundary.java`
- `metadata/authorization/internal/AuthorizationSecurityConfiguration.java`
- `metadata/authorization/model/DelegationConstraintRef.java`
- `metadata/authorization/model/DelegationConstraint.java`
- `metadata/authorization/internal/DelegationBoundary.java`
- `metadata/authorization/model/PlanningAuthorizationEvidence.java`
- `metadata/authorization/model/PlanningEffectiveScope.java`
- `metadata/authorization/request/PlanningSecurityRequest.java`
- `metadata/authorization/request/CapabilityScopeSelection.java`
- `metadata/authorization/model/AuthorizationSnapshot.java`
- `metadata/authorization/model/ExecutionScope.java`
- `metadata/authorization/port/AuthorizationPlanningPort.java`
- `metadata/authorization/internal/AuthorizationPlanningPortImpl.java`
- `metadata/authorization/internal/AuthorizationExecutionPortImpl.java`

### 15.3 Catalog/Domain seam

- `metadata/catalog/CapabilityCatalog.java`
- `metadata/catalog/AvailableCapability.java`
- `metadata/catalog/AvailableCapabilitySnapshot.java`
- `metadata/domain/port/DomainMetadataPort.java`
- `metadata/domain/port/CanonicalFieldRef.java`
- `metadata/domain/port/CanonicalOperatorRef.java`
- `metadata/domain/port/CanonicalFunctionRef.java`
- `metadata/domain/port/DomainMetadataReferenceSet.java`
- `metadata/domain/port/DomainAvailabilitySnapshot.java`
- `metadata/domain/port/DomainMetadataEvidence.java`
- `metadata/domain/DomainSecurityBoundary.java`
- `kernel/port/model/AdapterExecutionBinding.java`
- `kernel/port/model/DomainExecutionResolution.java`
- `kernel/port/model/DomainBindingRequest.java`
- `kernel/port/model/ExecutionFieldRule.java`
- `kernel/port/model/ExecutionValidationProjection.java`

### 15.4 Context

- `metadata/context/model/ContextRecordKey.java`
- `metadata/context/model/CapabilityContextEnvelope.java`
- `metadata/context/model/ContextSnapshot.java`
- `metadata/context/model/ContextWriteCandidate.java`
- `metadata/context/request/ContextReadRequest.java`
- `kernel/port/model/ContextApprovalRequest.java`
- `kernel/port/model/ExpectedContextVersion.java`
- `kernel/port/model/ApprovedContextWrite.java`
- `metadata/context/port/ContextPlanningPort.java`
- `metadata/context/internal/ContextBoundary.java`
- `metadata/context/internal/ContextBindingSupport.java`
- `metadata/context/internal/ContextRepository.java`
- `metadata/context/internal/ContextRecordEntity.java`
- `metadata/context/internal/ContextRecordMapper.java`
- `metadata/context/internal/ContextFinalizationParticipantImpl.java`
- `metadata/context/internal/ContextScopeRetirementParticipantImpl.java`
- `metadata/context/internal/ContextCleanupJob.java`
- `metadata/context/migration/ContextPayloadMigrator.java`
- `metadata/context/migration/ContextMigrationRegistry.java`
- `metadata/context/migration/QueryContextV1ToV1_1Migrator.java`（如ContractRegistry严格按版本校验，则新增；若采用兼容反序列化，则必须以测试证明旧payload可读）
- `metadata/crypto/model/ProtectedPayload.java`
- `metadata/crypto/model/PayloadProtectionContext.java`
- `metadata/crypto/port/ProtectedPayloadCodec.java`
- `metadata/crypto/model/PayloadPurpose.java`
- `metadata/crypto/port/PayloadKeyProvider.java`
- `metadata/crypto/internal/AeadProtectedPayloadCodec.java`
- `metadata/crypto/internal/EnvironmentPayloadKeyProvider.java`（环境变量来源兼容实现）
- `metadata/crypto/internal/PayloadJsonCodec.java`

### 15.5 Result/Config

- `kernel/port/model/SecuredResult.java`
- `metadata/result/FilteredResult.java`
- `metadata/result/ResultSecurityProjector.java`
- `metadata/result/ResultSecurityProjectorRegistry.java`
- `metadata/result/ResultSecurityBoundary.java`
- `metadata/result/QueryResultSecurityProjector.java`
- `metadata/result/AggregateResultSecurityProjector.java`
- `metadata/config/AgentMetadataProperties.java`
- `metadata/config/AgentMetadataPropertiesValidator.java`
- MODIFY `AgentProperties.java`、`AgentServiceApplication.java`、`application.yml`；KEEP `model/MaskType.java`；DELETE `model/FieldPolicy.java`；`AgentConfiguration.java`明确保持不变

### 15.6 测试文件

- `AgentProfileRegistryTest`
- `ProfileBehaviorProjectionBoundaryTest`
- `AgentPolicyConfigurationTest`
- `AgentSecuritySettingsRegistryTest`
- `AgentMetadataReloadTest`
- `AuthorizationPlanningPortTest`
- `AuthorizationExecutionPortTest`
- `UserPermissionBoundaryTest`
- `UserPermissionAuthorityWiringTest`
- `UserPermissionAuthorityContractTest`
- `CapabilityCatalogTest`
- `DomainMetadataPortContractTest`
- `ContextBoundaryTest`
- `ContextRuntimeViewTest`
- `ContextRepositoryIT`
- `ContextFinalizationIT`
- `ContextCleanupIT`
- `ContextMigrationRegistryTest`
- `QueryCapabilityContextPayloadCompatibilityTest`
- `ProtectedPayloadCodecTest`
- `PayloadKeyProviderTest`
- `PayloadJsonCodecTest`
- `ResultSecurityBoundaryTest`
- `MetadataArchitectureTest`
- `MetadataExtensionTest`

### 15.7 完整方法索引

未在下表出现的方法不得作为D03公共扩展点；record/final值对象除规范化构造器和只读访问器外无方法。

| 类/接口 | 方法 |
|---|---|
| `AgentProfileRegistry` | `getRequired(AgentProfileRef)`、`defaultRef()`、`activeProfiles()`、`activeVersion(String)`、`validateReferences(CapabilityRegistry)` |
| `ProfileBehaviorProjectionBoundary` | `project(PlanningAuthorizationEvidence)` |
| `AgentPolicyConfiguration` | `current()`、`requireVersion(String)` |
| `AgentMetadataStore` | `current()`、`compareAndSet(AgentMetadataBundle,AgentMetadataBundle)`；package-private |
| `AgentMetadataReloader` | `AgentMetadataBundle validateAndReload(AgentMetadataProperties)` |
| `AgentMetadataBootstrap` | `initialize()` |
| `AgentMetadataRefreshListener` | `onEnvironmentChange(EnvironmentChangeEvent)` |
| `AgentSecuritySettingsRegistry` | `current()` |
| `UserPermissionAuthorityPort` | `resolveCurrent(ExecutionSubjectRef, Instant)` |
| `UserPermissionAuthorityException` | `failure()`、`diagnosticId()`；cause仅内部日志使用 |
| `UserPermissionBoundary` | `resolve(ExecutionSubjectRef, Instant)` |
| `AuthorizationSecurityConfiguration` | `userPermissionBoundary(List<UserPermissionAuthorityPort>,Clock)` |
| `DelegationBoundary` | `resolve(DelegationConstraintRef, ExecutionSubjectRef, Instant)` |
| `AuthorizationPlanningPort` | `capture(PlanningSecurityRequest)`、`assertCurrent(PlanningAuthorizationEvidence)`、`freezeCapabilityScope(PlanningAuthorizationEvidence, CapabilityScopeSelection)` |
| `AuthorizationPlanningPortImpl` | 实现`capture`、`assertCurrent`、`freezeCapabilityScope`；无额外公开方法 |
| `AuthorizationExecutionPortImpl` | `recheck(AuthorizationSnapshot, InvocationHandle)` |
| `EffectiveProfileCalculator` | `compute(AgentProfileDefinition,AgentPolicySnapshot)` |
| `CapabilityCatalog` | `available(PlanningAuthorizationEvidence)` |
| `AvailableCapabilitySnapshot` | `contains(String)`、`getRequired(String)`、`capabilityIds()` |
| `DomainMetadataEvidence` | `safeRef()`及只读访问器 |
| `DomainMetadataReferenceSet` | `empty()`及只读访问器 |
| `DomainMetadataPort` | `knownRoles`、`validateReferences(DomainMetadataReferenceSet,Instant)`、`availability`、`assertCurrent`、`routeProjection`、`planSchema`、`executionProjection`、`bind`（其余签名见§7.1） |
| `ExecutionValidationProjection` | `none()`及只读访问器 |
| `DomainSecurityBoundary` | `DomainExecutionResolution resolve(DomainBindingRequest)` |
| `ContextPlanningPort` | `load(ContextReadRequest)`、`toRuntimeView(ContextSnapshot,ContextReadDeclaration,PlanningAuthorizationEvidence)` |
| `ExpectedContextVersion` | `targetVersion()`及sealed subtype只读访问器 |
| `ContextBoundary` | `load(ContextReadRequest)`、`revalidateAll(List<ContextSnapshot>,InvocationHandle,ResolvedRegistration,ExecutionScope)`、`approve(List<ContextWriteCandidate>,ContextApprovalRequest)` |
| `ContextBindingSupport` | package-private AAD binding digest与scope编解码辅助；不作为公共扩展点 |
| `ContextFinalizationParticipantImpl` | `persist(List<ApprovedContextWrite>)` |
| `ContextRepository` | `findCurrent`、`insertExpectedAbsent`、`updateExpectedVersion`、`findExact`、`markUnreadableByConversationScope`、`deleteExpired`（签名见§10.1） |
| `ContextRecordMapper` | 与Repository六个操作一一对应的MyBatis方法；参数使用typed parameter record |
| `ContextCleanupJob` | `tick()` |
| `ContextScopeRetirementParticipantImpl` | `retire(ConversationScope,Instant)`；`REQUIRES_NEW` |
| `ContextPayloadMigrator` | `source()`、`sourceType()`、`target()`、`targetType()`、`migrate(S)` |
| `ContextMigrationRegistry` | `resolve(ContractRef,ContractRef)`、`validateNoAmbiguousPathOrCycle()` |
| `QueryContextV1ToV1_1Migrator` | `source()`、`sourceType()`、`target()`、`targetType()`、`migrate(QueryCapabilityContextPayload)`；仅在严格版本迁移方案下新增 |
| `ProtectedPayloadCodec` | `encrypt(byte[],PayloadProtectionContext)`、`decrypt(ProtectedPayload,PayloadProtectionContext)` |
| `PayloadKeyProvider` | `requireKey(String)` |
| `AeadProtectedPayloadCodec` | 实现`encrypt`、`decrypt`；无额外公开方法 |
| `EnvironmentPayloadKeyProvider` | 实现`requireKey`；仅作为环境变量来源兼容实现 |
| `PayloadJsonCodec` | `serialize(Object,Class<?>)`、`deserialize(byte[],Class<T>)` |
| `SecuredResult` | `canonicalPayloadCopy()`及其余只读访问器 |
| `ResultSecurityProjector` | `supports()`、`filter(O,ExecutionScope)` |
| `ResultSecurityProjectorRegistry` | `getRequired(ContractRef)`、`validateUniqueCoverage(Set<ContractRef>)` |
| `ResultSecurityBoundary` | `secure(Object,ContractRef,ExecutionScope)` |
| `AgentMetadataPropertiesValidator` | `validate(AgentMetadataProperties,CapabilityRegistry,PayloadKeyProvider)` |

以上均为D03/D04计划变更；D02只评审本文。Canonical Catalog、DomainFieldCatalog、AdapterRole/Registration及具体domain数据不在此清单。

---

## 16. 验收标准与结论

1. Effective Profile不混入User Permission；Planning Scope才与Permission/Delegation求交。
2. Route前只捕获一次证据链，capability Snapshot在Plan后从同一证据冻结。
3. Snapshot完整绑定correlation、subject、Owner、Scope、Registration及版本链。
4. Catalog无capability/domain专用分支，不可用项不投影。
5. D02只定义D04消费端口，不实现Canonical Metadata或平行Runtime DTO。
6. Context Snapshot字段、currentness、strict TTL、加密、expected-version CAS和scope cleanup完整。
7. Context版本只通过Java迁移器显式升级，无latest猜测、脚本或Prompt修补。
8. Handler不能控制Owner/Scope/expiry；Lifecycle只能持久化ApprovedContextWrite。
9. ResultSecurity按ContractRef唯一解析projector，summary不能绕过过滤。
10. 配置只保存实例/策略，不复制Java结构和D04 metadata事实。
11. 外部 User Permission 只经唯一 Java SPI 解析；零/多生产实现、JWT/旧角色配置兜底和权威源不可用均 fail closed。
12. 类、方法、配置、DDL、测试和错误/观测均已列出；外部 Adapter 的具体传输实现由已评审的权威系统协议决定，并受 D03 投产门禁约束，不属于 D02 事实源。

最终评审结论（2026-06-30）：本文已与D02_00、D02_01、D02_02及上级L1交叉复审；两阶段授权、Catalog、D04 seam、Context生命周期、Result Security、配置与可落地性完整闭合，当前文档基线下无未决问题。D01退出后的Runtime投影类型复核、D04实现评审和唯一User Permission生产Adapter契约测试仍是后续生效/投产门禁，均已显式登记而非以JWT或本地配置兜底。
