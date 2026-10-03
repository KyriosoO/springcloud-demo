# 架构文档索引

本页是Agent统一文档版本序列的当前入口（索引v3.34；序列起点v3.0）。本次启用独立的新文档版本序列，不表示软件/API/task/config/index变更；原高版本纳入v3.0不构成回滚，后续各文档可独立递增。当前权威顺序为：`REQ_00 → L0_00 → L1_* → L2_* → 代码与验证证据`。旧版正文和历史审计材料只用于追溯，不得覆盖当前设计。

## 1. 编号与状态规则

- `REQ_XX`：需求；`L0_XX`：总体架构；`L1_XX`：域/模块架构；`L2_<父 L1>_<序号>`：实施详细设计。
- 编号是稳定沟通标识，不表示实施顺序或状态。
- 设计状态只使用 `Draft / In Review / Approved / Deprecated（计划评审可用Reviewed）`；代码实现、测试验证和部署生效状态分别记录，不能互相替代。
- 版本与评审状态见各表；各文档独立递增。当前Knowledge实施/验收由P3_01/UAT_02治理，Business由UAT_00维护；旧P3_00/UAT_01/ROADMAP_01退出当前推进权威。新设计、实施和效果状态分别记录，本索引不复制运行流水。

## 2. 需求与总体架构

