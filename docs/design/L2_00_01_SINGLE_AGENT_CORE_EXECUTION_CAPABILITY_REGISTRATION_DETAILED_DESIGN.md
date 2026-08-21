# [L2_00_01] 单体 Agent 核心执行、动作解析与能力注册详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_00_01` |
| 当前版本 | v1.0 |
| 日期 | 2026-08-21 |
| 权威范围 | Capability 公共契约、注册冻结、本地/模型动作解析、Core 单动作执行、LangGraph 状态与固定终态 |
| 上位文档 | [`L1_00` v1.0](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) |
| 来源文档 | [L2_00_01 v0.11 归档版](历史文档/2026-08-21-v0-baseline/L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) |
| 实施状态 | 当前代码已实现并通过单元、契约、组合根和系统 E2E；未生产生效 |

## 2. 阅读导航与变更记录

重点：第 7 节公共契约、第 8 节注册冻结、第 9 节动作解析、第 10 节 Core 流程、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立 Core 当前稳定基线 | 删除历史实现/评审流水，合并 Provider-neutral ID、Resolver、latch、状态与失败语义 |

## 3. 目标与范围

### 3.1 目标

让任意查询能力在不修改 Core 的前提下以强类型注册项接入；每个请求只允许一个最终候选和一次能力提交，模型输出永远不能直接执行，所有失败均映射为有限公共终态。

### 3.2 范围内

- Capability descriptor、argument schema、handler、result 和 execution context；
- 注册候选校验、唯一性、快照和冻结 Registry；
- Provider-neutral LocalActionResolver、ID-only model selection 和 Hybrid 裁决；
- LangGraph 请求状态、节点顺序和 Core 单动作 latch；
- 截止时间、取消、异常分类、不可变 JSON 和组合根校验。

### 3.3 范围外与不负责

