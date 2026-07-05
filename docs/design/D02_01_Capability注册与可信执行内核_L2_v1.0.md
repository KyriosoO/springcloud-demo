# D02_01 Capability 注册与可信执行内核 — L2 v1.0

> 文档层级：L2 实施详细设计  
> 文档状态：已实施（D01 退出门禁通过，D02 基线复核完成，代码已提交；2026-07-04 已按授权补充多轮分页与权限拒绝提示约束；2026-07-05 已补充 Runtime Plan 输出修复边界和 QUERY 白名单排序增量约束）
> 上位文档：`Agent目标架构总览_v1.0.md`、`Agent契约与规划架构设计_v1.0.md`、`Agent能力执行内核架构设计_v1.0.md`、`Agent元数据与上下文安全架构设计_v1.0.md`  
> 集成权威：`D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md`  
> 关联 L2：`D02_02_Invocation生命周期与持久化_L2_v1.0.md`、`D02_03_元数据授权与Context安全_L2_v1.0.md`  
> 交付阶段：D02 详细设计评审门禁；本文不实施代码  
> 适用代码基线：`4ce5ac3` 及其同源后续提交

---

## 0. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-04 | 授权恢复 / 第 3、5、7、8、10～12 节 | 用户授权修订关联设计文档 | 在授权范围内补充 `QUERY_CONTEXT` 1.1.0、多轮分页MERGE、末页校验、`FIELD_FORBIDDEN`、`ExecutionFailure.safeMessage` 与对应测试门禁。 |
| 2 | 2026-07-05 | 授权恢复 / 第 8、10～12 节 | UAT 修复后同步设计 | 补充 Runtime PlanOutcome 入 Core 前的 `requestId` 绑定和 bounded repair 边界，明确 Core/Registration 不承担 Runtime 输出修复职责。 |
| 3 | 2026-07-05 | 授权恢复 / 第 3、4、5、10～12 节 | 用户授权同步 `Agent与业务域白名单排序能力` 关联文档 | 补充 `AgentExecutionContracts` 排序相关版本、QUERY Context `sorts` 字段、`QueryPlanValidator` 排序白名单校验、`query.preview` 共享输出契约和测试门禁。 |

---

## 1. 文档定位

### 1.1 唯一负责

本文唯一负责：

- `CapabilityDefinition`、typed Routing Descriptor 和 Context 声明；
- `CapabilityRegistration`、`CapabilityRegistry`、`ResolvedRegistration`；
- Java 类型擦除桥的唯一实现位置；
- `CapabilityPlanValidator`、`ValidatedPlan`、`CapabilityHandler`；
- `ExecutionCommand`、Execution Core 13 步算法和 `ExecutionOutcome`；
- Core 消费的 authorization/context/domain/result 端口；
- 新 capability/domain 不侵入 Core 的测试设计。

本文不定义 Lifecycle 状态迁移和持久化，不实现 Profile/Policy/Auth/Context，不实现 D04 Canonical Domain/Adapter Metadata，不定义 Runtime HTTP DTO。

### 1.2 上位决策映射

| 决策 | 落点 |
|---|---|
| EK-01～EK-05 | 第 3～6 节 |
| EK-08、EK-09 | 第 7～9 节 |
| EK-11、EK-14～EK-16、EK-19 | 第 7～11 节 |
| CP-12、CP-15 | `ResolvedRegistration`、`ExecutablePlanningResult` 和唯一类型桥 |
| MS-13、MS-14、MS-19 | Core 稳定端口和步骤 4～12 |

---

## 2. 包结构与依赖

### 2.1 计划包

```text
agent-api/.../contract/common/ContractRef.java
agent-api/.../contract/common/AgentExecutionContracts.java
agent-api/.../response/AgentResultPayload.java
agent-api/.../response/QueryAgentResultPayload.java
agent-api/.../response/AggregateAgentResultPayload.java
agent-api/.../response/AgentChatResponse.java (MODIFY)
agent-api/.../enums/AgentResultKind.java
agent-api/.../enums/AgentResponseType.java (MODIFY)

agent-service/.../kernel/
├─ definition/
│  ├─ CapabilityDefinition.java
│  ├─ CapabilityRoutingDescriptor.java
│  ├─ ContextAccessDeclaration.java
│  ├─ ContextReadDeclaration.java
│  ├─ ContextWriteDeclaration.java
│  └─ ContractRegistry.java
├─ config/
│  └─ CapabilityKernelConfiguration.java
├─ registration/
│  ├─ CapabilityRegistration.java
│  ├─ CapabilityRegistry.java
│  ├─ CapabilityRegistrationValidator.java
│  ├─ ResolvedRegistration.java
│  ├─ TypedRegistrationInvoker.java
│  ├─ ValidatedPlanHandle.java
│  └─ HandlerCandidate.java
├─ validator/
│  ├─ CapabilityPlanValidator.java
│  └─ ValidatedPlan.java
├─ handler/
│  ├─ CapabilityHandler.java
│  └─ HandlerResult.java
├─ core/
│  ├─ ExecutionCore.java
│  ├─ ExecutionCommand.java
│  ├─ ExecutionValidationContext.java
│  ├─ ExecutionContext.java
│  ├─ ExecutionOutcome.java
│  ├─ ExecutionSuccess.java
│  └─ ExecutionFailure.java
└─ port/
   ├─ AuthorizationExecutionPort.java
   ├─ ContextExecutionPort.java
   ├─ ContextApprovalPort.java
   ├─ DomainExecutionPort.java
   └─ ResultSecurityPort.java
```

### 2.2 依赖规则

