# [L2_00_01] 单体 Agent Core 执行、QueryPlan 接缝与能力注册详细设计

> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L2_00_01 |
| 当前版本 | v1.5 |
| 更新日期 | 2026-08-24 |
| 上位设计 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v1.2 |
| 协作设计 | `L2_00_02` v1.5、`L2_02_00` v1.6 |
| 实施状态 | 公共 QueryPlan 合同、Business planning、组合根唯一分支与旧 Business Resolver 第一阶段清理已完成 non-live 实施及代码复核；系统 E2E/live 尚未完成 |

## 2. 修改历史、设计目标与范围

| 版本 | 日期 | 修改内容 |
|---|---|---|
| v1.1 | 2026-08-21 | 既有 Core/Hybrid/Registry 详细设计基线 |
| v1.2 | 2026-08-24 | 新增 Business QueryPlan→ActionCandidate 唯一接缝并退役 Business Resolver 目标路径 |
| v1.3 | 2026-08-24 | 显式绑定当前 `request_id`；明确共享 Runtime 中 Business 与非 Business 分支隔离、输入拒绝语义及启动一一映射校验 |
| v1.4 | 2026-08-24 | 独立复评 R1 发现并闭合请求取消信号接缝，禁止模型迟到结果进入 decoder/binder/Core |
| v1.5 | 2026-08-24 | 明确清理 Employee/Transaction 专属 Resolver 可执行资产，同时保留非 Business 共享 Hybrid/ID-only 与历史不可变证据 |

本文定义 Business QueryPlan 如何在 LangGraph 中转换为既有 `ActionCandidate`，以及 Registry/Core/组合根如何保证单动作和唯一链路。

范围外/不负责：不修改以下公共契约：

- `CapabilityDescriptor`、`ActionCandidate`、`CapabilityResult` 的既有对外含义；
- `CapabilityExecutionCore.execute(...)` 的职责；
- Spring/Runtime HTTP/OpenAPI；
- Employee/Transaction 参数字段和 Adapter codec。

### 2.1 当前实现基线

共享 `LocalActionResolver`、`HybridActionSelectionNode` 和 ID-only selector 仍可服务显式非 Business 能力；Employee/Transaction 专属 Resolver 类及只验证其旁路的测试不再有合法调用方，应删除。冻结历史 harness 仍可依赖兼容字段做离线复验，但其 definition 不得进入生产 `BusinessSupportFactory`/组合根；历史 evidence/hash 保持不变且不能证明新设计已实现。

## 3. 上位约束、需求与关联责任边界

上位约束来源是 L1_00 v1.2 的唯一编排、单动作和无 Business Resolver 旁路；本 L2 负责图/Core 接缝，不负责域字段、模型 transport 或 HTTP codec。`CON-CORE-001`：QueryPlan 只有在 Business 层验证并绑定后才能进入 Core，依赖方向固定为 Planning→Core→Handler，禁止反向依赖和绕过。

| ID | 要求 |
|---|---|
| `REQ-CORE-001` | 每请求最多形成并执行一个 ActionCandidate |
| `REQ-CORE-002` | Business 候选必须来自一个经验证、绑定的 LLM QueryPlan |
| `REQ-CORE-003` | 模型失败或非法计划不得调用 Local Resolver、Knowledge 或另一个域 |
| `REQ-CORE-004` | QueryPlan 未验证前不得进入 Core |
| `REQ-CORE-005` | 配置 snapshot 与候选/注册绑定必须一致 |
| `REQ-CORE-006` | Core 不包含 Employee/Transaction 自然语言或字段语法 |

## 4. 模块职责与接口契约设计

以下 provider-neutral 类型已由 `WP-BQ-PLAN-CONTRACT-01` 实现；Runtime 只依赖这些稳定边界。

### 4.1 建议新增模块 `agent_runtime.business.query_plan`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class QueryPlanLiteral:
    value: JsonValue

@dataclass(frozen=True, slots=True, kw_only=True)
class QueryPlanValueRef:
    value_ref: str

QueryPlanArgumentValue: TypeAlias = QueryPlanLiteral | QueryPlanValueRef

@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryPlan:
    domain: str
    action: str
    arguments: Mapping[str, QueryPlanArgumentValue]

@dataclass(frozen=True, slots=True, kw_only=True)
class ProtectedValueSlots:
    request_id: str
    values: Mapping[str, object]

