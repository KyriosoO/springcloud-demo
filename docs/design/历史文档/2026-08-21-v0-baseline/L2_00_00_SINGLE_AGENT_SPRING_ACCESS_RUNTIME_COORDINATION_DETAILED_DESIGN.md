# [L2_00_00] 单体 Agent Spring 接入与运行协同详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Spring 接入与运行协同详细设计 |
| 文档编号 | `L2_00_00` |
| 文档路径 | `docs/design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 历史 5 轮独立设计评审及 v0.4 Access 实施验证保持有效；v0.5 混合动作解析兼容结论保持；v0.6 已核实 Runtime 受管资源 lifespan 关闭接缝不改变 HTTP/OpenAPI/身份/时限/取消契约；v0.7 仅同步问题出域非 live 安全门禁证据；v0.8 `WP-SYSTEM-E2E-01` 聚焦设计评审符合；v0.9 代码对照设计复核未发现未关闭 Blocker/High/Medium |
| 当前版本 | v0.9 |
| 日期 | 2026-08-20 |
| 适用范围 | `agent-service` 外部接入、Spring→Python 内部协议、总时限与取消、双进程健康及观测 |
| 上位文档 | `REQ_00`、`L0_00`、`L1_00` |
| 直接依赖 | `L2_00_01` v0.10（Approved）的 `AgentRuntimeInvoker`、含 `original_question` 的执行上下文与 `AgentSemanticOutcome`；混合动作解析与模型装配均位于该调用边界之后 |
| 关联文档 | `L2_00_02` v0.17、`L1_01` v0.4、`L1_02` v0.4 |
| 实现基线 | `agent-contracts` 契约资产、`agent-runtime` FastAPI 回环入口与 `agent-service` Spring 接入均已存在；真实 Knowledge/Employee/Transaction Provider + 固定 stub 模型的 Spring→Runtime 系统 E2E 已通过 7 个场景。Runtime lifespan 可选识别并 `await runtime.aclose()`；public/internal OpenAPI、Spring DTO、HTTP 路由和 Runtime 入站签名均未改变 |
| 是否可作为实现依据 | 按范围可用 |
| 实施依据说明 | `WP-ACCESS-CONTRACT-01`、`WP-ACCESS-RUNTIME-01`、`WP-ACCESS-SPRING-01`、`WP-ACCESS-E2E-01` 已完成并通过限定验证；`CR-GATE-002` 已按该范围关闭，不替代真实模型/领域/发布门禁 |
| 当前允许实施范围 | 维护已完成的 OpenAPI、Spring/Runtime 接入代码和本地 stub 测试；按 `WP-SYSTEM-E2E-01` 新增测试范围三能力组合根、启动器、系统 E2E 与有限证据，真实 Provider 只用于只读联调且模型固定 stub |
| 当前禁止动作 | 修改生产 `agent-runtime.main`、公开/内部 OpenAPI、Spring 接入或领域 Provider 契约；读取 `LLM_API_KEY`、调用外部模型或把真实 Employee/Transaction 结果送入模型；加入父 POM、正式 Eureka/Gateway 路由、发布或宣称生产/P5 效果生效 |
| 修改权限 | 用户目标已授权文档聚焦修改、`WP-SYSTEM-E2E-01` 代码/受控环境实施及非 Markdown Git 提交推送；Markdown 仅原子同步，不纳入 Git 提交 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 第二批 L2 详细设计 | 创建 Spring 接入、跨进程协议、时限取消、健康与观测的实现级设计 |
| 2 | 2026-07-25 | 4.2、9、10、15、18～19 | 作者第 1 轮自检修复 | 展开全部追踪 ID，明确详细流程与权限/审计章节，规范建议新增测试路径和实施依据字段 |
| 3 | 2026-07-25 | 1～4、8～9、14～15、17～20 | 原子同步 `L2_00_01` v0.4 原始问题上下文补正 | 固定同一已校验 `question` 同时用于图输入和 `CapabilityExecutionContext.original_question`，补充不同源零调用失败与测试追踪；外部/内部 HTTP 字段不变 |
| 4 | 2026-07-25 | 14、19～20 | 本批次收口校验 | 重新执行严格文档校验并记录 0 errors、0 warnings；状态仍为 Draft，不替代独立评审 |
| 5 | 2026-07-25 | 8～15、17～21 | 独立评审第 1 轮修复 | 使响应预留进入 Runtime 子截止，统一 120 秒配置上限；补齐双端请求体和 WebClient 响应的前置字节限制；改为应用级 Runtime 准入并固定 429；补齐内部版本 Header、WebFlux/FastAPI 边界签名及回环信任假设 |
| 6 | 2026-07-25 | 8～15、17、19～21 | 独立评审第 2 轮修复 | 固定安全过滤器与 DTO 绑定前的统一公共错误信封；以最早 WebFilter 单调时钟定义总预算起点；对齐 16KiB JWT 与 32KiB 双端 Header 容量；明确 watcher 回收和 Jackson 未知字段配置 |
| 7 | 2026-07-25 | 4、8～10、14～15、17、19～21 | 独立评审第 3 轮修复 | 覆盖 FastAPI 默认 422/验证详情，穷尽 Runtime 非 200 传输映射，固定 WebClient 非 2xx 正文释放，并收窄应用错误信封对服务器级 Header 拒绝的承诺 |
| 8 | 2026-07-25 | 9、14～15、19～21 | 独立评审第 4 轮修复 | 固定问题长度按 Unicode code point 计数，由 Java 单一 validator 执行一次 `strip` 与计数，避免 `String.length/@Size` 和 Python `len` 漂移 |
| 9 | 2026-07-25 | 1～2、15、19～21 | 独立评审第 5 轮终审 | 从第 4 轮修订后全文复核，无新增 S0/S1/S2；关闭 `REV-ACCESS-017`，状态转 Approved；保留 `CR-GATE-002` Open 和未实施事实 |
| 10 | 2026-08-01 | 1～3、14～17、20～21 | `WP-ACCESS-CONTRACT-01` 实施完成后的原子证据同步 | 记录两份 OpenAPI、15 个 fixture case、独立测试配置和 21 项验证；把 `IMPL-ACCESS-001/002/014` 更新为已存在，保持 `IMPL-ACCESS-015` 归 Runtime HTTP；收窄但不关闭 `CR-GATE-002`，禁止误授权服务实现 |
| 11 | 2026-08-01 | 1～3、5～7、14～17、19～21 | 三个 Access 运行工作包实施完成后的原子证据同步 | 记录 FastAPI ingress、Spring 接入和本地双进程闭环；同步实现落点、31 项 Java、180 项 Runtime、21 项契约资产验证及代码对照设计评审；关闭 `CR-GATE-002`，保持真实模型、领域和部署门禁 Open |
| 12 | 2026-08-07 | 1～2、6、20～21 | Core/Model 混合动作解析定向兼容同步 | 确认 action 参数权威变化位于 `AgentRuntimeInvoker` 内部，public/internal OpenAPI、Spring/Python HTTP DTO、原始问题同源、JWT、deadline/cancel 和语义响应均不变；不新增 Access 实现工作包 |
| 13 | 2026-08-12 | 1～2、14～17、20～21 | `WP-MODEL-RUNTIME-01` 生命周期接缝原子同步 | FastAPI lifespan 在撤销readiness和runtime引用后可选await受管invoker的`aclose()`；新增关闭一次测试。未修改路由、DTO、OpenAPI、Spring接入或外部错误语义 |
| 14 | 2026-08-12 | 1～2、17、20～21 | 问题出域非 live 安全证据镜像同步 | `L2_00_02` 输入分类/最小化、Knowledge/Business fixture、denied/unknown 零 transport 与全量回归通过，`CR-GATE-003` 按问题输入安全前置范围关闭；Access 仍只透传到受控 Runtime，HTTP/OpenAPI 契约不变 |
| 15 | 2026-08-20 | 1～4、7～8、12、14～18、20～21 | `WP-SYSTEM-E2E-01` 实施前聚焦设计补充 | 增加测试范围三能力组合根、真实 Provider + 默认 stub 双进程矩阵、受控进程所有权、有限证据与零外部模型出域规则；不修改生产入口、公共契约、领域契约或历史 evidence |
| 16 | 2026-08-20 | 1～2、6、12、14～15、17、19～21 | `WP-SYSTEM-E2E-01` 实施、验证与代码对照设计复核同步 | 记录测试范围组合根、Java 公共入口 E2E、受控 launcher、严格有限 evidence、资源关闭和日志清理；7 个场景通过，外部模型调用与日志泄漏均为 0，公共契约保持不变 |

## 3. 背景、目标与范围

### 3.1 背景与问题

当前工作区已有 Gateway、Config Server、Eureka、`auth-service`、`common-security`、`agent-service`、`agent-runtime` 与共享契约资产。`L1_00` 确定的双进程逻辑 Agent 已按本 L2 完成本地 stub 闭环：Spring 拥有外部认证、请求治理和总时限，Python/LangGraph 拥有唯一 Agent 编排；真实模型、Knowledge、Business 与外部路由仍未接入。

### 3.2 目标与验收行为

| 需求编号 | 目标或用户可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-ACCESS-001` | 提供一个受 JWT 保护的 Agent 查询入口 | 缺失/无效 JWT 返回 401；非 `token_type=user` 返回 401；运行时调用为零 | `SEC-01`、`L1_00` 7.1 |
| `REQ-ACCESS-002` | 将一个有界问题传给唯一 Python 运行入口 | 一次外部请求最多一次内部 invoke；Spring 不选择动作、不调用 Adapter | `FR-01`、`CR-AD-001/002` |
| `REQ-ACCESS-003` | Java/Python 对请求、响应和错误含义一致 | 以 OpenAPI 3.1 为契约源，双端契约测试覆盖字段、枚举、空值和未知字段 | `L1_00` 7.4、16.1 |
| `REQ-ACCESS-004` | 全链路受同一总时限约束 | Spring 建立 60 秒硬截止时间；Python 只能消费剩余预算；逾期结果不返回 | `CR-AD-004` |
| `REQ-ACCESS-005` | 客户端断连或总时限耗尽后停止新增工作 | Spring 取消内部 HTTP；Python 发布取消信号并停止安排新节点 | `L1_00` 9.3、10.4 |
| `REQ-ACCESS-006` | 保持运行时确定性状态 | Spring 仅映射 `AgentSemanticOutcome`，不得把失败改写为成功 | `L1_00` 7.3、`L2_00_01` 11.1 |
| `REQ-ACCESS-007` | 两进程可独立诊断和重启 | 两端具备 liveness/readiness；Python 未完成组合根时不就绪 | `L1_00` 10.4、10.6 |
| `REQ-ACCESS-008` | 入口和跨进程负载有界 | 问题、正文、并发、响应与协议字段越界均在规定边界失败关闭 | `REQ_00` 9、10 |
| `REQ-ACCESS-009` | 身份可透传且不泄露 | 原始 JWT 仅位于 Authorization header/脱敏 wrapper；不进入正文、日志或响应 | `SEC-02`、`L2_00_01` 8.5 |
| `REQ-ACCESS-010` | 单实例个人项目可最小部署 | 默认同机回环地址、单 Python worker、无数据库/队列/请求续跑 | `REQ_00` 2、4.2；`L1_00` 10.6 |
| `REQ-ACCESS-011` | Runtime 为图与能力上下文绑定同一个权威原始问题 | Python 入站完成一次校验后，以同一字符串构造图输入和 `CapabilityExecutionContext.original_question`；不同源时图、模型、validator、handler 调用均为零 | `L2_00_01` v0.4 `DR-CORE-014` |
| `REQ-ACCESS-012` | 从 Spring 公共入口验证三种查询能力的完整双进程闭环 | Knowledge、Employee、Transaction 各至少覆盖真实 Provider 允许与业务域拒绝；联合既有 Access 运行时不可达和参数失败场景覆盖失败关闭；模型 provider 固定 stub，真实业务结果外部模型 outbound 为 0 | `P3_00 WP-SYSTEM-E2E-01`、`DR-BQCOM-046`、`DR-EMP-035`、`DR-TXN-020` |

### 3.3 范围内

- `POST /api/v1/agent/queries` 外部同步 JSON 契约。
- Spring WebFlux JWT 入口、用户主体提取、问题校验、并发准入与响应封装。
- `POST /internal/v1/agent-runs:invoke` 内部同步 JSON 契约。
- Java→Python 原始用户 JWT、主体、关联标识、契约版本和剩余时限传递。
- Python HTTP 入口构造 `RequestExecutionScope` 并调用 `AgentRuntimeInvoker.ainvoke`。
- 连接取消、总时限、迟到结果丢弃、协议错误映射。
- 双进程 liveness/readiness、最小日志和指标。
- 配置键、启动校验、部署顺序、回滚及测试落点。
- `WP-SYSTEM-E2E-01` 的测试范围组合根、受控本地启动器、三能力矩阵和有限证据；不构成新的生产启动方式。

### 3.4 范围外

- LangGraph 图、能力 API、注册表和领域结果组合；归 `L2_00_01`。
- DeepSeek Provider、模型输入和回答校验；归 `L2_00_02`。
- Knowledge、Employee、Transaction 的动作、协议和权限规则。
- Gateway 路由改造、`common-security` 公共契约修改、角色映射。
- 生产级 HA、集群、服务网格、持久请求表、幂等存储、断点续跑。
- SSE/WebSocket/流式回答、会话历史和多轮记忆。

### 3.5 适用技术剖面

