# [L2_02_01] 单体 Agent Employee Adapter 与业务授权联调详细设计 L2

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Employee Adapter 与业务授权联调详细设计 |
| 文档标识 | `SA-L2-EMPLOYEE-ADAPTER-001` |
| 文档编号 | `L2_02_01` |
| 文档路径 | `docs/design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 历史评审、资格、candidate/wrapper 与失败证据保持不可变；v0.51 完成现行权威与历史审计的物理分层，不改变 Employee 真实 Provider + stub 模型系统 E2E 与可选真实结果外部模型实验的既有边界 |
| 当前版本 | v0.51 |
| 日期 | 2026-08-20 |
| 适用范围 | Python `agent-employee-adapter` 的 `employee.detail` 单动作、本地确定性参数 Resolver、现有 Employee 详情接口映射、参数/响应/字段收紧、业务服务最终角色授权、错误映射、模型字段候选，以及 Gateway/Servlet 日志安全联调门禁 |
| 上位文档 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.5 Approved |
| 直接输入 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v0.57 Approved；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v0.23 Approved；[`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.11 Approved；[`L2_00_03`](L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) v0.4 Approved |
| 外部契约 | `employee-service` `GET /employees/{idCardNo}`；`auth-service/common-security` 用户 JWT/Authority |
| 实现基线 | 既有生产 Adapter、Authority、Provider、Resolver 及真实动作证据均不变；Employee 输入资格的最终受控验证已通过，生产 Python/Java/Gateway/API/数据未改变。精确 run、manifest 与 evidence 哈希见[历史审计记录](history/L2_02_01_EMPLOYEE_ADAPTER_AUDIT_HISTORY.md) |
| 是否可作为实现依据 | 按范围可用 |
| 实施依据说明 | Python Adapter 切片已关闭 `BQ-GATE-002`；维护者已确认复用详情端点、ADMIN/VIEWER 完整响应可见性与仓库内调用方范围，共享 Converter、Employee Provider、真实 JWT 矩阵和 Gateway/Servlet 日志安全证据均已通过，按范围关闭 `BQ-GATE-003/SA-GATE-004`。该结论不关闭问题或结果模型出域门禁，也不等于默认启用或生产生效 |
| 当前允许实施范围 | 只读维护既有 Adapter/Provider 与历史审计资产；当前系统 E2E 已调用通过验证的 Employee Provider，并固定使用默认 stub 模型。wrapper-v3 修复与真实 Employee 结果外部模型实验转为 Deferred |
| 当前禁止动作 | 改写或复用 candidate-01/02；以 Agent 投影替代业务服务授权；扩大公开接口/角色/DTO；新增正式 Gateway 路由；读取 `LLM_API_KEY`、调用 DeepSeek；持久化员工标识/JWT/字段值/原始响应/完整 path 或保留原始联调日志 |
| 修改权限 | 本轮仅授权设计与计划 Markdown 原子同步；未授权 wrapper-v3 代码、测试资产、服务/SQL/Employee/DeepSeek 调用或 Git 提交推送 |

> 第一阶段只设计 `employee.detail`。本地 Provider 切片已确认 ADMIN/VIEWER 完整响应可见性并复用现有详情接口，Adapter 仍只显式摘取六个许可字段。分页、计数、ES 搜索、聚合、变更申请和全部写/管理入口不注册。Provider 本地验证本身不等于真实动作启用；后续 `SA-GATE-004` 关闭只允许受控目标配置，仍不代表默认/生产启用，字段投影也不能替代 `employee-service` 的最终角色授权。

## 2. 修改历史

> 完整修改历史已迁移至 [L2_02_01 历史审计记录](history/L2_02_01_EMPLOYEE_ADAPTER_AUDIT_HISTORY.md)；历史文档只作审计，不覆盖本文当前权威。

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-08-20 | 文档治理、历史与评审章节 | 对现行文档执行物理瘦身 | 更新为 v0.51；完整历史与逐轮记录迁移到只读审计附件；稳定标识、设计语义、当前门禁、状态和结论不变 |

## 3. 背景、目标与范围

### 3.1 背景与根因

Provider 改造前，`EmployeeController` 同时公开分页、详情、数量、变更和删除能力，详情直接返回包含身份证、联系方式、地址、银行账户和亲属信息的完整实体，Resource Server 只要求 authenticated，详情方法也未执行动作级角色守卫。当前实现已为详情入口增加 endpoint-scoped 安全链和 Guard；Adapter 仍必须显式投影，避免把宽响应反射或透传到能力结果。

### 3.2 目标与可观察行为

| 需求编号 | 目标 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-EMP-001` | 只提供一个代码绑定详情动作 | registry 仅有 `employee.detail@1`；所有其他 Employee 路径调用数为零 | L1_02 6/7；L2_02_00 `DR-BQCOM-001` |
| `REQ-EMP-002` | 强类型标识映射到现有详情接口 | 输入不接受 URL、字段、分页、排序或 DSL；相对路径由 codec 唯一生成 | REQ_00 FR-03；接口优先复用 |
| `REQ-EMP-003` | 业务服务最终验证角色 | ADMIN/VIEWER 允许；认证失败 401；缺失/未知/混合非法 role 在统一安全边界 403，业务详情方法为零；有效 Authority 仍由 Employee 入口作动作级允许判断 | 用户确认；L1_02 7.4 |
| `REQ-EMP-004` | 宽响应只形成最小用户结果 | 账户、地址、电话、私人邮箱、亲属、生日等字段进入用户/模型结果次数为零 | L1_02 7.5/7.6 |
| `REQ-EMP-005` | 用户结果与模型结果分离 | 用户结果最多六字段；模型代码候选仅职位/工作地，配置和全局规则默认拒绝 | L2_02_00 9/11 |
| `REQ-EMP-006` | 现有状态语义不被猜测 | 当前 400 固定为 invalid_argument；不能把 `Employee not found` 文本解析成 no-result | L2_02_00 8.5/12.1 |
| `REQ-EMP-007` | 一次有界只读调用 | 每次最多一条 GET，无 retry/redirect/service-token，取消或迟到响应不接纳 | L2_02_00 `DR-BQCOM-014` |
| `REQ-EMP-008` | 敏感标识不进入模型或日志 | 原始 idCardNo、JWT、完整 URL、原始响应和异常正文均为零；具体身份问题不通过全局模型输入闸门 | L1_02 10；L2_00_02 |
| `REQ-EMP-009` | Employee 参数由有限本地语法确定性形成 | 匹配详情意图时模型调用为零；恰好提取一个标识并形成 `employee.detail` 候选；缺失、重复、附加子句或格式错误返回 `invalid_argument` 且业务 HTTP 为零 | L0 `SA-C-022`；L1_02 `BQ-AD-011`；L2_00_01 `DR-CORE-015～018` |
| `REQ-EMP-010` | Employee 结果出域候选在 Employee 请求前建立可恢复审计状态 | journal 先于 `employee.detail` 创建；请求 started/terminal 与 transport 调用计数一致；模型前失败为 `failed_unconsumed`，首次 outbound 后失败为 `failed_consumed`；所有可控失败输出有限 evidence，retry/resume=0 | L2_02_00 `REQ-BQCOM-014/DR-BQCOM-021`；用户 2026-08-14 授权 |
| `REQ-EMP-011` | 新候选前先验证真实 Employee 输入能通过完整最小结果链 | 独立资格candidate只读筛选最多一条；SQL覆盖 `idCardNo/chineseName/position/workBaseSi` codec最小条件，一次真实ADMIN detail还须形成 `employee_id_masked/chinese_name` required user result且 `position/work_base_si` egress allowed；有限证据不含业务值 | L2_02_00 `REQ-BQCOM-015/DR-BQCOM-022/023`；candidate-02失败证据 |
| `REQ-EMP-012` | 静态解释990条记录的 `workBaseSi` 有效计数为何为0 | 绑定既有聚合 evidence 哈希；证明 Entity/Mapper/SQL Provider 映射、通用 Map 写入和仓库数据来源现状；有限结论不得替代物理元数据或原始值分布 | L2_02_00 `REQ-BQCOM-016/DR-BQCOM-025`；用户 2026-08-14 授权 |
| `REQ-EMP-013` | 以两条最小只读查询确定 `WORK_BASE_SI` 的物理列定义和无效值分布 | 元数据结果恰好1行且仅六项；数据结果恰好1行且五类互斥计数和等于总数；总数/有效数须与静态evidence 990/0一致，否则失败关闭 | L2_02_00 `REQ-BQCOM-017/DR-BQCOM-026`；用户 2026-08-14 授权 |
| `REQ-EMP-014` | 新资格candidate前准备一条独立、非真实身份、可精确清理的synthetic Employee | 不修改现有990条记录；逻辑最小非空字段为`idCardNo/chineseName/position/workBaseSi`；确定性标识显式synthetic且不呈现真实身份证格式；create/verify/delete各最多1次并由耐久journal和有限evidence约束。物理契约未知时必须在fake实现前失败关闭 | L2_02_00 `REQ-BQCOM-018/DR-BQCOM-027`；用户 2026-08-14 授权 |
| `REQ-EMP-015` | 为synthetic Employee准备一次性真实create/verify/cleanup候选 | candidate绑定已关闭`GATE-050`的metadata历史，只使用测试范围JdbcTemplate和显式事务，固定3次SELECT/1次INSERT/1次DELETE；prepared阶段不得访问数据库，正式执行须精确授权`GATE-051` | L2_02_00 `REQ-BQCOM-019/DR-BQCOM-031` |
| `REQ-EMP-016` | 以全新candidate在同一生命周期完成synthetic fixture、一次真实detail资格判定和精确清理 | 四codec字段、两required user字段及`position/work_base_si` egress必须同时通过；INSERT后所有路径finally清理，deleted=1且remaining=0是除`failed_cleanup_required`外全部终态的必要条件；模型调用为0 | L2_02_00 `REQ-BQCOM-021/DR-BQCOM-033` |
| `REQ-EMP-017` | Spring测试上下文必须唯一、显式且在首SQL前可审计失败 | live test显式绑定`EmployeeServiceApplication`；launcher先写host journal再启动Maven。上下文失败必须形成`failed_unconsumed`有限结果并证明SQL/detail/model均0，已尝试run不得原地修复或重跑 | L2_02_00 `REQ-BQCOM-022/DR-BQCOM-034`；candidate-03 failure evidence |
| `REQ-EMP-018` | 资格live证据必须能被冻结writer/finalizer对应的同一validator完整重放 | `host_validation`等所有非run阶段必须按唯一生命周期语法形成started/terminal；业务字段与cleanup满足但validator拒绝时保持门禁Open，禁止追认、改写证据或复用run | L2_02_00 `REQ-BQCOM-023/DR-BQCOM-035`；candidate-04 post-consumption evidence |
| `REQ-EMP-019` | candidate-05必须在non-live阶段直接验证launcher实际调用的finalizer输出 | finalizer成功、host失败和log leak分支均须成对写`host_validation`，追加run终态后由同一validator通过；任何validator失败不得创建result | L2_02_00 `REQ-BQCOM-024/DR-BQCOM-036` |
| `REQ-EMP-020` | Employee资格staging的`codec`必须以固定四键跨语言一致解码 | Python只输出`idCardNo/chineseName/position/workBaseSi`，Java同时校验object size=4、四键存在且为boolean；未知、缺失或非boolean均拒绝，不得用第五个占位键适配错误实现 | L2_02_00 `REQ-BQCOM-025/DR-BQCOM-037`；candidate-05失败证据 |
| `REQ-EMP-021` | Employee真实结果出域候选必须在同一run中创建非真实fixture、调用一次现有detail、完成30次受控answer并精确清理 | 只复用现有`GET /employees/{idCardNo}`、生产codec/user projection/egress/grounding；模型只见`position/work_base_si`；SQL 3/1/1、detail1、answer30、有效至少27；任何INSERT后路径均deleted=1且remaining=0，否则不得通过 | L2_02_00 `REQ-BQCOM-026/DR-BQCOM-038`；`GATE-049` Closed；`GATE-024` Open |
| `REQ-EMP-022` | Employee后继出域候选必须使用answer v2并重新冻结当前生产组合根 | candidate-04继续只外发`position/work_base_si`、复用3/1/1+detail1+answer30与exact cleanup；manifest必须绑定answer v2源码/task version/新bootstrap及candidate-03五项历史，不得复用旧authorization | `L2_00_02 REQ-MODEL-013`；`L2_02_00 REQ-BQCOM-027` |
| `REQ-EMP-023` | Employee candidate-04外部执行环境必须由独立versioned bootstrap冻结 | bootstrap在读取HMAC/JWT/标识/密钥或启动auth前建立耐久lifecycle，绑定candidate-04 manifest/auth和自身资产；只启动auth并签发内存ADMIN JWT，Employee服务/fixture/detail仍由既有Java candidate宿主；candidate前失败时SQL/detail/model均0且形成有限证据 | `L2_02_00 REQ-BQCOM-030`；`P3_00 GATE-058/024` |
| `REQ-EMP-024` | Employee live入口必须冻结实际auth JAR并在消费`GATE-024`前具备有限启动诊断 | wrapper-v2用全新run/manifest/auth绑定auth JAR SHA、确定性构建命令、源码commit、wrapper-v1 prepared历史和candidate-04；JAR漂移在进程前拒绝，auth提前退出只产生严格有限diagnostic并删除原始日志 | `L2_02_00 REQ-BQCOM-032/DR-BQCOM-044`；Transaction wrapper-v1失败证据 |
| `REQ-EMP-025` | Employee outer必须在保留防重放的同时接受本次executor合法创建的lifecycle | run入口先验证outer/inner输出全不存在；共享journal继续exclusive-create；asset phase只允许当前lifecycle存在，并拒绝outer result/diagnostic、任一inner输出或哈希漂移 | wrapper-v2 outer lifecycle/result与`L2_02_00 REQ-BQCOM-033/DR-BQCOM-045` |
| `REQ-EMP-026` | 当前 Employee 查询能力验收不依赖真实 Employee 结果外部模型稳定性实验 | 系统 E2E 使用真实 `employee.detail` Provider、真实业务授权和默认 stub 模型，Employee 请求与权限/字段/失败链可验证且模型 outbound=0；历史3/1/1+detail1+answer30及27/30阈值只属于冻结实验，不是当前 P3/P4 完成条件 | L1_02 `BQ-AD-012`；L2_02_00 `DR-BQCOM-046` |

### 3.3 范围内

- `employee.detail` descriptor、强类型输入、request mapper/codec/normalizer 和 provider。
- `EmployeeDetailLocalActionResolver` 的有限语法、无匹配/无效裁决、definition 代码绑定和零模型调用测试。
- 详情响应的显式读取字段、用户投影、模型候选、转换和最小有效结果。
- 现有 Employee Controller 上该动作的最终 Authority 校验建议及允许/拒绝联调矩阵。
- 400/401/403/429/5xx、超时、宽响应、缺字段和未知字段的确定映射。
- `GatewaySecurityConfig` 移除完整请求 path 输出，以及只在 opt-in 测试进程中装配的临时 Employee 路由、一次合成 sentinel Gateway→Servlet 请求、日志扫描和有限 evidence。
- synthetic Employee fixture 的逻辑最小字段、确定性非真实标识、单记录create/verify/exact-delete、异常恢复与有限evidence边界；真实表映射须先通过独立元数据门禁。

### 3.4 范围外

- Employee 分页、count、ES 搜索/向量、聚合、创建、更新、删除、审批、索引和重建。
- 新增 Employee 公开接口、修改 not-found 为 404、拆分响应 DTO；如需实施必须另行确认。
- Transaction、Knowledge、统一 role converter 私有实现、DeepSeek Provider 和通用 Prompt。
- Employee 行级/字段级业务规则重写或数据库结构修改。
- 正式 Employee Gateway 路由、默认 Gateway 路由配置、真实员工标识及任何真实 Employee 数据读取。
- 模糊实体识别、LLM 参数抽取、词典/正则配置平台、跨句/多动作 Employee 查询。
- 在`GATE-050`关闭前创建fake/real fixture repository、写入/删除Employee数据、创建新资格candidate或把合成记录保留为初始化/业务数据。

### 3.5 非目标

- 不把完整 `Employee` 复制成 Python DTO，不建设动态字段映射/JSONPath。
- 不在 Adapter 解析 role claim、按用户名放行或使用固定管理员 token。
- 不因当前 400 message 看似“not found”而推导业务无结果。

### 3.6 实施剖面

| 剖面 | 适用 | 说明 |
|---|---|---|
| Python | 是 | Employee definition、DTO、codec、normalizer、provider、配置和测试 |
| Java/API | 是 | 复用现有详情方法；建议最小增加角色 guard 调用，不改 wire DTO |
| 安全 | 是 | 用户 JWT 透传、Authority 最终判定、敏感字段/日志隔离；Gateway 不输出完整请求 path |
| 测试运行 | 是 | 测试进程内临时 Employee 路由、合成 sentinel、一次请求、有限 evidence 与原始日志销毁 |
| 数据库/事务 | 否 | Adapter 只读且不持久化；Employee 查询事务归业务服务 |
| 模型出域 | 条件适用 | 只定义代码候选；全局与动作配置默认拒绝，真实外发不在本门禁内 |

## 4. 上位约束

| 约束编号 | 上位位置 | 约束 | 本设计落实 | 偏离 |
|---|---|---|---|---|
| `CON-EMP-001` | L1_02 6/7.2 | 独立 Adapter、有限动作、配置只收紧 | `DR-EMP-001`、`DR-EMP-002` | 无 |
| `CON-EMP-002` | L1_02 7.3/7.4 | 原用户 JWT 透传、业务服务最终授权 | `DR-EMP-003`、`DR-EMP-004` | 无 |
| `CON-EMP-003` | L1_02 7.5/7.6 | 授权响应后字段交集、最小有效结果、模型默认拒绝 | `DR-EMP-005`、`DR-EMP-006`、`DR-EMP-007` | 无 |
| `CON-EMP-004` | L2_02_00 8.5/12.1 | HTTP 状态由 common mapper 先解释，域 codec 只处理 2xx | `DR-EMP-008` | 无 |
| `CON-EMP-005` | L2_02_00 9/10 | 一次调用、绝对截止、无 retry/服务身份 | `DR-EMP-009`、`DR-EMP-010` | 无 |
| `CON-EMP-006` | L1_02 10.1 | 敏感问题/字段不直接进入外部模型 | `DR-EMP-007`、`DR-EMP-011` | 无 |
| `CON-EMP-007` | L1_02 `BQ-AD-011`；L2_00_01 `DR-CORE-015～018` | 域拥有有限参数语法，Core 拥有多 Resolver 裁决，模型只选能力 ID | `DR-EMP-013` | 无 |
| `CON-EMP-008` | L2_02_00 `CON-BQCOM-014/DR-BQCOM-021`；candidate-01 失败证据 | candidate-01 manifest、authorization、环境诊断、pre-model failure evidence 及精确哈希不可变；未消费不等于允许补跑，后继必须使用独立 candidate-02 资产与新授权 | `DR-EMP-014` | 无 |
| `CON-EMP-009` | L2_02_00 `CON-BQCOM-015/DR-BQCOM-022/023`；candidate-02失败证据 | Employee egress candidate-01/02八项历史和退役资格run六项绑定资产不可变；新资格candidate必须使用全新run并在数据库筛选/detail前exclusive create+fsync lifecycle。non-live准备不得持久化标识/JWT/字段值/原始响应，不得启动服务/数据库/JWT/detail、读取模型密钥或产生outbound | `DR-EMP-015/016` | 无 |
| `CON-EMP-010` | L2_02_00 `CON-BQCOM-016/DR-BQCOM-025`；聚合 evidence | 静态检查不得执行数据库/Employee端点，不得把 ES 重建视为数据库填充来源，也不得把仓库缺少 DDL 推导成列不存在 | `DR-EMP-018` | 无 |
| `CON-EMP-011` | L2_02_00 `CON-BQCOM-017/DR-BQCOM-026`；静态 evidence SHA-256=`7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8` | 最多执行一条元数据和一条单行整数聚合；不返回标识/值/原始行/分组，不调用HTTP/auth/JWT/模型，不修改数据/结构/生产/历史或准备candidate-03 | `DR-EMP-019` | 无 |
| `CON-EMP-012` | L2_02_00 `CON-BQCOM-018/DR-BQCOM-027`；数据诊断 evidence SHA-256=`b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6` | 不得更新、覆盖或借用现有990条记录；物理写入/清理前必须证明Employee全表列定义与表引擎、主键/唯一键、出入向外键、CHECK及trigger。任一未知即停止，不以fake替代真实约束证据 | `DR-EMP-020` | 无；当前`GATE-050`Open |
| `CON-EMP-013` | `GATE-050/GATE-051` Closed；`DR-EMP-020～024` | 不得调用Employee Service/Mapper/API、事件、JWT或模型，不得UPDATE或仅按标识宽DELETE；INSERT开始后无论业务阶段成功或失败均必须exact cleanup。candidate-01已证明deleted=1且remaining=0并消费，禁止重跑/resume | `DR-EMP-024` | 无；历史run不可复用 |
| `CON-EMP-014` | `GATE-051` Closed；旧资格candidate-02及fixture candidate-01历史不可变 | 新candidate必须全新run并复用既有fixture spec和生产Employee definition/handler/projector；不得复制域字段规则、修改Service/API/数据基线或持久化标识/JWT/字段值。non-live阶段不得访问数据库、服务、JWT或模型 | `DR-EMP-025` | `GATE-049/024` Open |
| `CON-EMP-015` | candidate-03 manifest/auth/pre-SQL failure及其历史不可变 | candidate-04 Java test必须导入并显式绑定`com.dylan.employee.EmployeeServiceApplication`；host journal必须在Maven前exclusive-create+fsync。Java SQL lifecycle存在时由原有数据库/cleanup链负责；不存在时只允许生成零SQL/detail/model的有限`failed_unconsumed`结果 | `DR-EMP-026` | `GATE-049/024` Open |
| `CON-EMP-016` | candidate-04 prepared资产、host lifecycle、SQL lifecycle、result及其SHA-256不可变 | candidate-04已消费且不得重跑；其业务资格/cleanup事实保留，但15条SQL lifecycle不能作为门禁关闭证据。未来candidate必须全新版本化并在non-live阶段用live同路finalizer输出通过同一validator | `DR-EMP-027` | `GATE-049/024` Open |
| `CON-EMP-017` | candidate-04五项证据、post-consumption history test及既有十一项历史不可变；Employee生产Adapter/Provider/API、角色、DTO和数据结构不变 | candidate-05只能新增测试范围versioned Python/Schema/launcher/Java disabled资产；schemaVersion 5、3/1/1+detail1+model0和新run固定，history共17项。prepared阶段不得启动服务、访问数据库、签发JWT或调用detail/model | `DR-EMP-028` | `GATE-049/024` Open |
| `CON-EMP-018` | candidate-05 manifest/auth/host/lifecycle/result及post-consumption history test精确哈希不可变；四键生产投影契约不变 | candidate-06只新增schemaVersion6测试范围资产；Java loader基数必须为4且继续逐键/类型严格校验，history共23项。不得修改v5、生产Adapter/Provider/API/DTO/角色/数据，prepared阶段外部调用0 | `DR-EMP-029` | `GATE-049/024` Open |
| `CON-EMP-019` | candidate-06 manifest/auth/host/lifecycle/result五项、旧egress candidate-01/02及全部fixture/metadata历史不可变 | candidate-03只新增versioned test-only Python/Schema/tests/launcher/manifest/auth与Java disabled测试；不得修改生产Adapter/Provider/API/DTO/角色/默认配置或现有990条记录。prepared阶段数据库、服务、JWT、模型、outbound均0；正式live必须另行绑定新run/hash/auth与3/1/1+detail1+answer30预算 | `DR-EMP-030` | `GATE-052`控制prep；`GATE-024/SA-GATE-006/GATE-033` Open |
| `CON-EMP-020` | candidate-03 manifest/auth/lifecycle/consumed/result及answer v1源码不可变；Employee field matrix、facts、grounding、API/角色/数据不变 | 不得修改candidate-03 runner/manifest或将其改绑answer v2。candidate-04已在`GATE-054`下以全新run/manifest/auth准备，prepared阶段数据库/JWT/Employee/DeepSeek=0 | `DR-EMP-031` | `GATE-054` Closed；`GATE-024/SA-GATE-006/GATE-033` Open |
| `CON-EMP-021` | candidate-04 manifest/auth、22项history、31项asset及prepared frozen HEAD不可变 | 新bootstrap不得修改或复制candidate内部fixture/detail/model/cleanup生命周期；HMAC、JWT、synthetic标识和模型密钥只驻留内存，日志只进临时目录并扫描删除；8090被非本次进程占用时失败关闭，不复用、不停止维护者进程，只停止本次启动且PID/进程树归属核实的auth进程 | `DR-EMP-032` | `GATE-058`控制non-live实现；`GATE-024`控制一次性执行；`GATE-033`与`SA-GATE-006[Employee]`控制完成 |
| `CON-EMP-022` | wrapper-v1 manifest/auth/source/history及outer/inner零输出反证不可变；candidate-04保持prepared | wrapper-v1不得执行或原地修改。wrapper-v2须绑定v1 prepared历史、candidate-04、公共v2 helper/Schema、auth JAR/source/build/command；仅启动auth，Employee服务和全部业务副作用仍由inner candidate唯一拥有 | `DR-EMP-033` | `GATE-062`控制v2 non-live冻结；完成后才可更新并关闭`GATE-024` |
| `CON-EMP-023` | wrapper-v2 manifest/auth/source及outer lifecycle/result不可变；candidate-04仍无inner输出 | wrapper-v2虽未调用candidate也不得重跑、续跑、删证据或原地修改。wrapper-v3必须使用全新run/manifest/auth并绑定v2四项历史；共享v1/v2 helper、Transaction资产、candidate-04及生产Employee/API保持只读 | `DR-EMP-034` | `GATE-063`控制non-live修复；完成后才可重新准备`GATE-024` |
| `CON-EMP-024` | L1_02 `BQ-AD-012`；L2_02_00 `DR-BQCOM-046`；P3当前交付周期 | wrapper-v3与真实Employee结果模型实验均转Deferred；P3 `GATE-063/024/033`记为Not Applicable且不得复用。历史run/manifest/authorization/evidence保持字节不变 | `DR-EMP-035` | `SA-GATE-006.EMPLOYEE`保持Open，只禁止真实Employee结果外发，不阻塞Provider + stub系统E2E |

### 4.1 端到端追踪矩阵

| REQ/CON | 设计规则 | 责任主体 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|
| `REQ-EMP-001`,`CON-EMP-001` | `DR-EMP-001`、`DR-EMP-002` | Employee provider/组合根 | `IMPL-EMP-001/002/007` | `TEST-EMP-001/002` | `VAL-EMP-001/002` |
| `REQ-EMP-002` | `DR-EMP-002`、`DR-EMP-010` | mapper/codec | `IMPL-EMP-003` | `TEST-EMP-003` | `VAL-EMP-001` |
| `REQ-EMP-003`,`CON-EMP-002` | `DR-EMP-003`、`DR-EMP-004` | employee-service/安全权威 | `IMPL-EMP-008/009` | `TEST-EMP-004/005` | `VAL-EMP-003/004` |
| `REQ-EMP-004`,`CON-EMP-003` | `DR-EMP-005`、`DR-EMP-006` | decoder/projector | `IMPL-EMP-004/005` | `TEST-EMP-006/007` | `VAL-EMP-001/002` |
| `REQ-EMP-005`,`CON-EMP-006` | `DR-EMP-007`、`DR-EMP-011` | field definition/egress | `IMPL-EMP-005/006` | `TEST-EMP-008/009` | `VAL-EMP-002` |
| `REQ-EMP-006`,`CON-EMP-004` | `DR-EMP-008` | status mapper/normalizer | `IMPL-EMP-004` | `TEST-EMP-010` | `VAL-EMP-001/003` |
| `REQ-EMP-007`,`CON-EMP-005` | `DR-EMP-009`、`DR-EMP-010` | common handler/client | `IMPL-EMP-003/007` | `TEST-EMP-011` | `VAL-EMP-002` |
| `REQ-EMP-008` | `DR-EMP-010/011` | Adapter/模型边界 | `IMPL-EMP-003/005/006` | `TEST-EMP-009/012` | `VAL-EMP-002/004` |
| `REQ-EMP-008` | `DR-EMP-012` | Gateway/Servlet/联调 harness | `IMPL-EMP-011～014` | `TEST-EMP-013` | `VAL-EMP-005` |
| `REQ-EMP-009`,`CON-EMP-007` | `DR-EMP-013` | Employee Resolver/Runtime 混合节点 | `IMPL-EMP-015` | `TEST-EMP-014` | `VAL-EMP-006` |
| `REQ-EMP-010`,`CON-EMP-008` | `DR-EMP-014` | candidate-02 test harness/launcher；Employee transport 计数接缝 | `IMPL-EMP-016～018` | `TEST-EMP-015` | `VAL-EMP-007` |
| `REQ-EMP-011`,`CON-EMP-009` | `DR-EMP-015`、`DR-EMP-016`、`DR-EMP-017` | Employee qualification历史、candidate-02 harness及单查询聚合诊断 | `IMPL-EMP-019～026` | `TEST-EMP-016～018` | `VAL-EMP-008～010` |
| `REQ-EMP-012`,`CON-EMP-010` | `DR-EMP-018` | Employee `WORK_BASE_SI` 静态来源诊断 | `IMPL-EMP-027` | `TEST-EMP-019` | `VAL-EMP-011` |
| `REQ-EMP-013`,`CON-EMP-011` | `DR-EMP-019` | Employee `WORK_BASE_SI` 物理元数据与互斥值分类诊断 | `IMPL-EMP-028` | `TEST-EMP-020` | `VAL-EMP-012` |
| `REQ-EMP-014`,`CON-EMP-012` | `DR-EMP-020`、`DR-EMP-021`、`DR-EMP-022`、`DR-EMP-023` | Employee synthetic fixture test preparation、run-01/candidate-02物理元数据及post-consumption前置 | `IMPL-EMP-029～034` | `TEST-EMP-021～024` | `VAL-EMP-013～017` |
| `REQ-EMP-015`,`CON-EMP-013` | `DR-EMP-024` | Employee synthetic fixture candidate-01准备 | `IMPL-EMP-035～037` | `TEST-EMP-025` | `VAL-EMP-018` |
| `REQ-EMP-016`,`CON-EMP-014` | `DR-EMP-025` | Employee资格candidate-03 non-live准备 | `IMPL-EMP-038～040` | `TEST-EMP-026` | `VAL-EMP-019` |
| `REQ-EMP-017`,`CON-EMP-015` | `DR-EMP-026` | Employee资格candidate-04 non-live准备 | `IMPL-EMP-041～043` | `TEST-EMP-027` | `VAL-EMP-020` |
| `REQ-EMP-018`,`CON-EMP-016` | `DR-EMP-027` | Employee资格candidate-04 post-consumption失败关闭 | `IMPL-EMP-044` | `TEST-EMP-028` | `VAL-EMP-021` |
| `REQ-EMP-019`,`CON-EMP-017` | `DR-EMP-028` | Employee资格candidate-05 lifecycle一致性non-live准备 | `IMPL-EMP-045～047` | `TEST-EMP-029` | `VAL-EMP-022` |
| `REQ-EMP-020`,`CON-EMP-018` | `DR-EMP-029` | Employee资格candidate-06 codec四键一致性准备 | `IMPL-EMP-048～050` | `TEST-EMP-030` | `VAL-EMP-023` |
| `REQ-EMP-021`,`CON-EMP-019` | `DR-EMP-030` | Employee egress candidate-03统一生命周期准备 | `IMPL-EMP-051～053` | `TEST-EMP-031` | `VAL-EMP-024` |
| `REQ-EMP-022`,`CON-EMP-020` | `DR-EMP-031` | Employee candidate-03失败历史与candidate-04新task绑定 | `IMPL-EMP-054` | `TEST-EMP-032` | `VAL-EMP-025` |
| `REQ-EMP-023`,`CON-EMP-021` | `DR-EMP-032` | Employee candidate-04外部versioned live bootstrap | `IMPL-EMP-055` | `TEST-EMP-033` | `VAL-EMP-026` |
| `REQ-EMP-024`,`CON-EMP-022` | `DR-EMP-033` | Employee wrapper-v2 auth JAR provenance与有限启动诊断 | `IMPL-EMP-056` | `TEST-EMP-034` | `VAL-EMP-027` |
| `REQ-EMP-025`,`CON-EMP-023` | `DR-EMP-034` | Employee wrapper-v3 lifecycle/preflight顺序一致性 | `IMPL-EMP-057` | `TEST-EMP-035` | `VAL-EMP-028` |
| `REQ-EMP-026`,`CON-EMP-024` | `DR-EMP-035` | 当前Employee交付边界与可选外发实验治理 | `IMPL-EMP-058` | `TEST-EMP-036` | `VAL-EMP-029` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文责任 | 对方责任 | 权限 |
|---|---|---|---|---|
| `L2_02_00` | 直接依赖 | 实例化公共原语 | 公共配置/HTTP/结果/投影语义 | 只读 |
| `employee-service` | 业务权威 | 映射确认后的只读入口 | Employee 数据、最终角色授权、响应真实性 | 设计建议；代码只读 |
| `auth-service/common-security` | 身份权威 | 定义消费场景 | 用户/角色、验签、Authority 映射 | 只读 |
| `gateway-service` | 测试入口与日志边界 | 删除完整 path 输出；测试期临时转发一次合成请求 | 正式路由与生产治理 | 最小代码修改；测试配置，不新增正式路由 |
| `agent-runtime` core | 调用方 | 提交 descriptor/handler | 单动作 claim、context/deadline/公共结果 | 设计 |
| DeepSeek 模型边界 | 条件下游 | 仅提供安全字段候选 | 全局问题/结果出域和模型协议 | 默认拒绝 |

## 6. 当前基线与最小变更

### 6.1 已核实事实

| 状态 | 路径/符号 | 事实 | 影响 |
|---|---|---|---|
| 已实现验证 | `employee-service/src/main/java/com/dylan/employee/controller/EmployeeController.java` `detail(Authentication,String)` | `GET /employees/{idCardNo}` 先执行 `requireEmployeeRead`，再恰好一次调用 `EmployeeService.detail` | 复用现有一次只读接口，不新增 endpoint/DTO |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/model/Employee.java` | 实体包含身份证、银行、地址、电话、亲属等宽字段 | Adapter 必须显式摘取，不能反射 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/service/EmployeeService.java` `detail(String)` | 未找到时抛 `IllegalArgumentException` | 当前经 advice 映射 400 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/web/EmployeeExceptionHandler.java` | 所有 `IllegalArgumentException` 返回 400 | 不能确认 no-result |
| 已实现验证 | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java` | 先校验 user token，再以 `GrantedAuthority.getAuthority()` 精确允许 `ROLE_ADMIN/ROLE_VIEWER` | 本地 Provider 权限边界与受控真实角色矩阵均已通过，`SA-GATE-004` Closed；不代表默认启用或生产生效 |
| 已实现验证 | `common-security` | `L2_00_03` 统一 role→Authority Converter、具名 Bean 与组合式真实 JWT 链路已验证 | `AUTH-GATE-001/002` Closed；目标部署/生产生效仍受`AUTH-GATE-003`控制 |
| 已实现验证 | `employee-service/src/test/resources/contracts/employee-detail-response-visibility-v1.json`、`employee-detail-callers-v1.json` | 冻结 ADMIN/VIEWER、58 个完整序列化字段、现有 Agent HTTP 调用方及同进程非 HTTP 消费者 | 支撑本地兼容与字段漂移检测，不替代真实运行证据 |
| 已实现验证 | `agent-runtime/src/agent_runtime/adapters/employee` | `employee.detail` definition/codec/normalizer/六字段投影和 fake Provider 已存在 | 真实 endpoint 仍保持禁用 |
| 已实现并验证 | `gateway-service/src/main/java/com/dylan/springgateway/config/GatewaySecurityConfig.java` `authTokenFilter(JwtDecoder)` | 已删除 `exchange.getRequest().getURI().getPath()` 的标准输出；认证、JWT 转发与白名单判断不变 | 过滤器日志契约、正式路由退出测试及 `VAL-EMP-005` live 证据均通过 |
| 已核实 | `gateway-service/src/main/java/com/dylan/springgateway/config/GatewayRouter.java` 与 `GatewayEmployeeRouteExitTest` | 正式路由表不含 Employee 路由，且测试固定该退出条件 | `VAL-EMP-005` 只能使用测试进程内临时路由，测试结束后不得形成正式路由或默认配置 |
| 已核实但不足 | `EmployeeSqlProvider.insert(Map)`、`deleteByIdCardNo()`、`EmployeeMapper`、`EmployeeService` | SQL Provider可按Map存在键生成58列稀疏INSERT并按`ID_CARD_NO`删除；正式Service写链包含审批/事件。仓库无版本化Employee DDL，当前只读证据仅覆盖`WORK_BASE_SI`单列 | 不能证明四字段真实插入成功、标识唯一、无FK/CHECK/trigger副作用或精确清理安全；`GATE-050`必须先关闭 |

### 6.2 最小改造判断

已落实的最小方案是复用 `GET /employees/{idCardNo}`，不新增 DTO/endpoint；Provider 在详情 HTTP 入口执行 Employee 读权限 guard，Python 侧只读取六个允许字段并忽略其余字段。维护者通过版本化策略 fixture 明确 ADMIN/VIEWER 对当前 58 字段完整响应可见，并以仓库静态调用方清单和回归证明当前兼容范围；Adapter 丢字段仍不构成业务字段授权。`VAL-EMP-005` 已通过删除全局过滤器完整 path 输出和测试临时路由，以一次合成请求证明实际到达 Servlet 且原始日志扫描为零；测试结束后原始日志已删除，只保留不含 sentinel/JWT/path 的有限证据。由于 400 同时承载参数错误和未找到，首期继续保守映射 invalid_argument；若需要准确 no-result，必须另行确认业务服务异常契约调整。

本轮 synthetic fixture 的最小改造判断是“先停在物理契约门禁”：逻辑上只需四个非空字段和一条确定性非真实记录，但当前静态源码无法证明其余54列可省略、`ID_CARD_NO`具有所需唯一性、DELETE不会触发外键/触发器副作用，也无法选择安全的事务/恢复方式。此时实现fake repository只会验证自造假设，因此不创建代码、Schema、journal或evidence，先由`GATE-050`只读关闭元数据缺口。

## 7. 责任、依赖与禁止路径

### 7.1 责任分解

| 组件 | 唯一职责 | 明确不负责 |
|---|---|---|
| Employee definition/provider | 冻结动作、字段、限制并提交公共组合根 | HTTP client、授权、另一业务域 |
| `EmployeeDetailLocalActionResolver` | 以本文有限语法把 Employee 详情问题解析为唯一候选参数或有限无效原因 | 业务调用、角色判断、模糊 NLU、模型调用、参数最终合法性判定 |
| Employee mapper/codec/normalizer | 强类型输入与现有详情 wire 契约转换 | 动态 URL、角色判断、模型调用 |
| common handler/client/projector | 执行一次用户 JWT 调用和公共投影顺序 | Employee 字段/端点/业务授权 |
| Employee Controller/guard | 在业务方法前完成最终角色授权 | Agent 字段收紧、模型出域 |
| EmployeeService/Mapper | 返回 Employee 业务事实 | Agent 动作注册和答案生成 |
| Gateway 安全过滤器 | 认证转发且不记录完整请求 path | Employee 正式路由、业务授权或员工标识脱敏副本 |
| `VAL-EMP-005` opt-in harness | 仅装配测试临时路由、发起一次合成请求、扫描并删除原始日志、写有限 evidence | 默认启用、真实员工数据、第二次请求或生产监控 |

### 7.2 依赖方向与调用边界

```text
agent-runtime RuntimeCompositionRoot
  -> HybridActionSelectionNode
     -> EmployeeDetailLocalActionResolver -> ActionCandidate(employee.detail, arguments)
  -> EmployeeDomainProvider
     -> CapabilityArgumentValidator -> BoundBusinessActionHandler
        -> EmployeeDetailMapper/Codec
        -> UserJwtBusinessHttpClient -> employee-service EmployeeController
           -> EmployeeReadAccessGuard -> EmployeeService -> EmployeeMapper
        -> EmployeeDetailNormalizer -> common user/egress projectors
