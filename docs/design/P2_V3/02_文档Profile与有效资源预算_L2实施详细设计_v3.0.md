# 文档 Profile 与有效资源预算 L2 实施详细设计 v3.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 文档 Profile 与有效资源预算 L2 实施详细设计 |
| 文档路径 | `docs/design/P2_V3/02_文档Profile与有效资源预算_L2实施详细设计_v3.0.md` |
| 文档状态 | In Review |
| 当前版本 | v3.0 |
| 创建/最后更新日期 | 2026-07-13 |
| 适用代码基线 | `816e2c855574da5326379128bfb3e230241d2fe3` |
| 设计层级 | L2 Document Profile、Planning 安全投影与 capability resource contract |
| 上级文档 | 四份当前 L0/L1；只读权威基线 |
| 直接前置 | P1_V2/01～06、P2_V3/00～01 |
| 关联文档 | P2_V3/03～07 |
| 合并来源 | P2/02、P2_V2/02，以及旧 P2/P2_V2 各专题中的 Document 业务资源上限 |
| 是否可作为实现依据 | 否；P2_V3 全集评审已完成且 S0/S1=0，但仍为 In Review；公共契约、配置切换和跨模块原子迁移经 M0 授权后方可实施 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | 多层分别读取配置导致预算不一致 | 将 domain/materialType/profile 与检索、evidence、generation 上限收敛为 typed `DocumentResourceLimit` |
| 2 | 2026-07-13 | 全文 | P2_V3 改为自包含基线 | 完整承接 P2/02、P2_V2/02 及旧专题散落预算，旧文档不再作为字段或缺省值来源 |
| 3 | 2026-07-13 | 全文 | 第一轮 cross-layer 评审发现 Profile 侵占 index/provider/rollout 所有权、资源限额混入 timeout/attempt、选择时序晚于 Runtime Plan、`ResolvedDocumentExecutionConfig` 侵入 P1 Context、Profile 独立 currentness 和请求收窄语义不闭合 | 重写为 exact AgentProfile 子资产、Pre-Plan server-origin 投影、单 Document ContractRef、P1 唯一 resolver 和明确的配置迁移矩阵 |
| 4 | 2026-07-13 | 10.1～10.4、10.9、14、22～24 | 第二轮复审发现“先选子 Profile、再由子 Profile 生成 PROFILE contribution”会与 P1 `AgentProfileDefinition` 已持有 typed contribution 形成环形依赖和双预算来源 | 改为 exact Agent Profile 的 capability-specific typed PROFILE contribution 先持有唯一数值 upper bound，其 evidenceRef 引用只含策略的 Document child asset；选择结果只校验 evidence/binding，不另造预算 |
| 5 | 2026-07-13 | 9、10.3、10.6～10.11、11、19～24 | 第三轮复审发现 Policy child 引用时序、Execution 最小投影字段以及 feature policy 与数值 0 的联合门禁仍不够明确 | 冻结 capture/selection/freeze 的无环时序、`DocumentExecutionProfileProjection` 具体结构和双门禁规则，补齐接口/落点/测试 |
| 6 | 2026-07-13 | 9、10.3、10.5～10.6、10.9、11、19、22～24 | 第四轮复审发现总体图仍把 contribution 形成放在 Profile selection 之后，且 eligibility validator 返回的新 projection 与 selection 内旧 projection 可能形成双对象错配 | 重排为 capture contributions→Route→selection→freeze→单次 projector，assembler 显式接收最终 projection；复审无 S0/S1 |
| 7 | 2026-07-13 | 10.5～10.6、10.8、19～24 | 第五轮关联复审发现 Execution projection 将 feature 压缩为 boolean 且遗漏 requiredChannels，Handler 无法区分 required failure 与 optional degradation | Execution projection 保留 closed `DocumentFeaturePolicy` 与 required channel 子集；OPTIONAL+0 仍在 Planning 转 DISABLED，REQUIRED+0 仍拒绝；复审无 S0/S1 |
| 8 | 2026-07-13 | 1、20、23～24 | P1_V2/P2_V3 全集终检同步模块名与终态 | 验收命令改用 `document-provider-adapter`，标记全集评审完成并保留 M0 实施边界；不新增评审轮次 |

## 3. 文档状态说明

本文处于 In Review，不授权修改公共请求契约、`AgentProfileDefinition`、`AgentPolicySnapshot`、P1 Core Context、配置中心、Provider 配置或生产数据。本文只冻结 Document capability 在 P1 已定义扩展缝隙上的具体类型、选择规则、贡献适配和消费约束。

本文是 P2_V3 中 Document Profile、Planning 安全投影和 Document 业务资源预算的唯一专题规范。旧 P2/P2_V2 仅保留 provenance；其中的 `indexAlias/schemaVersion/provider/model/timeout/qualityGate` Profile 字段、消费者散预算和 `ResolvedDocumentExecutionConfig` 不再属于目标设计。

## 4. 背景与目标

当前代码和旧设计把三类不同事实混在 `AgentProperties.Document` 与 `DocumentRetrievalProfile` 中：

- 检索策略：通道、权重、RRF、去重、上下文和可选增强；
- 基础设施事实：index alias、schema、embedding model/dimension、Provider endpoint/timeout；
- 业务资源上限：候选、证据、上下文、回答、摘要和结果字节数。

这会使 Profile 变成第二个 Corpus Catalog、Provider 配置中心和质量发布门禁，也会让 Validator、Handler、Provider 与 Result Security 分别读取不同上限。目标是：

1. Route 选定 capability/domain 后、Runtime Plan 前，由 Java 从 exact AgentProfile/Policy evidence 中选择一个不可变 Document Profile；
2. Profile 只拥有允许集合、feature policy 和确定性算法参数，不拥有索引、Provider transport 或 rollout 事实；
3. Document 业务资源统一为一个强类型 ContractRef，由 P1 `CapabilityResourceLimitResolver` 对 Definition/Profile/Policy/Permission/optional Request 单调求交并冻结；
4. Runtime Plan 不能覆盖 Profile 或 Effective limits，Execution 不重读配置；
5. Future Multi-Agent 只增加 P1 上层 contribution/binding source，不修改本专题 Profile、Contract 或消费者接口。

## 5. 设计范围

### 5.1 范围内

- `DocumentProfileSet`、`DocumentRetrievalProfile`、exact version 引用和选择规则；
- Document Profile 与 AgentProfile/Policy candidate 的原子引用闭合；
- `DocumentPlanningProfileProjection`、`DocumentProfileBinding`、`DocumentRawPlanAssembler`；
- `DocumentResourceLimit`、稳定 dimensions、ContractRef、intersection、strictness 和 canonical digest；
- PROFILE/POLICY/PERMISSION/optional REQUEST 的 contract-specific contribution 适配；
- document.search/answer/summarize Definition、消费者维度和启动/reload gate；
- 当前配置到 01/02/03/06/07 唯一所有者的迁移矩阵；
- 实现落点、测试、静态架构门禁和回滚边界。

### 5.2 范围外

- CorpusKey 到 read alias/schema、physical index、vector manifest 和索引生命周期，归 P2_V3/01；
- Document ACL scope、protected filter、撤权/currentness 和 `SafeDocumentCandidate`，归 P2_V3/03；
- 检索 DSL、RRF/dedup/context 算法执行与 Handler 总编排，归 P2_V3/04；
- evidence/citation/fallback/Result Security 具体规则，归 P2_V3/05；
- Provider endpoint/model/credential、stage cap、一次 attempt 和 typed client，归 P2_V3/06；
- Gold Query、quality gate、rollout/rollback/audit/reconciliation，归 P2_V3/07；
- 修改 P1 resolver、Authorization Snapshot、ExecutionValidationContext、ExecutionContext、PAI-1 或 Runtime wire contract。

## 6. 上级文档约束

| 上级文档 | 本文必须落实的约束 |
|---|---|
| `Agent目标架构总览_v1.0.md` | 当前只实现单 Agent；Profile/limit 必须绑定 owner/scope/version，Future Multi-Agent 不以 Document 特例侵入执行内核 |
| `Agent契约与规划架构设计_v1.0.md` | Runtime 只负责 Route/Plan；Java 类型、ContractRef、严格反序列化和 PAI-1 是权威，Runtime 输出不是授权或资源事实 |
| `Agent能力执行内核架构设计_v1.0.md` | Core 只消费 Registration/Validator/Handler seam，不认识 Document Profile 字段，不增加第二执行配置或状态机 |
| `Agent元数据与上下文安全架构设计_v1.0.md` | Profile/Policy/Permission 必须精确版本、失败封闭、单调收紧；Context 不保存 Profile 正文或权限正文 |

