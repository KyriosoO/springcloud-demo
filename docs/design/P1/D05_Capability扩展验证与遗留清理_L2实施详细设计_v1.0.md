# D05 Capability 扩展验证与遗留清理 — L2 实施详细设计 v1.0

> 文档状态：已实施（代码状态已核实；目标环境回归待执行；2026-07-05 已按授权补充 QUERY 白名单排序共享契约影响）
> 编写日期：2026-07-02
> 前置交付：D03 Capability v2 原子切换已完成代码评审；本地 API/UI E2E 已验证；发布前环境回归仍按 D03 第 10 节执行
> 上位依据：`Agent目标架构总览_v1.0.md`、`Agent契约与规划架构设计_v1.0.md`、`Agent能力执行内核架构设计_v1.0.md`、`Agent元数据与上下文安全架构设计_v1.0.md`
> 关联 L2：`D01_Agent契约生成与治理_L2实施详细设计_v1.0.md`、`D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md`、`D02_01_Capability注册与可信执行内核_L2_v1.0.md`、`D02_02_Invocation生命周期与持久化_L2_v1.0.md`、`D02_03_元数据授权与Context安全_L2_v1.0.md`、`D03_Capability v2跨服务原子切换_L2实施详细设计_v1.0.md`、`D03_01_UserPermissionAuthority权限权威源契约说明_L2_v1.0.md`、`D03_02_Capability v2实施落地清单_L2_v1.0.md`、`D04_Agent Adapter与Domain Metadata收敛_L2实施详细设计_v1.0.md`
> 后置交付：D06 Multi-Agent 详细设计；D06 必须等待 D05 验证扩展不变量通过

---

## 0. Change List

| 日期 | 内容 | 原因 |
|---|---|---|
| 2026-07-02 | 新增 D05 L2 实施详细设计，定义代表性 capability 扩展验证、遗留清理、文件级落点、门禁和评审矩阵 | D03 已交付 capability-first 主链路；进入 D06 前必须用真实新增 capability 证明扩展不变量 |
| 2026-07-03 | 根据品审修订 D04 metadata、Profile/Policy、Runtime Prompt 和 Preview 执行边界 | 原稿将 capability 可用性误落到 D04 metadata，且遗漏默认 Profile/Policy 可用性落点；需保证 D05 可直接指导编码且不越过上位扩展不变量 |
| 2026-07-03 | 根据用户确认放宽 domain 策略：employee 作为首版代表性验证样例，`query.preview` 支持所有已授权 `QUERYABLE` domain | 当前 D04/Catalog 模型按 AdapterRole 投影可用 domain，不新增 capabilityId 级 domain allowlist，避免修改上位或关联文档 |
| 2026-07-05 | 同步 D05 当前实现状态 | `query.preview` Java API payload、Capability registration、validator、handler、ResultSecurity projector、Profile/Policy/Catalog 接入与 Runtime prompt/plan 回归用例均已落地；目标环境回归仍按退出条件执行 |
| 2026-07-05 | 授权同步 QUERY 白名单排序共享契约影响 | `query.preview` 复用 `QueryAgentPlan`、`AgentQuerySpec`、`ValidatedQuery`、`AgentQueryParameters`，因此显式 `query.sorts` 必须参与白名单校验、Adapter 入参、响应回显和 ResultSecurity 过滤；仍不写 QUERY Context，不新增 prompt 固定分支 |

---

## 1. 文档目的

D05 的目标不是继续重构 D03 主链路，而是在 D03 已完成的 capability-first 架构上新增一个真实代表性 capability，证明以下扩展不变量成立：

1. 新增同 `planKind` capability 不修改 `AgentOrchestrator`、`PlanningService`、`ExecutionLifecycleService`、`ExecutionCore`。
2. 新增 capability 只通过 Java contract、CapabilityRegistration、Validator、Handler、Profile/Policy capability 组合、D04 metadata 复用、权限投影和测试接入。
3. Runtime 仍只消费 Java 生成的 active Route/Plan contract，不出现旧 `Intent`、旧 `/plans/generate`、v1/v2 双协议或兼容 facade。
4. 权限、Domain metadata、Context、ResultSecurity、Lifecycle finalization 继续沿用 D02/D03/D04 边界。
5. D05 完成后可为 D06 提供“新增 capability 零核心框架修改”的证据。

---

## 2. 输入基线

D03 向 D05 交付以下基线：

1. 单 Agent capability-first CHAT 主链路。
2. 生产 active Route/Plan Runtime contract。
3. 可扩展 `CapabilityRegistration`、`CapabilityPlanValidator`、`CapabilityHandler` 接入点。
4. D04 `DomainMetadataPort`、Canonical Domain Metadata、AdapterRegistration 生产接入点。
5. Context read/write、ResultSecurity、Lifecycle finalization 闭环。
6. 旧 intent、旧 Runtime 单 operation、旧 Router/Registry、旧 query context 生产路径删除后的静态验证结果。

D05 不重新评审 D03 架构，只验证 D03 的扩展承诺是否真实成立。

---

## 3. 范围

### 3.1 D05 负责

1. 新增代表性 capability：`query.preview`。
2. 补齐该 capability 的 Java contract、Registration、Validator、Handler、Result payload、Profile/Policy capability 组合、权限投影、Domain metadata 复用边界、Runtime prompt 回归约束和测试。
3. 验证 `query.preview` 与既有 `query.search` 共享 `QUERY` planKind 时不需要修改核心主流程。
4. 清理 D03 之后已无必要的遗留命名、过渡测试命名、无意义兼容注释和不再使用的 fixture/prompt 术语。
5. 建立 D06 前置证据：新增真实 capability 时核心框架 diff 为零。

