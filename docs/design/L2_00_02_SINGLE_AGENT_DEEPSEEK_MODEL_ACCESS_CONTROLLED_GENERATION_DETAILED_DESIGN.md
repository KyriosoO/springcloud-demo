# [L2_00_02] 单体 Agent DeepSeek 模型接入与受控生成详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent DeepSeek 模型接入与受控生成详细设计 |
| 文档编号 | `L2_00_02` |
| 文档路径 | `docs/design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 五轮独立评审及 Knowledge 消费契约针对性复评通过，`REV-MODEL-001`～`021` 全部关闭 |
| 当前版本 | v0.4 |
| 日期 | 2026-07-25 |
| 适用范围 | DeepSeek Provider、用户问题输入闸门、结构化动作选择、受控回答生成、模型预算/失败/观测 |
| 上位文档 | `REQ_00`、`L0_00`、`L1_00` |
| 直接依赖 | `L2_00_01` v0.4（Approved）的模型节点窄输入/决定、能力描述、公共状态和结果隔离；`L2_00_00` v0.2（Approved）的 Runtime 子截止与取消 |
| 关联文档 | `L1_01`、`L1_02`、`L2_01_00`、`L2_02_00` |
| 外部契约 | DeepSeek OpenAI-compatible `/chat/completions`、`deepseek-v4-pro`、Tool Calls、JSON Output |
| 实现基线 | `LLM_API_KEY` 环境变量存在；目标模型代码不存在；2026-07-25 只读 `/models` 验证返回 `deepseek-v4-pro` |
| 是否可作为实现依据 | 否 |
| 实施依据说明 | 五轮独立评审及 Knowledge 消费契约针对性复评已关闭 `REV-MODEL-001`～`021`；设计批准不等于代码实施、真实 Provider 可用或数据出域批准，`CR-GATE-002`、`SA-GATE-002`、`CR-GATE-003`、`SA-GATE-006` 均保持 Open |
| 当前允许实施范围 | 作为后续实施/测试计划依据；本轮仅获文档原子同步授权，仍只允许契约样例和纯本地 fake transport/模型替身推演 |
| 当前禁止动作 | 创建目标代码/配置/测试；执行付费生成 PoC；发送敏感问题或真实领域数据；关闭任何门禁 |
| 修改权限 | 本轮授权本文及直接相关文档原子同步，并授权 Git 提交、推送；代码、配置、测试和真实模型调用未获实施授权 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 第二批 L2 详细设计 | 创建 DeepSeek 接入、模型输入治理、动作选择、受控回答及实现测试落点 |
| 2 | 2026-07-25 | 7.4、8.2～8.3、12.2、13、17 | 作者第 1 轮自检修复 | 删除官方正式契约未列出的 `parallel_tool_calls` 字段，补充内聚/耦合依据、JSON Output 参数和建议修改路径标记 |
| 3 | 2026-07-25 | 1、2、17～18 | 原子同步 `L2_00_01` v0.4 契约状态 | 更新直接依赖版本/评审状态；模型节点仍只消费 graph wrapper 投影的窄问题输入，不读取 Capability 执行上下文，本文设计规则不变 |
| 4 | 2026-07-25 | 14、18～19 | 本批次收口校验 | 执行严格文档校验并记录 0 errors、0 warnings；状态仍为 Draft，不替代独立评审或真实模型 PoC |
| 5 | 2026-07-25 | 1～16、18～20 | 独立评审第 1 轮修复 | 以运行入口外层装饰器绑定安全模型上下文；增加绝对总截止、流式响应上限和 HTTPX 出域配置；补齐 task/DTO/grounding/JSON 契约、复合敏感分类、完整请求预算、Provider 响应兼容及 action/answer 双路径 PoC 门禁 |
| 6 | 2026-07-25 | 3.4、4、7.5、8.5、13～14、18～20 | 独立评审第 2 轮修复 | 补齐 15 条权威设计规则、Runtime 子截止术语、可配置响应上限、非 200 零正文读取和 answer PoC 独立追踪 |
| 7 | 2026-07-25 | 7.2～7.3、9.1、11～14、18～20 | 独立评审第 3 轮修复 | 增加 Provider-neutral transport 端口与精确响应模型，封装 DeepSeek DTO；明确 Knowledge task 超时继承及 PoC 单 case 下限 |
| 8 | 2026-07-25 | 7.3、10.2、12.1、12.3、13.1、18～20 | 独立评审第 4 轮修复 | 精确化 neutral request/tool/context 字段，统一设置类名和失败映射签名，修正 stub client 生命周期及 readiness 所有权 |
| 9 | 2026-07-25 | 1～20 | 独立评审第 5 轮终审 | 全量复核无新增 S0/S1/S2，关闭 `REV-MODEL-001`～`020`，版本升为 v0.3、状态改为 Approved；所有实施/PoC/真实数据门禁保持 Open |
| 10 | 2026-07-25 | 1、7.3、8.1、13.1、14、18、20 | `L2_01_00` 消费契约针对性补正 | `QuestionEgressDecision` 在 allowed/denied 两类决定中均返回代码绑定策略版本，使 Knowledge 能先显式判定问题出域；不改变 `ModelProviderFailureKind`、Provider、节点决定或门禁 |
| 11 | 2026-07-25 | 1 | 第二批 L2 终审状态原子同步 | 明确五轮评审及针对性复评的统一状态；不改变模型契约、实施/PoC/出域门禁或运行事实 |

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
| `REQ-MODEL-010` | 模型契约可用性有独立 PoC 证据 | 合成非敏感 action/answer 用例达到 14.3 门槛后才可申请关闭 `SA-GATE-002` | `SA-GATE-002` |

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
- Spring→Python 协议、接入硬截止与传给 Python 的 Runtime 子截止；归 `L2_00_00`。
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
| `CON-MODEL-007` | `L2_00_00` 11 | 消费同一请求的 Runtime 子截止剩余预算，不自行恢复接入层预留时间 | `DR-MODEL-010` | 无 |
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
| `REQ-MODEL-010`、`CON-MODEL-010` | PoC/门禁 | `DR-MODEL-013`、`DR-MODEL-014` | live PoC | 合成输入证据 | `IMPL-MODEL-012`、`IMPL-MODEL-017` | `TEST-MODEL-011`、`TEST-MODEL-012` | `VAL-MODEL-005` |

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
          → StructuredModelTransport
              ← DeepSeekChatTransport

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
| `QuestionDataClass` | `public_knowledge/generic_business/personal_identifier/employee_identifier/transaction_identifier/financial_account/contact/credential_or_secret/instruction_injection/free_text_sensitive/unknown`；分类器内部返回非空 `frozenset`，不是单值覆盖 |
| `QuestionEgressDecision` | `disposition: allowed/denied`、两类均必填 `policy_version`；allowed 仅增加 `minimized_question`，denied 仅增加 `reason_code`；互斥；不得携带原问题或分类命中片段 |
| `ModelTaskId` | `action_selection/answer_generation/knowledge_rewrite/knowledge_summary`；有限代码枚举 |
| `ModelCallContext` | `request_id: str`、`correlation_id: str`、`deadline_monotonic: float`；冻结；不含 JWT/subject/role |
| `ModelTaskDefinition[TInput,TOutput]` | `task_id`、`task_version`、`input_type`、`max_input_bytes`、`timeout_ms`、`max_output_tokens`、代码绑定 `build_request/parse_response`；冻结且只由组合根注册 |
| `StructuredToolDefinition` | `name: str`、`description: str`、`arguments_schema: FrozenJsonObject`；冻结、`additionalProperties=false`，不含 Provider tool ID/type/index |
| `StructuredModelRequest` | `task_id: ModelTaskId`、`task_version: str`、`system_instruction: str`、`user_payload_json: str`、`tools: tuple[StructuredToolDefinition,...]`、`tool_mode: none/required`、`output_mode: tool_calls/json_object`、`max_output_tokens: int`；冻结且只能由注册 task factory 构造 |
| `StructuredToolCall` | `name`、`arguments_json`；不含 Provider tool ID/type/index，arguments 尚未做 task schema 校验 |
| `StructuredModelResponse` | `finish_kind: tool_calls/stop`、`content: str \| None`、`tool_calls: tuple[StructuredToolCall,...]`、`usage_total_tokens: int \| None`；均为严格校验后的 Provider-neutral 字段，不含 raw JSON、reasoning content、model 或供应商 DTO |
| `CandidateAnswer` | `answer`、去重 `used_fact_ids`、空 `unsupported_claims`；从严格 JSON Output 解析，不含供应商对象 |
| `GroundingInput` | canonical capability ID、已允许的 minimized question、深冻结 safe payload、`CandidateAnswer` |
| `GroundingDecision` | `accepted: bool`、拒绝时有限 reason enum；不转换答案、不携带原始异常 |

`StructuredModelRequest` 构造器不对任意调用方公开；运行时只通过 `ModelTaskDefinition.build_request` 创建。task definition tuple 在组合根显式绑定并冻结，配置不能增加 Prompt、schema、class 或 endpoint。

### 7.4 内聚与耦合判断

共同传输、凭证、预算和供应商错误聚合在 `StructuredModelGateway`/`DeepSeekChatTransport`，因为它们只因模型提供方或通用调用规则变化；问题分类由输入安全策略拥有，领域 Prompt、safe payload 与事实验证仍由对应能力拥有。`GroundingPolicyRegistry` 只保护“公共回答生成必须取得领域验证器”这一稳定边界，不实现领域字段规则。该分解避免 Provider 依赖业务 DTO，也避免各能力复制 DeepSeek 协议；新增 task 仍需代码和设计，不演化为动态 Prompt 平台。

### 7.5 设计规则目录

| 设计规则 | 权威规则 |
|---|---|
| `DR-MODEL-001` | graph/core/能力只依赖 Provider-neutral 模型端口；DeepSeek/httpx DTO 只能存在于 model/deepseek adapter，模型上下文由不侵入 core 的同签名运行入口装饰器绑定。 |
| `DR-MODEL-002` | DeepSeek transport 固定正式 HTTPS endpoint、`deepseek-v4-pro`、禁用 thinking/stream、严格请求/响应 DTO 与 JSON 兼容边界；调用方不得传入 model、URL、header 或供应商扩展字段。 |
| `DR-MODEL-003` | 用户问题首次外发前必须由有限、版本化、确定性的分类器收集全部类别；任何 deny 命中优先，未明确允许即 unknown 并失败关闭。 |
| `DR-MODEL-004` | denied/unknown 问题、缺失 safe payload 或缺失领域策略时 Provider 调用必须为 0；允许输入只能使用确定性最小化结果，拒绝决定不得保留原文。 |
| `DR-MODEL-005` | 动作选择只能把冻结 `CapabilityDescriptor` 投影为有界 tool 集和调用内 reverse map；配置、模型或请求不得增加动作、URL、类名或任意 DSL。 |
| `DR-MODEL-006` | 模型最多产生一个结构化动作候选，unknown/multiple/invalid tool 一律拒绝；候选参数仍由核心公共边界和能力 validator 重新校验，模型不取得授权或执行权。 |
| `DR-MODEL-007` | task、Prompt、输入/输出 schema 与 grounding policy 必须由代码绑定并在组合根冻结；领域拥有其 Prompt、safe payload 与语义规则，公共层不得演化为动态 Prompt 平台。 |
| `DR-MODEL-008` | 回答生成仅接收已允许问题和领域显式 safe payload；不得接收完整 domain result、JWT、角色、下游地址或授权策略。 |
| `DR-MODEL-009` | 回答候选必须通过严格 JSON 结构、fact ID 子集与 capability 专属 deterministic grounding policy；任何未知字段、未支持主张或验证异常均丢弃全文。 |
| `DR-MODEL-010` | permit、连接池等待、网络、keep-alive、流式读取、解析和校验共享一个不晚于 Runtime 子截止的绝对截止，并受完整请求、响应、token 与并发上限约束。 |
| `DR-MODEL-011` | Provider 传输、HTTP transport 与 wrapper 自动重试均为 0；模型调用不缓存、不重放，未来语义重试只能由 LangGraph 在同一请求预算内显式设计。 |
| `DR-MODEL-012` | `LLM_API_KEY` 只在启动期读取并最小生命周期 reveal；client 禁止环境代理、redirect 和隐式 retry，日志、健康状态、异常及对象表示不得包含 secret 或内容正文。 |
| `DR-MODEL-013` | 官方契约核实、本地替身测试与真实 DeepSeek action/answer PoC 是不同证据；只有经单独授权的合成非敏感 PoC 达到固定门槛，才可申请关闭可行性门禁。 |
| `DR-MODEL-014` | 设计批准不关闭实施、敏感问题或真实领域数据门禁；未分类、策略缺失/冲突和证据不足均失败关闭，任何门禁状态只由其规定证据改变。 |
| `DR-MODEL-015` | 所有 Provider HTTP、transport、parse、finish reason、model 与 grounding 失败必须穷尽映射为有限 failure kind；不得携带响应正文、异常消息、Prompt 或供应商 DTO。 |

## 8. 详细功能与流程设计

### 8.1 问题输入闸门

校验顺序：

1. 必须是已由 `L2_00_01` 限制的非空字符串。
2. Unicode NFC、去首尾空白、连续空白折叠；不删除否定、时间、数字或标点。
3. 在最小化前以有限检测器收集全部命中类别；拒绝 NUL、不可见控制符、疑似
   JWT/API key/private key/password、Prompt/角色覆盖指令，以及个人、员工、交易、金融账户、
   联系方式和自由文本敏感模式。
4. 分类结果是非空集合；任何 deny 类别命中都优先于
   `public_knowledge/generic_business`，不得以后匹配覆盖前命中。没有明确 allow 类别时加入
   `unknown` 并拒绝。
5. 只有分类集合是 `{public_knowledge}`、`{generic_business}` 或二者组合，且
   `generic_business` 满足代码注册的非敏感句式时才允许；任何其他组合均拒绝。
6. allowed 返回最小化问题和策略版本 `question-egress-v1`；denied 返回同一代码绑定策略版本
   和有限 reason code，但不返回问题副本、命中类别或片段。调用方必须先检查 disposition，
   不得因为取得 policy version 而读取不存在的 minimized question。

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

1. HTTP/JSON/finish reason 有效，content 非空且只有一个 JSON object；重复 key、未知顶层字段和类型宽松转换均拒绝。
2. `answer` 1～4096 字符；禁止控制符、工具/URL/角色/策略指令输出。
3. `used_fact_ids` 是 1～256 项的去重字符串数组，单项 1～128 ASCII 字符且全部存在于
   safe payload；`unsupported_claims` 必须是空数组。
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

- 进入响应上下文后先检查 HTTP status；只有精确 200 才允许读取 body。408/504 直接映射
  `provider_timeout`，其余任意非 200 直接映射 `provider_failure`；错误正文不得读取、解析或记录，
  response 必须在退出上下文时关闭。
- HTTP 200 的媒体类型必须为 JSON，body ≤冻结设置 `max_response_bytes`（默认 262144）。
- 使用流式读取并在累计第 `max_response_bytes + 1` 个 raw byte 时立即关闭响应；不得先调用
  `response.aread()/response.json()` 再检查大小。请求固定 `Accept-Encoding: identity`，
  非 identity Content-Encoding 拒绝。
- `choices` 正好 1 项。
- `finish_reason` 只允许 task 预期的 `tool_calls` 或 `stop`；`length/content_filter/insufficient_system_resource/null` 均失败。
- response `model` 当前必须精确为 `deepseek-v4-pro`；任何别名或新值均失败关闭并需变更评审。
- UTF-8 和 JSON 解析严格拒绝重复 key、非有限 number 与顶层非 object。对 Provider
  top-level、`usage` 新增但未消费的字段允许忽略；`object/model/choices/finish_reason/message`
  及实际消费的 tool/content 字段必须严格类型化，未知枚举失败关闭。模型生成的
  `function.arguments` 和 JSON Output 对象始终 `extra=forbid`。
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

class StructuredModelTransport(Protocol):
    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse: ...
```

