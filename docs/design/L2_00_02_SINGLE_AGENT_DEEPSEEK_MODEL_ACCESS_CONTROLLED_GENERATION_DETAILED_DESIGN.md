# [L2_00_02] 单体 Agent DeepSeek 模型接入与 Business QueryPlan 受控生成详细设计

> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L2_00_02 |
| 当前版本 | v1.5 |
| 更新日期 | 2026-08-24 |
| 上位设计 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v1.2 |
| 协作设计 | `L2_00_01` v1.5、`L2_02_00` v1.6 |
| Provider | DeepSeek OpenAI-compatible API；默认 Runtime Provider 仍为 `stub` |
| 实施状态 | `business-query-plan-v1`、模型安全输入接缝、no-tools request、provider exact JSON decoder、fake transport 及生产 Business non-live 组合根已实现；真实模型验证尚未实施 |

## 2. 修改历史、设计目标与范围

| 版本 | 日期 | 修改内容 |
|---|---|---|
| v1.1 | 2026-08-21 | 既有 transport、ID-only selector、answer task 基线 |
| v1.2 | 2026-08-24 | 新增 `business-query-plan-v1`，Business 不再使用 ID-only selector |
| v1.3 | 2026-08-24 | 同步 `WP-BQ-MODEL-QUERYPLAN-01` non-live 实施与验证状态；生产 wiring/live 门禁保持未关闭 |
| v1.4 | 2026-08-24 | 校正 protected extractor 与 Model Guard 职责；非法 Business 输入固定在 Business 分支失败关闭，澄清生产 stub 与测试 fake 的边界 |
| v1.5 | 2026-08-24 | 明确历史 ID-only task/evidence 不改写，但 Employee/Transaction 不保留任何依赖该 task 的生产装配或专属兼容接缝 |

本文新增一个 provider-neutral `business-query-plan-v1` 模型任务。对于 Employee/Transaction，它取代“action-selection-v4 只输出 capability ID”的目标职责；旧 task 和历史 PoC/evidence 保持不可变，但不能作为新 QueryPlan 链路证据。

范围外/不负责：本文不定义业务字段合法性、Adapter、SQL/ES、权限或结果字段；这些由 Business L2 和业务服务治理。模型输出始终不可信，只有经下游本地 validator/binder 后才可执行。

上位约束来源是 L1_00 v1.2 的模型端口、唯一链路和敏感数据边界。关联责任边界：Model 只生成未信任计划，Business 层校验语义，Core 执行候选。`CON-MODEL-001`：禁止 Model 依赖 Adapter/业务服务/JWT，禁止 ID-only selector 绕过 QueryPlan。

当前实现基线已包含 transport/gateway、历史 action selector、answer task，以及新增的 QueryPlan task/generator/provider decoder 和 Business 输入保护接缝；catalog 由 Business common 构造，QueryPlan generator 已在 Runtime Business 专用分支完成 non-live 装配。历史 action selector 仅保留给非 Business/历史验证，对 Employee/Transaction 生产组合不可达。

## 3. 模块职责、依赖方向与模型任务分类

| Task | 输入 | 输出 | 是否 Business 目标路径 |
|---|---|---|---|
| `business-query-plan-v1` | 最小化问题、模型安全 Business catalog | exact `{domain,action,arguments}` | 是，强制 |
| `action-selection-v4` | 问题、安全 capability catalog | exact capability ID | 否，不得用于 Employee/Transaction 目标路径 |
| `answer-generation-v2` | 已批准安全 facts | grounded answer | 可选、默认关闭 |
| Knowledge tasks | Knowledge 受控输入 | 各自契约 | 与 Business 不互为回退 |

## 4. Provider-neutral 接口契约设计

### 4.1 `agent-runtime/src/agent_runtime/model/contracts.py`

建议扩展：

