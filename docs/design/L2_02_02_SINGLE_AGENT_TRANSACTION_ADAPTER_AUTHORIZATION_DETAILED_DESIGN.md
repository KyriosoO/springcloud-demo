# [L2_02_02] 单体 Agent Transaction QueryPlan、Adapter 与授权详细设计

> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | L2_02_02 |
| 当前版本 | v1.5 |
| 更新日期 | 2026-08-25 |
| 上位设计 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v1.3 |
| 公共详细设计 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v1.7 |
| 业务接口 | `POST /txn/search` |
| 实施状态 | Transaction QueryPlan definition/config/protected-ref、Runtime 唯一分支、Java 合同回归、专属旧 Resolver 清理、fake 系统闭环及真实 no_result/forbidden/unsupported 三场景均已验证；正式 UAT 尚未执行 |

## 2. 修改历史、设计目标与范围

| 版本 | 日期 | 修改内容 |
|---|---|---|
| v1.1 | 2026-08-21 | 既有 Transaction Adapter/Decimal/授权基线 |
| v1.2 | 2026-08-24 | Transaction 目标改为 LLM search QueryPlan，保留精确金额和有限查询上界 |
| v1.3 | 2026-08-24 | 同步 `WP-TXN-QUERYPLAN-01` 实施证据；固定 POST/Decimal/业务授权不变，Runtime/live 仍由后续工作包承接 |
| v1.4 | 2026-08-24 | 明确删除无调用方的 Transaction 专属 Local Resolver 源码/测试，不修改 Decimal/POST、历史 evidence 或共享组件 |
| v1.5 | 2026-08-25 | 仅同步 Transaction 真实 no_result/forbidden/unsupported 三场景及 P3 门禁关闭；Date 仍 unsupported |

设计目标是只复用 `/txn/search` 完成 LLM 受限查询。范围外/不负责：Date、aggregate、detail、写入、管理、新 DTO、数据库结构和业务角色变更。

上位约束来源是 L1_02 v1.3 与 L2_02_00 v1.7。关联责任边界：Transaction L2 负责 search definition/config/codec，公共 plan 层负责 exact 校验/binder，业务服务负责最终授权和 SQL。`CON-TXN-001`：禁止 Transaction Adapter 依赖模型、其他 endpoint、Employee/Knowledge 或数据库直连。

### 2.1 当前实现基线与只读接口核实

已核实：

- `mq-procedure-service/.../TransactionController.search(Authentication, TransactionSearchRequest)` 调用 `CapabilityAccessGuard.requireTransactionRead(...)`；
- `transaction-api/.../query/TransactionSearchRequest` 含 `condition/sorts/page/size`；
- `TransactionSearchResponse` 含 `rows/total/totalExact/page/size`；
- `TransactionService.search(...)` 最终调用 Mapper，可支持交易 ID/类型/日期/金额条件与排序，但 Agent 配置只开放本设计子集；
- detail、condition、query、aggregate、write 等接口不属于 Agent 本期范围。

本期唯一动作：`domain=transaction`、`action=transaction.search`。固定 `POST /txn/search`，page=1；排除 Date、聚合、detail、写入和管理。

## 3. 模块职责、依赖方向与核心处理流程

```text
minimized transaction question
  → LLM QueryPlan {transaction, transaction.search, arguments}
  → common exact/business config validation
  → protected ref binding (only when trans_id is used)
  → TransactionSearchArgumentValidator
  → TransactionSearchRequestMapper
  → TransactionSearchWireCodec
  → POST /txn/search + user JWT
  → business final authorization
  → Java BigDecimal / Mapper SQL owned by service
  → strict response / projection
```

模型不生成 endpoint、Java DTO、SQL/ES、列名或 float。失败不得切 Employee、Knowledge 或本地 Resolver。

## 4. Transaction 接口契约设计与动作定义

### 4.1 目标 Definition

修改 `agent-runtime/src/agent_runtime/adapters/transaction/definition.py`，保留函数签名：

```python
def transaction_search_definition() -> BusinessActionDefinition[
    TransactionSearchInput,
    TransactionSearchWireRequest,
    TransactionSearchWireResponse,
    TransactionRecord,
]: ...
```

删除 `local_action_resolver=TransactionSearchLocalActionResolver()`，增加代码绑定 query fields：

