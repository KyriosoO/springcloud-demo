# [L2_02_02] 单体 Agent Transaction Adapter 与业务授权联调详细设计 L2

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Transaction Adapter 与业务授权联调详细设计 |
| 文档标识 | `SA-L2-TRANSACTION-ADAPTER-001` |
| 文档编号 | `L2_02_02` |
| 文档路径 | `docs/design/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | v0.3 已完成两轮独立复评—修复—复核，`REV-TXN-021` 已关闭且未发现新的 S0/S1/S2；v0.2 的 `REV-TXN-001`～`REV-TXN-020` 历史发现保持关闭 |
| 当前版本 | v0.3 |
| 日期 | 2026-08-01 |
| 适用范围 | Python `agent-transaction-adapter` 的 `transaction.search` 单动作、现有 Transaction 搜索接口映射、标识/类型/精确金额条件、排序/页大小收紧、响应/字段投影、业务服务最终角色授权、错误映射和联调门禁 |
| 上位文档 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.2 Approved |
| 直接输入 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v0.4 Approved；[`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4 Approved |
| 外部契约 | `mq-procedure-service` `POST /txn/search`；`transaction-api` search DTO；`auth-service/common-security` 用户 JWT/Authority |
| 实现基线 | 目标 Python Adapter 不存在；现有 search 已要求 user token、至少一项条件、page 1+、size 1～100、排序最多两项，但 guard 未校验角色，统一 Authority converter 未具备 |
| 是否可作为实现依据 | 否 |
| 实施依据说明 | 设计已通过独立复评，但开始 Python 切片仍需关闭 `BQ-GATE-002`；Transaction Java/公开行为修改和真实动作启用还分别受 `BQ-GATE-003/SA-GATE-005` 控制 |
| 当前允许范围 | 文档评审、synthetic Transaction fixture、fake HTTP/Authority 契约推演 |
| 当前禁止动作 | 修改 Agent/Java/安全代码、配置、测试或公开契约；调用真实交易数据；启用真实动作、聚合或模型出域；关闭门禁 |
| 修改权限 | 本轮用户已授权独立复评、相关文档原子同步及 Git commit/push；代码、配置、Schema、接口和真实数据只读 |

> 第一阶段只设计 `transaction.search`，固定 page=1，支持交易标识、交易类型精确/包含及金额等值/开区间条件。模型参数中的金额使用规范十进制字符串，validator 转为 Python `Decimal`，公共 business wire 以精确 JSON number 发送至现有 Java `BigDecimal` 字段，全链路禁止 float。Java `Date` 的 JSON 格式仍未形成已验证契约，因此日期条件、日期排序和日期结果不进入 typed Agent 契约。detail/query/condition/aggregate 及写入口全部不可达。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-31 | 全文 | 第三批 L2 依序编写 | 新建 Transaction 单搜索动作、受控条件/排序、响应覆盖、字段分类、授权入口、失败、测试和门禁设计 |
| 2 | 2026-07-31 | 全文 | 第 1 轮内部自检 | 完成结构、追踪、责任、签名、失败、安全、事务、生命周期和门禁检查；严格校验无结构缺口 |
| 3 | 2026-07-31 | 8/9/13/15 章 | 第 2 轮内部自检 | 禁止 LIKE wildcard 扩大、修正 Decimal wire 示例、收紧 exact coverage 和固定 ROUND_HALF_UP |
| 4 | 2026-07-31 | 8/9/12～16 章 | 第 3 轮内部自检 | 补齐内部 wire/record 类型字段，展开精确配置键和 Java 测试路径，完成实施可验证性收口 |
| 5 | 2026-07-31 | 6 章 | 第三批原子一致性同步 | 展开已存在 Transaction Java 类完整路径；不改变三轮内审结论或动作边界 |
| 6 | 2026-07-31 | 全文 | 五轮独立评审—修复—复核 | 关闭切片门禁、金额请求契约、短ID脱敏、完整descriptor、snake/camel、严格响应、业务可见性、Java触点、请求—响应关联、发布回滚和验证等`REV-TXN-001`～`020`，定版v0.2 Approved；所有实施/集成门禁保持Open |
| 7 | 2026-07-31 | 13 章 | 终态验证证据同步 | 执行含 Transaction API、服务及直接依赖的 Maven 现有基线回归并通过；建议修改/新增的角色守卫、WebFlux 与响应可见性测试尚未实施，所有实施/集成门禁保持 Open |
| 8 | 2026-08-01 | 1～15、17～18章 | 用户确认补齐 BigDecimal/Decimal 查询链路 | 对齐 `L2_02_00` v0.4，新增 amount/amount_gt/amount_lt 规范字符串参数、强类型 Decimal 条件、精确 JSON number wire、边界/互斥/配置/测试和 provider 门禁；更新为 v0.3 In Review |
| 9 | 2026-08-01 | 8.1、8.3、13、16～18章 | v0.3 第 1 轮独立复评修复 | 将不可由合法 Transaction DTO 构造的 4096/4097-byte 域测试改为“最大合法请求小于动作上限”，并由公共 encoder 测试独占总字节边界；同步公共 v0.4 Approved 依赖，等待重新复评 |
| 10 | 2026-08-01 | 1、16～18章 | v0.3 第 2 轮独立复评收口 | 从当前全文和直接依赖重新复核，确认公共字节边界仍由共享 encoder 验证、域测试只验证合法 Transaction 请求；关闭 `REV-TXN-021`，未发现新的 S0/S1/S2，恢复为 Approved；实施及集成门禁保持 Open |

## 3. 背景、目标与范围

### 3.1 背景与根因

`TransactionController` 同时公开消息提交、更新、详情、宽条件、分页搜索、聚合、创建和删除。现有 `/txn/search` 是最接近 Agent 只读查询的接口，但其请求复用宽 `Transaction` 条件，公开 Date/金额等多种字段；当前 guard 只验证 user token。若 Adapter 允许模型直接构造该 DTO，可能扩大条件、调用聚合/写入口、混淆日期格式或在业务服务未最终验角色情况下查询。

### 3.2 目标与可观察行为