```python
class ModelTaskId(StrEnum):
    BUSINESS_QUERY_PLAN = "business_query_plan"
    # 既有枚举保持

@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryPlanTaskInput:
    minimized_question: str
    catalog: JsonObject
    catalog_snapshot_id: str

class BusinessQueryPlanGenerator(Protocol):
    async def generate(
        self,
        input: BusinessQueryPlanTaskInput,
        *,
        context: ModelCallContext,
    ) -> JsonObject: ...
```

返回 `JsonObject` 仍是未信任 decoded object；业务语义校验由 `L2_02_00` 完成。接口不接收 original question、slot values、JWT、结果或 Adapter 信息。

### 4.2 task definition（建议新增模块 `agent_runtime.model.deepseek.business_query_plan`）

```python
BUSINESS_QUERY_PLAN_TASK_VERSION = "business-query-plan-v1"

def build_business_query_plan_task_definition(
    *,
    max_output_bytes: int,
    max_json_depth: int,
    max_collection_items: int,
) -> ModelTaskDefinition[BusinessQueryPlanTaskInput, JsonObject]: ...

class DeepSeekBusinessQueryPlanGenerator:
    async def generate(
        self,
        input: BusinessQueryPlanTaskInput,
        *,
        context: ModelCallContext,
    ) -> JsonObject: ...

def decode_business_query_plan_output(
    response: StructuredModelResponse,
    *,
    max_output_bytes: int,
    max_json_depth: int,
    max_collection_items: int,
) -> JsonObject: ...
```

`DeepSeekBusinessQueryPlanGenerator.generate(...)` 必须在内部调用 `decode_business_query_plan_output(...)`，因此其返回值已是通过 provider JSON framing、重复键、大小、深度和集合上限校验的 `JsonObject`，不暴露模型原始文本或 `StructuredModelResponse` 给 Runtime。`JsonObject`→`BusinessQueryPlan` 的三字段/tagged-value exact decode 由 L2_02_00 定义的 Business decoder 负责；两级解码不得重复解析文本，也不得互相承担业务字段合法性。

## 5. 模型安全 Catalog

Catalog 由 Business code definitions 与配置 snapshot 的交集生成，建议新增：

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessPlannerCatalog:
    snapshot_id: str
    payload: JsonObject

