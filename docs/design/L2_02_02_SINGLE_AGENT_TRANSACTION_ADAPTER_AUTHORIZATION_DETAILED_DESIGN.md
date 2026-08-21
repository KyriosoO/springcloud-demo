# [L2_02_02] 单体 Agent Transaction Adapter 与授权详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_02_02` |
| 当前版本 | v1.0 |
| 日期 | 2026-08-21 |
| 权威范围 | `transaction.search` 参数、精确金额、wire、分页、字段投影、业务域授权与验证 |
| 上位文档 | [`L1_02` v1.0](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) |
| 公共下位依赖 | [`L2_02_00` v1.0](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) |
| 安全依赖 | [`L2_00_03` v1.0](L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) |
| 来源文档 | [L2_02_02 v0.23 归档版](历史文档/2026-08-21-v0-baseline/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) |
| 实施状态 | Adapter、精确金额链和领域最终授权已实现；真实业务结果外部模型出域默认关闭 |

## 2. 阅读导航与变更记录

重点阅读：第 7 节动作参数、第 8 节 ExactDecimal 链、第 9 节响应/分页、第 10 节授权、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立 Transaction 当前稳定基线 | 删除历史 live candidate 和门禁流水，固化当前 search、DECIMAL(50,2)、三字段投影、业务域授权及验证入口 |

## 3. 目标与范围

### 3.1 目标

把有限交易查询映射为对 `mq-procedure-service` 现有 `POST /txn/search` 的一次受控调用。金额从 Agent 参数到数据库比较保持十进制精确；Adapter 只收紧查询，业务服务完成最终身份/角色授权。

### 3.2 范围内

- `transaction.search` descriptor、有限本地 Resolver 和参数 validator；
- 交易标识、交易类型、类型包含、金额等值/开区间、第一页大小和有限排序；
- canonical JSON number → Java `BigDecimal` → SQL `=/>/<` 精确链；
- strict response、coverage、三字段用户视图和最多两个模型字段；
- ADMIN/VIEWER 业务域最终授权；
- Python/Java/Mapper 契约、安全和精度测试。

### 3.3 范围外与不负责

