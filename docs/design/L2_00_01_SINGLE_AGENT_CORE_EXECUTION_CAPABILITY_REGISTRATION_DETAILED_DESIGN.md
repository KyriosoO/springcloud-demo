# [L2_00_01] 单体 Agent Core 执行、QueryPlan 接缝与能力注册详细设计

> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L2_00_01 |
| 当前版本 | v1.2 |
| 更新日期 | 2026-08-24 |
| 上位设计 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v1.1 |
| 协作设计 | `L2_00_02` v1.2、`L2_02_00` v1.2 |
| 实施状态 | 既有 Core/Registry/Hybrid 节点已实现；本文新增的 Business QueryPlan 接缝和生产组合根切换尚未实现 |

## 2. 修改历史、设计目标与范围

| 版本 | 日期 | 修改内容 |
|---|---|---|
| v1.1 | 2026-08-21 | 既有 Core/Hybrid/Registry 详细设计基线 |
| v1.2 | 2026-08-24 | 新增 Business QueryPlan→ActionCandidate 唯一接缝并退役 Business Resolver 目标路径 |

本文定义 Business QueryPlan 如何在 LangGraph 中转换为既有 `ActionCandidate`，以及 Registry/Core/组合根如何保证单动作和唯一链路。

范围外/不负责：不修改以下公共契约：

- `CapabilityDescriptor`、`ActionCandidate`、`CapabilityResult` 的既有对外含义；
- `CapabilityExecutionCore.execute(...)` 的职责；
- Spring/Runtime HTTP/OpenAPI；
- Employee/Transaction 参数字段和 Adapter codec。

当前 `LocalActionResolver`、`HybridActionSelectionNode` 和 ID-only selector 是现状代码。本版本要求它们对 Employee/Transaction 生产路径不可达；历史测试/证据保持不变，但不能证明新设计已实现。

## 3. 上位约束、需求与关联责任边界

上位约束来源是 L1_00 v1.1 的唯一编排、单动作和无 Business Resolver 旁路；本 L2 负责图/Core 接缝，不负责域字段、模型 transport 或 HTTP codec。`CON-CORE-001`：QueryPlan 只有在 Business 层验证并绑定后才能进入 Core，依赖方向固定为 Planning→Core→Handler，禁止反向依赖和绕过。

| ID | 要求 |
|---|---|
| `REQ-CORE-001` | 每请求最多形成并执行一个 ActionCandidate |
| `REQ-CORE-002` | Business 候选必须来自一个经验证、绑定的 LLM QueryPlan |
| `REQ-CORE-003` | 模型失败或非法计划不得调用 Local Resolver、Knowledge 或另一个域 |
| `REQ-CORE-004` | QueryPlan 未验证前不得进入 Core |
| `REQ-CORE-005` | 配置 snapshot 与候选/注册绑定必须一致 |
| `REQ-CORE-006` | Core 不包含 Employee/Transaction 自然语言或字段语法 |

## 4. 模块职责与接口契约设计

以下为建议新增的 provider-neutral 类型；实现位置由本文固定，均未实现。

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

1. 校验 request/model context/deadline/snapshot 一致性；
2. 调用一次 `BusinessQueryPlanGenerator.generate(...)`，取得已通过 provider JSON framing/大小/深度校验的 `JsonObject`；
3. 调用 `BusinessQueryPlanDecoder.decode(...)` 对对象执行 exact `domain/action/arguments` 与 tagged-value 解码；
4. `BusinessQueryPlanValidator.validate(...)` 校验 domain/action/arguments/config；若返回 unsupported 终态则立即结束；
5. 仅对 `ValidatedBusinessQueryPlan` 调用 `ProtectedValueBinder.bind(...)`，解析同请求引用并构造候选参数；
6. 使用 Registry 对应的既有 `CapabilityArgumentValidator.validate(...)` 再校验；
7. 返回唯一 ActionCandidate；
8. 图进入 `CapabilityExecutionCore.execute(...)` 一次。

任何步骤失败均直接返回终态，不继续后续步骤。禁止：模型重试、计划修补、Local Resolver、ID-only selector 补参、另一个 domain、Knowledge 回退。

## 6. 组合根改造

### 6.1 `agent-runtime/src/agent_runtime/bootstrap.py`

目标修改 `RuntimeCompositionRoot`，建议签名：

