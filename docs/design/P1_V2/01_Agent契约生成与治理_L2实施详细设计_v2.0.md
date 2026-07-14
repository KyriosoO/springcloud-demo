# Agent 契约生成与治理 L2 实施详细设计 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | Agent 契约生成与治理 L2 实施详细设计 |
| 文档路径 | `docs/design/P1_V2/01_Agent契约生成与治理_L2实施详细设计_v2.0.md` |
| 文档状态 | Implemented |
| 当前版本 | v2.0 |
| 创建日期 | 2026-07-13 |
| 最后更新日期 | 2026-07-14 |
| 适用代码基线 | `28e662a97110f7d3d39211f3ac841a39491fc1b8` |
| 适用范围 | Java Agent 公共契约、Runtime Route/Plan/Error 契约、OpenAPI、fixtures、Python 生成模型与 drift 门禁 |
| 上级文档 | 四份当前 L0/L1 架构基线（L0 + 三份单 Agent L1） |
| 合并来源 | P1/D01，以及 P1 中分页、排序、Document 对公共契约的有效增量 |
| 是否可作为实现依据 | 是；契约生成、OpenAPI/fixtures、Python 模型与 drift 门禁已完成本地实施和验证 |

## 2. 修订历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | P1_V2 仍需回查 D01 和多个专项文档才能理解公共契约 | 合并 Java 权威、Route/Plan/Error、OpenAPI、fixtures、Python 零补丁生成与 drift 规则 |
| 2 | 2026-07-13 | 第 1、10、11、19、20 节 | 对齐 L1 与当前 Java 权威契约，补齐可编码接口证据 | 修正 Route/Plan/Clarification/Error/Operation Metadata 字段；冻结 Runtime HTTP header、状态码和类型；将旧平行 RuntimeErrorResponse 纳入原子删除；补充精确测试落点 |
| 3 | 2026-07-13 | 第1～2、24节 | P1_V2/P2_V3全集终检需统一代码基线和实施状态 | 对齐统一代码基线，标记全集评审完成并保留 In Review、Approved 与 M0 边界；不新增评审轮次，不改变已通过设计结论 |
| 4 | 2026-07-14 | 第1～3、23～24节 | 当前仓库契约链已按 P1_V2 完成实施 | 对齐代码基线，确认 Java 唯一源、OpenAPI/fixtures、Python 生成模型和 Runtime Route/Plan 端点已闭合，将状态同步为 Implemented |

## 3. 文档状态说明

| 状态 | 含义 | 是否可作为开发依据 |
|---|---|---:|
| Draft | 草稿 | 否 |
| In Review | 评审中 | 否 |
| Approved | 已评审通过 | 是 |
| Implementing | 实施中 | 是 |
| Implemented | 已实施并完成对齐 | 是 |
| Deprecated | 已废弃 | 否 |

当前状态：Implemented。当前 Java/Runtime 契约、OpenAPI/fixtures、Python 生成模型与 drift 校验已完成本地实施和全量验证；生产发布仍需独立授权。

## 4. 背景与目标

Agent 的跨语言契约当前以 `agent-api` Java DTO 为源，通过测试侧 OpenAPI factory 生成 candidate artifact，再由 Python 脚本生成 Pydantic model。旧 D01 对该链路描述完整，但后续分页、排序、Document capability 又补充了新的公共字段。本文把当前仍需要的规则收敛为一个自包含契约基线，后续不再阅读旧 D01 或专项设计才能判断生成方向、兼容性和测试门禁。

## 5. 设计范围

### 5.1 范围内

- `ContractRef`、capability/context/result 公共契约；
- Runtime Route/Plan/Clarification/Error 结构；
- Query/Aggregate/Document plan 和 response DTO；
- sealed union、wire enum、严格 JSON 规则；
- Java→OpenAPI candidate→Python generated model 单向生成；
- positive/negative fixtures、contract drift 和 changed-path isolation；
- 分页上下文、排序、Document options 的公共字段治理。

### 5.2 范围外

- Runtime prompt/graph 算法；
- Capability Registration/Execution Core；
- 业务 Adapter DTO；
- provider 私有 HTTP 契约；
- 手工修改 Python generated model。

## 6. 上级文档约束

