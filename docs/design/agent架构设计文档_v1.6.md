# 通用智能体 Agent 架构设计文档

> 项目：serviceCenter / agent-service / agent-runtime  
> 文档版本：v1.7（通用架构重构版）  
> 更新日期：2026-06-22  
> 文档状态：历史架构参考（非权威）  
> 替代关系：L0 权威基线已迁移至 `Agent目标架构总览_v1.0.md`  
> 文档定位：保留早期通用 Agent 架构思路，供 L1/L2 拆分时参考，不再作为上位架构或直接编码基线。  
> 关联文档：当前阶段的编码、DTO、接口、配置、数据库脚本、测试、部署和既有系统改造，放入对应实施设计或集成说明，不在本文展开。

---

## 1. 文档边界

本文保留历史架构原则和服务边界作为参考；当前目标分层、概念、依赖方向和架构不变量以 `Agent目标架构总览_v1.0.md` 为准。本文不再独立批准实施或约束下位设计。

### 1.1 本文负责

| 类别 | 内容 |
|---|---|
| 架构目标 | 通用 Agent 要解决的问题、长期能力和交付边界 |
| 服务边界 | agent-service、agent-runtime、业务服务、网关和身份系统之间的职责关系 |
| 能力模型 | Intent、Plan、Query、Aggregate、Update、Workflow、ResultRef、Memory 等通用概念 |
| 分工原则 | Java 与 Python 的职责划分，LLM 与确定性系统的边界 |
| Adapter 原则 | 业务域接入方式、能力接口组合、领域防腐层职责 |
| 安全原则 | 身份来源、权限层次、默认拒绝、输出过滤、脱敏、审计和写操作控制 |
| 演进路线 | 从查询到聚合、结果引用、摘要、修改、业务提交和工作流的阶段规划 |
| 架构不变量 | 后续设计、编码和评审必须保持的约束 |

### 1.2 本文不负责

| 类别 | 应放入 |
|---|---|
| 当前 P0 具体 DTO、类、方法和包结构 | P0 实施设计 |
| 具体业务域字段、字段别名、字段权限和脱敏规则 | Domain Spec / 领域 Adapter 设计 |
| Employee、Transaction、Workflow 等具体业务接口映射 | 对应领域 Adapter 设计 |
| Gateway、Auth、Maven、Eureka、Config、数据库初始化等既有系统改造 | 集成改造说明 / 部署说明 |
| 前端 Demo 页面、接口示例、测试用例、启动顺序和验收脚本 | 实施设计 / 验收说明 |

### 1.3 文档治理约束

1. 架构文档可以描述未来能力，但不得把未来能力标记为当前已实现。
2. 当前阶段的实现规格必须由实施设计承载，不能反向污染架构文档。
3. 新增能力必须先形成独立实施设计，再进入代码。
4. 只有服务边界、核心原则、能力模型或架构不变量发生变化时，才修改本文。
5. 业务域示例可以出现，但只能作为“接入模式示例”，不能成为通用 Agent 架构的一部分。

---

## 2. 目标与非目标

### 2.1 长期目标

在现有微服务体系中增加通用 Agent 能力，使自然语言请求能够被转换为受控、可校验、可审计的结构化计划，并通过受控业务服务完成查询、统计、摘要、修改、业务提交和工作流操作。

长期能力包括：

- 自然语言理解与反问。
- 多业务域查询和聚合。
- 基于结构化结果引用的多轮操作。
- LLM 摘要与解释。
- 修改前的权限校验、影响数量预估、风险评估和用户确认。
- 业务命令、变更申请和工作流动作。
- 会话事实、结果引用、长期记忆和审计。
- 可扩展的 Domain Adapter 接入机制。

这些能力按阶段交付，不要求首期全部实现。

### 2.2 非目标

通用 Agent 架构不承担以下职责：

- 替代业务系统已有权限、事务、审计和数据一致性机制。
- 绕过业务服务直接访问业务数据库。
- 让 LLM 自行决定是否有权执行、是否低风险、是否可以提交。
- 依赖自然语言摘要定位待修改对象。
- 为尚未进入实施阶段的能力预建完整代码骨架。
- 在架构文档中固化某一个业务域的字段、接口、索引、DTO 或部署细节。