`ModelTaskResult` 只能是 `success(output)` 或 `failure(ModelProviderFailureKind)`；failure kind 固定为 `input_denied/provider_timeout/provider_failure/invalid_output`。它不携带异常 message、HTTP body、Prompt 或供应商 DTO。

`BoundedStructuredModelGateway` 只依赖 `StructuredModelTransport`。`DeepSeekChatTransport`
在 adapter 内把 `StructuredModelRequest` 投影为私有 `DeepSeekRequest`，完成 canonical
序列化、HTTP 和响应 DTO 校验后，再投影为 `StructuredModelResponse`；公共 gateway、
task definition 和领域代码均不得导入 `model.deepseek.dto`。Provider 响应中的 model、
object、choice index、finish reason 等只用于 adapter 校验，不穿过 transport 端口。

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

二者不接收 `Runtime`、scope、JWT、domain result 或整个 state。请求上下文/截止时间由
模型模块的 `ModelContextBindingRuntimeInvoker` 外层装饰器提供：该装饰器实现
`L2_00_01` 的 `AgentRuntimeInvoker` 公共调用边界，顶层组合根先取得
`L2_00_01` 的原始 `AgentRuntimeInvoker`，再用装饰器包裹；装饰器保持完全相同的
`ainvoke(question, scope)` 签名，只从 `scope.context` 投影
requestId/correlationId/deadline 到 `ModelCallContext`，设置模型模块私有
`ContextVar`，委托原 invoker，并在 `finally` reset。`agent-core`、graph wrapper 和原
`AgentRuntimeInvoker` 不导入 model 包也不作任何修改。