- Core 依赖 `planning.model`、`invocation.model`、`kernel.port` 和不可变值对象。
- Core 不依赖 `lifecycle.service`、Mapper、Repository、Spring Configuration 或 metadata 实现包。
- 只有`kernel.config.CapabilityKernelConfiguration`作为composition root可同时依赖Registration集合、ContractRegistry、RegistrationValidator和D02 `DomainMetadataPort`；Core/Definition/Registry模型不反向依赖配置实现。
- `CapabilityDefinition` 使用 D01 Java `AgentPlanKind`、`AgentDomainMode`、`RuntimeContextType`；不得再定义平行 enum。
- `AdapterRole` 由 D04 在 `agent-adapter-api` 建立唯一稳定 Java 类型；Definition 只引用它。
- `ContractRef` 是 Java 内部 schema/version 唯一值对象；D03 删除或迁移旧 `CapabilityContractRef`，不能长期并存。

---

## 3. Capability Definition

### 3.1 `ContractRef.java`

```java
public record ContractRef(String schema, String version) {
    public ContractRef {
        // schema/version 均为非空规范化值；禁止 URL、Java class name 和隐式 latest
    }
}
```

方法只有 record 访问器。解析由 `ContractRegistry`（D03 composition root）完成；配置、Prompt、Python 不复制 schema 内容。

`ContractRegistry` 是final Java契约解析表，静态工厂`from(Collection<CapabilityRegistration<?,?,?>>)`只从Registration的input/output Java class及Context declaration payloadType收集绑定；同一ContractRef映射不同Class/结构摘要立即失败。公开方法：`ContractDescriptor require(ContractRef ref)`、`boolean isCompatible(ContractRef stored, ContractRef requested)`、`Set<ContractRef> all()`、`String runtimeSchemaRef(ContractRef ref)`。`ContractDescriptor`是其nested immutable record，只含ref、Java type和结构摘要。`runtimeSchemaRef`仅对D01 Runtime OpenAPI中已注册的Java root返回规范`#/components/schemas/<name>`，其他ContractRef拒绝；禁止调用方手工拼ref。Registry只从agent-api Java类型/生成artifact装配，不从Python、Prompt或YAML反向生成。

`AgentExecutionContracts`是不可实例化final类，只定义七个`public static final ContractRef`：`QUERY_PLAN`、`AGGREGATE_PLAN`（schema分别为D01 root，version直接引用`AgentRuntimeContract.VERSION`）、`QUERY_RESULT`（QueryAgentResultPayload）、`QUERY_PREVIEW_RESULT`（QueryPreviewResultPayload）、`AGGREGATE_RESULT`（AggregateAgentResultPayload）、`QUERY_CONTEXT`、`AGGREGATE_CONTEXT`。`QUERY_RESULT`和`QUERY_PREVIEW_RESULT`在 QUERY 排序回显修订后建议为`1.1.0`，因为`AgentQueryParameters`新增`sorts`；`QUERY_CONTEXT`在多轮分页和排序修订后版本为`1.2.0`，包含`sorts`、`total`、`totalExact`、`totalPages`；`AGGREGATE_CONTEXT`仍为`1.0.0`。后五项version只表达对应Java payload/result schema版本，不是Runtime contract、plan或strategy的平行版本轴；Registration、Context declaration、Result projector和迁移器只能引用这些常量，不重复字符串。

### 3.2 Agent API Result 单一扩展点

```java
public sealed interface AgentResultPayload
        permits QueryAgentResultPayload, AggregateAgentResultPayload {
    AgentResultKind getResultKind();
}
```

`AgentResultKind`初始值为QUERY、AGGREGATE；D05 代表性 capability 扩展后增加 QUERY_PREVIEW。`QueryAgentResultPayload`固定kind=QUERY，字段为required `AgentQueryParameters queryParameters`和required `AgentQueryResult queryResult`；`QueryPreviewResultPayload`固定kind=QUERY_PREVIEW，字段为required `AgentQueryParameters queryParameters`和required `QueryPreviewResult previewResult`；`AggregateAgentResultPayload`固定kind=AGGREGATE，字段为required `AgentAggregateResult aggregateResult`。三者提供无参构造器、只读discriminator及其余字段getter/setter，供Jackson/OpenAPI；现有叶子DTO继续复用，不复制字段。`AgentQueryParameters.sorts` 同时服务 `query.search` 与 `query.preview` 的安全回显。

该union使用与D01相同的Jackson/OpenAPI `resultKind` discriminator、`oneOf`、`additionalProperties=false`和`@Valid`规则；`AgentResultPayloadContractTest`覆盖两种round-trip、unknown kind、discriminator mismatch、并列旧字段不存在及ChatResponse条件形状。

D03直接修改未投产的`AgentChatResponse`：字段只保留conversationId、turnId、`AgentResponseType type`、message、summary、nullable `AgentResultPayload result`、nullable errorCode；删除并列queryParameters/queryResult/aggregateResult字段。`AgentResponseType`收敛为RESULT、CLARIFY、ERROR，删除AGGREGATE_RESULT；RESULT必须有result且无error，CLARIFY必须无result/error，ERROR必须无result且有error。新增结果形状只扩展Java sealed payload、ContractRef和projector，不修改`AgentChatResponseAssembler`/Controller主流程。

### 3.3 `CapabilityRoutingDescriptor.java`

| 字段 | 类型 | 约束 |
|---|---|---|
| `modelDescription` | `String` | 1～2000 字符 |
| `applicability` | `List<String>` | 只表达适用条件，不含权限/角色 |
| `exclusions` | `List<String>` | 只表达排除条件 |

公开方法：全参构造器、三个只读访问器。它是 Definition 内静态事实，不是 JSON String、YAML 副本或 Runtime DTO。

### 3.4 Context 声明

`ContextReadDeclaration` 字段：`RuntimeContextType contextType`、`ContractRef contractRef`、`Class<? extends CapabilityContextPayload> payloadType`、`boolean required`、`Set<String> readableFields`。

`ContextWriteDeclaration` 字段：`RuntimeContextType contextType`、`ContractRef contractRef`、`Class<? extends CapabilityContextPayload> payloadType`、`Duration maxTtl`、`Set<String> writableFields`。

`ContextAccessDeclaration` 字段：不可变 `List<ContextReadDeclaration> reads`、`List<ContextWriteDeclaration> writes`；方法：`read(type)`、`write(type)`、`validateNoDuplicateType()`。

