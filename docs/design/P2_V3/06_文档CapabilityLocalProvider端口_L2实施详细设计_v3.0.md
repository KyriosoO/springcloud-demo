# 文档 Capability-local Provider 端口 L2 实施详细设计 v3.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 文档 Capability-local Provider 端口 L2 实施详细设计 |
| 文档路径 | `docs/design/P2_V3/06_文档CapabilityLocalProvider端口_L2实施详细设计_v3.0.md` |
| 文档状态 | In Review |
| 当前版本 | v3.0 |
| 创建/最后更新日期 | 2026-07-13 |
| 适用代码基线 | `816e2c855574da5326379128bfb3e230241d2fe3` |
| 设计层级 | L2 Document capability-local Provider policy、port、wire、client、adapter 与 operational gate |
| 上级文档 | 四份当前 L0/L1；只读权威基线 |
| 直接前置 | P1_V2/02～06、P2_V3/00～05 |
| 关联文档 | P2_V3/01～05、07 |
| 合并来源 | P2/07、P2_V2/07、旧 rewrite/embedding/rerank/generation Provider 规则 |
| 是否可作为实现依据 | 否；P2_V3 全集评审已完成且 S0/S1=0，但仍为 In Review；模块重命名、内部 HTTP contract、服务身份、配置与旧路径删除经 M0 原子授权后方可实施 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | 四类 port 调用口径不一致且 rewrite 侵入 Planning Runtime | 统一 capability-local port、deadline/cancel/metadata/retry 边界 |
| 2 | 2026-07-13 | 10.7、19、21～24 | 替代 Provider 落点悬空 | 将 rewrite 暂定迁入既有 generation adapter，不新增通用 Provider 服务 |
| 3 | 2026-07-13 | 全文 | P2_V3 改为自包含基线 | 合并旧 Provider/rewrite/embedding/rerank 规则与迁移落点 |
| 4 | 2026-07-13 | 全文 | 第一轮 cross-layer 评审发现 operation request 未内嵌统一 context、generation 反向输出 trusted candidate、四类外发 policy 重复、三种部署/凭据边界、隐藏第二 endpoint fallback、Map wire、Provider/model 重入、attempt/availability/cancel/strict parser 和 Multi Agent 边界不闭合 | 重写为共享 current-scope outbound decision、四个 typed port、统一 wire envelope、单一 Document Provider Adapter、07 current activation、两跳一次 attempt、strict payload validator和原子迁移门禁 |
| 5 | 2026-07-13 | 第9～21节 | 第二轮发现07 snapshot携带endpoint会侵入06 composition，DPO-1示例漏authorization/limit binding，两跳attempt与Provider identity含义不清 | snapshot只发布operation/provider/contract state；06按operation映射固定internal endpoint；decision补authorization/resource binding和closed field rule；P1 attempts明确统计agent→adapter，vendor/model由validated binding及adapter审计表达 |
| 6 | 2026-07-13 | 第10～24节 | 第三轮发现DPW-1未携带absolute deadline与activation digest，adapter算法无法履约；失败wire未冻结；P1 Provider identity不应被内部adapter服务身份替代 | 请求补deadline/activation binding，success回显observed activation，新增closed error wire及本地映射；metadata provider恢复为逻辑vendor/model safe identity，adapter身份独立绑定，终审S0=0、S1=0 |
| 7 | 2026-07-13 | 1、21、23～24 | P1_V2/P2_V3 全集终检同步 07 闭合状态 | 标记 activation authority/feed/readiness/rollback 设计已由 07 承接，保留代码未实现与 M0 边界；不新增评审轮次 |
| 8 | 2026-07-13 | 2、22 | 评审报告移动到目标文档同目录 | 将最终结论引用改为同目录同名评审报告；不新增评审轮次，不改变设计结论 |

## 3. 文档状态说明

本文处于 In Review，不授权直接重命名模块、修改 Maven 聚合、替换内部 endpoint、移动凭据、删除 Runtime rewrite、发布 07 状态或启用真实 Provider。本文只冻结四类 Document capability-local Provider operation 的目标实现。

本文是 rewrite、embedding、rerank、generation Provider policy/port/wire/client/adapter 的唯一专题规范。旧 P2/P2_V2 仅保留 provenance；其中 Runtime rewrite、业务 request 携带 provider/model/dimension、`Map<String,Object>` wire、HTTP 404/405 切第二 endpoint、client 截断/归一化 Provider 答案、各 Provider 自读 `AgentProperties` 和混合部署路径不再用于补充实现。

## 4. 背景与目标

当前实现已存在四类 port/client 和 `document-generation-adapter`，但尚未满足 P1/P2_V3：

- 四类 port 直接返回业务结果或抛异常，没有 `CapabilityOperationContext/Outcome/Metadata`；
- rewrite 调用 Agent Runtime `/runtime/v1/document/rewrite`，把执行期 Provider 重新并入 Planning Runtime；
- embedding request 携带 provider/model/expectedModel/expectedDimension/queryVariants，且 404/405 后自动改调 `/embed`，一次 operation 可能发生两次外部调用；
- embedding client 使用 `Map` 解析并平均多向量，覆盖 04 已冻结的单 original query 语义；
- rerank request 携带 retrievalProfile、domain/materialType 和完整 `AdapterDocumentResult`，设施层看到不必要对象；
- generation request 发送 query/model/完整旧 ECP，Provider adapter 会去除 citation label、推导 binding并截断 answer/summary，侵入 05 candidate/citation/limit owner；
- agent-service 直连 embedding/rerank，另经 generation adapter 调 generation，rewrite 又经 Runtime，形成三种 endpoint、凭据、重试和审计边界；
- `document-generation-adapter` 已被计划承载 rewrite，模块名与责任开始漂移；若继续增加 embedding/rerank，后续必然再做服务重命名与调用迁移；
- 当前配置把 feature、Profile、业务预算、provider/model/baseUrl/fallback 和 operational timeout 混在 `AgentProperties`，多个消费者可独立扩大或改路由；
- Provider disable/rollback 只作为发布概念，未形成 HTTP write 前可验证的 current activation snapshot；
- client/SDK/mesh 的真实 attempt、deadline/cancel race、late result、request/response binding 和严格未知字段策略不可证明。

目标是形成一条最小且不可绕过的 Provider 链：04/05 在 current ExecutionScope 下取得同一 outbound decision并形成 provider-safe input；06 port 只接受内嵌 context/policy reference 的 typed request；agent-service 复核 limits/deadline/cancel/07 activation 后调用唯一 Document Provider Adapter；adapter 再以独立 vendor mapper/client执行一次外部 attempt并返回 strict untrusted payload；04/05决定候选、fallback和最终安全结果。

## 5. 设计范围

### 5.1 范围内

- rewrite/embedding/rerank/generation 四类 `CapabilityOperationType` 常量、typed input/request/outcome；
- current ExecutionScope 的共享 Provider outbound decision、canonical digest、non-wire reference和request binder；
- `DocumentProviderBindingReference`、07 current activation snapshot/read view和HTTP write前gate；
- agent-service 到 Document Provider Adapter 的统一 DPW-1 request/response envelope；
- 四个内部 endpoint、服务认证、contract/binding/digest校验和错误映射；
- adapter 到 vendor 的 operation-specific prompt/request/response mapper、一次attempt、strict parser；
- absolute deadline、operational stage cap、cancellation、late result、availability change和in-flight abort；
- request/response bytes、bulkhead、连接池、日志、指标、审计和启动/readiness门禁；
- `document-generation-adapter` 到 `document-provider-adapter` 的原子重命名与旧路径清理；
- 单 Agent 当前实现与未来 Multi Agent child Invocation 复用边界。

### 5.2 范围外

