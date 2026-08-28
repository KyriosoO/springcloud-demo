# 架构文档索引

本页是当前 Agent 设计入口。当前权威顺序为：`REQ_00 → L0_00 → L1_* → L2_* → 代码与验证证据`。旧版正文和历史审计材料只用于追溯，不得覆盖当前设计。

## 1. 编号与状态规则

- `REQ_XX`：需求；`L0_XX`：总体架构；`L1_XX`：域/模块架构；`L2_<父 L1>_<序号>`：实施详细设计。
- 编号是稳定沟通标识，不表示实施顺序或状态。
- 设计状态只使用 `Draft / In Review / Approved / Deprecated`；代码实现、测试验证和部署生效状态分别记录，不能互相替代。
- `REQ_00` v2.0 继续作为需求权威；当前设计基线为 L0 v2.2、L1 Core/Knowledge/Business v2.7/v1.5/v2.5，14 份 L2 的当前版本见下表。实施计划为 P3 v2.22，Business/Knowledge 验收计划分别为 UAT_00 v1.16、UAT_01 v1.5。

## 2. 需求与总体架构

| 编号 | 文档 | 版本/状态 | 阅读重点 |
|---|---|---|---|
| `REQ_00` | [单体 Agent 查询能力建设需求说明](REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v2.0 / Approved | 三动作、filters QueryPlan、字段边界与验收 |
| `L0_00` | [单体 Agent L0 总体架构](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v2.2 / Approved | 系统边界、唯一链路、权限与分域决策 |

## 3. L1 架构

| 编号 | 文档 | 版本/状态 | 治理范围 |
|---|---|---|---|
| `L1_00` | [核心与运行架构](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v2.7 / Approved | Runtime、filters planning bridge、可选 Knowledge、Core 与共享 Registry/组合根 |
| `L1_01` | [知识查询能力架构](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v1.5 / Approved | 问题改写、多域、多路召回/重排、证据与摘要、P5 |
| `L1_02` | [业务查询适配架构](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v2.5 / Approved | 三动作 Adapter、字段级配置、operator-specific 文本安全、端点级角色转换、最终授权与列表结果 |

## 4. L2 详细设计

### 4.1 核心与运行（受 `L1_00` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_00_00` | [Spring 接入与 Runtime 协同](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v1.2 / Approved |
| `L2_00_01` | [Core 执行与能力注册](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v2.2 / Approved |
| `L2_00_02` | [DeepSeek 接入与受控生成](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v2.3 / Approved |
| `L2_00_03` | [用户角色 Authority Converter](design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v1.2 / Approved |

### 4.2 Knowledge（受 `L1_01` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_01_00` | [Knowledge 流程与配置](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v1.6 / Approved |
| `L2_01_01` | [Knowledge 检索与本地模型](design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v1.5 / Approved |
| `L2_01_02` | [Knowledge 证据、出域、摘要与效果验证](design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v1.6 / Approved |

### 4.3 Business（受 `L1_02` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_02_00` | [Business 公共约束、配置与出域](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v2.5 / Approved |
| `L2_02_01` | [Employee Adapter 与授权](design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.5 / Approved |
| `L2_02_02` | [Transaction Adapter 与授权](design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.5 / Approved |

## 5. 关键阅读结论

- 一个逻辑 Agent 由 Spring `agent-service` 与 Python `agent-runtime` 两个进程组成；LangGraph 是唯一编排权威，Spring 只负责接入与治理。
- Core 只执行一个已验证 Action；能力通过冻结 Registry 接入。新增能力不得在 Core 写域分支。
- Knowledge 是一个复合查询能力，流程固定为问题处理、逻辑域选择、检索计划、多路检索/融合/重排、证据与摘要；不新增 `knowledge-service`。
- Business 目标动作是 `employee.search`、`employee.semantic_search` 与 `transaction.search`；`employee.detail` 仅保留历史兼容调用方，不在目标生产组合根。Adapter 透传用户 JWT，业务服务完成最终授权。
- 外部模型只接收各域明确允许的最小 payload；未知、敏感、冲突或未分类内容失败关闭。Business 真实结果出域默认关闭。
- Knowledge candidate-04 是历史有效运行且结论为 `ineffective`；candidate-05 是最新有效运行，Q1/Q2 通过、Q3/Q4 未通过，结论为 `partially_effective`。两者都不得改写为整体效果达标。

## 6. 实施计划与历史归档

- 当前实施计划：[P3_00 单体 Agent 查询能力代码实施计划](plans/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)，v2.22 / Reviewed；既有 25 个工作包 Done，本轮新增 7 个收口包中，文档纠偏与正式 Python 测试入口已 Done，效果诊断 Ready，后续优化、候选、live 和最终收口按依赖推进。
- 当前验收计划：[UAT_00 单体 Agent 查询用户验收计划](plans/UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md)，v1.16 / Reviewed；18 项真实 v4 QueryPlan 与 17 项等价自动化风险闭合，共 35/35 可追踪。Knowledge 由 [UAT_01](plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) v1.5 独立治理，功能 37/37 Passed，效果为 `partially_effective`。
- 本次被替换的需求、设计和计划分别归档至 [需求历史目录](历史文档/)、[设计历史目录](design/历史文档/) 和 [计划历史目录](plans/历史文档/)；历史文档仅用于追溯，不是当前实施权威。
- 批量发现当前设计时只扫描 `docs/design` 顶层，使用 `--non-recursive`，或显式使用 `--exclude '历史文档/**'`；归档来源链接与历史候选只能用于追溯，不能被纳入当前评审目标或替代现行上位文档。
- 更早版本的 14 份设计文档：[2026-08-21 v0 基线归档](design/历史文档/2026-08-21-v0-baseline/)。
- 原业务设计审计附件：[审计附件](design/历史文档/审计附件/)。
- 归档规则：[历史文档说明](design/历史文档/README.md)。

## 7. 当前基线状态

Employee/Transaction 需求、设计与 35/35 UAT 已完成且不得回退。Knowledge 默认关闭的生产接线、功能 UAT 37/37、域目录 v2 与 Summary v3 已实施；candidate-04/05 历史资产保持不可变，最新效果为 `partially_effective`。正式 Python 隔离入口已以 host 14/14、全量 1419 passed/27 opt-in skipped 和历史哈希复核关闭；本轮尚待关闭的是 candidate-05 的 Q3/Q4 根因、最小新版本优化、candidate-06 非 live 冻结及其后续精确授权效果 UAT，在这些门禁关闭前不得宣称 Knowledge 整体效果达标或七项收口完成。
