# [P3_00] Employee/Transaction 列表查询与语义搜索实施计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | P3_00 |
| 当前版本 | v2.8 |
| 文档状态 | Reviewed |
| 更新时间 | 2026-08-25 |
| 适用范围 | Business filters 合同、统一字段配置、三动作 Adapter、最终授权、组合根、联调与 UAT 交接 |
| 实施授权 | Ready 不等于实施授权；本任务已另行获得目标范围内代码实施、受控验证、文档同步及 Git 提交推送授权 |
| 归档来源 | [v1.34 已评审旧版](历史文档/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN_v1.34.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 目标、范围与计划原则

唯一目标链路为输入安全闸门/request-local slots → LLM filters QueryPlan → 两级 decoder → code/config validator 与 `value_ref` binder → 一个 ActionCandidate → 固定 Employee/Transaction Adapter → 服务最终授权与 ES/向量/SQL → 安全列表。输入闸门不得选择 domain/action 或生成 filters。目标动作只包括 `employee.search`、`employee.semantic_search`、`transaction.search`；员工地址固定 `contact_address → contactAddress`，`workBaseSi/workBaseAf` 不得启用。

原则：先公共合同与配置，再并行实现模型/Employee/Transaction；Employee 角色收紧与非 live 合同可同步准备；组合根切换等待全部 action 和 Employee guard；先 fake E2E 再受控 live，最后正式 UAT。禁止配置平台、复杂审批/证据流程、业务接口新增、数据库修改、真实调用未授权和历史证据复用。

## 3. 来源清单与当前基线

| 来源 | 当前版本 | 权威责任 | 状态 |
|---|---|---|---|
| [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) | v2.0 | 唯一链路、三动作、字段与验收 | Approved |
| [`L0_00`](../design/L0_00_SINGLE_AGENT_ARCHITECTURE.md) | v2.0 | 系统边界和下位治理 | Approved |
| [`L1_00`](../design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | v2.0 | Runtime/Model/Core/组合根 | Approved |
| [`L1_02`](../design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v2.2 | Business 公共边界、Adapter、结果卫生与 Employee 端点级角色转换 | Approved |
| [`L2_00_01`](../design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v2.0 | planning bridge、组合根和单动作 | Approved |
| [`L2_00_02`](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v2.0 | v3 模型安全 catalog 和 Prompt | Approved |
| [`L2_02_00`](../design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v2.2 | filters、统一配置、独立动作超时、validator、slot、真实 coverage | Approved |
| [`L2_02_01`](../design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.3 | Employee search/semantic、partial hits、记录卫生、端点级 converter 与最终读取授权 | Approved |
| [`L2_02_02`](../design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.2 | Transaction Date/Decimal/page/sort 与生产 Spring UTC 响应合同 | Approved |

Verified existing：Business filters plan、统一字段 JSON、v3 model catalog、Employee search/semantic Adapter、Employee Controller 最终读取守卫与 endpoint-scoped 共享 JWT role converter、真实 Servlet 过滤链角色/兼容矩阵、Transaction Date/Decimal/完整分页 Adapter、三动作生产组合根、旧目标入口退役核实、三动作完整 fake E2E、现有三个业务接口、隔离 Employee→es-query-service 只读联通、semantic 独立 10000ms action budget，以及现有向量 partial page/历史无姓名记录的 bounded codec/normalizer 合同。Employee 零模型生产 codec 返回 9/20 安全记录；Transaction production Spring UTC 零毫秒字符串/standalone epoch 严格双形态已实施，真实 Spring JSON 6/6、Python 专项 244/244、全量 1424/1424 和真实零模型 20/104 生产 codec 通过。新配置 SHA-256=`47077b3783e6fc7179c22a53aab37f714b2c1d278ad96d925a614b6406f173ba`，独立 live manifest SHA-256=`3da2d9f250253b142e43f690d5dc4e7ff8cf9bfe57f2e52ff6d248ec2c8d75d2`。Not implemented：成功受控 live 及正式 UAT 证据。前四次失败 SHA-256 分别为 `fdc37b16e45d58733ede0a468e90b4db5242de8c84bcda7cca18ef07bd368607`、`121814993c53c2f0b4910bb5efe8b35bfe3da65dc395bd3270aa1c57b6eb5a08`、`737d76c296d7803618f74c370a4478b73e2a65a3bbec66ffee3d2d577b4a467d`、`3582693a77b4b791eabdc7253778936ac76ae7a779c09fad1edb3057bc7c14de`；第五次 SHA-256=`e028ae64eb97ca56b4e1ff09ac04423317536d20fdd9d1792e652cc9acfe2c4e` 已证明 Employee 两动作分别返回 20/9 条，旧 Transaction 日期问题现已完成真实 codec 修复。五项失败和原 live manifest 字节保持不变；下一次联调只使用独立 controlled-run06 结果。

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
| `WP-BQ-CONTROLLED-LIVE-02` | 受控模型与业务联调 | `REQ_00`; `L2_00_02`; 两域 L2 | 有限固定场景、敏感值内存化、五次失败历史不可变 | `WP-BQ-NONLIVE-E2E-02`, `WP-EMP-DETAIL-RETIRE-02`, `WP-EMP-ES-AUTH-02`, `WP-TXN-DATE-WIRE-COMPAT-03` | `GATE-070` | 新的真实三动作 finite evidence，不覆盖既有失败证据 | 一计划/一业务调用与真实权限矩阵 | 失败即停止，先修复根因，不复用失败结果路径 | Ready |
| `WP-BQ-UAT-HANDOFF-02` | 正式 UAT 环境与交接 | [`UAT_00`](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | UAT 前置、真实数据可用性、固定用例与结论 | `WP-BQ-CONTROLLED-LIVE-02` | `GATE-UAT-007` | UAT 准入记录及阶段结论 | UAT 公共/Employee/Transaction/收口 | 不把旧 evidence 冒充本版 UAT | Blocked |

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

DAG 无环；既有 `WP-TXN-SEARCH-EXT-02` 的请求、Decimal/page 和 standalone epoch 证据保持 Done，新增 `WP-TXN-DATE-WIRE-COMPAT-03` 仅承接真实 Spring 响应差异，避免回退已被 Runtime 依赖的历史工作包。该兼容包在 `GATE-069/070` Open 时实施，完成后再恢复 controlled live，不构成门禁依赖环；后置 live/UAT gate 不反向阻塞独立 non-live 工作。

## 7. 阶段门禁

| 门禁 ID | 工作包 | 类型 | 控制动作 | 是否阻塞入口 | 关闭条件 | 证据/权威来源 | 责任方/外部提供方 | 最晚关闭阶段 | 验证者与方法 | 未关闭行为 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `GATE-067` | `WP-BQ-FILTER-CONTRACT-02` | closure | 新设计基线生效 | 否 | REQ/L0/L1/L2/P3/UAT 两阶段评审通过且版本一致 | 当前 Approved/Reviewed 文档、strict validators、跨层追踪与无环 DAG | 文档维护者 | 代码实施前 | 分层/跨层独立评审与 DAG 校验 | 不允许依据未评审设计实施 | Closed |
| `GATE-068` | `WP-EMP-ES-AUTH-02` | release_effective | Employee search/vector 端点级角色转换及最终守卫生效 | 否 | 两个既有 POST endpoint 显式绑定共享 converter，真实 JWT role claim 经完整 SecurityFilterChain 通过 ADMIN/VIEWER、拒绝矩阵及 detail/fallback 兼容 | `EmployeeEsSecurityIntegrationTest` 两入口真实 JWT role 矩阵；detail/matcher/controller 共 15 项定向通过，Employee 全模块 50 项中 30 通过、20 项 opt-in 跳过 | Employee 业务维护者/实施者 | 恢复 Employee 真实联调前 | Java 真实 Servlet SecurityFilterChain、两 endpoint 矩阵与既有调用方测试 | 禁止真实 Employee 联调及宣称最终授权已生效 | Closed |
| `GATE-069` | `WP-TXN-DATE-WIRE-COMPAT-03` | integration | Transaction Date 时区/精度及真实响应合同生效 | 否 | Python Date→HTTP→Jackson→Mapper instant/open interval/DB precision 成立；生产 Spring UTC 零毫秒 offset 字符串与 standalone 整秒 epoch 都通过严格 codec | 真实零模型 codec 成功解析 20/104；Java Spring JSON/安全链 6 项、Python 专项 244 项、全量 1424 项、非法日期拒绝与 `DATETIME(0)` 元数据 | Transaction 维护者/实施者 | 日期 live/UAT 前 | 双语言 production-config contract、strict bounds 与零模型实际 codec | 日期相关真实联调/UAT 不执行 | Closed |
| `GATE-070` | `WP-BQ-CONTROLLED-LIVE-02` | integration | 真实模型、业务服务和有限敏感数据调用 | 是 | 前置 non-live 包完成，GATE-068/069 关闭，semantic partial hits 与 Transaction 生产 Date 响应合同均已实现，环境/预算/授权/安全边界重新确认，历史 evidence 不可变 | controlled-run06 全新路径、五项 failure hash、Employee 9/20 和 Transaction 20/104 零模型生产 codec、Java 6 项、Python 1424 项及 strict mypy | 用户/业务维护者 | 下一次真实模型联调前 | frozen task/config/cases、真实安全链、预算、历史 hash 和零泄漏 preflight | controlled live 保持 Blocked；只允许独立零模型只读诊断 | Closed |
| `GATE-UAT-007` | `WP-BQ-UAT-HANDOFF-02` | closure | 正式四阶段 UAT | 是 | 前 12 个工作包与 controlled live 完成，UAT 环境/代表性业务数据就绪并获得明确授权；不要求 UAT 工作包自身预先完成 | UAT_00 准入和本版 live evidence | 用户/UAT 执行者 | 首个正式 UAT 用例前 | UAT checklist、调用预算及 gate→UAT 无环性复核 | 正式 UAT 保持 Blocked | Open |

## 8. 外部资源与事实

| 资源 ID | 工作包 | 资源/事实 | 提供方 | 开始准备 | 必须完成 | 产物/引用 | 缺失影响 |
|---|---|---|---|---|---|---|---|
| `EXT-BQS-001` | `WP-EMP-ES-AUTH-02` | 现有 search/vector 调用方清单和 ADMIN/VIEWER 兼容性 | Employee 服务维护者 | 工作包开始 | 角色守卫生效前 | 调用方兼容结论与 Java tests | `GATE-068` 保持 Open |
| `EXT-BQS-002` | `WP-TXN-SEARCH-EXT-02` | Java Date/Jackson、Asia/Shanghai 和生产 TRANS_DATE precision 合同 | Transaction 服务维护者 | Date fake 合同阶段 | 日期真实集成前 | 不含业务数据的 timezone/precision evidence | `GATE-069` 保持 Open |
| `EXT-BQS-003` | `WP-BQ-CONTROLLED-LIVE-02` | 模型凭证、业务服务、授权用户与有限安全测试输入 | 用户/维护者 | 全部 non-live 通过后 | `GATE-070` 关闭前 | 内存凭证和有限调用预算，不记录敏感值 | 真实联调不执行 |
| `EXT-BQS-004` | `WP-BQ-UAT-HANDOFF-02` | 联系地址真实可检索样本与 Transaction 日期/金额数据 | 业务维护者 | controlled live 之后 | 首个 UAT 前 | 非敏感准备状态和 UAT checklist | 正式 UAT 不执行 |

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
| 12 | `WP-BQ-CONTROLLED-LIVE-02` | Ready | - | Employee 两动作真实 20/9，Transaction 20/104 生产 codec 通过；新 run06 未消费 |
| 13 | `WP-BQ-UAT-HANDOFF-02` | Blocked | controlled live 与 `GATE-UAT-007` | UAT 不能复用旧 detail 证据 |

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
| `WP-BQ-UAT-HANDOFF-02` | 授权后执行四阶段 UAT | 旧 detail 证据替代新用例 | UAT 用例及阶段结论 | `REQ-BQS-012` | UAT 验收矩阵 | 正式验收结论 | code-review-against-docs |

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
| `WP-BQ-CONTROLLED-LIVE-02` | `DR-MODEL-104`; `DR-BQCOM-107/108`; `DR-EMP-105/107/108`; `DR-TXN-102/105` | action 独立超时、partial page、生产 Date codec、受控 runner、五次不可变失败及新的独立有限结果 | 有限三动作 live 矩阵 | `GATE-069/070` 已关闭 | Ready |
| `WP-BQ-UAT-HANDOFF-02` | `REQ-BQS-012` | UAT 环境与用例清单 | UAT 四阶段 | `GATE-UAT-007` 关闭证据 | Blocked |

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

## 13. 当前评审与状态规则

工作包状态根据直接依赖和入口门禁实时计算，不能把旧 detail/flat arguments 的历史 Done 或 candidate evidence 继承为新包完成；每个包需独立测试、代码对照设计评审与授权后状态同步。

## 14. 当前结论

总计 13 个工作包、17 条直接依赖：Done 11 个，Ready 1 个，Blocked 1 个。Transaction 生产 UTC `.000+00:00` 与历史 epoch 双形态严格响应合同已实施，真实 Spring 安全链 JSON 6 项、Python Transaction 244 项、全量 1424 项和实际零模型 20/104 codec 通过；Employee 两动作已分别真实返回 20/9。第五项失败 SHA-256=`e028ae64eb97ca56b4e1ff09ac04423317536d20fdd9d1792e652cc9acfe2c4e` 与前四项、旧 manifest 均不可变；下一次使用 controlled-run06 新结果路径。`GATE-067/068/069/070` Closed；`GATE-UAT-007` Open。成功 controlled live 和正式 UAT 尚未完成。

## 15. 后续实施建议

使用已冻结配置 snapshot/manifest 和独立 controlled-run06 执行真实联调，保护五项失败结果；真实三动作及权限矩阵通过后，按证据开放正式 UAT。不得新建业务接口、放宽日期语法或扩大权限。
