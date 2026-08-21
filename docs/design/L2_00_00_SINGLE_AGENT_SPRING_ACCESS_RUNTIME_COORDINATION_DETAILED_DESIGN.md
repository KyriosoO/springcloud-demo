# [L2_00_00] 单体 Agent Spring 接入与 Runtime 协同详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_00_00` |
| 当前版本 | v1.0 |
| 日期 | 2026-08-21 |
| 权威范围 | `agent-service` 公共 HTTP 接入、Spring→Python 内部协议、预算/取消/容量、健康与错误映射 |
| 上位文档 | [`L1_00` v1.0](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) |
| 来源文档 | [L2_00_00 v0.9 归档版](历史文档/2026-08-21-v0-baseline/L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md) |
| 实施状态 | 当前代码已实现并有 Java/Python 契约及系统 E2E；未生产生效 |

## 2. 阅读导航与变更记录

优先阅读：第 5 节责任边界、第 7 节双层契约、第 8 节流程、第 9 节错误映射、第 13 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立可实施且易读的新基线 | 删除历史 Gate/评审流水，保留当前协议、时限、容量、安全和代码锚点 |

## 3. 目标与范围

### 3.1 目标

提供唯一公网接入路径，把已认证用户问题转换为严格、最小、可取消的内部 Runtime 请求；Spring 负责接入治理，Python/LangGraph 负责语义执行，两侧均不越权编排另一侧职责。

### 3.2 范围内

- `POST /api/v1/agent/queries`；
- `POST /internal/v1/agent-runs:invoke`；
- 双层 DTO、版本头、JWT 透传、错误和状态映射；
- 请求体/并发上限、总时限、响应预留、取消和连接生命周期；
- liveness/readiness 及最小日志。

### 3.3 范围外与不负责

- 能力选择、参数生成、Core、Knowledge/Business 语义；
- JWT 角色到 Authority 的公共转换规则；
- Gateway 正式路由、生产高可用、跨进程重试、熔断或服务发现；
- 修改领域 Provider 或模型协议。

