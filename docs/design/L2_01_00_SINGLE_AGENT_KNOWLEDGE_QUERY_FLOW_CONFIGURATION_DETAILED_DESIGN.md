# [L2_01_00] 单体 Agent Knowledge 查询流程与配置详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_00` |
| 当前版本 | v1.18 |
| 日期 | 2026-09-04 |
| 权威范围 | `knowledge.query` 单动作、逻辑域目录、问题改写、多阶段协同、失败优先级、请求状态和流程配置 |
| 上位文档 | [`L1_01` v1.17](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 来源文档 | [L2_01_00 v0.14 归档版](历史文档/2026-08-21-v0-baseline/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) |
| 实施状态 | 生产入口、disabled 惰性、Spring non-live E2E、域目录 v2、Rewrite V4（复用V3严格合同）、Summary V4、阶段 B 有界检索与阶段 A 发布后只读快照消费已实现并通过 non-live 验证；V4真实效果未测量，效果运行与门禁状态由 UAT_01/P3 管理 |

## 2. 阅读导航与变更记录

重点：第 7 节动作/域、第 8 节改写、第 9 节主流程、第 10 节失败优先级、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.18 | 2026-09-04 | 澄清触发边界偏窄 | 新增Rewrite V4，仅修正适用判断与资料查阅的Prompt决策边界；复用V3严格合同，V3及失败证据不变；实现及真实效果状态分别管理 |
| v1.0 | 2026-08-21 | 建立 Knowledge 流程新基线 | 删除 candidate/Gate 流水，保留单动作、五阶段、问题保护、零域语义与当前任务版本 |
| v1.1 | 2026-08-21 | 代码对照评审修复 | 明确阶段 operation 的创建时点，并校正错误码、内部类型约束和测试落点 |
| v1.2 | 2026-08-26 | 生产接线与功能 UAT | 固化默认关闭、同 Registry 单注册、任务/Provider/资源生命周期和功能验收边界 |
| v1.3 | 2026-08-26 | Q1/Q3/Q4 效果诊断 | 将域目录升级为 v2，并把生产目标任务改为 rewrite v1 + summary v3；历史 v1/v2 继续不可变 |
| v1.6 | 2026-08-28 | 任务版本与依赖纠偏 | 将组合根步骤统一为 Rewrite V1 + Summary V3；历史 V1/V2 责任不变 |
| v1.8 | 2026-08-28 | Summary V4 实施同步 | 组合根已唯一切换为 Rewrite V1 + Summary V4，disabled 零依赖和 V1～V3 历史哈希保持不变 |
| v1.10 | 2026-08-28 | 稳定权威纠偏 | 移除候选、Gate、预算和运行流水，只保留流程、任务版本、配置、失败语义及验证合同 |
| v1.11 | 2026-09-02 | Rewrite 输出合同纠偏 | 新增 Rewrite V2 精确 JSON Schema 提示并切换生产组合根；复用既有严格 decoder、Guard、fallback，Rewrite V1 与历史证据保持不可变 |
| v1.12 | 2026-09-02 | 阶段 A 语料边界 | 明确在线流程只消费发布后的只读 Profile/快照；离线语料处理由 L2_01_01 治理，不改变域选择、Rewrite、排序或公共失败语义 |
| v1.13 | 2026-09-02 | 阶段 A 发布绑定 | 同步 current policy catalog 与 candidate a2 只读绑定已通过启动、typed retrieval、Evidence 和防回退验证；在线算法不变 |
| v1.14 | 2026-09-03 | 阶段 A 当前快照复评 | 同步 candidate a4 的 index UUID、policy/law snapshot 与 catalog v2 绑定；旧快照继续可校验，在线域选择、Rewrite、排序和失败语义不变 |
| v1.15 | 2026-09-03 | 阶段 A 最终快照迁移 | 将最终源码一致的 candidate a5 policy/law snapshot 追加到 catalog v2 并切换当前启动绑定；a4 与全部旧快照仍可校验，在线域选择、Rewrite、排序和失败语义不变 |

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
| `CON-KFLOW-001` | `L0_00 SA-C-015/018/019/021` |
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
| Composition Root | 唯一绑定 Rewrite V4、Summary V4、目录、Stages 和设置 | 请求级策略判断 |

依赖方向为 `Capability → stage Protocol ← retrieval/evidence implementations`；目录和 settings 不依赖 HTTP/DeepSeek。禁止 Knowledge 内部阶段注册为公共能力，禁止 Capability 依赖 ES DSL 或模型 SDK。

该分层保持动作内高内聚、基础设施低耦合；不新增 knowledge-service。

## 6. 当前实现基线与最小变更

当前实现已有：`knowledge.query` provider、空对象参数、`KnowledgeQueryCapability`、`tax-domain-catalog-v2`、V3格式语义域计划、typed Retrieval/Evidence Stage、阶段 deadline、可注入组合根及默认关闭生产接线。显式启用的生产组合绑定 `KnowledgeRewriteTaskV4` + `KnowledgeSummaryTaskV4`；V4 Prompt增量已通过non-live验证，真实效果尚未测量。Rewrite V1/V2/V3旧绑定及Summary V1～V3保留历史兼容、证据和可追溯回滚责任；V3公开decoder/类型由V4复用。

旧 Summary V1～V3 保留给历史资产；新生产组合根完成切换后只能注册 V4，不得覆盖或删除历史任务。阶段执行接缝必须在 deadline/cancel 校验通过后才创建对应 awaitable，避免预算已耗尽时遗留未等待协程。

阶段 A 不修改上述运行时：离线工具完成候选构建和发布后，启动配置只绑定新 Profile/index/policy snapshot。若任何快照不一致，Runtime 或 `es-query-service` 启动失败；在线请求不能选择候选索引、执行 alias 管理或回退旧/新索引。

## 7. 动作、逻辑域与请求状态

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KFLOW-001` | 只注册 `knowledge.query`，argument schema 为 exact 空 object |
| `DR-KFLOW-002` | 五阶段都在一次 handler 内，Core 看不到内部工具或第二动作 |
| `DR-KFLOW-003` | 原问题先提取受保护约束；改写不得改变主体、时间、条件、否定或法条含义 |
| `DR-KFLOW-004` | 生产使用V3定义的 exact outcome/queries/missing_conditions 合同；V4复用同一decoder，仅改变§8.1指令；每域最多一个表达、最多两域；旧任务只读历史 |
| `DR-KFLOW-005` | V3模型/解码/约束失败停止且检索0；敏感输入模型0。旧 original fallback 设置只服务显式历史装配，不得触发生产回退 |
| `DR-KFLOW-006` | 逻辑域目录代码绑定且有序；配置只能选择已知域 |
| `DR-KFLOW-007` | 计划仅含逻辑域、stable path、query、limit；不含索引/字段/DSL |
| `DR-KFLOW-008` | 每阶段使用总 deadline 派生的较小 phase deadline；仅在预算校验通过后创建阶段 operation，超时不进入下一阶段 |
| `DR-KFLOW-009` | 授权拒绝/读取权威失败优先于局部技术成功；coverage 必须与计划精确对应 |
| `DR-KFLOW-010` | `question_egress_denied=true` 时策略拒绝优先于 zero-domain/no-result；普通零域仍为 no_result |
| `DR-KFLOW-011` | 默认启动入口必须先解析 `AGENT_KNOWLEDGE_ENABLED`；false 时不得加载下游配置、任务、策略或创建 client |
| `DR-KFLOW-012` | true时唯一追加当前批准并实施的Rewrite任务/Summary V4与Knowledge Provider；§8.1目标为Rewrite V4；重复注册启动失败，旧任务不进入新生产对象图 |
| `DR-KFLOW-019` | §8.1的Rewrite V4仅收紧适用判断澄清指令，复用V3精确decoder/类型/预算；批准并实施后替换生产V3绑定，不双注册、不改变公共结果 |
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

目录逻辑域及默认出域策略继续固定；旧 `tax-domain-catalog-v2` 词面 Selector 的以下规则仅描述历史基线，不用于 V3 生产准入。新任务输入由当前 enabled 目录生成安全描述，由模型依据原问题一次性选择0～2域，本地按目录顺序规范排序并拒绝未知或重复域。旧规则如下：

1. 没有税务锚点时选择零域；
2. 显式法律名称、`税法`、`法律/法规/条例` 或法条引用形成 `tax.law` 信号；
3. 独立政策文种或政策语义形成 `tax.policy` 信号；仅出现“优惠”等弱政策词且已有明确法律名称/法条时，不额外扩为政策域；
4. 法律与独立政策信号同时存在时按目录顺序选择两域；
5. 有税务锚点但没有明确法律信号时默认只选择 `tax.policy`，不再以全域 fallback 扩大召回。

Selector 不判断被问文件是否真实存在；有合法域但检索无候选时由既有 `no_result` 语义处理。此边界避免为虚构文件建立专用识别或修改数据集。

### 7.4 请求级状态

请求中依次产生 `ProtectedConstraintSet`、`RewriteStageResult`、`DomainSelection`、`KnowledgeRetrievalPlan`、`RetrievalStageResult`、`EvidenceStageResult`。内部传递类型为 frozen、slots；字符串、集合、coverage 与 stage-result 组合等边界分别由可信生产者、严格 decoder 和 Capability 消费点校验，不要求每个内部 dataclass 重复同一组校验；不写跨请求存储。

## 8. 问题改写详细设计

本节列出由V3引入并继续复用的严格合同；当前生产任务版本是§8.1的V4，并非同时执行V3和V4。

1. 原问题经当前 `QuestionEgressGuard` 后才可调用模型；原文保留在请求内，不把语义规划交给输入安全层。V1/V2 原任务文件及其 parser 保持历史字节不变。
2. V3 输入为安全原问题和已启用逻辑域安全目录；只含逻辑 ID、说明，不含 Profile、物理字段、索引或 URL。
3. V3 唯一 JSON 字段为 `outcome/queries/missing_conditions`。search：queries为1～2个 exact `{domain_id,query}`，domain唯一且启用，query为非空NFC文本≤1024；missing_conditions必须为空。clarification_required：queries为空，missing_conditions为1～3个不重复有限值（subject/taxpayer_type/calculation_method/applicable_period）。unsupported：两个列表均为空。未知键、重复键、null、尾随JSON、非有限值和类型coercion均拒绝。
4. 新 `KnowledgeRewriteTaskV3` 独立 exact decoder；新请求级 planner 实现同一 Rewrite Stage 协议，不复制 Capability 流程。模型提出的 domain/query 均为不可信数据；query 还须重新经过现有 QuestionEgressGuard，拒绝模型引入敏感值或不可外发输入，禁止把该失败降级为可用子集。任何一域不合法则整份计划拒绝；只有可信 planner 可设置新策略版本与域计划，外部请求和模型没有策略选择字段。
5. 每个查询必须保留原问题显式数字、日期、文号、法条、否定、纳税人和计税方法约束；NFC规范化后校验。新增有限税务条件检查只防止遗漏/补造，不决定域或检索参数。服务/主体同义词由模型理解，原问题始终是摘要边界；本地校验不能宣称证明了任意自然语言等价，必须用保留集和人工原文UAT补证。 未附带具体数值的“税率/征收率”是问题主题，不要求每个分域表达重复；它们须在整组表达中完整保留且不得新增或互换。单域仍须保留；具体百分数及其类型、日期、纳税人、计税方法、否定条件仍逐query校验。
6. V3失败/超时不得回退本地选域或原问题检索。clarification_required不执行检索/摘要；描述性分类与法规查阅不因未提供纳税人信息而一律拒绝。问题策略拒绝优先，模型0；普通unsupported保留既有no_matching_domain语义。

主题分配只作用于未携带具体数值的税率类主题词；只要原问含比例记号（%/％/‰/‱或百分之/千分之/万分之），两类主题词继续逐query保持，不能以“分域聚焦”丢失数值含义。实现由semantic_planner承担，测试覆盖双域分配、单域丢失、整组丢失、新增类型、数字/中文比例反例；不修改历史QuestionSemanticGuard。

改写结果同时保存 `question_egress_denied`，供后续零域/证据阶段正确决定策略拒绝优先级；不保存模型原始响应。

### 8.1 适用判断澄清边界修复（DR-KFLOW-019）

直接依据为`REQ-KQUALITY-003`、`KQ-AD-015`及UAT_01 §14。上文V3合同仍作为不可变解码基线；本增量批准和实施后，生产改为V4，保留V3源文件、Prompt和历史证据。当前V3指令把澄清限定为“具体主体”，比需求的“单一适用结论”更窄：未出现企业或个人名称不能证明条件充分。一次真实失败支持修复该偏窄规则，但不证明某一句Prompt是唯一根因。

比较：仅增候选窗口与这一语义问题无关；新增一整套intent/条件证据Schema仍依赖同一模型判断，增加解码和快照成本且不能确定性证明意图。采用最小的新版本Prompt，保留原有三种输出与同一请求级planner，不新增模型调用、本地行业规则或第二次审核模型。

V4在生成域/query前先判定检索目的，不输出推理过程或新的intent字段：

1. **适用判断**：用户要求为某服务、交易或经营活动选择一个适用税率/征收率、优惠或处理结果；不要求用户给出具体企业/个人名称。若结论会因原问未给出的纳税人类型、计税方法、期间或主体而不同，输出clarification_required，只列真正缺失的有限条件，不生成queries，不预设“通常”“当前”或一般纳税人。
2. **资料查阅**：用户明确要求定义、分类、指定法条、一般规则列举或比较，且无需为某交易选择单一结果，可以search；不得机械要求所有四类条件。问到“适用”不自动等于适用判断，例如列举适用范围仍可为资料查阅；不得按单词或酒店等特定行业硬编码。
3. **歧义**：两类目的无法可靠区分、而直接回答可能被理解为单一适用结论时，使用现有clarification_required，限定在既有missing_conditions可表达的必要条件内；若不存在可表达的缺失条件且无法形成可靠知识计划，使用unsupported，不伪造一种缺失条件或增加公开状态。
4. 主体/服务、纳税人、计税方法、日期、比例、否定、文号和法条保持规则不变。无新事实、无失败扩域、无模型失败回退。候选仍每域一个、最多两域；512输出tokens、16384输入bytes和8000ms任务timeout不变。新完整system_instruction必须满足既有StructuredModelRequest的8192 UTF-8 bytes上限，以构造测试验证，不能截断指令通过。

实施落点：已新增`knowledge/rewrite_v4.py`及`KnowledgeRewriteTaskV4.definition()`，通过V3公开definition复用输入构建和parse_response，只替换任务版本与完整Prompt，不导入私有helper、不编辑V3。`bootstrap.KnowledgeCompositionRoot.task_definitions/build_provider`仅接受Rewrite4/Summary4；`KnowledgeSemanticPlanner`继续使用相同输入/输出类型和校验，不增加本地意图分类。disabled路径不变。

验证：新增V4请求合同、V3/V4相同合法/非法输出解码矩阵、预算与历史源码hash检查；当前生产根验证澄清终态零search/embedding/rerank/summary、旧V3任务拒绝装配、单域/双域正常查询、unsupported/非法JSON/模型失败/超时及无fallback。真实失败资产和runner不更新、不重新执行。fake仅证明指令到达及返回分支正确，不能证明LLM会稳定选择正确分支；核心P0仍以既有冻结UAT预期等待新授权测量，不在本增量中改判。

回滚仅通过恢复上一提交的生产任务绑定，不能运行时失败回退V3；不改数据、索引、接口或权限。本增量只允许批准后的非live实施/验证；真实调用暂停，代码通过也不关闭整体质量工作包。

## 9. 检索计划与核心流程

### 9.1 计划

对每个已批准域按目录路径生成keyword/vector两项，使用该域唯一query；limit≤20，稳定顺序为目录→路径。V3 plan携带不可变原问题用于最终语义边界；同域两路表达必须相同。域集合固定后任何路径结果不得追加域或query。

### 9.2 主流程

```text
validate empty arguments
  → rewrite/guard
  → validated immutable semantic domain plan (legacy selector unreachable)
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

### 10.1 阶段 B 内部原因与现有公共合同映射

`DR-KFLOW-016`：新内部 `PlannedDomainQuery` 与 RewriteResult 的可选版本化plan字段由V3 decoder产生；默认空值仅供旧显式测试/历史装配兼容。新生产Capability必须使用V3计划，不能在字段缺失时调用旧Selector。`unsupported`仍映射既有no_matching_domain；clarification是内部阶段终态，不新增公开CapabilityStatus。

`DR-KFLOW-017`：原问题、域查询、snapshot、预算均为请求级不可变状态。V3输入≤16384bytes、输出≤512tokens，规划一次且≤8秒；含动作选择和Summary的外部模型调用每E2E最多3次。查询阶段仍≤20秒，各HTTP≤5秒；每域一个query：embedding≤2、search≤4、rerank≤2，重排总候选≤80。配置只能收紧，不能通过追加query扩容。

| 内部原因/分支 | 现有公开状态及结果 | 用户文本 | 规划后检索/摘要调用 |
|---|---|---|---|
| no_retrieval_hit | no_result，保留兼容reason=no_candidate | 未找到符合条件的结果。 | 已批准search≤4，summary0 |
| insufficient_evidence | no_result，reason=insufficient_evidence | 已检索到资料，但不足以完整回答此问题。 | search≤4，summary0或1 |
| clarification_required | no_result，reason=clarification_required | 查询条件不足，请补充适用期间、纳税人类型或计税方法等必要条件。 | search/embedding/rerank/summary均0 |
| question/model egress denied | model_egress_denied，既有有限错误code | 保持既有出域拒绝文案。 | 问题拒绝时所有模型0；Evidence拒绝时summary0 |
| all paths failed / inadequate partial coverage | timeout或downstream_failure，既有阶段code | 下游查询暂时不可用或请求超时。 | 不追加路径，summary0 |
| invalid plan / model failure | downstream_failure；超时为timeout | 保持既有下游失败/超时文案。 | search/embedding/rerank/summary均0 |

`DR-KFLOW-018`：NO_RESULT的reason在既有开放object结果字段中表达，不增加公开DTO字段/状态。Core只按经过Capability校验的有限reason渲染固定文案，不解析问题、不读取模型文本、不执行领域路由；其他reason与Business保持原文案。无条件或未知reason不能变成success。技术覆盖不足与结构损坏须区分；前者downstream_failure，后者有限invalid_provider_result，不用internal_failure掩盖可预期依赖失败。

## 11. 配置、预算与启动校验

| 配置 | 默认/范围 |
|---|---|
| `AGENT_KNOWLEDGE_ENABLED` | false |
| `ENABLED_DOMAINS` | 只能是目录已知 ID，启用时至少一个 |
| rewrite candidates | 旧V1/V2设置1..3保留历史；V3至多2个唯一域表达 |
| original fallback | 旧设置保留历史；V3忽略该后备开关并始终失败关闭 |
| retrieval query chars | 默认/最大 1024 |
| per-path candidates | 默认 20，5..20 |
| partial candidates | 默认 3，3..20 且≤per-path |
| rewrite/retrieval/evidence timeout | 8000/20000/15000ms，均有界 |

未知 `AGENT_KNOWLEDGE_*` key 启动失败。配置只能收紧目录/代码边界；启用 Knowledge 时任务、目录、两 Stage 和所有依赖必须齐全，组合根才可 ready。

### 11.1 生产组合根装配顺序

1. 加载 `KnowledgeSettings`；disabled 时立即返回“无附加任务、无附加 Provider、无 owned Knowledge resource”的结果。
2. enabled 时拒绝生产 stub provider；测试可显式注入 fake transport，但必须继续走同一装配函数和注册校验。
3. enabled 时加载 `KnowledgeRetrievalSettings` 和 policy catalog，验证已启用域、Profile version、ES/BGE origins、1024 维、rerank model、final candidates 与 task version。
4. §8.1批准实施后创建 Rewrite V4/Summary V4 definitions，并作为既有 Model Gateway 的唯一 Knowledge 注册项；旧V1/V2/V3不同时注册、不作自动后备。
5. 所有纯配置、目录、策略和任务校验完成后，才为三个固定 origin 分别创建 bounded HTTP client/transport并构建 Retrieval/Provider。
6. 把 `KnowledgeCapabilityProvider` 作为 `BusinessQueryRuntimeCompositionRoot.additional_providers` 追加到同一 Runtime。
7. 顶层 lifecycle 同时拥有 Business clients、Knowledge clients 和 model；关闭按资源逐项尝试，保留首个异常但仍释放其余资源。

不得把部分构建对象暴露为 ready Runtime。通过把所有可预见校验前置到 client 创建之前，避免为同步启动路径另建异步“半成品清理”协议；已成功装配的 Runtime 必须完整关闭 owned resources。

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

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-KFLOW-001` | `agent-runtime/src/agent_runtime/knowledge/provider.py`：descriptor 和 registrations |
| `IMPL-KFLOW-002` | `agent-runtime/src/agent_runtime/knowledge/capability.py`：`KnowledgeArgumentValidator`、`KnowledgeQueryCapability.handle` |
| `IMPL-KFLOW-003` | `agent-runtime/src/agent_runtime/knowledge/question_semantics.py`：semantic guard |
| `IMPL-KFLOW-004` | 已有 `knowledge/rewrite_v3.py`（精确合同）与 `knowledge/semantic_planner.py`（同一Rewrite Stage协议适配）；已新增 `knowledge/rewrite_v4.py`复用公开V3合同并修正Prompt；bootstrap唯一绑定；历史文件不改 |
| `IMPL-KFLOW-005` | `agent-runtime/src/agent_runtime/knowledge/catalog.py`、`domain_selection.py` |
| `IMPL-KFLOW-006` | `agent-runtime/src/agent_runtime/knowledge/planning.py`：`KnowledgeRetrievalPlanBuilder.build` |
| `IMPL-KFLOW-007` | `agent-runtime/src/agent_runtime/knowledge/contracts.py`、`agent-runtime/src/agent_runtime/knowledge/context.py` |
| `IMPL-KFLOW-008` | `agent-runtime/src/agent_runtime/knowledge/settings.py`、`agent-runtime/src/agent_runtime/bootstrap.py` 的 Knowledge composition |
| `IMPL-KFLOW-009` | `agent-runtime/src/agent_runtime/main.py`：按开关构建 Knowledge tasks/retrieval/provider 并追加到 Business Runtime |
| `IMPL-KFLOW-010` | `agent-runtime/src/agent_runtime/bootstrap.py`：顶层 owned resource 生命周期与 disabled 零依赖装配 |
| `IMPL-KFLOW-011` | `agent-runtime` 当前策略目录加载与 `serviceCenter/knowledge-runtime-binding.v1.json`：只读发布绑定；历史目录继续独立可校验 |

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

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-KFLOW-001` | Provider/Capability 契约和单动作调用计数测试通过 |
| `VAL-KFLOW-002` | 当前Rewrite精确合同、Guard、敏感零调用和无fallback；V4增量单独执行，不继承V3测试结论；旧任务历史合同不变 |
| `VAL-KFLOW-003` | 两域目录、计划、配置未知 key/越界启动失败测试通过 |
| `VAL-KFLOW-004` | Knowledge 非 live 回归、strict mypy、compileall、组合根 Summary V4 单注册及 V1～V3 历史不可变通过 |
| `VAL-KFLOW-005` | 当前启动入口 disabled 零依赖、enabled 唯一对象图和 Spring→Runtime 功能 UAT 通过 |
| `VAL-KFLOW-006` | 阶段 A 发布绑定可由现有在线链路只读消费，且不改变域选择、Rewrite、排序、错误或 fallback 行为 |

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
| 是否可作为实现依据 | 是，v1.18的DR-KFLOW-019已完成三轮内审及独立复评，只批准非live实施；核心P0和真实UAT仍未通过 |
| 当前允许实施范围 | 既有在线流程；DR-KFLOW-019批准后仅非live任务版本修复，不涉及Profile/index/policy变更 |
| 当前禁止动作 | 未配置新域/物理资源选择、公共契约变化、未按UAT冻结或超预算的真实模型调用、请求触发索引写入或独立服务 |
| 回滚单位 | Knowledge Capability + settings/catalog + task bindings + Stage providers |

## 18. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 单动作、阶段、责任、来源和追踪一致 | Passed |
| 内审 2 | 错误优先级、安全、状态、配置和任务绑定一致 | Passed |
| 内审 3 | 真实落点、测试、版本、链接和可读性检查通过 | Passed |
| 独立评审 | `REV-L2-01-00-001` 已修复；单动作、五阶段、任务绑定、失败优先级与实现复核通过 | Passed |
| v1.2 聚焦评审与复评 | 修复 enabled+production-stub 歧义和半成品异步清理过度要求后，disabled 惰性、唯一注册、资源释放、Business 隔离通过；无 S0/S1/未处理 S2 | Passed |
| v1.3 三轮内审 | 域选择优先级、Summary v3 绑定、零域语义与历史任务隔离一致 | Passed |
| v1.3 独立评审 | 无 S0/S1/未处理 S2；Selector 不猜测文档真实性，DAG 无环 | Passed |
| v1.6 三轮内审与独立复评 | Rewrite V1/Summary V3 唯一生产绑定、历史 V1/V2 隔离和上位版本一致；无 S0/S1/未处理 S2 | Passed |
| v1.7 三轮内审与独立评审 | Summary V4 单绑定目标、V1～V3 历史隔离、组合根/回滚/门禁一致；无 S0/S1/未处理 S2 | Passed |
| v1.10 三轮内审与独立评审 | 稳定流程权威、Summary V4 单绑定、效果运行状态下沉与跨层依赖核对通过；S0=0、S1=0、未处理 S2=0 | Passed |
| v1.11 聚焦内审与独立评审 | Rewrite V2 精确 JSON 合同、V1 历史隔离、fallback/失败关闭和生产单绑定一致；S0=0、S1=0、未处理 S2=0 | Passed |
| v1.13 对照复评 | current policy catalog、candidate a2 snapshot、typed retrieval 与现有在线流程消费一致；未改变域选择、Rewrite、排序、失败语义或 fallback，S0=0、S1=0、未处理S2=0 | Passed |
| v1.14 对照复评 | candidate a4 的 policy/law snapshot、5600 项 catalog 全成员及启动 verifier 一致；保留旧快照，未改变在线算法或 fallback，S0=0、S1=0、未处理 S2=0 | Passed |
| v1.15 对照复评 | candidate a5 的 policy/law snapshot、5600 项 catalog 全成员、启动 verifier 与最终工具源码清单一致；a4/旧快照保留，未改变在线算法或 fallback，S0=0、S1=0、未处理 S2=0 | Passed |
| v1.18 内审1 | 对照REQ-KQUALITY-003/KQ-AD-015，适用判断不限于具名主体，资料查阅不机械要求全部条件；不新增本地意图规则 | Passed |
| v1.18 内审2 | 核实公开definition可用dataclass替换复用，V3decoder/预算不变，补充8192bytes指令边界；零调用、版本守卫、disabled路径及回滚明确 | Passed |
| v1.18 内审3 | 纠正§6/14/15旧V2实施描述及当前/拟议混淆；冻结真实批次不改，fake不能关闭P0，DAG无需新Gate | Passed |
| v1.18 独立审查首轮 | 分离作者修改阶段后重新核对L1/L2/REQ及代码契约；无S0/S1，发现S2：DR019未进入§4.2主追踪表、实施依据的否决状态不明确；已最小修复 | Fixed，待复评 |
| v1.18 独立复评 | 主追踪、实施准入、定义/查阅与适用判断、共享decoder、指令大小、失败零调用、单绑定及历史隔离闭合；S0=0、S1=0、未处理S2=0。为自动化辅助的分阶段审查，不冒充外部人工批准 | Passed，仅非live实施 |

- 当前版本：v1.18。
- 文档状态：Approved；DR-KFLOW-019增量评审通过，不代表代码实施完成或真实UAT通过。
- 新版本不继承旧版 candidate、Gate 或评审流水；来源与当前任务绑定已明确。

## 阶段 B 增量实施追踪

| 来源 | 设计 | 实现落点 | 测试 | 验证 |
|---|---|---|---|
| `REQ-KQUALITY-001～004`；`KQ-AD-013～016` | `DR-KFLOW-016～018` | rewrite_v3.py / semantic_planner.py / contracts.py / planning.py / capability.py；Core graph/nodes.py 固定文案；bootstrap 当前任务绑定 | `TEST-KFLOW-011`：V3 exact解码、原问题条件、单域/双域、澄清/unsupported/模型失败零检索、局部/全路径失败、固定reason文案、历史V1/V2字节不变 | `VAL-KFLOW-004`：V3单元/契约、生产根fake/Spring E2E、UAT_01 §14、模型/检索计数、strict mypy |
| `REQ-KQUALITY-003`；`KQ-AD-015` | `DR-KFLOW-019` | rewrite_v4.py；bootstrap任务工厂及版本守卫 | `TEST-KFLOW-003/004/009`：V4精确合同及Prompt、旧V3拒绝装配、生产澄清零调用；保留V3和冻结runner | `VAL-KFLOW-002/005`：non-live与Spring E2E已执行通过；实际LLM语义稳定性仍待新授权，不在本次补跑 |

上述编号定义本轮新增验证，不继承已有 Passed。新生产策略为 `knowledge-retrieval-quality-v1`，显式由生产组合根选用；旧调用默认保持 legacy，历史任务/证据不修改。UAT 使用独立阶段 B 命名空间，验收标准和执行状态归 UAT_01/P3。
