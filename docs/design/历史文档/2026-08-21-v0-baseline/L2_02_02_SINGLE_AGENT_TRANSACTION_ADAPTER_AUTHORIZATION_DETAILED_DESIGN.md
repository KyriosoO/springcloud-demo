# [L2_02_02] 单体 Agent Transaction Adapter 与业务授权联调详细设计 L2

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Transaction Adapter 与业务授权联调详细设计 |
| 文档标识 | `SA-L2-TRANSACTION-ADAPTER-001` |
| 文档编号 | `L2_02_02` |
| 文档路径 | `docs/design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 历史精度、Resolver、真实联调、candidate/wrapper 与失败证据保持不可变；v0.25 完成现行权威与历史审计的物理分层，不改变 Transaction 真实 Provider + stub 模型系统 E2E 与可选真实结果外部模型实验的既有边界 |
| 当前版本 | v0.25 |
| 日期 | 2026-08-20 |
| 适用范围 | Python `agent-transaction-adapter` 的 `transaction.search` 单动作、本地确定性参数 Resolver、现有 Transaction 搜索接口映射、标识/类型/精确金额条件、排序/页大小收紧、响应/字段投影、业务服务最终角色授权、错误映射和联调门禁 |
| 上位文档 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.5 Approved |
| 直接输入 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v0.57 Approved；[`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.11 Approved；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v0.23；[`L2_00_03`](L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) v0.4 Approved |
| 外部契约 | `mq-procedure-service` `POST /txn/search`；`transaction-api` search DTO；`auth-service/common-security` 用户 JWT/Authority |
| 实现基线 | `agent-runtime/src/agent_runtime/adapters/transaction` 既有 Adapter、ExactDecimal/scale≤2、Java Provider 与受控真实联调资产已实现验证。`TransactionSearchLocalActionResolver`、definition 绑定、金额字符串保真、最终 validator/配置复核和混合节点测试已按 `WP-BUSINESS-LOCAL-RESOLVER-01` 实施验证；共享 Authority、公开 DTO/endpoint、数据库 `DECIMAL(50,2)` 与既有 evidence 不因本同步改变 |
| 是否可作为实现依据 | 按范围可用 |
| 实施依据说明 | `BQ-GATE-002/003` 已分别按 Python Adapter 与 Provider 切片关闭；生产 `DECIMAL(50,2)`、共享 Authority、调用方/可见性快照及 `VAL-TXN-003～005` 证据齐备，`SA-GATE-005` 已关闭，允许受控目标配置启用 `transaction.search` |
| 当前允许实施范围 | 只读维护既有 Adapter/Provider/真实联调与历史审计资产；当前系统 E2E 已调用通过验证的 Transaction Provider，并固定使用默认 stub 模型。wrapper-v2 真实执行与 Transaction 真实结果外部模型实验转为 Deferred |
| 当前禁止动作 | 修改数据库结构或公开 DTO/endpoint，扩大 16 位整数部分的 Agent 金额绝对值上限，以字符串 coercion、舍入/截断或隐式 scale 转换绕过精度契约，增加 Date/聚合/写能力，新增未授权真实调用，默认/生产启用 search，或把 Transaction 数据发送真实模型 |
| 修改权限 | 本轮仅授权设计与计划Markdown原子同步；未授权代码、测试资产、服务/SELECT/Transaction/DeepSeek调用或Git提交推送 |

> 第一阶段只设计 `transaction.search`，固定 page=1，支持交易标识、交易类型精确/包含及金额等值/开区间条件。本地 Resolver 产生的金额参数保持规范十进制字符串，validator 转为 Python `Decimal`，公共 business wire 以精确 JSON number 发送至现有 Java `BigDecimal` 字段，全链路禁止 float。Java `Date` 的 JSON 格式仍未形成已验证契约，因此日期条件、日期排序和日期结果不进入 typed Agent 契约。detail/query/condition/aggregate 及写入口全部不可达。

## 2. 修改历史

> 完整修改历史已迁移至 [L2_02_02 历史审计记录](history/L2_02_02_TRANSACTION_ADAPTER_AUDIT_HISTORY.md)；历史文档只作审计，不覆盖本文当前权威。

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-08-20 | 文档治理、历史与评审章节 | 对现行文档执行物理瘦身 | 更新为 v0.25；完整历史与逐轮记录迁移到只读审计附件；稳定标识、设计语义、当前门禁、状态和结论不变 |

## 3. 背景、目标与范围

### 3.1 背景与根因

`TransactionController` 同时公开消息提交、更新、详情、宽条件、分页搜索、聚合、创建和删除。现有 `/txn/search` 是最接近 Agent 只读查询的接口，但其请求复用宽 `Transaction` 条件，公开 Date/金额等多种字段；当前 guard 只验证 user token。若 Adapter 允许模型直接构造该 DTO，可能扩大条件、调用聚合/写入口、混淆日期格式或在业务服务未最终验角色情况下查询。

### 3.2 目标与可观察行为

