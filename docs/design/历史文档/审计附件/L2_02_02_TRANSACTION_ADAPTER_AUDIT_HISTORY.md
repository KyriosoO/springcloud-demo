# [L2_02_02-HISTORY] 单体 Agent Transaction Adapter 与业务授权联调历史审计记录

## 1. 归档说明

| 项目 | 内容 |
|---|---|
| 文档角色 | 只读历史审计附件；不构成现行设计、计划、门禁或执行授权 |
| 来源文档 | [L2_02_02](../L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) |
| 迁移基线 | v0.24 |
| 迁移日期 | 2026-08-20 |
| 归档范围 | 来源文档的完整修改历史，以及逐轮内审/正式评审/实施复核流水 |
| 原文完整性 | 修改历史段 SHA-256 `cd20df58e612e9657c757791064477e3a151d31198c682165779eee5163cc264`；评审流水段 SHA-256 `26deeafa9d13f4111ec388697f0f52df3bc257e782f18c7833973a7c146afa38` |
| 权威边界 | 稳定规则、当前门禁、当前状态和当前结论以来源文档为准；本文件中的 run、manifest、hash、candidate、wrapper、JAR、HEAD 和历史状态不得作为可复用授权或当前执行入口 |

> 以下两个段落从迁移基线原文完整复制，正文和表格未改写。迁移只改变存放位置。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-31 | 全文 | 第三批 L2 依序编写 | 新建 Transaction 单搜索动作、受控条件/排序、响应覆盖、字段分类、授权入口、失败、测试和门禁设计 |
| 2 | 2026-07-31 | 全文 | 第 1 轮内部自检 | 完成结构、追踪、责任、签名、失败、安全、事务、生命周期和门禁检查；严格校验无结构缺口 |
| 3 | 2026-07-31 | 8/9/13/15 章 | 第 2 轮内部自检 | 禁止 LIKE wildcard 扩大、修正 Decimal wire 示例、收紧 exact coverage 和固定 ROUND_HALF_UP |
| 4 | 2026-07-31 | 8/9/12～16 章 | 第 3 轮内部自检 | 补齐内部 wire/record 类型字段，展开精确配置键和 Java 测试路径，完成实施可验证性收口 |
| 5 | 2026-07-31 | 6 章 | 第三批原子一致性同步 | 展开已存在 Transaction Java 类完整路径；不改变三轮内审结论或动作边界 |
| 6 | 2026-07-31 | 全文 | 五轮独立评审—修复—复核 | 关闭切片门禁、金额请求契约、短ID脱敏、完整descriptor、snake/camel、严格响应、业务可见性、Java触点、请求—响应关联、发布回滚和验证等`REV-TXN-001`～`020`，定版v0.2 Approved；所有实施/集成门禁保持Open |
| 7 | 2026-07-31 | 13 章 | 终态验证证据同步 | 执行含 Transaction API、服务及直接依赖的 Maven 现有基线回归并通过；建议修改/新增的角色守卫、WebFlux 与响应可见性测试尚未实施，所有实施/集成门禁保持 Open |
| 8 | 2026-08-01 | 1～15、17～18章 | 用户确认补齐 BigDecimal/Decimal 查询链路 | 对齐 `L2_02_00` v0.4，新增 amount/amount_gt/amount_lt 规范字符串参数、强类型 Decimal 条件、精确 JSON number wire、边界/互斥/配置/测试和 provider 门禁；更新为 v0.3 In Review |
| 9 | 2026-08-01 | 8.1、8.3、13、16～18章 | v0.3 第 1 轮独立复评修复 | 将不可由合法 Transaction DTO 构造的 4096/4097-byte 域测试改为“最大合法请求小于动作上限”，并由公共 encoder 测试独占总字节边界；同步公共 v0.4 Approved 依赖，等待重新复评 |
| 10 | 2026-08-01 | 1、16～18章 | v0.3 第 2 轮独立复评收口 | 从当前全文和直接依赖重新复核，确认公共字节边界仍由共享 encoder 验证、域测试只验证合法 Transaction 请求；关闭 `REV-TXN-021`，未发现新的 S0/S1/S2，恢复为 Approved；实施及集成门禁保持 Open |
| 11 | 2026-08-01 | 1～2、12～14、17～18 章 | `WP-TXN-ADAPTER-01` 实施状态原子同步 | 记录 Transaction Python Adapter、ExactDecimal 条件、canonical JSON number、codec/normalizer、字段投影、settings/provider 和 fake server 测试已实现并完成代码对照设计评审；关闭本切片 `BQ-GATE-002`，Java Provider、真实金额/JWT 与模型出域门禁保持 Open |
| 12 | 2026-08-03 | 1～2、11～14、17～18 章及 P3_00 | `WP-TXN-PROVIDER-01` 实施前置核实与停止证据同步 | 确认具名统一 Authority converter、现有调用方角色兼容及生产金额列 precision/scale 均无充分证据；唯一测试表为 `decimal(50,2)`，不足以证明 scale≤4 无舍入链路。在修改 guard/controller/service/tests 前停止，无 Java/API 代码变更，`BQ-GATE-003/SA-GATE-005/006` 保持 Open |
| 13 | 2026-08-03 | 1～2、6、8、10～15、17～18 章及 P3_00 | 生产 `DECIMAL(50,2)` 契约对齐与 Provider 候选复核 | 按用户明确授权将 Runtime 请求/响应金额从 scale≤4 收紧为 scale≤2，保持 16 位整数上限、`transaction.search` 动作和数据库结构不扩大；核对共享 converter、调用方/可见性/生产字段快照、Provider 校验与 Python/Java/MySQL 契约测试，仅关闭 Provider 实施切片，`SA-GATE-005/006` 保持 Open |
| 14 | 2026-08-06 | 1～2、6、11、13～14、16～18 章及 P3_00 | `WP-TXN-REAL-01` 受控真实联调与门禁关闭同步 | 基于 evidence `wp-txn-real-01-20260806T134518Z.json`、既有 Python/Java/MySQL 验证及独立代码对照设计复核，确认真实角色矩阵、精确金额、可见性、禁止接口、正式 Gateway 路由、调用计数与日志零泄漏；关闭 `SA-GATE-005`，不改变设计契约，`CR-GATE-003/SA-GATE-006` 保持 Open |
| 15 | 2026-08-07 | 1～4、7～18 章 | 新增 Transaction 本地确定性参数 Resolver | 固定有限中文多子句语法、金额原样 canonical string、冲突/重复/禁止子句失败关闭、最终 validator 复核、组合根绑定和测试追踪；模型不再生成 Transaction 参数，既有 Provider/精度/真实联调证据不变 |
| 16 | 2026-08-07 | 1～2、13～14、17～18 章及 `P3_00` | `IMPL-TXN-015/TEST-TXN-017/VAL-TXN-007` 实施验证状态同步 | 记录 `TransactionSearchLocalActionResolver`、definition 同 ID 绑定、有限多子句语法、金额字符串逐字符保真、重复/互斥/范围/禁项失败关闭、最终 validator/配置复核和混合节点零 selector/model/HTTP 已通过；Transaction 定向与 graph 62 passed，本工作包直接回归 109 passed，strict mypy 237 files 无问题；不改变 Date/聚合/写禁项、16/2→50/2 精度链或真实联调边界 |
| 17 | 2026-08-12 | 1～2、14、17～18 章及公共/模型 L2、P3_00 | Transaction 问题出域非 live 安全证据同步 | 业务 fixture 中交易号精确命中敏感类别，Transaction 金额未分类场景失败关闭；selector/answer fake transport 与 grounding 均为0。关闭 `CR-GATE-003/GATE-025` 问题输入前置，真实 Transaction 结果出域仍受 `GATE-026/SA-GATE-006` |
| 18 | 2026-08-14 | 1～4、8～14、17～18章及公共/模型L2、P3_00 | `WP-TXN-EGRESS-CANDIDATE-01-PREP`聚焦设计 | 增加`REQ-TXN-011/CON-TXN-009/DR-TXN-014`与实现/测试/验证追踪；固定无具体值通用问题、1次search/30次answer、type/amount唯一模型字段、精确Decimal事实、首outbound消费、三终态、有限证据和历史不可变；prepared只允许fake，`GATE-026/SA-GATE-006/GATE-034`保持Open |
| 19 | 2026-08-14 | v0.11增量及公共/模型/P3追踪 | 三轮聚焦独立评审—修复 | 收紧live query为进程级类型等值条件且值/哈希不落盘；核对single-row、type/amount、Decimal、facts/有限证据无provider coverage值或聚合、三终态、历史哈希和prep→live单向依赖；无未关闭S0/S1/S2 |
| 20 | 2026-08-14 | 1～4、8～14、16～18章及公共/模型L2、P3_00 | `WP-TXN-EGRESS-CANDIDATE-01-PREP`实施、冻结与代码复核 | 实现测试范围candidate/strict Schema/launcher/live opt-in/manifest/auth/history；fake复用生产codec/normalizer/projector/grounding验证1次search、30次answer、精确`100.10` fact、三终态和首outbound消费。冻结manifest SHA-256 `dba4610cc0e578e65c45b49b288ce9d4b74b90eea9f9d05609e7935dd2feac44`；真实search/model=0 |
| 21 | 2026-08-17 | 1～4、8～14、16～18章及公共/模型L2、P3_00 | Business Answer v2影响与candidate-02前置设计 | answer v2只强化模型可见行内fact marker，不改变Transaction字段、Decimal/BigDecimal、search或grounding；但生产bootstrap/task源码身份变化使candidate-01 current-source绑定过期。candidate-01 manifest/auth保持未消费历史且永久退役；新增`REQ/CON/DR-TXN-012/010/015`，v2本地通过后以全新candidate-02重新冻结 |
| 22 | 2026-08-17 | 1～4、8～14、16～18章及公共/模型L2、P3_00 | answer v2本地实施与Transaction历史兼容闭环 | 生产组合根已切换独立answer v2；candidate-01 manifest/auth保持未消费历史，20项asset按冻结commit验证，历史v1 fake harness显式使用v1而不冒充当前生产。67项完整相关定向及全量non-live 1024 passed/23 skipped/1既有历史deselect、strict mypy354、compileall和代码复核通过；真实Transaction/模型调用0，关闭`GATE-053`，`GATE-055/026`保持Open |
| 23 | 2026-08-17 | 1～4、8～14、16～18章及公共/模型L2、P3_00 | `WP-TXN-EGRESS-CANDIDATE-02-PREP/GATE-055`实施、冻结与代码复核 | 新增schemaVersion2 candidate、strict lifecycle/result Schema、answer v2 fake/harness/history/preparation/live-opt-in、versioned launcher及manifest/auth。全新run=`transaction-egress-v2-20260817-candidate-02`绑定answer v2/current bootstrap、candidate-01 manifest/auth/冻结commit、真实授权精度证据和29项asset，预算search1+answer30；manifest SHA-256=`527845915ad15aa6f24fe59ed31885dcd3fef245109e7cee820217a86cbafa9c`。定向22/1 skipped、Transaction/Business169/3 skipped、strict mypy110、compileall/AST/hash及代码复核通过；外部调用0，关闭`GATE-055` |
| 24 | 2026-08-17 | 1～4、8～14、16～18章及公共L2、P3_00 | `GATE-026` candidate-02初始化失败归档与candidate-03聚焦设计 | 唯一执行使用一次只读SELECT取得非空类型后，冻结launcher因未向pytest子进程提供当前仓库`agent-runtime/src`导入路径，在collection阶段以`ModuleNotFoundError(agent_runtime)`失败；lifecycle/consumed/result不存在，search/model/retry/resume=0。有限证据SHA-256=`37c4cf079cf1bb28e17c9b087df5707bf19c5bbfd8318d6c3f5f611f08fd72d9`，candidate-02不可重跑。新增`REQ/CON/DR-TXN-013/011/016`，candidate-03须以全新run在任何SELECT前完成受控import preflight及有限失败闭环 |
| 25 | 2026-08-17 | 1～4、8～14、16～18章及公共L2、P3_00 | `GATE-026` candidate-03失败归档与candidate-04聚焦设计 | candidate-03完成SELECT1/search1后在首次model delegate前以`failed_unconsumed/model_call_failed`结束，answer0、retry/resume0且consumed不存在；host-preflight/host-result/lifecycle/result SHA-256分别为`869e441bca5b85dcf71508d5f5a7e94fa8fb7f2a981eb0850f8a082a030eb2f4`/`ca87a7db00f38890d9f1cb17e3acd1dc520ddbd814e1496ca2b9b9b9bf1a6f2c`/`b5bb3e3d9413ad3a98ca9f34b0c76a6fd4b36c7c36d94ddf7aa5902827b7019f`/`eb5003cdc31a25a5aa2c201250fa00e4d7e5291aaf6482ffce63c3b5c8070b7d`。根因为test-only live harness把获准`transaction_type/amount`值并入禁止字面量集合；新增`REQ/CON/DR-TXN-014/012/017`，生产Adapter/字段/Decimal/grounding不变 |
| 26 | 2026-08-17 | 1～4、6～7、9～18章及公共L2/P3_00 | candidate-04外部bootstrap失败归档与versioned设计 | 最新执行在candidate调用前的datasource配置解析阶段失败，有限evidence SHA-256=`b831d2f9d019fcd3347f389cd92fa00b0fc5e6deee3efd2ff0024c17594c7357`，auth/Transaction未启动且SELECT/search/model=0；根因是临时bootstrap正则转义不匹配，不是Adapter、Provider、Decimal或candidate缺陷。新增`REQ-TXN-015/CON-TXN-013/DR-TXN-018`及实现/测试/验证追踪 |
| 27 | 2026-08-17 | 1～2、12～18章及公共L2/P3_00 | Transaction versioned live bootstrap实施、冻结与代码对照设计复核 | 新增公共helper消费的Transaction profile、versioned launcher、strict Schema、manifest/auth及direct/history测试；固定解析datasource四键并把auth/Transaction进程、ADMIN JWT、PID/readiness和日志清理纳入outer，SELECT/search/model仍由candidate-04唯一拥有。源码提交=`038b6a0f54f5f8ace9a68e49073e5035279473da`，wrapper manifest/auth SHA-256=`c1a90bb90a0cf44b378f9bde1b1701f8de1321e75a9eae0c23d1a15f30d4c0d6`/`b2b8d057afb1651cbb1b3ef098100846b30339da09ebbf2d7bb44ab705ae8308`；定向29、全量non-live1159/27 skipped/2既有历史deselect、strict mypy388、compileall/AST与代码复核通过，真实调用0 |
| 28 | 2026-08-18 | 1～4、12～18章及公共L2/P3_00 | `GATE-026` wrapper-v1失败归档与wrapper-v2聚焦设计 | 唯一执行在auth启动后、`auth_readiness`前以`failed_pre_candidate_unconsumed/process_exited`终止；candidate-04未调用，SELECT/search/model=0。outer lifecycle/result SHA-256=`a69fa805b9aa9b77035aa1f3c509195dd8a4e6ae0ed194ad2a58a8aa48f74891`/`626ac18f8738cfe73dbeed9461e7cd21fa07edd9ec6911263a9177d64fc0a60a`，独立历史测试随commit `7665022`冻结。wrapper-v1未绑定实际JAR哈希且有限结果不足以定位进程退出类别；新增`REQ/CON/DR-TXN-016/014/019`，`GATE-026`作为已消费入口关闭，完成门禁保持Open |
| 29 | 2026-08-18 | 1～2、6、9、12～18章及公共L2/P3_00 | `WP-TXN-EGRESS-LIVE-BOOTSTRAP-02-PREP/GATE-060` non-live实施、冻结与复核 | 独立Transaction wrapper-v2、strict diagnostic Schema、版本化launcher和direct/preparation/history测试已实现；source commit=`779c03c084655b2b2caa535c05911f303194f5e8`，prepared HEAD=`196845090124344deda901132ccd4cdc6c2149eb`，run=`transaction-egress-live-bootstrap-v2-20260818-candidate-02`，manifest/auth SHA-256=`a244abd6da21ce4bc04c65480208989714380dfbc7a28e61261bb97797fefd0d`/`46f0a6e78b341e6d106d75e4bd72560fd508036844e3fef2085fccdae9d275be`；确定性构建、non-live回归、strict mypy、compileall、AST及两轮代码复核通过，外部调用0。`GATE-060`关闭，`GATE-061/GATE-034/SA-GATE-006[Transaction]`保持Open |
| 30 | 2026-08-20 | 1～4、12～18章及公共L2/P3_00 | 当前交付周期Transaction门禁治理收敛 | 保留wrapper-v1失败、wrapper-v2冻结、candidate-01～04及全部历史证据；真实Transaction结果模型实验转Deferred，P3 `GATE-061/034`记为Not Applicable。`SA-GATE-006.TRANSACTION`继续Open并禁止真实结果外发，但不阻塞已验证Provider + stub模型系统E2E |
| 31 | 2026-08-20 | 2、4、14、17～18章及公共L2/P3 | 当前设计权威与历史证据边界聚焦修复 | 移除把`GATE-061`写成当前下一动作的残留表述；历史运行资产仅作审计，未来恢复实验须新立项且优先复用通用harness |

