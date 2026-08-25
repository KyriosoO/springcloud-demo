# [L2_02_01] 单体 Agent Employee 条件/语义查询 Adapter 与授权详细设计

> 文档状态：Approved

## 1. 文档信息、上位约束与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.1 |
| 更新时间 | 2026-08-25 |
| 上位约束来源 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v2.1；[`L2_00_03`](L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) `DR-AUTH-007` |
| 关联责任边界 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v2.0 |
| 归档来源 | [v1.6 已评审旧版](历史文档/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN_v1.6.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 设计目标、范围外与当前实现基线

目标复用 `EmployeeEsController.search` 和 `vectorSearch` 现有公开接口，分别提供 `employee.search`、`employee.semantic_search`，返回严格投影的员工列表。范围外包括新 endpoint/DTO、ES 直连、索引重建、聚合、写入、客户端二次筛选、自动互相 fallback 和启用 workBase 字段。

当前实现：Agent 已实现 search/semantic definition、统一字段配置、固定 endpoint Adapter、bounded ES hits codec 与生产组合根；两个 Controller 入口已调用 `requireEmployeeRead`。但现有 `EmployeeDetailSecurityConfiguration` 只为历史 detail 入口显式绑定 `userRoleJwtAuthenticationConverter`，两个 ES POST 仍落入使用 Spring 默认转换器的通用安全链，导致真实 `role=[ADMIN]` JWT 无法形成 `ROLE_ADMIN` 并被现有守卫误拒绝。该端点级安全链和真实过滤链权限测试尚未实施。

| 需求编号 | 需求 |
|---|---|
| `REQ-EMP-101` | 复用条件搜索接口返回过滤/分页/排序列表 |
| `REQ-EMP-102` | 复用向量接口返回业务语义列表且禁止结构化 filter 拼装 |
| `REQ-EMP-103` | 地址字段、敏感值、workBase 排除及 ES hits 严格投影 |
| `REQ-EMP-104` | 两个业务入口完成最终角色读取授权和兼容性验证 |

| 约束编号 | 上位约束 |
|---|---|
| `CON-EMP-101` | 单动作仅允许一个固定 Employee endpoint，禁止 ES/数据库直连 |
| `CON-EMP-102` | 既有公开接口只允许收紧读取授权，不新增 DTO 或扩大角色 |

## 3. 已核实接口契约、模块职责与依赖方向

| 动作 | Java 接口 | 请求类型 | 真实能力 | 当前鉴权 |
|---|---|---|---|---|
| `employee.search` | `POST /employees/es/search` | `SearchRequest/SearchFilter/SearchSort` | keyword、filter、from/size、sort；可含 aggregate 但 Agent 禁止 | Controller 已 `requireEmployeeRead`；安全链目前缺少共享角色转换 |
| `employee.semantic_search` | `POST /employees/es/vector-search` | `SemanticSearchRequest` | queryText、embeddingField、embeddingDims、k、numCandidates、trackTotalHits；没有 filter | Controller 已 `requireEmployeeRead`；安全链目前缺少共享角色转换 |

`EmployeeEsService.SEARCHABLE_FIELDS` 当前包括 `contactAddress/chineseName/idCardNo/memberNo/phoneNo/email/position/workBaseSi`；其中 workBaseSi 因无有效数据而禁止，workBaseAf 也不能成为开放字段。`keyword` multi-match 仅包括 `contactAddress/chineseName/idCardNo`。普通搜索 operator 现有归一化支持 `eq/contains/prefix/in` 及别名，但 Agent 只生成有限 canonical operator。

`buildEmbeddingText` 拼接姓名、联系地址、职位、学历、院校、专业、workBaseSi、workBaseAf。它表明现有 embedding 的历史组成，不代表支持按其中任一单字段独立向量检索；workBase 两字段仍不开放。依赖方向为 Business validated plan → Employee Adapter → EmployeeEsController → EmployeeEsService；禁止绕过 Controller/业务权限访问 ES。

既有 Java 边界为 `EmployeeEsController.search(Authentication, SearchRequest) -> String` 和 `EmployeeEsController.vectorSearch(Authentication, SemanticSearchRequest) -> String`，公开签名保持不变。Python 建议新增 `employee_search_definition()`、`employee_semantic_search_definition()`、`EmployeeSearchArgumentValidator.validate(JsonObject) -> EmployeeSearchInput`、`EmployeeSearchRequestMapper.map(EmployeeSearchInput, BusinessActionSettings) -> EmployeeSearchWireRequest`，以及对应 semantic mapper 与 `encode/decode_success` codec。上述 search/semantic 类和函数当前尚不存在，不能把已存在 `EmployeeDetail*` 类型冒充新动作实现。

## 4. 字段矩阵、输入保护与模型目录

| 逻辑字段 | 服务字段 | action | operator 代码上界 | 输入 exposure | 用户可见/转换 | 模型可见 |
|---|---|---|---|---|---|---|
| `contact_address` | `contactAddress` | search | `eq,contains,prefix,in` | 安全地点片段 literal；详细地址 ref | 是，`mask_address` | 否 |
| `chinese_name` | `chineseName` | search | `eq,contains,prefix,in` | `protected_ref` | 是，`mask_name` | 否 |
| `employee_identifier` | `idCardNo` | search | `eq` | `protected_ref` | 是，`mask_identifier` | 否 |
| `member_no` | `memberNo` | search | `eq,prefix` | `protected_ref` | 是，`mask_identifier` | 否 |
| `phone_no` | `phoneNo` | search | `eq,prefix` | `protected_ref` | 是，`mask_contact` | 否 |
| `email` | `email` | search | `eq` | `protected_ref` | 是，`mask_contact` | 否 |
| `position` | `position` | search | `eq,contains,prefix,in` | `literal` 安全业务文本 | 是，bounded text | 可由独立策略启用 |

安全地点 literal 只允许代码识别的有限城市片段，如“上海”；详细地址、姓名、证件、编号、邮箱和电话必须先经 request-local protected extractor 替换为 slot。不得假定“上海”、拼音、编码或同义词等价。

`workBaseSi/workBaseAf` 不纳入 Agent 已定义字段、启用配置、模型目录、结果字段或 semantic 可声明字段。未配置字段通过通用 QueryPlan 字段白名单拒绝，按通用合同返回 `unsupported` 或 `invalid_argument`，业务调用为 0；ES `_source` 中未配置字段由通用结果投影白名单自然丢弃。不得增加 workBase 专用黑名单、识别分支或门禁。

## 5. 请求/响应处理流程与接口契约设计

### 5.1 employee.search

```json
{"domain":"employee","action":"employee.search","arguments":{"filters":[{"field":"contact_address","operator":"contains","value":{"literal":"上海"}}],"page":1,"size":20,"sorts":[]}}
```

Adapter 固定映射为现有 `SearchRequest`：`filters[].field=contactAddress`、`operator=contains`、`value=上海`；`from=(page-1)*size`、`size≤50`，sort 字段和方向仅取已验证允许集合。keyword 可选，但必须先通过统一配置中的 action-level keyword policy，并使用 `literal/value_ref` tagged value；代码绑定匹配字段仅为 contactAddress/chineseName/idCardNo，真实姓名、标识和详细地址只能绑定请求级 protected ref，禁止裸字符串或敏感 literal。aggregate 必须始终不存在；filters 或 keyword 至少存在一个，避免默认 match_all。

`in` 值映射至现有 `SearchFilter.values`；敏感字段的多值集合必须由 protected slot 提供。禁止 DTO 字段名、ES DSL 和 raw query 进入模型。

### 5.2 employee.semantic_search

arguments exact 为 `query/size`；query 是安全业务文本 tagged literal，`1≤size≤50`。Adapter 固定映射为 `SemanticSearchRequest.queryText` 与 `k=size`；`embeddingField/embeddingDims/numCandidates/trackTotalHits` 仅来自代码绑定 finite profile，`queryVector` 始终不允许用户或模型输入。

当前 DTO 没有 `filters`，因此“语义能力匹配 + contact_address”等结构化约束必须 unsupported、调用 0；不得普通搜索后客户端过滤，不得一次请求执行 search 再 vector-search。语义请求包含姓名、手机号、详细地址等敏感值时拒绝，不得将 protected slot 解包到 embedding query。

### 5.3 bounded ES hits 响应

只接受固定 allowlist 的 JSON-compatible content-type：`application/json`、`application/*+json` 或既有 String Controller 的 `text/plain` 且 UTF-8；拒绝缺失类型、HTML 和非 UTF-8。复用现有最大响应字节上界 1 MiB，strict JSON decoder 拒绝重复键、非有限数值和非法 hits 结构；rows 数量不得超过请求 size。

仅按已允许的七个业务字段执行 `_source` 白名单投影；未配置字段以及 `embedding`、`embeddingText`、`operTime`、ES 索引/score 元数据均不会进入用户结果，其中 `workBaseSi/workBaseAf` 无需额外专用处理。`hits.total.relation=eq/gte` 分别映射 `totalExact=true/false`；无法证明 total 形状时返回 `invalid_response`，不得将原始 ES JSON 转发到用户或模型。

## 6. 最终读取授权、权限与审计设计

现有 `EmployeeEsController.search(...)` 和 `vectorSearch(...)` 已调用 `accessGuard.requireEmployeeRead(authentication)`。按共享安全设计 `L2_00_03 DR-AUTH-007`，还必须在现有 `EmployeeDetailSecurityConfiguration` 内新增仅匹配 `POST /employees/es/search` 和 `POST /employees/es/vector-search` 的 endpoint-scoped `SecurityFilterChain`，显式使用 `@Qualifier("userRoleJwtAuthenticationConverter")` 注入现有共享 Servlet converter。该链位于历史 detail 专用链之后、通用 fallback 链之前；只要求已认证用户进入 Controller，最终 ADMIN/VIEWER 读取决策仍由 `CapabilityAccessGuard.requireEmployeeRead` 执行。

detail 专用链继续使用原有 matcher、converter 和读取权限；所有其他 Employee endpoint 继续匹配原有 authenticated-only fallback，其默认转换与既有调用方行为不得改变。不得为修复两个查询入口修改全局 converter、公共安全组件、公开 endpoint/DTO、角色集合或生产依赖。

必须用经过真实 `SecurityFilterChain` 的 Java MVC/security 测试分别覆盖两个 ES POST 入口的 ADMIN/VIEWER 允许，非读取角色/混合非法角色、service token、missing/malformed token 拒绝，以及被拒绝请求不调用 `EmployeeEsService`；直接构造 Controller 或手工赋予 `ROLE_ADMIN` 的测试不能单独证明 JWT role claim 转换正确。同步验证 detail matcher/权限、其他 endpoint authenticated-only fallback、原 endpoint/DTO/响应及已有调用方行为保持不变。如完整链路或兼容性不能证明，该切换及真实 Employee 联调保持阻塞。

JWT 只透传业务服务，Agent 不根据角色放行业务。审计只记录 action、snapshot、有限 HTTP 状态和调用数；员工姓名、标识、地址、电话、邮箱、JWT 和 raw hits 永不写日志或 evidence。

## 7. 实现落点清单

| 实现编号 | 位置 | 目标职责 |
|---|---|---|
| `IMPL-EMP-101` | `agent-runtime/src/agent_runtime/adapters/employee/contracts.py` | search/semantic 输入、ES hits 和列表记录强类型合同 |
| `IMPL-EMP-102` | `agent-runtime/src/agent_runtime/adapters/employee/definition.py` | 两个 action definition、field/operator、固定 endpoint |
| `IMPL-EMP-103` | `agent-runtime/src/agent_runtime/adapters/employee/codec.py` | SearchRequest/SemanticSearchRequest 固定 mapper 和 bounded ES response codec |
| `IMPL-EMP-104` | `agent-runtime/src/agent_runtime/adapters/employee/fields.py` | 七字段分类、用户脱敏、模型默认拒绝、移除 workBase 目标可见性 |
| `IMPL-EMP-105` | `agent-runtime/src/agent_runtime/adapters/employee/provider.py` | 组装 search/semantic 两个固定 provider，不恢复 detail 目标绑定 |
| `IMPL-EMP-106` | `employee-service/src/main/java/com/dylan/employee/controller/EmployeeEsController.java` | 已存在：两个既有 endpoint 执行 `requireEmployeeRead`，继续保持业务服务最终授权及调用方兼容 |
| `IMPL-EMP-107` | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java` | 复用已存在的最终读取守卫，不扩展角色 |
| `IMPL-EMP-108` | `agent-runtime/src/agent_runtime/adapters/employee/protected_input.py` | 姓名/标识/联系方式/详细地址 request-local slots |
| `IMPL-EMP-109` | `employee-service/src/main/java/com/dylan/employee/security/EmployeeDetailSecurityConfiguration.java` | 建议修改已存在配置：只为两个 ES 查询 POST endpoint 新增显式绑定共享 converter 的安全链，保持 detail 和其他 endpoint 行为 |
| `IMPL-EMP-110` | `employee-service/src/test/java/com/dylan/employee/security/EmployeeEsSecurityIntegrationTest.java` | 建议新增真实 Servlet 安全过滤链测试，验证 role claim、两入口矩阵、下游零调用与敏感信息保护 |

## 8. 测试与验证设计

| 测试编号 | 场景 |
|---|---|
| `TEST-EMP-101` | 上海地址 contains、position eq/contains、keyword 真实三字段语义及 tagged literal/ref 合同 |
| `TEST-EMP-102` | 姓名/标识 protected ref、个人字段模型零泄漏、未配置字段由通用白名单拒绝且业务调用为 0 |
| `TEST-EMP-103` | Semantic queryText/k/profile，vector/physical 字段拒绝、semantic+filter 调用 0 |
| `TEST-EMP-104` | ES content-type、1 MiB、duplicate key、hits shape、未配置/unknown/embedding 字段经结果白名单自然丢弃 |
| `TEST-EMP-105` | page/from overflow、size、sort、in 上限及 aggregate 禁止 |
| `TEST-EMP-106` | 两个 ES POST 真实 SecurityFilterChain：共享 role converter、ADMIN/VIEWER 允许、denied/mixed/missing/malformed/service-token 拒绝、被拒绝请求零下游，以及 detail/其他 endpoint 历史调用方回归 |
| `TEST-EMP-107` | detail 调用方、兼容性和冻结历史证据核查；目标组合根不可达 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-EMP-101` | 两动作 fake server、strict contract、slot 与 ES hits 定向测试 |
| `VAL-EMP-102` | Employee Controller、ES/detail 完整 Servlet 安全链、matcher/fallback Maven 测试和既有调用方兼容检查 |
| `VAL-EMP-103` | Business/Knowledge 回归、strict mypy、compileall 与零泄漏扫描 |

## 9. 设计规则、失败类型与数据生命周期

| 规则编号 | 设计规则 |
|---|---|
| `DR-EMP-101` | `employee.search` 仅复用现有 ES search，逻辑字段/operator 有限映射 |
| `DR-EMP-102` | `employee.semantic_search` 仅复用 vector-search，不支持结构化 filter 或用户 vector |
| `DR-EMP-103` | `contact_address → contactAddress`，workBase 不纳入本版 Agent 字段定义与启用配置 |
| `DR-EMP-104` | bounded strict ES hits、字段白名单、敏感脱敏与模型出域默认拒绝 |
| `DR-EMP-105` | 两个 ES 查询 POST endpoint 必须显式绑定共享 `userRoleJwtAuthenticationConverter`；最终 ADMIN/VIEWER 授权仍由 Employee 读取守卫判定，detail/其他 endpoint 行为不变，切换前完成完整安全链及调用方兼容验证 |
| `DR-EMP-106` | detail 为历史实现，迁移/删除前核查 caller、公共兼容和冻结 evidence |

错误分类：unsupported/invalid plan 在发送前业务调用 0；forbidden 为固定 endpoint 1 次；timeout/unavailable/invalid_response 不重试、不切换搜索方式。数据生命周期仅为 request 内存；不修改 Employee 数据、索引和历史 evidence。事务边界与一致性归 employee-service/ES；本版复用现有 endpoint/guard，属于最小必要变更，避免 DTO 膨胀和 Adapter 耦合泄漏。

## 10. 风险、评审记录与实现就绪判定

主要风险：ES 查询入口虽然已调用读取守卫，但匹配通用安全链时 Spring 默认 converter 不理解既有 `role` claim，真实 ADMIN/VIEWER 会被错误拒绝；已有调用方可能依赖 authenticated-only fallback；raw hits 带 embeddingText、详细地址出域、向量接口被误判支持 filter。首次真实失败证明只测 Controller 会产生权限假阳性。endpoint-scoped 真实 SecurityFilterChain 与兼容检查是恢复业务服务和受控联调的前置，而非阻塞已完成 Python fake Adapter 的理由。

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计通过且获得实施授权后 |
| 当前允许实施范围 | 已批准的 endpoint-scoped 共享 converter 绑定、真实过滤链权限矩阵、detail/fallback 兼容测试及对应门禁复核 |
| 当前禁止动作 | 过滤链和兼容验证未通过前恢复真实 Employee/模型联调；新增业务接口/DTO、改全局 fallback、索引或数据修改 |

评审记录：当前大版本已通过独立分层与跨层评审；不继承旧版本评审过程。

## 11. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-EMP-101`; `CON-EMP-101` | `DR-EMP-101` | `IMPL-EMP-101`; `IMPL-EMP-102`; `IMPL-EMP-103` | `TEST-EMP-101`; `TEST-EMP-105` | `VAL-EMP-101` |
| `REQ-EMP-102` | `DR-EMP-102` | `IMPL-EMP-102`; `IMPL-EMP-103`; `IMPL-EMP-105` | `TEST-EMP-103` | `VAL-EMP-101` |
| `REQ-EMP-103` | `DR-EMP-103` | `IMPL-EMP-104`; `IMPL-EMP-108` | `TEST-EMP-102` | `VAL-EMP-103` |
| `REQ-EMP-103` | `DR-EMP-104` | `IMPL-EMP-103`; `IMPL-EMP-104` | `TEST-EMP-104` | `VAL-EMP-101` |
| `REQ-EMP-104`; `CON-EMP-102` | `DR-EMP-105` | `IMPL-EMP-106`; `IMPL-EMP-107`; `IMPL-EMP-109`; `IMPL-EMP-110` | `TEST-EMP-106` | `VAL-EMP-102` |
| `REQ-EMP-101` | `DR-EMP-106` | `IMPL-EMP-105` | `TEST-EMP-107` | `VAL-EMP-103` |
