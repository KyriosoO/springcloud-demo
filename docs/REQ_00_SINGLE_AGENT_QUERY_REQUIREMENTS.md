# [REQ_00] 单体 Agent 查询能力建设需求说明

> 文档状态：Approved

## 1. 文档信息与来源

| 项目 | 内容 |
|---|---|
| 文档编号 | REQ_00 |
| 当前版本 | v2.2 |
| 更新日期 | 2026-08-28 |
| 需求来源 | 个人学习、Agent 架构验证，以及现有 Knowledge、Employee、Transaction 查询服务 |
| 当前基线 | Knowledge 与 Business 查询能力均已接入统一 Runtime；功能验收和效果验收分开治理，具体运行状态由 P3/UAT 计划及 evidence 记录 |
| 权威边界 | 规定业务目标、安全边界和验收；不代替 L0/L1/L2 或业务服务接口合同 |
| 归档来源 | [v1.8 已评审旧版](历史文档/REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS_v1.8.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。v2.2 在既有 Employee 接口内增加受控多值引用、前缀/包含任一、同字段收紧型 AND 与有限行政区别名需求；不新增 endpoint、DTO、ES 结构或本地语义 Resolver。

## 2. 背景、设计目标与非目标

建设一个逻辑 Agent，优先打通知识查询以及 Employee、Transaction 只读列表查询。Spring 负责接入与治理，Python Runtime/LangGraph 负责唯一编排，业务服务保留数据、检索实现和最终授权。设计应与个人学习和技术验证的背景匹配，不引入配置中心、规则平台、审批系统或产品级证据体系。

非目标：新增业务公开接口或 DTO、直接访问业务数据库/ES、写操作、聚合、工作流、多 Agent、业务域间自动切换、文档录入，以及未经确认的字段、角色或模型出域扩张。

## 3. 已核实能力、目标与当前差距

| 对象 | verified existing | target design | 当前差距 |
|---|---|---|---|
| Knowledge | 既有问题改写、检索、证据及摘要链路；既有 P5 结论为 ineffective | 保持原有独立能力和结果，不作为 Business fallback | 不属于本次业务设计纠偏 |
| Employee 条件搜索 | `POST /employees/es/search` 支持 keyword、filter、分页、排序；Controller 读取守卫、endpoint-scoped 共享 converter、Agent Adapter 和真实 UAT 已通过 | `employee.search` 返回受控列表，业务服务执行读取角色授权 | 上海联系地址真实查询返回 20 条；Employee search 6 次 |
| Employee 语义搜索 | `POST /employees/es/vector-search` 支持 `queryText` 等语义检索参数，不支持结构化 filter；Agent Adapter、共享 converter、v4 完整意图与真实 UAT 已通过 | `employee.semantic_search` 返回受控列表；semantic+地址必须 unsupported/零调用 | 真实 semantic 返回 9 条；semantic+地址零业务调用 |
| Transaction 搜索 | `POST /txn/search` 已支持标识、类型、日期、金额、分页和排序，服务已执行读取授权；新版 Adapter、operator-specific 文本策略和真实 UAT 已通过 | `transaction.search` 完整映射既有列表搜索能力 | 正式 UAT search 7 次；相对日期/聚合零业务调用 |

现有 `employee.detail` 属于已实现的历史能力，不是本版 Employee 主查询目标；调用方、兼容性和历史审计资产已核实，仅保留仍有调用方的历史兼容实现，不进入目标生产链路。

## 4. 唯一查询链路与需求编号

`REQ-BQS-001`：

```text
用户问题 → 输入安全闸门与请求级 protected slot 提取
→ LLM 基于最小化问题和 slot 引用生成受限 QueryPlan → Model 严格解码为 JsonObject
→ Business 严格解码、配置校验和 protected value 绑定
→ 唯一 ActionCandidate → Employee/Transaction Adapter
→ 现有业务服务 → 业务服务最终授权与 ES/向量/SQL 查询
→ 响应严格解析、字段投影和脱敏 → 用户列表结果
```

LangGraph 维护唯一请求级状态，每次请求最多调用一个动作和一个业务 endpoint。输入闸门只做安全识别、最小化与 slot 提取，不选择 domain/action、生成 filters 或补充业务语义。禁止 Local Resolver 绕过 LLM、ID-only 补参、模型失败本地降级、Business→Knowledge、跨域 fallback、普通与向量搜索互相 fallback、客户端二次筛选，以及模型生成 SQL、DSL、URL、索引、表列、类名或方法名。

`REQ-BQS-002`：外层 QueryPlan 只能包含 `domain/action/arguments`；列表 arguments 使用 `filters/page/size/sorts`，其中每条 filter 包含 `field/operator/value`。value 严格为 `literal`、`value_ref` 或受控敏感多值 `value_refs` 之一；`value_refs` 仅供多值 operator 使用，数量 1～16、不得重复且必须全部属于当前请求并与目标逻辑字段类型一致。`in` 保持完整值精确任一，新增 `prefix_any/contains_any` 分别表达前缀任一和包含任一。允许 Decimal/Date 的 `gt+lt`，以及配置和代码共同批准的 Text 同字段收紧型 AND；拒绝重复键、未知属性、null、float、非有限值、超限集合和不被现有接口支持的组合。语义查询只允许受限业务语义文本与受控数量，不允许结构化 filter。

`REQ-BQS-003`：配置按 `version → domain → action → field/operator/result/egress` 组织；Employee keyword 必须具有同一份配置中的动作级 enable、输入保护及代码绑定字段集合，不能绕过字段策略。配置只能收紧 `业务服务现有能力 ∩ Adapter 代码合同 ∩ 数据分类策略`。采用单个版本化 JSON 文件与既有严格 Python 解析，不引入新平台。

## 5. Employee 列表与语义查询

| 逻辑字段 | 服务字段 | 可选操作符上界 | 输入保护 |
|---|---|---|---|
| `contact_address` | `contactAddress` | `contains/contains_any` | 代码绑定行政区 literal 或 literal list；详细地址必须 `value_ref` |
| `chinese_name` | `chineseName` | `eq/contains/prefix/in/prefix_any` 的代码绑定子集 | `value_ref/value_refs` |
| `employee_identifier` | `idCardNo` | `eq` | `value_ref` |
| `member_no` | `memberNo` | `eq/prefix` 的代码绑定子集 | `value_ref` |
| `phone_no` | `phoneNo` | `eq/prefix` 的代码绑定子集 | `value_ref` |
| `email` | `email` | `eq` | `value_ref` |
| `position` | `position` | `eq/contains/prefix/in` 的代码绑定子集 | 安全业务文本 literal |

`REQ-BQS-004`：用户问“帮我查询上海的员工”“上海地区的员工”或“上海市的员工”时，LLM 都应生成 `employee.search + contact_address contains`，本地只把模型已选择的有限行政区别名规范为“上海”。多地区使用 `contains_any`，不得用精确 `in` 冒充地址包含任一。单一姓氏使用 `chinese_name prefix + value_ref`，多个完整姓名使用 `in + value_refs`，多个姓氏使用 `prefix_any + value_refs`，姓氏与姓名片段可按批准矩阵形成同字段 `prefix+contains` AND。`keyword` 仅匹配现有服务的 `contactAddress/chineseName/idCardNo`；真实姓名、员工标识及详细地址不得以明文进入模型。

`REQ-BQS-005`：`workBaseSi/workBaseAf` 虽存在于部分代码或数据库模型，但当前数据没有有效启用；不得进入开放字段、模型目录、成功 UAT 或结果投影。未来开放必须重新核实真实数据、索引同步、设计和 UAT，而不能只改配置。

`REQ-BQS-006`：`employee.semantic_search` 只传递安全业务语义，embedding 参数和向量物理信息由固定代码掌握。现有 `buildEmbeddingText` 含姓名、联系地址、职位、教育/院校/专业及 workBase 字段，但这不代表支持单字段向量查询，亦不代表 workBase 字段已启用。语义检索与结构化地址过滤不能由现有单接口同时表达时返回 `unsupported`，业务调用为 0。

## 6. Transaction 列表查询

| 逻辑字段 | 允许 operator | Adapter 到现有 DTO 的固定映射 |
|---|---|---|
| `trans_id` | `eq` | `condition.transId` |
| `trans_type` | `eq/contains` | `condition.transType/transTypeContains` |
| `trans_date` | `eq/gt/lt` | `condition.transDate/transDateGt/transDateLt` |
| `amount` | `eq/gt/lt` | `condition.amount/amountGt/amountLt` |

`REQ-BQS-007`：field 和 operator 分离，支持同字段 `gt + lt` 范围；不得把 `amount_gt`、`trans_date_lt` 等 DTO 映射名公开给模型。日期使用带明确时区的规范时间格式；`gt/lt` 均为严格开区间。业务时区固定 `Asia/Shanghai`；“今天”“最近一周”等相对自然日只有在请求级时钟、数据库时间精度和边界规则得到合同证据后开放，否则 `unsupported`。

`REQ-BQS-008`：金额对齐 `DECIMAL(50,2)`；QueryPlan 使用 canonical decimal string，Java wire 使用 JSON number，业务服务使用 BigDecimal；保持现有更严格金额绝对值上界，scale≤2，禁止 float、舍入、截断和隐式 scale 转换。

`REQ-BQS-009`：page≥1，不再固定为 1；size 不得超过业务服务上限 100，也不得突破 Agent 现有更严格代码上限 50；验证 `(page-1)×size` 不溢出。排序只允许四个已核实字段、`ASC/DESC`、最多两项。结果包含 `rows/total/totalExact/page/size`；`totalExact=false` 表示下界估计，不得宣称精确总数。

## 7. 权限、敏感输入与模型出域

`REQ-BQS-010`：Employee 两个 ES endpoint 必须由业务域 `requireEmployeeRead` 执行最终读取授权，并经其端点级安全链显式使用既有共享 JWT role converter；先核实已有调用方兼容性，验证真实 ADMIN/VIEWER role claim 允许和无权限、missing、malformed、service-token 拒绝，不改变 detail 或其他 endpoint 的既有行为。Transaction 继续由服务执行最终读取授权。Agent 和 Adapter 只透传当前用户 JWT，不替代业务角色判定。

`REQ-BQS-011`：模型只能看到最小化问题、模型安全动作/字段/operator 目录、请求级 slot、配置 snapshot 及已批准的时间上下文；目录必须描述 operator 语义、单/多值形状、数量上限和允许的 tagged value。不得看到身份证号、员工编号、电话、邮箱、姓名、详细地址、JWT、凭证、业务原始响应、ES `_source`/`embeddingText`、索引或数据库物理信息。输入安全层只提取并替换敏感值，保留词序和 AND/OR 连接词，不得选择 domain/action/operator 或生成 filter。对不含“员工”但具有受保护姓名/姓氏强提示的输入，本地只允许进入受控规划，最终 domain/action 仍由 LLM 决定；无法可靠准入时返回 unsupported。

Employee 原始 ES JSON 必须在 Adapter 内进行 content-type、长度和结构校验，严格解析 hits，并丢弃 `embedding`、`embeddingText`、workBase 和未知字段；不得仅因原始响应而新增业务 endpoint 或公共 DTO。

## 8. 失败关闭和可观测性

`REQ-BQS-012`：模型失败、非法计划、不支持字段/operator、slot 非法、配置不一致、日期或金额无效、分页排序超界、物理表达式、workBase 字段及不可表达的语义+结构组合必须失败关闭，且下游业务调用为 0；业务服务返回拒绝时仅允许本次既定调用，不重试、不跨域、不回退。

仅记录 correlation ID、action、配置快照、有限阶段/错误、调用计数和耗时；不记录问题正文、slot 值、密钥、JWT、原始 QueryPlan、原始模型响应或原始业务响应。对个人学习项目保持普通日志和最小测试证明，不建设复杂审计平台。

## 9. 验收顺序与开放事项

1. 公共接入冒烟：认证、严格 JSON、默认 stub、单动作与 unsupported。
2. Employee：上海地址、职位、受保护标识/姓名、ES 列表、语义检索、权限矩阵、workBase 拒绝和 ES 字段丢弃。
3. Transaction：类型、日期、金额、同字段区间、组合过滤、分页、排序、精度及拒绝矩阵。
4. 结构化查询收口：Access/Core/Model/配置/Adapter/JWT/单动作与失败零调用回归。
5. Employee 自然语言扩展：单/复姓、多姓名、多姓氏、同字段 AND、行政区别名、多地区及问句/祈使句；真实模型和 Employee search 均受独立总预算约束。

实施状态由 P3 与 UAT 计划记录；本需求只要求 Employee/Transaction 读取守卫、严格 QueryPlan、固定 Adapter、业务最终授权、失败关闭及受控结果成立，不保存运行批次、调用计数或证据哈希。