`DeepSeekActionSelector/AnswerGenerator` 只调用只读
`ModelCallContextAccessor.require_current()`；缺失上下文时 transport 调用为 0 并返回
`invalid_output`。child task 只在当前结构化调用栈内创建并必须 join/cancel；不得把
ContextVar 用于图状态、跨请求缓存或领域数据。并发测试必须证明两个请求 context 不串扰，
也必须证明装饰器退出后 accessor 失败关闭。

### 9.3 错误映射

| 触发 | `ModelNodeFailureKind` | 重试 | 安全观测 |
|---|---|---:|---|
| 输入闸门 denied/unknown | `input_denied` | 否 | policy reason enum |
| connect/read/overall timeout、截止耗尽 | `provider_timeout` | 否 | phase + duration |
| HTTP 408/504 或本地绝对截止、任一 HTTPX timeout | `provider_timeout` | 否 | phase + duration |
| 其他任意非 200 HTTP、2xx≠200、3xx、连接重置/DNS/TLS/协议错误 | `provider_failure` | 否 | status/transport class |
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
- 仅 `ModelSettings.from_env` 在启动期读取，包装为 `ModelApiKey`；`repr/str` 固定 `<redacted>`。
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

`knowledge_rewrite` 复用 `AGENT_MODEL_ACTION_TIMEOUT_MS`，`knowledge_summary` 复用
`AGENT_MODEL_ANSWER_TIMEOUT_MS`；Knowledge 的代码绑定 task definition 只能在上述冻结值内
收紧，不能通过领域配置扩大。首期不增加同义超时配置项。

