# [L2_02_01] 单体 Agent Employee Adapter 与授权详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_02_01` |
| 当前版本 | v1.0 |
| 日期 | 2026-08-21 |
| 权威范围 | `employee.detail` 的参数、映射、wire、响应、字段投影、业务域授权与验证 |
| 上位文档 | [`L1_02` v1.0](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) |
| 公共下位依赖 | [`L2_02_00` v1.0](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) |
| 安全依赖 | [`L2_00_03` v1.0](L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) |
| 来源文档 | [L2_02_01 v0.49 归档版](历史文档/2026-08-21-v0-baseline/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) |
| 实施状态 | Adapter、领域最终授权与非 live 测试已实现；真实业务结果外部模型出域默认关闭 |

## 2. 阅读导航与变更记录

重点阅读：第 6 节当前基线、第 7 节动作契约、第 8 节 wire 与响应、第 9 节字段边界、第 10 节授权、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立 Employee 当前稳定基线 | 删除历史 Gate、临时数据诊断和候选运行流水，只保留现行代码契约、安全边界、验证入口及来源 |

## 3. 目标与范围

### 3.1 目标

把单个员工详情查询映射为对 `employee-service` 现有只读接口的一次受控调用。Adapter 负责协议适配、参数与响应收紧、字段投影；`employee-service` 负责最终身份与角色授权。

### 3.2 范围内

- `employee.detail` descriptor、参数 Schema 与本地 Resolver；
- `GET /employees/{idCardNo}` 的 path 编码、strict decode 与 normalizer；
- 六个 Agent 字段及其用户/模型可见边界；
- 只收紧配置、Provider 装配和公共 Business handler 接入；
- `ROLE_ADMIN`、`ROLE_VIEWER` 的业务域最终授权；
- fake、契约、架构边界和业务服务安全测试。

### 3.3 范围外与不负责

