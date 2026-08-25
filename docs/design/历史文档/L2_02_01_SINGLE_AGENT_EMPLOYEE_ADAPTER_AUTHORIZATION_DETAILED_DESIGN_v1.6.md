# [L2_02_01] 单体 Agent Employee 条件/语义查询 Adapter 与授权详细设计

> 文档状态：Approved

## 1. 文档信息、上位约束与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v1.6 |
| 更新时间 | 2026-08-25 |
| 上位约束来源 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v1.4 |
| 关联责任边界 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v1.8 |

修订历史：本版将 Employee 目标从旧 detail 改为既有 ES search 与 semantic search 两个受控列表动作。

## 2. 设计目标、范围外与当前实现基线

目标复用 `EmployeeEsController.search` 和 `vectorSearch` 现有公开接口，分别提供 `employee.search`、`employee.semantic_search`，返回严格投影的员工列表。范围外包括新 endpoint/DTO、ES 直连、索引重建、聚合、写入、客户端二次筛选、自动互相 fallback 和启用 workBase 字段。

当前实现：Agent `adapters/employee` 只支持 `employee.detail`；ES 两个接口已存在，但都调用 `requireUser` 而不是 `requireEmployeeRead`；原始响应为 `String`。新 Adapter、ES 响应 codec、字段配置及最终读取授权均未实施。

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
| `employee.search` | `POST /employees/es/search` | `SearchRequest/SearchFilter/SearchSort` | keyword、filter、from/size、sort；可含 aggregate 但 Agent 禁止 | `requireUser` |
| `employee.semantic_search` | `POST /employees/es/vector-search` | `SemanticSearchRequest` | queryText、embeddingField、embeddingDims、k、numCandidates、trackTotalHits；没有 filter | `requireUser` |

`EmployeeEsService.SEARCHABLE_FIELDS` 当前包括 `contactAddress/chineseName/idCardNo/memberNo/phoneNo/email/position/workBaseSi`；其中 workBaseSi 因无有效数据而禁止，workBaseAf 也不能成为开放字段。`keyword` multi-match 仅包括 `contactAddress/chineseName/idCardNo`。普通搜索 operator 现有归一化支持 `eq/contains/prefix/in` 及别名，但 Agent 只生成有限 canonical operator。

`buildEmbeddingText` 拼接姓名、联系地址、职位、学历、院校、专业、workBaseSi、workBaseAf。它表明现有 embedding 的历史组成，不代表支持按其中任一单字段独立向量检索；workBase 两字段仍不开放。依赖方向为 Business validated plan → Employee Adapter → EmployeeEsController → EmployeeEsService；禁止绕过 Controller/业务权限访问 ES。

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

workBase 字段禁止出现在 query fields、result fields、模型目录、成功 UAT 或 semantic 可声明字段；发现 `workBaseSi/workBaseAf/work_base_si/work_base_af` 时返回 unsupported 且业务调用为 0。现有 ES `_source.workBaseSi` 必须被丢弃。

## 5. 请求/响应处理流程与接口契约设计

### 5.1 employee.search

```json
{"domain":"employee","action":"employee.search","arguments":{"filters":[{"field":"contact_address","operator":"contains","value":{"literal":"上海"}}],"page":1,"size":20,"sorts":[]}}
```

Adapter 固定映射为现有 `SearchRequest`：`filters[].field=contactAddress`、`operator=contains`、`value=上海`；`from=(page-1)*size`、`size≤50`，sort 字段和方向仅取已验证允许集合。keyword 可选，但必须按现有三字段 multi-match 行为解释，不能伪称所有字段模糊匹配。aggregate 必须始终不存在；filters 或 keyword 至少存在一个，避免默认 match_all。

`in` 值映射至现有 `SearchFilter.values`；敏感字段的多值集合必须由 protected slot 提供。禁止 DTO 字段名、ES DSL 和 raw query 进入模型。

### 5.2 employee.semantic_search

arguments exact 为 `query/size`；query 是安全业务文本 tagged literal，`1≤size≤50`。Adapter 固定映射为 `SemanticSearchRequest.queryText` 与 `k=size`；`embeddingField/embeddingDims/numCandidates/trackTotalHits` 仅来自代码绑定 finite profile，`queryVector` 始终不允许用户或模型输入。