### 3.2 D05 不负责

1. 不新增 Multi-Agent、Run、Task、Attempt、ResultRef、Coordinator、TaskRunner、outbox。
2. 不新增写操作 capability，不引入审批、事务写入或外部工作流。
3. 不修改 D03 主链路、Lifecycle 状态机、ExecutionCore 执行流程或 Runtime Route/Plan 主 contract。
4. 不新增旧 intent 兼容、不恢复旧 `/runtime/v1/plans/generate`、不创建 v1/v2 endpoint、converter、facade 或 feature flag。
5. 不新增第二权限源、第二 Domain metadata 源、第二 ResultSecurity 路径。
6. 不让 Runtime、Handler、Adapter 执行授权决策。
7. 不把 D04 metadata 复制到 Prompt、Profile、Policy 或本地 YAML 旁路。

---

## 4. 代表性 capability 选择

D05 选择 `query.preview` 作为代表性 capability。

| 项 | 设计 |
|---|---|
| capabilityId | `query.preview` |
| planKind | `QUERY` |
| domainMode | `REQUIRED` |
| 首版重点验证 domain | `employee`；生产可用 domain 为 D04 availability 与 Profile/Policy/UserPermission 交集下的全部 `QUERYABLE` domain |
| input contract | `QueryAgentPlan`，复用 D01 active Runtime plan union |
| output contract | `QueryPreviewResultPayload`，新增 Java API result payload |
| context read | 可读 `QUERY` context，用于继承上一次查询过滤条件 |
| context write | 不写 Context；只返回预览结果，避免 D05 扩大到新 Context 生命周期 |
| validator | `QueryPreviewPlanValidator` |
| handler | `QueryPreviewCapabilityHandler` |
| adapter | 复用 `QueryableAdapter`，但通过独立 handler 限制返回字段和行数 |
| 权限 | `UserPermission.allowedCapabilityIds` 必须包含 `query.preview`；字段、operator、domain 仍受 D02_03/D04 交集限制 |
| Profile/Policy | 默认 Profile 与 active Policy 必须包含 `query.preview`；Profile/Policy 只能收紧，不能扩大 `UserPermission` |
| metadata | 复用 D04 各 domain 的 `QUERYABLE` role capability、字段和 operator 事实；不得在 `agent.domain-metadata` 下新增 capabilityId 维度 |
| Runtime | Route 可在 `query.search` 与 `query.preview` 间选择；Plan 仍返回 `QueryAgentPlan` |

选择理由：

1. 与 `query.search` 共享 `QUERY` planKind，能验证“同 planKind 多 capability 不改主流程”。
2. 复用既有 read-only adapter，不扩大到写操作、事务或外部工作流。
3. 输出 payload 与普通查询不同，能验证 ResultSecurity 和 API response sealed union 的扩展能力。
4. 首版以 `employee` 作为代表性 E2E/API/UI smoke 样例；同时允许 `transaction` 等已由 D04 接入并经授权的 `QUERYABLE` domain 进入 `query.preview`，以证明新增 capability 不需要 capability-domain 专用算法。

---

## 5. 架构约束

### 5.1 核心不变量

以下文件在 D05 编码中原则上必须保持 byte-for-byte 不变；若确需修改，必须暂停并重新评审 D05 文档：

| 文件 | 禁止原因 |
|---|---|
| `agent-service/src/main/java/com/dylan/agent/application/AgentOrchestrator.java` | Entry Adapter 不应感知具体 capability |
| `agent-service/src/main/java/com/dylan/agent/planning/PlanningService.java` | Planning 主流程不得按 capability 分支 |
| `agent-service/src/main/java/com/dylan/agent/lifecycle/ExecutionLifecycleService.java` | Lifecycle 不应感知 capability 业务语义 |
| `agent-service/src/main/java/com/dylan/agent/kernel/core/ExecutionCore.java` | Core 只执行 Registration/Validator/Handler 通用流程 |
| `agent-service/src/main/java/com/dylan/agent/kernel/registration/CapabilityRegistry.java` | Registry 只按 capabilityId 通用索引 |
| `agent-service/src/main/java/com/dylan/agent/client/AgentRuntimeClient.java` | Runtime Client 只保留 Route/Plan typed operation |
| `agent-runtime/app/api/runtime_api.py` | Runtime API 只保留 active Route/Plan endpoint |
| `agent-runtime/app/contracts/generated_models.py` | 只能由 Java OpenAPI 生成，不手工补丁 |

### 5.2 允许扩展点

| 扩展点 | D05 用法 |
|---|---|
| Java API result payload | 新增 `QueryPreviewResultPayload`，纳入 sealed result union |
| CapabilityRegistration | 新增 `query.preview` registration |
| CapabilityDefinition | 新增 capability metadata、input/output contract、context declaration |
| Validator | 新增 `QueryPreviewPlanValidator` |
| Handler | 新增 `QueryPreviewCapabilityHandler` |
| ResultSecurityProjector | 新增 `QueryPreviewResultSecurityProjector` 或扩展 registry 注册 |
| Profile/Policy capability 组合 | 默认 Profile 和 active Policy 增加 `query.preview`，使其进入 Available Capability 交集 |
| D04 Domain metadata | 复用现有 `QUERYABLE` role capability 覆盖的全部已授权 domain；不得把 capabilityId 写入 D04 Catalog |
| auth-service 权限投影 | 增加 `query.preview` capability 授权输出 |
| Runtime prompt | 不因 `query.preview` 修改共享 Prompt；只允许清理旧术语或保持通用 descriptor-driven 规则，且不得出现 `query.preview` 固定分支 |