- 员工列表、计数、ES、写入、变更申请、工作流和聚合；
- 新 Employee endpoint、窄 DTO 或业务字段语义变更；
- 在 Adapter 解析角色或使用服务身份代替用户身份；
- 将身份证、工号、姓名、邮箱等字段发送至外部模型；
- 真实 Employee 数据的持续测试资产和默认启用的真实模型出域。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-EMP-001` | 只注册 `employee.detail`，只调用既有详情接口且最多一次请求 |
| `REQ-EMP-002` | 只接受一个规范化员工标识，拒绝路径、查询和附加动作注入 |
| `REQ-EMP-003` | 严格校验 Employee 响应并输出受控六字段用户视图 |
| `REQ-EMP-004` | 原始用户 JWT 透传，由业务服务对 ADMIN/VIEWER 最终授权 |
| `REQ-EMP-005` | 模型字段默认空；显式启用时最多允许职位、工作地且失败关闭 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-EMP-001` | `L0_00`：业务服务最终授权，外部模型字段默认拒绝 |
| `CON-EMP-002` | `L1_02`：每域每动作强类型 Adapter，不得扩大业务服务契约 |
| `CON-EMP-003` | `L2_02_00`：JWT Client、配置只收紧、三视图和 grounding |
| `CON-EMP-004` | `L2_00_03`：role claim 只映射 `ROLE_ADMIN`、`ROLE_VIEWER` |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-EMP-001`、`CON-EMP-002` | `DR-EMP-001`、`DR-EMP-002` | `IMPL-EMP-001`、`IMPL-EMP-002` | `TEST-EMP-001`、`TEST-EMP-002` | `VAL-EMP-001` |
| `REQ-EMP-002` | `DR-EMP-003`、`DR-EMP-004` | `IMPL-EMP-003` | `TEST-EMP-003`、`TEST-EMP-004` | `VAL-EMP-002` |
| `REQ-EMP-003`、`CON-EMP-003` | `DR-EMP-005`、`DR-EMP-006` | `IMPL-EMP-004`、`IMPL-EMP-005` | `TEST-EMP-005`、`TEST-EMP-006` | `VAL-EMP-003` |
| `REQ-EMP-004`、`CON-EMP-001`、`CON-EMP-004` | `DR-EMP-007`、`DR-EMP-008` | `IMPL-EMP-006`、`IMPL-EMP-007` | `TEST-EMP-007`、`TEST-EMP-008` | `VAL-EMP-004` |
| `REQ-EMP-005` | `DR-EMP-009`、`DR-EMP-010` | `IMPL-EMP-008` | `TEST-EMP-009`、`TEST-EMP-010` | `VAL-EMP-005` |

## 5. 责任分解、内聚与责任边界

| 组件 | 负责 | 不负责 |
|---|---|---|
| Employee Adapter | 参数、固定 path、wire、normalization、字段目录、Provider | 业务角色判断、Employee 数据真相 |
| Business common | JWT Client、状态映射、用户投影、模型交集、grounding | Employee 语法和 DTO |
| `employee-service` | 详情查询、最终身份/角色授权、响应真相 | Agent 编排和模型策略 |
| Authority Converter | role claim 到 Spring Authority | 动作权限和行/字段权限 |

Employee 语法、wire 和字段保持在本域内聚；跨域只复用 Business common 的稳定契约。依赖方向为 `employee adapter → business common → capability/model contracts`。禁止反向依赖 Agent；禁止 Adapter 直连数据库、调用其他 Employee endpoint 或绕过公共 handler。

## 6. 当前实现基线与最小变更

当前代码已包含 descriptor、local resolver、argument validator、request mapper、wire codec、normalizer、field definitions、settings、provider 和业务域 SecurityFilterChain/guard。默认动作 `enabled=false`，默认模型字段为空。

本基线不要求新建接口或修改响应 DTO。归档文档中的 fixture、数据库诊断和多次 live candidate 仅作为历史审计，不是生产结构或后续实现前置。

## 7. 动作与参数契约

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-EMP-001` | capability ID 固定 `employee.detail`，domain 固定 `employee`，service key 固定 `employee-service` |
| `DR-EMP-002` | 每次执行最多一个 GET；不允许列表、计数、ES、写入、工作流或其他 Employee 动作 |
| `DR-EMP-003` | 参数 object 必须且仅含 `employee_identifier`，NFC+trim 后 5～64 字符、UTF-8≤192 bytes |
| `DR-EMP-004` | 标识不得含空白、控制/双向控制字符、`/\\%?#`；path segment 使用严格 percent encoding |
| `DR-EMP-005` | 响应必须为 2xx 非 204、`application/json`、≤65536 bytes；重复 key/非法常量失败 |
| `DR-EMP-006` | 响应至少含六个目标字段，`idCardNo` 必须等于请求标识；字段类型/长度/Unicode 不合格即失败 |
| `DR-EMP-007` | Adapter 只使用 `OpaqueUserToken`，不读取/转换角色，不使用 service token |
| `DR-EMP-008` | `employee-service` 在 filter chain 和 controller guard 两处收紧详情读取为 ADMIN/VIEWER 用户 token |
| `DR-EMP-009` | 用户字段固定六项；身份证和工号 mask keep last4，文本 bounded text |
| `DR-EMP-010` | 模型候选仅 `position/work_base_si`；默认为空，未知/敏感/冲突/缺失导致零模型调用 |

### 7.2 Capability Descriptor

```json
{
  "capability_id": "employee.detail",
  "api_version": 1,
  "kind": "query",
  "argument_schema": {
    "type": "object",
    "properties": {
      "employee_identifier": {"type": "string", "minLength": 5, "maxLength": 64}
    },
    "required": ["employee_identifier"],
    "additionalProperties": false
  }
}
```

`employee_identifier` 是业务服务已有 path 标识，不在 Agent 中断言其为身份证或工号，也不写日志。Resolver 只识别有限中文“单员工详情 + 标识”句式；模型即使选中动作也只返回 capability ID，不生成参数，参数仍由本地 Resolver 产生。

### 7.3 配置

前缀固定 `AGENT_EMPLOYEE_DETAIL_`：

| Key | 默认值 | 边界 |
|---|---:|---|
| `ENABLED` | `false` | canonical boolean |
| `TIMEOUT_MS` | `2000` | 100～3000 |
| `MAX_RESULT_COUNT` | `1` | 只能为 1 |
| `USER_FIELDS` | 六字段 | 必须含 `employee_id_masked,chinese_name` |
| `MODEL_FIELDS` | 空 | 只能是 `position,work_base_si` 且为 user fields 子集 |
| `USER_TRANSFORMS` | 固定安全转换 | 不可替换 |
| `MODEL_TRANSFORMS` | bounded text | 与选中模型字段一一对应 |

