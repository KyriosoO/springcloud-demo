# [L2_02_02] 单体 Agent Transaction Adapter 与业务授权联调详细设计 L2

> 文档层级：L2
> 文档状态：Draft

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Transaction Adapter 与业务授权联调详细设计 |
| 文档标识 | `SA-L2-TRANSACTION-ADAPTER-001` |
| 文档编号 | `L2_02_02` |
| 文档路径 | `docs/design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Draft |
| 当前版本 | v0.1 |
| 日期 | 2026-07-31 |
| 适用范围 | Python `agent-transaction-adapter` 的 `transaction.search` 单动作、现有 Transaction 搜索接口映射、条件/排序/页大小收紧、响应/字段投影、业务服务最终角色授权、错误映射和联调门禁 |
| 上位文档 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.2 Approved |
| 直接输入 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v0.2 Approved；[`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4 Approved |
| 外部契约 | `mq-procedure-service` `POST /txn/search`；`transaction-api` search DTO；`auth-service/common-security` 用户 JWT/Authority |
| 实现基线 | 目标 Python Adapter 不存在；现有 search 已要求 user token、至少一项条件、page 1+、size 1～100、排序最多两项，但 guard 未校验角色，统一 Authority converter 未具备 |
| 是否可作为实现依据 | 否 |
| 实施依据说明 | 本文完成内部自检后仍需独立评审、动作/字段/Authority 契约确认并关闭 `BQ-GATE-003/SA-GATE-005` |
| 当前允许范围 | 文档评审、synthetic Transaction fixture、fake HTTP/Authority 契约推演 |
| 当前禁止动作 | 修改 Agent/Java/安全代码、配置、测试或公开契约；调用真实交易数据；启用真实动作、聚合或模型出域；关闭门禁 |
| 修改权限 | 本轮只获授权第三批 L2 及直接相关文档索引原子同步；代码、配置、Schema、接口和真实数据只读 |

> 第一阶段只注册 `transaction.search`，固定 page=1 并只支持标识、类型和金额条件。Java `Date` 的 JSON 格式未形成已验证契约，因此日期条件、日期排序和日期结果暂不进入 Agent；detail/query/condition/aggregate 及写入口全部不可达。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-31 | 全文 | 第三批 L2 依序编写 | 新建 Transaction 单搜索动作、受控条件/排序、响应覆盖、字段分类、授权入口、失败、测试和门禁设计 |
| 2 | 2026-07-31 | 全文 | 第 1 轮内部自检 | 完成结构、追踪、责任、签名、失败、安全、事务、生命周期和门禁检查；严格校验无结构缺口 |
| 3 | 2026-07-31 | 8/9/13/15 章 | 第 2 轮内部自检 | 禁止 LIKE wildcard 扩大、修正 Decimal wire 示例、收紧 exact coverage 和固定 ROUND_HALF_UP |
| 4 | 2026-07-31 | 8/9/12～16 章 | 第 3 轮内部自检 | 补齐内部 wire/record 类型字段，展开精确配置键和 Java 测试路径，完成实施可验证性收口 |
| 5 | 2026-07-31 | 6 章 | 第三批原子一致性同步 | 展开已存在 Transaction Java 类完整路径；不改变三轮内审结论或动作边界 |

## 3. 背景、目标与范围

### 3.1 背景与根因

`TransactionController` 同时公开消息提交、更新、详情、宽条件、分页搜索、聚合、创建和删除。现有 `/txn/search` 是最接近 Agent 只读查询的接口，但其请求复用宽 `Transaction` 条件，公开 Date/金额等多种字段；当前 guard 只验证 user token。若 Adapter 允许模型直接构造该 DTO，可能扩大条件、调用聚合/写入口、混淆日期格式或在业务服务未最终验角色情况下查询。

### 3.2 目标与可观察行为

