# [L2_02_00] 单体 Agent 业务查询公共约束、配置与出域详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_02_00` |
| 当前版本 | v1.0 |
| 日期 | 2026-08-21 |
| 权威范围 | Business 公共类型、动作定义、强类型配置、JWT Client、结果映射、用户投影、有限转换、模型出域和 grounding |
| 上位文档 | [`L1_02` v1.0](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) |
| 来源文档 | [L2_02_00 v0.57 归档版](历史文档/2026-08-21-v0-baseline/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) |
| 实施状态 | Business common 与两个域的装配已实现并验证；真实业务结果外部模型出域默认关闭；未生产生效 |

## 2. 阅读导航与变更记录

重点：第 7 节动作/配置、第 8 节执行、第 9 节结果三视图、第 10 节出域/grounding、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立业务公共层稳定基线 | 删除多轮真实 egress/fixture Gate 流水，保留当前类型、ExactDecimal、只收紧配置、三视图和默认关闭边界 |

## 3. 目标与范围

### 3.1 目标

为 Employee/Transaction 提供最小共享执行骨架，同时保持域语法、端点、字段和最终授权独立。公共层必须保证配置不扩权、JWT 原样透传、响应严格归一、用户结果与模型载荷分离，并使任何未知字段或策略冲突失败关闭。

### 3.2 范围内

- 代码绑定 `BusinessActionDefinition`、Protocol 和公共结果类型；
- `BusinessActionSettings`、服务绑定、配置合并/快照/启动校验；
- 用户 JWT HTTP Client、请求/响应大小和状态映射；
- 用户结果投影、有限转换、ExactDecimal wire；
- 模型字段交集、safe facts、Business answer grounding；
- 公共 handler、Provider factory 和第三域扩展测试。

### 3.3 范围外与不负责

