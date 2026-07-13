# 有效资源预算与 Capability-local Port 收敛 L2 实施详细设计 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档状态 | In Review |
| 当前版本 | v2.0 |
| 创建/最后更新日期 | 2026-07-13 |
| 适用代码基线 | `816e2c855574da5326379128bfb3e230241d2fe3` |
| 设计层级 | L2 实施详细设计 |
| 适用阶段 | P1_V2 单 Agent 内核收敛 |
| 文档路径 | `docs/design/P1_V2/05_有效资源预算与CapabilityLocalPort收敛_L2实施详细设计_v2.0.md` |
| 权威范围 | Capability resource limit Contract、单调求交、Authorization Snapshot 冻结、同源传递、Capability-local Provider Operation Context/Outcome/Candidate |
| 前置阅读 | L0/L1、P1_V2/00～04 |
| 历史来源 | P1/D02_01、D02_03 与文档证据上下文优化方案的通用资源/Provider seam；仅作来源留档，不再是实施前置 |

## 2. 修订历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | 新 L1 要求 Validator、Handler、Provider、Result Security 使用同一 Effective Capability Resource Limits | 建立 typed limit、operation context/metadata 和 Generated Text Candidate 基线 |
| 2 | 2026-07-13 | 4～24 | cross-layer 评审发现多 ContractRef 容器过度、Provider 只有 limit reference 无实际限额、Planning/Execution budget 混层、收紧证明/operation outcome/candidate binding/配置清理不完整，并错误预设 P1_V2/06 增加 Run/Task budget | 收敛为单 Capability 单 Contract、强类型值和可证明收紧，冻结完整 resolver/context/outcome/candidate 接口、当前配置删除矩阵与 CHAT-only 演进边界 |
| 3 | 2026-07-13 | 8、10.2、10.8～10.11、19 | 第二轮发现 `agent-adapter-api` 的 Adapter SPI 不能反向依赖 `agent-service` operation/limit/cancellation 类型，且 OptionalInt attempts 与“本地必须证明 0/1 次”冲突、evidence/citation 空 marker 约束不足 | 将只读 operation SPI 放入 Spring-free `agent-adapter-api`，由 `CapabilityResourceLimitView/CancellationSignal` 隔离实现；attempts 改为必知 int，并冻结具体 evidence/citation reference |
| 4 | 2026-07-13 | 10.2、10.9、10.11～10.12、11、22 | 第三轮发现 Permission contribution 生成边界不清、通用文本候选误设单一文本字段、Provider failure code 无法区分 operational timeout/late/security rejection，且删除矩阵把 Planning Budget 重新引入 AvailableCapability | 冻结权限边界内的 typed contribution 适配，通用候选仅暴露安全 binding，补齐通用 failure code，并明确 AvailableCapability 不携带任何 Planning/resource budget |

## 3. 文档状态说明

本文处于 **In Review**，用于后续实施拆分。本文不授权代码、公共 API 或生产依赖变更；P1_V2 全套 L2 评审和后续实施授权完成前不得标记 Approved。

## 4. 背景与目标

当前实现把 `maxRepairAttempts/maxPageSize/maxResultRows/maxResultBytes` 分散在 Profile、Policy、PlanningEffectiveScope、ExecutionScope、Domain Projection、Validator 和 `AgentProperties`；Document Validator、Handler、Result Security 又各自读取 generation/evidence/retrieval 配置。Provider request 虽带部分 deadline/requestId，却没有统一 cancellation、同源 typed limits、operation metadata 与 typed failure，rewrite 还直接复用 Planning Runtime。

本文把三种容易混淆的限制彻底拆开：

1. **Planning Budget**：Route/Plan/repair 的总时长与 repair 次数，只属于 Planning；
2. **Effective Capability Resource Limits**：选定 capability 的 rows/bytes/evidence/citation/generation 等类型化业务资源上限，由 Authorization/metadata 边界一次冻结；
3. **Provider Operational Cap**：connect/read timeout、bulkhead、SDK response cap 等部署安全阀，只能提前拒绝或缩短调用，不能扩大/替代授权限额。

目标是让 Validator、Handler、Capability-local Provider 和 Result Security 消费同一 ContractRef/digest/typed value，同时保持 Core 不感知 Document 等具体字段，新 capability 仅增加自己的 limit type/contract/port。

## 5. 设计范围

### 5.1 范围内

- 单个 Capability Definition 声明的单一 resource limit ContractRef、typed intrinsic upper bound 和适用维度。
- Definition/Profile/Policy/Permission/optional request narrowing 的 source-aware 单调求交。
- Authorization Snapshot 冻结、Execution recheck 只收紧、Core 同源传递。
- ExecutionValidationContext、ExecutionContext、Provider Operation Context、ResultSecurityPort 的同值接口。
- capability-local typed request/outcome、operation metadata、deadline/cancellation/attempt 门禁。
- Generated Text Candidate 通用安全 binding 和非文本中间候选处理规则。
- 当前散预算/配置/Runtime rewrite 的精确清理和 P1_V2/06 原子迁移输入。

### 5.2 范围外

- DocumentResourceLimit 的具体字段、默认值和四类 Document Provider DTO，归 P2_V3/02、04～06。
- Provider 厂商、模型、部署形态、SDK 与 endpoint。
- Route/Plan Runtime operation metadata 结构；Planning 仍由 P1_V2/01 管理。
- Multi-Agent Run/Task/Delegation budget、usage ledger、ResultRef 和重试策略；必须由 future Multi-Agent L1 定义。
- 代码实施和外部 HTTP API。

## 6. 上级文档约束

1. 当前 CHAT 的有效资源限额只由 Definition、Profile、Policy、current User Permission 和 optional Request narrowing 形成；`CHAT_ALL` Delegation 是中性 seam，不创建 contribution/storage/type。
2. Definition 声明 resource limit ContractRef、Java type、intrinsic upper bound 和适用维度；请求级值不写回 Definition。
3. Planning 的 Authorization/metadata 边界是唯一 resolver 所有者；Core 只接受 Authorization Execution recheck 返回的同值或可证明更严格值。
4. Validator、Handler、Provider Operation Context、Adapter 和 Result Security 不得读取原始 Profile/Policy/Permission/实现配置重新计算或扩大限额。
5. Capability-local port 由 capability 模块声明、composition root 装配，不进入 Capability Registry、Adapter Registration、Domain metadata 或 Planning Runtime。
6. port 传播同一 absolute deadline、cancellation、correlation 和 Java operation metadata；默认一次调用，禁止不可见自动重试。
7. Provider 返回的文本、向量、排序或其他候选均不可信；最终 Handler output 必须满足 Registration output ContractRef 并经过统一 Result Security。
8. 当前不定义 Run/Task remaining budget；future 输入只能在 Multi-Agent L1 冻结后作为额外收紧来源接入 resolver。