---

## 3. 核心原则

1. **Runtime 只理解语义，不执行业务。**  
   Python Runtime 负责自然语言理解和生成候选 Plan，不直接访问业务服务或业务数据库。

2. **Java 决定能否执行。**  
   Java 侧负责 Plan 校验、权限、安全、Adapter 选择、业务调用、结果处理、持久化和审计。

3. **Runtime 输出始终不可信。**  
   Runtime 输出必须被当作外部输入处理，Java 必须重新校验版本、Intent、Domain、字段、Operator、值、分页、动作和上下文引用。

4. **业务域通过 Adapter 接入。**  
   Agent 核心只理解通用 Plan 和通用结果，不包含具体业务域逻辑。

5. **不直接访问业务数据库。**  
   Agent 通过业务服务公开接口完成操作，业务系统仍是业务规则和数据一致性的事实源。

6. **权限与脱敏由 Java 配置和策略控制。**  
   字段权限、展示权限、脱敏规则、动作权限和风险策略不能由 LLM 决定。

7. **默认拒绝。**  
   未声明的 Intent、Domain、Field、Operator、Action、ResultRef 和 Adapter 能力一律拒绝。

8. **写操作必须受控。**  
   修改、提交和工作流动作必须经过影响评估、风险判断、用户确认和幂等控制。

9. **多轮执行必须使用结构化引用。**  
   “刚才那些人”“上一批结果”等表达不能仅靠文本恢复对象，必须解析到 Java 生成的 ResultRef。

10. **当前实现与长期目标必须明确区分。**  
    文档和代码都不得把未来阶段能力误标为当前可用。

---

## 4. 总体架构

### 4.1 逻辑视图

```text
User / UI / API Client
        │
        ▼
API Gateway / Identity Boundary
        │ 认证结果、Token 透传、安全入口
        ▼
agent-service
        ├─ Conversation / Turn / ResultRef / Audit
        ├─ Plan Validator
        ├─ Permission / Policy / Risk / Confirmation
        ├─ Adapter Registry
        ├─ Result Filter / Mask / Snapshot
        │
        ├──► agent-runtime
        │       └─ Natural Language → Candidate Plan
        │
        └──► Domain Adapters
                └─ Business Services
                        └─ Business Data Sources
```

### 4.2 边界说明

| 组件 | 角色 | 是否属于 Agent 核心 |
|---|---|---:|
| agent-service | Agent 编排、校验、权限、策略、Adapter 调用、会话和审计事实源 | 是 |
| agent-runtime | 自然语言理解、候选 Plan 生成、LLM 输出结构化校验 | 是 |
| agent-api / contract | Java 与 Runtime、前端/API 之间的稳定契约 | 是 |
| Domain Adapter | Agent 与具体业务域之间的防腐层 | 半核心：模式通用，实现属领域 |
| Business Service | 业务能力、业务规则、数据一致性和领域授权 | 否 |
| Gateway / Identity | 认证入口、Token 校验、流量入口保护 | 否，但属于安全边界 |
| UI / Demo Page | Agent 使用入口或演示界面 | 否 |
| Maven / Registry / Config / DB 初始化 | 工程与运行环境 | 否 |

### 4.3 运行链路抽象

```text
输入
  → 建立或加载会话
  → 构建 Runtime 请求上下文
  → Runtime 生成候选 Plan
  → Java 校验 Plan
  → Java 校验权限和策略
  → 选择 Domain Adapter
  → Adapter 调用业务服务
  → 结果过滤、脱敏、快照或引用生成
  → 持久化 Turn / ResultRef / Audit
  → 返回稳定响应
```

该链路适用于查询、聚合、摘要、修改、业务提交和工作流动作。不同能力的差异体现在 Plan 类型、Adapter 能力、风险策略和执行阶段。

---

## 5. 服务职责

### 5.1 agent-runtime

`agent-runtime` 负责：

- 接收当前用户输入和 Java 提供的有限上下文。
- 根据 Domain Schema 理解自然语言中的字段、条件、动作和目标。
- 输出候选 Plan。
- 对 LLM 输出做结构化校验和一次可控修复。
- 在无法生成合法 Plan 时返回明确错误或反问。

