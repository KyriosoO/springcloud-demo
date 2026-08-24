# [L2_02_00] 单体 Agent Business QueryPlan 公共约束、配置与出域详细设计

> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L2_02_00 |
| 当前版本 | v1.4 |
| 更新日期 | 2026-08-24 |
| 上位设计 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v1.1 |
| 协作设计 | `L2_00_01` v1.2、`L2_00_02` v1.3、Employee L2 v1.3、Transaction L2 v1.3 |
| 实施状态 | 公共 QueryPlan 合同与 Employee/Transaction definition/config/protected-ref non-live 实现已完成；生产组合根切换和双域 E2E 尚未完成 |

## 2. 修改历史、设计目标与范围外

| 版本 | 日期 | 修改内容 |
|---|---|---|
| v1.1 | 2026-08-21 | 既有 Business common/config/egress 基线 |
| v1.2 | 2026-08-24 | 新增 QueryPlan/typed input config/slot binder，移除 Business definition 的 Resolver 目标绑定 |
| v1.3 | 2026-08-24 | 同步 `WP-BQ-PLAN-CONTRACT-01` non-live 实施证据；域配置与生产唯一链路仍由后续工作包承接 |
| v1.4 | 2026-08-24 | 同步两域 QueryPlan definition/config 完成状态；修正字段子集关闭时 Decimal/排序上界校验，并以拒绝首尾空格/非 NFC 防止文本 literal 在下游被规范化 |

本文详细定义两域共享的：

- QueryPlan provider-neutral 类型、exact 结构、业务校验和受保护值绑定；
- 每域每动作代码 definition 与强类型配置；
- 配置版本、snapshot、启动一致性；
- JWT client、结果投影、可选模型 facts、失败与测试。

本文不负责且不修改公共 Core/HTTP、业务服务 DTO、数据库、角色范围或 endpoint 路径；不实现自然语言本地 Resolver、SQL/ES DSL 或动态工具协议。

上位约束来源是 L1_02 v1.1 的 QueryPlan/config/Adapter 所有权。关联责任边界：common 负责 plan/config/binder，模型 L2 负责 provider decode，域 L2 负责字段/codec，Core 只执行候选。`CON-BQCOM-001`：依赖方向固定为 Model→Business validation→Core→Domain Handler，禁止绕过或反向依赖。

## 3. 当前实现基线与目标差距

现有文件：

- `agent-runtime/src/agent_runtime/business/contracts.py`：`BusinessActionDefinition`、字段/结果/HTTP 类型；
- `agent-runtime/src/agent_runtime/business/settings.py`：动作设置、字段投影、service binding 和 snapshot；
- `agent-runtime/src/agent_runtime/business/handler.py`、`http_client.py`、`result_mapping.py`、`egress.py`；
- 两域 definition 当前强制包含 `local_action_resolver`。

当前剩余差距：公共 QueryPlan/config/decoder/validator/binder 已实现，但 Employee/Transaction definition 尚未切换到强类型字段配置且仍绑定 Local Resolver；生产组合根仍可走旧本地参数路径。

## 4. 模块职责、代码绑定定义与接口契约设计

### 4.1 扩展 `BusinessActionDefinition`

目标签名：

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryFieldDefinition:
    logical_name: str
    model_safe_description: str
    value_type: BusinessQueryValueType
    allowed_operators: frozenset[BusinessQueryOperator]
    input_exposure: BusinessInputExposure
    required: bool
    max_text_chars: int | None = None
    text_policy_id: BusinessTextPolicyId | None = None
    enum_values: frozenset[str] = frozenset()

@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessCombinationRule:
    rule_id: str
    kind: BusinessCombinationRuleKind
    field_names: tuple[str, ...]