声明只引用 Java ContractRef，不复制 payload 字段结构；Profile/Policy/Permission 只能收紧。

### 3.5 `CapabilityDefinition.java`

| 字段 | 类型 |
|---|---|
| `capabilityId` | `String` |
| `planKind` | `AgentPlanKind` |
| `routingDescriptor` | `CapabilityRoutingDescriptor` |
| `domainMode` | `AgentDomainMode` |
| `adapterRole` | `Optional<AdapterRole>` |
| `riskLevel` | `AgentCapabilityRiskLevel` |
| `executionMode` | `AgentCapabilityExecutionMode` |
| `inputContract` | `ContractRef` |
| `outputContract` | `ContractRef` |
| `contextAccess` | `ContextAccessDeclaration` |

公开方法：全参构造器和十组只读访问器。构造器执行：

1. capabilityId 匹配 `[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+`。
2. `NONE` 必须无 adapterRole；`OPTIONAL/REQUIRED` 必须有 adapterRole。
3. descriptor、ContractRef 和 Context 声明非空、无重复。
4. 不允许 `enabled`、角色、mask、Profile/Policy、Handler class 或 Adapter 实例字段。

---

## 4. Registration、Registry 与唯一类型桥

### 4.1 `CapabilityRegistration<R,V,O>`

```java
public final class CapabilityRegistration<
        R extends AgentPlan,
        V extends ValidatedPlan,
        O> {
    private final CapabilityDefinition definition;
    private final Class<R> rawPlanType;
    private final CapabilityPlanValidator<R,V> validator;
    private final Class<V> validatedPlanType;
    private final CapabilityHandler<V,O> handler;
    private final Class<O> outputType;
    private final TypedRegistrationInvoker<R,V,O> invoker;
}
```

公开方法：全参构造器、六个只读访问器、`String identity()`、`ValidatedPlanHandle validateRaw(AgentPlan, ExecutionValidationContext)`、`HandlerCandidate executeValidated(ValidatedPlanHandle, ExecutionContext)`、`void validateOutput(Object)`。

`identity()` 是 Definition/plan types/handler-validator types/ContractRef 的稳定摘要，不包含实例地址。Registration 构造后不可变。

### 4.2 `TypedRegistrationInvoker<R,V,O>`

此 package-private final 类是唯一允许 `@SuppressWarnings("unchecked")` 的位置：

- `ValidatedPlanHandle validate(AgentPlan raw, ExecutionValidationContext context)`：先用 `rawPlanType.isInstance`，再执行唯一受控 cast 和 Validator。
- `HandlerCandidate execute(ValidatedPlanHandle handle, ExecutionContext context)`：验证 handle 的 registration identity 和 validated type，再执行唯一受控 cast 和 Handler。
- `void validateOutput(Object output)`：使用 `outputType.isInstance`。

`ValidatedPlanHandle` 构造器 package-private，字段为 `registrationIdentity`、`ValidatedPlan value`；调用方不能伪造其他 Registration 的 handle。

`HandlerCandidate` 是擦除后的内部值，字段为 `Object output`、不可变 `List<ContextWriteCandidate> contextWrites`。

Core 不持有裸 `CapabilityHandler<?,?>`，不执行 cast，不通过反射调用业务方法。

### 4.3 `ResolvedRegistration.java`

| 字段 | 类型 |
|---|---|
| `capabilityId` | `String` |
| `planKind` | `AgentPlanKind` |
| `registrationIdentity` | `String` |
| `registration` | `CapabilityRegistration<?,?,?>` |

公开方法：package-private 构造器、四个只读访问器、`validateIdentity()`。Planning 将同一个不可变引用放入 `ExecutablePlanningResult`；Execution 不重新查询 Registry。

### 4.4 `CapabilityRegistrationValidator.java`

方法：`void validateAll(Collection<CapabilityRegistration<?,?,?>> registrations, ContractRegistry contracts, Set<AdapterRole> knownRoles)`。

必须验证：ID 唯一、非空；planKind/raw subtype 一致；Validator/ValidatedPlan/Handler/output 泛型闭合；ContractRef 可解析；Context read/write 合法；DomainMode/AdapterRole 合法；Routing Descriptor 完整。任一失败拒绝启动，不部分注册。

### 4.5 `CapabilityRegistry.java`

公开方法：

| 签名 | 语义 |
|---|---|
| `ResolvedRegistration resolve(String capabilityId)` | 唯一解析；未知值 fail closed |
| `Collection<CapabilityRegistration<?,?,?>> registrations()` | 不可变集合，供 Catalog 计算 |
| `Set<String> capabilityIds()` | 不可变 ID 集合 |
| `Map<AgentPlanKind,List<String>> coverageByPlanKind()` | 仅启动覆盖检查，不选择 Handler |

Registry 构造器调用 `CapabilityRegistrationValidator` 后冻结。它不计算 Profile/Policy/Permission/Domain availability，不执行 Validator/Handler。

### 4.6 Composition Root 与首批 Registration

`CapabilityKernelConfiguration`只定义两个通用Bean方法：

- `ContractRegistry contractRegistry(List<CapabilityRegistration<?,?,?>> registrations)`：调用`ContractRegistry.from`；空集合拒绝启动。
- `CapabilityRegistry capabilityRegistry(List<CapabilityRegistration<?,?,?>> registrations, ContractRegistry contracts, CapabilityRegistrationValidator validator, DomainMetadataPort domainMetadata)`：读取D04 `knownRoles()`完成一次全量校验并冻结Registry。

每个capability在自己的实现包提供一个Registration Bean，不修改上述通用配置：

- `QueryCapabilityConfiguration.querySearchRegistration(QueryPlanValidator,QueryCapabilityHandler)`返回`CapabilityRegistration<QueryAgentPlan,ValidatedQueryPlan,QueryAgentResultPayload>`，Definition capabilityId=`query.search`。
- `AggregateCapabilityConfiguration.aggregateComputeRegistration(AggregatePlanValidator,AggregateCapabilityHandler)`返回`CapabilityRegistration<AggregateAgentPlan,ValidatedAggregatePlan,AggregateAgentResultPayload>`，Definition capabilityId=`aggregate.compute`。

