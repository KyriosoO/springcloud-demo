# [L0_00] 单体 Agent 查询能力总体架构

> 文档状态：Approved
> 文档层级：L0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L0_00 |
| 文档层级 | L0 |
| 当前版本 | v1.3 |
| 更新日期 | 2026-08-24 |
| 上位需求 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v1.6 |
| 架构范围 | 单体 Agent 接入、编排、Knowledge 与 Employee/Transaction 查询、权限和模型边界 |
| 实施状态 | QueryPlan 合同、模型任务、两域 definition/config、Runtime 唯一分支和旧 Resolver 清理已完成；fake 双域 system entry 候选已通过定向验证，仍待全量架构门禁复核；真实环境结论尚未完成 |

## 2. 来源与变更记录

本文来源于 REQ_00 v1.6 及 v1.0 架构基线。v1.1 将 Employee/Transaction 的权威路径由“本地 Resolver 生成参数、模型只选 ID”改为“LLM 生成逻辑 QueryPlan、本地严格校验和绑定”。历史 append-only 证据不改写；其复验所需兼容类型只能保留为生产不可达接缝。无调用方、无审计价值的旧可执行路径不属于历史证据，应在引用和回归核实后清理。

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-08-21 | 建立当前文档基线 |
| v1.1 | 2026-08-24 | 确立 Employee/Transaction LLM QueryPlan 唯一链路、强类型配置和接口缺口失败关闭 |
| v1.2 | 2026-08-24 | 区分历史不可变证据与过时可执行资产，允许最小清理无调用方 Business Resolver 代码/测试 |
| v1.3 | 2026-08-24 | 闭合既有架构测试与新 planning 的依赖边界：只允许唯一 LangGraph bridge 依赖 provider-neutral Model Port，Core/能力合同与 provider 实现继续隔离 |

## 3. 目标、范围与非目标

### 3.1 目标

- 保持 LangGraph 为唯一 Agent 编排权威；
- Knowledge 与 Business 使用各自必要的内部流程，但共享接入、Core 单动作和统一结果约束；
- Employee/Transaction 由 LLM 生成受限 `domain/action/arguments`，本地只做安全预处理、严格校验、值绑定和执行；
- 最终权限和 SQL/ES 执行始终属于业务服务；
- 以最少模块形成可实现、可验证、可扩展的单体架构。

### 3.2 范围内动作

| 动作 | 现有业务契约 | 本期说明 |
|---|---|---|
| `knowledge.query` | Knowledge typed retrieval | 独立检索/证据链路；不是 Business 回退 |
| `employee.detail` | `GET /employees/{idCardNo}` | 单员工详情；标识以请求级受保护引用进入 QueryPlan |
| `transaction.search` | `POST /txn/search` | 有限条件、ExactDecimal、有限分页与排序 |

### 3.3 非目标

- Employee 位置/职位筛选、Transaction Date/聚合/detail、跨域聚合；
- Agent 直连数据库或业务域 ES；
- 模型生成 SQL、DSL、endpoint、索引或代码符号；
- 本地业务 Resolver 旁路、模型失败本地降级、Business→Knowledge 回退、跨域切换；
- 新业务接口/DTO/数据库结构、写能力、Multi-Agent 和配置平台。

## 4. 系统上下文与跨域依赖关系

```text
Client
  → agent-service (Spring: auth / strict JSON / correlation / deadline)
  → agent-runtime (Python / LangGraph: only orchestration authority)
       ├─ Knowledge flow → es-query-service → ES/BGE
       └─ Business input guard
          → LLM Business QueryPlan
          → local exact decode / config validation / value binding
          → agent-core single-action execution
          → Employee or Transaction Adapter
             → employee-service or mq-procedure-service
                → final authorization → SQL/ES owned by business service
```

接入层可在模型前拒绝未认证、严格 JSON 非法或明确敏感违规请求；这是治理闸门，不是第二条业务查询链路。对进入 Business 语义处理的请求，LLM QueryPlan 是强制步骤。

## 5. 能力版图、模块划分与数据所有权

