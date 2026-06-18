# 通用智能体 Agent 架构设计文档

> 项目：serviceCenter / agent-service / agent-runtime
> 文档版本：v1.6（架构与实施规格拆分版）
> 更新日期：2026-06-18
> 文档定位：描述长期目标、服务边界、Java/Python 分工、Adapter 原则、安全边界和演进路线；当前编码规格见 [agent查询功能实施设计_v1.0.md](./agent查询功能实施设计_v1.0.md)。

---

## 1. 文档边界

本文件是 Agent 的目标架构文档，不再同时承担当前迭代的类清单、DTO 定义、配置样例和数据库脚本。

两类文档的职责如下：

| 文档 | 负责内容 | 不负责内容 |
|---|---|---|
| 本架构文档 | 服务边界、职责分工、能力模型、扩展原则、安全原则、长期演进 | 当前迭代的完整类和方法清单 |
| 查询实施设计 | 当前 P0 的模块、DTO、接口、配置、表结构、调用链、测试和验收标准 | 提前设计后续写操作的全部实现类 |

拆分后的约束：

1. 架构文档允许描述未来能力，但不把未来能力标记为当前已实现。
2. 实施设计只包含本阶段必须编码的内容。
3. 新增能力先更新实施设计，再进入代码；只有服务边界或核心原则变化时才修改本文件。

---

## 2. 目标与原则

### 2.1 长期目标

在现有 serviceCenter 微服务体系中增加通用 Agent 能力，使自然语言请求能够被转换为受控计划，并通过业务服务完成查询、统计、修改、业务提交和工作流操作。

长期能力包括：

- 自然语言理解与反问。
- 多业务域查询和聚合。
- 基于结构化结果引用的多轮操作。
- LLM 摘要。
- 修改前的权限、影响数量、风险和确认。
- 业务命令、变更申请和工作流动作。
- 会话记忆、结果引用和审计。

这些能力按阶段交付，不要求在首期同时实现。

### 2.2 核心原则

1. Python 负责理解自然语言和生成计划，不直接执行业务。
2. Java 负责校验、权限、安全、业务调用和持久化，不依赖 LLM 决定能否执行。
3. Agent 不直接访问业务数据库，只调用业务服务公开接口。
4. Runtime 输出始终是不可信输入，必须经过 Java 校验。
5. 业务域通过 Adapter 接入，Agent 核心不包含 employee、transaction 等领域逻辑。
6. 字段配置是查询权限、输出过滤和脱敏的统一事实来源。
7. 写操作必须在 Java 侧完成影响评估、风险决策、用户确认和幂等控制。
8. 执行动作不能仅依赖自然语言摘要定位对象，必须使用机器可读的结构化引用。
9. 默认拒绝：未声明的 intent、domain、field、operator 和 action 均不可执行。
10. 当前阶段不为未来能力预建完整代码骨架。

---

## 3. 当前落地基线

首期只实现 Employee 查询与反问的垂直闭环：

```text
用户输入
  → agent-service 保存用户 Turn
  → agent-runtime 生成 QUERY 或 CLARIFY Plan
  → agent-service 校验 Plan
  → 校验 intent、字段和 operator 权限
  → Employee QueryableAdapter
  → employee-service /employees/es/search
  → 解析结果、字段过滤、脱敏
  → 保存基础 Turn
  → 返回页面
```

当前实施范围：

| 项目 | P0 |
|---|---|
| Intent | `QUERY`、`CLARIFY` |
| 业务域 | `employee` |
| Agent 入口 | `POST /agent/chat` |
| Runtime 入口 | `POST /runtime/v1/plans/generate` |
| 业务查询接口 | `POST /employees/es/search` |
| Adapter 能力 | `QueryableAdapter` |
| 权限 | intent、字段、operator |
| 安全 | JWT、输出字段过滤、脱敏 |
| 会话 | Conversation 与基础 Turn |
| 页面 | `/agent.html` |

当前明确不实现：

- `UPDATE`
- `AGGREGATE`
- `SUMMARY`
- `BUSINESS_SUBMIT`
- `WORKFLOW_ACTION`
- 风险评估、确认单、`executionId` 和业务幂等
- `ResultRef` 持久化
- 长期记忆
- transaction 域
- Runtime 摘要接口
- Java/Python 契约代码生成和 `schemaHash` 启动校验

---

## 4. 系统边界

### 4.1 服务关系

```text
Browser
  │ /agent.html、/agent/**
  ▼
gateway-service :8888
  │ JWT 校验和 Token 透传
  ▼
agent-service :9220
  ├── agent-runtime :9230
  │     └── 自然语言 → QUERY/CLARIFY Plan
  ├── employee-service :9210
  │     └── /employees/es/search
  └── MySQL
        └── Conversation / Turn
```

长期增加 transaction、workflow 或其他业务域时，仍由 `agent-service` 通过对应 Adapter 调用，不允许 `agent-runtime` 直接访问业务服务。

### 4.2 服务职责

