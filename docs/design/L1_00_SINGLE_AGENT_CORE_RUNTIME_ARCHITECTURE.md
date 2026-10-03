# [L1_00] 单体 Agent 核心与运行架构

> 文档层级：L1
> 文档状态：Approved（v3.2动作选择职责增量独立定向复评通过；原证明范围不扩大）

## 1. 文档信息、来源与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v3.2 |
| 日期 | 2026-10-03 |
| 上位文档 | [`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v3.2 |
| 关联 L1 | [`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v3.6；[`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v3.1 |
| 权威范围 | LangGraph、Runtime、Model Port、Core、Registry、组合根和请求级状态 |
| 当前实现 | Business三动作对象图保持不变；Knowledge默认关闭，仓库当前12/9/minimal-v1已接入同一Registry/Core并有non-live证据。Knowledge启用时显式绑定action-selection-v5，关闭时保持原v4缺省；该增量已完成定向non-live及独立代码复评，真实效果未重新测量。旧Knowledge功能/效果结论仅适用原验证范围，不证明当前真实质量 |
| 归档来源 | [整理前 v3.6 原文](历史文档/2026-09-14-unified-v3-baseline/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |

修订历史：2026-09-14，整理纳入统一文档基线v3.0；原版本、源提交及完整字节归档见上表。本次版本序列重置不是代码或设计回滚，评审、实施、部署和UAT状态分别管理。

本轮v3.0经三轮内审及两轮同一执行者的分层/跨层正式复核通过；仅证明文档整合，不表示新实现、部署或UAT已完成。完整发现与验证见本次归档MIGRATION.md。

本次v3.1仅修订计划引用、权威归属和维护状态，不改变业务合同；本轮限定迁移复核已通过（同一执行者分阶段），原v3.0评审范围不扩大为新实现/验收。新入口及历史追溯见[计划迁移说明](../plans/历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

v3.2（2026-10-03）按维护者明确授权补齐能力选择与资料存在性判断的职责分界；仅新增选择任务合同，不改变Business、权限、公开DTO或历史验收。评审、实施及真实质量分别记录。

## 2. 架构目标、非目标与上位约束映射

既有职责：Knowledge 在既有 `no_result` 状态及开放的 `result` 对象内返回有限 reason；Core 只根据已验证的内部 reason 选择固定展示文本，不理解问题、不改变 domain/action、不生成补充计划。普通无命中、证据不足和需要澄清必须可区分；未知 reason 保持通用文本。状态枚举、公开 DTO 字段和 Business 行为不变。当前代码已有此接缝；新设计复用它，映射见 L2_01_00 §8。

v3.1整理时源码为11/7/v3、目标为12/8；这不是当前绑定。当前仓库已接线意图12/Summary9/minimal-v1，由同一Knowledge handler承担查询类型、一次选域、原问题检索及有引用的有限回答。Core仍不解释资料存在性或适用性；具体实现和验收状态以P3_01/UAT_02为权威。旧目标已取消，不继承其实施或模型授权。

核心职责是让 LangGraph 在一个逻辑 Agent 中维护单请求状态，把已验证的 Business 计划或 Knowledge 单动作选择转换为唯一 Core ActionCandidate。非目标是不可信模型直达 handler、本地业务语义解析、业务 SQL/ES、角色判定、第二动作及 Business/Knowledge 相互 fallback。

| L0 约束 | 模块约束落实 |
|---|---|
| `SA-AD-001` | 只允许 Model Port → Business decoder/validator/binder → Core |
| `SA-AD-002` | Registry 只注册已绑定的 Employee/Transaction 固定动作 |
| `SA-AD-003` | 请求从组合根捕获不可变已验证配置 snapshot |
| `SA-AD-004` | Runtime 透传用户上下文和取消信号，不判定业务角色 |
| `SA-AD-005` | Knowledge 作为同一 Registry/Core 内的独立 capability，可按开关注册，但与 Business 互不 fallback |

## 3. 模块职责与协作边界

| 组件 | 唯一负责 | 明确不负责 |
|---|---|---|
| Spring access | 请求认证、严格 JSON、上下文传递 | LangGraph 编排和业务 QueryPlan |
| LangGraph | 请求生命周期、输入安全闸门和 Business planning bridge | 本地生成 domain/action/filters、HTTP provider、业务角色授权 |
| Model Port | 基于安全目录请求模型并返回 provider-neutral `JsonObject` | Business field 校验或 Adapter 调用 |
| Business planning | strict decode、字段/config 验证、slot 绑定 | 生成缺失语义、数据库/ES 查询 |
| Registry/Core | 查找唯一 capability、复核参数并执行一次 | 解释自然语言、调用第二动作 |
| 组合根 | 非stub生产配置装配Business三动作；按显式开关追加唯一 `knowledge.query`、两项 Knowledge 模型任务和 owned clients | 决定查询语义、复制 Runtime 或建立兼容旁路 |

Business 依赖方向为 `LangGraph → provider-neutral Model Port → Business validation/binder → ActionCandidate → Core → Domain Handler`；Knowledge 依赖方向为 `LangGraph → capability selector → knowledge.query → Knowledge stages/ports`。两者共享 Registry、Core、Model Gateway 与请求上下文，但不共享领域计划、Adapter 或失败降级。provider 实现只能位于适配边界；Domain handler 不得反向依赖 LangGraph 或模型实现。

## 4. 运行处理流程与数据模型

1. Spring 接入层完成认证、严格请求结构和请求 ID。
2. Runtime 的输入安全闸门先生成受保护 slot、最小化模型问题，并固定请求级配置 snapshot、取消信号和时钟；该闸门可以基于显式业务锚点或受保护姓名/姓氏强提示决定是否允许进入受控 Business planning，但不得选择 domain/action/operator 或生成 filters。
3. Model Port 只接收脱敏问题、安全 action/field/operator 目录、slot ID 和已批准时间上下文；模型必须完整保留用户限定条件，不能将“语义检索 + 地址过滤”降级为只执行语义检索，也不能在缺少已批准时钟上下文时推断相对日期。
4. Model 层严格解码 provider response，Business 层再解码 `domain/action/arguments`、filters、tagged value、分页和排序。
5. 业务 validator 依据代码合同与配置校验，并执行同字段 range、日期、Decimal、敏感值和单接口可表达性验证。
6. binder 仅绑定当前请求 slot，生成一个 ActionCandidate；Core 再执行既有 CapabilityArgumentValidator 并只调用一个 handler。
7. Adapter 透传用户 JWT 到固定 endpoint；业务服务最终授权并产生受控列表。

unsupported sentinel 不进入 Core；模型失败、非法 plan、快照不一致、取消和缺失 slot 均在 Adapter 前终止。业务拒绝不重试、不切换域/动作，且不得回退 Knowledge。

### 4.1 能力选择不承担资料存在性判定

选择器只根据安全能力目录和用户请求的操作类型选择一个已启用Capability。资料查找、依据原文解释和适用性询问属于目录中Knowledge职责时，即使文件名称、年份或事实尚未确认，也不能仅凭模型常识猜测文件不存在、过时或语料未覆盖而选择unsupported。资料是否存在、所需条件是否齐备和证据是否充分，由Knowledge在已批准的域计划、读取授权和Evidence链路内判定；不保证一定有结果。

仍须拒绝目录未提供的能力、写操作和其他不可表达的请求。输入安全准入保持先于模型，不扩大允许出域的输入。选择器不回答问题、不生成域/检索条件、不修正用户事实，也不承诺资料真实或当前有效。模型输出unsupported后仍终止，禁止本地强制改选Knowledge、按文档名/测试题号特判或建立第二条fallback。

下位L2_00_02 §6.3以独立action-selection-v5落实该职责：仅当前Knowledge启用组合根明确绑定v5；Knowledge关闭及既有直接模型组合根保留v4兼容。v4源文件、历史任务和冻结资产不改。fake验证证明任务合同、唯一选路和拒绝路径，不证明真实模型能稳定遵循语义要求。

## 5. 生产组合根与单动作不变量

默认stub仅空能力安全冒烟，不装配业务Provider；非stub生产目标Registry公开 `employee.search`、`employee.semantic_search` 和 `transaction.search`；仅当 `AGENT_KNOWLEDGE_ENABLED=true` 时追加且只追加一个 `knowledge.query`。旧 `employee.detail` 已核实仅由历史兼容测试及冻结资产使用，不进入目标生产 Registry。目标安全 catalog 必须承接 `contact_address → contactAddress` 的业务动作语义；未配置字段通过通用白名单自然不可达，具体字段与 DTO 映射仍归 Business L1/L2 所有。

生产 Business 对象图禁止 Local Resolver、ID-only selector、自动补全 filters、旧 fallback、跨域重试和第二次 handler 调用。Knowledge 由普通 capability selector 选择空参数动作，内部五阶段仍只对应一次 Core handler；不得进入 Business QueryPlan decoder/binder，也不得作为其失败后备。两类能力共享的 Core 单动作约束必须对“第二动作”统一拒绝。

`AGENT_KNOWLEDGE_ENABLED=false` 为默认值：不得注册 Knowledge、创建其 HTTP client 或要求其配置。启用时组合根必须先加载 Knowledge flow/retrieval/policy/task 快照，再创建三个有限 HTTP client（es-query-service、Embedding、Rerank），并把唯一 Provider 作为附加注册项装入既有 Runtime；关闭时由同一 Runtime lifecycle 精确释放这些 owned clients 和模型资源。重复 capability、重复 task、缺失依赖或快照不一致均使启动失败关闭。

单请求数据仅在内存存在；JWT、真实标识、slot 值和原始响应不得进入模型、日志或持久化。请求级时钟只为已证明正确的日期解析提供一致性；自然日相对查询在数据库时间精度/边界合同未关闭前 unsupported。

## 6. 关键架构决策

| 决策 | 内容 |
|---|---|
| `CR-AD-001` | Model 与 Business 分两级解码；Core 仍只认识稳定 ActionCandidate |
| `CR-AD-002` | 组合根一次装配三个现有接口动作与不可变字段配置 |
| `CR-AD-003` | 所有失败在对应职责层停止，禁止任何替代业务执行链路 |
| `CR-AD-004` | 既有 Knowledge 路径和公共 Core/HTTP 契约保持兼容 |
| `CR-AD-005` | Knowledge 采用默认关闭、同 Runtime 可选注册；不复制组合根，资源生命周期由顶层组合根统一拥有 |
| `CR-AD-006` | 能力选择按目录职责与请求操作分类，不承担资料存在性、时效、证据或个案适用性判断；Knowledge在既有链路内判定，unsupported不得由本地fallback覆盖 |

## 7. 下位 L2 详细设计与责任分解

| L2 | 唯一权威责任 |
|---|---|
| [`L2_00_00`](L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) v3.1 | Spring 接入、Runtime 协同及当前生产启动入口状态 |
| [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v3.1 | Business bridge、组合根、Registry、取消与单动作执行 |
| [`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v3.4 | 模型安全catalog、Business v7、共享严格输出协议，以及按能力职责选路的独立action-selection-v5 |
| [`L2_00_03`](L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) v3.1 | 用户 JWT 角色到 Servlet/Reactive Authority 的共享转换合同 |
| [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v3.1 | QueryPlan、多值引用、字段组合、行政区规范化、validator、binder 与出域策略 |
| [`L2_01_00`](L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) v3.6 | Knowledge开关、单注册、意图12及minimal-v1流程 |
| [`L2_01_01`](L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) v3.12 | typed读取、授权、融合/rerank及离线语料/结构/表示边界 |
| [`L2_01_02`](L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) v3.6 | Evidence/出域、Summary9有引用的有限回答及四维验收 |

## 8. 风险、验证与当前实施状态

应验证 Business 三动作不回退、Knowledge disabled 完全惰性、enabled 唯一注册、一次规划/一次 handler、并发请求隔离、取消/关闭、strict decoder、config snapshot、不支持条件零调用和 Business/Knowledge 互不 fallback。无须独立工作流引擎、复杂 circuit breaker、动态 registry、第二套 Runtime 或生产级治理平台。

旧模型任务和旧 production bridge 只证明各自历史合同，不能替代当前版本验收。v7 在 v6 裸 slot 合同之上要求显式字段不可被替换或丢弃；catalog 未开放的显式字段必须 exact unsupported，仍由模型理解语义、本地严格校验，且业务调用为 0。具体运行批次、调用计数和证据哈希由 UAT_00/evidence 管理。当前实现未增加字段专用黑名单、本地语义 Resolver、重复付费调用或 live 审计平台。

Knowledge 历史效果运行只作为效果诊断基线，不证明当前生产入口已接线或效果达标。生产对象图和功能 UAT 分别关闭接线、安全及失败语义；后续Knowledge效果运行按P3_01/UAT_02的版本绑定及独立精确授权控制；历史计划授权不恢复。

v3.2限定验证：v5独立Prompt与exact输出、未知/额外字段/unsupported零下游、当前启用入口可达、disabled及v4兼容、Business v7不变、输入保护、超时/取消和资源关闭。历史失败案例不改判；本次仅授权non-live修复，不包含新的真实调用。

本增量两轮作者内审（职责/兼容与追踪/冻结），一轮独立设计评审及一次S2修复复核：helper的Prompt hash位置耦合已按L2 §6.3纠正设计，无未关闭S0/S1/S2。独立执行单元未参与文档起草，核查源码和上位约束；未执行真实验证。L1/L2严格结构校验0错误0警告，不替代语义评审。
