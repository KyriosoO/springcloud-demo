# [L2_00_00] 单体 Agent Spring 接入与运行协同详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Spring 接入与运行协同详细设计 |
| 文档编号 | `L2_00_00` |
| 文档路径 | `docs/design/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Draft |
| 当前版本 | v0.1 |
| 日期 | 2026-07-25 |
| 适用范围 | `agent-service` 外部接入、Spring→Python 内部协议、总时限与取消、双进程健康及观测 |
| 上位文档 | `REQ_00`、`L0_00`、`L1_00` |
| 直接依赖 | `L2_00_01` v0.4（In Review）的 `AgentRuntimeInvoker`、含 `original_question` 的执行上下文与 `AgentSemanticOutcome` |
| 关联文档 | `L2_00_02`、`L1_01`、`L1_02` |
| 实现基线 | Spring Boot 3.5.10、Spring Cloud 2025.0.1、`common-security` 当前资源服务器能力；目标 `agent-service`、`agent-runtime` 均不存在 |
| 是否可作为实现依据 | 否 |
| 实施依据说明 | 本文尚未独立评审，`CR-GATE-002` 仍为 Open |
| 当前允许实施范围 | 本文编写、评审、契约样例推演和不访问真实下游的隔离 PoC |
| 当前禁止动作 | 创建或修改目标代码、配置、OpenAPI、测试；真实 Agent 请求联调；关闭实施或集成门禁 |
| 修改权限 | 本轮授权本文及直接相关文档原子同步，并授权 Git 提交、推送；代码、配置、Schema 和测试未获修改授权 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 第二批 L2 详细设计 | 创建 Spring 接入、跨进程协议、时限取消、健康与观测的实现级设计 |
| 2 | 2026-07-25 | 4.2、9、10、15、18～19 | 作者第 1 轮自检修复 | 展开全部追踪 ID，明确详细流程与权限/审计章节，规范建议新增测试路径和实施依据字段 |
| 3 | 2026-07-25 | 1～4、8～9、14～15、17～20 | 原子同步 `L2_00_01` v0.4 原始问题上下文补正 | 固定同一已校验 `question` 同时用于图输入和 `CapabilityExecutionContext.original_question`，补充不同源零调用失败与测试追踪；外部/内部 HTTP 字段不变 |
| 4 | 2026-07-25 | 14、19～20 | 本批次收口校验 | 重新执行严格文档校验并记录 0 errors、0 warnings；状态仍为 Draft，不替代独立评审 |

## 3. 背景、目标与范围

### 3.1 背景与问题

当前工作区已有 Gateway、Config Server、Eureka、`auth-service` 与 `common-security`，但没有目标 `agent-service` 和 Python `agent-runtime`。`L1_00` 已确定两进程组成一个逻辑 Agent，并由 Spring 拥有外部认证、请求治理和总时限，Python/LangGraph 拥有唯一 Agent 编排。若不在本 L2 固化传输、契约源、身份传递、取消及失败映射，Java/Python 将分别解释同一请求，形成跨语言漂移、超时放大或重复执行。

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

### 3.3 范围内

- `POST /api/v1/agent/queries` 外部同步 JSON 契约。
- Spring WebFlux JWT 入口、用户主体提取、问题校验、并发准入与响应封装。
- `POST /internal/v1/agent-runs:invoke` 内部同步 JSON 契约。
- Java→Python 原始用户 JWT、主体、关联标识、契约版本和剩余时限传递。
- Python HTTP 入口构造 `RequestExecutionScope` 并调用 `AgentRuntimeInvoker.ainvoke`。
- 连接取消、总时限、迟到结果丢弃、协议错误映射。
- 双进程 liveness/readiness、最小日志和指标。
- 配置键、启动校验、部署顺序、回滚及测试落点。

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

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 交互契约 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|---|
| `REQ_00`、`L0_00`、`L1_00` | parent | 落实接入与协同 | 规定需求和架构边界 | 约束映射 | 上位文档 | 只读 |
| `L2_00_01` | peer/direct dependency | 传输适配 | 定义核心类型、运行入口与语义输出 | Python 进程内调用 | LangGraph/核心状态 | 只读 |
| `L2_00_02` | peer | 传播剩余预算和结果 | 定义模型调用及答案校验 | `AgentSemanticOutcome` | 模型请求状态 | 只读 |
| `common-security` | implementation baseline / external contract | 复用资源服务器与 JWT decoder | 验签、JWT 基础类型 | Spring Security | JWT 密钥和验证 | 只读 |
| `auth-service` | external contract | 消费用户 JWT | 签发 subject、`token_type=user`、role | Bearer JWT | 用户与角色 | 只读 |
| `agent-service` | target implementation | 外部接入、硬时限、调用与协议映射 | 不做编排或领域处理 | 外部/内部 HTTP | Spring 请求状态 | 建议新增，当前未授权实施 |
| `agent-runtime` HTTP 入口 | target implementation | 内部传输、scope 构造、取消观察 | 不做业务选择 | 内部 HTTP + 进程内 invoker | Python 传输状态 | 建议新增，当前未授权实施 |
| OpenAPI 3.1 文件 | target contract | 两个 HTTP 契约的唯一字段权威 | 双端按契约实现 | YAML | 契约版本 | 建议新增，当前未授权实施 |

外部框架事实依据 [FastAPI 官方说明](https://fastapi.tiangolo.com/) 与 PyPI 当前稳定版本页面：[FastAPI](https://pypi.org/project/fastapi/)、[Uvicorn](https://pypi.org/project/uvicorn/)、[Pydantic](https://pypi.org/project/pydantic/)。这些事实只用于选择新传输边界，不证明目标代码已存在。

## 6. 当前实现基线与最小变更方案

### 6.1 已核实当前实现

1. `serviceCenter/pom.xml` 当前管理 Spring Boot `3.5.10`、Spring Cloud `2025.0.1` 和 Java 25。
2. `common-security` 已提供 Servlet/Reactive Resource Server 自动配置、JWT decoder 与 `SecurityTokenUtils.isUserToken`。
3. `auth-service` 当前签发 `sub`、`iat`、`exp`、`token_type=user` 和 `role`；`dylan` 当前分配 `ADMIN`。
4. Gateway、Eureka、Config Server 与 Actuator 基础设施已存在。
5. 当前没有 `agent-service` Maven 模块、`agent-runtime` Python 工程或 Agent HTTP 契约。
6. `L2_00_01` 中全部 Python 核心路径为建议新增，尚无可调用实现。

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
| `AgentQueryController` | 建议新增 | HTTP 字段绑定和响应状态输出 | JWT 解析、编排、重试 | 外部 API 变化 | DTO ↔ HTTP |
| `AgentQueryApplicationService` | 建议新增 | 身份检查、预算、准入、一次 runtime 调用 | 动作选择、领域规则 | 接入治理变化 | query + Jwt → semantic response |
| `AgentRuntimeClient` | 建议新增 | 稳定 Java 运行时调用边界 | HTTP 细节、自动重试 | 内部协议调用语义变化 | internal request → outcome |
| `WebClientAgentRuntimeClient` | 建议新增 | HTTP 序列化、连接和传输错误转换 | 语义状态改写 | 传输实现变化 | OpenAPI DTO ↔ HTTP |
| `RuntimeIngress` | 建议新增 | 校验内部请求、构造 scope、调用 invoker | 图编排、领域调用 | 内部协议变化 | transport request → outcome |
| `DisconnectWatcher` | 建议新增 | 将上游连接断开转成一次性取消信号 | 强制中断第三方阻塞代码 | 取消传播变化 | ASGI request → signal |
| `AgentRuntimeInvoker` | 建议新增但由 `L2_00_01` 定义 | 执行 LangGraph | HTTP/认证 | 核心图变化 | question + scope → outcome |
| 两份 OpenAPI 文件 | 建议新增 | 字段、枚举和版本权威 | 运行逻辑 | HTTP 契约变化 | YAML schema |

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
| `DR-ACCESS-005` | Runtime 默认绑定回环地址且仅接收 Spring | Python 启动 | 进程启动 | 非回环部署不获本设计授权 |
| `DR-ACCESS-006` | JWT 只在 Authorization header 和 `OpaqueUserToken` 中传递 | 两端入口 | 内部调用 | 不进 JSON/state/log |
| `DR-ACCESS-007` | Spring 创建硬截止，Python 取剩余时限和绝对截止的较小值 | 两端 | 请求接收 | 单一有界预算 |
| `DR-ACCESS-008` | 连接断开/超时通过取消信号停止新增节点，迟到结果丢弃 | 两端 | 取消或逾期 | 无后台可见结果 |
| `DR-ACCESS-009` | 请求正文、问题、并发和响应均有固定上限 | 两端 | 入口/客户端 | 越界失败关闭 |
| `DR-ACCESS-010` | Runtime 语义结果使用 HTTP 200，传输错误使用非 2xx | Python API | invoker 完成或协议失败 | 传输/语义不混淆 |
| `DR-ACCESS-011` | Spring 保持 status、capability、answer、userResult、failure 语义 | response mapper | 收到合法内部响应 | 不改义、不补造领域结果 |
| `DR-ACCESS-012` | 未知字段/枚举/版本均失败关闭，不做宽松兼容 | 两端 DTO | 解析请求/响应 | 明确协议失败 |
| `DR-ACCESS-013` | liveness 只证明进程存活，readiness 证明本地对象图有效及对端可达 | 两进程 | 健康探测 | 可诊断启动顺序 |
| `DR-ACCESS-014` | 不持久化请求、不去重、不续跑；重复提交是新请求 | 两端 | 重复或重启 | 无幂等承诺 |
| `DR-ACCESS-015` | 日志仅记录安全元数据，异常正文不进入响应或日志 | 两端 | 全部边界 | JWT/问题/结果不泄露 |
| `DR-ACCESS-016` | 运行时配置启动校验并冻结，变更重启生效 | 两端组合根 | 启动 | 非法配置不就绪 |
| `DR-ACCESS-017` | Python ingress 对 `payload.question` 只校验一次并保存为局部不可变值；该值同时传给 `AgentRuntimeInvoker.ainvoke(question=...)` 和 `CapabilityExecutionContext.original_question`，不得再次 trim、改写或从模型候选回填 | Python ingress、Runtime invoker | 合法内部请求 | 同源进入图与 handler；不一致固定失败关闭 |

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
| `invalid_argument` | 400 | 空 | 必填 |
| `unauthenticated` | 401 | 空 | 必填 |
| `forbidden`、`model_egress_denied` | 403 | 空 | 必填 |
| `timeout` | 504 | 空 | 必填 |
| `downstream_failure` | 502 | 空 | 必填 |
| `internal_failure` | 500 | 空 | 必填 |

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
| `deadlineEpochMs` | int64 | 是 | Spring 硬截止 UTC epoch 毫秒 |
| `remainingTimeoutMs` | int32 | 是 | 1～60000；发送时剩余预算 |

Python 先把通过严格校验的 `question` 保存为单一局部值；该值既作为 `AgentRuntimeInvoker.ainvoke(question=...)` 的图输入，也由 `to_execution_scope` 原样写入 `CapabilityExecutionContext.original_question`。两处不得各自 trim、规范化或复制模型参数；Runtime 仍按 `L2_00_01` v0.4 执行精确相等闸门。该规则不增加内部协议字段。

Python 计算：

```text
effectiveRemainingMs =
  min(remainingTimeoutMs, deadlineEpochMs - currentEpochMs)
