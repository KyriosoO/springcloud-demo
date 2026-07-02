# D03_01 UserPermissionAuthority 权限权威源契约说明 — L2 v1.0

> 文档状态：已完成本轮评审
> 编写日期：2026-07-02
> 适用阶段：D03 编码前置门禁解除
> 上位依据：`D02_03_元数据授权与Context安全_L2_v1.0.md`、`D03_Capability v2跨服务原子切换_L2实施详细设计_v1.0.md`
> 本文输出：auth-service 内部 Agent Permission API 契约、agent-service `UserPermissionAuthorityPort` 生产 Adapter 消费契约

---

## 0. Change List

| 日期 | 内容 | 原因 |
|---|---|---|
| 2026-07-02 | 新增 D03_01 权限权威源契约说明，定义 auth-service 内部权限投影接口与 agent-service Adapter 消费约束 | D03 受 `UserPermissionAuthorityPort` 生产 Adapter 门禁阻断，需先完成权限权威源小设计和接口契约 |

---

## 1. 文档目的与边界

### 1.1 目的

本文只完成 D03 阻断项的前两步：

1. 补充权限权威源小设计和契约说明。
2. 明确 auth-service 暴露的内部接口、请求/响应 DTO、鉴权方式、超时、错误码和版本语义。

本文为后续两项编码提供稳定依据：

```text
agent-service
  UserPermissionAuthorityPort
    ↓ HTTP/OpenFeign/RestClient
auth-service
  internal Agent Permission API
    ↓
  权限数据源 / 规则 / 用户授权模型
```

### 1.2 非目标

本文不做以下事情：

- 不实现 auth-service API。
- 不实现 agent-service 生产 Adapter。
- 不修改 D03 主链、Runtime Route/Plan、Lifecycle、Execution Core、Context、ResultSecurity 或 UI。
- 不把 JWT role、本地 `agent.intent-roles`、测试替身或旧 `AgentPermissionService` 定义为生产权限源。
- 不设计完整 RBAC/ABAC 权限平台，只定义 Agent 侧所需的最小权限投影契约。
- 不改变 D02_03 已冻结的 `UserPermissionAuthorityPort` Java SPI。

---

## 2. 当前阻断与设计原则

### 2.1 当前阻断

D03 文档要求：D03 编码前必须存在且只存在一个生产 `UserPermissionAuthorityPort` 实现。当前仓库中：

- `agent-service` 已有 `UserPermissionAuthorityPort`、`UserPermissionBoundary` 和唯一 Bean 装配门禁；
- `auth-service` 当前只提供登录、JWT role claim、`agent:admin` / `agent:viewer`；
- 当前没有字段级、domain 级、capability 级权限投影 API；
- 当前没有生产 `UserPermissionAuthorityPort` Adapter。

因此必须先定义 auth-service 内部权限投影接口，再由 agent-service 实现生产 Adapter。

### 2.2 设计原则

1. auth-service 是用户权限投影的权威提供方；agent-service 只消费投影，不根据 role 二次推导权限。
2. JWT role 可以作为 auth-service 内部计算输入之一，但不能作为接口响应的替代。
3. agent-service 不接收权限表达式、规则脚本、JWT、完整角色列表或 auth-service 内部数据模型。
4. auth-service 响应必须覆盖 `UserPermission` 全字段。
5. 权限响应必须有 `evidenceId` 和 `version`，用于 Planning snapshot 与 Execution recheck。
6. 所有异常默认 fail closed；不得回退本地配置或上次允许结果。
7. 服务间调用使用服务 token 或等价内部服务认证，不转发用户 JWT 作为权限事实。
8. 接口是内部 API，不对前端或外部用户开放。

---

## 3. 权威关系与调用链

### 3.1 权威关系

| 事实 | 权威源 | 消费方 |
|---|---|---|
| 用户身份认证 | auth-service / OAuth2 resource server | agent-service Entry |
| Agent 用户权限投影 | auth-service internal Agent Permission API | agent-service `UserPermissionAuthorityPort` Adapter |
| Profile/Policy 收紧 | agent-service metadata | `AuthorizationPlanningPortImpl` |
| Domain field/operator/function 事实 | D04 `agent.domain-metadata` | `DomainMetadataPortImpl` |
| Planning/Execution scope | agent-service Authorization boundary | Planning/Core |

