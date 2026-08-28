# [L2_02_00] 单体 Agent Business filters QueryPlan、字段配置与出域详细设计

> 文档状态：Approved

## 1. 文档信息、上位约束与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.7 |
| 更新时间 | 2026-08-28 |
| 上位约束来源 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v2.7 |
| 关联责任边界 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md)；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md)；Employee/Transaction L2 |
| 归档来源 | [v1.8 已评审旧版](历史文档/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN_v1.8.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。v2.7 设计 `value_refs`、`prefix_any/contains_any`、有限同字段 Text 组合和版本化行政区规范化；v2 配置和历史 evidence 保持不可变。

## 2. 设计目标、范围外与当前实现基线

设计目标是让 Business 公共层统一承担 provider-neutral QueryPlan、field/operator/slot、配置 snapshot、启动一致性、JWT 透传、结果投影和可选模型出域。范围外包括问题语义本地生成、provider transport、Core 执行规则、业务 SQL/ES、业务最终授权、新 endpoint/DTO 和真实模型调用。

当前实现：`agent-runtime/src/agent_runtime/business/query_plan.py` 已实现 filters/operator/tagged value、同字段组合与严格 decoder；统一三动作版本化 JSON、strict settings/snapshot、protected slots、有限字段映射、projection 和目标生产组合根已通过 non-live、真实 controlled、18 个真实 UAT 场景及 17 个等价自动化风险验证。公共 validator 依据 operator 区分 `trans_type eq` 安全 token 与 `contains` 防 LIKE 通配策略；当前 Employee 配置、实际定义和模型目录均无 workBase，未配置字段依靠通用白名单自然失败关闭。Employee 业务最终授权和 SQL 实现仍不是公共层责任。

| 需求编号 | 需求 |
|---|---|
| `REQ-BQCOM-101` | exact filters QueryPlan 和同字段 operator 组合 |
| `REQ-BQCOM-102` | 统一字段级配置、严格收紧与不可变 snapshot |
| `REQ-BQCOM-103` | 受保护输入、JWT 透传、结果分类和模型出域独立 |
| `REQ-BQCOM-104` | 非法计划、语义+结构缺口、日期/金额越界失败关闭 |

| 约束编号 | 上位约束 |
|---|---|
| `CON-BQCOM-101` | domain/action/field/operator 不得超过现有业务接口和代码定义 |
| `CON-BQCOM-102` | Agent 不直接访问业务数据库或 ES，不替代业务最终授权 |

## 3. 模块职责、依赖方向与接口契约设计

Model provider decoder 只负责 JSON framing；公共 Business decoder 负责 `JsonObject → BusinessQueryPlan` exact payload；validator 负责代码 definition、配置 snapshot、日期/Decimal、operator value shape 与字段组合；binder 只把同请求 `value_ref/value_refs` 转换为不可变 Adapter 输入。依赖方向固定 Model → Business decode/validate/bind → Core → Domain Adapter；禁止绕过或反向依赖。

现有关键接缝为 `ExactBusinessQueryPlanDecoder.decode(payload: JsonObject) -> BusinessQueryPlan`、`DefaultBusinessQueryPlanValidator.validate(plan, *, snapshot) -> BusinessQueryPlanValidationResult`、`RequestProtectedValueBinder.bind(plan, *, slots, request_id) -> ActionCandidate` 和 `build_business_planner_catalog(...) -> BusinessPlannerCatalog`。不可变 `BusinessQueryFilter(field, operator, value)`、`BusinessListQueryArguments(filters, page, size, sorts, keyword)` 与 `EmployeeSemanticQueryArguments(query, size)` 等业务合同均已实施；历史 flat arguments 不满足且不得替代本设计。

### 3.1 统一计划外层与列表 arguments

```json
{
  "domain": "employee",
  "action": "employee.search",
  "arguments": {
    "filters": [
      {"field": "contact_address", "operator": "contains", "value": {"literal": "上海"}}
    ],
    "page": 1,
    "size": 20,
    "sorts": []
  }
}
```

```json
{
  "domain": "transaction",
  "action": "transaction.search",
  "arguments": {
    "filters": [
      {"field": "trans_type", "operator": "contains", "value": {"literal": "PAY"}},
      {"field": "amount", "operator": "gt", "value": {"literal": "100.00"}},
      {"field": "amount", "operator": "lt", "value": {"literal": "500.00"}}
    ],
    "page": 2,
    "size": 20,
    "sorts": [{"field": "trans_date", "direction": "DESC"}]
  }
}
```

外层只能包含 `domain/action/arguments`。`employee.search` arguments 只允许 `filters/page/size/sorts` 及可选 `keyword`；标量值 exact 为 `{"literal": ...}` 或 `{"value_ref":"slot-N"}`，多值 exact 为 literal list 或 `{"value_refs":["slot-1","slot-2"]}`。真实姓名、标识和详细地址必须绑定同请求 protected slot。`transaction.search` 只允许 `filters/page/size/sorts`；`employee.semantic_search` 只允许 `query/size`。分页与排序属于计划语义，不能由本地猜测。

filter 必须 exact 包含 `field/operator/value`；sort exact 为 `field/direction`。scalar operator 只接受 scalar literal/value_ref；`in/prefix_any/contains_any` 只接受 1～16 项 literal list 或唯一 `value_refs`。请求 JSON 禁止 duplicate key、unknown property、null、bool-as-int、float、NaN/Infinity、控制字符和物理键；继承现有大小上限，filters≤8、sorts≤2、page≤1000、size≤50，且具体 action 配置可继续收紧。

同字段 Decimal/Date 允许一次 `gt` 和一次 `lt`；`eq` 与 range 互斥且上下界严格 `lower < upper`。Text 默认互斥，只有字段 code definition 与配置共同列出的无序 operator 组合可按 AND 执行；`chinese_name` 上界仅含 `prefix+contains` 与 `prefix+eq`，重复 operator 始终拒绝。Employee extractor 为每个新 slot 同时保存 typed logical field；binder 必须验证 request ID、slot唯一性和 field一致性。同一个 slot 不能在同一计划重复引用或跨请求绑定；旧历史构造的无类型单值 slot 仅保留兼容，不允许形成新 `value_refs`。`unsupported` 仅允许 action 为 `unsupported` 且 arguments 为 `{}`。

### 3.2 Employee 和 Transaction 逻辑 operator

Employee 普通搜索新增逻辑 `prefix_any/contains_any`：`in→in/equalsAny`、`prefix_any→prefixAny`、`contains_any→containsAny`，均映射既有 `SearchFilter.values`；多个 filters 由服务 `bool.must` 组合。`chinese_name` 可配置 `eq/contains/prefix/in/prefix_any`，`contact_address` 仅配置 `contains/contains_any`。Transaction operator 集合保持不变；DTO/Java alias 仅归 Adapter 所有。

文本策略由有限代码枚举及当前 filter operator 共同确定，不引入可配置表达式：普通安全 token 可包含 `_`，但 `contains` 必须收紧为不包含 `_`、`%`、反斜杠和控制字符的安全片段。`trans_type eq` 因现有 SQL 使用参数化 `=`，必须允许真实已存在的合法下划线类型；`trans_type contains` 因现有 Mapper 使用未转义 `LIKE`，必须在模型计划校验和 Adapter 两层均失败关闭。Employee 既有城市、敏感字段和 protected-ref 规则保持不变；统一配置只启用既有 operator，不能放宽代码绑定策略，也无需新增配置 schema 或规则引擎。

时间文本必须是带明确 offset 的 ISO-8601/RFC3339 timestamp，按 `Asia/Shanghai` 合同归一，且 Java/Jackson/数据库 precision 必须由 contract test 证明；相对自然日未完成时钟/精度/边界验证时 unsupported。金额 literal 为 canonical decimal string，`abs≤9999999999999999.99`、scale≤2，发往 Java 时是 JSON number；禁止 float、舍入或截断。

## 4. 统一字段级配置与 snapshot

历史 `business-query.v2.json` 和 loader 保持字节与语义不变；当前生产新增 `business-query.v3.json`，仍由同一严格 Python 解码器读取并形成不可变 snapshot。本期不新增配置平台、DSL、watcher 或生产依赖。

```json
{
  "config_version": "business-query-v2",
  "code_contract_version": "business-query-contract-v2",
  "domains": [{
    "domain": "employee",
    "actions": [{
      "action": "employee.search",
      "enabled": true,
      "service_contract_ref": "employee.es.search.v1",
      "pagination": {"max_page": 1000, "max_size": 50, "max_results": 50},
      "sorts": {"max_items": 2, "directions": ["ASC", "DESC"]},
      "keyword": {
        "enabled": true,
        "input_exposure": "literal_or_protected_ref",
        "max_text_chars": 128,
        "service_field_ids": ["contactAddress", "chineseName", "idCardNo"]
      },
      "timeout_ms": 2000,
      "fields": [{
        "logical_name": "contact_address",
        "service_field": "contactAddress",
        "model_safe_description": "员工联系地点的非敏感城市片段",
        "value_type": "text",
        "enabled": true,
        "allowed_actions": ["employee.search"],
        "allowed_operators": ["contains"],
        "input_exposure": "literal_or_protected_ref",
        "required": false,
        "max_text_chars": 128,
        "enum_values": [],
        "combination_rules": [],
        "data_class": "personal_address",
        "user_visible": true,
        "user_transform": "mask_address",
        "model_visible": false,
        "model_transform": "deny",
        "sortable": false,
        "result_required": false,
        "code_contract_version": "employee.es.search.v1",
        "service_contract_ref": "employee.es.search.v1"
      }]
    }]
  }]
}
```

示例只展示形状。v3 配置新增有限 `operator_combinations` 与 `normalization_profile`，两者必须是代码 definition 的子集；不得携带正则或表达式。`service_field` 只能与 Adapter 代码绑定映射逐字相同，用于启动对齐且绝不进入模型目录。Employee keyword、endpoint、HTTP method 和 semantic profile 仍由既有代码边界控制。

输入 exposure 有限枚举保持不变；`value_refs` 是 protected_ref 的多值形状，不新增暴露类别。`contact_address` literal 只可通过版本化 code-bound 行政区目录规范化；配置只能选择该 profile，不能注入别名、正则或放宽判定。详细地址仍必须 protected ref。用户/模型 transform 为有限代码枚举，不能运行表达式。

超时按 action 的真实业务链路分别绑定：`employee.search≤3000ms`、`employee.semantic_search≤10000ms`、`transaction.search≤5000ms`。语义动作包含业务服务内本地 Embedding、Feign 转发及 ES 向量检索，不能机械复用普通 Employee 搜索的 3000ms 上限；10000ms 只调整该 action 的代码合同和受限配置，不扩张 endpoint、查询字段、结果字段、权限或模型调用。实际 deadline 仍取请求剩余时间与 action 配置的较小值，超时失败关闭，不重试、不降级。配置 snapshot 发生变化时启用全新的 live manifest；此前 manifest 和失败证据保持原始字节及哈希不变。

启动校验：exact JSON、版本、duplicate、动作/字段/operator 子集、code/service contract、逻辑字段与 `service_field` 固定映射、keyword 三字段及 protected exposure 对齐、descriptor/definition/config/validator/mapper/codec 完整对齐、result/model 字段子集和大小/timeout 上限；未出现在 Agent 代码定义和启用配置中的字段通过通用字段子集校验自然不可用，无需针对 `workBaseSi/workBaseAf` 增加专用黑名单、启动校验或输入分支。snapshot 使用 canonical JSON SHA-256，不可变地绑定单请求；不一致 readiness 失败，不得加载旧 Resolver。

## 5. 处理流程、权限与审计设计

1. request-local extractor 将单/复姓、姓名片段、完整姓名、标识、会员号、电话、邮箱和详细地址分别替换成 slot，保留原词序与连接词，但不生成业务计划。
2. 模型只见 minimized question、operator 语义/形状、字段组合、行政区 literal、slot ID、已批准时间上下文与 snapshot。
3. provider decoder 后执行 Business exact decoder、配置 validator、行政区规范化和 protected binder；规范化不选择字段或 operator。
4. Core 执行一次固定 Domain Adapter；client 仅透传原用户 JWT。
5. Adapter 严格解析服务返回；Employee 仅按其域内合同隔离缺失必填结果字段的历史索引记录，保留真实 total、有效 returned count 和 truncated 语义；user projection 和 model egress 分别执行代码/配置/分类交集。

用户读取权限不等于模型出域许可。未知字段、embedding、embeddingText、workBase、JWT、详细地址、姓名、标识、联系方式和原始业务响应不得进入模型。Transaction 默认模型字段仍最多 `trans_type/amount`；Employee 默认最多安全 `position`，绝不恢复 workBase 模型字段。结果模型调用不是列表查询必需步骤，默认关闭。

错误分类：`unsupported`、`invalid_argument`、`unauthenticated`、`forbidden`、`timeout`、`unavailable`、`invalid_response`、`internal_failure`；计划/配置/模型前置失败业务调用为 0，服务拒绝只允许既定一次调用。审计仅保留有限 action、snapshot、状态与计数，不输出问题、JWT、slot、数据库凭据、完整 plan 或原始响应。

## 6. 实现落点清单

| 实现编号 | 位置 | 责任 |
|---|---|---|
| `IMPL-BQCOM-101` | `agent-runtime/src/agent_runtime/business/query_plan.py` | filters/operator/tagged value 精确类型、decoder、validator、binder |
| `IMPL-BQCOM-102` | `agent-runtime/src/agent_runtime/business/contracts.py` | code-bound action、field、operator、classification、分页和时间合同 |
| `IMPL-BQCOM-103` | `agent-runtime/src/agent_runtime/business/settings.py` | 统一配置读取、subset 校验、canonical snapshot 和 readiness |
| `IMPL-BQCOM-104` | `agent-runtime/src/agent_runtime/business/business-query.v2.json` | 已实施：三动作单文件、版本化、默认拒绝的字段与结果配置 |
| `IMPL-BQCOM-105` | `agent-runtime/src/agent_runtime/business/planner_catalog.py` | 生成仅含逻辑字段的安全目录 |
| `IMPL-BQCOM-106` | `agent-runtime/src/agent_runtime/business/protected_input.py` | 请求级 slots 和地点片段/详细地址差异化保护 |
| `IMPL-BQCOM-107` | `agent-runtime/src/agent_runtime/business/user_projection.py` | 用户结果字段白名单与有限脱敏 |
| `IMPL-BQCOM-108` | `agent-runtime/src/agent_runtime/business/egress.py` | 模型字段交集、未知/敏感/冲突零调用 |
| `IMPL-BQCOM-109` | `agent-runtime/src/agent_runtime/business/business-query.v3.json` | 当前三动作配置、Employee 多值 operator、组合与行政区 profile；v2 保持历史兼容 |
| `IMPL-BQCOM-110` | `agent-runtime/src/agent_runtime/business/region_catalog.py` | 版本化省/市/自治区有限别名目录和确定性规范化 |

## 7. 测试与验证设计

| 测试编号 | 重点 |
|---|---|
| `TEST-BQCOM-101` | exact 三字段/filter/tagged union、重复键、unknown、float、集合/深度上限 |
| `TEST-BQCOM-102` | 同字段 gt+lt、eq/range 互斥、上下界、Employee operator 和 semantic+filter 拒绝；同一 Transaction 类型字段 `eq` 允许 `_` 而 `contains` 拒绝 `_/%/反斜杠` 并保持零调用 |
| `TEST-BQCOM-103` | config version/hash/subset、三动作 alignment、keyword 三字段和 protected exposure 对齐、未配置字段由通用 subset/白名单校验拒绝 |
| `TEST-BQCOM-104` | 同请求 slot、跨请求/重复 slot 拒绝，详细地址与上海片段边界，keyword tagged union 与敏感 keyword 零泄漏 |
| `TEST-BQCOM-105` | Date offset/timezone、相对日期 unsupported、Decimal canonical/scale≤2/JSON number |
| `TEST-BQCOM-106` | page/size/sorts/offset overflow、投影脱敏、模型出域拒绝与调用计数 |
| `TEST-BQCOM-107` | 三动作独立超时上限、semantic 10000ms contract/config 对齐、超界配置拒绝及历史 snapshot/manifest 不可变 |
| `TEST-BQCOM-108` | 上游 total、合法 raw hits 数量与有效返回记录数分离；eq 保留真实 total、gte 不公开精确 total；partial coverage 不伪造计数，全部命中不可投影时失败关闭 |
| `TEST-BQCOM-109` | `value_refs` 1～16、唯一/current-request 绑定、operator-specific shape 和零敏感出域 |
| `TEST-BQCOM-110` | `prefix+contains/prefix+eq` 允许，其余 Text 组合拒绝；行政区别名/未知值/多值规范化 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-BQCOM-101` | Business query/config/slot 定向单测和 strict JSON contract tests |
| `VAL-BQCOM-102` | Employee/Transaction fake adapters、零调用矩阵和用户/模型投影测试 |
| `VAL-BQCOM-103` | Business/Core/Knowledge 非 live 回归、strict mypy、compileall |

## 8. 设计规则、数据生命周期与迁移回滚

| 规则编号 | 设计规则 |
|---|---|
| `DR-BQCOM-101` | filters 列表与逻辑 operator 独立，exact decode 支持同字段开区间；文本策略必须以字段及 operator 共同确定，`eq` 安全 token 与 `contains` 防 LIKE 通配约束不得混用 |
| `DR-BQCOM-102` | 单一字段级 JSON 配置只能收紧 code/service contract，snapshot 不可变 |
| `DR-BQCOM-103` | protected ref 绑定在 validator 后、Core 前，仅限当前 request |
| `DR-BQCOM-104` | 用户结果与模型出域分别投影和脱敏；未配置、未知及敏感字段由通用白名单默认拒绝 |
| `DR-BQCOM-105` | Decimal/Date/分页/排序使用跨语言严格合同，失败关闭 |
| `DR-BQCOM-106` | 配置不携带 SQL/ES/endpoint，禁止 Agent DB/ES 依赖与权限替代 |
| `DR-BQCOM-107` | action 超时仅可由代码绑定合同及配置收紧：Employee search 3000ms、semantic 10000ms、Transaction 5000ms；保持请求 deadline、失败关闭及历史 snapshot 不可变 |
| `DR-BQCOM-108` | Domain Adapter 保留已证明的上游 total 与有效记录 coverage；只允许域合同明确的结果卫生，不得构造用户条件过滤、补请求、伪造 total 或放宽响应外壳/安全校验 |
| `DR-BQCOM-109` | `value_refs` 只服务多值 operator，1～16、唯一且 current-request；每个 slot 的 typed logical field 必须匹配 filter，绑定后为不可变字符串 tuple，真实值不出域 |
| `DR-BQCOM-110` | Text 同字段组合默认拒绝，仅允许 code/config 双重批准的收紧型 AND；不得合并、丢弃或改写 filter |
| `DR-BQCOM-111` | 行政区别名只在模型已选择 `contact_address` 后确定性规范化；目录代码绑定且配置只能选择/收紧，未知值失败关闭 |

数据生命周期：slots、JWT、plan、原始业务响应只存在于 request memory；不存在 Agent 数据库或数据迁移。事务边界与一致性由业务服务拥有；启动 snapshot 只读、无热更新。最小必要变更复用现有 query_plan/settings/projection/egress，不引入配置中心、通用规则 DSL、模板表达式或额外生产依赖，以避免耦合。

## 9. 风险、评审记录与实施就绪判定

主要风险：敏感地址误当城市 literal、组合条件被丢弃、配置扩大字段、Date precision 不明、`trans_type eq` 被错误套用 contains 限制或 contains 通配符导致查询扩大、旧 detail/flat arguments 被误认为新目标。以 code-bound operator policies、strict decode、subset 启动校验、fake 零调用和业务最终授权控制；历史 UAT 失败证据由 UAT_00/evidence 保持不可变。

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计通过且获得实施授权后 |
| 当前实施状态 | QueryPlan/config/catalog/slot/projection、三动作 non-live/live/UAT 与跨语言合同验证已完成 |
| 当前允许实施范围 | 已实施合同的缺陷修复、配置收紧和 non-live 回归 |
| 当前禁止动作 | 新增业务接口、权限扩权、放宽敏感/结果边界或允许 Agent 直接访问业务数据库/ES |

评审记录：当前大版本已通过独立分层与跨层评审；不继承旧版本评审过程。

## 10. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-BQCOM-101`; `CON-BQCOM-101` | `DR-BQCOM-101` | `IMPL-BQCOM-101` | `TEST-BQCOM-101`; `TEST-BQCOM-102` | `VAL-BQCOM-101` |
| `REQ-BQCOM-102` | `DR-BQCOM-102` | `IMPL-BQCOM-102`; `IMPL-BQCOM-103`; `IMPL-BQCOM-104`; `IMPL-BQCOM-105` | `TEST-BQCOM-103` | `VAL-BQCOM-101` |
| `REQ-BQCOM-103` | `DR-BQCOM-103` | `IMPL-BQCOM-106` | `TEST-BQCOM-104` | `VAL-BQCOM-102` |
| `REQ-BQCOM-103` | `DR-BQCOM-104` | `IMPL-BQCOM-107`; `IMPL-BQCOM-108` | `TEST-BQCOM-106` | `VAL-BQCOM-102` |
| `REQ-BQCOM-104` | `DR-BQCOM-105` | `IMPL-BQCOM-101`; `IMPL-BQCOM-103` | `TEST-BQCOM-105`; `TEST-BQCOM-106` | `VAL-BQCOM-103` |
| `CON-BQCOM-102` | `DR-BQCOM-106` | `IMPL-BQCOM-102`; `IMPL-BQCOM-105` | `TEST-BQCOM-103` | `VAL-BQCOM-103` |
| `REQ-BQCOM-102`; `REQ-BQCOM-104` | `DR-BQCOM-107` | `IMPL-BQCOM-102`; `IMPL-BQCOM-103`; `IMPL-BQCOM-104` | `TEST-BQCOM-103`; `TEST-BQCOM-107` | `VAL-BQCOM-101`; `VAL-BQCOM-103` |
| `REQ-BQCOM-103`; `CON-BQCOM-102` | `DR-BQCOM-108` | `IMPL-BQCOM-107` | `TEST-BQCOM-106`; `TEST-BQCOM-108` | `VAL-BQCOM-102` |