deadlineMonotonic =
  time.monotonic() + max(0, effectiveRemainingMs - 100) / 1000
```

100ms 是 Runtime 入口保护余量，不延长 Spring 硬截止。`effectiveRemainingMs <= 100` 时不调用 invoker，返回语义 `timeout/core.deadline_exhausted`。Python 不解析 JWT claims、不修改 token；其对 subject 的信任成立于回环内部边界，真实跨主机部署必须另行设计服务间认证。

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
| 400/409/413 | `internal_failure/core.runtime_protocol_error` | 否 | 500 |
| 401 | `unauthenticated/core.runtime_auth_context_invalid` | 否 | 401 |
| 429 | `downstream_failure/core.runtime_capacity_exceeded` | 否 | 502 |
| 503/连接拒绝 | `downstream_failure/downstream.runtime_unavailable` | 否 | 502 |
| Spring 硬截止/读取超时 | `timeout/downstream.runtime_timeout` | 否 | 504 |
| 无效 JSON/媒体类型/超界 body | `internal_failure/core.runtime_invalid_response` | 否 | 500 |
| Runtime 进程退出/连接重置 | `downstream_failure/downstream.runtime_connection_lost` | 否 | 502 |

Spring 不读取 Runtime 错误正文构造用户响应。传输异常不触发第二次 invoke；调用方若重新提交，形成新的 requestId 和新请求。

## 10. 权限、安全、审计与输入边界

### 10.1 Spring 认证顺序

1. Reactor Netty 在 32768 bytes 限制内读取 JSON。
2. Spring Security 验证 JWT 签名、有效期和结构。
3. application service 读取 `Jwt`，校验 `sub` 非空及 `SecurityTokenUtils.isUserToken(jwt)`。
4. 校验问题、关联标识和并发准入。
5. 建立总截止时间并构造一次内部请求。
6. 只有以上全部成功才显式读取 `jwt.getTokenValue()` 构造 Authorization header。

角色 claim 不参与 Agent 入口的业务授权；Employee/Transaction 最终授权仍在业务服务。合法服务 token 也不得作为本链路用户身份，返回 401。

### 10.2 Runtime 内部边界

- 默认 `host=127.0.0.1`、`port=8091`，Gateway/Eureka 不为 Runtime 建立路由或注册。
- Python 入口只验证 header/bearer 非空、协议字段严格有效，并将 token 包装为 `OpaqueUserToken`。
- 不在 Python 重复实现 JWT 验签、role 解析或业务授权。
- 若未来 Spring/Python 分主机部署，回环假设失效；必须新增受权的服务间认证/网络策略设计，不能仅把 host 改为 `0.0.0.0`。

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
| `agent.runtime.cancel-grace` | 250ms | 0～1000ms | Python ingress |

Spring 外层 `Mono.timeout(totalTimeout)` 是硬截止；内部连接、Runtime graph、模型和能力只能消费其剩余预算。任何子层配置不得延长总时限。

### 11.2 取消流程

1. 外部客户端断连、Spring timeout 或进程 shutdown 取消 application Mono。
2. WebClient subscription 取消并关闭内部响应等待。
3. ASGI `Request.is_disconnected()` 观察到上游断开，调用 `CancellationSignal.cancel(upstream_cancel)`。
4. invoker/core 在节点和出站前检查 signal；不再安排新模型或能力调用。
5. 取消后到达的结果不序列化、不写最终 outcome；请求内对象释放。

连接取消不能保证中断已经到达外部系统的只读请求，本期接受该限制。不得为“确认取消”新增持久任务、取消 API 或自动重放。

### 11.3 并发与重复

| 边界 | 默认 | 行为 |
|---|---:|---|
| Spring in-flight | 8 | 超出返回 429 `core.ingress_capacity_exceeded`，Runtime 调用为零 |
| Uvicorn worker | 1 | 保持一个进程级冻结注册快照 |
| Runtime in-flight | 8 | 超出返回 HTTP 429，Spring 映射下游容量失败 |
| request replay | 0 次自动重试 | 超时、连接失败和 5xx 均不重放 |

requestId 仅用于关联，不是幂等键。重复 requestId 不授予重放安全；内部调用者只有 Spring，必须每次生成新 UUID。

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
| `agent.ingress.max-in-flight` | 8 | 1～32 | 否 | 重启 |
| `agent.ingress.total-timeout` | 60s | 5～120s | 否 | 重启 |
| `agent.runtime.base-url` | `http://127.0.0.1:8091` | http + loopback；禁止 userinfo/path/query | 否 | 重启 |
| `agent.runtime.contract-version` | 1 | 只能 1 | 否 | 启动失败 |
| `agent.runtime.connect-timeout` | 1s | 100ms～5s | 否 | 重启 |
| `agent.runtime.max-response-bytes` | 393216 | 32768～524288 | 否 | 重启 |