P1_V2/03 与 P1_V2/05 已进一步冻结：一个 selected capability 只绑定一个 resource limit ContractRef；PROFILE/POLICY/PERMISSION 各恰好一个 typed contribution，REQUEST 可选；只有 P1 resolver 能形成 `EffectiveCapabilityResourceLimits`。本文不得复制或改写该算法。

## 7. 关联文档与边界

| 文档 | 向本文提供 | 本文向其提供 | 禁止重叠 |
|---|---|---|---|
| P1_V2/01 | `ContractRef`、Java schema/enum/canonical 规则 | `DocumentResourceLimit` ContractRef/type 注册项 | 本文不新增 Runtime Plan wire 字段 |
| P1_V2/02 | Registration、Planning Artifact、Validation/Execution Context seam | server-origin Raw Plan profile binding | 不向 P1 Context 增加 Document 字段 |
| P1_V2/03 | exact AgentProfile/Policy/Permission evidence、currentness | Document Profile/Policy 子资产闭合和 typed contributions | 不建立独立 latest/currentness port |
| P1_V2/05 | resource declaration/contract/resolver/view/reference | Document contract、dimensions、contribution adapters、consumer declarations | 不创建第二 resolver 或多 Contract 容器 |
| P2_V3/00 | 七专题所有权、Pre-Plan 时序、Raw Plan 本地绑定 | 02 的可实施细化 | 专题不得反转 00 的依赖方向 |
| P2_V3/01 | `DocumentCorpusKey`、Corpus Catalog、read target contract | bounded allowed corpus keys | Profile 不保存 alias/schema/vector manifest |
| P2_V3/03 | current Permission/ACL evidence | limits reference 和已验证 profile/corpus 范围 | Profile 不保存 ACL 表达式；02 不编译 protected filter |
| P2_V3/04 | `DocumentAgentPlan`、Validator/Handler 消费点 | `DocumentRawPlan`、Planning/Execution profile projection、typed limit | 04 不重选 Profile、不读取 Profile 配置 |
| P2_V3/05 | evidence/output consumer 语义 | evidence/output limit dimensions | 02 不实现 citation/fallback/projector |
| P2_V3/06 | operation transport 与 operational caps | enhancement/output limit dimensions、feature policy | Profile 不保存 endpoint/model/credential/timeout |
| P2_V3/07 | rollout/gate/audit 所有权 | profileVersion/limit safe reference | Profile 不保存 quality gate；02 不决定发布 |

冲突优先级：L0/L1 > P1_V2 > P2_V3/00 > 本文。若实现需要修改上级文档或 P1 seam，必须停止实施并单独申请授权；不得在本文中隐式扩展。

## 8. 设计边界与不变量

| 不变量 | 约束 |
|---|---|
| Pre-Plan 选择 | Document Profile 必须在 Route 已选 capability/domain 后、Runtime Plan 前由 Java 选择 |
| exact parent | Profile 子资产必须绑定 exact `AgentProfileRef`；Policy narrowing 必须绑定 exact policyVersion |
| 无独立 currentness | 不存在 Document Profile latest 指针、active version、热更新端口或独立撤销源 |
| 单 Contract | document.search/answer/summarize 各自只声明 `DocumentResourceLimit@1.0.0` 一个 ContractRef |
| 唯一 resolver | 02 只生成 typed contribution；P1 `CapabilityResourceLimitResolver` 唯一求交、冻结和 recheck |
| server-origin | Profile projection/binding 无 JSON 反序列化入口，不能由 Runtime、请求或 Provider 构造 |
| 单一索引事实 | Profile 只产生 `DocumentCorpusKey` allowlist；alias/schema/physical index 只由 01 解析 |
| 预算分层 | 业务资源上限进入 typed limit；absolute deadline 属于 P1；Provider timeout/bulkhead/response cap 属于 06 operational cap |
| 单调请求 | request 只能减少允许集合、禁用 optional feature 或降低数值；不能启用、增加或替换权威事实 |
| 同源消费 | Validator、Handler、Adapter/Provider 和 Result Security 必须使用同一 ContractRef/type/digest/binding |
| 无第二 Context | 不创建 `ResolvedDocumentExecutionConfig`，不向 Execution Context/Context Snapshot 加 Profile 正文 |
| 失败封闭 | 缺失、重复、版本错配、digest 错配、集合为空、request 放大或 consumer coverage 不全均拒绝 |

## 9. 总体设计

~~~text
P1 capture exact AgentProfile/Policy/Permission evidence
  -> PROFILE/POLICY/PERMISSION typed contributions + child evidence refs
  -> Route selected capability/domain
  -> DocumentRetrievalProfileResolver selects one immutable strategy Profile
  -> optional REQUEST contribution factory
  -> P1 freezeCapabilityScope / CapabilityResourceLimitResolver (the only resolver)
       EffectiveCapabilityResourceLimits + ResourceLimitReference
  -> DocumentPlanningProfileProjector
       applies caller-safe set/feature narrowing
       applies required/optional/zero dual gate
       produces the only final DocumentPlanningProfileProjection
  -> Runtime Plan (wire remains DocumentAgentPlan)
  -> package-private DocumentRawPlanAssembler
       runtime plan + final server profile projection + trusted binding
  -> PAI-1 / DocumentPlanValidator
  -> ValidatedDocumentPlan with minimal execution profile projection
  -> Handler / Provider / Result Security consume the same limits view
~~~

Profile selection、resource resolution 和 projection 是三个相邻但单向的责任：Profile resolver 不调用 P1 resource resolver；contribution adapters 不选择 Profile；P1 resolver 不投影策略；projector 只读取 selection 与已冻结 Effective value，不求交、不改值、不创建第二 resolver；Runtime Plan 四者都不做。

## 10. 详细功能设计

### 10.1 exact AgentProfile 子资产与原子发布

`DocumentProfileSet` 是 exact `AgentProfileRef(agentId, expectedVersion)` 的 capability-specific immutable child asset，不是独立配置产品。所属 `AgentProfileDefinition` 已按 P1_V2/03/05 为每个启用的 Document capability 持有唯一 typed PROFILE contribution；该 contribution 的 `evidenceRef` 引用本文的 child asset，形式为受校验的 `DocumentProfileAssetRef(agentProfileRef, documentProfileVersion, assetDigest)`。不得使用自由 URL、Map 或仅含 profileName 的弱引用。

数值 upper bound 只存在于 parent Agent Profile 的 typed contribution；`DocumentProfileSet` 不再保存第二份 `DocumentResourceLimit`。因此解析 child asset 不依赖“先选 Profile 才能生成 PROFILE contribution”，选择算法也不能按 profileName 偷换数值预算。确需不同业务预算时应使用不同 Agent Profile version、Policy/Permission 或 caller request narrowing，而不是在同一 child asset 内复制 resource source。

一个 metadata candidate 的可见性规则固定为：

1. 构建 immutable `DocumentProfileSet` 与 exact `DocumentPolicyConstraint`；
2. 校验 Profile/Policy/Definition/Contract/Domain Metadata/Corpus Catalog 引用闭合；
3. 校验能为每个启用的 Document capability 形成完整 PROFILE/POLICY contribution；
4. 将 child asset ref 写入所属 exact Agent Profile/Policy candidate evidence；
5. P1 metadata candidate 仅在全部校验通过后一次发布 active parent version。

实现可以先 stage immutable child asset，再切换 P1 parent candidate；但同一 key 只能 put-if-absent 且 digest 相同，child asset 没有 active/latest 指针。未被 parent exact ref 引用的 staged asset 对 Planning 不可见。这样既不把 Document 字段硬编码进 P1 Core，也不会形成两个可独立切换的 currentness 源。

`documentProfileVersion` 是内容版本，用于 canonical/audit；currentness 仍由 parent exact AgentProfileRef 和 policyVersion 决定。已有 Invocation 绑定旧 exact parent 时继续读取旧 immutable child；parent 失效、引用缺失或 digest 错配时由 P1 currentness/recheck 整体 fail closed。

### 10.2 Profile 权威类型与字段所有权

~~~java
public record DocumentProfileSet(
    AgentProfileRef ownerProfileRef,
    String documentProfileVersion,
    List<DocumentRetrievalProfile> profiles) {}