- Date 条件、详情、聚合、写入、MQ/Kafka 管理动作；
- 通用 DSL、任意列、任意排序、跨页遍历或全量导出；
- 修改 Transaction API DTO、数据库 `DECIMAL(50,2)` 或既有 search 语义；
- float、quoted JSON amount、舍入、截断或隐式 scale 转换；
- Adapter 角色判断和默认启用真实业务结果模型出域。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-TXN-001` | 只注册 `transaction.search`，最多一次 `POST /txn/search` |
| `REQ-TXN-002` | 参数/过滤/排序/结果上限由代码与强类型配置共同收紧 |
| `REQ-TXN-003` | 金额范围和 scale 精确，wire 为 JSON number，Java/数据库不舍入 |
| `REQ-TXN-004` | 严格响应与 coverage，不把不完整结果伪装为完整 |
| `REQ-TXN-005` | 原始用户 JWT 透传，业务服务对 ADMIN/VIEWER 最终授权 |
| `REQ-TXN-006` | 模型字段默认空；显式启用时最多为交易类型和金额且 grounded |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-TXN-001` | `L0_00`：业务服务最终授权、外部模型字段默认拒绝 |
| `CON-TXN-002` | `L1_02`：Transaction 独立强类型 Adapter，不扩大业务 API |
| `CON-TXN-003` | `L2_02_00`：ExactDecimal、JWT Client、三视图和 grounding |
| `CON-TXN-004` | 数据库权威：`t_transaction.AMOUNT DECIMAL(50,2)` |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-TXN-001`、`CON-TXN-002` | `DR-TXN-001`、`DR-TXN-002` | `IMPL-TXN-001`、`IMPL-TXN-002` | `TEST-TXN-001`、`TEST-TXN-002` | `VAL-TXN-001` |
| `REQ-TXN-002` | `DR-TXN-003`、`DR-TXN-004` | `IMPL-TXN-003`、`IMPL-TXN-004` | `TEST-TXN-003`、`TEST-TXN-004` | `VAL-TXN-002` |
| `REQ-TXN-003`、`CON-TXN-003`、`CON-TXN-004` | `DR-TXN-005`、`DR-TXN-006` | `IMPL-TXN-005`、`IMPL-TXN-006` | `TEST-TXN-005`、`TEST-TXN-006` | `VAL-TXN-003` |
| `REQ-TXN-004` | `DR-TXN-007`、`DR-TXN-008` | `IMPL-TXN-007` | `TEST-TXN-007`、`TEST-TXN-008` | `VAL-TXN-004` |
| `REQ-TXN-005`、`CON-TXN-001` | `DR-TXN-009`、`DR-TXN-010` | `IMPL-TXN-008`、`IMPL-TXN-009` | `TEST-TXN-009`、`TEST-TXN-010` | `VAL-TXN-005` |
| `REQ-TXN-006` | `DR-TXN-011`、`DR-TXN-012` | `IMPL-TXN-010` | `TEST-TXN-011`、`TEST-TXN-012` | `VAL-TXN-006` |

## 5. 责任分解、内聚与责任边界

| 组件 | 负责 | 不负责 |
|---|---|---|
| Transaction Adapter | 参数/Resolver、fixed wire、strict decode、字段目录和 Provider | 业务角色、数据库精度权威 |
| Business common | ExactDecimal encoder、JWT Client、投影、模型交集和 grounding | Transaction 字段/语法 |
| `transaction-api` | 既有 Java search DTO | Agent 配置与模型策略 |
| `mq-procedure-service` | search、BigDecimal validation、SQL、最终授权 | Agent 编排 |
| 数据库 | `DECIMAL(50,2)` 存储/比较真相 | Agent 输入解析 |

Transaction 语法、精确金额和 wire 保持在本域内聚；跨域只复用 Business common 的稳定契约。依赖方向为 `transaction adapter → business common → capability/model contracts`。禁止业务服务反向依赖 Agent；禁止 Adapter 直连数据库、绕过公共 handler 或调用 `/txn/search` 之外的 Transaction endpoint。

## 6. 当前实现基线与最小变更

当前代码已有完整 descriptor/resolver/validator/mapper/codec/normalizer/fields/settings/provider；Java 端有 endpoint-scoped SecurityWebFilterChain、controller guard、自定义 strict deserializer、`TransactionAmountContract` 和 mapper 比较。

默认动作 `enabled=false`，默认模型字段为空。归档中的多轮 live bootstrap/candidate/evidence 不属于稳定运行架构；它们不应成为代码实现的隐式依赖。

## 7. 动作、参数与配置契约

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-TXN-001` | capability ID 固定 `transaction.search`，domain=`transaction`，service=`mq-procedure-service` |
| `DR-TXN-002` | 每次最多一次 `POST /txn/search`；page 固定 1；不允许 Date、detail、aggregate 或写入 |
| `DR-TXN-003` | 过滤仅 `trans_id/trans_type/trans_type_contains/amount/amount_gt/amount_lt`，且至少一个存在 |
| `DR-TXN-004` | exact 与 contains、exact amount 与 range 互斥；gt&lt;lt；size 1～50；最多两个不同排序字段 |
| `DR-TXN-005` | Agent capability 参数中的金额是 canonical decimal string，转 `Decimal` 后范围≤9999999999999999.99、scale≤2、finite |
| `DR-TXN-006` | wire 金额必须为 canonical JSON number；Java 只接受 numeric token，绑定 BigDecimal，按 DECIMAL(50,2) 边界拒绝而非舍入 |
| `DR-TXN-007` | response 只接受精确 object shape，rows≤requested size，page/size 回显一致，金额仍满足相同精度边界 |
| `DR-TXN-008` | `totalExact=false` 时 coverage 必须 truncated 且 total_count 未知；矛盾空页/总数失败 |
| `DR-TXN-009` | Adapter 只透传原始用户 JWT，不读取角色，不使用 service token |
| `DR-TXN-010` | `mq-procedure-service` 对 `/txn/search` 在 reactive filter chain 和 controller guard 最终授权 ADMIN/VIEWER |
| `DR-TXN-011` | 用户字段固定交易号掩码、交易类型、金额；模型候选最多交易类型和金额，默认空 |
| `DR-TXN-012` | 未知/敏感/冲突/转换失败或 grounding 失败时模型调用为 0 或丢弃候选回答 |