两者使用D01 Java plan、agent-api typed result和第8节Java Context payload class literal；不得从YAML反射创建Handler/Validator类。新增同planKind capability只增加其本地Configuration/Validator/Handler/测试及Profile引用，不修改`CapabilityKernelConfiguration`、Registry、Core或PlanningService。

首批Definition冻结如下：

| 字段 | `query.search` | `aggregate.compute` |
|---|---|---|
| planKind | QUERY | AGGREGATE |
| descriptor | 查询、筛选、分页；排除聚合/写操作 | 分组、指标、聚合；排除明细分页/写操作 |
| domainMode/adapterRole | REQUIRED/QUERYABLE | REQUIRED/AGGREGATABLE |
| riskLevel/executionMode | READ_ONLY/IMMEDIATE | READ_ONLY/IMMEDIATE |
| input/output | `QUERY_PLAN`/`QUERY_RESULT` | `AGGREGATE_PLAN`/`AGGREGATE_RESULT` |
| Context read | optional `QUERY_CONTEXT`，字段filters/selectFields/sorts/page/size/total/totalExact/totalPages | optional `AGGREGATE_CONTEXT`，字段filters/metrics/groupByFields/orderBy/maxRows |
| Context write | `QUERY_CONTEXT`，相同字段，maxTtl=7d | `AGGREGATE_CONTEXT`，相同字段，maxTtl=7d |

Context最终expiry仍取Definition 7d与Profile/Policy/global/current ExecutionScope上限的最小值。Routing descriptor只保存上述通用语义，不写domain名称、字段、角色或权限；具体文案作为各Configuration中的不可变Java值并由snapshot test固定。

`query.search`的`total`、`totalExact`、`totalPages`只作为多轮分页规划状态使用：Runtime Context View可读取这些标量以把“最后一页”转换为确定页码；Adapter执行请求不得携带这些字段；Handler只在成功查询并获得下游total信息后写入。`sorts`作为上一轮明细排序状态进入QUERY Context：MERGE 时`sorts == null`继承上一轮排序，`sorts == []`清空用户排序并回到业务域默认排序，非空列表替换上一轮排序。旧`QUERY_CONTEXT` 1.0.0/1.1.0 payload缺少`sorts`时，必须通过D02_03迁移器补为`List.of()`，不能导致历史会话第二轮分页直接失败。

---

## 5. Validator 与 Handler

### 5.1 `ValidatedPlan.java`

```java
public interface ValidatedPlan {
    String capabilityId();
    AgentPlanKind planKind();
    Optional<String> domain();
}
```

每个具体 ValidatedPlan 必须不可变，构造器不得 public，只允许对应 Validator 在 capability 实现包内创建。ArchUnit 门禁禁止 Controller、Entry、Core、Handler 直接调用其构造器。

### 5.2 `CapabilityPlanValidator<R,V>`

唯一方法：`V validate(R rawPlan, ExecutionValidationContext context)`。

职责：校验 capabilityId/planKind/domain、字段/operator/function、Context merge 后一致性和 canonical 值；输出不可变 ValidatedPlan。

禁止：Runtime/LLM、Handler/Adapter/数据库调用、Invocation/Context 写入、权限扩大、自动 fallback capability/domain。

### 5.3 `CapabilityHandler<V,O>` 与 `HandlerResult<O>`

`CapabilityHandler` 唯一方法：`HandlerResult<O> execute(V plan, ExecutionContext context)`。

`HandlerResult<O>` 字段：`O output`、不可变 `List<ContextWriteCandidate> contextWrites`；公开静态工厂 `of(output)`、`of(output,writes)` 和只读访问器。

Handler 只能编排一个 capability；不得接收 Raw Plan、修改 Invocation、持久化 Context、作授权决定、二次选择 Adapter 或返回新 capabilityId/planKind。Owner/Scope/sourceInvocation/expiry 不由 Handler 填写。

### 5.4 首批具体 Validator、ValidatedPlan 与 Handler

- `QueryPlanValidator implements CapabilityPlanValidator<QueryAgentPlan,ValidatedQueryPlan>`；构造器只注入`FilterNormalizer`、`FieldConstraintValidator`和纯Query全局分页/排序上限配置。`validate`只接收D02_00 `QueryPlanBindingStrategy`/`QueryMergeEngine`已形成的merged query，并以`ExecutionValidationProjection`规范化、校验field/operator/removeFields/selectFields/sorts/page/size；排序校验必须在 Java 可信边界完成：`sorts`最多2个、字段不得重复、direction规范化为`ASC`/`DESC`、字段必须同时存在于最终执行投影的`fieldRules`和`sortFields`，未授权排序字段按字段越权 fail closed。当merged query来自`contextMode=MERGE`时，Validator可读取`ExecutionValidationContext.contextSnapshots`中的上一轮QUERY Context，仅用于确认Context仍有效、继承/清空`sorts`、使用`totalExact/totalPages`校验“最后一页”和页码上界，不再二次执行filters合并；size上限取global配置、projection和ExecutionScope budget的最小值，再创建package-private构造的`ValidatedQueryPlan`。
- `ValidatedQueryPlan`字段为固定capabilityId=`query.search`、planKind=QUERY、domain、`ValidatedQuery`；只读且只由QueryPlanValidator创建。
- `QueryCapabilityHandler implements CapabilityHandler<ValidatedQueryPlan,QueryAgentResultPayload>`；`execute`只通过`ExecutionContext.requireAdapter(QueryableAdapter.class)`调用一次typed port，以`QueryParameterMapper.toQueryParameters(ValidatedQueryPlan)`构造参数，返回包含parameters+result的`HandlerResult<QueryAgentResultPayload>`及可选QUERY Context candidate。
- `AggregatePlanValidator implements CapabilityPlanValidator<AggregateAgentPlan,ValidatedAggregatePlan>`；构造器只注入`FilterNormalizer`、`FieldConstraintValidator`和纯Aggregate全局数量上限配置。`validate`使用同一Execution projection校验filters/metric/function/group/order/maxRows；maxRows等上限取global配置、projection和ExecutionScope budget的最小值，再创建`ValidatedAggregatePlan`。
- `ValidatedAggregatePlan`字段为固定capabilityId=`aggregate.compute`、planKind=AGGREGATE、domain、`ValidatedAggregateQuery`；只读且只由AggregatePlanValidator创建。
- `AggregateCapabilityHandler implements CapabilityHandler<ValidatedAggregatePlan,AggregateAgentResultPayload>`；`execute`只通过`requireAdapter(AggregatableAdapter.class)`调用一次typed port，返回`HandlerResult<AggregateAgentResultPayload>`和可选AGGREGATE Context candidate。

