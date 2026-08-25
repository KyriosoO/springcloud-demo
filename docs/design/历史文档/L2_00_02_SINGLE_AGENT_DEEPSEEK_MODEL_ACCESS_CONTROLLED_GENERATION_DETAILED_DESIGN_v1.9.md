# [L2_00_02] 单体 Agent 模型接入与 Business filters QueryPlan 详细设计

> 文档状态：Approved

## 1. 文档信息、上位约束与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v1.9 |
| 更新时间 | 2026-08-25 |
| 上位约束来源 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v1.5 |
| 关联责任边界 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md)；[`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) |
| Provider 基线 | 已有 DeepSeek transport、input guard 与旧 `business-query-plan-v2`；默认 provider 为 stub |

修订历史：新 Business 模型任务与安全 catalog 必须承接 filters/operator 三动作，而不能复用旧 detail/flat arguments 的成功证据。

## 2. 设计目标、范围外与当前实现基线

目标是生成一个 provider-neutral JSON 对象，由 Business 下游解码 filters QueryPlan。Model 层负责 minimized question、安全 catalog、受保护 slot 引用、Prompt、provider framing decoder、timeout/cancel 和 secret 安全；不负责业务字段合法性、Business DTO 映射、业务最终授权或业务调用。

范围外：修改 Knowledge/answer task、将 SQL/ES/endpoint 暴露给模型、新增模型平台依赖、真实付费调用、模型失败回退或修改现有公共 Core/HTTP 合同。当前实现的 `business-query-plan-v2` 仍使用旧 argument 结构和旧 action catalog；本版目标 task 及 Prompt 尚未实施。

| 需求编号 | 需求 |
|---|---|
| `REQ-MODEL-101` | 安全三动作 catalog 与 filters JSON 一次规划 |
| `REQ-MODEL-102` | Provider framing decoder 与 Business payload decoder 分离 |
| `REQ-MODEL-103` | 敏感值保护、unsupported 完整意图和模型失败零下游调用 |

| 约束编号 | 上位约束 |
|---|---|
| `CON-MODEL-101` | Model 不拥有 Business 字段验证、角色授权、数据库/ES 或结果投影 |

## 3. 模块职责设计、依赖方向与接口契约

现有 provider-neutral `BusinessQueryPlanGenerator.generate(...)` 返回 `JsonObject`；复用现有 ModelContext、DeepSeek transport 与 client 生命周期。建议修改既有 `agent-runtime/src/agent_runtime/model/deepseek/business_query_plan.py`，将代码绑定 task version 提升为 `business-query-plan-v3`；保留历史 `v2` source/evidence 的 Git 可追溯性，不以旧 Prompt 结果证明新合同。

provider response decoder 仅执行单 JSON object、重复键、额外文本、字节数、深度、集合上限和有限数字校验。它不解析 Business field/operator；`JsonObject → BusinessQueryPlan` 的 exact 三字段、filters 与业务语义由 `L2_02_00` 拥有。依赖方向固定 `Model task → provider transport` 和 `Graph → provider-neutral Model Port`，禁止反向依赖 Business Adapter 或 Core handler。

## 4. 模型安全 catalog 与受控输入

目录只包含 enabled `employee.search`、`employee.semantic_search`、`transaction.search`，逻辑字段、模型安全说明、允许 operator、literal/ref 限制、已批准的日期时区和不可变 snapshot ID。模型不得看到 Java DTO 名称、endpoint、HTTP method、SQL、ES DSL、索引、向量字段/provider、embedding 参数、JWT、角色、详细地址、身份证、姓名、电话、邮箱、业务响应或 `workBaseSi/workBaseAf` 字段。

安全地点片段如“上海”仅在 code-bound 安全地点策略识别通过后进入模型；详细地址及其他个人字段只允许 request-local slot。Business 问题先由 protected input extractor 生成 slot，再由 Model input guard 核实 minimized question；guard 不选择 domain/action、不补参数、不创建第二链路。

## 5. Prompt、输出合同与核心处理流程

Prompt 必须明确：

1. 一次只输出一个 exact `{domain,action,arguments}` JSON object。
2. 条件搜索 arguments 使用 filters/page/size/sorts，每个 filter 都必须满足目录中逻辑 field/operator/value tagged union。
3. Transaction `gt + lt` 可以组合；不得吞掉用户条件、把逻辑 operator 编码进 field、发明字段或使用物理信息。
4. Employee 地点“上海”规划为 `contact_address contains "上海"`；职位对应 position；workBase 永远不可用。
5. Employee semantic 只接受语义文本；语义+结构过滤、非法日期边界和其他不可表达组合必须返回 exact `action=unsupported`，arguments 为空。
6. 限定 domain 的不支持请求返回该 domain + unsupported；无可识别 domain 时返回 `domain=unsupported/action=unsupported/arguments={}`。

QueryPlan 模型只规划，不执行 answer task；结果再次发送模型必须由独立 Business egress 策略授权，不是列表查询默认步骤。

## 6. Transport、失败类型与事务边界

复用现有 DeepSeek HTTP transport、超时、取消、client lifecycle 和 `LLM_API_KEY` 环境注入；默认 provider 必须继续为 stub。non-live 仅使用 fake transport，不读取密钥；真实调用另由 P3 live gate 明确约束。

模型失败/timeout、非法 framing、输入拒绝或取消固定映射为 `unavailable/timeout/invalid_argument`，业务下游调用为 0，不 retry、fallback、选择 Knowledge 或第二 domain。JWT/slot/model response 不持久化；数据生命周期只在单请求内，事务边界与一致性归业务服务。

## 7. 实现落点清单

| 实现编号 | 已验证位置 | 目标变更 |
|---|---|---|
| `IMPL-MODEL-101` | `agent-runtime/src/agent_runtime/model/deepseek/business_query_plan.py` | v3 filters Prompt、task version、no-tools JSON contract |
| `IMPL-MODEL-102` | `agent-runtime/src/agent_runtime/business/planner_catalog.py` | 由 Business 提供安全三动作 field/operator 目录；模型只消费 |
| `IMPL-MODEL-103` | `agent-runtime/src/agent_runtime/model/input_guard.py` | 安全地点片段、slot、Business 锚点与 prohibited 字段回归 |
| `IMPL-MODEL-104` | `agent-runtime/src/agent_runtime/model/contracts.py` | 保留 generator `JsonObject` 边界，仅扩展必要 task 输入 |
| `IMPL-MODEL-105` | `agent-runtime/src/agent_runtime/bootstrap.py` | provider-neutral v3 generator/lifecycle 组合装配 |

## 8. 测试与验证设计

| 测试编号 | 核心场景 |
|---|---|
| `TEST-MODEL-101` | 三动作安全目录、operator、workBase/物理信息/敏感字段为 0 |
| `TEST-MODEL-102` | v3 Prompt：上海地址、职位、amount/date 范围和 exact unsupported |
| `TEST-MODEL-103` | duplicate key、非 JSON、深度/大小/float 非法，provider decoder 边界明确 |
| `TEST-MODEL-104` | slot、详细地址/姓名/标识零出域，失败/取消/unsupported 业务零调用 |
| `TEST-MODEL-105` | Knowledge/answer 现有任务、默认 stub、client close 和并发隔离回归 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-MODEL-101` | fake transport catalog/Prompt/framing contract tests |
| `VAL-MODEL-102` | Business/Core/Knowledge 非 live 回归、strict mypy、compileall |

## 9. 设计规则、权限与审计设计

| 规则编号 | 设计规则 |
|---|---|
| `DR-MODEL-101` | code-bound `business-query-plan-v3` 只生成逻辑 filters QueryPlan |
| `DR-MODEL-102` | provider framing decoder 和 Business payload decoder 分层，不互相替代 |
| `DR-MODEL-103` | 安全目录只包含三动作及已启用逻辑 field/operator，protected slot 不含真实值 |
| `DR-MODEL-104` | 完整意图不可表达时 exact unsupported，禁止近似、丢条件与任何 fallback |
| `DR-MODEL-105` | 默认 stub、最小必要代码变更、现有 transport/Knowledge 任务稳定 |

权限与审计：模型不接触角色与 JWT；仅记录 snapshot、task version、action、有限错误和调用计数。数据生命周期与迁移回滚不改变数据库或历史 evidence；回滚撤销 v3 装配，不把 v2 重新用于新 Business filters 路径。该方案避免新增平台、复杂规则 DSL 与低内聚的领域 provider 耦合。

## 10. 风险、评审记录与实现就绪判定

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计评审通过并取得实施授权后 |
| 当前允许实施范围 | v3 task/catalog/input guard 的 fake/non-live 实施 |
| 当前禁止动作 | 真实模型调用、读取密钥、修改 Knowledge task、放宽 Business validator |

风险包括 Prompt 遗漏用户条件、敏感值出域和旧 v2 证据误用；以 adversarial fake、零调用、source/evidence 历史核查控制。评审记录：本版已通过独立设计评审。

## 11. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-MODEL-101`; `CON-MODEL-101` | `DR-MODEL-101` | `IMPL-MODEL-101`; `IMPL-MODEL-102` | `TEST-MODEL-101`; `TEST-MODEL-102` | `VAL-MODEL-101` |
| `REQ-MODEL-102` | `DR-MODEL-102` | `IMPL-MODEL-104` | `TEST-MODEL-103` | `VAL-MODEL-101` |
| `REQ-MODEL-103` | `DR-MODEL-103` | `IMPL-MODEL-103` | `TEST-MODEL-104` | `VAL-MODEL-102` |
| `REQ-MODEL-103` | `DR-MODEL-104` | `IMPL-MODEL-101` | `TEST-MODEL-102` | `VAL-MODEL-101` |
| `REQ-MODEL-102` | `DR-MODEL-105` | `IMPL-MODEL-105` | `TEST-MODEL-105` | `VAL-MODEL-102` |