| 需求编号 | 目标 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-TXN-001` | 只提供一个代码绑定搜索动作 | registry 仅有 `transaction.search@1`；其他 `/txn` 路径调用数为零 | L1_02 6/7；L2_02_00 |
| `REQ-TXN-002` | 条件与排序强类型收紧 | 至少一个文本或金额条件；page 固定 1；size≤配置≤50；排序≤2 且仅三字段 | L1_02 7.2 |
| `REQ-TXN-003` | 首期排除不稳定 Date wire | Agent 请求/typed record/用户/模型结果均无日期字段；原始响应日期显式跳过 | 当前代码使用 `java.util.Date`，wire 未验证 |
| `REQ-TXN-004` | 业务服务最终验证角色 | 统一安全边界拒绝非法 role；Transaction search 入口仍验证 ADMIN/VIEWER 后才调用 service/mapper | 用户确认；L1_02 7.4 |
| `REQ-TXN-005` | 空结果、覆盖与近似总数真实 | 仅 page1 rows空+total0+exact 可为 no-result；非 exact total 不冒充精确 total | 现有 `TransactionSearchResponse` |
| `REQ-TXN-006` | 结果字段最小化 | 用户最多交易 ID 掩码、类型、金额；短于掩码下限的 ID 安全省略；模型候选默认空；日期和所有查询辅助字段零 typed 投影 | L2_02_00 9/11 |
| `REQ-TXN-007` | 状态与失败稳定 | 400 invalid_argument；401/403/429/5xx/timeout 不混淆；非法 2xx 不变 no-result | L2_02_00 12.1 |
| `REQ-TXN-008` | 一次只读 HTTP、禁止聚合与写入 | 每次最多一次 POST `/txn/search`，无 retry/redirect/第二动作；禁止路径 spy 全零 | L1_02 9.3/10.3 |
| `REQ-TXN-009` | 金额条件全链路保持十进制精度 | 模型参数以规范字符串进入；validator 生成 finite `Decimal`；wire 为未加引号 JSON number；Java 精确接收 `BigDecimal`，任何路径不得调用 float 或依赖 string coercion | 用户确认；现有 Transaction API/Mapper |

### 3.3 范围内

- `transaction.search` descriptor、强类型条件/排序/input、wire request/response、normalizer/provider。
- page1 有界搜索、最多 50 条、现有 total/totalExact 的 coverage 映射。
- `transId/transType/transTypeContains/amount/amountGt/amountLt` 条件和 `transId/transType/amount` 三字段排序。
- Transaction search 入口的最终 Authority 判定建议、字段投影、失败和联调矩阵。

### 3.4 范围外

- 日期条件/排序/typed 输出；detail、condition、query、aggregate、create/update/delete、MQ/Kafka 提交。
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
| `CON-TXN-007` | L2_02_00 v0.4 `DR-BQCOM-019` | Core JSON 不接收 Decimal；业务 wire 以专用 ExactDecimal 编码为 JSON number | `DR-TXN-012` | 无 |

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
| `REQ-TXN-009`,`CON-TXN-007` | `DR-TXN-005`、`DR-TXN-012` | validator/mapper/codec/common wire encoder | `IMPL-TXN-002/003` | `TEST-TXN-003/004/016` | `VAL-TXN-001/003` |

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
| 已存在 | `Transaction.java` `amount/amountGt/amountLt`、`TransactionMapper.xml` 搜索条件 | 三个金额条件均使用 `BigDecimal`，Mapper 已支持 `=/>/<`；现有 service test 和 mapper integration test 使用 `new BigDecimal(...)` | 可复用现有公开 DTO/查询，无需新增 Java 字段或 endpoint；真实 precision/scale 仍待 provider contract 关闭门禁 |
| 已存在但不足 | Transaction `CapabilityAccessGuard.requireUser` | 只校验 user token | 需动作角色 guard 证据 |
| 缺失 | `common-security` role converter、Python Adapter | Authority/目标代码均未闭环 | 真实动作保持 disabled |

### 6.2 最小改造判断

复用 `/txn/search`，不新增接口或 DTO。Python 只构造现有 DTO 的安全子集。金额参数在 Core `JsonObject` 中保持规范字符串，由同一注册项 validator 转为 `Decimal`；mapper 执行范围、scale 和互斥校验，codec 复用 `L2_02_00` v0.4 `BusinessWireJsonEncoder` 把 `ExactDecimal` 写为未加引号 JSON number，禁止 binary float、quoted string coercion 和域内 raw JSON 拼接。Provider 侧继续建议新增动作专用 `requireTransactionRead` 并只替换 search 入口调用，现有 aggregate 继续使用 `requireUser`，避免本设计顺带改变聚合授权。日期 wire 没有显式 Jackson 配置或契约测试，因此首期仍排除。搜索已有明确空结果和 400 语义，可直接映射，不需要 Provider 状态改造；真实金额 precision/scale 与数据库比较行为必须在 `BQ-GATE-003` 关闭前验证。

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

Transaction 条件、wire 和 coverage 随业务 search 契约变化，内聚在 Transaction Adapter；精确十进制 JSON 编码、JWT client、状态和投影留在 business common；角色与数据查询留在业务服务。模块只通过 action definition、现有 JSON wire 和 Authority 可观察契约耦合，不共享私有 DTO。新增金额字段只实例化公共 `ExactDecimal`，不修改 core 或 Employee；后续验证 Date 时仍可只扩展 Transaction definition/codec/test。

## 8. 动作、输入、wire 与字段契约

### 8.1 动作定义

| 定义字段 | 冻结值 |
|---|---|
| `descriptor.capability_id` | `transaction.search` |
| `api_version/kind` | `1/query` |
| `display_name` | `Transaction search` |
| `description` | `按交易标识、交易类型或精确金额条件查询第一页受控交易记录；不提供日期条件、聚合或写入。` |
| `aliases` | `("交易查询","transaction lookup")`；只帮助模型理解，不可作为执行 ID |
| `argument_schema` | 8.2 的固定 object schema；无 Schema 默认表达式，`additionalProperties=false` |
| `domain_id/service_key` | `transaction/mq-procedure-service` |
| `answer_mode` | `model_assisted`，但结构化本地结果可独立返回 |
| `applicable_dimensions` | `max_page_size,max_result_count,filter_fields,sort_fields,timeout_ms` |
| filter code set | `trans_id,trans_type,trans_type_contains,amount,amount_gt,amount_lt` |
| sort code set | `trans_id,trans_type,amount` |
| contract limits | `max_page_size=max_result_count=50`；`max_timeout_ms=5000`；`max_request_bytes=4096`（共享 encoder 的安全上限；当前所有合法条件组合的 canonical body 必须严格小于该值）；无 time range；Transaction codec 另拒绝超过262144 raw bytes的已聚合2xx body |
| status semantics | `http_400_is_invalid_argument=true`；`http_204_is_no_result=false`；`http_404_is_no_result=false` |
| required user fields | `transaction_type,amount`；交易 ID 因短值不可安全保留末四位而为可选 |

### 8.2 强类型输入

`CapabilityDescriptor.argument_schema` 固定为下列受控 JSON Schema 子集。受控子集不能表达“至少一个条件”、类型条件互斥、contains wildcard 禁止、配置子集和 snake→camel 映射，这些仍由同一注册项 validator/mapper 确定性执行：

```json
{
  "type": "object",
  "properties": {
    "trans_id": {"type":"string","minLength":1,"maxLength":128},
    "trans_type": {"type":"string","minLength":1,"maxLength":128},
    "trans_type_contains": {"type":"string","minLength":1,"maxLength":128},
    "amount": {"type":"string","minLength":1,"maxLength":32},
    "amount_gt": {"type":"string","minLength":1,"maxLength":32},
    "amount_lt": {"type":"string","minLength":1,"maxLength":32},
    "size": {"type":"integer","minimum":1,"maximum":50},
    "sorts": {
      "type":"array","maxItems":2,
      "items": {
        "type":"object",
        "properties": {
          "field":{"type":"string","enum":["trans_id","trans_type","amount"]},
          "direction":{"type":"string","enum":["ASC","DESC"]}
        },
        "required":["field","direction"],
        "additionalProperties":false
      }
    }
  },
  "additionalProperties": false
}
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionSearchInput:
    trans_id: str | None = None
    trans_type: str | None = None
    trans_type_contains: str | None = None
    amount: Decimal | None = None
    amount_gt: Decimal | None = None
    amount_lt: Decimal | None = None
    size: int | None = None
    sorts: tuple[TransactionSort, ...] = ()
