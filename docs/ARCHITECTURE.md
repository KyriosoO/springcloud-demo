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

- [`REQ_00` 单体 Agent 查询能力建设需求说明](REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md)（v1.3，已确认）
- [`L0_00` 单体 Agent 查询能力 L0 总体架构设计](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md)（v0.5，已评审、有条件通过、`SA-GATE-001` 已关闭、未实施、未生效）
- [`L1_00` 单体 Agent 核心与运行架构 L1](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md)（v0.2，已评审、已通过、未实施、未生效；`CR-GATE-001` 已关闭）
- [`L1_01` 单体 Agent 知识查询能力架构 L1](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md)（v0.3，已评审、已通过、未实施、未生效；`KQ-GATE-001` 已关闭）
- [`L1_02` 单体 Agent 业务查询适配架构 L1](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md)（v0.2，已评审、已通过、未实施、未生效；`BQ-GATE-001` 已关闭）

## 当前 L2 详细设计

- [`L2_00_00` 单体 Agent Spring 接入与运行协同详细设计 L2](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md)（v0.2，Approved、五轮独立评审通过；`CR-GATE-002` Open，未实施、未生效）
- [`L2_00_01` 单体 Agent 核心执行与能力注册详细设计 L2](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md)（v0.4，Approved；v0.3 五轮评审、v0.4 针对性复评及业务 wire 的 Core JSON 边界检查均通过；`CR-GATE-002` Open，未实施、未生效）
- [`L2_00_02` 单体 Agent DeepSeek 模型接入与受控生成详细设计 L2](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md)（v0.4，Approved、五轮独立评审及 Knowledge 消费契约复评通过；模型实施/PoC/数据出域门禁 Open，未实施、未生效）
- [`L2_01_00` 单体 Agent Knowledge 查询流程与配置详细设计 L2](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md)（v0.2，Approved、五轮独立评审通过；`KQ-GATE-002` Open，未实施、未生效）
- [`L2_01_01` 单体 Agent Knowledge 检索与本地模型接入详细设计 L2](design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md)（v0.2，Approved、五轮独立评审通过；检索实施/集成门禁 Open，未实施、未生效）
- [`L2_02_00` 单体 Agent 业务查询公共约束、配置与出域详细设计 L2](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md)（v0.4，Approved；ExactDecimal/canonical JSON number 两轮独立复评及下游兼容检查通过；`BQ-GATE-002` 及真实业务/数据出域门禁 Open，未实施、未生效）
- [`L2_02_01` 单体 Agent Employee Adapter 与业务授权联调详细设计 L2](design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md)（v0.3，Approved；历史五轮评审、公共 v0.3 聚焦复核及公共 v0.4 GET/no-body 定向兼容检查通过；Provider/真实 Employee/出域门禁 Open，未实施、未生效）
- [`L2_02_02` 单体 Agent Transaction Adapter 与业务授权联调详细设计 L2](design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md)（v0.3，Approved；规范金额字符串→Decimal→JSON number→BigDecimal 条件两轮独立复评通过；Provider/真实 Transaction/出域门禁 Open，未实施、未生效）

## 已预留文档编号

| 文档编号 | 规划文档 | 上位文档 | 当前状态 |
|---|---|---|---|
| `L2_00_00` | 单体 Agent Spring 接入与运行协同 L2 | `L1_00` | 已创建（v0.2 Approved，五轮评审通过；实施门禁 Open） |
| `L2_00_02` | 单体 Agent DeepSeek 模型接入与受控生成 L2 | `L1_00` | 已创建（v0.4 Approved，五轮评审及针对性复评通过；实施/PoC 门禁 Open） |
| `L2_01_00` | 单体 Agent Knowledge 查询流程与配置 L2 | `L1_01` | 已创建（v0.2 Approved，五轮评审通过；实施门禁 Open） |
| `L2_01_01` | 单体 Agent Knowledge 检索与本地模型接入 L2 | `L1_01` | 已创建（v0.2 Approved，五轮独立评审通过；实施/集成门禁 Open） |
| `L2_01_02` | 单体 Agent Knowledge 证据、出域、摘要与效果验证 L2 | `L1_01` | 待创建 |
| `L2_02_00` | 单体 Agent 业务查询公共约束、配置与出域 L2 | `L1_02` | 已创建（v0.4 Approved；精确十进制 business wire 两轮复评及下游兼容检查通过；实施/集成门禁 Open） |
| `L2_02_01` | 单体 Agent Employee Adapter 与业务授权联调 L2 | `L1_02` | 已创建（v0.3 Approved；公共 v0.4 GET/no-body 定向兼容检查通过；Provider/集成门禁 Open） |
| `L2_02_02` | 单体 Agent Transaction Adapter 与业务授权联调 L2 | `L1_02` | 已创建（v0.3 Approved；精确金额条件两轮独立复评通过；Provider/集成门禁 Open） |

## 架构文档状态