`agent-runtime` 不负责：

- 解析 JWT 或判断用户身份。
- 判断当前用户是否有字段、动作或结果访问权限。
- 调用业务服务。
- 持久化会话、结果、确认单或审计记录。
- 判断写操作风险和是否允许执行。
- 生成可信 executionId。
- 保存或直接读取长期记忆。

### 5.2 agent-service

`agent-service` 负责：

- 从认证上下文解析当前用户身份和角色。
- 管理 Conversation、Turn、ResultRef、Confirmation 和 Audit。
- 构建 Runtime 请求上下文。
- 调用 Runtime 并接收候选 Plan。
- 校验 Plan 版本、Intent、Domain、字段、Operator、值、分页、动作和引用。
- 执行 Intent、Domain、字段、展示、动作和结果引用权限判断。
- 根据 Adapter 能力选择业务域处理器。
- 调用业务服务并处理业务响应。
- 对输出字段进行过滤、脱敏和快照治理。
- 对写操作执行影响数量预估、风险决策、用户确认和幂等控制。
- 返回稳定、可审计、对前端友好的 Agent 响应。

### 5.3 Domain Adapter

Domain Adapter 负责：

- 声明所属 Domain。
- 声明支持的能力接口，例如查询、聚合、影响预估、修改、业务提交、工作流动作。
- 将通用 Validated Plan 映射为业务服务 DTO 或 API 请求。
- 调用业务服务。
- 将业务响应转换为通用 Agent 内部结果。
- 屏蔽业务接口、DTO、错误码和数据结构变化对 Agent 核心的影响。

Domain Adapter 不负责：

- 接收原始 LLM JSON。
- 代替 Java 做最终权限判断。
- 把未过滤的业务响应直接返回给页面。
- 绕过业务服务访问业务数据库。

### 5.4 外部系统

外部系统只提供 Agent 运行所需的边界能力：

| 外部系统 | 与 Agent 的关系 | 架构约束 |
|---|---|---|
| 身份系统 | 提供可信认证结果 | Agent 只信任认证上下文，不信任请求体身份字段 |
| 网关 | 暴露入口、透传认证、基础限流 | 网关保护不替代 Agent 内部权限 |
| 业务服务 | 执行业务查询、统计、修改、提交和工作流动作 | Agent 只通过 Adapter 调用公开接口 |
| 配置中心 | 提供运行配置 | 不承载 LLM 生成的动态权限结论 |
| 数据库 | 存储 Agent 会话、引用、确认和审计 | 不存储未过滤的原始业务响应 |

---

## 6. 能力模型

### 6.1 Intent

Intent 表达用户目标，不表达具体执行方式。长期顶层 Intent 可演进为：

```text
CLARIFY
QUERY
AGGREGATE
SUMMARY
UPDATE
BUSINESS_SUBMIT
WORKFLOW_ACTION
```

约束：

- 当前阶段只允许实施设计明确声明的 Intent。
- Java 必须使用显式 allowlist 校验 Intent。
- 枚举中存在未来值不代表当前允许执行。
- 同一 Intent 的最终执行方式由 Java 根据 Adapter 能力、权限和风险策略决定。

### 6.2 Plan

Plan 是 Runtime 输出给 Java 的结构化候选计划。

Plan 必须满足：

- 包含版本号。
- 包含 Intent 和 Domain。
- 只描述用户意图和必要参数。
- 不携带最终权限结论。
- 不携带可信用户身份。
- 不包含业务服务地址。
- 不包含脚本、SQL、DSL 或任意可执行代码。
- 不包含 Java 已能从上下文获得的可信执行者信息。

Plan 可以包含：

- 查询条件。
- 聚合维度和指标。
- 展示字段。
- 分页或结果限制。
- 业务动作名称。
- 结构化 ResultRef 引用。
- 反问问题。

### 6.3 Domain Schema

Domain Schema 是 Java 提供给 Runtime 的“语义辅助信息”，用于帮助 Runtime 把自然语言映射为规范字段和动作。

Domain Schema 可以包含：

- Domain 名称。
- 字段名。
- 字段自然语言别名。
- 字段可用 Operator。
- 支持的动作名称。
- 当前阶段允许的能力范围。