## 7. 关联文档与边界

| 文档 | 本文依赖 | 本文输出给对方 |
|---|---|---|
| P1_V2/01 | ContractRef、Java schema/enum 权威规则 | resource limit/candidate 类型必须纳入契约 allowlist 与 drift gate |
| P1_V2/02 | Capability Definition/Registration、Core 时序、Execution contexts | Definition declaration、Core 同源传递与 output validation 接口 |
| P1_V2/03 | PlanningEffectiveScope、Authorization Snapshot/ExecutionScope、Result Security | contributions、冻结值、recheck 证明和 `secure` 的 limits 参数 |
| P1_V2/04 | Adapter SPI operation context | Adapter 与 capability-local port 使用同一 invocation/deadline/limits seam |
| P1_V2/06 | 纵向原子迁移和旧路径删除 | 精确删除矩阵、startup gate、验证命令 |
| P2_V3/02 | Document Profile 和 typed limits | 实现 `DocumentResourceLimit` 与各层 contribution |
| P2_V3/04～06 | Document orchestration/provider port | 具体 operation type、request/outcome、候选校验和 provider client |

## 8. 设计边界与不变量

| 不变量 | 强制规则 |
|---|---|
| 单 Capability 单 Contract | 当前选定 capability 只绑定 Definition 的一个 resource limit ContractRef；不使用 Map 容器预留多 Contract |
| Java 强类型 | limit/contribution/request/outcome/candidate 不使用自由 `Map<String,Object>` 或字符串 JSON |
| Resolver 单一所有者 | 只在 Authorization/metadata 边界计算；Core/Handler/Provider/Projector 不 resolve |
| 单调不放大 | Request 和 Execution recheck 只能得到与 Snapshot 相同或更严格值；无法证明则 fail closed |
| 同源传递 | 正确性由 ContractRef、type、canonical digest 和 binding identity 证明，不以 JVM `==` 证明 |
| Budget 分层 | Planning repair budget、absolute deadline、capability resource limits、provider operational cap 不相互替代 |
| 最小 Provider 输入 | 只含已授权/已验证业务输入、operation context 和必要 typed limit；无 JWT/完整 Scope/权限正文/mask |
| 一次 attempt | 当前 Provider 每个 operation 最多一次外部 attempt；自动 retry 配置必须关闭 |
| 候选不可信 | Provider success 不是最终成功；迟到、取消、limit mismatch、invalid metadata/candidate 均不得进入 secured result |
| 无新层级 | Registry/Contract/Context 是同进程内值与查找组件，不拆微服务、不增加通用 Provider Orchestrator |
| CHAT-only | 不创建 RunBudget、TaskBudget、DelegationBudget、ResultRef 或 usage ledger 空壳 |
| 模块依赖单向 | `agent-adapter-api` 只依赖 `agent-api`；不得引用 `agent-service` 的 ExecutionScope、CancellationToken、resolver 或实现类 |

## 9. 总体设计

```text
CapabilityResourceLimitDeclaration (Definition)
  + PROFILE contribution
  + POLICY contribution
  + PERMISSION contribution
  + optional REQUEST narrowing
        -> Authorization/metadata::CapabilityResourceLimitResolver
        -> EffectiveCapabilityResourceLimits
             (single ContractRef + typed immutable value + canonical digest + binding identity)
        -> AuthorizationSnapshot freeze

AuthorizationExecutionPort.recheck
        -> same or stricter EffectiveCapabilityResourceLimits
        -> ExecutionScope
             ├─ ExecutionValidationContext -> Validator
             ├─ ExecutionContext -> Handler
             │      └─ CapabilityOperationContext -> capability-local typed Port
             └─ ResultSecurityPort.secure(..., same limits)

Provider typed Outcome + operation metadata
        -> Handler validates intermediate candidate
        -> Registration-bound output candidate
        -> Result Security / Generated Text Candidate gate
```

Planning Budget 不进入上述 Contract；absolute deadline 作为所有阶段共享的独立字段传播。

## 10. 详细功能设计

### 10.1 Planning Budget、Resource Limit 与 Operational Cap

| 类别 | 例子 | 所有者 | 消费方 | 是否进入 Authorization Snapshot |
|---|---|---|---|---:|
| Planning Budget | maxTotalDuration、maxRepairAttempts | Profile/Policy + Planning | Route/Plan/repair | 否，Planning checkpoint 只存安全摘要 |
| Capability Resource Limit | maxRows、maxResultBytes、evidence/citation/generation 上限 | Definition + Authorization/metadata resolver | Validator/Handler/Provider/Result Security | 是 |
| Absolute Deadline | Caller 入口生成的绝对时刻 | Invocation Handle/Lifecycle | 全链所有阶段 | Snapshot 绑定引用，不作为 limit value |
| Provider Operational Cap | connect timeout、bulkhead、SDK response cap | composition root/provider client | Provider client | 否；只能进一步拒绝/缩短 |

`maxRepairAttempts` 从 `ExecutionBudget/ExecutionScope/AvailableCapability` 删除，只保留在 `PlanningBudgetLimits`。Provider `timeout=min(operationalStageCap, absoluteDeadline-now)`；不得把每个阶段配置 timeout 重新当作完整 deadline。

### 10.2 Java 权威类型

```java
// agent-adapter-api: Spring-free execution SPI
public interface CapabilityResourceLimit {}

public interface CapabilityResourceLimitView {
    <T extends CapabilityResourceLimit> T require(ContractRef ref, Class<T> type);
    ResourceLimitReference reference();
}

public record ResourceLimitDimension(String value) {}

public record CapabilityResourceLimitDeclaration<T extends CapabilityResourceLimit>(
    ContractRef contractRef,
    Class<T> limitType,
    T intrinsicUpperBound,
    Set<ResourceLimitDimension> applicableDimensions) {}

public enum ResourceLimitSource {
    PROFILE, POLICY, PERMISSION, REQUEST
}

public record CapabilityResourceLimitContribution<T extends CapabilityResourceLimit>(
    ResourceLimitSource source,
    ContractRef contractRef,
    Class<T> limitType,
    T upperBound,
    String evidenceRef) {}
```

`ResourceLimitDimension` 是受校验的 Java 值类型，不是通用 enum；具体 contract 定义稳定 dimension 常量，新 capability 不修改共享 enum。Definition 的 intrinsic upper bound 单独输入，不伪装为 contribution。