- Knowledge/Employee/Transaction 的域语法、参数、Provider 和字段；
- 模型供应商 HTTP、Prompt 和出域策略；
- Spring/FastAPI 传输契约；
- 重试、熔断、缓存、跨请求状态、持久工作流和 Multi-Agent。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-CORE-001` | 能力通过 descriptor+validator+handler 注册，不向 Core 增加域分支 |
| `REQ-CORE-002` | 本地 Resolver 优先，模型只返回 ID，最终参数不来自模型 |
| `REQ-CORE-003` | 每请求最多一次动作 claim 和一次 handler 调用 |
| `REQ-CORE-004` | 统一状态、失败、截止、取消和模型出域决定可验证 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-CORE-001` | `L0_00 SA-C-002/005/010/014/022` |
| `CON-CORE-002` | `L1_00`：LangGraph 唯一编排，Core 确定性执行 |
| `CON-CORE-003` | 所有外部输入、注册项和结果均视为不可信并失败关闭 |
| `CON-CORE-004` | 公共契约不得包含领域、框架或模型供应商类型 |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-CORE-001`、`CON-CORE-001`、`CON-CORE-004` | `DR-CORE-001`、`DR-CORE-002`、`DR-CORE-003` | `IMPL-CORE-001`、`IMPL-CORE-002` | `TEST-CORE-001`、`TEST-CORE-002` | `VAL-CORE-001` |
| `REQ-CORE-002`、`CON-CORE-003` | `DR-CORE-004`、`DR-CORE-005`、`DR-CORE-006` | `IMPL-CORE-003`、`IMPL-CORE-004` | `TEST-CORE-003`、`TEST-CORE-004` | `VAL-CORE-002` |
| `REQ-CORE-003`、`CON-CORE-002` | `DR-CORE-007`、`DR-CORE-008` | `IMPL-CORE-005`、`IMPL-CORE-006` | `TEST-CORE-005`、`TEST-CORE-006` | `VAL-CORE-003` |
| `REQ-CORE-004` | `DR-CORE-009`、`DR-CORE-010`、`DR-CORE-011` | `IMPL-CORE-007`、`IMPL-CORE-008` | `TEST-CORE-007`、`TEST-CORE-008` | `VAL-CORE-004` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 明确不负责 |
|---|---|---|
| Capability API | 稳定公共类型、JSON、状态和 Protocol | 注册存储、调用顺序、领域参数 |
| Local Resolver | 从问题确定性形成单能力参数候选 | 外部调用、模型回退、最终执行 |
| Hybrid selection | 汇总本地结果、必要时调用 ID-only selector、裁决唯一性 | 生成业务参数、执行 handler |
| Registry | 校验候选、建立快照、解析已注册能力 | 请求状态和调用计数 |
| Execution Core | 校验 context/candidate/arguments、claim、预算内调用、结果校验 | 领域流程和模型生成 |
| LangGraph nodes | 固定选择→执行→回答/固定终态顺序 | 修改领域状态、第二动作 |
| Composition Root | 装配 providers/resolvers/model/graph，执行全局一致性校验 | 请求级语义决策 |

依赖方向为 `domain implementations → capability_api ← core/graph`；组合根可依赖全部实现。禁止 `capability_api` 依赖 LangGraph、HTTP、领域或供应商；禁止 Core 反向依赖具体能力。

该边界以不变契约保持低耦合；不引入服务定位器、动态 import 或通用规则引擎。

## 6. 当前实现基线与最小变更

当前代码已具备：不可变公共 dataclass、canonical JSON、冻结 Registry、请求级 latch、Hybrid selection、本地 Resolver 列表、ID-only selector、LangGraph 节点、组合根对齐校验、Runtime `ainvoke` 和关闭生命周期。

现状与设计一致，不要求代码变更。新增能力只增加实现与组合根注册；若需要第二动作、聚合或重试，必须先修改上位架构而非扩展当前 Core 隐式行为。

## 7. 公共能力契约设计

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-CORE-001` | `CapabilityDescriptor` 使用稳定 ID、kind、版本、模型安全描述/aliases 和受限 JSON Schema |
| `DR-CORE-002` | 注册项必须同时提供 descriptor、validator、handler；三者不可运行时替换 |
| `DR-CORE-003` | Registry 在启动期校验并冻结；重复 ID、禁用/启用不一致或可变输入使启动失败 |
| `DR-CORE-004` | Local Resolver 只返回 `matched/no_match/invalid` 与本域参数，不执行调用 |
| `DR-CORE-005` | 模型 selection 只返回 exact capability ID 或 no-match，不返回 arguments |
| `DR-CORE-006` | Hybrid 仅在本地无匹配时调用模型；多本地匹配、ID 不对齐或需要参数的 model-only 选择失败关闭 |
| `DR-CORE-007` | `ActionExecutionLatch` 在 validator/handler 前 claim；同请求第二次 claim 永远拒绝 |
| `DR-CORE-008` | Core 固定顺序为 context→candidate→registry→claim→argument validate→budget/cancel→handler→result validate→finish |
| `DR-CORE-009` | 统一状态和 failure source/code 必须满足组合不变量；错误不得携带原异常正文 |
| `DR-CORE-010` | 取消、截止或 shutdown 与 handler 竞争；迟到结果丢弃且任务被 join |
| `DR-CORE-011` | Graph 只保存当前请求状态；能力结果决定 answer 或 fixed 路径，不允许循环回执行节点 |

### 7.2 Descriptor 与 JSON Schema

`CapabilityDescriptor` 的关键字段为 `capability_id`、`api_version`、`kind`、`display_name`、`description`、`aliases` 和 `argument_schema`。ID 采用小写点分域格式；版本为正整数；展示文本和 aliases 有界且不含敏感值。启停状态由 `CapabilityRegistrationCandidate.enabled` 持有，不得复制进 Descriptor。