| 需求编号 | 目标 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-TXN-001` | 只提供一个代码绑定搜索动作 | registry 仅有 `transaction.search@1`；其他 `/txn` 路径调用数为零 | L1_02 6/7；L2_02_00 |
| `REQ-TXN-002` | 条件与排序强类型收紧 | 至少一个已允许条件；page 固定 1；size≤配置≤50；排序≤2 且仅三字段 | L1_02 7.2 |
| `REQ-TXN-003` | 首期排除不稳定 Date wire | Agent 请求/typed record/用户/模型结果均无日期字段；原始响应日期显式跳过 | 当前代码使用 `java.util.Date`，wire 未验证 |
| `REQ-TXN-004` | 业务服务最终验证角色 | 统一安全边界拒绝非法 role；Transaction search 入口仍验证 ADMIN/VIEWER 后才调用 service/mapper | 用户确认；L1_02 7.4 |
| `REQ-TXN-005` | 空结果、覆盖与近似总数真实 | 仅 page1 rows空+total0+exact 可为 no-result；非 exact total 不冒充精确 total | 现有 `TransactionSearchResponse` |
| `REQ-TXN-006` | 结果字段最小化 | 用户最多交易 ID 掩码、类型、金额；模型候选默认空；日期和所有查询辅助字段零投影 | L2_02_00 9/11 |
| `REQ-TXN-007` | 状态与失败稳定 | 400 invalid_argument；401/403/429/5xx/timeout 不混淆；非法 2xx 不变 no-result | L2_02_00 12.1 |
| `REQ-TXN-008` | 一次只读 HTTP、禁止聚合与写入 | 每次最多一次 POST `/txn/search`，无 retry/redirect/第二动作；禁止路径 spy 全零 | L1_02 9.3/10.3 |

### 3.3 范围内

- `transaction.search` descriptor、强类型条件/排序/input、wire request/response、normalizer/provider。
- page1 有界搜索、最多 50 条、现有 total/totalExact 的 coverage 映射。
- `transId/transType/transTypeContains/amount/amountGt/amountLt` 条件和三字段排序。
- Transaction search 入口的最终 Authority 判定建议、字段投影、失败和联调矩阵。

### 3.4 范围外

- 日期条件/排序/输出；detail、condition、query、aggregate、create/update/delete、MQ/Kafka 提交。
- 新增或修改 Transaction 公开 DTO/endpoint、日期格式、数据库查询或分页协议；需另行确认。
- 跨域聚合、跨页遍历、自动翻页、汇总统计和总金额计算。
- Employee、Knowledge、统一 converter 私有实现、DeepSeek Provider/Prompt。

### 3.5 非目标

- 不复刻全部 `Transaction` Java DTO，不允许任意 condition map。
- 不在 Adapter 解释 role claim，不把聚合伪装成 search 后处理。
- 不从错误 body 推断 no-result，不因 total 字段存在而生成未请求的聚合答案。

### 3.6 实施剖面

| 剖面 | 适用 | 说明 |
|---|---|---|
| Python | 是 | Transaction definition、DTO、mapper/codec/normalizer、field/provider/config/test |
| Java/API | 是 | 复用 search wire；建议收紧既有 guard 行为，不改 DTO |
| 安全 | 是 | 原用户 JWT、业务动作角色、金额/标识/日志/模型隔离 |
| 数据库/事务 | 条件适用 | Agent 无事务；业务 search 内 count/query 一致性需按现有响应校验 |
| 模型出域 | 条件适用 | 只定义候选；默认空，真实数据外发另受 `SA-GATE-006` |

## 4. 上位约束

| 约束编号 | 上位位置 | 约束 | 本设计落实 | 偏离 |
|---|---|---|---|---|
| `CON-TXN-001` | L1_02 6/7.2 | 独立 Adapter、代码绑定有限动作、配置只收紧 | `DR-TXN-001`、`DR-TXN-002` | 无 |
| `CON-TXN-002` | L1_02 7.3/7.4 | 用户 JWT 透传、业务服务最终授权 | `DR-TXN-003`、`DR-TXN-004` | 无 |
| `CON-TXN-003` | L1_02 7.5/7.6 | typed result、字段交集和模型默认拒绝 | `DR-TXN-005`、`DR-TXN-006`、`DR-TXN-007` | 无 |
| `CON-TXN-004` | L2_02_00 8.5/12.1 | common status mapper 先处理非 2xx | `DR-TXN-008` | 无 |
| `CON-TXN-005` | L1_02 9.3/10.3 | 一次调用、无重试、禁止聚合/写入 | `DR-TXN-009`、`DR-TXN-010` | 无 |
| `CON-TXN-006` | L1_02 13.3 | 日期/接口差距不由域 L2 擅自改公开契约 | `DR-TXN-011` | 无 |

### 4.1 端到端追踪矩阵

| REQ/CON | 设计规则 | 责任主体 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|
| `REQ-TXN-001`,`CON-TXN-001` | `DR-TXN-001`、`DR-TXN-002` | provider/组合根 | `IMPL-TXN-001/002/007` | `TEST-TXN-001/002` | `VAL-TXN-001/002` |
| `REQ-TXN-002` | `DR-TXN-002`、`DR-TXN-005` | validator/mapper | `IMPL-TXN-003` | `TEST-TXN-003/004` | `VAL-TXN-001` |
| `REQ-TXN-003`,`CON-TXN-006` | `DR-TXN-005`、`DR-TXN-011` | codec/field registry | `IMPL-TXN-003/005` | `TEST-TXN-005` | `VAL-TXN-001/003` |
| `REQ-TXN-004`,`CON-TXN-002` | `DR-TXN-003`、`DR-TXN-004` | 安全边界/Transaction service | `IMPL-TXN-008/009` | `TEST-TXN-006/007` | `VAL-TXN-003/004` |
| `REQ-TXN-005`,`CON-TXN-003` | `DR-TXN-006` | normalizer | `IMPL-TXN-004` | `TEST-TXN-008` | `VAL-TXN-001/003` |
| `REQ-TXN-006` | `DR-TXN-007` | fields/projector | `IMPL-TXN-005/006` | `TEST-TXN-009/010` | `VAL-TXN-001/002` |
| `REQ-TXN-007`,`CON-TXN-004` | `DR-TXN-008` | status mapper/codec | `IMPL-TXN-003/004` | `TEST-TXN-011` | `VAL-TXN-001/003` |
| `REQ-TXN-008`,`CON-TXN-005` | `DR-TXN-009`、`DR-TXN-010` | common client/architecture | `IMPL-TXN-003/007` | `TEST-TXN-012/013` | `VAL-TXN-002` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文责任 | 对方责任 | 权限 |
|---|---|---|---|---|
| `L2_02_00` | 直接依赖 | 实例化公共原语 | HTTP/JWT/result/projector/配置算法 | 只读 |
| `transaction-api` | wire contract | 只消费已核实 search 子集 | Java DTO 和兼容性 | 只读 |
| `mq-procedure-service` | 业务权威 | 映射 search，建议动作 guard | Transaction 数据/查询/最终授权 | 设计建议；代码只读 |
| `auth-service/common-security` | 身份权威 | 定义消费矩阵 | role claim/验签/Authority | 只读 |
| core/DeepSeek 边界 | 上下游 | descriptor/安全字段候选 | 单动作 claim、全局出域和 grounding | 默认拒绝 |

## 6. 当前基线与最小变更

### 6.1 已核实事实

| 状态 | 路径/符号 | 事实 | 影响 |
|---|---|---|---|
| 已存在 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/controller/TransactionController.java` `search` | `POST /txn/search` 且调用 `requireUser` | 可复用只读入口 |
| 已存在 | `TransactionService.search` | 至少一条件、page≥1、size 1～100、最多两 sort；count 后 query | Agent 进一步收紧 page/size/fields |
| 已存在 | `transaction-api/src/main/java/com/dylan/transaction/api/query/TransactionSearchRequest.java` | condition 复用宽 Transaction；sort/page/size | 只构造子集，不动态透传 |
| 已存在 | `TransactionSearchResponse.java` | rows/total/totalExact/page/size；非 exact 时 total 是下界 | coverage 必须保真 |
| 已存在 | `Transaction.java` | Date、BigDecimal 及辅助 filter 字段同 DTO | 首期忽略 Date/辅助响应字段 |
| 已存在但不足 | Transaction `CapabilityAccessGuard.requireUser` | 只校验 user token | 需动作角色 guard 证据 |
| 缺失 | `common-security` role converter、Python Adapter | Authority/目标代码均未闭环 | 真实动作保持 disabled |