`CapabilityResourceLimit`、`CapabilityResourceLimitView` 和 `ResourceLimitReference` 位于 Spring-free `agent-adapter-api`，只依赖 `agent-api` 的 `ContractRef`；declaration/contribution/contract/resolver/Effective 实现位于 `agent-service`。这样 Adapter 与 capability-local port 可消费同一只读 view，而不会形成 `agent-adapter-api -> agent-service` 反向依赖。

PROFILE、POLICY、PERMISSION 对选定 ContractRef 都是必需来源；任何来源缺失/重复、type/ref 不匹配或 evidenceRef 无效均 fail closed。PERMISSION contribution 由 Authorization/metadata 边界依据当前 `UserPermission` 权威事实和 contract-specific adapter 形成，不要求 auth-service 公共 DTO 复制所有 capability limit subtype；adapter 缺失、当前权限证据不足或无法形成完整 typed value 时 fail closed。若某层不额外收紧，仍必须由该层基于 Definition 上限形成显式、有 evidence 的同类型 contribution，禁止 resolver 自行填“无限”。REQUEST 是可选 narrowing；缺失表示“不追加收紧”，存在时必须先证明不大于前三层交集。

当前不声明 DELEGATION/RUN/TASK source。未来 Multi-Agent L1 若增加来源，只扩展 contribution 输入和证明规则，不改变消费者接口。

### 10.3 CapabilityResourceLimitContract

```java
public interface CapabilityResourceLimitContract<T extends CapabilityResourceLimit> {
    ContractRef contractRef();
    Class<T> limitType();
    Set<ResourceLimitDimension> supportedDimensions();
    void validate(T value);
    T intersect(T left, T right);
    boolean isSameOrStricter(T candidate, T baseline);
    String canonicalDigest(T value);
}
```

约束：

- `intersect` 对合法值满足交换、结合、幂等；结果必须 `isSameOrStricter(result,left/right)`。
- `isSameOrStricter` 必须覆盖每个 supported dimension，不能只比较 digest/对象身份。
- `canonicalDigest` 使用 contract 自己的版本化 canonical form + SHA-256 lowercase hex；集合稳定排序，禁止 `hashCode/Objects.hash`、Java serialization 和自由 Map。
- 数值 0 的语义由具体 contract 明确为“禁止消费”或非法值，不能被通用层解释为 unlimited。
- Unknown dimension、NaN/负数/溢出、type mismatch 和 unsupported optional field 一律拒绝。

### 10.4 Registry 与启动门禁

`CapabilityResourceLimitRegistry.require(ContractRef,Class<T>)` 按 ContractRef 精确返回唯一 contract；duplicate/missing/type mismatch 启动失败。Registry 不保存请求值、Profile/Policy/Permission 或 provider 配置。

`CapabilityResourceConsumerDeclaration(consumerId,contractRef,requiredDimensions)` 由 Capability Registration/composition root 静态装配，用于声明 Validator、Handler、各 Provider Port 和 Result Projector 消费的维度。启动 gate 必须同时验证：

1. Definition declaration 的 ContractRef/type 可解析；
2. declaration dimensions 非空且是 contract supportedDimensions 子集；
3. Profile/Policy/Permission contribution source 能为该 ContractRef 形成完整 typed value；
4. 每个 consumer 的 requiredDimensions 是 declaration dimensions 子集；
5. Provider port request 编译期依赖正确 typed limit 或从 operation context 精确 `require`；
6. output/context projector 声明的 rows/bytes/evidence/citation/text 等维度被 contract 覆盖；
7. 同 capability 不存在第二 resource ContractRef 或散字段 fallback。

### 10.5 Resolver 与冻结算法

```java
public interface CapabilityResourceLimitResolver {
    EffectiveCapabilityResourceLimits resolve(
        String invocationId,
        String requestCorrelationId,
        String registrationIdentity,
        String authorizationEvidenceDigest,
        CapabilityResourceLimitDeclaration<?> declaration,
        List<CapabilityResourceLimitContribution<?>> contributions,
        Instant frozenAt);
}
```

算法固定为：

1. 按 ContractRef 解析 contract，核对 declaration type/dimensions/intrinsic value；
2. 精确收集 PROFILE/POLICY/PERMISSION 各一项，按固定 source 顺序校验；
3. 从 intrinsic upper bound 开始逐项 `intersect`；
4. 若存在 REQUEST，先验证其只涉及 declared dimensions，再证明 `isSameOrStricter(request,current)` 后求交；
5. 对最终值执行 `validate`、逐来源单调断言和 canonical digest；
6. 绑定 invocation/correlation/registration/authorization evidence 后构造不可变 Effective value；
7. 任一步失败不形成 Authorization Snapshot，不调用 Runtime Plan。

`CapabilityScopeSelection` 中的 request narrowing 只能来自 Java 已验证/受控的请求字段，不能信任 Runtime Raw Plan 作为 Planning 阶段授权输入。Runtime 只能在已冻结上限内选择具体 page/size/evidence 等值，Validator 再校验。

### 10.6 EffectiveCapabilityResourceLimits 与引用

当前一个 selected capability 只有一个 ContractRef，因此不使用 `Map<ContractRef,value>`：

```java
public final class EffectiveCapabilityResourceLimits
    implements CapabilityResourceLimitView {
    ContractRef contractRef();
    Class<? extends CapabilityResourceLimit> limitType();
    <T extends CapabilityResourceLimit> T require(ContractRef ref, Class<T> type);
    ResourceLimitReference reference();
    String canonicalDigest();
    ResourceLimitBindingIdentity bindingIdentity();
}

public record ResourceLimitBindingIdentity(
    String invocationId,
    String requestCorrelationId,
    String registrationIdentity,
    String authorizationEvidenceDigest,
    Instant frozenAt) {}

public record ResourceLimitReference(
    ContractRef contractRef,
    String canonicalDigest,
    String invocationId,
    String registrationIdentity) {}
```

typed value 私有保存在 Effective 对象内，不通过 `Object value()`、Map 或 JSON 暴露。`require` 同时核对 ref/type；Reference 不包含原始限额值和权限正文。

`EffectiveCapabilityResourceLimits implements CapabilityResourceLimitView`。Operation Context 持有该只读接口指向的同一对象，不复制 typed value；Adapter/Provider 能精确 `require` 实际限额，但不能访问 resolver、source contributions 或 Authorization Snapshot。

Authorization Snapshot 保存完整 immutable Effective 对象及 reference/digest；checkpoint/audit 只保存 reference。Execution recheck 由 Authorization boundary 使用同一 contract 对 Snapshot value 与当前精确版本贡献求交，返回绑定相同 invocation/registration、`isSameOrStricter` 为 true 的新 Effective 对象；若 ref/type/binding 变化或无法证明则 fail closed。