```

禁止依赖与反向依赖：Employee Adapter 不得导入 Transaction、Employee Java DTO、数据库/ES client 或安全私有类；core 不得导入 Employee 字段；`employee-service` 不得信任 Adapter 投影作为授权；配置不得绕过 codec 指定 URL/method/header；模型不得触发分页、count、ES、变更或第二动作。

### 7.3 内聚与耦合判断

动作、字段和 wire 契约随 Employee 业务接口共同变化，内聚在 Employee Adapter；JWT client、公共结果与投影算法随两域共同约束变化，留在 business common；最终角色授权随业务数据权威变化，留在 `employee-service`。三者只通过冻结 action definition、HTTP wire 和 Authority 可观察契约耦合，不共享 Java/Python 私有 DTO，因此新增 Transaction 或未来 Employee 第二动作不要求修改 core 或既有公共算法。

## 8. 动作、请求与响应契约

### 8.1 动作定义

| 定义字段 | 冻结值 |
|---|---|
| `descriptor.capability_id` | `employee.detail` |
| `api_version/kind` | `1/query` |
| `display_name` | `Employee detail` |
| `description` | `查询单个员工的受控基础信息；只接受 employee_identifier，不提供列表、聚合或写入。` |
| `aliases` | `("员工详情","employee profile")`；只帮助模型理解，不可作为执行 ID |
| `argument_schema` | 8.2 的固定执行 object schema；`required=["employee_identifier"]`、`additionalProperties=false`；只供本地候选最终校验与执行注册，不发送给模型 |
| 模型选择投影 | 仅 `capability_id/display_name/description/aliases`，tool 参数 Schema 固定为空 object；模型只可返回 `employee.detail` ID，不能返回标识 |
| `domain_id/service_key` | `employee/employee-service` |
| `answer_mode` | `model_assisted`，但本地结构化结果始终可返回 |
| `applicable_dimensions` | 仅 `max_result_count`、`timeout_ms` |
| `contract_limits` | `max_result_count=1`；`max_timeout_ms=3000`；`max_request_bytes=1024`；无 page/time/filter/sort；Employee codec 另拒绝超过 65536 raw bytes 的已聚合 2xx body |
| `http_status_semantics` | `http_400_is_invalid_argument=true`；`http_204_is_no_result=false`；`http_404_is_no_result=false` |
| `required_user_field_ids` | `employee_id_masked,chinese_name` |

### 8.2 Python 输入与方法

`CapabilityDescriptor.argument_schema` 固定为下列供应商无关执行契约；它不投影给模型。混合节点只对 Resolver arguments 执行公共 `JsonObject` 类型、深度、项数与字节边界并形成最终候选；Core 不新增通用 JSON Schema 执行器，随后仍必须由同一注册项的 validator 按该 Schema 的动作语义执行字段、UTF-8、控制字符、保留字符和掩码前置条件校验：

```json
{
  "type": "object",
  "properties": {
    "employee_identifier": {
      "type": "string",
      "minLength": 5,
      "maxLength": 64,
      "description": "Employee service identifier; never a URL or query expression."
    }
  },
  "required": ["employee_identifier"],
  "additionalProperties": false
}
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeDetailInput:
    employee_identifier: str
```

| 类型 | 精确字段 | 不变量 |
|---|---|---|
| `EmployeeDetailWireRequest` | `employee_identifier: str` | 只由 validator/mapper 构造，已满足标识边界 |
| `EmployeeDetailWireResponse` | `id_card_no: str`；`member_no: str \| None`；`chinese_name: str`；`public_email: str \| None`；`position: str \| None`；`work_base_si: str \| None` | 8.3 字段/空值/长度不变量 |
| `EmployeeDetailRecord` | 与 wire response 相同的六个冻结 typed 字段 | 只由 normalizer 构造，不保留原始 JSON |

`EmployeeDetailArgumentValidator.validate(arguments: JsonObject) -> EmployeeDetailInput` 只接受唯一 key `employee_identifier`。输入必须是 exact string；先去除首尾 Unicode whitespace 再做 NFC，结果为 5～64 Unicode code points 且 UTF-8≤192 bytes；拒绝内部 whitespace、Unicode control/Bidi override/isolate、`/`、反斜线、`%`、`?`、`#`，大小写不变。该边界只保证单一 path segment 和必需掩码可实现，不猜测 Employee 方身份证/护照字符集；业务语义仍由现有接口判断，配置不能放宽。

#### 8.2.1 Employee 本地 Resolver 有限语法

`EmployeeDetailLocalActionResolver` 只解析一个完整、单句详情请求。解析前对问题执行 NFC，并仅从首尾删除 `U+0020/U+3000`；控制字符、Bidi override/isolate 或 Core 已拒绝的超长输入在识别到 Employee 前缀后返回 `invalid(malformed_value)`。语法记号如下：

```text
SP      := 0..4 个 U+0020 或 U+3000
POLITE  := "请" | "请帮我" | ε
INTENT  := "查询员工详情" | "查询员工" | "查看员工详情" | "查看员工" | "员工详情"
DELIM   := SP | SP ("," | "，") SP
LABEL   := "员工标识" | "员工编号" | "身份证号" | "证件号"
OP      := "为" | "是" | "=" | ":" | "："
PUNCT   := "。" | "？" | "?" | ε
QUESTION := POLITE SP INTENT DELIM LABEL SP OP SP VALUE PUNCT
```

语法实现必须是锚定整串的确定性扫描，不得用包含搜索或正则回溯猜测切分：固定 token 一律按“当前位置可匹配的最长已列字面量”选择，因此 `请帮我` 优先于 `请`，较长 `INTENT` 优先于其前缀；`DELIM` 先消费 0～4 个结构空格，再优先消费至多一个逗号及其后 0～4 个结构空格。任一结构位置连续空格超过 4 个、双逗号或未消费尾随字符均在已识别意图后失败关闭。末尾只允许剥离恰好一个 `PUNCT`；剥离后再次以终止标点结尾视为附加语法，不得把第二个标点并入值。

其中 `VALUE` 是从 operator 后结构空格结束处到可选单一终止标点之前的全部非空剩余文本，再仅删除 0～4 个结构性尾空格；其中出现 `,`、`，`、`;`、`；` 时视为第二子句/列表边界并返回 `invalid(unsupported_clause)`，没有转义或引号机制。Resolver 不对值做业务归一化或放宽，只原样写入 `{"employee_identifier": VALUE}`，最终仍由 `EmployeeDetailArgumentValidator` 拒绝内部空白、保留字符、长度或 Unicode 非法值。裁决必须满足：

- 规范化问题不以可选 `POLITE+SP` 后的任一 `INTENT` 开始时返回 `no_match`，不产生参数；全局敏感问题闸门仍独立阻止具体标识进入模型。
- 已识别 `INTENT` 但缺 label/operator/value，返回 `invalid(missing_required)` 或 `invalid(malformed_value)`；出现两个已知 label 返回 `invalid(duplicate_argument)`。
- 出现第二子句、未列 label/operator、终止标点后的尾随文本、列表/分页/聚合/写入词句，统一返回 `invalid(unsupported_clause)`；不得退回模型修补参数。
- 唯一合法 Resolver 结果为 `candidate(arguments={"employee_identifier": VALUE})`；目标 ID 只由同一对象的 `capability_id="employee.detail"` 属性提供，混合节点据此构造最终 `ActionCandidate`。Resolver 不读取配置/JWT/角色，不访问网络或时钟，不记录问题/标识，不调用 validator、handler 或模型。
- Runtime 对 Resolver arguments 继续执行公共 JSON 结构/大小/深度校验，再由注册项 validator 执行动作 Schema 语义并进入单动作 claim；Resolver 成功不绕过任何执行契约。

`EmployeeDetailRequestMapper.map(input, settings) -> EmployeeDetailWireRequest` 验证 result count 恰为 1；`EmployeeDetailWireCodec.encode` 把未预编码的 NFC 值按 UTF-8 做一次 RFC 3986 segment percent-encoding、`safe=""`，生成且只生成 `GET /employees/{encoded}`，无 query/body/自定义 header；不得接受或二次解释已有 `%HH`。

### 8.3 2xx wire response

- 顶层必须为单个 JSON object，严格 UTF-8、unique keys；Employee codec 只接受 body≤65536 raw bytes。公共客户端仍先按 `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` 聚合，故 65537～全局上限由 codec 拒绝，超过全局上限由 transport 拒绝。
- 六个目标字段按现有 camelCase 名解码；`idCardNo/chineseName` 必须为非空 exact string，其余为 exact string 或 null；bool、number、array、object 均不宽松转换。
- 规范化后的响应 `idCardNo` 必须与同一次 `EmployeeDetailWireRequest.employee_identifier` code-point 精确相等；不做大小写或本地身份证规则归一化。不一致为 invalid_response，typed record/模型调用为零。
- 未列入的 Employee 字段和未来新增字段允许解析后显式丢弃，但不得进入 typed record、日志、错误或指标；目标字段类型错误、重复 key 或缺必需字段则整个响应 invalid_response。该策略是对公共“默认严格拒绝”的本域兼容性例外，仅因当前公开响应是已核实的宽实体而成立。
- string NFC 后上限：`idCardNo/memberNo` 为 5～64，姓名 1～128，邮箱 1～254，职位/工作地 1～256 code points；非空值含控制/Bidi 字符或越界时不截断并失败关闭。
- 首期不引入流式 JSON 生产依赖：strict decoder 可短暂构造受全局字节上限约束的 JSON object，但只能把六个目标字段复制进冻结 typed response，随后释放原始 bytes/object。测试以账户、地址、亲属和嵌套恶意字段证明零 typed 投影、零日志和零错误回显，不能声称未知值未进入 Agent 内存。

