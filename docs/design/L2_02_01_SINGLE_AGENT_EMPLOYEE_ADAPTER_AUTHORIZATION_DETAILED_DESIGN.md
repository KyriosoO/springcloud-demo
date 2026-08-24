# [L2_02_01] 单体 Agent Employee QueryPlan、Adapter 与授权详细设计

> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L2_02_01 |
| 当前版本 | v1.2 |
| 更新日期 | 2026-08-24 |
| 上位设计 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v1.1 |
| 公共详细设计 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v1.2 |
| 业务接口 | `GET /employees/{idCardNo}` |
| 实施状态 | Employee Adapter/codec/guard 与受控真实 detail 证据已存在；LLM QueryPlan、protected ref 配置和 Resolver 切断尚未实现 |

## 2. 修改历史、设计目标与范围

| 版本 | 日期 | 修改内容 |
|---|---|---|
| v1.1 | 2026-08-21 | 既有 Employee Adapter/授权/结果出域基线 |
| v1.2 | 2026-08-24 | Employee 目标改为 LLM detail QueryPlan + protected ref；核实通用 ES 搜索能力与授权/契约缺口并失败关闭 |

设计目标是仅用已确认 detail 接口完成受控 LLM QueryPlan 查询。范围外/不负责：Employee 列表筛选、ES 搜索、写接口、新 DTO、数据库和业务角色变更。

上位约束来源是 L1_02 v1.1 与 L2_02_00 v1.2。关联责任边界：Employee L2 负责 detail definition/config/codec，公共 plan 层负责 exact 校验/binder，业务服务负责最终授权。`CON-EMP-001`：禁止 Employee Adapter 依赖模型、数据库/ES、Knowledge 或 Transaction。

### 2.1 当前实现基线与只读接口核实

核实代码：

- `employee-service/src/main/java/com/dylan/employee/controller/EmployeeController.java`
  - `detail(Authentication, String)` 调用 `CapabilityAccessGuard.requireEmployeeRead(...)` 后执行 `EmployeeService.detail(...)`；
  - `page(page,size)` 仅分页，不接受字段筛选；
  - 写接口、count 和 change request 不在范围。
- `EmployeeService.detail(String idCardNo)` 只做精确标识查询。
- `EmployeeEsController` 暴露 `POST /employees/es/search`，其服务白名单含 `workBaseSi`、position 等字段；但 Controller 当前仅调用 `requireUser`，没有执行 `requireEmployeeRead` 的 `ROLE_ADMIN/ROLE_VIEWER` 最终授权，请求为通用 `SearchRequest`，响应为原始 ES 字符串。

本期唯一动作：`domain=employee`、`action=employee.detail`。按 `work_base_si`、position、姓名或其他字段搜索虽然有通用技术端点，但它不满足本设计的最终角色授权和受限稳定响应契约，因而当前没有可复用的 Agent 业务动作；必须 `unsupported`，Employee HTTP 调用为0。

## 3. 模块职责、依赖方向与核心处理流程

```text
question containing one employee identifier
  → Business Guard stores identifier in request-local slot
  → minimized question (no literal identifier)
  → LLM QueryPlan:
       domain=employee
       action=employee.detail
       employee_identifier={value_ref: slot-N}
  → common QueryPlan validator
  → Employee protected-ref binding
  → EmployeeDetailArgumentValidator
  → Employee Adapter
  → GET /employees/{encoded idCardNo} with user JWT
  → employee-service final authorization
  → strict response decode / projection
```

模型不接收员工标识、JWT、角色、endpoint 或 Employee 结果。Guard/binder 不决定 employee.detail，只保护和恢复模型已引用的值。

## 4. Employee 接口契约设计与动作定义

### 4.1 Definition

目标修改 `agent-runtime/src/agent_runtime/adapters/employee/definition.py`：

```python
def employee_detail_definition() -> BusinessActionDefinition[
    EmployeeDetailInput,
    EmployeeDetailWireRequest,
    EmployeeDetailWireResponse,
    EmployeeDetailRecord,
]: ...
```

保留 descriptor、argument validator、mapper、codec、normalizer、字段定义、HTTP 语义和限制；删除 `local_action_resolver=EmployeeDetailLocalActionResolver()`，新增：

```text
domain_id = employee
query_fields = (
  employee_identifier:
    description = "当前请求中单一员工标识的受保护引用"
    type = identifier
    operators = {eq}
    exposure = protected_ref
    required = true
)
combination_rules = empty
service_contract_ref = employee-detail-v1
```

### 4.2 QueryPlan

唯一可接受：

```json
{
  "domain": "employee",
  "action": "employee.detail",
  "arguments": {
    "employee_identifier": {"value_ref": "slot-1"}
  }
}
```

拒绝：literal identifier、额外参数、多个标识、列表条件、`work_base_si`/position/name、URL/路径/ES/DSL、其他 domain/action。

### 4.3 绑定后参数

Binder 解析同请求 slot 后构造既有：

```python
ActionCandidate(
    capability_id="employee.detail",
    arguments={"employee_identifier": protected_value},
)
```