- Employee/Transaction 具体 Resolver、DTO、端点、字段目录；
- 业务角色判断、行/字段授权和业务数据真相；
- DeepSeek transport/Prompt、公共 Core/HTTP；
- 动态 Adapter、聚合、写入、工作流、重试/熔断或策略平台。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-BQCOM-001` | 独立域定义通过公共 Protocol 接入，Core 不感知域类型 |
| `REQ-BQCOM-002` | 强类型配置只能启停/收紧代码动作、字段、条件和边界 |
| `REQ-BQCOM-003` | 原始用户 JWT 透传，业务服务最终授权，401/403/无结果可区分 |
| `REQ-BQCOM-004` | 用户结果与模型 safe facts 分离，模型字段默认拒绝且 grounded |
| `REQ-BQCOM-005` | Decimal wire 精确，不使用 float、字符串金额或隐式舍入 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-BQCOM-001` | `L0_00 SA-C-003～014/020/022` |
| `CON-BQCOM-002` | `L1_02`：两个独立 Adapter、一个动作一个只读公开契约 |
| `CON-BQCOM-003` | `L2_00_01`：Resolver/descriptor/validator/handler ID 对齐且单动作执行 |
| `CON-BQCOM-004` | `L2_00_02`：Business answer 只消费安全 payload，模型不生成参数 |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-BQCOM-001`、`CON-BQCOM-002`、`CON-BQCOM-003` | `DR-BQCOM-001`、`DR-BQCOM-002` | `IMPL-BQCOM-001`、`IMPL-BQCOM-002` | `TEST-BQCOM-001`、`TEST-BQCOM-002` | `VAL-BQCOM-001` |
| `REQ-BQCOM-002`、`CON-BQCOM-001` | `DR-BQCOM-003`、`DR-BQCOM-004` | `IMPL-BQCOM-003` | `TEST-BQCOM-003`、`TEST-BQCOM-004` | `VAL-BQCOM-002` |
| `REQ-BQCOM-003` | `DR-BQCOM-005`、`DR-BQCOM-006`、`DR-BQCOM-007` | `IMPL-BQCOM-004`、`IMPL-BQCOM-005` | `TEST-BQCOM-005`、`TEST-BQCOM-006` | `VAL-BQCOM-003` |
| `REQ-BQCOM-004`、`CON-BQCOM-004` | `DR-BQCOM-008`、`DR-BQCOM-009`、`DR-BQCOM-010` | `IMPL-BQCOM-006`、`IMPL-BQCOM-007` | `TEST-BQCOM-007`、`TEST-BQCOM-008` | `VAL-BQCOM-004` |
| `REQ-BQCOM-005` | `DR-BQCOM-011` | `IMPL-BQCOM-008` | `TEST-BQCOM-009` | `VAL-BQCOM-005` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Domain Provider | 提供本域 definitions + config fragment | 调用顺序和 Core |
| Settings Validator | 合并公共/域配置，验证只收紧并冻结 snapshot | 动态修正无效配置 |
| Bound Handler | 固定 mapper→codec→client→status→normalize→project→egress 顺序 | 域协议细节、角色判断 |
| JWT HTTP Client | 使用 context token 发送有界请求/接收有界响应 | 服务 token、自动重试 |
| User Projector | 构造本地最小用户结果 | 模型字段决定 |
| Egress Projector | 字段交集、转换、safe facts、拒绝 reason | 业务授权、模型调用 |
| Grounding Policy | 验证候选回答只表达 safe facts | 生成回答、改变 facts |
| Wire JSON Encoder | canonical JSON 与 ExactDecimal number | 通用 Core JSON |

依赖方向为 `domain adapters → business common → capability_api/model contracts`；组合根装配 Domain Provider。禁止 common 依赖 Employee/Transaction；禁止 Adapter 绕过 Bound Handler/Client；禁止业务服务依赖 Agent。

公共层只抽取已出现的稳定重复点，域定义仍独立，避免过度设计成动态平台。

## 6. 当前实现基线与最小变更

当前实现已有完整公共 contracts/settings/client/mapping/projection/transforms/egress/grounding/handler/provider/wire JSON，并由 Employee/Transaction 两域使用。默认 `AGENT_BUSINESS_EGRESS_ENABLED=false`；真实 Provider + 本地/stub 模型链可用。

新基线不要求代码修改。真实业务结果外部模型实验不是主链完成前置；未来启用需按域重新验证新鲜输入、字段交集和零泄漏。

## 7. 公共类型、动作定义与配置

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-BQCOM-001` | 每个动作由代码绑定 descriptor、domain、mapper、codec、normalizer、field definitions、status semantics 和 answer mode |
| `DR-BQCOM-002` | Domain Provider 只返回固定 definitions/config fragment；Factory 校验 ID/域唯一性并冻结 support snapshot |
| `DR-BQCOM-003` | 配置只能从代码声明集合取子集并收紧数值上限、timeout、目标 origin 和启用状态 |
| `DR-BQCOM-004` | 未知 key、跨域字段、非法转换、最小用户字段缺失、模型敏感候选或 endpoint 非法均启动失败 |
| `DR-BQCOM-005` | HTTP Client 只接受 `OpaqueUserToken`，精确透传 Bearer；缺失 token 不调用下游 |
| `DR-BQCOM-006` | 业务服务 HTTP 状态按动作固定 semantics 映射，401/403/no-result/technical failure 不混淆 |
| `DR-BQCOM-007` | 响应先按动作 codec 的显式字段 allowlist strict decode/normalize，再构造用户结果；allowlist 外字段或错误类型失败，不做宽松 coercion；被兼容 allowlist 接受但未投影的既有宽字段不得进入用户结果或模型 |
| `DR-BQCOM-008` | 用户结果、模型 safe facts 和授权 wire response 是独立对象 |
| `DR-BQCOM-009` | 模型字段为代码候选∩动作设置∩全局策略，未知/敏感/冲突/转换失败拒绝且模型调用 0 |
| `DR-BQCOM-010` | 候选回答必须经 `BusinessAnswerGroundingPolicy` 验证 protected tokens、fact ID 和规范值 |
| `DR-BQCOM-011` | Decimal 使用 `ExactDecimal` canonical JSON number，不接受 float、字符串金额或舍入 |

### 7.2 `BusinessActionDefinition`