- 是否调用 Provider、REQUIRED/OPTIONAL/DISABLED 和业务 fallback，归 04/05；
- query/channel/RRF/context/rerank order算法，归 04；
- evidence selection/ECP/citation/generated candidate/public result，归 05；
- Profile/feature/typed business limits 求交，归 02/P1；
- ACL/Safe candidate/final currentness，归 03；
- vendor采购、模型训练、Gold factuality/quality/capacity、生产启用/rollback决策，归 07；
- Planning Route/Plan prompt/repair、Agent Runtime API；
- Multi Agent coordinator、task graph、跨child Provider批处理、全局cache或共享prompt memory。

## 6. 上级文档约束

1. capability-local Provider port 由 capability 模块声明、composition root 装配；不进入 Capability Registry、Adapter Registration、Domain metadata或Planning Runtime。
2. typed request 必须实现P1 `CapabilityOperationRequest`并内嵌唯一`CapabilityOperationContext`；不能使用“业务request + 独立context”双参数。
3. context传播同一invocation/correlation/operationId/type、absolute deadline、read-only cancellation和`CapabilityResourceLimitView`；不得复制JWT/ExecutionScope/Policy/Profile。
4. success/failure均返回P1 `CapabilityOperationOutcome<T>`和本地权威`CapabilityOperationMetadata`；Provider不能自报可信attempt/duration/owner/limit。
5. disabled attempts=0；发生agent-service outbound时attempts=1；自动retry、备用Provider和第二endpoint fallback关闭。
6. operational cap只能缩短timeout、减小bytes/queue/concurrency或拒绝；不得替代、扩大或重算`DocumentResourceLimit`。
7. Provider输出均是不可信候选；04/05必须继续执行业务validator/candidate factory，最终结果经过03/P1安全边界。
8. 当前单智能体；未来child Invocation继续独立context/limit/decision/attempt，不在Provider层共享授权或聚合结果。

## 7. 关联文档与边界

| 文档 | 输入给06 | 06输出/服务 | 禁止侵入 |
|---|---|---|---|
| P1_V2/02～03 | ExecutionContext/current ExecutionScope、Result Security总边界 | outbound policy decision使用current refs | 不解析权限正文、不写Context/Result |
| P1_V2/05 | operation context/outcome/metadata、typed limit view/reference | 四类typed operation | 不自建attempt/deadline/failure enum |
| P1_V2/06 | M0/M2～M6原子迁移门禁 | contract/config/旧路径清理项 | 不自行授权模块重命名/删除 |
| P2_V3/01 | embedding manifest/model binding消费方 | safe embedding binding reference | 不解析alias/physical target |
| P2_V3/02 | feature policy和`DocumentResourceLimit` | request/response业务上限复核 | 不选择Profile/重算limit |
| P2_V3/03 | Safe candidate与final currentness目标 | rerank输入只接受04 projection；provider safe binding供final guard | 不把Safe等同外发许可 |
| P2_V3/04 | rewrite/embedding/rerank input、required/optional路由 | typed outcome | 不决定query/channel/rerank fallback |
| P2_V3/05 | generation input、policy/input digest、untrusted payload contract | typed generation outcome | 不构造ECP/candidate/citation/fallback/public result |
| P2_V3/07 | current activation snapshot、approved provider binding/version | read-only pre-send gate、safe metrics | 不创建rollout state/审批/报告 |

## 8. 设计边界与约束

| 约束 | 冻结规则 |
|---|---|
| 四port独立 | 保留业务typed差异；不建立`execute(Map)`、万能prompt或通用result union |
| Policy单一解释器 | 06只有一个`DocumentProviderOutboundPolicyDecisionFactory`；04/05只做operation-specific内容投影 |
| Request单context | `Document*OperationRequest`内嵌policy reference和operation context；Domain Adapter双参数SPI不受影响 |
| Input无设施选择 | caller/Plan/input不携带baseUrl/path/provider/model/credential/expectedDimension/timeout/retry |
| Wire唯一 | agent-service只调用Document Provider Adapter的四个internal endpoint；不直连vendor、不调用Runtime |
| Vendor mapper隔离 | DPW envelope/policy ref/operation context不直接发给vendor；只发送operation-specific safe input |
| 一次attempt | local inactive为0；agent→adapter最多1，adapter→vendor最多1；两跳均无自动retry/endpoint fallback |
| 失败不编排 | client只映射typed failure；Handler决定required/optional/fallback/refuse |
| 输出不修复 | 06不截断generated文本、不删除/别名化citation、不平均/补零vector、不增删rerank candidate |
| Availability只收紧 | 07 snapshot非ACTIVE/unknown/expired/mismatch时write前拒绝；不能由配置重新启用 |
| 无持久operation状态 | request/payload/decision不落业务表/Context/cache；P1 Lifecycle是唯一Invocation状态权威 |
| Multi Agent leaf | 不增加parentAgentId/taskId/workerId/sharedBudget/sharedEvidence字段 |

## 9. 总体设计

### 9.1 唯一调用链

~~~text
04/05 business stage
  -> DocumentProviderOutboundPolicyDecisionFactory(current ExecutionScope, operation, Corpus, feature, field view)
  -> operation-specific input projector
  -> DocumentProviderOperationRequestBinder(decision digest + canonical input digest + operation context)
  -> typed Document*Port.invoke(request)
       -> request/context/policy/typed-limit pre-validation
       -> 07 DocumentProviderActivationReadView.requireActive(operation)
       -> fixed internal endpoint + DPW-1 request canonicalization
       -> immediate activation/deadline/cancel recheck
       -> one internal HTTP attempt to document-provider-adapter
            -> service auth/DPW/binding/deadline/bytes validation
            -> adapter activation/binding recheck
            -> operation-specific vendor mapper/client, zero or one vendor attempt
            -> strict vendor response parser
            -> DPW-1 typed response envelope
       -> agent-side binding/payload/deadline/cancel/activation post-validation
       -> local CapabilityOperationOutcome + Metadata
  -> 04 validator/order or 05 candidate/citation/fallback
~~~

### 9.2 所有权

| 层 | 权威内容 | 不拥有 |
|---|---|---|
| 04/05 | 是否调用、业务input投影、required/optional/fallback、候选校验 | endpoint/model/credential/HTTP |
| 06 agent-service | shared outbound decision、request binding、port/client/wire验证、本地metadata | Profile/授权正文/业务fallback |
| 06 provider adapter | vendor binding/prompt/template/request/response/credential/SDK | Agent编排、ACL、ECP、public result |
| 07 | activation/readiness/rollout/rollback/current snapshot | port算法、HTTP parser、业务候选 |

### 9.3 部署收敛

当前`document-generation-adapter`已承担generation并计划增加rewrite；若embedding/rerank继续由agent-service直连，未来仍需迁移凭据、retry、availability和审计。目标在同一M0 Release Unit把既有模块重命名为`document-provider-adapter`，作为Document capability专用基础设施adapter，承载四个operation endpoint和各自vendor client。它不是跨capability通用Provider服务，不做fallback/路由/聚合，也不进入Agent Runtime。

## 10. 详细功能设计

### 10.1 Operation type 与调用条件

06复用P1 `CapabilityOperationType`受控值，不新增平行enum：

| 常量 | 业务调用者 | 当前最小数据 |
|---|---|---|
| `DOCUMENT_QUERY_REWRITE` | 04 | one normalized original query、language、maxCandidates |
| `DOCUMENT_QUERY_EMBEDDING` | 04 | 当前exactly one normalized original query |
| `DOCUMENT_RERANK` | 04 | bounded query + all-or-none provider-safe candidate items |
| `DOCUMENT_GENERATION` | 05 | provider-safe ECP projection，无query/identity/URI |

feature为DISABLED、对应typed limit为0、无输入或Handler已选择本地路径时不创建operation request、不调用port。06不根据配置替Handler决定是否调用。

### 10.2 Shared outbound policy decision

`DocumentProviderOutboundPolicyDecisionFactory`位于agent-service `capability/document/provider/security`，是四类operation唯一purpose/policy解释器。输入为operation type、current ExecutionScope、单一`DocumentCorpusKey`、02 feature policy、operation-specific intended field/data view和当前absolute deadline；输出内部immutable decision：