### 7.2 Capability 参数

| 参数 | 类型 | 约束 |
|---|---|---|
| `trans_id` | string | 1～128，exact |
| `trans_type` | string | 1～128，exact |
| `trans_type_contains` | string | 1～128，禁止 `%_\\` |
| `amount` | decimal string | exact，canonical、scale≤2 |
| `amount_gt` | decimal string | open lower bound |
| `amount_lt` | decimal string | open upper bound |
| `size` | integer | 1～50，可省略 |
| `sorts` | tuple of object | 最多 2；field=`trans_id/trans_type/amount`，direction=`ASC/DESC` |

Capability 参数采用 string 表达金额是为了避开 Core JSON/跨语言 float；这不等于业务 wire 接受字符串金额。`TransactionSearchWireCodec` 必须把已验证 `Decimal` 写成 JSON number。

### 7.3 配置

前缀 `AGENT_TRANSACTION_SEARCH_`：

| Key | 默认值 | 边界 |
|---|---:|---|
| `ENABLED` | `false` | canonical boolean |
| `TIMEOUT_MS` | `3000` | 100～5000 |
| `MAX_PAGE_SIZE` | `20` | 1～50 |
| `MAX_RESULT_COUNT` | `20` | 1～50 |
| `FILTER_FIELDS` | 六个代码过滤字段 | 非空子集 |
| `SORT_FIELDS` | 三个代码排序字段 | 可空子集 |
| `USER_FIELDS` | 三字段 | 必须含 `transaction_type,amount` |
| `MODEL_FIELDS` | 空 | 只能是 `transaction_type,amount` 且为 user fields 子集 |
| `USER_TRANSFORMS`/`MODEL_TRANSFORMS` | 固定转换 | field 与 transform 必须精确对应 |

配置只能收紧代码集合与上限；未知 key、重复项、越界、非法 transform 或扩大能力均启动失败。

## 8. ExactDecimal 端到端链

```text
capability argument canonical string
  → Python Decimal (finite, abs≤9999999999999999.99, scale≤2)
  → ExactDecimal
  → canonical JSON number token (not quoted, no exponent, no float)
  → Jackson numeric token
  → Java BigDecimal
  → TransactionAmountContract DECIMAL(50,2) validation
  → MyBatis parameter
  → SQL AMOUNT = / > / <
```

禁止任何阶段使用 float、科学计数法、字符串 coercion、`setScale` 舍入或数据库隐式截断。Agent 的绝对值上限比数据库 DECIMAL(50,2) 更小，是允许的只收紧边界；配置不得扩大。

`amount` 与 `amount_gt/amount_lt` 互斥；同时出现 gt/lt 时必须 `gt < lt`。Java 端对 `amount`、`amountGt`、`amountLt` 分别验证 fraction digits≤2、integer digits≤48、precision≤50。

## 9. Wire、响应、分页、错误分类与调用方可见语义

### 9.1 请求

```http
POST /txn/search
Authorization: Bearer <original user JWT>
Content-Type: application/json

{
  "condition": {"transType": "...", "amountGt": 1.23},
  "page": 1,
  "size": 20,
  "sorts": [{"field": "amount", "direction": "DESC"}]
}
```

请求 body≤4096 bytes。`page` 固定 1；默认 size 为 `min(20,max_page_size,max_result_count)`。caller 不能自定义 endpoint、任意 JSON、Date 字段或认证 header。

### 9.2 响应

顶层必须且仅含 `rows,total,totalExact,page,size`；body≤262144 bytes、无 BOM、无重复 key/NaN/Infinity。每行必须含 `transId,transType,amount`，只容忍既有 DTO 的受控宽字段 `transDate/transDateGt/transDateLt/amountGt/amountLt/transTypeContains`，但不读取或输出它们。