public record DocumentRetrievalProfile(
    String domain,
    String profileName,
    boolean defaultProfile,
    Set<String> allowedMaterialTypes,
    Set<DocumentOperation> allowedOperations,
    Set<DocumentRetrievalChannel> allowedChannels,
    Set<DocumentRetrievalChannel> requiredChannels,
    Map<DocumentRetrievalChannel, Integer> channelWeights,
    DocumentFusionPolicy fusionPolicy,
    DocumentDedupPolicy dedupPolicy,
    DocumentContextPolicy contextPolicy,
    DocumentFeaturePolicy rewritePolicy,
    DocumentFeaturePolicy embeddingPolicy,
    DocumentFeaturePolicy rerankPolicy,
    Map<DocumentOperation, DocumentFeaturePolicy> generationPolicy,
    Set<CanonicalFieldRef> searchableFields,
    Set<CanonicalFieldRef> returnableFields) {}

public enum DocumentFeaturePolicy {
    DISABLED, OPTIONAL, REQUIRED
}
~~~

字段语义：

- `domain/profileName` 是稳定选择键；`profileName` 只在所属 Agent Profile 与 domain 内唯一；
- `allowedMaterialTypes` 映射为有界 `DocumentCorpusKey(domain, materialType)` 集合；一次 Validated Plan 最终只能选择其中一个 CorpusKey；
- `allowedChannels/requiredChannels/weights` 与 fusion/dedup/context 是 04 执行的确定性策略参数；required 必须是 allowed 子集；
- rewrite/embedding/rerank/generation 只声明 `DISABLED/OPTIONAL/REQUIRED`，不声明 endpoint/model/timeout/credential；
- searchable/returnable fields 只能是 P1 Domain Metadata 与 01 schema contract 均支持的 `CanonicalFieldRef` 子集；
- parent Agent Profile 的 typed PROFILE contribution 提供数值 upper bound；Profile child 只提供策略，二者由同一 evidenceRef/asset digest 闭合。

Profile 明确禁止保存：`readAlias`、`physicalIndex`、`schemaVersion`、analyzer/vector manifest、embedding/generation/rerank provider/model/dimension、endpoint、credential、connect/read timeout、retry/attempt、ACL expression、permission/mask 正文、Gold Query、quality gate、rollout state 或 emergency control state。

### 10.3 Policy narrowing 与选择算法

Policy 只通过 exact policyVersion 下的 `DocumentPolicyConstraint` 收紧 Profile。与 PROFILE 相同，P1 capture 阶段已形成 capability-specific typed POLICY contribution，其 evidenceRef 精确引用 Policy child constraint；Profile resolver 只解析该已捕获 evidence，不读取 current/latest Policy：

~~~java
public record DocumentPolicyConstraint(
    String policyVersion,
    Map<String, Set<String>> allowedProfileNamesByDomain,
    Map<String, Set<DocumentRetrievalChannel>> allowedChannelsByDomain,
    Map<String, Set<DocumentOperation>> allowedOperationsByDomain) {}
~~~

它与 P1 `AgentPolicySnapshot` 同 candidate 发布，不包含 Profile 正文、索引、Provider 或 ACL。对于 P1 已允许的 Document domain/capability，Policy 必须显式给出非空 allowlist；不使用 `*`、空集合代表全部或 resolver 自填全部。

`DocumentRetrievalProfileResolver.select(...)` 的受控输入固定为：selected capabilityId/domain、exact AgentProfileRef、exact policyVersion、PlanningAuthorizationEvidence、Java 已校验的 optional requestedProfile/materialType 与 request set narrowing。算法固定为：

1. 使用 parent exact ref 解析唯一 `DocumentProfileSet`，核对 asset ref、version、digest 和 metadata evidence；
2. 取 selected domain 下 enabled profiles，并与 Policy allowed profile names、allowed operation 求交；
3. caller 提供 requestedProfile 时，只能精确选择求交后的同名 profile；不存在或不允许即拒绝，不回退 default；
4. caller 未提供 requestedProfile 时，只能选择 domain 下唯一 `defaultProfile=true` 且 Policy 允许的 profile；零个或多个均拒绝；
5. caller 提供 materialType 时，所选 profile 必须允许它，并将 allowed corpus 集合收窄为该一个 CorpusKey；未提供时保留 profile 的有界 allowed corpus 集合；
6. 将 exact `DocumentPolicyConstraint` 与 Java 已校验的 caller narrowing 作为 selection 的受控输入绑定；本步骤不生成第二份 narrowed Profile；
7. 只生成 immutable `DocumentProfileSelection`；最终 channels/operations/features/corpora 子集必须等待 P1 freeze 后由 10.5 的 projector 一次生成。

无环时序固定为：P1 capture 先从 exact Agent Profile/Policy candidate 取得 typed PROFILE/POLICY contributions 与 child evidence refs；Route 再确定 capability/domain；Document resolver 只使用已捕获 refs 选择策略 child；P1 freeze 使用 capture 中已存在的数值 contributions。selected profileName 不反向改变 PROFILE/POLICY upper bound，freeze 也不重新选择 Profile。

不得根据 materialType 自动猜另一个 Profile，不得在 explicit requestedProfile 失败时选 default，不得使用 Runtime echo、索引 alias 或 Provider availability 参与 Profile 选择。requestedProfile 是用户偏好输入而非授权事实；授权性来自 exact Profile/Policy/Permission evidence。

### 10.4 default、版本和 candidate 校验

每个 exact Agent Profile 的每个 Document domain 必须恰好一个 default Profile。Profile 可以支持多个 materialType，但每个 allowed `(domain, materialType)` 必须能在 01 Corpus Catalog 中解析，且一个 hybrid request 只能落到一个 physical target。

canonical form 使用 `DPROFILE-1` 前缀，包含 owner exact AgentProfileRef 和所有 Profile 策略字段，并按 domain/profileName、enum value、CanonicalFieldRef、materialType 和 map key 稳定排序。数值 upper bound 使用 `DLRL-1` 独立 canonical form 并由 parent PROFILE contribution digest 覆盖；两者均进入 metadata candidate digest 与 evidence binding，但不得互相复制。`documentProfileVersion = "dp1-" + SHA-256(lowercase hex)`；不得截断为 8 字节、使用 reload 序号、`hashCode`、`toString` 或 YAML 原始文本 hash。

启动/reload candidate 必须校验：

- exact owner/profile/policy 引用闭合且无同 key 异 digest；
- domain/profileName 唯一，每 domain 一个 default，Policy 未排除已允许 domain 的 default；
- materialTypes/operations/channels 非空，required 是 allowed 子集，weights 为正整数且只覆盖 allowed channels；
- searchable/returnable fields 是 Domain Metadata 与 schema 的交集子集；
- REQUIRED feature 的 parent PROFILE contribution 相应 dimensions 大于 0；DISABLED feature 由 projection 明确禁止，即使数值 upper bound 大于 0 也不能启用；任一最终 Effective dimension 为 0 时同样禁止消费；
- SEARCH 不允许 generation，ANSWER/SUMMARIZE 的生成策略与 output limits 一致；
- Profile/Policy/Permission adapters、Definition declaration、Contract、consumer declarations 和 Result projector coverage 全部闭合。

任一失败拒绝整个 metadata/composition candidate；不得只禁用坏 Profile 后发布，也不得保留旧散字段 fallback。旧 active candidate 可以继续服务其既有 exact Invocation，但新 candidate 不部分生效。

### 10.5 Planning 最小投影与 request narrowing

~~~java
public record DocumentProfileSelection(
    DocumentProfileAssetRef assetRef,
    String selectedProfileName,
    DocumentRetrievalProfile selectedProfile,
    DocumentPolicyConstraint policyConstraint,
    String selectionDigest) {}

public record DocumentPlanningProfileProjection(
    String domain,
    String profileName,
    String documentProfileVersion,
    List<DocumentCorpusKey> allowedCorpora,
    Set<DocumentOperation> allowedOperations,
    Set<DocumentRetrievalChannel> allowedChannels,
    Set<DocumentRetrievalChannel> requiredChannels,
    Map<DocumentRetrievalChannel, Integer> channelWeights,
    DocumentFusionPolicy fusionPolicy,
    DocumentDedupPolicy dedupPolicy,
    DocumentContextPolicy contextPolicy,
    DocumentFeaturePolicy rewritePolicy,
    DocumentFeaturePolicy embeddingPolicy,
    DocumentFeaturePolicy rerankPolicy,
    DocumentFeaturePolicy generationPolicy,
    Set<CanonicalFieldRef> searchableFields,
    Set<CanonicalFieldRef> returnableFields) {}
~~~

`DocumentProfileSelection` 是 server-internal 对已选 immutable strategy 的引用/值，不进入 Runtime、Context、checkpoint 或 audit。P1 freeze 完成后，`DocumentPlanningProfileProjector.project(selection, callerSetNarrowing, effectiveLimits, selectedCapabilityId)` 一次性应用 Policy/caller 集合收窄和 10.8 feature/limit 双门禁，生成唯一 final projection；不得同时保留“pre-limit projection”和“eligible projection”供后续任选。