~~~java
record DocumentProviderOutboundPolicyDecision(
    CapabilityOperationType operationType,
    DocumentCorpusKey corpusKey,
    String authorizationBindingDigest,
    String policyEvidenceDigest,
    String permissionEvidenceDigest,
    String profileProjectionDigest,
    ResourceLimitReference resourceLimitReference,
    List<DocumentProviderFieldRuleDecision> orderedFieldRules,
    Instant validUntil,
    String canonicalDigest) {}

record DocumentProviderFieldRuleDecision(
    CanonicalFieldRef field,
    SecurityClassificationRef classification,
    MaskType maskType) {}
~~~

factory只使用ExecutionScope已解析的field permission、P1 `MaskType/ResultValueMaskingSupport`、security-classification refs和same-or-narrower evidence；不读取Provider/07/config/credential，也不执行I/O。query-only operation的field rules可为空，但effective feature、Policy/Permission、Corpus和operation purpose仍必须显式允许；已有security-classification refs若不能表达外部处理许可，结果只能DENY并由07保持非ACTIVE，不得由06新增默认allow或要求修改L1才能启动disabled实现。unknown classification/Mask、scope/evidence缺失、purpose未声明、feature mismatch、过期或无法证明只收紧均DENY。

decision canonical使用`DPO-1`：固定版本、operation、DCK-1 Corpus、authorization/policy/permission/profile evidence digest、resource limit reference、按canonical field排序的classification/Mask rule、validUntil，UTF-8 length-prefixed，SHA-256 lowercase。`ResultValueMaskingSupport`只执行decision已经允许字段的值变换，不自行决定外发许可。decision不是Authorization Snapshot替代物，不跨Invocation缓存。

### 10.3 Policy reference 与 operation request

04/05应用decision形成最终provider-safe input后，`DocumentProviderOperationRequestBinder`计算operation-specific canonical input digest并构造non-wire reference：

~~~java
public record DocumentProviderOutboundPolicyReference(
    String invocationId,
    String operationId,
    CapabilityOperationType operationType,
    String decisionDigest,
    String inputDigest,
    ResourceLimitReference resourceLimitReference,
    Instant validUntil) {}
~~~

每个request实现P1 `CapabilityOperationRequest`：

~~~java
public record DocumentRewriteOperationRequest(
    DocumentRewriteInputProjection input,
    DocumentProviderOutboundPolicyReference outboundPolicyReference,
    CapabilityOperationContext operationContext)
    implements CapabilityOperationRequest {}

// Embedding/Rerank/Generation保持相同三段结构，业务input类型不同。
~~~

port入口重算input digest，验证reference的Invocation/operation/type/limit/validUntil与context完全一致。reference不进入DPW body/header/vendor；missing/mismatch/expired以attempts=0返回`SECURITY_REJECTED`或`BINDING_MISMATCH`。request/input可以是Spring-free adapter-api类型，但不能有Jackson creator把wire body直接反序列化成operation request。

### 10.4 Rewrite contract

~~~java
public record DocumentRewriteInputProjection(
    String originalQuery,
    DocumentLanguage language,
    int maxCandidates) {}

public record DocumentUntrustedRewritePayload(
    List<String> candidates) {}
~~~

input不含domain/materialType/Corpus alias/Profile/provider/model/prompt/filter/ACL/DSL/topK/timeout。adapter使用版本化`DOCUMENT_REWRITE`模板；Vendor只返回ordered plain strings。06只做wire count/string/control/schema cap，不trim后补齐、不生成intent/confidence、不删除超量项使其“变合法”；响应超count/char整体`INVALID_RESPONSE/LIMIT_EXCEEDED`，04再执行NFKC、DSL拒绝、去重和original比较。

### 10.5 Embedding contract

~~~java
public record DocumentEmbeddingInputProjection(List<String> texts) {}

public record DocumentUntrustedEmbeddingPayload(
    List<List<Float>> vectors,
    int dimension,
    DocumentEmbeddingBindingReference bindingReference) {}

public record DocumentEmbeddingValue(
    List<Float> vector,
    int dimension,
    DocumentEmbeddingBindingReference bindingReference) {}
~~~

contract保留bounded list以承接`maxEmbeddingTexts`，但04当前严格要求texts.size=1、response vectors.size=1。request不带provider/model/expectedModel/expectedDimension；adapter active binding决定vendor/model。06验证vector count、每个dimension、finite元素、actual list length和`maxEmbeddingDimensions`，不平均多向量、不截断/补零、不在404/405后切`/embed`。agent client从唯一vector构造`DocumentEmbeddingValue`；04和ES manifest继续复核binding与index vector policy。

### 10.6 Rerank contract

~~~java
public record DocumentRerankInputProjection(
    String queryText,
    List<DocumentRerankInputItem> items) {}

public record DocumentRerankInputItem(
    String candidateId,
    String title,
    String snippet,
    List<DocumentProviderFieldValue> fields) {}

public record DocumentProviderFieldValue(
    CanonicalFieldRef field,
    DocumentProviderScalar value) {}

public sealed interface DocumentProviderScalar
    permits DocumentProviderStringValue,
            DocumentProviderBooleanValue,
            DocumentProviderDecimalValue,
            DocumentProviderDateValue {}

public record DocumentProviderStringValue(String value) implements DocumentProviderScalar {}
public record DocumentProviderBooleanValue(boolean value) implements DocumentProviderScalar {}
public record DocumentProviderDecimalValue(BigDecimal value) implements DocumentProviderScalar {}
public record DocumentProviderDateValue(LocalDate value) implements DocumentProviderScalar {}

public record DocumentUntrustedRerankPayload(
    List<DocumentRerankScoreItem> scores) {}

public record DocumentRerankScoreItem(
    String candidateId,
    double score,
    DocumentRerankReasonCode reasonCode) {}
~~~

input由04 all-or-none projector形成，不接受`AdapterDocumentResult`、retrievalProfile、domain/materialType、URI、ACL、document/chunk identity、context全文、citation或free metadata。fields是closed canonical field+typed scalar，不是Map。06验证input IDs唯一、response为input子集、无重复、score finite、reason closed、count有界，且Provider未返回文本/fields/citation/order/topN。06不排序；04按已冻结规则排序并追加遗漏/tail。

### 10.7 Generation contract

generation业务contract完全沿用05：`DocumentGenerationInputProjection`、closed instruction/output shape、`DocumentGenerationOperationRequest(input,policyReference,operationContext)`和`DocumentUntrustedGenerationPayload`。06不得接收整个internal ECP、queryText、model、maxOutput散字段或public DTO，也不得返回`DocumentGeneratedTextCandidate`。

adapter vendor模板只接收input evidence与closed instruction；不接收policy reference、candidate/security binding、Invocation、ACL/target/profile/limit/URI。Vendor response必须是strict JSON union；06不去除code fence、不接受`citation:`/`citationId:`别名、不推导citation binding、不删除unknown citation、不截断answer/summary/bullet。任一wire/schema/operational cap问题返回invalid payload failure；05本地factory/verifier决定operation互斥、业务chars/bullets和exact `[C1]` marker语义。

### 10.8 Provider binding 与 activation snapshot

06在adapter-api定义safe binding：

~~~java
public record DocumentProviderBindingReference(
    CapabilityOperationType operationType,
    ProviderSafeIdentity provider,
    String adapterServiceIdentityRef,
    String adapterDeploymentRef,
    String vendorContractVersion,
    String templateOrModelBindingDigest,
    String canonicalDigest) {}
~~~

07拥有并原子发布只读current snapshot：

~~~java
public record DocumentProviderActivationSnapshot(
    CapabilityOperationType operationType,
    DocumentProviderActivationState state,
    Optional<DocumentProviderBindingReference> expectedProvider,
    String wireContractVersion,
    String rolloutVersion,
    Instant validUntil,
    String canonicalDigest) {}