---

## 6. 文件级落地清单

### 6.1 `agent-api`

| 路径 | 动作 | 要求 |
|---|---|---|
| `agent-api/src/main/java/com/dylan/agent/api/response/QueryPreviewResultPayload.java` | NEW | 新增 `AgentResultPayload` sealed subtype，表达预览摘要、字段、样例行和 totalEstimate |
| `agent-api/src/main/java/com/dylan/agent/api/response/AgentResultPayload.java` | MODIFY | 只增加 sealed permits，不改变既有 discriminator 语义 |
| `agent-api/src/main/java/com/dylan/agent/api/enums/AgentResultKind.java` | MODIFY | 增加 `QUERY_PREVIEW`，保持 Java 为唯一 API 契约源 |
| `agent-api/src/test/java/com/dylan/agent/api/AgentResultPayloadContractTest.java` | MODIFY | 覆盖 `QUERY_PREVIEW` discriminator 和 JSON 形状 |

禁止新增旧 `AgentIntent`、旧 `PlanGenerateRequest/Response` 或独立 Runtime DTO。

### 6.2 `agent-service` capability 扩展

| 路径 | 动作 | 要求 |
|---|---|---|
| `agent-service/src/main/java/com/dylan/agent/capability/querypreview/ValidatedQueryPreviewPlan.java` | NEW | 实现 `ValidatedPlan`，只保存已校验字段、过滤条件、limit 和 projection |
| `agent-service/src/main/java/com/dylan/agent/capability/querypreview/QueryPreviewPlanValidator.java` | NEW | 只接收 `QueryAgentPlan` raw plan 和 `ExecutionValidationContext`；使用其中的 execution projection 与 scope 上限 |
| `agent-service/src/main/java/com/dylan/agent/capability/querypreview/QueryPreviewCapabilityHandler.java` | NEW | 只接收 `ValidatedQueryPreviewPlan`，调用 `QueryableAdapter`，不做授权决策 |
| `agent-service/src/main/java/com/dylan/agent/capability/querypreview/QueryPreviewCapabilityConfiguration.java` | NEW | 注册 `CapabilityRegistration`、Validator、Handler、ResultSecurityProjector |
| `agent-service/src/main/java/com/dylan/agent/metadata/result/QueryPreviewResultSecurityProjector.java` | NEW | 负责过滤、脱敏、safeMessage、safeSummary、canonical payload |
| `agent-service/src/main/java/com/dylan/agent/metadata/config/DefaultAgentMetadataBootstrap.java` | MODIFY | 默认 Profile 与 active Policy capability 集合增加 `query.preview`；不得把该能力写入 D04 Catalog 或 Runtime Prompt |
| `agent-service/src/main/resources/application.yml` | KEEP | 不为 `query.preview` 新增 D04 `agent.domain-metadata` capabilityId 配置；只复用现有各 domain 的 `QUERYABLE` 字段/operator/registration |

### 6.3 `auth-service`

| 路径 | 动作 | 要求 |
|---|---|---|
| `auth-service/src/main/java/com/dylan/authcenter/agent/permission/AgentPermissionProjectionService.java` | MODIFY | 在 admin 或指定角色投影中增加 `query.preview`；viewer 是否可用由 D05 明确测试 |
| `auth-service/src/test/java/com/dylan/authcenter/agent/permission/AgentPermissionProjectionServiceTest.java` | MODIFY | 覆盖 capability 授权、narrow 后不扩大权限 |

不得改变 D03_01 请求/响应 DTO 字段、内部 endpoint、服务 token 鉴权方式和错误码语义。

### 6.4 `agent-runtime`

| 路径 | 动作 | 要求 |
|---|---|---|
| `agent-runtime/app/prompts/route_system.md` | KEEP/MODIFY | 不因 `query.preview` 增加能力专用说明；仅允许清理旧 intent/v1 术语或保持通用 descriptor-driven 规则 |
| `agent-runtime/app/prompts/query_system.md` | KEEP/MODIFY | 不出现 `query.preview` 字面量；同 `QUERY` planKind capability 仍由请求中的 descriptor/schema 驱动并输出 `QueryAgentPlan` |
| `agent-runtime/tests/test_prompt_contract.py` | MODIFY | 覆盖 prompt 禁止旧术语和固定 capability 旁路 |

禁止修改 `runtime_api.py` 增加新 endpoint；禁止修改 `generated_models.py` 手写新模型。

### 6.5 文档与清理

| 路径 | 动作 | 要求 |
|---|---|---|
| `docs/design/P1/D05_Capability扩展验证与遗留清理_L2实施详细设计_v1.0.md` | KEEP/MODIFY | D05 唯一实施基线 |
| D03 文档 | KEEP | 除非发现 D03 状态错误，否则不修改；需要修改时必须先暂停并取得授权 |
| D04 文档 | KEEP | 除非 D05 需要新增 Domain metadata 设计规则，否则不修改；需要修改时必须先暂停并取得授权 |
| 旧测试命名或注释 | MODIFY/DELETE | 只清理误导性的 legacy/compat 命名；不得删除证明旧路径不存在的测试 |

