# [REQ_00] 单体 Agent 查询能力建设需求说明

> 文档状态：Approved（v3.2 定向修订已通过独立复评；不代表代码或UAT完成）

## 1. 文档信息与来源

| 项目 | 内容 |
|---|---|
| 文档编号 | REQ_00 |
| 当前版本 | v3.2 |
| 日期 | 2026-09-29 |
| 需求来源 | 个人学习、Agent 架构验证，以及现有 Knowledge、Employee、Transaction 查询服务 |
| 当前基线 | Knowledge 与 Business 查询能力均已接入统一 Runtime；功能验收和效果验收分开治理，新Knowledge状态由P3_01/UAT_02记录；Business维护验收由UAT_00记录，原运行事实保留于历史计划及evidence |
| 权威边界 | 规定业务目标、安全边界和验收；不代替 L0/L1/L2 或业务服务接口合同 |
| 归档来源 | [整理前 v2.5 原文](历史文档/2026-09-14-unified-v3-baseline/REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md)；[完整性清单](历史文档/2026-09-14-unified-v3-baseline/README.md) |


本文件纳入新的统一文档版本序列；v3.0不是软件、API、模型任务、配置或索引版本。原版本及字节归档见上表。评审状态、实施状态、部署状态和UAT状态分别判断；历史通过不自动覆盖新合同。

修订历史：2026-09-14，整理纳入统一文档基线v3.0；原版本、源提交及完整字节归档见上表。本次版本序列重置不是代码或设计回滚，评审、实施、部署和UAT状态分别管理。

本轮v3.0经三轮内审及两轮同一执行者的分层/跨层正式复核通过；仅证明文档整合，不表示新实现、部署或UAT已完成。完整发现与验证见本次归档MIGRATION.md。

