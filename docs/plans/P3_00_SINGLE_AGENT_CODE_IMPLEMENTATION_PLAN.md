# [P3_00] 单体 Agent 查询能力实施与收口计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | P3_00 |
| 当前版本 | v2.45 |
| 文档状态 | Reviewed |
| 更新时间 | 2026-09-04 |
| 适用范围 | 已完成且不得回退的 Business/Knowledge 功能基线，以及效果测量终态、文档权威纠偏、全量设计落实审计和最终收口 |
| 实施授权 | Ready 不等于实施授权；本任务已另行获得目标范围内代码实施、受控验证、文档同步及 Git 提交推送授权 |
| 归档来源 | [v1.34 已评审旧版](历史文档/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN_v1.34.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

v2.34 在不修改 Rewrite V1 或历史候选的前提下新增 Knowledge Rewrite V2 精确 JSON 输出合同。v2.35 依据 ROADMAP_01 阶段 A 新增语料只读审计、版本化处理、候选索引、发布回滚和专项 UAT 工作包，并把入口门禁与 alias 发布门禁拆开以消除循环。v2.36 依据审计 v1 的实际失败修复来源可达性、正文完整性、人工优先级和精确预算边界。v2.37～v2.38 如实保留早期 candidate/UAT 及严格合同复评。v2.39 修复 legacy DOC 扁平解析导致条款关系缺失的问题并保留结构化 a4 中间候选。v2.40 将网络/损坏容器异常收敛为逐资产有限失败，以最终工具源码重建 Stage A corpus candidate-08/a5，并用 UAT/release attempt-05 完成发布收口；v2.41 修正 catalog Git/LF 分发哈希，增加历史评估输入的精确只读镜像，并让历史测试辅助层在临时仓库内复原已授权换行字节，使正式隔离回归可由干净检出复现。阶段 B 仍独立阻塞。

v2.43 聚焦修订阶段B实施中验证出的请求内rerank并发、长附件Evidence配额和分域主题词语义；根因和逐轮复评见§20.4。已通过基线仍有效，受影响增量在复评通过前暂停，不新增付费候选。

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
| [`L1_01`](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v1.17 | Knowledge 在线流程与阶段 A 离线 Corpus Build Plane | Approved |
| [`L2_01_00`](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v1.19 | 单动作、共享V3合同、V4澄清及V5最小必要域、发布后只读快照消费 | Approved |
| [`L2_01_01`](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v2.7 | typed retrieval、阶段 A asset/parser/chunk/candidate/alias 生命周期 | Approved |
| [`L2_01_02`](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v1.18 | Evidence/出域、Summary V4 及阶段 A 策略快照兼容 | Approved |
| [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | v1.24 | Business 35/35固定用例与15项Employee自然语言扩展 | Reviewed |
| [`UAT_01`](UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | v1.21 | Knowledge 功能/效果及阶段 A 语料专项验收 | Reviewed |
| [`ROADMAP_01`](ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md) | v0.8 | 语料、检索质量与图谱后续路线；阶段 A 已完成 | Reviewed |

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
| `WP-KRETRIEVAL-DESIGN-01` | 阶段 B 设计 | Knowledge L1/L2；诊断 | 最小方案、三轮内审和独立评审 | `WP-KRETRIEVAL-DIAG-01` | - | 经评审设计、独立 UAT 路径 | 合同、预算、安全与 DAG | 不改变历史版本 | Done |
| `WP-KRETRIEVAL-IMPLEMENT-01` | 阶段 B 实施 | `DR-KFLOW-016～019`；`DR-KRET-027`；`DR-KEV-026` | Rewrite V4（共享V3合同）、一次域计划、服务窗口、排序/Evidence、有限 reason；不代表真实P0通过 | `WP-KRETRIEVAL-DESIGN-01` | `GATE-KRG-006` | 最小实现、定向测试 | 不扩大公共 DTO/读取/出域 | 恢复上一代码绑定；索引不变 | Done |
| `WP-KRETRIEVAL-NONLIVE-01` | 阶段 B 回归 | 当前阶段 B L2 | fake、契约、Spring E2E、Python/Java/类型/历史 | `WP-KRETRIEVAL-IMPLEMENT-01` | - | 可复现验证结果 | 各调用次数、失败优先级、零泄漏 | 不运行付费 UAT | Done |
| `WP-KRETRIEVAL-UAT-01` | 阶段 B 专项 UAT | `UAT_01` §14 | run-03已停止：1通过/1失败/8未执行；三个批次证据不可变 | `WP-KRETRIEVAL-NONLIVE-01` | - | 逐 case 有限证据 | 累计5端到端/12模型，零重试 | 各批失败即停止，无run-04授权 | Deferred |
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
| `GATE-KRG-006` | `WP-KRETRIEVAL-IMPLEMENT-01` | slice_implementation | 阶段 B 受影响代码实施 | 是 | 根因/边界明确；三轮内审及独立分层跨层评审通过；无 fallback、权限/公共合同扩张 | §20 诊断及评审记录 | 设计维护者/评审者 | 生产代码修改前 | S0/S1/未处理 S2=0；不要求代码或 live 先完成 | 仅诊断与设计；不实施受影响代码 | Closed |

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
| 52 | `WP-KRETRIEVAL-DESIGN-01` | Done | WP-KRETRIEVAL-DIAG-01 | 阶段B独立DAG与§20证据；增量设计已复评通过，不继承live通过 |
| 53 | `WP-KRETRIEVAL-IMPLEMENT-01` | Done | WP-KRETRIEVAL-DESIGN-01 | 阶段B独立DAG与§20证据；增量设计已复评通过，不继承live通过 |
| 54 | `WP-KRETRIEVAL-NONLIVE-01` | Done | WP-KRETRIEVAL-IMPLEMENT-01 | 阶段B独立DAG与§20证据；增量设计已复评通过，不继承live通过 |
| 55 | `WP-KRETRIEVAL-UAT-01` | Deferred | WP-KRETRIEVAL-NONLIVE-01 | §20.14 run-03第二例域/必要引用不达标停止；不追加第四批 |
| 56 | `WP-KRETRIEVAL-QUALITY-01` | Blocked | WP-KRETRIEVAL-UAT-01 | 阶段B独立DAG与§20证据；增量设计已复评通过，不继承live通过 |

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
| `WP-KRETRIEVAL-DESIGN-01` | 目标文档修订与评审 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | IMPLEMENT | design-doc-review |
| `WP-KRETRIEVAL-IMPLEMENT-01` | 门禁后最小实施 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | NONLIVE | implement-from-detailed-design |
| `WP-KRETRIEVAL-NONLIVE-01` | 当前代码non-live验证 | 索引/语料修改、额外付费、历史覆盖、权限扩张 | Knowledge及直接测试/文档 | DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | UAT_01 §14；§20 | UAT | implement-from-detailed-design |
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
| `WP-KRETRIEVAL-DESIGN-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | §20 当前目标落点 | TEST-KFLOW-014、TEST-KRET-022、TEST-KEV-017；UAT_01 §14 | §20逐项证据 | Done |
| `WP-KRETRIEVAL-IMPLEMENT-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | §20 当前目标落点 | TEST-KFLOW-014、TEST-KRET-022、TEST-KEV-017；UAT_01 §14 | §20逐项证据 | Done |
| `WP-KRETRIEVAL-NONLIVE-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～018、DR-KRET-027、DR-KEV-026 | §20 当前目标落点 | TEST-KFLOW-014、TEST-KRET-022、TEST-KEV-017；UAT_01 §14 | §20逐项证据 | Done |
| `WP-KRETRIEVAL-UAT-01` | REQ-KQUALITY-001～004；DR-KFLOW-016～019、DR-KRET-027、DR-KEV-026 | §20 当前目标落点 | TEST-KFLOW-014、TEST-KRET-022、TEST-KEV-017；UAT_01 §14 | §20.14 run-03 failed；旧批不改判 | Deferred |
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