### 10.7 四边界同源传递

```java
ExecutionValidationContext.resourceLimits()
ExecutionContext.resourceLimits()
ExecutionScope.resourceLimits()
ResultSecurityPort.secure(
    Object candidate,
    ContractRef outputContract,
    ExecutionScope scope,
    EffectiveCapabilityResourceLimits limits)
```

Core 只从 AuthorizationExecutionPort 返回的 `ExecutionScope.resourceLimits()` 取值，构造 Validation/Execution Context 并调用 Result Security；不调用 resolver、不读取配置、不把 Snapshot 原值与 recheck 新值并列传入。正确性比较 ContractRef/type/digest/binding identity，不依赖 JVM reference 相等。

Validator 使用 typed limits 校验 Raw Plan 的 page/size/rows/evidence 等 capability-specific 结构；Handler 使用同一值裁剪 Provider request/组合候选；Result Security 使用同一值校验最终 rows/bytes/evidence/citation/text。任何消费者缺失相应 dimension consumer declaration 均由启动 gate 阻断。

### 10.8 CapabilityOperationContext 与 typed request

```java
public final class CapabilityOperationType {
    public static CapabilityOperationType of(String upperSnakeCase);
    public String value();
}

public interface CancellationSignal {
    boolean isCancelled();
}

public record CapabilityOperationContext(
    String invocationId,
    String requestCorrelationId,
    String capabilityId,
    String operationId,
    CapabilityOperationType operationType,
    Instant absoluteDeadline,
    CancellationSignal cancellation,
    CapabilityResourceLimitView resourceLimits) {}

public interface CapabilityOperationRequest {
    CapabilityOperationContext operationContext();
}
```

`CapabilityOperationType`、`CancellationSignal`、Context/Request/Outcome/Metadata 位于 `agent-adapter-api` 的 `operation` 包并保持 Spring-free。`CancellationSignal` 只暴露 `isCancelled()`；Core 用当前 `CancellationToken` 创建只读适配视图，取消写权限仍只在 Entry/Lifecycle。`CapabilityOperationType` 是 Java 受控值类型，不建立包含 DOCUMENT 专用项的共享 enum；具体 capability 模块声明常量。`ExecutionContext.operationContext(type)` 生成 Invocation 内唯一 operationId，并原样传入同一 deadline/cancellation/limit view。Capability-local Provider Port 只接收实现 `CapabilityOperationRequest` 的 typed request，不使用“业务 request + 独立 context”两份可错配参数；Domain Adapter 继续遵守 P1_V2/04 的 `(ValidatedCommand, CapabilityOperationContext)` SPI，不由本文改写。

Operation Context 不含 JWT、ExecutionScope、Authorization Snapshot、Profile/Policy/Permission、mask、Context Envelope、未过滤完整业务结果、provider endpoint/credential 或独立 timeout。Adapter/Provider 通过 `resourceLimits.require(expectedRef,expectedType)` 获得实际 typed value，而不是只拿无法执行的 digest reference。

### 10.9 CapabilityOperationOutcome 与 Metadata

```java
public enum CapabilityOperationTermination {
    SUCCEEDED, DISABLED, FAILED, DEADLINE_EXCEEDED, CANCELLED, REJECTED
}

public enum CapabilityOperationFailureCode {
    DISABLED, INVALID_REQUEST,
    PROVIDER_UNAVAILABLE, PROVIDER_TIMEOUT, PROVIDER_FAILED,
    INVALID_RESPONSE, LIMIT_EXCEEDED,
    DEADLINE_EXCEEDED, CANCELLED, LATE_RESULT,
    SECURITY_REJECTED, BINDING_MISMATCH
}

public record ProviderSafeIdentity(
    String providerId,
    Optional<String> modelRef) {}

public record CapabilityOperationMetadata(
    String operationId,
    CapabilityOperationType operationType,
    ProviderSafeIdentity provider,
    int providerAttempts,
    long durationMs,
    CapabilityOperationTermination termination,
    String diagnosticId,
    ResourceLimitReference resourceLimitReference,
    boolean limitTouched,
    boolean deadlineTouched,
    boolean cancellationObserved) {}

public sealed interface CapabilityOperationOutcome<R>
    permits CapabilityOperationSuccess, CapabilityOperationFailure {
    CapabilityOperationMetadata metadata();
}
```

`CapabilityOperationSuccess<R>` 保存受校验 candidate；`CapabilityOperationFailure<R>` 保存 `CapabilityOperationFailureCode` 和安全 diagnosticId，不传播 provider 原始异常/响应。Port 的 success 和 failure 都必须返回 metadata；抛出未分类异常由 client boundary 转为 `FAILED/PROVIDER_FAILED` typed outcome。`PROVIDER_TIMEOUT` 表示 provider stage cap 先于 absolute deadline 到期；absolute deadline 到期使用 `DEADLINE_EXCEEDED`。post-check 发现成功响应迟到时使用 `LATE_RESULT`，并按当时 deadline/cancellation 形成非成功 termination；不得把三者互相折叠后返回 success。

Metadata 由本地 client boundary 使用注入的 `Clock`、真实 outbound attempt 计数和 operation context 生成，不信任 provider 自报 duration/attempt/deadline。`DISABLED` 的 attempts=0；实际外部调用 attempts 必须为 1。client/mesh/SDK 无法证明 0/1 次时不满足生产启动门禁，禁止用 unknown/empty 或 0 冒充未知；>1 直接拒绝并告警。

### 10.10 调用、取消、迟到与重试

每次 operation 固定执行：

1. Handler 从 ExecutionContext 创建 operation context；
2. 调用前检查 cancellation 与 `clock.instant()<absoluteDeadline`；
3. 从同一 typed limits 构造最小 request 并在 capability-specific validator 校验；
4. port/client 执行最多一个外部 attempt，timeout 使用 `min(stageCap,remainingDeadline)`；
5. 返回后再次检查 cancellation/deadline、operationId/type、limit reference 和 metadata；
6. 迟到或取消结果转换为 typed failure，不进入 Handler candidate；
7. Handler 只能选择确定性本地 fallback 或 refuse，当前不得再次调用相同或备用 Provider。

HTTP client、SDK、service mesh/retry interceptor、Feign/RestClient wrapper 的自动 retry 都必须显式关闭并有测试。future retry/fallback provider 必须先由 ADR 定义 attempt policy、计费/幂等、deadline、metadata 和审计，不得只改配置。

### 10.11 Generated Text Candidate 与中间候选