final projection 只存在于 agent-service Planning 内存，不新增 `PlanRequest` wire 字段，也不发送给 Runtime。它不含 Agent Profile/Policy/Permission 正文、resource typed value、alias/schema/physical target 或 Provider 配置。

caller-safe narrowing 分两类：

| 类型 | 允许字段 | 冻结位置 |
|---|---|---|
| set/feature narrowing | requestedProfile、optional materialType、禁用 optional channel、禁用 optional rewrite/embedding/rerank/generation | 应用于 Planning Profile projection，进入 selection/projection digest |
| numeric resource narrowing | 更小的返回文档、候选、evidence/context/output 等公共契约明确字段 | 形成 optional REQUEST typed contribution，进入 Effective limit digest |

caller 不能指定/修改：required channel/feature、字段 allowlist、算法参数、Corpus alias/schema、Provider/model、ACL、timeout/deadline、attempt、quality gate 或任何未在 Java 公共请求契约声明的自由属性。Runtime Plan 中出现 profileName/materialType 时只作为 untrusted echo；Validator 必须与 server selection 一致，不能触发重选。

### 10.6 Raw Plan 本地绑定与 Execution 投影

Runtime 返回严格解析的 `DocumentAgentPlan` 后，PlanningService 只能调用 package-private `DocumentRawPlanAssembler`：

~~~java
final class DocumentRawPlanAssembler {
    DocumentRawPlan assemble(
        DocumentAgentPlan runtimePlan,
        DocumentProfileSelection selection,
        DocumentPlanningProfileProjection finalProfileProjection,
        ResourceLimitReference limitReference,
        PlanningBindingIdentity bindingIdentity);
}

public record DocumentProfileBinding(
    String invocationId,
    String requestCorrelationId,
    String registrationIdentity,
    AgentProfileRef agentProfileRef,
    String documentProfileVersion,
    ResourceLimitReference resourceLimitReference,
    String profileProjectionDigest) {}

public record DocumentRawPlan(
    DocumentAgentPlan runtimePlan,
    DocumentProfileBinding profileBinding,
    DocumentPlanningProfileProjection serverProfileProjection) {}

public record DocumentExecutionProfileProjection(
    String profileName,
    String documentProfileVersion,
    String profileProjectionDigest,
    DocumentCorpusKey selectedCorpus,
    DocumentOperation operation,
    Set<DocumentRetrievalChannel> enabledChannels,
    Set<DocumentRetrievalChannel> requiredChannels,
    Map<DocumentRetrievalChannel, Integer> channelWeights,
    DocumentFusionPolicy fusionPolicy,
    DocumentDedupPolicy dedupPolicy,
    DocumentContextPolicy contextPolicy,
    DocumentFeaturePolicy rewritePolicy,
    DocumentFeaturePolicy embeddingPolicy,
    DocumentFeaturePolicy rerankPolicy,
    DocumentFeaturePolicy generationPolicy,
    Set<CanonicalFieldRef> searchableFields,
    Set<CanonicalFieldRef> returnableFields) {}
~~~

assembler 必须核对 `finalProfileProjection.profileName/version` 与 selection 一致，并只对 final projection 计算/写入 binding digest。`DocumentProfileBinding` 构造入口和 assembler 均不对 JSON/Jackson 开放；Runtime response、Controller DTO、Provider payload 和测试 fixture 不能直接构造 trusted projection。`DocumentRawPlan` canonical form 同时覆盖 runtime plan canonical digest、完整 binding 和 final projection canonical digest，并进入 P1 PAI-1；它不是第二 Planning Artifact。

Execution 时 `DocumentPlanValidator` 只结合 `DocumentRawPlan`、`ExecutionValidationContext.domainProjection()` 和 `resourceLimits().require(DocumentResourceLimit...)` 校验，输出包含上述最小 `DocumentExecutionProfileProjection` 与具体操作参数的 `ValidatedDocumentPlan`。`selectedCorpus` 必须是 Planning allowedCorpora 中单一成员；`enabledChannels/fields/features` 必须是 server projection 子集且满足 Effective limits；`requiredChannels` 必须是 enabled 子集并原样保留 required/optional 语义。四个 feature policy 不能压缩为 boolean：Handler 必须据其区分 REQUIRED 失败拒绝、OPTIONAL 失败确定性降级和 DISABLED 禁止调用。投影不携带 alias/physical target、Provider、权限正文或 source contributions。Handler 只接收 Validated Plan/Execution Context；不重读 Profile/Policy/Permission/config，也不创建 `ResolvedDocumentExecutionConfig` 或新的 Context 字段。

### 10.7 DocumentResourceLimit 权威类型

`DocumentResourceLimit` 位于 Spring-free `agent-adapter-api`，使 Validator、Document Adapter、Provider port 和 Result Security 能依赖同一 typed value，而不形成 `agent-adapter-api -> agent-service` 反向依赖。嵌套 record 只用于值分组，不是额外 Contract、resolver 或持久化层。

~~~java
public record DocumentResourceLimit(
    DocumentInputLimit input,
    DocumentRetrievalLimit retrieval,
    DocumentEnhancementLimit enhancement,
    DocumentEvidenceOutputLimit output)
    implements CapabilityResourceLimit {}

public record DocumentInputLimit(
    int maxQueryChars,
    int maxCallerFilterCount) {}

public record DocumentRetrievalLimit(
    int maxChannelCount,
    int maxCandidatesPerChannel,
    int maxFusedCandidates,
    int maxChunksPerDocument,
    int maxReturnedDocuments) {}

public record DocumentEnhancementLimit(
    int maxRewriteCandidates,
    int maxEmbeddingTexts,
    int maxEmbeddingDimensions,
    int maxRerankCandidates) {}

public record DocumentEvidenceOutputLimit(
    int maxEvidenceCount,
    int maxEvidenceChars,
    int maxSnippetChars,
    int maxContextChars,
    int maxCitationCount,
    int maxGeneratedChars,
    int maxSummaryChars,
    int maxSummaryBullets,
    long maxResultBytes) {}
~~~

稳定 dimension ID 与语义：

| 分组 | dimension | 语义 |
|---|---|---|
| input | `document.input.query-chars` | 原始查询字符上限；不含 Provider 返回文本 |
| input | `document.input.caller-filter-count` | caller 业务过滤条件数；不把 03 protected filter 偷算为 caller 输入 |
| retrieval | `document.retrieval.channel-count` | 本次实际启用通道数 |
| retrieval | `document.retrieval.candidates-per-channel` | 单通道返回候选上限 |
| retrieval | `document.retrieval.fused-candidates` | RRF 后进入去重的候选上限 |
| retrieval | `document.retrieval.chunks-per-document` | 单文档保留 chunk 上限 |
| retrieval | `document.retrieval.returned-documents` | 最终 Document 结果/证据文档数上限 |
| enhancement | `document.enhancement.rewrite-candidates` | original query 之外的 rewrite 候选数；0 为禁用 |
| enhancement | `document.enhancement.embedding-texts` | 单 embedding operation 文本数；0 为禁用 |
| enhancement | `document.enhancement.embedding-dimensions` | 返回向量维度上限；0 为禁用 |
| enhancement | `document.enhancement.rerank-candidates` | rerank 输入候选数；0 为禁用 |
| output | `document.output.evidence-count` | evidence item 总数 |
| output | `document.output.evidence-chars` | evidence 文本总字符数 |
| output | `document.output.snippet-chars` | 单 snippet 字符数 |
| output | `document.output.context-chars` | generation context package 总字符数 |
| output | `document.output.citation-count` | citation 总数 |
| output | `document.output.generated-chars` | answer/generation 候选字符数；0 为禁用 |
| output | `document.output.summary-chars` | summary 字符数；0 为禁用 |
| output | `document.output.summary-bullets` | summary bullet 数；0 为禁用 |
| output | `document.output.result-bytes` | 最终序列化安全结果字节数 |

结构必需维度 `maxQueryChars/maxChannelCount/maxCandidatesPerChannel/maxFusedCandidates/maxChunksPerDocument/maxReturnedDocuments/maxEvidenceCount/maxEvidenceChars/maxSnippetChars/maxResultBytes` 必须为正。caller filter 和可选 enhancement/generation/summary 维度可为 0，且 0 永远表示禁止，不表示 unlimited。所有值不得为负；乘法/累加前使用 checked arithmetic，防止 `count * chars` 溢出。