### 6.6 Java 类、包、方法级清单

本节是 D05 编码的强制范围清单。未列入本节的 Java 生产类默认不修改；若编码时发现必须修改未列入类，先回到本文评审。

#### 6.6.1 `agent-api` 生产代码

| 包路径 | 类 | 动作 | 字段 / 方法 |
|---|---|---|---|
| `com.dylan.agent.api.response` | `QueryPreviewResultPayload` | NEW | 字段：`AgentQueryParameters queryParameters`、`QueryPreviewResult previewResult`；方法：无参构造器、全参构造器、`AgentResultKind getResultKind()`、`getQueryParameters()`、`setQueryParameters(AgentQueryParameters)`、`getPreviewResult()`、`setPreviewResult(QueryPreviewResult)` |
| `com.dylan.agent.api.response` | `QueryPreviewResult` | NEW | 字段：`List<String> columns`、`List<Map<String, Object>> sampleRows`、`Long totalEstimate`、`Boolean totalExact`、`Integer previewSize`；方法：无参构造器、全参构造器、对应 getter/setter |
| `com.dylan.agent.api.response` | `AgentResultPayload` | MODIFY | sealed `permits` 增加 `QueryPreviewResultPayload`；不新增并列 response 字段 |
| `com.dylan.agent.api.enums` | `AgentResultKind` | MODIFY | enum 增加 `QUERY_PREVIEW`；Swagger description 增加“查询预览结果 payload” |
| `com.dylan.agent.api.contract.common` | `AgentExecutionContracts` | MODIFY | 增加 `public static final ContractRef QUERY_PREVIEW_RESULT = new ContractRef("QueryPreviewResultPayload", "1.1.0")`；排序增量后该版本需与 `AgentQueryParameters.sorts` 回显契约一致 |

禁止在 `agent-api` 新增或恢复以下类：`AgentIntent`、`PlanGenerateRequest`、`PlanGenerateResponse`、旧 `AgentPlan`、`AgentCapabilityDescriptor`。

#### 6.6.2 `agent-service` 生产代码

| 包路径 | 类 | 动作 | 字段 / 方法 |
|---|---|---|---|
| `com.dylan.agent.capability.querypreview` | `ValidatedQueryPreviewPlan` | NEW | 字段：`String capabilityId`、`String domain`、`ValidatedQuery query`、`List<String> previewFields`、`int previewSize`；构造器必须断言 `query.getSelectFields()` 等于 `previewFields`、`query.getSize()` 等于 `previewSize`、`query.getPage()` 为 `1`；方法：`capabilityId()`、`domain()`、`query()`、`previewFields()`、`previewSize()` |
| `com.dylan.agent.capability.querypreview` | `QueryPreviewPlanValidator` | NEW | 实现 `CapabilityPlanValidator<QueryAgentPlan, ValidatedQueryPreviewPlan>`；常量：`KERNEL_CAPABILITY_ID = "query.preview"`；方法：`ValidatedQueryPreviewPlan validate(QueryAgentPlan rawPlan, ExecutionValidationContext context)`、`private List<ValidatedFilter> toValidatedFilters(List<AgentFilter>)`、`private List<ValidatedSort> toValidatedSorts(List<AgentSortSpec>, ExecutionValidationContext)`、`private List<String> normalizePreviewFields(List<String>, ExecutionValidationContext)`、`private int previewSize(AgentQuerySpec, ExecutionValidationContext)`、`private ValidatedQuery toPreviewQuery(List<ValidatedFilter>, List<String>, List<ValidatedSort>, int)`、`private static ExecutionFieldRule requireFieldRule(String, ExecutionValidationContext)` |
| `com.dylan.agent.capability.querypreview` | `QueryPreviewCapabilityHandler` | NEW | 实现 `CapabilityHandler<ValidatedQueryPreviewPlan, QueryPreviewResultPayload>`；方法：`HandlerResult<QueryPreviewResultPayload> execute(ValidatedQueryPreviewPlan plan, ExecutionContext context)`、`private static QueryPreviewResult toPreviewResult(ValidatedQueryPreviewPlan, AdapterQueryResult)`、`private static AgentQueryParameters toQueryParameters(ValidatedQueryPreviewPlan plan)`、`private static List<AgentSortSpec> toSortParameters(List<ValidatedSort> sorts)`、`private static QueryPreviewResultPayload toPayload(ValidatedQueryPreviewPlan, QueryPreviewResult)` |
| `com.dylan.agent.capability.querypreview` | `QueryPreviewCapabilityConfiguration` | NEW | Spring configuration；方法：`CapabilityRegistration<QueryAgentPlan, ValidatedQueryPreviewPlan, QueryPreviewResultPayload> queryPreviewRegistration(QueryPreviewPlanValidator validator, QueryPreviewCapabilityHandler handler)` |
| `com.dylan.agent.metadata.result` | `QueryPreviewResultSecurityProjector` | NEW | 实现 `ResultSecurityProjector<QueryPreviewResultPayload>`；方法：`ContractRef supports()`、`Class<QueryPreviewResultPayload> payloadType()`、`FilteredResult<QueryPreviewResultPayload> filter(QueryPreviewResultPayload candidate, ExecutionScope scope)`；必须过滤 `queryParameters.sorts` 中当前 `ExecutionScope` 不可见的字段 |
| `com.dylan.agent.metadata.result` | `ResultSecurityProjectorRegistry` | KEEP | 不新增 capability/domain 分支；只通过 Spring bean 集合接收 `QueryPreviewResultSecurityProjector` |
| `com.dylan.agent.metadata.config` | `DefaultAgentMetadataBootstrap` | MODIFY | `DEFAULT_CAPABILITY_IDS` 增加 `query.preview`，使默认 Profile 与 active Policy 均包含该 capability；bundle digest 必须随 capability 集合变化而稳定变化 |
| `com.dylan.agent.kernel.registration` | `CapabilityRegistry` | KEEP | 不修改；由 `QueryPreviewCapabilityConfiguration` 新增 registration 即可被索引 |
| `com.dylan.agent.kernel.core` | `ExecutionCore` | KEEP | 不修改；仍按 `ResolvedRegistration` 调用 Validator/Handler |