```java
public record CandidateEvidenceReference(
    String evidenceRefId,
    ContractRef evidenceContract,
    String authorizationBindingDigest,
    String ownerScopeDigest) {}

public record CandidateCitationReference(
    String citationId,
    String evidenceRefId) {}

public record CandidateSecurityBinding(
    String invocationId,
    String requestCorrelationId,
    ContractRef outputContract,
    ResourceLimitReference resourceLimitReference,
    List<CandidateEvidenceReference> evidenceRefs,
    List<CandidateCitationReference> citationRefs,
    CapabilityOperationMetadata operationMetadata) {}

public interface GeneratedTextCandidate {
    CandidateSecurityBinding securityBinding();
}
```

Evidence/citation reference 的 id 非空，两个 digest 必须是版本化 canonical SHA-256；每个 citation 的 `evidenceRefId` 必须精确命中同一 binding 中的一项 evidence。Result Security 还要用当前 ExecutionScope 复检 owner/scope 与 authorization binding，不能把 digest 当作授权本身。

通用接口只冻结安全 binding，不假设候选只有一个文本字段；answer、summary、bullets 等字段由具体 output ContractRef 的 concrete subtype 声明，并由 ResultSecurityProjectorRegistry 校验 Java runtime type 和逐字段限额。自由 String、未绑定 evidence/citation、operation metadata、output ContractRef 或 limits 的文本一律不能成为最终 answer/summary/message。

Embedding vector、rewrite variants、rerank order 等是 Handler 内部中间候选：

- typed port response validator 先校验 operation binding、dimension/count/finite values、candidate ownership 和同一 limits；
- 只能影响当前 Handler 的类型化最终候选，不直接写 Context/Result、日志或响应；
- 最终 Handler output 仍按 Registration output ContractRef 进入统一 Result Security；
- 若中间候选非法，走 typed local fallback/refuse，不能原样透传 provider 数据。

### 10.12 配置所有权与删除规则

Resource limit 数值只能通过 Definition/Profile/Policy/Permission/Request contribution 进入 resolver。以下 provider 配置允许保留：endpoint/model 安全引用、connect/read stage cap、maximum HTTP response bytes、bulkhead/concurrency、service credential locator；它们只能进一步拒绝或缩短调用。

若配置决定 page/rows/evidence/citation/context/output chars 等业务可接受上限，该值必须迁入相应 typed contribution，消费者不得同时直读配置。当前清理：

| 当前位置 | 问题 | 处理 |
|---|---|---|
| `AgentProfileDefinition`、`EffectiveProfile`、`BudgetLimits`、`PlanningEffectiveScope` | 混放 repair 与 page/result 散预算 | 只保留 `PlanningBudgetLimits`；resource 值改为 source-aware typed contributions |
| `AuthorizationSnapshot.executionBudget`、`ExecutionScope.maxRepairAttempts/maxResultRows/maxResultBytes`、`ExecutionBudget` | 非类型化且 repair 泄漏到 Execution | 删除 `ExecutionBudget`；改为 `EffectiveCapabilityResourceLimits` |
| `AvailableCapability.maxPageSize/maxResultRows/maxResultBytes/maxRepairAttempts` | Route projection 携带散预算 | 全部删除；AvailableCapability 不携带 Planning/resource budget，Planning Budget 只保留在 Planning request/checkpoint 边界 |
| `CanonicalRoleCapability/ExecutionValidationProjection` 的 page/result 上限 | Domain metadata 复制 resource facts | 按 P1_V2/04 删除 |
| Query/Aggregate/Document Validator 直读 `AgentProperties` 业务上限 | 与 Snapshot 冻结值多源 | 改读 `context.resourceLimits().require(...)` |
| `DocumentCapabilityHandler` evidence/generation 上限直读配置 | Handler 可重算/扩大 | 改读 typed DocumentResourceLimit |
| `DocumentResultSecurityProjector` 直读配置 | Result Security 与 Handler 不同源 | 改用 `secure` 传入 limits |
| `RuntimeDocumentQueryRewriteClient` 和 `/runtime/v1/document/rewrite` | 执行期复用 Planning Runtime | 由 P2_V3/06 迁为独立 capability-local provider client，并删除 Runtime endpoint/DTO/Prompt |

### 10.13 Startup/Reload Gate

启动或 metadata reload candidate 发布前必须完成 Definition declaration、contract/type/dimensions、Profile/Policy/Permission contribution schema、consumer declarations、Provider port request type、Result projector coverage 的全量闭合校验。任一 capability 不闭合则拒绝整个 candidate；不得将该 capability 动态 `enabled=false` 后静默启动。

Contract Registry 和 Capability Registration 必须作为同一原子 composition bundle 验证/发布；运行中不允许先发布新 Definition 再补 contract，或保留旧散预算 fallback。reload 后已有 Invocation 继续绑定原 Snapshot exact versions；Execution recheck 无法证明 current value 同值/收紧时 fail closed。

### 10.14 Multi-Agent 演进边界

当前类型只绑定 Invocation/correlation/Registration，不包含 RunId、TaskId、Delegation、remaining Run budget 或 usage ledger。future Multi-Agent L1 可以把其定义的 Run/Task remaining budget 作为新的 source-aware contribution 收紧输入，并扩展 binding identity；`EffectiveCapabilityResourceLimits` 的消费者接口、operation context、typed outcome 和 Result Security 接口保持不变。

## 11. 接口设计

| 接口/类型 | 方法 | 入参 | 返回/约束 |
|---|---|---|---|
| `CapabilityResourceLimitRegistry` | `require` | ContractRef、Class<T> | 唯一 typed contract |
| `CapabilityResourceLimitContract` | `intersect/isSameOrStricter/validate/canonicalDigest` | typed values | 单调交集与证明 |
| `CapabilityResourceLimitResolver` | `resolve` | binding identity、declaration、contributions | 单 Contract Effective limits |
| `AuthorizationExecutionPort` | `recheck` | Snapshot、InvocationHandle | 含同值/收紧 limits 的 ExecutionScope |
| `ExecutionValidationContext` | `resourceLimits` | 无 | Validator 同源值 |
| `ExecutionContext` | `resourceLimits/operationContext` | operation type | Handler/Provider 同源值 |
| `CapabilityOperationRequest` | `operationContext` | 无 | typed request 内唯一 context |
| Capability-local Port | capability-specific method | typed request | typed `CapabilityOperationOutcome<R>` |
| `ResultSecurityPort` | `secure` | candidate、output ContractRef、ExecutionScope、limits | `SecuredResult` |
| `GeneratedTextCandidate` | `securityBinding` | 无 | output contract concrete subtype 自行声明 answer/summary/bullets 等候选字段 |