### 6.2 最小改造判断

复用 `/txn/search`，不新增接口或 DTO。Python 仅构造现有 DTO 的安全子集；Provider 侧仅建议把现有 `requireUser` 收紧/替换为 Transaction search 动作角色检查。日期 wire 没有显式 Jackson 配置或契约测试，因此首期排除而不是猜格式。搜索已有明确空结果和 400 语义，可直接映射，不需要 Provider 状态改造。

## 7. 责任分解、依赖方向与耦合

### 7.1 责任分解

| 组件 | 唯一职责 | 明确不负责 |
|---|---|---|
| Transaction definition/provider | 冻结一个 action、字段、filter/sort/limits | 聚合、HTTP、安全实现 |
| validator/mapper/codec | 强类型条件→既有 search wire；严格 2xx 解码 | 动态 Transaction map、role、第二请求 |
| normalizer/fields | coverage 和最小结果 | 总金额聚合、日期猜测、业务授权 |
| common handler/client/projector | 一次 JWT HTTP、公共状态/字段交集 | Transaction 端点和字段语义 |
| Transaction Controller/guard/service | 动作角色授权、查询事实和响应 | Agent 配置/模型答案 |

### 7.2 依赖方向与调用边界

```text
agent-runtime registry
  -> TransactionDomainProvider
     -> BoundBusinessActionHandler
        -> TransactionSearchMapper/Codec
        -> UserJwtBusinessHttpClient -> POST mq-procedure-service /txn/search
           -> TransactionReadAccessGuard -> TransactionService -> TransactionMapper
        -> TransactionSearchNormalizer -> common user/egress projectors
```

禁止依赖与绕过：Adapter 不得导入 Employee、Java DTO、Mapper、DB/MQ/Kafka/ES client；core 不得导入 Transaction 字段；配置/模型不得选择 path/method/Date/aggregate；`mq-procedure-service` 不得把 Adapter 投影当授权；模型不得触发自动翻页或第二动作。

### 7.3 内聚与耦合判断

Transaction 条件、wire 和 coverage 随业务 search 契约变化，内聚在 Transaction Adapter；JWT client/状态/投影留在 business common；角色与数据查询留在业务服务。模块只通过 action definition、现有 JSON wire 和 Authority 可观察契约耦合，不共享私有 DTO，后续验证 Date 时可只扩展 Transaction definition/codec/test，不修改 core、Employee 或 common 算法。