```

| 类型 | 精确字段 | 不变量 |
|---|---|---|
| `TransactionSort` | `field: Literal["trans_id","trans_type","amount"]`；`direction: Literal["ASC","DESC"]` | tuple 最多2，field唯一 |
| `TransactionSearchCondition` | `trans_id/trans_type/trans_type_contains: str | None`；`amount/amount_gt/amount_lt: Decimal | None` | 至少一项；类型条件互斥；amount 与范围条件互斥；上下界有序；全部已验证并冻结 |
| `TransactionSearchWireRequest` | `condition: TransactionSearchCondition`；`sorts: tuple[TransactionSort,...]`；`page: Literal[1]`；`size: int` | 只由 mapper 构造，size≤有效上限 |
| `TransactionRecord` | `trans_id: str`；`trans_type: str`；`amount: Decimal` | 三字段非空、有界，不含 Date |
| `TransactionSearchWireResponse` | `rows: tuple[TransactionRecord,...]`；`total: int`；`total_exact: bool`；`page: int`；`size: int` | 8.4 coverage 不变量 |

- arguments 只接受 Schema 中 snake_case key；`size/sorts` 省略时 validator 保留 `None`/空 tuple，不从配置或模型补默认条件；未知/重复 key 拒绝，至少一个文本或金额条件非空。
- 标识 NFC/trim 1～128，类型/contains 1～128；禁止控制/Bidi 字符；`trans_type` 与 `trans_type_contains` 互斥。由于现有 SQL `LIKE concat('%', value, '%')` 未转义，`trans_type_contains` 还必须拒绝 `%`、`_` 和反斜线，避免调用方注入通配语义。
- `amount/amount_gt/amount_lt` 只接受 exact string，不接受 JSON number、float、int、bool 或 null。字符串必须匹配 `^-?(0|[1-9][0-9]*)(\.[0-9]{1,4})?$`，禁止前导 `+`、指数、前导零、whitespace、NaN/Infinity；解析后必须 finite、绝对值≤`9999999999999999.9999` 且 scale≤4。`amount` 与 `amount_gt/amount_lt` 互斥；两个范围同时存在时必须 `amount_gt < amount_lt`。任一失败均在 HTTP 前返回 invalid_argument，错误和日志不含原字符串。
- 任意 Date key 仍为 unknown argument 并在 HTTP 前拒绝。配置禁用的任一允许 filter 在 HTTP 前 invalid_argument；配置不能放宽金额 grammar、绝对值或 scale 上限。
- page 不暴露，wire 固定1。mapper 计算 `effective_max=min(settings.max_page_size,settings.max_result_count)`；显式 size 必须为1～effective_max，省略时取 `min(20,effective_max)`，因此配置降低上限不会让所有省略 size 的调用失效。
- sorts 0～2 项，field 只取有效 sort 子集，direction 只允许 `ASC/DESC`；field 不重复。

### 8.3 HTTP wire request

唯一请求为 `POST /txn/search`：

```json
{
  "condition": {
    "amountGt": 100.01,
    "transType": "PAY"
  },
  "page": 1,
  "size": 20,
  "sorts": [{"direction":"DESC","field":"amount"}]
}
```

snake_case 条件/排序必须由 codec 显式映射为 Java wire 名：`trans_id→transId`、`trans_type→transType`、`trans_type_contains→transTypeContains`、`amount→amount`、`amount_gt→amountGt`、`amount_lt→amountLt`，排序字段 `trans_id→transId`、`trans_type→transType`、`amount→amount`。空条件字段必须省略，不发送 null、Date 条件、响应专用字段或任意 unknown key。

金额在 capability arguments 中是字符串，但进入 `TransactionSearchInput/Condition` 后必须是 `Decimal`；codec 只能调用 `ExactDecimal.from_decimal` 和 `BusinessWireJsonEncoder.encode(..., max_bytes=4096)`，因此上例 `amountGt` 是未加引号的 JSON number。`"100.0100"` 可在通过 scale 校验后规范编码为 `100.01`，`-0/0.0` 统一为 `0`；禁止 `float()`、`json.dumps(default=str)`、quoted decimal、手写字符串拼接或绕过 `CanonicalBusinessJsonBody`。body 按公共 v0.4 的唯一 Unicode/key/number 规则、无多余空白编码，unique keys、UTF-8且≤4096 bytes；无 query 和自定义 header。上例因而使用顶层 `condition,page,size,sorts`、condition `amountGt,transType` 和 sort item `direction,field` 顺序。Transaction 域测试必须以所有合法条件组合中 canonical bytes 最大的一组证明长度严格小于4096；4096/4097 总字节边界由 `TEST-BQCOM-003/014` 直接构造共享 business-wire body 验证，域测试不得绕过 `TransactionSearchWireRequest` 不变量伪造超长请求。

### 8.4 2xx wire response 与 coverage

顶层必须是 object，且除 `rows,total,totalExact,page,size` 外的字段一律拒绝；要求 rows 为 array、page/size/total 为 exact int（bool 不得视为 int）、totalExact 为 exact bool、page与同一次 `TransactionSearchWireRequest.page` 精确相等、size与同一次request.size精确相等、`0≤total≤9223372036854775807`、rows数量≤request.size。每行必须是 object，只复制 `transId/transType/amount`；仅当前 `Transaction` 已核实的 `transDate,transDateGt,transDateLt,amountGt,amountLt,transTypeContains` 可作为宽 row 兼容例外存在于受限临时 JSON object，其他未知 row 字段拒绝。三目标字段必须存在、非 null 且类型正确；ID/type NFC 后1～128且无控制/Bidi。strict decoder 使用 `parse_float=Decimal`、`parse_int=int`、拒绝 NaN/Infinity/duplicate/BOM/trailing；amount只接受exact int（非bool）或Decimal并转为finite Decimal，绝对值≤`9999999999999999.9999`、小数位≤4，不得经过float。body>262144 bytes或rows>request.size整体invalid_response；codec不得以可变实例字段保存“上次请求”，common客户端仍先受全局response cap约束。

normalizer 规则：

- rows 空、total=0、totalExact=true → `no_result(returned=0,truncated=false,total_count=0)`。
- rows 非空、totalExact=true → records；要求 `rows数=min(total,size)`，`total_count=total`，`truncated=(rows数<total)`；page1 出现不足页但 total 声称更多时视为 count/query 矛盾。
- rows 非空、totalExact=false → records；`total_count=None,truncated=true`，保留“不完整”而不把 total 下界当精确值。
- rows 空但 total>0 或 totalExact=false、page/size 不回显、任一行不合法 → invalid_response。

### 8.5 字段目录与转换

| field_id | source | value_type | class | user | model candidate | allowed user transforms | allowed model transforms |
|---|---|---|---|---:|---:|---|---|
| `transaction_id_masked` | `transId`；仅长度5～128时 extractor 返回值，1～4时返回 `None` | `identifier` | `transaction_identifier` | 是/可选 | 否 | `{mask_keep_last4}` | `{}` |
| `transaction_type` | `transType` | `text` | `business_internal` | 是/必需 | 是 | `{bounded_text}` | `{bounded_text}` |
| `amount` | `amount` | `decimal` | `financial_value` | 是/必需 | 是 | `{decimal_2}` | `{decimal_2}` |

表中顺序就是冻结 field definition、用户结果和 facts 顺序。`transaction_id_masked` 对1～4位 ID 安全省略，不定义公共转换之外的短值特例；5～128位时严格复用 `mask_keep_last4`。模型字段代码候选是 `transaction_type,amount`，动作配置默认空，且仍受全局规则交集。`decimal_2` 使用 Decimal 并精确采用 `ROUND_HALF_UP`，不得经过 float；交易 ID 永不成为模型候选。用户结果 coverage 可携带 provider 返回的 exact `total_count`，但这不是第二次聚合调用；模型 facts 不含 coverage，答案不得生成合计、平均、趋势或把非 exact 下界表述为总数。

## 9. 详细功能与处理流程

### 9.1 设计规则

| 规则编号 | 规则 | 责任主体 | 效果 |
|---|---|---|---|
| `DR-TXN-001` | 只定义并注册 `transaction.search@1` | provider/组合根 | 动作有限 |
| `DR-TXN-002` | 配置只能禁用、缩小 filter/sort/size/result/timeout/字段，不能放宽金额 grammar/range/scale 或增加 Date/路径/动作 | settings/provider | 配置不扩权 |
| `DR-TXN-003` | Adapter 只透传当前 user JWT，不解析 role、不使用 service token | handler/client | 身份不替换 |
| `DR-TXN-004` | 统一边界先验证 role；Transaction search 再要求 ADMIN/VIEWER Authority 后调用 service | common-security/业务入口 | 最终动作授权 |
| `DR-TXN-005` | validator/mapper 执行文本与金额条件互斥、金额范围、filter/sort/page/size 收紧并只构造无 Date 的现有 DTO 子集；codec 显式完成 snake→camel 映射 | validator/mapper/codec | 请求有界且不降精度 |
| `DR-TXN-006` | normalizer 严格解释 rows/total/exact/page/size，非 exact total 不进入 total_count | normalizer | coverage 真实 |
| `DR-TXN-007` | 用户仅三字段，模型默认空；模型结果不得生成聚合/全量结论 | fields/egress | 字段和语义收紧 |
| `DR-TXN-008` | 400/401/403/429/5xx 由 common 固定映射，域不读错误 body | status mapper | 状态稳定 |
| `DR-TXN-009` | 一次动作最多一个 POST，共享绝对截止，无 retry/redirect/cache/自动翻页 | handler/client | 资源有界 |
| `DR-TXN-010` | 所有非 search 路径和 MQ/Kafka/aggregate 代码在 Adapter 架构测试中不可达 | codec/architecture | 无副作用/聚合 |
| `DR-TXN-011` | Date 输入/输出保持代码禁用，只有 wire 契约和时区测试确认后才可另行设计扩展 | definition/codec | 不猜日期 |
| `DR-TXN-012` | amount 三参数在 Core 边界只接受规范 decimal string，validator 转为 exact `Decimal`；codec 只经公共 `ExactDecimal`/encoder 输出 JSON number，Java 以现有 `BigDecimal` 接收；禁止 float、quoted coercion 和 raw JSON 拼接 | validator/codec/common wire encoder | Python/JSON/Java 金额精度一致 |

### 9.2 正常序列

1. core 以同一 descriptor validator 产生 typed input 并 claim 单动作。
2. handler 校验 context/token/deadline；validator/mapper 依据冻结 settings 校验文本/金额条件和排序，金额保持 `Decimal`。
3. codec 通过公共 exact-decimal encoder 构造唯一 POST body，common client 向绑定 service origin 发送一次原用户 JWT。
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
| `AGENT_TRANSACTION_SEARCH_FILTER_FIELDS` | 六个代码条件 | 只能取 `trans_id,trans_type,trans_type_contains,amount,amount_gt,amount_lt` 子集且非空；不能放宽金额 grammar/range/scale |
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
| 非法 2xx/204/body超限 | downstream_failure(`invalid_response`) | `business.invalid_response` | 1/0 |
| 404（未声明 no-result） | downstream_failure(`unavailable`) | `business.downstream_failure` | 1/0 |
| timeout/429/5xx/connect | typed common failure | common 固定 code | ≤1/0 |

### 10.2 权限与审计

建议新增 `CapabilityAccessGuard.requireTransactionRead(Authentication)`：先调用现有 `requireUser(authentication)`，再从 `authentication.getAuthorities()` 的不可变快照中要求至少一个 authority 精确等于 `ROLE_ADMIN` 或 `ROLE_VIEWER`，否则抛无敏感正文的403。原始 role 的缺失/未知/大小写错/混合未知由统一 reactive converter 在 Controller 前整体403；guard 不解析 claim、不改大小写、不按用户名判断。只把 `TransactionController.search` 的 guard 调用从 `requireUser` 改为 `requireTransactionRead`，并确保其位于 `TransactionService.search` 前；aggregate 和其他入口不在本切片修改。拒绝时 service/mapper 为零。

Adapter 投影不能证明业务数据可见性。`BQ-GATE-003` 关闭前，Transaction 方须以 versioned、无真实值的 provider fixture 冻结 `/txn/search`、允许角色 `ADMIN/VIEWER`、`TransactionSearchResponse` 顶层字段、`Transaction` 可序列化属性全集及 policy version，并由维护者确认两个角色均可接收包含 `transDate` 的现有 wire 响应；provider contract test 应使用所有属性均为合成非空值的 `Transaction`，避免 Jackson null inclusion 让测试漏掉潜在字段，再把序列化字段集合与 fixture 精确比较。若不能确认，须另行设计窄 row DTO，本文修订前不得真实接线。

日志只允许 correlation ID、动作 ID、有限 filter/sort ID（不含值）、page size、returned count、truncated/exact 状态、耗时和 snapshot ID。禁止 JWT、subject、条件值、交易 ID（含掩码）、金额、类型文本、请求/响应 body、URL query、异常 message/stack。真实数据和具体交易问题进入 DeepSeek 前仍受 `CR-GATE-003/SA-GATE-006`。

### 10.3 事务边界与一致性

Agent 无事务、持久化、缓存或重试。业务 search 当前先 count 后 query，代码未证明两次读取位于同一数据库快照；Adapter 不伪造强一致性。它只验证响应内部不变量，`totalExact=false` 时不输出精确 total；并发变更造成 rows空但 total>0 等矛盾时失败为 invalid_response。若未来要求快照一致或 cursor，必须由业务服务另行设计，不能在 Adapter 重查补偿。

## 11. 数据生命周期、发布与回滚

### 11.1 数据生命周期

输入条件、canonical request、原始 2xx body和 typed rows 只在单次请求内存中存活。原始 body 先由 common 客户端按 `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` 聚合，Transaction codec 只接受≤262144 bytes，并可能短暂构造包含 Date/辅助字段的 JSON object；复制三字段 typed rows 后必须解除原始 bytes/object 引用。原始交易 ID、金额和类型不持久化/缓存/日志。用户结果只保留可安全掩码的 ID、类型和金额；模型 safe payload 即使获准也无 ID，且只存在于一次模型调用。

### 11.2 发布与回滚

1. synthetic fake 先完成规范金额字符串→Decimal→精确 JSON number 请求、Decimal 响应、coverage、禁止路径和模型零调用测试。
2. 在修改 search guard 前盘点现有 `/txn/search` 调用方及其角色；不能证明合法调用方满足新角色契约时，`BQ-GATE-003` 不得关闭。
3. 单独实施统一 reactive converter、Transaction search guard 和 response visibility fixture，并回归现有 search/aggregate；Agent 不调用 aggregate且 aggregate授权不随本切片变化。
4. provider/consumer、角色、BigDecimal 请求反序列化和数据库比较矩阵通过后才允许真实 search 及金额条件；Date 仍禁用。
5. Agent 侧回滚将 `AGENT_TRANSACTION_SEARCH_ENABLED=false` 并重启 Runtime。Provider guard 事故先停用 Agent并阻断非预期 search 流量，再由 Transaction 方决定 provider 版本回滚；不得把恢复“任意 authenticated 用户可查询交易”作为自动降级，也不得切换到 detail/query/condition/aggregate。

本文不含数据迁移。Date、窄响应、cursor 或权限响应变化均需独立公开契约设计和兼容回滚。

## 12. 实现落点与关键签名

### 12.1 实现落点

| 编号 | 状态 | 路径/符号 | 责任 | 规则 |
|---|---|---|---|---|
| `IMPL-TXN-001` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/definition.py` | descriptor/limits/filter/sort/fields | `DR-TXN-001/002` |
| `IMPL-TXN-002` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/contracts.py` | 含 Decimal 金额条件的 input/sort/wire/record | `DR-TXN-001/005/006/012` |
| `IMPL-TXN-003` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/codec.py` | decimal string validator、mapper、公共 exact-decimal POST encode、2xx decode | `DR-TXN-002/005/008/011/012` |
| `IMPL-TXN-004` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/normalizer.py` | rows/total/exact→service result | `DR-TXN-006/008` |
| `IMPL-TXN-005` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/fields.py` | 三字段/转换/无 Date | `DR-TXN-007/011` |
| `IMPL-TXN-006` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/settings.py` | 精确 env fragment/default | `DR-TXN-002/007` |
| `IMPL-TXN-007` | 建议新增 | `agent-runtime/src/agent_runtime/adapters/transaction/provider.py` | TransactionDomainProvider | `DR-TXN-001/009/010` |
| `IMPL-TXN-008` | 建议修改 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java` | Transaction 读 Authority 判断 | `DR-TXN-004` |
| `IMPL-TXN-009` | 建议修改 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/controller/TransactionController.java` `search` | search 前调用动作 guard | `DR-TXN-004` |
| `IMPL-TXN-010` | 建议新增 | `mq-procedure-service/src/test/resources/contracts/agent/transaction-search-response-visibility-v1.json` | 经维护者确认的 endpoint/角色/顶层与 row 完整字段/policy version；无业务值 | `DR-TXN-004/006/011` |

### 12.2 Python 关键方法

| 符号 | 签名 | 输入/输出 | 副作用 |
|---|---|---|---|
| `TransactionSearchArgumentValidator.validate` | `def validate(self, arguments: JsonObject) -> TransactionSearchInput` | 三类文本条件、三个规范 decimal string、sort、size；金额转 exact Decimal；Date key拒绝 | 纯函数；非法值只抛 `InvalidCapabilityArguments` 且不含原值 |
| `TransactionSearchRequestMapper.map` | `def map(self, input: TransactionSearchInput, settings: BusinessActionSettings) -> TransactionSearchWireRequest` | filter/sort/settings 交集；金额互斥/范围/scale；page1 | 纯函数 |
| `TransactionSearchWireCodec.encode` | `def encode(self, request: TransactionSearchWireRequest) -> BusinessHttpRequest` | snake→camel；`ExactDecimal.from_decimal`；公共 encoder 产生≤4096 bytes canonical POST body | 纯函数；不得调用 float/quoted coercion/raw 拼接 |
| `TransactionSearchWireCodec.decode_success` | `def decode_success(self, *, request: TransactionSearchWireRequest, response: BoundedBusinessHttpResponse) -> TransactionSearchWireResponse` | request为当前调用栈同一冻结对象；仅2xx application/json；严格UTF-8、BOM/trailing/duplicate/非有限数拒绝；body≤262144；page/size与request精确相等、rows≤request.size；amount直接Decimal；row仅允许已核实宽字段 | 有界内存纯函数；不保存请求期状态/原object |
| `TransactionSearchResponseNormalizer.normalize_success` | `def normalize_success(self, response: TransactionSearchWireResponse) -> BusinessServiceResult[TransactionRecord]` | 8.4 exact/no-result/records | 纯函数 |
| `transaction_search_definition` | `def transaction_search_definition() -> BusinessActionDefinition[TransactionSearchInput,TransactionSearchWireRequest,TransactionSearchWireResponse,TransactionRecord]` | 返回冻结 descriptor/filter/sort/limit/field/status | 纯函数 |
| `TransactionDomainProvider.domain_id` | `def domain_id(self) -> BusinessDomainId` | 精确返回 `transaction` | 纯函数 |
| `TransactionDomainProvider.definitions` | `def definitions(self) -> tuple[BusinessActionDefinition[Any,Any,Any,Any], ...]` | 恰含 `transaction.search` | 纯函数 |
| `TransactionDomainProvider.configuration_fragment` | `def configuration_fragment(self) -> BusinessConfigurationFragment` | 只投影 `AGENT_TRANSACTION_SEARCH_*` 与 `mq-procedure-service` binding，不读 `os.environ`/其他域 | 纯函数 |

### 12.3 Java 关键方法

| 类/方法 | 建议签名 | 前置/返回 | 副作用 |
|---|---|---|---|
| `CapabilityAccessGuard.requireTransactionRead` | `void requireTransactionRead(Authentication authentication)` | 先 user JWT；再精确 `ROLE_ADMIN/ROLE_VIEWER` Authority，否则403 | 无 service/mapper 调用 |
| `TransactionController.search` | 已存在并建议修改内部 guard：`TransactionSearchResponse search(Authentication authentication, @RequestBody TransactionSearchRequest request)` | `requireTransactionRead` allow 后保持现有 wire | 一次 service |
| `TransactionService.search` | 已存在 `TransactionSearchResponse search(TransactionSearchRequest)` | 本文不修改签名/算法 | count≤1/query≤1 |

## 13. 测试与验证设计

### 13.1 测试矩阵

| 测试编号 | 规则 | 层级 | 建议路径/场景 | 关键断言 |
|---|---|---|---|---|
| `TEST-TXN-001` | `DR-TXN-001/002/012` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_definition.py` | descriptor/argument schema 全字段；唯一 action；三个金额参数为 string 且六个 filter 有限；Date/aggregate 不在定义/配置 |
| `TEST-TXN-002` | `DR-TXN-001/010` | Architecture | 建议新增：`agent-runtime/tests/architecture/test_transaction_adapter_boundaries.py` | 无 Employee/Java/DB/MQ/ES/retry；禁止 path 字面量零 |
| `TEST-TXN-003` | `DR-TXN-002/005/012` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_arguments.py` | 至少一项、类型互斥、LIKE wildcard；金额 exact/range 互斥、上下界、正负零、尾零、precision/scale±1；拒绝 JSON number/int/bool/null、指数及不符合 grammar 的字符串；Date拒绝；page1/size边界 |
| `TEST-TXN-004` | `DR-TXN-002/005/012` | Contract | 建议新增：`agent-runtime/tests/contract/adapters/transaction/test_search_request.py` | snake→camel、null省略、filter/sort子集；金额未加引号、plain、canonical key/Unicode顺序和精确 POST body；枚举互斥约束下逐组构造各文本字段最大 UTF-8 值、金额边界和两项排序，取 canonical bytes 最大合法请求并断言 `<4096`；不得绕过 typed request 构造超长 body；共享 4096/4097 边界由 `TEST-BQCOM-003/014` 证明；全路径无float |
| `TEST-TXN-005` | `DR-TXN-005/011` | Contract | 建议新增：`agent-runtime/tests/contract/adapters/transaction/test_date_exclusion.py` | Date args/config/request 拒绝；raw row Date只临时解析且 typed/user/model/log 零投影 |
| `TEST-TXN-006` | `DR-TXN-003/004` | Java Unit | 建议修改现有：`mq-procedure-service/src/test/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuardTest.java` | ADMIN/VIEWER allow；缺失角色/service token deny；aggregate 的 `requireUser` 语义不被本切片改变 |
| `TEST-TXN-007` | `DR-TXN-004/006/011` | Java MVC/Contract | 建议修改现有 `TransactionControllerTest.java` 并新增 `TransactionControllerAuthorizationTest.java`、`TransactionControllerResponseVisibilityContractTest.java` 与 12.1 visibility fixture | search 改调动作 guard；invalid/mixed role 在 reactive 安全边界403；deny service/mapper0；allow一次；实际顶层/row字段与维护者确认 fixture 精确一致 |
| `TEST-TXN-008` | `DR-TXN-006` | Parameterized | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_coverage.py` | rows/total/exact/page/size笛卡尔边界；exact矛盾失败；non-exact不产生total_count |
| `TEST-TXN-009` | `DR-TXN-007` | Unit | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_fields.py` | 1～4位ID省略、5位ID掩码；Decimal2；type/amount必需；无Date |
| `TEST-TXN-010` | `DR-TXN-007` | Model spy | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_egress.py` | 默认0；仅type/amount；coverage不进facts；禁止聚合/越界事实 |
| `TEST-TXN-011` | `DR-TXN-008` | Parameterized | 建议新增：`agent-runtime/tests/unit/adapters/transaction/test_status.py` | 400→invalid_argument、204→invalid_response、未声明404→downstream_failure；401/403/429/5xx且错误body读取0 |
| `TEST-TXN-012` | `DR-TXN-009` | Async HTTP | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_deadline_single_call.py` | HTTP≤1、无retry/自动翻页、取消/迟到丢弃 |
| `TEST-TXN-013` | `DR-TXN-010` | Security spies | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_forbidden_endpoints.py` | detail/query/condition/aggregate/write/MQ/Kafka调用全0 |
| `TEST-TXN-014` | `DR-TXN-003/007/009` | Log/security | 建议新增：`agent-runtime/tests/integration/adapters/transaction/test_sensitive_logging.py` | JWT、条件值、原始/掩码ID、类型、金额、请求/响应和异常sentinel零出现 |
| `TEST-TXN-015` | `DR-TXN-005/006/008` | Response contract/concurrency | 建议新增：`agent-runtime/tests/contract/adapters/transaction/test_search_response.py` | 顶层/row exact类型、已核实宽字段、未知字段、Decimal int/fraction/exponent/scale/界限、262144/262145 bytes；page/size错配；两个不同size并发交错响应 |
| `TEST-TXN-016` | `DR-TXN-004/005/012` | Java MVC/DB contract | 建议新增：`mq-procedure-service` Transaction search BigDecimal contract test | POST 数值 token `0/0.1/100.00/负值/边界` 进入 `amount/amountGt/amountLt`；捕获 service/mapper 参数及数据库 `=/>/<` 结果；quoted string、超 provider precision/scale 的允许/拒绝行为显式冻结 | Jackson 不经 double 精确构造 `BigDecimal`；参数和值与预期 `compareTo==0`；数据库不截断/舍入；不依赖 string coercion；不修改 DTO/endpoint |

