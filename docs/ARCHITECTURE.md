# Codex Agent 系统架构文档

> 生成日期：2026-06-25 | 分支：codex
> 2026-07-05 更新：按授权补充 Agent QUERY 白名单排序架构边界；QUERY `sorts` 与 AGGREGATE `orderBy` 保持独立语义。
> 2026-07-06 更新：按授权补齐 AGGREGATE Runtime Context View 的 `orderBy` 投影说明；不改变 `AGGREGATE_CONTEXT` 版本或下游聚合接口。

---

## 1. 项目总览

项目根目录 `D:\codex` 是一个多模块 Maven 项目，父 POM 位于 `serviceCenter`（`com.dylan`，版本 `0.0.1-SNAPSHOT`）。技术栈：Spring Boot 3.5.10、Spring Cloud 2025.0.1、Java 25、MyBatis 3.0.3、MySQL。

### Maven 模块及其用途

| 模块 | 用途 |
|------|------|
| **serviceCenter** | 父 POM，依赖管理，packaging=pom |
| **agent-api** | 纯 DTO 模块——请求/响应类、枚举、plan spec、runtime schema。不参与 Spring Boot repackage |
| **agent-adapter-api** | 业务适配器 SPI 接口（QueryableAdapter、AggregatableAdapter）、校验后的查询对象、适配器异常 |
| **agent-adapter-employee** | 员工域的 QueryableAdapter + AggregatableAdapter 实现 |
| **agent-adapter-transaction** | 交易域的 QueryableAdapter + AggregatableAdapter 实现 |
| **agent-service** | 核心 Agent 编排引擎——控制器、能力路由、规划、持久化 |
| **agent-runtime** | LLM-based 规划服务（通过 REST 调用，可能独立部署） |
| **common-security** | 共享安全工具（JWT/Feign token 中继） |
| **common-db** | 共享数据库工具 |
| **common-kafka** | 共享 Kafka 基础设施 |
| **common-redis** | 共享 Redis/缓存基础设施 |
| **common-ws** | 共享 WebSocket 基础设施 |
| **config-service** | Spring Cloud Config 配置中心 |
| **eureka-service** | Netflix Eureka 服务注册中心 |
| **gateway-service** | Spring Cloud Gateway，处理 JWT 认证并路由至 agent-service |
| **auth-service** | 认证服务 |
| **employee-service** | 员工业务微服务（被适配器查询） |
| **transaction-api** | 交易域 API DTO |
| **workflow-api** | 工作流 API DTO |
| **workflow-service** | 工作流执行服务 |
| **docs** | 设计文档 |

### Agent 模块依赖关系

```
agent-adapter-api (SPI 接口)
       ├── agent-adapter-employee (实现 QueryableAdapter + AggregatableAdapter)
       ├── agent-adapter-transaction (实现 QueryableAdapter + AggregatableAdapter)
       └── agent-service (通过 Registry 消费适配器)

agent-api (DTO) ──→ agent-service (主要消费者)

agent-service ──→ agent-adapter-api, agent-adapter-employee, agent-adapter-transaction, common-security
```

---

## 2. agent-api 模块文件清单

**路径：** `agent-api/src/main/java/com/dylan/agent/api/`

### 枚举 (8)

| 文件 | 用途 |
|------|------|
| `enums/AgentIntent.java` | 顶层意图枚举：`QUERY`、`CLARIFY`、`AGGREGATE` |
| `enums/AgentResponseType.java` | 响应类型：`RESULT`、`CLARIFY`、`AGGREGATE_RESULT`、`ERROR` |
| `enums/AgentErrorCode.java` | 统一错误码：`AGENT_INVALID_REQUEST`、`AGENT_CONVERSATION_NOT_FOUND`、`AGENT_INTENT_FORBIDDEN`、`AGENT_FIELD_FORBIDDEN`、`AGENT_OPERATOR_FORBIDDEN`、`AGENT_PLAN_INVALID`、`AGENT_RUNTIME_UNAVAILABLE`、`AGENT_QUERY_FAILED`、`AGENT_INTERNAL_ERROR` |
| `enums/AgentOperator.java` | 查询操作符：`EQ`、`CONTAINS`、`CONTAINS_ANY`、`STARTS_WITH`、`STARTS_WITH_ANY`、`IN`、`GT`、`LT` |
| `enums/AgentFieldType.java` | 字段数据类型：`STRING`、`DECIMAL`、`INSTANT` |
| `enums/AggregateFunction.java` | 聚合函数：`COUNT`、`SUM`、`AVG`、`MIN`、`MAX` |
| `enums/QueryContextMode.java` | 查询上下文模式：`REPLACE`、`MERGE` |
| `enums/RuntimeRole.java` | 对话角色：`USER`、`ASSISTANT` |

