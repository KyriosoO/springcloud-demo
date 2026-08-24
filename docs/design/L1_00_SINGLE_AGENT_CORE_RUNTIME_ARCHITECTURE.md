# [L1_00] 单体 Agent 核心与运行架构

> 文档状态：Approved
> 文档层级：L1

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L1_00 |
| 文档层级 | L1 |
| 当前版本 | v1.2 |
| 更新日期 | 2026-08-24 |
| 上位文档 | [`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v1.2 |
| 权威范围 | Runtime 请求状态、Business QueryPlan 调用顺序、Core、能力注册、组合根和模型端口协作 |
| 实施状态 | Business QueryPlan 节点、绑定、取消和组合校验已有 non-live 实现；system entry/E2E/live 尚未完成，旧 Business 可执行 Resolver 资产待安全清理 |

## 2. 变更记录

v1.1 保留 LangGraph、Core、Registry、Model Port 和单动作契约，废止 Employee/Transaction 目标路径中的“Local Resolver 优先、模型只选 ID”。Business 请求改为强制一次 LLM QueryPlan，再经本地验证映射为既有 `ActionCandidate`。Knowledge 既有内部流程不因本变更成为 Business 回退。v1.2 明确共享非 Business Hybrid/ID-only 组件继续保留，但 Employee/Transaction 专属 Resolver 源码及仅验证旧旁路的测试在无调用方后删除；冻结历史 harness 所需兼容类型可保留，生产工厂必须拒绝非空绑定，历史 evidence/hash 不动。

## 3. 目标与边界

### 3.1 目标

- LangGraph 唯一推进请求状态和调用顺序；
- Business 模型输出包含逻辑 `domain/action/arguments`；
- Core 继续只执行最终、强类型、单一候选，不吸收领域语法；
- 组合根证明每个 Business 动作只有一个 planner/validator/binder/handler/Adapter 链；
- 模型、配置或引用失败时在 Adapter 之前失败关闭。

### 3.2 范围外

- Spring HTTP/OpenAPI 字段变化；
- Employee/Transaction 业务字段和 endpoint 细节；
- Knowledge 检索内部设计；
- SQL/ES、业务授权、自动重试和 Multi-Agent。

### 3.3 上位约束映射

| L0 约束 | 本模块落实 |
|---|---|
| `SA-C-001/002` | LangGraph 唯一状态、Core 单动作 |
| `SA-C-005～010` | QueryPlan exact 校验、无 Resolver/切域/Knowledge 回退 |
| `SA-C-008/012` | slot 保护敏感值，物理调用由 Adapter/服务掌握 |
| `SA-C-014` | 当前实现与目标设计分离 |

## 4. 模块核心职责、唯一责任与不负责事项

| 组件 | 输入 | 输出 | 禁止职责 |
|---|---|---|---|
| Runtime entry | 已认证内部请求 | 请求级图状态 | 重新认证、业务授权 |
| Request Guard | question/context | 最小化问题、request-local slot map 或拒绝 | 选择 Business domain/action |
| BusinessQueryPlanningNode | 最小化问题、模型安全 catalog、快照 | 未信任 QueryPlan 或模型失败 | 执行、补参、访问下游 |
| QueryPlanDecoder | 模型文本 | exact 结构对象 | 语义修补、宽松 coercion |
| BusinessQueryPlanValidator | 结构对象、代码定义、配置快照 | 已验证逻辑计划 | 绑定敏感值、访问服务 |
| ProtectedValueBinder | 已验证计划、同请求 slot map | 既有动作参数 | 猜值、跨请求引用 |
| CapabilityArgumentValidator | 动作参数 | `ActionCandidate` | 问题理解 |
| CapabilityExecutionCore | 候选、上下文 | 统一 `CapabilityResult` | 选择第二动作、领域路由 |
| CapabilityRegistry | descriptor/validator/handler | 不可变注册表 | 动态发现任意工具 |
| Composition Root | 定义、配置、Provider | 唯一运行对象图 | 运行时隐式补默认绑定 |

## 5. 运行视图

```text
Runtime entry
  → access-derived request context
  → Request Guard
     ├─ reject → terminal result
     └─ minimized business question + protected slots
         → BusinessQueryPlanningNode
         → QueryPlanDecoder
         → BusinessQueryPlanValidator(config snapshot)
         → ProtectedValueBinder
         → CapabilityArgumentValidator
         → ActionCandidate
         → CapabilityExecutionCore.execute
         → registered handler
         → domain Adapter
```

Knowledge 分支仍调用 Knowledge Capability 自己的流程。Business 计划失败、校验失败或执行失败不得进入 Knowledge 分支。

## 6. 核心契约

### 6.1 Business QueryPlan

Provider-neutral 逻辑形态：

```text
BusinessQueryPlan
  domain: exact finite id
  action: exact registered id
  arguments: exact object of configured logical arguments
```

QueryPlan 不进入公共 Spring API，也不直接进入 Core。它先在 Business 边界转换为现有 ActionCandidate，从而保持 Core 公共执行契约稳定。

### 6.2 参数值

逻辑值是以下有限并集：

- 配置允许模型读取的 typed literal；
- `value_ref`：只引用当前请求 Guard 建立的 opaque slot。

Binder 只做引用解析和目标类型构造，不改变 domain/action/argument key/operator。引用不存在、重复使用冲突、类型不符或跨请求均失败。

### 6.3 ActionCandidate 与 Core

`ActionCandidate` 保持一个 `capability_id`、已绑定参数和来源元数据。Business 来源必须标识为经 QueryPlan 验证，并携带配置 snapshot ID；Core 拒绝：

- 未注册/未启用动作；
- snapshot 缺失或与注册绑定不一致；
- 第二次执行；
- 参数 validator 未通过；
- candidate 的 domain/action 映射不唯一。

### 6.4 Model Port

Model Port 提供独立任务：

- Business QueryPlan generation：强制输出 exact `domain/action/arguments`；
- 可选 answer generation：只消费已批准的安全 facts；
- Knowledge 任务：由 Knowledge 设计治理。

Business QueryPlan 任务不得复用 ID-only selector 作为等价实现，也不得在 transport 失败后调用 Local Resolver。

## 7. 状态模型、数据流与一致性

请求状态至少包含：

| 字段 | 所有者 | 约束 |
|---|---|---|
| correlation/deadline/principal token | Runtime context | token 不进入日志/模型 |
| original question | Runtime | 仅 Guard 输入；不进入 Business model 原样载荷 |
| minimized question | Guard | 不含受保护 literal |
| protected slot map | Guard | 请求内存；终止后销毁 |
| config snapshot | Composition Root | 请求开始时固定 |
| query plan | Planning node | 未信任，验证后不可修改 |
| action candidate | Validator/Binder | 最多一个 |
| execution count | Core | 只能从 0 到 1 |
| result | Capability | 终态不可被模型改义 |

Canonical 顺序不可调整为本地先解析。任何实现不得并行调用多个 domain planner、多个 Adapter 或 speculative 下游查询。

## 8. 组合根与启动校验

组合根负责建立：

- 不可变 capability registry；
- Business code-bound definitions 与配置 snapshot；
- 一个 Business QueryPlan decoder/validator/binder；
- 每个动作一个 handler 和一个 Adapter provider；
- 一个明确的 model provider；默认 `stub` 只供非 live/失败关闭验证，不能满足业务 UAT 成功路径。

启动必须检查：

1. config domain/action 是代码定义子集；
2. descriptor、plan definition、validator、binder、handler、Adapter ID 完全对齐；
3. Business 动作不存在 Local Resolver/ID-only selector 到 Core 的可达生产边；
4. 字段、operator、边界、结果字段和模型字段均为代码集合子集；
5. snapshot/version 唯一且可追踪；
6. provider 生命周期、取消和关闭钩子完整。

任一失败时 Runtime readiness 失败，不允许只关闭模型后继续走本地查询。

## 9. 失败、取消与并发

| 场景 | 映射 | 不变量 |
|---|---|---|
| Guard 拒绝 | `forbidden/unsupported` | model/Adapter=0 |
| model timeout/unavailable | `timeout/downstream_failure` | 无 fallback |
| exact decode/schema 失败 | `invalid_argument` | 不修复模型文本 |
| config/domain/action 不支持 | `unsupported` | 不切域/Knowledge |
| value_ref/typed value 失败 | `invalid_argument` | Adapter=0 |
| Core 第二动作 | `invalid_argument` | handler 仅一次或零次 |
| 下游拒绝/无结果/失败 | `forbidden/no_result/downstream_failure` | 终态保持原义 |

每请求使用独立 slot map、QueryPlan、snapshot reference 和执行计数；模型 client 可共享，但 ModelContext 不得跨请求泄漏。取消信号从 Spring deadline 传到模型和 Adapter；迟到结果不得进入终态。

## 10. 安全与可观测性

- 模型输入只含最小化 question、模型安全 domain/action/field description 和必要有限枚举；
- 模型目录不含 endpoint、HTTP、SQL/ES、索引、代码符号、角色、JWT、结果字段或业务原始响应；
- 日志只记录 correlation、task version、catalog/config snapshot、domain/action（验证后）、阶段、有限状态、调用计数和耗时；
- 不记录原始 question、slot value、JWT、完整 QueryPlan/模型响应或业务响应；
- 监测 `model_calls`、`adapter_calls`、`core_execution_count`，以证明唯一链路和失败关闭。

## 11. 依赖规则与同层协作边界

| 调用方 | 可依赖 | 禁止依赖 |
|---|---|---|
| Spring | Runtime internal contract | Core/Adapter/Model 实现 |
| LangGraph nodes | Capability API、Model Port、Business planning port | Java 业务实现、数据库 |
| Business planning common | provider-neutral model contract、business definitions | HTTP endpoint、具体 Adapter transport |
| Core | capability types/registry | Model、domain config、Adapter |
| Handler | domain port/Adapter | LangGraph state、其他 domain Adapter |
| Model transport | model task contract | Core、业务服务、JWT |

## 12. 关键决策

| ID | 决策 | 影响 |
|---|---|---|
| `CR-AD-001` | LangGraph 为唯一状态和调用顺序权威 | Spring/Core 不编排 |
| `CR-AD-002` | Business QueryPlan 在 Core 之前完成验证与绑定 | Core 公共契约保持稳定 |
| `CR-AD-003` | Business 必须一次模型计划后才可能形成候选 | 现有 Local Resolver 生产边需移除 |
| `CR-AD-004` | slotting 是安全转换，不是语义 Resolver | 敏感值不出域且模型仍决定动作/参数引用 |
| `CR-AD-005` | 配置 snapshot 与候选绑定 | 防止运行中漂移 |
| `CR-AD-006` | 模型失败不降级 | 可用性让位于契约正确性 |
| `CR-AD-007` | Knowledge 与 Business 无回退边 | 避免权限/事实混淆 |

## 13. 下位 L2 详细设计交付约束

| L2 | 本文下放内容 | 不得越界 |
|---|---|---|
| [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) | QueryPlan 到候选的节点顺序、Core/Registry、组合根唯一性 | 域字段、HTTP codec |
| [`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | Business QueryPlan model task、catalog、exact decode、transport | 业务语义 validator、Adapter |
| `L2_02_00` | Business 计划类型、配置、binder、字段/出域公共规则 | Core 和模型 transport |

## 14. 当前实现差距

| 目标 | 当前事实 | 处理 |
|---|---|---|
| Business 模型输出完整 QueryPlan | task/generator/两级 decoder 已实现 | system entry 仍需装配并做双域 E2E |
| 模型强制参与 | Runtime Business 分支已有 non-live 实现 | 清理专属 Resolver 资产并验证生产唯一可达性 |
| 强类型 snapshot 校验 | 配置、canonical catalog 与启动 validator 已实现 | E2E 证明实际启动快照一致 |
| 受保护引用 | Guard extractor + value_ref + 同请求 binder 已实现 | E2E 继续证明并发隔离和零泄漏 |
| 真实 LLM UAT | 当前 UAT 以 stub 为主 | 实施完成后单独受控 live UAT |

历史不可变 evidence/hash 保持不变；无调用方的旧可执行资产按 v1.2 清理，不得再作为符合性证据。

## 15. 验证与评审

### 15.1 必须验证

- exact QueryPlan、非法字段/值、snapshot 漂移；
- model failure 时 Core/Adapter/业务调用为零；
- 无 Local Resolver/ID-only selector Business 生产路径；
- request slot 并发隔离和零泄漏；
- Core 单动作、取消和终态不变；
- default stub 失败关闭与 explicit real provider UAT 分离。

### 15.2 v1.1 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | LangGraph/Core/组合根职责及唯一路径 | 补齐边界与 readiness，修复后通过 |
| 内审2 | unsupported、模型失败与无旁路 | 增加终态隔离并统一状态，修复后通过 |
| 内审3 | 并发 slot、JWT、跨层引用与 DAG | 无新增运行边；修正关联工作包引用后通过 |
| 独立评审 R1～R3 | 分层与跨层一致性 | 两级 decoder 与 unsupported 合同修复后，R3 无发现，通过 |
| v1.2 内审1 | Runtime 唯一路径与共享组件 | 仅清理两域专属 Resolver，保留非 Business Hybrid/ID-only | 修复后通过 |
| v1.2 内审2 | 历史复验兼容 | legacy definition 字段可保留但生产工厂拒绝非空绑定 | 修复后通过 |
| v1.2 内审3 | 取消、并发、DAG与过度设计 | 无新增运行节点/依赖边，system E2E 后再删空快照字段 | 通过 |
| v1.2 独立评审 R1～R3 | Runtime 可达性与清理兼容 | legacy 字段仅历史复验、生产 factory 拒绝；R3 无发现 | 通过 |

评审结论不等于代码实施完成。

## 16. 结论

Runtime 继续以 LangGraph 编排和 Core 确定性执行为骨架，但 Employee/Transaction 的语义计划权威转为受控 LLM QueryPlan。安全性通过模型前 slotting、模型后 exact validation、配置子集和业务服务最终授权实现，而不是通过保留本地参数 Resolver 实现。