单次调用先冻结：

```text
callDeadline =
  min(nowMonotonic + taskTimeout, requestDeadlineMonotonic - 250ms)
```

`callDeadline <= now` 时不获取 permit、不创建 HTTP 请求并返回 `provider_timeout`。获取
全局并发 permit、连接池等待、连接、写入、DeepSeek keep-alive/推理、流式读取、JSON/输出
校验全部包含在同一个 `asyncio.timeout_at(callDeadline)` 内；不得为各阶段重新获得完整
task timeout。HTTPX connect/pool/read/write timeout 仅作为更小的阶段保护，其中 connect
≤2s、pool≤1s，其余不超过调用剩余量；DeepSeek 返回空行 keep-alive 不能延长绝对截止。

全局模型并发默认 4、允许 1～8；超限不排无界队列，若无法在 `callDeadline` 前获得 permit
则 `provider_timeout`。取得 permit 后任意退出路径均在 `finally` exactly-once 释放；超时或
取消关闭 response stream，迟到 bytes/结果不接纳。

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
| `AGENT_MODEL_MAX_REQUEST_BYTES` | 131072 | 65536～262144 | 重启 |
| `AGENT_MODEL_MAX_RESPONSE_BYTES` | 262144 | 16384～524288 | 重启 |

`stub` 是显式本地测试实现，不得在真实链路伪装成 DeepSeek 成功。stub 模式可以在本地对象图
有效时满足 `L2_00_00` 的 Runtime readiness，但 readiness HTTP 契约不得由本文增加字段；
仅启动日志/指标可报告安全枚举 `modelProvider=stub`，验收不得据此声明真实模型已实现。

### 12.2 依赖

建议新增：在 `agent-runtime/pyproject.toml` 锁定 `httpx==0.28.1`；不得依赖 OpenAI SDK、LangChain model wrapper 或自动 retry 包作为首期 Provider 必需依赖。使用直接 HTTP 是为了明确 request body、timeout、response size 和错误映射，不是建立自研通用 SDK。

### 12.3 组合根

1. 加载并校验 `ModelSettings`。
2. 仅当 provider=`deepseek` 时读取 `LLM_API_KEY` 并创建一个进程级 `httpx.AsyncClient`：
   `base_url=https://api.deepseek.com`、
   `verify=True`、`trust_env=False`、`follow_redirects=False`、`http2=False`，
   `AsyncHTTPTransport(retries=0)`，连接池上限等于模型并发，默认 Header 固定
   `Accept=application/json`、`Accept-Encoding=identity`；stub 模式不读取 key、不创建
   HTTP client 或 DeepSeek transport。
3. 创建 `QuestionEgressGuard`，并按 provider 创建 `DeepSeekChatTransport` 或纯本地 stub。
4. 创建有限 `ModelTaskDefinition` tuple 并冻结。
5. 创建 grounding policy registry；只有当前启用且可能产生 safe payload 的 capability 均有 policy 时才就绪。
6. 将 `DeepSeekActionSelector`、`DeepSeekAnswerGenerator` 注入 `RuntimeCompositionRoot.build`。
7. 用 `ModelContextBindingRuntimeInvoker` 包裹核心 invoker 后交给 HTTP ingress；Runtime
   lifespan 关闭时必须 `await AsyncClient.aclose()`，并在关闭后拒绝新调用。

组合根可以知道具体 Provider，graph/core/领域流程不得知道。

任务表中的“最大输入 bytes”只限制 task 的 canonical JSON 输入，不含 system instruction、
tools 和 Provider envelope。`ModelTaskDefinition.build_request` 后必须对完整
`DeepSeekRequest` 做 canonical UTF-8 序列化并执行
`AGENT_MODEL_MAX_REQUEST_BYTES=131072` 上限；system instruction 单项≤8192 bytes、tools
总量≤65536 bytes。任何静态 prompt/tool 集在启动校验中已使最坏请求超界则不就绪；动态
输入使完整请求超界时 Provider 调用为 0 并返回 `input_denied`。

## 13. 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置 | 责任 | 设计规则 |
|---|---|---|---|---|---|---|
| `IMPL-MODEL-001` | 建议新增 | Python contract | `agent-runtime/src/agent_runtime/model/contracts.py` | enums、decisions、task/gateway/transport/grounding Protocol | Provider-neutral 契约 | `DR-MODEL-001/007/009/015` |
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
| `IMPL-MODEL-015` | 建议新增 | Python request context | `agent-runtime/src/agent_runtime/model/context.py` | private ContextVar、accessor、`ModelContextBindingRuntimeInvoker` | 安全运行元数据绑定且不侵入 core | `DR-MODEL-001/010/012` |
| `IMPL-MODEL-016` | 建议新增 | Python Provider DTO/JSON | `agent-runtime/src/agent_runtime/model/deepseek/dto.py`、`json_codec.py` | request/response typed projection、unique-key JSON、bounded stream | 严格 Provider 边界 | `DR-MODEL-002/009/015` |
| `IMPL-MODEL-017` | 建议新增 | PoC test | `agent-runtime/tests/poc/test_deepseek_answer_generation_live.py` | opt-in synthetic safe-payload cases | `SA-GATE-002` answer 路径证据 | `DR-MODEL-013/014` |

### 13.1 边界关键函数签名