## 8. 动作、输入、wire 与字段契约

### 8.1 动作定义

| 定义字段 | 冻结值 |
|---|---|
| `descriptor.capability_id` | `transaction.search` |
| `api_version/kind` | `1/query` |
| `domain_id/service_key` | `transaction/mq-procedure-service` |
| `answer_mode` | `model_assisted`，但结构化本地结果可独立返回 |
| `applicable_dimensions` | `max_page_size,max_result_count,filter_fields,sort_fields` |
| filter code set | `trans_id,trans_type,trans_type_contains,amount,amount_gt,amount_lt` |
| sort code set | `trans_id,trans_type,amount` |
| contract limits | page size/result≤50；timeout≤5000ms；request≤4096 bytes；无 time range |
| status semantics | 400→invalid_argument；204/404 不声明 no-result |
| required user fields | `transaction_id_masked,transaction_type,amount` |

### 8.2 强类型输入

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSearchInput:
    trans_id: str | None
    trans_type: str | None
    trans_type_contains: str | None
    amount: Decimal | None
    amount_gt: Decimal | None
    amount_lt: Decimal | None
    size: int
    sorts: tuple[TransactionSort, ...]
```

| 类型 | 精确字段 | 不变量 |
|---|---|---|
| `TransactionSort` | `field: Literal["trans_id","trans_type","amount"]`；`direction: Literal["ASC","DESC"]` | tuple 最多2，field唯一 |
| `TransactionSearchCondition` | 六个与 input 同名的可空字段 | 至少一项；互斥/范围已验证；冻结 |
| `TransactionSearchWireRequest` | `condition: TransactionSearchCondition`；`sorts: tuple[TransactionSort,...]`；`page: Literal[1]`；`size: int` | 只由 mapper 构造，size≤有效上限 |
| `TransactionRecord` | `trans_id: str`；`trans_type: str`；`amount: Decimal` | 三字段非空、有界，不含 Date |
| `TransactionSearchWireResponse` | `rows: tuple[TransactionRecord,...]`；`total: int`；`total_exact: bool`；`page: int`；`size: int` | 8.4 coverage 不变量 |

- arguments 只接受上述 snake_case key；未知/重复 key 拒绝，至少一个条件非空。
- 标识 NFC/trim 1～128，类型/contains 1～128；禁止控制/Bidi 字符；`trans_type` 与 `trans_type_contains` 互斥。由于现有 SQL `LIKE concat('%', value, '%')` 未转义，`trans_type_contains` 还必须拒绝 `%`、`_` 和反斜线，避免调用方注入通配语义。
- amount 参数在 capability JSON 中必须为十进制定点字符串，匹配可选负号、1～16 位整数、可选 1～4 位小数；转 `Decimal` 后 absolute≤`9999999999999999.9999` 且 finite。
- `amount` 与 gt/lt 互斥；gt/lt 同时存在时必须 `gt < lt`。配置禁用的 filter 在 HTTP 前 invalid_argument。
- page 不暴露，wire 固定 1；size 1～有效 `max_page_size/max_result_count` 较小值，默认 20。
- sorts 0～2 项，field 只取有效 sort 子集，direction 只允许 `ASC/DESC`；field 不重复。

### 8.3 HTTP wire request

唯一请求为 `POST /txn/search`：

```json
{
  "condition": {
    "transId": "optional",
    "transType": null,
    "transTypeContains": null,
    "amount": null,
    "amountGt": 100.5,
    "amountLt": null
  },
  "sorts": [{"field":"amount","direction":"DESC"}],
  "page": 1,
  "size": 20
}
```

实际 Decimal 必须编码为 canonical JSON number，不带引号、指数、正号或多余尾零；实施测试必须断言原始 JSON token 为 number。空条件字段建议省略，不发送 `transDate/transDateGt/transDateLt` 或响应专用字段。body 使用 unique keys、UTF-8、≤4096 bytes；无 query 和自定义 header。

### 8.4 2xx wire response 与 coverage

顶层精确消费 `rows,total,totalExact,page,size`，要求 page=1、size=请求 size、total≥0、rows 数量≤size。每行只读取 `transId/transType/amount`，显式跳过 `transDate` 及其他未知字段；三目标字段必须存在、非 null 且类型正确。ID/type 上限128；amount 必须 JSON number、finite、可转有界 Decimal。duplicate key、非法字段类型、body>256 KiB 或 rows>size 整体 invalid_response。

normalizer 规则：

- rows 空、total=0、totalExact=true → `no_result(returned=0,truncated=false,total_count=0)`。
- rows 非空、totalExact=true → records；要求 `rows数=min(total,size)`，`total_count=total`，`truncated=(rows数<total)`；page1 出现不足页但 total 声称更多时视为 count/query 矛盾。
- rows 非空、totalExact=false → records；`total_count=None,truncated=true`，保留“不完整”而不把 total 下界当精确值。
- rows 空但 total>0 或 totalExact=false、page/size 不回显、任一行不合法 → invalid_response。

### 8.5 字段目录与转换

| field_id | source | class | user | model candidate | user transform | model transform |
|---|---|---|---:|---:|---|---|
| `transaction_id_masked` | `transId` | `transaction_identifier` | 是/必需 | 否 | `mask_keep_last4` | 不适用 |
| `transaction_type` | `transType` | `business_internal` | 是/必需 | 是 | `bounded_text` | `bounded_text` |
| `amount` | `amount` | `financial_value` | 是/必需 | 是 | `decimal_2` | `decimal_2` |

模型字段代码候选是 `transaction_type,amount`，动作配置默认空，且仍受全局规则交集。`decimal_2` 使用 Decimal 并精确采用 `ROUND_HALF_UP`，不得经过 float；交易 ID 永不成为模型候选。结果只表达当前页记录，不生成计数、合计、平均或趋势结论。

## 9. 详细功能与处理流程

### 9.1 设计规则

| 规则编号 | 规则 | 责任主体 | 效果 |
|---|---|---|---|
| `DR-TXN-001` | 只定义并注册 `transaction.search@1` | provider/组合根 | 动作有限 |
| `DR-TXN-002` | 配置只能禁用、缩小 filter/sort/size/result/timeout/字段，不能增加 Date/路径/动作 | settings/provider | 配置不扩权 |
| `DR-TXN-003` | Adapter 只透传当前 user JWT，不解析 role、不使用 service token | handler/client | 身份不替换 |
| `DR-TXN-004` | 统一边界先验证 role；Transaction search 再要求 ADMIN/VIEWER Authority 后调用 service | common-security/业务入口 | 最终动作授权 |
| `DR-TXN-005` | mapper 执行条件互斥、Decimal、filter/sort/page/size 收紧并只构造现有 DTO 子集 | mapper/codec | 请求有界 |
| `DR-TXN-006` | normalizer 严格解释 rows/total/exact/page/size，非 exact total 不进入 total_count | normalizer | coverage 真实 |
| `DR-TXN-007` | 用户仅三字段，模型默认空；模型结果不得生成聚合/全量结论 | fields/egress | 字段和语义收紧 |
| `DR-TXN-008` | 400/401/403/429/5xx 由 common 固定映射，域不读错误 body | status mapper | 状态稳定 |
| `DR-TXN-009` | 一次动作最多一个 POST，共享绝对截止，无 retry/redirect/cache/自动翻页 | handler/client | 资源有界 |
| `DR-TXN-010` | 所有非 search 路径和 MQ/Kafka/aggregate 代码在 Adapter 架构测试中不可达 | codec/architecture | 无副作用/聚合 |
| `DR-TXN-011` | Date 输入/输出保持代码禁用，只有 wire 契约和时区测试确认后才可另行设计扩展 | definition/codec | 不猜日期 |

### 9.2 正常序列

1. core 以同一 descriptor validator 产生 typed input 并 claim 单动作。
2. handler 校验 context/token/deadline；mapper 依据冻结 settings 校验条件和排序。
3. codec 构造唯一 POST body，common client 向绑定 service origin 发送一次原用户 JWT。
4. 统一安全边界及 Transaction search guard 在 service 前完成角色验证；拒绝时 mapper/DB 为零。
5. `TransactionService.search` 最多执行 count/query 并返回现有 typed response。
6. Adapter 校验响应/coverage，只提取三字段；空与 records 按 8.4 映射。
7. user projector 生成掩码/decimal 结果；egress 默认空并直接返回结构化本地结果。

### 9.3 配置

建议新增动作前缀 `AGENT_TRANSACTION_SEARCH_`：

| key | 默认 | 约束 |
|---|---|---|
| `AGENT_TRANSACTION_SEARCH_ENABLED` | `false` | 真实门禁关闭前不得 true |
| `AGENT_TRANSACTION_SEARCH_TIMEOUT_MS` | `3000` | 100～5000 |
| `AGENT_TRANSACTION_SEARCH_MAX_PAGE_SIZE` | `20` | 1～50 |
| `AGENT_TRANSACTION_SEARCH_MAX_RESULT_COUNT` | `20` | 1～50；有效 size 取二者较小值 |
| `AGENT_TRANSACTION_SEARCH_FILTER_FIELDS` | 六个代码条件 | 只能取子集且非空 |
| `AGENT_TRANSACTION_SEARCH_SORT_FIELDS` | 三个代码排序字段 | 只能取子集，可空 |
| `AGENT_TRANSACTION_SEARCH_USER_FIELDS` | 三字段 | 子集且保留全部 required |
| `AGENT_TRANSACTION_SEARCH_MODEL_FIELDS` | 空 | 仅 type/amount 子集 |
| `AGENT_TRANSACTION_SEARCH_USER_TRANSFORMS` | 代码表固定 | 每用户字段恰一允许枚举 |
| `AGENT_TRANSACTION_SEARCH_MODEL_TRANSFORMS` | 空 | 每模型字段恰一允许枚举 |

service origin 只由组合根 `mq-procedure-service` binding 提供。未知 key、空 filter 集、Date 字段、移除 required、非法 sort/transform 或上限扩大均阻止 Runtime 就绪。

## 10. 失败类型、权限与审计

### 10.1 失败类型与错误码矩阵

| 触发 | Service result | 公共结果 | HTTP/模型 |
|---|---|---|---|
| context/token 缺失 | unauthenticated | `business.missing_user_token` | 0/0 |
| token 认证失败 | unauthenticated | `business.downstream_unauthenticated` | ≤1/0 |
| role/动作 Authority 拒绝 | forbidden | `business.downstream_forbidden` | ≤1；service/DB0；模型0 |
| typed input/config filter 非法 | invalid_argument | `business.invalid_arguments` | 0/0 |
| Transaction 400 | invalid_argument | `business.invalid_arguments` | 1/0 |
| rows空且 exact total0 | no_result | no_result | 1/0 |
| 合法 records | records | success | 1/0或1 |
| 非法 2xx/204/404/body超限 | invalid_response | `business.invalid_response` | 1/0 |
| timeout/429/5xx/connect | typed common failure | common 固定 code | ≤1/0 |

### 10.2 权限与审计

建议将现有 search 调用改为 `CapabilityAccessGuard.requireTransactionRead(Authentication)`：复用 user-token 校验，并要求已验证 Authority 含 `ROLE_ADMIN` 或 `ROLE_VIEWER`；原始 role 的缺失/未知/大小写错/混合未知由统一 converter 在 Controller 前整体 403。guard 不解析 claim，不按用户名判断。`TransactionController.search` 必须在 `TransactionService.search` 前调用，拒绝时 service/mapper 为零。

日志只允许 correlation ID、动作 ID、有限 filter/sort ID（不含值）、page size、returned count、truncated/exact 状态、耗时和 snapshot ID。禁止 JWT、subject、条件值、交易 ID（含掩码）、金额、类型文本、请求/响应 body、URL query、异常 message/stack。真实数据和具体交易问题进入 DeepSeek 前仍受 `CR-GATE-003/SA-GATE-006`。

### 10.3 事务边界与一致性

Agent 无事务、持久化、缓存或重试。业务 search 当前先 count 后 query，代码未证明两次读取位于同一数据库快照；Adapter 不伪造强一致性。它只验证响应内部不变量，`totalExact=false` 时不输出精确 total；并发变更造成 rows空但 total>0 等矛盾时失败为 invalid_response。若未来要求快照一致或 cursor，必须由业务服务另行设计，不能在 Adapter 重查补偿。

## 11. 数据生命周期、发布与回滚

### 11.1 数据生命周期

输入条件、canonical request、原始 2xx body和 typed rows 只在单次请求内存中存活；body 最多256 KiB，投影后释放。原始交易 ID、金额和类型不持久化/缓存/日志。用户结果只保留 ID 掩码、类型和金额；模型 safe payload 即使获准也无 ID，且只存在于一次模型调用。

### 11.2 发布与回滚

1. synthetic fake 先完成条件、Decimal、wire、coverage、禁止路径和模型零调用测试。
2. 单独实施统一 converter/Transaction guard，并回归现有 search/aggregate；Agent 不调用 aggregate。
3. provider/consumer、角色和数据库 spy 矩阵通过后才允许真实 search；Date 仍禁用。
4. 回滚将 `AGENT_TRANSACTION_SEARCH_ENABLED=false` 并重启 Runtime，不切换到 detail/query/condition/aggregate。

本文不含数据迁移。Date、窄响应、cursor 或权限响应变化均需独立公开契约设计和兼容回滚。

## 12. 实现落点与关键签名

### 12.1 实现落点

| 编号 | 状态 | 路径/符号 | 责任 | 规则 |
|---|---|---|---|---|
| `IMPL-TXN-001` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/definition.py` | descriptor/limits/filter/sort/fields | `DR-TXN-001/002` |
| `IMPL-TXN-002` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/contracts.py` | input/sort/wire/record | `DR-TXN-001/005/006` |
| `IMPL-TXN-003` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/codec.py` | validator/mapper/POST encode/2xx decode | `DR-TXN-002/005/008/011` |
| `IMPL-TXN-004` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/normalizer.py` | rows/total/exact→service result | `DR-TXN-006/008` |
| `IMPL-TXN-005` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/fields.py` | 三字段/转换/无 Date | `DR-TXN-007/011` |
| `IMPL-TXN-006` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/settings.py` | 精确 env fragment/default | `DR-TXN-002/007` |
| `IMPL-TXN-007` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/provider.py` | TransactionDomainProvider | `DR-TXN-001/009/010` |
| `IMPL-TXN-008` | 建议修改 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java` | Transaction 读 Authority 判断 | `DR-TXN-004` |
| `IMPL-TXN-009` | 建议修改 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/controller/TransactionController.java` `search` | search 前调用动作 guard | `DR-TXN-004` |