## 15. 内部自检记录（作者内审）

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-31 | 0 | 0 | 0 | 0 | 0 | 结构与追踪完整，首次严格校验 0 error/0 warning |
| 2 | 2026-07-31 | 0 | 2 | 2 | 4 | 0 | wildcard、Decimal、exact coverage 和 rounding 语义已收紧 |
| 3 | 2026-07-31 | 0 | 1 | 2 | 3 | 0 | wire/record 类型、精确配置键和 Java 路径已补齐 |
| 4 | 2026-08-01 | 0 | 2 | 1 | 3 | 0 | 将金额输入固定为规范字符串→Decimal→JSON number→BigDecimal，补齐互斥/边界/配置/跨语言测试与真实启用门禁；等待独立复评 |
| 5 | 2026-08-03 | 0 | 1 | 1 | 2 | 0 | 按已确认生产 `DECIMAL(50,2)` 将 Runtime 请求/响应 scale≤4 收紧为 scale≤2，同步补齐 Provider 真实实现落点和门禁/验证证据；未改 schema、金额整数位上限或动作 |

## 16. 独立正式评审记录

每轮均先以只读方式冻结发现，再进入目标/已授权直接相关文档修复；修复后重新从当前全文开始下一轮。作者内审和确定性validator只作辅助证据，不替代独立评审判断。