```python
class RuntimeCompositionRoot:
    def build(
        self,
        *,
        registration_providers: Sequence[CapabilityRegistrationProvider],
        business_definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
        business_snapshot: BusinessConfigurationSnapshot,
        business_query_plan_generator: BusinessQueryPlanGenerator,
        business_query_plan_decoder: BusinessQueryPlanDecoder,
        business_query_plan_validator: BusinessQueryPlanValidator,
        protected_value_binder: ProtectedValueBinder,
    ) -> RuntimeComponents: ...
```

Employee/Transaction 目标组合根不得接收或枚举 `local_action_resolvers`。Knowledge 若仍需自身确定性节点，应在 Knowledge 组合根内治理，不能形成 Business candidate。

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
- `HybridActionSelectionNode` 和 ID-only selector 不在 Business 图的可达对象图；
- model provider 为 stub 时可启动非 live，但 Business 成功路径必须固定失败关闭，不能执行 Adapter。

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
| model denied/unavailable | `downstream_failure` | 0/0 |
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
| `IMPL-CORE-001` | 建议新增模块 `agent_runtime.business.query_plan` | 建议新增 | QueryPlan/slot/validator/binder provider-neutral 类型 |
| `IMPL-CORE-002` | 建议新增模块 `agent_runtime.graph.business_query_planning` | 建议新增 | 单次模型计划与确定性转换节点 |
| `IMPL-CORE-003` | `agent-runtime/src/agent_runtime/bootstrap.py` | 修改 | Business 组合根切换、唯一性校验、移除 Resolver 可达边 |
| `IMPL-CORE-004` | `agent-runtime/src/agent_runtime/business/contracts.py` | 修改 | definition 移除强制 LocalActionResolver，增加 plan definition 引用 |
| `IMPL-CORE-005` | `agent-runtime/src/agent_runtime/capability_api/action_resolution.py` | 保留/退役 | 现有类型可留作历史兼容，但 Business 生产组合不得引用 |
| `IMPL-CORE-006` | `agent-runtime/src/agent_runtime/graph/action_resolution.py` | 保留/隔离 | Hybrid 节点不再承载 Business 目标路径 |

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
| `DR-CORE-016` | stub 仅验证失败关闭，不能产生 Business 成功候选 |

## 13. 当前差距与门禁

`IMPL-CORE-001～004` 尚未实现；P3_00 的 `WP-BQ-PLAN-CONTRACT-01` 和 `WP-BQ-PLAN-RUNTIME-01` 负责实施。完成前 Business UAT 成功路径保持 Blocked。

## 14. 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | 类型/函数、处理顺序、Core 稳定性 | 补齐实现落点与 trace/readiness，修复后通过 |
| 内审2 | unsupported 不进入 Core、固定失败映射 | 增加终态 union/分支约束，修复后通过 |
| 内审3 | 组合根唯一性、并发隔离、依赖无环 | 无新增问题，通过 |
| 独立评审 R1～R3 | L2 与跨层一致性 | 明确 generator→payload decoder→validator 顺序；R2复核上位 sentinel，R3 无发现，通过 |

Approved 表示本文可作为实施依据，不表示目标代码已实现。

## 15. 质量、风险与实现就绪判定

本设计保持 Core 稳定契约，新增抽象的必要性仅来自“模型计划对象在进入 Core 前必须有独立不可信边界”；最小变更是不扩展公共 ActionCandidate/HTTP。错误分类和调用方可见错误码见第8章。请求数据生命周期止于请求终态，无持久化或迁移；回滚只禁用新组合根。权限与审计设计只记录有限阶段/计数，不记录 token/slot/plan 原文。

| 项目 | 内容 |
|---|---|
| 是否可作为实现依据 | 是，设计可作为后续代码实施依据，但当前未授权实施 |
| 当前允许实施范围 | 取得 P3 `GATE-064` 后，仅限 IMPL-CORE-001～006 |
| 当前禁止动作 | 修改公共 Core/HTTP、业务字段、真实模型调用或恢复 Business Resolver 旁路 |

## 16. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-CORE-001`; `CON-CORE-001` | `DR-CORE-012` | `IMPL-CORE-001` | `TEST-CORE-001` | `VAL-CORE-001` |
| `REQ-CORE-002` | `DR-CORE-013` | `IMPL-CORE-003` | `TEST-CORE-006` | `VAL-CORE-002` |
| `REQ-CORE-003` | `DR-CORE-016` | `IMPL-CORE-003` | `TEST-CORE-003` | `VAL-CORE-003` |
