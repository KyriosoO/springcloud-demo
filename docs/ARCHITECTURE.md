# serviceCenter 微服务架构文档

> 项目：serviceCenter (com.dylan) **|** 版本：0.0.1-SNAPSHOT
> 技术栈：Spring Boot 3.5.10 + Spring Cloud 2025.0.1 + Java 25
> 更新日期：2026-06-17 **|** 基于当前源码

---

## 1. 项目总览

### 1.1 技术栈

| 类别 | 选型 | 版本 |
|------|------|------|
| 运行时 | Java | 25 |
| 框架 | Spring Boot / Spring Cloud | 3.5.10 / 2025.0.1 |
| 注册发现 | Netflix Eureka | - |
| 配置中心 | Spring Cloud Config (native) | - |
| API 网关 | Spring Cloud Gateway (WebFlux) | - |
| 声明式调用 | Spring Cloud OpenFeign | - |
| 容错降级 | Resilience4j + Sentinel | 1.8.9 |
| 安全 | Spring Security OAuth2 Resource Server + JWT | - |
| ORM | MyBatis | 3.0.3 |
| 缓存/锁 | Redis + Redisson | 3.52.0 |
| 搜索引擎 | Elasticsearch (Low Level RestClient) | - |
| 消息队列 | Apache Kafka + Apache RocketMQ | - |
| 高性能队列 | LMAX Disruptor | 4.0.0 |
| 序列化 | Jackson JSON + Kryo | 5.6.2 |
| WebSocket | Spring WebFlux Reactive | - |
| AI 嵌入 | BGE / OpenAI 兼容 API | bge-m3 / 1024d |

### 1.2 父 POM 管理的子模块（21 个）

```
serviceCenter (pom) ─── 统一管理版本号与依赖
 ├── workflow-api          # 工作流 DTO 契约
 ├── es-query-api          # ES 查询 DTO 契约
 ├── order-api             # 订单 DTO 契约
 ├── transaction-api       # 交易 DTO 契约
 ├── common-security       # 公共安全模块
 ├── common-db             # 公共数据库批量操作
 ├── common-redis          # 公共 Redis + Redisson
 ├── common-kafka          # 公共 Kafka 封装
 ├── common-ws             # 公共 WebSocket 模块
 ├── eureka-service        # 服务注册中心
 ├── config-service        # 配置中心
 ├── gateway-service       # API 网关
 ├── auth-service          # 认证授权服务
 ├── m-service-1           # 最小化微服务实例1
 ├── m-service-2           # 最小化微服务实例2
 ├── openfeign-service     # Feign 聚合调用服务
 ├── mq-procedure-service  # 消息生产者服务
 ├── mq-consumer-service   # 消息消费者服务
 ├── employee-service      # 员工主数据服务
 ├── es-query-service      # ES 查询服务
 └── workflow-service      # 工作流引擎服务
```

> serviceProvider 目录存在，但仅有 Eclipse 骨架（无 pom.xml、无 Java 源码），未被纳入 Maven 构建。

---

## 2. 分层架构

### 2.1 五层逻辑架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                       1. 基础设施层                                   │
│   eureka-service (8761)    config-service (9888)    gateway-service (8888) │
├─────────────────────────────────────────────────────────────────────┤
│                       2. 公共服务层                                   │
│   common-security   common-redis   common-kafka   common-db   common-ws │
├─────────────────────────────────────────────────────────────────────┤
│                       3. API 契约层                                   │
│   es-query-api     workflow-api     order-api     transaction-api    │
├─────────────────────────────────────────────────────────────────────┤
│                       4. 业务服务层                                   │
│   auth-service (8090)           openfeign-service (9000)             │
│   employee-service (9210)        workflow-service (9100)             │
│   es-query-service (9201)       mq-procedure-service (8182)          │
│   mq-consumer-service (8183)                                         │
├─────────────────────────────────────────────────────────────────────┤
│                       5. Demo / 辅助                                  │
│   m-service-1 (8180)     m-service-2 (8081)     serviceProvider (空)  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 调用依赖关系图

```
                        eureka-service (注册中心)
                              ↑ (所有服务注册)
                              │
                       gateway-service (统一入口 :8888)
                              │
        ┌─────────────┬───────┼───────────┬──────────┬──────────┐
        │             │       │           │          │          │
        ↓             ↓       ↓           ↓          ↓          ↓
  auth-service  openfeign  employee  workflow  mq-procedure  [agent]
    (8090)      (9000)    (9210)     (9100)     (8182)      (规划中)
        │          │          │          │          │
        │          │          │ Feign    │ Kafka    │ RMQ/Kafka
        │          │          ├──────────┤          │
        │          │          ↓          ↓          ↓
        │          │    es-query(9201)          mq-consumer(8183)
        │          │       (ES)                   (库存+交易)
        │          │
        └──────────┼─────── Feign 调用 ──────────┘
                   │
            m-service-1/2 (负载均衡验证)
```

---

## 3. 基础设施层

### 3.1 eureka-service — 服务注册中心