| 模块 | 负责 | 不负责 |
|---|---|---|
| `agent-service` | 认证、协议、correlation、deadline、响应映射 | 选择 domain/action、生成参数、调用 Adapter |
| LangGraph Runtime | 请求状态、Business/Knowledge 分支、调用顺序、终止 | 业务最终授权、SQL/ES、长期状态 |
| Business Input Guard | 屏蔽具体敏感值、生成请求级 opaque ref、保留内存 slot map | 判定 domain/action、生成业务参数 |
| Model Port | 生成受限 Business QueryPlan；按策略生成答案 | 生成物理查询、读取 JWT、执行工具 |
| QueryPlan Validator/Binder | exact decode、代码/配置子集校验、引用绑定、生成最终候选 | 猜测/修补参数、改变 domain/action |
| `agent-core` | 注册、单动作、最终候选校验、统一结果不变量 | 文本理解、领域语法、业务权限 |
| Employee/Transaction Adapter | 固定 endpoint 编码、JWT 透传、严格解码、投影 | 问题理解、角色判断、DB/ES 直连 |
| 业务服务 | 最终授权、业务契约、SQL/ES 选择与执行、数据所有权 | Agent 编排、模型调用 |

依赖方向补充：`capability_api`、`core` 和业务 handler 不依赖 Model；LangGraph 的 Business planning bridge 是唯一允许直接调用 provider-neutral Model Port 的编排接缝。它可以读取请求级 cancellation/deadline 并只读复用 Registry 中实际注册的 argument validator，但不得持有 handler 执行权，也不得依赖 DeepSeek/HTTP/provider DTO。该精确例外不构成第二编排器或 Core 反向依赖。

状态与数据所有权：图状态、slot map、配置快照和 QueryPlan 都是请求级非持久状态；Employee/Transaction 数据及物理查询由业务服务拥有；Agent 不复制业务数据。

## 6. Employee/Transaction 唯一链路

```text
question
  → Business Input Guard (protect literals; no semantic planning)
  → LLM exact QueryPlan {domain, action, arguments}
  → exact JSON + prohibited key/value scan
  → code-bound domain/action/config snapshot validation
  → request-local protected value binding
  → existing argument validator
  → one ActionCandidate
  → agent-core.execute once
  → exact Adapter
  → exact business service endpoint
  → final authorization and query
```

任何节点失败立即形成有限失败结果，后续调用计数必须为零。禁止：

- Local Resolver 直接产生 Business 候选；
- 模型只返回 capability ID 后由本地代码补充参数；
- 修补模型计划或改选另一个 domain/action；
- 执行失败后调用 Knowledge 或另一个业务域；
- Adapter 根据模型传入的 URL/SQL/DSL 动态路由。

## 7. QueryPlan 与配置架构

### 7.1 QueryPlan 边界

Business QueryPlan 顶层只包含 `domain`、`action`、`arguments`。它是模型输出、不可信、请求级且不可执行；通过本地校验和绑定后才可转换为既有 `ActionCandidate`。

受保护值采用 `value_ref`；模型安全 literal 仅对配置显式允许的字段开放。模型 catalog 不包含 endpoint、HTTP 方法、SQL/ES、结果字段、角色或实现符号。

### 7.2 每域每动作强类型配置

配置包括启用状态、逻辑字段及安全描述、类型/操作符、组合规则、Decimal/分页/条数/排序边界、允许结果/模型字段、配置/代码契约版本和快照。配置只能是代码能力与业务接口的子集。

### 7.3 启动一致性

组合根在 readiness 前验证 descriptor、QueryPlan definition、配置、binder、argument validator、handler 和 Adapter 的 domain/action/字段完全对齐。配置扩大代码能力、快照漂移、重复绑定或缺失绑定均导致该能力不注册并使目标 Runtime readiness 失败；不得部分降级为本地 Resolver。

## 8. 全局不变量

| ID | 不变量 | 验证方式 |
|---|---|---|
| `SA-C-001` | LangGraph 是唯一 Agent 编排权威 | 依赖/调用链测试 |
| `SA-C-002` | 每请求最多执行一个动作 | Core 计数和第二动作拒绝测试 |
| `SA-C-003` | Spring、Adapter、业务服务不选择 Agent 动作 | 依赖检查 |
| `SA-C-004` | 业务服务执行最终授权 | 角色允许/拒绝集成测试 |
| `SA-C-005` | 模型输出不可信；Business QueryPlan 必须本地严格校验后才可执行 | exact decode/validator 测试 |
| `SA-C-006` | QueryPlan 只能表达逻辑 domain/action/arguments | 禁止键和 catalog 快照测试 |
| `SA-C-007` | 配置只能收紧代码与业务契约 | 启动子集校验 |
| `SA-C-008` | JWT、密钥、具体受保护值和原始业务结果不得进入规划模型 | model spy/日志扫描 |
| `SA-C-009` | Business 模型失败或非法计划无本地降级 | 零 Adapter/零下游测试 |
| `SA-C-010` | Business 不回退 Knowledge，不跨业务域切换 | 图路径与调用计数测试 |
| `SA-C-011` | Agent/Adapter 不直连业务数据库或 ES | 依赖和网络目标检查 |
| `SA-C-012` | endpoint 与 SQL/ES 实现由 Adapter/业务服务代码掌握 | config/catalog/codec 测试 |
| `SA-C-013` | 失败、无结果、拒绝和成功不可互相改义 | 状态契约测试 |
| `SA-C-014` | 目标设计、已实现、已验证和已生效状态必须分离 | 文档/计划门禁检查 |