本文不新增外部 Agent HTTP API。Provider HTTP 契约由 P2_V3/06 具体定义。

## 12. 数据与持久化设计

Effective limits、typed value、operation context/outcome 和中间候选只在当前 Invocation 内存活，不新增数据库表。持久化规则：

- Authorization Snapshot 进程内保存完整 immutable Effective value；
- Invocation checkpoint/audit 只保存 ContractRef、canonical digest、registration/invocation safe binding 和 operation metadata 安全摘要；
- 不保存 Profile/Policy/Permission contribution 全文、provider request/response、vector、prompt、evidence 正文、credential 或 typed limit JSON；
- SUCCESS finalization 只持久化经过 Result Security 的结果；失败 operation metadata 只进入受限审计引用。

## 13. 状态与时序设计

本文不建立 Provider operation 持久状态机。每次调用只产生一个不可变 `CapabilityOperationMetadata.termination`；`NOT_STARTED/INVOKED` 是方法内时序，不是共享状态或数据库字段。

```text
create operation context
  -> pre-check cancel/deadline/limits
  -> zero or one provider attempt
  -> immutable typed success/failure + metadata
  -> post-check cancel/deadline/binding
  -> Handler intermediate validation
  -> final candidate -> Result Security
```

`FAILED/CANCELLED/DEADLINE_EXCEEDED/REJECTED` 不携带可当作 success 的候选；`DISABLED` attempts=0，只允许 Handler 使用预定义确定性本地路径。

## 14. 幂等、并发与一致性设计

- 当前 Provider operation 只读但可能产生计费；operationId 仅用于 correlation/audit，不是业务幂等键，也不授权 replay。
- 每个 operation 最多一个外部 attempt；同 operationId 重复发送视为实现缺陷并告警。
- candidate 不跨 Invocation 缓存；Embedding cache 若未来引入，必须绑定 model/dimension/input digest/tenant安全边界且不得缓存授权 evidence，本阶段不实现。
- cancellation/deadline 与 Provider response 竞争时，取消/超时优先，迟到 success 丢弃。
- Result Security 核对 candidate 的 ResourceLimitReference 与当前 ExecutionScope limits；不一致整体拒绝。
- Provider operational cap 可比 effective limit 更严格并提前拒绝，不能返回一个更宽松的 Effective reference。

## 15. 权限、风控与审计设计

- Port 输入由 Handler 从 Validated Plan、当前已授权最小数据和 ExecutionContext 构造；不得获得 JWT/Authorization Snapshot/完整 scope/mask。
- Generation 只能接收已经过 pre-security 的 evidence package；Embedding/Rewrite 不接收 ACL 明细或完整结果；Rerank 只接收当前已授权 candidate 最小投影。
- Provider credential 仅由 client boundary 注入 service credential，不进入 request/outcome/metadata。
- 审计记录 operationId/type、provider/model safe ref、attempts、duration、termination、diagnosticId、limit reference/digest 和 touched flags；不记录文本/vector/query/evidence/provider raw response。
- Result Security 必须校验 output type/ContractRef、evidence/citation owner、operation binding、当前字段权限/mask 和同一 limits；缺一项 fail closed。

## 16. 性能与容量设计

- Contract Registry 查找和 Effective limit `require` 为 O(1)；当前没有 Map<ContractRef,value> 多层遍历。
- Resolver 只在 capability freeze 和 Execution recheck 执行，contribution 数量固定为 3+optional request。
- provider timeout 使用剩余 absolute deadline；response bytes 由 HTTP client operational cap 和 typed result limit 双重限制。
- bulkhead/concurrency/queue cap 必须有界；队列等待也消耗同一 deadline。
- 禁止无界 batch、无界 evidence/vector、SDK retry、迟到 response buffering 和高基数 metrics label。

## 17. 兼容性与扩展性设计

系统未投产，`ExecutionBudget`、散 page/result 字段、Provider 旧 request/exception 接口和 Runtime rewrite 不保留兼容层。P1_V2/06 必须把 Definition declaration、Contract Registry、contributions、Snapshot、Core contexts、Provider ports、Result Security 和旧字段删除作为一个纵向原子交付单元。

新增 capability 只增加：limit subtype/contract/dimension 常量、Definition declaration、source contributions、consumer declarations、capability-local typed port/Handler/测试；不修改 Core resolver 算法、共享 enum、Planning 主流程或已有 capability。新增 Provider 实现只替换 composition root bean，不改变 port/limit/candidate contract。

## 18. 日志、监控与告警

| 类型 | 指标/事件 | 低基数维度 |
|---|---|---|
| metric | resource resolve/recheck allow/reject | stage、reason、contract family |
| metric | contract missing/type/dimension/monotonic failure | reason |
| metric | provider outcome/attempt/duration/late result | operationType、termination、provider safe id |
| metric | candidate binding/security rejection | reason、candidate type |
| alert | attempt > 1 或同 operationId 重复发送 | operationType/provider |
| alert | consumer dimension coverage gap | capability family/consumer type |
| alert | Runtime rewrite endpoint 被调用 | 固定事件，无 query label |

标签禁止 invocationId、userId、domain、query/evidence 文本、raw model response、完整 version/digest。详细关联进入受限审计，用 diagnosticId 查询。

## 19. 实现落点清单

### 19.1 通用 Java 落点

