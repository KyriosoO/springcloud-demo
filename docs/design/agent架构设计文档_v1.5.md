# 通用智能体 Agent 架构设计文档

> 项目：serviceCenter / agent-service / agent-runtime  
> 目标版本：P0 设计版 v1.6  
> 生成日期：2026-06-16  
> 设计范围：基于现有 serviceCenter 微服务体系，新增 `agent-service(Spring Boot, port:9220)` 与 `agent-runtime(Python LangGraph, port:9230)`，接入现存 `employee` 与 `transaction` 两个业务域。  
> 设计原则：围绕 Agent 能力展开，保持业务解耦、执行可控、权限闭环、风控前置、确认后执行、审计预留、扩展最小但结构完整。
> v1.2 修订说明：将 Python 端从完整工程化拆分收敛为 P0 Slim 结构，保留 Java/Python 契约、Prompt 文件体系、Plan DSL 与 LangGraph 流程，删除 Python 侧过度拆分的 Task/Planner/Prompt 管理层。  
> v1.3 修订说明：Prompt 按意图拆分，补充 Java/Python 功能分界核查结论，并校正 Python 端 P0 Slim 文件结构，确保 Python 不越界承担权限、风控、确认、记忆、导出、审计或业务执行职责。  
> v1.4 修订说明：统一 Runtime 单一接口 `/runtime/v1/plans/generate`，统一 Java/Python Plan DSL，Python contracts 采用 B-lite 拆分，补齐 TargetType、FieldUsage、关键 DTO/Result/Context、配置属性类、workflow 域配置、MemorySearchStrategy 预留接口，并明确 LLM Provider 配置由 Python 管理。  
> v1.5 整理说明：删除“已确认设计决策”章节，统一标题层级与编号结构，清理决策编号引用，检查接口、文件结构、调用链和示例引用的一致性。
> v1.6 修订说明：收敛 P0 schema 到业务实际能力，明确上一轮结构化结果继承、执行结果状态模型、operator 注入边界、确认职责归属 Java，明确 Agent 模块为待新增平级模块，拆分 Adapter 能力接口，采用 Java/Python 契约文件与 schemaHash 启动校验保证一致性，并补充 workflow 二层 action 权限模型。文件名保留历史版本号，正文目标版本以本行声明为准。

---

## 1. 设计目标

### 1.1 P0 目标

新增一个可真实落地的通用 Agent 能力层，使用户可以通过自然语言完成以下能力：

1. 反问：当领域、字段、条件、目标动作不明确时，Agent 必须反问，不得猜测执行。
2. 查询：支持 employee、transaction 两个业务域查询。
3. 修改：修改前必须完成字段权限校验、影响数量预估、风险控制、用户确认；高风险需二次确认。
4. 聚合统计：支持 transaction 聚合统计，employee 可预留或通过 adapter 提供 count/分组统计。
5. 导出：支持查询结果导出，小数据同步，大数据异步任务。
6. 业务提交：支持提交业务变更、业务命令，是否进入 workflow 由 Java 执行层决策。
7. 工作流动作：支持处理已有流程实例、审批节点、待办任务。
8. 多轮对话：支持上一轮结构化查询结果继承、上一轮筛选条件继承、待确认计划恢复；执行类动作必须基于机器可读的 `LAST_RESULT/resultRef`，不得仅依赖 summarizer 文本。
9. 记忆：Java 统一持久化管理记忆，支持会话记忆和长期记忆基础模型。
10. 逻辑分支：由 LangGraph 编排反问、计划生成、结构修复、异常处理等自然语言理解分支；待确认计划的等待、恢复、过期和二次确认由 Java 侧管理。

### 1.2 非目标

P0 不实现以下内容：

1. 不实现真实审计落库，仅预留审计接口。
2. 不实现复杂向量长期记忆，仅预留 `MemorySearchStrategy` 扩展点。
3. 不让 Python 直接调用 employee、transaction、workflow 等业务服务。
4. 不让 Agent 绕过业务服务直接访问业务库。
5. 不实现多 Agent 协作，仅采用单 Agent + Adapter 扩展模式。
6. 不实现复杂策略引擎，风控采用配置化规则 + Java 决策链。

---

## 2. 与现有 serviceCenter 架构的关系

### 2.1 新增服务

| 服务 | 技术 | 端口 | 职责 |
|---|---|---:|---|
| `agent-service` | Spring Boot / Spring Cloud / OpenFeign | 9220 | Agent 统一入口、权限、风控、确认、记忆、导出、Adapter 执行。 |
| `agent-runtime` | Python / FastAPI / LangGraph | 9230 | 自然语言理解、意图识别、Plan DSL 生成、反问生成、逻辑分支。 |

### 2.2 调用关系

```text
Browser / Client
  ↓
gateway-service(:8888) /agent/**
  ↓
agent-service(:9220)
  ├── agent-runtime(:9230)                  // 语言理解、计划生成
  ├── employee-service(:9210)               // 员工查询、修改、变更申请
  ├── mq-procedure-service(:8182)           // transaction 查询、聚合、修改、业务命令
  ├── workflow-service(:9100)               // 工作流提交、审批、驳回、待办
  ├── es-query-service(:9201)               // 如需统一 ES 检索能力，可由业务 adapter 间接调用
  └── MySQL / Redis                         // Agent 会话、记忆、确认、导出任务
```

### 2.3 服务边界

| 边界 | Python agent-runtime | Java agent-service |
|---|---|---|
| 自然语言理解 | 是 | 否 |
| 意图识别 | 是 | 只校验 |
| Plan 生成 | 是 | 校验、修正、拒绝 |
| 反问生成 | 是 | 可包装返回 |
| LangGraph 逻辑分支 | 是 | 否 |
| 权限控制 | 否 | 是 |
| 字段脱敏 | 否 | 是 |
| 风险控制 | 否 | 是 |
| 影响数量预估 | 否 | 是，通过 Adapter |
| 用户确认 | 否 | 是 |
| 业务服务调用 | 否 | 是 |
| 导出任务 | 否 | 是 |
| 记忆事实源 | 否 | 是 |
| 审计预留 | 否 | 是 |

核心原则：**Python 生成计划，Java 决定能否执行及如何执行。**

---

## 3. Agent 能力模型

### 3.1 顶层 Intent

```java
public enum AgentIntent {
    CLARIFY,
    QUERY,
    UPDATE,
    AGGREGATE,
    EXPORT,
    BUSINESS_SUBMIT,
    WORKFLOW_ACTION,
    SUMMARY
}
```

| Intent | 用户目标 | 示例 | 处理方式 |
|---|---|---|---|
| `CLARIFY` | 反问 | “你是要查员工还是交易？” | 返回反问，不执行业务。 |
| `QUERY` | 查询业务数据 | “查岗位是 HRM 的员工” | 权限校验后查询。 |
| `UPDATE` | 修改业务数据 | “把张三岗位改成 HRBP” | 风控 + 确认 + 执行策略决策。 |
| `AGGREGATE` | 聚合统计 | “统计每种交易类型金额总和” | 调业务聚合接口。 |
| `EXPORT` | 导出结果 | “把刚才结果导出” | 复用上一轮结果 + 字段权限 + 导出任务。 |
| `BUSINESS_SUBMIT` | 提交业务动作、业务申请、业务变更 | “提交张三的岗位变更” | 由 Adapter 决定业务命令、变更申请或流程提交。 |
| `WORKFLOW_ACTION` | 操作已有流程、待办、审批节点 | “审批通过流程 123” | 调 workflow adapter。 |
| `SUMMARY` | 总结结果 | “总结刚才这些交易” | 对结果摘要处理，不修改业务。 |

### 3.1.1 Workflow 二层 Action

顶层 `AgentIntent` 不拆分为 `WORKFLOW_TODO / WORKFLOW_DETAIL / WORKFLOW_APPROVE / WORKFLOW_REJECT`，避免自然语言分类过细。工作流场景统一使用 `intent=WORKFLOW_ACTION`，再由 `WorkflowActionSpec.action` 表达二层动作。

```java
public enum AgentWorkflowAction {
    TODO,
    DETAIL,
    APPROVE,
    REJECT
}
```

| AgentWorkflowAction | 用户目标 | 执行性质 | 确认要求 |
|---|---|---|---|
| `TODO` | 查看当前用户待办 | 读操作 | 不需要确认 |
| `DETAIL` | 查看流程详情 | 读操作 | 不需要确认 |
| `APPROVE` | 审批通过流程或待办 | 写操作 | 必须确认 |
| `REJECT` | 驳回流程或待办 | 写操作 | 必须确认 |

`operator` 不由 Python 输出。Java 执行层必须从 `AgentUserContext.userId` 注入当前操作者，再调用 workflow-service。

`todoId` 由 workflow-service 在待办响应中生成，用于 Agent 多轮引用和待办定位。P0 中 `todoId` 不要求作为 workflow 持久化主键；它是 workflow-service 私有的不透明 token，Agent 不自行解析。只有 `todoId` 时，Agent 通过 `GET /workflows/todos/{todoId}?operator=currentUser` 回查当前待办；执行 `APPROVE/REJECT` 时，请求体携带 `operator=currentUser` 和原始 `todoId`，由 workflow-service 校验流程、节点和 operator 是否仍匹配。

### 3.2 底层 ExecutionMode

```java
public enum ExecutionMode {
    DIRECT_UPDATE,
    CHANGE_REQUEST,
    WORKFLOW_SUBMIT,
    BUSINESS_COMMAND,
    WORKFLOW_ACTION,
    QUERY,
    AGGREGATE,
    EXPORT_SYNC,
    EXPORT_ASYNC,
    SUMMARY,
    CLARIFY,
    BLOCKED
}
```

| ExecutionMode | 含义 |
|---|---|
| `DIRECT_UPDATE` | 调业务服务暴露的同步 update 接口，确认后直接写入并可返回影响结果。异步提交、审批申请或仅返回“已提交”的接口不得归类为 DIRECT_UPDATE。 |
| `CHANGE_REQUEST` | 创建业务变更申请，由业务域自行处理是否审批。 |
| `WORKFLOW_SUBMIT` | 向 workflow-service 发起流程。 |
| `BUSINESS_COMMAND` | 调用业务命令接口，例如提交交易、创建订单等。 |
| `WORKFLOW_ACTION` | 执行 workflow 二层动作。`TODO/DETAIL` 是只读动作，不需要确认；`APPROVE/REJECT` 是写动作，必须确认。 |
| `QUERY` | 查询执行。 |
| `AGGREGATE` | 聚合统计执行。 |
| `EXPORT_SYNC` | 小结果同步导出。 |
| `EXPORT_ASYNC` | 大结果异步导出任务。 |
| `CLARIFY` | 反问。 |
| `BLOCKED` | 风险、权限或能力不允许执行。 |

#### ExecutionStatus

```java
public enum ExecutionStatus {
    SUCCEEDED,
    SUBMITTED,
    PENDING_APPROVAL,
    FAILED,
    BLOCKED
}
```

用途：描述执行结果状态。`ExecutionMode` 表示“采用哪种执行方式”，`ExecutionStatus` 表示“执行后的业务状态”。例如异步交易更新可以是 `executionMode=BUSINESS_COMMAND` 且 `status=SUBMITTED`；员工变更申请可以是 `executionMode=CHANGE_REQUEST` 且 `status=PENDING_APPROVAL`。

### 3.3 Intent 与 ExecutionMode 的关系

```text
UPDATE
  ├── DIRECT_UPDATE
  ├── CHANGE_REQUEST
  ├── WORKFLOW_SUBMIT
  └── BLOCKED

BUSINESS_SUBMIT
  ├── BUSINESS_COMMAND
  ├── CHANGE_REQUEST
  ├── WORKFLOW_SUBMIT
  └── BLOCKED

WORKFLOW_ACTION
  ├── WORKFLOW_ACTION        # AgentWorkflowAction TODO / DETAIL / APPROVE / REJECT
  └── BLOCKED
```

顶层 Intent 按用户目标分类；底层 ExecutionMode 按执行方式分类。

---

## 4. 总体架构

```text
┌───────────────────────────────────────────────────────────────┐
│                         Client / Browser                       │
└───────────────────────────────┬───────────────────────────────┘
                                │ /agent/**
┌───────────────────────────────▼───────────────────────────────┐
│                      gateway-service :8888                     │
│  JWT 校验 / Cookie AUTH_TOKEN 提取 / Authorization 透传          │
└───────────────────────────────┬───────────────────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────┐
│                      agent-service :9220                       │
│                                                               │
│  Controller                                                    │
│    ├── AgentConversationController                             │
│    ├── AgentConfirmationController                             │
│    ├── AgentExportController                                   │
│    └── AgentMemoryController                                   │
│                                                               │
│  Core Service                                                  │
│    ├── AgentOrchestrator                                       │
│    ├── PlanValidationService                                   │
│    ├── FieldPolicyEvaluator                                    │
│    ├── RiskEvaluator                                           │
│    ├── ExecutionModeResolver                                   │
│    ├── ConfirmationService                                     │
│    ├── MemoryService                                           │
│    ├── ExportService                                           │
│    └── SummaryService                                          │
│                                                               │
│  Adapter                                                       │
│    ├── EmployeeAgentAdapter                                    │
│    ├── TransactionAgentAdapter                                 │
│    └── WorkflowAgentAdapter                                    │
└───────────────┬──────────────────────────────┬────────────────┘
                │                              │
                │ Plan Request                 │ Feign 调用业务服务
┌───────────────▼────────────────┐             │
│         agent-runtime :9230     │             │
│  FastAPI + LangGraph             │             │
│  - load_context_node            │             │
│  - understand_node               │             │
│  - clarify_node                  │             │
│  - plan_node                     │             │
│  - repair_node                   │             │
│  - finalize_node                 │             │
└─────────────────────────────────┘             │
                                                │
          ┌───────────────────────┬─────────────┴──────────────┐
          │                       │                            │
┌─────────▼─────────┐   ┌─────────▼─────────┐        ┌─────────▼─────────┐
│ employee-service  │   │ mq-procedure      │        │ workflow-service  │
│ :9210             │   │ :8182             │        │ :9100             │
└───────────────────┘   └───────────────────┘        └───────────────────┘
```

---

## 5. 项目结构

### 5.1 Maven 模块新增

目标结构如下。当前仓库已在 gateway 中预留 `/agent/**` 路由，但 `agent-api`、`agent-service`、`agent-runtime` 目录尚未落地，`serviceCenter/pom.xml` 尚未引入 Agent Maven 模块；以下为实现阶段需要新增的目标结构。

```text
D:\codex
 ├── serviceCenter          # Maven 父工程，目标新增 ../agent-api 与 ../agent-service 模块声明
 ├── agent-api              # 待新增：Agent DTO / Enum / 契约文件 / schemaHash
 ├── agent-service          # 待新增：Java Agent 主服务，端口 9220
 └── agent-runtime          # 待新增：Python LangGraph Runtime，端口 9230，非 Maven 模块
```

`agent-api` 与 `agent-service` 应在 `D:\codex` 下作为平级 Maven 模块新增，并通过 `serviceCenter/pom.xml` 的 `<modules>` 引入；`agent-runtime` 是平级 Python 目录，不加入 Maven reactor。

推荐采用 `agent-api`，理由：DTO、枚举和契约文件可作为 Java 侧权威定义；Java/Python 通过 `contract-manifest.json` 与 schemaHash 启动校验保证契约一致，后续其他服务也可理解 Agent Plan、确认、导出等契约。

### 5.2 agent-api 包结构

```text
agent-api
└── src/main/java/com/dylan/agent/api
    ├── enums
    ├── plan
    ├── request
    ├── response
    ├── memory
    ├── export
    ├── confirmation
    └── audit
```


### 5.3 agent-service 包结构

P0 阶段采用 MyBatis Mapper 直连持久化层，不单独设计 repository 包，避免在 `service → repository → mapper` 之间增加非必要层级。

```text
agent-service
└── src/main/java/com/dylan/agent
    ├── AgentServiceApplication.java
    ├── config
    ├── controller
    ├── core
    │   ├── orchestrator
    │   ├── validation
    │   ├── permission
    │   ├── risk
    │   ├── execution
    │   ├── confirmation
    │   ├── memory
    │   ├── export
    │   ├── summary
    │   ├── mask
    │   └── audit
    ├── adapter
    │   ├── spi
    │   ├── employee
    │   ├── transaction
    │   └── workflow
    ├── client
    │   ├── runtime
    │   ├── employee
    │   ├── transaction
    │   └── workflow
    ├── mapper
    ├── entity
    ├── dto
    └── exception
```

### 5.4 agent-runtime 包结构（P0 Slim + Intent Prompt + Generated Contracts）

Python 端采用 P0 Slim 结构。其职责是自然语言理解、反问判断、Plan DSL 生成、Plan 结构修复和 LangGraph 节点流转，不承担权限、风控、确认、记忆持久化、导出和业务服务调用。

结构说明：Python contracts 通过本地契约文件约束输入输出结构，不手写维护业务 schema、字段权限或 workflow action policy。Java 与 Python 各自保存同版本 `contract-manifest.json`，通过 schemaHash 启动校验保证一致性；业务 schema、字段权限、workflow action policy 的事实来源均在 Java。

