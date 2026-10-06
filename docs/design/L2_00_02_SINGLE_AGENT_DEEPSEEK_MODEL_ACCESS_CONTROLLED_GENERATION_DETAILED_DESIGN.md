# [L2_00_02] 单体 Agent 模型接入与 Business filters QueryPlan 详细设计

> 文档状态：Approved（仅步骤一职责收敛定向复评；实施、部署与UAT证明范围不扩大）

## 1. 文档信息与依据

| 项目 | 内容 |
|---|---|
| 当前版本 | v3.5 |
| 日期 | 2026-10-06 |
| 上位约束来源 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v3.3 |
| 关联责任边界 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md)；[`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) |
| Provider 基线 | 已有 DeepSeek transport、input guard 与已实施并由生产组合根绑定的 `business-query-plan-v7`；默认 provider 仍为 stub，v4～v6仅用于历史追溯，不构成当前装配要求 |
| 归档来源 | [整理前 v2.9 原文](历史文档/2026-09-14-unified-v3-baseline/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |


本文件纳入新的统一文档版本序列；v3.0不是软件、API、模型任务、配置或索引版本。原版本及字节归档见上表。评审状态、实施状态、部署状态和UAT状态分别判断；历史通过不自动覆盖新合同。

修订历史：[既往修订与评审过程](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-13)。本文只定义现行职责和合同；实施、部署及验收分别依据当前计划和原始证据，文档整理不继承历史通过结论。

## 2. 设计目标、范围外与当前实现基线

目标是生成一个 provider-neutral JSON 对象，由 Business 下游解码 filters QueryPlan。Model 层负责 minimized question、安全 catalog、受保护 slot 引用、Prompt、provider framing decoder、timeout/cancel 和 secret 安全；不负责业务字段合法性、Business DTO 映射、业务最终授权或业务调用。

范围外：除§6.1既有协议、§6.2 Knowledge任务和§6.3独立选择器任务外修改Knowledge/answer task、将 SQL/ES/endpoint 暴露给模型、新增模型平台依赖、模型失败回退或修改现有公共 Core/HTTP 合同。当前 `business-query-plan-v7` 已实施；它在 v6 裸 slot 合同上只强化显式字段完整性，不改变 Business decoder、validator、binder 或业务接口。具体运行批次、调用计数和证据哈希由 UAT_00/evidence 管理。

| 需求编号 | 需求 |
|---|---|
| `REQ-MODEL-101` | 安全三动作 catalog 与 filters JSON 一次规划 |
| `REQ-MODEL-102` | Provider framing decoder 与 Business payload decoder 分离 |
| `REQ-MODEL-103` | 敏感值保护、unsupported 完整意图和模型失败零下游调用 |
| `REQ-MODEL-104` | 当前任务必须从安全目录理解精确任一、前缀任一、包含任一和批准的同字段 AND；不得依赖本地句式规则，且不得替换或丢弃显式未开放字段 |
| `REQ-MODEL-107` | 按安全目录职责选Capability，不以模型常识预判资料存在性；详细行为及兼容范围见§6.3 |

| 约束编号 | 上位约束 |
|---|---|
| `CON-MODEL-101` | Model 不拥有 Business 字段验证、角色授权、数据库/ES 或结果投影 |

## 3. 模块职责设计、依赖方向与接口契约

现有 provider-neutral `BusinessQueryPlanGenerator.generate(...)` 返回 `JsonObject`；复用现有 ModelContext、DeepSeek transport 与 client 生命周期。当前生产组合根只绑定独立 `business_query_plan_v7.py`；既有 v4～v6 模块及更早 source、manifest 和 evidence 保持 Git 可追溯及字节不可变。

provider response decoder 仅执行单 JSON object、重复键、额外文本、字节数、深度、集合上限和有限数字校验。它不解析 Business field/operator；`JsonObject → BusinessQueryPlan` 的 exact 三字段、filters 与业务语义由 `L2_02_00` 拥有。依赖方向固定 `Model task → provider transport` 和 `Graph → provider-neutral Model Port`，禁止反向依赖 Business Adapter 或 Core handler。完整意图示例归属 Model Prompt，保持模型规划职责内聚，不在 Business/Core 新增自然语言解析耦合。

关键已存在接口及目标变更：

```python
BusinessQueryPlanTaskInput(minimized_question: str, catalog: JsonObject, catalog_snapshot_id: str)
build_business_query_plan_task_definition(*, timeout_ms: int, ...) -> ModelTaskDefinition[BusinessQueryPlanTaskInput, JsonObject]
async BusinessQueryPlanGenerator.generate(input: BusinessQueryPlanTaskInput, *, context: ModelCallContext) -> JsonObject
decode_business_query_plan_output(response: StructuredModelResponse, *, max_output_bytes: int, max_json_depth: int, max_collection_items: int) -> JsonObject
```

现有 provider-neutral generator、task input 和 strict framing decoder 保持不变；当前生产使用独立v7 Prompt和更丰富但仍安全的目录；旧v5/v6仅按其冻结合同追溯，不新增 Provider 私有类型、额外本地语义解析或公共合同。

## 4. 模型安全 catalog 与受控输入

目录只包含 enabled `employee.search`、`employee.semantic_search`、`transaction.search`，逻辑字段、模型安全说明、operator 语义、cardinality、允许 tagged forms、字段组合、已批准的日期时区和不可变 snapshot ID。模型不得看到 Java DTO 名称、endpoint、HTTP method、SQL、ES DSL、索引、向量字段/provider、embedding 参数、JWT、角色、详细地址、身份证、姓名、电话、邮箱、业务响应或 `workBaseSi/workBaseAf` 字段。

行政区名称和有限别名可以作为非敏感 literal 进入模型，并在计划后由 code-bound 目录规范化；详细地址及其他个人字段只允许 request-local slot。Business 问题先由 protected input extractor 生成 slot，再由 Model input guard 核实 minimized question；guard 不选择 domain/action/operator、不补参数、不创建第二链路。

## 5. Prompt、输出合同与核心处理流程

Prompt 必须明确：

1. 一次只输出一个 exact `{domain,action,arguments}` JSON object。
2. 条件搜索 arguments 使用 filters/page/size/sorts，每个 filter 都必须满足目录中逻辑 field/operator/value tagged union；标量使用 `literal/value_ref`，多值使用 literal list 或 `value_refs`，敏感值只能引用当前请求 slot。
3. Transaction `gt + lt` 可以组合；不得吞掉用户条件、把逻辑 operator 编码进 field、发明字段或使用物理信息。
4. Employee 单姓、多姓、完整姓名、姓氏+姓名片段和单/多行政区必须分别选择 `prefix`、`prefix_any`、`in`、批准的同字段 AND、`contains/contains_any`；不得以逐句模板或错误 `in` 近似。职位对应 position；workBase 永远不可用。
5. Employee semantic 只接受语义文本。对“按语义搜索金融风控经验并限定上海员工”必须给出 exact `{"domain":"employee","action":"unsupported","arguments":{}}` 的显式反例；即使 search 和 semantic 两个 action 都启用，也不得选择其中一个后省略另一类限定，业务调用必须为 0。
6. 限定 domain 的不支持请求返回该 domain + unsupported；无可识别 domain 时返回 `domain=unsupported/action=unsupported/arguments={}`。
7. 对“查询今天发生的交易”，只要没有已批准的 request-local 日期/时钟上下文，即使 `trans_date` 已启用，也必须返回 exact `{"domain":"transaction","action":"unsupported","arguments":{}}`；不得猜测绝对日期或省略日期条件。
8. 用户显式提出的属性/字段名是不可丢弃约束；若 catalog 中不存在对应逻辑字段，必须返回明确 domain + `unsupported` + 空 arguments。不得把未知字段替换成最相近字段、静默省略或把其值复用于其他字段；camelCase/snake_case 形式也按显式字段处理，除非 catalog 明确声明对应逻辑字段。

QueryPlan 模型只规划，不执行 answer task；结果再次发送模型必须由独立 Business egress 策略授权，不是列表查询默认步骤。

### 5.1 Business QueryPlan v7 目录与 Prompt

目录对每个 operator 提供逻辑语义、`scalar/multi` cardinality、1～16 上限及允许的 `literal/value_ref/value_refs` tagged forms，并对每个字段提供允许组合。Prompt 负责理解问句、祈使句、姓氏/姓名/地区、多值和 AND/OR；输入安全层只把敏感值替换为 `protected-ref(slot-N)`，保留词序与连接词。v7 继承 v6 的裸 `slot-N` 合同：单值为 `{"value_ref":"slot-1"}`，多值为 `{"value_refs":["slot-1","slot-2"]}`；禁止 wrapper、遗漏语义相关 slot、重复 slot 或凭空生成 slot。v7 进一步规定显式字段是绑定条件，未在 catalog 中出现时只能 `unsupported`，不得替换、丢弃或近似执行。模型不得复述 slot 真值，不能用 `in` 代替 `prefix_any/contains_any`，也不能在任一条件不可表达时生成部分计划。

不含“员工”但经输入层识别出受保护姓名/姓氏强提示的请求可以进入同一 Business planning；这只是受控候选准入，domain/action 仍由模型决定，非法或不确定计划按 existing unsupported/invalid plan 失败关闭。v4～v6 必须独立版本化，冻结证据不修改。

## 6. Transport、失败类型与事务边界

复用现有 DeepSeek HTTP transport、超时、取消、client lifecycle 和 `LLM_API_KEY` 环境注入；默认 provider 必须继续为 stub。non-live 仅使用 fake transport，不读取密钥；原Business真实调用按历史P3_00绑定追溯，维护回归由UAT_00记录；新Knowledge调用按P3_01/UAT_02另行授权。

模型失败/timeout、非法 framing、输入拒绝或取消固定映射为 `unavailable/timeout/invalid_argument`，业务下游调用为 0，不 retry、fallback、选择 Knowledge 或第二 domain。JWT/slot/model response 不持久化；数据生命周期只在单请求内，事务边界与一致性归业务服务。

### 6.1 固定模型与只承载输出的严格Schema协议

`REQ-MODEL-105` / `DR-MODEL-110`：当前DeepSeek请求统一使用代码绑定的`deepseek-flash`；默认stub不变。不开放用户、模型或环境任意指定model/URL。响应identity仍严格核对当前model；旧任务源文件和历史运行model快照不改写。此变更影响所有当前DeepSeek任务的模型后端，不改变Business、selection、Summary的任务合同；旧成功效果不能冒充新后端实测。

`REQ-MODEL-106` / `DR-MODEL-111`：Model内部新增`StructuredToolMode.SCHEMA_ONLY`，仅接受一个固定输出定义和TOOL_CALLS模式。它只承载JSON参数，不是可执行Capability、函数分发或工具循环。Provider在相同受控origin上为此模式固定POST `/beta/chat/completions`，function带`strict=true`，`tool_choice`固定唯一name，`thinking=disabled`、stream=false；其他模式仍用`/chat/completions`且不改变旧投影。任务不接触provider URL或strict私有参数，不增加模型请求。

Schema使用当前Core已支持且provider严格模式可表达的object/array/string/enum子集；每层object必须`additionalProperties=false`且全部properties列入required。长度、数组数量、顺序、条件关联及语义仍由本地原validator校验，不因provider不支持minLength/maxLength/minItems/maxItems而放宽。只承载输出模式在HTTP前拒绝不支持的Schema关键字，不静默删除约束；不得扩充公共Core Schema。

Knowledge新任务负责唯一name、单调用、无混合正文及arguments严格解码；字段缺失/重复/未知、无调用/多调用、错误name、截断、语义非法均失败关闭。不得补字段、清洗模型响应、重试、降级为普通JSON模式或执行输出函数。原始响应/arguments仍只在请求内，不写日志、evidence或观测；观测复用现有安全请求投影。

`IMPL-MODEL-109`：`agent-runtime/src/agent_runtime/model/settings.py`、`agent-runtime/src/agent_runtime/model/contracts.py`、`agent-runtime/src/agent_runtime/model/deepseek/dto.py`及`agent-runtime/src/agent_runtime/model/deepseek/transport.py`；现行调用方按L2_01_00 §6源码基线解释；目标§8意图12复用该Model合同。`TEST-MODEL-109` / `VAL-MODEL-103`：固定model/两条固定path/strict/named choice/disabled thinking的MockTransport测试、不支持Schema的HTTP零调用、旧模式回归及严格类型检查。`REQ-MODEL-105/106 → DR-MODEL-110/111 → IMPL-MODEL-109 → TEST-MODEL-109 → VAL-MODEL-103`。

依据2026-09-11核实的[官方首次调用](https://api-docs.deepseek.com/zh-cn/)、[Tool Calls严格模式](https://api-docs.deepseek.com/zh-cn/guides/tool_calls)及[Chat Completions API](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion)：JSON mode不等于Schema约束，strict是Beta，固定tool_choice不支持thinking enabled。官方未来模型路由调整不得用于解释此前失败。本增量已按先设计复评、后编码的顺序实施；原non-live验证及状态归历史P3_00，不宣称真实生成可靠性已通过。

### 6.2 Knowledge最小任务设计的Model边界（当前仓库意图12/Summary9；旧Summary8仅作历史追溯）

当前§6.1共享固定后端、SCHEMA_ONLY信封、严格JSON子集及一次输出校验保持不变；该Summary9增量不切换deepseek-flash、不扩大Provider协议、不改变Business v7和action selector。§6.3单独定义后来授权的选择器增量。当前Knowledge任务只消费既有Model能力，不需要修改Core任务ID枚举或公开DTO。

- 意图任务注册键knowledge_rewrite/version12，固定输出名knowledge_query_intent：精确四字段、三类查询模式及一次选域，详细权威L2_01_00 §8。不输出改写文本或证明清单。
- 仓库当前Summary注册键knowledge_summary/version9、固定输出名knowledge_cited_answer，严格两分支及每点`evidence_ref/quote/claim`，详细权威L2_01_02 §9。旧version8的knowledge_extractive_answer及历史输入输出不改；当前原文/ref/引用validator先于有界claim检查，不能把模型claim当可信引用或原文。
- 输入大小、输出tokens和阶段deadline分别由两份L2定义；最多selector+意图+摘要3次模型HTTP。schema枚举/required/additionalProperties和本地数量/跨字段校验同时保留；没有模型失败修复、重试或第二执行工具。
- 新task独立构造Prompt和decoder，禁用多代字符串替换继承；当前仓库版本12/9与minimal-v1在同一唯一组合根注册，旧11/7/8文件及冻结测试不改写。受影响实现/测试义务为L2_01_02的IMPL-KEV-204、TEST-KEV-204及VAL-KEV-204；组件与Spring合成non-live已有证据，真实语义质量仍待评价。不新增模型HTTP阶段或第二动作。

任务Schema必须能由当前Model支持子集表示，错配在outbound前拒绝；新增模型后端或协议不属于本设计。设计及计划状态不能替代单独的运行授权。

### 6.3 按能力职责选择的新任务（action-selection-v5，仓库non-live已实施）

`REQ-MODEL-107` / `DR-MODEL-112`来源于L1_00 §4.1 / CR-AD-006：选择器按安全目录和用户请求操作选择一个Capability，不依据模型常识预判文件存在性、政策真实性、时效或当前语料覆盖。目录内的资料查找、原文解释和适用性询问可以进入Knowledge；这不承诺有资料或可回答。所需条件、检索命中、证据充分性及受控结果由Knowledge处理。写操作、目录外任务及不可表达意图仍exact unsupported。

1. 独立构造v5英文Prompt，不用对v4 Prompt的字符串替换继承。固定输入仍只有安全capabilities/question；输出仍唯一`{"capability_id":"目录中ID"}`，严格重复键、额外字段、深度/大小和目录成员检查，tool mode NONE、JSON_OBJECT，禁止答案、领域/检索条件、物理字段、工具、事实修正或额外解释。不得为某个题号、文档、年份或关键词编写本地路由。
2. 复用共享输入冻结、request构造及response framing校验；v5使用独立build_request包装，同时将definition和生成request的task_version固定为v5，不能仅替换捕获v4闭包的外层definition。不改v4源文件/常量/既有调用方。预算沿用timeout、max_input_bytes=65536、max_output_tokens=512，选择阶段仍一次调用，不增加重试或模型阶段。
3. 当前main.py仅在Knowledge enabled时明确传入v5任务定义。LocalModelCompositionRoot.build新增私有可选action_selection_definition参数（类型`ModelTaskDefinition[ActionSelectionTaskInput, str] | None`），默认None沿用v4；显式定义必须为ACTION_SELECTION和既有输入类型，错配在创建Provider/HTTP资源前启动失败。Business v7与disabled兼容路径不变，不新增环境任务版本开关。
4. 输入保护仍先于模型；拒绝输入模型0。目录无成员/非法输出/unsupported/超时/取消仍按既有typed错误终止，下游0；不得在unsupported后本地改选、重试、扩域或切换Capability。复用无状态任务和请求级上下文，取消与客户端关闭所有权不变。
5. 验证辅助工具须严格冻结实际任务及Prompt身份；固定资产路径，错配在outbound前拒绝。它不是生产任务装配的第二入口，也不要求新批次兼容旧manifest。细节见[动作选择验证辅助工具冻结规则](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-23)；运行批准由当前验收计划及独立授权控制。
6. 回滚恢复相容的选择任务、组合根和验证绑定；仅回退Prompt不能复用旧授权。non-live只证明合同、选路和零调用不变量，不证明真实语义质量。旧案例及结论见[选择器旧案例与回滚记录](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-24)。

`IMPL-MODEL-110`：当前使用`model/deepseek/action_selector_v5.py`的`build_action_selection_v5_task_definition(...)`（同步纯构造，返回上述task definition，无I/O）；`bootstrap.py:LocalModelCompositionRoot.build`与`main.py:build_runtime`作显式绑定；验证辅助工具只承担§6.3第5项的精确冻结，不是Model生产职责。直接消费者为generic DeepSeekCapabilitySelector，decoder/guard/gateway不改。

`TEST-MODEL-110`：现有`tests/contract/model/test_action_selection_v5.py`覆盖独立Prompt、安全输入、exact输出、任务错配启动零资源、disabled默认v4调用路径；当前`tests/integration/knowledge/test_minimal_current_root.py`覆盖enabled绑定、lookup不存在资料的fake no_result、unsupported/非法输出/模型超时零检索及无fallback；MEASURE fake工具测试检查版本与资产绑定。`VAL-MODEL-104`：执行上述定向测试、现有model/Knowledge/Core/Business相关non-live回归、strict mypy、compileall；不运行真实模型、ES/BGE或服务。

追踪：`REQ-MODEL-107 → DR-MODEL-112 → IMPL-MODEL-110 → TEST-MODEL-110 → VAL-MODEL-104`。本增量不修改接口/DTO字段、读取授权、出域策略、gold或历史任务；其non-live实施不关闭MEASURE/COMPARE/RELEASE质量前置。

## 7. 实现落点清单

下表只列现行实现。历史`IMPL-MODEL-106`不复用，定义见[历史Business v5实现编号](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-25)。

| 实现编号 | 已验证位置 | 目标变更 |
|---|---|---|
| `IMPL-MODEL-101` | `agent-runtime/src/agent_runtime/model/deepseek/business_query_plan.py` | 共享 generator、provider framing decoder 与历史 v4 基线；当前 Prompt 位于独立版本文件 |
| `IMPL-MODEL-102` | `agent-runtime/src/agent_runtime/business/planner_catalog.py` | 由 Business 提供安全三动作 field/operator 目录；模型只消费 |
| `IMPL-MODEL-103` | `agent-runtime/src/agent_runtime/model/input_guard.py` | 安全地点片段、slot、Business 锚点与 prohibited 字段回归 |
| `IMPL-MODEL-104` | `agent-runtime/src/agent_runtime/model/contracts.py` | 保留 generator `JsonObject` 边界，仅扩展必要 task 输入 |
| `IMPL-MODEL-105` | `agent-runtime/src/agent_runtime/bootstrap.py` | 保持现有 provider-neutral generator/lifecycle 装配，不新增本地语义分支 |
| `IMPL-MODEL-107` | `agent-runtime/src/agent_runtime/business/planner_catalog.py` | 输出 operator 语义、cardinality、tagged forms、数量和字段组合，不泄漏物理字段 |
| `IMPL-MODEL-108` | `agent-runtime/src/agent_runtime/model/deepseek/business_query_plan_v7.py` | v7显式字段完整性Prompt；未知显式字段exact unsupported；旧v6只保留冻结追溯 |
| `IMPL-MODEL-110` | bootstrap.py/main.py、action_selector_v5.py及当前MEASURE工具 | §6.3显式任务注入、独立Prompt及未来严格冻结已实施，定向non-live与独立代码复评通过；部署和真实质量未验证 |

## 8. 测试与验证设计

| 测试编号 | 核心场景 |
|---|---|
| `TEST-MODEL-101` | 三动作安全目录、operator、workBase/物理信息/敏感字段为 0 |
| `TEST-MODEL-102` | 现行v7 Prompt：上海地址、职位、amount/date 范围；semantic+地点过滤和缺少批准时钟的相对日期必须 exact unsupported/零调用 |
| `TEST-MODEL-103` | duplicate key、非 JSON、深度/大小/float 非法，provider decoder 边界明确 |
| `TEST-MODEL-104` | slot、详细地址/姓名/标识零出域，失败/取消/unsupported 业务零调用 |
| `TEST-MODEL-105` | Knowledge/answer 现有任务、默认 stub、client close 和并发隔离回归 |
| `TEST-MODEL-106` | 单/复姓、多姓名、多姓氏、同字段 AND、单/多地区及句式变化的 现行v7 fake Prompt/catalog 合同 |
| `TEST-MODEL-107` | `value_refs` 重复/跨请求/超限、非法 value shape、模型错误/超时均零 Employee 调用 |
| `TEST-MODEL-108` | 显式未开放字段不得替换为相近字段；exact unsupported 或 strict invalid plan 均必须业务零调用 |
| `TEST-MODEL-110` | §6.3现行v5及disabled默认v4、错配启动零资源、当前入口及失败零检索；fake不证明真实语义改善 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-MODEL-101` | fake transport catalog/Prompt/framing contract tests |
| `VAL-MODEL-102` | Business/Core/Knowledge 非 live 回归、strict mypy、compileall |
| `VAL-MODEL-104` | §6.3定向contract/current-root/MEASURE fake测试及相关non-live回归、strict mypy、compileall |

## 9. 设计规则、权限与审计设计

| 规则编号 | 设计规则 |
|---|---|
| `DR-MODEL-101` | 当前生产 task 必须是 code-bound `business-query-plan-v7` 并只生成逻辑 filters QueryPlan；v4～v6 及更早 source、manifest 与证据只作不可变历史 |
| `DR-MODEL-102` | provider framing decoder 和 Business payload decoder 分层，不互相替代 |
| `DR-MODEL-103` | 安全目录只包含三动作及已启用逻辑 field/operator，protected slot 不含真实值 |
| `DR-MODEL-104` | 完整意图不可表达时 exact unsupported；semantic+结构过滤与无批准时钟的相对日期必须通过显式 Prompt 反例失败关闭，禁止近似、丢条件和任何 fallback |
| `DR-MODEL-105` | 默认 stub、最小必要代码变更、现有 transport/Knowledge 任务稳定 |
| `DR-MODEL-106` | `business-query-plan-v7` 使用语义目录而非逐句规则；LLM 决定 domain/action/field/operator/AND/OR，本地只执行安全准入和行为校验 |
| `DR-MODEL-107` | `literal/value_ref/value_refs`、operator cardinality 和组合必须由 catalog 与 Business exact validator 一致约束；敏感真值模型零可见 |
| `DR-MODEL-108` | `value_ref(s)` 只接收问题中出现的裸 `slot-N`；wrapper、未知/重复/遗漏相关 slot 均由现有严格合同失败关闭，不做本地修补 |
| `DR-MODEL-109` | 用户显式字段是不可丢弃约束；catalog 未开放时模型必须返回明确域的 `unsupported`，禁止近似字段替换、条件丢弃或关联值复用；不增加字段专用黑名单或本地语义解析 |
| `DR-MODEL-112` | §6.3能力分类不承担资料存在性判定；v5独立任务、精确目录输出和输入保护，unsupported后不补救改选 |

权限与审计：模型不接触角色与 JWT；仅记录 snapshot、task version、action、有限错误和调用计数。数据生命周期与迁移回滚不改变数据库或历史 evidence；历史controlled/UAT结果只证明其冻结版本，不能替代现行任务验收。使用独立版本化 manifest 与新结果路径，不新增生产级审批、复杂规则 DSL 或本地语义 Resolver。

## 10. 风险、评审记录与实现就绪判定

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计评审通过并取得实施授权后 |
| 当前实施状态 | Business v7 Prompt/task version 与直接合同测试已实施；§6.1固定flash和Knowledge严格输出模式已实施，原non-live验证见历史P3_00，真实新后端效果未验证 |
| 当前允许实施范围 | §6.3独立v5及non-live范围已按本次授权实施与复评；其余既有范围不变，不包含新的真实模型、ES/BGE或服务验证授权 |
| 当前禁止动作 | 修改历史task/批次、放宽Business validator、unsupported后本地强制选路、额外真实调用或无界验证 |

主要风险是模型替换/遗漏用户条件、敏感值出域和误用旧证据。现行v7以通用字段完整性Prompt、安全目录、严格validator和零调用反例控制，不增加本地语义Resolver；原实验过程见[Business字段完整性历史案例](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-28)，原运行结论不改写。

## 11. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-MODEL-101`; `CON-MODEL-101` | `DR-MODEL-101` | `IMPL-MODEL-101`; `IMPL-MODEL-108`; `IMPL-MODEL-102` | `TEST-MODEL-101`; `TEST-MODEL-102` | `VAL-MODEL-101` |
| `REQ-MODEL-102` | `DR-MODEL-102` | `IMPL-MODEL-104` | `TEST-MODEL-103` | `VAL-MODEL-101` |
| `REQ-MODEL-103` | `DR-MODEL-103` | `IMPL-MODEL-103` | `TEST-MODEL-104` | `VAL-MODEL-102` |
| `REQ-MODEL-103` | `DR-MODEL-104` | `IMPL-MODEL-101`; `IMPL-MODEL-108` | `TEST-MODEL-102` | `VAL-MODEL-101` |
| `REQ-MODEL-104` | `DR-MODEL-106`; `DR-MODEL-107` | `IMPL-MODEL-108`; `IMPL-MODEL-107` | `TEST-MODEL-106`; `TEST-MODEL-107` | `VAL-MODEL-101`; `VAL-MODEL-102` |
| `REQ-MODEL-103`; `REQ-MODEL-104` | `DR-MODEL-108`; `DR-MODEL-109` | `IMPL-MODEL-108` | `TEST-MODEL-107`; `TEST-MODEL-108` | `VAL-MODEL-101`; `VAL-MODEL-102` |
| `REQ-MODEL-102` | `DR-MODEL-105` | `IMPL-MODEL-105` | `TEST-MODEL-105` | `VAL-MODEL-102` |
| `REQ-MODEL-107`（L1_00 CR-AD-006） | `DR-MODEL-112` | `IMPL-MODEL-110` | `TEST-MODEL-110` | `VAL-MODEL-104` |
