# [L2_02_01] 单体 Agent Employee Adapter 与业务授权联调详细设计 L2

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Employee Adapter 与业务授权联调详细设计 |
| 文档标识 | `SA-L2-EMPLOYEE-ADAPTER-001` |
| 文档编号 | `L2_02_01` |
| 文档路径 | `docs/design/L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 五轮独立评审—修复—复核及直接依赖聚焦一致性复核已通过，`REV-EMP-001`～`REV-EMP-017` 全部关闭 |
| 当前版本 | v0.3 |
| 日期 | 2026-07-31 |
| 适用范围 | Python `agent-employee-adapter` 的 `employee.detail` 单动作、现有 Employee 详情接口映射、参数/响应/字段收紧、业务服务最终角色授权、错误映射、模型字段候选和联调门禁 |
| 上位文档 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.2 Approved |
| 直接输入 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v0.3 Approved；[`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4 Approved |
| 外部契约 | `employee-service` `GET /employees/{idCardNo}`；`auth-service/common-security` 用户 JWT/Authority |
| 实现基线 | 目标 Python Adapter 不存在；Employee 详情端点存在但返回宽 `Employee` 实体，未调用现有用户守卫；现有守卫只校验 user token，不校验 `ROLE_ADMIN/ROLE_VIEWER`；未找到统一 Authority converter |
| 是否可作为实现依据 | 否 |
| 实施依据说明 | 本文已完成五轮独立评审并具备实施就绪条件；开始 Python 切片仍需明确关闭 `BQ-GATE-002`，Employee Java/公开行为修改和真实动作启用还分别受 `BQ-GATE-003/SA-GATE-004` 控制 |
| 当前允许范围 | 文档评审、合成 Employee fixture、fake HTTP/Authority 契约推演 |
| 当前禁止动作 | 修改 Agent/Java/安全代码、配置、测试或公开契约；调用真实 Employee 数据；启用真实动作或模型出域；关闭门禁 |
| 修改权限 | 本轮只获授权第三批 L2 及直接相关文档索引原子同步；代码、配置、Schema、接口和真实数据只读 |

> 第一阶段只设计 `employee.detail`。在 Employee 方确认完整响应可见性后，真实 Adapter 才可复用现有详情接口并显式忽略宽实体中的非许可字段；确认前只允许合成 fixture/fake。分页、计数、ES 搜索、聚合、变更申请和全部写/管理入口不注册。字段投影不能替代 `employee-service` 的最终角色授权。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-31 | 全文 | 第三批 L2 依序编写 | 新建 Employee 单动作、接口映射、字段分类、授权入口、错误语义、实现触点、测试和门禁设计 |
| 2 | 2026-07-31 | 7/15 章 | 第 1 轮内部自检 | 补齐责任分解、依赖方向及内聚耦合判断，消除结构校验缺口 |
| 3 | 2026-07-31 | 3/6/9/10/14/15 章 | 第 2 轮内部自检 | 区分统一 role 映射与业务动作授权，增加宽响应可见性确认和敏感问题模型输入门禁 |
| 4 | 2026-07-31 | 8～16 章 | 第 3 轮内部自检 | 补齐固定结果数配置、请求级宽响应生命周期和提供方响应可见性验证，完成实施可验证性收口 |
| 5 | 2026-07-31 | 8 章 | 第三批原子一致性同步 | 补齐 Employee wire request/record 精确字段；不改变三轮内审结论或动作边界 |
| 6 | 2026-07-31 | 全文 | 五轮独立评审—修复—复核 | 关闭实现门禁、公共转换/状态、宽响应生命周期、完整 descriptor、Java 触点、字段类型、发布回滚和验证命令等 `REV-EMP-001`～`016`，定版 v0.2 Approved；不关闭实施/集成门禁 |
| 7 | 2026-07-31 | 1/8/9/12/13/16～18章 | `L2_02_00` v0.3 聚焦一致性同步 | `decode_success` 显式接收同一次 request，并验证响应 `idCardNo` 与请求标识精确一致；关闭 `REV-EMP-017`，保持 Approved 和开放门禁 |
| 8 | 2026-07-31 | 13 章 | 终态验证证据同步 | 执行含 Employee 及直接依赖的 Maven 现有基线回归并通过；建议修改/新增的角色守卫、MVC 与响应可见性测试尚未实施，所有实施/集成门禁保持 Open |

## 3. 背景、目标与范围

### 3.1 背景与根因

现有 `EmployeeController` 同时公开分页、详情、数量、变更和删除能力，详情直接返回包含身份证、联系方式、地址、银行账户和亲属信息的完整实体。当前 Resource Server 只要求 authenticated，详情方法未调用 `CapabilityAccessGuard`，该 guard 也只校验 `token_type=user`。若 Adapter 直接反射或透传响应，会同时绕过业务动作授权和字段最小化。

### 3.2 目标与可观察行为