def build_business_planner_catalog(
    definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
    snapshot: BusinessConfigurationSnapshot,
) -> BusinessPlannerCatalog: ...
```

模型可见：

- finite `domain`、`action`；
- 每个逻辑字段的模型安全描述、类型、允许 operator；
- required/optional、互斥/组合、Decimal/size/sort 的有限边界；
- 参数应使用 literal 还是 `value_ref`；
- 无法表达时必须返回协议定义的 `unsupported` 计划结果。

模型不可见：

- endpoint、HTTP method/header、服务地址；
- SQL、ES DSL、索引、表、列物理名；
- Python/Java 类、模块、函数、方法；
- JWT、角色、subject、slot value；
- 用户/模型结果字段、原始业务数据；
- disabled action/field/operator。

Catalog canonical JSON 参与 snapshot/hash 测试，启动时与 Business snapshot 对齐。

## 6. 输入安全、权限与审计设计

### 6.1 输入闸门

现有 `model/question_policy.py` 与 `model/input_guard.py` 继续优先拒绝凭证、JWT、账户等禁止输入。输入处理分为两个不重叠责任：

1. Business/domain protected extractor 只识别代码绑定的明确受保护 literal，在请求内存创建无业务语义 `slot-N`；它不得选择 domain/action，多个域同时形成非空 slot 或跨请求绑定时失败；
2. Model `QuestionEgressGuard.is_business_question(...)` 只按有限 Employee/Transaction 业务锚点决定进入 Business 安全分支，不判定具体 domain/action；即使问题超长或含控制字符，也不得因此落入 Knowledge/ID-only fallback，而应交给 Business Guard 拒绝；
3. `QuestionEgressGuard.evaluate_business(...)` 接收 request-local slot map，将唯一 literal 替换为固定占位表达并执行敏感分类，输出 minimized question 或 `forbidden`；
4. 只有 Guard 允许后，Runtime 才能调用一次 Business QueryPlan generator。

Extractor/Guard 均不输出 domain/action，不生成执行参数，不校验业务字段组合。slot value 不进入模型输入、日志或 evidence。

### 6.2 模型输出引用

模型只能把 catalog 声明为 `protected_ref` 的字段输出为 `{"value_ref":"slot-N"}`，不能回显或猜测原值。不存在的 ref 在本地失败；模型不得请求 slot 内容。

## 7. 输出协议与核心处理流程

正常计划只允许：

```json
{
  "domain": "transaction",
  "action": "transaction.search",
  "arguments": {
    "amount_gt": {"literal": "100.00"}
  }
}
```

不支持的自然语言意图仍使用相同三字段 QueryPlan 外形；`unsupported` 是协议保留 action，不是可执行业务动作：

```json
{
  "domain": "employee",
  "action": "unsupported",
  "arguments": {}
}
```

对无法归入 Employee/Transaction 的问题，`domain` 使用协议保留值 `unsupported`。禁止 reason 自由文本。任务合同要求 `domain/action/arguments` 三字段结构；provider decoder 只安全地产生 `JsonObject`，随后 Business decoder 严格执行三字段/tagged-value 解码，Business validator 再将保留 sentinel 映射为 `unsupported` 并校验其余 domain/action/field/config。

provider response exact JSON decode 限制：

- no-tools；只允许 JSON Output；
- 顶层必须为单个 JSON object，重复键拒绝、UTF-8、最大 16 KiB、深度≤8、集合项≤128；
- 禁止 markdown fence、前后文本、null、float/非有限数；
- decoder 不做 coercion、key rename、值修复或重试。

Business payload decoder 随后强制顶层 exact 三字段、argument value 为 `literal`/`value_ref` 二选一，并递归拒绝 `sql/dsl/url/index/table/class/method/endpoint/http/headers/jwt/role` 等物理或安全键；该职责见 L2_02_00，不由 provider decoder重复实现。

## 8. Prompt 约束

system instruction 必须表达：

1. 只从 catalog 选择一个 domain/action；无法表达时使用保留 `unsupported` sentinel；
2. 根据用户问题生成所有且仅必要的逻辑 arguments；
3. 严格遵守字段、operator、组合和边界；
4. protected field 只引用已有 slot；
5. 不输出物理查询或实现信息；
6. 不可表达时仍输出 exact 三字段 QueryPlan，action 为 `unsupported`、arguments 为空；
7. 不解释、不建议另一个域、不生成第二动作。

Prompt、task version、catalog schema 和 decoder source 均需在 UAT manifest 中冻结。更改任一项需新 task version 和重新验证。

## 9. Transport 与运行设置

复用 `agent_runtime/model/deepseek/transport.py`、`gateway.py` 和现有 `httpx` 生命周期：

- API Key 仅从 `LLM_API_KEY` 注入，不记录/持久化；
- 模型名、base URL、timeout、concurrency 为受控设置；
- QueryPlan task 自动重试固定为 0；
- cancel/deadline 透传；
- HTTP/Schema/timeout 映射为有限 `ModelProviderFailureKind`；
- default `AGENT_MODEL_PROVIDER=stub`。

显式 `deepseek` 且配置完整才可进入真实 QueryPlan UAT。默认生产 stub 组合不装配可执行 Business generator/bindings并固定 model failure/unsupported；仅测试范围可显式注入 fake generator 与 fake handler 验证 non-live 成功链，该证据不能关闭 live/UAT 门禁。

## 10. 错误分类、失败映射与调用方可见错误码

| 模型层原因 | planning 结果 | 下游行为 |
|---|---|---|
| input denied | `forbidden` | Core/Adapter=0 |
| unsupported exact output | `unsupported` | Core/Adapter=0 |
| timeout/cancel | `timeout` | 无重试/降级 |
| network/provider | `downstream_failure` | 无重试/降级 |
| malformed/schema/prohibited key | `invalid_argument` | 不修补 |
| catalog snapshot mismatch | `internal_failure` | readiness 原则上先失败 |

错误与日志不包含请求、响应、slot、key 或 provider 原始正文。

## 11. 组合根与生命周期

`LocalModelCompositionRoot` 建议增加：

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LocalModelComponents:
    business_query_plan_generator: BusinessQueryPlanGenerator
    answer_generator: AnswerGenerator
    # existing components

class LocalModelCompositionRoot:
    def build(
        self,
        *,
        settings: ModelSettings,
        business_catalog: BusinessPlannerCatalog,
    ) -> LocalModelComponents: ...
```