Document limit 明确不含 `Duration`、absolute deadline、repair attempts、Provider attempts、connect/read timeout、bulkhead、concurrency、HTTP response cap、credentials 或 model/provider identity。这些分别归 P1 Planning/deadline 和 P2_V3/06 operational configuration。

### 10.8 ContractRef、求交与 canonical digest

三个 Document capability 均声明：

~~~java
public static final ContractRef DOCUMENT_RESOURCE_LIMIT_V1 =
    new ContractRef("DocumentResourceLimit", "1.0.0");
~~~

`DocumentResourceLimitContract` 实现 P1 `CapabilityResourceLimitContract<DocumentResourceLimit>`：

1. `supportedDimensions()` 精确返回 10.7 的 20 个稳定 dimension；
2. `validate` 校验 null、负数、结构必需正数、checked arithmetic 和 long 上限；
3. `intersect(left,right)` 对每个数值叶子取 `min`，不处理 allowed set 或 feature enum；
4. `isSameOrStricter(candidate,baseline)` 必须逐叶验证 `candidate <= baseline`；
5. `canonicalDigest` 使用 `DLRL-1` 前缀、固定字段顺序、十进制数值和 SHA-256 lowercase hex；
6. unknown dimension、ContractRef/type mismatch、遗漏叶子或旧版本 silent parse 一律拒绝。

`intersect` 必须满足交换、结合、幂等和结果对双方单调；nested record 不改变这些属性。Profile 的集合/feature policy 先按 10.3/10.5 收窄并进入 projection digest；不得把集合塞入 `DocumentResourceLimit` 后建立第二种 intersection 语义。

feature 的执行许可采用双门禁：`projection policy 允许` 且 `对应 Effective dimension > 0` 才能启用。`DISABLED` 无论 limit 多大都禁止；`OPTIONAL + limit=0` 在 Runtime Plan 前确定性转为 `DISABLED`；`REQUIRED + limit=0` 直接拒绝本次 Planning，不调用 Runtime；正数 limit 只表示容量，不授予 feature 权限。其余 OPTIONAL/REQUIRED 原值必须保留到 `DocumentExecutionProfileProjection`，不能只投影 enabled boolean，否则 Handler 无法执行 required/optional failure matrix。Runtime 只能在该结果内选择，Validator 再校验 echo/具体值。

document.search、document.answer、document.summarize 使用同一 ContractRef/type/dimensions，但 Definition intrinsic value 可不同：SEARCH 的 generation/summary dimensions 为 0；ANSWER 的 generated/evidence/context/citation 必须为正而 summary 可为 0；SUMMARIZE 的 summary/context/citation 必须为正。Profile/Policy/Permission 与 selected operation 交叉校验不一致时拒绝 candidate，不在运行时猜缺省值。

### 10.9 四类 contribution 与唯一 resolver

| source | 形成位置 | upperBound 来源 | evidenceRef 最小绑定 |
|---|---|---|---|
| Definition | `DocumentCapabilityConfiguration` | capability intrinsic safe upper bound | Registration identity + ContractRef/version；按 P1 作为 declaration 输入，不伪装 contribution |
| PROFILE | `DocumentProfileResourceLimitContributionAdapter` | exact Agent Profile 中该 capability 唯一 typed upper bound | exact AgentProfileRef + documentProfileVersion + assetDigest；selected profileName 只进入 selection binding，不改变 upper bound |
| POLICY | `DocumentPolicyResourceLimitContributionAdapter` | exact Policy 的 Document typed upper bound | policyVersion + policy evidence digest |
| PERMISSION | Authorization 边界内 `DocumentPermissionResourceLimitContributionAdapter` | current UserPermission 权威事实映射出的完整 typed upper bound | subject/permissionVersion/evidence digest，不含权限正文 |
| REQUEST | `DocumentRequestResourceLimitContributionFactory` | Java 已校验的 numeric narrowing | requestCorrelationId + narrowing canonical digest |

PROFILE/POLICY/PERMISSION 各必须恰好一项。PROFILE adapter 先从 exact parent contribution 取得 typed upper bound，再核对其 evidenceRef 所指 `DocumentProfileSet` 与本次 selection 的 asset/version/digest 一致；它不得从 selected child Profile 读取或计算第二份上限。某来源不额外收紧时，仍由该来源基于 Definition intrinsic value 形成显式同类型 upper bound 和有效 evidence；禁止缺省为 unlimited、空 contribution 或 resolver 自填。

Profile/Policy adapters 的形成时点是 P1 metadata candidate build/capture，而不是 Profile selection 之后：它们把强类型 upper bound 和 child evidenceRef 装入 P1 `PlanningEffectiveScope`。Document resolver 只消费这些已捕获的 refs；selection 完成后仅执行引用闭合校验。这样不要求修改 `CapabilityScopeSelection` 固定字段，也不向 P1 Planning 主流程加入 Document 专用 resource source。

PERMISSION adapter 位于 agent-service Authorization 边界，不要求 auth-service DTO 复制 20 个 Document 字段。它只能使用 P1 已授权的 current permission facts/attributes；unknown、越界、重复、无法形成完整 typed value 均 fail closed。03 的 ACL scope/filter 是访问控制事实，不作为数值资源求交的替代品。

REQUEST 是可选来源。由于 P1 contribution 的 `upperBound` 必须是完整 typed value，factory 先使用同一个 `DocumentResourceLimitContract` 对 Definition/Profile/Policy/Permission 构造 `preRequestUpperBound`，再仅覆盖 caller 明确给出的更小叶子；未提供叶子保持 pre-request 值。factory 不形成 Effective、Reference 或 binding。P1 resolver 随后独立重算前三层交集并证明 REQUEST `isSameOrStricter`；两次结果不一致即拒绝。禁止用 `Integer.MAX_VALUE`、null、0 或 sentinel 表示“未提供”。

`DocumentRetrievalProfileResolver` 不调用 P1 resolver；Document adapters 只形成 contributions。只有 P1 `CapabilityResourceLimitResolver.resolve(...)` 能产生 `EffectiveCapabilityResourceLimits`、canonical digest、binding identity 和 `ResourceLimitReference`。

P1 freeze 后、组装 PlanRequest 前，`DocumentPlanningProfileProjector` 执行 caller set narrowing 与 10.8 双门禁并返回唯一 final projection；它不修改 Effective value。该调用属于 Document Planning 组装逻辑，与 P2_V3/00 已定义的 `DocumentRawPlanAssembler` 同一 capability-local seam，不增加 P1 Context 字段或共享 enum。

### 10.10 Freeze、Execution recheck 与同源消费

Planning freeze 完成后，Authorization Snapshot 保存完整 immutable Effective value；Profile Binding/PAI/checkpoint/audit 只保存 safe reference/digest，不保存 typed value或 Profile/权限正文。Runtime Plan 只能在冻结上限内选择具体 count/feature，不能形成 REQUEST contribution。

Execution recheck 由 P1 Authorization boundary 使用 exact AgentProfileRef、policyVersion 和 current Permission 重新形成同一 ContractRef contributions：

- exact parent/profile child 引用和 digest 必须仍闭合；
- current value 必须与 Snapshot 同值或由 contract 证明更严格；
- invocation/correlation/registration/authorization binding 必须匹配；
- 扩大、换 ContractRef/type、切 profileName、Profile 独立换版本或无法证明均拒绝，不重新调用 Runtime Plan。

Core 从 recheck 后 `ExecutionScope.resourceLimits()` 构造 Validation/Execution Context。Validator、Handler、operation context、Adapter/Provider 和 Result Security 均通过 `require(DOCUMENT_RESOURCE_LIMIT_V1, DocumentResourceLimit.class)` 取得同一 typed value；禁止复制为散字段、重算 digest、按 JVM `==` 证明同源或回读 `AgentProperties`。

### 10.11 Definition 与 consumer dimension closure

| consumer | 必须声明/消费的主要 dimensions | 约束 |
|---|---|---|
| document.search Definition/Validator | input、retrieval、evidence/snippet/result | generation/summary 必须为 0 |
| document.answer Definition/Validator | input、retrieval、enhancement、evidence/context/citation/generated/result | required generation 对应值必须大于 0 |
| document.summarize Definition/Validator | input、retrieval、enhancement、evidence/context/citation/summary/result | summary chars/bullets 必须大于 0 |
| `DocumentCapabilityHandler` | selected operation 对应全部 dimensions | 实际参数先校验再调用任何 Adapter/Provider |
| document Adapter / es query request | channel/candidates/fused/chunks/returned | 不接收 Profile 或 Resource contribution 正文 |
| rewrite port | query chars/rewrite candidates | 只返回 original 之外有界候选 |
| embedding port | embedding texts/dimensions | dimension 同时受 01 manifest 精确校验；limit 不能替代 manifest |
| rerank port | rerank candidates | 输出 id 必须是输入安全候选子集 |
| generation port | context/evidence/citation/generated/summary | Provider response 仍是不可信 payload |
| Document Result Security | evidence/snippet/citation/generated/summary/result bytes | 与 current ExecutionScope limit reference 匹配后才输出 |