| 需求编号 | 目标 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-TXN-001` | 只提供一个代码绑定搜索动作 | registry 仅有 `transaction.search@1`；其他 `/txn` 路径调用数为零 | L1_02 6/7；L2_02_00 |
| `REQ-TXN-002` | 条件与排序强类型收紧 | 至少一个文本或金额条件；page 固定 1；size≤配置≤50；排序≤2 且仅三字段 | L1_02 7.2 |
| `REQ-TXN-003` | 首期排除不稳定 Date wire | Agent 请求/typed record/用户/模型结果均无日期字段；原始响应日期显式跳过 | 当前代码使用 `java.util.Date`，wire 未验证 |
| `REQ-TXN-004` | 业务服务最终验证角色 | 统一安全边界拒绝非法 role；Transaction search 入口仍验证 ADMIN/VIEWER 后才调用 service/mapper | 用户确认；L1_02 7.4 |
| `REQ-TXN-005` | 空结果、覆盖与近似总数真实 | 仅 page1 rows空+total0+exact 可为 no-result；非 exact total 不冒充精确 total | 现有 `TransactionSearchResponse` |
| `REQ-TXN-006` | 结果字段最小化 | 用户最多交易 ID 掩码、类型、金额；短于掩码下限的 ID 安全省略；模型候选默认空；日期和所有查询辅助字段零 typed 投影 | L2_02_00 9/11 |
| `REQ-TXN-007` | 状态与失败稳定 | 400 invalid_argument；401/403/429/5xx/timeout 不混淆；非法 2xx 不变 no-result | L2_02_00 12.1 |
| `REQ-TXN-008` | 一次只读 HTTP、禁止聚合与写入 | 每次最多一次 POST `/txn/search`，无 retry/redirect/第二动作；禁止路径 spy 全零 | L1_02 9.3/10.3 |
| `REQ-TXN-009` | 金额条件全链路保持十进制精度 | 最终候选参数以规范字符串进入；validator 生成 finite `Decimal`；wire 为未加引号 JSON number；Java 精确接收 `BigDecimal`，任何路径不得调用 float 或依赖 string coercion | 用户确认；现有 Transaction API/Mapper |
| `REQ-TXN-010` | Transaction 参数由有限本地语法确定性形成 | 匹配交易查询意图时模型调用为零；有限子句形成唯一候选；缺过滤条件、重复/冲突、Date/聚合/写入或格式错误返回 `invalid_argument`，业务 HTTP 为零 | L0 `SA-C-022`；L1_02 `BQ-AD-011`；L2_00_01 `DR-CORE-015～018` |
| `REQ-TXN-011` | 真实Transaction结果外发前形成一次性non-live候选 | generic问题不含具体值；最多1次search和30次answer；只外发`transaction_type/amount`精确facts及公共`coverage.truncated`安全布尔，禁止ID/date/provider coverage计数或总量/聚合；三终态、首outbound消费、retry/resume=0且有限证据不含业务值 | `L2_00_02 REQ-MODEL-012`；`L2_02_00 REQ-BQCOM-020`；`P3_00 GATE-026` |
| `REQ-TXN-012` | Transaction后继出域候选必须绑定answer v2与当前生产组合根 | candidate-02继续保持1次search、30次answer、`transaction_type/amount`唯一facts及精确Decimal；manifest须绑定v2 task/source/new bootstrap和candidate-01历史，不得复用旧authorization | `L2_00_02 REQ-MODEL-013`；`L2_02_00 REQ-BQCOM-027` |
| `REQ-TXN-013` | Transaction后继候选必须在任何类型SELECT/search/model前验证冻结Python运行时来源并形成preflight证据 | candidate-03以全新run/manifest/auth绑定candidate-02初始化失败历史；versioned host launcher先fsync journal，再验证`agent_runtime`从冻结`agent-runtime/src`导入并恢复环境。失败时SELECT/search/model=0且形成有限`failed_unconsumed`证据 | `L2_02_00 REQ-BQCOM-028`；candidate-02 failure SHA-256=`37c4cf079cf1bb28e17c9b087df5707bf19c5bbfd8318d6c3f5f611f08fd72d9` |
| `REQ-TXN-014` | Transaction live候选必须把允许模型事实值与禁止秘密/非模型字段值分开验证 | exact模型载荷仍仅允许`transaction_type/amount`并保留grounding所需确定性`record_ref`；test-only forbidden literal只包含JWT、API key及`transaction_id_masked`等非模型业务字段高熵值，不得包含已获准值或结构引用 | `L2_02_00 REQ-BQCOM-029`；candidate-03失败证据 |
| `REQ-TXN-015` | candidate-04外部的datasource/auth/Transaction服务宿主必须由versioned bootstrap冻结 | wrapper在读取数据库凭据或启动进程前建立耐久lifecycle，绑定candidate-04、bootstrap failure及自身资产；配置解析、auth/Transaction readiness、ADMIN JWT、PID和日志均失败关闭。candidate调用前失败时SELECT/search/model为0且candidate输出不存在 | `L2_02_00 REQ-BQCOM-030`；bootstrap failure SHA-256=`b831d2f9d019fcd3347f389cd92fa00b0fc5e6deee3efd2ff0024c17594c7357` |
| `REQ-TXN-016` | Transaction live bootstrap必须证明实际启动的auth/Transaction JAR身份并在进程提前退出时保留有限可诊断证据 | 新wrapper manifest绑定两个JAR SHA、源码commit与确定性构建命令；启动前重算。原始日志只驻留临时目录并在删除前映射到有限分类，禁止原文、路径、配置/秘密值及其哈希进入证据 | `L2_02_00 REQ-BQCOM-031`；wrapper-v1失败历史 |
| `REQ-TXN-017` | 当前Transaction查询能力验收不依赖真实Transaction结果外部模型稳定性实验 | 系统E2E使用真实`transaction.search` Provider、真实业务授权和默认stub模型，验证精确金额、权限、字段、失败链及禁止能力且模型outbound=0；历史search1+answer30及27/30阈值只属于冻结实验，不是当前P3/P4完成条件 | L1_02 `BQ-AD-012`；L2_02_00 `DR-BQCOM-046` |

### 3.3 范围内

- `transaction.search` descriptor、强类型条件/排序/input、wire request/response、normalizer/provider。
- `TransactionSearchLocalActionResolver` 的有限多子句语法、无匹配/无效裁决、definition 代码绑定和零模型调用测试。
- page1 有界搜索、最多 50 条、现有 total/totalExact 的 coverage 映射。
- `transId/transType/transTypeContains/amount/amountGt/amountLt` 条件和 `transId/transType/amount` 三字段排序。
- Transaction search 入口的最终 Authority 判定建议、字段投影、失败和联调矩阵。
- `GATE-026` 的测试范围candidate-01 non-live准备；不改变生产Adapter/Provider/Model公共契约。

### 3.4 范围外

- 日期条件/排序/typed 输出；detail、condition、query、aggregate、create/update/delete、MQ/Kafka 提交。
- 新增或修改 Transaction 公开 DTO/endpoint、日期格式、数据库查询或分页协议；需另行确认。
- 跨域聚合、跨页遍历、自动翻页、汇总统计和总金额计算。
- Employee、Knowledge、统一 converter 私有实现、DeepSeek Provider/Prompt。
- 模糊 NLU、LLM 参数抽取、任意比较表达式、括号/OR/NOT、跨句或动态字段语法。

### 3.5 非目标

- 不复刻全部 `Transaction` Java DTO，不允许任意 condition map。
- 不在 Adapter 解释 role claim，不把聚合伪装成 search 后处理。
- 不从错误 body 推断 no-result，不因 total 字段存在而生成未请求的聚合答案。

### 3.6 实施剖面

| 剖面 | 适用 | 说明 |
|---|---|---|
| Python | 是 | Transaction definition、DTO、mapper/codec/normalizer、field/provider/config/test |
| Java/API | 是 | 复用 search wire；建议收紧既有 guard 行为，不改 DTO |
| 安全 | 是 | 原用户 JWT、业务动作角色、金额/标识/日志/模型隔离 |
| 数据库/事务 | 条件适用 | Agent 无事务；业务 search 内 count/query 一致性需按现有响应校验 |
| 模型出域 | 条件适用 | 只定义候选；默认空，真实数据外发另受 `SA-GATE-006` |

## 4. 上位约束

| 约束编号 | 上位位置 | 约束 | 本设计落实 | 偏离 |
|---|---|---|---|---|
| `CON-TXN-001` | L1_02 6/7.2 | 独立 Adapter、代码绑定有限动作、配置只收紧 | `DR-TXN-001`、`DR-TXN-002` | 无 |
| `CON-TXN-002` | L1_02 7.3/7.4 | 用户 JWT 透传、业务服务最终授权 | `DR-TXN-003`、`DR-TXN-004` | 无 |
| `CON-TXN-003` | L1_02 7.5/7.6 | typed result、字段交集和模型默认拒绝 | `DR-TXN-005`、`DR-TXN-006`、`DR-TXN-007` | 无 |
| `CON-TXN-004` | L2_02_00 8.5/12.1 | common status mapper 先处理非 2xx | `DR-TXN-008` | 无 |
| `CON-TXN-005` | L1_02 9.3/10.3 | 一次调用、无重试、禁止聚合/写入 | `DR-TXN-009`、`DR-TXN-010` | 无 |
| `CON-TXN-006` | L1_02 13.3 | 日期/接口差距不由域 L2 擅自改公开契约 | `DR-TXN-011` | 无 |
| `CON-TXN-007` | L2_02_00 v0.4 `DR-BQCOM-019` | Core JSON 不接收 Decimal；业务 wire 以专用 ExactDecimal 编码为 JSON number | `DR-TXN-012` | 无 |
| `CON-TXN-008` | L1_02 `BQ-AD-011`；L2_00_01 `DR-CORE-015～018` | 域拥有有限参数语法，Core 拥有多 Resolver 裁决，模型只选能力 ID | `DR-TXN-013` | 无 |
| `CON-TXN-009` | `L2_00_02 DR-MODEL-018`；`L2_02_00 DR-BQCOM-032/043` | 通用问题只允许无具体值的单条交易结果说明；candidate不得扩大search输入、字段矩阵、金额精度或证据内容。prepared阶段真实业务/model调用为0；candidate保持冻结inner authorization，live须由outer wrapper再次绑定`GATE-061`及冻结run/manifest/auth | `DR-TXN-014`,`DR-TXN-019` | `GATE-061/SA-GATE-006/GATE-034` Open；历史`GATE-026`已消费关闭 |
| `CON-TXN-010` | candidate-01 manifest/auth、answer v1源码及Transaction历史不可变；金额/API/字段/grounding不变 | 不得修改candidate-01或用新bootstrap执行旧run。candidate-02已在`GATE-055`下以全新run/manifest/auth冻结；prepared真实search/model为0 | `DR-TXN-015` | `GATE-055` Closed；历史`GATE-026`已消费关闭；`GATE-061/SA-GATE-006/GATE-034` Open |
| `CON-TXN-011` | candidate-02 manifest/auth/launcher及初始化失败证据不可变；一次类型SELECT已使用，search/model=0 | 不得修改candidate-02 launcher、补设调用者环境后重跑或复用其authorization。candidate-03已用versioned test范围资产把preflight置于SELECT前并绑定candidate-01/02历史；生产Adapter/Provider/API/Decimal/字段矩阵不变 | `DR-TXN-016` | `GATE-056` Closed；历史`GATE-026`已消费关闭；`GATE-061/SA-GATE-006/GATE-034` Open |
| `CON-TXN-012` | candidate-03 manifest/auth/host-preflight/host-result/lifecycle/result与六项SHA不可变；SELECT1/search1已使用，run不得重跑 | candidate-04使用全新run/manifest/auth并绑定candidate-03六项历史；不得修改生产Adapter、Provider、API、Decimal、字段矩阵、question policy、validator或grounding，不得把未消费模型授权解释为旧run可复用 | `DR-TXN-017` | `GATE-057` Closed；历史`GATE-026`已消费关闭；`GATE-061/SA-GATE-006/GATE-034` Open |
| `CON-TXN-013` | candidate-04 manifest/auth、15项history、33项asset及latest bootstrap failure evidence不可变 | 不得原地修改candidate-04或临时脚本后直接重跑。wrapper-v2独立manifest绑定自身源码/Schema/tests/JAR、candidate与v1失败证据；数据库配置/JWT/key/type只驻留内存，wrapper仅停止自己的进程，inner candidate唯一拥有SELECT/search/model/consumed语义 | `DR-TXN-018`,`DR-TXN-019` | `GATE-059/060`已控制并关闭两代non-live实现；`GATE-061`控制v2一次性执行；`GATE-034`与`SA-GATE-006[Transaction]`控制完成 |
| `CON-TXN-014` | wrapper-v1 manifest/auth/lifecycle/result/history test精确SHA不可变；candidate-04全部inner输出不存在 | wrapper-v1授权已消费且永久退役。wrapper-v2必须全新run/manifest/auth，绑定v1四项历史和candidate-04；实际JAR、源码及诊断Schema均进入冻结资产。不得修改v1 helper、candidate-04、Adapter/Provider/Decimal/API | `DR-TXN-019` | `GATE-060`控制non-live准备；`GATE-061`控制新一次性live；`GATE-034/SA-GATE-006`继续Open |
| `CON-TXN-015` | L1_02 `BQ-AD-012`；L2_02_00 `DR-BQCOM-046`；P3当前交付周期 | wrapper-v2真实执行与Transaction真实结果模型实验转Deferred；P3 `GATE-061/034`记为Not Applicable且不得复用。历史run/manifest/authorization/evidence保持字节不变 | `DR-TXN-020` | `SA-GATE-006.TRANSACTION`保持Open，只禁止真实Transaction结果外发，不阻塞Provider + stub系统E2E |

### 4.1 端到端追踪矩阵

| REQ/CON | 设计规则 | 责任主体 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|
| `REQ-TXN-001`,`CON-TXN-001` | `DR-TXN-001`、`DR-TXN-002` | provider/组合根 | `IMPL-TXN-001/002/007` | `TEST-TXN-001/002` | `VAL-TXN-001/002` |
| `REQ-TXN-002` | `DR-TXN-002`、`DR-TXN-005` | validator/mapper | `IMPL-TXN-003` | `TEST-TXN-003/004` | `VAL-TXN-001` |
| `REQ-TXN-003`,`CON-TXN-006` | `DR-TXN-005`、`DR-TXN-011` | codec/field registry | `IMPL-TXN-003/005` | `TEST-TXN-005` | `VAL-TXN-001/003` |
| `REQ-TXN-004`,`CON-TXN-002` | `DR-TXN-003`、`DR-TXN-004` | 安全边界/Transaction service | `IMPL-TXN-008/009` | `TEST-TXN-006/007` | `VAL-TXN-003/004` |
| `REQ-TXN-005`,`CON-TXN-003` | `DR-TXN-006` | normalizer | `IMPL-TXN-004` | `TEST-TXN-008` | `VAL-TXN-001/003` |
| `REQ-TXN-006` | `DR-TXN-007` | fields/projector | `IMPL-TXN-005/006` | `TEST-TXN-009/010` | `VAL-TXN-001/002` |
| `REQ-TXN-007`,`CON-TXN-004` | `DR-TXN-008` | status mapper/codec | `IMPL-TXN-003/004` | `TEST-TXN-011` | `VAL-TXN-001/003` |
| `REQ-TXN-008`,`CON-TXN-005` | `DR-TXN-009`、`DR-TXN-010` | common client/architecture | `IMPL-TXN-003/007` | `TEST-TXN-012/013` | `VAL-TXN-002` |
| `REQ-TXN-009`,`CON-TXN-007` | `DR-TXN-005`、`DR-TXN-012` | validator/mapper/codec/common wire encoder | `IMPL-TXN-002/003` | `TEST-TXN-003/004/016` | `VAL-TXN-001/003` |
| `REQ-TXN-010`,`CON-TXN-008` | `DR-TXN-013` | Transaction Resolver/Runtime 混合节点 | `IMPL-TXN-015` | `TEST-TXN-017` | `VAL-TXN-007` |
| `REQ-TXN-011`,`CON-TXN-009` | `DR-TXN-014` | Transaction egress candidate测试切片 | `IMPL-TXN-016` | `TEST-TXN-018` | `VAL-TXN-008` |
| `REQ-TXN-012`,`CON-TXN-010` | `DR-TXN-015` | candidate-01退役与candidate-02 answer v2绑定 | `IMPL-TXN-017` | `TEST-TXN-019` | `VAL-TXN-009` |
| `REQ-TXN-013`,`CON-TXN-011` | `DR-TXN-016` | candidate-02失败归档与candidate-03 host preflight | `IMPL-TXN-018` | `TEST-TXN-020` | `VAL-TXN-010` |
| `REQ-TXN-014`,`CON-TXN-012` | `DR-TXN-017` | candidate-03失败归档与candidate-04安全分类 | `IMPL-TXN-019` | `TEST-TXN-021` | `VAL-TXN-011` |
| `REQ-TXN-015`,`CON-TXN-013` | `DR-TXN-018` | candidate-04外部versioned live bootstrap | `IMPL-TXN-020` | `TEST-TXN-022` | `VAL-TXN-012` |
| `REQ-TXN-016`,`CON-TXN-014` | `DR-TXN-019` | wrapper-v1失败归档与wrapper-v2产物/诊断冻结 | `IMPL-TXN-021` | `TEST-TXN-023` | `VAL-TXN-013` |
| `REQ-TXN-017`,`CON-TXN-015` | `DR-TXN-020` | 当前Transaction交付边界与可选外发实验治理 | `IMPL-TXN-022` | `TEST-TXN-024` | `VAL-TXN-014` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文责任 | 对方责任 | 权限 |
|---|---|---|---|---|
| `L2_02_00` | 直接依赖 | 实例化公共原语 | HTTP/JWT/result/projector/配置算法 | 只读 |
| `transaction-api` | wire contract | 只消费已核实 search 子集 | Java DTO 和兼容性 | 只读 |
| `mq-procedure-service` | 业务权威 | 映射 search，建议动作 guard | Transaction 数据/查询/最终授权 | 设计建议；代码只读 |
| `auth-service/common-security` | 身份权威 | 定义消费矩阵 | role claim/验签/Authority | 只读 |
| core/DeepSeek 边界 | 上下游 | descriptor/安全字段候选 | 单动作 claim、全局出域和 grounding | 默认拒绝 |

## 6. 当前基线与最小变更

### 6.1 已核实事实

| 状态 | 路径/符号 | 事实 | 影响 |
|---|---|---|---|
| 已存在 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/controller/TransactionController.java` `search` | `POST /txn/search` 且调用 `requireUser` | 可复用只读入口 |
| 已存在 | `TransactionService.search` | 至少一条件、page≥1、size 1～100、最多两 sort；count 后 query | Agent 进一步收紧 page/size/fields |
| 已存在 | `transaction-api/src/main/java/com/dylan/transaction/api/query/TransactionSearchRequest.java` | condition 复用宽 Transaction；sort/page/size | 只构造子集，不动态透传 |
| 已存在 | `TransactionSearchResponse.java` | rows/total/totalExact/page/size；非 exact 时 total 是下界 | coverage 必须保真 |
| 已存在 | `Transaction.java` | Date、BigDecimal 及辅助 filter 字段同 DTO | 首期忽略 Date/辅助响应字段 |
| 已存在 | `Transaction.java` `amount/amountGt/amountLt`、`TransactionMapper.xml` 搜索条件 | 三个金额条件均使用 `BigDecimal`，Mapper 已支持 `=/>/<`；service/MySQL contract tests 已证明 50/2 精确比较，受控 runner 证明 JSON number 与 mapper 参数不被改写 | 可复用现有公开 DTO/查询，无需新增 Java 字段或 endpoint；当前目标配置精度链已闭环 |
| 已存在 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java` `requireTransactionRead`；`mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/TransactionSearchSecurityConfiguration.java` | search 专用安全链显式选择共享 Reactive converter，并在 Controller 前与动作 guard 内两层精确要求 `ROLE_ADMIN/ROLE_VIEWER` | Provider 本地与真实 JWT 允许/拒绝矩阵均通过，`SA-GATE-005` 已关闭；其他动作不继承该结论 |
| 已存在 | `common-security` 具名 Servlet/Reactive role converter；`agent-runtime/src/agent_runtime/adapters/transaction` | `role` 可稳定转为 `ROLE_ADMIN/ROLE_VIEWER`；Python Adapter 已实现并保持 fake 默认 | 可恢复 Provider 候选复核；不因此启用真实动作 |
| 已存在 | `mq-procedure-service/src/test/resources/contracts/transaction-amount-column-v1.json` | 项目维护者确认的生产 `springboot_db.t_transaction.AMOUNT` 快照为 `DECIMAL(50,2)` | Runtime 金额契约必须 scale≤2；Agent 整数位上限仍保持 16 位，不扩大到 Provider 的 48 位整数容量 |

### 6.2 最小改造判断

复用 `/txn/search`，不新增接口或 DTO。Python 只构造现有 DTO 的安全子集。金额参数在 Core `JsonObject` 中保持规范字符串，由同一注册项 validator 转为 `Decimal`；mapper 执行范围、scale 和互斥校验，codec 复用 `L2_02_00` v0.4 `BusinessWireJsonEncoder` 把 `ExactDecimal` 写为未加引号 JSON number，禁止 binary float、quoted string coercion 和域内 raw JSON 拼接。Provider 侧已实现动作专用 `requireTransactionRead` 并只替换 search 入口调用，现有 aggregate 继续使用 `requireUser`，避免本设计顺带改变聚合授权。严格 deserializer 直接以 `BigDecimal` 接收 JSON number，service 在 mapper 之前以 `DECIMAL(50,2)` 拒绝 scale>2 或整数位>48 的值，不舍入或截断；Agent 上限仍只允许 16 位整数。日期 wire 没有显式契约测试，因此首期仍排除。搜索已有明确空结果和 400 语义，不需要 Provider 状态改造。

## 7. 责任分解、依赖方向与耦合

### 7.1 责任分解

| 组件 | 唯一职责 | 明确不负责 |
|---|---|---|
| Transaction definition/provider | 冻结一个 action、字段、filter/sort/limits | 聚合、HTTP、安全实现 |
| `TransactionSearchLocalActionResolver` | 以本文有限多子句语法形成搜索候选参数或有限无效原因 | 业务调用、角色判断、模糊 NLU、模型调用、参数最终合法性判定 |
| validator/mapper/codec | 强类型条件→既有 search wire；严格 2xx 解码 | 动态 Transaction map、role、第二请求 |
| normalizer/fields | coverage 和最小结果 | 总金额聚合、日期猜测、业务授权 |
| common handler/client/projector | 一次 JWT HTTP、公共状态/字段交集 | Transaction 端点和字段语义 |
| Transaction Controller/guard/service | 动作角色授权、查询事实和响应 | Agent 配置/模型答案 |

### 7.2 依赖方向与调用边界

```text
agent-runtime RuntimeCompositionRoot
  -> HybridActionSelectionNode
     -> TransactionSearchLocalActionResolver -> ActionCandidate(transaction.search, arguments)
  -> TransactionDomainProvider
     -> CapabilityArgumentValidator -> BoundBusinessActionHandler
        -> TransactionSearchMapper/Codec
        -> UserJwtBusinessHttpClient -> POST mq-procedure-service /txn/search
           -> TransactionReadAccessGuard -> TransactionService -> TransactionMapper
        -> TransactionSearchNormalizer -> common user/egress projectors