真实 transport 仍由组合根单例拥有并显式 `aclose()`；调用 context 请求隔离。不得把 ID-only selector 作为 Business generator 注入。

## 12. 实现落点清单

| ID | 路径 | 类型 | 目标变更 |
|---|---|---|---|
| `IMPL-MODEL-001` | `agent-runtime/src/agent_runtime/model/contracts.py` | 修改 | task id/input/generator protocol |
| `IMPL-MODEL-002` | 建议新增模块 `agent_runtime.model.deepseek.business_query_plan` | 建议新增 | request、prompt、decoder、generator |
| `IMPL-MODEL-003` | `agent-runtime/src/agent_runtime/model/input_guard.py` | 已修改/回归 | Business 锚点分支、minimized question、slot redaction 与拒绝接缝；不创建 slot、不选择域 |
| `IMPL-MODEL-004` | `agent-runtime/src/agent_runtime/model/gateway.py` | 修改 | 注册 code-bound QueryPlan task |
| `IMPL-MODEL-005` | `agent-runtime/src/agent_runtime/bootstrap.py` | 修改 | generator/catalog/context/lifecycle 装配 |
| `IMPL-MODEL-006` | `agent-runtime/src/agent_runtime/model/deepseek/action_selector.py` | 保留/隔离 | 不得服务 Business 目标路径；历史行为不改写 |

## 13. 测试与验证设计

| ID | 测试 | 关键断言 |
|---|---|---|
| `TEST-MODEL-001` | catalog snapshot | 只含安全逻辑字段；物理/权限/结果信息为0 |
| `TEST-MODEL-002` | provider exact JSON decoder | 单一 JSON object、重复键/fence/前后文本/null/float/超限拒绝；三字段/tagged union 由 `TEST-BQCOM-001` 验证 |
| `TEST-MODEL-003` | prompt contract | domain/action/arguments 强制；unsupported 唯一终态 |
| `TEST-MODEL-004` | input slotting | extractor 创建 request-local slot；受保护 literal 不进入 transport；非法业务输入不回退；Guard 不生成语义计划 |
| `TEST-MODEL-005` | failure/zero call | input denied 调用0；provider failure 无 retry/fallback |
| `TEST-MODEL-006` | composition | Business 注入 QueryPlan generator，不注入 ID-only selector |
| `TEST-MODEL-007` | lifecycle/concurrency | context 隔离、cancel、close、secret/log 零泄漏 |
| `TEST-MODEL-008` | history | 既有 task/source/evidence hash 不被改写 |

真实模型 UAT 另行授权，固定 case、task/prompt/catalog/HEAD、调用上限和一次性授权；非 live 测试不得读取 `LLM_API_KEY`。

## 14. 设计决策

| ID | 决策 |
|---|---|
| `DR-MODEL-016` | 新建 `business-query-plan-v1`，不篡改历史 ID-only task |
| `DR-MODEL-017` | no-tools exact JSON 同时输出 domain/action/arguments |
| `DR-MODEL-018` | protected value 用 opaque ref，不向模型暴露原值 |
| `DR-MODEL-019` | provider decoder 只做 JSON framing/资源限制；Business payload decoder 做计划结构，业务语义由 validator 决定 |
| `DR-MODEL-020` | 模型失败无 retry、Local Resolver 或跨域降级 |
| `DR-MODEL-021` | 默认 stub 只能证明失败关闭，不能满足 Business UAT |

