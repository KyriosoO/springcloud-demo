# [L2_00_02] 单体 Agent DeepSeek 模型接入与受控生成详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent DeepSeek 模型接入与受控生成详细设计 |
| 文档编号 | `L2_00_02` |
| 文档路径 | `docs/design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Draft |
| 当前版本 | v0.1 |
| 日期 | 2026-07-25 |
| 适用范围 | DeepSeek Provider、用户问题输入闸门、结构化动作选择、受控回答生成、模型预算/失败/观测 |
| 上位文档 | `REQ_00`、`L0_00`、`L1_00` |
| 直接依赖 | `L2_00_01` v0.4（In Review）的模型节点窄输入/决定、能力描述、公共状态和结果隔离；`L2_00_00` 的请求总预算 |
| 关联文档 | `L1_01`、`L1_02`、`L2_01_00`、`L2_02_00` |
| 外部契约 | DeepSeek OpenAI-compatible `/chat/completions`、`deepseek-v4-pro`、Tool Calls、JSON Output |
| 实现基线 | `LLM_API_KEY` 环境变量存在；目标模型代码不存在；2026-07-25 只读 `/models` 验证返回 `deepseek-v4-pro` |
| 是否可作为实现依据 | 否 |
| 实施依据说明 | 本文未独立评审，受控结构化动作付费 PoC 未执行，`SA-GATE-002`、`CR-GATE-003`、`SA-GATE-006` 均为 Open |
| 当前允许实施范围 | 本文编写、契约样例、纯本地 fake transport/模型替身推演 |
| 当前禁止动作 | 创建目标代码/配置/测试；执行付费生成 PoC；发送敏感问题或真实领域数据；关闭任何门禁 |
| 修改权限 | 本轮授权本文及直接相关文档原子同步，并授权 Git 提交、推送；代码、配置、测试和真实模型调用未获实施授权 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 第二批 L2 详细设计 | 创建 DeepSeek 接入、模型输入治理、动作选择、受控回答及实现测试落点 |
| 2 | 2026-07-25 | 7.4、8.2～8.3、12.2、13、17 | 作者第 1 轮自检修复 | 删除官方正式契约未列出的 `parallel_tool_calls` 字段，补充内聚/耦合依据、JSON Output 参数和建议修改路径标记 |
| 3 | 2026-07-25 | 1、2、17～18 | 原子同步 `L2_00_01` v0.4 契约状态 | 更新直接依赖版本/评审状态；模型节点仍只消费 graph wrapper 投影的窄问题输入，不读取 Capability 执行上下文，本文设计规则不变 |
| 4 | 2026-07-25 | 14、18～19 | 本批次收口校验 | 执行严格文档校验并记录 0 errors、0 warnings；状态仍为 Draft，不替代独立评审或真实模型 PoC |

## 3. 背景、目标与范围

### 3.1 背景与问题

`L1_00` 已选择 DeepSeek `deepseek-v4-pro`，但模型是外部、不可信且具有数据出域效应的依赖。模型既不能直接取得完整 Agent state，也不能凭自然语言返回值绕过能力注册、参数校验或领域出域决策。本 L2 需要把供应商协议限制在 Provider 内，并在每次模型调用前执行可验证的输入闸门，在返回后执行结构、事实和边界校验。

### 3.2 目标与验收行为

| 需求编号 | 目标或可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-MODEL-001` | 通过唯一 Provider 接入 `deepseek-v4-pro` | 供应商 DTO、URL、错误码不进入 graph/core/能力契约 | `SA-C-014`、`CR-AD-005` |
| `REQ-MODEL-002` | 用户问题在首次外发前分类和最小化 | denied/unknown 时 DeepSeek 调用为 0，返回 `input_denied` | `CR-GATE-003` |
| `REQ-MODEL-003` | 只能从冻结能力描述产生一个结构化动作候选 | 模型工具名必须映射当前 descriptor；多工具、未知工具、非法参数均拒绝 | `FR-06`、`L2_00_01` 8.6 |
| `REQ-MODEL-004` | 领域结果只有在明确允许且存在 safe payload 时进入模型 | Provider 接口不接受 `domain_result`；拒绝/缺失时回答模型调用为 0 | `SA-C-009/018` |
| `REQ-MODEL-005` | 候选回答受结构和事实约束 | 回答只接纳已注册 grounding policy 验证的候选；无依据内容失败关闭 | `REQ_00` 9、`L1_02` 7.6 |
| `REQ-MODEL-006` | 模型失败与无结果区分 | timeout、provider failure、invalid output 分别映射既定 `ModelNodeFailureKind` | `L2_00_01` 11.1 |
| `REQ-MODEL-007` | 模型调用受统一总预算和本地资源上限约束 | 单调用取 use-case 上限与请求剩余预算较小值；无自动重试 | `CR-AD-004/005` |
| `REQ-MODEL-008` | 凭证安全且配置失败关闭 | 真实 Provider 启用时缺少 `LLM_API_KEY` 启动失败；日志/状态不含密钥 | `L1_00` 5.2、10.2 |
| `REQ-MODEL-009` | Knowledge 可复用公共结构化生成传输而不泄漏供应商协议 | Knowledge 自有 typed port/Prompt 经代码绑定 task 调用 transport | `L1_01` 7.8 |
| `REQ-MODEL-010` | 模型契约可用性有独立 PoC 证据 | 合成非敏感用例达到 15.3 门槛后才可申请关闭 `SA-GATE-002` | `SA-GATE-002` |

### 3.3 范围内

- `deepseek-v4-pro`、正式 `https://api.deepseek.com/chat/completions` 与 Bearer 凭证映射。
- Provider-neutral structured transport、DeepSeek HTTP adapter 和有限 use-case 定义。
- 用户问题敏感分类、确定性最小化、允许/拒绝决定和零调用语义。
- `ActionSelectionNode` 的 DeepSeek 实现、descriptor→tool schema 投影及工具返回校验。
- `AnswerGenerationNode` 的 DeepSeek 实现、safe payload 前置条件、结构化回答和 grounding policy 接缝。
- Knowledge 问题改写/摘要未来复用的代码绑定 structured task 机制；不定义其领域 Prompt。
- 超时、并发、token/byte 预算、错误映射、日志指标、凭证和 PoC。

### 3.4 范围外

- LangGraph state、wrapper 路由、公共状态映射；归 `L2_00_01`。
- Spring→Python 协议和 60 秒总时限源；归 `L2_00_00`。
- Knowledge 的改写语义、域、检索、证据、出域策略和摘要 Prompt。
- Employee/Transaction 字段分类、转换、safe payload 和业务事实规则。
- 读取/业务授权、角色白名单或业务接口。
- 模型微调、代理切换、多 Provider 自动降级、缓存、批处理、流式输出。
- 生产级配额平台、成本系统或自动重试框架。

