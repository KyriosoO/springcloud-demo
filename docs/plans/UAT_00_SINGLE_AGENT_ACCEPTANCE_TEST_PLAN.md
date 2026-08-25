# [UAT_00] 单体 Agent 结构化查询用户验收计划

## 1. 文档信息与来源

| 项目 | 内容 |
|---|---|
| 当前版本 | v1.8 |
| 文档状态 | Reviewed |
| 更新日期 | 2026-08-25 |
| 上位来源 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v2.0；[`L1_02`](../design/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v2.3 |
| 详细设计 | [`L2_02_00`](../design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v2.3；Employee L2 v2.3；Transaction L2 v2.3 |
| 实施前置 | [`P3_00`](P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) v2.10 |
| 当前状态 | controlled-run06 已通过；首次 UAT 的九个 Employee 场景通过，首个 Transaction 类型 eq 因 `_` 被原 contains 策略误拒；`GATE-UAT-007` Open，operator-specific 修复待实施 |
| 归档来源 | [v0.9 已评审旧版](历史文档/UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN_v0.9.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 验收目标与范围外

验证输入安全闸门先形成最小化问题和 request-local slots，真实 LLM 再根据安全目录生成 `employee.search`、`employee.semantic_search`、`transaction.search` 三动作之一的 filters QueryPlan，经严格 decoder/validator/`value_ref` slot binder 和一次 Adapter 调用，复用现有 Employee ES/向量或 Transaction SQL 接口，返回受控列表。输入闸门不得选择业务动作或生成 filters；Knowledge 保持独立，不在本阶段执行效果验收。

范围外：真实业务写入、聚合、新 endpoint/DTO、DB/ES 直连、workBase 查询、跨域 fallback、Employee 双接口拼装、历史 evidence 复用，以及未经授权的模型费用和敏感数据持久化。

## 3. 环境前置和准入门禁

1. P3 中正式 UAT 之前的 13 个新目标工作包按依赖完成；第 14 个 `WP-BQ-UAT-HANDOFF-02` 必须在 `GATE-UAT-007` 关闭后执行，不能反向作为本门禁前置；Employee 两入口最终读取授权已验证。
2. `GATE-068` 已关闭；两个 Employee ES POST endpoint 使用明确绑定共享 `userRoleJwtAuthenticationConverter` 的专用真实 Servlet 安全链，ADMIN/VIEWER 允许及 denied/missing/malformed/service-token 拒绝矩阵成立；detail 和其他 endpoint 历史行为不变。仅有直接 Controller 单元测试或手工赋予 authority 的测试不能替代该证据。
3. `GATE-069` 已关闭后才执行 Transaction 绝对 Date 用例；必须验证生产 Spring UTC 零毫秒 offset 响应字符串与 legacy standalone epoch 毫秒都转换为同一上海时区 instant，拒绝其他日期形态。相对自然日若无数据库精度/边界证据，仍按 unsupported 验收。
4. 新三动作 filters task、code/config snapshot、权限、业务服务和 non-live/live 结果均属于当前设计，不得复用旧 detail 或旧 v2 Prompt 证据。
5. 真实 provider、用户 JWT、Employee 标识和业务样本仅在明确授权后进程内使用；日志/evidence 只存有限 case 状态和调用计数。
6. 联系地址样本确实支持 “上海” contains；若真实数据不存在，不得构造 workBase 样本伪造通过，应停止并报告数据前置缺失。
7. 正式验收仅在独立 `GATE-UAT-007` 关闭后开始；默认 provider `stub` 只能证明失败关闭，不能形成业务成功 UAT。
8. 三动作超时必须与代码/配置 snapshot 一致：Employee search 3000ms、semantic 10000ms、Transaction 5000ms；不得为规避超时增加重试、fallback 或第二次业务调用。

## 4. 固定验收顺序

| 阶段 | 内容 | 前置 | 当前状态 |
|---|---|---|---|
| `UAT-PUBLIC-02` | 公共接入冒烟 | `GATE-UAT-007` | Passed |
| `UAT-EMP-02` | Employee search/semantic 列表 UAT | 公共冒烟与 Employee 读取授权 | Partial：首次九场景通过，完整 UAT 尚未通过 |
| `UAT-TXN-02` | Transaction 类型/日期/金额/分页/排序 UAT | 公共冒烟、Transaction Date 合同与 operator-specific 文本策略 | Blocked |
| `UAT-BQ-CLOSURE-02` | Access/Core/Model/Config/Adapter/JWT/单动作收口 | Employee 与 Transaction 均完成 | Blocked |

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
| `UAT-EMP-210` | “语义能力 + 上海地址过滤” | 1/0 | unsupported；禁止两次搜索或客户端补筛 |
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
| `UAT-TXN-212` | 相对自然日缺少 precision/边界证明 | 1/0 | unsupported；不能猜测“今天/最近一周” |
| `UAT-TXN-213` | ADMIN/VIEWER/denied/missing/malformed/service-token | 0/0 或 1/1，按接入/业务拒绝位置断言 | 最终读取授权仍由 Transaction 服务执行 |
| `UAT-TXN-214` | rows/total/totalExact/page/size 及生产 Spring Date response | 1/1 | totalExact=false 仅表示 lower bound；仅接受真实 UTC `.000+00:00` 或 standalone 整秒 epoch 日期，转换上海时区；兼容九项 row 白名单并丢弃五项条件属性 |
| `UAT-TXN-215` | 聚合、detail、写入、物理 SQL/表列 | 0/0 或 1/0 | unsupported/invalid；其他 endpoint=0 |

## 8. 结构化阶段收口

回归 Access 认证/严格 JSON、LangGraph/Core、v3 Model task、filters 两级 decoder、Business validator/binder、不可变 JSON snapshot、request-local slots、用户 JWT 透传、三个固定 endpoint、单 action latch、取消、Knowledge 隔离、用户投影及模型出域默认拒绝。

每个成功业务 case 必须证明真实 QueryPlan 模型调用=1、对应 endpoint 调用=1、另一域/另一 Employee 动作/Knowledge/第二动作/重试=0。模型失败、非法计划、未配置字段、unsupported semantic+filter、非法日期/金额/分页均必须证明业务调用=0。

## 9. 结果记录、敏感扫描与失败处理

只允许记录 case ID、action、有限状态、模型/业务调用整数、projection/敏感扫描布尔值以及必要配置版本。不得保存原始用户问题、姓名、地址、身份证、电话、邮箱、JWT、模型原文、ES raw hits 或 Transaction raw rows。出现服务权限缺口、数据不具备、Date contract 不成立或模型失败时，暂停该用例并报告，不自动切换域、搜索方式或降低断言。

## 10. 当前状态与明确差距

controlled-run06 完成 6 次真实 LLM QueryPlan，证据 SHA-256=`d80167215796c53c05b2f9443eaa5c96c0e82215b46d8d5df2f5e888b2f37ef6`；公共接入 Java 20 项通过。首次正式 UAT 已通过九个 Employee search/semantic/角色/零调用场景，但在 `UAT-TXN-201` 处因真实 `trans_type` 包含 `_` 被原 contains 策略错误拒绝；Transaction 调用为 0、retry/resume 为 0，失败 SHA-256=`cc2905dab7a4d78fd52f7fd8c973b2c41fbaa77db47a0bc6036f45119f34c0c3`。`GATE-UAT-007` 已重新打开；须先修复 `eq/contains` 代码绑定策略并验证 contains 通配拒绝，再使用独立新 UAT 结果路径，既有失败及 manifest 保持不可变。