## 4. 上位约束与追踪关系

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-ACCESS-001` | 认证用户可通过唯一公共端点提交一个问题并获得统一响应 |
| `REQ-ACCESS-002` | Spring 与 Runtime 使用版本化严格 JSON 契约，额外字段失败关闭 |
| `REQ-ACCESS-003` | 总时限、取消、容量和响应大小均有界 |
| `REQ-ACCESS-004` | 未认证、协议错误、语义失败和基础设施失败保持可区分 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-ACCESS-001` | `L1_00`：Spring 只接入治理，LangGraph 是唯一编排权威 |
| `CON-ACCESS-002` | `L0_00 SA-C-007/011`：有效用户 JWT 必需且不得泄漏 |
| `CON-ACCESS-003` | `L0_00 SA-C-002/019`：一个请求最多一个动作，Spring 不复制语义路由 |
| `CON-ACCESS-004` | 公共与内部协议必须兼容演进并可由跨语言契约测试证明 |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-ACCESS-001`、`CON-ACCESS-001`、`CON-ACCESS-003` | `DR-ACCESS-001`、`DR-ACCESS-002` | `IMPL-ACCESS-001`、`IMPL-ACCESS-005` | `TEST-ACCESS-001`、`TEST-ACCESS-004` | `VAL-ACCESS-001` |
| `REQ-ACCESS-002`、`CON-ACCESS-004` | `DR-ACCESS-003`、`DR-ACCESS-004` | `IMPL-ACCESS-002`、`IMPL-ACCESS-006` | `TEST-ACCESS-002`、`TEST-ACCESS-005` | `VAL-ACCESS-002` |
| `REQ-ACCESS-003` | `DR-ACCESS-005`、`DR-ACCESS-006`、`DR-ACCESS-007` | `IMPL-ACCESS-003`、`IMPL-ACCESS-007` | `TEST-ACCESS-003`、`TEST-ACCESS-006` | `VAL-ACCESS-003` |
| `REQ-ACCESS-004`、`CON-ACCESS-002` | `DR-ACCESS-008`、`DR-ACCESS-009` | `IMPL-ACCESS-004`、`IMPL-ACCESS-008` | `TEST-ACCESS-007`、`TEST-ACCESS-008` | `VAL-ACCESS-004` |

## 5. 关联资源与责任边界

| 层/组件 | 唯一职责 | 不负责 |
|---|---|---|
| `AgentQueryController` | 公共 HTTP DTO、认证主体和 HTTP 状态 | 能力选择、Runtime 重试 |
| `AgentQueryApplicationService` | 输入规范化、接入容量、总预算、内部请求、响应映射 | LangGraph 节点和领域规则 |
| `AgentRuntimeClient` | 严格内部 HTTP 调用、大小限制、传输错误分类 | 语义失败解释、JWT 改写 |
| Runtime API | 内部协议校验、容量、JWT 包装、取消和 Runtime 调用 | 再认证用户、公共 HTTP 契约 |
| LangGraph Runtime | 返回统一语义终态 | Spring HTTP 状态或接入限流 |

依赖方向固定为 `Controller → ApplicationService → AgentRuntimeClient → Runtime API → LangGraph`。禁止 Runtime 反向依赖 Spring；禁止 Spring 根据能力 ID 编排工具或领域调用。

该拆分以内聚职责和稳定内部契约为边界，不增加第二个编排器或通用网关抽象。

## 6. 当前实现基线与最小变更判断

### 6.1 当前实现

- Java WebFlux 接入、JWT Resource Server、请求元数据、并发 lease 和 WebClient 已存在。
- Python FastAPI 内部端点、严格 Pydantic DTO、请求体限制、并发 limiter、断连监视和生命周期关闭已存在。
- 公共/内部状态枚举、Failure source、contract version=1 和跨语言 fixture 已落地。
- 当前默认内部地址为 loopback，Runtime 不公开 OpenAPI UI。

### 6.2 最小变更与抽象必要性

新基线不要求代码改造。`AgentRuntimeClient` 和 `RuntimeInvoker` 已提供测试替换和未来韧性装饰接缝；新增代理层、消息总线或统一工作流会扩大故障面，当前无必要。

## 7. 接口与契约设计

### 7.1 公共接口

`POST /api/v1/agent/queries`

请求：

```json
{"question":"用户问题"}
```

公共响应字段：`requestId`、`correlationId`、`status`、`capabilityId?`、`answer?`、`result?`、`error?`。`answerText/userResult` 只属于第 7.3 节内部 Runtime 响应，Spring 必须显式映射，不能泄漏内部字段名。请求未知字段、空白问题或超界问题在进入 Runtime 前拒绝。

### 7.2 内部接口

`POST /internal/v1/agent-runs:invoke`

必需头：

- `Authorization: Bearer <原始用户 JWT>`；
- `X-Agent-Contract-Version: 1`；
- `Content-Type: application/json`。

内部请求：

| 字段 | 类型/边界 | 来源 |
|---|---|---|
| `contractVersion` | exact integer `1` | Spring 配置 |
| `requestId`、`correlationId` | printable ASCII，1..128 | 接入元数据 |
| `question` | 非空，≤4096 字符 | 规范化公共请求 |
| `subject.id` | 非空 UTF-8，≤256 bytes | JWT subject |
| `subject.type` | exact `user` | 固定 |
| `deadlineEpochMs` | 正整数 | 总预算计算 |
| `remainingTimeoutMs` | 1..120000 | 总预算减响应预留 |

两侧严格拒绝未知字段、错误类型、版本不一致和不合法组合。内部协议不包含角色、能力参数、模型配置或领域数据。

### 7.3 内部响应

`RuntimeInvokeResponse` 使用 `contractVersion=1`、`requestId`、`status`、`capabilityId?`、`answerText?`、`userResult?`、`failure?`。`success/no_result` 不得带 failure；失败状态必须带 failure 且不得带 userResult。

`userResult` 仅承载公共 JSON object；Java 客户端仍需限制完整响应字节并严格解码。

## 8. 详细功能与核心流程

### 8.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-ACCESS-001` | 公共接口只接受一个问题，不接受能力、参数或工具提示 |
| `DR-ACCESS-002` | Spring 只治理认证、限流、预算和协议；不得按域或能力编排 |
| `DR-ACCESS-003` | 内部请求/响应均 extra-forbid、strict、version=1 |
| `DR-ACCESS-004` | 原始用户 JWT 只在受控 Client/Runtime ingress 边界揭示，不写 DTO |
| `DR-ACCESS-005` | Spring 计算硬截止并保留响应预算；Runtime 取传入剩余时间与 epoch deadline 的较小值 |
| `DR-ACCESS-006` | 两侧独立容量限制，获取失败立即返回，不排无界队列 |
| `DR-ACCESS-007` | 客户端断开触发 Runtime 取消；逾期结果不得返回 |
| `DR-ACCESS-008` | HTTP/传输失败与 Runtime 语义失败分层映射，未知异常失败关闭 |
| `DR-ACCESS-009` | 日志只记录请求标识、状态、耗时和有限类别，不记录 JWT/问题/结果正文 |