1. Java 是跨服务结构契约唯一事实源。
2. Runtime 只输出候选 Route/Plan/Clarification，不决定权限、Profile、Adapter 或 Result Security。
3. `capabilityId` 是授权、路由、执行和审计主键；`planKind` 只是结构类型。
4. 当前只启用 CHAT/ConversationScope；公共 Runtime DTO 不预建 TASK/Run 字段。
5. 新 capability 必须通过 sealed union/ContractRef/fixtures 扩展，不能自由 Map 穿透。
6. 未知 enum、discriminator、字段和 subtype 默认 fail closed。

## 7. 关联文档与边界

| 关联文档 | 本文职责 | 对方职责 | 边界 |
|---|---|---|---|
| P1_V2/02 | 提供稳定 Java/Runtime 公共结构 | Planning、Registration、Execution Core | Core 不定义 wire DTO |
| P1_V2/03 | 提供 Context/Result payload 契约 | 授权、Context、Mask、Result Security | 生成链不实现安全算法 |
| P1_V2/04 | 提供 Domain 投影和 Adapter role 契约 | Canonical metadata 与 binding | Contract 不保存业务配置事实 |
| P2_V3 | 提供 Document plan/result/options 公共类型 | Document 业务设计 | P2 不能手改 generated model |

旧 P1/P2/P2_V2 仅作为合并来源，不再是本文实施前置。

## 8. 设计边界与约束

- `agent-api` 不依赖 `agent-service`、Adapter、Runtime 或 Spring 实现。
- wire enum 必须有稳定字符串值；禁止依赖 ordinal。
- sealed union 必须有显式 discriminator，未知 subtype 拒绝。
- DTO 构造/反序列化只做结构级不变量；业务权限和 metadata 校验留给 Java Planning/Validator。
- OpenAPI candidate 位于 test resources，不作为生产 consumer 的动态输入。
- `generated_models.py` 只能由脚本覆盖，禁止语义补丁。
- 公共字段新增默认 optional；删除、重命名、收紧必填属于破坏性契约变更。

## 9. 总体设计

```text
agent-api Java DTO/enum/sealed union
  → AgentRuntimeContractOpenApiFactory
  → agent-runtime-openapi.json candidate
  → generate_contract_models.py
  → generated_models.py
  → Java fixtures + Python contract tests + check_contract_drift.py
```

生产调用链只消费已提交并通过测试的 Java/Python结构；运行时不读取 candidate OpenAPI 来决定行为。

## 10. 详细功能设计

### 10.1 公共契约世代与 ContractRef

`AgentRuntimeContract` 维护 generation/version 常量；`ContractRef` 使用稳定 `namespace/name/version`，禁止类名或对象地址进入 wire identity。`AgentExecutionContracts` 登记 Query/Aggregate/Document/Preview 的 input/output ContractRef。新增版本必须并存或显式迁移，不能静默复用旧 version 改语义。

### 10.2 Runtime Common

| 类型 | 必需语义 |
|---|---|
| `RuntimeOperationMetadata` | `operation`、`providerAttempts`、`repairAttempts`、`repairDurationMs`、`totalDurationMs`、`terminationReason`、`deadlineReached`、`repairLimitReached`；不含 prompt/token/diagnosticId |
| `RuntimeTurnProjection` | role、safe text、turn sequence；只含预算内历史 |
| `RuntimeProfileBehaviorProjection` | Profile 行为安全投影，不含凭据/权限全文 |
| `RuntimeCapabilityRoutingDescriptor` | capabilityId、planKind、domainMode、风险/执行模式安全投影 |
| `RuntimeDomainRoutingProjection` | domain、role、可用性和安全摘要 |
| `RuntimeDomainSchema/FieldSchema` | Java 允许的字段、类型、操作符、排序能力 |
| `RuntimeContextView` union | Query/Aggregate/Document 最小安全上下文；当前无 Run/Task view |

#### 10.2.1 Route/Plan wire 字段基线

以下字段名、Java 类型和 required/optional 是本版本实施基线；OpenAPI/Python 必须由这些 Java 类型生成，不得另行命名：