本次v3.1仅修订计划引用、权威归属和维护状态，不改变业务合同；本轮限定迁移复核已通过（同一执行者分阶段），原v3.0评审范围不扩大为新实现/验收。新入口及历史追溯见[计划迁移说明](plans/历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

v3.2定向修订REQ-KQ-202/203的回答边界：允许由直接原文支撑、逐点可引用的有限解释或条件判断；不授权无依据推理、个性化税务结论或新公开字段。定向独立复评通过，不改变当前实现和UAT状态。

## 2. 背景、设计目标与非目标

建设一个逻辑 Agent，优先打通知识查询以及 Employee、Transaction 只读列表查询。Spring 负责接入与治理，Python Runtime/LangGraph 负责唯一编排，业务服务保留数据、检索实现和最终授权。设计应与个人学习和技术验证的背景匹配，不引入配置中心、规则平台、审批系统或产品级证据体系。

非目标：新增业务公开接口或 DTO、Agent 直接访问业务数据库/ES、在线写操作、通用内容管理平台、工作流、多 Agent、业务域间自动切换，以及未经确认的字段、角色或模型出域扩张。阶段 A 仅允许独立离线工具受控获取官方公开正文/附件并构建新候选索引；该能力不是 Agent 动作，也不进入在线请求路径。

## 3. 已核实能力、目标与当前差距

| 对象 | verified existing | target design | 当前差距 |
|---|---|---|---|
| Knowledge | 既有问题改写、类型化检索、证据及摘要链路；最新有效效果等级为 partially_effective | 保持独立能力且不作为 Business fallback；离线补齐官方正文/附件，在线仍只消费受控只读索引 | 阶段 A 语料缺口已按有限 P0/P1/P2 边界完成处理并发布；旧阶段B目标取消；在线最小方案及资料表示后续工作由P3_01治理 |
| Employee 条件搜索 | `POST /employees/es/search` 支持 keyword、filter、分页、排序；Controller 读取守卫、endpoint-scoped 共享 converter、Agent Adapter 和真实 UAT 已通过 | `employee.search` 返回受控列表，业务服务执行读取角色授权 | 已有真实列表证据，原验证范围见UAT_00 |
| Employee 语义搜索 | `POST /employees/es/vector-search` 支持 `queryText` 等语义检索参数，不支持结构化 filter；Agent Adapter、共享 converter、v4 完整意图与真实 UAT 已通过 | `employee.semantic_search` 返回受控列表；semantic+地址必须 unsupported/零调用 | 已有真实语义列表及不支持组合零调用证据，见UAT_00 |
| Transaction 搜索 | `POST /txn/search` 已支持标识、类型、日期、金额、分页和排序，服务已执行读取授权；新版 Adapter、operator-specific 文本策略和真实 UAT 已通过 | `transaction.search` 完整映射既有列表搜索能力 | 相对日期/聚合仍不开放；原列表验收见UAT_00 |

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

## 5. Knowledge 正文与附件完整性

`REQ-KCORPUS-001`：阶段 A 只能从政府官方网站或经设计明确认可的同等权威来源获取公开正文和附件。每个原始资产必须保留最终来源 URL、HTTP/MIME/扩展名核验、字节数、SHA-256、抓取时间和来源文档关系；相同来源与相同内容必须幂等，内容变化生成新版本而不覆盖旧资产。现行索引库存、官方来源可达性与正文完整性必须分别陈述；403、404、超时或旧 URL 缺失只表示来源核验状态，不得推断正文缺失或自动降级到非权威副本。

`REQ-KCORPUS-002`：离线流水线必须受控处理 HTML、PDF、DOC/DOCX、XLS/XLSX 和必要扫描件，保留标题、章节、条款、表格、脚注以及父文档—附件—片段关系。OCR 文本必须标记解析方式和置信状态；来源不明、损坏、空白、截断、MIME 冲突或质量不合格的资产进入隔离区，不得进入候选索引。

`REQ-KCORPUS-003`：语料处理必须生成版本化 manifest、稳定 asset/chunk 身份、解析器/切片器/embedding 快照、时效元数据和有限质量报告。附件片段继承已核验父文档的读取与出域策略，但保留独立 asset/chunk 溯源；不得通过继承扩大父文档已有权限。

`REQ-KCORPUS-004`：现行索引只读且不得原地覆盖。离线工具只能创建精确命名的新候选索引；`es-query-service` 继续独占 Profile 到 alias、物理索引、字段和 DSL 的映射，并执行发布前校验、原子 alias 切换和回滚。Agent、模型及用户请求均不得指定候选索引或触发发布。

`REQ-KCORPUS-005`：阶段 A 完成边界为：P0 必须全部处理；P1 当前有效政策中已发现的正文/附件缺口必须处理；P2 全量盘点，仅处理当前时效或既有 UAT 依赖，其余形成后续清单。阶段 A 通过以直接类型化 keyword/vector 检索证明语料存在、可读、可引用为准，不要求同时修复域选择、Query Rewrite、RRF/rerank 或公共失败语义。

`REQ-KCORPUS-006`：发布前必须验证 P0/P1 范围、空正文、孤立附件、父子关系、embedding 维度、读取授权、模型出域目录、Evidence 连续子串及回滚。发布失败必须原子恢复原 alias 目标；旧索引不得在阶段 A 删除。新语料策略目录必须版本化，历史目录和历史 candidate/evidence 保持字节不变。

### 5.1 阶段 B 在线检索质量

`REQ-KQUALITY-001`：依据安全原问题，在读取开始前一次性决定允许目录内的单域或多域计划；原问题是查询和回答边界。改写不是必选环节；如以后启用，必须证明其保留主体、服务、纳税人、计税方法、日期、数字与否定限制，不补造条件。失败不得触发扩域、第二动作或 Business/Knowledge fallback。

`REQ-KQUALITY-002`：在既有类型化服务合同内正确执行候选上限，分别验证召回、融合、重排与 Evidence 损失。允许有界且确定的召回锚点保留；禁止 gold、case ID、指定文档或酒店专用加分参与在线排序。原文仍是唯一答案依据。

`REQ-KQUALITY-003`：区分完整无命中、证据不足、缺少必要条件、读取/出域拒绝与技术失败；复用既有公开状态和字段，不新增公共 DTO。部分覆盖不得宣称全面检索完成，条件不全不得生成单一适用结论。

`REQ-KQUALITY-004`：阶段 B 独立验证，不依赖图谱或新语料发布；阶段 A 索引/alias/正文及历史证据只读。核心原文充分场景必须满足预先确定的验收条件，功能、安全、效果分开报告；有限真实预算失败后不得自动补跑。

上述目标已完成设计评审，不代表代码或专项 UAT 已完成；新实施与验收状态归P3_01/UAT_02；原证据范围保留。

### 5.2 Knowledge 设计重建的需求边界（拟实施）

本节沿用已批准的Knowledge需求，不改变Business、安全和语料发布合同。此前阶段B优化目标已取消；新设计及后续实施状态以P3_01为准，不继承旧授权和效果结论。

| 需求 | 用户目标与成功判据 | 必要条件及拒绝边界 |
|---|---|---|
| `REQ-KQ-201` 资料查找 | 找政策、文号、条款、附件；返回相关原文摘录及可信来源，不承诺穷尽 | 只需明确查找主题；未给纳税人/计税方法不自动要求澄清。可以返回明确非穷尽的相关资料，不冒充适用结论 |
| `REQ-KQ-202` 原文解释 | 针对指定资料/问题，以足够的连续原文和逐点引用回应显式子问题 | 可用有界的自述语句解释直接原文，不允许无引用自由改写或增加原文外事实；资料冲突、缺少必要上下文或引用预算无法表达时返回证据不足 |
| `REQ-KQ-203` 适用性查询 | 仅按用户明确给出的主体、期间及相关条件，结合直接支持的条件与规则原文，给出有引用的有限条件判断 | 只要求实际影响该问题的缺失条件，不机械要求固定三项证明；不补造事实、不把成文/发布时间等同生效时间、不自行认定未证实的分类或现行效力。缺条件需澄清，缺原文需证据不足；不提供超出原文的自动税务推理或个性化保证 |
| `REQ-KQ-204` 最小可靠实现 | 复用一个Knowledge Capability及既有typed读取、授权、出域、原文引用；理解与确定性控制分离 | 不以模型自报coverage/证明角色、相似度阈值或域命中证明语义充分；安全约束与效果策略分别治理 |
| `REQ-KQ-205` 可归因验收 | 功能、安全、召回、回答质量分别验证；新方案允许先形成可比较基线 | 不强迫单一住宿题成功，不改历史gold/阈值或连续付费追逐通过；当前设计完成不等于新代码、部署或效果完成 |

首期采用原问题检索基线，改写增益及不同向量表示属于后续单变量实验，是否开放以新证据决策。来源为本次用户三类查询需求及取消旧目标后的设计重建授权；实现合同见Knowledge三份L2，验收方法见UAT_02 §5。

## 6. Employee 列表与语义查询

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

## 7. Transaction 列表查询

| 逻辑字段 | 允许 operator | Adapter 到现有 DTO 的固定映射 |
|---|---|---|
| `trans_id` | `eq` | `condition.transId` |
| `trans_type` | `eq/contains` | `condition.transType/transTypeContains` |
| `trans_date` | `eq/gt/lt` | `condition.transDate/transDateGt/transDateLt` |
| `amount` | `eq/gt/lt` | `condition.amount/amountGt/amountLt` |

`REQ-BQS-007`：field 和 operator 分离，支持同字段 `gt + lt` 范围；不得把 `amount_gt`、`trans_date_lt` 等 DTO 映射名公开给模型。日期使用带明确时区的规范时间格式；`gt/lt` 均为严格开区间。业务时区固定 `Asia/Shanghai`；“今天”“最近一周”等相对自然日只有在请求级时钟、数据库时间精度和边界规则得到合同证据后开放，否则 `unsupported`。

`REQ-BQS-008`：金额对齐 `DECIMAL(50,2)`；QueryPlan 使用 canonical decimal string，Java wire 使用 JSON number，业务服务使用 BigDecimal；保持现有更严格金额绝对值上界，scale≤2，禁止 float、舍入、截断和隐式 scale 转换。

`REQ-BQS-009`：page≥1，不再固定为 1；size 不得超过业务服务上限 100，也不得突破 Agent 现有更严格代码上限 50；验证 `(page-1)×size` 不溢出。排序只允许四个已核实字段、`ASC/DESC`、最多两项。结果包含 `rows/total/totalExact/page/size`；`totalExact=false` 表示下界估计，不得宣称精确总数。

## 8. 权限、敏感输入与模型出域

`REQ-BQS-010`：Employee 两个 ES endpoint 必须由业务域 `requireEmployeeRead` 执行最终读取授权，并经其端点级安全链显式使用既有共享 JWT role converter；先核实已有调用方兼容性，验证真实 ADMIN/VIEWER role claim 允许和无权限、missing、malformed、service-token 拒绝，不改变 detail 或其他 endpoint 的既有行为。Transaction 继续由服务执行最终读取授权。Agent 和 Adapter 只透传当前用户 JWT，不替代业务角色判定。

`REQ-BQS-011`：模型只能看到最小化问题、模型安全动作/字段/operator 目录、请求级 slot、配置 snapshot 及已批准的时间上下文；目录必须描述 operator 语义、单/多值形状、数量上限和允许的 tagged value。不得看到身份证号、员工编号、电话、邮箱、姓名、详细地址、JWT、凭证、业务原始响应、ES `_source`/`embeddingText`、索引或数据库物理信息。输入安全层只提取并替换敏感值，保留词序和 AND/OR 连接词，不得选择 domain/action/operator 或生成 filter。对不含“员工”但具有受保护姓名/姓氏强提示的输入，本地只允许进入受控规划，最终 domain/action 仍由 LLM 决定；无法可靠准入时返回 unsupported。

Employee 原始 ES JSON 必须在 Adapter 内进行 content-type、长度和结构校验，严格解析 hits，并丢弃 `embedding`、`embeddingText`、workBase 和未知字段；不得仅因原始响应而新增业务 endpoint 或公共 DTO。

## 9. 失败关闭和可观测性

`REQ-BQS-012`：模型失败、非法计划、不支持字段/operator、slot 非法、配置不一致、日期或金额无效、分页排序超界、物理表达式、workBase 字段及不可表达的语义+结构组合必须失败关闭，且下游业务调用为 0；业务服务返回拒绝时仅允许本次既定调用，不重试、不跨域、不回退。

仅记录 correlation ID、action、配置快照、有限阶段/错误、调用计数和耗时；不记录问题正文、slot 值、密钥、JWT、原始 QueryPlan、原始模型响应或原始业务响应。对个人学习项目保持普通日志和最小测试证明，不建设复杂审计平台。

## 10. 验收顺序与开放事项

1. 公共接入冒烟：认证、严格 JSON、默认 stub、单动作与 unsupported。
2. Employee：上海地址、职位、受保护标识/姓名、ES 列表、语义检索、权限矩阵、workBase 拒绝和 ES 字段丢弃。
3. Transaction：类型、日期、金额、同字段区间、组合过滤、分页、排序、精度及拒绝矩阵。
4. 结构化查询收口：Access/Core/Model/配置/Adapter/JWT/单动作与失败零调用回归。
5. Employee 自然语言扩展：单/复姓、多姓名、多姓氏、同字段 AND、行政区别名、多地区及问句/祈使句；真实模型和 Employee search 均受独立总预算约束。
6. Knowledge 阶段 A：全量只读盘点，P0 与目标 P1 正文/附件处理，新候选索引、直接类型化检索、授权/Evidence 和 alias 回滚验收；召回质量与图谱留给后续阶段。

Business原实施状态在历史P3_00保留，维护验收由UAT_00记录；新Knowledge实施/验收分别由P3_01/UAT_02记录；本需求只要求 Employee/Transaction 读取守卫、严格 QueryPlan、固定 Adapter、业务最终授权、失败关闭及受控结果成立，不保存运行批次、调用计数或证据哈希。