### 13.2 验证命令

| 编号 | 命令 | 证明范围 | 当前状态 |
|---|---|---|---|
| `VAL-TXN-001` | `python -m pytest agent-runtime/tests/unit/adapters/transaction agent-runtime/tests/contract/adapters/transaction -q` | definition/input/wire/coverage/fields/status | 未执行：代码不存在 |
| `VAL-TXN-002` | `python -m pytest agent-runtime/tests/integration/adapters/transaction agent-runtime/tests/architecture/test_transaction_adapter_boundaries.py -q` | 单调用、禁止接口、模型/日志边界 | 未执行：代码不存在 |
| `VAL-TXN-003` | `mvn -f serviceCenter/pom.xml -pl :transaction-api,:mq-procedure-service -am test` | provider DTO/search/guard/WebFlux回归 | 2026-07-31 通过更大聚合命令覆盖现有 Transaction 基线并 `BUILD SUCCESS`；本文建议修改/新增的角色守卫、WebFlux 与响应可见性测试尚未实施 |
| `VAL-TXN-004` | opt-in：ADMIN/VIEWER/unknown/missing/malformed/service-token真实JWT矩阵，并以service/mapper spy计数 | reactive Authority/业务最终授权/mapper次数 | 未执行：converter/guard差距未关闭 |
| `VAL-TXN-005` | opt-in：以合成 sentinel 条件经实际 Gateway/Netty 发起一次 search，并检索 correlation ID 对应日志 | JWT、请求 body、交易ID/类型/金额和原始异常在 Gateway/Netty/应用日志零出现 | 未执行：真实入口和日志策略未获联调授权 |
| `VAL-TXN-006` | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md --root D:\codex --strict` | v0.3 文档结构、追踪、引用和质量规则；不替代独立复评或运行契约测试 | 2026-08-01 已执行：0 errors、0 warnings |

## 14. 风险、门禁与授权

### 14.1 风险

| 编号 | 风险 | 触发 | 影响 | 处置 |
|---|---|---|---|---|
| `RISK-TXN-001` | Date wire 未验证 | 日期查询/结果 | 时区/格式错误 | 首期代码排除，后续独立契约测试 |
| `RISK-TXN-002` | count/query 非同一已证明快照 | 并发写 | total/rows 矛盾 | 严格不变量；不重查；业务侧另行设计 |
| `RISK-TXN-003` | Decimal request/response/scale | provider 接收或返回大值、高 scale、quoted decimal 或非标准数字 | 精度漂移、截断/舍入或查询语义错误 | 请求使用规范字符串→Decimal→plain JSON number，响应 strict JSON直读Decimal；共同有限值/绝对值/scale边界；provider/DB contract 关闭后才真实启用金额条件 |
| `RISK-TXN-004` | Authority 未闭环 | 真实 search | 越权/误拒绝 | converter+guard+mapper spy 矩阵 |
| `RISK-TXN-005` | 聚合端点相邻且现存 | 动态 path/模型越界 | 超范围统计或大查询 | codec唯一 path、架构和HTTP spy零调用 |
| `RISK-TXN-006` | total 非 exact | 大结果集 | 用户误读总数 | total_count=None、truncated=true、禁止聚合话术 |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 控制动作 | 关闭条件 | 责任方 | 状态 | 未关闭允许/禁止 |
|---|---|---|---|---|---|---|
| `BQ-GATE-002` | slice_implementation | 实施本 L2 的 Python Transaction Adapter/配置/测试切片 | 本文独立评审可实施、直接依赖稳定且维护者明确授权；关闭后可实现完整 Python provider wiring，但其余门禁开放时只能连接 fake server | 维护者 | Open | 允许文档/synthetic 推演；禁止目标代码实施；关闭后仍禁止真实 endpoint |
| `BQ-GATE-003` | slice_implementation | 修改 Transaction guard、API 或公开行为及启用真实金额条件 | 维护者确认 search 子集、角色 guard、现有调用方兼容、versioned response visibility fixture、JSON number→BigDecimal→数据库 `=/>/<` 的 precision/scale/无舍入契约、Decimal response/400/coverage 语义及具体代码范围 | 维护者/Transaction 方 | Open | 允许设计/fake；禁止 Java/API/公开行为修改和真实金额查询 |
| `CR-GATE-003` | integration | 具体交易问题进入 DeepSeek | 全局问题闸门对交易 ID、金额和敏感文本形成批准路径或零调用 | 维护者/模型方 | Open | 允许 synthetic explicit action；禁止真实敏感问题外发 |
| `SA-GATE-005` | integration | 启用真实 Transaction | 本文独立复评；Authority、guard、response visibility、JSON number→BigDecimal→数据库精确比较、Decimal response/coverage、禁止接口、访问日志和角色矩阵通过 | 维护者/安全/Transaction 方 | Open | 允许 fake；禁止真实交易查询和金额条件 |
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
| 4 | 2026-08-01 | 0 | 2 | 1 | 3 | 0 | 将金额输入固定为规范字符串→Decimal→JSON number→BigDecimal，补齐互斥/边界/配置/跨语言测试与真实启用门禁；等待独立复评 |

## 16. 独立正式评审记录

每轮均先以只读方式冻结发现，再进入目标/已授权直接相关文档修复；修复后重新从当前全文开始下一轮。作者内审和确定性validator只作辅助证据，不替代独立评审判断。

### 16.1 第1轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-001` | S1 | 本文未承接上位按每份L2切片判断的`BQ-GATE-002`，可能把设计通过误当代码授权 | 增加Transaction Python切片门禁，并与provider变化、真实启用/出域门禁作交集 | Closed |
| `REV-TXN-002` | S1 | 金额条件要求Decimal精确JSON number，但approved common request body只允许JsonObject且禁止Decimal；经float会破坏精度 | 首期移除金额条件，保留金额结果/排序；避免扩大公共HTTP body契约 | Closed |
| `REV-TXN-003` | S1 | 公共`mask_keep_last4`要求至少5位，但现有provider测试使用合法形态`T001`；把ID列为required会使现有结果稳定失败 | ID改为可选字段，1～4位安全省略，5～128位复用公共掩码；type/amount作为最小有效结果 | Closed |
| `REV-TXN-004` | S1 | 未声明no-result的404被合并为invalid_response，与公共`unavailable`映射冲突 | 分离204与404，404固定downstream_failure(`unavailable`) | Closed |
| `REV-TXN-005` | S1 | 文档把raw body上限写成256KiB且声称直接跳过Date，但common先按全局上限聚合且无流式JSON依赖 | 区分transport/codec上限，承认宽row临时object生命周期并固定typed/log/error零投影 | Closed |
| `REV-TXN-006` | S1 | “收紧/替换requireUser”可能顺带改变相邻aggregate权限，超出search切片 | 新增动作专用guard，只替换search调用；aggregate继续现有requireUser并做回归断言 | Closed |
| `REV-TXN-007` | S1 | Adapter字段投影无法证明ADMIN/VIEWER有权接收含Date的现有宽row | 增加维护者确认的versioned response visibility fixture及实际序列化字段契约；不能确认则转窄DTO设计 | Closed |