`CapabilityResourceConsumerDeclaration` 必须覆盖每个实际读取叶子。Definition 未声明、consumer 未登记或 Result projector coverage 缺失时启动/reload candidate 整体拒绝。

### 10.12 配置所有权与删除矩阵

| 当前/旧字段 | 目标唯一所有者 | 迁移动作 |
|---|---|---|
| `AgentProperties.Document.retrievalProfiles` 的 domain/materialTypes/profileName/channels/weights/RRF/dedup/context/field allowlist/feature policy | 本文 exact `DocumentProfileSet` | 从运行时散 properties 迁入 Agent Profile child asset；Resolver 只读 immutable candidate |
| retrieval profile 中的 `indexAlias/schemaVersion/embeddingField` | P2_V3/01 Corpus Catalog/manifest | 从 Profile 删除；以 `DocumentCorpusKey` 解析 |
| retrieval profile 中的 embedding provider/model/dimension | P2_V3/06 provider config + P2_V3/01 vector manifest | 从 Profile 删除；model operational identity 与 index dimension 分别校验 |
| rewrite/embedding/rerank/generation endpoint/model/credential/timeout/response cap/bulkhead | P2_V3/06 | 仅作为 operational config；不能进入 resource contribution |
| `maxProviderAttempts`/retry | P1_V2/05 + P2_V3/06 | 从 Document limit/Profile 删除；当前每 operation 外部 attempt 固定 0 或 1，自动 retry 关闭 |
| evidence/context/generated/summary/result bytes 等业务上限 | 本文 typed Definition/Profile/Policy/Permission/Request contribution | 删除 Handler/Provider/Projector 直读副本 |
| ACL endpoint、scope cache/currentness | P2_V3/03 | Profile 不保存 ACL/permission facts |
| qualityGate、Gold threshold、rollout state | P2_V3/07 | 从 Profile 删除；07 只引用 profileVersion/limit digest 做 change evidence |
| `document-adapter.index-by-domain` 或硬编码 alias fallback | P2_V3/01 | 删除；DocumentCorpusCatalog 唯一映射 |
| Runtime `/document/rewrite` 配置 | P2_V3/06 | 删除 Runtime 执行期 rewrite；迁 capability-local port |

`config-service/src/main/resources/config/application-agent-document.yml` 的现有字段必须按上表一次纵向迁移。02 只定义目标所有权，不直接授权修改关联专题文档或配置；实际切换遵守 P1_V2/06 M0～M6，不允许新旧配置双 active。

## 11. 接口设计

| 接口/类型 | 方法或构造 | 输入 | 输出/责任 |
|---|---|---|---|
| `DocumentProfileAssetRegistry` | `require(DocumentProfileAssetRef)` | exact safe ref | 唯一 immutable `DocumentProfileSet`；无 latest API |
| `DocumentRetrievalProfileResolver` | `select(DocumentProfileSelectionCommand)` | capability/domain、exact evidence、caller-safe narrowing | `DocumentProfileSelection` |
| `DocumentPlanningProfileProjector` | `project(selection, narrowing, effectiveLimits, capabilityId)` | selected strategy + caller narrowing + frozen typed value | 唯一 server-origin final projection，含 required/optional/zero 双门禁 |
| `DocumentProfileResourceLimitContributionAdapter` | `adapt(selection, declaration)` | selected profile + Definition | PROFILE contribution |
| `DocumentPolicyResourceLimitContributionAdapter` | `adapt(policyEvidence, declaration)` | exact policy | POLICY contribution |
| `DocumentPermissionResourceLimitContributionAdapter` | `adapt(permissionEvidence, declaration)` | current permission | PERMISSION contribution |
| `DocumentRequestResourceLimitContributionFactory` | `create(validatedNarrowing, preRequestSources)` | Java request + first three sources | optional full REQUEST contribution |
| `DocumentResourceLimitContract` | `validate/intersect/isSameOrStricter/canonicalDigest` | typed limit | P1 contract implementation |
| `DocumentRawPlanAssembler` | package-private `assemble(...)` | Runtime plan + server selection + limit ref/binding | trusted `DocumentRawPlan` |
| `DocumentPlanValidator` | `validate(DocumentRawPlan, ExecutionValidationContext)` | raw plan + domain/limits | `ValidatedDocumentPlan` |

所有 profile/resource 解析接口均为 agent-service 内部接口，不新增外部 HTTP endpoint。若实施需要给 public request 增加 requestedProfile/materialType/numeric narrowing 字段，属于公共契约修改，必须在 P1_V2/06 M0 单独授权并同步 Java/OpenAPI/Python/fixtures；本文评审不等于该授权。

## 12. 数据设计

本文不新增业务数据库表。配置/运行数据分层如下：

| 数据 | 存放 | 生命周期 |
|---|---|---|
| `DocumentProfileSet`/Policy constraint | P1 metadata candidate 引用的 immutable child asset | 与 exact AgentProfileRef/policyVersion 同发布、不可原地修改 |
| Profile/Policy/Permission contributions | Planning/Execution Authorization 内存 | Invocation 级，形成 Effective 后不向消费者暴露 source 正文 |
| Effective typed value | Authorization Snapshot/ExecutionScope 内存 | Invocation 级 immutable；Execution 可同值或收紧替换 |
| `ResourceLimitReference`/profile binding | PAI/checkpoint/audit safe metadata | 只存 ContractRef/digest/invocation/registration/profile safe ref |
| Profile/Permission 正文 | 不进入 Context/audit/result | 仅在受控 metadata/authorization 边界存在 |

checkpoint/audit 最多记录 `profileName/documentProfileVersion/profileProjectionDigest/ContractRef/limitDigest/registrationIdentity` 与安全拒绝码；不得记录 query、fields 全集、permission attributes、limit source values、Provider endpoint/credential 或完整 Profile YAML。

## 13. 状态流转设计

~~~text
CHILD_STAGED
  -> CANDIDATE_VALIDATED
  -> PARENT_PUBLISHED
  -> PROFILE_SELECTED
  -> CONTRIBUTIONS_ASSEMBLED
  -> LIMITS_FROZEN
  -> RAW_PLAN_BOUND
  -> PLAN_VALIDATED
  -> EXECUTION_RECHECKED
  -> CONSUMED
~~~

`CHILD_STAGED` 不对 Planning 可见；只有 `PARENT_PUBLISHED` 的 exact reference 可解析。candidate 失败停留在旧 parent，不能部分发布。Invocation 在 `LIMITS_FROZEN` 后不得换 Profile；Execution recheck 只允许资源同值/收紧，不允许返回 `PROFILE_SELECTED` 重规划。

## 14. 幂等、事务与一致性设计

- 同一 `DocumentProfileAssetRef` 重复 stage 只有 digest 相同才幂等成功；同 key 异 digest 是配置冲突；Profile child policy digest 与 parent typed contribution digest 分开计算，并由同一 metadata candidate/evidence 同时绑定；
- `DPROFILE-1` 与 `DLRL-1` canonicalization 对集合/Map 顺序不敏感，对任一语义字段变化敏感；
- metadata parent publish 是唯一可见性切换点；Profile、Policy constraints、typed contribution schema 和 Contract/Registration closure 要么全成功，要么仍使用旧 candidate；
- request set narrowing 与 numeric narrowing 重复应用幂等，且结果必须分别是原 projection 的子集、pre-request limit 的同值或更严格值；
- Execution recheck 与 Planning freeze 使用同一个 contract 实现；不得各自复制 min 算法；
- 一个 Invocation 只绑定一个 selected Profile、一个 Document ContractRef 和一个 current ResourceLimitReference；
- Profile 不参与 alias switch 事务，alias/current target 一致性由 01/07 负责。

## 15. 权限、风控与审计设计

- requestedProfile/materialType 是偏好/收窄输入，不授予 capability/domain/corpus/field/channel 权限；
- `DocumentProfileAssetRef`、Policy evidence、Permission evidence、projection digest 和 limit reference 全部绑定同一 invocation/correlation/registration；
- Profile field allowlist 只是静态上限，03 ACL/current Permission 与 P1 Result Security 仍必须动态收紧；
- required feature 被 caller 禁用、Policy allowlist 为空、Permission contribution 缺失、Runtime echo 错配均 fail closed；
- Provider 不能返回或覆盖 profileVersion/owner/authorization digest/ResourceLimitReference；
- audit 使用安全 ID/digest/拒绝码，不记录用户查询、文档文本、ACL 表达式、向量或 Provider 原始响应；
- 配置管理权限、Profile 发布权限、Document 查询权限和 07 rollout 权限相互独立；拥有其中一项不隐含其他权限。