### Plan Spec (7)

| 文件 | 用途 |
|------|------|
| `plan/AgentPlan.java` | Runtime 返回的根 Plan：含 `intent`、`planVersion`、`domain`，以及 `query`/`clarify`/`aggregate` 之一 |
| `plan/AgentQuerySpec.java` | QUERY plan：`filters`（最多 5），`selectFields`（最多 10），`sorts`（最多 2，字段必须来自白名单），`contextMode`，`removeFields`，`page`，`size` |
| `plan/AgentAggregateSpec.java` | AGGREGATE plan：`filters`、`metrics`（1-5）、`groupByFields`（最多 2）、`orderBy`、`maxRows`（1-100） |
| `plan/ClarifySpec.java` | CLARIFY plan：`question`（1-500 字符） |
| `plan/AgentFilter.java` | 查询过滤条件：`field`、`operator`、`value`（单值）、`values`（多值） |
| `plan/AgentSortSpec.java` | QUERY 明细排序条件：`field`、`direction`（ASC/DESC），只允许白名单字段 |
| `plan/AggregateMetricSpec.java` | 指标规格：`alias`（唯一）、`function`、`field`（COUNT 时为 null） |
| `plan/AggregateOrderSpec.java` | AGGREGATE 聚合结果排序规格：`field`、`direction`（ASC/DESC），字段来自 groupBy 或 metric alias |

### 请求/响应 DTO (10)

| 文件 | 用途 |
|------|------|
| `request/AgentChatRequest.java` | POST /agent/chat 请求：`conversationId`（可选）、`message`（必填，最长 2000） |
| `request/PlanGenerateRequest.java` | 发往 Runtime 的请求：`requestId`、`message`、`recentTurns`（最多 6）、`previousQuery`、`domainSchemas` |
| `response/AgentChatResponse.java` | 统一响应：`conversationId`、`turnId`、`type`、`message`、`summary`、`queryParameters`、`queryResult`、`aggregateResult`、`errorCode` |
| `response/AgentQueryResult.java` | 查询结果：`columns`、`rows`、`total`、`totalExact`、`page`、`size` |
| `response/AgentQueryParameters.java` | 前端展示的查询参数：`domain`、`filters`、`selectFields`、`sorts`、`page`、`size` |
| `response/AgentQueryFilterParameter.java` | 单个过滤参数：`field`、`operator`、`value`、`values` |
| `response/AgentAggregateResult.java` | 聚合结果：`domain`、`groupByFields`、`metricAliases`、`rows`、`partial` |
| `response/AgentAggregateRow.java` | 单行聚合结果：`groups` Map、`metrics` Map |
| `response/PlanGenerateResponse.java` | Runtime 响应：`requestId`、`plan`（可为 null 的 AgentPlan） |
| `response/RuntimeErrorResponse.java` | Runtime 错误：`code`、`message`、`requestId` |

### Runtime Schema DTO (5)

