# [L2_02_00] 单体 Agent 业务查询公共约束、配置与出域详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent 业务查询公共约束、配置与出域详细设计 |
| 文档标识 | `SA-L2-BUSINESS-COMMON-001` |
| 文档编号 | `L2_02_00` |
| 文档路径 | `docs/design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 历史 Employee/Transaction 结论、candidate/wrapper 资产及失败证据保持不可变；v0.57 完成现行权威与历史审计的物理分层，不改变真实 Provider + stub 模型系统 E2E 与可选真实业务结果外发实验的既有边界 |
| 当前版本 | v0.57 |
| 日期 | 2026-08-20 |
| 适用范围 | Python `agent-runtime` 内 Employee/Transaction Adapter 共用的代码绑定动作与本地 Resolver 绑定原语、强类型配置收紧、用户 JWT 透传、统一 Authority 外部契约消费语义、类型化业务结果、字段交集、模型出域、组合根与公共测试替身 |
| 上位文档 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v1.3；[`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v0.13；[`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.5（已评审/已通过，`BQ-GATE-001/CR-GATE-003` 已按各自范围关闭） |
| 直接依赖 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.11（Approved）的 `LocalActionResolver`、能力 API、JWT wrapper 和公共结果；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v0.23 的 selection-only、`question-egress-v2`、已实现`answer-generation-v2`与既有safe payload/grounding接缝 |
| 下位/后续契约 | [`L2_02_01`](L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v0.51 Approved；[`L2_02_02`](L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v0.25 Approved；Employee/Transaction 历史 candidate 与 wrapper 继续保持不可变，后续真实业务结果外发须作为新实验重新立项和授权 |
| 外部契约 | `auth-service` 用户 JWT；`common-security` role→Authority；`employee-service`、`mq-procedure-service` 公开只读查询契约 |
| 实现基线 | v0.5 Business common、两个 Adapter、共享 Authority Converter、两个 Java Provider 与受控真实联调已有证据；Employee 输入资格的最终受控验证已通过，生产 common、facts、Runtime answer、grounding、API 与数据结构未改变。精确 run、manifest 与 evidence 哈希见[历史审计记录](history/L2_02_00_BUSINESS_QUERY_AUDIT_HISTORY.md) |
| 是否可作为实现依据 | 按范围可用 |
| 当前允许实施范围 | 只读维护既有实现和历史审计资产；当前 P4 已基于真实 Provider、业务授权和默认 stub 模型完成系统 E2E。Employee wrapper-v3 修复及两域真实业务结果外部模型实验均为 Deferred，不属于当前交付周期 |
| 当前禁止动作 | 在 Agent 侧判定业务角色；扩大业务契约、授权或模型出域字段；修改 Java/公开 API；默认或生产启用任一业务动作；启用未获对应门禁允许的其他真实业务动作；发送真实业务数据到 DeepSeek |
| 修改权限 | 本轮仅授权设计与计划 Markdown 原子同步；未授权代码、测试资产、真实服务、secret、SQL、领域请求、模型 outbound 或 Git 提交推送 |
| 维护责任人 | 项目维护者（个人开发者，姓名未在需求中指定） |

> 本文只定义两个业务域可以复用的无业务字段语义原语，不列出 Employee/Transaction 精确动作、端点、请求/响应字段或业务授权实现。公共原语不得演化为动态 HTTP Adapter、权限引擎或字段脚本平台。

## 2. 修改历史

> 完整修改历史已迁移至 [L2_02_00 历史审计记录](history/L2_02_00_BUSINESS_QUERY_AUDIT_HISTORY.md)；历史文档只作审计，不覆盖本文当前权威。

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-08-20 | 文档治理、历史与评审章节 | 对现行文档执行物理瘦身 | 更新为 v0.57；完整历史与逐轮记录迁移到只读审计附件；稳定标识、设计语义、当前门禁、状态和结论不变 |

## 3. 背景、目标与范围

### 3.1 背景与问题

L1_02 已确定 Employee、Transaction 使用两个独立 Python Adapter，直接作为能力处理器注册；业务服务拥有最终角色授权，Adapter 只透传用户 JWT、收紧参数/字段并构造模型安全载荷。当前缺少一套公共但不含域业务语义的实现级规则，容易导致：

1. 两个 Adapter 各自定义 JWT 透传、错误状态和字段出域，产生契约漂移。
2. 复用现有服务令牌兜底，绕过用户身份和业务域审计主体。
3. 把 Adapter 字段投影误当成业务服务行级/字段级授权。
4. 配置增加动作、URL、字段或转换逻辑，演化为动态执行平台。
5. 已存在记录经字段删除后被误报为 `no_result` 或空 `success`。
6. 业务字符串被模型当作指令，或回答补造安全载荷外的实体、数值和状态。

### 3.2 目标与验收行为

| 需求编号 | 目标或用户可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-BQCOM-001` | 两域使用同一公共动作/结果骨架但保持域隔离 | 公共模块无 Employee/Transaction 字段或端点；两个域用代码定义实例化；模拟第三域不修改 core/现有 Adapter | REQ_00 EXT-01/02；L1_02 6、13 |
| `REQ-BQCOM-002` | 配置只能启停和收紧已确认动作 | 未知动作/字段/维度/转换、扩大上限、删除必需用户字段均在启动时失败 | REQ_00 CFG-01～04；L1_02 6.3 |
| `REQ-BQCOM-003` | 每次业务调用只透传当前原始用户 JWT | 缺 JWT、非 user context 或 token 为空时业务调用为零；不存在服务 token/固定管理员兜底 | REQ_00 SEC-01/02；L1_02 7.3 |
| `REQ-BQCOM-004` | 角色由统一安全契约映射并由业务服务最终验证 | `ADMIN/VIEWER` 消费场景形成预期 Authority；缺失/空白/未知/格式错误拒绝；Adapter 不读取 role 作授权 | REQ_00 SEC-03/04；L0 `SA-FACT-015` |
| `REQ-BQCOM-005` | 业务无结果、已有记录和契约失败保持真实语义 | `no_result` 只来自确认后的业务无数据语义；存在记录但必需用户字段缺失返回 `downstream_failure` | L1_02 7.5 |
| `REQ-BQCOM-006` | 用户结果和模型字段按多重交集失败关闭 | 未声明/未分类/额外/冲突字段不进入视图；模型字段必为用户结果字段子集 | L0 `SA-C-020`；L1_02 7.6 |
| `REQ-BQCOM-007` | 有限转换在模型调用前由代码执行 | 配置只能选择有限枚举；类型不匹配/转换失败时 safe payload 不存在且回答模型零调用 | REQ_00 CFG-03；L1_02 `BQ-AD-007` |
| `REQ-BQCOM-008` | 业务回答的肯定事实可追踪到本次安全载荷 | 每条回答语句带 fact 引用；引用存在且数字/日期/枚举/标识值来自事实；否则候选答案丢弃 | L1_02 7.6、10.2 |
| `REQ-BQCOM-009` | 失败状态和调用方可见语义稳定 | `401/403/no_result/invalid_argument/timeout/downstream_failure` 不混淆；模型拒绝保留有效本地结果，business common 不误发 `model_egress_denied`；原始错误不外泄 | REQ_00 异常要求；L1_02 7.7 |
| `REQ-BQCOM-010` | 业务敏感问题提供给全局输入闸门验证 | Employee/Transaction 标识、个人标识、账户、联系方式、凭证和敏感自由文本场景均有零调用测试 | L1_02 10.1；`CR-GATE-003` |
| `REQ-BQCOM-011` | 公共业务查询无持久化、无重试和写副作用 | 每个动作最多一次业务调用；取消/超时后不接纳结果；无 cache/database/message/replay | L1_02 9.3、10.3 |
| `REQ-BQCOM-012` | 业务请求可无损表达精确十进制 | 最终候选金额字符串不经过 binary float；域 validator 产生 `Decimal`，业务 wire 以 canonical JSON number 传输并由 Java `BigDecimal` 精确接收 | 用户确认；现有 Transaction `BigDecimal` 查询契约 |
| `REQ-BQCOM-013` | 每个启用且具有非空执行参数 Schema 的业务动作绑定一个本地 Resolver | definition 内 Resolver ID 必须等于 descriptor ID；配置不能替换/修改语法；组合根只把启用动作 Resolver 显式交给 Core；模型和 Adapter 调用阶段均不读取 Resolver | L0 `SA-C-022`；L1_02 `BQ-AD-011` |
| `REQ-BQCOM-014` | 受控业务结果出域候选在模型调用前也必须具有可审计、失败关闭的有限生命周期 | 域请求前创建 append-only journal；精确记录域请求尝试和终态；区分 `failed_unconsumed/failed_consumed`；只在首次模型 outbound 前消费授权；任一可控失败均写有限 evidence，且 retry/resume 恒为0 | 用户 2026-08-14 授权；candidate-01 pre-model failure evidence SHA-256 `1a55b324fc912ee4e9133c2946183473347eb8e7f3337f8e33286bdf96f0b76f` |
| `REQ-BQCOM-015` | 新 Employee live 候选只能使用可形成完整最小用户结果及最小安全 facts 的已验证输入 | 独立资格 candidate 只读筛选至多一条候选，筛选覆盖 Employee codec 的 `idCardNo/chineseName/position/workBaseSi` 最小要求；一次真实 detail 还须证明 `employee_id_masked/chinese_name` 用户结果完整、`position/work_base_si` 投影 allowed。标识、JWT、字段值和原始响应只驻留内存 | candidate-02 `failed_unconsumed/egress_projection_invalid`；用户 2026-08-14 最新授权 |
| `REQ-BQCOM-016` | `work_base_si` 计数归零必须先以静态来源诊断排除映射缺陷并界定证据缺口 | 绑定既有聚合 evidence 精确哈希；核对实体、ResultMap、SELECT/INSERT/UPDATE、通用 Map 写入口、版本化 DDL/初始化/导入/回填和下游 ES；只输出路径哈希、布尔值、整数计数和有限结论，不查询数据库或业务端点 | 用户 2026-08-14 授权 |
| `REQ-BQCOM-017` | 以最小只读查询证明 `WORK_BASE_SI` 的物理列定义和无效值类别 | 元数据只返回六项固定列定义且恰好1行；数据只返回单行互斥整数分类，五类计数之和等于总数；静态 evidence 的990/0快照不一致时失败关闭 | 用户 2026-08-14 授权 |
| `REQ-BQCOM-018` | 新资格 candidate 前只能准备一条独立、非真实身份、可精确清理的合成 Employee fixture | 不修改现有990条记录；逻辑最小非空字段限定为 `idCardNo/chineseName/position/workBaseSi`，标识必须确定性且显式标记 synthetic；创建前、写入、精确验证、清理和恢复均有耐久有限 lifecycle。若完整物理约束不能由静态代码证明，则 fake repository 与 fixture 实施均失败关闭 | 用户 2026-08-14 授权；两查询 evidence SHA-256=`b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6` |
| `REQ-BQCOM-019` | 将已验证的synthetic fixture契约实例化为一次性真实create/verify/cleanup候选 | candidate必须绑定已关闭`GATE-050`的六项来源历史，以显式事务提交1次INSERT和1次exact DELETE，最多3次SELECT；数据库阶段和宿主日志阶段共享耐久有限生命周期。prepared状态不得访问数据库，正式执行须独立精确授权`GATE-051` | `DR-BQCOM-027～030`；P3_00持续目标 |
| `REQ-BQCOM-020` | Transaction 真实结果出域必须先形成一次性、可审计且字段最小的非 live 候选 | 只允许1次 `transaction.search`、最多30次answer；模型事实仅含 `transaction_type/amount`，金额保持精确十进制文本；只保留公共safe payload既有`coverage.truncated`安全布尔，禁止provider coverage计数/总量、交易ID、日期、聚合与原始值进入facts或有限证据；首个模型outbound前消费，三终态且retry/resume=0 | `L2_00_02 REQ-MODEL-012`；`L2_02_02 REQ-TXN-011`；`P3_00 GATE-026` |
| `REQ-BQCOM-021` | Employee 资格恢复必须在同一受控生命周期内创建合成记录、验证一次真实 detail 并精确清理 | 测试候选复用四字段 synthetic fixture 与生产 Employee codec/user/egress 投影；数据库 SELECT/INSERT/DELETE 最大3/1/1，detail最大1，模型0；任何 INSERT 后路径均进入 exact cleanup，只有四字段/两用户字段/egress均通过且 deleted=1、remaining=0 才可 `qualified` | `GATE-051`关闭证据；`P3_00 GATE-049` |
| `REQ-BQCOM-022` | Spring测试上下文失败不得形成无证据窗口或复用已尝试run | candidate-03首SQL前失败须作为不可变`failed_unconsumed`历史；后继candidate显式绑定唯一生产启动类，并在启动Maven/Spring前建立host级pre-SQL journal，任何上下文失败均形成有限结果且数据库/detail/model计数为0 | candidate-03 pre-SQL failure evidence；`P3_00 GATE-049` |
| `REQ-BQCOM-023` | 一次性live候选的writer、finalizer与冻结validator必须接受同一唯一生命周期语言 | 每个受控阶段均须按设计形成可由冻结validator重放的started/terminal序列；运行时业务结果满足但权威validator拒绝时，必须保留历史并失败关闭，不得以结果字段、手工解释、放宽validator或改写证据关闭门禁 | candidate-04 post-consumption证据；`P3_00 GATE-049` |
| `REQ-BQCOM-024` | candidate-05冻结前必须以真实live finalizer路径证明完整生命周期可由同一冻结validator接受 | finalizer必须写入`host_validation started/terminal`、再写run终态，并在result exclusive-create前调用同模块`validate_lifecycle()`；non-live须覆盖qualified、host执行失败和日志泄漏分支，任一分支不得产生未校验result | `REQ-BQCOM-023`；candidate-04三项失败关闭证据 |
| `REQ-BQCOM-025` | 跨语言资格staging的`codec`容器基数必须与固定键集合一致 | Python staging、JSON Schema、Java loader与测试均只能接受`idCardNo/chineseName/position/workBaseSi`四键；必须同时校验exact key set、size=4和boolean类型，不得新增占位键或放宽未知字段 | candidate-05失败证据；现有Employee codec与`_validate_presence()` |
| `REQ-BQCOM-026` | Employee真实结果出域候选必须把合成fixture、一次detail、模型调用和精确清理纳入同一不可重放生命周期 | 新run在首SQL前耐久记录，SELECT/INSERT/DELETE最大3/1/1、detail恰好1、answer恰好30且有效至少27；只允许`position/work_base_si`进入模型；首次模型outbound前消费；任何INSERT后路径均finally exact cleanup，只有cleanup已证明且全链安全计数为0才可通过 | `GATE-049`关闭证据；`REQ-BQCOM-014/019/025`；`P3_00 GATE-024` |
| `REQ-BQCOM-027` | Business模型输出指令必须显式满足既有事实引用validator，而不是通过放宽validator容忍模型缺少引用 | 生产answer task要求每个非空事实片段含`[fact-NNNN]`，marker集合与去重`used_fact_ids`集合相等；现有sentence/token/protected-token/coverage校验完全不变 | Employee candidate-03 30/30 `invalid_output`证据；`L2_00_02 REQ-MODEL-013` |
| `REQ-BQCOM-028` | 一次性业务出域候选必须在消耗数据库选择或业务调用预算前证明测试运行时可从冻结仓库来源导入 | versioned host launcher先建立并fsync有限preflight journal，再以显式、作用域受控且finally恢复的Python导入路径验证`agent_runtime`来自当前冻结`agent-runtime/src`；失败形成有限`failed_unconsumed`证据且database selector/domain/model均为0 | Transaction candidate-02初始化失败证据SHA-256=`37c4cf079cf1bb28e17c9b087df5707bf19c5bbfd8318d6c3f5f611f08fd72d9` |
| `REQ-BQCOM-029` | 一次性业务出域候选的测试安全检查必须区分“获准模型事实值”和“禁止外发秘密/非模型字段值” | 禁止字面量集合必须包含JWT、API key及非模型字段的高熵字符串值，不得包含字段矩阵已批准且实际位于safe payload中的`transaction_type/amount`值；允许值仍由exact payload key、field ID、转换和grounding契约严格限定 | Transaction candidate-03 `failed_unconsumed`证据；模型调用0，`forbiddenLiteralCount=7` |
| `REQ-BQCOM-030` | 一次性业务出域的candidate外部启动环境必须与candidate本身同样版本化、可冻结和失败关闭 | 在读取密钥/数据库值、启动服务或调用candidate前创建并fsync外层lifecycle；wrapper manifest精确绑定candidate manifest/auth、wrapper源码、Schema/测试、历史失败证据及源码提交；任一candidate前失败形成有限`failed_pre_candidate_unconsumed`证据，领域/模型调用均0且只清理由本次启动并核实PID的进程 | `GATE-024/026`聚焦审计；Transaction bootstrap failure SHA-256=`b831d2f9d019fcd3347f389cd92fa00b0fc5e6deee3efd2ff0024c17594c7357` |
| `REQ-BQCOM-031` | versioned live bootstrap必须同时冻结源码与实际启动产物，并为进程提前退出保留可操作但不泄密的有限诊断 | 新wrapper manifest除源码/Schema/tests/history外，必须绑定auth与领域服务可执行JAR的路径、SHA-256、构建命令和对应源码提交；asset preflight在启动前重算JAR哈希。原始日志只驻留临时目录，cleanup前按有限枚举分类`process_exited`，证据不得包含原始消息、路径、配置值或秘密 | Transaction wrapper-v1 `auth_readiness/process_exited`；lifecycle/result SHA-256见修改历史66 |
| `REQ-BQCOM-032` | 未执行的Employee wrapper也不得复用已证实存在产物身份与诊断缺口的共享v1启动边界 | 新Employee wrapper使用全新run/manifest/auth，冻结实际auth JAR SHA、确定性构建命令、源码commit、wrapper-v1 prepared历史与candidate-04；在删除原始日志前只写严格有限diagnostic。旧wrapper保持未消费只读，不以重新构建或历史测试通过替代新冻结 | Transaction wrapper-v1失败与`REQ-BQCOM-031`实现证据；Employee wrapper-v1代码/manifest只读审计 |
| `REQ-BQCOM-033` | Employee outer preflight必须区分executor在本次run中合法创建的lifecycle与执行前已存在的历史输出 | 执行前仍要求outer/inner输出全不存在；共享executor以exclusive-create创建当前lifecycle后，域内preflight必须接受该唯一当前journal，仅拒绝outer result/diagnostic、任一inner输出或资产漂移。不得通过删除检查、放宽历史哈希或复用失败run解决 | wrapper-v2 result/lifecycle及`business_egress_live_bootstrap.py:BootstrapJournal/execute_bootstrap`、Employee `_asset_preflight`当前行为 |
| `REQ-BQCOM-034` | 当前 P3/P4 的业务查询完成条件必须与可选真实业务结果外部模型实验解耦 | 系统 E2E 使用真实 Employee/Transaction Provider、真实业务授权和默认 stub 模型，验证动作、权限、字段、Decimal、失败语义及端到端路由；不产生真实业务数据模型 outbound。历史30次/有效27次阈值仅属于对应冻结实验，不再作为当前 P3/P4 完成条件 | L0 `SA-AD-017`；L1_02 `BQ-AD-012`；当前项目为个人学习与架构验证 |

### 3.3 范围内

- 业务动作定义、适用约束维度、强类型收紧设置和启动快照。
- 类型化业务调用结果、受控用户结果、最小有效结果不变量和公共失败映射。
- 用户 JWT 专用只读 HTTP 客户端原则、取消/超时/响应大小和零服务身份兜底。
- role→Authority 的业务查询消费假设、现状差距和端到端联调矩阵。
- 字段分类、用户/模型字段交集、代码有限转换、safe payload 和 grounding policy。
- 业务敏感问题类别、日志/审计、组合根、模拟第三域和公共测试替身。
- `BusinessActionDefinition` 对 Provider-neutral `LocalActionResolver` 的代码绑定、一致性校验和组合根投影；不定义具体域语法。
- 业务 HTTP 请求专用的精确十进制值、canonical JSON number 编码及跨语言映射。
- 受控业务结果出域测试候选的 pre-model 生命周期、消费边界、有限终态和精确域调用计数；由 Employee 历史候选及 Transaction candidate-01 测试资产实例化，不新增生产 Runtime 抽象。
- 合成 Employee 测试数据准备的公共安全不变量：零既有记录修改、单记录创建、精确匹配清理、异常恢复和有限 evidence；物理字段/SQL 细节仍归 Employee L2。
- candidate外部test-only live bootstrap：资产预检、受控配置读取、auth/领域服务生命周期、JWT内存签发、PID/readiness、日志扫描删除及candidate调用边界；不进入生产Runtime或公共API。

### 3.4 范围外

- Employee/Transaction 精确动作 ID、端点、输入 DTO、结果字段、分页/时间上限、字段分类实例和方法授权；归各域 L2。
- 修改 `auth-service` 用户/角色、JWT 公共契约或 `common-security` 转换实现；需要时由其权威另行设计并获授权。
- 修改 `employee-service`、`mq-procedure-service` 接口、守卫、方法授权或响应数据可见性；归域 L2/提供方设计并受门禁控制。
- DeepSeek HTTP、Prompt 通用结构、Provider 失败、全局问题输入策略；归 `L2_00_02`。
- Knowledge、聚合、跨域组合、写入、审批、消息提交、索引管理、Multi-Agent 和生产级韧性平台。
- 扩大 L2_00_01 的 Core `JsonObject` 白名单、允许 binary float 表达金额，或把 Java `BigDecimal` 类型泄漏进 Python/Core 公共契约。
- 在 `GATE-050` 关闭前实现 fake/real fixture repository、执行任何 Employee 数据读写、创建新资格 candidate，或把 synthetic fixture 作为长期种子/业务数据保留。

### 3.5 适用技术剖面

| 剖面 | 适用性 | 说明 |
|---|---|---|
| Python | 适用 | 公共动作、设置、HTTP/JWT、投影、转换、事实及测试原语 |
| Java | 只读消费边界适用 | 本文记录当前 Java 触点和可观察 Authority 契约，不设计提供方私有实现或修改类 |
| HTTP/API | 适用 | Python→业务服务单次只读调用的通用安全/失败规则；精确路径归域 L2 |
| 配置 | 适用 | 全局出域硬限制和每动作收紧型设置；启动冻结 |
| 权限/审计 | 适用 | 用户 JWT、Authority、业务最终授权、字段最小化和日志禁项 |
| 状态/一致性 | 适用 | 单请求只读状态、一次调用、取消和迟到丢弃；无跨资源事务 |
| 数据库/消息/索引 | 不适用 | Adapter 不直接访问或写入这些资源 |
| 测试 | 适用 | Python 单元/契约/架构、Java 外部契约证据和跨服务集成矩阵 |

### 3.6 完成判定

本文达到“可进入独立正式评审”的条件为：

1. 公共结构不含两个域的具体业务字段/端点，且域 L2 可直接实例化。
2. 配置交集、最小有效用户结果、转换枚举和 safe payload 字段完整。
3. JWT/Authority 消费边界、当前差距、失败关闭和联调证据明确。
4. Python 公共类型和边界函数具有建议路径、签名、输入/输出、异步、错误和消费者。
5. Java 当前触点与“本文不修改”的边界明确。
6. 全部 REQ/CON 追踪完整，作者自检无 Blocker/Major，严格校验 0 errors、0 warnings。

## 4. 上位约束与追踪关系

### 4.1 约束映射

| 约束编号 | 上位文档/契约位置 | 约束内容 | 本设计落实方式 | 偏离情况 |
|---|---|---|---|---|
| `CON-BQCOM-001` | L1_02 `BQ-AD-001/002/003` | 两个独立 Adapter、代码绑定有限动作、一个动作映射一个只读契约 | `DR-BQCOM-001`、`DR-BQCOM-015` | 无 |
| `CON-BQCOM-002` | L1_02 6.3、7.2 | 配置只能收紧动作、参数、结果和模型字段 | `DR-BQCOM-002`、`DR-BQCOM-013` | 无 |
| `CON-BQCOM-003` | L1_02 7.3～7.4 | 原始用户 JWT 透传，无服务身份回退，业务服务最终授权 | `DR-BQCOM-003`、`DR-BQCOM-004`、`DR-BQCOM-005` | 无 |
| `CON-BQCOM-004` | L0 `SA-FACT-015`；L1_02 7.4 | 首批共同允许语义角色 `admin/viewer`，统一 Authority 映射归外部权威 | `DR-BQCOM-004` | 无 |
| `CON-BQCOM-005` | L1_02 7.5 | no_result 与已有记录、字段投影和契约失败分离 | `DR-BQCOM-006`、`DR-BQCOM-007` | 无 |
| `CON-BQCOM-006` | L0 `SA-C-020`；L1_02 7.6 | 模型字段为多重交集，未知默认拒绝，转换模型前执行 | `DR-BQCOM-008`、`DR-BQCOM-009`、`DR-BQCOM-010` | 无 |
| `CON-BQCOM-007` | L1_02 7.6；L2_00_02 8.3 | 业务文本是数据，回答事实绑定 safe payload | `DR-BQCOM-010`、`DR-BQCOM-011` | 无 |
| `CON-BQCOM-008` | L1_02 7.7、9.2 | 公共失败稳定且不泄露原始错误 | `DR-BQCOM-012` | 无 |
| `CON-BQCOM-009` | L1_02 8、9.3、10.3 | 无持久化/重试/写入，服从总预算和取消 | `DR-BQCOM-014` | 无 |
| `CON-BQCOM-010` | L1_02 13.3 | 公共 L2 不拥有域字段/端点或共享安全实现 | `DR-BQCOM-015`、`DR-BQCOM-016` | 无 |
| `CON-BQCOM-011` | L1_02 10.1 | 提供业务敏感问题场景但不复制全局输入策略 | `DR-BQCOM-017` | 无 |
| `CON-BQCOM-012` | L2_00_01 8.4 | Core 公共 `JsonObject` 禁止 `Decimal` 和任意自定义对象；域强类型 `TInput` 可在 validator 与 handler 内使用 | `DR-BQCOM-019` | 无；精确十进制只进入 business wire 私有类型 |
| `CON-BQCOM-013` | L1_02 `BQ-AD-011`；L2_00_01 `DR-CORE-015～018` | 域拥有具体 Resolver，common 只绑定/校验，Runtime 混合节点裁决；模型不生成业务参数 | `DR-BQCOM-020` | 无 |
| `CON-BQCOM-014` | 用户 2026-08-14 授权；candidate-01 四项冻结历史 | candidate-01 manifest、authorization、环境诊断和 pre-model failure evidence 字节及哈希不可变；不得以未消费为由补跑/续跑，后继必须创建新版本候选 | `DR-BQCOM-021` | 无 |
| `CON-BQCOM-015` | Employee egress candidate-01/02 八项历史；退役资格 run；用户 2026-08-14 最新授权 | 八项 egress 历史及退役资格 run 六项绑定资产不可变；新资格 candidate 使用全新 run，任何数据库筛选/detail 前必须 exclusive create+fsync lifecycle；非 live 准备不得读取 `LLM_API_KEY`、启动服务/数据库/JWT/detail、生成 outbound、持久化业务值或扩大生产/公开契约 | `DR-BQCOM-022/023` | 无 |
| `CON-BQCOM-016` | `DR-BQCOM-024` 聚合 evidence；用户 2026-08-14 授权 | 静态诊断不得把仓库未版本化的物理列定义、默认值或 990 条原始值分布推断为已确认事实；若静态证据不足，只能列出下一次最小只读元数据/整数聚合所需的独立授权 | `DR-BQCOM-025` | 无 |
| `CON-BQCOM-017` | `DR-BQCOM-025`及静态 evidence SHA-256=`7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8`；用户本轮授权 | 最多两条只读查询；不得返回标识、字段值、原始行或分组，不得调用Employee HTTP/auth/模型，不得修改数据/结构/生产/历史、准备candidate-03或重跑`GATE-049` | `DR-BQCOM-026` | 无 |
| `CON-BQCOM-018` | 用户本轮授权；`DR-BQCOM-026` evidence SHA-256=`b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6` | fixture 不得更新、覆盖或借用现有990条记录；真实写入契约必须先证明全表列约束、表引擎、主键/唯一键、出入向外键、CHECK 与触发器。未知时必须在代码和数据库动作前停止，不得用 fake 测试代替物理契约证据 | `DR-BQCOM-027` | 无；当前以 `GATE-050` 失败关闭 |
| `CON-BQCOM-019` | `GATE-050/GATE-051` Closed；metadata result SHA-256=`9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51` | candidate不得调用Employee API/Service/Mapper、JWT或模型，不得UPDATE或宽DELETE；任何INSERT开始后的失败必须尝试同fingerprint精确清理，不能证明删除1且剩余0时只能`failed_cleanup_required`。candidate-01已成功清理并消费，禁止重跑/resume | `DR-BQCOM-031` | 无；历史run不可复用 |
| `CON-BQCOM-020` | `L2_00_02 DR-MODEL-018`；`SA-GATE-005/GATE-025` Closed，历史`GATE-026`已消费关闭，`GATE-061` Open | Transaction candidate不得改变search参数/Provider/字段矩阵；generic问题只批准无具体值的单条结果说明。prepared阶段只能fake；candidate保持冻结的inner authorization，正式live必须由outer wrapper绑定`GATE-061`并只取已授权单条结果；历史业务/模型manifest与append-only evidence字节不变 | `DR-BQCOM-032`,`DR-BQCOM-043` | `GATE-061/SA-GATE-006/GATE-034` Open |
| `CON-BQCOM-021` | `GATE-050/051` Closed；旧资格candidate-02与fixture candidate-01全部历史不可变 | 新candidate不得复用已消费run或把fixture长期保留；lifecycle必须在首个SQL前exclusive-create+fsync，JWT/标识/字段值仅驻留内存；INSERT开始后无论detail、资格或宿主失败都必须finally exact cleanup。prepared阶段不得访问数据库、启动服务、签JWT或读取模型密钥 | `DR-BQCOM-033` | `GATE-049/024` Open |
| `CON-BQCOM-022` | candidate-03 manifest/auth及pre-SQL failure evidence不可变；failure SHA-256=`bfe4976f9a962bd1f7b9ed870176faefc4fbb742bf9b991cb07bba866a218d77` | candidate-04不得修改或复用candidate-03；Java live test必须显式声明`classes = EmployeeServiceApplication.class`。launcher在Maven/Spring启动前exclusive-create+fsync host journal；若进程未形成SQL lifecycle，必须以`failed_unconsumed`有限结果终止且SQL/detail/model均0 | `DR-BQCOM-034` | `GATE-049/024` Open |
| `CON-BQCOM-023` | candidate-04 manifest/auth/host lifecycle/SQL lifecycle/result与frozen HEAD不可变 | candidate-04业务资格与清理事实可保留，但其15条SQL lifecycle不能作为`GATE-049`关闭证据；未来candidate必须使用全新run/manifest/auth，并在non-live阶段以真实finalizer输出反证冻结validator可接受完整终态，禁止原地修复candidate-04或复用授权 | `DR-BQCOM-035` | `GATE-049/024` Open |
| `CON-BQCOM-024` | `CON-BQCOM-023`及candidate-04五项证据、post-consumption history test不可变；生产Employee/API/数据结构与3/1/1+detail1预算不变 | candidate-05只允许新增versioned test/Schema/launcher/disabled Java资产；history必须直接绑定candidate-04 manifest、authorization、host lifecycle、SQL lifecycle、result、history test及既有十一项历史，共17项。不得修改v4资产、生产src、公开契约或数据库结构；prepared阶段数据库/服务/JWT/detail/model均0 | `DR-BQCOM-036` | `GATE-049/024` Open |
| `CON-BQCOM-025` | candidate-05 manifest/auth/host lifecycle/SQL lifecycle/result及post-consumption history test不可变；其失败不改变公共四键契约 | candidate-06使用全新run/manifest/auth，只允许versioned test-only资产；直接绑定candidate-05六项及既有17项历史，共23项。Java必须按4键读取且继续逐键、类型、outer-shape严格校验；不得修改生产src、公开契约、字段集合、预算或历史证据 | `DR-BQCOM-037` | `GATE-049/024` Open |
| `CON-BQCOM-026` | `GATE-049/050/051`关闭且candidate-06五项证据不可变；Employee egress candidate-01/02及全部资格历史不可变 | candidate-03必须使用全新run/manifest/auth并绑定candidate-06资格、fixture物理契约、既有Employee授权证据、生产field/policy/model/grounding接缝和旧egress历史。prepared阶段只允许fake/static/disabled验证，不得启动服务、访问数据库、签JWT、读取`LLM_API_KEY`或产生outbound；正式live只能由重新精确绑定的`GATE-024`授权 | `DR-BQCOM-038` | `GATE-052`控制non-live冻结；`GATE-024/SA-GATE-006/GATE-033` Open |
| `CON-BQCOM-027` | `L2_00_02 DR-MODEL-019`；公共`CandidateAnswer`、safe payload、field matrix、grounding和全部candidate历史不可变 | answer v2只能改变模型可见task version/指令和生产组合根选择；不得修改Business facts、validator、领域字段、模型输入问题、授权或错误语义。任何绑定旧bootstrap/answer task的候选不得用于新live | `DR-BQCOM-039` | `GATE-053/054/055` |
| `CON-BQCOM-028` | Transaction candidate-02 manifest/authorization及初始化失败证据精确哈希不可变；其一次SELECT已使用，search/model均为0 | 不得修改candidate-02 launcher、补设外部`PYTHONPATH`后重跑或把无lifecycle解释为未尝试。candidate-03使用全新run/manifest/auth，已冻结versioned host launcher、import/collection source校验和preflight失败证据契约；prepared阶段只允许fake/static且外部调用为0 | `DR-BQCOM-040` | `GATE-056` Closed；历史`GATE-026`已消费关闭；`GATE-061/SA-GATE-006/GATE-034` Open |
| `CON-BQCOM-029` | candidate-03 manifest、authorization、host-preflight、host-result、lifecycle、result及六项SHA不可变；该run已使用SELECT1/search1且不得重跑 | candidate-04使用全新run/manifest/auth并绑定candidate-03六项历史。test-only检查必须继续拒绝JWT/API key、未知字段、交易标识、日期、provider coverage计数、总量、原始响应及未经批准的高熵字符串；不得以“修复误拒”为由放宽生产字段矩阵、safe payload、grounding、validator或公开契约 | `DR-BQCOM-041` | `GATE-057` Closed；历史`GATE-026`已消费关闭；`GATE-061/SA-GATE-006/GATE-034` Open |
| `CON-BQCOM-030` | candidate-04 manifest/auth及全部历史证据不可变；旧frozen HEAD只证明candidate prepared来源，不自动覆盖后续wrapper代码 | bootstrap必须以独立wrapper manifest绑定candidate及自身资产；精确资产哈希是执行权威，source commit仅作来源证明。外层不得复制candidate的SQL/detail/search/model/consumed语义，不得把pre-candidate失败记入candidate结果，不得读取或持久化秘密值；non-live准备外部调用必须为0 | `DR-BQCOM-042` | `GATE-058/059`控制bootstrap non-live实现；`GATE-024/026`控制一次性live入口；`GATE-033/034`控制完成声明 |
| `CON-BQCOM-031` | Transaction wrapper-v1 manifest/auth/lifecycle/result与独立历史测试不可变；candidate-04全部inner输出仍不存在 | wrapper-v1授权已消费且不得重跑。wrapper-v2必须使用新run/manifest/auth并绑定wrapper-v1四项历史、candidate-04、精确可执行JAR哈希及有限诊断Schema；不得修改共享v1 helper、candidate-04、生产src或Java生产代码。只有candidate未调用且inner输出全不存在时，candidate-04才可由新wrapper引用 | `DR-BQCOM-043` | `GATE-060`控制non-live准备；未来`GATE-061`控制新wrapper唯一live；`GATE-034/SA-GATE-006[Transaction]`仍控制完成 |
| `CON-BQCOM-032` | Employee wrapper-v1 manifest/auth/source与prepared无输出反证不可变；candidate-04全部inner输出不存在 | wrapper-v1虽未消费但不得执行或原地升级。wrapper-v2必须使用全新run/manifest/auth，绑定wrapper-v1 manifest/auth/history、candidate-04、auth JAR精确哈希、build/source及公共有限diagnostic Schema；不得修改v1 helper、candidate-04、生产src或Java服务 | `DR-BQCOM-044` | `GATE-062`控制non-live准备；`GATE-024`仅在v2冻结后控制唯一live；`GATE-033/SA-GATE-006[Employee]`控制完成 |
| `CON-BQCOM-033` | wrapper-v2 manifest/auth/source、outer lifecycle/result、candidate-04未调用反证及其SHA-256不可变 | wrapper-v2 run虽为`failed_pre_candidate_unconsumed`仍不得重跑、续跑、删除证据或原地修改。修复必须使用全新wrapper-v3 run/manifest/auth并绑定v2失败历史；共享v1/v2 helper、Transaction资产、candidate-04、生产src/API保持只读 | `DR-BQCOM-045` | `GATE-063`控制non-live修复；关闭后才可重新准备`GATE-024`；完成门禁保持Open |
| `CON-BQCOM-034` | L0 `SA-AD-017`、L1_02 `BQ-AD-012` 与 P3 当前交付周期 | 执行许可记录不得兼任验收门禁或 DAG 前置；历史 run/manifest/authorization/evidence 字节及结论保持不变。P3 `GATE-024/033/034/061/063` 在当前周期为 Not Applicable；未来真实业务结果外发必须重新建立 scoped 安全复核、全新执行授权与独立实验计划，不能复用这些门禁或历史授权 | `DR-BQCOM-046` | `SA-GATE-006.EMPLOYEE/TRANSACTION` 均保持 Open；只阻止对应域真实数据外发，不阻塞 Provider + stub 系统 E2E |

### 4.2 端到端追踪矩阵

| REQ/CON | 模块切片 | 设计规则 | 责任主体 | 契约/状态影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-BQCOM-001`、`CON-BQCOM-001` | 公共动作/扩展 | `DR-BQCOM-001`、`DR-BQCOM-015` | business common、域 provider | 代码定义/无动态 Adapter | `IMPL-BQCOM-001/010/011` | `TEST-BQCOM-001/011` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-002`、`CON-BQCOM-002` | 配置 | `DR-BQCOM-002`、`DR-BQCOM-013` | settings validator | 冻结动作快照 | `IMPL-BQCOM-002/009` | `TEST-BQCOM-002/010` | `VAL-BQCOM-002/004` |
| `REQ-BQCOM-003`、`CON-BQCOM-003` | JWT/业务调用 | `DR-BQCOM-003`、`DR-BQCOM-005` | outbound client、域 Adapter | Authorization header/一次调用 | `IMPL-BQCOM-003/014` | `TEST-BQCOM-003/009` | `VAL-BQCOM-002/005` |
| `REQ-BQCOM-004`、`CON-BQCOM-004` | Authority 消费 | `DR-BQCOM-004` | 外部安全权威/业务服务 | role claim→Authority 观察结果 | `IMPL-BQCOM-012` | `TEST-BQCOM-004` | `VAL-BQCOM-005` |
| `REQ-BQCOM-005`、`CON-BQCOM-005` | 响应/用户结果 | `DR-BQCOM-006`、`DR-BQCOM-007` | response mapper、projector | no_result/valid user result | `IMPL-BQCOM-004/005/014` | `TEST-BQCOM-005/006` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-006`、`CON-BQCOM-006` | 字段出域 | `DR-BQCOM-008`、`DR-BQCOM-009`、`DR-BQCOM-010`、`DR-BQCOM-018` | field registry、projector | 用户视图/safe payload | `IMPL-BQCOM-005/006/007` | `TEST-BQCOM-006/007` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-007` | 有限转换 | `DR-BQCOM-009` | transform registry | 转换值/拒绝 | `IMPL-BQCOM-006` | `TEST-BQCOM-007` | `VAL-BQCOM-002` |
| `REQ-BQCOM-008`、`CON-BQCOM-007` | 事实绑定 | `DR-BQCOM-010`、`DR-BQCOM-011` | safe payload、grounding policy | fact ID/候选回答 | `IMPL-BQCOM-007/008` | `TEST-BQCOM-008/012` | `VAL-BQCOM-003` |
| `REQ-BQCOM-009`、`CON-BQCOM-008` | 失败 | `DR-BQCOM-012` | client/mapper/handler | 公共 status/code/source | `IMPL-BQCOM-004/009/014` | `TEST-BQCOM-009` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-010`、`CON-BQCOM-011` | 模型输入负向场景 | `DR-BQCOM-017` | business fixture、L2_00_02 | 问题分类/零调用 | `IMPL-BQCOM-013` | `TEST-BQCOM-013` | `VAL-BQCOM-003` |
| `REQ-BQCOM-011`、`CON-BQCOM-009` | 生命周期 | `DR-BQCOM-014` | handler/client | 请求内只读状态 | `IMPL-BQCOM-003/009/014` | `TEST-BQCOM-009/010` | `VAL-BQCOM-003` |
| `REQ-BQCOM-012`、`CON-BQCOM-012` | 精确十进制业务 wire | `DR-BQCOM-019` | business wire contract/encoder、域 validator/codec | Core JSON 不变；业务请求增加 exact decimal scalar | `IMPL-BQCOM-001/003/015` | `TEST-BQCOM-003/014` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-013`、`CON-BQCOM-013` | Resolver 绑定/装配 | `DR-BQCOM-020` | domain definition、support factory、组合根 | 启用动作 Resolver tuple；执行候选契约不变 | `IMPL-BQCOM-016/017` | `TEST-BQCOM-015/016` | `VAL-BQCOM-006` |
| `REQ-BQCOM-014`、`CON-BQCOM-014` | 受控业务出域候选生命周期 | `DR-BQCOM-021` | 域 candidate harness；当前实例为 Employee candidate-02 | pre-model journal、精确域调用计数、消费前后失败终态；生产契约不变 | `IMPL-BQCOM-018` | `TEST-BQCOM-017` | `VAL-BQCOM-008` |
| `REQ-BQCOM-015`、`CON-BQCOM-015` | Employee 输入资格筛选、candidate-02历史与聚合诊断 | `DR-BQCOM-022`、`DR-BQCOM-023`、`DR-BQCOM-024` | Employee 测试 harness/聚合诊断；Business 投影只读复用 | 历史 journal/result；单条聚合查询、整数计数、有限首个归零条件；生产契约不变 | `IMPL-BQCOM-019`、`IMPL-BQCOM-020`、`IMPL-BQCOM-021` | `TEST-BQCOM-018`、`TEST-BQCOM-019`、`TEST-BQCOM-020` | `VAL-BQCOM-009`、`VAL-BQCOM-010`、`VAL-BQCOM-011` |
| `REQ-BQCOM-016`、`CON-BQCOM-016` | Employee `WORK_BASE_SI` 静态来源诊断 | `DR-BQCOM-025` | Employee 测试范围静态诊断 | 只形成有限来源结论与未知项；生产/数据/历史/门禁不变 | `IMPL-BQCOM-022` | `TEST-BQCOM-021` | `VAL-BQCOM-012` |
| `REQ-BQCOM-017`、`CON-BQCOM-017` | Employee `WORK_BASE_SI` 物理元数据与值类别诊断 | `DR-BQCOM-026` | Employee测试范围Java/Python诊断 | 只形成列元数据、互斥整数分类和有限原因；生产/数据/历史/门禁不变 | `IMPL-BQCOM-023` | `TEST-BQCOM-022` | `VAL-BQCOM-013` |
| `REQ-BQCOM-018`、`CON-BQCOM-018` | Employee synthetic fixture 安全准备与物理元数据前置 | `DR-BQCOM-027`、`DR-BQCOM-028`、`DR-BQCOM-029`、`DR-BQCOM-030` | Employee测试数据准备、candidate-02与post-consumption切片 | fixture non-live已完成；run-01/candidate-02历史不可变；真实fixture和`GATE-049`仍禁止 | `IMPL-BQCOM-024～027` | `TEST-BQCOM-023～026` | `VAL-BQCOM-014～018` |
| `REQ-BQCOM-019`、`CON-BQCOM-019` | Employee synthetic fixture真实候选准备与一次性执行 | `DR-BQCOM-031` | Employee测试范围candidate module/Java test/launcher/Schema | `GATE-051`已消费通过；append-only lifecycle/result与prepared快照不可变 | `IMPL-BQCOM-028` | `TEST-BQCOM-027` | `VAL-BQCOM-019` |
| `REQ-BQCOM-020`、`CON-BQCOM-020` | Transaction结果出域candidate-01 non-live准备 | `DR-BQCOM-032` | Transaction测试范围candidate/launcher/Schema/manifest/auth | prepared live=false；生产接缝只读复用；真实search/model受`GATE-026` | `IMPL-BQCOM-029` | `TEST-BQCOM-028` | `VAL-BQCOM-020` |
| `REQ-BQCOM-021`、`CON-BQCOM-021` | Employee资格candidate-03 non-live准备 | `DR-BQCOM-033` | Employee测试范围candidate/Java test/launcher/Schema/manifest/auth | synthetic fixture与一次detail共享生命周期；生产/API契约不变 | `IMPL-BQCOM-030` | `TEST-BQCOM-029` | `VAL-BQCOM-021` |
| `REQ-BQCOM-022`、`CON-BQCOM-022` | Employee资格candidate-04 non-live准备 | `DR-BQCOM-034` | Employee测试范围candidate/Java test/launcher/Schema/manifest/auth | 显式唯一Spring启动类；启动前host journal与有限失败闭环；生产/API契约不变 | `IMPL-BQCOM-031` | `TEST-BQCOM-030` | `VAL-BQCOM-022` |
| `REQ-BQCOM-023`、`CON-BQCOM-023` | Employee资格candidate-04 post-consumption失败关闭与后继约束 | `DR-BQCOM-035` | 当前history test与未来全新candidate设计 | 已消费证据保持字节不可变；writer/validator不一致不允许关闭门禁 | `IMPL-BQCOM-032` | `TEST-BQCOM-031` | `VAL-BQCOM-023` |
| `REQ-BQCOM-024`、`CON-BQCOM-024` | Employee资格candidate-05 lifecycle一致性non-live准备 | `DR-BQCOM-036` | candidate-05 versioned test-only writer/finalizer/validator与冻结资产 | live同路finalizer的成功/失败输出均须由同一validator接受；prepared阶段外部调用0 | `IMPL-BQCOM-033` | `TEST-BQCOM-032` | `VAL-BQCOM-024` |
| `REQ-BQCOM-025`、`CON-BQCOM-025` | Employee资格candidate-06跨语言codec基数修复 | `DR-BQCOM-037` | candidate-06 versioned Python/Java/Schema/tests/launcher/manifest/auth | 只修复test staging 4键基数；历史、生产与外部契约不变 | `IMPL-BQCOM-034` | `TEST-BQCOM-033` | `VAL-BQCOM-025` |
| `REQ-BQCOM-026`、`CON-BQCOM-026` | Employee egress candidate-03统一fixture/detail/model/cleanup生命周期 | `DR-BQCOM-038` | candidate-03 versioned Python/Java/Schema/tests/launcher/manifest/auth | 单一run覆盖3/1/1、detail1、answer30、首outbound消费与exact cleanup；生产契约不变 | `IMPL-BQCOM-035` | `TEST-BQCOM-034` | `VAL-BQCOM-026` |
| `REQ-BQCOM-027`、`CON-BQCOM-027` | Business Answer v2与既有grounding兼容 | `DR-BQCOM-039` | model answer task、Business grounding与Runtime组合根 | 只强化模型输出约束；public DTO、facts、validator和领域契约不变 | `IMPL-BQCOM-036` | `TEST-BQCOM-035` | `VAL-BQCOM-027` |
| `REQ-BQCOM-028`、`CON-BQCOM-028` | Transaction后继候选的host preflight与导入来源 | `DR-BQCOM-040` | Transaction测试范围host launcher/preflight journal | 新run与有限失败证据；生产Business/Core/API不变 | `IMPL-BQCOM-037` | `TEST-BQCOM-036` | `VAL-BQCOM-035` |
| `REQ-BQCOM-029`、`CON-BQCOM-029` | Transaction候选的允许事实与禁止字面量分类 | `DR-BQCOM-041` | Transaction test-only live harness/manifest/history | 全新candidate；生产Business/Core/API/字段矩阵不变 | `IMPL-BQCOM-038` | `TEST-BQCOM-037` | `VAL-BQCOM-036` |
| `REQ-BQCOM-030`、`CON-BQCOM-030` | 两域candidate外部live bootstrap | `DR-BQCOM-042` | test-only bootstrap wrapper；域candidate保持唯一业务生命周期权威 | 新wrapper manifest/lifecycle/failure evidence；生产Business/Core/API和candidate-04字节不变 | `IMPL-BQCOM-039` | `TEST-BQCOM-038` | `VAL-BQCOM-037` |
| `REQ-BQCOM-031`、`CON-BQCOM-031` | Transaction可执行产物冻结与有限启动诊断 | `DR-BQCOM-043` | 独立test-only wrapper-v2/diagnostic；v1 helper与candidate保持只读 | 新run/manifest/auth；绑定JAR哈希和v1失败历史，不改变生产契约 | `IMPL-BQCOM-040` | `TEST-BQCOM-039` | `VAL-BQCOM-038` |
| `REQ-BQCOM-032`、`CON-BQCOM-032` | Employee可执行auth产物冻结与有限启动诊断 | `DR-BQCOM-044` | 独立test-only Employee wrapper-v2；复用公共v2 validator/diagnostic，v1与candidate只读 | 新run/manifest/auth；绑定auth JAR和v1 prepared历史，不改变生产契约 | `IMPL-BQCOM-041` | `TEST-BQCOM-040` | `VAL-BQCOM-039` |
| `REQ-BQCOM-033`、`CON-BQCOM-033` | Employee outer lifecycle/preflight顺序一致性 | `DR-BQCOM-045` | 建议新增test-only Employee wrapper-v3；复用共享executor与公共diagnostic，v1/v2/candidate只读 | 新run/manifest/auth；绑定v2失败证据，公共/生产契约不变 | `IMPL-BQCOM-042` | `TEST-BQCOM-041` | `VAL-BQCOM-040` |
| `REQ-BQCOM-034`、`CON-BQCOM-034` | 当前交付周期门禁治理与系统 E2E | `DR-BQCOM-046` | L0/L1/L2 设计与 P3 计划；无生产代码落点 | Provider + stub E2E 可执行；真实业务结果外发仍失败关闭；历史证据不变 | `IMPL-BQCOM-043` | `TEST-BQCOM-042` | `VAL-BQCOM-041` |
| `CON-BQCOM-010` | 所有权边界 | `DR-BQCOM-015`、`DR-BQCOM-016` | common module、外部提供方 | 无越权实现 | `IMPL-BQCOM-010/012` | `TEST-BQCOM-004/011` | `VAL-BQCOM-003/005` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 交互契约 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|---|
| L1_02 v0.2 | parent | 细化公共 L2 唯一范围 | 架构边界、域隔离、门禁 | 业务查询公共语义 | 上位权威 | 只读 |
| L2_00_01 v0.4 | direct dependency | 消费 handler/context/result | 核心、注册、公共不变量 | `CapabilityResult`/JWT wrapper | 执行上下文 | 只读，Approved |
| L2_00_02 v0.4 | peer/direct dependency | 提供 business safe payload/grounding policy | Provider、通用 JSON output、失败映射 | facts envelope | 模型调用状态 | 只读，Approved |
| `auth-service` | external authority | 记录消费假设/测试场景 | 用户角色分配、JWT 签发 | `role` claim | 用户/角色 | 只读 |
| `common-security` | external authority | 记录 Authority 可观察要求和差距 | role→GrantedAuthority 统一映射 | Spring Security Authentication | 角色映射 | 只读；本文不设计修改 |
| `employee-service` | external/domain authority | 不定义具体动作 | Employee 最终授权和响应可见性 | 域 L2 固化 | Employee 数据/权限 | 只读 |
| `mq-procedure-service` | external/domain authority | 不定义具体动作 | Transaction 最终授权和响应可见性 | 域 L2 固化 | Transaction 数据/权限 | 只读 |
| L2_02_01 v0.3 Approved / L2_02_02 v0.3 Approved | child designs | 提供公共原语 | 分别实例化动作、字段、端点、客户端和权限测试 | code-bound definition | 域动作/配置 | Employee GET/no-body 与 Transaction 金额请求兼容性已复核；实施/Provider/真实集成/出域门禁 Open |

### 5.1 当前 Java 触点（只读事实）

| 状态 | 路径/符号 | 已核实行为 | 本文判断 |
|---|---|---|---|
| 已存在 | `auth-service/src/main/java/com/dylan/authcenter/service/JwtService.java` `String generateToken(String userId)` | JWT 包含 `sub/iat/exp/token_type=user/role`，role 来自用户服务集合 | 可复用声明来源；不修改 |
| 已存在 | `auth-service/src/main/resources/auth-users.yml` | admin→ADMIN、dylan→ADMIN、viewer_t→VIEWER | 用户分配与确认范围一致；不是运行时 Authority 证据 |
| 已存在 | `common-security/src/main/java/com/dylan/common/security/ResourceServerSecurityAutoConfiguration.java`、`common-security/src/main/java/com/dylan/common/security/ReactiveResourceServerSecurityAutoConfiguration.java` | 默认只要求 authenticated，未配置 role converter | `SA-GATE-004/005` 差距；本文不定义提供方类改造 |
| 已存在 | `common-security/src/main/java/com/dylan/common/security/FeignTokenRelayAutoConfiguration.java` | 缺用户 JWT 时可回退 service token | 不得复用于 Agent 用户查询客户端 |
| 已存在 | `transaction-api/src/main/java/com/dylan/transaction/api/model/Transaction.java` `amount/amountGt/amountLt`；`mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/mapper/TransactionMapper.xml` | Java DTO 使用 `BigDecimal`，搜索 SQL 已支持等值、大于和小于金额条件 | 不修改 Java API；business wire 必须无损映射为 JSON number→`BigDecimal`，真实 precision/scale 仍由 Transaction 门禁验证 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java` `void requireUser(Authentication)` | 只校验 user token | 未满足角色最终授权 |
| 已存在 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java` `void requireUser(Authentication)` | 只校验 user token | 未满足角色最终授权 |

上述精确文件已在当前仓库核实；本文不据此授权 Java 变更。若后续需要修改共享安全或业务服务，域 L2 必须记录精确文件、方法、契约影响并取得单独授权。

## 6. 当前实现基线与最小变更方案

### 6.1 差距与根因

| 维度 | 当前状态 | 设计根因 | 本文处理 |
|---|---|---|---|
| Python Adapter | 不存在 | 无公共业务查询原语 | 建议新增最小 common module |
| JWT 透传 | Java 通用客户端存在 service fallback | 通用服务调用与用户查询语义不同 | Python 专用用户 JWT 客户端，缺失零调用 |
| Authority | claim 已签发、converter 未具备 | 声明权威与执行权威未闭环 | 只定义消费预期/联调矩阵，真实动作禁用 |
| 结果 | 两域语义不同 | 原始 DTO 不能成为 Agent 契约 | 公共 tagged result + 域实例 |
| 字段出域 | 未建立 | 用户可见与模型可见未分离 | 两次投影、有限转换和 facts |
| 回答事实 | 无领域 grounding | 模型引用 fact ID 仍可能补造 | 业务 grounding policy |

### 6.2 最小变更方案与方案对比

| 变更项 | 必要性 | 复用内容 | 不采用的方案及原因 |
|---|---|---|---|
| 建议新增 `agent_runtime.business` 公共原语 | 两域共同语义只实现一次 | L2_00_01 能力 API | 不建设通用动态 Adapter：会把 URL/DTO/权限配置化 |
| 两域各自代码定义 | 保持域字段/契约所有权 | 公共 generic 类型 | 不把 Employee/Transaction 放进统一动作表 |
| Python 专用 user-JWT client | 禁止 service fallback | `OpaqueUserToken` | 不复用 Java Feign interceptor；它允许服务身份兜底且不在 Python |
| 字段定义+配置交集 | 只收紧且可测试 | 业务授权响应 | 不使用脚本/表达式/JSONPath；无法审计且可扩权 |
| 六个有限转换 | 覆盖首期基本最小化 | Python 标准库/Decimal | 不引入规则引擎或通用脱敏库 |
| 业务传输专用 exact decimal | 复用现有 Java `BigDecimal` 查询且避免 float 降精度 | Python `Decimal`、既有 code-bound codec | 不修改 Core `JsonObject`；不发送 quoted decimal 依赖 Jackson 宽松 coercion；不允许域 codec 自行拼接 raw JSON bytes |
| 结构化 facts+grounding | 防业务文本控制模型/补造事实 | L2_00_02 envelope | 不让模型自行脱敏或解释原始响应 |

## 7. 职责、分层与依赖设计

### 7.1 责任分解

| 组件/类型 | 状态 | 唯一职责 | 明确不负责 | 输入/输出 |
|---|---|---|---|---|
| `BusinessActionDefinition[...]` | 建议新增 | 代码绑定动作、类型、维度、字段和契约上限 | 动态端点/角色/脚本 | 定义→冻结动作 |
| `BusinessActionSettings` | 建议新增 | 表达配置收紧值 | 新动作/字段/权限 | 配置源→有效设置 |
| `BusinessFieldDefinition` | 建议新增 | 字段 ID、类型、分类、提取器和允许转换 | 业务服务授权 | typed record→field |
| `BusinessRequestMapper` / `BusinessWireCodec` | 建议新增 Protocol | 把强类型输入与冻结设置映射为域 wire request，再编码/严格解码受控 HTTP | 动态 URL、网络、授权 | input/settings↔bounded HTTP |
| `ExactDecimal` / `BusinessWireJsonEncoder` | 建议新增 | 表达并编码业务请求中的有限精确十进制 JSON number | Core/模型 JSON、业务金额范围、任意 raw body | `Decimal`→canonical UTF-8 JSON bytes |
| `BusinessResponseNormalizer` | 建议新增 Protocol | 把一个域响应映射为 tagged result | HTTP/角色/模型 | wire response→service result |
| `BoundBusinessActionHandler` | 建议新增 | 按固定顺序组合一个 definition、settings、client 和投影器 | 动作发现、另一域语义、重试 | typed input+context→capability result |
| `BusinessUserResultProjector` | 建议新增 | 形成最小有效本地用户视图 | no_result 判定、业务授权 | authorized records→user result |
| `BusinessEgressProjector` | 建议新增 | 计算交集、转换并构造 facts | 调用模型、Prompt | user result→egress |
| `BusinessTransformRegistry` | 建议新增 | 六个代码转换 | 配置脚本/动态参数 | typed value→safe value |
| `BusinessAnswerGroundingPolicy` | 建议新增 | 校验 fact 引用和事实 token | Provider/通用 JSON parsing | payload+candidate→decision |
| `UserJwtBusinessHttpClient` | 建议新增 | 单次只读请求、JWT header、预算/响应上限 | 选择动作、服务 token、域 DTO | request spec→bounded response |
| 域 Adapter | 后续建议新增 | 组合上述原语并实现具体 handler | 另一域、Knowledge、最终授权 | typed args+context→result |

### 7.2 依赖方向

```text
agent-core
  → agent-capability-api
    ← agent-employee-adapter
       → agent_runtime.business common primitives
       → employee-service public read contract
    ← agent-transaction-adapter
       → agent_runtime.business common primitives
       → mq-procedure-service public read contract

agent_runtime.business egress
  → L2_00_01 ModelEgressResult / safe payload
  → L2_00_02 AnswerGroundingPolicy seam
```

禁止依赖、禁止绕过和反向依赖规则：

- common 模块不得导入 Employee/Transaction DTO、URL、字段或角色实现。
- 两个 Adapter 不得互相导入，不得导入业务服务内部 Mapper/Repository/ES 客户端。
- core、LangGraph、模型 Provider 不得导入域字段配置。
- Adapter 不得解析 role 后决定调用；不得绕过业务服务直接访问数据。
- 业务服务不得依赖 Agent action、safe payload 或模型结构。
- 配置不得指定 Python 类、函数、URL path、HTTP method、SQL、DSL、JSONPath 或转换参数对象。

### 7.3 内聚与耦合判断

JWT 无兜底、配置交集、结果状态、有限转换和 facts envelope 是两个域完全相同的安全/契约语义，因此集中在 common module；动作、字段、端点和授权入口只因各业务域变化，留在域 Adapter。common 只提供代码原语，不保存动作实例或运行期全局可变注册表，避免成为第三个业务域权威。

## 8. 公共类型、动作定义与配置

### 8.1 设计规则目录

| 规则编号 | 规则 | 责任主体 | 触发条件 | 输出/状态效果 |
|---|---|---|---|---|
| `DR-BQCOM-001` | 每个业务动作以冻结 `CapabilityDescriptor.capability_id/api_version` 作为唯一身份/版本权威，并由域代码绑定一个只读外部契约、强类型输入/响应/记录和字段目录；common 不动态创建动作 | 域 definition/provider | 启动 | 有限可审计动作 |
| `DR-BQCOM-002` | 设置只允许在代码 definition 的适用维度和上限内取子集/更小值；未声明维度出现配置即失败 | settings validator | 启动 | 配置不能扩权 |
| `DR-BQCOM-003` | outbound client 只接受 `OpaqueUserToken` 显式 reveal 后设置单一 Authorization header；缺失/空 token 零网络调用且无 service fallback | HTTP client、handler | 调用前 | 用户身份原样透传 |
| `DR-BQCOM-004` | Agent 只消费外部 role→Authority 可观察契约：role claim 是已验证非空集合，`ADMIN/VIEWER` 分别形成 `ROLE_ADMIN/ROLE_VIEWER`；缺失/空白/未知/错误失败关闭；用户名不是规则 | 外部安全权威、业务集成测试 | 业务入口认证 | 业务服务获得统一 Authority |
| `DR-BQCOM-005` | 业务服务是动作和成功响应数据可见性的最终授权点；Adapter 只在已授权 2xx 类型化响应上继续收紧 | 业务服务、域 Adapter | 外部调用 | 投影不替代授权 |
| `DR-BQCOM-006` | `no_result` 只能由域 definition 绑定的明确无数据语义产生；401/403/timeout/invalid response/投影后空值均不能转 no_result | response normalizer | 响应映射 | 状态真实 |
| `DR-BQCOM-007` | 每个动作以唯一的非空 `required_user_field_ids` 声明最小用户结果；已有记录却无法满足时返回 downstream_failure，禁止空 success | definition、user projector | 用户结果投影 | 最小有效结果 |
| `DR-BQCOM-008` | 用户字段=实际授权响应字段∩代码 user 字段∩配置 user 字段；模型字段再交集代码 model candidate、配置 model 字段和全局规则 | field projectors | 成功响应 | 两个不同视图 |
| `DR-BQCOM-009` | 转换固定六个枚举、代码实现、类型严格；配置只可为字段选择 definition 明示允许项，失败时该模型载荷整体拒绝 | transform registry | 字段投影 | 模型前完成转换 |
| `DR-BQCOM-010` | safe payload 使用 `schema_version=1` 和有界 facts；业务文本只作为 JSON value，fact ID/record ref 为请求内序号，不含原始控制指令 | egress projector | 出域允许 | 结构化最小载荷 |
| `DR-BQCOM-011` | 回答按固定分隔符切成句段；除两个精确非事实前缀外每段必须携带 `[fact-NNNN]`，used IDs、标记和受保护 token 均须由该段引用 facts 支持，unsupported claims 为空；任一不确定整体拒绝 | grounding policy | 模型候选返回 | 无依据回答丢弃 |
| `DR-BQCOM-012` | 外部状态先映射为有限 `BusinessServiceFailureKind`，再穷尽映射固定公共 code；原始错误 message/body/header/stack 不进入公共结果、日志或模型 | client、normalizer、handler | 失败 | 稳定 code/source |
| `DR-BQCOM-013` | 任一已启用动作配置、definition、字段/转换引用或必需依赖无效时整个 Runtime 不就绪；禁用动作不建客户端 | composition root | 启动 | 不运行半有效动作 |
| `DR-BQCOM-014` | 每个动作最多一次业务 HTTP；以核心绝对截止与动作上限的较小值包住连接、发送、流式读取和解析；受控 host、响应聚合前字节上限、取消和资源关闭失败关闭；无自动 retry/replay/换身份/换动作 | handler/client | 每请求 | 只读且有界 |
| `DR-BQCOM-015` | common 只提供原语和 Protocol，域 provider 显式实例化；模拟第三域只新增 fixture/provider，不修改 core/common/已有 Adapter | composition root | 扩展 | 无动态插件平台 |
| `DR-BQCOM-016` | 本文不定义或修改 `auth-service/common-security` 私有实现、域端点/字段/授权方法；只记录消费差距和证据 | 文档/测试边界 | 设计/联调 | 权威不越界 |
| `DR-BQCOM-017` | 业务敏感问题类别与合成场景提供给 L2_00_02，实际 allow/deny 仍由全局 `QuestionEgressGuard` 决定 | fixture、模型测试 | 动作选择前 | 不复制输入策略 |
| `DR-BQCOM-018` | 本期业务动作都必须生成可返回的最小 `BusinessUserResult`；模型字段为空、全局禁用、冲突或转换失败时返回 `success + denied` 与本地受控结果，回答模型零调用；业务 common 不生成 `model_egress_denied` | egress projector、域 definition | 出域判定 | 本地/外发分离 |
| `DR-BQCOM-019` | Core 候选/结果继续使用 L2_00_01 `JsonObject` 并禁止 `Decimal`；业务请求另用只允许 exact bool/int/string/null/`ExactDecimal` 及深度、集合数、循环和字节均有界的 `BusinessWireJsonObject`。域 validator 必须先把规范十进制字符串解析为 finite `Decimal` 并执行域范围/scale 约束；公共 encoder 不接受 float，以唯一 Unicode/number 规则生成 canonical plain JSON，且在大指数 Decimal 展开前失败关闭，绝不经 binary float 或 quoted-string coercion | 域 validator、business contracts/encoder、域 codec | 业务请求含精确十进制 | Python `Decimal`→JSON number→Java `BigDecimal`，不扩大 Core 契约且编码资源有界 |
| `DR-BQCOM-020` | 每个 `BusinessActionDefinition` 必须代码绑定一个 `LocalActionResolver`，其 `capability_id` 精确等于 descriptor ID；support factory 校验 ID/对象唯一性，配置不得选择实现或修改语法；仅 enabled definition 的 Resolver 按 capability ID 排序交给 `RuntimeCompositionRoot` | 域 definition、support factory、组合根 | 启动 | 非空业务动作拥有唯一纯本地解析接缝；错配阻止就绪 |
| `DR-BQCOM-021` | 版本化业务出域 candidate 必须在首个域 transport 调用前以 exclusive create 建立 append-only lifecycle journal；域 transport 在 `send` 入口记录且 fsync `domain_request_started`，并为成功/受控失败写唯一 terminal，使 evidence 中“Agent侧域请求调用数”与 started 事件精确相等；该计数不冒充下游服务实际接收数。候选终态只能是 `passed`、`failed_unconsumed` 或 `failed_consumed`：是否存在与当前 run/hash/auth 精确绑定的 consumed marker 是后两者唯一判据；consumed 只能在请求通过字段/禁止值校验后、首次模型 delegate outbound 前 exclusive create。初始化后的所有可控异常必须以有限 `failure_phase/reason` 枚举写 terminal 和 evidence，禁止异常文本、业务值、JWT、Prompt 或模型响应；retry/resume 恒为0。文件系统故障无法写最终 evidence 时只能保留此前已 fsync 的 journal/marker 并返回有限 `evidence_write_failed`，不得声称运行有效。历史 candidate 不原地演进，新语义由新模块、Schema、manifest 和 authorization 实例化 | 测试范围 domain candidate harness；当前由 Employee L2 实例化 | 受控 live 候选执行 | 模型前失败可归因、消费状态和 Agent侧域调用次数可证明；生产 common/Core/HTTP/业务契约零变化 |
| `DR-BQCOM-022` | 输入资格筛选是独立的测试/评估前置，不是业务动作、生产数据发现或 live candidate。若维护者未提供已确认合格标识，只允许在本地 Employee 数据源以固定 SQL 条件筛选 `POSITION`、`WORK_BASE_SI` 均非空并最多返回一条标识；筛选值只留在测试进程内存。随后以真实 Auth 签发的内存 ADMIN JWT 经现有 `employee.detail` 发起恰好一次请求，并复用既有 decode、用户投影和 `BusinessEgressProjector` 判定两个字段存在性及有限 egress reason。有限 evidence 除 schema/work-package/run/status 元数据外，只能包含 `position/workBaseSi` 两个 boolean、`qualified/employee.no_qualified_input/business.no_model_fields/business.egress_disabled/business.policy_conflict/employee.result_invalid/employee.request_failed` 有限原因、数据库选择/detail/其他端点/模型调用计数和零泄漏布尔值；不得持久化标识、JWT、字段值、原始响应或异常正文。运行环境必须移除 `LLM_API_KEY`，模型调用/outbound 恒为0；通过仅允许后续另行设计 candidate-03，不关闭 `GATE-024/SA-GATE-006/GATE-033`。首次受控运行未形成最终 evidence，故该 run 不得复用；任何后继资格候选必须在数据库筛选和 detail 前写入新 run 的耐久阶段 journal，并确保失败终态仍可精确证明 detail=0/1 | 测试范围 Employee qualification harness；生产 common 只读复用 | candidate-03 准备前资格验证 | 真实 Employee 输入满足最小 safe facts 且零模型/零泄漏可证明；业务数据、公开契约和历史 candidate 零变化 |
| `DR-BQCOM-023` | `WP-EMP-EGRESS-INPUT-QUALIFY-02-PREP` 必须以全新 run 独立于已退役 v1 资格运行：在任何数据库筛选前 exclusive create lifecycle 首记录并 `flush+fsync`，数据库筛选 started/terminal/selectedRows 与 detail started/terminal 均只能为0或1，顺序或重复非法即失败关闭。candidate-02 只使用 `read_only_database`，固定条件同时覆盖标识5～64、UTF-8最多192字节且无空白/保留/控制/双向控制字符，姓名1～128、职位/工作地1～256且无控制/双向控制字符，最多只返回 `ID_CARD_NO` 一行；最终资格仍由现有 Employee codec、normalizer、required user projection 和 `BusinessEgressProjector` 共同判定。正式结果只保存四个 codec 最小字段和两个 required user 字段存在性 boolean、有限 phase/reason、精确计数、lifecycle hash及安全布尔；`egressReason` 必须与非成功终态的 `failure.reason` 完全一致；不保存标识、JWT、业务值、原始响应或异常。终态仅 `qualified/not_qualified/failed`，所有可控失败必须保留已 fsync journal 与有限 result；retry/resume/other endpoint/model 恒为0。manifest 必须绑定退役资格 run 六项资产和 Employee candidate-01/02 八项历史哈希；非 live authorization 的 `liveExecutionAuthorized=false`，正式数据库筛选与一次 detail 须再次精确绑定 `GATE-049` | 测试范围资格 v2 journal/result/manifest/launcher；生产 common 只读复用 | 新资格 candidate-02 准备与后续一次受控资格 | 失败窗口可复核、输入覆盖 codec/user-result/egress 全链；历史/生产契约零漂移 |
| `DR-BQCOM-024` | `WP-EMP-EGRESS-INPUT-QUALIFY-DIAG-02` 只解释已固定的 `employee.no_qualified_input`，不得替代资格验证或创建新的 live 候选。必须对本地 Employee 表执行恰好一条只读聚合 SQL，并由同一结果行返回：总记录数、`idCardNo/chineseName/position/workBaseSi` 四个条件各自满足数，以及按该顺序逐项叠加的四个累积满足数；禁止选择标识、字段值或原始记录。每个计数必须是0以上整数，累积计数不得递增且不得大于对应单项/总数；若最终累积为0，`firstZeroStage` 必须精确取 `total_records/id_card_no/chinese_name/position/work_base_si` 中第一个归零阶段，否则只能为 `none`。Java测试在查询前校验candidate-02两项历史哈希，只能exclusive写入测试临时目录的有限staging evidence且`rawLogsDeleted=false`；外层执行在扫描并删除临时Maven/Surefire原始日志后，才可由strict finalizer exclusive创建正式evidence并将该字段置true，staging随后删除，禁止提前声明清理完成。正式有限 evidence 只含固定 schema/work-package/run、candidate-02 lifecycle/result哈希、上述整数、`qualified_input_available/no_qualified_input`、聚合查询/结果行=1、detail/其他端点/model/retry/resume=0及不持久化标识/字段/原始行/JWT/密钥、无outbound/零日志泄漏/原始日志已删除的布尔结论；额外键、非法枚举、计数不一致均失败关闭。若完整资格计数仍为0，诊断终止于首个归零条件，不得修改/新增数据、准备candidate-03或重跑`GATE-049` | Employee测试范围聚合诊断、strict Schema/evidence；生产 common 只读 | 资格失败根因定位 | 一次查询即可区分数据为空、标识、姓名、职位或工作地条件归零；历史/生产/业务数据零变化 |
| `DR-BQCOM-025` | `WP-EMP-EGRESS-WORK-BASE-DIAG-01` 只消费 SHA-256=`f23115069adaa0bfedcfdb01b7f0889acb079961319db3c44547549ca088c46f` 的既有聚合 evidence，并静态检查版本化仓库。诊断必须证明或否定：实体 property/getter/setter、MyBatis ResultMap、SELECT列、INSERT/UPDATE条件列是否统一映射 `workBaseSi↔WORK_BASE_SI`；写入口是否为调用方提供的通用/稀疏 Map 且无 required/default/backfill；是否存在 Employee DDL、初始化、导入或回填资产；ES 映射/重建只能标为下游读取，不得当作数据库填充来源。strict evidence 只允许固定来源路径及 SHA-256、布尔值、非负资产计数和有限枚举。由于既有聚合直接在数据库列上执行，若映射一致则排除 Java 读取映射为计数0的原因；仓库没有版本化 DDL/数据来源时，只能判定 `data_population_provenance_gap`，不得断言物理列类型、nullable/default或区分 NULL/空白/非法值分布。数据库/服务/端点/JWT/密钥/模型调用均为0；静态证据不足时停止并列出独立授权的最小元数据/整数聚合查询，不得准备candidate-03或改变任何门禁 | Employee测试范围静态诊断、strict Schema/evidence；生产 common 只读 | 聚合首零的静态来源解释 | 排除已核实映射缺陷，明确数据来源缺口和剩余不可观察项；生产/API/数据/历史零变化 |
| `DR-BQCOM-026` | `WP-EMP-EGRESS-WORK-BASE-DATA-DIAG-01` 只消费静态 evidence SHA-256=`7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8`。查询1固定限定当前database、`employee`表、`WORK_BASE_SI`列，只返回`DATA_TYPE/COLUMN_TYPE/IS_NULLABLE/CHARACTER_MAXIMUM_LENGTH/COLUMN_DEFAULT/COLLATION_NAME`且结果必须恰好1行；查询2只返回单行整数，按互斥优先级 `NULL`、非NULL且长度不在1～256、长度有效且含POSIX control、前述均未命中且含九类bidi control、其余有效值分类，五类之和必须等于`COUNT(*)`。两查询在测试范围只读事务中顺序执行且各恰好1次，无retry/resume；strict evidence只含元数据、整数、有限reason和安全计数。若总数/有效数不再匹配静态证据990/0，标记`source_snapshot_mismatch`并停止；匹配时只证明物理值状态，不推导业务原因。不得返回字段值/标识/原始行/分组，不得调用HTTP/auth/模型或修改数据/结构/生产/历史；完成也不关闭`GATE-049`或准备candidate-03 | Employee测试范围Java查询接缝、Python strict contract/launcher | 精确解释物理列与无效值分布 | 形成可复核有限evidence；任何数据修复另行授权 |
| `DR-BQCOM-027` | `WP-EMP-EGRESS-TEST-DATA-PREP-01` 的逻辑 fixture 只允许一条独立 synthetic Employee，确定性标识必须由固定前缀和版本化非敏感seed哈希生成且不能呈现真实身份证格式；逻辑最小非空字段只含 `idCardNo/chineseName/position/workBaseSi`，其余字段不得凭空赋值。创建前必须 exclusive-create+fsync lifecycle，先做标识冲突检查；创建成功后只能以同一标识与完整 fixture fingerprint 精确验证和精确删除，删除计数必须为1，随后验证不存在。任何创建后失败必须进入 cleanup；清理失败终态必须保留为 `failed_cleanup_required`，不得覆盖、更新或模糊匹配既有记录。有限 evidence 只允许 synthetic/非真实身份布尔、字段名集合、契约版本/模板哈希、create/verify/delete 0或1计数、有限阶段/原因和零既有记录修改结论，不保存标识、fingerprint或字段值。物理前置固定消费candidate-02 result SHA-256=`9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51`：58列、InnoDB、0键/FK/CHECK/trigger且四目标列均nullable longtext、无default/generated；任何hash或结构漂移须在journal前失败 | Employee测试数据准备切片；生产 common/Employee 只读 | 新资格candidate前的fixture安全准备 | non-live只实现Protocol/in-memory fake/lifecycle/evidence；真实写删仍须全新候选与门禁 |
| `DR-BQCOM-028` | `GATE-050` 元数据候选只允许在只读事务中顺序执行最多四条固定 `information_schema` 查询：全表列与引擎、键及出入向外键、CHECK、trigger。不得读取业务记录；trigger action 只在内存分类，正式证据只保存数量、规范化哈希和有限副作用分类。只有四条均终态且完整约束可冻结时才允许关闭门禁；任一查询失败必须立即停止，不得自动重试、补跑或追加查询，并以新文件固化有限 phase/reason、SQL state/vendor code、started/terminal计数、源码/原始报告哈希及零数据/外部调用结论。run `employee-fixture-metadata-diagnostic-v1-20260814-run-01` 已在第2条约束查询因 metadata collation 冲突失败：started=2、success/failure=1/1，第3/4条=0，故不可重跑且不构成物理契约证据。后继只能使用全新 run/hash/auth，并在不改变查询投影的前提下采用字符排序规则无关的 schema/table 比较 | Employee测试范围只读 metadata probe、strict success/failure Schema/evidence | fixture物理契约前置核实 | 失败可归因且不越过四查询预算；当前 `GATE-050` Open，生产/API/数据/历史零修改 |
| `DR-BQCOM-029` | candidate-02固定run `employee-fixture-metadata-diagnostic-v2-20260814-candidate-02`、authorization reference `P3_00:GATE-050`和最大四查询。四条SELECT投影、FROM范围和顺序与run-01一致；所有`information_schema`的schema/table/constraint名称关联及过滤必须使用显式`BINARY left = BINARY right`，不得使用`LOWER`、隐式collation或会扩大结果集的模式匹配。首条查询前必须`CREATE_NEW`并`fsync` lifecycle，先写run-start，再为`column_and_engine→key_and_foreign_key→check_constraints→triggers`逐阶段写started/terminal；失败阶段terminal后立即写run failed并停止，retry/resume=0。success/failure只保存完整物理元数据或有限phase/reason/SQLState/vendorCode、三项历史hash、计数和安全布尔；CHECK/trigger正文只保存SHA-256。manifest绑定v2 probe、Java test、launcher、三份Schema和直接测试，authorization保持prepared/live=false；正式数据库执行须再次精确授权 | Employee测试范围独立v2 probe、manifest/authorization及fake故障注入 | 修复run-01 collation与失败窗口而不改生产或历史 | prepared阶段数据库/服务/JWT/模型/业务调用均0；`GATE-050`保持Open |
| `DR-BQCOM-030` | candidate-02执行后，manifest、authorization、lifecycle、result及冻结commit必须字节不可变。post-consumption测试从commit `80c52e030f41111aa1394d990a0af94568487b2c`读取七项prepared asset blob并匹配manifest SHA，同时在当前工作树验证lifecycle/result SHA-256=`affbd35987e4caaa4950888eaed80cf12e695470b1703735716f2dd54d52a105`/`9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51`、10条事件、四查询终态、58列、InnoDB、0 constraint/check/trigger及全部安全零值。prepared-only“结果不存在”断言必须转换为历史commit断言，不得修改冻结证据或重跑。宿主退出码与strict result冲突时，以通过Schema/hash的append-only lifecycle/result为门禁事实，并记录状态传播缺口 | Employee metadata post-consumption测试与门禁证据 | 保持准备态授权与消费态结果同时可重放 | `GATE-050`关闭只证明metadata完整；不授权fixture数据动作或`GATE-049` |
| `DR-BQCOM-031` | fixture candidate-01固定run `employee-synthetic-fixture-v1-20260814-candidate-01`、manifest SHA-256=`e0c74e5a21d4b80c292cf20266227f7c8f1a11037d1816a6513f6de604e98b11`、authorization=`P3_00:GATE-051`及SELECT/INSERT/DELETE最大3/1/1。候选复用`DR-BQCOM-027`四字段模板但不调用生产Service/Mapper/API：Java test-only代码以参数化SQL和`BINARY`等值先冲突检查，在显式事务中提交单条INSERT，以完整四字段验证，再在独立显式事务以同一四字段DELETE并验证剩余0。lifecycle在首个数据库动作前exclusive-create+fsync，按precheck/insert/verify/consumer/cleanup_delete/cleanup_verify成对记录；Java只形成pending staging，launcher完成日志扫描与原始日志删除后追加host_validation与最终run终态。所有受控失败形成严格有限result；INSERT开始后未证明deleted=1且remaining=0只能`failed_cleanup_required`，retry/resume=0。manifest绑定fixture contract/schema和metadata manifest/auth/lifecycle/result六项历史及六项实现资产；prepared authorization必须live=false且正式数据库执行须再次精确授权`GATE-051` | Employee测试范围Python candidate、Java disabled live test、versioned launcher、lifecycle/result Schema、manifest/auth及直接测试 | 一次真实fixture create/verify/cleanup的可审计准备 | non-live仅fake/static/disabled编译；数据库写读、服务/JWT/model均0 |
| `DR-BQCOM-032` | Transaction egress candidate-01须以独立run/manifest/authorization冻结当前`question-egress-v2`、Business字段/转换/facts/grounding、Transaction definition/codec/normalizer/fields、模型answer接缝、真实授权证据与直接测试。candidate在首次Transaction请求前exclusive-create并fsync lifecycle；search started/terminal严格0/1，固定`size=1`、单个`trans_type`等值条件且无Date/aggregate/write。真实条件值仅由维护者在live时通过进程级`TRANSACTION_EGRESS_LIVE_TEST_TYPE`提供并驻留内存；manifest只绑定输入契约版本，result/evidence不得保存该值或其哈希。投影facts只允许`transaction_type/amount`，金额以`Decimal`确定性形成精确字符串fact；模型safe payload仅沿用公共契约的`coverage.truncated`布尔用于防过度陈述，不得携带transaction ID、provider coverage计数/总量或原始响应。字段与禁止值校验通过后、首次answer delegate前紧邻创建consumed marker；最多30次answer，每次started/terminal，retry/resume=0，终态仅`passed/failed_unconsumed/failed_consumed`。有限result/evidence只保存run/manifest/auth/hash、阶段/原因枚举、整数计数、布尔安全结论和聚合阈值，不保存问题、JWT、交易条件/ID/类型/金额、facts、prompt、provider coverage值或原始模型响应。prepared阶段只用synthetic result/fake transport验证1/30预算、27/30与逐次终态、零调用负向矩阵、失败关闭、历史hash和首outbound消费；真实search/DeepSeek须另行精确绑定`GATE-026` | Transaction测试范围candidate、launcher、strict Schema、manifest/auth及直接/history测试；复用生产Business/Transaction/Model接缝 | 可审计的一次真实Transaction结果外发候选，不新增生产抽象 | non-live时Transaction/DeepSeek=0；不得关闭`GATE-026/SA-GATE-006/GATE-034` |
| `DR-BQCOM-033` | Employee资格candidate-03必须使用全新run/manifest/authorization，并绑定旧资格candidate-02 manifest/auth/lifecycle/result、fixture candidate-01 manifest/auth/lifecycle/result及post-consumption frozen commit。Java测试范围在首个SQL前创建并fsync统一lifecycle；以既有确定性synthetic spec完成precheck、INSERT、fingerprint verify，随后启动生产Employee HTTP测试上下文并把标识/JWT仅以内存环境传给Python probe。probe必须复用`employee_detail_definition`、`BoundBusinessActionHandler`、`BusinessUserResultProjector`和`BusinessEgressProjector`，在transport send边界记录唯一detail started/terminal，只输出四codec字段与两required user字段存在性及egress有限结论。Java在INSERT开始后的finally中始终执行四字段`BINARY` exact DELETE和remaining verify；任一cleanup无法证明deleted=1且remaining=0时终态只能`failed_cleanup_required`。最终状态仅`qualified/not_qualified/failed/failed_cleanup_required`；有限result只保存阶段、原因、0/1计数、布尔存在性、历史hash和零泄漏结论，不保存标识、JWT、fingerprint、字段值、原始响应或日志。数据库预算3/1/1、detail最大1、其他endpoint/model/retry/resume=0。non-live只允许fake repository/transport、逐阶段故障、disabled Java编译、PowerShell AST与冻结hash；不得创建正式lifecycle/result或执行`GATE-049` | Employee candidate-03测试范围module、strict Schema、Java disabled live test、versioned launcher、manifest/auth与直接/history测试 | 以一个可回滚生命周期形成Employee输入资格证据；生产src、API、业务数据基线不变 | prepared通过只允许申请新的`GATE-049`；真实SQL/JWT/detail仍需精确授权 |
| `DR-BQCOM-034` | candidate-03因多个测试范围`@SpringBootConfiguration`候选在Spring上下文建立前失败，且未创建lifecycle/result、未执行首SQL；该事实以pre-SQL failure evidence精确哈希固定，run虽未消费数据库授权仍不得重跑。candidate-04必须使用全新run/manifest/authorization，直接绑定candidate-03 manifest/auth/failure及其既有八项历史。Java live test除继承`DR-BQCOM-033`全部数据库、detail、投影和cleanup规则外，必须显式`@SpringBootTest(classes = EmployeeServiceApplication.class, webEnvironment = RANDOM_PORT)`，不得依赖包扫描选择启动配置。版本化launcher须在启动Maven前exclusive-create+fsync host lifecycle，记录`spring_context_started/terminal`；若Maven/Spring在Java SQL lifecycle前失败，则exclusive生成`failed_unconsumed`有限结果，固定`firstSql=false`、SELECT/INSERT/DELETE/detail/model/retry/resume均0、有限异常分类和日志已扫描删除，不保存异常正文/路径/凭证。若Java SQL lifecycle已出现，则host journal不得伪造SQL结果，必须由原有finally exact cleanup及严格finalizer处理。non-live只允许fake、静态唯一启动类断言、disabled Java编译、PowerShell AST和逐阶段host故障注入，不访问数据库/服务/JWT/model，不创建live lifecycle/result；冻结后仍须以candidate-04新run/hash/auth重新精确授权`GATE-049` | Employee candidate-04测试范围module、pre-SQL strict Schema、显式启动类Java disabled test、versioned launcher、manifest/auth与direct/history tests | 消除Spring配置歧义并关闭首SQL前无证据窗口；生产src/API/数据基线不变 | candidate-03不可复用；candidate-04 prepared只允许申请新授权，不关闭`GATE-049` |
| `DR-BQCOM-035` | candidate-04唯一live运行已证明业务链、字段资格与exact cleanup，但其SQL lifecycle仅有`host_validation succeeded`，没有对应started；冻结`validate_lifecycle()`按全部非run阶段成对规则拒绝该15条记录。manifest/auth/host lifecycle/SQL lifecycle/result及其SHA-256均转为只读历史，禁止修改writer、validator或证据后追认本run。post-consumption测试必须同时固定三项证据哈希、完整15条实际序列、业务/安全零值及“冻结validator拒绝”反证。未来恢复`GATE-049`时必须另行设计全新candidate，在冻结前用与live相同的finalizer路径生成完整终态并由同一validator通过；不得以手工序列校验替代门禁权威validator | Employee candidate-04 post-consumption history test；未来candidate的versioned writer/finalizer/validator接缝（待另行授权设计） | 保留可审计的业务成功与契约失败双重事实，防止证据放宽或历史改写 | candidate-04不可复用；`GATE-049`保持Open，`GATE-024/SA-GATE-006/GATE-033`不解锁 |
| `DR-BQCOM-036` | candidate-05使用run `employee-egress-input-qualification-v5-20260816-candidate-05`、独立manifest/authorization、schemaVersion 5和既有3/1/1+detail1+model0预算。test-only `finalize_live_candidate(...) -> dict[str, Any]`必须先以同一`LifecycleJournal`追加`host_validation started`，再按host exit/log leak追加`succeeded/failed`，随后追加run终态；完成后立即调用同模块`validate_lifecycle(lifecycle_path, manifest_sha256=...)`，验证通过才构建、校验并exclusive写result。finalizer不得调用fake专用`execute_fake_candidate()`或手工拼装记录；qualified、host execution failed、log leak三条non-live直接测试都必须从pending lifecycle调用该finalizer，并证明16条成对序列、result/lifecycle SHA绑定与无result-on-validation-failure。manifest/history须直接绑定candidate-04 manifest/auth/host/lifecycle/result五项精确SHA、candidate-04 post-consumption history test及v4既有十一项历史，共17项；asset hashes覆盖v5 Python/Schema/tests/launcher/显式生产启动类Java disabled test；prepared authorization必须`liveExecutionAuthorized=false`。本切片不修改生产src/API/数据、v4历史或门禁阈值；冻结manifest SHA后，正式SQL/JWT/detail必须以新run/hash/auth和3/1/1+detail1预算再次精确授权`GATE-049` | 建议新增 `agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v5.py`及host模块、v5 strict Schema/direct/history/live-opt-in测试、versioned launcher、`EmployeeEgressInputQualificationV5LiveIntegrationTest` | 在冻结前消除fake/live finalizer分叉，并使result存在性受权威lifecycle validator前置约束 | non-live只使用fake/static/disabled；`GATE-049/024/SA-GATE-006/GATE-033`保持Open |
| `DR-BQCOM-037` | candidate-05唯一live已形成完整16条lifecycle与exact cleanup，但Python probe的staging `codec`精确输出四键，而Java v5 `Presence.load()`错误要求`codec.size()==5`，从而在业务响应成功后形成`employee_result_invalid`。candidate-05 manifest/auth/host/lifecycle/result与新增post-consumption history test必须按精确SHA保持不可变，禁止修改v5 Java或重跑。candidate-06使用schemaVersion 6、新run/manifest/auth和原3/1/1+detail1+model0预算；仅在versioned Java test loader把容器基数改为4，同时保留四个具体键存在且为boolean、requiredUser两键、outer object五键、egress/requestSucceeded boolean的全部校验。Python staging、result Schema和`_validate_presence()`继续固定同一四键集合。non-live源码契约测试必须分别断言Python exact key set、Java `codec.size()!=4`及四个`path(...).isBoolean()`，并以fake qualified路径证明四键全部true；candidate-06 history直接绑定candidate-05 manifest/auth/host/lifecycle/result/post-consumption test六项及其既有17项历史，共23项。candidate-06准备态测试不得把“live输出不存在”冻结成永久资产断言；输出不存在由launcher preflight验证，未来post-consumption以独立精确哈希测试接管。生产src/API/数据库/字段集合/角色/预算均不变 | `agent-runtime` candidate-06 test-only module/Schema/tests/launcher/manifest/auth；`EmployeeEgressInputQualificationV6LiveIntegrationTest` disabled test；candidate-05 consumed history test | 修复跨语言测试载荷基数而不改变业务契约或放宽验证 | non-live只使用fake/static/disabled；新manifest冻结后仍须单独精确授权`GATE-049` |
| `DR-BQCOM-038` | Employee egress candidate-03必须以全新run和schemaVersion 3实例化，不复用candidate-01/02或资格candidate。版本化launcher必须在Maven/Spring启动前exclusive-create并fsync唯一append-only lifecycle，Java测试范围宿主只续写`fixture_precheck→fixture_insert→fixture_verify`数据库阶段；Python在同一journal上顺序追加一次`employee_detail`及30个`model_answer` started/terminal，Java随后在finally追加`cleanup_delete→cleanup_verify`，launcher在日志扫描后追加`host_validation`和唯一run终态。Spring上下文或宿主提前失败时必须由同一journal/fallback pending形成有限`failed_unconsumed/failed_cleanup_required`，不得出现无证据窗口。完整成功语言固定为76条记录；任一阶段重复、乱序、缺terminal、超预算或未知键均被同一冻结validator拒绝。模型consumed marker只能在严格safe payload、禁止字段/字面量校验通过后且首次delegate outbound紧邻前exclusive-create；首SQL后run即不可复用，但模型前失败仍为`failed_unconsumed`，marker存在后失败为`failed_consumed`，无法证明deleted=1且remaining=0时优先`failed_cleanup_required`。结果的cleanup只能取自Java pending实际`deleted/remaining`并与journal交叉校验，不得从阶段存在性推断。结果只保存run/hash/auth、有限phase/reason、3/1/1+detail1+answer30计数、有效answer数、cleanup及安全零值，不保存标识、JWT、字段值、safe payload、Prompt或原始模型响应。manifest必须冻结candidate-06五项资格证据、metadata/fixture证据、candidate-01/02 egress历史、Employee授权证据、生产field/policy/model/grounding接缝和直接测试；prepared authorization保持live=false。non-live必须以fake repository/domain/model和逐阶段故障注入证明76条成功语言、四终态、消费顺序、exact cleanup及retry/resume=0，不读取密钥或产生outbound；正式执行仍须以新run/hash/auth、3/1/1+detail1+30次预算精确授权`GATE-024` | Employee candidate-03测试范围Python lifecycle/validator/finalizer、Java disabled宿主、versioned launcher、strict Schema、manifest/auth与直接/history测试 | 在不改变生产common/Core/API的前提下把已验证输入资格安全接入真实结果出域候选 | `GATE-052`已关闭；`GATE-024/SA-GATE-006/GATE-033`继续Open |
| `DR-BQCOM-039` | Employee candidate-03唯一live结果固定为`failed_consumed/threshold_not_met`：数据库3/1/1、detail1、model started/terminal30/30、cleanup deleted1/remaining0且全部安全计数为0，但有效answer为0，30项均`invalid_output`；manifest/auth/lifecycle/consumed/result五项SHA必须保持不可变。根因是answer v1 system instruction没有显式要求既有`BusinessAnswerGroundingPolicy`的行内`[fact-NNNN]`语法。修复必须位于独立answer v2 task，要求每个事实片段含marker且marker集合精确等于`used_fact_ids`；不得修改事实投影、`CandidateAnswer`、parser、grounding接受规则或失败映射。生产组合根切换后，Employee candidate-03和Transaction candidate-01的current-source绑定均失效，只能以冻结提交/精确哈希验证历史；两域必须各自创建全新manifest/auth候选后才可live | 已新增`answer_generator_v2.py`并切换Runtime组合根；Employee candidate-04与Transaction candidate-02均已独立冻结 | 修复模型可见契约而保持领域、安全和公共契约稳定 | `GATE-053/054/055`已关闭；`GATE-024/026/SA-GATE-006`保持Open |
| `DR-BQCOM-040` | Transaction candidate-02的冻结launcher在pytest子进程中未提供当前仓库`agent-runtime/src`导入路径，唯一执行于collection阶段以`ModuleNotFoundError(agent_runtime)`失败。manifest/auth保持原字节，post-run初始化失败证据精确记录一次database selector、launcher一次、search/model/retry/resume均0且类型/JWT/业务值未持久化；该run不得重跑。candidate-03必须使用全新run/manifest/auth并绑定candidate-01历史、candidate-02 manifest/auth/失败证据。其versioned host launcher须在读取类型、JWT、密钥及任何数据库选择前exclusive-create+fsync preflight journal；以作用域受控的Python path导入`agent_runtime`并校验模块文件位于冻结仓库`agent-runtime/src`，随后finally恢复调用进程环境。import、资产、环境或测试collection失败须形成严格有限`failed_unconsumed`结果，database selector/search/model均0；只有preflight终态通过后才允许在未来单独授权中执行一次类型SELECT。candidate-03继续保持search1+answer30、字段/Decimal/grounding、三终态、首model outbound消费、retry/resume=0及敏感值零持久化，prepared阶段仅fake/static，不读取密钥、数据库、服务或产生outbound | 已新增Transaction candidate-03 test-only host/preflight、versioned launcher、四份strict Schema、manifest/auth及direct/history/live-opt-in测试；生产common、Core、Adapter、Provider、模型task不变 | 消除测试启动无证据窗口并确保外部预算只在可执行候选后消耗 | `GATE-056` Closed仅表示candidate-03可申请新`GATE-026`授权；不关闭`SA-GATE-006/GATE-034` |
| `DR-BQCOM-041` | candidate-03唯一执行已通过host preflight并完成SELECT1/search1，但test-only live harness把`transaction_type`及`domain_result`内的`transaction_type/amount`值加入`forbidden_literals`，导致safe payload在第一次delegate前被本地检查拒绝；consumed不存在、answer started/terminal=0/0，终态`failed_unconsumed/model_call_failed`。六项候选与执行证据须按精确SHA永久保持，不得修改或重跑。candidate-04必须使用全新run/manifest/auth并继续绑定production answer v2、字段矩阵、safe payload、grounding、Decimal和host preflight。其测试安全分类分为两层：exact payload key/field ID/transform契约唯一决定允许模型字段和安全结构元数据；forbidden literal仅扫描JWT、API key及非模型业务字段的高熵字符串值。获准`transaction_type/amount`及确定性`record_ref`的实际值不得再进入forbidden literal集合；低熵整数/布尔元数据不得用子串扫描替代exact key校验。fake测试必须以live同源构造证明获准type/amount与record_ref能到达delegate，而JWT/key/`transaction_id_masked`等非模型字段值一旦进入payload均在delegate前失败。生产src、公开契约、字段集合、问题策略、validator和grounding均不修改 | 建议新增全新Transaction candidate-04 test-only module/live harness/host launcher/Schema/manifest/auth/history；只复用已冻结生产接缝和candidate-03历史 | 修复测试安全分类的自相矛盾，不扩大真实模型出域字段 | `GATE-057`关闭仅允许新candidate申请`GATE-026`；旧run与授权均不可复用 |
| `DR-BQCOM-042` | Employee与Transaction分别使用独立versioned test-only live bootstrap，但共享同一有限状态语言和校验规则。wrapper须在任何配置值读取、服务启动或candidate调用前exclusive-create并fsync lifecycle，依次记录`asset_preflight`、`config_resolution`、`auth_start/readiness/login`、可选`domain_start/readiness`、`candidate_invoke`与`cleanup`的started/terminal；Employee只启动auth并调用既有candidate-04 launcher，Employee服务与fixture仍由既有Java candidate宿主；Transaction启动auth与Transaction服务后调用既有candidate-04 launcher。wrapper manifest必须绑定自身源码/Schema/tests、candidate manifest/auth、相关历史失败证据和source commit；执行时逐项重算哈希。敏感配置、HMAC、JWT、数据库凭据、员工标识、查询类型及原始日志只能驻留内存/临时目录，不得进入lifecycle、manifest或有限evidence。wrapper只停止自己启动且PID/监听归属均核实的进程，维护者进程只可只读复用且不得停止。任一`candidate_invoke`前失败只能生成`failed_pre_candidate_unconsumed`有限evidence，inner lifecycle/consumed/result必须不存在且SQL/detail/search/model均0；进入candidate后，SQL/detail/search/model、consume与业务终态完全由inner candidate权威记录，outer只记录invoke终态和cleanup，不得复制计数或改判。non-live实现只允许fake process/HTTP/config/clock/filesystem与PowerShell AST，必须覆盖阶段顺序、首失败即停、秘密零落盘、PID清理及candidate未调用反证 | 建议新增公共test-only bootstrap helper、Employee/Transaction versioned wrapper/Schema/manifest/authorization及直接/history测试；不得进入`agent-runtime/src` | 把临时宿主步骤纳入冻结执行边界，不改变candidate、生产Runtime、Provider或公开契约 | `GATE-058/059`关闭后才可冻结wrapper；`GATE-024/026`关闭只授予精确wrapper一次执行权，成功结论仍由`GATE-033/034` |
| `DR-BQCOM-043` | Transaction wrapper-v1唯一执行已在`auth_readiness`以`process_exited`失败；outer lifecycle/result与独立history test按精确SHA不可变，candidate-04未调用且全部inner输出不存在。v1 manifest只冻结源码资产，运行时仅检查两个JAR存在，且cleanup删除原始日志后只保留宽泛失败枚举，因此既不能证明启动产物对应冻结源码，也不能区分有限的配置绑定、类加载、端口绑定或其他启动退出类别。wrapper-v2须是独立test-only实现：沿用v1公共生命周期与outer/inner权威边界，但不得修改被v1 manifest绑定的helper；manifest新增两个可执行JAR的精确SHA资产并记录确定性构建命令与源码commit，启动前与源码资产一起校验。v2在原始日志扫描和删除前只允许生成严格`process-diagnostic`证据，字段固定为run/manifest/auth绑定、service、phase、exitCodePresent布尔、有限`classification`枚举和安全计数；分类至少包括`configuration_binding`,`class_loading`,`port_binding`,`dependency_connectivity`,`application_context`,`unknown`，禁止原始日志片段、异常消息、路径、用户名、密码、JWT、key、数据库值及其哈希。分类只能增强诊断，outer lifecycle/result仍以原有`process_exited`失败语义为权威，任何无法确定情况必须为`unknown`。wrapper-v2使用新run/manifest/auth，绑定candidate-04与v1 manifest/auth/lifecycle/result/history test；candidate-04只有在v1`candidateInvoked=false`且inner输出全部不存在时可继续被引用。non-live以fake logs/process覆盖每个分类、秘密零落盘、JAR漂移、build/source不一致、首失败即停和v1历史不可变；正式服务启动、secret、SELECT/search/model须由新一次性`GATE-061`精确绑定，不得重开或复用`GATE-026` | 建议新增独立`business_egress_live_bootstrap_v2.py`或Transaction v2扩展、diagnostic Schema、v2 profile/launcher/manifest/auth及direct/history tests；v1文件只读 | 恢复执行产物可追溯性和最小可诊断性，不改变candidate、生产Business/Core/API或业务服务 | `GATE-060`只允许non-live准备；`GATE-061`才可执行一次新wrapper；完成仍由`GATE-034/SA-GATE-006[Transaction]`判定 |
| `DR-BQCOM-044` | Employee wrapper-v1尚未执行，但与Transaction失败wrapper共享同一v1 helper、同一auth启动命令和只检查`auth-service/target/auth-service-0.0.1-SNAPSHOT.jar`存在的边界；manifest未冻结该JAR，`process_exited`也无有限分类。不能以prepared测试通过或JAR当前可重建证明live身份和失败可诊断。Employee wrapper-v2须独立于v1：复用已实现的公共v2 manifest validator、JAR preflight与strict diagnostic Schema，仅冻结它实际启动的auth JAR，不虚构Employee JAR；记录确定性`mvn -f serviceCenter/pom.xml -pl :auth-service -am -DskipTests package`、源码commit与JAR SHA。新manifest绑定wrapper-v1 manifest/auth/history测试且证明其outer输出不存在，并绑定candidate-04 manifest/auth与全部inner输出不存在；旧v1 source/manifest/auth字节不变且禁止执行。v2在auth提前退出时于日志删除前只写公共六分类之一，service固定`auth-service`、phase固定当前auth阶段、exitCodePresent为布尔，任何未知为`unknown`；不得持久化原文、路径、配置或秘密。non-live覆盖JAR缺失/漂移、build/source/command漂移、六分类、unknown、日志删除、秘密零落盘、v1/candidate历史不变和外部调用0。`GATE-062`关闭后才可用新wrapper source/run/manifest/auth/JAR与candidate-04精确重绑定`GATE-024` | 建议新增Employee `live_bootstrap_v2.py`、版本化launcher、direct/preparation/history测试和新manifest/auth；复用公共v2 helper/Schema，不复制第二套诊断实现 | 在消耗Employee一次性授权前消除与Transaction相同的宿主风险；不改变生产Business/Core/API、Employee服务或candidate-04 | `GATE-062`只允许non-live准备；`GATE-024`继续控制唯一live，完成仍由`GATE-033/SA-GATE-006[Employee]`判定 |
| `DR-BQCOM-045` | wrapper-v2唯一执行证明资产本身全部匹配，但`execute_bootstrap()`在任何phase前通过`BootstrapJournal(..., "x")`创建lifecycle，Employee `_asset_preflight()`随后对包含该lifecycle的`output_paths()`执行`any(path.exists())`，使合法本次journal被稳定误判为历史输出。最小修复不得改写共享v1/v2 helper或失败历史：建议新增Employee wrapper-v3，在调用共享executor前先校验全部outer/inner输出不存在；executor的exclusive-create继续唯一拥有lifecycle防重放；进入`asset_preflight`后再次校验冻结资产，仅允许当前lifecycle存在，并拒绝outer result/diagnostic与任一inner输出。full-path fake测试必须调用真实`execute_bootstrap()`和真实`_asset_preflight`组合，证明asset phase可通过、预存lifecycle在journal创建处失败、预存result/diagnostic/inner输出在副作用前失败。新manifest必须绑定wrapper-v2 manifest/auth/lifecycle/result精确SHA、candidate-04、auth JAR/source/build及所有直接测试；旧run不得重跑。`GATE-063`关闭只允许申请全新精确`GATE-024`，不授权live | 建议新增Employee `live_bootstrap_v3.py`、candidate-03 host launcher、full-path fake/preparation/history测试与新manifest/auth；复用共享executor、公共diagnostic/Schema和candidate-04 | 修正test-only入口的生命周期顺序，不改变生产Business/Core/API、Employee服务、字段、角色、预算或模型契约 | `GATE-063`仅允许non-live代码/冻结；`GATE-024/033/SA-GATE-006[Employee]`继续控制真实执行与完成 |
| `DR-BQCOM-046` | 当前交付周期将三种状态严格分离：一次性 outbound/SQL/服务启动授权是执行许可，不能作为验收门禁；30次/27次等阈值是特定冻结实验的结果判定，不能成为通用业务查询架构的完成标准；工作包状态只表示当前计划是否仍要求交付。P3 将 `GATE-024/033/034/061/063` 记为 Not Applicable，将 Employee wrapper-v3修复和两域真实模型出域工作包转 Deferred；不得改写任何历史 run、授权消费或失败结论。历史run、manifest、hash、candidate、JAR与HEAD只作不可变审计证据，不构成当前执行入口、可复用授权或自动新增工作包/门禁的依据。`WP-SYSTEM-E2E-01` 改由已完成的 Access E2E、Knowledge真实检索、Employee真实查询和Transaction真实查询直接解锁，模型 provider 固定默认 stub，模型 outbound=0。`SA-GATE-006.EMPLOYEE/TRANSACTION` 继续 Open 且只约束未来对应域真实业务结果外发；未来恢复实验须先完成非live诊断，仅在存在新的未决决策或安全边界时创建新工作包和有界门禁，并优先复用通用受控harness，不得复用当前 N/A 门禁或历史授权 | 设计/计划治理，无生产代码、API、Schema或配置落点 | 在保留安全失败关闭与历史审计性的同时恢复当前个人研发项目的完整系统闭环，并阻止测试治理继续形成第二套架构 | `P3_00` 当前计划 DAG/状态/门禁一致性校验；两个 scoped 安全门禁保持 Open |

#### 8.1.1 live bootstrap冻结与进程约束

- 冻结采用两步式：先提交仅含wrapper/helper/Schema/launcher/direct与history测试的非Markdown源码，记为`wrapper_source_commit`；随后生成manifest/authorization，按精确SHA绑定该commit中的源码、candidate资产和历史证据。manifest不得把包含自身内容的最终commit作为自引用哈希；live授权必须同时绑定`wrapper_source_commit`、manifest SHA-256和authorization SHA-256。
- 8090、9210、8182等受控端口在启动前必须为空；若已被任何非本次wrapper创建并登记的PID占用，立即形成`failed_pre_candidate_unconsumed/port_occupied`并停止。当前两域wrapper不复用、不停止维护者进程。
- 每个启动阶段和`candidate_invoke`均有固定deadline与取消处理。超时或取消后只终止本次wrapper创建且进程树归属可证明的PID；若inner candidate已开始且无法从inner evidence证明Employee fixture已精确清理，outer只能记录`failed_cleanup_required`，不得改写inner终态或宣称零副作用。
- readiness只允许命中冻结的健康/公开探针，不得调用Employee详情、Transaction search或其他业务端点；端口监听PID必须与本次进程树一致。原始日志经敏感扫描后删除，扫描失败或日志删除失败均失败关闭。

### 8.2 代码绑定动作定义

```python
BusinessActionDefinition[
    TInput,
    TWireRequest,
    TWireResponse,
    TRecord,
]
```

| 字段 | 类型 | 必填 | 语义 |
|---|---|---:|---|
| `descriptor` | `CapabilityDescriptor` | 是 | 唯一动作身份/版本权威；`capability_id` 为 canonical ID、`api_version=1`、`kind=query`，提交核心注册 |
| `domain_id` | `BusinessDomainId` | 是 | 代码绑定 newtype，值匹配 `^[a-z][a-z0-9_]{0,31}$`；首批生产值为 `employee/transaction`，不复用 capability canonical ID 语法且不能由模型或配置创建 |
| `service_key` | `BusinessServiceKey` | 是 | provider 代码绑定且在组合根解析为一个受控 base endpoint；配置不能为动作选择 host |
| `argument_validator` | `CapabilityArgumentValidator[TInput]` | 是 | 最终 `ActionCandidate.arguments` JSON→强类型输入；不得直接消费模型输出 |
| `local_action_resolver` | `LocalActionResolver` | 是 | 用户问题→本动作 `JsonObject arguments/no_match/invalid`；ID 必须等于 descriptor；具体有限语法归域 L2 |
| `request_mapper` | `BusinessRequestMapper[TInput,TWireRequest]` | 是 | `(TInput, BusinessActionSettings)`→`TWireRequest`；必须执行分页/时间/过滤/排序收紧，不接受动态 URL |
| `wire_codec` | `BusinessWireCodec[TWireRequest,TWireResponse]` | 是 | wire request→受控 HTTP；同一次 wire request+2xx bounded body→严格 typed wire response |
| `response_normalizer` | `BusinessResponseNormalizer[...]` | 是 | wire→tagged result |
| `http_status_semantics` | `BusinessHttpStatusSemantics` | 是 | 代码冻结 204/400/404 的有限契约语义；其他状态不可配置 |
| `applicable_dimensions` | `frozenset[ConstraintDimension]` | 是 | 配置可出现的有限维度 |
| `filter_field_ids_by_code` | `frozenset[str]` | 是 | 请求过滤字段代码上限；可为空，不要求同时为结果字段 |
| `sort_field_ids_by_code` | `frozenset[str]` | 是 | 请求排序字段代码上限；可为空，不要求同时为结果字段 |
| `field_definitions` | tuple | 是 | 非空、ID 唯一、代码绑定 extractor/type/classification |
| `required_user_field_ids` | `tuple[str,...]` | 是 | 唯一 required 权威；非空、唯一，且均为 code user-visible field |
| `answer_mode` | `structured_only/model_assisted` | 是 | 代码决定，不由配置放宽 |
| `contract_limits` | `BusinessContractLimits` | 是 | 代码冻结的数值/字节上限；配置只能降低 |

配置、日志、safe payload、Resolver 和域 handler 一律以 `descriptor.capability_id/api_version` 取动作身份与版本，不得复制 `action_id/contract_version` 字段。`argument_validator` 的输入是混合节点形成的最终候选 JSON，不再是“模型参数”。`structured_only` 与
`model_assisted` 都必须先形成可直接返回用户的最小结果；后者仅允许再生成可选摘要，不得
把模型变成唯一可读结果。definition 不能包含角色白名单；允许角色由业务服务实现并按上位
确认的 `admin/viewer` 验证。

### 8.3 强类型动作设置

| 字段 | 类型 | 约束 |
|---|---|---|
| `enabled` | bool | 只启停代码存在动作 |
| `max_page_size` | int/None | 仅适用维度可设置；1～代码上限 |
| `max_result_count` | int/None | 同上 |
| `max_time_range_days` | int/None | 同上 |
| `allowed_filter_field_ids` | tuple[str]/None | 代码允许集合的子集 |
| `allowed_sort_field_ids` | tuple[str]/None | 代码允许集合的子集 |
| `user_result_field_ids` | tuple[str] | 代码 user 字段子集且保留 required invariant |
| `model_field_ids` | tuple[str] | user fields 与代码 model candidates 的子集 |
| `user_transforms` | tuple[`FieldTransformSelection`] | 字段允许枚举之一 |
| `model_transforms` | tuple[`FieldTransformSelection`] | 同上；模型前执行 |
| `timeout_ms` | int | 100～动作 `max_timeout_ms`；调用时仍取请求绝对剩余预算的较小值 |

`BusinessContractLimits` 精确包含
`max_page_size/max_result_count/max_time_range_days: int | None`、
`max_timeout_ms: int` 和 `max_request_bytes: int`。非空数值分别必须处于
1～1000、1～1000、1～3660；timeout 为 100～60000ms，request 为 1024～65536 bytes。
某数值维度只有在 `applicable_dimensions` 声明时才能非空，已声明维度必须有代码上限。
settings 对应值必须≤代码上限；filter/sort settings 分别只能是
`filter_field_ids_by_code/sort_field_ids_by_code` 的子集。

每个 `user_result_field_id` 必须恰有一个唯一 user transform selection；每个
`model_field_id` 必须恰有一个唯一 model transform selection，且该 field 同时存在于 user
集合。缺失、重复或额外 selection 均启动失败，禁止以隐式 identity 填补。配置源的精确
环境键由域 L2 随 descriptor ID 固化；common 只拥有上述字段及验证算法。禁止使用任意
mapping 透传未声明配置。

### 8.4 字段定义与分类

`BusinessFieldDefinition[TRecord, TValue]` 至少包含：

| 字段 | 语义 |
|---|---|
| `field_id` | 域代码绑定稳定 ID，不是 JSONPath |
| `value_type` | `boolean/integer/decimal/date/datetime/enum/text/identifier` |
| `data_class` | `public/business_internal/personal_identifier/employee_identifier/transaction_identifier/financial_account/financial_value/contact/credential_or_secret/free_text_sensitive/unknown` |
| `extractor` | 代码函数，从 typed record 取值；配置不能指定 |
| `user_visible_by_code` | 业务服务授权后 Agent 本地视图的代码上限 |
| `model_candidate_by_code` | 默认 false；是否可进入后续交集 |
| `allowed_user_transforms` | 有限枚举子集 |
| `allowed_model_transforms` | 有限枚举子集 |
| `enum_values` | 仅 enum 类型可有，代码冻结 |

`unknown`、`credential_or_secret` 和 `free_text_sensitive` 的模型候选必须为 false。其他分类是否允许由域 L2逐字段确认，不能由分类名称自动放行。

### 8.5 请求、响应与公共 Protocol

所有类型使用 `@dataclass(frozen=True, slots=True, kw_only=True)` 或冻结 `Protocol`
输入；tuple/只读 mapping 在构造时深复制并冻结。

业务 HTTP 请求不能直接复用 Core `JsonObject`。公共 business contract 另定义三个不可配置的
代码常量：`BUSINESS_WIRE_MAX_DEPTH=8`、`BUSINESS_WIRE_MAX_COLLECTION_ITEMS=256`、
`EXACT_DECIMAL_MAX_TOKEN_BYTES=128`；动作 `max_request_bytes` 仍是更外层的总正文上限。
具体契约如下：

- `ExactDecimal(value: Decimal)`：只接受 `type(value) is Decimal` 且必须 finite；域
  validator/mapper 在构造前负责业务 precision、scale、最小值和最大值。公共 factory 必须先
  使用 `Decimal.as_tuple()` 做纯整数长度预检：正负零直接规范为 `0`；非零系数先移除尾随零并
  调整 exponent，再计算 plain 表示所需的符号位、整数位、小数点、前置小数零和小数位；若
  预计长度超过 `EXACT_DECIMAL_MAX_TOKEN_BYTES`，在创建对应长度字符串前失败。通过后按
  digits/exponent 直接构造 token，不调用可能先展开大指数的 `format(value, "f")`，也不经过
  binary float。token 禁止指数和前导 `+`，必须匹配
  `^-?(0|[1-9][0-9]*)(\.[0-9]+)?$` 且 UTF-8≤128 bytes。
- `BusinessWireJsonScalar = None | bool | int | str | ExactDecimal`；其中 bool 不得按 int
  接受，int 必须为 exact int 且在 Java long 范围内。`BusinessWireJsonValue` 只递归包含
  该 scalar、tuple 和字符串 key 的冻结 mapping。根 object 的 container depth=1，进入每层
  tuple/mapping 加 1，最大为 8；每个 tuple 项数或 mapping 字段数最大为 256；编码时维护当前
  祖先容器 identity，循环引用立即拒绝。任何 float、`Decimal` 裸值、日期、bytes、自定义
  DTO、可变容器、超深/超项容器或循环都拒绝。
- `BusinessWireJsonEncoder.encode(body, *, max_bytes)` 是唯一 wire JSON 编码入口：所有 key/value
  string 必须不含 surrogate code point；object key 按未转义 UTF-8 bytes 排序；编码
  不做 Unicode 归一化，不转义 `/`，`"` 与 `\` 使用反斜线转义，U+0008/000C/000A/000D/0009
  分别固定为 `\b/\f/\n/\r/\t`，其余 U+0000～001F 使用小写十六进制 `\u00xx`，其他
  code point 直接写 UTF-8。`ExactDecimal` 写为未加引号的 canonical JSON number；object/array
  无空白。编码器以迭代或等价的显式深度/祖先跟踪执行，并按实际发出字节累计，达到
  `max_bytes+1` 立即以 `InvalidBusinessWireRequest` 失败，不返回部分正文。
- 编码结果为冻结 `CanonicalBusinessJsonBody(content: bytes)`；构造器不公开，只有公共 encoder
  可以创建。域 codec 不得手工拼接 JSON、把金额作为 quoted string、调用 `float()`，或把
  任意 bytes 直接塞入请求。Core 候选、公共结果、safe payload 和日志仍只接受 L2_00_01
  `JsonObject`，不得出现 `ExactDecimal`。

| 类型 | 精确字段/方法 | 不变量 |
|---|---|---|
| `BusinessHttpRequest` | `method: Literal["GET","POST"]`；`relative_path: str`；`query: tuple[tuple[str,str], ...]`；`json_body: CanonicalBusinessJsonBody \| None` | path 以单个 `/` 开头且不得含 scheme/host/fragment、`..` 或反斜线；query key 唯一且排序，name/value 各≤256 UTF-8 bytes；GET body 必须空；POST body 必须由 `BusinessWireJsonEncoder` 在 definition request 上限内生成；除 client 注入的 Authorization/Accept/Content-Type 外不接受任意 header |
| `BoundedBusinessHttpResponse` | `status_code: int`；`content_type: str \| None`；`body: bytes \| None` | status 100～599；非 2xx 和 204 的 body 恒为 `None`；其他 2xx 只接受 `application/json`（参数可忽略）；body 已在聚合前受全局上限约束 |
| `BusinessTransportFailure` | `kind: timeout/response_too_large/tls_or_connect/protocol` | 不携带 URL、异常、message、header 或 body；`CancelledError` 不转换为该类型，清理后原样传播 |
| `BusinessRequestMapper[TInput,TWireRequest]` | `def map(self, input: TInput, settings: BusinessActionSettings) -> TWireRequest` | 纯函数；验证并收紧分页/时间/过滤/排序；只抛有限 `InvalidBusinessArguments`，不得访问网络或读取配置 |
| `BusinessWireCodec[TWireRequest,TWireResponse]` | `def encode(self, request: TWireRequest) -> BusinessHttpRequest`；`def decode_success(self, *, request: TWireRequest, response: BoundedBusinessHttpResponse) -> TWireResponse` | 代码绑定 method/path；decode 显式接收当前调用栈中完成 encode 的同一冻结 request，只接受2xx，执行请求—响应回显/上限校验、严格 UTF-8、JSON unique keys、顶层类型和 unknown-field 策略；只抛有限 `InvalidBusinessWireRequest/Response`，不得把 request 保存为 codec 可变实例状态 |
| `BusinessResponseNormalizer[TWireResponse,TRecord]` | `def normalize_success(self, response: TWireResponse) -> BusinessServiceResult[TRecord]` | 纯函数；输入只来自已解码 2xx；可生成 records/no_result/invalid_response，不能解释 4xx/5xx；不得读取 HTTP client、JWT 或配置 |

`BusinessHttpStatusSemantics` 只有三个 bool：
`http_204_is_no_result`、`http_400_is_invalid_argument`、
`http_404_is_no_result`，默认均为 false，且只能由域 definition 代码固定。配置不能更改；
204 声明为 no-result 时返回该结果，未声明则为 invalid response；未声明的 400/404 与所有
409/422/429/5xx 分别按 12.1 固定矩阵映射。公共
`map_business_http_status(response, semantics)` 在 codec 前执行：除 204 外的其他 2xx
返回 `None` 表示继续解码；204、401/403/429/5xx 和声明/未声明的 400/404 穷尽返回固定
`BusinessServiceResult`，其他 1xx/3xx/4xx 返回
`downstream_failure/unavailable`。域 codec/normalizer 不得看到或覆盖非 2xx 状态。

## 9. 详细功能与核心处理流程

### 9.1 固定执行顺序

```text
1. 核心校验候选、参数，由同一注册项 validator 生成 TInput 并 claim 单动作
2. BoundBusinessActionHandler 校验 context/token/cancel/deadline
3. request_mapper 使用冻结 settings 收紧分页/时间/过滤/排序并生成 TWireRequest
4. wire_codec 通过公共 `BusinessWireJsonEncoder` 生成有界 canonical body，再生成一个 code-bound BusinessHttpRequest
5. UserJwtBusinessHttpClient 发出至多一个请求并流式产生 bounded response
6. common status mapper 对非 2xx 直接产生固定结果；只有 2xx 连同当前调用栈的同一 `TWireRequest` 进入 wire_codec 严格解码
7. response_normalizer 只把 2xx typed wire response 映射为 BusinessServiceResult
8. user projector 形成最小有效 BusinessUserResult
9. egress projector 计算模型字段交集并执行有限转换
10. handler 构造合法 CapabilityResult
```

请求侧和响应侧异常不得因共用 `InvalidBusinessWire*` 前缀而混淆：注册项 argument validator
只抛 `InvalidCapabilityArguments`，由 Core 在 handler 前映射为 `invalid_argument`；mapper 的
`InvalidBusinessArguments` 由 bound handler 映射为
`invalid_argument/business.invalid_arguments`，网络调用为 0。已验证 `TInput` 经 mapper 后，
codec/`ExactDecimal`/encoder 若抛 `InvalidBusinessWireRequest`，说明本地代码、冻结 definition
或 mapper 未满足共享请求不变量，handler 不得伪装为用户参数或下游失败，必须让普通异常越过
领域处理并由 L2_00_01 Core 映射为
`internal_failure/core.handler_exception`，网络调用为 0。只有一次 HTTP 已完成后的
`InvalidBusinessWireResponse` 才映射为
`downstream_failure/business.invalid_response`。`BusinessTransportFailure.timeout` 映射
`timeout/business.downstream_timeout`；`response_too_large` 映射
`downstream_failure/business.invalid_response`；`tls_or_connect/protocol` 映射
`downstream_failure/business.downstream_failure`。`CancelledError` 清理后原样传播。

步骤 2～7 位于同一个动作 `call_deadline` 控制域：异步 I/O 使用
`asyncio.timeout_at(call_deadline)`，每个同步有界转换前后检查取消和
`loop.time() < call_deadline`；任何超时/取消后不得继续解码、投影或接纳结果。步骤 7
之前不能构造用户/模型字段，步骤 8 不能把投影当作业务授权，步骤 9 不能回看原始 wire
response。

### 9.2 类型化业务结果

`BusinessServiceResult[TRecord]` 是有限 tagged union；失败分支只携带
`BusinessServiceFailureKind`，不得携带域自定义字符串 code、原始 HTTP body 或异常：

| kind | 必填 | 禁止 | 公共映射 |
|---|---|---|---|
| `records` | 非空 typed records、受控分页/覆盖元数据 | failure/raw response | 进入 user projection |
| `no_result` | 确认契约允许的空元数据 | records/failure | `no_result` |
| `invalid_argument` | `failure_kind=invalid_argument` | records/body/code | `invalid_argument/business.invalid_arguments` |
| `unauthenticated` | `failure_kind=unauthenticated` | records/body/code | `unauthenticated/business.downstream_unauthenticated` |
| `forbidden` | `failure_kind=forbidden` | records/body/code | `forbidden/business.downstream_forbidden` |
| `timeout` | `failure_kind=timeout` | records/body/code | `timeout/business.downstream_timeout` |
| `downstream_failure` | `failure_kind=rate_limited/invalid_response/unavailable` | records/body/code | 穷尽映射 `business.rate_limited/business.invalid_response/business.downstream_failure` |

具体 variant 为泛型 `BusinessRecordsResult`（字段
`records: tuple[TRecord,...]`、`coverage: BusinessResultCoverage`）、
`BusinessNoResult`（字段 `coverage: BusinessResultCoverage`）和
`BusinessFailureResult`（字段 `kind: BusinessServiceFailureKind`）；union 不使用可空字段模拟 variant。
`BusinessResultCoverage` 精确含 `returned_count: int`、`truncated: bool`、
`total_count: int | None`：records 的 returned count 必须等于 tuple 长度且≥1；no-result
必须为 0/false 且 total count 只能为 0/None；若 total count 非空，必须≥returned count。
不得携带 cursor、原始页对象或业务主键。

unknown JSON fields、超界 body、类型错误、缺必需 wire 字段或业务 2xx 未满足契约均为 `downstream_failure/business.invalid_response`。域 L2 可根据已确认契约选择“拒绝未知字段”或“显式忽略且不进入 typed record”；首期默认严格拒绝，放宽需域 L2 证明兼容性且仍保证未知字段零投影。

### 9.3 用户结果投影

```text
用户结果字段
  = 本次授权响应中实际存在的已声明字段
    ∩ definition.user_visible_by_code
    ∩ settings.user_result_field_ids
```

投影顺序：

1. 只迭代 definition 字段，不反射/遍历原始 DTO 全部属性。
2. 对每条 record 按 definition 顺序提取。
3. 应用配置选择且代码允许的 user transform。
4. 验证 required fields/等价 invariant。
5. 构造有界 `BusinessUserResult`，保留分页、截断和覆盖语义。

已有 record 在步骤 3/4 后无法形成最小有效结果时返回 `downstream_failure/business.minimum_user_result_not_met`；不能变为 `no_result` 或空 `success`。

`BusinessUserResult` 是冻结 typed intermediate，精确包含
`capability_id: str`、非空 `records: tuple[BusinessUserRecord,...]` 和
`coverage: BusinessResultCoverage`。每个 `BusinessUserRecord` 含请求内连续
`record_ref=record-[0-9]{4}` 及非空、按 field definition 顺序冻结的
`fields: tuple[BusinessUserField,...]`；field 只含 `field_id` 与已完成 user transform 的
`JsonScalar value`，`None` 表示缺失并被省略，不能进入结果。

`to_domain_result()` 按固定结构输出核心 `JsonObject`：

```json
{
  "schema_version": 1,
  "capability_id": "namespace.action",
  "records": [
    {
      "record_ref": "record-0001",
      "fields": {
        "code-bound-field-id": "safe-local-value"
      }
    }
  ],
  "coverage": {
    "returned_count": 1,
    "truncated": false,
    "total_count": null
  }
}
```

key 和 records/fields 顺序按上述规则固定，canonical UTF-8 JSON 必须≤冻结
`max_user_result_bytes` 且该上限在启动时≤核心
`CoreRuntimeSettings.max_domain_result_bytes`；超界返回
`downstream_failure/business.user_result_too_large`，不得把超界值交给核心后再变成
`core.invalid_result`。模型载荷只能从 typed `BusinessUserResult` 生成，不能从序列化后的
mapping 反向遍历。

### 9.4 事务与一致性边界

本流程不写数据库、消息、索引或缓存，不适用跨资源事务、补偿、CAS 或分布式锁。单请求一致性来自冻结 action definition/settings、一次 HTTP 调用、不可变 typed result 和取消/截止后拒绝迟到结果。重复用户请求是新查询，不承诺跨请求快照一致、幂等结果或自动去重。

## 10. JWT、Authority 与业务最终授权

### 10.1 用户 JWT 客户端原则

- client 方法必须显式接收 `OpaqueUserToken`，不能读取进程全局 token 或创建 service token。
- `reveal_for_outbound()` 只在 header 构造的最小作用域调用一次；值只进入 `Authorization: Bearer ...`。
- token 不进入 body、query、URL、异常、repr、指标或日志。
- 缺 token/非法 context 时在创建 HTTP request 前返回 `unauthenticated/business.missing_user_token`。
- 每个动作一次请求、无 retry；重定向关闭，防 token 转发到非代码绑定 host。
- 每个已启用域创建一个 lifespan-scoped `httpx.AsyncClient`：base endpoint 来自该
  `BusinessServiceKey` 的冻结启动配置，只允许 `http/https`、非空 host、可选固定端口，
  禁止 user-info/query/fragment；production profile 必须使用 HTTPS，loopback
  development profile 才可显式允许 HTTP。
- client 固定 `trust_env=False`、`follow_redirects=False`、`http2=False`、
  `verify=True`（HTTPS）、`Accept-Encoding: identity`，transport retries=0；不得读取
  `HTTP_PROXY/HTTPS_PROXY/SSL_CERT_FILE` 等环境隐式扩大出站或信任边界。
- `BusinessHttpRequest` 只含代码定义的 `GET/POST`、以 `/` 开头且无 scheme/host 的相对
  path、排序后的受控 query 和由公共 encoder 生成的有界 canonical JSON body；client
  以 `content=CanonicalBusinessJsonBody.content` 发送，禁止使用可能重新解释 Decimal 的
  `json=` 参数。path/method 只由域 definition/codec 提供，模型参数和配置不得覆盖。
- handler 计算
  `call_deadline=min(context.deadline_monotonic, loop.time()+settings.timeout_ms/1000)`；
  剩余≤100ms 时零连接。client 用同一个 `asyncio.timeout_at(call_deadline)` 包住连接、
  发送、2xx 流式读取、解码和 typed parsing，不得为各阶段重置相对 timeout。
- 收到 headers 后先判 status：非 2xx 不读取正文；2xx 仅按 raw bytes 流式累计，读取
  `max_response_bytes+1` 即停止并失败，不能先 `response.aread()` 后校验。所有正常、
  超时、超界、取消和异常路径均关闭 response；Runtime shutdown 的
  `CancelledError` 原样传播。
- client 由组合根创建并在 Runtime lifespan 关闭；禁用域不创建。任何 URL/host、
  token 或响应正文不得进入异常、日志或指标。

### 10.2 role→Authority 消费契约

业务查询的目标可观察语义：

| JWT role claim | 统一映射预期 | 业务服务结果 |
|---|---|---|
| `["ADMIN"]` | `ROLE_ADMIN` | Employee/Transaction 首批动作允许 |
| `["VIEWER"]` | `ROLE_VIEWER` | Employee/Transaction 首批动作允许 |
| `["ADMIN","VIEWER"]` | 两个去重 Authority | 允许，不因顺序变化 |
| 已验证 user token，但 role 缺失/null/空集合/含空白元素 | 不产生允许 Authority | HTTP 403；受保护业务方法/数据访问 0 |
| 已验证 user token，但 role 是字符串、嵌套对象或含非字符串 | 格式错误且不宽松转换 | HTTP 403；受保护业务方法/数据访问 0 |
| 已验证 user token，但含未知 role、大小写漂移或已知+未知混合 | 整个 role 集合拒绝，不保留其中已知 Authority | HTTP 403；受保护业务方法/数据访问 0 |
| token 缺失、签名/有效期失败或 `token_type!=user` | 不形成有效 user Authentication | HTTP 401；受保护业务方法/数据访问 0 |

这是一份消费和集成验收预期，不是本文对 `common-security` 私有类或 converter 实现的定义。`dylan` 通过 JWT 中的 ADMIN 获权，用户名本身不得出现在 Adapter、业务服务授权规则或配置中。

### 10.3 最终授权与响应可见性

业务服务必须在实际动作入口：

1. 重新验证 JWT 签名、有效期和 `token_type=user`。
2. 消费统一 Authority，并允许首批 `ROLE_ADMIN/ROLE_VIEWER`。
3. 按 10.2 区分 token 认证失败 401 与已验证 user token 的 role/Authority 拒绝 403；
   security filter/受保护业务方法和数据访问 spies 必须证明拒绝路径的领域调用为零。
4. 保证 2xx 响应记录、字段和数据范围符合当前用户的本域可见性契约。

Adapter 不解析 role、不维护允许角色、不补做行/字段授权。只要第 4 点没有提供方契约和测试证据，真实动作必须保持禁用，即使 Adapter 能删除字段也不能关闭门禁。

## 11. 字段交集、有限转换与模型出域

### 11.1 模型字段交集

`GlobalBusinessEgressPolicy` 是从 12.2 冻结设置构造的代码类型，精确包含：
`enabled: bool`、`policy_version: Literal["business-egress-v1"]`、
`always_denied_classes: frozenset[DataClass]`（固定含
`credential_or_secret/free_text_sensitive/unknown`）以及
`max_safe_facts/max_safe_payload_bytes/max_text_value_chars/max_fields_per_record`。
配置只能关闭出域或降低四个上限，不能删除 always-denied class、增加分类或更改版本。
其他 data class 也不会因未在 always-denied 集合中自动允许，仍须通过 definition、
settings 和字段 transform 的全部交集。

```text
模型字段
  = 本次授权响应中实际存在的已声明字段
    ∩ definition.user_visible_by_code
    ∩ settings.user_result_field_ids
    ∩ definition.model_candidate_by_code
    ∩ settings.model_field_ids
    ∩ GlobalBusinessEgressPolicy
```

任一未分类、unknown、额外、策略缺失或冲突字段被拒绝。模型字段必须是最终用户结果字段的子集；不得从原始 wire response 重新取值。

### 11.2 有限转换枚举

| transform ID | 输入 | 输出 | 精确规则 | 失败 |
|---|---|---|---|---|
| `identity_scalar` | exact bool/int | 同类型 | `type(value) is bool`，或 `type(value) is int` 且绝对值≤`2^53-1`；不接受 string/float/bool-as-int | 拒绝整个 safe payload |
| `bounded_text` | exact string | string | NFC 后 1～全局 Unicode code-point 上限；拒绝全部 C0/C1 控制符（包括换行/制表）及 Bidi override/isolate；字段必须代码标记 model text allowed | 同上 |
| `mask_keep_last4` | exact string | string | NFC、无控制/Bidi 字符、5～256 Unicode code point；输出固定 `"***"`+末 4 个 code point；字段代码还须约束原始 identifier 字符集 | 同上 |
| `date_only` | exact `date` 或 `datetime` | ISO 公历日期字符串（四位年、两位月、两位日） | `datetime` 取其原有 offset/naive 表示的 `.date()`，不转换时区、不接受 string | 同上 |
| `decimal_2` | exact `Decimal` | string | finite，`ROUND_HALF_UP` 到 2 位并固定两位小数；禁止 string、binary float、NaN/Infinity | 同上 |
| `enum_code` | string enum | string | 必须精确位于字段代码 allowlist | 同上 |

`FieldTransformSelection` 只有 `field_id: str` 和
`transform_id: BusinessFieldTransform`，同一视图内 field ID 唯一，不提供参数。
不提供 `drop`、脚本、正则替换、表达式、动态模板或任意参数；字段不出域通过集合排除完成。
转换后的值重新执行类型、长度、JSON 深度和 payload 字节校验。

### 11.3 模型安全载荷

```json
{
  "schema_version": 1,
  "policy_version": "business-egress-v1",
  "config_snapshot_id": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "facts": [
    {
      "fact_id": "fact-0001",
      "value_type": "enum",
      "value": "ACTIVE",
      "transform_id": "enum_code",
      "source": {
        "record_ref": "record-0001",
        "field_id": "code-bound-field-id"
      }
    }
  ],
  "presentation": {
    "mode": "business_facts",
    "action_id": "code-bound-action-id"
  },
  "coverage": {
    "truncated": false
  }
}
```

约束：

- `fact_id`、`record_ref` 按请求内稳定顺序生成，不由值哈希，不包含真实主键。
- facts 顺序按 record 再 field definition 顺序，最多 `max_safe_facts`。
- `source.record_ref` 是请求内序号，`source.field_id` 必须在 action definition；value 已转换。
- `policy_version` 固定为代码策略版本，`config_snapshot_id` 来自非敏感规范化配置哈希；不得由模型或动作参数覆盖。
- `presentation` 只能含有限枚举和 action ID，不含 Prompt/指令。
- 原始业务 ID 只有经域字段定义、交集和转换后才能作为普通 fact value。
- safe payload 不包含 JWT、role、subject、URL、HTTP 状态、原始响应、异常或配置正文。
- 当前请求绑定由同一调用栈、`ModelCallContext` 和请求内 fact/record 序号保证；不得为此把 request ID 或 subject 写入 safe payload。

### 11.4 业务文本隔离与事实绑定

L2_00_02 仍使用固定 system instruction 与 user JSON 分离。业务 `bounded_text` 值一律视为不可信数据，即使包含“忽略规则”“调用工具”“显示更多字段”等文本也不能改变动作、权限、Prompt 或调用链。

`BusinessAnswerGroundingPolicy` 精确实现 `L2_00_02` 的
`AnswerGroundingPolicy.validate(input: GroundingInput) -> GroundingDecision`；
只从 `input.safe_payload` 和 `input.candidate` 读取下列内容，并至少执行：

1. 先验证 payload schema/version/action，fact ID 精确匹配
   `fact-[0-9]{4}` 且按连续 `fact-0001..N` 排列；`used_fact_ids` 非空、去重并全部存在。
2. 不改写 answer；按从左到右扫描，在 `.?!。！？;；\n` 后结束一个句段，尾部非空文本
   也形成句段；每段只去除首尾 Unicode whitespace，空段忽略。
3. fact marker 只接受精确 `\[fact-[0-9]{4}\]`；全 answer marker 的去重集合必须与
   `used_fact_ids` 精确相同，且每个被引用 ID 至少出现一次。
4. 除精确等于 `查询结果：` 或 `根据可用数据：` 的句段外，每个非空句段至少含一个
   marker；marker 必须引用本 payload fact。前缀比较不做模糊、包含或大小写转换。
5. 使用同一个 `extract_protected_tokens(text)` 分别处理句段（先移除 marker span）和其引用
   facts 的 canonical display text。display text 固定为：bool 的小写 JSON
   `true/false`、int 的十进制、decimal/date/enum/identifier/text 的已转换 string。
   tokenizer 按“`***`+后续恰好 4 个 `isalnum()`/`_`/`-` code point 的掩码标识 →
   `[0-9]{4}-[0-9]{2}-[0-9]{2}` 日期 → 有符号十进制/百分数 → ASCII token
   `[A-Za-z0-9][A-Za-z0-9_.:%+-]{0,127}`”顺序扫描；每次命中先占用 span，后续规则不得
   在已占 span 内重复提取。每个句段 token 必须存在于该段引用 facts 的 token 并集。
   system instruction 要求枚举、日期、数值和标识使用 canonical 形式，不允许同义改写。
6. `unsupported_claims` 必须为空；该字段为空不能替代第 1～5 步。
7. 若 `coverage.truncated=true`，对 answer 做 NFKC+casefold 的仅校验副本，出现
   `全部/唯一/完整/没有其他/all/only/complete/no other` 任一固定短语即拒绝。
8. 任一 schema、句段、marker、token、coverage 检查异常或不确定，丢弃整个候选并由
   L2_00_02 映射 `invalid_output`；不得局部裁剪或修改后返回。

该规则能确定性验证引用与受保护 token，但仍不能证明任意自然语言逻辑等价或中文自由
文本实体未被补造。因此域 L2 应优先允许枚举、日期、数值、短标签等可验证字段，并为
允许的回答形态提供合成正/负例；`free_text_sensitive` 默认禁止外发。超出该能力边界时
返回结构化本地结果，不把此规则描述为事实正确性证明。

### 11.5 出域判定

| 条件 | `CapabilityResult` |
|---|---|
| 用户结果有效、answer mode=structured_only | `success + not_applicable`，返回本地结构化结果 |
| 用户结果有效、模型允许且 facts 非空 | `success + allowed`，safe payload 非空 |
| 用户结果有效、全局禁用/字段全拒绝/冲突/转换失败 | `success + denied`，保留本地结果，回答模型零调用 |
| 业务无数据 | `no_result + not_applicable` |

策略不确定时不得使用 `not_applicable` 伪装允许；`not_applicable` 只用于 code-bound structured-only 动作。

`BusinessEgressProjector` 直接返回核心 `ModelEgressResult`，不再定义第二套
`BusinessEgressProjection`。`success + denied` 必须使用
`ModelEgressResult(disposition=denied, policy_version=business-egress-v1,
safe_payload=None, reason_code=<有限枚举>)` 且 `failure=None`；reason code 仅允许
`egress_disabled/no_model_fields/policy_conflict/transform_failed/payload_limit`。由于所有
启用业务动作都必须先形成可返回的最小用户结果，business common 本期不得构造
`model_egress_denied`；未来若出现模型专用动作，必须先修改上位/L2 契约，不能用配置开启。

## 12. 失败、配置、安全与观测

### 12.1 错误码与调用方可见语义

| 触发 | 公共 status | failure code | source | 网络调用 |
|---|---|---|---|---:|
| arguments/配置边界非法 | `invalid_argument` | `business.invalid_arguments` | capability | 0 |
| 已验证输入后的 mapper/codec/encoder 请求不变量失败 | `internal_failure` | `core.handler_exception` | core | 0 |
| user token/context 缺失 | `unauthenticated` | `business.missing_user_token` | capability | 0 |
| 业务 HTTP 401 | `unauthenticated` | `business.downstream_unauthenticated` | downstream | 1 |
| 业务 HTTP 403 | `forbidden` | `business.downstream_forbidden` | downstream | 1 |
| 明确契约 no data | `no_result` | 无 | 无 | 1 |
| HTTP 400 且域 definition 代码声明该状态就是用户参数错误 | `invalid_argument` | `business.invalid_arguments` | downstream | 1 |
| 未知 400/409/422、429、5xx、连接错误 | `downstream_failure` | `business.downstream_failure` 或 `business.rate_limited` | downstream | 1 |
| client deadline | `timeout` | `business.downstream_timeout` | downstream | 1 |
| 2xx body/字段/类型/大小非法 | `downstream_failure` | `business.invalid_response` | downstream | 1 |
| 有 record 但最小用户结果失败 | `downstream_failure` | `business.minimum_user_result_not_met` | capability | 1 |
| 有效投影超过冻结 user-result 字节上限 | `downstream_failure` | `business.user_result_too_large` | capability | 1 |
| 模型字段拒绝/转换失败且本地结果有效 | `success` | 无 | 无 | 回答模型 0 |

原始错误正文、业务 response、header、URL query、堆栈和敏感字段不得进入 `FailureDetail` 或普通日志。HTTP 404 是否是 no_result 必须由域公开契约明确；未确认时按 downstream failure。

### 12.2 全局公共配置

| 环境变量 | 默认 | 允许范围 | 生效/失败 |
|---|---:|---|---|
| `AGENT_BUSINESS_EGRESS_ENABLED` | `false` | true/false | 重启；false 时所有模型载荷 denied |
| `AGENT_BUSINESS_MAX_SAFE_FACTS` | `20` | 1～20 | 重启；只能降低 |
| `AGENT_BUSINESS_MAX_SAFE_PAYLOAD_BYTES` | `32768` | 4096～32768 | 重启；只能降低 |
| `AGENT_BUSINESS_MAX_TEXT_VALUE_CHARS` | `256` | 32～256 | 重启；只能降低 |
| `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` | `1048576` | 65536～1048576 | 重启；只能降低 |
| `AGENT_BUSINESS_MAX_FIELDS_PER_RECORD` | `32` | 1～32 | 重启；只能降低 |
| `AGENT_BUSINESS_MAX_USER_RESULT_BYTES` | `262144` | 16384～262144，且≤核心 `max_domain_result_bytes` | 重启；只能降低；交叉约束失败则不就绪 |

`business-egress-v1` 是代码策略版本，不由环境覆盖。每动作设置由域 L2 定义精确键；全部设置与 action definitions 归一化后计算非敏感 `snapshot_id`，运行期只读。

`BusinessConfigurationSource` 是启动期冻结 DTO，只含：
`global_settings: BusinessGlobalSettings`、
`actions: tuple[RawBusinessActionSettings, ...]` 和
`service_bindings: tuple[BusinessServiceBinding, ...]`。域 provider 负责把域 L2 固定的
精确环境键解析为该 DTO；未知键、重复 action/service key、缺失启用动作设置、空字符串、
非十进制整数或宽松 bool 均启动失败，禁止把 `os.environ` 或任意 mapping 传入 validator。

`BusinessConfigurationSnapshot` 包含已验证 global settings、按
`descriptor.capability_id` ASCII 排序的 action settings、按 service key 排序且已验证的
service bindings 和完整 64 位小写 SHA-256 `snapshot_id`。哈希输入是上述数据及
descriptor ID/api version、字段/转换 ID 的 canonical JSON（UTF-8、对象 key 排序、tuple
保持已定义顺序、无空白）；允许包含无 user-info 的 canonical endpoint，但不得包含 JWT、
API key、subject、问题或运行期值。日志只记录 snapshot 前 12 位，safe payload 使用完整
snapshot ID；同一输入必须得到相同 ID，任一生效设置/definition/binding 变化必须改变 ID。

### 12.3 业务敏感问题类别

向 L2_00_02 提供以下合成负向类别；不包含真实用户数据：

| 类别 | 代表性形态 | 预期 |
|---|---|---|
| `personal_identifier` | 校验合法的合成身份证/证件号 | DeepSeek transport 0 |
| `employee_identifier` | 合成员工编号与具体姓名组合 | transport 0，除非未来建立可验证最小化规则 |
| `transaction_identifier` | 合成交易/订单/消息 ID | transport 0 |
| `financial_account` | 合成银行卡/账户号 | transport 0 |
| `contact` | 合成手机号、邮箱或详细地址 | transport 0 |
| `credential_or_secret` | 密码、JWT、API key 形态 | transport 0 |
| `free_text_sensitive` | 含未分类个人/交易自由文本 | unknown/denied，transport 0 |
| `generic_business` | “查询员工列表支持哪些条件”等无具体实体问题 | 可进入全局允许判定，但不授予业务动作权限 |

### 12.4 权限、安全与审计设计

- 入口认证、role 映射、业务最终授权、Agent 字段收紧是连续但不同的控制点，不能互相替代。
- Adapter 不持有角色白名单或用户名例外；`admin/viewer` 只出现在外部契约测试预期。
- 业务 2xx 在真实集成门禁关闭前不能被假定为已满足响应数据可见性。
- 全局 egress disabled 是默认；未知字段/分类/策略/转换失败全部拒绝。
- 禁止日志：JWT/API key、subject/用户名、原始问题、身份证/员工/交易/账户/联系方式、完整响应、safe payload、模型回答和异常正文。
- 允许审计元数据：correlation/request ID、domain/action、config/policy version、阶段、status、HTTP status 类别、记录/字段/fact 数量、egress disposition、耗时。

### 12.5 状态、并发、容量与韧性

- 所有 action definition/settings/field registry 在启动时冻结；请求内只创建 typed input/result/view/payload。
- 每动作一次 HTTP；无 retry、熔断、缓存兜底、跨域降级或 service identity 切换。
- client timeout 取动作上限和总剩余 deadline 的较小值；剩余≤100ms 不连接。
- 取消后停止读取/解析响应，迟到结果不进入 user result 或 safe payload。
- 本文保留 client/handler 装饰接缝，未来韧性设计可包装一次调用，但必须由独立 L2 固定所有者、预算和重复语义。

### 12.6 可观测性

建议指标：

| 指标 | 有界标签 |
|---|---|
| `agent_business_action_total` | domain、action、status |
| `agent_business_http_duration_seconds` | domain、action、outcome |
| `agent_business_projection_total` | domain、action、projection=`user/model`、outcome |
| `agent_business_egress_total` | domain、action、disposition |
| `agent_business_grounding_total` | domain、action、outcome |

不得以 user/subject、字段 ID、业务值、URL、error message 作为指标标签。

## 13. 组合根、实现落点与关键签名

### 13.1 组合根与启动选择

1. 由 Employee/Transaction provider 分别提供代码 action definitions，并把各自精确环境键严格解析为 `BusinessConfigurationSource`。
2. 公共 validator 对全局设置、service bindings 和全部动作执行身份、配置子集、必需字段、转换、契约版本和依赖校验，生成一个冻结 snapshot。
3. 某一启用动作或域配置无效时，整个 Runtime readiness=false；不静默保留另一域形成半有效部署。
4. 全域禁用是合法状态：不创建业务客户端、不注册业务动作，但不影响 Knowledge/core 独立验证。
5. 对 enabled definitions 校验 Resolver ID/唯一性并形成按 capability ID 排序的 `local_action_resolvers` tuple；该 tuple 与 registrations 一并交给顶层 Runtime 组合根，不进入模型组合根或配置快照外部接口。
6. 按排序 service key 为有效启用域创建 client，再为每个动作创建
   `BoundBusinessActionHandler` 并显式提交核心 registry；任一步失败时按创建逆序
   `aclose()` 已建 client，注册表不得冻结，readiness=false。
7. common module 不扫描模块、不读取 entry point、不自动发现第三方 Adapter 或 Resolver。

Runtime shutdown 先停止接纳新请求并等待/取消既有 scope，再对每个 business client
恰好 `aclose()` 一次；关闭失败只记录安全枚举，不把 Runtime 重新标为 ready。client 不在
`BusinessSupportFactory.build` 中创建，使纯配置校验、全域禁用和失败回滚都无需网络资源。

`BusinessDomainProvider` 是域 L2 必须实现的公共 Protocol：

```python
class BusinessDomainProvider(Protocol):
    def domain_id(self) -> BusinessDomainId: ...
    def definitions(
        self,
    ) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]: ...
    def configuration_fragment(self) -> BusinessConfigurationFragment: ...