### 16.1 第1轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-001` | S1 | 本文未承接上位按每份L2切片判断的`BQ-GATE-002`，可能把设计通过误当代码授权 | 增加Transaction Python切片门禁，并与provider变化、真实启用/出域门禁作交集 | Closed |
| `REV-TXN-002` | S1 | 金额条件要求Decimal精确JSON number，但approved common request body只允许JsonObject且禁止Decimal；经float会破坏精度 | 首期移除金额条件，保留金额结果/排序；避免扩大公共HTTP body契约 | Closed |
| `REV-TXN-003` | S1 | 公共`mask_keep_last4`要求至少5位，但现有provider测试使用合法形态`T001`；把ID列为required会使现有结果稳定失败 | ID改为可选字段，1～4位安全省略，5～128位复用公共掩码；type/amount作为最小有效结果 | Closed |
| `REV-TXN-004` | S1 | 未声明no-result的404被合并为invalid_response，与公共`unavailable`映射冲突 | 分离204与404，404固定downstream_failure(`unavailable`) | Closed |
| `REV-TXN-005` | S1 | 文档把raw body上限写成256KiB且声称直接跳过Date，但common先按全局上限聚合且无流式JSON依赖 | 区分transport/codec上限，承认宽row临时object生命周期并固定typed/log/error零投影 | Closed |
| `REV-TXN-006` | S1 | “收紧/替换requireUser”可能顺带改变相邻aggregate权限，超出search切片 | 新增动作专用guard，只替换search调用；aggregate继续现有requireUser并做回归断言 | Closed |
| `REV-TXN-007` | S1 | Adapter字段投影无法证明ADMIN/VIEWER有权接收含Date的现有宽row | 增加维护者确认的versioned response visibility fixture及实际序列化字段契约；不能确认则转窄DTO设计 | Closed |

