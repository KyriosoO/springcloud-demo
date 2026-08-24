# [L1_02] 单体 Agent 业务查询与适配器架构

> 文档状态：Approved
> 文档层级：L1

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L1_02 |
| 文档层级 | L1 |
| 当前版本 | v1.2 |
| 更新日期 | 2026-08-24 |
| 上位文档 | [`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v1.3 |
| 协作文档 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v1.3 |
| 权威范围 | Business QueryPlan 公共约束、每域每动作配置、Employee/Transaction Adapter、业务 Provider、结果与模型出域 |
| 实施状态 | 两域 QueryPlan definition/config/Adapter/授权、Runtime 唯一分支、专属旧 Resolver 清理和 fake system E2E 已完成；live 尚未完成 |

## 2. 变更记录与接口核实

v1.1 将两域的目标动作解析从本地 Resolver 改为 LLM QueryPlan。v1.2 校正保留边界：冻结历史 manifest/evidence/hash 及其复验必需的兼容类型不删除，但生产 `BusinessSupportFactory` 拒绝非空 Resolver；Employee/Transaction 专属 Resolver 源码和只验证旧旁路的可执行测试，经调用方、共享组件和回归核实后删除，不作为回滚机制保留。

只读核实结果：

| 域 | 代码位置 | 可复用接口 | 结论 |
|---|---|---|---|
| Employee | `employee-service/.../EmployeeController.java` | `GET /employees/{idCardNo}` | 可用于 `employee.detail`；最终授权在服务内 |
| Employee | 同 Controller/Service | `GET /employees?page&size` | 只有分页，无 `work_base_si` 等筛选能力 |
| Employee ES | `EmployeeEsController` | `POST /employees/es/search`；含 `workBaseSi` 等白名单字段 | 当前仅 `requireUser`，未执行 `ROLE_ADMIN/ROLE_VIEWER` 最终读取授权；请求为通用动态 DTO、响应为原始 ES 字符串，不纳入本期 |
| Transaction | `mq-procedure-service/.../TransactionController.java` | `POST /txn/search` | 可用于受限 `transaction.search`；最终授权在服务内 |

因此 Employee 首期只支持 detail。“帮我查看上海的员工”应由模型形成 Employee 搜索意图后在本地配置校验阶段返回 `unsupported`，不得调用列表或通用 ES；这表示现有端点暂不满足安全与契约复用条件，而不是断言服务没有搜索实现。

## 3. 目标、范围与非目标

### 3.1 目标

- 让 LLM 基于模型安全动作目录生成一个 Business QueryPlan；
- 用代码绑定 definition 与每动作配置把计划收紧到既有接口；
- 让 Adapter 只执行已验证计划，不理解自然语言；
- 业务服务继续拥有最终授权、业务规则和物理查询；
- 保持 Employee/Transaction 相互隔离且无 Knowledge 回退。

### 3.2 非目标

- 新增 Employee search、Transaction Date/aggregate/detail/write；
- 动态 endpoint、通用 DSL、工具反射或数据库直连；
- 本地 Resolver fallback、跨域切换、计划自动修复；
- 在 Agent 中维护业务角色或复刻业务查询引擎。

### 3.3 上位约束映射

| L0 约束 | 本模块落实 |
|---|---|
| `SA-C-005～007` | QueryPlan 不可信、配置只收紧 |
| `SA-C-008～010` | 敏感值 slot、无降级/切域/Knowledge 回退 |
| `SA-C-011/012` | Adapter 不直连数据源，物理实现归业务服务 |
| `SA-C-014` | Adapter 已实现不等于 QueryPlan 目标已实现 |

## 4. 主要链路

```text
minimized question + protected slots
  → LLM Business QueryPlan {domain, action, arguments}
  → Business plan exact decoder
  → code definition ∩ action config validator
  → protected value binder
  → existing domain argument validator
  → agent-core single action
  → exact domain Adapter
  → existing business endpoint
  → business final authorization
  → SQL/ES selected and executed by business service
  → strict result decode / user projection
```

本域架构不得向 Runtime 提供以下替代入口：本地问题 Resolver、ID-only selector 参数补全、模型失败本地查询、Business→Knowledge fallback、Employee↔Transaction fallback。

## 5. 模块核心职责与公共责任边界

| 组件 | 负责 | 不负责 |
|---|---|---|
| Business Definition Registry | 代码绑定 domain/action/field/operator/result 上界 | 动态配置扩大能力 |
| Business Query Config | 每动作启用、字段描述/类型/规则、边界和 snapshot | endpoint/SQL/角色/新字段 |
| QueryPlan Validator | exact domain/action/argument、配置子集、组合规则 | 猜值、修补、业务调用 |
| Protected Value Binder | 同请求 `value_ref` 解析 | 从文本提取业务条件、跨请求查值 |
| Domain Handler | 调用唯一 Adapter、统一结果/出域处理 | 切域或调用 Knowledge |
| Adapter | 固定协议 codec、JWT、timeout/cancel、严格响应 | 授权、DB/ES、LLM |
| Business service | 最终授权、查询规则、物理执行 | Agent 计划和出域策略 |

## 6. QueryPlan 公共契约

```json
{
  "domain": "employee",
  "action": "employee.detail",
  "arguments": {
    "employee_identifier": {"value_ref": "slot-1"}
  }
}
```

```json
{
  "domain": "transaction",
  "action": "transaction.search",
  "arguments": {
    "trans_type": {"literal": "PAYMENT"},
    "amount_gt": {"literal": "100.00"},
    "size": {"literal": 20}
  }
}
```

说明：

- 例子仅说明逻辑形态；实际允许键以当前动作配置快照为准。
- literal 的 JSON 外层采用 tagged union，避免裸值的类型歧义；Decimal literal 是 canonical decimal string，仅存在于 QueryPlan 内部，Adapter 发往 Java 时编码为 JSON number。
- `value_ref` 只能引用同一请求 Guard 建立的 slot；模型看不到原值。
- 顶层和每个 value object 均 exact，禁止额外字段、null、混合 literal/ref 或物理查询字段。

## 7. 每域每动作强类型配置

### 7.1 配置单元

```text
BusinessActionConfig
  domain_id
  action_id
  enabled
  config_version
  code_contract_version
  service_contract_ref
  snapshot_id
  fields[]
    logical_name
    model_safe_description
    value_type
    allowed_operators
    input_exposure: literal | protected_ref
    required/optional
  combination_rules
  decimal_limits
  paging_limits
  sort_limits
  user_result_fields
  model_visible_result_fields
```

endpoint、HTTP 方法和物理字段映射属于 Adapter 代码 definition，不进入可编辑配置或模型 catalog。

### 7.2 只收紧规则

启动时计算：

```text
effective action = code-bound action ∩ enabled config
effective input = code field/type/operator/limit ∩ config rule
effective user result = code projection ∩ config result fields
effective model result = code model fields ∩ config model fields ∩ classification policy
```

配置出现未知动作/字段/operator、扩大数值/分页边界、增加返回/模型字段或契约版本不匹配时启动失败。

### 7.3 快照与请求一致性

- 配置加载后规范化并计算 snapshot ID；
- readiness 前校验 Registry/handler/Adapter 唯一绑定；
- 请求开始固定 snapshot，计划、候选、日志和测试证据引用同一 ID；
- 本期只支持重启加载，不建设热更新平台。

## 8. 动作目录

| domain/action | QueryPlan 输入 | 固定 Adapter/endpoint | 用户结果 | 模型结果 | 明确排除 |
|---|---|---|---|---|---|
| `employee/employee.detail` | 一个 `employee_identifier` protected ref | Employee Adapter → `GET /employees/{idCardNo}` | 既有六字段受控投影 | 默认关闭；启用时最多 `position/work_base_si` | 列表筛选、ES、写入 |
| `transaction/transaction.search` | 有限条件、Decimal、size/sorts | Transaction Adapter → `POST /txn/search` | 受控 rows/total/page | 默认关闭；启用时最多 `transaction_type/amount` | Date、聚合、detail、写入 |

## 9. 身份与最终授权

1. Runtime 接收已认证用户 JWT，不解析为 Agent 业务权限。
2. 规划模型不接收 JWT、角色或 service token。
3. Adapter 只透传用户 JWT，不在 Agent 侧判断 `ADMIN/VIEWER`。
4. Employee/Transaction 服务的 Authority Converter 和 guard 作最终授权。
5. `401/403` 保持区分，不得因模型或 Adapter 映射变成 `no_result`。
6. service token、missing/malformed/unknown role 的拒绝场景由业务集成测试验证。

## 10. 结果、答案与模型出域

结果按三种视图分离：业务原始响应、用户投影、可选模型 facts。原始响应只在 Adapter 解码期间驻留；用户投影按代码和配置取交集；模型 facts 再与数据分类策略取交集。

规划调用发生在业务请求之前且不包含结果；答案调用发生在成功结果之后且默认关闭。两次调用使用不同 task/version/schema，调用计数分别记录。模型不得根据结果改写 domain/action 或触发第二次业务查询。

## 11. 失败语义

| 场景 | 状态 | model plan / Adapter / business 调用 |
|---|---|---|
| 输入策略前置拒绝 | `forbidden/unsupported` | 0 / 0 / 0 |
| 模型失败/超时 | `downstream_failure/timeout` | 1 / 0 / 0 |
| QueryPlan JSON/Schema/引用非法 | `invalid_argument` | 1 / 0 / 0 |
| 未开放 domain/action/field/operator | `unsupported` | 1 / 0 / 0 |
| Adapter 参数或 codec 失败 | `invalid_argument/downstream_failure` | 1 / 1 内部尝试 / 0或1 |
| 业务拒绝 | `forbidden` | 1 / 1 / 1 |
| 无结果 | `no_result` | 1 / 1 / 1 |

这里的 model plan 调用数表示目标成功/语义失败路径；认证和严格 JSON 可在模型前结束。任何失败都不得触发另一个业务域、Knowledge 或本地 Resolver。

## 12. Employee 接口缺口

`POST /employees/es/search` 能表达 `workBaseSi`、position 等筛选，但当前安全链只要求已认证用户，未调用 `requireEmployeeRead`，且其通用 `SearchRequest` 可承载 keyword/filter/sort/aggregate、响应为原始 ES 字符串。它不满足“业务域最终角色授权 + 受限稳定跨语言契约”的复用前提。配置不得声明 `employee.search`，也不得把分页列表或该通用 ES 搜索伪装为受控动作。若要支持，需要用户另行决定并授权：收紧 endpoint-scoped 授权、固定受限 request/response 契约、调用方兼容性回归、Adapter 契约以及上位需求和 UAT 修订；本轮不得通过下位配置补偿。

## 13. 可观测性与可靠性

记录 correlation、snapshot、验证后的 domain/action、planning/validation/adapter 阶段、有限 reason、模型与下游计数、耗时和截断；禁止记录问题原文、slot 值、JWT、QueryPlan 原文、业务原始响应和模型原始响应。

本期只实现 timeout/deadline/cancel/client lifecycle。不得以 retry、熔断或降级恢复被禁止的替代链路。

## 14. 同层协作边界与下位 L2 详细设计交付约束

| L2 | 权威内容 |
|---|---|
| [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | 公共 QueryPlan 类型、配置 Schema、validator/binder、投影/出域 |
| [`L2_02_01`](L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | Employee detail 定义、protected ref、codec、接口缺口、授权验证 |
| [`L2_02_02`](L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | Transaction search 定义、Decimal、分页/排序、codec、授权验证 |

`L2_00_01` 拥有 QueryPlan→ActionCandidate 的图/Core 接缝；`L2_00_02` 拥有模型任务和 provider response→`JsonObject` 的 exact JSON decode；`L2_02_00` 拥有 `JsonObject`→`BusinessQueryPlan` 的 exact 三字段/tagged-value decode 与业务校验。Business L2 不修改公共 Core/HTTP。

## 15. 当前差距与实施顺序

1. 公共合同、模型 task、两域 definition/config、Runtime 唯一分支和专属 Resolver 清理已完成；
2. Spring→Runtime→fake model→fake domain 的双域 non-live 负向/组合根验证已完成；
3. 经单独精确授权执行真实模型 + 真实业务服务集成与 UAT。

当前 non-live system E2E 可以证明 fake 边界下的唯一链路，但不能证明真实 LLM、业务服务或 UAT 已完成。

## 16. 风险与关键架构决策

| ID | 决策/风险控制 |
|---|---|
| `BQ-AD-001` | LLM 生成完整逻辑 QueryPlan，本地不得补充语义参数 |
| `BQ-AD-002` | slot/binder 只保护并恢复值，不决定查询含义 |
| `BQ-AD-003` | 每动作配置只收紧代码与服务契约，endpoint 不模型可见 |
| `BQ-AD-004` | Employee 通用筛选端点未满足最终角色授权与受限响应契约，统一 `unsupported` |
| `BQ-AD-005` | 两域和 Knowledge 之间无失败回退 |
| `BQ-AD-006` | 结果模型出域与强制规划调用分离且默认关闭 |

## 17. 验证与评审

### 17.1 必须验证

- 两个 action 的 config subset/snapshot/readiness；
- QueryPlan exact schema、字段/operator/组合和引用；
- 模型失败、非法计划、Employee 筛选缺口下游零调用；
- Employee/Transaction 仅固定 endpoint；
- JWT 透传、最终授权和 `401/403/no_result` 保真；
- Decimal、分页、排序和字段投影；
- 无 Resolver、ID-only 补参、切域或 Knowledge 回退生产路径。

### 17.2 v1.1 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | 两域职责、配置、Adapter 与跨语言合同 | 补齐接口/配置/追踪，修复后通过 |
| 内审2 | unsupported、业务最终授权与失败关闭 | 闭合 unsupported 与 `401/403/no_result` 边界，修复后通过 |
| 内审3 | 只读接口复核、能力扩张与 DAG | 核实 Employee ES 字段能力及授权/响应缺口；保持不纳入，修复后通过 |
| 独立评审 R1～R3 | 分层与跨层一致性 | provider/payload decoder、Employee ES 复用条件及 unsupported 上位合同均闭合；R3 无发现，通过 |
| v1.2 内审1 | Adapter/Resolver 职责 | 专属 Resolver 源码/旧旁路测试删除，不触及 Adapter/服务合同 | 修复后通过 |
| v1.2 内审2 | 历史 manifest 与兼容调用 | 冻结 harness 所需字段保留，生产 support 禁止非空 Resolver | 修复后通过 |
| v1.2 内审3 | 两域隔离、版本与 DAG | 无跨域/Knowledge 回退，无新 API/DTO/DB/权限 | 通过 |
| v1.2 独立评审 R1～R3 | 两域清理、历史证据与接口边界 | 修正兼容字段与 launcher 范围后，R3 无发现 | 通过 |

评审通过不代表 QueryPlan 代码或 UAT 已完成。

## 18. 结论

Business 架构以两个已确认现有接口为硬上界，以 LLM QueryPlan 为唯一语义计划来源，以本地配置/validator/binder 和业务服务最终授权保证确定性。接口不能表达的需求明确拒绝，等待新授权，不通过 Adapter 或配置绕过。