### 16.2 第2轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-008` | S1 | 动作缺display/description/aliases/argument_schema，不能形成L2_00_01要求的完整descriptor | 固定完整descriptor和受控Schema，并明确跨字段规则由同一validator执行 | Closed |
| `REV-TXN-009` | S1 | snake_case输入未固定到Java camelCase filter/sort名，`trans_id/trans_type`可能直接形成provider 400 | 固定全部condition/sort映射、null省略和canonical key顺序 | Closed |
| `REV-TXN-010` | S1 | 响应未固定bool-as-int、非有限数字、Decimal直读、顶层/row unknown策略和Java long上限 | 固定strict parser、exact类型、Decimal无float、顶层严格/已核实宽row例外及数值边界 | Closed |
| `REV-TXN-011` | S2 | definition/provider方法不完整，现有guard/controller测试被误写为全部新增 | 补齐definition与provider三方法签名；把现有测试标为建议修改并分离新增权限/visibility测试 | Closed |

### 16.3 第3轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-012` | S1 | 请求示例仍发送应省略的null条件，且测试/风险仍要求已删除的金额请求编码 | 改为唯一规范请求示例，并重写参数、request、Date/金额排除、字段与风险测试 | Closed |
| `REV-TXN-013` | S1 | Maven命令在缺少聚合入口的仓库根目录不可执行，Python测试路径也不完整 | 以`serviceCenter/pom.xml`作为Maven聚合POM并使用artifact selector，同时统一`agent-runtime/tests`路径 | Closed |
| `REV-TXN-014` | S1 | search guard会改变现有公开行为，但没有旧调用方盘点或安全回滚流程 | 调用方角色兼容纳入provider gate；增加Agent先停用、provider显式决策的分层回滚 | Closed |