`QueryPreviewCapabilityConfiguration` 必须构造完整 `CapabilityDefinition`：`capabilityId=query.preview`、`planKind=QUERY`、`domainMode=REQUIRED`、`adapterRole=QUERYABLE`、`riskLevel=READ_ONLY`、`executionMode=IMMEDIATE`、`inputContract=AgentExecutionContracts.QUERY_PLAN`、`outputContract=AgentExecutionContracts.QUERY_PREVIEW_RESULT`、`contextAccess` 只声明读取 `RuntimeContextType.QUERY` + `AgentExecutionContracts.QUERY_CONTEXT` + `QueryCapabilityContextPayload.class`，`ContextWriteDeclaration` 为空。QUERY Context `sorts` 可作为只读字段随声明投影，但首版 preview 不写 Context，也不承诺 MERGE 继承上一轮排序；显式当前 plan `query.sorts` 才参与预览执行。

`agent-service/src/main/resources/application.yml` 不为 `query.preview` 新增 D04 capabilityId 配置。D04 `agent.domain-metadata` 的 `role-capabilities.QUERYABLE` 已表达各 domain 可查询字段/operator/`sort-fields` 和 `max-page-size`；D05 只能复用该事实。若编码时发现现有 D04 字段/operator/`sort-fields` 无法支撑预览需求，应暂停并按 D04 文档问题处理，不得在 D05 中扩展关联文档或新增第二 metadata 源。

`QueryPreviewPlanValidator` 的分页语义必须固定：preview 查询只允许 `page` 为空或 `1`，对 Adapter 发起的 `ValidatedQuery` 固定 `page=1`；`previewSize` 取 raw plan size、`agent.query.default-size`、`ExecutionValidationContext.domainProjection().maxPageSize()`、`ExecutionValidationContext.executionScope().maxResultRows()` 中的最小正数，超过任一上限必须 fail closed。排序语义必须与 `query.search` 共用字段白名单和方向校验：显式 `query.sorts` 可传入 `ValidatedQuery.sorts`；`sorts == null` 或 `sorts == []` 均表示使用业务域默认排序，不继承上一轮 Context 排序。

#### 6.6.3 `auth-service` 生产代码

| 包路径 | 类 | 动作 | 字段 / 方法 |
|---|---|---|---|
| `com.dylan.authcenter.agent.permission` | `AgentPermissionProjectionService` | MODIFY | 常量或集合中增加 `query.preview`；方法 `adminProjection()` 必须返回包含 `query.preview` 的 `allowedCapabilityIds`；若 viewer 支持预览，则 `viewerProjection()` 也必须显式测试；`Projection narrow(Set<String>, Set<String>)` 不得因请求方声明扩大 capability |
| `com.dylan.authcenter.agent.permission.api` | `AgentPermissionResolveRequest` | KEEP | 不新增字段，不改变 D03_01 请求契约 |
| `com.dylan.authcenter.agent.permission.api` | `AgentPermissionResolveResponse` | KEEP | 不新增字段，不改变 D03_01 响应契约 |
| `com.dylan.authcenter.agent.permission` | `AgentPermissionInternalController` | KEEP | 不修改 endpoint、服务 token 鉴权、错误码映射 |

#### 6.6.4 Java 测试类

