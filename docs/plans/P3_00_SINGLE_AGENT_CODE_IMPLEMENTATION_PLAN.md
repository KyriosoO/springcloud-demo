# [P3_00] 单体 Agent 查询能力实施与收口计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | P3_00 |
| 当前版本 | v2.62 |
| 文档状态 | Reviewed |
| 更新时间 | 2026-09-09 |
| 适用范围 | 已完成且不得回退的 Business/Knowledge 功能基线，以及效果测量终态、文档权威纠偏、全量设计落实审计和最终收口 |
| 实施授权 | Ready 不等于实施授权；本任务已另行获得目标范围内代码实施、受控验证、文档同步及 Git 提交推送授权 |
| 归档来源 | [v1.34 已评审旧版](历史文档/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN_v1.34.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

v2.59依据用户补充，将整体检索质量与资料缺口、摘要质量分层验收，执行§20.62的有限计分和拒绝诊断修复；当前真实终态仍为§20.61的run-12失败，不创建新付费批次，不改判历史。§20.56.2及更早记录保留各自时点。

v2.60推进§20.63代表集与本地检索基线，保持真实专项及最终QUALITY未完成；不增加付费批次、Gate或上位架构变更。

v2.61依据L2_01_00 v1.28推进§20.64文号边界误拒修复；不修改历史Guard、基线/gold、模型任务或索引，整体检索对照和真实UAT继续独立治理。

v2.62依据L2_01_01 v2.16推进§20.66服务内文号元数据匹配；先完成设计评审，再实施默认关闭切片，不修改旧基线、索引或付费运行边界。

v2.34 在不修改 Rewrite V1 或历史候选的前提下新增 Knowledge Rewrite V2 精确 JSON 输出合同。v2.35 依据 ROADMAP_01 阶段 A 新增语料只读审计、版本化处理、候选索引、发布回滚和专项 UAT 工作包，并把入口门禁与 alias 发布门禁拆开以消除循环。v2.36 依据审计 v1 的实际失败修复来源可达性、正文完整性、人工优先级和精确预算边界。v2.37～v2.38 如实保留早期 candidate/UAT 及严格合同复评。v2.39 修复 legacy DOC 扁平解析导致条款关系缺失的问题并保留结构化 a4 中间候选。v2.40 将网络/损坏容器异常收敛为逐资产有限失败，以最终工具源码重建 Stage A corpus candidate-08/a5，并用 UAT/release attempt-05 完成发布收口；v2.41 修正 catalog Git/LF 分发哈希，增加历史评估输入的精确只读镜像，并让历史测试辅助层在临时仓库内复原已授权换行字节，使正式隔离回归可由干净检出复现。阶段 B 仍独立阻塞。

v2.43 聚焦修订阶段B实施中验证出的请求内rerank并发、长附件Evidence配额和分域主题词语义；根因和逐轮复评见§20.4。已通过基线仍有效，受影响增量在复评通过前暂停，不新增付费候选。

v2.47记录用户对独立V5验证批次的明确授权，范围仅§20.18的run-04；保持原10例/gold、历史资产和累计预算，不授权失败后的下一批。V5设计与non-live实现已经完成，真实UAT及最终评审仍单独判断。

v2.49记录用户再次授权后的质量策略V2设计与实施；§20.23为本次增量权威。v2.48的V6切片和四批真实终态保持原证据范围；旧批次不续跑，新执行必须另行冻结且计入原总预算。

v2.50依据用户明确批准，将累计E2E上限调整为21、模型仍60；§20.33及UAT_01 §14.18治理一次独立七例验证与三项历史证据的受限复用，不改历史失败或生产设计。

v2.51依据继续目标授权，为§20.34三项已定位缺口修订必要证据合同并重算原工作包；不新增门禁、工作包或付费授权，旧已消费运行不变。设计与实现状态分开，以§20.36为本增量依据。

v2.53聚焦B-R8-SEM已核实的Prompt继承遗漏，依据L2_01_00 §8.6恢复澄清优先规则；只实施和验证non-live，不新增运行、预算、工作包或门禁。

## 2. 目标、范围与计划原则

唯一目标链路为输入安全闸门/request-local slots → LLM filters QueryPlan → 两级 decoder → code/config validator 与 `value_ref` binder → 一个 ActionCandidate → 固定 Employee/Transaction Adapter → 服务最终授权与 ES/向量/SQL → 安全列表。输入闸门不得选择 domain/action 或生成 filters。目标动作只包括 `employee.search`、`employee.semantic_search`、`transaction.search`；员工地址固定 `contact_address → contactAddress`，`workBaseSi/workBaseAf` 不得启用。

原则：先公共合同与配置，再并行实现模型/Employee/Transaction；Employee 角色收紧与非 live 合同可同步准备；组合根切换等待全部 action 和 Employee guard；先 fake E2E 再受控 live，最后正式 UAT。禁止配置平台、复杂审批/证据流程、业务接口新增、数据库修改、真实调用未授权和历史证据复用。

## 3. 来源清单与当前基线

| 来源 | 当前版本 | 权威责任 | 状态 |
|---|---|---|---|
| [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v2.4 | 稳定业务目标、安全、受控多值及 Knowledge 阶段 A 语料完整性 | Approved |
| [`L0_00`](../design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v2.8 | 系统边界和下位治理 | Approved |
| [`L1_00`](../design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v3.5 | Runtime/Model/Core、受控 Business 候选准入、组合根及完整意图边界 | Approved |
| [`L1_02`](../design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v2.8 | Business 多值/组合边界、Adapter、结果卫生与最终授权 | Approved |
| [`L2_00_00`](../design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v1.3 | Spring 公共接入、Runtime 内部协议和当前生产启动入口状态 | Approved |
| [`L2_00_01`](../design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v2.3 | planning bridge、组合根和单动作 | Approved |
| [`L2_00_02`](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v2.7 | v7 显式字段完整性、裸 slot 多值/组合 Prompt 与 unsupported | Approved |
| [`L2_00_03`](../design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v1.3 | 用户角色 Authority 的 Servlet/Reactive 统一转换及 Provider 消费 | Approved |
| [`L2_02_00`](../design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v2.8 | filters、v3配置、多值binder、组合/region与结果出域 | Approved |
| [`L2_02_01`](../design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.8 | Employee search多值映射/semantic、记录卫生与最终读取授权 | Approved |
| [`L2_02_02`](../design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.6 | Transaction Date/Decimal/page/sort 与跨语言合同 | Approved |
| [`L1_01`](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v1.21 | KQ-AD-018必要证据及019派生向量；在线/离线边界不变 | Approved；向量发布已完成，阶段B质量/UAT未完成，见§20.52～20.53 |
| [`L2_01_00`](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v1.28 | DR-KFLOW-024～027需求计划、澄清、当前摘要配对及文号边界 | Approved；已实施，文号增量non-live验证见§20.64.1 |
| [`L2_01_01`](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v2.16 | 需求排序、上下文评分及文号元数据匹配 | Approved；DR-KRET-035已实施并non-live验证，不放行配置启用 |
| [`L2_01_02`](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v1.24 | DR-KEV-029～033需求预算、覆盖、有限拒绝与检索分层计分 | Approved；§20.62增量单独验证，真实专项未通过 |
| [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | v1.24 | Business 35/35固定用例与15项Employee自然语言扩展 | Reviewed |
| [`UAT_01`](UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | v1.38 | 原十例历史及整体检索质量验收边界 | Reviewed；§14.43文号检索验证责任已审，不改判旧失败 |
| [`ROADMAP_01`](ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md) | v0.9 | 语料、检索质量与图谱后续路线；阶段 A 已完成 | Reviewed |

Verified existing：Business filters plan、统一字段 JSON、v4 model catalog/完整意图 Prompt、Employee search/semantic Adapter、Employee Controller 最终读取守卫与 endpoint-scoped 共享 JWT role converter、真实 Servlet 过滤链角色/兼容矩阵、Transaction Date/Decimal/完整分页 Adapter、三动作生产组合根、旧目标入口退役核实、三动作 fake E2E、现有三个业务接口、隔离 Employee→es-query-service 只读联通、semantic 独立 10000ms action budget，以及现有向量 partial page/历史无姓名记录的 bounded codec/normalizer 合同。Employee 零模型生产 codec 返回 9/20 安全记录；Transaction production Spring UTC 零毫秒字符串/standalone epoch 严格双形态和零模型 20/104 生产 codec 均通过。配置 SHA-256=`47077b3783e6fc7179c22a53aab37f714b2c1d278ad96d925a614b6406f173ba`，v3 历史 manifest SHA-256=`3da2d9f250253b142e43f690d5dc4e7ff8cf9bfe57f2e52ff6d248ec2c8d75d2`，v4 当前 manifest SHA-256=`58b04d469dc7ed584e6689b12bae2cb8f0b5922d6f2893af8eceeede4068ea3c`。controlled-run06 六项真实模型场景通过，有限结果 SHA-256=`d80167215796c53c05b2f9443eaa5c96c0e82215b46d8d5df2f5e888b2f37ef6`；正式 run03 UAT 18/18 通过，SHA-256=`b49832426147dc14d56e571fea11b0345e16602d8cb5e2ea2eeb3dacb3326dd8`。前五次 controlled 失败 SHA-256 分别为 `fdc37b16e45d58733ede0a468e90b4db5242de8c84bcda7cca18ef07bd368607`、`121814993c53c2f0b4910bb5efe8b35bfe3da65dc395bd3270aa1c57b6eb5a08`、`737d76c296d7803618f74c370a4478b73e2a65a3bbec66ffee3d2d577b4a467d`、`3582693a77b4b791eabdc7253778936ac76ae7a779c09fad1edb3057bc7c14de`、`e028ae64eb97ca56b4e1ff09ac04423317536d20fdd9d1792e652cc9acfe2c4e`；所有历史结果及原 manifest 均保持不可变。

首次正式 UAT 暴露现有 Transaction 类型样本含 `_`，公共 validator 误将 `eq` 套用 contains 限制；失败 SHA-256=`cc2905dab7a4d78fd52f7fd8c973b2c41fbaa77db47a0bc6036f45119f34c0c3` 保持不可变。`WP-TXN-TEXT-POLICY-COMPAT-03` 现已完成：`eq` 使用 safe token，`contains` 拒绝 `_/%/反斜杠`；UAT 只选择实际类型中的安全 contains 片段。95 项定向测试、1438 项全量 non-live 测试和 111 个生产模块 strict mypy 全部通过，未修改 Mapper、SQL、JSON 配置结构或 Employee 规则。

第二次正式 UAT 在 `UAT-EMP-210` 失败：v3 模型丢弃“限定上海”条件并执行一次 `employee.semantic_search`；失败 SHA-256=`1b4c5eb334a42f699afb05d68210b0585cb6940401bec082a0ea2946a89a2c8f`，模型调用 7 次、semantic 2 次、retry/resume 为 0。`WP-BQ-MODEL-INTENT-COMPLETENESS-03` 已完成：v4 Prompt 对 semantic+结构过滤、无批准时钟相对日期固定 exact unsupported 示例；独立 v3 manifest SHA-256=`58b04d469dc7ed584e6689b12bae2cb8f0b5922d6f2893af8eceeede4068ea3c`。正式 run03 UAT 18/18 通过，结果 SHA-256=`b49832426147dc14d56e571fea11b0345e16602d8cb5e2ea2eeb3dacb3326dd8`：18 次真实 QueryPlan、Employee search 6 次/semantic 1 次、Transaction search 7 次，其余 endpoint/answer/Knowledge/retry/resume 均为 0；未配置字段、语义+地点、相对日期与聚合均零业务调用。

## 4. 分批与执行边界

批次 A：公共 filters 合同与 Employee 授权兼容性调查；批次 B：统一配置；批次 C：模型 catalog、两个 Employee Adapter、Transaction 扩展；批次 D：组合根、detail 退役核实、non-live E2E；批次 E：受控真实联调；批次 F：正式 UAT。

真实模型、业务服务、数据库和敏感用户数据只在后置独立授权后使用；Open live/UAT 门禁不阻塞独立 non-live 工作包。

## 5. 工作包清单

| 工作包 ID | 名称 | 来源设计 | 范围 | 直接依赖 | 入口门禁 | 交付物 | 验证 | 回滚边界 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| `WP-BQ-FILTER-CONTRACT-02` | 公共 filters QueryPlan 合同 | `L2_02_00 DR-BQCOM-101/103` | exact filters/operator/tagged value、validator/binder、组合规则 | - | - | 公共计划类型与 fake 测试 | `VAL-BQCOM-101` | 撤销新合同，不恢复旧 Business 旁路 | Done |
| `WP-BQ-FIELD-CONFIG-02` | 统一字段级 JSON 配置 | `L2_02_00 DR-BQCOM-102/104` | 三动作 JSON、keyword 受控策略、subset、snapshot、分类与脱敏 | `WP-BQ-FILTER-CONTRACT-02` | - | 版本化配置与 strict loader | `VAL-BQCOM-101/102` | 关闭新配置，不扩大旧动作 | Done |
| `WP-BQ-MODEL-CATALOG-02` | filters 模型目录与 Prompt | `L2_00_02 DR-MODEL-101～105` | v3 task、安全目录、protected slots、unsupported | `WP-BQ-FIELD-CONFIG-02` | - | fake model task/catalog 测试 | `VAL-MODEL-101/102` | 移除 v3 装配，不复用旧 live 证据 | Done |
| `WP-EMP-SEARCH-ADAPTER-02` | Employee 条件搜索 | `L2_02_01 DR-EMP-101/103/104` | filters→SearchRequest、分页、排序、bounded hits | `WP-BQ-FIELD-CONFIG-02` | - | search definition/codec/projection | `VAL-EMP-101/103` | 禁用新 action，保留历史资产 | Done |
| `WP-EMP-SEMANTIC-ADAPTER-02` | Employee 语义搜索 | `L2_02_01 DR-EMP-102/104` | queryText/k/profile、单接口语义列表 | `WP-BQ-FIELD-CONFIG-02` | - | semantic definition/codec 与 fake tests | `VAL-EMP-101/103` | 禁用新 action，不建立普通搜索 fallback | Done |
| `WP-EMP-ES-AUTH-02` | Employee ES 最终读取授权 | `L2_02_01 DR-EMP-105`; `L2_00_03 DR-AUTH-007` | 两入口 requireEmployeeRead、endpoint-scoped 共享 converter、真实安全链角色矩阵及 detail/fallback 兼容 | - | - | Java guard/controller/完整 SecurityFilterChain 测试 | `VAL-EMP-102` | 仅撤销 ES 专用链，不修改其他 endpoint 安全行为 | Done |
| `WP-TXN-SEARCH-EXT-02` | Transaction Date/金额/分页扩展 | `L2_02_02 DR-TXN-101～105` | 四字段 operator、Date/Decimal、page/sort 和 standalone epoch 合同 | `WP-BQ-FIELD-CONFIG-02` | - | 扩展 Transaction Adapter 和 Java contract tests | `VAL-TXN-101/102/103` | 关闭新字段，不修改 Java DTO/SQL | Done |
| `WP-TXN-DATE-WIRE-COMPAT-03` | Transaction 生产 Date 响应兼容 | `L2_02_02 DR-TXN-102/105` | 真实 Spring UTC 零毫秒字符串与 standalone epoch 严格归一，其他形态拒绝 | `WP-TXN-SEARCH-EXT-02` | - | Python response codec、真实 Spring JSON contract 和零模型验证 | `TEST-TXN-102`; `VAL-TXN-101/102/103` | 撤销新增字符串分支，保持服务和 DTO 不变 | Done |
| `WP-BQ-RUNTIME-CUTOVER-02` | 三动作生产组合根切换 | `L2_00_01 DR-CORE-101～104` | model/catalog/snapshot/三 action/Registry 单一路径；仅证明本地对象图，不代表 Employee 真实授权生效 | `WP-BQ-MODEL-CATALOG-02`, `WP-EMP-SEARCH-ADAPTER-02`, `WP-EMP-SEMANTIC-ADAPTER-02`, `WP-TXN-SEARCH-EXT-02` | - | 组合根和 Core fake 契约 | `VAL-CORE-101/102` | 关闭新组合根，不恢复 Resolver | Done |
| `WP-EMP-DETAIL-RETIRE-02` | Employee detail 退役核实 | `L2_02_01 DR-EMP-106` | 调用方/兼容/历史证据核查，目标生产路径移除 | `WP-BQ-RUNTIME-CUTOVER-02` | - | 调用方清单和可达性/历史回归 | `TEST-EMP-107` | 保留冻结历史与仍有调用方的共享类型 | Done |
| `WP-BQ-NONLIVE-E2E-02` | 三动作 non-live E2E | `L2_00_01`; `L2_02_00`; `L2_02_01`; `L2_02_02` | fake model/三个 fake endpoint/失败零调用 | `WP-BQ-RUNTIME-CUTOVER-02` | - | non-live E2E 及跨域/Knowledge 回归 | 三动作、权限 fake、contract、mypy | 移除测试装配，不改历史 evidence | Done |
| `WP-BQ-CONTROLLED-LIVE-02` | 受控模型与业务联调 | `REQ_00`; `L2_00_02`; 两域 L2 | 有限固定场景、敏感值内存化、五次失败历史不可变 | `WP-BQ-NONLIVE-E2E-02`, `WP-EMP-DETAIL-RETIRE-02`, `WP-EMP-ES-AUTH-02`, `WP-TXN-DATE-WIRE-COMPAT-03` | `GATE-070` | controlled-run06 真实三动作通过，不覆盖既有失败证据 | 一计划/一业务调用与真实权限矩阵 | 失败即停止，先修复根因，不复用失败结果路径 | Done |
| `WP-TXN-TEXT-POLICY-COMPAT-03` | Transaction 按 operator 区分文本安全策略 | `L2_02_00 DR-BQCOM-101`; `L2_02_02 DR-TXN-101` | `eq` 允许合法 `_`，`contains` 继续拒绝 `_/%/反斜杠`，UAT 选择安全 contains 片段并冻结失败历史 | `WP-BQ-FILTER-CONTRACT-02`, `WP-TXN-SEARCH-EXT-02` | - | code-bound 文本策略、validator/Adapter 双向 tests、独立 UAT 结果路径 | `TEST-BQCOM-102`; `TEST-TXN-101` | 不修改业务 SQL/DTO，不放宽 contains 或覆盖历史结果 | Done |
| `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | Model 完整意图与不可表达组合收紧 | `L2_00_02 DR-MODEL-101/104`; `L2_02_01 DR-EMP-102` | v4 Prompt、semantic+地点及无批准时钟相对日期 exact unsupported；保留 v2/v3 manifest 和两次 UAT 失败历史 | `WP-BQ-MODEL-CATALOG-02`, `WP-EMP-SEMANTIC-ADAPTER-02` | - | 新 task version、直接 model/adversarial fake 测试、新 v3 manifest 与独立 run03 路径 | `TEST-MODEL-102/104`; `VAL-MODEL-101/102` | 不引入本地 Resolver、额外门禁、生产 DTO 或历史改写 | Done |
| `WP-BQ-UAT-HANDOFF-02` | 正式 UAT 环境与交接 | [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | UAT 前置、真实数据可用性、固定用例与结论 | `WP-BQ-CONTROLLED-LIVE-02`, `WP-TXN-TEXT-POLICY-COMPAT-03`, `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | `GATE-UAT-007` | 18 项真实结果及其不可变边界 | 当前真实模型/业务场景 | 不把旧 evidence 或未执行场景冒充真实执行 | Done |
| `WP-BQ-COMPLETION-CLOSURE-04` | 当前 35 用例证据与实现收口 | [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) v1.24；当前代码 | Spring 严格 JSON、Spring→Runtime 当前链路、workBase/detail 历史隔离、Transaction preflight 环境、35 用例逐项追踪、全量回归与正式代码评审 | `WP-BQ-UAT-HANDOFF-02` | - | `uat_traceability.v2.json`、当前测试结果、代码评审和 Git 提交 | 当前 Spring/Runtime/Employee/Transaction 测试与全量 non-live 回归 | 保持 18 项真实证据集合不变；17 项仅按风险使用等价自动化 | Done |
| `WP-K-BASELINE-03` | Knowledge 设计与 UAT 基线 | `L1_00/L1_01`、三份 Knowledge L2、`UAT_01` | 当前事实核实、生产接线/功能效果分离、三轮内审及独立评审 | - | - | Approved/Reviewed 文档和无环 DAG | strict validators、分层/跨层评审 | 仅回退本次文档语义，不改历史证据 | Done |
| `WP-K-RUNTIME-WIRING-03` | Knowledge 默认关闭生产接线 | `L2_01_00 DR-KFLOW-011～014`、`L2_01_01 DR-KRET-011/012` | 启动开关、stub/fake 边界、任务/Provider/typed retrieval、同 Registry、owned clients 和关闭 | `WP-K-BASELINE-03` | `GATE-071` | 生产组合根、配置和生命周期测试 | `VAL-KFLOW-005`; `VAL-KRET-005` | 关闭开关即恢复 Business-only 对象图 | Done |
| `WP-K-SPRING-NONLIVE-E2E-03` | Spring→Runtime Knowledge non-live E2E | 三份 Knowledge L2、`UAT_01` | 当前生产对象图、fake Model/typed Provider、权限/失败/零调用/关闭矩阵 | `WP-K-RUNTIME-WIRING-03` | - | Spring/Python 16 场景 E2E 与有限调用计数 | `UAT-K-*` 功能矩阵 | 删除测试装配，不改生产合同 | Done |
| `WP-K-FUNCTIONAL-UAT-03` | Knowledge 功能 UAT | `UAT_01` 第 5～6 节 | 37 case 追踪、Java/Python/当前对象图证据和功能结论 | `WP-K-SPRING-NONLIVE-E2E-03` | `GATE-UAT-008` | `knowledge_uat_traceability.v2.json` 和执行结果 | 37/37 有实际/等价证据 | 保持 Effectiveness 独立 | Done |
| `WP-K-EFFECT-DIAG-03` | candidate-04 只读效果诊断 | `L2_01_02 DR-KEV-013/014` | Q1/Q3/Q4 指标、逐 case 分布、根因与证据强度 | `WP-K-FUNCTIONAL-UAT-03` | - | `candidate_04_effect_diagnosis.v1.json` 与可复现测试 | 三项历史 SHA、指标/分布/域差异重算 | 不修改 candidate-04 | Done |
| `WP-K-EFFECT-OPT-03` | 最小效果改进 | `L2_01_02 DR-KEV-014/016`；`L2_01_00 DR-KFLOW-006/012` | 实施域目录 v2 与 Summary v3；不调整 RRF/rerank、validator、dataset/gold | `WP-K-EFFECT-DIAG-03` | - | 新版本代码/配置与 fake 反证 | 安全 Gate、Knowledge 回归、strict mypy | 新旧版本并存，可禁用新版本 | Done |
| `WP-K-EFFECT-CANDIDATE-05-PREP` | 新效果候选非 live 准备 | `L2_01_02 DR-KEV-015` | 新 run/manifest/hash/reference/预算/快照/历史 hash 和失败关闭 | `WP-K-EFFECT-OPT-03` | - | candidate-05 preparation 资产与正式授权模板 | fake budget、首 outbound、retry/resume=0 | 不执行真实 outbound | Done |
| `WP-K-EFFECT-LIVE-05` | 新效果 UAT | `UAT_01` 第 7 节 | 精确授权后执行冻结 candidate-05 并如实计算结论 | `WP-K-EFFECT-CANDIDATE-05-PREP` | `GATE-072` | append-only live result/evidence | Schema、预算、安全 Gate、人工 rubric | 失败即停止，不补跑或改判 | Done |
| `WP-K-CLOSURE-03` | Knowledge 正式代码评审与状态收口 | `L1_00/L1_01`、三份 Knowledge L2、`P3_00/UAT_01` | 全量验证、代码评审修复、文档状态、Git 提交推送 | `WP-K-EFFECT-LIVE-05` | - | review 结论、测试清单、commit/push | Blocker/Major=0、工作树明确 | 保持历史结果不可变 | Done |
| `WP-DOC-CONSISTENCY-06` | 七项文档事实与依赖纠偏 | L0/L1/L2、P3、UAT、`ARCHITECTURE.md` | 当前/历史效果分离、Summary v3、生产入口、版本/状态/证据计数同步 | `WP-K-CLOSURE-03` | - | 原子文档 diff、三轮内审、独立跨层评审 | strict validators、链接/版本/DAG 检查 | 仅回退本次文档修订 | Done |
| `WP-PY-REGRESSION-REPRO-06` | Python 正式全量入口可复现 | 当前 pyproject、Transaction 冻结 host/preflight | 临时隔离环境显式安装当前源码，稳定运行冻结 host 与全量 non-live | `WP-DOC-CONSISTENCY-06` | - | 版本化 bootstrap、命令和执行结果 | 两项失败消失、14 项 host/preflight、全量回归、历史 hash | 不改冻结资产或生产依赖 | Done |
| `WP-K-EFFECT-DIAG-06` | candidate-05 只读效果根因复核 | `L2_01_02`、candidate-05 append-only result | 重算 Q1～Q4、逐 case 失败分布、根因证据与最小接缝 | `WP-PY-REGRESSION-REPRO-06` | - | `candidate_05_effect_diagnosis.v1.json` 与重算测试 | 三项历史 hash、分母、逐 case coverage、敏感字段禁止 | 不修改历史、gold、阈值或正文 | Done |
| `WP-K-EFFECT-OPT-06` | Knowledge 最小效果优化 | `L1_01 v1.8`、`L2_01_00/02 v1.9`、`UAT_01 v1.8` | 实施 Summary V4 与效果口径 v2；不调整 retrieval/validator/dataset/gold/权限 | `WP-K-EFFECT-DIAG-06` | - | 新任务、evaluator 语义、组合根和测试 | Knowledge 全回归、E2E、strict mypy、历史 hash | 禁止放宽阈值/安全；V1～V3 不修改 | Done |
| `WP-K-EFFECT-CANDIDATE-06-PREP` | 新效果候选非 live 冻结 | 新优化版本与 candidate-04/05 历史 | 新 run/manifest/hash/reference/预算/快照/失败关闭 | `WP-K-EFFECT-OPT-06` | - | candidate-06 准备资产和一次性授权模板 | fake budget、首 outbound、retry/resume=0、历史 hash | 不读取密钥或产生 outbound | Done |
| `WP-K-EFFECT-LIVE-06` | candidate-06 效果 UAT | `UAT_01` 效果验收合同 | 唯一授权已消费；52 变体和 44 paid 完成后因 Harness 最终快照误判失败 | `WP-K-EFFECT-CANDIDATE-06-PREP` | `GATE-077` | append-only authorization/consumed/journals/failure | 精确哈希、调用计数、失败码和历史不可变 | 禁止重跑、补跑、续跑或改判 | Deferred |
| `WP-K-EFFECT-HARNESS-CLOSURE-07` | candidate-06 历史闭环与 Harness 修复 | `L2_01_02 DR-KEV-020` | 启动前/结束时共享唯一工作树 allowlist，固定 candidate-06 失败历史 | `WP-K-EFFECT-CANDIDATE-06-PREP` | - | allowlist 修复、history tests、评审结论 | 合法 authorization 可通过；任何额外变化失败关闭 | 不改生产 src、历史证据或效果合同 | Done |
| `WP-K-EFFECT-CANDIDATE-07-PREP` | 全新效果候选 non-live 冻结 | `DR-KEV-015/019/020` | 绑定 Harness 修复、candidate-06 历史和既有全部快照 | `WP-K-EFFECT-HARNESS-CLOSURE-07` | - | run=`knowledge-p5-live-v4-20260828-candidate-07`、manifest=`af545166...fc2211`、100项资产、reference/预算/launcher | fake 52 对、预算、失败关闭、历史 hash | 不读取密钥或产生 outbound | Done |
| `WP-K-EFFECT-LIVE-07` | 全新候选效果 UAT | `UAT_01` 效果验收合同 | 一次性绑定已执行；授权后预检因准备态 absence assertion 冲突而在 outbound 前停止 | `WP-K-EFFECT-CANDIDATE-07-PREP` | `GATE-079` | append-only authorization 与有限 failed_unconsumed evidence | 0 model/paid/business/retry/resume、历史不可变 | 不重跑、补跑、续跑或创建 candidate-08 | Deferred |
| `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | 效果 Harness 状态合同修复 | `L2_01_02 DR-KEV-020～022`；candidate-07 append-only 失败证据 | 准备态测试与授权后 live preflight 分离；历史 candidate-07 从 frozen HEAD 校验 | `WP-K-EFFECT-CANDIDATE-07-PREP` | - | launcher、history/preparation tests、失败证据哈希 | non-live、PowerShell AST、历史 hash、代码评审 | 不修改历史 manifest/evidence，不执行 live | Done |
| `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | 全部当前设计落实审计 | 当前 REQ/L0/L1/L2/P3/UAT/ARCH、代码、配置、测试和 evidence | 建立设计要求→实现→测试→UAT/evidence 矩阵并修复目标内缺口 | `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | - | 第16节完整审计矩阵、缺口处置与评审记录 | 文档/代码/测试交叉验证 | 超范围依赖如实标记，不伪装完成 | Done |
| `WP-SEVEN-ITEM-CLOSURE-06` | 最终验证与评审收口 | 本轮全部文档/代码/测试/UAT | 全量验证、代码评审、最终状态同步、原子提交推送 | `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | - | 测试清单、评审结论与 Git 交付记录；`GATE-078` 是本工作包的关闭门而非入口门 | Blocker/Major=0、最终 Git 状态明确 | 不改判效果或覆盖历史 | Done |
| `WP-K-UAT-TRACE-CLOSURE-09` | Knowledge UAT 追踪资产纠偏与有限收口 | `UAT_00 v1.24`、`UAT_01 v1.12`、candidate-05/07 不可变证据 | 修复 Business authority；以 Knowledge traceability schema v2 分离最新有效效果、最新执行终态和当前版本证据状态 | `WP-SEVEN-ITEM-CLOSURE-06` | - | 两份当前 traceability、strict validator/tests、评审与回归结果 | 35/35、37/37、历史哈希、零新 outbound、跨层状态一致 | 回退当前追踪资产和 validator，不修改任何历史 candidate/evidence | Done |
| `WP-K-REWRITE-SCHEMA-11` | Knowledge Rewrite 精确输出合同与验证台展示 | `L1_01 v1.10`、`L2_01_00 v1.11`、`UAT_01 v1.13` | 新增 Rewrite V2 精确 JSON 指令并切换生产单绑定；验证台显示安全模型投影、Knowledge 加工文本与完整结果 | `WP-K-UAT-TRACE-CLOSURE-09` | - | V2 task/生产装配、合同测试、页面与安全合同测试、文档同步 | Knowledge 定向回归、strict mypy、compileall、Spring 合同、历史 V1 文件无差异 | 回退 V2 生产绑定和当前文档/UI，不修改 V1 或历史 evidence | Done |
| `WP-EMP-NL-DESIGN-10` | Employee 自然语言扩展方案与设计 | 当前 `REQ_00`、`L1_00/L1_02`、`L2_00_02/L2_02_00/L2_02_01` | LLM 语义理解、typed protected references、多值 operator、同字段组合和行政区规范化的最小方案 | `WP-BQ-COMPLETION-CLOSURE-04` | - | 原子文档修订、三轮内审和独立跨层设计评审 | strict 文档校验；S0/S1/未处理 S2 均为0 | 不修改公共 DTO、Employee endpoint、权限或 ES 结构 | Done |
| `WP-BQ-MULTIVALUE-CONTRACT-10` | Business 多值 QueryPlan 公共合同 | `L2_00_02`、`L2_02_00` | `value_refs`、`prefix_any/contains_any`、operator value shape、组合矩阵、地区 profile 和模型 catalog | `WP-EMP-NL-DESIGN-10` | - | v3 配置、strict loader、decoder/validator/binder 与 v5 task | 单元、契约、mypy、compileall | 回退新 task/config 绑定，保留旧版本和历史 evidence | Done |
| `WP-EMP-NL-QUERY-10` | Employee 自然语言查询实现 | `L2_02_01`、`UAT_00` | protected extractor、Employee request mapper、现有 `/employees/es/search` 映射、零泄漏和失败关闭 | `WP-BQ-MULTIVALUE-CONTRACT-10` | - | 生产代码、fake server、Spring→Runtime E2E 和防回退测试 | extractor/mapper/integration/security/full non-live | 不启用 workBase，不新增 endpoint 或本地 Resolver | Done |
| `WP-EMP-NL-UAT-10` | Employee 自然语言扩展受控 UAT | `UAT_00 v1.24` | 15 类姓氏、姓名、地区、语言变化、拒绝和预算场景 | `WP-EMP-NL-QUERY-10` | `GATE-082` | candidate-01～04 append-only 结果及组合追踪测试 | 15类覆盖、累计模型30/Employee27、泄漏与其他 endpoint 为0 | 禁止额外模型调用、补跑、续跑或新候选 | Done |
| `WP-EMP-NL-CLOSURE-10` | Employee 自然语言扩展最终收口 | 本轮设计、代码、测试与 UAT | 历史哈希、全量验证、正式代码评审、文档状态和 Git 交付 | `WP-EMP-NL-UAT-10` | - | 组合历史测试、评审结论、验证记录与提交清单 | Blocker/Major=0；文档、代码、证据一致 | 不覆盖历史资产或用户无关修改 | Done |
| `WP-KCORPUS-AUDIT-01` | 正文及附件只读审计 | `REQ-KCORPUS-001/005`; `L2_01_01 v2.5` | 5596 个当前索引文档库存、官方来源可达性、可核验正文/附件完整性和人工 P0/P1/P2 清单 | - | - | strict audit JSONL、summary/hash、缺口与优先级 | Schema、三层事实、全量计数、抽样、当前索引零写入 | 删除本轮临时抓取；不改变现行索引 | Done |
| `WP-KCORPUS-DESIGN-01` | 阶段 A 语料生命周期设计 | `REQ_00 v2.3`; Knowledge L1/L2；审计 v1 事实输入 | 在线/离线隔离、asset/parser/OCR/chunk/index/policy/release/rollback 合同 | - | - | Approved 设计、三轮内审、独立评审 | strict validators、跨层追踪、无环 DAG | 回退文档；不改历史 evidence | Done |
| `WP-KCORPUS-PIPELINE-01` | 版本化语料处理流水线 | `L2_01_01 DR-KRET-013～021/026` | 官方下载、不可变 asset、PDF/Office/OCR/表格、结构切片、质量隔离、embedding | `WP-KCORPUS-AUDIT-01`、`WP-KCORPUS-DESIGN-01` | `GATE-083` | `knowledge-corpus-tools`、manifests、tests | `TEST-KRET-010～017/021`; `VAL-KRET-006` | 保留 raw，撤销未发布 parsed/build；不写现行索引 | Done |
| `WP-KCORPUS-INDEX-01` | 候选索引与策略/Profile 快照 | `L2_01_01 DR-KRET-022～024`; `L2_01_02 DR-KEV-023～025` | 复制基线、写新增合格 chunk、新 mapping/snapshot/catalog、完整性验证 | `WP-KCORPUS-PIPELINE-01` | - | 新索引、build manifest、v2 egress catalog、binding | `TEST-KRET-017/018`; `VAL-KRET-007` | 候选保持未发布；不删除旧索引 | Done |
| `WP-KCORPUS-UAT-01` | 阶段 A 直接检索 UAT | `UAT_01 v1.19` 阶段 A | 14类正文/附件/表格/OCR/时效/授权/Evidence及酒店住宿 P0 | `WP-KCORPUS-INDEX-01` | - | 逐 case 有限追踪和发布门禁证据 | typed keyword/vector、权限、引用、回归 | 不以阶段 B topK 失败否定语料存在性 | Done |
| `WP-KCORPUS-RELEASE-01` | alias 发布、回滚演练与收口 | `L2_01_01 DR-KRET-025` | 原子切候选、冒烟、切回旧目标验证、最终切候选、状态/评审/Git | `WP-KCORPUS-UAT-01` | - | release journal、最终 binding、评审和提交；alias 生效由发布门禁独立判定 | alias/UUID/Profile/policy、全量回归、历史 hash | 精确原子恢复旧目标；不删除索引 | Done |
| `WP-KRETRIEVAL-DIAG-01` | 阶段 B 根因诊断 | `REQ-KQUALITY-001～004` | 同索引十组零模型对照与有限排名证据 | - | - | diagnosis v1 JSONL、根因矩阵 | 当前服务窗口、改写反例、路径/融合/重排/Evidence | 不写索引、不调用外部模型 | Done |
| `WP-KRETRIEVAL-DESIGN-01` | 阶段 B 设计 | KQ-AD-018；DR-KFLOW-024/025、DR-KRET-029/034、DR-KEV-029/030 | §20.36及§20.55必要证据/评分表示增量；旧设计记录不覆盖 | `WP-KRETRIEVAL-DIAG-01` | - | 三轮内审及分离编辑的正式设计复评 | 合同、预算、安全与DAG | 不改变历史资产 | Done |
| `WP-KRETRIEVAL-IMPLEMENT-01` | 阶段 B 实施 | `DR-KFLOW-024～027`；`DR-KRET-029/034/035`；`DR-KEV-029～033` | 已有当前链路保持，§20.66文号匹配增量已实施 | `WP-KRETRIEVAL-DESIGN-01` | `GATE-KRG-006` | §20.66.1新增量代码对照复评 | 新TEST/VAL与公开接口零差异 | 默认关闭/源码回退；索引不变 | Done |
| `WP-KRETRIEVAL-NONLIVE-01` | 阶段 B 回归 | 当前阶段 B L2新需求增量 | 已有回归保持，DR-KRET-035 Java/基线/历史回归已验证 | `WP-KRETRIEVAL-IMPLEMENT-01` | - | §20.66.1新增量验证；旧记录不改 | 调用计数、零泄漏、来源绑定 | 不以fake关闭真实UAT | Done |
| `WP-KRETRIEVAL-UAT-01` | 阶段 B 专项 UAT | `UAT_01` §14.40～14.43、DR-KEV-032/033 | 分层检索计分、同快照文号对照待完成；旧失败不改 | `WP-KRETRIEVAL-NONLIVE-01` | - | 逐 case 检索/运行/回答分列 | 累计正式22/53已用，诊断1另列 | non-live已完成；不自动补跑付费 | In Progress |
| `WP-KRETRIEVAL-QUALITY-01` | 阶段 B 质量收口 | ROADMAP §4.5.2 | 正式代码评审、核心 P0、状态与 Git | `WP-KRETRIEVAL-UAT-01` | - | 评审结论和交付记录 | 核心 P0 不豁免，功能/安全/效果分列 | 未达标保持未完成 | Blocked |

## 6. 直接依赖图

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

DAG 无环；阶段 B 独立收口，不依赖阶段 C/D 或图谱联合 UAT。既有已消费授权不可复用；新的阶段 B 授权不等于允许重跑历史 P5 candidate。

## 7. 阶段门禁

| 门禁 ID | 工作包 | 类型 | 控制动作 | 是否阻塞入口 | 关闭条件 | 证据/权威来源 | 责任方/外部提供方 | 最晚关闭阶段 | 验证者与方法 | 未关闭行为 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `GATE-067` | `WP-BQ-FILTER-CONTRACT-02` | closure | 新设计基线生效 | 否 | REQ/L0/L1/L2/P3/UAT 两阶段评审通过且版本一致 | 当前 Approved/Reviewed 文档、strict validators、跨层追踪与无环 DAG | 文档维护者 | 代码实施前 | 分层/跨层独立评审与 DAG 校验 | 不允许依据未评审设计实施 | Closed |
| `GATE-068` | `WP-EMP-ES-AUTH-02` | release_effective | Employee search/vector 端点级角色转换及最终守卫生效 | 否 | 两个既有 POST endpoint 显式绑定共享 converter，真实 JWT role claim 经完整 SecurityFilterChain 通过 ADMIN/VIEWER、拒绝矩阵及 detail/fallback 兼容 | `EmployeeEsSecurityIntegrationTest` 两入口真实 JWT role 矩阵；detail/matcher/controller 共 15 项定向通过，Employee 全模块 50 项中 30 通过、20 项 opt-in 跳过 | Employee 业务维护者/实施者 | 恢复 Employee 真实联调前 | Java 真实 Servlet SecurityFilterChain、两 endpoint 矩阵与既有调用方测试 | 禁止真实 Employee 联调及宣称最终授权已生效 | Closed |
| `GATE-069` | `WP-TXN-DATE-WIRE-COMPAT-03` | integration | Transaction Date 时区/精度及真实响应合同生效 | 否 | Python Date→HTTP→Jackson→Mapper instant/open interval/DB precision 成立；生产 Spring UTC 零毫秒 offset 字符串与 standalone 整秒 epoch 都通过严格 codec | 真实零模型 codec 成功解析 20/104；Java Spring JSON/安全链 6 项、Python 专项 244 项、全量 1424 项、非法日期拒绝与 `DATETIME(0)` 元数据 | Transaction 维护者/实施者 | 日期 live/UAT 前 | 双语言 production-config contract、strict bounds 与零模型实际 codec | 日期相关真实联调/UAT 不执行 | Closed |
| `GATE-070` | `WP-BQ-CONTROLLED-LIVE-02` | integration | 真实模型、业务服务和有限敏感数据调用 | 是 | 前置 non-live 包完成，GATE-068/069 关闭，semantic partial hits 与 Transaction 生产 Date 响应合同均已实现，环境/预算/授权/安全边界重新确认，历史 evidence 不可变 | controlled-run06 全新路径、五项 failure hash、Employee 9/20 和 Transaction 20/104 零模型生产 codec、Java 6 项、Python 1424 项及 strict mypy | 用户/业务维护者 | 下一次真实模型联调前 | frozen task/config/cases、真实安全链、预算、历史 hash 和零泄漏 preflight | controlled live 保持 Blocked；只允许独立零模型只读诊断 | Closed |
| `GATE-UAT-007` | `WP-BQ-UAT-HANDOFF-02` | closure | 正式四阶段 UAT | 是 | 18 个真实模型/业务场景保持不可变，剩余 17 个确定性风险由当前生产组合根、Spring 安全链或跨语言合同逐项验证，35 个计划用例均有唯一追踪且不外推真实执行范围 | run03 SHA-256=`b49832426147dc14d56e571fea11b0345e16602d8cb5e2ea2eeb3dacb3326dd8`；`uat_traceability.v2.json`；Spring→Runtime、Java 安全链及 Python/Java 合同测试 | 用户/UAT 执行者 | 阶段最终收口前 | 严格校验 35 个 case、18/17 证据分类、引用符号、历史 hash、零调用与权限边界 | 任一 case 无实际或等价证据则恢复 Open，不得靠旧 detail/stub 结果关闭 | Closed |
| `GATE-071` | `WP-K-RUNTIME-WIRING-03` | closure | Knowledge 生产接线设计生效 | 是 | L1/L2/P3/UAT_01 语义一致，三轮内审与独立评审无 S0/S1/未处理 S2 | 当前文档、strict validators、跨层追踪和 DAG | 文档维护者 | 生产接线前 | 分层/跨层设计评审 | 不允许依据未评审语义接线 | Closed |
| `GATE-UAT-008` | `WP-K-FUNCTIONAL-UAT-03` | closure | Knowledge 功能验收 | 是 | UAT_01 37 个功能 case 均有实际/等价证据，关键 Spring→Runtime 16 场景 E2E 实际执行，权限/出域/失败/零调用成立 | `knowledge_uat_traceability.v2.json`、Spring/Python 测试与有限 evidence | 实施者/UAT 评审者 | 效果诊断前 | Schema、引用、调用计数和回归验证 | 任一当前证据失效则恢复 Open | Closed |
| `GATE-072` | `WP-K-EFFECT-LIVE-05` | integration | 真实付费 Knowledge 效果 UAT | 是 | frozen HEAD=`63bc30b...2efa`、manifest=`41997c6...e278c`、26 case 双变体、预算78完成唯一执行；安全 Gate 通过，结论 `partially_effective` | result SHA-256=`a6de81f...36eb`；44/44 terminal、rewrite22、summary22、retry/core answer=0；post-consumption tests | 用户 | 首个模型 outbound 前 | clean/frozen source、预算、历史 hash、敏感扫描 | 禁止重跑、补跑、续跑或改判 | Closed |
| `GATE-073` | `WP-DOC-CONSISTENCY-06` | closure | 七项文档纠偏生效 | 否 | 3 轮内审及独立分层/跨层评审通过，版本/状态/DAG/实现事实一致 | strict design/plan validators、链接和跨层差异矩阵 | 文档维护者 | 测试入口或效果代码修改前 | 独立评审无 S0/S1/未处理 S2 | 受影响代码实施保持 Blocked | Closed |
| `GATE-074` | `WP-PY-REGRESSION-REPRO-06` | closure | Python 正式全量入口生效 | 否 | 版本化隔离 bootstrap 显式安装当前源码；14 项 host/preflight 与全量 non-live 通过且历史 hash 不变 | `scripts/run-nonlive-regression.ps1`：Python 3.12.4、host 14/14、全量 1419 passed/27 opt-in skipped/0 failed；strict mypy 448 文件；candidate-04/05 17 项哈希复核 | 实施者 | candidate-05 根因复核前 | 从干净源码树重复执行 | 效果优化保持 Blocked | Closed |
| `GATE-075` | `WP-K-EFFECT-OPT-06` | closure | Summary V4 与效果口径 v2 生效 | 否 | candidate-05 诊断和设计评审通过；Summary V4 多要点/多域覆盖、v2 分母/质量 Gate、non-live、安全、E2E、类型和历史回归全部通过 | Knowledge 260 passed/6 opt-in skipped；正式全量 1427 passed/27 skipped；Spring E2E 1 passed；strict mypy 452 文件；compileall、历史哈希及代码评审通过 | 实施者/评审者 | 新候选冻结前 | 阈值/validator/权限/历史反证 | candidate-06 准备保持 Blocked | Closed |
| `GATE-076` | `WP-K-EFFECT-CANDIDATE-06-PREP` | closure | candidate-06 非 live 冻结 | 否 | run=`knowledge-p5-live-v3-20260828-candidate-06`、manifest=`7f54ddff...cc51b8`、reference=`P3_00:GATE-077`、预算78、92项资产与失败关闭已冻结 | candidate-06 preparation/contracts/history、唯一未跟踪授权记录及 HEAD/manifest 强绑定边界；正式全量1442 passed/27 skipped；strict mypy 454文件；compileall、PowerShell AST、历史 hash | 实施者 | 真实授权申请前 | 首 outbound、预算、retry/resume=0 | 关闭时未创建正式 authorization、未读取密钥或产生 outbound；后续消费不改写本门禁历史结论 | Closed |
| `GATE-077` | `WP-K-EFFECT-LIVE-06` | integration | candidate-06 一次性真实效果 UAT | 是 | 精确授权已消费；candidate-06 因 Harness `snapshot_changed` 失败，不形成效果结论 | consumed/failure/journals 精确哈希；44 paid、52 变体、retry=0 | 用户/实施者 | 已消费 | 历史哈希与有限失败复核 | 禁止重跑、补跑、续跑或复用授权 | Closed |
| `GATE-079` | `WP-K-EFFECT-LIVE-07` | integration | candidate-07 一次性真实效果 UAT 授权 | 是 | 绑定授权已执行一次并形成 `Failed/Unconsumed` 唯一终态；无论是否产生有效测量均不得复用 | authorization SHA-256=`47575441...7a06`；preflight failure SHA-256=`919fa148...32d6`；model/paid/business=0 | 用户/实施者 | 已终止 | frozen binding、失败阶段、零调用、敏感扫描和历史不可变 | 禁止重跑、补跑、续跑或创建 candidate-08 | Closed |
| `GATE-078` | `WP-SEVEN-ITEM-CLOSURE-06` | closure | 当前项目实现与验收治理收口 | 否 | candidate-07 无效运行及最新有效 `partially_effective` 均如实记录；Harness 状态合同、全量设计落实审计、必要实现、全量 Python/Java、设计/代码评审和文档状态全部闭合 | P3 第16节审计矩阵、UAT_01、1468/27 Python 隔离回归、五个 Java 模块验证与评审结论 | 实施者/评审者 | 最终内容提交前 | Blocker/Major=0；当前 V4 效果证据缺口显式列出；不存在待修改的目标内内容 | 不宣称效果已 effective；不自动创建新候选。Git commit/push 是门禁关闭后的交付验证，只记录在最终报告，避免 tracked 文档对自身提交 SHA 形成循环依赖 | Closed |
| `GATE-080` | `WP-EMP-NL-DESIGN-10` | closure | Employee自然语言扩展设计生效 | 否 | 服务合同核实、三轮内审和独立跨层设计评审完成，S0/S1/未处理S2均为0 | 当前REQ/L1/L2、Java search合同、strict文档校验和评审记录 | 文档维护者/评审者 | 公共合同实施前 | 分层/跨层设计评审与无环DAG检查 | 禁止依据未评审语义修改QueryPlan或Employee映射 | Closed |
| `GATE-081` | `WP-EMP-NL-QUERY-10` | closure | 多值合同与Employee查询non-live生效 | 否 | extractor、decoder/validator/binder、配置、v7模型任务、Employee mapper、Spring E2E、Java安全链、类型和正式隔离回归通过 | 定向单元/契约/集成、strict mypy、compileall、Maven与non-live结果 | 实施者/评审者 | 真实UAT冻结前 | 代码对照设计复核、敏感扫描和下游零调用 | 禁止冻结或执行真实UAT | Closed |
| `GATE-082` | `WP-EMP-NL-UAT-10` | integration | Employee自然语言扩展受控UAT与最终收口 | 是 | 四候选累计模型不超过30、Employee search不超过30；candidate-04代表性13/13通过并与candidate-03不可变302/307组成15类完整证据；至少一个地区成功列表、安全与零调用合同全部成立 | candidate-04 result SHA-256=`2dc6e4c3755f2a32542e6219d671b388a9b1eb7dc97c510225d995a5d3cc48fd`；history/combined coverage tests；全量回归与正式代码评审 | 用户/实施者/评审者 | 本目标最终收口 | exact hash、预算、逐case、零泄漏、历史不可变与代码对照设计复核 | 禁止任何额外模型调用或新候选；证据失效时如实重新打开，不得改判历史 | Closed |
| `GATE-083` | `WP-KCORPUS-PIPELINE-01` | slice_implementation | 首次持久下载和候选索引写入 | 是 | 官方来源/P0-P2范围、显式外部workspace、解析工具版本、下载/存储/索引预算、精确旧alias目标与回滚方案明确；REQ/L1/L2三轮内审和独立评审通过 | audit v3、Approved 阶段 A 设计、工具/依赖快照、旧 alias 只读证明 | 维护者/评审者 | 首次持久下载前 | strict Schema/设计/计划校验与分层跨层评审 | 只允许不落盘的官方来源和索引元数据审计 | Closed |
| `GATE-084` | `WP-KCORPUS-RELEASE-01` | release_effective | 候选 alias 生效 | 否 | P0及目标P1完成、P2清单、解析/OCR/表格质量、空正文/孤立附件、candidate完整性、typed keyword/vector、读取/出域/Evidence、回归和回滚演练通过 | Stage A corpus candidate-08/a5 build manifest、14/14 UAT attempt-05、release attempt-05 journal、测试和评审 | 维护者/UAT/评审者 | alias切换前 | 完整性、权限、引用、alias原子性和历史hash | 候选保持未发布；现行alias不变 | Closed |
| `GATE-KRG-006` | `WP-KRETRIEVAL-IMPLEMENT-01` | slice_implementation | §20.36/20.55/20.66合同、评分及文号增量实施；旧准入不撤销 | 是 | 三轮内审及正式分层/跨层复评通过；无fallback或公共接口/权限扩张 | §20.36/20.55/20.66及L1/L2新DR | 设计维护者/评审者 | 新增量代码修改前 | S0/S1/未处理S2=0；不依赖live结果 | 新增量已审，允许non-live；真实UAT仍暂停 | Closed |

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

| 顺序 | 工作包 | 判定 | 未关闭依赖/门禁 | 选择理由 |
|---|---|---|---|---|
| 1 | `WP-BQ-FILTER-CONTRACT-02` | Done | - | filters/operator/tagged value、组合校验与绑定已通过 45 项回归及 strict mypy |
| 2 | `WP-BQ-FIELD-CONFIG-02` | Done | `WP-BQ-FILTER-CONTRACT-02` | 三动作统一 JSON、固定字段映射、敏感暴露与有限脱敏通过 64 项回归 |
| 3 | `WP-BQ-MODEL-CATALOG-02` | Done | `WP-BQ-FIELD-CONFIG-02` | v3 filters Prompt、三个逻辑 action 目录及上海地址 fake 生成已通过 |
| 4 | `WP-EMP-SEARCH-ADAPTER-02` | Done | `WP-BQ-FIELD-CONFIG-02` | search 固定接口、上海地址、分页排序、严格 hits、字段脱敏及 protected slot 通过 106 项回归 |
| 5 | `WP-EMP-SEMANTIC-ADAPTER-02` | Done | `WP-BQ-FIELD-CONFIG-02` | 固定 vector-search/profile、单调用、敏感与 filter/vector 拒绝通过 82 项回归 |
| 6 | `WP-EMP-ES-AUTH-02` | Done | - | 两 ES POST endpoint 共享 converter、完整 Servlet 角色矩阵及 detail/fallback 兼容通过；Employee 全模块 30 项通过 |
| 7 | `WP-TXN-SEARCH-EXT-02` | Done | - | 四字段/Decimal/page 及 standalone epoch 合同已实施并保留 |
| 8 | `WP-TXN-DATE-WIRE-COMPAT-03` | Done | - | 生产 UTC/standalone epoch 双形态、Java Spring 6 项、Python 244 项及真实 20/104 codec 通过 |
| 9 | `WP-BQ-RUNTIME-CUTOVER-02` | Done | - | 正式启动入口、统一配置、三动作 Registry、受控 HTTP transport 与默认 stub 契约通过 |
| 10 | `WP-EMP-DETAIL-RETIRE-02` | Done | - | 生产目录只有三动作，Transaction protected slot 不再依赖旧参数校验；历史源码按冻结提交核验 |
| 11 | `WP-BQ-NONLIVE-E2E-02` | Done | - | 三动作唯一 production 对象图、上海地址、Date/Decimal、角色拒绝、非法字段、跨域与 Knowledge 隔离通过全量 1392 项测试 |
| 12 | `WP-BQ-CONTROLLED-LIVE-02` | Done | - | controlled-run06 六个真实模型场景通过：Employee search/semantic、Transaction、权限拒绝和未配置字段零调用 |
| 13 | `WP-TXN-TEXT-POLICY-COMPAT-03` | Done | - | `eq` 接受 `_`、contains 拒绝 LIKE 通配、95 项定向及 1438 项 non-live 通过；首次 UAT hash 不变 |
| 14 | `WP-BQ-MODEL-INTENT-COMPLETENESS-03` | Done | - | v4 显式 semantic+地点/相对日期 unsupported；119 项定向、1440 项 non-live、115 模块 strict mypy 与新 manifest 均通过 |
| 15 | `WP-BQ-UAT-HANDOFF-02` | Done | - | 独立 run03 正式 UAT 18/18 通过：Employee search 6、semantic 1、Transaction search 7、四项 unsupported 零调用 |
| 16 | `WP-BQ-COMPLETION-CLOSURE-04` | Done | `WP-BQ-UAT-HANDOFF-02` | 18 个真实场景边界不变，17 个确定性风险由当前自动化逐项闭合；旧 detail/stub UAT 仅作历史资产 |
| 17 | `WP-K-BASELINE-03` | Done | - | L1/L2/P3/UAT_01 已完成三轮内审和独立评审 |
| 18 | `WP-K-RUNTIME-WIRING-03` | Done | - | 默认关闭、enabled 单注册、owned clients 与 stub/fake 边界已验证 |
| 19 | `WP-K-SPRING-NONLIVE-E2E-03` | Done | `WP-K-RUNTIME-WIRING-03` | 当前生产对象图 16 场景 Spring→Runtime E2E 通过 |
| 20 | `WP-K-FUNCTIONAL-UAT-03` | Done | `WP-K-SPRING-NONLIVE-E2E-03` | 37/37 case 严格追踪，Functional=Passed |
| 21 | `WP-K-EFFECT-DIAG-03` | Done | `WP-K-FUNCTIONAL-UAT-03` | candidate-04 三项历史 hash、指标/分布/9 个域差异可复现 |
| 22 | `WP-K-EFFECT-OPT-03` | Done | `WP-K-EFFECT-DIAG-03` | 域目录 v2 与 Summary v3 已实施并通过安全/回归验证 |
| 23 | `WP-K-EFFECT-CANDIDATE-05-PREP` | Done | `WP-K-EFFECT-OPT-03` | run=`knowledge-p5-live-v2-20260826-candidate-05`，manifest=`41997c6...e278c`，预算 78，冻结准备已被唯一 live 消费 |
| 24 | `WP-K-EFFECT-LIVE-05` | Done | `WP-K-EFFECT-CANDIDATE-05-PREP`; `GATE-072` | 52 个 Capability 成对完成，44 次付费请求全部终态完成，安全 Gate 通过，结论 `partially_effective` |
| 25 | `WP-K-CLOSURE-03` | Done | `WP-K-EFFECT-LIVE-05` | 全量回归、正式代码评审和状态同步完成，Blocker/Major=0 |
| 26 | `WP-DOC-CONSISTENCY-06` | Done | `WP-K-CLOSURE-03` | 三轮内审及独立复评完成，修复两项 S2，`GATE-073` Closed |
| 27 | `WP-PY-REGRESSION-REPRO-06` | Done | `WP-DOC-CONSISTENCY-06` | 隔离安装入口已通过 host 14/14、全量 1419/1419、27 项 opt-in 跳过及历史哈希复核 |
| 28 | `WP-K-EFFECT-DIAG-06` | Done | `WP-PY-REGRESSION-REPRO-06` | 诊断重算通过；确认 summary 分母、gold 归因和 mixed-domain 覆盖三类根因 |
| 29 | `WP-K-EFFECT-OPT-06` | Done | `WP-K-EFFECT-DIAG-06` | Summary V4、效果口径 v2、生产单绑定和 non-live 反证均已通过 |
| 30 | `WP-K-EFFECT-CANDIDATE-06-PREP` | Done | `WP-K-EFFECT-OPT-06` | run=`knowledge-p5-live-v3-20260828-candidate-06`，92项资产、manifest=`7f54ddff...cc51b8`、reference=`P3_00:GATE-077`、预算78已冻结，无密钥/outbound |
| 31 | `WP-K-EFFECT-LIVE-06` | Deferred | `GATE-077` 已消费 | candidate-06 已终止失败且禁止重跑；后续由独立修复与新候选承接 |
| 32 | `WP-K-EFFECT-HARNESS-CLOSURE-07` | Done | `WP-K-EFFECT-CANDIDATE-06-PREP`；candidate-06 append-only 失败证据 | 共享allowlist、五项历史哈希和代码评审通过 |
| 33 | `WP-K-EFFECT-CANDIDATE-07-PREP` | Done | `WP-K-EFFECT-HARNESS-CLOSURE-07` | run/manifest/reference/78次预算/100项资产冻结，outbound=0 |
| 34 | `WP-K-EFFECT-LIVE-07` | Deferred | `WP-K-EFFECT-CANDIDATE-07-PREP`; `GATE-079` | candidate-07 已在 outbound 前形成 `failed_unconsumed` 唯一终态，Effectiveness=`invalid_run`；禁止重跑或创建 candidate-08 |
| 35 | `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | Done | `WP-K-EFFECT-CANDIDATE-07-PREP`；candidate-07 append-only failure | launcher 不再执行准备态 absence assertion；candidate-07 源码和三项历史资产从 frozen HEAD/精确哈希校验 |
| 36 | `WP-DESIGN-IMPLEMENTATION-AUDIT-08` | Done | `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` | 第16节覆盖全部当前权威文档；仅当前 V4 效果测量标记为 `Evidence missing` |
| 37 | `WP-SEVEN-ITEM-CLOSURE-06` | Done | `WP-DESIGN-IMPLEMENTATION-AUDIT-08`; `GATE-078` | 全量 Python/Java、文档、类型、历史、安全和正式评审通过；Git 交付状态由最终报告记录 |
| 38 | `WP-K-UAT-TRACE-CLOSURE-09` | Done | `WP-SEVEN-ITEM-CLOSURE-06` | Business 35/35 与 Knowledge 37/37 不变；当前追踪资产明确 latest valid partial、latest execution invalid 和 Summary V4 evidence missing |
| 39 | `WP-EMP-NL-DESIGN-10` | Done | `WP-BQ-COMPLETION-CLOSURE-04` | 三轮内审、独立跨层设计评审及既有Employee search能力核实完成，`GATE-080` Closed |
| 40 | `WP-BQ-MULTIVALUE-CONTRACT-10` | Done | `WP-EMP-NL-DESIGN-10` | `value_refs`、多值operator、组合矩阵、地区profile和严格catalog合同通过 |
| 41 | `WP-EMP-NL-QUERY-10` | Done | `WP-BQ-MULTIVALUE-CONTRACT-10` | extractor/binder/mapper、Spring E2E、安全与正式隔离non-live通过，`GATE-081` Closed |
| 42 | `WP-EMP-NL-UAT-10` | Done | `WP-EMP-NL-QUERY-10`; `GATE-082` | candidate-04代表性13/13及candidate-03不可变302/307共同覆盖15类；累计模型30、Employee27 |
| 43 | `WP-EMP-NL-CLOSURE-10` | Done | `WP-EMP-NL-UAT-10` | 历史哈希、组合覆盖、全量验证、正式评审和状态同步完成 |
| 44 | `WP-K-REWRITE-SCHEMA-11` | Done | `WP-K-UAT-TRACE-CLOSURE-09` | Rewrite V2 精确 JSON 合同、生产单绑定、页面安全投影和回归通过 |
| 45 | `WP-KCORPUS-AUDIT-01` | Done | - | audit v3 验证5597项三层事实，P0=3/P1=0/P2=5594，ES写入=0 |
| 46 | `WP-KCORPUS-DESIGN-01` | Done | - | 审计 v1 暴露的事实混淆和预算问题已进入 v2.1 合同；三轮内审、strict validator及独立评审通过 |
| 47 | `WP-KCORPUS-PIPELINE-01` | Done | - | 5个官方asset完成版本化获取/结构解析，形成749个block、738个合格chunk和55个条款引用；网络和损坏容器异常逐资产有限隔离，无失败件入索引 |
| 48 | `WP-KCORPUS-INDEX-01` | Done | - | 最终工具源码一致的 Stage A corpus candidate-08/a5 共15521 chunk、5600文档，policy full-membership通过 |
| 49 | `WP-KCORPUS-UAT-01` | Done | - | `UAT-KCORPUS-A-01～14` 全部 Passed，模型/Business调用为0 |
| 50 | `WP-KCORPUS-RELEASE-01` | Done | - | alias按a4→a5→a4→a5三步原子切换/回滚验证完成，最终指向a5，旧索引与早期候选均保留 |
| 51 | `WP-KRETRIEVAL-DIAG-01` | Done | - | 阶段B独立DAG与§20证据；增量设计已复评通过，不继承live通过 |
| 52 | `WP-KRETRIEVAL-DESIGN-01` | Done | WP-KRETRIEVAL-DIAG-01 | §20.36及§20.55增量三轮内审/正式只读评审通过；只准入non-live实施 |
| 53 | `WP-KRETRIEVAL-IMPLEMENT-01` | Done | WP-KRETRIEVAL-DESIGN-01 | §20.66.1文号匹配已实施/复评；旧增量保持 |
| 54 | `WP-KRETRIEVAL-NONLIVE-01` | Done | WP-KRETRIEVAL-IMPLEMENT-01 | §20.66.1 Java、基线和历史通过；旧回归保持 |
| 55 | `WP-KRETRIEVAL-UAT-01` | In Progress | WP-KRETRIEVAL-NONLIVE-01 | 待同快照对照及相关性标注；旧失败及8项未执行保持，暂停付费 |
| 56 | `WP-KRETRIEVAL-QUALITY-01` | Blocked | WP-KRETRIEVAL-UAT-01 | 阶段B独立DAG与§20证据；新需求设计、实现和non-live已完成，真实专项仍未完成 |

## 10. 实施交接

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
| `WP-KRETRIEVAL-NONLIVE-01` | 当前代码non-live验证 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-024、DR-KRET-029、DR-KEV-029/030 | UAT_01 §14.21；§20.40 | UAT | implement-from-detailed-design |
| `WP-KRETRIEVAL-UAT-01` | 冻结后一次有限真实UAT | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | QUALITY | implement-from-detailed-design |
| `WP-KRETRIEVAL-QUALITY-01` | 正式评审及状态/Git交付 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | 阶段B完成 | code-review-against-docs |

## 11. 风险与回滚

Employee 旧调用方不兼容、workBase 数据无效、raw hits 泄漏、Date 时区/精度未证明、Decimal 精度、slot 出域以及 non-live gate 被误用于 live 是主要风险。按 action 关闭、移除目标组合根和保留历史 evidence 回滚；不得重新启用 Resolver、删除测试、扩张业务接口或放宽 validator。

## 12. 追踪矩阵

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
| `WP-KRETRIEVAL-DESIGN-01` | REQ-KQUALITY-001～004；DR-KFLOW-024/025、DR-KRET-029/034、DR-KEV-029/030 | §20.36及§20.55必要证据/评分表示增量 | TEST-KFLOW-016、TEST-KRET-024/029、TEST-KEV-020；UAT_01 §14.21/14.31 | §20.36及§20.55三轮内审及正式评审 | Done |
| `WP-KRETRIEVAL-IMPLEMENT-01` | REQ-KQUALITY-001～004；DR-KFLOW-024/025、DR-KRET-029/034、DR-KEV-029/030 | §20.37～20.40及§20.55公共合同、需求排序、Summary覆盖及唯一成对绑定 | TEST-KFLOW-016、TEST-KRET-024/029、TEST-KEV-020；UAT_01 §14.21/14.31 | 当前完整对象图及代码复评通过；不替代真实效果 | Done |
| `WP-KRETRIEVAL-NONLIVE-01` | REQ-KQUALITY-001～004；DR-KFLOW-024～026、DR-KRET-029/034、DR-KEV-029～031 | 当前8/7/v3及授权上下文评分表示的完整对象图fake/Spring | TEST-KFLOW-016/018、TEST-KRET-024/029、TEST-KEV-020/021；UAT_01 §14.38 | §20.60.1正式隔离回归、类型及Spring实际通过 | Done |
| `WP-KRETRIEVAL-UAT-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～026、DR-KRET-027/028/034、DR-KEV-026～031 | §20.61 当前目标落点 | TEST-KFLOW-014/015/017/018、TEST-KRET-022/023/029、TEST-KEV-017～021；UAT_01 §14.39 | run-12实际1通过/1失败/8未执行，专项未通过 | In Progress |
| `WP-KRETRIEVAL-QUALITY-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | §20 当前目标落点 | TEST-KFLOW-014、TEST-KRET-022、TEST-KEV-017；UAT_01 §14 | §20逐项证据 | Blocked |

需求到工作包/UAT 的跨层映射：

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

工作包状态根据直接依赖和入口门禁实时计算，不能把旧 detail/flat arguments 的历史 Done 或 candidate evidence 继承为新包完成；每个包需独立测试、代码对照设计评审与授权后状态同步。

本次 Knowledge 正式代码对照设计评审覆盖生产对象图、默认关闭惰性、Capability/任务唯一性、读取授权、三层出域、typed retrieval、失败优先级、取消/关闭、Business 隔离、历史不可变与 candidate-05 消费后证据。首轮发现 live evidence 的 `workPackageId` 仍硬编码旧值；历史 evidence 保持不可变，runner 已改为从 manifest 取值并补充反证。复评结论：Blocker=0、Major=0、未处理 Minor=0，Passed。

`WP-PY-REGRESSION-REPRO-06` 代码对照设计评审覆盖隔离安装语义、冻结 host 错误分类、环境变量隔离、临时目录所有权、清理路径、历史哈希和生产依赖边界。版本化入口只安装 `pyproject.toml` 已声明的固定构建后端和当前源码，不修改 host/manifest/evidence；复核结论：Blocker=0、Major=0、Minor=0，Passed。

正式 Python 入口为 `agent-runtime/scripts/run-nonlive-regression.ps1`：Python 3.12.4、一次性 venv、`setuptools==80.9.0`、无依赖安装当前源码；先运行冻结 Transaction host/preflight 14/14，再运行全量 non-live `1419 passed, 27 opt-in skipped, 0 failed`。脚本清除进程级 `PYTHONPATH` 并在路径归属校验后清理临时环境；`mypy src tests` 覆盖 448 个文件、`compileall src tests` 通过。candidate-04/05 的 17 项历史资产哈希与冻结基线一致，故 `GATE-074` 已关闭。普通未安装源码树不再作为权威全量入口。

`WP-K-EFFECT-DIAG-06` 只读绑定 candidate-05 result SHA-256=`a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb`。诊断重算证明：4 个安全负例的正确零 Summary 调用使历史 completion 最高只能为 22/26；1 个 answerable `gold_issue` 被错误归因到模型质量；3 个 mixed case 因 coverage 不足不 useful，其中 2 个在 rerank recall=1.0 后仍只采用一条证据。由此只批准 Summary V4 和带 90% 数据质量 Gate 的效果口径 v2；RRF/rerank/Profile、validator、dataset/gold、权限、出域策略和阈值均不变。诊断测试 2/2 通过，candidate-05 manifest/authorization/result 哈希一致。对应 L1/L2/P3/UAT 三轮内审及独立跨层评审已通过，无 S0/S1/未处理 S2。

`WP-K-EFFECT-OPT-06` 已实现独立 `KnowledgeSummaryTaskV4` 并把显式启用的生产组合根唯一切换为 V4；V1～V3 及历史 manifest/evidence 保持不可变。效果口径 v2 仅从摘要完成率分母排除正确零调用的 `security_negative`，普通 no-result/失败仍计入分母；仅显式 `gold_issue` 从质量分母排除，且有效质量样本不足原 answerable 集合的 90% 时整次运行 `invalid_run`。定向合同、组合根和指标测试通过，Knowledge 260 passed/6 opt-in skipped，正式 Python 全量 1427 passed/27 opt-in skipped，Spring→Runtime Knowledge E2E 1 passed，strict mypy 452 文件、compileall、历史哈希和代码对照设计复核均通过；`GATE-075` Closed。

`WP-K-EFFECT-CANDIDATE-06-PREP` 的非 live 冻结事实保持成立：run=`knowledge-p5-live-v3-20260828-candidate-06`、manifest SHA-256=`7f54ddff600726d364edee6f7c6939d99c52aa5b533ac309d98887b6e8cc51b8`、authorization reference=`P3_00:GATE-077`、92 项资产和最多 78 次预算。随后 `GATE-077` 已被唯一执行消费；52 个 capability 变体完成、44 次 paid 全部终态，但最终工作树检查因未复用启动 allowlist 而误报 `snapshot_changed`。该失败不推翻 `GATE-076` 的历史准备证据，也不形成效果结论；其有限运行资产必须保持 append-only。

`WP-K-EFFECT-HARNESS-CLOSURE-07` 与 `WP-K-EFFECT-CANDIDATE-07-PREP` 已完成。candidate-06 authorization/consumed/paid/checkpoint/failure 五项精确哈希通过；启动与结束快照共享精确 allowlist，修改态或其他未跟踪文件继续拒绝。candidate-07 使用schema v5，run=`knowledge-p5-live-v4-20260828-candidate-07`、manifest SHA-256=`af545166b37a33899d6f1d7830c09472df8cc2fe45047fea242ecc524bfc2211`、reference=`P3_00:GATE-079`、100项资产和最多78次预算；35项定向、Knowledge evaluation 142项、正式隔离host 14/14和全量1462 passed/27 opt-in skipped、strict mypy 457文件及compileall/PowerShell AST通过。代码评审第1轮修复launcher schema v4→v5一项Major，第2轮Blocker/Major=0；未创建正式authorization/result，未读取密钥或产生outbound。

本轮 `WP-K-EFFECT-PREFLIGHT-CLOSURE-08` 将 candidate-07 preparation 的 absence assertions 固定为 frozen HEAD 历史检查，并从已要求正式 authorization 存在的 launcher preflight 移除该选择器；新 history 测试锁定 manifest/authorization/failure 三项 SHA-256、100项 frozen 资产、0 调用和唯一失败文件。定向 candidate-06/07 为 23 passed；Knowledge/追踪范围 308 passed、6 opt-in skipped；正式隔离 host 14/14、全量 non-live 1465 passed、27 opt-in skipped、0 failed；strict mypy 458 文件、compileall 和 PowerShell AST 通过。Java 实际结果为 agent-service 35/1 skipped、common-security 21/0、employee-service 50/20 skipped、mq-procedure-service 51/2 skipped、es-query-service reactor 43/0；单独运行 es-query-service 曾因未先构建 `es-query-api` 导致发现期 `ClassNotFoundException`，使用父 reactor `-pl :es-query-service -am test` 后通过，不涉及代码或设计修改。正式代码对照设计评审结论：Blocker=0、Major=0、Minor=0。

`WP-K-UAT-TRACE-CLOSURE-09` 保持 Business 35/35 与 Knowledge Functional 37/37 结论不变，只修复当前追踪权威和效果状态表达：Business traceability 当前绑定 `UAT_00 v1.24`；Knowledge traceability schema v2 绑定 candidate-05 最新有效 `partially_effective`、candidate-07 最新执行 `invalid_run / failed_unconsumed` 和 Summary V4 `Evidence missing`。旧 Knowledge traceability v1 通过精确哈希保留，candidate-01～07 运行资产均不修改；未读取 `LLM_API_KEY`、未创建 candidate-08、模型 outbound=0。

本轮最终验证实际结果：UAT traceability 13 passed；Knowledge 定向集合 311 passed/6 opt-in skipped；正式隔离入口先完成 Transaction host/preflight 14/14，再完成全量 non-live 1468 passed/27 opt-in skipped/0 failed；strict mypy 458 文件、compileall、candidate-07 PowerShell AST、19 份当前文档链接、P3 strict DAG 和敏感扫描均通过。Maven 实际结果为 agent-service 37 tests/3 skipped、common-security 21/0、employee-service 50/20、mq-procedure-service 37/2、es-query-service reactor 43/0，全部 0 failure/0 error。三轮内审第 1 轮修复 P3 状态/DAG，第 2～3 轮无新增问题；独立设计评审第 1 轮修复多余 `Not run` 效果枚举，复评 S0=0、S1=0、未处理 S2=0。正式代码/证据评审第 1 轮发现当前 `UAT-K-EV-006/007` 仍只绑定 Summary V2 合同的一项 Major，已改为同时绑定 Summary V4 当前任务合同与共享 validator 反证；30 项定向复核通过，第 2 轮 Blocker=0、Major=0、Minor=0。

## 14. 当前结论

总计 50 个工作包。前 44 个工作包保持既有终态；阶段 A 新增 6 个语料工作包现均为 Done，`GATE-083/084` 已按 audit v3、Stage A corpus candidate-08/a5、14/14 UAT attempt-05 和三步 alias 演练证据关闭。Knowledge 效果 candidate-07 仍以 `failed_unconsumed` 形成终态，且没有创建 Knowledge 效果 candidate-08；Employee/Transaction 既有 35/35 不回退；Knowledge 最新有效效果等级仍为 `partially_effective`，当前 Rewrite V2 + Summary V4 效果证据为 `Evidence missing`，不得宣称已 effective。

## 15. 后续实施建议

Employee/Transaction 保持已完成。Knowledge 阶段 A 已完成 Audit、Design、Pipeline、Candidate Index、14 项专项 UAT 与受控发布；阶段 B 检索质量和图谱工作包继续阻塞，下一步只能先做阶段 B 设计/诊断，不得把阶段 B 调参反写为阶段 A 证据。

## 16. 当前非历史设计落实审计矩阵

本矩阵只审计当前权威文档；归档版、历史 candidate 正文和默认 skip 的 live 测试不作为当前实现依据。状态枚举固定为 `Implemented and verified`、`Implemented but effectiveness below target`、`Designed but not implemented`、`Evidence missing`、`Not applicable`、`Blocked by out-of-scope dependency`。

| 权威文档/要求 | 代码或配置实现 | 单元/契约/集成验证 | UAT/evidence | 当前状态 | 缺口与处置 |
|---|---|---|---|---|---|
| `REQ_00 v2.3` 查询、安全、功能/效果分离、Employee 自然语言扩展与 Knowledge 阶段 A 语料需求 | 在线查询和阶段 A 离线处理均已实施 | 在线定向、契约、E2E、类型、Java与隔离回归，以及阶段 A 工具/数据测试通过 | 既有 Business/Knowledge 功能 UAT；阶段 A 14/14 | Implemented and verified | 阶段 B 检索质量与图谱仍按 ROADMAP 独立治理 |
| `L0_00 v2.8` 系统边界、唯一在线链路与离线 Corpus Build Plane | Spring 接入、统一 Runtime、业务 Adapter、typed Knowledge Provider 和离线 Plane 已实施 | 在线 Spring→Runtime E2E 与隔离反证；离线候选/发布/回滚验证通过 | 两份现有 UAT；阶段 A 14/14 | Implemented and verified | 在线基线无缺口；离线与在线仍只在只读 alias/Profile 交汇 |
| `L1_00 v3.4` Core/Model/Registry/生命周期 | Runtime、姓名/姓氏强提示准入及显式字段完整性已实施 | Core、组合根、候选闸门与失败映射测试通过 | 扩展15类Passed | Implemented and verified | 不允许本地生成计划或近似字段替换 |
| `L1_01 v1.15` `KQ-AD-001～011` | 在线 `knowledge/` 与离线 Corpus Build Plane 已实施 | Knowledge unit/contract/integration/evaluation、Spring E2E、阶段 A parser/index/release 验证通过 | Functional 37/37；最新有效 Effectiveness=`partially_effective`；阶段 A 14/14 | Implemented and verified | 当前效果风险保持；本阶段未调阶段 B |
| `L1_02 v2.8` Business 三动作与最终授权 | 三动作、授权、多值/组合/region已实施 | Business/Employee contract、E2E、权限防回退通过 | 既有35/35；扩展15类Passed | Implemented and verified | 未修改公共DTO/endpoint |
| `L2_00_00 v1.3` `DR-ACCESS-001～009` | `agent-service`、`runtime_http.py`、`main.build_runtime` | Agent access/runtime/Spring E2E | 公共接入与两类领域 UAT | Implemented and verified | 无目标内缺口 |
| `L2_00_01 v2.3` `DR-CORE-101～104` | `core/`、`graph/business_query_planning.py`、Registry/组合根 | Core、QueryPlan、单动作、失败关闭测试 | Business/Knowledge E2E | Implemented and verified | 无目标内缺口 |
| `L2_00_02 v2.7` `DR-MODEL-101～109` | v7显式字段完整性与v6裸slot合同已实施并由生产组合根唯一绑定 | v5/v6历史合同与v7字段完整性合同通过 | candidate-04代表性13/13通过 | Implemented and verified | v4～v6及candidate-01～03历史证据不可变 |
| `L2_00_03 v1.3` `DR-AUTH-001～007` | `common-security` Authority Converter 与各 Provider 安全配置 | Servlet/Reactive converter、角色矩阵及兼容测试 | Business/Knowledge 权限场景 | Implemented and verified | 无目标内缺口 |
| `L2_01_00 v1.15` `DR-KFLOW-001～015` | 在线 Flow/Rewrite V2/生产惰性装配已实施并绑定已发布只读快照 | Rewrite V2、Flow、settings/catalog、production wiring、Spring E2E | Functional 37/37；阶段 A 快照消费验证通过 | Implemented and verified | 阶段 A 未修改域选择/Rewrite/排序 |
| `L2_01_01 v2.5` `DR-KRET-001～012` | Python retrieval/clients 与 `es-query-service` typed endpoint/Profile/security | Retrieval unit/contract/integration 与 Java DTO/security/endpoint 测试 | 功能检索用例 | Implemented and verified | 在线合同无目标内缺口 |
| `L2_01_01 v2.5` `DR-KRET-013～026` | `knowledge-corpus-tools`、candidate mapping/index、release tooling 已实施 | `TEST-KRET-010～021`、strict Schema、typed retrieval 与回滚演练通过 | 阶段 A 14/14 | Implemented and verified | 发布目标为 a5；a1～a4 保持且不删除 |
| `L2_01_02 v1.16` `DR-KEV-001～009/016～018` | Evidence/Policy、Summary V4、validator、效果口径 v2 | Evidence/summary/effect metric、安全与 E2E 测试 | Functional 37/37 | Implemented and verified | 在线基线无缺口 |
| `L2_01_02 v1.16` `DR-KEV-010～015/019～022` | P5 runner、冻结合同、状态 allowlist、candidate-07 preflight/history 修复 | preparation/history/schema/budget/failure-close 测试 | candidate-07=`invalid_run / failed_unconsumed`；最新有效为 partial | Evidence missing | 当前 V4 没有有效效果测量；不创建效果 candidate-08 |
| `L2_01_02 v1.16` `DR-KEV-023～025` | policy catalog v2/current loader 与 candidate 全成员策略校验已实施 | `TEST-KEV-016`、5600 文档 full-membership 与旧目录 hash 通过 | 阶段 A Evidence UAT Passed | Implemented and verified | catalog v1 与历史 evidence 保持不变 |
| `L2_02_00 v2.8` `DR-BQCOM-101～111` | v3/value_refs/组合/region已实施 | Business unit/contract/E2E通过 | 扩展15类Passed | Implemented and verified | v2配置与历史证据不可变 |
| `L2_02_01 v2.8` `DR-EMP-101～111` | 多值extractor/mapper及既有两动作已实施 | Adapter/codec/fake server通过 | Employee扩展15类Passed | Implemented and verified | 只调用现有search endpoint |
| `L2_02_02 v2.6` `DR-TXN-101～105` | `transaction.search`、Date/Decimal/page/sort、Java guard | Python/Java/cross-language/frozen-host tests | Transaction UAT | Implemented and verified | 无目标内缺口 |
| `UAT_00 v1.24` 35 个固定 Business case 与15项扩展 | 既有35项实现/证据不变；扩展实现完成 | 扩展non-live与组合证据校验通过 | 35/35既有Passed；扩展15类Passed | Implemented and verified | candidate-01～03失败不改写；candidate-04为最终有效代表性运行 |
| `UAT_01 v1.19` Functional | 当前 Knowledge 生产对象图 | 37 项逐 case trace、Rewrite V2 合同、Spring E2E、Java/Python 契约 | 37/37 Passed | Implemented and verified | 无目标内缺口 |
| `UAT_01 v1.19` Effectiveness | P5 v2 metric、当前 Rewrite V2 + Summary V4、版本化 candidate runner | non-live、历史哈希、安全 Gate、candidate-07 history 与 traceability schema v2 | 当前 candidate-07 无效；最新有效 partial | Evidence missing | 当前任务组合未形成有效测量；作为显式剩余风险，不阻塞阶段 A |
| `UAT_01 v1.19` 阶段 A | 正文/附件/表格/OCR/时效/授权/Evidence 14 类专项 | 流水线、candidate 与 typed retrieval 已验证 | `UAT-KCORPUS-A-01～14` 14/14 Passed | Implemented and verified | attempt-05 为最终证据；阶段 B 四项发现独立记录，不影响阶段 A |
| `P3_00 v2.41` 工作包、Gate 与阶段 A | 既有工作包及阶段 A 6 包均闭合 | `GATE-080/081/082/083/084` Closed | 既有 UAT 不回退；阶段 A 14/14 | Implemented and verified | 禁止额外模型调用、阶段 B 调参或新效果候选 |
| `ARCHITECTURE.md` 权威索引 | 不对应生产实现 | 链接、版本与状态校验 | 引用 P3/UAT 高层状态 | Not applicable | 索引不复制运行流水或动态测试总数 |

## 17. Employee 自然语言扩展工作包（v2.33）

本节只扩展现有 `employee.search` 的规划表达力，不新增动作、服务接口或权限。三个方案已比较：Prompt-only 缺少合同闭环；validator-only 会造成语义和安全边界失控；采用 typed multi-value + v3 catalog/config + code/config 双重校验。v6 澄清模型序列化，v7 只强化显式字段不可替换/丢弃的通用完整性，不新增业务能力。

| 顺序 | 工作包 | 直接依赖 | Gate | 初始状态 | 完成证据 |
|---:|---|---|---|---|---|
| 39 | `WP-EMP-NL-DESIGN-10` | 当前 REQ/L1/L2 与已核实 Java search 合同 | `GATE-080` | Done | 三轮内审、独立跨层评审，S0/S1/未处理S2均为0 |
| 40 | `WP-BQ-MULTIVALUE-CONTRACT-10` | `WP-EMP-NL-DESIGN-10` | `GATE-080` Closed | Done | v3 config、`value_refs`、operator shape、组合、region profile、v5 catalog/task 单元和契约测试 |
| 41 | `WP-EMP-NL-QUERY-10` | `WP-BQ-MULTIVALUE-CONTRACT-10` | `GATE-081` Closed | Done | extractor、binder、Employee mapper/fake server、Spring E2E、零泄漏与正式隔离全量 non-live |
| 42 | `WP-EMP-NL-UAT-10` | `WP-EMP-NL-QUERY-10` | `GATE-082` | Done | candidate-04代表性13/13通过；结合candidate-03不可变302/307覆盖15类；累计模型30、Employee27，安全计数为0 |
| 43 | `WP-EMP-NL-CLOSURE-10` | `WP-EMP-NL-UAT-10` | `GATE-082` Closed | Done | 历史哈希、组合覆盖、全量验证、正式代码评审、文档/UAT状态与Git交付收口 |

`GATE-080` 只判定方案和设计可实施；`GATE-081` 只判定 non-live 合同与回归；`GATE-082` 是一次性 UAT 预算与执行门。任一 Gate 失败先区分实现、测试、环境、数据或设计，不得放宽 validator、修改历史 evidence 或增加未冻结调用。工作包 DAG 为线性直接依赖，无反向以 UAT 证明设计、无循环。

设计评审记录：第1轮内审修复 P3/索引旧版本引用及 v4/v5 目标混淆；第2轮补齐 typed logical field 与 current-request slot 绑定；第3轮核实唯一链路、行政区有限目录、服务能力交集、权限/出域、历史兼容和 DAG。独立分层及跨层评审复核 Java `SearchFilter.values`/`anyFilterClause`/`bool.must` 证据，结论 S0=0、S1=0、未处理S2=0，`GATE-080` Closed。

candidate-02 后续设计复核：第1轮确认失败发生在 provider 返回之后、Adapter 之前且结构语义正确；第2轮确认不能以本地 wrapper 归一化、validator 放宽或补跑关闭；第3轮补齐裸 slot、全量相关 slot、禁止 wrapper/未知/重复 slot 和有限诊断。独立复评结论：v6 Prompt 最小修订，S0=0、S1=0、未处理S2=0；Business strict decoder/validator/binder、Employee DTO及endpoint均无需修改。

candidate-03 后续设计复核：第1轮确认失败是模型把显式 `workBaseSi` 请求替换为合法 `contact_address`，因此通用字段 validator 无法识别已丢失的原始约束；第2轮排除 workBase 专用黑名单、本地技术字段解析、validator 放宽和单例补跑，采用通用“显式字段不可替换/丢弃”Prompt；第3轮核实 candidate-04 只复跑13项代表性集合，结合 candidate-03不可变前13项覆盖全部15类场景，并把总累计预算锁定为模型30、Employee不超过30。独立复评结论：v7 Prompt与 UAT unsupported 判定为最小闭环，S0=0、S1=0、未处理S2=0；公共合同、Employee DTO/endpoint、权限和通用 validator 均无需修改。

### 17.1 目标内实施映射

| 来源 | 实施 | 测试/UAT |
|---|---|---|
| `REQ-BQS-002/004/011/012` | `BusinessQueryOperator`、exact decoder/validator/binder、v3 settings、region catalog | `TEST-BQCOM-109/110`；`UAT-EMP-NL-301～315` |
| `DR-MODEL-106～109` | `business_query_plan_v7.py`、planner catalog、bootstrap 当前版本切换 | v6裸slot历史合同、v7显式字段完整性、有限诊断；真实 QueryPlan 总预算 |
| `DR-EMP-109～111` | Employee extractor、argument validator、request mapper | `TEST-EMP-110/111`；只读 Employee search 预算 |

### 17.2 关闭条件

`GATE-080/081` 分别由设计评审与non-live合同/回归关闭。`GATE-082` 的candidate-04冻结HEAD=`0fef025815c210a8ea3bfc2e64ed7451bee829ad`、manifest SHA-256=`e6c908503aa4f9544c6fea6e32e072ac76708ef6401cc46d32b61c513fefb19c`、task=`business-query-plan-v7`、Prompt SHA-256=`ecedafdfddeb0582b0cacfeefd9b5113b6f4e6173e4a60f841367c8305280f47`。13/13代表性用例通过，模型12、Employee11；candidate-03不可变302/307补足复姓与地区别名，15类均通过。四候选累计模型30、Employee27，无补跑、retry/resume、其他endpoint或泄漏，故 `GATE-082` Closed。

### 17.3 最终验证与代码评审

本轮正式隔离回归先完成 Transaction host/preflight 14/14，再完成全量 non-live 1541 passed、27 opt-in skipped、0 failed；Employee自然语言定向/追踪集合27 passed，strict mypy对9个目标文件无问题，compileall及candidate-04 launcher PowerShell AST通过。Java实际结果为employee-service 50 tests/20 opt-in skipped、agent-service 42 tests/3 opt-in skipped，均为0 failure/0 error。L1/L2/P3 strict文档校验、candidate-04精确哈希、历史组合覆盖、敏感扫描和Git差异检查通过。

正式代码对照设计评审第1轮结论为Blocker=0、Major=0。唯一低风险观察是v6/v7继承Prompt允许“问题明确要求时在另一filter复用slot”，而当前request binder始终拒绝跨filter重复slot；该差异只会使这类边缘计划额外失败关闭，不能造成敏感值泄漏或越权业务调用，且不影响本轮15类UAT。由于v7源码及Prompt已被candidate-04冻结、总模型预算已经恰好用尽，本轮接受该低风险兼容差异，不改写历史任务或创建新候选；如未来明确需要同一protected value跨filter复用，应以新任务版本和独立授权处理。复评结论Blocker=0、Major=0，未接受其他问题。

## 18. Knowledge Rewrite 精确输出合同与验证台展示（v2.34）

| 顺序 | 工作包 | 直接依赖 | Gate | 状态 | 完成证据 |
|---:|---|---|---|---|---|
| 44 | `WP-K-REWRITE-SCHEMA-11` | `L1_01 v1.10`、`L2_01_00 v1.11`、`UAT_01 v1.13` | 无新增 Gate | Done | Rewrite V2 精确 JSON 合同、生产任务版本单绑定、V1 历史隔离、页面安全投影与加工后文本合同测试；真实模型调用为0 |

该修复只解决模型请求合同未显式描述本地严格 decoder 的缺口：V2 明确唯一 `candidates` 字段、1..`max_candidates` 数量、字符串边界、语义保持和禁止直接回答；本地 parser、Question Guard、候选语义校验和原问题 fallback 不放宽。验证台只从最终受控响应的 `result.answerSummary` 显示 Knowledge 加工后文本，并继续保留完整结构化结果；不新增模型调用、后端 DTO 或敏感正文诊断字段。Rewrite V1、历史 candidate 和效果结论保持不可变，当前 Rewrite V2 + Summary V4 组合的效果证据仍为 `Evidence missing`。

## 19. Knowledge 阶段 A 语料完整性实施与收口（v2.41）

### 19.1 只读事实与精确目标

| 项目 | 冻结值 |
|---|---|
| 起始 Git HEAD | `ffba329404db13a49143c32b5c123ecfa9745536` |
| 当前只读 alias | `agent-doc-tax-policy-v2-read` |
| 阶段 A 起始目标 | `agent-doc-tax-policy-v3-20260803-agent-read-v1`；UUID=`k97bn1gxROSfVm7zGfzbOg`，14783 chunk、5596 document |
| 最终发布目标 | `agent-doc-tax-policy-v4-20260903-corpus-a5`；UUID=`SurWRSglRd6ZRddEBWy2Sw`，15521 chunk、5600 document |
| 阶段 A 外部 workspace | `D:\codex-data\knowledge-corpus-stage-a`，所有有状态命令必须显式传入该绝对路径 |
| 初始候选索引 | `agent-doc-tax-policy-v4-20260902-corpus-a1`；构建后因来源资产集合发生变化而保持未发布 |
| 早期/中间候选 | a1/a2/a3/a4 均保留且不删除；最终发布演练前精确 alias 目标为 a4，UUID=`mru7T8URQtOcUCVeG7ZAPw` |
| 最终候选/发布索引 | `agent-doc-tax-policy-v4-20260903-corpus-a5`；UUID=`SurWRSglRd6ZRddEBWy2Sw` |
| 候选 mapping version | `agent-knowledge-tax-v2-corpus-a1` |
| 本次 alias 回滚目标 | a4 及其 UUID；阶段 A 起始索引和 a1～a4 均不删除 |

### 19.2 工具链与操作预算

工具版本固定为 Python 3.12.4、Elasticsearch 9.4.1、`httpx==0.28.1`、`pydantic==2.13.5`、`beautifulsoup4==4.15.0`、`pypdf==6.16.2`、`python-docx==1.2.0`、`openpyxl==3.1.5`、`xlrd==2.0.2`、`legacy-doc==0.2.1`、`Pillow==12.3.0`、`PyMuPDF==1.28.2`、`rapidocr==3.9.2`、`onnxruntime==1.29.0`。依赖仅安装到阶段 A 外部 workspace 的隔离虚拟环境，不增加在线生产依赖。

| 操作 | 硬上限 | 失败/重试语义 |
|---|---:|---|
| 当前 ES audit page | 800 requests | 每页最多1000；失败停止，不重试 |
| 官方 parent page GET | 每个审计 run 必须等于“当前唯一规范 URL 数 + 明确种子数”，且在首请求前冻结；审计 v1 为5597 | 每个规范 URL 至多1次，重定向最多3跳且逐跳复核；种子必须计入预算 |
| 官方 attachment GET | 4096 requests | 每个规范最终 URL 至多1次；单资产≤50 MiB |
| 原始资产总量 | 20 GiB | 超界停止新增下载，保留有限清单 |
| 解析/OCR | 每个已下载 asset 至多1次 | 失败 quarantine，不重试、不索引 |
| BGE embedding | 最多100000 texts / 3125 batch requests | batch≤32；失败 chunk 不写入，不重试 |
| Candidate index create/reindex | 1 / 1 | 已存在、目标不精确或指向当前目标即停止 |
| 新增 candidate chunk | 100000 | bulk item 冲突或部分失败即停止发布 |
| Alias update | 最多3次 | 演练切候选→回旧目标→最终切候选；每次原子且验证精确前置 |
| 真实模型 outbound | 0 | 禁止读取 `LLM_API_KEY` |

### 19.3 入口门禁闭合条件

`GATE-083` 与 `GATE-KRG-001` 表示同一个阶段 A 入口门：只读审计已建立当前索引/策略文档/官方来源/P0-P2基线；REQ/L1/L2/P3/UAT/ROADMAP 三轮内审和独立评审通过；外部 workspace、工具版本、上述硬预算、精确候选名与回滚目标均已冻结。audit v3 strict 结果和工具就绪证据满足条件后该门已关闭；alias 生效仍由 `GATE-084/GATE-KRG-002` 独立控制。

审计 v1 已只读盘点 5596 个当前文档并额外加入 1 个 P0 官方种子，总计 5597 行，ES 写入为0、retry=0；但父页面预算错误冻结为5596而实际发起5597次，且把5577个 `http_non_200/url_missing` 与正文完整性混为同一失败维度，P0又由宽泛标题关键字产生74条。该运行保留为不可改写的失败基线，SHA-256=`d9d357f7f91d00d210895a015f49dce1e122ee84336071091f8aad46a0a8eedc`，不得据此宣称5574篇正文缺失，也不得自动重试。

最终 audit v3 按库存/可达性/完整性三层事实验证 5597 项：P0=3、P1=0、P2=5594，来源 `ok=20/source_unreachable=5574/url_missing=3`，完整性 `verified_complete=19/verified_gap=1/not_assessable=5577`，source GET=5594/5597、ES写入=0、retry=0；JSONL SHA-256=`ccdbfbe9983925f937421f31e0717387368416389c636a752544b3c2a506d272`。P0 的 3 个审计项对应 2 份逻辑来源文档：财税〔2016〕36号在现行索引和外部种子中各有一个稳定标识，另 1 项为现行增值税法；不得把稳定标识数误报为 3 份独立来源。P1=0 表示本轮人工目标 P1 清单无已确认缺口，不外推为所有不可达页面完整。

### 19.4 初始 P0 证据缺口

旧索引已包含 2026-01-01 生效的《中华人民共和国增值税法》及一般服务 6% 税率原文，但不能稳定直接检索到“住宿服务”的服务分类原文。P0 采用版本化人工清单，不以“营改增/增值税法”等标题关键字自动扩成74条。阶段 A 已从财政部、国家税务总局财税〔2016〕36号官方主页面取得4个官方附件并形成5个不可变 asset；其中来源扩展名与真实 OLE 格式不一致的两个 `.docx` 按实际 `.doc` 解析并保留 `format_mismatch`。结构化解析形成749个有序block、738个新chunk和55个条款引用；本轮官方 P0 资产没有原生表格或扫描件，表格/OCR能力以受控 fixture 验证，不虚报 live 处理数量。直接 typed keyword/vector 已证明“住宿服务”分类与当前税率规则存在、可读、可检索和可引用。最终用户问句仍可能因域选择、Rewrite 或 ranking 未进入 topK，归入阶段 B。

### 19.5 设计评审结论

三轮内审中，第1轮修复来源可达性/正文缺失混淆、宽泛P0分级和种子预算少计；第2轮修复上位语料需求逐项追踪；第3轮复核官方替代来源、无第三方降级、候选零覆盖、入口/发布Gate和阶段B边界，无新增问题。独立评审首轮发现 Audit→Design 的直接依赖会使 strict audit tool 无法在设计完成后、Gate关闭前落地；已改为 Audit/Design 共同直接约束 Pipeline。复评结论 S0=0、S1=0、未处理S2=0。strict audit/tool readiness 随后通过，`WP-KCORPUS-DESIGN-01` 与 `WP-KCORPUS-AUDIT-01` 为 Done，`GATE-083` Closed。

### 19.6 候选、UAT 与发布终态

- Stage A corpus candidate-08 build manifest SHA-256=`6cc043633dce354b5b83aa0592e84db702484566d76def8fab84afea3c09ead6`；asset manifest SHA-256=`c64c1cc69636bdfad6dbca2e9f127f8ccd9855e3baeabf70a6bc5fdd0405d01c`；mapping SHA-256=`7b83f96b013c6f6cfa671f13488d45101d2273a048eac88cc764fcf218fb3cdf`；processing result SHA-256=`2e780aa33ccb83dec30d292087471d1d5ad5e52c253a019bcec27e123eefbbb0`。
- candidate a5 由阶段 A 起始索引 14783 chunk 加 738 个合格新 chunk 构成，共15521 chunk、5600个唯一document；附件父关系缺失=0、条款引用=55、空 content/embedding=0，candidate write block=true；规范化内容 fingerprint=`bb63efe76774b9c82226625b25a9fabfc0be3004d8a678e5a739020107bf943b`，构建记录的工具源码 SHA-256=`81deb7ba75959485b8035412910617ba4eb4bb05359a1563d7bf8df633d05368` 与最终源码复算一致。
- policy catalog v1 字节保持不变，SHA-256=`442761355510165265cb2eee3be8ee8a310c38ab7796a998ff1863073dbbd698`；catalog v2 的 Git/LF 分发字节 SHA-256=`76dcbfa6da01b76b431417e5b540f7a540fd9daa352a61c36d1bb9fdc31b2a9b`，其规范化内容与 candidate 5600 个 document full-membership 完全一致；a5 policy/law snapshot 分别为 `5e7323100b1bfd44e7452e3ce409ff146800961c07a077b2585b670665b03136` / `b537176bf80323178aaaa1ca328f1534641b62f2671d8aa2e136fcef63495104`，覆盖5463/137个document；a4 和更早 snapshot 仍保留。
- UAT attempt-01（SHA-256=`5659904b75a211ed6f046509783a53679af2bb499df590c4713f1fbc7c1fb21b`）原样保留；正式复核发现其 PDF 用例只引用 live manifest，时效和当前税法也没有在同次运行中直接断言，因此不得作为最终 14/14 权威证据。
- 最终 UAT attempt-05：run=`knowledge-corpus-stage-a-uat-v1-20260903-attempt-05`，14/14 Passed，有限结果 SHA-256=`ad86ae89b48e0c96426cbadddef526d391e6b61214a254bba90049286afc162a`；模型/Business调用均为0，并在同次运行验证738个附件chunk、55个条款引用、native PDF fixture、ACTIVE/EXPIRED、tax.law 当前税法、alias 精确绑定及酒店住宿两类直接原文。attempt-01/02/04 保持不变；attempt-03 因前序索引元数据仍指向初始基线而不作为最终发布追踪。
- 首次发布后的 UAT 使用最终用户问句做向量 top20 断言，目标附件位于 rank 59；工具立即把 alias 回滚至旧目标，回滚 evidence SHA-256=`39ec3e5fbadc8ce37ffe8537b883fc0f8a69032463eecf4112ec83d2b5290e31`。这证明阶段 B 改写/排序缺口，不证明语料缺失。
- 最终 release run=`knowledge-corpus-stage-a-release-v1-20260903-attempt-05`，journal SHA-256=`623438fbedf9ff83c57607fc3b16735576a79c9b6a382092ad7b55e248b6010e`；按 a4→a5→a4→a5 三次原子操作完成回滚演练，alias 最终精确指向 a5，阶段 A 起始索引和 a1～a4 候选均未修改、未删除。
- 本次最终验证实际结果：阶段 A 工具 30 passed；Knowledge/追踪定向集合 206 passed、6 个显式 live opt-in skipped；由干净 HEAD 创建正式隔离环境后，Transaction host/preflight 14/14，Runtime 全量 non-live 1532 passed、27 个显式 live opt-in skipped、0 failed；strict mypy 478 个 Runtime 源/测试文件与 13 个语料工具源码文件均通过，compileall 与 PowerShell AST 通过。Java reactor 为 common-security 21/0、employee-service 50/20 skipped、mq-procedure-service 51/2 skipped、es-query-service 43/0，agent-service 40/1 skipped，全部 0 failure/0 error；跳过项均为未获本阶段授权的历史或真实 live 用例。
- `WP-KCORPUS-PIPELINE-01`、`WP-KCORPUS-INDEX-01`、`WP-KCORPUS-UAT-01`、`WP-KCORPUS-RELEASE-01` 均为 Done；`GATE-084/GATE-KRG-002` Closed。

### 19.7 正式代码、数据与索引复评

早期复评已修复 UAT 证据映射与严格合同。后续正式评审先发现一项 Major：4个官方legacy DOC被整体扁平化、候选条款引用为0；最小修复引入结构化纯文本解析并形成 a4。随后修复 attempt-03 的 `old_index` 有限元数据漂移。最终轮代码/数据评审又发现单资产网络异常会逃逸并中止整批处理、损坏 Office/PDF 容器异常没有统一形成有限失败，以及 a4 构建源码哈希早于这些修复；最小修复异常隔离测试后，以最终源码重建内容等价的 a5，不覆盖 a1～a4。clean-checkout 复评进一步发现 catalog 哈希受工作树 CRLF 影响、评估候选依赖被忽略的 provenance 输入、历史 Transaction 授权哈希依赖旧换行表示；现已改为绑定 Git 分发字节、提交精确只读 provenance 镜像，并仅在临时历史验证目录复原已授权字节。UAT attempt-05、Profile/catalog快照、三步发布回滚、正式隔离全量回归均通过；最终复评 Blocker=0、Major=0、Minor=0，在线算法、公共接口、授权与历史资产均未改变。

### 19.8 阶段 B 独立输入

用户问句“酒店行业的住宿费用，适用哪种税率”仍可能因 `domain_selection/query_rewrite/ranking/failure_semantics` 无法把已存在的直接原文送入最终 topK。阶段 A 不修改 Domain、Rewrite、RRF、rerank、topK、Prompt 或 fallback；后续应先按 `GATE-KRG-006` 完成阶段 B 只读诊断与设计评审。

## 20. 阶段 B：根因、实现入口与有限验收

### 20.1 当前基线与根因矩阵

起始分支 codex，HEAD `09eb9e26b2569990b92371d61e2728a72949e579`，与 origin/codex 一致且工作树干净。阶段 A 当前 alias/UUID 经只读核实不变。十组诊断使用生产 Adapter 和同一 corpus-a5 快照，但有意同时探测两域；它不是当前生产域选择结果，也不是端到端 UAT。有限 evidence：`agent-runtime/tests/system_e2e/knowledge_stage_b_diagnosis.v1.jsonl`，SHA-256=`daca09f544ff7a88d1a8386dfcc749b26fe017dc03e7323ce15237e6732f1bc7`。

| 问题/环节 | 实证 | 证据强度 | 最小处理 |
|---|---|---|---|
| 向量窗口 | limit=20、k=21，但 Java vector body 无 size；十组两域均只返回10且 truncated=false | 代码+同快照实际响应，强 | 补已有合同的 size=limit+1，不加 topK |
| 酒店原问域选择 | 本地 selector 仅 policy；离线 law 路径存在税法直接条款 | 单测反例+路径证据，强 | V3 一次性语义域计划，禁止失败扩域 |
| 改写条件 | 现 guard 接受小规模/简易计税丢失和住宿改成货物的反例 | 可复现反例，强；一般语义保持不可由正则完备证明 | exact V3、显式条件守卫、原问题摘要边界及人工 UAT |
| 分类 Evidence 丢失 | “住宿服务增值税税率”分类 keyword第2→融合第5→重排第18→未入 Evidence；“一般纳税人…”keyword第1→重排第19→未入 | 同快照有限排名，强 | 域内 rerank，保留各域 keyword/语义首位锚点；有界 Evidence |
| 检索词差异 | “住宿服务生活服务”分类融合第1/重排第2并入选；原问没有召回分类附件 | 受控离线词变体，强；不能据此断言端到端已修复 | 每域一个受原问题约束的检索表达 |
| 无结果文案折叠 | no_candidate 和 insufficient_evidence 均显示同一句无结果；覆盖不足可能转 internal_failure | 代码证据，强 | 现有状态+有限 reason，固定文案区分 |
| 冷态 rerank | 首次56候选5秒超时；随后独立校准1.265秒及十组通过 | 一次冷态事件，中 | 保留5秒硬界，非 live 检查就绪；不凭单次超时放宽 |
| 时效/语料缺口 | 写作日期不能证明适用期，content flags 不能充当法律 gold | 限制明确 | 人工核对适用条款；新缺口记阶段 A 维护，不改正文/索引 |

诊断累计本地调用：embedding22、search88、rerank12、外部模型0；含首个失败探针、仅路径对照、单次校准和完整十组。auth/es 隔离进程均按持有的子进程句柄停止，临时原始日志已删除。有限基线文件不可覆盖。Knowledge 定向 source-tree 验证需进程级 PYTHONPATH：160 passed/6 opt-in skipped；正式全量仍须隔离安装入口，不能把源码树未安装导致的 collection error 视为产品失败。

### 20.2 方案和控制

采用 L1_01 §4.5、L2_01_00 §8/10.1、L2_01_01 §8.4/9.3、L2_01_02 §7.3 的最小组合；Summary V4、RRF k=60、per-path20、final20、Evidence8/质量策略每文档3（legacy2）/32768字节、公共 DTO 和阶段 A 索引均不扩张。V1/V2任务和历史资产保持字节不变。生产使用新 V3 一次计划与域内排序版本；历史调用默认维持原合同。

授权总计最多20个真实端到端请求、60次外部模型 HTTP；包含 selection/rewrite/summary，自动 retry/resume=0。先冻结当前 commit、Prompt、配置、索引、case/gold 和各调用预算；不触及全局环境，不在准备阶段读取 LLM_API_KEY。失败即停止该真实批次，后续只能做 fake 修复，不补跑或新增付费候选。核心 P0 未通过则本包不标 Done。

### 20.3 评审与实施状态

本节记录本轮设计评审过程；最终结论以末尾复评及主表为准。初稿时GATE-KRG-006为Open、生产代码未修改，所有本轮验证不得继承历史Passed。

| 内审 | 实际检查与发现 | 本轮修复 |
|---|---|---|
| B-IR-1 | 职责/唯一链路/原问/域计划；发现路线图授权在rerank之后、模糊酒店问题例子加入纳税人类型、阶段B退出错误依赖图谱 | 授权前移、例子仅检索表达、阶段B独立UAT；原问边界和新任务无fallback明确 |
| B-IR-2 | Python/Java/公开响应/安全；发现不同域query的BGE分数不可直接比较、模型query还需安全复核、同identity跨域计数含糊、锚点与final容量冲突 | 域内rerank+rank轮转、重验QuestionGuard、80为路径候选总界、启动final≥2×域数；固定reason不改公开DTO |
| B-IR-3 | DAG/预算/回滚/可验证性；P3 strict无环通过；L2 strict报告增量追踪缺来源/设计列及草案readiness用词不明确 | 补来源/设计列与“否，草案”判定；冻结前人工gold、20/60含selection、失败不补跑、历史/索引保护及冷态风险明确 |

三轮内审结束时，独立设计评审尚未作出通过结论。一般自然语言等价和实际效力无法靠字符串guard证明，属于专项UAT必须验证的限制，不作为已完成能力声明。

独立只读评审首轮冻结发现：B-DR-001（S1，L2_01_00 §9.3）coverage并集漏列no_result，合法零命中路径会被误判协议损坏；修复为三集合精确且互斥。B-DR-002（S2，L2_01_00 §17）历史禁止真实调用文字与本轮有限授权冲突；限定为未冻结/超预算调用。B-DR-003（S2，ARCHITECTURE）新草案版本仍带旧Approved；同步索引与本轮实际评审状态。评审阶段只读，以上修改在另行切回已授权文档修订阶段完成。

独立复评 B-DR-R2：重新只读核对上述三项与完整层级/跨层 rubric，coverage三集合、已有公开结果对象及固定文案、受控域/预算/授权/历史边界和阶段B独立DAG一致；S0=0、S1=0、未处理S2=0，通过阶段B实施入口。L1两份、L2三份及P3严格校验通过。此为独立于编辑阶段的自动化辅助评审，不冒充外部人工审批。GATE-KRG-006关闭，Design=Done、Implement=Ready；生产代码和真实UAT仍未完成。ARCHITECTURE与metadata按本复评结论同步，不将设计Approved等同Implemented。

### 20.4 实施中发现的设计校准（零付费）

补充v5使用通过QuestionEgressGuard的税务表达并验证串行实现：search12/embedding6/rerank6/model0，所有HTTP200；但住宿定义最终rank9/16未入Evidence，一般纳税人表达中未进final20。因此sufficient仅为结构充分，不能算核心P0通过，暂不启动paid UAT。有限语义域query与人工原文根因对照仍需继续。

后续排序增量IR5-1核对v5与旧诊断，确认keyword高位在rerank填充中再次丢失；仅扩大配额不能修复，选择既有keyword/rerank序列交错而不是扩大topK。IR5-2核对身份/授权/跨域，补充跳过重复锚点后每域真正输出一项、无keyword时用rerank，不以重复项消耗另一域名额。IR5-3检查根因到测试/预算/DAG及strict：最多4锚点、20候选、8 Evidence、现有HTTP上限不变；未调整数据/gold/权限。独立只读DR5-R1发现§9.3旧句仍称仅rerank填充（S2），在修订阶段同步为交错规则；DR5-R2只读复核精确序列、空路、去重、tie-break、跨域与配额边界，S0/S1/未处理S2=0，允许实施该增量。此自动化辅助评审与编辑阶段分离，不冒充外部人工审批。

有限只读对照资产为 tests/system_e2e/knowledge_stage_b_local_validation.v1～v4.jsonl：v1启动未完成且原因尚不能确定；v2/v3跨域并发rerank出现HTTP500；v4仅串行化同一批域请求后四组全部完成，search12/embedding6/rerank6/model0。当前累计诊断调用search110/embedding33/rerank23/外部模型0；所有本次隔离进程停止、原始临时日志删除，Stage A索引/alias未修改。

| 新发现 | 证据与强度 | 最小处理及限制 |
|---|---|---|
| 同请求两个域的BGE并发请求失败 | v3的两域search均200，rerank500；v4同输入串行后均200；强关联，BGE内部原因未证实 | 请求内域序串行，不新增重试/延长deadline/修改BGE；跨请求负载仍可能失败，保持失败关闭 |
| 第三条必要定义被同文档配额排除 | 分类query的最终rank1/2/3同属一个附件；原文核对rank1为其他生活服务排除定义、rank2为生活服务总类、rank3为住宿服务定义；perdoc3离线对照入选 | 新质量策略每文档3条，legacy2；总8/32768字节不变；不增加topK，不使用文档ID/gold在线加分 |
| 泛化主题被误当成每域必须重复的取值约束 | 现行新Prompt要求所有query都含税率类主题，阻碍分类query和法定规则query独立聚焦；设计/代码静态证据，尚无真实模型证明 | 无具体百分数的主题整组保持，数值/否定/主体条件仍逐域；百分数存在时主题也逐域保持，不本地生成query |

本轮只读人工核对的公开附件片段：生活服务总类hash=6b845e33a7a53777961b871707601c8dec674cc8e7243a0a823ae2fd80a28d2a；住宿服务定义hash=f75587a18625412be4019c6f534ecf6ddfe133fd968984ce75406200cb77ebde；其他生活服务定义hash=42a09a564fac1ba06b81b275cbd20ef3a9f353c42e43d47134e0a2022d04e647。只作诊断与预冻结gold溯源，不把hash或case特判带入生产排序。

增量内审第1轮（B-IR4-1）：检查域query与原问题职责，发现无数值主题分配规则可能误用于具体税率，补充百分数存在时逐域保留；未触及公共DTO、原文或权限。
增量内审第2轮（B-IR4-2）：检查跨语言/授权/配额和历史兼容，明确新limits只由生产根注入、legacy v1保持两条；总输入/输出及三层权限不变；串行排队不得越过deadline。对应测试必须覆盖第三条、第四条拒绝及取消后不调用后一域。
增量内审第3轮（B-IR4-3）：P3 strict实际发现六个阶段B工作包未同步到Ready/交接/追踪三张表，补齐后errors=0/warnings=0；纠正此前笼统“strict通过”表述，以本次输出为准。L2 strict发现页首与尾部状态不同步，已修正草案状态；UAT旧条件fallback预期改为当前V3零下游。预算、DAG、legacy和索引回滚边界复核完成。

增量独立只读评审B-DR4-R1：范围L1_01及三份L2增量、P3/UAT/索引，依据REQ-KQUALITY与现有公共/策略合同；发现B-DR4-001（S2，L2_01_00 §8）比例判定未包括中文百分之及千分比记号，会使具体比例主题被错误分配。切回文档修订后补齐有限记号及对应测试要求。B-DR4-R2重新只读核查：比例/否定等原约束不弱化、质量配额不扩大可读/可出域集合、两域串行不增加调用和时限、旧limits/task隔离及工作包无环均闭合；S0=0、S1=0、未处理S2=0，增量允许实施，真实UAT仍未完成。此为与编辑阶段分离的自动化辅助复评，不代表外部人工审批。


### 20.5 实施与预 UAT non-live 验证（2026-09-04）

此前§15～19为阶段A收口时点记录；当前阶段B状态以本节最新执行记录及工作包表为准。总计56个工作包；IMPLEMENT/NONLIVE为Done仅表示批准方案已编码和非live验证完成，不表示语义效果达标。§20.6旧批首例失败，§20.11独立新批首例通过但第二例失败；UAT为Deferred（失败停止，不续用本批预算），QUALITY为Blocked，完整核心P0和整体正式评审仍未闭合，不能宣称阶段B完成。Deferred不是通过或豁免：现有工作包状态枚举不含Failed，运行结果仍准确为failed；不为匹配校验器而新增重复门禁或伪造未完成前置。

- 实现落点：`rewrite_v3.py`/`semantic_planner.py` 精确语义计划；`retrieval/quality_ranking.py` 域内串行排序、keyword/BGE锚点及交错填充；`evidence/builder.py` 必要锚点和有界选择；`capability.py` 路径coverage及有限失败原因；`bootstrap.py`/`main.py` 唯一V3/V4生产绑定；Java `KnowledgeSearchService` 修复vector顶层size缺省10的问题，公共DTO不变。
- 预UAT时正式隔离命令 `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1`：host/preflight 14 passed；全量1622 passed/27 opt-in skipped/0 failed，1条现有LangGraph依赖弃用预告。其后新增6项coverage测试，首次因fixture缺少require_semantic_plan失败，修正fixture后6 passed，未弱化断言或生产验证；最终全量结果见§20.7。
- strict mypy：122个生产模块通过；compileall通过。agent-service Maven终端本次40 tests/0 failure/1 skip；旧XML会累积，不冒充42项本次执行。相关reactor成功：common-security21/0skip，es-query-service43/0skip，Employee50/20skip，Transaction37/2skip；角色、公共接入、当前Spring→Runtime Business/Knowledge E2E及合同保持通过。
- 零外部模型诊断至v7累计search136/embedding46/rerank36。v7聚焦分类query在相同a5快照下使住宿定义与生活服务总类同时进入Evidence；同文档legacy2对照仍缺一条。v5/v6泛化query仍不能保证必要条款，不能把结构性sufficient冒充P0达标。
- 预UAT复核关闭：coverage路径集合遗漏测试、当前traceability authority、Summary V4真实请求投影识别和Spring unsupported=422的准备错误。历史任务/语料/alias不变。完整正式代码评审在专项UAT后执行，当前结论仅为可冻结实施基线。

### 20.6 一次真实专项 UAT 终态（2026-09-04）

本节取代§20.5的“准备”时点，不改写历史P5或阶段A结果。冻结HEAD=`338b387100f03f4153611b2324604c8e25466a2b`，run=`knowledge-stage-b-uat-v1-20260904-run-01`，reference=`P3_00:WP-KRETRIEVAL-UAT-01`。预算收紧为10端到端/30模型/40search/20embedding/20rerank；Business、retry、resume为0。

| 有限资产（`agent-runtime/tests/system_e2e/knowledge_stage_b_run_01/`） | SHA-256 |
|---|---|
| manifest.json | ee56673a262894a135379ae50d1d0e32d4cf3fe1051d6b8b40a55ab8da08a675 |
| consumed.json | 6a07070209e331d1cab326ffa907136a5cbeed65df84d165b2f3ef9de61b4f8d |
| journal.jsonl | 780335f53c910e84980cf479076de6bab32d579d0a8aa6388d617d44c2218d42 |
| evidence.jsonl | 563c36d4f57ea20f45c1e46fb44368e6cd862eebd67afc9f2dc5318927d0df24 |
| result.json | 819738da2abeb58164e222356b12820739d1e98f9793da8c2aa8b174eb7035f2 |

实际执行1个端到端请求、3次模型（selection V4/Rewrite V3/Summary V4各1）、4次search、2次embedding、2次rerank，Business/retry/resume均0。首例`UAT-KB-001`冻结预期为clarification_required/no_result且不检索；实际HTTP200/success、两域检索、最终1条law域引用，`passed=false`。这是可观测的产品语义失败，不是404、依赖失败或invalid_run。批次status=failed，其余9例未执行；不得使用剩余名义预算补跑或创建第二批。

| 根因/局限 | 证据与强度 | 最小处理与当前状态 |
|---|---|---|
| 缺条件的适用判断被当作直接规则查询 | 三个模型任务succeeded；预期澄清而实际search/success，强证据；未保存模型原文，不能推断它内部补造了哪项事实 | 当前Prompt语义约束不足以可靠触发澄清；需区分适用判断与一般规则查询，不能加酒店专用本地计划分支；未关闭 |
| 必要分类证据仍在排序/Evidence阶段丢失 | 同一a5快照，住宿定义policy keyword rank19、域融合rank34、域rerank rank31；未进final20/Evidence8，强证据 | 仅离线聚焦query可命中不代表真实模型query稳定；新方案必须先做同快照非live对照，不盲目扩大topK；未关闭 |
| 域覆盖不等于答案语义覆盖 | final20/Evidence8含两域，但最终1条引用只在law；合法引用不证明分类/期间/适用条件齐全 | 保留严格引用校验；不能将结构性sufficient或provider成功记作UAT通过 |

本次owned auth/es-query/agent/Runtime进程均停止，HTTP clients关闭，临时原始日志删除；有限evidence记录secretScanPassed。共享ES/BGE服务未停止，未写索引或alias。逐case状态见UAT_01 §14.2。冻结runner的单case `calls.e2e`错误显示0，而顶层`totals.e2e=1`及唯一case行证明实际1次；保留原字节，独立历史测试明确该低风险显示缺陷，不回写result。

### 20.7 正式代码对照设计评审与最终 non-live 验证

评审范围为当前三份Knowledge L2、生产组合根/Model/Capability/检索/Evidence/Java服务及直接测试；分实施后评审、最小修复后复评两轮。为自动化辅助的独立审查阶段，不冒充外部人工批准。

| Issue | 等级 | 发现、修复及关闭证据 | 终态 |
|---|---|---|---|
| B-CR-001 | Major | 首例缺条件应澄清却直接返回success；当前结构校验无法证明自然语言适用条件充分，且必要分类证据未入选。不得用fake通过替代真实失败 | Open；核心P0与正式评审均未通过 |
| B-CR-002 | Major | 新semantic planner未区别全角百分号/千分号等单位；反例首次3 failed/14 passed。最小新增比例单位保持校验，不改历史guard或Prompt；新增9项单元/生产零调用测试后38项定向通过 | Closed；提交7f5085a8d82107e9598c1cda9da79c78a49304d8 |
| B-CR-003 | Minor | 冻结runner单case e2e计数未递增；顶层计数、journal及case数可独立核实，不影响停止或预算 | Accepted仅限本次不可变资产；历史测试显式覆盖，后续新runner需修复 |

上述为run-01时点评审结论：Blocker=0、Major=1未关闭，正式代码评审未通过。已实施的确定性合同、授权、调用预算、取消、唯一链路及历史隔离验证通过，但不能据此宣布阶段B完成。未改gold、阈值、旧任务或冻结资产；当时未追加模型调用。后续独立授权及当前结论见§20.10～20.11，不把历史判断当作新批执行结果。

| 实际命令/验证范围 | 本轮结果 |
|---|---|
| `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1`（正式隔离安装） | host/preflight 14 passed；全量1637 passed、27 opt-in skipped、0 failed；1条既有LangGraph弃用预告 |
| `python -m pytest agent-runtime/tests/system_e2e/test_knowledge_stage_b_run_01_history.py -q` | 3 passed；5项有限资产hash、冻结提交源码、调用/清理/禁止原始数据字段校验 |
| `python -m mypy --strict src`、`python -m compileall -q src`（agent-runtime） | 122生产文件类型通过；编译通过 |
| agent-service `mvnw.cmd test` | 本次终端40 tests、0 failure、0 error、1 skip；含当前Spring→Runtime Business/Knowledge E2E；不使用陈旧XML累计总数 |
| serviceCenter reactor相关模块`-am test` | common-security21/0skip；es-query-service43/0skip；Employee50/20skip；Transaction37/2skip；均0 failure/0 error |

27项Python及Java所列opt-in/环境用例未执行，不计作新真实UAT通过。既有35项Business/37项Knowledge追踪与当前non-live防回退保持，阶段A与历史hash校验保持；本次未重复执行其历史live。只读/非付费诊断累计search136/embedding46/rerank36，加正式批次后的typed调用合计140/48/38；不将额外只读元数据检查计为业务search，也不宣称这些是全部HTTP总数。

当前可交付为已评审设计、最小实现、通过的non-live、失败的有限UAT证据及真实状态。后续必须先解决澄清与一般规则查询的语义边界、必要证据覆盖，再以新设计版本/非live证据评估是否另立受控真实验证目标。本目标不创建新付费候选、不扩大接口/语料/索引或阶段C范围。Git按设计、实现、准备、评审修复及失败证据分别提交，提交不代表UAT或正式评审通过。

最终状态复核：当前L1及三份L2严格结构校验通过，P3 strict为0 errors/0 warnings；UAT追踪及本次历史资产定向11 passed；PowerShell AST通过；阶段A四项最终资产SHA不变，当前alias仍指向a5、UUID=`SurWRSglRd6ZRddEBWy2Sw`，本次四个隔离监听端口均已释放。Git差异证明旧阶段A/evaluation staging与运行binding未改动。状态修订仅更正实施/验收结论和路线图旧入口表述，不改变设计合同或提升版本。P3校验器不识别“前置全部完成但一次授权已消费”的外部暂停情形，因此UAT使用已有Deferred并写明failed；不增加无决策价值的新门禁。

| 已推送原子提交 | 内容 |
|---|---|
| 0ea390277a04f7703926eccb4e090fcadb00c549 | 阶段B根因、设计及实施入口评审 |
| 9537548f0e73ef45725eeca185faed96d0cb2811 | 有界排序/Evidence设计校准 |
| 245b4c9d8ca774421506ef28a76777e291e41105 | 当前语义规划、检索及安全控制实现 |
| 338b387100f03f4153611b2324604c8e25466a2b | 非live诊断、专项批次准备与冻结源码 |
| 7f5085a8d82107e9598c1cda9da79c78a49304d8 | 比例单位保持的代码评审修复 |
| 85bcf2149a99cb5d038d8a9f688df7be03f562cf | 失败批次五项有限证据及冻结源码历史测试 |

最终状态同步提交及远端/工作树以Git日志和交付报告为准，避免文档自引用提交SHA。所有推送均为当前codex分支的普通快进推送，无PR或历史改写。

### 20.8 失败后非live澄清边界修复

只读核实发现V3 Prompt的“具体主体”触发条件比REQ-KQUALITY-003/KQ-AD-015的“单一适用判断”更窄；行业/服务的适用提问未给出具名主体，也可能缺少必要条件。这是有源码依据的候选原因，不证明其是唯一根因。最小方案由L2_01_00 v1.18 DR-KFLOW-019治理：新增V4 Prompt，复用公开V3 definition/decoder/类型/预算，当前生产单绑定改为V4，旧V3和冻结批次不改；不新建intent Schema、本地税务规则或额外模型审核。

三轮内审依次核对语义/责任、合同/安全、追踪/有限验证；独立审查首轮发现主追踪与准入状态两项S2，最小修复后第二轮通过，S0/S1/未处理S2均0。设计可作为非live实施依据；不改变UAT Deferred、质量包Blocked、B-CR-001 Open。排序/Evidence必要条款缺口仍独立保留，不通过Prompt修订宣称关闭。不得再次读取模型Key或执行本批剩余预算。

当前已新增`knowledge/rewrite_v4.py`，生产工厂与版本守卫唯一绑定Rewrite4/Summary4；V4直接复用V3公开输入构建与相同parse_response，没有复制decoder或增加本地意图规则。Prompt SHA-256=`a3baf3dcdc55e645660fecf94434669c72b27e8ba0545a02867e45f9ccfbc07d`，UTF-8长度3314bytes，低于8192硬上限；输入/输出/timeout预算不变。P3/UAT版本未因纯执行记录和来源版本同步而升级，已停止的真实批次继续绑定冻结V3。

| 本增量实际验证 | 结果与限制 |
|---|---|
| V4/V3契约、注册、版本拒绝及生产根定向pytest（5文件；显式`PYTHONPATH=agent-runtime/src`） | 98 passed；共享parser、请求仅版本/指令变化、资料查阅search、澄清零下游、invalid/timeout无fallback；fake不证明真实意图 |
| `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1` | 独立安装Python3.12环境：host/preflight14 passed；全量1687 passed/27 opt-in skipped/0 failed，1条既有LangGraph弃用预告；脚本清理临时环境 |
| `python -m mypy --strict src`；`python -m compileall -q src` | 123生产文件类型通过，编译通过 |
| agent-service：`mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test` | 40 tests/0 failures/0 errors/1 opt-in skip；含Access、Business、Knowledge三项Spring→Runtime E2E。测试进程显式PYTHONPATH当前src、stub模型、Knowledge默认false，清除Key；Knowledge测试独立注入同生产对象图fake |
| UAT两份traceability与本批历史pytest（3文件） | 15 passed；35/37固定追踪保留，失败批次五项hash/冻结Git源码/计数/清理/禁止原始字段验证通过 |
| 历史与阶段A保护 | V3源码/测试及冻结runner对照338b387无差异；阶段A四项最终hash、历史staging、本批有限evidence及运行binding无修改；没有新增真实模型、检索、embedding或rerank调用 |

验证过程中的失败如实保留：第一次全局Python定向命令未设置源码路径，5个collection error，未执行测试；显式路径后98项中新增版本拒绝fixture缺少enabled_domains，97 passed/1 failed，补齐fixture后98通过，未改生产验证或期望。第一次Maven用未安装Runtime的全局Python且没有PYTHONPATH，Access liveness失败（40 tests/1 failure/1 skip）；日志确认为ModuleNotFoundError，补齐仅测试进程环境后通过。没有把这些环境/fixture问题当成付费重跑理由。

本增量正式代码对照评审1轮，范围限DR-KFLOW-019、新任务/装配、共享decoder/guard和直接测试，复核模型登记身份、唯一任务、失败关闭、预算、无新敏感输入面、取消/lifecycle继承及历史保护。未发现新增Blocker/Major或需接受的Minor；这是本执行者的正式对照审查，不冒充独立评审人。整体B-CR-001仍Open：新Prompt真实语义未验证，必要分类Evidence仍有缺口。因此整体正式评审仍Major=1，UAT仍Deferred/failed，质量包仍Blocked，不宣布阶段B完成。

es-query-service/common-security/Employee/Transaction Java源码未改，本增量不重复执行这些模块Maven；其上一轮实际结果保留在§20.7，不冒充本增量新执行。未改launcher，未重复PowerShell AST；本轮全量Python已执行相应脚本合同和历史测试。随后完成下述必要Evidence覆盖的非live诊断；新的真实语义确认不在本次已停止批次内。

本增量设计提交`1a50221fd062935e73c227a6184d9263d0e765b8`、代码/测试/追踪元数据提交`5141da76497e6509421e23a4817a693ccbf112f6`已普通推送至origin/codex；状态同步提交以Git日志为准。提交不改变failed UAT或Major未关闭结论。

### 20.9 必要Evidence风险的有限复核

以`4181ed31d75118258063ebba0ba55017de852a55`为只读基线，定向核查DR-KRET-027/DR-KEV-026、当前排序/selector及冻结case；不修改实现或合同。按冻结有限排名重放“锚点→域内keyword/rerank交错→域间轮转”，所得前20项与真实记录逐项一致。住宿定义在完整57项身份序列中为第48项，因此该次排除发生于final20之前，不是每文档3条或8条Evidence配额造成；这个离线展开仅定位截断位置，不调用下游、不更改生产窗口，也不证明扩大到48能改善回答。

冻结KB-001没有requiredGold，预期是澄清且零检索；它已证实的是错误进入检索并返回success。住宿定义在错误分支中未入选属于独立质量风险，不能把它当成其余9个未执行条款用例已经失败的证据。v7人工聚焦检索表达中住宿定义/生活服务总类分别在rank2/3且已入Evidence，说明既有路径具备局部能力，但不是模型生成query或专项UAT通过。有限记录只有query哈希，不能从中还原真实改写或断言单一根因。

定向结论：排序及配额控制符合上述两条实现合同；真实语义与完整核心场景效果仍不可验证。不建议无证据扩大topK、改配额、按条款ID加分或新增第二查询；B-CR-001保持Open，整体正式评审仍未通过。无需新增任务版本、候选、门禁或证据副本。

本次实际命令：显式`PYTHONPATH=agent-runtime/src`后执行`python -m pytest tests/unit/knowledge/retrieval/test_quality_ranking.py tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q`，25 passed；有限排名重放断言通过；本次新增模型/search/embedding/rerank调用全部0。仅修改P3/UAT状态解释，无生产差异；§20.8全量、类型和Java结果是前一增量实测，不冒充本次重跑。

### 20.10 新增一次性run-02授权

用户在目标阻塞后明确授权“准备并执行新的独立受控验证批次，验证V4修复及未执行场景，重新绑定代码、用例、配置和调用预算”。仅开放`knowledge-stage-b-uat-v2-20260904-run-02`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-02`；不是旧run-01的补跑或授权复用。用例、顺序、gold和通过条件沿用原10例，任务绑定selection-v4/Rewrite4/Summary4；本批上限10端到端/30模型/40search/20embedding/20rerank，Business/answer/retry/resume=0。加旧批实际1/3/4/2/2后累计上限11/33/44/22/22，仍低于原总授权20/60/80/40/40。任一真实失败停止新批次，不自动创建run-03。

新入口`tests/system_e2e/knowledge_stage_b_uat_v2.py`只在独占CLI作用域复用冻结runner：新manifest绑定HEAD、3个Prompt hash、4/4任务、当前索引/配置/可执行文件、旧批五项hash、累计预算及唯一输出目录；修正新批单case e2e计数，调用前校验Prompt，澄清必须零下游。新入口和直接fake测试先验证，旧runner/cases/gold及run-01字节不改。prepare/check-environment不读取模型Key；execute是唯一读取入口。暂不关闭B-CR-001或质量包，真实结果形成后据实更新。

本次准备验证：新/旧runner及历史、V4合同和生产fake五文件101 passed；正式隔离入口host/preflight14 passed、全量1707 passed/27 opt-in skipped/0 failed（1条既有LangGraph预告）；strict mypy123生产文件及源码/新入口compileall通过。P3 strict为0 errors/0 warnings，阶段A四项最终hash及旧runner源码不变；9200/8908/8909健康检查200。新入口check-environment完成真实auth→Spring→stub Runtime的422 unsupported冒烟，model/Knowledge=0，owned进程、clients和临时原始日志已清理。新入口定向代码对照复核覆盖版本、Prompt、累计预算、目录防复用、异常停止和旧模块作用域恢复；未发现本增量Blocker/Major，不替代整体B-CR-001的真实验证。仅授权/执行状态同步，批准的V4设计、公共接口和生产代码未修改。

### 20.11 run-02终态与证据复核

本批按§20.10授权实际执行一次，frozen HEAD=`501bca8b68c6efef9931c7dfbf3ad335c59d7f0b`，manifest绑定287项源码、258项可执行资产、原10例/gold及既有索引快照。正式命令为在`agent-runtime`、显式`PYTHONPATH=src`环境执行`python -m tests.system_e2e.knowledge_stage_b_uat_v2 execute --root target/knowledge-stage-b-uat-v2-20260904-run-02 --manifest-sha256 e41585a4d43b58049aa64708906a460f324ddaea0d96aa5ee492cfbca1f62c20`；exit 1，受控测试失败，非uncaught runner故障或invalid_run。

| Case | 实际结果 | 调用与结论边界 |
|---|---|---|
| UAT-KB-001 | Passed；HTTP200/no_result/clarification_required | selection-v4、Rewrite4均成功；2模型，search/embedding/rerank/summary均0。原首例澄清反例已有V4真实通过证据，不外推全部措辞 |
| UAT-KB-015a | Failed；HTTP502/downstream_failure | selection成功，Rewrite4 invalid_output；2模型，尚未检索。没有返回分类/住宿Evidence，不证明索引缺正文或排序失败 |
| 其余8例 | Not executed | 第二例失败立即停止；清单由UAT_01 §14.5和result.notExecuted治理 |

本批实际2端到端/4模型/0search/0embedding/0rerank；两批累计3/7/4/2/2，Business/answer/retry/resume均0。名义剩余预算不得续用，无run-03。owned进程停止、Runtime clients关闭、临时原始日志扫描删除均有有限记录；18090/19201/18080/19091监听消失，共享9200/8908/8909未停止。六项运行资产逐字节复制保存于`agent-runtime/tests/system_e2e/knowledge_stage_b_run_02/`：

| 资产 | SHA-256 |
|---|---|
| manifest.json | e41585a4d43b58049aa64708906a460f324ddaea0d96aa5ee492cfbca1f62c20 |
| environment.jsonl | ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7 |
| consumed.json | 7ba1b07c7b9f678cb5b604dcd84e1feda3971dcc280dcfe0aadbbb94c9ae2635 |
| journal.jsonl | 0bf32c39e1021482bcd71ef3ee46c2f8fecb54db14b983accfaf097d4b9aed67 |
| evidence.jsonl | 52ea41efc75a7ef56c1c3e88863c7a67d2717805e6254e14e3b02d210a5cf85b |
| result.json | 48ec2dd512eac405e733e04b94f6095c5c0136d918c8472ea8022e4798a1c8aa |

失败根因证据分层：实际Rewrite任务版本为4，`taskBindingValid=false`同时包含“期望完整任务链成功”校验，并不表示错装V3。`invalid_output`可由provider响应解码或任务exact decoder产生；未保留原始模型响应或更细的分支枚举，不能断言具体字段、token截断、模型推理或某一句Prompt为根因。HTTP502和零检索符合DR-KFLOW-005/019失败关闭；不得为关闭UAT放宽decoder、恢复原问题检索或盲改Prompt/topK。本项目不需要因一次格式失败扩建审批/规则引擎；后续最小方向是先评估安全的有限错误枚举可观测性，再做synthetic复现，不保存原始响应；新的真实验证不属于本次已停止授权。

新增历史测试从冻结Git提交验证源码、六项hash、Schema/预算、逐case账和journal/cleanup一致性，不重新执行launcher。首轮39 passed/1 failed：新增源范围中8个文件冻结为混合换行，旧LF/CRLF二选一重建不足；核实各文件当前字节仍精确等于manifest且规范化后等于冻结Git，测试只记录行尾位置并从Git独立重建原SHA。未改8个源文件、冻结manifest、哈希或断言强度。

当前验收结论：run-02 Functional=Failed，完整专项效果未测完。B-CR-001中KB-001精确反例通过，但其整体核心P0覆盖和验收项仍Open；本次不能把KB-015a失败定位成一个已确认代码缺陷，也不能宣布全面代码评审通过。UAT工作包Deferred、质量包Blocked，GATE-KRG-006已批准设计的入口状态不回退。只同步执行状态，不升级设计/Prompt/Schema或放宽原验收条件。

| 运行后实际验证 | 结果 |
|---|---|
| `python -m pytest tests/system_e2e/test_knowledge_stage_b_run_02_history.py tests/system_e2e/test_knowledge_stage_b_uat_v2.py tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q`（agent-runtime，显式PYTHONPATH） | 修复纯测试换行重建后40 passed，1条既有LangGraph预告 |
| `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1` | 正式隔离host/preflight14 passed；最终全量1712 passed/27 opt-in skipped/0 failed，1条既有预告；临时环境已清理 |
| `python -m mypy --strict src`；`python -m compileall -q src tests/system_e2e/knowledge_stage_b_uat_v2.py tests/system_e2e/test_knowledge_stage_b_uat_v2.py tests/system_e2e/test_knowledge_stage_b_run_02_history.py` | 123生产文件类型及所列编译通过 |
| P3 `validate_implementation_plan.py --strict`；UAT当前10行与result逐项比对；六项hash与P3比对 | 0 errors/0 warnings；1通过/1失败/8未执行与有限结果一致 |
| 历史/敏感/差异 | 287源码从冻结Git重建hash通过；六项复制字节相同；阶段A四项hash不变；retained资产密钥/JWT/私钥模式扫描无命中；无生产或历史文件差异；git diff --check通过 |

运行后正式对照评审1轮：主依据P3 §20.10授权/失败停止合同，支撑DR-KFLOW-005/019与UAT §14；范围仅新版本runner、直接fake/history测试、有限结果和旧runner调用接缝。复核唯一生产装配、Prompt/版本/目录/累计预算绑定、调用前消费、失败中断、gold仅用于判定、客户端和进程清理、字节保护。未发现该增量新增Blocker/Major；计数字段解释和混合换行重建已明确，不将本执行者的复核冒充外部独立评审。整体核心UAT失败及证据不足仍阻塞最终评审/收口。生产Java、业务DTO、索引和权限均未修改；本增量不重复Maven/PowerShell AST，既有结果保留§20.7～20.8，不冒充新执行。准备提交`501bca8b68c6efef9931c7dfbf3ad335c59d7f0b`已推送；运行证据/历史校验提交`3d5d3dbda06144f0a1f10e811896b7a2455ec6bf`，状态同步另行提交，推送结果由Git日志及交付报告记录。

### 20.12 run-02失败边界的非live联合验证

以`327da9391cdf36bf160f95bb6557a03919e1325b`为基线，只补`tests/integration/knowledge/test_rewrite_v4_provider_boundary.py`，不改生产代码、Prompt、任务合同或历史运行资产。原生产fake测试直接注入已解码的StructuredModelResponse，shared transport另行测试；新增13项用HTTP MockTransport连接真实DeepSeekChatTransport、provider decoder、当前Rewrite4、gateway与生产Runtime，验证成功、澄清、HTTP Content-Type、外层JSON、model标识、length终止、任务JSON/重复键/额外键/未知条件、解码后日期漂移、503和timeout。模型和Knowledge HTTP均fake；Business send主动拦截并断言0；使用硬编码synthetic key，不读取进程模型Key。

定向核查结论：DR-KFLOW-005/019的严格解码、失败零检索/embedding/rerank/summary、固定任务版本、无Business fallback、关闭client和有限观察不泄露响应标记/JWT/key均符合。测试只观察真实provider decoder是否成功返回，不替换其判定；响应/任务解码失败均可能记录invalid_output，而解码后语义拒绝会留下模型succeeded。故历史run-02的failed/invalid_output可排除“已成功解码之后的语义保持检查”作为该失败条目的直接来源，仍不能在响应头、provider envelope和任务JSON之间确定具体根因。synthetic正向控制不证明模型分类或真实Evidence质量；不据此盲改Prompt、扩大512 token预算或放宽decoder。

| 本次实际验证 | 结果与范围 |
|---|---|
| 新联合测试定向pytest | 首次13 passed；后续复核补Business调用硬拦截，最终版随下行118项全部通过 |
| `python -m pytest tests/integration/knowledge/test_rewrite_v4_provider_boundary.py tests/integration/knowledge/test_stage_b_production.py tests/contract/knowledge/test_rewrite_task_v4.py tests/unit/model/test_deepseek_transport.py tests/system_e2e/test_knowledge_stage_b_run_02_history.py tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q`（agent-runtime，显式PYTHONPATH=src） | 118 passed，1条既有LangGraph预告；含最终Business拦截断言与旧/新批历史hash |
| `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1` | host/preflight14 passed；全量1725 passed/27 opt-in skipped/0 failed，126.00秒、1条既有预告；临时环境已清理。全量验证版本与最终版本的差异仅为测试拦截增强，无生产差异，最终测试版已在上述118项中复验 |
| `python -m mypy --strict src`；`python -m compileall -q src tests/integration/knowledge/test_rewrite_v4_provider_boundary.py` | 123生产文件类型及编译通过 |

本增量执行一次定向代码对照核查并修复测试隔离遗漏；不作整体正式评审通过判断。新增模型/search/embedding/rerank真实调用均0；六项run-02及四项阶段A最终hash不变；该增量未新增run-03。该时点P3仅追加执行记录、版本v2.43，不升级设计或改写UAT_01的冻结逐case结果。UAT继续Deferred/failed，QUALITY继续Blocked、B-CR-001继续Open。Java/公共DTO/launcher未改，本次未重复Maven、Spring E2E或PowerShell AST，不将历史结果冒充本次执行。现有证据不能恢复未保留的模型响应；进一步真实确认须作为新的明确授权事项，不续用两批已停止预算。

### 20.13 新授权run-03有限诊断与独立验证

用户明确授权先补齐有限失败诊断，再准备并执行一次新冻结的独立批次。授权仅用于`knowledge-stage-b-uat-v3-20260904-run-03`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-03`；不重启run-02，不授权run-04。沿用原10例及顺序/gold，selection-v4/Rewrite4/Summary4、Prompt/生产合同/索引不变。设计补齐限UAT_01 §14.6 KB-DIAG-001测试运行协议，本计划治理授权/顺序/状态；ARCHITECTURE仅同步版本，不升级L1/L2或改生产接口。

| 预算 | e2e | model | search | embedding | rerank |
|---|---|---|---|---|---|
| run-01/02实际累计 | 3 | 7 | 4 | 2 | 2 |
| run-03独立批次上限 | 10 | 30 | 40 | 20 | 20 |
| 包含本批的累计最大值 | 13 | 37 | 44 | 22 | 22 |
| 原目标总上限 | 20 | 60 | 80 | 40 | 40 |

Business/answer/retry/resume始终0。先协议三轮内审及只读设计评审，再实现版本化runner和诊断，随后fake/正式隔离回归/定向代码评审，提交干净HEAD后冻结manifest；仅execute读取Key并执行一次。首个模型outbound消费本批授权，失败立即停止，有限结果append-only；诊断不能改接受判定或触发补跑。旧批hash、阶段A索引和历史证据保持不变。

协议准备时尚无新真实调用；整体B-CR-001 Open、QUALITY Blocked，不因获得授权声明UAT通过。受影响任务复用现有WP-KRETRIEVAL-UAT-01，不新增循环门禁。随后实际终态见§20.14。

协议内审实际执行三轮：第一轮对照L2_01_00 §8/12及真实transport/gateway，限定诊断在原判定失败之后；第二轮对照V3共享parser与V4工厂，补足仅CLI作用域、原异常透传、取消和未知值的有限退路；第三轮对照两个冻结result和当前runner，复算累计预算13/37/44/22/22、拒绝旧目录复用、保持原case/gold及失败停止。随后切换只读设计评审，按详细设计可实施性和跨层职责核对KB-DIAG-001：未发现S0/S1或未处理S2，允许实施该测试协议。本结论为本执行者分阶段的自动化辅助评审，不冒充另一个独立评审人；不等于阶段B整体验收或B-CR-001关闭。

实现及准备复核：新增runner v3和独立有限诊断模块，不改任何生产src或旧runner。实际定向46 passed（首轮44，再补两项新旧acceptance verdict完全等价断言）；历史run-01/02和Business35/Knowledge37追踪20 passed。正式隔离命令`pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1`实际host/preflight14 passed、全量1769 passed/27 opt-in skipped/0 failed，135.65秒、1条既有LangGraph预告；该全量收集时为新增44项，随后补充的2项已在最终46项定向中通过。strict mypy123生产文件、compileall、P3 strict（0 errors/0 warnings）及git diff --check通过。阶段A与旧批源码/证据无Git差异，旧hash测试通过。本增量Java/公开合同和PowerShell未改，不重复Maven/AST，不把历史执行数字当作新结果。

正式代码对照评审1轮，主依据KB-DIAG-001和L2_01_00 DR-KFLOW-005/019，范围为3个新增测试文件及复用边界。检查原异常身份/取消透传、工厂identity、唯一接收判定、有限诊断Schema、未知值退路、context及绑定恢复、旧预算和case顺序、调用前Prompt hash、独占目录/不续跑、历史不可变。补强2项verdict等价断言后复核，无该增量Blocker/Major或未处理Minor，允许准备冻结；不等于整体B-CR-001关闭。真实模型/search/embedding/rerank新增调用仍0。

### 20.14 run-03真实结果及诊断边界

设计提交`7f7e44f`、runner/测试准备提交`4a095def4930810713314c15a34668a12fdf4a31`已推送origin/codex，后者为本批frozen HEAD。新manifest Schema3绑定297项源码、258项可执行资产、原10例和gold、4/4任务/Prompt、a5索引/配置及旧批hash。准备环境检查exit0，真实auth→Spring→stub Runtime返回422 unsupported，模型/Knowledge0。正式命令在agent-runtime、显式PYTHONPATH=src：`python -m tests.system_e2e.knowledge_stage_b_uat_v3 execute --root target/knowledge-stage-b-uat-v3-20260904-run-03 --manifest-sha256 c0f111d48195e73c7c1f07a81dec24c127b23aff55c81431452addad99d717e0`；执行一次、exit1、UAT failed，非invalid_run。

| Case | 实际结果 | 结论边界 |
|---|---|---|
| UAT-KB-001 | Passed；HTTP200/no_result/clarification_required；2模型，检索/摘要0 | 澄清控制获得该精确反例的真实通过 |
| UAT-KB-015a | Failed；HTTP200/success；3模型、4search、2embedding、2rerank | 期望policy单域，实际policy+law；lodging条款true，living条款false；1条policy引用 |
| 其余8例 | Not executed | 第二例失败立即停止，不外推跨域、期间或非酒店用例通过 |

本批实际2/5/4/2/2，三批累计5端到端/12模型/8search/4embedding/4rerank；Business/answer/retry/resume0。任务全部succeeded，modelFailures为空，版本绑定正确；run-02的invalid_output本次未复现，不代表永久修复，也不能回溯确定其原decoder分支。服务端HTTP success只表示既有结构/引用合同通过，不等于专项语义rubric通过。owned进程、clients、临时原始日志清理和secretScan均true，18090/19201/18080/19091均已释放，原9200/8908/8909未停止。

六项append-only资产精确复制至`agent-runtime/tests/system_e2e/knowledge_stage_b_run_03/`，无原始模型响应或知识正文：

| 资产 | SHA-256 |
|---|---|
| manifest.json | c0f111d48195e73c7c1f07a81dec24c127b23aff55c81431452addad99d717e0 |
| environment.jsonl | ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7 |
| consumed.json | 0caa52c2adc38267fc25661bcc84df851ca123cf7740767b2a201c9317e4d079 |
| journal.jsonl | ffac99686b316c68e34fe7d3a7ace3cc16409a79ba5c54ec422f6d1ef4f8a3d3 |
| evidence.jsonl | cf824819278a1cd076e14d3224b27035f6a0d8b3a09914c290ed9a1522044b16 |
| result.json | e414fc99138f75b9c278f5cb06df76d406eec8f6eaf866a5eebb4f152c0f712a |

有限根因矩阵（只读重放，没有额外外部调用）：

| 观察 | 证据强度 | 排除或后续边界 |
|---|---|---|
| 原问题是政策中的生活服务/住宿定义，冻结预期单policy；实际预先规划policy+law | 高：冻结case与有限domains结果 | 域意图过宽；不能称失败后扩域/fallback，4search在一次计划内 |
| lodging/living的policy keyword rank9/2，vector rank3/16，域内rerank rank1/2，final20 rank2/4，Evidence rank2/4 | 高：阶段chunk/hash序列及实际summary输入内容hash | 两项必要原文均已到模型；本例不是正文缺失、窗口截断或Evidence配额损失，不支持扩大topK |
| 最终1条连续引用满足lodging，但不满足冻结living条款 | 高：原rubric布尔值、引用数和域 | 摘要覆盖不满足本case预期；没有持久化quote，不推断完整回答文案或模型内部原因 |
| Summary4允许“一条已足够则不冗余”，冻结case要求分类及定义两条依据 | 合同核查线索，不是已确认实现缺陷 | 后续应先核实原问题的分类证明义务与摘要最小引用规则是否需澄清，不能事后改gold、降阈值或把本次failed改判passed |

当前专项Functional=Failed、完整效果未测完；B-CR-001的核心P0/完整UAT仍Open、QUALITY Blocked、UAT Deferred。当前授权已消费，不创建run-04、不继续读取Key或外部模型验证；后续优先在non-live中澄清域语义与摘要覆盖合同，而非直接重跑。阶段A、历史P5和固定Business35/Knowledge37功能追踪保持独立，不改判。代码诊断准备通过不等于阶段B正式整体评审通过。

| 运行后实际验证 | 结果 |
|---|---|
| `python -m pytest tests/system_e2e/test_knowledge_stage_b_run_03_history.py tests/system_e2e/test_knowledge_stage_b_uat_v3.py tests/system_e2e/test_knowledge_stage_b_run_02_history.py tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q`（agent-runtime，显式PYTHONPATH=src） | 最终71 passed；297源码从冻结Git重建、6项hash、预算、停止、排名、cleanup及35/37追踪通过 |
| `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1` | 最终正式隔离host/preflight14 passed；全量1776 passed/27 opt-in skipped/0 failed，144.75秒，1条既有LangGraph预告；临时环境清理完成 |
| `python -m mypy --strict src`；`python -m compileall -q src tests/system_e2e/knowledge_stage_b_failure_diagnostics.py tests/system_e2e/knowledge_stage_b_uat_v3.py tests/system_e2e/test_knowledge_stage_b_uat_v3.py tests/system_e2e/test_knowledge_stage_b_run_03_history.py` | 123生产文件类型及编译通过 |
| P3 strict、diff、历史和安全 | P3最终0 errors/0 warnings；diff --check通过；阶段A四项hash、前两批及生产源码无改动；六项新证据敏感模式扫描无命中；无run-04 |

本轮验证中的准备问题未隐藏：P3 Ready队列先改而工作包表仍Deferred，strict报READY-004，原子同步后三表一致；新增历史测试误估资产290项，首轮50 passed/1 failed，按实际冻结manifest和Git逐项核实为297后精确断言通过，没有改manifest或削弱源码hash检查。归档暂存时发现默认text换行转换将改变6项证据，在提交前沿用前两批的精确目录binary规则，仅追加`.gitattributes`的run-03一行；对6个精确路径重新应用归档属性后，暂存blob与运行原始字节逐项完全相等。没有修改旧规则、运行文件或哈希。

运行后代码/证据对照评审1轮（本增量准备及运行后共2次），发现B-R3-001：默认Git行尾归一化破坏新历史字节可复现性；上述binary隔离与暂存blob对照完成最小修复并复评关闭。当前新增runner/诊断/历史归档无未关闭Blocker/Major/Minor；整体B-CR-001仍Open、阶段B未完成。该评审是本执行者的分阶段对照审查，不冒充独立人员批准。Java源码/接口/权限及PowerShell没有修改，本次不重复Maven/AST；实际Spring→Runtime受控执行已完成上述两个case，其余8个未执行边界保留。

### 20.15 非live选域边界修复

起始HEAD为`a03f6ec6ffb6fe95f394f7be022722e04b008bfd`，工作树clean。继续原目标内非live修复，不构成run-04或任何新增模型请求授权。依据§20.14，先处理有直接依据的域语义风险，摘要必要条款覆盖仍单独保留：原问题限定政策定义，两个必要chunk已到模型，不能用扩大topK解决。`B-DOM-001`：V4的域指令没有明确区分税务背景与必要原文类别；本地接受合法双域符合现有decoder，不应增加本地关键词删域。

最小方案由L2_01_00 v1.19 DR-KFLOW-020治理：新增Rewrite V5指令、保持V3 exact合同/V4澄清、切换当前单绑定；Summary、排序、Evidence与全部冻结资产不变。三轮内审及只读设计复评已完成（同一执行者分阶段，不冒充另一人），strict首轮发现DR追踪行遗漏，补齐规范矩阵后0 errors/0 warnings。允许该切片非live实施；没有新门禁或付费候选。现有IMPLEMENT/NONLIVE的Done记录仍仅证明先前DR-019范围；DR-020代码和验证在本节后续记录前不得算Done。UAT Deferred、QUALITY Blocked、B-CR-001 Open不变。

增量实施完成：`knowledge/rewrite_v5.py`仅叠加最小必要原文域指令，复用V4公开definition/request及V3 exact decoder；`bootstrap`唯一绑定Rewrite5/Summary4。新增合同和18项域计划fake，覆盖单域、双域、配置顺序、未启用/未知/重复域以及相同/不同query的请求内embedding复用。旧V3/V4及历史run源码、Prompt、gold和六项run-03证据不改；历史诊断测试仅在测试作用域从冻结提交加载原Knowledge组合类，不放开当前生产版本守卫。没有删除代码或增加生产依赖。

实际测试和修复过程：首次新合同测试使用不存在的内部finish枚举，纠正为已有TOOL_CALLS；供应商length故障仍由wire测试覆盖。历史诊断首次未同步替换main中的导入绑定，补齐测试作用域隔离后46 passed。新fake首次把相同文本的embedding误计为每域一次，依据现有请求内去重实现修正精确断言，并追加不同文本的双调用反证。全量首轮1821 passed/27 skipped/1 failed，发现现行注册合同仍期望Rewrite4；迁移为精确5/4后重跑，不修改历史任务或放宽断言。

| 本次实际命令 | 结果 |
|---|---|
| `python -m pytest tests/contract/knowledge/test_rewrite_task_v5.py tests/integration/knowledge/test_rewrite_v5_domain_boundary.py tests/integration/knowledge/test_stage_b_production.py tests/integration/knowledge/test_rewrite_v4_provider_boundary.py tests/integration/knowledge/test_summary_v4_composition.py tests/system_e2e/test_knowledge_stage_b_uat_v3.py -q --tb=short` | 132 passed；现行V5与历史V4分别验证，fake不证明LLM语义 |
| `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1` | 最终host/preflight14 passed；全量1822 passed/27 opt-in skipped/0 failed，160.09秒，1条既有LangGraph预告 |
| `python -m pytest tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/system_e2e/test_knowledge_stage_b_run_02_history.py tests/system_e2e/test_knowledge_stage_b_run_03_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q --tb=short` | 25 passed；三批历史及Business35/Knowledge37追踪有效 |
| agent-runtime：`python -m mypy --strict src`；`python -m compileall -q src tests/contract/knowledge/test_rewrite_task_v5.py tests/integration/knowledge/test_rewrite_v5_domain_boundary.py tests/system_e2e/test_knowledge_stage_b_uat_v3.py` | 124生产文件类型通过；编译通过 |
| agent-service：`..\serviceCenter\mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test` | 40 tests/0 failures/0 errors/1 opt-in skip；Access、Business、Knowledge Spring→Runtime E2E实际执行。进程清除Key、stub/Knowledge默认false，测试独立注入fake；首次使用模块内不存在的wrapper路径未执行Maven，改用仓库现有wrapper |
| L2详细设计strict；P3计划strict；历史hash；敏感模式扫描；`git diff --check` | 设计/计划0 errors/0 warnings；阶段A四项hash及三批冻结资产不变；变更文件密钥/JWT/私钥模式0命中，并人工复核仅合成测试数据 |

代码对照设计评审1轮及修复后复评1轮：按DR-KFLOW-020核对公开definition复用、唯一注册/拒绝旧版本、disabled零依赖、原问题/澄清/decoder/预算不变、无本地语义路由或fallback、历史隔离及精确调用计数。首轮定位上述测试绑定和计数遗漏，修复后定向、全量和Spring回归通过；本增量Blocker/Major/未处理Minor为0。该评审为本执行者分阶段对照，不冒充另一名独立人员批准；整体B-CR-001仍Open，尚未通过阶段B最终评审。Java公共合同、安全策略、业务服务及PowerShell未改；Employee/Transaction/es-query-service模块Maven与AST本次未重复，不引用历史数字作为本轮结果。

DR-020的IMPLEMENT/NONLIVE切片现已完成；GATE-KRG-006保持仅实现入口Closed。UAT Deferred、QUALITY Blocked不变。新增真实e2e/model/search/embedding/rerank均0，三批累计仍5/12/8/4/4；没有run-04或新manifest。V5实际选域效果缺证据，Summary V4必要引用覆盖仍待原意/gold/指令一致性核查，不能事后改判run-03。设计提交`84939c6`、代码提交`c9dfe6e968a16395dea07d2206fa3471d3893972`；状态提交及推送由Git日志和交付报告记录。L1仅更新当前绑定元数据，未改变KQ-AD-013/016或提升架构版本；当前L2/P3/UAT/索引分别为v1.19/v2.45/v1.23及对应版本引用。

### 20.16 摘要覆盖与验收意图定向核查

起始HEAD=`36a59b1fb51f2ad91aabb0504090e2569c02bc18`，工作树clean且与origin/codex一致。上一轮属于有代码、测试和提交的实际推进；本轮先只读核查L1 KQ-AD-016、L2_01_02 §9/DR-KEV-008/017、UAT_01 §14及冻结KB-015a，不读取凭据或启动真实运行。这里记录证据边界和待决策事项，不在P3新建摘要语义权威。

| 核查点 | 直接证据 | 定向结论及影响 |
|---|---|---|
| 原文是否在送入Summary前丢失 | run-03历史测试复核两项gold的内容hash，Evidence排名2/4 | 两项均已进入输入；不建议以本例为依据修改语料、扩大窗口或Evidence配额 |
| validator是否漏实现已要求的本地检查 | L2_01_02 §9.2与`summary_validation.py::validate`均为outcome/点数/ref/连续子串/大小等确定性检查；不实施自然语言覆盖判断 | 符合该确定性合同；不建议把它改为行业关键词/分类推理器，也不以完整性通过证明答案充分 |
| coverage是否证明最终答案引用覆盖 | `summary_validation.py`从bundle复制检索域coverage，不根据最终points重新计算 | 两域检索完整与最终只引用一个域可以同时成立；当前字段不可外推为答案完整率，不修改公共DTO或历史结果 |
| 问句与双条款预期是否无歧义 | KB-015a问“生活服务中的住宿服务如何定义”，冻结requiredGold为lodging+living；Summary V4只要求显式独立要点，且单条足够时不得冗余引用 | 冻结判定仍明确为Failed；但“给定分类语境”与“请求证明分类”的自然语言解读并不唯一，现有有限证据不足以把漏引父分类唯一归因为Summary Prompt缺陷。该意图边界应先明确，不能仅为过测强制每次多引一条 |

新增`tests/unit/knowledge/evidence/test_summary_proof_boundaries.py`六项纯本地反证，直接沿用上述确定性合同：两种合成问句×单/双引用证明合法引用不等于语义覆盖；双域bundle/单域引用证明coverage来源；模型主动insufficient仍无结果。所有内容为合成数据，不接入LLM/ES/BGE，不导入gold参与生产，不改变现有断言。该测试是已知证明边界的刻画，不把不完整回答登记为语义正确。

实际命令（agent-runtime，显式PYTHONPATH=src）：新增测试+summary_validation_reasons+summary_task_v4+run-03 history定向24 passed；随后`python -m pytest tests/unit/knowledge/evidence tests/contract/knowledge/test_summary_task.py tests/contract/knowledge/test_summary_task_v2.py tests/contract/knowledge/test_summary_task_v3.py tests/contract/knowledge/test_summary_task_v4.py tests/integration/knowledge/test_stage_b_production.py tests/integration/knowledge/test_summary_v4_composition.py tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/system_e2e/test_knowledge_stage_b_run_02_history.py tests/system_e2e/test_knowledge_stage_b_run_03_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q --tb=short`为99 passed，1条既有LangGraph预告；新测试compileall通过。生产src、case/gold、三批历史及阶段A evidence相对起始HEAD均零差异。没有生产/Java/PS修改，本轮不重复全仓、Maven、mypy或AST；§20.15结果是上一轮实测，不冒充本轮执行。

按实现技能的focused路径只补充已批准§9.2的证明边界测试，再进行一次定向代码对照复核：测试没有放宽validator、调用模型或改判历史，未发现该测试增量的新增代码问题。此次无架构/L2语义修订，无整份设计或阶段B正式通过结论；阶段B核心UAT及整体评审仍未完成。

下一步有两种不同影响范围，尚未采用：A，保持原问句及双条款gold，明确与答案相关的显式分类上下文也须证据支持，然后先修订L1/L2并评审新的Summary任务（旧V4和validator不改）；B，另立明确询问“定义及所属分类依据”的新问题，同样保留两条款要求，不能覆盖旧case或声称同题效果改善。不得自行把原gold减为单条，不得在看到结果后修改本批问题或规则。为保持原验收目标，优先建议A，但其分类上下文语义需确认后再实施，不能仅在下位Prompt中暗改。无论选择哪项，都不授权自动开启新付费批次。UAT仍Deferred、QUALITY仍Blocked、B-CR-001仍Open；本轮新增全部真实调用0，累计计数不变，无run-04。

### 20.17 Summary V5 分类上下文证明切片

起始HEAD为 `993321ba1c8e0cba8da5136492cd99f12ee1bbb0`，工作树clean。用户明确采用§20.16方案A，授权恢复L1/L2语义修订、评审和非live实施；该回复不包含新付费批次。上位需求/L0的本次授权原文支持原则不变；唯一语义权威为L1_01 KQ-AD-017→L2_01_02 DR-KEV-027，组合根由L2_01_00 DR-KFLOW-012消费，不在P3复制规则。

本切片按“设计→三轮内审→只读独立复评→Summary V5与单绑定→合同/集成/历史/全量验证→代码复评”推进；不新增工作包或门禁。GATE-KRG-006仍仅为实现入口Closed，既有IMPLEMENT/NONLIVE Done只证明其已记录切片；本增量未验证前不计Done。UAT Deferred、QUALITY Blocked、整体B-CR-001 Open。真实效果须以后续新绑定授权验证，累计预算不因任务升级重置。

初始待验证落点：新task文件、bootstrap唯一Summary5与旧版本拒绝、当前测试迁移及历史测试作用域隔离。V1～V4、validator、case/gold、run-01～03、阶段A资产全部只读；无需Java/HTTP/Schema、索引、策略或额外模型任务变化。只提交本目标文件。

三轮内审已完成：第1轮核对用户原意→L0原文支持→KQ-AD-017，明确只覆盖相关显式类别、无关背景不扩展且单条足够时不凑双引；第2轮核对V4公开definition、输入/Prompt/quote预算及validator职责，明确分类清单必须保留归属上下文、不能拼接同ref，修复流程实施范围仍排除Summary的旧表述；第3轮核对测试/gold/历史/DAG与缺证据状态，strict发现DR-KEV-027未列入规则目录，补齐后通过。

随后冻结内容、按design-doc-review执行L1→L2→跨层只读复评：KQ-AD-017能治理DR-KEV-027，DR-KFLOW-012只消费版本绑定，P3/UAT不重定义语义；公开合同、责任、数据/权限、预算、失败、回滚及测试可执行性均闭合。该增量S0=0、S1=0、未处理S2=0，允许Summary V5及非live测试；无实现/真实效果通过声明。复评为本执行者的独立阶段，不冒充另一名人员/子代理评审。L1与两份L2/P3 strict最终均0 errors/0 warnings，后续代码必须另行复核；UAT/整体质量状态不变。


Summary V5已完成实施及non-live复评：新增`summary_task_v5.py`，仅以V4公开definition/build_request和不可变替换扩展Prompt与version；bootstrap唯一Rewrite5/Summary5并拒绝旧任务。Prompt为2963 UTF-8 bytes，SHA-256=`fee1a061fd68f49198a8832e222cdebdb6ec6f78cf95b48f5f10fd6bdc494e96`，小于既有8192上限。输入JSON32768bytes/1～8条、任务外层49152bytes、输出1536tokens、5points/512字符/ref唯一、parser和validator全部保持原约束；L2补充了双层预算说明，不是放宽。没有新依赖、公共合同、配置开关、索引、授权或额外模型任务。

本增量合同测试验证除了version/Prompt以外definition/request逐字段相等；生产fake覆盖合成分类+定义的单/双ref、缺证/冲突返回insufficient、非法ref/重复/非子串/超长/额外字段、模型异常/超时/取消。所有成功quote精确比对；Business send显式拦截且计数0，JWT仅透传读取端，observations/log不含正文或JWT。fake缺证/冲突由测试响应指定，不能声称模型会自行识别语义。旧wire测试从其显式组合根获得期望Summary版本，当前独立合同断言5/5；run-03测试仍从冻结Git加载4/4，不放开生产版本守卫。

| 本次实际验证命令或范围 | 结果 |
|---|---|
| agent-runtime，PYTHONPATH=src：`python -m pytest -q tests/contract/knowledge/test_summary_task_v5.py tests/integration/knowledge/test_summary_v5_production.py tests/integration/knowledge/test_summary_v4_composition.py tests/integration/knowledge/test_rewrite_v4_provider_boundary.py tests/contract/knowledge/test_provider_registration.py` | 修正新增测试预期后48 passed |
| 上述5文件追加`tests/integration/knowledge/test_evidence_stage.py tests/unit/knowledge/evidence tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/system_e2e/test_knowledge_stage_b_run_02_history.py tests/system_e2e/test_knowledge_stage_b_run_03_history.py tests/system_e2e/test_knowledge_stage_b_uat_v3.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py`，同一pytest -q命令 | 复评补强断言后156 passed；当前和历史绑定分别验证，Business35/Knowledge37既有追踪通过 |
| `pwsh -NoProfile -File agent-runtime/scripts/run-nonlive-regression.ps1` | 正式隔离host/preflight14 passed；全量1857 passed/27 opt-in skipped/0 failed，172.44秒，1条既有LangGraph预告，临时环境清理完成；其后仅补强新测试的Business拦截及quote精确断言，已由上述156项复跑覆盖 |
| agent-runtime：`python -m mypy --strict src`；`python -m compileall -q src tests/contract/knowledge/test_summary_task_v5.py tests/integration/knowledge/test_summary_v5_production.py` | 125个生产文件类型通过，编译通过 |
| agent-service：`..\serviceCenter\mvnw.cmd '-Dagent.runtime.python=C:\Python312\python.exe' '-Deureka.client.enabled=false' test`；子进程PYTHONPATH=D:\codex\agent-runtime\src，stub/Knowledge默认false，移除进程Key，测试显式fake | 最终40 tests/0 failures/0 errors/1 opt-in skip；Access/Business/Knowledge Spring→Runtime实际执行 |
| L1 Core/Knowledge、两份L2 strict；P3 strict；历史与敏感扫描；git diff --check | 当前结构及追踪0 errors/0 warnings；V1～V4与validator字节一致，run-01～03/P5历史验证通过；Stage A build/asset/UAT/release四项SHA与§19.6相同；目标差异敏感模式0命中，无历史/业务服务/索引变更 |

未隐藏首次失败：新测试将Model外层预算误写为输入JSON预算，并把现有insufficient有限reason误期望为null，首轮3 failed/45 passed；核实V4和现有失败映射后修正测试及L2预算说明，不改生产行为。Maven首次参数未加引号，被PowerShell拆解，未进入测试；修正引号后Access因基础Python未安装源码而liveness失败，日志明确ModuleNotFoundError，另外Business/Knowledge E2E通过；仅给当前Maven进程设置绝对PYTHONPATH后整模块通过，不修改全局配置或测试断言。

本增量正式代码对照复核1轮、修复后复评1轮：依据DR-KEV-027及DR-KFLOW-012核对公开definition复用、单绑定、disabled、预算/安全/失败/取消、历史隔离与测试。首轮补强测试对Business零调用及真实quote内容的证明；复评无未关闭Blocker/Major/Minor。状态同步时清除“建议新增”和旧当前Summary4描述，并修复L1 Core两项版本引用；预算层次及新运行绑定当前批准任务版本经只读设计复评，无语义扩权。审查均由本执行者分阶段完成，不冒充另一名独立人员批准；没有宣称阶段B整体正式评审通过。Java业务模块源码、公共DTO、PS均未改，Employee/Transaction/es-query-service/common-security Maven和PS AST本轮未重复。

设计提交`60345fc`；代码提交`73a3cfa0aeb63933784d77436bf4e5bb93ba280a`；状态提交及推送见Git日志和最终交付。DR-KEV-027及当前组合根的IMPLEMENT/NONLIVE切片已完成。Stage B UAT仍Deferred、QUALITY仍Blocked、B-CR-001仍Open：Rewrite5/Summary5真实语义缺证据，冻结P0/gold不变。新增真实e2e/model/search/embedding/rerank均0，三批累计仍5/12/8/4/4，Business/answer/retry/resume0；没有读取LLM_API_KEY、生成新manifest或run-04，不将剩余总预算解释为新的执行授权。

### 20.18 新授权独立V5验证批次

用户在明确的结构化授权请求后回复“授权，并继续”，仅授权准备并执行一次新的独立V5验证批次。起始HEAD为`27d01a2cdb306cc20a10278f201402409a8b60e4`，工作树clean、与origin/codex一致。新run为`knowledge-stage-b-uat-v4-20260904-run-04`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-04`；不是任何旧批的续跑。原10例、顺序、gold及判据不变，selection-v4/Rewrite5/Summary5。单批上限10端到端/30模型/40search/20embedding/20rerank；加前三批实际5/12/8/4/4后累计最大15/42/48/24/24，不超过原20/60/80/40/40，Business/answer/retry/resume仍0。任一失败停止，不授权run-05或额外付费批次。

新增`tests/system_e2e/knowledge_stage_b_uat_v4.py`及直接fake测试；仅在独占CLI作用域复用冻结runner/预算/生命周期/诊断，实现当前任务和Prompt绑定、前三批hash/实际计数、manifest Schema4、诊断版本v2。诊断仍为KB-DIAG-001原有限字段/枚举，仅任务白名单改为5/5；V5复用同一V3 decoder，原异常/取消透传，退出恢复全部绑定。生产src、Prompt、gold、validator、索引/alias、原runner及全部历史资产不改。prepare/check-environment不读取Key；新资产、测试及授权账提交后才能冻结，execute必须显式传入manifest SHA并验证干净HEAD。此节只授权该已批准设计的验证，不改变L1/L2语义或核心P0通过条件。

准备与执行结果将在本节后续追加；尚不关闭B-CR-001或质量包。先完成定向fake、当前生产根/历史回归、正式隔离回归、类型/编译及本增量代码对照评审，再冻结和只读readiness，最后执行一次真实批次。

准备验证：新入口最终48项fake通过；此前新/旧runner、历史与V5生产根/合同组合159 passed。正式隔离入口Transaction host/preflight14 passed，全量non-live1901 passed/27 opt-in skipped/0 failed（237.12秒，1条既有LangGraph预告）；该全量收集后仅追加4项预算/历史篡改反证，由最终48项覆盖。strict mypy125生产文件及compileall通过；P3和两份L2 strict均0 errors/0 warnings；阶段A四项最终hash、前三批资产及生产src不变，目标差异敏感模式无命中。9200/8908/8909只读健康检查200，未读取模型Key或新增真实调用。Java/公共合同/PowerShell无改动，本准备切片不重复Maven/AST，后续真实链路通过隔离Spring入口执行。

本增量正式代码对照评审1轮、补强测试后复核1轮：核对DR-KFLOW-012/017/020、DR-KEV-027及KB-DIAG-001，覆盖V5真实wire projection、旧Prompt拒绝、原10例判据等价、累计计数/历史篡改、失败停止、异常/取消及绑定恢复、有限诊断、owned进程和日志清理接缝。首轮新测试因依赖pytest mark顺序产生收集错误，按mark名称定位后修复；未改断言语义。未发现本增量未关闭Blocker/Major/Minor，允许冻结执行；不等于整体B-CR-001关闭。评审为同一执行者分阶段对照，不冒充独立人员批准。另按已批准V5规则纠正两份L2当前实现摘要残留V4，仅状态/引用修正，不改变语义或架构版本。

### 20.19 run-04终态、有限损失诊断与评审

准备提交及frozen HEAD=`77dad25db25205b3242e5a3b937de318a82d1053`，已推送origin/codex后在clean工作树冻结。manifest绑定308项源码/配置和258项可执行资产，selection-v4/Rewrite5/Summary5；case、gold、顺序、原判据及Stage A corpus-a5的alias/UUID/两域snapshot均与旧批相同。按§20.18执行唯一一次`prepare → check-environment → execute --manifest-sha256`，后者退出1并形成不可变`status=failed / failureKind=null`：这是用例验收失败，不是启动异常。

六项有限资产按原始字节归档至`agent-runtime/tests/system_e2e/knowledge_stage_b_run_04/`，`.gitattributes`使用精确目录binary以阻止换行归一化。旧三批及历史P5/阶段A不改。

| 资产 | SHA-256 |
|---|---|
| manifest.json | `f6b745545e2808ea776744360bb9a879cc520e12717a6479f9b8086d671f5848` |
| environment.jsonl | `ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7` |
| consumed.json | `0d1448502f7b6d8016716cfdca8509bc4cb799b19eaa962bd6b8ddd7f233661b` |
| journal.jsonl | `176f84c787acbdb8f4083c852dc8ae7cb23612826bf9003a4edee61ce0fab433` |
| evidence.jsonl | `23f3e091e9a3816cf950f5736f14ad8b3fec23f1b7a4607b3aa6c1875100c9e3` |
| result.json | `969e3f8e22b47ea98e6c6230a6289d24e68e911facda967ac25ae296d6e28c48` |

实际执行3例：KB-001 Passed（澄清、零检索），KB-015a Passed（仅policy，lodging/living均有引用），KB-004 Failed（正确双域，law_rate有引用而两项分类条款均未被引用）。其余7例未执行，逐例见UAT_01 §14.11。实际e2e/model/search/embedding/rerank为3/8/6/3/3；四批累计8/20/14/7/7，Business/answer/retry/resume0。本批剩余预算不再有效，没有run-05或补跑。

readiness通过真实auth→Spring→stub Runtime的unsupported冒烟，模型和Knowledge调用0。实际执行经Spring公共入口及当前V5生产对象图；各模型任务均succeeded、`modelFailures=[]`、任务绑定与澄清零调用检查通过。结束记录证明clientsClosed、ownedProcessesStopped、rawLogsDeleted、secretScanPassed均true，隔离端口无残留监听。没有保存模型原文、完整业务/知识正文、JWT或密钥。

#### 20.19.1 有限根因矩阵

| 问题/边界 | 原文hash排名证据 | 判断与证据强度 |
|---|---|---|
| KB-015a原精确反例 | 当前final/Evidence中lodging第2、living第3；仅policy，最终两条原文校验true | 本次精确反例已通过，强证据；不能外推模型稳定性或完整专项通过 |
| KB-004召回/域 | policy keyword：lodging第3、living第8；两者未进policy vector top20；plan为policy+law | 本例原文不是缺失、必要域未漏；强证据。不能由向量缺失推断索引/embedding损坏 |
| KB-004排序→final | policy rerank39：lodging第4、living第28；final20：lodging第9、living缺失 | living在有限最终选择处丢失，强证据；未保留改写文本/分数，不能确定BGE语义排名差的更深原因 |
| KB-004final→Evidence | final20有lodging第9；Evidence8无lodging/living，只有law_rate第4 | 第二个独立损失点，强证据；未保留正文/字节/文档配额诊断，不能断言仅总数8导致lodging落选 |
| KB-004摘要/公开结果 | Summary输入hash无两项gold，输出HTTP200/success、2条合法引用，但原条款判据false | 输入不足且结果仍未满足完整问题，专项失败。结构、引用存在及双域覆盖不能证明语义覆盖；不指认未保存的模型原文 |

结合个人学习项目背景，优先处理“必要语义证据的选择与不足判断”，不新增门禁/层层冻结，不以反复付费或扩大topK试错。DR-KRET-027只保每域keyword/rerank首位锚点和稳定有界轮转，DR-KEV-026只保锚点/域/每文档3/总8/32768字节，并没有可验证的逐要点覆盖信号。现有实现和10项排序/Evidence fake对照这些有限合同一致；该合同能力不能保证冻结核心P0所需的语义覆盖，属于效果/设计充分性缺口，不能直接归咎于数组截断代码错误。

后续最小处理位置为`quality_ranking.py`及`evidence/builder.py`的选择依据与L1/L2相应合同：先用有限排名重放/合成反例比较域内关键词与语义排名预算、Evidence条款多样性及不足判断，证明一般性且不注入gold/caseID；方案需先评审再编码。原文缺失、索引重建、扩大权限及公共DTO不在当前修复建议内。暂不改Prompt、topK、配额、validator或生产代码；本次证据不足以证明某个参数修改必然修复。明确不自动新建付费批次。

#### 20.19.2 运行后证据与代码复评

新增6项历史审计覆盖六文件字节、frozen Git来源、精确授权/Prompt/前批累计、3例逐项终态、8条付费journal、7例未执行、两处原文hash损失和清理/有限字段。首轮历史断言把计划域顺序误当作已排序citationDomains顺序，得到1 failed/15 passed；核对原结果及原collector后分别锁定两个精确列表，未排序掩盖差异或改运行结果。复测四批历史、新入口48项及排序/Evidence10项共77 passed（48.50秒，1条既有LangGraph预告）。

本次准备代码评审1轮+补强复核1轮，运行后正式代码/证据对照评审1轮+历史断言修复复核1轮。范围限新runner/测试/归档及DR-KFLOW-012/017/020、DR-KEV-027和KB-DIAG-001复用边界；额外定向核查DR-KRET-027/DR-KEV-026的现行排序/Evidence。B-R4-001（历史测试的域顺序错误）已关闭，归档字节、原判据、预算、日志、失败停止及不续跑未发现本增量未关闭Blocker/Major/Minor。评审为同一执行者分阶段复核，不冒充独立人员。整体B-CR-001仍Major/Open：跨域核心P0失败、7例未执行；阶段B正式整体评审和专项UAT均未通过。

当前UAT包Deferred、QUALITY Blocked，GATE-KRG-006仍仅实现入口Closed。V5不再描述为完全未测量，但只认可本次有限2例通过；P5最新有效partially_effective及既有35/37功能追踪与本专项分离。L1/L2只同步实施摘要，P3/UAT版本保持本次v2.47/v1.25，不作语义变更或新增设计批准。Java/公共合同/PowerShell未改，本次不重复其Maven/AST，准备阶段全量隔离结果见§20.18；运行后额外验证与提交结果在后续记录补齐。

运行后最终验证（均实际执行，Python命令工作目录为agent-runtime）：

| 命令/检查 | 结果 |
|---|---|
| `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1` | 显式安装当前源码的临时隔离环境：Transaction host/preflight14 passed（3.67秒）；全量1911 passed/27 opt-in skipped/0 failed（209.69秒）；1条既有LangGraph预告，临时环境清理成功 |
| `python -m pytest tests/system_e2e/test_knowledge_stage_b_run_01_history.py tests/system_e2e/test_knowledge_stage_b_run_02_history.py tests/system_e2e/test_knowledge_stage_b_run_03_history.py tests/system_e2e/test_knowledge_stage_b_run_04_history.py tests/system_e2e/test_knowledge_stage_b_uat_v4.py tests/unit/knowledge/retrieval/test_quality_ranking.py -q --tb=short` | 77 passed；上述全量随后覆盖这些测试及当前Knowledge/Core/Business、35/37原功能追踪 |
| `python -m mypy --strict src` | 125个生产文件通过 |
| `python -m compileall -q src tests/system_e2e/knowledge_stage_b_uat_v4.py tests/system_e2e/test_knowledge_stage_b_uat_v4.py tests/system_e2e/test_knowledge_stage_b_run_04_history.py` | 通过 |
| P3 strict、L1_01 strict、两份变更L2 strict | 均0 errors/0 warnings；本轮只同步已发生的状态，不重新批准语义设计 |
| 四批历史、阶段A、敏感扫描、隔离监听 | 六项新证据归档及暂存blob SHA均相同；308源资产按frozen Git校验；前三批/P5/生产src无差异，Stage A四项最终hash不变；无敏感token模式命中，18090/19201/18080/19091无残留监听 |
| `git diff --check`、`git diff --cached --check`及逐文件暂存复核 | 通过；只有本目标测试、有限资产和状态文档，无用户无关修改 |

准备提交`77dad25db25205b3242e5a3b937de318a82d1053`已推送；有限证据/历史保护提交`af4589c23024599e7acca86340cd7afac862cacd`。文档状态为独立提交，最终SHA/推送与工作树结果见Git日志和交付报告。未执行7例及Java/AST不重复的范围已明确，不用non-live绿灯覆盖本次真实失败。

### 20.20 冻结排名离线重放：排除未经证明的合并策略替换

本次起点为`e231499cb7ec681617ff2e81fce55a5c0af07451`，只增加`tests/system_e2e/knowledge_stage_b_rank_replay.py`及其测试，不修改生产代码、Prompt、配置或历史资产。执行前校验四批全部有限资产哈希；固定原路径和域内rerank次序，以单调合成分数调用当前真实`rank_by_domain`，四条有检索记录均精确复现原final序列。空keyword路径合法，不等于漏失路径；身份冲突、不完整阶段、哈希变化或当前排名不一致均停止，不静默继续比较。

试验只比较同一排名输入下的四种有界合并：keyword优先、rerank优先、keyword+rerank等权RRF、keyword+vector+rerank等权RRF。均保持现有每域首位锚点、跨域轮转及final20；gold只在排序完成后用于有限结果评价，不进入合并函数。该工具不访问服务、不读取凭据、不写运行文件；不产生新的模型、search、embedding或rerank HTTP请求。

| KB-004合并试验 | lodging最终名次 | living最终名次 | law_rate最终名次 |
|---|---:|---:|---:|
| 当前策略精确重放 | 9 | 未入选 | 4 |
| keyword优先 | 7 | 15 | 4 |
| rerank优先 | 9 | 未入选 | 4 |
| keyword+rerank RRF | 5 | 未入选 | 4 |
| keyword+vector+rerank RRF | 7 | 未入选 | 4 |

KB-015a在旧/新两条记录中，各试验均分别保持lodging/living为2/4和2/3。第一批KB-001没有requiredGold，仅验证原排名复现，不作为语义通过证据。结论限于这些冻结输入及四种策略：keyword优先可把living移入final20，但没有试验把全部三项必要条款放进前8；不能据此批准生产排序替换或宣称UAT修复。

证据限制：历史未保留原rerank query、原分数、完整文档身份、正文长度和逐项配额原因。合成分数只复现次序，不代表原BGE数值；合成文档身份不用于Evidence。该工具明确不是Evidence配额/字节、出域或Summary重放：实际selector可因配额跳过前序项，因此“前8不齐”也不能单独证明其他策略最终Evidence必然失败。现有观察仍只证明原Evidence缺少两项必要原文，不冒充新策略效果。

下一步设计依据：先区分是否需要更准确的域内检索表达、问题要点与候选的关联信号，或文档/条款重复造成的选择损失。必须给出不依赖gold/case/文档特判的一般性方案，并按既定设计评审流程处理；当前证据不足以唯一批准修改RRF权重、topK、每文档配额或Summary。不得恢复付费批次来替代诊断。

验证与定向对照：新增20项反证覆盖零外部IO、有限输出、四条精确重放、历史篡改、生产排名漂移、空keyword、非法身份/阶段、锚点/去重/数量与gold隔离。首轮1 failed/19 passed系新测试误引用第一批历史模块不存在的RUN_ID常量，改为读取已校验result的runId后恢复；未改旧测试或运行证据。新测试、四批历史及排序/Evidence定向组合49 passed（42.57秒）。`python -m mypy --strict src`通过125个生产文件，`compileall`通过。按DR-KRET-027/DR-KEV-026与本节有限诊断边界执行一次定向代码对照：排名重放、生产无改动、历史保护及gold离线使用均符合；真实语义修复仍不可验证。该核查不是阶段B整体正式评审通过。

本次最终实际命令（Python/PowerShell测试工作目录为agent-runtime）：

| 命令/检查 | 结果 |
|---|---|
| `python -m pytest tests/system_e2e/test_knowledge_stage_b_rank_replay.py -q --tb=short` | 20 passed（0.13秒） |
| `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1` | 显式安装当前源码的临时隔离环境；Transaction host/preflight14 passed（3.59秒），全量1931 passed/27 opt-in skipped/0 failed（243.68秒）；1条既有LangGraph预告，脚本退出0 |
| `python -m mypy --strict src`；`python -m compileall -q src tests/system_e2e/knowledge_stage_b_rank_replay.py tests/system_e2e/test_knowledge_stage_b_rank_replay.py` | mypy125生产文件通过；compileall通过 |
| P3计划`--strict`；历史hash；目标差异敏感模式扫描 | 0 errors/0 warnings；四批历史、P5及Stage A四项最终hash不变；未命中凭据/JWT模式 |
| `git diff --check`；`git diff --cached --check`；逐文件暂存差异复核 | 仅本节及两个诊断测试文件；无生产src、配置、索引/alias或用户无关改动 |

当前QUALITY仍Blocked、UAT仍Deferred、B-CR-001仍Major/Open；run-04终态与2通过/1失败/7未执行不变。本轮没有新run或付费请求，架构及UAT语义不变，不新增Gate或无关版本升级。本测试诊断增量不重复Maven/AST；没有新的Spring真实服务或效果UAT，不能用上述non-live通过替代。提交SHA及推送状态由Git日志与本次交付报告记录。

### 20.21 只读补证：问题聚焦、总条数与同文档配额

起始HEAD=`ff7cf53ed8d831df02ad0b4287b8ad94b2273f74`，工作树clean。该增量只做离线诊断和当前合同反例测试，不是第五批UAT、历史重跑或生产算法修订。没有读取LLM_API_KEY、创建新run、启动/停止服务或写索引。原run-04终态和六项hash不变。

读取Stage A外部受控workspace的build/chunk有限元数据，再对当前a5物理索引执行限定到KB-004冻结73个chunk的只读检查。UUID仍为`SurWRSglRd6ZRddEBWy2Sw`；73份实际content按服务合同计算NFC/UTF-8 SHA-256，全部与冻结候选hash一致。初次误用物理contentHash比较失败；Java `KnowledgeSearchService.mapCandidate`实际返回现算正文hash，改按该合同核对后通过，不能把此前诊断误差描述为索引变更。没有保存正文、完整BGE响应、向量、凭据或真实业务数据。

#### 20.21.1 已确认与未确认的根因

| 观察 | 结论与证据强度 | 不得外推的结论 |
|---|---|---|
| 原final第9的lodging为58字符/172 UTF-8 bytes；前8已全部入选，其中同文档仅1条 | 强：原遗漏首先由总8条限制触发，不是该条的同文档3条配额。已有8条原文合计约13.4KB；小条款位于第9不能绕过总数 | 不能因此提高总8或32KB，也未重放原始Summary输入全部metadata字节 |
| 固定39个policy候选，仅改变本地BGE query，人写的三种聚焦表达使lodging第1、living第3～4；均不含无关法律/税率词 | 强：该候选集的重排对问题表达敏感；中：提示每域聚焦可能改善候选顺序 | 原run-04未保留模型query，不能断言当时模型生成了哪一句，更不能把人工表达当作LLM UAT通过 |
| 保留“增值税”的两种聚焦表达，living仍第27/13；原用户整问对照第26 | 强：在同一39候选中，强制保留领域词面不是可靠的相关性保护；领域ID与原问题仍可保留背景 | 只测试有限表达；不能认定所有带税务词的问题都会失败或建议本地删词规则 |
| 采用第一次聚焦表达及域内rerank优先轮转的手工反事实，lodging全局第1、living第7、law_rate第2；living是同一文档第4个候选 | 强：在该反事实中，第7条会被现行每文档3条限制排除；这是不同于原运行的选择损失 | 不是原运行遗漏原因，也不是完整新流水线：law顺序冻结、未重新检索/摘要，未模拟全部payload bytes |
| 检查短片段是否为必要条款的通用标题/前缀，未得到可稳定删除的关系 | 证据不足：不采用短文本长度黑名单、酒店关键词、文档ID或未经证明的标题删除 | 不把“短”直接当作无用或重复，更不修改Stage A切片/正文 |

本次local BGE诊断共7次、只读ES HTTP共9次（含UUID及有限metadata/content校验）；外部模型、typed Knowledge search、embedding、Business、answer、retry/resume均0。前4次是聚焦表达及选择反事实，后3次是含税务词和原问题对照；不是请求预算补跑，不写任何历史运行计数。全部读取只发生在诊断工具上下文，Agent生产路径仍只访问es-query-service。

用于复核的人工诊断表达如下，均不是已恢复的模型输出。输入限同一39个policy候选，BGE返回model=`BAAI/bge-reranker-v2-m3`，index唯一、文本与内存输入一致、分数有限；输出只记录名次。首行执行两次，第二次用于上述选择反事实，其余各一次；不以这些表达创建逐句在线规则。

| 人工诊断query | lodging域内名次 | living域内名次 |
|---|---:|---:|
| 住宿服务的政策分类 | 1 | 4 |
| 住宿服务属于哪类服务 | 1 | 4 |
| 住宿服务是指什么 | 1 | 3 |
| 住宿服务的政策分类和增值税法的税率规定是什么？ | 8 | 26 |
| 增值税中住宿服务的政策分类及定义 | 1 | 27 |
| 增值税中住宿服务属于哪类服务 | 1 | 13 |

#### 20.21.2 设计取舍及授权边界

当前`DR-KRET-027`要求关键词首位和rerank首位为强制锚点；`DR-KEV-026`明确每文档3/总8/32768bytes。当前代码符合这两条合同，不能把现有配额行为直接修成代码bug。`DR-KEV-017/027`的语义完整性主要由模型指令及UAT约束；§9.4又明确validator不做语义覆盖判定，输入domain coverage不能冒充答案完整性。

| 候选处理 | 范围与判断 | 当前状态 |
|---|---|---|
| 仅放大topK或调整RRF权重 | §20.20未证明可让全部必要Evidence入选；增加窗口不解决同文档配额 | 不建议无证据实施 |
| 每域query只聚焦分配给该域的子问题，由逻辑domain与原问题维持背景 | 保持V3 exact形状、显式日期/数字/否定/纳税条件Guard；若采用必须新Rewrite版本及评审，不能用本地删词或关键字纠域 | 有限本地证据支持继续设计；尚未批准或实施 |
| 以rerank相关性代替强制关键词锚点，并重新评估同文档硬配额 | 会改变DR-KRET-027/DR-KEV-026；即便保持总8/32KB、读取/出域/引用不变，也改变现行每文档限制，存在单文档挤占和错误高排名风险 | 方案选择待确认，不直接把3改8，不放宽现行validator |
| 引入要点规划/证据簇或额外模型选择器 | 新合同及调用面更大，当前证据不足以证明必要 | 暂不采用，避免为单例建新流程 |

需要确认的最小边界：是否允许把“同文档最多3条”作为质量选择策略重新设计，而非不可调整的硬约束。若允许，先在已授权Knowledge L1及L2_01_00/01/02、P3/UAT范围内比较有界替代方案，完成三轮内审及正式复评，再实施；总8、32768bytes、5points、512字符quote、读取授权、三层出域、连续子串、唯一ref与历史资产仍不得放宽。该确认不包含新付费批次。当前没有采用或批准新的方案。

#### 20.21.3 可复现合同反例与检查

新增`tests/unit/knowledge/evidence/test_stage_b_selection_counterexamples.py`，只用合成公开文本和匿名文档组调用现行真实IntegrityVerifier/Selector，8项覆盖：原观察顺序形状的总数阻断、聚焦反事实形状的文档配额阻断、同文档3/4/5条与域覆盖不等于答案覆盖、锚点不能绕过配额/字节，以及全部现行上限不变。测试不调用网络、不读gold/真实正文、不修改限额；不是原运行的全文/字节/语义重放。

首次源码树pytest因未显式安装/设置src而收集失败，改用命令进程内PYTHONPATH；不改全局环境。随后一项字节fixture过长，被已有candidate合法性检查先拒绝，改为4条各自合法、合计越界的合成片段，保持原字节断言，未放宽生产规则。新增反例、当前排序和原排名重放组合38 passed。后续最终回归、定向对照、hash与Git结果在本节末补充。

仅执行上述边界的定向设计核查：现行代码对配额/锚点合同符合；“这些启发式保证问题所需条款完整”证据不足，不能据此给整个设计通过结论。QUALITY仍Blocked、UAT仍Deferred、B-CR-001仍Open；新方案的三轮内审、正式设计/代码评审及真实专项UAT尚未完成。

本增量定向代码对照1轮、修复后复核1轮：检查DR-KEV-003/026、匿名合成fixture、原文/网络零依赖、先Integrity后Selector及历史保护。发现新fixture仍沿用单域successful_paths，已按选中域补齐两条路径；锚点反例也限定每域两个，避免用不可能的上游形状证明配额问题。定向复核符合当前合同；不作整体代码评审通过判断。没有语义性L1/L2修改或新设计批准，P3保持v2.47，仅追加诊断与执行记录。

| 本轮最终命令/检查 | 实际结果 |
|---|---|
| `python -m pytest tests/unit/knowledge/evidence/test_stage_b_selection_counterexamples.py -q --tb=short` | 8 passed（0.08秒）；命令进程内PYTHONPATH指向src |
| 上述文件 + `tests/unit/knowledge/retrieval/test_quality_ranking.py` + `tests/system_e2e/test_knowledge_stage_b_rank_replay.py` | 38 passed（0.21秒） |
| `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1` | 正式临时隔离安装：host/preflight14 passed（3.40秒），全量1939 passed/27 opt-in skipped/0 failed（226.46秒），1条既有LangGraph预告；脚本退出0 |
| `python -m mypy --strict src`；`python -m compileall -q src tests/unit/knowledge/evidence/test_stage_b_selection_counterexamples.py` | 125个生产文件类型通过；编译通过 |
| P3 `--strict`、`git diff --check` | 0 errors/0 warnings；差异检查通过 |
| 四批历史/P5/Stage A最终hash、生产src差异、有限token模式扫描 | 历史回归及Stage A四项精确hash通过；生产src无差异；目标文件无凭据/JWT模式命中 |

Java、公共接口、生产配置及PowerShell无改动，本增量没有重跑Maven、Spring真实入口或AST；不能以Python回归替代尚未执行的专项7例。当前只提交本节及合成反例测试，提交/推送SHA以Git日志和交付报告为准。

### 20.22 Rewrite V6 每域子问聚焦切片

起始HEAD=`32fa171e2defcff726cd559bb175b94947e704fe`。§20.21的有界诊断支持检索表达影响域内排名，但没有恢复历史模型query，也不能证明新Prompt能稳定生成正确表达。本切片只替换V5中要求每域复制全部税务/法律背景的笼统指令；作用于本域的显式税种、日期、数值、否定等条件不允许删除。模型负责语义归属，不新增本地删词或行业规则。

设计：L2_01_00 v1.21 DR-KFLOW-021三轮内审完成，独立于修订操作的第1轮只读L2/跨层复评通过（S0=0、S1=0、未处理S2=0），允许新V6任务、唯一生产绑定和直接fake测试的非live实施。该分阶段审查由同一执行者完成，不代表外部人员批准。计划DAG不变；本切片不依赖待确认的Evidence配额，不关闭QUALITY、UAT或B-CR-001。

实施前状态：生产仍为Rewrite5/Summary5，V6未实施。排序/锚点、Evidence每文档3/总8/32768bytes、Summary5及validator保持不变；不读LLM_API_KEY、不启动真实业务服务、不创建run-05、不执行任何模型outbound。run-04仍2 passed/1 failed/7未执行；不得用非live测试外推真实语义通过。实现、验证和代码复评完成后在本节追加实际结果。

实施：新增`knowledge/rewrite_v6.py`，唯一替换V5的一段背景指令并验证旧片段恰好出现一次；新指令4946 UTF-8 bytes，其余请求、decoder identity、16384输入/512输出/8000ms预算不变。`bootstrap.py`唯一绑定Rewrite6/Summary5并拒绝旧Rewrite5；未修改旧任务、semantic_planner、QuestionSemanticGuard、QuestionEgressGuard、排序、Evidence、Summary或公共合同。新增V6合同/合成分域接线测试，迁移现行根的版本断言，保留全部原成功/异常/零调用断言。

回归首轮：定向91 passed（50.48秒）。正式隔离入口host14 passed（4.63秒），全量1961 passed/27 skipped/19 failed（265.93秒）。19项均已定位：1项注册合同和12项Summary当前根测试仍断言Rewrite5，6项run-04诊断使用了当前V6根而不是其冻结V5根。前两类仅更新为批准的6/5绑定；第三类沿用历史run-03的隔离方法，从run-04冻结提交`77dad25db25205b3242e5a3b937de318a82d1053`只读提取组合根类，测试结束由monkeypatch恢复。现行测试引导源变更可辨识，历史源字节继续从冻结Git校验；四批runner、manifest、gold、结果和hash未修改，也不放宽诊断schema或原断言。修复组合68 passed（40.79秒）；需等完整复验后确认本切片回归状态。

Spring接入本轮实际验证：agent-service运行`..\serviceCenter\mvnw.cmd '-Dagent.runtime.python=C:\Python312\python.exe' '-Deureka.client.enabled=false' test`，子进程使用当前src、stub并移除进程级Key，40 tests/0 failure/0 error/1 opt-in skip，BUILD SUCCESS（34.240秒）；Access、Business、Knowledge三个Spring→Runtime E2E均执行，测试自行管理和关闭临时Spring/Python服务，不连接真实业务系统。strict mypy126生产文件及compileall通过；历史run-04六项和Stage A四项SHA-256均一致。没有外部模型/真实search/embedding/rerank调用，未改变已有服务或其环境。

最终完整复验：`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`退出0；显式安装当前源码的临时环境中host/preflight14 passed（4.33秒），全量1980 passed/27 opt-in skipped/0 failed（263.68秒），1条既有LangGraph预告。该入口包含Knowledge unit/contract/integration/evaluation、Business/Employee/Transaction/Core、四批历史与P5，以及35/37功能追踪校验；临时环境由脚本安全清理。27项跳过不计为真实验证通过。

代码正式对照复评第1轮：范围限定DR-KFLOW-021及生产单绑定、直接合同/fake和历史测试引导；逐项核对指令唯一替换、同一decoder/预算、Guard不变、单次规划、原问Summary、disabled零依赖、失败/取消/client关闭、无Business fallback及历史保护。验证阶段的版本迁移和历史根隔离问题均Fixed；最终Blocker=0、Major=0、未处理Minor=0，本非live切片通过。该结论不关闭阶段B总体`B-CR-001`，不证明模型语义或必要Evidence覆盖。

文档状态同步后执行只读跨层复核：L1当前绑定、L2实现触点、P3及UAT_01 §14.12一致；L1/L2_01_02仅更新实际绑定元数据，没有新语义或版本升级。L2_01_00及L2_01_02严格校验、P3严格DAG校验均0 errors/0 warnings；6份目标文档55个本地Markdown链接存在，差异及凭据/JWT模式扫描通过。Java业务模块、PowerShell脚本、索引/alias均未改，本切片不重复其他Maven模块或AST；没有真实模型/业务/本地BGE请求。

阶段B状态仍为QUALITY Blocked、UAT Deferred、B-CR-001 Major/Open。Evidence每文档3条的设计调整仍待用户确认，排序/锚点与Summary不改；V6真实效果Evidence missing，不创建第五批。设计提交与后续实现/状态提交、推送结果见Git日志及交付报告。

### 20.23 恢复授权后的相关性与Evidence选择V2

起始HEAD=`e0cc21de90a3c680aa7acf678dea7642f6ff99b5`，分支codex、工作树clean、与origin/codex一致。用户最新明确“授权并继续目标，现授权达成目标所需的各类权限，后续无需单独要求权限”，解除§20.21方案选择的暂停。按该授权先修订本节及Knowledge L1/L2、UAT/索引；不把授权视为设计已评审或实现已通过。

根因沿用§20.21可核实的两个独立反例：关键词强制前排与总8条限制可能挤出相关条款；父文档配额又可能排除同一法规中的第四条必要原文。V2比较保留硬配额、两遍多样性与域覆盖/相关性方案，选择后者：每域语义首位、纯rerank域内顺序轮转、不设额外父文档配额。最终20、Evidence8/32768bytes、5points/512quote、读取/出域/validator/gold均不变，不增加模型选择器或行业特判。

合同链：L1 KQ-AD-014→DR-KFLOW-022（版本生产/消费）→DR-KRET-028（排序）/DR-KEV-028（选择）→当前IMPLEMENT/NONLIVE工作包增量→UAT→QUALITY，DAG不新增节点或循环。原Done只证明旧切片；本次设计、实现、non-live分别在实际验证后记录，不继承Passed。GATE-KRG-006的历史Closed不自动批准新V2，在本增量设计复评通过前受影响实现暂停。

授权边界：允许目标内设计/代码/测试/Git以及通过fake和冻结预检后的一次新独立验证，不能续用run-04。四批累计仍为8 E2E/20模型/14search/7embedding/7rerank；在原20/60/80/40/40总上限内剩余12/40/66/33/33，不因版本升级重置。若准备新批，只能沿用原10例/顺序/gold，单批最多10/30/40/20/20，失败停止、retry/resume0，未消费的预算不授权自动再建下一批。真正绑定的HEAD/manifest及实际调用账在准备后另记；当前没有新run、密钥读取或模型outbound。Stage A索引/alias、公共DTO、权限、历史run资产仍不可变。

V2当前为设计待评审、未实施、未测量。设计内审/正式复评、测试与提交记录在完成后追加；QUALITY和总体B-CR-001仍未关闭。

内审第1轮：比较三种方案并分离原总8条损失与反事实同文档3条损失，补充V1历史、无语义完整保证及L1选择依据。第2轮：逐项核对producer/consumer，补齐V2 planner/plan/两阶段/limits的成对版本与错配拒绝；无公共DTO、模型任务或安全策略变化。第3轮：检查DAG/预算/回滚和跨层追踪，严格校验发现5个DR/TEST/VAL表定义遗漏并补齐；三份L2及P3严格复验均0 errors/0 warnings。

正式设计评审第1轮（仅只读）：范围冻结为KQ-AD-014、DR-KFLOW-022、DR-KRET-028、DR-KEV-028及P3/UAT/ARCH引用；依据REQ-KQUALITY-001～004、L0边界、现行rank/selector/limits/根和历史反例，检查L1→L2与L2→本切片实施准入。发现`B-V2-DOC-001`（S2）：实施依据仍只允许旧V6/Summary切片，与新增V2准入冲突；已切换回文档修订阶段最小同步允许范围和变更记录。该审查与修改分阶段进行，由同一执行者完成，不冒充外部人员批准。

正式只读复评第2轮：逐项回读修改后的7份目标差异及上位约束，B-V2-DOC-001已关闭；V1/V2/legacy解释范围、producer/consumer、配额/预算、安全/失败/取消及回滚闭合，无S0/S1/未处理S2，允许本次V2实施和non-live。三份L2严格结构/追踪与P3 DAG校验通过；不将静态校验当作正式语义评审。GATE-KRG-006的准入现覆盖DR-KFLOW-022/DR-KRET-028/DR-KEV-028；实现与真实UAT仍未完成，不提前关闭QUALITY/B-CR-001。

### 20.24 质量V2实施、回归与环境阻塞

本节取代§20.23“未实施”的时点状态。设计提交为`371631c0a11bb4bc97775ec943ade1f12070ea11`；代码、测试与状态修改尚未提交/推送，不能宣称Git或阶段B收口完成。

实现映射：DR-KFLOW-022对应contracts常量、semantic_planner内部版本、planning/capability透传和bootstrap成对绑定；DR-KRET-028新增quality_ranking_v2.py并由stage按版本选择；DR-KEV-028新增quality_v2()及verifier/selector版本、锚点和限额校验。旧V1排序、旧任务、历史运行及Stage A配置/索引未改。V2不设独立父文档配额，但保留8条/32768bytes、域覆盖、授权/出域及Summary确定性校验。

代码对照设计首轮发现`B-V2-TEST-001`（Minor）：单元测试证明配额错配拒绝，但未直接证明当前Runtime中Summary零调用。已增加真实生产组合根+fake模型/服务的反例，验证evidence_failure、模型仅selection/rewrite、2次已授权search、不执行Summary，修复后定向9 passed。复评核对原问题、内部版本、纯域内排序/跨域轮转、去重、总数/字节、取消、拒绝及历史兼容；本切片Blocker/Major/未处理Minor=0，整体B-CR-001的真实核心P0仍Open。此为同一执行者分离编辑阶段的对照审查，不冒充外部人员批准。

新版本化入口`knowledge_stage_b_uat_v5.py`准备run-05，任务selection-v4/Rewrite6/Summary5和quality-v2；复用原10例、顺序、gold、source-clause verdict和owned服务生命周期。新增manifest Schema5只增加质量版本和第四批累计绑定，有限诊断v3只更新允许任务版本；旧Schema/代码/结果不改。fake证明累计预算、Prompt/版本、原判据、旧quality拒绝、防复用、其他endpoint零调用和作用域恢复。当前只有未冻结的环境预检资产，尚无manifest、consumed、journal或result，没有真实模型调用。

| 本轮实际验证 | 结果 |
|---|---|
| V2排序/V1/选择反例定向 | 初轮36 passed；后续新增同父4条、跨域共享identity、同分及完整Runtime错配反例 |
| current root、V2与Stage B定向 | 53 passed；随后完整Runtime错配所在文件9 passed |
| 新runner fake及run-04历史 | 38 passed |
| `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`（agent-runtime） | 最终host/preflight14 passed；全量2034 passed/27 opt-in skipped/0 failed；1条既有LangGraph预告 |
| `python -m mypy --strict src`；`python -m compileall -q src` | 127个生产文件类型检查通过；编译通过 |
| agent-service `..\serviceCenter\mvnw.cmd '-Dagent.runtime.python=C:\Python312\python.exe' '-Deureka.client.enabled=false' test` | 40 tests/0 failures/0 errors/1 opt-in skip；Access/Business/Knowledge Spring→Runtime实际执行 |
| es-query-service/common-security/employee-service：同wrapper `'-Deureka.client.enabled=false' test` | 分别43/21/50 tests；均0 failures/0 errors；Employee 20 opt-in skipped |
| mq-procedure-service 同wrapper test | 未完成：新Testcontainers MySQL在JDBC readiness超时，日志有redo/checkpointer lag；随后回收阻塞。核实后停止本次卡住的测试JVM，Maven最终BUILD FAILURE/退出1（已报告16 tests/1 skipped不是整模块通过）；不使用旧surefire报告冒充通过 |
| 三份L2 strict | 0 errors/0 warnings；元数据纠偏后再次通过 |
| Stage A四项hash、旧run字节 | 四项与§20.22一致；四个run历史测试通过；当前配置/Stage A工具及证据相对起始HEAD无差异 |

Maven测试子进程移除进程Key；agent-service仅对子进程设置绝对PYTHONPATH、stub/Knowledge默认false，测试显式使用fake。首次误用不存在的mq-producer-service目录未启动命令，核实实际模块mq-procedure-service后执行，未修改任何Java源码。PowerShell源码未改，不重复AST；27项opt-in不计为本次live通过。

环境预检首次记录PermissionError（模型0），随后独立仅服务启动检查成功，owned进程停止、原始日志删除和secretScan均true；未重试模型或执行业务查询。与此同时，本次git add长期无进展，核实并终止所启动PID后，Windows仍枚举HasExited=true的进程并占用`.git/index.lock`（0字节）；安全移除失败，不能暂存/提交/冻结。未删除或替换Git索引，未关闭其他用户服务，未绕过fsync或冻结检查。文件句柄/持久化异常与Docker卡顿可能相关，但尚无充分证据证明共同根因，不据此修改生产代码、测试超时或存储配置。

当前动作：暂停新的UAT冻结和模型执行；non-live工作包因Transaction容器验证及环境问题Blocked，UAT Deferred、QUALITY Blocked。四批累计仍8/20/14/7/7，新增模型/Knowledge live/Business请求0；本次仅隔离auth/readiness及测试容器验证，不消费付费预算。待环境恢复后在同一授权内继续验证、提交、冻结和唯一新批，无需再就正常步骤索要授权；不得用剩余预算自动新建额外批次。

最终状态复核：P3 strict为0 errors/1 warning（READY-003）：自动推导只识别未完成依赖/入口Gate，不能表达实现后的运行环境阻塞。本次保留有实际证据的Blocked并接受该校验局限，不为消除warning增设无必要门禁，也不宣称strict通过。focused计划内审核对现有直接DAG与两项环境事实，未调整依赖顺序或设计权限。diff --check通过，新增差异凭据/JWT/私钥模式扫描0命中；所有目标变更仍为本地diff，暂存区为空。HEAD为上述设计提交，origin/codex仍为`e0cc21de90a3c680aa7acf678dea7642f6ff99b5`；未执行push。新runner环境检查留下的有限错误资产保留，未创建manifest/consumed/result；Docker testcontainer回收因daemon调用无响应尚未核实，未停止用户Docker或其既有服务。

### 20.25 环境恢复及run-05冻结准备

2026-09-07只读复核：目标代码与§20.24测试版本未变。Docker、9200/8908/8909恢复响应；核实无活动Git进程后，仅移除2026-09-04留下的0字节index.lock，未改写Git索引。核实旧MySQL容器的创建时间、Testcontainers session标签和精确ID后，仅停止/删除本次遗留测试容器，未影响用户既有容器、真实数据库或索引。

只补做未完成的mq-procedure-service `..\serviceCenter\mvnw.cmd '-Deureka.client.enabled=false' test`：51 tests/0 failures/0 errors/2 opt-in skipped，BUILD SUCCESS（36.400秒），其中MySQL mapper集成4项实际通过。测试进程移除LLM_API_KEY。其余§20.24已通过的Python2034/27、host14、mypy127及Java结果对应同一代码，不将本次复验冒充重复执行全部模块。

新独立非模型环境预检`knowledge_stage_b_uat_v5 check-environment`通过：Spring/Runtime ready、认证stub unsupported，model=0/knowledge=0，clientsClosed/ownedProcessesStopped/rawLogsDeleted/secretScanPassed均true。2026-09-04首次PermissionError文件原样保留；恢复检查保存在独立target目录，不覆盖失败记录。V2实现提交`851a42d`，正式代码切片复评结论保持Blocker/Major/未处理Minor=0。

NONLIVE恢复Done、UAT Ready、QUALITY及B-CR-001仍Open/Blocked。按既有§20.23授权准备唯一run-05：原10例和gold不变，上限10/30/40/20/20，四批累计8/20/14/7/7；失败停止，不自动新增第六批。当前无manifest/consumed/模型outbound；freeze与终态由后续有限资产及本计划记录，不能预先声称UAT通过。

### 20.26 run-05终态、有限诊断及评审

2026-09-07执行唯一新批`knowledge-stage-b-uat-v5-20260904-run-05`（run名保留首次准备日期）；frozen HEAD=`91c1266f2df913609406bc3b53127585923f0625`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-05`。执行前tracked工作树clean且HEAD=origin/codex；321项源码资产、258项可执行资产、原10例/gold、索引绑定、任务selection-v4/Rewrite6/Summary5及quality-v2冻结。准备与执行之间未改tracked文件或可执行资产。

| 有限归档文件 | SHA-256 |
|---|---|
| manifest.json | `1910e8a1c3ef31aa232031b48c2df7e61edc1f41e74c3234cdbab880afd80bbd` |
| environment.jsonl（9月4日失败） | `9e54ca56bef6c43b53f99963b2bb5348f63672340bdb0c86aec79ccffbf3e681` |
| environment-recovered.jsonl（9月7日预检） | `ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7` |
| consumed.json | `9d01af797de6314a93840bc0c3904437757e227ea2a66a9f228a1d33a23ba73c` |
| journal.jsonl | `0bf32c39e1021482bcd71ef3ee46c2f8fecb54db14b983accfaf097d4b9aed67` |
| evidence.jsonl | `3bde6582172b6436d8ec65dbb5aab4d9e5f16128e399b8644ca23de8b7f9f455` |
| result.json | `075c2549f7545ab02961f872c37e8789176f7ad6c69b3f3773740ffd638e0c0c` |

原样归档至`agent-runtime/tests/system_e2e/knowledge_stage_b_run_05/`，包括先前未消费环境失败及恢复预检，不覆盖任何原资产。当前批status=failed（已消费），1通过/1失败/8未执行。KB-001正确clarification_required，模型2、其他0；KB-015a HTTP504/timeout，模型2/search1/embedding1/rerank1，尚无Summary。合计2 E2E/4模型/1search/1embedding/1rerank；五批累计10/24/15/8/8，Business/answer/retry/resume0。模型计数是HTTP尝试而非供应商账单；未消费余额不授权第六批。

| 根因核查 | 可核实证据及强度 | 判断与最小处理 |
|---|---|---|
| 选域/任务输出 | 两例selection及Rewrite6均succeeded；第二例只选tax.policy，quality-v2 accepted（强） | 不是此次直接失败点；taskBindingValid=false是预期Summary未发生，不是版本错配 |
| vector路径缺失 | embedding尝试1，但只有keyword search1及20条授权候选；未发vector search（强）；没有保存该次embedding的有限异常分类/耗时（不足） | 限定为embedding未产出可用向量；不能确定是超时、协议或传输错误 |
| 排序未完成 | 记录两次fusion、无成功rerank/final_rank/Evidence探针，rerank尝试1，最终timeout（强） | 直接阻塞在排序请求之后完成之前；既有代码将局部/阶段deadline超时映射504。没有足够证据分辨具体计时器或Docker/GPU原因 |
| 安全与失败语义 | 不进入Summary、不伪装no_result，无第二动作；client/owned进程/原始日志/secretScan均通过（强） | 保留当前失败关闭，不通过放宽超时、跳过rerank或改判来关闭UAT |
| 健康预检 | HTTP health和认证stub通过；预检不执行BGE推理（强） | 存活不等于在3秒embedding/5秒rerank内完成。后续应先做独立有界本地性能诊断；当前不重跑原问题或付费batch |

只读复核后未更改生产代码、Prompt、超时、gold、配置或数据。只增加两项fake HTTP故障反例，覆盖embedding超时/协议失败后keyword成功、rerank超时，验证当前Runtime返回timeout/knowledge.retrieval_timeout、Summary0、只调用三类既有endpoint、clients关闭。该反例证明失败映射，不冒充本次底层原因重现。新归档测试验证7项hash、321项冻结Git源码、原判据、累计预算、停止和有限payload。定向17 passed（28.84秒）；新runner及run-04预检回归38 passed（13.49秒）。

正式本增量代码/证据复评：对DR-KFLOW-017/021/022、DR-KRET-028、DR-KEV-028与UAT §14逐项核查，冻结版本/单绑定/无fallback/域内排序/边界/历史/预算/清理符合。新增故障测试和证据测试可验证，无需修改生产代码。`B-R5-EVID-001`为证据局限：未保存BGE异常类别和耗时，不能事后补造；未来有限诊断宜只增加操作枚举、状态及耗时，不保存内容。该问题不改判原运行；本切片无新增未修复代码Blocker/Major，整体B-CR-001仍Major/Open，核心跨域P0和其余8例未验证，阶段B正式整体评审不能通过。

设计语义未再次变化，仅按实际终态同步P3/UAT和上层实施摘要，不虚构新设计三轮批准。质量策略V2已实施但真实相关性/Evidence有效性仍Evidence missing；不能将本次timeout评价为其质量成功或失败。专项Functional=Failed，完整Effectiveness未完成测量，不给effective或partially_effective等级。阶段A及既有35/37功能证据保持原证明范围。后续完整回归、静态检查、Git与最终风险在本节末记录。

最终复验：`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`退出0；Transaction host/preflight14 passed（4.05秒），正式全量2042 passed/27 opt-in skipped/0 failed（308.89秒）。包含Knowledge/Business/Core/Employee/Transaction、Spring测试用Runtime、现行35/37功能追踪和全部历史；不把这些非live结果替代本批未执行8例或真实摘要。`python -m mypy --strict src`127个文件通过，`python -m compileall -q src tests/system_e2e/test_knowledge_stage_b_run_05_history.py tests/integration/knowledge/test_rewrite_v6_query_focus.py`通过。Java未有新变更，实际各模块结果仍见§20.24/20.25，不复制为本批重复执行；PowerShell未改，不重复AST。

三份L2 strict及P3 strict最终0 errors/0 warnings；7份当前文档57个本地Markdown链接存在。Stage A四项hash及前四批资产相对起始HEAD不变，run-05七项逐字节/冻结源码验证通过；敏感模式扫描0命中，严格有限evidence递归禁用raw payload字段，git diff --check通过。最后只读复评未发现新增代码或状态冲突；归档审查与故障反例补充共两轮，整体B-CR-001及UAT/QUALITY缺口仍保留，不宣称阶段B完成。

本目标增量已按设计`371631c`、V2实现`851a42d`、runner/恢复预检状态`91c1266`、run-05证据/反例及本次终态文档分开提交；完整SHA和推送结果以Git日志及交付报告为准。run-05已终止、无第六批；owned隔离进程已关闭、原始日志已删除，既有BGE/ES与用户服务未停止或修改。剩余工作为本地BGE推理时延/协议故障的有界诊断，以及新的独立目标下是否重新进行真实核心P0/剩余8例验证；不能在当前已消费批次内补跑。

### 20.27 run-05后续本地依赖诊断（非UAT重放）

2026-09-07从`dbac18c0c7bf5421e3882e3566b7b2583c95bc02`的clean工作树继续，只做两次预先限定的loopback合成输入诊断：embedding1、rerank1；paid model、E2E、Knowledge search、Business、retry/resume均0，不读取LLM_API_KEY，不调用原case、不修改索引、不重启BGE。输入为27字符合成句，rerank使用20份各1600字符合成文本，不读取业务数据或知识正文。调用复用当前BgeM3EmbeddingAdapter、BgeRerankAdapter及HttpxKnowledgeTransport，3秒/5秒上限不变。

| 本地操作 | 本次实测 | 可证明的范围 |
|---|---|---|
| embedding | 219ms；1024维有限数严格校验通过 | 当前服务能完成该合成输入；不证明run-05当时成功或冷启动根因 |
| rerank | 891ms；20条index/text/score一一对应校验通过 | 当前服务能处理该合成负载；不证明真实20条候选、排队或最坏负载满足时限 |

两个HTTP client均已关闭，无密钥、JWT、原始向量或响应持久化。有限记录为[local-model probe v1](../../agent-runtime/tests/system_e2e/knowledge_stage_b_local_model_probe.v1.json)，SHA-256=`8b8e31007a1ca4dc354e54adbe778c0170104544b931b03297e63f3b63e23f15`。记录不是candidate或UAT evidence，不重分类任何既有结果。这两次本地调用作为目标新增诊断单独计数，不回写原批次计数；五批UAT仍为10 E2E/24模型/15search/8embedding/8rerank。

定向代码对照设计核查L2_01_01 §9～11和§20.26的B-R5-EVID-001：`HttpxKnowledgeTransport.send`已将timeout/transport/protocol失败及durationMs送入`RunObservationCollector`，snapshot仍保留；但冻结runner的`run_server`只持久化modelTasks、retrievalStages和计数，`assess`没有保留下游状态/耗时。因此缺口位于测试证据投影，不应通过新增生产诊断层、放宽超时或重写历史结果修复。适配器响应解码失败与HTTP成功仍须分层区别；仅HTTP200不能证明严格解码成功。

本轮按聚焦实施路径，只加强现有两项fake故障反例：捕获当前生产Runtime observation，断言embedding timeout或protocol_failure、search completed/200、rerank timeout及非负整数durationMs，同时保留原timeout、Summary0、endpoint次数和关闭断言。未改变测试预期来容忍失败，也未修改src、Prompt、质量配置、冻结runner或运行资产。定向复评结论为：有限状态在生产观测可取符合；run-05底层原因仍不可验证，不能事后补证；整体B-CR-001仍Major/Open。

实际验证：`python -m pytest tests/integration/knowledge/test_rewrite_v6_query_focus.py tests/contract/knowledge/test_bge_embedding.py tests/contract/knowledge/test_bge_rerank.py tests/system_e2e/test_knowledge_stage_b_run_05_history.py -q --tb=short`为21 passed（25.02秒；1条既有LangChain pending-deprecation warning）；修改测试compileall通过。未重跑全量Python/Java：没有生产或Java变更，§20.26全量2042/27及对应Java验证仍为上次实际结果，不冒充本轮重复执行。P3 strict为0 errors/0 warnings；JSON有限字段、计数、来源/hash及git diff --check通过；src、冻结runner、run-05资产相对起始HEAD无差异。

本轮是追加诊断事实及测试强度，没有变更设计语义、工作包DAG、门禁或UAT通过标准，版本保持v2.49，不触发无关L0/L1/L2/UAT升级。当前不建议修改3秒/5秒配置；缺少原失败负载/有限异常证据，无法确认可安全修复的生产根因。run-05保持failed，8例未执行，V2完整效果仍Evidence missing；禁止自动创建第六批的执行边界不变。

### 20.28 run-06明确授权、有限诊断及冻结准备

2026-09-07用户针对上次请求明确“授权，继续目标”，批准一次新的独立10 E2E/30模型批次，不是run-05续跑。本节取代§20.27的待授权状态，不改历史失败结论。起始HEAD=`e6f4a16a6a8743e8f440f6eef05fae327980038e`，codex与origin/codex一致、工作树clean。新run=`knowledge-stage-b-uat-v6-20260907-run-06`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-06`；单批上限10/30/40/20/20（E2E/模型/search/embedding/rerank），加五批实际10/24/15/8/8后最多20/54/55/28/28，不突破原20/60/80/40/40。Business、answer、retry/resume均0；失败停止，不补跑旧批、不自动建立run-07。

最小变化是新版本化测试入口`knowledge_stage_b_uat_v6.py`，沿用原10例/顺序/gold、selection-v4/Rewrite6/Summary5、quality-v2和现有服务生命周期。manifest Schema6新增有限下游诊断版本及前五批不可变绑定。结果仅追加operation、status、httpStatus、durationMs；每请求embedding≤2、search≤4、rerank≤2，总条数≤8，严格有限枚举/整数边界；不保存request、response、query、正文或异常文本。HTTP200只证明HTTP完成，不能替代Adapter严格解码通过。该变化落实L2_01_01 §11允许的有限诊断并补足B-R5-EVID-001未来观测，不回填旧批证据，不新增生产诊断层或放宽超时。

源代码、Prompt、配置、公共DTO、安全策略、Stage A索引/alias和历史runner均不变。prepare/check-environment不读取模型凭据；仅正式execute允许读取进程级Key。先做fake、正式隔离回归及无模型环境预检，再提交/推送本次入口和授权记录，以clean HEAD冻结manifest；冻结后到终态之间不修改tracked文件。当前尚无新manifest、consumed或模型outbound，QUALITY和B-CR-001仍未关闭。

定向fake首轮：新/旧runner及run-05历史90 passed（14.67秒，1条既有LangChain预告）；之后加强逐case断言，证明下游投影确实进入有限verdict且不携带request，待完整回归核验。只读代码对照复核检查原判据、Prompt身份、累计预算、无重试、目录防复用、故障有限枚举、同请求观测投影和旧模块作用域恢复；没有改变业务设计或DAG，不重新包装为架构设计评审。正式回归、环境检查和本增量复评结论将在实际完成后追加。

实际复验：移除测试子进程Key后执行`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`，host/preflight14 passed（3.86秒），全量2094 passed/27 opt-in skipped/0 failed（297.35秒，1条既有预告），包含加强后的10个逐case投影断言及所有历史。strict mypy127生产文件和src/新runner/tests的compileall通过。无模型check-environment通过真实auth→Spring→stub Runtime（HTTP422 unsupported）；model/search0，clients、owned进程、原始日志及secretScan全部清理通过。P3 strict 0 errors/0 warnings，两份计划21个本地链接有效；源码、索引绑定、run-01～05无差异，凭据/JWT模式扫描0命中、git diff --check通过。

本增量代码正式对照复评共2轮：首轮发现逐case投影缺少直接断言的测试弱项，已加强并经全量验证；复评检查L2_01_01 §11/当前UAT合同，有限投影与原modelTasks、预算、gold和失败停止一致，未处理Blocker/Major/Minor=0。审查由同一执行者分离编辑阶段完成，不冒充外部独立人员；总体B-CR-001仍Major/Open。Java/PowerShell/生产源未变，不重复Maven或AST，既有实际结果见§20.24/20.25，不外推本批成功。UAT现在Ready、QUALITY仍Blocked；本节只同步授权/执行状态，P3 v2.49与UAT_01 v1.27保持不变。

### 20.29 run-06终态与检索前语义保护核查

本节取代§20.28的Ready时点。2026-09-07在clean且HEAD=origin/codex的`9a288f575da110c8127bae05d539780f772c48d3`冻结并执行唯一run-06；manifest覆盖332源码资产、258可执行资产、原10例/gold、现行索引、三个任务及quality-v2。冻结至终态tracked文件未变，未调整Prompt/阈值/超时/权限。六项原始有限资产逐字节归档至`agent-runtime/tests/system_e2e/knowledge_stage_b_run_06/`：

| 资产 | SHA-256 |
|---|---|
| manifest.json | `315e129634b0b437336ac632d31755aa5112baecba7a2aeb501a886dc670eee3` |
| environment.jsonl | `ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7` |
| consumed.json | `812cd5fc7a29c7bd0596fa237f6a0e67028803db668b412aab44fe7021dfbd1c` |
| journal.jsonl | `436251a9d346c7b91e2083d30ca0ff2271dcd48baf367bb0fb00d5e467b32674` |
| evidence.jsonl | `0a38058905b4171911585faef0225d01674d3d6da4a3d83c11b36e5068abe562` |
| result.json | `20254e46db4c86d6b666b365ec0ecfdf6d260947ebe36288bb71b6440dc14897` |

实际4 E2E/10模型/6search/3embedding/3rerank；六批累计14/34/21/11/11，Business/answer/retry/resume0。前三例KB-001（缺条件澄清）、KB-015a（定义与生活服务分类）、KB-004（政策/法律双域三条必要原文）通过；KB-002在Rewrite模型成功解码后、检索计划记录前返回HTTP502/downstream_failure，所有Knowledge下游/Summary0，后六例未执行。实际任务selection-v4/Rewrite6/Summary5无版本错配、模型失败诊断为空。不得把缺失Summary导致taskBindingValid=false误报为模型JSON失败。

本次BGE三次embedding为875/46/47ms，三次rerank为1000/938/672ms；六次search均HTTP200，所有下游diagnostic均completed。成功两例还具有路径/融合/重排/final/Evidence探针及原gold逐项校验，不是仅凭HTTP状态通过。KB-004的lodging/living/law_rate均true，较run-04该精确反例已改善；不能外推其他问题或认定完整V2效果已达标。运行status=failed（failed_consumed），专项Functional=Failed，完整Effectiveness未测完。

失败根因分层：第四例无任何下游操作，排除本次ES/BGE超时为直接原因；selection/rewrite均succeeded，仅能限定在模型解码之后的本地语义/计划检查，有限资产未保存输出或具体拒绝枚举，不能还原或认定某个模型改写。禁止读取日志补造原始输出或再发请求。客户端、owned进程、原始日志及敏感扫描均通过，未创建run-07。

聚焦设计核查发现独立反例`B-R6-DES-001`：L2_01_00 DR-KFLOW-003/§8要求保持实际条件，但复用QuestionSemanticGuard的数字正则会把“一般纳税人”“一般计税”的“一”算作数值；原问数字序列为(一,一,2026)，保持全部条件但将2026提前的候选变为(2026,一,一)，被判missing_constraint。两组当前生产根+fake验证：原序表达success、7个fake下游/3模型任务；仅年份提前的表达knowledge.rewrite_failure、下游0/2个succeeded模型任务；client均关闭，无真实调用。这证明误拒绝风险可复现，但不证明真实KB-002使用了这一表达。

设计核查结论限定为：将中文词素顺序等同数值语义保持，不足以落实原问题条件保护要求；不建议简单放宽为数字集合或去掉Guard，因为可能放过数值关联变化。历史Guard/任务/冻结资产不可改写。最小后续修复必须先定义已由独立检查保护的类别词与真实数量约束边界，完成设计内审和复评，再非live实施；当前未修改生产validator，不因该反例重判历史。总体B-CR-001保留Major/Open，UAT Deferred、QUALITY Blocked。

归档验证：新history与run-06 fake共59 passed（11.36秒），包括六项SHA、332项冻结Git源码、严格有限结果、累计预算、原gold、停止/清理及冻结Guard反例。该反例使用冻结Git源码，不要求未来生产永远保留误拒绝。全量2094/27、mypy/compileall等真实命令见§20.28；归档后最终复核结果在后续追加。阶段A和既有35/37功能结论保持原范围，未继承为新增条件语义通过。

归档后再次执行正式隔离入口`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`，host/preflight14 passed，全量2101 passed/27 opt-in skipped/0 failed（277.33秒，1条既有预告）。归档测试和六项原始资产逐字节/hash复核通过；版本化runner、生产源码、Stage A绑定及旧六批源资产未改变。有限证据正式复核检查严格字段、调用账本、失败即停止、原gold和不可变源码来源，无新增Blocker/Major；B-R6-DES-001与总体B-CR-001仍待后续处理，不以归档通过替代专项UAT通过。

### 20.30 类别词误识别最小设计修订

用户阶段B持续授权包含失败后的根因分析、目标内设计与非live修复；run-06仍停止，不读取Key、不新建付费批次。B-R6-DES-001已由§20.29反例证实。L2_01_00升级v1.23/DR-KFLOW-023：新内部Guard仅排除已有四个税务类别短语中的数字词素，逐query类别存在性、真正数字/比例/日期/文号/法条/否定检查保持；新Guard与旧默认隔离，当前根显式绑定，任务/Prompt和历史字节不变。REQ/L1已要求保护实际条件并由LLM理解，无须修改上层语义；P3/UAT/ARCH只同步直接依据。

本切片复用既有实施→nonlive依赖，没有新增Gate/工作包或重新申请付费额度。主表Done描述§20.24之前已验实现，本增量设计待审、实现未开始、nonlive未开始；其当前状态以本节为准，未批准不能编码。QUALITY仍Blocked、UAT仍Deferred；预算累计14/34/21/11/11不变。

三轮内审记录：(1) 核对L1 KQ-AD-013/REQ-KQUALITY-001与真实反例，排除Prompt维持词序、集合比较及泛化词典方案；(2) 核对Guard原始token/计数/候选长度边界，纠正“长度由extract统一控制”的描述，原文其他约束不受mask影响且类别检查必须成对；(3) 核对代码调用方、旧Guard/任务历史依赖、主追踪及唯一当前根，修复§8/§11残留V5引用与版本状态歧义。内审不构成正式批准，接下来冻结设计修订执行只读L2/跨层评审。

正式设计复评第1轮（独立于编辑阶段的只读检查）：按L2实施可行性与跨层rubric核对上述REQ/L1、旧Guard、Planner、bootstrap及测试落点；公共合同/权限/阶段A不变，类别保护与新数字提取成对、历史默认与回滚明确、真实数量顺序不放宽、没有case特判/新增Gate。S0=0、S1=0、未处理S2=0，批准DR-KFLOW-023非live切片；当前实现尚未开始。L2 strict与P3 strict均0 errors/0 warnings。此为同一执行者分离阶段审查，不冒充另一独立人员批准；不构成新付费授权或完整UAT结论。

### 20.31 DR-KFLOW-023实施及非live复评

设计提交`ffef03d`先于代码。新增`knowledge/tax_question_semantics.py`：先用旧Guard核验未改动原文，再仅对numbers副本屏蔽完整四类短语；其他约束保留原对象值。`semantic_planner.py`共用原有四类条件tuple、增加内部可选Guard注入，旧默认不变；bootstrap仅当前enabled根显式使用新Guard。没有新环境开关、Prompt/任务/decoder/HTTP/业务/索引变化；移除的只是Planner私有重复tuple定义，其唯一原调用点改用共享常量，全仓无其他调用方。旧Guard文件、旧任务、历史runner和全部冻结运行字节不变。

新增单测及当前根fake共46项：完整类别与年份变序、住宿/软件/咨询、单/双域、真实数字顺序/次数/日期/文号/法条/比例/否定反例、原始非法输入与上限、旧默认、disabled、整份计划拒绝、请求隔离及client关闭。测试只证明局部可执行行为，不证明真实模型语义或实际税务结论。

验证过程如实记录：初次普通Python未设置src路径，4个collection errors，未执行测试；改用本子进程`PYTHONPATH=D:\codex\agent-runtime\src`后77 passed/4 failed。4项是新测试fixture假设错误：现有Retrieval对相同query请求内只embedding一次（旧stage.py已有dict去重），以及默认stub根没有owned异步client；保持生产行为、改用准确的7次双域调用断言和enabled-model但Knowledge-disabled的真实组合根，未删除必要断言或放宽生产校验。随后定向81 passed（55.01秒）。

代码对照设计review_and_fix第1轮发现`B-R6-CR-001`（medium/测试缺口）：并发测试各建一份Runtime，不能证明共享Planner的请求隔离；要求同一Runtime并发两种年份。已修复为共享Runtime/Guard、每请求独立observation，成功请求4个fake下游、拒绝请求0，模型合计5且clients关闭；最终该集成文件21 passed（26.73秒）。第2轮对照DR-KFLOW-023六条、主追踪及REQ/L1检查：mask只作用numbers、旧限制先执行、四类逐query检查成对、历史默认/当前唯一绑定、无case特判/外部配置/副作用，未发现新增Blocker/Major/未处理Minor；正式全量回归仍待完成，不据此关闭总体B-CR-001。

实际Spring验证：agent-service运行`..\serviceCenter\mvnw.cmd '-Dagent.runtime.python=C:\Python312\python.exe' '-Deureka.client.enabled=false' test`，子进程src路径、stub并移除Key，40 tests/0 failures/0 errors/1 opt-in skip，BUILD SUCCESS（35.707秒）；Access/Business/Knowledge Spring→Runtime均执行。strict mypy128生产文件、compileall、L2/P3 strict（均0 errors/0 warnings）通过。本次无Java/PowerShell源码变化，其余Maven模块与AST未重跑，过去结果不算本轮重跑。真实运行仍只有run-06，累计14/34/21/11/11不变。

最终正式隔离回归：`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`在显式安装当前源码的临时环境执行，host/preflight14 passed（4.01秒），全量2147 passed/27 opt-in skipped/0 failed（354.91秒，1条既有LangChain预告）；包含46项新测试、所有历史hash、35/37既有功能追踪、Business/Core/Knowledge回归。临时环境由入口安全清理。49个当前文档本地链接有效、凭据/JWT模式0命中、git diff --check通过；旧Guard、旧任务、Stage A绑定和run-01～06相对基线字节不变。

DR-KFLOW-023设计/实施/nonlive均Done，替代§20.30准备时点；增量代码review_and_fix两轮完成，B-R6-CR-001修复，当前切片Blocker=0、Major=0、未处理Minor=0。B-R6-DES-001的可复现类别词误分类已关闭；这不确认它就是run-06真实拒绝根因。总体B-CR-001仍Major/Open，WP-KRETRIEVAL-UAT-01 Deferred、QUALITY Blocked。没有新live运行或自动创建run-07，未覆盖gold、失败结果或放宽核心P0。后续必须先针对剩余真实验收作独立批次决策，不能直接执行被冻结的run-06或复用剩余额度。未修改用户运行中的服务和现行索引，未实施图谱或阶段C/D。

### 20.32 剩余真实验收与累计预算只读复核

2026-09-07以`550b012ad390463816372054d1c87f5877209f40`为基线，逐一读取run-01～06不可变result及原10例清单，不读取模型凭据、不重放请求。核查问题仅限剩余预算能否覆盖未通过场景，不构成新的执行授权、完整设计批准或UAT通过结论。

| 资源 | 原累计上限 | 六批实际累计 | 剩余 |
|---|---|---|---|
| E2E | 20 | 14 | 6 |
| 外部模型HTTP | 60 | 34 | 26 |
| search | 80 | 21 | 59 |
| embedding | 40 | 11 | 29 |
| rerank | 40 | 11 | 29 |

历史通过case去重后只有`UAT-KB-001/015a/004`三项；没有真实通过记录的七项为`UAT-KB-002/003/005/006/015b/016/008`。其中KB-002在run-06失败，后六项在全部六批均未执行。即使后续经评审允许等价复用前三项、且其余七项均一次成功，也至少需要7个E2E，超过剩余6个；这只是最乐观下限，不预先认定旧版本证据可覆盖当前Guard。若仍按现有原10例完整新批的冻结上限预检，累计将需24 E2E/64模型，同样超出20/60；不能依赖“也许提前失败或少调Summary”通过预算预检。

结论：已执行六批没有超限；不足发生在失败后剩余验收与原累计上限之间，并非应当放宽validator或删减gold。当前禁止自动新批和复用余额的约束继续有效。后续若要求全部真实验收收口，必须先独立决定证据复用范围、新批清单及累计预算调整；这些尚未获准、未写成新运行资产。本次仅追加事实和算术核查，不调整版本、DAG、门禁、用例、预算或通过标准。IMPLEMENT/NONLIVE保持Done，UAT Deferred、QUALITY Blocked，未创建run-07。

本轮实际验证：移除测试子进程Key并设置当前src路径，执行六个`test_knowledge_stage_b_run_0N_history.py`及`tests/uat/test_current_traceability.py`、`test_knowledge_traceability.py`，44 passed（53.54秒）；历史hash/冻结源、原判据、累计计数、既有35/37追踪通过。P3 strict为0 errors/0 warnings，git diff --check通过。只改本节事实记录，没有源码/测试/配置/历史资产变化，因此未重跑全量Python、mypy或Java；§20.31数字仅代表上轮执行。本轮模型及真实Knowledge/Business调用均0。

后续以`cbfb11486be4cbe0292f326d3e9239ecf836aecb`执行只读targeted_check，范围仅为上述三项run-06成功证据与DR-KFLOW-023修复的代码兼容性。相对run-06冻结HEAD，生产差异仅bootstrap绑定、Planner内部注入/静态tuple共用及新Guard；任务/Prompt、case/gold、检索/评分/摘要实现未变。三项原问题均不含四个类别短语，原有逐query检查亦禁止候选新增它们；因此任何可接受候选均不触发新mask，合法澄清分支也不变。结论为符合这一限定兼容性检查，不是全部实现批准、正式证据合并或当前版本真实UAT通过。

本次实际验证：旧默认Guard与当前Guard的39组Planner非live对照（前三项原问、单/双域、澄清、非法输入及新增类别/数量/否定条件）结果一致；`python -m pytest tests/unit/knowledge/test_tax_question_semantics.py tests/integration/knowledge/test_tax_semantic_guard_production.py tests/system_e2e/test_knowledge_stage_b_run_06_history.py -q --tb=short`为53 passed（23.63秒，1条既有LangChain预告），测试子进程移除Key并使用当前src。未保存或重建历史模型输出，真实模型/下游调用0。后续若决定复用，仍须核对新冻结时配置/索引/模型绑定及原评分合同，并正式批准新批次范围；本核查不证明外部模型未来输出稳定，不改变剩余七项或原累计上限。无源码变化，未重跑全量或Java；本节仅补充证据适用范围，不新增运行资产或Gate。

### 20.33 独立七例授权与证据复用计划

2026-09-07用户明确“允许，继续目标”，批准上一轮精确请求：累计E2E上限21、模型仍60，评审复用run-06前三项，独立验证剩余七项且失败停止。本节取代§20.32待授权状态；起始HEAD为`eeae6eb4f4111a5c7602d3ca46ff5a322499d64a`、工作树clean、与origin/codex一致。只允许`knowledge-stage-b-uat-v7-20260907-run-07`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-07`，不重启旧批，不授权run-08。

新批固定顺序为KB-002、003、005、006、015b、016、008；原问题/域/gold/阈值完全复用旧10例对应项，不修改冻结case文件。单批上限7 E2E/21模型/28search/14embedding/14rerank；加六批14/34/21/11/11后，最多21/55/49/25/25，不突破修订后21/60/80/40/40。Business/answer/retry/resume均0；首个outbound消费授权，失败停止，余量不授权下一批。

复用决定受UAT_01 §14.18约束：run-06的KB-001/015a/004仅作为原版本实际执行证据，必须通过只读源码/任务/配置/索引/可执行资产一致性及Guard兼容校验。不会在run-07生成这三项的虚假执行行或重计调用；10例联合追踪明确区分3项复用和7项本批结果。任何复用前提失效，停止新批准备，不扩大到全10例或提高其他上限。

实施范围仅新`tests/system_e2e/knowledge_stage_b_uat_v7.py`及直接fake/历史测试，沿用既有生产Runtime、原判据、有限诊断和owned生命周期；P3/UAT/ARCH同步直接版本和状态。没有生产、Prompt、公开DTO、权限、索引、旧runner/资产修改。审批顺序为三轮内审→分离编辑阶段的只读设计评审→新runner/fake与回归→代码复评→无模型环境检查→提交并冻结→唯一live→终态/评审/Git。复用既有UAT工作包，不新增Gate或虚构DAG依赖；新协议待审期间只读/文档可做，尚未实施或调用模型。

三轮内审完成：(1) 对照原10例责任和Guard兼容证据，明确“3复用+7新执行”不能写为同批10/10；(2) 核对预算/JSON合同，补齐重复key、非有限数及bool冒充整数拒绝，累计账不重置；(3) 核对历史保护、源码/可执行漂移、停止/回滚、DAG和最小范围，旧批只读，新协议不改生产。正式设计评审第1轮在文档编辑结束后只读执行，范围为P3 §20.33/UAT §14.18到L2 DR-KFLOW-023和原验收合同的交接；S0=0、S1=0、未处理S2=0，允许新runner非live实施。复用正式批准仅在§14.18列明快照条件全部成立时生效；真实执行仍须runner/回归/代码评审、环境与冻结预检。此为同一执行者分离阶段评审，不冒充外部独立人员批准。P3 strict与diff检查通过，当前代码尚未修改、模型调用0。

非live实现已新增v7入口及直接fake测试，原生产源、六批runner/资产、问题和gold均未修改。UAT §14.18追踪为：固定七例→`CASES`切片/继承顺序预算；历史复用→`run06_assets/validate_reuse`；精确协议→`strict_json/same_json/validate_manifest`；累计账→`prior_bindings`；消费/停止/清理→继承只读版本化runner并在CLI作用域恢复绑定。60项定向测试通过（7.17秒）：真实历史hash及已审Git源校验、七例顺序/原判据、快照/源码/可执行漂移拒绝、21/60累计硬上限、bool/浮点整数/重复key/非有限数拒绝、消费资产拒绝、取消恢复、旧Prompt/额外调用/其他endpoint拒绝。准备测试仅隔离旧文件扫描，另验证必须调用旧冻结资产校验；实际完整资产验证仍需clean HEAD准备和execute预检。

本增量正式代码对照设计第1轮（编辑结束后只读检查）限定新runner及测试到本节/UAT §14.18，复核任务绑定、原判据、复用兼容来源、配置/可执行/索引拒绝、总账、单case、失败停止、凭据读取和旧模块恢复，未发现未处理Blocker/Major/Minor；不将该切片结论当作整体B-CR-001通过。该审查仍由同一执行者分离阶段完成。`python -m mypy --strict src`通过（128源文件），`python -m compileall -q src tests/system_e2e/knowledge_stage_b_uat_v7.py tests/system_e2e/test_knowledge_stage_b_uat_v7.py`通过；新增文件敏感模式扫描0命中。完整隔离回归与环境烟测尚待终态，不预记真实UAT结果。

执行前验证已完成：`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`在Python3.12.4临时虚拟环境显式安装当前源码，host/preflight14 passed（4.42秒），全量2207 passed/27 opt-in skipped/0 failed（384.17秒、1条既有LangChain预告），退出清理临时环境。包含当前35/37追踪、Knowledge/Business/Core及历史资产校验；跳过仅代表已有opt-in边界，不计作本批真实通过。`python -m tests.system_e2e.knowledge_stage_b_uat_v7 check-environment --root target/knowledge-stage-b-uat-v7-20260907-run-07`通过真实auth→Spring→stub Runtime冒烟，model/knowledge0；alias/UUID检查、clientsClosed、ownedProcessesStopped、rawLogsDeleted、secretScanPassed均通过。8908/8909只读health200，无embedding/rerank计算调用。上述子进程均移除Key，不读取模型凭据。

正式复评第2轮结合实际回归和环境终态，当前runner切片无未处理Blocker/Major/Minor，允许提交、clean HEAD冻结和唯一run-07执行；总体UAT仍In Progress，QUALITY及B-CR-001未关闭。Java源/可执行产物和PowerShell脚本未修改，未重复Maven或AST，既有模块结果不冒充本轮执行；本轮真实Spring smoke已执行，可执行资产仍须在冻结及execute时逐项校验。P3 strict/diff通过，执行后只追加真实有限终态，不改旧六批或预记通过。

### 20.34 run-07真实终态与逐阶段缺口

2026-09-07在clean HEAD=`806e1568c694a95769852a47e6c7ff00ec5b1f5a`且与origin/codex一致时冻结并执行§20.33唯一run-07，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-07`。342项源码、258项可执行资产、7例/原gold、任务及Prompt、quality-v2、配置/indexBinding和run-06兼容校验全部通过；冻结后至终态未修改tracked文件。准备不读取Key，仅execute按授权使用进程级Key，未输出或保存密钥。

| 不可变文件 | SHA-256 |
|---|---|
| manifest.json | `ec02be380e4528ade13a6a4eb38a57436270a83b5c9fe78ad52a7b63b7a0e12c` |
| environment.jsonl | `ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7` |
| consumed.json | `c7af33c643f19ded61ea87f0b5410fa0cd4709735c08353e7e226a0e615e90dd` |
| journal.jsonl | `2f25b9a09b510579f02063ac88c7837ce58e68c3c4c7579119d58265420d45c3` |
| evidence.jsonl | `feeab5a3fa3bc26e8c1b75801e9ef7751524e694b39f42d99ab699a8d0e46d99` |
| result.json | `4fea1e2654825d18bd31b156b75cb8d5b6e2393b36504e5ec7c1a0c704e28aff` |

归档根为`agent-runtime/tests/system_e2e/knowledge_stage_b_run_07/`；六文件由原运行目录逐字节复制及hash比对，新增精确Git字节保护，旧六批保持不变。实际首例KB-002 HTTP200/status=success但验收Failed：仅tax.law、1条引用，law_rate=true、lodging=false、law_effective=false。selection-v4/Rewrite6/Summary5均succeeded，quality/task/零额外调用检查通过。剩余KB-003/005/006/015b/016/008全部Not executed，未补跑。原10例联合状态仍只有run-06三项有通过证据，不能记为本批或整体Passed。

本批1 E2E/3模型/2search/1embedding/1rerank；七批累计15/37/23/12/12，低于21/60/80/40/40。Business/answer/retry/resume0，journal恰好3条，首outbound消费标记存在；授权已终止，剩余额度不构成新批授权。Runtime clients关闭、owned服务停止、临时原始日志删除和密钥扫描通过，四个隔离端口执行后无监听；未停止用户其他进程，未修改阶段A索引/alias。

| 缺口/证据等级 | 本次可核实事实 | 判断及最小处理方向 |
|---|---|---|
| B-R7-DOM-001；高 | 计划仅tax.law；两条检索均该域；全部候选无lodging | 适用问题所需政策分类没有进入一次性域计划，不是policy服务失败后的fallback问题。V5/V6已有“必要原文共同证明”抽象规则，但本次模型未形成相应证明范围；先审查适用性证据需求与最小选域合同，不能本地按酒店词强塞第二域 |
| B-R7-COV-001；高 | law_effective向量12、融合21、重排/最终15；最终Evidence8条不含该SHA；law_rate为Evidence第3 | 已召回原文在Evidence选择阶段丢失，不能宣称原文缺失，也不能归为top20未召回。先评估必要时效证据与选择责任；不直接放宽8条/配额或按gold ID加分 |
| B-R7-PROOF-001；高（结构性边界，非原输出重建） | Summary输入有限hash无两项必要原文，输出通过现有结构/引用校验且HTTP200，原文验收失败 | 现有合法引用不等于适用结论已完整证明；原问题充分性主要依赖模型，内部sufficient仅代表现行机械条件。需先设计证明覆盖如何可靠表达/验证，不能删gold或把HTTP200改判通过 |
| 环境/旧Guard推断；不支持 | 本次全部下游200，embedding703ms、search359/217ms、rerank1296ms；本地计划已形成 | 不支持将本次归因于BGE超时、空库或旧类别词误拒绝。不能据此重建run-06原模型输出或倒推其确切根因 |

结合个人学习项目，不建议为此新增审批层、重复冻结或再试一次模型；问题是查询适用性需要的证明内容未稳定进入计划/最终证据，不是运行治理不足。可选最小后续方案为先用非live反例区分“资料查阅”与“条件完整的适用判断”的必要证据责任，再进行有版本的模型规划/证据完整性设计；必须同时防止全域广播、gold参与在线逻辑和任意扩大topK。新语义/Prompt/选择策略尚未设计批准或实施，本节只记录根因和建议，不绕过先审后改。本次未新增生产修复、公共DTO、模型调用、run-08或付费候选。

UAT工作包Deferred、QUALITY Blocked，整体B-CR-001 Major/Open；GATE-KRG-006的已有设计准入不等于真实核心P0通过。Functional专项Failed，完整效果未测完，不给该不完整批赋予effective/partially_effective等级；已有35/37功能追踪及历史P5效果结论保留各自证明范围。P3 v2.50/UAT v1.28仅同步实际终态，不为一次失败升级架构版本。

归档后实际验证：`python -m pytest tests/system_e2e/test_knowledge_stage_b_run_07_history.py tests/system_e2e/test_knowledge_stage_b_uat_v7.py -q --tb=short`为67 passed（20.26秒）；严格字段、六项hash、342项冻结源、3项复用/7项独立边界、1失败/6未执行、累计账、逐阶段排名及无raw payload均验证。再次正式隔离回归为host/preflight14 passed（3.47秒），全量2214 passed/27 opt-in skipped/0 failed（248.25秒、1条既有预告），临时环境清理完成。当前35/37追踪仍通过；新增历史测试compileall通过。P3 strict 0 errors/0 warnings，三份状态文档41个本地Markdown链接0缺失，六项新资产敏感模式0命中，git diff --check通过。

终态代码/证据正式审查1轮：来源与调用账独立、原判据/阈值不变、历史与本次结果分离、HTTP成功不冒充核心验收、阶段定位不重建模型输出、版本化数据无秘密、owned清理与旧资产保护符合本次执行合同。归档/runner增量未发现未关闭Blocker/Major/Minor；不改变总体B-CR-001 Major/Open和上述三项语义/覆盖风险。生产源/Prompt/索引绑定相对本批冻结提交差异为空，本次没有删除业务或共享代码。仅提交已验证的执行器、失败事实、历史测试和当前状态，不以Git交付表示阶段B完成。

### 20.35 引用来源验收反例及非live修复

起始HEAD=`8b7602ff25ce4140780278bec4a42677931b74ce`，工作树clean。继续执行失败后的授权内非live审查；不读取模型Key、不调用真实依赖、不创建run-08。UAT_01 §14.1已要求必要原文hash与最终引用对应，L2_01_02 §13.6/13.7允许有限诊断及版本化Harness；本切片落实既有要求，不修改生产语义、公共合同、gold、阈值或历史评分器。

发现`B-R7-EVAL-001`（medium，验收完整性）：冻结`knowledge_stage_b_cases.py::assess`分别检查“gold正文位于Summary输入”和“最终quote出现在该正文”，未绑定quote实际citation.evidenceId。同一句话同时存在于两份不同来源时，引用另一来源仍可能通过。合成反例从run-07冻结提交读取评分器并核对manifest SHA，仅在测试内存替换合成gold；旧评分器确实返回true。**这证明判据存在可能假通过的缺口，不证明任何历史case实际错引，不是run-07已确认失败的根因，也不能据此改判旧结果。** 历史有限结果缺少重新评分所需的逐引用对应关系，保持原结论及其旧证明范围。

最小处理：新增测试专用`tests/system_e2e/knowledge_stage_b_citation_check.py`（`stage-b-citation-binding-v1`），不修改或接入已消费runner。调用方必须在当前请求内提供已验证bundle、实际出域决定生成的Summary输入、已验证公开points及预先冻结gold；不能根据quote反推来源。校验引用ID→bundle片段标识/内容hash→该来源连续quote→必要条款。先核对实际模型输入与bundle一致，再作结果后评估；gold不进入在线模型/规划/检索/排序。只返回有限布尔值和原因，不返回问题、正文、引用ID或原始响应；完整对象只在请求内存使用。它不代替域、任务、预算、安全及人工语义/usefulness判定，也不产生整体UAT通过结论。

代码对照设计review_and_fix两轮，范围仅新增校验器与两个测试文件：第1轮发现`B-R7-EVAL-002`（medium），仅比hash仍不能区分相同正文的不同chunk；已补齐gold已有chunk标识的对应校验和正反例，未改gold。精确类型反例另覆盖bool冒充schema整数、整数冒充coverage布尔和非法gold键。第2轮复核请求内取证、政策可省略模型元数据、未知/重复引用、同文不同来源、零I/O及有限输出，当前非live校验切片Blocker/Major/未处理Minor为0。这是同一执行者分离编辑阶段的复核，不宣称另一独立人员审查。

新增40项定向验证通过：其中2项使用当前`build_runtime`生产对象图、fake模型及fake类型化服务，观察真正出域输入和公开citation，不构造另一条在线流程；两种合法连续引文均可获得Runtime成功结果，但新验收只接受指定来源。本切片不经过Spring入口，不冒充新Spring E2E。每例fake任务3次（selection-v4/Rewrite6/Summary5）、search2、embedding1、rerank1，Business0，client关闭且日志/observations无合成正文或JWT。命令为`python -m pytest tests/system_e2e/test_knowledge_stage_b_citation_check.py tests/integration/knowledge/test_stage_b_citation_binding.py -q --tb=short`（40 passed，3.98秒，1条既有LangChain预告）；测试子进程移除Key并使用当前src。校验器单文件strict mypy通过，正式隔离全量结果见本节末段。代码/测试原子提交为`c8db12abf3f7ca6031b5c6b7801b61ef5aaca0ef`。

文档定向核查仅检查本节与UAT_01 §14.20是否正确落实§14.1/L2 §13.6/13.7：来源绑定、历史不可变、有限输出和无新付费授权均符合；没有上位语义变更，不升级L0/L1/L2或重新声称整体设计通过。P3 v2.50/UAT v1.28只追加缺口及已执行证据。WP-KRETRIEVAL-UAT-01仍Deferred、QUALITY仍Blocked，B-CR-001及B-R7-DOM/COV/PROOF三项仍Open。该工具尚未用于真实运行，后续若采用必须纳入新的版本化执行合同；本轮不创建或授权该批次。累计真实计数仍15/37/23/12/12。

最终验证：`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`正式临时安装入口通过，host/preflight14 passed（4.03秒），全量2253 passed/27 opt-in skipped/0 failed（392.79秒、1条既有LangChain预告），临时环境已清理。全量收集后增加的“相同正文、不同chunk”1项反例另由上述最终40项定向回归覆盖，不把全量计数写成2254。全量包含七批历史hash/冻结源、Knowledge/Core/Business及原35/37功能追踪；不是重新执行35/37真实UAT。`python -m mypy --strict src`128生产文件及新校验器单文件通过，`python -m compileall -q src`和三个新文件通过。P3 strict为0 errors/0 warnings；两份文档21个本地Markdown链接无缺失，5个目标文件凭据/JWT扫描0命中，git diff --check通过。生产源/服务/阶段A绑定/旧gold/七批资产相对起始提交无修改。本切片无Java、PowerShell或生产修改，未重跑Maven、Spring→Runtime Java测试及AST；没有真实ES/BGE/模型请求，不计为新端到端或效果验证。

### 20.36 必要证据覆盖设计与实施交接

起始HEAD=`57980e0e147ac15b09ea55694cb11f33c624fffc`，codex与origin/codex一致、工作树clean。只读核实当前REQ-KQUALITY-001～004、L1/L2、实际Planner/Stage/selector/summary serializer及生产调用方；本次没有读取Key、真实模型/ES/BGE请求、服务启动或新运行资产。§20.34三个高证据缺口仍Open，§20.35来源绑定工具不能修复生产语义。

方案比较及权威分配在L1_01 KQ-AD-018，字段/方法/算法分别在DR-KFLOW-024、DR-KRET-029、DR-KEV-029/030。选择一次模型规划生成必要证据需求，需求内重排保留与最终引用覆盖共同消费；不调检索topK、不提高Evidence预算、不修改公共业务DTO。代码引用扫描表明涉及的内部类型消费者仅Knowledge及bootstrap，没有Java、Business或公共Core数据合同消费者；旧Stage方法签名保持。L2_01_02 §13.7的历史Prompt-only限制被明确限定，不能以隐藏query/context传递绕过内部合同。REQ和L0的唯一链路/安全/行为要求已经覆盖本增量，无需修改；ROADMAP阶段B边界不变。

本增量只使用原工作包及DEP-KQUALITY-001～005，未新增审批层或candidate。DIAG已完成；DESIGN新增量评审完成；IMPLEMENT为Ready、NONLIVE为Blocked，不抹去旧6/5/v2的完成及回归证据；UAT继续Deferred、QUALITY Blocked。GATE-KRG-006按本节设计证据关闭，仅准入新合同non-live实施，不要求先有代码或live。整体B-CR-001 Major/Open不因设计修订关闭。

实施交接顺序：先落实内部需求类型、V7任务/decoder及非live合同；在同一批准合同下实现需求排序和V6覆盖两个消费者；两者完成后才能切换生产成对绑定；最后当前对象图/Spring/全量/正式代码复评。这里是原IMPLEMENT工作包内部直接数据依赖，不人为新增工作包或强制两个独立消费者串行。每个切片按L2测试先定向验证；新模型真实性、核心P0和整体UAT仍不由fake关闭。未来如要真实验证必须另有未消费执行合同，本次不准备run-08，不将余额解释为权限。

授权文件范围为L1_01、三份Knowledge L2、P3、UAT_01及ARCHITECTURE索引；本轮暂不修改生产代码或测试。冻结历史任务、七批资产、阶段A索引/绑定、gold、读取/出域目录、公开DTO均只读。回滚为禁用Knowledge或整体源码/版本绑定回退，不请求内fallback、不改写历史。

三轮作者内审实际完成：

| 轮次 | 发现与最小修复 | 关闭依据 |
|---|---|---|
| 1：职责/语义/数据 | question_kind如果只在模型输出出现，后续无法复核适用性三角色；补齐RewriteResult→Plan→EvidenceInput的kind/需求tuple及同一纯校验函数，禁止本地补需求或按行业选域 | DR-KFLOW-024与KQ-AD-018一致；旧实例空/None，新search必须完整，非search不建计划 |
| 2：安全/兼容/预算 | 当前Planner在clarification提前返回；通用观测会序列化新增dataclass字段，BGE观测会展示focus；ModelGateway采用精确input_type | 在终态前校验新输出，Plan显式安全投影、Summary维持白名单、rerank query统一隐藏；新Summary精确注册子类型，保留旧asdict/网关/validator；需求与JSON结构计入32KiB |
| 3：追踪/DAG/状态 | 严格校验发现9项未定义追踪/拟新增路径说明缺口；另发现旧实施依据、版本尾注及一次超时状态外推 | 补齐规范定义和拟新增标记，分开新旧准入，移除L1过时根因；使用原DEP链，未新增门禁。修复后L1/三L2/P3 strict全部0 errors/0 warnings |

正式评审固定范围为上述L1、三L2的必要证据增量及P3/UAT/索引交叉一致性；当前REQ-KQUALITY-001～004、L0唯一链路/安全边界和当前模型/Stage/HTTP数据类型为只读上位与实现事实依据。分别使用L1分解、L2可实施及跨层评审标准；不把未实施代码、fake语义或历史运行当作新效果证据。评审和编辑分阶段执行，执行者相同，不冒充另一独立人员批准，也不形成全仓评审结论。

| 正式轮次/问题 | 证据、触发影响及结论 | 修复与复评 |
|---|---|---|
| 1，B-DES-REQ-001，S1；L2_01_02 §9.5/UAT §14.21 | 当前citation checker的schema_version精确为1，新Summary计划为2，直接复用将拒绝所有新验收输入；阻塞新验收接缝实施 | 新测试专用v2先检查新类型/Schema2，再原样投影已允许字段复用v1来源算法；不放宽/修改v1，不把需求当gold。第2轮复读合同、v1实现及错源测试要求，Closed |
| 1，B-DES-REQ-002，S2；L2_01_01 §9.4 | 多需求共享candidate时未定义单个rerank_score和canonical域来源，可能跨query取max或丢域，破坏确定性与归域 | 使用Stage已验证fused对象，score固定首次入选队列、rank按锚点/轮转、标签按需求序合并；签名与既有V2接缝明确。第2轮逐步核对，Closed |
| 2，复评 | 复核原两项及全部层级标准，S0=0、S1=0、未处理S2=0；允许新内部合同/排序/Summary及测试适配的non-live实施 | 旧生产仍6/5/v2，StageA/公共DTO/读取/出域不改；模型语义、≤4次BGE的实测时延、核心P0及整体UAT仍待验证 |

§14.18三项旧成功的同版本复用条件在未来7/6/v3切换后不再成立，UAT已明确不能自动按三旧七新关闭；新真实执行仍需有效未消费合同。本轮仅完成设计准入，B-R7-DOM/COV/PROOF及总体B-CR-001仍Open，不把设计改完当作生产缺口关闭。

本轮实际验证：L1使用validate_architecture_doc.py、三L2使用validate_detailed_design.py，均以`--file <本轮文档> --root D:/codex --strict`执行，P3使用validate_implementation_plan.py `--file docs/plans/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md --strict`；最终五项均0 errors/0 warnings。7份文档57个本地Markdown链接无缺失，新增diff凭据/JWT模式0命中，git diff --check通过。生产/服务/索引绑定相对起始HEAD差异为空，未删除文件。

在agent-runtime目录、子进程移除Key且PYTHONPATH=src后执行`python -m pytest tests/system_e2e/test_knowledge_stage_b_run_07_history.py tests/system_e2e/test_knowledge_stage_b_citation_check.py tests/integration/knowledge/test_stage_b_citation_binding.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q --tb=short`：59 passed（12.89秒，1条既有LangChain预告）。包含run-07六项hash/冻结源、40项引用来源校验及真实当前对象图fake反例、原35/37追踪；不等同于重新执行35/37真实UAT。本轮只改设计，未重复Maven、Spring Java E2E、全量non-live、strict mypy、compileall或PowerShell AST；相关完整命令应在新代码实施后执行，旧§20.35数字不冒充本轮结果。真实模型/ES/BGE新增调用均0。

### 20.37 必要证据公共合同部分实施与回归

2026-09-07从clean HEAD=`35e8cbee955d41e4f088b6664972fc9a243d922c`继续§20.36已批准的non-live实施。本节只关闭DR-KFLOW-024的公共合同切片，不宣称需求排序、Summary消费者或新成对生产接线已经完成。没有设计语义变化；L1/流程L2/索引仅同步部分实施状态，版本保持不变，不因测试数量变化触发架构升级。P3主表和追踪表统一为IMPLEMENT In Progress、NONLIVE Blocked，旧§20.24/20.31完成记录保留其历史适用范围。

| 批准要求 | 当前实现与验证 | 状态 |
|---|---|---|
| frozen需求、question_kind、同请求tuple | contracts/evidence_requirements；RewriteResult→Plan保持同一需求tuple；旧quality拒绝新字段 | 本切片完成 |
| Rewrite7五字段精确合同 | rewrite_v7复用原安全请求工厂，新完整指令/1536输出上限；exact decoder及内部fake输出复核，保留旧任务 | 本切片完成，未接生产根 |
| 原问/query/focus校验顺序 | semantic_planner保留原完整query guards，focus安全及受保护token计数子集校验；非法整体失败 | 本切片完成 |
| 观测最小暴露 | Plan显式旧字段投影、Summary原白名单不变、rerank query统一隐藏；实际BGE请求不变 | 本切片完成 |
| 当前消费者版本失败关闭 | Capability/Retrieval/Evidence在I/O前拒绝尚未支持的v3；旧输入默认None/空tuple兼容 | 本切片完成 |
| DR-KRET-029需求排序 | 最多4个需求队列、锚点保留及标签 | 待实施 |
| DR-KEV-029/030 Summary6覆盖 | Evidence需求验证、子类型输入、覆盖关系及引用复核 | 待实施 |
| 成对生产绑定及新完整对象图 | 必须等待上述两个消费者；当前仍Rewrite6/Summary5/quality-v2，默认disabled | 未切换，不计作新UAT通过 |

没有把v3提前加入全局可执行版本集合；仅Planner/PlanBuilder允许构造新合同供非live验证。否则现有分派可能把新版本送入旧排序实现，形成假通过。新增组件集成使用真实ModelGateway/Planner及fake transport，不冒充已启用的新生产对象图或真实模型语义验证。

本切片代码对照设计review_and_fix分两轮完成，执行者相同且编辑/只读评审分阶段，不冒充外部独立人员或全仓批准：

| 发现 | 最小修复及关闭证据 |
|---|---|
| B-CODE-REQ-001，中；v3任务只查版本而未查task ID/input type，错误装配可能进入模型 | constructor同时校验KNOWLEDGE_REWRITE及精确既有输入类型；两项错误装配零调用反例通过 |
| B-CODE-REQ-002，中；run-07历史测试fixture把当前变化的源码hash当作旧已批准源码 | 不改被冻结的test/runner/validator。新增test-only conftest仅替换该模块fixture准备，读取批准提交Git blob；新增当前源码hash仍被原validator拒绝及旧文件字节不变的反例。历史定向69 passed，完整回归通过 |
| 状态复核：P3追踪仍把旧实施Done当作新增量完成 | 主表/追踪/本节统一新旧适用范围；无新DAG或Gate |

第2轮复读全部本切片diff、直接调用方、旧版本路径及实际验证结果，当前公共合同切片Blocker=0、Major=0、未处理Minor=0。整体B-CR-001仍Major/Open；B-R7-DOM/COV/PROOF未关闭。结构校验不能证明模型focus/角色具有真实语义充分性，须后续消费者和受控验收，不以fake关闭。

本轮实际命令及结果（测试子进程移除Key，不读取值）：

- `python -m pytest tests/contract/knowledge/test_rewrite_task_v7.py tests/unit/knowledge/test_evidence_requirements.py tests/integration/knowledge/test_requirement_plan_production.py -q --tb=short`：129 passed（0.64秒）。最初新增fixture的enabled domains漏配和构造参数误名已修正，不改生产断言。
- `python -m pytest tests/system_e2e/test_run07_frozen_fixture.py tests/system_e2e/test_knowledge_stage_b_uat_v7.py tests/system_e2e/test_knowledge_stage_b_run_07_history.py -q --tb=short`：69 passed（20.46秒）。
- `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`：首次host14 passed，全量2351 passed/27 skipped/1 failed/31 errors；32项均为上述历史fixture取源问题。修复后重新完整执行：host/preflight14 passed（3.53秒），全量2385 passed/27 opt-in skipped/0 failed（247.71秒，1条既有LangChain预告）。临时虚拟环境显式安装当前源码并于退出清理；不修改冻结host或放宽断言。
- `python -m mypy --strict src`：130源文件通过；`python -m compileall -q src`及5份新增测试编译通过。
- agent-service目录执行`..\serviceCenter\mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test`，测试环境为当前PYTHONPATH、stub、Knowledge默认false：BUILD SUCCESS，40 tests/0 failures/0 errors/1 opt-in skip（32.565秒）。当前Access/Business/Knowledge Spring→Runtime non-live E2E实际执行，Knowledge E2E 1 passed；不把它写成新7/6/v3接线验证。

其他Java模块及PowerShell源未变，未在本切片重复其Maven/AST；历史回归及既有35/37追踪通过不等于重新执行真实UAT。阶段A内容/索引/alias/绑定、旧任务及七批资产无修改；无公开DTO、依赖、权限或数据变更。本轮真实模型、ES、embedding、rerank新增调用均0，累计仍15/37/23/12/12；不准备run-08、不复用已消费授权。

下一直接实施项为需求排序及Summary覆盖两个消费者，二者完成后才能切生产根并执行新完整non-live与正式复评。UAT Deferred、QUALITY Blocked；保留所有未通过P0和未执行场景，不声称阶段B完成。

公共合同代码/测试原子提交：`c14455fb2ec5e14728ef463d0808a7a6768c368c`（14项精确路径）。提交前status、diff --check、cached清单及完整差异已复核，密钥/JWT模式扫描0命中；无历史资产删除或业务/索引修改。计划状态同步单独提交，推送结果以Git实际结果为准。

### 20.38 必要证据重排组件实施与复核

从clean HEAD=`dfc50b4c6a39ba1693ca1a9bbe6f7beb5dbf71d7`继续既有批准合同，新增`quality_ranking_v3.py`及内部候选标签，Retrieval Stage显式消费v3。每域沿既有RRF池≤40，每需求串行BGE、最多4次/160次评分；锚点按需求序保留、同identity合并标签、普通候选轮转，不比较跨query裸分数。没有新增检索、扩域、topK或fallback。旧消费者拒绝新标签，完整版本集合/Capability/生产根未切换，当前仍Rewrite6/Summary5/quality-v2。

按DR-KRET-029及读取/快照合同执行两轮代码对照复核（同一执行者、编辑与评审分阶段）：首轮发现全路径Profile版本一致性检查原在BGE之后，已前移到融合/重排之前，反例证明Profile不一致时BGE0；第二轮复核需求域、canonical身份、分数归属、锚点/轮转、空域、并发取消与失败零后续调用，组件切片Blocker/Major/未处理Minor为0。旧排序、历史runner/fixture源、阶段A绑定及服务合同未修改。ranker仅保证必要证据的排序机会，不证明语义蕴含或UAT效果。

实际验证（测试子进程移除Key，不读取值）：

- `python -m pytest tests/unit/knowledge/retrieval tests/contract/knowledge tests/integration/knowledge/test_requirement_plan_production.py -q --tb=short`：372 passed（1.47秒）。最初新增并列顺序测试误把chunk次序置于RRF之前，按批准排序键修正预期，未修改算法或旧断言。
- 后续新增Gateway→Rewrite7→Plan→需求重排fake接线，组件文件最终35 passed（0.61秒）。一次从仓库根误执行导致tests包导入失败；改为agent-runtime工作目录通过，没有修改导入合同。
- `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`：host/preflight14 passed（4.55秒），全量2422 passed/27 opt-in skipped/0 failed（353.54秒，1条既有LangChain预告），包括上述最终接线测试；临时安装环境已清理。
- `python -m mypy --strict src`：131源文件通过；`python -m compileall -q src`通过。
- es-query-service目录执行`..\serviceCenter\mvnw.cmd -Dtest=Knowledge*Test -Deureka.client.enabled=false test`：29 tests/0 failures/0 errors/0 skipped，BUILD SUCCESS（10.550秒）；DTO/Profile/安全/endpoint使用非live依赖，既有Mockito/JDK预告不影响结果。

本轮未重复Spring Java E2E，前一公共合同切片的40项执行保留原证明范围；新7/6/v3完整对象图必须在Summary完成后再验证。无Java/PowerShell修改，不重复其他Maven/AST；全量包含Knowledge/Core/Business、35/37追踪和历史hash，不等同于重做真实UAT。新增真实模型/ES/BGE调用0，累计仍15/37/23/12/12，不创建run-08。

代码/测试提交=`2d20cd6c5132e4d638dc720dc3060a1fb8ec63e7`，6项精确路径，暂存完整diff、删除范围（无删除）、凭据/JWT模式0命中及diff --check均通过。L2/P3/索引仅如实同步部分实施，版本不变，无新语义或门禁。IMPLEMENT In Progress、NONLIVE Blocked、UAT Deferred、QUALITY Blocked；Summary6/Evidence覆盖、新成对生产绑定及最终复评尚未完成，整体B-CR-001与B-R7三项继续Open。

### 20.39 必要证据Summary组件与敏感输入边界复核

从clean HEAD=`677064ab0c38f4813d12c8ccf526b5d0b85ba3ca`落实DR-KEV-029/030：新增Summary6精确子类型/schema2/coverage合同；Evidence检查请求需求与锚点身份，同一序列化函数计算最大及实际模型payload；coverage核对需求、实际出域输入、源hash/identity/域及引用后，继续使用未修改的ExtractiveSummaryValidator。必需锚点缺失或装不下为insufficient、Summary0；畸形coverage为invalid_summary，不伪装成无证据。三层policy省略的元数据不补发，8证据/32KiB/5点/512字符上限不变。新增测试专用citation v2先核对真实schema2输入，再向未修改的v1检查器投影原字段，gold只在执行后使用。

代码对照设计复核为三轮，同一执行者、编辑与只读复评分离，不宣称另一独立人员审查：

| 发现 | 修复与结论 |
|---|---|
| B-CODE-EVIDENCE-001，高；中文紧邻ASCII邮箱绕过既有CONTACT分类 | 首轮Stage反例真实复现：敏感问题出现Summary调用。原Unicode词边界改为不依赖词分隔的邮箱存在性分类，CONTACT deny策略不变；第二轮发现首修后英文句号漏检，补齐句末中英文标点反例。第三轮复核两种Guard、Stage零调用及无邮箱话题不误拒绝，关闭 |
| V6源与声明可核对但不是语义证明 | 专门合成反例证明结构通过仍可缺分类/时效事实；必须保留人工语义/核心P0判据，不把结构validator或fake称为效果通过 |
| 历史载荷及检查器兼容 | 旧Summary基类不增字段，V1～V5、policy、extractive、v1 citation、历史run资产字节不改；旧任务拒绝新子类型，V6拒绝旧基类，均0outbound |

组件切片Blocker=0、Major=0、未处理Minor=0；整体B-CR-001及B-R7-DOM/COV/PROOF继续Open。没有设计语义改动，不重复设计批准或新增Gate；文档仅同步已验证组件状态，版本不变。当前生产仍Rewrite6/Summary5/quality-v2，不能把新组件测试当成新完整对象图或真实UAT。

本轮实际验证（子进程移除Key，不读取值）：

- 初次新组件用例114 passed/4 failed：均为新增fixture构造错误（不可变tuple、无效枚举、超单段长度），修正fixture后119 passed（0.65秒），未削弱生产断言。扩大回归397 passed/1 failed定位上述邮箱缺陷，首修后相关446 passed（2.12秒）。
- `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`：host/preflight14 passed（4.55秒），全量2554 passed/27 opt-in skipped/0 failed（376.49秒，1条既有LangChain预告），临时安装环境已清理。该全量快照在最后6项句末标点反例之前，不冒充最终全仓数字。
- 最终邮箱修复后，`python -m pytest tests/unit/model/test_email_input_boundary.py tests/integration/knowledge/test_requirement_evidence_stage.py tests/contract/knowledge/test_summary_task_v6.py tests/unit/knowledge/evidence tests/system_e2e/test_knowledge_stage_b_citation_check_v2.py -q --tb=short`：177 passed（1.25秒）。
- `python -m mypy --strict src tests/system_e2e/knowledge_stage_b_citation_check_v2.py`：134 files通过；`python -m compileall -q src`及新增辅助/检查器/邮箱测试编译通过。
- agent-service执行`..\serviceCenter\mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test`：40 tests/0 failures/0 errors/1旧opt-in skip，BUILD SUCCESS（40.147秒）；当前Access、Business、Knowledge Spring→Runtime E2E实际执行，保持旧生产绑定的证明范围。

其他Java模块和PowerShell源未变，本切片未重复其Maven/AST。全量含历史hash及原35/37追踪，不等同于重做真实UAT。新增真实模型/ES/BGE调用0，累计仍15/37/23/12/12，retry/resume0；不准备run-08，不改阶段A内容/索引/alias、公开DTO、依赖或权限。

安全修复提交=`e2ed624b4e85d3c0f0e4d880c4a423e06f8b5216`；Summary组件提交=`07a445dc6c02121bf7c275f64564055fc792889c`。精确暂存2项/12项路径，完整diff、无删除及凭据/JWT模式0命中复核通过。下一步为新成对生产绑定、完整对象图fake/Spring/最终全量及代码复评。IMPLEMENT In Progress、NONLIVE Blocked、UAT Deferred、QUALITY Blocked保持真实状态。

### 20.40 必要证据生产单绑定与non-live收口

从clean HEAD=`7cf52bcf82b6bca1e294a00fd884fb101332b25f`完成既有批准设计的最后接线切片。当前bootstrap唯一注册Rewrite7/Summary6，Planner与Evidence使用quality-v3及配对limits，默认disabled不变；main在任何client前拒绝final_candidates<4，任务工厂先检查版本/ID/精确输入类型，Provider再次核对。新增需求贯穿原有Capability、Retrieval和Evidence，不新增流程、endpoint、模型复核调用或查询扩域。

当前完整对象图测试使用真实Gateway、两级解码、Planner、需求重排、Evidence/三层策略和旧extractive validator，只将模型及Knowledge HTTP替换为合成transport。覆盖单域三个证明、双域、缺失条件、unsupported、非法计划/coverage/引用、敏感输入、读取拒绝、部分/全部技术失败、输入/输出观测保护、取消与同一Runtime并发；计数与零后续调用均有断言。另通过DeepSeek HTTP格式fake响应验证provider decoder→任务decoder，不使用真实Key或联网。Spring现行harness只更新fake到7/6形状并显式断言版本；Java公共合同、16场景原断言与有限证据Schema不变。

代码对照设计复核两轮，同一执行者分离编辑和只读评审，不冒充外部独立人员：

| 问题 | 最小修复与关闭证据 |
|---|---|
| B-CODE-ROOT-001，中；合法unsupported被search需求校验误判rewrite_failure | Capability只对V3空域终态检查None/空tuple，继续原no_matching_domain；search仍必须有需求，畸形终态及错请求保持零检索。新根终态及5种内部注入反例通过 |
| B-CODE-ROOT-002，中；任务配对仅在Provider创建阶段检查，晚于client分配 | 同一校验前移至任务工厂并在Provider复用；错误版本、ID、输入类型及数量配置反例证明资源工厂零调用 |
| 历史版本测试在新根下失去原证明语义 | test-only fixture仅对10个明确路径只读加载run-07冻结Git中的组合根类；原测试、任务、runner、manifest/hash不改。测试结束恢复；新根/Spring不在隔离名单，精确作用域及恢复反例通过 |

首轮隔离按pytest模块名匹配，在源码树收集为`knowledge.*`时失效，出现78 failed/151 passed/6 skipped；改为精确绝对目录和文件名后，扩大集成275 passed/6 opt-in skipped。新fixture中多域sourceRank、已消费空HTTP响应和客户端base_url问题均已修正，未修改服务decoder、原错误分类或放宽断言。复评检查全部本切片diff、调用方和批准DR：Blocker=0、Major=0、未处理Minor=0；总体B-CR-001及B-R7-DOM/COV/PROOF仍Open，因为真实必要域、原文蕴含和核心P0未被新版本测量。

本轮实际验证（测试子进程移除Key，不读取其值）：

| 命令 | 实际结果 |
|---|---|
| `python -m pytest tests/integration/knowledge/test_requirement_runtime_composition.py tests/integration/knowledge/test_requirement_plan_production.py tests/system_e2e/test_knowledge_nonlive_runtime.py -q --tb=short` | 92 passed（54.98秒） |
| `pwsh -NoProfile -File scripts/run-nonlive-regression.ps1` | 正式临时隔离安装当前源码：host/preflight14 passed（4.45秒），全量2615 passed/27 opt-in skipped/0 failed（287.75秒，1条既有LangChain预告）；退出0、临时环境清理完成 |
| `python -m mypy --strict src`；`python -m compileall -q src tests/integration/knowledge tests/system_e2e/knowledge_runtime_server.py` | 133源文件类型通过；编译通过 |
| agent-service：`..\serviceCenter\mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test` | BUILD SUCCESS（32.639秒）；40 tests/0 failures/0 errors/1旧opt-in skip。Access/Business/Knowledge Spring→Runtime均执行，新Knowledge E2E 1 passed（5.287秒） |
| `python -m pytest tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py tests/system_e2e/test_knowledge_stage_b_run_07_history.py -q --tb=short` | 文档状态同步后19 passed（11.49秒，1条既有LangChain预告）；35/37追踪及run-07历史语义保持 |

状态文档只读复核发现P3来源表、Summary标题及旧版本段落仍有“待接线/当前旧版本”残留，已依据本次代码和测试修正，并将旧增量明确限定为当时状态，不改变历史事实。7份目标文档63个本地链接均存在；L1、三份L2和P3严格结构/追踪/DAG检查均0 errors/0 warnings。此次不新增设计语义或版本，不以结构校验替代此前设计评审或代码复评。

全量包括历史候选/七批资产hash、Knowledge/Core/Business/Employee/Transaction以及原35/37追踪，不等同于重做真实UAT。其他Java模块与PowerShell源码未变，不重复其Maven/AST；es-query-service29项最近实际结果见§20.38，不称为本切片重跑。StageA语料、索引/alias/策略快照、旧任务及历史数据零差异。新增真实模型/ES/embedding/rerank调用0，累计仍15/37/23/12/12，retry/resume0，不读取Key、不准备run-08。

代码/测试提交=`e1c391e3f2568e968fbffa1c30165314004175dd`，9项精确路径；status、diff --check、cached清单及完整差异、凭据/JWT模式0命中通过，无文件删除。文档仅同步已有批准合同的实际状态，L1/L2/P3/UAT版本不变、不新增门禁或语义批准。

IMPLEMENT=Done、NONLIVE=Done；GATE-KRG-006保持Closed，UAT=Deferred、QUALITY=Blocked。当前真实执行器仍是已消费的旧6/5/v2合同，不能用于新7/6/v3；未来新批还需显式定义Schema2来源绑定、原十例版本影响覆盖及≤4次重排预算，取得有效未消费执行合同后方可运行。旧三项成功不能自动迁移到新版本，剩余总预算不等于新批授权。阶段B整体未完成，不以non-live通过关闭核心P0或把结构coverage当作语义证明。

### 20.41 新版本专项UAT的只读恢复核算

2026-09-07从clean HEAD=`75b18a04212d4e1e4b2ce10a73d0576485f2a090`复核唯一剩余直接工作包`WP-KRETRIEVAL-UAT-01`。本节只是计划级依赖、兼容性和预算核算，不创建新run、manifest、authorization或执行器，不批准额外调用，不改变原case/gold及历史状态。前一切片实施/验证/推送为实际进展；本次通过读取当前源码及七批调用账核实下一步限制，不重跑已通过全量。

run-07六项文件SHA与§20.34一致。由其manifest.priorRuns.calls加result.totals重新求和，累计为15 E2E/37 model/23 search/12 embedding/12 rerank，Business/retry/resume均0。目标原上限20 E2E/60 model剩5/23；最后一次精确运行协议上限21/60剩6/23。两者都不足以在新版完整测量原十例，不能由计划自行选择更宽上限或把历史余额作为新授权。

| 原case | 现有证据与新版直接影响 | 完整通过路径模型次数 |
|---|---|---|
| KB-001 | run-06澄清Passed仅属旧任务；V7非search新五字段及终态需真实验证 | 2：selection+Rewrite |
| KB-015a | run-06单policy Passed；V7需求、V3重排、V6引用覆盖已变化 | 3 |
| KB-004 | run-06双域Passed；同上，不满足旧三项复用条件 | 3 |
| KB-002 | run-07 Failed；必要域、分类/规则/时效共同证明为核心缺口 | 3 |
| KB-003 | 旧批未执行；单域两类必要原文及多需求 | 3 |
| KB-005 | 旧批未执行；缺必要期间的澄清，不允许假设条件后查询 | 2：selection+Rewrite |
| KB-006 | 旧批未执行；历史期间、分类及适用规则 | 3 |
| KB-015b | 旧批未执行；措辞变体、双域和适用性证明 | 3 |
| KB-016 | 旧批未执行；非酒店保留问题和文号约束 | 3 |
| KB-008 | 旧批未执行；单law查阅，不强制适用判断三角色 | 3 |

原十例及七项gold读取自未修改的`tests/system_e2e/knowledge_stage_b_cases.py`。完整成功路径为两例澄清、八例检索摘要，即10 E2E/28 model；这是预算推导，不是已执行结果。23次模型余额不足，不能跳过selection、改成fake模型、删除用例或把旧三项合算为新版通过。若未来保持通用每case最多3模型的保守运行上限，则需新批最多10/30，累计上限至少25/67；这些只是待用户明确批准的请求规模，不在本节生效。search≤4、embedding≤2、V3 rerank≤4的单case硬边界不变，新批及累计本地调用上限也须一起明确，不沿用旧≤2 rerank合同。

兼容性只读检查：相对旧复用准入提交`550b012ad390463816372054d1c87f5877209f40`，允许范围内现行生产源码有18条变化（含新需求类型/两消费者/根/观测/安全修复），超出旧协议只允许三文件且必须精确字节一致的约束；新任务为7/6、quality-v3，不能通过更新旧hash放行。Rewrite7输出上限由旧512变为1536tokens，Summary6实际输入为Schema2且增加coverage输出；未来费用快照与来源校验应绑定已实施`stage-b-citation-binding-v2`，不能直接使用旧schema1评分或只改旧runner的版本常量。

下一步最小范围是明确批准新版本原十例的独立执行合同及足够的累计预算，然后按现有L2/UAT规则完成新runner/快照/有限证据的non-live验证和冻结，再执行一次失败即停止的真实批次。无需重新设计生产链路、重建索引、修改gold、增加审批Gate或重复全部已通过代码实施。授权和合同未满足前，UAT继续Deferred、QUALITY继续Blocked；本轮Key读取、模型/ES/BGE调用、服务启动、新候选资产均0。

本轮focused计划自审确认：只有UAT这一直接后继受限，不重开已完成IMPLEMENT/NONLIVE，不新增Gate/依赖、不改上位合同。实际只读脚本断言10例/2澄清/8检索/28模型成功路径、run-07六项hash全部相等；P3严格校验0 errors/0 warnings，git diff --check通过，差异仅本计划。没有生产或测试代码修改，不重复pytest、Maven或live，以前一节完整回归保持其实际证明范围。

### 20.42 新版十例执行授权与准备

2026-09-07用户对§20.41之后明确提出的run-08规模回复“授权”：本批10 E2E/30模型/40search/20embedding/40rerank，累计25/67/80/40/52；Business/answer/retry/resume0。起点clean HEAD=`5b245eaa0c4d5cea248b07a60e91fabfc4471ad0`。本授权只恢复UAT工作包，不重开已完成生产实施/non-live，不自动授权run-09。旧七批和原10例/gold不变，新模型版本不复用旧三项通过。

具体执行合同由UAT_01 §14.22治理，技术继承DR-KFLOW-024、DR-KRET-029、DR-KEV-029/030。修改范围为新增测试runner/直接fake测试、P3/UAT_01及ARCHITECTURE版本索引；不改L1/L2稳定设计、生产源码、公开接口、索引或权限。先完成协议三轮自审与分离编辑的只读跨层评审，再实施runner、fake和代码复核，提交后生成实际冻结绑定；最后执行唯一真实批次。不得在runner未验证时提前读取Key。

三轮协议内审：第一轮确认原十例不复用与Schema2实际输入/引用源绑定；第二轮发现旧执行器只有哈希子集检查及无显式authorization，协议补入完整资产集合、独占authorization及target目录允许集合；第三轮核对DAG、预算算术、先journal后outbound、失败终态、owned清理和无run-09，未发现新增问题。随后分离编辑进行只读跨层评审，针对本协议实施准入结论通过，S0=0/S1=0/未处理S2=0；同一执行者阶段分离，不冒充外部独立人员。实际代码、安全及效果通过仍须后续证据，不以协议评审替代。

执行器实施新增`knowledge_stage_b_uat_v8.py`及直接fake测试，不改历史runner。正式代码对照协议复核两轮：首轮B-R8-001发现环境预检失败记录未参与执行准入，修复为严格要求readiness、Spring/auth/stub冒烟、client关闭及owned进程/日志清理的唯一成功记录；增加缺失、失败、重复异常及清理不通过拒绝用例。复评读取完整代码/测试，确认实际Schema2输入捕获而非从payload重建，原gold/域/任务/quality判据未弱化；本执行器切片Blocker=0/Major=0/未处理Minor=0。该结论不等于阶段B真实效果已通过。

2026-09-07实际验证：`scripts/run-nonlive-regression.ps1`在临时安装当前源码的隔离环境中host/preflight 14 passed、全量2670 passed/27 opt-in skipped/0 failed（297.96秒）。收集后补入6项预检测试，另行运行v8+citation-v2+两份当前UAT追踪=88 passed（3.37秒）；旧base+v8+run-07 history=79 passed（14.24秒），覆盖最终切片，不把新增6项冒称已进入前次全量收集。`mypy --strict src`133文件通过，`compileall`源码和两新增文件通过。P3严格校验0 errors/0 warnings，diff --check通过，历史七批hash及35/37追踪通过。

agent-service实际执行Maven测试40项、0失败/错误、1历史opt-in跳过（31.530秒），含当前Spring→Runtime Business/Knowledge E2E。命令使用`-Dagent.runtime.python=C:\Python312\python.exe`及进程级`PYTHONPATH=D:\codex\agent-runtime\src`；前次未设置PYTHONPATH导致隔离子进程`ModuleNotFoundError`，不是生产缺陷，不改断言或全局安装。另一次未引用PowerShell的`-D`参数导致命令解析失败，已用带引号参数纠正。其他Java/PowerShell源码未变，不称为本切片全部重跑。所有non-live命令移除子进程Key；新增真实模型/search/embedding/rerank=0，依赖只读health不计业务查询。冻结和执行尚未发生。

### 20.43 run-08一次性终态及只读根因复核

§20.42准备提交为文档`b869839`和runner/fake `1fbd62aeebc01af0951ddcd62281be589f6eba6a`，已推送origin/codex；后者为本批clean frozen HEAD。360项源码与258项Java执行资产、原十例/gold、旧七批、7/6/v3及Schema2来源校验冻结后，readiness与Spring/auth/stub预检通过；在未修改tracked文件的前提下独占authorization，再执行唯一一次live。具体run和case权威见UAT_01 §14.23，原始七项资产在`agent-runtime/tests/system_e2e/knowledge_stage_b_run_08/`。

结果：首例UAT-KB-001 Failed，其余九例Not executed，result.status=failed，failureKind=null表示无launcher异常，不是业务通过。实际E2E/model/search/embedding/rerank=1/2/4/2/2；加历史账后16/39/27/14/14，未超25/67/80/40/52。Business/answer/retry/resume=0。consumed已生成，本批授权已终止，余额不授权重试、续跑或run-09。

| 问题/等级 | 当前证据与根因边界 | 最小后续处理及状态 |
|---|---|---|
| B-R8-SEM，Major：缺少决定性条件却进入search | 原case冻结预期clarification；Rewrite7调用succeeded，实际policy+law四路径、两需求rerank、Evidence产生。当前结构校验不推断用户意图，不能证明模型选了正确终态。Prompt的lookup/具体适用判断区分与“缺条件须澄清”在这次模型选择上未稳定落实；未保存原始输出，不能声称已核实其推理或补造了哪些条件 | 先聚焦审查缺条件适用问题与普通规则查阅的决定顺序，形成非live对照方案；不硬编码酒店/用例ID，不放宽原澄清零调用判据，不靠加topK或更多付费请求修复。Open |
| B-R8-DIAG：摘要provider_failure容易误归因供应商 | 新runner对冻结澄清case禁止Summary，先于model count/journal拦截；gateway把该本地异常映射为provider_failure。模型观测有三任务，真实HTTP尝试journal只有selection+Rewrite两次。不能把该502称为DeepSeek服务故障，也不能用它掩盖更早的澄清失败 | 本轮证据说明与历史断言明确本地拦截；不改已冻结runner或result，不伪造新的failure枚举。新版本诊断若有需要应先设计，不在已消费运行补采原始响应 |
| B-CR-001及B-R7-DOM/COV/PROOF，既有未关闭质量风险 | 新版原九个检索/后续澄清case均未执行；本批无Summary outbound、无最终引文，不能据此关闭必要域、必要原文与完整证明缺口 | 保持Open，不把non-live或旧三例通过迁移成新任务效果通过 |

该失败不是原文缺失、索引不健康或候选窗口证据：实际三路返回候选，law keyword正常no_result；没有路径技术失败记录，流程已到Evidence。两次rerank且两域均非空与lookup路径相符，但有限资产未保存question_kind，结论只认定“错误进入search”，不把推断当原始模型事实。不得修改阶段A内容/alias、gold、公开状态或validator来使其通过。

读取授权、单动作和禁止Business的执行限制未被突破；但功能要求“该缺条件case检索0”确实失败，安全未越权不等于功能Passed。`citationBindingValid=true`及空requiredClauseChecks是澄清case不进入引文校验的空检查，不能计为Summary成功或引用已测量。代码/evidence复核以此保留整体Major，不宣布阶段B收口。

环境及真实两个阶段均记录clientsClosed、ownedProcessesStopped、rawLogsDeleted、secretScanPassed=true；实际核查18090/19201/18080/19091无监听，本次进程已退出，临时原始日志已删除（仅本次日志，不可恢复；有限证据仍保留）。阶段A只读alias/UUID/snapshot与冻结一致；本轮无索引、数据、权限、生产源码或公共DTO修改，无run-09。

终态后新增6项只读历史验证，检查七资产exact SHA、Schema8与独占authorization、原十例及九未执行、当前/累计调用账、三任务观测与两次HTTP尝试区分、环境/cleanup、360源码从冻结提交重建及有限字段。定向命令`python -m pytest tests/system_e2e/test_knowledge_stage_b_run_08_history.py tests/system_e2e/test_knowledge_stage_b_uat_v8.py tests/system_e2e/test_knowledge_stage_b_citation_check_v2.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q --tb=short`最终94 passed（19.58秒）；新增测试初次有手工抄写SHA多一个字符、quality版本缩写两处笔误，按原文件实际值修复，未修改任何冻结资产或放宽比较。再次`mypy --strict src`133文件与compileall通过，七资产凭据/JWT模式扫描0命中，P3严格校验0 errors/0 warnings，diff --check通过。

终态只读证据评审确认原始字节、账本、停止点和状态同步一致，记录与测试切片无未处理Blocker/Major；整体语义质量Major仍Open。文档本次仅同步运行事实和已发现差距，不改变L1/L2合同或验收判据，不新增批准门禁。全量与Java结果仍为§20.42本轮实测；终态后只有历史测试/文档新增，因此执行定向复核，不把终态94项算入此前2670项全量，也不重复模型请求。

提交前发现默认Git文本属性会把新有限JSON的CRLF转LF，故沿用旧run目录规则，为`.gitattributes`精确增加run-08目录binary一行。仅影响本批七文件；原始资产不转换，暂存blob逐项SHA必须等于原始target/归档/hash常量。该必要字节保护不修改历史规则、manifest或全局Git配置。

有限失败证据、历史验证及精确字节属性提交=`1ab4f6c5ac77246a26ab3ae4a9b5d1653474be80`；提交前七项暂存blob与target/归档/hash常量全部相等。未删除文件或提交目标外修改。设计、实施、non-live已完成的证据范围不变；实现入口GATE-KRG-006保持Closed，UAT=Deferred、QUALITY=Blocked，整体目标未完成。后续优先处理B-R8-SEM的非live设计分析，不创建新run、不补跑旧批、不把未消费余额误当持续付费授权。

### 20.44 澄清优先指令恢复（non-live）

起始clean HEAD=`61a8f68ce4428b8edfe761394d23122007c24bcf`且与origin/codex一致。代码逐段比较补强B-R8-SEM根因：V4明确先判适用/查阅、禁止默认用户条件和将不完整适用降为查阅；V5/V6继承该段，V7完整重写Prompt时遗漏大部且改为“确定条件下的具体适用判断”。这是现行DR-KFLOW-019继承缺失的直接证据；本批真实终态失败仍不能精确归因其全部模型推理或question_kind。结构validator无法代替语义判断，不能靠新增本地关键词分支或topK关闭。

L2_01_00 v1.25/DR-KFLOW-025最小方案：新V8精确替换V7意图段，保留五字段decoder identity、输入、预算及其余指令；仅当前根绑定8/6/v3，旧7显式历史可用但生产不可达。Summary/排序/索引/策略/公共DTO不变。受影响IMPLEMENT/NONLIVE先暂停至该切片设计复评；无新DAG边或Gate，UAT继续Deferred、QUALITY继续Blocked。

三轮内审：第1轮核对REQ-KQUALITY-003/KQ-AD-015、§8.1与8.5，固定先决策再计划及不机械要求所有条件，补齐主追踪；第2轮核对decoder兼容、版本守卫、原8192bytes和零调用、rollback，补入旧run-08依赖helper须按冻结源码隔离而非改断言；第3轮校验测试定义和版本状态，修复REQ来源本地映射与VAL-KFLOW-008定义缺失，严格校验最终0 errors/0 warnings。随后冻结修改，按L2及跨层rubric执行只读复评：本非live切片S0=0/S1=0/未处理S2=0，准入实施。该审查由同一执行者分阶段进行，不冒充外部独立人员，不证明真实模型语义。新增任务/测试此时尚未实现。

实施已完成：新增`knowledge/rewrite_v8.py`、V8合同测试及历史fixture隔离恢复测试；当前根唯一8/6/v3，Spring fake harness同步8。没有修改历史V4～V7任务、run-08 runner/原断言或七项运行文件。旧fake helper未列入live manifest，历史fixture因此将其冻结提交源码SHA单独核对，不伪造manifest条目；仅精确匹配该已消费runner的一项fake测试，测试后恢复当前根与module。

首次定向命令未设置进程PYTHONPATH，发生6项collection错误、没有测试执行；纠正测试环境后226 passed/1 fixture error，根因为把历史fake helper误当manifest资产。按实际冻结源码校验修复并补隔离作用域/恢复测试后，V8+V7合同、当前生产根、历史run-08及Spring Python harness定向296 passed（44.76秒，1条既有LangChain预告）。`mypy --strict src`134源文件、compileall通过。没有放宽decoder、原断言或运行合同。

正式代码对照DR-KFLOW-025只读复核：版本/指令之外definition/request相同、parse_response同一对象、预算不变；旧版本不进当前根，disabled/非法任务在资源创建前拒绝；当前fake覆盖澄清/unsupported零下游、单/多域、coverage/引用拒绝、授权/敏感输入、并发/取消和无fallback。历史helper问题已修复，复核未发现本切片未处理Blocker/Major；同一执行者阶段分离，不冒充外部独立评审。真实语义B-R8-SEM及B-CR-001仍Open，不能据fake通过宣布阶段B完成。

首次正式隔离全量：host/preflight14 passed（3.93秒）；2750 passed/27 opt-in skipped/2 failed（292.00秒）。两项均复现：当前注册测试仍断言7而非8；需求重排时钟相减得0.010000000002037268，严格≤0.01断言误报。前者按本增量迁移当前版本断言；后者仅在该测试替换ranker模块所见时钟为0→0.03，保留原≤0.01、只调用一次和下一需求前TimeoutError全部断言，取消测试内真实sleep，生产deadline逻辑不变。定向注册/排序/历史44 passed（12.07秒）。该测试修正按DR-KRET-029复评，属于可复现性修复，不是放宽时限或新增排序策略。

agent-service Maven命令同§20.42，进程PYTHONPATH指向当前源码且移除Key：40 tests/0 failures/0 errors/1历史opt-in skip，BUILD SUCCESS（29.774秒）；当前Access、Business、Knowledge Spring→Runtime E2E均执行。1份L1、三份L2及P3严格结构/追踪/DAG校验均0 errors/0 warnings；外围L1/L2仅据实际任务绑定同步，不改变语义或升级版本。授权消耗仍为§20.43。新增外部模型0、不读取Key、不创建run-09；本地ES/BGE结构诊断单独记入§20.45，不与真实UAT调用账混算。

最终重跑`pwsh -NoProfile -File scripts/run-nonlive-regression.ps1`：正式临时环境显式安装当前源码，host/preflight14 passed、全量2752 passed/27 opt-in skipped/0 failed（292.23秒，1条既有LangChain预告），脚本退出0并清理临时环境。27跳过为既有受控live/诊断opt-in，不是本次关键E2E跳过；不以其为真实效果通过。后续追踪/隔离复核14 passed（0.83秒）；所有新增及修改Python编译通过。全量包括Knowledge/Core/Business/Employee/Transaction、历史八批及原35/37追踪；其他Java模块和PowerShell源码未改，未重跑其Maven/AST，不复制旧数字冒充本轮。

修复后的第二轮只读代码复评、最终跨层状态复核均未发现本切片未处理Blocker/Major/Minor；修正L2末尾旧“未实施/7”状态，明确8/6/v3是代码绑定、不是当前用户服务已重启或真实UATPassed。7份修改Markdown的57个本地链接均存在；凭据/JWT模式扫描0命中，diff及暂存完整差异检查通过，无删除文件、旧任务/runner/运行文件及StageA工具/发布绑定零差异。

代码及测试原子提交=`7162ee5122f6d1069bcf1048168a14981451a6c7`，11个精确路径；目标文档/只读诊断另行提交后一并推送。IMPLEMENT/NONLIVE对本次澄清恢复保持Done，UAT=Deferred、QUALITY=Blocked；真实语义Major和新的向量结构验证不因该提交关闭。阶段B目标保持未完成，下一步为§20.45授权内结构对照与必要设计，不再重复本轮完整回归或重启已消费批次。

### 20.45 政策库向量存储结构追加授权与只读诊断

2026-09-07用户明确允许为目标调整政策库ES向量存储结构。该授权解除阶段B原先“结构一律不可调整”的对应限制，允许目标内结构方案、候选对照及必要迁移设计；不自动批准任意重建、覆盖旧索引、扩大权限、修改原文/公共DTO或新增付费run。授权范围内正常步骤不再逐项申请；任何写入/发布前仍须有审查通过的具体方案、验证和可回滚目标。当前只完成读取和诊断，存储方案尚未批准实施。

实际环境：ES 9.4.1，alias=`agent-doc-tax-policy-v2-read`，目标=`agent-doc-tax-policy-v4-20260903-corpus-a5`、UUID=`SurWRSglRd6ZRddEBWy2Sw`。该物理索引由tax.policy与tax.law共享、按Profile channel过滤；不能只因名称含policy就覆盖或丢弃law内容。15,521记录均有向量；14,783基线条款、738附件片段。当前embedding为1024维cosine、bbq_hnsw、m16/ef_construction100/rescore oversample3。正文2～1166字符、均值591.33；小于100字符的片段1,060条。

诊断固定原始公开问题/既有人工gold，只在离线检查比较、不供在线排序；同一policy过滤、同一查询向量，ANN沿用k21/num_candidates100，精确对照使用cosine script_score top100。5题ANN与精确前20 ID均20/20重合。下表“窗外”表示未进入指定窗口，不代表原文不存在：

| 问题类型 | 必要片段 | ANN前21排名 | 精确前100排名 |
|---|---|---|---|
| 短检索词“住宿服务生活服务” | lodging / living | 2 / 5 | 2 / 5 |
| 生活服务中住宿如何定义 | lodging / living | 6 / 窗外 | 6 / 窗外 |
| 住宿与不动产租赁分类边界 | lodging / rent | 窗外 / 21 | 窗外 / 21 |
| 2016一般计税住宿税率 | lodging / historical_rate | 窗外 / 窗外 | 窗外 / 70 |
| 软件即征即退证明材料（保留问题） | software | 2 | 2 |

这5题没有显示ANN量化/近似损失，暂不建议先更换HNSW或量化算法，也不能外推为全库算法无损。`knowledge-corpus-tools/indexing.py`目前只将`chunk.content`送入embedding，不带标题和层级。四条必要片段长度58/74/39/43，section仅为宽泛“销售服务”或“税率和征收率”；均有parentDocumentId但validityStatus=UNKNOWN，不能将有effectiveDate误判为现行有效。因此“上下文不足的短条款向量”是有证据支持的候选解释，尚非已验证修复。

最小下一步是对照验证“保留引用原文，另构造带可信标题/父级分类上下文的向量输入”，必要时完善条款层级关系；不改原文hash或用模型补写政策，不以gold/文档ID定制生产加分。采用新的候选索引及版本化构建器，不复用仅接收阶段A前置mapping的旧create_and_clone去覆盖a5；保留共享law数据、旧索引、读授权/出域元数据及快照，发布只在必要原文覆盖、引用、兼容和回滚验证通过后进行。若单纯上下文向量无收益则不发布，继续按证据区分分块/检索/排序问题，不无限放大窗口。

本次实际本地诊断：ES HTTP17（其中一次dense_vector missing聚合不支持，改用exists过滤后成功）、BGE HTTP1/文本5；付费模型、rerank、业务接口、ES写入/新索引/alias切换均0。未保存向量、原始模型响应、JWT或正文。该诊断不是一次新的UAT，不能关闭缺条件错误查询、必要证据或完整专项风险；run-08及累计付费账保持不变。结构追加授权与Prompt遗漏属于两个独立因果层面，不能互相冒充关闭证据。

### 20.46 全政策库向量表示对照与最小实现切片

起始HEAD=`92ee9907fdfef004fd3483bb1a44eda6df316ce7`，codex/origin一致且clean。承接§20.45结构授权，本轮只读固定write-blocked源及UUID、policy Profile的八类channel。先对996条候选池比较，再对全13,909条policy记录作三臂精确余弦比较；gold只在排序之后判排名，不进入表示构造。源fingerprint=`71983e8060434cf835ed56ad2321dd30cffe57ce63ce3b7810a51893d5838d1f`，按chunkId排序，逐行绑定ID、实际原文SHA、库存hash、title、section。共享law不在重编码试验中，没有修改或省略现行law数据。

| 固定问题 | 必要原文 | 库存向量排名 | 同BGE仅重编码正文 | 同BGE标题＋现有章节＋正文 |
|---|---|---|---|---|
| 住宿服务生活服务 | lodging / living | 2 / 5 | 2 / 5 | 1 / 2 |
| 增值税政策中，生活服务中的住宿服务如何定义？ | lodging / living | 6 / 155 | 4 / 74 | 1 / 3 |
| 住宿服务与不动产租赁的增值税分类有什么区别？ | lodging / rent | 481 / 21 | 361 / 14 | 3 / 4 |
| 2016年一般纳税人按一般计税提供住宿服务的增值税税率是多少？ | lodging / historical_rate | 5141 / 70 | 4556 / 82 | 41 / 24 |
| 财税〔2011〕100号规定软件产品享受增值税即征即退需取得哪些证明材料？ | software | 2 | 2 | 1 |

全库每臂使用同五个查询向量，候选排序稳定为余弦降序/chunkId升序。context输入仅去除title/section中空、精确重复或与content相同的项，然后以换行连接原文；没有猜测税率/层级、条款合并、gold特判或修改topK。996池中“推测祖先”在租赁及保留问题不优于简单context，且存在把相邻段误作上级的风险，因此不纳入当前方案。子集不是完整排名证据，最终采用上表全库结果。

738附件的库存向量与当前正文重编码最小cosine=0.9999682729；13,171基线片段全部低于0.99（最小0.3327238893），且其库存contentHash均不同于当前content实际SHA。Java实际返回候选时重新对原文计算hash；不能因此修改原文或放宽附件hash，也不能在未核实原导入输入/模型前武断称为BGE模型故障。对照已将重编码收益与context收益分开，标题/章节有实测收益；历史税率必要原文仍在现有前20之外，完整核心P0未通过，不能发布或关闭QUALITY。

向量比较合计ES HTTP40、BGE embedding HTTP989/文本30821，另health GET1；其中最终全库18/891/27823、628.7秒。先行试验一次缺numpy在网络前退出，改用标准库；另一次legacy hash假设错误在ES8/BGE1(5文本)后停止，核实真实Java hash语义后才启动不同对照，不掩盖失败或重试付费。无Key读取、外部模型、业务接口、rerank、ES写入、alias变更、服务启停或新付费run。起止alias、UUID和write-block均一致。

当前最小实施单元为L1_01 KQ-AD-019/L2_01_01 DR-KRET-030：离线纯表示构造器及定向测试，不触达HTTP/生产根。现有主WP下直接依赖为“对照已完成→表示设计评审→纯函数及fake→新候选构建合同/实现→只读候选验证→有证据才发布”；不新增Gate，不复用老StageA create_and_clone覆盖a5，不把下游迁移设计冒称已就绪。UAT=Deferred、QUALITY=Blocked不变；新构建器、模型身份快照、全记录保持、source/law/ACL/egress fingerprint及发布演练尚未完成。后续结构范围内继续推进无需逐项授权；新的付费批次不包含在旧已消费run中。

设计三轮内审：第1轮固定同记录输入、无祖先推断、实际body与历史hash分离；第2轮限定三种错误码、边界先验证、禁止正文repr/隐式截断，并明确纯函数不拥有ACL决策；第3轮补全DR定义、计划新增路径标记和主追踪，修复索引页链接笔误及L2尾部版本。随后只读复核REQ-KCORPUS-003/004/006、SA-AD-006、KQ-AD-019及DR-KRET-030，范围不改变上位在线/安全权威；本纯函数设计切片S0=0/S1=0/未处理S2=0。该评审同一执行者分离编辑进行，不冒充外部独立人员。1份L1、目标L2和P3严格校验0 errors/0 warnings，7份文档63个本地链接可解析。代码尚未实施时不以计划路径存在性作为实现证据。

后续只读模型来源核查确认8908由既有Docker BGE-M3服务提供，实际encode固定max_length=1024、fp16；容器镜像/服务源码hash、缓存revision及库版本记录于本轮有限evidence。使用同一只读源、相同fingerprint和缓存tokenizer纯CPU计数，额外ES17次、embedding0：738附件正文/新表示最长224/244 tokens，均不截断；13,171基线正文4条超限（max1070），新表示7条超限（max1102），纯函数字符/字节校验拒绝0。故前述全库向量试验7条context实际被服务截断，不能视为全库无损构建证明。累计本轮ES57，BGE仍989/30821、health1、付费0/写入0。追加复核区分纯函数字节边界与模型token前置，并将无截断预检明确于L2 §12.8；不引入Tokenizer依赖、不修改BGE服务、不放宽输入边界。

随后完成“仅重编码738个受控附件、保留13,171基线向量”的全policy离线对照，仍是同五问题和源fingerprint，范围按assetKind与Profile而非gold/文档ID。必要原文排名依次为1/2、1/3、4/6、33/18、2；定义/边界明显改善，税率规则进入前20但住宿定义仍33，软件保留问题仍2。该最小范围比全部重编码更适合进入候选设计，且全部待重编码文本无token截断；不修改law、不重新处理正文或放大窗口。新增ES18、BGE25/743文本、18.2秒，写入和付费0；本轮累计ES75、BGE1014/31564文本、health1。局部候选本身尚未构建/发布，不能称为真实检索或完整P0通过。历史税率覆盖、旧基线向量来源、模型权重身份及完整发布回归继续显式待办。

设计/诊断提交=`499f837`。随后DR-KRET-030纯函数及48项新测试完成，旧indexing.py、既有依赖和生产根未改。正式代码对照设计复核两轮：首轮`B-VEC-001`发现`raise ... from None`仍在异常`__context__`保存非法输入；改为离开Unicode处理块后抛有限ContractError，并验证cause/context均None。第二轮复核原字节、精确去重、三种错误、字符/字节边界、frozen/repr、无网络/全局读写/计划/gold依赖，纯函数切片无未处理Blocker/Major/Minor。该复核与作者编辑分开执行，不冒充外部独立人员；整体语义和P0风险不关闭。

实际验证：使用已存在`D:\codex-data\knowledge-corpus-stage-a\.venv\Scripts\python.exe`，`-m pytest -o addopts='' tests -q --tb=short`最终78 passed（1.07秒），含48新例与30原工具例；`-m mypy --strict src`14文件通过；`-m compileall -q src tests`通过。先在通用C:\Python312检查工具依赖时缺pymupdf，未执行工具回归；定位README指定既有隔离环境后全部通过，无安装或全局配置修改。agent-runtime以进程PYTHONPATH运行run-08 history及两份current traceability，18 passed（12.62秒，1条既有LangChain预告），覆盖七项冻结hash和原35/37追踪。所有测试子进程移除Key，无真实模型调用。

L1、三份Knowledge L2和P3严格结构/追踪校验0 errors/0 warnings，63个本地链接存在；有限JSON计数/排名/预算算术及凭据/JWT模式扫描通过。源码引用仅在新离线模块及其测试，没有接入现行builder或在线生产。历史run、StageA evidence及旧工具源码、Java服务/权限、现行索引/alias均不变；新模块使当前工具源码fingerprint变化，不用于覆盖旧build manifest或重新证明历史运行。有限数据见`knowledge-corpus-tools/evidence/vector-representation-full-policy-20260907.v1.json`，不保存原文或向量。此次无Java/PowerShell/Runtime源码变化，未重复其Maven/AST/全量Runtime，上一轮§20.44结果仍仅表示当时执行；本纯函数不能代替后续迁移的完整验证。

本切片表示设计/实施/non-live已完成；下一步在同一目标下落实738附件限定候选的构建合同、模型完整快照、全记录/旧向量保持及真实只读候选验证。不要求对已授权政策结构正常步骤重复授权，也不自动复用已消费模型批次。阶段B仍未完成：UAT=Deferred、QUALITY=Blocked，无新付费run或索引发布。

### 20.47 限定政策附件向量候选（2026-09-07，v2.55）

承接用户政策ES向量结构授权及L2_01_01 v2.11 DR-KRET-031，不扩大付费批次、索引删除或读取权限。起始HEAD=`1ee25343ecbfc2eecefa93421b9d1d40cb65c162`，工作树与origin/codex一致。实际ES9.4.1，源索引write-blocked，15521记录；已发表alias不动。现有原生clone可保留底层段与全部law/旧policy向量，避免_source重建的精度变化；旧StageA工具会因既有trace字段而拒绝重复导入，不修改其历史行为。

本增量归`WP-KRETRIEVAL-IMPLEMENT-01`的后续政策存储切片；主表Done仅表示§20.37～20.40在线切片，不包含本增量。`WP-KRETRIEVAL-QUALITY-01`仍Blocked，专项UAT仍Deferred。以本节单一进度表记录新动作，不重复新增Gate或把发布前置变成编码阻塞：

| 动作 | 直接前置及设计 | 状态 | 验证/失败边界 |
|---|---|---|---|
| 构建合同及评审 | KQ-AD-019、DR-KRET-031、当前源/模型事实 | Done | 三轮内审和分离编辑L2/跨层复评通过；只准入builder |
| builder及fake验证 | 上述合同评审 | Done | TEST-KRET-026/VAL-KRET-012；87新增fake及原工具回归通过，无真实写入 |
| 模型/token前置与真实候选 | builder/fake通过、源/模型精确绑定 | Done | b1失败保持不可变；§20.48修复后另名b2完成真实构建、全记录保持和同窗口对照，无alias |
| typed验证及受控发布 | 候选完整性、新policy/law快照与目录、授权/Evidence/回滚 | Done | DR-KRET-024/025/032；§20.50～20.52真实typed、隔离回滚和受控发布通过；现行alias指向b2，a5保留；不关闭完整专项UAT |

准备可并行读取模型hash，不能提前消费写入/模型请求。当前模型缓存revision和refs/main相同；模型文件最后修改早于既有容器启动。pytorch_model.bin SHA-256=`b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`（2271145830字节）；tokenizer.json=`21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08`；sentencepiece=`cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865`。这些只读事实补齐上一轮模型权重hash缺口，正式构建仍须首尾核验全部模型/服务快照和每个输入token上限，不以health替代。

已提交设计`249fcd974e603f6c7d53b768afb14ff05d8ba263`后，新增`vector_candidate.py`及`test_vector_candidate.py`。不改旧`indexing.py`/`release.py`、Java/Runtime生产代码、冻结资产或索引。builder选择器与Java配置严格相同：字段为`channel`，不是猜测的`category`；只更新其中的attachment。HTTP origin/环境代理/redirect/超时、严格JSON/有限向量、完整scan/fingerprint、原生clone、候选只读初态、CAS批量partial update、最终逐条比对及失败封存均有反例。只读扫描真实源15521条，policy13909、attachment738；所有目标附件身份/ACL/原文hash及全库向量格式通过。盘点64次ES读取，候选写入/alias/embedding/付费均0；额外版本/定义/计数/元数据类型检查4次只读，正文/向量未落盘。

源绑定：UUID=`SurWRSglRd6ZRddEBWy2Sw`；mapping SHA=`7b83f96b013c6f6cfa671f13488d45101d2273a048eac88cc764fcf218fb3cdf`；全记录fingerprint=`fac81f8f0fc73b23b0b7719c846662faf35e20b7dc3a6a70379abad917e1e418`。本fingerprint按DR-KRET-031全字段+float32算法，不与§20.46较窄字段对照hash混用；真实构建仍重新核对，不以盘点时事实假定源永不变化。

代码对照评审共4轮（同一执行者分阶段，不冒充外部人员）：首轮发现bulk回执未绑定文档ID、候选初始设置检查及取消清理诊断不足，完成最小修复；第二轮发现HTTP环境代理可继承及边界反例不足，强制trust_env=false并补齐大小/流超时/重复JSON/预算/篡改测试，澄清分阶段timeout；第三轮暂存复核发现callback可通过自定义异常reason带出任意文本，以及数字1可误当write-block true，收敛全部错误码并严格区分类型；第四轮只读复核代码、87个反例/成功例及全量工具结果，builder切片Blocker=0、Major=0、未处理Minor=0。真实驱动/model/token/ANN/typed/发布均不包含在本次通过结论内。

实际命令与结果：

| 命令/环境 | 本次结果 |
|---|---|
| 既有corpus隔离Python，工具目录`-m pytest` | 165 passed（1.84秒）：87新builder、48表示、30原工具 |
| 同环境`-m mypy --strict src` | 15源文件通过 |
| 同环境`-m compileall -q src tests` | 通过 |
| C:\Python312\python.exe，进程移除Key、PYTHONPATH=当前src，`-m pytest tests/system_e2e/test_knowledge_stage_b_run_08_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q --tb=short` | 18 passed（12.77秒），1条既有LangChain预告；七项冻结hash及35/37追踪，不冒充重跑真实UAT |

环境失败如实记录：工具目录直接`-m mypy`因包级查找缺py.typed未执行类型检查，改为README既有源码入口`--strict src`后通过；初用agent-runtime/.venv运行追踪因该服务环境没有pytest而未执行测试，改用既有C:\Python312及进程PYTHONPATH后通过，无安装或全局配置变动。新代码首次类型检查发现7处Optional控制流注解问题，通过NoReturn及已有运行时校验表达修复，不弱化类型或测试。

本轮不重复无变更的Java/Maven、PowerShell AST、全量Runtime或Spring E2E；新模块没有在线调用方，待真实索引接线/发布前执行相应完整验证。当前source/alias、StageA和run-08历史均未变；不创建run-09、不读取Key、不重用付费授权。阶段B整体仍未完成，下一步直接完成已授权模型/token准备及无alias候选构建，再按证据推进typed检索和发布。

### 20.48 本地模型接缝及首次候选集成（2026-09-07，v2.56）

起始HEAD=`f81d4683ec9da669dbc1a23cd3fc10365fcd4411`。新增离线`local_vector_preparation.py`、版本化`run-policy-vector-candidate.py`、两份直接测试及源绑定文件，提交`bf87a86`并推送codex。模型在既有Docker环境核对11份权重/Tokenizer/配置文件、服务源码、实际Encoder实现、库版本、唯一cache revision与启动身份；不得导入另一份embedding模型或继承Key。真实preflight发现refs/main在模型加载时刷新时间，修正为“唯一snapshot目录和实际模型文件在启动前已存在且首尾hash不变”，不把mutable ref mtime当作加载身份。fake测试覆盖token超限、首尾模型漂移、非法向量、超时、无重试和有限错误，runner验证exclusive binding/result及禁止重入。

实际命令：工具隔离Python `-m pytest -o addopts='' tests -q --tb=short`，199 passed（2.24秒）；`-m mypy --strict src scripts/run-policy-vector-candidate.py`，17文件通过；`-m compileall -q src tests scripts`通过。首次新增测试误把POST _search当作写入，改为明确允许只读POST _search但拒绝clone/mapping/update路径，未放宽零写入语义。正式代码对照复核两轮关闭模型身份时序误判及runner/真实builder接缝覆盖问题，本地准备切片通过；不声称其fake证明真实ES兼容。

源绑定见`knowledge-corpus-tools/evidence/policy-vector-source-binding-20260907.v1.json`。真实b1入口为`scripts/run-policy-vector-candidate.py --source-binding evidence/policy-vector-source-binding-20260907.v1.json --container <binding.json中的完整容器ID> --output-directory evidence/policy-vector-candidate-20260907-b1 --execute`，不可再次执行。模型snapshot SHA=`bb701284a410cc88e80816bea0f40c0420fd501ed30f879cd290802c5835b4ec`；738文本无截断（最大244 tokens），24次本地BGE HTTP、738文本；ES HTTP72，其中clone已发生，但尚未解除候选写保护、添加字段或更新向量。外部模型/付费/Business/retry/resume/alias写入均0。

b1终态为`failed / clone / schema_invalid / candidate_seal_failed`，result SHA=`62566e2973ffbac96340f2f14e4559fc6a06010929b66eebdc0c77a635c27496`。不改写该结果。补充65次只读核查证明新UUID=`bQPe6P2fR-SEBbpqH4-2wg`、write-block=true、alias为空；全15521记录fingerprint和mapping均与源相同。`post-failure-check.json`仅证明停止后实际只读状态，不冒称原自动封存成功。源alias仍精确指向a5，旧索引未改动；b1保留，不删除、不补跑。此前健康/容量检查3次ES读取、故障定义/恢复/alias检查3次读取，均无额外写入。

根因`B-CLONE-001`：ES9.4.1官方`ResizeSourceIndexSettingsUpdater`在所有主分片启动后删除临时resize source设置；旧L2/fixture错误假定该字段永久存在。不是数据、权限、向量或业务接口缺口。最小修复只改L2_01_01 v2.12 DR-KRET-031的clone归属合同及builder/fake；不加永久marker、锁服务、Gate或修改公共DTO。先冻结发现，再完成三轮内审及分离编辑的L2/跨层复评，设计问题已关闭；允许最小实现修复，source/ACL/全记录比较与无alias边界不变。同一执行者分阶段，不冒充外部独立人员。

后续实施已完成clone确认回执/UUID与临时来源消失兼容，提交`399a592e50d7f5c6a01a7ba56bdcbcf6fc9e9743`；源码修复、14个新增fake和当时全工具213例通过后，使用新源绑定v2另名构建b2，没有恢复b1。归属不明且无来源/UUID证据时不做清理写入，原文/ACL/非目标向量与源别名保护保持。新存储候选不是新付费模型run；不创建run-09、不读取Key、不扩大模型预算。

#### 20.48.1 新候选完整构建与同窗口检索结果

真实执行以`399a592`为构建HEAD，绑定、result、ANN对照均保存在`knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/`，字节不可覆盖：

| 资产/事实 | 当前结果 |
|---|---|
| 候选 | `agent-doc-tax-policy-v5-20260907-vector-b2`；UUID=`jJ5Ww3LCRWWycfDkUZvmdw`；`built_read_only_unpublished` |
| binding SHA-256 | `26d9644b3c2b30511249b79c09399557ced6dfb6f11d526829e43c6e2296ee3f` |
| result SHA-256 | `71f08b8be07738ce2925b2931387ff9e5ec1c1b3840b7fbb6a0273a0664de518` |
| ANN comparison SHA-256 | `003929b26104b0d1b9724d0bd7666f4854fd44923a0df290ef35a46c10fb5eff` |
| 全记录保持 | 15521条；policy13909；仅更新738个policy附件向量及4项表示元数据；所有原文/引用/ACL不变，law及其余基线向量float32字节相同 |
| 候选 fingerprint | `fb285fc5e5e838fbccb2025f24c0f4472802b8beb7190247cefc9a2978b9a17d`；源fingerprint仍为§20.47绑定值 |
| 构建实耗 | ES HTTP228；本地BGE HTTP24/738文本；max tokens244；96.36秒；付费/retry/resume/alias写入0 |
| 检索对照实耗 | ES读取HTTP24、本地BGE HTTP1/5文本；max tokens26；付费/写入/retry0；同一模型、固定五题与gold，窗口20、k21、num_candidates100 |

| 问题类型/必要片段 | 原索引 keyword / vector | b2 keyword / vector |
|---|---|---|
| 住宿服务生活服务：lodging/living | 5,2 / 2,5 | 5,2 / 1,2 |
| 住宿如何定义：lodging/living | 窗外,2 / 6,窗外 | 窗外,2 / 1,3 |
| 住宿与不动产租赁：lodging/rent | 均窗外 / 均窗外 | 均窗外 / 4,6 |
| 2016一般计税住宿税率：lodging/historical_rate | 2,窗外 / 均窗外 | 2,窗外 / 窗外,18 |
| 软件即征即退材料：software | 1 / 2 | 1 / 2 |

五题所需原文均进入候选的keyword/vector合并池。尤其历史税率问题虽向量路径的住宿定义仍在窗外，keyword第2名已提供它，vector第18名提供税率；不得继续把单路排名33解读为整个候选池仍缺定义。该事实只关闭“这五题的同窗口候选池缺证据”诊断，尚不证明quality-v3会保留全部必要片段、typed授权、Evidence、摘要或完整UAT通过。未改变topK、gold、原文、算法、现行服务或alias。

本地准备、克隆修复及对照工具按DR-KRET-030/031完成分阶段代码复核。对照工具首轮发现Python优化模式会移除断言，增加`-O`启动即拒绝并补测试；复评确认gold仅用于检索后排名、固定服务窗口、严格绑定/有限输出、无写入/模型Key及禁止覆盖。新证据hash和证明范围加入直接测试；本切片Blocker/Major=0，未处理Minor=0，由同一执行者分离编辑复核，不冒充外部独立人员。

本次最终工具命令：既有corpus隔离Python在工具目录执行`-m pytest -o addopts='' tests -q --tb=short`，216 passed（4.51秒）；`-m mypy --strict src scripts/run-policy-vector-candidate.py scripts/compare-policy-vector-candidate.py`，18文件通过；`-m compileall -q src tests scripts`通过。Runtime run-08历史与两份追踪定向入口最终18 passed（12.25秒，1条既有LangChain预告），原35/37功能追踪和七项run-08 hash保持。未重跑无源码变化的Java/Maven、Spring E2E、PowerShell或全量Runtime，不将此前结果复制为本轮通过。

本节从本地准备到当前对照合计ES HTTP395（含两次clone及b2限定写入）、本地BGE HTTP49/1481文本；源/alias写入、外部付费模型、Business、服务启停均0。b1保留只读且失败结果不改写；b2保留只读未发布。精确索引、目录/Profile快照、typed授权/Evidence、回滚和发布仍是下一直接步骤；当前Java启动校验确实要求真实alias/UUID/mapping/snapshot，不以绕过Verifier完成验证。QUALITY仍Blocked，专项UAT仍Deferred，阶段B整体保持未完成。

候选有限证据、同窗口工具及其测试原子提交=`294e70eb715c40e5715c99ddf1cb9f43851c711a`；暂存逐文件/完整diff及敏感模式扫描通过（0命中）。状态同步不修改设计语义、任务或UAT完成定义，不为测试计数变化再次升级版本。L2/P3严格校验0 errors/0 warnings；在线Runtime、Java服务和原历史资产相对本节起点无文件差异。

### 20.49 候选目录与Profile离线准备（2026-09-07）

沿既有L2_01_01 DR-KRET-024实施，不改变设计语义、公开合同或版本，不新增Gate。起始HEAD=`4489f47156c6060cd583ade41c9637c18767ddcc`，工作树干净。`catalog_preparation.py`只扩展同一文档、同一policy的所属域新快照；`prepare-policy-vector-publication.py`只读核验b2并生成pending文件，不改变生产resource、serviceCenter启动binding或alias。

真实准备命令（工具目录、既有corpus隔离Python）：`python scripts/prepare-policy-vector-publication.py --candidate-directory D:\codex\knowledge-corpus-tools\evidence\policy-vector-candidate-20260907-b2 --output-directory D:\codex-data\knowledge-policy-vector\publication-preparation-20260907-b2`。输出路径已存在时禁止覆盖或重入。输入精确绑定b2构建result和binding、当前旧catalog；核对候选UUID、完整mapping及分片/分析器设置、write-block、无alias、全部15521条的fingerprint及成员关系，首尾源与候选定义相同。本次ES只读HTTP67，embedding/付费/ES写入/alias写入/服务启停均0；未读取Key。

| 准备/校验结果 | 事实与有限证据 |
|---|---|
| pending目录 | 上述本地受控目录；仅保存文档标识/策略/快照元数据，无正文、向量、JWT或模型响应；不直接作为生效配置 |
| 新catalog SHA-256 | `87c3963a15ea98cca444438c3439094b6881bba31ceaef265db92f5caab21b00`，2581948字节；旧catalog/hash/loader不变 |
| pending binding SHA-256 | `a6d2c00eddf46827750a8100357c909bab944f27d10b41218e2c9754457f9682`；新policy/law快照按Java既有五段输入公式计算 |
| 新policy snapshot | `8bb0918b1a8e6edd9bc2b88b23bb99571810b1423796b27ed3287e92a82d6025`；5463份实际policy文档 |
| 新law snapshot | `522d4da243e338196143a92bf7e57ed6dffa063c9abd009892e2a5ed8fa8a7a3`；137份实际law文档；其1612条记录的向量/正文未改，物理UUID变化仍须新快照 |
| Runtime真实校验 | 使用当前`catalog.py`的`_parse_snapshot`、`KnowledgeEgressPolicyCatalog`及`resolve`，5600个新绑定、22396个原有绑定全部解析；5600次未知快照均拒绝；全部policy/字段上限相同，当前resource再次加载仍不变 |
| 有限evidence | `knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/`；`preparation.json` SHA=`cfce562ee4f5e69e75c511450a9598ce9cda9c721a3f07b1b117df2754c3c7d3`，`runtime-catalog-check.json` SHA=`0fd0fd58904298c8181bc87d9e398a7b5d303020e91fc191d6b393bc9258cebd` |

原preparation中的`runtime_loader_validation_pending`是生成时事实，后续校验由独立有限结果补充，不覆盖原文件。Runtime校验为本地实际validator调用，网络0；不是Java typed检索、授权链、Evidence或UAT证明。没有将2.58MB pending目录复制进当前生产resource或Git，版本化工具、来源hash和有限证据足以追溯本准备步骤。

代码对照DR-KRET-024/031分两轮复核：首轮`B-PREP-001`发现仅校验mapping版本不能发现同版本结构漂移，改为完整mapping/原字段/四trace字段及关键settings比较；`B-PREP-002`将本地文件读取收紧为4MiB+1预读，避免先加载任意大文件。补齐错误结构、目录成员/快照、重复输出、非法写入、80次HTTP上限和`-O`禁止测试。第二轮复核固定源、只读HTTP、旧policy与绑定保持、同域快照、无生产接线、有限日志与结果；本离线切片Blocker/Major=0，未处理Minor=0。同一执行者分离编辑复核，不冒充外部独立人员。设计未发生语义变化，不重复三轮设计内审或新增批准门。

实际验证：工具目录`python -m pytest -o addopts='' -q --tb=short`最终259 passed（2.98秒）；`python -m mypy --strict src scripts/prepare-policy-vector-publication.py scripts/run-policy-vector-candidate.py scripts/compare-policy-vector-candidate.py`20文件通过；`python -m compileall -q src tests scripts`通过。新增43项测试，其中首次超大参数测试因pytest自动生成过长用例ID造成2个setup error，改为有限ID后通过，没有放宽输入或断言。Runtime以C:\Python312及进程PYTHONPATH执行policy catalog、egress manifest、run-08 history、Business/Knowledge两份traceability，共31 passed（14.03秒，1条既有LangChain预告）。原35/37功能追踪和冻结run-08 hash保持。Java/Runtime生产代码、公开DTO、配置及历史资产未改，本轮没有重跑Maven、Spring E2E或全量Runtime，不能把此前结果算作本轮通过。

工具/测试/有限证据提交=`bba85df38123776d1232f06e7ff2d028ca089732`。当前完成的是候选发布**准备**，不是发布：下一步仍须让真实Java Profile校验、typed keyword/vector、读取拒绝、出域/Evidence验证和精确alias回滚顺序可执行；不得通过绕过Verifier或提前替换现行alias取得通过。QUALITY=Blocked、专项UAT=Deferred不变，run-08保持失败终态，无run-09或新的付费授权消费。

### 20.50 隔离真实typed验证与发布前防回退（2026-09-08）

起始HEAD=`9cccc897b788956817efac906b0cb9862b7ac255`。复核发现`B-ALIAS-001`：原发布条件要求先typed验证，真实Java启动又要求alias已经存在；如果把隔离测试alias也算线上发布，会形成循环。按个人验证项目背景，L2_01_01 v2.13 DR-KRET-032只新增随机临时alias，不加新服务、Gate或第二在线流程。三轮内审分别核对链路/职责、归属/不明写入/清理、预算/依赖/验收边界；冻结编辑后的L2及跨层复评通过，允许实现此切片，不批准线上发布。P3/UAT只同步状态和上位版本，未为测试数量变化升级版本。

新增离线`validation_alias.py`及`validate-policy-vector-typed-v1.py`，固定loopback、source/candidate UUID、write-block、线上alias空flags基线和pending binding/catalog hash。临时alias独占随机名称、`is_write_index=false`，创建/切换/删除前检查归属；不明响应不重试，冲突时不覆盖他人修改。该流程是单操作人窗口，不冒称多HTTP请求具有分布式CAS。真实ADMIN由隔离auth签发，VIEWER/UNKNOWN/service-token使用同一随机HMAC内存签发；Java原ProfileVerifier、Python原strict decoder及授权均不修改。

实际入口脚本为`python scripts/validate-policy-vector-typed-v1.py --execute --result D:\codex-data\knowledge-policy-vector\publication-preparation-20260907-b2\typed-validation-20260908-04.json`。该已存在结果不可覆盖或重入。环境勘误：此前写为“corpus隔离Python”不足以复现，§20.51确认它缺少Runtime所需FastAPI；可复现环境必须使用C:\Python312及进程PYTHONPATH，不从原有限结果推断未记录的解释器身份。以下四次非付费集成各有独立有限终态；失败后先按证据修复并通过fake再另次验证，未恢复旧执行：

| 执行 | 终态及原因 | typed / embedding / ES管理读取 / 临时alias写入 | 原始结果SHA-256 |
|---|---|---|---|
| 01 | Failed；预检误要求现行alias带false标记，实际冻结StageA flags为`{}`；修复工具基线检查，未修改旧alias | 0 / 0 / 3 / 0 | `ecf611dbcdbcd73d370ea009da3b477db590a4c23f424b99795c6d97ba3120aa` |
| 02 | Failed；ES9.4.1回执包含`errors=false`，旧fake误要求仅acknowledged；创建/清理实际完成，随后只读确认无残留；核对官方源码并修复精确响应合同 | 0 / 0 / 8 / 2 | `26cf361e3aa5ec2eade3ab1fdeeef8dd0574c3ecbe87c1d397a4bacc7b4f1085` |
| 03 | Failed；PATH选择Java8导致服务退出；改为预检JAVA_HOME的Java25，不改全局环境。owned PID停止、日志扫描删除、临时alias移除 | 0 / 0 / 13 / 2 | `e1af256d29ef7874cf8191a1a6a1cfdf455526f4882ea6923a6438af72d9f764` |
| 04 | Passed；真实typed及权限16组合、严格解码/正文hash/目录/Evidence引用兼容通过，owned进程及日志清理通过 | 16 / 2 / 13 / 2 | `c1e7b29ee099bcbbfeb4e640e70e70844003b6de555b73ec85d140c21ff25c95` |

四项文件位于`knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/typed-validation-20260908-01.json`至`04.json`，保留源文件CRLF字节。`.gitattributes`仅对此四文件加binary，避免仓库默认LF转换破坏已记录hash；四项历史测试固定校验原SHA、失败/成功、零模型/线上写入及证明限制，不改任何旧evidence。本表管理读取只计runner请求，额外手工只读alias/settings诊断不混入runner精确计数。

04覆盖policy/law各自ADMIN/VIEWER的keyword/vector，8个允许路径各严格校验20候选（160次候选校验，不是160份唯一文档）；各域UNKNOWN=403、service/malformed/missing=401，共8个拒绝且零正文。使用当前Adapter和Evidence完整性/策略/连续子串/唯一性validator，未知snapshot与重复引用拒绝；选证使用既有v1兼容限制和合成原文引用，不执行quality-v3需求重排、Summary或Spring真实模型链。此结果不能证明原十个阶段B case通过。

成功实测launcher SHA=`54ec6f9a95f187c48a5dcd512373fea185358a2cef477e2fd118f11a413c191d`；当时alias模块SHA=`0a641c1ec0aabdf6d16a172838be825b9fe910ffb02e8c24a4f0d37d4a1abf56`。后续代码评审收紧Python数值0/1与bool相等导致的回执/flags误接受，增加8个反例；最终模块SHA=`b15c8bda5d935b675eec41269ee9613ac603133be66754d8d84258df5b313ad2`。实测响应本来就是bool，新收紧以fake验证，不额外重跑真实请求或声称原实测覆盖最终源码hash。

正式代码对照复核分两轮：首轮关闭上述bool类型问题、清理预算预留及证据CRLF入库问题；第二轮按DR-KRET-024/025/032核对精确归属、读取授权、响应限额、拒绝零正文、client/PID/finally、敏感扫描、旧配置不变和测试结果。本工具/launcher切片Blocker=0、Major=0、未处理Minor=0；由同一执行者分离编辑复核，不冒充外部人员，阶段B原在线语义/效果问题不在本切片关闭范围。

| 本次实际验证入口 | 结果与边界 |
|---|---|
| corpus既有隔离Python，工具目录`-m pytest` | 最终291 passed（2.96秒），含28个alias fake、4个不可变结果测试；无模型或服务启动 |
| 同环境`-m mypy --strict src`、`-m compileall -q src scripts` | 18源文件strict通过，compileall通过；bare mypy曾因包查找缺py.typed失败，明确源码入口后通过 |
| Runtime目录C:\Python312，当前进程PYTHONPATH及移除Key，`-m pytest tests/system_e2e/test_policy_vector_typed_validation.py -q --tb=short` | 14 passed，真实Java形状的fake经实际Adapter/Evidence/拒绝检查；不是外部实测 |
| Runtime `scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe` | 临时隔离安装当前源码：冻结host/preflight14 passed；全量2766 passed/27 opt-in skipped/0 failed（289.21秒），1条既有LangChain预告；临时环境已清理 |
| Runtime `-m mypy --strict src`、`-m compileall -q src tests/system_e2e/test_policy_vector_typed_validation.py` | 134源文件strict通过，compileall通过 |
| es-query-service `..\serviceCenter\mvnw.cmd '-Dtest=Knowledge*Test' '-Deureka.client.enabled=false' test` | 29 tests/0 failures/0 errors/0 skips，BUILD SUCCESS；DTO/security/endpoint/Profile不改 |
| agent-service `..\serviceCenter\mvnw.cmd '-Dagent.runtime.python=C:\Python312\python.exe' '-Deureka.client.enabled=false' test` | 40 tests/0 failures/0 errors/1历史opt-in skip，BUILD SUCCESS（28.048秒）；Access/Business/Knowledge E2E实际执行；进程PYTHONPATH=当前Runtime/src、provider=stub、Knowledge=false、移除Key |

首轮Spring命令遗漏PYTHONPATH，40项中Access liveness 1失败；所选Python直接探测无法导入Runtime，且Access测试不主动设置源码路径。恢复既有§20.42命令的进程环境后全通过，不改生产代码、断言或全局安装；其余Java模块无变更，未在本切片重复Maven，不把历史结果算作本次执行。

新结果合计typed16、本地embedding2、rerank/外部模型/Business/retry/resume/线上alias写入均0；临时alias写入合计6、runner管理读取37。当前source/线上alias、旧catalog resource、serviceCenter binding、所有冻结run文件均不变，临时alias为空，04 owned PID3068/30692已退出，原始日志已扫描删除。下一直接步骤是隔离alias候选→旧目标→候选的真实Profile重启/回滚演练，再评估受控发布；不能把fake演练当真实演练。QUALITY=Blocked、专项UAT=Deferred，run-08失败保持，无run-09、不读取Key，目标仍未全部完成。

### 20.51 真实回滚演练及安装态修复（2026-09-08）

沿DR-KRET-024/025/032实施，不增加设计语义、门禁或版本。起始HEAD=`3bab4f7a54d8d3f3632605e821b83d135eed70f6`；回滚launcher提交=`5404b9e93d08db7722f144696831ce8142937821`。`rehearse-policy-vector-rollback-v1.py`绑定既有typed helper、alias模块、Java可执行资产及新旧索引；在一个临时alias上执行候选→a5→候选，每段先停止本次服务，再切换alias、用对应Profile重新启动真实auth/es-query。Popen对象/PID核验、日志扫描删除和alias归属检查不可跳过。

两次有限结果位于`knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/`，保留原始字节：

| 结果文件 | 终态 | typed / 本地embedding / 管理读取 / 临时alias写入 | SHA-256 |
|---|---|---|---|
| rollback-rehearsal-20260908-01.jsonl | Failed；corpus Python缺少FastAPI，实际Java启动成功但Runtime导入失败；停止并清理，无typed/model调用 | 0 / 0 / 13 / 2 | `6841870de283ce5fbd667c56c8258aa3996a5c8dad86d690973a16a301dab109` |
| rollback-rehearsal-20260908-02.jsonl | Passed；3段各8项真实typed/拒绝检查通过，原alias始终指向a5，最终临时alias为空 | 24 / 6 / 23 / 4 | `76b8456e510bb2228bfafbabf75f31251d982541719191ab5630b8ea554f227b` |

先以无网络Runtime导入复现`ModuleNotFoundError: fastapi`，改用既有C:\Python312，不安装全局依赖、不改旧结果或重入01。02执行环境：移除进程Key，`PYTHONPATH=D:\codex\agent-runtime\src;D:\codex\knowledge-corpus-tools\src`、`JAVA_HOME=C:\Program Files\Java\jdk-25.0.2`；命令`C:\Python312\python.exe scripts/rehearse-policy-vector-rollback-v1.py --execute --result D:\codex-data\knowledge-policy-vector\publication-preparation-20260907-b2\rollback-rehearsal-20260908-02.jsonl`，工作目录knowledge-corpus-tools。已消费结果禁止再次执行。两个回滚结果共24typed、6embedding、0外部模型；各段进程退出/日志清理通过，不是付费候选或在线发布。

目录与启动接线随后增加`egress-policy-catalog-v3.json`、`knowledge-runtime-binding.v2.json`；旧v1/v2目录、旧binding及历史资产不变。v3保留5600文档、全部原策略和22396旧快照成员，只添加所属域的5463 policy/137 law新绑定；默认loader转v3，保留显式`load_v2_resource()`。serviceCenter启用Knowledge时默认选binding v2，显式路径和环境覆盖优先级不变；disabled不加载Knowledge。新目录/绑定hash仍为§20.49准备值。

安装态首次全回归出现181 failed/2602 passed/27 skipped；源码目录定向测试通过不等于wheel可用。根因`B-PACK-001`：pyproject.package-data只包含旧目录，安装后的v3文件缺失。补齐唯一资源声明、增加打包清单断言后，隔离安装全量通过；未改validator或测试预期以掩盖错误。

分阶段代码对照复核：回滚工具首轮关闭prepare输出失败时未用client释放、可执行文件首尾hash漂移问题，15个fake通过后复评；发布/接线首轮补齐完整mapping/settings及全记录fingerprint检查，冻结旧任务/结果、新同域绑定、误回执和不明写入的精确回滚；最终读取代码、diff和测试复评，本存储发布切片Blocker/Major=0。由同一执行者分离编辑复核，不冒充外部独立人员；未发生设计语义变化，不重复三轮架构内审。

### 20.52 政策向量b2受控发布（2026-09-08）

发布代码/目录/测试提交=`81dac4e706817022803d3abb77a60ee41fb43366`，工作树干净后执行一次`publish-policy-vector-v1.py --execute --result D:\codex-data\knowledge-policy-vector\publication-preparation-20260907-b2\publication-20260908-01.jsonl`；解释器及进程环境同§20.51。绑定真实回滚02证据、Java原可执行资产、新旧目录/UUID和同一源/候选fingerprint，不读取Key，不执行模型或Business。

| 发布事实 | 结果 |
|---|---|
| 前置完整性 | 源、候选各15521条全字段/float32向量fingerprint再次等于冻结值；完整mapping只差批准的4个trace字段和版本；均write-blocked；候选无alias |
| 原子切换 | `agent-doc-tax-policy-v2-read`：a5→`agent-doc-tax-policy-v5-20260907-vector-b2`；1次`_aliases`精确remove/add；a5不删除、不改正文/向量 |
| 新索引身份 | UUID=`jJ5Ww3LCRWWycfDkUZvmdw`；mapping=`agent-knowledge-tax-v3-policy-context-v1`；新policy/law快照及目录见§20.49 |
| 发布冒烟 | 16/16；policy/law×ADMIN/VIEWER×keyword/vector允许，UNKNOWN403、service/malformed/missing401；strict decoder、正文hash、目录、Evidence子串/唯一性通过 |
| 实耗 | 完整性只读HTTP130、管理GET10、线上alias写入1；typed16、本地embedding2；model/Business/rerank/retry/resume=0 |
| 清理 | owned PID31552/10852退出，原始日志扫描删除，未停止其他用户进程；临时alias为空 |
| 有限证据 | `knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/publication-20260908-01.jsonl`；SHA=`e716addba9d02979bc5104a6a1df1ead83b84bd6a0a9968686351e644b1917d0` |
| 实测launcher hash | `8c675be23fa8867d54f9f97b2cc578c6ca3b14f225f123e519a49b0f7a0ebfb2`，从上述提交读取原源码校验，不假定后续代码hash等于实测版本 |

切换后用实际发布alias和新Profile启动真实服务，而非只验证临时alias。默认启动binding v2与Runtime v3同步；本机实际`agent-runtime/.venv`也已用`python -m pip install --disable-pip-version-check --no-deps .`安装当前包，并以`-I`隔离导入确认v3、精确hash和5600绑定。没有新增生产依赖或全局安装。其他工作副本的`-SkipBuild`不负责更新旧安装；旧进程不会热更新，本次未为演示额外启动整套服务。回滚路径明确保留a5及binding v1；发生失败时工具先按UUID/alias精确前置恢复a5，操作者使用`-KnowledgeBindingPath D:\codex\serviceCenter\knowledge-runtime-binding.v1.json`启动；v3目录保留旧成员，无需删除或改旧目录。真实隔离回滚通过，实际发布成功故未额外往返线上alias制造无价值写入。

发布后代码复核`B-PUB-002`发现停机窗口检查漏了默认Runtime 8091（已有8090/8092/9201及隔离端口检查）；最小补入8091并增加占用拒绝fake。运行后只读检查确认这些端口实际均无服务，未发生旧Runtime读取新索引。原实测代码和结果由冻结commit/hash保持，不改写为新检查已在原实测执行；该收紧没有重跑发布或模型。

| 本次验证命令 | 结果 |
|---|---|
| Runtime `scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe`（隔离安装，移除Key，PYTEST_ADDOPTS=--tb=short） | 资源修复后首次全量2784 passed；补齐发布30例及最终修复后重新执行：host14 passed、全量2814 passed/27 opt-in skipped/0 failed（278.03秒），1条既有LangChain预告；临时测试环境清理完成 |
| Runtime `-m pytest tests/system_e2e/test_policy_vector_publication.py tests/system_e2e/test_policy_vector_rollback_rehearsal.py tests/unit/knowledge/evidence/test_policy_catalog.py -q --tb=short` | 最终59 passed（4.11秒）：30发布、15回滚、14目录；全部为fake或不可变证据校验，不冒充额外真实验证 |
| Runtime `-m mypy --strict src` / `-m compileall -q src tests/system_e2e/test_policy_vector_publication.py ../knowledge-corpus-tools/scripts/publish-policy-vector-v1.py` | 134源文件strict通过；compileall通过 |
| corpus隔离Python，工具目录`-m pytest -q --tb=short`、`-m mypy --strict src`、`-m compileall -q src scripts` | 291通过、18源文件strict通过、compileall通过 |
| agent-service Maven `'-Dagent.runtime.python=C:\Python312\python.exe' '-Deureka.client.enabled=false' test`（当前PYTHONPATH、stub、Knowledge=false、移除Key） | 40 tests，0 failures/errors，1历史opt-in skip；BUILD SUCCESS（27.853秒）；当前Spring→Runtime Access/Business/Knowledge非live链路执行 |
| es-query-service Maven `'-Dtest=Knowledge*Test' '-Deureka.client.enabled=false' test` | 29 tests，0 failures/errors/skips，BUILD SUCCESS（5.480秒） |
| PowerShell Parser.ParseFile(serviceCenter/run-all-services.ps1)、暂存敏感扫描、git diff --check | AST0错误、凭据/JWT模式0命中、diff通过；目录全部绑定另由严格测试逐项检查 |

当前只关闭§20.47存储切片：表示、构建、目录、typed、回滚及发布均已完成。`WP-KRETRIEVAL-QUALITY-01=Blocked`、专项UAT=Deferred仍保持；Rewrite8/Summary6/quality-v3在新索引上的原十例完整问答、澄清零检索和必要证据/usefulness未通过本次发布测试。run-08仍失败且不可恢复，未创建run-09、未读取Key、未自动追加付费验证；下一步先在当前新快照核实必要证据经真实融合/rerank/quality-v3是否保留，再决定完整受控UAT，不把存储改善当作整体目标已完成。

发布有限证据及8091防护提交=`b35c0907b3c2be498870ecf5633e748ba55918d5`。最终代码对照复评核对30发布例、15回滚例、14目录例和2814全回归、真实索引/alias、来源hash及旧资产Git差异；本存储发布切片无未处理Blocker/Major/Minor，不外推整体阶段B通过。文档只作实施状态和命令勘误：L1_01保持v1.21、L2_01_01保持v2.13、P3保持v2.56、UAT_01保持v1.32；无新的设计合同，无需为动态计数升级版本。L1/L2/P3严格校验均0 errors/0 warnings，三份修改文档32个本地链接全部存在；原35/37追踪和run-08/旧candidate哈希由全回归校验通过。

### 20.53 当前quality-v3诊断与本地重排冷启动（2026-09-08）

从`d06160b55077abf951e6a34e724f5645dece4545`继续；向量发布已完成，不能继续用旧quality-v1 typed兼容检查或合成分数重放声称新排序/Evidence通过。新测试入口`knowledge_stage_b_quality_v3_probe.py`冻结八个手工检索计划，调用真实当前Stage/RRF/ranker/Selector/策略；gold只在排序及选证后评估，001/005澄清和真实Rewrite/Summary不在本诊断证明范围。上限search/embedding/rerank=22/11/18，模型/Business/索引写入/retry/resume0。

唯一真实诊断源提交=`88900bfa660074334ec5429ab2afff26d165f81d`；使用C:\Python312、当前Runtime及corpus/src进程PYTHONPATH、Java25，未读取Key。执行`python -m tests.system_e2e.knowledge_stage_b_quality_v3_probe --execute --result D:\codex-data\knowledge-policy-vector\publication-preparation-20260907-b2\quality-v3-probe-20260908-01.jsonl`。原始字节复制到`knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-probe-20260908-01.jsonl`，SHA=`7387ba9450d46529c48434592d09a2b846cfb4c5532b922ec2a6b25512c378b6`，不可覆盖/重入。

| 诊断事实 | 有限结果 |
|---|---|
| 首例UAT-KB-015a | keyword20、vector20，RRF去重35；首次BGE rerank触发现行5秒timeout，`rerank_timeout`，未产生最终排序或Evidence |
| 终态 | Failed；其余七个手工计划未执行；不补跑，不计为UAT通过 |
| 实耗 | search2、embedding1、rerank1；ES管理预检读取3；外部模型/Business/索引与alias写入/retry/resume0 |
| 环境/清理 | 当前b2精确binding/catalog及Java ProfileVerifier通过；随机HMAC/真实auth内存ADMIN，owned进程停止、原始日志扫描删除通过 |

`B-READY-001`根因复核：当前BGE镜像GPU CUDA可用、FP16、batch16/max_length512；仅health可达不证明推理就绪。一次现有实例合成35×4096字符、实际strict Adapter校验耗时1421ms。随后同镜像创建只读模型缓存、network=none、4GiB上限的临时容器，health正常后第一次相同合成评分7167ms，第二次801ms；启动health等待9018ms。该独立冷实例复现证明启动前置不足，不声称已获取原失败请求全部内部计时或排除所有并发因素。只停止并删除已核验ID/独占label的本次容器，现有BGE/ES未改。有限控制台结果归`knowledge_stage_b_local_model_probe.v2.json`，明确人工记录来源而非伪造运行器原始输出。本合成诊断本地rerank3、外部模型/检索/embedding0；未重放失败case。

方案比较：扩大在线timeout会改变用户deadline且掩盖冷启动；缩小候选池损害已证明的必要证据召回；因此采用独立启动期一次合成预热。L2_01_01 v2.14 DR-KRET-033已完成三轮内审及分离编辑的分层/跨层复评，无S0/S1/未处理S2，允许只改运维工具/启动接线及直接fake。在线5秒、stage20秒、排序、索引、权限和模型预算均不变；不新增Gate、不改变工作包DAG。P3/UAT只同步本地预检和当前状态，不因动态测试计数升级版本。

本节关闭的是设计中的“health等同推理就绪”假设，工具实际实施/验证结果随后追加。`WP-KRETRIEVAL-QUALITY-01=Blocked`、专项UAT=Deferred；run-08失败、原35/37功能追踪、旧P5及阶段A内容不变。新快照上的完整排序/Evidence、Rewrite8澄清与Summary6语义覆盖仍未完成；不读取Key、不创建run-09，不外推存储发布或合成预热为阶段B通过。

DR-KRET-033实施提交=`d8c407c29cdc98c1d570ed0be97d1cf730766592`，设计提交=`b6affb9`。`serviceCenter/warmup-knowledge-reranker.py`仅依赖已有httpx，30秒绝对startup deadline内单次发送40条合成文本，2MiB有界严格响应；serviceCenter只在Knowledge enabled、环境构建完成后、进程启动循环前调用。PlanOnly/disabled零调用；TCP跳过参数不跳过预热；独立CLI不接受endpoint/文本覆盖，不读Key。在线Runtime src、Java、公共DTO、5秒/20秒及索引均无改动。实际以`agent-runtime/.venv/Scripts/python.exe serviceCenter/warmup-knowledge-reranker.py`执行一次：40项严格通过、1515ms、clientClosed=true，本地rerank1；源SHA=`d37b016330b45b24c19c378a6e5ff29b22bc0b643e9b95996864e8bbe4b914d8`。它和前三次合成容量请求分别计账，本节合计search2/embedding1/rerank5、付费及索引写入0；没有再次执行原失败批次。

代码对照DR-KRET-029/033及三层策略分两轮复核：首轮补齐新诊断失败文件的原SHA/冻结源码校验，修正启动顺序测试误匹配`Assert-Plan`内部循环的测试定位；不改生产顺序或放宽断言。复评核对40项严格回显、bool/重复key/非有限数、超时/transport/超限关闭、只一次请求、fixed origin/no proxy、gold仅在真实排序后评估、PID/日志/历史保护。两项工具切片无未处理Blocker/Major/Minor；同一执行者分离编辑复核，不冒充外部评审，不外推完整阶段B通过。

| 本轮最终验证 | 实际结果/范围 |
|---|---|
| Runtime `scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe`；进程移除Key，PYTEST_ADDOPTS=--tb=short | 隔离安装；host/preflight14 passed（3.92秒）；全量2866 passed/27历史opt-in skipped/0 failed（390.02秒），1条既有LangChain预告；临时环境已清理 |
| Runtime `python -m pytest tests/system_e2e/test_knowledge_stage_b_quality_v3_probe.py tests/system_e2e/test_knowledge_reranker_warmup.py tests/unit/knowledge/retrieval/test_quality_ranking_v3.py tests/unit/knowledge/evidence/test_requirement_coverage.py tests/contract/knowledge/test_summary_task_v6.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q --tb=short` | 最终185 passed（1.30秒）；含全量采集后补入的失败文件hash/冻结源码反例追踪；原35/37追踪保持，不冒充真实UAT |
| `python -m mypy --strict src ../serviceCenter/warmup-knowledge-reranker.py`；`python -m compileall -q src tests ../serviceCenter/warmup-knowledge-reranker.py` | 135源文件strict通过；compileall通过 |
| PowerShell AST及`serviceCenter/run-all-services.ps1 -PlanOnly -EnableKnowledge -ModelProvider deepseek` | AST0错误；14服务有序计划，无服务启动/Key读取/模型调用 |
| L2/P3严格校验、有限证据敏感字段扫描、git diff --check | 0 errors/warnings；0敏感字段/凭据模式命中；diff通过。首次P3命令相对路径位于Runtime目录而报文件不存在，改为绝对路径后通过，不改validator |

本轮没有Java、业务合同或Runtime生产修改，未重复Maven及完整Spring Java E2E；不把§20.52的40/29项Java结果复制为本轮执行。本轮全量包括Knowledge/Core/Business、历史hash和追踪回归；它及合成检查都不证明八个真实手工计划的最终排序或Summary。b2 alias已只读再次确认不变，本次owned服务端口/诊断容器为空。后续先处理当前快照实际排序/Evidence证明，再评估受控完整UAT；已消费run-08和禁止自动run-09的边界不变。

### 20.54 预热修复后的当前排序实测与两项剩余缺口（2026-09-08）

从clean `4ba5d5ed6ee3fdc7b687af262e0df01545c93bd9`继续。按现有本地只读/BGE验证授权执行修复后的独立诊断，不续写§20.53失败文件，不恢复付费run-08，不创建run-09。先单列一次DR-KRET-033合成预热：40项、1296ms、clientClosed=true、rerank1；再以同一已提交手工计划工具/八个固定计划测量当前b2及quality-v3。原计划、gold、窗口、在线时限、排序、Selector、policy及任何生产源码均未修改；这不是新的付费批次或正式UAT。

实际命令（Runtime目录；移除进程Key，PYTHONPATH指向当前Runtime/corpus源码，JAVA_HOME为本机Java25）：`C:\Python312\python.exe -m tests.system_e2e.knowledge_stage_b_quality_v3_probe --execute --result D:\codex-data\knowledge-policy-vector\publication-preparation-20260907-b2\quality-v3-post-warmup-20260908-01.jsonl`。完整八例执行终态`measured`，实耗search22/embedding11/rerank18；加独立启动检查，本轮rerank19。外部模型、Business、索引/alias写入、retry/resume均0。真实auth/es-query owned PID28516/28340已停止，client关闭、原始日志扫描删除和前后精确索引/模型/源码绑定检查通过。

| 手工计划来源 | 必需原文进入实际policy允许Evidence的位置 | 该诊断结论 |
|---|---|---|
| UAT-KB-015a | lodging1、living5 | 原定义/分类来源保留 |
| UAT-KB-004 | lodging1、law_rate2、living7 | 原跨域分类/税率来源保留 |
| UAT-KB-002 | law_rate2、lodging4、law_effective6 | 原适用规则/定义/施行来源保留 |
| UAT-KB-003 | lodging1；rent缺失 | 未满足预定必要来源覆盖 |
| UAT-KB-006 | lodging3；historical_rate缺失 | 未满足预定必要来源覆盖 |
| UAT-KB-015b | law_rate2、law_effective6、lodging7 | 原多要点来源保留 |
| UAT-KB-016 | software1 | 保留回归来源保留 |
| UAT-KB-008 | law_rate1 | 指定法条来源保留 |

八例均完成真实Stage/RRF/需求重排/Selector/三层策略；六例保留全部预定原文。所有`selectionSufficient=true`仅证明结构及预算可用，不能抹掉两个语义来源缺口。001/005澄清没有执行；没有真实Rewrite或Summary、没有用户端引用/usefulness判定。不得以6/8或`measured`标记专项UAT Passed。

`B-RANK-CTX-001`根因定位：003的rent在vector第1，两个需求重排分别第28/17；006的historical_rate在vector第6，三个需求重排第27/13/22。两者均不在最终20，也不在Evidence8。故不是这两条原文不存在、域未选择、召回窗口缺失或policy拒绝；直接丢失发生于重排后锚点/轮转窗口。不能直接推导增加topK、恢复旧双锚点或替换gold。

另作3次有界只读运维源检查（两份唯一文档），在当前BGE容器中使用本地缓存tokenizer、零推理复核：两片段分别39/43字符、26/39 tokens，必要条款完整处于512窗口内，排除其token截断。现行Adapter仅把content送给BGE；这两份文档另有标题与writtenDate，原短片段不含2016或住宿用词。上下文缺失可能影响相关度，但改善效果尚未测量，也未审核当前入选文档是否能提供等价证明；**不是已证实的唯一模型根因**。不修改正文、补写元数据、放宽validator或通过改变expected来关闭。下一最小诊断应比较既有授权元数据的上下文表示与现有正文表示，固定候选池、模型和问题，gold只用于结果后观察；须先明确方案/边界并按原流程评审，不能直接改在线排序。

原始诊断文件逐字复制到`knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-post-warmup-20260908-01.jsonl`，SHA=`923697c6a8314e8f4a64d83f307e91df7bc308f7240c70007f5589ce1a95af5f`；旧失败SHA仍`7387ba9450d46529c48434592d09a2b846cfb4c5532b922ec2a6b25512c378b6`。有限token/元数据控制台结果归`knowledge_stage_b_rerank_visibility.v1.json`，显式标注人工记录来源及未证明项；未保存正文、问题、JWT或模型响应。证据/定向追踪提交=`c066e9a`。

零外部调用的离线反事实检查：仅对该不可变文件中的每域召回rank及每需求BGE排序，比较`sum(path 1/(60+rank)) + 1/(60+requirement_rerank_rank)`的等权rank融合，再按既有需求锚点/轮转取20；gold仅在完成排序后查位置，未输入排序。两条缺口位置分别变成11/18，仍不在前8，其余六例保持预定来源位于前8。未重放Selector字节预算、policy或Summary，故不是实际Evidence通过；不调整权重试参直到gold通过，不据此修改线上算法。该结果不支持“仅增加一层等权RRF即可关闭”方案，也不证明所有其他融合参数无效。

本轮代码/证据复核两轮：首轮核对来源commit/hash、八例不删减、两个失败不能因结构sufficient而改判；补齐从原始rerank分数复算人工记录的名次，并验证目标分数无并列歧义。复评核对新旧字节、实际调用数、仅本地元数据检查、三层策略和owned进程清理；本次测试/证据切片无未处理Blocker/Major/Minor，两个业务质量缺口仍Open。不冒充独立外部人员或整体代码评审完成；无设计语义修订，不为动态计数升级文档。

本轮实际定向命令为§20.53相同七个pytest文件，新增两项不可变证据测试后最终`187 passed`（1.21秒）；`compileall -q tests/system_e2e/test_knowledge_stage_b_quality_v3_probe.py`通过。原35/37追踪及相关排序/Evidence/Summary6契约保持既有证明范围。无生产/Java修改，不重复上一轮全量2866项、mypy或Maven，也不声称本轮重跑这些命令。最初运维hash命令在Runtime目录误用了仓库相对路径，绝对路径复核后通过；一次无输出metadata投影仍计入上述3次读取，不隐瞒调用。有限资产敏感模式扫描0命中，Git diff检查通过；索引/alias和历史正式UAT结果不变。

当前`WP-KRETRIEVAL-QUALITY-01=Blocked`、专项UAT=Deferred保持；存储发布及推理就绪已验证，剩余是两条必要来源的重排/窗口问题和当前Rewrite8/Summary6完整端到端实证。不得自动调用付费模型、创建run-09或将这次本地手工计划诊断当作全目标完成。

### 20.55 授权元数据重排表示的有限离线配对方案（2026-09-08）

承接§20.54，仅执行既有DIAG范围的本地实验，不改变L2在线合同或生产版本。比较同一批已授权候选的正文评分与上下文评分；不增加Gate、付费candidate或索引版本。保持当前8个手工计划、原gold、b2快照、模型及keyword/vector20、final20、Evidence8不变。备选“只加Prompt”不能解释已给定计划后的丢失；“扩大窗口/调融合权重”尚无必要性证据；本次只检验当前typed DTO已经提供的元数据是否改善短条款相关度。

- 表示唯一固定为：原始content在前，随后非空title、documentNumber、writtenDate，中文标签分别为“文档标题”“文号”“成文日期（非生效日期）”。不读取ES私有section、上文/邻居、附件全文、URL或新字段，不生成事实、行业标签或时效判断。title/documentNumber各≤256字符、content≤4096、日期ISO；总表示≤4700字符，原始正文不截断、不覆盖。空元数据不补造，全部为空时表示保持原正文。长文受原模型512 token窗口约束，不声称尾部元数据一定被模型看到。
- 两臂在同一个RerankPort调用内使用完全相同的query及有序候选；先raw，再context，各一次本地BGE，禁止失败重试。raw输出仅作对照，context分数进入本次测试对象图的现有quality-v3 ranker和Selector；不安装到生产组合根。候选content/hash、授权、Evidence及Summary输入仍为原始对象，表示不是可引用证据，也不发送给外部模型。
- 复用冻结`knowledge_stage_b_quality_v3_probe.py`的计划、typed检索、Stage、Selector、三层策略、原文核对与owned服务清理；新测试入口在限定上下文替换测试观察器，离开后恢复。不得改写冻结源码、历史结果或生产src。派生BGE响应独立校验其真实发送文本的exact echo，不伪造回显来骗过原Adapter。gold只在排序完成后用于判定，不进入表示、query、评分或排序。
- 固定预算：8个手工计划，typed search≤22、embedding≤11、配对rerank≤36（每例≤8）；如冷实例需要，单独计入一次既有合成预热，合计≤37次本地rerank。HTTP仍5秒/2MiB，Stage仍20秒；两臂占用同一有限诊断deadline，不据此提高线上时限。外部LLM、Business、索引/alias写入、retry/resume均0。不读LLM_API_KEY。
- 继承前后源码HEAD、helper/hash、binding/catalog、模型容器及Java产物、只读alias/UUID/write-block检查。结果以新精确路径`xb`创建append-only有限JSONL，只存标识/hash、分数/名次、计数、覆盖及清理布尔值；不落问题、正文、标题、文号、日期、JWT或原始HTTP响应。异常停止全批、保留有限失败，PID核实后仅停止本次服务并扫描删除原始日志。
- 判定预先固定：配对完成且所有8例均保留原定必要来源、原6例无回退，才支持进入在线设计修订；若任一缺口仍在或原6例回退，则不采用该表示作为当前修复，不再改变模板或调参追逐gold。两臂分数及候选池可复算，但不把raw单次分数差异自动当成历史结果失效。实际context Evidence由现有Selector/policy计算，禁止用“进入final20”冒充Evidence8通过。
- 这是检索/Evidence局部诊断，不验证LLM选域/Rewrite8、Summary6引用/usefulness、澄清或完整Spring端到端；即使8例通过也不能关闭专项UAT。实际预算、结论、测试和评审状态在本节追加，不更新长期UAT测试总数。

方案内审三轮：第一轮限定读取授权→评分→原文Evidence所有权，排除未公开section和成文日期等同生效日期；第二轮核实DTO真实上限为title/documentNumber各256，修正表示总上限及exact echo独立校验，禁止替换candidate.content/hash；第三轮核实双臂实际预算36+独立预热1、失败全批停止、旧文件不变和不使用gold调参。随后单独只读复评L2_01_01 §7.4/§8.3/§9.4、当前Stage/Adapter/Selector及§20.54证据：仅上述离线实验可实施，S0=0、S1=0、未处理S2=0；线上表示变更仍未批准。该复评是与编写分离的检查阶段，不冒充独立外部评审人员。

执行前实验实现范围冻结为`tests/system_e2e/knowledge_stage_b_context_rerank_probe.py`及直接测试；当时独立BGE派生文本校验只存在于实验工具，生产Adapter不改。代码复核首轮发现3个输入边界测试在构造真实candidate时已提前触发原validator，尚未覆盖实验格式器；改用显式合成对象测试格式器，未放宽原断言或生产校验。复评验证配对query/候选顺序、raw失败不调用context、context失败不回退raw、403时rerank0、原文/hash不变、patch退出恢复、精确source绑定和有限结果。该实验切片Blocker/Major/未处理Minor为0，整体StageB质量仍未关闭。执行前定向八文件pytest=`214 passed`（1.72秒）；`mypy --strict src`=134源文件通过；两个新增文件compileall通过。此时尚未执行真实配对及全量/Maven；随后执行和实现结果如下，不以旧§20.54的6/8代替。

实际配对已于clean `401988e531a231e10cbfc50ce50e00b8cbe8d8b4`执行一次：入口`python -m tests.system_e2e.knowledge_stage_b_context_rerank_probe --execute --result <受控外部路径>`，source SHA=`18376f164d5811925b4ffa0fb212a47072687b1b2637b7e95c3f1219777ad81d`；合成预热1次/1578ms，正文与上下文共rerank36、search22、embedding11，外部模型/Business/index/alias/retry/resume均0。8例全部保留预定原文；context Evidence位置依次为015a(lodging1/living3)、004(lodging1/living2/law_rate3)、002(lodging1/law_rate5/law_effective6)、003(lodging1/rent2)、006(lodging1/historical_rate6)、015b(lodging1/law_rate2/law_effective6)、016(software1)、008(law_rate1)。两个原缺口中，rent对应rule裸重排名次17→1；historical_rate的三个需求分别27/13/22→24/10/4，由现有轮转和Selector进入Evidence6。未改变排序或gold。

完整有限文件为`knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-context-paired-20260908-01.jsonl`，SHA=`beae7ddda48b4afd8382c975f1cb107c0e24a6d489b497808c6a82a4d8b35275`。前后绑定/快照、policy/原文及清理检查通过；本次PID8484/33288均已停止，18090/19201无监听，原始日志扫描删除，旧两份探针和所有付费结果不变。该结果支持最小表示修复，不证明Rewrite8/Summary6、澄清、用户引用或usefulness；专项UAT仍Deferred。

线上设计三轮内审：①在L1既有本地模型职责内只用typed授权metadata，明确成文日期不是时效、派生表示不是Evidence；②固定4700字符/单次5秒/2MiB，保持4次160评分及20秒，旧Adapter不动且新错误不能回退raw；③仅内部Factory版本参数，main固定新值、历史默认保留、disabled零资源，运行快照需新表示SHA，回滚整版代码。只读正式复评L2_01_01 §9.6与L2_01_00 §11.1、Provider/main/typed契约及8例配对证据：S0=0、S1=0、无未处理S2，可实施DR-KRET-034；不是外部人员批准或整体UAT通过。REQ/L0/L1无职责变化，不无关升级。

实施顺序为当前DIAG→已完成的设计复评→`IMPL-KRET-022`新Adapter/Factory/main→`VAL-KRET-015`→后续完整UAT；不要求付费UAT先通过才允许代码修复。当前代码及新根non-live已完成，完整真实UAT仍Deferred；不得自动启动run-09。

#### 20.55.1 实施、反证修复与最终non-live记录

`IMPL-KRET-022`在`87213051ad0bfb297f673eec035fee024b4ae76d`实施：新增`knowledge/retrieval/bge_rerank_context.py`，仅对既有授权candidate生成同实验一致的评分文本，校验真实派生文本的exact echo和有限分数；Provider增加严格内部版本参数，main显式固定`authorized-body-first-metadata-v1`。单需求仅一次BGE，不把实验双臂引入线上；原candidate.content/hash、Evidence及Summary输入不变。旧`bge_rerank.py`和默认raw兼容调用不动，未知版本启动拒绝，错误不回退raw，disabled无Knowledge资源。没有新增DTO、endpoint、生产依赖或用户输入开关。

最终源码SHA分别为新Adapter=`8e6ad49dd0555befc211d988cc052438596133fa5d09ef811567ce5aadf0d1cd`、provider=`ecc2ebc8c3f4e2c243f1006bbea9ebc39d89292ba4db30a4111a33f9444d4d64`、main=`909e7425d139f1d78bd3b61256e06721931b5ce50b8f651b5e59a1c38b340e55`；实验源码和配对证据保持原hash。`TEST-KRET-029`补齐实际评分字符串、单请求/40项上限、错误echo/model/index/JSON/有限数、取消/超时、拒绝零调用、原文不变、metadata观测隐藏、legacy factory及当前根。没有修改ranker、Selector、policy、原gold或结果阈值。

本切片代码对照设计评审两轮及历史fixture定向复评，发现和修复如下；作者与复评阶段分离，但仍为同一执行者，不冒充外部独立人员批准。

| 问题 | 根因、最小修复与关闭证据 |
|---|---|
| B-CTX-CR-001 | 新有限证据测试误把BGE按分数排序后的响应顺序当成相同请求顺序，第一次全量2917 passed/27 skipped/1 failed。改为核对两臂相同唯一ID/hash集合、数量和需求ordinal；独立HTTP单测仍逐项核对请求query和候选原顺序，未弱化候选一致性。新增生产乱序合法响应回归。 |
| B-CTX-CR-002 | 合法JSON超大整数score在转换浮点时可抛OverflowError；合成反证复现，新增窄范围转换拒绝为invalid_response及正负超大数/无穷测试，不放宽finite validator或吞掉其他异常。 |
| B-CTX-TEST-003 | 第二次全量2927 passed/27 skipped/1 failed，冻结Employee假进程退出测试的10ms deadline在两次monotonic之间被调度耗尽，未进入poll，得到readiness_timeout而非process_exited。受控时钟复现两分支及poll 0/1，不推断某个外部进程是唯一原因。新增精确文件+用例名匹配的外部fixture，仅替换该合成用例的两次时钟读数并自动恢复；不改历史helper、deadline、断言或live行为。六项范围/恢复/超时优先级测试通过，修复提交`86fd1cbcfe81729d066d65421ec6cb68cd8249dd`。 |

历史冻结文件`test_employee_live_bootstrap_v2.py` SHA=`f204ea7fb66ffbc42bd956fd46c509e0e850c915458f9db87025bcda21c5dfc7`、`business_egress_live_bootstrap.py` SHA=`1135b8a241844de52fc4320e94794a3b7e0d40eb1fb667498d95d232393df009`前后不变。新增fixture属于全量测试可复现性接缝，不改Employee生产代码、不删除历史测试或修改冻结manifest。

以下均为本次真实执行；Python使用`C:\Python312\python.exe`，定向入口的PYTHONPATH显式指向`D:\codex\agent-runtime\src`，child进程移除LLM_API_KEY。一次定向命令最初漏设PYTHONPATH导致4项collection import错误，仅修正命令环境后重跑，无全局配置变更。正式隔离bootstrap自行安装当前源码及固定工具依赖，测试后清理临时venv。

| 命令/验证范围 | 最终实际结果 |
|---|---|
| Runtime：`pwsh -NoProfile -File .\scripts\run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe`；仅附加`PYTEST_ADDOPTS=--tb=short` | Transaction host/preflight 14 passed（4.44s）；正式隔离全量2934 passed / 27历史opt-in skipped / 0 failed（441.03s），1项既有LangChain弃用warning；未把skip计为UAT |
| `python -m pytest tests/system_e2e/test_knowledge_stage_b_context_rerank_probe.py tests/unit/knowledge/retrieval/test_bge_rerank_context.py tests/integration/knowledge/test_requirement_runtime_composition.py tests/unit/knowledge/retrieval/test_provider.py -q --tb=short` | 112 passed（54.91s）；当前根包含Business/Knowledge及拒绝/取消反证 |
| `python -m pytest tests/integration/adapters/employee/test_frozen_exit_clock.py tests/integration/adapters/employee/test_employee_live_bootstrap_v2.py tests/integration/adapters/employee/test_employee_live_bootstrap_v2_history.py tests/integration/adapters/test_business_egress_live_bootstrap.py tests/integration/adapters/test_business_egress_live_bootstrap_v2.py -q --tb=short` | 38 passed（2.97s） |
| 最终状态同步后：`python -m pytest tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py tests/system_e2e/test_knowledge_stage_b_quality_v3_probe.py tests/system_e2e/test_knowledge_stage_b_context_rerank_probe.py -q --tb=short` | 68 passed（1.28s）；当前追踪、旧/新有限证据及实验失败边界通过 |
| `python -m mypy --strict src`；`python -m compileall -q src`及本次新增/修改测试 | 135源文件类型通过；编译通过 |
| agent-service：`..\serviceCenter\mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test`，隔离child固定stub/Knowledge disabled默认，Java25 | BUILD SUCCESS（40.058s），40项/0失败/0错误/1旧opt-in跳过；当前Business和Knowledge Spring→Runtime E2E各1项均实际执行、0skip |
| es-query-service：`..\serviceCenter\mvnw.cmd -Dtest=Knowledge*Test -Deureka.client.enabled=false test` | BUILD SUCCESS（10.920s），29项/0失败/0错误/0skip |
| 两份L2 `validate_detailed_design.py --file <目标> --root D:/codex --strict`；P3 `validate_implementation_plan.py --file <目标> --strict` | 均0 errors/0 warnings；最终纯状态同步后复核 |
| `run-nonlive-regression.ps1`及`run-all-services.ps1` PowerShell AST；有限资产/暂存差异敏感模式；`git diff --check` | AST 0错误、凭据模式0命中、差异通过；未运行全量服务启动脚本 |

本次没有Java生产修改，因此未重跑Employee、Transaction和common-security模块各自的Maven全量，不复制旧数字；当前Java边界由上述Spring/Knowledge安全测试及Python正式全量防回退覆盖，旧模块证据保留原范围。最终本切片Blocker/Major/未处理Minor为0，完整StageB真实UAT缺口不随切片复评关闭。

完成后额外4次只读ES元数据请求复核：现行alias仍指向b2、UUID=`jJ5Ww3LCRWWycfDkUZvmdw`、count15521、write block=true；首次flat settings过滤投影未返回所需键，改用完整settings读取后确认，不把空投影误判为真实漂移。索引/alias写入0，旧索引/历史证据不变。只停止本次owned隔离服务；没有重启用户持续运行的服务，生产部署需加载新提交方能采用新评分表示。

提交拆分：`a9aeb75`离线方案、`401988e`配对工具/测试、`ba48afb`正式设计和有限证据、`8721305`生产表示及当前根测试、`86fd1cb`冻结测试时钟隔离；最终状态同步独立提交，最终SHA和远端结果以Git及交付报告为准。所有当前增量验证完成，但本轮外部模型0，未读取Key、未创建run-09或复用run-08。两条固定手工计划的来源覆盖缺口已在8/8局部配对关闭，当前Rewrite8/Summary6的澄清、模型规划、最终引用和usefulness仍需完整真实专项证据；`WP-KRETRIEVAL-UAT-01=Deferred`、`WP-KRETRIEVAL-QUALITY-01=Blocked`保持，不能宣布阶段B全部完成。

### 20.56 当前生产版本原十例独立UAT（2026-09-08）

用户明确批准上一轮提出的10 E2E/28模型及32search/16embedding/32在线rerank，另一次启动预热，累计E2E上限26、模型67；精确协议由UAT_01 v1.34 §14.32治理。起始clean HEAD=`36ba62d2e91eab6ea9f7781e73da1414f4365e6f`，与origin/codex一致。八批实际累计16/39/27/14/14，旧run-08已消费，不能恢复。新授权只允许独立run-09；不自动run-10，不改原十例/gold、当前生产代码或b2索引/alias。

直接DAG：既有NONLIVE已完成→本协议三轮内审/设计复评→新runner/fake与代码复核→提交clean冻结→一次预热/环境检查→独占authorization→一次完整UAT→QUALITY评审/验证/状态及Git。UAT=In Progress，QUALITY=Blocked至原判据实测通过；GATE-KRG-006保持原已关闭实施入口，不新增重复审批门。准备不等于UAT通过。

三轮内审已完成：①旧helper固定v1/a5，明确新runner仅局部读取v2/b2且完整资产冻结；②旧观察器只覆盖raw Adapter，新增当前Adapter只读探针、方法只执行一次、原文及实际Summary绑定不变；③固定28模型与32+1本地rerank，预热前持久化尝试、失败/中断不重试、目录排他、十例不删减、累计范围明确。未修改历史代码或放宽validator。

分离的正式只读复评覆盖UAT_01 §14.32、P3当前DAG及L2_01_00 §8.6/11.1、L2_01_01 §9.4～9.6、L2_01_02 §9.5、原case/gold与旧runner生命周期。结论：该测试接缝可实施，S0=0/S1=0/未处理S2=0；授权仅本次执行，不证明真实效果。复评为同一执行者与编辑分离阶段，不冒充外部人员评审。后续实际fake、冻结、调用及终态在本节追加。

#### 20.56.1 新runner准入验证

仅新增`tests/system_e2e/knowledge_stage_b_uat_v9.py`及直接测试；版本化入口复用既有生命周期，明确v2 binding/当前8/6/v3/context Adapter。首次导入检查发现V8没有独立INSTRUCTION导出，已改为从真实任务请求工厂取指令；未修改V8生产实现。代码复核另将environment完整成功校验前移到authorization独占创建之前，防止坏预检产生看似有效授权。正式只读复评原十例、gold、实际Summary捕获、单次context观测、逐HTTP预算、预热尝试先落盘、失败/中断/重复拒绝、路径patch恢复及旧hash，无未处理Blocker/Major/Minor；这是本runner切片结论，不是阶段B整体UAT通过。

本次实际验证（Python3.12.4；各non-live子进程移除Key）：

| 命令/范围 | 结果 |
|---|---|
| Runtime `python -m pytest tests/system_e2e/test_knowledge_stage_b_uat_v9.py -q --tb=short` | 初始80 passed（3.79s）；包含当前完整对象图、真实provider wire及context三次观察 |
| 同目录 `python -m pytest tests/system_e2e/test_knowledge_stage_b_uat_v9.py tests/system_e2e/test_knowledge_stage_b_run_08_history.py tests/system_e2e/test_knowledge_reranker_warmup.py tests/system_e2e/test_knowledge_stage_b_citation_check_v2.py -q --tb=short` | 最终131 passed（19.78s），含追加CLI三阶段/不重复预热、JSON重复key/非有限反例；新runner直接测试83项 |
| `pwsh -NoProfile -File .\scripts\run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe`，PYTEST_ADDOPTS=--tb=short | host/preflight14 passed（3.77s）；隔离安装后全量3014 passed/27历史opt-in skipped/0 failed（432.52s），1既有LangChain预告；全量采集后新增的3项已由上行覆盖，临时venv已清理 |
| `python -m mypy --strict src`；新增runner/tests `compileall -q` | 135源文件通过；编译通过 |
| agent-service `..\serviceCenter\mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test`，Java25、stub/Knowledge false默认 | BUILD SUCCESS（41.238s），40项/0失败/0错误/1旧opt-in skip；当前Business及Knowledge Spring E2E各1项实际通过、0skip |
| es-query-service `..\serviceCenter\mvnw.cmd -Dtest=Knowledge*Test -Deureka.client.enabled=false test` | BUILD SUCCESS（10.533s），29项/0失败/0错误/0skip |
| P3 strict、现有两启动/回归脚本AST、staged完整diff和凭据模式扫描 | 0 errors/warnings、AST0错误、凭据模式0命中、diff通过 |

额外仅3次只读ES元数据请求核对b2 alias/UUID/write-block/mapping，BGE容器/镜像身份有效；没有新模型或BGE推理调用。隔离端口18080/18090/19091/19201空闲，Java25及既有classpath/auth JAR可读。没有Java生产或Business修改，不重复Employee/Transaction/common-security各模块Maven全量，保留旧证据范围。代码提交与精确clean冻结以随后manifest记录为准；真实环境预检、一次预热和付费UAT尚待执行。

#### 20.56.2 一次执行终态及非live失败复核

§20.56.1为执行前记录，本节替代其待执行状态。设计提交`b9d7fd0`、runner/tests提交`dab4fef`、准入记录提交`dab9fa118b3cf9effda1e89e985d61e30a527ac0`均已推送codex；最后一项为本批clean frozen HEAD。manifest schema9冻结382项源资产、258项可执行资产、原十例/gold、当前Rewrite8/Summary6/quality-v3/context及b2索引/模型绑定。严格独占执行一次，不修改冻结源码或历史批次。

依次执行新runner的prepare、check-environment、authorize、execute。一次独立合成rerank预热成功，随后真实auth/Spring→stub冒烟模型及Knowledge为0，才创建绑定startup/environment哈希的authorization。run-09首个模型HTTP前已消费；正式批次执行2例/4次模型后失败停止，search/embedding/在线rerank/Summary/Business/answer/retry/resume均0。包含预热的累计正式计数为E2E18、模型43、search27、embedding14、rerank15，没有突破授权上限；剩余上限不是重用该批次的权限。

| 用例 | 实际结果及证明边界 |
|---|---|
| UAT-KB-001 | Passed；HTTP200、no_result、clarification_required，两次模型，检索/embedding/rerank均0。已实际证明当前版本该例的澄清；没有引用，不将默认citation布尔值当作摘要成功。 |
| UAT-KB-015a | Failed；HTTP502/downstream_failure，selection成功、Rewrite8 invalid_output。没有任何检索或Summary，requiredClauseChecks均false，input_binding_missing是未产生Summary输入的后果，不是已生成错误引文的证据。 |
| 其余八例 | Not executed；首个失败停止，不用手工计划、旧成功或fake结果代替本批真实执行。完整表见UAT_01 §14.33。 |

全部八项运行文件从受控输出目录逐字节复制到`agent-runtime/tests/system_e2e/knowledge_stage_b_run_09/`；SHA校验一致，以精确binary属性保存，不修改原始文件。证据唯一权威为该目录，以下是提交前核实值：

| 文件 | SHA-256 |
|---|---|
| manifest.json | c0411adab152939f09e5c06b866d017a0ade7c1382fb1c785d891454f6d39071 |
| authorization.json | 30d4aa9007e694de715118f3450945eec93654a0f3ccab399ce3a7390e74d71c |
| startup.jsonl | 9484a41eaf700cd69675987afc22deddf10302fefff6a3108f3919b077c54d12 |
| environment.jsonl | 753c395c33e04976b05598a87d25ff00503cf5c174ac6bebd94665ad39d90ddf |
| consumed.json | ffe005f17400ab111103f135cc1d47ede32be0309e505bc14ca3d43b653bac3d |
| journal.jsonl | 0bf32c39e1021482bcd71ef3ee46c2f8fecb54db14b983accfaf097d4b9aed67 |
| evidence.jsonl | 962c8ccde14b5706adb6621ef10a58ab25749a825e76a2e04ffbfccce49fc7cc |
| result.json | de416286b8ac6d416781f7e6f22b4cc57f6d84fa8dd5f03a25bb7fce6e3dd4b0 |

原始日志扫描后删除、owned进程退出及client关闭、前后源码/索引/模型绑定检查均通过；执行后18080/18090/19091/19201无监听。ES索引/alias/真实数据写入0，没有恢复旧运行或新建run-10。新result顶层failureKind=null表示没有额外runner异常，不表示该批成功，真实终态以status=failed及case为准。

结合个人学习项目的聚焦根因复核：

| 问题 | 当前证据与最小判断 |
|---|---|
| B-R9-OUTPUT-001（Open） | 失败定位于Model响应边界/Rewrite8，任务失败及零下游证据强；没有保存原始模型响应，无法确认是provider JSON/finish标记还是任务字段/数组/枚举形状，精确子原因证据不足。不能断言本次由ES、rerank或缺语料造成。 |
| 合同是否不可实现 | non-live合成的015a lookup计划，两个subject_scope要求、无missing_conditions，在当前真实Rewrite8请求/解析器通过。设计允许定义查询，不强加适用性三段证明；这只排除该类计划不可表达，不证明真实模型遵循合同。 |
| 有限诊断是否充分 | 五个合成反例：非法JSON、缺字段、非法kind、非连续ID、多余字段，均可映射到同一invalid_output。Gateway未保留更细分原因，现有证据不能反推实际分支。下一最小诊断方向是版本化有限phase/code枚举，不保存模型正文；本批不盲目改Prompt、validator、ES或gold，不新增付费候选。 |
| 关闭条件是否过重 | 每批一旦失败不补跑仍是已批准预算/安全合同；没有据此新增Gate或重复全量环境，runner归档复用现有冻结Git读取及换行还原校验。核心P0真实未通过不能因个人项目背景改判；阶段B仍未完成。 |

新增`test_knowledge_stage_b_run_09_history.py`验证八项SHA、冻结提交源码重建、原十例、预算/任务/快照、有限结果/清理、拒绝重用，以及上述合同合成反例。首次运行7 failed/86 passed仅发生在新测试：一项把Git LF blob直接当作Windows冻结工作字节，六项构造StructuredModelResponse遗漏必填usage_total_tokens。最小修复为复用既有冻结Git换行还原核对并显式传None；没有修改历史文件、失败结果或生产断言。相同两文件命令复跑93 passed（19.41s），1项既有LangChain预告。

执行后实际命令：Runtime `python -m pytest tests/system_e2e/test_knowledge_stage_b_run_09_history.py tests/system_e2e/test_knowledge_stage_b_uat_v9.py -q --tb=short`得到上述93项；状态同步后 `python -m pytest tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py tests/system_e2e/test_knowledge_stage_b_run_09_history.py tests/system_e2e/test_knowledge_stage_b_run_08_history.py -q --tb=short`得到28 passed（25.96s）。新增三文件compileall、P3 strict（0 errors/warnings）、git diff --check通过；未在仅新增归档测试和状态文档后再次执行全量或Maven，不将§20.56.1的3014项夸称为包含后加10项历史测试的新全量。

本轮代码和证据复评两轮：首轮关闭上述两类新测试fixture缺陷；第二轮与编辑分离地只读核对UAT §14.32/14.33、原始八项SHA、frozen源码、四条journal、逐case计数/状态、模型边界和当前DAG，禁止从通用invalid_output推导未经证实的根因。此次状态同步不改变设计或验收标准，不触发无关上位升级。复评仅涵盖新runner、不可变归档、测试及状态：能可靠记录失败、严格停止且无未处理切片Blocker/Major；不是外部独立人员评审，也不是阶段B全体代码/效果评审通过。总体B-CR-001及本节B-R9-OUTPUT-001仍Open，`WP-KRETRIEVAL-UAT-01=Deferred`、`WP-KRETRIEVAL-QUALITY-01=Blocked`。原35/37功能追踪保持原范围，当前Summary6完整效果Evidence missing；不得自动创建run-10、重跑run-09或借本次归档扩张授权。

失败证据/复核测试提交`52684f39ebd78dc3f6acef6121702609578a19b5`；提交前8项归档与暂存blob逐字节一致、凭据模式0命中、暂存完整差异核对通过。仅本节和UAT最新终态另作状态提交，提交/推送最终结果以Git及交付报告为准，不修改冻结manifest中的执行HEAD。

### 20.57 失败原因的非live观察接缝

起始clean HEAD=`556792b170ad241d8143bfdbac8b9f6c3c420657`。上一轮执行和归档形成真实进展，本轮仅继续B-R9-OUTPUT-001的非付费诊断，不恢复任何已消费运行。主工作包、原十例/gold及关闭条件不变；UAT Deferred、QUALITY Blocked，禁止run-10或额外模型outbound。

直接依据为L2_01_00 §8.5/8.6/10.1的同一严格decoder、原异常映射及零下游，UAT_01 §14.32/14.33的有限信息和历史不可变边界。只读核实发现：ModelBoundaryError已有code，Gateway在except内部调用model_call_failed时仍可访问当前异常及cause，随后统一折叠invalid_output。不必修改历史V7/V8 parser、生产Gateway、公开observation DTO或接口；也不能从保存的run-09结果补回已丢弃的cause。

候选比较：保存模型响应违反安全边界；修改公共观测字段扩大接口影响；改生产异常码牵涉冻结parser且当前无充分根因。最小方案是在`tests/system_e2e`新增版本化测试观察器与直接测试：仅在显式作用域旁观现有失败回调，原回调仍恰好一次，返回值、异常、取消、超时及下游计数不变。它只把已存在异常投影为固定白名单的阶段/code/cause类别，不读取正文、异常消息/args、JSON文档、栈局部变量或调用新的decoder；未知值统一unknown。仅保存进程内不可变小记录，每作用域最多8项、溢出显式标识；离开作用域恢复patch、停止记录，拒绝嵌套/重叠安装，其他请求上下文不采集。没有文件输出、CLI、Key读取、网络入口、模型执行能力或新运行Schema；未来如何接入真实执行必须另行明确，不能修改run-09。

三轮内审：①排除在P3重定义生产错误或改变decoder identity，仅落实既有测试诊断责任；②将任意exception字符串改为代码白名单和有限cause类型，检查未知/畸形code、循环cause、记录上限与敏感反例；③增加作用域外并发、退出后子任务、取消、嵌套拒绝和恢复测试，不新增公共ContextVar合同或生产观察链路。REQ/L0/L1/L2职责及接口没有变化，按最小范围不升级这些文档或UAT协议。

实施范围仅新增`tests/system_e2e/knowledge_model_failure_probe_v1.py`及`test_knowledge_model_failure_probe_v1.py`，P3只记录计划/证据。直接顺序：上述规则复核→仅fake实现/测试→当前根零下游及现行观测防回退→代码对照复评→状态/Git；真实UAT保持独立暂停。待实现的测试包括provider framing/JSON、task JSON/shape/semantic、成功无记录、未知异常、敏感异常不泄漏、8项上限、相同公开ModelTaskResult、当前8/6/v3根失败零检索和client关闭，以及旧八项hash不变。使用synthetic transport，不读取Key、不访问真实服务，不声称能重建本次真实失败的字段。

正式只读复核：依据上述L2和现行Gateway/异常/observation合同，分别检查数据所有权、单decoder、零副作用、可验证性及计划直接DAG。该观察器仅消费已有有限错误，不新增生产规则、公开Schema或运行授权；S0=0、S1=0、无未处理S2，允许上述两文件non-live实施。审查是同一执行者与编辑分离阶段，不冒充外部独立人员批准；具体未知字段无法还原及整体UAT缺口保持Open。

#### 20.57.1 实施、代码复评及验证结果

上述两文件已实施。观察器只在已有Gateway失败回调执行期间读取当前异常：20个精确code白名单映射有限阶段，cause只按已知类型分类、最多追溯8层，未知类型不调用其自定义属性；不读取异常消息、JSON文本或frame。记录为frozen/slots对象、tuple快照，最多8项并显式overflowed。单安装锁防止嵌套覆盖，测试级ContextVar隔离其他请求，退出后关闭collector并恢复原hook；未来其他作用域运行时，旧子任务也不能追加到任一collector。生产代码不引用该测试模块。

代码对照复评两轮，第一轮发现并修复：B-DIAG-CR-001，未知cause子类可能重载属性，应停止跟随而非执行自定义逻辑；B-DIAG-CR-002，新测试不应要求可演进的生产HEAD永久等于基线，改为仅保护历史run-09原始字节，当前生产零差异由本次Git检查证明；B-DIAG-TEST-003，补足旧子任务在新观察作用域仍在运行时的隔离，以及取消作用域所有者后恢复hook/锁的反证，避免仅在hook已经撤销后断言无记录的弱测试。类型检查最初1项attr-defined失败（Gateway未显式导出导入的hook），改为对现有测试patch目标作明确Callable类型绑定，未修改生产模块导出或加ignore。第二轮只读复评全部安全、上下文、有限输出、回调一次、原ModelTaskResult与观测完全一致及真实生产根零下游：该诊断切片Blocker/Major/未处理Minor为0，不是阶段B整体评审通过，也非外部独立人员批准。

| 本轮实际命令（Runtime目录，non-live child移除Key） | 结果及范围 |
|---|---|
| `python -m pytest tests/system_e2e/test_knowledge_model_failure_probe_v1.py -q --tb=short` | 初版28 passed（2.15s），随后新增两个反证；最终直接测试30项由下列组合覆盖 |
| `python -m pytest tests/system_e2e/test_knowledge_model_failure_probe_v1.py tests/unit/test_run_observation.py tests/unit/model/test_budget_concurrency.py tests/contract/knowledge/test_rewrite_task_v7.py tests/contract/knowledge/test_rewrite_task_v8.py tests/integration/knowledge/test_requirement_runtime_composition.py -q --tb=short` | 232 passed（48.41s）；包含当时29项probe、共享观测/并发、V7/V8合同与当前8/6/v3完整对象图 |
| `python -m pytest tests/system_e2e/test_knowledge_model_failure_probe_v1.py tests/system_e2e/test_knowledge_stage_b_run_09_history.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q --tb=short` | 最终52 passed（14.81s）；包含最终30项probe、冻结Git/run-09哈希及既有35/37追踪 |
| `python -m mypy --strict src tests/system_e2e/knowledge_model_failure_probe_v1.py` | 修复后136源文件通过，无ignore或生产导出变更 |
| `python -m compileall -q tests/system_e2e/knowledge_model_failure_probe_v1.py tests/system_e2e/test_knowledge_model_failure_probe_v1.py`；P3 strict；Git范围/差异扫描 | 编译通过；P3 0 errors/warnings；目标外及生产src修改0 |

上述pytest各有1项既有LangChain预告，不影响断言。本轮没有重跑全量隔离bootstrap、Spring/Java/Maven或任何真实接口：仅新增test-only观察器且不装配到生产，当前根和受影响共享观察/并发回归已执行，旧全量/Java证据保留原范围。没有修改任务/Prompt/配置、生产src、公开DTO、索引、alias或任何历史资产；无Key读取/付费/本地BGE/业务调用、无服务启动、无新run。

本轮只能关闭“无法保留既有有限异常类别”的non-live测试工具缺口，不能关闭B-R9-OUTPUT-001的真实原因或8例未执行责任；run-09的已丢弃信息无法恢复。下一次真实执行需明确的新批次及观察证据绑定，当前没有这项权限，不准备run-10，也不把该工具或synthetic结果改称新UAT通过。P3/UAT现有终态、总体目标及关闭判据保持不变。

观察器及30项直接测试提交`13d80c4e0dd46b59aa9ea606061dcc22038ed318`，仅包含上述两个新增测试文件；提交前已检查status、diff --check、暂存文件清单及完整暂存差异。本节验证记录另作状态提交，不改变run-09 frozen HEAD或历史资产；推送结果以交付时Git核实为准。

### 20.58 持续授权恢复与单次Rewrite诊断（2026-09-09）

起始clean HEAD=`534041efc17743fdbee492f3377d711f67773dad`，与origin/codex一致。用户授权完成目标所需权限且无需后续逐项申请；新执行依据为UAT_01 §14.34，不复用run-09或将其剩余额度充当新授权。先以最多1次Rewrite HTTP定位B-R9-OUTPUT-001，其他阶段全0；本次授权后的诊断单列计数。已完成的存储发布及上下文重排不重新实施，不因invalid_output猜测ES根因。

直接顺序：§14.34三轮内审/设计复核→版本化单次诊断工具及fake→提交冻结→一次执行→根据有限原因最小修复/设计评审→当前根non-live→有界正式专项→整体评审/Git。新增文件仅`tests/system_e2e/knowledge_rewrite_diagnostic_v1.py`及直接测试，复用已验证错误投影，增加固定throwSite枚举；不改公共观测、旧任务或历史运行。UAT=In Progress，QUALITY仍Blocked，诊断本身不能关闭整体目标。正常范围内不再向用户重复申请，但仍禁止重试已消费运行或无根因地追加付费批次。

诊断准入：首轮fake发现三项静态行号映射偏差和一个测试环境mock作用域错误，已对照冻结代码修正行号、限制mock存活期，不改生产断言。合并诊断/旧probe/run-09历史回归58 passed（14.26s）；追加import-source和binding先于client校验后，最终直接20 passed（0.85s）。`mypy --strict src`135源文件、两文件compileall、P3 strict及diff检查通过。代码复评两轮分别核对有限site、零原文、同一decoder、未知异常不检查、消费前落盘、导入来源/字节绑定、仅1个HTTP、超时取消和client关闭；无未处理Blocker/Major。上述为分离编辑后的同一执行者复核，不冒充外部独立人员审查，fake不证明真实失败原因。测试工具未进入生产，无Java或索引改动，不为单任务诊断重跑无关Maven。

### 20.59 真实单任务结果与完整链路续进

文档提交`e6af884`、测试工具提交`6e864a5f6ce8f07165362e13ded0fbc249706035`已推送codex。后者为单次诊断frozen HEAD，manifest SHA=`dca59ed52e9dd007c41aa1c0f273a158404a1f6cd4fb89b5d89d4c49d49d29ac`。prepare不读Key、execute独占执行一次：Rewrite8成功，search/1查询/1要求；模型1、其他调用全0，client关闭。最终合并fake/probe/run-09历史60 passed（15.49s）。没有重现旧失败，不宣称B-R9-OUTPUT-001已定位或修复。

下一直接工作依据UAT_01 §14.35，在原版本和原十例中接入有限失败观察，形成新的有界完整测量；不改变Prompt、validator、索引或gold。新runner最小复用v9生命周期，新增九批历史及独立诊断绑定，不复制服务启动或Runtime。正常推进不再重复请求权限。WP-KRETRIEVAL-UAT-01=In Progress、QUALITY=Blocked，正式十例/核心P0及最终评审仍未完成；不以这一次单任务成功关闭工作包。版本化证据目录及执行终态随后按真实结果追加。

单任务四文件逐字节归档于`tests/system_e2e/knowledge_rewrite_diagnostic_01/`，固定hash由新runner绑定。run-10代码复核第一轮发现历史result只统计在线rerank，不含run-09 startup1；已将startupCalls单列纳入总预算，不改旧结果或放宽总数。第二轮检查原任务/十例/gold/解码器、有限异常无消息、回调一次、patch恢复、先绑定后Key、消费/预算、当前context对象图及服务生命周期，无未处理Blocker/Major（仅此接缝范围，非阶段B整体通过）。新旧runner/诊断/probe/run-09历史五文件联合206 passed（23.79s），新增compileall及strict mypy135源文件通过，P3 strict零错误/警告；没有Java/生产源码变化。本次不以重复Maven或无关全量代替待执行真实专项。

run-10冻结`9774cac766d64b37d0d1a203adb80891be9a40a2`，manifest=`c8d1605700a23a72e85155a957570f11fad31cee2dfc3b5860a8beb5ffceaccf`。check-environment失败：PATH的Oracle Java8无法加载Java25编译产物；一次启动rerank成功，其余调用0，未创建authorization/consumed/result。旧服务helper只调用裸java，预检没有绑定JDK，是测试环境缺陷；不是ES/模型故障。三个owned进程退出、日志扫描删除和端口释放通过，三文件逐字节保留。新UAT协议§14.36规定仅子进程固定并预检已有JDK25、manifest绑定可执行文件，直接修复后继续；不重复运行run-10，不改已执行字节，UAT仍In Progress。

### 20.60 摘要遗漏的实证与修复切片

run-11冻结`09413f7bf0a0b3d34476b76b9db7571fbeb9b21e`，manifest=`56c3fc8b1d312e734a5ca13ed38390869befb8222673ddff7c70fb3c534b2807`，result=`2025550720405361a79d659cf02dc500dfb5561c983171d6b7bd5cf01e0d0392`，完整八文件归档`tests/system_e2e/knowledge_stage_b_run_11/`，逐字节核对原target。执行与停止见UAT_01 §14.37：001 Passed，015a Failed，其余8项未执行；实际模型5，必要上位/下位原文均已进入Summary，缺失的是引用支持，不是召回。累计正式E2E/model为20/48，独立诊断模型1另列。运行环境JDK25修复有效，所有owned进程/日志清理通过。

最小直接DAG：L2_01_02 DR-KEV-031与L2_01_00 DR-KFLOW-026三轮内审及分离设计复评→Summary7/当前root/Stage版本→定向及全量/Spring验证→代码复评→新版本有界专项→最终收口。不新增Gate，不改Rewrite8/索引/gold/validator，不把已检索正文或模型coverage声明当语义证明。两份L2版本v1.22/v1.27，ARCHITECTURE仅更新版本索引；P3/UAT本次是执行增量，不因测试数量变化升级长期合同。当前UAT=In Progress、QUALITY=Blocked；新代码未实施前仍8/6/v3，Summary7效果尚未验证。

#### 20.60.1 实施、验证及代码复评

已新增`summary_task_v7.py`，仅指令/版本区别于V6，同一parse_response及输入输出合同；bootstrap唯一8/7/v3，Stage保留6/7历史构造但生产根拒绝6/未知版。当前根、注册合同及Spring fake的版本期待同步；v9/v10特定冻结测试在隔离作用域读取run-11冻结Git根/helper，不改其旧断言。run-09历史测试的“run-10不存在”改为核对当时Git树，不把历史事实误作永远禁止后续授权；原历史八文件/hash不变。

两轮代码对照复评：首轮及测试修复了历史fixture错误换行假设、遗漏的当前注册版本期待、历史时间边界，以及新fake仍生成旧Summary6请求的问题；未改旧任务、gold、生产decoder/validator或放宽失败断言。第二轮核对同一parser/预算、分类完整性指令、single/multi-ref、当前根/disabled/旧版拒绝、失败关闭、历史作用域恢复和实际新任务wire；本次增量Blocker/Major/未处理Minor=0。与编辑分离、同一执行者审查，不冒充外部独立评审或整体阶段B通过。

| 本轮实际验证（non-live child移除Key） | 结果 |
|---|---|
| 新Summary7、Rewrite8、当前需求root/plan、历史v9/v10定向pytest | 347 passed，45.17s |
| 新v12预算/绑定/原根/原判据、run-11历史及注册合同pytest | 80 passed，5.42s；初轮旧fake请求1失败已修正 |
| v12、Summary7、Evidence Stage及Business/Knowledge追踪组合pytest | 153 passed，5.74s；与上述有重叠，不相加 |
| `scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe` | 最终Transaction host 14 passed/3.58s；全量3269 passed、27 opt-in skipped、0 failed/409.35s，临时venv清理；初轮3189 passed/27 skipped/2 failed为上述注册期待与历史时间断言，已修复并全量复验 |
| `python -m mypy --strict src`、`python -m compileall -q src`及新增测试/runner | 136源文件通过，编译通过 |
| agent-service `mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test` | JDK25、PYTHONPATH指向Runtime src、stub/Knowledge disabled；40 tests，0失败/错误、1历史系统opt-in跳过；Business及Knowledge Spring E2E均实际通过。初次缺PYTHONPATH导致main导入失败，纠正执行环境后复验，不改Java代码 |
| es-query-service `mvnw.cmd -Dtest=Knowledge*Test -Deureka.client.enabled=false test` | 29 tests，0失败/错误/跳过 |
| L2两文件strict、P3 strict、历史hash、敏感模式及Git差异 | 0错误/警告；历史资产不变、新增文件敏感模式0命中、diff检查通过 |

受控专项协议见UAT_01 §14.38：真实调用仅在提交冻结后发生。所有上述测试均不能证明Summary7真实语义效果，QUALITY及专项关闭仍须原十例实际证据。此次没有Java/公开DTO、索引/alias、读取权限或出域变更；LangChain及Java依赖预告保持既有范围，未引入额外依赖来压掉警告。

### 20.61 run-12失败后先补齐有限诊断，不继续猜测调参

实施提交`56c0899`、专项工具提交`05ffadd353eb7299849e1c63893bb18fc6671f66`已推送codex；后者为run-12 frozen HEAD。manifest SHA=`7b558c0058be884565544724a5e65a70d99df2fb298bb04031f2a5cd03c121ea`，result SHA=`8122f04207e4cead37727b49818aeb62618b0139cc6085043bf919a9a2f43ac1`。八文件原始字节已归档`tests/system_e2e/knowledge_stage_b_run_12/`，不修改旧资产。真实结果和逐例责任见UAT_01 §14.39；当前累计正式E2E22/model53，独立诊断model1另列，无超预算和重试。

确认事实：001澄清通过；015a模型任务均解码成功、两域检索成功、必要原文进入Summary，但最终HTTP502且没有有效points；选域偏离单policy预期。证据不足：旧结果没有实际后置拒绝分支，不能把验收citation_invalid当作生产quote_not_substring，也不能断言Summary7或索引修复整体有效。原始响应已按设计丢弃，不恢复、不补写历史。当前仅允许UAT_01 §14.39的纯函数有限后置校验投影与合成反证；不修改生产validator/Prompt，不创建run-13。

直接落点新增`tests/system_e2e/knowledge_summary_failure_probe_v1.py`及直接测试；核验固定代码位置、coverage/引用/子串各类错误、未知及恶意异常零泄漏、原异常对象/返回结果不变。该工具尚不构成真实诊断完成或UAT通过。现有设计/实现/non-live工作包保持其已验证范围；UAT仍In Progress（真实执行暂停、诊断继续）、QUALITY仍Blocked。正常目标内无需重新请求授权；下一付费动作须由能改变下一行动的诊断方案和固定预算驱动，而不是按剩余额度机械开新批次。

#### 20.61.1 有限后置诊断实现与复核

纯投影函数已实施，未注册到生产、未装配新live runner，不捕获或保存新模型响应。Coverage的十个既有raise位置逐项映射有限branch；Extractive沿用原reason枚举。仅精确InvalidSummary和枚举类型可进入投影，其他类型不读取自定义属性；最多32个frame，仅检查代码身份和行号，不读取cause、消息或frame局部/全局数据。返回frozen/slots记录，无全局hook、IO、网络或validator二次执行。

三轮分离编辑的代码复核：首轮要求补齐深栈上限、零validator重入、以及当前Summary7解码成功但后置拒绝的反证，三项已补齐；第二轮发现深栈反证没有明确断言必须抛出，改为pytest.raises防止无异常时假通过，同时澄清未知位置仅phase/branch为unknown的文档表述。第三轮确认每个当前Coverage抛出分支都有合成测试、静态位置变动会使测试失败、未知/恶意异常不泄漏、两级校验职责不变。有限`coverage_refs_or_domain`保留源代码合并分支，不冒称可以再细分实际引用或域错误；这是明确接受的诊断粒度，后续如仍不足需在内存作用域分析，不允许回填旧结果。该工具切片Blocker/Major/未处理Minor=0，审查人为同一执行者的分离只读阶段，不是整个阶段B通过。

| 本次实际non-live验证（子进程移除Key） | 结果 |
|---|---|
| 新probe、run-12历史、Summary7、原摘要拒绝reason组合pytest | 70 passed/0.25s |
| 新probe、run-11/12历史、v12 runner、Summary6/7、当前root、Business/Knowledge追踪组合pytest | 245 passed/50.09s |
| 补齐反证后的probe及run-12历史直接pytest | 23 passed/0.16s |
| 全部`test_knowledge_stage_b_run_*_history.py`、最终probe、Business/Knowledge追踪pytest | 91 passed/106.79s；原历史字节及35/37追踪保持通过 |
| `python -m mypy --strict src tests/system_e2e/knowledge_summary_failure_probe_v1.py`；新增三文件compileall | 137源文件通过；编译通过 |
| P3 strict、敏感模式扫描、Git diff --check；owned端口检查 | 0 errors/warnings；新增资产凭据/JWT/私钥模式0命中；端口无本次服务残留 |

上述有重叠，不相加。run-12后没有修改生产src、case/gold、citation checker、Rewrite/Summary任务或任何ES资源；因此未重复执行§20.60.1已通过的全量隔离3269/27、Java40/1及29/0，仍保留其原执行范围和时间，未将新增测试计数写入长期UAT合同。没有run-13、新模型调用或新服务启动；原日志已由runner扫描后删除，有限归档可追溯，原始模型输出不可恢复。剩余实质责任是015a域语义及后置拒绝根因、其余八例真实专项和最终质量收口；授权本身不缺，不请求重复授权。

### 20.62 检索质量主目标与有限诊断增量

用户明确：资料录入不足时不要求住宿费问题必须通过，主要目标是通过向量库/知识库设计改进提高召回准确率。依据L2_01_02 v1.23 DR-KEV-032/033及UAT_01 §14.40，不把这项补充解释为允许漏掉已有必要原文、忽略502或改判历史。原十例仍保留失败/未执行状态；住宿只是代表集之一，非唯一关闭门槛。

当前安全可执行顺序：①按原证据区分语料/检索/回答；②三轮内审和只读独立阶段复评设计；③实现测试侧指标与明确内部原因，定向及必要回归；④基于人工可核实原文扩充代表集、留出集及冻结通过标准；⑤有界检索对比及必要端到端；⑥正式评审和质量收口。不新增Gate，不把真实模型证据当作这两个零网络代码切片的入口；整体UAT与QUALITY仍未完成。旧20.61时点的行号探针只保留历史来源，当前工具升级为稳定枚举投影。

本增量最终允许修改范围（以v1.24修正为准）：L2_01_02、P3、UAT_01、ROADMAP_01及ARCHITECTURE版本入口；`requirement_validation.py`内部枚举/兼容异常/原拒绝原因、已有纯测试探针及直接测试；新增`tests/evaluation/knowledge/retrieval_metrics.py`及测试、有限只读复算资产。`summary_validation.py`及旧哈希测试不修改。无公共DTO/Stage签名/结果语义、模型任务、配置、索引、alias、权限及历史资产修改。没有新付费运行，本轮不读取Key。

验收：拒绝条件不变而原因可区分；指标不读摘要结果，不把missing/unknown或未标注计为通过；有限原证据可分开呈现必要原文入选与回答失败；原35/37及History保留证明范围。具体代码、测试及设计/代码评审结果在本节记录；尚未执行的代表性整体质量测量不得标为Done。

设计三轮内审已执行：①分开现有资料漏召回与缺料分母，补齐未标注指标为null，禁止据摘要结果反算检索；②核对内部枚举而非公共契约，明确phase不是生产执行证明，来源ID/哈希输入必须有界；③核对现有WP直接依赖、历史不可变、无新付费批次及后续代表集/留出集未完成，避免新增循环门禁。随后与编辑分离的只读设计复评覆盖REQ-KQUALITY-002/003/004、L1_01 §4.6、L2_01_02 §9.2.1/13.8及当前P3/UAT/ROADMAP：两个切片可实施，S0=0、S1=0、无未处理S2；不代表全阶段或外部人员评审通过。L2/P3严格校验均0错误/0警告，Git差异无空白错误。

#### 20.62.1 冻结兼容设计复核

设计提交`4f88e93`已推送。首轮实现的166项定向测试通过，但正式隔离全量发现历史Summary V2～V5与诊断manifest直接校验summary_validation.py整文件SHA；只增加枚举也违反冻结合同。此问题归为设计落点遗漏，不是效果失败；暂停受影响实现，不修改旧哈希、历史测试或断言。比较后不选“更新旧哈希/把全部旧测试迁移到冻结Git”，采用最小方案：覆盖模块本地新枚举和InvalidSummary兼容子类，原摘要validator整文件还原不产生diff。

L2_01_02 v1.24复核三轮：①核对旧摘要文件/任务哈希与新覆盖模块的修改边界；②核对父异常reason、固定文本、Stage catch、严格类型投影和未知子类零属性访问；③核对无新增配置/网络/依赖、旧断言保持、直接回归和原工作包DAG。随后分离只读设计复评确认：公共行为不变，父类兼容但新coverage_reason可诊断，历史哈希可验证；该修正可实施，S0/S1/未处理S2=0。以上为同一执行者分阶段复核，不声称外部独立人员评审；L2/P3 strict均0错误/0警告。

#### 20.62.2 实施、有限复算及切片收口

兼容设计提交`97ba5e192b96e9076d34f7fe4bc8a87a1c712396`，代码/测试提交`43272cb8ac9eb0330e9aa0121f13f88c389a2efe`。代码共7文件：一个覆盖校验生产模块、现有probe及其测试、Stage拒绝映射测试、新增指标纯函数及两份测试。DR-KEV-032/033已实施；原摘要validator SHA仍为`80a3846814dc360291078649697aebdd2b393971b8abb933ed0f645200c4f6d6`，旧enum/哈希测试零diff。新probe不读取调用栈、行号或消息，不接入live；指标无I/O、无问题/回答正文、无在线gold，未标注Precision/nDCG为null，缺料/未知保留但不评分。

只读复算见UAT_01 §14.40：run-11和run-12的015a必要来源Recall@20、MRR、Evidence coverage均为1，但原回答均Failed；八个历史手工计划必要来源Recall@20及Evidence coverage均为1，不是八次真实模型端到端成功。这些资产没有完整相关性分级，不能推导Precision/nDCG或整体召回准确率。三项新回归分别先验SHA、复算、保留原终态及确认字节不变，没有新建历史结果副本或改判旧UAT。

代码对照评审采用与编辑分离的两轮只读阶段：首轮发现旧validator整文件冻结冲突，返回设计修订而非更新哈希；复评核对v1.24异常兼容、拒绝集合/顺序、公开映射、严格类型与恶意子类、指标边界/null/分母、无正文和历史保护，并增加八个手工计划的独立分层反证。该两项DR切片Blocker=0、Major=0、无未处理Minor；不是外部独立人员批准，也不表示阶段B整体代码或效果评审通过。P3/ROADMAP与UAT/L2两处版本引用漂移已在兼容设计提交中最小同步。

| 本轮实际验证命令及范围 | 结果 |
|---|---|
| `agent-runtime/scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe`（显式安装当前源码的临时隔离环境） | 最终host/preflight 14 passed（3.54s）；全量3363 passed、27 skipped、0 failed（310.37s）。跳过均为既有opt-in/live或指定历史诊断资产，不能算新效果UAT通过；1项既有LangChain预告 |
| `python -B -m pytest`：probe、coverage、原摘要reason、Stage、新指标及历史复算、Summary V2～V5和诊断manifest的11文件组合 | 195 passed（0.53s）；随后新增的八手工计划复算已被最终全量覆盖 |
| `python -B -m pytest tests/evaluation/knowledge/test_retrieval_metrics.py tests/evaluation/knowledge/test_historical_retrieval_separation.py tests/system_e2e/test_knowledge_summary_failure_probe_v1.py tests/integration/knowledge/test_requirement_evidence_stage.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py -q -p no:cacheprovider --tb=short` | 最终128 passed（0.57s）；单独三项历史分层复算3 passed（0.03s） |
| `python -B -m mypy --strict src tests/evaluation/knowledge/retrieval_metrics.py tests/system_e2e/knowledge_summary_failure_probe_v1.py`；`compileall`生产src及本次直接测试 | 138源文件类型通过；编译通过 |
| agent-service中`..\serviceCenter\mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test`（仅子进程JDK25/fake配置及无Key环境） | BUILD SUCCESS，40 tests、0 failures、0 errors、1 skipped（29.366s）；Business与Knowledge的Spring→Runtime当前根E2E实际执行，旧Structured UAT opt-in跳过 |
| L2 strict、P3 strict；当前7文件凭据/JWT/私钥模式扫描；Git范围、完整暂存差异及diff --check | 0 errors/warnings；模式0命中；只含本目标文件，历史资产零变更 |

上述命令有重叠，不相加。失败经过保留：初始定向有一项旧enum总数断言失败；首轮全量3356 passed/27 skipped/5 failed（315.57s），五项均为上述冻结哈希冲突。最终采用v1.24落点、还原旧文件和旧测试后重新执行正式全量通过，未放宽断言或跳过失败。非live子进程移除Key；没有读取凭据、调用真实模型/ES/BGE、修改索引/alias、启动真实业务服务或创建run-13。Maven仅启动测试管理的fake Runtime，不持久化真实JWT/正文。

未重复执行无Java/DTO/授权改动的Employee、Transaction、es-query-service、common-security全模块Maven；没有PowerShell修改，未单独重跑AST。跨域防回退由本次完整Python、两条Spring E2E及既有35/37追踪核实，不能据此声称所有外部服务或新效果已经验收。当前仍需人工确认20～30题及不少于三分之一留出集、完整相关性分级、同快照检索基线/对比和基于真实损失的最小改进；run-12实际后置拒绝原因仍不可恢复。`WP-KRETRIEVAL-UAT-01=In Progress`、`WP-KRETRIEVAL-QUALITY-01=Blocked`，不以局部指标1.0关闭整体目标。最终状态提交及推送结果以Git和交付报告为准。

### 20.63 代表集与本地检索基线

依据UAT_01 §14.41/DR-KEV-033继续同一个`WP-KRETRIEVAL-UAT-01`，不增加Gate。执行次序为来源核对和24题协议→三轮聚焦内审及分离只读设计复核→测试侧fixture/薄runner→fake、类型及历史回归→提交源码→有界本地检索测量→归因及正式复评。已有计分工具为直接前置，当前生产检索/任务/索引不改；本轮不消费付费额度。

目标修改范围为UAT_01本协议、P3状态，以及`tests/evaluation/knowledge/retrieval_benchmark.v1.json`、严格loader、`tests/system_e2e/knowledge_retrieval_benchmark_v1.py`和直接测试。既有probe/helper/历史result保持字节不变；以当前生产context rerank进行测量。方案不新增公共合同、来源下载、索引构建或服务，执行者原文核对和后续相关性标注状态必须如实区分。基线有效不等于质量已经达标，QUALITY仍Blocked；尚未执行结果不得写为Done。

源码准备：24题（16开发/8文档族留出）、20来源/26锚点已只读核对当前b2；fixture SHA=`ca076f8096ddf1210ddcf26da1a23135ee14c3cf415960fbaf03ea1e3a8f84f9`。预算search54/embedding27/rerank29，启动rerank另1。所有题均present且无相关性grade，不能代表全库语料覆盖或精确率；空返回的P@20可确定为0，其余未标注为null，沿用原计分合同，不修改指标。

文档三轮内审及一次分离只读设计复核见UAT_01 §14.41。代码两轮复核：第一轮修复fixture焦点缺少公共税务语境、超大pytest参数ID、空结果精确率断言，并让loader在I/O前调用当前需求/敏感输入校验；第二轮修复来源预检的隐式NFC转换，补齐非NFC、重复、域和来源缺失反证。复核后此测试切片Blocker/Major/未处理Minor=0，不是整个阶段B或外部人员评审。24题保留原问题；其中KRB-015暴露文号识别把“请分别查找”纳入文号的真实线索，暂用原问题连续片段作为手工focus以保留现行合同，未修复生产缺陷或冒称验证Rewrite成功；该缺口进入下一步诊断，不通过改题隐藏。

当前定向命令：新dataset/runner、计分/历史复算、旧probe、Business/Knowledge追踪组合`pytest -q -p no:cacheprovider --tb=short`为148 passed（1.13s）；`mypy --strict src tests/evaluation/knowledge/retrieval_benchmark_dataset.py`为137源文件通过，新增四Python文件compileall通过。最初测试2 failed/38 passed/2 errors（超长参数ID含setup/teardown），修正后直接41 passed，再补充反证由148项覆盖；未删除或弱化原历史断言。尚未执行新本地测量，不读取Key。

源码冻结前正式隔离命令`agent-runtime/scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe`实际完成：host/preflight 14 passed（3.72s），全量3410 passed、27 skipped、0 failed（491.31s），1项既有LangChain预告。跳过均为既有opt-in/live或历史诊断，不能计为本次新UAT；该命令移除子进程Key且不消费真实运行。P3 strict为0错误/0警告，五项新资产凭据/JWT/私钥模式0命中，diff --check通过；生产src、serviceCenter、业务Java和历史资产零diff。此测试侧增量未重复Java/Maven或PowerShell AST（无相应改动），真实检索执行与其证据单列，不能用non-live替代。

#### 20.63.1 本地测量完成与下一步决策

协议提交`e24f883`、源码提交`0727bfd8e8bceb62f5044dcd4bfd253ab7eff802`已推送origin/codex；干净HEAD上运行`python -B -m tests.system_e2e.knowledge_retrieval_benchmark_v1 --execute --result D:\codex-data\knowledge-retrieval-benchmark-20260909-v1.jsonl`，仅子进程JDK25/PYTHONPATH配置并移除Key。终态measured，24题完成、23题必要来源齐全，分组指标见UAT_01 §14.41.1；实际search54/embedding24/rerank29，另1次本地合成预热、2次来源审计，0外部模型/Business/写索引/重试/续跑。运行产物按字节复制到测试evidence，未规范化或重写原记录；SHA一致，敏感key/凭据模式扫描0命中。owned PID 33904/34524停止已复查，临时原始日志已扫描删除，无旧服务停止或索引/alias变化。

新`test_retrieval_benchmark_baseline.py`只读验证原SHA、绑定、24项原指标复算、KRB-006损失、预算及清理，不从测量终态推导UAT Passed；完整定向组合新增后149 passed（1.09s）。此前3410项正式全量不包含这一项新增的只读evidence测试，未伪报为3411全量。最终分离只读代码/证据复核确认薄runner复用当前授权检索、gold不参与在线评分、异常停批/零命中继续和来源前后检查；该切片Blocker/Major/未处理Minor=0，整体QUALITY仍Blocked、UAT仍In Progress。

| 已确认问题/线索 | 证据与判断 | 最小后续处理 |
|---|---|---|
| 多文档同域查询召回损失 | KRB-006两份公告原文均存在且hash已验，但keyword/vector各20项均无必要来源，融合37项、按需求两次重排仍无法补回 | 先对开发集上的单/多文号规范化及有界查询表达做同快照对照；不以增大最终topK或改摘要解决召回前损失 |
| 文号检索字段未参与keyword | 当前KnowledgeSearchService使用Profile的title/content/section做multi_match；现行mapping的documentNo为keyword且只是返回字段 | 先核实文号表达及metadata匹配方案；不能仅把keyword型documentNo加入全文query就声称可解决。不先重建向量库 |
| 改写语义校验误把问句前缀纳入文号 | KRB-015准备阶段核实_DOCUMENT将“请分别查找财税〔2011〕100号”当完整文号 | 独立修正文号边界的设计与测试，保留年份/编号/否定约束；不通过弱化validator或逐句业务特判解决 |
| 结构覆盖与语义覆盖不同 | KRB-006 selectionSufficient=true但必要来源覆盖0；本轮没有Summary | 结构校验不作为答案充分性结论；保留外部事实/引用核对，不伪造本次摘要结果 |

当前决策：先修复有证据支持的查询表达/召回覆盖问题，再以同快照代表集和不参与调参的留出集验证；只有仍存在可定位的向量表示/切片损失时，才提出最小结构改进和候选索引对照。现有基线23/24并不证明无需任何结构改进，也不证明已达到整体准确率目标。尚缺完整相关性分级、新旧对照、真实Rewrite及摘要后置失败收口；不再以住宿单题必须答出为质量唯一门槛，不自动产生新付费运行。

### 20.64 文号查阅前缀误拒的最小修复

起点clean HEAD=`fbc0179a847bafaf044967afd8832013ca251ae2`。直接调用当前Tax Guard和focus validator复现KRB-015误拒，旧文件将查阅前缀纳入document_numbers。单/复合表达的三次只读keyword诊断均未找回KRB-006两项来源；两次元数据读取（一次修正展示方式）确认文号字段存在，未读取正文。共5次只读ES请求、无索引写入或模型调用，不把直接ES诊断当生产Agent链路或UAT证据。基线/loader/Tax Guard/requirements四文件回归89 passed（0.35s），历史基线结果仍为23/24必要来源齐全。

本切片范围：L2_01_00 §8.8/DR-KFLOW-027；新增当前Guard及单元/生产根fake测试；bootstrap一处显式注入。P3/UAT_01/ARCH只同步直接依据和验证。旧question_semantics.py、tax_question_semantics.py、任务/Prompt、运行资产和24题基线均只读。REQ-KFLOW-002及L1 KQ-AD-013已要求保护真实条件，不需要上位职责变更。

直接顺序：三轮内审→分离只读设计复核→新Guard及当前根实施→定向/历史/类型/正式回归→代码复评与提交。沿用已有实施工作包的缺陷修复，不新增Gate。非live切片不得关闭`WP-KRETRIEVAL-UAT-01`或`WP-KRETRIEVAL-QUALITY-01`；多文档召回、完整相关性标注、同快照对比和真实后置失败仍未完成，不创建新付费运行。

设计内审三轮：①核对KQ-AD-013和旧Guard冻结，明确新增实现只替换文号token，补齐§8.4旧Tax规则与当前派生规则关系；②核对单次前缀语法、非空机关、ASCII年号、未知/重复/否定和机关歧义，补充不归一括号/地域、重复不循环和未覆盖表达限制；③核对当前root测试未被legacy fixture替换、校验先后与零下游，strict发现四个ID只有正文说明、未进入定义表，补齐定义和直接追踪。不修改Prompt、公共DTO、策略、索引或旧任务。

独立于编辑阶段的只读设计复核第1轮：实际重读§8.8、L1 KQ-AD-013及UAT §14.42，按L2实现可行性和跨层约束rubric核实职责、query/focus共用Guard、旧源码兼容、有限语法/限额、失败、测试与回滚；S0=0、S1=0、未处理S2=0，允许该Guard非live实施。接受限制B-REF-DES-001：有限词法不证明所有机关法律身份，未知/歧义表达和其他数字词素不能外推为任意改写正确；不据此减少质量验收。该评审为同一执行者分离修改后的只读复核，不声称外部独立人员批准。L2/P3 strict最终0 errors/0 warnings，原先四条追踪warning已补齐而非关闭校验。

#### 20.64.1 文号修复实施、验证与代码复评

设计提交`7a4dbb78d41a45ebd304f4e1b42599ce751639aa`、代码提交`a00b576c2f9e45d80349c21d3866a2d6cd57a210`已推送origin/codex。实现仅新增34行当前Guard、bootstrap显式注入和两份测试文件；旧两个Guard、模型任务/Prompt、生产查询文本、业务服务、公共合同、索引/alias、代表集及历史证据未修改。没有删除文件。该增量只修复KRB-015词法误拒，不能修复KRB-006多文档召回或证明真实Rewrite/Summary质量。

代码对照设计复核两轮，范围为DR-KFLOW-027/IMPL-KFLOW-015/TEST-KFLOW-019/VAL-KFLOW-010及当前调用链：首轮B-REF-CR-001（测试完整性，medium）指出多域原问题的成功测试仅模拟一个域，不能证明两个focus共同通过；已补为policy+law、两项requirement、4次search、1次embedding、2次rerank及两项合成引用，未修改已有测试断言。第二轮重新只读检查同一Guard实例、原输入不重写、机关/年份/编号/重复条件拒绝、全部计划零下游、请求隔离、disabled/双重关闭及冻结兼容。该切片Blocker/Major/未处理Minor=0；这是同一执行者分离编辑后的复评，不是外部独立人员评审，也不覆盖整个阶段B质量。

实际验证（执行子进程移除LLM_API_KEY）：

| 命令/范围 | 本次结果 |
|---|---|
| `python -B -m pytest -q -p no:cacheprovider --tb=short tests/unit/knowledge/test_document_reference_semantics.py tests/integration/knowledge/test_document_reference_guard_production.py tests/unit/knowledge/test_tax_question_semantics.py tests/unit/knowledge/test_evidence_requirements.py tests/integration/knowledge/test_requirement_runtime_composition.py tests/evaluation/knowledge/test_retrieval_benchmark_baseline.py` | 203 passed，86.98s，1项既有LangChain预告；包含首轮测试修复 |
| `agent-runtime/scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe` | Transaction host/preflight 14 passed（4.70s）；全量3507 passed / 27既有opt-in skipped / 0 failed（502.85s）；隔离环境清理后进程exit=0 |
| `python -B -m mypy --strict src` | 137 source files通过 |
| `python -B -m compileall -q`，精确四个修改Python文件 | 通过 |
| `serviceCenter/mvnw.cmd -Dagent.runtime.python=C:\Python312\python.exe -Deureka.client.enabled=false test`（agent-service目录，JDK25、当前源码PYTHONPATH、stub） | BUILD SUCCESS；40 tests / 0 failures / 0 errors / 1 skipped，40.853s；Business/Knowledge Spring→Runtime E2E均执行通过 |
| 两个旧Guard及代表集/原结果SHA、全量历史测试、精确四文件凭据模式扫描、`git diff --check` | SHA与修改前一致；凭据/JWT/私钥模式0命中；无冻结资产diff |

Maven数字来自本次控制台，未计入target里2026-08-24遗留的StructuredQueryUAT XML；本次skip为已有opt-in System E2E，不冒充真实效果通过。业务Java、服务配置与PowerShell脚本未修改，未重复Employee/Transaction/es-query-service Maven或PowerShell AST。27项opt-in跳过不计为阶段B真实UAT通过。真实模型/业务ES/BGE/索引写入/alias/重试/续跑均0；不读取Key、不创建run-13。整体QUALITY仍Blocked、UAT仍In Progress，后续必须完成召回缺口、完整相关性标注和新旧对照。

### 20.65 双文号召回损失的只读对照

在§20.64代码已推送后，针对已冻结开发集KRB-006执行四次只读ES诊断，不修改线上查询、类型化接口、索引或问题/gold。原问题不变，category过滤与policy Profile一致，size=20、只取chunkId/documentNo元数据，无正文/向量/model/BGE。先后读取settings核对当前b2 UUID=`jJ5Ww3LCRWWycfDkUZvmdw`和write block=true，中间field_caps确认documentNo为可搜索keyword、title/content/section为text。总计7次只读ES HTTP请求（4 search、1 field_caps、2 settings），各search均无timeout/shard failure，未启动服务或保存原始响应。

| 对照 | 返回数 | 必要来源情况 | 证据边界 |
|---|---|---|---|
| 原问题全文multi_match title/content/section | 20（总匹配13828） | 两份来源均不在前20 | 复现当前keyword窗口损失 |
| 相同全文，仅增加keyword字段documentNo | 20（总匹配13828） | 两份来源均不在前20 | 单纯追加字段无收益，不能据此宣布修复 |
| 使用已核实库内完整文号的terms查询 | 2（总匹配2） | 两份必要原文分别第1/2 | 只证明现有元数据可精确定位；文号由离线源检查提供，不证明线上识别或LLM计划 |
| 相同两个文号仅去掉机关间ASCII空格 | 0 | 无匹配 | 字符表示差异足以导致exact miss，非资料缺失 |

该反例支持下一步优先设计“原问题/受控query中的文号识别与现有元数据匹配”。不得将两个gold文号、年份/编号、case ID或文档ID硬编码到生产；不得把去空格后的字符串直接用于现有keyword就宣称规范化已实现。需比较在es-query-service内部完成有限、安全的等价表示匹配与新增规范化元数据字段两种影响范围；只有前者无法可靠闭合语义/性能时才使用新候选索引，原索引/alias及正文不变。识别不确定时仍走既有有界检索与证据不足合同，不能匹配同年份/编号的其他机关。该段是诊断和候选方向，不新增实现合同、不批准修改当前字段/索引；具体设计评审仍是实施前置。

完整相关性标注、新旧同快照/留出集对照、真实Rewrite/后置失败及阶段B专项UAT仍未完成。不得将诊断中的2/2已知目标命中计入原24题基线、真实UAT或召回质量改进率。住宿题继续只作代表性样本；语料缺失单列而非强制补造答案，不删除资料存在却漏召的失败题。

### 20.66 有界文号匹配的设计与实现切片

依据L2_01_01 §9.7/DR-KRET-035，保持已有主工作包，直接顺序为三轮内审→分离设计评审→Java纯词法/keyword子句/冻结开关及mapping校验→定向与回归→代码复评→隔离typed同快照对照。实施入口已完成本切片评审；不以现有GATE-KRG-006的早期通过跳过新设计，也不新增Gate或要求先跑live才可编码。生产配置保持默认关闭；其启用须有同快照、非文号回退及错误机关反证。相关工作属于已有WP-KRETRIEVAL-IMPLEMENT-01增量，整个UAT/QUALITY仍未完成。

本次范围：L2_01_01/P3/UAT_01/ARCH入口；es-query-service内部helper、SearchService、Properties、Verifier及直接Java测试。es-query-api、LLM/Runtime、现行配置、索引、alias、正文、历史任务/manifest/结果只读。Java部署字节和配置hash作为后续对照绑定，既有物理snapshot不改。完整相关性标注可独立推进，不依赖此helper；不自动新增付费候选，不读取Key。

设计内审三轮：①核对KQ-AD-013/014及公共1024码点合同，补齐成对括号/机关长度、不截取长机关尾部；②核对keyword mapping隐式normalizer/index=false，增加启动拒绝，保持默认false及旧Profile兼容；③明确超限整项关闭、未知简写不借机关和软匹配非完整语义，补齐REQ/DR定义消除两条strict追踪warning。最终L2/P3 strict均0错误/0警告。

随后与编辑分离的正式L2/跨层切片复核：重读§9.7及REQ-KQUALITY-002/003、KQ-AD-013/014、SearchService/Properties/Verifier、公开DTO/codec和现有测试；核查职责、一次查询、过滤/授权、默认及快照、错误/预算、兼容与测试矩阵。该non-live实施准入S0=0、S1=0、无未处理S2；词法身份与单文号多chunk占位属于已明确的效果限制，不宣称上线或整体UAT通过。由同一执行者分离编辑阶段复核，不冒充外部独立人员。GATE-KRG-006对本增量的准入依据增加本节；IMPLEMENT Ready、NONLIVE Blocked等待实现。状态复算发现旧UAT In Progress与新NONLIVE前置冲突，改为Blocked等待增量，QUALITY保持Blocked；不改判历史用例，待验证后再更新。

#### 20.66.1 文号匹配实现与非live验证

代码提交`d511077afa3229d6a083bcb23547cd8d80b7bf53`已推送origin/codex。9项Java实现/测试文件包含DocumentNumberQuery、KnowledgeSearchService、KnowledgeSearchProperties、KnowledgeProfileVerifier及五项测试/fixture；没有删除文件。单个keyword请求增加可选、有限文号元数据信号，配置默认false且冻结；授权、category、原全文、vector和公共DTO保持不变，失败不移除子句重试。实际application配置未启用该功能，索引/alias/正文、Python生产代码、模型任务及历史资产未改。

代码对照设计复核两轮，范围为DR-KRET-035/IMPL-KRET-023/TEST-KRET-030/VAL-KRET-016。首轮B-DOCNO-CR-001指出缺少真实Spring属性绑定及开启状态下超时零重试反证；补齐Binder合法/非法布尔、timeout/IOException和有限词法边界。第二轮重新只读核对完整差异、授权先于ES、单HTTP、默认关闭、mapping条件、不可变请求内计算、资源退出和历史兼容；该non-live切片Blocker/Major/未处理Minor=0。同一执行者分离编辑后的复核，不声称外部独立人员评审或整个阶段B通过。

| 实际命令/范围 | 结果 |
|---|---|
| es-query-service目录：`..\serviceCenter\mvnw.cmd '-Dtest=Knowledge*Test,DocumentNumberQueryTest' '-Deureka.client.enabled=false' test`，子进程JDK25 | 修复前70 passed；补齐复核反证后73 passed，0 failures/errors/skips（9.228s） |
| es-query-service目录：`..\serviceCenter\mvnw.cmd '-Deureka.client.enabled=false' test` | 全模块87 tests，0 failures/errors/skips，BUILD SUCCESS（12.075s） |
| Python `pytest -q -p no:cacheprovider --tb=short`：基线/dataset/metrics/benchmark runner、两项现行UAT追踪及所有匹配的Stage B/P5 candidate history测试 | 189 passed（122.82s），1项既有LangChain预告；没有真实调用 |
| 随后的分析复核：`python -B -m pytest -q -p no:cacheprovider --tb=short tests/evaluation/knowledge/test_retrieval_benchmark_baseline.py tests/evaluation/knowledge/test_retrieval_benchmark_dataset.py tests/evaluation/knowledge/test_retrieval_metrics.py` | 94 passed（0.36s）；原问题资产及结果SHA不变 |
| 精确9文件暂存完整差异、凭据/JWT/私钥模式扫描及`git diff --check` | 无越界文件、0模式命中、差异检查通过；提交推送成功 |

以上范围有重叠，不相加。初次Maven命令因未引用PowerShell中的`-Deureka.client.enabled=false`而被拆为非法lifecycle，构建前exit=1；修正命令引用后执行以上结果，不以代码改动掩盖环境错误。Java现有Mockito/JDK警告保留。子进程移除Key，不读取或打印凭据。

本增量没有Python/PowerShell或公共接口修改，未重跑正式全量Python、mypy/compileall、PowerShell AST及其他业务Java模块；此前§20.64.1结果保持其当时范围，不冒称本次全仓验证。Java编译及当前基线/追踪/历史回归已执行；Spring→Runtime和全目标验证仍随最终收口执行。真实ES/BGE/外部模型、索引写入、alias及付费运行均0，仅使用测试拥有的fake HTTP/Servlet；Java模式匹配不能证明Lucene兼容、真实排名或性能。

当前该代码增量IMPLEMENT/NONLIVE完成，UAT恢复In Progress、QUALITY仍Blocked。下一步按UAT_01 §14.43完成同索引24题有界隔离typed对照，补齐相关性分级并分别报告开发/留出、文号/非文号及召回/Evidence。该对照前保持生产开关关闭；不创建run-13，不继承或改判旧真实失败，也不以新增单测关闭整体准确性目标。
