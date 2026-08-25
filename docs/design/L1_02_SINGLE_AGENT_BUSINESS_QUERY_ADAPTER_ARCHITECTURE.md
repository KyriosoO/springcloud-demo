# [L1_02] 单体 Agent Business 查询与适配架构

> 文档层级：L1
> 文档状态：Approved

## 1. 文档信息、来源与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.1 |
| 更新日期 | 2026-08-25 |
| 上位文档 | [`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v2.0 |
| 关联 L1 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v2.0 |
| 权威范围 | Business filters QueryPlan、统一字段配置、三动作 Adapter、最终授权与结果投影 |
| 当前实现 | filters/config、三个列表动作、生产组合根、Controller 读取守卫和 Employee ES 专用 JWT 角色转换均已实施；完整安全链回归已通过，成功真实联调和 UAT 尚未完成 |
| 归档来源 | [v1.4 已评审旧版](历史文档/L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE_v1.4.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 架构目标、非目标与上位约束映射

唯一负责 Employee/Transaction 现有只读列表接口的逻辑计划、字段级配置、固定 Adapter 和响应边界。不负责生成 SQL/ES DSL、业务数据库访问、业务角色判定、Knowledge 流程、新业务接口/DTO、写入或聚合。

上位约束映射：`SA-AD-001` 固化 LLM 单计划/单调用；`SA-AD-002` 限定三个已核实 endpoint；`SA-AD-003` 限定配置收紧；`SA-AD-004` 要求业务最终授权和受保护输入；`SA-AD-005` 禁止旧证据冒充新实现。

## 3. 已核实接口与能力缺口

| 动作 | 固定业务接口 | 已核实能力 | 当前缺口 |
|---|---|---|---|
| `employee.search` | `POST /employees/es/search` | keyword、`eq/contains/prefix/in`、分页、排序、原始 ES hits；Agent Adapter、读取守卫与专用共享 converter 已实施 | 成功受控真实联调和正式 UAT 尚未完成 |
| `employee.semantic_search` | `POST /employees/es/vector-search` | `queryText` 向量检索和受控 k；无结构化 filter；Agent Adapter、读取守卫与专用共享 converter 已实施 | 成功受控真实联调和正式 UAT 尚未完成 |
| `transaction.search` | `POST /txn/search` | 类型、标识、Date、BigDecimal、page/size、最多两个 sort；Agent Adapter 已实施 | 当前仍缺新版本受控真实联调与正式 UAT 证据 |

Employee `keyword` 只匹配 `contactAddress/chineseName/idCardNo`，且必须复用与 filter 相同的 `literal/value_ref` 输入保护；真实姓名、员工标识和详细地址不能作为明文 keyword 出域。当前语义接口不能表达“语义匹配 + contact_address 过滤”；必须 unsupported，不能调用两个接口或客户端补筛。

## 4. Business 唯一数据流与职责边界

```text
输入安全闸门与 request-local slots → LLM QueryPlan → Model framing decoder → Business exact decoder
→ code/config validator → request-scoped protected binder
→ 单一 ActionCandidate → 固定 Domain Adapter
→ 业务服务最终授权/ES/向量/SQL → 安全列表投影
```

Model 只认识逻辑 domain/action/field/operator；Business 公共层拥有 strict plan/config/slot；域 Adapter 拥有固定 endpoint、DTO 映射和 response codec；业务服务拥有最终授权与物理查询。依赖方向不得逆转，禁止 Local Resolver、ID-only 参数补齐、跨域/Knowledge fallback 和 Employee 普通/语义互相 fallback。

## 5. QueryPlan、统一字段配置与模型目录

顶层 exact 三字段 `domain/action/arguments`。列表 arguments 采用 `filters/page/size/sorts`；filter 为 `field/operator/value`，value 只能为 `literal` 或当前请求 `value_ref`；同字段可组合 `gt + lt`，不能重复同 operator、冲突 eq/range 或丢弃未知条件。unsupported 仅允许 exact sentinel，且业务调用为 0。

一份版本化、强类型、默认拒绝 JSON 配置声明 domain/action/field、模型安全描述、operator、输入 exposure、必填/组合、Decimal/日期、分页/排序、用户结果、分类/脱敏和模型出域；Employee keyword 另以动作级受控策略定义启用状态、输入保护及代码绑定的既有三字段集合。启动时校验 version/snapshot、definition/validator/mapper/codec 对齐、service contract reference、所有字段和 operator 子集；`workBaseSi/workBaseAf` 永远不能通过配置直接启用。

### 5.1 Employee 字段

`contact_address → contactAddress`、`chinese_name → chineseName`、`employee_identifier → idCardNo`、`member_no → memberNo`、`phone_no → phoneNo`、`email → email`、`position → position`。地址仅允许有限安全地点片段如“上海”作为 literal；详细地址、姓名、标识、会员号、电话和邮箱必须使用 protected slot。`workBaseSi/workBaseAf` 数据无效，排除查询目录、结果字段、模型目录及成功用例。

### 5.2 Transaction 字段与操作符

`trans_id:eq`；`trans_type:eq/contains`；`trans_date:eq/gt/lt`；`amount:eq/gt/lt`。逻辑 field/operator 分离；DTO `transTypeContains/transDateGt/transDateLt/amountGt/amountLt` 仅为 Adapter 私有映射。Date 采用明确 offset 与 `Asia/Shanghai` 合同；未验证自然日边界时相对日期 unsupported。金额采用 canonical decimal string → JSON number → BigDecimal，scale≤2；page 不固定为 1，size≤50 且不突破服务上限 100，最多两个排序字段。

## 6. 业务最终授权、响应与模型出域

Employee 两个 ES 入口已由 Controller 执行 `requireEmployeeRead`，但必须同时使用仅覆盖这两个既有 POST endpoint 的专用 Servlet 安全链，显式绑定共享 `userRoleJwtAuthenticationConverter`，以满足 `L2_00_03 DR-AUTH-007`。现有 detail 专用链和其他 endpoint 的通用认证行为保持不变；业务读取授权仍由 Employee 服务守卫最终判定。必须用真实 Spring Security 过滤链验证 ADMIN/VIEWER 允许、denied/missing/malformed/service-token 拒绝及既有调用方兼容。Transaction 保持现有 `requireTransactionRead`；Agent 只透传当前用户 JWT，不判断域内角色。

Employee Adapter 对原始 ES JSON 执行 content-type、最大字节数、JSON duplicate key、hits 结构和 `_source` 白名单校验；未知、workBase、`embedding`、`embeddingText` 默认丢弃。Transaction 解析既有 rows/total/totalExact/page/size 合同；`totalExact=false` 不是精确总数。

用户可见字段与模型可见字段各自执行 `代码允许 ∩ 配置允许 ∩ 分类允许`。标识、姓名、联系方式、详细地址、JWT 和业务原始响应不可出域；未分类、冲突或敏感转换失败必须零模型调用。

## 7. 错误分类与调用计数

| 场景 | 对外语义 | 允许业务调用 |
|---|---|---|
| 模型不可用/超时 | `unavailable/timeout` | 0 |
| 非法 JSON、tag、slot、Decimal、Date、page、sort | `invalid_argument` | 0 |
| 未启用动作/字段、workBase、语义+结构组合 | `unsupported` | 0 |
| 服务最终授权拒绝 | `unauthenticated/forbidden` | 至多 1 次既定 endpoint |
| 业务无匹配结果 | `no_result` 或空列表 | 1 |
| 服务响应非法 | `invalid_response` | 1，不重试 |

## 8. 关键架构决策与下位 L2 详细设计

| 决策 | 内容 | 下位设计 |
|---|---|---|
| `BQ-AD-001` | filters/operator/tagged value 与统一收紧型字段配置 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v2.1 |
| `BQ-AD-002` | Employee search/semantic 两动作、ES hits parsing、端点级统一角色转换与业务最终授权 | [`L2_02_01`](L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v2.2 |
| `BQ-AD-003` | Transaction Date/Decimal、分页、排序和 Java DTO 固定映射 | [`L2_02_02`](L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v2.0 |

关联 L1 协作：Runtime L1 拥有组合根和 Core 单动作；Model L2 拥有安全 catalog/Prompt 与 provider framing decoder；Business L2 不改变公共 Core/HTTP/业务 DTO。

## 9. 当前实现、风险与验证

本版 filters 合同、统一配置、三个 Adapter、生产组合根和 non-live 回归已实施；旧 `employee.detail` 不在新目标生产注册表。首次受控联调的真实 LLM 已生成上海 `contact_address contains` 计划，但旧安全链导致 ADMIN 403；现已通过 endpoint-scoped 共享 converter 修复，并以两个 ES 入口完整角色矩阵及 detail/fallback 兼容测试验证。该历史失败证据不可替代修复后的成功受控联调或正式 UAT。

主要风险为 Employee ES 现有调用方兼容性、原始 hits 泄漏、受保护值出域、Date/Jackson/数据库精度不一致和 workBase 虚假可用。通过受限 Adapter、角色矩阵、严格跨语言合同、配置 snapshot、零调用断言及非 live 优先顺序控制；不引入配置中心、规则引擎或多层重复门禁。