`FilterNormalizer`公开`normalizeAll(List<AgentFilter>,ExecutionValidationProjection)`与`normalize(AgentFilter,ExecutionFieldRule)`；`FieldConstraintValidator`公开`validateChanges(List<ValidatedFilter>,Set<String>,ExecutionValidationProjection)`和`validateFinalQuery(List<ValidatedFilter>,ExecutionValidationProjection)`。`OperatorSemantics.profileOf/supports`只表达Java operator的值基数/类型结构，最终允许集合仍取ExecutionFieldRule；`FieldFilterSet`仅保留package-private原子/range合并方法。上述工具不得注入AgentProperties domain、D04实现或Adapter Registry。

字段校验必须区分“字段不存在”和“字段存在但当前主体未授权”：前者仍归一为`PLAN_VALIDATION_FAILED`；后者抛出受控字段越权异常并由Core映射为`FIELD_FORBIDDEN`。该判断以D04 Canonical field存在性和D02_03 `ExecutionValidationProjection.fieldRules`交集为依据，不得把未授权字段伪装为unknown field，也不得自动删除用户显式请求字段后继续执行。

---

## 6. Core 稳定端口

所有接口位于 `kernel.port`，由 D02_03 实现。

| 接口 | 方法 |
|---|---|
| `AuthorizationExecutionPort` | `ExecutionScope recheck(AuthorizationSnapshot snapshot, InvocationHandle handle)` |
| `ContextExecutionPort` | `void revalidateAll(List<ContextSnapshot> snapshots, InvocationHandle handle, ResolvedRegistration registration, ExecutionScope scope)` |
| `DomainExecutionPort` | `DomainExecutionResolution resolve(DomainBindingRequest request)` |
| `ContextApprovalPort` | `List<ApprovedContextWrite> approve(List<ContextWriteCandidate> candidates, ContextApprovalRequest request)` |
| `ResultSecurityPort` | `SecuredResult secure(Object candidate, ContractRef outputContract, ExecutionScope scope)` |

`DomainBindingRequest` 和 `ContextApprovalRequest` 由 D02_03 所有的不可变值对象承载，不接受自由 Map/JSON。

---

## 7. Execution 模型

### 7.1 `ExecutionCommand.java`

字段仅有：`InvocationHandle handle`、`ExecutablePlanningResult planningResult`、`CancellationToken cancellation`。全参构造器和三个访问器，无 setter。

构造器确认 Handle 与 PlanningResult 的 correlation、subject/Owner/Scope 和 deadline 一致。Registration、Raw Plan、Snapshot 不得作为可替换并列参数。

### 7.2 `ExecutionValidationContext.java`

字段：capabilityId、planKind、domainMode、`ExecutionScope`、`ExecutionValidationProjection`、可选`AdapterExecutionBinding`、按contextType唯一的不可变`List<ContextSnapshot>`、absoluteDeadline、CancellationToken。全参构造器和只读访问器。

### 7.3 `ExecutionContext.java`

字段：invocationId、ExecutionSubjectRef、ContextOwnerRef、InvocationScope、可选 AdapterExecutionBinding、absoluteDeadline、CancellationToken。

公开方法：只读访问器和 `<P extends AgentAdapterPort> P requireAdapter(Class<P> portType)`；该方法只验证已绑定 port 类型，不查询 Registry、不按 domain 路由。

### 7.4 `ExecutionOutcome`

```java
public sealed interface ExecutionOutcome permits ExecutionSuccess, ExecutionFailure {}
```

`ExecutionSuccess` 字段：`SecuredResult securedResult`、`List<ApprovedContextWrite> approvedContextWrites`、capabilityId、planKind。

`ExecutionFailure` 字段：`ExecutionStage stage`、`KernelErrorCode errorCode`、`String diagnosticId`、`boolean cancelled`、`String safeMessage`。

`safeMessage`只允许保存可直接展示给用户的安全提示，不包含异常类名、SQL、下游响应、权限正文、JWT、敏感字段值或完整字段清单之外的内部细节。字段越权场景使用`FIELD_FORBIDDEN`并写入“当前角色无权限访问请求字段：{字段列表}。请调整查询字段或联系管理员授权。”；其他执行失败可为空，由D02_02 Lifecycle使用通用兜底提示。

不存在 boolean success + nullable 字段组合；Core 不返回 API DTO，不声明持久化终态。

---

## 8. Execution Core 13 步算法

`ExecutionCore` 构造器注入第 6 节五个端口和 `Clock`；唯一公开方法为 `ExecutionOutcome execute(ExecutionCommand command)`。