Core JSON 只允许 `null/bool/int/有限 Decimal/str/list/object` 的受控子集，拒绝 float、非字符串 key、深度/节点/字符串超界和循环引用。`freeze_json_object` 深冻结输入，`canonical_json_bytes` 提供稳定比较；它不是业务 wire encoder，ExactDecimal 由 Business L2 单独治理。

Argument Schema 只支持本期有限 JSON Schema 关键字；不允许 `$ref`、自定义执行关键字或宽松 additional properties。

### 7.3 Execution context

`CapabilityExecutionContext` 包含 request/correlation ID、原始问题、用户 subject、`OpaqueUserToken`、单调时钟 deadline 和 cancellation signal。它不包含角色白名单、服务 token、模型 Client 或跨请求 session。

### 7.4 Result

`CapabilityResult` 包含 `status`、`domain_result?`、`answer_text?`、`failure?`、`model_egress`。成功/无结果不得带 failure；失败必须带有限 `FailureDetail`；领域结果必须是不可变公共 JSON object。

`ModelEgressResult` 明确 `not_applicable/allowed/denied`，并把领域是否允许模型调用与 Core 终态分离。

## 8. 能力注册与冻结

1. 各 Provider 返回固定 tuple 的 `CapabilityRegistrationCandidate`。
2. Builder 按 capability ID 排序并逐个校验 descriptor、schema、validator、handler 和 enabled 状态。
3. 对 descriptor canonical JSON 计算稳定 snapshot material；形成单一 registry snapshot ID。
4. `FrozenCapabilityRegistry` 只暴露有序 descriptors、`resolve()`、`contains()`。
5. Runtime ready 后不得注册、移除、替换或修改能力。

Registry 不持久化，也不从远端发现能力。配置变更要求重启；回滚恢复上一组代码+配置并重建快照。

## 9. 动作解析

### 9.1 本地 Resolver

```text
每个 resolver.resolve(question)
  → matched(candidate) | no_match | invalid(reason)
```

- `invalid` 优先终止，不能当作 `no_match`。
- 恰好一个 `matched` 才产生候选；两个及以上匹配为跨域歧义。
- 候选 capability ID 必须等于 resolver 声明 ID、已注册 ID 和 validator 目标。
- Local Resolver 不访问网络、不读取模型、不改变配置。

### 9.2 ID-only 模型选择

只有全部本地 Resolver `no_match` 时，Hybrid 节点才把模型安全 catalog 和经输入闸门允许的问题交给 selector。模型返回值严格解码为 exact JSON ID/no-match；ID 未注册、未启用、重复或能力需要非空参数而模型无本地参数来源时拒绝。

模型调用不能改变本地 `invalid`、多匹配或能力参数。最终 `ActionCandidate` 始终再次通过 Core validator。

## 10. 核心处理流程

### 10.1 单动作执行

```text
ActionCandidate
  → validate context
  → validate candidate shape
  → registry.resolve
  → latch.claim(capability_id)
  → registered.validate(arguments)
  → calculate remaining budget / cancellation race
  → handler.handle(validated, context)
  → validate capability result
  → latch.finish(completion)
```

claim 位于 handler 之前，因此 validator 异常后也不可用另一动作回退。一次请求中 handler 实际调用次数为 0 或 1。

### 10.2 截止、取消和并发一致性

- 每请求拥有独立 latch、context 和 graph state；Registry/配置只读共享。
- Core 使用单调时钟计算剩余预算，并以 handler、cancel signal、shutdown 三方竞争。
- 超时/取消后取消并 join handler task；迟到 success 不得覆盖终态。
- 本期查询无重试、重放、补偿或跨请求幂等承诺；因此无数据库事务。

### 10.3 Graph 固定路径

```text
select_action
  ├─ selected → execute_capability
  │               ├─ model egress allowed → generate_answer
  │               └─ other → finalize_without_model
  └─ unsupported/invalid/failure → end
```

Graph 不循环到 select/execute。回答节点不执行能力；模型失败只能影响回答，不得改写已完成的领域调用结论。

## 11. 失败类型、错误分类和调用方可见语义