- `L0_00` 总体架构：v0.3 五轮独立评审及 v0.4、v0.5 两次针对性复核均无剩余 S0/S1，项目维护者已完成确认，`SA-GATE-001` 保持关闭；v0.5 是当前三份 L1 的引用基线。
- `L1_00` 核心与运行架构：v0.2 已完成五轮评审并通过，明确 Spring 接入治理、LangGraph 唯一编排、确定性核心、差异化能力处理器形态、能力契约/注册、模型输入/结果出域边界及 DeepSeek 模型端口。
- `L1_01` Knowledge 架构：v0.2 已完成五轮独立评审并通过；v0.3 针对性复核关闭 `REV-KQ-009`，将逻辑域到物理资源拆为 Adapter 的“逻辑域→稳定检索 Profile”和 `es-query-service` 的“Profile→物理资源”两级权威；`KQ-GATE-001` 保持关闭。
- `L1_02` 业务查询适配架构：v0.2 已完成五轮独立评审并通过，关闭 `REV-BQ-001`～`REV-BQ-006`，明确业务服务拥有动作及响应数据可见性的最终授权、Adapter 只能二次收紧、最小有效用户结果、业务文本不可执行、回答事实绑定安全载荷，以及代码绑定有限转换；`BQ-GATE-001` 已关闭。
- `L2_00_01` 核心执行与能力注册详细设计：v0.3 已完成五轮独立评审—修订—复核并关闭 `REV-L2-001`～`009`；v0.4 对 `CapabilityExecutionContext.original_question` 及同源校验的针对性复评已关闭 `REV-L2-010`，对业务 wire 的 Core JSON 边界定向检查符合，当前为 Approved；`CR-GATE-002` 保持 Open。
- 第二批详细设计中，`L2_00_00` v0.2、`L2_00_02` v0.4、`L2_01_00` v0.2 仍为 Approved；`L2_02_00` v0.4 的精确十进制共享契约已完成两轮独立复评，`REV-BQCOM-023`～`025` 全部关闭，下游与 Core 定向兼容检查通过并恢复 Approved。连同 `L2_00_01`，这些 L2 均未实施、未生效，各自实施/集成门禁保持 Open。
- 第三批详细设计中，`L2_01_01` v0.2、`L2_02_01` v0.3 与 `L2_02_02` v0.3 均为 Approved；Employee 对公共 v0.4 的 GET/no-body 定向兼容检查通过，Transaction 的 amount/amount_gt/amount_lt 精确金额条件已完成两轮独立复评并关闭 `REV-TXN-021`；Date、聚合及写入口仍排除。三份均未实施、未生效，所有切片实施、Provider、真实集成和数据出域门禁保持 Open。
- `L2_01_02` 尚未建立。证据出域、摘要、效果验证，以及全部切片实施、外部契约变更和真实模型/数据集成均未完成。
- 已删除的旧 L0、L1、L2 文档及历史 Agent 实现不得反向提升为当前架构权威。

## 权威边界

- 当前权威顺序为：`REQ_00` → `L0_00` → `L1_*` → `L2_*` → 实现与验证证据。
- `L0_00` 已确认一个逻辑 Agent、Spring 接入治理进程、Python LangGraph 唯一编排运行时、DeepSeek `deepseek-v4-pro` 及本地 BGE 检索模型边界；具体接口、运行参数和实现仍由 L1/L2 治理。
- `L1_00` v0.2 是其权威范围内的 L2 编写基线，不改变 `L0_00` 状态，也不代表内部协议已定版、模型 PoC 已通过、实现已完成或真实数据允许进入外部模型。
- `L2_00_01` 当前权威版本为 v0.4 Approved，`REV-L2-010` 已关闭，业务 wire 的 Core JSON 边界定向检查符合；`CR-GATE-002` 获准前仍不得据此实施代码。Spring→Python 传输/入口上下文和真实 DeepSeek 契约分别由 `L2_00_00`、`L2_00_02` 承接。
- `L2_00_00` v0.2、`L2_00_01/02` v0.4、`L2_01_00` v0.2 与 `L2_02_00` v0.4 当前均为 Approved；严格校验或设计评审通过不代表实施门禁关闭、实现完成、真实 Provider/业务链路可用或真实数据允许出域。
- `L2_01_01` v0.2、`L2_02_01/02` v0.3 当前均为 Approved；Employee GET/no-body 和 Transaction 精确金额请求已完成公共 v0.4 兼容性检查。任何评审结论都不构成代码实施授权、Provider 契约确认、真实链路可用或真实数据出域证据。
- `L1_01` v0.3 是其权威范围内的 L2 编写基线，但仍未实施、未生效：2026-07-31 只读点测确认 ES 9.4.1、税务索引、Embedding 1024 维及 Rerank 当前最小 wire 可用，但这不等于真实集成通过；`es-query-service` 类型化只读契约、读取判定权威、Profile/快照、自动化负向契约和文档级出域元数据仍受 `SA-GATE-003/006` 约束。
- `L1_02` v0.2 是其权威范围内的 L2 编写基线，但仍未实施、未生效：现有业务只读候选接口、JWT 角色声明和业务服务当前实现只用于事实核实；最终动作映射、统一 Authority、业务最终授权、外部契约变化和业务字段出域仍受 `BQ-GATE-002/003`、`CR-GATE-003` 及 `SA-GATE-004/005/006` 约束。
- `auth-service`、`employee-service`、`mq-procedure-service`、`es-query-*`、网关、配置中心和通用组件可作为现状核实对象，但其既有实现不自动构成新 Agent 的目标架构。
- 文档状态、代码实现状态、验证状态和发布状态相互独立，不得以其中一项替代其他项。