| 剖面 | 适用 | 本文落实 |
|---|---|---|
| Java/Spring | 是 | WebFlux controller、application service、运行时客户端、配置、健康、契约与测试 |
| Python/ASGI | 是 | FastAPI 传输边界、Pydantic 传输模型、取消观察、运行入口与测试 |
| 跨语言 HTTP 契约 | 是 | OpenAPI 3.1、固定枚举、版本、样例与双端契约测试 |
| 数据库/迁移 | 否 | 全链路无持久状态，不新增 Schema 或迁移 |
| 消息/异步任务 | 否 | 单请求同步等待，不引入队列、回调或后台续跑 |
| 前端 | 否 | 本文只定义 HTTP API，不设计页面 |

## 4. 上位约束与追踪关系

### 4.1 上位与同层约束

| 约束编号 | 上位文档/契约位置 | 约束内容 | 本设计落实方式 | 偏离情况 |
|---|---|---|---|---|
| `CON-ACCESS-001` | `L1_00` 5.3、`CR-AD-001` | Spring 与 Python 是两个进程、一个逻辑 Agent | `DR-ACCESS-001/002` | 无 |
| `CON-ACCESS-002` | `L1_00` `CR-AD-002` | LangGraph 是唯一编排权威 | Spring 只做接入与映射，见 `DR-ACCESS-003` | 无 |
| `CON-ACCESS-003` | `L1_00` `CR-AD-004` | Spring 拥有总时限且不重放 | `DR-ACCESS-007/008` | 无 |
| `CON-ACCESS-004` | `L1_00` 10.2 | Runtime 不是第二个外部入口 | 回环绑定和 Gateway 不路由，见 `DR-ACCESS-005` | 无 |
| `CON-ACCESS-005` | `L2_00_01` 8.5 | Python 消费不可变执行上下文 | 严格转换为 `CapabilityExecutionContext`，见 `DR-ACCESS-006` | 无 |
| `CON-ACCESS-006` | `L2_00_01` 11.1 | 跨进程输出为 `AgentSemanticOutcome` | 内部响应一一映射，见 `DR-ACCESS-011` | 无 |
| `CON-ACCESS-007` | `REQ_00` SEC-02/03 | 原始用户 JWT 透传，不回退服务身份 | `DR-ACCESS-004/006` | 无 |
| `CON-ACCESS-008` | `L1_00` 10.6 | 不新增 Agent 数据库、缓存、消息队列 | 传输和运行状态仅请求内存，见 `DR-ACCESS-014` | 无 |
| `CON-ACCESS-009` | `L1_00` 7.4、16.1 | 内部协议独立版本化并防漂移 | 两份 OpenAPI 权威源和契约测试，见 `DR-ACCESS-002/012` | 无 |
| `CON-ACCESS-010` | `L1_00` 13 | 本文不定义图、能力或模型供应商字段 | 范围外及依赖方向明确 | 无 |
| `CON-ACCESS-011` | `L2_00_01` v0.4 8.5、11.1 | 原始问题不得由模型候选重建或在 Runtime 内静默覆盖 | `DR-ACCESS-017` | 无 |
| `CON-ACCESS-012` | `P3_00 WP-SYSTEM-E2E-01`、`L2_01_01`、`L2_02_00/01/02` | 系统 E2E 必须复用真实只读 Provider 和既有权限边界；默认模型保持 stub，Employee/Transaction 真实结果不得出域 | `DR-ACCESS-019` | 无；仅新增测试装配和证据 |

### 4.2 端到端追踪矩阵

| REQ/CON | 模块切片 | 设计规则 | 责任主体 | 契约/状态影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-ACCESS-001`、`CON-ACCESS-001`、`CON-ACCESS-004`、`CON-ACCESS-007` | Spring 入口 | `DR-ACCESS-001`、`DR-ACCESS-004`、`DR-ACCESS-005` | `agent-service` | JWT/subject、唯一外部入口 | `IMPL-ACCESS-004`、`IMPL-ACCESS-005` | `TEST-ACCESS-002` | `VAL-ACCESS-002` |
| `REQ-ACCESS-002`、`CON-ACCESS-002`、`CON-ACCESS-010` | 请求协调 | `DR-ACCESS-003` | application service | 一次内部调用且不编排 | `IMPL-ACCESS-006` | `TEST-ACCESS-003` | `VAL-ACCESS-002`、`VAL-ACCESS-003` |
| `REQ-ACCESS-003`、`CON-ACCESS-009` | 契约 | `DR-ACCESS-002`、`DR-ACCESS-012` | OpenAPI 契约 | 两个版本 1 API | `IMPL-ACCESS-001`、`IMPL-ACCESS-002`、`IMPL-ACCESS-014` | `TEST-ACCESS-001`、`TEST-ACCESS-008` | `VAL-ACCESS-003` |
| `REQ-ACCESS-004`、`CON-ACCESS-003` | 时限 | `DR-ACCESS-007` | Spring + Runtime ingress | 硬截止/单调截止 | `IMPL-ACCESS-006`、`IMPL-ACCESS-009`、`IMPL-ACCESS-011` | `TEST-ACCESS-004` | `VAL-ACCESS-002`、`VAL-ACCESS-004` |
| `REQ-ACCESS-005` | 取消 | `DR-ACCESS-008` | 两端传输边界 | 首个取消来源 | `IMPL-ACCESS-006`、`IMPL-ACCESS-011` | `TEST-ACCESS-005` | `VAL-ACCESS-004` |
| `REQ-ACCESS-006`、`CON-ACCESS-006` | 响应 | `DR-ACCESS-010`、`DR-ACCESS-011` | Runtime ingress + Spring mapper | status 不改义 | `IMPL-ACCESS-007`、`IMPL-ACCESS-010` | `TEST-ACCESS-006` | `VAL-ACCESS-003` |
| `REQ-ACCESS-007` | 运行治理 | `DR-ACCESS-013`、`DR-ACCESS-016` | 两进程 | liveness/readiness、启动冻结 | `IMPL-ACCESS-012`、`IMPL-ACCESS-013` | `TEST-ACCESS-007` | `VAL-ACCESS-005` |
| `REQ-ACCESS-008` | 容量 | `DR-ACCESS-009` | Spring + Runtime ingress | 有界正文/并发 | `IMPL-ACCESS-003`、`IMPL-ACCESS-008`、`IMPL-ACCESS-009` | `TEST-ACCESS-003`、`TEST-ACCESS-004` | `VAL-ACCESS-002`、`VAL-ACCESS-004` |
| `REQ-ACCESS-009`、`CON-ACCESS-005` | 身份转换 | `DR-ACCESS-006`、`DR-ACCESS-015` | 两端入口 | token 不入正文/state/log | `IMPL-ACCESS-005`、`IMPL-ACCESS-010`、`IMPL-ACCESS-015` | `TEST-ACCESS-002`、`TEST-ACCESS-009` | `VAL-ACCESS-003`、`VAL-ACCESS-004` |
| `REQ-ACCESS-010`、`CON-ACCESS-008` | 部署与重复语义 | `DR-ACCESS-014` | 组合根/启动配置 | 单 worker、无持久化/重放 | `IMPL-ACCESS-003`、`IMPL-ACCESS-012`、`IMPL-ACCESS-016` | `TEST-ACCESS-007`、`TEST-ACCESS-010` | `VAL-ACCESS-005` |
| `REQ-ACCESS-011`、`CON-ACCESS-011` | 原始问题绑定 | `DR-ACCESS-017` | Python ingress + Runtime invoker | 一份已校验问题、两个只读消费视图 | `IMPL-ACCESS-011/015` | `TEST-ACCESS-011` | `VAL-ACCESS-003/004` |
| `REQ-ACCESS-001`、`REQ-ACCESS-003`、`REQ-ACCESS-008` | 公开失败信封 | `DR-ACCESS-018` | metadata/security/error boundary | 进入应用链后的前 Controller 失败保持公共字段与零 Runtime 调用 | `IMPL-ACCESS-004/007/017/019` | `TEST-ACCESS-002/012` | `VAL-ACCESS-002/003` |
| `REQ-ACCESS-012`、`CON-ACCESS-012` | 三能力系统 E2E | `DR-ACCESS-019` | 测试范围组合根与启动器 | 生产契约零变化；真实 Provider、stub 模型、有限证据 | `IMPL-ACCESS-022/023/024/025` | `TEST-ACCESS-013` | `VAL-ACCESS-006` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 交互契约 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|---|
| `REQ_00`、`L0_00`、`L1_00` | parent | 落实接入与协同 | 规定需求和架构边界 | 约束映射 | 上位文档 | 只读 |
| `L2_00_01` | peer/direct dependency | 传输适配 | 定义核心类型、运行入口与语义输出 | Python 进程内调用 | LangGraph/核心状态 | 只读 |
| `L2_00_02` | peer | 传播剩余预算和结果 | 定义模型调用及答案校验 | `AgentSemanticOutcome` | 模型请求状态 | 只读 |
| `common-security` | implementation baseline / external contract | 复用资源服务器与 JWT decoder | 验签、JWT 基础类型 | Spring Security | JWT 密钥和验证 | 只读 |
| `auth-service` | external contract | 消费用户 JWT | 签发 subject、`token_type=user`、role | Bearer JWT | 用户与角色 | 只读 |
| `agent-service` | implemented target | 外部接入、硬时限、调用与协议映射 | 不做编排或领域处理 | 外部/内部 HTTP | Spring 请求状态 | 已存在并完成本地限定验证 |
| `agent-runtime` HTTP 入口 | implemented target | 内部传输、scope 构造、取消观察 | 不做业务选择 | 内部 HTTP + 进程内 invoker | Python 传输状态 | 已存在并完成本地限定验证 |
| OpenAPI 3.1 文件 | implemented contract | 两个 HTTP 契约的唯一字段权威 | 双端按契约实现 | YAML | 契约版本 | 已存在并由双端消费验证 |

外部框架事实依据 [FastAPI 官方说明](https://fastapi.tiangolo.com/) 与 PyPI 当前稳定版本页面：[FastAPI](https://pypi.org/project/fastapi/)、[Uvicorn](https://pypi.org/project/uvicorn/)、[Pydantic](https://pypi.org/project/pydantic/)。这些事实只用于选择新传输边界，不证明目标代码已存在。

## 6. 当前实现基线与最小变更方案

### 6.1 已核实当前实现

1. `serviceCenter/pom.xml` 当前管理 Spring Boot `3.5.10`、Spring Cloud `2025.0.1` 和 Java 25。
2. `common-security` 已提供 Servlet/Reactive Resource Server 自动配置、JWT decoder 与 `SecurityTokenUtils.isUserToken`。
3. `auth-service` 当前签发 `sub`、`iat`、`exp`、`token_type=user` 和 `role`；`dylan` 当前分配 `ADMIN`。
4. Gateway、Eureka、Config Server 与 Actuator 基础设施已存在。
5. `agent-service` Maven 模块、`agent-runtime` Python 工程及两份 Agent HTTP OpenAPI 已存在；`agent-service` 未加入父 POM、Gateway、Eureka 或生产配置。
6. `L2_00_01` 的 Core 与本 L2 的 Runtime HTTP 入口已存在；当前组合根只装配无模型、无领域 Provider 的本地 stub。

### 6.2 当前问题与根因

| 问题 | 直接原因 | 设计根因 |
|---|---|---|
| 无 Agent 外部入口 | 目标 Spring 模块不存在 | 接入治理尚未下沉到 L2 |
| Java/Python 字段可能漂移 | 无跨语言契约源 | 不能仅靠两端手写 DTO |
| 超时与取消含义不确定 | 无硬截止和连接取消规则 | 各进程可能各自启动完整超时 |
| Runtime 可能成为旁路入口 | 无网络暴露规则 | 双进程不等于双外部入口 |
| 状态可能被 Spring 改义 | 无精确映射矩阵 | 传输层和语义层未隔离 |

### 6.3 最小变更方案

| 变更项 | 必要性 | 复用内容 | 新增/修改原因 | 不采用的方案及原因 |
|---|---|---|---|---|
| 新增 `agent-service` | 必须 | Spring Cloud、common-security、Actuator | 承担唯一外部接入治理 | Spring 内嵌 Python/LangGraph会混合运行时；不采用 |
| 新增 FastAPI 内部入口 | 必须 | Python 3.12、`AgentRuntimeInvoker` | 提供异步取消感知的最小 HTTP 边界 | 自写 HTTP Server 增加协议风险；gRPC 对个人项目过重 |
| 新增两份 OpenAPI 3.1 | 必须 | 现有 Swagger 依赖/测试能力 | 防止跨语言契约漂移 | Java DTO 作为唯一权威无法直接约束 Python |
| 回环 HTTP/JSON | 必须 | 本地单实例部署 | 可调试、依赖少、支持连接取消 | 消息队列会引入持久状态；进程内 FFI 破坏进程隔离 |
| 单次同步响应 | 必须 | WebFlux/ASGI | 本期没有流式需求 | SSE/WebSocket 扩大状态与断连复杂度 |

## 7. 职责、分层与依赖设计

### 7.1 责任分解

| 组件/类/函数 | 状态 | 唯一职责 | 明确不负责 | 变化原因 | 输入/输出 |
|---|---|---|---|---|---|
| `AgentQueryController` | 已存在 | HTTP 字段绑定和响应状态输出 | JWT 解析、编排、重试 | 外部 API 变化 | DTO ↔ HTTP |
| `AgentQueryApplicationService` | 已存在 | 身份检查、预算、准入、一次 runtime 调用 | 动作选择、领域规则 | 接入治理变化 | query + Jwt → semantic response |
| `AgentRuntimeClient` | 已存在 | 稳定 Java 运行时调用边界 | HTTP 细节、自动重试 | 内部协议调用语义变化 | internal request → outcome |
| `WebClientAgentRuntimeClient` | 已存在 | HTTP 序列化、连接和传输错误转换 | 语义状态改写 | 传输实现变化 | OpenAPI DTO ↔ HTTP |
| `RuntimeIngress` | 已存在（`api.ingress`） | 校验内部请求、构造 scope、调用 invoker | 图编排、领域调用 | 内部协议变化 | transport request → outcome |
| `DisconnectWatcher` | 已存在 | 将上游连接断开转成一次性取消信号 | 强制中断第三方阻塞代码 | 取消传播变化 | ASGI request → signal |
| `AgentRuntimeInvoker` | 已存在，由 `L2_00_01` 定义 | 执行 LangGraph | HTTP/认证 | 核心图变化 | question + scope → outcome |
| 两份 OpenAPI 文件 | 已存在 | 字段、枚举和版本权威 | 运行逻辑 | HTTP 契约变化 | YAML schema |

### 7.2 允许依赖方向

```text
Caller/Gateway
  → agent-service.web
      → agent-service.application
          → AgentRuntimeClient
              ← WebClientAgentRuntimeClient
                  → agent-runtime.api
                      → AgentRuntimeInvoker