| 路径/符号 | 建议签名 | 输入/校验 | 输出/错误 | 副作用/调用方 |
|---|---|---|---|---|
| `QuestionEgressGuard.evaluate` | `def evaluate(self, question: str) -> QuestionEgressDecision` | NFC、长度、控制符、有限类别；纯函数 | 两类均含策略版本；allowed 含最小问题，denied 含有限 reason；不抛原文异常 | 无；selector/answer/Knowledge task |
| `ModelTaskDefinition.build_request` | `def build_request(self, input: TIn) -> StructuredModelRequest` | `type(input) is input_type`，canonical input bytes≤task 上限；definition 来自冻结 registry | 返回冻结 Provider-neutral request；非法/超界为 typed input denial，不含输入正文 | 纯函数；gateway |
| `ModelTaskDefinition.parse_response` | `def parse_response(self, response: StructuredModelResponse) -> TOut` | 仅接收已通过共同 Provider 校验的 response；task-specific exact schema | 返回冻结 typed output；空/额外字段/越界抛无正文 `InvalidModelOutput` | 纯函数；gateway |
| `BoundedStructuredModelGateway.generate` | `async def generate(self, *, definition: ModelTaskDefinition[TIn,TOut], input: TIn, context: ModelCallContext) -> ModelTaskResult[TOut]` | task 必须来自冻结 registry；预算/permit | typed result；不传播供应商异常 | 获取并发 permit，一次 transport |
| `DeepSeekChatTransport.complete` | `async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse` | request 只能由冻结 task definition 构造；adapter 内投影私有 `DeepSeekRequest` 并校验 canonical body≤完整请求上限；固定 URL/model；deadline 为当前 loop 单调值 | 流式≤响应上限、严格 JSON/type/model 校验后返回 Provider-neutral response；typed transport exception | 一个绝对 timeout 内一次 HTTPS；无 retry；stream 在 finally 关闭 |
| `project_capability_tools` | `def project_capability_tools(descriptors: tuple[CapabilityDescriptor, ...]) -> CapabilityToolProjection` | 非空、≤32、schema 已由 registry 验证 | frozen tools + reverse map；冲突为 internal config error | 纯函数；action selector |
| `DeepSeekActionSelector.__call__` | `async def __call__(self, input: ActionSelectionInput) -> ActionSelectionDecision` | question guard、descriptor/tool 限制 | candidate/unsupported/failure；不写 graph state | 至多一次模型调用 |
| `DeepSeekAnswerGenerator.__call__` | `async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision` | question guard、safe payload、policy、大小 | answer/failure；丢弃未验证全文 | 至多一次模型调用 |
| `GroundingPolicyRegistry.require` | `def require(self, capability_id: str) -> AnswerGroundingPolicy` | canonical ID，registry 冻结 | policy；缺失 `MissingGroundingPolicy` 由 generator 转 invalid_output | 无；answer generator |
| `AnswerGroundingPolicy.validate` | `def validate(self, input: GroundingInput) -> GroundingDecision` | 只读 minimized question、safe payload 和已做共同结构校验的候选；不得访问 Provider/JWT/下游 | accepted 或有限拒绝原因；异常/未知原因失败关闭，不能改写候选答案 | 纯函数；answer generator |
| `ModelContextBindingRuntimeInvoker.ainvoke` | `async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome` | 与 delegate 精确同签名；只投影 request/correlation/deadline | 设置私有 context、await delegate、finally reset；保持 delegate outcome/cancel | 每请求绑定一次；HTTP ingress |
| `ModelCallContextAccessor.require_current` | `def require_current(self) -> ModelCallContext` | 当前 task 必须处于 binding invoker 调用栈 | 返回冻结安全上下文；缺失抛无正文 `MissingModelCallContext` | 只读；两个模型节点/Knowledge task |
| `parse_unique_json_object` | `def parse_unique_json_object(raw: bytes | str, *, max_bytes: int, max_depth: int, max_items: int) -> FrozenJsonObject` | UTF-8、字节、深度、集合、finite number；拒绝重复 key/顶层非 object | 深冻结对象或 `InvalidModelOutput` | 无；Provider/tool/JSON Output parser |
| `map_deepseek_failure` | `def map_deepseek_failure(failure: DeepSeekTransportFailure) -> ModelProviderFailureKind` | `failure` 是 adapter 私有冻结值，仅含有限 category、可空 status/phase；不得含异常对象、message 或 body | timeout/408/504→`provider_timeout`；其他 HTTP/transport→`provider_failure`；parse/schema/model/size→`invalid_output`；未知 category 失败关闭为 `provider_failure` | 纯函数；transport/gateway |
| `ModelSettings.from_env` | `@classmethod def from_env(cls, env: Mapping[str, str]) -> Self` | provider enum、key、预算和常量 | 冻结 settings；非法配置阻止启动 | 只在启动读取 env |

私有 JSON parsing、header 构造和字符串规范化函数可由实现决定，但不得改变上述输入、失败、重试、出域和日志不变量。

### 13.2 Provider DTO 精确边界

`DeepSeekRequest` 由 transport 内部 frozen DTO 表示，字段全集固定为：

| 字段 | 值/类型 | 约束 |
|---|---|---|
| `model` | string | 精确 `deepseek-v4-pro` |
| `messages` | tuple | 正好一条 system 和一条 user；content 非空；user content 是 canonical JSON |
| `thinking` | object | 精确 `{"type":"disabled"}` |
| `stream` | bool | false |
| `temperature` | number | 0 |
| `max_tokens` | int | 来自冻结 task definition |
| `tools` | tuple/null | 仅 action selection；1～33 个有限 function tool |
| `tool_choice` | string/null | tools 存在时精确 `required` |
| `response_format` | object/null | JSON task 精确 `{"type":"json_object"}` |

禁止 `user/user_id`、调用方 model/base URL、proxy、stream options、reasoning effort、
任意 stop、额外 headers 或未列字段。上述 DTO 由 `DeepSeekChatTransport` 从
`StructuredModelRequest` 内部投影，绝不作为 transport 入参或返回类型。`DeepSeekResponse` 只投影
`object/model/choices[0].index/finish_reason/message.content/message.tool_calls/usage.total_tokens`；
`object` 必须为 `chat.completion`、choice index 必须为 0。未消费的安全新增 top-level/usage
字段可忽略但不得进入其他层，所有消费字段按 8.5 严格校验；随后只构造 7.3 的
`StructuredModelResponse`。

