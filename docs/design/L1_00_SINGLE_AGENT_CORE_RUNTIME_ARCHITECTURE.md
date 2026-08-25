# [L1_00] 单体 Agent 核心与运行架构

> 文档层级：L1
> 文档状态：Approved

## 1. 文档信息、来源与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.0 |
| 更新日期 | 2026-08-25 |
| 上位文档 | [`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v2.0 |
| 关联 L1 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v2.1；Knowledge L1 保持 v1.0 |
| 权威范围 | LangGraph、Runtime、Model Port、Core、Registry、组合根和请求级状态 |
| 当前实现 | 新 filters/actions/config 三动作组合根与 Knowledge 独立对象图已实施并通过 non-live；Employee ES 端点级角色转换修复前不得宣称真实联调完成 |
| 归档来源 | [v1.5 已评审旧版](历史文档/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE_v1.5.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 架构目标、非目标与上位约束映射

核心职责是让 LangGraph 在一个逻辑 Agent 中维护单请求状态，并把已验证的 Business 计划转换为唯一 Core ActionCandidate。非目标是不可信模型直达 handler、本地业务语义解析、业务 SQL/ES、角色判定、第二动作及 Knowledge/跨域 fallback。

| L0 约束 | 模块约束落实 |
|---|---|
| `SA-AD-001` | 只允许 Model Port → Business decoder/validator/binder → Core |
| `SA-AD-002` | Registry 只注册已绑定的 Employee/Transaction 固定动作 |
| `SA-AD-003` | 请求从组合根捕获不可变已验证配置 snapshot |
| `SA-AD-004` | Runtime 透传用户上下文和取消信号，不判定业务角色 |
| `SA-AD-005` | Knowledge 保持独立分支，不作为 Business fallback |

## 3. 模块职责与协作边界

| 组件 | 唯一负责 | 明确不负责 |
|---|---|---|
| Spring access | 请求认证、严格 JSON、上下文传递 | LangGraph 编排和业务 QueryPlan |
| LangGraph | 请求生命周期、输入安全闸门和 Business planning bridge | 本地生成 domain/action/filters、HTTP provider、业务角色授权 |
| Model Port | 基于安全目录请求模型并返回 provider-neutral `JsonObject` | Business field 校验或 Adapter 调用 |
| Business planning | strict decode、字段/config 验证、slot 绑定 | 生成缺失语义、数据库/ES 查询 |
| Registry/Core | 查找唯一 capability、复核参数并执行一次 | 解释自然语言、调用第二动作 |
| 组合根 | 装配三动作 definition、snapshot、model port 与 handler | 决定业务查询条件或兼容旁路 |

依赖方向：`LangGraph → provider-neutral Model Port → Business validation/binder → ActionCandidate → Core → Domain Handler`。provider 实现只能位于 Model 适配边界；Domain handler 不得反向依赖 LangGraph 或模型实现。

## 4. 运行处理流程与数据模型

1. Spring 接入层完成认证、严格请求结构和请求 ID。
2. Runtime 的输入安全闸门先生成受保护 slot、最小化模型问题，并固定请求级配置 snapshot、取消信号和时钟；该闸门不得选择 domain/action 或生成 filters。
3. Model Port 只接收脱敏问题、安全 action/field/operator 目录、slot ID 和已批准时间上下文。
4. Model 层严格解码 provider response，Business 层再解码 `domain/action/arguments`、filters、tagged value、分页和排序。
5. 业务 validator 依据代码合同与配置校验，并执行同字段 range、日期、Decimal、敏感值和单接口可表达性验证。
6. binder 仅绑定当前请求 slot，生成一个 ActionCandidate；Core 再执行既有 CapabilityArgumentValidator 并只调用一个 handler。
7. Adapter 透传用户 JWT 到固定 endpoint；业务服务最终授权并产生受控列表。

unsupported sentinel 不进入 Core；模型失败、非法 plan、快照不一致、取消和缺失 slot 均在 Adapter 前终止。业务拒绝不重试、不切换域/动作，且不得回退 Knowledge。

## 5. 生产组合根与单动作不变量

目标 Registry 公开 `employee.search`、`employee.semantic_search` 和 `transaction.search`；旧 `employee.detail` 仅在完成调用方/兼容性分析前作为历史实现存在，不能继续作为目标 Employee 主查询能力。目标安全 catalog 必须承接 `contact_address → contactAddress` 的业务动作语义，并明确排除 `workBaseSi/workBaseAf`；具体字段与 DTO 映射仍归 Business L1/L2 所有。

生产 Business 对象图禁止 Local Resolver、ID-only selector、自动补全 filters、旧 fallback、跨域重试和第二次 handler 调用。共享 Knowledge/Core 兼容类型只有在仍被有效调用方或冻结历史资产依赖时保留，不得以兼容性为由重新接入 Business 生产路径。

单请求数据仅在内存存在；JWT、真实标识、slot 值和原始响应不得进入模型、日志或持久化。请求级时钟只为已证明正确的日期解析提供一致性；自然日相对查询在数据库时间精度/边界合同未关闭前 unsupported。

## 6. 关键架构决策

| 决策 | 内容 |
|---|---|
| `CR-AD-001` | Model 与 Business 分两级解码；Core 仍只认识稳定 ActionCandidate |
| `CR-AD-002` | 组合根一次装配三个现有接口动作与不可变字段配置 |
| `CR-AD-003` | 所有失败在对应职责层停止，禁止任何替代业务执行链路 |
| `CR-AD-004` | 既有 Knowledge 路径和公共 Core/HTTP 契约保持兼容 |

## 7. 下位 L2 详细设计与责任分解

| L2 | 唯一权威责任 |
|---|---|
| [`L2_00_00`](L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) v1.0 | 既有 Spring 接入与 Runtime 协同，不在本次修改范围 |
| [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v2.0 | Business bridge、组合根、Registry、取消与单动作执行 |
| [`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v2.0 | 模型安全 catalog、Prompt、provider response 严格解码 |
| [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v2.0 | QueryPlan、字段配置、validator、binder 与出域策略 |

## 8. 风险、验证与当前实施状态

应验证三动作唯一可达、一次规划/一次 handler、并发请求 slot 隔离、取消、strict decoder、config snapshot、不支持条件零调用和 Knowledge 回归。无须独立工作流引擎、复杂 circuit breaker、动态 registry 或生产级治理平台。

既有 v2 模型任务和旧 production bridge 只证明旧合同，不证明 filters QueryPlan、Employee search/semantic 或扩展 Transaction。新组合根与其 fake/live/UAT 证据均为 proposed implementation，不得标记 Implemented。