随后必须复用 `EmployeeDetailArgumentValidator.validate(arguments) -> EmployeeDetailInput`；不得绕过 5～64 字符、UTF-8、空白/控制/双向字符、`/\\%?#` 等现有校验。

## 5. Employee 强类型配置

建议扩展 `EmployeeAdapterSettings.from_env(env)` 产生如下有效配置：

| 配置 | 代码上界/默认 | 规则 |
|---|---|---|
| enabled | 默认 false | 只能关闭/启用代码已定义动作 |
| config_version | 必填版本 | 进入 snapshot |
| code_contract_version | `employee-detail-plan-v1` | 必须 exact |
| service_contract_ref | `employee-detail-v1` | 必须 exact |
| query fields | 仅 `employee_identifier` | protected_ref、eq、required，不可配置 literal |
| max_result_count | 1 | 只能1 |
| timeout_ms | ≤3000 | 配置只能收紧 |
| user fields | 六字段代码集合子集，至少 masked id + chinese_name | 不能新增响应字段 |
| model fields | `position/work_base_si` 子集，默认空 | 必须也是 user fields |

endpoint base address 属于 service binding；relative path `/employees/{encoded}` 和 GET 固定在 codec，不进入模型 catalog。

## 6. Python Adapter 契约

### 6.1 既有输入/请求

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeDetailInput:
    employee_identifier: str

class EmployeeDetailRequestMapper:
    def map(
        self,
        input: EmployeeDetailInput,
        settings: BusinessActionSettings,
    ) -> EmployeeDetailWireRequest: ...

class EmployeeDetailWireCodec:
    def encode(self, request: EmployeeDetailWireRequest) -> BusinessHttpRequest: ...
    def decode_success(
        self,
        *,
        request: EmployeeDetailWireRequest,
        response: BoundedBusinessHttpResponse,
    ) -> EmployeeDetailWireResponse: ...