## 14. 测试与验证设计

### 14.1 测试定义

| 测试编号 | 设计规则 | 层级 | 建议路径 | 核心断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-MODEL-001` | `DR-MODEL-001/002` | Architecture/Unit | 建议新增：`agent-runtime/tests/architecture/test_model_dependencies.py` | core/graph/能力/公共 gateway 无 DeepSeek/httpx DTO 依赖；transport 端口只收发 neutral DTO | 供应商泄漏 |
| `TEST-MODEL-002` | `DR-MODEL-003` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_input_guard.py` | 每个类别、边界和 NFC 行为确定；两类决定策略版本相同；denied 不保留原文且访问 minimized question 失败 | 敏感样例 allowed、拒绝决定缺策略版本或携带原文 |
| `TEST-MODEL-003` | `DR-MODEL-004` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_zero_call.py` | question denied/unknown 时 transport spy=0 | 先调用后拒绝 |
| `TEST-MODEL-004` | `DR-MODEL-005/006` | Contract | 建议新增：`agent-runtime/tests/contract/model/test_action_selection.py` | tool 映射唯一；单合法 tool→candidate；未知/多 tool/非法 args→invalid | 未注册候选被接纳 |
| `TEST-MODEL-005` | `DR-MODEL-008` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_answer_preconditions.py` | 缺/空/超界 safe payload、缺 policy、question denied 均零调用 | domain result 或拒绝载荷外发 |
| `TEST-MODEL-006` | `DR-MODEL-007/009` | Contract | 建议新增：`agent-runtime/tests/contract/model/test_grounded_answer.py` | fact ID 子集、unsupported 为空、领域 policy 通过才接纳 | 无依据实体/数字被返回 |
| `TEST-MODEL-007` | `DR-MODEL-015` | Unit | 建议新增：`agent-runtime/tests/unit/model/test_deepseek_error_mapping.py` | 全 HTTP/transport/parse/finish reason 到固定 kind；无正文 | 错误映射为 no_result 或泄露 |
| `TEST-MODEL-008` | `DR-MODEL-010/011` | Async Unit | 建议新增：`agent-runtime/tests/unit/model/test_budget_concurrency.py` | 较小 deadline、生效并发、零 retry、取消不接纳晚到结果 | 超预算或多次 HTTP |
| `TEST-MODEL-009` | `DR-MODEL-012` | Unit/Log | 建议新增：`agent-runtime/tests/unit/model/test_credentials.py` | key 缺失启动失败；repr/log/health 无 key | secret 出现在 capture |
| `TEST-MODEL-010` | `DR-MODEL-007` | Contract | 建议新增：`agent-runtime/tests/contract/model/test_code_bound_tasks.py` | 未注册 task/prompt/schema/config class 均不可调用 | 任意 task 被执行 |
| `TEST-MODEL-011` | `DR-MODEL-013/014` | Opt-in PoC | 建议新增：`agent-runtime/tests/poc/test_deepseek_action_selection_live.py` | 仅合成非敏感 descriptors/questions；记录结构与语义指标 | 任一真实/敏感数据进入 PoC |
| `TEST-MODEL-012` | `DR-MODEL-013/014` | Opt-in PoC | 建议新增：`agent-runtime/tests/poc/test_deepseek_answer_generation_live.py` | 3 组合成 safe payload 各 2 次；严格 JSON 与 grounding 结果满足 14.3 | 未验证候选公开或真实数据进入 PoC |

### 14.1.1 共享 Fixture 与动作要求

| 测试组 | Fixture/setup | 执行动作 | 必须断言 |
|---|---|---|---|
| input/zero-call | 含复合 allow+deny、Unicode 变体、凭证、注入指令的表驱动问题；计数 transport | 分别调用 selector、answer、rewrite guard | 任一 deny 命中优先；denied decision 不含原文；transport=0 |
| HTTP/budget | `httpx.MockTransport`/本地 chunked ASGI server、可控 loop clock、阻塞 semaphore、持续空行 keep-alive、边界±1 body | 通过真实 gateway/transport 调用一次 | 同一绝对截止覆盖 permit 和 stream；第 max+1 byte 中止；stream/client/permit 全释放；HTTP 次数≤1 |
| context | 两个并发 scope 使用不同 request/correlation/deadline，另有无 binder 调用和取消路径 | 经 `ModelContextBindingRuntimeInvoker` 进入 selector/answer | 两请求不串扰；退出后 accessor 缺失；取消传播；core invoker 无 model import |
| Provider contract | 固定 request capture；重复 key、未知 enum、额外 model-output 字段、2xx≠200/3xx/任意 4xx/5xx、压缩响应 | 构造 request、流式解析并映射 | request 字段全集/bytes 精确；model 只接受固定值；生成对象 extra 拒绝；Provider 新 top-level 仅忽略；错误无正文 |
| grounding | 代码绑定 policy、含未支持数字/实体/关系/coverage 的候选与 safe payload | `DeepSeekAnswerGenerator` 共同校验后调用 policy | 只有 policy accepted 返回 answer；policy 不得转换文本；拒绝时丢弃全文 |
| secret/lifecycle | sentinel key、代理环境变量、日志 capture、关闭中的 client | 构建/调用/关闭组合根 | `trust_env=False`，无代理请求；key 不出现；只创建一个 client；shutdown aclose 后拒绝调用 |
| live PoC | action 10 个合成问题×3、answer 3 个合成 safe payload×2；两个独立 opt-in 文件 | 在双重授权环境执行 `TEST-MODEL-011/012` | 分别计算结构/语义/grounding 指标；任一真实数据、少执行或失败均不关闭门禁 |

### 14.2 负向场景来源

- Knowledge：否定、时间条件、法律适用范围被改写或回答改变。
- Employee：身份证、电话、账户、员工编号、指令性自由文本。
- Transaction：交易号、账户、金额组合、写入/聚合诱导。
- 通用：JWT/API key、Prompt injection、多 tool、幻觉字段、超界 JSON、空 content、`finish_reason=length`。

`L2_02_00` 负责把业务类别实例化为稳定 fixtures；本文负责这些 fixtures 到 question guard/Provider spy 的共同断言。

### 14.3 结构化动作 PoC 门槛