### 16.2 第2轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-008` | S1 | 动作缺display/description/aliases/argument_schema，不能形成L2_00_01要求的完整descriptor | 固定完整descriptor和受控Schema，并明确跨字段规则由同一validator执行 | Closed |
| `REV-TXN-009` | S1 | snake_case输入未固定到Java camelCase filter/sort名，`trans_id/trans_type`可能直接形成provider 400 | 固定全部condition/sort映射、null省略和canonical key顺序 | Closed |
| `REV-TXN-010` | S1 | 响应未固定bool-as-int、非有限数字、Decimal直读、顶层/row unknown策略和Java long上限 | 固定strict parser、exact类型、Decimal无float、顶层严格/已核实宽row例外及数值边界 | Closed |
| `REV-TXN-011` | S2 | definition/provider方法不完整，现有guard/controller测试被误写为全部新增 | 补齐definition与provider三方法签名；把现有测试标为建议修改并分离新增权限/visibility测试 | Closed |

### 16.3 第3轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-012` | S1 | 请求示例仍发送应省略的null条件，且测试/风险仍要求已删除的金额请求编码 | 改为唯一规范请求示例，并重写参数、request、Date/金额排除、字段与风险测试 | Closed |
| `REV-TXN-013` | S1 | Maven命令在缺少聚合入口的仓库根目录不可执行，Python测试路径也不完整 | 以`serviceCenter/pom.xml`作为Maven聚合POM并使用artifact selector，同时统一`agent-runtime/tests`路径 | Closed |
| `REV-TXN-014` | S1 | search guard会改变现有公开行为，但没有旧调用方盘点或安全回滚流程 | 调用方角色兼容纳入provider gate；增加Agent先停用、provider显式决策的分层回滚 | Closed |