```text
agent-runtime
├── pyproject.toml
├── README.md
├── .env.example
├── app
│   ├── __init__.py
│   ├── main.py                         # FastAPI 启动入口
│   ├── api
│   │   ├── __init__.py
│   │   └── runtime_api.py              # /runtime/v1/plans/generate
│   ├── contracts
│   │   ├── __init__.py                 # 聚合导出 generated 类型
│   │   ├── contract-manifest.json      # Python 侧契约版本与 schemaHash
│   │   ├── agent-plan.schema.json      # Python 侧契约文件
│   │   ├── runtime.schema.json         # Runtime 请求/响应契约文件
│   │   └── models.py                   # Pydantic 模型，需与契约文件一致
│   ├── core
│   │   ├── __init__.py
│   │   ├── graph.py                    # LangGraph 构建与运行入口
│   │   ├── graph_nodes.py              # P0 节点函数集中管理
│   │   ├── planning.py                 # Plan 结构校验、规范化、修复
│   │   ├── prompts.py                  # Prompt 文件加载、按 intent 选择、变量渲染
│   │   ├── llm_client.py               # LLM 调用封装
│   │   └── settings.py                 # 配置加载，LLM Provider 配置归属 Python
│   └── prompts
│       ├── system.md                   # 全局角色、边界、安全约束
│       ├── clarify.md                  # 反问生成规则
│       ├── repair.md                   # Plan 结构修复规则
│       └── intents                     # 按意图拆分的 Plan 生成规则
│           ├── query.md
│           ├── update.md
│           ├── aggregate.md
│           ├── export.md
│           ├── business_submit.md
│           ├── workflow_action.md
│           └── summary.md
└── tests
    ├── test_contracts.py               # 校验生成的 Pydantic 模型可解析 Java 契约样例
    ├── test_prompt_render.py           # Prompt 渲染测试
    └── test_plan_shape.py              # 各 intent 最小 Plan 结构测试
```

P0 不新增 Python 侧业务 adapter、记忆持久化、审计模块、导出模块和复杂 TaskRunner。后续如果 LangGraph 节点复杂化，可以再从 `graph_nodes.py` 拆出 `nodes/` 包；如果 prompt 复杂化，优先在 `prompts/intents/` 下继续按意图或领域子目录扩展，不改变 Python/Java 职责边界。Python Pydantic 模型可以手写或生成，但必须与本地契约文件和 Java 侧 manifest 的 schemaHash 一致。

### 5.5 文件结构与职责边界核查结论

经核查，当前文件结构按“Java 企业级治理 + Python 智能规划”的边界划分是合理的：

| 结构 | 核查结论 |
|---|---|
| `agent-api` | 作为 Java DTO、枚举和 Java 侧契约文件的权威定义；通过 contract manifest 与 Python 侧契约文件校验一致性。 |
| `agent-service` | 拆分 controller、orchestrator、validation、permission、risk、execution、confirmation、memory、export、mask、audit、adapter、client、mapper、entity，覆盖 Agent 执行闭环，合理。 |
| `agent-runtime/app/contracts` | 保留 Python 侧契约文件、contract manifest 与 Pydantic 模型，不扩展业务对象，合理。 |
| `agent-runtime/app/core` | 仅保留 graph、graph_nodes、planning、prompts、llm_client、settings 六个核心运行文件，保持轻量，合理。 |
| `agent-runtime/app/prompts/intents` | Prompt 按意图拆分，降低单个 prompt 复杂度，但不增加 Python 业务执行职责，合理。 |
| `agent-runtime/tests` | 用于保证契约文件、schemaHash、Pydantic 模型、Prompt 渲染与 Plan 最小结构不漂移，合理。 |

明确禁止的越界结构：

1. Python 不新增 `adapter/employee`、`adapter/transaction`、`adapter/workflow`。
2. Python 不新增 `repository`、`mapper`、`entity`。
3. Python 不实现 `RiskEvaluator`、`PermissionEvaluator`、`ExecutionModeResolver`。
4. Python 不保存长期记忆，不生成确认单，不创建导出任务，不记录审计事件。
5. Java 不直接写 prompt，不负责自然语言语义推理；Java 只校验、治理和执行 Python 输出的候选 Plan。

## 6. agent-api 详细类与方法结构


### 6.1 enums 包

#### `AgentIntent`

```java
public enum AgentIntent {
    CLARIFY,
    QUERY,
    UPDATE,
    AGGREGATE,
    EXPORT,
    BUSINESS_SUBMIT,
    WORKFLOW_ACTION,
    SUMMARY
}
```

用途：表示用户顶层目标。

#### `ExecutionMode`

```java
public enum ExecutionMode {
    DIRECT_UPDATE,
    CHANGE_REQUEST,
    WORKFLOW_SUBMIT,
    BUSINESS_COMMAND,
    WORKFLOW_ACTION,
    QUERY,
    AGGREGATE,
    EXPORT_SYNC,
    EXPORT_ASYNC,
    CLARIFY,
    BLOCKED
}
```

用途：表示 Java 执行层最终选择的执行策略。

#### `AgentWorkflowAction`

```java
public enum AgentWorkflowAction {
    TODO,
    DETAIL,
    APPROVE,
    REJECT
}
```

用途：表示 `WORKFLOW_ACTION` 下的 Agent 二层动作。命名带 `Agent` 前缀，避免与 workflow-api 现有 `WorkflowActionType(SUBMIT/APPROVE/REJECT)` 混淆。

#### `ExecutionStatus`

```java
public enum ExecutionStatus {
    SUCCEEDED,
    SUBMITTED,
    PENDING_APPROVAL,
    FAILED,
    BLOCKED
}
```

用途：表示执行后的当前业务状态，与 `ExecutionMode` 分离。

#### `TargetType`

```java
public enum TargetType {
    BUSINESS_OBJECT,
    BUSINESS_CHANGE,
    WORKFLOW_PROCESS,
    WORKFLOW_TODO,
    LAST_RESULT
}
```

用途：描述用户操作对象，用于区分业务对象、业务变更、流程实例、待办任务和上一轮结果。`TargetType` 不表示执行方式，而是帮助 Java 在后续执行链中区分业务提交与工作流动作。

| 值 | 含义 | 示例 |
|---|---|---|
| `BUSINESS_OBJECT` | 业务数据对象 | “查张三的信息”“修改这笔交易” |
| `BUSINESS_CHANGE` | 业务变更、业务申请 | “提交张三的岗位变更” |
| `WORKFLOW_PROCESS` | 已有流程实例 | “查看流程 123”“审批流程 123” |
| `WORKFLOW_TODO` | 待办任务、审批节点 | “处理我的待办”“驳回这个审批任务” |
| `LAST_RESULT` | 上一轮结果引用 | “导出刚才那些”“把刚才查到的人改掉” |

#### `FieldUsage`

```java
public enum FieldUsage {
    DISPLAY,
    QUERY,
    UPDATE,
    EXPORT,
    MASK
}
```

用途：描述字段使用场景。字段在展示、查询、修改、导出、脱敏场景下的权限可能不同，因此 `AgentPermissionService.allowField()` 必须带上 usage。

| 值 | 场景 | 对应字段契约 |
|---|---|---|
| `DISPLAY` | 返回给用户展示 | `show` |
| `QUERY` | 作为查询条件 | `queryable`、`allowedOperators` |
| `UPDATE` | 作为修改字段 | `writable`、`allowedActions` |
| `EXPORT` | 导出文件字段 | `exportable` |
| `MASK` | 输出脱敏 | `masked`、`maskType` |

#### `RiskDecision`

```java
public enum RiskDecision {
    CONFIRM_REQUIRED,
    DOUBLE_CONFIRM_REQUIRED,
    WORKFLOW_REQUIRED,
    BLOCKED
}
```

用途：表示风控结论。

#### `RiskLevel`

```java
public enum RiskLevel {
    LOW,
    MEDIUM,
    HIGH,
    CRITICAL
}
```

用途：字段或操作风险等级。

#### `ConfirmationStatus`

```java
public enum ConfirmationStatus {
    PENDING,
    CLAIMED,
    SUCCEEDED,
    FAILED,
    REJECTED,
    EXPIRED
}
```

用途：确认单状态。`CLAIMED` 表示确认单已通过 CAS 获取执行权并生成 `executionId`。

#### `MemoryScope`

```java
public enum MemoryScope {
    TURN,
    SESSION,
    LONG_TERM
}
```

用途：统一记忆模型中的作用域。

#### `MemoryType`

```java
public enum MemoryType {
    LAST_QUERY,
    LAST_RESULT,
    FIELD_ALIAS,
    DOMAIN_ALIAS,
    USER_PREFERENCE,
    SUMMARY,
    PENDING_PLAN
}
```

用途：记忆内容类型。

#### `MaskType`

```java
public enum MaskType {
    NONE,
    NAME,
    ID_CARD,
    MOBILE,
    EMAIL,
    AMOUNT,
    CUSTOM
}
```

用途：脱敏类型，支持通过类型注入脱敏逻辑。

---

### 6.2 plan 包

#### `AgentPlan`

```java
public class AgentPlan {
    private String planId;
    private String conversationId;
    private String domain;
    private AgentIntent intent;
    private TargetType targetType;
    private String resultRefId;
    private List<AgentFilter> filters;
    private List<AgentAction> actions;
    private AgentAggregate aggregate;
    private AgentExportSpec exportSpec;
    private WorkflowActionSpec workflowAction;
    private Boolean useLastResult;
    private Boolean requiresConfirmation;
    private Double confidence;
    private String reasoningSummary;
    private Map<String, Object> context;
}
```

| 方法 | 用途 |
|---|---|
| `getDomain()` | 获取业务域，如 `employee`、`transaction`、`workflow`。 |
| `getIntent()` | 获取顶层意图。 |
| `getTargetType()` | 获取用户操作对象类型。 |
| `getResultRefId()` | 获取上一轮结构化结果引用，用于“刚才那些”“他们”等多轮指代。 |
| `getFilters()` | 获取查询/修改条件。 |
| `getActions()` | 获取修改动作。 |
| `hasAction()` | 判断是否包含修改动作。 |
| `isWriteIntent()` | 判断是否为写操作，包括 UPDATE、BUSINESS_SUBMIT，以及 `WORKFLOW_ACTION` 下的 `APPROVE/REJECT`。 |

说明：DTO 不承载归一化行为。Plan 归一化统一由 `PlanNormalizeService` 处理。`targetType=LAST_RESULT` 时，必须提供 `resultRefId` 或 `useLastResult=true`，Java 侧从 `MemoryService` 读取结构化结果引用后再执行字段权限、影响数量、风控与确认。

#### `AgentFilter`

```java
public class AgentFilter {
    private String field;
    private String operator;
    private Object value;
    private List<Object> values;
}
```

| 方法 | 用途 |
|---|---|
| `isMultiValue()` | 判断是否为多值条件。 |

#### `AgentAction`

```java
public class AgentAction {
    private String field;
    private String operation;
    private Object value;
}
```

| 方法 | 用途 |
|---|---|
| `isSetAction()` | 判断是否为设置字段值。 |
| `isClearAction()` | 判断是否为清空字段值。 |
| `requiresValue()` | 判断动作是否需要 value。 |

#### `AgentAggregate`

```java
public class AgentAggregate {
    private List<String> groupBy;
    private List<AgentMetric> metrics;
}
```

| 方法 | 用途 |
|---|---|
| `hasGroupBy()` | 判断是否存在分组字段。 |
| `validateMetrics()` | 校验聚合指标结构。 |

#### `AgentMetric`

```java
public class AgentMetric {
    private String field;
    private String function;
    private String alias;
}
```

用途：描述 `SUM/AVG/MAX/MIN/COUNT` 等聚合指标。Agent 侧保持强类型，transaction adapter 负责转换为现有 `AggregateRequest.metrics` 字符串格式。

#### `AgentExportSpec`

```java
public class AgentExportSpec {
    private String format;
    private List<String> fields;
    private Boolean includeHeader;
    private Integer maxRows;
}
```

用途：导出请求参数。

#### `WorkflowActionSpec`

```java
public class WorkflowActionSpec {
    private AgentWorkflowAction action;
    private String processId;
    private String todoId;
    private String nodeId;
    private String reason;
}
```

用途：描述审批、驳回、查看待办等 workflow 动作。`action` 是 Agent 二层 workflow 动作枚举，取值为 `TODO/DETAIL/APPROVE/REJECT`。`todoId` 由 workflow-service 生成，用于多轮引用和待办定位；Agent 不解析该 token，只有 `todoId` 时通过 workflow-service 回查当前待办，执行 `APPROVE/REJECT` 时将 `operator=currentUser` 与原始 `todoId` 一并提交给 workflow-service 校验。`operator` 不属于 Plan 契约，Java 执行层必须以 `AgentUserContext.userId` 注入当前操作者，不要求也不允许 Python 根据用户文本生成操作者。

---

### 6.3 request 包

#### `AgentChatRequest`

```java
public class AgentChatRequest {
    private String conversationId;
    private String message;
    private String domainHint;
    private Map<String, Object> clientContext;
}
```

| 方法 | 用途 |
|---|---|
| `hasConversationId()` | 判断是否已有会话。 |
| `hasDomainHint()` | 判断前端是否指定领域。 |

#### `PlanGenerateRequest`

```java
public class PlanGenerateRequest {
    private String requestId;
    private String conversationId;
    private String turnId;
    private String userInput;
    private String locale;
    private AgentUserContext userContext;
    private MemoryRuntimeContext memoryContext;
    private List<DomainSchema> domainSchemas;
    private String contractVersion;
}
```

用途：Java 调 Python runtime 的请求体，包含用户输入、领域 schema、记忆摘要、用户上下文和契约版本。

#### `ConfirmExecutionRequest`

```java
public class ConfirmExecutionRequest {
    private String confirmationId;
    private String confirmText;
}
```

用途：用户确认执行。

#### `RejectExecutionRequest`

```java
public class RejectExecutionRequest {
    private String confirmationId;
    private String reason;
}
```

用途：用户拒绝执行。

---

### 6.4 response 包

#### `AgentChatResponse`

```java
public class AgentChatResponse {
    private String conversationId;
    private String message;
    private AgentIntent intent;
    private String domain;
    private Boolean requiresConfirmation;
    private String confirmationId;
    private Object data;
    private List<String> warnings;
}
```

用途：统一对话响应。

#### `PlanGenerateResponse`

```java
public class PlanGenerateResponse {
    private String requestId;
    private String conversationId;
    private String turnId;
    private String responseType;
    private AgentPlan plan;
    private ClarifyQuestion clarifyQuestion;
    private List<String> warnings;
    private String contractVersion;
}
```

用途：Python runtime 返回 Java 的结构化结果。`responseType=PLAN` 时 `plan` 非空；`responseType=CLARIFY` 时 `clarifyQuestion` 非空。

#### `AgentExecutionResult`

```java
public class AgentExecutionResult {
    private Boolean success;
    private ExecutionMode executionMode;
    private ExecutionStatus status;
    private String message;
    private Object data;
    private String businessId;
    private String businessRequestId;
    private String processId;
    private String trackingId;
    private List<String> warnings;
}
```

用途：执行结果。`success` 表示 Agent 执行链路是否成功完成提交或处理；`status` 表示业务侧最终或当前状态。异步提交、审批流和同步执行必须通过 `status`、`trackingId`、`businessRequestId`、`processId` 区分，避免把“已提交”误报为“已完成修改”。

#### `AgentQueryResult`

```java
public class AgentQueryResult {
    private List<Map<String, Object>> rows;
    private Long total;
    private Integer offset;
    private Integer size;
    private Boolean hasMore;
}
```

用途：查询结果。

---

### 6.5 memory 包

#### `MemoryItem`

```java
public class MemoryItem {
    private String id;
    private String userId;
    private String conversationId;
    private String domain;
    private MemoryScope scope;
    private MemoryType memoryType;
    private String memoryKey;
    private Object memoryValue;
    private String source;
    private Double confidence;
    private LocalDateTime expiresAt;
}
```

用途：统一记忆模型 DTO。

#### `MemoryWriteRequest`

```java
public class MemoryWriteRequest {
    private String domain;
    private MemoryScope scope;
    private MemoryType memoryType;
    private String memoryKey;
    private Object memoryValue;
    private Boolean userConfirmed;
}
```

用途：写入记忆。

---

### 6.6 export 包

#### `ExportTaskResponse`

```java
public class ExportTaskResponse {
    private String taskId;
    private String status;
    private String fileName;
    private String downloadUrl;
    private String message;
}
```

用途：导出任务响应。

#### `ExportTaskStatusResponse`

```java
public class ExportTaskStatusResponse {
    private String taskId;
    private String status;
    private Long totalRows;
    private Long exportedRows;
    private String fileName;
    private String downloadUrl;
    private String errorMessage;
}
```

用途：查询异步导出任务状态。

---

### 6.7 confirmation 包

#### `PendingConfirmation`

```java
public class PendingConfirmation {
    private String confirmationId;
    private String userId;
    private String conversationId;
    private AgentPlan plan;
    private ExecutionMode executionMode;
    private RiskDecision riskDecision;
    private Long affectedCount;
    private String summary;
    private ConfirmationStatus status;
    private String executionId;
    private LocalDateTime expiresAt;
}
```

用途：待确认执行单。`executionId` 在确认成功时生成，用于后续执行幂等。

#### `AgentExecutionContext`

```java
public class AgentExecutionContext {
    private String executionId;
    private String confirmationId;
    private String conversationId;
    private AgentPlan plan;
    private ExecutionMode executionMode;
    private AgentUserContext userContext;
}
```

用途：进入 dispatcher 执行链的统一上下文。所有经 `AgentExecutionDispatcher` 分发的执行路径都必须携带 `executionId`，并贯穿 dispatcher、adapter、审计和下游幂等。