未知同前缀 key、重复字段、非 canonical 数字/布尔、越界、扩大代码候选或缺失最小字段均启动失败。

## 8. Wire、响应与失败语义

### 8.1 请求

```text
GET /employees/{percent-encoded employee_identifier}
Authorization: Bearer <original user JWT>
body: none
```

请求只能由 `EmployeeDetailWireCodec.encode` 生成。Adapter 不允许 caller 自定义 method、origin、path、query 或 Authorization header。

### 8.2 成功响应

| wire 字段 | Agent 字段 | 约束 |
|---|---|---|
| `idCardNo` | `id_card_no` | 必填，5～64，与请求相等 |
| `memberNo` | `member_no` | 可空，非空时 5～64 |
| `chineseName` | `chinese_name` | 必填，1～128 |
| `publicEmail` | `public_email` | 可空，非空时 1～254 |
| `position` | `position` | 可空，非空时 1～256 |
| `workBaseSi` | `work_base_si` | 可空，非空时 1～256 |

全部字符串 NFC 规范化并拒绝控制/双向控制字符。wire 可含业务 DTO 其他字段，但 Agent 只读取六项；额外字段不得自动进入用户或模型结果。

### 8.3 归一、错误分类与调用方可见语义

详情成功归一为一条 `EmployeeDetailRecord`，coverage=`returned_count=1,truncated=false,total_count=1`。当前动作仅声明 HTTP 400 映射 `invalid_argument`，包括既有 Employee 服务的“不存在员工”语义；未声明 404 为 `no_result`，因此 404 按不可用失败处理。401、403、429、5xx、超时、取消、无效 content-type/body/JSON 均进入公共有限失败语义，禁止返回部分 Employee 数据。

## 9. 用户结果与模型字段

| field ID | 数据分类 | 用户可见 | 用户转换 | 模型候选 |
|---|---|---:|---|---:|
| `employee_id_masked` | personal identifier | 是 | mask keep last4 | 否 |
| `member_no_masked` | employee identifier | 是 | mask keep last4 | 否 |
| `chinese_name` | personal identifier | 是 | bounded text | 否 |
| `public_email` | contact | 是 | bounded text | 否 |
| `position` | business internal | 是 | bounded text | 是 |
| `work_base_si` | business internal | 是 | bounded text | 是 |

用户结果最小字段是 `employee_id_masked,chinese_name`。启用模型出域时若 `position/work_base_si` 均为空、含注入文本、转换失败或策略冲突，拒绝且模型调用为 0。

身份证、工号、姓名、邮箱、JWT、原始响应和问题中的具体标识永不进入模型。候选回答必须通过公共 grounding；拒绝时仅返回本地受控结果或固定失败。

## 10. 身份、权限与审计设计

```text
user JWT → agent-service → agent-runtime OpaqueUserToken
  → employee-service Resource Server
  → userRoleJwtAuthenticationConverter
  → detail SecurityFilterChain
  → CapabilityAccessGuard.requireEmployeeRead
```

`EmployeeDetailSecurityConfiguration` 只匹配 `GET /employees/{single-segment}`，排除 `count`、`es` 和多段路径；要求 `ROLE_ADMIN` 或 `ROLE_VIEWER`。Controller 再验证用户 token 与角色。其他 Employee endpoint 沿用既有 fallback，不因本动作扩大授权。

| 主体 | 预期 |
|---|---|
| 用户 + ADMIN/VIEWER | 允许进入业务查询 |
| 用户 + 其他/空 role | 403 |
| service token | 401 / `invalid_token` |
| missing/malformed/expired JWT | 401/认证失败 |

`dylan` 是用户标识而非角色；其角色归属由 auth-service 数据决定，不硬编码在 Adapter 或 Employee 服务。

## 11. 核心流程

```text
question → local resolver / ID-only selector
→ deterministic resolver validates employee_identifier
→ argument validator → mapper → fixed GET codec
→ JWT HTTP client(one request) → business final authorization
→ strict decode + normalize → user projection
→ optional default-off egress intersection + grounding
→ CapabilityResult
```

请求前后检查 deadline/cancellation；无自动 retry/resume。失败后不能回退到列表、数据库或其他能力。

## 12. 安全、日志与数据生命周期

