# [L2_01_00] 单体 Agent Knowledge 查询流程与配置详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_00` |
| 当前版本 | v3.1 |
| 日期 | 2026-09-14 |
| 权威范围 | `knowledge.query` 单动作、逻辑域目录、问题改写、多阶段协同、失败优先级、请求状态和流程配置 |
| 上位文档 | [`L1_01` v3.1](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 本次变更 | v3.1计划入口与历史依据迁移；不改变代码、任务、配置、索引或业务合同 |
| 实施状态 | 生产入口、disabled惰性、域目录v2、Rewrite V11/Summary V7/quality-v3、阶段B有界检索与阶段A只读快照消费已实现；DR-KFLOW-023～031已有定向non-live证据，真实专项未通过。原验证/效果记录见历史P3_00/UAT_01；新实施/验收由P3_01/UAT_02管理 |
| 归档来源 | [整理前 v1.34 原文](历史文档/2026-09-14-unified-v3-baseline/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |

本文件纳入新的统一文档版本序列；v3.0不是软件、API、模型任务、配置或索引版本。原版本及字节归档见上表。评审状态、实施状态、部署状态和UAT状态分别判断；历史通过不自动覆盖新合同。

修订历史：2026-09-14，整理纳入统一文档基线v3.0；原版本、源提交及完整字节归档见上表。本次版本序列重置不是代码或设计回滚，评审、实施、部署和UAT状态分别管理。

本轮v3.0经三轮内审及两轮同一执行者的分层/跨层正式复核通过；仅证明文档整合，不表示新实现、部署或UAT已完成。完整发现与验证见本次归档MIGRATION.md。

本次v3.1仅修订计划引用、权威归属和维护状态，不改变业务合同；本轮限定迁移复核已通过（同一执行者分阶段），原v3.0评审范围不扩大为新实现/验收。新入口及历史追溯见[计划迁移说明](../plans/历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

勘误（2026-09-15）：仅修正§8旧改写对照和§19目标意图合同的章节指向；沿用v3.1，不改变设计、实施或验收状态。

## 2. 阅读导航

重点阅读§7动作/域、§8目标意图合同、§9/10流程与错误、§11装配、§19资料边界。历次修订及旧评审只见归档；本v3.0整合已有有效合同，不新增能力。Knowledge新合同明确标记待实施，旧实现定义仅用于兼容与迁移，不作为第二套目标权威。

## 3. 目标与范围

### 3.1 目标

用一个 `knowledge.query` 动作完成问题改写、逻辑域选择、多路检索、融合重排、证据摘要；各阶段只通过强类型 Protocol 协作，任何失败或安全拒绝都按固定优先级终止，不生成无证据答案。

### 3.2 范围内

- 动作 descriptor、空参数 validator 和 capability handler；
- `tax.policy`、`tax.law` 逻辑域目录与确定性选择；
- 原问题保护、当前版本语义规划、候选校验与无自动回退；历史V1/V2的显式装配不作为生产后备；
- 检索计划、阶段 deadline、coverage 充分性和结果映射；
- 流程级配置、启动校验、日志和组合根任务版本绑定。

### 3.3 范围外与不负责

- ES/BGE HTTP、RRF/rerank 算法和物理 Profile；
- 证据策略、摘要 decoder、P5 数据集与指标；
- DeepSeek transport、公共 Core/HTTP、Employee/Transaction；
- 文档获取、解析/OCR、切片和候选索引写入（由 `L2_01_01` 的离线构建合同治理）、独立 Knowledge Service。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-KFLOW-001` | 一个 `knowledge.query` 内完整执行五阶段，不注册内部阶段为动作 |
| `REQ-KFLOW-002` | 改写保持主体/时间/条件/否定/法律含义，非法候选不得用于检索 |
| `REQ-KFLOW-003` | 逻辑域和检索计划由代码目录及只收紧配置决定 |
| `REQ-KFLOW-004` | 阶段失败、授权拒绝、零域、无候选和摘要失败保持可区分 |
| `REQ-KFLOW-005` | 默认入口 disabled 零依赖；enabled 只在同一 Runtime 注册一个动作和两个固定任务 |
| `REQ-KFLOW-006` | Knowledge 与 Business 共享单动作 Core 但互不 fallback，关闭时释放所有 owned resources |
| `REQ-KFLOW-007` | 在线流程只消费已通过发布门禁的只读 Profile/index/policy snapshot；候选构建和 alias 切换不得由请求触发 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-KFLOW-001` | `L0_00 §3/§5/§8；SA-AD-005` |
| `CON-KFLOW-002` | `L1_01`：Capability 拥有查询策略，Adapter/Provider 拥有检索协议和物理映射 |
| `CON-KFLOW-003` | `L2_00_01`：动作参数不由模型生成，Core 只执行注册 handler |
| `CON-KFLOW-004` | `L2_00_02`：rewrite/summary 是代码绑定任务，默认模型可为 stub |
| `CON-KFLOW-005` | `REQ-KCORPUS-001～006`、`L1_01 KQ-AD-011/012`：离线构建与在线查询隔离 |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-KFLOW-001`、`CON-KFLOW-001`、`CON-KFLOW-003` | `DR-KFLOW-001`、`DR-KFLOW-002` | `IMPL-KFLOW-001`、`IMPL-KFLOW-002` | `TEST-KFLOW-001`、`TEST-KFLOW-002` | `VAL-KFLOW-001` |
| `REQ-KFLOW-002`、`CON-KFLOW-004` | `DR-KFLOW-003`、`DR-KFLOW-004`、`DR-KFLOW-005` | `IMPL-KFLOW-003`、`IMPL-KFLOW-004` | `TEST-KFLOW-003`、`TEST-KFLOW-004` | `VAL-KFLOW-002` |
| `REQ-KFLOW-003`、`CON-KFLOW-002` | `DR-KFLOW-006`、`DR-KFLOW-007` | `IMPL-KFLOW-005`、`IMPL-KFLOW-006` | `TEST-KFLOW-005`、`TEST-KFLOW-006` | `VAL-KFLOW-003` |
| `REQ-KFLOW-004` | `DR-KFLOW-008`、`DR-KFLOW-009`、`DR-KFLOW-010` | `IMPL-KFLOW-007`、`IMPL-KFLOW-008` | `TEST-KFLOW-007`、`TEST-KFLOW-008` | `VAL-KFLOW-004` |
| `REQ-KFLOW-005`、`REQ-KFLOW-006` | `DR-KFLOW-011`、`DR-KFLOW-012`、`DR-KFLOW-013`、`DR-KFLOW-014` | `IMPL-KFLOW-009`、`IMPL-KFLOW-010` | `TEST-KFLOW-009`、`TEST-KFLOW-010` | `VAL-KFLOW-005` |
| `REQ-KFLOW-007`、`CON-KFLOW-005` | `DR-KFLOW-015` | `IMPL-KFLOW-011` | `TEST-KFLOW-011` | `VAL-KFLOW-006` |
| `REQ-KFLOW-002`、`REQ-KFLOW-004`、`CON-KFLOW-004` | `DR-KFLOW-019` | `IMPL-KFLOW-004`、`IMPL-KFLOW-010` | `TEST-KFLOW-003`、`TEST-KFLOW-004`、`TEST-KFLOW-009` | `VAL-KFLOW-002`、`VAL-KFLOW-005` |
| `REQ-KFLOW-002`、`REQ-KFLOW-003`、`CON-KFLOW-004` | `DR-KFLOW-020` | `IMPL-KFLOW-004`、`IMPL-KFLOW-010` | `TEST-KFLOW-012` | `VAL-KFLOW-002`、`VAL-KFLOW-005` |
| `REQ-KFLOW-002`、`REQ-KFLOW-003`、`CON-KFLOW-004` | `DR-KFLOW-021` | `IMPL-KFLOW-004`、`IMPL-KFLOW-010` | `TEST-KFLOW-013` | `VAL-KFLOW-002`、`VAL-KFLOW-005` |
| `REQ-KFLOW-003`、`CON-KFLOW-004`；`KQ-AD-014` | `DR-KFLOW-022` | `IMPL-KFLOW-004`、`IMPL-KFLOW-010`：semantic_planner、planning、capability、bootstrap的内部版本透传 | `TEST-KFLOW-014`：V2成对绑定、未知版本零检索、历史V1、disabled与单动作 | `VAL-KFLOW-005`：当前根/历史根及严格类型回归 |
| `REQ-KFLOW-002`、`CON-KFLOW-004`；`KQ-AD-013` | `DR-KFLOW-023` | `IMPL-KFLOW-003`、`IMPL-KFLOW-004`、`IMPL-KFLOW-010` | `TEST-KFLOW-015` | `VAL-KFLOW-002`、`VAL-KFLOW-005` |
| `REQ-KFLOW-002`、`REQ-KFLOW-003`、`REQ-KFLOW-005`；`KQ-AD-018` | `DR-KFLOW-024` | `IMPL-KFLOW-012` | `TEST-KFLOW-016` | `VAL-KFLOW-007` |
| `REQ-KFLOW-002`、`REQ-KFLOW-004`；`KQ-AD-015` | `DR-KFLOW-025` | `IMPL-KFLOW-013` | `TEST-KFLOW-017` | `VAL-KFLOW-008` |
| `REQ-KFLOW-002`；`KQ-AD-013` | `DR-KFLOW-027` | `IMPL-KFLOW-015` | `TEST-KFLOW-019` | `VAL-KFLOW-010` |
| `REQ-KFLOW-002`；`KQ-AD-013/018` | `DR-KFLOW-028` | `IMPL-KFLOW-016` | `TEST-KFLOW-020` | `VAL-KFLOW-011` |
| `REQ-KFLOW-004`；`KQ-AD-018` | `DR-KFLOW-026` | `IMPL-KFLOW-014` | `TEST-KFLOW-018` | `VAL-KFLOW-009` |
| `REQ-KFLOW-002`、`REQ-KFLOW-003`、`REQ-KFLOW-004`；`KQ-AD-013/018` | `DR-KFLOW-031` | `IMPL-KFLOW-019` | `TEST-KFLOW-023` | `VAL-KFLOW-014` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Knowledge Provider | descriptor、空参数注册 | 流程阶段实现 |
| Capability | 阶段顺序、deadline、失败优先级、公共结果 | ES/BGE/模型协议 |
| Semantic Guard/Planner | 原问题保护、V3模型计划解码、受限语义域/查询表达 | 检索执行、角色授权或物理资源 |
| Domain Catalog/Selector | 逻辑域定义与确定性选择 | 物理索引和读取授权 |
| Plan Builder | 逻辑域×允许检索路径的有界计划 | 执行 HTTP 或排序 |
| Retrieval Stage | 消费计划并返回 typed batch+coverage | 改写和摘要 |
| Evidence Stage | 消费授权候选并形成最终本地/出域结果 | 首次读取授权 |
| Composition Root | 唯一绑定当前已实施的Rewrite/Summary、目录、Stages和设置；源码基线11/7/v3；目标§8为12/8/minimal-v1 | 请求级策略判断 |

依赖方向为 `Capability → stage Protocol ← retrieval/evidence implementations`；目录和 settings 不依赖 HTTP/DeepSeek。禁止 Knowledge 内部阶段注册为公共能力，禁止 Capability 依赖 ES DSL 或模型 SDK。

该分层保持动作内高内聚、基础设施低耦合；不新增 knowledge-service。

## 6. 当前实现基线与迁移

最小变更原则：本轮仅整合已批准合同与迁移边界，不新增实现、依赖或质量策略。当前实现与待实施目标分别标识；不能将旧验证移作新合同通过。

源码当前绑定Rewrite11/Summary7/quality-v3，旧策略仍在代码而非本次回滚对象。§8的意图12/Summary8/minimal-v1和§19资料接缝均为已批准待实施设计。后续按P3_01在线合同、检索/回答、组合工作包迁移；不得将模型任务或配置版本改为文档v3.0。旧实现与原测试由归档和冻结提交解释；本次只改文档。

## 7. 动作、逻辑域与请求状态

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KFLOW-001` | 只注册 `knowledge.query`，argument schema 为 exact 空 object |
| `DR-KFLOW-002` | 五阶段都在一次 handler 内，Core 看不到内部工具或第二动作 |
| `DR-KFLOW-003` | 原问题先经安全与约束保护；目标固定原问题，不生成改写，主体、时间、条件、否定和法条不得被补造或丢失 |
| `DR-KFLOW-004` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-005` | 模型/解码/约束失败停止且检索0；敏感输入模型0。旧original fallback仅历史兼容，不得触发生产回退 |
| `DR-KFLOW-006` | 逻辑域目录代码绑定且有序；配置只能选择已知域 |
| `DR-KFLOW-007` | 计划只含逻辑域、stable path、query、limit及代码绑定版本；目标不携带旧证据需求，不含物理索引/字段/DSL |
| `DR-KFLOW-008` | 每阶段使用总 deadline 派生的较小 phase deadline；仅在预算校验通过后创建阶段 operation，超时不进入下一阶段 |
| `DR-KFLOW-009` | 授权拒绝/读取权威失败优先于局部技术成功；coverage 必须与计划精确对应 |
| `DR-KFLOW-010` | `question_egress_denied=true` 时策略拒绝优先于 zero-domain/no-result；普通零域仍为 no_result |
| `DR-KFLOW-011` | 默认启动入口必须先解析 `AGENT_KNOWLEDGE_ENABLED`；false 时不得加载下游配置、任务、策略或创建 client |
| `DR-KFLOW-012` | 同一根唯一注册已批准并实施的任务/Provider；当前源码11/7，目标12/8按§8成对迁移，不自动后备 |
| `DR-KFLOW-019` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-020` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-021` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-022` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-023` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-024` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-025` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-026` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-027` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-028` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-031` | 旧实现策略编号保留，仅用于归档/兼容；目标规划与原问合同由DR-KFLOW-201～205及§8替代，不复用旧证明声明或候选格式 |
| `DR-KFLOW-013` | Knowledge 与 Business 共享 Core 单动作约束但互不 fallback；Knowledge 不进入 Business QueryPlan decoder/binder |
| `DR-KFLOW-014` | `enabled=true` 时生产 stub provider 是非法组合并启动失败；测试 fake 必须经显式注入接缝使用同一生产装配函数 |
| `DR-KFLOW-015` | 只有发布门禁通过并同步 Profile、物理 index UUID/mapping、逻辑 snapshot 及模型出域目录后，在线组合根才允许消费新 alias 目标；任何不一致失败关闭且不自动切换 |

### 7.2 动作契约

`knowledge_query_descriptor()` 返回 ID=`knowledge.query`、kind=`query`、`api_version=1`、模型安全描述和 exact empty schema。`KnowledgeArgumentValidator.validate(arguments)` 只接受空 object，任何额外参数失败；问题来自 execution context。

### 7.3 逻辑域目录

| domain ID | 选择锚点 | 允许路径 | 默认出域策略引用 |
|---|---|---|---|
| `tax.policy` | 税务锚点 + 政策/公告/通知/优惠/征管等 | keyword, vector | `knowledge.egress.tax_policy.v1` |
| `tax.law` | 税务锚点 + 法律/法规/条例/法条等 | keyword, vector | `knowledge.egress.tax_law.v1` |

目录ID、固定顺序及出域策略不变；表中锚点只说明域的安全描述，不作为本地词面准入规则。目标模型按§8一次选择已启用域，本地只验证成员、数量和顺序。旧tax-domain-catalog-v2词面Selector细则归档，不控制新计划。Selector不判断文件是否存在；无候选沿既有no_result语义，不新增虚构文件识别。

### 7.4 请求级状态

当前旧实现使用ProtectedConstraintSet/RewriteStageResult/DomainSelection等类型；目标按§8以不可变KnowledgeQueryIntent和新计划承接原问题，再产生RetrievalStageResult/EvidenceStageResult。旧生产者不伪装成新类型。内部传递类型为 frozen、slots；字符串、集合、coverage 与 stage-result 组合等边界分别由可信生产者、严格 decoder 和 Capability 消费点校验，不要求每个内部 dataclass 重复同一组校验；不写跨请求存储。

## 8. 最小查询流程合同（新设计，未实施）

本节承接REQ-KQ-201～205与KQ-AD-020～024，作为后续首期实施权威；整理前改写章节（见§1归档来源）中的Rewrite3～11、需求/scope增量及DR-KFLOW-016～031保留为当前源码/历史合同对照，不要求新链路继续调用。既有Guard、typed端口、授权、超时/取消、无fallback约束不被替代。旧任务文件不改写；新实现不通过伪造requirements绕过旧校验器。

### 8.1 职责、数据及模型合同

`DR-KFLOW-201`：既有Core selector只选择knowledge.query；进入同一handler后，Guard检查原问题。安全最小化、NFC后的完整问题记为Q，在本请求内冻结。Q长1～1024字符；公共接入仍接受原公开长度，超过Knowledge接口能力的请求在handler中返回既有INVALID_ARGUMENT/knowledge.invalid_question（规划与检索0），不截断、不调用模型压缩。此收紧是明确的首期能力限制，不修改Spring DTO，也不将长问题冒充unsupported语义。

拟新增内部`KnowledgeQueryIntentTaskV12`（文件建议`agent-runtime/src/agent_runtime/knowledge/intent_task_v12.py`）：继续使用注册键knowledge_rewrite、version=12以复用现有任务目录，不表示执行查询文本改写。新任务独立构造Prompt/decoder，不链式字符串替换旧Prompt。输入为Q及启用域的只读安全目录（ID/安全描述）；无业务凭据、物理Profile/index、正文、证明需求或历史回答。

输出只允许四字段：
`{"outcome":"search","query_mode":"lookup","domains":{"tax.policy":"selected","tax.law":"not_selected"},"missing_conditions":[]}`。

- outcome：search / clarification_required / unsupported。
- query_mode：lookup / explanation / applicability / none。
- domains：键集合精确等于该任务启动时的enabled域目录（1～2个）；值仅selected/not_selected。JSON对象键顺序不具有语义、不作为拒绝条件；解码后由代码按目录顺序形成不可变域元组。单域部署不要求另一个域的键。禁止重复键、额外域、null及其他值。
- missing_conditions：0～4个唯一枚举，允许subject / period / taxpayer_type / calculation_method；不得返回自由文本或敏感输入。
- search：模式非none，选1～2域，missing_conditions空。
- clarification_required：模式非none、全部域not_selected、missing_conditions非空；仅对确实影响含义的条件提出澄清，普通资料查找不要求纳税人/计税法。
- unsupported：模式none、全部域not_selected、missing_conditions空。
- 不承诺模型能在本地证明语义分类正确；不会因检测不到关键词而本地改选域。模型不确定需求或不可表达时unsupported，不猜用户事实。

复用Model既有SCHEMA_ONLY单输出承载协议：固定输出名knowledge_query_intent；每层object禁止额外字段，全部required；Provider不支持的集合上限仍本地检查。只有一次指定输出、无混合正文；异常不修复、不切JSON模式、不重试。任务系统指令≤8192bytes、输入≤16384bytes、输出≤512tokens、阶段8秒；这些是上限而非必须消耗。模型版本仍为当前共享配置的固定值，本设计不切换后端。

`DR-KFLOW-202`：拟新增frozen/slots内部`KnowledgeQueryIntent`，字段为query_mode、selected_domain_ids、missing_conditions和outcome；Q与request-local context由代码持有，不让模型回显/覆盖。意图阶段结果为成功意图或现有有限失败；新内部类型不继承/伪装`KnowledgeRequirementPlanOutput`。在既有Capability流程增加一次版本分派，之后仍执行同一检索/Evidence阶段；不复制一个新Runtime。内部Stage数据注解可演进，三个调用入口rewrite/execute/build_result的keyword参数和公开HTTP不变；旧serializer及冻结构造器继续按旧版本读取，不对旧对象asdict追加新字段。

### 8.2 确定性计划与原问责任

`DR-KFLOW-203`：search后按目录顺序生成每域keyword/vector两项，query_text均精确为Q（vector HTTP只发送其本地embedding）。计划固定`knowledge-minimal-v1`版本、query_mode、域目录快照、Q及固定Profile映射；无requirements、focus、classification/proof role或评分指令。原问、计划、rerank和Summary的Q必须相同；拒绝错版本/不同Q/重复路径/非法域，不能把模型改写拼回去。

检索接口上限与时限保持L2_01_01：每路20、域≤2、路径≤4；同一Q只embedding一次并在本请求内复用向量，不跨请求缓存。只选原问需要的域，不因结果为空/失败再选域。任一model失败时retrieval/embedding/rerank/summary均0；原问检索是正常固定路径，不是模型失败fallback。

原问保留不等于检索完美：多主题噪声和长句相关性可能降低。后续若测试证明需要改写，另行预注册“同语料/同模型/同预算，仅改变query表示”的实验；未批准前不增加隐藏rewrite分支或模型调用。用户条件最终仍由原问约束Summary，不能以高召回分数作适用结论。

### 8.3 公开结果与有限失败映射

`DR-KFLOW-204`：复用当前CapabilityStatus、错误码和开放domain_result，以下reason均使用现有值；不新增HTTP/Java字段、动态澄清文本或新公开枚举。调用计数中的M包含selector，K为Knowledge意图，S为Summary，R为typed search；权限失败前可能已产生selector/意图，但不允许读取未授权正文。

| 场景 | 现有公开映射 / reason | 用户语义 | 上限与零调用 |
|---|---|---|---|
| 接入认证/JSON非法 | 既有401/403/400 | 拒绝请求 | Runtime/模型/检索0 |
| 敏感原问 | model_egress_denied/既有输入拒绝 | 输入不能处理 | 模型0、R0 |
| Q超过Knowledge长度 | invalid_argument / knowledge.invalid_question | 输入不满足能力边界 | selector≤1，K/S/R0 |
| 无支持域 | no_result / no_matching_domain | 无匹配知识能力 | M≤2，R/S0 |
| 必要条件缺失 | no_result / clarification_required | 使用既有固定补充条件提示，不假设条件 | M≤2，R/S0 |
| 意图模型非法/失败 | downstream_failure / knowledge.rewrite_failure | 规划失败，不是无结果 | M≤2，R/S0 |
| 意图模型超时 | timeout / knowledge.rewrite_timeout | 规划超时 | M≤2，R/S0 |
| 所有路径成功但零候选 | no_result / no_candidate | 当前检索未命中，不宣称全库无资料 | M≤2，R≤4，S0 |
| 有候选但证据/表达预算不足 | no_result / insufficient_evidence | 无充分原文依据 | M≤3，R≤4，S≤1 |
| 读取拒绝、授权权威故障、快照/完整性非法 | 既有授权或downstream_failure/evidence_failure | 不泄漏其他域正文；保持现有错误优先 | S0，不追加域/路径 |
| 部分技术失败 | 仅在原覆盖规则满足时继续；coverage.retrievalComplete=false | 部分检索，不能说全面 | R≤4、S≤1，无重试 |
| 所有路径技术失败/覆盖条件不满足 | downstream_failure / knowledge.retrieval_failure | 下游失败，不是无命中 | S0 |
| 选中证据出域拒绝 | model_egress_denied / 既有policy reason | 资料不能用于模型处理 | S0，不换证据绕拒绝 |
| Summary非法/超时 | downstream_failure或timeout / 既有summary错误码 | 回答生成失败 | S≤1，无Core answer |
| 合法抽取 | success / 既有extractive_evidence | 按模式返回原文摘录 | M≤3，R≤4，无第二动作 |

原有部分继续条件（每域至少一条成功路径及候选，总候选达到已冻结最小值）不放宽。单域全部无候选而另一域有结果时不能标成完整覆盖；按现有不足/失败语义结束，不由lookup模式绕开安全/覆盖规则。缺条件由模型判断只影响正常查询语义，不授权返回税务结论。

上述阶段上限不是串行累加保证：沿用compute_phase_deadline，实际截止为min(请求剩余deadline-0.1秒, 阶段上限)，每个子HTTP再收紧。请求预算不足不启动下一阶段，返回既有对应timeout码；不得为了凑8+20+15秒修改Spring/Core公开超时。TEST-KFLOW-202须涵盖selector已消耗预算、检索成功但Summary时间不足、取消后迟到结果丢弃。

### 8.4 配置、兼容与回滚

`DR-KFLOW-205`：后续目标仅将当前11/7/v3替换为12/8/knowledge-minimal-v1的**成对代码绑定**。不提供请求级版本选择，不同时注册两代，不让配置扩大域或预算。默认disabled继续零Knowledge任务/client/配置要求；enabled配置错误仍启动失败关闭，不吞错自动降级。共享selector、Business v7、Model固定后端及三客户端所有权不变。

预热的已知影响只登记为运维设计：原全量启动可能因Knowledge预热失败停止后续启动。首期保留显式enabled时失败关闭；disabled/PlanOnly不预热、不校验Knowledge依赖。不设计“失败后自动关Knowledge继续”的隐藏降级；需要只运行Business时由维护者显式disabled。后续验证serviceCenter路径，但本次不改脚本或新增服务。

回滚优先显式禁用Knowledge；如恢复源码绑定，恢复整套任务/内部类型/配置与相容测试，不单独把Summary8接到quality-v3。模型、索引、alias与部署实例分别核对，代码回滚不执行ES操作、不恢复旧授权。历史版本只对冻结运行负责；清理前扫描所有现行/冻结调用方，不以删除旧测试掩盖兼容问题。

### 8.5 实施与验证追踪（全部待实施）

#### 新设计编号定义

| 需求编号 | 规则编号 | 实现编号 | 测试编号 | 验证编号 | 定义位置与状态 |
|---|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KFLOW-201、DR-KFLOW-202、DR-KFLOW-203、DR-KFLOW-204、DR-KFLOW-205 | IMPL-KFLOW-201、IMPL-KFLOW-202、IMPL-KFLOW-203 | TEST-KFLOW-201、TEST-KFLOW-202、TEST-KFLOW-203 | VAL-KFLOW-201、VAL-KFLOW-202、VAL-KFLOW-203 | 需求定义见REQ_00 §5.2；本节前述条款和下表逐项展开；全部待实施验证 |

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KFLOW-201、DR-KFLOW-202 | IMPL-KFLOW-201：拟新增intent_task_v12.py/intent_contracts.py，替换当前semantic_planner.py中的生产意图适配；旧任务文件只读 | TEST-KFLOW-201：三模式、单/双域、重复/未知/null、terminal组合、缺条件、长度、敏感输入、模型失败/超时/取消及0下游 | VAL-KFLOW-201：定向unit/contract，strict mypy/compileall，非live仅fake |
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KFLOW-203、DR-KFLOW-204 | IMPL-KFLOW-202：planning.py、capability.py、contracts.py的请求内新版本数据通道；现有协议与错误映射复用 | TEST-KFLOW-202：Q逐阶段相等、仅4路径/1embedding、无失败扩域、部分/全失败、reason/HTTP映射、并发隔离 | VAL-KFLOW-202：current-root fake、Spring→Runtime、Knowledge/Core/Business回归 |
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KFLOW-205 | IMPL-KFLOW-203：bootstrap.py、main.py和直接测试；旧根仅冻结测试隔离，运行配置不自动改 | TEST-KFLOW-203：12/8唯一、错配拒绝、disabled0依赖、全局模型不变、三client关闭、历史hash/取消 | VAL-KFLOW-203：生产可达性/历史引用扫描、已有启动静态验证；真实部署另行授权 |

新文件名与类名为拟议落点，非已经存在。TEST/VAL是后续实施义务，不是本次已执行测试。原设计内审/正式复评及文档验证见历史P3_00 §21；当前交接见P3_01；本目标不准入代码、测试、配置或服务操作。

## 9. 检索计划与核心流程

### 9.1 计划

按§8.2，从安全原Q与一次冻结域集合生成每域keyword/vector两项，按目录→路径稳定排序、单路≤20。两路使用同一Q，查询向量只在本请求复用一次；不携带requirements/focus，不截断原Q，不根据结果扩域或改表达。

### 9.2 主流程

```text
validate empty arguments
  → input guard / intent12
  → validated immutable KnowledgeQueryIntent (legacy planner unreachable)
  → zero-domain priority decision
  → build retrieval plan
  → retrieval stage
  → validate exact coverage and partial-success sufficiency
  → evidence/egress/summary stage
  → map to CapabilityResult
```

### 9.3 coverage 充分性

- coverage 的 successful/no_result/failed path 三集合并集必须精确等于计划，且互斥、无重复；no_result 是成功完成但零命中的路径，不能当作技术失败。
- 每个 selected domain 必须有一个 candidate count。
- 整域授权拒绝或 auth authority failure 立即失败，不参与“部分成功”。
- 技术性局部失败仅在每个选中域至少一条成功路径、每域至少一候选且总数达到partial threshold时继续；否则返回timeout/downstream_failure，不是internal_failure或no_result。
- 无候选只在 coverage 完整且没有安全失败时映射 `no_result`。

## 10. 错误分类、失败优先级与调用方可见语义

从高到低：

1. 输入/参数非法；
2. 用户身份/读取授权拒绝或权威失败；
3. 问题出域策略拒绝（包括拒绝后的 zero-domain）；
4. deadline/cancel；
5. coverage/协议不一致；
6. 技术性检索失败且证据不足；
7. 安全允许的零域/无候选；
8. evidence/summary 失败；
9. success。

| 场景 | Capability 状态 | 典型 code/结果 |
|---|---|---|
| 非空 arguments/问题非法 | `invalid_argument` | `knowledge.arguments_not_empty` / `knowledge.invalid_question` |
| 问题策略拒绝 | `model_egress_denied` | `knowledge.rewrite_input_denied`，模型调用 0 |
| 安全普通零域 | `no_result` | `reason=no_matching_domain` |
| 整域读取拒绝 | `forbidden` | `knowledge.domain_forbidden` |
| rewrite/retrieval/summary timeout | `timeout` | 阶段专属 code |
| 协议/coverage/技术失败 | `downstream_failure` | 有限阶段 code |
| 完整无候选 | `no_result` | `reason=no_candidate` |
| 证据成功 | `success` | domain result + egress decision |

### 10.1 当前目标的有限错误

目标12/8链路按§8.3的严格矩阵映射既有公开状态；保留本节公共异常类别与安全优先级。旧阶段B查询改写、focus及证明需求相关原因只解释旧实现，不进入目标合同。

## 11. 配置、预算与启动校验

| 配置 | 默认/范围 |
|---|---|
| `AGENT_KNOWLEDGE_ENABLED` | false |
| `ENABLED_DOMAINS` | 只能是目录已知 ID，启用时至少一个 |
| retrieval query chars | 默认/最大 1024 |
| per-path candidates | 默认 20，5..20 |
| partial candidates | 默认 3，3..20 且≤per-path |
| intent/retrieval/evidence timeout | 8000/20000/15000ms，均有界 |

未知 `AGENT_KNOWLEDGE_*` key 启动失败。配置只能收紧目录/代码边界；启用 Knowledge 时任务、目录、两 Stage 和所有依赖必须齐全，组合根才可 ready。

### 11.1 生产组合根装配顺序

1. 加载 `KnowledgeSettings`；disabled 时立即返回“无附加任务、无附加 Provider、无 owned Knowledge resource”的结果。
2. enabled 时拒绝生产 stub provider；测试可显式注入 fake transport，但必须继续走同一装配函数和注册校验。
3. enabled 时加载 `KnowledgeRetrievalSettings` 和 policy catalog，验证已启用域、Profile version、ES/BGE origins、1024 维、rerank model、final candidates 与 task version。
4. 目标按§8创建意图12/Summary8/minimal-v1唯一配对；当前源码仍11/7，后续COMPOSE完成后才能改变事实状态。旧任务不同时注册，也不作自动后备。
5. 所有纯配置、目录、策略和任务校验完成后，才为三个固定 origin 分别创建 bounded HTTP client/transport并构建 Retrieval/Provider。
6. 把 `KnowledgeCapabilityProvider` 作为 `BusinessQueryRuntimeCompositionRoot.additional_providers` 追加到同一 Runtime。
7. 顶层 lifecycle 同时拥有 Business clients、Knowledge clients 和 model；关闭按资源逐项尝试，保留首个异常但仍释放其余资源。

不得把部分构建对象暴露为 ready Runtime。通过把所有可预见校验前置到 client 创建之前，避免为同步启动路径另建异步“半成品清理”协议；已成功装配的 Runtime 必须完整关闭 owned resources。

授权评分表示保持当前固定版本及L2_01_01 DR-KRET-034的原文/派生隔离；新最小策略不同时更换模型或向量。disabled零创建；版本必须进入新测量快照，不继承旧UAT。

## 12. 权限、安全、审计与一致性

- Capability 把同一 `OpaqueUserToken`、subject 和 deadline 转成 Retrieval/Evidence context，不解析角色。
- 原问题、rewrite、正文、向量、JWT、模型原响应不进入普通日志。
- 日志只记录 request/correlation、目录/config version、选中域数、阶段、状态、coverage 计数和耗时。
- 每请求无持久状态、数据库事务、重试或 resume；取消后下一阶段调用次数为 0。
- Retrieval/Evidence 执行发生于边界 Protocol 后，Capability 不依赖它们的 HTTP/模型实现。

## 13. 发布、数据生命周期与回滚

- 默认 Knowledge disabled；启用需完整配置和已就绪 Provider。
- 请求状态随请求释放；知识正文不由 Agent 持久化，无数据迁移。
- 回滚可禁用 `AGENT_KNOWLEDGE_ENABLED` 并重启；task version 回滚必须同步组合根和测试，不能覆盖历史 task 源码。
- 语料发布不属于请求状态机。阶段 A 的 alias 原子切换、原目标记录、冒烟和失败回滚由 `L2_01_01` 治理；本流程只接受已发布且启动校验通过的只读快照。

## 14. 实现落点清单

本节旧IMPL/TEST/VAL编号仅定位保留组件和原版本兼容责任；新实现主线以§8.5、资料以§19追踪。涉及旧证明策略的具体操作见归档，不能按此重建并行生产流程。

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-KFLOW-001` | `agent-runtime/src/agent_runtime/knowledge/provider.py`：descriptor 和 registrations |
| `IMPL-KFLOW-002` | `agent-runtime/src/agent_runtime/knowledge/capability.py`：`KnowledgeArgumentValidator`、`KnowledgeQueryCapability.handle` |
| `IMPL-KFLOW-003` | 已有`knowledge/question_semantics.py`旧Guard不改；DR-KFLOW-023已新增`knowledge/tax_question_semantics.py`类别词数字分离 |
| `IMPL-KFLOW-004` | 已有`knowledge/rewrite_v3.py`（精确合同）、`knowledge/semantic_planner.py`、V4/V5/V6任务；DR-KFLOW-023已增加Planner内部Guard注入及共享类别tuple，旧默认与任务不变 |
| `IMPL-KFLOW-005` | `agent-runtime/src/agent_runtime/knowledge/catalog.py`、`domain_selection.py` |
| `IMPL-KFLOW-006` | `agent-runtime/src/agent_runtime/knowledge/planning.py`：`KnowledgeRetrievalPlanBuilder.build` |
| `IMPL-KFLOW-007` | `agent-runtime/src/agent_runtime/knowledge/contracts.py`、`agent-runtime/src/agent_runtime/knowledge/context.py` |
| `IMPL-KFLOW-008` | `agent-runtime/src/agent_runtime/knowledge/settings.py`、`agent-runtime/src/agent_runtime/bootstrap.py` 的 Knowledge composition |
| `IMPL-KFLOW-009` | `agent-runtime/src/agent_runtime/main.py`：按开关构建 Knowledge tasks/retrieval/provider 并追加到 Business Runtime |
| `IMPL-KFLOW-010` | `agent-runtime/src/agent_runtime/bootstrap.py`：顶层 owned resource 生命周期与 disabled 零依赖装配 |
| `IMPL-KFLOW-011` | `agent-runtime` 当前策略目录加载与 `serviceCenter/knowledge-runtime-binding.v1.json`：只读发布绑定；历史目录继续独立可校验 |
| `IMPL-KFLOW-012` | 整理前改写章节（见归档）批准的需求类型、V7任务、Planner/Capability透传、当前根成对绑定及安全观测目标；原部分实施进度见历史P3_00；不改历史任务与公开合同 |
| `IMPL-KFLOW-013` | 整理前改写章节（见归档）已实施V8指令恢复、当前根单绑定和相同内部合同版本识别；不新增decoder、语义分类器或模型调用 |
| `IMPL-KFLOW-014` | 整理前改写章节（见归档）当前根绑定Summary7，Stage历史合同兼容6/7，Rewrite8不变 |
| `IMPL-KFLOW-015` | 整理前改写章节（见归档）已实现document_reference_semantics.py及bootstrap显式注入；原两个Guard不改 |
| `IMPL-KFLOW-016` | 整理前改写章节（见归档）已新增query_constraint_scope.py/rewrite_v9.py，实现semantic_planner的版本9分支及bootstrap唯一绑定；旧任务/Guard/公共合同不改 |
| `IMPL-KFLOW-019` | 整理前改写章节（见归档）已新增rewrite_v11.py及组合根不可变域快照、当前Planner接线；直接fake迁移、历史夹具隔离，不改公共DTO/旧任务/历史运行 |

### 14.2 关键签名

```python
class KnowledgeQuestionRewriteStage(Protocol):
    async def rewrite(
        self,
        *,
        original_question: str,
        timeout_s: float,
    ) -> RewriteStageResult: ...

class KnowledgeRetrievalStage(Protocol[TBatch]):
    async def execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> RetrievalStageResult[TBatch]: ...

class KnowledgeEvidenceStage(Protocol[TBatch]):
    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[TBatch],
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult: ...
```

## 15. 测试与验证设计

本节旧IMPL/TEST/VAL编号仅定位保留组件和原版本兼容责任；新实现主线以§8.5、资料以§19追踪。涉及旧证明策略的具体操作见归档，不能按此重建并行生产流程。

### 15.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-KFLOW-001` | descriptor/empty arguments/单注册：`agent-runtime/tests/contract/knowledge/test_provider_registration.py` |
| `TEST-KFLOW-002` | Capability 契约、阶段协同和上下文裁剪：`agent-runtime/tests/unit/knowledge/test_capability_contract.py`、`agent-runtime/tests/integration/knowledge/test_flow_with_fake_stages.py` |
| `TEST-KFLOW-003` | V3精确合同与V4复用合同：`agent-runtime/tests/contract/knowledge/test_rewrite_task_v3.py`、`test_rewrite_task_v4.py`、`test_provider_registration.py`；历史V1/V2测试单独保留 |
| `TEST-KFLOW-004` | 当前input denied/模型失败/澄清/unsupported零调用且无原问题回退；旧fallback仅验证显式历史装配 |
| `TEST-KFLOW-005` | 两域单选/多选/零域与稳定顺序：`test_domain_selection.py` |
| `TEST-KFLOW-006` | plan 域×路径、limit 和无物理资源字段：`test_planning.py` |
| `TEST-KFLOW-007` | coverage、部分成功、授权优先和阶段 timeout：`agent-runtime/tests/integration/knowledge/test_flow_with_fake_stages.py` 与 Retrieval/Evidence Stage tests |
| `TEST-KFLOW-008` | denied + zero-domain 与普通 zero-domain 反证：`agent-runtime/tests/evaluation/knowledge/test_live_p5_denied_zero_domain.py` |
| `TEST-KFLOW-009` | `build_runtime` disabled/enabled、enabled+production-stub 拒绝、显式 fake 注入、唯一注册、缺失配置和重复任务/能力 |
| `TEST-KFLOW-010` | Spring→当前 Runtime non-live：动作选择、两域、失败优先级、Business 隔离、取消及 client close |
| `TEST-KFLOW-011` | 新 alias 目标下 Profile/index/policy snapshot 一致性；错绑启动失败、请求零管理调用、旧历史目录哈希不变 |
| `TEST-KFLOW-012` | DR-KFLOW-020：V5仅改指令/版本、V3 exact合同等价、该历史版本唯一V5与旧版本拒绝、单域/双域fake及非酒店保留表达；真实语义另行UAT，不修改历史gold |
| `TEST-KFLOW-013` | DR-KFLOW-021：V6指令局部替换/同一decoder与预算、每域聚焦及显式条件不丢失、原问Summary、当前单绑定与旧版本拒绝、历史隔离；合同/生产fake/防回退，真实语义不由fake证明 |
| `TEST-KFLOW-014` | DR-KFLOW-022：quality-v2从当前根透传、错误版本拒绝、V2/limits配对、历史V1默认、disabled及单动作防回退 |
| `TEST-KFLOW-015` | DR-KFLOW-023：已新增`test_tax_question_semantics.py`及`test_tax_semantic_guard_production.py`；类别/年份变序成功、类别丢失新增、实际数字/比例/日期/文号/法条/否定变化拒绝、重复数量和上限、旧默认和历史哈希、当前根唯一绑定/零调用/资源关闭 |
| `TEST-KFLOW-016` | 整理前改写章节（见归档） V7精确合同、终态前校验、同域多角色、语义保护、需求透传、版本矩阵与三处观测不展示focus；已实现测试路径见该节及当前根test_requirement_runtime_composition.py |
| `TEST-KFLOW-017` | 整理前改写章节（见归档） V8指令恢复、五字段decoder identity/矩阵、当前根/旧版拒绝、澄清零下游及历史作用域恢复；VAL-KFLOW-008不替代真实UAT |
| `TEST-KFLOW-018` | 整理前改写章节（见归档）版本配对/拒绝旧版、disabled、当前Spring根和冻结历史fixture隔离 |
| `TEST-KFLOW-019` | 整理前改写章节（见归档）文号正反例、旧Guard、当前生产query/focus、整份拒绝零下游及生命周期；新增两测试文件 |
| `TEST-KFLOW-020` | 整理前改写章节（见归档）分域/全局计数和顺序、声明与query一致、语义限制反例、V9合同/current root和历史兼容 |
| `TEST-KFLOW-023` | 整理前改写章节（见归档）固定域槽位、原语义差分、快照/请求隔离、当前根零调用及历史保护；已实施并定向执行通过 |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-KFLOW-001` | Provider/Capability 契约和单动作调用计数测试通过 |
| `VAL-KFLOW-002` | 当前Rewrite精确合同、Guard、敏感零调用和无fallback；V5增量单独执行，不继承V4测试结论；旧任务历史合同不变 |
| `VAL-KFLOW-003` | 两域目录、计划、配置未知 key/越界启动失败测试通过 |
| `VAL-KFLOW-004` | Knowledge 非 live 回归、strict mypy、compileall、组合根 Summary V5 单注册及 V1～V4 历史不可变通过 |
| `VAL-KFLOW-005` | 当前启动入口 disabled 零依赖、enabled 唯一对象图和 Spring→Runtime 功能 UAT 通过 |
| `VAL-KFLOW-006` | 阶段 A 发布绑定可由现有在线链路只读消费，且不改变域选择、Rewrite、排序、错误或 fallback 行为 |
| `VAL-KFLOW-007` | 整理前改写章节（见归档）任务/计划/current root fake、strict mypy、compileall、历史hash及Spring回归；新真实语义另行验证 |
| `VAL-KFLOW-008` | 整理前改写章节（见归档） V8合同/当前根/Spring、历史隔离与hash、正式全量non-live、strict mypy、compileall；不产生或证明真实模型调用 |
| `VAL-KFLOW-009` | 整理前改写章节（见归档）当前根/合同/Spring/类型/全量与原专项UAT分别给出实际证据 |
| `VAL-KFLOW-010` | 整理前改写章节（见归档）定向/历史/当前根及Spring、正式隔离non-live、strict mypy、compileall；不证明真实改写或召回精度 |
| `VAL-KFLOW-011` | 整理前改写章节（见归档）纯校验/合同/当前根/Spring/历史与正式non-live、类型检查；真实语义仍由UAT独立判断 |
| `VAL-KFLOW-014` | 整理前改写章节（见归档）合同/当前根/Spring/历史及正式non-live、strict mypy/compileall；定向验证已通过，完整执行记录归[整理前P3 §20.94.1](../plans/历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md)，不证明真实UAT |

## 16. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 改写改变语义 | 模型删除否定/条件 | protected constraints + local validation | 否 |
| 零域掩盖拒绝 | 被拒问题恰好无域 | denied 优先规则和成对测试 | 否 |
| 阶段变公共动作 | Core 可分别调用 rewrite/retrieve | 只注册 `knowledge.query` | 否 |
| 配置扩权 | 动态域/路径 | 代码目录+未知 key 失败 | 否 |
| 新知识域 | 需要新增目录/Profile/策略 | 先修改 L1/L2 并验证读取/出域 | 需授权但不阻塞当前依据 |

## 17. 实施依据

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 按范围可用：目标合同可供后续授权实施；并非代码已完成 |
| 现行实现 | 源码11/7/quality-v3，仅作为迁移事实；原定向non-live证据不证明部署或完整真实UAT |
| 当前允许实施范围 | 后续独立授权后：§8的12/8/minimal-v1和§19资料接缝；设计评审后仍须独立实施授权，状态由P3_01治理 |
| 本轮权限 | 仅文档整合、归档、评审与验证，不修改或部署代码 |
| 当前禁止动作 | 新公开契约/域/权限、自动fallback、索引写入、消费旧授权或重跑历史候选 |
| 回滚单位 | Knowledge Capability、settings/catalog、成对任务绑定及Stage providers；优先禁用Knowledge |

## 18. v3.0评审记录

本轮仅整理文档，不继承旧评审。内审及正式分层、跨层复核的实际问题与结论见[整理记录](../历史文档/2026-09-14-unified-v3-baseline/MIGRATION.md)。整理前评审原样保存在归档；本轮为同一执行者分阶段复核，不冒充外部独立人员评审。

## 19. 资料表示与在线流程的接缝（新设计，未实施）

依据L1_01 §4.6的KQ-AD-025～028；离线具体字段与切片权威为L2_01_01 §18，引用权威为L2_01_02 §19。本节不改变§8的12/8/minimal-v1待实施方案，也不切换当前11/7/v3源码。

`DR-KFLOW-301`：原始资料、标准化sidecar及向量构建只能由离线工具消费；Runtime不得读取本地语料目录、拼接ES字段、额外取父正文或按用户输入选择物理索引。读取授权仍先于候选正文进入后续Stage，父子关系只是来源关系，不是授权凭证。enabled=false继续无Knowledge依赖；新增离线元数据不成为统一启动的强制前置。

`DR-KFLOW-302`：现typed候选仅有既有title/content/sourceUrl/documentNo/writtenDate等允许字段。taxType、effectLevel、validityStatus、effectiveDate及新的来源断言不会因为ES/sidecar存在而自动可见。首期不新增请求filter、公共响应字段或Prompt输入；writtenDate仍标记成文日期。无可靠时效证据时沿用既有不足/澄清边界，不能利用未传入的元数据宣称当前有效。支持按指定期间精确过滤或展示条款效力是另项合同设计，不伪装为本轮已具备。

`DR-KFLOW-303`：离线候选迁移与在线代码发布独立。发布后的精确索引、Profile及文档出域目录必须成套相容；只读ES alias核实不等于运行Java/Python实例已加载该绑定。部署验收需分别证明索引实际目标、服务Profile、Runtime任务及策略；任一不一致失败关闭。回滚以相容整套绑定或禁用Knowledge为单位，不单换alias掩盖catalog不匹配。不得重用历史授权执行发布。

### 19.1 实施追踪（未执行）

#### 新设计编号定义

| 规则编号 | 实现编号 | 测试编号 | 验证编号 |
|---|---|---|---|
| DR-KFLOW-301、DR-KFLOW-302、DR-KFLOW-303 | IMPL-KFLOW-301、IMPL-KFLOW-302、IMPL-KFLOW-303 | TEST-KFLOW-301、TEST-KFLOW-302、TEST-KFLOW-303 | VAL-KFLOW-301、VAL-KFLOW-302、VAL-KFLOW-303 |

#### 资料接缝追踪

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-KFLOW-007、CON-KFLOW-005、KQ-AD-025/028 | DR-KFLOW-301 | IMPL-KFLOW-301：现bootstrap/settings及离线工具的依赖隔离检查；原则上不改Runtime | TEST-KFLOW-301：disabled零依赖、不得导入corpus工具、父关系不扩读取 | VAL-KFLOW-301：静态及fake边界回归 |
| REQ-KQ-203/204、KQ-AD-026 | DR-KFLOW-302 | IMPL-KFLOW-302：复用es_adapter/codec及既有DTO白名单，测试防止离线字段泄漏 | TEST-KFLOW-302：成文非生效、未知日期/分类不注入、无额外父查询 | VAL-KFLOW-302：Python/Java契约和脱敏观测测试 |
| REQ-KFLOW-007、CON-KFLOW-005、KQ-AD-028 | DR-KFLOW-303 | IMPL-KFLOW-303：既有Profile verifier、binding/catalog部署验证；不新增服务 | TEST-KFLOW-303：alias/UUID/catalog错配、取消及恢复旧成套绑定 | VAL-KFLOW-303：fake后另授权隔离typed验证 |

本轮只读审计不运行这些测试或部署。测试缺口和发布步骤列入P3_01资料主线，当前公开合同原样保留。