PoC 仅在用户另行授权真实模型调用后执行：

1. action selection 使用 10 个合成、非敏感、无真实业务/知识数据的问题，每题独立执行 3 次，共 30 次。
2. 结构有效率必须 100%：每次均为一个已映射 tool 或 `agent_unsupported`，且 arguments 可由 JSON/核心边界解析；否则门禁不关闭。
3. 预期动作/unsupported 聚合一致率至少 90%，且每个 case 至少 2/3 次符合预期；任一
   case 低于单项下限或聚合低于门槛都说明当前 Prompt/schema 不足，不能用 retry 掩盖。
4. 所有错误候选均须被 deterministic validator 拒绝，未注册动作、动态 URL/DSL/类名的实际执行次数为 0。
5. 记录模型、时间、Prompt/task 版本、case ID、决定和耗时，不记录完整问题以外的真实数据；case 本身进入版本控制。
6. answer generation 另使用 3 个合成 safe payload（纯字符串、数字/状态、coverage），每个
   独立执行 2 次，共 6 次；JSON 结构有效率必须 100%，全部候选都必须由对应 deterministic
   grounding policy 得到预期接受/拒绝结果，且未支持 claim 的公开返回次数为 0。

该门槛只证明结构化动作可行性，不证明知识/业务效果、权限或真实数据出域。

### 14.4 验证定义

| 验证编号 | 工作目录/前置 | 命令/步骤 | 预期 | 当前状态 |
|---|---|---|---|---|
| `VAL-MODEL-001` | `D:\codex` | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md --root D:\codex --strict` | 0 errors、0 warnings；不替代评审/PoC | 已执行：0 errors、0 warnings（2026-07-25） |
| `VAL-MODEL-002` | 未来 `agent-runtime` | `python -m pytest tests/unit/model -q` | input、transport、预算、失败、secret 测试通过 | 未执行：代码不存在 |
| `VAL-MODEL-003` | 未来 `agent-runtime` | `python -m pytest tests/contract/model tests/architecture/test_model_dependencies.py -q` | 节点/领域/依赖契约通过 | 未执行：代码不存在 |
| `VAL-MODEL-004` | 当前环境/未来实现 | 检查 `LLM_API_KEY` 存在性但不输出值；运行 secret/log tests | 环境存在且无泄露 | 存在性已核实；实现测试未执行 |
| `VAL-MODEL-005` | `CR-GATE-002` 已授权 PoC harness 代码，且另有明确付费调用授权；仅非敏感 case | `RUN_DEEPSEEK_POC=1 python -m pytest tests/poc/test_deepseek_action_selection_live.py tests/poc/test_deepseek_answer_generation_live.py -q` | 满足 14.3 action 30 次 + answer 6 次全部门槛 | 未执行：本轮未获真实生成调用授权 |

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
| `SA-GATE-002` | slice_implementation | 将真实 DeepSeek transport 接入 Runtime 组合根、设为 provider 并声明真实模型切片完成 | 官方契约核实、14.3 的 30 次 action + 6 次 answer PoC 达标、预算/失败/secret 测试、项目维护者确认 | Open | `CR-GATE-002` 与单独付费调用授权后，允许实现/运行 opt-in 隔离 PoC harness；禁止接入 Runtime、默认启用或完成声明 |
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

## 18. 独立正式评审记录

### 18.1 第 1 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-001` | S1 | 文档让已批准核心 `AgentRuntimeInvoker` 直接设置 model ContextVar，却未在核心契约中定义，形成隐式侵入 | 改为 model 包外层同签名装饰器，核心/graph 不导入 model | Closed（第 2 轮） |
| `REV-MODEL-002` | S1 | HTTPX read timeout 是“等待下一块”超时，DeepSeek keep-alive 可持续重置；响应上限也未保证在聚合前执行 | 增加单一 `asyncio.timeout_at`、流式 raw byte 上限和所有退出路径关闭 | Closed（第 2 轮） |
| `REV-MODEL-003` | S1 | HTTPX 默认信任代理/证书环境且 client 关闭责任未固化，外部模型出域路径可被环境扩大 | 固定 `trust_env=False`、verify、无 redirect/HTTP2、retries=0、identity encoding 和 lifespan aclose | Closed（第 2 轮） |
| `REV-MODEL-004` | S1 | task definition、Provider DTO、JSON parser 和 grounding policy 缺少输入输出签名，无法直接实现或做跨模块契约测试 | 补齐公共类型、边界函数、Provider DTO 字段全集与直接消费者 | Closed（第 2 轮） |
| `REV-MODEL-005` | S1 | 单值问题分类未定义复合 allow+deny 优先级，后匹配可能覆盖敏感命中 | 改为类别集合且任一 deny 优先，加入 instruction injection 和复合 fixtures | Closed（第 2 轮） |
| `REV-MODEL-006` | S1 | task input、tools 与完整 HTTP request 共用 65536 表述，无法证明最终请求有界 | 分离 canonical task input、prompt/tools 和 131072-byte 完整 request 上限 | Closed（第 2 轮） |
| `REV-MODEL-007` | S1 | Provider 非 200、model allowlist、重复 JSON key、未知字段兼容策略和模型输出 extra 语义未闭合 | 固定 catch-all 状态、精确 model、unique-key JSON、Provider 新增字段与生成对象不同兼容规则 | Closed（第 2 轮） |
| `REV-MODEL-008` | S1 | `SA-GATE-002` 一边禁止真实 Provider 实现、一边要求用它做 PoC，且 PoC 仅覆盖 action、不覆盖 JSON answer | 允许经双重授权的隔离 harness，禁止 Runtime wiring；门槛增加 6 次合成 answer PoC | Closed（第 2 轮） |
| `REV-MODEL-009` | S2 | 测试表只有断言，缺少关键 fake、时钟、并发和执行动作，不能证明负向测试不会假阳性 | 增加共享 fixture/setup/action/资源释放矩阵 | Closed（第 2 轮） |

首轮修复不构成评审通过，不关闭任何实施、PoC 或真实数据门禁，也未使用
`LLM_API_KEY` 发起生成调用。

