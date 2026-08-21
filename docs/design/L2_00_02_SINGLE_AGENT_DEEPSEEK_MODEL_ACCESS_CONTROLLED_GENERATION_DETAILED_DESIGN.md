# [L2_00_02] 单体 Agent DeepSeek 模型接入与受控生成详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_00_02` |
| 当前版本 | v1.0 |
| 日期 | 2026-08-21 |
| 权威范围 | Provider-neutral 模型任务、问题输入闸门、DeepSeek transport、ID-only action selection、受控 answer generation、ModelContext 和生命周期 |
| 上位文档 | [`L1_00` v1.0](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) |
| 来源文档 | [L2_00_02 v0.23 归档版](历史文档/2026-08-21-v0-baseline/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) |
| 实施状态 | 本地/fake 与一次性 PoC 已验证，DeepSeek Runtime 可显式装配；默认 Provider 仍为 stub；未生产生效 |

## 2. 阅读导航与变更记录

重点：第 7 节任务契约、第 8 节输入闸门、第 9 节选择/回答、第 10 节 transport、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立模型接入稳定基线 | 删除 candidate/付费调用流水，保留 v4 ID-only、answer v2、输入安全、严格 transport 与默认 stub 边界 |

## 3. 目标与范围

### 3.1 目标

把外部模型限制为可替换、受预算和 Schema 约束的不可信计算器：调用前完成输入出域判定，调用后严格解码并 grounding；模型不得决定权限、物理资源、业务参数或工具执行。

### 3.2 范围内

- `StructuredModelGateway`、task registry、call context 和并发预算；
- `QuestionEgressGuard` 与有限问题类别；
- action-selection-v4 exact JSON ID；
- answer-generation-v1/v2 和领域 grounding policy；
- Knowledge rewrite/summary 等结构化 task 的公共接缝；
- DeepSeek `https://api.deepseek.com`、`deepseek-v4-pro` transport、secret、超时、取消和错误映射；
- 默认 stub / 显式 deepseek 组合根。

### 3.3 范围外与不负责