**端口** 8761 | **启动类** @EnableEurekaServer

单节点 Eureka Server，所有微服务向其注册。不注册自身、不拉取注册表。开启自我保护。

| Bean/配置 | 说明 |
|-----------|------|
| `register-with-eureka: false` | 不向自身注册 |
| `fetch-registry: false` | 不拉取 peer |
| `enable-self-preservation: true` | 自我保护开启 |

### 3.2 config-service — 配置中心

**端口** 9888 | **启动类** @EnableConfigServer + @EnableDiscoveryClient

Native 模式从 `classpath:/config` 加载配置文件，向 Eureka 注册自身供其他服务发现。

**管理的配置文件**（`src/main/resources/config/`）：

| 文件 | Profile | 内容要点 |
|------|---------|----------|
| `application-datasource.yml` | datasource | MySQL localhost:3306/springboot_db, 用户 root |
| `application-redis.yml` | redis | Redis 127.0.0.1:6379, 密码 123456, 库 0 |
| `application-es.yml` | es | Elasticsearch 127.0.0.1:9200, 连接/套接字超时 |
| `application-emp.yml` | emp | Kafka localhost:9092, ES 索引 employee, Embedding bge-m3/1024d |

### 3.3 gateway-service — API 网关

**端口** 8888 | **启动类** @EnableDiscoveryClient

基于 Spring Cloud Gateway (WebFlux) 的统一入口，负责路由转发、JWT 鉴权、Token 透传、Sentinel 限流。

**路由表（GatewayRouter 定义）**：