### 12.2 Python 关键方法

| 符号 | 签名 | 输入/输出 | 副作用 |
|---|---|---|---|
| `TransactionSearchArgumentValidator.validate` | `def validate(self, arguments: JsonObject) -> TransactionSearchInput` | 条件/Decimal/sort/size typed input | 纯函数 |
| `TransactionSearchRequestMapper.map` | `def map(self, input: TransactionSearchInput, settings: BusinessActionSettings) -> TransactionSearchWireRequest` | filter/sort/settings 交集；page1 | 纯函数 |
| `TransactionSearchWireCodec.encode` | `def encode(self, request: TransactionSearchWireRequest) -> BusinessHttpRequest` | canonical POST body | 纯函数 |
| `TransactionSearchWireCodec.decode_success` | `def decode_success(self, response: BoundedBusinessHttpResponse) -> TransactionSearchWireResponse` | rows/coverage/三字段 | 有界解析 |
| `TransactionSearchResponseNormalizer.normalize_success` | `def normalize_success(self, response: TransactionSearchWireResponse) -> BusinessServiceResult[TransactionRecord]` | 8.4 exact/no-result/records | 纯函数 |
| `TransactionDomainProvider.definitions` | `def definitions(self) -> tuple[BusinessActionDefinition[Any,Any,Any,Any], ...]` | 恰含 `transaction.search` | 纯函数 |