### 16.4 第4轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-015` | S1 | 省略size固定为20时，配置若收紧到10会使所有省略size的合法调用在运行期失败 | input保留`size=None`，mapper使用`min(20,effective_max)`；显式size仍严格受配置约束 | Closed |
| `REV-TXN-016` | S1 | 公共`decode_success(response)`拿不到同一次request，无法校验page/size/rows且用实例字段会在并发时串响应 | 原子聚焦修订`L2_02_00`为v0.3，显式传入同一冻结request；本文同步签名及交错并发测试 | Closed |
| `REV-TXN-017` | S2 | visibility测试若用默认null row，可能受Jackson null inclusion影响而漏检可序列化敏感字段 | fixture按属性全集冻结，provider测试使用所有属性均为合成非空值的Transaction | Closed |
| `REV-TXN-018` | S2 | 日志要求没有实际Gateway/Netty/body sentinel验证，无法证明请求条件未被日志设施采集 | 增加Agent日志测试与真实入口`VAL-TXN-005` | Closed |

### 16.5 第5轮冻结发现、修复与终审

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-019` | S2 | 响应page/size只写“与请求一致”，但实现签名/测试未明确禁止codec保存可变上次请求 | 签名显式接收request并声明纯函数；两个不同size交错响应必须各自绑定 | Closed |
| `REV-TXN-020` | S2 | 测试矩阵没有一项完整覆盖strict response、Decimal、宽row、字节边界与并发回显 | 增加独立`TEST-TXN-015` response contract/concurrency测试 | Closed |

修复后重新从REQ/L0/L1、`L2_00_01`与`L2_02_00` v0.3、当前Transaction API/service/mapper/security事实、descriptor、输入/配置/wire/coverage、Decimal、宽row、JWT/Authority、禁止端点、并发/截止、生命周期、实现签名、测试、发布回滚和全部开放门禁复核；未发现新的S0/S1/S2，`REV-TXN-001`～`REV-TXN-020`全部关闭。评审结论为Approved；该结论不关闭`BQ-GATE-002/003`、`CR-GATE-003`、`SA-GATE-005/006`。

### 16.6 v0.3 精确金额条件修订范围

v0.3 在保持 `transaction.search@1`、现有 endpoint/DTO、单次调用、权限、结果字段和 Date/聚合/写入禁项不变的前提下，新增三个金额过滤参数及其跨语言精确数值链路。这属于动作参数和共享 business wire 的语义变化；历史五轮评审与 `REV-TXN-001`～`020` 的关闭证据只覆盖 v0.2。本次两轮独立复评已覆盖该变化；`BQ-GATE-003` 关闭前，真实金额条件仍失败关闭。

### 16.7 v0.3 第 1 轮独立复评冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-TXN-021` | S2 | `TEST-TXN-004` 要求 4096/4097-byte Transaction 请求，但合法字段长度、条件互斥和排序数量使 typed request 无法到达该边界；测试若强行构造只能绕过自身不变量，无法证明真实 codec 行为 | 域测试改为枚举各类最大合法组合并断言最大 canonical body `<4096`；4096/4097 边界由公共 `TEST-BQCOM-003/014` 独占验证 | Closed |