固定字段包括 capability/domain ID、request mapper、wire codec、response normalizer、field definitions、supported constraint dimensions、HTTP status semantics、answer mode。Definition 不包含 URL 字符串、角色白名单、动态类名或脚本。

### 7.3 字段定义

`BusinessFieldDefinition` 固定 field ID、value type、data class、record accessor、是否 code-model candidate、用户/模型允许转换和 enum values。`DataClass.CREDENTIAL_OR_SECRET/FREE_TEXT_SENSITIVE/UNKNOWN` 永远不允许模型候选。

有限类型：boolean、integer、decimal、date、datetime、enum、text、identifier。有限转换：identity scalar、bounded text、mask keep last4、date only、decimal 2、enum code。

### 7.4 配置

`BusinessActionSettings` 只含 enabled、endpoint、timeout、允许约束维度、用户字段、模型字段和两类 transform selection。它不能定义方法/路径/Schema/role。

公共配置默认：egress=false、safe facts≤20、safe payload≤32768 bytes、text≤256 chars、HTTP response≤1MiB、record fields≤32、user result≤256KiB；环境值必须 canonical integer/bool 且只能收紧代码上限。

`BusinessSettingsValidator.validate(global, providers)` 产生含 `snapshot_id` 的冻结 `BusinessConfigurationSnapshot`。任何无效域使该启动剖面失败，不做半有效注册。

## 8. 详细功能与核心处理流程

### 8.1 固定执行顺序

```text
validated domain input
  → request mapper(action settings)
  → wire codec.encode
  → JWT HTTP client.execute(deadline)
  → map HTTP status
  → codec.decode_success
  → normalizer.normalize_success
  → user result projector
  → egress projector
  → CapabilityResult
```

Bound Handler 在每个边界前后检查 deadline/cancellation。一次动作最多一个业务 HTTP 请求，不自动 retry/resume，不回退另一个域。

### 8.2 HTTP 请求/响应

`BusinessHttpRequest` 只允许固定 method/path、有限 headers/body bytes；Client 添加 Authorization，不允许调用方提供认证 header。响应严格限制状态、headers/body bytes；超界即 transport failure。

`map_business_http_status` 把动作定义中的 success/no-result statuses 与 401/403/429/5xx 映射到 `BusinessRecordsResult/BusinessNoResult/BusinessFailureResult` 或有限 transport failure。

### 8.3 事务与一致性边界

本期动作只读；Agent 不开启跨服务事务、不重试、不缓存业务结果。请求中的 definition/settings snapshot 固定；取消或超时后迟到响应不得进入投影/模型。

### 8.4 错误分类与调用方可见语义

公共错误码区分 invalid arguments、unauthenticated、forbidden、no result、invalid response、timeout、rate limited 和 downstream unavailable；请求取消对外映射为 `timeout`，具体取消原因只保留在内部分类。调用方只能看到有限稳定语义，不暴露业务响应正文或传输异常细节。

## 9. 用户结果投影

### 9.1 三视图

| 视图 | 内容 | 生命周期 |
|---|---|---|
| wire response | 业务协议完整受控对象 | decode/normalize 前后请求内 |
| normalized records | 动作定义的领域记录 | 请求内 |
| `BusinessUserResult` | action/domain/config snapshot、coverage、最小字段记录 | 进入 Capability domain result |

`BusinessUserResultProjector.project` 仅处理 settings.user_result_fields，按定义顺序输出。每条记录至少包含动作规定的 required user fields；字段缺失/转换失败是 downstream failure，不能把有记录伪装为 no_result 或空 success。

用户结果转换只允许 field definition 已允许的枚举，不影响业务授权或模型字段。

## 10. 模型出域与 grounding

### 10.1 字段交集与默认拒绝

`BusinessEgressProjector.project` 首先检查 answer mode：structured-only→not_applicable；model-assisted 还要求全局 egress enabled。随后计算：

```text
normalized authorized record fields
∩ definition.model_candidate_by_code
∩ settings.model_fields
∩ GlobalBusinessEgressPolicy allowed data classes/transforms
```