| argument | 逻辑字段/操作符 | 类型 | 模型输入 | 代码上界 |
|---|---|---|---|---|
| `trans_id` | transaction id / eq | identifier | protected_ref | 1～128 字符 |
| `trans_type` | transaction type / eq | text | model_literal | 1～128；`SAFE_TOKEN` |
| `trans_type_contains` | transaction type / contains | text | model_literal | 1～128；`SAFE_CONTAINS_TOKEN`，因此同时禁 `%_\` |
| `amount` | amount / eq | decimal | model_literal | abs≤9999999999999999.99，scale≤2 |
| `amount_gt` | amount / gt | decimal | model_literal | 同上 |
| `amount_lt` | amount / lt | decimal | model_literal | 同上 |
| `size` | page size | integer | model_literal | 1～50 |
| `sorts` | result sort | sort_list | model_literal | 最多2；有限字段/方向 |

组合规则：

- 六个 filter 至少一个；
- `trans_type` 与 `trans_type_contains` 互斥；
- `amount` 与 `amount_gt/amount_lt` 互斥；
- 同时存在 `amount_gt/amount_lt` 时 `gt < lt`；
- sorts 字段不重复。

### 4.2 QueryPlan 示例

```json
{
  "domain": "transaction",
  "action": "transaction.search",
  "arguments": {
    "trans_type": {"literal": "PAYMENT"},
    "amount_gt": {"literal": "100.00"},
    "amount_lt": {"literal": "500.00"},
    "size": {"literal": 20},
    "sorts": {"literal": [
      {"field": "amount", "direction": "DESC"}
    ]}
  }
}
```

如果问题含具体 transaction ID，Guard 将值放入 slot，模型输出 `{"value_ref":"slot-N"}`；binder 恢复为既有 `trans_id` 参数。

### 4.3 禁止计划

- Date keys、aggregate/group/metric/detail/write/admin；
- 未声明字段/operator、空条件、多个 action/domain；
- amount JSON float/number、指数、scale>2、舍入后才能合法的值；
- SQL/ES/URL/index/table/column/class/method 键，或含引号、冒号、斜线、括号、分号、等号、尖括号等物理表达式形态的文本 literal；
- sort expression、任意方向、重复字段、page≠1。

## 5. 强类型配置

`TransactionAdapterSettings.from_env(env)` 目标扩展：

| 配置 | 代码上界 | 只收紧要求 |
|---|---|---|
| enabled | action 已定义 | 默认 false |
| config_version | 必填 | snapshot material |
| code_contract_version | `transaction-search-plan-v1` | exact |
| service_contract_ref | `transaction-search-v1` | exact |
| filter fields/operators | 表 4.1 | 任意子集，但启用 action 时至少一个 filter |
| max_decimal_abs | `9999999999999999.99` | 不得扩大 |
| max_decimal_scale | 2 | 0～2，不得扩大 |
| fixed_page | 1 | 不可变 |
| max_page_size/max_result_count | 50 | 1～50 |
| sort fields | `trans_id/trans_type/amount` | 子集 |
| sort directions | `ASC/DESC` | 子集 |
| max_sort_items | 2 | 0～2 |
| user fields | masked id/type/amount 代码集合 | 至少 type+amount |
| model fields | type/amount | 默认空且为 user 子集 |

业务服务公开 DTO 支持更宽字段和 size≤100，不代表 Agent 可配置扩大到该上界；以代码 definition 的更窄上界为准。

## 6. Python 参数与 Decimal

复用：

```python
class TransactionSearchArgumentValidator:
    def validate(self, arguments: JsonObject) -> TransactionSearchInput: ...

class TransactionSearchRequestMapper:
    def map(
        self,
        input: TransactionSearchInput,
        settings: BusinessActionSettings,
    ) -> TransactionSearchWireRequest: ...
```

QueryPlan validator 先把 tagged literal 解包为既有参数 JSON：文本/int/sorts 保持类型，Decimal 保持 canonical string；既有 validator 用 `Decimal(value)` 精确构造并再次检查范围/scale/组合。

`trans_type` 必须按公共 `SAFE_TOKEN` 逐 Unicode code point 校验，`trans_type_contains` 按 `SAFE_CONTAINS_TOKEN` 校验；不使用可配置正则、不规范化文本、不移除非法字符。该规则是 Agent 代码上界，只收紧现有业务 DTO，不改变服务契约。

禁止 `float` 进入任一阶段。默认 size 仍为 `min(20,effective_max)`，这是执行边界默认值，不改变查询过滤含义；page 固定1。

## 7. Wire 与 Java 契约

### 7.1 Python codec

```python
class TransactionSearchWireCodec:
    def encode(self, request: TransactionSearchWireRequest) -> BusinessHttpRequest: ...
    def decode_success(
        self,
        *,
        request: TransactionSearchWireRequest,
        response: BoundedBusinessHttpResponse,
    ) -> TransactionSearchWireResponse: ...
```

固定 POST `/txn/search`、无 query。逻辑字段映射为 Java DTO 字段；Decimal 通过 `ExactDecimal` 和 canonical encoder 写成 JSON number，不是字符串，不舍入。

### 7.2 Java DTO/方法

保持现有：

```java
public TransactionSearchResponse search(
    Authentication authentication,
    TransactionSearchRequest request)