| 文件 | 用途 |
|------|------|
| `runtime/RuntimeTurn.java` | 供 Runtime 上下文的单轮对话：`role`、`content` |
| `runtime/RuntimeDomainSchema.java` | 发往 Runtime 的域 Schema：`domain`、`aliases`、`fields`、`defaultSelectFields`、`sortFields`、`maxFilters`、分页限制 |
| `runtime/RuntimeFieldSchema.java` | 字段 Schema：`name`、`aliases`、`operators`、`type`、`formatHint`、`supportedAggregateFunctions` |
| `runtime/RuntimeQueryContext.java` | 上一轮查询上下文（供 MERGE 使用）：`sourceTurnId`、`domain`、`filters`、`selectFields`、`sorts`、`page`、`size`、分页总数元数据 |
| `runtime/RuntimeAggregateContext.java` | 聚合查询上下文（供 Runtime 多轮聚合规划、持久化和审计）：`sourceTurnId`、`domain`、`filters`、`metrics`、`groupByFields`、`orderBy`、`maxRows` |

---

## 3. agent-service 模块结构

**路径：** `agent-service/src/main/java/com/dylan/agent/`

| 包 | 关键类 | 用途 |
|----|--------|------|
| `application/` | `AgentOrchestrator` | 主对话流程编排器 |
| `controller/` | `AgentChatController` | REST 端点 `/agent/chat` |
| `capability/` | `AgentCapabilityHandler`（接口）、`AgentCapabilityHandlerRegistry`、`CapabilityRouter`、`CapabilityRouteResolver`、`CapabilityExecutionContext`、`CapabilityValidationContext`、`CapabilityExecutionResult`、`CapabilityRiskLevel` | 意图路由与能力抽象 |
| `capability/query/` | `QueryCapabilityHandler`、`QueryPlanValidator`、`QueryMessages`、`QueryParameterMapper`、`QueryRuntimeContextFactory` | QUERY 意图处理器 |
| `capability/clarify/` | `ClarifyCapabilityHandler`、`ClarifyPlanValidator` | CLARIFY 意图处理器 |
| `capability/aggregate/` | `AggregateCapabilityHandler`、`AggregatePlanValidator`、`AggregateMessages` | AGGREGATE 意图处理器 |
| `capability/model/` | `ValidatedCapabilityPlan`、`ValidatedQueryPlan`、`ValidatedClarifyPlan`、`ValidatedAggregatePlan` | 校验后的 Plan 类型 |
| `client/` | `AgentRuntimeClient` | 发往 LLM Runtime 的 HTTP 客户端 |
| `config/` | `AgentConfiguration`、`AgentProperties`、`AgentPropertiesValidator` | Spring 配置 |
| `conversation/` | `ConversationService`、`ConversationHandle`、`TurnHandle`、`ConversationCleanupJob` | 对话/Turn 生命周期管理 |
| `exception/` | 8 个异常类 | 统一异常层次结构 |
| `mask/` | `FieldMasker`、`FieldMaskerRegistry`、`MobileFieldMasker`、`EmailFieldMasker`、`IdCardFieldMasker`、`AddressFieldMasker`、`NoneFieldMasker` | 数据脱敏 SPI + 实现 |
| `model/` | `AgentUserContext`、`ConversationStatus`、`TurnStatus`、`FieldPolicy`、`MaskType` | 内部领域模型 |
| `persistence/entity/` | `AgentConversationEntity`、`AgentTurnEntity` | 持久化实体 |
| `persistence/mapper/` | `AgentConversationMapper`、`AgentTurnMapper` | MyBatis Mapper |
| `planning/` | `RuntimeDomainSchemaFactory` | 从配置构建 Runtime 域 Schema |
| `planning/filter/` | `FilterNormalizer`、`FieldConstraintValidator`、`OperatorSemantics`、`FieldFilterSet`、`QueryMergeEngine` | 过滤条件校验与 MERGE 逻辑 |
| `result/` | `AgentResultProcessor`、`AggregateResultProcessor` | 结果处理（权限、脱敏） |
| `security/` | `AgentPermissionService`、`AgentUserContextResolver` | 授权 |
| `adapter/` | `QueryableAdapterRegistry`、`AggregatableAdapterRegistry` | 适配器 SPI 注册表 |

---

## 4. 完整请求流程：`/agent/chat`

### 步骤详解