@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessActionDefinition(Generic[TInput, TWireRequest, TWireResponse, TRecord]):
    descriptor: CapabilityDescriptor
    domain_id: str
    service_key: BusinessServiceKey
    query_fields: tuple[BusinessQueryFieldDefinition, ...]
    combination_rules: tuple[BusinessCombinationRule, ...]
    argument_validator: CapabilityArgumentValidator[TInput]
    request_mapper: BusinessRequestMapper[TInput, TWireRequest]
    wire_codec: BusinessWireCodec[TWireRequest, TWireResponse]
    response_normalizer: BusinessResponseNormalizer[TWireResponse, TRecord]
    field_definitions: tuple[BusinessFieldDefinition[TRecord, object], ...]
    required_user_field_ids: tuple[str, ...]
    contract_limits: BusinessContractLimits
    answer_mode: BusinessAnswerMode
```

删除目标 definition 对 `LocalActionResolver` 的强制属性；旧类文件可保留历史兼容，但 Employee/Transaction definition 和组合根不得引用。

### 4.2 有限枚举

```python
class BusinessQueryValueType(StrEnum):
    TEXT = "text"
    IDENTIFIER = "identifier"
    DECIMAL = "decimal"
    INTEGER = "integer"
    SORT_LIST = "sort_list"

class BusinessQueryOperator(StrEnum):
    EQ = "eq"
    CONTAINS = "contains"
    GT = "gt"
    LT = "lt"

class BusinessInputExposure(StrEnum):
    MODEL_LITERAL = "model_literal"
    PROTECTED_REF = "protected_ref"

class BusinessTextPolicyId(StrEnum):
    SAFE_TOKEN = "safe_token"
    SAFE_CONTAINS_TOKEN = "safe_contains_token"

class BusinessCombinationRuleKind(StrEnum):
    AT_LEAST_ONE = "at_least_one"
    MUTUALLY_EXCLUSIVE = "mutually_exclusive"
    ALL_OR_NONE = "all_or_none"
```

不引入任意表达式语言。每个动作只声明本身需要的有限规则。

## 5. QueryPlan 数据设计与生命周期

### 5.1 类型

建议新增模块 `agent_runtime.business.query_plan`，类型与 `L2_00_01` 一致。模型 L2 的 provider decoder 只把原始响应严格解码为 `JsonObject`；本模块的 `BusinessQueryPlanDecoder.decode(payload: JsonObject) -> BusinessQueryPlan` 再严格校验顶层仅有 `domain/action/arguments`、argument value 仅为 `literal/value_ref` tagged union，并构造未信任的结构化计划。随后本文 validator 才校验 domain/action/字段/operator/组合/config。计划、slot 和 snapshot 只存在于单请求生命周期，无持久化或数据迁移。

### 5.2 计划值规则

- `MODEL_LITERAL`：只接受 exact `{"literal": value}`；值类型必须匹配 definition/config。
- `PROTECTED_REF`：只接受 exact `{"value_ref": "slot-N"}`；禁止 literal。
- `TEXT` literal 必须执行代码绑定 `BusinessTextPolicyId`：`SAFE_TOKEN` 仅允许 Unicode 字母/数字、空格、`_-.`；`SAFE_CONTAINS_TOKEN` 仅允许 Unicode 字母/数字、空格、`-.`。两者均拒绝控制字符、换行、引号、冒号、斜线/反斜线、括号、花括号、分号、等号和尖括号，不做 normalization/coercion；配置不得提供自定义正则或扩大字符集合。
- Decimal literal 必须匹配 `0|[1-9][0-9]*` 加可选小数，禁止指数、符号 `+`、前导零、NaN/Infinity；允许负数与否由域 definition 决定。
- `SORT_LIST` 是有限对象数组，字段和方向均来自配置 allowlist；禁止表达式和物理列名。

### 5.3 Validator 核心处理流程与调用边界

```python
class DefaultBusinessQueryPlanValidator:
    def validate(
        self,
        plan: BusinessQueryPlan,
        *,
        definitions: Mapping[str, BusinessActionDefinition[Any, Any, Any, Any]],
        snapshot: BusinessConfigurationSnapshot,
    ) -> BusinessQueryPlanValidationResult: ...
