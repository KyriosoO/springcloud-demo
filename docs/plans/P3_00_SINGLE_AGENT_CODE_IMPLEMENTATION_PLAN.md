# [P3_00] 单体 Agent 查询能力实施与收口计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | P3_00 |
| 当前版本 | v2.25 |
| 文档状态 | Reviewed |
| 更新时间 | 2026-08-28 |
| 适用范围 | 已完成且不得回退的 Business/Knowledge 功能基线，以及七项文档、测试可复现性与 Knowledge 效果收口 |
| 实施授权 | Ready 不等于实施授权；本任务已另行获得目标范围内代码实施、受控验证、文档同步及 Git 提交推送授权 |
| 归档来源 | [v1.34 已评审旧版](历史文档/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN_v1.34.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

v2.18 在不回退 Business 16 个已完成工作包的前提下，如实关闭 Knowledge 生产接线、non-live E2E、功能 UAT 和只读诊断；诊断只批准域目录 v2 与 Summary v3。v2.19 同步最小优化、candidate-05 非 live 冻结、全量回归和正式代码评审。v2.20 如实记录 candidate-05 唯一 live 运行、`partially_effective` 结论、消费后哈希和 runner 元数据绑定修复。v2.21 新增七项收口工作包，先纠正文档和正式 Python 测试入口，再基于 candidate-05 诊断、版本化优化和准备新候选；新的真实 outbound 继续受独立精确授权阻断。v2.22 关闭正式 Python 隔离入口：版本化 bootstrap 在一次性 venv 中安装固定构建后端和当前源码，冻结 host/preflight 14/14、全量 non-live 1419/1419 通过，27 项仅按设计 opt-in 跳过，candidate-04/05 历史哈希不变。v2.23 关闭 candidate-05 只读诊断：确认安全负例 summary 分母冲突、显式 gold issue 归因冲突和 mixed-domain 覆盖缺口，批准 Summary V4 与效果口径 v2，保持阈值、validator、权限、数据集/gold 和历史资产不变。v2.24 如实关闭 Summary V4 与效果口径 v2 的 non-live 实施：生产组合根唯一绑定 V4，功能、安全、效果口径、Spring E2E、全量回归、类型检查和历史哈希均通过。v2.25 关闭 candidate-06 非 live 冻结：固定 92 项资产、run/manifest/reference/78 次预算、历史哈希、首 outbound 消费和失败关闭；未生成正式授权或真实 outbound。

## 2. 目标、范围与计划原则

唯一目标链路为输入安全闸门/request-local slots → LLM filters QueryPlan → 两级 decoder → code/config validator 与 `value_ref` binder → 一个 ActionCandidate → 固定 Employee/Transaction Adapter → 服务最终授权与 ES/向量/SQL → 安全列表。输入闸门不得选择 domain/action 或生成 filters。目标动作只包括 `employee.search`、`employee.semantic_search`、`transaction.search`；员工地址固定 `contact_address → contactAddress`，`workBaseSi/workBaseAf` 不得启用。

原则：先公共合同与配置，再并行实现模型/Employee/Transaction；Employee 角色收紧与非 live 合同可同步准备；组合根切换等待全部 action 和 Employee guard；先 fake E2E 再受控 live，最后正式 UAT。禁止配置平台、复杂审批/证据流程、业务接口新增、数据库修改、真实调用未授权和历史证据复用。

## 3. 来源清单与当前基线

| 来源 | 当前版本 | 权威责任 | 状态 |
|---|---|---|---|
| [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v2.0 | 唯一链路、三动作、字段与验收 | Approved |
| [`L0_00`](../design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v2.5 | 系统边界和下位治理 | Approved |
| [`L1_00`](../design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v3.0 | Runtime/Model/Core、Knowledge 可选接线、组合根及完整意图边界 | Approved |
| [`L1_02`](../design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v2.5 | Business 公共边界、按 operator 区分文本策略、Adapter、结果卫生与 Employee 端点级角色转换 | Approved |
| [`L2_00_00`](../design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) | v1.2 | Spring 公共接入、Runtime 内部协议和当前生产启动入口状态 | Approved |
| [`L2_00_01`](../design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v2.2 | planning bridge、组合根和单动作 | Approved |
| [`L2_00_02`](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v2.3 | v4 模型安全 catalog、完整意图 Prompt 与不可表达组合 unsupported | Approved |
| [`L2_00_03`](../design/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) | v1.2 | 用户角色 Authority 的 Servlet/Reactive 统一转换及 Provider 消费 | Approved |
| [`L2_02_00`](../design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v2.5 | filters、统一配置、operator-specific 文本策略、动作超时、validator、slot、真实 coverage | Approved |
| [`L2_02_01`](../design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.5 | Employee search/semantic、partial hits、记录卫生、端点级 converter 与最终读取授权 | Approved |
| [`L2_02_02`](../design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.5 | Transaction Date/Decimal/page/sort、精确/模糊文本策略与生产 Spring UTC 响应合同 | Approved |
| [`L1_01`](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | v1.8 | Knowledge 能力、candidate-05 根因、Summary V4、效果口径 v2 与 candidate-06 冻结 | Approved |
| [`L2_01_00`](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | v1.9 | 单动作、域目录 v2、默认关闭接线、当前任务/Provider 装配 | Approved |
| [`L2_01_01`](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | v1.8 | typed retrieval、读取授权、RRF/rerank 和 client 生命周期 | Approved |
| [`L2_01_02`](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | v1.9 | Evidence/出域、Summary V4、效果口径 v2、诊断和 candidate-06 冻结 | Approved |
| [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | v1.19 | Business 35/35 追踪、当前测试计数与正式 Python 入口 | Reviewed |
| [`UAT_01`](UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | v1.8 | Knowledge 功能与效果验收 | Reviewed |

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
| `WP-BQ-COMPLETION-CLOSURE-04` | 当前 35 用例证据与实现收口 | [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) v1.14；当前代码 | Spring 严格 JSON、Spring→Runtime 当前链路、workBase/detail 历史隔离、Transaction preflight 环境、35 用例逐项追踪、全量回归与正式代码评审 | `WP-BQ-UAT-HANDOFF-02` | - | `uat_traceability.v2.json`、当前测试结果、代码评审和 Git 提交 | 当前 Spring/Runtime/Employee/Transaction 测试与全量 non-live 回归 | 保持 18 项真实证据集合不变；17 项仅按风险使用等价自动化 | Done |
| `WP-K-BASELINE-03` | Knowledge 设计与 UAT 基线 | `L1_00/L1_01`、三份 Knowledge L2、`UAT_01` | 当前事实核实、生产接线/功能效果分离、三轮内审及独立评审 | - | - | Approved/Reviewed 文档和无环 DAG | strict validators、分层/跨层评审 | 仅回退本次文档语义，不改历史证据 | Done |
| `WP-K-RUNTIME-WIRING-03` | Knowledge 默认关闭生产接线 | `L2_01_00 DR-KFLOW-011～014`、`L2_01_01 DR-KRET-011/012` | 启动开关、stub/fake 边界、任务/Provider/typed retrieval、同 Registry、owned clients 和关闭 | `WP-K-BASELINE-03` | `GATE-071` | 生产组合根、配置和生命周期测试 | `VAL-KFLOW-005`; `VAL-KRET-005` | 关闭开关即恢复 Business-only 对象图 | Done |
| `WP-K-SPRING-NONLIVE-E2E-03` | Spring→Runtime Knowledge non-live E2E | 三份 Knowledge L2、`UAT_01` | 当前生产对象图、fake Model/typed Provider、权限/失败/零调用/关闭矩阵 | `WP-K-RUNTIME-WIRING-03` | - | Spring/Python 16 场景 E2E 与有限调用计数 | `UAT-K-*` 功能矩阵 | 删除测试装配，不改生产合同 | Done |
| `WP-K-FUNCTIONAL-UAT-03` | Knowledge 功能 UAT | `UAT_01` 第 5～6 节 | 37 case 追踪、Java/Python/当前对象图证据和功能结论 | `WP-K-SPRING-NONLIVE-E2E-03` | `GATE-UAT-008` | `knowledge_uat_traceability.v1.json` 和执行结果 | 37/37 有实际/等价证据 | 保持 Effectiveness 独立 | Done |
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
| `WP-K-EFFECT-LIVE-06` | candidate-06 效果 UAT | `UAT_01` 效果验收合同 | 仅在精确绑定后执行一次并如实计算 effective/partial/ineffective/invalid | `WP-K-EFFECT-CANDIDATE-06-PREP` | `GATE-077` | append-only live result/evidence | Schema、预算、安全 Gate、人工 rubric、Q1～Q4 | 未获精确授权保持 Blocked；失败不补跑 | Blocked |
| `WP-SEVEN-ITEM-CLOSURE-06` | 七项最终验证与评审收口 | 本轮全部文档/代码/测试/UAT | 全量验证、代码评审、最终状态同步、原子提交推送 | `WP-K-EFFECT-LIVE-06` | - | 测试清单、评审结论、提交与推送记录 | Blocker/Major=0、工作树/远端明确 | 不改判效果或覆盖历史 | Blocked |

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
| `DEP-BQS-025` | `WP-BQ-UAT-HANDOFF-02` | `WP-BQ-COMPLETION-CLOSURE-04` | validation | 先冻结 18 项真实结果，再对未执行风险建立当前自动化追踪并完成正式收口 | `UAT_00` v1.14；`uat_traceability.v2.json` |
| `DEP-KQ-001` | `WP-K-BASELINE-03` | `WP-K-RUNTIME-WIRING-03` | contract | 生产接线只能依据评审通过的默认关闭与生命周期合同 | `L1_00` v3.0；`L2_01_00` v1.9；`L2_01_01` v1.8 |
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
| `DEP-KQ-015` | `WP-K-EFFECT-LIVE-06` | `WP-SEVEN-ITEM-CLOSURE-06` | validation | 效果结论形成后才能执行最终全量验证和状态收口 | append-only candidate-06 result/evidence |

DAG 无环；Business 与 Knowledge 工作包之间没有反向依赖。Knowledge 接线只向既有 Runtime 添加可选 Provider/任务/resources，不恢复或重开 Business 工作包。`GATE-072` 只控制已消费的 candidate-05，新的 candidate-06 必须依次通过 `GATE-073～077`；未获 `GATE-077` 精确绑定授权前，计划在非 live 准备后停止。

## 7. 阶段门禁

| 门禁 ID | 工作包 | 类型 | 控制动作 | 是否阻塞入口 | 关闭条件 | 证据/权威来源 | 责任方/外部提供方 | 最晚关闭阶段 | 验证者与方法 | 未关闭行为 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `GATE-067` | `WP-BQ-FILTER-CONTRACT-02` | closure | 新设计基线生效 | 否 | REQ/L0/L1/L2/P3/UAT 两阶段评审通过且版本一致 | 当前 Approved/Reviewed 文档、strict validators、跨层追踪与无环 DAG | 文档维护者 | 代码实施前 | 分层/跨层独立评审与 DAG 校验 | 不允许依据未评审设计实施 | Closed |
| `GATE-068` | `WP-EMP-ES-AUTH-02` | release_effective | Employee search/vector 端点级角色转换及最终守卫生效 | 否 | 两个既有 POST endpoint 显式绑定共享 converter，真实 JWT role claim 经完整 SecurityFilterChain 通过 ADMIN/VIEWER、拒绝矩阵及 detail/fallback 兼容 | `EmployeeEsSecurityIntegrationTest` 两入口真实 JWT role 矩阵；detail/matcher/controller 共 15 项定向通过，Employee 全模块 50 项中 30 通过、20 项 opt-in 跳过 | Employee 业务维护者/实施者 | 恢复 Employee 真实联调前 | Java 真实 Servlet SecurityFilterChain、两 endpoint 矩阵与既有调用方测试 | 禁止真实 Employee 联调及宣称最终授权已生效 | Closed |
| `GATE-069` | `WP-TXN-DATE-WIRE-COMPAT-03` | integration | Transaction Date 时区/精度及真实响应合同生效 | 否 | Python Date→HTTP→Jackson→Mapper instant/open interval/DB precision 成立；生产 Spring UTC 零毫秒 offset 字符串与 standalone 整秒 epoch 都通过严格 codec | 真实零模型 codec 成功解析 20/104；Java Spring JSON/安全链 6 项、Python 专项 244 项、全量 1424 项、非法日期拒绝与 `DATETIME(0)` 元数据 | Transaction 维护者/实施者 | 日期 live/UAT 前 | 双语言 production-config contract、strict bounds 与零模型实际 codec | 日期相关真实联调/UAT 不执行 | Closed |
| `GATE-070` | `WP-BQ-CONTROLLED-LIVE-02` | integration | 真实模型、业务服务和有限敏感数据调用 | 是 | 前置 non-live 包完成，GATE-068/069 关闭，semantic partial hits 与 Transaction 生产 Date 响应合同均已实现，环境/预算/授权/安全边界重新确认，历史 evidence 不可变 | controlled-run06 全新路径、五项 failure hash、Employee 9/20 和 Transaction 20/104 零模型生产 codec、Java 6 项、Python 1424 项及 strict mypy | 用户/业务维护者 | 下一次真实模型联调前 | frozen task/config/cases、真实安全链、预算、历史 hash 和零泄漏 preflight | controlled live 保持 Blocked；只允许独立零模型只读诊断 | Closed |
| `GATE-UAT-007` | `WP-BQ-UAT-HANDOFF-02` | closure | 正式四阶段 UAT | 是 | 18 个真实模型/业务场景保持不可变，剩余 17 个确定性风险由当前生产组合根、Spring 安全链或跨语言合同逐项验证，35 个计划用例均有唯一追踪且不外推真实执行范围 | run03 SHA-256=`b49832426147dc14d56e571fea11b0345e16602d8cb5e2ea2eeb3dacb3326dd8`；`uat_traceability.v2.json`；Spring→Runtime、Java 安全链及 Python/Java 合同测试 | 用户/UAT 执行者 | 阶段最终收口前 | 严格校验 35 个 case、18/17 证据分类、引用符号、历史 hash、零调用与权限边界 | 任一 case 无实际或等价证据则恢复 Open，不得靠旧 detail/stub 结果关闭 | Closed |
| `GATE-071` | `WP-K-RUNTIME-WIRING-03` | closure | Knowledge 生产接线设计生效 | 是 | L1/L2/P3/UAT_01 语义一致，三轮内审与独立评审无 S0/S1/未处理 S2 | 当前文档、strict validators、跨层追踪和 DAG | 文档维护者 | 生产接线前 | 分层/跨层设计评审 | 不允许依据未评审语义接线 | Closed |
| `GATE-UAT-008` | `WP-K-FUNCTIONAL-UAT-03` | closure | Knowledge 功能验收 | 是 | UAT_01 37 个功能 case 均有实际/等价证据，关键 Spring→Runtime 16 场景 E2E 实际执行，权限/出域/失败/零调用成立 | `knowledge_uat_traceability.v1.json`、Spring/Python 测试与有限 evidence | 实施者/UAT 评审者 | 效果诊断前 | Schema、引用、调用计数和回归验证 | 任一当前证据失效则恢复 Open | Closed |
| `GATE-072` | `WP-K-EFFECT-LIVE-05` | integration | 真实付费 Knowledge 效果 UAT | 是 | frozen HEAD=`63bc30b...2efa`、manifest=`41997c6...e278c`、26 case 双变体、预算78完成唯一执行；安全 Gate 通过，结论 `partially_effective` | result SHA-256=`a6de81f...36eb`；44/44 terminal、rewrite22、summary22、retry/core answer=0；post-consumption tests | 用户 | 首个模型 outbound 前 | clean/frozen source、预算、历史 hash、敏感扫描 | 禁止重跑、补跑、续跑或改判 | Closed |
| `GATE-073` | `WP-DOC-CONSISTENCY-06` | closure | 七项文档纠偏生效 | 否 | 3 轮内审及独立分层/跨层评审通过，版本/状态/DAG/实现事实一致 | strict design/plan validators、链接和跨层差异矩阵 | 文档维护者 | 测试入口或效果代码修改前 | 独立评审无 S0/S1/未处理 S2 | 受影响代码实施保持 Blocked | Closed |
| `GATE-074` | `WP-PY-REGRESSION-REPRO-06` | closure | Python 正式全量入口生效 | 否 | 版本化隔离 bootstrap 显式安装当前源码；14 项 host/preflight 与全量 non-live 通过且历史 hash 不变 | `scripts/run-nonlive-regression.ps1`：Python 3.12.4、host 14/14、全量 1419 passed/27 opt-in skipped/0 failed；strict mypy 448 文件；candidate-04/05 17 项哈希复核 | 实施者 | candidate-05 根因复核前 | 从干净源码树重复执行 | 效果优化保持 Blocked | Closed |
| `GATE-075` | `WP-K-EFFECT-OPT-06` | closure | Summary V4 与效果口径 v2 生效 | 否 | candidate-05 诊断和设计评审通过；Summary V4 多要点/多域覆盖、v2 分母/质量 Gate、non-live、安全、E2E、类型和历史回归全部通过 | Knowledge 260 passed/6 opt-in skipped；正式全量 1427 passed/27 skipped；Spring E2E 1 passed；strict mypy 452 文件；compileall、历史哈希及代码评审通过 | 实施者/评审者 | 新候选冻结前 | 阈值/validator/权限/历史反证 | candidate-06 准备保持 Blocked | Closed |
| `GATE-076` | `WP-K-EFFECT-CANDIDATE-06-PREP` | closure | candidate-06 非 live 冻结 | 否 | run=`knowledge-p5-live-v3-20260828-candidate-06`、manifest=`7f54ddff...cc51b8`、reference=`P3_00:GATE-077`、预算78、92项资产与失败关闭已冻结 | candidate-06 preparation/contracts/history、唯一未跟踪授权记录及 HEAD/manifest 强绑定边界；正式全量1442 passed/27 skipped；strict mypy 454文件；compileall、PowerShell AST、历史 hash | 实施者 | 真实授权申请前 | 首 outbound、预算、retry/resume=0 | 未创建正式 authorization，未读取密钥或产生 outbound | Closed |
| `GATE-077` | `WP-K-EFFECT-LIVE-06` | integration | candidate-06 一次性真实效果 UAT | 是 | 用户精确绑定 frozen HEAD、run ID、manifest SHA-256、authorization reference 和最大调用数 | 后续一次性明确授权 | 用户 | 首个模型 outbound 前 | clean source、依赖、预算、历史 hash、敏感扫描 | 保持 Blocked，禁止推断授权 | Open |
| `GATE-078` | `WP-SEVEN-ITEM-CLOSURE-06` | closure | 七项最终收口 | 否 | candidate-06 结果如实记录；全量 Python/Java/设计/代码评审通过；状态、提交、远端一致 | 最终测试清单、评审结论、commit/push | 实施者/评审者 | 最终完成声明前 | Blocker/Major=0，工作树/远端复核 | 不宣称七项目标完成 | Open |

## 8. 外部资源与事实

| 资源 ID | 工作包 | 资源/事实 | 提供方 | 开始准备 | 必须完成 | 产物/引用 | 缺失影响 |
|---|---|---|---|---|---|---|---|
| `EXT-BQS-001` | `WP-EMP-ES-AUTH-02` | 现有 search/vector 调用方清单和 ADMIN/VIEWER 兼容性 | Employee 服务维护者 | 工作包开始 | 角色守卫生效前 | 调用方兼容结论与 Java tests | `GATE-068` 保持 Open |
| `EXT-BQS-002` | `WP-TXN-SEARCH-EXT-02` | Java Date/Jackson、Asia/Shanghai 和生产 TRANS_DATE precision 合同 | Transaction 服务维护者 | Date fake 合同阶段 | 日期真实集成前 | 不含业务数据的 timezone/precision evidence | `GATE-069` 保持 Open |
| `EXT-BQS-003` | `WP-BQ-CONTROLLED-LIVE-02` | 模型凭证、业务服务、授权用户与有限安全测试输入 | 用户/维护者 | 全部 non-live 通过后 | `GATE-070` 关闭前 | 内存凭证和有限调用预算，不记录敏感值 | 真实联调不执行 |
| `EXT-BQS-004` | `WP-BQ-UAT-HANDOFF-02` | 联系地址真实可检索样本与 Transaction 日期/金额数据 | 业务维护者 | controlled live 之后 | 首个 UAT 前 | 非敏感准备状态和 UAT checklist | 正式 UAT 不执行 |
| `EXT-KQ-001` | `WP-K-RUNTIME-WIRING-03` | es-query-service typed endpoint、Profile 配置、8908/8909 本地服务 | 当前仓库/维护者 | 接线前 | non-live/只读契约验证 | 固定配置与 existing tests | 功能 UAT 只允许 fake/contract 证据，不执行真实效果 |
| `EXT-KQ-002` | `WP-K-EFFECT-LIVE-05` | 精确模型授权、冻结索引/Profile/数据集和人工 rubric | 用户/维护者 | candidate-05 准备完成后 | `GATE-072` 关闭前 | 一次性 authorization、44 次 paid journal 与 append-only result/evidence | 已完成，Effectiveness=`Partially effective` |
| `EXT-KQ-003` | `WP-K-EFFECT-LIVE-06` | candidate-06 精确模型授权及冻结运行依赖 | 用户/维护者 | `GATE-076` 关闭后 | `GATE-077` 关闭前 | frozen HEAD/run/manifest/reference/预算的一次性授权 | 未提供前只完成 non-live 准备 |

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
| 31 | `WP-K-EFFECT-LIVE-06` | Blocked | `WP-K-EFFECT-CANDIDATE-06-PREP`; `GATE-077` | 等待用户精确绑定一次性授权 |
| 32 | `WP-SEVEN-ITEM-CLOSURE-06` | Blocked | `WP-K-EFFECT-LIVE-06` | live 结论形成后再做全量验证、评审、状态和 Git 收口 |

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
| `WP-K-EFFECT-LIVE-06` | 精确授权后执行一次冻结效果 UAT | 未绑定授权、重试、补跑、改判 | append-only candidate-06 assets | `UAT_01` 效果合同 | P5 Schema、安全 Gate、Q1～Q4/rubric | `GATE-078` | implement-from-detailed-design |
| `WP-SEVEN-ITEM-CLOSURE-06` | 全量验证、正式代码评审、状态与 Git 收口 | 隐瞒失败、提前关闭 live 或覆盖历史 | 当前目标代码/测试/文档 | 本轮全部 DR/VAL/UAT | review-and-fix、全量回归、git checks | 本目标完成 | code-review-against-docs |

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
| `WP-K-EFFECT-LIVE-06` | `UAT_01` 效果合同 | append-only live runner/result | frozen P5、Q1～Q4、安全 Gate | `GATE-077` | Blocked |
| `WP-SEVEN-ITEM-CLOSURE-06` | 本轮全部设计/UAT | review fixes/state sync | 全量 Python/Java/文档 | `GATE-078` | Blocked |

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

## 13. 当前评审与状态规则

工作包状态根据直接依赖和入口门禁实时计算，不能把旧 detail/flat arguments 的历史 Done 或 candidate evidence 继承为新包完成；每个包需独立测试、代码对照设计评审与授权后状态同步。

本次 Knowledge 正式代码对照设计评审覆盖生产对象图、默认关闭惰性、Capability/任务唯一性、读取授权、三层出域、typed retrieval、失败优先级、取消/关闭、Business 隔离、历史不可变与 candidate-05 消费后证据。首轮发现 live evidence 的 `workPackageId` 仍硬编码旧值；历史 evidence 保持不可变，runner 已改为从 manifest 取值并补充反证。复评结论：Blocker=0、Major=0、未处理 Minor=0，Passed。

`WP-PY-REGRESSION-REPRO-06` 代码对照设计评审覆盖隔离安装语义、冻结 host 错误分类、环境变量隔离、临时目录所有权、清理路径、历史哈希和生产依赖边界。版本化入口只安装 `pyproject.toml` 已声明的固定构建后端和当前源码，不修改 host/manifest/evidence；复核结论：Blocker=0、Major=0、Minor=0，Passed。

正式 Python 入口为 `agent-runtime/scripts/run-nonlive-regression.ps1`：Python 3.12.4、一次性 venv、`setuptools==80.9.0`、无依赖安装当前源码；先运行冻结 Transaction host/preflight 14/14，再运行全量 non-live `1419 passed, 27 opt-in skipped, 0 failed`。脚本清除进程级 `PYTHONPATH` 并在路径归属校验后清理临时环境；`mypy src tests` 覆盖 448 个文件、`compileall src tests` 通过。candidate-04/05 的 17 项历史资产哈希与冻结基线一致，故 `GATE-074` 已关闭。普通未安装源码树不再作为权威全量入口。

`WP-K-EFFECT-DIAG-06` 只读绑定 candidate-05 result SHA-256=`a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb`。诊断重算证明：4 个安全负例的正确零 Summary 调用使历史 completion 最高只能为 22/26；1 个 answerable `gold_issue` 被错误归因到模型质量；3 个 mixed case 因 coverage 不足不 useful，其中 2 个在 rerank recall=1.0 后仍只采用一条证据。由此只批准 Summary V4 和带 90% 数据质量 Gate 的效果口径 v2；RRF/rerank/Profile、validator、dataset/gold、权限、出域策略和阈值均不变。诊断测试 2/2 通过，candidate-05 manifest/authorization/result 哈希一致。对应 L1/L2/P3/UAT 三轮内审及独立跨层评审已通过，无 S0/S1/未处理 S2。

`WP-K-EFFECT-OPT-06` 已实现独立 `KnowledgeSummaryTaskV4` 并把显式启用的生产组合根唯一切换为 V4；V1～V3 及历史 manifest/evidence 保持不可变。效果口径 v2 仅从摘要完成率分母排除正确零调用的 `security_negative`，普通 no-result/失败仍计入分母；仅显式 `gold_issue` 从质量分母排除，且有效质量样本不足原 answerable 集合的 90% 时整次运行 `invalid_run`。定向合同、组合根和指标测试通过，Knowledge 260 passed/6 opt-in skipped，正式 Python 全量 1427 passed/27 opt-in skipped，Spring→Runtime Knowledge E2E 1 passed，strict mypy 452 文件、compileall、历史哈希和代码对照设计复核均通过；`GATE-075` Closed。

`WP-K-EFFECT-CANDIDATE-06-PREP` 已冻结 run=`knowledge-p5-live-v3-20260828-candidate-06`、manifest SHA-256=`7f54ddff600726d364edee6f7c6939d99c52aa5b533ac309d98887b6e8cc51b8`、authorization reference=`P3_00:GATE-077` 和最多 78 次付费请求。manifest 包含 92 项排序资产，绑定 dataset/provenance、Rewrite V1、Summary V4、效果口径 v2、六项 Profile/索引快照、策略及 candidate-01～05 历史哈希。代码评审发现并修复正式 authorization 与 clean HEAD 的循环及 HEAD 绑定缺口：运行时只允许该严格授权记录作为唯一未跟踪文件，授权记录、launcher 参数、实际 HEAD 和 manifest SHA-256 必须一致，任何其他工作树变化继续失败关闭。contracts/preparation/history、正式 Python 入口 host/preflight 14/14、全量 1442 passed/27 opt-in skipped/0 failed，strict mypy 454 文件、compileall 与 PowerShell AST 通过；当前未创建正式 authorization、未读取密钥、未启动 live 或产生 outbound，`GATE-076` Closed。

## 14. 当前结论

总计 32 个工作包：既有 Business 16 个、Knowledge 9 个均为 Done；本轮新增 7 个收口包中，文档纠偏、Python 正式入口、candidate-05 诊断、最小优化和 candidate-06 非 live 准备已 Done，live 与最终收口按依赖 Blocked。`GATE-071～076` 与 `GATE-UAT-008` 已关闭；`GATE-077～078` 保持 Open。candidate-05 结论保持 `partially_effective`，Business v3/v4/run03 与 Knowledge candidate-01～05 历史均保持不可变。

## 15. 后续实施建议

Employee/Transaction 保持已完成。文档纠偏与评审、Python 正式入口、candidate-05 只读诊断、最小优化和 candidate-06 非 live 冻结均已完成；当前必须暂停并输出 `GATE-077` 精确授权模板。不得重用 `GATE-072`、读取密钥或产生真实 outbound。