| 类型 | required 字段 | optional 字段 | 封闭性/校验 |
|---|---|---|---|
| `RouteRequest` | `requestId:String`、`contractVersion:String`、`message:String`、`history:List<RuntimeTurnProjection>`、`profileBehavior:RuntimeProfileBehaviorProjection`、`capabilities:List<RuntimeCapabilityRoutingDescriptor>`、`domains:List<RuntimeDomainRoutingProjection>`、`absoluteDeadline:Instant`、`repairLimit:Integer` | 无 | message 1～8000；history≤20；capabilities 非空且 capabilityId 唯一；repairLimit 0～3 |
| `RouteDecision` | `outcomeType=DECISION`、`requestId:String`、`capabilityId:String`、`metadata:RuntimeOperationMetadata` | `domain:String` | 只属于 `RouteOutcome`；domain 必须符合所选 Definition 的 Domain Mode |
| `ClarificationRequired` | `outcomeType=CLARIFICATION`、`requestId:String`、`reasonCode:ClarificationReasonCode`、`args:ClarificationArgs`、`metadata:RuntimeOperationMetadata` | 无 | 同时属于 Route/Plan outcome；不含 `question`、`safeMessage` 或自由文本 |
| `PlanRequest` | `requestId:String`、`contractVersion:String`、`message:String`、`history:List<RuntimeTurnProjection>`、`capabilityId:String`、`planKind:AgentPlanKind`、`capability:RuntimeCapabilityRoutingDescriptor`、`inputSchemaRef:String`、`contextViews:List<RuntimeContextView>`、`absoluteDeadline:Instant`、`repairLimit:Integer` | `domain:String`、`domainSchema:RuntimeDomainSchema` | requestId/deadline 与 Route 相同；history≤20；contextType 唯一；domain/schema 与 Domain Mode 一致 |
| `ExecutablePlan` | `outcomeType=EXECUTABLE`、`requestId:String`、`plan:AgentPlan`、`metadata:RuntimeOperationMetadata` | 无 | 只属于 `PlanOutcome`；AgentPlan 仅 QUERY/AGGREGATE/DOCUMENT |
| `RuntimeOperationMetadata` | `operation:RuntimeOperationType`、`providerAttempts:Integer`、`repairAttempts:Integer`、`repairDurationMs:Long`、`totalDurationMs:Long`、`terminationReason:RuntimeTerminationReason`、`deadlineReached:Boolean`、`repairLimitReached:Boolean` | 无 | 数值非负；repairAttempts≤max(providerAttempts-1,0)；合法 outcome/error 必须携带 |
| `RuntimeErrorResponse` | `code:RuntimeErrorCode`、`message:String`、`metadata:RuntimeOperationMetadata`、`diagnosticId:String` | `requestId:String` | 不含 `retryable`；重试不得由 Runtime 建议；解析前拿不到 requestId 时才允许为空 |

网络中断或无法解析响应时不存在合法 wire `RuntimeOperationMetadata`。Planning 侧只能形成内部本地观测，repair/provider 次数使用 `NOT_REPORTED` 等价缺失语义，不得构造全 0 wire metadata 冒充 Runtime 已报告。

### 10.3 Clarification

`ClarificationArgs` 是封闭 union：capability/domain/field/value choice 和 field forbidden。`ClarificationRequired` 必含 requestId、reasonCode、args 和 operation metadata，不含 `safeMessage` 或最终 question；用户提示由 Java Planning Service 使用安全模板形成。不得把异常文本、权限表达式或内部 class name 作为用户提示。新增 clarification subtype 必须更新 Java permits、OpenAPI discriminator、fixtures 和 Python tests。

### 10.4 Route

`RouteRequest` 输入 requestId、contractVersion、safe turn/profile/capability/domain projections、absoluteDeadline 和 repairLimit；`RouteDecision` 输出固定 outcomeType、requestId、capabilityId、可选 domain 和 operation metadata。Runtime 不能返回 Adapter bean、index/table、权限 scope 或 executable command。

### 10.5 Plan

`PlanRequest` 输入同一 requestId/contractVersion、选定 capability/domain、安全 schema/context、当前请求、absoluteDeadline 和 repairLimit。`AgentPlan` union 当前包含 `QueryAgentPlan`、`AggregateAgentPlan`、`DocumentAgentPlan`；`ExecutablePlan` 只表示 Runtime 结构候选，不等于 P1_V2/02 的可信 `ExecutablePlanningResult`。