```

provider 在构造时只接收本域强类型启动 settings；`configuration_fragment()` 只投影本域
已知 action settings 和唯一 service binding，不接收/返回 `os.environ` 或任意 mapping，
不创建 client、不注册能力。组合根按 `domain_id` ASCII 排序 provider；空/重复 domain、
definition 的 domain 不匹配、跨 provider 重复 descriptor/service key 或 fragment 引用
其他域均启动失败。

`BusinessSupportSnapshot` 精确包含冻结 `global_settings`、按 capability ID 排序的
`actions: tuple[BoundBusinessActionSupport,...]`（每项只有 definition+validated settings）、
按 capability ID 排序的 `local_action_resolvers: tuple[LocalActionResolver,...]`、按 service key
排序的 `service_bindings` 和 `snapshot_id`；不含 client、JWT、handler、环境对象或可变 registry。
`local_action_resolvers` 只对应 enabled actions，作为冻结字段直接交给顶层组合根，不是可调用
factory 方法。组合根仅从该 snapshot 为 enabled action 创建 client/handler/
`CapabilityRegistrationCandidate`，禁用 action 只保留校验证据而不产生 registration/Resolver。

### 13.2 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置项 | 责任 | 必要性 | 设计规则 |
|---|---|---|---|---|---|---|---|
| `IMPL-BQCOM-001` | 建议新增 | Python contracts | `agent-runtime/src/agent_runtime/business/contracts.py` | action/field/settings/service result/user result/fact 类型和 Protocol | 公共稳定语义 | 防两域漂移 | `DR-BQCOM-001/005/006/007/010/012/015` |
| `IMPL-BQCOM-002` | 建议新增 | Python config | `agent-runtime/src/agent_runtime/business/settings.py` | global settings、action settings validator、snapshot | 配置只收紧 | 防动态/半有效配置 | `DR-BQCOM-002/013` |
| `IMPL-BQCOM-003` | 建议新增 | Python HTTP/JWT | `agent-runtime/src/agent_runtime/business/http_client.py` | `UserJwtBusinessHttpClient`、bounded response | JWT 单次只读调用 | 禁 service fallback | `DR-BQCOM-003/005/012/014` |
| `IMPL-BQCOM-004` | 建议新增 | Python result | `agent-runtime/src/agent_runtime/business/result_mapping.py` | tagged result 校验/公共失败映射 | 状态真实性 | 区分 no_result/失败 | `DR-BQCOM-006/007/012` |
| `IMPL-BQCOM-005` | 建议新增 | Python projection | `agent-runtime/src/agent_runtime/business/user_projection.py` | `BusinessUserResultProjector` | 用户字段交集/最小结果 | 防空 success | `DR-BQCOM-005/007/008` |
| `IMPL-BQCOM-006` | 建议新增 | Python transform | `agent-runtime/src/agent_runtime/business/transforms.py` | enum、`BusinessTransformRegistry` | 六个有限转换 | 模型前最小化 | `DR-BQCOM-009` |
| `IMPL-BQCOM-007` | 建议新增 | Python egress | `agent-runtime/src/agent_runtime/business/egress.py` | `BusinessEgressProjector` | 模型交集/facts/决定 | 默认拒绝 | `DR-BQCOM-008/009/010/018` |
| `IMPL-BQCOM-008` | 建议新增 | Python grounding | `agent-runtime/src/agent_runtime/business/grounding.py` | `BusinessAnswerGroundingPolicy` | 事实/coverage 验证 | 防无依据回答 | `DR-BQCOM-010/011` |
| `IMPL-BQCOM-009` | 建议新增 | Python validation | `agent-runtime/src/agent_runtime/business/validation.py` | definition/settings/result validators、finite errors | 启动/运行失败关闭 | 集中无业务语义不变量 | `DR-BQCOM-002/006/007/012/013` |
| `IMPL-BQCOM-010` | 建议新增 | Python provider support | `agent-runtime/src/agent_runtime/business/provider.py` | `BusinessDomainProvider`、`BusinessSupportSnapshot`、`BusinessSupportFactory` | 聚合域 definition/config 并提供冻结原语 | 不扫描、不创建 client、不自动注册动作 | `DR-BQCOM-013/015/016` |
| `IMPL-BQCOM-011` | 建议新增 | Python composition | `agent-runtime/src/agent_runtime/bootstrap.py` | 显式接收 Employee/Transaction providers | 组合根接入 | 可扩展不侵入 core | `DR-BQCOM-013/015` |
| `IMPL-BQCOM-012` | 建议新增 | Contract fixture | `agent-runtime/tests/contract/business/authority_expectations.json` | role/Authority/allow-deny 场景 | 外部安全消费证据 | 不定义 Java 实现 | `DR-BQCOM-004/016` |
| `IMPL-BQCOM-013` | 已存在（非 live 安全契约已验证） | Security fixture/test | `agent-runtime/tests/fixtures/business_sensitive_questions.json`、`agent-runtime/tests/contract/business/test_sensitive_question_scenarios.py` | 合成敏感问题类别与严格消费 | 给 L2_00_02 selector/answer 负向测试 | 防遗漏问题出域；不复制全局策略 | `DR-BQCOM-017` |
| `IMPL-BQCOM-014` | 建议新增 | Python handler | `agent-runtime/src/agent_runtime/business/handler.py` | `BoundBusinessActionHandler` | 固定 mapper→codec→client→normalizer→projection 顺序和绝对截止 | 防两个域复制/漂移调用语义 | `DR-BQCOM-003/005/006/007/012/014/015/018` |
| `IMPL-BQCOM-015` | 建议新增 | Python wire JSON | `agent-runtime/src/agent_runtime/business/wire_json.py` | `ExactDecimal`、`BusinessWireJsonValue`、`CanonicalBusinessJsonBody`、`BusinessWireJsonEncoder` | 精确十进制 canonical JSON number、唯一字符串转义、深度/集合/循环与请求字节上限 | 隔离 Core JSON，禁止大指数展开、float/quoted coercion/域内 raw JSON 拼接 | `DR-BQCOM-019` |
| `IMPL-BQCOM-016` | 建议修改 | Python contracts/validation | `agent-runtime/src/agent_runtime/business/contracts.py`、`validation.py` | `BusinessActionDefinition.local_action_resolver`、ID/对象唯一性校验 | 绑定域 Resolver，不实现域语法 | 防配置/模型替换解析权威 | `DR-BQCOM-020` |
| `IMPL-BQCOM-017` | 建议修改 | Python support/composition | `agent-runtime/src/agent_runtime/business/provider.py`、`agent-runtime/src/agent_runtime/bootstrap.py` | enabled Resolver tuple 投影并传入 `RuntimeCompositionRoot.build` | 显式装配 | 保持 disabled 零资源和无动态发现 | `DR-BQCOM-013/015/020` |
| `IMPL-BQCOM-018` | 建议新增（测试范围，由 Employee L2 实例化） | Versioned live candidate lifecycle | `L2_02_01 IMPL-EMP-016～018` 定义的 candidate-02 独立模块、Schema、launcher 与测试 | pre-model journal、domain request started/terminal、consumed 前后终态、有限 evidence builder/validator | 修复 candidate-01 观测缺口且不形成第二套生产出域流程 | 保持 candidate-01 与生产 `src` 不变；未来域复用须由其 L2 单独实例化 | `DR-BQCOM-021` |
| `IMPL-BQCOM-019` | 建议新增（测试范围，由 Employee L2 实例化） | Employee input qualification | `L2_02_01 IMPL-EMP-019～021` 定义的 strict evidence、Python qualification probe、Java opt-in test 与 launcher | 只读选择、一次 detail、字段存在性/egress reason 与计数 | 在创建下一 live candidate 前验证输入质量 | 不修改生产 common；不读取模型密钥或产生 outbound | `DR-BQCOM-022` |
| `IMPL-BQCOM-020` | 已新增（测试范围，由 Employee L2 实例化） | Employee input qualification candidate-02 | `L2_02_01 IMPL-EMP-022～024` 定义的 v2 lifecycle/result Schema、Python journal/result/manifest validator、Java codec-complete筛选接缝、版本化 launcher/manifest/authorization | 数据库筛选/detail前耐久记录、精确0/1、有限终态、14项历史绑定 | 修复 `CR-BQCOM-QUAL-001` 的非 live 前置且不执行真实资格 | 不修改生产 common；不启动服务/数据库/JWT/detail，不读取模型密钥或产生 outbound | `DR-BQCOM-023` |
| `IMPL-BQCOM-021` | 已新增并验证（测试范围，由 Employee L2 实例化） | Employee input qualification aggregate diagnostic | `L2_02_01 IMPL-EMP-025/026` 定义的 strict final/staging validator、Schema、单查询 Java test 与有限 evidence | 一条聚合 SQL、九个整数计数、有限首个归零条件、candidate-02 两项历史哈希；日志删除后才从staging生成正式evidence | 定位 `employee.no_qualified_input` 的首个归零条件 | 不修改生产 common/数据；不读取标识、JWT、模型密钥，不调用Employee端点或模型 | `DR-BQCOM-024` |
| `IMPL-BQCOM-022` | 已新增并验证（测试范围，由 Employee L2 实例化） | Employee work-base static provenance diagnostic | `L2_02_01 IMPL-EMP-027` 定义的 static diagnostic、strict Schema/evidence与直接测试 | 聚合evidence和9项源码hash、映射/写入布尔、版本化Employee数据来源计数、有限未知项与全零外部调用 | 排除读取映射并定位数据填充来源缺口 | 不修改生产common/Employee/数据/历史，不执行数据库、端点或模型 | `DR-BQCOM-025` |
| `IMPL-BQCOM-023` | 建议新增并已完成非live前置 | Employee work-base data diagnostic | `L2_02_01 IMPL-EMP-028`定义的Java两查询测试、Python strict contract/Schema、launcher与直接测试 | 六项列元数据、五类互斥计数、精确2查询、静态evidence哈希和安全反证 | 查询执行后形成有限物理数据诊断 | 不修改生产common/Employee/数据/结构/历史 | `DR-BQCOM-026` |
| `IMPL-BQCOM-024` | 已实现并通过non-live验证 | Employee synthetic fixture test preparation | `L2_02_01 IMPL-EMP-029`定义test-only fixture contract、repository Protocol/in-memory fake、lifecycle/Schema/evidence与故障注入 | 单记录、确定性synthetic标识、精确创建/验证/清理、异常恢复 | 只消费已关闭`GATE-050`证据 | 不访问数据库/服务/JWT/模型；真实repository和fixture仍不存在 | `DR-BQCOM-027` |
| `IMPL-BQCOM-025` | 已新增；run-01失败关闭 | Employee fixture metadata gate probe | `L2_02_01 IMPL-EMP-030` 定义的 Python strict finalizer、success/failure Schema/evidence、PowerShell launcher及 Java `information_schema` 只读测试 | 四查询预算、触发器正文内存分类、有限失败归档、源evidence与实现hash绑定 | 关闭 fixture 实施前的物理元数据缺口 | 不读取业务行、不写数据库、不调用HTTP/auth/model；run-01不可重跑 | `DR-BQCOM-028` |
| `IMPL-BQCOM-026` | 已新增并完成非live冻结 | Employee fixture metadata candidate-02 | `L2_02_01 IMPL-EMP-031～033`定义的v2 lifecycle/result/manifest validator、三份Schema、Java test-only probe、versioned launcher、manifest/authorization及direct/history tests | binary名称比较、查询前耐久journal、四阶段精确计数、有限终态、三项历史hash与七项实现asset冻结 | 为新的`GATE-050`一次性执行准备可审计候选 | prepared阶段不访问数据库/服务/凭证/模型，不创建fixture或live结果 | `DR-BQCOM-029` |
| `IMPL-BQCOM-027` | 已修改并验证（测试范围） | Employee metadata candidate-02 post-consumption闭环 | `L2_02_01 IMPL-EMP-034`定义的prepared blob校验、当前lifecycle/result严格校验及历史测试 | 冻结commit/manifest/evidence双快照；不修改四查询、Schema或append-only资产 | 持续回归同时证明准备态授权与消费态结果 | 禁止重跑、补跑、续跑或修改冻结证据 | `DR-BQCOM-030` |
| `IMPL-BQCOM-028` | 已完成non-live冻结、一次性live执行与post-consumption闭环 | Employee synthetic fixture candidate-01 | `L2_02_01 IMPL-EMP-035～037`定义的Python candidate/Schema、Java test-only显式事务、versioned launcher、manifest/auth及直接/history测试 | 3/1/1数据库预算、exact fingerprint、host validation、三终态与历史hash | `GATE-051`通过后保留不可变历史，不提供重跑权利 | Employee API/JWT/model=0；inserted/verified/deleted=1、remaining=0 | `DR-BQCOM-031` |
| `IMPL-BQCOM-029` | 建议新增 | Transaction egress candidate-01测试切片 | `agent-runtime/tests/integration/adapters/transaction/egress_candidate.py`、candidate/live opt-in/history测试、versioned launcher、strict lifecycle/result Schema、manifest/auth | 1次search/30次answer、字段交集、精确decimal fact、首outbound消费、三终态与历史hash | 为`GATE-026`一次性live准备 | prepared阶段只允许synthetic/fake，真实业务/model=0 | `DR-BQCOM-032` |
| `IMPL-BQCOM-030` | 已实现并冻结（测试范围） | Employee资格candidate-03测试切片 | `agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v3.py`、candidate/live/history测试、两份strict Schema、versioned launcher、manifest/auth及`EmployeeEgressInputQualificationV3LiveIntegrationTest` | 单一lifecycle、3/1/1、一次detail、四终态、finally exact cleanup、跨进程连续sequence与历史hash | 为`GATE-049`一次性live准备 | prepared阶段仅执行fake/disabled；数据库/服务/JWT/model=0，manifest=`495063a328af6a233f5600bd4efff31fdae5ab4e28aad8287bfce194051680dd` | `DR-BQCOM-033` |
| `IMPL-BQCOM-031` | 已实现并冻结 | Employee资格candidate-04测试切片 | 独立v4 candidate/Schema/tests、显式`EmployeeServiceApplication` Java disabled test、pre-SQL host journal/failure finalizer、versioned launcher、manifest/auth/history | 继承3/1/1+detail1+cleanup规则；新增Spring唯一绑定与启动前失败有限化 | 为新的`GATE-049`一次性live准备 | non-live阶段数据库/服务/JWT/model=0；candidate-03历史不可变；manifest SHA-256=`7dcae58a2a503a97fe89de0d01e63cb0450ccb0dd5945e4da5947d2df0875bb9` | `DR-BQCOM-034` |
| `IMPL-BQCOM-032` | 已完成历史固定；后继实现待另行设计授权 | Employee资格candidate-04 post-consumption闭环 | `agent-runtime/tests/integration/adapters/employee/test_employee_egress_input_qualification_v4_history.py`与三项append-only证据；未来candidate路径待确认 | 固定prepared frozen HEAD、三项证据SHA、15条序列、qualified/cleanup事实与validator拒绝反证 | 防止candidate-04被误作门禁通过；为全新candidate设计提供唯一缺口 | 不修改冻结v4 writer/validator/manifest/auth/evidence，不重跑SQL/JWT/detail | `DR-BQCOM-035` |
| `IMPL-BQCOM-033` | 已新增（测试范围，non-live冻结） | Employee资格candidate-05一致性准备 | `agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v5.py`、`egress_input_qualification_v5_host.py`、v5 Schema/direct/history/live-opt-in测试、versioned launcher及Employee Java disabled live test | live同路finalizer成对写host_validation并在result前调用同一validator；17项history与12项asset hash已冻结 | candidate-05 prepared资产可重放，且candidate-04历史字节不变 | prepared阶段未访问数据库/服务/JWT/detail/model，未创建正式live lifecycle/result | `DR-BQCOM-036` |
| `IMPL-BQCOM-034` | 已完成（测试范围，live证据闭环） | Employee资格candidate-05归档与candidate-06基数修复及真实资格 | candidate-05 post-consumption history test；candidate-06 Python/host、四Schema、direct/host/history/live-opt-in、launcher、manifest/auth、Employee Java live test及独立consumed-history测试 | 固定candidate-05失败历史；Java v6 `codec.size()==4`并保留逐键boolean；23项history/12项asset及五项candidate-06准备/结果SHA冻结 | candidate-06唯一run可由同一validator重放，v5历史字节与生产/API/数据不变 | manifest/host/lifecycle/result SHA-256=`44f25232b445e0f1c8184b31ccf2dff4d5751a796b4f3ec327fb1ea2cbb702b2`/`9c4f7d9981bef665bd06068a96155433bfbe838ebad65d4ac5dc4424106c28d5`/`ec87bcb430fc90b3e9511871625bba60c07f7d4cc7e12842f3e18255624f6677`/`750f2e0d13866203116884e1950734bcb2b06100343f142cb5e96c63fe55a9cd`；外部模型调用0 | `DR-BQCOM-037` |
| `IMPL-BQCOM-035` | 已完成并冻结（仅测试范围，默认disabled） | Employee egress candidate-03统一生命周期与冻结准备 | `agent-runtime/tests/integration/adapters/employee/egress_candidate_v3.py`、direct/preparation/history/live-opt-in测试、五份strict Schema、versioned launcher、manifest/auth；`EmployeeEgressCandidateV3LiveIntegrationTest` | lifecycle/consumed/pending/finalizer使用同一validator；launcher先建journal，Java只负责fixture/cleanup并以pending报告实际计数，Python只负责生产detail/egress/model接缝；安全拒绝计数仅允许进入失败证据 | run=`employee-egress-v3-20260817-candidate-03`、manifest SHA-256=`901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e`、17项history/28项asset；prepared阶段外部调用0 | `GATE-052` Closed；正式live另受`GATE-024` | `DR-BQCOM-038` |
| `IMPL-BQCOM-036` | 已完成（生产模型task与两域新候选；Business public code不变） | Business Answer v2兼容接缝 | `agent-runtime/src/agent_runtime/model/deepseek/answer_generator_v2.py`、`agent-runtime/src/agent_runtime/bootstrap.py`、Business/model contract/history tests及Employee candidate-04、Transaction candidate-02 test-only资产 | v2 task复用v1 DTO/parser；fake候选带marker通过既有grounding，无marker候选保持拒绝；生产只装配v2 | v1与全部旧candidate历史SHA不变，两域新候选均使用全新run/auth | 真实业务/模型调用0 | `DR-BQCOM-039` |
| `IMPL-BQCOM-037` | 已完成并冻结（仅Transaction测试范围） | candidate-03 host preflight与初始化失败闭环 | 全新candidate-03 host/preflight module、versioned launcher、四份strict Schema、manifest/auth及direct/history/live-opt-in tests | 在任何数据库选择前耐久记录，校验8项history、33项asset、冻结仓库`agent_runtime`来源及live测试collection；launcher作用域设置并finally恢复环境 | 不修改candidate-02或生产src/公共契约 | frozen HEAD=`0e6b748b8263fc5f0c35729099e41313bdddc247`；run=`transaction-egress-v3-20260817-candidate-03`、manifest SHA-256=`9c1fb119f98fa9f1dc9bbd6904955d222c26fb39c837c179d3a85c1d883e6460`、authorization SHA-256=`ca8983463fc051cf87bc563658bbe80cd583453de4547cd4c81df6524522970c`；prepared外部调用0 | `DR-BQCOM-040`；`GATE-056` Closed |
| `IMPL-BQCOM-038` | 已完成（仅Transaction测试范围） | candidate-04安全分类与历史闭环 | 独立candidate-04 module/live harness/host launcher、strict Schema、manifest/auth及direct/history/preparation测试 | 从live同源domain result提取非模型字段高熵值；JWT/key恒禁止；type/amount只受exact模型载荷契约控制；绑定candidate-03六项历史 | candidate-03与生产src/公共契约零修改 | run=`transaction-egress-v4-20260817-candidate-04`，manifest/authorization SHA-256=`ca440b8f3cf664cfe77b803c6a7786816935d391bc56e50a522f6cb76f0535d3`/`885ddb8854b34ccebf29d481e78fb84b1b6a550adf5330bf321eea5085690359`，15项history/33项asset | `DR-BQCOM-041`；`GATE-057` Closed |
| `IMPL-BQCOM-039` | 已完成并冻结（仅测试范围） | 两域versioned live bootstrap公共原语 | `agent-runtime/tests/integration/adapters/business_egress_live_bootstrap.py`、两份strict Schema、两域profile/launcher/manifest/auth/direct/history测试 | 显式domain profile装配有限阶段；配置/secret不序列化；PID/readiness与进程树清理失败关闭；outer只记录candidate invoke，不复制inner预算 | 未修改`agent-runtime/src`、candidate-04或Java生产代码 | source commit=`038b6a0f54f5f8ace9a68e49073e5035279473da`；两域manifest/auth哈希见`VAL-BQCOM-037` | `DR-BQCOM-042`；`GATE-058/059` Closed |
| `IMPL-BQCOM-040` | 已实现（仅Transaction测试范围） | wrapper-v2可执行产物冻结与有限进程诊断 | `business_egress_live_bootstrap_v2.py`、严格diagnostic Schema、Transaction `live_bootstrap_v2.py`、版本化launcher、direct/preparation/history测试及manifest/auth；两个JAR只作为本地冻结运行资产，不进入Git | 复用v1状态机而不修改v1文件；preflight校验JAR SHA；cleanup前内存分类并exclusive写有限diagnostic，再执行既有秘密扫描和原日志删除 | candidate-04与v1历史只读；生产src/Java/API不变 | source commit=`779c03c084655b2b2caa535c05911f303194f5e8`；run=`transaction-egress-live-bootstrap-v2-20260818-candidate-02`；manifest/auth SHA-256=`a244abd6da21ce4bc04c65480208989714380dfbc7a28e61261bb97797fefd0d`/`46f0a6e78b341e6d106d75e4bd72560fd508036844e3fef2085fccdae9d275be`；正式输出不存在 | `DR-BQCOM-043`；`GATE-060` Closed |
| `IMPL-BQCOM-041` | 已完成并冻结（仅Employee测试范围） | Employee wrapper-v2 auth JAR冻结与有限诊断 | 新增Employee `live_bootstrap_v2.py`、launcher、direct/preparation/history测试、manifest/auth；复用公共v2 ProcessDiagnostic/Schema与v1执行状态机，域内校验精确限定唯一auth JAR，公共v2源码保持字节不变 | v1 wrapper只读；preflight校验auth JAR/source/build/command；cleanup前有限分类并写diagnostic，随后秘密扫描和原日志删除 | candidate-04、v1 prepared历史与Transaction wrapper-v2只读；生产src/Java/API不变 | source commit=`37b51608b851d463a1b1f6e5a782589efba9c49d`；prepared HEAD=`4dff45bfe0fdb3be2787b4c2231e8859299d6570`；run=`employee-egress-live-bootstrap-v2-20260818-candidate-02`；manifest/auth SHA-256=`899eb378df014085c6e419a1720be96994698457b1f248215e8df2374118b383`/`0f9d71d0636f956aa12c4928a91137e53a211a74718a66a30b8f29fd8eb63000`；auth JAR SHA-256=`da59695336c6f2fd11581760b41f0958114ac1f9e728ad834ff1a25a7595a96b` | `DR-BQCOM-044`；`GATE-062` Closed，`GATE-024`仍Open |
| `IMPL-BQCOM-042` | 建议新增（仅Employee测试范围） | Employee wrapper-v3生命周期/preflight一致性 | 新增独立v3 module/launcher/tests/manifest/auth；共享executor、公共diagnostic/Schema、wrapper-v1/v2、Transaction与candidate-04保持字节不变 | run入口先做全输出缺失检查；journal仍由共享executor exclusive-create；phase preflight只允许当前lifecycle存在并复核资产/其他输出 | 绑定wrapper-v2失败证据SHA及既有candidate/auth JAR provenance；生产src/Java/API不变 | 未授权实施；完成后须冻结全新source/run/manifest/auth并证明外部调用0 | `DR-BQCOM-045`；`GATE-063` Open |
| `IMPL-BQCOM-043` | 已完成（仅文档与计划治理） | 当前交付周期门禁分层与系统 E2E 解耦 | L0/L1/L2 与 `P3_00`；无生产代码、运行配置或测试资产修改 | 入口执行许可、实验验收和工作包状态分离；`WP-SYSTEM-E2E-01`改由三个真实 Provider 工作包直接解锁并使用默认 stub 模型 | 历史 run/manifest/authorization/evidence 字节不变；真实业务结果模型出域继续失败关闭 | P3 五项历史/可选门禁为 Not Applicable，三个实验包为 Deferred，系统 E2E 为 Ready | `DR-BQCOM-046` |

### 13.3 Python 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| 建议新增：`business.settings.BusinessSettingsValidator.validate` | `def validate(self, definitions: Sequence[BusinessActionDefinition[Any,Any,Any,Any]], raw: BusinessConfigurationSource, *, core_max_domain_result_bytes: int) -> BusinessConfigurationSnapshot` | descriptor/domain/service ID、维度/子集/上限/required fields/transform/binding/依赖、user≤core bytes 及 canonical snapshot | 冻结 snapshot；配置错误只含稳定 code | 无 I/O；composition root |
| 建议新增：`business.contracts.BusinessRequestMapper.map` | `def map(self, input: TInput, settings: BusinessActionSettings) -> TWireRequest` | input 已由本 definition validator 产生；settings 属于同一 snapshot/action；执行域约束收紧 | typed wire request；有限 `InvalidBusinessArguments` | 纯函数；bound handler |
| 建议新增：`business.wire_json.ExactDecimal.from_decimal` | `@classmethod def from_decimal(cls, value: Decimal) -> Self` | 只接受 exact finite Decimal；域 precision/scale/range 已先校验；以 `as_tuple()` 在任何大字符串分配前计算并限制 plain token≤128 bytes，零规范为 `0` | 冻结 exact decimal 和仅供 encoder 使用的 canonical token；非法值抛不携带原值的 `InvalidBusinessWireRequest` | 纯函数；域 wire codec；请求不变量失败由 Core 映射 internal failure |
| 建议新增：`business.wire_json.BusinessWireJsonEncoder.encode` | `def encode(self, body: BusinessWireJsonObject, *, max_bytes: int) -> CanonicalBusinessJsonBody` | 只接受 business wire 白名单；root depth=1且≤8、每容器≤256、拒绝循环及 key/value surrogate；key 按未转义 UTF-8 排序并执行 8.5 唯一转义；ExactDecimal 写未加引号 plain number；max bytes 1024～65536 | 冻结 canonical bytes；类型/深度/集合/循环/Unicode/大小非法抛 `InvalidBusinessWireRequest`，不返回部分正文 | 纯函数；所有 POST 域 codec；client 只消费结果 bytes；请求不变量失败由 Core 映射 internal failure |
| 建议新增：`business.contracts.BusinessWireCodec.encode/decode_success` | `def encode(self, request: TWireRequest) -> BusinessHttpRequest`；`def decode_success(self, *, request: TWireRequest, response: BoundedBusinessHttpResponse) -> TWireResponse` | 8.5 的 path/method/query/body；decode 只接受2xx并校验当前冻结 request 对应的回显/结果边界、content-type/strict JSON | typed request/response；有限 wire error | 纯函数；bound handler按同一调用栈传参，不共享请求期状态 |
| 建议新增：`business.result_mapping.map_business_http_status` | `def map_business_http_status(response: BoundedBusinessHttpResponse, semantics: BusinessHttpStatusSemantics) -> BusinessServiceResult[Never] | None` | 穷尽 1xx～5xx；semantics 来自 definition | 2xx 为 None；非2xx为固定 tagged result | 纯函数；codec 前唯一状态解释点 |
| 建议新增：`business.contracts.BusinessResponseNormalizer.normalize_success` | `def normalize_success(self, response: TWireResponse) -> BusinessServiceResult[TRecord]` | 同一动作已解码 2xx wire response | records/no_result/invalid_response；不携带自定义 code/body | 纯函数；bound handler |
| 建议新增：`business.http_client.UserJwtBusinessHttpClient.execute` | `async def execute(self, *, request: BusinessHttpRequest, user_token: OpaqueUserToken, call_deadline: float, cancellation: CancellationSignal) -> BoundedBusinessHttpResponse` | request 仅含受控相对路径；token 非空；绝对 deadline、取消、聚合前 raw body 上限；client 已绑定 service key/base endpoint | 任一 HTTP status 返回 bounded response（非 2xx body 恒空）；超时/超界/连接/协议为有限 typed transport failure | 一个绝对 timeout 内至多一次 HTTP、无 retry；所有路径关闭 response；域 client |
| 建议新增：`business.http_client.UserJwtBusinessHttpClient.aclose` | `async def aclose(self) -> None` | 可重复调用但底层 client 只关闭一次；关闭后 execute 固定失败 | 无业务结果；关闭错误只转安全内部枚举 | Runtime lifespan |
| 建议新增：`business.handler.BoundBusinessActionHandler.handle` | `async def handle(self, input: TInput, context: CapabilityExecutionContext) -> CapabilityResult` | 构造时绑定同一 definition/settings/client/projectors；校验 context、token、cancel、绝对 deadline | 按 9.1/11.5/12.1 返回合法公共结果；未知异常留给 core，`CancelledError` 传播 | 每次至多一个 HTTP 和一个 answer-safe payload；core registry |
| 建议新增：`business.user_projection.BusinessUserResultProjector.project` | `def project(self, *, definition: BusinessActionDefinition[...,TRecord], settings: BusinessActionSettings, result: BusinessRecordsResult[TRecord], max_user_result_bytes: int) -> BusinessUserResult` | 只迭代 definition、apply user transforms、required invariant、固定 JSON/bytes | 冻结 user result；失败 typed code | 纯函数；域 handler |
| 建议新增：`business.contracts.BusinessUserResult.to_domain_result` | `def to_domain_result(self) -> JsonObject` | 已在构造时验证 schema、顺序和 canonical bytes | 新建深冻结固定 JSON；不暴露 typed record | 纯函数；bound handler/core |
| 建议新增：`business.transforms.BusinessTransformRegistry.apply` | `def apply(self, *, transform_id: BusinessFieldTransform, definition: BusinessFieldDefinition[TRecord,TValue], value: TValue) -> JsonScalar` | 保留字段强类型，校验类型/字段 allowlist/全局上限；Decimal/date 不先降为 JSON | canonical safe JSON scalar；失败不含原值 | 纯函数；两个 projectors |
| 建议新增：`business.egress.BusinessEgressProjector.project` | `def project(self, *, definition: BusinessActionDefinition[Any,Any,Any,Any], settings: BusinessActionSettings, user_result: BusinessUserResult, policy: GlobalBusinessEgressPolicy, config_snapshot_id: str) -> ModelEgressResult` | 字段交集、转换、facts/bytes/count；snapshot ID 必须来自同一冻结 support | 核心定义的 allowed/denied/not_applicable 与 payload，不定义重复结果类型 | 纯函数；域 handler |
| 建议新增：`business.grounding.BusinessAnswerGroundingPolicy.validate` | `def validate(self, input: GroundingInput) -> GroundingDecision` | capability ID 必须等于 payload presentation action；只读 minimized question、safe payload、已共同校验的 `CandidateAnswer`；schema/fact/marker/token/coverage | accepted 或有限 reason；异常/未知 reason 失败关闭，不能改写候选 | 纯函数；`L2_00_02 GroundingPolicyRegistry` |
| 建议新增：`business.provider.BusinessDomainProvider` | `def domain_id(self) -> BusinessDomainId`；`def definitions(self) -> tuple[BusinessActionDefinition[Any,Any,Any,Any], ...]`；`def configuration_fragment(self) -> BusinessConfigurationFragment` | provider 已由域强类型 settings 构造；返回值须同域且冻结 | 有限定义/配置；非法 provider 阻止启动 | 不创建 client/registration；composition root |
| 建议新增：`business.provider.BusinessSupportFactory.build` | `def build(self, *, definitions: Sequence[BusinessActionDefinition[Any,Any,Any,Any]], config: BusinessConfigurationSource, core_max_domain_result_bytes: int) -> BusinessSupportSnapshot` | 全部启动不变量、service binding 唯一性、user≤core bytes 和 snapshot 算法 | 冻结 support 或启动失败 | 创建无外部连接对象；composition root |
| 建议修改：`business.provider.BusinessSupportSnapshot.local_action_resolvers` | `local_action_resolvers: tuple[LocalActionResolver, ...]` | `BusinessSupportFactory.build` 仅投影 enabled actions；按 capability ID 排序；校验 resolver ID 与 descriptor 精确相等且对象不重复 | 冻结 Resolver tuple；错配为启动错误 | 不调用 Resolver、不创建客户端；顶层 composition root 只读消费 |
| 已新增（测试范围）：`fixture_metadata_diagnostic_v2.execute_fake_candidate` | `def execute_fake_candidate(lifecycle_path: Path, result_path: Path, operations: Sequence[Callable[[], object]]) -> None` | operations必须恰好4项；lifecycle/result必须不存在；按固定phase顺序执行 | passed或首个失败的strict有限result；异常值不持久化 | 仅fake回调和测试临时文件；不得连接数据库 |
| 已新增（测试范围）：`fixture_metadata_diagnostic_v2.validate_manifest` | `def validate_manifest(manifest_path: Path, authorization_path: Path, repository_root: Path) -> None` | strict JSON、run/gate/auth/四查询预算、prepared/live=false、三项历史与七项asset SHA-256 | 成功无返回；任一漂移抛有限`employee.fixture_metadata_v2_invalid` | 只读文件/hash；launcher preflight |
| 已新增（测试范围）：`fixture_metadata_diagnostic_v2.finalize_staging_result` | `def finalize_staging_result(staging_path: Path, result_path: Path) -> None` | staging必须strict且`rawLogsDeleted=false`；result不存在 | 将日志清理事实收紧为true后exclusive+fsync正式result | 仅正式授权launcher在原始日志删除后调用 |
| 已新增（测试范围）：`employee_test_data_fixture.build_fixture_spec` | `def build_fixture_spec(seed: str) -> EmployeeFixtureSpec` | seed仅允许版本化非敏感ASCII token；返回固定四字段、非身份证格式标识及进程内fingerprint | 纯函数；值不得进入日志/evidence |
| 已新增（测试范围）：`EmployeeFixtureRepository` | `count_by_identifier(str) -> int`；`insert(EmployeeFixtureSpec) -> int`；`count_by_fingerprint(EmployeeFixtureSpec) -> int`；`delete_by_fingerprint(EmployeeFixtureSpec) -> int` | 每次返回严格0或1；实现不得update、宽查/删或重试 | 当前仅in-memory fake；未来真实实现须新设计/授权 |
| 已新增（测试范围）：`execute_fixture_lifecycle` | `def execute_fixture_lifecycle(*, repository: EmployeeFixtureRepository, metadata_result_path: Path, lifecycle_path: Path, evidence_path: Path, run_id: str, seed: str, consumer: Callable[[EmployeeFixtureSpec], None]) -> EmployeeFixtureExecution` | metadata hash/结构先于journal；precheck→insert→verify→consumer→cleanup严格单调，任何创建后失败finally清理；返回三终态和有限evidence | exclusive+fsync测试文件；fake repository调用各≤1，retry/resume=0 |
| 已新增（测试范围）：`validate_lifecycle`/`validate_evidence` | `def validate_lifecycle(path: Path) -> tuple[Mapping[str, object], ...]`；`def validate_evidence(value: object) -> Mapping[str, object]` | exact keys、顺序/terminal、模板/metadata hash、计数/终态/禁止持久化字段 | 只读或纯函数；不接收业务值 |

### 13.4 Java 边界关键方法适用性

本文不建议新增或修改 Java 方法，因为共享安全和业务授权实现不属于当前授权范围。后续提供方设计必须至少覆盖：

- JWT decoder/converter 如何把 `role` 集合映射为 Authority。
- Employee/Transaction 精确动作入口如何验证 `ROLE_ADMIN/ROLE_VIEWER`。
- 允许/拒绝时业务方法和数据访问调用次数。
- 2xx 响应数据可见性契约。

精确 Java 类路径/方法由 `L2_02_01/02` 或经授权的共享安全详细设计在核实实现后定义，本文只以 5.1 已存在触点和 10.2 可观察行为作为消费依据。

## 14. 测试与验证设计

### 14.1 测试定义

| 测试编号 | 状态 | 设计规则 | 层级 | 建议路径/用例 | Fixture、动作 | 关键断言 | 失败信号 |
|---|---|---|---|---|---|---|---|
| `TEST-BQCOM-001` | 建议新增 | `DR-BQCOM-001/015` | Unit/Contract | `agent-runtime/tests/unit/business/test_action_definition.py` | 两个 fake 域、descriptor/domain/service 重复/错配、filter/sort/contract limit 边界、required 空/重复/不可见、动态端点 | definition 冻结；身份/required/代码上限单一权威；common 无域字段；动作唯一 | 双重权威、动态 action/URL 或域耦合 |
| `TEST-BQCOM-002` | 建议新增 | `DR-BQCOM-002/013` | Unit | `agent-runtime/tests/unit/business/test_settings.py` | 各维度边界±1、未知/重复 filter/sort 字段、删除 required、user/model transform 缺失/重复/额外、重复 service/action、快照顺序置换/单值变化 | 只允许代码子集/更小值；每字段恰一 transform；任一 enabled 错误不就绪；canonical 输入同值同 ID、任一生效值变化必改 ID | 配置扩权、隐式 transform、半有效启动或快照不确定 |
| `TEST-BQCOM-003` | 建议新增 | `DR-BQCOM-003/014/019` | Unit/HTTP | `agent-runtime/tests/unit/business/test_user_jwt_http_client.py`、`test_wire_json.py` | 缺 token、fake service token provider、恶意 base/path、proxy env、redirect、非2xx大正文、2xx limit±1、timeout/cancel/close；ExactDecimal正负零/尾零/128与129字节及巨大正负 exponent；Unicode/控制字符/surrogate、depth 8/9、collection 256/257、循环、nested body、float/裸Decimal/quoted/raw bytes拒绝 | 缺 token调用0；只有原 user JWT header；无 retry/redirect/env proxy；非2xx正文读取0；大指数在 token 展开前拒绝；相同 Unicode/decimal 输入只产生一组 canonical bytes；所有路径关闭且 aclose 一次 | service fallback、SSRF/token 泄露、多调用、非唯一编码、递归/内存失控、精度漂移或资源泄漏 |
| `TEST-BQCOM-004` | 建议新增 | `DR-BQCOM-004/005/016` | Cross-service Contract | `agent-runtime/tests/contract/business/test_authority_consumption.py` | 10.2 全矩阵；含已知+未知混合 role、无效 token；安全边界/业务/DAO spies | ADMIN/VIEWER 允许；token 认证失败401；已验证 token 的缺失/未知/格式错 role 403且领域调用0；Adapter 不解析 role | 401/403、混合 role 或 Adapter 白名单漂移 |
| `TEST-BQCOM-005` | 建议新增 | `DR-BQCOM-006/012` | Unit | `agent-runtime/tests/unit/business/test_service_result_mapping.py` | 1xx～5xx 分区、204/400/404 semantics true/false、其他2xx records/empty、401/403/429/5xx/timeout/unknown body | common status mapper 穷尽；不继续解码的 status codec调用0；204/404 未确认不得变 no_result；无域自定义公共 code | 域解释状态、401/403混淆、无界 code 或失败变 no_result |
| `TEST-BQCOM-006` | 建议新增 | `DR-BQCOM-007/008` | Unit | `agent-runtime/tests/unit/business/test_user_projection.py` | records/coverage不变量、连续 ref、字段顺序/额外/缺 required、canonical bytes limit±1、core limit小于业务设置 | 固定 JSON；extra零进入；必需/超界失败 downstream；core交叉约束启动失败；不制造 no_result/空 success | 宽字段、core invalid result 或状态漂移 |
| `TEST-BQCOM-007` | 已存在并经 Employee 非 live 复用验证 | `DR-BQCOM-008/009/018` | Unit | `agent-runtime/tests/unit/business/test_egress_projection.py`、`agent-runtime/tests/unit/adapters/employee/test_egress.py` | 字段交集；六转换逐一测试 exact type、边界±1、string/float/bool-as-int、控制/Bidi、naive/aware datetime、Decimal rounding；Employee 默认空、代码上限、payload超界/global disabled | model⊂user；转换输出精确；未知/类型错/转换失败模型调用0且本地结果保留；只返回核心 `ModelEgressResult` | 原始字段外发、宽松强转或重复结果类型 |
| `TEST-BQCOM-008` | 已存在并经 Employee 非 live 复用验证 | `DR-BQCOM-010/011` | Unit | `agent-runtime/tests/unit/business/test_grounding.py`、`agent-runtime/tests/integration/adapters/employee/test_sensitive_egress_zero_call.py` | marker ID/连续性/重复/集合、每种句末/尾段、两个精确前缀、跨句引用、掩码ID/负数/日期的重叠 span、text 内 ASCII token、unsupported、truncated 禁词；Employee safe facts正向 | 同一 tokenizer 生成 fact/answer token；span 不重复提取；无依据或不确定候选整体拒绝；合法 canonical 引用通过 | 掩码/负数误拒、只核 fact ID、模糊前缀或未核本句事实 token |
| `TEST-BQCOM-009` | 建议新增 | `DR-BQCOM-003/012/014/019` | Integration with fake server | `agent-runtime/tests/integration/business/test_failure_and_cancellation.py` | mapper/codec/client/normalizer spy、mapper arguments failure、encode request invariant failure、decode response failure、两个并发请求交错响应、请求回显不匹配、解析跨 deadline、迟到 body、断连、敏感异常、重复请求、启动中途失败 | mapper失败为invalid_argument且HTTP0；encode失败越过handler并由Core固定为internal_failure且HTTP0；decode失败为downstream invalid_response且HTTP1；decode每次取得当前调用栈同一冻结wire request且无codec可变请求状态；取消后丢弃；已建client逆序关闭；日志无敏感值 | 请求/响应失败归属混淆、并发串响应、后台结果、半冻结registry、资源或原始异常泄露 |
| `TEST-BQCOM-010` | 建议新增 | `DR-BQCOM-013/014` | Architecture | `agent-runtime/tests/architecture/test_business_common_boundaries.py` | import graph、dependency/storage/retry scan | common 无域/SDK/DB/message/role auth；无 retry | 动态平台、持久化或反向依赖 |
| `TEST-BQCOM-011` | 建议新增 | `DR-BQCOM-001/015` | Extensibility | `agent-runtime/tests/contract/business/test_fake_third_domain.py` | 新增 test-only `sample.read` definition/provider；provider 顺序置换、跨域 fragment/重复 service；全域禁用 | 只新增 fixture/provider；snapshot 顺序稳定；错配启动失败；禁用无 client/registration；core/common/已有域源不改 | 扩展要求改 core/common 或 provider 泄漏域 |
| `TEST-BQCOM-012` | 已存在并通过非 live 验证 | `DR-BQCOM-010/011` | Model integration with spy | `agent-runtime/tests/integration/business/test_business_text_is_data.py` | fact text 含注入语句、模型越界回答 | 请求保持 no-tools 且文本只在 JSON value；不触发第二动作/权限变化；越界答案拒绝 | 文本影响控制语义 |
| `TEST-BQCOM-013` | 已存在并通过非 live 验证 | `DR-BQCOM-017` | Security contract | `agent-runtime/tests/contract/business/test_sensitive_question_scenarios.py`、`agent-runtime/tests/integration/adapters/employee/test_sensitive_egress_zero_call.py` | 12.3 合成问题+model spy | 每个敏感类别 transport 0；generic case只通过输入闸门不等于授权 | 具体标识或凭证外发 |
| `TEST-BQCOM-014` | 建议新增 | `DR-BQCOM-019` | Cross-language contract | `agent-runtime/tests/contract/business/test_exact_decimal_wire.py`；Transaction provider MockMvc contract | `0/-0/100/100.00/0.1`、正负值、末位边界、超precision/scale、指数/quoted/float/NaN/Infinity、非 ASCII 字符及4096字节边界 | Python canonical bytes 中金额是未加引号 plain number且不经float，字符串转义与排序字节唯一；Java 精确接收为预期 `BigDecimal`；非法 capability 输入 HTTP=0；Employee GET body仍为空 | 精度漂移、canonical 实现分叉、Jackson coercion依赖、共享契约破坏或跨语言值不一致 |
| `TEST-BQCOM-015` | 建议新增 | `DR-BQCOM-020` | Unit/contract | `agent-runtime/tests/unit/business/test_local_action_resolver_binding.py` | definition 缺 Resolver、ID 错配、重复对象、重复 capability、disabled/enabled 组合和 provider 顺序置换 | 缺失/错配/重复均阻止就绪；只输出 enabled Resolver；结果按 canonical capability ID 稳定排序 | 配置替换 Resolver、禁用动作仍参与解析或启动顺序漂移 |
| `TEST-BQCOM-016` | 建议新增 | `DR-BQCOM-013/015/020` | Composition | `agent-runtime/tests/integration/business/test_business_resolver_composition.py` | 两域全禁用、只启用一域、两域启用、support 构建中途失败、Runtime build spy | snapshot 字段不可变；禁用时无 registration/client/Resolver；启用时 registration 与 Resolver 集合一一对应；失败不冻结 registry 且已建资源逆序关闭 | 半有效 Runtime、Resolver/handler 集合漂移或动态发现 |
| `TEST-BQCOM-017` | 建议新增（Employee candidate-02 承担） | `DR-BQCOM-021` | Contract/fault injection | `L2_02_01 TEST-EMP-015` | 在域请求前、域请求中、响应映射、投影、模型初始化、首 outbound 前后、模型终态和 evidence 写入阶段逐点注入失败 | pre-model journal 总是先存在；域 started/terminal 与精确计数一致；未 outbound 为 `failed_unconsumed` 且无 marker，已 outbound 为 `failed_consumed` 且 marker 精确绑定；每条受控失败均有有限 terminal/evidence；retry/resume=0 | 缺 journal、计数范围化、错误掩盖、消费状态错判或历史资产被改写 |
| `TEST-BQCOM-018` | 建议新增（Employee qualification 承担） | `DR-BQCOM-022` | Contract/fake/live opt-in | `L2_02_01 TEST-EMP-016` | synthetic 合格/字段缺失/策略冲突/请求失败、strict Schema、至多一条只读筛选、一次真实 detail、敏感扫描和八项历史哈希 | 两字段布尔与有限原因一致；detail=1、其他端点/model=0；evidence 无标识/JWT/字段值/原始响应；candidate-01/02 哈希不变 | 把不合格输入再次送入付费候选、业务值落盘、隐式读取模型密钥或历史漂移 |
| `TEST-BQCOM-019` | 已新增（Employee qualification v2 承担） | `DR-BQCOM-023` | Contract/fake/history/static integration | `L2_02_01 TEST-EMP-017` | exclusive lifecycle、数据库/detail各阶段故障、重复/乱序拒绝、strict result/Schema、codec/user-result最小字段、PowerShell授权顺序、Java固定SQL、退役run六项与egress八项历史哈希 | fake所有阶段都有有限终态；数据库筛选/detail started/terminal均0/1；model/retry/resume/other endpoint=0；manifest/auth精确绑定且live输出不存在 | 在 journal 前触发数据库/detail、筛选条件漏字段、prepared入口读取密钥/启动进程、历史漂移或把non-live误记为门禁通过 |
| `TEST-BQCOM-020` | 已新增并通过（Employee aggregate diagnostic承担） | `DR-BQCOM-024` | Contract/static integration/opt-in database | `L2_02_01 TEST-EMP-018` | strict Schema/validator、额外键/负数/非单调/错误首零反证、Java源码单个聚合调用与禁止列反证、candidate-02两项hash、一次真实聚合 | 只产生一个计数行；所有计数整数且关系一致；detail/endpoint/model/retry/resume=0；evidence无标识/字段值/原始行；若完整计数0则精确报告首零阶段 | 多查询、选择原始列、持久化业务值、将诊断误作资格通过或据此自动准备新候选 |
| `TEST-BQCOM-021` | 已新增并通过（Employee static diagnostic承担） | `DR-BQCOM-025` | Contract/static/history | `L2_02_01 TEST-EMP-019` | 聚合evidence/9项源码精确hash、映射八项、Map写入、DTO/required/default/backfill反证、版本化资产计数、strict Schema额外键/错误已知项/外部调用反证 | 映射一致、数据来源资产为0、物理列和原始分布保持unknown；数据库/端点/服务/model=0 | 以硬编码结论掩盖源码漂移、把ES当数据库导入或把静态缺口误作物理数据事实 |
| `TEST-BQCOM-022` | 建议新增；非live契约已通过 | `DR-BQCOM-026` | Contract/static/live-opt-in | `L2_02_01 TEST-EMP-020` | strict Schema/validator、互斥分区和总数不变量、snapshot drift、两查询静态反证、launcher日志清理/零凭证/零HTTP/零模型 | 查询前证明最小边界；查询后验证有限evidence与精确计数 | 用重叠分类、返回原始值、超过2查询或把快照漂移判为根因 |
| `TEST-BQCOM-023` | 已实现并通过 | `DR-BQCOM-027` | Contract/fake repository/fault injection | `L2_02_01 TEST-EMP-021` | 覆盖metadata/schema、确定性模板、正常create/verify/consumer/cleanup、冲突、precheck/insert/verify/delete/cleanup验证/consumer失败、非法计数、输出冲突、strict lifecycle/evidence与敏感值反证 | 16 passed；物理证据已确认但仅验证fake/non-live | 真实数据访问、阶段无terminal/重排、计数误分类、cleanup失败被吞或标识/值持久化 |
| `TEST-BQCOM-024` | 已新增并通过非live；run-01 live失败按历史测试固定 | `DR-BQCOM-028` | Contract/static/live-opt-in/history | `L2_02_01 TEST-EMP-022` | strict success/failure Schema、四查询源码计数、只读/禁止SQL反证、查询预算、失败终态、源/实现/报告hash和原始日志删除 | run-01只证明第1条成功与第2条collation失败，不允许把部分结果当作完整元数据 | 自动重试、失败后继续查询、持久化trigger正文/业务值、改写失败历史 |
| `TEST-BQCOM-025` | 已新增并通过non-live | `DR-BQCOM-029` | Contract/static/fake/history/disabled Java | `L2_02_01 TEST-EMP-023` | 四阶段每一处故障立即停止；lifecycle查询前存在且exclusive/fsync；SELECT alias投影不变；所有名称比较显式BINARY；三份Schema闭合；manifest/auth及三项历史hash严格 | candidate-02 lifecycle/result正式文件不存在，数据库/外部调用0 | 修改run-01、隐式collation、失败后继续、retry/resume、未绑定live执行 |
| `TEST-BQCOM-026` | 已修改并通过 | `DR-BQCOM-030` | Post-consumption contract/history | `L2_02_01 TEST-EMP-024` | frozen commit七asset、manifest/auth、lifecycle/result精确hash；四查询10事件、58列/InnoDB/三类约束0、全部安全零值 | 不读取数据库或凭证，不修改证据 | 当前asset冒充prepared、证据漂移、历史不可重放 |
| `TEST-BQCOM-027` | 已通过non-live、live与post-consumption history | `DR-BQCOM-031` | Contract/fake/static/live-opt-in/history | `L2_02_01 TEST-EMP-025` | 正常16事件、3/1/1预算、逐阶段故障、consumer/cleanup/host失败、严格Schema/manifest/auth、参数化BINARY SQL、显式事务、证据精确hash与frozen commit | live唯一执行通过；后续测试仅只读冻结blob与append-only证据 | 宽DELETE、隐式事务、host成功误报、INSERT后未清理、历史或asset漂移 |
| `TEST-BQCOM-028` | 建议新增 | `DR-BQCOM-032` | Contract/fake/history | `agent-runtime/tests/integration/adapters/transaction/test_transaction_egress_candidate_preparation.py`、`test_transaction_egress_candidate_harness.py`、`test_real_transaction_egress_candidate.py`及model input guard直接测试 | generic Transaction问题、具体值/敏感/extra/unknown、single search与30 answer fake、type/amount精确facts、三终态及manifest/history | prepared阶段business/model outbound=0；字段/预算/消费顺序/strict Schema/hash全部通过 | 模糊allow、字段泄露、消费过早、失败无证据、重试/续跑或旧manifest漂移 |
| `TEST-BQCOM-029` | 已通过 | `DR-BQCOM-033` | Contract/fake/static/history | candidate-03 module/Schema/manifest/auth、fake repository+detail consumer、Java disabled test、launcher与history测试 | 正常qualified、precheck/insert/verify/detail/资格/cleanup/host故障、cleanup-required、3/1/1与detail 0/1、生产投影复用、跨进程sequence、历史hash和零敏感持久化 | 定向14 passed/1 live skipped；全量930 passed/19 live skipped；strict mypy 326 files、compileall、AST、Java disabled编译通过；真实数据库/JWT/detail/model=0 | 无未关闭反证；live结果仍待`GATE-049` |
| `TEST-BQCOM-030` | 已新增并通过 | `DR-BQCOM-034` | Contract/fake/static/history/disabled Java | candidate-04 module/pre-SQL Schema/manifest/auth、host故障注入、显式启动类源码断言、candidate-03历史hash | Maven/Spring失败在首SQL前形成`failed_unconsumed`；SQL/detail/model为0；唯一生产启动类绑定；原v3资产与证据不可变 | 定向19 passed/1 live skipped；Employee/Business 315 passed/10 skipped；全量949 passed/20 skipped；strict mypy332、compileall、AST、disabled Java编译及hash校验通过 | 未访问数据库/服务/JWT/model；prepared不构成live授权 |
| `TEST-BQCOM-031` | 已新增并通过 | `DR-BQCOM-035` | Post-consumption contract/history | candidate-04 history test、prepared frozen HEAD、host/lifecycle/result三项证据 | 精确哈希、4条host与15条SQL事件、3/1/1+detail1、字段全true、exact cleanup、安全零值；显式断言冻结validator拒绝未成对`host_validation` | 定向20 passed/1 live skipped；不读取JWT/密钥、不访问数据库/服务/model | 只固定失败关闭事实，不放宽validator、不关闭`GATE-049` |
| `TEST-BQCOM-032` | 已新增并通过 | `DR-BQCOM-036` | Contract/fake/static/history/disabled Java | v5 direct/finalizer/host/history/live-opt-in tests及v4 post-consumption history | qualified、host exit、log leak均由真实finalizer形成成对`host_validation`和run终态并通过同一validator；注入非法pending/lifecycle时result不存在；manifest/auth/history/asset/预算精确，v4五项及既有十一项历史hash不变 | 定向22/1 skipped、Employee/Business 337/11 skipped、全量972/21 skipped、strict mypy 338、compileall、PowerShell AST及Java disabled编译通过 | 未启动服务/数据库/JWT/detail/model，未设置live开关 |
| `TEST-BQCOM-033` | 已新增并通过 | `DR-BQCOM-037` | Post-consumption/contract/fake/static/history/live Java | v5 consumed history；v6 direct/finalizer/host/history/live-opt-in、launcher AST、Java live test及独立v6 consumed-history | v5历史精确；v6 Python/Java exact四键、逐键boolean、23项history/12项asset、五项SHA、完整16条序列、3/1/1+detail1、字段全true、exact cleanup及安全零值 | 消费后定向23 passed；Java后续disabled编译1 skipped；其余回归/类型/compileall见`VAL-BQCOM-025` | 唯一live已消费；未调用模型、未修改生产代码/API/数据 |
| `TEST-BQCOM-034` | 已新增并通过 | `DR-BQCOM-038` | Contract/fake/static/history/disabled Java/live-opt-in | candidate-03 lifecycle/consumed/pending/staging/result Schema、逐阶段fake、manifest/auth/history、launcher AST、Java disabled与生产接缝测试 | 成功76条唯一语言；3/1/1+detail1+answer30、有效≥27、四终态、首outbound消费、INSERT后cleanup、上下文/staging失败有限化、禁止字段/字面量/log/retry/resume=0；17项history/28项asset精确hash | 定向21 passed/1 live skipped；全量1017 passed/23 skipped/1历史deselect；Maven BUILD SUCCESS/1 skipped | prepared阶段数据库/服务/JWT/model/outbound=0 |
| `TEST-BQCOM-035` | 已新增并通过 | `DR-BQCOM-039` | Contract/grounding/composition/history/candidate preparation | answer v2精确指令、v1 parser复用、带marker/无marker反证、生产组合根唯一v2、Employee candidate-04及Transaction candidate-02 task/bootstrap/history/asset/fake生命周期 | marker与ID集合一致才通过；validator/public DTO/facts不变；旧candidate证据和answer v1源码不变；两域新run不复用旧authorization | Employee候选定向23项及Transaction候选定向22项、Transaction/Business 169项回归通过 | 未读取key、未调用模型/业务系统 |
| `TEST-BQCOM-036` | 已新增并通过 | `DR-BQCOM-040` | Contract/fake/static/history/launcher | candidate-02四项历史精确SHA与不可重跑；candidate-03全资产绑定、真实collection smoke、wrong/missing source、asset失败跳过collection、preflight fsync、环境隔离、首SELECT前零调用及既有1/30 fake链 | 定向27 passed/1 live skipped；Transaction/Business 199 passed/4 skipped；full non-live 1097 passed/26 skipped/1既有Employee历史断言deselect；strict mypy372、compileall/AST通过 | prepared路径未读取真实类型/JWT/密钥，数据库/服务/model/outbound均0 | 不包含live或数据库 |
| `TEST-BQCOM-037` | 已新增并通过 | `DR-BQCOM-041` | Contract/fake/static/history/launcher | candidate-03六项SHA与失败计数不可变；candidate-04用live同源构造验证获准type/amount及record_ref通过，JWT/key/`transaction_id_masked`值及未知payload key在delegate前拒绝；首outbound消费、1/30预算、三终态及host preflight不变 | 定向34 passed/1 live skipped；Transaction/Business 230 passed/5 skipped/1 retired prepared-only deselected；全量1130 passed/27 skipped/2 retired prepared-only deselected；strict mypy 8 files、compileall、AST通过 | 外部调用0；生产src和旧候选不变 | `GATE-057` Closed |
| `TEST-BQCOM-038` | 已新增并通过 | `DR-BQCOM-042` | Contract/fake/static/history/PowerShell AST | 两域全部阶段成功顺序；asset/config/auth/domain/readiness/login/candidate/cleanup逐阶段失败；candidate前失败时inner输出与外部调用为0；candidate后不复制inner计数；仅own PID停止；secret/log零落盘；candidate-04及历史哈希不变 | 定向bootstrap、两域Business回归、strict mypy、compileall、AST与历史hash | non-live期间未读取真实JWT/密钥、启动服务、访问数据库或产生outbound | `GATE-058/059`已关闭 |
| `TEST-BQCOM-039` | 已实现并通过 | `DR-BQCOM-043` | Contract/fake/static/history/build provenance/PowerShell AST | v1四项执行历史与candidate未调用反证；v2源码资产和两个JAR精确hash；JAR缺失/漂移/source-build不一致在启动前失败；六类有限诊断与unknown、原始消息/路径/secret禁止、日志仍删除；candidate前inner输出为0 | 定向21 passed；Transaction/bootstrap 152 passed、5 skipped、2个历史prepared-only断言按既有post-consumption覆盖排除；Business/Transaction 127 passed；strict mypy 395 files、compileall、AST、历史hash与构建产物hash通过 | 全程未启动服务、读取secret、访问数据库或产生outbound | `GATE-060`关闭证据 |
| `TEST-BQCOM-040` | 已完成 | `DR-BQCOM-044` | Contract/fake/static/history/build provenance/PowerShell AST | Employee v1 manifest/auth/source/history及prepared零输出不变；v2 auth JAR/source/build/command精确绑定；JAR缺失/漂移在启动前拒绝；六分类+unknown、禁止字段、日志删除、outer语义和candidate零调用；共享Transaction v2哈希不变 | 冻结后定向33 passed；全量non-live 1189 passed/27 skipped/3个既有prepared-only历史断言deselect；strict mypy 399 files；compileall、launcher AST、确定性Maven build和JAR SHA重算通过 | 未启动服务、读取secret、访问数据库、Employee或DeepSeek；正式v2 lifecycle/result/diagnostic不存在 | `GATE-062`关闭；不构成`GATE-024`授权 |
| `TEST-BQCOM-041` | 建议新增 | `DR-BQCOM-045` | Contract/full-path fake/static/history/PowerShell AST | 真实共享executor与真实Employee v3 preflight组合必须越过asset phase；执行前outer/inner输出全缺失；当前lifecycle合法；预存lifecycle/result/diagnostic/任一inner输出均失败关闭；v2四项历史、candidate-04、Transaction资产与生产src不变 | 失败信号不得再为本次lifecycle触发`asset_hash_invalid`；fake candidate调用最多1且外部调用0 | strict pytest、full-path组合测试、history hash、mypy、compileall、AST及代码对照设计复核 | `GATE-063`关闭前不得创建新live授权 |
| `TEST-BQCOM-042` | 已完成 | `DR-BQCOM-046` | 文档契约/计划 DAG/状态统计/跨层一致性 | 核对系统 E2E 只依赖已完成真实 Provider；五项 Not Applicable 门禁不授予执行权；三个 Deferred 实验包不阻塞当前交付；Employee/Transaction 两个 scoped 安全门禁继续禁止真实业务结果外发 | 历史失败结论、30/27实验阈值和 append-only 证据均不改判 | architecture/L2/plan strict validator、计划上下文发现与 `git diff --check` | 仅证明治理闭环，不替代运行时系统 E2E |

### 14.2 关键权限与出域场景

| 场景 | 业务 HTTP | 用户结果 | 回答模型 | 公共结果 |
|---|---:|---|---:|---|
| 缺 user JWT | 0 | 无 | 0 | unauthenticated |
| ADMIN/VIEWER 且业务允许 | 1 | 按字段交集 | 0或1 | success/no_result |
| 已验证 user token 但 unknown/missing/malformed role | 1 到达安全边界，受保护业务方法/数据访问0 | 无 | 0 | forbidden |
| token 缺失/签名或有效期失败/非 user token | 缺 token 时0；其他无效 token 为1并止于安全边界 | 无 | 0 | unauthenticated |
| 业务 403 | 1 | 无 | 0 | forbidden |
| records 存在但 required field 缺失 | 1 | 无 | 0 | downstream_failure |
| 用户结果有效、egress disabled | 1 | 有 | 0 | success+denied |
| 业务文本含指令 | 1 | 受控 | 至多1 | 只能作为 fact；越界回答 invalid_output |

### 14.3 验证定义

| 验证编号 | 工作目录/前置 | 命令或人工步骤 | 验证范围与充分性 | 预期结果 | 当前执行状态 |
|---|---|---|---|---|---|
| `VAL-BQCOM-001` | `D:\codex`；本文/validator 可读 | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md --root D:\codex --strict` | 只证明文档结构、追踪、引用和质量规则 | 0 errors、0 warnings | 2026-08-14：v0.12 严格校验通过 |
| `VAL-BQCOM-002` | `D:\codex\agent-runtime`；common unit tests 已存在 | `python -m pytest tests/unit/business -q` | 证明已实施配置、结果、字段、转换和 grounding 纯逻辑；不证明 v0.6 Resolver 绑定 | 全部通过 | 历史 `WP-BQCOMMON-01` 已验证；本轮未改代码，不重复冒充 v0.6 通过 |
| `VAL-BQCOM-003` | `D:\codex\agent-runtime`；contract/integration/architecture tests 已存在 | `python -m pytest tests/contract/business tests/integration/business tests/architecture/test_business_common_boundaries.py -q` | 证明既有 JWT、扩展、模型/文本隔离和边界；不证明真实业务授权或真实结果外发 | 全部通过 | 2026-08-13：10 passed；另有 Employee 出域定向26 passed、全量非 live 724 passed/10 skipped、strict mypy 284 files 与 compileall 通过 |
| `VAL-BQCOM-004` | `D:\codex\agent-runtime` | `python -m compileall -q src tests`、`python -m mypy --strict src tests`、`python -m pip check` | 证明已实施签名/依赖一致，须与行为测试联合 | 三条无错误 | 历史实施验证见 `P3_00`；本轮无代码修改 |
| `VAL-BQCOM-005` | Java 提供方与受控角色 token | 两域各自 Maven/真实允许拒绝矩阵，命令由域 L2 固定 | 证明外部 Authority 与最终授权，不由 Python 测试替代 | ADMIN/VIEWER 允许；认证/角色失败按契约拒绝；领域调用受控 | Employee `VAL-EMP-003～005` 与 Transaction `VAL-TXN-003～005` 已按各自冻结目标配置通过；不等于默认/生产生效 |
| `VAL-BQCOM-006` | `D:\codex\agent-runtime` | `$env:PYTHONPATH='src;.'; python -m pytest tests/unit/business/test_local_action_resolver_binding.py tests/integration/business/test_business_resolver_composition.py -q`，再执行 `python -m mypy --strict src tests` | 证明 common 只绑定/投影 Resolver 且不实现域语法，registration/Resolver 一一对应 | 全部通过 | 2026-08-07：公共绑定/组合根 8 passed；本工作包直接回归 109 passed；strict mypy 237 source files 无问题 |
| `VAL-BQCOM-007` | `D:\codex\agent-runtime`；live opt-in 全部为0 | `python -m pytest tests/contract/business/test_sensitive_question_scenarios.py tests/unit/model/test_input_guard.py tests/unit/model/test_zero_call.py -q`，并纳入 `VAL-MODEL-013` 全量回归 | 证明12.3 fixture精确分类、敏感与域特定unknown在selector/answer前失败关闭且transport=0；generic只通过输入Guard，不授予业务权限 | 全部通过 | 2026-08-12 已由172项模型/安全定向、578项全量非live、243文件strict mypy及compileall覆盖；代码复核无遗留 blocker/high/medium |
| `VAL-BQCOM-008` | `D:\codex\agent-runtime`；仅 candidate-02 fake/non-live | 执行 `L2_02_01 VAL-EMP-007`，并重算 candidate-01 manifest/authorization/诊断/pre-model failure 四项 SHA-256 | 证明 `DR-BQCOM-021` 在当前 Employee 实例中的消费边界、精确计数、失败终态和历史不可变性；不证明真实服务或模型出域 | 全部通过且四项历史哈希精确不变 | 2026-08-14：candidate 定向18 passed/1 live skipped；Employee/Business 154 passed/3 live skipped；全量752 passed/12 live skipped；strict mypy 293 files、compileall、PowerShell AST、四项历史hash、24项manifest资产、41节点/73边DAG均通过；代码对照设计复核无未关闭 blocker/high/medium |
| `VAL-BQCOM-009` | `D:\codex`；资格筛选不读取模型密钥 | 执行 `L2_02_01 VAL-EMP-008`，并重算 candidate-01 四项与 candidate-02 manifest/authorization/lifecycle/result 四项 SHA-256 | 证明 `DR-BQCOM-022` 的只读资格筛选、一次 detail、严格有限 evidence、零模型/零泄漏和八项历史不可变性；不证明 candidate-03 或真实模型出域 | 两字段均存在、egress reason=`qualified`、计数与安全结论符合且全部哈希不变 | 非 live、类型、AST、Java编译及八项历史校验通过；受控运行失败且未创建最终 evidence，detail只能判定0～1，故本VAL未通过，三项门禁保持Open |
| `VAL-BQCOM-010` | `D:\codex`；不设置live开关且不读取任何密钥 | 执行 `L2_02_01 VAL-EMP-009`；严格验证 v2 manifest/authorization、退役run六项和Employee egress八项历史哈希，并确认 lifecycle/result 不存在 | 证明 `DR-BQCOM-023` 非 live 设计与实现、请求前journal、精确0/1、完整最小字段条件和失败关闭；不证明数据库内容、JWT、真实detail或资格通过 | 定向14 passed；Employee/Business 179 passed/5 skipped；全量777 passed/14 skipped；strict mypy 299 files、compileall、PowerShell AST、Java disabled编译及全部哈希通过；manifest SHA-256=`6d853ecee412a734f111d1d30740a703fe0343593560b7b01ed4c5194dfdb66f` | 2026-08-14：非 live准备通过，`GATE-049`保持Open；代码复核无未关闭 blocker/high/medium |
| `VAL-BQCOM-011` | `D:\codex`；不启动auth、不设置/读取JWT与`LLM_API_KEY` | 执行 `L2_02_01 VAL-EMP-010`；先验证strict Schema、源码单查询/禁止列和candidate-02两项历史哈希，再以opt-in Java测试执行唯一一次本地数据库聚合，最后做敏感扫描、非live回归和代码对照设计复核 | 只证明本地Employee数据在四个资格条件上的整数分布和首个归零条件；不证明真实detail、资格通过、candidate-03可准备或模型出域 | aggregate query/result row=1/1；总数990，四单项988/989/10/0，四累积988/988/10/0，首零`work_base_si`；Employee端点/model/retry/resume/泄漏=0，evidence SHA-256=`f23115069adaa0bfedcfdb01b7f0889acb079961319db3c44547549ca088c46f` | 2026-08-14：strict evidence定向15 passed；全量non-live除冻结prepared断言外790 passed/15 skipped/1 deselected；该不可变旧断言单独如实为1 failed，新增post-consumption history测试通过；strict mypy 302 files、compileall、AST、Java disabled编译及代码复核通过。完整计数0后已停止，`GATE-049`保持Open |
| `VAL-BQCOM-012` | `D:\codex`；静态/非live，不读取数据库、JWT或`LLM_API_KEY` | 执行 `L2_02_01 VAL-EMP-011`；校验聚合evidence与9项源码hash、strict Schema/evidence、Employee/Business和全量non-live、strict mypy、compileall、Git历史/版本化数据资产只读检查及代码对照设计复核 | 只证明当前冻结源码映射一致、写入依赖调用方key且仓库没有Employee DDL/初始化/导入/回填；不证明物理列类型/default或990条原始值分类 | evidence SHA-256=`7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8`；数据库/Employee端点/服务/model=0 | 2026-08-14：定向11 passed；Employee/Business 276 passed/6 skipped/1 deselected；全量801 passed/15 skipped/1 deselected；strict mypy304、compileall与聚焦代码复核通过；`GATE-049`保持Open |
| `VAL-BQCOM-013` | `D:\codex`；测试范围，只读数据库最多2查询 | 执行 `L2_02_01 VAL-EMP-012`；先完成Python/Java disabled/AST非live验证，再运行版本化launcher并校验strict evidence、查询/结果计数、分类和、敏感扫描、原日志删除及代码对照设计复核 | 元数据1次/1行、聚合1次/1行，HTTP/JWT/model/retry/resume=0；任何漂移失败关闭 | 2026-08-14：唯一一次执行得到nullable `longtext`、总数/NULL=990/990、其余分类=0；evidence SHA-256=`b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6`；定向14、相关290 passed/6 skipped/1 deselected、全量815 passed/15 skipped/1 deselected，strict mypy/compileall通过 | `GATE-049`保持Open；只证明本地数据全部NULL，不形成数据修复或candidate授权 |
| `VAL-BQCOM-014` | `D:\codex`；纯静态且零数据库/服务/模型 | 核对 source evidence SHA-256、Employee动态SQL/Mapper/Service副作用边界、版本化DDL/约束资产和现有诊断；确认是否足以实施 `DR-BQCOM-027` | 若列/键/FK/CHECK/trigger任一未知则必须在代码修改前停止，测试及外部调用计数均为0 | 2026-08-14：证据hash通过；静态代码只证明58列动态按键INSERT、按`ID_CARD_NO`DELETE，未发现版本化表约束来源，无法证明安全写入与清理 | 失败关闭；`IMPL/TEST-BQCOM-024/023`未实施，`GATE-050/049`保持Open |
| `VAL-BQCOM-015` | `D:\codex`；测试范围，只读数据库最多四条查询且无重试 | 执行 `L2_02_01 VAL-EMP-014`：非live contract/mypy/compileall/AST/Java disabled编译后运行一次版本化 launcher；失败时扫描、哈希并删除原始报告，固化严格有限 failure evidence | 只有四条查询均完成且完整元数据可冻结时关闭 `GATE-050`；部分成功或查询错误保持Open | 2026-08-14：第1条列/引擎查询成功，第2条约束查询因 `HY000/1267 information_schema_collation_mismatch`失败，第3/4条未执行；total started=2、success/failure=1/1、retry/resume=0，业务行/写入/HTTP/auth/model/泄漏=0；failure evidence SHA-256=`dce5e7659ed9cc49b52aa9cca6b70c9701c22cc55867f26cfa6a50ead291e7a1` | 未通过；run-01不可重跑，`GATE-050/049`保持Open |
| `VAL-BQCOM-016` | `D:\codex`；纯non-live/fake/static，不设置live开关 | 执行`L2_02_01 VAL-EMP-015`：candidate-02定向pytest、Employee/Business回归、strict mypy、compileall、PowerShell AST、Java disabled编译、三项历史/七项asset/manifest hash及代码对照设计复核 | binary SQL、四阶段journal/failure、strict Schema/manifest均通过；lifecycle/result正式文件不存在，数据库/HTTP/auth/model=0 | 2026-08-14：candidate-02准备已完成；run ID、manifest SHA-256和authorization reference见`L2_02_01 VAL-EMP-015` | 仅关闭非live工作包；`GATE-050/049`保持Open，正式四查询须再次授权 |
| `VAL-BQCOM-017` | `D:\codex`；只读post-consumption，不设置live开关 | 执行`L2_02_01 VAL-EMP-016`：定向post-consumption/history、Employee/Business非live回归、strict mypy、compileall、manifest/证据/commit hash及代码对照设计复核 | 冻结资产不变，数据库/HTTP/auth/model新增调用0 | lifecycle/result SHA-256=`affbd35987e4caaa4950888eaed80cf12e695470b1703735716f2dd54d52a105`/`9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51` | 通过后关闭`GATE-050`；`GATE-049`继续Open |
| `VAL-BQCOM-018` | `D:\codex\agent-runtime`；纯non-live/fake，不设置live开关 | 执行`L2_02_01 VAL-EMP-017`：fixture定向、Employee/Business相关回归、strict mypy、compileall、strict L2/P3 validator、diff/hash和代码对照设计复核 | metadata/hash在journal前校验；repository/consumer故障均有有限终态并finally清理；真实数据库/HTTP/auth/JWT/model=0 | 2026-08-14：三轮内审完成，fixture定向16 passed，目标strict mypy/compileall通过；完整相关结果见`VAL-EMP-017` | 通过后将test-data prep置Done；不关闭`GATE-049/024`，不授权真实fixture |
| `VAL-BQCOM-019` | `D:\codex`；`GATE-051`已消费，后续只读post-consumption | 执行`L2_02_01 VAL-EMP-018`：candidate定向/history、Employee/Business回归、strict mypy/compileall、PowerShell AST、六项历史/六项asset/manifest及证据hash、代码对照设计复核 | 唯一live执行形成16项lifecycle；3/1/1 terminal，inserted/verified/deleted=1、remaining=0，API/JWT/model/retry/resume/leak=0；原始日志已删除 | lifecycle/result SHA-256=`4d5ab81e68d24ac76a7c1d6f7b1a57204b7cb81c99f40f93afe444f4077f5b6c`/`f0003ec559fa4606edda2982f0ae6878bfa066262168236128705d0c40aa0e4a`；frozen commit=`fd95e181993caec1263529ebf6ff357daad5bcaa` | 通过并关闭`GATE-051`；`GATE-049/024`保持Open |
| `VAL-BQCOM-020` | `D:\codex\agent-runtime`；全部live开关为0，不读取密钥 | 执行Transaction candidate定向、model input guard、Business/Transaction回归、历史manifest重建、strict mypy、compileall、PowerShell AST、L2/P3 strict validator与代码对照设计复核 | synthetic/fake证明1/30预算、字段交集、decimal/facts/grounding、零调用负向、三终态和首outbound消费；真实search/DeepSeek=0 | 实施后冻结run/manifest SHA/auth/max calls | 只允许prep Done；`GATE-026/SA-GATE-006/GATE-034`保持Open |
| `VAL-BQCOM-021` | `D:\codex`；全部live开关为0，不读取JWT/密钥 | Employee candidate-03定向/history、全量非live、strict mypy/compileall、PowerShell AST、Java disabled编译、八项历史hash、manifest/auth/asset hash、L2/P3 strict validator及代码对照设计复核 | fake证明单一生命周期、3/1/1、detail最大1、四终态、cleanup-required、跨语言journal连续和零持久敏感值；正式lifecycle/result不存在 | run=`employee-egress-input-qualification-v3-20260814-candidate-03`；manifest=`495063a328af6a233f5600bd4efff31fdae5ab4e28aad8287bfce194051680dd`；auth=`P3_00:GATE-049` | prep Done；`GATE-049/024/SA-GATE-006/GATE-033`保持Open |
| `VAL-BQCOM-022` | `D:\codex`；全部live开关为0，不读取JWT/密钥 | Employee candidate-04定向/history、相关non-live回归、strict mypy/compileall、PowerShell AST、Java disabled编译、candidate-03 failure与11项history/11项asset hash、L2/P3 strict validator及三轮代码对照设计复核 | 显式Spring启动类、pre-SQL host journal/failure、3/1/1+detail1继承、retry/resume=0和零敏感持久化均通过；正式live lifecycle/result不存在 | run=`employee-egress-input-qualification-v4-20260816-candidate-04`；manifest SHA-256=`7dcae58a2a503a97fe89de0d01e63cb0450ccb0dd5945e4da5947d2df0875bb9`；authorization=`P3_00:GATE-049` | prep工作包关闭；`GATE-049/024/SA-GATE-006/GATE-033`保持Open |
| `VAL-BQCOM-023` | `D:\codex`；candidate-04已消费，后续只读且不设置live开关 | 校验prepared frozen HEAD、manifest/auth/history/asset、host/lifecycle/result精确SHA、实际15条序列、strict result与安全扫描；执行candidate-04 post-consumption定向测试和代码对照设计复核 | 业务资格、3/1/1、detail1、deleted1/remaining0及安全零值成立；host/result semantic validator通过；冻结SQL lifecycle validator因`host_validation`缺started而拒绝 | host/lifecycle/result SHA-256=`73bd37aaec1c3c57d7debea5f1120cd3cff828057bcaee84afbdb4495658472a`/`aa2479fc8051cb4741f9826b81521583285ede692d31b9c6bed01bf1b2a922c3`/`757bd4840143bbe5158facec89f7035cf72f99eac88b4c345d70cbc8ea0b5975`；定向20 passed/1 live skipped | candidate-04转不可复用历史；`GATE-049`失败关闭并保持Open，后继须全新candidate |
| `VAL-BQCOM-024` | `D:\codex`；candidate-05 prepared且live开关/数据库/JWT/model环境均不设置 | 已执行v5 direct/finalizer/host/history/live-opt-in定向测试、Employee/Business非live回归、strict mypy、compileall、PowerShell AST、Java disabled编译、v4五项及既有十一项历史SHA、manifest/authorization/asset与严格文档校验；聚焦代码对照设计复核符合 | 三个live同路finalizer分支形成16条完整lifecycle并由同一validator接受，invalid输入无result；prepared输出不存在且外部调用0 | run=`employee-egress-input-qualification-v5-20260816-candidate-05`；manifest SHA-256=`8b44a38ad6a02edd6db64b7c8e5fd02adee67a19ff1e9ef08e2ed3eb82f5ff74`；authorization=`P3_00:GATE-049`；asset=12 | candidate-05 prep实现切片已关闭；`GATE-049`保持Open，正式live须再次精确授权 |
| `VAL-BQCOM-025` | `D:\codex`；candidate-06已消费，后续只读且所有live/数据库/JWT/model开关未设置 | 校验manifest/auth/23项history/12项asset及host/lifecycle/result精确SHA；独立consumed-history严格重放16条序列、字段、3/1/1+detail1、cleanup与安全计数；执行定向、全量non-live、strict mypy、compileall、PowerShell AST、Java disabled编译及聚焦代码对照设计复核 | run唯一终态`qualified`；严格四键与两required-user字段全true，egress allowed；inserted/verified/deleted=1、remaining=0；模型/其他端点/retry/resume/leak=0；冻结validator接受16条完整lifecycle | manifest/auth/host/lifecycle/result SHA-256=`44f25232b445e0f1c8184b31ccf2dff4d5751a796b4f3ec327fb1ea2cbb702b2`/`bd0cb4d67c00e2aeba7756860f02a4f7df1fd9f17eb9420cc3ece4e524a697c5`/`9c4f7d9981bef665bd06068a96155433bfbe838ebad65d4ac5dc4424106c28d5`/`ec87bcb430fc90b3e9511871625bba60c07f7d4cc7e12842f3e18255624f6677`/`750f2e0d13866203116884e1950734bcb2b06100343f142cb5e96c63fe55a9cd` | 2026-08-17：消费后定向23 passed；全量996 passed/22 skipped/1 deselected，唯一deselect为不可变candidate-05 prepared-only历史断言且独立consumed-history通过；strict mypy346、compileall、AST、Java BUILD SUCCESS/1 skipped、聚焦代码复核符合。关闭`GATE-049`；`GATE-024/SA-GATE-006/GATE-033`保持Open |
| `VAL-BQCOM-026` | `D:\codex`；全部live开关为0且不读取JWT/`LLM_API_KEY` | candidate-03 direct/preparation/history/live-opt-in skip；Employee/Business与全量non-live；strict mypy/compileall、PowerShell AST、Java disabled编译、candidate-06五项及旧egress历史hash、manifest/auth/asset、L2/P3 strict validator与代码对照设计复核 | fake证明76条成功语言、四终态、3/1/1+detail1+answer30、有效阈值、首outbound消费、pending实际cleanup交叉校验、安全拒绝有限证据及passed安全零值；正式lifecycle/consumed/pending/staging/result不存在 | run=`employee-egress-v3-20260817-candidate-03`；manifest SHA-256=`901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e`；定向21/1 skipped、Employee/Business 375/13 skipped/1已知历史失败、全量1017/23 skipped/1同项deselect、strict mypy351、compileall、AST、Java BUILD SUCCESS/1 skipped | 通过并关闭`GATE-052`；`GATE-024/SA-GATE-006/GATE-033`保持Open |
| `VAL-BQCOM-027` | `D:\codex\agent-runtime`及适用域测试；全部live开关为0且未读取密钥 | 执行answer v2、两域新候选定向/相关non-live、strict mypy、compileall、AST、历史hash与代码对照设计复核 | Employee既有证据保持；Transaction candidate-02定向22 passed/1 skipped、Transaction/Business 169 passed/3 skipped、strict mypy110、compileall/AST通过；validator/public契约/v1/append-only历史无漂移，真实调用0 | 代码复核无blocker/high/medium | 通过并关闭`GATE-054/055`；`GATE-024/026/SA-GATE-006/GATE-033/034`保持Open |
| `VAL-BQCOM-035` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且移除JWT/`LLM_API_KEY` | candidate-03 host/preflight direct/history/fake、既有Transaction/Business non-live、strict mypy、compileall、PowerShell AST、candidate-01/02历史hash、manifest/auth重建及代码对照设计复核 | 已证明导入来源为冻结`src`、实际live测试collection在数据库选择前完成、asset/import/collection失败证据有限、子进程环境不含密钥/JWT/PYTHONPATH、database/search/model=0且candidate-02四项SHA不变 | run=`transaction-egress-v3-20260817-candidate-03`；manifest/authorization SHA-256=`9c1fb119f98fa9f1dc9bbd6904955d222c26fb39c837c179d3a85c1d883e6460`/`ca8983463fc051cf87bc563658bbe80cd583453de4547cd4c81df6524522970c` | 通过并保持`GATE-056` Closed；`GATE-026/SA-GATE-006/GATE-034`保持Open |
| `VAL-BQCOM-036` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且移除JWT/`LLM_API_KEY` | candidate-04 direct/history/preparation/live-opt-in skip、Transaction/Business非live回归、strict mypy、compileall、PowerShell AST、candidate-03六项SHA、manifest/auth重建及代码对照设计复核 | 允许type/amount与record_ref到fake delegate；JWT/key、非模型高熵值、非模型field ID和未知safe-payload key均零delegate；prepared数据库/search/model/outbound=0 | frozen HEAD=`680cd25ac0475f301260123c8ce6229ed05dc8c9`；run=`transaction-egress-v4-20260817-candidate-04`；manifest/authorization SHA-256=`ca440b8f3cf664cfe77b803c6a7786816935d391bc56e50a522f6cb76f0535d3`/`885ddb8854b34ccebf29d481e78fb84b1b6a550adf5330bf321eea5085690359`；15 history/33 assets | 通过并关闭`GATE-057`；`GATE-026/SA-GATE-006/GATE-034`保持Open |
| `VAL-BQCOM-037` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且未提供JWT/`LLM_API_KEY`/数据库凭据 | 两域bootstrap contract/failure/history、PowerShell AST、Business/Employee/Transaction及全量non-live回归、strict mypy、compileall、candidate-04与历史hash及代码对照设计复核 | 23项公共/域直接测试及冻结后29项全部通过；全量1159 passed/27 skipped/2既有历史deselect；strict mypy388、compileall、两launcher AST通过；未启动服务或产生外部调用。`pip check`仅报告工作站既有依赖版本漂移，不影响本test-only切片 | source commit=`038b6a0f54f5f8ace9a68e49073e5035279473da`；Employee manifest/auth=`b7be5caa4b3450242e9c63abf80152c023874641ed1bf4bf34bafdb10177af9a`/`d3d281ba5b62da632e4f52cdd4b86963b67a458c310ffdfaf799755c89158de9`；Transaction=`c1a90bb90a0cf44b378f9bde1b1701f8de1321e75a9eae0c23d1a15f30d4c0d6`/`b2b8d057afb1651cbb1b3ef098100846b30339da09ebbf2d7bb44ab705ae8308` | 通过；两个bootstrap包可置Done，`GATE-024/026/033/034/SA-GATE-006`保持Open |
| `VAL-BQCOM-038` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且移除JWT/`LLM_API_KEY` | wrapper-v1失败history、v2 direct/fake/history/preparation、确定性Maven构建及SHA重算、PowerShell AST、Transaction/Business回归、strict mypy、compileall和两轮代码对照设计复核 | v1四项SHA及candidate零输出不变；v2 JAR/source/build绑定、有限分类、秘密零落盘、原日志删除、retry/resume=0且正式v2 lifecycle/result/diagnostic不存在 | 已冻结run/manifest/auth/source commit；auth/Transaction JAR SHA-256=`da59695336c6f2fd11581760b41f0958114ac1f9e728ad834ff1a25a7595a96b`/`69cbb7a7a1b3193fb5d06a2c9af474e54917b1ac9c7786dcac1565aa32a8487e` | 已通过并关闭`GATE-060`；只允许申请`GATE-061`，不关闭完成门禁 |
| `VAL-BQCOM-039` | `D:\codex\agent-runtime`；全部live/数据库/服务开关为0且未读取JWT/HMAC/标识/`LLM_API_KEY` | Employee v1 prepared history、Employee v2 direct/fake/history/preparation、确定性auth Maven构建与SHA重算、PowerShell AST、Employee/Business及全量non-live回归、strict mypy、compileall和代码对照设计复核 | 已证明v1 manifest/auth/source/history与outer/inner零输出不变；v2 auth JAR/source/build/command、有限分类、秘密零落盘、原日志删除、retry/resume=0且正式v2输出不存在；共享Transaction v2源码与冻结历史无漂移 | source commit=`37b51608b851d463a1b1f6e5a782589efba9c49d`；prepared HEAD=`4dff45bfe0fdb3be2787b4c2231e8859299d6570`；run=`employee-egress-live-bootstrap-v2-20260818-candidate-02`；manifest/auth/auth-JAR SHA-256=`899eb378df014085c6e419a1720be96994698457b1f248215e8df2374118b383`/`0f9d71d0636f956aa12c4928a91137e53a211a74718a66a30b8f29fd8eb63000`/`da59695336c6f2fd11581760b41f0958114ac1f9e728ad834ff1a25a7595a96b` | 2026-08-18：定向33 passed；全量1189 passed/27 skipped/3个既有prepared-only历史断言deselect；strict mypy399、compileall、AST、Maven BUILD SUCCESS及代码复核通过。关闭`GATE-062`；`GATE-024/033/SA-GATE-006[Employee]`继续Open |
| `VAL-BQCOM-040` | `D:\codex\agent-runtime`；仅fake/static/disabled，禁止读取secret、启动服务、SQL、Employee或DeepSeek | 运行新v3 full-path fake、输出冲突、冻结历史、preparation、PowerShell AST、Employee/Business相关回归、strict mypy、compileall和代码对照设计复核 | 证明共享executor创建本次lifecycle后asset preflight通过；任何执行前历史输出仍失败关闭；旧证据哈希不变且外部调用0 | 未执行；须在`GATE-063`代码授权下完成 | 通过后只允许冻结新wrapper并重新申请`GATE-024` |
| `VAL-BQCOM-041` | `D:\codex`；仅文档修改，不执行代码、服务、数据库或模型调用 | 对 L0/L1、三份业务 L2 与 `P3_00` 执行 strict validator、计划 DAG/状态统计检查、跨层版本和门禁语义核对及 `git diff --check` | 结构、引用、追踪、枚举、DAG、状态统计和 scoped 安全门禁一致；历史证据与代码未修改 | 2026-08-20：4份架构、3份业务L2与P3 strict validator均0错误/0警告；计划发现确认71包/107依赖/63门禁和Done60/Ready1/Deferred10；`git diff --check`通过 | 通过只允许进入 `WP-SYSTEM-E2E-01` 的后续独立授权，不授权真实业务结果模型出域 |