public TransactionSearchResponse search(TransactionSearchRequest request)
```

`TransactionSearchRequest.condition` 的 amount/amountGt/amountLt 绑定为 Java `BigDecimal`；数据库生产列为 `DECIMAL(50,2)`，但 Agent 仍使用更窄绝对值范围和 scale≤2。链路必须验证 canonical JSON number → BigDecimal → Mapper `=/>/<` 无 float、无舍入和隐式 scale coercion。

### 7.3 Response

Python strict decode 要求顶层 exact `rows,total,totalExact,page,size`；page/size 与请求一致，row 只接受 `transId/transType/amount` 及既有兼容宽字段集合，用户投影只输出 masked ID、type、amount。`totalExact=false` 时 total 是下界，不得改写为精确总数。

## 8. 权限、审计设计与 endpoint 隔离

Adapter 透传用户 JWT；Transaction service `CapabilityAccessGuard.requireTransactionRead(...)` 作最终授权。Agent 不配置角色。

必须证明目标链路只可达 `/txn/search`。以下现有 endpoint 即使业务服务公开也不可达：`/{transId}`、`/condition`、`/query`、`/aggregate`、根 POST、update/delete、MQ/Kafka 测试入口。

## 9. 错误分类、失败与调用方可见错误码

| 场景 | 状态 | plan/search calls |
|---|---|---|
| 认证/strict JSON/输入策略拒绝 | 既有状态 | 0/0 |
| model failure/timeout | `downstream_failure/timeout` | 1/0 |
| empty/Date/aggregate/illegal operator | `unsupported/invalid_argument` | 1/0 |
| Decimal/组合/size/sort 非法 | `invalid_argument` | 1/0 |
| authorized success/no result | `success/no_result` | 1/1 |
| forbidden | `forbidden` | 1/1 |
| HTTP/codec failure | `downstream_failure` | 1/1 |

不得 retry、补跑、切域、回退 Knowledge 或本地补参数。

## 10. 结果与模型出域

用户结果代码上界：`transaction_id_masked`、`transaction_type`、`amount`；至少 type+amount。可选模型字段上界仅 type+amount，默认空。

规划模型不接收业务结果；答案模型仅在结果 egress 显式启用且交集/grounding 通过后调用。transaction ID、JWT、原始 rows、未分类字段和禁止文本不得出域；answer failure 不触发第二次 search。

## 11. 实现落点清单

| ID | 路径 | 类型 | 目标变更 |
|---|---|---|---|
| `IMPL-TXN-001` | `agent-runtime/src/agent_runtime/adapters/transaction/definition.py` | 修改 | 去 Resolver；增加 query fields/rules/version ref |
| `IMPL-TXN-002` | `agent-runtime/src/agent_runtime/adapters/transaction/settings.py` | 修改 | typed input config/Decimal/page/sort/snapshot |
| `IMPL-TXN-003` | 已删除的 Transaction 专属 action resolver | 已清理 | 专属旧旁路且无有效调用方；历史 evidence/hash 不删除 |
| `IMPL-TXN-003A` | 已删除的 Transaction 专属 resolver 单元测试 | 已清理 | 仅验证已废弃专属实现，等价负向由 QueryPlan/组合根测试覆盖 |
| `IMPL-TXN-004` | `agent-runtime/src/agent_runtime/adapters/transaction/codec.py` | 最小适配/回归 | plan unwrapped args 复用、wire 精度不变 |
| `IMPL-TXN-005` | `agent-runtime/src/agent_runtime/adapters/transaction/provider.py` | 修改 | 注册无 Resolver definition/snapshot |
| `IMPL-TXN-006` | `transaction-api/.../query/*` | 只读回归 | 不修改公开 DTO |
| `IMPL-TXN-007` | `mq-procedure-service/.../TransactionController.java` | 只读回归 | 不修改 endpoint/guard |

## 12. 测试与验证设计

| ID | 覆盖 |
|---|---|
| `TEST-TXN-001` | exact QueryPlan、有限 field/operator/exposure |
| `TEST-TXN-002` | at-least-one、type 互斥、amount 互斥/range、两类安全文本策略与物理表达式值拒绝 |
| `TEST-TXN-003` | Decimal canonical/scale≤2/绝对值/无 float/无舍入 |
| `TEST-TXN-004` | page=1、size≤50、sort allowlist/≤2/不重复 |
| `TEST-TXN-005` | Date/aggregate/detail/write/物理键 unsupported 且 search=0 |
| `TEST-TXN-006` | trans_id protected ref 与并发/零泄漏 |
| `TEST-TXN-007` | POST exact body、JSON number→BigDecimal→DB comparison |
| `TEST-TXN-008` | strict response、totalExact、投影/egress |
| `TEST-TXN-009` | JWT/ADMIN/VIEWER/拒绝矩阵 |
| `TEST-TXN-010` | 仅 `/txn/search` 可达，其他 endpoint=0 |
| `TEST-TXN-011` | model failure 无 Resolver/Employee/Knowledge fallback |
| `TEST-TXN-012` | Python/Java DTO、数据库 precision/scale 兼容回归 |
| `TEST-TXN-013` | 删除后引用扫描为0；旧 UAT launcher 不再选择 Resolver 测试；历史 manifest/hash 不变 |

## 13. 设计决策

| ID | 决策 |
|---|---|
| `DR-TXN-013` | 只复用现有 `/txn/search`，Agent 范围窄于业务 DTO |
| `DR-TXN-014` | 模型生成逻辑过滤/分页/排序，物理映射固定在 Adapter/服务 |
| `DR-TXN-015` | Decimal plan 用 canonical string，wire 用 JSON number，Java 用 BigDecimal |
| `DR-TXN-016` | page 固定1、size≤50、sort≤2，配置只能收紧 |
| `DR-TXN-017` | Date/aggregate/detail/write 明确不可达 |
| `DR-TXN-018` | 具体 trans_id 使用 protected ref；其他允许字段按配置决定 literal |

## 14. 当前差距与门禁

`WP-TXN-QUERYPLAN-01` 及其 non-live system E2E 已完成，Runtime 唯一分支已消费该 definition；8 个逻辑字段、4 条组合规则、配置版本/Decimal/page/sort 上界和 transaction ID protected-ref 已落地。专属旧 Resolver 源码/测试已按 `CLN-BQP-001` 清理，真实 DeepSeek/Transaction 服务的 no_result、forbidden、unsupported 三场景均已通过，Transaction search 调用精确为2；正式 UAT 尚未执行。

## 15. 评审记录

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | search 字段、Decimal、分页/排序与跨语言合同 | 补齐实现/测试追踪，修复后通过 |
| 内审2 | 非法计划与失败关闭 | 明确不切域、不回退、不补参数，修复后通过 |
| 内审3 | Java BigDecimal/DB `DECIMAL(50,2)`、endpoint 可达性与 DAG | 只读证据一致，无新增问题，通过 |
| 独立评审 R1～R3 | L2 与跨层一致性 | 增加代码绑定安全文本策略，Decimal/分页/排序/Java合同保持不变；R3 无发现，通过 |
| v1.4 内审1 | 专属 Resolver 调用方 | 仅旧单元/旁路测试引用，production definition 已为 None |
| v1.4 内审2 | 历史证据与共享合同 | 专属实现文件不在冻结 manifest；shared resolver 与 evidence 保持 |
| v1.4 内审3 | Decimal/POST/授权范围 | 清理不改金额、codec、Java DTO、endpoint、DB或角色 |
| v1.4 独立评审 R1～R3 | Transaction 专属删除与跨语言稳定 | 确认 action_resolver 未被冻结 manifest 引用；R3 无发现 |

Approved 本身不替代真实证据；本目标只使用新的 Transaction 三场景集成结果，不使用 GATE-026 历史 evidence 代替。

## 16. 数据生命周期、一致性、风险与实现就绪判定

QueryPlan、Decimal、JWT 和响应只存在于单请求生命周期，无持久化或数据迁移；只读 search 不创建 Agent 事务，数据库一致性与事务边界属于业务服务。设计复用既有 `TransactionSearchInput`/codec/Java DTO 稳定契约，仅增加计划 definition/config，是最小必要变更并与 Core 解耦。风险是 float/舍入、开放禁止 endpoint、配置扩大和跨域降级，由 exact Decimal、reachability、startup subset 和零调用审计控制。

| 项目 | 内容 |
|---|---|
| 是否可作为实现依据 | 是 |
| 实现说明 | IMPL-TXN-001～007、Runtime/E2E 消费及真实 no_result/forbidden/unsupported 三场景均已通过代码对照设计复核 |
| 当前允许实施范围 | Transaction non-live 实现及一次性真实三场景均已完成；正式 UAT 仍需独立门禁 |
| 当前禁止动作 | Date/aggregate/detail/write、新 DTO/DB/角色、float/舍入、预算外真实调用、恢复 Resolver |

## 17. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-TXN-001`; `CON-TXN-001` | `DR-TXN-013` | `IMPL-TXN-001` | `TEST-TXN-001` | `VAL-TXN-001` |
| `REQ-TXN-002` | `DR-TXN-015` | `IMPL-TXN-004` | `TEST-TXN-003` | `VAL-TXN-002` |
| `REQ-TXN-003` | `DR-TXN-017` | `IMPL-TXN-007` | `TEST-TXN-005` | `VAL-TXN-003` |
