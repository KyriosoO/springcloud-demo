# Adapter 与 Domain Metadata 治理 L2 实施详细设计 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档状态 | In Review |
| 当前版本 | v2.0 |
| 创建/最后更新日期 | 2026-07-13 |
| 适用代码基线 | `816e2c855574da5326379128bfb3e230241d2fe3` |
| 设计层级 | L2 实施详细设计 |
| 适用阶段 | P1_V2 单 Agent 内核收敛 |
| 文档路径 | `docs/design/P1_V2/04_Adapter与DomainMetadata治理_L2实施详细设计_v2.0.md` |
| 权威范围 | Canonical Domain Field Catalog、Adapter Role/Registration、请求级 Domain 投影、一次 Adapter Binding、QUERY 白名单排序 |
| 前置阅读 | L0/L1、P1_V2/00～03 |
| 历史来源 | P1/D04 与 Agent 与业务域白名单排序设计；仅作来源留档，不再是实施前置 |

## 2. 修订历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | 合并 Adapter/Domain Metadata 收敛与 QUERY 白名单排序 | 形成可独立实施的 v2.0 基线 |
| 2 | 2026-07-13 | 4～24 | cross-layer 评审发现 Registration 动态化/重复类型与版本、Catalog 混入资源上限、静态 bundle 混入动态健康、Validator 直读事实源、Execution 投影与 Binding 分次解析、清理和扩展门禁不完整 | 收敛唯一事实源与静态装配，分离请求级 availability evidence，冻结原子执行解析接口、投影模型、排序安全链、删除矩阵和新 Domain 无 Core 改动验证 |

## 3. 文档状态说明

本文处于 **In Review**，用于后续实施拆分。本文不授权代码、公共 HTTP 契约或下游服务变更；`transaction-api` 等公共契约若在 P1_V2/06 实施时仍需变化，必须另行确认兼容范围。未经用户确认不得标记 Approved。

## 4. 背景与目标

当前代码已经形成 Catalog、Registration 和 Adapter SPI 雏形，但仍存在四类双来源：Validator 直接读取 `DomainCatalogView`，Domain role metadata 保存 page/result 资源上限，Runtime Prompt 示例硬编码真实业务字段，Domain execution 先后调用 projection 与 bind。上述结构会让权限、可执行能力和 Adapter 选择在新增 Domain 时发生漂移。

本文把 Domain 静态事实、部署装配事实、请求级可用性和执行绑定分为四层，确保：

1. Canonical Domain Field Catalog 是 Agent 内 field/operator/function/role capability 的唯一事实源；
2. Adapter Registration 只绑定 `(AdapterRole, domainId)` 与兼容 typed port，不保存动态 `enabled`、权限或字段清单；
3. Profile/Policy/Permission/健康度只参与请求级投影，不反写 Catalog/Registration；
4. Core 每个 Invocation 原子解析一次 Execution Validation Projection 与 Adapter Execution Binding；
5. 新增 Domain 只增加 Catalog 数据、Adapter/Registration、Policy、下游 API 依赖和 composition root 装配，不修改 Planning/Core/Lifecycle/既有 Handler/Validator。

## 5. 设计范围

### 5.1 范围内

- `agent-adapter-api` 的角色化 SPI、typed request/result 和调用上下文。
- `agent.domain-metadata` 唯一配置输入、不可变 Catalog/Registration bundle、启动/reload gate。
- Route Projection、Runtime Domain Schema、Execution Validation Projection 与一次 Adapter Execution Binding。
- QUERY 用户排序契约、Context 继承、Adapter/downstream 安全映射和结果回显。
- employee/transaction 代表性 coverage test 与新 Domain 无 Core 改动门禁。
- 旧配置、Prompt、Adapter 自报清单、Java Domain 事实副本的清理矩阵。

### 5.2 范围外

- Profile/Policy/Permission 计算、Authorization Snapshot 和 Result Security 算法，归 P1_V2/03。
- Effective Capability Resource Limits 与 `CapabilityOperationContext` 的通用结构，归 P1_V2/05；本文只消费其接口。
- Invocation/Lifecycle 状态机和 finalization，归 P1_V2/02。
- 文档检索编排、索引、ACL、证据输出和生成预算，归 P2_V3。
- 业务域数据库/索引物理设计、远程 Adapter 注册中心、负载均衡和 Multi-Agent 调度。

## 6. 上级文档约束

1. 当前只实现 CHAT/ConversationScope；不新增 Task、Run、Delegation 存储、ResultRef 或远程 Agent owner/locality 字段。
2. Catalog/Registration 是版本化静态事实；部署启停、健康、Policy 和请求权限形成请求级 availability。
3. Route Projection 不含 field schema；Runtime Domain Schema 仅在 capability/domain 确定后生成。
4. Core 在当前授权复检后只解析一次 Binding；Handler 不持有 Registry，也不二次路由。
5. Validator、Handler、Provider、Result Security 使用 Authorization Snapshot 冻结的同一或更严格资源限额；Domain metadata 不保存 `maxPageSize/maxResultRows/maxResultBytes`。
6. P1_V2/06 原子迁移前不得发布新旧 Catalog、权限、Context 或 Adapter metadata 并行链。

## 7. 关联文档与边界

