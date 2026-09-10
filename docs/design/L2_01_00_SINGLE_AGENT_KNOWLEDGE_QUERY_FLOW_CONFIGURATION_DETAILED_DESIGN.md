# [L2_01_00] 单体 Agent Knowledge 查询流程与配置详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_00` |
| 当前版本 | v1.30 |
| 日期 | 2026-09-10 |
| 权威范围 | `knowledge.query` 单动作、逻辑域目录、问题改写、多阶段协同、失败优先级、请求状态和流程配置 |
| 上位文档 | [`L1_01` v1.23](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 本次增量 | DR-KFLOW-029原问keyword与分域vector计划；增量评审通过、尚未实施；现行Rewrite9/Summary7及quality-v3合同不改 |
| 来源文档 | [L2_01_00 v0.14 归档版](历史文档/2026-08-21-v0-baseline/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) |
| 实施状态 | 生产入口、disabled惰性、域目录v2、Rewrite V9/Summary V7/quality-v3、阶段B有界检索与阶段A只读快照消费已实现；当前对象图定向non-live通过，真实效果尚未验证。DR-KFLOW-023～028已实施，验证由P3管理，效果由UAT_01管理 |

## 2. 阅读导航与变更记录

重点：第 7 节动作/域、第 8 节改写、第 9 节主流程、第 10 节失败优先级、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.30 | 2026-09-10 | 改写表达替代两路原问使词面线索同时丢失 | §8.10定义原问来源、长度预选、内部计划字段与显式组合根接线，不修改模型输出及公开DTO |
| v1.29 | 2026-09-10 | 分域聚焦与逐query复制全部约束冲突 | §8.9明确需求归属、未分配条件保守全局、计数/顺序及语义证明限制；版本化替换而非移除Guard |
| v1.28 | 2026-09-09 | 正常查阅前缀被当作文号本体，合理focus误拒 | §8.8限定前缀词法分离，保持机关/年份/编号及旧Guard字节；新增当前根Guard与反证测试落点 |
| v1.27 | 2026-09-09 | 原问分类限定未完整体现在引用中 | 目标配对Summary7，Rewrite8、检索和内部合同保持；不修改历史版本 |
| v1.26 | 2026-09-08 | 授权元数据评分表示接线 | §11.1明确内部评分版本、历史兼容、disabled惰性和快照；Rewrite8/Summary6/quality-v3及预算不变 |
| v1.25 | 2026-09-07 | 完整重写V7 Prompt遗漏澄清优先规则 | §8.6恢复既有意图/条件决策顺序，保持decoder和预算；纠正§11.1旧绑定说明，不改历史任务 |
| v1.24 | 2026-09-07 | 必要证明未在规划和下游形成共同合同 | 新Rewrite7需求计划及内部透传、成对版本/回滚和严格失败关闭；旧V3～V6合同保留，不改公开接口 |
| v1.23 | 2026-09-07 | 类别词中的中文词素被错误识别为数值 | DR-KFLOW-023区分既有四类税务条件与数量约束，保留历史Guard和真实数字/日期/比例检查；仅当前根显式绑定，已评审准入非live实施 |
| v1.22 | 2026-09-04 | 排序与Evidence策略必须同版消费 | DR-KFLOW-022定义V2内部版本透传、唯一成对绑定及历史V1隔离，不改变模型或HTTP Schema |
| v1.21 | 2026-09-04 | 每域检索表达被其他子问题的背景牵引 | 新增DR-KFLOW-021：Rewrite V6只调整每域表达聚焦指令，保留V3 decoder/Guard和V4/V5澄清/最小必要域；排序、Evidence配额、Summary及历史资产不改；本增量评审前不可实施 |
| v1.20 | 2026-09-04 | 用户确认摘要分类上下文证明要求 | DR-KFLOW-012的目标单绑定调整为Rewrite5/Summary5，摘要语义由L2_01_02 DR-KEV-027治理；旧任务/validator/历史资产不变 |
| v1.19 | 2026-09-04 | 原文类别与税务背景混淆 | DR-KFLOW-020新增Rewrite V5，仅明确最小必要域的判断顺序；保留V3 decoder、V4澄清规则、Summary V4和历史资产；实施及测量状态见P3 |
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
| `REQ-KFLOW-002`、`REQ-KFLOW-003`、`CON-KFLOW-004` | `DR-KFLOW-020` | `IMPL-KFLOW-004`、`IMPL-KFLOW-010` | `TEST-KFLOW-012` | `VAL-KFLOW-002`、`VAL-KFLOW-005` |
| `REQ-KFLOW-002`、`REQ-KFLOW-003`、`CON-KFLOW-004` | `DR-KFLOW-021` | `IMPL-KFLOW-004`、`IMPL-KFLOW-010` | `TEST-KFLOW-013` | `VAL-KFLOW-002`、`VAL-KFLOW-005` |
| `REQ-KFLOW-003`、`CON-KFLOW-004`；`KQ-AD-014` | `DR-KFLOW-022` | `IMPL-KFLOW-004`、`IMPL-KFLOW-010`：semantic_planner、planning、capability、bootstrap的内部版本透传 | `TEST-KFLOW-014`：V2成对绑定、未知版本零检索、历史V1、disabled与单动作 | `VAL-KFLOW-005`：当前根/历史根及严格类型回归 |
| `REQ-KFLOW-002`、`CON-KFLOW-004`；`KQ-AD-013` | `DR-KFLOW-023` | `IMPL-KFLOW-003`、`IMPL-KFLOW-004`、`IMPL-KFLOW-010` | `TEST-KFLOW-015` | `VAL-KFLOW-002`、`VAL-KFLOW-005` |
| `REQ-KFLOW-002`、`REQ-KFLOW-003`、`REQ-KFLOW-005`；`KQ-AD-018` | `DR-KFLOW-024` | `IMPL-KFLOW-012` | `TEST-KFLOW-016` | `VAL-KFLOW-007` |
| `REQ-KFLOW-002`、`REQ-KFLOW-004`；`KQ-AD-015` | `DR-KFLOW-025` | `IMPL-KFLOW-013` | `TEST-KFLOW-017` | `VAL-KFLOW-008` |
| `REQ-KFLOW-002`；`KQ-AD-013` | `DR-KFLOW-027` | `IMPL-KFLOW-015` | `TEST-KFLOW-019` | `VAL-KFLOW-010` |
| `REQ-KFLOW-002`；`KQ-AD-013/018` | `DR-KFLOW-028` | `IMPL-KFLOW-016` | `TEST-KFLOW-020` | `VAL-KFLOW-011` |
| `REQ-KFLOW-004`；`KQ-AD-018` | `DR-KFLOW-026` | `IMPL-KFLOW-014` | `TEST-KFLOW-018` | `VAL-KFLOW-009` |

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
| Composition Root | 唯一绑定当前已实施的Rewrite/Summary、目录、Stages和设置；当前§8.9为9/7/v3 | 请求级策略判断 |

依赖方向为 `Capability → stage Protocol ← retrieval/evidence implementations`；目录和 settings 不依赖 HTTP/DeepSeek。禁止 Knowledge 内部阶段注册为公共能力，禁止 Capability 依赖 ES DSL 或模型 SDK。

该分层保持动作内高内聚、基础设施低耦合；不新增 knowledge-service。

## 6. 当前实现基线与最小变更

当前实现已有`knowledge.query`、空参数、Capability、域目录v2、typed Retrieval/Evidence Stage、阶段deadline及默认关闭接线。显式启用唯一绑定`KnowledgeRewriteTaskV9` + `KnowledgeSummaryTaskV7` + quality-v3，采用§8.5必要证据合同、§8.6意图规则及§8.9分域条件校验；§8.4类别词保护保持。旧Rewrite V1～V8、Summary V1～V6及其decoder/基类保留历史兼容和可追溯回滚责任。§8.9的Rewrite9、纯校验、Planner及生产根已实施，现行Spring fake同步使用新根；非live验证和代码复核见P3 §20.77.2。当前non-live与历史真实效果证明范围分离，见UAT_01。

旧Summary V1～V6保留给历史资产；当前生产组合根只能注册V7，不得覆盖或删除历史任务。阶段执行接缝必须在deadline/cancel校验通过后才创建对应awaitable，避免预算已耗尽时遗留未等待协程。

阶段 A 不修改上述运行时：离线工具完成候选构建和发布后，启动配置只绑定新 Profile/index/policy snapshot。若任何快照不一致，Runtime 或 `es-query-service` 启动失败；在线请求不能选择候选索引、执行 alias 管理或回退旧/新索引。

## 7. 动作、逻辑域与请求状态

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KFLOW-001` | 只注册 `knowledge.query`，argument schema 为 exact 空 object |
| `DR-KFLOW-002` | 五阶段都在一次 handler 内，Core 看不到内部工具或第二动作 |
| `DR-KFLOW-003` | 原问题先提取受保护约束；改写不得改变主体、时间、条件、否定或法条含义 |
| `DR-KFLOW-004` | 当前生产V9使用§8.5 V7精确五字段合同及同一decoder；每域最多一个表达、最多两域。此前V3三字段及V4～V6复用decoder仅用于历史版本，不用于宽松解码V7～V9 |
| `DR-KFLOW-005` | V3模型/解码/约束失败停止且检索0；敏感输入模型0。旧 original fallback 设置只服务显式历史装配，不得触发生产回退 |
| `DR-KFLOW-006` | 逻辑域目录代码绑定且有序；配置只能选择已知域 |
| `DR-KFLOW-007` | 计划只含逻辑域、stable path、query、limit及代码绑定版本；DR-KFLOW-024仅增加内部证据需求，不含物理索引/字段/DSL |
| `DR-KFLOW-008` | 每阶段使用总 deadline 派生的较小 phase deadline；仅在预算校验通过后创建阶段 operation，超时不进入下一阶段 |
| `DR-KFLOW-009` | 授权拒绝/读取权威失败优先于局部技术成功；coverage 必须与计划精确对应 |
| `DR-KFLOW-010` | `question_egress_denied=true` 时策略拒绝优先于 zero-domain/no-result；普通零域仍为 no_result |
| `DR-KFLOW-011` | 默认启动入口必须先解析 `AGENT_KNOWLEDGE_ENABLED`；false 时不得加载下游配置、任务、策略或创建 client |
| `DR-KFLOW-012` | true时唯一追加当前批准并实施的Rewrite/Summary任务与Knowledge Provider；当前§8.9为Rewrite V9/Summary V7，摘要由L2_01_02 §9.6治理；重复注册启动失败，旧任务不进入新生产对象图 |
| `DR-KFLOW-019` | §8.1的Rewrite V4仅收紧适用判断澄清指令，复用V3精确decoder/类型/预算；批准并实施后替换生产V3绑定，不双注册、不改变公共结果 |
| `DR-KFLOW-020` | §8.2的Rewrite V5明确原文类别与最小必要域，复用V3合同及V4澄清规则；仅模型负责语义选域，不新增本地关键词规则、额外调用或Summary变更 |
| `DR-KFLOW-021` | §8.3的Rewrite V6以本域待证明子问题为query边界，不把其他子问题的背景词机械复制到每域；原问题和所有既有显式条件校验不变，V6批准并实施后唯一替换V5，不影响排序/Evidence/Summary |
| `DR-KFLOW-022` | 质量策略V2内部版本沿planner→plan→retrieval→Evidence透传并与limits成对绑定；详见文末增量，模型及HTTP不能选择版本 |
| `DR-KFLOW-023` | 当前根仅将既有四个明确类别短语与数量分开检查；数字之外的约束、逐域类别保护及全部失败关闭不变，历史Guard/default不变；详见§8.4 |
| `DR-KFLOW-024` | §8.5 Rewrite7一次生成有界需求，检索前冻结并贯穿后续阶段；已实施及non-live验证，不把旧三字段输出当作新合同接受 |
| `DR-KFLOW-025` | §8.6恢复澄清优先指令，新V8复用相同五字段decoder；不以fake证明真实语义，生产版本切换须完成该切片评审 |
| `DR-KFLOW-026` | §8.7仅将当前摘要绑定升级为V7，Rewrite8/quality-v3及全部限额不变；版本严格匹配，不新增在线流程 |
| `DR-KFLOW-027` | §8.8只分离文号前有限查阅措辞，保留真正约束、旧Guard和模型输入；新当前根Guard不生成检索计划 |
| `DR-KFLOW-028` | §8.9在同一次Rewrite的既有requirements中声明条件归属，严格检查本域与未分配全局条件；新V9复用精确五字段decoder，旧V7/V8行为保持，禁止跨域补救和条件补造 |
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

本节列出V3～V8沿用的严格合同及版本增量；当前生产为§8.9的V9及§8.7的Summary7。§8.9仅在V9中替换逐query约束范围规则，其他结构、输入安全、预算和失败边界继续适用；§8.5～8.8中的旧绑定保留当时版本语境，不是同时执行多个Rewrite。

1. 原问题经当前 `QuestionEgressGuard` 后才可调用模型；原文保留在请求内，不把语义规划交给输入安全层。V1/V2 原任务文件及其 parser 保持历史字节不变。
2. V3 输入为安全原问题和已启用逻辑域安全目录；只含逻辑 ID、说明，不含 Profile、物理字段、索引或 URL。
3. V3 唯一 JSON 字段为 `outcome/queries/missing_conditions`。search：queries为1～2个 exact `{domain_id,query}`，domain唯一且启用，query为非空NFC文本≤1024；missing_conditions必须为空。clarification_required：queries为空，missing_conditions为1～3个不重复有限值（subject/taxpayer_type/calculation_method/applicable_period）。unsupported：两个列表均为空。未知键、重复键、null、尾随JSON、非有限值和类型coercion均拒绝。
4. 新 `KnowledgeRewriteTaskV3` 独立 exact decoder；新请求级 planner 实现同一 Rewrite Stage 协议，不复制 Capability 流程。模型提出的 domain/query 均为不可信数据；query 还须重新经过现有 QuestionEgressGuard，拒绝模型引入敏感值或不可外发输入，禁止把该失败降级为可用子集。任何一域不合法则整份计划拒绝；只有可信 planner 可设置新策略版本与域计划，外部请求和模型没有策略选择字段。
5. 每个查询必须保留原问题显式数字、日期、文号、法条、否定、纳税人和计税方法约束；NFC规范化后校验。新增有限税务条件检查只防止遗漏/补造，不决定域或检索参数。服务/主体同义词由模型理解，原问题始终是摘要边界；本地校验不能宣称证明了任意自然语言等价，必须用保留集和人工原文UAT补证。 未附带具体数值的“税率/征收率”是问题主题，不要求每个分域表达重复；它们须在整组表达中完整保留且不得新增或互换。单域仍须保留；具体百分数及其类型、日期、纳税人、计税方法、否定条件仍逐query校验。
6. V3失败/超时不得回退本地选域或原问题检索。clarification_required不执行检索/摘要；描述性分类与法规查阅不因未提供纳税人信息而一律拒绝。问题策略拒绝优先，模型0；普通unsupported保留既有no_matching_domain语义。

主题分配只作用于未携带具体数值的税率类主题词；只要原问含比例记号（%/％/‰/‱或百分之/千分之/万分之），两类主题词继续逐query保持，不能以“分域聚焦”丢失数值含义。实现由semantic_planner承担，测试覆盖双域分配、单域丢失、整组丢失、新增类型、数字/中文比例反例；不修改历史QuestionSemanticGuard。

改写结果同时保存 `question_egress_denied`，供后续零域/证据阶段正确决定策略拒绝优先级；不保存模型原始响应。

### 8.1 适用判断澄清边界修复（DR-KFLOW-019）

直接依据为`REQ-KQUALITY-003`、`KQ-AD-015`及UAT_01 §14。上文V3合同仍作为不可变解码基线；V4实施阶段将生产从V3切换至V4，保留V3源文件、Prompt和历史证据，当前任务绑定见§8.2。V3指令把澄清限定为“具体主体”，比需求的“单一适用结论”更窄：未出现企业或个人名称不能证明条件充分。一次真实失败支持修复该偏窄规则，但不证明某一句Prompt是唯一根因。

比较：仅增候选窗口与这一语义问题无关；新增一整套intent/条件证据Schema仍依赖同一模型判断，增加解码和快照成本且不能确定性证明意图。采用最小的新版本Prompt，保留原有三种输出与同一请求级planner，不新增模型调用、本地行业规则或第二次审核模型。

V4在生成域/query前先判定检索目的，不输出推理过程或新的intent字段：

1. **适用判断**：用户要求为某服务、交易或经营活动选择一个适用税率/征收率、优惠或处理结果；不要求用户给出具体企业/个人名称。若结论会因原问未给出的纳税人类型、计税方法、期间或主体而不同，输出clarification_required，只列真正缺失的有限条件，不生成queries，不预设“通常”“当前”或一般纳税人。
2. **资料查阅**：用户明确要求定义、分类、指定法条、一般规则列举或比较，且无需为某交易选择单一结果，可以search；不得机械要求所有四类条件。问到“适用”不自动等于适用判断，例如列举适用范围仍可为资料查阅；不得按单词或酒店等特定行业硬编码。
3. **歧义**：两类目的无法可靠区分、而直接回答可能被理解为单一适用结论时，使用现有clarification_required，限定在既有missing_conditions可表达的必要条件内；若不存在可表达的缺失条件且无法形成可靠知识计划，使用unsupported，不伪造一种缺失条件或增加公开状态。
4. 主体/服务、纳税人、计税方法、日期、比例、否定、文号和法条保持规则不变。无新事实、无失败扩域、无模型失败回退。候选仍每域一个、最多两域；512输出tokens、16384输入bytes和8000ms任务timeout不变。新完整system_instruction必须满足既有StructuredModelRequest的8192 UTF-8 bytes上限，以构造测试验证，不能截断指令通过。

实施落点：已新增`knowledge/rewrite_v4.py`及`KnowledgeRewriteTaskV4.definition()`，通过V3公开definition复用输入构建和parse_response，只替换任务版本与完整Prompt，不导入私有helper、不编辑V3。该增量当时将`bootstrap.KnowledgeCompositionRoot.task_definitions/build_provider`绑定为Rewrite4/Summary4；当前唯一绑定见§8.2。`KnowledgeSemanticPlanner`继续使用相同输入/输出类型和校验，不增加本地意图分类。disabled路径不变。

验证：新增V4请求合同、V3/V4相同合法/非法输出解码矩阵、预算与历史源码hash检查；当前生产根验证澄清终态零search/embedding/rerank/summary、旧V3任务拒绝装配、单域/双域正常查询、unsupported/非法JSON/模型失败/超时及无fallback。真实失败资产和runner不更新、不重新执行。fake仅证明指令到达及返回分支正确，不能证明LLM会稳定选择正确分支；核心P0仍以既有冻结UAT预期等待新授权测量，不在本增量中改判。

回滚仅通过恢复上一提交的生产任务绑定，不能运行时失败回退V3；不改数据、索引、接口或权限。本增量只允许批准后的非live实施/验证；真实调用暂停，代码通过也不关闭整体质量工作包。

### 8.2 最小必要原文域（DR-KFLOW-020）

直接上位为L1_01 KQ-AD-013：原问题一次性决定必要域，模型负责语义，本地只验证合同。已核实V4只概括“政策分类用policy、法定规则用law”，没有明确税务背景与原文类别的区别；合法的两域输出会被本地正确接受，结构白名单不能证明第二域在语义上必要。该风险不能通过检索窗口、事后删域或本地关键词路由修复。

采用独立`KnowledgeRewriteTaskV5`（已新增`knowledge/rewrite_v5.py`），复用V4请求构造与V3 exact decoder，只有task_version及system_instruction变化。指令继承§8.1全部适用判断/澄清、条件保持、禁止补造和失败关闭规则，并明确以下决策：

1. 域表示所需原文类别，不是税种标签。只有税种、税务背景或一般政策定义/分类，不足以增加法律域。
2. 问题只要求政策文件、实施细则中的定义、分类或办理条件，且未提出独立法律规则问题时，只选`tax.policy`；指定法律/行政法规的法条、基本规则查阅而不要求政策分类/实施依据时，只选`tax.law`。这不是“出现某词即选域”，应结合完整语义。
3. 只有回答原问题确实需要政策分类/实施依据与法律规则分别提供不可替代的依据时，才一次选择两域。不为补充背景、保险召回或重复同一问题增加域。
4. 不依据常识补出用户未问的税率、期间、法条或第二个问题。不因单独出现“税率”就指定law；不得假设某历史期间适用当前法律。目录未启用必要域时按既有unsupported/失败关闭合同处理，不静默改用其他域。
5. 查询表达、白名单、每域1表达、最多2域、512输出tokens、16384输入bytes、8000ms超时和8192指令bytes上限不变；没有新intent字段、规则引擎、模型复核轮次或失败后扩域。

仅改Prompt适用于这个已定位的局部缺口，不作为阶段B整体修复方案。对比：扩大topK与选域语义无关；本地关键词纠域违反语义职责；新增领域理由Schema仍由同一模型产生且增加解码/治理成本。本方案不宣称静态测试能证明LLM语义稳定性。

本Rewrite增量当时将`KnowledgeCompositionRoot.task_definitions/build_provider`的唯一Rewrite绑定及版本守卫改为V5、保留Summary V4；当前Summary绑定见§11.1。版本守卫继续由代码固定，不接受环境配置；生产不得注册或回退旧Rewrite V4。旧V1～V4任务、runner、case/gold及所有冻结资产不改。历史测试若需要旧根，仅在测试作用域从其冻结Git源码加载该根或显式装配旧版本；不能为历史兼容放开生产守卫。回滚是整套源码/任务绑定的一致回退，不允许单请求切换任务。

验证追踪：`TEST-KFLOW-012`→新增V5请求/预算/指令合同、与V3/V4相同合法/非法decoder矩阵、历史源码哈希；当前生产fake验证policy/law/双域、澄清、unsupported、模型错误/超时及零下游调用、旧版本拒绝装配；独立保留非酒店表达。V5 fake只能证明指令、装配和行为边界，不得计为真实UAT通过。摘要必要条款覆盖仍为独立未关闭项，本设计不修改Summary、validator、gold、检索排序或Evidence配额；后续真实运行必须另有未消费绑定授权。

### 8.3 每域子问题聚焦（DR-KFLOW-021）

上位为`REQ-KQUALITY-001/002`与`KQ-AD-013`：模型理解原问题、一次决定必要域，原问题始终作为最终回答边界。当前V4/V5指令同时允许分类/规则分域聚焦，又要求每个query重复原问题税务或法律语境，易把属于另一子问题的法律名称或规则主题复制到分类查询。只读、固定候选的本地BGE对照证明表达会影响排名，不能恢复历史未保存的模型query，也不能证明新LLM语义已通过。具体诊断和运行状态只引用P3，不在本层复制流水。

方案比较：仅调topK不处理表达牵引；在本地删除税种/法律词会篡改模型语义并可能丢失必要条件；新建facet Schema或增加模型轮次没有必要性证据。采用单一新任务版本，精确替换旧指令中“每个query必须保留所有税务/法律检索语境”的笼统要求，保留其他指令和同一V3输入、decoder、planner、Guard。

V6规则：

1. 先按V4/V5规则确定适用判断/查阅及最小必要域，再为每域生成一个只服务该域待证明子问题的表达；不输出新的子问题或理由字段，不增加域/query/调用。
2. 原问题的税务意图和每个逻辑domain共同约束检索范围，但不要求每域机械重复仅修饰另一子问题的税法名称、文种或背景词。不得为缺乏领域词的普通问题伪造税务意图；不把索引或Profile送给模型。
3. **若税种、法律名称或其他限定确实修饰本域所查分类/规则，它仍是必要条件，不能借聚焦删除。** 单域不得省略原问题实质主题，多域整组不能遗漏任何子问题；不能为了获得更高排名把增值税分类改成另一税种分类。该归属由模型理解，不实现逐句正则、行业特判或本地删词。
4. 每个query继续逐项保留原问显式主体/服务、日期、数字、具体比例、否定、文号、法条、纳税人及计税方法；既有税率主题整组保持和具体比例逐query保持规则不改。所有现行SemanticGuard、QuestionEgressGuard和精确decoder均保持原样；不允许通过重写本地规则接受原本非法的查询。
5. 检索词只是候选表达，不是业务分类、适用结论或已证实事实；原问题仍直接传入Summary V5。不存在第二次改写、结果失败后扩域、自动回退或重试。
6. 所有预算不变：每域1表达、最多2域、query≤1024字符、输入16384bytes、输出512tokens、8000ms、指令≤8192bytes。V6任务本身不调整排序或Evidence；后续策略V2由DR-KFLOW-022和两份下位阶段合同治理，不将旧V1配额当作V6任务的永久约束。

已新增`knowledge/rewrite_v6.py`的`KnowledgeRewriteTaskV6.definition()`：复用V5公开definition和请求工厂，只替换task_version=`6`及上述一段system_instruction；替换必须精确匹配唯一旧片段，禁止追加互相冲突的指令或覆盖旧任务。该增量当时将`KnowledgeCompositionRoot.task_definitions/build_provider`设为唯一Rewrite6/Summary5并拒绝旧Rewrite5；不添加配置开关或兼容生产旁路。历史V1～V5源资产和四批runner/manifest/gold/hash保持不变；现行生产测试迁移至6，历史合同测试继续显式使用原任务。

`TEST-KFLOW-013`：新definition与V5除version/instruction外完全相同，V3 parse_response identity与预算不变；唯一旧片段被替换，Prompt没有酒店/case/gold/文档ID特判；合法/非法JSON、敏感输入、条件丢失/补造、日期/比例/否定、unsupported/clarification/model error/timeout保持原失败关闭。当前生产根fake验证分域表达逐字到达对应keyword/vector/rerank、原问题到达Summary、调用上限、唯一注册、disabled零依赖、取消和client关闭，并包含非酒店保留问题。fake只证明合同与接线，不证明模型能正确理解条件归属或真实UAT已通过。

允许动作仅为本切片评审通过后的非live实施；不依赖待确认的Evidence配额调整，也不授权新的付费批次。回滚通过一致恢复源码及任务绑定，不能运行时切换旧任务；无数据迁移、公开DTO、索引、角色或出域范围变化。

证据限制：现行Guard能拒绝其已编码的日期、数值、比例、否定和纳税条件偏差，不足以证明任意税种、法律名称或主体同义表达的语义归属。V6不新增这些词的本地黑白名单，也不把结构合法当作语义正确。非酒店保留问题与“税种明确修饰本域”的成对UAT必须继续验证该风险；未获新授权前不得以fake或本地BGE试验关闭它。

### 8.4 类别词与数量约束分离（DR-KFLOW-023）

本节Tax Guard及旧默认的字节和行为保持；当前根新增的文号前缀边界规则仅由§8.8在该Guard之上实现，不改变本节其他约束。

直接依据为REQ-KQUALITY-001、REQ-KFLOW-002和L1 KQ-AD-013。当前数字提取把“一般纳税人”“一般计税”的“一”当成数量，导致仅将年份提前、保留全部条件的改写被误拒绝。此处纠正约束类型识别，不允许删去真实数字、弱化条件保护或由本地代替模型生成计划。

最小方案比较：仅要求Prompt维持原词序会把正常表达限制转移给模型，无法可靠修复；数字改为集合比较会丢失次数/顺序并可能掩盖数值对应关系，不采用；新增全量语义Schema或中文分析器范围过大。采用新内部`TaxQuestionSemanticGuard`，只处理已经有独立保护的四个代码绑定完整短语：`一般纳税人`、`小规模纳税人`、`一般计税`、`简易计税`。不按具体UAT问题、文档ID或酒店关键词特判。

1. 已新增`knowledge/tax_question_semantics.py`，定义四短语只读tuple和继承旧Guard的`TaxQuestionSemanticGuard.extract(original_question: str) -> ProtectedConstraintSet`。首先在原NFC文本执行旧extract，原类型、控制字符、128字符约束token及32/64约束数限制仍生效；候选1024字符限制由原validate_candidate保留，原问题总长仍由入口控制。
2. 只在用于提取numbers的局部副本中把完整短语替换为等长空格，防止两侧数值被拼接；禁止删单独“一”、泛化后缀或任意词典/配置。重用旧extract取得该副本的numbers；原始返回中的dates、document_numbers、article_refs和negations必须来自未替换原文。全部约束仍保持原顺序、次数及精确值；不作集合化、排序、归一比例或丢弃单位。
3. 类别词没有从原问题、模型输入或输出查询删除。Planner逐query对四个短语继续执行与原问相同的存在性检查；任何遗漏、新增或替换整份计划失败。Guard与Planner共享这一静态tuple，不能各自扩充或由请求/环境选择。类别词检查与新数字提取必须成对使用，不能用新Guard单独证明完整语义等价。
4. 已修改`KnowledgeSemanticPlanner.__init__`增加内部可选`semantic_guard: QuestionSemanticGuard | None = None`；默认仍旧Guard，历史调用方无需迁移。当前bootstrap显式传新Guard；disabled无实例/下游资源。只有内部代码可绑定，不新增公共DTO、模型字段、配置或选择开关。旧`question_semantics.py`、Rewrite/Summary/Prompt、decoder、历史runner和冻结资产逐字节不变。
5. 继承旧validate_candidate，真正数字顺序、日期、文号、法条及否定检查保持；Planner另有比例完整值/单位与逐域类别检查，两者不可移除。错误继续knowledge.rewrite_failure，下游和Summary0，无fallback，不新增外部错误枚举。原问题仍为Summary边界，无额外模型或业务调用。
6. 这是有限词素误分类修复，不是任意语义等价证明；多组真实数字重排、其他汉字词素/否定词歧义仍按既有失败关闭处理，记录风险而不顺带建设规则引擎。真实模型是否输出了误拒绝表达未知，不以合成反例改判历史UAT。

实现切片依赖：本节设计评审→新Guard/Planner成对绑定→单元/当前根fake/历史/类型/Spring回归→代码复评。回滚单位为当前根Guard绑定及配对实现，旧Guard仍可追溯；默认禁用Knowledge也可隔离，禁止请求内切换或live补跑。本节经三轮内审及分离编辑阶段的只读L2/跨层复评通过，允许本切片非live实施；审批和实施证据归P3。

### 8.5 必要证据计划（DR-KFLOW-024；已实施，真实效果待验证）

依据KQ-AD-018，新增`knowledge/rewrite_v7.py::KnowledgeRewriteTaskV7.definition()`，不修改旧任务，不复用V3 parser来宽松接受新字段。task_id仍knowledge_rewrite、version=`7`，同一ModelGateway单次调用；输入仍安全原问和启用域安全目录。新exact JSON为：

```json
{"outcome":"search","question_kind":"applicability","queries":[{"domain_id":"tax.policy","query":"保留原问限制的政策检索表达"},{"domain_id":"tax.law","query":"保留原问限制的法律检索表达"}],"requirements":[{"requirement_id":"r1","domain_id":"tax.policy","kind":"subject_scope","focus":"所问服务的分类依据"},{"requirement_id":"r2","domain_id":"tax.law","kind":"rule","focus":"该问题所需的适用规则"},{"requirement_id":"r3","domain_id":"tax.law","kind":"temporal_scope","focus":"规则在所问期间的施行依据"}],"missing_conditions":[]}
```

示例只展示形状，不是固定双域计划、查询词或在线gold；实际问题的语义与域由模型一次确定。

| 字段/对象 | 精确合同及所有者 |
|---|---|
| outcome | search / clarification_required / unsupported；原三种语义不变 |
| question_kind | search必为lookup或applicability；其余两种终态必须是none，不允许null |
| queries | search为1～2个唯一启用域、NFC非空query≤1024；沿用现行逐query数值/日期/否定/类别及整组主题保护；非search为空 |
| requirements | search为1～4个exact对象；非search为空；顺序ID必须为r1..rN、不缺号、不重复；domain必须在queries中且每个query域至少有一项需求 |
| kind | subject_scope / rule / temporal_scope / constraint；lookup按问题选择1～4项，不强制适用性三项；applicability必须各有且仅有一个subject_scope、rule、temporal_scope，余下一项可为constraint |
| focus | NFC非空文本≤192 code points；描述待查证的问题，不得输出税率、类别归属等答案；不是SQL、URL、索引、文档ID或调用指令 |
| missing_conditions | search/unsupported为空；clarification_required为原subject/taxpayer_type/calculation_method/applicable_period中的1～3个唯一值 |

所有层次拒绝unknown/duplicate key、bool冒充整数、null、coercion、非有限值、尾随JSON。新任务输出上限1536tokens，输入16384bytes、指令8192bytes、任务8秒不变；超限/截断按非法输出失败，不追加模型请求。模型只生成需求，不生成引文或已证事实。applicability的三角色是回答责任的机械完整性，不是本地识别问题类型；对类型误判、需求错误及自然语言蕴含仍必须进行真实UAT。

安全及校验顺序：原问QuestionEgressGuard→模型一次→exact decode→既有query guards→全部focus的QuestionEgressGuard→需求/域关联与版本冻结。focus可省略与该证明无关的原问条件，但禁止新增原问没有的数字/日期/比例/文号/法条/否定及四类税务条件；以现行保护token的计数子集校验，不用focus改写检索query。某个focus不安全或需求非法使整份计划失败，search/embedding/rerank/summary全0；不丢弃非法项后执行子集。缺少决定性用户条件仍用已有clarification，不为补齐三角色捏造期间或主体。未知必要域不能用当前可用域替代。

`IMPL-KFLOW-012`批准且已实施的触点（non-live/真实效果证明范围由P3/UAT_01治理）：

- `knowledge/contracts.py`新增frozen/slots `KnowledgeEvidenceRequirement(requirement_id, domain_id, kind, focus)`及有限枚举；`RewriteResult`、`KnowledgeRetrievalPlan`、`KnowledgeEvidenceInput`追加默认空tuple的`evidence_requirements`及默认None的`question_kind`。内部question_kind只用lookup/applicability枚举，非search不建立检索计划。旧实例保持空/None；quality-v3成功检索必须有kind及非空需求，旧quality拒绝非空需求或kind。Plan/Evidence消费边界可据此复核三角色，不能在第一次解码后丢失目的信息。
- `rewrite_v7.py`复用现有`KnowledgeSemanticPlanInput`，新增继承`KnowledgeSemanticPlanOutput`的frozen/slots输出子类型（question_kind及evidence_requirements），新decoder只解新五字段合同；非search的外部none在可信decoder中映射内部None。definition保持Planner既有泛型基类签名，返回子类型；Planner必须检查V7输出的实际子类型及版本，不用cast或getattr默认空绕过。复用既有公开请求工厂取得安全域目录及输入JSON，再一次性替换为新完整指令、版本与输出预算，不导入私有helper。原有V1/V2构造默认、旧任务对象及其parser保持原语义。
- `planning.py::KnowledgeRetrievalPlanBuilder.build`在I/O前校验域、kind、需求与代码版本，并原样传递kind/tuple；`capability.py::KnowledgeQueryCapability.handle`把相同两项传至EvidenceInput，不能重建或从摘要反推。Stage Protocol的三个方法签名保持不变；不改公共Core/HTTP/Java/ES DTO。核心结构检查集中于已实现的`knowledge/evidence_requirements.py`的纯函数，各边界复用同一合同，不能复制四套角色规则。
- 本节引入的`bootstrap.KnowledgeCompositionRoot`绑定为Rewrite7/Summary6/quality-v3；后续由§8.6/8.7升级为8/7，当前由§8.9升级为9/7，相同需求合同、quality-v3及limits不变。版本由代码选择，不提供环境热切换；disabled不创建需求、任务或client。final_candidates至少4，保持现有≥2×enabled域数及最大20。任务工厂在资源创建前核对版本/ID/输入类型，Provider再次核对；数量配置同样在client创建前拒绝。

V7输出子类型、outcome对应的kind/需求形状及配对版本校验必须先于clarification_required或unsupported提前返回；即使fake或内部Provider绕过decoder，也不能把非法终态当作正常拒绝。合法unsupported保持现行SUCCESS rewrite/空域的内部约定，question_kind=None、需求空，Capability在no_matching_domain终态结束，不建立检索计划；clarification保持现行有限reason映射。

数据仅驻留同请求；不得通过query编码、ContextVar、全局registry、持久化或额外Capability传递。需求ID不是跨请求引用。观测只消费安全投影：planning.py在record_plan前为V3显式投影原有计划字段，省略question_kind/evidence_requirements，不把新dataclass整体交给通用_to_plain；无需扩展公开观测Schema。Summary观测保留当前白名单，不加入requirements；observation.py::knowledge_http_request_view对/rerank的既有query键统一返回固定隐藏标记，防止focus通过下游请求展示泄漏。不引入版本侧信道或修改RerankPort/HTTP DTO。此调整只收紧观测内容，不改变实际BGE请求及旧任务输入，现行观测测试需覆盖Plan/Summary/下游三处均不含focus，历史运行观测字节不改。

`TEST-KFLOW-016`：新增V7任务精确JSON/大小/重复键矩阵；search/lookup/applicability/clarification/unsupported，漏三角色、重复/乱序ID、未知/未查询域、无需求的查询域、超4项、focus敏感/新增受保护token均零检索；同一域多个角色合法、资料查阅不被三角色强迫；既有query条件保护不退化。生产根fake验证tuple贯穿、版本错配/旧形状拒绝、disabled、单动作、无fallback、取消/关闭、非酒店表达和历史源hash。新增测试路径为`tests/contract/knowledge/test_rewrite_task_v7.py`、`tests/unit/knowledge/test_evidence_requirements.py`、`tests/integration/knowledge/test_requirement_plan_production.py`。`VAL-KFLOW-007`要求这些测试、strict mypy、compileall、现行Spring→Runtime及历史回归实际通过；fake不证明LLM规划正确。

本节的目标合同与§8.1～8.4历史Prompt增量区分：此前“不增加intent/需求Schema”的取舍只适用于当时局部修复。此次有跨阶段丢失证据，不通过隐式prompt约定代替类型合同。实施需先完成本增量评审，整套新绑定可禁用或按一致源码回退，不能请求内fallback；新真实批次不在本节授权范围。

### 8.6 澄清优先规则的完整继承（DR-KFLOW-025）

依据`REQ-KQUALITY-003`、`KQ-AD-015`及§8.1/DR-KFLOW-019。只读代码比较确认V4～V6保留“先判意图及必要条件、不把不完整适用判断降为查阅”的完整规则；V7重建指令时仅剩简短的缺条件句，并用“确定条件下的具体适用判断”描述applicability。恢复遗漏是实现合同纠偏，不新增本地意图分类器。有限运行证据及其推断边界见P3；不能从未保存的模型输出反推其实际question_kind或推理。

方案取舍：扩大topK不影响发生于检索前的终态选择；本地按行业/词面拒绝或增加第二模型校验会扩大职责与成本；只追加一句与旧描述并存仍有歧义。采用新`KnowledgeRewriteTaskV8`，在V7公开请求工厂上**精确替换唯一的意图分类段**，其余指令保持原文；替换目标缺失或重复必须立即拒绝构造。不得修改V7或将V4三字段输出范例追加到V8五字段Schema中。

决策顺序（不输出推理过程）：

1. 先区分用户是要为服务、交易或活动选择适用结果，还是仅查阅定义、分类、法条、一般规则或比较。不要求出现企业/个人名称，不由“适用”等单词决定意图。
2. 对适用判断，先核对结果是否取决于未提供的主体、纳税人类型、计税方法或期间。只列实际必要且可由既有枚举表达的缺失条件；缺条件时直接`clarification_required`，question_kind=none，queries/requirements为空，不默认一般纳税人、一般计税或当前期间。不得把不完整适用判断降为lookup来生成答案。
3. 明确资料查阅且不要求选择单一适用结果时可search/lookup，不机械要求全部四类条件。目的含糊且直接回答可能被理解为单一适用结果时，优先澄清实际必要条件；没有可表达条件又不能形成可靠计划则unsupported，不伪造缺失项。
4. 只有允许search后才决定一次性的必要域、queries及requirements；applicability仍必须三证明角色。§8.5的字段、类型、上限、每域表达、focus保护、三终态与失败优先级全部不变。

`IMPL-KFLOW-013`（已实施）：新增`knowledge/rewrite_v8.py::KnowledgeRewriteTaskV8.definition()`，复用V7公开definition、输入/输出类型及**同一parse_response对象**，只改task_version和build_request中的system_instruction/version；1536tokens、16384输入bytes、8192指令bytes、8秒及单次规划不变。`bootstrap.KnowledgeCompositionRoot.task_definitions/_validate_tasks`唯一绑定8/6/v3；`KnowledgeSemanticPlanner`仅把已确认兼容的7和8都识别为内部需求合同，拒绝其他task与quality错配。允许7仅为显式历史调用，当前生产根仍拒绝7；无环境版本开关、请求内fallback或额外任务。

当前生产测试迁移到8，保留全部旧断言意图；旧V7任务及已消费runner、case/gold、七项运行文件不变。历史源码按冻结Git提交校验，不要求当前组合根永远绑定旧任务。旧run-08测试若依赖当前测试helper，仅在该测试作用域读取其冻结Git helper和根，不修改断言或runner；新增隔离恢复测试证明不影响当前根。Spring fake harness应使用8请求并继续验证实际生产对象图；不对旧run执行器补写新版本接缝。回滚只能禁用Knowledge，或一致回退已版本化源码/绑定，不能单请求回退。没有公开DTO、索引、读取授权、出域、状态、持久化或Java变更。

`TEST-KFLOW-017`：V8与V7除版本/指令外definition/request完全相同，decoder identity及V7合法/非法完整矩阵保持；指令精确覆盖上述四步且不含行业/case/gold特判，唯一替换、大小限制及旧源码hash；当前根8/6/v3、拒绝7/未知版本、disabled惰性；真实生产根fake覆盖澄清/unsupported零检索、lookup及条件充分applicability、非法计划、模型失败/超时、敏感输入、授权/出域、单动作、并发和取消。合成Prompt/结构测试只证明指令恢复与接线，不能证明LLM意图正确。

`VAL-KFLOW-008`：新V8合同测试、当前需求Runtime集成、Spring→Runtime Knowledge E2E、历史run-08/hash测试、正式隔离全量non-live、strict mypy、compileall和diff检查。实现入口仅需本切片设计评审通过；真实UAT仍需独立未消费授权，不创建run-09、不读取Key、不新建live资产。即使全部non-live通过，缺条件真实语义及阶段B整体质量仍未关闭。

### 8.7 摘要指令增量的成对接线（DR-KFLOW-026；已实施）

L2_01_02 §9.6治理Summary7的分类前提证明语义；本层不重复其Prompt。`bootstrap.KnowledgeCompositionRoot.task_definitions/_validate_tasks`只注册Rewrite8/Summary7/quality-v3，拒绝旧Summary6/未知版本并在client创建前失败。disabled不创建任务或依赖；不修改Rewrite8的factory/parser、需求形状、每域query、原问约束或任何检索配置。

REQ-KFLOW-004→DR-KFLOW-026→IMPL-KFLOW-014（上述两个现有方法）→TEST-KFLOW-018（当前root配对/拒绝旧版/disabled、Spring→Runtime、历史fixture隔离）→VAL-KFLOW-009（定向合同、实际对象图、strict mypy、全量non-live及原UAT）。旧runner测试只在特定测试范围读取冻结Git根及helper，不更新其冻结断言或把历史运行换成当前生产。回滚为禁用或成对源码回退，无请求内切换。

三轮内审与跨层只读设计复评随L2_01_02 §9.6完成：职责不变、当前与目标分离、旧版本字节保护、单动作/生命周期及预算不回退，S0/S1/未处理S2=0，允许此两方法和直接测试的最小实施，不代表真实效果已达标。

### 8.8 文号本体与查阅前缀分离（DR-KFLOW-027；已实施并完成non-live验证）

依据REQ-KFLOW-002/DR-KFLOW-003及L1 KQ-AD-013：保护用户真正的约束，不要求模型保留与文号无关的查阅措辞。已复现旧Guard将“请分别查找财税〔2011〕100号”整体提取为文号，使合法focus“财税〔2011〕100号的软件产品定义”被拒为新增约束。这是词法边界缺陷，不是模型错误，也不证明更宽泛的改写均安全。

方案比较：Prompt要求逐字保留查阅前缀会把错误词法当成模型合同，不采用；只比年份/编号或允许任意后缀匹配会丢失机关，禁止；新增通用NLP依赖和全量中文规则引擎超出最小修复。采用当前根专用Guard，仅在旧文号token开头识别一次有限查阅前缀，剩余文号保持原字节和顺序。

1. 当前实现为`knowledge/document_reference_semantics.py::DocumentReferenceSemanticGuard(TaxQuestionSemanticGuard)`。`extract(original_question: str) -> ProtectedConstraintSet`先执行原Tax Guard全部校验，再只替换document_numbers；numbers/dates/article_refs/negations及四类别独立检查不变。原问、模型query/focus、Prompt、检索请求和Summary输入均不重写。
2. 可分离前缀语法固定为：可选礼貌词`请/请帮我/帮我/麻烦/麻烦帮我`，可选`分别/同时`，必须接一个`查找/查询/检索/查阅/查看/对比/比较`。只匹配token起始处一次，不循环删除、不允许任意中间文本；余部必须为1～24个汉字或ASCII字母的非空机关前缀，加旧式`〔YYYY〕N号`或`[YYYY]N号`（YYYY为4位ASCII数字，N为1～12位ASCII数字）。只剥离匹配的请求措辞，不剥离地域或机关，不把不同括号、简称、年份、编号或前导零归一。未识别的表达保持旧token，不猜测。`苏财税`不能变成`财税`；`请不要查找`不能当成`请查找`；重复查阅动词最多去掉第一组，不能使重复前缀与裸文号等价。若真实机关名称恰以前述动词开头，词法有歧义，不能声称本规则证明其法律身份；该边界需要语料证据驱动的后续处理，而非自动扩张规范化。
3. 该有限语法只解释明确的查阅措辞，不选择domain/action、生成filter或判断法律事实；不读取gold、case ID、文档ID、在线索引或配置。复合文号识别及公告式年份表达保持现行边界，本节不以局部修复声称已覆盖所有自然语言。
4. query仍按全部受保护组精确值/顺序/次数比较；focus仍按原问token计数子集校验。两者必须消费同一Guard实例。删除、替换机关/年份/编号，新增或重复focus约束仍拒绝；拒绝整份计划，公开映射继续`knowledge.rewrite_failure`，search/embedding/rerank/Summary全部0。实际数量、日期、否定条件不因前缀分离而移除。
5. 当前`bootstrap.KnowledgeCompositionRoot.build_provider`显式绑定新Guard；默认Planner、旧`question_semantics.py`和`tax_question_semantics.py`保持字节不变，历史构造不迁移。disabled不实例化Guard或HTTP资源；没有共享可变状态、新依赖、环境开关或额外请求。按当前根绑定一致源码回滚，禁止请求内fallback。

`IMPL-KFLOW-015`为上述新Guard和当前根一处显式注入；`TEST-KFLOW-019`为`tests/unit/knowledge/test_document_reference_semantics.py`及`tests/integration/knowledge/test_document_reference_guard_production.py`。覆盖不同查阅词、裸文号、未知机关/地区前缀、机关更换、年号/编号/括号、真实数字/否定、重复约束、非法/超限原问、旧Guard不变、当前8/7/v3根成功、query/focus任一拒绝零下游、原问/query不被改写、并发隔离、disabled与client关闭。`VAL-KFLOW-010`已完成定向测试、历史哈希、当前根/Spring和正式non-live回归、strict mypy及compileall，命令与计数由P3 §20.64.1管理。真实Rewrite行为和整体召回改善仍需单独实测，不用本节fake改判既有失败。

### 8.9 需求声明驱动的分域条件校验（DR-KFLOW-028；已实施，真实效果待验证）

依据REQ-KFLOW-002、REQ-KQUALITY-001及KQ-AD-013/018，整个计划必须保留原问题条件，但不要求政策文号和独立法律法条同时复制进两个域的query。原问不改写；归属由同一次模型在既有`requirements.focus/domain_id`中表达，本地不拆句、不推断行业、不生成需求或查询。

| 方案 | 主要影响 | 决策 |
|---|---|---|
| 仅Prompt或放大topK | 不能修复检索前的逐query误拒；增加窗口无作用 | 不采用 |
| 只比较全体query约束并集 | 可能把日期/纳税人条件挪到无关域，集合还会丢重复次数 | 禁止 |
| 新增独立scope字段或条件ID目录 | 可显式声明但重复已有需求所有权，新增模型Schema/迁移，仍不能证明语义归属 | 当前不采用 |
| 复用既有需求声明并保守保留未分配条件 | 不新增wire字段/调用；声明错误仍需语义UAT，能核验每域query与声明一致 | 推荐最小方案 |

**输入及版本。** 新`KnowledgeRewriteTaskV9`复用V7精确五字段decoder与V8澄清优先意图规则，只替换条件归属指令。search时要求focus写出该需求相关的原问受保护条件；全局条件须在每个受影响域至少一个focus中明确。不得把税率数字、日期或纳税人类型补成用户事实。数量、1536输出tokens、8000ms、指令8192bytes、输入16384bytes、两域/四需求及每域query1024字符上限不变。非search仍先校验完整Schema再返回原终态，不创建需求或检索。

**校验顺序。** 原问Guard及敏感输入检查 → 模型/精确decoder → 需求形状/域白名单 → 所有focus的敏感性及原问约束子集检查 → 请求内分域约束计算 → query安全/范围校验 → 一次性不可变计划。任一focus失败时不得先信任其归属；所有query通过前不调用search、embedding、rerank或Summary。

**确定性计算。** 对现有五组受保护token和完整比例及单位token，以原问有序token的计数为`O`；每域所有focus计数的逐token最大值为`M_d`（同域多个证明角色重复同一条件不累计）。未分配计数`G=max(O-sum(M_d),0)`，该全局余量加入每个域；该域必须保留的计数为`E_d=M_d+G`。按原问顺序选取`E_d`数量构成期望有序token，query必须精确匹配，不得新增、重复增加、遗漏或换值。focus每组仍不得超过O。单域自然退化为全部原问约束；没有任何focus声明的条件也保留于全部域。重复原问值分属两个域时按计数分配，不能用去重集合掩盖遗漏。

四类纳税人/计税方法词继续按是否出现判断，而不新增类别词词序/次数限制：本域期望为本域focus中的类别集合，加原问中在任何focus均未声明的类别；query类别集合须精确相同。有具体比例时，税率/征收率主题也按此集合规则归属，不能把已有的完整比例或单位改成另一含义；无具体比例时继续原有税率/征收率主题整组保持规则。focus不得新增原问不存在的税率主题。语义上具体比例对应哪个税种/主题仍需模型及UAT判断，不能以集合验证代替。

**语义边界。** 上述计算证明“原问约束有覆盖、query符合本域声明”，不证明声明符合任意中文语义。模型把全局日期只写入某一域focus、把纳税人条件错误分给另一域，即使结构满足也可能语义错误；不得把这种情况写成validator必然能发现。Prompt、原问题贯穿Summary和预先人工核对的语义UAT共同约束；若真实语义未通过，保持专项UAT未完成，不能靠词面分支、删除case或继续付费试错改判。共指/重复值的归属存在歧义时，只有能用既有missing_conditions准确表达的缺失条件才返回clarification，否则按V8既有意图规则返回unsupported；不能新增枚举或伪造缺失条件。局部规则无法识别的歧义属于明示剩余风险。

**失败及观测。** 原有`knowledge.rewrite_failure`公开映射保持不变；可在已有内部`RewriteStageResult.reason_code`保留有限`query_scope_mismatch`，不包含token、原问、focus或模型响应，不增加HTTP/observations字段。敏感拒绝、模型异常/超时、未知域和其他失败优先级不变；禁止丢掉问题条件继续检索，也不进行本地fallback。

**实施、兼容和回滚。** `IMPL-KFLOW-016`新增`knowledge/query_constraint_scope.py`请求内纯校验及`rewrite_v9.py`；现有`semantic_planner.py`仅对版本9采用此校验，版本7/8保持原顺序/行为；当前`bootstrap`在本增量评审和定向验证后唯一绑定9/7/v3。旧Guard、V1～V8任务/decoder、Summary、检索配置、Profile/索引/alias、公共DTO和历史资产字节不改。没有共享可变状态、新依赖、配置中心或额外调用。回滚为一致源码恢复8/7/v3或disabled，不支持请求内版本降级。

`TEST-KFLOW-020`：scope纯函数及当前根fake覆盖独立文号/法条分域、单域保持、全局日期/否定/纳税人/比例、局部条件、多角色重复、原问重复、未分配条件、query挪用/增删/变序、focus新增/敏感/超限、非法/clarification/unsupported/模型超时零下游、请求隔离、原问Summary和client关闭；另以显式反例记录“错误focus归属可结构通过”而非误称安全证明。V9与V8除版本/指令外request一致，decoder identity及旧任务矩阵不变；当前根拒绝8/未知版，冻结runner只通过隔离历史fixture使用旧根，不改历史断言。

`VAL-KFLOW-011`：新增unit/contract/current-root集成、现行Spring fake、历史hash和scope相关回归、strict mypy、compileall、正式non-live全量。UAT_01专项语义/真实证据另行治理，本设计不新增真实运行或预算，不重复已消费批次。阶段B继续以代表集准确率及必要覆盖验收；资料缺失不要求住宿单题成功，不借此放过资料充分场景的实际缺陷。

### 8.10 同预算原问关键词保留（DR-KFLOW-029；设计增量，尚未实施）

依据REQ-KQUALITY-001/002及L1 KQ-AD-014：现有SemanticPlanner继续安全检查、一次Rewrite9、精确解码及§8.9分域条件校验。只有合法search才建立计划；模型失败、非法计划、clarification或unsupported不能因有原问而进入检索。原问不是本地生成的业务计划，也不用于扩域。

`KnowledgeRetrievalPlanBuilder`建议增加代码级关键字参数`preserve_original_keyword: bool=False`。默认保持既有显式旧调用语义；建议修改当前`main.py`经`KnowledgeCompositionRoot.build_provider`显式传true。不是环境配置或模型字段，不允许请求级选择；参数必须为实际bool。true只适用于quality-v3合法MODEL rewrite，不能附着于legacy/旧quality/denied计划。

在网络前复用`QuestionEgressGuard.evaluate(rewrite.original_question)`获得ALLOWED的`minimized_question`，只做现有NFC及空白标准化，不抽词、截断、识别文号或生成子问。生产Capability继续验证original_question与同请求输入一致。安全拒绝、空值、类型或版本非法时计划构造失败且不产生检索调用；不以“原问不可用”回退安全已拒绝的问题。

- 安全规范化原问长度≤`settings.max_retrieval_query_chars`（现有配置可收紧、代码最大1024）：每个已选域keyword使用同一原问，vector使用该域已校验query。
- 原问安全但长度超过该配置值（用户输入仍遵循现有4096上限）：两路预先固定用该域已校验query，保持长问题兼容；不截断原问或扩大HTTP上限，不因检索结果改变此选择。
- queries、requirements、question_kind、域顺序、每路20及总4路、最多2次embedding/4次需求rerank、截止时间均不变。不同域仍独立授权；原问包含其他域条件可能引入噪声，但不得据此客户端增删条件或跨域补查。

`IMPL-KFLOW-017`建议修改：`knowledge/contracts.py::KnowledgeRetrievalPlan`末尾追加frozen/slots字段`original_keyword_query: str | None = None`。非None只由上述Builder从安全同请求原问赋值，用于显式表达keyword来源；它不是模型输出、HTTP字段、能力参数或认证凭据。长问题及默认旧调用保持None。Builder按路径填入真实query_text，观测继续仅投影原有items/domain/config/quality，不把新增字段或整个dataclass自动输出；没有原问的副本进入日志/evidence。既有验证台可看到已经安全处理的真实检索文本，不额外暴露内部字段。

Stage对该字段执行DR-KRET-037消费校验；不删除旧同query校验。目标为main显式启用而旧Builder/Provider调用默认false，保护历史重放；冻结资产仍从冻结提交读取，不能因默认兼容就重跑旧批次。无需新Rewrite/Summary task或Prompt版本，因为模型输入、输出、decoder和指令均不变；检索策略身份由当前源码提交及内部计划字段追踪。disabled不建Provider/client。回滚是禁用Knowledge或一致源码回退/显式装配恢复，不是请求内fallback。

`TEST-KFLOW-021`→建议新增`tests/unit/knowledge/test_original_keyword_planning.py`，验证两域原问keyword/各域vector、同request、NFC/空白、1024边界、配置收紧、长原问不截断、unsafe/model failure/unsupported零调用、旧默认及任务不变；当前main对象图测试证明显式启用、disabled惰性、观测无内部字段和并发隔离。`VAL-KFLOW-012`为上述测试、现有QueryPlan/Knowledge/Core/Business回归、Spring E2E、strict mypy和compileall；真实语义效果仍单独UAT。此增量不调整公共接口、安全策略、索引或排序，评审完成后才允许代码实施。

## 9. 检索计划与核心流程

### 9.1 计划

对每个已批准域按目录路径生成keyword/vector两项；limit≤20，稳定顺序为目录→路径。DR-KFLOW-029目标模式按§8.10绑定安全原问keyword及分域改写vector；原问超长和历史默认调用仍为同域两路同query。原问题在请求内保留用于最终语义边界，不从改写重建；新增计划字段仅表示可直接检索的安全原问。域集合固定后任何路径结果不得追加域、路径或改变表达。

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

`DR-KFLOW-016`：新内部 `PlannedDomainQuery` 与 RewriteResult 的可选版本化plan字段由V3 decoder产生；默认空值仅供旧显式测试/历史装配兼容。当前生产Capability使用V9生成的§8.5五字段需求计划，此前V3三字段只供历史版本；字段缺失时不能调用旧Selector。`unsupported`仍映射既有no_matching_domain；clarification是内部阶段终态，不新增公开CapabilityStatus。

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
4. 按§8.5/8.6/8.9及L2_01_02 §9.6的当前需求合同创建唯一Rewrite/Summary definitions；当前已实施9/7/v3。旧任务不同时注册、不作自动后备。§8.8的Guard保持不变。
5. 所有纯配置、目录、策略和任务校验完成后，才为三个固定 origin 分别创建 bounded HTTP client/transport并构建 Retrieval/Provider。
6. 把 `KnowledgeCapabilityProvider` 作为 `BusinessQueryRuntimeCompositionRoot.additional_providers` 追加到同一 Runtime。
7. 顶层 lifecycle 同时拥有 Business clients、Knowledge clients 和 model；关闭按资源逐项尝试，保留首个异常但仍释放其余资源。

不得把部分构建对象暴露为 ready Runtime。通过把所有可预见校验前置到 client 创建之前，避免为同步启动路径另建异步“半成品清理”协议；已成功装配的 Runtime 必须完整关闭 owned resources。

授权上下文评分增量：按L2_01_01 DR-KRET-034，main在第5步为同一Retrieval Factory显式绑定`authorized-body-first-metadata-v1`；该增量实施时保持8/6/v3计划/任务，只改变本地BGE评分表示；当前任务绑定见§8.9，Evidence原文及次数不变。Factory默认raw仅承担旧显式调用兼容，不是当前根后备；无环境/请求版本开关，disabled不构造它。该接线已实施并通过non-live验证，证据由P3管理；后续运行快照必须包含新表示版本及源码SHA，不继承旧UAT证明。

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
| `IMPL-KFLOW-003` | 已有`knowledge/question_semantics.py`旧Guard不改；DR-KFLOW-023已新增`knowledge/tax_question_semantics.py`类别词数字分离 |
| `IMPL-KFLOW-004` | 已有`knowledge/rewrite_v3.py`（精确合同）、`knowledge/semantic_planner.py`、V4/V5/V6任务；DR-KFLOW-023已增加Planner内部Guard注入及共享类别tuple，旧默认与任务不变 |
| `IMPL-KFLOW-005` | `agent-runtime/src/agent_runtime/knowledge/catalog.py`、`domain_selection.py` |
| `IMPL-KFLOW-006` | `agent-runtime/src/agent_runtime/knowledge/planning.py`：`KnowledgeRetrievalPlanBuilder.build` |
| `IMPL-KFLOW-007` | `agent-runtime/src/agent_runtime/knowledge/contracts.py`、`agent-runtime/src/agent_runtime/knowledge/context.py` |
| `IMPL-KFLOW-008` | `agent-runtime/src/agent_runtime/knowledge/settings.py`、`agent-runtime/src/agent_runtime/bootstrap.py` 的 Knowledge composition |
| `IMPL-KFLOW-009` | `agent-runtime/src/agent_runtime/main.py`：按开关构建 Knowledge tasks/retrieval/provider 并追加到 Business Runtime |
| `IMPL-KFLOW-010` | `agent-runtime/src/agent_runtime/bootstrap.py`：顶层 owned resource 生命周期与 disabled 零依赖装配 |
| `IMPL-KFLOW-011` | `agent-runtime` 当前策略目录加载与 `serviceCenter/knowledge-runtime-binding.v1.json`：只读发布绑定；历史目录继续独立可校验 |
| `IMPL-KFLOW-012` | §8.5批准的需求类型、V7任务、Planner/Capability透传、当前根成对绑定及安全观测目标；部分实施进度由P3治理；不改历史任务与公开合同 |
| `IMPL-KFLOW-013` | §8.6已实施V8指令恢复、当前根单绑定和相同内部合同版本识别；不新增decoder、语义分类器或模型调用 |
| `IMPL-KFLOW-014` | §8.7当前根绑定Summary7，Stage历史合同兼容6/7，Rewrite8不变 |
| `IMPL-KFLOW-015` | §8.8已实现document_reference_semantics.py及bootstrap显式注入；原两个Guard不改 |
| `IMPL-KFLOW-016` | §8.9已新增query_constraint_scope.py/rewrite_v9.py，实现semantic_planner的版本9分支及bootstrap唯一绑定；旧任务/Guard/公共合同不改 |

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
| `TEST-KFLOW-012` | DR-KFLOW-020：V5仅改指令/版本、V3 exact合同等价、该历史版本唯一V5与旧版本拒绝、单域/双域fake及非酒店保留表达；真实语义另行UAT，不修改历史gold |
| `TEST-KFLOW-013` | DR-KFLOW-021：V6指令局部替换/同一decoder与预算、每域聚焦及显式条件不丢失、原问Summary、当前单绑定与旧版本拒绝、历史隔离；合同/生产fake/防回退，真实语义不由fake证明 |
| `TEST-KFLOW-014` | DR-KFLOW-022：quality-v2从当前根透传、错误版本拒绝、V2/limits配对、历史V1默认、disabled及单动作防回退 |
| `TEST-KFLOW-015` | DR-KFLOW-023：已新增`test_tax_question_semantics.py`及`test_tax_semantic_guard_production.py`；类别/年份变序成功、类别丢失新增、实际数字/比例/日期/文号/法条/否定变化拒绝、重复数量和上限、旧默认和历史哈希、当前根唯一绑定/零调用/资源关闭 |
| `TEST-KFLOW-016` | §8.5 V7精确合同、终态前校验、同域多角色、语义保护、需求透传、版本矩阵与三处观测不展示focus；已实现测试路径见该节及当前根test_requirement_runtime_composition.py |
| `TEST-KFLOW-017` | §8.6 V8指令恢复、五字段decoder identity/矩阵、当前根/旧版拒绝、澄清零下游及历史作用域恢复；VAL-KFLOW-008不替代真实UAT |
| `TEST-KFLOW-018` | §8.7版本配对/拒绝旧版、disabled、当前Spring根和冻结历史fixture隔离 |
| `TEST-KFLOW-019` | §8.8文号正反例、旧Guard、当前生产query/focus、整份拒绝零下游及生命周期；新增两测试文件 |
| `TEST-KFLOW-020` | §8.9分域/全局计数和顺序、声明与query一致、语义限制反例、V9合同/current root和历史兼容 |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-KFLOW-001` | Provider/Capability 契约和单动作调用计数测试通过 |
| `VAL-KFLOW-002` | 当前Rewrite精确合同、Guard、敏感零调用和无fallback；V5增量单独执行，不继承V4测试结论；旧任务历史合同不变 |
| `VAL-KFLOW-003` | 两域目录、计划、配置未知 key/越界启动失败测试通过 |
| `VAL-KFLOW-004` | Knowledge 非 live 回归、strict mypy、compileall、组合根 Summary V5 单注册及 V1～V4 历史不可变通过 |
| `VAL-KFLOW-005` | 当前启动入口 disabled 零依赖、enabled 唯一对象图和 Spring→Runtime 功能 UAT 通过 |
| `VAL-KFLOW-006` | 阶段 A 发布绑定可由现有在线链路只读消费，且不改变域选择、Rewrite、排序、错误或 fallback 行为 |
| `VAL-KFLOW-007` | §8.5任务/计划/current root fake、strict mypy、compileall、历史hash及Spring回归；新真实语义另行验证 |
| `VAL-KFLOW-008` | §8.6 V8合同/当前根/Spring、历史隔离与hash、正式全量non-live、strict mypy、compileall；不产生或证明真实模型调用 |
| `VAL-KFLOW-009` | §8.7当前根/合同/Spring/类型/全量与原专项UAT分别给出实际证据 |
| `VAL-KFLOW-010` | §8.8定向/历史/当前根及Spring、正式隔离non-live、strict mypy、compileall；不证明真实改写或召回精度 |
| `VAL-KFLOW-011` | §8.9纯校验/合同/当前根/Spring/历史与正式non-live、类型检查；真实语义仍由UAT独立判断 |

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
| 是否可作为实现依据 | 是，DR-KFLOW-028三轮内审及分离只读设计复评通过，已实施当前根9/7/v3；核心场景及真实UAT未通过 |
| 当前允许实施范围 | §8.9纯校验、V9指令、Planner/current root及直接测试；不改已消费运行或Profile/index/policy、权限、Summary、检索或阈值 |
| 当前禁止动作 | 未配置新域/物理资源选择、公共契约变化、未按UAT冻结或超预算的真实模型调用、请求触发索引写入或独立服务 |
| 回滚单位 | Knowledge Capability + settings/catalog + task bindings + Stage providers |

## 18. 三轮内部自检与独立评审记录

v1.29/DR-KFLOW-028三轮内审及一次分离只读设计复核完成，经过类别词兼容、未分配条件/顺序计数及澄清枚举边界修复；S0=0、S1=0、未处理S2=0，可实施本切片，不代表整体效果。评审为同一执行者分离编辑的只读复核，语义归属无法由机械token证明的限制明确接受为UAT风险；过程及命令归P3 §20.77。

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

- 当前版本：v1.29；DR-KFLOW-024～028已评审实施，当前任务9/7/v3；纯校验/V9/Planner、生产根及现行Spring fake已落实，命令及评审见P3 §20.77.2，真实专项未通过。
- 文档状态：Approved；本次DR-KFLOW-028非live实施准入评审通过，不代表真实UAT通过。
- 新版本不继承旧版 candidate、Gate 或评审流水；来源与当前任务绑定已明确。

## 阶段 B 增量实施追踪

| 来源 | 设计 | 实现落点 | 测试 | 验证 |
|---|---|---|---|
| `REQ-KQUALITY-001～004`；`KQ-AD-013～016` | `DR-KFLOW-016～018` | rewrite_v3.py / semantic_planner.py / contracts.py / planning.py / capability.py；Core graph/nodes.py 固定文案；bootstrap 当前任务绑定 | `TEST-KFLOW-011`：V3 exact解码、原问题条件、单域/双域、澄清/unsupported/模型失败零检索、局部/全路径失败、固定reason文案、历史V1/V2字节不变 | `VAL-KFLOW-004`：V3单元/契约、生产根fake/Spring E2E、UAT_01 §14、模型/检索计数、strict mypy |
| `REQ-KQUALITY-003`；`KQ-AD-015` | `DR-KFLOW-019` | rewrite_v4.py；bootstrap任务工厂及版本守卫 | `TEST-KFLOW-003/004/009`：V4精确合同及Prompt、旧V3拒绝装配、生产澄清零调用；保留V3和冻结runner | `VAL-KFLOW-002/005`：non-live与Spring E2E已执行通过；实际LLM语义稳定性仍待新授权，不在本次补跑 |
| `REQ-KQUALITY-001`；`KQ-AD-013` | `DR-KFLOW-020` | 已新增rewrite_v5.py；bootstrap唯一绑定与版本守卫切换；既有semantic_planner不改 | `TEST-KFLOW-012`：任务合同、域计划fake、版本拒绝、历史隔离 | `VAL-KFLOW-002/005`：定向/full non-live、strict mypy及Spring E2E执行结果见P3；真实语义暂缺 |

v1.19评审范围仅§8.2/DR-KFLOW-020及直接追踪。三轮内审分别核实：(1) L1 KQ-AD-013与原问题域语义，禁止本地词面纠域；(2) 不变的V3 decoder、V4澄清及安全预算，移除无必要的新增配置/版本常量；(3) 固定任务切换、历史测试隔离、可回退源码及UAT缺口。随后冻结修订，按L2实施可行性rubric执行只读设计复评：无S0/S1/未处理S2，允许该非live切片实施，不允许新live批次或专项收口。该评审为同一执行者的分阶段对照复评，不是另一名独立人员批准，也不验证LLM实际语义。Summary覆盖判据仍需另行核查，不以本规则改写历史gold。

上述DR-KFLOW-017/018的质量V1保留历史解释责任；当前增量目标为下述DR-KFLOW-022的V2，旧调用默认及历史任务/证据不修改。UAT使用独立阶段B命名空间，验收标准和执行状态归UAT_01/P3。

### 质量策略V2内部版本绑定（DR-KFLOW-022）

本节保留v1.22历史增量，当前V3合同以§8.5为准：当时生产根在保留Rewrite6/Summary5的前提下，将`knowledge-retrieval-quality-v2`与Evidence `quality_v2()`成对绑定。`KnowledgeSemanticPlanner`新增内部构造参数quality_version，默认仍为V1，只接受V1/V2；不由模型、HTTP、用户或环境配置选择。该值经RewriteResult.plan_version→DomainSelection.catalog_version→RetrievalPlan.quality_version→EvidenceInput.quality_version原样透传；未知版本在检索前失败关闭，不回退。计划观测沿用既有quality_version字段，运行manifest额外冻结实际策略与源码，不改公共DTO或模型输出Schema。

Retrieval按版本选择旧V1或新V2内部排序函数，Evidence按同一版本验证锚点；V2根不得错配旧每文档3条limits。历史冻结根默认V1、quality_v1仍3，legacy仍2。该历史增量当时只绑定V2，不增加请求内版本切换、第二流程或新配置服务。修改触点为contracts常量、semantic_planner、planning、capability、bootstrap及下位两阶段consumer；旧Rewrite/Summary源码、Guard、HTTP、policy和历史运行资产不改。

本增量当前状态：V2已按三轮内审和只读设计复评结论实施，非live与代码复核记录归P3；真实专项完成仍由P3/UAT判定，不能继承旧批Passed。回滚可禁用Knowledge，或将同一代码发布中的planner/ranking/limits绑定整体恢复为V1；不得单独切换一端或改写历史证据。

v1.21内审1：对照REQ-KQUALITY-001与KQ-AD-013，明确只允许不重复其他子问的背景，作用于本域的税种/法律条件不能删除；原问题、每域1表达及总预算不变。内审2：核实V5 definition公开可替换，唯一旧指令精确替换，V3 decoder/planner/Guard不变；补充本地无法证明任意语义归属的限制，禁止以fake冒充语义保持。内审3：补齐DR-021主追踪、实现/测试映射及回滚，纠正§6“V5未测量”的过时状态，明确V6未实施、配额/锚点和独立真实UAT仍未关闭。

v1.21正式只读复评第1轮：冻结§8.3/DR-KFLOW-021修订后，依据REQ-KQUALITY-001/002、L1 KQ-AD-013/014/017、V3精确decoder/planner和V4/V5公开definition，审查L2实现可行性及跨层边界。S0=0、S1=0、未处理S2=0；追踪、语义职责、不变Guard/预算、版本兼容、失败关闭、单绑定和源码回滚闭合，允许本切片非live实施。严格结构校验0 errors/0 warnings。该结论来自同一执行者分离修改阶段的只读对照审查，不冒充另一名独立人员批准；不证明LLM条件归属、核心P0或整体UAT通过。Evidence配额与真实执行仍独立暂停。