Domain Schema 不应包含：

- 当前用户角色。
- 当前用户最终权限结论。
- 脱敏规则。
- 风险规则。
- 业务服务地址。
- 数据库或索引结构。
- API key、Token 或内部密钥。

### 6.4 Query

`QUERY` 描述只读查询请求，包括 Domain、过滤条件、展示字段、分页和排序策略。

通用约束：

- 不允许无约束全量查询，除非实施设计明确允许并有额外限流。
- 查询字段、Operator、值、展示字段和分页必须由 Java 校验。
- 用户自定义排序必须独立声明能力和权限；未声明时不允许。
- Adapter 返回的原始结果不得直接对外输出。

### 6.5 Aggregate

`AGGREGATE` 描述统计请求，包括 Domain、过滤条件、分组维度和指标。

通用约束：

- 指标和维度必须来自 allowlist。
- 聚合结果仍需字段级展示权限和必要脱敏。
- 聚合不能绕过单条数据权限或租户边界。

### 6.6 Summary

`SUMMARY` 描述对已授权结果或结构化快照的摘要请求。

通用约束：

- 摘要输入必须来自 Java 过滤后的结果快照或受控 ResultRef。
- Runtime 不得接收未脱敏的原始业务响应，除非该字段已被明确授权用于摘要。
- 摘要必须保留来源引用，避免生成无法追踪的结论。

### 6.7 Update / Business Submit / Workflow Action

写操作类 Intent 只表达目标，不代表允许执行。

通用链路：

```text
写操作 Plan
  → Java 结构校验
  → 权限校验
  → ResultRef 或明确业务主键解析
  → 影响数量预估
  → 风险决策
  → 用户确认
  → executionId claim
  → Adapter 调用业务服务
  → 执行状态和审计记录
```

关键约束：

- Python 不生成可信 executionId。
- 用户确认状态由 Java 持久化。
- 同一 executionId 只能执行一次。
- 异步受理必须返回准确状态，不能误报完成。
- 工作流 operator 必须由认证上下文注入。

### 6.8 Clarify

`CLARIFY` 描述需要向用户补充的信息。

适用场景：

- 用户目标不完整。
- 字段明确但缺少值。
- 表达存在多种可能映射。
- 用户请求当前阶段不支持的能力。
- 用户引用了当前阶段无法解析的结果对象。

约束：

- 反问只用于补足语义，不用于绕过权限错误。
- 权限错误应由 Java 返回受控错误，而不是让 Runtime 反问。
- 反问文本可以由 Runtime 生成，但必须由 Java 持久化为 Turn 事实。

---

## 7. Java 与 Python 分工

| 职责 | agent-runtime | agent-service |
|---|---:|---:|
| 自然语言理解 | 是 | 否 |
| 候选 Intent 识别 | 是 | 校验 |
| 候选 Plan 生成 | 是 | 校验、归一化、拒绝 |
| 反问生成 | 是 | 返回、持久化 |
| 用户身份解析 | 否 | 是 |
| Intent 权限 | 否 | 是 |
| Domain 权限 | 否 | 是 |
| 字段和 Operator 权限 | 否 | 是 |
| ResultRef 归属校验 | 否 | 是 |
| 风险评估和确认 | 否 | 是 |
| 幂等控制 | 否 | 是 |
| Adapter 选择 | 否 | 是 |
| 业务服务调用 | 否 | 是 |
| 输出过滤和脱敏 | 否 | 是 |
| 会话、引用和审计持久化 | 否 | 是 |

Java 不能把 Runtime 的“已授权”“低风险”“已经确认”等自然语言或结构化字段作为执行依据。即使 Runtime 输出了类似字段，Java 也必须拒绝未知字段或忽略并记录契约漂移。

---

## 8. Adapter 架构

### 8.1 定位

Adapter 是 Agent 与业务域之间的防腐层。

```text
Candidate Plan
  → Java 校验为 Validated Plan
  → Domain Adapter
  → Business Service DTO/API
  → Business Response
  → Agent Internal Result
  → Result Processor
```

Agent 核心不理解具体业务域的内部 DTO、索引结构、数据库结构、工作流 token 或业务错误细节。

### 8.2 能力接口组合