@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatedBusinessQueryPlan:
    plan: BusinessQueryPlan
    config_snapshot_id: str

@dataclass(frozen=True, slots=True, kw_only=True)
class UnsupportedBusinessQueryPlan:
    domain: str
    config_snapshot_id: str

BusinessQueryPlanValidationResult: TypeAlias = (
    ValidatedBusinessQueryPlan | UnsupportedBusinessQueryPlan
)

class BusinessQueryPlanDecoder(Protocol):
    def decode(self, payload: JsonObject) -> BusinessQueryPlan: ...

class BusinessQueryPlanValidator(Protocol):
    def validate(
        self,
        plan: BusinessQueryPlan,
        *,
        snapshot: BusinessConfigurationSnapshot,
    ) -> BusinessQueryPlanValidationResult: ...

class ProtectedValueBinder(Protocol):
    def bind(
        self,
        plan: ValidatedBusinessQueryPlan,
        *,
        slots: ProtectedValueSlots,
        request_id: str,
    ) -> ActionCandidate: ...
```

约束：

- Decimal 不进入公共 Core `JsonValue` 扩展；QueryPlan 中采用严格 canonical decimal string，域 validator 构造 `Decimal`。
- `ProtectedValueSlots` 不可序列化、不可哈希、`repr` 必须脱敏，且只能匹配同一 `request_id`。
- `UnsupportedBusinessQueryPlan` 仅表示 exact `action=unsupported` 且 arguments 为空；它不能进入 binder/Core。
- `ActionCandidate.arguments` 保持既有 JSON 兼容对象；snapshot 关联由请求图状态/注册绑定保存，不向公共 HTTP 扩展字段。

### 4.2 建议新增模块 `agent_runtime.graph.business_query_planning`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessPlanningInput:
    request_id: str
    minimized_question: str
    protected_slots: ProtectedValueSlots
    config_snapshot: BusinessConfigurationSnapshot
    model_context: ModelCallContext
    cancellation: CancellationSignal

@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessPlanningDecision:
    candidate: ActionCandidate | None
    status: CapabilityStatus | None
    failure_code: str | None
    config_snapshot_id: str

class BusinessQueryPlanningNode:
    async def __call__(
        self,
        input: BusinessPlanningInput,
    ) -> BusinessPlanningDecision: ...
```

构造依赖：model `BusinessQueryPlanGenerator`、Business `BusinessQueryPlanDecoder`、validator、binder 和 registry view。generator 内部完成 provider response→`JsonObject` 的严格 JSON 解码；Business decoder 只完成 `JsonObject`→三字段/tagged-value `BusinessQueryPlan` 的严格对象解码。不得接收 Local Resolver。

## 5. 核心处理流程与调用边界

`BusinessQueryPlanningNode.__call__` 必须按以下顺序执行：

1. 校验 request/model context/deadline/snapshot 一致性，并在模型调用前检查 request-scoped `CancellationSignal`；
2. 调用一次 `BusinessQueryPlanGenerator.generate(...)`，取得已通过 provider JSON framing/大小/深度校验的 `JsonObject`；
3. 模型返回后再次检查 `CancellationSignal`；已取消则丢弃迟到结果并返回 `timeout`，不得进入 decoder/binder/Core；
4. 调用 `BusinessQueryPlanDecoder.decode(...)` 对对象执行 exact `domain/action/arguments` 与 tagged-value 解码；
5. `BusinessQueryPlanValidator.validate(...)` 校验 domain/action/arguments/config；若返回 unsupported 终态则立即结束；
6. 绑定前再次检查取消；仅对 `ValidatedBusinessQueryPlan` 调用 `ProtectedValueBinder.bind(..., request_id=input.request_id)`，显式校验并解析同请求引用后构造候选参数；
7. 使用 Registry 对应的既有 `CapabilityArgumentValidator.validate(...)` 再校验；
8. 返回唯一 ActionCandidate；
9. 图进入 `CapabilityExecutionCore.execute(...)` 一次。

任何步骤失败均直接返回终态，不继续后续步骤。禁止：模型重试、计划修补、Local Resolver、ID-only selector 补参、另一个 domain、Knowledge 回退。

## 6. 组合根改造

### 6.1 `agent-runtime/src/agent_runtime/bootstrap.py`

`RuntimeCompositionRoot` 使用以下兼容式签名：