## 9. 身份、权限与模型出域

- `agent-service` 验证用户 JWT；Runtime 仅在请求上下文中保存，Adapter 原样透传。
- auth-service 的 role claim 经统一 Converter 形成 `ROLE_ADMIN/ROLE_VIEWER`；业务服务守卫作最终决定。
- 具体员工标识先被替换为 opaque ref，原值不离开请求内存；引用缺失、重复或跨请求即失败。
- 规划模型只接收最小化问题和模型安全动作配置；不接收 JWT、角色、endpoint、业务结果。
- 可选答案模型出域与规划调用分离，默认关闭，并受代码、配置、数据分类三重交集约束。

## 10. 失败与可靠性

| 失败点 | 有限结果 | 后续行为 |
|---|---|---|
| 接入认证/JSON | `unauthenticated/invalid_argument` | 模型与下游零调用 |
| 输入策略拒绝 | `forbidden/unsupported` | 模型与下游零调用 |
| 模型不可用/超时 | `downstream_failure/timeout` | 无本地 Resolver 降级 |
| QueryPlan 结构/值非法 | `invalid_argument` | 不修补、不执行 |
| 未开放 domain/action/field/operator | `unsupported` | 不切域、不回退 |
| 业务拒绝 | `forbidden` | 不改写为 no_result |
| 业务无结果 | `no_result` | 不切换查询 |
| 下游协议/超时 | `downstream_failure/timeout` | 不伪装为空结果 |

本期可靠性只要求 deadline、超时、取消、连接生命周期和有限失败分类；不引入自动重试、熔断或动态降级。

## 11. 质量属性与关键架构决策

| 质量属性 | 目标 | 验证 |
|---|---|---|
| 正确性 | 非法计划、失败和无结果不改义 | 状态与零下游测试 |
| 安全性 | JWT/受保护值/物理查询信息不进入模型 | model spy、日志扫描、catalog 快照 |
| 可演进性 | 新域通过 definition/config/Adapter 接入，不侵入 Core | 依赖与组合根测试 |
| 可验证性 | 每阶段有有限状态和调用计数 | non-live/live evidence |

| ID | 决策 | 理由 | 影响 |
|---|---|---|---|
| `SA-AD-001` | Spring 接入与 Python Runtime 分离职责 | 保持协议治理与 Agent 编排边界 | 内部 HTTP 契约稳定 |
| `SA-AD-002` | LangGraph 唯一编排 | 避免双状态机 | 所有能力由 Runtime 调用 |
| `SA-AD-003` | Business 必须由 LLM 生成完整逻辑 QueryPlan | 满足自然语言到查询计划目标 | 现有本地 Resolver 生产路径需切断 |
| `SA-AD-004` | 本地只做安全预处理、严格校验、引用绑定和执行 | 保持模型参与且安全失败关闭 | 不允许本地猜参或切域 |
| `SA-AD-005` | 每域每动作配置为代码能力子集 | 适应业务接口调整但不扩大契约 | 需要版本/快照/启动校验 |
| `SA-AD-006` | 业务服务拥有 endpoint 后的 SQL/ES 与最终授权 | 服从业务域治理 | Adapter 不直连数据源 |
| `SA-AD-007` | Knowledge 与 Business 不互为回退 | 防止事实与权限语义混淆 | 失败直接终止 |

## 12. 下位 L1 治理