public enum DocumentProviderActivationState { ACTIVE, INACTIVE }
~~~

`provider`表示P1定义的逻辑vendor/model安全身份，供operation metadata、embedding/index、05 candidate、07 quality和03 final currentness使用；`adapterServiceIdentityRef/adapterDeploymentRef`仅表示受控内部Document Provider Adapter服务身份与部署，不冒充P1 Provider。`providerAttempts=1`表示client boundary发起了一次逻辑Provider operation；该operation由一次agent→adapter写入和adapter内最多一次vendor写入实现。两跳真实次数分别由agent本地metadata与adapter受限审计证明，不能相加为2，也不能因内部hop而把metadata provider改成adapter服务名。

`DocumentProviderActivationReadView.requireCurrent(operationType)`是06唯一runtime读取入口。snapshot不含URL/credential/prompt正文/业务budget或endpoint选择；ACTIVE时`expectedProvider`必须present，INACTIVE可empty。06 composition按operation映射唯一固定internal endpoint/client，07只发布该operation允许的provider/contract binding。INACTIVE映射attempts=0 `DISABLED`；snapshot missing/authority failure/expired映射attempts=0 `PROVIDER_UNAVAILABLE`；binding/contract或06 endpoint映射缺失映射attempts=0 `BINDING_MISMATCH`。07决定状态，06只消费且不能从配置重新启用或改endpoint。

### 10.9 DPW-1 internal wire

agent-service与`document-provider-adapter`共享Spring-free strict envelope，不复用Planning/Domain Adapter DTO：

~~~java
public record DocumentProviderWireRequest<T>(
    String wireContractVersion,
    String operationId,
    CapabilityOperationType operationType,
    String requestDigest,
    long absoluteDeadlineEpochMillis,
    String expectedActivationDigest,
    String expectedProviderBindingDigest,
    T input) {}

public record DocumentProviderWireResponse<T>(
    String wireContractVersion,
    String operationId,
    CapabilityOperationType operationType,
    String requestDigest,
    String activationDigest,
    DocumentProviderBindingReference providerBinding,
    T payload) {}

public record DocumentProviderWireError(
    String wireContractVersion,
    String operationId,
    CapabilityOperationType operationType,
    String requestDigest,
    DocumentProviderAdapterFailureCode failureCode,
    String diagnosticId) {}

public enum DocumentProviderAdapterFailureCode {
    REQUEST_REJECTED,
    ACTIVATION_REJECTED,
    DEADLINE_REJECTED,
    REQUEST_ABORTED,
    VENDOR_UNAVAILABLE,
    VENDOR_TIMEOUT,
    VENDOR_INVALID_RESPONSE,
    VENDOR_FAILED
}
~~~

泛型只在四个endpoint的编译期具体签名中使用；controller/client必须声明完整`DocumentProviderWireRequest<DocumentRewriteInputProjection>`等参数化类型，并使用保留泛型的typed reader，禁止raw/wildcard generic、`Object/Map/JsonNode` payload或运行时自由type discriminator。DPW-1 request digest覆盖版本、operationId/type、absolute deadline epoch、expected activation/provider binding和operation-specific canonical input；deadline必须与本地context完全一致且不能被adapter延长。2xx只允许对应typed success；经认证且request header可关联的non-2xx只允许`DocumentProviderWireError`，closed code由agent本地映射，不携带vendor状态/message/body。success必须原样回显request digest，并返回adapter实际观察到的activation digest及与07 snapshot相同的provider binding；任一不一致整包拒绝。envelope不含JWT/ExecutionScope/policy reference/ResourceLimit正文/Provider credential。

401/403、TLS/连接失败或连error header都无法可信解析时，agent仅使用本地HTTP阶段事实映射，不能信任error body。已认证error必须校验wire version、operation、request digest和diagnosticId格式；unknown code/unknown field/digest mismatch映射`INVALID_RESPONSE`。`REQUEST_REJECTED/ACTIVATION_REJECTED`映射`BINDING_MISMATCH`，`DEADLINE_REJECTED`由本地Clock判定为`DEADLINE_EXCEEDED`或`LATE_RESULT`，`REQUEST_ABORTED`映射`CANCELLED`或`PROVIDER_FAILED`，其余vendor code分别映射P1同义failure。adapter failure code只是受控原因证据，不拥有P1 metadata/termination/fallback。

内部endpoint固定：

| operation | endpoint |
|---|---|
| rewrite | `POST /internal/document-providers/rewrite` |
| embedding | `POST /internal/document-providers/embedding` |
| rerank | `POST /internal/document-providers/rerank` |
| generation | `POST /internal/document-providers/generation` |

旧`/document-generation`、`/document-rewrite`和Runtime rewrite endpoint不作为兼容route。内部endpoint不经gateway公开；专用service scope为`agent.document.provider.invoke`。

### 10.10 Agent-side port/client algorithm

每次port固定执行：

1. 验证typed request/input/policy reference/context非空、type一致且input digest重算一致；
2. 从context `resourceLimits.require(DocumentResourceLimit@1.0.0)`取得实际typed value，校验本operation全部count/chars/dimension；
3. 使用注入Clock检查cancel和absolute deadline；失败attempts=0；
4. 读取07 current ACTIVE snapshot，验证provider/wire binding并取得immutable snapshot digest；按operation从06 composition解析唯一internal endpoint；
5. 使用operation-specific serializer把context absolute deadline、expected activation/provider digest和safe input写入DPW body并生成request digest；先计算UTF-8 bytes并满足typed上限与06 operational request cap交集；不通过attempts=0；
6. 进入bounded bulkhead/connection queue；等待也受remaining deadline限制；
7. 紧邻HTTP write再次读取snapshot并核对digest/validUntil，同时重查cancel/deadline；变化则attempts=0；
8. 增加本地outbound attempt到1，发送一次internal request；client/SDK/mesh retry全部关闭；
9. response先按bytes/content-type/status读取；2xx strict解析success并校验request/activation/provider/payload，受控non-2xx strict解析error并本地映射，其他响应按失败contract拒绝；
10. post-check cancel、deadline、activation digest、operation/request/provider binding；cancel/deadline/activation变化优先于2xx success；
11. 本地构造P1 metadata和typed success/failure；原始exception/status/body不出boundary。

ACTIVE snapshot必须有`expectedProvider`；`CapabilityOperationMetadata.provider`由agent-service根据该trusted value的`provider`本地构造，不从DPW response/vendor自报值构造，response binding只能被校验。`providerAttempts`统计client boundary发起的逻辑Provider operation次数，只能0或1；agent→adapter真实write次数与其同步记录，adapter→vendor真实attempt由adapter本地强制0/1并进入受限06/07审计。内部adapter身份使用binding的`adapterServiceIdentityRef`做service-auth校验，不能写入P1 provider字段；两跳任一隐藏retry均阻塞生产readiness。

### 10.11 Adapter-side algorithm

每个internal controller/use case固定执行：

1. 专用service identity/scope、TLS、content-type、request bytes和header格式校验；
2. strict DPW反序列化、operation endpoint/type、request digest、absolute deadline、expected activation/provider binding校验；
3. bounded `DocumentProviderReplayGuard`以service identity + operationId + requestDigest的hash检查本实例短窗重复；重复拒绝且不回放旧response；
4. 读取同一07发布源的local immutable activation snapshot；非ACTIVE或binding mismatch不调用vendor；
5. 验证deadline epoch仍有效且不超过允许clock skew/最大stage horizon；
6. operation-specific validator再次执行count/chars/schema cap；
7. mapper只把safe input映射到版本化vendor request/prompt；DPW metadata不进入vendor body；
8. 进入operation-specific bulkhead，执行最多一次vendor attempt；vendor SDK/proxy/mesh retry和redirect关闭；
9. 流式读取bounded vendor response，strict parse为对应untrusted payload，不做业务修复；
10. post-check deadline、request abort、activation/binding仍相同；无效则丢弃payload；
11. success返回strict DPW response并回显实际activation digest/provider binding；失败仅返回closed DPW error或无body transport status，不返回vendor body/message/header。