本轮只修正共享边界与域测试的责任分配，不改变动作参数、金额范围/scale、wire bytes、Java DTO/endpoint、权限或开放门禁。

### 16.8 v0.3 第 2 轮重新复评结论

重新从当前全文及 `L2_02_00` v0.4、`L2_00_01` v0.4、现有 Transaction DTO/service/mapper 事实检查动作参数、Decimal/BigDecimal 精度链路、canonical request、合法请求上界、响应解码、权限、门禁和测试追踪。`TEST-TXN-004` 现在只使用合法 typed request 证明域内请求严格小于 4096 bytes，`TEST-BQCOM-003/014` 继续直接证明共享 encoder 的 4096/4097 bytes 边界；两者责任互补且没有测试绕过。`REV-TXN-021` 已关闭，未发现新的 S0/S1/S2，结论为 Approved。该结论不关闭 `BQ-GATE-002/003`、`CR-GATE-003`、`SA-GATE-005/006`。

### 16.9 v0.6 生产精度对齐增量复核

v0.6 只收紧 Transaction 金额边界：规范输入 grammar 从 4 位小数收紧到 2 位，Agent 绝对值上限从可表达的 `9999999999999999.9999` 收紧为 `9999999999999999.99`，Provider 响应同样只接受 scale≤2。共享 `ExactDecimal`、Core JSON、公开 DTO/endpoint、数据库结构、page/field/业务动作均未变更。

对照审查确认：Python validator 在 HTTP 前拒绝 scale=3 和第 17 位整数，codec 仍以 canonical JSON number 发送；Java deserializer 不经 `double`构造 `BigDecimal`，`TransactionAmountContract` 在 mapper 前按 50/2 失败关闭且不改写值；MySQL 8.0 契约测试验证 `DECIMAL(50,2)` 的 `=/>/<` 精确比较。未发现 S0/S1/S2 代码对照偏差。该增量复核是作者自检+代码对照设计评审，不冒充新一轮独立设计复评；本段记录 v0.6 当时状态，`SA-GATE-005/006` 当时仍为 Open，后续 v0.7 证据仅按受控范围关闭 `SA-GATE-005`。

### 16.10 v0.7 受控真实联调证据与独立代码对照设计复核

`wp-txn-real-01-20260806T134518Z.json`（SHA-256 `1109da47183a822c9ad82fbcc2ef3619163a8089d8f0f420d045e0d30d80f7d1`）严格状态为 passed：真实 admin 两个主体和 viewer 允许，unknown role 返回 forbidden，missing/malformed/service-token 返回 unauthenticated；amount/amountGt/amountLt 与正式 Gateway 路径金额均保持精确 JSON number，mapper 参数未改写。总计 Transaction 请求 7 次、Adapter 6 次、Gateway 1 次，service search 4 次、mapper count 4 次，其他 service 方法、其他 Transaction endpoint 与模型调用均为 0。

证据还确认正式 Gateway MQ 路由被使用，JWT、body、principal、交易值和密钥均未持久化，日志泄漏计数为 0，原始日志已删除。live 数据库未访问且 live 响应为空，因此数据库 `=/>/<` 精确比较继续由 `VAL-TXN-003` 的 MySQL `DECIMAL(50,2)` 契约测试证明，响应可见性由版本化 Provider contract 与空 live response 共同证明；不得把本 evidence 误写成非空真实业务数据或生产数据库验证。

独立代码对照设计复核结合上述 evidence、Python/Java 定向回归和 MySQL 契约测试检查了 Authority、guard、精度、禁止入口、调用计数、日志与默认关闭边界，未发现 S0/S1/S2。由此关闭 `SA-GATE-005`，并允许 P3 关闭 `GATE-018/031`、将 `WP-TXN-REAL-01` 标记 Done；后续问题输入非 live 证据已关闭 `CR-GATE-003/GATE-025`，但 `SA-GATE-006/GATE-026`、默认/生产启用和真实结果模型出域保持 Open。

### 16.11 v0.8 Transaction Resolver 评审批次

| 阶段 | 审计 ID | 本文重点 | 结论 |
|---|---|---|---|
| 三轮作者内审 | `AR-HYBRID-01～03` | whole-string/HEADSEP/子句切分、最长 token、金额字符串保真、重复/互斥/范围与终止标点 | 修复后无遗留 Blocker/Major，严格校验通过 |
| 五轮独立评审 | `FR-HYBRID-01～05` | no-match/invalid/ambiguous 边界、模型/HTTP 零调用、最终 validator/配置复核、ExactDecimal/BigDecimal/50,2 与既有 Provider 证据兼容 | 新增发现均已关闭，无未关闭 S0/S1/S2；`SA-GATE-005` 证据保持有效，Resolver 仍未实施 |