- 领域证据、字段分类、出域策略本身；
- 业务参数生成、业务授权、检索或 Adapter；
- 模型训练、效果调优平台、自动重试、供应商路由和成本结算；
- 把历史一次性 PoC 授权当作新 live 调用许可。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-MODEL-001` | 模型任务以代码绑定定义注册，调用受输入、预算和输出 Schema 约束 |
| `REQ-MODEL-002` | Action 模型只返回已注册能力 ID，arguments 始终为空 |
| `REQ-MODEL-003` | Answer 只表达本次安全载荷支持的事实，grounding 失败不返回候选 |
| `REQ-MODEL-004` | DeepSeek secret、超时、取消、大小和错误均失败关闭且可替换 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-MODEL-001` | `L0_00 SA-C-005/009/011/014/020/021` |
| `CON-MODEL-002` | `L1_00`：模型端口不拥有编排、领域策略或执行参数 |
| `CON-MODEL-003` | `L2_00_01`：selection 决定只含 ID，最终候选由 Core 校验 |
| `CON-MODEL-004` | 外部模型调用必须显式启用；默认配置不得读取或要求 API key |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-MODEL-001`、`CON-MODEL-001` | `DR-MODEL-001`、`DR-MODEL-002`、`DR-MODEL-003` | `IMPL-MODEL-001`、`IMPL-MODEL-002` | `TEST-MODEL-001`、`TEST-MODEL-002` | `VAL-MODEL-001` |
| `REQ-MODEL-002`、`CON-MODEL-003` | `DR-MODEL-004`、`DR-MODEL-005` | `IMPL-MODEL-003` | `TEST-MODEL-003` | `VAL-MODEL-002` |
| `REQ-MODEL-003` | `DR-MODEL-006`、`DR-MODEL-007`、`DR-MODEL-008` | `IMPL-MODEL-004`、`IMPL-MODEL-005` | `TEST-MODEL-004`、`TEST-MODEL-005` | `VAL-MODEL-003` |
| `REQ-MODEL-004`、`CON-MODEL-002`、`CON-MODEL-004` | `DR-MODEL-009`、`DR-MODEL-010`、`DR-MODEL-011` | `IMPL-MODEL-006`、`IMPL-MODEL-007`、`IMPL-MODEL-008` | `TEST-MODEL-006`、`TEST-MODEL-007`、`TEST-MODEL-008` | `VAL-MODEL-004` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Question Guard | 判定原始/改写问题是否可进入外部模型 | 业务授权、文档/字段出域 |
| Model Task Definition | 固定 task ID/version、request builder、response parser、限额 | Runtime 路由、动态 Prompt |
| Gateway | 注册任务、绑定 context、并发/超时、调用 transport、解析 | 领域 grounding 与策略决定 |
| Action Selector | 安全 catalog→exact ID/no-match | arguments、执行、领域语法 |
| Answer Generator | 安全 payload→candidate→grounding | 选择证据/字段、补造事实 |
| DeepSeek Transport | HTTP、secret header、严格 DTO、错误映射 | 任务 Prompt、领域 Schema |
| ModelContext binding | 请求级 request/correlation/cancel/deadline 传播 | 跨请求 session |

依赖方向为 `graph/knowledge/business → model contracts ← gateway/deepseek`；组合根装配具体 Provider。禁止领域模块依赖 DeepSeek DTO；禁止 transport 依赖 Core/领域；禁止模型层反向决定领域出域。

设计以任务定义和 transport 两个稳定契约降低耦合，不引入多供应商路由或 Prompt 管理平台。

## 6. 当前实现基线与最小变更

当前实现具备 Provider-neutral contracts、冻结 task registry、有界 gateway、contextvars 请求绑定、DeepSeek HTTP transport、v4 action selector、answer v1/v2、问题分类和默认 stub 组合根。历史 PoC 已证明固定任务可调用真实接口，但其 manifest/evidence 只作不可变审计，不构成当前授权。

新基线不要求生产代码变更。保留 answer v1 仅用于历史 harness/evidence 或仍显式绑定的兼容调用方，生产 Business answer 使用 v2；Knowledge rewrite/summary 使用各自独立的领域任务定义。禁止为“统一版本”删除历史任务或重写 evidence。

## 7. 公共类型与任务契约

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-MODEL-001` | 每个任务由代码绑定 `ModelTaskDefinition(task_id, task_version, build_request, parse_response, limits)` |
| `DR-MODEL-002` | `FrozenModelTaskRegistry` 按 `(task_id, task_version)` 唯一注册；未注册或对象不一致拒绝 |
| `DR-MODEL-003` | 每次调用必须绑定 `ModelCallContext`，并受请求 deadline、取消和 Provider 并发共同限制 |
| `DR-MODEL-004` | action-selection-v4 使用无 tools 的 JSON object，仅输出 exact capability ID 或 no-match |
| `DR-MODEL-005` | selector catalog 只含模型安全 ID/description/aliases；arguments 和领域 Schema 不出域 |
| `DR-MODEL-006` | answer 只接收领域已批准的最小 safe payload 和 fact IDs |
| `DR-MODEL-007` | 响应必须 strict JSON、唯一 key、finish reason 完整、字节/字符有界 |
| `DR-MODEL-008` | candidate 必须经领域 `AnswerGroundingPolicy` 验证；拒绝时不返回模型文本 |
| `DR-MODEL-009` | 默认 `AGENT_MODEL_PROVIDER=stub`；只有显式 `deepseek` 才读取 `LLM_API_KEY` |
| `DR-MODEL-010` | transport 自动重试次数为 0；HTTP/timeout/schema/cancel 映射有限失败，不暴露正文 |
| `DR-MODEL-011` | Client 由组合根唯一拥有并在 Runtime 关闭时精确关闭一次 |

### 7.2 核心类型

- `ModelTaskId`：action selection、answer generation、knowledge rewrite/summary 等有限枚举。
- `StructuredModelRequest`：task/version、system/user message、structured output mode、token/byte 限额；不可携带任意 SDK 对象。
- `StructuredModelResponse`：完成类型、内容、tool calls 和有限 usage；字段组合严格。
- `ModelTaskResult[T]`：解析后的领域中立输出和有限调用元数据。
- `ModelCallContext`：request ID、correlation ID、deadline、cancellation。

## 8. 问题输入闸门

`QuestionEgressGuard.evaluate(question)` 先规范化，再按“禁止类别优先”分类：JWT/凭证、身份证/员工号/电话/账户等具体标识、控制字符和不允许的敏感输入一律拒绝。允许规则只覆盖已审查的非敏感问题，其中“未包含任何具体员工标识值的单员工详情通用意图”可进入 action selection；它不允许真实标识出域。

判定结果为 `allowed/denied` + 有限 reason + 数据类别集合；拒绝时模型调用必须为 0。领域在此基础上还要执行自己的证据/字段出域策略，公共 Guard 不能放宽领域拒绝。

## 9. 详细功能与处理流程：动作选择与回答生成

### 9.1 action-selection-v4

请求只包含：固定系统指令、规范化问题、排序稳定的模型安全 capability catalog。使用 `response_format=json_object`、`temperature=0`、固定输出 token 上限，无 tool/function calling。

输出只允许：

```json
{"capability_id":"knowledge.query"}
```

或受控 no-match 表达。重复 key、Markdown fence、附加字段、未知 ID、大小写漂移、arguments、自然语言解释均为 `invalid_output`。模型选择之后仍由 Hybrid/Core 校验。