```python
class RuntimeCompositionRoot:
    def build(
        *,
        settings: CoreRuntimeSettings,
        providers: Sequence[CapabilityRegistrationProvider],
        capability_selector: CapabilitySelectionNode,
        answer_generator: AnswerGenerationNode,
        local_action_resolvers: Sequence[LocalActionResolver] = (),
        business_query_plan: BusinessQueryPlanRuntimeBindings | None = None,
    ) -> AgentRuntimeInvoker: ...
```

`BusinessQueryPlanRuntimeBindings` 只携带 Business definitions/snapshot/catalog/generator/context/extractor/guard；decoder、validator、binder 与 registry view 由组合根固定装配。为兼容既有 Knowledge 分支，公共 Runtime 仍可接收 `local_action_resolvers`，但启动时只允许它们绑定已从 Business action 集合剔除的非 Business descriptor。Business 分支先按有限业务锚点进入 planning，不能调用、枚举或回退至该 Hybrid/ID-only 分支；包含业务锚点但输入非法时仍在 Business Guard 内失败关闭。

### 6.2 启动校验

建议新增：

```python
def validate_business_query_plan_composition(
    *,
    registry: CapabilityRegistry,
    definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
    snapshot: BusinessConfigurationSnapshot,
    planner_catalog: BusinessPlannerCatalog,
) -> None: ...
```

校验：

- snapshot 中启用动作与 definitions/registry/catalog 完全一致；
- 每个动作一个 validator、handler、Adapter binding；
- domain/action 到 capability ID 映射一一对应；
- Business definitions 不再包含有效 `local_action_resolver` 绑定；
- catalog 的 `domain/action` 对、snapshot 启用动作、definitions 和 registry 必须数量及值完全一致；
- `HybridActionSelectionNode` 和 ID-only selector 只属于显式非 Business fallback 分支，对 Business 输入不可达；
- 默认生产 stub 组合不装配可执行 Business generator/bindings并固定失败关闭；测试范围可显式注入 fake generator 与 fake handler 验证成功链，但不能据此证明 live/UAT。

## 7. Core 与 Registry 保持不变的部分

`agent-runtime/src/agent_runtime/core/registry.py` 继续负责 descriptor/validator/handler 注册唯一性；`agent-runtime/src/agent_runtime/core/execution.py` 继续负责：

- candidate 基本结构、注册和 enabled 校验；
- action latch 从 0→1；
- 领域 argument validator；
- handler 调用、取消/deadline 和结果契约；
- 统一异常到有限 `CapabilityStatus/FailureDetail`。

Core 不读取问题、不调用模型、不解析 QueryPlan、不读取 Business 配置字段，也不切换动作。

## 8. 状态与错误映射

| 原因 | `BusinessPlanningDecision` | Core/Adapter 调用 |
|---|---|---|
| model input denied / Business Guard 拒绝 | `forbidden` | 0/0 |
| model unavailable | `downstream_failure` | 0/0 |
| model timeout/cancel | `timeout` | 0/0 |
| JSON/Schema/值引用非法 | `invalid_argument` | 0/0 |
| 未开放 domain/action/field/operator | `unsupported` | 0/0 |
| snapshot mismatch | `internal_failure`，readiness 原则上应先失败 | 0/0 |
| candidate validator 失败 | `invalid_argument` | 0/0 |
| 成功 | candidate | Core 1，Adapter 最多1 |

错误详情只使用固定 code，例如 `business.plan_model_failure`、`business.plan_invalid`、`business.plan_unsupported`、`business.plan_snapshot_mismatch`、`business.protected_value_invalid`；不携带模型原文或业务值。

## 9. 并发、取消与安全

- 每请求新建 `ProtectedValueSlots`、planning input/decision 和 action latch；
- model gateway 可共享，`ModelCallContext` 必须显式绑定 request/correlation/deadline；
- 取消发生于计划阶段时不得调用 binder/Core；执行阶段取消沿既有 Core/Adapter 传播；
- 日志不输出 original/minimized question、slot、完整 plan、JWT 或模型响应；
- metrics 记录 `planning_calls`、`planning_terminal`、`core_execute_calls`、`adapter_calls` 的整数及有限标签。

## 10. 实现落点清单