| 文档 | 本文依赖 | 本文输出给对方 |
|---|---|---|
| P1_V2/01 | Java ContractRef、Runtime Domain Schema、Query/Context/Result 契约 | canonical 字段、排序和投影生成规则 |
| P1_V2/02 | Core 固定时序、Resolved Registration、Execution Context | `DomainExecutionPort.resolve` 的一次解析结果 |
| P1_V2/03 | PlanningEffectiveScope、ExecutionScope、DomainMetadataEvidence | availability、Route/Plan/Validation 最小投影 |
| P1_V2/05 | Effective limits、Cancellation、CapabilityOperationContext | Adapter SPI 消费同一 operation context |
| P1_V2/06 | 原子迁移、旧路径删除和发布门禁 | 精确删除清单、实施落点、验收命令 |
| P2_V3/04 | Document retrieval 专用 request/response | 仅复用 `DOCUMENT_RETRIEVABLE` role/binding，不定义检索编排 |

## 8. 设计边界与不变量

| 不变量 | 强制规则 |
|---|---|
| Stable IDs | `domainId` 使用 lower snake case；`fieldId/operatorId/functionId` 使用 Java 契约声明的 canonical 标识；禁止物理列名/索引字段进入 Runtime |
| 单一事实源 | Agent 可声明的 Domain field/operator/function/role capability 只来自 `CanonicalDomainCatalog` |
| Registration 静态化 | 不含 `roles` 集合、动态 `enabled`、health、permission、field list、endpoint、credential |
| 权限隔离 | Catalog/Adapter health 不授予权限；Domain metadata 只消费已计算的 Planning/Execution scope |
| 预算隔离 | Catalog、Projection 不保存 page/result/evidence/generation 上限；Validator 从 `resourceLimits()` 读取 typed limits |
| 投影只读 | 所有 Projection/Snapshot/Binding 只在当前请求内有效，不反向更新事实源 |
| 一次 Binding | 非 `NONE` Domain 每个 Invocation 只调用一次 `DomainExecutionPort.resolve`，同时得到 projection 和 binding |
| Adapter 无二次路由 | Handler 只能从 `ExecutionContext` 获取已绑定 typed port；禁止注入全局 RegistrationSet/ApplicationContext |
| 下游防御 | 下游公共 API 继续独立校验字段/排序，Agent Catalog 不替代服务边界校验 |
| 扩展封闭 | 新 Domain 不修改 Catalog 算法、Planning/Core/Lifecycle、共享 Prompt、现有 Handler/Validator |

## 9. 总体设计

```text
config-service/agent-service.yml::agent.domain-metadata
    + Spring composition root 中的 AgentAdapterPort beans
        -> DomainMetadataStaticBundleCandidateBuilder
        -> reference/coverage/type/version/digest 全量校验
        -> immutable DomainMetadataStaticBundle
        -> DomainMetadataStore atomic publish

受控 deployment/health signal（只表达 AVAILABLE/UNAVAILABLE）
    + PlanningEffectiveScope + static bundle evidence
        -> DomainAvailabilitySnapshot
        -> Domain Routing Projection（无字段）
        -> RouteDecision + ResolvedRegistration
        -> Runtime Domain Schema（最小字段/操作符/函数）

ExecutionScope + selected domain + expected evidence
        -> DomainExecutionPort.resolve（一次）
        -> DomainExecutionResolution
             ├─ ExecutionValidationProjection -> Validator
             └─ AdapterExecutionBinding -> ExecutionContext -> Handler -> typed Adapter
```

`CanonicalDomainCatalog` 与 `AdapterRegistrationSet` 必须作为一个 `DomainMetadataStaticBundle` 原子发布，禁止分别刷新或使用多个 `AtomicReference`。Deployment/health 属于请求级动态输入，不写回静态 bundle；`DomainAvailabilitySnapshot` 把本次使用的 static evidence 与 availability evidence 绑定成 `DomainMetadataEvidence`。

## 10. 详细功能设计

### 10.1 唯一存储与装配来源

当前阶段唯一持久输入是 `config-service/src/main/resources/config/agent-service.yml` 的 `agent.domain-metadata`。`DomainMetadataProperties` 只是 Spring 可变绑定对象，不是运行时事实源；`DomainMetadataStaticBundleCandidateBuilder` 必须一次性把它转换为不可变对象。当前不新增 Domain metadata 数据库、远程 Registry 或 Adapter 自描述接口。

配置根字段固定为：

| 字段 | 必填 | 语义 |
|---|---:|---|
| `catalog-version` | 是 | Catalog 单调版本；非空稳定标识 |
| `adapter-registration-version` | 是 | RegistrationSet 单调版本 |
| `domains` | 是 | `domainId -> DomainProperties`，至少一项 |
| `registrations` | 是 | 一项只绑定一个 role/domain/port bean |

配置中心 reload 事件只能触发完整 candidate 构建；不得把原始 Properties 暴露给 Planning、Validator、Handler 或 Adapter。

### 10.2 Canonical Domain Field Catalog

不可变模型冻结为：

```java
public record CanonicalDomainCatalog(
    String catalogVersion,
    Map<String, CanonicalDomainDefinition> domains,
    String canonicalDigest) {}

public record CanonicalDomainDefinition(
    String domain,
    List<String> aliases,
    String description,
    Map<AdapterRole, List<String>> defaultSelectFieldsByRole,
    Map<String, CanonicalFieldDefinition> fields,
    Map<AdapterRole, CanonicalRoleCapability> roleCapabilities) {}

public record CanonicalFieldDefinition(
    String field,
    List<String> aliases,
    String description,
    AgentFieldType type,
    Optional<String> unit,
    Optional<String> valueFormat,
    Optional<Integer> maxLength,
    Optional<Integer> precision,
    Optional<Integer> scale) {}

public record CanonicalRoleCapability(
    AdapterRole role,
    Set<String> fields,
    Set<String> sortFields,
    Map<String, Set<AgentOperator>> operatorsByField,
    Map<String, Set<AggregateFunction>> functionsByField) {}
```