| 需求编号 | 目标 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-EMP-001` | 只提供一个代码绑定详情动作 | registry 仅有 `employee.detail@1`；所有其他 Employee 路径调用数为零 | L1_02 6/7；L2_02_00 `DR-BQCOM-001` |
| `REQ-EMP-002` | 强类型标识映射到现有详情接口 | 输入不接受 URL、字段、分页、排序或 DSL；相对路径由 codec 唯一生成 | REQ_00 FR-03；接口优先复用 |
| `REQ-EMP-003` | 业务服务最终验证角色 | ADMIN/VIEWER 允许；认证失败 401；缺失/未知/混合非法 role 在统一安全边界 403，业务详情方法为零；有效 Authority 仍由 Employee 入口作动作级允许判断 | 用户确认；L1_02 7.4 |
| `REQ-EMP-004` | 宽响应只形成最小用户结果 | 账户、地址、电话、私人邮箱、亲属、生日等字段进入用户/模型结果次数为零 | L1_02 7.5/7.6 |
| `REQ-EMP-005` | 用户结果与模型结果分离 | 用户结果最多六字段；模型代码候选仅职位/工作地，配置和全局规则默认拒绝 | L2_02_00 9/11 |
| `REQ-EMP-006` | 现有状态语义不被猜测 | 当前 400 固定为 invalid_argument；不能把 `Employee not found` 文本解析成 no-result | L2_02_00 8.5/12.1 |
| `REQ-EMP-007` | 一次有界只读调用 | 每次最多一条 GET，无 retry/redirect/service-token，取消或迟到响应不接纳 | L2_02_00 `DR-BQCOM-014` |
| `REQ-EMP-008` | 敏感标识不进入模型或日志 | 原始 idCardNo、JWT、完整 URL、原始响应和异常正文均为零；具体身份问题不通过全局模型输入闸门 | L1_02 10；L2_00_02 |

### 3.3 范围内

- `employee.detail` descriptor、强类型输入、request mapper/codec/normalizer 和 provider。
- 详情响应的显式读取字段、用户投影、模型候选、转换和最小有效结果。
- 现有 Employee Controller 上该动作的最终 Authority 校验建议及允许/拒绝联调矩阵。
- 400/401/403/429/5xx、超时、宽响应、缺字段和未知字段的确定映射。

### 3.4 范围外

- Employee 分页、count、ES 搜索/向量、聚合、创建、更新、删除、审批、索引和重建。
- 新增 Employee 公开接口、修改 not-found 为 404、拆分响应 DTO；如需实施必须另行确认。
- Transaction、Knowledge、统一 role converter 私有实现、DeepSeek Provider 和通用 Prompt。
- Employee 行级/字段级业务规则重写或数据库结构修改。

### 3.5 非目标

- 不把完整 `Employee` 复制成 Python DTO，不建设动态字段映射/JSONPath。
- 不在 Adapter 解析 role claim、按用户名放行或使用固定管理员 token。
- 不因当前 400 message 看似“not found”而推导业务无结果。

### 3.6 实施剖面

| 剖面 | 适用 | 说明 |
|---|---|---|
| Python | 是 | Employee definition、DTO、codec、normalizer、provider、配置和测试 |
| Java/API | 是 | 复用现有详情方法；建议最小增加角色 guard 调用，不改 wire DTO |
| 安全 | 是 | 用户 JWT 透传、Authority 最终判定、敏感字段/日志隔离 |
| 数据库/事务 | 否 | Adapter 只读且不持久化；Employee 查询事务归业务服务 |
| 模型出域 | 条件适用 | 只定义代码候选；全局与动作配置默认拒绝，真实外发不在本门禁内 |

## 4. 上位约束

| 约束编号 | 上位位置 | 约束 | 本设计落实 | 偏离 |
|---|---|---|---|---|
| `CON-EMP-001` | L1_02 6/7.2 | 独立 Adapter、有限动作、配置只收紧 | `DR-EMP-001`、`DR-EMP-002` | 无 |
| `CON-EMP-002` | L1_02 7.3/7.4 | 原用户 JWT 透传、业务服务最终授权 | `DR-EMP-003`、`DR-EMP-004` | 无 |
| `CON-EMP-003` | L1_02 7.5/7.6 | 授权响应后字段交集、最小有效结果、模型默认拒绝 | `DR-EMP-005`、`DR-EMP-006`、`DR-EMP-007` | 无 |
| `CON-EMP-004` | L2_02_00 8.5/12.1 | HTTP 状态由 common mapper 先解释，域 codec 只处理 2xx | `DR-EMP-008` | 无 |
| `CON-EMP-005` | L2_02_00 9/10 | 一次调用、绝对截止、无 retry/服务身份 | `DR-EMP-009`、`DR-EMP-010` | 无 |
| `CON-EMP-006` | L1_02 10.1 | 敏感问题/字段不直接进入外部模型 | `DR-EMP-007`、`DR-EMP-011` | 无 |

### 4.1 端到端追踪矩阵

| REQ/CON | 设计规则 | 责任主体 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|
| `REQ-EMP-001`,`CON-EMP-001` | `DR-EMP-001`、`DR-EMP-002` | Employee provider/组合根 | `IMPL-EMP-001/002/007` | `TEST-EMP-001/002` | `VAL-EMP-001/002` |
| `REQ-EMP-002` | `DR-EMP-002`、`DR-EMP-010` | mapper/codec | `IMPL-EMP-003` | `TEST-EMP-003` | `VAL-EMP-001` |
| `REQ-EMP-003`,`CON-EMP-002` | `DR-EMP-003`、`DR-EMP-004` | employee-service/安全权威 | `IMPL-EMP-008/009` | `TEST-EMP-004/005` | `VAL-EMP-003/004` |
| `REQ-EMP-004`,`CON-EMP-003` | `DR-EMP-005`、`DR-EMP-006` | decoder/projector | `IMPL-EMP-004/005` | `TEST-EMP-006/007` | `VAL-EMP-001/002` |
| `REQ-EMP-005`,`CON-EMP-006` | `DR-EMP-007`、`DR-EMP-011` | field definition/egress | `IMPL-EMP-005/006` | `TEST-EMP-008/009` | `VAL-EMP-002` |
| `REQ-EMP-006`,`CON-EMP-004` | `DR-EMP-008` | status mapper/normalizer | `IMPL-EMP-004` | `TEST-EMP-010` | `VAL-EMP-001/003` |
| `REQ-EMP-007`,`CON-EMP-005` | `DR-EMP-009`、`DR-EMP-010` | common handler/client | `IMPL-EMP-003/007` | `TEST-EMP-011` | `VAL-EMP-002` |
| `REQ-EMP-008` | `DR-EMP-011` | 全边界 | `IMPL-EMP-003/005/006` | `TEST-EMP-009/012` | `VAL-EMP-002/004` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文责任 | 对方责任 | 权限 |
|---|---|---|---|---|
| `L2_02_00` | 直接依赖 | 实例化公共原语 | 公共配置/HTTP/结果/投影语义 | 只读 |
| `employee-service` | 业务权威 | 映射确认后的只读入口 | Employee 数据、最终角色授权、响应真实性 | 设计建议；代码只读 |
| `auth-service/common-security` | 身份权威 | 定义消费场景 | 用户/角色、验签、Authority 映射 | 只读 |
| `agent-runtime` core | 调用方 | 提交 descriptor/handler | 单动作 claim、context/deadline/公共结果 | 设计 |
| DeepSeek 模型边界 | 条件下游 | 仅提供安全字段候选 | 全局问题/结果出域和模型协议 | 默认拒绝 |

## 6. 当前基线与最小变更

### 6.1 已核实事实

| 状态 | 路径/符号 | 事实 | 影响 |
|---|---|---|---|
| 已存在 | `employee-service/src/main/java/com/dylan/employee/controller/EmployeeController.java` `detail(String)` | `GET /employees/{idCardNo}` 返回 `Employee` | 可复用一次只读接口 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/model/Employee.java` | 实体包含身份证、银行、地址、电话、亲属等宽字段 | Adapter 必须显式摘取，不能反射 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/service/EmployeeService.java` `detail(String)` | 未找到时抛 `IllegalArgumentException` | 当前经 advice 映射 400 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/web/EmployeeExceptionHandler.java` | 所有 `IllegalArgumentException` 返回 400 | 不能确认 no-result |
| 已存在但不足 | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java` | `requireUser` 只验证 user token；detail 未调用 | `SA-GATE-004` Open |
| 缺失 | `common-security` 当前 Resource Server | 未找到 role→Authority converter | 真实 ADMIN/VIEWER 联调不可关闭 |
| 缺失 | Python 目标 | `agent-employee-adapter` 尚不存在 | 所有 Python 路径均为建议新增 |

### 6.2 最小改造判断

候选最小方案是复用 `GET /employees/{idCardNo}`，不新增 DTO/endpoint。Provider 侧最小建议修改仅是在该详情 HTTP 入口调用一个 Employee 读权限 guard；Python 侧显式读取六个允许字段并忽略其余字段。该复用成立的前提是 Employee 方确认 ADMIN/VIEWER 对现有完整响应具有读取权限，且传输/访问日志符合敏感数据要求；Adapter 丢字段不是业务字段授权。确认前，即使后续关闭 `BQ-GATE-002`，完整 Python provider wiring 也只能连接 fake server，不能配置或访问真实 Employee endpoint。若不能确认，必须停在 `BQ-GATE-003` 并另行确认窄响应契约，修订本文后才能真实接线。由于 400 同时承载参数错误和未找到，首期保守映射 invalid_argument；若需要准确 no-result，也必须另行确认业务服务异常契约调整。

## 7. 责任、依赖与禁止路径

### 7.1 责任分解

| 组件 | 唯一职责 | 明确不负责 |
|---|---|---|
| Employee definition/provider | 冻结动作、字段、限制并提交公共组合根 | HTTP client、授权、另一业务域 |
| Employee mapper/codec/normalizer | 强类型输入与现有详情 wire 契约转换 | 动态 URL、角色判断、模型调用 |
| common handler/client/projector | 执行一次用户 JWT 调用和公共投影顺序 | Employee 字段/端点/业务授权 |
| Employee Controller/guard | 在业务方法前完成最终角色授权 | Agent 字段收紧、模型出域 |
| EmployeeService/Mapper | 返回 Employee 业务事实 | Agent 动作注册和答案生成 |

### 7.2 依赖方向与调用边界

```text
agent-runtime registry
  -> EmployeeDomainProvider
     -> BoundBusinessActionHandler
        -> EmployeeDetailMapper/Codec
        -> UserJwtBusinessHttpClient -> employee-service EmployeeController
           -> EmployeeReadAccessGuard -> EmployeeService -> EmployeeMapper
        -> EmployeeDetailNormalizer -> common user/egress projectors