| 场景 | 状态/错误码原则 | handler 调用 |
|---|---|---:|
| 无匹配能力 | `unsupported` | 0 |
| 本地歧义/非法、模型非法 ID | `invalid_argument` 或受控 `unsupported` | 0 |
| 候选未注册/禁用/参数非法 | `invalid_argument` | 0 |
| 身份/context 非法 | `unauthenticated` 或 `invalid_argument` | 0 |
| 第二次 claim | `internal_failure`，记录不含输入的诊断 fingerprint | 0（第二次） |
| 截止耗尽/请求取消 | 公共状态 `timeout` | 0 或 1，迟到结果无效 |
| Runtime shutdown/外层任务取消 | 内部 latch 完成值 `runtime_cancelled`，随后传播 `CancelledError`；不生成公共 `CapabilityResult` | 0 或 1 |
| handler 已知失败 | 保留领域映射后的有限状态/failure | 1 |
| handler 未知异常/结果违反契约 | `internal_failure` | 1 |

异常类名、堆栈、原消息和用户输入不进入公共结果；日志使用 rule code、stage 和不可逆 fingerprint。

## 12. 权限、安全、审计与状态生命周期

- Core 只要求有效 user context，不做 Employee/Transaction 角色判断或 Knowledge 文档授权。
- `OpaqueUserToken` 只有下游 Client 可以显式揭示，禁止序列化、哈希值展示和普通 repr。
- 模型输出、领域结果和 handler 返回均在信任边界后校验。
- 日志字段仅 request/correlation ID、capability ID、snapshot、状态、stage、rule code、耗时；不记录问题、arguments、token 或 domain_result。
- 请求级 state、latch 和 token wrapper 在请求结束后释放；Registry 与配置随 Runtime 生命周期存在，无数据迁移。

## 13. 配置、容量、发布与回滚

`CoreRuntimeSettings` 固定公共 JSON 深度/节点/字符串、最大 action 数、最小时限余量等边界；任何非整数、布尔伪装整数或越界值启动失败。数据生命周期仅覆盖请求级 `AgentState`，请求结束即释放；本设计无持久数据迁移。

发布时先构建全部 Provider、Resolver、Model 组件和 Registry，再执行 ID/覆盖/唯一性检查并编译 Graph；完成后 Runtime 才 ready。回滚以整个 Runtime 代码+配置快照为单位，不在运行中变更 Registry。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-CORE-001` | `agent-runtime/src/agent_runtime/capability_api/contracts.py`：Descriptor、Context、Result、Protocols、JSON 校验 |
| `IMPL-CORE-002` | `agent-runtime/src/agent_runtime/core/registry.py`：`CapabilityRegistryBuilder.build(...) -> FrozenCapabilityRegistry` |
| `IMPL-CORE-003` | `agent-runtime/src/agent_runtime/capability_api/action_resolution.py`：`LocalActionResolver.resolve(question)` |
| `IMPL-CORE-004` | `agent-runtime/src/agent_runtime/graph/action_resolution.py`：`HybridActionSelectionNode.__call__(...)` |
| `IMPL-CORE-005` | `agent-runtime/src/agent_runtime/core/execution.py`：`ActionExecutionLatch` |
| `IMPL-CORE-006` | `agent-runtime/src/agent_runtime/core/execution.py`：`CapabilityExecutionCore.execute(...)` |
| `IMPL-CORE-007` | `agent-runtime/src/agent_runtime/graph/state.py`、`agent-runtime/src/agent_runtime/graph/nodes.py` |
| `IMPL-CORE-008` | `agent-runtime/src/agent_runtime/bootstrap.py`：`RuntimeCompositionRoot.build(...)`、resolver 对齐校验 |

### 14.2 关键签名

```python
class LocalActionResolver(Protocol):
    @property
    def capability_id(self) -> str: ...
    def resolve(self, question: str) -> LocalActionResolution: ...