```

顺序：

1. 先识别 exact unsupported sentinel：`domain` 仅允许已知域或保留 `unsupported`，`action=unsupported` 且 arguments 为空；返回 `UnsupportedBusinessQueryPlan` 并终止；
2. 对可执行计划校验 domain/action 语法和一一映射；
3. action enabled 与 snapshot/version；
4. argument key exact subset；
5. literal/ref 形态和 input exposure；
6. field type/operator/enum/text/Decimal/int/sort 边界；
7. required/at-least-one/mutual-exclusion/all-or-none；
8. 禁止物理字段、未知字段和超限；
9. 生成不可变 Validated plan。

模型输出不能被 rename、补默认业务条件或改选 action。分页的代码固定值可以在 domain mapper 中使用，但不得把缺失业务筛选条件补成另一查询含义。

## 6. 受保护值绑定

```python
class RequestProtectedValueBinder:
    def bind(
        self,
        plan: ValidatedBusinessQueryPlan,
        *,
        slots: ProtectedValueSlots,
        definitions: Mapping[str, BusinessActionDefinition[Any, Any, Any, Any]],
    ) -> ActionCandidate: ...
```

规则：

- `slots.request_id` 必须等于当前请求；
- ref 必须存在一次，值类别/目标类型匹配，且未被未授权字段复用；
- binder 只把 QueryPlan logical key 映射为同名既有 argument key，并恢复 value；
- binder 不读取 original question、不解析文本、不调用模型或服务；
- 输出立即进入已有 `CapabilityArgumentValidator`；
- slot map 在请求终止后释放，`repr/log/evidence` 均不含值。

## 7. 强类型配置

### 7.1 扩展设置

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryFieldSettings:
    logical_name: str
    enabled: bool
    model_safe_description: str
    allowed_operators: tuple[BusinessQueryOperator, ...]
    required: bool

@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessActionSettings:
    enabled: bool
    config_version: str
    code_contract_version: str
    service_contract_ref: str
    query_fields: tuple[BusinessQueryFieldSettings, ...]
    combination_rule_ids: tuple[str, ...]
    max_decimal_abs: str | None
    max_decimal_scale: int | None
    fixed_page: int | None
    max_page_size: int | None
    max_result_count: int | None
    allowed_sort_field_ids: tuple[str, ...] | None
    allowed_sort_directions: tuple[str, ...] | None
    max_sort_items: int | None
    user_result_field_ids: tuple[str, ...]
    model_field_ids: tuple[str, ...]
    timeout_ms: int
```

使用现有静态环境/配置加载方式即可，不建设配置中心。base endpoint 仍是环境级 service binding；固定 path/method 只在 Adapter codec 中。

### 7.2 子集与 snapshot

`BusinessSettingsValidator.validate(...)` 扩展检查：

- 配置 action/field/operator/rule 是 definition 子集；
- model-safe description 非空、长度有限且不含 URL/SQL/实现标记；TEXT 字段的 `text_policy_id` 必须来自代码 definition，配置只能保持该策略并收紧长度；
- required 不能从代码 required 放宽为 optional；
- Decimal/page/size/result/sort/timeout 不超过代码上限；
- model fields ⊆ user fields ∩ code model candidates；
- service contract ref 与 definition 固定值相等；
- config/code version 非空且进入 canonical snapshot material。

snapshot 继续用 canonical JSON + SHA-256。未知配置 key、重复键、宽松 bool/int 或隐式默认扩大均失败。

## 8. Planner Catalog

```python
def build_business_planner_catalog(
    definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
    snapshot: BusinessConfigurationSnapshot,
) -> BusinessPlannerCatalog: ...
```