Query 计划必须覆盖 filters/sorts/page/size/contextMode；Aggregate 覆盖 groupBy/metrics/order；Document 覆盖 operation/retrieval/generation/summary scope。字段/操作符/排序/profile 必须由 Java 再校验。

### 10.6 Runtime Error

`RuntimeErrorResponse` 固定 `code/message/metadata/diagnosticId` 和可选 `requestId`。不提供 `retryable`；HTTP/解析/契约错误先映射 `RuntimeErrorCode`，禁止将 Python traceback、provider body 或 prompt 透传给客户端。`agent-api.response.RuntimeErrorResponse` 是旧平行类型，必须由 P1_V2/06 在原子迁移中删除，运行链只允许 `agent-api.contract.runtime.error.RuntimeErrorResponse`。

### 10.7 Response 与内部候选隔离

`AgentChatResponse` 使用封闭 `AgentResultPayload`。`candidateAnswerText/candidateSummaryText/candidateSummaryBullets` 等内部候选字段必须 `@JsonIgnore` 或不属于公共 DTO；最终 answer/summary 只由 Result Security 写入。分页、排序和解析后的 query 参数通过明确字段返回，不依赖自由 metadata。

### 10.8 OpenAPI 生成

`AgentRuntimeContractOpenApiFactory` 只读取 Java 类型和显式 schema metadata，输出稳定排序的 OpenAPI 3.1 candidate。生成测试默认 drift-only；只有显式更新 candidate 时写文件，随后必须回到只读 drift 验证。

### 10.9 Golden Fixtures

至少保留 route request/decision/clarification、plan request、query/aggregate/document plan、plan clarification、runtime error positive fixtures，以及 unknown-plan-kind、unknown-operator、extra-field、missing-query、discriminator-mismatch negative fixtures。新增公共字段必须同步 positive fixture；破坏性拒绝必须有 negative fixture。

### 10.10 Python 零补丁生成

`generate_contract_models.py` 从 candidate OpenAPI 生成 `generated_models.py`；`models.py` 只能提供非语义 import/facade，不补字段、不改 enum、不放宽 extra。`check_contract_drift.py` 在临时目录重生成并逐字/规范化比较，发现手工修改直接失败。

### 10.11 Changed-path Isolation

契约生成变更必须限制在 Java 源契约、factory、candidate、fixtures、生成脚本和 Python generated/tests。若同一目标还修改 Planning/Core/权限算法，应拆成可独立评审的变更集合，避免契约 diff 隐藏行为变更；但不得独立发布或启用半套协议，最终运行切换仍由 P1_V2/06 作为一个纵向原子交付单元完成。

## 11. 接口设计

| 接口 | 方法/URI | 必需 Header | Request | 2xx Response | 错误状态/Body | 超时与重试 |
|---|---|---|---|---|---|---|
| Runtime Route | `POST /runtime/v1/route` | `Content-Type: application/json`、`X-Agent-Runtime-Key` | `RouteRequest` | `200 RouteOutcome` | `400 CONTRACT_INVALID`、`401 AUTHENTICATION_FAILED`、`422 OUTPUT_REPAIR_EXHAUSTED/其他受控规划错误`、`503 PROVIDER_UNAVAILABLE`、`504 DEADLINE_EXCEEDED`、`500 INTERNAL_ERROR`；body 均为 `RuntimeErrorResponse` | 使用 request absoluteDeadline；无隐藏重试；repair 仅在本 operation 内 |
| Runtime Plan | `POST /runtime/v1/plan` | `Content-Type: application/json`、`X-Agent-Runtime-Key` | `PlanRequest` | `200 PlanOutcome` | 与 Route 相同的状态码和 `RuntimeErrorResponse` 映射 | 使用同一 absoluteDeadline；无隐藏重试；repair 不得重跑 Route |

`X-Agent-Runtime-Key` 只承载内部服务认证，不转发用户 JWT。未知字段、未知 discriminator、缺失 required 字段或约束失败映射 `400 CONTRACT_INVALID`。Route/Plan 是 Agent Runtime 唯一业务端点；Document rewrite 不属于该 API，并由 P2_V3/06 迁出 Runtime。

## 12. 数据设计