`transId/transType` 为 NFC 1～128 且无控制/双向控制字符。`amount` 必须是 JSON number，解析为 int/Decimal 并满足 Agent 精度上限；字符串和 float 路径拒绝。

### 9.3 Coverage

- `totalExact=true`：rows 数必须等于 `min(total,size)`；truncated=`rows<total`，total_count=`total`。
- `totalExact=false`：非空 rows 才有效；truncated=true，total_count=null。
- rows 空且 `total=0,totalExact=true` → no_result。
- 其他空页/总数/页码矛盾 → invalid response。

HTTP 400 可映射 invalid arguments；401/403/429/5xx、超时、取消、strict decode 或 coverage 失败使用公共有限失败语义，不返回部分 rows。

## 10. 字段投影、模型出域、权限与审计设计

### 10.1 字段矩阵

| field ID | 数据分类 | 用户可见 | 转换 | 模型候选 |
|---|---|---:|---|---:|
| `transaction_id_masked` | transaction identifier | 是 | mask keep last4；短于 5 则缺失 | 否 |
| `transaction_type` | business internal | 是 | bounded text | 是 |
| `amount` | financial value | 是 | decimal 2 | 是 |

用户结果必须含 `transaction_type,amount`。模型候选默认空；显式启用时最多是这两项。原始交易号、JWT、查询条件、原始 row/response 不得进入模型。模型回答必须通过公共 fact ID、规范金额显示和 protected-token grounding。

### 10.2 最终授权

```text
user JWT → agent-service → runtime OpaqueUserToken
→ mq-procedure-service Resource Server
→ reactiveUserRoleJwtAuthenticationConverter
→ POST /txn/search SecurityWebFilterChain
→ CapabilityAccessGuard.requireTransactionRead
```

filter chain 只匹配 `POST /txn/search` 并要求 `ROLE_ADMIN`/`ROLE_VIEWER`；controller guard 再验证 user token 与角色。其它 `/txn/**` endpoint 沿用既有 fallback，绝不因 search 能力获得相同角色授权。

| 主体 | 预期 |
|---|---|
| 用户 + ADMIN/VIEWER | 允许进入 search |
| 用户 + 其他/空 role | 403 |
| service token | 401 / `invalid_token` |
| missing/malformed/expired JWT | 401/认证失败 |

## 11. 核心流程

```text
question → local resolver / ID-only selector
→ deterministic resolver produces validated filters/sorts
→ argument validator → settings mapper(page=1)
→ ExactDecimal wire codec → one JWT HTTP request
→ business final authorization → BigDecimal boundary → SQL
→ strict response + coverage normalization
→ user projection → optional default-off model facts + grounding
→ CapabilityResult
```

每个边界检查 deadline/cancellation；自动 retry/resume=0。失败后不得换用 `/txn/query`、`/txn/condition`、aggregate、detail 或数据库。

## 12. 安全、日志与数据生命周期

- 日志限于 correlation/action/config snapshot、阶段、HTTP/失败类别、rows/coverage 计数、egress disposition 和耗时；禁止 JWT、查询值、交易号、类型、金额、原始 body 和模型文本。
- Decimal 与业务 records 仅驻留请求内存；不缓存、不持久化。
- SQL 为已有只读 search；Agent 不建立事务、不锁表、不扫描后续页。
- 超时/取消/失败后的迟到响应不得进入投影或模型。
- 回滚通过禁用动作或清空模型字段；不改变数据库或 Transaction API。

## 13. 并发、兼容与扩展