**1. Controller**（`AgentChatController.java`）
- 接收 POST `/agent/chat`，请求体为 `AgentChatRequest`（conversationId + message）
- `@AuthenticationPrincipal Jwt` 从安全上下文中提取 JWT
- `AgentUserContextResolver.resolve(jwt)` 从 JWT claims 提取 userId 和 roles
- 委托给 `AgentOrchestrator.chat(userContext, request)`

**2. Orchestrator**（`AgentOrchestrator.java`）
- `permissionService.requireAgentAccess(userContext)` — 用户至少需要一个匹配任意 intent 角色的 role
- `normalizeMessage(message)` — 去空白，截断至 2000 字符
- `conversationService.openConversation(...)` — 加载已有或新建对话，返回 `ConversationHandle`
- `conversationService.startTurn(...)` — 创建状态为 `PROCESSING` 的新 turn，返回 `TurnHandle`
- `conversationService.loadRecentTurns(...)` — 加载最近 N 条成功 turn（USER + ASSISTANT 消息）作为 Runtime 上下文
- `conversationService.loadLatestQueryContext(...)` — 加载上一次成功 QUERY 的上下文，用于 MERGE 支持
- `schemaFactory.createAll()` — 从配置构建域 Schema 发给 Runtime
- 构建 `PlanGenerateRequest`
- `runtimeClient.generate(pgReq)` — 发送至 Runtime，返回 `PlanGenerateResponse`

**3. Runtime Client**（`AgentRuntimeClient.java`）
- 使用独立 `RestClient`（不转发用户 JWT）
- POST 至 `/runtime/v1/plans/generate`，Header 含 `X-Agent-Runtime-Key` 共享密钥
- 读取响应体（受 `maxResponseBytes` 限制）
- JSON 解析为 `PlanGenerateResponse`
- HTTP 状态码 + 错误码映射为类型化异常

**4. 意图解析**（`CapabilityRouteResolver.java`）
- 校验：response 非 null，plan 非 null，requestId 匹配，planVersion="1.0"，intent 非 null
- 返回 `AgentIntent`（QUERY、CLARIFY 或 AGGREGATE）

**5. 权限检查**（`AgentPermissionService.checkIntent()`）
- 验证用户角色包含 `intentRoles[intent]` 中至少一个角色

**6. 能力路由**（`CapabilityRouter.java`）
- `registry.getRequired(intent)` — 从 `EnumMap<AgentIntent, AgentCapabilityHandler<?>>` 中 O(1) 查找

**7. 校验阶段**（多态，每个 handler 独立实现）
- 创建 `CapabilityValidationContext(planResponse, turnId, previousQuery, userContext)`
- 调用 `handler.validate(validationContext)` — 返回 `ValidatedCapabilityPlan` 子类
- 每个 handler 委托给自己的 PlanValidator

**8. 执行阶段**（多态，每个 handler 独立实现）
- 创建 `CapabilityExecutionContext(conversationId, turnId, normalizedMessage, userContext, previousQuery)`
- 调用 `handler.execute(executionContext, plan)` — 返回 `CapabilityExecutionResult`

**9. Turn 完成**（`AgentOrchestrator.completeTurn()`）
- `conversationService.completeSuccess(turnId, intent, responseType, assistantMessage, contextToPersist)`
- CAS 更新：`SET status='SUCCEEDED' WHERE id=? AND status='PROCESSING'`
- 将 `contextToPersist` 序列化为 JSON 写入 `query_context_json` 列

**10. 响应构建**（`AgentOrchestrator.buildResponse()`）
- `result.applyTo(response)` — 将所有字段从 CapabilityExecutionResult 复制到 AgentChatResponse

**错误路径：**
- try 块中的任何 `AgentException` 或未检查异常：
  - `conversationService.completeFailure(turnId, errorCode, safeMessage)` — CAS 至 FAILED
  - 携带上下文（conversationId + turnId）重新抛出
- `AgentExceptionHandler`（@RestControllerAdvice）捕获所有异常，返回统一的 AgentChatResponse(type=ERROR)

---

## 5. 意图路由架构