### 13.2 Python 配置

| 环境键 | 默认 | 校验 | 敏感 | 说明 |
|---|---|---|---:|---|
| `AGENT_RUNTIME_HOST` | `127.0.0.1` | 当前只能回环地址 | 否 | 非回环启动失败 |
| `AGENT_RUNTIME_PORT` | `8091` | 1～65535 | 否 | 与 Spring URL 对齐 |
| `AGENT_RUNTIME_CONTRACT_VERSION` | `1` | 只能 1 | 否 | 启动失败 |
| `AGENT_RUNTIME_MAX_BODY_BYTES` | `32768` | 4096～65536 | 否 | ASGI 前置限制 |
| `AGENT_RUNTIME_MAX_IN_FLIGHT` | `8` | 1～32 | 否 | 与 Uvicorn limit 对齐 |
| `AGENT_RUNTIME_DISCONNECT_POLL_MS` | `100` | 50～500 | 否 | 取消观察 |

配置加载后冻结，不支持热更新。Spring 配置可来自 Config Server；Python 仅通过启动环境/命令参数加载非敏感设置。两端显式非法值均阻止 readiness。

### 13.3 构建依赖

- `agent-service` 继承 `serviceCenter/pom.xml`，新增 `spring-boot-starter-webflux`、`spring-boot-starter-oauth2-resource-server`、`spring-boot-starter-actuator`、`common-security` 和测试依赖。
- `agent-runtime` 保持 Python `>=3.12,<3.13`、`langgraph==1.2.9`；传输边界建议锁定 `fastapi==0.139.2`、`uvicorn==0.51.0`、`pydantic==2.13.4`。
- Pydantic 仅用于 `agent_runtime.api` 传输 DTO；`capability_api`、`core` 和 graph state 不得依赖它。
- 升级任一 HTTP/序列化依赖必须重跑双端契约、取消、body 限制和未知字段测试。