```

- Java web 层不得依赖 Python DTO、LangGraph、能力 API 或任何 Adapter。
- Python API 层只能依赖 transport model、执行上下文工厂和 `AgentRuntimeInvoker`。
- `AgentRuntimeInvoker` 不得依赖 FastAPI `Request`、Pydantic model 或 HTTP header。
- OpenAPI DTO 翻译仅发生在两端传输适配层；核心类型不带 camelCase/HTTP 注解。
- Spring 不得绕过 `AgentRuntimeClient` 直接调用业务服务；Runtime API 不得绕过 invoker 直接调用能力。

### 7.3 内聚与耦合判断

Spring 接入与 Python 编排分离是已确认的技术边界，不为每个步骤新增服务。OpenAPI 文件是跨语言稳定契约所需的最小共享资产；不生成独立部署模块。FastAPI/Pydantic 仅位于 `agent_runtime.api`，不得成为 `agent_runtime.core` 或能力 API 的依赖，保持 `L2_00_01` 的标准库核心约束。

## 8. 设计规则目录

| 规则编号 | 规则 | 责任主体 | 触发条件 | 输出/状态效果 |
|---|---|---|---|---|
| `DR-ACCESS-001` | 对外只暴露 Spring 查询入口 | `agent-service` | 任意用户请求 | Runtime 无公网/网关路由 |
| `DR-ACCESS-002` | 外部/内部契约分别以 OpenAPI 3.1 v1 为唯一字段权威 | 契约文件 | 构建与测试 | 漂移使契约测试失败 |
| `DR-ACCESS-003` | Spring 每请求只调用 Runtime 一次且不选择动作、不重放 | application service | 通过认证和准入 | 单 invoke 或明确失败 |
| `DR-ACCESS-004` | JWT 必须有效、subject 非空、`token_type=user` | Spring | 调用 Runtime 前 | 失败 401，内部调用为零 |
| `DR-ACCESS-005` | Runtime 默认绑定回环地址；在“单用户本机、无不受信本地进程”的冻结威胁模型内，Spring 是唯一受支持调用方 | Python 启动、部署约束 | 进程启动/调用 | 非回环或存在不受信本地调用方时不获本设计授权 |
| `DR-ACCESS-006` | JWT 只在 Authorization header 和 `OpaqueUserToken` 中传递 | 两端入口 | 内部调用 | 不进 JSON/state/log |
| `DR-ACCESS-007` | Spring 创建外层硬截止，并在扣除固定响应预留后创建 Runtime 子截止；Python 取子截止与发送时剩余时限的较小值 | 两端 | 请求接收 | 子调用不能占用响应预留或延长外层预算 |
| `DR-ACCESS-008` | 连接断开/超时通过取消信号停止新增节点，迟到结果丢弃 | 两端 | 取消或逾期 | 无后台可见结果 |
| `DR-ACCESS-009` | 请求正文、问题、并发和响应均有固定上限；正文限制必须在 DTO 解码前按实际接收字节执行，Runtime 响应限制必须在 WebClient 聚合时执行 | 两端 | 入口/客户端 | Content-Length 和 chunked 均越界失败关闭 |
| `DR-ACCESS-010` | Runtime 语义结果使用 HTTP 200，传输错误使用非 2xx | Python API | invoker 完成或协议失败 | 传输/语义不混淆 |
| `DR-ACCESS-011` | Spring 保持 status、capability、answer、userResult、failure 语义 | response mapper | 收到合法内部响应 | 不改义、不补造领域结果 |
| `DR-ACCESS-012` | 未知字段/枚举/版本均失败关闭，不做宽松兼容 | 两端 DTO | 解析请求/响应 | 明确协议失败 |
| `DR-ACCESS-013` | liveness 只证明进程存活，readiness 证明本地对象图有效及对端可达 | 两进程 | 健康探测 | 可诊断启动顺序 |
| `DR-ACCESS-014` | 不持久化请求、不去重、不续跑；重复提交是新请求 | 两端 | 重复或重启 | 无幂等承诺 |
| `DR-ACCESS-015` | 日志仅记录安全元数据，异常正文不进入响应或日志 | 两端 | 全部边界 | JWT/问题/结果不泄露 |
| `DR-ACCESS-016` | 运行时配置启动校验并冻结，变更重启生效 | 两端组合根 | 启动 | 非法配置不就绪 |
| `DR-ACCESS-017` | Python ingress 对 `payload.question` 只校验一次并保存为局部不可变值；该值同时传给 `AgentRuntimeInvoker.ainvoke(question=...)` 和 `CapabilityExecutionContext.original_question`，不得再次 trim、改写或从模型候选回填 | Python ingress、Runtime invoker | 合法内部请求 | 同源进入图与 handler；不一致固定失败关闭 |
| `DR-ACCESS-018` | 已通过 HTTP framing 并进入 Spring 应用过滤链的公开端点请求，在安全过滤器、codec、参数绑定、准入和 Runtime 映射各阶段均使用同一安全响应信封；请求元数据在安全链之前只创建一次 | Spring WebFilter、安全处理器、异常映射器 | 应用链内公开端点响应 | 401/400/413/415/429 与语义结果字段一致，且失败阶段不会调用 Runtime |
| `DR-ACCESS-019` | `WP-SYSTEM-E2E-01` 只在测试范围建立一个由既有 `RuntimeCompositionRoot` 组装的三能力 Runtime：Knowledge 复用真实 ES/BGE Retrieval，Employee/Transaction 复用真实只读 Adapter；模型任务统一由本地确定性 stub transport 响应。系统矩阵经 Spring 公共 API 发起，真实用户 JWT 只驻留进程内存；Employee 标识只从进程环境读取。允许路径验证 `success/no_result`，未知角色 JWT 必须由各 Provider 最终返回 `forbidden`；失败路径联合既有 Runtime unavailable 与本地参数失败证明，禁止为了制造失败停止非本次拥有的服务。运行证据仅持久化 case/status、调用整数、provider 类型、清理与零泄漏布尔值，不保存问题、JWT、员工标识、知识/业务内容或原始响应 | 测试范围 Python 组合根、Java E2E 与版本化 launcher | 执行 `WP-SYSTEM-E2E-01` | 三能力真实 Provider 闭环；external model outbound=0；不改变生产启动与契约 |

## 9. 详细功能与流程设计

### 9.1 接口与跨语言契约设计

| 契约 | 建议权威路径 | 版本传递 | 生产者 | 消费者 |
|---|---|---|---|---|
| 外部 Agent API | 建议新增：`agent-contracts/openapi/agent-public-v1.yaml` | URI `/api/v1` | `agent-service` | Gateway/调用方 |
| 内部 Runtime API | 建议新增：`agent-contracts/openapi/agent-runtime-internal-v1.yaml` | URI `/internal/v1` + body `contractVersion=1` | `agent-runtime` | `agent-service` |

OpenAPI 是字段、必填、空值、枚举和 example 的唯一传输权威。Java record 与 Python Pydantic model 为手写实现，禁止把任一端实现反向视为契约源。实现阶段可添加 schema 校验测试，不要求引入代码生成器。破坏性变更创建 v2 路径并同步两端；本期不支持 v1/v2 混跑。

### 9.2 外部请求

`POST /api/v1/agent/queries`

Headers：

| Header | 必填 | 约束 | 语义 |
|---|---|---|---|
| `Authorization` | 是 | `Bearer <JWT>`；总 header 受服务器限制 | 用户 JWT |
| `X-Correlation-Id` | 否 | 可打印 ASCII 1～128；非法值不回显并由 Spring 生成 UUID | 调用链关联 |
| `Content-Type` | 是 | `application/json` | 不接受 form/multipart |

Body：

| 字段 | 类型 | 必填/空值 | 约束 |
|---|---|---|---|
| `question` | string | 必填、不可空 | 去除首尾空白后 1～4096 字符；不得静默截断 |

未知字段拒绝；正文最大 32768 bytes。当前不接收 `conversationId`、历史消息、动作 ID、模型名、URL、超时、角色或物理资源。

“字符”精确定义为 Unicode code point。Java 不得用 `String.length()` 或 Bean Validation
`@Size(max=4096)` 作为最终长度权威；`AgentQuestionValidator.normalize` 必须只执行一次
`String.strip()`，再以 `codePointCount(0, normalized.length())` 校验 1～4096，并将该同一
字符串继续传给内部 DTO。Python 内部模型以 `len(str)` 校验相同 code point 上限且不得再
trim。UTF-8 字节总量另受 32768-byte 正文上限约束。

`AgentRequestMetadataWebFilter` 以最高应用过滤顺序为每次
`POST /api/v1/agent/queries` 创建一次 `requestId`、安全 `correlationId` 和
`receivedMonotonicNanos`，写入只读 exchange attribute；它不读取正文、JWT claim 或用户
身份。后续 Security entry point、codec/validation 异常映射、准入和 Controller 必须复用
该对象，不得分别生成不同 requestId 或重新接受非法 correlation ID。

### 9.3 外部响应

| 字段 | 类型 | 必填/空值 | 语义 |
|---|---|---|---|
| `requestId` | string | 必填 | Spring 每请求生成 UUID，不是幂等键 |
| `correlationId` | string | 必填 | 安全关联标识 |
| `status` | enum | 必填 | 与 `CapabilityStatus` 同值 |
| `capabilityId` | string | 可空 | 仅核心已 claim 动作后存在 |
| `answer` | string | 可空 | 固定安全文本或已校验模型答案 |
| `result` | object | 可空 | 仅 `AgentSemanticOutcome.user_result`；不含 safe payload |
| `error` | object | 可空 | 失败时仅 `code`、`source` |

`error.source` 只允许 `core/capability/downstream/policy`。响应不包含 JWT、role、Prompt、模型推理、`safe_payload`、策略正文、原始异常或下游响应。

| 语义状态 | HTTP | `result` | `error` |
|---|---:|---|---|
| `success` | 200 | 可空 | 空 |
| `no_result` | 200 | 可为受控覆盖元数据 | 空 |
| `unsupported` | 422 | 空 | 必填 |
| `invalid_argument` | 400；仅 `core.request_body_too_large` 为 413，`core.unsupported_media_type` 为 415 | 空 | 必填 |
| `unauthenticated` | 401 | 空 | 必填 |
| `forbidden`、`model_egress_denied` | 403 | 空 | 必填 |
| `timeout` | 504 | 空 | 必填 |
| `downstream_failure` | 502；仅 `core.ingress_capacity_exceeded` 为 429 | 空 | 必填 |
| `internal_failure` | 500 | 空 | 必填 |

429 是 Spring 在调用 Runtime 前实施本地准入的唯一代码级例外；其响应保持
`status=downstream_failure`、`error.code=core.ingress_capacity_exceeded`、`error.source=core`，
且 `capabilityId/result` 为空。Runtime 的 429 不沿用该例外，而按 9.6 映射为外部 502。

公开端点在 Controller 前失败时仍使用同一 `AgentQueryResponse` 字段契约：

| 失败阶段 | HTTP | `status/error.code/source` | Runtime 调用 |
|---|---:|---|---:|
| JWT 缺失、无效、过期、空 subject、非 user token 或 token 超过 16384 UTF-8 bytes | 401 | `unauthenticated/core.user_identity_required/core` | 0 |
| JSON 非法、未知字段、问题字段非法 | 400 | `invalid_argument/core.invalid_request/core` | 0 |
| 实际正文超过 32768 bytes | 413 | `invalid_argument/core.request_body_too_large/core` | 0 |
| Content-Type 不是 `application/json` | 415 | `invalid_argument/core.unsupported_media_type/core` | 0 |
| Spring 准入超限 | 429 | `downstream_failure/core.ingress_capacity_exceeded/core` | 0 |

`AgentPublicErrorWriter` 是上述固定信封的唯一序列化器；Spring Security
`ServerAuthenticationEntryPoint`、`ServerAccessDeniedHandler` 和 WebFlux
`ErrorWebExceptionHandler` 只选择稳定 code/HTTP 并调用该 writer，不能把框架异常 message、
默认 HTML、OAuth 错误正文或 stack 写给调用方。

超过 `server.max-http-request-header-size`、非法请求行或其他 Reactor Netty HTTP framing
错误发生在任何应用 WebFilter 之前，无法取得 `AgentRequestMetadata`，因此不承诺
`AgentQueryResponse` 信封；服务器按固定 400/431 关闭请求，应用/Runtime 调用为零。该边界
只接受“组合 Header≤32KB 且 user token≤16KiB”的公开 API 输入，不能把 transport reject
解释为 Agent 语义状态。

### 9.4 内部请求

`POST /internal/v1/agent-runs:invoke`，非流式 JSON。

| 位置/字段 | 类型 | 必填 | 约束与转换 |
|---|---|---:|---|
| Header `Authorization` | Bearer JWT | 是 | 原样来自已认证 Spring token；不写 body |
| Header `X-Agent-Contract-Version` | string | 是 | 当前精确为 `1` |
| `contractVersion` | integer | 是 | 当前精确为 1；与 header 不同即 409 |
| `requestId` | string | 是 | UUID；ASCII ≤128 |
| `correlationId` | string | 是 | ASCII 1～128 |
| `question` | string | 是 | 1～4096 字符 |
| `subject.id` | string | 是 | Spring 认证后的 `sub`；UTF-8 ≤256 bytes |
| `subject.type` | enum | 是 | 当前只能 `user` |
| `deadlineEpochMs` | int64 | 是 | Spring 计算的 Runtime 子截止 UTC epoch 毫秒，即外层硬截止减去 `response-reserve` |
| `remainingTimeoutMs` | int32 | 是 | 1～120000；发送时至 Runtime 子截止的剩余预算 |

Python 先把通过严格校验的 `question` 保存为单一局部值；该值既作为 `AgentRuntimeInvoker.ainvoke(question=...)` 的图输入，也由 `to_execution_scope` 原样写入 `CapabilityExecutionContext.original_question`。两处不得各自 trim、规范化或复制模型参数；Runtime 仍按 `L2_00_01` v0.4 执行精确相等闸门。该规则不增加内部协议字段。

Python 计算：

```text
effectiveRemainingMs =
  min(remainingTimeoutMs, deadlineEpochMs - currentEpochMs)