Adapter 按能力拆分接口，而不是要求所有业务域实现一个大接口。

可演进能力接口包括：

| 能力接口 | 用途 |
|---|---|
| QueryableAdapter | 查询 |
| AggregatableAdapter | 聚合统计 |
| SummarizableSourceAdapter | 摘要输入快照提供 |
| ImpactEstimatableAdapter | 写操作影响数量预估 |
| UpdatableAdapter | 受控修改 |
| BusinessCommandAdapter | 业务提交、业务命令 |
| WorkflowActionAdapter | 工作流动作 |

约束：

- Adapter 只声明自己真实支持的能力。
- Agent 根据 Intent 和 Adapter 能力匹配执行链。
- 未实现的能力默认不可用。
- 新增能力必须配套实施设计、权限策略、错误语义和测试。

### 8.3 Domain Spec

每个业务域接入前必须提供 Domain Spec。

Domain Spec 至少包含：

- Domain 名称。
- 支持的 Intent。
- 字段列表、别名、类型和可用 Operator。
- 查询字段权限。
- 展示字段权限。
- 脱敏策略。
- 支持的动作。
- 动作权限。
- 风险规则。
- 业务接口映射。
- 错误语义。
- 是否读操作或写操作。
- 是否需要确认、审批或幂等。

Domain Spec 是领域接入文档，不应写入通用架构文档正文。

### 8.4 Adapter 输出约束

Adapter 输出只能进入 Agent 内部结果模型。对外响应必须经过统一 Result Processor。

统一处理顺序：

```text
Adapter Raw Result
  → 字段提取
  → 展示权限校验
  → 脱敏
  → 行数和大小限制
  → 快照或 ResultRef 生成
  → API Response / Summary Input / Audit
```

---

## 9. 安全架构

### 9.1 身份来源

用户身份只来自认证上下文。请求体、Runtime Plan、自然语言文本、前端隐藏字段中的 `userId`、`role`、`operator` 都不可信。

### 9.2 权限层次

权限按以下顺序执行：

```text
认证
  → Agent 入口权限
  → Intent 权限
  → Domain 权限
  → 字段/Operator 权限
  → 展示字段权限
  → ResultRef 归属权限
  → Action 权限
  → 风险策略
  → 用户确认
  → 输出过滤与脱敏
```

任一层失败即停止，不调用后续业务服务。

### 9.3 字段策略

字段策略是 Java 侧最终事实源，至少包含：

- 字段名。
- 自然语言别名。
- 支持的 Intent。
- 支持的 Operator。
- 查询权限。
- 展示权限。
- 脱敏类型。
- 是否可参与聚合。
- 是否可参与排序。
- 是否可用于摘要。
- 是否可修改。

Runtime 可以接收字段语义描述以提升 Plan 准确度，但不接收最终权限结论。

### 9.4 输出安全

所有业务服务返回内容都按不可信数据处理。

约束：

1. 禁止把原始业务响应直接返回浏览器。
2. 禁止把原始业务响应直接作为 LLM 摘要输入。
3. 禁止在日志中记录敏感字段原值、Token、API key 和内部密钥。
4. 输出前必须字段过滤和脱敏。
5. 响应行数、字段数和响应大小必须受限。
6. 查询结果如果需要多轮引用，必须生成结构化 ResultRef，而不是依赖文本摘要。

### 9.5 Runtime 安全

Runtime 是内部服务，不直接暴露给浏览器。

约束：

- Runtime 调用使用内部认证机制。
- agent-service 不向 Runtime 转发用户 JWT、Cookie 或角色。
- Runtime 日志不得记录完整敏感 Prompt、用户敏感值、LLM key 或内部共享密钥。
- Runtime 只能返回约定契约内字段。
- Runtime Provider 必须符合组织数据处理政策。

### 9.6 写操作安全

写操作必须满足：

- 明确目标对象。
- 明确动作和字段。
- 通过权限校验。
- 通过影响数量评估。
- 通过风险策略。
- 必要时通过用户确认或审批。
- 使用 Java 生成的 executionId 实现幂等。
- 记录执行审计。
- 不允许 Runtime 直接执行或绕过确认。

---

## 10. 会话、ResultRef 与记忆