| 步骤 | 动作 | 失败后禁止 |
|---|---|---|
| 1 | 校验 Handle/correlation/deadline/cancellation | Registration/外部端口 |
| 2 | 校验 ResolvedRegistration identity 与不可变引用 | 后续全部 |
| 3 | 校验capabilityId/planKind/selected domain与Registration/PlanningResult绑定，并校验raw subtype；D01 Raw Plan不重复capabilityId/domain | 授权/Validator |
| 4 | `AuthorizationExecutionPort.recheck` | Context/Validator/Handler |
| 5 | 对每个ContextSnapshot复检request correlation、Owner、Scope、source domain、stored/effective ContractRef及迁移器、record version、readable、TTL，并拒绝重复contextType | Binding/Validator/Handler |
| 6 | 校验DomainMode/domain；NONE或OPTIONAL无domain时不调用Domain端口并使用`ExecutionValidationProjection.none()`；OPTIONAL有domain或REQUIRED时只调用一次resolve取得同时含required Binding与projection的`DomainExecutionResolution`，任一绑定不一致即失败且不降级 | Validator/Handler |
| 7 | 构建最小 ExecutionValidationContext，再检查 deadline/cancel | Validator |
| 8 | 通过 Registration 唯一 invoker 调用 Validator，得到 ValidatedPlanHandle | Handler |
| 9 | 构建 ExecutionContext，再检查 deadline/cancel | Handler |
| 10 | 通过同一 Registration invoker 调用 Handler | 输出处理 |
| 11 | 校验 output runtime type、output ContractRef、Context candidate type/ContractRef/声明 | 安全过滤/持久化 |
| 12 | 先执行 ResultSecurityPort，再按 Effective Context Write Scope 审批 Context writes | Lifecycle SUCCESS |
| 13 | 返回 ExecutionSuccess 或安全 ExecutionFailure | — |

Context 当前性失败不得重载另一份 Context或重做 Planning。权限范围缩小时，只要计划使用的 capability/domain/field/operator/context 仍在 ExecutionScope 内可以继续；任何必要项被撤销即 fail closed。

### 8.1 异常归一化

Core 在阶段边界捕获已知安全异常并映射为 `ExecutionFailure`。未知异常只记录 diagnosticId，不把类名、堆栈、SQL、下游原文或权限事实放入 errorCode/message。

阶段至少包含 `EXECUTION_PREFLIGHT`、`AUTHORIZATION`、`CONTEXT_VALIDATION`、`BINDING`、`PLAN_VALIDATION`、`HANDLER`、`ADAPTER_DOWNSTREAM`、`OUTPUT_VALIDATION`、`RESULT_SECURITY`、`CONTEXT_APPROVAL`、`CANCELLATION_DEADLINE`。

存在但未授权字段的受控异常必须在`PLAN_VALIDATION`阶段映射为`KernelErrorCode.FIELD_FORBIDDEN`，并保留安全`safeMessage`。它不同于Runtime输出结构错误、未知字段、operator不支持等计划无效问题；后者仍映射为`PLAN_VALIDATION_FAILED`。Entry/API层必须穷尽映射`FIELD_FORBIDDEN`到`AGENT_FIELD_FORBIDDEN`，不得落入`AGENT_PLAN_INVALID`默认分支。

Runtime PlanOutcome 进入 Core 前必须已经完成 D01 绑定校验或在 Runtime 本地完成受限输出修复：仅允许把已解析 envelope 的 `requestId` 归一化为当前 PlanRequest 标识，并按 `repairLimit` 修复结构化输出。Core、Registration、Validator 不二次修复 Runtime 原始输出，也不把 `OUTPUT_REPAIR_EXHAUSTED` 当作字段权限或业务校验错误；该错误仍属于 Planning failure 的 `RUNTIME_OUTPUT_INVALID` 路径。

---

## 9. Adapter Binding

`AdapterExecutionBinding`由D02_03/D04 seam创建，字段为AdapterRole、domain、`Class<? extends AgentAdapterPort> portType`、`AgentAdapterPort port`、adapter registration version。`DomainExecutionResolution`把该binding、`ExecutionValidationProjection`和同一`DomainMetadataEvidence`封装为不可变值；Core不接受二者作为可替换并列返回。它们不包含全局Registry、Catalog、用户权限或数据库配置。

DomainMode分支固定如下：NONE必须无domain/role/binding；OPTIONAL无domain时使用empty projection和empty binding，OPTIONAL有domain时必须完整绑定；REQUIRED必须有domain并完整绑定。已选择domain后若D04不可用，Core必须失败，禁止退回domainless执行。

D04必须先在`agent-adapter-api`增加稳定marker `AgentAdapterPort`，并使现有`QueryableAdapter`、`AggregatableAdapter`扩展该marker；D04的AdapterRegistration随后才能校验port type。D03只消费这些已评审端口。Handler只能使用`ExecutionContext.requireAdapter(QueryableAdapter.class)`等已绑定端口。

---

## 10. 测试与架构门禁

### 10.1 Registration

| 测试方法 | 断言 |
|---|---|
| `rejectsDuplicateCapabilityId` | 启动失败 |
| `rejectsRawPlanKindMismatch` | subtype/planKind 不闭合 |
| `rejectsValidatorHandlerGenericMismatch` | 唯一类型桥拒绝 |
| `rejectsUnresolvableContractRef` | 启动失败 |
| `rejectsNonRuntimeContractForRuntimeSchemaRef` | 不能手工或错误投影PlanRequest inputSchemaRef |
| `pinsExecutionContractRefsAndStructuralDigests` | 七个Java ContractRef唯一；Runtime输入版本绑定D01；output/context结构变化必须显式升版 |
| `bumpsQueryContextContractForPaginationTotalsAndSorts` | `QUERY_CONTEXT`为1.2.0且包含sorts/total/totalExact/totalPages；旧1.0.0和1.1.0必须有兼容读取或精确迁移路径 |
| `bumpsQueryResultContractsForSortEcho` | `QUERY_RESULT`和`QUERY_PREVIEW_RESULT`为1.1.0，`AgentQueryParameters.sorts`可序列化且由ResultSecurity按scope过滤 |
| `keepsRuntimeOutputRepairOutsideCore` | Runtime `requestId`归一化、repairAttempts和`OUTPUT_REPAIR_EXHAUSTED`不进入Core修复分支；Core只消费已绑定Plan或Planning failure |
| `rejectsInvalidDomainModeRole` | NONE/REQUIRED 规则成立 |
| `resolvesOnlyByCapabilityId` | 不存在 planKind→Handler API |
| `doesNotExposeMutableRegistration` | 集合/字段不可变 |

