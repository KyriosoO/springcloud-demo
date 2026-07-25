# 架构文档索引

本仓库新的 Agent 设计以已确认需求为当前需求基线。原 `docs/design/agent/` 下的旧 Agent 设计已退出当前工作区，不得作为新设计或实现依据。

## 文档编号规则

- 文档编号是稳定沟通标识，不表示实施顺序、优先级或正式状态；分配后不得因文档顺序变化而重排或复用。
- 文档编号不替代文档内部既有的“文档标识”、架构决策 ID 或门禁 ID。
- 需求文档使用 `REQ_XX`，总体架构使用 `L0_XX`，分域/模块架构使用 `L1_XX`。
- L2 使用 `L2_<父 L1 两位序号>_<本级两位序号>`；例如 `L2_00_01` 表示由 `L1_00` 治理的第二份 L2。
- 文件名使用 `<文档编号>_<英文语义名>.md`；Markdown 标题和治理信息同时显示文档编号。
- `ARCHITECTURE.md` 是固定仓库入口，不分配编号、不改名。

## 当前有效文档

- [`REQ_00` 单体 Agent 查询能力建设需求说明](REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md)（v1.2，已确认）
- [`L0_00` 单体 Agent 查询能力 L0 总体架构设计](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md)（v0.4，已评审、有条件通过、`SA-GATE-001` 已关闭、未实施、未生效）
- [`L1_00` 单体 Agent 核心与运行架构 L1](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md)（v0.2，已评审、已通过、未实施、未生效；`CR-GATE-001` 已关闭）
- [`L1_01` 单体 Agent 知识查询能力架构 L1](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md)（v0.2，已评审、已通过、未实施、未生效；`KQ-GATE-001` 已关闭）
- [`L1_02` 单体 Agent 业务查询适配架构 L1](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md)（v0.2，已评审、已通过、未实施、未生效；`BQ-GATE-001` 已关闭）

## 当前在编文档

- [`L2_00_00` 单体 Agent Spring 接入与运行协同详细设计 L2](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md)（v0.1，Draft、严格校验通过、未独立评审、未实施、未生效）
- [`L2_00_01` 单体 Agent 核心执行与能力注册详细设计 L2](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md)（v0.4，In Review；v0.3 的五轮评审结论保留，`REV-L2-010` Open；未实施、未生效）
- [`L2_00_02` 单体 Agent DeepSeek 模型接入与受控生成详细设计 L2](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md)（v0.1，Draft、严格校验通过、未独立评审、未实施、未生效）
- [`L2_01_00` 单体 Agent Knowledge 查询流程与配置详细设计 L2](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md)（v0.1，Draft、严格校验通过、未独立评审、未实施、未生效）
- [`L2_02_00` 单体 Agent 业务查询公共约束、配置与出域详细设计 L2](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md)（v0.1，Draft、严格校验通过、未独立评审、未实施、未生效）

## 已预留文档编号

| 文档编号 | 规划文档 | 上位文档 | 当前状态 |
|---|---|---|---|
| `L2_00_00` | 单体 Agent Spring 接入与运行协同 L2 | `L1_00` | 已创建（v0.1 Draft，严格校验通过，未独立评审） |
| `L2_00_02` | 单体 Agent DeepSeek 模型接入与受控生成 L2 | `L1_00` | 已创建（v0.1 Draft，严格校验通过，未独立评审） |
| `L2_01_00` | 单体 Agent Knowledge 查询流程与配置 L2 | `L1_01` | 已创建（v0.1 Draft，严格校验通过，未独立评审） |
| `L2_01_01` | 单体 Agent Knowledge 检索与本地模型接入 L2 | `L1_01` | 待创建 |
| `L2_01_02` | 单体 Agent Knowledge 证据、出域、摘要与效果验证 L2 | `L1_01` | 待创建 |
| `L2_02_00` | 单体 Agent 业务查询公共约束、配置与出域 L2 | `L1_02` | 已创建（v0.1 Draft，严格校验通过，未独立评审） |
| `L2_02_01` | 单体 Agent Employee Adapter 与业务授权联调 L2 | `L1_02` | 待创建 |
| `L2_02_02` | 单体 Agent Transaction Adapter 与业务授权联调 L2 | `L1_02` | 待创建 |

## 架构文档状态