```

禁止依赖与绕过：Adapter 不得导入 Employee、Java DTO、Mapper、DB/MQ/Kafka/ES client；core 不得导入 Transaction 字段；配置/模型不得选择 path/method/Date/aggregate；`mq-procedure-service` 不得把 Adapter 投影当授权；模型不得触发自动翻页或第二动作。

### 7.3 内聚与耦合判断

Transaction 条件、wire 和 coverage 随业务 search 契约变化，内聚在 Transaction Adapter；精确十进制 JSON 编码、JWT client、状态和投影留在 business common；角色与数据查询留在业务服务。模块只通过 action definition、现有 JSON wire 和 Authority 可观察契约耦合，不共享私有 DTO。新增金额字段只实例化公共 `ExactDecimal`，不修改 core 或 Employee；后续验证 Date 时仍可只扩展 Transaction definition/codec/test。

## 8. 动作、输入、wire 与字段契约

### 8.1 动作定义

| 定义字段 | 冻结值 |
|---|---|
| `descriptor.capability_id` | `transaction.search` |
| `api_version/kind` | `1/query` |
| `display_name` | `Transaction search` |
| `description` | `按交易标识、交易类型或精确金额条件查询第一页受控交易记录；不提供日期条件、聚合或写入。` |
| `aliases` | `("交易查询","transaction lookup")`；只帮助模型理解，不可作为执行 ID |
| `argument_schema` | 8.2 的固定执行 object schema；无 Schema 默认表达式，`additionalProperties=false`；不发送给模型 |
| 模型选择投影 | 仅 `capability_id/display_name/description/aliases`，tool 参数 Schema 固定为空 object；模型只可返回 `transaction.search` ID，不能返回任何过滤/金额/排序参数 |
| `domain_id/service_key` | `transaction/mq-procedure-service` |
| `answer_mode` | `model_assisted`，但结构化本地结果可独立返回 |
| `applicable_dimensions` | `max_page_size,max_result_count,filter_fields,sort_fields,timeout_ms` |
| filter code set | `trans_id,trans_type,trans_type_contains,amount,amount_gt,amount_lt` |
| sort code set | `trans_id,trans_type,amount` |
| contract limits | `max_page_size=max_result_count=50`；`max_timeout_ms=5000`；`max_request_bytes=4096`（共享 encoder 的安全上限；当前所有合法条件组合的 canonical body 必须严格小于该值）；无 time range；Transaction codec 另拒绝超过262144 raw bytes的已聚合2xx body |
| status semantics | `http_400_is_invalid_argument=true`；`http_204_is_no_result=false`；`http_404_is_no_result=false` |
| required user fields | `transaction_type,amount`；交易 ID 因短值不可安全保留末四位而为可选 |

### 8.2 强类型输入

`CapabilityDescriptor.argument_schema` 固定为下列受控执行 JSON Schema 子集，并且不投影给模型。受控子集不能表达“至少一个条件”、类型条件互斥、contains wildcard 禁止、配置子集和 snake→camel 映射，这些仍由同一注册项 validator/mapper 确定性执行：

```json
{
  "type": "object",
  "properties": {
    "trans_id": {"type":"string","minLength":1,"maxLength":128},
    "trans_type": {"type":"string","minLength":1,"maxLength":128},
    "trans_type_contains": {"type":"string","minLength":1,"maxLength":128},
    "amount": {"type":"string","minLength":1,"maxLength":32},
    "amount_gt": {"type":"string","minLength":1,"maxLength":32},
    "amount_lt": {"type":"string","minLength":1,"maxLength":32},
    "size": {"type":"integer","minimum":1,"maximum":50},
    "sorts": {
      "type":"array","maxItems":2,
      "items": {
        "type":"object",
        "properties": {
          "field":{"type":"string","enum":["trans_id","trans_type","amount"]},
          "direction":{"type":"string","enum":["ASC","DESC"]}
        },
        "required":["field","direction"],
        "additionalProperties":false
      }
    }
  },
  "additionalProperties": false
}
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSearchInput:
    trans_id: str | None = None
    trans_type: str | None = None
    trans_type_contains: str | None = None
    amount: Decimal | None = None
    amount_gt: Decimal | None = None
    amount_lt: Decimal | None = None
    size: int | None = None
    sorts: tuple[TransactionSort, ...] = ()