`CanonicalRoleCapability` 不保留 `maxPageSize/maxResultRows`。`defaultSelectFieldsByRole`、`sortFields`、operator/function map 的 key 都必须是该 role `fields` 子集；field type 与 operator/function 必须通过 Java 权威兼容矩阵。Catalog 不保存 sensitivity/mask/用户角色/权限、Profile/Policy、Capability Definition、Adapter endpoint/credential 或下游实时状态。

`canonicalDigest` 采用版本化 `DCF-1` canonical form + SHA-256 lowercase hex：domain、role、field、operator、function 按稳定标识排序；别名保持声明顺序且去重。禁止 `Objects.hash/hashCode`、Java 序列化或 Map 迭代顺序参与 digest。

### 10.3 Adapter Role 与 SPI

`AdapterRole` 是 `agent-adapter-api` 中的 Java 权威值类型；当前注册 `QUERYABLE`、`AGGREGATABLE`、`DOCUMENT_RETRIEVABLE`。`AdapterRolePortTypes` 是 role 到接口类型的唯一封闭映射：

| AdapterRole | Port type | 方法 |
|---|---|---|
| QUERYABLE | `QueryableAdapter` | `query(ValidatedQuery, CapabilityOperationContext)` |
| AGGREGATABLE | `AggregatableAdapter` | `aggregate(ValidatedAggregateQuery, CapabilityOperationContext)` |
| DOCUMENT_RETRIEVABLE | `DocumentRetrievableAdapter` | `retrieve(DocumentRetrievalRequest, CapabilityOperationContext)` |

新增 Domain 必须复用现有 role。只有执行端口语义确实新增时，才可在同一变更中增加 `AdapterRole` 常量、typed port、`AdapterRolePortTypes`、契约测试和上级设计授权；不能通过自由字符串绕过 port type gate。

SPI 只接收已验证业务请求与 P1_V2/05 定义的 operation context。禁止接收 Runtime/Web DTO、Raw Plan、Profile/Policy/Permission、ExecutionScope、JWT、Prompt、全局 Registry 或独立 timeout；禁止 Adapter 自动重试。

### 10.4 Adapter Registration

```java
public record AdapterRegistration(
    String registrationId,
    AdapterRole role,
    String domain,
    String portBeanName,
    String registrationVersion) {}
```

`AdapterRegistrationSet` 以 `(role,domain)` 为唯一 key，提供 `find/require/roles/domains/sortedRegistrations`。`portType` 只能由 `AdapterRolePortTypes.requirePortType(role)` 派生，Catalog version/digest 只能由所在 static bundle 绑定；二者均不得在逐项 Registration 中重复配置。禁止把多个 role 合并为一个 Registration，也禁止 `enabled`、health、field/operator/function、用户权限、endpoint 或 credential 字段。多个物理实例的负载均衡/故障转移必须封装在唯一逻辑 port 之后。

Candidate builder 必须从同一 Catalog 派生 `CanonicalRoleCapabilityRef(catalogVersion,catalogDigest,domain,role)` 并随 RegistrationSet 索引保存；该引用不是配置字段，也不复制 field/operator/function 清单。Binding identity 使用此引用证明端口绑定到了哪份 canonical role capability。

Candidate build 必须校验：

1. role 由 `AdapterRolePortTypes` 识别；
2. domain/role 在同一 Catalog 中存在；
3. static bundle 把整个 RegistrationSet 与同一 Catalog version/digest 绑定，不接受逐项 Catalog version；
4. bean 存在且实现 role 派生的权威 port type；
5. 同一 `(role,domain)` 只有一项、registrationId 唯一；
6. 每个 Catalog role capability 恰有一个 Registration，每个 Registration 被 Catalog 引用；
7. registration version 非空且进入 bundle evidence/digest。

任一项失败时启动失败或拒绝 reload candidate，不能通过跳过 Domain、回退旧常量或标记 `enabled=false` 隐藏错误。

### 10.5 静态事实与动态 Availability

`AdapterAvailabilityResolver.capture(keys,deadline)` 返回请求级不可变 `AdapterDeploymentAvailability`，只保存 `(role,domain)->AVAILABLE|UNAVAILABLE`、受控 reason code、capturedAt 和 canonical digest，不保存字段能力。信号来源限于已验证 bean 装配、部署开关和当前健康检查；未知/超时按 UNAVAILABLE。Profile/Policy/Permission 不写入该对象，也不触发 static bundle reload。

请求级计算固定为：

```text
DomainAvailabilitySnapshot(role)
  = RegistrationSet.domains(role)
  ∩ Catalog.domainsSupporting(role)
  ∩ AdapterDeploymentAvailability.available(role)
  ∩ PlanningEffectiveScope.allowedDomains
```

`DomainMetadataPort.availability(roles, scope, deadline)` 只消费调用方已经算出的 `PlanningEffectiveScope`，不得再次读取 Profile、Policy 或 Permission。它把 static evidence、所评估 key 集合和本次 availability digest 绑定进 `DomainMetadataEvidence`。不可用通过不投影表达，不修改 Registration；Execution resolve 时还必须对 expected evidence 覆盖的选定 key 重新检查当前 health 和 `ExecutionScope.allowedDomains`，任何漂移 fail closed。无关 role/domain 的健康变化不使本 Invocation 失效。

### 10.6 Bundle 构建、发布与 Currentness

`DomainMetadataStaticBundle` 固定包含 Catalog、RegistrationSet 和 `DomainMetadataStaticEvidence(catalogVersion,catalogDigest,registrationSetVersion,registrationDigest,publishedAt)`。构建顺序：bind -> normalize -> reference closure -> port type -> Adapter coverage -> digest -> immutable bundle。请求级 `DomainMetadataEvidence` 额外包含所评估 `(role,domain)` key 集合的 canonical digest、availability digest 和 capturedAt，不把 health 写入 static evidence。