### 12.3 Java 关键方法

| 类/方法 | 建议签名 | 前置/返回 | 副作用 |
|---|---|---|---|
| `CapabilityAccessGuard.requireTransactionRead` | `void requireTransactionRead(Authentication authentication)` | user JWT；含 ADMIN/VIEWER Authority，否则403 | service/mapper 0 |
| `TransactionController.search` | 已存在 `TransactionSearchResponse search(Authentication, TransactionSearchRequest)` | 将 guard 调用收紧后保持 wire | 一次 service |
| `TransactionService.search` | 已存在 `TransactionSearchResponse search(TransactionSearchRequest)` | 本文不修改签名/算法 | count≤1/query≤1 |

## 13. 测试与验证设计

### 13.1 测试矩阵

| 测试编号 | 规则 | 层级 | 建议路径/场景 | 关键断言 |
|---|---|---|---|---|
| `TEST-TXN-001` | `DR-TXN-001/002` | Unit | 建议新增：`tests/unit/adapters/transaction/test_definition.py` | 唯一 action；Date/aggregate 不在定义/配置 |
| `TEST-TXN-002` | `DR-TXN-001/010` | Architecture | 建议新增：`tests/architecture/test_transaction_adapter_boundaries.py` | 无 Employee/Java/DB/MQ/ES/retry；禁止 path 字面量零 |
| `TEST-TXN-003` | `DR-TXN-002/005` | Unit | 建议新增：`tests/unit/adapters/transaction/test_arguments.py` | 条件互斥/至少一项/LIKE wildcard/Decimal/page1/size边界 |
| `TEST-TXN-004` | `DR-TXN-002/005` | Contract | 建议新增：`tests/contract/adapters/transaction/test_search_request.py` | canonical numeric token、filter/sort 子集、精确 POST body |
| `TEST-TXN-005` | `DR-TXN-005/011` | Contract | 建议新增：`tests/contract/adapters/transaction/test_date_exclusion.py` | Date args/config/request/record/result 全拒绝或跳过 |
| `TEST-TXN-006` | `DR-TXN-003/004` | Java Unit | 建议新增：`mq-procedure-service/src/test/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuardTest.java` | ADMIN/VIEWER allow；无动作角色 deny |
| `TEST-TXN-007` | `DR-TXN-004` | Java MVC/Contract | 建议新增：`mq-procedure-service/src/test/java/com/dylan/mqprocedureserver/controller/TransactionControllerAuthorizationTest.java` | invalid/mixed role 在安全边界403；deny service/mapper0；allow一次 |
| `TEST-TXN-008` | `DR-TXN-006` | Parameterized | 建议新增：`tests/unit/adapters/transaction/test_coverage.py` | rows/total/exact/page/size 笛卡尔边界 |
| `TEST-TXN-009` | `DR-TXN-007` | Unit | 建议新增：`tests/unit/adapters/transaction/test_fields.py` | ID mask、Decimal2、三 required、无 Date |
| `TEST-TXN-010` | `DR-TXN-007` | Model spy | 建议新增：`tests/integration/adapters/transaction/test_egress.py` | 默认0；仅type/amount；禁止聚合/越界事实 |
| `TEST-TXN-011` | `DR-TXN-008` | Parameterized | 建议新增：`tests/unit/adapters/transaction/test_status.py` | 400/401/403/204/404/429/5xx且错误body读取0 |
| `TEST-TXN-012` | `DR-TXN-009` | Async HTTP | 建议新增：`tests/integration/adapters/transaction/test_deadline_single_call.py` | HTTP≤1、无retry/自动翻页、取消/迟到丢弃 |
| `TEST-TXN-013` | `DR-TXN-010` | Security spies | 建议新增：`tests/integration/adapters/transaction/test_forbidden_endpoints.py` | detail/query/condition/aggregate/write/MQ/Kafka调用全0 |