| 数据 | 所有者 | 生命周期 | 约束 |
|---|---|---|---|
| Java DTO/enum | `agent-api` | 代码版本 | 唯一源 |
| OpenAPI candidate | `agent-api/src/test/resources/contract/openapi` | 版本控制 | 不被生产动态读取 |
| Golden fixtures | `agent-api/src/test/resources/contract/fixtures` | 版本控制 | 正负样例配对 |
| Python generated model | `agent-runtime/app/contracts/generated_models.py` | 生成产物 | 禁止手改 |

不新增数据库表、缓存或消息主题。

## 13. 状态流转设计

契约产物状态：`JAVA_SOURCE_CHANGED→OPENAPI_GENERATED→FIXTURES_VERIFIED→PYTHON_GENERATED→DRIFT_CLEAN→READY_FOR_REVIEW`。任一阶段失败不得跳过；`READY_FOR_REVIEW` 不等于文档 Approved 或运行时发布完成。

## 14. 幂等、事务与一致性设计

相同 Java 源和生成器版本必须生成字节稳定 candidate/model。生成写入采用临时文件后原子替换；测试不修改生产状态。Java/Python 无分布式事务，通过同一提交内的 source/candidate/generated/fixture 闭合保持一致。

## 15. 权限、风控与审计设计

- 生成脚本不读取生产凭据；
- Runtime 请求只接受内部服务身份；
- fixtures 不含真实用户、token、权限列表或业务敏感正文；
- CI 记录 generation/drift 结果，不输出完整 prompt/request；
- 公共错误和 clarification 使用安全 message allowlist。

## 16. 性能与容量设计

Runtime request 的 turns/context/schema/capability/domain 数量必须受 Planning input budget。OpenAPI/fixtures 是构建期小文件；生成时间目标为本地秒级。不得为规避模型大小而删除安全字段或放宽 strict schema。

## 17. 兼容性与扩展性设计

新增 capability/domain 通过现有 descriptors/sealed union 扩展；当前不加入 Multi-Agent DTO。optional 字段支持灰度读取，服务端写新字段前必须确保 Python model 已生成部署。删除字段需新 ContractRef/version 和显式迁移窗口。

## 18. 日志、监控与告警

构建指标：contract generation success、drift、fixture failure、unknown field/subtype。运行指标：Route/Plan contract rejection、error code、termination。禁止 userId/query/prompt 作为标签。

## 19. 实现落点清单

### 19.1 Java 实现落点

| 序号 | 路径 | 类/方法 | 入参 | 返回 | 动作 |
|---:|---|---|---|---|---|
| 1 | `agent-api/src/main/java/com/dylan/agent/api/contract/runtime/**` | Route/Plan/Common/Error/Clarification DTO | JSON/constructor fields | immutable DTO | 修改 |
| 2 | `agent-api/src/main/java/com/dylan/agent/api/contract/common/ContractRef.java` | constructor/accessors | namespace/name/version | `ContractRef` | 修改 |
| 3 | `agent-api/src/main/java/com/dylan/agent/api/response/**` | payload/result DTO | typed fields | DTO | 修改 |
| 4 | `agent-api/src/test/java/com/dylan/agent/api/contract/AgentRuntimeContractOpenApiFactory.java` | `build()` | Java schema registry | OpenAPI model | 修改 |
| 5 | 同测试包 | `AgentRuntimeContractOpenApiGenerationTest` | candidate path/mode | void | 修改 |
| 6 | `agent-api/src/main/java/com/dylan/agent/api/response/RuntimeErrorResponse.java` | 旧平行 Runtime error DTO | 无 | 无 | 由 P1_V2/06 原子删除；调用方迁移到 contract/runtime/error 类型 |

### 19.2 Python 实现落点

| 序号 | 路径 | 函数/类 | 入参 | 返回 | 动作 |
|---:|---|---|---|---|---|
| 1 | `agent-runtime/scripts/generate_contract_models.py` | `main/generate` | OpenAPI path/output path | generated Python | 修改 |
| 2 | `agent-runtime/scripts/check_contract_drift.py` | `main/check` | candidate/generated paths | exit code | 修改 |
| 3 | `agent-runtime/app/contracts/generated_models.py` | generated Pydantic models | JSON | typed model | 生成更新 |
| 4 | `agent-runtime/app/contracts/models.py` | import facade | generated types | re-export | 修改 |

### 19.3 脚本、契约与配置落点