`executionId` 生成规则：

1. 需要用户确认的执行路径，由 `ConfirmationService.confirmAndClaim()` 在确认单 `PENDING -> CLAIMED` CAS 成功时生成，并随 `ExecutionClaim` 返回。
2. 无需确认但仍经 dispatcher 执行的路径，由 agent-service 编排层在调用 `AgentExecutionDispatcher.dispatch()` 前直接生成，`confirmationId` 为空。
3. `executionId` 只由 Java 侧生成和传递，Python 不输出、不推断、不覆盖该字段。

#### `ExecutionClaim`

```java
public class ExecutionClaim {
    private String confirmationId;
    private String executionId;
    private AgentPlan plan;
    private ExecutionMode executionMode;
    private AgentUserContext userContext;
}
```

用途：`ConfirmationService.confirmAndClaim()` 的原子 claim 结果，用于组装 `AgentExecutionContext`。

---

### 6.8 audit 包

#### `AgentAuditEvent`

```java
public class AgentAuditEvent {
    private String eventId;
    private String userId;
    private String conversationId;
    private String eventType;
    private String domain;
    private AgentIntent intent;
    private ExecutionMode executionMode;
    private Object payload;
    private LocalDateTime createdAt;
}
```

用途：审计事件结构。P0 仅用于接口预留，不落库。


### 6.9 dto / support 包

以下类型用于补齐 controller、service、permission、validation、export、mask 等方法签名，保证类与方法结构闭合。

#### `AgentUserContext`

```java
public class AgentUserContext {
    private String userId;
    private List<String> roles;
    private String tenantId;
    private String authorization;
    private Boolean serviceToken;
}
```

用途：封装当前用户身份、角色、租户和 token 信息，供权限、风控、adapter 调用使用。

#### `PlanValidationResult`

```java
public class PlanValidationResult {
    private Boolean valid;
    private List<PlanValidationError> errors;
    private AgentPlan normalizedPlan;
}
```

用途：Plan 结构校验结果。

#### `PlanValidationError`

```java
public class PlanValidationError {
    private String field;
    private String code;
    private String message;
}
```

用途：描述 Plan 结构错误、缺字段、枚举不合法、条件冲突等问题。

#### `FieldPolicyResult`

```java
public class FieldPolicyResult {
    private Boolean allowed;
    private List<FieldDecision> decisions;
    private List<FieldPolicyViolation> violations;
}
```

用途：字段级权限与契约校验结果。

#### `FieldDecision`

```java
public class FieldDecision {
    private String domain;
    private String field;
    private FieldUsage usage;
    private Boolean allowed;
    private Boolean masked;
    private String maskType;
    private Boolean directUpdateAllowed;
    private Boolean workflowRequired;
    private Integer maxAffected;
    private RiskLevel riskLevel;
    private String reason;
}
```

用途：单个字段在具体使用场景下的决策结果。

#### `FieldPolicyViolation`

```java
public class FieldPolicyViolation {
    private String field;
    private FieldUsage usage;
    private String code;
    private String message;
}
```

用途：描述字段不可查、不可改、不可导出、operator/action 不允许等问题。

#### `ConversationDetailResponse`

```java
public class ConversationDetailResponse {
    private String conversationId;
    private String userId;
    private String title;
    private String status;
    private List<AgentTurnItem> turns;
}
```

用途：返回会话详情，用于前端恢复上下文。

#### `AgentTurnItem`

```java
public class AgentTurnItem {
    private String turnId;
    private String role;
    private String message;
    private AgentPlan plan;
    private Object result;
    private LocalDateTime createdAt;
}
```

用途：会话轮次展示 DTO。

#### `MemoryQueryRequest`

```java
public class MemoryQueryRequest {
    private String conversationId;
    private String domain;
    private MemoryScope scope;
    private MemoryType memoryType;
}
```

用途：查询当前用户记忆。

#### `MemoryRuntimeContext`

```java
public class MemoryRuntimeContext {
    private Map<String, Object> lastQuery;
    private Map<String, Object> lastResultRef;
    private Map<String, String> aliases;
    private Map<String, Object> preferences;
}
```

用途：Java 传给 Python 的最小记忆摘要。Python 只读，不作为记忆事实源。

#### `ClarifyQuestion`

```java
public class ClarifyQuestion {
    private String question;
    private List<String> missingFields;
    private List<String> options;
}
```

用途：Python 反问输出。

#### `DomainSchema` / `FieldSchema`

```java
public class DomainSchema {
    private String domain;
    private String displayName;
    private List<AgentIntent> supportedIntents;
    private List<FieldSchema> fields;
    private List<WorkflowActionSchema> workflowActions;
}

public class FieldSchema {
    private String name;
    private String displayName;
    private Boolean queryable;
    private Boolean writable;
    private Boolean exportable;
    private List<String> operators;
    private List<String> actions;
}
```

```java
public class WorkflowActionSchema {
    private AgentWorkflowAction action;
    private Boolean readOnly;
    private Boolean requiresConfirmation;
    private List<String> requiredRoles;
    private List<String> requiredContext;
    private List<List<String>> requiredAnyOf;
    private String operatorSource;
}
```

用途：Java 根据配置生成并传给 Python 的领域 schema。Python 只能在 schema 范围内生成候选 Plan。`workflowActions` 仅用于 `domain=workflow`，表达二层 action 的可用性、必需上下文、角色要求和确认建议；最终权限、确认与执行仍由 Java 校验。

`requiredContext` 表示必须全部存在的上下文字段；`requiredAnyOf` 表示多组上下文字段二选一或多选一。例如 `[[processId], [todoId]]` 表示可以通过流程号执行，也可以只带待办号，由 Java 先调用 workflow-service 的 todo resolve API 回查流程。

#### `MaskContext`

```java
public class MaskContext {
    private String userId;
    private String domain;
    private String field;
    private FieldUsage usage;
}
```

用途：脱敏器执行上下文。

#### `ExportWriteContext`

```java
public class ExportWriteContext {
    private String taskId;
    private String userId;
    private String domain;
    private String format;
    private Path baseDir;
}
```

用途：导出文件写入上下文。

---

## 7. agent-service 详细类与方法结构

### 7.1 启动类

#### `AgentServiceApplication`

```java
@SpringBootApplication
@EnableDiscoveryClient
@EnableFeignClients
@ConfigurationPropertiesScan
public class AgentServiceApplication {
    public static void main(String[] args);
}
```

| 方法 | 用途 |
|---|---|
| `main(String[] args)` | 启动 agent-service。 |

---

### 7.2 config 包

#### `AgentProperties`

```java
@ConfigurationProperties(prefix = "agent")
public class AgentProperties {
    private RuntimeProperties runtime;
    private Map<String, AgentDomainProperties> domains;
    private ExportProperties export;
    private MemoryProperties memory;
}
```

| 方法 | 用途 |
|---|---|
| `getDomain(String domain)` | 获取业务域配置。 |
| `isDomainEnabled(String domain)` | 判断领域是否启用。 |

#### `AgentDomainProperties`

```java
public class AgentDomainProperties {
    private Boolean enabled;
    private String displayName;
    private Map<String, AgentFieldProperties> fields;
    private AgentRiskProperties risk;
    private AgentRoleProperties roles;
    private Map<AgentWorkflowAction, WorkflowActionProperties> workflowActions;
}
```

| 方法 | 用途 |
|---|---|
| `getField(String field)` | 获取字段契约。 |
| `hasField(String field)` | 判断字段是否存在于契约。 |

#### `AgentFieldProperties`

```java
public class AgentFieldProperties {
    private Boolean show;
    private Boolean queryable;
    private Boolean writable;
    private Boolean exportable;
    private Boolean masked;
    private String maskType;
    private String riskLevel;
    private Boolean directUpdateAllowed;
    private Boolean workflowRequired;
    private Integer maxAffected;
    private List<String> allowedOperators;
    private List<String> allowedActions;
    private List<String> roles;
    private List<String> users;
}
```

| 方法 | 用途 |
|---|---|
| `isVisibleToSystem()` | 判断系统级是否展示。 |
| `isQueryable()` | 判断是否允许查询。 |
| `isWritable()` | 判断是否允许修改。 |
| `isExportable()` | 判断是否允许导出。 |
| `requiresMask()` | 判断是否需要脱敏。 |
| `requiresWorkflow()` | 判断是否强制流程。 |
| `allowsDirectUpdate()` | 判断是否允许直接调用业务 update。 |

#### `AgentRiskProperties`

```java
public class AgentRiskProperties {
    private Map<String, OperationRiskProperties> operations;
    private Map<String, FieldRiskProperties> fieldRisk;
}
```

| 方法 | 用途 |
|---|---|
| `getOperationRisk(AgentIntent intent)` | 获取操作级风控配置。 |
| `getFieldRisk(String riskLevel)` | 获取字段风险配置。 |


#### `RuntimeProperties`

```java
public class RuntimeProperties {
    private String baseUrl;
    private Integer connectTimeoutMs;
    private Integer readTimeoutMs;
}
```

用途：配置 Java 调 Python runtime 的地址与超时。

#### `ExportProperties`

```java
public class ExportProperties {
    private Integer syncMaxRows;
    private Integer asyncMaxRows;
    private String storageMode;
    private String baseDir;
    private String publicBaseUrl;
    private Integer expireHours;
}
```

用途：配置同步导出阈值、异步导出上限、存储模式、导出文件目录、公开访问前缀和下载过期时间。

#### `MemoryProperties`

```java
public class MemoryProperties {
    private Boolean enabled;
    private Integer defaultSessionTtlHours;
    private Integer defaultLongTermTtlDays;
}
```

用途：配置记忆能力开关、会话记忆有效期、长期记忆默认有效期。

#### `AgentRoleProperties`

```java
public class AgentRoleProperties {
    private Map<String, RolePolicyProperties> policies;
}
```

用途：承载不同角色在当前 domain 下的 intent 权限和影响数量限制。

#### `RolePolicyProperties`

```java
public class RolePolicyProperties {
    private List<String> allowIntents;
    private List<String> denyIntents;
    private Integer maxUpdateAffected;
}
```

用途：描述单个角色的允许意图、禁止意图和最大修改影响数量。

#### `OperationRiskProperties`

```java
public class OperationRiskProperties {
    private Boolean enabled;
    private Boolean confirmRequired;
    private Integer doubleConfirmAffected;
    private Integer workflowAffected;
    private Integer blockAffected;
}
```

用途：描述操作级风控阈值，如修改影响数量达到多少需要二次确认、工作流或阻断。

#### `WorkflowActionProperties`

```java
public class WorkflowActionProperties {
    private Boolean readOnly;
    private Boolean requiresConfirmation;
    private List<String> requiredRoles;
    private List<String> requiredContext;
    private List<List<String>> requiredAnyOf;
    private String operatorSource;
    private Integer doubleConfirmAffected;
    private Integer blockAffected;
}
```

用途：承载 `agent.domains.workflow.workflow-actions` 下每个二层工作流动作的配置。Java 根据该配置生成 `WorkflowActionSchema` 并做最终权限、上下文和确认校验。

#### `FieldRiskProperties`

```java
public class FieldRiskProperties {
    private RiskDecision decision;
    private Integer maxAffected;
    private Integer doubleConfirmAffected;
}
```

用途：描述字段风险等级对应的默认处理策略。

#### `AgentFeignConfig`

```java
@Configuration
public class AgentFeignConfig {
    @Bean
    public RequestInterceptor agentFeignTokenRelayInterceptor();
}
```

用途：确保调用 runtime/业务服务时透传用户 Token 或服务 Token。

#### `AgentAsyncConfig`

```java
@Configuration
@EnableAsync
public class AgentAsyncConfig {
    @Bean("agentExportExecutor")
    public Executor agentExportExecutor();
}
```

用途：导出任务异步线程池。

---

### 7.3 controller 包

#### `AgentConversationController`

```java
@RestController
@RequestMapping("/agent")
public class AgentConversationController {
    private final AgentOrchestrator agentOrchestrator;

    @PostMapping("/chat")
    public AgentChatResponse chat(@RequestBody AgentChatRequest request);

    @GetMapping("/conversations/{conversationId}")
    public ConversationDetailResponse getConversation(@PathVariable String conversationId);
}
```

| 方法 | 用途 |
|---|---|
| `chat()` | Agent 主入口，处理自然语言请求。 |
| `getConversation()` | 查询会话详情，用于前端恢复上下文。 |

#### `AgentConfirmationController`

```java
@RestController
@RequestMapping("/agent/confirmations")
public class AgentConfirmationController {
    private final ConfirmationService confirmationService;

    @PostMapping("/{confirmationId}/confirm")
    public AgentChatResponse confirm(@PathVariable String confirmationId,
                                     @RequestBody ConfirmExecutionRequest request);

    @PostMapping("/{confirmationId}/reject")
    public AgentChatResponse reject(@PathVariable String confirmationId,
                                    @RequestBody RejectExecutionRequest request);

    @GetMapping("/{confirmationId}")
    public PendingConfirmation get(@PathVariable String confirmationId);
}
```

| 方法 | 用途 |
|---|---|
| `confirm()` | 用户确认后触发执行。 |
| `reject()` | 用户拒绝执行，更新确认状态。 |
| `get()` | 获取待确认计划详情。 |

#### `AgentExportController`

```java
@RestController
@RequestMapping("/agent/exports")
public class AgentExportController {
    private final ExportService exportService;

    @GetMapping("/{taskId}")
    public ExportTaskStatusResponse getTask(@PathVariable String taskId);

    @GetMapping("/{taskId}/download")
    public ResponseEntity<Resource> download(@PathVariable String taskId);
}
```

| 方法 | 用途 |
|---|---|
| `getTask()` | 查询异步导出任务状态。 |
| `download()` | 下载导出文件。 |

#### `AgentMemoryController`

```java
@RestController
@RequestMapping("/agent/memories")
public class AgentMemoryController {
    private final MemoryService memoryService;

    @GetMapping
    public List<MemoryItem> list(MemoryQueryRequest request);

    @PostMapping
    public MemoryItem save(@RequestBody MemoryWriteRequest request);

    @DeleteMapping("/{memoryId}")
    public void delete(@PathVariable String memoryId);
}
```

| 方法 | 用途 |
|---|---|
| `list()` | 查询当前用户记忆。 |
| `save()` | 写入用户确认的长期偏好或别名。 |
| `delete()` | 删除记忆。 |

---

### 7.4 core.orchestrator 包

#### `AgentOrchestrator`

```java
@Service
public class AgentOrchestrator {
    public AgentChatResponse handle(AgentChatRequest request);
    public AgentChatResponse executeConfirmed(String confirmationId, String confirmText);
}
```

| 方法 | 用途 |
|---|---|
| `handle()` | Agent 主编排入口：会话加载、记忆加载、调用 runtime、校验 plan、决策、执行或生成确认。 |
| `executeConfirmed()` | 用户确认后加载确认单并执行。 |

`handle()` 内部建议流程：

```text
1. 获取 AgentUserContext
2. 加载 ConversationSession
3. 加载 MemoryContext
4. 组装 PlanGenerateRequest
5. 调 AgentRuntimeClient.generatePlan()
6. 如果需要反问，返回 CLARIFY
7. PlanValidationService.validate()
8. DomainAdapterRegistry.getAdapter()
9. FieldPolicyEvaluator.evaluate()
10. DomainAdapterRegistry.getAdapter(domain, AffectEstimatableAdapter.class).estimateAffected()
11. RiskEvaluator.evaluate()
12. ExecutionModeResolver.resolve()
13. 如需确认，ConfirmationService.create()
14. 如 executionMode 为 EXPORT_SYNC / EXPORT_ASYNC，调用 ExportService.export()
15. 如 executionMode 为 SUMMARY，调用 SummaryService.summarize()
16. 其他可直接执行路径调用 AgentExecutionDispatcher.dispatch()
17. 保存 Turn 与 Memory
18. 返回 AgentChatResponse
```

---

### 7.5 core.validation 包

#### `PlanNormalizeService`

```java
@Service
public class PlanNormalizeService {
    public AgentPlan normalize(AgentPlan plan);
    public String normalizeOperator(String operator);
    public String normalizeAction(String operation);
    public String normalizeField(String domain, String field);
}
```

| 方法 | 用途 |
|---|---|
| `normalize()` | 对 Plan 进行统一归一化，包括空集合、字段别名、operator/action 大小写、targetType 默认值等。 |
| `normalizeOperator()` | 规范化查询操作符。 |
| `normalizeAction()` | 规范化修改动作。 |
| `normalizeField()` | 根据字段别名和配置规范化字段名。 |

#### `PlanValidationService`

```java
@Service
public class PlanValidationService {
    public PlanValidationResult validate(AgentPlan plan);
    public void validateDomain(AgentPlan plan);
    public void validateIntent(AgentPlan plan);
    public void validateFilters(AgentPlan plan);
    public void validateActions(AgentPlan plan);
    public void validateWorkflowAction(AgentPlan plan, DomainSchema domainSchema);
    public void validateNoConflict(AgentPlan plan);
}
```

| 方法 | 用途 |
|---|---|
| `validate()` | 统一校验 Plan 结构。 |
| `validateDomain()` | 校验 domain 是否存在且启用。 |
| `validateIntent()` | 校验 intent 是否为允许值。 |
| `validateFilters()` | 校验 filters 字段、operator、value。 |
| `validateActions()` | 校验 update actions 是否完整。 |
| `validateWorkflowAction()` | 校验 `workflowAction.action` 是否在 `workflowActions` 内，`requiredContext` 是否全部满足，`requiredAnyOf` 是否至少满足一组，`APPROVE/REJECT` 是否只命中单个流程或待办。 |
| `validateNoConflict()` | 防止同一字段既出现在 filter 又被不合理 action 修改等冲突。 |