### 8.4 字段目录与转换

| field_id | source | value_type | class | user | model candidate | allowed user transforms | allowed model transforms |
|---|---|---|---|---:|---:|---|---|
| `employee_id_masked` | `idCardNo` | `identifier` | `personal_identifier` | 是/必需 | 否 | `{mask_keep_last4}` | `{}` |
| `member_no_masked` | `memberNo` | `identifier` | `employee_identifier` | 是 | 否 | `{mask_keep_last4}` | `{}` |
| `chinese_name` | `chineseName` | `text` | `personal_identifier` | 是/必需 | 否 | `{bounded_text}` | `{}` |
| `public_email` | `publicEmail` | `text` | `contact` | 是 | 否 | `{bounded_text}` | `{}` |
| `position` | `position` | `text` | `business_internal` | 是 | 是 | `{bounded_text}` | `{bounded_text}` |
| `work_base_si` | `workBaseSi` | `text` | `business_internal` | 是 | 是 | `{bounded_text}` | `{bounded_text}` |

表中顺序就是冻结 field definition、用户结果和事实生成顺序；`None` 依公共规则省略，不能进入结果。模型字段代码上限仅为 `position/work_base_si`，动作配置默认空，且仍与全局规则取交集。姓名、标识和邮箱永不进入模型候选。`mask_keep_last4` 完全复用 `L2_02_00`：输入必须为 NFC、无控制/Bidi 且 5～256 code points，输出固定为 `***` 加末四个 code points；本文不定义长度≤4的域内特例，任一不满足值使用户投影失败关闭。

## 9. 详细功能与处理流程

### 9.1 设计规则

| 规则编号 | 规则 | 责任主体 | 效果 |
|---|---|---|---|
| `DR-EMP-001` | 只定义并注册 `employee.detail@1`，descriptor 是唯一动作权威 | provider/组合根 | 动作面有限 |
| `DR-EMP-002` | 配置只能禁用动作、减少本地/模型字段和 timeout，不能新增动作/参数/URL | settings/provider | 配置不扩权 |
| `DR-EMP-003` | Adapter 只透传当前 opaque user JWT，不解析 role、不使用 service token | handler/client | 身份不替换 |
| `DR-EMP-004` | 统一安全边界先验证 role claim 并映射 Authority；Employee 详情入口再于 service 前验证 user token 且含 `ROLE_ADMIN` 或 `ROLE_VIEWER` | common-security/employee-service | 映射与业务授权分层 |
| `DR-EMP-005` | codec 只提取六个字段，其他宽实体字段显式忽略且零留存 | codec | 宽响应隔离 |
| `DR-EMP-006` | idCard/memberNo 先掩码；必需 ID/姓名缺失时 downstream failure，不制造空 success | projector | 最小有效结果 |
| `DR-EMP-007` | 模型字段只可能是职位/工作地，默认空；转换/交集失败保留本地结果且模型调用为零 | egress projector | 出域失败关闭 |
| `DR-EMP-008` | 400 固定 invalid_argument；401/403 保持；404/204/非法 2xx 不猜 no-result | status mapper/normalizer | 状态真实 |
| `DR-EMP-009` | 一次请求至多一个 GET，共享绝对截止，无 retry/redirect/cache/第二动作 | common handler/client | 资源有界 |
| `DR-EMP-010` | path 只由 codec 编码受控标识生成，原始标识不进入日志/异常 | mapper/codec | 无动态调用 |
| `DR-EMP-011` | 具体 Employee 标识、姓名、联系方式和返回自由文本均作为敏感场景输入全局问题/模型闸门 | fixtures/L2_00_02 | 模型零调用可证 |
| `DR-EMP-012` | Gateway 全局过滤器不得输出完整请求 path；`VAL-EMP-005` 只在 opt-in 测试进程中创建临时 Employee 路由，以进程内合成 sentinel 发起恰好一次 Gateway→Servlet 请求，扫描 sentinel/编码 sentinel/JWT/密钥/完整 path 后删除全部原始日志，只持久化有限计数与零泄漏结论 | gateway-service/测试 harness | 修复生产日志泄漏点但不扩大正式路由；日志证据可复现且不形成敏感副本 |
| `DR-EMP-013` | `EmployeeDetailLocalActionResolver` 只实现 8.2.1 的有限纯函数语法；无匹配不造参数，识别后缺失/重复/附加子句失败关闭，成功只产生 `employee.detail` 与单一标识 JSON；配置、模型和业务服务均不能修改该语法 | Employee Adapter/Runtime 混合节点 | 敏感标识在本地解析，模型调用为零；最终 Schema/validator/单动作约束保持权威 |
| `DR-EMP-014` | candidate-02 必须用独立 v2 模块、Schema、launcher、manifest 和 authorization 实例化 `DR-BQCOM-021`，不得修改 candidate-01 文件。lifecycle journal 在读取 Employee 标识/JWT 后但在 `handler.handle` 前 exclusive create 并 fsync 无敏感 header；`LiveEmployeeTransportV2.send` 一进入唯一调用即写并 fsync `employee_detail_started`，随后调用唯一 `httpx.AsyncClient.get`，在响应或受控异常后写唯一 terminal。evidence 的精确 `employeeDetailRequests` 表示 Agent transport `send` 调用数，只能为0或1，不冒充 Employee 服务实际接收计数。未出现 consumed marker 的终态只能是 `failed_unconsumed`；marker 与 run/manifest/auth 精确绑定并只在首个通过安全校验的模型请求调用 delegate 前创建，存在 marker 后失败只能是 `failed_consumed`。初始化后的响应/投影/模型设置/模型调用/阈值/cleanup 等可控失败均写有限 `failurePhase/failureReason`、terminal 和 evidence；禁止持久化异常文本、标识、JWT、Employee 值、Prompt 或原始模型响应，retry/resume=0 | candidate-02 测试 harness/launcher | pre-model 根因窗口和 Agent侧 Employee 调用次数可证明；candidate-01 与生产契约不变 |
| `DR-EMP-015` | `WP-EMP-EGRESS-INPUT-QUALIFY-01` 是 test-only 前置：若进程级 `EMPLOYEE_EGRESS_QUALIFY_TEST_IDENTIFIER` 已由维护者确认为 `position/workBaseSi` 非空则直接使用且数据库筛选计数为0；否则 Java opt-in 测试通过 `JdbcTemplate.query(... LIMIT 1)` 只返回一个 `ID_CARD_NO`，WHERE 固定为两字段 `IS NOT NULL AND TRIM(...) <> ''`，排序固定且不修改 Mapper/生产 SQL。标识只通过父子进程环境传给 Python probe并在进程退出时销毁；真实 auth-service 仅签发内存 ADMIN JWT，Python probe 通过现有 definition/codec/normalizer/user projector/`BusinessEgressProjector` 发起恰好一次 detail。strict evidence 顶层只允许 schema/work-package/run/status、两个字段存在性 boolean、有限 egress reason、四项请求计数和零泄漏结论；`qualified` 必须同时满足两字段存在、egress allowed、数据库返回≤1、detail=1、其他端点/model=0。runner 在启动子进程前移除 `LLM_API_KEY`，扫描标识/JWT/HMAC/密码/字段值后删除原始日志和本次 surefire 报告。任何失败只输出有限 `employee.egress_input_qualify_*` code，不保存异常正文；资格通过不创建 candidate-03、不消费授权、不关闭三项 live 门禁。首次受控运行已证明“成功后才写 evidence”不足以覆盖失败窗口；该 run 不得复用，后继新 run 必须在数据库筛选/detail 前先写耐久阶段 journal，并在失败时保留精确0/1计数和有限终态 | Java/Python opt-in tests 与版本化 launcher | 真实输入资格、一次调用和零泄漏可证；生产 Java/Python、业务数据和 candidate-01/02 不变 |
| `DR-EMP-016` | `WP-EMP-EGRESS-INPUT-QUALIFY-02-PREP` 以 run `employee-egress-input-qualification-v2-20260814-candidate-02` 实例化 `DR-BQCOM-023`。candidate只允许 `read_only_database`：Java测试在 `JdbcTemplate.query` 前创建并fsync lifecycle首记录，固定SQL只选择 `ID_CARD_NO`，WHERE显式覆盖id 5～64、UTF-8最多192字节且无空白/URL保留/控制/双向控制字符、`CHINESE_NAME` 1～128、`POSITION/WORK_BASE_SI` 1～256且无控制/双向控制字符，`ORDER BY ID_CARD_NO LIMIT 1`；标识只在Java→Python子进程内存传递。Python transport在真实send边界写detail started/terminal，现有definition/codec/normalizer/user projector/egress projector是最终权威。lifecycle和result均严格拒绝额外键，结果只保留四个codec字段和两个required user字段存在性、有限phase/reason、数据库/detail精确0/1、lifecycle hash和安全布尔，非成功 `egressReason` 必须等于 `failure.reason`；模型/其他端点/retry/resume恒0。探针只能先写临时有限结果，launcher完成日志扫描删除后才exclusive create正式result，禁止提前声称日志已清理。manifest绑定退役v1资格run六项及Employee egress八项历史，authorization保持`prepared_unconsumed/liveExecutionAuthorized=false`；本轮只用fake和disabled Java编译，不创建lifecycle/result。正式数据库筛选/一次detail须再次绑定run、manifest SHA-256、authorization reference并授权`GATE-049` | `agent-runtime`/`employee-service`测试、Schema、版本化launcher与冻结资产 | 新资格candidate-02准备与后续一次受控执行；精确失败证据、完整输入条件和历史不可变，生产src/API/数据/角色/默认配置零变化 |
| `DR-EMP-017` | `WP-EMP-EGRESS-INPUT-QUALIFY-DIAG-02` 以全新诊断run只读解释candidate-02的rows=0。Java测试必须使用单次 `JdbcTemplate.queryForMap` 执行一个 `SELECT`，只含`COUNT(*)`及`SUM(CASE WHEN ... THEN 1 ELSE 0 END)`聚合，复用`DR-EMP-016`中id/name/position/workBaseSi四项条件；同时计算各单项计数与按id→name→position→workBaseSi顺序的累积计数，禁止查询/返回`ID_CARD_NO`、`CHINESE_NAME`、`POSITION`、`WORK_BASE_SI`原始值或任何记录。Python strict validator/JSON Schema固定键、枚举、整数关系及candidate-02两项历史哈希：总数/单项/累积非负，累积单调不增且不超过相应单项与总数，最终累积为0时首个归零阶段必须唯一正确，否则为`none`。Java查询前必须重新校验candidate-02两项历史哈希，只能exclusive写临时staging且`rawLogsDeleted=false`；外层执行扫描、删除临时Maven/Surefire日志后，strict finalizer才可exclusive创建正式evidence并置true，随后删除staging，禁止提前声明日志已清理。正式evidence只保存计数、`qualified_input_available/no_qualified_input`、aggregateQueries/resultRows=1、detail/other endpoint/model/retry/resume=0及无标识/字段值/原始行/JWT/密钥/outbound/日志泄漏结论；不得启动auth、签JWT或Web服务。真实聚合仅执行一次；若完整资格计数仍为0，输出首个归零条件后停止，不得修改数据、准备candidate-03或重跑`GATE-049` | `agent-runtime`/`employee-service`测试、Schema与有限evidence | 本地数据资格条件诊断；精确定位首个归零条件且不泄露业务值，生产/API/数据/历史零变化 |
| `DR-EMP-018` | `WP-EMP-EGRESS-WORK-BASE-DIAG-01` 必须以既有聚合 evidence SHA-256=`f23115069adaa0bfedcfdb01b7f0889acb079961319db3c44547549ca088c46f` 为唯一数据事实。静态检查固定覆盖 `Employee.java` 的 property/getter/setter、`EmployeeMapper.java` 的 ResultMap、`EmployeeSqlProvider.java` 的列/属性顺序与按键写入、`EmployeeService/Controller` 的通用 Map create/update、Employee resources/README、仓库版本化 SQL/初始化/导入/回填及 Employee ES rebuild 边界。有限 evidence 只保存固定源码路径/SHA-256、映射/写入布尔、非负资产计数、`data_population_provenance_gap`、`not_versioned`、`not_observable_without_separate_query` 等有限枚举和全零外部调用计数。既有聚合直接统计数据库列且 Java 映射一致，因此读取映射不是计数0的原因；当前写链只在调用方提供 key 时写入且无 required/default/backfill，仓库也没有版本化 Employee DDL/初始化/导入来源，故可判定数据填充/来源缺口。但静态证据不能证明物理列类型/nullability/default，也不能区分990条是NULL、空白还是其他非法值；到此停止并仅建议另行授权最小 `information_schema` 元数据及单行整数分类聚合 | `agent-runtime` Employee测试范围静态诊断、Schema/evidence | 解释 `work_base_si` 首零并限定未知项；不查询数据库/端点，不修改生产/数据/历史，不解锁`GATE-049`或candidate-03 |
| `DR-EMP-019` | `WP-EMP-EGRESS-WORK-BASE-DATA-DIAG-01` 必须先精确校验静态 evidence SHA-256=`7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8`。测试范围 `EmployeeWorkBaseDataDiagnosticLiveIntegrationTest` 在`@Transactional(readOnly=true)`内只执行两次JdbcTemplate调用：元数据SQL限定当前database、employee表和`WORK_BASE_SI`列，只投影`DATA_TYPE/COLUMN_TYPE/IS_NULLABLE/CHARACTER_MAXIMUM_LENGTH/COLUMN_DEFAULT/COLLATION_NAME`并要求1行；聚合SQL不选择原始列、不分组，只以 `NULL→非NULL长度不在1～256→长度有效且control→前述未命中且bidi→valid` 的优先级返回五个互斥整数和总数，分类和必须等于总数。strict evidence记录两次查询/两行结果、六项元数据、整数分布、有限reason和零HTTP/JWT/模型/retry/resume/泄漏；若total/valid不等于990/0则`source_snapshot_mismatch`且不宣称分布根因。launcher必须删除临时日志后才exclusive-create最终evidence。不得修改生产src、数据/结构/API/历史，不得重跑`GATE-049`或准备candidate-03 | `employee-service` test、`agent-runtime` Employee integration test/Schema/launcher | 物理列定义与值状态只读证据；不形成数据修复授权 |
| `DR-EMP-020` | `WP-EMP-EGRESS-TEST-DATA-PREP-01` 固定消费metadata result SHA-256=`9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51`。逻辑 fixture 只允许 `idCardNo/chineseName/position/workBaseSi` 四个非空字段：标识由固定 synthetic 前缀和版本化非敏感seed哈希生成，不得匹配真实身份证格式；姓名/职位/工作地使用固定合成文本。test-only repository必须在任一操作前exclusive-create+fsync lifecycle，先确认标识不存在，再单次INSERT、按标识和四字段fingerprint验证恰好1条；consumer完成或失败后以相同完整fingerprint单次DELETE并确认不存在。创建开始后任一失败都进入cleanup；删除计数异常或清理不能证明均为`failed_cleanup_required`，禁止UPDATE、宽DELETE、重试、覆盖或修改现有990条。有限evidence不得保存标识、fingerprint或字段值，只记录schema/version/模板hash、synthetic=true、字段名集合、create/verify/delete精确0或1、有限phase/reason、existingRowsModified=0与cleanup终态。当前metadata证明58列、InnoDB、0键/FK/CHECK/trigger且四列均nullable longtext、无default/generated；任何hash/结构漂移须在journal前失败 | `employee_test_data_fixture.py`测试范围Protocol/in-memory fake；未来真实repository待单独设计 | 新资格candidate前合成输入准备；non-live契约闭环，生产Service/Mapper/API/数据与历史均不修改 |
| `DR-EMP-021` | `GATE-050` 只读探针固定四条顺序查询：`information_schema.columns/tables`、键和出入向外键、CHECK、trigger；不得查询Employee业务记录。trigger动作定义只在Java进程内分类，正式结果只保存数量、规范化SHA-256与有限副作用枚举。只有四条均完成、58列与Provider对齐、引擎/唯一性/FK/CHECK/trigger足以冻结最小INSERT和精确cleanup时才允许关门；任一失败必须停止且无retry/补跑/追加查询，并持久化不含SQL/异常正文/业务值的有限failure evidence。run `employee-fixture-metadata-diagnostic-v1-20260814-run-01` 已在第2条约束查询发生隐式collation冲突，故第3/4条未执行且门禁保持Open；后继必须以新run/hash/auth采用显式binary或其他collation-neutral schema/table比较，不得改写或复用run-01 | `agent-runtime` Employee测试范围strict probe/Schema/launcher、`employee-service` test-only只读Java probe | fixture物理契约核实；失败可归因、预算可审计、生产/数据/API/历史零修改 |
| `DR-EMP-022` | candidate-02使用run `employee-fixture-metadata-diagnostic-v2-20260814-candidate-02`、`P3_00:GATE-050`和最多四查询。Java四条SQL的SELECT alias、FROM范围和顺序保持run-01不变；`TABLE_SCHEMA/TABLE_NAME/CONSTRAINT_SCHEMA/CONSTRAINT_NAME/EVENT_OBJECT_SCHEMA/EVENT_OBJECT_TABLE`的关联或过滤均必须显式`BINARY left = BINARY right`，不得使用`LOWER`或隐式collation。Java在第一次`queryForList`前`CREATE_NEW`并`force(true)` lifecycle；run-start后按四phase逐一started/terminal，失败terminal与run-failed写入后立即停止。Python v2 module严格验证lifecycle/result/manifest/auth和三项历史hash；success保留完整列/键/FK及CHECK/trigger哈希，failure只保留phase/reason/query ordinal/SQLState/vendorCode和计数。launcher先校验manifest SHA和asset历史，再要求独立进程级live开关；prepared manifest/auth均保持live/database=false。本轮仅fake/static/disabled Java，不创建正式lifecycle/result | `agent-runtime/tests/integration/adapters/employee/fixture_metadata_diagnostic_v2.py`、v2 Schema/tests/launcher/manifest/auth；`EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest` | 新`GATE-050`候选准备；run-01不可变，数据库/Employee HTTP/auth/JWT/模型/业务数据/fixture均0 |
| `DR-EMP-023` | candidate-02消费后保持manifest、authorization、lifecycle、result和commit `80c52e030f41111aa1394d990a0af94568487b2c`不可变。post-consumption history test从该commit读取manifest绑定的七项prepared blob并逐项核对SHA；当前工作树测试严格锁定manifest/auth、10条lifecycle事件、result两项SHA及58列/InnoDB/0 constraint/check/trigger和全部安全计数。原prepared-only输出不存在断言只对冻结commit内容成立，不得继续作为当前工作树断言。不得修改launcher/SQL/Schema/证据、再次访问数据库或复用run；宿主命令退出码与strict result冲突时记录为launcher状态传播缺口，但门禁事实以通过Schema/hash的append-only结果为准 | `test_employee_fixture_metadata_diagnostic_v2.py`、`test_employee_fixture_metadata_diagnostic_v2_history.py` | candidate-02 post-consumption与`GATE-050`关闭；只解锁`IMPL-EMP-029/TEST-EMP-021`非live准备，不授权真实fixture或`GATE-049` |
| `DR-EMP-024` | candidate-01固定run `employee-synthetic-fixture-v1-20260814-candidate-01`、manifest SHA-256=`e0c74e5a21d4b80c292cf20266227f7c8f1a11037d1816a6513f6de604e98b11`、authorization=`P3_00:GATE-051`及数据库SELECT/INSERT/DELETE最大3/1/1。`EmployeeSyntheticFixtureCandidateLiveIntegrationTest`只在双进程级opt-in均为1时启动无Web测试上下文；使用参数化SQL和`BINARY`四字段等值，precheck、INSERT、verify、DELETE、remaining分别在显式`TransactionTemplate`中执行，INSERT与DELETE各自提交，禁止Service/Mapper/API/事件。Python lifecycle必须在首个SQL前exclusive-create+fsync；Java记录六个数据库/consumer阶段后只写pending staging，PowerShell删除原始日志并由Python追加host_validation与run终态。strict result只含来源/asset hash、字段名、3/1/1及0/1计数、有限status/reason和安全布尔，不保存标识/fingerprint/字段值。INSERT开始后必须尝试exact DELETE；非`failed_cleanup_required`必须deleted=1且remaining=0。manifest绑定fixture contract/schema、metadata四项历史和六项候选asset；authorization保持live=false，正式执行须另行绑定`GATE-051`且禁止retry/resume | `employee_test_data_fixture_candidate.py`、两份Schema、Java disabled test、versioned launcher、manifest/auth与直接测试 | 一次真实fixture安全候选准备；生产代码/API/数据当前零变化 |
| `DR-EMP-025` | candidate-03固定使用全新run `employee-egress-input-qualification-v3-20260814-candidate-03`和`P3_00:GATE-049`，manifest在实施后冻结。Python `egress_input_qualification_v3.py`定义唯一strict lifecycle/result、四终态和有限原因；fake harness复用`EmployeeFixtureRepository/build_fixture_spec`，验证3/1/1、一次qualification consumer及finally cleanup。Java `EmployeeEgressInputQualificationV3LiveIntegrationTest`仅在显式opt-in下以RANDOM_PORT启动Employee上下文，首SQL前创建journal，使用与`DR-EMP-024`相同的参数化四字段`BINARY` SQL和显式事务完成precheck/insert/verify；随后只启动一次Python detail probe。probe复用现有Employee definition/settings/handler/user projector/egress projector，并在HTTP transport send边界写detail started/terminal；只把存在性布尔和有限egress reason写入staging。Java在finally执行exact delete/remaining并由host finalizer在删除原始日志后写终态。`qualified`要求preexisting0、inserted/verified/deleted=1、remaining0、detail 1/1、四codec字段和两required user字段均true、egress allowed；`not_qualified`只用于已完成detail但结果/egress不满足；基础设施/请求失败为`failed`；任一cleanup失败优先`failed_cleanup_required`。manifest绑定candidate-02四项、fixture candidate-01四项及实现资产hash；authorization保持prepared/live=false，数据库3/1/1、detail1、model0、retry/resume0。不得创建正式lifecycle/result或执行live，直到再次精确授权`GATE-049` | candidate-03 Python/Schema/tests、Java disabled live test、versioned launcher、manifest/auth | 新资格候选non-live冻结；生产Java/Python/API/数据基线不变 |
| `DR-EMP-026` | candidate-03因Spring Boot自动发现同包多个嵌套测试配置而在首SQL前失败，未创建SQL lifecycle/result；其manifest/auth/pre-SQL failure及SHA不可变且run不得重跑。candidate-04继承`DR-EMP-025`的fixture、生产detail probe、3/1/1、detail1、四终态和finally exact cleanup，但使用全新run/manifest/auth并绑定candidate-03失败及全部历史。`EmployeeEgressInputQualificationV4LiveIntegrationTest`必须显式`@SpringBootTest(classes = EmployeeServiceApplication.class, webEnvironment = RANDOM_PORT)`，禁止依赖自动发现。launcher在Maven前创建并fsync独立host lifecycle；Spring context failure且Java SQL lifecycle不存在时，写strict `failed_unconsumed/spring_context_start_failed`有限结果，SQL/detail/model/retry/resume均0并在敏感扫描后删除原始报告；一旦SQL lifecycle存在，host不得覆盖Java阶段或跳过exact cleanup。non-live实现只允许v4 fake/Schema、静态注解唯一性检查、逐阶段launcher故障、disabled Java编译、AST/hash；不得启动服务、数据库/JWT/model或生成正式live结果。冻结后须以candidate-04新run/hash/auth重新授权`GATE-049` | candidate-04 Python/Schema/tests、显式启动类Java disabled test、pre-SQL launcher、manifest/auth/history | 消除Spring配置歧义并使首SQL前失败可审计；生产src/API/数据基线不变 |
| `DR-EMP-027` | candidate-04唯一live运行已形成`qualified`并完成3/1/1、detail1、四codec字段、两required-user字段、egress allowed与exact cleanup；但live finalizer只追加`host_validation succeeded`，冻结`validate_lifecycle()`要求全部非run阶段started/terminal成对，故15条SQL lifecycle被拒绝。prepared、host lifecycle、SQL lifecycle、result及其SHA必须只读，禁止修改v4 writer/validator/Schema/manifest/auth/evidence或重跑。post-consumption history test必须固定frozen HEAD、三项精确SHA、完整15条序列、业务/安全零值和validator拒绝反证。未来恢复资格须另行设计全新candidate，使live同路finalizer在冻结前生成可由同一validator接受的完整终态 | candidate-04 history test与append-only evidence；未来candidate路径待另行授权确认 | 保留业务成功与契约失败双重事实，失败关闭`GATE-049`且不侵入生产src/API |
| `DR-EMP-028` | candidate-05固定run `employee-egress-input-qualification-v5-20260816-candidate-05`、schemaVersion 5、独立manifest/auth和3/1/1+detail1+model0预算。`egress_input_qualification_v5.py::finalize_live_candidate(...)`必须使用与Java/launcher正式路径相同的pending lifecycle：先写`host_validation started`，再写对应terminal和run终态，随后调用同模块`validate_lifecycle()`；只有完整16条记录通过后才允许`validate_result()`与exclusive result写入。direct test必须调用该函数而不是复制事件，覆盖qualified、host exit、log leak及非法pending/lifecycle无result；manifest history直接绑定candidate-04 manifest/auth/host lifecycle/SQL lifecycle/result五项精确SHA、candidate-04 post-consumption history test及v4既有十一项历史，共17项；asset覆盖v5 Python/host、四Schema、direct/host/history/live-opt-in测试、versioned launcher与显式`EmployeeServiceApplication` Java disabled测试。v4全部字节与生产Employee代码保持不变；prepared authorization不构成live许可，冻结后仍须以新run/hash/auth重新授权`GATE-049` | 建议新增candidate-05测试范围Python/Schema/tests、`run-employee-egress-input-qualification-candidate-05.ps1`、`EmployeeEgressInputQualificationV5LiveIntegrationTest` | 以最小versioned测试资产关闭candidate-04暴露的finalizer/validator分叉，不改变业务域或生产契约 |
| `DR-EMP-029` | candidate-05唯一live的host lifecycle、16条SQL lifecycle、3/1/1、detail1和exact cleanup均通过，但Python probe staging的`codec`只含`idCardNo/chineseName/position/workBaseSi`四个boolean键，Java v5 `Presence.load()`却要求`codec.size()==5`，导致捕获`employee_result_invalid`并把presence保守置false。candidate-05 manifest/auth/host/lifecycle/result与独立post-consumption history test须按精确SHA不可变，禁止修改v5或重跑。candidate-06固定run `employee-egress-input-qualification-v6-20260816-candidate-06`、schemaVersion 6和相同3/1/1+detail1+model0预算；仅允许`EmployeeEgressInputQualificationV6LiveIntegrationTest.Presence.load()`把nested codec基数校验改为4，outer object仍5键，四个具体codec键、两个requiredUser键及全部boolean类型校验不变。Python `_validate_presence()`、staging writer和result Schema继续exact四键。static contract test必须同时匹配Java `codec.size()!=4`及四键`.isBoolean()`，fake qualified须证明四键与两用户键全true。history绑定candidate-05 manifest/auth/host/lifecycle/result/post-consumption test六项及既有17项，共23项；asset仍为12项。prepared历史测试只校验manifest/auth/history/asset，不冻结未来必然失效的“输出不存在”断言；launcher在每次live preflight独立强制全部输出不存在。生产Adapter/Provider/API/DTO/角色/数据均不修改，candidate-06正式执行仍需新授权`GATE-049` | candidate-05 consumed history test；candidate-06 Python/host/Schema/tests/launcher/manifest/auth及Java disabled live test | 恢复跨语言四键契约一致性，保留严格拒绝和历史不可变性 |
| `DR-EMP-030` | Employee egress candidate-03固定使用全新run `employee-egress-v3-20260817-candidate-03`、schemaVersion 3、preparation gate `GATE-052`和live gate `GATE-024`。版本化launcher必须在Maven/Spring前exclusive-create并fsync统一journal；测试范围Java `EmployeeEgressCandidateV3LiveIntegrationTest`显式绑定`EmployeeServiceApplication`，复用candidate-06四字段non-real fixture、参数化BINARY SQL、显式事务和3/1/1预算，只续写precheck/insert/verify并启动唯一Python live test。若Spring上下文在JUnit前失败，launcher以同journal/fallback pending形成有限`failed_unconsumed`；若INSERT后宿主异常且清理不可证明，必须形成`failed_cleanup_required`。Python复用生产Employee definition/settings/`BoundBusinessActionHandler`/user projector/`BusinessEgressProjector`，在同一journal写detail 1/1，并且仅当egress safe payload严格只含`position/work_base_si`、禁止字段和值计数为0时构造现有answer generator。模型transport先写started，再在第1次delegate紧邻前写consumed，固定30次、无retry/resume；每次都有唯一terminal且不保存响应。Python退出后Java无论成功失败均finally执行exact delete/remaining并写pending；Java必须从唯一journal重建detail/model计数并与staging交叉校验，staging丢失不得把已发生调用记为0。launcher删除并扫描原始日志后使用同模块finalizer写host validation/run terminal和strict result；cleanup结果必须使用pending实际`deleted/remaining`而非阶段存在性推断。完整成功必须由同一validator接受76条记录，且inserted/verified/deleted=1、remaining=0、detail1/1、answer30/30、有效≥27、其他端点/禁止字段/敏感字面量/log/retry/resume=0；清理不能证明时终态优先`failed_cleanup_required`，模型marker决定其余失败为`failed_unconsumed/failed_consumed`。manifest绑定candidate-06五项资格SHA、fixture/metadata证据、旧egress历史、授权证据、生产接缝与直接测试；prepared阶段只允许fake/static/disabled验证与故障注入，正式输出必须不存在。不得改生产src/API/DTO/角色/数据或读取密钥；冻结后须以run/hash/auth和精确预算再次授权`GATE-024` | candidate-03 Python lifecycle/validator/finalizer、Java disabled宿主、versioned launcher、五份strict Schema、manifest/auth及direct/preparation/history/live-opt-in测试 | 把已验证合成输入安全承接到Employee真实结果模型出域，不建立第二套生产流程 |
| `DR-EMP-031` | candidate-03唯一live按冻结run执行并形成76条lifecycle、3/1/1、detail1、30个model terminal、cleanup deleted1/remaining0，终态为`failed_consumed/threshold_not_met`，30项全部`invalid_output`且有效0；五项证据SHA必须不可变。answer v2只修复模型可见行内fact marker约束，不改变Employee field matrix、facts、safe payload、grounding、接口、角色或数据。生产组合根切换v2后，candidate-03只按冻结提交/精确哈希做历史校验，不得重跑。candidate-04必须使用全新run/manifest/auth并绑定answer v2 task/source、新bootstrap、candidate-03五项失败历史、candidate-06资格和既有授权证据；prepared仅fake/static/disabled，正式live仍须另行精确授权`GATE-024` | 后续candidate-04 versioned测试/launcher/manifest/auth；candidate-03 consumed-history只读测试 | 以新候选验证v2，不篡改已消费失败历史 |
| `DR-EMP-032` | Employee live bootstrap使用独立run/manifest/authorization，并精确绑定candidate-04 manifest/auth、versioned wrapper/helper、strict lifecycle/failure Schema、direct/history tests与source commit；candidate-04本身字节不变。wrapper须在任何敏感值读取和进程启动前exclusive-create+fsync lifecycle，顺序执行asset preflight、auth配置解析、随机HMAC生成、auth进程启动、`/public/test` readiness、ADMIN login/token内存提取、candidate-04 launcher调用和cleanup。不得由wrapper启动第二个Employee服务：既有`EmployeeEgressCandidateV4LiveIntegrationTest`继续唯一创建RANDOM_PORT Employee上下文、synthetic fixture、detail、model和exact cleanup。任何candidate调用前失败形成`failed_pre_candidate_unconsumed`，candidate lifecycle/consumed/result不存在且SQL/detail/model=0；进入candidate后outer不得复制其76事件或计数，只记录invoke terminal。所有原始日志位于临时目录，扫描HMAC/JWT/标识/key后删除；只停止本次启动且PID/监听归属核实的auth进程。non-live使用fake process/HTTP/config/filesystem覆盖逐阶段失败、PID所有权、secret零落盘和candidate零调用，不读取真实环境或启动服务 | 建议新增Employee bootstrap module、versioned PowerShell launcher、strict Schema/manifest/auth和direct/history tests；复用公共`business_egress_live_bootstrap.py` | 把auth/JWT宿主纳入冻结边界，不改变Employee生产代码、公开API、角色、field matrix或candidate-04；`GATE-058`关闭后可冻结wrapper，`GATE-024`只授权其一次执行，成功仍由`GATE-033/SA-GATE-006[Employee]`判定 |
| `DR-EMP-033` | wrapper-v1虽处于`prepared_unconsumed`且outer/inner输出不存在，但它与Transaction失败wrapper共享公共v1 helper和auth JAR存在性检查；其manifest未冻结实际auth JAR，提前退出只能保留宽泛`process_exited`。v1 source/manifest/auth/history必须保持字节不变并转为只读历史，不得执行或原地改造。wrapper-v2使用全新run/manifest/auth，复用公共`business_egress_live_bootstrap_v2.py`和strict diagnostic Schema，只冻结outer实际启动的`auth-service/target/auth-service-0.0.1-SNAPSHOT.jar`；manifest记录确定性命令`mvn -f serviceCenter/pom.xml -pl :auth-service -am -DskipTests package`、源码commit和JAR SHA。preflight须同时校验tracked assets、v1 prepared历史、candidate-04、build/source/command及JAR；任一漂移在进程前失败。auth进程提前退出时，cleanup在秘密扫描和原始日志删除前只写service=`auth-service`、当前auth phase、exitCodePresent布尔、公共六分类之一和安全计数；不得写原始日志、异常、路径、配置、用户、JWT/key/HMAC或字段值。wrapper-v2仍只启动auth并调用冻结candidate-04，Employee RANDOM_PORT服务、3/1/1、detail1、answer30、consume和cleanup继续由inner唯一权威。non-live覆盖JAR漂移、build/source/command漂移、六分类+unknown、日志删除、秘密零落盘、v1/candidate历史及全部正式输出不存在 | 建议新增`employee/live_bootstrap_v2.py`、candidate-02 launcher、direct/preparation/history测试及manifest/auth；复用公共v2 helper/Schema，不修改v1 | 消除已证实的共享宿主风险，不改变生产Employee/API/角色/字段或candidate-04；`GATE-062`关闭仅允许更新`GATE-024`精确绑定，不得据此执行live或关闭`GATE-033/SA-GATE-006` |
| `DR-EMP-034` | wrapper-v2资产哈希全部匹配且outer终态为`failed_pre_candidate_unconsumed`，直接根因是共享`execute_bootstrap()`先exclusive-create lifecycle，随后Employee `_asset_preflight()`把包含该当前文件的`output_paths()`整体判为冲突。不得删除防重放检查、放宽manifest或修改旧run。建议新增独立wrapper-v3：`run()`在调用共享executor前确认全部outer/inner输出不存在；共享`BootstrapJournal`继续以`"x"`独占当前lifecycle；phase preflight复核冻结资产时排除当前lifecycle，仅检查outer result/diagnostic及所有inner输出仍不存在。必须用真实executor+真实preflight的full-path fake覆盖成功越过asset phase、预存lifecycle由journal拒绝、预存其他outer/inner输出由preflight拒绝、candidate最多调用1及外部调用0。新manifest绑定wrapper-v2 manifest/auth/lifecycle/result SHA、candidate-04与auth JAR/source/build；v1/v2 source及全部历史保持字节不变 | 建议新增`agent-runtime/tests/integration/adapters/employee/live_bootstrap_v3.py`、candidate-03 host launcher、direct/full-path/preparation/history测试、manifest/auth | 只修复Employee test-only outer顺序，不修改生产Employee、API、角色、字段、3/1/1+detail1+answer30预算、candidate-04或公共契约；`GATE-063`关闭仅解锁新`GATE-024`申请，真实执行和完成门禁仍Open |
| `DR-EMP-035` | 当前交付周期严格分离执行许可、实验验收和工作包状态。`WP-EMP-EGRESS-LIVE-BOOTSTRAP-03-PREP`与`WP-EMP-EGRESS-01`转Deferred，P3 `GATE-063/024/033`为Not Applicable；这一治理变化不得修改wrapper-v2失败、candidate-04或任何历史资产，也不得把历史30/27阈值解释为已达到。历史run、manifest、hash、candidate、JAR与HEAD只作审计，不是当前执行入口或可复用授权。`WP-SYSTEM-E2E-01`直接依赖已完成的`WP-EMP-REAL-01`，以真实Provider、真实ADMIN/VIEWER授权和默认stub模型验证Employee链路，模型outbound固定0。`SA-GATE-006.EMPLOYEE`继续Open；未来恢复真实外发须先诊断，仅在新的未决决策或安全边界存在时新建工作包和有界门禁，并优先复用通用受控harness、全新run/authorization | 设计/计划治理，无Employee生产代码、API、角色、字段、配置或测试资产修改 | 恢复当前系统闭环且不削弱真实Employee数据默认不外发边界；历史实验可审计性保持，测试治理不再自动扩张 |