`DomainMetadataStore.publish(expectedStaticEvidence,candidate)` 使用一个 `AtomicReference<DomainMetadataStaticBundle>` 执行 compare-and-set：

- candidate 全部校验通过才可发布；
- CAS 失败表示并发 reload，丢弃 candidate 并重新读取，不覆盖新版本；
- 配置校验、bean/type coverage 或静态预热失败时保留旧 ACTIVE bundle 并告警；health timeout 只影响本次请求级 availability，不发布旧健康结论；
- 不建立 `LOADING/VALIDATED/ACTIVE/RETIRED` 持久状态机；这些只是 reload 过程事件；
- `assertCurrent(expected,deadline)` 必须比较 catalog/registration static digest，并通过 availability resolver 只复检 expected evidence 中已评估的 key；变化即当前 Invocation fail closed，不切换新事实继续执行。

### 10.7 DomainMetadataPort 与投影生成

```java
public interface DomainMetadataPort {
    Set<AdapterRole> knownRoles();
    DomainMetadataEvidence validateReferences(
        DomainMetadataReferenceSet refs, Instant absoluteDeadline);
    DomainAvailabilitySnapshot availability(
        Set<AdapterRole> roles, PlanningEffectiveScope scope, Instant absoluteDeadline);
    void assertCurrent(DomainMetadataEvidence expected, Instant absoluteDeadline);
    List<RuntimeDomainRoutingProjection> routeProjection(
        Set<String> domains, PlanningEffectiveScope scope,
        DomainMetadataEvidence expected, Instant absoluteDeadline);
    RuntimeDomainSchema planSchema(
        AdapterRole role, String domain, PlanningEffectiveScope scope,
        DomainMetadataEvidence expected, Instant absoluteDeadline);
    DomainExecutionResolution resolveExecution(
        AdapterRole role, String domain, ExecutionScope scope,
        DomainMetadataEvidence expected, Instant absoluteDeadline);
}
```

删除 `planSchema(agentId,profileId,planningEvidence)` 这类重新读取身份/配置的签名；删除无消费者的 `authorizationEvidenceDigest` 参数。Authorization evidence 由 P1_V2/03 的 Available/Authorization Snapshot 绑定，Domain projection 不复制该 digest。

投影字段上限：

| 投影 | 产生时点 | 允许内容 | 禁止内容 |
|---|---|---|---|
| `RuntimeDomainRoutingProjection` | Route 前 | domain、允许别名、安全描述 | fields/operators/functions/sort/mask/port |
| `RuntimeDomainSchema` | capability/domain 合法后 | 当前允许 field/type/format/operator/function、defaultSelect、sortFields | 权限正文、physical mapping、Adapter、资源上限散字段 |
| `ExecutionValidationProjection` | Execution recheck 后 | role/domain、fieldRules、defaultSelect、sortFields、projectionVersion | port、Profile/Policy、mask、`maxPageSize/maxResultRows` |
| `AdapterExecutionBinding` | 与 validation projection 同次解析 | role/domain、role 派生的 typed port、registration identity/version、catalog/availability evidence、resolvedAt | endpoint、credential、Registry、权限正文 |

Projection builder 是 `DomainMetadataPortImpl` 内部纯函数，不形成第二 Schema Registry 或可注入事实服务。

### 10.8 一次 Execution Resolution

`DomainExecutionPort.resolve(DomainBindingRequest)` 调用一次 `DomainMetadataPort.resolveExecution`，返回同一 bundle view 构造的 `DomainExecutionResolution(binding,projection,evidence)`。删除当前先调用 `executionProjection(role,domain,scope,evidence,deadline)`、再调用 `bind(role,domain,scope,evidence,deadline)` 的两次读取路径。

解析步骤固定为：

1. 校验 deadline/cancellation、expected evidence current；
2. 校验 selected domain 属于 ExecutionScope 且 role/domain 与 Resolved Registration 一致；
3. 校验当前 health 仍 AVAILABLE；
4. 从同一 static bundle 精确 require 唯一 Registration 和 role capability；
5. 计算授权字段与 Catalog capability 的交集，构造 validation projection；
6. 从 composition root 取得声明 bean，复核 typed port；
7. 同时返回 immutable projection/binding；任一步失败均不返回部分结果。

`AdapterExecutionBinding` 只提供 `requirePort(Class<P> expectedType)` 的受控 typed access；Handler 通过 `ExecutionContext` 获取，不能看到 `ApplicationContext` 或 `AdapterRegistrationSet`。Domain Mode `NONE` 由 Core 返回显式 no-binding/no-projection；`OPTIONAL` 无 domain 时同样无需伪造空 Adapter；有 domain 和 `REQUIRED` 必须唯一解析。

### 10.9 Validator 去事实源化

`QueryPlanValidator`、`AggregatePlanValidator`、`DocumentPlanValidator`、`QueryPreviewPlanValidator` 只消费 `ExecutionValidationContext.domainProjection()` 与 P1_V2/05 typed limits。`FilterNormalizer`、`FieldConstraintValidator` 改为消费 `ExecutionFieldRule`/Projection，不得接收 `DomainCatalogView.DomainView`。

`DomainCatalogView` 及其 Spring bean 删除。启动配置引用通过 `DomainMetadataReferenceSet` + `validateReferences` 或 candidate builder 校验，不能让 `AgentPropertiesValidator`、`DefaultAgentMetadataBootstrap` 直接遍历原始 Domain Properties。Capability/document enablement 使用 Capability Registration + availability 通用公式，不保留 `DOCUMENT_RETRIEVABLE` 专用分支。