### 16.4 第4轮冻结发现与修复

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-015` | S1 | 省略size固定为20时，配置若收紧到10会使所有省略size的合法调用在运行期失败 | input保留`size=None`，mapper使用`min(20,effective_max)`；显式size仍严格受配置约束 | Closed |
| `REV-TXN-016` | S1 | 公共`decode_success(response)`拿不到同一次request，无法校验page/size/rows且用实例字段会在并发时串响应 | 原子聚焦修订`L2_02_00`为v0.3，显式传入同一冻结request；本文同步签名及交错并发测试 | Closed |
| `REV-TXN-017` | S2 | visibility测试若用默认null row，可能受Jackson null inclusion影响而漏检可序列化敏感字段 | fixture按属性全集冻结，provider测试使用所有属性均为合成非空值的Transaction | Closed |
| `REV-TXN-018` | S2 | 日志要求没有实际Gateway/Netty/body sentinel验证，无法证明请求条件未被日志设施采集 | 增加Agent日志测试与真实入口`VAL-TXN-005` | Closed |

### 16.5 第5轮冻结发现、修复与终审

| 发现ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-TXN-019` | S2 | 响应page/size只写“与请求一致”，但实现签名/测试未明确禁止codec保存可变上次请求 | 签名显式接收request并声明纯函数；两个不同size交错响应必须各自绑定 | Closed |
| `REV-TXN-020` | S2 | 测试矩阵没有一项完整覆盖strict response、Decimal、宽row、字节边界与并发回显 | 增加独立`TEST-TXN-015` response contract/concurrency测试 | Closed |