| 序号 | 路径 | 类/动作 | 变更 |
|---:|---|---|---|
| 1 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityResourceLimit.java` | typed value marker | 新增 |
| 2 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityResourceLimitView.java` | `require/reference` read-only SPI | 新增 |
| 3 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/ResourceLimitReference.java` | safe ContractRef/digest/binding | 新增 |
| 4 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CancellationSignal.java` | read-only cancel view | 新增 |
| 5 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationType.java` | validated upper-snake value | 新增 |
| 6 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationContext.java` | limit view/deadline/cancel | 新增 |
| 7 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationRequest.java` | typed request seam | 新增 |
| 8 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationOutcome.java` | sealed root | 新增 |
| 9 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationSuccess.java` | typed success | 新增 |
| 10 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationFailure.java` | typed failure | 新增 |
| 11 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationMetadata.java` | immutable safe metadata | 新增 |
| 12 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationTermination.java` | terminal enum | 新增 |
| 13 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/CapabilityOperationFailureCode.java` | safe failure enum | 新增 |
| 14 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/operation/ProviderSafeIdentity.java` | provider/model safe ref | 新增 |
| 15 | `agent-service/src/main/java/com/dylan/agent/kernel/resource/ResourceLimitDimension.java` | validated value object | 新增 |
| 16 | `agent-service/src/main/java/com/dylan/agent/kernel/resource/CapabilityResourceLimitDeclaration.java` | 单 Contract declaration | 新增 |
| 17 | `agent-service/src/main/java/com/dylan/agent/kernel/resource/CapabilityResourceLimitContract.java` | intersection/strictness/digest | 新增 |
| 18 | `agent-service/src/main/java/com/dylan/agent/kernel/resource/CapabilityResourceLimitRegistry.java` | `require` | 新增 |
| 19 | `agent-service/src/main/java/com/dylan/agent/kernel/resource/EffectiveCapabilityResourceLimits.java` | implements read-only view | 新增 |
| 20 | `agent-service/src/main/java/com/dylan/agent/kernel/resource/CapabilityResourceConsumerDeclaration.java` | consumer dimension gate | 新增 |
| 21 | `agent-service/src/main/java/com/dylan/agent/metadata/authorization/resource/CapabilityResourceLimitContribution.java` | source-aware contribution | 新增 |
| 22 | `agent-service/src/main/java/com/dylan/agent/metadata/authorization/resource/CapabilityResourceLimitResolver.java` | 第 10.5 节唯一 resolver | 新增 |
| 23 | `agent-service/src/main/java/com/dylan/agent/kernel/definition/CapabilityDefinition.java` | resource declaration accessor | 修改 |
| 24 | `agent-service/src/main/java/com/dylan/agent/metadata/authorization/model/AuthorizationSnapshot.java` | `resourceLimits` 替换 `executionBudget` | 修改 |
| 25 | `agent-service/src/main/java/com/dylan/agent/metadata/authorization/model/ExecutionScope.java` | `resourceLimits`，删除散预算 | 修改 |
| 26 | `agent-service/src/main/java/com/dylan/agent/metadata/authorization/model/ExecutionBudget.java` | 删除 | 删除 |
| 27 | `agent-service/src/main/java/com/dylan/agent/kernel/core/ExecutionValidationContext.java` | `resourceLimits` | 修改 |
| 28 | `agent-service/src/main/java/com/dylan/agent/kernel/core/ExecutionContext.java` | `resourceLimits/operationContext` + token adapter | 修改 |
| 29 | `agent-service/src/main/java/com/dylan/agent/kernel/port/ResultSecurityPort.java` | 四参 `secure` | 修改 |
| 30 | `agent-service/src/main/java/com/dylan/agent/kernel/infrastructure/GeneratedTextCandidate.java` | output candidate seam | 新增 |
| 31 | `agent-service/src/main/java/com/dylan/agent/kernel/infrastructure/CandidateSecurityBinding.java` | output/operation/limit binding | 新增 |
| 32 | `agent-service/src/main/java/com/dylan/agent/kernel/infrastructure/CandidateEvidenceReference.java` | evidence authorization/owner binding | 新增 |
| 33 | `agent-service/src/main/java/com/dylan/agent/kernel/infrastructure/CandidateCitationReference.java` | citation-to-evidence binding | 新增 |
| 34 | `agent-service/src/main/java/com/dylan/agent/metadata/authorization/resource/ResourceLimitSource.java` | PROFILE/POLICY/PERMISSION/REQUEST | 新增 |
| 35 | `agent-service/src/main/java/com/dylan/agent/kernel/resource/ResourceLimitBindingIdentity.java` | invocation/correlation/registration/evidence binding | 新增 |

### 19.2 现有散预算删除落点

| 路径 | 动作 |
|---|---|
| `agent-service/src/main/java/com/dylan/agent/metadata/profile/model/AgentProfileDefinition.java` | 删除 page/result 散字段，增加 typed contributions |
| `agent-service/src/main/java/com/dylan/agent/metadata/profile/model/EffectiveProfile.java` | 同上 |
| `agent-service/src/main/java/com/dylan/agent/metadata/policy/model/BudgetLimits.java` | 仅保留 PlanningBudget；resource 迁 typed Policy contribution |
| `agent-service/src/main/java/com/dylan/agent/metadata/authorization/model/PlanningEffectiveScope.java` | PlanningBudget 与 resource contributions 分字段 |
| `agent-service/src/main/java/com/dylan/agent/metadata/catalog/AvailableCapability.java` | 删除 repair/page/result/bytes 散字段 |
| `agent-service/src/main/java/com/dylan/agent/metadata/catalog/CapabilityCatalog.java` | 不投影散预算 |
| `agent-service/src/main/java/com/dylan/agent/metadata/authorization/internal/AuthorizationPlanningPortImpl.java` | 按选定 Definition 调 resolver/freeze |
| `agent-service/src/main/java/com/dylan/agent/metadata/authorization/internal/AuthorizationExecutionPortImpl.java` | exact-version contribution recheck + strictness proof |
| `agent-service/src/main/java/com/dylan/agent/config/AgentProperties.java` | 业务资源上限迁 Profile/Policy typed contribution；只留 operational cap |
| `config-service/src/main/resources/config/agent-service.yml` | 按 ContractRef 绑定 typed Profile/Policy 值；删除消费者直读副本 |

### 19.3 Capability-local Port 迁移落点

P2_V3 具体实现必须覆盖以下当前接口：

| 当前路径 | 迁移动作 |
|---|---|
| `agent-service/src/main/java/com/dylan/agent/capability/document/rewrite/DocumentQueryRewritePort.java` | typed operation request/outcome；独立 provider client |
| `agent-service/src/main/java/com/dylan/agent/capability/document/rewrite/RuntimeDocumentQueryRewriteClient.java` | 删除，不再依赖 AgentRuntimeClient |
| `agent-service/src/main/java/com/dylan/agent/capability/document/embedding/DocumentEmbeddingPort.java` | typed context/outcome、dimension/finite validation |
| `agent-service/src/main/java/com/dylan/agent/capability/document/rerank/DocumentRerankPort.java` | 最小已授权 candidate projection、typed context/outcome |
| `agent-service/src/main/java/com/dylan/agent/capability/document/generation/DocumentGenerationPort.java` | Generated Text Candidate + typed context/outcome |
| `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentPlanValidator.java` | 只读 DocumentResourceLimit |
| `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentCapabilityHandler.java` | 不直读业务 max 配置；验证所有 operation outcomes |
| `agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java` | 使用传入同一 limits/candidate binding |
| `agent-runtime/app/api/runtime_api.py` 及 rewrite route/DTO/Prompt | 删除执行期 rewrite 路径；Runtime 只保留 Route/Plan |

## 20. 测试设计与验收命令

### 20.1 测试矩阵