### 10.2 Core

必须覆盖步骤 1～13 的成功和每个失败短路，包括：registration 调换、raw subtype、撤权、Context owner/scope/schema/recordVersion/TTL 变化、Binding 缺失/重复、Validator/Handler/Adapter异常、output type/ContractRef、Context声明、过滤/mask失败、deadline/cancel、迟到结果。

关键测试名：

- `rejectsContextChangeBeforeValidator`
- `neverReloadsContextAfterCurrentnessFailure`
- `invokesValidatorBeforeHandler`
- `usesOneBindingForValidatorAndHandler`
- `resolvesBindingAndProjectionAsOneDomainResolution`
- `doesNotCallDomainPortForNoneOrDomainlessOptional`
- `rejectsSelectedDomainBindingFailureWithoutDomainlessFallback`
- `mergeQueryContextForSecondTurnPagination`
- `rejectsQueryMergeWhenPreviousContextMissing`
- `mapsForbiddenFieldToFieldForbiddenFailure`
- `fieldForbiddenCarriesSafeMessage`
- `doesNotPersistOrBuildApiResponse`
- `doesNotInvokeLaterStageAfterFailure`
- `returnsApprovedWritesOnlyAfterResultSecurity`

### 10.3 扩展与静态门禁

- 用户表达层“新增意图”若仍属于已有 capability 语义，只修改对应Registration的typed Routing Descriptor/行为资产及测试；若引入新的业务动作或授权/执行语义，则新增Capability Registration，必要时才新增PlanKind。两类情况都不得恢复`AgentIntent`枚举、intent→Handler switch或修改Core/Planning主算法。
- `addsRoutingIntentToExistingCapabilityWithoutSharedFlowChange`
- `registersSecondCapabilityOfSamePlanKindWithoutCoreChange`
- `addsDomainThroughD04PortWithoutCoreOrHandlerChange`
- ArchUnit：Core 不依赖 persistence/metadata implementation/Runtime client。
- AST/源码扫描：Core、Registry、Catalog 不含具体 capabilityId/domain 字面量分支。
- 全仓扫描：`@SuppressWarnings("unchecked")` 只允许 `TypedRegistrationInvoker`。

---

## 11. 计划文件清单

| 范围 | 文件数 | 说明 |
|---|---:|---|
| `agent-api contract/common` | 2 | `ContractRef`、`AgentExecutionContracts` |
| `kernel/definition` | 6 | Definition、Descriptor、Context declarations、ContractRegistry |
| `kernel/config` | 1 | 通用composition root |
| `kernel/registration` | 7 | Registration、Registry、validator、resolved、invoker、handles |
| `kernel/validator` | 2 | Validator、ValidatedPlan |
| `kernel/handler` | 2 | Handler、HandlerResult |
| `kernel/core` | 7 | Core、Command、contexts、outcome variants；`ExecutionFailure`包含安全`safeMessage` |
| `kernel/port` | 5 | 稳定执行端口 |
| `agent-adapter-api`（D04前置，不计入D03文件） | 1 NEW + 2 MODIFY | marker；现有Queryable/Aggregatable继承，由D04 L2列出并实施 |
| agent-api response | 4 NEW + 2 MODIFY | sealed result payload、kind、两种payload、ChatResponse/ResponseType收敛 |
| tests | 6 | API result/Contract constants、Registration、Core、Architecture、Extension |
| capability local config | 2 | Query/Aggregate各自Registration Bean |
| capability concrete implementation/utilities | 11 | 2 Validator、2 Handler、2 ValidatedPlan、5内部工具 |
| existing capability tests | 4 | Query/Aggregate Validator/Handler tests |
| build | 1 MODIFY | `agent-service/pom.xml`增加`com.tngtech.archunit:archunit:1.4.2` test scope；Testcontainers/MySQL已存在不重复声明 |
| **D02_01范围合计** | **62个计划变更文件** | 另有3个agent-adapter-api文件属于D04；Planning merge文件归D02_00 |

详细文件名以第2.1节、`kernel/config/CapabilityKernelConfiguration.java`、`capability/query/QueryCapabilityConfiguration.java`、`capability/aggregate/AggregateCapabilityConfiguration.java`为准；Agent API新增`AgentResultKind.java`、`AgentResultPayload.java`、`QueryAgentResultPayload.java`、`AggregateAgentResultPayload.java`并修改`AgentChatResponse.java`、`AgentResponseType.java`。具体实现为`QueryPlanValidator.java`、`QueryCapabilityHandler.java`、`ValidatedQueryPlan.java`、`AggregatePlanValidator.java`、`AggregateCapabilityHandler.java`、`ValidatedAggregatePlan.java`、`QueryParameterMapper.java`、`OperatorSemantics.java`、`FilterNormalizer.java`、`FieldFilterSet.java`、`FieldConstraintValidator.java`。测试为`AgentResultPayloadContractTest`、`AgentExecutionContractsTest`、`CapabilityRegistryTest`、`ExecutionCoreTest`、`KernelArchitectureTest`、`CapabilityExtensionTest`、`QueryPlanValidatorTest`、`QueryCapabilityHandlerTest`、`AggregatePlanValidatorTest`、`AggregateCapabilityHandlerTest`；分页与权限拒绝补充用例为`mergeQueryContextForSecondTurnPagination`、`rejectsQueryMergeWhenPreviousContextMissing`、`rejectsPageGreaterThanTotalPagesWhenTotalExact`、`mapsForbiddenFieldToFieldForbiddenFailure`。

### 11.1 完整方法索引