| 包路径 | 类 | 动作 | 覆盖方法 / 场景 |
|---|---|---|---|
| `com.dylan.agent.api` | `AgentResultPayloadContractTest` | MODIFY | 新增 `queryPreviewPayloadSerializesWithDiscriminator()`、`queryPreviewPayloadRejectsUnknownFields()`；覆盖 `QUERY_PREVIEW` discriminator 和 JSON 形状 |
| `com.dylan.agent.api` | `AgentExecutionContractsTest` | MODIFY | 新增 `queryPreviewResultContractIsRegistered()`；覆盖 `QUERY_PREVIEW_RESULT` ContractRef 名称、`1.1.0` 版本和唯一性 |
| `com.dylan.agent.capability.querypreview` | `QueryPreviewPlanValidatorTest` | NEW | `validatesPreviewPlan()`、`acceptsExplicitWhitelistedSorts()`、`rejectsUnsupportedSortField()`、`rejectsCapabilityIdMismatch()`、`rejectsUnauthorizedField()`、`rejectsUnauthorizedOperator()`、`rejectsPreviewSizeAboveExecutionBudget()` |
| `com.dylan.agent.capability.querypreview` | `QueryPreviewCapabilityHandlerTest` | NEW | `executesPreviewAgainstQueryableAdapter()`、`passesSortsToQueryableAdapter()`、`queryParametersEchoSorts()`、`returnsOnlyPreviewFields()`、`doesNotCreateContextWrite()` |
| `com.dylan.agent.capability.querypreview` | `QueryPreviewCapabilityRegistrationTest` | NEW | `registersQueryPreviewWithQueryPlanKind()`、`coexistsWithQuerySearchRegistration()`、`closesRegistrationGenericTypes()` |
| `com.dylan.agent.metadata.result` | `QueryPreviewResultSecurityProjectorTest` | NEW | `supportsQueryPreviewResultContract()`、`filtersUnauthorizedFields()`、`filtersUnauthorizedSortParameters()`、`createsSafeMessageAndSummary()` |
| `com.dylan.agent.metadata.config` | `AgentMetadataProductionBootstrapTest` | MODIFY | 新增 `defaultProfileAndPolicyIncludeQueryPreview()`；覆盖 Profile、Policy 与 capability constraints 同时包含 `query.preview` |
| `com.dylan.agent.metadata` | `CapabilityCatalogTest` | MODIFY | 新增 `queryPreviewBecomesAvailableThroughProfilePolicyPermissionAndQueryableDomain()`、`queryPreviewExposesAllAuthorizedQueryableDomains()`；证明 capability 可用性来自 Profile/Policy/UserPermission/D04 role 交集，且不新增 capability-domain 专用过滤 |
| `com.dylan.agent.metadata` | `AuthorizationPlanningPortTest` | MODIFY | 新增 `planningScopeIncludesQueryPreviewOnlyWhenPermissionAllows()`；覆盖权限未授予时不进入 Available Capability |
| `com.dylan.agent.kernel` | `CapabilityExtensionTest` | MODIFY | 新增 `addingQueryPreviewDoesNotRequireCoreFrameworkChange()` |
| `com.dylan.agent.kernel.core` | `ExecutionCoreTest` | MODIFY | 新增 `executesQueryPreviewThroughRegistrationBridge()` |
| `com.dylan.agent.planning` | `PlanningServiceTest` | MODIFY | 新增 `routesToQueryPreviewAndBuildsExecutablePlan()` |
| `com.dylan.authcenter.agent.permission` | `AgentPermissionProjectionServiceTest` | MODIFY | 新增 `adminProjectionIncludesQueryPreview()`、`requestedCapabilityCannotExpandProjection()` |

### 6.7 Python 文件、函数和脚本清单

本节列出 D05 范围内允许修改的 Python 文件、函数或脚本。未列入的 Python 文件默认不修改。

| 文件 | 动作 | 函数 / 脚本 | 要求 |
|---|---|---|---|
| `agent-runtime/app/prompts/route_system.md` | KEEP/MODIFY | 非 Python 函数；Route prompt 文本 | 不因 `query.preview` 新增能力专用文本；如清理旧术语，只保留通用 descriptor-driven 规则 |
| `agent-runtime/app/prompts/query_system.md` | KEEP/MODIFY | 非 Python 函数；Query prompt 文本 | 可描述通用 QUERY 排序规则并要求只使用 `domainSchema.sortFields`；不得出现 `query.preview` 字面量，同 `QUERY` planKind capability 仍由请求 descriptor/schema 决定 |
| `agent-runtime/tests/test_prompt_contract.py` | MODIFY | `test_no_legacy_terms`、新增 `test_prompt_does_not_pin_query_preview_as_static_route` | 确认 prompt 不出现旧术语，不把 `query.preview` 写成 Runtime 固定分支 |
| `agent-runtime/tests/test_planning.py` | MODIFY | 新增 `test_route_can_return_query_preview_decision`、`test_plan_for_query_preview_still_returns_query_agent_plan` | 覆盖 Runtime 返回 target `RouteDecision(capabilityId="query.preview")` 和 target `ExecutablePlan(QueryAgentPlan)` |
| `agent-runtime/scripts/check_contract_drift.py` | KEEP/RUN | 脚本入口 | 只运行，不修改；用于验证 Java OpenAPI → Python generated model 无 drift |
| `agent-runtime/scripts/generate_contract_models.py` | KEEP/RUN | 脚本入口 | 仅由 drift/codegen 流程调用，不为 D05 手工改生成逻辑 |
| `agent-runtime/app/api/runtime_api.py` | KEEP | `route`、`plan` endpoint 函数 | 不修改；不得新增 endpoint |
| `agent-runtime/app/core/runtime_planning.py` | KEEP | `RuntimeRoutePlanner.route`、`RuntimePlanPlanner.plan`、`_parse_route`、`_parse_plan` | 不修改；不得新增旧输出 fallback 或 capabilityId 字面量分支 |
| `agent-runtime/app/contracts/generated_models.py` | KEEP/GENERATED | generated model 文件 | 只能由 `check_contract_drift.py` 或 codegen 生成，不手写补丁 |

### 6.8 删除清单

D05 没有强制删除的生产 Java 类、生产 Python 文件或脚本。若执行遗留清理，只允许删除以下类型：

| 类型 | 允许删除条件 |
|---|---|
| 旧术语测试 fixture | 已被 D05 新测试覆盖，且不是证明旧路径不存在的 negative test |
| 误导性 legacy/compat 测试命名 | 只改名或删除无效测试，不删除仍有约束价值的测试 |
| 整文件注释代码 | 证明未被编译、未被引用、无审计价值 |
| prompt 旧术语 | 删除后 `test_prompt_contract.py` 仍覆盖禁止旧术语 |