---

### 7.6 core.permission 包

#### `FieldPolicyEvaluator`

```java
@Service
public class FieldPolicyEvaluator {
    public FieldPolicyResult evaluate(AgentPlan plan, AgentUserContext userContext);
    public FieldDecision evaluateFilterField(String domain, AgentFilter filter, AgentUserContext userContext);
    public FieldDecision evaluateActionField(String domain, AgentAction action, AgentUserContext userContext);
    public FieldDecision evaluateExportField(String domain, String field, AgentUserContext userContext);
    public FieldDecision evaluateWorkflowAction(AgentPlan plan,
                                                WorkflowActionSchema schema,
                                                AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `evaluate()` | 对 Plan 中所有字段执行权限和契约校验。 |
| `evaluateFilterField()` | 校验字段是否可查询、operator 是否允许。 |
| `evaluateActionField()` | 校验字段是否可修改、action 是否允许。 |
| `evaluateExportField()` | 校验字段是否可导出。 |
| `evaluateWorkflowAction()` | 基于 plan、workflow action schema 和当前用户校验二层 action 的角色、上下文和确认策略。 |

#### `AgentUserContextResolver`

```java
@Component
public class AgentUserContextResolver {
    public AgentUserContext resolve();
    public String currentUserId();
    public List<String> currentRoles();
}
```

| 方法 | 用途 |
|---|---|
| `resolve()` | 从 SecurityContext/JWT 中提取当前用户、角色、token 信息。 |
| `currentUserId()` | 获取当前用户 ID。 |
| `currentRoles()` | 获取当前角色列表。 |

#### `AgentPermissionService`

```java
@Service
public class AgentPermissionService {
    public boolean allowIntent(String domain, AgentIntent intent, AgentUserContext userContext);
    public boolean allowWorkflowAction(AgentPlan plan, WorkflowActionSchema schema, AgentUserContext userContext);
    public boolean allowField(String domain, String field, FieldUsage usage, AgentUserContext userContext);
    public boolean allowUserRule(AgentFieldProperties field, AgentUserContext userContext);
    public boolean allowRoleRule(AgentFieldProperties field, AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `allowIntent()` | 判断用户是否允许执行某领域 intent。 |
| `allowWorkflowAction()` | 根据 workflow action schema 判断用户是否允许执行二层 action。 |
| `allowField()` | 判断字段在查询/修改/导出/展示场景是否允许。 |
| `allowUserRule()` | 判断字段用户白名单。 |
| `allowRoleRule()` | 判断字段角色规则。 |

---

### 7.7 core.risk 包

#### `RiskEvaluator`

```java
@Service
public class RiskEvaluator {
    public RiskEvaluationResult evaluate(AgentPlan plan,
                                         FieldPolicyResult fieldPolicyResult,
                                         long affectedCount,
                                         AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `evaluate()` | 基于配置化多维风险矩阵输出风险等级和处理决策。 |

#### `AffectedCountService`

```java
@Service
public class AffectedCountService {
    public long estimate(AgentPlan plan,
                         AffectEstimatableAdapter adapter,
                         AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `estimate()` | 调用 adapter 预估影响数量，供风控使用。 |

#### `RiskSummaryBuilder`

```java
@Component
public class RiskSummaryBuilder {
    public String buildSummary(AgentPlan plan,
                               RiskEvaluationResult risk,
                               long affectedCount);
}
```

| 方法 | 用途 |
|---|---|
| `buildSummary()` | 生成给用户确认的风险摘要。 |

#### `RiskEvaluationResult`

```java
public class RiskEvaluationResult {
    private RiskDecision decision;
    private RiskLevel maxRiskLevel;
    private Long affectedCount;
    private List<String> reasons;
    private Boolean doubleConfirmRequired;
}
```

用途：风控输出。

---

### 7.8 core.execution 包

#### `ExecutionModeResolver`

```java
@Service
public class ExecutionModeResolver {
    public ExecutionMode resolve(AgentPlan plan,
                                 FieldPolicyResult fieldPolicy,
                                 AdapterCapabilities capabilities,
                                 RiskEvaluationResult risk,
                                 long affectedCount);
}
```

| 方法 | 用途 |
|---|---|
| `resolve()` | 根据 intent、field 契约、adapter 能力、风险结果决定最终执行模式。`EXPORT` 输出 `EXPORT_SYNC/EXPORT_ASYNC`，`SUMMARY` 输出 `SUMMARY`，二者不要求领域 adapter 实现写能力。 |

#### `AgentExecutionDispatcher`

```java
@Service
public class AgentExecutionDispatcher {
    public AgentExecutionResult dispatch(AgentExecutionContext context,
                                         AgentDomainAdapterRegistry adapterRegistry);
}
```

| 方法 | 用途 |
|---|---|
| `dispatch()` | 根据 `context.executionMode` 通过 `AgentDomainAdapterRegistry.getAdapter(domain, capabilityType)` 获取具备目标能力的 adapter，再调用对应能力接口方法。`context.executionId` 必须贯穿执行链。`EXPORT_SYNC/EXPORT_ASYNC/SUMMARY` 不走 adapter dispatcher，由编排层分别调用 `ExportService` 与 `SummaryService`。 |

返回值规则：

1. 写操作 adapter 直接返回 `AgentExecutionResult`。
2. `QUERY/AGGREGATE` 以及 `WORKFLOW_ACTION` 中 `TODO/DETAIL` 等只读动作返回 `AgentQueryResult` 时，由 dispatcher 包装为 `AgentExecutionResult`：`success=true`、`executionMode=context.executionMode`、`status=SUCCEEDED`、`data=AgentQueryResult`。
3. dispatcher 是统一执行出口，调用方不直接依赖 adapter 的内部返回类型差异。

---

### 7.9 core.confirmation 包

#### `ConfirmationService`

```java
@Service
public class ConfirmationService {
    public PendingConfirmation create(AgentPlan plan,
                                      ExecutionMode executionMode,
                                      RiskEvaluationResult risk,
                                      String summary,
                                      AgentUserContext userContext);

    public PendingConfirmation get(String confirmationId);
    public void reject(String confirmationId, String reason, AgentUserContext userContext);
    public ExecutionClaim confirmAndClaim(String confirmationId, String confirmText, AgentUserContext userContext);
    public boolean requiresDoubleConfirm(PendingConfirmation confirmation);
    public void expireTimeoutConfirmations();
}
```

| 方法 | 用途 |
|---|---|
| `create()` | 创建待确认执行单。 |
| `get()` | 查询确认单。 |
| `reject()` | 拒绝确认单。 |
| `confirmAndClaim()` | 校验确认短语，并通过 CAS 将确认单从 `PENDING` 原子更新为 `CLAIMED`，同时写入 `executionId`。CAS 失败表示确认单已被处理，不得执行。 |
| `requiresDoubleConfirm()` | 判断是否需要二次确认。 |
| `expireTimeoutConfirmations()` | 定时过期超时确认单。 |

---

### 7.10 core.memory 包

#### `MemoryService`

```java
@Service
public class MemoryService {
    public List<MemoryItem> loadForRuntime(String userId, String conversationId, String domainHint);
    public MemoryItem save(MemoryWriteRequest request, AgentUserContext userContext);
    public void saveTurnMemory(String conversationId, AgentPlan plan, AgentExecutionResult result);
    public void saveLastResult(String conversationId, AgentQueryResult result);
    public Optional<MemoryItem> findLastResult(String conversationId, String domain);
    public List<MemoryItem> findLongTermMemories(String userId, String domain);
    public void delete(String memoryId, AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `loadForRuntime()` | 为 Python runtime 组装可用记忆上下文。 |
| `save()` | 保存用户明确确认的长期记忆。 |
| `saveTurnMemory()` | 保存当前轮 Plan 与结果摘要。 |
| `saveLastResult()` | 保存上一轮查询结果引用。 |
| `findLastResult()` | 查找上一轮结果，支持“刚才那些”。 |
| `findLongTermMemories()` | 获取用户长期记忆。 |
| `delete()` | 删除记忆。 |

#### `LastResultRef` 规则

`LAST_RESULT` 必须保存为结构化引用，而不是只保存 summarizer 文本。推荐最小结构：

```json
{
  "resultRefId": "result-001",
  "conversationId": "conv-001",
  "domain": "employee",
  "sourcePlanId": "plan-001",
  "sourcePlan": {},
  "primaryKeys": [
    {"idCardNo": "110101199001010011"}
  ],
  "rowCount": 1,
  "summary": "上一轮查到 1 名员工",
  "createdAt": "2026-06-16T10:00:00",
  "expiresAt": "2026-06-17T10:00:00"
}
```

上述完整结构仅保存在 Java `agent-service` 内部。传给 Python 的 `memoryContext.lastResultRef` 必须是安全摘要，不包含 `primaryKeys`、隐藏字段或未脱敏敏感字段。推荐传输结构：

```json
{
  "resultRefId": "result-001",
  "domain": "employee",
  "sourcePlanId": "plan-001",
  "rowCount": 1,
  "summary": "上一轮查到 1 名员工",
  "displayFields": ["name", "position"],
  "createdAt": "2026-06-16T10:00:00"
}
```

当用户输入“把他们改成 xxx”“导出刚才那些”时，Python 可以基于安全摘要生成 `targetType=LAST_RESULT` 与 `resultRefId` 的 Plan；Java 执行层必须根据 `resultRefId` 在服务端恢复主键列表或原始查询条件。summarizer 生成的自然语言摘要只用于对话理解和用户展示，不得作为修改、导出或审批动作的唯一执行依据。

#### `MemorySearchStrategy`（预留）

```java
public interface MemorySearchStrategy {
    List<MemoryItem> search(MemoryQueryRequest request, AgentUserContext userContext);
}
```

用途：长期记忆检索扩展点。P0 不实现复杂向量记忆，仅保留空接口或 Noop 实现，后续可扩展为关键词检索、向量检索或混合检索。

#### `MemoryPolicyService`

```java
@Service
public class MemoryPolicyService {
    public boolean allowAutoWrite(MemoryItem item);
    public boolean requiresUserConfirmation(MemoryItem item);
    public boolean isSensitive(MemoryItem item);
    public LocalDateTime resolveExpireTime(MemoryScope scope, MemoryType type);
}
```

| 方法 | 用途 |
|---|---|
| `allowAutoWrite()` | 判断是否允许自动写入。 |
| `requiresUserConfirmation()` | 判断长期偏好是否需要用户确认。 |
| `isSensitive()` | 判断是否敏感，敏感默认不写入。 |
| `resolveExpireTime()` | 根据 scope/type 计算过期时间。 |

---

### 7.11 core.export 包

#### `ExportService`

```java
@Service
public class ExportService {
    public AgentExecutionResult export(AgentPlan plan, AgentUserContext userContext);
    public ExportTaskResponse createAsyncTask(AgentPlan plan, AgentUserContext userContext);
    public Resource download(String taskId, AgentUserContext userContext);
    public ExportTaskStatusResponse getStatus(String taskId, AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `export()` | 判断同步/异步并执行导出。 |
| `createAsyncTask()` | 创建异步导出任务。 |
| `download()` | 下载导出文件，轻量承载导出文件访问控制与存储分支处理。 |
| `getStatus()` | 查询导出状态。 |

P0 不定义单独的 `ExportableAdapter`。导出由通用 `ExportService` 编排，优先复用上一轮 `LAST_RESULT/resultRef`；需要重新取数时，通过 `QueryableAdapter.query()` 或领域查询接口获取数据，再统一执行字段过滤、脱敏、同步/异步分流和下载鉴权。

`download()` 轻量化职责：

1. 按 `taskId` 查询 `agent_export_task`，校验任务存在、状态已完成、未超过 `expiresAt`。
2. 校验当前用户可访问该任务：默认要求 `task.userId == userContext.userId`；如后续开放管理员下载，必须通过角色策略显式放行。
3. 校验任务所属 `conversationId/domain` 与当前上下文匹配，避免跨会话或跨领域下载。
4. 按 `storageMode` 分支处理：`local/shared-filesystem` 仅允许读取 `base-dir` 下的 `filePath`；`object-storage` 优先返回有效 `downloadUrl` 或通过后端代理读取 `storageKey`。
5. 下载接口不得直接暴露未校验的本地绝对路径或长期有效 URL。

#### `ExportFieldResolver`

```java
@Component
public class ExportFieldResolver {
    public List<String> resolveExportFields(String domain,
                                            AgentExportSpec spec,
                                            AgentUserContext userContext);
}
```

用途：根据字段契约过滤不可导出字段。

#### `ExportFileWriter`

```java
public interface ExportFileWriter {
    String format();
    Path write(List<Map<String, Object>> rows, List<String> fields, ExportWriteContext context);
}
```

用途：导出文件写入 SPI。

#### `CsvExportFileWriter`

```java
@Component
public class CsvExportFileWriter implements ExportFileWriter {
    public String format();
    public Path write(List<Map<String, Object>> rows, List<String> fields, ExportWriteContext context);
}
```

用途：CSV 导出实现。

---

### 7.12 core.summary 包

#### `SummaryService`

```java
@Service
public class SummaryService {
    public AgentExecutionResult summarize(AgentPlan plan, AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `summarize()` | 基于 `LAST_RESULT/resultRef` 或当前 Plan 指定的结果引用生成摘要响应，不修改业务数据。 |

P0 摘要能力只读取 Java 侧保存的结构化 `LastResultRef` 和可展示字段；不得把 Python summarizer 文本作为执行依据。若需要 LLM 生成自然语言摘要，Java 只传脱敏后的摘要材料给 runtime，返回内容作为 `AgentExecutionResult.data`。

---

### 7.13 core.mask 包

#### `FieldMasker`

```java
public interface FieldMasker {
    String maskType();
    Object mask(Object value, MaskContext context);
}
```

用途：脱敏策略 SPI。

#### `MaskerRegistry`

```java
@Component
public class MaskerRegistry {
    public FieldMasker get(String maskType);
    public Object mask(String maskType, Object value, MaskContext context);
}
```

| 方法 | 用途 |
|---|---|
| `get()` | 根据 maskType 获取脱敏器。 |
| `mask()` | 执行脱敏。 |

#### `IdCardMasker / MobileMasker / EmailMasker / AmountMasker / NameMasker`

```java
@Component
public class IdCardMasker implements FieldMasker {
    public String maskType();
    public Object mask(Object value, MaskContext context);
}
```

用途：按类型注入脱敏逻辑。

---

### 7.14 core.audit 包

#### `AgentAuditRecorder`

```java
public interface AgentAuditRecorder {
    void recordReceived(AgentAuditEvent event);
    void recordPlanGenerated(AgentAuditEvent event);
    void recordRiskEvaluated(AgentAuditEvent event);
    void recordConfirmationCreated(AgentAuditEvent event);
    void recordExecuted(AgentAuditEvent event);
    void recordFailed(AgentAuditEvent event);
}
```

用途：审计事件预留接口。**P0 coding 中只预留，不实现真实落库。**

#### `NoopAgentAuditRecorder`

```java
@Component
public class NoopAgentAuditRecorder implements AgentAuditRecorder {
    public void recordReceived(AgentAuditEvent event) {}
    public void recordPlanGenerated(AgentAuditEvent event) {}
    public void recordRiskEvaluated(AgentAuditEvent event) {}
    public void recordConfirmationCreated(AgentAuditEvent event) {}
    public void recordExecuted(AgentAuditEvent event) {}
    public void recordFailed(AgentAuditEvent event) {}
}
```

用途：默认空实现，保证业务代码可依赖接口。

#### `@AgentAuditable`（预留）

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface AgentAuditable {
    String value() default "";
}
```

用途：后续如采用 AOP 审计，可标记关键方法。P0 不要求实现切面。

---

### 7.15 adapter.spi 包

#### `AgentDomainAdapter`

```java
public interface AgentDomainAdapter {
    String domain();
    AdapterCapabilities capabilities();
}
```

用途：所有业务域 adapter 的最小公共接口，只负责声明领域标识与能力集合，不承载具体业务动作。具体动作通过下列能力接口按需实现，避免每个领域实现大量无效方法。

#### `AffectEstimatableAdapter`

```java
public interface AffectEstimatableAdapter extends AgentDomainAdapter {
    long estimateAffected(AgentPlan plan, AgentUserContext userContext);
}
```

用途：需要风控预估影响数量的领域实现。

#### `QueryableAdapter`

```java
public interface QueryableAdapter extends AgentDomainAdapter {
    AgentQueryResult query(AgentPlan plan, AgentUserContext userContext);
}
```

用途：支持查询的领域实现。

#### `DirectUpdateAdapter`

```java
public interface DirectUpdateAdapter extends AgentDomainAdapter {
    AgentExecutionResult directUpdate(AgentExecutionContext context);
}
```

用途：支持直接调用业务写接口的领域实现。

#### `ChangeRequestAdapter`

```java
public interface ChangeRequestAdapter extends AgentDomainAdapter {
    AgentExecutionResult createChangeRequest(AgentExecutionContext context);
}
```

用途：支持创建业务变更申请的领域实现。

#### `WorkflowSubmitAdapter`

```java
public interface WorkflowSubmitAdapter extends AgentDomainAdapter {
    AgentExecutionResult submitWorkflow(AgentExecutionContext context);
}
```

用途：支持提交业务流程的领域实现。

#### `BusinessCommandAdapter`

```java
public interface BusinessCommandAdapter extends AgentDomainAdapter {
    AgentExecutionResult executeBusinessCommand(AgentExecutionContext context);
}
```

用途：支持业务命令入口的领域实现。

#### `WorkflowActionAdapter`

```java
public interface WorkflowActionAdapter extends AgentDomainAdapter {
    AgentQueryResult queryTodos(AgentExecutionContext context);
    AgentQueryResult detail(AgentExecutionContext context);
    AgentExecutionResult approve(AgentExecutionContext context);
    AgentExecutionResult reject(AgentExecutionContext context);
}
```

用途：支持工作流二层动作。`queryTodos/detail` 是读操作，返回 `AgentQueryResult`；dispatcher 负责将其包装为统一的 `AgentExecutionResult`。`approve/reject` 是写操作，直接返回 `AgentExecutionResult`，执行时必须由 Java 注入当前用户作为 operator；若 Plan 携带 todoId，则由 adapter 原样传回 workflow-service 做待办一致性校验。

#### `AggregatableAdapter`

```java
public interface AggregatableAdapter extends AgentDomainAdapter {
    AgentQueryResult aggregate(AgentPlan plan, AgentUserContext userContext);
}
```

用途：支持聚合统计的领域实现。

#### 导出能力边界

P0 不新增 `ExportableAdapter` 与 `AgentExportResult` 契约。`AdapterCapabilities.supportExport=true` 仅表示该领域的数据可由通用 `ExportService` 基于查询结果导出；领域 adapter 不需要实现额外导出接口。

#### `AdapterCapabilities`

```java
public class AdapterCapabilities {
    private boolean supportQuery;
    private boolean supportDirectUpdate;
    private boolean supportChangeRequest;
    private boolean supportWorkflowSubmit;
    private boolean supportBusinessCommand;
    private boolean supportWorkflowAction;
    private boolean supportAggregate;
    private boolean supportExport;
}
```

用途：业务域能力声明。

#### `AgentDomainAdapterRegistry`

```java
@Component
public class AgentDomainAdapterRegistry {
    public AgentDomainAdapterRegistry(List<AgentDomainAdapter> adapters);
    public AgentDomainAdapter getAdapter(String domain);
    public <T extends AgentDomainAdapter> T getAdapter(String domain, Class<T> capabilityType);
    public boolean supports(String domain, Class<? extends AgentDomainAdapter> capabilityType);
    public boolean hasAdapter(String domain);
    public List<String> domains();
}
```

| 方法 | 用途 |
|---|---|
| `getAdapter()` | 根据 domain 获取 adapter。 |
| `getAdapter(domain, capabilityType)` | 根据 domain 获取具备指定能力接口的 adapter；不具备能力时抛出 `AgentUnsupportedCapabilityException`。 |
| `supports()` | 判断指定 domain 是否实现某项能力接口。 |
| `hasAdapter()` | 判断 domain 是否已接入。 |
| `domains()` | 返回所有已注册领域。 |

---

### 7.16 adapter.employee 包

#### `EmployeeAgentAdapter`

```java
@Component
public class EmployeeAgentAdapter implements QueryableAdapter,
        AffectEstimatableAdapter,
        DirectUpdateAdapter,
        ChangeRequestAdapter,
        WorkflowSubmitAdapter,
        BusinessCommandAdapter {
    public String domain();
    public AdapterCapabilities capabilities();
    public long estimateAffected(AgentPlan plan, AgentUserContext userContext);
    public AgentQueryResult query(AgentPlan plan, AgentUserContext userContext);
    public AgentExecutionResult directUpdate(AgentExecutionContext context);
    public AgentExecutionResult createChangeRequest(AgentExecutionContext context);
    public AgentExecutionResult submitWorkflow(AgentExecutionContext context);
    public AgentExecutionResult executeBusinessCommand(AgentExecutionContext context);
}
```

| 方法 | 用途 |
|---|---|
| `domain()` | 返回 `employee`。 |
| `capabilities()` | 声明 employee 支持 query、directUpdate、changeRequest、workflowSubmit、export；其中 export 表示可由通用 `ExportService` 基于查询结果导出。 |
| `estimateAffected()` | 调 employee count/search 接口预估影响数量。 |
| `query()` | 调 employee 查询或 ES 查询接口。 |
| `directUpdate()` | 调 employee 暴露的 update 服务，不直接操作 DB；请求体按 `AgentPlan.actions` 转换为只包含变更键值的 Map，由 employee-service 依据 `map.containsKey` 判断实际更新字段。Agent 侧字段名使用 schema 中的 Java/camelCase 名称，适配到 employee-service 请求前必须完成字段名映射。 |
| `createChangeRequest()` | 创建 employee 变更申请。 |
| `submitWorkflow()` | 按 employee 变更申请结果提交工作流；流程定义键由 `domain + "-" + operationType` 组合得到。 |
| `executeBusinessCommand()` | 预留员工域业务命令。 |

#### `EmployeePlanMapper`

```java
@Component
public class EmployeePlanMapper {
    public EmployeeQueryRequest toQueryRequest(AgentPlan plan);
    public Map<String, Object> toUpdatePatchMap(AgentPlan plan);
    public EmployeeChangeRequestCommand toChangeRequestCommand(AgentPlan plan);
}
```

用途：将 AgentPlan 转换为 employee-service 请求 DTO。更新场景只输出变更字段 Map，不构造完整员工对象。`toUpdatePatchMap()` 的输出字段以 Java/camelCase 属性名为主；若 employee-service 某接口仍要求数据库列名，由 mapper 在这一层做显式转换，不允许 Python 或通用 Agent 核心感知数据库列名。

---

### 7.17 adapter.transaction 包

#### `TransactionAgentAdapter`

```java
@Component
public class TransactionAgentAdapter implements QueryableAdapter,
        AffectEstimatableAdapter,
        DirectUpdateAdapter,
        BusinessCommandAdapter,
        AggregatableAdapter {
    public String domain();
    public AdapterCapabilities capabilities();
    public long estimateAffected(AgentPlan plan, AgentUserContext userContext);
    public AgentQueryResult query(AgentPlan plan, AgentUserContext userContext);
    public AgentExecutionResult directUpdate(AgentExecutionContext context);
    public AgentExecutionResult executeBusinessCommand(AgentExecutionContext context);
    public AgentQueryResult aggregate(AgentPlan plan, AgentUserContext userContext);
}
```

| 方法 | 用途 |
|---|---|
| `domain()` | 返回 `transaction`。 |
| `capabilities()` | 声明 transaction 支持 query、directUpdate、aggregate、businessCommand、export；其中 export 表示可由通用 `ExportService` 基于查询结果导出。 |
| `estimateAffected()` | 调 transaction 查询/count 接口预估影响数量。 |
| `query()` | 调 `/txn/query`。 |
| `directUpdate()` | 调 `/txn/{transId}` 或业务暴露的批量修改接口。 |
| `executeBusinessCommand()` | 调交易业务提交入口，如 `/txn/txnkafka`、`/txn/txnmq` 或后续标准提交接口。 |
| `aggregate()` | 调 `/txn/aggregate`。 |

#### `TransactionPlanMapper`

```java
@Component
public class TransactionPlanMapper {
    public TransactionQueryRequest toQueryRequest(AgentPlan plan);
    public AggregateRequest toAggregateRequest(AgentPlan plan);
    public TransactionUpdateRequest toUpdateRequest(AgentPlan plan);
}
```

用途：将 AgentPlan 转换为 transaction 请求 DTO。

---

### 7.18 adapter.workflow 包

#### `WorkflowAgentAdapter`

```java
@Component
public class WorkflowAgentAdapter implements WorkflowActionAdapter,
        AffectEstimatableAdapter {
    public String domain();
    public AdapterCapabilities capabilities();
    public long estimateAffected(AgentPlan plan, AgentUserContext userContext);
    public AgentQueryResult queryTodos(AgentExecutionContext context);
    public AgentQueryResult detail(AgentExecutionContext context);
    public AgentExecutionResult approve(AgentExecutionContext context);
    public AgentExecutionResult reject(AgentExecutionContext context);
}
```

| 方法 | 用途 |
|---|---|
| `domain()` | 返回 `workflow`。 |
| `capabilities()` | 只声明 workflowAction。 |
| `estimateAffected()` | 工作流动作通常影响 1 个流程或 1 个待办。 |
| `queryTodos()` | 调 workflow-service 查询当前用户待办。 |
| `detail()` | 调 workflow-service 查询流程详情；若 Plan 只有 todoId，先通过 `/workflows/todos/{todoId}?operator=` 回查当前待办并取得 processId。 |
| `approve()` | 调 workflow-service approve，请求体携带 operator=currentUser；若有 todoId，原样传回 workflow-service 做当前待办校验。 |
| `reject()` | 调 workflow-service reject，请求体携带 operator=currentUser；若有 todoId，原样传回 workflow-service 做当前待办校验。 |
| 未实现的能力接口 | 不支持；由 `AgentDomainAdapterRegistry.supports()` 与执行分发层拦截。 |

---

### 7.19 client 包

#### `AgentRuntimeClient`

```java
@FeignClient(name = "agent-runtime", url = "${agent.runtime.base-url:http://localhost:9230}")
public interface AgentRuntimeClient {
    @PostMapping("/runtime/v1/plans/generate")
    PlanGenerateResponse generatePlan(@RequestBody PlanGenerateRequest request);
}
```

| 方法 | 用途 |
|---|---|
| `generatePlan()` | 请求 Python 根据自然语言、领域 schema 和记忆上下文生成候选 Plan 或 Clarify。 |

说明：P0 只保留单一 `generatePlan()` 接口。查询、修改、统计、导出、业务提交、工作流动作、反问均由 Python Runtime 内部 LangGraph 分支收敛到 `/runtime/v1/plans/generate`。反问作为 `responseType=CLARIFY` 返回，不单独暴露 `/clarify`。

#### `EmployeeAgentFeignClient`

```java
@FeignClient(name = "employee-service")
public interface EmployeeAgentFeignClient {
    @PostMapping("/employees/es/search")
    Object search(@RequestBody Object request);

    @GetMapping("/employees/count")
    Long count();

    @PutMapping("/employees/{idCardNo}")
    Object update(@PathVariable String idCardNo, @RequestBody Object request);

    @PostMapping("/employees")
    Object create(@RequestBody Object request);

    @GetMapping("/employees/change-requests/{id}")
    Object getChangeRequest(@PathVariable String id);
}
```

用途：Agent 调 employee-service。实际 DTO 可在 coding 时对齐 employee-service 现有 DTO。

#### `TransactionAgentFeignClient`

```java
@FeignClient(name = "mq-procedure-service")
public interface TransactionAgentFeignClient {
    @PostMapping("/txn/query")
    Object query(@RequestBody Object request);

    @PostMapping("/txn/aggregate")
    Object aggregate(@RequestBody Object request);

    @PutMapping("/txn/{transId}")
    Object update(@PathVariable String transId, @RequestBody Object request);

    @PostMapping("/txn")
    Object create(@RequestBody Object request);
}
```

用途：Agent 调 transaction 相关接口。

#### `WorkflowAgentFeignClient`

```java
@FeignClient(name = "workflow-service")
public interface WorkflowAgentFeignClient {
    @PostMapping("/workflows")
    Object submit(@RequestBody Object request);

    @PostMapping("/workflows/{processId}/approve")
    Object approve(@PathVariable String processId, @RequestBody Object request);

    @PostMapping("/workflows/{processId}/reject")
    Object reject(@PathVariable String processId, @RequestBody Object request);

    @GetMapping("/workflows/{processId}")
    Object detail(@PathVariable String processId);

    @GetMapping("/workflows/todos")
    Object todos(@RequestParam String operator);

    @GetMapping("/workflows/todos/{todoId}")
    Object resolveTodo(@PathVariable String todoId, @RequestParam String operator);
}
```

用途：Agent 调 workflow-service。

---

### 7.20 entity / mapper 包

#### `AgentConversationEntity`

字段：`id, userId, title, status, createdAt, updatedAt`。

用途：会话主表。

#### `AgentTurnEntity`

字段：`id, conversationId, userId, role, message, planJson, resultJson, createdAt`。

用途：会话轮次记录。

#### `AgentMemoryEntity`

字段：`id, userId, conversationId, domain, scope, memoryType, memoryKey, memoryValue, source, confidence, expiresAt, createdAt, updatedAt`。

用途：统一记忆表。

#### `AgentConfirmationEntity`

字段：`id, userId, conversationId, planJson, executionMode, riskDecision, affectedCount, summary, status, executionId, expiresAt, createdAt, updatedAt`。

用途：待确认执行单。

#### `AgentExportTaskEntity`

字段：`id, userId, conversationId, domain, planJson, status, fileName, storageMode, storageKey, filePath, downloadUrl, expiresAt, totalRows, exportedRows, errorMessage, createdAt, updatedAt`。

用途：导出任务表。

#### Mapper 方法

##### `AgentConversationMapper`

```java
int insert(AgentConversationEntity entity);
AgentConversationEntity selectById(String id);
int updateStatus(String id, String status);
```

##### `AgentTurnMapper`

```java
int insert(AgentTurnEntity entity);
List<AgentTurnEntity> selectByConversationId(String conversationId, int limit);
```

##### `AgentMemoryMapper`

```java
int insert(AgentMemoryEntity entity);
int update(AgentMemoryEntity entity);
AgentMemoryEntity selectById(String id);
List<AgentMemoryEntity> selectForRuntime(String userId, String conversationId, String domain);
List<AgentMemoryEntity> selectLongTerm(String userId, String domain);
int deleteById(String id);
int deleteExpired(LocalDateTime now);
```

##### `AgentConfirmationMapper`

```java
int insert(AgentConfirmationEntity entity);
AgentConfirmationEntity selectById(String id);
int updateStatus(String id, String status);
int claimPending(String id, String executionId, LocalDateTime now);
int rejectPending(String id, String reason, LocalDateTime now);
List<AgentConfirmationEntity> selectExpired(LocalDateTime now);
```

##### `AgentExportTaskMapper`

```java
int insert(AgentExportTaskEntity entity);
AgentExportTaskEntity selectById(String id);
int updateProgress(String id, String status, Long exportedRows);
int updateSuccess(String id, String fileName, String storageMode, String storageKey, String filePath,
                  String downloadUrl, LocalDateTime expiresAt);
int updateFailed(String id, String errorMessage);
```

---

## 8. agent-runtime Python 详细结构（P0 Slim）

### 8.1 Python 端定位

`agent-runtime` 是轻量规划运行时，不是业务执行服务。其输入来自 Java `agent-service`，输出为候选 Plan 或 Clarify，不直接调用 employee、transaction、workflow、es-query 等业务服务。

| 职责类别 | Python agent-runtime | Java agent-service |
|---|---|---|
| 自然语言理解 | 是 | 否 |
| 意图识别 | 是，生成候选 intent | 校验 intent 是否在领域契约内 |
| 反问生成 | 是 | 包装返回、保存会话状态 |
| Plan DSL 生成 | 是，生成 Candidate Plan | 校验并转为 Executable Decision |
| LangGraph 分支 | 是 | 否 |
| Prompt 管理 | 是，仅加载和渲染 prompt 文件 | 否 |
| 字段权限 | 否 | 是 |
| 风控 | 否 | 是 |
| 确认/二次确认 | 否 | 是 |
| 影响数量预估 | 否 | 是，通过 Adapter |
| 执行模式决策 | 否，不输出 `executionMode` | 是，通过 `ExecutionModeResolver` |
| 业务调用 | 否 | 是，通过 Adapter |
| 导出任务 | 否 | 是 |
| 记忆事实源 | 否，只读取 Java 传入摘要 | 是 |
| 审计预留 | 否 | 是 |

核心原则：**Python 端完整但不复杂；Java 端负责企业级治理；Python 端负责智能规划。**

#### 8.1.1 Java/Python 功能分界核查结论

本设计核查后确认：Python 端虽然按意图拆分 prompt，但职责没有扩大。Python 只生成“候选业务语义 Plan”，Java 负责“可执行决策”。

| 能力 | 归属 | 原因 |
|---|---|---|
| 意图识别、槽位抽取、字段别名理解 | Python | 依赖 LLM 与 prompt，属于语言理解能力。 |
| Plan 结构最小校验 | Python | 用于保证返回 JSON 可解析、字段基本存在，减少 Java 无效请求处理。 |
| 字段是否可查、可改、可导出 | Java | 属于权限与治理，必须以后端契约为准。 |
| 影响数量预估 | Java | 必须调用业务 Adapter 或查询服务，Python 不访问业务数据。 |
| 风险等级与确认策略 | Java | 涉及安全边界、角色、数量、字段风险和业务策略。 |
| `DIRECT_UPDATE / CHANGE_REQUEST / WORKFLOW_SUBMIT` 决策 | Java | 属于执行模式，不是自然语言理解结果。 |
| 多轮记忆持久化 | Java | 统一治理、脱敏、过期、删除和审计。 |
| LangGraph checkpoint | Python | 仅用于当前图执行状态，不作为长期记忆事实源。 |

---


### 8.2 Python 端完整目录结构

```text
agent-runtime
├── pyproject.toml
├── README.md
├── .env.example
├── app
│   ├── __init__.py
│   ├── main.py
│   ├── api
│   │   ├── __init__.py
│   │   └── runtime_api.py
│   ├── contracts
│   │   ├── __init__.py
│   │   ├── contract-manifest.json
│   │   ├── agent-plan.schema.json
│   │   ├── runtime.schema.json
│   │   └── models.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── graph.py
│   │   ├── graph_nodes.py
│   │   ├── planning.py
│   │   ├── prompts.py
│   │   ├── llm_client.py
│   │   └── settings.py
│   └── prompts
│       ├── system.md
│       ├── clarify.md
│       ├── repair.md
│       └── intents
│           ├── query.md
│           ├── update.md
│           ├── aggregate.md
│           ├── export.md
│           ├── business_submit.md
│           ├── workflow_action.md
│           └── summary.md
└── tests
    ├── test_contracts.py
    ├── test_prompt_render.py
    └── test_plan_shape.py
```

P0 核心 Python 代码文件包括：`main.py`、`runtime_api.py`、`contracts/models.py`、`graph.py`、`graph_nodes.py`、`planning.py`、`prompts.py`、`llm_client.py`、`settings.py`。其中 `contracts/contract-manifest.json`、`agent-plan.schema.json`、`runtime.schema.json` 用于和 Java 侧契约文件做 schemaHash 校验。Python 不手写业务字段权限、执行能力或 workflow action policy。

---

### 8.3 Java 与 Python 接口契约

#### 8.3.1 Runtime API 列表

`agent-runtime` 只提供一个 P0 必须实现接口。

| 方法 | 路径 | 是否 P0 必须 | 用途 |
|---|---|---:|---|
| `POST` | `/runtime/v1/plans/generate` | 是 | 根据用户输入、领域 schema、会话上下文生成候选 Plan 或 Clarify。 |

P0 不单独暴露 `/repair`、`/clarify`、`/intent`、`/query`、`/update` 等接口。所有自然语言请求都进入 `/runtime/v1/plans/generate`，由 LangGraph 内部完成意图识别、反问、Plan 生成与一次结构修复。

#### 8.3.2 单一 generate 接口的原因

1. Python Runtime 的职责是“生成候选 Plan”，不是按意图执行业务。查询、修改、统计、导出、业务提交、工作流动作在 Python 侧都是自然语言到 Plan 的转换。
2. 用户输入在识别前可能无法判断意图，例如“帮我处理一下刚才那个”。若拆分接口，Java 必须先做自然语言意图判断，违背服务边界。
3. `CLARIFY` 是 Plan 生成过程中的缺槽结果，不是独立业务动作，因此作为 `responseType=CLARIFY` 返回即可。
4. 单接口便于版本治理、日志追踪、超时控制、测试样例维护和契约演进。
5. LangGraph 本身是内部状态图，外部只需要暴露一个图入口。

#### 8.3.3 字段命名规范

Java 与 Python 对外 JSON 统一使用 `camelCase`。Python 内部如使用 snake_case，需要通过 Pydantic alias 适配；HTTP 契约不得随 Python 内部命名变化而变化。

#### 8.3.4 请求体 `PlanGenerateRequest`

```json
{
  "requestId": "req-20260616-0001",
  "conversationId": "conv-001",
  "turnId": "turn-003",
  "userInput": "把张三的岗位改成 HRBP",
  "locale": "zh-CN",
  "userContext": {
    "userId": "dylan",
    "roles": ["agent:admin"],
    "tenantId": "default"
  },
  "memoryContext": {
    "lastQuery": {},
    "lastResultRef": {
      "resultRefId": "result-001",
      "domain": "employee",
      "sourcePlanId": "plan-001",
      "rowCount": 1,
      "summary": "上一轮查到 1 名员工",
      "displayFields": ["name", "position"],
      "createdAt": "2026-06-16T10:00:00"
    },
    "aliases": {"岗位": "position"},
    "preferences": {}
  },
  "domainSchemas": [
    {
      "domain": "employee",
      "displayName": "员工",
      "supportedIntents": ["QUERY", "UPDATE", "EXPORT", "BUSINESS_SUBMIT", "SUMMARY"],
      "fields": [
        {
          "name": "position",
          "displayName": "岗位",
          "queryable": true,
          "writable": true,
          "exportable": true,
          "operators": ["EQ"],
          "actions": ["SET"]
        }
      ]
    },
    {
      "domain": "workflow",
      "displayName": "工作流",
      "supportedIntents": ["WORKFLOW_ACTION"],
      "fields": [
        {"name": "processId", "displayName": "流程号", "queryable": true, "operators": ["EQ"]},
        {"name": "todoId", "displayName": "待办号", "queryable": true, "operators": ["EQ"]},
        {"name": "reason", "displayName": "审批意见", "writable": true, "actions": ["SET"]}
      ],
      "workflowActions": [
        {"action": "TODO", "readOnly": true, "requiresConfirmation": false, "requiredRoles": ["agent:viewer", "agent:admin"], "requiredContext": [], "requiredAnyOf": [], "operatorSource": "CURRENT_USER"},
        {"action": "DETAIL", "readOnly": true, "requiresConfirmation": false, "requiredRoles": ["agent:viewer", "agent:admin"], "requiredContext": [], "requiredAnyOf": [["processId"], ["todoId"]], "operatorSource": "CURRENT_USER"},
        {"action": "APPROVE", "readOnly": false, "requiresConfirmation": true, "requiredRoles": ["agent:admin"], "requiredContext": [], "requiredAnyOf": [["processId"], ["todoId"]], "operatorSource": "CURRENT_USER"},
        {"action": "REJECT", "readOnly": false, "requiresConfirmation": true, "requiredRoles": ["agent:admin"], "requiredContext": [], "requiredAnyOf": [["processId"], ["todoId"]], "operatorSource": "CURRENT_USER"}
      ]
    }
  ],
  "contractVersion": "v1"
}
```

说明：Java 组装 `domainSchemas` 时必须包含当前已启用的业务域 schema。schema 应按当前业务接口实际能力提供；业务接口不能准确转换的 operator/action 不应出现在 P0 schema 示例中。P0 支持 `WORKFLOW_ACTION`，因此 workflow domain schema 必须由 Java 传入 Python，Python 不内置 workflow schema。

#### 8.3.5 响应体 `PlanGenerateResponse`

```json
{
  "requestId": "req-20260616-0001",
  "conversationId": "conv-001",
  "turnId": "turn-003",
  "responseType": "PLAN",
  "plan": {
    "domain": "employee",
    "intent": "UPDATE",
    "targetType": "LAST_RESULT",
    "resultRefId": "result-001",
    "filters": [],
    "actions": [
      {"field": "position", "operation": "SET", "value": "HRBP"}
    ],
    "aggregate": null,
    "exportSpec": null,
    "workflowAction": null,
    "requiresConfirmation": true,
    "confidence": 0.86,
    "reasoningSummary": "用户要求修改上一轮查询结果中的员工岗位字段。"
  },
  "clarifyQuestion": null,
  "warnings": [],
  "contractVersion": "v1"
}
```

当需要反问时：

```json
{
  "requestId": "req-20260616-0002",
  "conversationId": "conv-001",
  "turnId": "turn-004",
  "responseType": "CLARIFY",
  "plan": null,
  "clarifyQuestion": {
    "question": "你是要提交业务变更，还是审批/处理已有工作流待办？",
    "missingFields": ["targetType"],
    "options": ["提交业务变更", "处理工作流待办"]
  },
  "warnings": [],
  "contractVersion": "v1"
}
```

响应规则：

1. `responseType=PLAN` 时，`plan` 必须非空。
2. `responseType=CLARIFY` 时，`clarifyQuestion` 必须非空。
3. `requiresConfirmation` 是 Python 建议值，Java 可以覆盖。
4. Python 不输出 `executionMode`，执行模式由 Java 决定。
5. Python 不输出风险等级，风险由 Java 决定。
6. Python 可以输出 `targetType=LAST_RESULT` 与 `resultRefId`，但不得把 summarizer 文本当作执行依据；Java 必须根据服务端保存的结构化 `LastResultRef` 恢复主键、数量和原始查询条件。

#### 8.3.6 错误响应

```json
{
  "requestId": "req-20260616-0003",
  "errorCode": "PLAN_GENERATION_FAILED",
  "message": "failed to generate valid plan",
  "details": []
}
```

---

### 8.4 `app/main.py`

```python
from fastapi import FastAPI
from app.api.runtime_api import router as runtime_router


def create_app() -> FastAPI:
    app = FastAPI(title="agent-runtime", version="1.0.0")
    app.include_router(runtime_router, prefix="/runtime/v1")
    return app


app = create_app()
```

| 方法 | 用途 |
|---|---|
| `create_app()` | 创建 FastAPI 应用，注册 runtime 路由，后续可加入健康检查、中间件、异常处理。 |
| `app` | Uvicorn 启动对象。 |

启动命令：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 9230
```

---

### 8.5 `app/api/runtime_api.py`

```python
from fastapi import APIRouter
from app.contracts.models import PlanGenerateRequest, PlanGenerateResponse
from app.core.graph import run_graph

router = APIRouter()


@router.post("/plans/generate", response_model=PlanGenerateResponse)
async def generate_plan(request: PlanGenerateRequest) -> PlanGenerateResponse:
    return await run_graph(request)
```

| 方法 | 用途 |
|---|---|
| `generate_plan()` | Java 调 Python 的唯一 P0 主入口，接收用户输入、领域 schema、记忆上下文，返回候选 Plan 或反问。 |

---

### 8.6 `app/contracts` 契约文件结构

#### 8.6.1 `contract-manifest.json`

Java 与 Python 各保存一份同版本 manifest，通过 hash 校验保证契约一致。

```json
{
  "contractVersion": "v1",
  "schemaHash": "sha256:...",
  "schemas": {
    "AgentPlan": "sha256:...",
    "PlanGenerateRequest": "sha256:...",
    "PlanGenerateResponse": "sha256:..."
  }
}
```

Hash 计算规则：

1. 每个 schema 文件先按 JSON 解析，再序列化为 canonical JSON 后计算 `sha256`。
2. canonical JSON 使用 UTF-8；对象 key 递归按字典序排列；数组顺序保持不变；不输出无意义空白；不允许注释或非标准 JSON 扩展。
3. `schemas` 中每个条目的 hash 为对应 schema canonical JSON 字节的 `sha256`。
4. manifest 顶层 `schemaHash` 基于 `{ "contractVersion": "...", "schemas": { ... } }` 的 canonical JSON 计算，不把 `schemaHash` 自身纳入输入，避免循环依赖。
5. Java 和 Python 必须使用同一套 canonical JSON 与 SHA-256 规则；任何 schema 语义变更都必须重新生成 schema hash。

Java 侧位置：

```text
agent-api/src/main/resources/agent-contract/contract-manifest.json
agent-api/src/main/resources/agent-contract/agent-plan.schema.json
agent-api/src/main/resources/agent-contract/runtime.schema.json
```

Python 侧位置：

```text
agent-runtime/app/contracts/contract-manifest.json
agent-runtime/app/contracts/agent-plan.schema.json
agent-runtime/app/contracts/runtime.schema.json
```

#### 8.6.2 启动校验

`agent-runtime` 启动时读取本地契约文件，校验 Pydantic 模型可解析契约样例，并暴露：

```text
GET /runtime/v1/contracts/version
```

返回 `contractVersion`、`schemaHash` 和各 schema hash。`agent-service` 启动时读取 `agent-api` 内置 manifest，并调用 `agent-runtime` 的契约版本接口：

```text
dev/test：hash 不一致，启动失败
prod：应用进程允许启动，但 readiness DOWN，Agent 请求不可服务，并输出 ERROR 日志
```

#### 8.6.3 `app/contracts/models.py`

用途：Python Pydantic 模型定义。模型可以手写或生成，但必须与 Python 本地契约文件一致；Python 业务代码 import 该模型，不额外维护业务 schema。

---

### 8.7 `app/core/settings.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    appName: str = "agent-runtime"
    host: str = "0.0.0.0"
    port: int = 9230
    llmBaseUrl: str
    llmApiKey: str
    llmModel: str
    llmTimeoutSeconds: int = 30
    llmTemperature: float = 0.0
    promptDir: str = "app/prompts"
    contractVersion: str = "v1"
    enablePlanRepair: bool = True
    logLevel: str = "INFO"


def get_settings() -> Settings:
    return Settings()
```

`.env.example`：

```properties
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=replace-me
LLM_MODEL=deepseek-v4-pro
LLM_TIMEOUT_SECONDS=30
LLM_TEMPERATURE=0.0
PROMPT_DIR=app/prompts
```

LLM Provider 配置归属：P0 中 `base-url / api-key / model / timeout / temperature` 由 Python `agent-runtime` 管理。Java 只配置 `agent.runtime.base-url`，不向 Python 透传 API Key。后续如需统一策略，可在 Java 增加非敏感的 `llm-policy`，但密钥仍保留在 Python 运行时环境。

---

### 8.8 `app/core/prompts.py`

```python
from pathlib import Path
from string import Template
from app.core.settings import get_settings

INTENT_PROMPT_MAP = {
    "QUERY": "intents/query",
    "UPDATE": "intents/update",
    "AGGREGATE": "intents/aggregate",
    "EXPORT": "intents/export",
    "BUSINESS_SUBMIT": "intents/business_submit",
    "WORKFLOW_ACTION": "intents/workflow_action",
    "SUMMARY": "intents/summary",
}


def load_prompt(name: str) -> str:
    settings = get_settings()
    path = Path(settings.promptDir) / f"{name}.md"
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, variables: dict) -> str:
    template = Template(load_prompt(name))
    return template.safe_substitute(**variables)


def select_intent_prompt(intent: str) -> str:
    return INTENT_PROMPT_MAP.get(intent, "intents/query")


def render_intent_prompt(intent: str, variables: dict) -> str:
    return render_prompt(select_intent_prompt(intent), variables)
```

#### 8.8.1 Prompt 文件规则

`system.md` 定义总边界：Python 只生成结构化 Plan，不直接调用业务服务，不输出 `executionMode`、`riskLevel`、`affectedCount`。

`intents/query.md`：生成查询类 Plan，不得生成 actions。

`intents/update.md`：生成修改类 Plan，必须包含 filters 或 useLastResult，并包含 actions。

`intents/aggregate.md`：生成聚合统计 Plan，必须使用嵌套 `aggregate.groupBy / aggregate.metrics`，不得使用顶层 `groupBy / metrics`。

`intents/export.md`：生成导出 Plan，必须使用 `exportSpec`，不得决定同步或异步导出。

`intents/business_submit.md`：面向业务对象、业务申请、业务变更、业务命令。不得因为底层可能调用 workflow-service 就改成 `WORKFLOW_ACTION`。

`intents/workflow_action.md`：仅面向已有流程实例、审批节点、待办任务。必须生成 `workflowAction.action`，且 action 只能来自 Java 传入的 `workflowActions`。

`intents/summary.md`：生成总结计划，不直接输出最终长篇总结正文。

`clarify.md`：生成反问。

`repair.md`：仅修复 JSON 格式、枚举大小写、字段别名、缺失 targetType 等结构问题，不修复权限问题。

---

### 8.9 `app/core/llm_client.py`

```python
from typing import TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LlmClient:
    async def chat_text(self, messages: list[dict], temperature: float = 0.0) -> str:
        """调用 LLM 返回文本。"""
        raise NotImplementedError

    async def chat_json(self, messages: list[dict], response_model: Type[T]) -> T:
        """调用 LLM 并解析为 Pydantic 模型。"""
        raise NotImplementedError
```

P0 实现建议：使用 OpenAI-compatible Chat Completions API，temperature 默认 `0.0`，`chat_json()` 至少支持一次 JSON 解析失败后的 repair。

---

### 8.10 `app/core/planning.py`

```python
from app.contracts.models import AgentPlan, DomainSchema, ClarifyQuestion


def normalize_plan(plan: AgentPlan, domain_schemas: list[DomainSchema]) -> AgentPlan:
    """规范化 domain、intent、operator、operation、field 等值。"""
    return plan


def validate_plan_shape(plan: AgentPlan, domain_schemas: list[DomainSchema]) -> list[str]:
    """校验 Plan 的结构合法性，只做 schema 层校验，不做权限和风控。"""
    return []


def should_clarify(plan: AgentPlan | None, errors: list[str]) -> bool:
    """根据缺槽、歧义、结构错误判断是否需要反问。"""
    return bool(errors)


def build_clarify_question(errors: list[str]) -> ClarifyQuestion:
    """将结构错误或歧义转换为用户可理解的反问。"""
    return ClarifyQuestion(question="请补充必要信息", missingFields=errors, options=[])
```

结构校验规则：

| Intent | Python 侧最低结构要求 |
|---|---|
| `QUERY` | 有 domain；有 filters、keyword、useLastResult 或上下文引用。 |
| `UPDATE` | 有 domain、filters 或 useLastResult、actions。 |
| `AGGREGATE` | 有 domain；有 `aggregate.groupBy` 或 `aggregate.metrics`。 |
| `EXPORT` | 有 domain；有 filters 或 useLastResult；可包含 `exportSpec`。 |
| `BUSINESS_SUBMIT` | 有 domain；能识别业务对象或业务变更。 |
| `WORKFLOW_ACTION` | 有 `workflowAction.action`，且 action 必须在 `domainSchemas.workflowActions` 内；`DETAIL/APPROVE/REJECT` 必须满足 `requiredContext`，并满足 `requiredAnyOf` 中至少一组上下文，例如 `processId` 或 `todoId`。 |
| `SUMMARY` | 有待总结对象或 useLastResult。 |

---

### 8.11 `app/core/graph.py`

```python
from langgraph.graph import StateGraph
from app.contracts.models import PlanGenerateRequest, PlanGenerateResponse
from app.core.graph_nodes import (
    load_context_node,
    understand_node,
    clarify_node,
    plan_node,
    repair_node,
    finalize_node,
    route_after_understand,
    route_after_plan,
)


def build_agent_graph():
    graph = StateGraph(dict)
    graph.add_node("load_context", load_context_node)
    graph.add_node("understand", understand_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("plan", plan_node)
    graph.add_node("repair", repair_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "understand")
    graph.add_conditional_edges("understand", route_after_understand)
    graph.add_conditional_edges("plan", route_after_plan)
    graph.add_edge("repair", "finalize")
    graph.add_edge("clarify", "finalize")
    return graph.compile()


async def run_graph(request: PlanGenerateRequest) -> PlanGenerateResponse:
    graph = build_agent_graph()
    state = {"request": request}
    result = await graph.ainvoke(state)
    return result["response"]
```

Graph 流程：

```text
load_context_node
  ↓
understand_node
  ↓
是否需要反问？
  ├── 是 → clarify_node → finalize_node
  └── 否 → plan_node
          ↓
      Plan 是否合规？
          ├── 是 → finalize_node
          └── 否 → repair_node → finalize_node
```

---

### 8.12 `app/core/graph_nodes.py`

```python
async def load_context_node(state: dict) -> dict:
    """加载 Java 请求中的用户输入、领域 schema、记忆上下文。"""
    return state

async def understand_node(state: dict) -> dict:
    """识别初步 domain、intent、targetType，并判断是否存在明显歧义。"""
    return state

def route_after_understand(state: dict) -> str:
    """understand 后的路由：需要反问则进入 clarify，否则进入 plan。"""
    return "clarify" if state.get("need_clarify") else "plan"

async def clarify_node(state: dict) -> dict:
    """生成 ClarifyQuestion。"""
    return state

async def plan_node(state: dict) -> dict:
    """调用 LLM 生成 AgentPlan，并进行 normalize + validate。"""
    return state

def route_after_plan(state: dict) -> str:
    """plan 后的路由：结构合法则 finalize，否则 repair。"""
    return "repair" if state.get("plan_errors") else "finalize"

async def repair_node(state: dict) -> dict:
    """对 LLM 输出的候选 Plan 做一次结构修复。"""
    return state

async def finalize_node(state: dict) -> dict:
    """组装 PlanGenerateResponse。"""
    return state
```

#### 8.12.1 业务提交与工作流动作在 Python 节点中的处理规则

| 判断依据 | 归类 |
|---|---|
| 用户操作对象是 employee、transaction 等业务对象 | `BUSINESS_SUBMIT` 或 `UPDATE` |
| 用户操作对象是业务变更、业务申请 | `BUSINESS_SUBMIT` |
| 用户操作对象是流程实例、审批节点、待办任务 | `WORKFLOW_ACTION` |
| 用户表达“提交/处理/通过它”且上下文只有业务变更 | `BUSINESS_SUBMIT` |
| 用户表达“提交/处理/通过它”且上下文只有工作流待办 | `WORKFLOW_ACTION` |
| 两者都可能 | `CLARIFY` |

Python 不判断底层是否调用 workflow-service。底层 `DIRECT_UPDATE / CHANGE_REQUEST / WORKFLOW_SUBMIT / BUSINESS_COMMAND / WORKFLOW_ACTION / BLOCKED` 由 Java `ExecutionModeResolver` 决定。

Workflow 二层动作识别规则：

| 用户表达 | Plan 输出 |
|---|---|
| “查我的待办”“有什么需要我处理” | `intent=WORKFLOW_ACTION, workflowAction.action=TODO` |
| “看一下流程 123”“这个流程详情” | `intent=WORKFLOW_ACTION, workflowAction.action=DETAIL` |
| “审批通过流程 123”“通过它” | `intent=WORKFLOW_ACTION, workflowAction.action=APPROVE` |
| “驳回流程 123”“拒绝这个待办” | `intent=WORKFLOW_ACTION, workflowAction.action=REJECT` |

Python 只负责输出二层 `action` 和可识别的 `processId/todoId/reason`。`operator` 由 Java 注入；当 `APPROVE/REJECT` 从 `LAST_RESULT` 继承到多个流程或待办时，P0 必须反问或返回无法生成可执行 Plan，不默认批量审批。

---

### 8.13 Prompt 与 Graph 的调用关系

```text
understand_node
  ├── render_prompt("system")
  └── 使用 domainSchemas + memoryContext 初步识别 domain / intent / targetType

plan_node
  ├── render_prompt("system")
  ├── select_intent_prompt(candidateIntent)
  └── render_intent_prompt(candidateIntent)

clarify_node
  ├── render_prompt("system")
  └── render_prompt("clarify")

repair_node
  ├── render_prompt("system")
  ├── render_intent_prompt(candidateIntent)
  └── render_prompt("repair")
```

Intent 与 prompt 文件映射：

| Intent | Prompt 文件 |
|---|---|
| `QUERY` | `prompts/intents/query.md` |
| `UPDATE` | `prompts/intents/update.md` |
| `AGGREGATE` | `prompts/intents/aggregate.md` |
| `EXPORT` | `prompts/intents/export.md` |
| `BUSINESS_SUBMIT` | `prompts/intents/business_submit.md` |
| `WORKFLOW_ACTION` | `prompts/intents/workflow_action.md` |
| `SUMMARY` | `prompts/intents/summary.md` |
| `CLARIFY` | `prompts/clarify.md` |

---

### 8.14 Python 侧不实现内容

P0 明确不在 Python 中实现以下内容：

1. 不实现业务 Adapter。
2. 不调用 employee、transaction、workflow、es-query 服务。
3. 不实现权限判断。
4. 不实现风险评估。
5. 不实现确认单。
6. 不实现记忆持久化。
7. 不实现导出任务。
8. 不实现审计记录。
9. 不实现复杂 Prompt Registry；仅按 intent 选择 prompt 文件。
10. 不实现 TaskRunner。
11. 不实现向量记忆。
12. 不实现多 Agent 协作。

---

### 8.15 Java/Python 对齐要求

#### 8.15.1 契约版本

Java 与 Python 通过契约文件和 schemaHash 保持一致。Java 侧 `agent-api/src/main/resources/agent-contract` 与 Python 侧 `agent-runtime/app/contracts` 必须包含相同 `contractVersion` 与 `schemaHash`。

```text
contractVersion = v1
```

不兼容变更必须升级版本。

推荐校验流程：

```text
agent-service 启动
  → 读取 agent-api 内置 contract-manifest.json
  → 调 agent-runtime /runtime/v1/contracts/version
  → 比对 contractVersion + schemaHash
  → 不一致时 dev/test 启动失败；prod 进程保留但 readiness DOWN，Agent API 拒绝服务

agent-runtime 启动
  → 读取本地 contract-manifest.json
  → 校验 Pydantic models 可解析契约样例
  → 暴露 /runtime/v1/contracts/version
```

#### 8.15.2 枚举对齐

以下枚举必须与 Java 保持一致：

```text
AgentIntent
AgentWorkflowAction
TargetType
PlanFilter.operator
PlanAction.operation
ResponseType
```

#### 8.15.3 Schema 对齐测试

Python 端至少提供以下测试：

| 测试 | 用途 |
|---|---|
| `test_contracts.py` | 验证 Python 本地契约文件、Pydantic 模型与 contract manifest 的 schemaHash 一致，并可解析 Java 请求/响应样例。 |
| `test_prompt_render.py` | 验证 system、clarify、repair 及各 intent prompt 可正常渲染。 |
| `test_plan_shape.py` | 验证 QUERY/UPDATE/AGGREGATE/EXPORT/BUSINESS_SUBMIT/WORKFLOW_ACTION/SUMMARY 等 Plan 最小结构。 |

#### 8.15.4 与 Java 决策链的关系

Python 输出的 `AgentPlan` 进入 Java 后，必须经过：

```text
PlanNormalizeService
  → PlanValidationService
  → FieldPolicyEvaluator
  → AffectedCountService
  → RiskEvaluator
  → ExecutionModeResolver
  → ConfirmationService（仅需要确认时）
  → AgentExecutionDispatcher
```

Python 侧校验只保证“结构可读”，Java 侧校验才保证“可执行、可授权、可控风险”。

## 9. Plan DSL 规范

### 9.1 查询示例

```json
{
  "planId": "plan-001",
  "domain": "employee",
  "intent": "QUERY",
  "targetType": "BUSINESS_OBJECT",
  "filters": [
    {"field": "idCardNo", "operator": "EQ", "value": "110101199001010011"}
  ],
  "actions": [],
  "requiresConfirmation": false
}
```

### 9.2 修改示例

```json
{
  "planId": "plan-002",
  "domain": "employee",
  "intent": "UPDATE",
  "targetType": "LAST_RESULT",
  "resultRefId": "result-001",
  "filters": [],
  "actions": [
    {"field": "position", "operation": "SET", "value": "HRBP"}
  ],
  "requiresConfirmation": true
}
```

### 9.3 聚合示例

```json
{
  "planId": "plan-003",
  "domain": "transaction",
  "intent": "AGGREGATE",
  "filters": [
    {"field": "transType", "operator": "EQ", "value": "PAYMENT"}
  ],
  "aggregate": {
    "groupBy": ["transType"],
    "metrics": [
      {"field": "amount", "function": "SUM", "alias": "totalAmount"},
      {"field": "transId", "function": "COUNT", "alias": "count"}
    ]
  },
  "requiresConfirmation": false
}
```

### 9.4 工作流动作示例

```json
{
  "planId": "plan-004",
  "domain": "workflow",
  "intent": "WORKFLOW_ACTION",
  "targetType": "WORKFLOW_PROCESS",
  "workflowAction": {
    "processId": "wf-123",
    "action": "APPROVE",
    "reason": "确认通过"
  },
  "requiresConfirmation": true
}
```

---

## 10. 字段权限与风控配置

### 10.1 application-agent.yml 示例

```yaml
server:
  port: 9220

spring:
  application:
    name: agent-service
  profiles:
    active: datasource,redis,agent

agent:
  runtime:
    base-url: http://localhost:9230
    connect-timeout-ms: 3000
    read-timeout-ms: 30000

  memory:
    enabled: true
    default-session-ttl-hours: 24
    default-long-term-ttl-days: 365

  export:
    sync-max-rows: 1000
    async-max-rows: 100000
    storage-mode: local # local / shared-filesystem / object-storage
    base-dir: ./data/agent/export
    public-base-url:
    expire-hours: 24

    # 多实例部署最小落地建议：
    # 1. 单实例或本地开发可使用 local。
    # 2. 多实例生产环境至少使用 shared-filesystem，将 base-dir 挂载到所有 agent-service 实例的同一路径。
    # 3. 如已有对象存储或文件服务，使用 object-storage，并通过 public-base-url 或后端下载接口返回文件。

  domains:
    employee:
      enabled: true
      display-name: 员工域
      roles:
        agent:viewer:
          allow-intents: [QUERY, AGGREGATE, EXPORT, SUMMARY]
          deny-intents: [UPDATE, BUSINESS_SUBMIT, WORKFLOW_ACTION]
        agent:admin:
          allow-intents: [QUERY, UPDATE, AGGREGATE, EXPORT, BUSINESS_SUBMIT, SUMMARY]
          max-update-affected: 20

      risk:
        operations:
          UPDATE:
            confirm-required: true
            double-confirm-affected: 10
            workflow-affected: 50
            block-affected: 100
          DELETE:
            enabled: false
        field-risk:
          LOW:
            decision: CONFIRM_REQUIRED
            max-affected: 50
          MEDIUM:
            decision: CONFIRM_REQUIRED
            max-affected: 20
            double-confirm-affected: 10
          HIGH:
            decision: WORKFLOW_REQUIRED
            max-affected: 5
          CRITICAL:
            decision: BLOCKED

      fields:
        name:
          show: true
          queryable: false
          writable: false
          exportable: true
          masked: false
          risk-level: LOW
          allowed-operators: []

        position:
          show: true
          queryable: false
          writable: true
          exportable: true
          masked: false
          direct-update-allowed: false
          workflow-required: true
          risk-level: MEDIUM
          max-affected: 20
          allowed-actions: [SET, CLEAR]
          allowed-operators: []

        idCardNo:
          show: false
          queryable: true
          writable: false
          exportable: false
          masked: true
          mask-type: ID_CARD
          risk-level: HIGH
          allowed-operators: [EQ]

    transaction:
      enabled: true
      display-name: 交易域
      roles:
        agent:viewer:
          allow-intents: [QUERY, AGGREGATE, EXPORT, SUMMARY]
        agent:admin:
          allow-intents: [QUERY, UPDATE, AGGREGATE, EXPORT, BUSINESS_SUBMIT, SUMMARY]

      risk:
        operations:
          UPDATE:
            confirm-required: true
            double-confirm-affected: 10
            block-affected: 100

      fields:
        transId:
          show: true
          queryable: true
          writable: false
          exportable: true
          risk-level: LOW
          allowed-operators: [EQ, IN]

        transType:
          show: true
          queryable: true
          writable: true
          exportable: true
          direct-update-allowed: true
          risk-level: MEDIUM
          allowed-actions: [SET]
          allowed-operators: [EQ, IN]

        amount:
          show: true
          queryable: false
          writable: false
          exportable: true
          masked: true
          mask-type: AMOUNT
          risk-level: HIGH
          allowed-operators: []

    workflow:
      enabled: true
      display-name: 工作流域
      roles:
        agent:viewer:
          allow-intents: [WORKFLOW_ACTION]
        agent:admin:
          allow-intents: [WORKFLOW_ACTION]
      risk:
        operations:
          WORKFLOW_ACTION:
            confirm-required: false
            double-confirm-affected: 1
            block-affected: 10
      workflow-actions:
        TODO:
          read-only: true
          required-roles: [agent:viewer, agent:admin]
          required-context: []
          required-any-of: []
          requires-confirmation: false
          operator-source: CURRENT_USER
        DETAIL:
          read-only: true
          required-roles: [agent:viewer, agent:admin]
          required-context: []
          required-any-of:
            - [processId]
            - [todoId]
          requires-confirmation: false
          operator-source: CURRENT_USER
        APPROVE:
          read-only: false
          required-roles: [agent:admin]
          required-context: []
          required-any-of:
            - [processId]
            - [todoId]
          requires-confirmation: true
          double-confirm-affected: 1
          block-affected: 10
          operator-source: CURRENT_USER
        REJECT:
          read-only: false
          required-roles: [agent:admin]
          required-context: []
          required-any-of:
            - [processId]
            - [todoId]
          requires-confirmation: true
          double-confirm-affected: 1
          block-affected: 10
          operator-source: CURRENT_USER
      fields:
        processId:
          show: true
          queryable: true
          writable: false
          exportable: false
          risk-level: MEDIUM
          allowed-operators: [EQ]

        todoId:
          show: true
          queryable: true
          writable: false
          exportable: false
          risk-level: MEDIUM
          allowed-operators: [EQ]

        reason:
          show: true
          queryable: false
          writable: true
          exportable: false
          risk-level: LOW
          allowed-actions: [SET]

```

### 10.2 默认拒绝原则

```text
未配置领域 → 拒绝
未配置字段 → 拒绝
字段 show=false → 不展示给用户/Agent 输出
字段 queryable=false → 不允许作为查询条件
字段 writable=false → 不允许修改
字段 exportable=false → 不允许导出
字段 masked=true → 输出和导出均需脱敏
operator 不在 allowed-operators → 拒绝
action 不在 allowed-actions → 拒绝
workflow action 不在 workflow-actions → 拒绝
workflow action required-roles 不匹配 → 拒绝
workflow action required-context 缺失 → 反问或拒绝
workflow action required-any-of 任一组都不满足 → 反问或拒绝
```

---

## 11. 数据表设计

### 11.1 `agent_conversation`

```sql
CREATE TABLE agent_conversation (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(128) NOT NULL,
  title VARCHAR(255),
  status VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

### 11.2 `agent_turn`

```sql
CREATE TABLE agent_turn (
  id VARCHAR(64) PRIMARY KEY,
  conversation_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(128) NOT NULL,
  role VARCHAR(32) NOT NULL,
  message TEXT,
  plan_json JSON,
  result_json JSON,
  created_at DATETIME NOT NULL
);
```

### 11.3 `agent_memory`

```sql
CREATE TABLE agent_memory (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(128) NOT NULL,
  conversation_id VARCHAR(64),
  domain VARCHAR(64),
  scope VARCHAR(32) NOT NULL,
  memory_type VARCHAR(64) NOT NULL,
  memory_key VARCHAR(255) NOT NULL,
  memory_value JSON NOT NULL,
  source VARCHAR(64) NOT NULL,
  confidence DECIMAL(5,4),
  expires_at DATETIME,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX idx_memory_user_domain(user_id, domain),
  INDEX idx_memory_conversation(conversation_id),
  INDEX idx_memory_type(user_id, memory_type)
);
```

### 11.4 `agent_confirmation`

```sql
CREATE TABLE agent_confirmation (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(128) NOT NULL,
  conversation_id VARCHAR(64) NOT NULL,
  plan_json JSON NOT NULL,
  execution_mode VARCHAR(64) NOT NULL,
  risk_decision VARCHAR(64) NOT NULL,
  affected_count BIGINT,
  summary TEXT,
  status VARCHAR(32) NOT NULL,
  execution_id VARCHAR(64),
  expires_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uk_agent_confirmation_execution_id (execution_id),
  KEY idx_agent_confirmation_status_expires (status, expires_at)
);
```

确认幂等规则：

1. 用户确认时必须使用 CAS 更新：`UPDATE agent_confirmation SET status='CLAIMED', execution_id=? WHERE id=? AND status='PENDING'`。
2. CAS 返回 0 表示确认单已过期、已拒绝、已被 claim 或已执行，不能再次执行。
3. `confirmAndClaim()` 返回 `ExecutionClaim`，编排层据此组装 `AgentExecutionContext`。
4. 执行分发必须携带 `execution_id`；同一 `execution_id` 只能执行一次。
5. 执行结束后更新状态为 `SUCCEEDED` 或 `FAILED`。确认单状态集合为 `PENDING / CLAIMED / SUCCEEDED / FAILED / REJECTED / EXPIRED`。

### 11.5 `agent_export_task`

```sql
CREATE TABLE agent_export_task (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(128) NOT NULL,
  conversation_id VARCHAR(64),
  domain VARCHAR(64) NOT NULL,
  plan_json JSON NOT NULL,
  status VARCHAR(32) NOT NULL,
  file_name VARCHAR(255),
  storage_mode VARCHAR(32) NOT NULL,
  storage_key VARCHAR(512),
  file_path VARCHAR(512),
  download_url VARCHAR(1024),
  expires_at DATETIME,
  total_rows BIGINT,
  exported_rows BIGINT,
  error_message TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

导出存储字段生成规则：

| storage-mode | 字段规则 |
|---|---|
| `local` / `shared-filesystem` | `file_path` 必填，`storage_key` 可为相对路径，`download_url` 可为空，由后端下载接口代理。 |
| `object-storage` | `storage_key` 必填，`file_path` 为空，`download_url` 可选，通常为预签名 URL，`expires_at` 必填。 |

导出文件必须统一通过 `ExportService.download()` 访问。调用方不得直接使用 `file_path` 读取本地文件，也不得直接信任表内长期保存的 `download_url`。

---

## 12. 核心流程

### 12.1 查询流程

```text
用户：查身份证号为 110101199001010011 的员工
  ↓
agent-service 加载会话与记忆
  ↓
agent-runtime 生成 QUERY Plan
  ↓
PlanValidationService 校验
  ↓
FieldPolicyEvaluator 校验 idCardNo 可查询
  ↓
ExecutionModeResolver 决定 QUERY
  ↓
AgentExecutionDispatcher.dispatch(context)
  ↓
EmployeeAgentAdapter.query()
  ↓
MaskerRegistry 对输出字段脱敏
  ↓
MemoryService 保存 LAST_QUERY / 结构化 LAST_RESULT(resultRef)
  ↓
返回结果
```

### 12.2 修改流程

```text
用户：把刚才查到的员工岗位改成 HRBP
  ↓
agent-runtime 基于 memoryContext.lastResultRef 生成 UPDATE Plan(targetType=LAST_RESULT)
  ↓
PlanValidationService 校验 Plan
  ↓
FieldPolicyEvaluator 校验 position 可写、action 允许
  ↓
MemoryService 根据 resultRefId 从服务端 LastResultRef 恢复主键列表或原始查询条件
  ↓
EmployeeAgentAdapter.estimateAffected() 预估影响数量
  ↓
RiskEvaluator 输出 CONFIRM_REQUIRED / DOUBLE_CONFIRM / WORKFLOW_REQUIRED / BLOCKED
  ↓
ExecutionModeResolver 决定 CHANGE_REQUEST / WORKFLOW_SUBMIT / BLOCKED；只有同步写入接口才可选择 DIRECT_UPDATE
  ↓
ConfirmationService 创建确认单
  ↓
用户确认
  ↓
ConfirmationService.confirmAndClaim() 返回 ExecutionClaim(executionId)
  ↓
编排层组装 AgentExecutionContext
  ↓
AgentExecutionDispatcher 调 adapter 执行
  ↓
MemoryService 记录本轮结果
```

### 12.3 高风险二次确认流程

```text
风险结果 = DOUBLE_CONFIRM_REQUIRED
  ↓
返回风险摘要：影响字段、影响数量、执行模式、风险原因
  ↓
用户必须输入确认短语，如“确认执行”
  ↓
ConfirmationService.confirmAndClaim() 校验确认短语
  ↓
ConfirmationService 通过 PENDING → CLAIMED CAS 获取 executionId
  ↓
编排层组装 AgentExecutionContext
  ↓
AgentExecutionDispatcher.dispatch(context) 幂等执行
```

### 12.4 BUSINESS_SUBMIT 流程

```text
用户：提交张三的岗位变更
  ↓
intent = BUSINESS_SUBMIT
  ↓
Java 判断对象为 employee change
  ↓
根据 adapter 能力 + field 契约 + 风控
  ├── BUSINESS_COMMAND
  ├── CHANGE_REQUEST
  └── WORKFLOW_SUBMIT
```

### 12.5 WORKFLOW_ACTION 流程

```text
用户：审批通过流程 123
  ↓
intent = WORKFLOW_ACTION
  ↓
domain = workflow
  ↓
workflowAction.action = TODO / DETAIL / APPROVE / REJECT
  ↓
PlanValidationService 校验 workflowAction 必填字段与 workflow-actions policy
  ↓
AgentPermissionService 校验二层 action 角色权限
 ↓
编排层为 TODO/DETAIL 生成 executionId；APPROVE/REJECT 在确认 claim 时生成 executionId
 ↓
按 action 分支：
  ├── TODO → AgentExecutionDispatcher → WorkflowAgentAdapter.queryTodos(currentUser) → 包装 AgentQueryResult
  ├── DETAIL → 如只有 todoId 先 resolveTodo(todoId, currentUser) → AgentExecutionDispatcher → WorkflowAgentAdapter.detail(processId) → 包装 AgentQueryResult
  ├── APPROVE → 如有 todoId 先 resolveTodo(todoId, currentUser) 生成确认摘要 → 用户确认 → confirmAndClaim → AgentExecutionDispatcher → WorkflowAgentAdapter.approve(processId, operator=currentUser, todoId)
  └── REJECT → 如有 todoId 先 resolveTodo(todoId, currentUser) 生成确认摘要 → 用户确认 → confirmAndClaim → AgentExecutionDispatcher → WorkflowAgentAdapter.reject(processId, operator=currentUser, todoId)

TODO / DETAIL / APPROVE / REJECT 均属于 ExecutionMode.WORKFLOW_ACTION，由 WorkflowActionAdapter 分发。
Agent 不解析 todoId token；只有 todoId 时必须通过 workflow-service resolve API 回查。待办已变化、已处理或不属于 currentUser 时，workflow-service 返回 409 TODO_CHANGED，Agent 返回 CLARIFY 或 BLOCKED。
approve/reject 请求体由 Java 注入 operator=currentUser，并在有 todoId 时原样传回 workflow-service。
```

### 12.6 导出流程

```text
用户：导出刚才查询结果
  ↓
MemoryService.findLastResult()
  ↓
ExportFieldResolver 过滤不可导出字段
  ↓
MaskerRegistry 脱敏
  ↓
rows <= syncMaxRows → EXPORT_SYNC
rows > syncMaxRows → EXPORT_ASYNC
  ↓
ExportService.export() 创建同步文件或异步导出任务
  ↓
下载统一走 ExportService.download()
```

EXPORT_SYNC / EXPORT_ASYNC 是 `ExecutionModeResolver` 的输出，但不通过 `AgentExecutionDispatcher` 调业务 adapter。编排层直接调用 `ExportService.export()`；当需要重新取数时，`ExportService` 内部可通过 `AgentDomainAdapterRegistry` 获取 `QueryableAdapter` 执行查询。

### 12.7 总结流程

```text
用户：总结刚才查询结果
  ↓
agent-runtime 生成 SUMMARY Plan(useLastResult=true 或 resultRefId)
  ↓
PlanValidationService 校验待总结对象
  ↓
MemoryService.findLastResult()
  ↓
MaskerRegistry 对摘要材料脱敏
  ↓
ExecutionModeResolver 决定 SUMMARY
  ↓
SummaryService.summarize()
  ↓
返回摘要 AgentExecutionResult(status=SUCCEEDED)
```

---

## 13. employee / transaction 接入策略

### 13.1 employee 域

| 能力 | P0 支持方式 |
|---|---|
| 查询 | 按当前 employee-service 实际能力提供 schema，可支持详情、分页、count 或 ES 查询；未能准确转换的字段条件不在 P0 schema 暴露。 |
| 修改 | 优先基于结构化 `LAST_RESULT/resultRef` 定位业务主键；根据 field 契约和风控选择 changeRequest / workflowSubmit。只有存在同步安全写入接口时才允许 directUpdate。 |
| 聚合统计 | P0 可支持 count，复杂 groupBy 预留。 |
| 导出 | Agent 侧基于查询结果导出。 |
| 业务提交 | 通过 EmployeeAgentAdapter 创建变更申请或提交流程。 |
| 工作流 | 不在 employee 顶层处理已有流程动作，交给 WorkflowAgentAdapter。 |

### 13.2 transaction 域

| 能力 | P0 支持方式 |
|---|---|
| 查询 | 调 `/txn/query`，P0 schema 只开放能转换为 `Transaction condition` 的等值类条件。 |
| 修改 | 当前 transaction update 为异步提交语义时，按 `BUSINESS_COMMAND` 或异步提交结果处理，不标记为同步 `DIRECT_UPDATE`。 |
| 聚合统计 | 调 `/txn/aggregate`。 |
| 导出 | Agent 侧基于查询结果导出。 |
| 业务提交 | 调 transaction 业务命令接口。 |
| 工作流 | P0 默认不支持，后续可通过 adapter 能力扩展。 |


### 13.3 transaction 聚合适配策略

当前 transaction 业务接口为：

```java
@PostMapping("/aggregate")
public Map<String, Object> aggregate(@RequestBody AggregateRequest request)
```

现有 `AggregateRequest` 结构为：

```java
public class AggregateRequest {
    private Transaction condition;
    private List<String> groupBy;
    private List<String> metrics;
}
```

P0 不修改 transaction-api。Agent 侧保持强类型聚合 DSL：

```java
public class AgentAggregate {
    private List<String> groupBy;
    private List<AgentMetric> metrics;
}
```

由 `TransactionPlanMapper.toAggregateRequest(AgentPlan plan)` 负责适配：

1. 将 `AgentPlan.filters` 转换为 `Transaction condition`。
2. 将 `AgentAggregate.groupBy` 原样转换为 `AggregateRequest.groupBy`。
3. 将 `AgentMetric(field, function, alias)` 转换为 transaction-service 当前支持的 `metrics` 字符串格式。
4. P0 schema 只提供当前 `Transaction condition` 能准确承载的 operator。复杂范围条件、模糊条件或组合条件不在 Agent schema 中暴露；后续如业务接口升级 Criteria DTO，再同步扩展 schema。

该策略保证 Agent DSL 强类型、Java/Python 契约稳定，同时不要求 P0 重构 transaction 现有接口。

---

## 14. 安全与权限设计

### 14.1 认证

沿用现有 Gateway + common-security JWT 模型。`agent-service` 作为 Resource Server，所有 `/agent/**` 请求默认需要认证。

### 14.2 角色

P0 角色沿用：

```text
agent:admin
agent:viewer
```

推荐语义：

| 角色 | 权限 |
|---|---|
| `agent:viewer` | 查询、统计、导出可授权字段，可查看工作流待办和详情。 |
| `agent:admin` | 查询、统计、导出、修改、业务提交，可审批或驳回工作流。 |

### 14.3 字段级权限

字段权限优先级：

```text
系统级 show=false
  > 用户禁止
  > 角色禁止
  > intent 禁止
  > workflow action 禁止
  > field usage 禁止
  > operator/action 禁止
```

### 14.4 脱敏

所有输出统一经过：

```text
Adapter 原始结果
  ↓
FieldPolicyEvaluator 过滤字段
  ↓
MaskerRegistry 脱敏
  ↓
AgentChatResponse / ExportFile
```

---

## 15. 异常处理


### 15.1 异常类

```text
AgentException
 ├── AgentPlanValidationException
 ├── AgentPermissionDeniedException
 ├── AgentRiskBlockedException
 ├── AgentConfirmationExpiredException
 ├── AgentAdapterNotFoundException
 ├── AgentUnsupportedCapabilityException
 ├── AgentRuntimeException
 └── AgentExportException
```

| 异常 | 触发场景 |
|---|---|
| `AgentPlanValidationException` | Plan 结构不合法、缺少必要字段、intent/domain/operator/action 不在允许范围。 |
| `AgentPermissionDeniedException` | 用户、角色、字段或 intent 权限不足。 |
| `AgentRiskBlockedException` | 风控结果为 `BLOCKED`，例如影响数量超阈值或字段风险为 CRITICAL。 |
| `AgentConfirmationExpiredException` | 用户确认时确认单已过期、已拒绝或已执行。 |
| `AgentAdapterNotFoundException` | domain 未注册对应 `AgentDomainAdapter`。 |
| `AgentUnsupportedCapabilityException` | domain 已注册，但未实现当前执行模式要求的能力接口。 |
| `AgentRuntimeException` | 调用 Python Runtime 失败、超时、返回无法解析。 |
| `AgentExportException` | 导出任务创建、写文件、下载文件失败。 |

### 15.2 全局异常处理

#### `AgentExceptionHandler`

```java
@RestControllerAdvice
public class AgentExceptionHandler {
    @ExceptionHandler(AgentException.class)
    public ResponseEntity<AgentChatResponse> handleAgentException(AgentException ex);

    @ExceptionHandler(Exception.class)
    public ResponseEntity<AgentChatResponse> handleUnknown(Exception ex);
}
```

用途：统一返回用户可理解的错误信息。

---

## 16. P0 编码边界

### 16.1 必须实现

1. `agent-service` 服务启动，端口 9220。
2. `agent-runtime` 服务启动，端口 9230。
3. `/agent/chat` 主入口。
4. Python 生成强类型 Plan DSL。
5. Java Plan 归一化与校验。
6. Adapter SPI/Registry。
7. EmployeeAgentAdapter、TransactionAgentAdapter、WorkflowAgentAdapter。
8. 字段契约配置。
9. 字段权限校验。
10. 多维风险矩阵。
11. 确认单与二次确认。
12. Java 统一记忆模型。
13. 查询、修改、聚合、导出、业务提交、工作流动作基础流程。
14. 审计接口预留 + Noop 实现。

### 16.2 可以预留但不实现

1. 真实审计落库。
2. 审计 AOP 切面。
3. 向量长期记忆。
4. 多 Agent 协作。
5. 复杂策略引擎。
6. employee 复杂聚合统计。
7. transaction workflow 接入。

---

## 17. 最小落地顺序建议

1. 新增 `agent-api` DTO、enum。
2. 新增 `agent-service` 空服务，接入 Gateway/Eureka/Config/Security。
3. 新增 `agent-runtime` FastAPI 服务，打通 `/runtime/v1/plans/generate`。
4. 实现 Plan DSL、Java 归一化与 Java 校验。
5. 实现 AgentDomainAdapter SPI 与 Registry。
6. 实现 employee/transaction 查询。
7. 实现字段权限与脱敏。
8. 实现影响数量预估。
9. 实现风险矩阵。
10. 实现确认单。
11. 实现修改执行链。
12. 实现聚合统计。
13. 实现导出。
14. 实现 Java 记忆模型。
15. 增加 workflow action。
16. 增加审计预留接口与 Noop 实现。

---

## 18. 设计闭环说明

本设计满足以下闭环：

| 能力 | 闭环 |
|---|---|
| 反问 | Python 判断缺槽 → Java 返回反问 → 用户补充 → 继续 Plan。 |
| 查询 | Plan → 字段权限 → Adapter 查询 → 脱敏 → 记忆。 |
| 修改 | Plan → 字段权限 → 影响数量 → 风控 → 确认 → 执行。 |
| 聚合 | Plan → 字段权限 → Adapter 聚合 → 返回统计。 |
| 导出 | Plan/上一轮结果 → 字段过滤 → 脱敏 → 同步/异步导出。 |
| 业务提交 | BUSINESS_SUBMIT → Java 决策 ExecutionMode → Adapter 执行。 |
| 工作流动作 | WORKFLOW_ACTION → WorkflowActionSpec.action → WorkflowAgentAdapter → workflow-service。 |
| 多轮 | Conversation + Turn + Memory。 |
| 记忆 | Java 统一 agent_memory。 |
| 逻辑分支 | LangGraph runtime 负责 graph state 与分支。 |
| 权限 | 默认拒绝 + field 契约 + role/user。 |
| 审计 | `AgentAuditRecorder` 预留，P0 不落库。 |

---

## 19. 关键设计原则总结

1. **Python 不执行业务，Java 不理解自然语言。**
2. **Agent 不直接操作业务库，只调用业务服务。**
3. **field 契约是权限、风控、展示、导出的核心事实源。**
4. **影响数量是风控核心维度之一，但不是唯一维度。**
5. **修改必须确认，高风险必须二次确认。**
6. **业务提交和工作流动作顶层区分用户目标，底层再决定执行策略。**
7. **Adapter 是业务接入边界，Agent 核心不写 employee/transaction 业务逻辑。**
8. **记忆由 Java 统一治理，Python 只做运行时 checkpoint。**
9. **审计先预留接口，coding 中明确标注为 P0 不实现。**
10. **P0 保持最小可运行，但包、类、方法结构为后续扩展留足空间。**