只输出有效 domain/action、field 安全描述、logical type/operator/exposure、组合与有限边界。endpoint、service binding、result fields、data class、role、transform 和代码路径不得出现。catalog snapshot 必须绑定 Business snapshot ID。

## 9. Handler、JWT、权限与审计设计

复用既有 `BusinessCapabilityHandler.handle(input, context)`：

1. 从 context 获取 opaque user token，仅传给 `BusinessHttpClient`；
2. mapper/codec 固定构造现有 endpoint 请求；
3. strict response decode/normalize；
4. user projection；
5. 可选 egress policy/facts；
6. 构造 `CapabilityResult`。

Handler 不接收 QueryPlan、slot、original question 或其他 domain Adapter；它只消费已验证 domain input。

## 10. 结果与模型出域

有效交集：

```text
user result = code user-visible ∩ config user fields
model facts = code model-candidate ∩ config model fields
              ∩ user result ∩ data classification policy
```

规划 catalog 与结果 facts 分离。结果 egress 默认 `disabled`；未分类、敏感类别、策略冲突、转换失败或最小字段缺失时模型答案调用为零。即使答案生成失败，也不得重跑业务查询。

## 11. 错误分类、失败语义与调用方可见错误码

| Code | 状态 | 场景 |
|---|---|---|
| `business.plan_invalid` | `invalid_argument` | 结构值/引用/组合非法 |
| `business.plan_unsupported` | `unsupported` | domain/action/field/operator 未启用 |
| `business.plan_snapshot_mismatch` | `internal_failure` | 启动或请求 snapshot 漂移 |
| `business.protected_value_invalid` | `invalid_argument` | ref 缺失/跨请求/类型错误 |
| `business.configuration_invalid` | readiness failed | 配置扩大/不一致 |
| 既有 HTTP/codec codes | 既有状态 | Adapter/业务服务阶段 |

不得把规划失败映射为本地解析、另一个 action 或 `no_result`。

## 12. 实现落点清单

| ID | 路径 | 类型 | 目标变更 |
|---|---|---|---|
| `IMPL-BQCOM-001` | 建议新增模块 `agent_runtime.business.query_plan` | 建议新增 | plan/value/ref/payload decoder/validator/binder |
| `IMPL-BQCOM-002` | `agent-runtime/src/agent_runtime/business/contracts.py` | 修改 | query field/operator/combination 与 definition 去 Resolver |
| `IMPL-BQCOM-003` | `agent-runtime/src/agent_runtime/business/settings.py` | 修改 | typed input config、version、snapshot/subset |
| `IMPL-BQCOM-004` | 建议新增模块 `agent_runtime.business.planner_catalog` | 建议新增 | 安全 catalog |
| `IMPL-BQCOM-005` | `agent-runtime/src/agent_runtime/business/provider.py` | 修改 | 提供 definitions/snapshot/planning bindings |
| `IMPL-BQCOM-006` | `agent-runtime/src/agent_runtime/business/handler.py` | 最小修改/回归 | 仅证明已验证 input 与单 Adapter，不接收 plan |
| `IMPL-BQCOM-007` | `agent-runtime/src/agent_runtime/business/egress.py` | 回归 | 规划 catalog 与结果 facts 分离 |

## 13. 测试与验证设计

| ID | 覆盖 |
|---|---|
| `TEST-BQCOM-001` | `JsonObject`→plan 的 domain/action/arguments exact、tagged union、unsupported 与 prohibited keys |
| `TEST-BQCOM-002` | literal/ref union、字段类型/operator/enum/text；物理键及 SQL/DSL/URL 形态文本值拒绝 |
| `TEST-BQCOM-003` | required/互斥/至少一项/all-or-none |
| `TEST-BQCOM-004` | Decimal/page/size/sort 边界及无 coercion |
| `TEST-BQCOM-005` | config 只能收紧、version/snapshot canonical |
| `TEST-BQCOM-006` | catalog 不含 endpoint/SQL/ES/code/JWT/result/role |
| `TEST-BQCOM-007` | slot 同请求绑定、并发隔离、缺失/跨请求失败 |
| `TEST-BQCOM-008` | model/plan failure 时 handler/Adapter/Knowledge/另一域=0 |
| `TEST-BQCOM-009` | user/model 字段交集和默认 egress off |
| `TEST-BQCOM-010` | JWT 只进入 HTTP client，日志/模型为0 |
| `TEST-BQCOM-011` | 启动唯一性与 Resolver/ID-only Business 可达性为0 |
| `TEST-BQCOM-012` | 既有 Business handler/result/egress 回归 |