| ID | 路径 | 类型 | 目标变更 |
|---|---|---|---|
| `IMPL-CORE-001` | `agent-runtime/src/agent_runtime/business/query_plan.py` | 已存在 | QueryPlan/slot/validator/binder provider-neutral 类型 |
| `IMPL-CORE-002` | `agent-runtime/src/agent_runtime/graph/business_query_planning.py` | 建议新增（候选已实现） | 单次模型计划与确定性转换节点 |
| `IMPL-CORE-003` | `agent-runtime/src/agent_runtime/bootstrap.py` | 建议修改（候选已实现） | Business 分支切换、非 Business fallback 隔离、启动唯一性校验 |
| `IMPL-CORE-004` | `agent-runtime/src/agent_runtime/business/contracts.py` | 已存在 | definition 已支持 plan definition 且两域不再绑定 Resolver |
| `IMPL-CORE-005` | `agent-runtime/src/agent_runtime/capability_api/action_resolution.py` | 保留/退役 | 现有类型可留作历史兼容，但 Business 生产组合不得引用 |
| `IMPL-CORE-006` | `agent-runtime/src/agent_runtime/graph/action_resolution.py` | 保留/隔离 | Hybrid 节点不再承载 Business 目标路径 |
| `IMPL-CORE-007` | `agent-runtime/src/agent_runtime/business/protected_input.py` | 建议新增（候选已实现） | 组合域 extractor 的 request-local slot，拒绝跨请求或多域非空 slot；不选择 domain/action |
| `IMPL-CORE-008` | `agent-runtime/src/agent_runtime/graph/state.py`、`agent-runtime/src/agent_runtime/graph/nodes.py`、`agent-runtime/src/agent_runtime/graph/business_query_planning.py` | 建议修改 | 从 `GraphRunContext.execution_scope` 传递请求取消信号，并在模型前/后及绑定前失败关闭 |
| `IMPL-CORE-009` | `agent-runtime/tests/integration/graph/test_business_local_resolvers.py`、`agent-runtime/scripts/run-structured-query-uat.ps1` | 删除/修改 | 删除旧旁路集成测试并移除 launcher 入口；不改共享 resolver 测试 |

不得修改公共 Spring/OpenAPI、业务 Adapter 参数 Schema 或 Java 服务。

## 11. 测试与验证设计

| ID | 测试 | 断言 |
|---|---|---|
| `TEST-CORE-001` | exact plan decode | extra/duplicate/null/超限/物理键拒绝 |
| `TEST-CORE-002` | canonical order | model→decode→validate→bind→candidate→Core 顺序唯一 |
| `TEST-CORE-003` | model failure | Core/Adapter/Knowledge/另一域均0 |
| `TEST-CORE-004` | protected slots | 同请求成功；缺失/重复/跨请求失败且零泄漏 |
| `TEST-CORE-005` | snapshot startup | 漂移/扩大/缺失/重复绑定 readiness 失败 |
| `TEST-CORE-006` | composition reachability | Employee/Transaction 无 Resolver/ID-only selector 可达边 |
| `TEST-CORE-007` | action latch | 每请求 Core/handler 最多1次 |
| `TEST-CORE-008` | concurrency/cancel | 状态隔离、取消后无迟到执行 |
| `TEST-CORE-009` | Core regression | 既有 Registry/Core/CapabilityResult 契约不变 |

建议新增测试模块：`tests.unit.business.test_query_plan`、`tests.unit.graph.test_business_query_planning`、`tests.unit.test_business_query_plan_composition`、`tests.integration.business.test_business_query_plan_runtime`。

## 12. 设计决策

| ID | 决策 |
|---|---|
| `DR-CORE-012` | QueryPlan 位于 Model 与 Core 之间，不扩大 Core 公共契约 |
| `DR-CORE-013` | Employee/Transaction 目标组合根中 Local Resolver 和 ID-only selector 不可达 |
| `DR-CORE-014` | Binder 只解析请求级引用，不做语义参数生成 |
| `DR-CORE-015` | snapshot 绑定由 Business planning 状态携带，Core 仍保持领域中立 |
| `DR-CORE-016` | 默认生产 stub 不装配可执行 Business generator/bindings并固定失败关闭；仅测试范围可注入 fake generator/handler 验证 non-live 链 |

## 13. 当前差距与门禁