## 14. 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置项 | 责任 | 必要性 | 设计规则 |
|---|---|---|---|---|---|---|---|
| `IMPL-ACCESS-001` | 建议新增 | OpenAPI | `agent-contracts/openapi/agent-public-v1.yaml` | `/api/v1/agent/queries` | 外部契约权威 | 防字段漂移 | `DR-ACCESS-002/011/012` |
| `IMPL-ACCESS-002` | 建议新增 | OpenAPI | `agent-contracts/openapi/agent-runtime-internal-v1.yaml` | invoke/health | 内部契约权威 | 跨语言一致 | `DR-ACCESS-002/010/012` |
| `IMPL-ACCESS-003` | 建议新增 | Maven/配置 | `agent-service/pom.xml`、`agent-service/src/main/resources/application.yml` | 依赖和 `agent.*` | Spring 构建/配置 | 新进程必需 | `DR-ACCESS-009/013/016` |
| `IMPL-ACCESS-004` | 建议新增 | Java security | `agent-service/src/main/java/com/dylan/agent/service/config/AgentSecurityConfiguration.java` | `SecurityWebFilterChain agentSecurityWebFilterChain(ServerHttpSecurity http)` | API 认证及健康白名单 | 用户入口保护 | `DR-ACCESS-001/004` |
| `IMPL-ACCESS-005` | 建议新增 | Java boundary | `agent-service/src/main/java/com/dylan/agent/service/security/AgentUserContextFactory.java` | `AgentUserContext requireUser(Jwt jwt)` | subject/token_type 与 token 提取 | 禁服务身份回退 | `DR-ACCESS-004/006` |
| `IMPL-ACCESS-006` | 建议新增 | Java application | `agent-service/src/main/java/com/dylan/agent/service/application/AgentQueryApplicationService.java` | `Mono<AgentQueryResponse> query(AgentQueryCommand command, Jwt jwt, String requestedCorrelationId)` | 准入、预算、一次调用 | 接入治理核心 | `DR-ACCESS-003/004/007/008` |
| `IMPL-ACCESS-007` | 建议新增 | Java web | `agent-service/src/main/java/com/dylan/agent/service/web/AgentQueryController.java` | `Mono<ResponseEntity<AgentQueryResponse>> query(AgentQueryRequest request, JwtAuthenticationToken authentication, ServerWebExchange exchange)` | HTTP 输入输出 | 外部入口 | `DR-ACCESS-001/011` |
| `IMPL-ACCESS-008` | 建议新增 | Java control | `agent-service/src/main/java/com/dylan/agent/service/application/AgentRequestLimiter.java` | `Lease tryAcquire()`、`void close()` | 有界并发且 exactly-once 释放 | 入口容量 | `DR-ACCESS-009` |
| `IMPL-ACCESS-009` | 建议新增 | Java client contract | `agent-service/src/main/java/com/dylan/agent/service/runtime/AgentRuntimeClient.java` | `Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken)` | 稳定调用边界 | 隔离 HTTP | `DR-ACCESS-003/006/007` |
| `IMPL-ACCESS-010` | 建议新增 | Java HTTP adapter | `agent-service/src/main/java/com/dylan/agent/service/runtime/WebClientAgentRuntimeClient.java` | `invoke(...)`、`mapTransportFailure(Throwable)` | HTTP 调用、严格响应和失败转换 | 跨进程调用 | `DR-ACCESS-006/010/011/012` |
| `IMPL-ACCESS-011` | 建议新增 | Python ingress | `agent-runtime/src/agent_runtime/api/ingress.py` | `async def invoke_agent(request: Request, payload: RuntimeInvokeRequest, authorization: str, runtime: AgentRuntimeInvoker) -> RuntimeInvokeResponse` | scope/原始问题同源构造、取消、invoker 调用 | Python 入口 | `DR-ACCESS-005/006/007/008/010/017` |
| `IMPL-ACCESS-012` | 建议新增 | Python app factory | `agent-runtime/src/agent_runtime/api/app.py` | `def create_app(settings: RuntimeHttpSettings, runtime_factory: RuntimeFactory) -> FastAPI` | lifespan、route、ready 状态 | 可测试组合 | `DR-ACCESS-005/013/016` |
| `IMPL-ACCESS-013` | 建议新增 | 健康 | Java `AgentRuntimeHealthIndicator`；Python `health.py` | `health()`、`live()`、`ready()` | 双进程健康语义 | 启停诊断 | `DR-ACCESS-013` |
| `IMPL-ACCESS-014` | 建议新增 | 契约测试资产 | `agent-contracts/fixtures/*.json` | 成功/失败/未知字段/版本样例 | 双端共用样例 | 防实现漂移 | `DR-ACCESS-002/012` |
| `IMPL-ACCESS-015` | 建议新增 | Python transport DTO | `agent-runtime/src/agent_runtime/api/models.py` | strict Pydantic request/response models | camelCase↔核心转换并提供单一已校验 question 值 | 传输隔离 | `DR-ACCESS-006/010/012/017` |
| `IMPL-ACCESS-016` | 建议新增 | 启动入口 | `agent-runtime/src/agent_runtime/main.py` | `def main() -> None` | 单 worker、回环启动 | 双进程部署 | `DR-ACCESS-005/014/016` |