| 类别 | 必测场景 | 关键断言 |
|---|---|---|
| Contract properties | 交换/结合/幂等、每维单调、0/负数/溢出/unknown dimension | invalid fail closed；不把 0 当 unlimited |
| Registry/startup | duplicate/missing/type mismatch、Definition/consumer dimension gap、第二 ContractRef | 启动/reload candidate 拒绝 |
| Resolver | 缺/重复 source、optional request absent、request 扩大、集合重排、digest 篡改 | 3 个必需 source；request 只能收紧；digest 稳定 |
| Execution recheck | Permission 收紧/扩大、Policy/Profile exact version 变化、binding mismatch | 输出同值或更严格；无法证明 fail closed |
| Core propagation | ValidationContext/ExecutionContext/Provider/ResultSecurity | ContractRef/type/digest/binding identity 全部一致 |
| Operation context | operationId unique、deadline/cancel/correlation、实际 typed limits | Provider 可 require 值；无完整 Scope/JWT |
| Attempt/deadline | disabled、一次成功、异常、cancel race、late response、SDK retry 开启 | attempts 0/1；迟到不进入 candidate；retry gate 失败 |
| Outcome metadata | provider raw duration/attempt 欺骗、无法证明本地 outbound 次数、wrong operation/limit ref | 本地 metadata 权威；attempt 不可观测或绑定错配均拒绝 |
| Candidate security | free String、缺 evidence/citation/metadata/ContractRef/limit ref、wrong owner | Result Security 拒绝或安全 fallback |
| Non-text candidate | NaN/Inf/wrong dimension/越权 rerank candidate/超量 variants | Handler response validator 拒绝，不泄漏 |
| Architecture | Core 无 capability limit switch；port 不依赖 AgentRuntimeClient/Planning/metadata internal | 新 capability 只加 subtype/contract/port |
| Cleanup | 散预算 getter、ExecutionBudget、Runtime rewrite route、consumer 直读 max 配置 | 原子迁移后零命中或仅允许 Planning/operational cap |

### 20.2 最小实施验证命令

```powershell
mvn -pl agent-api,agent-adapter-api,agent-service,agent-adapter-document -am test
python -m pytest agent-runtime/tests/test_contracts.py agent-runtime/tests/test_planning.py
rg -n "ExecutionBudget|maxResultRows\(\)|maxResultBytes\(\)|maxPageSize\(\)" agent-service/src/main/java
rg -n "RuntimeDocumentQueryRewriteClient|/runtime/v1/document/rewrite" agent-service agent-runtime
rg -n "retry|max-attempts|maxAttempts" agent-service/src/main/java agent-service/src/main/resources config-service/src/main/resources/config/agent-service.yml
```

前两条必须通过；后三条按删除矩阵只能命中允许的 Planning Budget、Provider operational cap 或测试断言，不能命中消费者散预算/Runtime rewrite/自动 retry 生效配置。P1_V2/06 还需执行全模块 contract generation 与旧路径零命中门禁。

## 21. 风险与待确认事项

| 风险 | 触发场景 | 处理 |
|---|---|---|
| 资源上限多源 | Validator/Handler/Projector 继续读取 AgentProperties | architecture test + 删除 getter；只从 context require typed limit |
| Provider 无法执行限额 | operation context 只传 digest/ref | 直接传 opaque Effective typed value，并保留 safe reference 校验 |
| 自动 retry/计费放大 | SDK/mesh/client 默认重试 | 显式 maxAttempts=1、attempt telemetry 和启动/测试门禁 |
| 迟到结果提交 | Provider 在 deadline/cancel 后返回成功 | post-check 优先，转换 typed failure，Lifecycle 不提交 |
| 中间候选泄漏 | vector/rewrite/rerank 原始结果进入日志/Context/响应 | typed response validator + final output Result Security |
| 配置硬上限漂移 | operational cap 也承担业务可接受上限 | 业务维度迁 typed contribution；operational cap 只可更严格拒绝 |
| 半链迁移 | 先删散预算但 Definition/contract/contribution 未就绪 | 仅 P1_V2/06 纵向原子切换 |
| future Multi-Agent 侵入 | 当前预建 Run/Task budget 字段/ledger | 当前禁止；future L1 只追加收紧 contribution/binding 扩展 |

## 22. 评审记录

| 轮次 | 日期 | 结论 | 发现与处理 |
|---:|---|---|---|
| 1 | 2026-07-13 | 修订后复审 | 发现多 Contract 容器、Provider 无实际 limits、budget 混层、resolver/strictness/outcome/candidate/config 清理不完整及提前引入 Run/Task budget；已全面修订 |
| 2 | 2026-07-13 | 修订后复审 | 发现 Adapter SPI 与 agent-service operation 类型形成反向依赖、attempts 可未知削弱 retry gate、evidence/citation 空 marker 约束不足；已拆 Spring-free read-only SPI、改为必知 0/1 次并冻结具体 reference |
| 3 | 2026-07-13 | 通过 | 澄清 Permission contribution 适配边界，移除通用候选的单文本假设，补齐 timeout/late/security failure code，并删除 AvailableCapability 中残留的 Planning Budget 引用；复审无 S0/S1 |

## 23. 实施对齐检查

- [x] Definition 的单 Contract declaration、type、intrinsic upper bound 和 dimensions 已冻结。
- [x] PROFILE/POLICY/PERMISSION 必需 contribution 与 optional REQUEST narrowing 已冻结。
- [x] Contract intersection、strictness proof、canonical digest 和 startup gate 已冻结。
- [x] Authorization Snapshot freeze 与 Execution recheck 同值/收紧算法已冻结。
- [x] Validator/Handler/Provider/Result Security 同源传递接口已冻结。
- [x] Operation Context 含实际 opaque typed limits，而非仅 reference。
- [x] typed Outcome/Metadata、attempt、deadline/cancel/late-result 语义已冻结。
- [x] Generated Text Candidate 与非文本中间候选安全规则已冻结。
- [x] Planning Budget/resource limits/operational cap 和配置删除边界已分离。
- [x] 当前无 Run/Task/Delegation budget 空壳。
- [ ] P1_V2 全套 L2 串行评审通过。
- [ ] P1_V2/06 原子实施授权完成。

## 24. 任务完成摘要

本文已形成单 Capability 单 Contract、source-aware 单调求交、Authorization Snapshot 冻结、Core 同源传递、Provider typed operation/outcome 和候选安全的独立实施基线。实施者无需回查旧 D02 或文档证据优化方案补通用资源/Provider seam；Document 具体字段和 DTO 继续由 P2_V3 承接。当前状态：**In Review**。