### 9.2 answer-generation-v1/v2

Answer 输入只包含任务固定指令、用户安全问题、领域安全 payload 和 fact IDs。v2 强化业务事实表达和禁止字段约束；v1 只用于仍绑定该版本的历史/兼容任务。

模型输出经 strict parser 得到 `CandidateAnswer(answer_text, cited_fact_ids)`；随后领域 grounding 校验引用存在、事实覆盖、禁止 token 和表达约束。失败返回受控模型节点失败，绝不回退未经校验的原文本。

### 9.3 Knowledge 结构化任务

Knowledge rewrite/summary 复用 Gateway/transport/context，但任务输入、证据引用唯一性、子串校验和版本由 `L2_01_00/02` 拥有。模型层不复制 Knowledge 策略。

## 10. DeepSeek Provider 契约设计

### 10.1 配置

| 配置 | 当前值/边界 |
|---|---|
| base URL | 固定默认 `https://api.deepseek.com`，只允许 HTTPS 受控地址 |
| model | 固定 `deepseek-v4-pro` |
| secret | 进程环境 `LLM_API_KEY`，仅 deepseek 模式必需 |
| concurrency | 默认 4，范围由 `ModelSettings` 校验 |
| action timeout | 默认 8000ms |
| answer timeout | 默认 15000ms |
| request/response | 默认 131072/262144 bytes，有界 |

### 10.2 HTTP 请求

`DeepSeekChatTransport.complete(request, context)` 将 Provider-neutral request 映射为 Chat Completions JSON：`model`、messages、`temperature=0`、`max_tokens`、必要时 `response_format={type:json_object}`。API key 只进入 Authorization header。

禁止传入真实 JWT、密钥、未授权问题、知识正文或业务原始响应。调用次数由上层一次性授权/harness 控制；Runtime 本身不自动重试。

### 10.3 严格响应、错误分类与调用方可见语义

- 仅接受成功 HTTP、允许 Content-Type、有限长度和唯一 JSON key。
- choices 必须唯一且 finish reason 完整；正文和 tool_calls 组合服从 task mode。
- 401/403、429、timeout、connect、5xx、取消、大小和 schema 分别映射有限 `ModelProviderFailureKind`。
- 不保存原始响应，不把供应商错误正文、request ID 或 header 暴露到用户结果。

## 11. 状态、并发、一致性与资源生命周期

- Gateway 使用有界 semaphore；未取得 slot 时在剩余 deadline 内等待或失败，不开无界任务。
- `ModelContextBindingRuntimeInvoker` 在每个 `ainvoke` 建立 context token，并在 finally 恢复，保证并发隔离。
- 取消和 deadline 传播到 transport；取消后不接受迟到响应。
- 每个任务一次调用，无自动 retry/resume；调用是否幂等不作为重放依据。
- API key/Client 存活期为 Runtime 生命周期；问题/payload/response 仅请求期；无数据库事务和数据迁移。

## 12. 权限、安全与审计设计

- Question Guard 与领域 Egress 均允许才可调用；任一拒绝优先。
- `ModelApiKey` 的 `repr`/hash 不暴露值；日志和 evidence 禁止 key、Authorization、原始响应和敏感 payload。
- 记录 task ID/version、provider、状态、有限 failure kind、耗时、调用计数和字节计数；不记录 Prompt 正文。
- 历史 live manifest/authorization/consumed/evidence append-only；新调用需新鲜、精确绑定授权。

## 13. 发布、兼容与回滚

- 默认 stub 不读取 secret，不产生外部调用；显式 deepseek 配置才创建 HTTP Client。
- 新 task version 与旧 version 并存，调用方必须显式绑定；禁止原地修改历史 Prompt/decoder。
- 回滚优先设置 Provider=stub 并重启；若任务版本回滚，组合根、测试和调用方绑定必须同步。
- 不修改公共 Core/HTTP 契约。数据生命周期限于请求内 DTO、HTTP Client 和 append-only 授权证据；无业务持久数据迁移。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-MODEL-001` | `agent-runtime/src/agent_runtime/model/contracts.py`：task/request/response/context/grounding Protocol |
| `IMPL-MODEL-002` | `agent-runtime/src/agent_runtime/model/gateway.py`：`FrozenModelTaskRegistry`、`BoundedStructuredModelGateway.generate(...)` |
| `IMPL-MODEL-003` | `agent-runtime/src/agent_runtime/model/deepseek/action_selector.py`：v4 task、`DeepSeekCapabilitySelector.__call__` |
| `IMPL-MODEL-004` | `agent-runtime/src/agent_runtime/model/deepseek/answer_generator.py`：v1 task、grounded generator |
| `IMPL-MODEL-005` | `agent-runtime/src/agent_runtime/model/deepseek/answer_generator_v2.py`：v2 task |
| `IMPL-MODEL-006` | `agent-runtime/src/agent_runtime/model/deepseek/transport.py`：client factory、`DeepSeekChatTransport.complete` |
| `IMPL-MODEL-007` | `agent-runtime/src/agent_runtime/model/input_guard.py`、`question_policy.py` |
| `IMPL-MODEL-008` | `agent-runtime/src/agent_runtime/model/context.py`、`agent-runtime/src/agent_runtime/model/settings.py`、`agent-runtime/src/agent_runtime/bootstrap.py` |

### 14.2 关键签名

```python
class StructuredModelGateway(Protocol):
    async def generate(
        self,
        *,
        definition: ModelTaskDefinition[TInput, TOutput],
        input: TInput,
        context: ModelCallContext,
    ) -> ModelTaskResult[TOutput]: ...

