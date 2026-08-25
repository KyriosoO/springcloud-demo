# [P3_00] Employee/Transaction 列表查询与语义搜索实施计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | P3_00 |
| 当前版本 | v2.0 |
| 文档状态 | Reviewed |
| 更新时间 | 2026-08-25 |
| 适用范围 | Business filters 合同、统一字段配置、三动作 Adapter、最终授权、组合根、联调与 UAT 交接 |
| 实施授权 | 已获得目标范围内代码实施、受控验证、文档同步及 Git 提交推送授权 |
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
| [`L1_02`](../design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) | v2.0 | Business 公共边界和 Adapter | Approved |
| [`L2_00_01`](../design/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | v2.0 | planning bridge、组合根和单动作 | Approved |
| [`L2_00_02`](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | v2.0 | v3 模型安全 catalog 和 Prompt | Approved |
| [`L2_02_00`](../design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) | v2.0 | filters、统一配置、validator、slot、projection | Approved |
| [`L2_02_01`](../design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.0 | Employee search/semantic/role guard | Approved |
| [`L2_02_02`](../design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) | v2.0 | Transaction Date/Decimal/page/sort | Approved |

Verified existing：旧 detail、有限 Transaction、Business protected slot、Model transport、现有三个业务接口和 Transaction 最终读取授权。Not implemented：filters plan、统一 JSON、v3 catalog、Employee search/semantic Adapter、Employee ES role guard、Transaction Date/完整分页、新组合根、fake/live/UAT 证据。

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
| `WP-EMP-SEMANTIC-ADAPTER-02` | Employee 语义搜索 | `L2_02_01 DR-EMP-102/104` | queryText/k/profile、单接口语义列表 | `WP-BQ-FIELD-CONFIG-02` | - | semantic definition/codec 与 fake tests | `VAL-EMP-101/103` | 禁用新 action，不建立普通搜索 fallback | Ready |
| `WP-EMP-ES-AUTH-02` | Employee ES 最终读取授权 | `L2_02_01 DR-EMP-105` | 调用方兼容核查、两入口 requireEmployeeRead、角色矩阵 | - | - | Java guard/controller/security 测试 | `VAL-EMP-102` | 未确认兼容前不启用授权变更 | Done |
| `WP-TXN-SEARCH-EXT-02` | Transaction Date/金额/分页扩展 | `L2_02_02 DR-TXN-101～105` | 四字段 operator、Date/Decimal、page/sort、稳定列表 | `WP-BQ-FIELD-CONFIG-02` | - | 扩展 Transaction Adapter 和 Java contract tests | `VAL-TXN-101/102/103` | 关闭新字段，不修改 Java DTO/SQL | Ready |
| `WP-BQ-RUNTIME-CUTOVER-02` | 三动作生产组合根切换 | `L2_00_01 DR-CORE-101～104` | model/catalog/snapshot/三 action/Registry 单一路径 | `WP-BQ-MODEL-CATALOG-02`, `WP-EMP-SEARCH-ADAPTER-02`, `WP-EMP-SEMANTIC-ADAPTER-02`, `WP-TXN-SEARCH-EXT-02`, `WP-EMP-ES-AUTH-02` | - | 组合根和 Core fake 契约 | `VAL-CORE-101/102` | 关闭新组合根，不恢复 Resolver | Blocked |
| `WP-EMP-DETAIL-RETIRE-02` | Employee detail 退役核实 | `L2_02_01 DR-EMP-106` | 调用方/兼容/历史证据核查，目标生产路径移除 | `WP-BQ-RUNTIME-CUTOVER-02` | - | 调用方清单和可达性/历史回归 | `TEST-EMP-107` | 保留冻结历史与仍有调用方的共享类型 | Blocked |
| `WP-BQ-NONLIVE-E2E-02` | 三动作 non-live E2E | `L2_00_01`; `L2_02_00`; `L2_02_01`; `L2_02_02` | fake model/三个 fake endpoint/失败零调用 | `WP-BQ-RUNTIME-CUTOVER-02` | - | non-live E2E 及跨域/Knowledge 回归 | 三动作、权限 fake、contract、mypy | 移除测试装配，不改历史 evidence | Blocked |
| `WP-BQ-CONTROLLED-LIVE-02` | 受控模型与业务联调 | `REQ_00`; `L2_00_02`; 两域 L2 | 单次授权、有限固定场景、敏感值内存化 | `WP-BQ-NONLIVE-E2E-02`, `WP-EMP-DETAIL-RETIRE-02` | `GATE-070` | 真实三动作 finite evidence | 一计划/一业务调用与权限矩阵 | 失败即停止，不补跑或复用历史授权 | Blocked |
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
| `DEP-BQS-010` | `WP-EMP-ES-AUTH-02` | `WP-BQ-RUNTIME-CUTOVER-02` | security | 生产 Employee 路径启用前必须完成服务最终授权 | `DR-EMP-105` |
| `DEP-BQS-011` | `WP-BQ-RUNTIME-CUTOVER-02` | `WP-EMP-DETAIL-RETIRE-02` | rollback | 旧动作退役前先建立替代 search 组合根 | `DR-EMP-106` |
| `DEP-BQS-012` | `WP-BQ-RUNTIME-CUTOVER-02` | `WP-BQ-NONLIVE-E2E-02` | runtime | E2E 需要三动作唯一 production 对象图 | `DR-CORE-102` |
| `DEP-BQS-013` | `WP-EMP-DETAIL-RETIRE-02` | `WP-BQ-CONTROLLED-LIVE-02` | validation | live 前确认旧目标入口不可达及历史兼容 | `TEST-EMP-107` |
| `DEP-BQS-014` | `WP-BQ-NONLIVE-E2E-02` | `WP-BQ-CONTROLLED-LIVE-02` | validation | 真实调用前完成所有 fake 成功/拒绝/零调用 | `VAL-BQCOM-102` |
| `DEP-BQS-015` | `WP-BQ-CONTROLLED-LIVE-02` | `WP-BQ-UAT-HANDOFF-02` | validation | 正式 UAT 前必须获得本版真实链路证据 | `REQ-BQS-012` |

DAG 无环；Employee guard 调查与公共合同可并行，三个 Adapter/Model 在配置完成后可并行。`WP-EMP-ES-AUTH-02` 只有 `GATE-068` 关闭后才能标记 Done；`WP-TXN-SEARCH-EXT-02` 只有 Date 跨语言合同和 `GATE-069` 关闭后才能标记 Done。两项 gate 不阻止各自 non-live 开始，但防止未验证的授权/日期能力进入后续生产组合根。后置 live/UAT gate 不反向阻塞独立 non-live 工作。

## 7. 阶段门禁

| 门禁 ID | 工作包 | 类型 | 控制动作 | 是否阻塞入口 | 关闭条件 | 证据/权威来源 | 责任方/外部提供方 | 最晚关闭阶段 | 验证者与方法 | 未关闭行为 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `GATE-067` | `WP-BQ-FILTER-CONTRACT-02` | closure | 新设计基线生效 | 否 | REQ/L0/L1/L2/P3/UAT 两阶段评审通过且版本一致 | 当前 Approved/Reviewed 文档、strict validators、跨层追踪与无环 DAG | 文档维护者 | 代码实施前 | 分层/跨层独立评审与 DAG 校验 | 不允许依据未评审设计实施 | Closed |
| `GATE-068` | `WP-EMP-ES-AUTH-02` | release_effective | Employee search/vector 角色守卫生效 | 否 | 调用方兼容性确认，两入口 requireEmployeeRead 及完整角色矩阵通过 | Employee Controller/security/调用方回归：7 项测试通过；既有交互用户仅 ADMIN/VIEWER | Employee 业务维护者/实施者 | 生产组合根切换前 | Java MVC/security 与既有调用方测试 | 禁止有效生产路径和真实 Employee 联调 | Closed |
| `GATE-069` | `WP-TXN-SEARCH-EXT-02` | integration | Transaction Date 时区/精度合同生效 | 否 | Python Date→HTTP→Jackson→Mapper instant/open interval/DB precision 证据成立 | Transaction Java/Python fixture 与业务时区合同 | Transaction 维护者/实施者 | 日期 live/UAT 前 | 双语言 contract 与 strict bounds tests | 日期相关真实联调/UAT 不执行 | Open |
| `GATE-070` | `WP-BQ-CONTROLLED-LIVE-02` | integration | 真实模型、业务服务和有限敏感数据调用 | 是 | 前置 non-live 包完成，GATE-068/069 关闭，环境/预算/授权/安全边界已确认 | 实施代码证据、服务状态和用户真实调用授权 | 用户/业务维护者 | 首次模型或业务调用前 | frozen task/config/cases、预算和零泄漏 preflight | live 保持 Blocked，不调用真实系统 | Open |
| `GATE-UAT-007` | `WP-BQ-UAT-HANDOFF-02` | closure | 正式四阶段 UAT | 是 | 前 11 个工作包与 controlled live 完成，UAT 环境/代表性业务数据就绪并获得明确授权；不要求 UAT 工作包自身预先完成 | UAT_00 准入和本版 live evidence | 用户/UAT 执行者 | 首个正式 UAT 用例前 | UAT checklist、调用预算及 gate→UAT 无环性复核 | 正式 UAT 保持 Blocked | Open |

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
| 5 | `WP-EMP-SEMANTIC-ADAPTER-02` | Ready | `WP-BQ-FIELD-CONFIG-02` | semantic profile 和字段分类已就绪 |
| 6 | `WP-EMP-ES-AUTH-02` | Done | - | 两入口复用现有读取守卫，调用方兼容核实与 7 项安全测试通过 |
| 7 | `WP-TXN-SEARCH-EXT-02` | Ready | `WP-BQ-FIELD-CONFIG-02` | Date/Decimal/分页统一字段合同已就绪 |
| 8 | `WP-BQ-RUNTIME-CUTOVER-02` | Blocked | Model/两个 Employee/Transaction/Employee 授权五项前置 | 生产组合根必须等待完整安全对象图 |
| 9 | `WP-EMP-DETAIL-RETIRE-02` | Blocked | `WP-BQ-RUNTIME-CUTOVER-02` | 先具备新列表替代路径 |
| 10 | `WP-BQ-NONLIVE-E2E-02` | Blocked | `WP-BQ-RUNTIME-CUTOVER-02` | E2E 需要唯一三动作对象图 |
| 11 | `WP-BQ-CONTROLLED-LIVE-02` | Blocked | non-live/retire 与 `GATE-070` | 真实调用必须独立授权和受控 |
| 12 | `WP-BQ-UAT-HANDOFF-02` | Blocked | controlled live 与 `GATE-UAT-007` | UAT 不能复用旧 detail 证据 |

## 10. 实施交接

| 工作包 | 允许动作 | 禁止动作 | 预期文件/模块 | 来源设计 ID | 测试与验证 | 开放后续门禁 | 建议执行技能 |
|---|---|---|---|---|---|---|---|
| `WP-BQ-FILTER-CONTRACT-02` | fake filters/decoder/validator/binder | 真实模型/业务调用 | business/query_plan | `DR-BQCOM-101/103` | `VAL-BQCOM-101` | 字段配置依赖 | implement-from-detailed-design |
| `WP-BQ-FIELD-CONFIG-02` | 单文件 typed config/snapshot | 配置平台/扩字段 | business/contracts/settings/json | `DR-BQCOM-102/104` | `VAL-BQCOM-101/102` | Model/Adapter 依赖 | implement-from-detailed-design |
| `WP-BQ-MODEL-CATALOG-02` | fake v3 task/catalog | 读取密钥/真实模型 | model/deepseek/business_query_plan | `DR-MODEL-101～105` | `VAL-MODEL-101/102` | 组合根依赖 | implement-from-detailed-design |
| `WP-EMP-SEARCH-ADAPTER-02` | fake ES search/strict hits | 真实 ES/数据库/endpoint 扩张 | adapters/employee | `DR-EMP-101/103/104` | `VAL-EMP-101/103` | 组合根依赖 | implement-from-detailed-design |
| `WP-EMP-SEMANTIC-ADAPTER-02` | fake vector-search/profile | 用户 vector/filter/双调用 | adapters/employee | `DR-EMP-102/104` | `VAL-EMP-101/103` | 组合根依赖 | implement-from-detailed-design |
| `WP-EMP-ES-AUTH-02` | 调用方核实和既有 guard 安全测试 | 新角色、新接口、未核实直接生效 | EmployeeEsController/guard | `DR-EMP-105` | `VAL-EMP-102` | `GATE-068` | implement-from-detailed-design |
| `WP-TXN-SEARCH-EXT-02` | fake Date/Decimal/page/sort 和 Java tests | 改 DTO/SQL、未经证实相对日期 | adapters/transaction 与现有 Java tests | `DR-TXN-101～105` | `VAL-TXN-101/102` | `GATE-069` | implement-from-detailed-design |
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
| `WP-EMP-SEMANTIC-ADAPTER-02` | `DR-EMP-102/104` | `IMPL-EMP-101～105` | `TEST-EMP-103/104` | `VAL-EMP-101/103` | Ready |
| `WP-EMP-ES-AUTH-02` | `DR-EMP-105` | `IMPL-EMP-106/107` | `TEST-EMP-106` | `VAL-EMP-102` | Done |
| `WP-TXN-SEARCH-EXT-02` | `DR-TXN-101～105` | `IMPL-TXN-101～107` | `TEST-TXN-101～106` | `VAL-TXN-101/102/103` | Ready |
| `WP-BQ-RUNTIME-CUTOVER-02` | `DR-CORE-101～104` | `IMPL-CORE-101～104` | `TEST-CORE-101～104` | `VAL-CORE-101/102` | Blocked |
| `WP-EMP-DETAIL-RETIRE-02` | `DR-EMP-106` | `IMPL-EMP-105` | `TEST-EMP-107` | `VAL-EMP-103` | Blocked |
| `WP-BQ-NONLIVE-E2E-02` | `DR-BQCOM-106`; `DR-CORE-102` | 现有 system_e2e 测试入口 | 三动作 fake 与零调用 | non-live/mypy/compileall | Blocked |
| `WP-BQ-CONTROLLED-LIVE-02` | `DR-MODEL-104`; `DR-EMP-105`; `DR-TXN-105` | 受控 runner 和有限 evidence | 有限三动作 live 矩阵 | `GATE-070` 关闭证据 | Blocked |
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

总计 12 个工作包、15 条直接依赖：Ready 3 个，Blocked 5 个，Done 4 个。filters 合同、统一三动作配置、v3 Model 逻辑目录/Prompt 与 Employee ES 最终读取授权已完成；Model/Business/graph 231 项 Python 回归和读取授权 7 项 Java 测试通过。两个 Employee Adapter 和 Transaction Adapter 可独立实施。`GATE-067/068` Closed，`GATE-069/070` 与 `GATE-UAT-007` 保持 Open。

## 15. 后续实施建议

获得代码授权后，先并行执行 `WP-BQ-FILTER-CONTRACT-02` 和 `WP-EMP-ES-AUTH-02` 调用方核实；再实施统一配置、Model/Employee/Transaction、组合根、non-live E2E、受控 live 和 UAT。若现有接口无法安全表达目标，应停止对应扩展并报告，不得自行新建接口或扩大权限。