### 3.5 适用技术剖面

| 剖面 | 适用 | 本文落实 |
|---|---|---|
| Python | 是 | Protocol/dataclass、httpx async client、Provider adapter、typed wrapper、测试 |
| 外部 HTTP/API | 是 | DeepSeek request/response、错误、超时、兼容与 PoC |
| LLM Prompt/Schema | 是 | 代码绑定系统指令、工具投影、JSON response 和输出校验 |
| 安全/出域 | 是 | 问题输入闸门、领域 safe payload 前置条件、凭证和日志 |
| Java | 否 | Spring 只传播总预算；本文不新增 Java 模型客户端 |
| 持久化/迁移 | 否 | 模型请求/响应不持久化，不新增数据库或缓存 |

## 4. 上位约束与追踪关系

### 4.1 约束映射

| 约束编号 | 来源 | 约束 | 落实 | 偏离 |
|---|---|---|---|---|
| `CON-MODEL-001` | `L1_00` `CR-AD-005` | DeepSeek 置于模型端口后 | `DR-MODEL-001/002` | 无 |
| `CON-MODEL-002` | `L2_00_01` 11.1 | 模型节点只返回窄决定 | `DR-MODEL-006/009` | 无 |
| `CON-MODEL-003` | `L2_00_01` 8.2/8.6 | descriptor/候选供应商无关且核心复验 | `DR-MODEL-005/006` | 无 |
| `CON-MODEL-004` | `L1_00` 7.3 | 只有 allowed + safe payload 可生成回答 | `DR-MODEL-008` | 无 |
| `CON-MODEL-005` | `L1_00` 10.2 | 用户问题首次外发必须过闸门 | `DR-MODEL-003/004` | 无 |
| `CON-MODEL-006` | `L1_00` 10.1 | 默认不自动重试模型传输 | `DR-MODEL-011` | 无 |
| `CON-MODEL-007` | `L2_00_00` 11 | 消费同一硬截止剩余预算 | `DR-MODEL-010` | 无 |
| `CON-MODEL-008` | `L1_01`/`L1_02` | 领域拥有 Prompt/出域/事实规则 | `DR-MODEL-007/009` | 无 |
| `CON-MODEL-009` | `L1_00` 5.2 | `LLM_API_KEY` 外置且不泄露 | `DR-MODEL-012` | 无 |
| `CON-MODEL-010` | `SA-GATE-002/006` | 文档/接口核实不能替代 PoC 或真实数据授权 | `DR-MODEL-013/014` | 无 |

### 4.2 端到端追踪矩阵