### 10.10 QUERY 排序契约

Java 公共模型仍以 `AgentQuerySpec.sorts: List<AgentSortSpec>` 表达用户排序；列表 `null` 与空列表必须在反序列化后保持可区分。`AgentSortSpec(field,direction)` 中 direction 只接受 `ASC|DESC`，canonicalizer 使用 `Locale.ROOT` 大写。用户排序最多 2 项、field 不重复；该数量是 Query Contract 结构约束，不是 Domain resource budget。

`QueryPlanValidator` 顺序固定为：结构数量 -> non-null/格式 -> canonical field -> `ExecutionValidationProjection.sortFields` -> fieldRules/current scope -> 去重。禁止通过 `DomainCatalogView` 判断“字段存在但无权限”，外部错误统一为安全的 `PLAN_VALIDATION_FAILED/FIELD_FORBIDDEN`，不泄漏 Catalog 存在性。

Context 继承遵循 P1_V2/03：

- `REPLACE`：无用户排序时使用 domain/adapter 稳定默认顺序；
- `MERGE`：`sorts=null` 继承，`sorts=[]` 清除用户排序并恢复稳定默认，非空列表替换；
- 继承/替换后的用户排序均按当前 projection 复检；
- Query Context 和回显保存 canonical 用户排序，不把 Adapter 追加的内部 tie-breaker 冒充用户输入。

`ValidatedSort` 是进入 Adapter 的唯一用户排序类型。Adapter/downstream 可以追加固定唯一 tie-breaker 以保证分页稳定，但该实现只能引用已通过 coverage gate 的 canonical 字段/物理映射，不能向 Planning/Authorization 自报新能力。

### 10.11 Employee 与 Transaction 安全映射

Employee：`EmployeePlanMapper.toSorts` 只把 `ValidatedSort` 映射为 `SearchSort`；无用户排序时使用稳定默认顺序，非空时追加唯一 tie-breaker。`employee-service` 的 `SEARCHABLE_FIELDS` 是下游服务自身的防御式 API 契约，不是 Agent metadata 来源；coverage test 证明 Agent role fields/sortFields 都是下游集合的子集。

Transaction：`TransactionPlanMapper` 只生成 `TransactionSearchSort`。`TransactionService.buildOrderByClause` 必须再次校验最多 2 个用户 sort、field、去重和 direction，并只从 `FIELD_MAP` 生成固定列名；唯一 tie-breaker 由服务端固定追加。Mapper XML 的 `${orderByClause}` 只接收该内部方法生成值，绝不接收公共请求原文。

`transaction-api` 的 `sorts` 保持可选，旧调用者不传时保持原默认顺序。P1_V2/06 必须执行调用者清单、OpenAPI/fixture/generated model 一致性与兼容测试；若需要改变既有公共字段或语义，实施前另行取得公共契约变更授权。

### 10.12 Prompt、配置和代码副本清理