| 职责 | agent-runtime | agent-service |
|---|---|---|
| 自然语言理解 | 是 | 否 |
| Intent 识别 | 生成候选结果 | 校验是否允许 |
| Plan 生成 | 是 | 归一化、校验或拒绝 |
| 反问文本生成 | 是 | 返回并持久化 |
| 身份认证 | 否 | 是 |
| Intent 权限 | 否 | 是 |
| 字段/operator 权限 | 否 | 是 |
| 字段过滤和脱敏 | 否 | 是 |
| Adapter 选择 | 否 | 是 |
| 业务服务调用 | 否 | 是 |
| 会话事实源 | 否 | 是 |
| 风控、确认和幂等 | 否 | 后续阶段由 Java 实现 |

边界不因后续能力增加而变化。

---

## 5. 能力模型

### 5.1 Intent

长期顶层 Intent 可演进为：

```text
CLARIFY
QUERY
AGGREGATE
SUMMARY
UPDATE
BUSINESS_SUBMIT
WORKFLOW_ACTION
```

Intent 表达用户目标，不表达具体执行方式。例如 `UPDATE` 只说明用户希望修改数据，最终走同步修改、变更申请还是工作流，由 Java 根据 Adapter 能力和风险规则决定。

当前 P0 只允许：

```text
CLARIFY
QUERY
```

Java 必须使用显式 allowlist 校验 Intent，不能因为枚举中存在未来值就允许执行。

### 5.2 Plan

Plan 是 Runtime 输出给 Java 的结构化候选计划，满足以下原则：

- 只描述用户意图和必要参数。
- 不携带最终权限结论。
- 不携带可信用户身份。
- 不携带 Java 已能从上下文获得的 operator。
- 不包含业务服务地址或任意脚本。
- 版本化，并保持向后兼容或显式拒绝。

### 5.3 Query 与 Clarify

`QUERY` 计划描述领域、过滤条件、返回字段和分页。

`CLARIFY` 计划描述需要向用户补充确认的问题。反问只用于补足语义，不用于绕过权限错误或业务异常。

---

## 6. Java 与 Python 分工

### 6.1 Python 端

`agent-runtime` 负责：

- 接收当前用户输入和有限的最近 Turn。
- 根据 Java 提供的领域字段描述理解用户表达。
- 输出 `QUERY` 或 `CLARIFY` Plan。
- 对 LLM 输出做 Pydantic 结构校验。
- 在输出无法修复时返回明确错误。

Python 不负责：

- JWT 解析和角色判定。
- 字段是否允许当前用户查询。
- operator 是否允许当前用户使用。
- 业务服务调用。
- 输出字段过滤和脱敏。
- 会话、结果、确认或审计持久化。
- 写操作的风险和幂等。

### 6.2 Java 端

`agent-service` 负责：

- 认证当前用户并解析角色。
- 管理 Conversation 和 Turn。
- 调用 Runtime。
- 校验 Plan 版本、Intent、Domain、字段、operator、值和分页。
- 执行权限判断。
- 选择 Adapter 并调用业务服务。
- 解析业务响应。
- 仅保留允许展示的字段并执行脱敏。
- 返回稳定的 Agent API 响应。

Java 不能把 Runtime 的“已授权”“低风险”或类似自然语言结论作为执行依据。

---

## 7. Adapter 架构

### 7.1 定位

Adapter 是 Agent 与业务域之间的防腐层：

```text
Agent Plan
  → 通用校验和权限
  → Domain Adapter
  → 业务服务 DTO/API
  → 通用 Agent Result
```

Agent 核心只理解通用 Plan 和通用结果，不理解 Employee ES DSL、Transaction condition 或 Workflow todo token。

### 7.2 当前接口

P0 只需要查询能力：

```java
public interface QueryableAdapter {
    String domain();

    AdapterQueryResult query(ValidatedQuery query, AgentUserContext userContext);
}
```

约束：

- `domain()` 必须唯一。
- Adapter 接收的是 Java 已校验的查询，不接收原始 LLM JSON。
- Adapter 只负责领域 DTO 映射、业务调用和响应解析。
- Adapter 返回仅供 Java 内部使用的 `AdapterQueryResult`；输出过滤和脱敏在统一结果处理层完成，不能依赖业务服务偶然不返回敏感字段。

### 7.3 后续扩展

后续阶段可按能力增加聚合、影响数量预估、修改、业务提交和工作流动作接口。扩展遵循能力接口组合，不要求所有 Adapter 实现一个包含全部方法的“大接口”。

新增能力时必须同时声明：

- 支持的 domain 和 intent。
- 输入字段和 operator。
- 业务接口和错误语义。
- 是否为读操作或写操作。
- 是否需要风险、确认和幂等。

---

## 8. 安全架构

### 8.1 身份来源

用户身份只来自 Gateway 校验并透传的 JWT。`operator`、`userId` 和角色不得从 Runtime Plan 或浏览器请求体中接受。

### 8.2 权限层次

权限按以下顺序执行：