任一未知 field、敏感 data class、transform 不匹配、值非法、字段冲突、safe facts 空/超数或 payload 超字节，返回 `DENIED`，不产生部分 payload。

### 10.2 Safe facts

每项 fact 使用稳定 fact ID、field ID、value type、transform ID 和转换后 JSON 值；不含原始 DTO、标识、JWT、配置或角色。业务文本作为 data，不拼入 system instruction。

### 10.3 Grounding

`BusinessAnswerGroundingPolicy.validate` 要求模型 cited fact IDs 存在且唯一，回答中保护 token 不能来自 safe facts 外部，关键值必须与 fact 的 canonical display 对齐；额外事实、缺失引用、禁止标识或注入文本导致拒绝。拒绝后返回本地结构化结果或固定失败，不返回原模型文本。

## 11. ExactDecimal wire

`ExactDecimal.from_decimal(value)` 只接受 finite `Decimal`，按 canonical plain JSON number token 编码：无指数、无多余正号/前导零、保留业务所需小数，不经过 float。token≤128 bytes。

`BusinessWireJsonEncoder` 递归编码有限 JSON object，深度≤8、collection items≤256；普通字符串使用 JSON escaping，ExactDecimal 写入 number token。该 encoder 只用于业务 wire，不扩大 Core JSON 允许类型。

## 12. 身份、权限、安全与审计

- Adapter 不读取 role；业务服务使用共享 Authority Converter 执行最终授权。
- Client 只透传当前用户 JWT，禁止固定 service token、token 缓存或 header 日志。
- 401→unauthenticated，403→forbidden；授权成功后的结果投影仍不是业务授权点。
- 日志仅记录 request/correlation、domain/action、config snapshot、阶段、状态、计数、出域 disposition/reason 和耗时；禁止 token、参数值、业务正文、safe payload 和原始模型响应。
- 无持久状态/业务数据/数据库事务；Client 与 transport 随 Runtime 生命周期关闭。

## 13. 发布、兼容与回滚

- 每域动作默认可独立 disabled；Business egress 全局默认 false。
- 公开业务契约变化必须同步域 codec、fixtures、Provider tests；配置不能静默兼容。
- 回滚优先禁用单域/egress 并重启；若 common contract 变化，两个 Adapter 和组合根按兼容版本共同回滚。
- 不迁移业务数据，不修改数据库。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-BQCOM-001` | `agent-runtime/src/agent_runtime/business/contracts.py`：definitions/settings/results/Protocols |
| `IMPL-BQCOM-002` | `agent-runtime/src/agent_runtime/business/provider.py`：`BusinessSupportFactory.build` |
| `IMPL-BQCOM-003` | `agent-runtime/src/agent_runtime/business/settings.py`：`BusinessSettingsValidator.validate` |
| `IMPL-BQCOM-004` | `agent-runtime/src/agent_runtime/business/http_client.py`：`UserJwtBusinessHttpClient.execute` |
| `IMPL-BQCOM-005` | `agent-runtime/src/agent_runtime/business/result_mapping.py`、`agent-runtime/src/agent_runtime/business/handler.py` |
| `IMPL-BQCOM-006` | `agent-runtime/src/agent_runtime/business/user_projection.py`、`agent-runtime/src/agent_runtime/business/transforms.py` |
| `IMPL-BQCOM-007` | `agent-runtime/src/agent_runtime/business/egress.py`、`agent-runtime/src/agent_runtime/business/grounding.py` |
| `IMPL-BQCOM-008` | `agent-runtime/src/agent_runtime/business/wire_json.py`：`ExactDecimal`、encoder |

### 14.2 关键签名

```python
class BusinessRequestMapper(Protocol[TInput_contra, TWireRequest_co]):
    def map(self, input: TInput_contra, settings: BusinessActionSettings) -> TWireRequest_co: ...

class BusinessWireCodec(Protocol[TWireRequest_contra, TWireResponse_co]):
    def encode(self, request: TWireRequest_contra) -> BusinessHttpRequest: ...
    def decode_success(
        self,
        *,
        request: TWireRequest_contra,
        response: BoundedBusinessHttpResponse,
    ) -> TWireResponse_co: ...