逐轮冻结发现与原子修复摘要见 `P3_00` 13.18；本批次不改变公开 DTO、数据库结构、金额上限、Date/聚合/写入禁项或模型出域门禁。

### 16.12 v0.12 Transaction egress candidate-01 non-live代码对照设计复核

candidate测试切片复用生产`TransactionSearchArgumentValidator`、request mapper/codec、normalizer、字段定义、Business投影/grounding与Runtime answer generator。fake请求固定为单个`trans_type`等值条件、`page/size=1`且sorts为空；响应只向模型形成`transaction_type/amount`，金额精确字符串`100.10`通过新增grounding回归。Decimal修复仅避免把数字内部`.`当句号，不改变token白名单、fact marker或接受阈值。

生命周期在search前exclusive-create并fsync，严格记录search started/terminal和30次answer started/terminal，首次模型delegate前写consumed；passed/failed_unconsumed/failed_consumed、retry/resume=0和有限result Schema均由故障注入验证。run `transaction-egress-v1-20260814-candidate-01`、manifest SHA-256 `dba4610cc0e578e65c45b49b288ce9d4b74b90eea9f9d05609e7935dd2feac44`、authorization `P3_00:GATE-026`已冻结；全量non-live 913 passed/18 skipped、strict mypy321、compileall/PowerShell AST/Schema通过。真实Transaction与DeepSeek调用均为0，未发现S0/S1/S2偏差。

### 16.13 v0.13 Business Answer v2影响与candidate-02聚焦独立设计评审

| 复核项 | 证据与判断 | 结论 |
|---|---|---|
| 域契约 | answer v2只强化模型可见fact marker，不改变search、type/amount facts、Decimal/BigDecimal、grounding或安全矩阵 | Transaction生产代码与公开契约无需修改 |
| candidate-01身份 | manifest/auth未消费，但冻结了answer v1和旧bootstrap；生产切换v2后current-source不再匹配 | 不应原地重算或继续live；candidate-01转为不可变退役历史 |
| candidate-02 | 全新run/manifest/auth绑定v2/new bootstrap和candidate-01历史，继续fake验证1/30、精确金额与三终态 | 只在`GATE-053`关闭后由`GATE-055`另行授权准备 |
| 门禁 | `GATE-055`单向连接v2本地实现与`GATE-026` live | 无环；本轮不创建candidate-02、不读取密钥、不产生outbound |

聚焦独立设计评审无未关闭S0/S1/S2。

### 16.14 v0.18 candidate-03失败归档与candidate-04聚焦独立设计评审

| 复核项 | 证据与判断 | 结论 |
|---|---|---|
| 失败窗口 | preflight、SELECT与search均完成；consumed不存在且answer started/terminal=0/0，失败发生在第一次model delegate前的test-only request检查 | 不是DeepSeek、Transaction Provider、Decimal或生产egress失败 |
| 最小修复 | exact payload keys继续只允许type/amount并保留grounding所需record_ref；forbidden literal排除这些获准值/结构元数据，但仍覆盖JWT、key、`transaction_id_masked`及未知字段 | 安全边界未放宽；只消除test harness自相矛盾 |
| 历史与兼容 | candidate-03六项文件及SHA只读，SELECT/search预算已使用；candidate-04全新run/manifest/auth绑定旧历史 | 旧run即使未消费模型授权也不得复用 |
| 门禁与DAG | candidate-04 prep单向依赖candidate-03，完成后才进入既有live包 | `GATE-057`仅控制non-live；`GATE-026`继续Open且DAG无环 |

独立聚焦设计评审无未关闭S0/S1/S2；不建议修改生产Adapter、Provider、金额、字段或公共契约。

### 16.15 v0.19 candidate-04 non-live实施与代码对照设计复核

| 复核项 | 证据与判断 | 结论 |
|---|---|---|
| 允许/禁止边界 | live同源fake正向证明type/amount与record_ref可到delegate；反向证明JWT/key、非模型高熵值、`transaction_id_masked` field ID和未知safe-payload key均零delegate | 符合`DR-TXN-017`，生产字段矩阵、Decimal、validator和grounding均未修改 |
| 历史与冻结 | candidate-03六项文件SHA精确不变；candidate-04绑定15项history、33项asset、answer v2与当前bootstrap | run=`transaction-egress-v4-20260817-candidate-04`；manifest/authorization SHA-256=`ca440b8f3cf664cfe77b803c6a7786816935d391bc56e50a522f6cb76f0535d3`/`885ddb8854b34ccebf29d481e78fb84b1b6a550adf5330bf321eea5085690359` |
| 预算与失败关闭 | fake继续覆盖search1、answer30、有效≥27、三终态、首次delegate前consume和retry/resume=0；prepared正式输出不存在 | 数据库、Transaction、JWT、密钥、DeepSeek与outbound均0 |
| 验证与提交 | 定向34 passed/1 skipped；Transaction/Business 230 passed/5 skipped/1历史deselect；全量1130 passed/27 skipped/2历史deselect；strict mypy、compileall、AST、历史hash、敏感扫描和代码复核通过 | 非Markdown资产已提交推送至frozen HEAD=`680cd25ac0475f301260123c8ce6229ed05dc8c9`；无未关闭S0/S1/S2 |