## 15. 发布、迁移与回滚

- common 模块和两个 Adapter 均为新增；本文不产生数据库、索引、消息或业务数据迁移。
- 全局业务模型出域默认关闭；两个真实业务域动作默认禁用，先用合成 fake 实现公共切片。
- 域 L2 完成前只允许 test-only fake definitions，不得把候选端点或字段写成已确认事实。
- Authority/业务最终授权证据未完成时，真实动作即使客户端可达也必须保持禁用。
- 回滚优先禁用对应域动作并重启 Runtime；出域不确定时回滚为 `AGENT_BUSINESS_EGRESS_ENABLED=false`。
- 若共享安全/业务契约后续变化，必须同步提供方、域 Adapter、配置和 consumer/provider tests；不能只以配置兼容。
- 无持久业务状态，回滚不需要数据补偿；在途请求明确失败，不自动续跑。

## 16. 风险、待确认事项与门禁

### 16.1 风险与待确认事项

| 编号 | 类型 | 证据缺口或风险 | 触发场景 | 影响 | 建议 | 是否阻塞/需授权 |
|---|---|---|---|---|---|---|
| `RISK-BQCOM-001` | 直接依赖 | 混合裁决与 common Resolver 绑定现已实现；后续公共签名、definition 或组合根变更仍可能造成契约漂移 | 变更 Runtime 混合节点、公共签名或动作启停装配 | registration、Resolver 与 handler 集合可能漂移 | 保持 `TEST-BQCOM-015/016`、启动一一对应校验和 strict mypy 回归 | 当前工作包不再受阻；未来契约变更须回到对应 L2 并重新验证 |
| `RISK-BQCOM-002` | Authority | 共享 Converter 已形成且 Transaction 真实 JWT 装配已验证；未来配置或 Provider 版本仍可能漂移 | 默认/生产启用或契约演进 | ADMIN/VIEWER 可能误拒绝或越权 | 保持共享实现对照、真实 JWT 端到端矩阵和生效核验 | 不阻塞已验证的 Transaction 目标配置；不证明默认/生产生效，也不自动覆盖其他域 |
| `RISK-BQCOM-003` | 最终授权 | Transaction search 已具备专用 guard 与真实允许/拒绝证据；其他域或相邻动作仍须独立证明 | 扩大真实动作范围 | 把单动作证据外推可能造成越权 | 每个域/动作由域 L2 与业务服务独立关闭方法授权和响应可见性 | 不阻塞已验证的 Transaction 目标配置；其他域/动作不得继承该结论 |
| `RISK-BQCOM-004` | 服务身份 | 误复用 Feign fallback 或未来 Python通用 client | 缺 user context | 绕过用户权限 | 专用 client 和服务 token 零调用测试；本地负向测试已通过 | 不阻塞已完成本地切片；真实联调仍须复核 |
| `RISK-BQCOM-005` | 字段分类 | 域字段已由两份 L2 确认本地候选，但真实授权/出域证据不存在 | 真实业务结果外发 | 敏感数据泄露 | 保持 global egress off，真实链路逐字段确认 | 不阻塞本地 fake；真实出域保持未获准 |
| `RISK-BQCOM-006` | 自然语言验证 | fact marker/token 校验不能证明复杂关系完全正确 | 模型总结多记录关系 | 仍可能语义过度概括 | 域 L2限制字段/回答模板，失败使用结构化结果 | 阻塞效果结论；不阻塞公共 fake |
| `RISK-BQCOM-007` | 兼容性 | strict unknown-field 可能因提供方新增字段失败 | 业务服务兼容扩展 | Agent downstream failure | 域 L2选择严格拒绝或显式忽略并做契约测试 | 不阻塞本文；域 L2必须选择 |
| `RISK-BQCOM-008` | 过度抽象 | common generic 被扩展为动态 Adapter | 新第三域需求 | 责任/安全边界丢失 | 保持代码 definition+显式 provider；架构测试 | 不阻塞当前切片；相关扩展须先评审 |
| `RISK-BQCOM-009` | 精确十进制兼容性 | 当前 JSON number→BigDecimal→MySQL `DECIMAL(50,2)` 的 `=/>/<`、无舍入链已验证；后续 schema、Jackson 或 mapper 演进可能漂移 | 契约版本变化后启用金额过滤 | provider 拒绝、截断/舍入或查询语义漂移 | 保持 16/2 Agent 硬上限、50/2 Provider 契约和跨语言/数据库回归，不依赖 string coercion | 当前 Transaction 目标配置可继续；任何精度链变更须重新评审 |
| `RISK-BQCOM-010` | Resolver 装配 | definition、registration 与 Resolver 由不同装配步骤产生，当前已由 snapshot 校验和组合根测试约束 | 启停配置、第三域或动作重命名 | 可被模型选中却不能本地解析，或禁用动作仍参与裁决 | 保持三者集合一次性校验冻结、ID/对象唯一、禁用零 Resolver及顺序置换测试 | 当前实现证据已满足；未来扩域或重命名时重新执行 `VAL-BQCOM-006` |
| `RISK-BQCOM-011` | 候选生命周期可观测性 | journal 只在域投影成功后建立，或 `finally` 强制读取未创建文件 | pre-model 失败 | 根因被二次异常遮蔽，域调用次数只能给范围，无法判定授权消费状态或关闭门禁 | 以 `DR-BQCOM-021` 在域请求前创建/同步 journal，transport 记录精确 started/terminal，有限终态由 consumed marker 唯一判定；历史 candidate 只读 | 阻塞 candidate-02 live；不阻塞其独立非 live 实施，不影响生产 Runtime |
| `RISK-BQCOM-012` | 测试输入资格 | 用字段为空或策略拒绝的员工输入创建付费候选 | 首次 Employee detail 后无法形成最小 safe facts | live 授权在模型前失败，不能产生有效出域证据 | 先执行 `DR-BQCOM-022`；只把 qualified 的内存标识交给后续独立 candidate-03 准备，历史失败候选保持只读 | 阻塞 candidate-03 准备；不阻塞本地查询或既有 Provider |
| `RISK-BQCOM-013` | 资格恢复证据不完整 | 仅检查两个模型字段，或数据库/detail发生在journal之前 | codec/user projection仍失败，或再次无法判定detail次数 | 重复消耗一次真实资格机会，错误解锁candidate-03 | `DR-BQCOM-023` 固定codec/user-result/egress全链条件、请求前fsync、精确0/1和有限失败结果；prepared manifest绑定14项历史，正式执行须新授权 | 未满足时`GATE-049`与candidate-03保持Open；不影响生产查询 |
| `RISK-BQCOM-014` | 聚合诊断泄露或被误当作资格结论 | SQL返回原始列/多行、evidence含字段值，或完整计数被直接用于解锁后继 | 员工数据泄露、绕过detail/egress真实校验、重复消耗门禁 | `DR-BQCOM-024` 固定单行整数聚合、strict Schema、禁止列源码反证和历史哈希；诊断只定位首零条件 | 完整计数为0时停止；即使大于0也必须另行设计/授权新资格candidate |
| `RISK-BQCOM-015` | 静态来源诊断过度归因 | 把映射一致等同物理列已知，或把仓库无初始化资产等同990条全部NULL | 误改生产代码/数据并错误重启资格流程 | `DR-BQCOM-025`和strict evidence分离mapping排除、data provenance gap、physical definition unknown与raw distribution unknown | 后续元数据/整数聚合或数据修复必须单独授权；当前不关闭任何门禁 |
| `RISK-BQCOM-016` | 两查询分类或快照失真 | 控制字符与bidi重复计数，或总数/有效数已变化仍沿用990/0 | 查询执行时分类不互斥或数据已漂移 | 形成伪根因并错误修复数据/准备candidate | `DR-BQCOM-026`固定互斥优先级、分类和不变量及`source_snapshot_mismatch`失败关闭；证据只存元数据和整数 | 查询各一次且禁止自动重跑；不关闭`GATE-049` |
| `RISK-BQCOM-017` | synthetic fixture 误伤既有数据或残留 | 仅凭动态SQL假定四字段可插入、按标识宽删，或忽略外键/CHECK/触发器和崩溃恢复 | 写入失败、覆盖/删除既有员工或遗留测试行 | `DR-BQCOM-027`要求先关闭`GATE-050`，再以确定性synthetic标识、完整fingerprint、precheck、精确0/1计数、耐久journal和cleanup-required终态实施 | 元数据前置已满足；仅解锁fake repository与非live验证，真实写删仍禁止 |
| `RISK-BQCOM-018` | 元数据查询字符排序规则漂移 | 对 `information_schema` 的 schema/table 名使用隐式 collation 比较，或失败后继续执行余下查询 | 元数据候选在约束阶段失败、查询预算不可审计，或把部分列证据误判为完整物理契约 | `DR-BQCOM-028`固定顺序、started/terminal计数、失败即停和不可变有限 evidence；candidate-02使用显式 binary/collation-neutral 名称比较并形成完整结果 | run-01历史保持失败；candidate-02已关闭当前缺口 |
| `RISK-BQCOM-019` | prepared候选被误当作数据库执行授权 | manifest/auth冻结后直接设置live开关，或把prepared通过误作门禁关闭 | 未经确认访问数据库，或在无完整物理证据时实现fixture | `DR-BQCOM-029`固定manifest/auth为prepared/live=false，launcher要求精确SHA与进程级开关；candidate-02现已按目标授权一次性消费并形成严格证据 | 本run风险已解除且不可复用；未来候选仍须独立授权 |
| `RISK-BQCOM-020` | prepared测试与已消费证据互相否定 | 运行后继续断言lifecycle/result不存在，或修改manifest绑定asset后以当前文件重算prepared状态 | 回归假失败、授权快照丢失或历史不可重放 | `DR-BQCOM-030`以冻结commit验证prepared blob，以当前只读测试验证append-only结果 | 已通过post-consumption闭环解除 |
| `RISK-BQCOM-021` | Transaction通用问题或结果字段越界 | allow规则使用substring、问题含具体值/额外子句，或candidate把交易ID、provider coverage计数/总量、原始响应写入模型/证据 | 敏感查询意图与真实交易数据共同出域，或形成聚合误导 | `question-egress-v2` exact allow且deny优先；`DR-BQCOM-032`固定type/amount、single-row、仅保留`coverage.truncated`安全布尔、strict evidence、model spy和零调用矩阵 | 未通过`VAL-BQCOM-020`不得申请`GATE-026` |
| `RISK-BQCOM-022` | 资格与fixture生命周期割裂 | 先执行create/cleanup再运行旧资格probe，或detail失败时跳过cleanup | 资格输入消失、遗留synthetic记录或误关闭`GATE-049` | `DR-BQCOM-033`固定同一run、首SQL前journal、INSERT后finally exact cleanup与`failed_cleanup_required`优先级；历史run只读 | 未通过`VAL-BQCOM-021`不得申请新`GATE-049` |
| `RISK-BQCOM-023` | Spring上下文选择歧义造成首SQL前证据空窗 | 测试包存在多个嵌套`@SpringBootConfiguration`且live test依赖自动发现 | Maven失败但无lifecycle/result，无法审计是否发生数据库动作并诱发原run重试 | `DR-BQCOM-034`显式绑定生产启动类，launcher在Maven前持久化host journal并有限化上下文失败；Java SQL lifecycle出现后仍以原cleanup链为权威 | candidate-03只读归档；candidate-04已完成`VAL-BQCOM-022`并唯一执行，当前结果转由`RISK-BQCOM-024/VAL-BQCOM-023`约束 |
| `RISK-BQCOM-024` | live writer与冻结validator接受的生命周期语言不一致 | fake路径写入`host_validation started/succeeded`，live finalizer只写terminal，且finalizer未在落盘result前调用完整lifecycle validator | 业务执行成功但门禁证据无法由自身契约重放，可能诱发放宽校验、追认或重复外部动作 | `DR-BQCOM-035`固定candidate-04三项证据和validator拒绝反证；禁止改写历史或重跑，未来candidate须在non-live使用真实finalizer输出并由同一validator通过 | `GATE-049`保持Open；全新candidate设计与执行分别重新授权 |
| `RISK-BQCOM-025` | candidate-05再次只验证fake手工序列而未验证live finalizer | direct fake执行通过，但launcher实际调用的finalizer仍写出不同事件或在validator前落盘result | 第二次消耗数据库/detail机会后仍无法关闭门禁 | `DR-BQCOM-036`要求测试直接调用launcher同一`finalize_live_candidate`，覆盖成功/host失败/log leak，并断言validator先于result；manifest冻结该函数及测试hash | 未通过`VAL-BQCOM-024`不得冻结或申请`GATE-049` |
| `RISK-BQCOM-026` | 跨语言容器基数与具体键集合分离校验 | Python固定四键但Java只检查错误size，或测试只搜索outer size token而漏检nested codec | 合格响应被误拒，浪费一次性SQL/detail授权；若反向放宽则可能接纳未知字段 | `DR-BQCOM-037`要求size=4、四个具体boolean键和Python exact key set同时验证；candidate-05证据不可改写，candidate-06独立冻结 | 未通过`VAL-BQCOM-025`不得申请candidate-06 `GATE-049` |
| `RISK-BQCOM-027` | fixture、模型授权与cleanup分属不同run或不同证据权威 | 先创建并清理fixture再调用旧egress runner，或Python模型完成后Java cleanup失败却先写passed | 候选输入消失、遗留synthetic记录、错误关闭出域门禁或无法判断授权消费 | `DR-BQCOM-038`固定单一run、跨语言单journal、首outbound marker、INSERT后finally cleanup及result前同validator；prepared阶段以live同路finalizer和故障注入反证 | 未通过`VAL-BQCOM-026`不得冻结或申请`GATE-024` |
| `RISK-BQCOM-028` | 模型可见引用契约弱于本地grounding | 模型只返回`used_fact_ids`数组但answer正文无行内marker | 结构解析通过而30/30被grounding拒绝，付费调用无有效结果 | answer v2明确marker与ID集合一致；validator不放宽；组合根唯一v2；旧candidate退役并重新冻结 | `GATE-053/054/055` |
| `RISK-BQCOM-029` | 测试launcher依赖调用者偶然提供Python导入路径 | 子进程在pytest collection前无法导入`agent_runtime`，但数据库选择或其他一次性预算已先消耗 | 无正式lifecycle/result，run不可复用且外部预算浪费 | versioned host preflight先耐久记录并校验模块来源，失败时database/search/model=0；新候选绑定旧失败证据，禁止原地重跑 | `GATE-056/026` |
| `RISK-BQCOM-030` | 禁止字面量扫描与获准模型字段值重叠 | live harness把type/amount值既写入safe payload又列为forbidden literal | 第一次delegate前自拒绝，浪费SELECT/search授权且无法验证真实模型 | `DR-BQCOM-041`分离exact字段白名单与秘密/非模型字段值扫描；live同源fake必须同时证明允许值通过和禁止值拒绝 | candidate-03只读失败历史；未通过`VAL-BQCOM-036`不得申请新`GATE-026` |
| `RISK-BQCOM-031` | candidate外部bootstrap未冻结或与门禁语义混合 | 临时脚本误解析配置、启动错误进程、读取secret后才建证据，或把一次性授权门禁同时当作成功门禁 | candidate前失败无稳定证据、旧run/授权反复开关、误停维护者服务或错误宣布域出域完成 | `DR-BQCOM-042`以versioned wrapper、pre-side-effect lifecycle、PID归属、有限failure和inner/outer单一权威拆分；`GATE-024/026`只作为精确一次性执行入口，`GATE-033/034`作为完成门禁 | `GATE-058/059`未关闭前不得冻结wrapper；入口失败不得改判candidate或重开同一执行授权 |
| `RISK-BQCOM-032` | wrapper源码冻结但实际JAR与失败原因不可追溯 | target JAR由更早构建产生，或auth启动立即退出而原始日志删除后只剩`process_exited` | 无法证明运行代码身份，维护者只能猜测并重复消耗一次性授权 | `DR-BQCOM-043`绑定JAR SHA/源码commit/构建命令，并在原日志删除前输出严格有限诊断枚举；unknown失败关闭且不得重跑旧wrapper | wrapper-v1已退役；未通过`VAL-BQCOM-038`不得申请新live入口 |
| `RISK-BQCOM-033` | 未执行的Employee wrapper-v1沿用已暴露缺口的共享auth启动边界 | 直接以旧wrapper关闭`GATE-024`，auth在candidate前退出且无JAR身份或有限诊断 | 浪费一次性Employee授权，仍无法区分构建、配置、端口、依赖或上下文问题 | `DR-BQCOM-044`要求Employee独立v2复用公共JAR/diagnostic能力并冻结v1 prepared历史 | `GATE-062`关闭前不得关闭或执行`GATE-024` |
| `RISK-BQCOM-034` | non-live测试只分别验证manifest与操作类，未覆盖executor创建journal后调用preflight的组合顺序 | 直接执行wrapper-v2时，本次合法lifecycle被误判为已有输出 | candidate前稳定失败，无法进入auth/Employee/model链路；若删除输出检查则又会引入重放风险 | `DR-BQCOM-045`要求新wrapper同时保留run前全输出检查、journal exclusive-create与phase内其余输出检查，并增加真实组合路径fake测试 | `GATE-063`关闭前不得创建或执行新的`GATE-024`绑定 |