### AgentIntent 枚举
三个值：`QUERY`、`CLARIFY`、`AGGREGATE`。定义在 `agent-api` 中。代表 LLM Runtime 确定的用户高层目标。

### CapabilityRouteResolver
**文件：** `agent-service/.../capability/CapabilityRouteResolver.java`

对 Runtime 响应进行信封校验：
- 响应和 plan 必须非 null
- `requestId` 必须匹配 turnId
- `planVersion` 必须为 `"1.0"`
- `intent` 必须非 null

不校验 domain、filter 形状或意图特有细节——这些交给 handler.validate()。

### CapabilityRouter
**文件：** `agent-service/.../capability/CapabilityRouter.java`

`AgentCapabilityHandlerRegistry` 上的薄门面。通过 O(1) EnumMap 查找将 `AgentIntent` 路由到正确的 handler。

### AgentCapabilityHandlerRegistry
**文件：** `agent-service/.../capability/AgentCapabilityHandlerRegistry.java`

构造时自动发现所有 `AgentCapabilityHandler` Spring Bean：
- 拒绝 null intent、重复 intent、空列表
- 构造后使用 `Map.copyOf` 冻结
- 提供 `getRequired(intent)` — intent 未找到时抛异常

### AgentCapabilityHandler 接口
**文件：** `agent-service/.../capability/AgentCapabilityHandler.java`

泛型接口 `AgentCapabilityHandler<P extends ValidatedCapabilityPlan>`：
- `intent()` — 返回此 handler 服务的 AgentIntent
- `riskLevel()` — READ_ONLY、CONFIRM_REQUIRED 或 HIGH_RISK_CONFIRM_REQUIRED
- `validate(CapabilityValidationContext) -> P` — 将原始 Runtime plan 转换为校验后的 plan
- `execute(CapabilityExecutionContext, P) -> CapabilityExecutionResult` — 执行校验后的 plan

### 三个实现

| Handler | Intent | validate() 委托 | execute() 步骤 |
|---------|--------|-----------------|----------------|
| `QueryCapabilityHandler` | QUERY | `QueryPlanValidator` | 权限检查 → 适配器查找 → query() → 结果处理+脱敏 → 构建响应+查询上下文 |
| `ClarifyCapabilityHandler` | CLARIFY | `ClarifyPlanValidator` | 直接返回 `CapabilityExecutionResult.clarify(question)` |
| `AggregateCapabilityHandler` | AGGREGATE | `AggregatePlanValidator` | 权限检查 → 适配器查找 → aggregate() → 结果处理+脱敏 → 构建响应+聚合上下文 |

---

## 6. 能力处理器详解

### 6.1 QueryCapabilityHandler
**文件：** `agent-service/.../capability/query/QueryCapabilityHandler.java`

**依赖：** QueryPlanValidator、AgentPermissionService、QueryableAdapterRegistry、AgentResultProcessor

**validate() 流程**（通过 `QueryPlanValidator`）：
1. 断言 intent=QUERY，domain 非 null 且已配置，query spec 非 null
2. 断言 clarify/aggregate 为 null（不允许混合）
3. 确定 `QueryContextMode`（默认 REPLACE）
4. 若 MERGE：要求 previousQuery 存在且 domain 相同，规范化历史过滤条件，校验变更，通过 `QueryMergeEngine` 合并
5. 若 REPLACE：规范化过滤条件，要求至少一个过滤条件，解析 selectFields、sorts，设置 page/size
6. 校验最终过滤条件数量、分页限制和排序规则：`sorts.field` 必须来自 Domain Metadata 投影的 `sortFields` 且仍在当前执行字段权限内；`sorts.direction` 只能为 ASC/DESC；不允许重复排序字段

**execute() 流程：**
1. `permissionService.checkQuery()` — 域访问权限、字段过滤角色、操作符白名单、字段展示角色和排序字段可见性
2. `adapterRegistry.getRequired(domain)` — 查找 QueryableAdapter
3. `adapter.query(plan.query())` — 执行后端查询，返回 `AdapterQueryResult`
4. `resultProcessor.process()` — 按列应用展示权限，脱敏敏感数据
5. `QueryMessages.buildSuccessMessage()` — 构建人类可读的结果消息
6. `CapabilityExecutionResult.queryResult(...)` — 返回带 `RuntimeQueryContext` 的统一结果