- `L0_00` 总体架构：v0.3 五轮独立评审及 v0.4 针对性复核均无剩余 S0/S1，项目维护者已完成确认，`SA-GATE-001` 已关闭；v0.4 是当前三份 L1 的编写基线。
- `L1_00` 核心与运行架构：v0.2 已完成五轮评审并通过，明确 Spring 接入治理、LangGraph 唯一编排、确定性核心、差异化能力处理器形态、能力契约/注册、模型输入/结果出域边界及 DeepSeek 模型端口。
- `L1_01` Knowledge 架构：v0.2 已完成五轮独立评审并通过，关闭 `REV-KQ-001`～`REV-KQ-008`，明确读取授权先于候选正文/BGE、失败优先级、按 L2 切片实施门禁、上位决策追踪和可验证多域边界；`KQ-GATE-001` 已关闭。
- `L1_02` 业务查询适配架构：v0.2 已完成五轮独立评审并通过，关闭 `REV-BQ-001`～`REV-BQ-006`，明确业务服务拥有动作及响应数据可见性的最终授权、Adapter 只能二次收紧、最小有效用户结果、业务文本不可执行、回答事实绑定安全载荷，以及代码绑定有限转换；`BQ-GATE-001` 已关闭。
- `L2_00_01` 核心执行与能力注册详细设计：v0.3 已完成五轮独立评审—修订—复核并进入 Approved，关闭 `REV-L2-001`～`REV-L2-009`；第二批 Knowledge L2 发现权威原始问题无法由处理器取得后，v0.4 以最小契约补正增加 `CapabilityExecutionContext.original_question` 及同源校验，当前回到 In Review，`REV-L2-010` 保持 Open。v0.3 的评审证据仍保留，但不替代 v0.4 针对性复评；`CR-GATE-002` 保持 Open。
- 第二批四份 L2 已建立为 v0.1 Draft，并均通过严格文档校验：`L2_00_00` 固化 Spring 接入、跨进程协议、总时限与取消；`L2_00_02` 固化 DeepSeek Provider、输入闸门、结构化动作和受控生成；`L2_01_00` 固化 Knowledge 单动作流程、问题改写、多域选择与检索计划；`L2_02_00` 固化业务查询公共配置、JWT/Authority 消费、字段交集、有限转换与安全载荷。严格校验不等于独立评审、实施授权或运行证据。
- `L2_01_01`、`L2_01_02`、`L2_02_01`、`L2_02_02` 尚未建立。切片实施、外部契约变更、真实模型/数据集成和效果证据均未完成。
- 已删除的旧 L0、L1、L2 文档及历史 Agent 实现不得反向提升为当前架构权威。

## 权威边界

- 当前权威顺序为：`REQ_00` → `L0_00` → `L1_*` → `L2_*` → 实现与验证证据。
- `L0_00` 已确认一个逻辑 Agent、Spring 接入治理进程、Python LangGraph 唯一编排运行时、DeepSeek `deepseek-v4-pro` 及本地 BGE 检索模型边界；具体接口、运行参数和实现仍由 L1/L2 治理。
- `L1_00` v0.2 是其权威范围内的 L2 编写基线，不改变 `L0_00` 状态，也不代表内部协议已定版、模型 PoC 已通过、实现已完成或真实数据允许进入外部模型。
- `L2_00_01` 当前权威版本为 v0.4 In Review；v0.3 的五轮 Approved 评审证据仅适用于变更前基线。`REV-L2-010` 关闭且 `CR-GATE-002` 获准前，v0.4 不得作为代码实施授权。Spring→Python 传输/入口上下文和真实 DeepSeek 契约分别由 `L2_00_00`、`L2_00_02` 承接。
- `L2_00_00`、`L2_00_02`、`L2_01_00`、`L2_02_00` 当前均为 v0.1 Draft；严格文档校验只证明确定性结构规则通过，不代表独立评审、门禁关闭、实现完成或真实链路可用。
- `L1_01` v0.2 是其权威范围内的 L2 编写基线，但仍未实施、未生效：2026-07-25 的 ES/BGE 点测可用不等于真实集成通过；当前 `es-query-service` 类型化只读契约、读取判定权威和文档级出域元数据仍受 `SA-GATE-003/006` 约束。
- `L1_02` v0.2 是其权威范围内的 L2 编写基线，但仍未实施、未生效：现有业务只读候选接口、JWT 角色声明和业务服务当前实现只用于事实核实；最终动作映射、统一 Authority、业务最终授权、外部契约变化和业务字段出域仍受 `BQ-GATE-002/003`、`CR-GATE-003` 及 `SA-GATE-004/005/006` 约束。
- `auth-service`、`employee-service`、`mq-procedure-service`、`es-query-*`、网关、配置中心和通用组件可作为现状核实对象，但其既有实现不自动构成新 Agent 的目标架构。
- 文档状态、代码实现状态、验证状态和发布状态相互独立，不得以其中一项替代其他项。