### 16.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威来源 | 责任方 | 最晚阶段 | 验证者与方法 | 状态 | 未关闭时允许/禁止动作 | 模拟或替代路径 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BQ-GATE-001` | design_decomposition | L1_02→本文 | 编写本文 | L1_02 v0.2 五轮评审通过 | L1_02 14.2 | 项目维护者/独立评审方 | 本文前 | 核对评审记录 | Closed | 允许本文；不授权代码 | 不适用 |
| `BQ-GATE-002` | slice_implementation | 本文 business common 代码/测试切片 | 创建 common contracts/settings/client/projection/grounding/ExactDecimal wire 代码和测试 | 本文独立评审可实施；直接依赖稳定；用户明确实施授权 | 本文评审与追踪、`P3_00` 与本地测试/代码对照设计评审证据 | 项目维护者 | P3 common 实施前 | 核对授权、fake-domain 边界、测试和代码对照设计评审 | Closed | 本地 common 切片可维护；Provider、真实业务和模型出域仍禁止 | 合成纯函数/fake domain |
| `CR-GATE-003` | integration | 业务敏感问题进入 DeepSeek | 发送具体身份/交易/账户问题 | L2_00_02 输入策略及 12.3 全部零调用场景通过 | 模型 L2/Provider spy、`TEST/VAL-BQCOM-013/007` | 项目维护者/模型方 | 首次敏感问题联调前 | 负向测试 | Closed（2026-08-12；仅问题输入安全前置） | 具体敏感/unknown问题继续失败关闭；Employee/Transaction本地Resolver继续不向模型发送问题；不授权真实业务结果出域 | generic synthetic question；本地有限 Resolver |
| `SA-GATE-004` | integration | Employee 真实动作 | 启用 Employee | 动作/接口/字段确认；Authority、ADMIN/VIEWER、响应可见性和契约测试通过 | `L2_02_01`、Employee 受控真实联调及 Gateway 日志 evidence | 项目维护者/提供方 | Employee P4 | 跨服务矩阵 | Closed（2026-08-06） | 允许受控目标配置启用；默认/生产启用、正式 Gateway 路由和模型出域仍禁止 | 已验证的 opt-in Employee provider |
| `SA-GATE-005` | integration | Transaction 真实动作 | 启用 Transaction | 动作/接口/字段确认；Authority、ADMIN/VIEWER、JSON number→BigDecimal→数据库精确比较、聚合写入不可达和契约测试通过 | `L2_02_02`、`wp-txn-real-01-20260806T134518Z.json`、独立代码对照设计复核 | 项目维护者/提供方 | Transaction P4 | 真实允许/拒绝、精确金额、可见性、禁止接口、调用计数和日志零泄漏矩阵 | Closed（2026-08-06） | 允许受控目标配置启用；默认/生产启用和模型出域仍禁止 | 已验证的 opt-in Transaction provider |
| `SA-GATE-006.EMPLOYEE` | security/integration | Employee真实结果进入外部模型 | 常规外发 Employee 数据 | 未来新实验须重新证明字段交集、facts/grounding、零调用负向、零泄漏并取得新鲜精确授权 | Employee/Common/Model L2及未来独立 evidence | 项目维护者/Employee/模型方 | Employee真实结果外发前 | 当前真实Provider查询已验证；外发实验Deferred | Open | 禁止真实Employee载荷外发；允许真实Provider + stub模型系统E2E；不依赖当前P3 N/A门禁 | synthetic safe payload |
| `SA-GATE-006.TRANSACTION` | security/integration | Transaction真实结果进入外部模型 | 常规外发 Transaction 数据 | 未来新实验须重新证明字段/Decimal/facts/grounding/无聚合越界、零泄漏并取得新鲜精确授权 | Transaction/Common/Model L2及未来独立 evidence | 项目维护者/Transaction/模型方 | Transaction真实结果外发前 | 当前真实Provider查询与精确金额已验证；外发实验Deferred | Open | 禁止真实Transaction载荷外发；允许真实Provider + stub模型系统E2E；不依赖当前P3 N/A门禁 | synthetic safe payload |