| 文档 | 权威范围 | 必须落实 |
|---|---|---|
| [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | Runtime、模型规划节点、Core、组合根 | QueryPlan→ActionCandidate、单动作、无 Business Resolver 旁路 |
| `L1_01` | Knowledge 流程 | 保持独立，不作为 Business 回退 |
| [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | Business QueryPlan 配置、两域 Adapter、权限/结果边界 | 每域每动作配置、接口缺口和 Adapter 固定绑定 |

同层冲突以本 L0 和 REQ_00 为准；L1 不得通过局部设计恢复被禁止的替代链路。L1 分域与模块治理只允许细化本表权威，不得扩大动作或业务接口。

## 13. 当前状态、差距与门禁

### 13.1 已有事实

- Access、Core、能力注册、模型 transport、Business Adapter、JWT 透传、业务服务授权守卫和受控只读接口已有不同层级的实现/验证证据。
- QueryPlan 公共合同、模型任务、两域 definition/config 与 Runtime 唯一分支已有实现；共享 ID-only selector 仅服务非 Business，Employee/Transaction 专属旧 Resolver 资产和最后空 support 字段已按边界清理。
- `employee.detail`、`transaction.search` 可复用。Employee 通用 ES 搜索具有字段筛选能力，但缺少本架构要求的业务角色最终授权与受限响应契约，不能作为当前 Agent 动作。

### 13.2 未完成目标

- system entry 的 QueryPlan 组合装配与双域 non-live E2E；
- 经引用核实删除 Employee/Transaction 专属旧 Resolver 代码/测试；
- 受控真实 LLM + 业务服务集成和 UAT。

这些差距由 P3_00 v1.27 工作包和门禁治理。在完成前，不得把原有本地 Resolver E2E 或历史模型 PoC 当作本目标通过证据。

## 14. 风险与控制

| 风险 | 触发场景 | 控制 |
|---|---|---|
| 模型扩大查询范围 | 生成未开放动作/字段/操作符 | exact schema、代码/配置双重子集、失败关闭 |
| 敏感值出域 | 问题包含身份证等标识 | 策略优先、request-local slot、model spy |
| 双链路 | 保留 Resolver 作为 fallback | 组合根唯一性、依赖扫描、模型失败零下游测试 |
| 接口能力误判 | 用仅校验用户令牌、返回原始 ES 字符串的通用搜索实现 Employee 筛选 | 仅使用满足业务最终授权与稳定契约的 endpoint；缺口 `unsupported` |
| 配置漂移 | 配置版本与代码/接口不一致 | snapshot 与 readiness 校验 |
| 过度设计 | 建动态 DSL/配置平台/通用工具协议 | 只实现两个代码绑定动作和静态版本配置 |

## 15. 需求追踪与评审

| 需求 | 架构落点 |
|---|---|
| FR-01 | 单动作与唯一编排 |
| FR-02 | Knowledge 独立边界 |
| FR-03/04 | 两个代码绑定动作与现有接口 |
| FR-05 | 第 6 章唯一 QueryPlan 链路 |
| FR-06 | Adapter 与业务服务所有权 |
| CFG-01～04 | 第 7 章契约、配置与启动校验 |
| SEC | 第 9 章身份、slot 与最终授权 |

### 15.1 v1.1 内审与正式评审

| 阶段 | 重点 | 发现与修复 | 结论 |
|---|---|---|---|
| 内审1 | 唯一链路、层次与追踪 | 补齐层级元数据、目标/现状和下位权威 | 修复后通过 |
| 内审2 | 失败语义与 unsupported | 统一 `unauthenticated`，闭合 unsupported 终态 | 修复后通过 |
| 内审3 | 业务接口、安全与无环性 | 将 Employee 搜索结论修正为“有技术能力但不满足最终授权/受限契约” | 修复后通过 |
| 独立评审 R1～R3 | 分层与跨层一致性 | 依次关闭 decoder 所有权、文本 literal 安全、上位 unsupported 合同三项跨层问题；R3 无发现 | 通过 |
| v1.2 内审1 | 唯一链路与清理职责 | 明确旧可执行旁路不属于架构回滚资产 | 修复后通过 |
| v1.2 内审2 | 历史证据和兼容风险 | 保留冻结 harness 复验所需类型，生产工厂拒绝非空绑定 | 修复后通过 |
| v1.2 内审3 | 跨层版本、DAG与最小性 | 清理活动不扩大动作/API/DB/权限且不新增依赖边 | 通过 |
| v1.2 独立评审 R1～R3 | 证据不可变、生产隔离、跨层一致性 | 历史复验兼容与生产拒绝边界修复后，R3 无发现 | 通过 |

评审通过只代表设计一致、可实施，不代表代码已实现或环境已生效。

## 16. 结论

本架构以 LLM Business QueryPlan 为 Employee/Transaction 唯一语义入口，以本地严格验证和业务服务最终授权保持安全确定性。设计范围限于当前满足复用条件的 `employee.detail` 和 `transaction.search`；Employee 条件筛选虽然存在通用 ES 技术端点，但其授权与响应契约不满足本架构边界，故明确失败关闭并等待独立授权。