```text
认证
  → Intent 权限
  → Domain 权限
  → 查询字段权限
  → Operator 权限
  → 展示字段权限
  → 脱敏
```

任一层失败即停止，不调用业务服务。

### 8.3 字段事实源

Java 字段策略至少包含：

- 字段名和自然语言别名。
- 可用于哪些 intent。
- 可使用的 operator。
- 哪些角色可作为查询条件。
- 哪些角色可查看结果。
- 脱敏类型。

Runtime 可以接收字段语义描述以提高 Plan 准确度，但 Java 配置仍是最终权限事实源。

### 8.4 输出安全

业务服务返回内容按不可信数据处理：

1. 解析业务响应。
2. 只提取允许返回的字段。
3. 对字段执行脱敏。
4. 限制行数和响应大小。
5. 禁止记录原始敏感响应。
6. 只向页面、Turn 摘要和未来结果快照传递过滤后的内容。

---

## 9. 会话、结果引用与记忆

### 9.1 P0 会话

P0 仅保存 Conversation 和基础 Turn，用于：

- 将用户对反问的回答与上一轮问题关联。
- 记录本轮请求、Intent、状态和助手文本。
- 支持故障排查。

P0 不把查询结果持久化为可再次执行的业务对象引用。

### 9.2 后续 ResultRef

当进入多轮查询和修改阶段时，引入 `ResultRef`：

- 由 Java 生成和持久化。
- 绑定 user、conversation、domain 和有效期。
- 保存结构化查询来源和必要的业务主键。
- 给 Runtime 只暴露有限摘要，不暴露未过滤原始数据。
- 修改、摘要等动作必须解析并校验 ResultRef，不能从 LLM 文本恢复目标对象。

### 9.3 长期记忆

长期记忆不是首期依赖。引入时由 Java 作为事实源管理，Python 仅接收经过筛选的运行时上下文。

---

## 10. 写操作的长期边界

写操作在后续阶段按以下链路实现：

```text
UPDATE/BUSINESS_SUBMIT/WORKFLOW_ACTION Plan
  → Java 结构校验
  → 字段和动作权限
  → 解析 ResultRef 或明确业务主键
  → 影响数量预估
  → 风险决策
  → 用户确认
  → 生成 executionId 并 claim
  → Adapter 调用业务服务
  → 记录执行状态和审计
```

关键约束：

- Python 不生成可信 `executionId`。
- 用户确认状态由 Java 持久化。
- 同一 `executionId` 只能执行一次。
- 异步受理必须返回 `SUBMITTED` 或 `PENDING_APPROVAL`，不能误报为已完成。
- 工作流 operator 始终由当前 JWT 用户注入。

本节只定义边界，不要求 P0 创建相关表、类或接口。

---

## 11. 契约治理

### 11.1 P0 策略

P0 的 Java DTO 和 Python Pydantic 模型只覆盖 `QUERY`、`CLARIFY`，采用小型手工维护契约：

- 使用固定 `planVersion`。
- 文档提供规范 JSON 示例。
- Java 和 Python 都用同一组行为场景做测试。
- Java 对未知字段和未知枚举值默认拒绝。

P0 不实现：

- Java/Python DTO 自动生成。
- 全量 JSON Schema 生成流水线。
- `contract-manifest.json`。
- `schemaHash` 启动校验。

### 11.2 引入代码生成的条件

仅当出现多个独立消费者、契约字段显著增加或手工同步已产生实际缺陷时，再评估契约生成。代码生成是治理工具，不是 Agent 查询闭环的前置条件。

---

## 12. 演进路线

| 阶段 | 能力 | 主要新增内容 |
|---|---|---|
| P0 | Employee 查询、反问、权限、脱敏 | QueryableAdapter、基础 Turn、查询页面 |
| P1 | Transaction 查询 | Transaction QueryableAdapter、字段策略 |
| P2 | 聚合查询 | Aggregate Plan、聚合权限、Aggregatable 能力 |
| P3 | ResultRef 和多轮查询 | 结果引用持久化、归属与有效期校验 |
| P4 | LLM 摘要 | 脱敏快照、摘要 Runtime API、来源关联 |
| P5 | 修改、影响数量、风控、确认 | 写能力 Adapter、风险矩阵、确认单、executionId |
| P6 | 业务提交与工作流动作 | 业务命令、变更申请、Workflow action 权限 |

每一阶段都必须形成独立可验收闭环，不把下一阶段的完整实现类提前加入当前代码。

---

## 13. 架构不变量

后续设计和代码评审必须保持以下不变量：

1. Runtime 不直接调用业务服务。
2. Runtime 输出必须经过 Java 校验。
3. 用户身份只来自认证上下文。
4. 未配置能力默认拒绝。
5. Adapter 不绕过业务服务访问业务库。
6. 原始业务结果必须先过滤和脱敏再返回或持久化。
7. 写操作必须在 Java 侧完成风险、确认和幂等。
8. 多轮执行必须使用结构化引用，不能依赖摘要文本。
9. 架构文档和当前实施规格分别维护。
10. 当前实现状态必须与文档明确区分。
