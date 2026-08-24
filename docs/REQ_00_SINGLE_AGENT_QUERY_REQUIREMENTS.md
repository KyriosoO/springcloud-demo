# [REQ_00] 单体 Agent 查询能力建设需求说明

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | REQ_00 |
| 当前版本 | v1.4 |
| 状态 | 已确认 |
| 更新日期 | 2026-08-24 |
| 需求来源 | 用户确认的单体 Agent、知识查询、Employee/Transaction 结构化查询及 LLM QueryPlan 唯一链路 |
| 适用阶段 | P1～UAT |

## 2. 背景与目标

本项目是个人研发项目，用于学习、验证 Agent 技术与架构，并以“架构完整、链路打通、能力可验证”为优先，不追求生产级规模和复杂交接流程。

本期建立一个单体 Agent，提供已有知识库查询、Employee 域有限只读查询和 Transaction 域有限只读查询，并建立查询、权限、模型出域和失败语义的最小可靠约束。

Employee/Transaction 的目标不是让模型生成 SQL 或任意工具调用，而是让模型在业务服务既有只读契约之内生成一个受限逻辑查询计划，再由本地确定性校验和 Adapter 执行。

## 3. 当前事实与目标差距

### 3.1 已确认的业务接口基线

| 域 | 可复用只读接口 | 本期动作 | 已确认边界 |
|---|---|---|---|
| Employee | `GET /employees/{idCardNo}` | `employee.detail` | 仅按单一员工标识查询详情；业务服务最终授权 |
| Transaction | `POST /txn/search` | `transaction.search` | 复用现有 search；Agent 仅开放有限条件、精确金额、有限分页与排序 |

Employee 现有分页接口只接受 `page/size`。`POST /employees/es/search` 虽在服务内支持 `workBaseSi` 等字段，但当前只执行用户令牌校验、没有落实本需求要求的 `ROLE_ADMIN/ROLE_VIEWER` 业务域最终读取授权，并复用通用动态搜索 DTO、返回原始 ES 字符串；因此它尚不构成可供 Agent 复用的受限业务动作。“查看上海的员工”等筛选需求当前必须返回 `unsupported`，不得自行新增接口、借用宽泛接口或绕过业务域最终授权。

### 3.2 当前实现差距

当前代码仍以本地 Resolver 生成 Employee/Transaction 执行参数，并由模型只选择 capability ID。该实现是只读历史现状，不符合本版本目标。以下能力均尚未实现，不得标记为已完成：

- LLM 同时判定 `domain`、`action` 并生成 `arguments`；
- Employee/Transaction 共用的严格 `QueryPlan` 契约；
- 生产组合根对业务本地 Resolver 的切断；
- 按域、按动作的完整查询字段配置与启动快照一致性校验；
- 基于真实 LLM QueryPlan 的 Employee/Transaction UAT。

## 4. 范围

### 4.1 本期范围

- 单次请求、单动作、只读查询；
- `knowledge.query`、`employee.detail`、`transaction.search`；
- LangGraph 作为唯一 Agent 编排权威；
- Spring 接入治理、JWT 透传、业务服务最终授权；
- LLM 生成 Employee/Transaction 逻辑 QueryPlan；
- 本地强类型配置、严格校验、Adapter 与统一失败语义；
- 最小日志、测试和 UAT 证据。

### 4.2 非本期范围

- 聚合查询、跨域查询、自动切换业务域；
- 工作流、写入、审批、状态变更；
- Multi-Agent 实现；
- Agent/Adapter 直连数据库或业务域 ES；
- 新增业务接口、公共 DTO、数据库结构或扩大业务授权；
- 模型生成 SQL、ES DSL、URL、索引名、类名、方法名或物理调用信息；
- 文档录入和知识库治理平台。

## 5. 功能需求

### FR-01 单体 Agent 与单动作

1. 每个请求由 LangGraph 维护唯一请求级状态。
2. 每个请求最多执行一个已注册、启用且校验通过的动作。
3. Spring、Core、Adapter 和业务服务不得建立第二套 Agent 编排状态机。
4. 第二动作、跨域重试和 Business→Knowledge 回退必须被拒绝。

### FR-02 Knowledge 查询

