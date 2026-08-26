# [L2_00_01] 单体 Agent Core 执行、QueryPlan 接缝与能力注册详细设计

> 文档状态：Approved

## 1. 文档信息、来源与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.1 |
| 更新时间 | 2026-08-26 |
| 上位约束来源 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v2.2 |
| 关联责任边界 | [`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md)；[`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) |
| 归档来源 | [v1.8 已评审旧版](历史文档/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN_v1.8.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 设计目标、范围外与当前实现基线

目标是在不修改公共 Core、HTTP、CapabilityResult 和 Knowledge 契约的前提下，由唯一 LangGraph Business bridge 执行 filters QueryPlan 验证并产生一个 ActionCandidate。范围外包括本地语义补参、SQL/ES 生成、业务权限判断、domain fallback 和真实模型调用。

当前实现：`agent-runtime/src/agent_runtime/graph/business_query_planning.py`、`agent-runtime/src/agent_runtime/business/query_plan.py`、`agent-runtime/src/agent_runtime/bootstrap.py` 及 Registry/Core 已承接新 filters QueryPlan、`employee.search`、`employee.semantic_search`、扩展 `transaction.search` 和唯一三动作生产组合根。Employee 服务端点级角色转换、六场景受控联调及正式 18 项 v4 UAT 全部通过；每个成功业务请求仅生成一个计划、执行一个固定 endpoint。

| 需求编号 | 需求 |
|---|---|
| `REQ-CORE-101` | 规划、严格验证和一次 Core 执行顺序唯一 |
| `REQ-CORE-102` | 三动作组合根、不可变 snapshot 与 Business 无旁路 |
| `REQ-CORE-103` | 请求隔离、取消、失败关闭并保留 Knowledge/Core 兼容 |

| 约束编号 | 上位约束 |
|---|---|
| `CON-CORE-101` | L1 Core 不拥有业务合同、模型 provider 或角色授权 |

## 3. 模块职责设计、依赖方向与接口契约

```text
BusinessQueryPlanningNode
  → BusinessQueryPlanGenerator.generate(request)
  → BusinessQueryPlanDecoder.decode(JsonObject)
  → BusinessQueryPlanValidator.validate(plan, snapshot)
  → ProtectedValueBinder.bind(validated, slots, request_id)
  → CapabilityExecutionCore.execute(ActionCandidate)
```

Model generator 只返回完成 provider framing 校验的 `JsonObject`；Business decoder 才理解 filters/page/size/sorts；validator 固定 domain/action、代码/配置、operator/slot/时间/Decimal；binder 只解析同请求引用，不产生缺失语义。Core 继续调用既有 capability argument validator，不接触模型、字段配置或业务私有 DTO。

依赖方向固定为 graph → provider-neutral model/business contracts → Core/Registry → domain handler；禁止绕过、反向依赖、直接调用 registered handler 或依赖私有 registered-call 类型。

关键已存在接缝必须保持明确：

```python
async BusinessQueryPlanningNode.__call__(input: BusinessPlanningInput) -> BusinessPlanningDecision
BusinessQueryPlanDecoder.decode(payload: JsonObject) -> BusinessQueryPlan
BusinessQueryPlanValidator.validate(plan: BusinessQueryPlan, *, snapshot: BusinessConfigurationSnapshot) -> BusinessQueryPlanValidationResult
ProtectedValueBinder.bind(plan: ValidatedBusinessQueryPlan, *, slots: ProtectedValueSlots, request_id: str) -> ActionCandidate
async CapabilityExecutionCore.execute(*, candidate: ActionCandidate, scope: RequestExecutionScope) -> CapabilityResult
```

前三个 Business 接缝的 filters 语义已在既有类中完成扩展，并由当前 contract/non-live/UAT 证据验证；公共 Core `execute` 签名与返回合同保持不变。

## 4. 核心处理流程、状态与失败类型

1. 接收已认证的 execution scope、request ID、取消信号和用户 JWT。
2. 输入安全闸门先创建 request-local protected slots 和最小化问题，并捕获不可变 Business 配置 snapshot；不得在此步骤选择 domain/action 或生成 filters。
3. 检查取消，然后调用模型一次；模型只接收安全 catalog 和 slot 标识。
4. 再检查取消，依次执行 provider decode、Business decode、validator。
5. exact unsupported sentinel 直接终止；其他失败映射到 `invalid_argument/timeout/unavailable`，Core 和 Adapter 均不调用。
6. 在 slot binding 前检查取消；binder 生成唯一 action candidate，现有 Core/Registry 验证和执行一次。
7. 返回确定性列表/错误；禁止第二动作、Employee search/semantic 切换、跨域切换及 Knowledge fallback。

快照不一致应在 readiness 失败；若请求间发生失配，返回 `internal_failure` 且业务调用为 0。业务 `forbidden` 只允许当前固定 endpoint 的单次请求。

## 5. 组合根、取消与事务边界

`agent-runtime/src/agent_runtime/bootstrap.py` 已装配 `employee.search`、`employee.semantic_search`、`transaction.search` 三条 code-bound capability、共享 JSON 配置 snapshot、provider-neutral planning generator、request cancellation 和固定 domain handlers。启动检查 action 唯一、descriptor/config/validator/mapper/codec 对齐、三动作与注册表一致，以及旧 `employee.detail` 不再出现在目标模型目录。

默认 provider 仍为 stub；只有测试明确注入 fake provider 或后续获得真实调用授权，才允许规划成功。现有 Knowledge 图和公共 action selector 不得被无关修改。

请求状态、JWT、slot 和计划都不落盘；无 Agent 数据库事务。事务边界与一致性归业务服务；取消在模型前、模型后、绑定前检查，禁止迟到业务执行和跨请求 slot 复用。

## 6. 实现落点清单

| 实现编号 | 已验证位置 | 目标变更 |
|---|---|---|
| `IMPL-CORE-101` | `agent-runtime/src/agent_runtime/graph/business_query_planning.py` | 复用现有 node，承接新 filters plan 与单次调用顺序 |
| `IMPL-CORE-102` | `agent-runtime/src/agent_runtime/bootstrap.py` | 新三动作/config/provider 组合根及唯一可达性 |
| `IMPL-CORE-103` | `agent-runtime/src/agent_runtime/graph/state.py` | 请求级 snapshot、取消和 slot 生命周期复核 |
| `IMPL-CORE-104` | `agent-runtime/src/agent_runtime/core/execution.py` | 保持公共 Core 不改；以回归验证一次执行 |

## 7. 测试与验证设计

| 测试编号 | 场景 |
|---|---|
| `TEST-CORE-101` | model→decode→validate→bind→Core 调用顺序、exact unsupported 和零调用 |
| `TEST-CORE-102` | 三动作 Registry、旧 detail/Resolver/ID-only/fallback 不可达 |
| `TEST-CORE-103` | snapshot 漂移、并发 slot 隔离、三处取消、Knowledge 回归 |
| `TEST-CORE-104` | business 服务拒绝只触发固定 endpoint，一次 handler 上界 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-CORE-101` | 定向 graph/Core 单测、组合根契约和 fake handler 调用计数 |
| `VAL-CORE-102` | Business/Knowledge 回归、strict mypy 和 compileall |

## 8. 设计规则、权限与审计设计

| 规则编号 | 设计规则 |
|---|---|
| `DR-CORE-101` | Model decoder、Business decoder、validator、binder、Core 必须固定顺序 |
| `DR-CORE-102` | 三动作是唯一 Business 生产可达路径；不得保留旧 detail/Resolver 旁路 |
| `DR-CORE-103` | snapshot、slot、JWT 和取消只存在于当前请求；失败关闭 |
| `DR-CORE-104` | 公共 Core/HTTP/Knowledge 合同稳定，保持高内聚与最小必要变更 |

权限与审计：Runtime 只透传当前用户 JWT，业务角色由业务服务判断；日志只允许 correlation/action/阶段/有限错误/调用计数，禁止问题、slot、JWT、完整计划和原始响应。数据生命周期与迁移回滚：无数据库变更；回滚只撤销新对象图，不恢复旧 Business 本地 Resolver。

## 9. 风险、评审记录与实施就绪判定

风险包括模型失败被误降级、组合根混入历史 selector、取消后晚执行及请求 slot 泄漏；对应唯一可达性、取消和零调用测试。最小变更只扩展既有 node/组合根，不新增通用编排框架。

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计评审通过并取得实施授权后 |
| 当前实施状态 | filters planning bridge、三动作组合根、单动作/取消/隔离及 non-live/live/UAT 验证已完成 |
| 当前允许实施范围 | 仅允许按新的已评审需求修复现行链路并执行 non-live 回归 |
| 当前禁止动作 | 修改公共 Core/HTTP/Knowledge、恢复旁路或扩大授权 |

评审记录：当前大版本已通过独立分层与跨层评审；不继承旧版本评审过程。

## 10. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-CORE-101`; `CON-CORE-101` | `DR-CORE-101` | `IMPL-CORE-101` | `TEST-CORE-101` | `VAL-CORE-101` |
| `REQ-CORE-102` | `DR-CORE-102` | `IMPL-CORE-102` | `TEST-CORE-102`; `TEST-CORE-104` | `VAL-CORE-101` |
| `REQ-CORE-103` | `DR-CORE-103` | `IMPL-CORE-103` | `TEST-CORE-103` | `VAL-CORE-102` |
| `REQ-CORE-103` | `DR-CORE-104` | `IMPL-CORE-104` | `TEST-CORE-103` | `VAL-CORE-102` |