禁止删除 DB 历史迁移、contract provenance、generated hash、已冻结文档历史记录和旧路径 negative tests。

---

## 7. 实施顺序

1. 增加 `QueryPreviewResultPayload` 和 API contract test。
2. 在 `agent-service` 新增 querypreview package 的 ValidatedPlan、Validator、Handler、Configuration。
3. 增加 ResultSecurity projector，确保返回前唯一过滤边界不变。
4. 在 `DefaultAgentMetadataBootstrap` 默认 Profile 与 active Policy 中增加 `query.preview`，并验证 D04 所有已授权 `QUERYABLE` domain 被复用。
5. 在 `auth-service` 权限投影中增加 `query.preview`，并补充 narrow/fail closed 测试。
6. 补充 Planning/Registry/ExecutionCore tests，证明同 `QUERY` planKind 多 capability 可并存，且 Runtime 仍只从请求 catalog/descriptor 选择 capability。
7. 调整 Runtime prompt contract tests；只有存在旧 intent/v1 术语时才清理 Prompt，禁止写入 `query.preview` 固定分支。
8. 执行 D03 静态删除门禁，证明 D05 未恢复旧路径。
9. 执行 D05 核心框架无 diff 审查，确认第 5.1 节文件未被修改。
10. 执行 D05 范围污染门禁，确认本次 diff 未新增 D06 概念或第二 metadata/权限源。
11. 执行 API smoke/UI smoke，确认 `QUERY_PREVIEW` result payload 可正确渲染或安全降级显示。

任何步骤需要修改第 5.1 节核心文件时，立即暂停编码，先回到本文评审。

---

## 8. 测试门禁

### 8.1 Java contract

```powershell
cd D:\codex\serviceCenter
.\mvnw.cmd -pl "..\agent-api" -am "-Dtest=AgentResultPayloadContractTest,AgentExecutionContractsTest" test --batch-mode
```

### 8.2 Capability 扩展专项

```powershell
cd D:\codex\serviceCenter
.\mvnw.cmd -pl "..\common-security,..\agent-api,..\agent-adapter-api,..\agent-adapter-employee,..\agent-adapter-transaction,..\agent-service" -am "-Dtest=QueryPreviewPlanValidatorTest,QueryPreviewCapabilityHandlerTest,QueryPreviewCapabilityRegistrationTest,QueryPreviewResultSecurityProjectorTest,AgentMetadataProductionBootstrapTest,CapabilityCatalogTest,AuthorizationPlanningPortTest,CapabilityExtensionTest,ExecutionCoreTest" "-Dsurefire.failIfNoSpecifiedTests=false" test --batch-mode
```

### 8.3 Planning/Runtime

```powershell
cd D:\codex\serviceCenter
.\mvnw.cmd -pl "..\common-security,..\agent-api,..\agent-adapter-api,..\agent-adapter-employee,..\agent-adapter-transaction,..\agent-service" -am "-Dtest=PlanningServiceTest,RouteOutcomeValidatorTest,PlanOutcomeValidatorTest,AgentRuntimeClientContractTest" "-Dsurefire.failIfNoSpecifiedTests=false" test --batch-mode
```

### 8.4 auth-service 权限投影

```powershell
cd D:\codex\serviceCenter
.\mvnw.cmd -pl "..\auth-service" -am "-Dtest=AgentPermissionProjectionServiceTest,AgentPermissionInternalControllerTest,AgentPermissionServiceTokenSecurityTest" "-Dsurefire.failIfNoSpecifiedTests=false" test --batch-mode
```

### 8.5 Python Runtime

```powershell
cd D:\codex\agent-runtime
.\.venv\Scripts\python.exe scripts\check_contract_drift.py
.\.venv\Scripts\python.exe -m pytest -q
```

### 8.6 静态删除门禁

以下搜索在 D05 完成后必须继续为空：

```powershell
cd D:\codex
rg -n "AgentIntent|ClarifyCapabilityHandler|CapabilityRouter|CapabilityRouteResolver|AgentCapabilityHandlerRegistry|CapabilityDescriptorFactory|query_context_json|/plans/generate|PlanGenerateRequest|PlanGenerateResponse" agent-api/src/main agent-service/src/main/java agent-runtime/app
```

以下搜索只允许命中 `TypedRegistrationInvoker`：

```powershell
rg -n '@SuppressWarnings\(\{\"unchecked\"|@SuppressWarnings\(\"unchecked\"' agent-service/src/main/java
```

以下搜索在 Prompt 文件中必须为空，避免共享 Prompt 绑定 `query.preview` 字面量：

```powershell
rg -n "query\.preview" agent-runtime/app/prompts
```

以下 diff 级搜索用于确认 D05 未引入 D06 概念；只检查本次新增行，已有 D02/D03 中的中性 `RunScope`、`TaskInvocationOrigin` 等不作为 D05 失败依据：

```powershell
git diff -U0 -- agent-api agent-service auth-service agent-runtime | rg -n "^\+.*\b(Run|Task|Attempt|ResultRef|Coordinator|TaskRunner|outbox)\b"
```

预期输出为空。

### 8.7 核心框架无 diff 门禁