本轮只关闭`GATE-057`并将candidate-04 prep置Done；`GATE-026/SA-GATE-006/GATE-034`继续Open，且本文不构成任何live执行授权。

### 16.16 v0.20 Transaction live bootstrap聚焦设计内审

三轮内审依次关闭了datasource临时正则与证据边界、outer/inner双重调用权威、入口门禁与完成门禁混用三个问题。latest bootstrap failure按精确SHA只读，candidate-04与生产Adapter/Provider/API/Decimal/字段均不修改。

### 16.17 v0.20 Transaction live bootstrap独立聚焦设计评审

独立评审按公共`REV-BQBOOT-001～003`复核两步冻结、固定datasource键、端口/PID所有权、timeout/cancel、pre-SELECT失败与门禁无环性；Transaction wrapper唯一启动隔离auth与Transaction进程，inner candidate唯一拥有SELECT/search/model/consumed。未发现未关闭S0/S1/S2；允许实施`IMPL-TXN-020`的fake/static non-live切片，不授权数据库、服务、JWT、密钥或outbound。

### 16.18 v0.22 wrapper-v1失败与wrapper-v2聚焦评审

| 复核项 | 冻结证据与判断 | 结论 |
|---|---|---|
| 失败窗口 | wrapper-v1在`auth_start`通过、`auth_readiness`以`process_exited`失败；candidateInvoked=false，inner输出全部不存在 | SELECT/search/model均0；不否定Adapter、Provider、Decimal、字段或candidate-04 |
| 可追溯性 | v1 manifest冻结wrapper源码但只以`is_file()`检查target JAR；JAR未进入执行资产哈希 | 不能证明实际启动字节对应prepared源码，必须由独立v2修复 |
| 诊断与安全 | v1只保留`process_exited`，原始日志已安全扫描并删除 | 不应保留原日志；应在删除前映射到严格有限枚举，未知继续失败关闭 |
| 历史与门禁 | wrapper-v1 manifest/auth/lifecycle/result由commit `7665022`中的history test精确锁定；`GATE-026`已消费 | 旧run/授权不得重开；新wrapper使用`GATE-060`准备和未来`GATE-061`执行 |
| 兼容与DAG | candidate-04没有被调用且全部inner输出不存在；v2只替换外层测试宿主 | candidate-04可继续被新wrapper引用；完成门禁仍单向位于`GATE-034/SA-GATE-006` |

聚焦评审未发现阻断`IMPL-TXN-021` non-live实施的S0/S1/S2。不得修改v1历史、生产代码或candidate-04；本结论不授权真实服务、secret、SELECT、Transaction或DeepSeek调用。

### 16.19 v0.23 wrapper-v2 non-live实施与代码对照设计复核

| 复核项 | 实施与验证证据 | 结论 |
|---|---|---|
| 实现边界 | 仅新增test-only公共v2 helper、Transaction `live_bootstrap_v2.py`、版本化launcher、strict diagnostic Schema、manifest/auth及直接测试；生产Adapter/Provider/API/Decimal、candidate-04和wrapper-v1均未修改 | 符合`DR-TXN-019`最小边界 |
| 授权与调用权威 | outer wrapper固定`P3_00:GATE-061`，inner candidate继续传递其冻结的`P3_00:GATE-026`；outer不拥有SELECT/search/model，candidate未被调用 | 修复首次代码复核发现的outer/inner授权引用混用，不改candidate冻结资产 |
| 冻结身份 | source commit=`779c03c084655b2b2caa535c05911f303194f5e8`；prepared HEAD=`196845090124344deda901132ccd4cdc6c2149eb`；manifest/auth SHA-256=`a244abd6da21ce4bc04c65480208989714380dfbc7a28e61261bb97797fefd0d`/`46f0a6e78b341e6d106d75e4bd72560fd508036844e3fef2085fccdae9d275be` | 两步冻结成立，v1四项历史和candidate-04哈希继续受测 |
| JAR provenance | 确定性Maven构建成功；auth/Transaction JAR SHA-256=`da59695336c6f2fd11581760b41f0958114ac1f9e728ad834ff1a25a7595a96b`/`69cbb7a7a1b3193fb5d06a2c9af474e54917b1ac9c7786dcac1565aa32a8487e` | 执行字节、源码commit和构建命令已冻结；构建前后哈希一致，不支持“旧JAR导致v1失败”的原假设 |
| 验证与复核 | 定向21 passed；Transaction/bootstrap 152 passed、5 live skipped、2个历史prepared-only断言排除；Business/Transaction 127 passed；strict mypy 395 files、compileall、AST与历史哈希通过；独立复核补齐build/source和构建命令漂移反证 | 无未关闭S0/S1/S2；外部调用0，正式v2输出不存在 |

`IMPL-TXN-021/TEST-TXN-023/VAL-TXN-013`已满足，`GATE-060`关闭。后续只可通过精确绑定的`GATE-061`执行一次wrapper-v2；`GATE-034/SA-GATE-006[Transaction]`保持Open。

