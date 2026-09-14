# 架构文档索引

本页是Agent统一文档基线v3.0的当前入口。本次启用独立的新文档版本序列，不表示软件/API/task/config/index变更；原高版本纳入v3.0不构成回滚，后续各文档可独立递增。当前权威顺序为：`REQ_00 → L0_00 → L1_* → L2_* → 代码与验证证据`。旧版正文和历史审计材料只用于追溯，不得覆盖当前设计。

## 1. 编号与状态规则

- `REQ_XX`：需求；`L0_XX`：总体架构；`L1_XX`：域/模块架构；`L2_<父 L1>_<序号>`：实施详细设计。
- 编号是稳定沟通标识，不表示实施顺序或状态。
- 设计状态只使用 `Draft / In Review / Approved / Deprecated（计划评审可用Reviewed）`；代码实现、测试验证和部署生效状态分别记录，不能互相替代。
- `REQ_00` v3.0；L0 v3.0、L1 Core/Knowledge/Business v3.0/v3.0/v3.0，L2版本见下表。P3 v3.0；UAT_00 v3.0、UAT_01 v3.0；ROADMAP_01 v3.0。新Knowledge设计与已实施/效果待验证严格分开；本索引不复制候选、门禁、哈希或动态测试总数。

## 2. 需求与总体架构

| 编号 | 文档 | 版本/状态 | 阅读重点 |
|---|---|---|---|
| `REQ_00` | [单体 Agent 查询能力建设需求说明](REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v3.0 / Approved | 三动作、filters QueryPlan、字段边界及 Knowledge 阶段 A 语料完整性 |
| `L0_00` | [单体 Agent L0 总体架构](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v3.0 / Approved | 系统边界、唯一链路、在线/离线 Knowledge 边界与权限 |

## 3. L1 架构

| 编号 | 文档 | 版本/状态 | 治理范围 |
|---|---|---|---|
| `L1_00` | [核心与运行架构](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v3.0 / Approved | Runtime、filters planning bridge、可选 Knowledge、Core 与共享 Registry/组合根 |
| `L1_01` | [知识查询能力架构](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v3.0 / Approved（新设计未实施） | 在线查询、资料组织与表示、证据及受控发布 |
| `L1_02` | [业务查询适配架构](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v3.0 / Approved | 三动作 Adapter、多值/组合字段配置、operator-specific 文本安全、最终授权与列表结果 |

## 4. L2 详细设计

### 4.1 核心与运行（受 `L1_00` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_00_00` | [Spring 接入与 Runtime 协同](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v3.0 / Approved |
| `L2_00_01` | [Core 执行与能力注册](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v3.0 / Approved |
| `L2_00_02` | [DeepSeek 接入与受控生成](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v3.0 / Approved |
| `L2_00_03` | [用户角色 Authority Converter](design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v3.0 / Approved |

### 4.2 Knowledge（受 `L1_01` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_01_00` | [Knowledge 流程与配置](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v3.0 / Approved（新设计未实施） |
| `L2_01_01` | [Knowledge 检索、本地模型与阶段 A 语料生命周期](design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v3.0 / Approved（新设计未实施） |
| `L2_01_02` | [Knowledge 证据、出域、摘要与效果验证](design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v3.0 / Approved（新设计未实施） |

### 4.3 Business（受 `L1_02` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_02_00` | [Business 公共约束、配置与出域](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v3.0 / Approved |
| `L2_02_01` | [Employee Adapter 与授权](design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v3.0 / Approved |
| `L2_02_02` | [Transaction Adapter 与授权](design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v3.0 / Approved |

## 5. 关键阅读结论

- 一个逻辑 Agent 由 Spring `agent-service` 与 Python `agent-runtime` 两个进程组成；LangGraph 是唯一编排权威，Spring 只负责接入与治理。
- Core 只执行一个已验证 Action；能力通过冻结 Registry 接入。新增能力不得在 Core 写域分支。
- Knowledge 是一个复合查询能力，在线流程固定为问题处理、逻辑域选择、检索计划、多路检索/融合/重排、证据与摘要；阶段 A 离线语料工具与在线请求隔离，不新增 `knowledge-service`。
- Business 目标动作是 `employee.search`、`employee.semantic_search` 与 `transaction.search`；`employee.detail` 仅保留历史兼容调用方，不在目标生产组合根。Adapter 透传用户 JWT，业务服务完成最终授权。
- 外部模型只接收各域明确允许的最小 payload；未知、敏感、冲突或未分类内容失败关闭。Business 真实结果出域默认关闭。
- Knowledge 最新有效效果等级为 `partially_effective`，不等于整体效果达标；具体候选、运行结论和证据由 UAT_01/evidence 管理。

## 6. 实施计划与历史归档

- ARCHITECTURE.md自身纳入v3.0，索引复核Reviewed；原20文件归档与完整性见[本次归档](历史文档/2026-09-14-unified-v3-baseline/README.md)，取舍、评审和验证见[整理记录](历史文档/2026-09-14-unified-v3-baseline/MIGRATION.md)。
- 当前实施计划：[P3_00 单体 Agent 查询能力实施与收口计划](plans/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)，v3.0 / Reviewed；工作包、Gate、当前验证和提交状态只在该计划维护。
- 当前验收计划：[UAT_00 单体 Agent 结构化查询用户验收计划](plans/UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md)，v3.0 / Reviewed；Knowledge 在线与资料专项验收由 [UAT_01](plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) v3.0 独立治理。后续演进见 [ROADMAP_01](plans/ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md) v3.0。
- 本次被替换的需求、设计和计划分别归档至 [需求历史目录](历史文档/)、[设计历史目录](design/历史文档/) 和 [计划历史目录](plans/历史文档/)；历史文档仅用于追溯，不是当前实施权威。
- 批量发现当前设计时只扫描 `docs/design` 顶层，使用 `--non-recursive`，或显式使用 `--exclude '历史文档/**'`；归档来源链接与历史候选只能用于追溯，不能被纳入当前评审目标或替代现行上位文档。
- 更早版本的 14 份设计文档：[2026-08-21 v0 基线归档](design/历史文档/2026-08-21-v0-baseline/)。
- 原业务设计审计附件：[审计附件](design/历史文档/审计附件/)。
- 归档规则：[历史文档说明](design/历史文档/README.md)。

## 7. 当前基线状态

Employee/Transaction及原Knowledge功能UAT保持原证明范围。当前仓库Knowledge默认关闭，源码11/7/quality-v3；目标意图12/Summary8最小链路及资料组织/表示方案均待实施、待验证。本轮不核实运行部署或重做UAT，不宣称效果改善；图谱仍为后续方向。已取消优化目标不恢复。文档评审、实施、部署及验收分别管理。