auth-service 不拥有 D04 Canonical Domain Catalog；它只返回对 canonical id 的授权投影。字段、operator、function 是否存在仍由 agent-service 的 D04/D02_03 边界 fail closed 校验。

### 3.2 目标调用链

```text
AuthorizationPlanningPortImpl.capture
  → UserPermissionBoundary.resolve(subject, deadline)
  → AuthServiceUserPermissionAuthorityAdapter.resolveCurrent(subject, deadline)
  → auth-service internal Agent Permission API
  → UserPermission
  → PlanningEffectiveScope = Profile ∩ Policy ∩ UserPermission ∩ Delegation
```

Execution recheck 使用同一 Adapter：

```text
AuthorizationExecutionPortImpl.recheck(snapshot, handle)
  → UserPermissionBoundary.resolve(handle.subject(), handle.absoluteDeadline())
  → compare current permission with snapshot required scope
  → keep or shrink only; shrink required scope = fail closed
```

---

## 4. auth-service 内部 API 契约

### 4.1 Endpoint

| 项 | 设计 |
|---|---|
| Method | `POST` |
| Path | `/internal/agent/permissions/resolve` |
| Content-Type | `application/json` |
| Auth | 服务间 token；要求 `service=agent-service` 且具备内部 scope `agent.permission.resolve` |
| 用户 JWT | 不转发，不作为权限事实输入 |
| 幂等性 | 读操作，按同一 subject 与同一权限版本返回等价 projection |
| 超时 | agent-service Adapter 调用预算不得超过当前 absoluteDeadline；默认连接 2s，读取 2s 或剩余 deadline 较小值 |

### 4.2 Request DTO

Java 建议包名：

```text
auth-service/src/main/java/com/dylan/authcenter/agent/permission/api/AgentPermissionResolveRequest.java
```

字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `requestId` | `String` | 是 | agent-service 生成的请求关联 ID，不含用户 JWT |
| `subject` | `SubjectRefDto` | 是 | 与 `ExecutionSubjectRef` 同构 |
| `requestedAt` | `Instant` | 是 | agent-service 发起请求时间 |
| `deadline` | `Instant` | 是 | 当前 Invocation absolute deadline |
| `agentId` | `String` | 是 | 首版固定 `default-agent`，未来多 profile 可扩展 |
| `profileId` | `String` | 是 | 当前 `AgentProfileRef.id` |
| `scopeType` | `String` | 是 | `CONVERSATION` 或 `RUN`；D03 只发送 `CONVERSATION` |
| `scopeId` | `String` | 是 | conversationId 或 runId |
| `requestedCapabilityIds` | `Set<String>` | 否 | 可选收敛输入；auth-service 不得返回未授权 capability |
| `requestedDomains` | `Set<String>` | 否 | 可选收敛输入；auth-service 不得返回未授权 domain |

`SubjectRefDto`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | `String` | 是 | D03 CHAT 固定 `USER` |
| `id` | `String` | 是 | 稳定用户 ID |

约束：

- `subject.type` 与 `subject.id` 必须非空。
- `deadline` 早于 auth-service 当前时间时返回 deadline failure。
- `requestedCapabilityIds` 和 `requestedDomains` 是收敛输入，不是授权事实；auth-service 可以返回其子集，不能因请求列出而扩大授权。

### 4.3 Response DTO

Java 建议包名：

```text
auth-service/src/main/java/com/dylan/authcenter/agent/permission/api/AgentPermissionResolveResponse.java
```

字段必须覆盖 agent-service `UserPermission`：

| 字段 | 类型 | 必填 | 对应 `UserPermission` |
|---|---|---|---|
| `subject` | `SubjectRefDto` | 是 | `subject` |
| `evidenceId` | `String` | 是 | `evidenceId` |
| `version` | `String` | 是 | `version` |
| `allowedCapabilityIds` | `Set<String>` | 是 | `allowedCapabilityIds` |
| `allowedDomains` | `Set<String>` | 是 | `allowedDomains` |
| `filterableFields` | `Map<String, Set<String>>` | 是 | `filterableFields` |
| `displayableFields` | `Map<String, Set<String>>` | 是 | `displayableFields` |
| `allowedOperators` | `Map<String, Set<String>>` | 是 | `allowedOperators` |
| `allowedFunctions` | `Map<String, Set<String>>` | 是 | `allowedFunctions` |
| `readableContextTypes` | `Set<String>` | 是 | `readableContextTypes` |
| `writableContextTypes` | `Set<String>` | 是 | `writableContextTypes` |
| `attributes` | `Map<String, String>` | 是 | `attributes` |
| `resolvedAt` | `Instant` | 是 | `resolvedAt` |