### 13.2 验证命令

| 编号 | 命令 | 证明范围 | 当前状态 |
|---|---|---|---|
| `VAL-TXN-001` | `python -m pytest tests/unit/adapters/transaction tests/contract/adapters/transaction -q` | definition/input/wire/coverage/fields/status | 未执行：代码不存在 |
| `VAL-TXN-002` | `python -m pytest tests/integration/adapters/transaction tests/architecture/test_transaction_adapter_boundaries.py -q` | 单调用、禁止接口、模型/日志边界 | 未执行：代码不存在 |
| `VAL-TXN-003` | `mvn -pl transaction-api,mq-procedure-service -am test` | provider DTO/search/guard/MVC 回归 | 未执行：未获代码授权 |
| `VAL-TXN-004` | ADMIN/VIEWER/unknown/missing/malformed/service-token 真实 JWT 矩阵 | Authority/业务最终授权/mapper 次数 | 未执行：converter/guard 差距未关闭 |

## 14. 风险、门禁与授权

### 14.1 风险

| 编号 | 风险 | 触发 | 影响 | 处置 |
|---|---|---|---|---|
| `RISK-TXN-001` | Date wire 未验证 | 日期查询/结果 | 时区/格式错误 | 首期代码排除，后续独立契约测试 |
| `RISK-TXN-002` | count/query 非同一已证明快照 | 并发写 | total/rows 矛盾 | 严格不变量；不重查；业务侧另行设计 |
| `RISK-TXN-003` | Decimal wire/scale | 大值/小数 | 精度漂移 | string输入→Decimal→canonical number；provider contract |
| `RISK-TXN-004` | Authority 未闭环 | 真实 search | 越权/误拒绝 | converter+guard+mapper spy 矩阵 |
| `RISK-TXN-005` | 聚合端点相邻且现存 | 动态 path/模型越界 | 超范围统计或大查询 | codec唯一 path、架构和HTTP spy零调用 |
| `RISK-TXN-006` | total 非 exact | 大结果集 | 用户误读总数 | total_count=None、truncated=true、禁止聚合话术 |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 控制动作 | 关闭条件 | 责任方 | 状态 | 未关闭允许/禁止 |
|---|---|---|---|---|---|---|
| `BQ-GATE-003` | provider_contract | 修改 Transaction guard/公开契约 | 维护者确认 search 子集、角色 guard、Decimal/400/coverage 语义及代码范围 | 维护者/Transaction 方 | Open | 允许设计/fake；禁止 Java/API 修改 |
| `CR-GATE-003` | integration | 具体交易问题进入 DeepSeek | 全局问题闸门对交易 ID、金额和敏感文本形成批准路径或零调用 | 维护者/模型方 | Open | 允许 synthetic explicit action；禁止真实敏感问题外发 |
| `SA-GATE-005` | integration | 启用真实 Transaction | 本文独立评审；Authority、guard、Decimal/coverage、禁止接口和角色矩阵通过 | 维护者/安全/Transaction 方 | Open | 允许 fake；禁止真实交易查询 |
| `SA-GATE-006` | integration | 真实交易结果进入 DeepSeek | 字段交集、facts/grounding、无聚合越界、零调用测试通过 | 维护者/模型方 | Open | 允许本地结构化结果；禁止真实外发 |