adapter不是fallback orchestrator。vendor 404/405、429、timeout或invalid response均结束本operation；不能切另一路径、模型或Provider。

### 10.12 Deadline、timeout 与 cancellation

agent client有效等待=`min(remaining absolute deadline, agent internal stage cap)`；adapter vendor等待=`min(DPW deadline remaining, adapter vendor stage cap)`。connect cap、pool acquire cap、response read cap均包含在剩余时间内，不能每阶段重新获得完整timeout。配置Duration是operational cap，不进入Plan/request业务语义。

`CancellationSignal`对象不序列化。agent client订阅只读signal并中止/关闭internal HTTP exchange；adapter使用支持abort传播的HTTP实现，把client disconnect/request abort和deadline转为vendor subscription cancellation。同步client无法证明断连会停止vendor调用时不得通过生产gate。调用后cancel/deadline发生时，payload永不形成success；优先级为`CANCELLED`、`DEADLINE_EXCEEDED`、stage `PROVIDER_TIMEOUT`、其他failure。

### 10.13 Activation change 与 in-flight operation

06在write前和response后都核对同一snapshot digest。若07在write前disable/rollback，attempts=0；write后变化时best-effort取消对应in-flight exchange并返回non-success，03/05不接收candidate。已发往vendor的数据无法被撤回，系统不宣称零时窗；07定义撤权传播SLA、adapter abort能力和审计，03 final currentness保证结果不返回。

snapshot listener只维护按operation/provider safe key索引的bounded in-flight handle，不保存input/body。完成/cancel后必须删除；listener不是第二状态机或业务task registry。

### 10.14 Typed failure mapping

只使用P1 `CapabilityOperationFailureCode`：

| 场景 | failure code | termination | attempts |
|---|---|---|---:|
| static disabled或07非ACTIVE且未write | `DISABLED` | DISABLED | 0 |
| request/policy/input/typed limit非法 | `INVALID_REQUEST`/`LIMIT_EXCEEDED` | REJECTED | 0 |
| policy/security/binding拒绝 | `SECURITY_REJECTED`/`BINDING_MISMATCH` | REJECTED | 0或1，取决于是否已write；adapter `REQUEST_REJECTED/ACTIVATION_REJECTED`为1 |
| internal adapter不可达/429/503或`VENDOR_UNAVAILABLE` | `PROVIDER_UNAVAILABLE` | FAILED | 1 |
| operational stage cap或`VENDOR_TIMEOUT`先到 | `PROVIDER_TIMEOUT` | FAILED | 1 |
| absolute deadline到期 | `DEADLINE_EXCEEDED` | DEADLINE_EXCEEDED | 0或1 |
| cancellation | `CANCELLED` | CANCELLED | 0或1 |
| 2xx wire/payload非法，或error envelope未知/错绑 | `INVALID_RESPONSE` | REJECTED | 1 |
| vendor/internal未分类失败 | `PROVIDER_FAILED` | FAILED | 1 |
| post-check发现成功迟到 | `LATE_RESULT` | REJECTED | 1 |

401/403来自internal service时映射`SECURITY_REJECTED`并强审计；adapter closed code按10.9映射，vendor status只在adapter内部解释且不原样返回。Handler仅依据P1 typed code与02 feature policy路由，不能按HTTP status/message或adapter code猜fallback。

### 10.15 Strict schema 与 payload validator

两侧ObjectMapper/JSON parser必须启用unknown field拒绝，并限制总bytes、nesting depth、string/list长度和number token。操作规则：

- rewrite：plain string list、count/char/control；不接受object candidate/free metadata；
- embedding：vector count=input count、dimension/length一致、finite、无extra vector/model override；
- rerank：ID子集/唯一、finite score、closed reason、无text/field/citation；
- generation：strict operation union、closed finish reason、bounded raw chars/lists；不做citation语义修复；
- 所有payload：禁止HTML/script/control、credential/token/endpoint/prompt/ACL/target/profile/limit/owner字段；unknown/prohibited任一出现整包拒绝。

验证顺序是bytes→content-type/status→JSON constraints→wire binding→operation payload→post deadline/cancel/activation。不能先构造业务candidate再补安全校验。

### 10.16 Prompt/template 与 model binding

rewrite/generation template位于`document-provider-adapter` operation包的版本化code/resource，不复用Planning prompt，不允许config下发自由prompt。embedding/rerank vendor request由typed mapper生成。active provider binding digest覆盖provider/model safe ref、vendor contract、template/mapper version和关键response schema version；不覆盖credential或endpoint secret。

request不允许选择model。07 activation选择已验证的binding；adapter根据expected binding解析唯一vendor client。unknown/multiple binding、response model/version drift或embedding dimension binding不一致均拒绝，不能自动切备用model。

### 10.17 配置与装配

agent-service只保留内部adapter operational config：service discovery/base URL safe binding、四个固定path、service credential ref、connect/pool/response caps、wire contract version和bulkhead；不保存vendor key/model/prompt、feature policy、business limit或fallback。

`document-provider-adapter`按operation保存vendor endpoint/credential ref/model safe ref/template/mapper version、connect/stage/request/response cap和bulkhead。secret只由受限provider注入；生产禁止明文/API key默认值和公共vendor base URL fallback。07保存activation safe refs/version，不复制URL/credential。

每个operation在agent-service恰有一个active port bean：disabled或HTTP。重复bean、Runtime URL、direct vendor URL、自动retry/redirect、missing service scope、wire version mismatch、unbounded bytes/queue或07 active binding无endpoint mapping均启动/activation失败。disabled bean可存在，但任何REQUIRED Profile不得在07发布ACTIVE前通过readiness。

### 10.18 Multi Agent演进 seam

未来coordinator为每个child创建独立P1 Invocation/ExecutionScope/limits/deadline，再调用同一Document leaf。06 request/reference/metadata继续绑定child invocation/operation；adapter可共享无状态连接池和按Provider的bulkhead，但不能合并不同child文本、共享policy decision、批量拼接ECP或跨child重试。Run/Task/Delegation预算若未来进入P1，只通过收紧后的operation context体现；06 DTO不预留parent/task/worker字段。

## 11. 接口设计

| 接口/类型 | 方法/字段 | 所有者 | 责任 |
|---|---|---|---|
| `DocumentProviderOutboundPolicyDecisionFactory` | `create(type,scope,corpus,feature,fieldView)` | agent-service/06 | 唯一current-scope purpose decision，无I/O |
| `DocumentProviderOperationRequestBinder` | `bind(decision,inputDigest,context)` | agent-service/06 | non-wire policy reference |
| `DocumentQueryRewritePort` | `rewrite(DocumentRewriteOperationRequest)` | agent-service/06 | outcome of untrusted candidate list |
| `DocumentEmbeddingPort` | `embed(DocumentEmbeddingOperationRequest)` | agent-service/06 | outcome of validated embedding value |
| `DocumentRerankPort` | `rerank(DocumentRerankOperationRequest)` | agent-service/06 | outcome of untrusted score list |
| `DocumentGenerationPort` | `generate(DocumentGenerationOperationRequest)` | agent-service/05+06 | outcome of 05 untrusted generation payload |
| `DocumentProviderActivationReadView` | `requireCurrent(operationType)` | 07 owner、06 consumer | immutable current activation |
| `DocumentProviderEndpointRegistry` | `require(operationType)` | 06 composition | operation→唯一固定internal client；07不选择endpoint |
| `DocumentProviderWireCanonicalizer` | `requestDigest` | adapter-api/06 | DPW-1 deadline/activation/provider/input exact canonical |
| `DocumentProviderWireResponseValidator` | `validateSuccess(request,snapshot,response)`、`validateError(request,error)` | agent-service/06 | contract/request/activation/provider/payload或closed error binding |
| `DocumentProviderInternalController` | four fixed endpoints | provider-adapter/06 | service auth + typed use case |
| `DocumentProviderReplayGuard` | `register(serviceIdentity,operationId,requestDigest)` | provider-adapter/06 | 本实例短TTL重复检测，不回放response |
| `DocumentVendorClient` | operation-specific `invoke` | provider-adapter/06 | one vendor attempt，no fallback |