```

禁止依赖与反向依赖：Employee Adapter 不得导入 Transaction、Employee Java DTO、数据库/ES client 或安全私有类；core 不得导入 Employee 字段；`employee-service` 不得信任 Adapter 投影作为授权；配置不得绕过 codec 指定 URL/method/header；模型不得触发分页、count、ES、变更或第二动作。

### 7.3 内聚与耦合判断

动作、字段和 wire 契约随 Employee 业务接口共同变化，内聚在 Employee Adapter；JWT client、公共结果与投影算法随两域共同约束变化，留在 business common；最终角色授权随业务数据权威变化，留在 `employee-service`。三者只通过冻结 action definition、HTTP wire 和 Authority 可观察契约耦合，不共享 Java/Python 私有 DTO，因此新增 Transaction 或未来 Employee 第二动作不要求修改 core 或既有公共算法。

## 8. 动作、请求与响应契约

### 8.1 动作定义

| 定义字段 | 冻结值 |
|---|---|
| `descriptor.capability_id` | `employee.detail` |
| `api_version/kind` | `1/query` |
| `display_name` | `Employee detail` |
| `description` | `查询单个员工的受控基础信息；只接受 employee_identifier，不提供列表、聚合或写入。` |
| `aliases` | `("员工详情","employee profile")`；只帮助模型理解，不可作为执行 ID |
| `argument_schema` | 8.2 的固定 object schema；`required=["employee_identifier"]`、`additionalProperties=false` |
| `domain_id/service_key` | `employee/employee-service` |
| `answer_mode` | `model_assisted`，但本地结构化结果始终可返回 |
| `applicable_dimensions` | 仅 `max_result_count`、`timeout_ms` |
| `contract_limits` | `max_result_count=1`；`max_timeout_ms=3000`；`max_request_bytes=1024`；无 page/time/filter/sort；Employee codec 另拒绝超过 65536 raw bytes 的已聚合 2xx body |
| `http_status_semantics` | `http_400_is_invalid_argument=true`；`http_204_is_no_result=false`；`http_404_is_no_result=false` |
| `required_user_field_ids` | `employee_id_masked,chinese_name` |

### 8.2 Python 输入与方法

`CapabilityDescriptor.argument_schema` 固定为下列供应商无关受控子集；Schema 只用于动作选择描述，运行时仍必须由同一注册项的 validator 执行 UTF-8、控制字符、保留字符和掩码前置条件校验：

```json
{
  "type": "object",
  "properties": {
    "employee_identifier": {
      "type": "string",
      "minLength": 5,
      "maxLength": 64,
      "description": "Employee service identifier; never a URL or query expression."
    }
  },
  "required": ["employee_identifier"],
  "additionalProperties": false
}
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeDetailInput:
    employee_identifier: str
```

| 类型 | 精确字段 | 不变量 |
|---|---|---|
| `EmployeeDetailWireRequest` | `employee_identifier: str` | 只由 validator/mapper 构造，已满足标识边界 |
| `EmployeeDetailWireResponse` | `id_card_no: str`；`member_no: str \| None`；`chinese_name: str`；`public_email: str \| None`；`position: str \| None`；`work_base_si: str \| None` | 8.3 字段/空值/长度不变量 |
| `EmployeeDetailRecord` | 与 wire response 相同的六个冻结 typed 字段 | 只由 normalizer 构造，不保留原始 JSON |

`EmployeeDetailArgumentValidator.validate(arguments: JsonObject) -> EmployeeDetailInput` 只接受唯一 key `employee_identifier`。输入必须是 exact string；先去除首尾 Unicode whitespace 再做 NFC，结果为 5～64 Unicode code points 且 UTF-8≤192 bytes；拒绝内部 whitespace、Unicode control/Bidi override/isolate、`/`、反斜线、`%`、`?`、`#`，大小写不变。该边界只保证单一 path segment 和必需掩码可实现，不猜测 Employee 方身份证/护照字符集；业务语义仍由现有接口判断，配置不能放宽。

`EmployeeDetailRequestMapper.map(input, settings) -> EmployeeDetailWireRequest` 验证 result count 恰为 1；`EmployeeDetailWireCodec.encode` 把未预编码的 NFC 值按 UTF-8 做一次 RFC 3986 segment percent-encoding、`safe=""`，生成且只生成 `GET /employees/{encoded}`，无 query/body/自定义 header；不得接受或二次解释已有 `%HH`。

### 8.3 2xx wire response