### 14.3 后续需授权

- 新增 Python Transaction Adapter、配置和测试。
- 修改 Transaction guard/controller/test 或统一 Authority converter。
- 变更 Date/公开 DTO/数据库一致性、启用真实 search 或外发真实结果。

## 15. 内部自检记录（作者内审）

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-31 | 0 | 0 | 0 | 0 | 0 | 结构与追踪完整，首次严格校验 0 error/0 warning |
| 2 | 2026-07-31 | 0 | 2 | 2 | 4 | 0 | wildcard、Decimal、exact coverage 和 rounding 语义已收紧 |
| 3 | 2026-07-31 | 0 | 1 | 2 | 3 | 0 | wire/record 类型、精确配置键和 Java 路径已补齐 |

## 16. 实施前检查

- [x] 单 search 动作、现有接口、条件/排序、字段和授权边界已定义。
- [x] Date、聚合、自动翻页和写入口均明确不可达。
- [x] 公开接口/安全不足保持开放门禁。
- [x] 三轮内部自检完成且无遗留 Blocker/Major。
- [x] 严格详细设计校验通过。
- [ ] 独立评审及 `BQ-GATE-003/SA-GATE-005` 关闭。

## 17. 当前结论

本文为 Draft，只支持 Transaction fake、独立评审和实施范围确认。真实 Transaction 查询、Java guard 修改、Date 能力和真实数据模型出域均保持禁止。