Knowledge 继续使用既有独立链路，包含问题改写、多域、多路召回与重排、证据选择和答案摘要。Knowledge 不是 Business 查询失败后的回退路径，本次修订不改变其检索与证据契约。

### FR-03 Employee 查询

1. 首期仅开放 `employee.detail`。
2. QueryPlan 必须以受保护值引用表达员工标识，原始身份证号、员工编号等具体标识不得发送给模型。
3. 本地绑定器只能把 QueryPlan 中已验证的引用绑定回同一请求内存中的值。
4. Adapter 固定调用 `GET /employees/{idCardNo}`，不得调用列表、ES 搜索或写接口。
5. `work_base_si`、职位等筛选当前不受支持；模型提出此类计划时本地返回 `unsupported`，业务调用为零。

### FR-04 Transaction 查询

1. 首期仅开放 `transaction.search`。
2. 允许条件限于既有代码和配置共同开放的 `trans_id`、`trans_type`、`trans_type_contains`、`amount`、`amount_gt`、`amount_lt`，以及有限 `size/sorts`。
3. 金额使用精确 Decimal；禁止 float、舍入、字符串金额 wire 和隐式 scale 转换。
4. 首期排除 Date、聚合、detail、写入和管理动作。
5. Adapter 固定调用 `POST /txn/search`，业务服务自行决定 SQL/ES 等物理实现。

### FR-05 Employee/Transaction 唯一 QueryPlan 链路

对通过接入认证、严格 JSON 和敏感输入闸门的 Employee/Transaction 问题，唯一业务查询链路为：

```text
用户问题
  → LLM 生成 {domain, action, arguments} 受限 QueryPlan
  → 本地按代码契约和强类型配置严格校验与受保护值绑定
  → 对应 Employee/Transaction Adapter
  → employee-service 或 mq-procedure-service
  → 业务服务最终授权并执行 SQL/ES 查询
  → 返回结果
```

约束：

- LLM 必须参与目标域、动作和逻辑参数的生成；本地代码不得绕过 LLM 生成完整执行参数。
- 模型失败、超时、拒绝或计划非法时失败关闭，不得降级为本地查询。
- 一个业务域失败后不得自动切换到另一业务域。
- 模型只接触逻辑字段、有限运算符和模型安全描述，不接触固定 endpoint、SQL/ES、代码符号、JWT 或原始业务响应。

### FR-06 Adapter

每个业务域使用独立 Adapter。Adapter 负责：

- 把已验证的逻辑参数编码为既有业务接口请求；
- 透传当前用户 JWT；
- 设置超时、处理取消、严格解码和归一失败；
- 执行允许返回字段投影。

Adapter 不负责问题理解、QueryPlan 生成、角色判定、SQL/DSL 生成、数据库访问或新业务规则。

### FR-07 结果与可选答案生成

业务查询结果默认在本地形成确定性回答。若显式启用模型答案生成，模型可见字段必须满足“代码允许 ∩ 配置允许 ∩ 数据分类允许”，且调用发生在业务查询成功之后。答案模型调用不是 QueryPlan 的替代，也不得改变业务结果状态。

## 6. QueryPlan 与强类型配置需求

### CFG-01 QueryPlan 外形

业务 QueryPlan 仅允许以下顶层结构。可执行计划为：

```json
{
  "domain": "employee|transaction",
  "action": "employee.detail|transaction.search",
  "arguments": {}
}
```

不可表达或未开放的意图只能使用同一三字段外形的保留终态：

```json
{
  "domain": "employee|transaction|unsupported",
  "action": "unsupported",
  "arguments": {}
}
```

`unsupported` 不是可执行 action；它必须在本地校验阶段终止，不能进入 binder、Core 或 Adapter。已知业务域但动作/字段未开放时可保留对应 domain；无法识别为两个业务域时 domain 必须为保留值 `unsupported`。

- exact JSON：禁止额外顶层字段、重复键、非有限数和超限嵌套；
- 每次只能包含一个 domain、一个 action 和一组 arguments；
- arguments 只能使用当前动作配置声明的逻辑字段；
- 受保护值使用不含业务语义的请求级 `value_ref`，其他值只有在配置显式允许模型读取时才可使用 literal；
- QueryPlan 的键和值均不得承载 endpoint、HTTP 方法、SQL、ES DSL、URL、索引、类、方法、角色或 JWT；文本 literal 必须通过动作代码绑定的有限安全字符策略，不能由配置注入任意正则或表达式。