class BusinessResponseNormalizer(Protocol[TWireResponse_contra, TRecord_co]):
    def normalize_success(self, response: TWireResponse_contra) -> BusinessServiceResult[TRecord_co]: ...

class BusinessHttpClient(Protocol):
    async def execute(
        self,
        *,
        request: BusinessHttpRequest,
        user_token: OpaqueUserToken,
        call_deadline: float,
        cancellation: CancellationSignal,
    ) -> BoundedBusinessHttpResponse: ...
```

## 15. 测试与验证设计

### 15.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-BQCOM-001` | definitions/Protocols/third-domain extension：Business unit/architecture tests |
| `TEST-BQCOM-002` | Provider factory ID/domain/handler registration and snapshot |
| `TEST-BQCOM-003` | config unknown key/subset/bounds/endpoint/min fields：Business settings tests |
| `TEST-BQCOM-004` | invalid field/transform/sensitive candidate/startup fail |
| `TEST-BQCOM-005` | original JWT、no token zero call、timeout/cancel/size：Business HTTP tests |
| `TEST-BQCOM-006` | status mapping、strict decode、no-result 与 user projection |
| `TEST-BQCOM-007` | field intersection/default deny/zero call：`employee_egress_field_matrix.json` 和域矩阵 |
| `TEST-BQCOM-008` | injection/protected tokens/fact ID/value grounding |
| `TEST-BQCOM-009` | ExactDecimal canonical number、no float/string/rounding、深度/大小 |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-BQCOM-001` | common contracts/provider/第三域扩展测试通过，Core 无域分支 |
| `VAL-BQCOM-002` | 配置只收紧与启动失败矩阵通过 |
| `VAL-BQCOM-003` | fake domain server JWT/HTTP/status/取消/响应大小测试通过 |
| `VAL-BQCOM-004` | `TEST-BQCOM-007/008/012/013` 语义对应的出域/grounding/零调用回归通过 |
| `VAL-BQCOM-005` | Decimal 精度与 canonical wire、strict mypy、compileall、全量 Business 非 live 回归通过 |

## 16. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| common 演化为动态平台 | 配置 URL/method/schema/script | 代码 definition + strict settings | 否 |
| 本地投影代替授权 | Adapter 根据 role/字段允许 | 原 JWT + 业务最终授权 | 否 |
| 宽 DTO/额外字段泄漏 | 动作 codec 未限定兼容字段或将未投影字段直接出域 | 显式响应 allowlist + 三视图 | 否 |
| Decimal 失真 | float/string/rounding | ExactDecimal canonical number | 否 |
| 真实业务数据外发 | 全局/域 egress 误开 | 默认 false + 分域新鲜验证 | 否；真实出域不在本基线实施范围 |
| 重试导致重复/预算漂移 | transport 自动 retry | 当前 retry=0；未来另行设计 | 不阻塞当前依据 |

## 17. 实施依据

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前 v1.0 可作为 Business common、两个域公共装配和代码评审依据 |
| 当前允许实施范围 | 公共类型/配置/JWT client/handler/投影/出域/grounding/ExactDecimal 与非 live 测试 |
| 当前禁止动作 | 新业务动作/接口、角色判断、真实业务结果外发、默认/生产启用、重试熔断 |
| 回滚单位 | Business common + 两域 definitions/settings/组合根的兼容快照 |

## 18. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 公共/域边界、稳定契约、来源和追踪一致 | Passed |
| 内审 2 | 权限、出域、ExactDecimal、错误分类和状态一致 | Passed |
| 内审 3 | 真实落点、测试、扩展、链接和可读性检查通过 | Passed |
| 独立评审 | `REV-L2-02-00-001～003` 已修复；公共 Protocol、失败语义、响应 allowlist、配置、出域与 Decimal 边界复核通过 | Passed |

- 当前版本：v1.0。
- 文档状态：Approved。
- 新版本不继承旧版 fixture/Gate/真实试验流水；仅保留当前稳定契约和保护条件。