### 9.2 正常序列

1. Runtime 混合节点按 canonical ID 调用本地 Resolver；命中 8.2.1 时形成 `employee.detail` 最终候选且模型调用为零，识别但无效则返回 `invalid_argument` 且 HTTP 为零。
2. core 对最终候选执行公共 JSON 结构/大小/深度校验、同一注册项 validator 和单动作 claim，产生 `EmployeeDetailInput`；本地解析不能绕过该步骤。
3. handler 校验 context、opaque user token、取消和绝对 deadline；失败时网络为零。
4. mapper/codec 生成唯一详情 GET，common client 只向冻结的 employee-service origin 发送原用户 JWT。
5. 统一安全边界拒绝非法 role claim；Employee Controller 再于调用 `EmployeeService.detail` 前执行动作角色 guard，拒绝时 service/mapper/DAO 为零。
6. 2xx body 经 common 全局上限聚合后，由 Employee codec 以同一次 wire request 校验标识回显，并再校验≤65536 bytes及严格 JSON；未知宽字段只在受限临时 object 中存在，不能进入 typed response。
7. normalizer 产生一条 records result；公共 projector 构造掩码后的用户结果。
8. egress projector 计算配置/代码/全局交集；默认空时不调用答案模型，直接返回结构化结果。

### 9.3 配置

建议新增的动作前缀固定为 `AGENT_EMPLOYEE_DETAIL_`：

| key | 默认 | 约束 |
|---|---|---|
| `AGENT_EMPLOYEE_DETAIL_ENABLED` | `false` | Authority/契约未闭环前不得 true |
| `AGENT_EMPLOYEE_DETAIL_TIMEOUT_MS` | `2000` | 100～3000 |
| `AGENT_EMPLOYEE_DETAIL_MAX_RESULT_COUNT` | `1` | 必须精确为 1，仅为 common settings/definition 一致性校验，不提供扩展空间 |
| `AGENT_EMPLOYEE_DETAIL_USER_FIELDS` | 六个代码字段 | 子集且保留两个 required |
| `AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS` | 空 | 仅 `position,work_base_si` 子集 |
| `AGENT_EMPLOYEE_DETAIL_USER_TRANSFORMS` | 代码表固定选择 | 每个启用用户字段恰一允许枚举 |
| `AGENT_EMPLOYEE_DETAIL_MODEL_TRANSFORMS` | 空 | 每个启用模型字段恰一 `bounded_text` |

服务 origin 使用组合根通用 `employee-service` binding，不使用本动作 key 覆盖 URL。未知前缀键、重复字段、移除 required、添加 filter/sort/page 参数或非法转换均阻止 Runtime 就绪。

### 9.4 `VAL-EMP-005` 测试临时路由流程

1. opt-in runner 在进程内生成合成 sentinel、随机 HMAC 测试密钥、合成 user JWT、correlation ID 与空闲端口；这些值不得写入代码、fixture 或 evidence。
2. runner 启动隔离的 Servlet `employee-service` 测试实例，并以命令行测试配置启动实际 Gateway 可执行包；只在该测试进程中注册 `/employees/**` 到隔离 Servlet 的临时路由，同时关闭服务发现和远程配置。
3. runner 经 Gateway 发起恰好一次详情 GET；合成 sentinel 必须命中 `EmployeeController`，预期不存在数据时保持现有 400，且 `EmployeeService.detail`/mapper 各恰好一次、其他 Employee 方法为零。
4. 子进程在 `finally` 中停止。runner 对 Gateway、Servlet、测试报告和进程输出执行 exact-value 扫描；sentinel、编码 sentinel、JWT、HMAC 密钥、subject 与完整 path 任一命中即失败。
5. 无论成功失败，原始日志和测试报告都必须在扫描后删除；只有符合严格 Schema、且不含上述敏感值的有限 evidence 可以持久化。正式 `GatewayRouter` 与默认配置必须保持无 Employee 路由。

### 9.5 candidate-02 非 live 生命周期与终态

1. launcher 在读取敏感输入前校验 candidate-02 manifest/authorization、候选自身资产以及 candidate-01 四项历史哈希；任何漂移均在创建运行 journal 和业务/模型调用前失败。
2. live test 取得输出路径后立即 exclusive create lifecycle journal；header 只含 schema/run/manifest/authorization、预算及 `retryAllowed=false/resumeAllowed=false`，不得含时间以外的运行值。
3. `LiveEmployeeTransportV2.send` 只允许一次固定详情 GET：进入 `send` 后、调用 `httpx` 前 append+flush+fsync `employee_detail_started`，响应或受控异常后写唯一 `employee_detail_terminal`。started 数是 Agent侧 `employeeDetailRequests` 的唯一计数来源；success evidence 必须为1，pre-request failure 可为0；不得把该客户端调用计数表述为下游服务接收计数。
4. 响应、状态、投影和模型初始化成功后才构造模型 transport。首次请求在 task/字段/禁止字面量校验通过后，先 exclusive create consumed marker，再写并 fsync `model_outbound_started`，随后调用真实 delegate；两步之间异常仍属于 `failed_consumed`，不得删除 marker或补跑。
5. `finally` 不假定模型 journal 已存在；它从 lifecycle journal 和 consumed marker 构造唯一终态。未消费失败写 `failed_unconsumed`，已消费失败写 `failed_consumed`，30/30终态且有效回答≥27才写 `passed`。有限失败阶段仅允许 `employee_request`、`employee_result`、`egress_projection`、`model_setup`、`model_call`、`threshold`、`cleanup`、`internal`；原因只用相应版本化有限枚举。

### 9.6 输入资格筛选流程

1. runner 校验八项 candidate 历史哈希，确认未读取/透传 `LLM_API_KEY`，并以随机 HMAC 启动隔离 auth-service。
2. Java opt-in test 优先读取维护者已确认标识；缺失时执行固定只读 SQL，数据库只返回一个标识且 `LIMIT 1`，字段值不从筛选查询返回。
3. Java test 启动随机端口隔离 employee-service，把标识、实际 ADMIN JWT、base URL 和临时 evidence 路径只放入 Python 子进程环境。
4. Python probe 通过既有 `employee.detail` handler 发起恰好一次 GET，读取本次结果的两个字段存在性与既有 egress disposition/reason；不构造模型组件。
5. Java spy 复核 service/mapper detail 各一次且其他业务方法为0；runner 扫描所有临时日志和 evidence，删除原始日志/surefire 输出，再把 strict 有限 evidence 原子移动到版本化 evidence 目录。
6. 只有 `qualified` 才允许下一轮申请 candidate-03 设计/准备；`not_qualified/failed` 均停止，不能再次执行 candidate-02 或直接申请模型 live。
6. 可控异常路径必须先写 run terminal，再 exclusive create evidence；证据写失败时保留已 fsync journal/marker并由 launcher 只返回 `employee.egress_candidate_evidence_write_failed`，不得生成替代“passed”文件。raw service/launcher 日志仍按既有规则扫描删除。
7. candidate-01 的 manifest、authorization、环境诊断和 pre-model failure evidence 继续只读；candidate-02 preparation/history tests 必须逐文件重算并锁定其 SHA-256，禁止把 candidate-01 未消费状态解释为可重试授权。

### 9.7 synthetic fixture 准备流程（`GATE-050`关闭后方可实施）

1. 先校验源 evidence 与完整schema/constraint/trigger元数据结论；任一漂移或未知在创建fixture journal前失败。
2. 以全新run exclusive-create并fsync有限lifecycle；确定性synthetic标识和值只驻留执行进程及测试数据库生命周期，不进入日志/evidence。
3. precheck确认标识不存在；只允许单次INSERT，并以标识+四字段fingerprint确认恰好一条且codec最小字段均有效。
4. 后继资格运行只消费内存标识；无论资格成功或失败，finally都执行一次精确DELETE并确认不存在。
5. 清理不能证明完成时保留`failed_cleanup_required`有限证据并停止；不得自动重试、改用宽条件删除、创建candidate或进入模型调用。

## 10. 失败类型、权限与审计

### 10.1 失败类型与错误码矩阵

| 触发 | Service result | 公共结果 | 下游/模型调用 |
|---|---|---|---|
| context/JWT 缺失 | unauthenticated | `business.missing_user_token` | HTTP 0/模型 0 |
| token 认证失败 | unauthenticated | `business.downstream_unauthenticated` | Controller 后 0/模型 0 |
| Authority 明确拒绝/不可判定 | forbidden | `business.downstream_forbidden` | service/DAO 0/模型 0 |
| 输入格式非法或 Employee 400 | invalid_argument | `business.invalid_arguments` | 至多 HTTP 1/模型 0 |
| Employee 2xx 合法 | records | success | HTTP 1/模型 0 或 1 |
| Employee 204 | invalid_response | `business.invalid_response` | HTTP 1/模型 0 |
| Employee 404（未声明 no-result） | downstream_failure(`unavailable`) | `business.downstream_failure` | HTTP 1/模型 0 |
| 目标字段缺失/类型错/body 超限 | invalid_response | `business.invalid_response` | HTTP 1/模型 0 |
| required 投影失败 | records 后投影失败 | `business.minimum_user_result_not_met` | HTTP 1/模型 0 |
| timeout/429/5xx/协议失败 | timeout/rate_limited/unavailable | common 固定 code | HTTP≤1/模型 0 |

禁止解析 400/404 body、异常 message 或 `Employee not found` 字样决定状态。若业务服务后续提供明确 404 no-result 契约，须经公开契约确认后把 definition 的 `http_404_is_no_result` 改为 true 并同步 consumer/provider test。

### 10.2 权限与审计

建议 Employee 业务边界新增/修改的可观察方法为 `CapabilityAccessGuard.requireEmployeeRead(Authentication)`：先调用现有 `requireUser(authentication)`，再从 `authentication.getAuthorities()` 读取不可变快照，并在至少一个 authority 精确等于 `ROLE_ADMIN` 或 `ROLE_VIEWER` 时允许，否则抛无敏感正文的 403。它不做大小写转换、不解析原始 `role` claim，也不按 `dylan` 用户名判断；缺失、未知、大小写错误或已知+未知混合 role 必须已由统一 converter 在进入 Controller 前整体拒绝，不能靠 guard 从原 claim 重做映射。`EmployeeController` 构造器必须新增注入 `CapabilityAccessGuard`，`detail(Authentication,String)` 必须先调用 guard，再且仅再调用一次 `EmployeeService.detail`。

`BQ-GATE-003` 的响应可见性证据不能只由 Adapter 测试反推。建议 Employee 方在 provider 测试资源中新增版本化、无真实数据的 `employee-detail-response-visibility-v1.json`，至少冻结 endpoint、允许角色 `ADMIN/VIEWER`、当前 `Employee` 序列化字段名全集和 policy version；维护者对该证据作明确确认后，provider contract test 才能证明实际 200 字段集合与已确认策略一致。若 Employee 方不能确认完整字段集对两个角色均可见，则该 fixture 不得伪造，必须转入窄 DTO/endpoint 的单独设计与授权。

日志只允许 correlation ID、`employee.detail`、有限状态、耗时、响应字节数和配置 snapshot ID。禁止 JWT、subject、原始/掩码员工标识、姓名、邮箱、完整 path、响应字段、异常 message/stack。Gateway 全局过滤器不得打印或拼接完整 path；本阶段直接删除现有完整 path 输出，不新增掩码副本或独立监控依赖。`VAL-EMP-005` 必须以一次合成 sentinel 请求扫描 Gateway/Servlet 原始日志，并在形成有限证据后销毁原始日志。

### 10.3 事务边界与一致性

Adapter 不创建事务，不写缓存、数据库、消息或索引。一次详情 GET 的数据一致性由 `employee-service` 当前查询提供；Adapter 只保证同一冻结 definition/settings、一次响应和不可变投影。重复请求是新的只读查询，不自动重试或声称跨请求快照一致。