- 顶层必须为单个 JSON object，严格 UTF-8、unique keys；Employee codec 只接受 body≤65536 raw bytes。公共客户端仍先按 `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` 聚合，故 65537～全局上限由 codec 拒绝，超过全局上限由 transport 拒绝。
- 六个目标字段按现有 camelCase 名解码；`idCardNo/chineseName` 必须为非空 exact string，其余为 exact string 或 null；bool、number、array、object 均不宽松转换。
- 规范化后的响应 `idCardNo` 必须与同一次 `EmployeeDetailWireRequest.employee_identifier` code-point 精确相等；不做大小写或本地身份证规则归一化。不一致为 invalid_response，typed record/模型调用为零。
- 未列入的 Employee 字段和未来新增字段允许解析后显式丢弃，但不得进入 typed record、日志、错误或指标；目标字段类型错误、重复 key 或缺必需字段则整个响应 invalid_response。该策略是对公共“默认严格拒绝”的本域兼容性例外，仅因当前公开响应是已核实的宽实体而成立。
- string NFC 后上限：`idCardNo/memberNo` 为 5～64，姓名 1～128，邮箱 1～254，职位/工作地 1～256 code points；非空值含控制/Bidi 字符或越界时不截断并失败关闭。
- 首期不引入流式 JSON 生产依赖：strict decoder 可短暂构造受全局字节上限约束的 JSON object，但只能把六个目标字段复制进冻结 typed response，随后释放原始 bytes/object。测试以账户、地址、亲属和嵌套恶意字段证明零 typed 投影、零日志和零错误回显，不能声称未知值未进入 Agent 内存。

### 8.4 字段目录与转换

| field_id | source | value_type | class | user | model candidate | allowed user transforms | allowed model transforms |
|---|---|---|---|---:|---:|---|---|
| `employee_id_masked` | `idCardNo` | `identifier` | `personal_identifier` | 是/必需 | 否 | `{mask_keep_last4}` | `{}` |
| `member_no_masked` | `memberNo` | `identifier` | `employee_identifier` | 是 | 否 | `{mask_keep_last4}` | `{}` |
| `chinese_name` | `chineseName` | `text` | `personal_identifier` | 是/必需 | 否 | `{bounded_text}` | `{}` |
| `public_email` | `publicEmail` | `text` | `contact` | 是 | 否 | `{bounded_text}` | `{}` |
| `position` | `position` | `text` | `business_internal` | 是 | 是 | `{bounded_text}` | `{bounded_text}` |
| `work_base_si` | `workBaseSi` | `text` | `business_internal` | 是 | 是 | `{bounded_text}` | `{bounded_text}` |

表中顺序就是冻结 field definition、用户结果和事实生成顺序；`None` 依公共规则省略，不能进入结果。模型字段代码上限仅为 `position/work_base_si`，动作配置默认空，且仍与全局规则取交集。姓名、标识和邮箱永不进入模型候选。`mask_keep_last4` 完全复用 `L2_02_00`：输入必须为 NFC、无控制/Bidi 且 5～256 code points，输出固定为 `***` 加末四个 code points；本文不定义长度≤4的域内特例，任一不满足值使用户投影失败关闭。

## 9. 详细功能与处理流程

### 9.1 设计规则

| 规则编号 | 规则 | 责任主体 | 效果 |
|---|---|---|---|
| `DR-EMP-001` | 只定义并注册 `employee.detail@1`，descriptor 是唯一动作权威 | provider/组合根 | 动作面有限 |
| `DR-EMP-002` | 配置只能禁用动作、减少本地/模型字段和 timeout，不能新增动作/参数/URL | settings/provider | 配置不扩权 |
| `DR-EMP-003` | Adapter 只透传当前 opaque user JWT，不解析 role、不使用 service token | handler/client | 身份不替换 |
| `DR-EMP-004` | 统一安全边界先验证 role claim 并映射 Authority；Employee 详情入口再于 service 前验证 user token 且含 `ROLE_ADMIN` 或 `ROLE_VIEWER` | common-security/employee-service | 映射与业务授权分层 |
| `DR-EMP-005` | codec 只提取六个字段，其他宽实体字段显式忽略且零留存 | codec | 宽响应隔离 |
| `DR-EMP-006` | idCard/memberNo 先掩码；必需 ID/姓名缺失时 downstream failure，不制造空 success | projector | 最小有效结果 |
| `DR-EMP-007` | 模型字段只可能是职位/工作地，默认空；转换/交集失败保留本地结果且模型调用为零 | egress projector | 出域失败关闭 |
| `DR-EMP-008` | 400 固定 invalid_argument；401/403 保持；404/204/非法 2xx 不猜 no-result | status mapper/normalizer | 状态真实 |
| `DR-EMP-009` | 一次请求至多一个 GET，共享绝对截止，无 retry/redirect/cache/第二动作 | common handler/client | 资源有界 |
| `DR-EMP-010` | path 只由 codec 编码受控标识生成，原始标识不进入日志/异常 | mapper/codec | 无动态调用 |
| `DR-EMP-011` | 具体 Employee 标识、姓名、联系方式和返回自由文本均作为敏感场景输入全局问题/模型闸门 | fixtures/L2_00_02 | 模型零调用可证 |

### 9.2 正常序列

1. core 通过同一 descriptor validator 产生 `EmployeeDetailInput` 并 claim 单动作。
2. handler 校验 context、opaque user token、取消和绝对 deadline；失败时网络为零。
3. mapper/codec 生成唯一详情 GET，common client 只向冻结的 employee-service origin 发送原用户 JWT。
4. 统一安全边界拒绝非法 role claim；Employee Controller 再于调用 `EmployeeService.detail` 前执行动作角色 guard，拒绝时 service/mapper/DAO 为零。
5. 2xx body 经 common 全局上限聚合后，由 Employee codec 以同一次 wire request 校验标识回显，并再校验≤65536 bytes及严格 JSON；未知宽字段只在受限临时 object 中存在，不能进入 typed response。
6. normalizer 产生一条 records result；公共 projector 构造掩码后的用户结果。
7. egress projector 计算配置/代码/全局交集；默认空时不调用模型，直接返回结构化结果。

### 9.3 配置

建议新增的动作前缀固定为 `AGENT_EMPLOYEE_DETAIL_`：

| key | 默认 | 约束 |
|---|---|---|
| `AGENT_EMPLOYEE_DETAIL_ENABLED` | `false` | Authority/契约未闭环前不得 true |
| `AGENT_EMPLOYEE_DETAIL_TIMEOUT_MS` | `2000` | 100～3000 |
| `AGENT_EMPLOYEE_DETAIL_MAX_RESULT_COUNT` | `1` | 必须精确为 1，仅为 common settings/definition 一致性校验，不提供扩展空间 |
| `AGENT_EMPLOYEE_DETAIL_USER_FIELDS` | 六个代码字段 | 子集且保留两个 required |
| `AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS` | 空 | 仅 `position,work_base_si` 子集 |
| `AGENT_EMPLOYEE_DETAIL_USER_TRANSFORMS` | 代码表固定选择 | 每个启用用户字段恰一允许枚举 |
| `AGENT_EMPLOYEE_DETAIL_MODEL_TRANSFORMS` | 空 | 每个启用模型字段恰一 `bounded_text` |

