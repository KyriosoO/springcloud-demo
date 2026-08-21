# [L1_02] 单体 Agent 业务查询与适配器架构

> 文档层级：L1
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L1_02` |
| 文档层级 | L1 能力架构 |
| 文档状态 | Approved |
| 当前版本 | v1.0 |
| 日期 | 2026-08-21 |
| 权威范围 | Business 公共约束、Employee/Transaction 本地 Resolver、Adapter、业务 Provider、结果与模型出域边界 |
| 上位文档 | [`L0_00` v1.0](L0_00_SINGLE_AGENT_ARCHITECTURE.md) |
| 来源文档 | [L1_02 v0.5 归档版](历史文档/2026-08-21-v0-baseline/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) |
| 关联 L1 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md)、[`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 下位文档 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md)、[`L2_02_01`](L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md)、[`L2_02_02`](L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) |
| 实施状态 | 两域本地 Resolver、Python Adapter、Java 最终授权及受控真实只读查询已有证据；真实业务结果模型出域默认关闭；未生产生效 |

## 2. 阅读导航

重点顺序：

1. [能力与责任边界](#5-能力与责任边界)；
2. [动作目录](#6-动作目录)；
3. [身份与最终授权](#8-身份与最终授权)；
4. [结果与模型出域](#9-结果与模型出域)；
5. [失败语义](#11-失败语义)；
6. [L2 交付边界](#15-l2-交付边界)。

## 3. 来源与取舍

### 3.1 保留的设计

- Employee 与 Transaction 使用独立 Adapter；不建设动态通用 HTTP Adapter。
- 当前只提供 `employee.detail` 和 `transaction.search` 两个代码绑定只读动作。
- 业务参数由各域本地 Resolver 确定性生成；模型只可选择能力 ID，不得生成参数。
- Adapter 透传原始用户 JWT；业务服务拥有最终动作授权和成功响应可见性。
- 强类型配置只能启停或收紧代码、公开契约和授权已允许的范围。
- 业务服务响应、Agent 用户结果和模型安全载荷相互分离。
- 模型字段默认拒绝，取授权响应、代码字段、动作配置、出域配置和全局规则的交集。
- `transaction.search` 的金额采用精确 Decimal 语义；首期排除 Date、聚合、写入和管理能力。
- 当前真实 Provider 查询可用，但真实 Employee/Transaction 结果进入外部模型仍是默认关闭的可选实验。

### 3.2 简化内容

移除旧版逐轮门禁、candidate/manifest/hash、已解决实施缺口和重复状态流水。历史审计细节保留在归档；本版本只说明当前有效架构、启用条件和保护边界。

### 3.3 本版本变更记录

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立新的可读业务查询架构基线 | 合并公共语义，突出动作、授权、配置、结果/出域隔离和两域差异 |

## 4. 目标、范围与上位约束

### 4.1 目标

以两个最小只读动作验证 Agent 对业务域的安全访问：自然语言只负责触发动作，本地确定性逻辑负责参数，Adapter 负责协议适配，业务服务负责最终授权；任何配置、模型或响应漂移都不能扩大查询、权限或模型出域范围。

### 4.2 范围内

- Business 公共输入、结果、配置、JWT 透传和出域语义；
- Employee、Transaction 各自的本地 Resolver 与 Adapter；
- 两个现有只读公开接口的类型化消费；
- 业务服务最终角色授权、响应可见性和跨语言契约验证；
- 结构化本地结果、可选模型回答及 grounding。

### 4.3 范围外

- 新业务接口、动态 URL/方法、数据库或业务域 ES 直连；
- 列表、Date、聚合、写入、审批、工作流和跨域聚合；
- 业务角色配置、行级/字段级业务授权规则的复制；
- Knowledge 检索、公共 Runtime、DeepSeek 协议实现；
- 生产级熔断、重试、降级、缓存、服务发现和策略管理平台。

### 4.4 L0 约束映射

| L0 约束 | 本文落实 |
|---|---|
| `SA-C-002/013` | 每请求最多一个已注册只读动作；禁止入口不注册 |
| `SA-C-003/004` | Adapter 只调用业务公开接口；业务服务最终授权 |
| `SA-C-005/022` | 本地 Resolver 生成参数；模型不生成或修补业务参数 |
| `SA-C-006/012` | 配置只收紧；契约变化必须同步代码和契约测试 |
| `SA-C-007/011` | 原始用户 JWT 必需；敏感值不进入日志和未授权模型输入 |
| `SA-C-008/009` | 不持久化业务数据；失败或不完整数据不生成肯定事实 |
| `SA-C-010/014/019` | 新域经独立 Adapter 和组合根接入；公共契约不含供应商或业务分支 |
| `SA-C-020` | 模型字段默认拒绝，并取多重允许集合交集 |

`SA-C-015～018/021` 为 Knowledge 专属约束；本文不重定义。

## 5. 能力与责任边界

本文唯一负责 Business 查询公共约束及两个业务域的 Agent 侧适配；业务数据、公开接口、角色授权和数据可见性的权威仍在业务服务。

### 5.1 主要链路

```text
LangGraph / Hybrid Action Selection
        │
        ├─ Employee Local Resolver ─ Employee Adapter ─ HTTP ─ employee-service
        │
        └─ Transaction Local Resolver ─ Transaction Adapter ─ HTTP ─ mq-procedure-service
```

所有业务调用均经 `CapabilityExecutionCore` 的单动作闸门；Adapter 不绕过注册、validator、截止时间或取消语义。

### 5.2 责任表

| 组件 | 核心职责 | 明确不负责 |
|---|---|---|
| Business Common | 公共动作/结果类型、配置规则、JWT Client、投影、有限转换、grounding | 域语法、业务角色判断、动态协议 |
| Employee Resolver | 识别单员工详情有限语法并产生候选参数 | 访问服务、猜测标识、模型回退 |
| Employee Adapter | 请求/响应 codec、六字段本地投影、状态归一化 | Employee 授权、业务规则、数据库访问 |
| Transaction Resolver | 识别受控交易查询有限语法和精确金额条件 | Date、聚合、写入、模型猜参 |
| Transaction Adapter | `transaction.search` codec、Decimal、投影和状态归一化 | Transaction 授权、金额舍入、数据库访问 |
| 业务服务 | 公开契约、最终授权、成功响应可见性、数据真相 | Agent 路由、模型出域策略 |
| 模型端口 | 可选地表达已允许 facts | 参数生成、授权判断、补造事实 |

### 5.3 稳定扩展缝隙

- 新业务域增加新的 Resolver、Adapter、强类型配置和组合根绑定。
- 新域不得修改现有 Employee/Transaction 实现，也不得向 Core 加域分支。
- 只有出现真实第三域的重复需求时才评估抽取更多公共框架。
- 聚合、工作流、提交和 Multi-Agent 需要新的上位设计，不能复用当前查询动作绕过范围。

## 6. 动作目录

| 能力 ID | 参数来源 | 下游契约 | 结果边界 | 禁止能力 |
|---|---|---|---|---|
| `employee.detail` | Employee 本地 Resolver；单一员工标识 | `GET /employees/{idCardNo}` | 仅本地六字段投影；模型最多使用经允许的 `position/work_base_si` | 列表、写入、其他 Employee 端点 |
| `transaction.search` | Transaction 本地 Resolver；有限条件和 ExactDecimal | `POST /txn/search` | 受控查询结果；模型最多使用经允许的 `transaction_type/amount` | Date、聚合、detail、写入、管理 |

动作 ID、参数 Schema、HTTP 方法和路径由代码绑定。模型、配置和用户不得传入 URL、类名、DTO 类型、SQL、ES DSL 或任意字段名。

### 6.1 动作判定

1. 本地域 Resolver 先判断是否匹配并生成强类型参数。
2. `no_match` 才允许公共选择链继续；`invalid` 或歧义直接失败。
3. 若多个本地 Resolver 同时匹配，Hybrid 节点拒绝，不选择“更像”的一个。
4. 模型选择仅返回 exact capability ID；最终参数仍必须来自本地 Resolver。
5. Resolver、descriptor、validator、handler 和配置的动作 ID 必须在组合根启动时完全对齐。

## 7. 强类型配置

### 7.1 配置权限

配置可以：

- 启用或禁用代码中已存在的域和动作；
- 收紧允许条件、排序、分页、超时、结果字段和模型字段；
- 从代码声明的有限转换枚举中选择转换；
- 选择受控目标地址和已知契约版本。

配置不得：

- 创建动作、端点、HTTP 方法、请求字段或响应字段；
- 增加角色、扩大业务授权或改变公开契约；
- 注入脚本、表达式、类名、SQL、DSL 或任意转换代码；
- 绕过必需用户结果字段、Decimal 约束、单动作或默认拒绝策略。

### 7.2 启动校验

组合根在就绪前校验动作 ID、Resolver/handler 唯一性、字段引用、最小有效结果、转换枚举、边界值、目标地址和契约版本。无效域不得部分注册；禁止用宽松默认值使其“可运行”。

配置在启动时冻结，请求处理中不可热变更。回滚以禁用单域动作并重启为主。

## 8. 身份与最终授权

### 8.1 信任链

```text
auth-service role claim
  → common-security Authority Converter
  → ROLE_ADMIN / ROLE_VIEWER
  → Agent 透传原始用户 JWT
  → 业务服务最终动作授权与响应可见性
```

- `auth-service` 的首批角色 claim 为精确大写 `ADMIN`、`VIEWER`；`dylan` 是当前映射为 `ADMIN` 的用户，不是角色。
- Servlet 和 Reactive 使用共享 Authority 语义；业务查询只消费，不复制 Converter 规则。
- 缺失、格式错误、过期 JWT 或 service-token 均不得触发业务调用。
- Adapter 不解析角色作允许判断，也不以固定服务身份回退。
- Agent 的字段投影是二次最小化，不替代业务服务的行级、字段级或动作授权。

### 8.2 允许/拒绝语义

| 场景 | 业务调用 | 公共结果 |
|---|---:|---|
| 无有效用户身份 | 0 | `unauthenticated` |
| 有效用户但业务服务拒绝 | 1 | `forbidden` |
| 业务服务允许且有数据 | 1 | `success` |
| 业务服务允许且明确无数据 | 1 | `no_result` |

Agent 入口认证成功不代表业务动作已授权。业务 `401/403` 必须保留区分，不得降级为 `no_result`。

## 9. 结果与模型出域

### 9.1 三种视图

| 视图 | 用途 | 规则 |
|---|---|---|
| 授权业务响应 | 业务服务返回的协议对象 | 仅在最终授权成功后接收；仍视为外部不可信输入 |
| Agent 用户结果 | 本地结构化响应 | 只保留动作声明字段和最小有效结果；不因投影伪造 `no_result` |
| 模型安全载荷 | 可选 answer 输入 | 独立构建、默认拒绝，只含允许 facts |

### 9.2 字段交集

模型可见字段集合为：

```text
业务服务已授权返回字段
∩ 代码结果 Schema
∩ 动作结果配置
∩ 模型出域配置
∩ 全局安全规则
```

任何未知字段、嵌套结构、策略冲突、不支持转换、最小字段缺失或敏感问题都使业务结果模型调用为 0。业务授权成功不等于允许外发。

当前字段上限：

- Employee：`position`、`work_base_si`；身份证、成员号、姓名、联系方式、地址、账户、凭证等不得进入模型。
- Transaction：`transaction_type`、`amount`；标识、日期、账户及其他未声明字段不得进入模型；金额保持 ExactDecimal 语义。

### 9.3 有限转换与 grounding

- 转换由代码实现，配置只选择有限枚举；转换后重新校验类型、长度和结构。
- 业务文本始终作为不可信数据，不得被模型解释为系统指令或工具调用。
- 模型回答的每个肯定业务事实必须能追踪到本次模型安全载荷。
- 无法验证 grounding 时丢弃候选回答，返回结构化本地结果或固定受控响应。

## 10. 运行流程

### 10.1 通用流程

```text
用户 JWT + 问题
  → 输入安全闸门
  → 本地域 Resolver
  → Core 单动作提交
  → 动作参数 validator
  → Adapter 透传 JWT 调用业务服务
  → 最终授权/数据可见性
  → 严格响应 codec 与动作字段投影
  → Agent 用户结果
  → [可选] 出域交集与转换
  → [允许] 模型回答 + grounding / [拒绝] 零模型调用
```

### 10.2 数量与时限

- 每请求业务动作执行次数为 0 或 1；Employee 与 Transaction 不交叉调用。
- Adapter 从 Runtime 剩余总预算派生更小的下游超时，并传播取消。
- 分页、结果条数、字段数、响应大小和金额/文本边界均有上限；精确值由对应 L2 固化。
- 本期不自动重试，不在一个请求内切换业务域或调用第二动作。

## 11. 失败语义

| 场景 | 结果 | 约束 |
|---|---|---|
| Resolver 不匹配 | `no_match`（选择阶段内部） | 不触发当前域调用 |
| Resolver 歧义、冲突或参数非法 | `invalid_argument` | 不回退模型猜参 |
| JWT 缺失/无效 | `unauthenticated` | 下游调用为 0 |
| 业务服务 `403` | `forbidden` | 不改写为无结果 |
| 明确无业务记录 | `no_result` | 仅 Provider 明确表达时成立 |
| 超时或取消 | `timeout` | 取消原因可保留在内部错误码；迟到响应不得进入结果或模型 |
| 协议、类型、动作 codec 兼容 allowlist 外字段或必需字段错误 | `downstream_failure` | 失败关闭；不做宽松 coercion；兼容宽字段不得进入受控结果 |
| 出域策略拒绝 | 本地结果保留；模型调用 0 | 不等于业务查询失败 |
| 模型/grounding 失败 | 本地结果或受控失败 | 不改变业务调用结论 |

两个业务域均不因另一域失败而回退或聚合；服务错误正文不得直接进入用户响应、日志或模型。

## 12. 横切机制

### 12.1 安全与日志

至少记录关联 ID、域、动作、配置快照、阶段、有限状态、耗时、结果数量/截断和出域允许/拒绝。不得记录完整 JWT、密钥、员工标识、账户、联系方式、完整业务响应、完整模型载荷或原始错误正文。

### 12.2 可演进韧性接缝

本期只要求超时、截止时间、取消、连接生命周期和失败分类。未来可在业务客户端边界增加重试、熔断或限流装饰器，但不得修改 Core、Resolver、动作契约或业务服务。任何重试必须先重新设计幂等性、预算和身份语义。

### 12.3 可观测性

同一关联 ID 可追踪 Resolver、validator、业务调用、响应映射、用户投影、出域决定和回答生成；指标只使用有限枚举和整数，不携带业务值。

## 13. 质量目标与验证

| 质量目标 | 可验证不变量 |
|---|---|
| 单动作与域隔离 | 每请求业务调用 0/1；跨域调用 0 |
| 只读安全 | 写入、聚合、Date、管理和直连存储入口均不可达 |
| 身份与最终授权 | 原始 JWT 透传；service-token 回退 0；业务 401/403 可区分 |
| 参数安全 | 未声明、越界、冲突参数在下游前拒绝；模型参数生成 0 |
| 结果安全 | 未投影的兼容宽字段及未知字段进入受控结果 0；不制造空 `success` 或伪 `no_result` |
| Decimal 精度 | JSON number → Python Decimal → Java BigDecimal → `DECIMAL(50,2)` 不舍入、不用 float |
| 出域安全 | 禁止/未知/冲突字段进入模型 0；拒绝场景模型调用 0 |
| 事实约束 | 最终肯定事实均可追踪到本次安全 facts |
| 可扩展性 | 模拟第三域不修改 Core 或现有两个域实现 |
| 兼容性 | 公开契约漂移由调用方/Provider 契约测试检出 |

本文不承诺生产吞吐、可用性或延迟 SLO。

## 14. 架构决策

| 决策 ID | 决策 | 理由与影响 |
|---|---|---|
| `BQ-AD-001` | 两个独立 Adapter 直接实现能力处理器 | 保留业务域隔离；接受少量重复 |
| `BQ-AD-002` | 代码绑定有限动作是最小执行单位 | 阻止动态端点和模型协议控制 |
| `BQ-AD-003` | 现有只读公开契约是能力上限，配置只收紧 | 契约变化需同步代码与测试 |
| `BQ-AD-004` | 一个动作只映射一个业务只读契约 | 避免隐式聚合和部分失败 |
| `BQ-AD-005` | 业务服务最终授权，Adapter 仅透传原始 JWT | 权限与数据所有权留在业务域 |
| `BQ-AD-006` | 授权响应、用户结果、模型载荷分离 | 支持本地可用与外发默认拒绝并存 |
| `BQ-AD-007` | 多重字段交集、有限转换和 grounding | 防止配置扩权、提示注入与无依据事实 |
| `BQ-AD-008` | 暂不抽取动态业务框架 | 符合个人验证项目的最小可靠设计 |
| `BQ-AD-009` | 公共约束一份 L2，两个域各一份 L2 | 共享语义集中，域契约隔离 |
| `BQ-AD-010` | 接口不足时停止并先取得确认 | Adapter 不模拟或越权扩充业务契约 |
| `BQ-AD-011` | 各域本地 Resolver 生成参数，Hybrid 节点只裁决唯一性 | 敏感参数不出域且 Core 不含域语法 |
| `BQ-AD-012` | 真实 Provider + stub 模型可完成主链；真实业务结果出域为可选实验 | 既验证完整查询链，又避免把外发和随机模型效果变成主链前置 |

## 15. L2 交付边界

| 文档 | 唯一负责 | 明确不负责 |
|---|---|---|
| [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | 公共动作/结果、配置、JWT Client、投影、转换、grounding、字段交集和公共装配 | 两域具体语法、端点和字段清单 |
| [`L2_02_01`](L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | Employee Resolver、`employee.detail` codec、六字段用户投影、模型字段、授权/可见性联调 | Transaction、Employee 业务规则或新接口 |
| [`L2_02_02`](L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | Transaction Resolver、`transaction.search`、ExactDecimal、模型字段、授权/可见性联调 | Employee、Date/聚合/写入或新接口 |

### 15.1 同层协作边界

- `L1_00/L2_00_01` 拥有能力 API、Core、Hybrid 裁决和公共结果；本域只实现 Resolver/handler。
- `L2_00_02` 拥有模型 Provider、选择和回答生成；业务 L2 只提供安全 facts、领域字段策略和 grounding 输入。
- `L2_00_03` 与 `common-security` 拥有 Authority Converter；业务 L2 只定义消费假设和角色矩阵。
- 每个域 L2 拥有本域语法、端点、字段和业务授权联调，不修改另一域。

### 15.2 实施顺序

1. `L2_02_00` 先固定公共契约和组合根约束。
2. `L2_02_01`、`L2_02_02` 可在公共约束稳定后独立实施和验证。
3. 单域真实 Provider 失败不阻塞另一域或公共 Runtime。
4. 任何新增/不兼容业务接口先形成差距和影响分析，再取得明确授权。

## 16. 当前状态与保护条件

### 16.1 已有证据范围

- Business common、两个 Python Adapter、本地 Resolver、共享 Authority Converter 和 Java 最终授权守卫已实现。
- Employee `employee.detail` 与 Transaction `transaction.search` 的受控真实只读查询、角色允许/拒绝和日志零泄漏已有证据。
- Transaction 金额链已按 `DECIMAL(50,2)` 收紧，Agent 输入 scale≤2，禁止 float 和隐式舍入。
- 三域真实 Provider + 默认 stub 模型的系统 E2E 已完成。

这些结论只说明当前受控实现和测试切片，不代表默认启用、目标部署或生产生效。

### 16.2 数据、状态与一致性

Business 查询不持久化业务数据，也不建立跨服务事务。每个请求绑定不可变的动作定义、配置快照、用户 token 和截止时间；响应仅在同一请求内完成 strict decode、归一与投影。取消、超时或失败后的迟到结果不得进入用户结果或模型，不产生跨请求状态合并或最终一致性补偿。

### 16.3 仍生效的保护条件

| 保护条件 | 当前状态 | 允许 | 禁止 |
|---|---|---|---|
| Employee 真实结果模型出域 | 默认关闭 | 真实 Provider + 本地/stub 结果 | 真实 Employee facts 进入外部模型 |
| Transaction 真实结果模型出域 | 默认关闭 | 真实 Provider + 本地/stub 结果 | 真实 Transaction facts 进入外部模型 |
| 默认/生产启用 | 未授权 | 隔离测试和显式本地配置 | 宣称生产生效或自动打开动作 |
| 新增/不兼容业务接口 | 未授权 | 记录差距、做影响分析 | 直接修改业务服务公开契约 |

历史一次性 Gate、run、manifest 和 evidence 只作审计，不构成新执行授权，也不在本版本重复维护。

## 17. 风险与控制

| 风险 | 触发场景 | 控制 |
|---|---|---|
| 动态 Adapter 演化 | 配置可指定路径、类名或任意字段 | 代码绑定动作与严格启动校验 |
| Adapter 越权 | 本地角色白名单替代业务服务 | 只透传 JWT；业务服务最终授权 |
| 宽实体泄露 | 直接返回或外发业务 DTO | 三视图分离、字段交集、默认拒绝 |
| 服务身份兜底 | 用户 JWT 丢失后使用固定凭证 | 专用用户 Client；无 JWT 零调用 |
| 模型猜参或补事实 | Resolver 失败后交给模型 | `invalid` 失败关闭；grounding 校验 |
| Decimal 失真 | float、字符串 coercion、隐式 scale | canonical JSON number 与 Decimal/BigDecimal 链 |
| 过度抽象 | 为两个域建立动态策略平台 | 保留轻量公共层，第三域出现后再评估 |

## 18. 需求追踪与评审

### 18.1 需求追踪

| 需求 | 本文落实 | 下位文档 |
|---|---|---|
| `FR-03` Employee 查询 | 独立 Adapter、现有详情接口、最终授权 | `L2_02_01` |
| `FR-04` Transaction 查询 | 独立 Adapter、有限 search、ExactDecimal | `L2_02_02` |
| `FR-05` Adapter 模块 | 两个独立 Python Adapter、协议转换和 JWT 透传 | `L2_02_00/01/02` |
| `FR-06` 有限动作 | 代码绑定、单动作、本地 Resolver、禁止动态协议 | 三份业务 L2 |
| `CFG-01～04` | 每域每动作强类型配置只收紧 | 三份业务 L2 |
| `SEC-01～05` | 原始 JWT、共享 Authority、业务服务最终授权 | `L2_02_00/01/02`、`L2_00_03` |
| `EXT-01～03` | 新域经新 Resolver/Adapter/组合根接入 | `L2_02_00` |

### 18.2 三轮内审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 1 | 范围、责任、上位权威和三份 L2 分工一致 | Passed |
| 2 | 两动作、最终授权、字段出域、Decimal 和失败边界一致 | Passed |
| 3 | 可读性、追踪、链接、实施边界和历史隔离检查通过 | Passed |

### 18.3 独立正式评审

| 项目 | 状态 |
|---|---|
| 评审结论 | Passed；`REV-L1-02-001～004` 已修复并独立复核 |
| 未关闭 S0/S1 | 0 / 0 |
| 基线状态 | Approved；可治理三份 Business L2 |

## 19. 术语与状态声明

| 术语 | 含义 |
|---|---|
| 有限动作 | 代码绑定、强类型输入、受控结果且只映射一个已确认只读契约的动作 |
| Agent 用户结果 | 授权响应经协议校验和动作投影形成的本地最小结果 |
| 模型安全载荷 | 经多重字段交集和有限转换后允许进入模型的最小 facts |
| 最终授权 | 业务服务依据当前用户 Authority 对动作及成功响应数据范围作出的决定 |
| 配置只收紧 | 配置只能减少既有动作、字段、条件和边界，不能创建或扩权 |

- 当前版本：v1.0。
- 文档状态：Approved。
- 当前实现不是生产级或生产生效声明。
- 新版本不继承旧版修订流水；来源、有效决策和当前证据边界已在本文明确。