class StructuredModelTransport(Protocol):
    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse: ...

class AnswerGroundingPolicy(Protocol):
    def validate(self, input: GroundingInput) -> GroundingDecision: ...
```

`build_action_selection_task_definition()`、`build_answer_generation_task_definition()` 和 `build_answer_generation_v2_task_definition()` 返回冻结任务定义；普通 Prompt helper 不作为公共接口。

## 15. 测试与验证设计

### 15.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-MODEL-001` | task registry/gateway/context：`agent-runtime/tests/unit/model` |
| `TEST-MODEL-002` | 代码绑定 task 与版本：`agent-runtime/tests/contract/model/test_code_bound_tasks.py` |
| `TEST-MODEL-003` | v4 exact ID、无 tools、arguments 空：`test_action_selection.py`、`test_capability_selection.py` |
| `TEST-MODEL-004` | answer v1/v2 strict parse：`test_grounded_answer.py`、`test_answer_generation_v2.py` |
| `TEST-MODEL-005` | Knowledge/Business grounding 与禁止事实：领域 contract tests |
| `TEST-MODEL-006` | fake HTTP、headers、timeouts、大小、HTTP/schema failure：`agent-runtime/tests/integration/model` |
| `TEST-MODEL-007` | 问题分类、敏感优先和零调用：`agent-runtime/tests/unit/model/test_input_guard.py`、业务敏感 fixture |
| `TEST-MODEL-008` | 组合根默认 stub、显式 deepseek、并发/取消/关闭：`agent-runtime/tests/unit/test_action_resolution_composition.py`、`agent-runtime/tests/unit/model` |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-MODEL-001` | task registry、gateway、context 与严格 DTO 测试通过 |
| `VAL-MODEL-002` | `VAL-MODEL-008`：v4 catalog/JSON ID/零 arguments/manifest 本地契约通过 |
| `VAL-MODEL-003` | answer v1/v2 与领域 grounding 回归通过，禁止字段和注入文本不被接受 |
| `VAL-MODEL-004` | fake transport、默认 stub、strict mypy、compileall 和全量非 live 回归通过；不以历史 live 证据替代当前测试 |

## 16. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 敏感输入出域 | 问题或 payload 未分类 | Guard + 领域策略双重允许 | 否 |
| 模型控制执行 | 输出 arguments/tool call | no-tools exact ID + Core 再校验 | 否 |
| Prompt/版本漂移 | 原地修改历史任务 | task version 唯一、历史哈希不可变 | 否 |
| secret 泄漏 | repr/log/evidence/异常 | opaque key、零泄漏测试 | 否 |
| 成本失控 | retry/补跑/默认 deepseek | 默认 stub、retry=0、live 精确授权 | 否；任何新 live 调用需授权 |
| 供应商变更 | API/model contract 漂移 | transport contract tests；失败关闭 | 不阻塞非 live 依据 |

## 17. 实施依据

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前 v1.0 可作为模型本地实现、Runtime 装配和代码评审依据 |
| 当前允许实施范围 | Provider-neutral contracts、Guard、v4 selector、answer v1/v2、fake transport、显式 DeepSeek wiring 与非 live 测试 |
| 当前禁止动作 | 未经新鲜授权的真实调用、领域策略扩大、公共 Core/HTTP 变化、自动重试和默认启用 DeepSeek |
| 回滚单位 | Provider 配置、task definitions、Gateway/transport 和组合根绑定按兼容快照回滚 |

## 18. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 任务契约、责任、Provider 边界与追踪一致 | Passed |
| 内审 2 | 输入/输出、安全、错误分类和生命周期一致 | Passed |
| 内审 3 | 真实落点、测试、兼容和可读性检查通过 | Passed |
| 独立评审 | `REV-L2-00-02-001/002` 已修复；模型公共接缝、领域所有权、实现落点与安全边界复核通过 | Passed |

- 当前版本：v1.0。
- 文档状态：Approved。
- 历史 PoC 与证据不可变，但不继承为本版本修订记录或新执行许可。