- definition/settings snapshot 不可变；HTTP Client 可并发，但 token/request/result 请求隔离。
- `DECIMAL(50,2)`、numeric-token 和 response shape 任一变化都属于跨语言契约变更，须同步 Python codec、Java deserializer/service/mapper 和 fixtures。
- Date、聚合、详情或写入必须新增独立动作设计，不扩展 `transaction.search`。
- 真实模型出域不是结构化 search 成功的必要条件，保持默认关闭与独立验证。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-TXN-001` | `agent-runtime/src/agent_runtime/adapters/transaction/definition.py`：`transaction_search_definition()` |
| `IMPL-TXN-002` | `agent-runtime/src/agent_runtime/adapters/transaction/provider.py`：`TransactionDomainProvider` |
| `IMPL-TXN-003` | `agent-runtime/src/agent_runtime/adapters/transaction/action_resolver.py` |
| `IMPL-TXN-004` | `agent-runtime/src/agent_runtime/adapters/transaction/codec.py`：validator、mapper |
| `IMPL-TXN-005` | `agent-runtime/src/agent_runtime/business/wire_json.py`、`agent-runtime/src/agent_runtime/adapters/transaction/codec.py`：ExactDecimal wire |
| `IMPL-TXN-006` | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/web/TransactionSearchRequestDeserializer.java`、`mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/service/TransactionAmountContract.java`、`mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/mapper/TransactionMapper.xml` |
| `IMPL-TXN-007` | `agent-runtime/src/agent_runtime/adapters/transaction/contracts.py`、`agent-runtime/src/agent_runtime/adapters/transaction/codec.py`、`agent-runtime/src/agent_runtime/adapters/transaction/normalizer.py` |
| `IMPL-TXN-008` | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/TransactionSearchSecurityConfiguration.java` |
| `IMPL-TXN-009` | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java`、`mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/controller/TransactionController.java` |
| `IMPL-TXN-010` | `agent-runtime/src/agent_runtime/adapters/transaction/fields.py`、`agent-runtime/src/agent_runtime/adapters/transaction/settings.py` |

### 14.2 关键类型与签名

```python
class TransactionSearchInput:
    trans_id: str | None
    trans_type: str | None
    trans_type_contains: str | None
    amount: Decimal | None
    amount_gt: Decimal | None
    amount_lt: Decimal | None
    size: int | None
    sorts: tuple[TransactionSort, ...]

class TransactionSearchArgumentValidator:
    def validate(self, arguments: JsonObject) -> TransactionSearchInput: ...

class TransactionSearchRequestMapper:
    def map(self, input: TransactionSearchInput, settings: BusinessActionSettings) -> TransactionSearchWireRequest: ...

class TransactionSearchWireCodec:
    def encode(self, request: TransactionSearchWireRequest) -> BusinessHttpRequest: ...
    def decode_success(self, *, request: TransactionSearchWireRequest, response: BoundedBusinessHttpResponse) -> TransactionSearchWireResponse: ...

class TransactionSearchResponseNormalizer:
    def normalize_success(self, response: TransactionSearchWireResponse) -> BusinessServiceResult[TransactionRecord]: ...
```

```java
public TransactionSearchResponse search(Authentication authentication, TransactionSearchRequest request);
public TransactionSearchResponse search(TransactionSearchRequest request);
public void requireTransactionRead(Authentication authentication);
static void validateSearchCondition(Transaction condition);
```

私有 helper 不是稳定接口，可在不改变金额、wire、失败和授权契约的前提下调整。

## 15. 测试与验收

### 15.1 测试编号定义

| 测试编号 | 覆盖内容 |
|---|---|
| `TEST-TXN-001` | descriptor/domain/service key/单动作 Provider |
| `TEST-TXN-002` | 架构边界：只到 `/txn/search`，Date/aggregate/write 不可达 |
| `TEST-TXN-003` | Resolver/validator 正常、必填、互斥、排序、contains 注入和 Unicode 负例 |
| `TEST-TXN-004` | 配置只收紧、page=1、size/filters/sorts 上限 |
| `TEST-TXN-005` | canonical string→Decimal→JSON number，禁止 float/quoted amount/scientific notation |
| `TEST-TXN-006` | Java BigDecimal precision/scale/极值、等值和开区间、无舍入 Mapper 契约 |
| `TEST-TXN-007` | response exact shape、数字金额、row 字段/长度/大小/BOM/重复 key 负例 |
| `TEST-TXN-008` | exact/inexact total、空页矛盾、truncated 与 total_count |
| `TEST-TXN-009` | ADMIN/VIEWER 允许，unknown/missing/malformed/service token 拒绝 |
| `TEST-TXN-010` | endpoint-scoped matcher、controller guard、其他 `/txn/**` 不扩权 |
| `TEST-TXN-011` | 用户投影、短 ID、decimal 2；模型最多 transaction_type/amount |
| `TEST-TXN-012` | model spy、敏感/未知/冲突零调用、grounding 与日志零泄漏 |