| 类/接口 | 方法 |
|---|---|
| `ContractRegistry` | `from(Collection<CapabilityRegistration<?,?,?>>)`、`require(ContractRef)`、`isCompatible(ContractRef,ContractRef)`、`all()`、`runtimeSchemaRef(ContractRef)` |
| `AgentExecutionContracts` | private构造器；仅七个public static final ContractRef常量，无public方法 |
| `AgentResultPayload` | `getResultKind()` |
| `AgentResultKind`、`AgentResponseType` | 仅enum隐式`values()`、`valueOf(String)` |
| `QueryAgentResultPayload` | 构造器、只读`getResultKind()`、`get/setQueryParameters`、`get/setQueryResult` |
| `AggregateAgentResultPayload` | 构造器、只读`getResultKind()`、`get/setAggregateResult` |
| `AgentChatResponse` | 构造器；conversationId/turnId/type/message/summary/result/errorCode getter/setter |
| `ContextAccessDeclaration` | `read(RuntimeContextType)`、`write(RuntimeContextType)`、`validateNoDuplicateType()` |
| `CapabilityDefinition` | 全参构造器和十组只读访问器 |
| `CapabilityRegistration` | 六个访问器、`identity()`、`validateRaw`、`executeValidated`、`validateOutput` |
| `TypedRegistrationInvoker` | `validate(AgentPlan,ExecutionValidationContext)`、`execute(ValidatedPlanHandle,ExecutionContext)`、`validateOutput(Object)` |
| `ResolvedRegistration` | 四个访问器、`validateIdentity()` |
| `CapabilityRegistrationValidator` | `validateAll(Collection,ContractRegistry,Set<AdapterRole>)` |
| `CapabilityRegistry` | `resolve(String)`、`registrations()`、`capabilityIds()`、`coverageByPlanKind()` |
| `CapabilityKernelConfiguration` | `contractRegistry(List<CapabilityRegistration<?,?,?>>)`、`capabilityRegistry(List<CapabilityRegistration<?,?,?>>,ContractRegistry,CapabilityRegistrationValidator,DomainMetadataPort)` |
| `QueryCapabilityConfiguration` | `querySearchRegistration(QueryPlanValidator,QueryCapabilityHandler)` |
| `AggregateCapabilityConfiguration` | `aggregateComputeRegistration(AggregatePlanValidator,AggregateCapabilityHandler)` |
| `CapabilityPlanValidator` | `validate(R,ExecutionValidationContext)` |
| `CapabilityHandler` | `execute(V,ExecutionContext)` |
| `HandlerResult` | `of(O)`、`of(O,List<ContextWriteCandidate>)`及访问器 |
| `QueryPlanValidator` | `validate(QueryAgentPlan,ExecutionValidationContext)` |
| `QueryCapabilityHandler` | `execute(ValidatedQueryPlan,ExecutionContext)` |
| `AggregatePlanValidator` | `validate(AggregateAgentPlan,ExecutionValidationContext)` |
| `AggregateCapabilityHandler` | `execute(ValidatedAggregatePlan,ExecutionContext)` |
| `QueryParameterMapper` | package-private `toQueryParameters(ValidatedQueryPlan)` |
| `FilterNormalizer` | `normalizeAll(List<AgentFilter>,ExecutionValidationProjection)`、`normalize(AgentFilter,ExecutionFieldRule)` |
| `FieldConstraintValidator` | `validateChanges(List<ValidatedFilter>,Set<String>,ExecutionValidationProjection)`、`validateFinalQuery(List<ValidatedFilter>,ExecutionValidationProjection)` |
| `OperatorSemantics` | `profileOf(AgentOperator)`、`supports(AgentOperator,AgentFieldType)` |
| `ExecutionContext` | 只读访问器、`requireAdapter(Class<P>)` |
| `ExecutionCore` | `execute(ExecutionCommand)` |
| 五个kernel port | 第6节列出的唯一方法 |

其余Definition/Context declaration、handle、command、context和outcome类型均为record或defensive-copy final value，只暴露规范化构造器和只读访问器。

---

## 12. 验收标准与结论

1. Definition 不保存动态 enabled/权限/实现类，Routing Descriptor 不是 JSON String。
2. Registration 不可变绑定 Definition、Raw Plan、Validator、Validated Plan、Handler、output type。
3. Registry 只按 capabilityId 解析。
4. unchecked cast 只存在于 TypedRegistrationInvoker。
5. Core 接收内部 ExecutablePlanningResult，不接收 D01 ExecutablePlan 作为完整命令。
6. Core 13 步顺序与 L1 一致，Context 当前性在 Validator 前。
7. Handler 能返回 ContextWriteCandidate，但不能提供 Owner/Scope/expiry 或持久化。
8. ResultSecurity 与 ContextApproval 在 Lifecycle 持久化前完成。
9. Core 无持久化、Runtime、API response、capability/domain 专用分支。
10. 所有类、方法、端口、测试和计划文件有唯一所有者。
11. `QUERY_CONTEXT` 1.2.0 的分页总数字段只用于多轮规划状态，不进入Adapter执行请求；`sorts`只作为上一轮排序状态，进入Adapter前必须重新形成`ValidatedQuery.sorts`并通过`ExecutionValidationProjection.sortFields`校验。
12. `FIELD_FORBIDDEN` 与`ExecutionFailure.safeMessage`链路可证明字段越权不会被误报为`AGENT_PLAN_INVALID`。
13. Runtime output repair 不改变Core职责：`requestId`绑定和结构修复发生在Planning Runtime边界，Core不得引入原始LLM输出修复分支。

最终评审结论（2026-06-30）：本文已与D02_00、D02_02、D02_03及三份L1交叉复审；类型桥、执行顺序、Context当前性、Adapter Binding、输出/Context安全和扩展不变量完整闭合，当前文档基线下无未决问题。实际D01类名/包名/字段以D01退出门禁产物复核为生效条件。

2026-07-05 授权同步结论：QUERY 白名单排序属于已批准的增量契约变更，未改变 Core 13 步顺序、Handler 不做授权决策、Adapter 只执行已验证命令等 D02 不变量。实现前必须以本节新增版本和校验规则为准，补齐 D01/D02_03/D04/D05 的关联同步和契约测试。