当前 DTO 没有 `filters`，因此“语义能力匹配 + contact_address”等结构化约束必须 unsupported、调用 0；不得普通搜索后客户端过滤，不得一次请求执行 search 再 vector-search。语义请求包含姓名、手机号、详细地址等敏感值时拒绝，不得将 protected slot 解包到 embedding query。

### 5.3 bounded ES hits 响应

只接受固定 allowlist 的 JSON-compatible content-type：`application/json`、`application/*+json` 或既有 String Controller 的 `text/plain` 且 UTF-8；拒绝缺失类型、HTML 和非 UTF-8。复用现有最大响应字节上界 1 MiB，strict JSON decoder 拒绝重复键、非有限数值和非法 hits 结构；rows 数量不得超过请求 size。

仅提取 `_source` 已允许七个业务字段；丢弃未知字段、`workBaseSi/workBaseAf`、`embedding`、`embeddingText`、`operTime` 以及 ES 索引/score 元数据。`hits.total.relation=eq/gte` 分别映射 `totalExact=true/false`；无法证明 total 形状时返回 `invalid_response`，不得将原始 ES JSON 转发到用户或模型。

## 6. 最终读取授权、权限与审计设计

建议修改现有 `EmployeeEsController.search(...)` 和 `vectorSearch(...)`，将 `accessGuard.requireUser(authentication)` 替换为现有 `accessGuard.requireEmployeeRead(authentication)`；不增加 endpoint、DTO、权限角色或新 dependency。

这是现有公开接口授权收紧，必须先列出调用方、确认 ADMIN/VIEWER 与现有合法调用兼容，再用 Java MVC/security 测试覆盖 ADMIN/VIEWER 允许，非读取角色、service token、missing/malformed token 拒绝，以及原 endpoint/DTO/响应行为不变。如调用方兼容性不能证明，该切换及真实 Employee 联调保持阻塞。

JWT 只透传业务服务，Agent 不根据角色放行业务。审计只记录 action、snapshot、有限 HTTP 状态和调用数；员工姓名、标识、地址、电话、邮箱、JWT 和 raw hits 永不写日志或 evidence。

## 7. 实现落点清单

| 实现编号 | 位置 | 目标职责 |
|---|---|---|
| `IMPL-EMP-101` | `agent-runtime/src/agent_runtime/adapters/employee/contracts.py` | search/semantic 输入、ES hits 和列表记录强类型合同 |
| `IMPL-EMP-102` | `agent-runtime/src/agent_runtime/adapters/employee/definition.py` | 两个 action definition、field/operator、固定 endpoint |
| `IMPL-EMP-103` | `agent-runtime/src/agent_runtime/adapters/employee/codec.py` | SearchRequest/SemanticSearchRequest 固定 mapper 和 bounded ES response codec |
| `IMPL-EMP-104` | `agent-runtime/src/agent_runtime/adapters/employee/fields.py` | 七字段分类、用户脱敏、模型默认拒绝、移除 workBase 目标可见性 |
| `IMPL-EMP-105` | `agent-runtime/src/agent_runtime/adapters/employee/provider.py` | 组装 search/semantic 两个固定 provider，不恢复 detail 目标绑定 |
| `IMPL-EMP-106` | `employee-service/src/main/java/com/dylan/employee/controller/EmployeeEsController.java` | 建议收紧两个既有 endpoint 为 `requireEmployeeRead`，先核实调用方兼容 |
| `IMPL-EMP-107` | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java` | 复用已存在的最终读取守卫，不扩展角色 |
| `IMPL-EMP-108` | `agent-runtime/src/agent_runtime/adapters/employee/protected_input.py` | 姓名/标识/联系方式/详细地址 request-local slots |

## 8. 测试与验证设计

| 测试编号 | 场景 |
|---|---|
| `TEST-EMP-101` | 上海地址 contains、position eq/contains、keyword 真实三字段语义 |
| `TEST-EMP-102` | 姓名/标识 protected ref、个人字段模型零泄漏、workBase unsupported |
| `TEST-EMP-103` | Semantic queryText/k/profile，vector/physical 字段拒绝、semantic+filter 调用 0 |
| `TEST-EMP-104` | ES content-type、1 MiB、duplicate key、hits shape、unknown/embedding/workBase 丢弃 |
| `TEST-EMP-105` | page/from overflow、size、sort、in 上限及 aggregate 禁止 |
| `TEST-EMP-106` | Java ADMIN/VIEWER、denied/missing/malformed/service-token 和历史调用方回归 |
| `TEST-EMP-107` | detail 调用方、兼容性和冻结历史证据核查；目标组合根不可达 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-EMP-101` | 两动作 fake server、strict contract、slot 与 ES hits 定向测试 |
| `VAL-EMP-102` | Employee controller/security Maven 测试和既有调用方兼容检查 |
| `VAL-EMP-103` | Business/Knowledge 回归、strict mypy、compileall 与零泄漏扫描 |