### CFG-02 每域每动作配置

每个配置单元至少包含：

- 已启用的 `domain/action`、配置版本、代码契约版本和快照 ID；
- 查询字段、模型安全描述、字段类型、允许操作符及输入暴露方式；
- 必填、可选、互斥、至少一项和合法组合条件；
- Decimal 绝对值和 scale、固定/允许页码、条数上限、排序字段/方向及排序项上限；
- 允许返回字段和模型可见字段；
- Adapter 代码绑定标识和业务契约快照引用。

配置只能收紧代码绑定能力和业务服务现有契约；不能通过配置新增 action、字段、操作符、endpoint、授权、返回字段或模型出域范围。

### CFG-03 启动一致性

组合根必须在 readiness 前验证：

- 配置 domain/action 是代码定义的子集且唯一；
- 参数字段、类型、操作符和边界不超过代码 validator；
- 返回字段和模型字段均为代码允许集合的子集；
- descriptor、QueryPlan validator、binder、handler、Adapter 和动作 ID 完全对齐；
- 配置版本、代码契约版本和快照 ID 可追踪。

不一致时相关业务能力不得注册或对外就绪，禁止宽松默认值或部分启用。

### CFG-04 变更

配置变更必须版本化，并重新执行启动校验、契约测试和相关 UAT。运行中请求绑定不可变快照；本期不要求动态热更新。

## 7. 身份、敏感数据与授权

1. `agent-service` 验证用户身份后，将用户 JWT 通过内部请求交给 Runtime。
2. JWT 不得发送给模型、写入 QueryPlan 或持久化。
3. 具体员工标识等敏感 literal 在模型调用前由确定性输入闸门替换为请求级 opaque reference；原值只驻留请求内存。
4. Adapter 透传用户 JWT；业务服务依据统一 Authority Converter 和自身权限规则执行最终授权。
5. Agent 的配置和字段策略只能进一步收紧，不能扩大业务服务授权。
6. 未分类字段、策略冲突、引用不存在/重复/跨请求时失败关闭。

## 8. 失败语义

| 场景 | 对外有限状态 | 必须行为 |
|---|---|---|
| 未认证/业务服务拒绝 | `unauthenticated/forbidden` | 不改写为无结果或成功 |
| 模型不可用、超时 | `downstream_failure/timeout` | Adapter 和业务调用为零；无本地降级 |
| QueryPlan JSON/Schema 非法 | `invalid_argument` | 不执行；不修补模型输出 |
| domain/action/字段/操作符未开放 | `unsupported` | 不切域、不回退 Knowledge |
| 值引用、类型、组合或边界非法 | `invalid_argument` | 不执行；不得猜值或舍入 |
| 业务查询无结果 | `no_result` | 保持业务事实，不切换域 |
| 下游协议或依赖失败 | `downstream_failure/timeout` | 不把失败伪装成空结果 |

## 9. 扩展性与最小设计

- 新业务域通过新的代码绑定定义、强类型配置、validator/binder、Adapter 和 handler 接入，不修改既有域实现。
- Core 只接收经校验的最终 ActionCandidate，不包含 Employee/Transaction 语法。
- 不为未来 Multi-Agent、动态 DSL、配置平台、通用查询语言或复杂韧性框架提前建设实现。
- 未来新增业务接口必须先由业务服务明确契约与授权，再更新上位需求和设计。

## 10. 日志与观测

至少记录 correlation ID、配置快照、domain/action、阶段、有限状态、模型/下游调用计数和耗时。不得记录 JWT、密钥、原始员工标识、数据库凭据、完整 QueryPlan 原文、完整模型响应或业务原始响应。

## 11. 测试要求