### 8.2 正常流程

1. WebFlux Security 验证 JWT；未认证请求不进入 Controller。
2. Metadata filter 建立 request/correlation ID 和单调时钟接收时间。
3. Controller 只构造 `AgentQueryCommand`。
4. Application Service 验证主体和问题，获取 Spring lease，计算硬截止与 Runtime 剩余预算。
5. WebClient 发送严格内部请求和原始用户 Bearer token。
6. Runtime 校验 Content-Type、大小、版本、DTO 和 token 形态，再获取 Runtime lease。
7. Runtime 将 token 包装为 `OpaqueUserToken`、创建请求级取消信号与执行 scope，调用 `ainvoke`。
8. 语义终态严格编码；Java 严格解码并映射公共响应和 HTTP 状态。
9. finally 释放两侧 lease；Runtime 生命周期结束时关闭组合根资源。

### 8.3 时限、取消与并发一致性

- Spring 总时限是接入权威；Runtime 只消费更小预算，不延长截止时间。
- Runtime 保留 100ms 内部安全余量；有效预算不足时直接 `timeout`。
- Spring timeout、客户端断连、Runtime shutdown 使用不同来源；都不得触发自动重试。
- lease 必须在所有完成、异常和取消路径精确释放一次。
- 请求状态仅驻留内存；无数据库事务、跨请求幂等键或恢复语义。

## 9. 失败类型与调用方可见语义

| 失败类型 | 内部/公共语义 | HTTP |
|---|---|---:|
| JWT 缺失/无效 | `unauthenticated` | 401 |
| 公共请求非法 | `invalid_argument` | 400 |
| 接入或 Runtime 容量不足 | `downstream_failure` + `core.ingress_capacity_exceeded` | 429 |
| 能力不支持 | `unsupported` | 422 |
| 业务拒绝 | `forbidden` | 403 |
| 模型出域拒绝 | `model_egress_denied` | 403 |
| 总预算耗尽 | `timeout` | 504 |
| Runtime/业务下游失败 | `downstream_failure` | 502 |
| 未分类内部异常 | `internal_failure` | 500 |

协议层 400/409/413/415/429/5xx 由 `AgentRuntimeClient` 映射为有限 `RuntimeClientException`；不得把 Runtime 错误正文透传给公共调用方。

## 10. 权限、安全与审计设计

- 公共端点仅 `authenticated()`，动作授权由能力/业务服务继续执行。
- Runtime 绑定 loopback；它不承担第二次 JWT 验签，但不得接受无 Bearer token 的调用。
- 用户 token 采用显式 opaque wrapper，`repr` 不暴露值，只在 outbound 边界揭示。
- 问题、JWT、用户结果和原始错误不进入普通日志；只记录有限状态、计数和耗时。
- 请求体上限、响应上限、严格 DTO 和 deny-all 未声明路由共同降低攻击面。