```

| 类型 | 精确字段 | 不变量 |
|---|---|---|
| `TransactionSort` | `field: Literal["trans_id","trans_type","amount"]`；`direction: Literal["ASC","DESC"]` | tuple 最多2，field唯一 |
| `TransactionSearchCondition` | `trans_id/trans_type/trans_type_contains: str | None`；`amount/amount_gt/amount_lt: Decimal | None` | 至少一项；类型条件互斥；amount 与范围条件互斥；上下界有序；全部已验证并冻结 |
| `TransactionSearchWireRequest` | `condition: TransactionSearchCondition`；`sorts: tuple[TransactionSort,...]`；`page: Literal[1]`；`size: int` | 只由 mapper 构造，size≤有效上限 |
| `TransactionRecord` | `trans_id: str`；`trans_type: str`；`amount: Decimal` | 三字段非空、有界，不含 Date |
| `TransactionSearchWireResponse` | `rows: tuple[TransactionRecord,...]`；`total: int`；`total_exact: bool`；`page: int`；`size: int` | 8.4 coverage 不变量 |

- arguments 只接受 Schema 中 snake_case key；`size/sorts` 省略时 validator 保留 `None`/空 tuple，不从配置或模型补默认条件；未知/重复 key 拒绝，至少一个文本或金额条件非空。
- 标识 NFC/trim 1～128，类型/contains 1～128；禁止控制/Bidi 字符；`trans_type` 与 `trans_type_contains` 互斥。由于现有 SQL `LIKE concat('%', value, '%')` 未转义，`trans_type_contains` 还必须拒绝 `%`、`_` 和反斜线，避免调用方注入通配语义。
- `amount/amount_gt/amount_lt` 只接受 exact string，不接受 JSON number、float、int、bool 或 null。字符串必须匹配 `^-?(0|[1-9][0-9]*)(\.[0-9]{1,2})?$`，禁止前导 `+`、指数、前导零、whitespace、NaN/Infinity；解析后必须 finite、绝对值≤`9999999999999999.99` 且 scale≤2。这只将原 16 位整数+4 位小数边界收紧为 16 位整数+2 位小数，不利用 Provider `DECIMAL(50,2)` 的 48 位整数容量扩大 Agent 范围。`amount` 与 `amount_gt/amount_lt` 互斥；两个范围同时存在时必须 `amount_gt < amount_lt`。任一失败均在 HTTP 前返回 invalid_argument，错误和日志不含原字符串。
- 任意 Date key 仍为 unknown argument 并在 HTTP 前拒绝。配置禁用的任一允许 filter 在 HTTP 前 invalid_argument；配置不能放宽金额 grammar、绝对值或 scale 上限。
- page 不暴露，wire 固定1。mapper 计算 `effective_max=min(settings.max_page_size,settings.max_result_count)`；显式 size 必须为1～effective_max，省略时取 `min(20,effective_max)`，因此配置降低上限不会让所有省略 size 的调用失效。
- sorts 0～2 项，field 只取有效 sort 子集，direction 只允许 `ASC/DESC`；field 不重复。

#### 8.2.1 Transaction 本地 Resolver 有限语法

`TransactionSearchLocalActionResolver` 只解析一个完整的交易搜索句。解析前执行 NFC，并仅从首尾删除 `U+0020/U+3000`；识别 Transaction 意图后出现控制字符、Bidi override/isolate 或超过 Core 问题上限时返回 `invalid(malformed_value)`。有限语法为：

```text
SP       := 0..4 个 U+0020 或 U+3000
POLITE   := "请" | "请帮我" | ε
INTENT   := "查询交易" | "交易查询" | "查询交易记录" | "交易记录查询"
HEADSEP  := 1..4 个空格 | SP ("," | "，" | ";" | "；") SP
CLAUSESEP:= SP ("," | "，" | ";" | "；") SP
EXACTOP  := "为" | "是" | "=" | ":" | "："
GTOP     := "大于" | ">"
LTOP     := "小于" | "<"
PUNCT    := "。" | "？" | "?" | ε
QUESTION := POLITE SP INTENT HEADSEP CLAUSE (CLAUSESEP CLAUSE){0,7} PUNCT
```

语法实现必须使用锚定整串的确定性扫描：固定 token 在当前位置按最长已列字面量匹配，`请帮我` 优先于 `请`，较长 `INTENT` 优先于其前缀。`HEADSEP` 先读取意图后的结构区；若存在逗号/分号则消费该单一标点及两侧各 0～4 个结构空格，否则必须消费 1～4 个结构空格。随后只按未转义的 `,`、`，`、`;`、`；` 切分子句；引号和转义不是语法的一部分，空子句、连续分隔符或 9 个以上片段失败关闭。末尾只允许先剥离恰好一个 `PUNCT`，剥离后再次以终止标点结尾视为附加语法；其他位置的终止标点属于所在文本值并由最终 validator 或禁项规则处理。任一结构位置连续空格超过 4 个或整串解析后仍有未消费字符均失败关闭。

`CLAUSE` 只允许下表形式；每个片段从头按最长 label/operator token 解析，结构性 `SP` 被删除，`VALUE` 是 operator 后到片段末尾的非空全部文本（仅删除 0～4 个结构性尾空格）。文本值除该结构空格外不归一化；金额 token 不转换为 float/Decimal，直接以原字符串进入最终候选：

| 输入子句 | 输出 key/value | 额外约束 |
|---|---|---|
| `("交易号"|"交易标识") SP EXACTOP SP VALUE` | `trans_id: VALUE` | VALUE 非空；最终 validator 执行文本边界 |
| `"交易类型" SP EXACTOP SP VALUE` | `trans_type: VALUE` | VALUE 非空 |
| `"交易类型" SP "包含" SP VALUE` | `trans_type_contains: VALUE` | VALUE 非空；最终 validator 拒绝 `%/_/反斜线` |
| `"金额" SP EXACTOP SP DECIMAL` | `amount: DECIMAL` | DECIMAL 必须先匹配 8.2 的 canonical grammar，否则 malformed |
| `"金额" SP GTOP SP DECIMAL` | `amount_gt: DECIMAL` | 同上 |
| `"金额" SP LTOP SP DECIMAL` | `amount_lt: DECIMAL` | 同上 |
| `"条数" SP EXACTOP SP UINT` | `size: int(UINT)` | UINT 只含 ASCII 数字、无前导零且 1～50；配置更小上限由最终 validator/mapper 执行 |
| `"排序" SP EXACTOP SP SORTFIELD SP SORTDIR` | 在 `sorts` 追加一项 | SORTFIELD=`交易号/交易类型/金额` 映射 `trans_id/trans_type/amount`；SORTDIR=`升序/降序` 映射 `ASC/DESC`；最多两项且 field 唯一 |

裁决规则固定如下：

- 规范化问题不以可选 `POLITE+SP` 后的任一 `INTENT` 开始时返回 `no_match`；全局敏感问题闸门仍独立阻止具体交易内容进入模型。
- 识别意图后必须包含 1～8 个完整子句且至少一个文本或金额过滤条件；只有 size/sort、缺 label/operator/value、空子句或终止标点后仍有文本分别返回 `invalid(missing_required/malformed_value/unsupported_clause)`。
- 同一输出 key 重复或 sort field 重复返回 `invalid(duplicate_argument)`；`trans_type` 与 `trans_type_contains`、`amount` 与任一范围条件同时出现，以及范围下界不小于上界，返回 `invalid(conflicting_argument)`，不得交给模型修补。
- Date、detail、聚合/合计/平均/趋势、分页/翻页、OR/NOT、括号表达式、创建/更新/删除/MQ/Kafka 或任何未列子句返回 `invalid(unsupported_clause)`；模型与业务 HTTP 均为零。
- 唯一合法 Resolver 结果为 `candidate(arguments=<按输入子句顺序构造的冻结 JsonObject>)`；目标 ID 只由同一对象的 `capability_id="transaction.search"` 属性提供，混合节点据此构造最终 `ActionCandidate`。Resolver 不读取配置/JWT/角色，不访问网络/时钟，不记录 question/值，不调用 validator、handler 或模型。
- Runtime 随后执行公共 JSON 结构/大小/深度校验、`TransactionSearchArgumentValidator`、配置收紧和单动作 claim；Resolver 的数值/互斥预检是早拒绝，不替代最终权威。

### 8.3 HTTP wire request

唯一请求为 `POST /txn/search`：

```json
{
  "condition": {
    "amountGt": 100.01,
    "transType": "PAY"
  },
  "page": 1,
  "size": 20,
  "sorts": [{"direction":"DESC","field":"amount"}]
}
```

snake_case 条件/排序必须由 codec 显式映射为 Java wire 名：`trans_id→transId`、`trans_type→transType`、`trans_type_contains→transTypeContains`、`amount→amount`、`amount_gt→amountGt`、`amount_lt→amountLt`，排序字段 `trans_id→transId`、`trans_type→transType`、`amount→amount`。空条件字段必须省略，不发送 null、Date 条件、响应专用字段或任意 unknown key。

金额在 capability arguments 中是字符串，但进入 `TransactionSearchInput/Condition` 后必须是 `Decimal`；codec 只能调用 `ExactDecimal.from_decimal` 和 `BusinessWireJsonEncoder.encode(..., max_bytes=4096)`，因此上例 `amountGt` 是未加引号的 JSON number。`"100.10"` 可在通过 scale 校验后规范编码为 `100.1`，`-0/0.0` 统一为 `0`；`"100.010"` 因 scale=3 必须在 HTTP 前拒绝，不得删除尾零后放行。禁止 `float()`、`json.dumps(default=str)`、quoted decimal、手写字符串拼接或绕过 `CanonicalBusinessJsonBody`。body 按公共 v0.4 的唯一 Unicode/key/number 规则、无多余空白编码，unique keys、UTF-8且≤4096 bytes；无 query 和自定义 header。上例因而使用顶层 `condition,page,size,sorts`、condition `amountGt,transType` 和 sort item `direction,field` 顺序。Transaction 域测试必须以所有合法条件组合中 canonical bytes 最大的一组证明长度严格小于4096；4096/4097 总字节边界由 `TEST-BQCOM-003/014` 直接构造共享 business-wire body 验证，域测试不得绕过 `TransactionSearchWireRequest` 不变量伪造超长请求。

### 8.4 2xx wire response 与 coverage

顶层必须是 object，且除 `rows,total,totalExact,page,size` 外的字段一律拒绝；要求 rows 为 array、page/size/total 为 exact int（bool 不得视为 int）、totalExact 为 exact bool、page与同一次 `TransactionSearchWireRequest.page` 精确相等、size与同一次request.size精确相等、`0≤total≤9223372036854775807`、rows数量≤request.size。每行必须是 object，只复制 `transId/transType/amount`；仅当前 `Transaction` 已核实的 `transDate,transDateGt,transDateLt,amountGt,amountLt,transTypeContains` 可作为宽 row 兼容例外存在于受限临时 JSON object，其他未知 row 字段拒绝。三目标字段必须存在、非 null 且类型正确；ID/type NFC 后1～128且无控制/Bidi。strict decoder 使用 `parse_float=Decimal`、`parse_int=int`、拒绝 NaN/Infinity/duplicate/BOM/trailing；amount只接受exact int（非bool）或Decimal并转为finite Decimal，绝对值≤`9999999999999999.99`、小数位≤2，不得经过float。这与已确认的 Provider `DECIMAL(50,2)` 输出边界保持一致，不将响应放宽为请求不可表达的 scale 3～4。body>262144 bytes或rows>request.size整体invalid_response；codec不得以可变实例字段保存“上次请求”，common客户端仍先受全局response cap约束。

normalizer 规则：

- rows 空、total=0、totalExact=true → `no_result(returned=0,truncated=false,total_count=0)`。
- rows 非空、totalExact=true → records；要求 `rows数=min(total,size)`，`total_count=total`，`truncated=(rows数<total)`；page1 出现不足页但 total 声称更多时视为 count/query 矛盾。
- rows 非空、totalExact=false → records；`total_count=None,truncated=true`，保留“不完整”而不把 total 下界当精确值。
- rows 空但 total>0 或 totalExact=false、page/size 不回显、任一行不合法 → invalid_response。

### 8.5 字段目录与转换

| field_id | source | value_type | class | user | model candidate | allowed user transforms | allowed model transforms |
|---|---|---|---|---:|---:|---|---|
| `transaction_id_masked` | `transId`；仅长度5～128时 extractor 返回值，1～4时返回 `None` | `identifier` | `transaction_identifier` | 是/可选 | 否 | `{mask_keep_last4}` | `{}` |
| `transaction_type` | `transType` | `text` | `business_internal` | 是/必需 | 是 | `{bounded_text}` | `{bounded_text}` |
| `amount` | `amount` | `decimal` | `financial_value` | 是/必需 | 是 | `{decimal_2}` | `{decimal_2}` |

表中顺序就是冻结 field definition、用户结果和 facts 顺序。`transaction_id_masked` 对1～4位 ID 安全省略，不定义公共转换之外的短值特例；5～128位时严格复用 `mask_keep_last4`。模型字段代码候选是 `transaction_type,amount`，动作配置默认空，且仍受全局规则交集。`decimal_2` 使用 Decimal 并精确采用 `ROUND_HALF_UP`，不得经过 float；交易 ID 永不成为模型候选。用户结果 coverage 可携带 provider 返回的 exact `total_count`，但这不是第二次聚合调用；模型 facts 不含 coverage，答案不得生成合计、平均、趋势或把非 exact 下界表述为总数。

## 9. 详细功能与处理流程

### 9.1 设计规则

| 规则编号 | 规则 | 责任主体 | 效果 |
|---|---|---|---|
| `DR-TXN-001` | 只定义并注册 `transaction.search@1` | provider/组合根 | 动作有限 |
| `DR-TXN-002` | 配置只能禁用、缩小 filter/sort/size/result/timeout/字段，不能放宽金额 grammar/range/scale 或增加 Date/路径/动作 | settings/provider | 配置不扩权 |
| `DR-TXN-003` | Adapter 只透传当前 user JWT，不解析 role、不使用 service token | handler/client | 身份不替换 |
| `DR-TXN-004` | 统一边界先验证 role；Transaction search 再要求 ADMIN/VIEWER Authority 后调用 service | common-security/业务入口 | 最终动作授权 |
| `DR-TXN-005` | validator/mapper 执行文本与金额条件互斥、金额范围、filter/sort/page/size 收紧并只构造无 Date 的现有 DTO 子集；codec 显式完成 snake→camel 映射 | validator/mapper/codec | 请求有界且不降精度 |
| `DR-TXN-006` | normalizer 严格解释 rows/total/exact/page/size，非 exact total 不进入 total_count | normalizer | coverage 真实 |
| `DR-TXN-007` | 用户仅三字段，模型默认空；模型结果不得生成聚合/全量结论 | fields/egress | 字段和语义收紧 |
| `DR-TXN-008` | 400/401/403/429/5xx 由 common 固定映射，域不读错误 body | status mapper | 状态稳定 |
| `DR-TXN-009` | 一次动作最多一个 POST，共享绝对截止，无 retry/redirect/cache/自动翻页 | handler/client | 资源有界 |
| `DR-TXN-010` | 所有非 search 路径和 MQ/Kafka/aggregate 代码在 Adapter 架构测试中不可达 | codec/architecture | 无副作用/聚合 |
| `DR-TXN-011` | Date 输入/输出保持代码禁用，只有 wire 契约和时区测试确认后才可另行设计扩展 | definition/codec | 不猜日期 |
| `DR-TXN-012` | amount 三参数在 Core 边界只接受规范 decimal string，validator 转为 exact `Decimal`；codec 只经公共 `ExactDecimal`/encoder 输出 JSON number，Java 以现有 `BigDecimal` 接收；禁止 float、quoted coercion 和 raw JSON 拼接 | validator/codec/common wire encoder | Python/JSON/Java 金额精度一致 |
| `DR-TXN-013` | `TransactionSearchLocalActionResolver` 只实现 8.2.1 的有限纯函数语法；无匹配不造参数，识别后的缺失/重复/冲突/禁止子句失败关闭，金额保持 canonical string；配置、模型和业务服务均不能修改语法 | Transaction Adapter/Runtime 混合节点 | 业务参数在本地确定，模型调用为零；最终 Schema/validator/配置/单动作约束保持权威 |
| `DR-TXN-014` | Transaction egress candidate-01绑定`question-egress-v2`、生产Transaction/Business/Model接缝、`WP-TXN-REAL-01`证据与直接测试；固定generic无值问题、`size=1`、单个`trans_type`等值条件、search 0/1、answer最多30次且有效至少27次。live条件值只从进程级`TRANSACTION_EGRESS_LIVE_TEST_TYPE`读取并驻留内存，manifest只绑定输入契约版本，有限证据禁止保存值或值哈希。只允许单条`transaction_type/amount`精确facts；公共`coverage.truncated`安全布尔可进入模型供grounding，ID/date/provider coverage计数或总量/聚合和值不得进入facts或有限证据；search前fsync lifecycle，字段校验后且首次model outbound前消费，终态仅`passed/failed_unconsumed/failed_consumed`，retry/resume=0。prepared只用synthetic/fake并冻结run/manifest/auth；真实search/DeepSeek须另行精确授权`GATE-026` | Transaction测试范围candidate/launcher/Schema/manifest/auth/history | 一次性外发候选可审计且不改生产域契约；non-live外部调用0 |
| `DR-TXN-015` | candidate-01 run/manifest/auth虽未消费，但其manifest冻结的是answer v1与旧bootstrap。`L2_00_02 DR-MODEL-019`要求生产组合根唯一切换到answer v2后，旧candidate的current-source身份不再成立，必须永久退役而不能原地重算manifest或复用authorization。candidate-02须使用全新run/manifest/auth，绑定answer v2 task/source、新bootstrap、candidate-01精确历史、`WP-TXN-REAL-01`授权/精度证据和既有Transaction/Business接缝；保持generic问题、1次search、30次answer、`transaction_type/amount`、Decimal、三终态、首outbound消费和有限证据完全不变。prepared只用fake/static并证明真实search/model=0；正式live仍须另行精确授权`GATE-026` | 已新增candidate-02 test-only module/launcher/Schema/manifest/auth/history并完成冻结 | 以新候选承接模型task升级，不改变Transaction域契约或历史 |
| `DR-TXN-016` | candidate-02冻结launcher的pytest子进程没有显式导入当前仓库`agent-runtime/src`，唯一执行在collection阶段失败；一次只读类型SELECT已先发生，但candidate lifecycle/consumed/result不存在且search/model=0。candidate-02 manifest/auth/launcher及post-run failure evidence须按精确SHA永久保持，不得通过设置外部`PYTHONPATH`重跑。candidate-03使用全新run/manifest/auth，绑定candidate-01历史与candidate-02 manifest/auth/failure。versioned host launcher在读取类型/JWT/密钥和任何SELECT前exclusive-create+fsync preflight journal，以作用域受控导入路径启动Python smoke并验证`agent_runtime.__file__`位于冻结仓库`agent-runtime/src`，finally恢复环境；import、collection、资产或环境失败均写严格有限`failed_unconsumed`结果且SELECT/search/model=0。只有preflight终态通过后，未来精确授权才可执行一次只读类型SELECT、最多1次search和30次answer。candidate-03不得改变type/amount、Decimal、字段交集、grounding、三终态、首model outbound消费、retry/resume=0及敏感值零持久化 | 已新增candidate-03 test-only host/preflight、versioned launcher、四份strict Schema、manifest/auth及direct/history/live-opt-in tests；生产src/API不变 | 修复测试启动边界，不改变Transaction域能力；`GATE-056` Closed只控制non-live准备，live仍受新`GATE-026`授权 |
| `DR-TXN-017` | candidate-03唯一执行已完成SELECT1/search1，但live test把`transaction_type`及`domain_result`所有字符串/整数递归加入`forbidden_literals`；这与获准模型facts精确包含`transaction_type/amount`并携带grounding所需`record_ref`矛盾，导致第一次model delegate前本地拒绝并形成`failed_unconsumed/model_call_failed`，consumed与answer事件均不存在。candidate-03六项资产/证据与精确SHA必须永久只读且不得重跑。candidate-04使用全新run/manifest/auth，继续绑定answer v2、当前生产bootstrap、host preflight、1次search/30次answer、Decimal、字段交集、三终态及首outbound消费。test-only检查必须由exact payload key与field ID决定允许字段；forbidden literal仅接收JWT、API key和非模型业务字段的高熵字符串值，例如`transaction_id_masked`，不能接收获准type/amount或确定性`record_ref`，也不能对子串低熵整数/布尔元数据作替代性扫描。fake必须使用live同源构造证明允许值与record_ref可到delegate，任何JWT/key/非模型字段值或未知payload key仍在delegate前失败 | 建议新增candidate-04 test-only module/live harness/host launcher/Schema/manifest/auth/history；生产src/API不变 | 只修复测试安全分类自相矛盾，不扩大Transaction模型字段或业务动作；`GATE-057`关闭后仍须新`GATE-026` |
| `DR-TXN-018` | Transaction live bootstrap使用独立run/manifest/authorization，精确绑定candidate-04 manifest/auth、bootstrap failure SHA、versioned wrapper/helper、strict lifecycle/failure Schema、direct/history tests及source commit；candidate-04字节不变。wrapper在任何配置值读取前exclusive-create+fsync lifecycle，按asset preflight、datasource/auth配置解析、随机HMAC、auth启动/readiness/login、Transaction启动/readiness、candidate调用和cleanup顺序记录started/terminal。datasource只按固定`spring.datasource.url/username/password/driver-class-name`键解析，缺失/重复/非法即失败，不用脆弱的跨行正则猜测；值不进入日志/证据。Transaction服务固定受控端口8182，auth固定8090，readiness只能证明本次PID监听，不调用search。ADMIN JWT、数据库凭据、类型和key只驻留内存并作用域传给既有candidate-04 launcher。任何candidate调用前失败形成`failed_pre_candidate_unconsumed`有限evidence，candidate host/lifecycle/consumed/result不存在且SELECT/search/model=0；进入candidate后outer不得复制SELECT/search/model或consume计数。wrapper只停止自己启动且PID/监听归属核实的进程，扫描并删除临时原始日志。non-live仅用fake process/HTTP/config/filesystem覆盖正常与逐阶段失败、配置重复/缺失、PID不匹配、日志泄漏和candidate零调用 | 建议新增Transaction bootstrap module、versioned PowerShell launcher、strict Schema/manifest/auth和direct/history tests；复用公共bootstrap helper | 修复candidate前未冻结的环境宿主，不修改Transaction生产代码、API、Decimal、字段或candidate-04；`GATE-059`关闭后可冻结wrapper，`GATE-026`只授权其一次执行，成功仍由`GATE-034/SA-GATE-006[Transaction]`判定 |
| `DR-TXN-019` | wrapper-v1唯一执行已形成outer lifecycle/result并在`auth_readiness`以`process_exited`失败；两文件与manifest/auth由独立history test按精确SHA冻结，candidate-04未调用且host/lifecycle/consumed/result均不存在。v1 run与`GATE-026`授权不得重跑、补跑、续跑或改判。wrapper-v2必须沿用candidate-04及v1 outer/inner权威边界，但使用新run/manifest/auth；不修改v1公共helper或任何v1资产。v2 manifest除tracked source/Schema/tests/history外，必须把`auth-service/target/auth-service-0.0.1-SNAPSHOT.jar`与`mq-procedure-service/target/mq-procedure-service-0.0.1-SNAPSHOT.jar`作为本地执行资产记录精确SHA-256，并记录产生这两个JAR的确定性Maven命令、源码commit；执行前任一缺失/漂移都在`asset_preflight`失败且不启动进程。v2 cleanup在既有秘密扫描和原始日志删除前，按strict有限规则对已退出进程日志仅输出`configuration_binding/class_loading/port_binding/dependency_connectivity/application_context/unknown`之一及exitCodePresent布尔，禁止保存exit code值、原文、异常、路径、配置、用户名、密码、JWT、key、类型、数据库值或任何秘密哈希；不确定必须`unknown`。该diagnostic不改变outer result的`process_exited`语义，不得用分类结果自动修复或重试。fake/static须覆盖JAR漂移、各分类、unknown、秘密零持久化、原日志删除和candidate零调用；冻结后只能申请新`GATE-061`，不得重新打开`GATE-026` | 建议新增独立v2 Transaction bootstrap/profile/launcher、diagnostic Schema、direct/history/preparation tests和manifest/auth；JAR只在本地构建/校验，不提交 | 修复外层运行产物身份和可诊断性，不改变Transaction业务/模型契约；`GATE-060`只允许non-live，`GATE-061`才允许唯一live，完成仍由`GATE-034/SA-GATE-006`判定 |
| `DR-TXN-020` | 当前交付周期严格分离执行许可、实验验收和工作包状态。`WP-TXN-EGRESS-01`转Deferred，P3 `GATE-061/034`为Not Applicable；不得修改wrapper-v1失败、wrapper-v2冻结、candidate-04或任何历史资产，也不得把历史30/27阈值解释为已达到。历史run、manifest、hash、candidate、JAR与HEAD只作审计，不是当前执行入口或可复用授权。`WP-SYSTEM-E2E-01`直接依赖已完成的`WP-TXN-REAL-01`，以真实Provider、真实ADMIN/VIEWER授权、精确Decimal链和默认stub模型验证Transaction链路，模型outbound固定0。`SA-GATE-006.TRANSACTION`继续Open；未来恢复真实外发须先诊断，仅在新的未决决策或安全边界存在时新建工作包和有界门禁，并优先复用通用受控harness、全新run/authorization | 设计/计划治理，无Transaction生产代码、API、DTO、数据库、Decimal、配置或测试资产修改 | 恢复当前系统闭环且不削弱真实Transaction数据默认不外发边界；历史实验可审计性保持，测试治理不再自动扩张 |

### 9.2 正常序列

1. Runtime 混合节点按 canonical ID 调用本地 Resolver；命中 8.2.1 时形成 `transaction.search` 最终候选且模型调用为零，识别但无效则返回 `invalid_argument` 且 HTTP 为零。
2. core 对最终候选执行公共 JSON 结构/大小/深度校验、同一注册项 validator 和单动作 claim，产生 typed input；本地解析不能绕过该步骤。
3. handler 校验 context/token/deadline；validator/mapper 依据冻结 settings 再校验文本/金额条件和排序，金额保持 `Decimal`。
4. codec 通过公共 exact-decimal encoder 构造唯一 POST body，common client 向绑定 service origin 发送一次原用户 JWT。
5. 统一安全边界及 Transaction search guard 在 service 前完成角色验证；拒绝时 mapper/DB 为零。
6. `TransactionService.search` 最多执行 count/query 并返回现有 typed response。
7. Adapter 校验响应/coverage，只提取三字段；空与 records 按 8.4 映射。
8. user projector 生成掩码/decimal 结果；egress 默认空并直接返回结构化本地结果。

### 9.3 配置

建议新增动作前缀 `AGENT_TRANSACTION_SEARCH_`：

| key | 默认 | 约束 |
|---|---|---|
| `AGENT_TRANSACTION_SEARCH_ENABLED` | `false` | 真实门禁关闭前不得 true |
| `AGENT_TRANSACTION_SEARCH_TIMEOUT_MS` | `3000` | 100～5000 |
| `AGENT_TRANSACTION_SEARCH_MAX_PAGE_SIZE` | `20` | 1～50 |
| `AGENT_TRANSACTION_SEARCH_MAX_RESULT_COUNT` | `20` | 1～50；有效 size 取二者较小值 |
| `AGENT_TRANSACTION_SEARCH_FILTER_FIELDS` | 六个代码条件 | 只能取 `trans_id,trans_type,trans_type_contains,amount,amount_gt,amount_lt` 子集且非空；不能放宽金额 grammar、16 位整数+2 位小数范围或 scale≤2 |
| `AGENT_TRANSACTION_SEARCH_SORT_FIELDS` | 三个代码排序字段 | 只能取子集，可空 |
| `AGENT_TRANSACTION_SEARCH_USER_FIELDS` | 三字段 | 子集且保留全部 required |
| `AGENT_TRANSACTION_SEARCH_MODEL_FIELDS` | 空 | 仅 type/amount 子集 |
| `AGENT_TRANSACTION_SEARCH_USER_TRANSFORMS` | 代码表固定 | 每用户字段恰一允许枚举 |
| `AGENT_TRANSACTION_SEARCH_MODEL_TRANSFORMS` | 空 | 每模型字段恰一允许枚举 |

service origin 只由组合根 `mq-procedure-service` binding 提供。未知 key、空 filter 集、Date 字段、移除 required、非法 sort/transform 或上限扩大均阻止 Runtime 就绪。

## 10. 失败类型、权限与审计

### 10.1 失败类型与错误码矩阵

| 触发 | Service result | 公共结果 | HTTP/模型 |
|---|---|---|---|
| context/token 缺失 | unauthenticated | `business.missing_user_token` | 0/0 |
| token 认证失败 | unauthenticated | `business.downstream_unauthenticated` | ≤1/0 |
| role/动作 Authority 拒绝 | forbidden | `business.downstream_forbidden` | ≤1；service/DB0；模型0 |
| typed input/config filter 非法 | invalid_argument | `business.invalid_arguments` | 0/0 |
| Transaction 400 | invalid_argument | `business.invalid_arguments` | 1/0 |
| rows空且 exact total0 | no_result | no_result | 1/0 |
| 合法 records | records | success | 1/0或1 |
| 非法 2xx/204/body超限 | downstream_failure(`invalid_response`) | `business.invalid_response` | 1/0 |
| 404（未声明 no-result） | downstream_failure(`unavailable`) | `business.downstream_failure` | 1/0 |
| timeout/429/5xx/connect | typed common failure | common 固定 code | ≤1/0 |

### 10.2 权限与审计

已实现 `CapabilityAccessGuard.requireTransactionRead(Authentication)`：先调用现有 `requireUser(authentication)`，再从 `authentication.getAuthorities()` 中要求至少一个 authority 精确等于 `ROLE_ADMIN` 或 `ROLE_VIEWER`，否则抛无敏感正文的403。原始 role 的缺失/未知/大小写错/混合未知由统一 reactive converter 在 Controller 前整体403；guard 不解析 claim、不改大小写、不按用户名判断。`TransactionController.search` 已从 `requireUser` 改为 `requireTransactionRead`，且位于 `TransactionService.search` 前；aggregate 和其他入口没有随本切片修改。拒绝时 service/mapper 为零。

Adapter 投影不能证明业务数据可见性。`BQ-GATE-003` 关闭前，Transaction 方须以 versioned、无真实值的 provider fixture 冻结 `/txn/search`、允许角色 `ADMIN/VIEWER`、`TransactionSearchResponse` 顶层字段、`Transaction` 可序列化属性全集及 policy version，并由维护者确认两个角色均可接收包含 `transDate` 的现有 wire 响应；provider contract test 应使用所有属性均为合成非空值的 `Transaction`，避免 Jackson null inclusion 让测试漏掉潜在字段，再把序列化字段集合与 fixture 精确比较。若不能确认，须另行设计窄 row DTO，本文修订前不得真实接线。

日志只允许 correlation ID、动作 ID、有限 filter/sort ID（不含值）、page size、returned count、truncated/exact 状态、耗时和 snapshot ID。禁止 JWT、subject、条件值、交易 ID（含掩码）、金额、类型文本、请求/响应 body、URL query、异常 message/stack。真实数据和具体交易问题进入 DeepSeek 前仍受 `CR-GATE-003/SA-GATE-006`。

### 10.3 事务边界与一致性

Agent 无事务、持久化、缓存或重试。业务 search 当前先 count 后 query，代码未证明两次读取位于同一数据库快照；Adapter 不伪造强一致性。它只验证响应内部不变量，`totalExact=false` 时不输出精确 total；并发变更造成 rows空但 total>0 等矛盾时失败为 invalid_response。若未来要求快照一致或 cursor，必须由业务服务另行设计，不能在 Adapter 重查补偿。

## 11. 数据生命周期、发布与回滚

### 11.1 数据生命周期

输入条件、canonical request、原始 2xx body和 typed rows 只在单次请求内存中存活。原始 body 先由 common 客户端按 `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` 聚合，Transaction codec 只接受≤262144 bytes，并可能短暂构造包含 Date/辅助字段的 JSON object；复制三字段 typed rows 后必须解除原始 bytes/object 引用。原始交易 ID、金额和类型不持久化/缓存/日志。用户结果只保留可安全掩码的 ID、类型和金额；模型 safe payload 即使获准也无 ID，且只存在于一次模型调用。

### 11.2 发布与回滚

1. synthetic fake 先完成规范金额字符串→Decimal→精确 JSON number 请求、Decimal 响应、coverage、禁止路径和模型零调用测试。
2. 在修改 search guard 前盘点现有 `/txn/search` 调用方及其角色；不能证明合法调用方满足新角色契约时，`BQ-GATE-003` 不得关闭。
3. 单独实施统一 reactive converter、Transaction search guard 和 response visibility fixture，并回归现有 search/aggregate；Agent 不调用 aggregate且 aggregate授权不随本切片变化。
4. provider/consumer、真实角色、BigDecimal 请求反序列化、数据库比较、禁止接口与日志矩阵现已通过；允许受控目标配置启用真实 search 及金额条件，默认配置与 Date 仍禁用。
5. Agent 侧回滚将 `AGENT_TRANSACTION_SEARCH_ENABLED=false` 并重启 Runtime。Provider guard 事故先停用 Agent并阻断非预期 search 流量，再由 Transaction 方决定 provider 版本回滚；不得把恢复“任意 authenticated 用户可查询交易”作为自动降级，也不得切换到 detail/query/condition/aggregate。

本文不含数据迁移。Date、窄响应、cursor 或权限响应变化均需独立公开契约设计和兼容回滚。

## 12. 实现落点与关键签名

### 12.1 实现落点

| 编号 | 状态 | 路径/符号 | 责任 | 规则 |
|---|---|---|---|---|
| `IMPL-TXN-001` | 已实现 | `agent-runtime/src/agent_runtime/adapters/transaction/definition.py` | descriptor/limits/filter/sort/fields | `DR-TXN-001/002` |
| `IMPL-TXN-002` | 已实现 | `agent-runtime/src/agent_runtime/adapters/transaction/contracts.py` | 含 Decimal 金额条件的 input/sort/wire/record | `DR-TXN-001/005/006/012` |
| `IMPL-TXN-003` | 已实现，本次收紧 | `agent-runtime/src/agent_runtime/adapters/transaction/codec.py` | scale≤2 decimal string validator、mapper、公共 exact-decimal POST encode、scale≤2 2xx decode | `DR-TXN-002/005/008/011/012` |
| `IMPL-TXN-004` | 已实现 | `agent-runtime/src/agent_runtime/adapters/transaction/normalizer.py` | rows/total/exact→service result | `DR-TXN-006/008` |
| `IMPL-TXN-005` | 已实现 | `agent-runtime/src/agent_runtime/adapters/transaction/fields.py` | 三字段/转换/无 Date | `DR-TXN-007/011` |
| `IMPL-TXN-006` | 已实现 | `agent-runtime/src/agent_runtime/adapters/transaction/settings.py` | 精确 env fragment/default | `DR-TXN-002/007` |
| `IMPL-TXN-007` | 已实现 | `agent-runtime/src/agent_runtime/adapters/transaction/provider.py` | TransactionDomainProvider | `DR-TXN-001/009/010` |
| `IMPL-TXN-008` | 已实现 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java` | Transaction 读 Authority 判断 | `DR-TXN-004` |
| `IMPL-TXN-009` | 已实现 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/controller/TransactionController.java` `search` | search 前调用动作 guard | `DR-TXN-004` |
| `IMPL-TXN-010` | 已实现 | `mq-procedure-service/src/test/resources/contracts/transaction-search-response-visibility-v1.json` | endpoint/角色/顶层与 row 完整字段/policy version；无业务值 | `DR-TXN-004/006/011` |
| `IMPL-TXN-011` | 已实现 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/TransactionSearchSecurityConfiguration.java` | 仅 `POST /txn/search` 使用共享 Reactive converter 并要求 `ROLE_ADMIN/ROLE_VIEWER`；其他入口保持 fallback 链 | `DR-TXN-004` |
| `IMPL-TXN-012` | 已实现 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/config/TransactionSearchJsonConfiguration.java`；`mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/web/TransactionSearchRequestDeserializer.java` | 仅 search DTO 的 amount 字段接受 JSON number 并直接构造 `BigDecimal`，拒绝 quoted amount | `DR-TXN-005/012` |
| `IMPL-TXN-013` | 已实现 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/service/TransactionAmountContract.java`；`TransactionService.validateSearchRequest` | mapper 前拒绝超过 `DECIMAL(50,2)` 的 scale/整数位，不修改原 `BigDecimal` | `DR-TXN-005/012` |
| `IMPL-TXN-014` | 已实现 | `mq-procedure-service/src/test/resources/contracts/transaction-search-callers-v1.json`；`transaction-amount-column-v1.json` | 冻结静态调用方盘点和项目维护者确认的生产列 precision/scale 快照 | `DR-TXN-004/012` |
| `IMPL-TXN-015` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/action_resolver.py` `TransactionSearchLocalActionResolver`；修改 `definition.py/provider.py` 绑定 | 实现 8.2.1 有限多子句语法并返回公共 `LocalActionResolution`；definition 代码绑定同 ID Resolver | `DR-TXN-013` |
| `IMPL-TXN-016` | 建议新增 | `agent-runtime/tests/integration/adapters/transaction/egress_candidate.py`、candidate preparation/live opt-in/history测试、`agent-runtime/scripts/run-transaction-egress-live-candidate-01.ps1`、strict Schema、manifest/auth | 复用生产Business/Transaction/Model接缝，实施1/30预算、三终态、首outbound消费、字段/值零持久化和fake故障注入 | `DR-TXN-014` |
| `IMPL-TXN-017` | 已完成（test-only准备） | `agent-runtime/tests/integration/adapters/transaction/egress_candidate_v2.py`、candidate-02 harness/history/preparation/live-opt-in、两份strict Schema、versioned launcher及manifest/auth | 复用candidate-01域流程，冻结answer v2/current bootstrap、candidate-01历史和真实授权精度证据；新run/auth且prepared外部调用0 | `DR-TXN-015`；`GATE-055` Closed，live仍受`GATE-026`阻断 |
| `IMPL-TXN-018` | 已完成并冻结（test-only准备） | candidate-03 host/preflight module、versioned launcher、host/lifecycle/result四份strict Schema、manifest/auth及direct/history/live-opt-in测试 | 绑定candidate-02失败证据；在SELECT前验证8项history、33项asset、冻结仓库Python import source和live测试collection并形成耐久有限证据；prepared外部调用0 | `DR-TXN-016`；`GATE-056` Closed |
| `IMPL-TXN-019` | 已完成（test-only准备） | candidate-04 module/live harness/host launcher、strict Schema、manifest/auth及direct/history/preparation测试 | 绑定candidate-03六项历史；允许模型事实值与确定性record_ref不进入forbidden literal，JWT/key/非模型高熵值、`transaction_id_masked` field ID和未知safe-payload key仍在delegate前拒绝；prepared外部调用0 | run=`transaction-egress-v4-20260817-candidate-04`；manifest SHA-256=`ca440b8f3cf664cfe77b803c6a7786816935d391bc56e50a522f6cb76f0535d3`；`GATE-057` Closed |
| `IMPL-TXN-020` | 已完成并冻结（test-only） | `agent-runtime/tests/integration/adapters/transaction/live_bootstrap_v1.py`、`agent-runtime/scripts/run-transaction-egress-live-bootstrap-candidate-01.ps1`、公共strict Schema、manifest/authorization、direct/history tests | 固定Transaction profile启动auth与mq-procedure-service、严格解析四个datasource键、签发内存ADMIN JWT并调用既有candidate-04 launcher；未进入`agent-runtime/src`且未修改Java生产代码 | source commit=`038b6a0f54f5f8ace9a68e49073e5035279473da`；manifest/auth哈希见`VAL-TXN-012`；`GATE-059` Closed |
| `IMPL-TXN-021` | 已实现（test-only） | `agent-runtime/tests/integration/adapters/transaction/live_bootstrap_v2.py`、v2 launcher、strict diagnostic Schema、direct/history/preparation tests、manifest/auth；两个本地JAR作为manifest执行资产 | 复用v1生命周期而不修改v1文件；启动前校验JAR SHA，cleanup前有限分类，随后沿用秘密扫描/原日志删除；outer authorization=`P3_00:GATE-061`，inner candidate继续使用冻结的`P3_00:GATE-026`；绑定wrapper-v1四项历史与candidate-04 | `DR-TXN-019`；`GATE-060` Closed |
| `IMPL-TXN-022` | 已完成（仅文档与计划治理） | L0/L1/L2 与 `P3_00` 的 Transaction 当前交付边界同步；无生产代码、配置或测试资产修改 | 真实 `transaction.search` Provider、业务最终授权、精确 Decimal 与默认 stub 模型用于系统 E2E；真实结果外发实验转 Deferred | `SA-GATE-006.TRANSACTION`继续Open并禁止真实Transaction结果模型出域；历史wrapper/candidate/evidence不可变 |

### 12.2 Python 关键方法

| 符号 | 签名 | 输入/输出 | 副作用 |
|---|---|---|---|
| `TransactionSearchArgumentValidator.validate` | `def validate(self, arguments: JsonObject) -> TransactionSearchInput` | 三类文本条件、三个规范 decimal string、sort、size；金额转 exact Decimal；Date key拒绝 | 纯函数；非法值只抛 `InvalidCapabilityArguments` 且不含原值 |
| `TransactionSearchLocalActionResolver.capability_id` | `@property def capability_id(self) -> str` | 精确返回 `transaction.search`；不可配置 | 纯函数 |
| `TransactionSearchLocalActionResolver.resolve` | `def resolve(self, question: str) -> LocalActionResolution` | question 已经 Runtime 公共上限校验；只按 8.2.1 NFC/token/子句表解析；不得读取 JWT/配置 | 返回 no_match、候选或有限 invalid；无 I/O/日志/共享状态；金额不经 float/Decimal |
| `TransactionSearchRequestMapper.map` | `def map(self, input: TransactionSearchInput, settings: BusinessActionSettings) -> TransactionSearchWireRequest` | filter/sort/settings 交集；金额互斥/范围/scale；page1 | 纯函数 |
| `TransactionSearchWireCodec.encode` | `def encode(self, request: TransactionSearchWireRequest) -> BusinessHttpRequest` | snake→camel；`ExactDecimal.from_decimal`；公共 encoder 产生≤4096 bytes canonical POST body | 纯函数；不得调用 float/quoted coercion/raw 拼接 |
| `TransactionSearchWireCodec.decode_success` | `def decode_success(self, *, request: TransactionSearchWireRequest, response: BoundedBusinessHttpResponse) -> TransactionSearchWireResponse` | request为当前调用栈同一冻结对象；仅2xx application/json；严格UTF-8、BOM/trailing/duplicate/非有限数拒绝；body≤262144；page/size与request精确相等、rows≤request.size；amount直接Decimal；row仅允许已核实宽字段 | 有界内存纯函数；不保存请求期状态/原object |
| `TransactionSearchResponseNormalizer.normalize_success` | `def normalize_success(self, response: TransactionSearchWireResponse) -> BusinessServiceResult[TransactionRecord]` | 8.4 exact/no-result/records | 纯函数 |
| `transaction_search_definition` | `def transaction_search_definition() -> BusinessActionDefinition[TransactionSearchInput,TransactionSearchWireRequest,TransactionSearchWireResponse,TransactionRecord]` | 返回冻结 descriptor/filter/sort/limit/field/status | 纯函数 |
| `TransactionDomainProvider.domain_id` | `def domain_id(self) -> BusinessDomainId` | 精确返回 `transaction` | 纯函数 |
| `TransactionDomainProvider.definitions` | `def definitions(self) -> tuple[BusinessActionDefinition[Any,Any,Any,Any], ...]` | 恰含 `transaction.search` | 纯函数 |
| `TransactionDomainProvider.configuration_fragment` | `def configuration_fragment(self) -> BusinessConfigurationFragment` | 只投影 `AGENT_TRANSACTION_SEARCH_*` 与 `mq-procedure-service` binding，不读 `os.environ`/其他域 | 纯函数 |

### 12.3 Java 关键方法

| 类/方法 | 建议签名 | 前置/返回 | 副作用 |
|---|---|---|---|
| `CapabilityAccessGuard.requireTransactionRead` | `void requireTransactionRead(Authentication authentication)` | 先 user JWT；再精确 `ROLE_ADMIN/ROLE_VIEWER` Authority，否则403 | 无 service/mapper 调用 |
| `TransactionController.search` | 已修改内部 guard：`TransactionSearchResponse search(Authentication authentication, @RequestBody TransactionSearchRequest request)` | `requireTransactionRead` allow 后保持现有 wire | 一次 service |
| `TransactionService.search` | 已存在 `TransactionSearchResponse search(TransactionSearchRequest)` | 本文不修改签名/算法 | count≤1/query≤1 |
| `TransactionSearchSecurityConfiguration.transactionSearchSecurityWebFilterChain` | `SecurityWebFilterChain transactionSearchSecurityWebFilterChain(ServerHttpSecurity http, Converter<Jwt,Mono<AbstractAuthenticationToken>> converter)` | 具名注入 `reactiveUserRoleJwtAuthenticationConverter`；仅匹配 `POST /txn/search` | 构造端点专用安全链；不改其他端点角色语义 |
| `TransactionSearchRequestDeserializer.deserialize` | `TransactionSearchRequest deserialize(JsonParser parser, DeserializationContext context) throws IOException` | amount 三字段只接受 numeric token，以 `getDecimalValue()` 直接得到 `BigDecimal` | 构造现有 DTO；不经 `double`/字符串 coercion |
| `TransactionAmountContract.validateSearchCondition` | `static void validateSearchCondition(Transaction condition)` | 检查 amount 三字段的 scale≤2、整数位≤48、precision≤50 | 纯校验；失败抛 `IllegalArgumentException`，不舍入/截断/改写值 |

## 13. 测试与验证设计

### 13.1 测试矩阵

| 测试编号 | 规则 | 层级 | 建议路径/场景 | 关键断言 |
|---|---|---|---|---|
| `TEST-TXN-001` | `DR-TXN-001/002/012` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_definition.py` | descriptor/argument schema 全字段；唯一 action；三个金额参数为 string 且六个 filter 有限；Date/aggregate 不在定义/配置 |
| `TEST-TXN-002` | `DR-TXN-001/010` | Architecture | 建议新增：`agent-runtime/tests/architecture/test_transaction_adapter_boundaries.py` | 无 Employee/Java/DB/MQ/ES/retry；禁止 path 字面量零 |
| `TEST-TXN-003` | `DR-TXN-002/005/012` | Unit | `agent-runtime/tests/unit/adapters/transaction/test_arguments_definition.py` | 至少一项、类型互斥、LIKE wildcard；金额 exact/range 互斥、上下界、正负零、两位尾零、`9999999999999999.99` 通过且 scale=3/第17位整数拒绝；拒绝 JSON number/int/bool/null、指数及不符合 grammar 的字符串；Date拒绝；page1/size边界 |
| `TEST-TXN-004` | `DR-TXN-002/005/012` | Contract | 建议新增：`agent-runtime/tests/contract/adapters/transaction/test_search_request.py` | snake→camel、null省略、filter/sort子集；金额未加引号、plain、canonical key/Unicode顺序和精确 POST body；枚举互斥约束下逐组构造各文本字段最大 UTF-8 值、金额边界和两项排序，取 canonical bytes 最大合法请求并断言 `<4096`；不得绕过 typed request 构造超长 body；共享 4096/4097 边界由 `TEST-BQCOM-003/014` 证明；全路径无float |
| `TEST-TXN-005` | `DR-TXN-005/011` | Contract | 建议新增：`agent-runtime/tests/contract/adapters/transaction/test_date_exclusion.py` | Date args/config/request 拒绝；raw row Date只临时解析且 typed/user/model/log 零投影 |
| `TEST-TXN-006` | `DR-TXN-003/004` | Java Unit | 建议修改现有：`mq-procedure-service/src/test/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuardTest.java` | ADMIN/VIEWER allow；缺失角色/service token deny；aggregate 的 `requireUser` 语义不被本切片改变 |
| `TEST-TXN-007` | `DR-TXN-004/006/011` | Java MVC/Contract | 建议修改现有 `TransactionControllerTest.java` 并新增 `TransactionControllerAuthorizationTest.java`、`TransactionControllerResponseVisibilityContractTest.java` 与 12.1 visibility fixture | search 改调动作 guard；invalid/mixed role 在 reactive 安全边界403；deny service/mapper0；allow一次；实际顶层/row字段与维护者确认 fixture 精确一致 |
| `TEST-TXN-008` | `DR-TXN-006` | Parameterized | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_coverage.py` | rows/total/exact/page/size笛卡尔边界；exact矛盾失败；non-exact不产生total_count |
| `TEST-TXN-009` | `DR-TXN-007` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_fields.py` | 1～4位ID省略、5位ID掩码；Decimal2；type/amount必需；无Date |
| `TEST-TXN-010` | `DR-TXN-007` | Model spy | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_egress.py` | 默认0；仅type/amount；coverage不进facts；禁止聚合/越界事实 |
| `TEST-TXN-011` | `DR-TXN-008` | Parameterized | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_status.py` | 400→invalid_argument、204→invalid_response、未声明404→downstream_failure；401/403/429/5xx且错误body读取0 |
| `TEST-TXN-012` | `DR-TXN-009` | Async HTTP | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_deadline_single_call.py` | HTTP≤1、无retry/自动翻页、取消/迟到丢弃 |
| `TEST-TXN-013` | `DR-TXN-010` | Security spies | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_forbidden_endpoints.py` | detail/query/condition/aggregate/write/MQ/Kafka调用全0 |
| `TEST-TXN-014` | `DR-TXN-003/007/009` | Log/security | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_sensitive_logging.py` | JWT、条件值、原始/掩码ID、类型、金额、请求/响应和异常sentinel零出现 |
| `TEST-TXN-015` | `DR-TXN-005/006/008/012` | Response contract/concurrency | `agent-runtime/tests/contract/adapters/transaction/test_search_request_response.py` 及相关响应测试 | 顶层/row exact类型、已核实宽字段、未知字段、Decimal int/两位小数/界限；scale=3 响应拒绝；262144/262145 bytes；page/size错配；两个不同size并发交错响应 |
| `TEST-TXN-016` | `DR-TXN-004/005/012` | Java MVC/DB contract | `mq-procedure-service` `TransactionSearchRequestDeserializerTest`、`TransactionAmountContractTest`、`TransactionServiceSearchTest`、`TransactionMapperIntegrationTest`；覆盖 POST 数值 token `0/0.1/100.00/负值/边界`、scale=2/3、service/mapper 参数、MySQL `DECIMAL(50,2)` 的 `=/>/<` 与 quoted string 拒绝 | Jackson 不经 double 精确构造 `BigDecimal`；scale=3 在 mapper 前拒绝；校验不改写原值；数据库比较无截断/舍入；不依赖 string coercion；不修改 DTO/endpoint/schema |
| `TEST-TXN-017` | `DR-TXN-013` | Unit/Runtime contract | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_action_resolver.py` 及混合节点集成用例；覆盖四个 intent 及前缀最长匹配、空格 0/4/5 边界、HEADSEP 空格/单标点、全部 clause/operator/field/direction、1/8/9 子句、连续/尾随分隔符、单一/重复终止标点、文本值含分隔符、合法组合、重复/互斥/范围逆序/仅 size-sort/禁项/控制字符/超长/no_match，并让候选经真实 Schema/validator | 合法问题产生唯一 `transaction.search` 参数且 selector/model/HTTP 为 0；同一文本切分稳定，金额字符串逐字符保持且无 float；识别后非法只返回有限 code；配置更严边界由最终 validator/mapper 拒绝；日志无问题/条件值 |
| `TEST-TXN-018` | `DR-TXN-014` | Contract/fake/live-opt-in/history | Transaction candidate-01 preparation/harness/live/history及model input guard直接测试 | generic exact allow；具体ID/金额/账户/JWT/注入/extra/unknown零调用；synthetic单行经真实codec/normalizer/projector只形成type/amount精确facts并保留公共`coverage.truncated`布尔；search 0/1、answer 0～30、27阈值、三终态、消费顺序、strict evidence、无ID/date/provider coverage计数或总量/聚合/业务值和历史漂移 |
| `TEST-TXN-019` | 已新增并通过；`DR-TXN-015` | History/Contract/Preparation/Fake/Live-opt-in | candidate-01 manifest/auth精确SHA、冻结commit asset及历史v1 harness保持；candidate-02绑定answer v2/current bootstrap、四项history、29项asset、1/30预算、精确Decimal、三终态、消费顺序、strict evidence及敏感问题零调用 | candidate-01不改写且不可live复用；candidate-02 prepared真实search/model=0，live test严格skip |
| `TEST-TXN-020` | 已新增并通过；`DR-TXN-016` | History/Contract/Host preflight/Fake/Live-opt-in | candidate-02四项SHA不可变；candidate-03全资产、import+真实collection成功、missing/wrong-source、asset失败跳过collection、preflight journal fsync、环境隔离、SELECT前失败零调用及既有1/30 fake链 | 定向27 passed/1 live skipped；Transaction/Business 199 passed/4 skipped；prepared不读取类型/JWT/key，不访问数据库/服务/model，正式输出不存在 |
| `TEST-TXN-021` | 已新增并通过；`DR-TXN-017` | History/Contract/Fake/Static/Live-opt-in | candidate-03六项SHA、SELECT1/search1、answer0、failed_unconsumed及不可重跑；candidate-04以live同源domain result验证type/amount与record_ref到达delegate，JWT/key/非模型高熵值、`transaction_id_masked` field ID和未知safe-payload key零delegate；1/30、三终态、consume顺序及preflight不变 | 定向34 passed/1 live skipped；Transaction/Business 230 passed/5 skipped/1历史deselect；全量1130 passed/27 skipped/2历史deselect；strict mypy、compileall、AST、manifest/history hash通过；真实调用0 |
| `TEST-TXN-022` | 已新增并通过；`DR-TXN-018` | Contract/Fake/Static/History/PowerShell AST | datasource固定键解析成功及缺失/重复/非法失败；asset/auth/Transaction/readiness/login/candidate/cleanup逐阶段失败；candidate前inner输出、SELECT/search/model为0；own-PID cleanup、维护者服务不停止、secret/log零落盘、candidate-04/failure/history精确hash | non-live定向、Transaction/Business回归、strict mypy、compileall、AST；真实数据库/服务/JWT/key/outbound均0 |
| `TEST-TXN-023` | 已实现并通过；`DR-TXN-019` | Contract/Fake/Static/History/JAR provenance/PowerShell AST | wrapper-v1 manifest/auth/lifecycle/result/history test SHA不可变且candidate输出不存在；v2双JAR SHA/source/build绑定；JAR漂移启动前拒绝；六分类+unknown、禁止字段、原日志删除、outer语义不变；v2正式输出不存在 | 定向21 passed；Transaction/bootstrap 152 passed、5 live skipped、2个历史prepared-only断言排除；Business/Transaction 127 passed；strict mypy 395 files、compileall、AST、history/JAR hash通过；真实服务/secret/SELECT/search/model=0 |
| `TEST-TXN-024` | 已完成；`DR-TXN-020` | 文档契约/计划 DAG/状态与 scoped 门禁一致性 | 系统 E2E 依赖 `WP-TXN-REAL-01` 而非 Transaction egress 实验；Deferred 包不进入当前关键路径；Not Applicable 不表示通过或授权 | 核对历史30/27阈值、精确 Decimal 约束、失败证据与 `SA-GATE-006.TRANSACTION` 均未改判 |