四个port不继承一个有`execute(Object)`的方法；共享仅限P1 operation types、policy/binder、wire envelope、transport safety和metadata factory。业务payload validator保持operation-specific。

## 12. 数据设计

本文不新增数据库表或业务cache：

| 数据 | 生命周期 | 持久化 |
|---|---|---|
| outbound decision/reference | agent-service当前Invocation | 否 |
| input/DPW request/response/untrusted payload | 单operation内存/HTTP | 否 |
| activation snapshot | 07权威存储发布的本地immutable view | 06不另存第二current state |
| in-flight handle | operation/provider keyed bounded registry | 否；无body/input |
| replay guard key | adapter单实例短TTL hash(service identity,operationId,requestDigest) | 否；不存body/response，不宣称集群exactly-once |
| Provider binding/template/model report | 07 validation/rollout | 由07定义，06只safe ref |
| operation metadata/audit fact | P1 finalization/受限审计 | 只safe metadata，不含正文 |

允许audit：operation type、safe provider/model/deployment ref、wire/template/mapper safe version、attempts、duration、termination、failure code、diagnosticId、limit/decision/request/activation safe digest、counts/bytes、deadline/cancel/availability touched。禁止query/snippet/evidence/vector/generated text、citation/candidate/document ID、ACL/target/Profile/Policy正文、URL/credential/prompt/vendor body或exception message。

## 13. 状态流转设计

~~~text
LOCAL_VALIDATION
  -> DISABLED_OR_REJECTED (attempts=0)
  -> ACTIVATION_BOUND
  -> READY_TO_WRITE
  -> INTERNAL_ATTEMPT_STARTED (attempts=1)
       -> ADAPTER_VALIDATED
       -> VENDOR_ATTEMPT_STARTED (adapter local 1)
       -> WIRE_RESPONSE_VALIDATED
  -> SUCCEEDED | FAILED | CANCELLED | DEADLINE_EXCEEDED | REJECTED
~~~

这些是一次方法内trace阶段，不是持久状态机、checkpoint或第二Lifecycle。P1 `CapabilityOperationMetadata.termination`是唯一operation终态；adapter local vendor stage只用于受限诊断/07 readiness，不对public API暴露。

## 14. 幂等、事务与一致性设计

- Provider调用只读但可能计费；operationId用于correlation和重复发送检测，不是业务幂等或重放授权。
- 同operationId第二次internal write是实现缺陷，agent client与adapter单实例bounded replay guard拒绝并告警；不自动重放response。它是防御检测，不宣称跨实例exactly-once，正确性仍依赖两跳retry关闭和operationId唯一。
- agent→adapter和adapter→vendor各最多一次；DPW request digest防串包，不授权retry。
- DPW-1、policy decision/reference和input canonical在相同trusted输入下确定；Vendor输出可非确定，仍受binding/validator。
- activation snapshot在write前冻结digest并在post-check复核；变化后不返回success。
- 无跨agent-service/provider-adapter/vendor/07的分布式事务；使用fail-closed、deadline/cancel、binding和审计控制窗口。
- 06不写Context/result/audit业务表；P1 finalization决定最终成功/失败与必要审计提交。

## 15. 权限、风控与审计设计

1. current ExecutionScope只进入本地decision factory，不进入operation input、DPW或adapter。
2. policy reference绑定decision/input/context但不序列化；Provider看不到policy/permission evidence或limit。
3. agent-service到adapter使用专用服务身份/mTLS或受控service token scope；不转发用户JWT。
4. adapter endpoint不经gateway公开；非agent-service身份、scope、contract或binding拒绝且0 vendor attempt。
5. vendor credential只在adapter client boundary解析，不进入properties dump、Actuator、DTO、metadata或日志。
6. URL/path/provider/model不能来自caller/Plan/input；07 safe binding + composition registry精确选择。
7. request/response均先bytes/strict schema/binding再使用；Map/JsonNode只允许vendor parser内部瞬时树且不能跨wire/port返回，优先typed DTO。
8. generation不做citation alias/截断/推导；embedding不切endpoint/平均/补零；rerank不返回文本；rewrite不返回DSL。
9. availability change触发pre-write拒绝或in-flight best-effort abort；post-check失败不返回candidate。
10. security rejection、attempt>1、binding drift、credential/URL异常、Runtime/direct vendor回归为强制审计/告警。

## 16. 性能与容量设计

| 阶段 | 上限/复杂度 | 防护 |
|---|---|---|
| outbound decision | O(fields) | bounded field view、canonical sorted rules、无I/O |
| rewrite | O(query+candidates) | maxQuery/maxRewrite/count/response bytes |
| embedding | O(texts×dimension) | maxTexts/maxDimensions、finite streaming parse、当前1 text |
| rerank | O(items×safe fields) | maxRerankCandidates/snippet/field count、无全文 |
| generation | O(ECP chars+output chars) | 05 context/evidence/output caps + wire bytes |
| DPW canonical | O(request bytes) | streaming digest/serializer，不materialize日志副本 |
| bulkhead | bounded queue/concurrency | queue等待计入deadline；full立即unavailable |
| cancellation registry | O(in-flight operation) | bounded handle、完成即删除、无body |

agent-service与adapter各只保留当前input、wire bytes或parsed payload必要副本；不得同时记录vendor body、DPW JSON和业务candidate多份。response cap在读取流时执行，不能先让ObjectMapper加载无界body。

## 17. 兼容性与扩展性设计

### 17.1 原子迁移目标

- `document-generation-adapter`模块/artifact/application name重命名为`document-provider-adapter`；不长期保留两个服务名。
- generation/rewrite/embedding/rerank统一走四个internal endpoint；agent-service不直连vendor或Runtime。
- 旧四类request/result/exception接口替换为typed operation request/outcome；无双active port。
- Runtime `/document/rewrite`与core实现删除；Planning Runtime只保留Route/Plan。
- embedding `/embeddings`→404/405→`/embed` fallback、queryVariants平均、request provider/model/dimension字段删除。
- rerank `AdapterDocumentResult/retrievalProfile` request和Map body删除。
- generation旧query/model/ECP request、citation alias修复、binding推导和substring truncation删除。
- `AgentProperties`中的feature/Profile/business limit/fallback/provider direct URL/model/dimension迁往02 typed contract、07 activation或adapter operational config；不双读。

### 17.2 发布顺序

同一M0 Release Unit内按构建依赖顺序完成：新adapter-api contract→新provider-adapter四endpoint/disabled vendor实现→agent-service新ports/clients/policy/activation→contract/integration/readiness测试→配置/服务名原子切换→删除旧Runtime/direct clients/DTO/config/tests。可以在非生产测试环境先验证新服务，但生产/共享环境不允许双调用、shadow发送真实query/evidence或长期compat route。

### 17.3 新Provider/operation

新增vendor只增加adapter operation binding/mapper/client/config/07 report，不修改Handler/port/input contract；新增Document Provider operation必须同时增加受控operation type、typed input/payload、policy purpose、limit consumer、DPW endpoint/validator、07 gate和测试，不通过`Map/extensions/free prompt`扩展。是否拆出跨capability Provider平台需独立ADR；当前Document adapter不预留万能SPI或动态脚本。

## 18. 日志、监控与告警

### 18.1 Metrics

- `agent_document_provider_operation_total{operation,termination,failure}`；
- `agent_document_provider_duration_seconds{operation,termination}`；
- `agent_document_provider_attempts{operation,hop}`；
- `agent_document_provider_wire_bytes{operation,direction,outcome}`；
- `agent_document_provider_activation_total{operation,state,outcome}`；
- `agent_document_provider_binding_total{operation,outcome,reason}`；
- `agent_document_provider_cancel_total{operation,stage}`；
- `document_provider_vendor_operation_total{operation,termination}`。