| 类别 | 位置 | 处理 | 是否保留 |
|---|---|---|---:|
| Runtime Prompt 真实 Domain 示例 | `agent-runtime/app/prompts/query_system.md`、`aggregate_system.md`、`document_system.md` | 把 amount/transType/sourceType/contactAddress 等真实字段示例改为由测试装配的抽象 schema 示例；Prompt 只声明“使用请求中的 schema” | 否 |
| Validator 事实读取 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/DomainCatalogView.java` 及 Query/Aggregate/Document validator、filter helper 的依赖 | 删除 View；统一消费 Execution Validation Projection | 否 |
| Domain 散预算 | `DomainMetadataProperties.RoleCapabilityProperties`、`CanonicalRoleCapability`、`ExecutionValidationProjection`、配置中的 `max-page-size/max-result-rows` | 删除并迁入 P1_V2/05 typed resource contributions/limits | 否 |
| Capability 专用 metadata bootstrap | `DefaultAgentMetadataBootstrap.validateDocumentEnablement/domainNames` 对原始 Domain Properties 的遍历 | 改为通用 Reference/availability gate | 否 |
| Adapter 自报字段能力 | 当前 employee/transaction/document Adapter 无正式自报接口 | 维持禁止；architecture test 禁止新增 `supportedFields/operators/functions` SPI | 否 |
| Adapter 物理映射 | `EmployeePlanMapper`、`TransactionPlanMapper`、Document mapper | 保留 canonical request/result 到下游模型的必要转换，并加 Catalog coverage test | 是 |
| 下游边界白名单 | `EmployeeEsService.SEARCHABLE_FIELDS`、`TransactionService.FIELD_MAP` | 保留服务自主防御与物理列映射；不得被 Agent 当作 metadata 读取 | 是 |
| Result/文档 DTO 字段映射 | Result Security projector、Document evidence mapper 的 typed 字段访问 | 作为 output Contract/防腐映射保留；权限仍来自 ExecutionScope/Result Security | 是 |

删除动作必须与新 Projection/typed limits/Prompt 测试在 P1_V2/06 同一次原子切换中完成，不允许保留兼容 fallback。

### 10.13 新 Domain 扩展流程

新增 Domain 只允许以下改动：

1. 在 `agent.domain-metadata.domains` 增加 Domain/field/role capability；
2. 新增独立 Adapter 实现/模块及必要下游 client/mapper；
3. 增加一个或多个 `(role,domain)` Registration 和 Spring bean 装配；
4. 增加 Policy 允许范围、下游公开 API 依赖和契约/coverage 测试；
5. 若复用既有 Plan Kind/Handler 语义，生产 `PlanningService`、`ExecutionCore`、Lifecycle、既有 Handler/Validator/Prompt 均不得变化。

若现有 Plan/Handler 语义不足，必须按新增 capability/Plan Kind 流程单独设计，不能以 Domain 接入名义向通用 Validator 添加 domain `if/switch`。

## 11. 接口设计

| 接口/类型 | 方法/字段 | 入参 | 返回/约束 |
|---|---|---|---|
| `DomainMetadataPort` | `availability` | roles、PlanningEffectiveScope、deadline | 请求级 `DomainAvailabilitySnapshot` |
| `DomainMetadataPort` | `routeProjection` | domains、scope、expected evidence、deadline | 无字段 schema 的列表 |
| `DomainMetadataPort` | `planSchema` | role、domain、scope、expected evidence、deadline | 最小 `RuntimeDomainSchema` |
| `DomainMetadataPort` | `resolveExecution` | role、domain、ExecutionScope、expected evidence、deadline | 原子 `DomainExecutionResolution` |
| `DomainExecutionPort` | `resolve` | `DomainBindingRequest` | 同一 projection + binding |
| `AdapterRegistrationSet` | `require` | role、domain | 唯一静态 Registration |
| `AdapterExecutionBinding` | `requirePort` | expected typed class | 当前 Invocation port；类型不符 fail closed |
| `QueryableAdapter` | `query` | `ValidatedQuery`、operation context | `AdapterQueryResult` + operation metadata |
| `AggregatableAdapter` | `aggregate` | validated aggregate、operation context | typed result + metadata |
| `DocumentRetrievableAdapter` | `retrieve` | typed request、operation context | typed result + metadata |

本文不新增外部 Agent HTTP API。`transaction-api` 保持现有可选 `sorts` 兼容语义。

## 12. 数据与配置设计

本文不新增数据库表。Catalog/Registration/Projection/Binding 只在内存中存在；Invocation checkpoint 只保存 `DomainMetadataEvidence` 安全引用/digest，不保存 Catalog 全文、port bean name 或健康明细。

配置约束：

- role capability 不再接受 `max-page-size/max-result-rows`；旧字段出现即启动失败，不能静默忽略；
- `registrations[*]` 必须逐项包含 registration-id、role、domain、port-bean-name、registration-version；出现逐项 `port-type/catalog-version` 即拒绝，避免与 role 映射/static bundle 根版本形成双来源；
- 所有未知字段由严格配置绑定/自定义 validator 拒绝；
- test fixture 与生产配置使用同一 candidate builder，不建立测试专用事实源。

## 13. 状态与时序设计

本文不建立持久状态机。静态 bundle 只有“当前已发布引用”和“尚未发布 candidate”；reload 过程的 received/validated/rejected/published 是事件，不入库。

```text
Reload event
  -> build candidate
  -> validate references/types/coverage/digests
  -> reject and keep current
     OR CAS publish complete bundle

Invocation
  -> capture expected evidence during Planning
  -> Execution authorization recheck
  -> one resolveExecution
  -> Validator/Handler use same resolution
  -> evidence changes at any checkpoint: fail closed
