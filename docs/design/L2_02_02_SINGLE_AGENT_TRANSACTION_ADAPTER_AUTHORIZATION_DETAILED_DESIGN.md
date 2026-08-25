# [L2_02_02] 单体 Agent Transaction 列表查询、跨语言合同与 Adapter 详细设计

> 文档状态：Approved

## 1. 文档信息、上位约束与修订历史

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.3 |
| 更新时间 | 2026-08-25 |
| 上位约束来源 | [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v2.3 |
| 关联责任边界 | [`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v2.3 |
| 归档来源 | [v1.6 已评审旧版](历史文档/L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN_v1.6.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 设计目标、范围外与当前实现基线

唯一动作 `transaction.search` 固定复用 `POST /txn/search`，以逻辑 filters/operator 查询既有 SQL 列表，并保留服务最终读取授权。范围外包括 aggregate、detail、condition、query、写入、管理接口、Agent 数据库直连、float/rounding、跨域 fallback 与新 DTO。

当前实现：Java Controller、`TransactionSearchRequest/Response`、Deserializer、Service 与 Mapper 已支持 transId/transType/transDate/amount；Agent 新 Adapter 已实施独立 field/operator、Date filters、Decimal、完整分页、同字段上下界和受控 result projection。Agent 已严格兼容生产 Spring UTC 零毫秒 offset 字符串与历史 standalone 整秒 epoch 毫秒；真实 Spring 安全链、零模型 20/104 codec 及六场景 controlled 联调均通过。`trans_type eq` 现允许真实安全 token 中的 `_`，`contains` 在公共 validator 与 Adapter 两层拒绝 `_/%/反斜杠`；95 项定向及 1438 项 non-live 回归通过，完整正式 UAT 尚未完成。

| 需求编号 | 需求 |
|---|---|
| `REQ-TXN-101` | 四逻辑字段及独立 operator 映射既有 condition DTO |
| `REQ-TXN-102` | Date/timezone/open interval 与 Decimal/BigDecimal 跨语言严格合同 |
| `REQ-TXN-103` | 多页、offset、四字段排序及稳定 rows/total/totalExact/page/size |
| `REQ-TXN-104` | JWT 透传、业务最终授权、字段投影与失败关闭 |

| 约束编号 | 上位约束 |
|---|---|
| `CON-TXN-101` | 单动作只调用现有 `POST /txn/search`，不新增 DTO/数据库接口 |
| `CON-TXN-102` | 配置不得超过服务 page/size/sort 和现有 Agent 金额上界 |

## 3. 已核实接口契约、模块职责与依赖方向

`TransactionController.search` 执行既有 `requireTransactionRead` 后调用 Service；`TransactionSearchRequest` 包含 `condition/sorts/page/size`，`Transaction` condition 已包含 transId、transType、transTypeContains、transDate、transDateGt/Lt、amount、amountGt/Lt。现有 `TransactionSearchRequestDeserializer` 会跳过未知属性，并对 page/size 使用 Jackson `getValueAsInt()`；因此 Agent 必须先 exact 拒绝未知属性、bool、字符串和非整数，不能依赖业务端反序列化补做严格校验，也不得修改既有公共 DTO。

Service 要求至少一个条件、page≥1、1≤size≤100、最多两项不重复排序；排序字段为 transId/transType/transDate/amount，ASC/DESC；缺少 transId sort 时业务服务会添加稳定 transId tiebreaker。Mapper 使用精确 `=`、严格 `>`、严格 `<` 和 `LIKE contains`，禁止 Agent 伪造 `>=/<=`。依赖方向为 validated Business plan → Transaction Adapter → TransactionController/Service → Mapper/DB；Agent 禁止绕过服务访问数据库。

已存在的关键实现接缝为 `transaction_search_definition()`、`TransactionSearchArgumentValidator.validate(arguments: JsonObject) -> TransactionSearchInput`、`TransactionSearchRequestMapper.map(input: TransactionSearchInput, settings: BusinessActionSettings) -> TransactionSearchWireRequest`、`TransactionSearchWireCodec.encode(request) -> BusinessHttpRequest` 和 `decode_success(*, request, response) -> TransactionSearchWireResponse`。建议在这些既有类中补齐独立 field/operator、Date、page>1 和既有九字段响应兼容；Java `TransactionController.search(Authentication, TransactionSearchRequest) -> TransactionSearchResponse`、公开 DTO 和 Mapper SQL 不改变。

## 4. field/operator/DTO 固定映射

| 逻辑 field | operator | 服务 condition 字段 | value exposure | 数据分类 |
|---|---|---|---|---|
| `trans_id` | `eq` | `transId` | `protected_ref` | 交易标识 |
| `trans_type` | `eq` | `transType` | `safe_token` literal，允许合法 `_` | 内部业务文本 |
| `trans_type` | `contains` | `transTypeContains` | `safe_contains_token` literal，拒绝 `_/%/反斜杠` | 内部业务文本 |
| `trans_date` | `eq` | `transDate` | canonical timestamp literal | 交易时间 |
| `trans_date` | `gt` | `transDateGt` | canonical timestamp literal | 交易时间 |
| `trans_date` | `lt` | `transDateLt` | canonical timestamp literal | 交易时间 |
| `amount` | `eq` | `amount` | canonical decimal literal | 金融金额 |
| `amount` | `gt` | `amountGt` | canonical decimal literal | 金融金额 |
| `amount` | `lt` | `amountLt` | canonical decimal literal | 金融金额 |

`trans_type_contains/trans_date_gt/trans_date_lt/amount_gt/amount_lt` 不再是模型逻辑字段；Java DTO 字段名仅可存在于 Adapter 内。现有 Mapper 对 `transType` 使用参数化 `=`，但对 `transTypeContains` 使用 `LIKE concat('%', value, '%')` 且不转义通配字符，因此同一个逻辑字段必须根据 operator 选择有限代码策略：`eq` 接受真实安全 token 中的 `_`；`contains` 继续拒绝 `_`、`%` 和反斜杠，禁止通过修改 SQL、转义规则或放宽 validator 解决。每字段最多一次同 operator；同字段 `gt+lt` 同时存在时必须严格 lower<upper；eq 与同字段其他 operator 互斥，contains 与 eq 互斥。整体 filters 至少一项，最多 8 项。

## 5. Python/Java Date 接口契约

QueryPlan Date literal 和 HTTP 请求日期初始采用 RFC3339 秒级完整日期时间和显式 `±HH:mm` offset，例如 `2026-08-25T09:00:00+08:00`；业务时区为 `Asia/Shanghai`，必须拒绝无 offset、本地歧义时间和未经合同证明的 fractional precision。Java `TransactionSearchRequestDeserializer` 最终交由 Jackson 解析 `java.util.Date`，因此需要 Java/Python fixture 验证 epoch instant、offset 和 Mapper condition 一致。

必须区分请求与响应的实际序列化环境。运行中 `mq-procedure-service` 的 Spring/Jackson HTTP 响应采用 RFC3339 UTC、三位零毫秒和显式 `+00:00`，例如 `2026-08-25T01:00:00.000+00:00`；`WebTestClient.bindToController(...).build()` 使用独立默认 codec，会将相同 instant 输出为 epoch 毫秒，不能作为生产响应格式的唯一依据。Agent response codec 仅兼容这两个已验证 wire 形态：严格匹配上述 UTC 零毫秒字符串，或可整除 1000 的整数 epoch 毫秒；均按同一 instant 转换到 `Asia/Shanghai`。继续允许既有 nullable Date；拒绝无 timezone、`Z`、非 UTC offset、非零毫秒、其他小数精度、bool、float、日期字符串及无效日历。生产 Spring 配置下的 HTTP/JSON 契约与 Python 两种形态测试必须共同成立，不修改业务 DTO、服务序列化配置或数据库。

`gt/lt` 必须映射现有 SQL 开区间，不能冒充 `>=/<=`。请求级 `Clock` 为唯一相对时间来源；“今天”“最近一周”等自然日转换只有在生产 `TRANS_DATE` 时间精度、offset、时区和严格开区间补偿边界得到证据后开放。该前置未完成时，相对自然日返回 unsupported、业务调用 0；绝对日期 eq/gt/lt 在跨语言合同测试通过后开放。

## 6. ExactDecimal、分页、排序与响应合同

金额列已知为 `DECIMAL(50,2)`；计划 literal 使用规范十进制字符串，例如 `100.00`，Adapter 使用现有 ExactDecimal canonical JSON number 编码，Jackson 接收 JSON number 并绑定 `BigDecimal`。保持 Agent 已有 `abs≤9999999999999999.99`，scale≤2；拒绝 float、指数、字符串 wire、舍入、截断、NaN、Infinity 和隐式 scale 改写。

`1≤page≤1000`，`1≤size≤50`，且配置 `max_size/max_results` 可继续收紧；不得超过服务 size≤100。先用安全整数校验 `(page-1)*size≤2147483647`，再原样映射 Java page/size，不重新固定为 page 1。sort field 仅允许四个逻辑字段，Adapter 转换为现有 camelCase 字段；direction exact 为 ASC/DESC，最多两项且不得重复。

响应顶层 exact 包含 `rows/total/totalExact/page/size`。既有 Java `Transaction` row 的已核实响应可见性包括 `transId/transType/transDate/amount` 和条件属性 `transDateGt/transDateLt/amountGt/amountLt/transTypeContains`；Adapter 只能接受这九项代码绑定白名单，丢弃五项条件属性，并仅将 masked trans_id、trans_type、trans_date、amount 投影给用户，绝不能要求业务服务修改 DTO。真正未知字段失败关闭；Date 仅接受已验证的生产 UTC 零毫秒 offset 字符串或 standalone 整秒 epoch 毫秒，统一输出上海时区秒级字符串，金额保持精度。`totalExact=false` 表示 lower bound；rows 不超过请求 size，page/size 必须和请求一致，空 rows 为 no_result。

## 7. 权限与审计、处理流程和失败类型

Transaction 服务继续执行既有 ADMIN/VIEWER 最终读取授权；Adapter 透传用户 JWT，不代替服务角色判断。用户可见字段和模型可见字段独立：trans_id 永不进入模型，trans_type/amount 仅在独立 result-egress 开关及交集允许时可见；列表查询不要求 answer 模型调用。

处理流程：filters strict decode → code/config validation → protected trans_id binding → fixed condition mapper → canonical Decimal/Date codec → 一次 search → bounded response decode/projection。非法 operator/date/Decimal/page/sort 和 unsupported 必须在请求前失败；forbidden 仅触发一次 search，timeout/unavailable/invalid_response 不重试、不切域。审计只记录有限 action/snapshot/错误/计数，不记录 JWT、交易标识、业务响应或金额明细。

## 8. 实现落点清单

| 实现编号 | 位置 | 目标职责 |
|---|---|---|
| `IMPL-TXN-101` | `agent-runtime/src/agent_runtime/adapters/transaction/contracts.py` | 四字段 filter、Date、Decimal、完整分页和列表记录合同 |
| `IMPL-TXN-102` | `agent-runtime/src/agent_runtime/adapters/transaction/definition.py` | 独立 field/operator、Date、code-bound 限额和四字段 sort |
| `IMPL-TXN-103` | `agent-runtime/src/agent_runtime/adapters/transaction/codec.py` | condition DTO 映射、Date offset、canonical Decimal JSON number、response 校验 |
| `IMPL-TXN-104` | `agent-runtime/src/agent_runtime/adapters/transaction/fields.py` | masked trans_id、trans_type、trans_date、amount 分类和投影 |
| `IMPL-TXN-105` | `agent-runtime/src/agent_runtime/adapters/transaction/settings.py` | 统一 JSON action settings、page/size/sort/Decimal 子集 |
| `IMPL-TXN-106` | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/web/TransactionSearchRequestDeserializer.java` | 只读对照并由测试证明 Date/BigDecimal binding，不预设需要生产改动 |
| `IMPL-TXN-107` | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/mapper/TransactionMapper.xml` | 只读对照现有 =/>/<、contains 和排序，不修改 SQL |

## 9. 测试与验证设计

| 测试编号 | 场景 |
|---|---|
| `TEST-TXN-101` | 四字段/operator 全矩阵、同字段上下界、冲突/unknown/empty 条件；真实类型形状 `eq` 允许 `_`，`contains` 拒绝 `_/%/反斜杠` 且下游零调用 |
| `TEST-TXN-102` | Python→HTTP→Jackson Date offset/instant/open interval；生产 Spring UTC 零毫秒 offset 响应与 standalone 整秒 epoch 毫秒归一；其他 wire 形态拒绝；未验证相对日期 unsupported |
| `TEST-TXN-103` | canonical Decimal、scale≤2、极值、JSON number、BigDecimal、禁止 float/rounding |
| `TEST-TXN-104` | page 2、size 边界、offset overflow、四字段排序、重复/方向/项数拒绝 |
| `TEST-TXN-105` | rows/totalExact/page/size、no_result、九项既有 row 白名单、五项条件属性丢弃、masked ID 和真正未知字段拒绝 |
| `TEST-TXN-106` | ADMIN/VIEWER/denied，非法模型计划或 Date/金额下游零调用 |

| 验证编号 | 验证方式 |
|---|---|
| `VAL-TXN-101` | fake Transaction server、Python condition/Decimal/Date/response contract tests |
| `VAL-TXN-102` | 既有 Java Deserializer/Service/Mapper、真实 Spring 配置 HTTP response Maven 契约与 Date timezone fixture |
| `VAL-TXN-103` | Business/Core/Knowledge 非 live 回归、strict mypy、compileall |

## 10. 设计规则、数据生命周期与迁移回滚

| 规则编号 | 设计规则 |
|---|---|
| `DR-TXN-101` | 四逻辑 field/operator 映射现有 condition DTO，不把 suffix 暴露给模型；`trans_type eq` 使用允许 `_` 的 safe token，`contains` 使用拒绝 SQL LIKE 通配字符的更严格 token |
| `DR-TXN-102` | 请求 Date 使用显式 offset、固定时区和严格开区间；响应只接受生产 UTC 零毫秒 offset 字符串或 standalone 整秒 epoch 毫秒并按同一 instant 转换；相对日期必须先证明边界 |
| `DR-TXN-103` | ExactDecimal canonical string→JSON number→BigDecimal，scale≤2，无舍入 |
| `DR-TXN-104` | page 不固定；size≤50、offset 不溢出、最多两项四字段排序 |
| `DR-TXN-105` | 稳定列表结果、业务最终授权、敏感字段独立投影和失败关闭 |

数据生命周期仅为请求级计划、JWT 和响应；不新增数据库存储、修改数据库结构或执行数据迁移。事务边界与一致性属于 Transaction service/Mapper。最小必要变更扩展既有 Adapter 和 Java contract tests，不修改已有 endpoint/DTO/SQL、引入规则平台或形成额外耦合。

## 11. 风险、评审记录与实施就绪判定

主要风险是 standalone Controller 默认 codec 与真实 Spring/Jackson HTTP codec 对 Date 的序列化不同、生产 TRANS_DATE 精度未证明、金额数值退化、page 溢出、totalExact 误读，以及合法带 `_` 的精确类型被误拒或 contains 通配导致查询扩大。Date 和 operator 文本策略均需 non-live 双向测试先于对应真实 UAT；不得调整业务服务、接受任意日期字符串、放宽 LIKE 校验或重新执行已消费 UAT。首次失败 SHA-256=`cc2905dab7a4d78fd52f7fd8c973b2c41fbaa77db47a0bc6036f45119f34c0c3` 保持不变。

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：设计通过且获得实施授权后 |
| 当前允许实施范围 | Transaction fake Adapter、Date/Decimal/Page/Sort 合同及 Java 非 live 测试 |
| 当前禁止动作 | 真实业务/模型/数据库调用、相对日期无证启用、业务 DTO/SQL/公开接口扩张 |

评审记录：当前大版本已通过独立分层与跨层评审；不继承旧版本评审过程。

## 12. 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-TXN-101`; `CON-TXN-101` | `DR-TXN-101` | `IMPL-TXN-101`; `IMPL-TXN-102` | `TEST-TXN-101` | `VAL-TXN-101` |
| `REQ-TXN-102` | `DR-TXN-102` | `IMPL-TXN-103`; `IMPL-TXN-106`; `IMPL-TXN-107` | `TEST-TXN-102` | `VAL-TXN-102` |
| `REQ-TXN-102` | `DR-TXN-103` | `IMPL-TXN-103`; `IMPL-TXN-105` | `TEST-TXN-103` | `VAL-TXN-102` |
| `REQ-TXN-103`; `CON-TXN-102` | `DR-TXN-104` | `IMPL-TXN-101`; `IMPL-TXN-102`; `IMPL-TXN-105` | `TEST-TXN-104` | `VAL-TXN-101` |
| `REQ-TXN-104` | `DR-TXN-105` | `IMPL-TXN-104` | `TEST-TXN-105`; `TEST-TXN-106` | `VAL-TXN-103` |