| 编号 | 文档 | 版本/状态 | 阅读重点 |
|---|---|---|---|
| `REQ_00` | [单体 Agent 查询能力建设需求说明](REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v3.2 / Approved | 三动作、filters QueryPlan、字段边界及 Knowledge 有引用有限回应边界 |
| `L0_00` | [单体 Agent L0 总体架构](design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v3.2 / Approved | 系统边界、唯一链路、在线/离线 Knowledge 边界与权限 |

## 3. L1 架构

| 编号 | 文档 | 版本/状态 | 治理范围 |
|---|---|---|---|
| `L1_00` | [核心与运行架构](design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v3.2 / Approved | Runtime、filters planning bridge、可选 Knowledge、Core 与共享 Registry/组合根；动作选择不预判资料存在性 |
| `L1_01` | [知识查询能力架构](design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v3.7 / Approved | 新增验证可靠性与检索诊断经定向复核、待实施；在线补检/框架迁移未批准 |
| `L1_02` | [业务查询适配架构](design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v3.1 / Approved | 三动作 Adapter、多值/组合字段配置、operator-specific 文本安全、最终授权与列表结果 |

## 4. L2 详细设计

### 4.1 核心与运行（受 `L1_00` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_00_00` | [Spring 接入与 Runtime 协同](design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v3.1 / Approved |
| `L2_00_01` | [Core 执行与能力注册](design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v3.1 / Approved |
| `L2_00_02` | [DeepSeek 接入与受控生成](design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v3.4 / Approved |
| `L2_00_03` | [用户角色 Authority Converter](design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v3.1 / Approved |

### 4.2 Knowledge（受 `L1_01` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_01_00` | [Knowledge 流程与配置](design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v3.7 / Approved |
| `L2_01_01` | [Knowledge 检索、本地模型与阶段 A 语料生命周期](design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v3.13 / Approved |
| `L2_01_02` | [Knowledge 证据、出域、摘要与效果验证](design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v3.6 / Approved |

### 4.3 Business（受 `L1_02` 治理）

| 编号 | 文档 | 版本/状态 |
|---|---|---|
| `L2_02_00` | [Business 公共约束、配置与出域](design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v3.1 / Approved |
| `L2_02_01` | [Employee Adapter 与授权](design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v3.1 / Approved |
| `L2_02_02` | [Transaction Adapter 与授权](design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v3.1 / Approved |

## 5. 关键阅读结论

- 一个逻辑 Agent 由 Spring `agent-service` 与 Python `agent-runtime` 两个进程组成；LangGraph 是唯一编排权威，Spring 只负责接入与治理。
- Core 只执行一个已验证 Action；能力通过冻结 Registry 接入。新增能力不得在 Core 写域分支。
- Knowledge 是一个复合查询能力，在线流程固定为问题处理、逻辑域选择、检索计划、多路检索/融合/重排、证据与摘要；阶段 A 离线语料工具与在线请求隔离，不新增 `knowledge-service`。
- Business 目标动作是 `employee.search`、`employee.semantic_search` 与 `transaction.search`；`employee.detail` 仅保留历史兼容调用方，不在目标生产组合根。Adapter 透传用户 JWT，业务服务完成最终授权。
- 外部模型只接收各域明确允许的最小 payload；未知、敏感、冲突或未分类内容失败关闭。Business 真实结果出域默认关闭。
- 原Knowledge最新有效效果等级为 `partially_effective`，只证明原冻结范围；具体运行在历史UAT_01/evidence保存。新方案由UAT_02治理，当前仅有部分fake/non-live阶段证据；新版完整功能/安全UAT与真实效果测量尚未完成，不继承历史通过。

## 6. 当前计划、维护基线与历史资料

| 定位 | 唯一入口 | 版本/状态 | 边界 |
|---|---|---|---|
| 当前Knowledge实施计划 | [P3_01](plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md) | v3.34 / Reviewed | 新增独立演练与离线诊断交接已复核、待实施；原终态保持，不自动重跑 |
| 当前Knowledge验收计划 | [UAT_02](plans/UAT_02_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | v3.34 / Reviewed | 新增同正式路径演练及否决候选边界已复核；正向阈值不变，完整新版UAT未完成 |
| Business维护验收基线 | [UAT_00](plans/UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | v3.1 / Reviewed | 原固定用例及Employee扩展证明范围保留；不重做UAT |
| 历史计划与迁移映射 | [本次归档](plans/历史文档/2026-09-14-knowledge-plan-handoff/README.md) | 原版本/状态不变 | 原ROADMAP_01、P3_00、UAT_01退出当前推进；UAT_00保留整理前快照 |

- 统一v3.0序列的原20文件归档见[统一基线归档](历史文档/2026-09-14-unified-v3-baseline/README.md)，原整理复核见[整理记录](历史文档/2026-09-14-unified-v3-baseline/MIGRATION.md)。
- 不新增替代ROADMAP，不继承旧目标预算/候选，不把图谱或旧联合UAT放入当前关键路径；历史Blocked/Deferred保持可追溯，不被归档抹除。
- 批量发现当前设计只扫描`docs/design`顶层；计划按本页显式清单读取，不递归把`历史文档`归档当当前权威。归档相对链接通过其原路径/冻结提交解释。
- 更早[14份设计v0基线](design/历史文档/2026-08-21-v0-baseline/)、[审计附件](design/历史文档/审计附件/)、[归档规则](design/历史文档/README.md)仍保留，只供追溯。

## 7. 当前基线状态

新增验证可靠性与离线检索诊断的设计已定向复核、尚未实施；优先用同正式路径无付费演练消除执行风险，再依阶段损失选择最小检索修正。当前固定原问和调用上限不变，线上补检、Deep Agents及父单元补取未启用；不因计划补齐宣称召回或UAT提升。

Employee/Transaction及原Knowledge功能UAT保持原证明范围。当前仓库Knowledge默认关闭；启用时唯一生产组合根已接线action-selection-v5/意图12/Summary9/minimal-v1，关闭时保持原selector v4及Business v7。动作选择职责修正已有non-live及独立代码复评，实际部署和真实效果未复测；Spring→Runtime合成lookup、explanation、applicability与失败链保持原证明范围。独立隔离运行已有部分真实typed及公开结果证据，维护者已确认部分整题通过与不通过，但未形成完整有效测量，不证明常规部署或整体回答质量通过。CONTRACT、RETRIEVAL、EVIDENCE、COMPOSE及资料主线NORMALIZE、CHUNK、REPRESENT分别完成P3_01限定的组件、仓库non-live或离线范围。新独立成对对照协议完整，但未满足主指标改善条件、候选相关性人工评价尚缺；端到端测量因技术失败停止，不补跑或继承历史通过。现行索引保持、候选未发布。COMPARE和MEASURE仍未完成，RELEASE受阻；新版完整UAT未通过，逐包状态以P3_01为准。本索引不复制运行身份、hash或动态测试数，不证明部署、效果改善或验收通过；图谱仍为后续方向，已取消优化目标不恢复。文档评审、实施、部署及验收分别管理。
