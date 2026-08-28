# [L2_00_02] 单体 Agent 模型接入与 Business filters QueryPlan 详细设计

> 文档状态：Approved

## 1. 文档信息、上位约束与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.5 |
| 更新时间 | 2026-08-28 |
| 上位约束来源 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v3.2 |
| 关联责任边界 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md)；[`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) |
| Provider 基线 | 已有 DeepSeek transport、input guard 与已实施 `business-query-plan-v4`；本版目标为独立 `business-query-plan-v5`，默认 provider 仍为 stub |
| 归档来源 | [v1.9 已评审旧版](历史文档/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN_v1.9.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。v2.5 设计 Business v5 的 operator 语义目录、受控 `value_refs` 和自然语言完整意图要求；v4 源码及历史 evidence 保持不可变。

## 2. 设计目标、范围外与当前实现基线

目标是生成一个 provider-neutral JSON 对象，由 Business 下游解码 filters QueryPlan。Model 层负责 minimized question、安全 catalog、受保护 slot 引用、Prompt、provider framing decoder、timeout/cancel 和 secret 安全；不负责业务字段合法性、Business DTO 映射、业务最终授权或业务调用。

范围外：修改 Knowledge/answer task、将 SQL/ES/endpoint 暴露给模型、新增模型平台依赖、模型失败回退或修改现有公共 Core/HTTP 合同。当前 `business-query-plan-v4` 已实施；目标 `business-query-plan-v5` 在不复用历史授权的前提下补充 operator 语义、单/多值形状、AND/OR 保留和姓名/地区自然语言规划。具体运行批次、调用计数和证据哈希由 UAT_00/evidence 管理。

| 需求编号 | 需求 |
|---|---|
| `REQ-MODEL-101` | 安全三动作 catalog 与 filters JSON 一次规划 |
| `REQ-MODEL-102` | Provider framing decoder 与 Business payload decoder 分离 |
| `REQ-MODEL-103` | 敏感值保护、unsupported 完整意图和模型失败零下游调用 |
| `REQ-MODEL-104` | v5 必须从安全目录理解精确任一、前缀任一、包含任一和批准的同字段 AND；不得依赖本地句式规则 |

| 约束编号 | 上位约束 |
|---|---|
| `CON-MODEL-101` | Model 不拥有 Business 字段验证、角色授权、数据库/ES 或结果投影 |

## 3. 模块职责设计、依赖方向与接口契约

现有 provider-neutral `BusinessQueryPlanGenerator.generate(...)` 返回 `JsonObject`；复用现有 ModelContext、DeepSeek transport 与 client 生命周期。新增独立 `business_query_plan_v5.py` 并由当前生产组合根切换到 v5；既有 v4 模块及更早 source、manifest 和 evidence 保持 Git 可追溯及字节不可变，不以旧 Prompt 结果证明 v5 多值/组合行为。

provider response decoder 仅执行单 JSON object、重复键、额外文本、字节数、深度、集合上限和有限数字校验。它不解析 Business field/operator；`JsonObject → BusinessQueryPlan` 的 exact 三字段、filters 与业务语义由 `L2_02_00` 拥有。依赖方向固定 `Model task → provider transport` 和 `Graph → provider-neutral Model Port`，禁止反向依赖 Business Adapter 或 Core handler。完整意图示例归属 Model Prompt，保持模型规划职责内聚，不在 Business/Core 新增自然语言解析耦合。

关键已存在接口及目标变更：

```python
BusinessQueryPlanTaskInput(minimized_question: str, catalog: JsonObject, catalog_snapshot_id: str)
build_business_query_plan_task_definition(*, timeout_ms: int, ...) -> ModelTaskDefinition[BusinessQueryPlanTaskInput, JsonObject]
async BusinessQueryPlanGenerator.generate(input: BusinessQueryPlanTaskInput, *, context: ModelCallContext) -> JsonObject
decode_business_query_plan_output(response: StructuredModelResponse, *, max_output_bytes: int, max_json_depth: int, max_collection_items: int) -> JsonObject
```

现有 provider-neutral generator、task input 和 strict framing decoder 保持不变；新增独立 v5 Prompt 和更丰富但仍安全的目录，不新增 Provider 私有类型、额外本地语义解析或公共合同。

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

QueryPlan 模型只规划，不执行 answer task；结果再次发送模型必须由独立 Business egress 策略授权，不是列表查询默认步骤。

### 5.1 Business QueryPlan v5 目录与 Prompt

目录对每个 operator 提供逻辑语义、`scalar/multi` cardinality、1～16 上限及允许的 `literal/value_ref/value_refs` tagged forms，并对每个字段提供允许组合。Prompt 负责理解问句、祈使句、姓氏/姓名/地区、多值和 AND/OR；输入安全层只把敏感值替换为 `protected-ref(slot-N)`，保留词序与连接词。模型不得复述 slot 真值，不能用 `in` 代替 `prefix_any/contains_any`，也不能在任一条件不可表达时生成部分计划。

不含“员工”但经输入层识别出受保护姓名/姓氏强提示的请求可以进入同一 Business planning；这只是受控候选准入，domain/action 仍由模型决定，非法或不确定计划按 existing unsupported/invalid plan 失败关闭。v5 必须独立版本化，v4 模块和冻结证据不修改。

## 6. Transport、失败类型与事务边界

复用现有 DeepSeek HTTP transport、超时、取消、client lifecycle 和 `LLM_API_KEY` 环境注入；默认 provider 必须继续为 stub。non-live 仅使用 fake transport，不读取密钥；真实调用另由 P3 live gate 明确约束。

模型失败/timeout、非法 framing、输入拒绝或取消固定映射为 `unavailable/timeout/invalid_argument`，业务下游调用为 0，不 retry、fallback、选择 Knowledge 或第二 domain。JWT/slot/model response 不持久化；数据生命周期只在单请求内，事务边界与一致性归业务服务。

## 7. 实现落点清单

| 实现编号 | 已验证位置 | 目标变更 |
|---|---|---|
| `IMPL-MODEL-101` | `agent-runtime/src/agent_runtime/model/deepseek/business_query_plan.py` | v4 filters Prompt、完整意图 unsupported 反例、task version、no-tools JSON contract |
| `IMPL-MODEL-102` | `agent-runtime/src/agent_runtime/business/planner_catalog.py` | 由 Business 提供安全三动作 field/operator 目录；模型只消费 |
| `IMPL-MODEL-103` | `agent-runtime/src/agent_runtime/model/input_guard.py` | 安全地点片段、slot、Business 锚点与 prohibited 字段回归 |
| `IMPL-MODEL-104` | `agent-runtime/src/agent_runtime/model/contracts.py` | 保留 generator `JsonObject` 边界，仅扩展必要 task 输入 |
| `IMPL-MODEL-105` | `agent-runtime/src/agent_runtime/bootstrap.py` | 保持现有 provider-neutral generator/lifecycle 装配，不新增本地语义分支 |
| `IMPL-MODEL-106` | `agent-runtime/src/agent_runtime/model/deepseek/business_query_plan_v5.py` | v5 Prompt、task version、operator-specific value shape 和完整意图合同；v4 保持历史兼容 |
| `IMPL-MODEL-107` | `agent-runtime/src/agent_runtime/business/planner_catalog.py` | 输出 operator 语义、cardinality、tagged forms、数量和字段组合，不泄漏物理字段 |

## 8. 测试与验证设计

| 测试编号 | 核心场景 |
|---|---|
| `TEST-MODEL-101` | 三动作安全目录、operator、workBase/物理信息/敏感字段为 0 |
| `TEST-MODEL-102` | v4 Prompt：上海地址、职位、amount/date 范围；semantic+地点过滤和缺少批准时钟的相对日期必须 exact unsupported/零调用 |
| `TEST-MODEL-103` | duplicate key、非 JSON、深度/大小/float 非法，provider decoder 边界明确 |
| `TEST-MODEL-104` | slot、详细地址/姓名/标识零出域，失败/取消/unsupported 业务零调用 |
| `TEST-MODEL-105` | Knowledge/answer 现有任务、默认 stub、client close 和并发隔离回归 |
| `TEST-MODEL-106` | 单/复姓、多姓名、多姓氏、同字段 AND、单/多地区及句式变化的 v5 fake Prompt/catalog 合同 |
| `TEST-MODEL-107` | `value_refs` 重复/跨请求/超限、非法 value shape、模型错误/超时均零 Employee 调用 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-MODEL-101` | fake transport catalog/Prompt/framing contract tests |
| `VAL-MODEL-102` | Business/Core/Knowledge 非 live 回归、strict mypy、compileall |

## 9. 设计规则、权限与审计设计

| 规则编号 | 设计规则 |
|---|---|
| `DR-MODEL-101` | 当前生产 task 必须是 code-bound `business-query-plan-v5` 并只生成逻辑 filters QueryPlan；v4 及更早 source、manifest 与证据只作不可变历史 |
| `DR-MODEL-102` | provider framing decoder 和 Business payload decoder 分层，不互相替代 |
| `DR-MODEL-103` | 安全目录只包含三动作及已启用逻辑 field/operator，protected slot 不含真实值 |
| `DR-MODEL-104` | 完整意图不可表达时 exact unsupported；semantic+结构过滤与无批准时钟的相对日期必须通过显式 Prompt 反例失败关闭，禁止近似、丢条件和任何 fallback |
| `DR-MODEL-105` | 默认 stub、最小必要代码变更、现有 transport/Knowledge 任务稳定 |
| `DR-MODEL-106` | `business-query-plan-v5` 使用语义目录而非逐句规则；LLM 决定 domain/action/field/operator/AND/OR，本地只执行安全准入和行为校验 |
| `DR-MODEL-107` | `literal/value_ref/value_refs`、operator cardinality 和组合必须由 catalog 与 Business exact validator 一致约束；敏感真值模型零可见 |

权限与审计：模型不接触角色与 JWT；仅记录 snapshot、task version、action、有限错误和调用计数。数据生命周期与迁移回滚不改变数据库或历史 evidence；v3 controlled/UAT 结果只能证明历史版本，不得替代 v4 UAT。使用独立版本化 manifest 与新结果路径，不新增生产级审批、复杂规则 DSL 或本地语义 Resolver。

## 10. 风险、评审记录与实现就绪判定

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计评审通过并取得实施授权后 |
| 当前实施状态 | v4 Prompt/task version、版本化 UAT、adversarial fake/non-live 与既有受控真实验证已完成 |
| 当前允许实施范围 | 已实施 v4 链路的缺陷修复、fake/non-live 回归；额外真实调用须绑定新的受控场景与预算 |
| 当前禁止动作 | 修改 Knowledge task、放宽 Business validator、复用历史授权或无界真实模型调用 |

风险包括 Prompt 遗漏用户条件、敏感值出域和旧版本证据误用。历史 UAT 已证明 semantic+location 原 Prompt 不稳定；以明确反例、adversarial fake、零调用、版本化 task/manifest 及不可变历史控制，不添加本地语义识别。运行批次和证据哈希由 UAT_00/evidence 管理。

## 11. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-MODEL-101`; `CON-MODEL-101` | `DR-MODEL-101` | `IMPL-MODEL-101`; `IMPL-MODEL-102` | `TEST-MODEL-101`; `TEST-MODEL-102` | `VAL-MODEL-101` |
| `REQ-MODEL-102` | `DR-MODEL-102` | `IMPL-MODEL-104` | `TEST-MODEL-103` | `VAL-MODEL-101` |
| `REQ-MODEL-103` | `DR-MODEL-103` | `IMPL-MODEL-103` | `TEST-MODEL-104` | `VAL-MODEL-102` |
| `REQ-MODEL-103` | `DR-MODEL-104` | `IMPL-MODEL-101` | `TEST-MODEL-102` | `VAL-MODEL-101` |
| `REQ-MODEL-102` | `DR-MODEL-105` | `IMPL-MODEL-105` | `TEST-MODEL-105` | `VAL-MODEL-102` |