**QUERY 排序边界：**
- Runtime 只能根据 `RuntimeDomainSchema.sortFields` 生成 QUERY `sorts`，不得凭字段别名或完整 Catalog 自由选择排序字段。
- Java `QueryPlanValidator` 是可信校验边界；Adapter 只接收 `ValidatedQuery.sorts`，不自报也不自行扩大排序能力。
- 业务域服务负责把已校验 canonical field 映射到 ES/SQL 字段；transaction 动态 `ORDER BY` 只能由服务层白名单映射生成。
- QUERY `sorts` 是明细行排序；AGGREGATE `orderBy` 是聚合结果排序，字段来源和校验规则互不复用。
- AGGREGATE `orderBy` 已进入 Runtime Aggregate Context View，用于多轮聚合规划继承或显式重排；该投影不代表 `AGGREGATE_CONTEXT` payload 版本升级，也不要求下游聚合接口新增排序入参。

### 6.2 ClarifyCapabilityHandler
**文件：** `agent-service/.../capability/clarify/ClarifyCapabilityHandler.java`

**依赖：** ClarifyPlanValidator

**validate() 流程**（通过 `ClarifyPlanValidator`）：
1. 断言 intent=CLARIFY，clarify spec 非 null
2. 断言 query/aggregate 为 null
3. 校验问题长度（1-500 字符）
4. 若提供了 domain，校验其存在于配置中

**execute() 流程：**
1. 返回 `CapabilityExecutionResult.clarify(question)` — 无适配器调用，无持久化上下文

### 6.3 AggregateCapabilityHandler
**文件：** `agent-service/.../capability/aggregate/AggregateCapabilityHandler.java`

**依赖：** AggregatePlanValidator、AgentPermissionService、AggregatableAdapterRegistry、AggregateResultProcessor

**validate() 流程**（通过 `AggregatePlanValidator`）：
1. 断言 intent=AGGREGATE，domain 非 null 且已配置
2. 断言 query/clarify 为 null
3. 校验 metrics：至少 1 个，最多 `aggregate.maxMetrics`，唯一别名，函数-字段兼容性（COUNT 无字段，SUM/AVG 需 DECIMAL，MIN/MAX 需 DECIMAL 或 INSTANT），适配器函数支持
4. 规范化并校验过滤条件（若存在）
5. 校验 groupByFields：最多 `aggregate.maxGroupFields`，必须已配置且适配器支持
6. 校验 maxRows 边界
7. 校验 orderBy：字段必须来自 groupByFields 或指标别名

**execute() 流程：**
1. `permissionService.checkAggregate()` — 域访问权限、过滤字段权限和操作符、groupBy 字段展示权限、指标字段展示权限
2. `adapterRegistry.getRequired(domain)` — 查找 AggregatableAdapter
3. `adapter.aggregate(plan.aggregate())` — 执行，返回 `AdapterAggregateResult`
4. `resultProcessor.process()` — groupBy 值的展示权限，指标值脱敏
5. `AggregateMessages.success()` — 概要消息
6. 从校验后的 plan 构建 `RuntimeAggregateContext`
7. `CapabilityExecutionResult.aggregateResult(...)` — 返回带聚合上下文的统一结果

---

## 7. 持久化层

### 数据库 Schema（3 个迁移文件）

**agent-p0.sql**（初始 Schema）：
```sql
agent_conversation: id, user_id, status, created_at, updated_at
agent_turn: id, turn_seq (AUTO_INCREMENT), conversation_id (FK), user_id,
            user_message (TEXT), intent, response_type, assistant_message (TEXT),
            query_context_json (JSON), status, error_code, created_at, completed_at
```

**agent-p0-v1.1.sql**：新增 `turn_seq` AUTO_INCREMENT 列及排序索引。

**agent-p0-v1.2.sql**：新增 `query_context_json JSON` 列，用于持久化查询/聚合上下文以支持 MERGE。