## 16. 性能与容量设计

- Profile/Policy child asset 在 candidate build 时解析和 canonicalize，Invocation 不重复解析 YAML；
- Registry 以 exact ref O(1) 查找，domain/profileName 使用 immutable index；
- Profile 集合、materialTypes、channels、fields 和 policies 均设置 candidate-build 数量/字符串长度上限，防止配置型内存放大；
- `DocumentResourceLimit` 为小型 immutable value；contract intersection/canonical digest 为固定 20 叶 O(1) 操作；
- Permission 交集和 Effective value 不跨用户/租户全局缓存；
- Provider stage cap 与 absolute deadline 的计算不进入 Profile resolver，避免一次 Invocation 多处重复计算。

建议 candidate hard cap：每 Agent Profile 每 domain Profile 数不超过 32、materialTypes 不超过 32、channels 不超过 8、field refs 不超过 256。该 hard cap 是 metadata parser 的拒绝阈值，不是业务授权 limit，也不得成为消费者 fallback。

## 17. 兼容性与 Multi-Agent 扩展设计

系统未投产，本次不保留旧 `DocumentRetrievalProfile(indexAlias, hybridOptions)`、`ResolvedDocumentExecutionConfig`、散预算 properties 或 Runtime rewrite 兼容层。切换必须在 P1_V2/06 的同一 Release Unit 中纵向完成，防止新 Profile 与旧 Handler/Projector 双权威。

Future Multi-Agent 演进保持以下 seam：

- `DocumentProfileAssetRef` 继续绑定 P1 提供的 owner/scope/exact AgentProfileRef，不增加 `parentAgentId/childAgentId` Document 字段；
- 若 L1 将来新增 DELEGATION/RUN/TASK resource source，只由 P1 扩展 contribution 输入与单调证明；`DocumentResourceLimitContract` 和消费者 `require` 接口不变；
- Coordinator 只能传递 P1 的精确 Profile/limit/delegation binding，不能直接选择 alias/provider 或扩大 Document Profile；
- child Agent 使用相同 Profile selection/Raw Plan/Validator/Handler 链，不复制 Document resolver 或资源状态机。

新增 Document channel/feature 时，只有在 Profile enum、04/06 typed port、Contract dimensions、consumer declarations、Result Security 和测试同一版本闭合后才能启用；不能用自由 Map 预留未知扩展。

## 18. 日志、监控与告警

| 类型 | 事件/指标 | 允许标签 | 禁止内容 |
|---|---|---|---|
| event | profile candidate accepted/rejected | metadataBundleVersion、safe profile ref、reasonCode | Profile YAML、field 全集、credentials |
| metric | profile selection success/reject | capabilityId、domain、profileName、reasonCode | query/material content |
| metric | contribution/resolver reject | source、ContractRef、dimension、reasonCode | permission/source values |
| metric | execution recheck tightened/rejected | ContractRef、changed dimension count、reasonCode | before/after raw values |
| alert | duplicate default、asset digest conflict、consumer gap | safe candidate/version | 配置正文 |
| alert | Runtime profile echo mismatch、request enlargement | capabilityId、reasonCode | Runtime raw payload |

日志不得输出完整 `DocumentResourceLimit`、query、ACL、evidence、Provider response 或 Profile/Policy/Permission 正文。需要定位数值问题时只记录 dimension ID、比较结果和 diagnosticId。

## 19. 实现落点清单

### 19.1 新增/修改类型