### 18.2 第 2 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-010` | S1 | `DR-MODEL-001`～`015` 只被追踪表引用却没有权威规则定义，实施者无法判断散落正文与规则 ID 的确定关系 | 增加 7.5 设计规则目录，并保持每条规则到 IMPL/TEST/VAL 的既有追踪 | Closed（第 3 轮） |
| `REV-MODEL-011` | S1 | answer PoC 已成为 `SA-GATE-002` 关闭条件，但实现/测试追踪仍只列 action 文件，可能在缺少 answer 证据时误关门禁 | 增加 `IMPL-MODEL-017`、`TEST-MODEL-012`，同步 REQ 追踪、fixture 与验证命令 | Closed（第 3 轮） |
| `REV-MODEL-012` | S1 | 配置允许调整 response bytes，但响应流程硬编码 262144/262145，配置改变后会出现两个权威上限 | 统一引用冻结 `max_response_bytes`，保留 262144 仅作为默认值 | Closed（第 3 轮） |
| `REV-MODEL-013` | S2 | 本文仍把模型预算称为“同一硬截止”，与 `L2_00_00` 已批准的接入硬截止/Runtime 子截止二级预算不一致 | 改为消费 Runtime 子截止且不得恢复接入预留 | Closed（第 3 轮） |
| `REV-MODEL-014` | S1 | 非 200 响应虽有失败映射，却未规定错误正文是否读取，可能绕过 body 上限并把外部正文带入解析/日志 | 固化先判 status、非 200 零正文读取并关闭 response | Closed（第 3 轮） |

第二轮修复仍不构成评审通过，也不授权目标代码、真实 Provider wiring 或任何生成调用。

### 18.3 第 3 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-015` | S1 | 公共 task 构造 `StructuredModelRequest`，但 transport 签名收发 `DeepSeekRequest/Response`，会迫使公共 gateway 依赖供应商 DTO，与 Provider-neutral 目标冲突 | 增加 `StructuredModelTransport`，只收发 neutral DTO；DeepSeek adapter 内部完成双向投影 | Closed（第 4 轮） |
| `REV-MODEL-016` | S2 | `knowledge_rewrite/summary` 有默认超时但配置只列 action/answer，实施者可能自创两套配置或使用无界默认 | 明确分别复用 action/answer timeout，领域只能代码级收紧且本期不新增配置 | Closed（第 4 轮） |
| `REV-MODEL-017` | S2 | action PoC 只有 90% 聚合门槛，一个 case 持续误选仍可能整体达标 | 增加每 case 至少 2/3 符合预期的下限 | Closed（第 4 轮） |

第三轮修复仍不关闭实施、PoC 或真实数据门禁；下一轮须重新检查全部规则和跨边界契约，
不能只验证本轮三处文本存在。

### 18.4 第 4 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-018` | S1 | neutral request/tool 仍只有概念字段，没有精确类型与有限模式，两个 adapter 可产生不兼容结构 | 固化 `StructuredToolDefinition`、`StructuredModelRequest`、context 的字段类型和有限枚举 | Closed（第 5 轮） |
| `REV-MODEL-019` | S2 | 凭证章节使用不存在的 `DeepSeekSettings`，且 `map_deepseek_failure` 落点没有边界签名 | 统一为 `ModelSettings`，增加有限私有 failure 入参与穷尽返回签名 | Closed（第 5 轮） |
| `REV-MODEL-020` | S2 | 组合根步骤让 stub 也创建 DeepSeek client，且 readiness detail 试图增加 `L2_00_00` 所有的 HTTP 契约字段 | stub 不读取 key/不创建 client；readiness 只复用既有语义，安全枚举移至日志/指标 | Closed（第 5 轮） |

第四轮修复仍为待复评状态；不以字段补齐或严格校验结果提前判定通过。

### 18.5 第 5 轮终审结论

第 5 轮从上位约束、职责/依赖、neutral/DeepSeek DTO、输入与证据出域、绝对截止、
失败映射、配置生命周期、实现签名、负向测试和门禁证据重新全量检查；未发现新的
S0/S1/S2，`REV-MODEL-001`～`020` 全部关闭。评审结论为 Approved/设计已具备实施就绪
条件，但在 `CR-GATE-002` 关闭前不构成当前实施依据；这不证明真实 DeepSeek 生成、
Tool Calls/JSON Output 质量或真实领域数据出域已经通过。

### 18.6 Knowledge 消费契约针对性复评

`L2_01_00` 首轮评审发现 Knowledge 不能把 gateway 的通用 `input_denied` 等同于“问题出域
拒绝”，因为完整模型请求超界也使用该 failure kind。冻结发现 `REV-MODEL-021`（S1）后，
本文采用最小修复：不扩大 `ModelTaskResult`，只让既有 `QuestionEgressDecision` 的 denied
分支也携带安全策略版本；Knowledge 在调用 gateway 前显式使用同一个 guard，从而只有
guard denied 才设置 `question_egress_denied`，后续 gateway input denial 仍按任务输入失败
处理。针对性复评确认 selector/answer 既有行为、Provider DTO、failure kind 和全部门禁均
未变化，`REV-MODEL-021` Closed；本文保持 Approved。

## 19. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] Provider-neutral 与 DeepSeek-specific 路径、关键函数、输入/输出/失败已明确。
- [x] action selection、answer generation 和 Knowledge task 的所有权不重叠。
- [x] 问题输入、领域 safe payload、凭证和日志均失败关闭。
- [x] timeout、并发、token/byte、retry 和取消边界明确。
- [x] PoC 与真实数据门禁未被 `/models` 核实替代。
- [x] `validate_detailed_design.py --strict` 已通过，结果为 0 errors、0 warnings。
- [x] 独立评审已关闭全部 S0/S1/S2。
- [ ] `SA-GATE-002` PoC 已在单独授权下通过。

## 20. 当前结论

本文 v0.4 已完成五轮独立评审及一次 Knowledge 消费契约针对性复评并 Approved，设计已具备实施就绪条件；由于
`CR-GATE-002` 仍为 Open 且本轮没有目标代码/测试实施授权，当前仍不可作为实施依据。
官方契约核实与本地严格校验不替代付费 PoC、代码实施或真实数据出域证据；当前不得接入
或启用真实 DeepSeek，也不得关闭 `SA-GATE-002`、`CR-GATE-003` 或 `SA-GATE-006`。