- exact JSON、重复键、额外字段、深度/大小上限；
- 每域每动作配置的子集、版本、快照和启动失败测试；
- 受保护值 slot 化、绑定、跨请求/缺失/重复引用及零泄漏；
- 模型必须生成 domain/action/arguments，且非法计划失败关闭；
- Employee 仅 detail 成功；`work_base_si` 筛选为 `unsupported` 且下游零调用；
- Transaction 有限条件、Decimal scale≤2、边界、分页和排序；
- 模型失败无本地降级、Business 无 Knowledge 回退、域失败不切换；
- JWT 透传与业务服务最终允许/拒绝矩阵；
- 单动作、并发隔离、取消、日志敏感扫描；
- 默认 stub 只能用于非 live 测试，不能作为 Employee/Transaction LLM 计划 UAT 的通过证据。

## 12. 第一批 UAT 验收标准

1. 公共接入冒烟：认证、严格 JSON、`unsupported`、单动作和默认 stub 失败关闭。
2. Employee：显式真实模型 Provider 生成 `employee.detail` QueryPlan；受保护值不出域；仅一次 detail 调用；权限与失败语义正确。
3. Employee 缺口：地点筛选问题产生的未开放计划被本地拒绝，模型一次、Employee 调用零次。
4. Transaction：显式真实模型 Provider 生成受限 `transaction.search` QueryPlan；精确 Decimal 与有限分页/排序正确；仅一次 search 调用。
5. 阶段收口：Access、Core、QueryPlan validator、配置快照、JWT、Adapter、单动作和禁止替代链路全部回归通过。

## 13. 实施阶段

| 阶段 | 内容 | 退出条件 |
|---|---|---|
| P1/P2 | REQ、L0/L1/L2 权威对齐 | QueryPlan 与配置边界评审通过 |
| P3 | QueryPlan 合同、配置、Runtime 切换、两域接入 | 非 live 测试通过且无业务 Resolver 生产旁路 |
| P4 | 受控真实模型与业务服务集成 | 权限、单动作、失败关闭和零泄漏证据完整 |
| UAT | 公共冒烟、Employee、Transaction、结构化收口 | 第 12 章全部满足 |
| 后续 | Knowledge UAT 与效果优化 | 单独授权与数据/模型门禁 |

## 14. 待确认与阻断事项

- Employee 按地点、职位等筛选存在技术搜索端点，但缺少本需求要求的 endpoint-scoped `ROLE_ADMIN/ROLE_VIEWER` 最终授权和稳定受限响应契约；当前保持 `unsupported`。若要支持，需用户另行确认是否收紧现有端点或新增受限 DTO/端点，并授权相应业务服务、Adapter、设计与测试变更。
- 目标 QueryPlan Runtime、强类型配置和生产组合根尚未实现，第一批业务 UAT 当前不得开始执行成功场景。
- 真实 LLM UAT 需要单独绑定 Provider、模型、固定问题集、预算和一次性调用授权。
- 本需求不授权修改代码、业务接口、数据库结构、生产依赖或执行真实调用。

## 15. 原子修订内审记录

| 轮次 | 检查重点 | 发现与最小修复 | 结论 |
|---:|---|---|---|
| 1 | 唯一链路、职责、QueryPlan/config、权限、跨语言、DAG、过度设计 | 补齐架构元数据、L2 追踪/就绪信息和计划模板；修正计划门禁/资源所有权 | 通过修复复核 |
| 2 | 失败关闭、状态词汇、unsupported 终态、当前/目标分离 | 统一 `unauthenticated`；增加不可进入 binder/Core 的 unsupported 计划终态；明确旧 Resolver/ID-only 仅为现状 | 通过修复复核 |
| 3 | 既有接口事实、安全复用条件、引用一致性、无环性 | 核实 Employee 通用 ES 搜索具备字段能力但缺最终角色授权和受限响应契约；修正失效工作包引用 | 通过修复复核 |
| 独立评审 R1～R3 | 分层与跨层合同、状态、门禁和可实施性 | R1 关闭两项 Major（两级 decoder 所有权、文本 literal 物理表达式）；R2 关闭一项 Major（REQ unsupported sentinel）；R3 无发现 | 通过 |

三轮均复核模型失败、非法计划和不支持查询无 Adapter/业务调用，JWT/受保护值不出域，Employee/Transaction 不切域、不回退 Knowledge，配置不得扩大代码与业务契约。正式独立评审结论由下位设计和计划的评审记录共同承载。