### 14.1 Java 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| `AgentUserContextFactory.requireUser` | `AgentUserContext requireUser(Jwt jwt)` | jwt 非空、sub 非空、`token_type=user`；不得校验业务角色 | 返回只读 `subjectId/rawToken`；失败抛无敏感正文的 `AgentUnauthenticatedException` | 无；application service |
| `AgentQueryApplicationService.query` | `Mono<AgentQueryResponse> query(AgentQueryCommand command, Jwt jwt, String requestedCorrelationId)` | 身份→问题→关联 ID→准入→预算顺序 | 唯一外部响应；超时/协议错误按 9.6 映射 | 一次 runtime invoke；`doFinally` 释放 lease |
| `AgentRuntimeClient.invoke` | `Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken)` | request 已由 application service 构造；raw token 不可空 | 仅返回已通过契约校验的 response；传输错误为 typed exception | 不重试；application service |
| `AgentQueryController.query` | `Mono<ResponseEntity<AgentQueryResponse>> query(AgentQueryRequest request, JwtAuthenticationToken authentication, ServerWebExchange exchange)` | WebFlux/Bean Validation 只做传输校验 | 按 9.3 状态映射 HTTP | 不读取 Adapter/模型 |
| `AgentRequestLimiter.tryAcquire` | `Lease tryAcquire()` | 原子计数小于上限 | 返回 AutoCloseable lease；超限抛 `IngressCapacityExceeded` | 请求完成/取消只释放一次 |

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
| `api.ingress.invoke_agent` | `async def invoke_agent(request: Request, payload: RuntimeInvokeRequest, authorization: str, runtime: AgentRuntimeInvoker) -> RuntimeInvokeResponse` | header/body/version/预算严格校验；把同一已校验 question 传入 scope 与 invoker；token 包装；不解析 role | 合法 outcome 响应；不同源由 invoker 固定返回 `invalid_argument`；transport error 由 exception handler 映射 | 创建请求级 scope 和 disconnect task |
| `api.ingress.to_execution_scope` | `def to_execution_scope(payload: RuntimeInvokeRequest, raw_token: str, cancellation: CancellationSignal, clocks: RuntimeClocks) -> RequestExecutionScope` | 使用 9.4 较小预算、`payload.question` 原样写入 `original_question`；subject user | scope；非法身份/问题/过期预算为 typed ingress error | 无外部 I/O |
| `api.cancellation.watch_disconnect` | `async def watch_disconnect(request: Request, signal: CancellationSignal, poll_interval_s: float) -> None` | 周期有界；只观察首个断开 | 无返回；首个断开发布 `upstream_cancel` | 不取消进程全局任务 |
| `api.app.create_app` | `def create_app(settings: RuntimeHttpSettings, runtime_factory: RuntimeFactory) -> FastAPI` | settings 已冻结；lifespan 构建 runtime | FastAPI app；构建失败保持 not ready | 唯一知道 transport/runtime 绑定 |
| `main.main` | `def main() -> None` | 读取严格环境设置；host 必须回环、workers=1 | 启动 Uvicorn；非法配置退出非零 | 不动态扫描能力 |