### 16.3 需要后续授权的动作

- 扩大已完成 Business common 切片或改变共享/公开契约。
- 修改 `auth-service`、`common-security`、Employee/Transaction Java 类、配置、测试或公共契约。
- 确认并实现两个域精确动作、字段、端点及角色方法授权。
- 超出已完成 `WP-TXN-REAL-01` evidence 范围的新增真实调用，或使用真实用户 JWT/业务数据进行其他域、默认/生产启用及外部模型联调。
- 修改任何冻结candidate/wrapper/Schema/launcher/manifest/authorization或历史证据，或复用已退役的一次性执行门禁；历史资产只允许只读审计。
- `GATE-049/050/051/053/054/057/060`均为历史已关闭门禁；`GATE-024/033/034/061/063`在当前周期为Not Applicable，不能授予执行权。未来恢复任一真实业务结果外发实验，必须先诊断并以全新工作包、按需要建立的新有界门禁、run/authorization和预算重新授权；优先复用通用受控harness，完成结论仍由对应域`SA-GATE-006`判定。

## 17. 内部自检记录

| 日期 | 检查范围 | 结论 |
|---|---|---|
| 2026-08-20 | 现行权威、稳定标识、追踪矩阵、门禁与历史迁移完整性 | 物理瘦身不改变设计语义、Approved 状态、实施边界或门禁结论；完整逐轮记录见历史审计文档 |