服务 origin 使用组合根通用 `employee-service` binding，不使用本动作 key 覆盖 URL。未知前缀键、重复字段、移除 required、添加 filter/sort/page 参数或非法转换均阻止 Runtime 就绪。

## 10. 失败类型、权限与审计

### 10.1 失败类型与错误码矩阵

| 触发 | Service result | 公共结果 | 下游/模型调用 |
|---|---|---|---|
| context/JWT 缺失 | unauthenticated | `business.missing_user_token` | HTTP 0/模型 0 |
| token 认证失败 | unauthenticated | `business.downstream_unauthenticated` | Controller 后 0/模型 0 |
| Authority 明确拒绝/不可判定 | forbidden | `business.downstream_forbidden` | service/DAO 0/模型 0 |
| 输入格式非法或 Employee 400 | invalid_argument | `business.invalid_arguments` | 至多 HTTP 1/模型 0 |
| Employee 2xx 合法 | records | success | HTTP 1/模型 0 或 1 |
| Employee 204 | invalid_response | `business.invalid_response` | HTTP 1/模型 0 |
| Employee 404（未声明 no-result） | downstream_failure(`unavailable`) | `business.downstream_failure` | HTTP 1/模型 0 |
| 目标字段缺失/类型错/body 超限 | invalid_response | `business.invalid_response` | HTTP 1/模型 0 |
| required 投影失败 | records 后投影失败 | `business.minimum_user_result_not_met` | HTTP 1/模型 0 |
| timeout/429/5xx/协议失败 | timeout/rate_limited/unavailable | common 固定 code | HTTP≤1/模型 0 |

禁止解析 400/404 body、异常 message 或 `Employee not found` 字样决定状态。若业务服务后续提供明确 404 no-result 契约，须经公开契约确认后把 definition 的 `http_404_is_no_result` 改为 true 并同步 consumer/provider test。

### 10.2 权限与审计

建议 Employee 业务边界新增/修改的可观察方法为 `CapabilityAccessGuard.requireEmployeeRead(Authentication)`：先调用现有 `requireUser(authentication)`，再从 `authentication.getAuthorities()` 读取不可变快照，并在至少一个 authority 精确等于 `ROLE_ADMIN` 或 `ROLE_VIEWER` 时允许，否则抛无敏感正文的 403。它不做大小写转换、不解析原始 `role` claim，也不按 `dylan` 用户名判断；缺失、未知、大小写错误或已知+未知混合 role 必须已由统一 converter 在进入 Controller 前整体拒绝，不能靠 guard 从原 claim 重做映射。`EmployeeController` 构造器必须新增注入 `CapabilityAccessGuard`，`detail(Authentication,String)` 必须先调用 guard，再且仅再调用一次 `EmployeeService.detail`。

`BQ-GATE-003` 的响应可见性证据不能只由 Adapter 测试反推。建议 Employee 方在 provider 测试资源中新增版本化、无真实数据的 `employee-detail-response-visibility-v1.json`，至少冻结 endpoint、允许角色 `ADMIN/VIEWER`、当前 `Employee` 序列化字段名全集和 policy version；维护者对该证据作明确确认后，provider contract test 才能证明实际 200 字段集合与已确认策略一致。若 Employee 方不能确认完整字段集对两个角色均可见，则该 fixture 不得伪造，必须转入窄 DTO/endpoint 的单独设计与授权。

日志只允许 correlation ID、`employee.detail`、有限状态、耗时、响应字节数和配置 snapshot ID。禁止 JWT、subject、原始/掩码员工标识、姓名、邮箱、完整 path、响应字段、异常 message/stack。由于现有标识位于 URL path，真实启用前还须验证 Gateway/Servlet access log 不记录或已脱敏该 path；未验证时 `SA-GATE-004` 保持 Open。

### 10.3 事务边界与一致性

Adapter 不创建事务，不写缓存、数据库、消息或索引。一次详情 GET 的数据一致性由 `employee-service` 当前查询提供；Adapter 只保证同一冻结 definition/settings、一次响应和不可变投影。重复请求是新的只读查询，不自动重试或声称跨请求快照一致。

## 11. 数据生命周期、发布与回滚

### 11.1 数据生命周期

原始标识只存在于当前 input、编码 path 和业务调用；现有宽详情的 2xx 原始 body 会先在 common 客户端中以最多 `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` 请求级字节聚合，Employee codec 只接受≤65536 bytes，并可能短暂构造包含未知字段的受限 JSON object。构造六字段 typed response 后必须解除原始 bytes/object 引用，不能声称未知字段从未进入 Agent 进程。原始/掩码标识和 Employee 字段均不持久化、不缓存、不写日志。模型 safe payload 若被全局允许，也只能含职位/工作地和请求内 `record_ref`。

### 11.2 发布与回滚

1. 先用 synthetic Employee fake 完成 Python definition/codec/字段/失败测试。
2. 在修改详情 guard 前盘点现有 `GET /employees/{idCardNo}` 调用方及其角色；不能证明所有合法调用方均满足新角色契约时，`BQ-GATE-003` 不得关闭。
3. 再单独实施并验证 Authority converter、Employee detail guard 和完整响应 visibility fixture；不同时改变响应 DTO。
4. 真实动作初始仍 disabled；完成 provider/consumer、访问日志和角色矩阵后才允许启用。
5. Agent 侧回滚只将 `AGENT_EMPLOYEE_DETAIL_ENABLED=false` 并重启 Runtime。Provider guard 失败时先停用 Agent 并阻断该详情入口的非预期流量，再按 provider 版本回滚；不得把“恢复任意 authenticated 用户可读宽实体”作为自动降级。公开行为恢复涉及安全接受，必须由 Employee 方明确决定。

本文不含数据迁移。若后续把详情响应改为窄 DTO 或修正 404，必须制定公开契约兼容/回滚方案，不能只改 Adapter 猜测。

## 12. 实现落点与关键签名

### 12.1 实现落点