```

encode 使用 UTF-8 percent encoding，`safe=""`，固定 GET/path、无 query/body。禁止从 QueryPlan 读取 base URL 或 relative path。

### 6.2 响应

strict decode 至少要求并校验 `idCardNo/memberNo/chineseName/publicEmail/position/workBaseSi`；响应 `idCardNo` 必须等于请求标识。未知额外响应字段可以由现有兼容策略忽略，但不得自动进入用户或模型投影。

用户字段代码上界：

- `employee_id_masked`、`member_no_masked`、`chinese_name`、`public_email`、`position`、`work_base_si`。

模型字段代码上界：`position`、`work_base_si`；默认关闭。身份证、成员号、姓名、邮箱、联系方式、地址、账户、凭证、注入文本和未知字段不得进入模型。

## 7. Java 服务、权限与审计设计

既有 Java 签名保持：

```java
public Employee detail(Authentication authentication, String idCardNo)
public Employee detail(String idCardNo)
```

Controller 必须先调用 `CapabilityAccessGuard.requireEmployeeRead(authentication)`；`ROLE_ADMIN/ROLE_VIEWER` 等实际允许矩阵由业务服务 guard 和统一 Authority Converter 决定。Agent 不在配置中声明角色，不将 service token 替代用户 token。

HTTP 行为沿用现有契约：

- `2xx application/json`：严格解码；
- `401/403`：`unauthenticated/forbidden`；
- 当前 detail not-found 经既有 400 语义映射为 `invalid_argument`，本设计不擅自改业务错误契约；
- timeout/5xx/协议错误：`timeout/downstream_failure`。

## 8. 不支持查询的处理

示例：“帮我查看一下上海的员工”。

目标行为：

1. LLM 可识别为 Employee 条件搜索意图并生成非开放 action/field；
2. 本地 config validator 返回 `unsupported`；
3. Core、Employee Adapter、Employee HTTP、ES、Knowledge、Transaction 均0；
4. 不改写为分页列表，不从 `work_base_si` 本地过滤，不新增 endpoint。

如果希望支持，应先由用户单独决定是收紧现有通用端点还是提供受限业务端点，并确认 endpoint-scoped `ROLE_ADMIN/ROLE_VIEWER` 授权、request/response DTO、字段可见性和调用方兼容性，再更新 REQ/L0/L1/L2；本工作不授权。

## 9. 错误分类、失败与调用方可见错误码

| 场景 | 状态 | plan/Employee calls |
|---|---|---|
| 认证/strict JSON/禁止敏感输入 | 既有接入状态 | 0/0 |
| model failure | `downstream_failure/timeout` | 1/0 |
| literal identifier/ref 非法 | `invalid_argument` | 1/0 |
| search/field unsupported | `unsupported` | 1/0 |
| detail authorized success | `success` | 1/1 |
| detail forbidden | `forbidden` | 1/1 |
| downstream/codec failure | `downstream_failure` | 1/1 |

不得自动重试、切 Transaction、回退 Knowledge 或调用本地 Resolver。

## 10. 实现落点清单

| ID | 路径 | 类型 | 目标变更 |
|---|---|---|---|
| `IMPL-EMP-001` | `agent-runtime/src/agent_runtime/adapters/employee/definition.py` | 修改 | 去 Local Resolver；增加 query field/contract ref |
| `IMPL-EMP-002` | `agent-runtime/src/agent_runtime/adapters/employee/settings.py` | 修改 | input config/version/snapshot |
| `IMPL-EMP-003` | `agent-runtime/src/agent_runtime/adapters/employee/action_resolver.py` | 保留历史/生产退役 | 不再由目标组合根引用 |
| `IMPL-EMP-004` | `agent-runtime/src/agent_runtime/adapters/employee/codec.py` | 回归 | 既有参数/GET/strict decode 保持 |
| `IMPL-EMP-005` | `agent-runtime/src/agent_runtime/adapters/employee/provider.py` | 修改 | 注册无 Resolver definition 与 snapshot |
| `IMPL-EMP-006` | `employee-service/.../EmployeeController.java` | 只读回归 | 不改接口/DTO；验证 guard |

## 11. 测试与验证设计

| ID | 覆盖 |
|---|---|
| `TEST-EMP-001` | exact Employee QueryPlan，仅 protected ref |
| `TEST-EMP-002` | literal/unknown/ref missing/cross-request/多标识拒绝 |
| `TEST-EMP-003` | config 只含 detail/eq/ref/max1/version/snapshot |
| `TEST-EMP-004` | `work_base_si` 等 search 为 unsupported，所有下游0 |
| `TEST-EMP-005` | argument validator、percent encoding、GET no-body |
| `TEST-EMP-006` | strict response、标识一致、六字段投影 |
| `TEST-EMP-007` | model fields 默认空，敏感/未知/冲突零调用 |
| `TEST-EMP-008` | JWT 透传、ADMIN/VIEWER 允许及拒绝矩阵 |
| `TEST-EMP-009` | model failure 无 Resolver/Knowledge/Transaction fallback |
| `TEST-EMP-010` | composition 仅一 Employee handler/Adapter，Resolver 不可达 |
| `TEST-EMP-011` | 日志/model spy 无 identifier/JWT/raw response |
| `TEST-EMP-012` | 既有 Java/Python contract 与调用方兼容回归 |

## 12. 设计决策

| ID | 决策 |
|---|---|
| `DR-EMP-013` | Employee 首期只开放现有 detail 接口 |
| `DR-EMP-014` | 具体员工标识只通过 request-local protected ref 参与计划 |
| `DR-EMP-015` | Guard/binder 不承担 Employee 语义解析 |
| `DR-EMP-016` | 地点/职位筛选缺口失败关闭，不复用分页或通用 ES |
| `DR-EMP-017` | Java 最终授权与公开 DTO 保持不变 |

## 13. 当前差距与门禁

目标变更由 P3_00 `WP-EMP-QUERYPLAN-01` 承接，依赖公共 QueryPlan 与 Runtime 切换。完成前 Employee LLM 成功 UAT Blocked；真实模型/服务 UAT 需单独授权。

## 14. 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | detail/ref/config/codec/最终授权 | 补齐实现与测试追踪，修复后通过 |
| 内审2 | literal/ref 失败与 unsupported 隔离 | 明确下游零调用和不回退，修复后通过 |
| 内审3 | Employee 既有接口只读复核 | 确认 ES 搜索字段能力，但因最终角色授权和受限响应契约缺口不纳入，修复后通过 |
| 独立评审 R1～R3 | L2 与跨层一致性 | detail/ref/授权合同与既有接口事实一致；R3 无发现，通过 |

Approved 不表示 Employee QueryPlan 已实现，也不表示现有通用筛选端点已满足 Agent 复用条件。

## 15. 数据生命周期、一致性、风险与实现就绪判定

Employee identifier、slot、JWT 和原始响应只存在于单请求生命周期，无持久化、事务或数据迁移；请求终态后释放。业务数据一致性与事务边界属于 employee-service，本动作只读。设计以既有 detail codec/validator 作为稳定契约，只增加 protected-ref 计划接缝，是最小必要变更且与 Core 低耦合。主要风险是标识出域、误用列表/ES 和错误角色判断，分别由 slot/model spy、endpoint reachability 和业务 guard 审计控制。

| 项目 | 内容 |
|---|---|
| 是否可作为实现依据 | 是，设计可作为后续代码实施依据，但当前未授权实施 |
| 当前允许实施范围 | 取得 P3 `GATE-064` 后，仅限 IMPL-EMP-001～006 的 non-live 实现/回归 |
| 当前禁止动作 | 新增 Employee search/DTO、修改数据库/角色、真实调用、记录标识/JWT、恢复 Resolver |

## 16. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-EMP-001`; `CON-EMP-001` | `DR-EMP-013` | `IMPL-EMP-001` | `TEST-EMP-001` | `VAL-EMP-001` |
| `REQ-EMP-002` | `DR-EMP-014` | `IMPL-EMP-002` | `TEST-EMP-002` | `VAL-EMP-002` |
| `REQ-EMP-003` | `DR-EMP-016` | `IMPL-EMP-006` | `TEST-EMP-004` | `VAL-EMP-003` |
