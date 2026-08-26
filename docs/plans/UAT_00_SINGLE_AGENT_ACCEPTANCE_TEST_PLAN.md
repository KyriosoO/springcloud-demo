# [UAT_00] 单体 Agent 结构化查询用户验收计划

## 1. 文档信息与来源

| 项目 | 内容 |
|---|---|
| 当前版本 | v1.14 |
| 文档状态 | Reviewed |
| 更新日期 | 2026-08-26 |
| 上位来源 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v2.0；[`L1_02`](../design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v2.4 |
| 详细设计 | [`L2_02_00`](../design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v2.4；Employee L2 v2.4；Transaction L2 v2.4 |
| 实施前置 | [`P3_00`](P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) v2.16 |
| 当前状态 | 35 个固定用例均已有可审查证据：18 个使用不可变真实 v4 QueryPlan/业务证据，17 个按风险使用当前生产组合根、Spring 安全链或跨语言契约自动化验证；没有把旧 detail/stub UAT 计入当前通过 |
| 归档来源 | [v0.9 已评审旧版](历史文档/UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN_v0.9.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 验收目标与范围外

验证输入安全闸门先形成最小化问题和 request-local slots，真实 LLM 再根据安全目录生成 `employee.search`、`employee.semantic_search`、`transaction.search` 三动作之一的 filters QueryPlan，经严格 decoder/validator/`value_ref` slot binder 和一次 Adapter 调用，复用现有 Employee ES/向量或 Transaction SQL 接口，返回受控列表。输入闸门不得选择业务动作或生成 filters；Knowledge 保持独立，不在本阶段执行效果验收。

范围外：真实业务写入、聚合、新 endpoint/DTO、DB/ES 直连、workBase 查询、跨域 fallback、Employee 双接口拼装、历史 evidence 复用，以及未经授权的模型费用和敏感数据持久化。

## 3. 环境前置和准入门禁

1. P3 中正式 UAT 之前的 14 个新目标工作包按依赖完成，包括 v4 完整意图 Prompt；第 15 个 `WP-BQ-UAT-HANDOFF-02` 必须在 `GATE-UAT-007` 关闭后执行，不能反向作为本门禁前置；Employee 两入口最终读取授权已验证。
2. `GATE-068` 已关闭；两个 Employee ES POST endpoint 使用明确绑定共享 `userRoleJwtAuthenticationConverter` 的专用真实 Servlet 安全链，ADMIN/VIEWER 允许及 denied/missing/malformed/service-token 拒绝矩阵成立；detail 和其他 endpoint 历史行为不变。仅有直接 Controller 单元测试或手工赋予 authority 的测试不能替代该证据。
3. `GATE-069` 已关闭后才执行 Transaction 绝对 Date 用例；必须验证生产 Spring UTC 零毫秒 offset 响应字符串与 legacy standalone epoch 毫秒都转换为同一上海时区 instant，拒绝其他日期形态。相对自然日若无数据库精度/边界证据，仍按 unsupported 验收。
4. 新三动作 filters task、code/config snapshot、权限、业务服务和 non-live/live 结果均属于当前设计，不得复用旧 detail 或旧 v2 Prompt 证据。
5. 真实 provider、用户 JWT、Employee 标识和业务样本仅在明确授权后进程内使用；日志/evidence 只存有限 case 状态和调用计数。
6. 联系地址样本确实支持 “上海” contains；若真实数据不存在，不得构造 workBase 样本伪造通过，应停止并报告数据前置缺失。
7. `GATE-UAT-007` 是 UAT 准入与证据闭合门禁：成功业务规划风险必须由不可变真实 v4 结果覆盖；严格 JSON、身份拒绝、字段边界和跨语言契约可由当前自动化等价验证。默认 provider `stub` 不能单独形成业务成功证据。
8. 三动作超时必须与代码/配置 snapshot 一致：Employee search 3000ms、semantic 10000ms、Transaction 5000ms；不得为规避超时增加重试、fallback 或第二次业务调用。

## 4. 固定验收顺序

| 阶段 | 内容 | 前置 | 当前状态 |
|---|---|---|---|
| `UAT-PUBLIC-02` | 公共接入冒烟 | `GATE-UAT-007` | Passed：5/5，均由当前 Spring 安全/严格 JSON/Runtime E2E 自动化验证 |
| `UAT-EMP-02` | Employee search/semantic 列表 UAT | 公共冒烟、Employee 读取授权与 v4 完整意图约束 | Passed：15/15；9 个真实场景，6 个风险等价自动化场景 |
| `UAT-TXN-02` | Transaction 类型/日期/金额/分页/排序 UAT | 公共冒烟、Transaction Date 合同、operator-specific 文本策略与 v4 相对日期约束 | Passed：15/15；9 个真实场景，6 个风险等价自动化场景 |
| `UAT-BQ-CLOSURE-02` | Access/Core/Model/Config/Adapter/JWT/单动作收口 | Employee 与 Transaction 均完成 | Passed：35/35 可追踪；18 次真实规划，17 个等价自动化风险闭合 |

Employee 和 Transaction 用例组相互独立，若按用户指定顺序执行，则先 Employee、后 Transaction；Knowledge 政策查询 UAT 单独规划，不因 Business 失败启动。

## 5. 公共接入冒烟

| 用例 | 验证项 | 预期模型调用 | 预期业务调用 |
|---|---|---:|---:|
| `UAT-PUB-201` | missing/malformed 身份认证 | 0 | 0 |
| `UAT-PUB-202` | duplicate key、额外字段、null 和非法 JSON | 0 | 0 |
| `UAT-PUB-203` | 默认 stub 业务请求失败关闭，不生成成功查询 | 0 或按 stub 合同计 1；无真实 outbound | 0 |
| `UAT-PUB-204` | 非业务或超出当前目录的问题 unsupported | 0 或 1；按明确入口设计断言 | 0 |
| `UAT-PUB-205` | 第二动作/跨域/Knowledge/Resolver/ID-only 不可达 | 0 或 1；不得触发第二模型规划 | 0 |

## 6. Employee UAT

| 用例 | 用户意图与 QueryPlan 断言 | 预期模型/Employee 调用 | 结果与安全断言 |
|---|---|---|---|
| `UAT-EMP-201` | “查询上海员工”：`employee.search + contact_address + contains + 上海` | 1/1 | 只调用 search，rows 为受控列表；不使用 workBase |
| `UAT-EMP-202` | 职位精确：`position eq` | 1/1 | 查询字段、operator 和用户投影精确匹配 |
| `UAT-EMP-203` | 职位模糊：`position contains` | 1/1 | 不退化为其他 field/operator |
| `UAT-EMP-204` | 姓名查询：`chinese_name + value_ref` | 1/1 | 模型、日志和 evidence 不含真实姓名 |
| `UAT-EMP-205` | 员工标识：`employee_identifier eq + value_ref` | 1/1 | 不调用旧 detail，ID 不进入模型或 evidence |
| `UAT-EMP-206` | Employee ES keyword + tagged literal/ref | 1/1 | 只对 contactAddress/chineseName/idCardNo 的现有 multi-match 解释；敏感 keyword 必须为 protected ref，模型和日志无明文 |
| `UAT-EMP-207` | Employee page/size/sort | 1/1 | from 转换正确、size≤50、rows 不超界 |
| `UAT-EMP-208` | 业务语义：`employee.semantic_search + query + size` | 1/1 | 只调用 vector-search；允许既有接口返回小于 k 的 partial hits，仅隔离缺必填身份字段的历史记录并保留真实 total/coverage；10000ms 上限、请求 deadline、零重试和零 fallback |
| `UAT-EMP-209` | 未配置 Employee 字段；以 `workBaseSi/workBaseAf` 作为样例 | 1/0 | 模型依据通用目录返回 `unsupported`，或字段 validator 返回 `invalid_argument`；业务调用为 0，不增加 workBase 专用识别或拒绝逻辑 |
| `UAT-EMP-210` | “语义能力 + 上海地址过滤” | 1/0 | 必须 exact unsupported；禁止省略上海后调用 semantic，也禁止调用 search、两次搜索或客户端补筛 |
| `UAT-EMP-211` | ADMIN/VIEWER 实际 JWT role claim 分别经真实 Servlet 安全链访问 search 与 semantic | 各 1/1 | endpoint-scoped 共享 converter 生效，Employee 服务最终授权允许；detail/fallback 行为保持兼容 |
| `UAT-EMP-212` | 无读取角色、service token | 1/1 或接入拒绝 0/0 | forbidden；不切换动作或域 |
| `UAT-EMP-213` | missing/malformed token | 0/0 | unauthenticated；不调用模型和服务 |
| `UAT-EMP-214` | 原始 ES hits 含未知字段、embedding、embeddingText、workBase 或缺必填字段的历史记录 | 1/1 | 仅七字段受控投影；合法 partial hits 保留真实 total/有效记录数，缺失姓名或标识记录隔离；非法类型或全部命中无效仍失败关闭 |
| `UAT-EMP-215` | 详细地址、电话、邮箱、真实姓名及 identifier 输入 | 0/0 或 1/1，仅当 protected-ref 已成功绑定 | 模型 payload/log/evidence 不含具体敏感值 |

普通与向量模式不得互相 fallback。真实数据为空或索引未同步时，应记录 no_result/数据缺口，不得把合成 workBase 值当真实能力。

## 7. Transaction UAT

| 用例 | QueryPlan 断言 | 模型/search 调用 | 结果与合同断言 |
|---|---|---|---|
| `UAT-TXN-201` | `trans_type eq`，真实类型允许合法 `_` | 1/1 | condition.transType 精确映射；不得把 LIKE 安全限制套用到 `=` |
| `UAT-TXN-202` | `trans_type contains`，使用已存在类型中不含 `_/%/反斜杠` 的安全片段 | 1/1 | condition.transTypeContains；通配字符零调用拒绝，不公开 DTO suffix |
| `UAT-TXN-203` | `trans_date eq` + canonical offset | 1/1 | Java Date instant、Asia/Shanghai 合同、返回 rows 一致 |
| `UAT-TXN-204` | `trans_date gt + lt` | 1/1 | SQL 严格开区间；上下界不丢失 |
| `UAT-TXN-205` | `amount eq` | 1/1 | canonical decimal→JSON number→BigDecimal，scale≤2 |
| `UAT-TXN-206` | `amount gt + lt` | 1/1 | 同字段双 filter 和严格 open range |
| `UAT-TXN-207` | `trans_type + trans_date + amount` 组合 | 1/1 | 所有用户条件完整存在，不能删条件执行更宽查询 |
| `UAT-TXN-208` | page 2、size≤50 | 1/1 | page 不固定为1，offset 安全 |
| `UAT-TXN-209` | 四字段各自排序、最多两项 | 1/1 | 只允许 ASC/DESC；稳定 tiebreaker 由业务服务掌握 |
| `UAT-TXN-210` | trans_id protected-ref | 1/1 | 标识不进入模型、日志及结果明文 |
| `UAT-TXN-211` | Decimal 超精度、float、非法 date/offset/size/sort | 0 或 1/0 | invalid_argument；不调用 search |
| `UAT-TXN-212` | 相对自然日缺少批准时钟/precision/边界证明 | 1/0 | 即使 `trans_date` 已启用也必须 unsupported；不能猜测“今天/最近一周” |
| `UAT-TXN-213` | ADMIN/VIEWER/denied/missing/malformed/service-token | 0/0 或 1/1，按接入/业务拒绝位置断言 | 最终读取授权仍由 Transaction 服务执行 |
| `UAT-TXN-214` | rows/total/totalExact/page/size 及生产 Spring Date response | 1/1 | totalExact=false 仅表示 lower bound；仅接受真实 UTC `.000+00:00` 或 standalone 整秒 epoch 日期，转换上海时区；兼容九项 row 白名单并丢弃五项条件属性 |
| `UAT-TXN-215` | 聚合、detail、写入、物理 SQL/表列 | 0/0 或 1/0 | unsupported/invalid；其他 endpoint=0 |

## 8. 结构化阶段收口

回归 Access 认证/严格 JSON、LangGraph/Core、v4 Model task、filters 两级 decoder、Business validator/binder、不可变 JSON snapshot、request-local slots、用户 JWT 透传、三个固定 endpoint、单 action latch、取消、Knowledge 隔离、用户投影及模型出域默认拒绝。

每个成功业务 case 必须证明真实 QueryPlan 模型调用=1、对应 endpoint 调用=1、另一域/另一 Employee 动作/Knowledge/第二动作/重试=0。模型失败、非法计划、未配置字段、unsupported semantic+filter、非法日期/金额/分页均必须证明业务调用=0。

## 9. 结果记录、敏感扫描与失败处理

只允许记录 case ID、action、有限状态、模型/业务调用整数、projection/敏感扫描布尔值以及必要配置版本。不得保存原始用户问题、姓名、地址、身份证、电话、邮箱、JWT、模型原文、ES raw hits 或 Transaction raw rows。出现服务权限缺口、数据不具备、Date contract 不成立或模型失败时，暂停该用例并报告，不自动切换域、搜索方式或降低断言。

## 10. 用例—证据追踪

当前权威机器可校验追踪资产为 `agent-runtime/tests/uat/uat_traceability.v2.json`，严格校验入口为 `tests/uat/test_current_traceability.py`。旧 `uat_cases.v1.json` 与 `structured-query-uat-v1` 结果只代表历史 `employee.detail + stub` 阶段，保持字节不变但不参与当前 35 个用例的通过判定。

| 用例 | 验证方式 | 当前证据 | 状态 |
|---|---|---|---|
| `UAT-PUB-201` | Spring 安全链 | `AgentSecurityContractTest#missingInvalidAndServiceTokensUseSafe401EnvelopeWithoutRuntime` | Passed |
| `UAT-PUB-202` | Spring 严格 JSON | `AgentSecurityContractTest#duplicateNullAndMalformedJsonFailBeforeRuntime`；unknown-field 测试 | Passed |
| `UAT-PUB-203` | 默认 stub/零外发契约 | `test_runtime_composition.py` | Passed |
| `UAT-PUB-204` | Spring→Runtime non-live | `AgentBusinessQueryPlanNonLiveE2ETest` | Passed |
| `UAT-PUB-205` | Spring→Runtime + 当前三动作组合根 | 第二动作/跨域用例；当前三动作 Resolver 零绑定与 cutover 测试 | Passed |
| `UAT-EMP-201` | 真实 LLM + 真实业务 | run03 `UAT-EMP-201` | Passed |
| `UAT-EMP-202` | Python Adapter 合同 | position `eq` 精确映射与受控用户结果投影 | Passed |
| `UAT-EMP-203` | 真实 LLM + 真实业务 | run03 `UAT-EMP-203` | Passed |
| `UAT-EMP-204` | 当前生产组合根 non-live | 姓名 `value_ref` 模型前替换/模型后绑定 | Passed |
| `UAT-EMP-205` | 真实 LLM + 真实业务 | run03 `UAT-EMP-205` | Passed |
| `UAT-EMP-206` | 当前生产组合根 non-live + 配置合同 | keyword protected-ref 与固定三字段服务解释 | Passed |
| `UAT-EMP-207` | 真实 LLM + 真实业务 | run03 `UAT-EMP-207` | Passed |
| `UAT-EMP-208` | 真实 LLM + 真实业务 | run03 `UAT-EMP-208` | Passed |
| `UAT-EMP-209` | 真实 LLM + 通用配置白名单 | run03 + `test_unconfigured_field_is_unreachable_through_generic_allowlist` | Passed |
| `UAT-EMP-210` | 真实 LLM 零业务调用 | run03 `UAT-EMP-210` | Passed |
| `UAT-EMP-211` | 真实 LLM + Java Servlet 安全链 | run03 + `EmployeeEsSecurityIntegrationTest` ADMIN/VIEWER 双入口 | Passed |
| `UAT-EMP-212` | 真实 LLM + Java Servlet 安全链 | run03 + denied/service-token 矩阵 | Passed |
| `UAT-EMP-213` | Spring 接入 + Java Servlet 安全链 | missing/malformed 零下游调用 | Passed |
| `UAT-EMP-214` | Python fake ES 合同 | unknown/embedding/workBase 丢弃与 partial hits 隔离 | Passed |
| `UAT-EMP-215` | 输入保护 + 当前组合根 non-live | 地址/电话/邮箱/姓名/标识模型前保护 | Passed |
| `UAT-TXN-201` | 真实 LLM + 真实业务 | run03 `UAT-TXN-201` | Passed |
| `UAT-TXN-202` | 真实 LLM + 真实业务 | run03 `UAT-TXN-202` | Passed |
| `UAT-TXN-203` | 真实 LLM + 真实业务 | run03 `UAT-TXN-203` | Passed |
| `UAT-TXN-204` | Python/Java 范围合同 | 双 Date bound 与严格开区间 | Passed |
| `UAT-TXN-205` | 真实 LLM + 真实业务 | run03 `UAT-TXN-205` | Passed |
| `UAT-TXN-206` | 真实 LLM + 真实业务 | run03 `UAT-TXN-206` | Passed |
| `UAT-TXN-207` | Python Adapter 合同 | type/date/amount 条件完整保留 | Passed |
| `UAT-TXN-208` | 真实 LLM + 真实业务 | run03 `UAT-TXN-208` | Passed |
| `UAT-TXN-209` | Python Adapter 合同 | 排序映射与非法/重复排序拒绝 | Passed |
| `UAT-TXN-210` | Python protected-ref 合同 | 标识 request-local 绑定且模型不可见 | Passed |
| `UAT-TXN-211` | Python/Java 输入合同 | Decimal/float/date/page/size/sort 非法输入零 search | Passed |
| `UAT-TXN-212` | 真实 LLM 零业务调用 | run03 `UAT-TXN-212` | Passed |
| `UAT-TXN-213` | 真实 LLM + Java Reactive 安全链 | run03 + ADMIN/VIEWER/拒绝矩阵 | Passed |
| `UAT-TXN-214` | Python/Java 跨语言合同 | rows/totalExact/page/size/Date/Decimal | Passed |
| `UAT-TXN-215` | 真实 LLM 零业务调用 | run03 `UAT-TXN-215` | Passed |

## 11. 当前结论与证据边界

v3 controlled-run06 SHA-256=`d80167215796c53c05b2f9443eaa5c96c0e82215b46d8d5df2f5e888b2f37ef6`；首次和第二次 UAT 不可变失败 SHA-256 分别为 `cc2905dab7a4d78fd52f7fd8c973b2c41fbaa77db47a0bc6036f45119f34c0c3`、`1b4c5eb334a42f699afb05d68210b0585cb6940401bec082a0ea2946a89a2c8f`。v4 run03 正式成功结果 SHA-256=`b49832426147dc14d56e571fea11b0345e16602d8cb5e2ea2eeb3dacb3326dd8`，只证明其中列出的 18 个真实场景，不外推为 35 次真实执行。

剩余 17 个用例按风险分别由当前 Spring→Runtime、Spring/Servlet/Reactive 安全链、Python 生产组合根 fake E2E 和 Java/Python 跨语言契约关闭；追踪资产验证每个引用路径与测试符号真实存在，并强制真实证据集合仍为 18。该分层与个人学习项目的风险相称：不重复付费验证确定性 codec/权限/严格 JSON，同时不降低 QueryPlan 真实模型及真实业务调用证据。最终全量 Python non-live 回归为 `1389 passed / 27 opt-in skipped`，agent-service 当前 Spring→Runtime 与严格 JSON 套件包含在 `34 tests / 1 opt-in skipped / 0 failures` 中；Employee/Transaction Java 安全和合同回归分别为 `50 tests / 20 opt-in skipped / 0 failures`、`51 tests / 2 skipped / 0 failures`。四个阶段均标记 Passed，`GATE-UAT-007` 基于 35/35 追踪矩阵有效关闭。