## 18. 独立正式评审记录

- 本文既有独立正式评审通过结论保持不变；本次仅进行非语义的文档分层与物理瘦身，不据此重新授予批准状态。
- 完整逐轮发现、修复和代码对照设计复核记录见 [`L2_02_00` 历史审计记录](history/L2_02_00_BUSINESS_QUERY_AUDIT_HISTORY.md)。
## 19. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] 公共类型不含 Employee/Transaction 精确字段、端点或业务规则。
- [x] 动作 definition、配置维度、最小有效用户结果和状态语义明确。
- [x] JWT 原样透传、零服务身份兜底、Authority 消费和业务最终授权边界明确。
- [x] 用户/模型字段交集、六个转换、facts envelope 和 grounding 明确。
- [x] Python 模块、关键函数、输入输出、错误、副作用和消费者明确。
- [x] Java 当前类/方法触点与本文不修改边界明确。
- [x] 配置默认值、上限、启动失败、冻结和回滚明确。
- [x] 权限、安全、审计、取消、无重试/无持久化和外部门禁明确。
- [x] 作者自检无遗留 Blocker/Major。
- [x] `validate_detailed_design.py --strict` 已通过；该结果仅是确定性文档证据。
- [x] v0.3 五轮独立正式评审及第三批聚焦一致性复核已关闭全部历史 S0/S1/S2。
- [x] v0.4 精确十进制共享契约完成两轮独立复评，`REV-BQCOM-023`～`025` 全部关闭。
- [x] Employee GET/no-body、Transaction 金额请求和 Core JSON 边界定向兼容检查完成。
- [x] 用户已授权本地 Business common 切片并在测试、代码对照设计评审后关闭 `BQ-GATE-002`。
- [x] Transaction 受控真实 JWT、最终授权、精确金额、可见性、禁止接口和日志证据已通过独立代码对照设计复核，`SA-GATE-005` 已关闭；common 契约未扩大。
- [x] v0.6 已把 Resolver 所有权限定为域、公共层限定为绑定/投影、Core 限定为裁决，且未扩大最终执行候选或业务 Provider 契约。
- [x] v0.6 完成 `AR-HYBRID-01～03` 与 `FR-HYBRID-01～05`，新增发现全部关闭。
- [x] `IMPL-BQCOM-016/017`、`TEST-BQCOM-015/016` 与 `VAL-BQCOM-006` 已完成；本地 Resolver 命中时 selector/model/HTTP 为零，公共层未吸收域语法。
- [x] candidate-01 manifest/authorization/环境诊断/pre-model failure 四项历史哈希已冻结；其 pre-model 失败不构成 GATE-024 通过证据，禁止补跑/续跑或原地改写。
- [x] candidate-02 已完成 `DR-BQCOM-021/IMPL-BQCOM-018/TEST-BQCOM-017/VAL-BQCOM-008` 非 live 实施与代码对照设计复核；新 run/manifest/authorization 已冻结，未创建 consumed/result 或执行 live。
- [x] `DR-BQCOM-023/IMPL-BQCOM-020/TEST-BQCOM-019/VAL-BQCOM-010` 的资格 candidate-02 非 live 准备及随后不可变运行证据均已形成；run 已消费且不得重跑。
- [x] candidate-02 以 `not_qualified/employee.no_qualified_input` 结束，`GATE-049`仍Open；`DR-BQCOM-024`的单次聚合诊断已确认`work_base_si`为首个归零条件，不得仅凭该诊断准备candidate-03。
- [x] `DR-BQCOM-025/IMPL-BQCOM-022/TEST-BQCOM-021/VAL-BQCOM-012` 已完成静态来源诊断、strict evidence、非live回归和代码复核；只排除读取映射并确认数据来源缺口，物理列/原始值分布保持未知。
- [x] `DR-BQCOM-026/IMPL-BQCOM-023/TEST-BQCOM-022/VAL-BQCOM-013` 已以元数据/聚合各1次完成只读诊断，strict evidence证明`WORK_BASE_SI`为可空`longtext`且990条全部NULL；没有修改数据或解锁资格门禁。
- [x] `REQ/CON/DR-BQCOM-018/027` 已完成静态前置复核；确认物理表约束不足以支撑安全 fixture 实施，并在创建 fake repository/Schema/test 前失败关闭。
- [x] `DR-BQCOM-028/IMPL-BQCOM-025/TEST-BQCOM-024/VAL-BQCOM-015` 已形成严格只读探针和不可变失败证据；run-01在第2条查询失败后停止且无重试/追加查询。
- [x] `DR-BQCOM-029/IMPL-BQCOM-026/TEST-BQCOM-025/VAL-BQCOM-016` 已完成独立candidate-02非live准备、历史绑定、binary SQL、耐久lifecycle、fake故障与冻结校验；未访问数据库。
- [x] `DR-BQCOM-030/IMPL-BQCOM-027/TEST-BQCOM-026/VAL-BQCOM-017` 已完成post-consumption双快照、证据hash、metadata/safety和持续回归闭环。
- [x] `GATE-050` 已关闭；完整四查询证明当前表58列、InnoDB且无键/FK/CHECK/trigger，`IMPL-BQCOM-024/TEST-BQCOM-023`可恢复非live实施。
- [x] `DR-BQCOM-027/IMPL-BQCOM-024/TEST-BQCOM-023/VAL-BQCOM-018` 已完成fixture spec、repository Protocol/in-memory fake、strict lifecycle/evidence、故障注入与精确cleanup的non-live闭环。
- [x] `DR-BQCOM-031/IMPL-BQCOM-028/TEST-BQCOM-027/VAL-BQCOM-019` 已完成一次性真实create/verify/exact cleanup与post-consumption历史闭环；`GATE-051`关闭，run已消费且不可重放。
- [x] `DR-BQCOM-032/IMPL-BQCOM-029/TEST-BQCOM-028/VAL-BQCOM-020` 已完成non-live实施、冻结与代码对照设计复核；只允许申请`GATE-026`，不得据此执行live。
- [x] `DR-BQCOM-033/IMPL-BQCOM-030/TEST-BQCOM-029/VAL-BQCOM-021` 已完成candidate-03 non-live实施、三轮代码复核、冻结和全量回归；正式SQL/JWT/detail及`GATE-049`均未执行。
- [x] candidate-03首SQL前Spring配置歧义失败已以精确SHA-256有限证据归档；数据库/detail/model均0且run不可复用。
- [x] `DR-BQCOM-034/IMPL-BQCOM-031/TEST-BQCOM-030/VAL-BQCOM-022` candidate-04 non-live实现、冻结与三轮代码对照设计复核已完成；正式live仍受`GATE-049`阻断。
- [x] `DR-BQCOM-035/IMPL-BQCOM-032/TEST-BQCOM-031/VAL-BQCOM-023` 已固定candidate-04唯一live的业务成功、exact cleanup、三项证据哈希和冻结validator拒绝反证；run不可复用。
- [x] `DR-BQCOM-036` 已把candidate-05的live同路finalizer、validator前置、17项历史绑定、实现触点和测试反证设计到可实施粒度。
- [x] `CR-BQCOM-QUAL-001` 已由`IMPL-BQCOM-033/TEST-BQCOM-032/VAL-BQCOM-024`关闭：live同路finalizer三分支、16条validator、invalid无result、17项history和12项asset冻结均已通过；`GATE-049`继续Open。
- [x] candidate-05唯一live失败已由`TEST-BQCOM-033/VAL-BQCOM-025`按精确SHA归档；完整cleanup不改变`employee_result_invalid`失败结论，run不可复用。
- [x] `DR-BQCOM-037/IMPL-BQCOM-034/TEST-BQCOM-033/VAL-BQCOM-025`已完成candidate-06四键基数修复、23项历史/12项asset冻结、唯一live、五项SHA锁定与聚焦复核；`GATE-049`已关闭。
- [x] `DR-BQCOM-038/IMPL-BQCOM-035/TEST-BQCOM-034/VAL-BQCOM-026`已完成candidate-03统一journal、五Schema、Java/Python/launcher同路finalizer、17项历史/28项asset冻结与三轮内审；`GATE-052`关闭，未执行`GATE-024`。
- [x] `DR-BQCOM-039/IMPL-BQCOM-036/TEST-BQCOM-035/VAL-BQCOM-027`已完成answer v2、Employee candidate-04与Transaction candidate-02 non-live验证；`GATE-053/054/055`关闭，两域live仍须另行精确授权。
- [x] Transaction candidate-02初始化失败已以SHA-256=`37c4cf079cf1bb28e17c9b087df5707bf19c5bbfd8318d6c3f5f611f08fd72d9`有限证据归档；一次类型SELECT已使用，search/model=0且run不可重跑。
- [x] `DR-BQCOM-040/IMPL-BQCOM-037/TEST-BQCOM-036/VAL-BQCOM-035`已完成candidate-03 host/collection preflight、四份strict Schema、8项history/33项asset冻结和代码对照设计复核；`GATE-056`关闭，但不得直接执行`GATE-026`。
- [x] candidate-03唯一执行已按四项新证据SHA归档为`failed_unconsumed/model_call_failed`，SELECT1/search1、answer0、retry/resume0且consumed不存在；run不得重跑。
- [x] `REQ/CON/DR-BQCOM-029/029/041`已通过聚焦评审；只允许在全新candidate-04中修正test-only允许值/禁止字面量分类，不改变生产字段、payload、validator、grounding或公开契约。
- [x] `DR-BQCOM-041/IMPL-BQCOM-038/TEST-BQCOM-037/VAL-BQCOM-036`已完成candidate-04 test-only non-live实现、15项history/33项asset冻结、全量回归与代码对照设计复核；`GATE-057`关闭，`GATE-026`保持Open。
- [x] `REQ/CON/DR-BQCOM-030/030/042`已把candidate外部启动环境纳入versioned wrapper，明确outer/inner单一权威、入口/完成门禁拆分和秘密/PID/日志边界。
- [x] `IMPL-BQCOM-039/TEST-BQCOM-038/VAL-BQCOM-037`已完成non-live实现、两步冻结、全量回归与代码对照设计复核；当前外部调用为0。
- [x] Transaction wrapper-v1唯一执行已以精确SHA归档，candidate未调用、inner输出不存在、SELECT/search/model为0；旧run和`GATE-026`授权不可复用。
- [x] `REQ/CON/DR-BQCOM-031/031/043`已完成聚焦设计与评审，wrapper-v2只增加双JAR provenance和有限诊断，生产契约与candidate-04保持不变。
- [x] `IMPL-BQCOM-040/TEST-BQCOM-039/VAL-BQCOM-038`已完成独立wrapper-v2 non-live实现、确定性构建、双JAR/源码/历史冻结、回归及代码对照设计复核；`GATE-060`关闭，正式输出仍不存在。
- [x] `REQ/CON/DR-BQCOM-032/032/044`已完成Employee wrapper-v1风险审计、三轮内审与聚焦评审。
- [x] `IMPL-BQCOM-041/TEST-BQCOM-040/VAL-BQCOM-039`已完成Employee wrapper-v2 non-live实现、两步冻结、全量回归和代码对照设计复核；共享Transaction v2资产无漂移，`GATE-062`关闭。
- [x] wrapper-v2唯一失败已按outer lifecycle/result精确SHA归档，candidate/SQL/Employee/model为0，原始日志与自有进程清理通过；run不得重跑。
- [ ] `DR-BQCOM-045/IMPL-BQCOM-042/TEST-BQCOM-041/VAL-BQCOM-040`尚未实施并转为 Deferred；其历史缺口不阻塞当前 Provider + stub 系统 E2E。恢复该可选实验时必须重新立项、授权和建立新门禁，不得复用当前记为 Not Applicable 的 `GATE-063/024`。
- [x] `DR-BQCOM-046` 已完成门禁治理收敛：执行许可、实验验收与工作包状态分离；P3 当前无 Open 门禁，两个 scoped `SA-GATE-006` 继续失败关闭真实业务结果外发。