## 11. 数据生命周期、发布与回滚

### 11.1 数据生命周期

原始标识只存在于当前 input、编码 path 和业务调用；现有宽详情的 2xx 原始 body 会先在 common 客户端中以最多 `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` 请求级字节聚合，Employee codec 只接受≤65536 bytes，并可能短暂构造包含未知字段的受限 JSON object。构造六字段 typed response 后必须解除原始 bytes/object 引用，不能声称未知字段从未进入 Agent 进程。原始/掩码标识和 Employee 字段均不持久化、不缓存、不写日志。模型 safe payload 若被全局允许，也只能含职位/工作地和请求内 `record_ref`。

### 11.2 发布与回滚

1. 先用 synthetic Employee fake 完成 Python definition/codec/字段/失败测试。
2. 在修改详情 guard 前盘点现有 `GET /employees/{idCardNo}` 调用方及其角色；不能证明所有合法调用方均满足新角色契约时，`BQ-GATE-003` 不得关闭。
3. 再单独实施并验证 Authority converter、Employee detail guard 和完整响应 visibility fixture；不同时改变响应 DTO。
4. 真实动作初始仍 disabled；完成 provider/consumer、访问日志和角色矩阵后才允许启用。
5. `VAL-EMP-005` 仅以测试临时路由执行；测试结束后停止隔离进程并删除原始日志，正式 `GatewayRouter` 无需回滚。完整 path 输出不得因测试结束而恢复。
6. Agent 侧回滚只将 `AGENT_EMPLOYEE_DETAIL_ENABLED=false` 并重启 Runtime。Provider guard 失败时先停用 Agent 并阻断该详情入口的非预期流量，再按 provider 版本回滚；不得把“恢复任意 authenticated 用户可读宽实体”作为自动降级。公开行为恢复涉及安全接受，必须由 Employee 方明确决定。

本文不含数据迁移。若后续把详情响应改为窄 DTO 或修正 404，必须制定公开契约兼容/回滚方案，不能只改 Adapter 猜测。

## 12. 实现落点与关键签名

### 12.1 实现落点