## 11. 健康、配置与数据生命周期

### 11.1 健康

- Runtime `/health/live` 只表明进程存活；`/health/ready` 只有组合根完成创建后才为就绪。
- Spring Runtime health 只用于诊断，不改变查询编排或自动降级。

### 11.2 关键配置

| 位置 | 配置 | 边界 |
|---|---|---|
| Spring `AgentIngressProperties` | question/body/response/并发/总时限/响应预留 | 启动校验；正数和有界关系 |
| Spring `AgentRuntimeProperties` | base URL、contractVersion、连接/响应/内存限制 | loopback/受控地址；version=1 |
| Python `RuntimeHttpSettings` | host/port/body/in-flight/disconnect poll | host 必须 loopback；范围校验 |

配置错误启动失败。无数据迁移；请求、token、取消信号和响应在请求结束后释放，不写持久存储。

## 12. 依赖、发布与回滚

- Java 使用既有 WebFlux/Security/Jackson；Python 使用既有 FastAPI/Pydantic/Uvicorn 运行栈，不新增生产依赖。
- 部署顺序：Runtime 启动并 ready → Spring 启动 → 受控探活 → 显式开放公共流量。
- 回滚顺序相反；内部 version 不兼容时先回滚调用方或双方一起回滚，禁止宽松兼容未知字段。
- 当前不实施数据库迁移，也不持久化会话或业务数据。

## 13. 实现落点清单

### 13.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-ACCESS-001` | `agent-service/src/main/java/com/dylan/agent/service/web/AgentQueryController.java`：`query(AgentQueryRequest, JwtAuthenticationToken, ServerWebExchange)` |
| `IMPL-ACCESS-002` | `agent-service/src/main/java/com/dylan/agent/service/contract/RuntimeInvokeRequest.java`、`RuntimeInvokeResponse.java` |
| `IMPL-ACCESS-003` | `agent-service/src/main/java/com/dylan/agent/service/application/AgentQueryApplicationService.java`：`query(AgentQueryCommand, Jwt, AgentRequestMetadata)` |
| `IMPL-ACCESS-004` | `agent-service/src/main/java/com/dylan/agent/service/config/AgentSecurityConfiguration.java`、`web/AgentWebExceptionHandler.java` |
| `IMPL-ACCESS-005` | `agent-runtime/src/agent_runtime/api/app.py`：`create_app(settings, runtime_factory) -> FastAPI` |
| `IMPL-ACCESS-006` | `agent-runtime/src/agent_runtime/api/models.py`：`RuntimeInvokeRequest`、`RuntimeInvokeResponse` |
| `IMPL-ACCESS-007` | `agent-runtime/src/agent_runtime/api/ingress.py`：`invoke_agent(...) -> RuntimeInvokeResponse`、`to_execution_scope(...)` |
| `IMPL-ACCESS-008` | `agent-runtime/src/agent_runtime/api/errors.py`、`limits.py`、`cancellation.py` |

### 13.2 边界签名

```java
Mono<ResponseEntity<AgentQueryResponse>> query(
    AgentQueryRequest request,
    JwtAuthenticationToken authentication,
    ServerWebExchange exchange)

Mono<AgentQueryResponse> query(
    AgentQueryCommand command,
    Jwt jwt,
    AgentRequestMetadata metadata)

Mono<RuntimeInvokeResponse> invoke(
    RuntimeInvokeRequest request,
    String rawUserToken)
```

```python
def create_app(
    settings: RuntimeHttpSettings,
    runtime_factory: RuntimeFactory,
) -> FastAPI

async def invoke_agent(
    request: Request,
    payload: RuntimeInvokeRequest,
    authorization: str,
    x_agent_contract_version: str,
    runtime: RuntimeInvoker,
    limiter: RuntimeRequestLimiter,
    *,
    clocks: RuntimeClocks | None = None,
    disconnect_poll_s: float = 0.1,
) -> RuntimeInvokeResponse
```