provider/model使用受控低基数safe ID；operationId/invocationId/digest/query/candidate不作tag。

### 18.2 Log/audit

structured log仅记录requestCorrelation safe ref、operation/stage/termination/failure、attempts、duration、counts/bytes、safe binding/version、deadline/cancel/availability touched、diagnosticId。普通日志不记录operationId全值、input/body/vector/text/citation、vendor error body/header或credential。审计按P1/07保留必要safe refs和change/rollout关联。

### 18.3 告警

- agent或vendor hop attempt>1、same operationId duplicate write；
- Runtime/direct vendor URL或旧endpoint被调用；
- activation unknown/expired/binding drift或active无endpoint mapping；
- deadline后success、cancel不传播、in-flight handle泄漏；
- unknown/prohibited field、response bytes、invalid vector/rerank/citation payload；
- adapter service auth failure、credential缺失/泄漏、retry/redirect开启；
- required feature在07非ACTIVE、Provider late/invalid率或bulkhead拒绝持续升高。

## 19. 实现落点清单

### 19.1 agent-adapter-api

| 序号 | 路径 | 类/动作 | 变更 |
|---:|---|---|---|
| 1 | `agent-adapter-api/.../document/provider` | `DocumentProviderBindingReference`、`DocumentProviderOutboundPolicyReference` | 新增Spring-free safe refs |
| 2 | 同包/wire | `DocumentProviderWireRequest/Response`、DPW canonicalizer | 新增strict generic envelope；无Object/Map |
| 3 | 同包/rewrite | input/operation request/untrusted payload/language | 新增/替换旧rewrite DTO |
| 4 | 同包/embedding | input/operation request/untrusted payload/binding/value | 新增/替换旧embedding DTO |
| 5 | 同包/rerank | input item/field/operation request/score payload/reason | 新增/替换旧rerank DTO |
| 6 | `.../document/generation` | 05 input/request/untrusted payload | 增加policy reference并按05冻结字段 |

### 19.2 agent-service

| 序号 | 路径 | 类/动作 | 变更 |
|---:|---|---|---|
| 1 | `.../capability/document/provider/security` | outbound decision factory/canonicalizer/request binder/verifier | 新增；四operation唯一policy seam |
| 2 | `.../capability/document/provider/activation` | 07 read view consumer、pre-write/post-check/in-flight cancel | 新增；不建第二current state |
| 3 | `.../capability/document/provider/wire` | endpoint registry、DPW client/canonical/validator、metadata factory | 新增共享transport safety |
| 4 | `.../document/rewrite` | typed port、HTTP/disabled实现 | 重写；删除Runtime client/request/response |
| 5 | `.../document/embedding` | typed port、HTTP/disabled实现 | 重写；删除Map、direct vendor、endpoint fallback/average |
| 6 | `.../document/rerank` | typed port、HTTP/disabled实现 | 重写；删除AdapterDocumentResult/Profile request |
| 7 | `.../document/generation` | 05 typed port、HTTP/disabled实现 | 重写；只返回untrusted payload |
| 8 | `.../config` | internal adapter operational properties/validators | 新增；删除Document provider业务散配置 |
| 9 | composition/tests | 每operation exactly-one bean、consumer declaration/readiness | 重写 |

### 19.3 document-provider-adapter

| 序号 | 路径 | 类/动作 | 变更 |
|---:|---|---|---|
| 1 | module/pom/application | `document-generation-adapter`→`document-provider-adapter` | 原子重命名 |
| 2 | `.../internal` | four controllers/use cases/service auth/DPW validators | 新增/替换公开旧controller |
| 3 | `.../internal/security` | bounded `DocumentProviderReplayGuard` | 新增单实例短窗重复检测；不持久化正文/response |
| 4 | `.../rewrite` | template/mapper/vendor client/parser | 新增 |
| 5 | `.../embedding` | mapper/vendor client/vector parser | 新增/disabled until selected |
| 6 | `.../rerank` | mapper/vendor client/score parser | 新增/disabled until selected |
| 7 | `.../generation` | strict template/mapper/parser | 重写；删除citation修复/截断 |
| 8 | `.../activation` | 07 snapshot consumer/binding verifier | 新增 |
| 9 | resources/config | operation-specific vendor operational config/secret refs | 重写；无默认公网URL/API key |

### 19.4 删除与零残留门禁

实施后main source/config下列模式必须零命中或只存在迁移负例：

~~~text
RuntimeDocumentQueryRewriteClient|/runtime/v1/document/rewrite|app/core/document_rewrite
HttpDocumentEmbeddingClient.*embedViaTextEndpoint|supportsEmbedFallback|queryVariants|expectedModel|expectedDimension
DocumentRerankRequest.*retrievalProfile|AdapterDocumentResult
DocumentGenerationRequest.*queryText|model|EvidenceContextPackage|maxOutputChars
DeepSeekDocumentGenerationClient.*stripCitationLabel|normalizeCitationMarkers|substring
agent.document.(rewrite|embedding|rerank|generation).*(model|dimension|failure-policy|max-context|max-output)
document-generation-adapter|/document-generation|/document-rewrite
Map<String,Object>|Map<String, Object>
~~~

Map零命中按provider adapter vendor mapper的受控第三方request构造例外白名单处理，但port/wire/payload和agent-service client不得使用Map。例外必须具体到类/方法并有strict response test，不能全目录放行。

## 20. 测试设计与验收命令

### 20.1 Policy/request单元测试

- 四operation current scope allow/deny、feature mismatch、Policy/Permission/version/classification/Mask unknown、validUntil；
- DPO-1顺序/length-prefix/digest；不同operation/Corpus/field/mask/evidence变化digest变化；
- input canonical/reference Invocation/operation/type/limit/input/expiry mismatch为0attempt；
- 04 rewrite/embedding/rerank和05 generation均只引用同一decision factory/binder，无第二evaluator。

### 20.2 Port/client contract测试

- typed limits require、0语义、count/chars/dimension/checked overflow；
- disabled/activation unknown/expired/mismatch在write前attempts=0；
- DPW request/response version/operationId/type/request digest/absolute deadline/activation/provider binding exact；
- 2xx success与authenticated non-2xx closed error互斥；unknown/error digest错绑/原始vendor message全部拒绝；
- unknown/prohibited field、content-type、status、bytes/depth/list/string/number限制；
- local metadata的attempt/duration/termination/diagnostic/limit/deadline/cancel touched不信任response；
- rewrite超量/DSL对象、embedding多余vector/nonfinite/dimension、rerank unknown/duplicate/text、generation code fence/alias/超cap；
- client不截断/补零/平均/别名化/推导candidate，不切endpoint/provider/model。

### 20.3 Deadline/cancel/attempt测试

- pre-cancel/pre-deadline 0attempt；queue等待、connect、read、vendor cap均取remaining deadline；
- response与cancel/deadline竞态，cancel/deadline优先，late 2xx不成功；
- activation在serialize前、write前、in-flight、response后变化；0/1attempt和abort/post-reject正确；
- agent HTTP、adapter vendor SDK、service mesh retry/redirect全部关闭；404/405不第二调用；
- same operationId duplicate write拒绝；in-flight handle完成/cancel无泄漏。
- adapter replay guard重复请求0 vendor attempt、TTL/容量有界，且测试不把它当集群exactly-once。

### 20.4 Adapter/security测试

- internal endpoint专用身份/scope、无gateway route、无用户JWT转发；
- DPW envelope不进入vendor body；policy/context/limit/activation metadata不外发；
- vendor credential不在DTO/log/Actuator/error；无默认公网URL/API key；
- adapter local activation/binding/deadline/request abort；vendor attempts 0/1；
- prompt/template版本binding，Planning prompt不可引用；
- vendor raw error/body/header不会返回agent-service。

### 20.5 集成/架构测试