deadlineMonotonic =
  time.monotonic() + max(0, effectiveRemainingMs - 100) / 1000
```

100ms 是 Runtime 入口保护余量，不延长 Runtime 子截止或 Spring 外层硬截止。
`effectiveRemainingMs <= 100` 时不调用 invoker，返回语义
`timeout/core.deadline_exhausted`。Python 不解析 JWT claims、不修改 token；其对 subject 的
信任只成立于 10.2 冻结的本机威胁模型，真实跨主机或不受信本地进程场景必须另行设计
服务间认证或受保护 IPC。

### 9.5 内部响应

内部语义响应始终 HTTP 200，body 与 `AgentSemanticOutcome` 一一对应：

| 字段 | 类型 | 必填/空值 | 映射 |
|---|---|---|---|
| `contractVersion` | integer | 必填 | 1 |
| `requestId` | string | 必填 | 原请求 |
| `status` | enum | 必填 | 原样 |
| `capabilityId` | string | 可空 | 原样 |
| `answerText` | string | 可空 | 原样 |
| `userResult` | object | 可空 | 原样深冻结序列化 |
| `failure` | object | 可空 | 仅 code/source |

Spring 先校验 HTTP 状态、媒体类型、body 大小、版本、requestId、枚举和组合，再映射外部响应。响应最大 393216 bytes；越界、未知字段、requestId 不匹配或非法组合统一为 `internal_failure/core.runtime_invalid_response`，不得部分采纳。

### 9.6 传输错误与映射

| Runtime HTTP/传输场景 | Spring 语义状态/失败码 | 是否重试 | 外部 HTTP |
|---|---|---:|---:|
| 2xx 但不是 200、3xx、400/404/405/409/413/415/422 或其他未登记非 2xx | `internal_failure/core.runtime_protocol_error` | 否 | 500 |
| 401 | `unauthenticated/core.runtime_auth_context_invalid` | 否 | 401 |
| 429 | `downstream_failure/core.runtime_capacity_exceeded` | 否 | 502 |
| 503/连接拒绝 | `downstream_failure/downstream.runtime_unavailable` | 否 | 502 |
| 500/502/504 或其他 Runtime 5xx（503 除外） | `downstream_failure/downstream.runtime_failure` | 否 | 502 |
| Spring 硬截止/读取超时 | `timeout/downstream.runtime_timeout` | 否 | 504 |
| 无效 JSON/媒体类型/超界 body | `internal_failure/core.runtime_invalid_response` | 否 | 500 |
| Runtime 进程退出/连接重置 | `downstream_failure/downstream.runtime_connection_lost` | 否 | 502 |

Runtime 必须把语义结果放在 HTTP 200；FastAPI 的 `RequestValidationError`、缺 Header、未知
字段或类型错误统一由 `RuntimeProtocolExceptionHandlers` 转为 HTTP 400，固定小型正文只含
`contractVersion=1` 和 `code=runtime.protocol_error`，不得返回默认 422、Pydantic
`errors()`、输入值、URL 或异常 message。版本 Header/body 冲突仍为 409，正文采用同一安全
形态；未知 ingress 异常固定 500 `runtime.internal_error`。

Spring 使用 `exchangeToMono` 先按状态表选择映射；所有非 200 分支只调用
`ClientResponse.releaseBody()` 并等待释放完成，不反序列化、不记录、不基于错误正文构造
公开响应。200 分支才在 `max-response-bytes` 内聚合并严格解码。传输异常不触发第二次
invoke；调用方若重新提交，形成新的 requestId 和新请求。

## 10. 权限、安全、审计与输入边界

### 10.1 Spring 认证顺序

1. `AgentRequestMetadataWebFilter` 在 Spring Security 之前创建 9.2 的请求元数据和单调预算起点。
2. `AgentSecurityConfiguration` 显式复用 `common-security` 提供的
   `ReactiveJwtDecoder`，只放行 `/actuator/health/**`，只允许已认证身份访问
   `POST /api/v1/agent/queries`，其余路径失败关闭；自定义 `SecurityWebFilterChain` 后不得
   依赖 `@ConditionalOnMissingBean` 的默认链继续生效。
3. `AgentHttpCodecConfiguration` 在 WebFlux DTO 解码前把默认 codec
   `maxInMemorySize` 精确绑定为 `agent.ingress.max-body-bytes`；Content-Length 已超限或
   chunked 实际累计超限均返回 413，Controller/application service/Runtime 调用均为零。
4. Spring Security 验证 JWT 签名、有效期和结构；失败由统一 entry point 写 401 信封。
5. application service 读取 `Jwt`，校验 `sub` 非空、`SecurityTokenUtils.isUserToken(jwt)`
   及 raw token UTF-8 bytes≤16384。
6. 校验问题并执行并发准入。
7. 从请求元数据恢复最早单调起点，计算剩余总预算并构造一次内部请求。
8. 只有以上全部成功才显式读取 `jwt.getTokenValue()` 构造 Authorization header。

角色 claim 不参与 Agent 入口的业务授权；Employee/Transaction 最终授权仍在业务服务。合法服务 token 也不得作为本链路用户身份，返回 401。

### 10.2 Runtime 内部边界

- 默认 `host=127.0.0.1`、`port=8091`，Gateway/Eureka 不为 Runtime 建立路由或注册。
- 本设计把操作系统登录会话内的本机进程视为同一受信部署边界；“Spring 是唯一调用方”
  表示唯一受支持调用路径，不表示仅凭 TCP loopback 可以鉴别进程身份。
- Python 入口只验证 header/bearer 非空、协议字段严格有效，并将 token 包装为 `OpaqueUserToken`。
- Runtime 强制 Uvicorn `http="h11"` 且 `h11_max_incomplete_event_size=32768`；结合
  `OpaqueUserToken` 的 16384-byte 上限，为 Authorization、版本和关联 Header 留出有界余量。
- 不在 Python 重复实现 JWT 验签、role 解析或业务授权。
- 若未来 Spring/Python 分主机部署、共享开发主机存在不受信本地进程或 Runtime 需要面向
  容器网络监听，回环信任假设失效；必须新增受权的服务间认证/网络策略或受保护 IPC
  设计，不能仅把 host 改为 `0.0.0.0`。

### 10.3 日志脱敏

允许记录：requestId、correlationId、HTTP route、status、failure code/source、耗时、请求/响应字节数、取消来源、Runtime contract version。

禁止记录：Authorization、JWT 片段/哈希、subject 原文、question、完整 body、answer/result、异常 message、堆栈中的敏感请求、任意模型/业务载荷。开发级堆栈只允许保留异常类型和安全内部码。

## 11. 时限、取消、并发与状态

### 11.1 总预算

| 配置 | 默认值 | 允许范围 | 所有者 |
|---|---:|---:|---|
| `agent.ingress.total-timeout` | 60s | 5s～120s | Spring |
| `agent.ingress.response-reserve` | 500ms | 100～2000ms 且小于总时限 | Spring |
| `agent.runtime.connect-timeout` | 1s | 100ms～5s | Spring client |
| `agent.runtime.disconnect-poll-interval` | 100ms | 50～500ms | Python ingress |

Spring 以 9.2 最早 WebFilter 捕获的 `receivedMonotonicNanos` 为唯一总预算起点。应用服务
在认证、字段校验和准入后只计算剩余量，不重新启动完整超时：

```text
hardDeadlineMonotonicNanos = receivedMonotonicNanos + totalTimeoutNanos
hardRemainingMs = floor((hardDeadlineMonotonicNanos - nowMonotonicNanos) / 1_000_000)
runtimeRemainingMs = hardRemainingMs - responseReserveMs
runtimeDeadlineEpochMs = sendEpochMs + runtimeRemainingMs
```

内部请求使用 `deadlineEpochMs=runtimeDeadlineEpochMs`、
`remainingTimeoutMs=runtimeRemainingMs`。`hardRemainingMs <= responseReserveMs` 时 Spring
不建立内部连接，直接返回
`timeout/downstream.runtime_timeout`。内部请求中的 `deadlineEpochMs` 使用
`runtimeDeadlineEpochMs`；Spring 外层 `Mono.timeout` 只使用调用时剩余的
`hardRemainingMs`，
不在调用链中重新获得一个完整 `totalTimeout`。Runtime graph、模型和能力只能消费 Runtime
子截止以内的预算，`response-reserve` 专用于内部响应读取、严格校验、外部 DTO 映射和写回。
任何子层配置不得延长 Runtime 子截止或外层硬截止。

### 11.2 取消流程

1. 外部客户端断连、Spring timeout 或进程 shutdown 取消 application Mono。
2. WebClient subscription 取消并关闭内部响应等待。
3. ASGI `Request.is_disconnected()` 观察到上游断开，调用 `CancellationSignal.cancel(upstream_cancel)`。
4. invoker/core 在节点和出站前检查 signal；不再安排新模型或能力调用。
5. 取消后到达的结果不序列化、不写最终 outcome；请求内对象释放。

连接取消不能保证中断已经到达外部系统的只读请求，本期接受该限制。不得为“确认取消”新增持久任务、取消 API 或自动重放。
无论 invoker 正常、失败、超时还是 route task 被取消，`invoke_agent` 的 `finally` 都必须取消
并 `await` 当前请求的 disconnect watcher；只允许抑制该 watcher 自身因清理产生的
`CancelledError`，外层 task 的取消必须继续传播。正常成功请求结束后 watcher 数必须回到零。

### 11.3 并发与重复

| 边界 | 默认 | 行为 |
|---|---:|---|
| Spring in-flight | 8 | 超出返回 429 `core.ingress_capacity_exceeded`，Runtime 调用为零 |
| Uvicorn worker | 1 | 保持一个进程级冻结注册快照 |
| Runtime invoke in-flight | 8 | `RuntimeRequestLimiter` 在进入 invoker 前原子准入；超出返回 HTTP 429，invoker 调用为零，Spring 映射下游容量失败 |
| request replay | 0 次自动重试 | 超时、连接失败和 5xx 均不重放 |

requestId 仅用于关联，不是幂等键。重复 requestId 不授予重放安全；内部调用者只有 Spring，必须每次生成新 UUID。

本期不把 Uvicorn `limit_concurrency` 当作上述语义准入器：该参数按 Uvicorn 契约返回 503，
且会把健康请求和 invoke 连接共同计数，不能证明 429 及 invoker 零调用。若实施阶段另设
Uvicorn 传输安全上限，它必须高于应用级 invoke 上限，触发的 503 只按
`downstream.runtime_unavailable` 处理。

## 12. 健康、部署与观测

### 12.1 健康语义

| 进程/端点 | 语义 | 依赖 |
|---|---|---|
| Spring `/actuator/health/liveness` | JVM 与 WebFlux 活着 | 不探测 Runtime/模型/业务服务 |
| Spring `/actuator/health/readiness` | 本地配置有效且 Runtime ready 可达 | 500ms 内调用 Runtime ready |
| Runtime `/internal/health/live` | ASGI event loop 可响应 | 不要求 registry/外部依赖 |
| Runtime `/internal/health/ready` | lifespan 完成、配置有效、registry 冻结、graph 已编译 | 不把 DeepSeek/业务瞬时可用性当本地 ready |

健康端点不得返回能力描述、配置正文、模型名以外的秘密、异常正文或 JWT。Runtime ready 只允许回环访问。

### 12.2 启动顺序

1. 启动 `agent-runtime`，校验 Python、传输设置和 `L2_00_01` 组合根。
2. Runtime ready 后启动 `agent-service`，校验安全、契约和客户端配置。
3. Spring readiness 探测 Runtime；成功后才对外接收流量。
4. Gateway 路由到 `agent-service`（实际路由修改不在本文授权范围）。

停止时先使 Spring readiness DOWN 并拒绝新请求，再等待不超过 2 秒的本地在途结束，随后停止 Runtime；超时请求取消，不续跑。

### 12.3 最小指标

| 指标 | 标签 | 禁止标签 |
|---|---|---|
| `agent_ingress_requests_total` | method、route、status | user、question、token |
| `agent_ingress_duration_seconds` | outcome status | capability result body |
| `agent_runtime_client_duration_seconds` | transport outcome | URL query/body |
| `agent_runtime_inflight` | process instance | requestId |
| `agent_runtime_cancellations_total` | cancellation source | subject |
| `agent_runtime_protocol_errors_total` | stable error code | exception message |

本期使用 Micrometer/Actuator 与 Python 日志/简单计数；不要求引入 OpenTelemetry collector 或独立指标平台。

## 13. 配置与依赖

### 13.1 Spring 配置

| Key | 默认 | 校验/来源 | 敏感 | 变更效果 |
|---|---|---|---:|---|
| `spring.application.name` | `agent-service` | 代码默认/Config Server | 否 | 重启 |
| `server.port` | `8090` | 1～65535 | 否 | 重启 |
| `agent.ingress.max-question-chars` | 4096 | 256～4096；不得高于 Core | 否 | 重启 |
| `agent.ingress.max-body-bytes` | 32768 | 4096～65536 | 否 | 重启 |
| `agent.ingress.max-user-token-bytes` | 16384 | 当前必须等于 `OpaqueUserToken` 上限，不允许域配置放宽 | 否 | 重启 |
| `agent.ingress.max-in-flight` | 8 | 1～32 | 否 | 重启 |
| `agent.ingress.total-timeout` | 60s | 5～120s | 否 | 重启 |
| `agent.ingress.response-reserve` | 500ms | 100～2000ms 且小于 `total-timeout` | 否 | 重启 |
| `agent.runtime.base-url` | `http://127.0.0.1:8091` | http + loopback；禁止 userinfo/path/query | 否 | 重启 |
| `agent.runtime.contract-version` | 1 | 只能 1 | 否 | 启动失败 |
| `agent.runtime.connect-timeout` | 1s | 100ms～5s | 否 | 重启 |
| `agent.runtime.max-response-bytes` | 393216 | 32768～524288 | 否 | 重启 |
| `server.max-http-request-header-size` | `32KB` | 当前固定 32KB；不得低于 user token 上限加受控 Header 余量 | 否 | 重启 |
| `spring.jackson.deserialization.fail-on-unknown-properties` | `true` | 当前必须为 true | 否 | 启动校验，非法/缺失不就绪 |

### 13.2 Python 配置

| 环境键 | 默认 | 校验 | 敏感 | 说明 |
|---|---|---|---:|---|
| `AGENT_RUNTIME_HOST` | `127.0.0.1` | 当前只能回环地址 | 否 | 非回环启动失败 |
| `AGENT_RUNTIME_PORT` | `8091` | 1～65535 | 否 | 与 Spring URL 对齐 |
| `AGENT_RUNTIME_CONTRACT_VERSION` | `1` | 只能 1 | 否 | 启动失败 |
| `AGENT_RUNTIME_MAX_BODY_BYTES` | `32768` | 4096～65536 | 否 | ASGI receive 前置累计限制 |
| `AGENT_RUNTIME_MAX_IN_FLIGHT` | `8` | 1～32 | 否 | 应用级 invoke 准入；不映射为 Uvicorn `limit_concurrency` |
| `AGENT_RUNTIME_DISCONNECT_POLL_MS` | `100` | 50～500 | 否 | 取消观察 |
| `AGENT_RUNTIME_MAX_INCOMPLETE_EVENT_BYTES` | `32768` | 当前固定 32768；仅与强制 h11 协议共同生效 | 否 | 覆盖 16KiB JWT 及受控 Header 余量 |

配置加载后冻结，不支持热更新。Spring 配置可来自 Config Server；Python 仅通过启动环境/命令参数加载非敏感设置。两端显式非法值均阻止 readiness。

### 13.3 构建依赖

- `agent-service` 继承 `serviceCenter/pom.xml`，新增 `spring-boot-starter-webflux`、`spring-boot-starter-oauth2-resource-server`、`spring-boot-starter-actuator`、`common-security` 和测试依赖。
- `agent-runtime` 保持 Python `>=3.12,<3.13`、`langgraph==1.2.9`；传输边界建议锁定 `fastapi==0.139.2`、`uvicorn==0.51.0`、`pydantic==2.13.4`。
- Pydantic 仅用于 `agent_runtime.api` 传输 DTO；`capability_api`、`core` 和 graph state 不得依赖它。
- 升级任一 HTTP/序列化依赖必须重跑双端契约、取消、body 限制和未知字段测试。

## 14. 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置项 | 责任 | 必要性 | 设计规则 |
|---|---|---|---|---|---|---|---|
| `IMPL-ACCESS-001` | 已存在 | OpenAPI | `agent-contracts/openapi/agent-public-v1.yaml` | `/api/v1/agent/queries` | 外部契约权威 | 防字段漂移 | `DR-ACCESS-002/011/012` |
| `IMPL-ACCESS-002` | 已存在 | OpenAPI | `agent-contracts/openapi/agent-runtime-internal-v1.yaml` | invoke/health | 内部契约权威 | 跨语言一致 | `DR-ACCESS-002/010/012` |
| `IMPL-ACCESS-003` | 已存在 | Maven/配置 | `agent-service/pom.xml`、`agent-service/src/main/resources/application.yml` | 依赖和 `agent.*` | Spring 构建/配置 | 新进程必需 | `DR-ACCESS-009/013/016` |
| `IMPL-ACCESS-004` | 已存在 | Java security | `agent-service/src/main/java/com/dylan/agent/service/config/AgentSecurityConfiguration.java` | `SecurityWebFilterChain agentSecurityWebFilterChain(ServerHttpSecurity http, ReactiveJwtDecoder decoder, AgentPublicErrorWriter errorWriter)` | API 认证及健康白名单 | 用户入口保护 | `DR-ACCESS-001/004` |
| `IMPL-ACCESS-005` | 已存在 | Java boundary | `agent-service/src/main/java/com/dylan/agent/service/security/AgentUserContextFactory.java` | `AgentUserContext requireUser(Jwt jwt)` | subject/token_type 与 token 提取 | 禁服务身份回退 | `DR-ACCESS-004/006` |
| `IMPL-ACCESS-006` | 已存在 | Java application | `agent-service/src/main/java/com/dylan/agent/service/application/AgentQueryApplicationService.java` | `Mono<AgentQueryResponse> query(AgentQueryCommand command, Jwt jwt, AgentRequestMetadata metadata)` | 准入、预算、一次调用 | 接入治理核心 | `DR-ACCESS-003/004/007/008` |
| `IMPL-ACCESS-007` | 已存在 | Java web | `agent-service/src/main/java/com/dylan/agent/service/web/AgentQueryController.java` | `Mono<ResponseEntity<AgentQueryResponse>> query(AgentQueryRequest request, JwtAuthenticationToken authentication, ServerWebExchange exchange)` | HTTP 输入输出 | 外部入口 | `DR-ACCESS-001/011` |
| `IMPL-ACCESS-008` | 已存在 | Java control | `agent-service/src/main/java/com/dylan/agent/service/application/AgentRequestLimiter.java` | `Lease tryAcquire()`、`void close()` | 有界并发且 exactly-once 释放 | 入口容量 | `DR-ACCESS-009` |
| `IMPL-ACCESS-009` | 已存在 | Java client contract | `agent-service/src/main/java/com/dylan/agent/service/runtime/AgentRuntimeClient.java` | `Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken)` | 稳定调用边界 | 隔离 HTTP | `DR-ACCESS-003/006/007` |
| `IMPL-ACCESS-010` | 已存在 | Java HTTP adapter | `agent-service/src/main/java/com/dylan/agent/service/runtime/WebClientAgentRuntimeClient.java` | `invoke(...)`、`decodeResponse(...)`、`mapTransportFailure(Throwable)` | HTTP 调用、严格响应和失败转换 | 跨进程调用 | `DR-ACCESS-006/010/011/012` |
| `IMPL-ACCESS-011` | 已存在 | Python ingress | `agent-runtime/src/agent_runtime/api/ingress.py` | `async def invoke_agent(...) -> RuntimeInvokeResponse`、`to_execution_scope(...)` | scope/原始问题同源构造、取消、invoker 调用 | Python 入口 | `DR-ACCESS-005/006/007/008/010/017` |
| `IMPL-ACCESS-012` | 已存在 | Python app factory | `agent-runtime/src/agent_runtime/api/app.py` | `def create_app(settings: RuntimeHttpSettings, runtime_factory: RuntimeFactory) -> FastAPI` | lifespan、route、ready 状态 | 可测试组合 | `DR-ACCESS-005/013/016` |
| `IMPL-ACCESS-013` | 已存在 | 健康 | Java `AgentRuntimeHealthIndicator`；Python `agent_runtime/api/health.py` | `health()`、`live()`、`ready()` | 双进程健康语义 | 启停诊断 | `DR-ACCESS-013` |
| `IMPL-ACCESS-014` | 已存在 | 契约测试资产 | `agent-contracts/pyproject.toml`、`agent-contracts/fixtures/`、`agent-contracts/tests/test_openapi_examples.py` | 成功/失败/未知字段/版本样例及 OpenAPI 3.1 校验 | 双端共用样例 | 防实现漂移 | `DR-ACCESS-002/012` |
| `IMPL-ACCESS-015` | 已存在 | Python transport DTO | `agent-runtime/src/agent_runtime/api/models.py` | strict Pydantic request/response models | camelCase↔核心转换并提供单一已校验 question 值 | 传输隔离 | `DR-ACCESS-006/010/012/017` |
| `IMPL-ACCESS-016` | 已存在 | 启动入口 | `agent-runtime/src/agent_runtime/main.py` | `def main() -> None` | 单 worker、回环启动 | 双进程部署 | `DR-ACCESS-005/014/016` |
| `IMPL-ACCESS-017` | 已存在 | Java codec 配置 | `agent-service/src/main/java/com/dylan/agent/service/config/AgentHttpCodecConfiguration.java` | `configureHttpMessageCodecs(...)`、Runtime `WebClient` codec | DTO 解码前限制外部正文、聚合时限制内部响应 | 声明上限必须可执行 | `DR-ACCESS-009/012/016` |
| `IMPL-ACCESS-018` | 已存在 | Python ASGI 边界 | `agent-runtime/src/agent_runtime/api/limits.py` | `MaxBodyBytesMiddleware`、`RuntimeRequestLimiter` | receive 累计字节限制和 invoke 应用级准入 | 覆盖 chunked 与确定性 429 | `DR-ACCESS-009/010/016` |
| `IMPL-ACCESS-019` | 已存在 | Java 请求元数据/错误边界 | `agent-service/src/main/java/com/dylan/agent/service/web/AgentRequestMetadataWebFilter.java`、`AgentPublicErrorWriter.java`、`AgentWebExceptionHandler.java` | `filter(...)`、`write(...)`、`handle(...)` | 安全链前单次元数据与统一公开错误信封 | 前 Controller 失败也必须满足 OpenAPI | `DR-ACCESS-004/009/015/018` |
| `IMPL-ACCESS-020` | 已存在 | Python 协议错误边界 | `agent-runtime/src/agent_runtime/api/errors.py` | `RuntimeProtocolExceptionHandlers`、固定错误 DTO | 覆盖 FastAPI/Pydantic 默认 422 和异常详情 | Spring 需要有限且安全的传输状态全集 | `DR-ACCESS-010/012/015` |
| `IMPL-ACCESS-021` | 已存在 | Java 输入值对象 | `agent-service/src/main/java/com/dylan/agent/service/application/AgentQuestionValidator.java` | `normalize(String)` | 单点 trim、Unicode code point 长度与同源字符串输出 | 防 Java/Python 字符计数漂移 | `DR-ACCESS-009/017` |
| `IMPL-ACCESS-022` | 建议新增 | Python test composition | `agent-runtime/tests/system_e2e/runtime_server.py` | `build_system_e2e_runtime() -> AgentRuntimeInvoker`、`main() -> None` | 只在测试进程装配三个真实 Provider、本地 stub model、受管 client 与关闭证据 | 复用生产组合根而不改生产入口 | `DR-ACCESS-019` |
| `IMPL-ACCESS-023` | 建议新增 | Java system E2E | `agent-service/src/test/java/com/dylan/agent/service/e2e/AgentSystemE2ETest.java` | `verifiesThreeCapabilitiesThroughSpringAndRuntime()` | 从公开 API 执行允许/拒绝/失败矩阵；只检查有限状态和字段存在性 | 证明双进程公共入口链路 | `DR-ACCESS-019` |
| `IMPL-ACCESS-024` | 建议新增 | PowerShell launcher | `agent-runtime/scripts/run-system-e2e.ps1` | 版本化受控启动、JWT 内存签发、Maven E2E、PID/日志清理 | 只启动并停止本次拥有的本地服务；校验 9200/8908/8909 | 真实 Provider 环境与可恢复性 | `DR-ACCESS-019` |
| `IMPL-ACCESS-025` | 建议新增 | 有限证据 | `agent-runtime/tests/system_e2e/evidence/system-e2e-v1.schema.json`、运行结果 JSON | 严格字段集：case/status、调用计数、stub/external outbound、清理与泄漏布尔值 | 可审计且不持久化内容/身份 | `DR-ACCESS-015/019` |

### 14.1 Java 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| `AgentUserContextFactory.requireUser` | `AgentUserContext requireUser(Jwt jwt)` | jwt 非空、sub 非空、`token_type=user`，raw token UTF-8≤16384 bytes；不得校验业务角色 | 返回只读 `subjectId/rawToken`；失败抛无敏感正文的 `AgentUnauthenticatedException` | 无；application service |
| `AgentQueryApplicationService.query` | `Mono<AgentQueryResponse> query(AgentQueryCommand command, Jwt jwt, AgentRequestMetadata metadata)` | 身份→问题→准入→从 metadata 计算剩余预算顺序；不得重新生成 ID/预算起点 | 唯一外部响应；超时/协议错误按 9.3/9.6 映射 | 一次 runtime invoke；`doFinally` 释放 lease |
| `AgentRuntimeClient.invoke` | `Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken)` | request 已由 application service 构造；raw token 不可空 | 仅返回已通过契约校验的 response；传输错误为 typed exception | 不重试；application service |
| `AgentQueryController.query` | `Mono<ResponseEntity<AgentQueryResponse>> query(@Valid @RequestBody AgentQueryRequest request, JwtAuthenticationToken authentication, ServerWebExchange exchange)` | WebFlux 在参数绑定前执行正文上限，Bean Validation 只做字段校验 | 按 9.3 状态映射 HTTP | 不读取 Adapter/模型 |
| `AgentRequestLimiter.tryAcquire` | `Lease tryAcquire()` | 原子计数小于上限 | 返回 AutoCloseable lease；超限抛 `IngressCapacityExceeded` | 请求完成/取消只释放一次 |
| `AgentHttpCodecConfiguration.configureHttpMessageCodecs` | `void configureHttpMessageCodecs(ServerCodecConfigurer configurer)` | 读取已校验的 `agent.ingress.max-body-bytes` | 设置 server default codecs 的 `maxInMemorySize`；超限统一映射 413，不把异常正文外发 | 只影响 `agent-service` 入站 DTO 解码 |
| `WebClientAgentRuntimeClient.createWebClient` | `WebClient createWebClient(AgentRuntimeProperties properties)` | base URL 已校验为 loopback；`maxResponseBytes` 已在范围内；客户端禁止自动重定向 | 通过 `ExchangeStrategies` 将 default codecs `maxInMemorySize` 设置为 `agent.runtime.max-response-bytes`；`DataBufferLimitException` 映射 `core.runtime_invalid_response` | 构造一次不可变客户端；application service 消费 |
| `WebClientAgentRuntimeClient.decodeResponse` | `Mono<RuntimeInvokeResponse> decodeResponse(ClientResponse response, String expectedRequestId)` | 先按 9.6 检查 HTTP status；仅 200 检查媒体类型并解码；requestId 必须匹配 | 非 200 先 `releaseBody()` 再抛仅含稳定码的 typed exception；200 无效/超界转 `core.runtime_invalid_response` | 每个 response body 只消费或释放一次；不得读取错误正文 |
| `AgentRequestMetadataWebFilter.filter` | `Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain)` | 仅公开查询路径；严格校验或生成 correlation；捕获 requestId 与 `System.nanoTime()` | 把冻结 `AgentRequestMetadata` 写入 exchange attribute 后继续链；重复执行检测为内部失败 | 不读取正文/JWT；顺序必须早于 Spring Security |
| `AgentPublicErrorWriter.write` | `Mono<Void> write(ServerWebExchange exchange, HttpStatusCode httpStatus, CapabilityStatus status, String code, FailureSource source)` | 只接受 9.3 的固定组合和现有 request metadata | 写唯一 `AgentQueryResponse`；非法组合固定转 500 `core.public_error_mapping_invalid` | 仅一次写响应；不得记录异常正文 |
| `AgentSecurityConfiguration.agentSecurityWebFilterChain` | `SecurityWebFilterChain agentSecurityWebFilterChain(ServerHttpSecurity http, ReactiveJwtDecoder decoder, AgentPublicErrorWriter errorWriter)` | health permitAll；公开查询 authenticated；其余 denyAll；显式配置 OAuth2 JWT decoder | 认证失败使用 401 安全信封，拒绝使用 403 安全信封 | 覆盖 common-security 的默认 chain，但复用其 decoder/key provider |
| `AgentQuestionValidator.normalize` | `String normalize(String rawQuestion)` | raw 不可空；只执行一次 `String.strip()`；以 `codePointCount` 校验 1～4096 | 返回唯一规范化字符串；非法值抛只含 `core.invalid_request` 的 typed exception | 无 I/O；application service 将返回值同时用于 command 和内部 request，不得再次 trim |

建议 Java record：

```text
AgentQueryRequest(String question)
AgentQueryResponse(
  String requestId,
  String correlationId,
  CapabilityStatus status,
  @Nullable String capabilityId,
  @Nullable String answer,
  @Nullable Map<String, Object> result,
  @Nullable FailureResponse error)
RuntimeInvokeRequest(
  int contractVersion,
  String requestId,
  String correlationId,
  String question,
  RuntimeSubject subject,
  long deadlineEpochMs,
  int remainingTimeoutMs)
RuntimeInvokeResponse(
  int contractVersion,
  String requestId,
  CapabilityStatus status,
  @Nullable String capabilityId,
  @Nullable String answerText,
  @Nullable Map<String, Object> userResult,
  @Nullable FailureResponse failure)
```

所有 mapping 必须深度/数量/字节受限，Jackson 对未知字段启用失败；不得把原始 `Map` 交给日志或模型。

### 14.2 Python 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| `api.ingress.invoke_agent` | `async def invoke_agent(request: Request, payload: RuntimeInvokeRequest, authorization: Annotated[str, Header(alias="Authorization")], x_agent_contract_version: Annotated[str, Header(alias="X-Agent-Contract-Version")], runtime: AgentRuntimeInvoker = Depends(require_runtime), limiter: RuntimeRequestLimiter = Depends(require_runtime_limiter)) -> RuntimeInvokeResponse` | 两个 Header、body、版本一致性和预算严格校验；先取得应用级 lease，再把同一已校验 question 传入 scope 与 invoker；token 包装；不解析 role | 合法 outcome 响应；版本 Header 缺失/非法为 400、与 body 不同为 409；超限为 429 且 invoker 零调用；不同源由 invoker 固定返回 `invalid_argument` | 创建请求级 lease、scope 和 disconnect task；`finally` 先取消并 await watcher，再 exactly-once 释放 lease；外层取消继续传播 |
| `api.ingress.to_execution_scope` | `def to_execution_scope(payload: RuntimeInvokeRequest, raw_token: str, cancellation: CancellationSignal, clocks: RuntimeClocks) -> RequestExecutionScope` | 使用 9.4 较小预算、`payload.question` 原样写入 `original_question`；subject user | scope；非法身份/问题/过期预算为 typed ingress error | 无外部 I/O |
| `api.cancellation.watch_disconnect` | `async def watch_disconnect(request: Request, signal: CancellationSignal, poll_interval_s: float) -> None` | 周期有界；只观察首个断开 | 无返回；首个断开发布 `upstream_cancel` | 不取消进程全局任务 |
| `api.limits.MaxBodyBytesMiddleware.__call__` | `async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None` | 仅限制 `/internal/v1/agent-runs:invoke`；先拒绝超界 Content-Length，再包装 receive 并累计每个 `http.request.body` 实际字节 | 超过 `AGENT_RUNTIME_MAX_BODY_BYTES` 立即发送 413，Pydantic/route/invoker 调用均为零；不得缓存第二份完整正文 | 只代理当前 ASGI 请求；live/ready 不受影响 |
| `api.limits.RuntimeRequestLimiter.try_acquire` | `async def try_acquire(self) -> RuntimeRequestLease` | 在 Header/body 严格校验后、scope/invoker 前原子比较 in-flight 上限 | 返回 async context lease；超限抛 `RuntimeCapacityExceeded`，异常处理器固定返回 429 空安全正文 | 完成、异常、超时、断连均 exactly-once 释放 |
| `api.errors.RuntimeProtocolExceptionHandlers.install` | `def install(app: FastAPI) -> None` | app factory 创建时且 route 接收请求前安装一次；显式覆盖 `RequestValidationError`、受控协议异常和未知异常 | validation→400、版本冲突→409、capacity→429、未知→500；均使用固定 DTO，不含 `errors()/input/message/stack` | 只写 HTTP 传输错误；不得把 `AgentSemanticOutcome` 改成非 200 |
| `api.app.create_app` | `def create_app(settings: RuntimeHttpSettings, runtime_factory: RuntimeFactory) -> FastAPI` | settings 已冻结；lifespan 构建 runtime | FastAPI app；构建失败保持 not ready | 唯一知道 transport/runtime 绑定 |
| `main.main` | `def main() -> None` | 读取严格环境设置；host 必须回环、workers=1、`http="h11"`、`h11_max_incomplete_event_size=32768` | 启动 Uvicorn；非法配置退出非零 | 不动态扫描能力 |

Pydantic models 使用 `ConfigDict(extra="forbid", strict=True, populate_by_name=False)`，传输字段使用显式 alias；转换后不得把 Pydantic model 传入 core。

## 15. 测试与验证设计

### 15.1 测试定义

| 测试编号 | 设计规则 | 层级 | 建议路径/用例 | 测试意图与关键断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-ACCESS-001` | `DR-ACCESS-002/012` | Contract | 已存在：`agent-contracts/tests/test_openapi_examples.py` | 两份 schema 和全部 fixture 合法；未知字段/枚举/版本样例拒绝；内部 Header 缺失/非法/与 body 不同分别固定为 400/409 | 任一端可接受契约外字段或 Header 未参与判定 |
| `TEST-ACCESS-002` | `DR-ACCESS-004/006/015/018` | Java Unit/Web | 已存在：`agent-service/src/test/java/com/dylan/agent/service/security/AgentSecurityContractTest.java`、`AgentUserContextFactoryTest.java` | 缺 token、坏 token、service token、token 16384±1 均使用安全身份边界；request/correlation 与预安全 metadata 相同；runtime spy=0；自定义 chain 实际调用 `ReactiveJwtDecoder` | 非用户身份触发内部调用、返回框架默认正文或自定义 chain 绕过 JWT |
| `TEST-ACCESS-003` | `DR-ACCESS-003/009/014/017` | Java Unit | `AgentQueryApplicationServiceTest`、`AgentQuestionValidatorTest` | 成功/失败均一次 invoke；Spring 超限返回 `downstream_failure/core.ingress_capacity_exceeded` + HTTP 429；Runtime 429 映射外部 502；参数化 BMP/补充字符、首尾 Unicode 空白和 code point 边界±1，内部 request 与规范化值精确相同；客户端错误不重试 | invoke 次数不为 0/1、两个容量边界被混为同一 HTTP、使用 UTF-16 code unit 误拒绝或问题被二次规范化 |
| `TEST-ACCESS-004` | `DR-ACCESS-007/009` | Cross-language Integration | 已存在：Java `AgentQueryApplicationServiceTest`、Python `agent-runtime/tests/integration/test_deadline.py` | 参数化 5s/60s/120s，并以可控单调时钟计入前置耗时；Runtime 子截止=最早接收起点的外层硬截止−响应预留；Python 取绝对/相对较小值；边界耗尽零 invoker | 前置处理时间未计入、子预算占用响应预留、超过外层硬截止或合法 120s 配置生成非法内部 DTO |
| `TEST-ACCESS-005` | `DR-ACCESS-008` | Integration | `agent-runtime/tests/integration/test_disconnect_cancellation.py` | 断连发布一次取消，停止新增 node，晚到结果不响应；成功/失败/超时/外层取消后 watcher task 与 lease 均归零 | 取消后仍安排调用、成功请求遗留 watcher 或外层取消被吞 |
| `TEST-ACCESS-006` | `DR-ACCESS-010/011` | Contract | 已存在：Java `AgentQueryControllerTest`、`RuntimeContractTest` 与 Python API/核心状态测试 | 全状态/合法空值映射；失败不得变 success；safe payload 不出现 | 状态改义或字段泄露 |
| `TEST-ACCESS-007` | `DR-ACCESS-005/013/016` | Integration | 已存在：Python `test_health_and_startup.py`、Java `AgentAccessE2ETest` | graph 未编译时 Runtime not ready；Runtime down 时 Spring not ready；两端 liveness 独立 | 假就绪或健康泄密 |
| `TEST-ACCESS-008` | `DR-ACCESS-002/010/012/015` | Consumer/Provider | 已存在：Java `RuntimeContractTest`、Python `test_runtime_openapi.py` | 共享 fixture 双端同判定；FastAPI 安全传输错误；Spring 穷尽非 200 映射并释放正文；requestId/版本/未知字段/媒体类型/组合非法响应拒绝 | 默认 422/详情泄露、未映射状态、错误正文被读取、连接 buffer 未释放或手写 DTO 漂移 |
| `TEST-ACCESS-009` | `DR-ACCESS-006/015` | Architecture/Log | 已存在：Java `AgentUserContextFactoryTest`、`AgentAccessE2ETest` 与 Python API 测试 | body/state/log/repr 均无 JWT、subject、question、result | 捕获敏感文本 |
| `TEST-ACCESS-010` | `DR-ACCESS-001/005/014` | Architecture | 已存在：`agent-runtime/tests/architecture/test_runtime_not_public.py` | host 固定回环、无 Eureka/Gateway 注册、无 persistence/messaging dependency | Runtime 可由外部路由访问 |
| `TEST-ACCESS-011` | `DR-ACCESS-017` | Python Unit/Integration | 已存在：`agent-runtime/tests/unit/api/test_question_binding.py` | spy 捕获 invoker question 和 handler context；合法请求两值精确相同；不同源固定失败关闭；日志无问题正文 | 两处独立规范化、静默覆盖、信任模型参数或发生下游调用 |
| `TEST-ACCESS-012` | `DR-ACCESS-009/010/016/018` | Java/Python Boundary | 已存在：Java `AgentSecurityContractTest`、`RuntimeResponseLimitTest`；Python `test_limits.py` | Content-Length/chunked、WebClient 响应、未知字段、JWT 和并发准入边界；请求/响应越界失败关闭，未知字段 400，Runtime 超限固定 429 且 invoker=0，lease 最终归零 | 只校验 Content-Length、先聚合后限流、默认 Jackson 接受未知字段、返回 503/错误正文或发生 permit 泄漏 |
| `TEST-ACCESS-013` | `DR-ACCESS-019` | Cross-process System E2E | 建议新增：Python `tests/system_e2e/test_runtime_composition.py`、Java `AgentSystemE2ETest`、launcher/schema 契约测试 | Knowledge/Employee/Transaction 分别通过 Spring→Runtime→真实 Provider 覆盖允许与未知角色拒绝；Transaction 保持 exact Decimal/no-result；Employee 只断言允许字段存在而不落盘；Access runtime unavailable 与本地 invalid argument 共同覆盖失败关闭；所有外部模型调用为 0，日志/证据无问题、JWT、标识或领域内容；逆序停止且只停止 owned PID | 任一能力旁路 Spring/Runtime、业务授权在 Agent 判定、模型外部出站、敏感内容持久化、重试/补跑或误停外部进程 |

v0.4 已执行契约资产、Java/Python consumer/provider、HTTP 状态、DTO、limit、deadline、取消、健康和本地双进程行为；这些证据只证明本地 stub Access 切片，不证明真实模型、领域能力、Gateway 路由或生产生效。

### 15.2 关键场景

| 场景 | Java→Python 次数 | 预期 |
|---|---:|---|
| 缺失/无效/服务 JWT | 0 | 401 `unauthenticated` |
| 空问题、超长问题、未知字段 | 0 | 400 `invalid_argument` |
| Spring 准入超限 | 0 | 429，安全固定错误 |
| 正常 `no_result` | 1 | 外部 200，状态保持，无伪造结果 |
| Runtime 返回 `forbidden` | 1 | 外部 403，状态/失败码保持 |
| Runtime body/版本非法 | 1 | 500 `core.runtime_invalid_response` |
| Runtime 连接失败 | 1 | 502，不重试 |
| 总时限耗尽 | 1 或尚未连接时 0 | 504，取消传播，不重放 |
| 外部断连 | 至多 1 | 内部连接取消，停止新增工作 |

### 15.3 验证定义

| 验证编号 | 工作目录/前置 | 命令或人工步骤 | 验证范围与预期 | 当前执行状态 |
|---|---|---|---|---|
| `VAL-ACCESS-001` | `D:\codex` | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md --root D:\codex --strict` | 0 errors、0 warnings；仅证明文档确定性规则 | 已执行：v0.4 0 errors、0 warnings（2026-08-01） |
| `VAL-ACCESS-002` | `D:\codex` | `mvn -f agent-service/pom.xml test` | Java 安全、准入、映射、客户端和 E2E 测试通过 | 已执行：31 passed（2026-08-01） |
| `VAL-ACCESS-003` | `agent-contracts`、`agent-runtime`、`agent-service` | 三端 contract/unit suites 及 Access 相关严格类型检查 | 两份 OpenAPI、共享 fixture 与 Java/Python 消费者/生产者一致 | 已执行：契约 21 passed + mypy；Runtime 180 passed，Access mypy 20 files；Java 31 passed（2026-08-01） |
| `VAL-ACCESS-004` | `D:\codex\agent-runtime` | `python -m pytest tests/integration/test_deadline.py tests/integration/test_disconnect_cancellation.py -q`（亦包含在全量 180 项） | 时限、取消和晚到结果符合设计 | 已执行并由 Runtime 全量回归覆盖（2026-08-01） |
| `VAL-ACCESS-005` | `agent-service` 本地 E2E | `mvn -f agent-service/pom.xml -Dtest=AgentAccessE2ETest test` | Runtime→Spring 启动、四个健康端点、认证/映射、Spring→Runtime 逆序停止 | 已执行：1 passed，且纳入 Java 31 项全量回归（2026-08-01） |
| `VAL-ACCESS-006` | `D:\codex`；9200/8908/8909 可用，Employee 测试标识通过进程环境提供 | `pwsh -NoProfile -File agent-runtime/scripts/run-system-e2e.ps1`；随后执行相关 Python/Java 回归、strict mypy 与 compileall | 三能力真实 Provider 双进程矩阵、有限 evidence Schema、external model outbound=0、日志零泄漏、owned PID 逆序停止；不得读取 `LLM_API_KEY` | 已执行：7 个 allow/deny/invalid/no-result 场景通过；`externalModelOutbound=0`、`logLeakCount=0`，evidence SHA-256 `064205754924b62fda2912f31361af51f004a46d596207df3a57f6f9605dec71`；Python 定向 10 passed、全量非 live 1193 passed/27 skipped/4 deselected，Java 32 tests/0 failures/1 skipped，strict mypy 403 files 与 compileall 通过（2026-08-20） |

## 16. 发布、迁移与回滚

- 全部目标模块和契约为新增，无数据库、索引或消息迁移。
- 初次实现先使用 `L2_00_01` 本地模型/能力 stub 验证双进程，不接入真实 DeepSeek 或业务数据。
- 发布粒度必须包含内部 OpenAPI、Java DTO/客户端和 Python DTO/入口的同一 v1 版本；不支持只部署单侧破坏性变化。
- 回滚时先停止 `agent-service`，恢复两端前一兼容构建和配置，再先 Runtime 后 Spring 启动。
- Runtime 异常可停止整个逻辑 Agent；不得让 Spring 绕过 Runtime 直接调用能力。
- in-flight 请求在重启中失败并由调用方决定是否新建请求，不自动续跑。
- 系统 E2E 回滚只删除/禁用测试范围组合根与启动器并恢复既有 `AgentAccessE2ETest`；停止顺序为 Spring 测试上下文→Runtime→本次 launcher 拥有的领域服务→auth-service，不修改索引、数据库或生产配置。

## 17. 风险、待确认事项与授权需求

### 17.1 风险与待确认事项

| 编号 | 类型 | 证据缺口或风险 | 触发场景 | 影响 | 建议 | 是否阻塞/需授权 |
|---|---|---|---|---|---|---|
| `RISK-ACCESS-001` | 契约漂移 | OpenAPI 与两端手写 DTO 不一致 | 单侧修改字段 | 解析失败或含义漂移 | 共享 fixture 和 provider/consumer test | 不阻塞已完成本地切片；单侧契约变更前阻塞 |
| `RISK-ACCESS-002` | 网络边界 | 回环假设被部署改为跨主机 | 修改 host 为非 loopback | Runtime 形成未认证入口 | 另行设计服务间认证和网络策略 | 跨主机前需上位/安全授权 |
| `RISK-ACCESS-003` | 取消限制 | 已发出只读 HTTP 不能强制中断 | 客户端断连 | 短时资源继续占用 | 硬时限、并发上限、迟到丢弃 | 不阻塞本地切片 |
| `RISK-ACCESS-004` | 身份泄露 | 调试日志记录 header/body | HTTP 异常 | JWT/问题泄露 | 日志捕获负向测试 | 不阻塞已完成本地切片；日志策略变更前阻塞 |
| `RISK-ACCESS-005` | 版本依赖 | FastAPI/Uvicorn 升级改变断连或 strict parsing | 依赖升级 | 取消/解析行为漂移 | 锁版本并全量回归 | 升级需变更评审 |
| `RISK-ACCESS-006` | 预算 | 60 秒对真实模型/知识链路是否合适尚无实测 | P4 完整链路 | 误超时或等待过长 | P3/P4 采集阶段耗时后在允许范围内调整 | 不阻塞设计；阻塞完成性能结论 |
| `RISK-ACCESS-007` | 外部路由 | Gateway 当前路由与错误格式尚未为 Agent 固化 | P4 通过 Gateway | 外部响应可能被重写 | 后续在实现授权内增加 Gateway contract test | 不阻塞本文；阻塞 Gateway 端到端 |
| `RISK-ACCESS-008` | 上下文同源 | ingress 分别构造图问题与 handler 原始问题 | 未来重构 DTO/scope 转换 | Knowledge 改写与图问题漂移 | 单一局部值、Runtime 精确相等闸门和 `TEST-ACCESS-011` | 不阻塞已完成本地切片；相关重构前阻塞 |
| `RISK-ACCESS-009` | 本机信任边界 | loopback 不能鉴别同机进程身份 | 共享主机出现不受信本地进程、容器共享网络或监听地址放宽 | 可旁路 Spring 的 JWT 验签和准入 | 本期冻结单用户可信本机假设；假设失效前必须新增服务间认证/受保护 IPC 并重审 | 不阻塞当前本地学习切片；假设失效时阻塞部署 |
| `RISK-ACCESS-010` | 服务器 framing | 超界 Header 在应用 WebFilter 前被拒绝，无法生成 Agent error envelope | token/组合 Header 超过冻结 32KB transport 边界 | 调用方只得到服务器 400/431 | OpenAPI 明确应用契约输入上限；Gateway 联调验证相同或更宽 Header 上限 | 不阻塞合法输入；阻塞 Gateway 端到端契约关闭 |
| `RISK-ACCESS-011` | 系统 E2E 环境 | 将历史业务出域 candidate/wrapper、维护者进程或真实模型混入系统 E2E | 为复用启动逻辑而执行旧一次性资产，或端口被外部进程占用 | 破坏历史不可变性、误停服务或形成未授权出域 | 独立 launcher、端口/PID 所有权校验、provider=stub 与 external outbound=0 硬断言；占用即失败关闭 | 不阻塞 test-only 实现；阻塞实际 live E2E 直到环境满足 |

### 17.2 阶段门禁与外部证据

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威来源 | 责任方 | 最晚阶段 | 状态 | 未关闭时允许/禁止动作 |
|---|---|---|---|---|---|---|---|---|---|
| `CR-GATE-001` | design_decomposition | L1→本文 | 编写本文 | L1_00 v0.2 评审通过 | L1_00 14.1 | 项目维护者 | P2-L2 前 | Closed | 允许本文，不授权代码 |
| `CR-GATE-002` | slice_implementation | `agent-service`、Runtime HTTP ingress 与本地双进程 stub 测试 | 创建服务代码/配置/测试并宣称 Access 本地运行切片完成 | 本文与 `L2_00_01` 已评审可实施；用户明确授权三个工作包；`VAL-ACCESS-002～005` 与代码对照设计评审通过 | 两份 L2、`P3_00 GATE-004/005`、本地双进程验证 | 项目维护者 | P3 Access 工作包 | Closed | 允许维护已完成本地切片；真实模型、领域和部署仍由其他门禁控制 |
| `CR-GATE-003` | integration | 用户问题进入 DeepSeek | 敏感问题外发 | `L2_00_02` 输入分类/最小化、Knowledge/Business fixture 与 denied/unknown 零 transport 证据 | 模型 L2、2026-08-12 非 live 安全回归 | 项目维护者/模型方 | 首次敏感联调 | Closed（2026-08-12；仅问题输入安全前置） | 本文仍只传问题到受控 Runtime；具体敏感/unknown 问题继续失败关闭，真实领域数据仍受 `SA-GATE-006` |
| `SA-GATE-002` | slice_implementation | 真实模型 Runtime 实现切片 | DeepSeek 受控装配 | Provider契约/PoC、默认stub、fake组合根/生命周期/失败回归 | `L2_00_02` v0.16、P3 `GATE-020` | 项目维护者/DeepSeek | 模型切片完成前 | Closed（2026-08-12；未启用目标环境） | 可维护默认stub和显式provider装配；真实数据出域仍禁止 |
| `SA-GATE-006` | integration | 真实领域数据模型输入 | 真实证据/业务结果外发 | 领域出域 L2 与零调用测试 | 关联 L2 | 项目维护者/领域方 | P4 | Open | 只用合成安全载荷 |

### 17.3 需要后续授权的动作

- 修改两份 OpenAPI 的传输语义，或扩大已完成 `agent-service`、`agent-runtime/api` 的职责和公开边界。
- 将 `agent-service` 加入父 POM、Eureka 或 Gateway，或宣称可选 Config Server 引用已经过集成验证。
- Runtime 改为非回环部署或新增服务间认证。
- 关闭任何真实领域或数据出域集成门禁，或据 `SA-GATE-002` 声称目标环境/生产已启用 DeepSeek。
- `WP-SYSTEM-E2E-01` 以外的 live candidate/wrapper 重跑、业务结果外部模型出域或任何付费模型调用。

## 18. 内部自检记录

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-25 | 0 | 1 | 2 | 3 | 无 | 修复校验器未识别的流程/安全章节、组合追踪 ID 和建议新增路径标记 |
| 2 | 2026-07-25 | 0 | 0 | 0 | 0 | 无 | 完整 rubric 复核无目标内材料缺口，进入严格校验 |

作者自检只用于改进 Draft，不构成独立评审、Approved、实施授权或门禁关闭证据。

## 19. 独立正式评审记录

### 19.1 第 1 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-ACCESS-001` | S1 | `response-reserve` 未进入任何截止计算，且总时限允许 120 秒而内部字段上限仅 60 秒；合法配置会失配，Runtime 可耗尽外层写回预算 | 区分外层硬截止和扣除响应预留后的 Runtime 子截止，字段上限统一为 120000ms，并增加 5/60/120 秒测试 | Closed（第 2 轮） |
| `REV-ACCESS-002` | S1 | 三处字节上限只有数值，没有 DTO 解码前 ASGI/WebFlux receive 限制及 WebClient 聚合限制的实现落点；chunked 请求可绕过仅看 Content-Length 的方案 | 增加 WebFlux codec、ASGI receive middleware 和 WebClient codec 的路径、签名、错误映射及边界测试 | Closed（第 2 轮） |
| `REV-ACCESS-003` | S1 | 文档要求 Runtime 超限返回 429，却把限制描述为 Uvicorn limit；后者契约返回 503 且同时计入健康连接 | 改为应用级 `RuntimeRequestLimiter`，Uvicorn 只可作为更高的传输安全上限，固定两类错误映射 | Closed（第 2 轮） |
| `REV-ACCESS-004` | S1 | 内部契约要求 `X-Agent-Contract-Version`，但 Python route 签名没有消费该 Header，无法实现 Header/body 一致性检查 | 在 FastAPI 边界签名和契约测试中显式加入 Header 与 400/409 语义 | Closed（第 2 轮） |
| `REV-ACCESS-005` | S1 | 场景要求 Spring 准入超限返回 429，但外部状态表把全部 `downstream_failure` 固定为 502 | 将 `core.ingress_capacity_exceeded` 定义为唯一 429 例外，并证明 Runtime 429 仍映射 502 | Closed（第 2 轮） |
| `REV-ACCESS-006` | S2 | Java Controller 边界签名缺少 `@RequestBody/@Valid`，与文中“WebFlux/Bean Validation”不闭合 | 补齐精确注解和前置字节限制责任 | Closed（第 2 轮） |
| `REV-ACCESS-007` | S2 | 仅凭 loopback 不能证明“只有 Spring 进程可调用” | 将其收敛为可信单用户本机的唯一受支持路径，并把假设失效条件列为部署阻塞风险 | Closed（第 2 轮） |

### 19.2 第 2 轮冻结发现与修复

第 2 轮从 v0.2 首轮修订后的全文重新评审，确认 `REV-ACCESS-001`～`007` 已关闭，并冻结：

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-ACCESS-008` | S1 | Spring Security、codec 和参数绑定均可在 Controller 前失败，但文档没有统一 error writer 或预安全 request/correlation 所有者，OpenAPI 必填字段与 401/413 实现无法同时成立 | 增加最早 metadata WebFilter、显式 JWT security chain、统一 error writer/exception handler 和前 Controller 失败矩阵 | Closed（第 3 轮） |
| `REV-ACCESS-009` | S1 | 首轮公式同时使用“准入后”与“接收时”作为总预算起点，新引入的 413 也未进入公开状态矩阵 | 以最早 WebFilter 单调时间为唯一预算起点，并为 413/415 定义固定 `invalid_argument` 组合 | Closed（第 3 轮） |
| `REV-ACCESS-010` | S1 | Core 允许 16384-byte JWT，但两端 HTTP Header 容量与 Uvicorn 协议未冻结，合法执行上下文可能在跨进程前被默认上限拒绝 | 冻结 16KiB token、32KiB server/h11 event 上限及强制 h11，并增加边界测试 | Closed（第 3 轮） |
| `REV-ACCESS-011` | S1 | disconnect watcher 只描述创建，没有任何正常完成清理路径，每次成功请求都可能遗留后台 task | 固定 route `finally` 取消并 await watcher、保留外层取消并验证任务/lease 归零 | Closed（第 3 轮） |
| `REV-ACCESS-012` | S2 | Java 端未知字段失败关闭未绑定到具体 Jackson 配置，默认行为可能接受未知字段 | 将 `fail-on-unknown-properties=true` 纳入冻结配置、启动校验和边界测试 | Closed（第 3 轮） |

### 19.3 第 3 轮冻结发现与修复

第 3 轮从第二轮修订后的全文重新评审，确认 `REV-ACCESS-008`～`012` 已关闭，并冻结：

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-ACCESS-013` | S1 | FastAPI/Pydantic 的绑定错误默认返回 422 和结构化 validation detail，而内部协议只登记 400/409/413，可能泄露输入并令 Spring 落入未定义映射 | 增加 Python 协议异常处理器，固定 400/409/429/500 小型安全正文并禁止默认 422/detail | Closed（第 4 轮） |
| `REV-ACCESS-014` | S1 | Spring 未定义 Runtime 2xx≠200、3xx、404/405/415/422 和一般 5xx 映射，新增/框架错误可能绕过确定性失败语义 | 穷尽状态分类并固定 catch-all 失败关闭，语义结果仍只接受 200 | Closed（第 4 轮） |
| `REV-ACCESS-015` | S2 | “不读取 Runtime 错误正文”没有 WebClient 消费/释放方法，可能泄漏连接 buffer 或被默认异常处理聚合 | 固定 `exchangeToMono`、非 200 `releaseBody()` 和 exactly-once body 消费 | Closed（第 4 轮） |
| `REV-ACCESS-016` | S2 | 32KB Header framing reject 发生在应用过滤器前，不能满足“任意响应都有 Agent 信封”的表述 | 将统一信封收敛到进入应用链的请求，并明确 server 400/431、零调用及 Gateway 风险 | Closed（第 4 轮） |

### 19.4 第 4 轮冻结发现与修复

第 4 轮从第三轮修订后的全文重新评审，确认 `REV-ACCESS-013`～`016` 已关闭，并冻结：

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-ACCESS-017` | S1 | OpenAPI/Python 的 4096 长度按 Unicode code point，而 Java `String.length()`/`@Size` 按 UTF-16 code unit；包含补充字符的问题会在两端产生不同接受集合 | 固定 Java 单点 `strip + codePointCount` validator、Python 不再 trim，并增加 BMP/补充字符边界测试 | Closed（第 5 轮） |

### 19.5 第 5 轮终审结论

第 5 轮从第 4 轮修订后的全文重新执行依赖、契约、权限、时限、取消、并发、容量、
错误、实现落点、测试与门禁复核，无新增 S0/S1/S2。累计关闭 S1 12 项、S2 5 项；
当前未关闭 S0/S1/S2 均为 0，达到用户限定的 5 轮上限，本文评审结论为 Approved。

该段是 v0.2 实施前结论。v0.3 完成 OpenAPI/fixture 契约资产子切片；v0.4 已在明确授权下
完成 Runtime HTTP、Spring 接入和本地双进程 stub 工作包，`CR-GATE-002` 关闭。该结论不允许
真实模型或业务数据联调，也不表示 Gateway/生产部署生效。

单轮修复本身不等于评审通过；19.5 已从修订后全文完成终审并进入 Approved。外部框架事实
仅用于验证设计可实现性，不替代本仓库契约。

### 19.6 v0.4 代码对照设计评审

按 `WP-ACCESS-RUNTIME-01`、`WP-ACCESS-SPRING-01`、`WP-ACCESS-E2E-01` 依次对照本文执行
实现、测试和复评。实施中修复：chunked 超界被框架默认错误正文吞并、Runtime 健康落点未
独立、Spring raw token 长度校验晚于准入、readiness 未显式纳入 Runtime、预算/全状态/请求与
响应字节边界测试不足，以及 E2E 启动参数优先级未覆盖 `agent-service/src/main/resources/application.yml`。修复后从目标代码、
配置和测试重新核对契约、认证、单次调用、预算、取消、并发、失败映射、日志和双进程启停，
Access 范围内未遗留 Blocker/Major；全仓 model 测试的 15 个既有 mypy 错误不属于本 L2
实现切片，也不据此削弱 Access 严格类型检查。

### 19.7 v0.8 `WP-SYSTEM-E2E-01` 聚焦独立评审

| 检查问题 | 证据与判断 | 结论 |
|---|---|---|
| 测试组合根是否侵入生产边界 | `IMPL-ACCESS-022～025` 仅新增 `tests/system_e2e`、Java 测试、版本化 launcher 与有限 evidence；`agent_runtime.main`、OpenAPI、Spring 接入和领域 Provider 契约保持不变 | 符合 |
| 拒绝、失败与零出域是否可验证 | `TEST-ACCESS-013` 要求三个 Provider 各自返回未知角色拒绝，联合既有 Runtime unavailable 与本地参数失败验证失败关闭，并硬断言 external model outbound=0、有限 evidence 和日志零泄漏 | 符合 |
| P3 依赖是否无环且不依赖 Deferred 实验 | `WP-SYSTEM-E2E-01` 只依赖已 Done 的 Access E2E、Knowledge Retrieval、Employee Real 与 Transaction Real；Employee/Transaction 出域包及 wrapper 修复均为 Deferred，两个 scoped `SA-GATE-006` 只禁止真实业务结果外部模型出域 | 符合 |

本次结论只确认 v0.8 新增切片可作为 `WP-SYSTEM-E2E-01` 的实施依据，不重新评审历史全文，
不关闭 `SA-GATE-006.EMPLOYEE/TRANSACTION`，也不证明 Gateway/Eureka/Config Server、外部模型、
P5 效果、目标环境启用或生产部署。

### 19.8 v0.9 `WP-SYSTEM-E2E-01` 代码对照设计复核

| 检查项 | 实现与验证证据 | 结论 |
|---|---|---|
| 组合与契约边界 | Python/Java/PowerShell/Schema 均位于测试范围；Spring 公共 API、Runtime 入站、领域 Provider 与生产组合根未改。唯一生产修复由 `L2_01_01/02` 单独治理 | 符合 |
| Provider、权限与模型边界 | Knowledge/Employee/Transaction 使用真实只读 Provider，未知角色由领域服务最终拒绝；模型固定本地 stub，未读取 `LLM_API_KEY`，external outbound=0 | 符合 |
| 失败关闭与资源回收 | 无效本地参数在网络前拒绝；受管资源关闭逐项尝试并在关闭失败时写有限证据；launcher 只停止 owned PID，扫描并删除原始日志和临时 Surefire 报告 | 符合 |
| 验证充分性 | 7 个系统场景通过；定向、Knowledge/全量非 live、Java、strict mypy、compileall、PowerShell AST 与严格 evidence 校验通过 | 符合 |

复核未发现未关闭 Blocker/High/Medium。该结论仅关闭当前测试范围系统 E2E 工作包，
不替代 scoped `SA-GATE-006`、目标环境启用或生产发布验收。

## 20. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] Java 类路径、关键方法、输入、输出、错误和消费者已明确。
- [x] Python 模块、关键函数、异步、取消和状态影响已明确。
- [x] 外部与内部契约字段、枚举、空值、版本、超时和兼容性已明确。
- [x] 责任、非责任、依赖方向和禁止旁路已明确。
- [x] JWT、日志、Runtime 网络暴露和失败关闭已明确。
- [x] 当前允许/禁止实施范围和开放门禁已明确。
- [x] 本轮原始问题同源补正后已重新执行 `validate_detailed_design.py --strict`，结果为 0 errors、0 warnings；仅作为确定性文档证据。
- [x] 5 轮独立评审—修复—复评已关闭全部 S0/S1/S2。
- [x] 项目维护者已明确授权并完成 OpenAPI/fixture 契约资产子切片。
- [x] 项目维护者已明确授权并完成 Runtime HTTP、Spring 接入和双进程测试切片；`CR-GATE-002` 已关闭。
- [x] Core v0.6/Model v0.8 混合动作解析只改变 Runtime 内部 action resolution，Access wire 与实现无需修改。
- [x] `WP-MODEL-RUNTIME-01` 只增加 Runtime 可选 `aclose()` 生命周期接缝；HTTP/OpenAPI/Spring 契约未变，关闭一次测试与全量非live回归已通过。
- [x] `WP-SYSTEM-E2E-01` 的测试装配、三能力矩阵、有限证据、PID/日志清理和零外部模型出域已形成可实施追踪；不改变生产入口或领域契约。
- [x] `VAL-ACCESS-006` 已以混合知识域、Employee 与 Transaction 真实 Provider 完成 7 个系统场景；外部模型调用和日志泄漏均为 0，代码对照设计复核无未关闭 Blocker/High/Medium。

## 21. 当前结论

本文 v0.9 保持历史 5 轮独立设计评审通过与 Approved 状态；`WP-SYSTEM-E2E-01`
测试装配切片已于 2026-08-20 完成聚焦设计评审、实施验证和代码对照设计复核，结论为“符合”。`WP-ACCESS-CONTRACT-01`、
`WP-ACCESS-RUNTIME-01`、`WP-ACCESS-SPRING-01`、`WP-ACCESS-E2E-01` 均已按授权完成；
契约 21 项、Runtime 180 项、Java 31 项测试及 Access 相关严格类型检查通过，三个运行工作包
完成代码对照设计评审，`CR-GATE-002` 已关闭。`WP-SYSTEM-E2E-01` 已以测试范围
组合根、启动器和有限证据完成真实 Knowledge/Employee/Transaction Provider + 默认 stub 模型的
Spring→Runtime 闭环；`VAL-ACCESS-006` 的 7 个场景、零外部模型调用、零日志泄漏和 owned PID 清理均通过。该结果不证明 Gateway/Eureka/Config Server、外部模型、P5 效果、生产部署或运行生效。Core v0.6 的本地 Resolver+ID-only 模型选择与
L2_00_02 v0.16 的受控模型装配均位于 `AgentRuntimeInvoker` 内部；Access 侧只增加可选受管资源
`aclose()` 调用，不改变任何 OpenAPI、DTO、身份或时限契约。`SA-GATE-002` 仅按 Runtime 实现切片关闭，
`CR-GATE-003` 已按问题输入非 live 安全前置关闭，但不替代 `SA-GATE-006`、领域数据出域门禁或目标环境启用授权。