## 14. 设计决策

| ID | 决策 |
|---|---|
| `DR-BQCOM-019` | Definition 是上界，配置只收紧 |
| `DR-BQCOM-020` | QueryPlan typed union 显式区分 literal 与 protected ref |
| `DR-BQCOM-021` | Decimal 在逻辑计划中用 canonical string，wire 仍用 JSON number |
| `DR-BQCOM-022` | 不引入规则 DSL，只用有限枚举和规则元组 |
| `DR-BQCOM-023` | endpoint path/method 只在 Adapter 代码，不进模型 catalog |
| `DR-BQCOM-024` | Local Resolver 不再属于 BusinessActionDefinition 目标合同 |

## 15. 当前差距与门禁

`IMPL-BQCOM-001～005` 的公共 non-live 实现已由 `WP-BQ-PLAN-CONTRACT-01` 完成并通过定向、Business 回归、strict mypy 和 compileall。Employee/Transaction definition/config、Runtime 唯一链路和跨模块 E2E 仍由后续工作包承接；真实模型/业务 UAT 继续受独立门禁约束。

## 16. 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | QueryPlan/config/validator/binder 责任闭合 | 补齐配置 Schema、实现追踪与启动校验，修复后通过 |
| 内审2 | unsupported、slot 与 Core 隔离 | 增加 unsupported 终态 union，修复后通过 |
| 内审3 | 配置子集、快照、出域与过度设计 | 确认静态有限配置、不引入 DSL/平台，通过 |
| 独立评审 R1～R3 | L2 与跨层一致性 | 增加 payload decoder 和有限文本策略，闭合物理表达式值旁路；R3 无发现，通过 |

Approved 不表示当前配置或代码已完成本设计。

## 17. 质量、耦合、风险与实现就绪判定

QueryPlan/config/binder 形成一个高内聚 Business planning 边界，并以稳定 ActionCandidate 与 Core 解耦。新增抽象是支持模型计划、敏感引用和配置子集的最小必要集合；不引入规则 DSL 或配置平台。风险包括配置扩大、snapshot 漂移、slot 泄漏和双链路，分别由 startup subset、request binding、脱敏审计和 composition reachability 控制；回滚为禁用新 action/config，不迁移数据。

| 项目 | 内容 |
|---|---|
| 是否可作为实现依据 | 是，设计可作为后续代码实施依据，但当前未授权实施 |
| 当前允许实施范围 | 取得 P3 `GATE-064` 后，仅限 IMPL-BQCOM-001～007 的 non-live 实现 |
| 当前禁止动作 | 新业务接口/DTO/DB、扩大权限/字段、真实调用、动态 DSL、恢复 Resolver 旁路 |

## 18. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-BQCOM-001`; `CON-BQCOM-001` | `DR-BQCOM-019` | `IMPL-BQCOM-002` | `TEST-BQCOM-005` | `VAL-BQCOM-001` |
| `REQ-BQCOM-002` | `DR-BQCOM-020` | `IMPL-BQCOM-001` | `TEST-BQCOM-001` | `VAL-BQCOM-002` |
| `REQ-BQCOM-003` | `DR-BQCOM-023` | `IMPL-BQCOM-004` | `TEST-BQCOM-006` | `VAL-BQCOM-003` |