Pydantic models 使用 `ConfigDict(extra="forbid", strict=True, populate_by_name=False)`，传输字段使用显式 alias；转换后不得把 Pydantic model 传入 core。

## 15. 测试与验证设计

### 15.1 测试定义

| 测试编号 | 设计规则 | 层级 | 建议路径/用例 | 测试意图与关键断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-ACCESS-001` | `DR-ACCESS-002/012` | Contract | 建议新增：`agent-contracts/tests/test_openapi_examples.py` | 两份 schema 和全部 fixture 合法；未知字段/枚举/版本样例拒绝 | 任一端可接受契约外字段 |
| `TEST-ACCESS-002` | `DR-ACCESS-004/006/015` | Java Unit/Web | 建议新增：`agent-service/src/test/java/com/dylan/agent/service/security/AgentSecurityContractTest.java` | 缺 token、坏 token、service token、空 sub 均 401；runtime spy=0；日志无 token | 非用户身份触发内部调用 |
| `TEST-ACCESS-003` | `DR-ACCESS-003/009/014` | Java Unit | `AgentQueryApplicationServiceTest` | 成功/失败均一次 invoke；超限 429；客户端错误不重试 | invoke 次数不为 0/1 |
| `TEST-ACCESS-004` | `DR-ACCESS-007/009` | Cross-language Integration | 建议新增：`agent-service/src/test/java/com/dylan/agent/service/runtime/AgentRuntimeDeadlineIntegrationTest.java`、`agent-runtime/tests/integration/test_deadline.py` | 预算取较小值、边界耗尽零 invoker、Spring 60s 硬截止 | 子预算延长总时限 |
| `TEST-ACCESS-005` | `DR-ACCESS-008` | Integration | `agent-runtime/tests/integration/test_disconnect_cancellation.py` | 断连发布一次取消，停止新增 node，晚到结果不响应 | 取消后仍安排调用 |
| `TEST-ACCESS-006` | `DR-ACCESS-010/011` | Contract | Java/Python `test_semantic_mapping` | 全状态/合法空值映射；失败不得变 success；safe payload 不出现 | 状态改义或字段泄露 |
| `TEST-ACCESS-007` | `DR-ACCESS-005/013/016` | Integration | 建议新增：`agent-runtime/tests/integration/test_health_and_startup.py` | graph 未编译时 runtime not ready；runtime down 时 Spring not ready；liveness 独立 | 假就绪或健康泄密 |
| `TEST-ACCESS-008` | `DR-ACCESS-002/012` | Consumer/Provider | 建议新增：`agent-service/src/test/java/com/dylan/agent/service/runtime/RuntimeContractTest.java`、`agent-runtime/tests/contract/test_runtime_openapi.py` | 共享 fixture 双端同判定，requestId 不匹配/超界响应拒绝 | 手写 DTO 漂移 |
| `TEST-ACCESS-009` | `DR-ACCESS-006/015` | Architecture/Log | Java/Python logging tests | body/state/log/repr 均无 JWT、subject、question、result | 捕获敏感文本 |
| `TEST-ACCESS-010` | `DR-ACCESS-001/005/014` | Architecture | 建议新增：`agent-runtime/tests/architecture/test_runtime_not_public.py` | host 固定回环、无 Eureka/Gateway 注册、无 persistence/messaging dependency | Runtime 可由外部路由访问 |
| `TEST-ACCESS-011` | `DR-ACCESS-017` | Python Unit/Integration | 建议新增：`agent-runtime/tests/unit/api/test_question_binding.py` | spy 捕获 invoker question 和 handler context；合法请求两值精确相同；人为构造不同值时 graph/selector/validator/handler 均为 0 且返回 `invalid_argument/core.question_context_mismatch`；日志无问题正文 | 两处独立规范化、静默覆盖、信任模型参数或发生下游调用 |

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
| `VAL-ACCESS-001` | `D:\codex` | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md --root D:\codex --strict` | 0 errors、0 warnings；仅证明文档确定性规则 | 已执行：0 errors、0 warnings（2026-07-25） |
| `VAL-ACCESS-002` | 未来 `agent-service` | `mvn -f agent-service/pom.xml test` | Java 安全、准入、映射和客户端测试通过 | 未执行：代码未授权且不存在 |
| `VAL-ACCESS-003` | 未来契约与两端代码 | `python -m pytest agent-contracts/tests agent-runtime/tests/contract -q`，并执行 Java contract test | 两端对同一 fixture 判定一致 | 未执行：资产不存在 |
| `VAL-ACCESS-004` | 两进程本地启动 | `python -m pytest agent-runtime/tests/integration/test_deadline.py agent-runtime/tests/integration/test_disconnect_cancellation.py -q` | 时限、取消和晚到结果符合设计 | 未执行：代码不存在 |
| `VAL-ACCESS-005` | 本地双进程 | 启动 Runtime→Spring，探测四个健康端点，再逆序停止 | 就绪顺序、取消与单实例恢复正确 | 未执行：进程不存在 |

