# [P3_00] 单体 Agent 查询能力实施与收口计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | P3_00 |
| 当前版本 | v3.0 |
| 文档状态 | Reviewed |
| 日期 | 2026-09-14 |
| 适用范围 | 统一文档基线、原工作包终态、新Knowledge在线与资料设计的后续实施交接 |
| 实施授权 | 本轮仅文档、归档、验证及Git；Ready表示技术输入具备，不授权代码、数据或模型调用 |
| 归档来源 | [整理前 v2.74 原文](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |

修订历史：2026-09-14，整理纳入统一文档基线v3.0；原版本、源提交及完整字节归档见上表。本次版本序列重置不是代码或设计回滚，评审、实施、部署和UAT状态分别管理。

本轮v3.0经三轮内审及两轮同一执行者的分层/跨层正式复核通过；仅证明文档整合，不表示新实现、部署或UAT已完成。完整发现与验证见本次归档MIGRATION.md。

## 2. 目标、范围与计划原则

P3只治理工作包、直接依赖、门禁与交接；设计由REQ/L0/L1/L2定义，验收由UAT计划治理。当前文档整理不实施后续包，不重新消费任何历史授权。

Business维持安全输入→LLM filters QueryPlan→严格decoder/validator/binder→单Action→固定Adapter→业务最终授权→受控列表。Knowledge当前源码11/7/v3；后续在线目标12/8/minimal-v1及资料组织设计独立推进。新包不继承已取消阶段B的Gate、剩余预算、失败候选或图谱前置。功能、安全可先完成，真实召回/回答测量必须后置独立授权。

## 3. 来源清单与当前基线

| 来源 | 当前版本 | 权威责任 | 状态 |
|---|---|---|---|
| [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v3.0 | 稳定业务目标、安全、受控多值及 Knowledge 阶段 A 语料完整性 | Approved |
| [`L0_00`](../design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v3.0 | 系统边界和下位治理 | Approved |
| [`L1_00`](../design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v3.0 | Runtime/Model/Core、受控 Business 候选准入、组合根及完整意图边界 | Approved |
| [`L1_02`](../design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v3.0 | Business 多值/组合边界、Adapter、结果卫生与最终授权 | Approved |
| [`L2_00_00`](../design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v3.0 | Spring 公共接入、Runtime 内部协议和当前生产启动入口状态 | Approved |
| [`L2_00_01`](../design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v3.0 | planning bridge、组合根和单动作 | Approved |
| [`L2_00_02`](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v3.0 | v7 显式字段完整性、裸 slot 多值/组合 Prompt 与 unsupported | Approved |
| [`L2_00_03`](../design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v3.0 | 用户角色 Authority 的 Servlet/Reactive 统一转换及 Provider 消费 | Approved |
| [`L2_02_00`](../design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v3.0 | filters、v3配置、多值binder、组合/region与结果出域 | Approved |
| [`L2_02_01`](../design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v3.0 | Employee search多值映射/semantic、记录卫生与最终读取授权 | Approved |
| [`L2_02_02`](../design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v3.0 | Transaction Date/Decimal/page/sort 与跨语言合同 | Approved |
| [`L1_01`](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v3.0 | §4.5在线重建及§4.6资料组织决策 | Approved；新设计待实施，不证明效果 |
| [`L2_01_00`](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v3.0 | §8在线合同、§19离线资料消费边界 | Approved；新设计待实施 |
| [`L2_01_01`](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v3.0 | §9检索、§18来源/切片/分类/时效/表示及迁移 | Approved；新设计待实施 |
| [`L2_01_02`](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v3.0 | §9回答及§19原文/派生表示/时效证据边界 | Approved；新设计待实施 |
| [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | v3.0 | Business 35/35固定用例与15项Employee自然语言扩展 | Reviewed |
| [`UAT_01`](UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | v3.0 | §15在线与§16资料表示分维验收；旧证据不改判 | Reviewed；本轮未执行新UAT |
| [`ROADMAP_01`](ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md) | v3.0 | 资料组织/表示的定向补充；旧阶段A证明范围保持 | Reviewed；当前资料设计未实施 |

本轮起始HEAD、20份原版本和字节归档见完整性清单。部署状态未复核；当前能力及证据适用范围见§16。旧测试总数和运行流水保存在原包冻结记录，不作为本轮已执行结果。

## 4. 分批与执行边界

本次：归档→正文整合→内审/正式复核→文档及定向兼容验证→Git交付。只整理授权20文档和本次归档。后续在线按§21、资料按§22推进，两个分支可独立实施；不先要求付费测量才能完成基础代码包。

## 5. 工作包清单

旧包只保留稳定身份、直接依赖及原终态；完整交付、历史依据和验证见表中原文。Done不代表本轮重执行；Deferred保留未完成事实，特别是两项旧效果UAT和已取消阶段B质量目标。后续12包具有独立验证/回滚，不复用旧批准或预算。

| 工作包 ID | 名称 | 来源设计 | 范围 | 直接依赖 | 入口门禁 | 交付物 | 验证 | 回滚边界 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| `WP-BQ-FILTER-CONTRACT-02` | 公共 filters QueryPlan 合同 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 公共 filters QueryPlan 合同的原冻结范围；非新设计通过 | - | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 撤销新合同，不恢复旧 Business 旁路 | Done |
| `WP-BQ-FIELD-CONFIG-02` | 统一字段级 JSON 配置 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 统一字段级 JSON 配置的原冻结范围；非新设计通过 | `WP-BQ-FILTER-CONTRACT-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 关闭新配置，不扩大旧动作 | Done |
| `WP-BQ-MODEL-CATALOG-02` | filters 模型目录与 Prompt | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | filters 模型目录与 Prompt的原冻结范围；非新设计通过 | `WP-BQ-FIELD-CONFIG-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 移除 v3 装配，不复用旧 live 证据 | Done |
| `WP-EMP-SEARCH-ADAPTER-02` | Employee 条件搜索 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee 条件搜索的原冻结范围；非新设计通过 | `WP-BQ-FIELD-CONFIG-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 禁用新 action，保留历史资产 | Done |
| `WP-EMP-SEMANTIC-ADAPTER-02` | Employee 语义搜索 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee 语义搜索的原冻结范围；非新设计通过 | `WP-BQ-FIELD-CONFIG-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 禁用新 action，不建立普通搜索 fallback | Done |
| `WP-EMP-ES-AUTH-02` | Employee ES 最终读取授权 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee ES 最终读取授权的原冻结范围；非新设计通过 | - | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 仅撤销 ES 专用链，不修改其他 endpoint 安全行为 | Done |
| `WP-TXN-SEARCH-EXT-02` | Transaction Date/金额/分页扩展 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Transaction Date/金额/分页扩展的原冻结范围；非新设计通过 | `WP-BQ-FIELD-CONFIG-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 关闭新字段，不修改 Java DTO/SQL | Done |
| `WP-TXN-DATE-WIRE-COMPAT-03` | Transaction 生产 Date 响应兼容 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Transaction 生产 Date 响应兼容的原冻结范围；非新设计通过 | `WP-TXN-SEARCH-EXT-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 撤销新增字符串分支，保持服务和 DTO 不变 | Done |
| `WP-BQ-RUNTIME-CUTOVER-02` | 三动作生产组合根切换 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 三动作生产组合根切换的原冻结范围；非新设计通过 | `WP-BQ-MODEL-CATALOG-02`, `WP-EMP-SEARCH-ADAPTER-02`, `WP-EMP-SEMANTIC-ADAPTER-02`, `WP-TXN-SEARCH-EXT-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 关闭新组合根，不恢复 Resolver | Done |
| `WP-EMP-DETAIL-RETIRE-02` | Employee detail 退役核实 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee detail 退役核实的原冻结范围；非新设计通过 | `WP-BQ-RUNTIME-CUTOVER-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 保留冻结历史与仍有调用方的共享类型 | Done |
| `WP-BQ-NONLIVE-E2E-02` | 三动作 non-live E2E | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 三动作 non-live E2E的原冻结范围；非新设计通过 | `WP-BQ-RUNTIME-CUTOVER-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 移除测试装配，不改历史 evidence | Done |
| `WP-BQ-CONTROLLED-LIVE-02` | 受控模型与业务联调 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 受控模型与业务联调的原冻结范围；非新设计通过 | `WP-BQ-NONLIVE-E2E-02`, `WP-EMP-DETAIL-RETIRE-02`, `WP-EMP-ES-AUTH-02`, `WP-TXN-DATE-WIRE-COMPAT-03` | `GATE-070` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 失败即停止，先修复根因，不复用失败结果路径 | Done |
| `WP-TXN-TEXT-POLICY-COMPAT-03` | Transaction 按 operator 区分文本安全策略 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Transaction 按 operator 区分文本安全策略的原冻结范围；非新设计通过 | `WP-BQ-FILTER-CONTRACT-02`, `WP-TXN-SEARCH-EXT-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不修改业务 SQL/DTO，不放宽 contains 或覆盖历史结果 | Done |
| `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | Model 完整意图与不可表达组合收紧 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Model 完整意图与不可表达组合收紧的原冻结范围；非新设计通过 | `WP-BQ-MODEL-CATALOG-02`, `WP-EMP-SEMANTIC-ADAPTER-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不引入本地 Resolver、额外门禁、生产 DTO 或历史改写 | Done |
| `WP-BQ-UAT-HANDOFF-02` | 正式 UAT 环境与交接 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 正式 UAT 环境与交接的原冻结范围；非新设计通过 | `WP-BQ-CONTROLLED-LIVE-02`, `WP-TXN-TEXT-POLICY-COMPAT-03`, `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | `GATE-UAT-007` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不把旧 evidence 或未执行场景冒充真实执行 | Done |
| `WP-BQ-COMPLETION-CLOSURE-04` | 当前 35 用例证据与实现收口 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 当前 35 用例证据与实现收口的原冻结范围；非新设计通过 | `WP-BQ-UAT-HANDOFF-02` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 保持 18 项真实证据集合不变；17 项仅按风险使用等价自动化 | Done |
| `WP-K-BASELINE-03` | Knowledge 设计与 UAT 基线 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Knowledge 设计与 UAT 基线的原冻结范围；非新设计通过 | - | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 仅回退本次文档语义，不改历史证据 | Done |
| `WP-K-RUNTIME-WIRING-03` | Knowledge 默认关闭生产接线 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Knowledge 默认关闭生产接线的原冻结范围；非新设计通过 | `WP-K-BASELINE-03` | `GATE-071` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 关闭开关即恢复 Business-only 对象图 | Done |
| `WP-K-SPRING-NONLIVE-E2E-03` | Spring→Runtime Knowledge non-live E2E | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Spring→Runtime Knowledge non-live E2E的原冻结范围；非新设计通过 | `WP-K-RUNTIME-WIRING-03` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 删除测试装配，不改生产合同 | Done |
| `WP-K-FUNCTIONAL-UAT-03` | Knowledge 功能 UAT | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Knowledge 功能 UAT的原冻结范围；非新设计通过 | `WP-K-SPRING-NONLIVE-E2E-03` | `GATE-UAT-008` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 保持 Effectiveness 独立 | Done |
| `WP-K-EFFECT-DIAG-03` | candidate-04 只读效果诊断 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | candidate-04 只读效果诊断的原冻结范围；非新设计通过 | `WP-K-FUNCTIONAL-UAT-03` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不修改 candidate-04 | Done |
| `WP-K-EFFECT-OPT-03` | 最小效果改进 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 最小效果改进的原冻结范围；非新设计通过 | `WP-K-EFFECT-DIAG-03` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 新旧版本并存，可禁用新版本 | Done |
| `WP-K-EFFECT-CANDIDATE-05-PREP` | 新效果候选非 live 准备 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 新效果候选非 live 准备的原冻结范围；非新设计通过 | `WP-K-EFFECT-OPT-03` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不执行真实 outbound | Done |
| `WP-K-EFFECT-LIVE-05` | 新效果 UAT | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 新效果 UAT的原冻结范围；非新设计通过 | `WP-K-EFFECT-CANDIDATE-05-PREP` | `GATE-072` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 失败即停止，不补跑或改判 | Done |
| `WP-K-CLOSURE-03` | Knowledge 正式代码评审与状态收口 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Knowledge 正式代码评审与状态收口的原冻结范围；非新设计通过 | `WP-K-EFFECT-LIVE-05` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 保持历史结果不可变 | Done |
| `WP-DOC-CONSISTENCY-06` | 七项文档事实与依赖纠偏 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 七项文档事实与依赖纠偏的原冻结范围；非新设计通过 | `WP-K-CLOSURE-03` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 仅回退本次文档修订 | Done |
| `WP-PY-REGRESSION-REPRO-06` | Python 正式全量入口可复现 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Python 正式全量入口可复现的原冻结范围；非新设计通过 | `WP-DOC-CONSISTENCY-06` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不改冻结资产或生产依赖 | Done |
| `WP-K-EFFECT-DIAG-06` | candidate-05 只读效果根因复核 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | candidate-05 只读效果根因复核的原冻结范围；非新设计通过 | `WP-PY-REGRESSION-REPRO-06` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不修改历史、gold、阈值或正文 | Done |
| `WP-K-EFFECT-OPT-06` | Knowledge 最小效果优化 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Knowledge 最小效果优化的原冻结范围；非新设计通过 | `WP-K-EFFECT-DIAG-06` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 禁止放宽阈值/安全；V1～V3 不修改 | Done |
| `WP-K-EFFECT-CANDIDATE-06-PREP` | 新效果候选非 live 冻结 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 新效果候选非 live 冻结的原冻结范围；非新设计通过 | `WP-K-EFFECT-OPT-06` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不读取密钥或产生 outbound | Done |
| `WP-K-EFFECT-LIVE-06` | candidate-06 效果 UAT | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | candidate-06 效果 UAT未完成；旧执行已终止，不恢复授权 | `WP-K-EFFECT-CANDIDATE-06-PREP` | `GATE-077` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 禁止重跑、补跑、续跑或改判 | Deferred |
| `WP-K-EFFECT-HARNESS-CLOSURE-07` | candidate-06 历史闭环与 Harness 修复 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | candidate-06 历史闭环与 Harness 修复的原冻结范围；非新设计通过 | `WP-K-EFFECT-CANDIDATE-06-PREP` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不改生产 src、历史证据或效果合同 | Done |
| `WP-K-EFFECT-CANDIDATE-07-PREP` | 全新效果候选 non-live 冻结 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 全新效果候选 non-live 冻结的原冻结范围；非新设计通过 | `WP-K-EFFECT-HARNESS-CLOSURE-07` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不读取密钥或产生 outbound | Done |
| `WP-K-EFFECT-LIVE-07` | 全新候选效果 UAT | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 全新候选效果 UAT未完成；旧执行已终止，不恢复授权 | `WP-K-EFFECT-CANDIDATE-07-PREP` | `GATE-079` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不重跑、补跑、续跑或创建 candidate-08 | Deferred |
| `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | 效果 Harness 状态合同修复 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 效果 Harness 状态合同修复的原冻结范围；非新设计通过 | `WP-K-EFFECT-CANDIDATE-07-PREP` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不修改历史 manifest/evidence，不执行 live | Done |
| `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | 全部当前设计落实审计 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 全部当前设计落实审计的原冻结范围；非新设计通过 | `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 超范围依赖如实标记，不伪装完成 | Done |
| `WP-SEVEN-ITEM-CLOSURE-06` | 最终验证与评审收口 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 最终验证与评审收口的原冻结范围；非新设计通过 | `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不改判效果或覆盖历史 | Done |
| `WP-K-UAT-TRACE-CLOSURE-09` | Knowledge UAT 追踪资产纠偏与有限收口 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Knowledge UAT 追踪资产纠偏与有限收口的原冻结范围；非新设计通过 | `WP-SEVEN-ITEM-CLOSURE-06` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 回退当前追踪资产和 validator，不修改任何历史 candidate/evidence | Done |
| `WP-K-REWRITE-SCHEMA-11` | Knowledge Rewrite 精确输出合同与验证台展示 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Knowledge Rewrite 精确输出合同与验证台展示的原冻结范围；非新设计通过 | `WP-K-UAT-TRACE-CLOSURE-09` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 回退 V2 生产绑定和当前文档/UI，不修改 V1 或历史 evidence | Done |
| `WP-EMP-NL-DESIGN-10` | Employee 自然语言扩展方案与设计 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee 自然语言扩展方案与设计的原冻结范围；非新设计通过 | `WP-BQ-COMPLETION-CLOSURE-04` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不修改公共 DTO、Employee endpoint、权限或 ES 结构 | Done |
| `WP-BQ-MULTIVALUE-CONTRACT-10` | Business 多值 QueryPlan 公共合同 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Business 多值 QueryPlan 公共合同的原冻结范围；非新设计通过 | `WP-EMP-NL-DESIGN-10` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 回退新 task/config 绑定，保留旧版本和历史 evidence | Done |
| `WP-EMP-NL-QUERY-10` | Employee 自然语言查询实现 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee 自然语言查询实现的原冻结范围；非新设计通过 | `WP-BQ-MULTIVALUE-CONTRACT-10` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不启用 workBase，不新增 endpoint 或本地 Resolver | Done |
| `WP-EMP-NL-UAT-10` | Employee 自然语言扩展受控 UAT | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee 自然语言扩展受控 UAT的原冻结范围；非新设计通过 | `WP-EMP-NL-QUERY-10` | `GATE-082` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 禁止额外模型调用、补跑、续跑或新候选 | Done |
| `WP-EMP-NL-CLOSURE-10` | Employee 自然语言扩展最终收口 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | Employee 自然语言扩展最终收口的原冻结范围；非新设计通过 | `WP-EMP-NL-UAT-10` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不覆盖历史资产或用户无关修改 | Done |
| `WP-KCORPUS-AUDIT-01` | 正文及附件只读审计 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 正文及附件只读审计的原冻结范围；非新设计通过 | - | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 删除本轮临时抓取；不改变现行索引 | Done |
| `WP-KCORPUS-DESIGN-01` | 阶段 A 语料生命周期设计 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 A 语料生命周期设计的原冻结范围；非新设计通过 | - | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 回退文档；不改历史 evidence | Done |
| `WP-KCORPUS-PIPELINE-01` | 版本化语料处理流水线 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 版本化语料处理流水线的原冻结范围；非新设计通过 | `WP-KCORPUS-AUDIT-01`、`WP-KCORPUS-DESIGN-01` | `GATE-083` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 保留 raw，撤销未发布 parsed/build；不写现行索引 | Done |
| `WP-KCORPUS-INDEX-01` | 候选索引与策略/Profile 快照 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 候选索引与策略/Profile 快照的原冻结范围；非新设计通过 | `WP-KCORPUS-PIPELINE-01` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 候选保持未发布；不删除旧索引 | Done |
| `WP-KCORPUS-UAT-01` | 阶段 A 直接检索 UAT | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 A 直接检索 UAT的原冻结范围；非新设计通过 | `WP-KCORPUS-INDEX-01` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不以阶段 B topK 失败否定语料存在性 | Done |
| `WP-KCORPUS-RELEASE-01` | alias 发布、回滚演练与收口 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | alias 发布、回滚演练与收口的原冻结范围；非新设计通过 | `WP-KCORPUS-UAT-01` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 精确原子恢复旧目标；不删除索引 | Done |
| `WP-KRETRIEVAL-DIAG-01` | 阶段 B 根因诊断 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 B 根因诊断的原冻结范围；非新设计通过 | - | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不写索引、不调用外部模型 | Done |
| `WP-KRETRIEVAL-DESIGN-01` | 阶段 B 设计 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 B 设计的原冻结范围；非新设计通过 | `WP-KRETRIEVAL-DIAG-01` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不改变历史资产 | Done |
| `WP-KRETRIEVAL-IMPLEMENT-01` | 阶段 B 实施 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 B 实施的原冻结范围；非新设计通过 | `WP-KRETRIEVAL-DESIGN-01` | `GATE-KRG-006` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | legacy绑定/显式false回退；索引不变 | Done |
| `WP-KRETRIEVAL-NONLIVE-01` | 阶段 B 回归 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 B 回归的原冻结范围；非新设计通过 | `WP-KRETRIEVAL-IMPLEMENT-01` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 不以fake关闭真实UAT | Done |
| `WP-KRETRIEVAL-UAT-01` | 阶段 B 专项 UAT | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 B 专项 UAT未完成；旧执行已终止，不恢复授权 | `WP-KRETRIEVAL-NONLIVE-01` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 本批终态，不复用余额或追加批次 | Deferred |
| `WP-KRETRIEVAL-QUALITY-01` | 阶段 B 质量收口 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原来源/版本 | 阶段 B 质量收口未完成；旧执行已终止，不恢复授权 | `WP-KRETRIEVAL-UAT-01` | - | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原交付/有限证据 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：原验证与适用边界 | 旧目标取消；未通过事实保留，见§21 | Deferred |
| WP-KREBUILD-DESIGN-01 | DESIGN | 本轮12份授权文档、分类决策、方案及实施/验收边界 | 待实施边界见§21；本轮12份授权文档、分类决策、方案及实施/验收边界 | - | - | 本轮12份授权文档、分类决策、方案及实施/验收边界 | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | 只文档diff，不回滚历史；无服务/模型 | Done |
| WP-KREBUILD-CONTRACT-01 | CONTRACT | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | 待实施边界见§21；DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | WP-KREBUILD-DESIGN-01 | - | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | 后续代码授权；新增独立类型/task，暂不切root | Ready |
| WP-KREBUILD-RETRIEVAL-01 | RETRIEVAL | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | 待实施边界见§21；DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | WP-KREBUILD-CONTRACT-01 | - | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | 本地fake；独立strategy，旧prod不变；无索引写入 | Blocked |
| WP-KREBUILD-EVIDENCE-01 | EVIDENCE | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | 待实施边界见§21；DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | WP-KREBUILD-CONTRACT-01 | - | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | 与RETRIEVAL可并行；旧Prompt/serializer不改 | Blocked |
| WP-KREBUILD-COMPOSE-01 | COMPOSE | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | 待实施边界见§21；DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | WP-KREBUILD-RETRIEVAL-01、WP-KREBUILD-EVIDENCE-01 | - | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | current-root、Spring E2E、37功能重新逐case、Business35关键防退、Java安全/类型/non-live、正式代码评审；Blocker/Major0 | 后续代码/测试权限；不用live作基础代码包完成前置；禁用Knowledge或整套恢复相容发布 | Blocked |
| WP-KREBUILD-MEASURE-01 | MEASURE | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | 待实施边界见§21；UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | WP-KREBUILD-COMPOSE-01 | - | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | 人工gold/语料就绪、新独立授权、版本绑定及预算预检；按预置判据分类，真实失败停止；未达标不写Passed | 需只读服务/模型与真人评价授权；无自动候选循环，不回滚索引；结果append-only | Blocked |
| WP-KORG-DESIGN-01 | DESIGN | 本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | 待实施边界见§22；本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | - | - | 本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | 三轮内审、两轮正式复核、文档验证通过；以包含本节的目标提交推送成功为Git收口证明 | 只文档；不动服务/模型/索引 | Done |
| WP-KORG-NORMALIZE-01 | NORMALIZE | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | 待实施边界见§22；DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | WP-KORG-DESIGN-01 | - | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | TEST-KRET-301、hash/span反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | 仅技术Ready，需代码/测试及有限资产读取新授权；sidecar追加，不迁现索引 | Ready |
| WP-KORG-CHUNK-01 | CHUNK | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | 待实施边界见§22；DR-KRET-304；chunking_v2.py、结构fixture、span回放 | WP-KORG-NORMALIZE-01 | - | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | TEST-KRET-302；条件/否定/表格/短块/长条款均可追溯；不静默遗漏 | 需代码/测试；新版本并存，旧chunker不覆盖；不依赖BGE或线上UAT | Blocked |
| WP-KORG-REPRESENT-01 | REPRESENT | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | 待实施边界见§22；DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | WP-KORG-NORMALIZE-01 | - | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | TEST-KRET-303；明确实际长度单位/版本，无截断；旧未知不回填 | 需代码/配置/本地固定tokenizer资源权限；无推理的纯构造可先完成，与CHUNK并行 | Blocked |
| WP-KORG-COMPARE-01 | COMPARE | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | 待实施边界见§22；DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | - | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | fake/类型→人工原文→另授权BGE及只读typed；逐阶段损失、保留题、安全与停止规则 | 需独立索引候选/BGE/只读服务/必要模型预算授权；同源切片与表示分轮；不切线上alias | Blocked |
| WP-KORG-RELEASE-01 | RELEASE | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | 待实施边界见§22；DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | WP-KORG-COMPARE-01 | - | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；无证据不得发布 | 需新索引/受控部署/alias写授权；精确旧绑定与原子回滚；不删旧索引 | Blocked |
| `WP-KCORPUS-ATTACHMENT-01` | 正文及附件版本化补齐 | `REQ-KCORPUS-001～006`；`L2_01_01 DR-KRET-013～025`；`L2_01_02 DR-KEV-023～025` | 阶段A已拆分流水线/索引/UAT/发布包的历史汇总身份；不重复执行 | `WP-KCORPUS-AUDIT-01` | - | 版本化原始资产、解析结果、质量报告、新索引候选、回滚记录；alias 生效另受发布门禁控制 | 解析合同、表格/OCR抽样、索引完整性、别名切换演练 | 新索引整体下线；旧索引和别名目标可恢复 | Done |
| `WP-KGRAPH-CONTRACT-01` | 轻量图谱合同实现与只读接口 | 待新增 Knowledge Graph REQ/L1/L2；保持 `L1_01 §5/6` 两级映射 | 按已批准设计实现实体、关系、溯源、时效、版本、读取授权和类型化导航合同 | `WP-KCORPUS-AUDIT-01` | `GATE-KRG-007` | 严格 Schema、类型化接口、版本策略实现、fake 合同测试 | Schema 正反例、来源缺失、过期、未授权和物理信息零暴露 | 禁用图谱导航配置；原检索链路不受影响 | Blocked |
| `WP-KGRAPH-BUILD-01` | 版本化关系数据构建 | `WP-KGRAPH-CONTRACT-01` 批准后的 IMPL/TEST/VAL | 从已核验原文提取、校验和发布最小关系数据，不修改原文 | `WP-KCORPUS-ATTACHMENT-01`、`WP-KGRAPH-CONTRACT-01` | - | 关系数据、来源绑定、时效信息、构建报告和只读快照 | 100% 可追溯、哈希、时效、抽样人工复核和敏感扫描 | 整体撤下图谱版本；不回滚原文索引 | Blocked |
| `WP-KHYBRID-RETRIEVAL-01` | 图谱导航与原文检索联合 | 待新增联合检索 DR；保持 `L2_01_02 DR-KEV-*` | 在一个 `knowledge.query` 内使用图谱扩展候选，再回到授权原文 Evidence | `WP-KRETRIEVAL-QUALITY-01`、`WP-KGRAPH-BUILD-01` | - | 联合检索实现、类型化 Provider、配置快照和故障降级规则 | 图谱命中/缺失/过期/不可用、多跳、原文回证据、无图谱答案测试 | 关闭图谱导航，保留批准的原文检索路径 | Blocked |
| `WP-KNOWLEDGE-UAT-02` | 语料、检索与图谱联合 UAT | 批准后的 P3/UAT 计划；`L2_01_02 TEST/VAL` | 功能、安全、时效、多跳和效果验收；如需付费调用另行冻结授权 | `WP-KHYBRID-RETRIEVAL-01` | - | case 追踪、有限 evidence、功能结论、效果分类和剩余风险 | 严格 Schema、安全 Gate、原文引用、人工 rubric、全量回归 | 失败如实记录；不自动创建下一 candidate | Blocked |

## 6. 直接依赖图

原包依赖的旧版本号为当时技术依据，按整理前归档解释，不冒充当前v3.0上位文档。新包只引用当前目标合同。

保留旧边的历史含义，不把其完成作为新设计前置；新边只连接各自六包，不包含测量→基础代码的反向边。

| 依赖 ID | 前置工作包 | 后继工作包 | 类型 | 技术依据 | 来源证据 |
|---|---|---|---|---|---|
| `DEP-BQS-001` | `WP-BQ-FILTER-CONTRACT-02` | `WP-BQ-FIELD-CONFIG-02` | contract | 配置需绑定真实 filters 类型与 operator | `DR-BQCOM-101/102` |
| `DEP-BQS-002` | `WP-BQ-FIELD-CONFIG-02` | `WP-BQ-MODEL-CATALOG-02` | contract | catalog 必须来源于 verified snapshot | `DR-MODEL-103` |
| `DEP-BQS-003` | `WP-BQ-FIELD-CONFIG-02` | `WP-EMP-SEARCH-ADAPTER-02` | contract | Employee search 字段/operator 需要 code/config 交集 | `DR-EMP-101` |
| `DEP-BQS-004` | `WP-BQ-FIELD-CONFIG-02` | `WP-EMP-SEMANTIC-ADAPTER-02` | contract | semantic action/profile 需 code/config 交集 | `DR-EMP-102` |
| `DEP-BQS-005` | `WP-BQ-FIELD-CONFIG-02` | `WP-TXN-SEARCH-EXT-02` | contract | Date/Decimal/page/sort 受统一字段配置限制 | `DR-TXN-101/104` |
| `DEP-BQS-006` | `WP-BQ-MODEL-CATALOG-02` | `WP-BQ-RUNTIME-CUTOVER-02` | runtime | 组合根必须接入 filters v3 generator | `DR-CORE-101` |
| `DEP-BQS-007` | `WP-EMP-SEARCH-ADAPTER-02` | `WP-BQ-RUNTIME-CUTOVER-02` | runtime | 组合根需要实际 search handler | `DR-CORE-102` |
| `DEP-BQS-008` | `WP-EMP-SEMANTIC-ADAPTER-02` | `WP-BQ-RUNTIME-CUTOVER-02` | runtime | 组合根需要实际 semantic handler | `DR-CORE-102` |
| `DEP-BQS-009` | `WP-TXN-SEARCH-EXT-02` | `WP-BQ-RUNTIME-CUTOVER-02` | runtime | 组合根需要扩展 Transaction handler | `DR-CORE-102` |
| `DEP-BQS-011` | `WP-BQ-RUNTIME-CUTOVER-02` | `WP-EMP-DETAIL-RETIRE-02` | rollback | 旧动作退役前先建立替代 search 组合根 | `DR-EMP-106` |
| `DEP-BQS-012` | `WP-BQ-RUNTIME-CUTOVER-02` | `WP-BQ-NONLIVE-E2E-02` | runtime | E2E 需要三动作唯一 production 对象图 | `DR-CORE-102` |
| `DEP-BQS-013` | `WP-EMP-DETAIL-RETIRE-02` | `WP-BQ-CONTROLLED-LIVE-02` | validation | live 前确认旧目标入口不可达及历史兼容 | `TEST-EMP-107` |
| `DEP-BQS-014` | `WP-BQ-NONLIVE-E2E-02` | `WP-BQ-CONTROLLED-LIVE-02` | validation | 真实调用前完成所有 fake 成功/拒绝/零调用 | `VAL-BQCOM-102` |
| `DEP-BQS-015` | `WP-BQ-CONTROLLED-LIVE-02` | `WP-BQ-UAT-HANDOFF-02` | validation | 正式 UAT 前必须获得本版真实链路证据 | `REQ-BQS-012` |
| `DEP-BQS-016` | `WP-EMP-ES-AUTH-02` | `WP-BQ-CONTROLLED-LIVE-02` | security | 恢复真实模型/Employee 调用前必须补齐 endpoint-scoped 共享 converter 和真实过滤链矩阵 | `DR-EMP-105`; `DR-AUTH-007` |
| `DEP-BQS-017` | `WP-TXN-SEARCH-EXT-02` | `WP-TXN-DATE-WIRE-COMPAT-03` | contract | 生产响应兼容建立在既有 Date/Decimal/page Adapter 上 | `DR-TXN-102/105` |
| `DEP-BQS-018` | `WP-TXN-DATE-WIRE-COMPAT-03` | `WP-BQ-CONTROLLED-LIVE-02` | validation | 新 controlled live 前先证明真实 Spring 日期可被生产 codec 处理 | `VAL-TXN-101/102/103` |
| `DEP-BQS-019` | `WP-BQ-FILTER-CONTRACT-02` | `WP-TXN-TEXT-POLICY-COMPAT-03` | contract | 公共 validator 必须依据已验证 filter/operator 类型选择有限文本策略 | `DR-BQCOM-101` |
| `DEP-BQS-020` | `WP-TXN-SEARCH-EXT-02` | `WP-TXN-TEXT-POLICY-COMPAT-03` | security | Transaction `=` 与 `LIKE` 不同安全语义只能收紧现有 Adapter 合同 | `DR-TXN-101` |
| `DEP-BQS-021` | `WP-TXN-TEXT-POLICY-COMPAT-03` | `WP-BQ-UAT-HANDOFF-02` | validation | 首次 UAT 失败后先修复实际类型精确匹配并证明 contains 通配拒绝，再使用独立结果路径 | `TEST-BQCOM-102`; `TEST-TXN-101` |
| `DEP-BQS-022` | `WP-BQ-MODEL-CATALOG-02` | `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | contract | v4 Prompt 复用已验证三动作安全 catalog 和 provider-neutral generator | `DR-MODEL-101/103` |
| `DEP-BQS-023` | `WP-EMP-SEMANTIC-ADAPTER-02` | `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | contract | semantic+地点组合不能由任一现有单接口表达，必须规划 unsupported | `DR-EMP-102`; `DR-MODEL-104` |
| `DEP-BQS-024` | `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | `WP-BQ-UAT-HANDOFF-02` | validation | 两次失败后先固定 v4 完整意图约束和新 manifest，再使用 run03 独立结果路径 | `TEST-MODEL-102/104`; `VAL-MODEL-101` |
| `DEP-BQS-025` | `WP-BQ-UAT-HANDOFF-02` | `WP-BQ-COMPLETION-CLOSURE-04` | validation | 先冻结 18 项真实结果，再对未执行风险建立当前自动化追踪并完成正式收口 | `UAT_00` v1.24；`uat_traceability.v2.json` |
| `DEP-KQ-001` | `WP-K-BASELINE-03` | `WP-K-RUNTIME-WIRING-03` | contract | 生产接线只能依据评审通过的默认关闭与生命周期合同 | `L1_00` v3.1；`L2_01_00` v1.10；`L2_01_01` v1.9 |
| `DEP-KQ-002` | `WP-K-RUNTIME-WIRING-03` | `WP-K-SPRING-NONLIVE-E2E-03` | runtime | Spring E2E 必须使用当前生产对象图而非历史专用 Runtime | `DR-KFLOW-011～013` |
| `DEP-KQ-003` | `WP-K-SPRING-NONLIVE-E2E-03` | `WP-K-FUNCTIONAL-UAT-03` | validation | 先证明完整链路和失败/零调用，再汇总逐 case 功能结论 | `UAT_01` 第 5～6 节 |
| `DEP-KQ-004` | `WP-K-FUNCTIONAL-UAT-03` | `WP-K-EFFECT-DIAG-03` | validation | 功能缺陷不得混入效果根因或通过调参掩盖 | `DR-KEV-013` |
| `DEP-KQ-005` | `WP-K-EFFECT-DIAG-03` | `WP-K-EFFECT-OPT-03` | contract | 只有冻结指标/分布支持的接缝允许优化 | `DR-KEV-014` |
| `DEP-KQ-006` | `WP-K-EFFECT-OPT-03` | `WP-K-EFFECT-CANDIDATE-05-PREP` | contract | 新候选必须绑定已回归的新版本 | `DR-KEV-015` |
| `DEP-KQ-007` | `WP-K-EFFECT-CANDIDATE-05-PREP` | `WP-K-EFFECT-LIVE-05` | validation | 真实运行只能消费冻结候选和一次性授权 | `DR-KEV-015`; `GATE-072` |
| `DEP-KQ-008` | `WP-K-EFFECT-LIVE-05` | `WP-K-CLOSURE-03` | validation | live 结论和 append-only 证据形成后才能执行最终状态同步与复评 | `UAT_01` 第 7 节；消费后 history tests |
| `DEP-KQ-009` | `WP-K-CLOSURE-03` | `WP-DOC-CONSISTENCY-06` | validation | 新一轮优化前先冻结已完成基线并纠正当前/历史事实 | candidate-04/05 append-only hash；当前代码 |
| `DEP-KQ-010` | `WP-DOC-CONSISTENCY-06` | `WP-PY-REGRESSION-REPRO-06` | validation | 正式测试入口必须依据评审后的当前实施状态和历史保护边界 | `GATE-073` |
| `DEP-KQ-011` | `WP-PY-REGRESSION-REPRO-06` | `WP-K-EFFECT-DIAG-06` | validation | 先建立稳定全量基线，避免把环境失败误判为效果实现缺陷 | `GATE-074` |
| `DEP-KQ-012` | `WP-K-EFFECT-DIAG-06` | `WP-K-EFFECT-OPT-06` | contract | 只允许由 candidate-05 有限证据直接支持的最小接缝优化 | `L2_01_02` 效果诊断合同 |
| `DEP-KQ-013` | `WP-K-EFFECT-OPT-06` | `WP-K-EFFECT-CANDIDATE-06-PREP` | validation | 新候选只能绑定已评审且 non-live 全通过的新版本 | `GATE-075` |
| `DEP-KQ-014` | `WP-K-EFFECT-CANDIDATE-06-PREP` | `WP-K-EFFECT-LIVE-06` | security | 真实 outbound 只能消费冻结 HEAD、manifest、reference 和预算 | `GATE-076`; `GATE-077` |
| `DEP-KQ-016` | `WP-K-EFFECT-CANDIDATE-06-PREP` | `WP-K-EFFECT-HARNESS-CLOSURE-07` | validation | candidate-06 已消费失败证据暴露准备合同在结束校验未完整实现；修复只继承其冻结合同，不继承失败运行状态 | `DR-KEV-020`；candidate-06 failure |
| `DEP-KQ-017` | `WP-K-EFFECT-HARNESS-CLOSURE-07` | `WP-K-EFFECT-CANDIDATE-07-PREP` | validation | 新候选必须冻结修复后源码及 candidate-06 历史哈希 | `TEST-KEV-012` |
| `DEP-KQ-018` | `WP-K-EFFECT-CANDIDATE-07-PREP` | `WP-K-EFFECT-LIVE-07` | security | 新 outbound 只能消费全新 HEAD/run/manifest/reference/预算 | `GATE-079` |
| `DEP-KQ-019` | `WP-K-EFFECT-CANDIDATE-07-PREP` | `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | validation | 以已冻结候选和其 append-only 无效运行证据修复不可达预检合同；不把 Deferred live 工作包伪装为完成前置 | append-only authorization/failure；`DR-KEV-021` |
| `DEP-KQ-020` | `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | validation | 先使当前 Harness 合同与设计一致，再审计全部当前设计落实状态 | `TEST-KEV-013`; non-live/history checks |
| `DEP-KQ-021` | `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | `WP-SEVEN-ITEM-CLOSURE-06` | validation | 缺口处置与评审完成后才能执行最终全量收口 | 完整落实矩阵；`GATE-078` |
| `DEP-KQ-022` | `WP-SEVEN-ITEM-CLOSURE-06` | `WP-K-UAT-TRACE-CLOSURE-09` | validation | 追踪元数据纠偏必须建立在已冻结的35/35、37/37及candidate-05/07终态上，不得反向改写既有验收 | `UAT_00 v1.24`；`UAT_01 v1.12`；不可变 evidence |
| `DEP-KQ-023` | `WP-K-UAT-TRACE-CLOSURE-09` | `WP-K-REWRITE-SCHEMA-11` | contract | 当前 UAT 权威和历史效果边界稳定后，才能切换新的 Rewrite 任务版本且不误用历史效果证据 | `L2_01_00 DR-KFLOW-004/012`；`UAT_01 v1.13` |
| `DEP-EMP-NL-001` | `WP-BQ-COMPLETION-CLOSURE-04` | `WP-EMP-NL-DESIGN-10` | validation | 自然语言扩展以已关闭的三动作生产链路和35项Business UAT为稳定基线，不重开旧 detail/Resolver | 当前生产组合根；`UAT_00` v1.24 |
| `DEP-EMP-NL-002` | `WP-EMP-NL-DESIGN-10` | `WP-BQ-MULTIVALUE-CONTRACT-10` | contract | 多值合同、operator shape和组合矩阵只能依据评审通过的LLM理解/本地控制职责实施 | `DR-MODEL-106/107`; `DR-BQCOM-109/110` |
| `DEP-EMP-NL-003` | `WP-BQ-MULTIVALUE-CONTRACT-10` | `WP-EMP-NL-QUERY-10` | runtime | extractor、binder和Employee mapper依赖已冻结的typed slots、配置及operator合同 | `DR-BQCOM-109～111`; `DR-EMP-109～111` |
| `DEP-EMP-NL-004` | `WP-EMP-NL-QUERY-10` | `WP-EMP-NL-UAT-10` | validation | 真实UAT前必须先完成fake、Spring E2E、Java安全链、类型和正式隔离回归 | `GATE-081`; `UAT_00` 第13节 |
| `DEP-EMP-NL-005` | `WP-EMP-NL-UAT-10` | `WP-EMP-NL-CLOSURE-10` | validation | append-only UAT终态和15类组合覆盖形成后才能执行历史校验、正式评审与状态收口 | `GATE-082`; candidate-03/04 history tests |
| `DEP-KCORPUS-001` | `WP-KCORPUS-AUDIT-01` | `WP-KCORPUS-PIPELINE-01` | data | strict 三层事实清单和人工 P0/P1 优先级必须先于持久下载与候选写入 | ROADMAP_01 §4.5.1.1；`DR-KRET-026` |
| `DEP-KCORPUS-002` | `WP-KCORPUS-DESIGN-01` | `WP-KCORPUS-PIPELINE-01` | contract | 下载与写入只能依据已评审的离线生命周期合同 | `GATE-083` |
| `DEP-KCORPUS-003` | `WP-KCORPUS-PIPELINE-01` | `WP-KCORPUS-INDEX-01` | data | 只有质量通过且关系完整的 chunk 可进入候选 | `DR-KRET-018～022` |
| `DEP-KCORPUS-004` | `WP-KCORPUS-INDEX-01` | `WP-KCORPUS-UAT-01` | validation | UAT 必须针对冻结 candidate/profile/policy snapshot | `UAT_01` 阶段 A |
| `DEP-KCORPUS-005` | `WP-KCORPUS-UAT-01` | `WP-KCORPUS-RELEASE-01` | validation | alias 生效只依赖质量、安全、直接检索和回滚证据 | `GATE-084` |
| `DEP-KQUALITY-001` | `WP-KRETRIEVAL-DIAG-01` | `WP-KRETRIEVAL-DESIGN-01` | validation | 根因先于设计 | §20 |
| `DEP-KQUALITY-002` | `WP-KRETRIEVAL-DESIGN-01` | `WP-KRETRIEVAL-IMPLEMENT-01` | contract | 评审通过先于实现 | `GATE-KRG-006` |
| `DEP-KQUALITY-003` | `WP-KRETRIEVAL-IMPLEMENT-01` | `WP-KRETRIEVAL-NONLIVE-01` | validation | 验证当前实现 | L2 TEST/VAL |
| `DEP-KQUALITY-004` | `WP-KRETRIEVAL-NONLIVE-01` | `WP-KRETRIEVAL-UAT-01` | validation | fake 先于真实请求 | UAT_01 §14 |
| `DEP-KQUALITY-005` | `WP-KRETRIEVAL-UAT-01` | `WP-KRETRIEVAL-QUALITY-01` | validation | 逐 case 证据与正式评审 | §20 |
| DEP-KREBUILD-001 | WP-KREBUILD-DESIGN-01 | WP-KREBUILD-CONTRACT-01 | contract | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | §21及对应L2合同 |
| DEP-KREBUILD-002 | WP-KREBUILD-CONTRACT-01 | WP-KREBUILD-RETRIEVAL-01 | contract | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | §21及对应L2合同 |
| DEP-KREBUILD-003 | WP-KREBUILD-CONTRACT-01 | WP-KREBUILD-EVIDENCE-01 | contract | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | §21及对应L2合同 |
| DEP-KREBUILD-004 | WP-KREBUILD-RETRIEVAL-01 | WP-KREBUILD-COMPOSE-01 | contract | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | §21及对应L2合同 |
| DEP-KREBUILD-005 | WP-KREBUILD-EVIDENCE-01 | WP-KREBUILD-COMPOSE-01 | contract | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | §21及对应L2合同 |
| DEP-KREBUILD-006 | WP-KREBUILD-COMPOSE-01 | WP-KREBUILD-MEASURE-01 | contract | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | §21及对应L2合同 |
| DEP-KORG-001 | WP-KORG-DESIGN-01 | WP-KORG-NORMALIZE-01 | contract | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | §22及对应L2合同 |
| DEP-KORG-002 | WP-KORG-NORMALIZE-01 | WP-KORG-CHUNK-01 | contract | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | §22及对应L2合同 |
| DEP-KORG-003 | WP-KORG-NORMALIZE-01 | WP-KORG-REPRESENT-01 | contract | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | §22及对应L2合同 |
| DEP-KORG-004 | WP-KORG-CHUNK-01 | WP-KORG-COMPARE-01 | contract | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | §22及对应L2合同 |
| DEP-KORG-005 | WP-KORG-REPRESENT-01 | WP-KORG-COMPARE-01 | contract | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | §22及对应L2合同 |
| DEP-KORG-006 | WP-KORG-COMPARE-01 | WP-KORG-RELEASE-01 | contract | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | §22及对应L2合同 |
| `DEP-KRG-001` | `WP-KCORPUS-AUDIT-01` | `WP-KCORPUS-ATTACHMENT-01` | data | 未知缺口和来源前不能安全下载、解析或发布 | ROADMAP_01 §4.5.1 |
| `DEP-KRG-003` | `WP-KCORPUS-AUDIT-01` | `WP-KGRAPH-CONTRACT-01` | data | 图谱实体和关系必须来源于可用文档与真实查询缺口 | ROADMAP_01 §4.5.3 |
| `DEP-KRG-004` | `WP-KCORPUS-ATTACHMENT-01` | `WP-KGRAPH-BUILD-01` | data | 不从缺失、未核验或不可追溯正文构建关系 | ROADMAP_01 §4.5.1、§4.5.3.3 |
| `DEP-KRG-005` | `WP-KGRAPH-CONTRACT-01` | `WP-KGRAPH-BUILD-01` | contract | 关系数据必须遵循已批准 Schema、溯源和时效合同 | ROADMAP_01 §4.5.3 |
| `DEP-KRG-006` | `WP-KRETRIEVAL-QUALITY-01` | `WP-KHYBRID-RETRIEVAL-01` | runtime | 先稳定原文检索基线，才能判断图谱增益 | ROADMAP_01 §4.5.2、§4.5.4 |
| `DEP-KRG-007` | `WP-KGRAPH-BUILD-01` | `WP-KHYBRID-RETRIEVAL-01` | data | 联合检索依赖可追溯的关系快照 | ROADMAP_01 §4.5.3.3、§4.5.4 |
| `DEP-KRG-008` | `WP-KHYBRID-RETRIEVAL-01` | `WP-KNOWLEDGE-UAT-02` | runtime | UAT 验证完整联合对象图，而非局部替身 | ROADMAP_01 §10.1 |

## 7. 阶段门禁

原ROADMAP的GATE-KRG-001/002分别是阶段A入口/发布决策的历史别名（当前唯一对应GATE-083/084），不再复制为独立审批；原图谱GATE-KRG-003/004/005/007的Open及未实施包转入本表，未被清空。其设计前提尚不存在，本轮不补设计、不授权实施。

下表为历史门禁的保留终态与原关闭条件，不重新授予任何动作。Closed也可表示一次授权已终止，不等于效果成功；无效测量仍按UAT原结论保留。新在线/资料包没有新增重复Gate，设计评审控制实施输入，质量及发布条件仅约束各自后续包。

| 门禁 ID | 工作包 | 类型 | 控制动作 | 是否阻塞入口 | 关闭条件 | 证据/权威来源 | 责任方/外部提供方 | 最晚关闭阶段 | 验证者与方法 | 未关闭行为 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `GATE-067` | `WP-BQ-FILTER-CONTRACT-02` | closure | 新设计基线生效 | 否 | REQ/L0/L1/L2/P3/UAT 两阶段评审通过且版本一致 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-067`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 文档维护者 | 代码实施前 | 分层/跨层独立评审与 DAG 校验 | 不允许依据未评审设计实施 | Closed |
| `GATE-068` | `WP-EMP-ES-AUTH-02` | release_effective | Employee search/vector 端点级角色转换及最终守卫生效 | 否 | 两个既有 POST endpoint 显式绑定共享 converter，真实 JWT role claim 经完整 SecurityFilterChain 通过 ADMIN/VIEWER、拒绝矩阵及 detail/fallback 兼容 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-068`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | Employee 业务维护者/实施者 | 恢复 Employee 真实联调前 | Java 真实 Servlet SecurityFilterChain、两 endpoint 矩阵与既有调用方测试 | 禁止真实 Employee 联调及宣称最终授权已生效 | Closed |
| `GATE-069` | `WP-TXN-DATE-WIRE-COMPAT-03` | integration | Transaction Date 时区/精度及真实响应合同生效 | 否 | Python Date→HTTP→Jackson→Mapper instant/open interval/DB precision 成立；生产 Spring UTC 零毫秒 offset 字符串与 standalone 整秒 epoch 都通过严格 codec | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-069`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | Transaction 维护者/实施者 | 日期 live/UAT 前 | 双语言 production-config contract、strict bounds 与零模型实际 codec | 日期相关真实联调/UAT 不执行 | Closed |
| `GATE-070` | `WP-BQ-CONTROLLED-LIVE-02` | integration | 真实模型、业务服务和有限敏感数据调用 | 是 | 前置 non-live 包完成，GATE-068/069 关闭，semantic partial hits 与 Transaction 生产 Date 响应合同均已实现，环境/预算/授权/安全边界重新确认，历史 evidence 不可变 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-070`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 用户/业务维护者 | 下一次真实模型联调前 | frozen task/config/cases、真实安全链、预算、历史 hash 和零泄漏 preflight | controlled live 保持 Blocked；只允许独立零模型只读诊断 | Closed |
| `GATE-UAT-007` | `WP-BQ-UAT-HANDOFF-02` | closure | 正式四阶段 UAT | 是 | 18 个真实模型/业务场景保持不可变，剩余 17 个确定性风险由当前生产组合根、Spring 安全链或跨语言合同逐项验证，35 个计划用例均有唯一追踪且不外推真实执行范围 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-UAT-007`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 用户/UAT 执行者 | 阶段最终收口前 | 严格校验 35 个 case、18/17 证据分类、引用符号、历史 hash、零调用与权限边界 | 任一 case 无实际或等价证据则恢复 Open，不得靠旧 detail/stub 结果关闭 | Closed |
| `GATE-071` | `WP-K-RUNTIME-WIRING-03` | closure | Knowledge 生产接线设计生效 | 是 | L1/L2/P3/UAT_01 语义一致，三轮内审与独立评审无 S0/S1/未处理 S2 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-071`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 文档维护者 | 生产接线前 | 分层/跨层设计评审 | 不允许依据未评审语义接线 | Closed |
| `GATE-UAT-008` | `WP-K-FUNCTIONAL-UAT-03` | closure | Knowledge 功能验收 | 是 | UAT_01 37 个功能 case 均有实际/等价证据，关键 Spring→Runtime 16 场景 E2E 实际执行，权限/出域/失败/零调用成立 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-UAT-008`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 实施者/UAT 评审者 | 效果诊断前 | Schema、引用、调用计数和回归验证 | 任一当前证据失效则恢复 Open | Closed |
| `GATE-072` | `WP-K-EFFECT-LIVE-05` | integration | 真实付费 Knowledge 效果 UAT | 是 | frozen HEAD=`63bc30b...2efa`、manifest=`41997c6...e278c`、26 case 双变体、预算78完成唯一执行；安全 Gate 通过，结论 `partially_effective` | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-072`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 用户 | 首个模型 outbound 前 | clean/frozen source、预算、历史 hash、敏感扫描 | 禁止重跑、补跑、续跑或改判 | Closed |
| `GATE-073` | `WP-DOC-CONSISTENCY-06` | closure | 七项文档纠偏生效 | 否 | 3 轮内审及独立分层/跨层评审通过，版本/状态/DAG/实现事实一致 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-073`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 文档维护者 | 测试入口或效果代码修改前 | 独立评审无 S0/S1/未处理 S2 | 受影响代码实施保持 Blocked | Closed |
| `GATE-074` | `WP-PY-REGRESSION-REPRO-06` | closure | Python 正式全量入口生效 | 否 | 版本化隔离 bootstrap 显式安装当前源码；14 项 host/preflight 与全量 non-live 通过且历史 hash 不变 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-074`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 实施者 | candidate-05 根因复核前 | 从干净源码树重复执行 | 效果优化保持 Blocked | Closed |
| `GATE-075` | `WP-K-EFFECT-OPT-06` | closure | Summary V4 与效果口径 v2 生效 | 否 | candidate-05 诊断和设计评审通过；Summary V4 多要点/多域覆盖、v2 分母/质量 Gate、non-live、安全、E2E、类型和历史回归全部通过 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-075`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 实施者/评审者 | 新候选冻结前 | 阈值/validator/权限/历史反证 | candidate-06 准备保持 Blocked | Closed |
| `GATE-076` | `WP-K-EFFECT-CANDIDATE-06-PREP` | closure | candidate-06 非 live 冻结 | 否 | run=`knowledge-p5-live-v3-20260828-candidate-06`、manifest=`7f54ddff...cc51b8`、reference=`P3_00:GATE-077`、预算78、92项资产与失败关闭已冻结 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-076`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 实施者 | 真实授权申请前 | 首 outbound、预算、retry/resume=0 | 关闭时未创建正式 authorization、未读取密钥或产生 outbound；后续消费不改写本门禁历史结论 | Closed |
| `GATE-077` | `WP-K-EFFECT-LIVE-06` | integration | candidate-06 一次性真实效果 UAT | 是 | 精确授权已消费；candidate-06 因 Harness `snapshot_changed` 失败，不形成效果结论 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-077`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 用户/实施者 | 已消费 | 历史哈希与有限失败复核 | 禁止重跑、补跑、续跑或复用授权 | Closed |
| `GATE-079` | `WP-K-EFFECT-LIVE-07` | integration | candidate-07 一次性真实效果 UAT 授权 | 是 | 绑定授权已执行一次并形成 `Failed/Unconsumed` 唯一终态；无论是否产生有效测量均不得复用 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-079`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 用户/实施者 | 已终止 | frozen binding、失败阶段、零调用、敏感扫描和历史不可变 | 禁止重跑、补跑、续跑或创建 candidate-08 | Closed |
| `GATE-078` | `WP-SEVEN-ITEM-CLOSURE-06` | closure | 当前项目实现与验收治理收口 | 否 | candidate-07 无效运行及最新有效 `partially_effective` 均如实记录；Harness 状态合同、全量设计落实审计、必要实现、全量 Python/Java、设计/代码评审和文档状态全部闭合 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-078`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 实施者/评审者 | 最终内容提交前 | Blocker/Major=0；当前 V4 效果证据缺口显式列出；不存在待修改的目标内内容 | 不宣称效果已 effective；不自动创建新候选。Git commit/push 是门禁关闭后的交付验证，只记录在最终报告，避免 tracked 文档对自身提交 SHA 形成循环依赖 | Closed |
| `GATE-080` | `WP-EMP-NL-DESIGN-10` | closure | Employee自然语言扩展设计生效 | 否 | 服务合同核实、三轮内审和独立跨层设计评审完成，S0/S1/未处理S2均为0 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-080`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 文档维护者/评审者 | 公共合同实施前 | 分层/跨层设计评审与无环DAG检查 | 禁止依据未评审语义修改QueryPlan或Employee映射 | Closed |
| `GATE-081` | `WP-EMP-NL-QUERY-10` | closure | 多值合同与Employee查询non-live生效 | 否 | extractor、decoder/validator/binder、配置、v7模型任务、Employee mapper、Spring E2E、Java安全链、类型和正式隔离回归通过 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-081`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 实施者/评审者 | 真实UAT冻结前 | 代码对照设计复核、敏感扫描和下游零调用 | 禁止冻结或执行真实UAT | Closed |
| `GATE-082` | `WP-EMP-NL-UAT-10` | integration | Employee自然语言扩展受控UAT与最终收口 | 是 | 四候选累计模型不超过30、Employee search不超过30；candidate-04代表性13/13通过并与candidate-03不可变302/307组成15类完整证据；至少一个地区成功列表、安全与零调用合同全部成立 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-082`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 用户/实施者/评审者 | 本目标最终收口 | exact hash、预算、逐case、零泄漏、历史不可变与代码对照设计复核 | 禁止任何额外模型调用或新候选；证据失效时如实重新打开，不得改判历史 | Closed |
| `GATE-083` | `WP-KCORPUS-PIPELINE-01` | slice_implementation | 首次持久下载和候选索引写入 | 是 | 官方来源/P0-P2范围、显式外部workspace、解析工具版本、下载/存储/索引预算、精确旧alias目标与回滚方案明确；REQ/L1/L2三轮内审和独立评审通过 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-083`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 维护者/评审者 | 首次持久下载前 | strict Schema/设计/计划校验与分层跨层评审 | 只允许不落盘的官方来源和索引元数据审计 | Closed |
| `GATE-084` | `WP-KCORPUS-RELEASE-01` | release_effective | 候选 alias 生效 | 否 | P0及目标P1完成、P2清单、解析/OCR/表格质量、空正文/孤立附件、candidate完整性、typed keyword/vector、读取/出域/Evidence、回归和回滚演练通过 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-084`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 维护者/UAT/评审者 | alias切换前 | 完整性、权限、引用、alias原子性和历史hash | 候选保持未发布；现行alias不变 | Closed |
| `GATE-KRG-006` | `WP-KRETRIEVAL-IMPLEMENT-01` | slice_implementation | 原§20.36/20.55/20.66/20.68/20.71合同、评分、文号、可选Evidence与离线窗口诊断 | 是 | 三轮内审及正式分层/跨层复评通过；无fallback或公共接口/权限扩张 | [原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)：`GATE-KRG-006`关闭证据；运行身份及效果结论见UAT_01/00和原evidence | 设计维护者/评审者 | 新增量代码修改前 | S0/S1/未处理S2=0；不依赖live结果 | 已审增量准入不变；原§20.93.1本批已终止，授权不可续用 | Closed |
| `GATE-KRG-003` | `WP-KGRAPH-BUILD-01` | integration | 关系数据发布为可检索快照 | 否 | 关系 100% 绑定来源和时效；未知/失效/未审核关系不可用；Schema 和人工抽样通过 | 图谱 manifest、Schema、hash、抽样报告 | Knowledge 维护者 | 联合检索接入前 | 自动校验 + 人工抽样 | 保持图谱版本 disabled | Open |
| `GATE-KRG-004` | `WP-KHYBRID-RETRIEVAL-01` | release_effective | 图谱导航进入生产对象图 | 否 | 图谱只返回候选；所有回答回到授权原文；图谱不可用时无权限放宽、无图谱直接答案、无第二动作 | 联合 E2E、model/provider spy、引用验证 | Runtime/Knowledge 维护者 | 受控 UAT 前 | 代码对照设计评审 | 保持原文检索路径，图谱 disabled | Open |
| `GATE-KRG-005` | `WP-KNOWLEDGE-UAT-02` | closure | 路线图阶段收口 | 否 | P0/P1 功能、安全、时效、多跳和引用 case 完整；效果按现行口径如实分类；Blocker/Major=0 | UAT、有限 evidence、测试和评审报告 | 维护者/UAT | 最终收口 | Schema、安全 Gate、人工 rubric、回归 | 如实保留未完成和效果风险，不自动重跑 | Open |
| `GATE-KRG-007` | `WP-KGRAPH-CONTRACT-01` | slice_implementation | 图谱 Schema、类型化接口和导航合同进入实现 | 是 | Knowledge Graph REQ/L1/L2 获批，明确实体、关系、溯源、时效、授权和物理边界 | 新 Approved 设计 | 设计/维护者 | 图谱合同代码编写前 | 分层及跨层设计评审 | 不创建图谱代码、数据或依赖 | Open |

## 8. 外部资源与事实

| 资源 ID | 工作包 | 资源/事实 | 提供方 | 开始准备 | 必须完成 | 产物/引用 | 缺失影响 |
|---|---|---|---|---|---|---|---|
| `EXT-BQS-001` | `WP-EMP-ES-AUTH-02` | 现有 search/vector 调用方清单和 ADMIN/VIEWER 兼容性 | Employee 服务维护者 | 工作包开始 | 角色守卫生效前 | 调用方兼容结论与 Java tests | `GATE-068` 保持 Open |
| `EXT-BQS-002` | `WP-TXN-SEARCH-EXT-02` | Java Date/Jackson、Asia/Shanghai 和生产 TRANS_DATE precision 合同 | Transaction 服务维护者 | Date fake 合同阶段 | 日期真实集成前 | 不含业务数据的 timezone/precision evidence | `GATE-069` 保持 Open |
| `EXT-BQS-003` | `WP-BQ-CONTROLLED-LIVE-02` | 模型凭证、业务服务、授权用户与有限安全测试输入 | 用户/维护者 | 全部 non-live 通过后 | `GATE-070` 关闭前 | 内存凭证和有限调用预算，不记录敏感值 | 真实联调不执行 |
| `EXT-BQS-004` | `WP-BQ-UAT-HANDOFF-02` | 联系地址真实可检索样本与 Transaction 日期/金额数据 | 业务维护者 | controlled live 之后 | 首个 UAT 前 | 非敏感准备状态和 UAT checklist | 正式 UAT 不执行 |
| `EXT-KQ-001` | `WP-K-RUNTIME-WIRING-03` | es-query-service typed endpoint、Profile 配置、8908/8909 本地服务 | 当前仓库/维护者 | 接线前 | non-live/只读契约验证 | 固定配置与 existing tests | 功能 UAT 只允许 fake/contract 证据，不执行真实效果 |
| `EXT-KQ-002` | `WP-K-EFFECT-LIVE-05` | 精确模型授权、冻结索引/Profile/数据集和人工 rubric | 用户/维护者 | candidate-05 准备完成后 | `GATE-072` 关闭前 | 一次性 authorization、44 次 paid journal 与 append-only result/evidence | 已完成，Effectiveness=`Partially effective` |
| `EXT-KQ-003` | `WP-K-EFFECT-LIVE-06` | candidate-06 精确模型授权及冻结运行依赖 | 用户/维护者 | `GATE-076` 关闭后 | 已消费 | frozen HEAD/run/manifest/reference/预算的一次性授权与失败证据 | 不得复用 |
| `EXT-KQ-004` | `WP-K-EFFECT-LIVE-07` | candidate-07 精确模型授权及冻结运行依赖 | 用户/维护者 | 已完成 | 已终止 | 严格 authorization 与有限 failed_unconsumed evidence | 不得复用或产生额外 outbound |

## 9. Ready 队列与执行建议

Ready只表示直接技术依赖完成；本轮无实现授权。旧Done/Deferred不是待执行队列。

| 顺序 | 工作包 | 判定 | 未关闭依赖/门禁 | 选择理由 |
|---|---|---|---|---|
| 1 | `WP-BQ-FILTER-CONTRACT-02` | Done | - | 保留原完成范围 |
| 2 | `WP-BQ-FIELD-CONFIG-02` | Done | - | 保留原完成范围 |
| 3 | `WP-BQ-MODEL-CATALOG-02` | Done | - | 保留原完成范围 |
| 4 | `WP-EMP-SEARCH-ADAPTER-02` | Done | - | 保留原完成范围 |
| 5 | `WP-EMP-SEMANTIC-ADAPTER-02` | Done | - | 保留原完成范围 |
| 6 | `WP-EMP-ES-AUTH-02` | Done | - | 保留原完成范围 |
| 7 | `WP-TXN-SEARCH-EXT-02` | Done | - | 保留原完成范围 |
| 8 | `WP-TXN-DATE-WIRE-COMPAT-03` | Done | - | 保留原完成范围 |
| 9 | `WP-BQ-RUNTIME-CUTOVER-02` | Done | - | 保留原完成范围 |
| 10 | `WP-EMP-DETAIL-RETIRE-02` | Done | - | 保留原完成范围 |
| 11 | `WP-BQ-NONLIVE-E2E-02` | Done | - | 保留原完成范围 |
| 12 | `WP-BQ-CONTROLLED-LIVE-02` | Done | - | 保留原完成范围 |
| 13 | `WP-TXN-TEXT-POLICY-COMPAT-03` | Done | - | 保留原完成范围 |
| 14 | `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | Done | - | 保留原完成范围 |
| 15 | `WP-BQ-UAT-HANDOFF-02` | Done | - | 保留原完成范围 |
| 16 | `WP-BQ-COMPLETION-CLOSURE-04` | Done | - | 保留原完成范围 |
| 17 | `WP-K-BASELINE-03` | Done | - | 保留原完成范围 |
| 18 | `WP-K-RUNTIME-WIRING-03` | Done | - | 保留原完成范围 |
| 19 | `WP-K-SPRING-NONLIVE-E2E-03` | Done | - | 保留原完成范围 |
| 20 | `WP-K-FUNCTIONAL-UAT-03` | Done | - | 保留原完成范围 |
| 21 | `WP-K-EFFECT-DIAG-03` | Done | - | 保留原完成范围 |
| 22 | `WP-K-EFFECT-OPT-03` | Done | - | 保留原完成范围 |
| 23 | `WP-K-EFFECT-CANDIDATE-05-PREP` | Done | - | 保留原完成范围 |
| 24 | `WP-K-EFFECT-LIVE-05` | Done | - | 保留原完成范围 |
| 25 | `WP-K-CLOSURE-03` | Done | - | 保留原完成范围 |
| 26 | `WP-DOC-CONSISTENCY-06` | Done | - | 保留原完成范围 |
| 27 | `WP-PY-REGRESSION-REPRO-06` | Done | - | 保留原完成范围 |
| 28 | `WP-K-EFFECT-DIAG-06` | Done | - | 保留原完成范围 |
| 29 | `WP-K-EFFECT-OPT-06` | Done | - | 保留原完成范围 |
| 30 | `WP-K-EFFECT-CANDIDATE-06-PREP` | Done | - | 保留原完成范围 |
| 31 | `WP-K-EFFECT-LIVE-06` | Deferred | - | 原运行失败/取消，禁止续跑 |
| 32 | `WP-K-EFFECT-HARNESS-CLOSURE-07` | Done | - | 保留原完成范围 |
| 33 | `WP-K-EFFECT-CANDIDATE-07-PREP` | Done | - | 保留原完成范围 |
| 34 | `WP-K-EFFECT-LIVE-07` | Deferred | - | 原运行失败/取消，禁止续跑 |
| 35 | `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | Done | - | 保留原完成范围 |
| 36 | `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | Done | - | 保留原完成范围 |
| 37 | `WP-SEVEN-ITEM-CLOSURE-06` | Done | - | 保留原完成范围 |
| 38 | `WP-K-UAT-TRACE-CLOSURE-09` | Done | - | 保留原完成范围 |
| 39 | `WP-K-REWRITE-SCHEMA-11` | Done | - | 保留原完成范围 |
| 40 | `WP-EMP-NL-DESIGN-10` | Done | - | 保留原完成范围 |
| 41 | `WP-BQ-MULTIVALUE-CONTRACT-10` | Done | - | 保留原完成范围 |
| 42 | `WP-EMP-NL-QUERY-10` | Done | - | 保留原完成范围 |
| 43 | `WP-EMP-NL-UAT-10` | Done | - | 保留原完成范围 |
| 44 | `WP-EMP-NL-CLOSURE-10` | Done | - | 保留原完成范围 |
| 45 | `WP-KCORPUS-AUDIT-01` | Done | - | 保留原完成范围 |
| 46 | `WP-KCORPUS-DESIGN-01` | Done | - | 保留原完成范围 |
| 47 | `WP-KCORPUS-PIPELINE-01` | Done | - | 保留原完成范围 |
| 48 | `WP-KCORPUS-INDEX-01` | Done | - | 保留原完成范围 |
| 49 | `WP-KCORPUS-UAT-01` | Done | - | 保留原完成范围 |
| 50 | `WP-KCORPUS-RELEASE-01` | Done | - | 保留原完成范围 |
| 51 | `WP-KRETRIEVAL-DIAG-01` | Done | - | 保留原完成范围 |
| 52 | `WP-KRETRIEVAL-DESIGN-01` | Done | - | 保留原完成范围 |
| 53 | `WP-KRETRIEVAL-IMPLEMENT-01` | Done | - | 保留原完成范围 |
| 54 | `WP-KRETRIEVAL-NONLIVE-01` | Done | - | 保留原完成范围 |
| 55 | `WP-KRETRIEVAL-UAT-01` | Deferred | - | 原运行失败/取消，禁止续跑 |
| 56 | `WP-KRETRIEVAL-QUALITY-01` | Deferred | - | 原运行失败/取消，禁止续跑 |
| 57 | WP-KREBUILD-DESIGN-01 | Done | - | 保留原完成范围 |
| 58 | WP-KREBUILD-CONTRACT-01 | Ready | - | 按§21后续新授权 |
| 59 | WP-KREBUILD-RETRIEVAL-01 | Blocked | WP-KREBUILD-CONTRACT-01 | 按§21后续新授权 |
| 60 | WP-KREBUILD-EVIDENCE-01 | Blocked | WP-KREBUILD-CONTRACT-01 | 按§21后续新授权 |
| 61 | WP-KREBUILD-COMPOSE-01 | Blocked | WP-KREBUILD-RETRIEVAL-01、WP-KREBUILD-EVIDENCE-01 | 按§21后续新授权 |
| 62 | WP-KREBUILD-MEASURE-01 | Blocked | WP-KREBUILD-COMPOSE-01 | 按§21后续新授权 |
| 63 | WP-KORG-DESIGN-01 | Done | - | 保留原完成范围 |
| 64 | WP-KORG-NORMALIZE-01 | Ready | - | 按§22后续新授权 |
| 65 | WP-KORG-CHUNK-01 | Blocked | WP-KORG-NORMALIZE-01 | 按§22后续新授权 |
| 66 | WP-KORG-REPRESENT-01 | Blocked | WP-KORG-NORMALIZE-01 | 按§22后续新授权 |
| 67 | WP-KORG-COMPARE-01 | Blocked | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | 按§22后续新授权 |
| 68 | WP-KORG-RELEASE-01 | Blocked | WP-KORG-COMPARE-01 | 按§22后续新授权 |
| 69 | `WP-KCORPUS-ATTACHMENT-01` | Done | - | 原阶段A汇总身份 |
| 70 | `WP-KGRAPH-CONTRACT-01` | Blocked | `WP-KCORPUS-AUDIT-01`；`GATE-KRG-007` | 路线方向未获详细合同；保留Blocked，不纳入当前实施主线 |
| 71 | `WP-KGRAPH-BUILD-01` | Blocked | `WP-KCORPUS-ATTACHMENT-01`、`WP-KGRAPH-CONTRACT-01`；- | 路线方向未获详细合同；保留Blocked，不纳入当前实施主线 |
| 72 | `WP-KHYBRID-RETRIEVAL-01` | Blocked | `WP-KRETRIEVAL-QUALITY-01`、`WP-KGRAPH-BUILD-01`；- | 路线方向未获详细合同；保留Blocked，不纳入当前实施主线 |
| 73 | `WP-KNOWLEDGE-UAT-02` | Blocked | `WP-KHYBRID-RETRIEVAL-01`；- | 路线方向未获详细合同；保留Blocked，不纳入当前实施主线 |

## 10. 实施交接

旧Done/Deferred包的交接列仅追溯当时范围；Deferred的失效运行和已取消阶段B不再开放实现或调用。当前可实施性仅由新包与另行目标授权判定，本次文档整理不执行任何代码。

旧包表行仅解释原授权范围，均非当前执行许可。新增包的详细方法、外部资源及回滚见§21/22。

| 工作包 | 允许动作 | 禁止动作 | 预期文件/模块 | 来源设计 ID | 测试与验证 | 开放后续门禁 | 建议执行技能 |
|---|---|---|---|---|---|---|---|
| `WP-BQ-FILTER-CONTRACT-02` | fake filters/decoder/validator/binder | 真实模型/业务调用 | business/query_plan | `DR-BQCOM-101/103` | `VAL-BQCOM-101` | 字段配置依赖 | implement-from-detailed-design |
| `WP-BQ-FIELD-CONFIG-02` | 单文件 typed config/snapshot | 配置平台/扩字段 | business/contracts/settings/json | `DR-BQCOM-102/104` | `VAL-BQCOM-101/102` | Model/Adapter 依赖 | implement-from-detailed-design |
| `WP-BQ-MODEL-CATALOG-02` | fake v3 task/catalog | 读取密钥/真实模型 | model/deepseek/business_query_plan | `DR-MODEL-101～105` | `VAL-MODEL-101/102` | 组合根依赖 | implement-from-detailed-design |
| `WP-EMP-SEARCH-ADAPTER-02` | fake ES search/strict hits | 真实 ES/数据库/endpoint 扩张 | adapters/employee | `DR-EMP-101/103/104` | `VAL-EMP-101/103` | 组合根依赖 | implement-from-detailed-design |
| `WP-EMP-SEMANTIC-ADAPTER-02` | fake vector-search/profile | 用户 vector/filter/双调用 | adapters/employee | `DR-EMP-102/104` | `VAL-EMP-101/103` | 组合根依赖 | implement-from-detailed-design |
| `WP-EMP-ES-AUTH-02` | 两 ES POST endpoint 专用共享 converter、真实安全链矩阵和 detail/fallback 回归 | 新角色、新接口、全局 converter 变更、未核实直接生效 | EmployeeEsController/guard/EmployeeDetailSecurityConfiguration | `DR-EMP-105`; `DR-AUTH-007` | `VAL-EMP-102` | `GATE-068` | implement-from-detailed-design |
| `WP-TXN-SEARCH-EXT-02` | fake Date/Decimal/page/sort 和 Java tests | 改 DTO/SQL、未经证实相对日期 | adapters/transaction 与现有 Java tests | `DR-TXN-101～105` | `VAL-TXN-101/102` | `GATE-069` | implement-from-detailed-design |
| `WP-TXN-DATE-WIRE-COMPAT-03` | strict 双形态 response codec、真实 Spring JSON test、零模型实际响应验证 | 改 DTO/服务 Jackson、接受任意 ISO、重查 | Transaction codec/tests 与既有 Java test scope | `DR-TXN-102/105` | `VAL-TXN-101/102/103` | `GATE-069/070` | implement-from-detailed-design |
| `WP-BQ-RUNTIME-CUTOVER-02` | 组合根与三动作 fake 对象图 | Core/HTTP/Knowledge 破坏 | bootstrap/graph | `DR-CORE-101～104` | `VAL-CORE-101/102` | non-live E2E | implement-from-detailed-design |
| `WP-EMP-DETAIL-RETIRE-02` | caller/历史核实和移除目标绑定 | 删除冻结 evidence 或仍被使用代码 | Employee provider/生产组合根 | `DR-EMP-106` | `TEST-EMP-107` | controlled live 依赖 | implement-from-detailed-design |
| `WP-BQ-NONLIVE-E2E-02` | fake 三动作、拒绝矩阵和 Knowledge 回归 | 真实凭证/真实调用 | system_e2e/tests | `DR-CORE-101`; `DR-BQCOM-106` | fake E2E/strict mypy | `GATE-070` 准备 | implement-from-detailed-design |
| `WP-BQ-CONTROLLED-LIVE-02` | 明确授权后有限真实集成 | 无授权费用、补跑、敏感持久化 | 受控 integration runner | `DR-MODEL-104`; `DR-EMP-105`; `DR-TXN-105` | 单调用/权限/敏感扫描 | `GATE-UAT-007` 准备 | implement-from-detailed-design |
| `WP-TXN-TEXT-POLICY-COMPAT-03` | code-bound `eq/contains` 文本策略、fake 兼容矩阵与独立 UAT 结果路径 | 放宽 LIKE 通配、修改 SQL/DTO、覆盖失败历史 | business/contracts/query_plan 与 UAT tests/launcher | `DR-BQCOM-101`; `DR-TXN-101` | `TEST-BQCOM-102`; `TEST-TXN-101` | `GATE-UAT-007` 重新准入 | implement-from-detailed-design |
| `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | v4 Prompt、exact unsupported 明确反例、fake 零调用、版本化 manifest | 本地语义 Resolver、模型真实调用、覆盖旧 manifest 或失败历史 | model/deepseek/business_query_plan 与 system_e2e/tests | `DR-MODEL-101/104`; `DR-EMP-102` | `TEST-MODEL-102/104`; `VAL-MODEL-101/102` | `GATE-UAT-007` 重新准入 | implement-from-detailed-design |
| `WP-BQ-UAT-HANDOFF-02` | 授权后执行四阶段 UAT | 旧 detail 证据替代新用例 | UAT 用例及阶段结论 | `REQ-BQS-012` | UAT 验收矩阵 | 正式验收结论 | code-review-against-docs |
| `WP-BQ-COMPLETION-CLOSURE-04` | 当前 Spring→Runtime、历史隔离、35 用例追踪、全量回归和正式评审 | 重写历史 evidence、重复真实调用或为通过而弱化测试 | agent-service、agent-runtime 当前测试与 P3/UAT | `REQ-BQS-012`; `UAT_00` v1.14 | 当前 Spring/Runtime/Employee/Transaction 测试与全量 non-live 回归 | 22 项完成标准最终审计 | code-review-against-docs |
| `WP-K-BASELINE-03` | 文档语义修订、内审与独立评审 | 代码实施、真实调用 | L1/L2/P3/UAT_01 | `DR-KFLOW-011～013`; `DR-KEV-013～015` | strict validators、分层/跨层评审 | `GATE-071` | architecture/detailed/design-review skills |
| `WP-K-RUNTIME-WIRING-03` | 默认关闭开关、同 Runtime Provider/task/client 装配 | 第二 Runtime、业务接口变化 | bootstrap/main/knowledge retrieval | `DR-KFLOW-011～013`; `DR-KRET-011/012` | unit/contract/lifecycle/mypy | non-live E2E | implement-from-detailed-design |
| `WP-K-SPRING-NONLIVE-E2E-03` | 当前对象图 fake 完整链、拒绝/失败/调用计数 | 真实付费模型、历史专用 Runtime 代替 | agent-service E2E、agent-runtime system_e2e | `UAT_01` 第 5 节 | Spring/Python E2E | `GATE-UAT-008` | implement-from-detailed-design |
| `WP-K-FUNCTIONAL-UAT-03` | 逐 case 追踪与功能结论 | 把功能通过当效果达标 | Knowledge UAT assets | `UAT_01` 第 5～6 节 | traceability Schema/引用/执行 | effect diagnosis | code-review-against-docs |
| `WP-K-EFFECT-DIAG-03` | 只读 candidate-04 指标与根因 | 改历史、补跑或保存敏感内容 | evaluation/knowledge diagnostics | `DR-KEV-014` | history hash/Schema/tests | optimization | implement-from-detailed-design |
| `WP-K-EFFECT-OPT-03` | 证据支持的最小新版本 | 阈值/validator/正文/index/权限放宽 | Knowledge prompt/config/selection/harness | `DR-KEV-014` | fake safety/effect regression | candidate prep | implement-from-detailed-design |
| `WP-K-EFFECT-CANDIDATE-05-PREP` | 新 manifest/hash/reference/budget 和 fake 失败关闭 | 读取密钥或 outbound | evaluation/knowledge candidate-05 assets | `DR-KEV-015` | preparation/history/hash tests | `GATE-072` | implement-from-detailed-design |
| `WP-K-EFFECT-LIVE-05` | 精确授权后执行一次冻结效果 UAT | 未绑定授权、重试、补跑、改判 | append-only live assets | `UAT_01` 第 7 节 | P5 Schema、安全 Gate、rubric | 效果结论 | implement-from-detailed-design |
| `WP-K-CLOSURE-03` | 全量验证、正式代码评审、状态与 Git 收口 | 关闭未执行的 live gate | 当前目标代码/测试/文档 | 全部 Knowledge DR/VAL | review-and-fix、回归、git checks | 本阶段完成 | code-review-against-docs |
| `WP-DOC-CONSISTENCY-06` | 原子修订当前文档、三轮内审和独立评审 | 代码优化、历史改写、无关重排 | L0/L1/L2/P3/UAT/ARCHITECTURE | 当前代码和 candidate-04/05 事实 | strict validators、版本/DAG/跨层评审 | `GATE-073` | architecture/detailed/plan/design-review skills |
| `WP-PY-REGRESSION-REPRO-06` | 临时隔离环境安装当前源码并运行测试 | 全局安装、生产依赖、冻结资产修改 | agent-runtime scripts/tests | Transaction frozen host 合同 | 14 项 host/preflight、全量 non-live、历史 hash | `GATE-074` | implement-from-detailed-design |
| `WP-K-EFFECT-DIAG-06` | 只读重算 candidate-05 指标和逐 case 根因 | 修改历史、gold、阈值或真实调用 | evaluation/knowledge diagnostics | `DR-KEV-013～015` | Schema、指标重算、history hash | 效果设计修订 | implement-from-detailed-design |
| `WP-K-EFFECT-OPT-06` | 证据支持的新版本与 non-live 反证 | 放宽 validator/权限、改正文/index | Knowledge task/selection/config/tests | 评审后的 Knowledge L1/L2 | unit/contract/E2E/mypy/history | `GATE-075` | implement-from-detailed-design |
| `WP-K-EFFECT-CANDIDATE-06-PREP` | 新 manifest/hash/reference/budget 与 fake 失败关闭 | 读取密钥、outbound、覆盖旧候选 | evaluation/knowledge candidate-06 assets | 更新后的 `DR-KEV` 与 `UAT_01` | preparation/history/hash tests | `GATE-076/077` | implement-from-detailed-design |
| `WP-K-EFFECT-LIVE-06` | 保存唯一已消费失败运行并完成历史校验 | 重跑、补跑、续跑、改判或伪造结果 | append-only candidate-06 authorization/consumed/journals/failure | `UAT_01` 效果合同；`DR-KEV-020` | 精确哈希、52 变体、44 paid、retry=0、failure code | Harness closure | implement-from-detailed-design |
| `WP-K-EFFECT-HARNESS-CLOSURE-07` | 固定 candidate-06 失败历史并共享快照 allowlist | 修改生产 src、历史 evidence、放宽 dirty-source | evaluation/knowledge Harness/tests | `DR-KEV-020` | history、fake snapshot、全量 non-live | candidate-07 准备 | implement-from-detailed-design |
| `WP-K-EFFECT-CANDIDATE-07-PREP` | 新 run/manifest/hash/reference/budget 与 fake 失败关闭 | 读取密钥、outbound、覆盖历史候选 | evaluation/knowledge 新候选资产 | `DR-KEV-015/019/020` | preparation/history/hash tests | `GATE-079` | implement-from-detailed-design |
| `WP-K-EFFECT-LIVE-07` | 保存一次性 `failed_unconsumed` 终态并完成历史校验 | 重试、补跑、续跑、改判或 candidate-08 | append-only authorization/failure | `UAT_01` 效果合同 | 精确哈希、零调用、失败阶段与敏感扫描 | Harness closure | implement-from-detailed-design |
| `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | 分离准备态和授权后 live preflight | 修改历史 manifest/evidence、读取密钥或 outbound | evaluation/knowledge launcher/tests | `DR-KEV-020～022` | 定向/non-live/AST/history hash | 设计落实审计 | implement-from-detailed-design |
| `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | 全部当前设计落实矩阵与目标内缺口修复 | 以历史/fake/skip冒充当前实现或扩大公共契约 | 当前文档、代码、配置、测试和 UAT/evidence | 全部当前 REQ/DR/VAL | 交叉追踪、代码对照设计评审 | `GATE-078` | code-review-against-docs |
| `WP-SEVEN-ITEM-CLOSURE-06` | 全量验证、正式代码评审、状态与 Git 收口 | 隐瞒失败、提前关闭 live 或覆盖历史 | 当前目标代码/测试/文档 | 本轮全部 DR/VAL/UAT | review-and-fix、全量回归、git checks | 本目标完成 | code-review-against-docs |
| `WP-K-UAT-TRACE-CLOSURE-09` | 更新当前 traceability、strict validator/tests 和直接状态引用 | 修改历史 candidate/evidence、产生新模型 outbound、创建 candidate-08 | `agent-runtime/tests/uat`、P3/UAT_01/ARCHITECTURE | `UAT_00 v1.24`；`UAT_01 v1.12` | 35/37 case、effect evidence binding、全量回归、设计/代码评审 | 无新增 Gate | implement-from-detailed-design + code-review-against-docs |
| `WP-EMP-NL-DESIGN-10` | 核实既有接口并原子修订目标文档、内审和独立评审 | 修改公共DTO/endpoint/权限/ES结构或以本地规则替代LLM | REQ/L1/L2/P3/UAT | `DR-MODEL-106/107`; `DR-BQCOM-109～111`; `DR-EMP-109～111` | strict validators、三轮内审、独立跨层评审 | `GATE-080` | architecture/detailed/design-review skills |
| `WP-BQ-MULTIVALUE-CONTRACT-10` | typed `value_refs`、operator shape、组合和region profile的最小内部合同 | 放宽validator、发送敏感真值、修改公共业务DTO | business/query_plan/contracts/settings、model catalog/task | `DR-MODEL-106/107`; `DR-BQCOM-109～111` | unit/contract/mypy/compileall | Employee实现 | implement-from-detailed-design |
| `WP-EMP-NL-QUERY-10` | extractor仅保护值、固定search映射、fake/Spring/Java验证 | workBase专用分支、本地Resolver、新endpoint或fallback | protected input、employee codec、bootstrap及直接测试 | `DR-EMP-109～111` | extractor/mapper/E2E/security/full non-live | `GATE-081/082` | implement-from-detailed-design |
| `WP-EMP-NL-UAT-10` | 冻结候选、按总预算执行一次性受控UAT并保存有限证据 | 重试、补跑、续跑、原始敏感数据或额外endpoint | `tests/uat/employee_nl`及版本化launcher/evidence | `UAT_00` 第13节 | exact budget/case/hash/security/history | `GATE-082` | implement-from-detailed-design |
| `WP-EMP-NL-CLOSURE-10` | 组合历史验证、全量回归、正式评审、状态同步和Git交付 | 修改冻结证据、额外live、隐藏用户无关修改 | 当前目标测试/文档与Git交付 | 本轮全部DR/UAT | review-and-fix、全量验证、git checks | 本目标完成 | code-review-against-docs |
| `WP-K-REWRITE-SCHEMA-11` | 维护已完成 Rewrite V2 当前合同和验证台安全展示 | 改写历史 V1/evidence 或新增 live | Knowledge rewrite/UI 当前接缝 | `DR-KFLOW-004/012` | 合同、页面安全和回归 | 阶段 A 在线基线 | implement-from-detailed-design |
| `WP-KCORPUS-AUDIT-01` | 只读 ES/官方来源/附件引用盘点并生成有限清单 | 持久附件、ES 写入或 alias 修改 | `knowledge-corpus-tools` audit、外部 workspace manifests | `DR-KRET-013`; `REQ-KCORPUS-001/005` | strict Schema、全量计数、抽样、零写入 | `GATE-083` | implement-from-detailed-design |
| `WP-KCORPUS-DESIGN-01` | 原子修订语料生命周期合同并评审 | 设计通过前下载/解析/候选写入 | REQ/L0/L1/L2/P3/UAT/ROADMAP | `REQ-KCORPUS-001～006`; `DR-KRET-013～026` | 三轮内审、strict validator、独立评审 | `GATE-083` | architecture/detailed/design-review skills |
| `WP-KCORPUS-PIPELINE-01` | 入口门禁后下载、immutable store、解析/OCR/表格/chunk/embedding | 非官方来源、静默丢失、阶段 B 调参 | `knowledge-corpus-tools`、外部 workspace | `IMPL-KRET-010～014` | `TEST-KRET-010～017`; `VAL-KRET-006` | Candidate Index | implement-from-detailed-design |
| `WP-KCORPUS-INDEX-01` | 创建精确新索引、复制基线、写入合格 chunk、生成快照/catalog | 原地覆盖、删除旧索引、公共 DTO 变化 | tool indexing、egress catalog v2、live binding | `DR-KRET-022～024`; `DR-KEV-023～025` | mapping/count/fingerprint/full-membership/typed retrieval | Stage A UAT | implement-from-detailed-design |
| `WP-KCORPUS-UAT-01` | 在 candidate 上执行14类直接 typed UAT | 以阶段 B topK 作为阶段 A 通过条件 | UAT trace/limited evidence | `UAT-KCORPUS-A-01～14` | keyword/vector/授权/Evidence/P0 | `GATE-084` | code-review-against-docs |
| `WP-KCORPUS-RELEASE-01` | 门禁后原子切换、冒烟、回滚演练、最终发布 | 未验收切换、删除旧索引或模糊回滚 | release tooling、serviceCenter binding、文档状态 | `DR-KRET-025` | alias target/UUID/Profile/policy/history/regression | 阶段 A 完成 | implement-from-detailed-design + code-review-against-docs |
| `WP-KRETRIEVAL-DIAG-01` | 只读根因对照 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | DESIGN | implement-from-detailed-design |
| `WP-KRETRIEVAL-DESIGN-01` | 目标文档修订与评审 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-024、DR-KRET-029、DR-KEV-029/030 | UAT_01 §14；§20 | IMPLEMENT | design-doc-review |
| `WP-KRETRIEVAL-IMPLEMENT-01` | 门禁后最小实施 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-024、DR-KRET-029、DR-KEV-029/030 | UAT_01 §14；§20 | NONLIVE | implement-from-detailed-design |
| `WP-KRETRIEVAL-NONLIVE-01` | 当前代码non-live验证 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-024、DR-KRET-029、DR-KEV-029/030 | 原UAT_01 §14.21；原§20.40 | UAT | implement-from-detailed-design |
| `WP-KRETRIEVAL-UAT-01` | 冻结后一次有限真实UAT | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | QUALITY | implement-from-detailed-design |
| `WP-KRETRIEVAL-QUALITY-01` | 正式评审及状态/Git交付 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | 阶段B完成 | code-review-against-docs |
| WP-KREBUILD-DESIGN-01 | 保留已完成设计 | 本轮代码/服务/模型/数据写入禁止 | 本轮12份授权文档、分类决策、方案及实施/验收边界 | 本轮12份授权文档、分类决策、方案及实施/验收边界 | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KREBUILD-CONTRACT-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KREBUILD-RETRIEVAL-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KREBUILD-EVIDENCE-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KREBUILD-COMPOSE-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | current-root、Spring E2E、37功能重新逐case、Business35关键防退、Java安全/类型/non-live、正式代码评审；Blocker/Major0 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KREBUILD-MEASURE-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | 人工gold/语料就绪、新独立授权、版本绑定及预算预检；按预置判据分类，真实失败停止；未达标不写Passed | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KORG-DESIGN-01 | 保留已完成设计 | 本轮代码/服务/模型/数据写入禁止 | 本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | 本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | 三轮内审、两轮正式复核、文档验证通过；以包含本节的目标提交推送成功为Git收口证明 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KORG-NORMALIZE-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | TEST-KRET-301、hash/span反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KORG-CHUNK-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | TEST-KRET-302；条件/否定/表格/短块/长条款均可追溯；不静默遗漏 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KORG-REPRESENT-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | TEST-KRET-303；明确实际长度单位/版本，无截断；旧未知不回填 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KORG-COMPARE-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | fake/类型→人工原文→另授权BGE及只读typed；逐阶段损失、保留题、安全与停止规则 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| WP-KORG-RELEASE-01 | 取得后续授权后按L2最小实施 | 本轮代码/服务/模型/数据写入禁止 | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；无证据不得发布 | 无新增门禁；独立授权与完成条件仍需满足 | implement-from-detailed-design |
| `WP-KCORPUS-ATTACHMENT-01` | 入口门禁通过后按版本化流水线实施；发布另受发布门禁控制 | 覆盖旧索引、无来源导入、静默忽略解析失败 | `knowledge-corpus-tools`、`es-query-service` 内部 mapping/Profile、版本化 policy catalog | `DR-KRET-013～025`、`DR-KEV-023～025` | 解析、OCR、表格、hash、索引、授权、回滚 | 发布后开放 `GATE-KRG-003` | `implement-from-detailed-design` |
| `WP-KGRAPH-CONTRACT-01` | 按已批准设计实现最小实体、关系、溯源、时效和类型化接口合同 | 未批准先编码、引入 Neo4j、让 Agent 看到物理查询 | 待详细设计确定的 `agent-runtime`/`es-query-service` 接缝 | 待新增 REQ/DR/IMPL/TEST/VAL | Schema fake、接口合同和物理信息零暴露 | `GATE-KRG-003` | `implement-from-detailed-design` |
| `WP-KGRAPH-BUILD-01` | 按批准合同构建版本化关系数据 | 修改原文、无来源关系、自动生效 | 待详细设计确定 | 待新增 IMPL/TEST/VAL | 溯源、时效、hash、人工抽样 | `GATE-KRG-004` | `implement-from-detailed-design` |
| `WP-KHYBRID-RETRIEVAL-01` | 图谱扩展候选后回到授权原文检索 | 图谱直接回答、第二链路、物理资源暴露 | `agent-runtime` Knowledge + `es-query-service` 类型化接口内部实现 | 待新增 DR/IMPL/TEST/VAL | provider spy、授权、原文引用、故障注入 | `GATE-KRG-005` | `implement-from-detailed-design` |
| `WP-KNOWLEDGE-UAT-02` | non-live 和经精确授权的受控效果测量 | 自动重跑、改 gold/阈值、保存敏感内容 | UAT/evaluation/evidence 范围 | 待批准 UAT/P3 | 安全 Gate、Q 指标、人工 rubric、历史 hash | 阶段收口 | `code-review-against-docs` |

## 11. 风险与回滚

Employee 旧调用方不兼容、workBase 数据无效、raw hits 泄漏、Date 时区/精度未证明、Decimal 精度、slot 出域以及 non-live gate 被误用于 live 是主要风险。按 action 关闭、移除目标组合根和保留历史 evidence 回滚；不得重新启用 Resolver、删除测试、扩张业务接口或放宽 validator。

## 12. 追踪矩阵

旧包追踪指整理前冻结范围；新包的设计ID、落点和验收不从旧通过推导。旧包中的原章节号、任务和版本均按[整理前P3](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)及[原UAT_01](历史文档/2026-09-14-unified-v3-baseline/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md)解释，不是当前章节权威。

| 工作包 | 来源 REQ/CON/DR | IMPL | TEST | VAL | 交付状态 |
|---|---|---|---|---|---|
| `WP-BQ-FILTER-CONTRACT-02` | `DR-BQCOM-101/103` | `IMPL-BQCOM-101/106` | `TEST-BQCOM-101/102/104` | `VAL-BQCOM-101` | Done |
| `WP-BQ-FIELD-CONFIG-02` | `DR-BQCOM-102/104` | `IMPL-BQCOM-102/103/104/105/107/108` | `TEST-BQCOM-103/106` | `VAL-BQCOM-101/102` | Done |
| `WP-BQ-MODEL-CATALOG-02` | `DR-MODEL-101～105` | `IMPL-MODEL-101～105` | `TEST-MODEL-101～105` | `VAL-MODEL-101/102` | Done |
| `WP-EMP-SEARCH-ADAPTER-02` | `DR-EMP-101/103/104` | `IMPL-EMP-101～105/108` | `TEST-EMP-101/102/104/105` | `VAL-EMP-101/103` | Done |
| `WP-EMP-SEMANTIC-ADAPTER-02` | `DR-EMP-102/104` | `IMPL-EMP-101～105` | `TEST-EMP-103/104` | `VAL-EMP-101/103` | Done |
| `WP-EMP-ES-AUTH-02` | `DR-EMP-105`; `DR-AUTH-007` | `IMPL-EMP-106/107/109/110` | `TEST-EMP-106` | `VAL-EMP-102` | Done |
| `WP-TXN-SEARCH-EXT-02` | `DR-TXN-101～105` | `IMPL-TXN-101～107` | `TEST-TXN-101～106` | `VAL-TXN-101/102/103` | Done |
| `WP-TXN-DATE-WIRE-COMPAT-03` | `DR-TXN-102/105` | `IMPL-TXN-103/106` | `TEST-TXN-102/105` | `VAL-TXN-101/102/103` | Done |
| `WP-BQ-RUNTIME-CUTOVER-02` | `DR-CORE-101～104` | `IMPL-CORE-101～104` | `TEST-CORE-101～104` | `VAL-CORE-101/102` | Done |
| `WP-EMP-DETAIL-RETIRE-02` | `DR-EMP-106` | `IMPL-EMP-105` | `TEST-EMP-107` | `VAL-EMP-103` | Done |
| `WP-BQ-NONLIVE-E2E-02` | `DR-BQCOM-106`; `DR-CORE-102` | 现有 system_e2e 测试入口 | 三动作 fake 与零调用 | non-live/mypy/compileall | Done |
| `WP-BQ-CONTROLLED-LIVE-02` | `DR-MODEL-104`; `DR-BQCOM-107/108`; `DR-EMP-105/107/108`; `DR-TXN-102/105` | action 独立超时、partial page、生产 Date codec、受控 runner、五次不可变失败及新的独立有限结果 | controlled-run06 六场景真实三动作和拒绝矩阵 | `GATE-069/070` 已关闭 | Done |
| `WP-TXN-TEXT-POLICY-COMPAT-03` | `DR-BQCOM-101`; `DR-TXN-101` | `IMPL-BQCOM-101`; `IMPL-BQCOM-102`; `IMPL-TXN-102`; UAT runner | `eq` 下划线接受、contains 通配拒绝、下游零调用与历史 hash | `TEST-BQCOM-102`; `TEST-TXN-101` | Done |
| `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | `DR-MODEL-101/104`; `DR-EMP-102` | `IMPL-MODEL-101`; system_e2e manifest/runner | semantic+location/relative-date unsupported 零调用、两次 failure hash | `TEST-MODEL-102/104`; `VAL-MODEL-101/102` | Done |
| `WP-BQ-UAT-HANDOFF-02` | `REQ-BQS-012` | UAT 环境与用例清单 | UAT 四阶段和 run03 18 项真实场景 | `GATE-UAT-007` 已关闭，有限结果 hash 已绑定 | Done |
| `WP-BQ-COMPLETION-CLOSURE-04` | `REQ-BQS-012`; `UAT_00` v1.14 | 严格 JSON 错误映射、当前 Spring E2E、历史生产 Provider 清理、UAT v2 追踪 | 35 用例引用、Transaction frozen-host 双环境验证、全量相关回归 | 正式代码对照设计评审 | Done |
| `WP-K-BASELINE-03` | `L1_00/L1_01`; `DR-KFLOW-011～013`; `DR-KEV-013～015` | 文档与 DAG | 三轮内审、独立评审、strict validators | `GATE-071` | Done |
| `WP-K-RUNTIME-WIRING-03` | `DR-KFLOW-011～013`; `DR-KRET-011/012` | `IMPL-KFLOW-009/010`; `IMPL-KRET-009` | `TEST-KFLOW-009`; `TEST-KRET-009` | `VAL-KFLOW-005`; `VAL-KRET-005` | Done |
| `WP-K-SPRING-NONLIVE-E2E-03` | `UAT_01` 第 5 节 | 当前 production bootstrap + fake provider | `TEST-KFLOW-010`; UAT functional matrix | Spring→Runtime/call counts | Done |
| `WP-K-FUNCTIONAL-UAT-03` | `REQ-KFLOW-001～006`; `REQ-KRET-001～005`; `REQ-KEV-001～005` | traceability/evidence | `UAT-K-*` | `GATE-UAT-008` | Done |
| `WP-K-EFFECT-DIAG-03` | `DR-KEV-013/014` | `IMPL-KEV-009` diagnostic | `TEST-KEV-009` | history hash/Schema | Done |
| `WP-K-EFFECT-OPT-03` | `DR-KEV-014` | 域目录 v2 与 Summary v3 | fake safety/effect tests | `VAL-KEV-005` | Done |
| `WP-K-EFFECT-CANDIDATE-05-PREP` | `DR-KEV-015` | candidate-05 non-live assets | `TEST-KEV-010` | manifest/hash/budget/history | Done |
| `WP-K-EFFECT-LIVE-05` | `UAT_01` 第 7 节 | append-only live runner/result | frozen P5 | `GATE-072` | Done |
| `WP-K-CLOSURE-03` | 全部 Knowledge 设计/UAT | review fixes/state sync | 全量 Knowledge/Core/Business/Java | 正式代码评审与 Git | Done |
| `WP-DOC-CONSISTENCY-06` | 当前 L0/L1/L2/P3/UAT/ARCH 状态 | 原子文档纠偏 | strict validators/版本与 DAG | `GATE-073` | Done |
| `WP-PY-REGRESSION-REPRO-06` | Transaction frozen host 合同 | 版本化隔离安装 bootstrap | 14 项 host/preflight 与全量 non-live | `GATE-074` | Done |
| `WP-K-EFFECT-DIAG-06` | `DR-KEV-013～015` | candidate-05 有限诊断 | 指标/逐 case/Schema/history | 根因证据评审 | Done |
| `WP-K-EFFECT-OPT-06` | `DR-KFLOW-012`、`DR-KEV-017～019` | Summary V4、效果口径 v2 与组合根切换 | Knowledge 回归/E2E/mypy/history | `GATE-075` | Done |
| `WP-K-EFFECT-CANDIDATE-06-PREP` | 更新后的 `DR-KEV-015` | candidate-06 non-live assets | preparation/history/budget | `GATE-076` | Done |
| `WP-K-EFFECT-LIVE-06` | `UAT_01` 效果合同；`DR-KEV-020` | append-only authorization/consumed/journals/failure | 精确哈希、调用计数、失败码 | `GATE-077` 已消费 | Deferred |
| `WP-K-EFFECT-HARNESS-CLOSURE-07` | `DR-KEV-020` | bootstrap/runner/history tests | allowlist 一致、candidate-06 hash | candidate-07 prep | Done |
| `WP-K-EFFECT-CANDIDATE-07-PREP` | `DR-KEV-015/019/020` | 新候选 non-live assets | preparation/history/budget | `GATE-079` | Done |
| `WP-K-EFFECT-LIVE-07` | `UAT_01` 效果合同 | append-only authorization/failed_unconsumed | frozen binding、preflight、零调用 | `GATE-079` Closed（Failed/Unconsumed） | Deferred |
| `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | `DR-KEV-020～022` | launcher/preparation/history tests | 准备态/live preflight 分离、历史 hash | non-live 与代码评审 | Done |
| `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | 全部当前设计/UAT | 设计落实矩阵与目标内修复 | 文档/代码/配置/测试/evidence 交叉验证 | 独立评审与代码评审 | Done |
| `WP-SEVEN-ITEM-CLOSURE-06` | 本轮全部设计/UAT | review fixes/state sync | 全量 Python/Java/文档 | `GATE-078` | Done |
| `WP-K-UAT-TRACE-CLOSURE-09` | `UAT_00 v1.24`；`UAT_01 v1.12` | 当前 traceability schema/validator/tests | 35/35、37/37及三层效果状态绑定 | authority/evidence hash/回归/评审 | Done |
| `WP-K-REWRITE-SCHEMA-11` | `DR-KFLOW-004/012`；`UAT_01 v1.13` | `rewrite_v2.py`、生产组合根、验证台静态页 | V2 精确 decoder 合同、单绑定、页面安全投影 | Knowledge 定向回归、mypy/compileall、Spring 合同 | Done |
| `WP-EMP-NL-DESIGN-10` | `REQ-BQS-001/002/003/005/010`; `DR-MODEL-106/107`; `DR-BQCOM-109～111`; `DR-EMP-109～111` | 评审通过的跨层方案与计划DAG | 三轮内审和独立评审 | `GATE-080` | Done |
| `WP-BQ-MULTIVALUE-CONTRACT-10` | `DR-MODEL-106/107`; `DR-BQCOM-109～111` | typed slots、v3 config、region profile、v5/v6/v7 task | decoder/validator/binder/catalog/direct tests | `GATE-081` | Done |
| `WP-EMP-NL-QUERY-10` | `DR-EMP-109～111` | protected extractor、Employee search mapper、生产v7绑定 | unit/contract/fake server/Spring E2E/Java security | `GATE-081` | Done |
| `WP-EMP-NL-UAT-10` | `UAT_00` 第13节 | candidate-01～04 append-only UAT资产 | 15类组合覆盖、预算、零泄漏和历史测试 | `GATE-082` | Done |
| `WP-EMP-NL-CLOSURE-10` | 本轮全部DR/UAT | review fixes/state sync | full non-live、Maven、strict mypy、compileall、history/security | 正式代码评审与Git | Done |
| `WP-KCORPUS-AUDIT-01` | `REQ-KCORPUS-001/005`; `DR-KRET-013` | `IMPL-KRET-010` | `TEST-KRET-010/011` | `VAL-KRET-006` | Done |
| `WP-KCORPUS-DESIGN-01` | `REQ-KCORPUS-001～006`; `DR-KRET-013～026`; `DR-KEV-023～025` | REQ/L0/L1/L2/P3/UAT/ROADMAP | strict validators、三轮内审、独立评审 | `GATE-083` | Done |
| `WP-KCORPUS-PIPELINE-01` | `DR-KRET-013～021` | `IMPL-KRET-011～014` | `TEST-KRET-011～017` | `VAL-KRET-006` | Done |
| `WP-KCORPUS-INDEX-01` | `DR-KRET-022～024`; `DR-KEV-023～025` | `IMPL-KRET-014/016`; `IMPL-KEV-011` | `TEST-KRET-017/018`; `TEST-KEV-014～016` | `VAL-KRET-007`; `VAL-KEV-008` | Done |
| `WP-KCORPUS-UAT-01` | `UAT_01 v1.19` 阶段 A | current typed Provider + candidate binding | `TEST-KRET-020`; `UAT-KCORPUS-A-01～14` | `GATE-084` 证据输入 | Done |
| `WP-KCORPUS-RELEASE-01` | `DR-KRET-025` | `IMPL-KRET-015/016` | `TEST-KRET-019`; release smoke/rollback | `VAL-KRET-007`; `VAL-KEV-008` | Done |
| `WP-KRETRIEVAL-DIAG-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | §20 当前目标落点 | TEST-KFLOW-014、TEST-KRET-022、TEST-KEV-017；UAT_01 §14 | §20逐项证据 | Done |
| `WP-KRETRIEVAL-DESIGN-01` | REQ-KQUALITY-001～004；DR-KFLOW-024/025、DR-KRET-029/034、DR-KEV-029/030 | 原§20.36及原§20.55必要证据/评分表示增量 | TEST-KFLOW-016、TEST-KRET-024/029、TEST-KEV-020；原UAT_01 §14.21/14.31 | 原§20.36及原§20.55三轮内审及正式评审 | Done |
| `WP-KRETRIEVAL-IMPLEMENT-01` | REQ-KQUALITY-001～004；DR-KFLOW-024～027、DR-KRET-029/034/035、DR-KEV-029～034 | 原§20.72文号配置及Evidence默认代码接线；已有增量保持原范围 | TEST-KRET-030、TEST-KEV-024；原UAT_01 §14.46及既有追踪 | 代码接线完成，运行实例升级另列 | Done |
| `WP-KRETRIEVAL-NONLIVE-01` | REQ-KQUALITY-001～004；DR-KFLOW-024～027、DR-KRET-029/034/035、DR-KEV-029～034 | 原§20.72默认接线、当前根及历史防回退 | TEST-KRET-030、TEST-KEV-024、VAL-KEV-016；原UAT_01 §14.46 | 原§20.72.1实际回归通过，计数分列 | Done |
| `WP-KRETRIEVAL-UAT-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～029、DR-KRET-027/028/034/035/037、DR-KEV-026～034 | 原§20.88.1 KRB-017/019/021/023新批通过；run-02失败保持，不证明旧失败根因已消失 | 原UAT_01 §14.39～14.57 | 同生产版本9题有通过证据；人工usefulness未评估，跨域015为较早版本，不冒充当前10/10 | Deferred |
| `WP-KRETRIEVAL-QUALITY-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | §20 当前目标落点 | TEST-KFLOW-014、TEST-KRET-022、TEST-KEV-017；UAT_01 §14 | §20逐项证据 | Deferred |
| WP-KREBUILD-DESIGN-01 | 本轮12份授权文档、分类决策、方案及实施/验收边界 | 本轮12份授权文档、分类决策、方案及实施/验收边界 | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | Done |
| WP-KREBUILD-CONTRACT-01 | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | Ready |
| WP-KREBUILD-RETRIEVAL-01 | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | Blocked |
| WP-KREBUILD-EVIDENCE-01 | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | Blocked |
| WP-KREBUILD-COMPOSE-01 | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | current-root、Spring E2E、37功能重新逐case、Business35关键防退、Java安全/类型/non-live、正式代码评审；Blocker/Major0 | current-root、Spring E2E、37功能重新逐case、Business35关键防退、Java安全/类型/non-live、正式代码评审；Blocker/Major0 | Blocked |
| WP-KREBUILD-MEASURE-01 | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | 人工gold/语料就绪、新独立授权、版本绑定及预算预检；按预置判据分类，真实失败停止；未达标不写Passed | 人工gold/语料就绪、新独立授权、版本绑定及预算预检；按预置判据分类，真实失败停止；未达标不写Passed | Blocked |
| WP-KORG-DESIGN-01 | 本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | 本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | 三轮内审、两轮正式复核、文档验证通过；以包含本节的目标提交推送成功为Git收口证明 | 三轮内审、两轮正式复核、文档验证通过；以包含本节的目标提交推送成功为Git收口证明 | Done |
| WP-KORG-NORMALIZE-01 | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | TEST-KRET-301、hash/span反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | TEST-KRET-301、hash/span反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | Ready |
| WP-KORG-CHUNK-01 | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | TEST-KRET-302；条件/否定/表格/短块/长条款均可追溯；不静默遗漏 | TEST-KRET-302；条件/否定/表格/短块/长条款均可追溯；不静默遗漏 | Blocked |
| WP-KORG-REPRESENT-01 | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | TEST-KRET-303；明确实际长度单位/版本，无截断；旧未知不回填 | TEST-KRET-303；明确实际长度单位/版本，无截断；旧未知不回填 | Blocked |
| WP-KORG-COMPARE-01 | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | fake/类型→人工原文→另授权BGE及只读typed；逐阶段损失、保留题、安全与停止规则 | fake/类型→人工原文→另授权BGE及只读typed；逐阶段损失、保留题、安全与停止规则 | Blocked |
| WP-KORG-RELEASE-01 | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；无证据不得发布 | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；无证据不得发布 | Blocked |
| `WP-KCORPUS-ATTACHMENT-01` | `REQ-KCORPUS-001～006`、`DR-KRET-013～025`、`DR-KEV-023～025` | `IMPL-KRET-010～016` | `TEST-KRET-010～020`、`TEST-KEV-016` | candidate a5结构完整、源码可复现、可检索、可引用且可回滚 | Done |
| `WP-KGRAPH-CONTRACT-01` | 待新增 Knowledge Graph REQ/L1/L2 | 合同和 Schema 待形成 | fake、正反例、物理信息零暴露 | 独立设计评审通过 | Blocked |
| `WP-KGRAPH-BUILD-01` | 待批准图谱 DR | 待设计 | 来源、时效、hash、人工抽样 | 关系可追溯率 100% | Blocked |
| `WP-KHYBRID-RETRIEVAL-01` | 待批准联合检索 DR + `DR-KEV-*` | 待设计 | 联合 E2E、授权、引用、故障注入 | 图谱仅导航，原文最终取证 | Blocked |
| `WP-KNOWLEDGE-UAT-02` | 待批准 P3/UAT | 待准备 | 功能、安全、效果和历史 hash | 如实分类、Blocker/Major=0 | Blocked |

下表保留原需求到工作包的映射；原验收编号适用范围见当前UAT计划，新Knowledge合同另由§21/22追踪。

| 需求 | L0 决策 | 详细设计 | 工作包 | UAT |
|---|---|---|---|---|
| `REQ-BQS-001` | `SA-AD-001` | `DR-CORE-101/102` | `WP-BQ-RUNTIME-CUTOVER-02` | `UAT-BQ-CLOSURE-02` |
| `REQ-BQS-002` | `SA-AD-001` | `DR-BQCOM-101` | `WP-BQ-FILTER-CONTRACT-02` | `UAT-EMP-02`; `UAT-TXN-02` |
| `REQ-BQS-003` | `SA-AD-003` | `DR-BQCOM-102` | `WP-BQ-FIELD-CONFIG-02` | `UAT-BQ-CLOSURE-02` |
| `REQ-BQS-004` | `SA-AD-002` | `DR-EMP-101/103` | `WP-EMP-SEARCH-ADAPTER-02` | `UAT-EMP-201` |
| `REQ-BQS-005` | `SA-AD-003` | `DR-EMP-103` | `WP-EMP-SEARCH-ADAPTER-02` | `UAT-EMP-209` |
| `REQ-BQS-006` | `SA-AD-002` | `DR-EMP-102` | `WP-EMP-SEMANTIC-ADAPTER-02` | `UAT-EMP-208/210` |
| `REQ-BQS-007` | `SA-AD-002` | `DR-TXN-101/102` | `WP-TXN-SEARCH-EXT-02` | `UAT-TXN-203/204` |
| `REQ-BQS-008` | `SA-AD-003` | `DR-TXN-103` | `WP-TXN-SEARCH-EXT-02` | `UAT-TXN-205/206` |
| `REQ-BQS-009` | `SA-AD-002` | `DR-TXN-104` | `WP-TXN-SEARCH-EXT-02` | `UAT-TXN-208/209` |
| `REQ-BQS-010` | `SA-AD-004` | `DR-EMP-105`; `DR-TXN-105` | `WP-EMP-ES-AUTH-02` | `UAT-EMP-211/212`; `UAT-TXN-213` |
| `REQ-BQS-011` | `SA-AD-004` | `DR-BQCOM-103/104`; `DR-MODEL-103` | `WP-BQ-FIELD-CONFIG-02`; `WP-BQ-MODEL-CATALOG-02` | `UAT-EMP-215` |
| `REQ-BQS-012` | `SA-AD-005` | `DR-CORE-103`; `DR-BQCOM-106` | `WP-BQ-NONLIVE-E2E-02` | `UAT-BQ-CLOSURE-02` |
| `REQ-KFLOW-005/006` | `SA-AD-005`; `CR-AD-005` | `DR-KFLOW-011～013`; `DR-KRET-011/012` | `WP-K-RUNTIME-WIRING-03`; `WP-K-SPRING-NONLIVE-E2E-03` | `UAT-K-PUB/ISO` |
| `REQ-KFLOW-001～004`; `REQ-KRET-001～004`; `REQ-KEV-001～003` | `KQ-AD-001～010` | 三份 Knowledge L2 当前规则 | `WP-K-FUNCTIONAL-UAT-03` | `UAT-K-RW/DOM/RET/EV` |
| `REQ-KEV-004～006` | `KQ-AD-006/007/009` | `DR-KEV-010～015` | `WP-K-EFFECT-DIAG-03`; `WP-K-EFFECT-OPT-03`; `WP-K-EFFECT-CANDIDATE-05-PREP`; `WP-K-EFFECT-LIVE-05`; `WP-K-EFFECT-DIAG-06`; `WP-K-EFFECT-OPT-06`; `WP-K-EFFECT-CANDIDATE-06-PREP`; `WP-K-EFFECT-LIVE-06` | `UAT_01` 第 7 节 |
| `REQ-KCORPUS-001～006` | `SA-AD-006`; `KQ-AD-011` | `DR-KFLOW-015`; `DR-KRET-013～025`; `DR-KEV-023～025` | `WP-KCORPUS-AUDIT-01`～`WP-KCORPUS-RELEASE-01` | `UAT-KCORPUS-A-01～14` |

## 13. 当前评审与状态规则

工作包按直接依赖和真实证据判断。文档Reviewed/Approved、代码Done、部署生效与UAT通过分别管理。本轮内审、分层/跨层正式复核及实际验证集中于[本次整理记录](../历史文档/2026-09-14-unified-v3-baseline/MIGRATION.md)；旧评审、测试数字及完整过程原样归档，不冒充本轮执行。

正式Python全量入口仍为agent-runtime/scripts/run-nonlive-regression.ps1，隔离安装源码后执行历史host和non-live；本次纯文档仅运行安全定向兼容检查，不要求全量Python/Maven。任一对应case/合同/evidence失效才重新评估该验收，不因其他测试数量变化自动失效。

## 14. 当前结论

Business原35项及Employee扩展15类保留原证据范围；Knowledge原37功能项、阶段A14项、历史P5最近有效partially_effective均不外推为当前源码或新设计全套通过。两项无效效果运行及旧阶段B专项/质量包维持Deferred；已取消目标不恢复。后续在线12/8和资料方案只完成设计，实施与真实效果待验证。

## 15. 后续实施建议

本目标完成后停止。后续可独立授权WP-KREBUILD-CONTRACT-01或WP-KORG-NORMALIZE-01，先纯代码/契约，后组合/数据比较，最后单次有限测量或受控发布。图谱、记忆、多轮及公共DTO扩展不进入本基线主线。

## 16. 当前设计、实施与证据适用矩阵

本矩阵是整理时证据范围核实，不是新全仓代码评审。具体稳定需求/DR仍由各L2及§12追踪；历史逐要求审计原样归档。

| 设计范围 | 代码/配置事实 | 既有证据 | 状态及缺口 |
|---|---|---|---|
| REQ/L0、Core、Spring、Authority、Business L1/L2 | 统一Runtime、三动作、v7 QueryPlan/v3字段配置、权限与列表已存在 | UAT_00原35项及15类扩展；原Java/Python/Spring证据 | 既有范围Implemented and verified；部署/全量回归本轮未重验 |
| Model L2共享deepseek-flash/严格输出 | 当前源码配置事实；不改任务版本 | 各任务原冻结合同；旧模型结果不可等同新模型性能 | 模型变更影响所有任务，当前性能未重新测量 |
| Knowledge当前11/7/quality-v3 | 已实施旧链路，默认disabled | 原37功能及多轮局部证据；最近人工批次未通过且旧目标取消 | 不能称当前完整UAT Passed；效果Evidence missing/局部失败事实保留 |
| Knowledge原阶段A离线处理及安全来源 | 流水线与发布成果保留；当前别名不在本轮运行核实 | UAT_01阶段A14项原冻结范围 | Implemented and verified（仅原范围）；后续统计发现不推翻旧运行、也不证明全库元数据正确 |
| KQ-AD-020～024及FLOW/RET/KEV-201段 | 意图12/Summary8/minimal-v1待实施 | 新UAT-KM及原37风险新版本映射尚待执行 | Designed but not implemented；源码与设计差异见§21 |
| KQ-AD-025～028及FLOW/RET/KEV-301段 | 来源、时效、结构/表示新方案待实施 | 原30父范围只读审计，不是效果UAT；UAT-KORG待执行 | Designed but not implemented；收益Evidence missing，见§22 |
| P3/UAT/ROADMAP/ARCHITECTURE | 文档基线v3.0 | 本次文档/兼容检查 | 不对应新运行部署；图谱等Not applicable于本轮 |

## 17. 历史阶段索引

[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)第17节保存完整执行、失败、评审和有限证据引用。当前工作包终态见§5/7，验收结论见UAT_00/UAT_01；原“待执行/继续/授权”不构成当前许可。

## 18. 历史阶段索引

[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)第18节保存完整执行、失败、评审和有限证据引用。当前工作包终态见§5/7，验收结论见UAT_00/UAT_01；原“待执行/继续/授权”不构成当前许可。

## 19. 历史阶段索引

[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)第19节保存完整执行、失败、评审和有限证据引用。当前工作包终态见§5/7，验收结论见UAT_00/UAT_01；原“待执行/继续/授权”不构成当前许可。

## 20. 历史阶段索引

[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)第20节保存完整执行、失败、评审和有限证据引用。当前工作包终态见§5/7，验收结论见UAT_00/UAT_01；原“待执行/继续/授权”不构成当前许可。

## 21. Knowledge设计重建与有限实施交接

Ready 不等于实施授权。当前新目标只授权文档工作及其Git收口。

### 21.1 当前与目标

源码11/7/v3；后续12/8/minimal-v1。旧目标起止比较和证据事实见整理前§21.1，不能用测试通过替代效果。主要取舍为移除跨阶段模型证明声明、保留安全与基础组件；不默认整体回滚。

### 21.2 设计来源、合同与影响清单

| 需求/决策 | 首期设计权威 | 后续代码/配置/测试影响 | 不变边界 |
|---|---|---|---|
| REQ-KQ-201～205；KQ-AD-020/021 | L2_01_00 §8，DR-KFLOW-201～205 | 新intent12/internal类型；semantic_planner/planning/capability；当前任务目录与fake | selector/公共HTTP不改；模型不回显Q、不计划证明集合 |
| KQ-AD-022 | L2_01_01 §9，DR-KRET-201～204 | 原问同池、请求内embedding复用、minimal ranking；配置版本代码绑定；排序分阶段诊断 | typed接口、Profile物理映射、BGE重排512token窗口/embedding1024维、读取授权不改 |
| KQ-AD-023 | L2_01_02 §9，DR-KEV-201～205 | minimal Evidence、新内部schema3、Summary8及decoder；直接脱敏观测/测试 | 三层出域、identity/hash、ref/子串/唯一性及公开extractive DTO不改 |
| KQ-AD-024 | 三L2兼容/回滚、UAT_01 §15 | 同一root成对切换；旧测试迁移与历史隔离；后续traceability新版本 | Business35与Knowledge37旧证据不覆盖；旧task/source资产不静默删 |
| 模型/运行环境 | L2_00_02 §6.2；L1_00 | 复用固定后端，任务及快照变化；启动测试检查enabled/disabled | 不安装新生产依赖、不改全局环境、不自动部署 |
| 语料/向量 | L2_01_01 §9.3；StageA既有合同 | 首期仅记录只读绑定；新策略不写ES或切alias | corpus、parser、index/mapping、ACL和历史发布零修改 |

旧实验中无调用方的requirement/proof策略、继承Prompt补丁及临时Harness是否清理，由COMPOSE包逐项引用/冻结资产扫描决定；“退出主线”不授权现在删除。存在冻结引用时优先冻结源读取/测试隔离，不把旧实验默认挂入生产，不恢复第二在线流程。

### 21.3 后续工作包与直接依赖（新设计，不是本轮实施授权）

| 工作包 | 设计与范围/交付物 | 直接依赖 | 状态 | 验证与完成条件 | 回滚与资源 |
|---|---|---|---|---|---|
| WP-KREBUILD-DESIGN-01 | 本轮12份授权文档、分类决策、方案及实施/验收边界 | 无 | Done | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | 只文档diff，不回滚历史；无服务/模型 |
| WP-KREBUILD-CONTRACT-01 | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | WP-KREBUILD-DESIGN-01 | Ready | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | 后续代码授权；新增独立类型/task，暂不切root |
| WP-KREBUILD-RETRIEVAL-01 | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | WP-KREBUILD-CONTRACT-01 | Blocked | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | 本地fake；独立strategy，旧prod不变；无索引写入 |
| WP-KREBUILD-EVIDENCE-01 | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | WP-KREBUILD-CONTRACT-01 | Blocked | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | 与RETRIEVAL可并行；旧Prompt/serializer不改 |
| WP-KREBUILD-COMPOSE-01 | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | WP-KREBUILD-RETRIEVAL-01、WP-KREBUILD-EVIDENCE-01 | Blocked | current-root、Spring E2E、37功能重新逐case、Business35关键防退、Java安全/类型/non-live、正式代码评审；Blocker/Major0 | 后续代码/测试权限；不用live作基础代码包完成前置；禁用Knowledge或整套恢复相容发布 |
| WP-KREBUILD-MEASURE-01 | UAT_01 §15：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | WP-KREBUILD-COMPOSE-01 | Blocked | 人工gold/语料就绪、新独立授权、版本绑定及预算预检；按预置判据分类，真实失败停止；未达标不写Passed | 需只读服务/模型与真人评价授权；无自动候选循环，不回滚索引；结果append-only |

依赖边精确为DESIGN→CONTRACT，CONTRACT→RETRIEVAL/EVIDENCE，二者→COMPOSE，COMPOSE→MEASURE。没有MEASURE→基础代码的反向边，没有旧UAT或图谱前置。设计完成后仅CONTRACT具备技术Ready，仍不等于获准代码实施；其他包随直接依赖完成才就绪。不单设新Gate或另建“总收口候选”：COMPOSE完成实现交付，MEASURE形成自己的有限测量结论；质量未达标须报告但不重启取消目标。

每包提交前完成相关测试/类型及代码对照检查，仅目标文件；依赖失败先定位实现/测试/设计/环境，不放宽安全。若提出新公共DTO、作用域/角色/数据/索引变化，阻塞相关包并另作决策，不通过下位文档越权。

### 21.4 验收、变量和回滚边界

UAT_01 §15独占新方法和case类别；功能、安全、召回、回答四维分列。新任务是整体简化基线，不能用与旧模型/旧索引不同的结果声称某一个策略产生因果提升。后续实验一次只改变改写、向量表示或一个评分参数；查询/语料不足与排序损失分开归类。新变量实验不属于首期实施必需，不为每个失败追加门禁/候选。

四条回滚基线分别是代码提交（含任务类型）、模型后端/版本、配置及索引/策略快照、实际部署实例。首期只改代码绑定与相关配置，在相同索引上验证；真实进程不由本轮操作。清理前验证目标发布整体可恢复，不能单换Summary或伪造requirements给旧validator。原a5来源保留不意味着当前alias应恢复a5；向量表示优劣尚未有同条件受控结论，默认保持现状。

### 21.5 设计与验证状态

原设计已评审，六包状态见§5；本轮仅整合文档，当前正式复核见§13。代码、任务与运行证据未修改；新的效果验收未执行。

## 22. 资料组织与检索表示设计审计

### 22.1 审计来源与证明范围

整理前§22.1的只读审计完整保留于[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)。来源HF数据卡/官方抽查、30父范围样本及有限索引统计只证明2026-09-14该次读取，不是本轮再次查询或全库时效认证。发现日期同值、附件短块、旧跨度及hash/表示来源不清、分类存储与消费分离；新合同见L2_01_01资料组织章节。本轮不补造字段、不重建索引、不宣称收益。

### 22.2 有限统计与样本

整理前§22.2的只读审计完整保留于[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)。来源HF数据卡/官方抽查、30父范围样本及有限索引统计只证明2026-09-14该次读取，不是本轮再次查询或全库时效认证。发现日期同值、附件短块、旧跨度及hash/表示来源不清、分类存储与消费分离；新合同见L2_01_01资料组织章节。本轮不补造字段、不重建索引、不宣称收益。

### 22.3 字段映射

整理前§22.3的只读审计完整保留于[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)。来源HF数据卡/官方抽查、30父范围样本及有限索引统计只证明2026-09-14该次读取，不是本轮再次查询或全库时效认证。发现日期同值、附件短块、旧跨度及hash/表示来源不清、分类存储与消费分离；新合同见L2_01_01资料组织章节。本轮不补造字段、不重建索引、不宣称收益。

### 22.4 主要发现与决策

整理前§22.4的只读审计完整保留于[原包完整记录](历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)。来源HF数据卡/官方抽查、30父范围样本及有限索引统计只证明2026-09-14该次读取，不是本轮再次查询或全库时效认证。发现日期同值、附件短块、旧跨度及hash/表示来源不清、分类存储与消费分离；新合同见L2_01_01资料组织章节。本轮不补造字段、不重建索引、不宣称收益。

### 22.5 后续工作包、直接依赖与授权

以下代码/数据步骤均未实施、未获本轮执行授权。Ready仅表示设计输入具备；无付费预算继承，也不以图谱或旧专项完成为前置。新资料包与§21在线重建可独立推进；对照阶段选择一套冻结在线实现，不要求先完成§21真实测量。

| 工作包 | 设计/落点与交付物 | 直接依赖 | 状态 | 验证及完成条件 | 迁移/回滚、资源与后续权限 |
|---|---|---|---|---|---|
| WP-KORG-DESIGN-01 | 本节审计；L1_01 §4.6、三L2新节、UAT_01 §16/ROADMAP_01 §15 | 无 | Done | 三轮内审、两轮正式复核、文档验证通过；以包含本节的目标提交推送成功为Git收口证明 | 只文档；不动服务/模型/索引 |
| WP-KORG-NORMALIZE-01 | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | WP-KORG-DESIGN-01 | Ready | TEST-KRET-301、hash/span反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | 仅技术Ready，需代码/测试及有限资产读取新授权；sidecar追加，不迁现索引 |
| WP-KORG-CHUNK-01 | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | WP-KORG-NORMALIZE-01 | Blocked | TEST-KRET-302；条件/否定/表格/短块/长条款均可追溯；不静默遗漏 | 需代码/测试；新版本并存，旧chunker不覆盖；不依赖BGE或线上UAT |
| WP-KORG-REPRESENT-01 | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | WP-KORG-NORMALIZE-01 | Blocked | TEST-KRET-303；明确实际长度单位/版本，无截断；旧未知不回填 | 需代码/配置/本地固定tokenizer资源权限；无推理的纯构造可先完成，与CHUNK并行 |
| WP-KORG-COMPARE-01 | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | Blocked | fake/类型→人工原文→另授权BGE及只读typed；逐阶段损失、保留题、安全与停止规则 | 需独立索引候选/BGE/只读服务/必要模型预算授权；同源切片与表示分轮；不切线上alias |
| WP-KORG-RELEASE-01 | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | WP-KORG-COMPARE-01 | Blocked | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；无证据不得发布 | 需新索引/受控部署/alias写授权；精确旧绑定与原子回滚；不删旧索引 |

直接边：DESIGN→NORMALIZE，NORMALIZE→CHUNK/REPRESENT，CHUNK/REPRESENT→COMPARE，COMPARE→RELEASE。6包6边，无反向边；新工作包规则由三L2定义，P3不自创设计DR。可选公共时效/分类DTO和额外父读取未列入关键链：若后续要实现，另作受影响公共契约设计与授权，当前包不能偷偷实现。

没有新增重复Gate。设计评审是纯实现入口，COMPARE结果和既有发布安全条件仅控制RELEASE；不是要求先真实测量才能完成NORMALIZE/CHUNK/REPRESENT。任一候选质量失败只保留有限结论、停止该实验，不自动新candidate。代码/模型/配置/索引四类回滚独立记录，禁止单纯git回退冒称数据已恢复。

### 22.6 设计与验证状态

原资料设计已评审；六包状态见§5。本轮正式复核见§13，不把原审计或文档验证冒充实施、推理或UAT。
