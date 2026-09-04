# 架构文档索引

本页是当前 Agent 设计入口。当前权威顺序为：`REQ_00 → L0_00 → L1_* → L2_* → 代码与验证证据`。旧版正文和历史审计材料只用于追溯，不得覆盖当前设计。

## 1. 编号与状态规则

- `REQ_XX`：需求；`L0_XX`：总体架构；`L1_XX`：域/模块架构；`L2_<父 L1>_<序号>`：实施详细设计。
- 编号是稳定沟通标识，不表示实施顺序或状态。
- 设计状态只使用 `Draft / In Review / Approved / Deprecated`；代码实现、测试验证和部署生效状态分别记录，不能互相替代。
- `REQ_00` v2.4；L0 v2.8、L1 Core/Knowledge/Business v3.5/v1.16/v2.8，10份L2当前版本见下表。实施计划P3 v2.42；验收计划UAT_00 v1.24、UAT_01 v1.20；路线图ROADMAP_01 v0.8。阶段B新增语义仍须按评审和实施事实分开管理，不继承历史通过结论。本索引不复制工作包、Gate、candidate、哈希或动态测试总数。

## 2. 需求与总体架构

| 编号 | 文档 | 版本/状态 | 阅读重点 |
|---|---|---|---|
| `REQ_00` | [单体 Agent 查询能力建设需求说明](REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v2.4 / Approved | 三动作、filters QueryPlan、字段边界及 Knowledge 阶段 A 语料完整性 |
| `L0_00` | [单体 Agent L0 总体架构](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v2.8 / Approved | 系统边界、唯一链路、在线/离线 Knowledge 边界与权限 |

## 3. L1 架构

| 编号 | 文档 | 版本/状态 | 治理范围 |
|---|---|---|---|
| `L1_00` | [核心与运行架构](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v3.5 / Approved | Runtime、filters planning bridge、可选 Knowledge、Core 与共享 Registry/组合根 |
| `L1_01` | [知识查询能力架构](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v1.16 / Approved | 在线查询及离线语料构建平面、证据与受控发布 |
| `L1_02` | [业务查询适配架构](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v2.8 / Approved | 三动作 Adapter、多值/组合字段配置、operator-specific 文本安全、最终授权与列表结果 |

## 4. L2 详细设计

### 4.1 核心与运行（受 `L1_00` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_00_00` | [Spring 接入与 Runtime 协同](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v1.3 / Approved |
| `L2_00_01` | [Core 执行与能力注册](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v2.3 / Approved |
| `L2_00_02` | [DeepSeek 接入与受控生成](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v2.7 / Approved |
| `L2_00_03` | [用户角色 Authority Converter](design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v1.3 / Approved |

### 4.2 Knowledge（受 `L1_01` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_01_00` | [Knowledge 流程与配置](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v1.16 / Approved |
| `L2_01_01` | [Knowledge 检索、本地模型与阶段 A 语料生命周期](design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v2.6 / Approved |
| `L2_01_02` | [Knowledge 证据、出域、摘要与效果验证](design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v1.17 / Approved |

### 4.3 Business（受 `L1_02` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_02_00` | [Business 公共约束、配置与出域](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v2.8 / Approved |
| `L2_02_01` | [Employee Adapter 与授权](design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.8 / Approved |
| `L2_02_02` | [Transaction Adapter 与授权](design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.6 / Approved |

## 5. 关键阅读结论

- 一个逻辑 Agent 由 Spring `agent-service` 与 Python `agent-runtime` 两个进程组成；LangGraph 是唯一编排权威，Spring 只负责接入与治理。
- Core 只执行一个已验证 Action；能力通过冻结 Registry 接入。新增能力不得在 Core 写域分支。
- Knowledge 是一个复合查询能力，在线流程固定为问题处理、逻辑域选择、检索计划、多路检索/融合/重排、证据与摘要；阶段 A 离线语料工具与在线请求隔离，不新增 `knowledge-service`。
- Business 目标动作是 `employee.search`、`employee.semantic_search` 与 `transaction.search`；`employee.detail` 仅保留历史兼容调用方，不在目标生产组合根。Adapter 透传用户 JWT，业务服务完成最终授权。
- 外部模型只接收各域明确允许的最小 payload；未知、敏感、冲突或未分类内容失败关闭。Business 真实结果出域默认关闭。
- Knowledge 最新有效效果等级为 `partially_effective`，不等于整体效果达标；具体候选、运行结论和证据由 UAT_01/evidence 管理。

## 6. 实施计划与历史归档

- 当前实施计划：[P3_00 单体 Agent 查询能力实施与收口计划](plans/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)，v2.41 / Reviewed；工作包、Gate、当前验证和提交状态只在该计划维护。
- 当前验收计划：[UAT_00 单体 Agent 结构化查询用户验收计划](plans/UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md)，v1.24 / Reviewed；Knowledge 在线与阶段 A 语料专项验收由 [UAT_01](plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) v1.19 独立治理。后续演进见 [ROADMAP_01](plans/ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md) v0.7。
- 本次被替换的需求、设计和计划分别归档至 [需求历史目录](历史文档/)、[设计历史目录](design/历史文档/) 和 [计划历史目录](plans/历史文档/)；历史文档仅用于追溯，不是当前实施权威。
- 批量发现当前设计时只扫描 `docs/design` 顶层，使用 `--non-recursive`，或显式使用 `--exclude '历史文档/**'`；归档来源链接与历史候选只能用于追溯，不能被纳入当前评审目标或替代现行上位文档。
- 更早版本的 14 份设计文档：[2026-08-21 v0 基线归档](design/历史文档/2026-08-21-v0-baseline/)。
- 原业务设计审计附件：[审计附件](design/历史文档/审计附件/)。
- 归档规则：[历史文档说明](design/历史文档/README.md)。

## 7. 当前基线状态

Employee/Transaction 需求、设计与35/35 UAT 已完成且不得回退。Knowledge 默认关闭的生产接线、功能 UAT 37/37、域目录 v2、Summary V4 与效果口径 v2 已实施；阶段 A 正文及附件完整性已完成审计、版本化处理、candidate 索引、14/14专项 UAT 和受控发布。最新有效效果等级仍为 `partially_effective`；阶段 B 检索质量和图谱尚未实施。具体 Gate、candidate、测试总数和 evidence 只在 P3、UAT_01 与 evidence 中维护。