## 16. 发布、迁移与回滚

- 全部目标模块和契约为新增，无数据库、索引或消息迁移。
- 初次实现先使用 `L2_00_01` 本地模型/能力 stub 验证双进程，不接入真实 DeepSeek 或业务数据。
- 发布粒度必须包含内部 OpenAPI、Java DTO/客户端和 Python DTO/入口的同一 v1 版本；不支持只部署单侧破坏性变化。
- 回滚时先停止 `agent-service`，恢复两端前一兼容构建和配置，再先 Runtime 后 Spring 启动。
- Runtime 异常可停止整个逻辑 Agent；不得让 Spring 绕过 Runtime 直接调用能力。
- in-flight 请求在重启中失败并由调用方决定是否新建请求，不自动续跑。

## 17. 风险、待确认事项与授权需求

### 17.1 风险与待确认事项

| 编号 | 类型 | 证据缺口或风险 | 触发场景 | 影响 | 建议 | 是否阻塞/需授权 |
|---|---|---|---|---|---|---|
| `RISK-ACCESS-001` | 契约漂移 | OpenAPI 与两端手写 DTO 不一致 | 单侧修改字段 | 解析失败或含义漂移 | 共享 fixture 和 provider/consumer test | 阻塞实施门禁 |
| `RISK-ACCESS-002` | 网络边界 | 回环假设被部署改为跨主机 | 修改 host 为非 loopback | Runtime 形成未认证入口 | 另行设计服务间认证和网络策略 | 跨主机前需上位/安全授权 |
| `RISK-ACCESS-003` | 取消限制 | 已发出只读 HTTP 不能强制中断 | 客户端断连 | 短时资源继续占用 | 硬时限、并发上限、迟到丢弃 | 不阻塞本地切片 |
| `RISK-ACCESS-004` | 身份泄露 | 调试日志记录 header/body | HTTP 异常 | JWT/问题泄露 | 日志捕获负向测试 | 阻塞实施门禁 |
| `RISK-ACCESS-005` | 版本依赖 | FastAPI/Uvicorn 升级改变断连或 strict parsing | 依赖升级 | 取消/解析行为漂移 | 锁版本并全量回归 | 升级需变更评审 |
| `RISK-ACCESS-006` | 预算 | 60 秒对真实模型/知识链路是否合适尚无实测 | P4 完整链路 | 误超时或等待过长 | P3/P4 采集阶段耗时后在允许范围内调整 | 不阻塞设计；阻塞完成性能结论 |
| `RISK-ACCESS-007` | 外部路由 | Gateway 当前路由与错误格式尚未为 Agent 固化 | P4 通过 Gateway | 外部响应可能被重写 | 后续在实现授权内增加 Gateway contract test | 不阻塞本文；阻塞 Gateway 端到端 |
| `RISK-ACCESS-008` | 上下文同源 | ingress 分别构造图问题与 handler 原始问题 | 未来重构 DTO/scope 转换 | Knowledge 改写与图问题漂移 | 单一局部值、Runtime 精确相等闸门和 `TEST-ACCESS-011` | 阻塞对应实施门禁 |