### 13.2 验证命令

| 编号 | 命令 | 证明范围 | 当前状态 |
|---|---|---|---|
| `VAL-TXN-001` | `python -m pytest agent-runtime/tests/unit/adapters/transaction agent-runtime/tests/contract/adapters/transaction -q` | definition/input/wire/coverage/fields/status | 2026-08-03 已与 `VAL-TXN-002` 联合执行：23 passed；scale=2/绝对值上限通过，scale=3/第17位整数在 HTTP 前拒绝，响应 scale=3/超上限拒绝 |
| `VAL-TXN-002` | `python -m pytest agent-runtime/tests/integration/adapters/transaction agent-runtime/tests/architecture/test_transaction_adapter_boundaries.py -q` | 单调用、禁止接口、模型/日志边界 | 2026-08-03 与 `VAL-TXN-001` 联合执行 23 passed；另从 `agent-runtime` 项目入口执行全量 Runtime 回归 329 passed/2 live PoC skipped，production strict mypy 99 source files 通过 |
| `VAL-TXN-003` | `mvn -f serviceCenter/pom.xml -pl :mq-procedure-service -am test` | provider DTO/search/guard/WebFlux/BigDecimal/MySQL 回归 | 2026-08-03 `BUILD SUCCESS`；`mq-procedure-service` 42 passed，含 Testcontainers MySQL 8.0 的 4 项 Mapper 测试；定向 Provider/Authority 子集另执行 33 passed，数据库契约子集 4 passed |
| `VAL-TXN-004` | opt-in：ADMIN/VIEWER/unknown/missing/malformed/service-token真实JWT矩阵，并以service/mapper spy计数 | reactive Authority/业务最终授权/mapper次数 | 2026-08-06 已通过：evidence 记录 admin 两个主体与 viewer allowed，unknown forbidden，missing/malformed/service-token unauthenticated；Transaction 请求 7、Adapter 6、service search 4、mapper count 4、其他 service/endpoint/model 0。live 响应为空，可见性由版本化 Provider contract 与空响应共同证明 |
| `VAL-TXN-005` | opt-in：以合成 sentinel 条件经实际 Gateway/Netty 发起一次 search，并检索 correlation ID 对应日志 | JWT、请求 body、交易ID/类型/金额和原始异常在 Gateway/Netty/应用日志零出现 | 2026-08-06 已通过：实际 Gateway 正式 MQ 路由 1 次，gatewayAmount 精确；`logLeakCount=0`，JWT/body/principal/交易值均未持久化，原始日志已删除，DeepSeek 调用 0 |
| `VAL-TXN-006` | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md --root D:\codex --strict` | v0.8 文档结构、追踪、引用和质量规则；不替代独立复评或运行契约测试 | 本次修订完成后重新执行 |
| `VAL-TXN-007` | `D:\codex\agent-runtime`：`$env:PYTHONPATH='src;.'; python -m pytest tests/unit/adapters/transaction/test_action_resolver.py tests/integration/graph -q`，再执行 `python -m mypy --strict src tests` | Transaction 有限语法、混合裁决、金额字符串保真、真实 validator/配置复核、模型/HTTP 零调用和类型一致性 | 2026-08-07：62 passed；本工作包直接回归 109 passed；strict mypy 237 source files 无问题 |
| `VAL-TXN-008` | `D:\codex\agent-runtime`；全部live开关为0且不读取密钥 | 执行candidate定向、input guard、Transaction/Business回归、历史manifest重建、strict mypy、compileall、PowerShell AST、L2/P3 strict validator及代码对照设计复核 | 实施后记录synthetic/fake的1/30预算、字段/decimal/facts/grounding、三终态、首outbound消费和零调用负向；未通过不得申请`GATE-026`，且不关闭`SA-GATE-006/GATE-034` |
| `VAL-TXN-009` | `D:\codex\agent-runtime`；全部live开关为0且子进程移除`LLM_API_KEY` | candidate-02定向、Transaction/Business non-live、strict mypy、compileall、PowerShell AST、candidate-01历史SHA、candidate-02 manifest/auth及代码对照设计复核 | 22 passed/1 live skipped；169 passed/3 live skipped；strict mypy110 files、compileall/AST通过；candidate-01不可变，candidate-02 manifest/auth SHA-256=`527845915ad15aa6f24fe59ed31885dcd3fef245109e7cee820217a86cbafa9c`/`79733dd70d86c0acec44341d024c38849d45d58bb23dbf9ea9b98d9852c9cd38`，真实调用0 | 通过并关闭`GATE-055`；`GATE-026/SA-GATE-006/GATE-034`保持Open |
| `VAL-TXN-010` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且移除JWT/`LLM_API_KEY` | candidate-03 direct/history/preflight/fake/live-opt-in skip、Transaction/Business non-live、strict mypy、compileall、PowerShell AST、candidate-01/02历史hash、manifest/auth重建及代码对照设计复核 | import与live测试collection均来自冻结`src`且位于SELECT前；asset/import/collection失败有限可重放，子进程不继承JWT/key/PYTHONPATH，database/search/model=0；candidate-02四项SHA保持 | frozen HEAD=`0e6b748b8263fc5f0c35729099e41313bdddc247`；run=`transaction-egress-v3-20260817-candidate-03`；manifest/authorization SHA-256=`9c1fb119f98fa9f1dc9bbd6904955d222c26fb39c837c179d3a85c1d883e6460`/`ca8983463fc051cf87bc563658bbe80cd583453de4547cd4c81df6524522970c`；8 history/33 assets | 通过并关闭`GATE-056`；`GATE-026/SA-GATE-006/GATE-034`保持Open |
| `VAL-TXN-011` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且移除JWT/`LLM_API_KEY` | candidate-04 direct/history/preparation/live-opt-in skip、Transaction/Business non-live、strict mypy、compileall、PowerShell AST、candidate-03六项历史hash、manifest/auth重建及代码对照设计复核 | exact模型字段与forbidden literal分类互斥；允许type/amount与record_ref到fake delegate，秘密/非模型字段及未知key均零delegate；prepared database/search/model/outbound=0 | frozen HEAD=`680cd25ac0475f301260123c8ce6229ed05dc8c9`；run=`transaction-egress-v4-20260817-candidate-04`；manifest/authorization SHA-256=`ca440b8f3cf664cfe77b803c6a7786816935d391bc56e50a522f6cb76f0535d3`/`885ddb8854b34ccebf29d481e78fb84b1b6a550adf5330bf321eea5085690359`；15 history/33 assets | 通过并关闭`GATE-057`；`GATE-026/SA-GATE-006/GATE-034`保持Open |
| `VAL-TXN-012` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且未提供JWT/数据库凭据/`LLM_API_KEY` | Transaction bootstrap direct/failure/history、公共bootstrap、PowerShell AST、Transaction/Business及全量non-live回归、strict mypy、compileall、candidate-04与failure hash及代码对照设计复核 | 公共/Employee/Transaction冻结后定向29通过；全量1159 passed/27 skipped/2既有历史deselect；strict mypy388、compileall及Transaction launcher AST通过。验证固定四键、pre-side-effect lifecycle、prelaunch零candidate计数、PID/log/secret边界及inner唯一权威；数据库/服务/JWT/SELECT/search/model调用0 | source commit=`038b6a0f54f5f8ace9a68e49073e5035279473da`；run=`transaction-egress-live-bootstrap-v1-20260817-candidate-01`；manifest/auth SHA-256=`c1a90bb90a0cf44b378f9bde1b1701f8de1321e75a9eae0c23d1a15f30d4c0d6`/`b2b8d057afb1651cbb1b3ef098100846b30339da09ebbf2d7bb44ab705ae8308` | 通过；bootstrap包Done，`GATE-026/034/SA-GATE-006[Transaction]`保持Open |
| `VAL-TXN-013` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且移除JWT/数据库凭据/`LLM_API_KEY` | wrapper-v1执行历史、v2 direct/fake/history/preparation、确定性Maven构建与双JAR SHA、PowerShell AST、Transaction/Business回归、strict mypy、compileall及两轮代码对照设计复核 | v1四项SHA和candidate未调用反证不变；v2六分类/unknown、JAR漂移、秘密零落盘、原日志删除、retry/resume=0均通过；正式v2输出不存在 | run=`transaction-egress-live-bootstrap-v2-20260818-candidate-02`；source commit=`779c03c084655b2b2caa535c05911f303194f5e8`；manifest/auth SHA-256=`a244abd6da21ce4bc04c65480208989714380dfbc7a28e61261bb97797fefd0d`/`46f0a6e78b341e6d106d75e4bd72560fd508036844e3fef2085fccdae9d275be`；双JAR SHA-256=`da59695336c6f2fd11581760b41f0958114ac1f9e728ad834ff1a25a7595a96b`/`69cbb7a7a1b3193fb5d06a2c9af474e54917b1ac9c7786dcac1565aa32a8487e` | 已通过并关闭`GATE-060`；只允许申请`GATE-061`，不关闭`GATE-034/SA-GATE-006` |
| `VAL-TXN-014` | `D:\codex`；仅文档修改，不启动服务、数据库或模型调用 | 执行 Transaction L2 strict validator、P3 strict validator、跨层版本/门禁核对与 `git diff --check` | 追踪、DAG、状态、精确 Decimal、历史不可变声明与 scoped 安全边界一致 | 2026-08-20：Transaction L2与P3 strict validator均0错误/0警告，跨层核对及`git diff --check`通过 |

## 14. 风险、门禁与授权

### 14.1 风险

| 编号 | 风险 | 触发 | 影响 | 处置 |
|---|---|---|---|---|
| `RISK-TXN-001` | Date wire 未验证 | 日期查询/结果 | 时区/格式错误 | 首期代码排除，后续独立契约测试 |
| `RISK-TXN-002` | count/query 非同一已证明快照 | 并发写 | total/rows 矛盾 | 严格不变量；不重查；业务侧另行设计 |
| `RISK-TXN-003` | Decimal request/response/scale 漂移 | 后续 provider 接收或返回大值、高 scale、quoted decimal 或非标准数字 | 精度漂移、截断/舍入或查询语义错误 | 当前规范字符串→Decimal→plain JSON number→BigDecimal→MySQL 50/2 已验证；保持跨语言/数据库回归，契约变化重新评审 |
| `RISK-TXN-004` | Authority/装配漂移 | 共享 converter、guard 或有效配置后续变化 | 越权/误拒绝 | 保持真实角色矩阵、guard 与 service/mapper spy 回归；本次 evidence 只覆盖冻结目标配置 |
| `RISK-TXN-005` | 聚合端点相邻且现存 | 动态 path/模型越界 | 超范围统计或大查询 | codec唯一 path、架构和HTTP spy零调用 |
| `RISK-TXN-006` | total 非 exact | 大结果集 | 用户误读总数 | total_count=None、truncated=true、禁止聚合话术 |
| `RISK-TXN-007` | 生产精度快照后续漂移 | 生产 `AMOUNT` 从 `DECIMAL(50,2)` 变更但未同步 fixture/L2/Runtime/Provider 契约 | 新旧边界不一致，可能误拒绝、隐式转换或改变数据库比较 | 以 `transaction-amount-column-v1.json` 和 `TransactionAmountContractTest` 冻结 50/2，Runtime 仅允许更小的 16/2 输入；任何列精度变更必须重回 L2 并生成新版契约 |
| `RISK-TXN-008` | 有限语法覆盖不足或误命中 | 用户使用未列同义词、复杂布尔表达式、多个冲突条件或把交易词句嵌入长文本 | 合法请求被拒绝，或错误动作获得参数 | 只接受 8.2.1 完整语法；识别后歧义失败关闭且不回退模型；扩充 token/运算符必须修订本文与契约测试，不通过配置热扩展 |
| `RISK-TXN-009` | egress候选把通用问题或单条结果扩大为具体查询/聚合 | allow规则接受具体值/额外子句，或candidate外发ID、provider coverage计数/总量或多行结果 | 敏感意图与真实交易值共同出域，或模型生成总量/趋势等无依据结论 | exact `question-egress-v2`、single search/row、type/amount白名单、仅保留`coverage.truncated`安全布尔、strict有限证据、model spy与零调用矩阵；未过`VAL-TXN-008`不得申请live |
| `RISK-TXN-010` | 用answer v2执行candidate-01造成冻结身份漂移 | 当前bootstrap/task变化后仍复用旧manifest/authorization | 审计证据与实际代码不一致，错误消费历史`GATE-026` | candidate-01永久退役；历史从冻结来源校验；candidate-02全新run/manifest/auth已冻结 | `GATE-055` Closed；历史`GATE-026`已消费关闭，后继只受`GATE-061`控制 |
| `RISK-TXN-011` | launcher隐式依赖外部Python导入路径且在SELECT后才暴露 | 干净子进程pytest collection无法导入`agent_runtime` | 一次类型SELECT被消耗、无candidate lifecycle且无法安全重跑 | candidate-02失败证据不可变；candidate-03在SELECT前执行全资产、来源受控import和真实collection preflight并持久化有限失败；子进程环境隔离且launcher finally恢复作用域变量 | `GATE-056` Closed；历史`GATE-026`已消费关闭，后继只受`GATE-061`控制 |
| `RISK-TXN-012` | test-only禁止字面量集合包含获准type/amount值 | safe payload按字段矩阵正确生成，但live harness把同值视为泄漏 | 首次delegate前自拒绝并浪费SELECT/search预算 | candidate-03六项证据不可变；`DR-TXN-017`以exact key约束允许字段，以JWT/key/非模型高熵值约束literal扫描，并用live同源fake正反例冻结 | `GATE-057/026` |
| `RISK-TXN-013` | candidate外bootstrap依赖临时正则和未冻结进程编排 | datasource YAML格式微调、Spring参数重复、端口被占或PID归属不明 | candidate前失败且无稳定证据，或误停维护者服务、错误消费一次性run | `DR-TXN-018`以固定键解析、versioned wrapper、首副作用前journal、PID/readiness和有限failure收口；wrapper-v1失败永久只读，wrapper-v2由`DR-TXN-019`补齐JAR与有限诊断 | `GATE-059/060` Closed；新执行仅受`GATE-061`控制 |
| `RISK-TXN-014` | wrapper源码与实际启动JAR身份分离且失败分类过宽 | target目录残留旧JAR，或auth启动立即退出但原日志删除后只剩`process_exited` | 无法证明运行版本和最小修复位置，可能重复浪费新一次性授权 | `DR-TXN-019`冻结两个JAR SHA/源码commit/构建命令并输出有限诊断；旧run不可重试，unknown继续失败关闭 | `GATE-060/061` |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 关闭条件 | 责任方 | 状态 | 未关闭允许/禁止 |
|---|---|---|---|---|---|---|
| `BQ-GATE-002` | slice_implementation | 实施既有 Python Transaction Adapter/配置/测试切片 | 历史独立评审、明确授权、本地/金额精度测试和代码对照设计评审通过 | 维护者 | Closed（Adapter 与 Resolver 均 implementation-verified） | 既有 Adapter 与本地 Resolver 可维护；语法/金额范围扩大、真实调用、默认启用和模型出域仍须另行授权 |
| `BQ-GATE-003` | slice_implementation | 修改 Transaction search guard/公开行为及实施精确金额 Provider 契约 | 维护者确认 search 子集、角色 guard、现有调用方兼容、versioned response visibility fixture、JSON number→BigDecimal→数据库 `=/>/<` 的 precision/scale/无舍入契约、Decimal response/400/coverage 语义及具体代码范围 | 维护者/Transaction 方 | Closed（仅 Provider 实施切片） | 可维护已验证实现；受控真实目标配置已由 `SA-GATE-005`、`P3_00 GATE-018/031` 关闭证据允许，公开契约扩大仍禁止 |
| `CR-GATE-003` | integration | 具体交易问题进入 DeepSeek | 全局问题闸门对交易 ID、金额和敏感文本形成批准路径或零调用 | 维护者/模型方 | Closed（2026-08-12；以具体/unknown 零调用关闭问题输入前置） | 8.2.1 本地 Resolver 命中时继续不进入模型；具体敏感或未分类交易问题仍禁止走模型 fallback/答案模型，真实结果仍受 `SA-GATE-006` |
| `SA-GATE-005` | integration | 启用真实 Transaction | Authority、guard、response visibility、JSON number→BigDecimal→数据库精确比较、Decimal response/coverage、禁止接口、访问日志和角色矩阵通过 | 维护者/安全/Transaction 方 | Closed（2026-08-06） | evidence `wp-txn-real-01-20260806T134518Z.json` 与独立代码对照设计复核通过；允许受控目标配置，默认/生产启用与模型出域仍禁止 |
| `SA-GATE-006.TRANSACTION` | security/integration | 真实Transaction结果进入外部模型 | 未来新实验须重新证明字段/Decimal/facts/grounding/无聚合越界、零调用负向与零泄漏，并取得新鲜精确授权 | 维护者/Transaction/模型方 | Open（当前外发实验Deferred） | 禁止真实Transaction载荷外发；允许真实Provider + stub模型系统E2E；不依赖当前P3中已Not Applicable的执行/完成门禁 |

### 14.3 后续需授权

- 扩大已完成 Python Adapter 动作、字段、金额或 wire 契约范围。
- 继续修改已验证的 Transaction guard/controller/严格 JSON/precision 契约，或改变统一 Authority converter 语义。
- 变更 Date/公开 DTO/数据库一致性；超出 `WP-TXN-REAL-01` evidence 范围新增真实调用；默认/生产启用 search 或外发真实结果。
- 修改已验证的 `IMPL-TXN-015` Resolver、扩大 8.2.1 有限语法或改变金额保真、最终 validator/配置复核与混合裁决契约。
- 重跑candidate-01～04、修改冻结wrapper-v1/v2、manifest/auth/失败证据，或复用历史`GATE-026/061`。`GATE-061/034`在当前周期为Not Applicable且不能授予执行权；未来恢复实验须先诊断并使用全新工作包、按需要建立的新有界门禁、run/authorization和预算，优先复用通用受控harness，完成状态仍由`SA-GATE-006.TRANSACTION`判定。

## 15. 内部自检记录（作者内审）

| 日期 | 检查范围 | 结论 |
|---|---|---|
| 2026-08-20 | 现行权威、稳定标识、追踪矩阵、门禁与历史迁移完整性 | 物理瘦身不改变设计语义、Approved 状态、实施边界或门禁结论；完整逐轮记录见历史审计文档 |

## 16. 独立正式评审记录

- 本文既有独立正式评审通过结论保持不变；本次仅进行非语义的文档分层与物理瘦身，不据此重新授予批准状态。
- 完整逐轮发现、修复和代码对照设计复核记录见 [`L2_02_02` 历史审计记录](history/L2_02_02_TRANSACTION_ADAPTER_AUDIT_HISTORY.md)。
## 17. 实施前检查

- [x] 单 search 动作、现有接口、文本/金额条件、排序、字段和授权边界已定义。
- [x] Date、聚合、自动翻页和写入口均明确不可达。
- [x] 公开接口/安全不足保持开放门禁。
- [x] 三轮内部自检完成且无遗留 Blocker/Major。
- [x] 严格详细设计校验通过。
- [x] v0.2 五轮独立评审—修复—复核完成，全部历史 S0/S1/S2 已关闭。
- [x] v0.3 精确金额条件与 `L2_02_00` v0.4 已完成两轮独立复评—修复—复核，`REV-TXN-021` 已关闭。
- [x] 用户已授权 Python Adapter 切片并在测试、金额精度验证和代码对照设计评审后关闭 `BQ-GATE-002`；Provider 变化现已完成并仅按实施切片关闭 `BQ-GATE-003`。
- [x] 用户已确认生产 `DECIMAL(50,2)` 并授权金额契约收紧；Provider 实现、Python/Java/MySQL 测试和代码对照设计评审已完成。
- [x] `VAL-TXN-004/005` 与 evidence 严格校验通过，独立代码对照设计复核无 S0/S1/S2，`SA-GATE-005` 已关闭；问题输入 `CR-GATE-003/GATE-025` 已以非 live 零调用证据关闭，`SA-GATE-006/GATE-026` 保持 Open。
- [x] v0.8 已固定 Transaction Resolver 的有限多子句语法、金额字符串保真、模型零调用、最终 validator/配置复核与实现/测试落点；未把设计完成误记为代码已实施。
- [x] v0.8 完成 `AR-HYBRID-01～03` 与 `FR-HYBRID-01～05`，新增发现全部关闭。
- [x] `IMPL-TXN-015/TEST-TXN-017/VAL-TXN-007` 已完成；Transaction 定向与 graph 62 passed，工作包直接回归 109 passed，strict mypy 237 files 无问题，金额未经过 float、舍入或字符串 wire 改写。
- [x] `DR-TXN-014/IMPL-TXN-016/TEST-TXN-018/VAL-TXN-008` 已完成non-live实施、冻结和代码对照设计复核；仅允许申请`GATE-026`，不得直接执行。
- [x] `DR-TXN-015/IMPL-TXN-017/TEST-TXN-019/VAL-TXN-009`已完成answer v2、candidate-01历史兼容及candidate-02 non-live冻结，`GATE-053/055`关闭；正式live仍须另行精确授权`GATE-026`。
- [x] candidate-02初始化失败已以SHA-256=`37c4cf079cf1bb28e17c9b087df5707bf19c5bbfd8318d6c3f5f611f08fd72d9`归档；一次类型SELECT已使用，lifecycle/search/model均0且run不得重跑。
- [x] `DR-TXN-016/IMPL-TXN-018/TEST-TXN-020/VAL-TXN-010`已完成candidate-03 non-live实现、8项history/33项asset冻结、回归和代码对照设计复核；`GATE-056`关闭。
- [x] candidate-03唯一执行已按六项文件与哈希归档为`failed_unconsumed/model_call_failed`；SELECT1/search1、answer0、retry/resume0且不得重跑。
- [x] `REQ/CON/DR-TXN-014/012/017`聚焦评审通过；candidate-04只允许test-only non-live修复允许事实值与禁止字面量分类，生产契约不变。
- [x] `DR-TXN-017/IMPL-TXN-019/TEST-TXN-021/VAL-TXN-011`已完成candidate-04 test-only non-live实现、15项history/33项asset冻结、回归与代码对照设计复核；`GATE-057`关闭，live仍受`GATE-026`阻断。
- [x] `REQ-TXN-015/CON-TXN-013/DR-TXN-018`已定义Transaction外层bootstrap、固定配置键、pre-candidate失败、PID/secret/log及inner唯一权威边界。
- [x] `IMPL-TXN-020/TEST-TXN-022/VAL-TXN-012`已完成non-live实现、两步冻结、全量回归和代码对照设计复核。
- [x] wrapper-v1唯一执行已归档为`failed_pre_candidate_unconsumed/process_exited`；manifest/auth/lifecycle/result及独立history test不可变，candidate-04未调用且inner输出不存在。
- [x] `REQ-TXN-016/CON-TXN-014/DR-TXN-019`已明确wrapper-v2的JAR SHA、源码/build provenance、有限诊断、旧run不可复用与新门禁边界；聚焦评审无未关闭S0/S1/S2。
- [x] `IMPL-TXN-021/TEST-TXN-023/VAL-TXN-013`已完成wrapper-v2 non-live实现、确定性构建、双JAR/源码/历史冻结、回归和代码对照设计复核；`GATE-060`关闭且正式输出不存在。
- [x] `DR-TXN-020`已完成当前交付周期治理收敛；P3 `GATE-061/034`为Not Applicable，`WP-TXN-EGRESS-01`转Deferred，`SA-GATE-006.TRANSACTION`继续Open并只约束真实Transaction结果外发。

## 18. 当前结论

本文v0.24为Approved；当前规范权威为需求/约束/决策、当前门禁表和本节结论，历史评审与运行章节只作不可变审计轨迹。历史Adapter、Provider、16/2→50/2金额、角色/Gateway、candidate-01～04、wrapper-v1/v2及全部证据继续有效且不可变。wrapper-v1失败和wrapper-v2冻结事实不变；真实Transaction结果模型实验转Deferred，P3 `GATE-061/034`在当前周期为Not Applicable。当前系统E2E可使用已验证Transaction Provider、精确Decimal链与默认stub模型，模型outbound=0。`SA-GATE-006.TRANSACTION`保持Open，继续禁止真实Transaction结果外发；未来恢复实验必须使用全新工作包、按需要建立的新有界门禁与精确授权并优先复用通用harness，不能复用历史run或授权。