| 序号 | 路径 | 类/动作 | 变更 |
|---:|---|---|---|
| 1 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/document/resource/DocumentResourceLimit.java` | root typed limit + nested value records | 新增 |
| 2 | `agent-service/src/main/java/com/dylan/agent/capability/document/resource/DocumentResourceLimitContract.java` | ContractRef/dimensions/validate/intersect/strictness/digest | 新增 |
| 3 | `agent-service/src/main/java/com/dylan/agent/capability/document/resource/DocumentResourceLimitDimensions.java` | 20 个稳定 dimension 常量 | 新增 |
| 4 | `agent-service/src/main/java/com/dylan/agent/capability/document/profile/DocumentProfileSet.java` | exact AgentProfile child asset | 新增 |
| 5 | 同包 `DocumentRetrievalProfile.java` | 移除 alias/provider，改为本文权威结构 | 替换现有类型 |
| 6 | 同包 `DocumentProfileAssetRef.java`、`DocumentProfileAssetRegistry.java` | exact immutable lookup，无 latest API | 新增 |
| 7 | 同包 `DocumentPolicyConstraint.java` | exact Policy profile/channel/operation narrowing | 新增 |
| 8 | 同包 `DocumentRetrievalProfileResolver.java` | Pre-Plan deterministic selection | 替换现有 properties resolver |
| 9 | 同包 `DocumentProfileSelection.java`、`DocumentPlanningProfileProjection.java` | server-origin selection/projection | 新增 |
| 10 | 同包 `DocumentPlanningProfileProjector.java` | caller-safe narrowing + frozen limit 双门禁，唯一 final projection | 新增 |
| 11 | `agent-service/src/main/java/com/dylan/agent/capability/document/planning/DocumentProfileBinding.java` | Invocation/Profile/limit/projection binding | 新增 |
| 12 | 同包 `DocumentRawPlan.java`、`DocumentRawPlanAssembler.java` | package-private trusted assembly，显式接收 final projection | 新增 |
| 13 | 同包 `DocumentExecutionProfileProjection.java` | Validated Plan 的最小具体策略；含 requiredChannels 与四个 closed feature policy | 新增 |
| 14 | `agent-service/src/main/java/com/dylan/agent/capability/document/resource/contribution/*` | Profile/Policy/Permission/Request adapters | 新增 |
| 15 | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentCapabilityConfiguration.java` | 三个 Definition 的单 Contract declaration/consumer closure | 修改 |
| 16 | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentPlanValidator.java` | 接收 DocumentRawPlan，读取 typed limits | 修改 |
| 17 | `agent-service/src/main/java/com/dylan/agent/capability/document/ValidatedDocumentPlan.java` | 增加最小 execution profile projection/具体参数 | 修改 |
| 18 | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentCapabilityHandler.java` | 删除 Profile/散预算直读 | 修改 |
| 19 | `agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java` | 只使用传入同一 limits/reference | 修改 |

### 19.2 metadata/config 原子切换

| 路径 | 动作 |
|---|---|
| `agent-service/src/main/java/com/dylan/agent/metadata/profile/model/AgentProfileDefinition.java` | 仅按 P1_V2/03/05 承载 typed contribution/evidence seam；不得增加 Document 专用字段 |
| `agent-service/src/main/java/com/dylan/agent/metadata/policy/model/AgentPolicySnapshot.java` | 仅按 P1 generic typed Policy contribution/evidence seam 接入；不得嵌入 Document 类 |
| `agent-service/src/main/java/com/dylan/agent/metadata/config/AgentMetadataBootstrap.java`/`AgentMetadataReloader.java` | 通过 P1 composition/reload closure 调用 Document candidate validator；不增加第二 active store |
| `agent-service/src/main/java/com/dylan/agent/config/AgentProperties.java` | 删除 Document 业务 Profile/limit、alias/model/dimension 混合结构；只保留仍归该模块的 operational locator |
| `config-service/src/main/resources/config/application-agent-document.yml` | 按 10.12 一次迁移到 Profile child、Corpus Catalog、ACL、Provider、rollout 唯一段 |

若 P1 实现尚未提供 typed contribution/evidence 和 candidate closure seam，P2 实施必须等待 P1_V2 M2/M3 完成；不得先在 `AgentProfileDefinition` 添加 Document 专用字段临时绕过。

### 19.3 静态删除门禁

实施完成后下列模式在生产 main source/config 中必须零命中或只存在于迁移说明/测试负例：

~~~text
ResolvedDocumentExecutionConfig
DocumentRetrievalProfile(... indexAlias ...)
getRetrievalProfiles()/getIndexAlias()/getEmbeddingProvider()/getEmbeddingModel()
maxProviderAttempts/maxRewriteStage/maxEmbeddingStage/maxRerankStage/maxGenerationStage
DocumentPlanValidator -> AgentProperties
DocumentCapabilityHandler -> AgentProperties
DocumentResultSecurityProjector -> AgentProperties
RuntimeDocumentQueryRewriteClient
document-adapter.index-by-domain
~~~

## 20. 测试设计与验收命令

### 20.1 测试矩阵

| 类别 | 必测场景 | 关键断言 |
|---|---|---|
| Profile asset | exact ref、missing/duplicate/异 digest、无 latest API、旧 Invocation | parent exact binding；部分 candidate 不可见 |
| selection | explicit/default、0/2 default、Policy 排除、materialType 不支持、Runtime echo mismatch | deterministic；失败不回退其他 Profile |
| projection | caller 禁 required、启 disabled、扩大字段/channel、序列化伪造 | 只收窄；trusted projection 无 JSON 入口 |
| projection/eligibility | REQUIRED+0、OPTIONAL+0、DISABLED+positive、OPTIONAL/REQUIRED+positive、requiredChannels、双 projection 注入 | required+0 拒绝；optional+0 转 DISABLED；其余 policy/requiredChannels 原样保留；正数不授予权限；只有一个 final projection |
| canonical | set/map 重排、任一字段变化、8-byte collision fixture、非法字符 | 同语义同 digest；语义变化可检出；完整 SHA-256 |
| contract property | 每叶 min、交换/结合/幂等/单调、负数/0/溢出/unknown dimension | 0 不作 unlimited；20 叶全覆盖 |
| contributions | 缺/重复 Profile/Policy/Permission、neutral source、request partial/扩大、evidence 错配 | 三必需一可选；request 只收紧 |
| freeze/recheck | Permission 收紧/扩大、Profile/Policy 版本变化、registration/limit ref 错配 | 同值/更严格通过；否则 fail closed |
| PAI binding | Runtime plan/projection/binding 任一篡改 | PAI-1 不一致；不进入 Handler |
| consumer closure | Validator/Handler/四 Provider/Result projector 漏 dimension | startup/reload candidate 拒绝 |
| ownership | Profile 残留 alias/provider/timeout/qualityGate；消费者直读 properties | architecture test 失败 |
| Multi-Agent seam | 模拟 future extra source 后消费者接口 | Document contract/Handler 接口不变；未授权 source 当前拒绝 |

### 20.2 最小实施验收命令

~~~powershell
./mvnw.cmd -f serviceCenter/pom.xml -pl agent-adapter-api,agent-service,agent-adapter-document,document-provider-adapter -am test

rg -n "ResolvedDocumentExecutionConfig|maxProviderAttempts|maxRewriteStage|maxEmbeddingStage|maxRerankStage|maxGenerationStage" agent-service/src/main agent-adapter-api/src/main config-service/src/main/resources/config

rg -n "getRetrievalProfiles|getIndexAlias|getEmbeddingProvider|getEmbeddingModel|document-adapter\.index-by-domain" agent-service/src/main config-service/src/main/resources/config

rg -n "AgentProperties" agent-service/src/main/java/com/dylan/agent/capability/document/DocumentPlanValidator.java agent-service/src/main/java/com/dylan/agent/capability/document/DocumentCapabilityHandler.java agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java

rg -n "RuntimeDocumentQueryRewriteClient|/runtime/v1/document/rewrite" agent-service/src/main agent-runtime/app
~~~

上述命令是实施验收规范，本次文档评审不声称代码测试已通过。

## 21. 风险与待确认事项

| 风险 | 触发场景 | 影响 | 控制 |
|---|---|---|---|
| P1 seam 未实施 | typed contribution/evidence/candidate closure 尚不存在 | P2 可能临时侵入 AgentProfile/Core | 将 P1_V2 M2/M3 作为实施硬前置，不加 Document 专用字段 |
| 双配置权威 | 新 Profile child 与旧 AgentProperties 同时 active | 不同消费者得到不同策略/预算 | P1_V2/06 同 Release Unit 切换，静态零残留 gate |
| request partial 语义错误 | 未提供叶子用 0/MAX/sentinel | 意外禁用或放大 | factory 以 preRequestUpperBound 填充，P1 resolver 独立复核 |
| Profile/Index 漂移 | Profile 保存 alias/schema/model | 无谓重建、错索引或维度冲突 | Profile 只保存 CorpusKey allowlist；01/06 各自权威 |
| currentness 分裂 | Document Profile 自建 active/latest/reload | Execution 无法证明 exact version | parent exact ref 唯一 currentness；无独立 active API |
| consumer 漏维度 | Provider/Projector 未声明/校验新叶子 | 输出或调用越界 | consumer declaration + startup coverage + architecture test |
| public contract 变更 | 增加 requestedProfile/materialType/numeric narrowing | Java/OpenAPI/Python/调用方漂移 | M0 单独授权和原子生成/切换 |

当前无文档级 S0/S1 阻塞。代码实施仍受 P1_V2 M2/M3、公共契约授权和 P1_V2/06 原子迁移门禁约束。

## 22. 评审记录

| 轮次 | 日期 | 结论 | 处理 |
|---:|---|---|---|
| 1 | 2026-07-13 | 修订后复审 | 发现 Profile 侵占 index/provider/quality gate、资源预算混入 timeout/attempt、选择晚于 Plan、独立 currentness、第二 Execution Config 和 request partial contribution 不闭合；已按 P1/P2_V3/00 重写 |
| 2 | 2026-07-13 | 修订后复审 | 发现 selected child Profile 自带 upper bound 会与 P1 parent typed PROFILE contribution 重复并形成选择/贡献环；已将数值上限收回 exact parent contribution，child asset 只保留策略并以 evidenceRef 闭合 |
| 3 | 2026-07-13 | 修订后复审 | 冻结 Policy child evidence、Execution 最小 projection 和 feature/limit 双门禁；发现总图和对象模型仍保留 contribution/selection 时序及双 projection 歧义 |
| 4 | 2026-07-13 | 通过 | 重排为 capture contributions→Route→selection→freeze→单次 projector，assembler 显式绑定 final projection；复核上级约束、专题所有权、接口、数据、配置、测试与 Multi-Agent seam 后无 S0/S1 |
| 5 | 2026-07-13 | 通过 | 关联复审修复 Execution projection 的 required/optional 信息损失：新增 requiredChannels，四类 feature 保留 closed policy；最终无 S0/S1 |

## 23. 实施对齐检查

- [x] Profile selection 已冻结在 Route 后、Runtime Plan 前。
- [x] Document Profile 已绑定 exact AgentProfile parent，无独立 latest/currentness。
- [x] Profile 与 index/provider/ACL/rollout 所有权已拆分。
- [x] `DocumentPlanningProfileProjection` 与 Raw Plan server-origin binding 已冻结。
- [x] `DocumentExecutionProfileProjection` 保留 requiredChannels 与 REQUIRED/OPTIONAL/DISABLED，且与 Effective limit 双门禁已冻结。
- [x] 单 `DocumentResourceLimit` ContractRef、20 dimensions、0 语义和 canonical digest 已冻结。
- [x] Definition/Profile/Policy/Permission/optional Request contribution 已闭合。
- [x] parent typed PROFILE contribution 与 child Profile policy 已去重，选择不再改变数值 source。
- [x] P1 resolver 唯一性与 Execution recheck 同源消费已冻结。
- [x] 配置删除/迁移、实现路径、consumer coverage 和测试门禁已列出。
- [ ] P1_V2 M2/M3 typed resource/evidence seam 尚未在当前代码完成。
- [ ] 当前 `DocumentRetrievalProfile/Resolver` 与 `AgentProperties` 仍是旧实现。
- [ ] 公共请求是否新增 narrowing 字段尚未授权。
- [x] P2_V3 全集评审已完成且 S0/S1=0；本文仍为 In Review，等待用户 Approved 与 M0 实施授权。

## 24. 任务完成摘要

本文已将 Document Profile、Planning 投影和有效资源预算收敛为 P1 扩展模型：exact AgentProfile typed contribution + strategy child asset、Pre-Plan Java 选择、server-origin Raw Plan binding、单强类型 ContractRef、P1 唯一 resolver 与同源消费。旧 Profile 中的 alias/schema/provider/model/timeout/attempt/ACL/qualityGate 已移交唯一所有者，`ResolvedDocumentExecutionConfig` 和消费者散预算已退出目标设计。

当前文档级结论为：五轮评审-修复完成，S0=0、S1=0；Execution projection 已保留 channel/feature requiredness，P2_V3 全集评审已完成，本文仍保持 In Review。实现级结论为：必须等待用户 Approved、P1_V2 M2/M3 seam 和 M0 原子迁移授权，不得以 Document 专用字段侵入 P1 Core。