### 15.2 验证编号定义

| 验证编号 | 通过标准 |
|---|---|
| `VAL-TXN-001` | 仅 `transaction.search` 注册并最多一次固定 POST |
| `VAL-TXN-002` | 查询参数、配置和分页只收紧，禁止动作不可达 |
| `VAL-TXN-003` | DECIMAL(50,2) 精确链无 float、字符串 wire、舍入或截断 |
| `VAL-TXN-004` | strict response 与 coverage 一致，不返回部分/伪完整结果 |
| `VAL-TXN-005` | 业务服务最终授权，Adapter 不判断角色 |
| `VAL-TXN-006` | 字段交集和 grounding 通过，默认及拒绝场景模型调用为 0 |

### 15.3 建议命令

```powershell
Set-Location D:\codex\agent-runtime
python -m pytest tests/unit/adapters/transaction tests/contract/adapters/transaction tests/integration/adapters/transaction/test_fake_server.py -q
python -m mypy --strict src/agent_runtime/adapters/transaction tests/unit/adapters/transaction tests/contract/adapters/transaction
python -m compileall -q src/agent_runtime/adapters/transaction

Set-Location D:\codex
mvn -pl mq-procedure-service -am -DskipTests compile
mvn -pl mq-procedure-service -am -Dtest=TransactionSearchRequestDeserializerTest,TransactionAmountContractTest,TransactionServiceSearchTest,TransactionControllerAuthorizationTest,TransactionSearchSecurityConfigurationTest,TransactionSearchSecurityIntegrationTest,TransactionMapperIntegrationTest test
```

真实 JWT/Transaction 数据/外部模型只在独立显式授权下执行，不属于基线校验。

## 16. 可观测性与运维

第一阶段复用现有日志设施，不引入独立监控依赖。仅记录 correlation ID、action、config snapshot、阶段、有限状态/失败类别、row/coverage 计数、egress disposition 和耗时；不记录 JWT、查询值、交易字段、body 或模型载荷。

## 17. 风险与开放项

| 风险 | 控制 |
|---|---|
| Python/Java/DB 金额语义漂移 | 同一精度边界、numeric-token 与跨层测试 |
| DTO 宽字段被错误出域 | strict target fields + field definitions + 默认空模型字段 |
| search 角色扩散至其他 Transaction endpoint | endpoint-scoped filter chain + controller guard |
| inexact total 被当成完整数据 | coverage 显式 `truncated=true,total_count=null` |
| 历史 live 环境失败污染主设计 | live evidence 留档，稳定契约不依赖 bootstrap |

当前无阻断设计开放项。真实业务结果外部模型出域继续默认关闭；其环境或效果失败不影响结构化 search 契约。

## 18. 实施就绪结论

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前代码实现可据本版本复核 |
| 当前允许实施范围 | Adapter/Java search 契约内缺陷修复、测试补齐、配置收紧 |
| 当前禁止动作 | Date/聚合/详情/写入、API/DB 扩张、Agent 角色判断、float/舍入、默认开启真实 egress |
| 当前结论 | Approved；可作为 Transaction Adapter、精确金额与授权代码评审基线 |

## 19. 三轮内部自检与独立评审记录

| 类型 | 状态 | 结论 |
|---|---|---|
| 内部自检第 1 轮 | Passed | 范围、责任、来源、上位与公共 L2 一致 |
| 内部自检第 2 轮 | Passed | search、ExactDecimal、最终授权、字段出域和错误语义一致 |
| 内部自检第 3 轮 | Passed | 真实落点、测试、去重、链接和可读性检查通过 |
| 独立正式评审 | Passed | `REV-L2-02-02-001` 已修复；service-token、ExactDecimal、coverage、字段和最终授权语义与实现复核通过 |