`filterableFields`、`displayableFields` 的 key 是 canonical domain id。
`allowedOperators`、`allowedFunctions` 的 key 是 stable field key：

```text
<domain>.<field>
```

示例：

```json
{
  "subject": {"type": "USER", "id": "dylan"},
  "evidenceId": "perm-user-dylan-v20260702-000001",
  "version": "authz-2026-07-02T10:00:00Z",
  "allowedCapabilityIds": ["query.search", "aggregate.compute"],
  "allowedDomains": ["employee", "transaction"],
  "filterableFields": {
    "employee": ["chineseName", "memberNo", "position"],
    "transaction": ["transId", "transType", "transDate", "amount"]
  },
  "displayableFields": {
    "employee": ["chineseName", "memberNo", "position"],
    "transaction": ["transId", "transType", "transDate", "amount"]
  },
  "allowedOperators": {
    "employee.chineseName": ["EQ", "CONTAINS", "CONTAINS_ANY", "STARTS_WITH", "STARTS_WITH_ANY", "IN"],
    "transaction.amount": ["EQ", "GT", "LT"]
  },
  "allowedFunctions": {
    "transaction.amount": ["SUM", "AVG", "MIN", "MAX"]
  },
  "readableContextTypes": ["QUERY", "AGGREGATE"],
  "writableContextTypes": ["QUERY", "AGGREGATE"],
  "attributes": {
    "source": "auth-service-agent-permission",
    "policyTier": "default"
  },
  "resolvedAt": "2026-07-02T10:00:00Z"
}
```

### 4.4 响应闭合规则

auth-service 必须保证：

1. `subject` 精确等于请求 subject。
2. `evidenceId` 非空且同一次权限计算唯一。
3. `version` 非空且表达权限数据/规则版本。
4. 所有集合和 Map 非 null；无权限时返回空集合，不返回 null。
5. `allowedOperators` 使用 D01 `AgentOperator` 的 enum name 字符串。
6. `allowedFunctions` 使用 D04 canonical lowercase function id。
7. `resolvedAt` 不晚于响应生成时间。

agent-service Adapter 仍必须重新校验以上规则，并将不合法响应映射为 `INVALID_RESPONSE`。

---

## 5. evidenceId 与 version 语义

### 5.1 `version`

`version` 表示 auth-service 权限数据和规则的可比较版本。

建议格式：

```text
authz-<yyyyMMddHHmmss>-<monotonicRevision>
```

要求：

- 同一用户权限规则或授权数据变化后，`version` 必须变化。
- Planning capture 和 Execution recheck 使用 `version` 判断权限是否发生变化。
- 如果 auth-service 无法证明当前 version，必须返回错误，不得生成一次性随机 version。

### 5.2 `evidenceId`

`evidenceId` 表示本次权限投影计算证据 ID。

建议格式：

```text
perm-<subjectType>-<subjectId>-<version>-<shortDigest>
```

要求：

- 同一 subject、version、projection 内容一致时，`evidenceId` 可以稳定。
- projection 内容变化时，`evidenceId` 必须变化。
- `evidenceId` 不包含权限正文、JWT、业务凭据或 PII 明文。

### 5.3 Planning 与 Execution 关系

Planning 阶段保存：

```text
permissionEvidenceId
permissionVersion
PlanningEffectiveScope
```

Execution 阶段重新查询当前权限：

- 当前权限覆盖 Planning required scope：允许继续。
- 当前权限缩小导致 required scope 不满足：fail closed。
- 当前 `version` 或 `evidenceId` 变化但仍覆盖 required scope：允许继续，但记录 current evidence。
- 权限源不可用或响应非法：fail closed。