## 9. 设计规则、失败类型与数据生命周期

| 规则编号 | 设计规则 |
|---|---|
| `DR-EMP-101` | `employee.search` 仅复用现有 ES search，逻辑字段/operator 有限映射 |
| `DR-EMP-102` | `employee.semantic_search` 仅复用 vector-search，不支持结构化 filter 或用户 vector |
| `DR-EMP-103` | `contact_address → contactAddress`，workBase 永不成为本版 enabled 字段 |
| `DR-EMP-104` | bounded strict ES hits、字段白名单、敏感脱敏与模型出域默认拒绝 |
| `DR-EMP-105` | 最终 ADMIN/VIEWER 授权在 Employee 服务；授权收紧先证明调用方兼容 |
| `DR-EMP-106` | detail 为历史实现，迁移/删除前核查 caller、公共兼容和冻结 evidence |

错误分类：unsupported/invalid plan 在发送前业务调用 0；forbidden 为固定 endpoint 1 次；timeout/unavailable/invalid_response 不重试、不切换搜索方式。数据生命周期仅为 request 内存；不修改 Employee 数据、索引和历史 evidence。事务边界与一致性归 employee-service/ES；本版复用现有 endpoint/guard，属于最小必要变更，避免 DTO 膨胀和 Adapter 耦合泄漏。

## 10. 风险、评审记录与实现就绪判定

主要风险：ES 入口只有 requireUser、已有调用方可能依赖更宽授权、raw hits 带 embeddingText、详细地址出域、向量接口被误判支持 filter。Java security/兼容检查是业务服务切换前置，而非阻塞 Python fake Adapter 的理由。

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计通过且获得实施授权后 |
| 当前允许实施范围 | Employee 两动作 fake Adapter、codec、字段配置及授权兼容性只读核实 |
| 当前禁止动作 | 未确认兼容即启用守卫、真实 Employee/模型调用、新业务接口/DTO、索引或数据修改 |

评审记录：独立评审已确认接口复用、最终授权、ES 安全 parsing 与当前实现差距；批准不表示授权改造已完成。

## 11. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-EMP-101`; `CON-EMP-101` | `DR-EMP-101` | `IMPL-EMP-101`; `IMPL-EMP-102`; `IMPL-EMP-103` | `TEST-EMP-101`; `TEST-EMP-105` | `VAL-EMP-101` |
| `REQ-EMP-102` | `DR-EMP-102` | `IMPL-EMP-102`; `IMPL-EMP-103`; `IMPL-EMP-105` | `TEST-EMP-103` | `VAL-EMP-101` |
| `REQ-EMP-103` | `DR-EMP-103` | `IMPL-EMP-104`; `IMPL-EMP-108` | `TEST-EMP-102` | `VAL-EMP-103` |
| `REQ-EMP-103` | `DR-EMP-104` | `IMPL-EMP-103`; `IMPL-EMP-104` | `TEST-EMP-104` | `VAL-EMP-101` |
| `REQ-EMP-104`; `CON-EMP-102` | `DR-EMP-105` | `IMPL-EMP-106`; `IMPL-EMP-107` | `TEST-EMP-106` | `VAL-EMP-102` |
| `REQ-EMP-101` | `DR-EMP-106` | `IMPL-EMP-105` | `TEST-EMP-107` | `VAL-EMP-103` |