### 实体

**`AgentConversationEntity`**：id、userId、status、createdAt、updatedAt

**`AgentTurnEntity`**：id、conversationId、userId、userMessage、intent、responseType、assistantMessage、queryContextJson、status、errorCode、createdAt、completedAt

### MyBatis Mapper

**`AgentConversationMapper`**：
- `insert` — INSERT
- `selectOwned` — 通过 id + userId 查询
- `touchOwned` — 更新 updated_at（用于所有权验证）
- `deleteExpiredWithoutTurns` — 清理无关联 turn 的对话

**`AgentTurnMapper`**：
- `insert` — INSERT，状态为 PROCESSING
- `selectRecentSucceeded` — 按对话查询成功的 turn，按 turn_seq DESC 排序
- `selectLatestSucceededQuery` — 查询最近一条成功的 QUERY turn（query_context_json 非 null）
- `completeSuccess` — CAS 更新：SET status=SUCCEEDED WHERE id=? AND status=PROCESSING
- `completeFailure` — CAS 更新：SET status=FAILED WHERE id=? AND status=PROCESSING
- `deleteBefore` — 删除 cutoff 之前的 turn

### ConversationService
**文件：** `agent-service/.../conversation/ConversationService.java`

关键方法（各自 `@Transactional`）：

- `openConversation(requestedId, userId)` — 加载已有（验证所有权）或创建新对话
- `startTurn(conversationId, userId, message)` — 验证对话所有权，创建 PROCESSING 状态的 turn
- `loadRecentTurns(conversationId, userId, limit)` — 加载成功的 turn，按时间顺序构建 USER/ASSISTANT RuntimeTurn 列表
- `loadLatestQueryContext(conversationId, userId)` — 加载最近 QUERY turn 的 query_context_json，反序列化为 `RuntimeQueryContext`
- `completeSuccess(turnId, intent, responseType, assistantMessage, contextToPersist)` — CAS 更新至 SUCCEEDED；若 contextToPersist 非 null，序列化为 JSON 并写入 query_context_json
- `completeFailure(turnId, errorCode, assistantMessage)` — CAS 更新至 FAILED
- `cleanupExpired(cutoff)` — 删除过期 turn 和对话

### TurnStatus
PROCESSING → SUCCEEDED（通过 `completeSuccess` CAS）或 FAILED（通过 `completeFailure` CAS）

### ConversationCleanupJob
使用可配置的 `cleanup-delay`（默认 1h）的定时任务。删除超过 `retentionDays` 的 turn 以及无关联 turn 的对话。

---

## 8. CapabilityExecutionResult

**文件：** `agent-service/.../capability/CapabilityExecutionResult.java`

这是能力处理器与编排器持久化/完成流程之间的**桥梁**。通过工厂方法创建的不可变值对象：

### 工厂方法

| 方法 | Intent | ResponseType | contextToPersist |
|------|--------|-------------|-----------------|
| `queryResult(message, queryParams, queryResult, queryContext)` | QUERY | RESULT | `RuntimeQueryContext` |
| `clarify(question)` | CLARIFY | CLARIFY | `null` |
| `aggregateResult(message, aggregateResult, context)` | AGGREGATE | AGGREGATE_RESULT | `RuntimeAggregateContext` |

### 关键字段
- `intent` / `responseType` — 用于持久化
- `assistantMessage` — 展示给用户
- `queryParameters` — 序列化至前端用于过滤条件展示
- `queryResult` / `aggregateResult` — 实际数据
- `contextToPersist` — 泛型 `Object`，由 ConversationService 序列化为 `query_context_json`

### applyTo(AgentChatResponse)
填充所有响应字段并显式设置 `errorCode = null`（错误走异常路径）。

---

## 9. 前端 (agent.html)

**文件：** `agent-service/src/main/resources/static/agent.html`

单页 HTML 应用，访问路径 `/agent.html`，包含四个展示区：

### 结构