---

## 6. 错误码与 HTTP 映射

### 6.1 auth-service 错误响应

`AgentPermissionErrorResponse`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `requestId` | `String` | 是 | 原请求 ID |
| `code` | `String` | 是 | typed error code |
| `message` | `String` | 是 | 安全错误描述，不含权限正文 |
| `diagnosticId` | `String` | 是 | 服务端诊断 ID |

允许错误码：

| code | HTTP | Adapter 映射 |
|---|---|---|
| `AGENT_PERMISSION_SUBJECT_NOT_FOUND` | 404 | `SUBJECT_NOT_FOUND` |
| `AGENT_PERMISSION_DEADLINE_EXCEEDED` | 504 | `DEADLINE_EXCEEDED` |
| `AGENT_PERMISSION_UNAVAILABLE` | 503 | `UNAVAILABLE` |
| `AGENT_PERMISSION_INVALID_REQUEST` | 400 | `INVALID_RESPONSE` |
| `AGENT_PERMISSION_INTERNAL_ERROR` | 500 | `UNAVAILABLE` |

### 6.2 Adapter 映射规则

agent-service `AuthServiceUserPermissionAuthorityAdapter` 映射到：

| 场景 | `UserPermissionAuthorityFailure` |
|---|---|
| 连接超时、读取超时、deadline 已过 | `DEADLINE_EXCEEDED` |
| 404 subject not found | `SUBJECT_NOT_FOUND` |
| 503 或 auth-service 不可用 | `UNAVAILABLE` |
| 非法 JSON、缺字段、subject mismatch、operator 非法、version/evidence 缺失 | `INVALID_RESPONSE` |
| 401/403 服务间认证失败 | `UNAVAILABLE` |
| 未知 5xx | `UNAVAILABLE` |

所有映射抛出 `UserPermissionAuthorityException`，message 和 diagnosticId 不得包含 JWT、权限正文、外部响应体或凭据。

---

## 7. 服务间鉴权与超时

### 7.1 鉴权

首版使用 common-security 已有服务 token 机制：

```text
Authorization: Bearer <service-token>
```

auth-service 必须校验：

- token 是服务 token；
- 调用方 service identity 是 `agent-service`；
- token scope 包含 `agent.permission.resolve`。

禁止：

- 转发用户 JWT 作为权限事实；
- 使用前端 cookie/session；
- 在请求中携带完整 JWT、role claim 或本地权限表达式。

### 7.2 超时

agent-service Adapter：

- connect timeout 默认 2s；
- read timeout 使用 `min(configuredReadTimeout, remainingDeadline)`；
- 调用前若 `absoluteDeadline` 已过期，直接抛 `DEADLINE_EXCEEDED`；
- 调用后若当前时间超过 deadline，丢弃响应并抛 `DEADLINE_EXCEEDED`。

auth-service：

- 如果收到请求时 deadline 已过，返回 `AGENT_PERMISSION_DEADLINE_EXCEEDED`；
- 如果内部权限计算无法在 deadline 前完成，返回 `AGENT_PERMISSION_DEADLINE_EXCEEDED`；
- 不返回部分权限。

---

## 8. auth-service 权限计算边界

auth-service 可以使用以下输入计算权限：

- 用户身份；
- 用户角色；
- 部门、租户、岗位等授权数据；
- auth-service 自有权限规则；
- Agent capability/domain/field/operator/context 的授权配置。

auth-service 不得把以下事实交给 agent-service 再推导：

- 原始 role 列表作为唯一响应；
- 权限规则表达式；
- 数据库行权限 SQL；
- JWT claim；
- 未闭合的 domain/field/operator 字符串。

首版如果 auth-service 还没有完整权限平台，可以用内部静态规则计算投影，但必须满足：

1. 静态规则位于 auth-service，不在 agent-service。
2. 输出仍是完整 `AgentPermissionResolveResponse`。
3. 规则版本进入 `version`。
4. 后续替换为数据库/权限平台时，agent-service Adapter 不变。

---

## 9. agent-service Adapter 消费契约

后续实现文件建议：

```text
agent-service/src/main/java/com/dylan/agent/metadata/authorization/internal/AuthServiceUserPermissionAuthorityAdapter.java
```