### 10.1 Conversation 与 Turn

Conversation 表示一次多轮交互上下文。Turn 表示用户输入、Agent 响应和处理状态。

P0 起即可保存基础 Turn，用于：

- 支持反问后的语义补全。
- 记录本轮 Intent、状态和助手文本。
- 支持故障排查。

约束：

- Turn 不应长期保存敏感原始数据。
- Turn 不应保存未过滤的业务响应。
- 最近上下文传给 Runtime 前必须裁剪。
- 当前处理中的 Turn 不应作为已完成上下文参与下一次规划。

### 10.2 ResultRef

ResultRef 是多轮操作的结构化结果引用。

进入多轮查询、摘要和修改阶段后，必须引入 ResultRef：

- 由 Java 生成。
- 绑定 user、conversation、domain 和有效期。
- 保存结构化查询来源和必要业务主键。
- 只暴露有限摘要给 Runtime。
- 修改、摘要和后续查询必须解析并校验 ResultRef。
- 不能从自然语言文本恢复待操作对象。

### 10.3 Snapshot

Snapshot 是经过过滤和脱敏后的结果快照，可用于摘要、展示和审计。

约束：

- Snapshot 不等于原始业务响应。
- Snapshot 必须记录来源、生成时间、字段策略版本和访问边界。
- Snapshot 的持久化周期应短于或等于业务合规要求。

### 10.4 Long-term Memory

长期记忆不是首期依赖。引入时必须满足：

- Java 是事实源和治理入口。
- Python 只接收 Java 筛选后的运行时上下文。
- 用户偏好、业务事实、历史行为和系统规则必须分层存储。
- 敏感信息不能未经治理进入长期记忆。
- 记忆召回结果不能直接作为权限或执行依据。

---

## 11. 契约治理

### 11.1 契约类型

Agent 至少存在三类契约：

| 契约 | 说明 |
|---|---|
| Agent API Contract | 前端/API Client 与 agent-service 的接口契约 |
| Runtime Plan Contract | agent-service 与 agent-runtime 的 Plan 契约 |
| Domain Adapter Contract | agent-service 与具体业务 Adapter 的内部契约 |

### 11.2 P0 契约策略

P0 可以采用小型手工维护契约：

- 固定 Plan Version。
- Java DTO 与 Python Pydantic 模型手工对齐。
- 使用 Golden Fixture 和行为测试防止契约漂移。
- Java 与 Python 都拒绝未知字段和未知枚举。

### 11.3 代码生成引入条件

仅当出现以下情况时，再引入 JSON Schema、OpenAPI、代码生成或 schemaHash：

- 多个独立消费者同时依赖 Plan 契约。
- Plan 字段显著增加。
- 手工同步已经产生实际缺陷。
- 需要跨语言自动生成并强制版本校验。

代码生成是治理工具，不是首期查询闭环的前置条件。

---

## 12. 错误处理与观测

### 12.1 错误分类

Agent 错误应分为：

| 类型 | 示例 |
|---|---|
| 认证错误 | 未登录、Token 无效 |
| 权限错误 | Intent、Domain、字段、动作、ResultRef 无权限 |
| Plan 错误 | Runtime 输出非法、字段不存在、分页超限 |
| 业务错误 | 下游业务服务失败、业务规则拒绝 |
| Runtime 错误 | LLM Provider 超时、Runtime 不可用 |
| 系统一致性错误 | Turn 状态更新失败、幂等 claim 失败 |

错误响应必须对用户安全可理解，不能暴露堆栈、下游原始响应、Prompt、Token 或密钥。

### 12.2 日志原则

允许记录：

- conversationId。
- turnId。
- userId 或脱敏后的用户标识。
- intent。
- domain。
- 结果行数。
- 耗时。
- errorCode。

禁止记录：

- JWT、Cookie、API key、Runtime 内部密钥。
- 完整用户敏感输入。
- 敏感 filter 原值。
- 原始业务响应。
- 未脱敏 `_source` 或业务主键集合。
- LLM 完整 Prompt 和原始输出。

### 12.3 指标与追踪

建议观测指标：