class CapabilityArgumentValidator(Protocol[TValidated_co]):
    def validate(self, arguments: JsonObject) -> TValidated_co: ...

class CapabilityHandler(Protocol[THandled_contra]):
    async def handle(
        self,
        input: THandled_contra,
        context: CapabilityExecutionContext,
    ) -> CapabilityResult: ...

class CapabilityRegistrationProvider(Protocol):
    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]: ...
```

`CapabilityExecutionCore.execute(candidate, scope) -> CapabilityResult` 是唯一 handler 执行入口；具体完整类型以当前源码签名为准。普通私有 helper 不作为跨模块契约。

## 15. 测试与验证设计

### 15.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-CORE-001` | 公共类型、JSON/schema、result 不变量：`agent-runtime/tests/unit/capability_api` |
| `TEST-CORE-002` | Registry 重复/无效/冻结/快照：`agent-runtime/tests/unit/core/test_registry.py` |
| `TEST-CORE-003` | Local Resolver contract：`agent-runtime/tests/contract/test_local_action_resolver_contract.py` |
| `TEST-CORE-004` | Hybrid 唯一性、ID-only、模型零调用和覆盖：`agent-runtime/tests/unit/graph/test_hybrid_action_resolution.py` |
| `TEST-CORE-005` | latch、第二动作、validator 顺序：`agent-runtime/tests/unit/core/test_execution.py` |
| `TEST-CORE-006` | timeout/cancel/shutdown/迟到任务：`agent-runtime/tests/unit/core/test_execution.py` |
| `TEST-CORE-007` | graph route 和固定终态：`agent-runtime/tests/unit/graph` |
| `TEST-CORE-008` | 组合根唯一性、ID 对齐和模拟扩展：`agent-runtime/tests/unit/test_action_resolution_composition.py`、`agent-runtime/tests/architecture/test_extensibility.py` |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-CORE-001` | Capability/Registry 定向单元与契约测试通过 |
| `VAL-CORE-002` | `VAL-CORE-006`：Provider-neutral ID、local-first、无模型参数和歧义失败关闭通过 |
| `VAL-CORE-003` | `VAL-CORE-007`：strict mypy 覆盖 registry/execution/action resolution，且 latch/cancel 测试通过 |
| `VAL-CORE-004` | 全量非 live pytest、compileall、依赖方向和系统 stub E2E 通过 |

## 16. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| Core 域分支 | 按 capability ID 写 if/else | handler/registry 多态与依赖测试 | 否 |
| 模型直接执行 | 模型返回 arguments/URL | ID-only decoder + local parameter source | 否 |
| 第二动作 | 失败后回退另一 handler | claim-before-validate latch + 无图循环 | 否 |
| 可变注册 | 运行时修改 descriptor | 深冻结、snapshot、ready 前构建 | 否 |
| 新增聚合/工作流 | 试图复用当前 Core | 必须修改上位设计和状态模型 | 需授权但不阻塞当前依据 |

## 17. 实施依据

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前 v1.0 可作为 Core/Registry/Graph 切片实现与代码评审依据 |
| 当前允许实施范围 | Capability API、Registry、Resolver/Hybrid、单动作 Core、Graph、组合根与非 live 测试 |
| 当前禁止动作 | 领域参数变更、公共 HTTP、真实模型调用、第二动作、重试和持久化工作流 |
| 回滚单位 | Runtime Core + Registry + Graph + 组合根按同一兼容快照回滚 |

## 18. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 契约、责任、来源和追踪一致 | Passed |
| 内审 2 | 状态、失败、安全、并发和生命周期一致 | Passed |
| 内审 3 | 真实落点、测试、扩展与可读性检查通过 | Passed |
| 独立评审 | `REV-L2-00-01-001/002` 已修复；公共类型、取消语义、实现落点与上位约束复核通过 | Passed |

- 当前版本：v1.0。
- 文档状态：Approved。
- 新版本不继承旧版评审和实现流水；历史文档仅作为来源。