| 类型 | 路径 | 产物/效果 |
|---|---|---|
| OpenAPI | `agent-api/src/test/resources/contract/openapi/agent-runtime-openapi.json` | candidate |
| Fixtures | `agent-api/src/test/resources/contract/fixtures/**` | 正负契约样例 |
| Maven | `serviceCenter/pom.xml`、`agent-api/pom.xml` | 测试/生成依赖，非必要不新增生产依赖 |

### 19.4 测试落点

| 路径/测试 | 核心用例 |
|---|---|
| `AgentRuntimeContractArchitectureTest` | 包依赖、sealed union、candidate 不进生产 consumer |
| `AgentRuntimeContractFixtureTest` | 全部 positive/negative fixtures |
| `AgentRuntimeContractOpenApiGenerationTest` | 稳定生成和 drift |
| `agent-runtime/tests/test_contracts.py` | generated model strict parsing |
| `agent-runtime/tests/test_runtime_api.py` | Route/Plan HTTP 契约 |
| `agent-runtime/tests/test_runtime_auth.py` | 缺失/错误 `X-Agent-Runtime-Key` 返回 401 typed error，且不进入 planner/provider |
| `AgentRuntimeContractArchitectureTest` + changed-path gate | 旧 `agent-api.response.RuntimeErrorResponse` 无引用且在原子迁移后不存在 |

## 20. 测试设计

- 单元：enum wire value、DTO invariants、ContractRef、sealed union。
- 契约：Java/Python 双端解析同一 fixtures。
- 异常：extra/unknown/missing/discriminator/error 安全映射。
- HTTP：Route/Plan header、400/401/422/500/503/504 与 `RuntimeErrorResponse` 一致；认证失败不进入 operation。
- 兼容：optional 新字段、旧 fixture、版本切换。
- 架构：Python generated 禁止手改、Runtime 仅 Route/Plan、agent-api 依赖方向。
- 回归：Query/Aggregate/Document/Preview response 序列化。

最小命令：`./serviceCenter/mvnw.cmd -f serviceCenter/pom.xml -pl agent-api -am test`、`python agent-runtime/scripts/check_contract_drift.py`、`python -m pytest agent-runtime/tests/test_contracts.py agent-runtime/tests/test_runtime_api.py`。

## 21. 风险与待确认事项

| 序号 | 类型 | 内容 | 影响 | 建议 | 是否阻塞 |
|---:|---|---|---|---|---:|
| 1 | 兼容 | 系统未投产但本地可能有旧 generated model | drift/fixture 失败 | 同一变更原子重生成 | 否 |
| 2 | 规模 | D01 旧文档包含大量脚本源码副本 | 新文档不再复制脚本全文 | 以仓库脚本为权威并保留接口/门禁 | 否 |

## 22. 评审记录

| 轮次 | 日期 | 结论 | 发现 | 修正 | 遗留 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | 通过 | 3 | 3 | 0 | 补齐分页/排序/Document 增量、Runtime 端点白名单和 generated candidate 隔离 |
| 2 | 2026-07-13 | 通过 | 5 | 5 | 0 | 对齐精确 wire 字段、HTTP header/status、Runtime error 唯一类型和原子切换边界；复审无 S0/S1 遗留 |

## 23. 实施对齐检查

| 检查 | 设计目标 | 当前实现 | 状态 |
|---|---|---|---|
| Java 唯一源 | agent-api | 已满足 | 是 |
| OpenAPI/fixtures | 稳定 candidate | 已按当前 Java 契约更新并通过测试 | 是 |
| Python 零补丁 | 脚本生成 | generated models 已更新且 Python 契约测试通过 | 是 |
| Runtime 端点 | 仅 Route/Plan | document rewrite 已迁出 Runtime | 是 |

## 24. 任务完成摘要

| 项目 | 内容 |
|---|---|
| 文档状态 | Implemented |
| 是否可作为实现依据 | 是 |
| 主要内容 | 自包含 Java/Runtime 公共契约、OpenAPI、fixtures、Python 生成和 drift 治理 |
| 是否需回查旧 P1 | 否；旧 D01/专项契约内容已合并 |
| 遗留风险 | 生产发布前仍需执行独立发布门禁；后续 Java 契约变化仍须持续执行 drift 门禁 |