- 请求量、成功率、错误率。
- Runtime 调用耗时和失败率。
- 各 Intent 分布。
- 各 Domain 分布。
- Adapter 调用耗时和失败率。
- Plan 校验失败原因。
- 权限拒绝原因。
- 写操作确认、拒绝和执行结果。

---

## 13. 阶段演进路线

| 阶段 | 能力 | 架构新增点 |
|---|---|---|
| P0 | 查询、反问、权限、脱敏 | QueryableAdapter、基础 Conversation/Turn、Plan 校验、结果过滤 |
| P1 | 多业务域查询 | 新 Domain Spec、新 QueryableAdapter、领域权限配置 |
| P2 | 聚合统计 | Aggregate Plan、AggregatableAdapter、维度/指标权限 |
| P3 | ResultRef 和多轮操作 | ResultRef 持久化、归属校验、有效期、结构化引用解析 |
| P4 | LLM 摘要 | 脱敏 Snapshot、Summary Plan、摘要 Runtime API、来源关联 |
| P5 | 修改、影响数量、风控、确认 | ImpactEstimatableAdapter、UpdatableAdapter、风险矩阵、确认单、executionId |
| P6 | 业务提交与工作流动作 | BusinessCommandAdapter、WorkflowActionAdapter、审批/待办权限、执行审计 |
| P7 | 长期记忆和个性化 | Memory Store、记忆治理、召回过滤、用户偏好上下文 |

每一阶段必须形成独立可验收闭环，不把下一阶段完整实现类提前加入当前代码。

---

## 14. 当前 P0 架构边界

P0 是通用 Agent 的第一个最小闭环，范围只应表达为能力边界，而不是把某个业务域写入架构核心。

P0 架构范围：

| 类别 | P0 范围 |
|---|---|
| Intent | CLARIFY、QUERY |
| Runtime | 自然语言到查询/反问候选 Plan |
| Java | Plan 校验、权限、Adapter 编排、结果过滤、脱敏、基础会话 |
| Adapter | 至少一个 QueryableAdapter 示例域 |
| 会话 | Conversation 与基础 Turn |
| 不实现 | UPDATE、AGGREGATE、SUMMARY、BUSINESS_SUBMIT、WORKFLOW_ACTION、ResultRef、长期记忆、风险确认、执行幂等 |

P0 的具体业务域、接口、字段、DTO、数据库脚本、测试用户、网关限流、前端页面和启动顺序应放入 P0 实施设计或集成说明。

---

## 15. 与实施文档的关系

架构文档与实施文档按以下边界维护：

```text
架构文档
  ├─ 说明为什么这样分层
  ├─ 定义哪些边界不能突破
  ├─ 定义能力如何演进
  └─ 定义安全和治理原则

实施设计
  ├─ 说明本阶段做什么
  ├─ 列出模块、类、方法、DTO、配置和数据库脚本
  ├─ 描述具体业务域接入
  ├─ 描述测试、部署、启动和验收
  └─ 记录既有系统需要如何配合改造
```

当实施设计发现需要突破架构不变量时，必须先评审并更新架构文档；当只是新增业务域、字段、接口或测试，则不应修改架构文档。

---

## 16. 架构不变量

后续设计、编码和评审必须保持以下不变量：

1. Runtime 不直接调用业务服务。
2. Runtime 输出必须经过 Java 校验。
3. 用户身份只来自认证上下文。
4. 请求体和自然语言中的身份、角色、operator 不可信。
5. 未配置能力默认拒绝。
6. Agent 不绕过业务服务访问业务数据库。
7. 业务响应必须先过滤和脱敏，再返回、摘要、持久化或引用。
8. 字段权限、动作权限、风险策略和脱敏规则由 Java 事实源控制。
9. 写操作必须在 Java 侧完成影响预估、风险判断、用户确认和幂等控制。
10. 多轮执行必须使用结构化 ResultRef，不能依赖摘要文本定位对象。
11. Runtime 不接收用户 JWT、Cookie、角色和最终权限结论。
12. Adapter 接收的是 Java 校验后的对象，不接收原始 LLM JSON。
13. 每个业务域能力必须通过 Domain Spec 声明后才能接入。
14. 当前实现状态必须与长期目标明确区分。
15. 架构文档不承载具体业务域实现、既有系统改造、启动部署和测试脚本。