修复后重新从REQ/L0/L1、`L2_00_01`与`L2_02_00` v0.3、当前Transaction API/service/mapper/security事实、descriptor、输入/配置/wire/coverage、Decimal、宽row、JWT/Authority、禁止端点、并发/截止、生命周期、实现签名、测试、发布回滚和全部开放门禁复核；未发现新的S0/S1/S2，`REV-TXN-001`～`REV-TXN-020`全部关闭。评审结论为Approved；该结论不关闭`BQ-GATE-002/003`、`CR-GATE-003`、`SA-GATE-005/006`。

### 16.6 v0.3 精确金额条件修订范围

v0.3 在保持 `transaction.search@1`、现有 endpoint/DTO、单次调用、权限、结果字段和 Date/聚合/写入禁项不变的前提下，新增三个金额过滤参数及其跨语言精确数值链路。这属于动作参数和共享 business wire 的语义变化；历史五轮评审与 `REV-TXN-001`～`020` 的关闭证据只覆盖 v0.2。本次两轮独立复评已覆盖该变化；`BQ-GATE-003` 关闭前，真实金额条件仍失败关闭。

### 16.7 v0.3 第 1 轮独立复评冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-TXN-021` | S2 | `TEST-TXN-004` 要求 4096/4097-byte Transaction 请求，但合法字段长度、条件互斥和排序数量使 typed request 无法到达该边界；测试若强行构造只能绕过自身不变量，无法证明真实 codec 行为 | 域测试改为枚举各类最大合法组合并断言最大 canonical body `<4096`；4096/4097 边界由公共 `TEST-BQCOM-003/014` 独占验证 | Closed |