`IMPL-CORE-001～008` 已完成 non-live 实施：两级 decoder 后按 validator→binder→registry argument validator 固定顺序生成唯一 candidate，Business 描述符从 Hybrid/ID-only fallback 中剔除，取消/超时/非法计划均在 Core/Adapter 前终止。专属 Employee/Transaction Resolver 及旧旁路测试已删除，生产 Business factory 拒绝非空 legacy Resolver；冻结历史 harness 所需兼容字段保持不变。双域系统 E2E 与真实调用仍由后续工作包/门禁承接，Business UAT 成功路径保持 Blocked。

## 14. 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | 类型/函数、处理顺序、Core 稳定性 | 补齐实现落点与 trace/readiness，修复后通过 |
| 内审2 | unsupported 不进入 Core、固定失败映射 | 增加终态 union/分支约束，修复后通过 |
| 内审3 | 组合根唯一性、并发隔离、依赖无环 | 无新增问题，通过 |
| 独立评审 R1～R3 | L2 与跨层一致性 | 明确 generator→payload decoder→validator 顺序；R2复核上位 sentinel，R3 无发现，通过 |
| v1.3 内审1 | binder 当前请求安全合同 | 增加显式 `request_id`，关闭无法证明同请求绑定的问题 |
| v1.3 内审2 | 共享 Runtime 分支与失败语义 | 明确 Business/非 Business 分支隔离、非法业务输入不回退、input denied=`forbidden` |
| v1.3 内审3 | 组合校验、trace 与过度设计 | 增加 domain/action 数量和值一致性；复用共享 Runtime 而不新增第二编排器，通过 |
| v1.4 独立复评 R1 | 取消与迟到结果 | S1：缺少显式 `CancellationSignal` 接缝；冻结发现后进入授权内修订 |
| v1.4 内审1 | 取消信号所有权与依赖 | 信号继续由 request execution scope 所有，Runtime 只透传/检查，不扩公共 Core/HTTP |
| v1.4 内审2 | 前置/迟到/失败语义 | 模型前、模型返回后和 binder 前检查；统一 `timeout`，Core/Adapter=0 |
| v1.4 内审3 | 并发、兼容与过度设计 | `ActionSelectionInput` 仅增加可选内部信号，既有非 Business 节点忽略；不新增全局状态，通过 |
| v1.5 内审1 | 唯一可达性与清理范围 | 删除两域专属 Resolver/旧旁路测试，保留非 Business shared Hybrid |
| v1.5 内审2 | 历史 harness 兼容 | 修正为保留 legacy 字段、生产 factory 拒绝非空 Resolver，避免破坏冻结源码复验 |
| v1.5 内审3 | 引用、取消、版本与无环 | 空 support 字段延后至 E2E 解除调用；不新增节点、依赖或公共合同 |
| v1.5 独立评审 R1～R3 | 可达性、冻结兼容与实现触点 | R1 修复 legacy 字段误删，R2 增加旧集成测试/launcher 清理落点，R3 无发现 |

Approved 表示本文可作为实施依据，不表示目标代码已实现。

## 15. 质量、风险与实现就绪判定

本设计保持 Core 稳定契约，新增抽象的必要性仅来自“模型计划对象在进入 Core 前必须有独立不可信边界”；最小变更是不扩展公共 ActionCandidate/HTTP。错误分类和调用方可见错误码见第8章。请求数据生命周期止于请求终态，无持久化或迁移；回滚只禁用新组合根。权限与审计设计只记录有限阶段/计数，不记录 token/slot/plan 原文。

| 项目 | 内容 |
|---|---|
| 是否可作为实现依据 | 是，设计可作为后续代码实施依据，但当前未授权实施 |
| 当前允许实施范围 | `GATE-064` 已关闭；允许完成 `WP-BQ-PLAN-RUNTIME-01` non-live 实现、复核及原子提交 |
| 当前禁止动作 | 修改公共 Core/HTTP、业务字段、真实模型调用或恢复 Business Resolver 旁路 |

## 16. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-CORE-001`; `CON-CORE-001` | `DR-CORE-012` | `IMPL-CORE-001` | `TEST-CORE-001` | `VAL-CORE-001` |
| `REQ-CORE-002` | `DR-CORE-013` | `IMPL-CORE-003` | `TEST-CORE-006` | `VAL-CORE-002` |
| `REQ-CORE-003` | `DR-CORE-016` | `IMPL-CORE-003` | `TEST-CORE-003` | `VAL-CORE-003` |