| 编号 | 状态 | 路径/符号 | 责任 | 规则 |
|---|---|---|---|---|
| `IMPL-EMP-001` | 已存在并验证 | `agent-runtime/src/agent_runtime/adapters/employee/definition.py` `employee_detail_definition()` | 冻结 descriptor/limits/fields/status | `DR-EMP-001/002` |
| `IMPL-EMP-002` | 已存在并验证 | `agent-runtime/src/agent_runtime/adapters/employee/contracts.py` | input/wire response/record | `DR-EMP-001/005` |
| `IMPL-EMP-003` | 已存在并验证 | `agent-runtime/src/agent_runtime/adapters/employee/codec.py` | validator/mapper/GET encode/strict decode | `DR-EMP-002/005/009/010` |
| `IMPL-EMP-004` | 已存在并验证 | `agent-runtime/src/agent_runtime/adapters/employee/normalizer.py` | 合法 2xx→一条 records | `DR-EMP-005/008` |
| `IMPL-EMP-005` | 已存在并验证 | `agent-runtime/src/agent_runtime/adapters/employee/fields.py` | 六字段 extractor/class/transform | `DR-EMP-005/006/007` |
| `IMPL-EMP-006` | 已存在并验证 | `agent-runtime/src/agent_runtime/adapters/employee/settings.py` | 精确 env fragment/default/校验 | `DR-EMP-002/007` |
| `IMPL-EMP-007` | 已存在并验证 | `agent-runtime/src/agent_runtime/adapters/employee/provider.py` `EmployeeDomainProvider` | definition/config fragment；不建 client | `DR-EMP-001/009` |
| `IMPL-EMP-008` | 已存在并验证 | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java`、`EmployeeDetailSecurityConfiguration.java` | Employee 读 Authority 判定与 endpoint-scoped 安全链 | `DR-EMP-003/004` |
| `IMPL-EMP-009` | 已存在并验证 | `employee-service/src/main/java/com/dylan/employee/controller/EmployeeController.java` 构造器与 `detail` | 注入 guard；详情调用前执行业务 guard | `DR-EMP-004` |
| `IMPL-EMP-010` | 已存在并验证 | `employee-service/src/test/resources/contracts/employee-detail-response-visibility-v1.json`、`employee-detail-callers-v1.json` | 冻结维护者确认的角色、完整响应字段、policy version 和仓库调用方；无业务值 | `DR-EMP-004/005` |
| `IMPL-EMP-011` | 已实现并通过非 live 验证 | `gateway-service/src/main/java/com/dylan/springgateway/config/GatewaySecurityConfig.java` `authTokenFilter(JwtDecoder)` | 删除完整请求 path 的标准输出；认证、JWT 转发和 `X-USER-ID` 行为不变 | `DR-EMP-012` |
| `IMPL-EMP-012` | 已实现并验证 | `gateway-service/src/test/java/com/dylan/springgateway/config/GatewaySensitivePathLoggingTest.java` | 以合成 path/token 调用过滤器并捕获输出，证明不回显敏感输入；保留无正式 Employee 路由契约 | `DR-EMP-012` |
| `IMPL-EMP-013` | 已实现并验证 | `employee-service/src/test/java/com/dylan/employee/live/EmployeeGatewayLogSafetyLiveIntegrationTest.java`、`agent-runtime/scripts/run-employee-gateway-log-live.ps1` | opt-in 隔离 Servlet + actual Gateway 测试临时路由；单次合成请求、到达计数、全临时目录扫描/销毁；初版签名字节错误已修正且唯一重试 evidence 已通过 | `DR-EMP-004/008/012` |
| `IMPL-EMP-014` | 已实现并验证 | `agent-runtime/tests/integration/adapters/employee/evidence/employee-gateway-log-evidence-v1.schema.json` 及 `agent-runtime/tests/integration/adapters/employee/evidence_contract.py` 对应校验 | 严格限制 evidence 为状态、计数、隔离方式和零泄漏结论，不允许 sentinel/JWT/path/正文 | `DR-EMP-012` |
| `IMPL-EMP-015` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/action_resolver.py` `EmployeeDetailLocalActionResolver`；修改 `definition.py/provider.py` 绑定 | 实现 8.2.1 有限语法并返回公共 `LocalActionResolution`；definition 代码绑定同 ID Resolver | `DR-EMP-013` |
| `IMPL-EMP-016` | 建议新增（测试范围） | `agent-runtime/tests/integration/adapters/employee/egress_candidate_v2.py`；`employee-egress-live-evidence-v2.schema.json` | 定义 candidate-02 常量、有限枚举、`EmployeeEgressLifecycleJournalV2`、strict journal/evidence/manifest/authorization validator 与 budgeted transport；不复用或修改 candidate-01 模块 | `DR-EMP-014` |
| `IMPL-EMP-017` | 建议新增（测试范围） | `agent-runtime/tests/integration/adapters/employee/test_real_employee_egress_candidate_v2.py`；`agent-runtime/scripts/run-employee-egress-live-candidate-02.ps1` | 以真实 handler/transport/answer/grounding 接缝执行 v2；所有可控失败形成有限 terminal/evidence；launcher 做版本化双重预检、敏感日志清理和有限退出码映射 | `DR-EMP-014` |
| `IMPL-EMP-018` | 建议新增（测试范围） | `test_employee_egress_candidate_v2_preparation.py`、`test_employee_egress_candidate_v2_harness.py`、`test_employee_egress_candidate_01_history.py` 及 candidate-02 manifest/authorization（仅后续实施时创建） | fake 逐阶段故障注入、预算/消费/终态/Schema 验证和 candidate-01 四项精确哈希反证；不得创建 live 结果或读取密钥 | `DR-EMP-014` |
| `IMPL-EMP-019` | 建议新增（测试范围） | `agent-runtime/tests/integration/adapters/employee/egress_input_qualification.py`；`evidence/employee-egress-input-qualification-v1.schema.json` | 定义 run、有限 status/reason、strict evidence builder/validator、两个字段存在性和零泄漏契约 | `DR-EMP-015` |
| `IMPL-EMP-020` | 建议新增（测试范围） | `agent-runtime/tests/integration/adapters/employee/test_real_employee_egress_input_qualification.py`；`test_employee_egress_input_qualification.py` | fake 证明合格/缺字段/失败与严格 Schema；opt-in probe 复用真实 handler 发起一次 detail，模型组件为零 | `DR-EMP-015` |
| `IMPL-EMP-021` | 建议新增（测试范围） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressInputQualificationLiveIntegrationTest.java`；`agent-runtime/scripts/run-employee-egress-input-qualification.ps1` | Java 进程内只读选择、随机端口 Employee、真实 ADMIN JWT、Python probe、service/mapper计数、敏感扫描与原始日志删除 | `DR-EMP-015` |
| `IMPL-EMP-022` | 已新增（测试范围） | `agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v2.py`；`evidence/employee-egress-input-qualification-v2-{lifecycle,result}.schema.json` | v2 run常量、exclusive/fsync journal、严格顺序/0或1计数、有限终态/result、manifest/auth/history validator | `DR-EMP-016` |
| `IMPL-EMP-023` | 已新增（测试范围） | `test_employee_egress_input_qualification_v2.py`；`test_real_employee_egress_input_qualification_v2.py` | fake阶段故障/strict反证；未来opt-in通过现有handler/codec/projectors发起一次detail并先写临时有限结果 | `DR-EMP-016` |
| `IMPL-EMP-024` | 已新增（测试范围） | `employee-service/.../EmployeeEgressInputQualificationV2LiveIntegrationTest.java`；`agent-runtime/scripts/run-employee-egress-input-qualification-candidate-02.ps1`；candidate-02 manifest/authorization | 查询前journal、codec-complete只读SQL、版本化binding/history校验、日志清理后正式result；prepared阶段live开关关闭 | `DR-EMP-016` |
| `IMPL-EMP-025` | 已新增并验证（测试范围） | `agent-runtime/tests/integration/adapters/employee/egress_input_qualification_diagnostic_v2.py`；`evidence/employee-egress-input-qualification-diagnostic-v2.schema.json`；直接Python测试 | strict final/staging loader/validator、日志清理后finalizer、计数关系、首个归零枚举、candidate-02两项SHA-256及禁止字段反证 | `DR-EMP-017` |
| `IMPL-EMP-026` | 已新增并验证（测试范围） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest.java` | opt-in `WebEnvironment.NONE`、查询前历史hash、单次`queryForMap`聚合、单行计数、exclusive+fsync staging；不加载auth/JWT/HTTP/model | `DR-EMP-017` |
| `IMPL-EMP-027` | 已新增并验证（测试范围） | `agent-runtime/tests/integration/adapters/employee/work_base_static_diagnostic.py`；`test_employee_work_base_static_diagnostic.py`；`evidence/employee-work-base-static-diagnostic-v1.{schema.json,20260814-run-01.json}` | strict loader/validator、聚合evidence与9项源码hash、映射/写入/资产计数、有限诊断/未知项和全零外部调用反证 | `DR-EMP-018` |
| `IMPL-EMP-028` | 建议新增并已完成非live前置 | `employee-service/src/test/java/com/dylan/employee/live/EmployeeWorkBaseDataDiagnosticLiveIntegrationTest.java`；`agent-runtime/tests/integration/adapters/employee/work_base_data_diagnostic.py`、`test_employee_work_base_data_diagnostic.py`、`run_employee_work_base_data_diagnostic.ps1`及`evidence/employee-work-base-data-diagnostic-v1.schema.json` | 两条只读SQL、strict staging/final evidence、互斥分区、snapshot drift、日志清理及零外部调用反证 | `DR-EMP-019` |
| `IMPL-EMP-029` | 已实现并通过non-live验证 | `agent-runtime/tests/integration/adapters/employee/employee_test_data_fixture.py`、`evidence/employee-test-data-fixture-v1.schema.json`、`test_employee_test_data_fixture.py` | deterministic synthetic spec、metadata前置、repository Protocol/in-memory fake、strict lifecycle/evidence、consumer/finally cleanup及逐阶段故障；未来真实repository/live test/launcher不存在 | `DR-EMP-020`；不访问数据库 |
| `IMPL-EMP-030` | 已新增；run-01失败关闭 | `agent-runtime/tests/integration/adapters/employee/fixture_metadata_diagnostic.py`、`run_employee_fixture_metadata_diagnostic.ps1`、success/failure Schema/evidence与history test；`employee-service/.../EmployeeFixtureMetadataDiagnosticLiveIntegrationTest.java` | 四条只读metadata查询、Provider列对齐、严格成功判定、触发器正文内存分类、有限失败证据和原始报告清理 | `DR-EMP-021`；不包含fixture repository或业务数据访问 |
| `IMPL-EMP-031` | 已新增并验证（测试范围） | `agent-runtime/tests/integration/adapters/employee/fixture_metadata_diagnostic_v2.py`；`evidence/employee-fixture-metadata-diagnostic-v2-{lifecycle,success,failure}.schema.json` | v2常量、exclusive/fsync journal、四phase顺序、fake执行/故障、strict result/finalizer、manifest/auth与三项历史校验 | `DR-EMP-022` |
| `IMPL-EMP-032` | 已新增并完成disabled编译（测试范围） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest.java` | 四条投影不变且名称显式BINARY的只读SQL；查询前journal；完整metadata或有限failure staging | `DR-EMP-022`；默认disabled，不访问数据库 |
| `IMPL-EMP-033` | 已新增并冻结（测试范围） | `run_employee_fixture_metadata_diagnostic_v2.ps1`、candidate-02 manifest/authorization、`test_employee_fixture_metadata_diagnostic_v2.py`及history test | manifest/hash/prepared边界、日志扫描删除后finalize、PowerShell AST、七项asset与run-01三项历史反证 | `DR-EMP-022`；正式执行须新授权 |
| `IMPL-EMP-034` | 已修改并验证（测试范围） | `test_employee_fixture_metadata_diagnostic_v2.py`、`test_employee_fixture_metadata_diagnostic_v2_history.py` | prepared-only断言迁移为frozen commit blob验证；新增当前lifecycle/result精确hash、metadata和safety断言；保留manifest/auth与正式证据不可变 | `DR-EMP-023` |
| `IMPL-EMP-035` | 已完成冻结、live消费与history闭环（测试范围） | `agent-runtime/tests/integration/adapters/employee/employee_test_data_fixture_candidate.py`、两份strict Schema、candidate-01 manifest/authorization/lifecycle/result及直接/history测试 | candidate常量、source history、fsync lifecycle、strict result/finalizer/manifest validator与3/1/1证据精确hash | `DR-EMP-024` |
| `IMPL-EMP-036` | 已完成唯一一次live执行（测试范围） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeSyntheticFixtureCandidateLiveIntegrationTest.java` | 参数化BINARY SQL、显式TransactionTemplate、六阶段pending journal/staging、finally exact cleanup；inserted/verified/deleted=1、remaining=0 | `DR-EMP-024`；不可重跑 |
| `IMPL-EMP-037` | 已完成host finalization并冻结（测试范围） | `run_employee_test_data_fixture_candidate_01.ps1`、candidate直接/history测试 | binding/manifest、临时日志扫描删除、host finalization、环境清理与post-consumption历史校验 | `DR-EMP-024`；`GATE-051`已消费 |
| `IMPL-EMP-038` | 已实现并冻结（测试范围） | `agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v3.py`、两份strict Schema、manifest/auth及直接/history测试 | lifecycle/result/manifest/auth validator、fake repository+consumer、四终态、成功计数/原因语义与history hash | `DR-EMP-025` |
| `IMPL-EMP-039` | 已实现并disabled验证（测试范围） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressInputQualificationV3LiveIntegrationTest.java`、`test_real_employee_egress_input_qualification_v3.py` | RANDOM_PORT、显式事务、参数化exact SQL、生产投影detail probe、跨进程journal续号、异常terminal与finally cleanup | `DR-EMP-025` |
| `IMPL-EMP-040` | 已实现并冻结（测试范围） | `agent-runtime/scripts/run-employee-egress-input-qualification-candidate-03.ps1` | frozen binding、preflight历史/资产校验、临时auth/JWT与日志安全、模型密钥零暴露、host finalization | `DR-EMP-025` |
| `IMPL-EMP-041` | 已实现并冻结 | candidate-04 Python/strict Schema/direct/history tests | 新run常量、candidate-03失败历史锁定、pre-SQL host journal/result validator与既有v3资格契约复用 | `DR-EMP-026` |
| `IMPL-EMP-042` | 已实现并冻结 | `EmployeeEgressInputQualificationV4LiveIntegrationTest` | 显式`EmployeeServiceApplication.class`、继承v3参数化SQL/detail/cleanup规则，默认disabled | `DR-EMP-026` |
| `IMPL-EMP-043` | 已实现并冻结 | candidate-04 versioned launcher、manifest/authorization | Maven前journal、Spring失败有限化、日志扫描删除、11项asset与精确hash/prepared绑定 | `DR-EMP-026` |
| `IMPL-EMP-044` | 已完成历史固定；后继实现待另行授权设计 | `agent-runtime/tests/integration/adapters/employee/test_employee_egress_input_qualification_v4_history.py`及candidate-04三项append-only证据 | frozen HEAD与prepared资产不变；固定host/lifecycle/result SHA、实际15条序列、qualified/cleanup事实和冻结validator拒绝 | `DR-EMP-027` |
| `IMPL-EMP-045` | 已新增并冻结 | `agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v5.py`、`egress_input_qualification_v5_host.py`及v5 strict Schema/direct/host/history/live-opt-in测试 | schemaVersion 5；live同路finalizer写成对host_validation并在result前调用同一validator；history直接固定candidate-04六项与既有十一项，共17项 | `DR-EMP-028` |
| `IMPL-EMP-046` | 已新增（默认disabled） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressInputQualificationV5LiveIntegrationTest.java` | 复用v4显式`EmployeeServiceApplication`、fixture/detail/finally exact cleanup语义，仅切换v5路径、run与环境变量；disabled编译/跳过已验证 | `DR-EMP-028` |
| `IMPL-EMP-047` | 已新增并冻结 | `agent-runtime/scripts/run-employee-egress-input-qualification-candidate-05.ps1`、candidate-05 manifest/authorization | 预检新run/hash/auth、host journal、Java disabled/live入口和Python v5 finalizer；manifest SHA-256=`8b44a38ad6a02edd6db64b7c8e5fd02adee67a19ff1e9ef08e2ed3eb82f5ff74`，prepared authorization不授予live | `DR-EMP-028` |
| `IMPL-EMP-048` | 已新增并冻结 | candidate-05 post-consumption history test；candidate-06 Python/host及四份strict Schema/direct/host/history/live-opt-in测试 | 固定v5三项证据SHA、16事件和失败语义；v6 schemaVersion6、四键exact presence、23项history与12项asset | `DR-EMP-029` |
| `IMPL-EMP-049` | 已新增（默认disabled） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressInputQualificationV6LiveIntegrationTest.java` | 复用v5启动、预算、detail、lifecycle与finally cleanup；只将nested `codec.size()`改为4，保留outer/逐键/type严格校验 | `DR-EMP-029` |
| `IMPL-EMP-050` | 已完成并冻结 | `agent-runtime/scripts/run-employee-egress-input-qualification-candidate-06.ps1`、candidate-06 manifest/authorization、host/lifecycle/result及独立consumed-history测试 | preflight校验23项history/12项asset；唯一live形成16条同validator lifecycle、严格字段资格、3/1/1+detail1与exact cleanup；manifest/authorization/host/lifecycle/result五项SHA精确锁定，prepared authorization文件本身保持live=false且由外部一次性授权消费 | `DR-EMP-029` |
| `IMPL-EMP-051` | 已新增并冻结（默认disabled） | `agent-runtime/tests/integration/adapters/employee/egress_candidate_v3.py`、五份strict Schema及direct/preparation/history/live-opt-in测试 | 定义schemaVersion3统一journal、consumed、pending/staging/result、manifest/auth、76条validator、逐阶段fake与live同路finalizer；cleanup使用pending实际计数 | `DR-EMP-030` |
| `IMPL-EMP-052` | 已新增（默认disabled） | `employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressCandidateV3LiveIntegrationTest.java` | 显式生产启动类；复用四字段fixture、3/1/1和finally exact cleanup；从journal重建detail/model计数并只在内存传递identifier/JWT给唯一Python live test | `DR-EMP-030` |
| `IMPL-EMP-053` | 已新增并冻结 | `agent-runtime/scripts/run-employee-egress-live-candidate-03.ps1`、candidate-03 manifest/authorization | Maven前建立journal，preflight校验17项history/28项asset和输出不存在，fallback有限化上下文失败；prepared/live权限分离 | run=`employee-egress-v3-20260817-candidate-03`，manifest SHA-256=`901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e`，authorization=`P3_00:GATE-024`，live=false |
| `IMPL-EMP-054` | 已完成（test-only准备） | `agent-runtime/tests/integration/adapters/employee/egress_candidate_v4.py`、candidate-04五Schema/harness/preparation/history/live-opt-in、`run-employee-egress-live-candidate-04.ps1`、Java disabled宿主及manifest/auth | 复用candidate-03生命周期与Employee接缝，冻结answer v2/current bootstrap、candidate-03五项失败历史、candidate-06资格和既有授权；全新run/auth，prepared外部调用0 | `DR-EMP-031`；`GATE-054` Closed，live仍受`GATE-024` |
| `IMPL-EMP-055` | 已完成并冻结（test-only） | `agent-runtime/tests/integration/adapters/employee/live_bootstrap_v1.py`、`agent-runtime/scripts/run-employee-egress-live-host-candidate-01.ps1`、公共strict Schema、manifest/authorization、direct/history tests | 调用公共bootstrap helper，以固定Employee profile只启动auth、签发内存ADMIN JWT并调用既有candidate-04 launcher；未进入`agent-runtime/src`且未修改Java服务 | source commit=`038b6a0f54f5f8ace9a68e49073e5035279473da`；manifest/auth哈希见`VAL-EMP-026`；`GATE-058` Closed |
| `IMPL-EMP-056` | 已完成并冻结（test-only） | `agent-runtime/tests/integration/adapters/employee/live_bootstrap_v2.py`、`agent-runtime/scripts/run-employee-egress-live-host-candidate-02.ps1`、公共v2 ProcessDiagnostic/Schema、全新manifest/authorization及direct/preparation/history tests | 复用公共诊断类型与v1执行状态机，域内manifest校验器精确冻结唯一auth JAR；两步冻结源码commit与确定性构建产物，只读绑定wrapper-v1 prepared历史和candidate-04；共享Transaction v2文件、生产src/Java/API和inner生命周期均不变 | source commit=`37b51608b851d463a1b1f6e5a782589efba9c49d`；prepared HEAD=`4dff45bfe0fdb3be2787b4c2231e8859299d6570`；run=`employee-egress-live-bootstrap-v2-20260818-candidate-02`；manifest/auth/auth-JAR SHA-256=`899eb378df014085c6e419a1720be96994698457b1f248215e8df2374118b383`/`0f9d71d0636f956aa12c4928a91137e53a211a74718a66a30b8f29fd8eb63000`/`da59695336c6f2fd11581760b41f0958114ac1f9e728ad834ff1a25a7595a96b`；`GATE-062` Closed，仍不授权`GATE-024` live |
| `IMPL-EMP-057` | 建议新增（test-only） | 独立Employee wrapper-v3 module/launcher/full-path fake/preparation/history测试与新manifest/authorization | 复用共享executor、公共diagnostic/Schema与candidate-04；在executor前检查全部输出，asset phase仅排除本次lifecycle；绑定v2失败历史且不修改旧文件 | 未授权实施；须在`GATE-063`下冻结全新source/run/manifest/auth，外部调用0 |
| `IMPL-EMP-058` | 已完成（仅文档与计划治理） | L0/L1/L2 与 `P3_00` 的 Employee 当前交付边界同步；无生产代码、配置或测试资产修改 | 真实 `employee.detail` Provider、业务最终授权和默认 stub 模型用于系统 E2E；wrapper-v3与真实结果外发实验转 Deferred | `SA-GATE-006.EMPLOYEE`继续Open并禁止真实Employee结果模型出域；历史run和证据不可变 |

### 12.2 Python 关键方法

| 符号 | 签名 | 输入校验/输出 | 副作用 |
|---|---|---|---|
| `EmployeeDetailArgumentValidator.validate` | `def validate(self, arguments: JsonObject) -> EmployeeDetailInput` | 唯一标识字段；有限错误 | 纯函数 |
| `EmployeeDetailLocalActionResolver.capability_id` | `@property def capability_id(self) -> str` | 精确返回 `employee.detail`；不可配置 | 纯函数 |
| `EmployeeDetailLocalActionResolver.resolve` | `def resolve(self, question: str) -> LocalActionResolution` | question 已由 Runtime 做公共上限校验；只按 8.2.1 NFC/有限 token 解析；不得读取 JWT/配置 | 返回 no_match、单标识 candidate 或有限 invalid；无 I/O/日志/共享状态 |
| `EmployeeDetailRequestMapper.map` | `def map(self, input: EmployeeDetailInput, settings: BusinessActionSettings) -> EmployeeDetailWireRequest` | result=1/no extra dimension | 纯函数 |
| `EmployeeDetailWireCodec.encode` | `def encode(self, request: EmployeeDetailWireRequest) -> BusinessHttpRequest` | 唯一 GET path | 纯函数 |
| `EmployeeDetailWireCodec.decode_success` | `def decode_success(self, *, request: EmployeeDetailWireRequest, response: BoundedBusinessHttpResponse) -> EmployeeDetailWireResponse` | 仅2xx application/json；request为当前调用栈同一冻结对象；严格UTF-8、无BOM/trailing、duplicate key/NaN/Infinity拒绝；body≤65536；六字段exact type；响应ID与请求精确一致；未知字段仅临时解析后丢弃 | 有界内存纯函数；不保存请求期状态/原object |
| `EmployeeDetailResponseNormalizer.normalize_success` | `def normalize_success(self, response: EmployeeDetailWireResponse) -> BusinessServiceResult[EmployeeDetailRecord]` | 恰一 record | 纯函数 |
| `employee_detail_definition` | `def employee_detail_definition() -> BusinessActionDefinition[EmployeeDetailInput,EmployeeDetailWireRequest,EmployeeDetailWireResponse,EmployeeDetailRecord]` | 返回冻结代码上限、字段顺序与状态语义 | 纯函数 |
| `EmployeeDomainProvider.domain_id` | `def domain_id(self) -> BusinessDomainId` | 精确返回 `employee` | 纯函数 |
| `EmployeeDomainProvider.definitions` | `def definitions(self) -> tuple[BusinessActionDefinition[Any,Any,Any,Any], ...]` | 恰含 `employee.detail` | 纯函数 |
| `EmployeeDomainProvider.configuration_fragment` | `def configuration_fragment(self) -> BusinessConfigurationFragment` | 只投影 `AGENT_EMPLOYEE_DETAIL_*` 与 `employee-service` binding，不读取 `os.environ`/其他域 | 纯函数 |
| `EmployeeEgressLifecycleJournalV2.__init__` | `def __init__(self, path: Path, *, run_id: str, manifest_sha256: str) -> None` | run/hash 必须等于 candidate-02 代码常量；以 `x` 模式创建并 fsync header；已存在即失败 | 创建 append-only、无敏感值的测试证据文件 |
| `EmployeeEgressLifecycleJournalV2.record_employee_detail_started` | `def record_employee_detail_started(self) -> None` | 仅允许0→1；必须在唯一 `httpx.get` 之前完成 | append+flush+fsync；定义精确请求计数 |
| `EmployeeEgressLifecycleJournalV2.record_employee_detail_terminal` | `def record_employee_detail_terminal(self, *, status: Literal["completed", "failed"]) -> None` | 必须已有且仅有一次 started；不得携带异常文本 | append+flush+fsync；关闭域请求阶段 |
| `EmployeeEgressLifecycleJournalV2.record_run_terminal` | `def record_run_terminal(self, *, status: Literal["passed", "failed_unconsumed", "failed_consumed"], failure_phase: EmployeeEgressFailurePhase | None, failure_reason: EmployeeEgressFailureReason | None) -> None` | consumed marker 存在性必须与失败终态一致；`passed` 时 failure 为空且预算/阈值满足 | append+flush+fsync；恰好一次终态 |
| `validate_employee_egress_lifecycle_v2` | `def validate_employee_egress_lifecycle_v2(path: Path, *, consumed_path: Path, manifest_sha256: str) -> EmployeeEgressLifecycleSnapshotV2` | strict JSONL、顺序、计数、终态、run/hash/auth 和有限枚举；不读取业务值 | 只读；返回构造有限 evidence 所需的不可变计数快照 |
| `build_input_qualification_evidence` | `def build_input_qualification_evidence(*, selection_mode: QualificationSelectionMode, result: CapabilityResult, database_selection_rows: int, employee_detail_requests: int) -> dict[str, object]` | 仅接受0/1筛选行与恰好一次detail；从本次 domain result 计算两个 nonblank boolean，从既有 egress 得到有限原因；不接收标识/JWT/原始响应 | 纯函数；输出 strict 有限 evidence |
| `validate_input_qualification_evidence` | `def validate_input_qualification_evidence(value: object) -> dict[str, object]` | exact keys/types/enums；`qualified` 强制两字段true、reason=`qualified`、detail=1、other/model=0及全部安全项false/零 | 纯函数；不访问文件或环境 |
| `write_input_qualification_evidence` | `def write_input_qualification_evidence(path: Path, value: Mapping[str, object]) -> None` | 先 strict validate；目标须不存在 | exclusive create+flush+fsync；仅写有限 evidence |
| `fixture_metadata_diagnostic_v2.execute_fake_candidate` | `def execute_fake_candidate(lifecycle_path: Path, result_path: Path, operations: Sequence[Callable[[], object]]) -> None` | 恰好四项fake operation；目标文件不存在；固定phase顺序 | strict passed或首个失败result；有限错误 | 仅测试临时文件，无数据库 |
| `fixture_metadata_diagnostic_v2.validate_lifecycle` | `def validate_lifecycle(path: Path) -> list[Mapping[str, object]]` | 4～10条JSONL、连续sequence、run→query pair→run terminal | 冻结records；乱序/重复/失败后继续均拒绝 | 只读；launcher/tests |
| `fixture_metadata_diagnostic_v2.validate_manifest` | `def validate_manifest(manifest_path: Path, authorization_path: Path, repository_root: Path) -> None` | prepared/live=false、run/gate/auth/预算、七项asset与三项历史 | 成功无返回；漂移为有限错误 | launcher preflight，只读hash |
| `build_fixture_spec` | `def build_fixture_spec(seed: str) -> EmployeeFixtureSpec` | 版本化非敏感ASCII seed；返回固定四字段、非身份证格式标识和仅驻内存fingerprint | 纯函数；值不得进入日志/evidence |
| `EmployeeFixtureRepository` | `count_by_identifier(str) -> int`；`insert(EmployeeFixtureSpec) -> int`；`count_by_fingerprint(EmployeeFixtureSpec) -> int`；`delete_by_fingerprint(EmployeeFixtureSpec) -> int` | 所有计数严格0或1；不允许update、宽删除或重试 | 当前仅`InMemoryEmployeeFixtureRepository`；真实实现待新门禁 |
| `execute_fixture_lifecycle` | `def execute_fixture_lifecycle(*, repository: EmployeeFixtureRepository, metadata_result_path: Path, lifecycle_path: Path, evidence_path: Path, run_id: str, seed: str, consumer: Callable[[EmployeeFixtureSpec], None]) -> EmployeeFixtureExecution` | metadata/hash先于journal；precheck→insert→verify→consumer→cleanup单调，创建后finally清理 | exclusive+fsync测试文件；fake调用各≤1，retry/resume=0 |
| `validate_lifecycle`/`validate_evidence` | `def validate_lifecycle(path: Path) -> tuple[Mapping[str, object], ...]`；`def validate_evidence(value: object) -> Mapping[str, object]` | exact keys、阶段成对/顺序/terminal、contract/template/metadata hash、三终态和计数 | 只读或纯函数；禁止标识/fingerprint/值字段 |

### 12.3 Java 关键方法

| 类/方法 | 建议签名 | 前置/返回 | 副作用 |
|---|---|---|---|
| `CapabilityAccessGuard.requireEmployeeRead` | `void requireEmployeeRead(Authentication authentication)` | user JWT；含 `ROLE_ADMIN` 或 `ROLE_VIEWER`；否则 403 | 无 DAO 调用 |
| `EmployeeController.EmployeeController` | `EmployeeController(EmployeeService employeeService, CapabilityAccessGuard accessGuard)` | 两个依赖均由 Spring 注入并保存为 final | 仅装配依赖 |
| `EmployeeController.detail` | `Employee detail(Authentication authentication, @PathVariable String idCardNo)` | guard allow 后调用 service；保持现有 200/400 wire | 一次 service 调用 |
| `EmployeeService.detail` | 已存在 `Employee detail(String idCardNo)` | 本文不修改签名/异常 | 一次 mapper 读取 |
| `GatewaySecurityConfig.authTokenFilter` | `GlobalFilter authTokenFilter(JwtDecoder jwtDecoder)` | 保持既有认证/转发；不得读取 path 用于输出 | 每请求最多一次既有 header 转发；无 path 日志副作用 |
| `EmployeeGatewayLogSafetyLiveIntegrationTest.gatewayForwardsSingleSyntheticRequestWithoutPersistingSensitiveValues` | `void gatewayForwardsSingleSyntheticRequestWithoutPersistingSensitiveValues()` | 仅在 `RUN_EMPLOYEE_GATEWAY_LOG_LIVE=1` 运行；所有必要值来自进程环境 | 启停隔离 Gateway；发起恰好一次合成 GET；写不含敏感值的临时计数 |
| `EmployeeEgressInputQualificationLiveIntegrationTest.qualifiesSingleEmployeeWithoutPersistingSensitiveValues` | `void qualifiesSingleEmployeeWithoutPersistingSensitiveValues()` | `RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY=1`；维护者标识非空则直接使用，否则 `JdbcTemplate` 固定只读查询最多一行 | 启动 Python probe；真实 detail 恰好一次；写临时有限证据和计数，不输出标识/字段值 |
| `EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest.writesCollationNeutralFourQueryEvidenceWithDurableLifecycle` | `void writesCollationNeutralFourQueryEvidenceWithDurableLifecycle() throws Exception` | env路径与三项历史；只读事务；四条固定binary SQL | success/failure staging；查询失败抛有限测试异常 | 仅未来精确授权的opt-in数据库测试 |
| `EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest.executeQuery` | `List<Map<String,Object>> executeQuery(LifecycleWriter journal, String phase, int ordinal, String sql)` | 仅内部固定SQL/phase/ordinal | 0～128行或`MetadataQueryFailure` | 每phase一次`queryForList`，无retry |

## 13. 测试与验证设计

### 13.1 测试矩阵

| 测试编号 | 规则 | 层级 | 建议路径/场景 | 关键断言 |
|---|---|---|---|---|
| `TEST-EMP-001` | `DR-EMP-001/002` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_definition.py` | descriptor 全字段与固定 argument schema；validator 对 schema 内更严格边界；唯一动作/无 page/filter/sort/URL 配置 |
| `TEST-EMP-002` | `DR-EMP-001/009` | Architecture | 建议新增：`agent-runtime/tests/architecture/test_employee_adapter_boundaries.py` | 无 Transaction/Java/DB/ES/retry import；禁止路径不可达 |
| `TEST-EMP-003` | `DR-EMP-002/010` | Unit | 建议新增：`tests/unit/adapters/employee/test_codec_request.py` | Unicode/UTF-8/控制/Bidi/保留字符边界；单次编码且拒绝预编码 `%HH`；唯一 GET、无 query/body |
| `TEST-EMP-004` | `DR-EMP-003/004` | Java Unit/Contract | 已实现：`common-security/src/test/java/com/dylan/common/security/UserRoleJwtAuthenticationConverterTest.java`、`employee-service/src/test/java/com/dylan/employee/security/CapabilityAccessGuardTest.java`、`EmployeeDetailSecurityIntegrationTest.java` | guard 对 ADMIN/VIEWER allow；converter 对 unknown/mixed role 403；service token 401/Guard 403；拒绝时 service=0 |
| `TEST-EMP-005` | `DR-EMP-004/005` | Java MVC/Provider contract | 已实现：`employee-service/src/test/java/com/dylan/employee/controller/EmployeeControllerAuthorizationTest.java`、`EmployeeControllerResponseVisibilityContractTest.java`、`security/EmployeeDetailSecurityIntegrationTest.java` 和 12.1 的两个 fixture | deny 时 service=0；allow 恰一次；实际 200 序列化字段集合与维护者确认的 versioned fixture 精确一致；既有 400 保持 |
| `TEST-EMP-006` | `DR-EMP-005/006` | Contract | 建议新增：`agent-runtime/tests/contract/adapters/employee/test_detail_response.py` | 六字段exact type/limit；请求/响应ID相等与不匹配；两个并发请求交错响应不串状态；BOM/trailing/NaN/duplicate key；65536/65537 bytes；宽敏感字段可短暂解析但typed result/日志/错误零投影 |
| `TEST-EMP-007` | `DR-EMP-006` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_user_projection.py` | 5 字符/64 字符掩码与 4 字符拒绝；required 缺失不得变 no-result |
| `TEST-EMP-008` | `DR-EMP-007` | Unit | 已实现：`agent-runtime/tests/unit/adapters/employee/test_egress.py`、`agent-runtime/tests/fixtures/employee_egress_field_matrix.json` | exact matrix；model⊂user；默认空；配置只接受职位/工作地；safe facts 不含标识/姓名/邮箱；冲突拒绝 |
| `TEST-EMP-009` | `DR-EMP-007/011` | Model spy | 已实现：`agent-runtime/tests/integration/adapters/employee/test_sensitive_egress_zero_call.py` | production route/answer/grounding 接缝只用 fake transport；标识/姓名/邮箱/账户/凭证/注入/unknown 问题、无允许事实、策略冲突及最小结果缺失均模型 0；允许路径仅含职位/工作地 |
| `TEST-EMP-010` | `DR-EMP-008` | Parameterized | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_status_mapping.py` | 400→invalid_argument、204→invalid_response、未声明404→downstream_failure；401/403/429/5xx 精确且不读 body |
| `TEST-EMP-011` | `DR-EMP-009` | Async fake HTTP | 建议新增：`agent-runtime/tests/integration/adapters/employee/test_deadline_single_call.py` | ≤1 HTTP、无 retry、取消/迟到丢弃 |
| `TEST-EMP-012` | `DR-EMP-010/011` | Log/security | 建议新增：`agent-runtime/tests/integration/adapters/employee/test_sensitive_logging.py` | token/path/标识/字段/异常 sentinel 零出现 |
| `TEST-EMP-013` | `DR-EMP-012` | Java contract/opt-in live | 建议新增：`GatewaySensitivePathLoggingTest`、`EmployeeGatewayLogSafetyLiveIntegrationTest`、runner/evidence contract tests | 过滤器输出不含 path/token；正式 Employee 路由仍不存在；一次请求确实到 Servlet；扫描命中数 0；原始日志已删除；evidence 严格且不含 sentinel/JWT/path |
| `TEST-EMP-014` | `DR-EMP-013` | Unit/Runtime contract | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_action_resolver.py` 及混合节点集成用例；覆盖五个 intent、前缀重叠的 polite/intent 最长匹配、四个 label、五个 operator、两类空格的 0/4/5 边界、无逗号/单逗号/双逗号、三种单一与重复终止标点、缺值/重复/附加子句/禁项/控制字符/超长/no_match，并让候选再经真实 Schema/validator | 合法问题产生唯一 `employee.detail` 参数且 selector/model/HTTP 为 0；同一文本不因 parser 实现产生不同值；识别后非法只返回有限 code；非法标识由最终 validator 拒绝；原问题/标识不进日志 |
| `TEST-EMP-015` | `DR-EMP-014` | Contract/fake integration/history | 建议新增：candidate-02 preparation/harness/history tests；对 manifest/auth、Employee request 前/中、响应映射、投影、模型设置、首 outbound 前/后、模型 terminal、阈值、cleanup/evidence 写入逐点故障注入 | journal 在 handler 前存在；Employee started/terminal与0或1精确计数一致；无 marker=`failed_unconsumed`，有 marker=`failed_consumed`；30/30且≥27才`passed`；每个初始化后可控失败均有有限 evidence；retry/resume、其他端点、禁止字段/字面量/日志泄漏均0；candidate-01四项hash不变 |
| `TEST-EMP-016` | `DR-EMP-015` | Contract/fake + opt-in live | `test_employee_egress_input_qualification.py`、`test_real_employee_egress_input_qualification.py`、Java live test 与 launcher AST/history tests | synthetic 合格/缺失/策略拒绝/请求失败；exact Schema拒绝额外键与敏感值；维护者/DB两种选择分支；数据库≤1行、detail/service/mapper各1、其他端点/方法/model=0；日志与最终 evidence 不含标识/JWT/HMAC/密码/字段值/原始响应；八项历史hash不变 |
| `TEST-EMP-017` | `DR-EMP-016` | Contract/fake/history/static integration | v2 module/tests、两份strict Schema、disabled Java live test、versioned launcher、manifest/authorization | journal先于数据库/detail；数据库/detail started/terminal各0/1；数据库失败/零候选/detail失败/重复/乱序均有限失败关闭；四codec字段、两required user字段和两egress字段绑定；launcher在外部进程前校验授权；退役run六项+egress八项hash不变；live lifecycle/result不存在 |
| `TEST-EMP-018` | `DR-EMP-017` | Contract/static integration/opt-in database（已通过） | diagnostic module、strict Schema、Python direct tests与Java aggregate test | 有效/额外键/负数/非单调/错误首零/禁止计数反证；源码精确一个`queryForMap`且SQL仅聚合、不选择原始列；candidate-02 lifecycle/result hash不变；真实执行只产生一行整数计数与有限evidence，Employee端点/model=0 |
| `TEST-EMP-019` | `DR-EMP-018` | Contract/static/history（已通过） | static diagnostic module、strict Schema/evidence与直接测试 | 聚合evidence/9项源码hash、Entity/ResultMap/SQL Provider八项映射、Map写入、DTO/required/default/backfill反证、版本化资产计数、ES下游边界、额外键/错误已知项/外部调用失败关闭及敏感值扫描 |
| `TEST-EMP-020` | `DR-EMP-019` | Contract/static/live-opt-in（非live已通过） | work-base data diagnostic Java/Python/launcher/Schema | 全NULL、混合无效、snapshot drift、分区和、额外查询、元数据类型、staging日志清理、恰好两次JdbcTemplate、无原始列/分组/HTTP/凭证/模型、静态evidence哈希及live evidence opt-in |
| `TEST-EMP-021` | `DR-EMP-020` | Contract/fake repository/fault injection（已通过） | `test_employee_test_data_fixture.py` | 16项覆盖metadata/schema、deterministic spec、正常create/verify/consumer/delete、冲突、precheck/insert/verify/delete/cleanup验证/consumer异常、非法计数、输出冲突、lifecycle缺terminal/重排、strict evidence与敏感值反证；cleanup失败保留`failed_cleanup_required`，existingRowsModified/retry/resume=0 |
| `TEST-EMP-022` | `DR-EMP-021` | Contract/static/live-opt-in/history | metadata probe、success/failure Schema、launcher与Java probe | 四条queryForList且无业务SQL/写SQL；源/实现hash；trigger原文不持久化；查询失败立即停止；run-01失败阶段/计数/报告hash/零泄漏不可变；成功evidence缺失时不得关门 |
| `TEST-EMP-023` | `DR-EMP-022` | Contract/static/fake/history/disabled Java | v2 module、三份Schema、Java probe、launcher、manifest/auth及direct/history tests | 查询前exclusive+fsync；四phase逐点失败立即停止；started=terminal、retry/resume=0；SELECT alias不变、所有名称比较BINARY且无LOWER；manifest七asset/历史三hash；prepared无live输出 |
| `TEST-EMP-024` | `DR-EMP-023` | Post-consumption/history | 两个candidate-02测试文件；只读Git blob与正式evidence | frozen commit七asset/manifest/auth hash；lifecycle/result精确SHA、四查询10事件、58列/InnoDB、0 constraint/check/trigger、安全计数全零；不访问数据库或凭证 |
| `TEST-EMP-025` | `DR-EMP-024` | Contract/fake/static/live-opt-in/history | candidate Python/Schema/manifest/auth/lifecycle/result、Java test、launcher与直接/history测试 | 覆盖六项history、正常16事件/3-1-1、precheck/insert/verify/delete/cleanup/consumer/host失败、strict result、参数化exact SQL、显式事务、frozen commit及四项精确hash |
| `TEST-EMP-026` | 已通过；`DR-EMP-025` | Contract/fake/static/history | candidate-03 Python/Schema/manifest/auth、fake repository+detail consumer、Java disabled test、launcher与history测试 | 覆盖正常qualified、四类终态、各阶段故障、cleanup优先级、3/1/1与detail 0/1、跨进程sequence/terminal、生产投影符号、历史hash、正式输出不存在和敏感值不落盘；定向14 passed/1 live skipped，全量930 passed/19 live skipped |
| `TEST-EMP-027` | 已新增并通过；`DR-EMP-026` | Contract/fake/static/history/disabled Java | candidate-04 Python/pre-SQL Schema、Java显式启动类、launcher、manifest/auth及direct/history tests | 覆盖Spring context失败在首SQL前有限化、唯一启动类绑定、SQL/detail/model=0、host journal顺序、v3失败历史精确hash、v3资格规则复用及正式live输出不存在；定向19 passed/1 live skipped、Employee/Business 315 passed/10 skipped、全量949 passed/20 skipped |
| `TEST-EMP-028` | 已新增并通过；`DR-EMP-027` | Post-consumption contract/history | candidate-04 history test、prepared frozen HEAD、host/lifecycle/result三项证据 | 固定4条host、15条SQL序列、3/1/1+detail1、字段全true、deleted1/remaining0与安全零值；显式反证冻结validator拒绝未成对`host_validation`；定向20 passed/1 live skipped |
| `TEST-EMP-029` | 已新增并通过；`DR-EMP-028` | Contract/fake/static/history/disabled Java | candidate-05 direct/finalizer/host/history/live-opt-in、launcher AST与Java disabled测试 | qualified/host exit/log leak均走真实finalizer并由同一validator接受16条序列；非法pending/lifecycle无result；3/1/1+detail1预算、17项history、12项asset hash和v4历史精确；生产/API/数据diff=0 |
| `TEST-EMP-030` | 已新增并通过；`DR-EMP-029` | Post-consumption/contract/fake/static/history/live Java | v5 consumed history；v6 direct/finalizer/host/history/live-opt-in、launcher AST、Java live test与独立v6 consumed-history | v5证据不可变；v6 Python/Java exact四键、逐键boolean、23项history/12项asset、五项SHA、完整16条序列、3/1/1+detail1、全部资格字段、exact cleanup及安全零值；生产/API/数据diff=0 |
| `TEST-EMP-031` | 已新增并通过；`DR-EMP-030` | Contract/fake/static/history/disabled Java/live-opt-in | candidate-03 Python/五Schema/launcher/manifest/auth、Java disabled、direct/preparation/history及真实接缝测试 | 76条成功语言、阶段成对终态、3/1/1+detail1+answer30、有效≥27、四终态、首outbound消费、INSERT后cleanup、上下文/staging失败有限化、17项history/28项asset精确hash、安全计数全0；定向21 passed/1 live skipped |
| `TEST-EMP-032` | 已通过；`DR-EMP-031` | History/Contract/Preparation | candidate-03五项精确SHA与`failed_consumed`语义、candidate-06资格/授权、answer v2/current bootstrap、31项asset、五份strict Schema、76条成功语言、11类逐阶段故障、四终态、3/1/1+detail1+answer30、字段/cleanup和live opt-in | 23 passed/1 live skipped；旧资产字节不变且不得live复用，prepared数据库/JWT/Employee/DeepSeek/outbound均0 |
| `TEST-EMP-033` | 建议新增；`DR-EMP-032` | Contract/Fake/Static/History/PowerShell AST | 全阶段顺序及asset/config/auth-start/readiness/login/candidate-invoke/cleanup逐阶段失败；candidate前失败时candidate输出与SQL/detail/model均0；auth PID ownership、维护者进程不停止、secret/log零落盘、candidate-04/history精确hash | non-live定向、Employee/Business回归、strict mypy、compileall、AST；真实服务/JWT/key/数据库/outbound均0 |
| `TEST-EMP-034` | 已完成；`DR-EMP-033` | Contract/Fake/Static/History/PowerShell AST | v2 preflight拒绝auth JAR、build/source/command、v1历史或candidate-04任一漂移；六分类及unknown严格有限；原始日志删除、秘密零落盘、outer/inner正式输出全部不存在；v1与共享Transaction v2文件字节不变 | 冻结后定向33 passed；全量non-live 1189 passed/27 skipped/3个既有prepared-only历史断言deselect；strict mypy399、compileall、AST及确定性Maven build hash通过；真实服务/JWT/key/数据库/outbound均0 |
| `TEST-EMP-035` | 建议新增；`DR-EMP-034` | Contract/Full-path Fake/Static/History/PowerShell AST | 真实executor驱动真实v3 preflight越过asset phase；预存lifecycle/result/diagnostic/inner输出分别失败关闭；v2四项SHA、candidate-04、共享Transaction与生产src不变；retry/resume/外部调用0 | 失败信号不得再由本次lifecycle触发`asset_hash_invalid`；`GATE-063`关闭前不得执行live |
| `TEST-EMP-036` | 已完成；`DR-EMP-035` | 文档契约/计划 DAG/状态与 scoped 门禁一致性 | 系统 E2E 依赖 `WP-EMP-REAL-01` 而非 Employee egress 实验；Deferred 包不进入当前关键路径；Not Applicable 不表示通过或授权 | 核对历史30/27阈值、失败证据与 `SA-GATE-006.EMPLOYEE` 均未改判 |

### 13.2 验证命令

| 编号 | 命令 | 证明范围 | 当前状态 |
|---|---|---|---|
| `VAL-EMP-001` | PowerShell：`$env:PYTHONPATH='agent-runtime/src;agent-runtime'; python -m pytest agent-runtime/tests/unit/adapters/employee agent-runtime/tests/contract/adapters/employee -q` | definition/codec/field/status/结果出域字段矩阵 | 2026-08-13：56 passed |
| `VAL-EMP-002` | PowerShell：`$env:PYTHONPATH='agent-runtime/src;agent-runtime'; python -m pytest agent-runtime/tests/integration/adapters/employee agent-runtime/tests/architecture/test_employee_adapter_boundaries.py -q` | 单调用、模型/日志零泄露、结果出域 fake 接缝与边界 | 2026-08-13：25 passed、1 live skipped；全量非 live 724 passed/10 skipped，strict mypy 284 files、compileall通过 |
| `VAL-EMP-003` | `mvn -f serviceCenter/pom.xml -pl :employee-service -am test` | Employee guard/MVC/现有回归 | 2026-08-03：`common-security` 20、`employee-service` 23，共 43 项通过；覆盖 Guard、实际 200 全字段、角色拒绝矩阵、调用次数、400 兼容、fixture/调用方和既有回归 |
| `VAL-EMP-004` | opt-in：ADMIN/VIEWER/unknown/missing/malformed/service-token 真实 JWT 矩阵，并以 service/mapper spy 计数 | Authority/业务最终授权/领域调用次数 | 2026-08-06：`wp-emp-real-01-20260806T075036Z.json` 通过；7 次 Employee 请求，ADMIN 两身份与 VIEWER 允许，unknown/missing/malformed/service-token 拒绝，detail/mapper 各 3 次，其他接口/模型调用为 0，泄漏计数 0且原始日志已删除 |
| `VAL-EMP-005` | opt-in：`pwsh -NoProfile -File agent-runtime/scripts/run-employee-gateway-log-live.ps1`；runner 内部生成合成 sentinel，经测试临时路由通过 actual Gateway→Servlet 发起恰好一次详情请求，扫描后删除原始日志，并以严格 Schema 校验有限 evidence | 完整/编码 sentinel、JWT、HMAC 密钥、subject、完整 path 在 Gateway/Servlet/测试输出中均零出现；Gateway/Servlet/detail/mapper 调用计数均为 1；正式 Employee 路由为零；原始日志已删除 | 2026-08-06：首次请求失败并安全清理后，维护者重新授权的唯一一次重试通过；`wp-emp-gateway-log-20260806T091456Z.json` 记录 Gateway/Servlet/detail/mapper 各 1 次、响应 400、其他 service 调用 0、泄漏计数 0、原始日志已删除，正式路由/真实员工标识/DeepSeek 均为 false；严格 evidence 校验通过 |
| `VAL-EMP-006` | `D:\codex\agent-runtime`：`$env:PYTHONPATH='src;.'; python -m pytest tests/unit/adapters/employee/test_action_resolver.py tests/integration/graph -q`，再执行 `python -m mypy --strict src tests` | Employee 有限语法、混合裁决、真实 validator 复核、模型/HTTP 零调用和类型一致性 | 2026-08-07：42 passed；本工作包直接回归 109 passed；strict mypy 237 source files 无问题 |
| `VAL-EMP-007` | `D:\codex\agent-runtime`；只允许 fake/non-live | `$env:PYTHONPATH='src;.'; python -m pytest tests/integration/adapters/employee/test_employee_egress_candidate_v2_preparation.py tests/integration/adapters/employee/test_employee_egress_candidate_v2_harness.py tests/integration/adapters/employee/test_employee_egress_candidate_01_history.py -q`；随后执行 Employee/Business 非 live 回归、`python -m mypy --strict src tests`、`python -m compileall -q src tests`、PowerShell AST 和四项历史 SHA-256 校验 | 2026-08-14：candidate 定向18 passed/1 live skipped；Employee/Business 154 passed/3 live skipped；全量752 passed/12 live skipped；strict mypy 293 files、compileall、PowerShell AST、四项历史hash、24项manifest资产及41节点/73边DAG通过；未读取密钥、启动服务或产生outbound |
| `VAL-EMP-008` | `D:\codex`；不设置/读取 `LLM_API_KEY` | `python -m pytest` 执行资格定向及 Employee/Business 非 live 回归；`mvn ... -Dtest=EmployeeEgressInputQualificationLiveIntegrationTest test` 由版本化 runner opt-in 执行；随后 strict mypy、compileall、PowerShell AST、Schema、敏感扫描和八项历史 SHA-256 校验 | 非 live 11 passed/1 skipped、Employee/Business 138 passed/2 skipped、mypy/compileall/AST/Java编译及八项历史通过；受控运行以有限 integration error 失败，未生成 evidence，detail只能判定0～1，故本VAL未通过且不得进入candidate-03 |
| `VAL-EMP-009` | `D:\codex`；不设置live开关，不读取密钥 | v2定向pytest；Employee/Business及全量non-live回归；`mypy --strict src tests`、`compileall`、PowerShell AST；Maven仅编译/skip `EmployeeEgressInputQualificationV2LiveIntegrationTest`；strict manifest/auth/Schema与退役run六项+egress八项hash | v2定向14 passed；Employee/Business 179 passed/5 skipped；全量777 passed/14 skipped；strict mypy 299 files、compileall、AST、Java 1 skipped且BUILD SUCCESS；manifest SHA-256 `6d853ecee412a734f111d1d30740a703fe0343593560b7b01ed4c5194dfdb66f`、authorization `P3_00:GATE-049`且live=false；lifecycle/result不存在 | 非 live准备通过；不证明数据库候选、JWT、detail或资格结论，`GATE-049`保持Open |
| `VAL-EMP-010` | `D:\codex`；不启动auth，不设置/读取JWT与`LLM_API_KEY` | 先执行diagnostic Python/Schema/static tests与Java disabled编译；再仅设置诊断opt-in和有限evidence路径，以`mvn -f serviceCenter/pom.xml -pl :employee-service -am -Dtest=EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest test`执行唯一一次本地聚合；随后敏感扫描、Employee/Business及全量non-live、strict mypy、compileall、历史hash和代码对照设计复核 | aggregate query/result row=1/1；总数990，单项988/989/10/0，累积988/988/10/0，首零`work_base_si`；detail/endpoint/model/retry/resume/泄漏=0；candidate-02两项hash不变；evidence SHA-256=`f23115069adaa0bfedcfdb01b7f0889acb079961319db3c44547549ca088c46f` | 2026-08-14：strict evidence定向15 passed；全量non-live除冻结prepared断言外790 passed/15 skipped/1 deselected；冻结旧断言单独如实1 failed，独立post-consumption history测试通过；strict mypy 302 files、compileall、AST、Java disabled编译和聚焦代码复核通过。完整计数0后已停止，`GATE-049`保持Open |
| `VAL-EMP-011` | `D:\codex`；静态/非live，不读取数据库、JWT或`LLM_API_KEY` | 定向static diagnostic；Employee/Business回归；全量non-live；strict mypy/compileall；聚合evidence与9项源码hash、仓库数据资产/Git历史只读核对及聚焦代码对照设计复核 | 映射八项true，Map写入且无required/default/backfill；Employee DDL/数据/初始化/导入/回填资产计数0；数据库/端点/服务/model=0；evidence SHA-256=`7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8` | 2026-08-14：定向11 passed；Employee/Business 276 passed/6 skipped/1 deselected；全量801 passed/15 skipped/1 deselected；strict mypy304、compileall与代码复核通过。物理列/原始值分布保持unknown，`GATE-049`保持Open |
| `VAL-EMP-012` | `D:\codex`；测试范围，只读数据库最多2查询 | Python定向/strict mypy/compileall、PowerShell AST、Java disabled编译；随后运行`run_employee_work_base_data_diagnostic.ps1`一次，验证source hash、元数据/聚合各1次1行、互斥分类和、日志删除/敏感扫描及strict live evidence；最后执行相关回归和代码对照设计复核 | 唯一一次执行得到nullable `longtext`、总数/NULL=990/990、长度/control/bidi/valid=0；数据库查询2，HTTP/auth/JWT/model/retry/resume/泄漏=0 | evidence SHA-256=`b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6`；strict定向14、相关290 passed/6 skipped/1 deselected、全量815 passed/15 skipped/1 deselected，strict mypy/compileall通过 | 通过；`GATE-049`保持Open，不形成数据修复或candidate授权 |
| `VAL-EMP-013` | `D:\codex`；仅静态源代码/evidence核实 | 重算输入evidence；核对`EmployeeSqlProvider`、`EmployeeMapper`、`EmployeeService`及版本化DDL/约束来源；不设置live开关，不启动服务、数据库或模型 | 静态证据必须足以证明最小INSERT所需字段、唯一性、FK/CHECK/trigger和精确cleanup，否则代码/测试计数为0并失败关闭 | 2026-08-14：输入hash通过；当前仅能证明58列动态按键INSERT、按标识DELETE和正式Service含事件副作用，完整物理约束不可知 | 未通过；`IMPL-EMP-029/TEST-EMP-021`未实施，`GATE-050/049`保持Open |
| `VAL-EMP-014` | `D:\codex`；测试范围，只读数据库最多四查询且无重试 | 定向pytest、strict mypy、compileall、PowerShell AST、Java disabled编译；随后只运行一次版本化launcher，失败时敏感扫描、记录报告hash、删除原始报告并校验strict failure evidence；最后执行相关回归和代码对照设计复核 | 第1条列/引擎查询成功；第2条约束查询以`HY000/1267 information_schema_collation_mismatch`失败；第3/4条0次，total started=2、success/failure=1/1、retry/resume=0；业务行/写入/HTTP/auth/JWT/model/泄漏=0 | failure evidence SHA-256=`dce5e7659ed9cc49b52aa9cca6b70c9701c22cc55867f26cfa6a50ead291e7a1`；未形成成功evidence，run-01不可重跑，`GATE-050/049`保持Open |
| `VAL-EMP-015` | `D:\codex`；non-live/fake/static，不设置`RUN_EMPLOYEE_FIXTURE_METADATA_DIAG_V2` | v2 direct/history pytest；Employee/Business回归；strict mypy/compileall；PowerShell AST；Maven指定V2 test且2 skipped；重算run-01三项、manifest七项asset和manifest/auth绑定；代码对照设计复核 | run `employee-fixture-metadata-diagnostic-v2-20260814-candidate-02`、manifest SHA-256=`ce3dcd481352bbb59be01a2d3b975dfd1b9f35ae1479dd24d7408f11be7af6b7`、authorization=`P3_00:GATE-050`、maxQueries=4、live/database=false；正式lifecycle/result不存在 | 通过；仅prep工作包Done，`GATE-050/049`保持Open |
| `VAL-EMP-016` | `D:\codex`；post-consumption只读，不设置任何live开关 | candidate-02 direct/history、Employee/Business非live回归、strict mypy、compileall、两份L2/P3 strict validator、证据/commit hash及代码对照设计复核 | lifecycle/result hash=`affbd35987e4caaa4950888eaed80cf12e695470b1703735716f2dd54d52a105`/`9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51`；四查询passed、零副作用 | 全部通过后关闭`GATE-050`并将test-data prep转Ready；不关闭`GATE-049/024` |
| `VAL-EMP-017` | `D:\codex\agent-runtime`；纯non-live/fake，不设置live开关 | fixture定向pytest；Employee/Business相关回归；strict mypy/compileall；两份L2/P3 strict validator；metadata/schema/hash、diff与代码对照设计复核 | metadata/hash先于journal；所有阶段成对terminal且单调；repository/consumer故障有限化并finally cleanup；标识/fingerprint/字段值不落盘；数据库/HTTP/auth/JWT/model=0 | 2026-08-14：三轮内审完成，定向16 passed、目标strict mypy/compileall通过；宽回归唯一失败为既有GATE-049 prepared-only断言，不属于本包 | 本包通过并可Done；真实fixture、`GATE-049/024`保持禁止 |
| `VAL-EMP-018` | `D:\codex`；`GATE-051`已消费，后续只读post-consumption | candidate定向/history pytest、Employee/Business非live回归、strict mypy/compileall、PowerShell AST、六项history/asset/manifest与证据hash、L2/P3 strict validator及代码复核 | 唯一live执行16项lifecycle；SELECT/INSERT/DELETE terminal=3/1/1，inserted/verified/deleted=1、remaining=0，endpoint/JWT/model/retry/resume/leak=0，原始日志已删除 | lifecycle/result SHA-256=`4d5ab81e68d24ac76a7c1d6f7b1a57204b7cb81c99f40f93afe444f4077f5b6c`/`f0003ec559fa4606edda2982f0ae6878bfa066262168236128705d0c40aa0e4a`；frozen commit=`fd95e181993caec1263529ebf6ff357daad5bcaa` | 通过并关闭`GATE-051`；`GATE-049/024`保持Open |
| `VAL-EMP-019` | `D:\codex`；全部live开关为0，不读取JWT/密钥 | candidate-03定向/history、全量非live、strict mypy/compileall、PowerShell AST、Java disabled编译、旧资格与fixture八项history、manifest/auth/asset hash、L2/P3 strict validator及代码对照设计复核 | fake证明16项有序lifecycle、3/1/1、detail最大1、四终态、跨语言journal连续、finally exact cleanup与零敏感持久化；正式lifecycle/result不存在 | run=`employee-egress-input-qualification-v3-20260814-candidate-03`；manifest=`495063a328af6a233f5600bd4efff31fdae5ab4e28aad8287bfce194051680dd`；auth=`P3_00:GATE-049` | prep Done；`GATE-049/024/SA-GATE-006/GATE-033`保持Open |
| `VAL-EMP-020` | `D:\codex`；全部live开关为0，不读取JWT/密钥 | candidate-04 direct/history、Employee/Business相关回归、strict mypy/compileall、PowerShell AST、Java disabled编译、candidate-03 failure及11项历史/11项asset hash、L2/P3 strict validator与三轮代码对照设计复核 | Spring配置由唯一生产启动类显式确定；Maven前host journal和pre-SQL有限结果经fake故障证明；正式SQL/JWT/detail/model=0 | run=`employee-egress-input-qualification-v4-20260816-candidate-04`；manifest SHA-256=`7dcae58a2a503a97fe89de0d01e63cb0450ccb0dd5945e4da5947d2df0875bb9`；authorization=`P3_00:GATE-049`；预算3/1/1+detail1+model0 | prep通过不关闭`GATE-049/024/SA-GATE-006/GATE-033` |
| `VAL-EMP-021` | `D:\codex`；candidate-04已消费，后续只读且不设置live开关 | 校验prepared frozen HEAD、manifest/auth/history/asset、host/lifecycle/result精确SHA、完整15条序列、strict result与敏感扫描；执行post-consumption定向测试和代码对照设计复核 | 业务资格、3/1/1、detail1、inserted/verified/deleted1、remaining0及安全零值成立；host/result validator通过；冻结SQL lifecycle validator拒绝 | host/lifecycle/result SHA-256=`73bd37aaec1c3c57d7debea5f1120cd3cff828057bcaee84afbdb4495658472a`/`aa2479fc8051cb4741f9826b81521583285ede692d31b9c6bed01bf1b2a922c3`/`757bd4840143bbe5158facec89f7035cf72f99eac88b4c345d70cbc8ea0b5975`；定向20 passed/1 live skipped | candidate-04转不可复用历史；`GATE-049`保持Open，未来全新candidate须另行设计与授权 |
| `VAL-EMP-022` | `D:\codex`；candidate-05 prepared且所有live/数据库/JWT/model开关未设置 | 已执行candidate-05定向、Employee/Business非live、strict mypy、compileall、PowerShell AST、Java disabled编译、v4五项及既有十一项历史hash、manifest/auth/asset、L2/P3 strict validator与代码对照设计复核 | live同路finalizer三分支均产生validator可接受的16条lifecycle，invalid输入无result，prepared输出不存在且外部调用0 | run=`employee-egress-input-qualification-v5-20260816-candidate-05`；manifest SHA-256=`8b44a38ad6a02edd6db64b7c8e5fd02adee67a19ff1e9ef08e2ed3eb82f5ff74`；authorization=`P3_00:GATE-049`；history=17；asset=12 | non-live prep已完成；`GATE-049`保持Open，正式live需新授权 |
| `VAL-EMP-023` | `D:\codex`；candidate-06已消费，后续只读且全部live/数据库/JWT/model开关未设置 | 校验manifest/auth/23项history/12项asset及host/lifecycle/result精确SHA；独立consumed-history严格重放16条序列、字段、3/1/1+detail1、cleanup和安全计数；执行定向、全量non-live、strict mypy、compileall、PowerShell AST、Java disabled编译及聚焦代码对照复核 | 唯一终态`qualified`；exact四键、两required-user字段与egress全true；inserted/verified/deleted=1、remaining=0；model/other endpoint/retry/resume/leak=0；冻结validator接受完整16条lifecycle | manifest/auth/host/lifecycle/result SHA-256=`44f25232b445e0f1c8184b31ccf2dff4d5751a796b4f3ec327fb1ea2cbb702b2`/`bd0cb4d67c00e2aeba7756860f02a4f7df1fd9f17eb9420cc3ece4e524a697c5`/`9c4f7d9981bef665bd06068a96155433bfbe838ebad65d4ac5dc4424106c28d5`/`ec87bcb430fc90b3e9511871625bba60c07f7d4cc7e12842f3e18255624f6677`/`750f2e0d13866203116884e1950734bcb2b06100343f142cb5e96c63fe55a9cd` | 2026-08-17：消费后定向23 passed；全量996 passed/22 skipped/1 deselected，唯一deselect为不可变candidate-05 prepared-only历史断言且其独立consumed-history通过；strict mypy346、compileall、AST、Java BUILD SUCCESS/1 skipped、聚焦代码复核符合。关闭`GATE-049`；`GATE-024/SA-GATE-006/GATE-033`保持Open |

| `VAL-EMP-024` | `D:\codex`；全部live开关为0，不读取JWT/`LLM_API_KEY` | candidate-03定向/history、Employee/Business及全量non-live、strict mypy/compileall、PowerShell AST、Java disabled编译、candidate-06与旧egress历史hash、manifest/auth/asset、L2/P3 strict validator及代码对照设计复核 | fake证明统一76条生命周期、3/1/1+detail1+answer30、四终态、首outbound消费、pending actual cleanup、安全拒绝有限证据、模型字段仅两项及passed安全零值；正式输出不存在 | run=`employee-egress-v3-20260817-candidate-03`；manifest SHA-256=`901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e`；定向21/1 skipped、Employee/Business 375/13 skipped/1历史失败、全量1017/23 skipped/1同项deselect、strict mypy351、compileall、AST、Java BUILD SUCCESS/1 skipped | 通过并关闭`GATE-052`；`GATE-024/SA-GATE-006/GATE-033`保持Open |
| `VAL-EMP-025` | `D:\codex\agent-runtime`与`D:\codex\employee-service`；全部live开关为0 | candidate-04定向、Employee/Business相关及全量non-live回归、strict mypy、compileall、PowerShell AST、Java disabled、manifest/history hash及代码对照设计复核 | 23 passed/1 live skipped；相关405 passed/14 skipped/1既有candidate-05 prepared-only断言deselect；全量1047 passed/24 skipped/1同一历史deselect；strict mypy source105+candidate5 files、compileall、AST及Java disabled通过；candidate-03五项历史不可变，真实调用0 | 通过并关闭`GATE-054`；`GATE-024/SA-GATE-006/GATE-033`保持Open |
| `VAL-EMP-026` | `D:\codex\agent-runtime`；全部live/服务/数据库开关为0且未提供JWT/HMAC/标识/`LLM_API_KEY` | Employee bootstrap direct/failure/history、公共bootstrap、PowerShell AST、Employee/Business及全量non-live回归、strict mypy、compileall、candidate-04 hash和代码对照设计复核 | 公共/Employee/Transaction冻结后定向29通过；全量1159 passed/27 skipped/2既有历史deselect；strict mypy388、compileall及Employee launcher AST通过。验证pre-side-effect lifecycle、prelaunch零candidate计数、auth唯一启动、PID/log/secret边界及inner唯一权威；真实服务/SQL/Employee/模型调用0 | source commit=`038b6a0f54f5f8ace9a68e49073e5035279473da`；run=`employee-egress-live-bootstrap-v1-20260817-candidate-01`；manifest/auth SHA-256=`b7be5caa4b3450242e9c63abf80152c023874641ed1bf4bf34bafdb10177af9a`/`d3d281ba5b62da632e4f52cdd4b86963b67a458c310ffdfaf799755c89158de9` | 通过；bootstrap包Done，`GATE-024/033/SA-GATE-006[Employee]`保持Open |
| `VAL-EMP-027` | `D:\codex\agent-runtime`；全部live/服务/数据库开关为0，未读取JWT/HMAC/标识/`LLM_API_KEY` | Employee wrapper-v2 direct/preparation/history、公共v2 diagnostic、确定性auth构建、PowerShell AST、相关及全量non-live回归、strict mypy、compileall、历史hash与代码对照设计复核 | 已证明源码commit→JAR→manifest闭环、JAR漂移进程前失败、有限诊断/日志销毁、v1 prepared与candidate-04不可变、共享Transaction v2历史无漂移、全部live输出不存在 | source commit=`37b51608b851d463a1b1f6e5a782589efba9c49d`；prepared HEAD=`4dff45bfe0fdb3be2787b4c2231e8859299d6570`；run=`employee-egress-live-bootstrap-v2-20260818-candidate-02`；manifest/auth/auth-JAR SHA-256=`899eb378df014085c6e419a1720be96994698457b1f248215e8df2374118b383`/`0f9d71d0636f956aa12c4928a91137e53a211a74718a66a30b8f29fd8eb63000`/`da59695336c6f2fd11581760b41f0958114ac1f9e728ad834ff1a25a7595a96b`；定向33 passed、全量1189 passed/27 skipped/3个既有历史断言deselect、strict mypy399、compileall/AST/Maven BUILD SUCCESS。关闭`GATE-062`；`GATE-024/033/SA-GATE-006[Employee]`继续Open |
| `VAL-EMP-028` | `D:\codex\agent-runtime`；仅fake/static/disabled，禁止JWT/HMAC/标识/`LLM_API_KEY`和任何服务/数据库/outbound | wrapper-v3 full-path fake、输出冲突、preparation/history、PowerShell AST、Employee/Business回归、strict mypy、compileall、历史SHA与代码对照设计复核 | 当前lifecycle合法通过asset phase；预存outer/inner输出仍失败关闭；v2失败证据与所有历史不变，candidate/外部调用0 | 未执行；须在`GATE-063`代码授权下完成 |
| `VAL-EMP-029` | `D:\codex`；仅文档修改，不启动服务、数据库或模型调用 | 执行 Employee L2 strict validator、P3 strict validator、跨层版本/门禁核对与 `git diff --check` | 追踪、DAG、状态、历史不可变声明与 scoped 安全边界一致 | 2026-08-20：Employee L2与P3 strict validator均0错误/0警告，跨层核对及`git diff --check`通过 |

## 14. 风险、门禁与授权

### 14.1 风险

| 编号 | 风险 | 触发 | 影响 | 处置 |
|---|---|---|---|---|
| `RISK-EMP-001` | 详情 URL 含敏感标识 | Gateway/Servlet/filter 输出完整 path | 标识泄露 | 删除 Gateway 完整 path 输出；以测试临时路由执行一次 synthetic sentinel 扫描，任一命中失败关闭；不新增正式路由 |
| `RISK-EMP-002` | 400 混合 not-found/invalid | 不存在员工 | 不能准确 no-result | 保守 invalid_argument；变更 404 须另行确认 |
| `RISK-EMP-003` | 宽实体兼容 | 目标六字段类型/语义改变，或新增未知字段含恶意嵌套值 | 目标变化导致受控失败；未知值短暂进入受限内存 | 六字段 exact decode；未知字段仅临时解析后丢弃；visibility fixture 使任何实际字段集合变化先触发 provider contract 失败 |
| `RISK-EMP-004` | 真实 Authority 链后续漂移 | auth/common-security、Gateway 或 Employee Authority 契约变更 | 越权/误拒绝 | 当前 converter、业务 guard、真实 JWT/调用次数矩阵已闭环；相关契约或部署环境变更时重新执行 `VAL-EMP-004/005`，失败关闭 |
| `RISK-EMP-005` | 姓名/职位用于模型 | 误开配置 | 个人/内部数据外发 | code candidates 最小、默认空、全局门禁仍 Open |
| `RISK-EMP-006` | 宽响应策略漂移 | Employee 字段或角色策略变化但 fixture 未同步 | 业务服务把新增或已收紧字段传给 Agent 进程 | 实际 200 全字段契约测试失败关闭；策略变化须重新确认，不能由 Agent 投影补足 |
| `RISK-EMP-007` | 真实入口证据随环境变化失效 | Gateway/Auth/Employee 配置、日志设施或路由变化后沿用旧证据 | 合法请求误拒绝、敏感 path 进入日志或运行权限偏差 | 当前 `VAL-EMP-003～005` 已闭环；目标环境或相关配置变化时重新验证，默认 action 继续 disabled |
| `RISK-EMP-008` | 有限语法覆盖不足或误命中 | 用户使用同义表达、多个标识或把 Employee 词句嵌入长文本 | 合法请求被拒绝，或错误动作获得参数 | 只接受 8.2.1 完整语法；识别后歧义失败关闭且不回退模型；扩充 token 必须修订本文和契约测试，不通过配置热扩展 |
| `RISK-EMP-009` | candidate pre-model 失败不可归因 | lifecycle journal 在投影成功后才创建，`finally` 再校验缺失 journal | Employee 请求/响应/投影/模型初始化任一失败 | 原因被二次异常覆盖，Employee 请求只能给0～1范围，门禁证据无效 | candidate-02 采用 `DR-EMP-014` 独立 v2 文件、域请求前 journal、transport 精确 started/terminal 和 consumed 派生终态；candidate-01 只读 | 阻塞 candidate-02 live；不影响生产 Employee action/Provider |
| `RISK-EMP-010` | Employee 输入不具备模型最小字段 | 测试员工 `position` 或 `workBaseSi` 为空 | detail成功但投影 denied，付费候选在首outbound前失败 | 重复制造无效 candidate 和不可关闭门禁 | `DR-EMP-015` 先以只读筛选+一次真实 detail验证；只把 qualified 结论用于后续新 candidate 设计 | 阻塞 candidate-03 准备；不影响 Employee 本地查询 |
| `RISK-EMP-011` | 新资格运行再次不可判定 | SQL只筛两个模型字段，或journal在查询/detail后建立 | codec/required user结果仍失败，detail次数再次只能给范围 | 浪费一次受控资格机会并错误解锁后继 | `DR-EMP-016` 绑定四codec字段、两required user字段、请求前fsync和有限结果；prepared入口先校验14项历史，正式执行另行授权 | 阻塞`GATE-049`；不影响生产Employee查询 |
| `RISK-EMP-012` | 聚合诊断泄露业务值或产生错误归因 | SQL选择原始字段/多行，或单项和累积计数/首零阶段不一致 | 员工标识/属性泄露，误判数据缺口并错误准备新候选 | `DR-EMP-017`固定一个聚合调用、单行整数、strict关系校验、禁止列源码测试和candidate-02历史hash；诊断不具备资格通过语义 | 完整计数0时停止；非0也须另行设计新资格candidate，`GATE-049`继续Open |
| `RISK-EMP-013` | 静态检查把未知物理数据误判为已知 | 由Java映射一致直接推断列类型/default，或由无初始化资产直接推断全部NULL | 误改生产Mapper/数据并错误准备新资格候选 | `DR-EMP-018`分离`data_population_provenance_gap`、`not_versioned`和`not_observable_without_separate_query`；strict evidence拒绝改判 | 只建议另行授权最小元数据与整数分类聚合；当前不修改数据或关闭门禁 |
| `RISK-EMP-014` | 两查询结果被误作资格或业务修复依据 | 分类重叠、快照漂移，或只凭NULL分布推断业务填充值 | 伪根因、未授权数据变更或错误准备candidate-03 | `DR-EMP-019`强制互斥分区和、990/0快照一致性及有限reason；只证明物理状态，不产生修复策略 | `GATE-049`继续Open；数据修复与新资格candidate均须单独授权 |
| `RISK-EMP-015` | synthetic fixture 误伤或残留 | 仅凭动态Map SQL假定四字段可插入，按标识宽删，忽略键/FK/CHECK/trigger或崩溃恢复 | 修改/删除既有员工或遗留测试记录 | `DR-EMP-020`先以`GATE-050`关闭物理约束，再用确定性synthetic标识、完整fingerprint、耐久journal和精确0/1 cleanup实施 | 元数据前置已满足；仅解锁fake repository与非live验证，真实写删仍禁止 |
| `RISK-EMP-016` | `information_schema`名称比较发生collation冲突 | schema/table/constraint关联依赖隐式字符排序规则，或失败后继续执行后继查询 | 元数据证据不完整、查询预算失真并可能误关fixture门禁 | `DR-EMP-021`要求失败即停、有限history和新run；candidate-02使用显式binary/collation-neutral比较并形成完整结果 | run-01历史保持失败；candidate-02已关闭当前缺口 |
| `RISK-EMP-017` | candidate-02 prepared状态被误用为live授权 | 只凭manifest存在或进程开关访问数据库 | 绕过维护者的精确run/hash/预算授权 | `DR-EMP-022`要求manifest/auth均live/database=false、launcher核对精确SHA；candidate-02已按目标授权一次性执行 | 本run已消费且不可复用；未来候选仍须独立授权 |
| `RISK-EMP-018` | post-consumption测试改写prepared历史 | 直接修改manifest绑定asset并以当前工作树校验原授权，或继续执行输出不存在断言 | manifest漂移、回归假失败、运行历史不可重放 | `DR-EMP-023`固定commit blob与当前结果双快照，禁止修改正式资产和重跑 | 已通过`TEST-EMP-024/VAL-EMP-016`解除 |
| `RISK-EMP-019` | Spring Boot自动发现多个测试配置 | live test与历史嵌套`@SpringBootConfiguration`同包且未显式指定生产启动类 | 上下文在lifecycle前失败，形成证据空窗并诱发同run重试 | `DR-EMP-026`显式绑定`EmployeeServiceApplication`，launcher在Maven前耐久记录并有限化pre-SQL失败 | candidate-03不可重跑；candidate-04已完成`VAL-EMP-020`并唯一执行，当前结果转由`RISK-EMP-020/VAL-EMP-021`约束 |
| `RISK-EMP-020` | live finalizer与冻结lifecycle validator语义不一致 | fake candidate写入`host_validation started/succeeded`，真实finalizer只追加terminal且不在result落盘前验证完整lifecycle | 业务成功却无法形成自洽门禁证据，诱发历史改写、校验放宽或重复SQL/detail | `DR-EMP-027`固定candidate-04三项证据和validator拒绝；未来candidate必须在non-live使用live同路finalizer输出通过同一validator | candidate-04不可复用；`GATE-049`保持Open |
| `RISK-EMP-021` | candidate-05测试与launcher finalizer再次分叉 | 测试手工写16条记录，但launcher调用另一条finalizer或在validator前落盘result | non-live假阳性并再次浪费一次性SQL/detail机会 | `DR-EMP-028`要求direct test导入launcher同一函数，manifest冻结函数、launcher及测试hash；validator调用必须位于result exclusive-write之前 | 未通过`VAL-EMP-022`不得冻结或申请`GATE-049` |
| `RISK-EMP-022` | Python staging与Java loader对nested codec基数理解漂移 | Java只检查错误size，contract test又只命中outer `value.size()!=5` | 合格响应被拒绝并消耗一次性授权；反向放宽时未知字段可能被接纳 | `DR-EMP-029`把size=4、四键逐项boolean和Python exact key set作为同一验收；v5证据只读，v6独立冻结 | `VAL-EMP-023`未通过不得申请candidate-06 live |
| `RISK-EMP-023` | Employee fixture与模型调用分离导致清理或消费状态不可证明 | 使用旧egress runner读取已删除记录，或模型完成后先写passed再由另一路cleanup | pre-model重复失败、遗留synthetic记录、已消费授权被误记未消费或错误关闭`GATE-024` | `DR-EMP-030`固定跨Java/Python唯一journal、76条同validator语言、首outbound marker、finally exact cleanup与result后置 | 未通过`VAL-EMP-024`不得冻结或申请`GATE-024` |
| `RISK-EMP-024` | 复用candidate-03测试answer v2会篡改已消费身份 | 修改旧manifest/runner或让历史测试要求当前bootstrap仍等于旧hash | 历史证据失真或同一authorization被不同代码执行 | candidate-03五项精确SHA+冻结来源校验；candidate-04全新run/manifest/auth；旧入口永久退役 | `GATE-054` Closed；`GATE-024` Open |
| `RISK-EMP-025` | auth/JWT宿主位于candidate manifest之外 | 临时命令重复Spring参数、错误readiness、JWT写日志或停止非本次进程 | candidate未开始却无可复核失败证据，或影响维护者服务 | `DR-EMP-032`以versioned wrapper、首副作用前journal、PID归属、有限failure和日志销毁收口；candidate内部生命周期保持唯一 | `GATE-058`未关闭前不得冻结wrapper，`GATE-024`不得关闭 |
| `RISK-EMP-026` | Employee wrapper-v1继承已证实的共享启动风险 | 与Transaction失败入口共用v1 helper，只检查auth JAR存在且提前退出仅给`process_exited` | 在未冻结可执行物或无法归因的情况下消费一次性Employee live授权 | v1保持prepared历史且禁止执行；`DR-EMP-033`以wrapper-v2冻结auth JAR/source/build并复用有限diagnostic | `GATE-062`关闭前不得更新或执行`GATE-024` |
| `RISK-EMP-027` | wrapper-v2局部测试未覆盖executor与preflight真实组合顺序 | 本次合法lifecycle在asset phase被误判为历史输出 | 稳定阻断candidate前路径；直接删除检查会破坏重放防护 | `DR-EMP-034`以wrapper-v3拆分run前全输出检查与phase内其余输出检查，并要求full-path fake | `GATE-063`关闭前不得准备或执行新`GATE-024` |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 关闭条件 | 责任方 | 状态 | 未关闭允许/禁止 |
|---|---|---|---|---|---|---|
| `BQ-GATE-002` | slice_implementation | 实施既有 Python Employee Adapter/配置/测试切片 | 历史独立评审、明确授权、本地测试和代码对照设计评审通过 | 维护者 | Closed（Adapter 与 Resolver 均 implementation-verified） | 既有 Adapter 与本地 Resolver 可维护；语法扩大、真实调用、默认启用和模型出域仍须另行授权 |
| `BQ-GATE-003` | slice_implementation | 实施/变更 Employee 提供方接口、公开行为或守卫 | 维护者确认复用详情、ADMIN/VIEWER 对完整响应的可见性、versioned visibility fixture、现有调用方角色兼容、角色 guard 与 400 语义，并批准具体 Java/测试范围 | 维护者/Employee 方 | Closed | 仅证明当前 Provider 实现/契约闭环；受控真实目标配置已由 `SA-GATE-004` 关闭证据允许，默认/生产启用、正式 Gateway 路由与模型出域仍禁止 |
| `CR-GATE-003` | integration | 具体 Employee 问题进入 DeepSeek 以选择/摘要动作 | 全局问题闸门能对标识、姓名、联系方式等形成已批准最小化或零调用路径 | 维护者/模型方 | Closed（2026-08-12；以具体/unknown 零调用关闭问题输入前置） | 8.2.1 本地 Resolver 命中时继续不进入模型；具体敏感或未分类 Employee 问题仍禁止走模型 fallback/答案模型，真实结果仍受 `SA-GATE-006` |
| `SA-GATE-004` | integration | 启用真实 Employee 动作 | 本文既有独立评审结论有效；`VAL-EMP-003/004/005` 证明 Authority、业务 guard、字段/status、允许拒绝矩阵、Gateway/Servlet 日志零泄漏、正式无 Employee 路由与原始日志销毁 | 维护者/安全/Employee 方 | Closed | 允许受控目标配置启用；默认 action 仍 disabled，正式 Gateway 路由、模型出域和生产生效不在本门禁关闭范围 |
| `SA-GATE-006.EMPLOYEE` | security/integration | Employee真实结果进入外部模型 | 未来新实验须重新证明字段交集、全局策略、facts/grounding、零调用负向与零泄漏，并取得新鲜精确授权 | 维护者/Employee/模型方 | Open（当前外发实验Deferred） | 禁止真实Employee载荷外发；允许真实Provider + stub模型系统E2E；不依赖当前P3中已Not Applicable的执行/完成门禁 |
| `GATE-050` | integration_precondition | synthetic Employee fixture物理写入/精确清理契约 | 以独立只读元数据证据证明全表58列属性及表引擎、主键/唯一键、出入向外键、CHECK和trigger；能够据此冻结最小INSERT、冲突检查、fingerprint验证、精确DELETE与cleanup恢复，且无需修改生产代码/结构 | 维护者/Employee数据责任方 | Closed（2026-08-14；candidate-02四查询passed） | 只允许实施fixture spec、fake repository、lifecycle/Schema和非live测试；真实数据写删、新资格candidate及`GATE-049`仍须独立授权 |

### 14.3 后续需授权

- 扩大已完成 Python Adapter 动作、字段或契约范围。
- 再次修改本轮已验证范围之外的 Employee guard/controller/test 或统一 Authority Converter 契约。
- 修改详情 not-found/响应 DTO、启用真实 Employee 或外发真实结果。
- 新增正式 Employee Gateway 路由、恢复完整 path 日志、使用真实员工标识执行 `VAL-EMP-005`，或保留原始联调日志。
- 再次执行 synthetic `VAL-EMP-005` Gateway→Servlet 请求或刷新现有 live 证据。
- 修改已验证的 `IMPL-EMP-015` Resolver、扩大 8.2.1 有限语法或改变最终 validator/混合裁决契约。
- 修改已冻结 candidate-02 module/Schema/launcher/manifest/authorization、修改 candidate-01 四项历史，或执行 candidate-02 live；须取得新的精确授权，live 必须绑定 run/hash/auth 与预算。
- `GATE-049/050/051/053/054`均为历史已关闭门禁，所有run与append-only证据不可变；`GATE-063/024/033`在当前周期为Not Applicable且不能授予执行权。未来恢复真实Employee结果外发时，须先诊断并以全新工作包、按需要建立的新有界门禁、run/authorization和预算重新授权，优先复用通用受控harness；完成状态仍由`SA-GATE-006.EMPLOYEE`判定。

## 15. 内部自检记录（作者内审）

| 日期 | 检查范围 | 结论 |
|---|---|---|
| 2026-08-20 | 现行权威、稳定标识、追踪矩阵、门禁与历史迁移完整性 | 物理瘦身不改变设计语义、Approved 状态、实施边界或门禁结论；完整逐轮记录见历史审计文档 |

## 16. 独立正式评审记录

- 本文既有独立正式评审通过结论保持不变；本次仅进行非语义的文档分层与物理瘦身，不据此重新授予批准状态。
- 完整逐轮发现、修复和代码对照设计复核记录见 [`L2_02_01` 历史审计记录](history/L2_02_01_EMPLOYEE_ADAPTER_AUDIT_HISTORY.md)。
## 17. 实施前检查

- [x] 单动作、现有接口、字段、状态和授权边界已显式定义。
- [x] Adapter 投影与业务服务最终授权未混淆。
- [x] 公开接口不足项保持门禁，不宣称已获修改授权。
- [x] 三轮内部自检完成且无遗留 Blocker/Major。
- [x] 严格详细设计校验通过。
- [x] 五轮独立评审—修复—复核及直接依赖聚焦一致性复核完成，全部S0/S1/S2已关闭。
- [x] `L2_02_00` v0.4 GET/no-body 定向兼容检查通过，未发现新的 S0/S1/S2。
- [x] 用户已授权 Python Adapter 与 Employee Provider 本地切片；测试和代码对照复核后关闭 `BQ-GATE-002/003`。Provider 切片当时未自行关闭真实门禁，后续 `VAL-EMP-004/005` 已按受控范围关闭 `SA-GATE-004`。
- [x] 首次合成 sentinel 请求失败并安全清理后，用户已重新授权且只执行一次修正后的 `VAL-EMP-005`；严格 evidence 通过，正式路由、公开接口、真实员工标识和 DeepSeek 均未进入范围。
- [x] v0.9 已固定 Employee Resolver 的有限语法、模型零调用、最终 validator 复核与实现/测试落点；未把设计完成误记为代码已实施。
- [x] v0.9 完成 `AR-HYBRID-01～03` 与 `FR-HYBRID-01～05`，新增发现全部关闭。
- [x] `IMPL-EMP-015/TEST-EMP-014/VAL-EMP-006` 已完成；Employee 定向与 graph 42 passed，工作包直接回归 109 passed，strict mypy 237 files 无问题。
- [x] `TEST-EMP-008/009` 与公共 `TEST-BQCOM-007/008/012/013` 的 Employee 非 live 复用路径已完成；定向26、Employee 56+25/1 skipped、全量724/10 skipped、strict mypy284与compileall通过，真实结果出域门禁保持Open。
- [x] candidate-01 manifest/authorization/环境诊断/pre-model failure 四项历史已锁定精确 SHA-256；本次失败未消费授权但不得补跑、续跑或原地修复。
- [x] candidate-02 的 `DR-EMP-014/IMPL-EMP-016～018/TEST-EMP-015/VAL-EMP-007` 已完成非 live 实施、冻结与代码对照设计复核；未创建 consumed/result 或执行 live。
- [x] `DR-EMP-016/IMPL-EMP-022～024/TEST-EMP-017/VAL-EMP-009` 的资格candidate-02准备与不可变运行证据均已形成；candidate-02不得重跑、补跑或续跑。
- [x] candidate-02以`not_qualified/employee.no_qualified_input`结束；`DR-EMP-017`的聚合诊断已确认`work_base_si`为首个归零条件，不能关闭`GATE-049`或授权candidate-03。
- [x] `DR-EMP-018/IMPL-EMP-027/TEST-EMP-019/VAL-EMP-011` 已完成静态来源诊断、strict evidence、非live回归和代码复核；只排除读取映射并确认数据填充来源缺口，物理列/原始值分布保持未知。
- [x] `DR-EMP-019/IMPL-EMP-028/TEST-EMP-020/VAL-EMP-012` 已以元数据/聚合各1次完成只读诊断，strict evidence证明`WORK_BASE_SI`为可空`longtext`且990条全部NULL；没有修改数据或解锁资格门禁。
- [x] `REQ/CON/DR-EMP-014/012/020` 已完成聚焦静态前置复核；逻辑最小字段与零既有记录修改边界已固定。
- [x] `DR-EMP-021/IMPL-EMP-030/TEST-EMP-022/VAL-EMP-014` 已形成strict只读探针和run-01不可变失败证据；失败后没有重试、补跑或追加查询。
- [x] `DR-EMP-022/IMPL-EMP-031～033/TEST-EMP-023/VAL-EMP-015` 已完成candidate-02非live实现、binary SQL、四阶段journal/failure、strict Schema、manifest/auth冻结和历史校验；未访问数据库。
- [x] `DR-EMP-023/IMPL-EMP-034/TEST-EMP-024/VAL-EMP-016` 已完成post-consumption双快照、严格证据与持续回归闭环。
- [x] `GATE-050` 已关闭；`IMPL-EMP-029/TEST-EMP-021`可恢复非live实施，但真实fixture和`GATE-049`仍禁止。
- [x] `DR-EMP-020/IMPL-EMP-029/TEST-EMP-021/VAL-EMP-017` 已完成fixture spec、repository Protocol/in-memory fake、strict lifecycle/evidence、故障注入和finally cleanup的non-live闭环。
- [x] `DR-EMP-024/IMPL-EMP-035～037/TEST-EMP-025/VAL-EMP-018` 已完成一次性真实create/verify/exact cleanup与post-consumption历史闭环；`GATE-051`关闭，candidate-01不可重放。
- [x] `DR-EMP-025/IMPL-EMP-038～040/TEST-EMP-026/VAL-EMP-019` 已完成candidate-03 non-live实施、三轮代码复核、冻结和全量回归；正式SQL/JWT/detail及`GATE-049`均未执行。
- [x] candidate-03首SQL前Spring配置歧义失败已以精确SHA-256有限证据归档；SQL/detail/model均0且run不可复用。
- [x] `DR-EMP-026/IMPL-EMP-041～043/TEST-EMP-027/VAL-EMP-020` candidate-04 non-live实现、冻结与三轮代码对照设计复核已完成；正式live仍受`GATE-049`阻断。
- [x] `DR-EMP-027/IMPL-EMP-044/TEST-EMP-028/VAL-EMP-021` 已固定candidate-04唯一live的业务成功、exact cleanup、三项证据SHA和冻结validator拒绝反证；run不可复用。
- [x] `DR-EMP-028` 已把candidate-05的versioned finalizer、validator前置、历史/asset冻结和测试反证设计到可实施粒度。
- [x] `CR-EMP-QUAL-002` 已由`IMPL-EMP-045～047/TEST-EMP-029/VAL-EMP-022`关闭：live同路finalizer、16条validator、invalid无result、17项history与12项asset冻结均已通过；`GATE-049`继续Open。
- [x] candidate-05唯一live失败已按三项精确SHA及16事件归档；run不可重跑，`GATE-049`未关闭。
- [x] `DR-EMP-029/IMPL-EMP-048～050/TEST-EMP-030/VAL-EMP-023`已完成candidate-06四键一致性修复、23项history/12项asset冻结、唯一live、五项SHA锁定与聚焦复核；`GATE-049`已关闭。
- [x] `DR-EMP-030/IMPL-EMP-051～053/TEST-EMP-031/VAL-EMP-024`已完成candidate-03统一journal、五Schema、Java/Python/launcher同路finalizer、17项history/28项asset冻结和三轮内审；`GATE-052`关闭，`GATE-024`未执行。
- [x] `DR-EMP-031/IMPL-EMP-054/TEST-EMP-032/VAL-EMP-025`已完成：candidate-04以全新run/manifest/auth冻结answer v2、current bootstrap和不可变历史，`GATE-054`关闭；live仍须另行精确授权`GATE-024`。
- [x] `REQ-EMP-023/CON-EMP-021/DR-EMP-032`已定义Employee外层bootstrap、pre-candidate失败、PID/secret/log和inner唯一权威边界。
- [x] `IMPL-EMP-055/TEST-EMP-033/VAL-EMP-026`已完成non-live实现、两步冻结、全量回归和代码对照设计复核。
- [x] `REQ-EMP-024/CON-EMP-022/DR-EMP-033`已把wrapper-v1转为prepared只读历史，并为wrapper-v2固定auth JAR/source/build、有限诊断和inner唯一权威边界。
- [x] `IMPL-EMP-056/TEST-EMP-034/VAL-EMP-027`已完成non-live实现、两步冻结、全量回归和代码对照设计复核；共享Transaction v2资产无漂移，`GATE-062`关闭。
- [x] wrapper-v2唯一失败已按outer lifecycle/result精确SHA归档；candidate/SQL/detail/model为0，旧run不得重跑、续跑或改写。
- [ ] `DR-EMP-034/IMPL-EMP-057/TEST-EMP-035/VAL-EMP-028`尚未实施并转Deferred；不阻塞当前Employee Provider + stub系统E2E。未来恢复实验时须新建立项、门禁和授权，不得复用`GATE-063/024`。
- [x] `DR-EMP-035`已完成当前交付周期治理收敛；P3 `GATE-063/024/033`为Not Applicable，`SA-GATE-006.EMPLOYEE`继续Open并只约束真实Employee结果外发。

## 18. 当前结论

本文v0.50为Approved；当前规范权威为需求/约束/决策、当前门禁表和本节结论，历史评审与运行章节只作不可变审计轨迹。历史Adapter、Provider、Gateway日志安全、资格、candidate-04、wrapper-v1/v2、共享Transaction资产及全部哈希继续有效且字节不变。Employee wrapper-v2唯一执行仍以`failed_pre_candidate_unconsumed/asset_hash_invalid`归档，candidate/SQL/detail/model均0。该test-only wrapper组合缺口和真实Employee结果模型实验均转Deferred；P3 `GATE-063/024/033`在当前周期为Not Applicable。当前系统E2E可使用已验证Employee Provider与默认stub模型，模型outbound=0。`SA-GATE-006.EMPLOYEE`保持Open，继续禁止真实Employee结果外发；未来恢复实验必须使用全新工作包、按需要建立的新有界门禁与精确授权并优先复用通用harness，不能复用历史run或授权。