1. **输入区**：文本输入框（最多 2000 字符）+ 发送按钮，支持 Enter 键
2. **Section 1 - "Summarizer Text"**：响应的 `summary` 字段（LLM 自然语言摘要）
3. **Section 2 - "LLM Parsed Query Parameters"**：`queryParameters` 的预格式化 JSON（domain、filters、selectFields、分页）
4. **Section 3 - "AgentQueryResult"**：HTML 表格渲染，含列头、数据行、元数据（总数、页码）。处理 `totalExact=false` 时显示 "至少 N 条"
5. **Section 4 - "AgentAggregateResult"**：HTML 表格渲染，先展示 groupBy 列，再展示指标列。显示 domain、行数、部分结果标识

### JS 函数

- `sendMessage()` — POST 至 `/agent/chat`，credentials=include，处理登录重定向
- `renderSummary(text, isError)` — 展示摘要文本，错误时红色
- `renderQueryParameters(parameters)` — JSON.stringify 展示
- `renderQueryResult(result)` — 表格渲染，正确处理 null/value
- `renderAggregateResult(result)` — 表格渲染，groups+metrics 结构
- `setBusy(busy)` — 请求期间禁用输入
- `isLoginRedirect(response)` — 检测登录页重定向

### 认证
使用 `credentials: "include"` 通过 Gateway 进行 session/JWT cookie 认证。

---

## 10. 近期重构：统一持久化链路

### 重构前（按意图分叉）

```
CapabilityExecutionResult
  ├─ queryContextToPersist: RuntimeQueryContext    ← QUERY 专用，强类型
  └─ aggregateResult() factory 硬编码 null

AgentOrchestrator.completeTurn()
  ├─ if queryContextToPersist != null → completeQuerySuccess    ← 硬编码 QUERY
  └─ else                              → completeSuccess        ← 不写 context

ConversationService / AgentTurnMapper
  ├─ completeSuccess()       → SQL 无 query_context_json
  └─ completeQuerySuccess()  → SQL 硬编码 intent='QUERY'
```

### 重构后（通用路径）

核心改动：`CapabilityExecutionResult.contextToPersist` 类型泛化为 `Object`。

**1. Handler 返回**：`CapabilityExecutionResult`，携带不透明的 `contextToPersist`（QUERY → `RuntimeQueryContext`，AGGREGATE → `RuntimeAggregateContext`，CLARIFY → `null`）

**2. Orchestrator 调用**（零分支）：
```java
private void completeTurn(String turnId, CapabilityExecutionResult result) {
    conversationService.completeSuccess(
        turnId,
        result.intent(),
        result.responseType(),
        result.assistantMessage(),
        result.contextToPersist());
}
```

**3. ConversationService.completeSuccess()**（统一序列化）：
```java
String contextJson = null;
if (contextToPersist != null) {
    contextJson = objectMapper.writeValueAsString(contextToPersist);
}
turnMapper.completeSuccess(turnId, intent, responseType, assistantMessage, contextJson, now);
```

**4. AgentTurnMapper.completeSuccess()** SQL 无条件写入 `query_context_json`：
```sql
UPDATE agent_turn SET query_context_json = #{contextJson}
WHERE id = #{id} AND status = 'PROCESSING'
```

### 扩展性

新意图（UPDATE / WORKFLOW / COMMAND）接入时仅需：
1. Handler 构建对应 DTO
2. 传入 `CapabilityExecutionResult` 工厂方法
3. 零 plumbing 改动，由统一链路完成持久化

### 各意图 query_context_json 存储内容

| Intent | 存储类型 | 用途 |
|--------|---------|------|
| QUERY | `RuntimeQueryContext`（sourceTurnId, domain, filters, selectFields, sorts, page, size, total/totalExact/totalPages） | 下一轮 MERGE、分页和排序继承时加载使用 |
| AGGREGATE | `RuntimeAggregateContext`（sourceTurnId, domain, filters, metrics, groupByFields, orderBy, maxRows） | 审计追溯，并为兼容上一轮聚合的多轮规划提供最小上下文 |
| CLARIFY | `null` | 无上下文需要持久化 |
