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
- [`L0_00` 单体 Agent 查询能力 L0 总体架构设计](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md)（v0.5，已评审、有条件通过、`SA-GATE-001` 已关闭；Core、Access、Model local、Knowledge 和 Business 本地 fake/stub 切片已实施验证，未生效）
- [`L1_00` 单体 Agent 核心与运行架构 L1](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md)（v0.2，已评审、已通过；Core、Access 契约、本地 stub 模型边界及 HTTP/Spring 双进程本地链已实施验证，真实模型与领域能力仍未实施，未生效；`CR-GATE-001` 已关闭）
- [`L1_01` 单体 Agent 知识查询能力架构 L1](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md)（v0.3，已评审、已通过；三份 L2 的本地 fake/stub 生产代码切片已实施验证，真实检索/出域/P5 未实施，未生效；`KQ-GATE-001` 已关闭）
- [`L1_02` 单体 Agent 业务查询适配架构 L1](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md)（v0.2，已评审、已通过；Business common 与两个 Python fake Adapter 已实施验证，Java Provider/真实授权/出域未实施，未生效；`BQ-GATE-001` 已关闭）

## 当前 L2 详细设计

- [`L2_00_00` 单体 Agent Spring 接入与运行协同详细设计 L2](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md)（v0.4，Approved、五轮独立设计评审通过；OpenAPI、Runtime HTTP、Spring 接入和本地双进程 stub 已实现验证，`CR-GATE-002` Closed；未部署、未生效）
- [`L2_00_01` 单体 Agent 核心执行与能力注册详细设计 L2](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md)（v0.5，Approved；Core 实现、61 项测试和两轮代码对照设计评审通过；`CR-GATE-002` Closed，未部署、未生效）
- [`L2_00_02` 单体 Agent DeepSeek 模型接入与受控生成详细设计 L2](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md)（v0.6，Approved；隔离 DeepSeek transport、fake 验证与固定 30 action+6 answer PoC 已完成；action 29/30，`SA-GATE-002` 及 Runtime live/数据出域门禁 Open，未生效）
- [`L2_01_00` 单体 Agent Knowledge 查询流程与配置详细设计 L2](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md)（v0.4，Approved；`WP-KFLOW-01` 本地 fake/stub 切片已实施验证，`KQ-GATE-002` Closed；真实检索/模型/出域未实施、未生效）
- [`L2_01_01` 单体 Agent Knowledge 检索与本地模型接入详细设计 L2](design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md)（v0.4，Approved；`WP-KRET-PY-01` Python fake 切片已实施验证；ES Provider 因统一 Authority converter 前置不足停止，真实 ES/BGE 仍 Open，未生效）
- [`L2_01_02` 单体 Agent Knowledge 证据、出域、摘要与效果验证详细设计 L2](design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md)（v0.4，Approved；`WP-KEV-01` 合成/stub 与 `WP-KP5-HARNESS-01` synthetic harness 已实施验证；代表性数据集、live P5、真实策略目录/出域仍 Open，未生效）
- [`L2_02_00` 单体 Agent 业务查询公共约束、配置与出域详细设计 L2](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md)（v0.5，Approved；`WP-BQCOMMON-01` fake-domain 切片已实施验证，`BQ-GATE-002` Closed；真实业务/数据出域仍 Open，未生效）
- [`L2_02_01` 单体 Agent Employee Adapter 与业务授权联调详细设计 L2](design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md)（v0.5，Approved；`WP-EMP-ADAPTER-01` Python fake Adapter 已实施验证；Provider 因完整响应可见性、调用方和统一 Authority 前置不足停止，真实 Employee/出域仍 Open，未生效）
- [`L2_02_02` 单体 Agent Transaction Adapter 与业务授权联调详细设计 L2](design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md)（v0.5，Approved；`WP-TXN-ADAPTER-01` Python fake Adapter/ExactDecimal 已实施验证；Provider 因生产 precision/scale、调用方和统一 Authority 前置不足停止，真实 Transaction/出域仍 Open，未生效）

## 当前实施计划

- [`P3_00` 单体 Agent 查询能力代码实施计划](plans/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)（v0.7，Approved；14 个工作包 Done，13 个工作包 Blocked，0 个 Ready；Model PoC action 29/30，三项 Java Provider 按前置条件停止；不构成其余代码、外部调用或 Git 授权）

## 已预留文档编号

| 文档编号 | 规划文档 | 上位文档 | 当前状态 |
|---|---|---|---|
| `L2_00_00` | 单体 Agent Spring 接入与运行协同 L2 | `L1_00` | 已创建（v0.4 Approved；契约、HTTP/Spring 和本地双进程 stub 已实现验证，`CR-GATE-002` Closed） |
| `L2_00_02` | 单体 Agent DeepSeek 模型接入与受控生成 L2 | `L1_00` | 已创建（v0.6 Approved；隔离 transport/PoC 已执行，action 29/30；Runtime live/出域门禁 Open） |
| `L2_01_00` | 单体 Agent Knowledge 查询流程与配置 L2 | `L1_01` | 已创建（v0.4 Approved；本地 flow fake/stub 切片已实施验证；真实集成门禁 Open） |
| `L2_01_01` | 单体 Agent Knowledge 检索与本地模型接入 L2 | `L1_01` | 已创建（v0.4 Approved；Python fake retrieval 已实施验证；ES Provider 前置阻断/真实集成门禁 Open） |
| `L2_01_02` | 单体 Agent Knowledge 证据、出域、摘要与效果验证 L2 | `L1_01` | 已创建（v0.4 Approved；Evidence 合成/stub 与 P5 synthetic harness 已实施验证；代表性数据集/live P5/真实出域门禁 Open） |
| `L2_02_00` | 单体 Agent 业务查询公共约束、配置与出域 L2 | `L1_02` | 已创建（v0.5 Approved；fake-domain common 已实施验证；真实集成/出域门禁 Open） |
| `L2_02_01` | 单体 Agent Employee Adapter 与业务授权联调 L2 | `L1_02` | 已创建（v0.5 Approved；Python fake Adapter 已实施验证；Provider 前置阻断/真实集成门禁 Open） |
| `L2_02_02` | 单体 Agent Transaction Adapter 与业务授权联调 L2 | `L1_02` | 已创建（v0.5 Approved；Python fake Adapter/ExactDecimal 已实施验证；Provider 前置阻断/真实集成门禁 Open） |