### 17.2 阶段门禁与外部证据

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威来源 | 责任方 | 最晚阶段 | 状态 | 未关闭时允许/禁止动作 |
|---|---|---|---|---|---|---|---|---|---|
| `CR-GATE-001` | design_decomposition | L1→本文 | 编写本文 | L1_00 v0.2 评审通过 | L1_00 14.1 | 项目维护者 | P2-L2 前 | Closed | 允许本文，不授权代码 |
| `CR-GATE-002` | slice_implementation | `agent-service`、Runtime HTTP ingress、两份 OpenAPI 与双进程测试 | 创建目标代码/配置/测试并宣称该切片完成 | 本文与 `L2_00_01` 已评审可实施；契约、失败、测试、回滚明确；用户明确授权 | 两份 L2 的正式评审与追踪 | 项目维护者 | P3 前 | Open | 允许文档/fixture 推演；禁止目标实施 |
| `CR-GATE-003` | integration | 用户问题进入 DeepSeek | 敏感问题外发 | `L2_00_02` 输入分类/最小化/零调用证据 | 模型 L2 | 项目维护者/模型方 | 首次敏感联调 | Open | 本文只传问题到受控 Runtime；禁止据此允许模型外发 |
| `SA-GATE-002` | slice_implementation | 真实模型 | DeepSeek 真实实现 | Provider 契约与 PoC | `L2_00_02` | 项目维护者/DeepSeek | 模型切片前 | Open | 可用本地模型 stub |
| `SA-GATE-006` | integration | 真实领域数据模型输入 | 真实证据/业务结果外发 | 领域出域 L2 与零调用测试 | 关联 L2 | 项目维护者/领域方 | P4 | Open | 只用合成安全载荷 |

### 17.3 需要后续授权的动作

- 创建 `agent-contracts`、`agent-service`、`agent-runtime` 代码、配置和测试。
- 将 `agent-service` 加入父 POM、Config Server、Eureka 或 Gateway。
- Runtime 改为非回环部署或新增服务间认证。
- 关闭 `CR-GATE-002` 或任何真实模型/数据集成门禁。

## 18. 内部自检记录

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-25 | 0 | 1 | 2 | 3 | 无 | 修复校验器未识别的流程/安全章节、组合追踪 ID 和建议新增路径标记 |
| 2 | 2026-07-25 | 0 | 0 | 0 | 0 | 无 | 完整 rubric 复核无目标内材料缺口，进入严格校验 |

作者自检只用于改进 Draft，不构成独立评审、Approved、实施授权或门禁关闭证据。

## 19. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] Java 类路径、关键方法、输入、输出、错误和消费者已明确。
- [x] Python 模块、关键函数、异步、取消和状态影响已明确。
- [x] 外部与内部契约字段、枚举、空值、版本、超时和兼容性已明确。
- [x] 责任、非责任、依赖方向和禁止旁路已明确。
- [x] JWT、日志、Runtime 网络暴露和失败关闭已明确。
- [x] 当前允许/禁止实施范围和开放门禁已明确。
- [x] 本轮原始问题同源补正后已重新执行 `validate_detailed_design.py --strict`，结果为 0 errors、0 warnings；仅作为确定性文档证据。
- [ ] 独立设计评审已通过并获准关闭对应 `CR-GATE-002` 切片。

## 20. 当前结论

本文已形成 Spring WebFlux 外部入口、回环 HTTP/JSON 内部协议、OpenAPI 契约源、原始问题同源绑定、总时限/取消、双进程健康和实现/测试落点的 Draft，并已通过严格文档校验。它可进入独立设计评审，但在正式评审和 `CR-GATE-002` 关闭前，不得作为代码实施授权或真实链路可用证据。