本轮只修正共享边界与域测试的责任分配，不改变动作参数、金额范围/scale、wire bytes、Java DTO/endpoint、权限或开放门禁。

### 16.8 v0.3 第 2 轮重新复评结论

重新从当前全文及 `L2_02_00` v0.4、`L2_00_01` v0.4、现有 Transaction DTO/service/mapper 事实检查动作参数、Decimal/BigDecimal 精度链路、canonical request、合法请求上界、响应解码、权限、门禁和测试追踪。`TEST-TXN-004` 现在只使用合法 typed request 证明域内请求严格小于 4096 bytes，`TEST-BQCOM-003/014` 继续直接证明共享 encoder 的 4096/4097 bytes 边界；两者责任互补且没有测试绕过。`REV-TXN-021` 已关闭，未发现新的 S0/S1/S2，结论为 Approved。该结论不关闭 `BQ-GATE-002/003`、`CR-GATE-003`、`SA-GATE-005/006`。

## 17. 实施前检查

- [x] 单 search 动作、现有接口、文本/金额条件、排序、字段和授权边界已定义。
- [x] Date、聚合、自动翻页和写入口均明确不可达。
- [x] 公开接口/安全不足保持开放门禁。
- [x] 三轮内部自检完成且无遗留 Blocker/Major。
- [x] 严格详细设计校验通过。
- [x] v0.2 五轮独立评审—修复—复核完成，全部历史 S0/S1/S2 已关闭。
- [x] v0.3 精确金额条件与 `L2_02_00` v0.4 已完成两轮独立复评—修复—复核，`REV-TXN-021` 已关闭。
- [ ] 用户另行授权实施并关闭本切片`BQ-GATE-002`；`BQ-GATE-003/SA-GATE-005`仍分别控制provider变化与真实启用。

## 18. 当前结论

本文 v0.3 已完成精确金额条件修订、作者内审及两轮独立复评—修复—复核，`REV-TXN-021` 已关闭且未发现新的 S0/S1/S2，文档状态恢复为 Approved。该结论确认设计内部一致，不代表实现授权或集成门禁关闭：`BQ-GATE-002/003`、`CR-GATE-003`、`SA-GATE-005/006` 均保持 Open；目标代码、Transaction Java/API/公开行为修改、真实金额/日期查询、真实 Transaction 接线和真实数据模型出域仍禁止。