## 架构文档状态

- `L0_00` 总体架构：v0.3 五轮独立评审及 v0.4、v0.5 两次针对性复核均无剩余 S0/S1，项目维护者已完成确认，`SA-GATE-001` 保持关闭；v0.5 是当前三份 L1 的引用基线。
- `L1_00` 核心与运行架构：v0.2 已完成五轮评审并通过，明确 Spring 接入治理、LangGraph 唯一编排、确定性核心、差异化能力处理器形态、能力契约/注册、模型输入/结果出域边界及 DeepSeek 模型端口。
- `L1_01` Knowledge 架构：v0.2 已完成五轮独立评审并通过；v0.3 针对性复核关闭 `REV-KQ-009`，将逻辑域到物理资源拆为 Adapter 的“逻辑域→稳定检索 Profile”和 `es-query-service` 的“Profile→物理资源”两级权威；`KQ-GATE-001` 保持关闭。
- `L1_02` 业务查询适配架构：v0.2 已完成五轮独立评审并通过，关闭 `REV-BQ-001`～`REV-BQ-006`，明确业务服务拥有动作及响应数据可见性的最终授权、Adapter 只能二次收紧、最小有效用户结果、业务文本不可执行、回答事实绑定安全载荷，以及代码绑定有限转换；`BQ-GATE-001` 已关闭。
- `L2_00_01` 核心执行与能力注册详细设计：v0.3/v0.4 评审结论保持有效；v0.5 已完成模型无关 Core 实现、61 项测试、严格类型/依赖验证和两轮代码对照设计评审，`CR-GATE-002` 已关闭；未部署、未生效，且不授权 HTTP、领域或真实模型。
- Knowledge 三份详细设计已同步为 `L2_01_00` v0.4、`L2_01_01` v0.4、`L2_01_02` v0.4 Approved；Flow、Python Retrieval、Evidence/Policy/Summary 与 P5 synthetic harness 已实施验证。ES Provider 因统一 Authority converter 前置不足停止；真实 ES/BGE、知识正文、DeepSeek 出域、代表性数据集和 live P5 仍未实施，相关门禁保持 Open。
- Business 三份详细设计已同步为 `L2_02_00` v0.5、`L2_02_01` v0.5、`L2_02_02` v0.5 Approved；Business common 与两个 Python fake Adapter 已实施验证。Employee/Transaction Java Provider 分别因可见性/调用方/Authority 和生产精度/调用方/Authority 前置不足停止；真实 JWT、真实业务数据与模型出域仍未实施，相关门禁保持 Open；Date、聚合与写入口继续排除。
- 已删除的旧 L0、L1、L2 文档及历史 Agent 实现不得反向提升为当前架构权威。

## 权威边界

- 当前权威顺序为：`REQ_00` → `L0_00` → `L1_*` → `L2_*` → 实现与验证证据。
- `L0_00` 已确认一个逻辑 Agent、Spring 接入治理进程、Python LangGraph 唯一编排运行时、DeepSeek `deepseek-v4-pro` 及本地 BGE 检索模型边界；具体接口、运行参数和实现仍由 L1/L2 治理。
- `L1_00` v0.2 是其权威范围内的 L2 编写基线，不改变 `L0_00` 状态，也不代表内部协议已定版、模型 PoC 已通过、实现已完成或真实数据允许进入外部模型。
- `L2_00_01` 当前权威版本为 v0.5 Approved，Core `CR-GATE-002` 已关闭且限定实现验证完成；该结论不授权 Spring→Python HTTP、真实 DeepSeek 或领域能力，三者分别由 `L2_00_00`、`L2_00_02` 和领域 L2 承接。
- 九份 L2 当前均为 Approved；Core、Access、Model local、Knowledge 与 Business 的十二个本地 fake/stub 工作包已建立限定实施证据。该结论不代表真实 Provider/业务链路可用、Gateway/生产生效、真实数据允许出域或 P5 效果通过。
- `L1_01` v0.3 是 Knowledge 权威基线：本地 Flow/Retrieval/Evidence fake/stub 切片已实施验证；2026-07-31 的 ES/BGE 只读点测仍只是易漂移事实。`es-query-service` 类型化端点、读取判定、Profile/快照、真实正文与文档级出域仍受 `SA-GATE-003/006` 及 P3 入口门禁约束。
- `L1_02` v0.2 是 Business 权威基线：Business common 与两个 Python fake Adapter 已实施验证；最终动作服务端映射、统一 Authority、业务最终授权、外部契约变化、真实 JWT 和业务字段出域仍受 `BQ-GATE-003`、`CR-GATE-003` 及 `SA-GATE-004/005/006` 约束。
- `auth-service`、`employee-service`、`mq-procedure-service`、`es-query-*`、网关、配置中心和通用组件可作为现状核实对象，但其既有实现不自动构成新 Agent 的目标架构。
- 文档状态、代码实现状态、验证状态和发布状态相互独立，不得以其中一项替代其他项。