| 编号 | 状态 | 路径/符号 | 责任 | 规则 |
|---|---|---|---|---|
| `IMPL-EMP-001` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/definition.py` `employee_detail_definition()` | 冻结 descriptor/limits/fields/status | `DR-EMP-001/002` |
| `IMPL-EMP-002` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/contracts.py` | input/wire response/record | `DR-EMP-001/005` |
| `IMPL-EMP-003` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/codec.py` | validator/mapper/GET encode/strict decode | `DR-EMP-002/005/009/010` |
| `IMPL-EMP-004` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/normalizer.py` | 合法 2xx→一条 records | `DR-EMP-005/008` |
| `IMPL-EMP-005` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/fields.py` | 六字段 extractor/class/transform | `DR-EMP-005/006/007` |
| `IMPL-EMP-006` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/settings.py` | 精确 env fragment/default/校验 | `DR-EMP-002/007` |
| `IMPL-EMP-007` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/employee/provider.py` `EmployeeDomainProvider` | definition/config fragment；不建 client | `DR-EMP-001/009` |
| `IMPL-EMP-008` | 建议修改 | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java` | 增加 Employee 读 Authority 判定 | `DR-EMP-004` |
| `IMPL-EMP-009` | 建议修改 | `employee-service/src/main/java/com/dylan/employee/controller/EmployeeController.java` 构造器与 `detail` | 注入 guard；详情调用前执行业务 guard | `DR-EMP-004` |
| `IMPL-EMP-010` | 建议新增 | `employee-service/src/test/resources/contracts/agent/employee-detail-response-visibility-v1.json` | 记录经维护者确认的角色/完整响应字段/policy version；无业务值 | `DR-EMP-004/005` |

### 12.2 Python 关键方法

| 符号 | 签名 | 输入校验/输出 | 副作用 |
|---|---|---|---|
| `EmployeeDetailArgumentValidator.validate` | `def validate(self, arguments: JsonObject) -> EmployeeDetailInput` | 唯一标识字段；有限错误 | 纯函数 |
| `EmployeeDetailRequestMapper.map` | `def map(self, input: EmployeeDetailInput, settings: BusinessActionSettings) -> EmployeeDetailWireRequest` | result=1/no extra dimension | 纯函数 |
| `EmployeeDetailWireCodec.encode` | `def encode(self, request: EmployeeDetailWireRequest) -> BusinessHttpRequest` | 唯一 GET path | 纯函数 |
| `EmployeeDetailWireCodec.decode_success` | `def decode_success(self, *, request: EmployeeDetailWireRequest, response: BoundedBusinessHttpResponse) -> EmployeeDetailWireResponse` | 仅2xx application/json；request为当前调用栈同一冻结对象；严格UTF-8、无BOM/trailing、duplicate key/NaN/Infinity拒绝；body≤65536；六字段exact type；响应ID与请求精确一致；未知字段仅临时解析后丢弃 | 有界内存纯函数；不保存请求期状态/原object |
| `EmployeeDetailResponseNormalizer.normalize_success` | `def normalize_success(self, response: EmployeeDetailWireResponse) -> BusinessServiceResult[EmployeeDetailRecord]` | 恰一 record | 纯函数 |
| `employee_detail_definition` | `def employee_detail_definition() -> BusinessActionDefinition[EmployeeDetailInput,EmployeeDetailWireRequest,EmployeeDetailWireResponse,EmployeeDetailRecord]` | 返回冻结代码上限、字段顺序与状态语义 | 纯函数 |
| `EmployeeDomainProvider.domain_id` | `def domain_id(self) -> BusinessDomainId` | 精确返回 `employee` | 纯函数 |
| `EmployeeDomainProvider.definitions` | `def definitions(self) -> tuple[BusinessActionDefinition[Any,Any,Any,Any], ...]` | 恰含 `employee.detail` | 纯函数 |
| `EmployeeDomainProvider.configuration_fragment` | `def configuration_fragment(self) -> BusinessConfigurationFragment` | 只投影 `AGENT_EMPLOYEE_DETAIL_*` 与 `employee-service` binding，不读取 `os.environ`/其他域 | 纯函数 |

### 12.3 Java 关键方法

| 类/方法 | 建议签名 | 前置/返回 | 副作用 |
|---|---|---|---|
| `CapabilityAccessGuard.requireEmployeeRead` | `void requireEmployeeRead(Authentication authentication)` | user JWT；含 `ROLE_ADMIN` 或 `ROLE_VIEWER`；否则 403 | 无 DAO 调用 |
| `EmployeeController.EmployeeController` | `EmployeeController(EmployeeService employeeService, CapabilityAccessGuard accessGuard)` | 两个依赖均由 Spring 注入并保存为 final | 仅装配依赖 |
| `EmployeeController.detail` | `Employee detail(Authentication authentication, @PathVariable String idCardNo)` | guard allow 后调用 service；保持现有 200/400 wire | 一次 service 调用 |
| `EmployeeService.detail` | 已存在 `Employee detail(String idCardNo)` | 本文不修改签名/异常 | 一次 mapper 读取 |

## 13. 测试与验证设计

### 13.1 测试矩阵

