# 架构文档索引

本页是当前 Agent 设计入口。当前权威顺序为：`REQ_00 → L0_00 → L1_* → L2_* → 代码与验证证据`。旧版正文和历史审计材料只用于追溯，不得覆盖当前设计。

## 1. 编号与状态规则

- `REQ_XX`：需求；`L0_XX`：总体架构；`L1_XX`：域/模块架构；`L2_<父 L1>_<序号>`：实施详细设计。
- 编号是稳定沟通标识，不表示实施顺序或状态。
- 设计状态只使用 `Draft / In Review / Approved / Deprecated`；代码实现、测试验证和部署生效状态分别记录，不能互相替代。
- 当前新基线统一为 v1.0；来源只在各文档首页声明，不继承旧版修订流水。

## 2. 需求与总体架构

| 编号 | 文档 | 版本/状态 | 阅读重点 |
|---|---|---|---|
| `REQ_00` | [单体 Agent 查询能力建设需求说明](REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v1.3 / 已确认 | 范围、验收、阶段边界 |
| `L0_00` | [单体 Agent L0 总体架构](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v1.0 / Approved | 系统边界、质量属性、关键决策、演进缝隙 |

## 3. L1 架构

| 编号 | 文档 | 版本/状态 | 治理范围 |
|---|---|---|---|
| `L1_00` | [核心与运行架构](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v1.0 / Approved | Spring 接入、Python Runtime、Core、Capability、模型接缝 |
| `L1_01` | [知识查询能力架构](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v1.0 / Approved | 问题改写、多域、多路召回/重排、证据与摘要、P5 |
| `L1_02` | [业务查询适配架构](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v1.0 / Approved | Business common、Employee/Transaction Adapter、最终授权 |

## 4. L2 详细设计

### 4.1 核心与运行（受 `L1_00` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_00_00` | [Spring 接入与 Runtime 协同](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v1.0 / Approved |
| `L2_00_01` | [Core 执行与能力注册](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v1.0 / Approved |
| `L2_00_02` | [DeepSeek 接入与受控生成](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v1.0 / Approved |
| `L2_00_03` | [用户角色 Authority Converter](design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v1.0 / Approved |

### 4.2 Knowledge（受 `L1_01` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_01_00` | [Knowledge 流程与配置](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v1.0 / Approved |
| `L2_01_01` | [Knowledge 检索与本地模型](design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v1.0 / Approved |
| `L2_01_02` | [Knowledge 证据、出域、摘要与效果验证](design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v1.0 / Approved |

### 4.3 Business（受 `L1_02` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_02_00` | [Business 公共约束、配置与出域](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v1.0 / Approved |
| `L2_02_01` | [Employee Adapter 与授权](design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v1.0 / Approved |
| `L2_02_02` | [Transaction Adapter 与授权](design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v1.0 / Approved |

## 5. 关键阅读结论

- 一个逻辑 Agent 由 Spring `agent-service` 与 Python `agent-runtime` 两个进程组成；LangGraph 是唯一编排权威，Spring 只负责接入与治理。
- Core 只执行一个已验证 Action；能力通过冻结 Registry 接入。新增能力不得在 Core 写域分支。
- Knowledge 是一个复合查询能力，流程固定为问题处理、逻辑域选择、检索计划、多路检索/融合/重排、证据与摘要；不新增 `knowledge-service`。
- Business 仅含 `employee.detail` 与 `transaction.search`。Adapter 透传用户 JWT，业务服务完成最终授权。
- 外部模型只接收各域明确允许的最小 payload；未知、敏感、冲突或未分类内容失败关闭。Business 真实结果出域默认关闭。
- 当前 Knowledge P5 已得到有效但 `ineffective` 的结论；这表示验证完成但效果未达阈值，不应改写为“未执行”或“已达标”。

## 6. 实施计划与历史归档

- 当前实施计划：[P3_00 单体 Agent 查询能力代码实施计划](plans/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)。计划是调度/证据索引，不得反向修改设计权威。
- 旧版 14 份设计文档：[2026-08-21 v0 基线归档](design/历史文档/2026-08-21-v0-baseline/)。
- 原业务设计审计附件：[审计附件](design/历史文档/审计附件/)。
- 归档规则：[历史文档说明](design/历史文档/README.md)。

## 7. 当前基线状态

14 份 v1.0 文档已完成内容重建、三轮内部自检和独立正式评审，当前统一为 `Approved`。本基线可作为后续 L2 对照代码评审的设计权威；代码实现、测试通过和部署生效仍需分别核实，不能由设计状态代替。