| REQ/CON | 模块切片 | 设计规则 | 责任主体 | 契约/状态影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-MODEL-001`、`CON-MODEL-001` | Provider | `DR-MODEL-001`、`DR-MODEL-002` | model/deepseek | 供应商隔离 | `IMPL-MODEL-001`、`IMPL-MODEL-006` | `TEST-MODEL-001` | `VAL-MODEL-002` |
| `REQ-MODEL-002`、`CON-MODEL-005` | 输入闸门 | `DR-MODEL-003`、`DR-MODEL-004` | input guard | question decision | `IMPL-MODEL-003`、`IMPL-MODEL-004` | `TEST-MODEL-002`、`TEST-MODEL-003` | `VAL-MODEL-002` |
| `REQ-MODEL-003`、`CON-MODEL-003` | 动作选择 | `DR-MODEL-005`、`DR-MODEL-006` | action selector | tool→candidate | `IMPL-MODEL-007`、`IMPL-MODEL-008` | `TEST-MODEL-004` | `VAL-MODEL-003` |
| `REQ-MODEL-004`、`CON-MODEL-004` | 回答前置 | `DR-MODEL-008` | answer generator | safe payload only | `IMPL-MODEL-009` | `TEST-MODEL-005` | `VAL-MODEL-003` |
| `REQ-MODEL-005`、`CON-MODEL-008` | 回答校验 | `DR-MODEL-007`、`DR-MODEL-009` | grounding registry | typed policy | `IMPL-MODEL-005`、`IMPL-MODEL-010` | `TEST-MODEL-006` | `VAL-MODEL-003` |
| `REQ-MODEL-006`、`CON-MODEL-002` | 失败映射 | `DR-MODEL-015` | Provider wrappers | failure kind | `IMPL-MODEL-006`、`IMPL-MODEL-011` | `TEST-MODEL-007` | `VAL-MODEL-002` |
| `REQ-MODEL-007`、`CON-MODEL-006`、`CON-MODEL-007` | 预算 | `DR-MODEL-010`、`DR-MODEL-011` | gateway | deadline/concurrency | `IMPL-MODEL-002`、`IMPL-MODEL-006` | `TEST-MODEL-008` | `VAL-MODEL-002` |
| `REQ-MODEL-008`、`CON-MODEL-009` | 凭证 | `DR-MODEL-012` | settings/client | secret lifetime | `IMPL-MODEL-002`、`IMPL-MODEL-006` | `TEST-MODEL-009` | `VAL-MODEL-004` |
| `REQ-MODEL-009`、`CON-MODEL-008` | Knowledge 扩展 | `DR-MODEL-007` | structured gateway | code-bound tasks | `IMPL-MODEL-005` | `TEST-MODEL-010` | `VAL-MODEL-003` |
| `REQ-MODEL-010`、`CON-MODEL-010` | PoC/门禁 | `DR-MODEL-013`、`DR-MODEL-014` | live PoC | 合成输入证据 | `IMPL-MODEL-012` | `TEST-MODEL-011` | `VAL-MODEL-005` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 契约 | 修改权限 |
|---|---|---|---|---|---|
| `REQ_00`、`L0_00`、`L1_00` | parent | 下沉模型细节 | 规定范围、边界、门禁 | 上位约束 | 只读 |
| `L2_00_01` | peer/direct dependency | 实现其两个模型 Protocol | 定义窄输入/决定和公共映射 | Python Protocol | 只读 |
| `L2_00_00` | peer | 消费 deadline/context | 定义总预算与跨进程请求 | 执行 scope | 只读 |
| Knowledge L2 | peer | 提供结构化传输和全局输入闸门 | 定义改写/摘要 Prompt、证据与 grounding | typed task adapter | 只读 |
| 业务查询 L2 | peer | 提供全局输入/回答 Provider | 定义字段、safe payload 与事实规则 | grounding policy | 只读 |
| DeepSeek API | external_contract | 严格适配与错误转换 | 提供模型 API | HTTPS JSON | 外部只读 |
| `LLM_API_KEY` | implementation baseline | 只读取并包装 | OS 环境提供 | secret string | 只读，不输出 |

官方证据：

- [DeepSeek 首次 API 调用](https://api-docs.deepseek.com/)列出 `https://api.deepseek.com` 与 `deepseek-v4-pro`。
- [Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion)定义 tool calls、JSON output、finish reason 和响应结构，并明确工具参数仍需调用方校验。
- [JSON Output 指南](https://api-docs.deepseek.com/guides/json_mode/)提示需显式 JSON 指令，且响应可能为空。
- [错误码](https://api-docs.deepseek.com/quick_start/error_codes/)定义 400/401/402/422/429/500/503；本文均不把它们视为业务无结果。
- 2026-07-25 使用环境中的 `LLM_API_KEY` 对 `/models` 做只读调用，返回 `deepseek-v4-pro`；未输出密钥，未执行生成调用。

## 6. 当前实现基线与最小变更方案

### 6.1 已核实事实

1. `LLM_API_KEY` 在当前进程和用户级 OS 环境存在；未读取到文档或日志。
2. 当前仓库没有目标 Python 模型端口、DeepSeek client、input guard 或模型测试。
3. `L2_00_01` 已固定 `ActionSelectionInput/Decision`、`AnswerGenerationInput/Decision` 与 `ModelNodeFailureKind`。
4. 当前没有真实结构化动作 PoC，因此 `/models` 可用不等于 Tool Calls 质量、预算或回答事实约束已验证。
5. 历史 Agent/ES 代码不构成目标模型实现基线。

### 6.2 最小变更方案

| 变更 | 必要性 | 选择 | 不采用 |
|---|---|---|---|
| Provider-neutral structured gateway | 多场景共用传输且隔离供应商 | 代码绑定有限 task | 允许调用方传任意 Prompt/schema，会形成通用模型执行平台 |
| DeepSeek async HTTP client | LangGraph 异步与取消 | `httpx.AsyncClient`、正式 endpoint、non-stream | SDK 会引入供应商/兼容层行为且仍需自定义校验；本期直接 HTTP 更透明 |
| 动作选择 Tool Calls | 让每个 descriptor 带自身 schema | 每能力一个不可逆安全 tool name + fixed unsupported tool | 单一任意 arguments tool 会弱化 schema；beta strict endpoint 不稳定 |
| 回答 JSON Output | 校验 answer 与事实引用 | 结构化 envelope + grounding policy | 直接接纳自然语言 content 无法验证 |
| thinking disabled | 避免 reasoning_content、多轮和高延迟 | 所有本期 task 禁用 | 默认 thinking 增加协议和预算复杂度 |
| zero automatic retry | 避免重复收费和预算放大 | 一次传输失败即 typed failure | Provider 内隐式重试会绕过 LangGraph 决策 |

## 7. 职责、依赖与公共类型

### 7.1 责任分解

| 组件 | 状态 | 唯一职责 | 明确不负责 |
|---|---|---|---|
| `QuestionEgressGuard` | 建议新增 | 问题分类、最小化和允许/拒绝 | 动作选择、业务授权 |
| `StructuredModelGateway` | 建议新增 | 执行代码绑定 task、预算/并发/共同校验 | 领域 Prompt/事实规则 |
| `DeepSeekChatTransport` | 建议新增 | HTTP、凭证、供应商 DTO 和错误转换 | graph state、领域结果 |
| `DeepSeekActionSelector` | 建议新增 | descriptor→tools、响应→窄决定 | 核心参数授权/执行 |
| `DeepSeekAnswerGenerator` | 建议新增 | safe payload→结构化回答候选 | 领域出域策略计算 |
| `GroundingPolicyRegistry` | 建议新增 | 按 canonical capability ID 取得代码绑定验证器 | 动态插件、角色或字段配置 |
| 领域 grounding policy | 关联 L2 建议新增 | 验证候选回答仅使用本域事实 | Provider 协议 |

### 7.2 依赖方向

```text
L2_00_01 ActionSelectionNode / AnswerGenerationNode
  ← DeepSeekActionSelector / DeepSeekAnswerGenerator
      → QuestionEgressGuard
      → StructuredModelGateway
          → DeepSeekChatTransport

DeepSeekAnswerGenerator
  → GroundingPolicyRegistry
      ← Knowledge / Business code-bound grounding policies
```

- core/graph state 不导入 DeepSeek/httpx/provider DTO。
- `DeepSeekChatTransport` 不导入 capability handler、domain result 或 LangGraph Runtime。
- 领域模块只依赖 provider-neutral task/grounding Protocol，不依赖 DeepSeek request/response。
- question、safe payload、Prompt 和 model response 仅存在当前调用栈，不进入持久化或共享 state。

### 7.3 公共类型

| 类型 | 字段/语义 |
|---|---|
| `QuestionDataClass` | `public_knowledge/generic_business/personal_identifier/employee_identifier/transaction_identifier/financial_account/contact/credential_or_secret/free_text_sensitive/unknown` |
| `QuestionEgressDecision` | `disposition: allowed/denied`；allowed 时 `minimized_question`、`policy_version`；denied 时 `reason_code`；互斥 |
| `ModelTaskId` | `action_selection/answer_generation/knowledge_rewrite/knowledge_summary`；有限代码枚举 |
| `ModelCallContext` | `request_id`、`correlation_id`、`deadline_monotonic`；不含 JWT/subject/role |
| `StructuredModelRequest` | `task_id`、代码绑定 instruction/schema、最小 JSON payload、max output；只能由注册 task factory 构造 |
| `StructuredModelResponse` | raw JSON object + safe provider metadata；不含 reasoning content |
| `GroundingDecision` | `accepted: bool`、拒绝时有限 reason enum；不携带原始文本 |

`StructuredModelRequest` 构造器不对任意调用方公开；运行时只通过 `ModelTaskDefinition.build_request` 创建。task definition tuple 在组合根显式绑定并冻结，配置不能增加 Prompt、schema、class 或 endpoint。

### 7.4 内聚与耦合判断

共同传输、凭证、预算和供应商错误聚合在 `StructuredModelGateway`/`DeepSeekChatTransport`，因为它们只因模型提供方或通用调用规则变化；问题分类由输入安全策略拥有，领域 Prompt、safe payload 与事实验证仍由对应能力拥有。`GroundingPolicyRegistry` 只保护“公共回答生成必须取得领域验证器”这一稳定边界，不实现领域字段规则。该分解避免 Provider 依赖业务 DTO，也避免各能力复制 DeepSeek 协议；新增 task 仍需代码和设计，不演化为动态 Prompt 平台。

## 8. 详细功能与流程设计

### 8.1 问题输入闸门

校验顺序：

1. 必须是已由 `L2_00_01` 限制的非空字符串。
2. Unicode NFC、去首尾空白、连续空白折叠；不删除否定、时间、数字或标点。
3. 拒绝 NUL、不可见控制符、疑似 JWT/API key/private key/password 等凭证模式。
4. 依有限检测器标记个人标识、员工标识、交易标识、金融账户、联系方式、自由文本敏感类别。
5. 只有明确匹配 `public_knowledge` 或不含敏感片段且满足已注册业务非敏感句式的 `generic_business` 才允许；无法分类为 `unknown` 并拒绝。
6. allowed 仅返回最小化问题和策略版本 `question-egress-v1`；denied 不返回问题副本。

首期允许示例：

- “增值税小规模纳税人的现行政策是什么”
- “查询员工列表支持哪些条件”
- “查询交易记录支持哪些时间范围”

首期拒绝示例：

- 含完整/疑似身份证、手机号、银行卡、账户、JWT、API key。
- 含具体员工编号、交易号且规则尚未提供可验证的本地占位/恢复机制。
- 无法确认是否公开或可能包含自由文本敏感内容的问题。

该分类是外发控制，不是业务动作授权。拒绝时 `ActionSelectionDecision.failure(kind=input_denied)`，由核心 wrapper 映射 `model_egress_denied/model.input_denied`，DeepSeek transport 调用计数必须为 0。

### 8.2 动作选择

#### 8.2.1 tool 投影

每个启用 `CapabilityDescriptor` 投影一个 function tool：

```text
tool_name =
  "cap_" + safe_slug(capability_id, max=36)
  + "_" + sha256(capability_id).hexdigest()[0:12]
```

- `tool_name` 与 canonical capability ID 的 mapping 只在本次调用内存中存在。
- description 只包含 descriptor 的 display name、description 和 canonical ID，不含 URL、角色、物理索引或秘密。
- parameters 直接深复制 descriptor 的受控 `argument_schema`，强制 `additionalProperties=false`。
- 另加固定无参数工具 `agent_unsupported`。
- 工具总数上限 33（最多 32 个能力 + unsupported），总序列化字节上限 65536。

DeepSeek request 使用：

- `model=deepseek-v4-pro`
- `stream=false`
- `thinking={"type":"disabled"}`
- `temperature=0`
- `tool_choice="required"`
- system message 为代码常量，只要求选择一个工具，不允许执行工具。
- user message 是 canonical JSON：`{"question": "<minimized>"}`。

正式 API 的 `required` 允许返回一个或多个工具；本文不发送官方契约未列出的并行控制字段，而是在响应边界强制“正好一个 tool call”，多调用一律 `invalid_output`。

#### 8.2.2 输出校验

| 响应 | 决定 |
|---|---|
| 正好一个已映射 capability tool，arguments 是有界 JSON object | `candidate(ActionCandidate)`；核心继续校验 |
| 正好一个 `agent_unsupported` 且 arguments 为空 | `unsupported` |
| 无 tool、多个 tool、未知 tool、arguments 非法/越界、content 与 tool 矛盾 | `failure(invalid_output)` |
| Provider timeout/failure | 对应 failure |

Tool Calls 只是候选生成，不授予执行权；模型返回的 arguments 必须再次通过 `L2_00_01` 公共 JSON 限制和对应能力 validator。

### 8.3 受控回答生成

前置条件由核心 route 保证且本实现防御性复核：

- `capability_id` 是 canonical ID。
- `safe_payload` 非空、≤65536 bytes、深度≤8、单集合≤256。
- 问题再次经过同一 `QuestionEgressGuard`；若拒绝，回答生成 transport 调用为 0。
- `GroundingPolicyRegistry` 中存在该 capability 的 policy；缺失失败关闭为 `invalid_output`，不得使用通用宽松 policy。

safe payload 必须由领域 L2 提供最小 envelope：

| 字段 | 必填 | 语义 |
|---|---:|---|
| `schema_version` | 是 | 当前 1 |
| `facts` | 是 | 有界 fact object；每项有稳定 `fact_id` 和结构化 value/source |
| `presentation` | 否 | 领域允许的格式提示，不得含系统指令 |
| `coverage` | 否 | 截断/部分覆盖元数据 |

Provider request 将固定 system instruction 与 user JSON 分离；领域文本只作为 JSON value，不拼入 system instruction。JSON Output 目标：

```json
{
  "answer": "候选回答",
  "used_fact_ids": ["fact-1"],
  "unsupported_claims": []
}
```

请求必须显式设置 `response_format={"type":"json_object"}`，system instruction 必须包含 JSON 输出要求和固定结构示例，并设置 task 的 `max_tokens`；空 content 或 `finish_reason=length` 均失败关闭。

接纳顺序：

1. HTTP/JSON/finish reason 有效，content 非空且只有一个 JSON object。
2. `answer` 1～4096 字符；禁止控制符、工具/URL/角色/策略指令输出。
3. `used_fact_ids` 非空、去重、全部存在于 safe payload；`unsupported_claims` 必须为空。
4. capability 对应 grounding policy 验证实体、数字、状态、关系、引用和 coverage 表达。
5. 全部通过才返回 `AnswerGenerationDecision(answer)`；否则丢弃全文并返回 `invalid_output`。

模型声称引用 fact ID 不能替代语义验证。领域 policy 是事实校验权威；本文只定义调用前置、共同结构与失败关闭。

### 8.4 Knowledge 结构化任务复用

`knowledge_rewrite` 与 `knowledge_summary` 只能由 Knowledge 模块定义的 typed adapter 调用 `StructuredModelGateway`：

- Knowledge 拥有输入 DTO、Prompt、输出 DTO、语义保持/证据验证。
- 本文拥有 Provider request、凭证、共同预算、JSON parsing 和失败映射。
- task definition 必须在组合根代码绑定；配置不能提供任意 Prompt/schema。
- `knowledge_rewrite` 仍须先通过 `QuestionEgressGuard`。
- `knowledge_summary` 仍须收到领域已允许的 evidence safe payload；真实证据受 `SA-GATE-006`。

### 8.5 Provider 请求与响应

请求固定 `POST https://api.deepseek.com/chat/completions`、`Content-Type: application/json`、`Authorization: Bearer <LLM_API_KEY>`。不使用 beta base URL、streaming、prefix/FIM、文件、任意代理地址或调用方提供的 model 参数。

响应共同校验：

- HTTP 200、媒体类型 JSON、body ≤262144 bytes。
- `choices` 正好 1 项。
- `finish_reason` 只允许 task 预期的 `tool_calls` 或 `stop`；`length/content_filter/insufficient_system_resource/null` 均失败。
- response `model` 必须为 `deepseek-v4-pro` 或 Provider 官方等价响应标识的精确 allowlist；未知值失败关闭并记录安全指标。
- reasoning content 不读取、不返回、不持久化。
- usage 仅记录总 token 数值指标，不绑定 user/request 标签，不作为事实。

## 9. 接口与模型契约设计

### 9.1 Provider-neutral Protocol

```python
class StructuredModelGateway(Protocol):
    async def generate(
        self,
        *,
        definition: ModelTaskDefinition[TInput, TOutput],
        input: TInput,
        context: ModelCallContext,
    ) -> ModelTaskResult[TOutput]: ...
```

`ModelTaskResult` 只能是 `success(output)` 或 `failure(ModelProviderFailureKind)`；failure kind 固定为 `input_denied/provider_timeout/provider_failure/invalid_output`。它不携带异常 message、HTTP body、Prompt 或供应商 DTO。

### 9.2 `L2_00_01` Protocol 实现

```python
class DeepSeekActionSelector:
    async def __call__(
        self,
        input: ActionSelectionInput,
    ) -> ActionSelectionDecision: ...

class DeepSeekAnswerGenerator:
    async def __call__(
        self,
        input: AnswerGenerationInput,
    ) -> AnswerGenerationDecision: ...
```

二者不接收 `Runtime`、scope、JWT、domain result 或整个 state。请求上下文/截止时间通过组合根绑定的 request-scoped model context accessor 提供；该 accessor 只能读取 requestId/correlationId/deadline，不读取 token/role。若实现无法在不访问整个 state 的情况下取得 context，必须回到 `L2_00_01` 评审，不得以全局可变变量绕过。

为避免 context 丢失，目标实现采用 Python `contextvars.ContextVar[ModelCallContext]`，仅由 `AgentRuntimeInvoker.ainvoke` 调用边界设置并在 `finally` reset；child task 继承当前 context。不得把它用于图状态、跨请求缓存或领域数据。并发测试必须证明两个请求 context 不串扰。

### 9.3 错误映射

| 触发 | `ModelNodeFailureKind` | 重试 | 安全观测 |
|---|---|---:|---|
| 输入闸门 denied/unknown | `input_denied` | 否 | policy reason enum |
| connect/read/overall timeout、截止耗尽 | `provider_timeout` | 否 | phase + duration |
| HTTP 400/401/402/422 | `provider_failure` | 否 | status class；配置告警 |
| HTTP 429/500/503、连接重置/DNS/TLS | `provider_failure` | 否 | status/transport class |
| 空 content、非法 JSON/tool、多个 choices、finish reason 非法 | `invalid_output` | 否 | stable parse reason |
| 响应超界、model 不匹配、grounding 拒绝 | `invalid_output` | 否 | stable validation reason |

Provider response/error body、exception message 和 Prompt 不进入 `ModelNodeFailure`。`401/402` 表示运维/账户问题，仍不得回退其他模型或服务。

## 10. 权限、安全、审计与出域

### 10.1 调用前置矩阵

| 调用 | 用户问题闸门 | 领域 safe payload | 领域 policy | 真实数据门禁 |
|---|---|---|---|---|
| action selection | 必须 allowed | 不适用 | 不适用 | `CR-GATE-003` 控制敏感问题 |
| Knowledge rewrite | 必须 allowed | 不适用 | Knowledge 改写校验 | `CR-GATE-003` |
| final answer | 必须 allowed | 必须存在 | capability grounding policy 必须存在 | `SA-GATE-006` |
| Knowledge summary | 必须 allowed | 必须是允许证据 | Knowledge evidence policy | `SA-GATE-006` |

任何一个前置条件缺失时 Provider 调用为 0。模型不能读取 JWT、角色、业务授权规则、物理索引、下游 URL、完整 domain result 或策略正文。

### 10.2 凭证

- `LLM_API_KEY` 是唯一目标环境键；实现不回退 `DEEPSEEK_API_KEY`、配置文件明文或默认值。
- 仅 `DeepSeekSettings.from_env` 在启动期读取，包装为 `ModelApiKey`；`repr/str` 固定 `<redacted>`。
- 真实 Provider 模式缺失/空白 key 时 Runtime 启动失败；stub 模式不读取 key。
- key 仅在创建 Authorization header 时显式 reveal；不得进入 dataclass equality/hash、异常、metrics 或 health。

### 10.3 最小审计

安全事件仅记录：correlationId、taskId、model 常量、policyVersion、decision、failure kind/reason enum、耗时、input/output byte bucket、token usage bucket。question、Prompt、tools schema、safe payload、answer、subject、JWT 和 API key 均不记录。

## 11. 状态、并发、一致性与资源预算

### 11.1 调用预算

| Task | 默认超时上限 | max output tokens | 最大输入 bytes | 说明 |
|---|---:|---:|---:|---|
| `action_selection` | 8s | 512 | 65536 | descriptor + minimized question |
| `knowledge_rewrite` | 8s | 512 | 16384 | 具体上限可由 Knowledge 收紧 |
| `answer_generation` | 15s | 1024 | 65536 | safe payload + minimized question |
| `knowledge_summary` | 15s | 1536 | 65536 | 具体证据上限由 Knowledge 收紧 |

实际超时：

```text
min(taskTimeout, deadlineMonotonic - nowMonotonic - 250ms)
```

不足 250ms 时不创建 HTTP 请求并返回 `provider_timeout`。全局模型并发默认 4、允许 1～8；超限不排无界队列，若无法在剩余预算内获得 permit 则 `provider_timeout`。

### 11.2 重试与幂等

- Provider、httpx transport 和 wrapper 自动重试次数固定为 0。
- 模型调用有成本且非幂等；同一请求不会因 429/5xx/timeout 自动重发。
- 语义性再次询问只能由 LangGraph 在未来明确设计并受同一总预算控制；本期图不包含该边。
- 不缓存问题、响应或 Prompt，不持久化 usage。

### 11.3 Context 隔离

`ModelCallContext` 在 `AgentRuntimeInvoker.ainvoke` 外层设置，在 `finally` reset。取消后不接受结果；runtime shutdown 的 `CancelledError` 继续向上，不转成普通 Provider failure。任何后台 task 必须在请求结束前 join/cancel，不得持有 context 继续调用。

## 12. 配置、依赖与组合根

### 12.1 配置

| Key/环境 | 默认 | 校验 | 变更 |
|---|---|---|---|
| `AGENT_MODEL_PROVIDER` | `stub`（P3 前） | `stub/deepseek`；真实部署显式 deepseek | 重启 |
| `LLM_API_KEY` | 无 | deepseek 模式必填 | 重启 |
| `AGENT_MODEL_BASE_URL` | 不开放 | 代码常量 `https://api.deepseek.com` | 修改需评审 |
| `AGENT_MODEL_NAME` | 不开放 | 代码常量 `deepseek-v4-pro` | 修改需评审 |
| `AGENT_MODEL_MAX_CONCURRENCY` | 4 | 1～8 | 重启 |
| `AGENT_MODEL_ACTION_TIMEOUT_MS` | 8000 | 1000～15000 | 重启 |
| `AGENT_MODEL_ANSWER_TIMEOUT_MS` | 15000 | 3000～30000 | 重启 |
| `AGENT_MODEL_MAX_RESPONSE_BYTES` | 262144 | 16384～524288 | 重启 |

`stub` 是显式本地测试实现，不得在真实链路伪装成 DeepSeek 成功。生产启动若配置 stub，readiness detail 只报告 `modelProvider=stub` 的安全枚举，验收不得据此声明真实模型已实现。

### 12.2 依赖

建议新增：在 `agent-runtime/pyproject.toml` 锁定 `httpx==0.28.1`；不得依赖 OpenAI SDK、LangChain model wrapper 或自动 retry 包作为首期 Provider 必需依赖。使用直接 HTTP 是为了明确 request body、timeout、response size 和错误映射，不是建立自研通用 SDK。

### 12.3 组合根

1. 加载并校验 `ModelSettings`。
2. 创建一个进程级 `httpx.AsyncClient`，固定 base URL、连接池上限和无重试 transport。
3. 创建 `QuestionEgressGuard`、`DeepSeekChatTransport` 或 stub。
4. 创建有限 `ModelTaskDefinition` tuple 并冻结。
5. 创建 grounding policy registry；只有当前启用且可能产生 safe payload 的 capability 均有 policy 时才就绪。
6. 将 `DeepSeekActionSelector`、`DeepSeekAnswerGenerator` 注入 `RuntimeCompositionRoot.build`。

组合根可以知道具体 Provider，graph/core/领域流程不得知道。

## 13. 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置 | 责任 | 设计规则 |
|---|---|---|---|---|---|---|
| `IMPL-MODEL-001` | 建议新增 | Python contract | `agent-runtime/src/agent_runtime/model/contracts.py` | enums、decisions、task/gateway/grounding Protocol | Provider-neutral 契约 | `DR-MODEL-001/007/009/015` |
| `IMPL-MODEL-002` | 建议新增 | Python config | `agent-runtime/src/agent_runtime/model/settings.py` | `ModelSettings`、`ModelApiKey` | 配置/凭证/预算 | `DR-MODEL-010/012` |
| `IMPL-MODEL-003` | 建议新增 | Python policy | `agent-runtime/src/agent_runtime/model/input_guard.py` | `QuestionEgressGuard.evaluate` | 分类与最小化 | `DR-MODEL-003/004` |
| `IMPL-MODEL-004` | 建议新增 | Python policy data | `agent-runtime/src/agent_runtime/model/question_policy.py` | finite detectors、`question-egress-v1` | 代码绑定全局规则 | `DR-MODEL-003/014` |
| `IMPL-MODEL-005` | 建议新增 | Python gateway | `agent-runtime/src/agent_runtime/model/gateway.py` | `BoundedStructuredModelGateway`、task registry、grounding registry | 有界任务与领域接缝 | `DR-MODEL-007/009/010/011` |
| `IMPL-MODEL-006` | 建议新增 | Python adapter | `agent-runtime/src/agent_runtime/model/deepseek/transport.py` | `DeepSeekChatTransport.complete` | HTTPS/DTO/error | `DR-MODEL-002/010/011/012/015` |
| `IMPL-MODEL-007` | 建议新增 | Python projection | `agent-runtime/src/agent_runtime/model/deepseek/tools.py` | `project_capability_tools` | descriptor→tool + reverse map | `DR-MODEL-005` |
| `IMPL-MODEL-008` | 建议新增 | Python node implementation | `agent-runtime/src/agent_runtime/model/deepseek/action_selector.py` | `DeepSeekActionSelector.__call__` | 动作选择决定 | `DR-MODEL-003/005/006` |
| `IMPL-MODEL-009` | 建议新增 | Python node implementation | `agent-runtime/src/agent_runtime/model/deepseek/answer_generator.py` | `DeepSeekAnswerGenerator.__call__` | safe payload 回答 | `DR-MODEL-004/008/009` |
| `IMPL-MODEL-010` | 建议新增 | Python validation | `agent-runtime/src/agent_runtime/model/grounding.py` | `GroundingPolicyRegistry.require` | code-bound grounding | `DR-MODEL-007/009` |
| `IMPL-MODEL-011` | 建议新增 | Python mapping | `agent-runtime/src/agent_runtime/model/deepseek/errors.py` | `map_deepseek_failure` | 有限失败转换 | `DR-MODEL-015` |
| `IMPL-MODEL-012` | 建议新增 | PoC test | `agent-runtime/tests/poc/test_deepseek_action_selection_live.py` | opt-in live cases | `SA-GATE-002` 证据 | `DR-MODEL-013/014` |
| `IMPL-MODEL-013` | 建议新增 | Python build | 建议新增：`agent-runtime/pyproject.toml` | `httpx==0.28.1` | Provider 依赖 | `DR-MODEL-002` |
| `IMPL-MODEL-014` | 建议新增 | composition | 建议新增：`agent-runtime/src/agent_runtime/bootstrap.py` | model settings、selector、answer generator、policies | 显式装配 | `DR-MODEL-001/007/014` |

### 13.1 边界关键函数签名

| 路径/符号 | 建议签名 | 输入/校验 | 输出/错误 | 副作用/调用方 |
|---|---|---|---|---|
| `QuestionEgressGuard.evaluate` | `def evaluate(self, question: str) -> QuestionEgressDecision` | NFC、长度、控制符、有限类别；纯函数 | allowed 最小问题或 denied reason；不抛原文异常 | 无；selector/answer/Knowledge task |
| `BoundedStructuredModelGateway.generate` | `async def generate(self, *, definition: ModelTaskDefinition[TIn,TOut], input: TIn, context: ModelCallContext) -> ModelTaskResult[TOut]` | task 必须来自冻结 registry；预算/permit | typed result；不传播供应商异常 | 获取并发 permit，一次 transport |
| `DeepSeekChatTransport.complete` | `async def complete(self, request: DeepSeekRequest, *, timeout_s: float) -> DeepSeekResponse` | request 只能由 task adapter 构造；固定 URL/model | 合法 provider response；typed transport exception | 一次 HTTPS；无 retry |
| `project_capability_tools` | `def project_capability_tools(descriptors: tuple[CapabilityDescriptor, ...]) -> CapabilityToolProjection` | 非空、≤32、schema 已由 registry 验证 | frozen tools + reverse map；冲突为 internal config error | 纯函数；action selector |
| `DeepSeekActionSelector.__call__` | `async def __call__(self, input: ActionSelectionInput) -> ActionSelectionDecision` | question guard、descriptor/tool 限制 | candidate/unsupported/failure；不写 graph state | 至多一次模型调用 |
| `DeepSeekAnswerGenerator.__call__` | `async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision` | question guard、safe payload、policy、大小 | answer/failure；丢弃未验证全文 | 至多一次模型调用 |
| `GroundingPolicyRegistry.require` | `def require(self, capability_id: str) -> AnswerGroundingPolicy` | canonical ID，registry 冻结 | policy；缺失 `MissingGroundingPolicy` 由 generator 转 invalid_output | 无；answer generator |
| `ModelSettings.from_env` | `@classmethod def from_env(cls, env: Mapping[str, str]) -> Self` | provider enum、key、预算和常量 | 冻结 settings；非法配置阻止启动 | 只在启动读取 env |

私有 JSON parsing、header 构造和字符串规范化函数可由实现决定，但不得改变上述输入、失败、重试、出域和日志不变量。

## 14. 测试与验证设计

### 14.1 测试定义

| 测试编号 | 设计规则 | 层级 | 建议路径 | 核心断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-MODEL-001` | `DR-MODEL-001/002` | Architecture/Unit | 建议新增：`agent-runtime/tests/architecture/test_model_dependencies.py` | core/graph/能力无 DeepSeek/httpx DTO 依赖 | 供应商泄漏 |
| `TEST-MODEL-002` | `DR-MODEL-003` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_input_guard.py` | 每个类别、边界和 NFC 行为确定；denied 不保留原文 | 敏感样例 allowed |
| `TEST-MODEL-003` | `DR-MODEL-004` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_zero_call.py` | question denied/unknown 时 transport spy=0 | 先调用后拒绝 |
| `TEST-MODEL-004` | `DR-MODEL-005/006` | Contract | 建议新增：`agent-runtime/tests/contract/model/test_action_selection.py` | tool 映射唯一；单合法 tool→candidate；未知/多 tool/非法 args→invalid | 未注册候选被接纳 |
| `TEST-MODEL-005` | `DR-MODEL-008` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_answer_preconditions.py` | 缺/空/超界 safe payload、缺 policy、question denied 均零调用 | domain result 或拒绝载荷外发 |
| `TEST-MODEL-006` | `DR-MODEL-007/009` | Contract | 建议新增：`agent-runtime/tests/contract/model/test_grounded_answer.py` | fact ID 子集、unsupported 为空、领域 policy 通过才接纳 | 无依据实体/数字被返回 |
| `TEST-MODEL-007` | `DR-MODEL-015` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_deepseek_error_mapping.py` | 全 HTTP/transport/parse/finish reason 到固定 kind；无正文 | 错误映射为 no_result 或泄露 |
| `TEST-MODEL-008` | `DR-MODEL-010/011` | Async Unit | 建议新增：`agent-runtime/tests/unit/model/test_budget_concurrency.py` | 较小 deadline、生效并发、零 retry、取消不接纳晚到结果 | 超预算或多次 HTTP |
| `TEST-MODEL-009` | `DR-MODEL-012` | Unit/Log | 建议新增：`agent-runtime/tests/unit/model/test_credentials.py` | key 缺失启动失败；repr/log/health 无 key | secret 出现在 capture |
| `TEST-MODEL-010` | `DR-MODEL-007` | Contract | 建议新增：`agent-runtime/tests/contract/model/test_code_bound_tasks.py` | 未注册 task/prompt/schema/config class 均不可调用 | 任意 task 被执行 |
| `TEST-MODEL-011` | `DR-MODEL-013/014` | Opt-in PoC | 建议新增：`agent-runtime/tests/poc/test_deepseek_action_selection_live.py` | 仅合成非敏感 descriptors/questions；记录结构与语义指标 | 任一真实/敏感数据进入 PoC |

### 14.2 负向场景来源

- Knowledge：否定、时间条件、法律适用范围被改写或回答改变。
- Employee：身份证、电话、账户、员工编号、指令性自由文本。
- Transaction：交易号、账户、金额组合、写入/聚合诱导。
- 通用：JWT/API key、Prompt injection、多 tool、幻觉字段、超界 JSON、空 content、`finish_reason=length`。

`L2_02_00` 负责把业务类别实例化为稳定 fixtures；本文负责这些 fixtures 到 question guard/Provider spy 的共同断言。

### 14.3 结构化动作 PoC 门槛

PoC 仅在用户另行授权真实模型调用后执行：

1. 使用 10 个合成、非敏感、无真实业务/知识数据的能力选择问题，每题独立执行 3 次，共 30 次。
2. 结构有效率必须 100%：每次均为一个已映射 tool 或 `agent_unsupported`，且 arguments 可由 JSON/核心边界解析；否则门禁不关闭。
3. 预期动作/unsupported 一致率至少 90%；低于门槛说明当前 Prompt/schema 不足，不能用 retry 掩盖。
4. 所有错误候选均须被 deterministic validator 拒绝，未注册动作、动态 URL/DSL/类名的实际执行次数为 0。
5. 记录模型、时间、Prompt/task 版本、case ID、决定和耗时，不记录完整问题以外的真实数据；case 本身进入版本控制。

该门槛只证明结构化动作可行性，不证明知识/业务效果、权限或真实数据出域。

### 14.4 验证定义

| 验证编号 | 工作目录/前置 | 命令/步骤 | 预期 | 当前状态 |
|---|---|---|---|---|
| `VAL-MODEL-001` | `D:\codex` | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md --root D:\codex --strict` | 0 errors、0 warnings；不替代评审/PoC | 已执行：0 errors、0 warnings（2026-07-25） |
| `VAL-MODEL-002` | 未来 `agent-runtime` | `python -m pytest tests/unit/model -q` | input、transport、预算、失败、secret 测试通过 | 未执行：代码不存在 |
| `VAL-MODEL-003` | 未来 `agent-runtime` | `python -m pytest tests/contract/model tests/architecture/test_model_dependencies.py -q` | 节点/领域/依赖契约通过 | 未执行：代码不存在 |
| `VAL-MODEL-004` | 当前环境/未来实现 | 检查 `LLM_API_KEY` 存在性但不输出值；运行 secret/log tests | 环境存在且无泄露 | 存在性已核实；实现测试未执行 |
| `VAL-MODEL-005` | 明确授权付费调用、非敏感 case | `RUN_DEEPSEEK_POC=1 python -m pytest tests/poc/test_deepseek_action_selection_live.py -q` | 满足 14.3 全部门槛 | 未执行：本轮未获真实生成调用授权 |

## 15. 发布、迁移与回滚

- 模型模块为新增 Python 代码，无数据迁移。
- P3 默认 `AGENT_MODEL_PROVIDER=stub`，只验证模型无关图和本地契约；不得声称真实 DeepSeek 完成。
- `SA-GATE-002` 满足后才能将目标环境显式切换为 `deepseek`，并重启形成新冻结快照。
- 回滚优先切回 stub/禁用模型相关能力并重启；对外必须返回明确模型不可用/出域拒绝，不得伪造回答。
- Provider request/response 契约破坏性变化需同步 transport、所有 task adapter 和测试；不能用宽松 JSON parser 临时兼容。
- 不保存模型响应，因此回滚无数据补偿；在途请求失败且不重放。

## 16. 风险、待确认事项与门禁

### 16.1 风险

| 编号 | 类型 | 风险/证据缺口 | 触发 | 影响 | 控制 | 阻塞 |
|---|---|---|---|---|---|---|
| `RISK-MODEL-001` | 可行性 | Tool Calls 实际稳定性未 PoC | 真实 action selection | 非法/误选候选 | 14.3 PoC + deterministic validator | `SA-GATE-002` |
| `RISK-MODEL-002` | 输入分类 | 有限规则漏识别敏感文本 | 复杂业务问题 | 问题泄露 | unknown 默认拒绝、业务 fixtures、零调用 | `CR-GATE-003` |
| `RISK-MODEL-003` | 事实 | 模型虚构但引用合法 fact ID | 回答生成 | 错误事实 | 领域 grounding policy；无法验证则丢弃 | `SA-GATE-006` |
| `RISK-MODEL-004` | 外部变更 | DeepSeek API/model 行为变化 | 模型升级 | 解析/质量漂移 | 固定 model/task version、contract test/PoC | 模型升级时 |
| `RISK-MODEL-005` | 成本/延迟 | 大 payload 或 retry 放大 | 多阶段 Knowledge | 超时/成本 | 预算、零 retry、并发 4 | 不阻塞设计 |
| `RISK-MODEL-006` | context | `ContextVar` 未 reset 或后台 task 泄漏 | 并发/取消 | 请求串扰 | finally reset、并发测试、禁后台续跑 | `CR-GATE-002` |
| `RISK-MODEL-007` | 领域依赖 | Grounding policy 尚由后续 L2 提供 | 启用真实 capability | 无法安全回答 | policy 缺失启动/调用失败关闭 | 对应能力真实模型 |

### 16.2 阶段门禁

| 门禁 ID | 类型 | 控制动作 | 关闭条件 | 状态 | 未关闭允许/禁止 |
|---|---|---|---|---|---|
| `CR-GATE-001` | design_decomposition | 编写本文 | L1_00 已评审 | Closed | 允许文档，不授权代码 |
| `CR-GATE-002` | slice_implementation | 创建模型公共代码与本地 stub 测试 | 本文和依赖 L2 已评审可实施、用户授权 | Open | 允许文档；禁止代码实施 |
| `SA-GATE-002` | slice_implementation | 定版本文并实现/启用真实 DeepSeek | 官方契约核实、30 次 PoC 达标、预算/失败测试、项目维护者确认 | Open | 允许 fake transport；禁止真实 Provider 实现完成声明 |
| `CR-GATE-003` | integration | 敏感用户问题进入 DeepSeek | 问题类别、最小化、业务/知识 fixtures、denied/unknown 零调用均通过 | Open | 只允许非敏感合成问题或本地替身 |
| `SA-GATE-006` | integration | 真实知识证据/业务结果进入 DeepSeek | 领域出域、grounding、未分类/冲突失败关闭、零调用证据 | Open | 只允许合成 safe payload |

### 16.3 需要后续授权

- 创建/修改 `agent-runtime` 模型代码、依赖、配置和测试。
- 使用 `LLM_API_KEY` 执行任何生成/付费 PoC。
- 发送敏感用户问题、真实知识证据或真实业务结果。
- 改用 beta endpoint、其他模型、SDK、代理 URL、自动 retry 或动态 Prompt。
- 关闭任一实施/集成门禁。

## 17. 内部自检记录

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-25 | 0 | 1 | 2 | 3 | PoC/领域 policy 属开放门禁 | 修复非权威 Provider 字段、内聚依据、JSON Output 与路径标记 |
| 2 | 2026-07-25 | 0 | 0 | 0 | 0 | PoC/领域 policy 属开放门禁 | 完整 rubric 复核无目标内材料缺口，进入严格校验 |

作者自检不构成正式批准、真实模型可用证明或门禁关闭。

## 18. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] Provider-neutral 与 DeepSeek-specific 路径、关键函数、输入/输出/失败已明确。
- [x] action selection、answer generation 和 Knowledge task 的所有权不重叠。
- [x] 问题输入、领域 safe payload、凭证和日志均失败关闭。
- [x] timeout、并发、token/byte、retry 和取消边界明确。
- [x] PoC 与真实数据门禁未被 `/models` 核实替代。
- [x] `validate_detailed_design.py --strict` 已通过，结果为 0 errors、0 warnings。
- [ ] 独立评审和 `SA-GATE-002` PoC 已通过。

## 19. 当前结论

本文已经形成 DeepSeek Provider、问题输入闸门、结构化动作工具投影、受控回答/grounding、Knowledge 复用接口、预算/错误/凭证和 PoC 的 Draft 设计，并已通过严格文档校验。官方模型存在性已核实，但独立评审、结构化生成 PoC、目标代码和领域 grounding policy 均未完成，因此本文不能作为真实模型实施或数据出域依据。