| 测试编号 | 规则 | 层级 | 建议路径/场景 | 关键断言 |
|---|---|---|---|---|
| `TEST-EMP-001` | `DR-EMP-001/002` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_definition.py` | descriptor 全字段与固定 argument schema；validator 对 schema 内更严格边界；唯一动作/无 page/filter/sort/URL 配置 |
| `TEST-EMP-002` | `DR-EMP-001/009` | Architecture | 建议新增：`agent-runtime/tests/architecture/test_employee_adapter_boundaries.py` | 无 Transaction/Java/DB/ES/retry import；禁止路径不可达 |
| `TEST-EMP-003` | `DR-EMP-002/010` | Unit | 建议新增：`tests/unit/adapters/employee/test_codec_request.py` | Unicode/UTF-8/控制/Bidi/保留字符边界；单次编码且拒绝预编码 `%HH`；唯一 GET、无 query/body |
| `TEST-EMP-004` | `DR-EMP-003/004` | Java Unit/Contract | 建议修改现有：`employee-service/src/test/java/com/dylan/employee/security/CapabilityAccessGuardTest.java`；建议新增统一 converter contract fixture | guard 对 ADMIN/VIEWER allow；converter 对 unknown/mixed role 403；service token 403 |
| `TEST-EMP-005` | `DR-EMP-004/005` | Java MVC/Provider contract | 建议新增：`employee-service/src/test/java/com/dylan/employee/controller/EmployeeControllerAuthorizationTest.java`、`EmployeeControllerResponseVisibilityContractTest.java` 和 12.1 的 visibility fixture | deny 时 controller 的 service=0；allow 恰一次；实际 200 序列化字段集合与维护者确认的 versioned fixture 精确一致；fixture 未确认时测试不得替代门禁 |
| `TEST-EMP-006` | `DR-EMP-005/006` | Contract | 建议新增：`agent-runtime/tests/contract/adapters/employee/test_detail_response.py` | 六字段exact type/limit；请求/响应ID相等与不匹配；两个并发请求交错响应不串状态；BOM/trailing/NaN/duplicate key；65536/65537 bytes；宽敏感字段可短暂解析但typed result/日志/错误零投影 |
| `TEST-EMP-007` | `DR-EMP-006` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_user_projection.py` | 5 字符/64 字符掩码与 4 字符拒绝；required 缺失不得变 no-result |
| `TEST-EMP-008` | `DR-EMP-007` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_egress.py` | model⊂user；默认空；仅职位/工作地 |
| `TEST-EMP-009` | `DR-EMP-007/011` | Model spy | 建议新增：`agent-runtime/tests/integration/adapters/employee/test_sensitive_egress_zero_call.py` | 标识/姓名/邮箱/注入文本均模型 0 |
| `TEST-EMP-010` | `DR-EMP-008` | Parameterized | 建议新增：`agent-runtime/tests/unit/adapters/employee/test_status_mapping.py` | 400→invalid_argument、204→invalid_response、未声明404→downstream_failure；401/403/429/5xx 精确且不读 body |
| `TEST-EMP-011` | `DR-EMP-009` | Async fake HTTP | 建议新增：`agent-runtime/tests/integration/adapters/employee/test_deadline_single_call.py` | ≤1 HTTP、无 retry、取消/迟到丢弃 |
| `TEST-EMP-012` | `DR-EMP-010/011` | Log/security | 建议新增：`agent-runtime/tests/integration/adapters/employee/test_sensitive_logging.py` | token/path/标识/字段/异常 sentinel 零出现 |

### 13.2 验证命令

| 编号 | 命令 | 证明范围 | 当前状态 |
|---|---|---|---|
| `VAL-EMP-001` | `python -m pytest agent-runtime/tests/unit/adapters/employee agent-runtime/tests/contract/adapters/employee -q` | definition/codec/field/status | 未执行：代码不存在 |
| `VAL-EMP-002` | `python -m pytest agent-runtime/tests/integration/adapters/employee agent-runtime/tests/architecture/test_employee_adapter_boundaries.py -q` | 单调用、模型/日志零泄露、边界 | 未执行：代码不存在 |
| `VAL-EMP-003` | `mvn -f serviceCenter/pom.xml -pl :employee-service -am test` | Employee guard/MVC/现有回归 | 2026-07-31 通过更大聚合命令覆盖现有 Employee 基线并 `BUILD SUCCESS`；本文建议修改/新增的角色守卫、MVC 与响应可见性测试尚未实施 |
| `VAL-EMP-004` | opt-in：ADMIN/VIEWER/unknown/missing/malformed/service-token 真实 JWT 矩阵，并以 service/mapper spy 计数 | Authority/业务最终授权/领域调用次数 | 未执行：converter/guard 差距未关闭 |
| `VAL-EMP-005` | opt-in：以仅用于测试的合成 sentinel identifier 通过实际 Gateway/Servlet 发起一次详情请求，并检索该 correlation ID 的访问日志 | 完整/编码标识、JWT、完整 path 在 Gateway/Servlet/应用日志均零出现 | 未执行：真实入口和日志策略未获联调授权 |

## 14. 风险、门禁与授权

### 14.1 风险

| 编号 | 风险 | 触发 | 影响 | 处置 |
|---|---|---|---|---|
| `RISK-EMP-001` | 详情 URL 含敏感标识 | access log 开启 | 标识泄露 | P4 前验证 Gateway/Servlet path 脱敏；否则不启用 |
| `RISK-EMP-002` | 400 混合 not-found/invalid | 不存在员工 | 不能准确 no-result | 保守 invalid_argument；变更 404 须另行确认 |
| `RISK-EMP-003` | 宽实体兼容 | 目标六字段类型/语义改变，或新增未知字段含恶意嵌套值 | 目标变化导致受控失败；未知值短暂进入受限内存 | 六字段 exact decode；未知字段仅临时解析后丢弃；visibility fixture 使任何实际字段集合变化先触发 provider contract 失败 |
| `RISK-EMP-004` | Authority 未闭环 | 真实调用 | 越权/误拒绝 | converter+业务 guard+DAO spy 矩阵 |
| `RISK-EMP-005` | 姓名/职位用于模型 | 误开配置 | 个人/内部数据外发 | code candidates 最小、默认空、全局门禁仍 Open |
| `RISK-EMP-006` | 宽响应可见性未确认 | VIEWER 调用现有详情 | 业务服务把未授权字段传给 Agent 进程 | Employee 方确认完整响应权限；否则另行确认窄 DTO/endpoint |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 控制动作 | 关闭条件 | 责任方 | 状态 | 未关闭允许/禁止 |
|---|---|---|---|---|---|---|
| `BQ-GATE-002` | slice_implementation | 实施本 L2 的 Python Employee Adapter/配置/测试切片 | 本文独立评审可实施、直接依赖稳定且维护者明确授权具体代码切片；关闭后可实现完整 Python provider wiring，但在其余门禁开放时只能连接 fake server | 维护者 | Open | 允许文档与合成推演；禁止目标代码实施；关闭后仍禁止修改 Employee Java 或连接/启用真实 endpoint |
| `BQ-GATE-003` | slice_implementation | 实施/变更 Employee 提供方接口、公开行为或守卫 | 维护者确认复用详情、ADMIN/VIEWER 对完整响应的可见性、versioned visibility fixture、现有调用方角色兼容、角色 guard 与 400 语义，并批准具体 Java/测试范围 | 维护者/Employee 方 | Open | 允许设计/fake；禁止 Java/公开行为修改 |
| `CR-GATE-003` | integration | 具体 Employee 问题进入 DeepSeek 以选择/摘要动作 | 全局问题闸门能对标识、姓名、联系方式等形成已批准最小化或零调用路径 | 维护者/模型方 | Open | 允许显式 synthetic action/fake；禁止具体敏感问题外发 |
| `SA-GATE-004` | integration | 启用真实 Employee 动作 | 本文独立评审；Authority、业务 guard、字段/status、访问日志、允许拒绝矩阵通过 | 维护者/安全/Employee 方 | Open | 允许 synthetic fake；禁止真实数据动作 |
| `SA-GATE-006` | integration | Employee 结果进入 DeepSeek | 字段交集、全局策略、facts/grounding 和零调用测试通过 | 维护者/模型方 | Open | 允许本地结果/合成 payload；禁止真实数据外发 |

### 14.3 后续需授权

- 新增 Python Adapter、配置和测试。
- 修改 Employee guard/controller/test 或统一 Authority converter。
- 修改详情 not-found/响应 DTO、启用真实 Employee 或外发真实结果。

## 15. 内部自检记录（作者内审）

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-31 | 0 | 2 | 1 | 3 | 0 | 责任、依赖和耦合结构已补齐，严格校验结构项清零 |
| 2 | 2026-07-31 | 0 | 2 | 2 | 4 | 0 | Authority 分层、宽响应可见性和敏感问题门禁已对齐 |
| 3 | 2026-07-31 | 0 | 0 | 3 | 3 | 0 | 固定结果数、原始 body 生命周期和提供方 visibility test 已收口 |

## 16. 独立正式评审记录

每轮均先在只读评审阶段冻结发现，再进入文档修复；修复完成后重新从当前全文开始下一轮，未把作者自检或确定性 validator 结果替代为独立评审结论。

### 16.1 第 1 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-EMP-001` | S1 | 本文未承接上位按 L2 切片判定的 `BQ-GATE-002`，可能把文档通过误解为 Python 实施授权 | 增加本切片实施门禁，并与 provider 变化、真实启用和出域门禁作交集 | Closed |
| `REV-EMP-002` | S1 | 长度≤4的域内掩码特例违反 `L2_02_00 mask_keep_last4` 的 5～256 精确前置条件 | 删除特例，统一复用公共转换并令不满足值失败关闭 | Closed |
| `REV-EMP-003` | S1 | 未声明 no-result 的 404 被写成 invalid_response，与公共 `unavailable` 映射冲突 | 分离 204 与 404，固定 404 为 downstream_failure(`unavailable`) | Closed |
| `REV-EMP-004` | S1 | 文档声称宽字段流式跳过、原始 body 最多64KiB，但 common 先按全局上限聚合且无流式 JSON 依赖 | 区分全局 transport cap 与 Employee 65536-byte codec cap，承认受限临时 object 生命周期并禁止投影/日志/错误回显 | Closed |
| `REV-EMP-005` | S2 | ASCII 字符白名单没有现有接口/数据契约依据，可能误拒合法业务标识 | 改为只解决 path/掩码安全的 Unicode/UTF-8/控制字符边界，业务标识语义仍归 Employee | Closed |