职责：

1. 实现 `UserPermissionAuthorityPort`。
2. 将 `ExecutionSubjectRef` 和 `absoluteDeadline` 转换为 `AgentPermissionResolveRequest`。
3. 使用 OpenFeign 或 RestClient 调用 auth-service 内部 API。
4. 校验 HTTP status、错误响应、成功响应结构和 subject。
5. 将 operator 字符串转换为 D01 `AgentOperator`。
6. 构造 `UserPermission`。
7. 将错误映射为 `UserPermissionAuthorityException`。

禁止：

- 从 JWT role 或 `AgentUserContext` 推导 `UserPermission`。
- 读取 `agent.intent-roles`。
- 读取 D04 `agent.domain-metadata` 后自行补全字段权限。
- 缓存允许结果作为 fallback。
- 在 Adapter 内扩大 auth-service 返回的权限集合。

配置建议：

```yaml
agent:
  authorization:
    authority:
      auth-service:
        base-url: http://auth-service
        resolve-path: /internal/agent/permissions/resolve
        connect-timeout: 2s
        read-timeout: 2s
        max-response-bytes: 65536
```

---

## 10. 测试与门禁

### 10.1 auth-service 测试

建议新增：

- `AgentPermissionInternalControllerTest`
- `AgentPermissionProjectionServiceTest`
- `AgentPermissionErrorResponseTest`
- `AgentPermissionServiceTokenSecurityTest`

覆盖：

1. 正常用户返回完整投影。
2. unknown subject 返回 `AGENT_PERMISSION_SUBJECT_NOT_FOUND`。
3. deadline 过期返回 `AGENT_PERMISSION_DEADLINE_EXCEEDED`。
4. 非服务 token 或缺 scope 返回 401/403。
5. 响应不包含 JWT、role 原文或权限规则表达式。
6. role 变化或授权规则变化导致 `version` 变化。

### 10.2 agent-service Adapter 测试

建议新增：

- `AuthServiceUserPermissionAuthorityAdapterTest`
- `UserPermissionAuthorityWiringTest`
- `UserPermissionAuthorityContractTest`

覆盖：

1. 成功响应转换为 `UserPermission`。
2. subject mismatch -> `INVALID_RESPONSE`。
3. 缺 `evidenceId` / `version` -> `INVALID_RESPONSE`。
4. 非法 operator -> `INVALID_RESPONSE`。
5. 超时 -> `DEADLINE_EXCEEDED`。
6. 404 -> `SUBJECT_NOT_FOUND`。
7. 503/5xx -> `UNAVAILABLE`。
8. 生产上下文恰好一个 `UserPermissionAuthorityPort` Bean。
9. 搜索确认没有 Adapter fallback 到 JWT role、本地 role 或旧 `AgentPermissionService`。

### 10.3 静态门禁

D03 编码前解除阻断至少要求：

```powershell
rg -n "implements UserPermissionAuthorityPort|class AuthServiceUserPermissionAuthorityAdapter" agent-service/src/main/java
rg -n "agent.intent-roles|AgentPermissionService|JWT role|claims.*role" agent-service/src/main/java/com/dylan/agent/metadata/authorization agent-service/src/main/java/com/dylan/agent/application
rg -n "/internal/agent/permissions/resolve|AgentPermissionResolveRequest|AgentPermissionResolveResponse" auth-service/src/main/java
```

预期：

- 第一条命中唯一生产 Adapter。
- 第二条无命中。
- 第三条命中 auth-service 内部权限接口和 DTO。

---

## 11. 评审结论

本文完成 D03 阻断项的契约前置设计：

1. 已明确 auth-service 内部 Agent Permission API。
2. 已明确请求/响应 DTO。
3. 已明确服务间鉴权方式。
4. 已明确超时和 deadline 语义。
5. 已明确错误码和 `UserPermissionAuthorityFailure` 映射。
6. 已明确 `evidenceId` / `version` 语义。
7. 已明确 agent-service 生产 Adapter 的消费边界。
8. 已明确 fail closed 和测试门禁。

本文不解除 D03 编码门禁本身。只有当 auth-service API 和 agent-service 生产 Adapter 按本文实现并通过门禁后，D03 原子切换编码才能继续。