| 路由 ID | 匹配路径 | 目标 (lb://) | 说明 |
|----------|---------|-------------|------|
| hello_route | /test, /api/**, /orders/** | openfeign-service | 聚合调用 |
| ws_route | /ws/** | mq-procedure-service | WebSocket |
| auth_route | /login, /login.html, /home.html, /as/** | auth-service | 认证 |
| direct_route | /index | m-service | 多实例验证 |
| mq_route | /txn/** | mq-procedure-service | 交易/订单 |
| emp | /employees/**, /employee-workflow.html, /employee-es.html | employee-service | 员工 |
| workflow | /workflows/** | workflow-service | 工作流 |
| agent | /agent/** | agent-service | Agent (路由已配，服务待实现) |

**安全过滤器链**（GatewaySecurityConfig）：

- 白名单放行：/login, /login.html, /home.html, /css/**, /js/**
- `authTokenFilter`（@Order MIN_VALUE）：优先从 Cookie `AUTH_TOKEN` 提取 JWT，缺失时回退读取 `Authorization: Bearer <token>` → 校验 → 转写 Authorization Header + X-USER-ID Header 透传到下游
- `authTokenFilter` 对缺失或非法 token 沿用浏览器登录重定向到 `/login.html`；Security 异常处理器对 401/403 返回 JSON，500 由全局异常处理器返回 JSON
- CSRF 禁用

**Sentinel 限流规则**：hello_route / auth_route / direct_route，10s 窗口内 5 QPS，突发 5。

---

## 4. 公共服务层

### 4.1 common-security — 安全模块

为所有微服务提供统一的 JWT 认证授权能力。使用 HS256 对称密钥，同时支持 Servlet 和 Reactive 两种 Web 栈。

| 类 | 职责 |
|---|------|
| `JwtConfig` | 注册 SecretKey、JwtEncoder、JwtDecoder，均为 @AutoConfiguration |
| `ResourceServerSecurityAutoConfiguration` | Servlet 环境：禁用 CSRF，所有请求需认证 |
| `ReactiveResourceServerSecurityAutoConfiguration` | Reactive 环境：放行 /ws/**，其余需认证 |
| `FeignTokenRelayAutoConfiguration` | Feign 调用时自动从 SecurityContext 提取用户 JWT 写入 Authorization；无用户上下文时签发短时效 Service Token |
| `ServiceTokenProvider` | 签发 300s 短时效服务间调用 Token，含 `token_type: service` claim，提前 30s 刷新 |
| `SecurityTokenUtils` | 工具类，判断 token 类型（user/service） |

**自动配置导入**（`META-INF/spring/...AutoConfiguration.imports`）：
JwtConfig → ResourceServerSecurityAutoConfiguration → ReactiveResourceServerSecurityAutoConfiguration → FeignTokenRelayAutoConfiguration

### 4.2 common-redis — Redis 模块

封装 Spring Data Redis + Redisson，提供通用 Redis 操作、分布式锁、序列号生成。

| 类 | 职责 |
|---|------|
| `RedisConfig` | 注册 RedisTemplate（String 序列化 key，JSON 序列化 value）和 RedissonClient（单机模式） |
| `RedisService` | 全能 Redis 操作：Key/Value/Hash/List/Set/SortedSet、批量、Scan、Lua 原子脚本、Bloom Filter、全局自增 |
| `@DistributedLock` + `DistributedLockAspect` | AOP 声明式分布式锁，支持 SpEL 动态 key，底层 Redisson RLock.tryLock() |
| `RedisLockService` | 手动编程式锁（setIfAbsent + Lua 解锁） |
| `SeqNoGenerator` | 批量序列号分配 + Bloom Filter 去重全局序列 |

### 4.3 common-kafka — Kafka 模块

提供两套独立的 Kafka 基础设施：

| 模式 | 序列化 | Bean 名称 | 适用场景 |
|------|--------|-----------|----------|
| Object 模式 | JSON | objectKafkaTemplate | 通用开发 |
| Bytes 模式 | Kryo → byte[] | byteKafkaTemplate | 高性能/大数据量 |

两套模式均包含：手动 ACK、批量消费、DLT 死信重试（失败写入 `-DLT` topic，间隔 2s 重试 3 次）。

`KryoUtils`：ThreadLocal Kryo 实例，线程安全的高性能序列化工具。

### 4.4 common-db — 数据库模块

`DBBatchExecutor`：MyBatis BATCH 模式批量执行器，泛型支持任意 Mapper，默认每 100 条 flush。

### 4.5 common-ws — WebSocket 模块

基于 WebFlux Reactive WebSocket，提供统一实时通信。

| 类 | 职责 |
|---|------|
| `CommonWebSocketHandler` | 连接认证（JWT 从 Header/Cookie 提取）→ 提取 userId → ConcurrentHashMap 存储 → 异步消息处理 |
| `WsSender` | 按 userId 推送泛型 WsMessage<T> JSON |
| `CookieAuthWebSocketHandler` | 装饰器，在真实 handler 前完成 Token 提取 |

---

## 5. API 契约层

四个纯 POJO 模块，不含业务逻辑和 Feign 接口定义。Feign 接口驻留在消费方模块中。

### 5.1 es-query-api（9 个类）

| 类 | 说明 |
|----|------|
| SearchFilter | 搜索过滤（field, operator, value, values[]） |
| SearchRequest | 关键词搜索（keyword, from, size, filters[]） |
| SemanticSearchRequest | 语义搜索（embeddingField, queryText, queryVector, dims, k, numCandidates） |
| VectorSearchRequest | 向量检索（embeddingField, queryVector, k, numCandidates） |
| IndexDocumentRequest | 单文档索引（id, document Map） |
| BulkIndexRequest | 批量索引（idField, documents List） |
| RebuildRequest | 重建请求（sourceUrl, targetIndex, idField, cursor, since, batchSize, indexDefinition, sourceParams） |
| RebuildTask | 重建任务状态（taskId, status, totalIndexed, lastCursor, errorMessage, 时间戳） |
| SourcePageResponse | 源数据分页（documents[], hasMore, nextCursor） |

### 5.2 workflow-api（12 个类 — 4 枚举 + 8 DTO）

**枚举**：

| 枚举 | 值 |
|------|-----|
| WorkflowActionType | SUBMIT, APPROVE, REJECT |
| WorkflowApprovalType | SINGLE（普通）, COUNTERSIGN（会签）, OR_SIGN（或签） |
| WorkflowNodeStatus | PENDING, APPROVED, REJECTED |
| WorkflowStatus | SUBMITTED, APPROVED, REJECTED |

**DTO**：

| DTO | 主要字段 / 职责 |
|-----|----------------|
| WorkflowRequest | 创建流程实例请求：domain、operationType、businessId、payload、submitAction、operator。domain 表示业务域，operationType 表示业务域内的操作类型，当前流程定义键由 `domain + "-" + operationType` 组合得到 |
| WorkflowSubmitResponse | 创建流程实例响应：processId |
| WorkflowDetailResponse | 流程实例详情：processId、domain、businessId、status、operator、payload、currentNodeIndex、currentNodeId、nodes[]。详情接口表达流程实例视图，不应作为当前用户待办定位的唯一来源 |
| WorkflowTodoResponse | 当前用户待办列表项：todoId、processId、domain、operationType、businessId、status、payload、currentNodeIndex、currentNodeId、currentNodeName。todoId 由 workflow-service 生成，是面向 operator 的待办引用 |
| WorkflowActionMessage | 工作流动作事件体：eventId、actionName、processId、domain、businessId、actionType、payload、operator |
| WorkflowNodeDefinition | 提交流程时的节点配置：nodeId、nodeName、approvalType、approvers、approveAction、rejectAction |
| WorkflowOperationRequest | 审批/驳回操作请求：operator、todoId（可选）。携带 todoId 时用于校验待办仍匹配当前 operator 和当前节点 |
| WorkflowNodeDetailResponse | 流程节点详情：nodeId、nodeName、approvalType、status、approvers、approvedOperators、rejectedOperators |

### 5.3 order-api（4 个类 — 1 枚举 + 3 DTO）

| 类 | 说明 |
|----|------|
| OrderMessage | 订单消息（orderId, userId, productId, quantity, orderStatus, amount, createdAt），含 copyForAsync() 深拷贝方法支持 Disruptor 跨线程传递 |
| OrderResult | 订单结果（orderId, status, reason） |
| OrderStatus | PEDDING / UNPAID / PAID / CLOSED / REFUND / FAIL |
| Stock | 库存（key, value） |

### 5.4 transaction-api（5 个类 — 无枚举）

| 类 | 说明 |
|----|------|
| Transaction | 交易实体（transId, transType, transDate, amount） |
| TransactionLog | 交易日志（transId, seqNo, payload, createdAt），重写 equals/hashCode |
| TransactionLogArchive | 归档日志（transId, seqNo, payload, processedAt） |
| AggregateRequest | 聚合请求（condition, groupBy[], metrics[] — 支持 MAX/MIN/SUM/AVG/COUNT） |
| TransactionEvent | Disruptor RingBuffer 事件包装器（含 set/get） |

**跨模块引用**：四个 API 模块彼此独立，无交叉依赖，均仅继承父 POM。

---

## 6. 业务服务层

### 6.1 auth-service — 认证授权服务

端口 8090 | 无数据库 | 内存硬编码用户

**端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /login | 接收 userId+password → 签发 JWT → HttpOnly Cookie 返回 |
| GET | /public/test | 白名单测试 |
| GET | /as/getUserId | 从 SecurityContext 获取当前用户 ID |
| GET | /as/my | 返回 "Hello" + 当前用户 ID |

**JWT Claims**：sub=userId, iat, exp(1h), role。admin/dylan 拥有 agent:admin+agent:viewer，viewer_t 拥有 agent:viewer。

**Service**：`JwtService`（JWT 生成/校验/提取）、`UserService`（实现 UserDetailsService，仅支持 admin/123456）。

**安全配置**：/login、/login.html、/css/**、/js/**、/public/** 放行；其余需认证。使用 common-security 的 `JwtResourceServerHttpSecurity.applyDefaults()`。

### 6.2 employee-service — 员工主数据服务

端口 9210 | Profile: datasource,emp | MyBatis + MySQL + Feign + Kafka

**核心功能**：员工 CRUD、变更请求审批模型、ES 全文/向量搜索、索引同步。所有 CUD 操作通过 ChangeRequest 模型经审批后生效。

**端点**：

| 分类 | 方法 | 路径 | 说明 |
|------|------|------|------|
| CRUD | GET/POST | /employees | 分页查询 / 创建（需审批） |
| | GET/PUT/DELETE | /employees/{idCardNo} | 详情 / 更新（需审批） / 删除 |
| | GET | /employees/change-requests/{id} | 变更申请详情 |
| | GET | /employees/count | 总数统计 |
| ES 搜索 | POST | /employees/es/search | 关键词全文搜索（multi_match+filter） |
| | POST | /employees/es/vector-search | 语义向量搜索 |
| ES 管理 | POST/DELETE | /employees/es/documents/{id} | 单条索引/删除 |
| | POST | /employees/es/bulk | 批量索引 |
| | POST | /employees/es/rebuild/full | 全量索引重建 |
| | POST | /employees/es/rebuild/incremental | 增量索引重建 |
| | GET | /employees/es/rebuild/tasks/{id} | 重建任务查询 |
| | GET | /employees/es/rebuild/tasks | 所有重建任务 |
| 数据源 | GET | /internal/es/employees | 为 es-query-service 提供分页源数据 |

**Service 层**：

| 类 | 职责 |
|---|------|
| EmployeeService | CRUD 编排、ChangeRequest 管理、审批提交/回调处理、ES 文档转换、源数据分页 |
| EmployeeEsService | ES 操作编排（Feign 调用 es-query-service）、DSL 构建、索引 mapping 定义 |
| EmployeeEmbeddingService | 向量嵌入：BGE (bge-m3/1024d) 和 OpenAI 兼容双模式 |

**Feign 客户端**：

| 接口 | 目标服务 | 路径 |
|------|---------|------|
| EsQueryClient | es-query-service | /es |
| WorkflowClient | workflow-service | /workflows |

**消息消费者**：

| 消费者 | Topic | 用途 |
|--------|-------|------|
| EmployeeChangeEventConsumer | employee-change-topic | 监听变更事件同步 ES |
| WorkflowActionEventConsumer | workflow-action-topic | 接收审批结果写入 Inbox |
| WorkflowInboxProcessor (@Scheduled) | - | 定时重放 Inbox 失败事件 |

**Mapper**：EmployeeMapper（MyBatis 注解式，58 字段，selectPage/selectByIdCardNo/selectSourcePage/countAll/countSource/insert/update/delete）

**员工审批持久化**：

| 对象 | 存储 | 说明 |
|---|---|---|
| employee_change_request | MySQL | 员工创建/更新变更申请，保存 action/status/idCardNo/employee_json/applicant/approvalProcessId |
| employee_workflow_inbox_message | MySQL | 工作流审批动作 Inbox，按 eventId 幂等接收并通过状态机重放处理 |

### 6.3 workflow-service — 工作流引擎

端口 9100 | Profile: datasource | MyBatis + MySQL

**核心功能**：轻量级工作流引擎，支持按 `domain + operationType` 选择流程定义、实例创建、会签/或签、当前用户待办查询、动作分发（Outbox + Kafka）。

**端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /workflows | 提交流程实例，入参使用 domain + operationType 定位流程定义 |
| POST | /workflows/{processId}/approve | 审批通过当前节点；请求体包含 operator，可选携带 todoId 做当前待办校验 |
| POST | /workflows/{processId}/reject | 审批拒绝（终止流程）；请求体包含 operator，可选携带 todoId 做当前待办校验 |
| GET | /workflows/{processId} | 流程详情（含节点状态），按 processId 查询流程实例 |
| GET | /workflows/todos?operator= | 当前 operator 的待审批列表，返回 operator 视角的 todoId |
| GET | /workflows/todos/{todoId}?operator= | 按 todoId 回查当前 operator 的待办；待办已流转、已处理或 operator 不匹配时返回 409 TODO_CHANGED |

**引擎组件**：

| 类 | 职责 |
|---|------|
| WorkflowEngine | 核心：submit→approve→推进→终态，支持 SINGLE/COUNTERSIGN/OR_SIGN 三种审批策略 |
| WorkflowTodoIdCodec | 生成/解析 `td1_` 前缀的 URL-safe 待办引用，token 仅由 workflow-service 使用 |
| WorkflowActionService | Outbox 异步分发：先写 Outbox → Kafka 投递 → @Scheduled 每 5s 重试失败 |
| WorkflowActionDispatchChain | 责任链分发（log + kafka） |
| KafkaWorkflowActionDispatcher | 通过 Kafka（Kryo 序列化）发送审批结果事件 |

**预定义流程**：TWO_LEVEL_COUNTERSIGN（提交→审核1会签→审核2会签）、ONE_LEVEL_OR_SIGN、EMPLOYEE_CREATE、EMPLOYEE_UPDATE。员工场景当前使用 `employee-create` / `employee-update` 作为流程定义键，对应请求中的 `domain=employee`、`operationType=create/update`。

**Repository / Mapper**：

| 组件 | 存储 | 说明 |
|---|---|---|
| WorkflowDefinitionRepository | 内存 Map | 当前仍以内置流程定义维护流程定义键与节点配置，定义键由 `domain + "-" + operationType` 组合得到 |
| WorkflowInstanceRepository + WorkflowInstanceMapper | MySQL `workflow_instance` | 持久化流程实例、节点状态、payload、当前节点 |
| WorkflowOutboxRepository + WorkflowOutboxEventMapper | MySQL `workflow_outbox_event` | 持久化待投递/失败/已投递的工作流动作事件 |

**待办标识**：`todoId` 由 workflow-service 在 `/workflows/todos?operator=` 响应中生成，用于前端或 Agent 在多轮交互中引用待办。它是 workflow-service 私有的非持久化、不透明 URL-safe token，当前实现编码 `processId/currentNodeIndex/currentNodeId/operator`，外部系统不得自行解析。只有 `todoId` 时应调用 `GET /workflows/todos/{todoId}?operator=` 回查当前待办；审批/驳回时可在 `WorkflowOperationRequest.todoId` 中原样传回，由 workflow-service 在同一写入事务前校验流程、节点和 operator 是否仍匹配。待办已流转、已处理或 operator 不匹配时返回 `409 TODO_CHANGED`。


### 6.4 es-query-service — Elasticsearch 查询服务

端口 9201 | Profile: es | Low Level RestClient

**核心功能**：ES 索引/查询统一抽象层，封装文档 CRUD、全文搜索、向量检索、异步索引重建。

**端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /es/indexes/{index}/search | 执行 DSL 查询 |
| PUT | /es/indexes/{index}/documents | 索引单文档 |
| DELETE | /es/indexes/{index}/documents/{id} | 删除单文档 |
| POST | /es/indexes/{index}/bulk | 批量索引（NDJSON） |
| POST | /es/indexes/{index}/rebuild/full | 全量异步重建 |
| POST | /es/indexes/{index}/rebuild/incremental | 增量异步重建 |
| GET | /es/rebuild/tasks/{taskId} | 任务状态 |
| GET | /es/rebuild/tasks | 全部任务 |
| POST | /es/indexes/{index}/vector-search | KNN 向量检索 |

**Service**：`EsDocumentService`（RestClient 封装）、`IndexRebuildService`（异步分页拉取→重建索引→批量写入）、`RebuildTaskRepository`（任务状态管理）。

重建时序：收到重建请求 → recreateIndex（DELETE+PUT with mapping）→ 循环 RestTemplate 拉取 sourceUrl 分页数据 → 逐批 bulkIndex → 状态 SUBMITTED→RUNNING→SUCCESS/FAILED

### 6.5 openfeign-service — Feign 聚合调用服务

端口 9000 | Resilience4j 容错

**核心功能**：聚合调用下游服务，集成 Resilience4j 限流/重试/熔断，透传认证信息。

**端点**：

| 方法 | 路径 | 代理目标 | 说明 |
|------|------|----------|------|
| GET | /test?user= | m-service:/index | 负载均衡验证 |
| GET | /api/my | auth-service:/as/my | 认证测试 |
| GET | /api/getUserId | auth-service:/as/getUserId | 认证测试 |
| POST | /orders/create | mq-procedure-service:/orders/create | 下单 |
| POST | /orders/mqTest | mq-procedure-service:/orders/mqTest | 消息测试 |

**Feign 客户端**：AsFeignClient → auth-service、IndexFeignClient → m-service、MQProducerClient → mq-procedure-service

**容错配置**（FeignConfig）：

| 机制 | 参数 |
|------|------|
| 限流 | 5s 窗口内 50 次 |
| 重试 | 3 次，间隔 500ms |
| 熔断 | 滑动窗口 100，失败率 >20% 开启，半开等待 5s |
| 超时 | 连接 2s，读取 5s |

装饰链顺序：RateLimiter → Retry → CircuitBreaker。`DecoratorService` 统一编排所有 Feign 调用并提供 fallback。

**认证透传**：`FeignAuthInterceptor` 从 RequestContextHolder 提取 Authorization Header 注入 Feign 请求。

### 6.6 mq-procedure-service — 消息生产者服务

端口 8182 | WebFlux Reactive | Profile: redis,datasource

**核心功能**：订单/交易的生产者，支持 RocketMQ + Kafka 双通道 + Disruptor 秒杀优化 + WebSocket 实时推送。

**订单端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /orders/create | 创建订单（userId/productId/quantity/amount） |
| POST | /orders/mqTest | 测试 RocketMQ 事务消息 |

**交易端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /txn | 直接创建交易 |
| GET/PUT/DELETE | /txn/{transId} | 查询/更新/删除交易 |
| POST | /txn/query | 条件查询 |
| POST | /txn/aggregate | 动态聚合统计（groupBy + MAX/MIN/SUM/AVG/COUNT） |
| POST | /txn/txnmq | 通过 RocketMQ 批量测试 |
| POST | /txn/txnkafka | 通过 Kafka 批量测试 |

**订单处理双路径**：

```
下单请求
  ├── Disruptor 可用 → RingBuffer 零 GC 异步 → Redis 暂存 → RocketMQ 事务消息
  └── Disruptor 不可用 → 直接创建 → Redis 暂存 → RocketMQ 事务消息

反馈 → OrderStockFeedbackConsumer (RocketMQ)
  ├── UNPAID → Redis TTL → RocketMQ 延迟消息 → order-topic:timeout
  └── 其他状态 → 直接完结

超时 → OrderTimeoutMQListener → CLOSED → order-topic:rollback
```

**分布式锁**：@DistributedLock 保护 userId:productId（防超卖）和 orderId 操作。

**消息消费者**（在本模块）：

| 消费者 | Topic/Tag | 用途 |
|--------|-----------|------|
| OrderStockFeedbackConsumer | order-topic:feedback | 接收库存扣减反馈 |
| OrderTimeoutMQListener | order-topic:timeout | 超时关闭 |
| OrderTransactionListener | @RocketMQTransactionListener | 本地事务执行+回查 |

**Service**：OrderService（订单生命周期）、TransactionService（交易 CRUD + 动态聚合）、TransactionOperMQProducer/KafkaProducer（双通道投递）

**WebSocket**：MqProcedureWsSender + OrderWebSocketHandler + TransWebSocketHandler 实时推送

### 6.7 mq-consumer-service — 消息消费者服务

端口 8183 | Spring MVC | Profile: redis,datasource | 纯消费者（无 Controller）

**核心功能**：消费 RocketMQ/Kafka 消息，执行库存操作（Redis Lua 原子脚本）和交易日志批量落库。

**消息消费者**：

| 消费者 | Topic/Tag | 序列化 | 用途 |
|--------|-----------|--------|------|
| OrderCreateConsumer | order-topic:create (RocketMQ) | Kryo→OrderMessage | 扣减库存，反馈结果 |
| OrderRollbackConsumer | order-topic:rollback (RocketMQ) | Kryo→OrderMessage | 恢复库存 |
| TransactionOperMQConsumer | transaction-topic (RocketMQ, 顺序消费) | - | 批量落库 TransactionLog |
| TransactionOperKafkaConsumer | transaction-topic (Kafka, byte[]) | Kryo | 批量落库 TransactionLog |
| TxConsumer | order-topic:txTest | - | 测试消费 |

**库存操作**（StockOperService — Redis Lua 原子脚本）：

```
deductStock Lua 五步：幂等检查 → 存在性检查 → 库存充足 → DECRBY → 标记已处理(TTL 3600s)
increaseStock Lua 同理反向操作
```

**批量落库**（TransBatchService）：

```
flushBatch 事务流程：
  SeqNoGenerator 分配 seq_no → 排序 → 批量 insert TransactionLog
  → 区分新增/编辑 → insert/update Transaction → 归档 TransactionLogArchive
  → 清理日志表 → 删除 Redis 脏标记
异常时：TransExceptionLogService 独立事务(REQUIRES_NEW)保存异常日志
```

**Mapper**：TransactionMapper（insert/update Transaction）、TransactionLogMapper（save/fetchNew/clear/saveException）、TransactionLogArchiveMapper（save 归档）

---

## 7. 核心调用链路

### 7.1 员工创建审批链

```
浏览器 → Gateway(:8888) → employee-service(:9210) POST /employees
  ├── EmployeeController.create() → EmployeeService
  │     ├── 创建 EmployeeChangeRequest (PENDING_APPROVAL)
  │     ├── Feign → workflow-service(:9100) POST /workflows
  │     │     ├── WorkflowRequest(domain=employee, operationType=create/update, businessId=changeRequestId)
  │     │     ├── WorkflowEngine.submit() → 创建实例
  │     │     └── WorkflowActionService (Outbox → Kafka workflow-action-topic)
  │     └── 返回 EmployeeChangeSubmitResponse (含 processId)
  │
  └── 审批 POST /workflows/{id}/approve → workflow-service
        ├── WorkflowEngine.approve() → 节点推进 / 流程结束
        └── Kafka → workflow-action-topic
              └── employee-service WorkflowActionEventConsumer
                    ├── 幂等检查 (eventId)
                    └── EmployeeService.processWorkflowInboxMessage()
                          ├── 应用变更 → EmployeeMapper.insert/update
                          └── Kafka → employee-change-topic → ES 同步
```

### 7.2 订单 Saga 分布式事务链

```
浏览器 → Gateway(:8888) → mq-procedure-service(:8182) POST /orders/create
  ├── @DistributedLock(userId:productId)
  ├── Disruptor RingBuffer / 直接路径 → Redis 暂存
  └── RocketMQ 事务消息 → order-topic:create

mq-consumer-service(:8183) OrderCreateConsumer
  ├── Kryo 反序列化 OrderMessage
  ├── StockOperService.deductStock() (Lua 原子扣减)
  └── RocketMQ → order-topic:feedback
        └── mq-procedure-service OrderStockFeedbackConsumer
              ├── SUCCESS → 订单 PAID
              ├── OUT_OF_STOCK → 订单 FAIL
              └── UNPAID → Redis TTL → RocketMQ 延迟消息 → order-topic:timeout

超时：mq-procedure-service OrderTimeoutMQListener
  └── 订单 → CLOSED → RocketMQ → order-topic:rollback
        └── mq-consumer-service OrderRollbackConsumer
              └── StockOperService.increaseStock() (Lua 原子恢复)
```

### 7.3 ES 全文搜索链

```
浏览器 → Gateway → employee-service(:9210) POST /employees/es/search
  ├── EmployeeEsService → 构建 DSL (multi_match + filter + prefix + wildcard)
  ├── EmployeeEmbeddingService (BGE bge-m3) → 可选向量查询
  └── Feign → es-query-service(:9201) POST /es/indexes/employee/search
        └── EsDocumentService.search() → Low Level RestClient → ES _search API
```

### 7.4 索引重建链

```
浏览器 → Gateway → employee-service(:9210) POST /employees/es/rebuild/full
  └── Feign → es-query-service(:9201) POST /es/indexes/employee/rebuild/full
        ├── RebuildTask (ACCEPTED)
        └── @Async IndexRebuildService
              ├── recreateIndex (DELETE + PUT with mapping)
              └── 循环 RestTemplate → GET localhost:9210/internal/es/employees?cursor=&batchSize=
                    └── 逐批 bulkIndex (NDJSON)
              └── 状态：SUBMITTED → RUNNING → SUCCESS/FAILED
```

### 7.5 服务间 Token 透传链

```
浏览器 Cookie AUTH_TOKEN 或 Authorization Bearer Header
  → GatewaySecurityConfig 提取 token
  → JwtDecoder 校验 → Authorization: Bearer <token> + X-USER-ID 透传给下游

下游服务：
  ├── 直接 HTTP：SecurityContextHolder 获取 JWT
  └── Feign 调用：FeignTokenRelayAutoConfiguration 拦截器
        ├── 有用户上下文 → 透传用户 Bearer Token
        └── 无用户上下文 → ServiceTokenProvider 签发短时 Service Token (HS256, token_type=service, 300s TTL)
```

---

## 8. 消息拓扑

### 8.1 Kafka Topics

| Topic | 生产者 | 消费者 | 序列化 | 用途 |
|-------|--------|--------|--------|------|
| workflow-action-topic | workflow-service | employee-service | Kryo byte[] | 审批动作分发 |
| employee-change-topic | employee-service | employee-service (自身) | JSON | ES 索引同步 |
| transaction-topic | mq-procedure-service | mq-consumer-service | Kryo byte[] | 交易日志批量落库 |

### 8.2 RocketMQ Topics

| Topic | Tag | 生产者 | 消费者 | 消费模式 | 用途 |
|-------|-----|--------|--------|---------|------|
| order-topic | :create | mq-procedure-service | mq-consumer-service | 集群 | 订单创建→扣库存 |
| order-topic | :feedback | mq-consumer-service | mq-procedure-service | 集群 | 库存扣减结果 |
| order-topic | :rollback | mq-procedure-service | mq-consumer-service | 集群 | 退库回滚 |
| order-topic | :timeout | mq-procedure-service | mq-procedure-service | 集群 | 延迟超时关闭 |
| order-topic | :txTest | mq-procedure-service | mq-consumer-service | 集群 | 事务消息测试 |
| transaction-topic | (无 Tag) | mq-procedure-service | mq-consumer-service | 顺序(ORDERLY) | 交易日志批量 |

---

## 9. 弹性与容错设计

| 层级 | 机制 | 实现 | 参数 |
|------|------|------|------|
| 网关 | Sentinel 限流 | SentinelGatewayFilter | 10s 窗口 / 5 QPS / 突发 5 |
| 网关路由 | 重试 | Retry GatewayFilter | 最多 3 次，仅 502 触发，退避 500ms |
| Feign 调用 | Resilience4j | DecoratorService 装饰链 | 限流→重试→熔断，各自独立配置 |
| 消息消费 | DLT 死信 | DefaultErrorHandler | FixedBackOff 2s×3，失败写入 {topic}-DLT |
| 并发控制 | 分布式锁 | @DistributedLock + RLock | Redisson tryLock，支持 SpEL 动态 key |
| 原子操作 | Redis Lua | StockOperService | 库存扣减/回退/幂等一体化原子执行 |
| 消息一致性 | Outbox | WorkflowActionService | 工作流动作写入 Outbox → Kafka 投递 → 定时重试失败事件 |
| Saga 事务 | 补偿操作 | OrderService 全链路 | 每步有对等回退（扣库存↔恢复、创建↔关闭） |

---

## 10. 外部系统依赖

| 系统 | 地址 | 使用方 | 用途 |
|------|------|--------|------|
| MySQL | localhost:3306/springboot_db | employee-service, workflow-service, mq-procedure-service, mq-consumer-service | 持久化 |
| Redis | localhost:6379 (密码 123456) | common-redis, mq-procedure-service, mq-consumer-service | 缓存/锁/库存 |
| Elasticsearch | localhost:9200 | es-query-service, employee-service | 全文/向量搜索 |
| Kafka | localhost:9092 | workflow-service, employee-service, mq-procedure-service, mq-consumer-service | 异步消息 |
| RocketMQ | localhost:9876 | mq-procedure-service, mq-consumer-service | 事务消息+顺序消息 |
| BGE Embedding | localhost:8908 | employee-service | 文本向量嵌入 (bge-m3/1024d) |

---

## 11. 安全架构

```
[网关层] GatewaySecurityConfig
  ├── Cookie AUTH_TOKEN 或 Authorization Bearer Header → JWT 校验 (HS256)
  ├── 白名单：/login, *.html, /css/**, /js/**
  ├── Sentinel 限流 (10s/5 QPS)
  ├── authTokenFilter 未取到/无法解析 token → /login.html
  └── Security 401/403 → JSON 响应

[服务层] common-security (Servlet / Reactive 自适应)
  ├── OAuth2 Resource Server JWT
  ├── 禁用 CSRF
  ├── Reactive 模式放行 /ws/**
  └── JwtResourceServerHttpSecurity.applyDefaults()

[Feign 调用链] FeignTokenRelayAutoConfiguration
  ├── 用户 Token：SecurityContext → Authorization Header
  └── 服务 Token：ServiceTokenProvider (HS256, 300s TTL, token_type=service)

[角色 RBAC]
  └── agent:admin / agent:viewer（JWT role claim，为 Agent 功能预埋）
```

---

## 12. Agent 能力现状

agent-api、agent-service 和 agent-runtime（Python LangGraph）模块当前未纳入代码树，也未加入 `serviceCenter/pom.xml` 的 Maven reactor。当前只有以下基础设施预留：

| 预埋点 | 位置 | 说明 |
|--------|------|------|
| 网关路由 | GatewayRouter.java | `/agent/**` → `lb://agent-service` |
| JWT 角色 | JwtService.java | agent:admin / agent:viewer |
| 前端入口 | home.html | "Agent Query" 按钮 |
| 向量嵌入 | EmployeeEmbeddingService | BGE (bge-m3/1024d) + OpenAI 兼容双模式 |

---

## 13. Demo 辅助模块

### 13.1 m-service-1 / m-service-2

两个共享 Eureka 服务名 `m-service` 的最小化实例，用于验证 Eureka 多实例负载均衡。

| 项目 | 端口 | 源码 |
|------|------|------|
| m-service-1 | 8180 | GET /index?user= → "user!! Hello World! from 8180" |
| m-service-2 | 8081 | GET /index?user= → "user!! Hello World! from 8081" |

### 13.2 serviceProvider

Eclipse 工程骨架（.project / .gitignore / .gitattributes / maven-wrapper.properties），无 pom.xml，无 Java 源码，未纳入 Maven 构建。