只列跨模块关键入口；普通私有 helper 以代码为准。

## 14. 测试与验证设计

### 14.1 测试编号定义

| 测试编号 | 场景与证据位置 |
|---|---|
| `TEST-ACCESS-001` | 公共 Controller、正常状态和 HTTP 映射：`agent-service/src/test/java/com/dylan/agent/service/web/AgentQueryControllerTest.java` |
| `TEST-ACCESS-002` | Java/Python 内部 DTO 和严格 JSON：`agent-service/src/test/java/com/dylan/agent/service/runtime/RuntimeContractTest.java`、`agent-runtime/tests/contract/test_runtime_openapi.py` |
| `TEST-ACCESS-003` | Spring 预算/容量：`AgentQueryApplicationServiceTest.java`、`AgentRequestLimiterTest.java` |
| `TEST-ACCESS-004` | 接入 E2E：`agent-service/src/test/java/com/dylan/agent/service/e2e/AgentAccessE2ETest.java` |
| `TEST-ACCESS-005` | Python API、版本、未知字段与大小限制：`agent-runtime/tests/api` |
| `TEST-ACCESS-006` | Runtime 并发、断连、取消、lease 释放：`agent-runtime/tests/api` |
| `TEST-ACCESS-007` | 认证、401/403 和零泄漏：`agent-service/src/test/java/com/dylan/agent/service/security/AgentSecurityContractTest.java` |
| `TEST-ACCESS-008` | 三能力系统 E2E：`agent-service/src/test/java/com/dylan/agent/service/e2e/AgentSystemE2ETest.java` |

### 14.2 验证编号定义

| 验证编号 | 命令/判定 |
|---|---|
| `VAL-ACCESS-001` | `mvn -pl agent-service -am test` 通过 |
| `VAL-ACCESS-002` | Java Runtime contract 与 Python API contract 全部通过，未知字段和版本漂移失败关闭 |
| `VAL-ACCESS-003` | `pytest agent-runtime/tests/api agent-runtime/tests/integration/api` 及 strict mypy 通过 |
| `VAL-ACCESS-004` | 系统 E2E 中 Spring 仅一次 Runtime 调用，失败映射、日志扫描和默认 stub 模型符合约束 |

## 15. 风险与保护条件

| 风险 | 触发场景 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 双重编排 | Spring 根据能力 ID 再路由 | Controller/ApplicationService 不含域分支；架构测试 | 否 |
| JWT 泄漏 | DTO、日志或异常包含 token | opaque wrapper、日志断言、响应最小化 | 否 |
| 预算漂移 | 两侧各自重新计算并延长时限 | epoch deadline 与 remaining 取最小值 | 否 |
| 无界并发 | 等待队列或 lease 未释放 | 两侧 fail-fast limiter 与 finally | 否 |
| 生产拓扑变化 | Runtime 不再同机 loopback | 必须另行完成网络信任与部署设计 | 需授权，但不阻塞当前实现依据 |

## 16. 实施依据与回滚判定

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前 v1.0 可作为该切片实现与代码评审依据 |
| 当前允许实施范围 | Spring 公共接入、Runtime 内部 API、跨语言契约、预算/取消/容量、健康和测试 |
| 当前禁止动作 | 新公共能力字段、Gateway 正式路由、生产部署、领域语义、重试熔断和持久化 |
| 回滚单位 | `agent-service` 接入切片与 `agent-runtime/api` 内部协议必须按兼容版本共同回滚 |

## 17. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 责任、接口、来源和上位追踪一致 | Passed |
| 内审 2 | 失败、安全、预算、状态和数据生命周期一致 | Passed |
| 内审 3 | 实现落点、测试、链接和可读性检查通过 | Passed |
| 独立评审 | `REV-L2-00-00-001` 已修复；公共/内部字段、上位约束、实现落点与验证闭环一致 | Passed |

- 当前版本：v1.0。
- 文档状态：Approved。
- 新版本不继承旧版修订流水；旧版只作为来源和审计档案。