## 15. 当前差距与门禁

`WP-BQ-PLAN-CONTRACT-01`、`WP-BQ-MODEL-QUERYPLAN-01`、两域 definition/config 与 Runtime Business 专用分支已完成 non-live 实施和代码复核：catalog、task、输入保护、provider decoder、失败关闭及组合根唯一性验证已具备。系统级 non-live E2E 与真实调用仍由后续工作包和独立门禁承接；旧 Action PoC 不自动关闭新 QueryPlan 门禁。

## 16. 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | task/catalog/decoder/失败语义 | 补齐实现与验证追踪，修复后通过 |
| 内审2 | exact JSON、敏感输入、ID-only 隔离 | 无可执行旁路，修复状态词汇后通过 |
| 内审3 | 工作包引用、历史资产与模型调用边界 | 修正工作包引用；无真实调用，修复后通过 |
| 独立评审 R1～R3 | L2 与跨层一致性 | provider JSON decoder 与 Business payload decoder 已分责；R2复核 sentinel，R3 无发现，通过 |
| v1.4 内审1 | extractor/Guard 职责 | slot 创建归 Business/domain extractor，Guard 只负责锚点、最小化和拒绝 |
| v1.4 内审2 | 失败关闭与 fallback | 非法 Business 输入仍固定进入 Business Guard，禁止落入 Knowledge/ID-only |
| v1.4 内审3 | stub/fake、live 门禁与最小变更 | 区分默认生产 stub 和测试 fake；不新增 provider/task/公共合同，通过 |
| v1.5 内审1 | Business/非 Business 模型职责 | 共享 ID-only task 保留但不进入两域 QueryPlan 组合 |
| v1.5 内审2 | 历史 evidence 与任务兼容 | 不改写 task/PoC/evidence，不保留两域专属装配 |
| v1.5 内审3 | 门禁、调用预算与最小性 | 清理阶段不读 key、不调用模型、不新增 task |
| v1.5 独立评审 R1～R3 | ID-only 历史与 Business 隔离 | 共享 task/evidence 保留、两域生产装配为0；R3 无发现 |

Approved 不表示真实模型任务已实施或执行。

## 17. 质量、数据生命周期、风险与实现就绪判定

本设计保持 Model gateway 稳定契约；新 task 的必要性来自 Business 输出合同与历史 ID-only task 不兼容，采用新版本比原地改写影响更小。模型调用数据生命周期仅覆盖单请求，不持久化问题、slot、响应或密钥，无数据迁移；回滚为取消 task 注册并保持 stub。主要风险是 catalog/Prompt 漂移、敏感值出域和错误重试，分别由 snapshot、model spy 和 retry=0 控制。

| 项目 | 内容 |
|---|---|
| 是否可作为实现依据 | 是，设计可作为后续代码实施依据，但当前未授权实施/真实调用 |
| 当前允许实施范围 | `GATE-064` 已关闭；允许完成 Runtime non-live 组合与相关 Model Guard 回归 |
| 当前禁止动作 | 读取 LLM_API_KEY、真实调用、修改历史 task/evidence、接入业务结果出域 |

## 18. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-MODEL-001`; `CON-MODEL-001` | `DR-MODEL-016` | `IMPL-MODEL-001` | `TEST-MODEL-001` | `VAL-MODEL-001` |
| `REQ-MODEL-002` | `DR-MODEL-017` | `IMPL-MODEL-002` | `TEST-MODEL-002` | `VAL-MODEL-002` |
| `REQ-MODEL-003` | `DR-MODEL-018` | `IMPL-MODEL-003` | `TEST-MODEL-004` | `VAL-MODEL-003` |