## 20. 当前结论

- 本文版本：v0.56。
- 文档状态：Approved。
- 评审状态：历史 Employee/Transaction 评审、run/manifest/authorization/evidence 及失败结论全部保持；v0.56 已完成当前交付周期门禁治理收敛，未改动生产 Business/Core/API 或历史资产。
- 实施状态：candidate-06资格证据继续关闭`GATE-049`；Employee wrapper-v2唯一run仍以`failed_pre_candidate_unconsumed/asset_hash_invalid`归档。Employee wrapper-v3修复与两域真实模型出域转 Deferred；P3 `GATE-024/033/034/061/063`为Not Applicable。`SA-GATE-006.EMPLOYEE/TRANSACTION`保持Open并继续禁止真实业务结果外发。
- 生效状态：未生效。
- 是否可作为实现依据：按范围可用；当前可据此执行真实 Provider + 默认 stub 模型的系统 E2E。任何真实 Employee/Transaction 结果外部模型实验均须未来独立重开设计、门禁和精确授权。
- 当前规范权威为需求/约束/决策、当前门禁表和本节结论；修订历史、评审记录及candidate/wrapper运行章节仅作不可变审计轨迹，不得覆盖当前Not Applicable/Deferred状态或直接生成后继执行路径。
- 确定性文档校验：已通过，0 errors、0 warnings；不替代独立正式评审或外部权限证据。
- 当前已证明 Adapter/Provider 的字段、权限、Decimal、失败和默认拒绝边界；历史 wrapper/candidate 的生命周期事实继续有效但不再构成当前 P3/P4 交付依赖。不能复用任何历史 wrapper run、SQL、领域调用或授权；系统 E2E 必须保持默认 stub 模型和真实业务数据 outbound=0。