- 日志只允许 correlation/action/config snapshot、阶段、HTTP 类别、计数与有限 reason；禁止标识、JWT、Employee 字段值、完整 path、原始响应和模型文本。
- 用户标识只驻留请求内存；Adapter 不持久化、不缓存、不写 evidence。
- real/live 验证如需合成员工数据，必须独立授权、精确创建/清理并限于测试范围；不构成生产设计依赖。
- 取消、超时或失败后的迟到响应不得投影或进入模型。
- 回滚通过禁用动作或清空模型字段；不修改数据库。

## 13. 并发、兼容与扩展

- 定义和配置 snapshot 不可变，可并发复用；JWT、标识、响应均为请求级对象。
- 事务边界仅在 `employee-service` 的只读详情查询内；Agent 不建立跨服务事务。请求与响应按 execution context 关联，超时/取消后的迟到结果不得提交，保证请求级一致性。
- 现有详情 endpoint 与 DTO 是兼容权威；如字段或错误语义改变，先核实调用方并同步 codec/fixture。
- 新 Employee 动作必须新增 definition/codec/normalizer，不向 `employee.detail` 追加分支。
- 真实模型出域不是详情查询成功的必要条件，保持默认关闭和独立验证。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-EMP-001` | `agent-runtime/src/agent_runtime/adapters/employee/definition.py`：`employee_detail_definition()` |
| `IMPL-EMP-002` | `agent-runtime/src/agent_runtime/adapters/employee/provider.py`：`EmployeeDomainProvider` |
| `IMPL-EMP-003` | `agent-runtime/src/agent_runtime/adapters/employee/action_resolver.py`、`agent-runtime/src/agent_runtime/adapters/employee/codec.py`：Resolver、`EmployeeDetailArgumentValidator.validate()` |
| `IMPL-EMP-004` | `agent-runtime/src/agent_runtime/adapters/employee/contracts.py`、`agent-runtime/src/agent_runtime/adapters/employee/normalizer.py` |
| `IMPL-EMP-005` | `agent-runtime/src/agent_runtime/adapters/employee/codec.py`：`EmployeeDetailWireCodec` |
| `IMPL-EMP-006` | `employee-service/src/main/java/com/dylan/employee/security/EmployeeDetailSecurityConfiguration.java` |
| `IMPL-EMP-007` | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java`、`controller/EmployeeController.java` |
| `IMPL-EMP-008` | `agent-runtime/src/agent_runtime/adapters/employee/fields.py`、`agent-runtime/src/agent_runtime/adapters/employee/settings.py` |

### 14.2 关键类型与签名

```python
class EmployeeDetailInput:
    employee_identifier: str

class EmployeeDetailArgumentValidator:
    def validate(self, arguments: JsonObject) -> EmployeeDetailInput: ...

class EmployeeDetailRequestMapper:
    def map(self, input: EmployeeDetailInput, settings: BusinessActionSettings) -> EmployeeDetailWireRequest: ...

class EmployeeDetailWireCodec:
    def encode(self, request: EmployeeDetailWireRequest) -> BusinessHttpRequest: ...
    def decode_success(self, *, request: EmployeeDetailWireRequest, response: BoundedBusinessHttpResponse) -> EmployeeDetailWireResponse: ...

class EmployeeDetailResponseNormalizer:
    def normalize_success(self, response: EmployeeDetailWireResponse) -> BusinessRecordsResult[EmployeeDetailRecord]: ...
```

```java
public Employee detail(Authentication authentication, String idCardNo);
public void requireEmployeeRead(Authentication authentication);
SecurityFilterChain employeeDetailSecurityFilterChain(
    HttpSecurity http,
    Converter<Jwt, AbstractAuthenticationToken> converter
) throws Exception;
```

私有 helper 不是稳定接口，可在不改变本节契约、错误语义和测试意图的前提下调整。

## 15. 测试与验收

### 15.1 测试编号定义