- `agent-service -> document-provider-adapter -> vendor stub`四operation typed contract；
- Runtime没有Document rewrite，agent-service没有direct vendor client；
- 04/05 required/optional/fallback仅在Handler，06/adapter无fallback composer/Result projector；
- 07 rollback使后续write为0attempt，在途operation不形成success，03 final guard拒绝旧binding；
- architecture rule：Core/Planning Runtime/Domain Adapter Registry不依赖Document Provider类型；
- architecture rule：operation request内嵌context，Domain Adapter仍双参数；
- architecture rule：Provider/model/baseUrl不在Plan/input/AgentProperties业务配置；
- Multi Agent模拟两个child，context/decision/limits/operationId完全隔离，adapter不聚合正文。

### 20.6 建议命令

~~~powershell
.\mvnw.cmd -f serviceCenter\pom.xml -pl agent-adapter-api,agent-service,document-provider-adapter -am test
rg -n "RuntimeDocumentQueryRewriteClient|/runtime/v1/document/rewrite|embedViaTextEndpoint|supportsEmbedFallback|retrievalProfile|stripCitationLabel|normalizeCitationMarkers" agent-service agent-runtime document-provider-adapter
rg -n "queryText|model|EvidenceContextPackage|maxOutputChars" agent-adapter-api\src\main\java\com\dylan\agent\adapter\api\document\generation
rg -n "document-generation-adapter|/document-generation|/document-rewrite" pom.xml serviceCenter config-service agent-service document-provider-adapter
git diff --check
git status --short
~~~

第一个命令在模块重命名实施后执行；设计评审阶段不宣称其当前可运行。零命中规则需排除明确迁移负例测试，不能通过删除测试或放宽regex制造通过。

## 21. 风险与待确认事项

| 风险/待确认 | 触发场景 | 影响 | 处理/门禁 | 是否阻塞本文 |
|---|---|---|---|---|
| 模块重命名/统一endpoint未授权 | 替换generation adapter和embedding/rerank direct client | Maven/config/service discovery调用中断 | M0 caller/config/deploy/runbook清单+原子Release Unit | 不阻塞设计，阻塞实施 |
| 真实embedding/rerank vendor未选 | feature启用 | 无法形成binding/quality/capacity证据 | disabled port + 07 gate；不配置默认vendor | 不阻塞结构，阻塞对应生产feature |
| 07 activation snapshot设计已闭合但尚未实现 | HTTP Provider可能发送 | disable/rollback不能pre-write生效 | 按 07 唯一发布源、read view、传播 SLA 与 readiness 设计实施并验证 | 阻塞真实Provider调用 |
| 两跳cancellation无法证明 | synchronous adapter断连不终止vendor | 取消后仍计费/处理敏感数据 | 使用可abort transport并做integration gate；否则生产禁用 | 阻塞对应Provider生产启用 |
| 已write后紧急disable | vendor已收到input | 数据无法撤回 | pre-write双检、in-flight abort、post-reject、07传播SLA/审计；不宣称零时窗 | 不阻塞设计 |
| Provider data-sharing purpose未在Policy闭合 | query/evidence分类未知 | 外发越权 | shared decision DENY、0attempt；高敏Corpus feature禁用 | 阻塞对应operation |
| adapter集中导致容量热点 | 多operation/未来多child并发 | queue/latency放大 | operation/provider独立bulkhead、容量gate、水平扩展；不在port聚合 | 不阻塞设计 |
| 两跳attempt审计混淆 | P1逻辑operation attempts=1、内部两跳事实另计 | 隐藏retry未发现或Provider identity错写为adapter | P1 metadata记录逻辑Provider与0/1 operation；agent/adapter受限审计分别记录两跳真实write；07同时gate | 不阻塞设计 |
| strict vendor contract未定 | Provider响应漂移 | invalid response率高 | disabled/fake完成结构；真实contract+Gold gate后ACTIVE | 不阻塞文档 |
| 当前配置含默认公网URL/散业务预算 | 环境变量缺失或旧profile仍active | 误连外部/预算多源 | 新config validator+static zero residual+secret scan | 阻塞实施 |

## 22. 评审记录

| 轮次 | 日期 | 结论 | 主要问题与处理 |
|---:|---|---|---|
| 1 | 2026-07-13 | 不通过 | request/context/outcome不符合P1；generation返回trusted candidate；rewrite侵入Runtime；embedding隐藏第二endpoint/平均；rerank传完整Adapter result；generation修复citation/截断；三种部署与凭据/availability/attempt/cancel/wire边界分裂 | 全文重写为shared outbound decision、typed request/outcome、统一DPW-1、单Document Provider Adapter、07 activation、strict untrusted payload和原子迁移 |
| 2 | 2026-07-13 | 不通过 | 07 snapshot携带endpoint会侵入06 composition；DPO-1漏authorization/limit binding；两跳attempt与Provider identity未区分 | endpoint归06固定映射；decision补授权/limit/field rule；provider binding拆分逻辑Provider与adapter部署身份，继续复核wire可执行性 |
| 3 | 2026-07-13 | 通过 | DPW-1缺absolute deadline/activation digest和closed failure wire；P1 Provider identity一度被内部adapter身份替代 | request绑定deadline/activation/provider，success回显observed activation，新增closed error contract；P1 metadata使用逻辑vendor/model safe identity，adapter身份单列；终审S0=0、S1=0 |

第3轮已完成wire generic、deadline/activation、两跳attempt/cancel、P1 metadata、04/05 contract和模块迁移复审，当前S0=0、S1=0；最终结论以本文档同目录下的同名评审报告为准。

## 23. 实施对齐检查

- [x] 四类Provider operation type/input/request/outcome与P1 context/metadata已冻结。
- [x] shared current-scope outbound decision/reference是四operation唯一policy seam。
- [x] request内嵌context；Domain Adapter双参数SPI未被改写。
- [x] Plan/input不携带provider/model/endpoint/credential/timeout/retry。
- [x] agent-service只调用统一Document Provider Adapter，不直连Runtime/vendor。
- [x] DPW-1 strict envelope、provider binding和request digest已冻结。
- [x] DPW-1 absolute deadline/activation digest与closed error wire已冻结，P1 failure由agent本地映射。
- [x] 07 current activation在HTTP write前后fail closed，不能被配置放宽。
- [x] agent/vendor两跳各0/1 attempt，无retry/endpoint/model fallback。
- [x] rewrite/embedding/rerank/generation各自payload validator和“不修复”边界已冻结。
- [x] deadline/cancel/late/activation race和in-flight abort语义已冻结。
- [x] credential/config/log/audit/metrics和启动/readiness门禁已冻结。
- [x] 当前单Agent leaf可由未来独立child Invocation复用，不预建聚合层。
- [x] 07评审已承接activation发布、readiness、rollback、SLA与两跳attempt证据。
- [ ] 模块重命名、内部contract/config/secret/旧路径删除尚未获得M0实施授权。

## 24. 任务完成摘要

本文已把Document Provider从四套散乱client/DTO/配置收敛为一条capability-local基础设施链：04/05先通过06共享factory取得current ExecutionScope purpose-specific outbound decision并形成最小input；operation request内嵌non-wire policy reference和P1 context；agent-service绑定07 ACTIVE snapshot后，以包含absolute deadline与activation/provider binding的DPW-1发起一次逻辑Provider operation；目标`document-provider-adapter`再执行最多一次vendor调用并返回strict untrusted payload或closed error，P1 metadata仍由agent按可信逻辑vendor/model binding本地构造。业务候选、fallback、citation和最终Result Security仍归04/05/03/P1。目标实现原子重命名既有generation模块而不新增通用Provider平台，统一四类凭据、attempt、availability和审计边界；未来Multi Agent只复用独立child Invocation，不在06增加coordinator或共享内容状态。本次完成3轮评审，最终S0/S1为0；07设计已闭合activation与治理链，P2_V3全集评审已完成；文档保持In Review，等待用户Approved与M0实施授权。