```powershell
git diff --name-only -- `
  agent-service/src/main/java/com/dylan/agent/application/AgentOrchestrator.java `
  agent-service/src/main/java/com/dylan/agent/planning/PlanningService.java `
  agent-service/src/main/java/com/dylan/agent/lifecycle/ExecutionLifecycleService.java `
  agent-service/src/main/java/com/dylan/agent/kernel/core/ExecutionCore.java `
  agent-service/src/main/java/com/dylan/agent/kernel/registration/CapabilityRegistry.java `
  agent-service/src/main/java/com/dylan/agent/client/AgentRuntimeClient.java `
  agent-runtime/app/api/runtime_api.py `
  agent-runtime/app/contracts/generated_models.py
```

预期输出为空。

---

## 9. 遗留清理规则

D05 允许清理：

1. D03 之后已误导的 `legacy`、`compat`、`v1` 测试命名。
2. 与旧 intent 主链相关但已无测试价值的 fixture。
3. 无意义的兼容注释、整文件注释代码、过期 TODO。
4. prompt 中不再需要的旧术语。

D05 禁止清理：

1. DB 历史迁移文件和历史列说明。
2. contract provenance、generated model hash、OpenAPI committed artifact。
3. 已冻结文档中的历史审计记录。
4. 证明旧路径不存在的 negative tests。
5. D03 发布前环境回归说明。

---

## 10. 评审矩阵

| 检查项 | 通过标准 | 证据 |
|---|---|---|
| 是否修改核心主流程 | 第 5.1 节核心文件无 diff | 8.7 门禁 |
| 是否新增第二 metadata 源 | 不在 D04 `agent.domain-metadata` 中新增 capabilityId 维度，只复用各 domain 的 `QUERYABLE` role capability | 配置 diff + D04 tests + CapabilityCatalog tests |
| 是否进入 Available Capability | `query.preview` 同时经过 Registration、Profile、Policy、UserPermission、D04 role/domain 交集 | AgentMetadataProductionBootstrapTest + CapabilityCatalogTest + AuthorizationPlanningPortTest |
| 是否绕过权限边界 | `query.preview` 只来自 Profile/Policy/UserPermission 的交集；auth-service 投影不得因 requestedCapabilityIds 扩大 | auth-service + agent-service tests |
| 是否恢复旧协议 | 旧路径静态搜索为空 | 8.6 门禁 |
| 是否引入 D06 概念 | D05 代码 diff 不新增 Run/Task/Attempt/ResultRef/Coordinator/TaskRunner/outbox | 8.6 diff 级静态搜索 |
| 是否绕过 ResultSecurity | Handler 返回候选结果，API/持久化前经过 projector | ResultSecurity tests |
| 是否修改 Runtime 主契约 | 不手写 generated model，不新增 endpoint | drift + git diff |
| 是否固定 Runtime Prompt 分支 | Prompt 文件不得出现 `query.preview` 字面量；Runtime 只能通过请求 descriptor/catalog 选择 | prompt contract + 8.6 Prompt 搜索 |
| 是否证明同 planKind 扩展 | `query.search` 与 `query.preview` 同时注册并通过 Planning/Core tests | capability tests |
| 是否安全处理 QUERY 排序共享契约 | `query.preview` 仅消费显式当前 plan `sorts`，使用 D04 `sort-fields` 白名单校验，响应回显经 ResultSecurity 过滤，且不写 QUERY Context | QueryPreviewPlanValidatorTest + QueryPreviewCapabilityHandlerTest + QueryPreviewResultSecurityProjectorTest |
| 是否保留 fail closed | 手工伪造 capabilityId/domain/field/operator 被 Java 拒绝 | Validator/Core tests |

---

## 11. 退出条件

D05 只有同时满足以下条件才可视为完成。当前代码状态已满足实现落点和专项测试类存在性核实；目标环境回归与 UI/API smoke 仍需作为发布前证据补齐：

1. D05 文档评审通过。
2. `query.preview` 端到端通过：Route、Plan、Java validation、ExecutionCore、Handler、ResultSecurity、API response。
3. `query.search` 与 `query.preview` 共享 `QUERY` planKind，核心主流程文件无 diff。
4. `query.preview` 进入 Available Capability 的证据来自 Registration、Profile、Policy、UserPermission 和 D04 `QUERYABLE` role capability 的交集，且覆盖所有已授权 `QUERYABLE` domain。
5. D03 静态删除门禁继续通过。
6. Runtime contract drift 通过，Python tests 通过。
7. auth-service 权限投影 tests 通过。
8. D05 新增 capability tests、Registration tests、Validator tests、Handler tests、ResultSecurity tests、Profile/Policy/Catalog tests 全部通过。
9. QUERY 排序增量实施后，`query.preview` 显式排序、Adapter 入参、响应回显和 ResultSecurity 过滤测试全部通过，且 Prompt 仍不出现 `query.preview` 固定分支。
9. UI/API smoke 证明新增 result payload 可展示或安全降级。
10. `git diff --check` 通过。
11. `git status --short --branch` 只包含 D05 预期改动，且未 commit/push/PR，除非用户明确授权。

---

## 12. D06 准入结论模板

D05 完成后，必须在实施结果中明确回答：

1. 新增真实 capability 是否做到零核心框架修改。
2. 是否仍只有 Java contract 是跨 Java/Runtime 结构契约源。
3. Runtime 是否仍不维护固定 capability 目录。
4. Authorization、Domain metadata、Context、ResultSecurity 是否仍各自只有一个权威边界。
5. D06 是否可以基于 Planning、Lifecycle、ExecutionCore 和 Invocation Record 继续设计 Multi-Agent。

任一答案为否，不得进入 D06。