| 测试编号 | 覆盖内容 |
|---|---|
| `TEST-EMP-001` | descriptor/domain/service key/单动作定义与 Provider 配置 |
| `TEST-EMP-002` | 架构边界：无数据库、无其他 Employee endpoint、无域外依赖 |
| `TEST-EMP-003` | Resolver 与参数正常、缺失、重复、附加动作、Unicode/path 注入 |
| `TEST-EMP-004` | 固定 GET/no-body/percent encoding/一次请求 |
| `TEST-EMP-005` | 六字段 strict decode、请求标识一致、重复 key、类型/长度/Unicode/大小失败 |
| `TEST-EMP-006` | normalizer、coverage、用户最小字段和转换 |
| `TEST-EMP-007` | ADMIN/VIEWER 允许，unknown/missing/malformed/service token 拒绝 |
| `TEST-EMP-008` | matcher、controller guard、非详情 endpoint 不被扩大 |
| `TEST-EMP-009` | 默认模型字段空；仅 position/work_base_si；敏感/未知/冲突零调用 |
| `TEST-EMP-010` | model spy、grounding、日志/禁止字面量零泄漏 |

### 15.2 验证编号定义

| 验证编号 | 通过标准 |
|---|---|
| `VAL-EMP-001` | `employee.detail` 唯一注册，固定只读详情调用，无动作扩张 |
| `VAL-EMP-002` | 参数/path 负例失败关闭，最多一次业务请求 |
| `VAL-EMP-003` | 响应、投影、失败语义与业务接口一致，无额外字段泄漏 |
| `VAL-EMP-004` | 业务服务最终授权，Adapter 无角色判断 |
| `VAL-EMP-005` | 模型交集与 grounding 通过，默认及拒绝场景模型调用为 0 |

### 15.3 建议命令

```powershell
Set-Location D:\codex\agent-runtime
python -m pytest tests/unit/adapters/employee tests/contract/adapters/employee tests/integration/adapters/employee/test_fake_server.py tests/integration/adapters/employee/test_sensitive_egress_zero_call.py -q
python -m mypy --strict src/agent_runtime/adapters/employee tests/unit/adapters/employee tests/contract/adapters/employee
python -m compileall -q src/agent_runtime/adapters/employee

Set-Location D:\codex
mvn -pl employee-service -am -DskipTests compile
mvn -pl employee-service -am -Dtest=EmployeeControllerAuthorizationTest,EmployeeDetailSecurityConfigurationTest,EmployeeDetailSecurityIntegrationTest test
```

真实 JWT/Employee 数据/模型出域只在独立显式授权下执行，不属于文档基线校验。

## 16. 可观测性与运维

第一阶段复用现有日志设施，不引入独立监控依赖。结构化字段限于 correlation ID、action、config snapshot、阶段、有限 HTTP/失败类别、returned count、egress disposition/reason 和耗时；任何完整 path、标识、JWT、Employee 内容和模型载荷不得记录。

## 17. 风险与开放项

| 风险 | 控制 |
|---|---|
| 业务 DTO 增长被误当作 Agent 可见字段 | codec 六字段 + 显式 field definitions |
| 标识泄漏到日志或模型 | 禁止完整 path 日志；模型候选从代码排除标识 |
| Adapter 代替业务域授权 | 原始 JWT 透传 + Employee 双层最终 guard |
| 真实样本字段为空导致模型实验失败 | 不降低资格或安全边界；独立合成 fixture 验证 |
| 历史 Gate 流程影响主设计阅读 | 历史材料只保留在归档与实施证据 |

当前无阻断设计开放项。外部模型真实出域继续默认关闭，其效果或环境失败不影响本地结构化查询。

## 18. 实施就绪结论

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前代码实现可据本版本复核 |
| 当前允许实施范围 | Adapter/业务服务契约内缺陷修复、测试补齐、只收紧配置 |
| 当前禁止动作 | 新 endpoint/DTO、列表/写入/聚合、Agent 角色判断、敏感字段模型出域、默认开启真实 egress |
| 当前结论 | Approved；可作为 Employee Adapter 与授权代码评审基线 |

## 19. 三轮内部自检与独立评审记录

| 类型 | 状态 | 结论 |
|---|---|---|
| 内部自检第 1 轮 | Passed | 范围、责任、来源、上位与公共 L2 一致 |
| 内部自检第 2 轮 | Passed | 单详情契约、最终授权、字段出域和错误语义一致 |
| 内部自检第 3 轮 | Passed | 真实落点、测试、去重、链接和可读性检查通过 |
| 独立正式评审 | Passed | `REV-L2-02-01-001～003` 已修复；Descriptor、状态映射、service-token 语义与实现复核通过 |