```

## 14. 幂等、并发与一致性设计

- 相同 canonical config/version 构建出的 digest 必须一致；同 version 不同 digest 拒绝发布并告警 `METADATA_VERSION_REUSED`。
- reload 使用 bundle 级 CAS；并发 candidate 不得覆盖更新版本。
- Projection/Binding 不跨 Invocation 缓存；允许缓存的仅是以 bundle evidence + permission digest 为 key 的不可变 Planning projection，evidence 变化整体失效。
- Adapter 调用不由本文重试；deadline/cancellation 由 operation context 传递，迟到结果不得进入 Handler candidate。
- 排序必须有稳定 tie-breaker；跨页期间 metadata/权限变化导致当前 Invocation 失败，后续请求重新 Planning/校验 Context。

## 15. 权限、风控与审计设计

- Planning schema 只包含 Catalog、availability 与 PlanningEffectiveScope 的交集；Execution 再按 ExecutionScope 生成更小或相同 projection。
- Catalog capability/health 不授予权限；权限源不可用或 currentness 无法确认一律 fail closed。
- 审计只记录 invocation/correlation 安全引用、domain、role、catalog/registration/availability digest、projection/binding identity、sort field/direction 和拒绝 reason code。
- 应用日志不得记录 JWT、Permission/Profile/Policy 正文、SQL/ES DSL、物理字段、bean name、查询原文、无权限字段是否真实存在或 credential。
- field/domain/version 等高基数值不得作为 metrics label；必要关联使用 diagnosticId 查审计。

## 16. 性能与容量设计

- Catalog/Registration 使用不可变 Map/Set；candidate 构建和 digest 只在启动/reload 执行。
- route/schema/projection 构建为 O(请求允许 domain + 当前 role fields)，不得扫描所有 Profile/Permission。
- Projection cache 必须有容量上限和最严 TTL；key 不含 raw userId，使用受控 permission evidence digest。
- health 检查有独立短 deadline；超时使组合不可用，不拖延 Planning absolute deadline。
- sort 用户输入最多 2 项；禁止脚本排序、跨域 join 排序和任意表达式。

## 17. 兼容性与扩展性设计

P1_V2 当前未投产，`DomainCatalogView`、散预算字段和分次 execution resolve 不保留兼容层。配置和 Java 契约在 P1_V2/06 原子切换，旧配置字段必须被删除而非 deprecated。

未来 Multi-Agent 可以在 future Multi-Agent L1 完成后复用相同 Catalog/Registration/Projection 接口，并在其自身设计中增加 execution owner/locality/lease；当前 Registration/Binding 不预留未使用字段，也不实现远程发现。稳定的 role/domain key、typed port 和中立 scope 输入足以避免当前单 Agent 设计锁死。

## 18. 日志、监控与告警

| 类型 | 名称/维度 | 要求 |
|---|---|---|
| metric | metadata candidate build/publish/reject | label 仅 result/reason |
| metric | registration conflict/type/coverage failure | label 仅 role/reason；domain 写审计不作 label |
| metric | availability/resolve failure | label 仅 role/status/reason |
| metric | projection cache hit/miss/evict | 低基数 outcome |
| metric | sort validation/downstream rejection | reason/role，不含 field value |
| alert | version reused with different digest | 立即告警并拒绝发布 |
| alert | Catalog/Registration coverage gap | 启动阻断或 reload 拒绝 |
| alert | 连续 health unknown、resolve currentness failure | 按受控阈值告警 |

## 19. 实现落点清单

| 序号 | 路径 | 类/动作 | 变更 |
|---:|---|---|---|
| 1 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/AdapterRole.java` | 保持 Java 权威 role 值类型 | 修改校验/测试，不增加 Domain 值 |
| 2 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/QueryableAdapter.java` | `query(ValidatedQuery,CapabilityOperationContext)` | 修改 |
| 3 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/AggregatableAdapter.java` | 增加 operation context | 修改 |
| 4 | `agent-adapter-api/src/main/java/com/dylan/agent/adapter/api/DocumentRetrievableAdapter.java` | 增加 operation context | 修改 |
| 5 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/DomainMetadataProperties.java` | 删除 role 散预算；严格绑定唯一输入 | 修改 |
| 6 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/CanonicalRoleCapability.java` | 删除 `maxPageSize/maxResultRows` | 修改 |
| 7 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/DomainMetadataPropertiesValidator.java` | 拆为/收敛到 candidate builder；闭合校验与 canonical digest | 修改 |
| 8 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/DomainMetadataStore.java` | bundle 级 CAS publish/assertCurrent | 修改 |
| 9 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/port/DomainMetadataPort.java` | 冻结第 10.7 节接口 | 修改 |
| 10 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/DomainMetadataPortImpl.java` | 请求级投影与原子 execution resolution | 修改 |
| 11 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/DomainSecurityBoundary.java` | 一次 delegate `resolveExecution` | 修改 |
| 12 | `agent-service/src/main/java/com/dylan/agent/kernel/port/model/ExecutionValidationProjection.java` | 删除散预算、保留安全 field rules | 修改 |
| 13 | `agent-service/src/main/java/com/dylan/agent/kernel/port/model/AdapterExecutionBinding.java` | 增加证据/identity 和受控 typed access | 修改 |
| 14 | `agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/DomainCatalogView.java` | 删除直读事实源 | 删除 |
| 15 | `agent-service/src/main/java/com/dylan/agent/capability/query/QueryPlanValidator.java` | 只读 projection/typed limits；排序复检 | 修改 |
| 16 | `agent-service/src/main/java/com/dylan/agent/capability/aggregate/AggregatePlanValidator.java` | 只读 projection/typed limits | 修改 |
| 17 | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentPlanValidator.java` | 只读 projection/typed limits | 修改 |
| 18 | `agent-service/src/main/java/com/dylan/agent/planning/filter/FilterNormalizer.java` | 入参改为 `ExecutionFieldRule`/projection | 修改 |
| 19 | `agent-service/src/main/java/com/dylan/agent/planning/filter/FieldConstraintValidator.java` | 不再依赖 DomainView | 修改 |
| 20 | `agent-service/src/main/java/com/dylan/agent/metadata/config/DefaultAgentMetadataBootstrap.java` | 删除 Domain Properties 专用遍历/散预算 | 修改 |
| 21 | `config-service/src/main/resources/config/agent-service.yml` | 删除 role `max-page-size/max-result-rows` | 修改 |
| 22 | `agent-runtime/app/prompts/query_system.md` | 删除真实 Domain 字段事实示例 | 修改 |
| 23 | `agent-runtime/app/prompts/aggregate_system.md` | 删除真实 Domain 字段事实示例 | 修改 |
| 24 | `agent-runtime/app/prompts/document_system.md` | 删除真实 Domain 字段事实示例 | 修改 |
| 25 | `agent-adapter-employee/src/main/java/com/dylan/agent/adapter/employee/EmployeePlanMapper.java` | 保留安全映射/稳定排序并接受 operation context | 修改 |
| 26 | `agent-adapter-transaction/src/main/java/com/dylan/agent/adapter/transaction/TransactionPlanMapper.java` | 保留 typed sort 映射 | 修改/验证 |
| 27 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/service/TransactionService.java` | 保留二次白名单与固定 ORDER BY | 验证 |

## 20. 测试设计与验收命令

### 20.1 测试矩阵

| 类别 | 必测场景 | 关键断言 |
|---|---|---|
| Catalog | duplicate domain/field/alias、unknown role field、type/operator/function 不兼容、同 version 不同 digest | candidate 拒绝；digest 稳定 |
| Registration | duplicate key/id、bean 缺失、port type mismatch、Catalog/Registration coverage gap | 启动失败/reload 保留旧 bundle |
| Availability | healthy/unhealthy/unknown、scope 收紧、Policy/Permission 不在 metadata 内重复读取 | 只投影完整交集；unknown fail closed |
| Projection | Route 无 field；Plan/Execution 字段逐级不扩大；无散预算 | 未授权/未映射项不出现 |
| Execution resolution | metadata/health 在 resolve 前变化、重复 Registration、wrong port、OPTIONAL/NONE/REQUIRED | 一次原子返回或整体失败；Handler 不二次路由 |
| Query sort | null/empty/replace/inherit、大小写、重复/超量/未知/无权限字段、tie-breaker | canonical 用户排序安全；分页稳定 |
| Downstream | employee/transaction mapping、恶意 field/direction、`${orderByClause}` 来源 | 原文不能进入 SQL/ES；二次校验有效 |
| Prompt | 三份 Prompt 不含生产 domain/field 清单；schema 驱动 fixture | 新 Domain 不修改 Prompt |
| Resource limits | Domain config/projection 无散 budget；Validator 只读 typed limits | 同一 ContractRef/digest 贯穿 |
| New Domain | test fixture 新增 `sample_domain` + adapter + registration + policy | Route/Plan/resolve 成功；生产 Planning/Core/Lifecycle/既有 Handler/Validator 无 domain 分支 |

### 20.2 架构门禁

- `DomainMetadataArchitectureTest`：禁止 capability/validator 包依赖 `metadata.domain.internal`；只允许依赖 port/model。
- `AdapterMetadataSelfReportArchitectureTest`：禁止 `AgentAdapterPort` 子接口声明 fields/operators/functions/capabilities。
- `DomainResourceLimitArchitectureTest`：禁止 Domain properties/projection 声明 `maxPageSize/maxResultRows/maxResultBytes`。
- `NewDomainExtensionArchitectureTest`：扫描 Planning/Core/Lifecycle/通用 Handler/Validator 不包含 `employee/transaction/sample_domain` 字符串、Adapter 实现依赖或 domain switch。
- `RuntimePromptDomainFactTest`：Prompt 只引用 `domainSchema`，不包含生产 Catalog 的 domain/field 标识集合。
- `AdapterRegistrationCoverageTest`：Catalog role capability 与 Registration 双向一一覆盖。

### 20.3 最小实施验证命令

```powershell
mvn -pl agent-adapter-api,agent-api,agent-service,agent-adapter-employee,agent-adapter-transaction,transaction-api,mq-procedure-service -am test
python -m pytest agent-runtime/tests/test_contracts.py agent-runtime/tests/test_planning.py
rg -n "DomainCatalogView|max-page-size|max-result-rows" agent-service config-service/src/main/resources/config/agent-service.yml
rg -n "amount|transType|sourceType|contactAddress" agent-runtime/app/prompts
```

前两条必须通过；后两条只能命中保留映射/测试解释清单允许的位置，不能命中被删除的事实源。P1_V2/06 还需执行全量 contract generation/diff gate。

## 21. 风险与待确认事项

| 风险 | 触发场景 | 处理 |
|---|---|---|
| 公共契约兼容 | 实施需要改变 `transaction-api.sorts` 既有字段/语义 | 先清点调用者并取得公共契约变更授权；当前设计保持可选兼容 |
| 下游白名单漂移 | Catalog 声明字段但 adapter/downstream 不支持 | build/startup coverage + 双边 contract test；运行时仍二次校验 |
| 权限泄漏 | Validator 直读 Catalog 区分 unknown/forbidden | 删除 DomainCatalogView；只消费当前 Execution Projection |
| 预算多源 | Domain metadata、AgentProperties、ExecutionScope 各有 page/result 上限 | 删除散字段，统一 P1_V2/05 typed limits |
| TOCTOU | projection 与 binding 分次读取时 reload/health 变化 | `resolveExecution` 使用同一 static bundle view 和同次 health currentness check 原子产生两者 |
| SQL 注入 | sort 原文进入 `${orderByClause}` | 仅 `FIELD_MAP` 固定列 + ASC/DESC 生成内部字符串 |
| 分页不稳定 | 用户排序值相同或无排序 | adapter/downstream 固定追加唯一 tie-breaker |
| 半链发布 | 先删旧 View/预算但新 Projection/limits 未就绪 | 仅由 P1_V2/06 原子迁移发布 |

## 22. 评审记录

| 轮次 | 日期 | 结论 | 发现与处理 |
|---:|---|---|---|
| 1 | 2026-07-13 | 修订后复审 | 发现 Registration 动态化、Catalog/Projection 混入预算、Validator 直读 Catalog、execution 分次解析、清理与扩展门禁不足；已修订 |
| 2 | 2026-07-13 | 修订后复审 | 发现 Registration 重复配置 port type/catalog version，且动态 health 被混入 static bundle；已删重复字段并拆分请求级 availability evidence |
| 3 | 2026-07-13 | 通过 | 对照 L0/L1、P1_V2/01～03/05/06、Java 权威类型与当前实现偏差终审；S0/S1 均为 0 |

## 23. 实施对齐检查

- [x] Canonical Domain Field Catalog 唯一输入、不可变模型和 digest 已冻结。
- [x] Adapter Role/Registration 唯一绑定且不含动态 enabled/field/permission。
- [x] Route/Plan/Validation/Binding 投影层次和一次 execution resolution 已冻结。
- [x] 配置、Prompt、Adapter 自报、Java 事实副本清理清单已明确。
- [x] build/startup/reload coverage gate 和 currentness fail-closed 已明确。
- [x] 代表性新 Domain 不修改 Planning/Core/Lifecycle/既有 Handler/Validator 的门禁已明确。
- [x] QUERY 排序从 Runtime 到下游的安全闭环已明确。
- [ ] P1_V2 全套 L2 串行评审通过。
- [ ] P1_V2/06 原子实施授权和公共契约兼容清单确认。

## 24. 任务完成摘要

本文已完整承接 P1/D04 与 QUERY 白名单排序历史设计，不再要求实施者回查旧文档。当前形成唯一 Catalog/Registration、请求级 availability、分层安全投影、一次 Adapter Binding、排序防注入、双来源删除和新 Domain 无 Core 改动基线。当前状态：**In Review**。