### 16.2 第 2 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-EMP-006` | S1 | Java 只列 guard/detail 方法，未覆盖 Controller 构造器依赖和 Authority 精确读取语义 | 补齐构造器、先 user-token 后 exact Authority 判定、guard-before-service 顺序和签名 | Closed |
| `REV-EMP-007` | S1 | Adapter 侧字段测试不能证明 ADMIN/VIEWER 获准读取现有宽实体，真实复用缺少 provider 权威证据 | 增加 versioned visibility fixture、维护者确认和实际序列化字段集合契约测试；不能确认则转窄 DTO 设计 | Closed |
| `REV-EMP-008` | S2 | 已存在 `CapabilityAccessGuardTest` 被误标为建议新增，实施者可能重复创建测试 | 改为建议修改现有测试，并分离新增 MVC/visibility 测试 | Closed |
| `REV-EMP-009` | S2 | strict JSON、definition/provider 方法和配置 fragment 的输入输出不完整 | 固定 BOM/trailing/NaN/duplicate/字节语义，补齐 definition 与 provider 三个 Protocol 方法签名 | Closed |

### 16.3 第 3 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-EMP-010` | S1 | 动作定义缺 `display_name/description/aliases/argument_schema`，不能形成 L2_00_01 要求的完整 descriptor | 固定完整 descriptor 和受控 JSON Schema，明确 validator 是更严格运行权威 | Closed |
| `REV-EMP-011` | S1 | `mvn -pl employee-service -am test` 在缺少 Maven 聚合入口的仓库根目录不可执行 | 改为 `mvn -f serviceCenter/pom.xml -pl :employee-service -am test`，并统一 Python 测试根路径 | Closed |
| `REV-EMP-012` | S1 | 详情 guard 会收紧现有公开行为，但未盘点旧调用方，也无安全回滚边界 | 把调用方/角色兼容纳入 provider gate，增加 Agent 先停用、provider 显式决策的分层回滚 | Closed |

### 16.4 第 4 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-EMP-013` | S1 | 六字段目录没有 `value_type` 和允许转换集合，无法直接构造公共 `BusinessFieldDefinition` | 补齐每字段 value type、data class、代码可见性和两类 singleton/empty transform 集合，并固定顺序/null 语义 | Closed |
| `REV-EMP-014` | S2 | 敏感标识位于 path，但只有笼统日志要求，没有真实 ingress 可复现验证 | 增加合成 sentinel 经 Gateway/Servlet 的日志零出现验证 `VAL-EMP-005` | Closed |
| `REV-EMP-015` | S2 | `BQ-GATE-002` 的初版表述把 Python provider 代码 wiring 与连接真实 endpoint 混为一谈 | 明确关闭切片门禁可实现完整 Python wiring，但其余门禁开放时只能连接 fake | Closed |

### 16.5 第 5 轮冻结发现、修复与终审

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-EMP-016` | S2 | `BQ-GATE-003` 类型写成未在上位门禁目录使用的 `provider_contract`，门禁报表会产生同 ID 异义 | 与 L1_02 统一为 `slice_implementation`，并在控制动作中标明 Employee provider 公开行为/守卫范围 | Closed |

修复后重新从 REQ/L0/L1、`L2_00_01` 与 `L2_02_00` 契约、当前 Employee Java 事实、descriptor/输入/wire/字段、JWT/Authority、宽响应可见性、状态、配置、生命周期、实现签名、测试、发布回滚和全部开放门禁复核；未发现新的 S0/S1/S2，`REV-EMP-001`～`REV-EMP-016` 全部关闭。评审结论为 Approved；该结论不关闭 `BQ-GATE-002/003`、`CR-GATE-003`、`SA-GATE-004/006`。

### 16.6 直接依赖聚焦一致性复核

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-EMP-017` | S1 | `L2_02_00` v0.3要求codec显式接收同一次wire request；旧签名既不兼容，也无法拒绝provider返回另一员工记录 | 同步新签名并固定响应`idCardNo`与请求标识精确一致；增加错配及并发交错测试，禁止codec保存请求期状态 | Closed |

该聚焦同步不改变动作、接口、字段可见性或门禁。重新复核调用顺序、标识规范化、宽响应生命周期和并发隔离后未发现新的S0/S1/S2，本文保持Approved。

## 17. 实施前检查

- [x] 单动作、现有接口、字段、状态和授权边界已显式定义。
- [x] Adapter 投影与业务服务最终授权未混淆。
- [x] 公开接口不足项保持门禁，不宣称已获修改授权。
- [x] 三轮内部自检完成且无遗留 Blocker/Major。
- [x] 严格详细设计校验通过。
- [x] 五轮独立评审—修复—复核及直接依赖聚焦一致性复核完成，全部S0/S1/S2已关闭。
- [ ] 用户另行授权实施并关闭本切片 `BQ-GATE-002`；`BQ-GATE-003/SA-GATE-004` 仍分别控制 provider 变化与真实启用。

## 18. 当前结论

本文 v0.3 已完成五轮独立评审—修复—复核及直接依赖聚焦一致性复核并 Approved，可作为 `L2_02_01` Employee Adapter 切片的详细设计基线；但设计可实施不等于已获代码实施授权。`BQ-GATE-002/003`、`CR-GATE-003`、`SA-GATE-004/006` 均保持 Open，目标代码、Employee Java/公开行为修改、真实数据调用和模型出域仍禁止。
