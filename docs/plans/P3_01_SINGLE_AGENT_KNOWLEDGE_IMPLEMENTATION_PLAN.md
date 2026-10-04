# [P3_01] Knowledge 新设计实施计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档标识 | P3_01 |
| 文档类型 | 设计驱动实施计划 |
| 当前版本 | v3.41 |
| 文档状态 | Reviewed（发布守卫non-live增量已独立定向复评；完整验收未完成） |
| 日期 | 2026-10-04 |
| 目标计划路径 | docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md |
| 适用范围 | 已批准Knowledge在线重建、资料组织与检索表示两条主线 |
| 非范围 | Business重新设计、图谱、记忆、多轮、旧候选推进 |
| 权威顺序 | 用户范围 → 仓库规则 → REQ/L0/L1/公共契约 → Knowledge L2 → 当前实现证据 → 本计划 |
| 实施授权 | Ready不等于实施授权。历史独立B/MEASURE执行及授权消费见§14.31～37，原目录不复用；selector v5仓库non-live修正见§14.38。DRYRUN及纯离线DIAGNOSE见§14.40/42。本轮另经维护者确认一次独立词法诊断：同现行b2、旧/当前helper、固定001/002/003/012，typed与物理search各8、只读元数据18、健康检查≤40；模型/BGE/写入/retry/resume均0，具体冻结及终态见§14.43。该授权已执行，不是新B/MEASURE或滚动运行许可；后续操作仍须精确范围及有效授权，gold/阈值及在线父读取禁令保持 |
| 计划执行状态 | Done=11（含DRYRUN、DIAGNOSE）；In Progress=2（COMPARE、MEASURE）；Ready=0；Blocked=1（RELEASE），共14包/14直接边。原Done证明范围保持；两项新包仅工具non-live及离线诊断完成，不证明效果。B主指标未改善、precision未评；MEASURE完成4题后005技术失败，001/002人工Passed、003/004 Failed，整批仍invalid_run。保留现行b2，不发布/追加实验 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-09-14 | 全文 | 旧综合计划退出当前推进权威 | 新文档首版v3.0，承接已批准设计，不继承旧计划通过结论、Gate或预算 |
| 2 | 2026-09-15 | §7/12/13 | 跨阶段VAL可能被误读为早期包的全部前置 | v3.0内澄清各验证部分及后续承接包；工作包、直接依赖、状态和验收标准不变 |
| 3 | 2026-09-15 | §1/3/5/7/9/10/12/14 | 按包推进实际实施 | v3.0状态更新：核实CONTRACT提交、完成RETRIEVAL组件与non-live；设计、12条直接依赖及验收判据不变 |
| 4 | 2026-09-24 | §1/3～5/9/10/12～14 | 资料结构单元设计补齐 | v3.1承接L1/L2 v3.2：把解析顺序、稳定unit/span及策略选择分配到NORMALIZE/CHUNK；在线补取仍未授权，12包/12边与既有Done状态不变 |
| 5 | 2026-09-24 | §1/5/9/12～14 | 启动NORMALIZE并修复范围外旧版引用 | v3.1内仅同步执行事实：NORMALIZE离线基础代码及测试已本地提交，真实来源验收待补；L0/L1_00五处Knowledge版本引用已另获授权修正 |
| 6 | 2026-09-28 | §1/5/9/12/14 | 按依赖完成有限来源核对及离线CHUNK | v3.1内同步NORMALIZE、CHUNK的本包验证与审查边界；REPRESENT转Ready，不改12包/12边或在线合同 |
| 7 | 2026-09-29 | §1/3/9 | 消除已完成包与当前描述的状态漂移 | v3.2仅修正既往授权、结构单元离线范围和COMPARE未关闭前置的表述；12包/12边、验收判据及执行结论不变 |
| 8 | 2026-09-29 | §1/3/5/7/8 | 当前独立目标实施与L2_01_01 v3.3候选合同 | v3.3区分当前有限授权和实际准入，COMPARE承接独立新候选构建器与逐记录向量来源前检；不预记测量、发布或质量通过 |
| 9 | 2026-09-29 | §1/3/5/9/12/14 | 本轮组件、组合根与候选工具阶段证据 | v3.4按实跑non-live同步EVIDENCE/REPRESENT完成、COMPOSE/COMPARE在制及真实测量/发布阻塞；引用L2_01_01 v3.5与UAT_02 v3.4，不预记新版UAT通过 |
| 10 | 2026-09-29 | §1/3/5/9/12/14 | 关闭COMPOSE的non-live范围并记录对照前检 | v3.5补齐Spring逐case typed和拒绝路径断言、并发/证据防误报；36项fake/non-live风险有证据、EV006留给MEASURE人工评价。COMPARE仅纯离线预算预检，真实候选仍被结构证明/gold阻断 |
| 11 | 2026-09-29 | §1/3/14 | 单域当前root真实typed只读接线补证 | v3.6记录显式opt-in隔离预检；不扩展COMPOSE完成范围，不把有限接线证据改写为Spring全链、真实效果或新版UAT通过 |
| 12 | 2026-09-29 | §14.10 | COMPARE附件节标题解析缺陷的最小修复 | v3.6内记录v2 `.doc`解析修复及定向/全包验证；独立原件结构证明和A/B准入仍未完成，工作包状态不变 |
| 13 | 2026-09-29 | §3/14.9/14.11 | 纠正旧库存正文hash表述并同步逐记录溯源前检 | v3.7区分旧索引`contentHash`、typed响应重算hash与四附件旧向量trace；同步UAT_02当前版本，不把只读前检写成全库冻结、A/B准入或人工gold |
| 14 | 2026-09-29 | §14.12 | COMPARE的旧DOC原生段落与失败关闭前检 | v3.7内记录v2专用解析修复、独立原件对照和复评；结构证明、A/B准入及工作包状态不变 |
| 15 | 2026-09-29 | §14.13 | COMPARE全库只读指纹及A单变量边界复核 | v3.7内补记当前b2完整竞争池指纹和A解析源漂移；B仍缺人工gold、模型快照及正式预算，不预记真实对照 |
| 16 | 2026-09-29 | §14.14 | COMPARE模型同一性与旧DOC结构再核对 | v3.7内补记当前BGE快照仅启动时间变化、四份旧DOC结构证明的边界；A/B状态及人工gold准入不变 |
| 17 | 2026-09-29 | §3/14.15 | B表示输入来源的最小设计修正 | v3.8承接L2_01_01 v3.7已复评合同：从已核验的同次源扫描构造表示并识别keyword混杂；构建器fake已实施，一次性入口、正式spec和真实对照仍待实施/冻结，COMPARE状态不变 |
| 18 | 2026-09-29 | §1/3/5/11/14 | 真实12题与Summary8能力冲突 | v3.9承接已授权的Summary9定向设计；MEASURE不增加独立包或Gate，付费调用前须完成设计评审、最小代码及non-live；当前9个Done包的原证明范围不改写 |
| 19 | 2026-09-29 | §1/3/5/9/12/14 | Summary9仓库实施与B冻结设计纠偏 | v3.10如实同步Summary9代码及定向non-live、正式隔离Python全量和独立代码复评；MEASURE转In Progress但真实批次未启动。L2_01_01 v3.8/UAT_02 v3.10的B两阶段冻结与隔离设计已定向复评，工具和Java仍待实施复评，真实B/发布未执行 |
| 20 | 2026-09-29 | §1/3/14 | B冻结工具与Summary9合成三模式接线 | v3.11记录源绑定与比较器的synthetic-only验证及18个Spring合成case；不把fake指标当真实B，也不把合成claim当人工回答质量。COMPARE/MEASURE继续In Progress，RELEASE仍Blocked |
| 21 | 2026-09-30 | §1/3/5/9/11/14 | 一次性B/MEASURE工具和本轮回归已提交 | v3.12仅同步提交`631cc47c`及§14.18的fake、类型、UI、Java和正式隔离回归；不改工作包依赖、门禁、阈值或真实UAT结论 |
| 22 | 2026-09-30 | §1/3/5/9/12/14.19 | B候选与失败终态、MEASURE未冻结准备同步 | v3.13记录提交`c9b8642e`的append-only B证据：候选只读未发布、比较消费而无有效测量；MEASURE仅有build-only准备。COMPARE/MEASURE仍In Progress，RELEASE仍Blocked，A仍Not assessed；不改§14.1～14.18的历史发生状态 |
| 23 | 2026-09-30 | §1/3/5/9/12/14.20 | MEASURE首次冻结批次失败终态同步 | v3.14仅记录`knowledge-rebuild-measure-20260930-02`冻结后在ledger初始化前失败、0模型及typed检索等执行调用（不含启动前只读ES元数据前检），随后最小修复只有non-live证明；不复用该run，不改§14.1～14.19的历史发生状态、门禁或阈值 |
| 24 | 2026-09-30 | §1/3/14.21 | 新独立验证授权及启动准入补齐 | v3.15先补独立无LLM启动预检和已建候选跨run绑定；保留旧失败run终态、题目、预算、gold及阈值，不新增Gate或候选索引 |
| 25 | 2026-09-30 | §1/3/14.22 | 正式元数据HTTP与检查次数混淆 | v3.16据源码纠正新MEASURE元数据上限为维护者批准的72；保留每次双GET安全核查和实际attempt计数，其余正式预算与历史资产不变 |
| 26 | 2026-09-30 | §3/14.23 | 新工具复评及B无推理启动预检完成 | v3.17记录有限真实启动证据，不预记B对照、MEASURE、人工评价或发布通过 |
| 27 | 2026-09-30 | §14.24 | MEASURE无推理启动失败及non-live诊断 | v3.18保留端口归属失败终态，不自动复跑，未观测代理计数不补造0 |
| 28 | 2026-09-30 | §1/3/5/12/14.25 | 新B全部调用后准入失败及内部请求见证纠偏 | v3.19区分旧首题前失败与新10题后验失败，仍无有效比较/人评/发布；承接L2_01_01 v3.11，不改历史终态、题目、预算或阈值 |
| 29 | 2026-09-30 | §3/14.26 | 私有工具的消费后有限失败与自有进程清理证明缺口 | v3.20同步最小修复、定向non-live及独立代码复评；不改工作包状态、真实运行终态、预算、阈值或生产合同 |
| 30 | 2026-10-02 | §1/3/14.27 | 新独立启动预检失败及Java运行时选择纠偏 | v3.21记录本次零推理终态、有限证据和私有工具non-live修复；不进入新正式冻结，不改变历史结果、gold、阈值、调用预算或包状态 |
| 31 | 2026-10-02 | §1/3/14.28 | 新授权下两套独立无付费预检结果 | v3.22记录B ready与MEASURE es_ready失败；B可独立继续，MEASURE不复跑；不改历史终态、DAG、gold、阈值或预算 |
| 32 | 2026-10-02 | §1/3/14.29 | 新B后验请求同一性失败及字段投影确定性修复 | v3.23记录实际调用、有限拒绝原因和non-live修复；不改判、不复跑，不改变预算、gold、阈值或工作包DAG |
| 33 | 2026-10-03 | §1/3/5/9/14.31 | 启动及清理修复后继续新独立验证 | v3.25同步B与MEASURE无推理启动证明和有限源码复核；不预记正式质量、人评或发布，不改gold、阈值、预算或DAG |
| 34 | 2026-10-03 | §1/14.32 | 新B正式协议完整、质量边界明确 | v3.26记录recall相同及215项盲标缺口，保留现行b2；不把执行完整改判为质量通过 |
| 35 | 2026-10-03 | §1/3/5/9/12/14.33 | 新MEASURE已消费后停止及当前状态漂移纠偏 | v3.27记录实际调用、4题结果和第005题失败定位边界；不复跑、不修改预算/gold/阈值，修正当前追踪行及UAT版本引用 |
| 36 | 2026-10-03 | §3/14.34 | MEASURE失败响应观测不足 | v3.28记录私有runner的固定分类补齐及零outbound验证；不补写旧证据，不把观测修复说成第005题根因修复，工作包、预算和判据不变 |
| 37 | 2026-10-03 | §14.35 | 已封存B来源损失及部分人评材料复核 | v3.29补录离线定位与四题审阅准备，不代填维护者评分、不改变失败终态或发布条件 |
| 38 | 2026-10-03 | §3/14.36 | 独立有限元数据诊断及联合机关软匹配修正 | v3.30承接L2_01_01 v3.12已评审切片，只记录4次GET及non-live修正；不重跑、不改历史结果或发布条件 |
| 39 | 2026-10-03 | §1/3/5/9/12/14.37 | 维护者确认已完成四题的人工结论 | v3.31独立记录001/002 Passed、003/004 Failed，不补造分项评分，不改整批invalid_run、历史资产、预算或发布状态 |
| 40 | 2026-10-03 | §14当前结论 | 当前摘要仍混用旧批次状态 | v3.32按§14.32/33/37同步新B有限证据、四题执行与人工结论；不修改各批次历史记录、工作包状态、阈值或授权 |
| 41 | 2026-10-03 | §1/3/14.38 | 动作选择职责与新任务接线 | v3.33承接L1_00 v3.2、L2_00_02 v3.4定向复评，实施独立selector v5、enabled组合根及未来严格冻结；仅记录non-live验证，不改历史结果、gold、阈值、预算或12包DAG，不预记真实质量 |
| 42 | 2026-10-03 | §3/5/6/9/10/12/14.39 | 重复执行失败与召回无收益需分开处理 | v3.34承接L1_01 §4.7、流程L2 §20及检索L2 §9.9；新增两个有限准备包，不增加在线调用、框架或真实预算 |
| 43 | 2026-10-03 | §1/3/4/5/9/12/14.40 | 正式路径无付费演练包实施及复评 | v3.35关闭DRYRUN的有限non-live范围，同步单一预算、失败取证、清理及提交/验证；DIAGNOSE仍Ready，原效果/测量/发布状态和14包/14边不变 |
| 44 | 2026-10-03 | §5/9/12/14.41 | 按现行验收合同明确B候选不采用 | v3.36只读验真及逐阶段排名比较，记录有限否决与仍未知原因；不补盲标、不改历史结果、不关闭COMPARE/A/MEASURE/RELEASE，不启动新运行 |
| 45 | 2026-10-03 | §1/3/4/5/9/12/14.42 | 离线损失诊断本包实施及复评 | v3.37关闭DIAGNOSE有限离线范围，保留unknown、原终态和14包/14边；不预记召回提升、完整测量或发布 |
| 46 | 2026-10-04 | §1/3/14/14.43 | 另获精确授权的同索引词法helper比较 | v3.38记录唯一有限诊断的8次typed/物理search及局部收益；旧终态、工作包DAG、整体质量和发布状态不变，不追加真实批次 |
| 47 | 2026-10-04 | §1/3/5/14.44 | 原005解释路径未进入正式runner合成覆盖 | v3.39补齐同runner/生产ASGI的explanation正向和非法引用停批反例；不归因旧失败，不改生产实现、gold或真实测量状态 |
| 48 | 2026-10-04 | §9.1 | 恢复推进需明确可信基线及下一验证变量 | v3.40澄清旧A不能只补proofRef；优先提出同b2的文号修正检索全链对照，保留独立授权、预算及验收边界；不新增工作包、Gate或真实批次 |
| 49 | 2026-10-04 | §5/14.45 | 旧发布工具遗漏完整alias及成功回执守卫 | v3.41按现有DR-KRET-025补齐空flags、候选无alias、严格回执与切后UUID核查；只执行fake/工具回归，RELEASE仍Blocked，不启动新批次或发布 |

## 3. 来源清单与当前基线

| 资源 | 角色 | 层级 | 状态/版本 | 权威范围 | 是否读取 | 置信度 |
|---|---|---|---|---|---|---|
| [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | 目标架构 | L1 | v3.7 / Approved | §4.5/4.6原合同保持；§4.7新增验证/诊断决策 | 是 | 本轮增量已独立定向核查，不证明真实效果 |
| [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | 流程详细合同 | L2 | v3.8 / Approved | §8/19原合同、§20 DR-KFLOW-401～403 | 是 | 演练本包已实施并独立代码复评；只证明验证工具non-live可靠性 |
| [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | 检索与资料合同 | L2 | v3.14 / Approved | §9/18原合同、§9.9 DR-KRET-401～403 | 是 | 离线诊断及有限定位已实施、独立复评；在线补检未批准，预算不变 |
| [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | Evidence/回答合同 | L2 | v3.6 / Approved | §9、§19，DR-KEV-201～206/301～304 | 是 | Summary9三模式Spring合成链已验证；lookup两题人工Passed，完整真实语义效果未评价；父正文不自动成为Evidence |
| [L1_00](../design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | 共享动作选择职责 | L1 | v3.2 / Approved | §4.1按能力职责选择，不预判资料存在性 | 是 | 本轮增量定向独立复评；Business与历史v4不变 |
| [L2_00_02](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | 模型任务及绑定合同 | L2 | v3.4 / Approved | §6.3、DR-MODEL-112动作选择v5 | 是 | 本轮增量已实施并有non-live证明，不表示实际部署或真实效果 |
| [UAT_02](UAT_02_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 当前验收 | 计划 | v3.39 / Reviewed | 原功能/安全/召回/回答及资料判据，§5.6/6.4演练/诊断与不采用边界 | 是 | 005合成路径和003词法局部收益各有证明边界；不改gold、阈值或旧终态，完整质量及发布未通过 |
| [UAT_00](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | Business维护基线 | 验收 | v3.1 / Reviewed | 固定35风险与Employee15类扩展，原证据范围 | 是 | 历史等价复用，不是本轮UAT |
| [旧P3_00快照](历史文档/2026-09-14-knowledge-plan-handoff/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) | 承接与历史事实 | 归档 | v3.0 / 原状态保留 | §21/22新设计交接，其余旧执行不继承 | 是 | 冻结提交/原资产可追溯 |

原计划建立时的起始代码提交为`8ae32c50a567850c67b4d1e726304934ab07162c`；本次独立目标起点为`2e27086150360bda87ef09e319a2569a2246c07b`，当时仓库生产root绑定11/7/quality-v3，默认Knowledge disabled。当前仓库已成对接线intent12/Summary9/minimal-v1并保持disabled缺省；原12/8组件及COMPOSE的non-live证明按§14.6～14.7记录，Summary9定向证据见§14.16～14.17，工具与回归见§14.18，B有限终态及首次MEASURE准备边界见§14.19，本次MEASURE失败终态见§14.20，单域当前root真实typed只读接线的有限预检见§14.8。COMPOSE Done只指仓库组合根、Spring fake与安全回归；Spring→Runtime Summary9合成三模式及失败链已验证，实际部署和效果仍待后续验证。仓库配置不是实际部署证明；首次正式冻结不构成有效测量，后续必须另行决定是否准备新目标和新批次，不复用失败run。历史审计与运行状态见[迁移清单](历史文档/2026-09-14-knowledge-plan-handoff/README.md)，不复制到新计划作为新验证结果。

## 4. 计划原则与范围

Ready 不等于实施授权；DRYRUN及必要的纯离线DIAGNOSE范围现已完成，不能由此自动启动任何真实操作。

两条主线分别由三份Knowledge L2定义；本计划不新增DR或修改算法、公共DTO、授权及失败语义。旧ROADMAP不再是前置，不新增替代路线图。原文、安全组件和阶段A成果保留职责；内部旧实验的清理只在后续授权COMPOSE中确认调用方、冻结源可追溯后进行。

Online：合同 → 检索/证据并行 → 成对接线 → 测量。
Corpus：标准化 → 切片/表示并行 → 对照 → 受控发布。
两条主线没有彼此真实UAT前置；COMPARE需选择一套冻结在线实现，可用现有相容实现，不要求先完成MEASURE。新公共父读取、时效/分类DTO或权限变更不是当前隐含交付。

资料结构单元补充沿用现有DAG：NORMALIZE提供来源/版本、规范解析源与结构可信状态的严格记录；CHUNK先修复受影响解析器的段落/表格交错顺序，再生成完整结构单元、连续chunk span及稳定关系；REPRESENT可独立以固定的已验证旧chunk fixture验证表示构造，新的结构chunk与表示集成留给同时依赖CHUNK/REPRESENT的COMPARE。当前typed合同禁止在线父正文补取；未来若确需补取，先单独评审公共合同、安全与预算，不并入EVIDENCE、COMPOSE或本轮资料包的Done判据。

## 5. 工作包清单

来源设计Done承接原审查范围，不表示本轮重做全部设计；v3.2结构单元补充另作本轮文档评审与本地提交，不能把原DESIGN包的历史推送证明改写为本轮推送。验证列是各包完成条件；已完成范围以逐包状态及§14证据为准，未完成包不得预记通过。

| 工作包 ID | 名称 | 来源设计 | 范围 | 直接依赖 | 入口门禁 | 交付物 | 验证 | 回滚边界 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| WP-KREBUILD-DESIGN-01 | DESIGN | L2_01_00 §8 DR-KFLOW-201～205 | 已批准在线设计/分类决策；不重新设计 | - | - | 设计来源与实施边界 | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | 只文档diff，不回滚历史；无服务/模型 | Done |
| WP-KREBUILD-CONTRACT-01 | CONTRACT | L2_01_00 §8 DR-KFLOW-201/202 | 内部意图合同及task12 | WP-KREBUILD-DESIGN-01 | - | 内部schema3/精确decoder/task | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | 后续代码授权；新增独立类型/task，暂不切root | Done |
| WP-KREBUILD-RETRIEVAL-01 | RETRIEVAL | L2_01_00 §8 DR-KFLOW-203；L2_01_01 §9 DR-KRET-201～204 | 原Q双路、域内融合/重排与有界配置 | WP-KREBUILD-CONTRACT-01 | - | planning/semantic_planner/ranking/config最小策略 | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | 本地fake；独立strategy，旧prod不变；无索引写入 | Done |
| WP-KREBUILD-EVIDENCE-01 | EVIDENCE | L2_01_02 §9 DR-KEV-201～205 | minimal Evidence和Summary8 | WP-KREBUILD-CONTRACT-01 | - | mode input、evidence selector、serializer、summary_task_v8.py/decoder | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | 直接代码和fake证据见§14.6；旧Prompt/serializer不改 | Done |
| WP-KREBUILD-COMPOSE-01 | COMPOSE | L2_01_00 §8 DR-KFLOW-204/205；L2_01_02 §9 | 唯一root迁移与历史隔离 | WP-KREBUILD-RETRIEVAL-01、WP-KREBUILD-EVIDENCE-01 | - | bootstrap/capability/任务目录；37风险新版映射及non-live验证 | current-root、Spring E2E、37风险逐case追踪、Business35关键防退、Java安全/类型/non-live、正式代码评审；实质回答充分性由MEASURE承担；Blocker/Major0 | 仓库接线及non-live范围完成，36项fake/non-live直接证据；§14.8另有单域当前root真实typed只读预检，EV006真人语义评价、Spring全链和部署均不属于本包Done | Done |
| WP-KREBUILD-MEASURE-01 | MEASURE | L2_01_02 §9 DR-KEV-205/206；UAT_02 §5 | 固定12题及一次独立测量；Summary9最小回答接缝已完成 | WP-KREBUILD-COMPOSE-01 | - | Summary9独立任务/严格解码/原文及claim校验/唯一root及验证台同屏引用展示，继而新版本问题/来源/预算绑定、有限结果及真人评价 | REQ→L0/L1→L2设计复评及Summary9定向non-live已通过；§14.33完成4题后005技术失败停止；§14.37维护者确认001/002 Passed、003/004 Failed，完整12题未完成 | 本批授权已消费；不补跑/续跑或复用目录，不因余额追加调用。可继续无付费诊断；后续真实验证须独立决定。Done包原证明范围不变 | In Progress |
| WP-KORG-DESIGN-01 | DESIGN | L1_01 §4.6；L2_01_01 §18；L2_01_00/02 §19 | 已批准资料组织设计；本轮仅补结构单元与补取边界，不重判原完成证据 | - | - | 设计来源、样本边界及资料方案 | 原设计的内审/复核/文档及Git证明维持原范围；v3.2补充须单独评审和本地提交，不冒称新代码或推送 | 只文档；不动服务/模型/索引 | Done |
| WP-KORG-NORMALIZE-01 | NORMALIZE | L2_01_01 §18 DR-KRET-301～303；L2_01_02 §19 DR-KEV-301；L2_01_00 §19 DR-KFLOW-301/302 | 标准化、不可变源版本及结构可信状态记录；不把现有DOCX乱序产物标verified | WP-KORG-DESIGN-01 | - | normalization_v2.py/来源位置Schema/fixture | TEST-KRET-301、hash/span及不可靠顺序反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | 本包代码与有限来源核对见§14.3/14.4；未批量生成真实v2 sidecar或迁现索引 | Done |
| WP-KORG-CHUNK-01 | CHUNK | L2_01_01 §18 DR-KRET-303/304 | 最小修复受影响DOCX解析顺序，建立结构单元身份、同版本父子关系与连续chunk span | WP-KORG-NORMALIZE-01 | - | parser顺序接缝/chunking_v2.py及段表交错、短长条、表格/否定/例外fixture | TEST-KRET-302；完整单元可按源span恢复且hash一致，跨版本/悬空/乱序失败关闭，不静默遗漏 | 本包离线代码、fixture和复评见§14.5；旧chunker不覆盖，真实资料重切/发布待后续包 | Done |
| WP-KORG-REPRESENT-01 | REPRESENT | L2_01_01 §18 DR-KRET-305/306 | 独立检索表示及token前检；不把父单元或派生表头当可引用正文 | WP-KORG-NORMALIZE-01 | - | 表示构造/model manifest/tokenizer验证 | TEST-KRET-303；明确实际长度单位/版本，无截断、body/input hash独立；旧未知不回填 | 纯构造、固定tokenizer与直接证据见§14.6；无推理或索引写入 | Done |
| WP-KORG-COMPARE-01 | COMPARE | L2_01_01 §18 DR-KRET-307；L2_01_02 §19 DR-KEV-304；UAT_02 §6 | 单变量有限对照 | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | - | 独立新版离线候选构建器、完整竞争池、scope/原文gold/排名损失/四维报告 | fake/类型→逐记录旧向量溯源及人工原文→有限BGE/候选/只读typed；逐阶段损失、keyword漂移归因、人工盲标及停止规则 | §14.41据完整封存B的主指标未改善决定不采用、保留b2；precision仍null/215项未标，A仍Not assessed，整个COMPARE未完成、不追加对照 | In Progress |
| WP-KORG-RELEASE-01 | RELEASE | L2_01_00 §19 DR-KFLOW-303；L2_01_02 §19 DR-KEV-302/303 | 选定候选兼容发布 | WP-KORG-COMPARE-01 | - | 策略/Profile一致性、精确旧绑定、回滚与冒烟证据 | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；§14.45仅补齐alias守卫fake，不代替真实验证；无证据不得发布 | 当前目标仅在条件满足后授权新索引/受控部署/alias写入；生效前仍须核实精确旧绑定与原子回滚；不删旧索引 | Blocked |
| WP-KVERIFY-DRYRUN-01 | DRYRUN | L1_01 §4.7；L2_01_00 §20 DR-KFLOW-401～403；UAT_02 §5.6 | 正式runner同路径演练、预算与失败/清理闭环；不重跑真实批次 | WP-KREBUILD-COMPOSE-01 | - | 私有测试接缝、合成12题及故障注入、有限演练证据 | §14.40/44：TEST/VAL-KFLOW-401～403及005解释正反向、零真实调用、安全扫描与独立代码复评通过；非startup-only或真实质量证明 | 只恢复验证工具相容绑定，生产/历史不动；不授予真实批次或启动诊断 | Done |
| WP-KRETRIEVAL-DIAGNOSE-01 | DIAGNOSE | L1_01 §4.7；L2_01_01 §9.9 DR-KRET-401～403；UAT_02 §6.4 | 既有封存证据逐阶段损失与最小修正决策；不实施在线补检 | WP-KREBUILD-RETRIEVAL-01 | - | 离线trace/source reader、unknown分类、有限诊断和B不采用决策交接 | §14.42：TEST/VAL-KRET-401～403、严格封存重放、合成定位与独立复评通过；新读取仍须预算授权 | 新增离线入口可撤销，不改旧结果、数据或在线配置 | Done |

## 6. 直接依赖图

| 依赖 ID | 前置工作包 | 后继工作包 | 类型 | 技术依据 | 来源证据 |
|---|---|---|---|---|---|
| DEP-KREBUILD-001 | WP-KREBUILD-DESIGN-01 | WP-KREBUILD-CONTRACT-01 | contract | DR-KFLOW-201/202及新内部plan/schema3、精确intent12；模式/目录/terminal合同 | L2_01_00 §8 / L2_01_01、02 §9 |
| DEP-KREBUILD-002 | WP-KREBUILD-CONTRACT-01 | WP-KREBUILD-RETRIEVAL-01 | contract | DR-KFLOW-203及DR-KRET-201～204；原问两路、域内RRF/rerank及minimal配置 | L2_01_00 §8 / L2_01_01、02 §9 |
| DEP-KREBUILD-003 | WP-KREBUILD-CONTRACT-01 | WP-KREBUILD-EVIDENCE-01 | contract | DR-KEV-201～205；minimal选择、mode input、Summary8；精确输出及模式语义反例 | L2_01_00 §8 / L2_01_01、02 §9 |
| DEP-KREBUILD-004 | WP-KREBUILD-RETRIEVAL-01 | WP-KREBUILD-COMPOSE-01 | contract | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | L2_01_00 §8 / L2_01_01、02 §9 |
| DEP-KREBUILD-005 | WP-KREBUILD-EVIDENCE-01 | WP-KREBUILD-COMPOSE-01 | contract | DR-KFLOW-204/205；12/8/minimal-v1唯一接线、迁移测试、确认无调用方旧实现清理 | L2_01_00 §8 / L2_01_01、02 §9 |
| DEP-KREBUILD-006 | WP-KREBUILD-COMPOSE-01 | WP-KREBUILD-MEASURE-01 | contract | UAT_02 §5：人工问题/来源冻结、真实typed只读确认、一次新版本有限测量、四维报告 | L2_01_00 §8 / L2_01_01、02 §9 |
| DEP-KORG-001 | WP-KORG-DESIGN-01 | WP-KORG-NORMALIZE-01 | contract | DR-KRET-301/302/303、DR-KEV-301；normalization_v2.py/sidecar及来源位置Schema | L2_01_01 §18 / L2_01_00、02 §19 |
| DEP-KORG-002 | WP-KORG-NORMALIZE-01 | WP-KORG-CHUNK-01 | contract | DR-KRET-304；chunking_v2.py、结构fixture、span回放 | L2_01_01 §18 / L2_01_00、02 §19 |
| DEP-KORG-003 | WP-KORG-NORMALIZE-01 | WP-KORG-REPRESENT-01 | contract | DR-KRET-305/306；独立表示、模型manifest补证及tokenizer预检 | L2_01_01 §18 / L2_01_00、02 §19 |
| DEP-KORG-004 | WP-KORG-CHUNK-01 | WP-KORG-COMPARE-01 | contract | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | L2_01_01 §18 / L2_01_00、02 §19 |
| DEP-KORG-005 | WP-KORG-REPRESENT-01 | WP-KORG-COMPARE-01 | contract | DR-KRET-307、UAT-KORG-001～012；有限scope/原文gold/四维实验报告 | L2_01_01 §18 / L2_01_00、02 §19 |
| DEP-KORG-006 | WP-KORG-COMPARE-01 | WP-KORG-RELEASE-01 | contract | DR-KFLOW-303、DR-KEV-302/303及既有发布合同；选定候选的策略/索引兼容发布 | L2_01_01 §18 / L2_01_00、02 §19 |
| DEP-KVERIFY-001 | WP-KREBUILD-COMPOSE-01 | WP-KVERIFY-DRYRUN-01 | runtime | 演练消费已接线的当前root及正式runner，不再复制另一套流程 | L2_01_00 §20 DR-KFLOW-401 |
| DEP-KDIAG-001 | WP-KREBUILD-RETRIEVAL-01 | WP-KRETRIEVAL-DIAGNOSE-01 | contract | 需要当前原问双路、RRF/重排输出语义以归属阶段损失 | L2_01_01 §9.9 DR-KRET-401 |

共14包、14条直接边，无新增跨主线强制边。新增两包独立产出可靠性与诊断证据；两包互不前置，也不把后续真实UAT变成基础实现依赖。原WP/DEP身份及完成范围保持，推荐顺序不是依赖。

## 7. 阶段门禁

| 门禁 ID | 工作包 | 类型 | 控制动作 | 是否阻塞入口 | 关闭条件 | 证据/权威来源 | 责任方/外部提供方 | 最晚关闭阶段 | 验证者与方法 | 未关闭行为 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|

门禁表有意为空：没有需另设编号的门禁，不为格式创造重复审批。

本计划不新增编号门禁，也不继承旧Gate。包的完成条件和外部操作授权按§5/8控制：设计输入允许技术Ready；COMPOSE以non-live、契约、类型及代码评审完成，不以真实效果作其反向前置；MEASURE与COMPARE仅完成有限测量。COMPARE未Done时RELEASE为Blocked；COMPARE按完整协议Done、两项额度收口但无合格候选时，保留旧绑定并将RELEASE记为Deferred；COMPARE Done且存在合格候选时RELEASE可Ready，但Ready不等于允许切alias。实际生效仍须核实完整性、安全、精确旧绑定、回滚和部署证据，未满足则不切换或记Done。当前目标已授权限定范围内的一次批次、至多两项对照和满足条件后的发布；首次外部操作前仍核对人工确认、冻结身份、精确预算及停止条件，超范围或新批次须另行授权。

§5/12中的VAL是来源设计的验证集合，不是该ID全部阶段均须在每个引用包完成。跨阶段部分按§12分工承接；后续包的真实测量或发布验证不得反向阻塞早期组件包，也不得因组件包Done而被标为已通过。

## 8. 外部资源与事实

| 资源 ID | 工作包 | 资源/事实 | 提供方 | 开始准备 | 必须完成 | 产物/引用 | 缺失影响 |
|---|---|---|---|---|---|---|---|
| EXT-KNEW-001 | WP-KREBUILD-CONTRACT-01 | 代码/测试及有限fixture读取授权；可复现本地环境 | 项目维护者/实施者 | 开始相应包之前 | 首次代码/测试修改前 | 新目标范围及non-live命令 | 无授权不得实施，技术Ready不变 |
| EXT-KNEW-007 | WP-KORG-NORMALIZE-01 | 资料代码/测试及有限fixture读取授权；同一目标可一并授权，不增加审批层 | 项目维护者/实施者 | 开始相应包之前 | 首次代码/测试修改前 | 新目标范围及non-live命令 | 无授权不得实施，技术Ready不变 |
| EXT-KNEW-002 | WP-KREBUILD-COMPOSE-01 | 隔离Spring/Runtime/Java安全测试环境与当前生产root | 维护者/实施者 | 相关实现并行时 | 接线验收前 | 测试版本、无live边界及失败/取消证据 | COMPOSE不能记Done |
| EXT-KNEW-003 | WP-KREBUILD-MEASURE-01 | 12题人工gold/必要来源、版本绑定、只读服务/模型预算及真人评价 | 维护者确认原文与人评；实施者受控执行 | COMPOSE期间可准备 | gold/预算在首调用前；结果人评在测量后、效果结论前 | UAT_02 §5，当前目标一次有限授权；人工确认仍是执行前置 | 停止真实执行/不分类质量达标 |
| EXT-KNEW-004 | WP-KORG-REPRESENT-01 | 固定tokenizer/model manifest及有限离线资源权限 | 模型资源维护者/实施者 | NORMALIZE期间可准备 | 表示长度验收前 | DR-KRET-306，版本和单位证明；当前目标已授权项目级资源准备 | 不得猜测token上限或补造旧表示来源 |
| EXT-KNEW-005 | WP-KORG-COMPARE-01 | 有限source/gold、完整竞争池、候选索引/BGE/typed及精确预算 | 维护者确认gold；实施者受控执行 | CHUNK/REPRESENT期间可准备 | 真实实验前 | UAT_02 §6与L2_01_01 §18.4.1；当前目标最多两项对照/两个新候选，前置仍须冻结和证明 | 不实验、不补跑、不继承旧候选 |
| EXT-KNEW-006 | WP-KORG-RELEASE-01 | 通过的质量/安全证据、精确旧索引与策略绑定、隔离回滚、受控部署/alias授权 | 数据与服务维护者/实施者 | COMPARE期间准备 | 候选生效前 | DR-KFLOW-303/DR-KEV-302/303；当前目标已授权条件满足后的切换，授权不代替质量门槛 | 未就绪不发布；原数据/旧索引不删除 |

## 9. Ready 队列与执行建议

| 顺序 | 工作包 | 判定 | 未关闭依赖/门禁 | 选择理由 |
|---|---|---|---|---|
| 1 | WP-KREBUILD-DESIGN-01 | Done | 无技术前置阻塞；后续操作须独立授权 | 来源设计已完成，非新实现 |
| 2 | WP-KREBUILD-CONTRACT-01 | Done | 无；提交及复核见§14.1 | 内部组件已验证；生产接线待COMPOSE |
| 3 | WP-KREBUILD-RETRIEVAL-01 | Done | 无；提交及验证见§14.2 | 新策略独立验证，生产接线待COMPOSE |
| 4 | WP-KREBUILD-EVIDENCE-01 | Done | 无；直接fake及代码复核见§14.6 | Summary8/Evidence组件完成，不预记完整UAT |
| 5 | WP-KREBUILD-COMPOSE-01 | Done | §14.7：Spring逐案typed、拒绝/并发及有限证据复评；§14.8：单域当前root真实typed只读预检 | 仅non-live实现包关闭；附加预检不代表Spring全链、部署、37/37 UAT或效果通过 |
| 6 | WP-KREBUILD-MEASURE-01 | In Progress | 无未完成直接依赖；§14.33本批已消费后技术失败，完整测量未完成；四题人工结论见§14.37 | 冻结现行b2与意图12/Summary9/minimal-v1，完成4题后停止；不补跑或续跑，真实复测不自动授权。先无付费定位，不以部分结果宣布验收通过 |
| 7 | WP-KORG-DESIGN-01 | Done | 无技术前置阻塞；后续操作须独立授权 | 来源设计已完成，非新实现 |
| 8 | WP-KORG-NORMALIZE-01 | Done | 无；有限来源核验见§14.4 | 离线版本/来源/结构可信合同完成；不声称全库v2转换或父单元读取 |
| 9 | WP-KORG-CHUNK-01 | Done | 无；代码及复评见§14.5 | v2离线切片合同完成；真实资料重切和候选发布仍未执行 |
| 10 | WP-KORG-REPRESENT-01 | Done | 无；纯构造及tokenizer验证见§14.6 | 不冒称真实向量效果或候选构建已通过 |
| 11 | WP-KORG-COMPARE-01 | In Progress | §14.41按§6.4作有限B不采用决定；215项盲标仍未评、A未评价 | 该否决不需要为不会改变决定的precision补标签；不能据此关闭整个COMPARE、A或RELEASE，不复跑/追加对照 |
| 12 | WP-KORG-RELEASE-01 | Blocked | WP-KORG-COMPARE-01 | 等待直接前置；发布还需§7/8证据 |
| 13 | WP-KVERIFY-DRYRUN-01 | Done | §14.40同路径正反向测试、预算、取证/清理及独立代码复评通过 | 仅验证工具non-live范围关闭，不证明真实测量就绪或效果 |
| 14 | WP-KRETRIEVAL-DIAGNOSE-01 | Done | §14.42纯离线实施、封存重放、直接测试及独立复评通过 | 仅可观测损失及unknown交接，不证明召回提升或授权新真实操作 |

### 9.1 恢复推进的基线与验证选择

以下是当前证据支持的后续选择，不是新增实验授权，也不改变§5工作包状态或§7完成条件。已完成DRYRUN、DIAGNOSE及§14.43诊断不重做，旧失败目录和预算不复用。

| 选择 | 已核实限制 | 后续处理 |
|---|---|---|
| 沿用旧解析恢复A | 首份冻结附件ordinal 51/58/103/109为paragraph；`chunking_v2.py`对疑似标题强制`review_required`，即使补独立proofRef也不能发布。第三份旧187块与当前179原生段落不同；既有HWPF核对删除空白/控制字符，不是精确跨度证明 | 不以补proofRef、缩样本或放宽validator放行。A保持Not assessed |
| 固定新解析后比较切片 | 先证明新解析的顺序、结构及无遗漏，再让两臂消费同一解析源；直接把现行b2与新parser/chunker产物比较会混入解析变量 | 属于需另行决定的A基线重准备；完整竞争池检索需新解析＋旧chunker基线和新解析＋v2chunker候选两套索引。现构建器不支持前者；不自行扩大候选额度或更换源绑定 |
| 既有文号修正的全检索链对照 | §14.43已确认003的keyword必要来源恢复、三题top20未变；但vector/融合/rerank/final20及其余题尚未验证 | 推荐优先准备独立无付费、只读对照：两臂同b2完整竞争池、同模型/配置/gold，仅旧/当前`DocumentNumberQuery`不同；不新建索引，不修改线上排序、窗口或正文 |

最后一项沿用L2_01_01文号软匹配及§9.9的有限诊断边界，**不是第三项已获授权的A/B实验**，不能替代A、关闭整个COMPARE或直接解锁资料RELEASE。预期改善属于待测假设；003旧人工Failed及B不采用结论不改判。现四题keyword探针不能直接扩大，原B评分器把keyword变化视为混杂，也不能放宽后充当新协议。若维护者选择这一范围，先补独立私有协议与评估入口、核验单变量源码差异、冻结新run/HEAD、实际索引/策略及排他窗口，并完成fake预算、协议和清理反例，再执行新的独立只读批次。

从现有固定fixture的10个`retrievalDenominator=true`题、11个域单元可推导：成对typed search及物理search各≤44，共享query embedding≤10，成对rerank≤22；外部模型、Business、索引/alias写入、retry/resume均0。**这只是问题与路径数量的预算推导，不是完整可执行授权**：索引身份/全记录前后核验、Profile启动、健康检查和必要预热仍须按实际工具计算、分项冻结上限；不能继承旧全库fingerprint或隐去这些调用。precision仍须人工盲标，不由来源列表代填。

MEASURE另按UAT_02 §5.4准备独立授权与冻结，既定12题/gold/阈值及12 E2E、36模型、48 typed、12 query embedding、24 rerank、72正式ES元数据上限不自动增加；准备期全库读取和startup操作仍单独事前列明。新测量即使形成完整有效终态，也不能代替COMPARE的质量和资料发布条件。上述推荐顺序不新增DAG边或审批Gate；若缺范围确认，继续保留各包原状态，而非再做合成测试或重复付费调用。

## 10. 实施交接

以下“允许动作”界定工作包边界；当前目标的实际授权见§1，不能凭此表扩大外部调用或后续批次。源码/文件名若为拟议落点须先引用检查，不覆盖既有同名文件；各包严格沿用来源L2，不扩展公共能力。

| 工作包 | 允许动作 | 禁止动作 | 预期文件/模块 | 来源设计 ID | 测试与验证 | 开放后续门禁 | 建议执行技能 |
|---|---|---|---|---|---|---|---|
| WP-KREBUILD-DESIGN-01 | 复用设计输入，不重新实施 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | docs/design Knowledge三L2 | L2_01_00 §8 DR-KFLOW-201～205 | 文档来源/状态 | 不继承旧Gate；见§7/8 | design-doc-review |
| WP-KREBUILD-CONTRACT-01 | 内部意图合同及task12 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | agent-runtime/src/agent_runtime/knowledge：internal类型、intent_task_v12.py及直接fake tests | L2_01_00 §8 DR-KFLOW-201/202 | TEST-KFLOW-201 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KREBUILD-RETRIEVAL-01 | 原Q双路、域内融合/重排与有界配置 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | agent-runtime/src/agent_runtime/knowledge：planning、retrieval、ranking、配置loader及直接tests | L2_01_00 §8 DR-KFLOW-203；L2_01_01 §9 DR-KRET-201～204 | TEST-KRET-201～203 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KREBUILD-EVIDENCE-01 | minimal Evidence和Summary8 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | agent-runtime/src/agent_runtime/knowledge/evidence及直接tests | L2_01_02 §9 DR-KEV-201～205 | TEST-KEV-201～203 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KREBUILD-COMPOSE-01 | 唯一root迁移与历史隔离 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | agent-runtime生产组合根、tests；agent-service Spring E2E；es-query-service读取安全测试 | L2_01_00 §8 DR-KFLOW-204/205；L2_01_02 §9 | TEST-KFLOW-201～203 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KREBUILD-MEASURE-01 | 固定12题及一次独立测量 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | agent-runtime/tests/uat、evaluation/system_e2e的后续新资产；不覆盖历史 | L2_01_02 §9 DR-KEV-205；UAT_02 §5 | UAT-KM-001～012 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KORG-DESIGN-01 | 复用设计输入，不重新实施 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | docs/design Knowledge三L2 | L1_01 §4.6；L2_01_01 §18；L2_01_00/02 §19 | 文档来源/状态 | 不继承旧Gate；见§7/8 | design-doc-review |
| WP-KORG-NORMALIZE-01 | 标准化与可追溯sidecar | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | 既有离线语料工具模块及测试；追加sidecar，不改旧源 | L2_01_01 §18 DR-KRET-301～303；L2_01_02 §19 DR-KEV-301；L2_01_00 §19 DR-KFLOW-301/302 | TEST-KRET-301 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KORG-CHUNK-01 | 解析顺序修复、结构单元与连续span回放 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | 既有离线语料parser/chunk模块及tests，新版本并存 | L2_01_01 §18 DR-KRET-303/304 | TEST-KRET-302 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KORG-REPRESENT-01 | 独立检索表示及token前检 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | 既有离线语料表示模块、模型manifest及直接tests | L2_01_01 §18 DR-KRET-305/306 | TEST-KRET-303 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KORG-COMPARE-01 | 单变量有限对照 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | 后续离线评估Harness和受控候选索引验证资产 | L2_01_01 §18 DR-KRET-307；L2_01_02 §19 DR-KEV-304；UAT_02 §6 | UAT-KORG-001～012 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
| WP-KORG-RELEASE-01 | 选定候选兼容发布 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | 既有离线发布工具、es-query-service私有Profile/策略快照；不得扩展公共接口 | L2_01_00 §19 DR-KFLOW-303；L2_01_02 §19 DR-KEV-302/303 | UAT-KORG-012 | 发布证据及独立授权 | implement-from-detailed-design；code-review-against-docs |
| WP-KVERIFY-DRYRUN-01 | 同正式路径non-live演练及故障注入 | 无真实密钥/网络/服务、无新冻结、无修改历史或生产模式 | 当前MEASURE runner/prepare/startup/harness及launcher私有测试接缝 | DR-KFLOW-401～403 | TEST/VAL-KFLOW-401～403；脚本改动AST | 新真实运行仍须独立授权、实际部署与快照前检 | implement-from-detailed-design；code-review-against-docs |
| WP-KRETRIEVAL-DIAGNOSE-01 | 纯离线冻结证据诊断及最小修正建议 | 不读现库、不推理、不改gold/策略/旧终态，不把grep放在线Runtime | 现evaluation及B trace reader，有限公开合成fixture | DR-KRET-401～403 | TEST/VAL-KRET-401～403；来源与阶段人工核对 | 新只读诊断和在线修正另定范围，不自动消耗旧预算 | implement-from-detailed-design；code-review-against-docs |

## 11. 风险与阻塞

| 风险 ID | 工作包 | 类型 | 触发条件 | 影响 | 缓解/解除条件 | 责任方 |
|---|---|---|---|---|---|---|
| RISK-KNEW-001 | WP-KREBUILD-COMPOSE-01、WP-KREBUILD-MEASURE-01 | compatibility | 将Summary9接入旧quality输入，或同时注册8/9、只改Prompt | 新旧合同错配、历史结果失真 | 原12/8证据保持原证明范围；当前12/9/minimal唯一绑定及历史隔离验证；禁用或整套相容恢复 | 实施者 |
| RISK-KNEW-002 | WP-KREBUILD-MEASURE-01 | evidence | 来源不足、人评缺失或绑定漂移 | 新质量无可判证据 | 按UAT_02保留source_gap/Not assessed；不补造gold，不自动候选循环 | 维护者 |
| RISK-KNEW-003 | WP-KORG-COMPARE-01 | attribution | 同时更换切片、表示、模型或语料 | 无法归因 | 单变量、完整竞争池、固定来源span与分母；未知不是通过 | 实施者/维护者 |
| RISK-KNEW-004 | WP-KORG-RELEASE-01 | rollback | 只恢复代码而未恢复相容数据/策略 | 发布不可用或越权 | 独立记录代码、模型、配置/策略、索引/部署绑定并演练；不删除旧索引 | 发布维护者 |
| RISK-KNEW-005 | WP-KORG-NORMALIZE-01 | authority | 公共DTO/父读取/权限变更成为前置 | 超出批准设计 | 暂停相关包，明确最小设计及授权范围；不借计划自创合同 | 维护者 |

旧P3中四项Deferred旧效果/阶段B工作仍是未完成、执行已终止；四项图谱/联合UAT为历史Blocked、未来待决策。它们均不迁入当前关键路径，也不被改判。原非Knowledge工作包未发现未完成项；完整逐项处置见迁移清单。此结论只覆盖旧计划登记项，不是全仓完成审计。

## 12. 追踪矩阵

下列ID来自三L2，路径落点见§10。NORMALIZE中的关系基础与CHUNK中的结构跨度共享IMPL-KRET-302的不同切片，不形成第二实现；比较/发布同理。跨主线安全测试按各自目标版本重新验证，不强制另一主线完成。

| 工作包 | 来源 REQ/CON/DR | IMPL | TEST | VAL | 交付状态 |
|---|---|---|---|---|---|
| WP-KREBUILD-DESIGN-01 | 设计输入；REQ-KQ-201～205 | 已批准三L2，不新增代码 | 原设计文档复核 | 原设计验证；本轮仅引用核实 | Done |
| WP-KREBUILD-CONTRACT-01 | DR-KFLOW-201/202 | IMPL-KFLOW-201 | TEST-KFLOW-201 | VAL-KFLOW-201 | Done |
| WP-KREBUILD-RETRIEVAL-01 | DR-KFLOW-203；DR-KRET-201～204 | IMPL-KFLOW-202；IMPL-KRET-201～203 | TEST-KFLOW-202；TEST-KRET-201～203 | VAL-KFLOW-202；VAL-KRET-201～203 | Done |
| WP-KREBUILD-EVIDENCE-01 | DR-KEV-201～205 | IMPL-KEV-201～203 | TEST-KEV-201～203 | VAL-KEV-201～203 | Done；仅组件fake/non-live |
| WP-KREBUILD-COMPOSE-01 | DR-KFLOW-204/205；DR-KEV-204 | IMPL-KFLOW-202/203；IMPL-KEV-203 | TEST-KFLOW-202/203；TEST-KEV-203；原37风险新版映射 | VAL-KFLOW-202/203；VAL-KEV-202/203；UAT_02 §3 | Done；36项fake/non-live直接证据，EV006语义充分性按§12交MEASURE |
| WP-KREBUILD-MEASURE-01 | DR-KEV-205/206；DR-KRET-204 | IMPL-KEV-203；IMPL-KRET-203 | UAT-KM-001～012 | VAL-KEV-203；VAL-KRET-203；UAT_02 §5 | In Progress：Summary9仓库non-live范围保持；001/002人工Passed、003/004人工Failed，005技术失败、006～012未执行，整批仍invalid_run；历史失败不复用或改判 |
| WP-KORG-DESIGN-01 | 设计输入；REQ-KCORPUS-001～006 | 已批准三L2资料章节，不新增代码 | 原资料设计复核 | 原有限审计与文档验证 | Done |
| WP-KORG-NORMALIZE-01 | DR-KRET-301/302及303的来源版本前提；DR-KEV-301；DR-KFLOW-301/302 | IMPL-KRET-301；IMPL-KEV-301；IMPL-KFLOW-301/302 | TEST-KRET-301；TEST-KEV-301；TEST-KFLOW-301/302 | VAL-KRET-301；VAL-KEV-301；VAL-KFLOW-301/302的离线/来源部分；UAT-KORG-001～004/009仅来源身份、附件关系与fake授权部分 | Done；仅本包离线/有限来源部分 |
| WP-KORG-CHUNK-01 | DR-KRET-303/304；DR-KEV-302/303 | IMPL-KRET-302；IMPL-KEV-302 | TEST-KRET-302；TEST-KEV-302 | VAL-KRET-302；VAL-KEV-302的结构/span部分；UAT-KORG-004的unit父子关系、005/006/008 | Done；仅本包fixture/结构部分 |
| WP-KORG-REPRESENT-01 | DR-KRET-305/306；DR-KEV-302/303 | IMPL-KRET-303；IMPL-KEV-302 | TEST-KRET-303；TEST-KEV-302 | VAL-KRET-303；VAL-KEV-302；UAT-KORG-003/007/008 | Done；仅纯构造/固定tokenizer |
| WP-KORG-COMPARE-01 | DR-KRET-307；DR-KEV-304 | IMPL-KRET-304；IMPL-KEV-303 | TEST-KRET-304；TEST-KEV-303；UAT-KORG-001～012 | VAL-KRET-304；VAL-KEV-303；UAT_02 §6 | In Progress；§14.41有限B不采用，原typed44/embed10/rerank22及recall均0.85保持；215项盲标缺失、precision为null，A及完整资料质量未通过、候选未发布 |
| WP-KORG-RELEASE-01 | DR-KFLOW-303；DR-KRET-307；DR-KEV-302/303 | IMPL-KFLOW-303；IMPL-KRET-304；IMPL-KEV-302 | TEST-KFLOW-303；TEST-KRET-304；TEST-KEV-302 | VAL-KFLOW-303；VAL-KRET-304；VAL-KEV-302；UAT-KORG-012 | Blocked |
| WP-KVERIFY-DRYRUN-01 | KQ-AD-029；DR-KFLOW-401～403 | MEASURE runner/prepare/startup/launcher私有接缝及冻结PLAN，落点见L2_01_00 §20 | TEST-KFLOW-401～403 | VAL-KFLOW-401～403；UAT_02 §5.6 | Done；§14.40仅工具non-live可靠性，不继承真实UAT通过 |
| WP-KRETRIEVAL-DIAGNOSE-01 | KQ-AD-030；DR-KRET-401～403 | 离线evaluation/trace reader及有限内存来源定位，落点见L2_01_01 §9.9 | TEST-KRET-401～403 | VAL-KRET-401～403；UAT_02 §6.4 | Done；§14.42，unknown不自动升级策略或框架 |

跨阶段验证按以下责任切片执行，不新增VAL、工作包或门禁。实际验证记录注明已执行部分、结果及未执行部分的承接包；不得将部分通过写成整个VAL或整套UAT通过。

| 本包/相关验证集合 | 本包完成所需部分 | 后续承接，不作为本包反向前置 |
|---|---|---|
| RETRIEVAL：VAL-KFLOW-202、VAL-KRET-201～203；EVIDENCE：VAL-KEV-201～203 | 新组件的定向单元/契约、fake集成、类型及安全反例；含原问/数量/失败优先级、Evidence/引用和离线计分反例 | current-root/Spring及成对接线回归由COMPOSE承担；真实召回、摘要效果和人工评价由MEASURE承担 |
| COMPOSE：VAL-KFLOW-202/203、VAL-KEV-202/203、UAT_02 §3 | 目标生产对象图的non-live接线、Spring/Java安全、37风险新版证据及相关历史/Business防回退；保留§5代码评审完成条件 | VAL-KEV-203的有限真实/人工评价由MEASURE承担；non-live通过不证明真实效果 |
| NORMALIZE：VAL-KRET-301、VAL-KEV-301、VAL-KFLOW-301/302；CHUNK：VAL-KRET-302、VAL-KEV-302 | 各自有限fixture的来源/字段/关系或结构/span验证；CHUNK另证DOCX源顺序、unit完整性与chunk集合覆盖分离、保守/复核分流及人工结构核对；对应契约/fake安全反例，仅验证各自变更范围 | UAT-KORG-009的真实typed部分及VAL-KEV-302的候选只读证明由COMPARE承担，发布绑定验证由RELEASE承担 |
| REPRESENT：VAL-KRET-303、VAL-KEV-302 | 纯表示构造、固定tokenizer长度/版本、无截断及派生上下文不能成为quote的unit/contract/fake验证 | VAL-KRET-303的BGE对照及VAL-KEV-302的真实typed部分由COMPARE承担；不以推理服务就绪作为纯构造包完成条件 |
| COMPARE：VAL-KRET-304、VAL-KEV-303、UAT_02 §6；RELEASE：VAL-KFLOW-303、VAL-KRET-304、UAT-KORG-012 | COMPARE完成预先冻结协议内的fake、人工原文及当前目标限额内BGE/隔离typed对照；涉及回答质量时满足当前一次模型批次与事后人工评价条件，未评维度明确记录 | 线上alias/部署、选定候选发布绑定及发布回滚由RELEASE承担；COMPARE的fake回滚不代替RELEASE真实发布验证，测量完成不自动满足发布质量条件 |

## 13. 自检记录

文档审查与实施验证分开；本节只维护新计划实际文档复核结论。2026-09-14计划迁移的三轮内审及两轮同一执行者分阶段正式复核完成，最终S0/S1/未处理S2均0；记录由当次[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)集中承载；不得把源设计旧轮次写成本轮轮次。

2026-09-15限定澄清完成一轮自检、措辞补齐及复核（同一执行者，非整套设计重新评审）：REV-P3-001的跨阶段VAL分工、REV-P3-002的资料缺口/安全停止边界、REV-P3-003的四处L2章节指向均已处理。P3及三份L2严格校验零错误/警告；12包/12直接边、状态、37+12+12用例、阈值/预算及设计追踪编号保持不变，36个本地链接可解析。仅五份当前文档本地修改，历史资产/代码/测试/配置未改；未执行实现、UAT或Git提交推送。

2026-09-24结构单元补充执行两轮内审：第一轮核对文档类型、解析顺序、unit/content版本和可恢复span，修正根单元可无`parentUnitId`及版本身份；第二轮核对在线授权/引用、unit完整性与chunk覆盖、保守切片分流、P3直接依赖及UAT边界，修正缺块不得发布和解析异常必须复核的条件。随后由同一Codex任务内未参与起草的只读执行单元进行分层/跨层复评，目标七文档范围内S0=0、S1=0、未处理S2=0；该复评不冒充外部人员评审，也不证明新设计已实施。L0_00第78行及L1_00第13、94～96行中的Knowledge文档版本引用仍为v3.1，属本轮未授权文档的元数据欠账，接受为范围外S2并明确需另获这两份文档的引用修订授权；不得声称全套跨层版本引用已完全同步。

2026-09-29对v3.4目标七文档执行只读分层/跨层复评，范围内S0/S1/未处理S2均0；五份P3/L1/L2严格校验零错误、零警告，目标文档88条本地链接均可解析，12包/12直接依赖无环。评审对象是计划与阶段证据表述，不是六个未闭合UAT风险、真实效果或发布的通过结论；范围外L0/L1_00旧版引用仍待处理。

## 14. 当前结论

当前Done=11（两项来源设计、CONTRACT、RETRIEVAL、EVIDENCE、COMPOSE、NORMALIZE、CHUNK、REPRESENT、DRYRUN、DIAGNOSE）；In Progress=2（COMPARE、MEASURE）；Ready=0；Blocked=1（RELEASE），各阶段证据见§14.1～14.43。DRYRUN只证明正式验证工具的non-live可靠性，DIAGNOSE只证明有限离线损失诊断，二者不是新真实批次或检索质量证明。仓库Knowledge enabled root接线selector v5/12/9/minimal-v1，disabled保持v4；v5仅有non-live证明（§14.38），不反向替换旧批次的selector v4。Summary9机械non-live与代码复评、Spring合成三模式及有限失败路径已通过，但旧12/8与新12/9证据不能拼接为新版37/37。单域只读预检和最新四题的有限端到端记录不证明完整两域链路、常规生产部署或新版UAT通过。最新B（§14.32）10题协议完整且保存traces，双臂recall@20均0.85、主指标未改善，215项人工盲标仍缺、precision为null；§14.41已作不采用决定，A仍Not assessed，候选只读未发布。最新MEASURE（§14.33）完成001～004后005技术失败，模型13/typed8/embedding4/rerank4，整批failed_consumed / invalid_run；§14.37维护者确认001/002 Passed、003/004 Failed，005根因仍未知、006～012未执行。各旧失败批次保持原终态，不补跑、续跑或复用余额。另获授权的§14.43词法诊断确认003必要来源由旧keyword top20无命中提升至当前第1，001/002/012的keyword top20完全相同；012仍缺两项必要来源，不能证明双路、回答或整体质量提升。观测与动作选择修复仍只具non-live证明。保留现行b2，没有合格候选或发布完成证据，完整测量与新版UAT尚未完成。

### 14.1 CONTRACT完成证据（2026-09-15）

`WP-KREBUILD-CONTRACT-01`已完成，代码提交`21983d8332ebddda31b8cc8a98afad9a26734416`，交付`intent_contracts.py`、`intent_task_v12.py`及三份直接unit/contract/fake Gateway测试。当前核查起点`7b98da62be6c86eae593bf4e4d9c2e9228bc781b`的五份文件与该提交无差异；本轮重新执行直接测试255 passed。原实施轮次另有Knowledge及防回退、strict mypy、compileall证据，本处不冒充本轮全量执行。

独立内部合同不改变旧task11/Summary7/quality-v3生产绑定，也不证明新链路或真实UAT通过。完成状态仅适用于本包TEST/VAL-KFLOW-201；RETRIEVAL和EVIDENCE的直接技术前置已满足。

### 14.2 RETRIEVAL完成证据（2026-09-15）

代码/测试提交`1762fd860cc95631256edea344bd8f22e074e6b6`（本地`codex_0915`，未推送）。交付`knowledge/minimal_plan.py`、`retrieval/minimal_stage.py`、`retrieval/minimal_ranking.py`及四份直接测试；不修改旧Stage、quality ranking、Provider、root、任务、公共DTO、模型/索引绑定或历史资产。`tests/evaluation/knowledge/live`下17份已跟踪历史资产的Git blob与本轮起始HEAD逐项相同（0差异）；离线评价测试另核验所引用的冻结评价文件SHA-256，未将未读取的其他运行资产宣称为全量SHA审计。

| 设计/验证 | 本包实现及证据 | 后续边界 |
|---|---|---|
| DR-KFLOW-203 / TEST-KFLOW-202 | 独立schema3计划，安全原Q/模式/目录/固定Profile不可变；配置只能收紧域、partial阈值和时限；错配零端口调用 | Capability/公开reason接线由COMPOSE完成 |
| DR-KRET-201 / TEST-KRET-201 | 每域原Q keyword/vector各20；请求内1次1024维embedding，最多4次typed search；全部候选hash/快照/身份冲突在评分前检查 | 真实实例授权及索引快照未读取；沿用现有typed Adapter |
| DR-KRET-202/203 / TEST-KRET-202 | 域内RRF60→一次BGE重排（每域40，总80，串行≤2）；确定性并列、跨域轮转final20、来源合并、无锚点/需求标签；读取拒绝取消并join、partial阈值、全失败不冒充无结果、超时迟到结果丢弃 | 无新连接池；不切root、不声称完整Spring链路已迁移 |
| DR-KRET-204 / TEST-KRET-203 | 复用现有离线metrics/relevance反例：来源hash与绑定漂移拒绝、同池未标注不计分/null及历史SHA校验；无在线gold依赖 | 按L2_01_01 §9.4，IMPL-KRET-203的新同池比较资产和只读真实测量留待MEASURE；历史协议测试不证明新策略效果 |

本轮执行结果（集合有重叠，不相加作总数）：

| 验证集合/命令 | 实际结果 |
|---|---|
| `python -m pytest -q -p no:cacheprovider` + 下列四份直接测试 | 最终116 passed；含5个内存transport+现有ES/BGE Adapter集成场景，不建立网络服务 |
| `python -m pytest -q -p no:cacheprovider --basetemp <本次唯一临时目录>/pytest tests/unit/knowledge tests/contract/knowledge tests/integration/knowledge tests/evaluation/knowledge/test_retrieval_metrics.py tests/evaluation/knowledge/test_query_representation_relevance.py` | 2084 passed / 6 opt-in skipped / 0 failed；271.57s。此较大回归后补齐的边界由最终116项定向复核覆盖 |
| 四份直接测试 + `tests/unit/test_business_query_plan_composition.py tests/unit/test_action_resolution_composition.py tests/integration/model/test_runtime_composition.py tests/system_e2e/test_runtime_composition.py` | 140 passed；之后两项policy ID边界计入最终116，不重复冒充新root测试 |
| `python -m pytest -q -p no:cacheprovider tests/unit/core tests/unit/capability_api tests/unit/business tests/contract/business tests/integration/business tests/unit/adapters/employee tests/unit/adapters/transaction tests/contract/adapters tests/integration/graph tests/unit/api` | 360 passed；旧公共链路及Business关键防回退 |
| `python -m mypy --strict src/agent_runtime`；`python -m compileall -q src/agent_runtime` | strict mypy 147源文件通过；compileall通过 |
| P3 `validate_implementation_plan.py --file <本文件> --strict`；Git差异、范围与敏感信息检查 | 零错误/警告；12包/12直接边无环；只新增本包代码/测试及更新P3，不修改历史资产 |

四份直接测试：`tests/unit/knowledge/test_minimal_retrieval_plan.py`、`tests/unit/knowledge/retrieval/test_minimal_ranking.py`、`tests/unit/knowledge/retrieval/test_minimal_stage.py`、`tests/integration/knowledge/test_minimal_retrieval_adapters.py`。

复现环境：Python3.12，测试工作目录`agent-runtime`，进程级`PYTHONPATH=D:/codex/agent-runtime/src`；历史fixture读取Git需进程级`GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=safe.directory`、`GIT_CONFIG_VALUE_0=D:/codex`，不修改全局Git配置；含tmp_path的集合每次创建唯一临时目录并显式`--basetemp`。一次额外root回归漏设此前置出现3项setup error，正确设置后140项全部通过；未改变测试断言。初始定向失败分别定位为合成问题触发现有Guard、吞取消后的迟到结果，以及测试JWT helper名称错误，均已按原合同修复/补反例。P3严格校验要求的Ready授权声明已保留；未放宽校验器。

代码对照复核为同一执行者两轮（非外部独立评审）：REV-KRET-001超时/取消被端口吞掉后仍可能推进下一阶段，已以timeout.expired/task.cancelling及零后续反例修正；REV-KRET-002读取策略ID应沿现有typed Adapter的256字符合同，已修正并验证256/257边界。同时核对已完成拒绝与畸形响应的优先级、并发请求隔离、Q/向量不缓存、有限排序及历史调用方不变。最终本包无未关闭Blocker/Major；不替代COMPOSE发布评审。

6项跳过均需独立live/历史Gate opt-in（真实egress诊断4项、真实检索2项）；本轮无模型、BGE或ES实际调用，无密钥读取、服务启动和索引操作。现有LangChain反序列化默认值弃用提示不在本包修改范围。未执行全仓Python、Java/Maven、Spring跨进程E2E或真实UAT；P3 §12明确由后续COMPOSE/MEASURE承接。现有输入Guard仍可能拒绝无可识别税务语义的问句，本包不放宽该边界；原问相关性、top20噪声及512token重排窗口效果仍待实测。

### 14.3 NORMALIZE启动证据与未闭合条件（2026-09-24）

本地`codex_0915`提交`96cf200c5cc9009a8e587ef75de179a6ddeb6fb6`新增离线`normalization_v2.py`与15项直接测试；严格v2侧车、来源断言、不可变身份claim、原始资产hash、父附件/修订关系、规范解析源span及结构可信状态均有合成正反例。它不接入旧解析、索引构建或在线查询，旧DOCX乱序和扁平表格不被标为已验证。独立只读代码对照复评的阻断/高风险问题已修复，最终Blocker=0、High=0；该评审不证明真实来源或资料效果。

Python3.12隔离环境执行`python -B -m pytest -p no:cacheprovider --basetemp <唯一工作区临时目录> --tb=short tests -q`，`knowledge-corpus-tools`全包306项通过；直接`tests/test_normalization_v2.py`为15项通过。`mypy --strict src/knowledge_corpus_tools/normalization_v2.py`与`compileall -q -f`通过。对一份既有官方附件执行只读抽样：本地文件SHA-256、旧asset manifest及旧parsed record hash相同，父文档ID一致；这是有限历史资产交叉核对，不等于新v2全量来源清单或当前官网复核。截至2026-09-24，当时尚须对冻结来源记录、完整父清单及结构证明作人工核验，关闭`VAL-KRET-301`后才能将本包标Done、解除`DEP-KORG-002`；后续有限核验与边界见§14.4。未知`aging/channel`映射保持unknown，不补造时效或文档类型。本轮没有模型调用、索引/alias写入或在线父单元补取。

先前§13自检记录中的L0_00、L1_00旧版引用欠账，已在另获明确授权后由本地提交`c7f69edc37e41fc4a087e6b24839740db3e664a8`精确修正五处元数据；原复评当时的范围结论保留，不冒称该复评已覆盖后续修改。

### 14.4 NORMALIZE有限来源核验与关闭边界（2026-09-28）

只读复核冻结`corpus_audit.v3.jsonl`：5597条、5597个唯一`documentId`，文件SHA-256为`ccdbfbe9983925f937421f31e0717387368416389c636a752544b3c2a506d272`，与既有summary一致。candidate-08的1份官网HTML与4份附件共5项，原始bytes SHA-256及字节数均与既有asset manifest一致，均指向清单中的同一父ID；官网当前页面的标题、文号和四个附件链接与保存的HTML及manifest对应。两个标称`.docx`的附件实际为旧`.doc`字节，原manifest已标`format_mismatch=true`。核对的是全父身份清单的唯一性和这5份有限资产的来源/父子关系，不是逐篇证明5597项的官网可达性、时效或正文完整性。

旧解析记录的749个块序号连续，但`quality=accepted`不构成原文件结构或顺序的独立证明；原DOCX及扁平表格仍为`unverified/review_required`。§14.3当时提出的“结构证明”在本包只能核对其有无并准确记录可信状态，不能要求把无证明资产提升为`verified`；缺证明的内容仍阻断对应候选发布。据此只关闭NORMALIZE的离线合同、fixture及`VAL-KRET-301`有限来源核对部分，解除`DEP-KORG-002/003`。尚未为真实语料批量生成v2 sidecar，也未修改索引/alias；这些不是本包Done的含义，由后续COMPARE/RELEASE按各自范围验证。

### 14.5 CHUNK离线实现、验证与复评（2026-09-28）

新增`chunking_v2.py`及`parse_asset_v2`接缝，保持旧parser/chunker和在线链路不变。v2对同一原始bytes先核资产SHA再解析；DOCX保留段落/表格交错顺序，HTML/PDF/DOCX仅在有限可靠边界识别章、节和条。结构单元以同版本源span、parser及hash派生稳定身份；chunk内容必须逐字等于规范解析源的连续子串，条号从原文核对，扁平表格的`tableId`不冒充可信定位。单元完整性与chunk覆盖独立记录；超长无安全边界、短块、表格关系未知及疑似无空格标题均显式保守处理，受影响结果不可发布；无在线父单元补取。

本轮使用隔离Python 3.12环境执行`tests/test_parsing_v2.py tests/test_chunking_v2.py`共21项通过；`knowledge-corpus-tools/tests`全包327项通过；两份修改源码严格mypy与compileall通过。独立只读代码评审初轮发现条号未绑定原文、v2资产hash未校验及真实解析层级缺口，修复并补反例后复评Blocker=0、Major=0。接受Minor=1：无空格“第…节”也可能是普通引用句，首期统一`review_required`并待人工核对，不用猜测标题来换取表面覆盖；测试覆盖此保守路径。评审是同一任务内另一只读执行单元，不冒充外部人员。此处只证明离线代码/fixture合同，未执行真实资料重切、embedding、索引发布、在线UAT或效果测量。

### 14.6 本目标的阶段实施、验证及未关闭条件（2026-09-29）

本轮已在`codex_0915`本地提交独立`minimal_selection.py`、`summary_task_v8.py`、检索表示与tokenizer前检（`65bb9beb`），目标`intent12 / Summary8 / knowledge-minimal-v1`唯一组合根及直接non-live测试（`25b5eb78`），以及与旧`vector_candidate.py`分离的`rechunk_candidate_v1.py`及fake测试（`a067d1d6`）；均未推送。默认disabled不装配Knowledge依赖；旧11/7任务及历史资产没有被覆盖。此为仓库实现状态，不证明当前部署已更新。EVIDENCE、REPRESENT按各自组件合同标Done；COMPOSE仍待§5所列37风险补证及真实typed接缝，COMPARE仍待真实资料、索引和效果对照。

新候选构建器的**本轮可执行A范围仅为经预登记且可核验全篇span的`tax.policy`附件**；它不是对正文、`tax.law`或全部资料类型的重切承诺。未受影响的policy/law/无分类记录仍须全量保留并验证。若A的人工样本需要正文或law重切，不能让现有工具静默跳过或把附件结果外推；先记录为范围不匹配，当前A不执行。B固定同一chunk集合、正文和模型，只对预登记表示作单变量比较。A/B的人工必要原文、主指标、噪声及延迟容忍值尚未确认，真实A/B的BGE推理、ES候选写入和候选发布均为0；不以fake测试代替真实构建。

| 本轮实际执行或复评 | 结果与证明边界 |
|---|---|
| `agent-runtime/scripts/run-nonlive-regression.ps1 -PythonExecutable C:\Python312\python.exe` | Transaction host/preflight **14 passed**；正式隔离Python全量 **5332 passed、27 opt-in skipped、0 failed**，1条既有警告。全量收集时`UG`为11项；其后新增的unsupported路由用例已单独执行`UG`全文件**12 passed**，不伪装为已进入该次全量。未执行live opt-in或真实Knowledge端到端测量 |
| `knowledge-corpus-tools`直接构建器fake、全包、严格类型与编译 | `tests/test_rechunk_candidate_v1.py` **43 passed**；全包 **428 passed**；`mypy --strict`、`compileall`通过。三个新增反例保证源block整块遗漏、部分跨块和重复span在准备向量/clone前失败关闭 |
| 在线组件、Spring接缝和Java模块 | 当前root直接fake、Spring→Runtime Knowledge non-live、Business/Core/Employee/Transaction关键防退通过；本轮Maven：es-query-service 99、common-security 21、employee-service 50（20 skipped）、agent-service 42（3 skipped）、Transaction 37（2 skipped），均无失败。Java数字按各模块原报告口径，不相加为UAT总数 |
| 隔离es-query-service真实typed只读预检 | 以当前v2 binding核实policy read alias唯一目标、UUID、mapping和policy/law snapshot；本次自有127.0.0.1:19201进程仅关闭无关DB健康子项，health其余组件UP。`tax.law` keyword typed POST 1次返回HTTP 200、5个候选，ES search计数+1；missing/malformed/service token各401，unknown-role 403，四个拒绝响应均无`candidates`/`content` JSON字段；BGE/LLM/rerank及ES/alias写入0。进程已停止、端口释放。只证明隔离typed读取与入口拒绝，不证明完整服务生产健康、当前root真实typed全链、跨域或新候选对照；未做拒绝响应与全部真实原文逐字比对 |
| 类型/源码与评审 | `agent-runtime` strict mypy **150源文件**、compileall通过。组合根及构建器由同一任务中未参与相应实现的执行单元只读复评，最终Blocker/Major/Minor均0；构建器最初原文覆盖Major已修复并重跑43例；自审和此复评都不冒充外部人员或真实效果评价 |
| UAT_02 v3.4逐项追踪 | 新版37项风险中31项有直接fake/non-live阶段证据，6项仍部分/缺证；因此新版Functional/Safety整体尚未Passed。仅隔离单域typed只读预检有有限结果；当前root端到端typed、人工12题效果和发布Not assessed |

维护者已要求先审阅12题草案及原文定位。草案中部分原题缺当前索引直接来源，替换提议尚未获确认；精确问题、必要来源/span/gold、A/B阈值和人工rubric均未冻结。未读取`LLM_API_KEY`，无真实外部模型请求、BGE推理、ES候选写入或线上alias切换。不能将MEASURE或RELEASE标Done，也不能把历史部分有效效果移作本版证明。

### 14.7 COMPOSE补证及COMPARE只读前检（2026-09-29）

§14.6是v3.4当时的阶段快照；以下是之后的新增证据，不改写该次5332项Python全量或Java模块测试计数。Spring→当前Runtime的non-live测试仍执行16个合成case，新增每案有限`typedSearches`域/路径/Profile和调用计数：政策、法律各keyword/vector两路，双域共四路；拒绝读取案Summary与Business调用0、公开result缺失且三条合成正文不出现在响应、运行日志或有限evidence。测试适配器逐请求核对用户JWT透传，不记录令牌；请求级`ContextVar`与双请求事件屏障反例避免并发串案，有限证据校验器拒绝把错误域路径标为`passed`。定向Python `agent-runtime/tests/system_e2e/test_knowledge_nonlive_runtime.py`为3 passed，定向Java `AgentKnowledgeNonLiveE2ETest`为1测试方法/16合成case通过；`policy_missing`已有独立未绑定文档策略反例，另行定向执行1 passed。受影响测试代码经同目标内另一只读执行单元复评，Blocker/Major为0；其复评不代替真实服务集成或效果评价。

因此COMPOSE只按§5/12的**仓库接线与non-live范围**关闭。UAT_02 v3.5的37项风险中36项具有该阶段直接证据，EV006解释/适用性实质充分性由MEASURE的真实输出与维护者人工rubric判定；当前root→真实es-query-service typed整链及实际部署仍Not assessed，Functional/Safety总体不得标Passed。MEASURE虽因直接依赖满足而转Ready，人工gold/冻结绑定未完成前仍不得启动付费调用。

COMPARE的独立只读执行单元对预登记4份附件核对原始SHA后仅在内存执行v2解析/切片：旧738个chunk对应新100个；这4份样本的有序block文本/hash/种类和parser版本与冻结旧解析相同，不代表其他资料亦如此。按历史b2总量15521估算，A候选构建器上限为ES HTTP 375、写操作838、embedding批次4，低于代码硬限；**这只是历史基数预算预估，不是当前索引冻结或候选构建**。四份v2输出均`publishable=false`，因结构单元缺独立顺序/结构证明，第一份还有4个`review_required`歧义单元。不得伪造`proofRef`或把附件局部收益外推为正文、law或全类型改善。真实A/B前还须解决结构复核、分别冻结≤24题A/B原文gold与阈值、当前索引UUID/全量fingerprint和逐记录旧向量来源；本次BGE推理、ES候选/alias写入及LLM请求均为0。COMPARE继续In Progress，RELEASE继续Blocked。

### 14.8 当前root→真实typed单域只读接线预检（2026-09-29）

新增显式opt-in测试`agent-runtime/tests/system_e2e/test_knowledge_current_root_real_typed_optin.py`（本地提交`e6c8f1a2`）：先核对v2运行绑定、policy只读alias唯一目标、索引UUID和mapping，再用本轮构建的es-query-service JAR在`127.0.0.1:19201`启动自有隔离进程；`JAVA_HOME`固定Java 25，随机短期HMAC/JWT只供该进程及当前请求使用。当前`build_runtime`由stub配置与固定fake任务输出驱动，单域`tax.policy`的keyword/vector各向真实typed接口POST一次且均返回200；本地embedding调用1次，rerank上限1次，Business调用0，外部LLM调用0。HTTP客户端已关闭，自有Java进程停止且端口释放；索引、alias及正文均未写入。最终opt-in用例1 passed、单文件strict mypy与compileall通过；默认未显式启用时1 skipped。同目标内另一只读执行单元复评本测试Blocker/Major/未处理Minor均0。

首次启动诊断曾使随机临时HMAC值出现在pytest回溯中；该值仅属已退出的隔离进程，现已失效。测试随后将敏感值移出contextmanager参数、使用脱敏repr、关闭局部变量展示、只输出固定诊断码并在finally扫描临时日志；修复后复评和最终用例均通过。中途一次启动成功但只见1条typed路径，未按通过记录；加入有限路径/状态计数后，最终断言keyword和vector各一次。该预检只证明当前root的单域只读接线，不证明Spring全链、真实模型、Evidence/回答质量、两域权限矩阵、实际部署或新版UAT完成。COMPARE的结构证明、A/B gold及阈值仍缺；MEASURE的12题必要来源、人工rubric和冻结组合仍未确认，故没有读取`LLM_API_KEY`或启动付费批次。

### 14.9 12题草案原文定位与时效数据边界（只读，未冻结）

按UAT_02 §5.3固定风险类别整理12题候选问句：其中8题的拟定必要来源在当前policy alias目标`agent-doc-tax-policy-v5-20260907-vector-b2`（UUID `jJ5Ww3LCRWWycfDkUZvmdw`）可定位到具体chunk；其中2016年附件的3个拟用chunk可按当前`content`复算索引`contentHash`，其余8个拟用旧库存chunk的该字段与当前正文直接SHA-256不一致，历史字段口径尚未证实，不能称已按现行正文合同核对。当前typed服务会依据返回的`content`重新计算`contentSha256`，Runtime再校验；旧索引字段差异不直接证明在线Evidence失败，也不能替代原文人工核验。维护者尚未确认任何新gold、逐条相关性标签、完整预期或A/B阈值，故这只是审阅草案，不能据8/12定位启动MEASURE、补算指标或称人工验收已完成。官方政策法规库页面的有限核对支持公告原文期限、资源税法条号、增值税法第十/三十八条等短定位；2016年附件本轮仅有既存官方附件manifest及索引片段，官方DOCX直读未成功，不记为已完成独立原文复核。

时效前检发现一项明确字段错误：当前索引中《中华人民共和国增值税法》的`effectiveDate=2024-12-25`对应成文日期，而官网第三十八条写明2026-01-01施行。公告2022年第13号和2023年第6号原文执行期限均至2024-12-31，但索引`status=ACTIVE`、`validityStatus=UNKNOWN`且`expiryDate`为空；这些字段不足以判断今日效力，也不能把原期限自动推成后续政策结论。当前在线typed响应仅有`writtenDate`等已定义字段，本次不原地修现行索引；使用上述资料冻结时效题gold或构建/发布候选前，须核对官方现行状态与来源断言，按L2_01_01 §18的版本化资料合同修正候选并另行验证。不能据索引`ACTIVE`或错误`effectiveDate`生成肯定适用结论。COMPARE、MEASURE和RELEASE状态保持§5所列未完成。

### 14.10 COMPARE旧DOC节标题解析定向修复（2026-09-29）

四份candidate-08原始`.doc`附件的字节数及SHA-256与冻结manifest一致，当前解析重放的block数分别为342/149/187/60。首份附件ordinal 51、58、103、109为“第×节”标题，但冻结旧解析将其标为`paragraph`；根因是`.doc`的`parse_asset_v2`路径未启用已有的有界节标题识别。提交`ebede2ba`仅在v2路径启用该识别并将新输出的parserVersion改为`0.2.1+sections-v2`，历史`parse_asset`及冻结manifest的`0.2.1+structure-v1`不变。四份原件只读重解析后block数不变，首份上述四处均为`heading`；合成定向测试10 passed、`knowledge-corpus-tools`全包429 passed、受影响文件strict mypy通过，另一只读执行单元的定点代码复核无Blocker/Major/Minor。

这些结果只证明已提取文本的节标题分类及v1兼容，不证明原始Word表格、全文顺序或遗漏。隔离Word COM空实例虽设置禁宏、禁链接更新和只读预期，但退出未能立即确认清理；因此未打开任何原件或副本，最终确认Word进程为0、原件hash及目录不变。四份附件仍缺独立、可审计的原文顺序/结构证明，不能仅凭重解析一致性或补造proofRef改为`publishable=true`。该次记录时COMPARE仍In Progress；A/B人工gold、阈值、当前索引冻结及旧向量逐记录溯源尚未完成。本次解析修复与原件复核未写ES、未调用BGE或外部LLM、未切换alias。

### 14.11 COMPARE旧向量溯源与原件结构复核（2026-09-29，只读）

在当前write-blocked的b2目标（UUID `jJ5Ww3LCRWWycfDkUZvmdw`）中，按预登记的四个附件assetId有限查询，旧chunk共738条（342/149/187/60），无超时或失败分片。逐记录核对身份、asset版本和SHA-256；`vectorRepresentationVersion=policy-title-section-body-v1`、`vectorModelSnapshotSha256`与旧构建快照相符，按当前`content`及冻结旧表示算法分别复算正文、`vectorBodySha256`和`vectorInputSha256`，738条均一致。因此这四份附件的**旧向量逐记录来源前检**已有结果，不能仅因“只有全局快照”标为`legacy_unknown`；当前有限只读计数为15521，但此次未读取全库向量或计算全记录fingerprint，也未冻结完整当次模型快照和精确候选预算，不能据此启动真实A/B。

四份`.doc`原件的字节数与SHA-256再次匹配既有manifest；机器未找到独立的DOC结构解析器，重复当前`legacy_doc`路径及官方HTML旁证均不能证明原件表格、顺序和无遗漏，四份v2结果仍为`publishable=false`。在不补造`proofRef`的前提下，A的当前样本不准入；B可按事前登记的“原只读索引同chunk基线”规则独立准备，但人工gold、质量主指标及噪声/时延容忍值、当前全库fingerprint、当次同模型快照和精确预算未冻结前，仍不得运行BGE、写候选或声称对照完成。COMPARE为In Progress，MEASURE仅技术Ready，RELEASE为Blocked；本次只读核查未调用BGE/外部LLM或写ES。

### 14.12 COMPARE旧DOC原生段落与完整性前检（2026-09-29，未放行候选）

提交`39fa0322`只调整`parse_asset_v2`的`.doc`路径：固定`legacy-doc==0.2.1`，在提取前严格核验完整piece table、CP/FC边界及解码，再区分原生段落结束`\r`与段内手动换行`\x0b`；新`parserVersion=0.2.1+native-paragraphs-v2`。旧`parse_asset`与冻结manifest不改。对既有四份SHA绑定附件只读重放，v2 blocks为342/149/179/60，分别与隔离Apache POI HWPF 5.5.1辅助解析的非空段落数一致；第三份旧187个行块中的两组段内换行恢复为179个原生段落。五处段落hash差异经原始Word字段边界核查，均为8个非显示`HYPERLINK`代码/URL被既有清洗规则移除，8处中文显示文字仍保留；该有限样本中未发现有效正文因本修复丢失。

首次代码复核发现底层库会静默跳过越界piece、公开提取与v2复核可能共同漏字；新增v2专用严格预检及内存篡改负测后，独立复评该范围Blocker/Major/Minor均为0。实际复跑`knowledge-corpus-tools`全包440 passed、strict mypy 23 files成功；四原件原始SHA/字节数保持不变，第三份仅在内存篡改第二PCD时明确失败关闭。隔离解析辅助工具仍在忽略的临时目录，不构成持久独立`proofRef`。四份`parsed_source_v2`的order/structure仍为`unverified`，A的受影响候选仍`publishable=false`；人工gold、A/B主指标及噪声/时延容忍值也未冻结，故COMPARE保持In Progress、MEASURE仅技术Ready、RELEASE保持Blocked。本轮没有BGE/外部LLM请求、ES写入或alias切换。

### 14.13 COMPARE全库只读指纹与单变量边界复核（2026-09-29，未启动真实对照）

以仓库现有受限scanner只读扫描当前write-blocked的`agent-doc-tax-policy-v5-20260907-vector-b2`：read alias `agent-doc-tax-policy-v2-read`唯一指向UUID `jJ5Ww3LCRWWycfDkUZvmdw`，mapping SHA-256为`1c2ab9b48ae5b3fcd37b91fec883b6141d3616b2331cdf3a430ea4500a40db82`。69次ES只读HTTP完整扫描15521条及其1024维向量，每页≤250、单响应≤16 MiB；含向量全记录fingerprint为`fb285fc5e5e838fbccb2025f24c0f4472802b8beb7190247cefc9a2978b9a17d`，与冻结b2构建result一致。扫描前后definition、alias和计数不变，ES写入0；这是当前只读前检，不是新候选`CandidateSpec`的正式冻结或质量收益。

A原预登记四份附件的旧b2块数为342/149/187/60，第三份经当前v2原生段落解析为179块；直接用旧b2对当前v2产物会同时改变parser与chunker，不符合UAT_02 §6.1的A单变量判据。本轮隔离HWPF交叉核对仅证明v2提取文本的有限段落对应，尚不足以给四份旧解析源的完整顺序及结构出具持久独立`proofRef`；旧`accepted`及hash不能替代该证明。因此A保持Not assessed/未执行，不按效果失败记录，也不创建额外parser基线或缩小预登记样本来凑通过。若后续能对同一解析源独立证明完整结构并使`chunking_v2.publishable=true`，才重新核对A准入及两候选预算；否则B可按原b2同chunk/正文基线独立准备。

B所需的四附件738条旧向量模型、表示、正文和输入hash逐记录前检见§14.11，全库指纹前检已补齐；仍须维护者确认B精确范围、gold、主指标及噪声/时延容忍值，随后把当次source/alias/mapping、精确`update_ids`和表示binding冻结到正式spec，核对完整当前模型/tokenizer快照与旧快照的同一性并做无截断预检，按最终范围冻结精确调用及写入预算。若仍只替换738条且总数不变，工具公式给出的ES HTTP≤366、BGE batch≤24、写操作738仅为条件性上限，不是已批准的正式运行预算。本轮无BGE/外部LLM、ES写入、alias切换；COMPARE保持In Progress，MEASURE仅技术Ready，RELEASE保持Blocked。

### 14.14 COMPARE模型快照及旧DOC结构只读复核（2026-09-29，未冻结对照）

当前运行的`bge-m3-service`容器ID与冻结b2 `binding.json`相同。仓库快照探针只读核对容器、服务、实现、依赖及11个模型文件：旧完整快照SHA-256为`bb701284a410cc88e80816bea0f40c0420fd501ed30f879cd290802c5835b4ec`，当前为`8bfbd88036db6b21263f4927ad093a9e8995e28c4c4f08d94657e98d5deb6d96`；逐字段唯一差异是`container.started`由`2026-09-07T00:48:23.858361985Z`变为`2026-09-28T09:59:52.377452626Z`。四个tokenizer文件的映射hash均为`83715342856e72d33ecc6e5732eefccb01ba21ae1127ca4dd91160860e2f48d7`。这符合L2_01_01 §18.4.1允许的同模型快照差异，仅解除该项只读前检疑点；真实tokenizer无截断、正式spec、人工gold与预算仍未完成。

四份原件SHA/字节与manifest一致，冻结旧解析与旧`parse_asset`重放逐字段相等。隔离HWPF核对均无原生表格；非空原生段落为342/149/179/60，第三份旧187块多出的8块对应两段内的手动换行。当前辅助核对删除空白/控制字符后比较全文顺序，不能充当逐codepoint的持久独立证明。首份旧解析还将ordinal 51、58、103、109四个“第×节”标为`paragraph`并停留在旧章节路径；原件对应段虽无专用标题style，但均居中、首run加粗，与邻近正文格式不同。`chunking_v2`对此类块强制`review_required`。因此不能把旧解析标成结构已验证，也不能靠补`proofRef`放行现有A样本；A保持Not assessed。B可独立准备，但不得跳过§14.13的人工确认与正式冻结。本次没有BGE推理、外部LLM、ES写入或alias切换，COMPARE/MEASURE/RELEASE状态不变。

### 14.15 B表示接缝与待冻结条件（2026-09-29）

`L2_01_01` v3.7 §18.4.1 的源绑定及keyword混杂规则已完成定向内审及独立复评（S0/S1/未处理S2均为0）：B模式从同一次已核验的完整源扫描，按预登记`update_ids`确定性重建`body-only-v2`表示；外来表示tuple不能代替源记录，不能为此增加一遍ES读取或持久化正文。内部BGE准备接缝已在本地提交`a5f84f37`，构建器同源重建已在本地提交`9b5a45a2`；后者的48项定向fake及受影响文件strict mypy通过，独立定点代码复核无Blocker/Major/Minor。以上均不包含真实BGE、ES写入或typed对照。一次性入口、正式`CandidateSpec`仍待实施与冻结，不能据此关闭COMPARE。

维护者已确认先把A保留`Not assessed`、按当前b2相同chunk/正文优先准备B；12题草案的问句与必要来源按已批准的措辞调整作为后续冻结输入，既有UAT阈值保持不变。B的事前质量判据确认为必要来源宏平均`recall@20`严格提高、`precision@20`不低于基线、同机同条件median检索时延不超过基线的110%，且核心及保留题覆盖不退化。最终运行仍需逐题人工核实返回候选相关性、精确spec/预算和执行时快照；未取得这些证据时指标为`Not assessed`，不把草案确认说成真实对照完成。独立复核又发现CAS向量更新可能改变Lucene文档状态，B须核对keyword top20及UAT_02 §6.1的盲标、聚合、计时和混杂停止条件；否则不能归因或发布。另发现现有Summary8仅能摘录，不能完成已确认适用性题的有限明确回应；真实模型测量必须待上位回答设计修订、复评及non-live验证后重新冻结，本节不预记任何UAT或发布结果。

### 14.16 Summary9当前接线及B冻结设计复核（2026-09-29）

维护者授权REQ_00 §5.2、L0_00 §3、L1_01、L2_00_02及Knowledge L2中仅涉及“有引用有限判断”的最小修订；目标仍禁止无依据适用性肯定、放宽原文引用或改变公共DTO字段。设计提交`10f2f42c`经定向跨层复评S0/S1/未处理S2均为0。运行时取消传播修复提交`c1b886a8`，当前唯一root接线intent12/Summary9/minimal-v1及验证台逐点同屏引用提交`e58f4837`；Summary9独立任务输出经严格Schema、模式、逐点quote/ref/claim配对和连续原文校验。定向fake/non-live、Node展示测试及agent-service Maven均通过；正式隔离Runtime全量为5437 passed、28 opt-in skipped、0 failed。代码对照设计的独立只读复评Blocker/Major/Minor均0。上述机械验证不证明模型真实claim的语义忠实、12题人工usefulness或新版37/37功能UAT；Spring目标12/9全链及实际部署也未记录通过。

`mvnw.cmd -q '-Dtest=AgentKnowledgeNonLiveE2ETest' test`在agent-service当次通过：Spring→当前Runtime执行16个合成case，Runtime fake断言Summary9任务版本，含lookup成功、读取/出域拒绝、引用非法及技术失败；它未覆盖解释/适用性有限claim的Spring端到端语义，不代表真实模型或索引。

`L2_01_01` v3.8、`UAT_02` v3.10已对真实B的两阶段冻结、候选UUID后验绑定、双域物理快照和固定物理查询设计完成定向复评（S0/S1/S2均0）。es-query-service隔离查询接缝已在`codex_0915`本地提交`1ba93bb8`，默认仍走alias；固定物理路径仅在专用隔离配置下启用。es-query-service及common-security当次Maven分别106、21 tests，0失败/错误/跳过；源b2历史build绑定、自算hash篡改拒绝及候选比较器仅有未提交的fake/单元代码。尚无受控双Java实例launcher、运行归属和alias完整flags的前后证据，未创建真实候选或执行真实typed B，因此COMPARE仍In Progress、RELEASE仍Blocked。§14.9～14.15保留各次发生时的状态，不作为本节当前状态的替代权威。

### 14.17 当前B冻结工具与Summary9三模式合成验证（2026-09-29）

本地提交`dd73d130`补齐B源绑定、候选规格及比较输入的严格冻结工具。定向corpus测试23项、比较器测试50项通过；比较器fake只能产生`Not assessed / synthetic_only`，缺少隔离Java实例及物理查询归属证明时，真实模式在首次typed查询前失败关闭。此提交没有创建真实候选索引、执行BGE推理或ES对照；真实双实例launcher、运行前后alias完整flags/UUID/mapping及请求目标证明仍待完成。B的盲标和真实指标均未评价，COMPARE保持In Progress。

Spring→Runtime新增lookup以外的explanation、applicability合成场景后，`AgentKnowledgeNonLiveE2ETest`所调用的18个合成case均通过，验证`summaryType=cited_limited_answer`、逐点quote与citation配对及有限claim在公开结果中的结构；没有真实模型、BGE或索引调用，也不证明claim忠实度。维护者对12题回答的人工评价仍未开始，MEASURE保持In Progress。§14.16记录其发生时的16案与未提交工具状态；本节记录当前增量，不改写既往执行结果。

### 14.18 一次性B/MEASURE工具提交与non-live回归（2026-09-30）

本地提交`631cc47c4e19ccc17861cc4aba5349a8097282e7`补齐B两阶段准备/冻结、候选接缝、双臂隔离typed比较及MEASURE一次性launcher。B工具核对冻结Git blob、源b2回链、全源ID映射、候选UUID/mapping/fingerprint、两臂Profile/ACL/物理路径和查询体，并对预算、取消及失败终态关闭；MEASURE工具只在既定12题、快照和预算前检通过后允许执行。维护者已确认B独占运行窗口要求，但这一确认及fake验证都不是一次真实窗口或真实对照的证据。新工具尚未消费真实B/MEASURE运行，不据此关闭工作包。

本轮实际验证记录：正式`agent-runtime`隔离non-live回归5481 passed、28 opt-in skipped、0 failed；Transaction host/preflight 14 passed；`knowledge-corpus-tools`全包525用例、退出码0；B定向fake 76 passed、MEASURE定向fake 18 passed；Runtime源码strict mypy检查152个文件成功，B相关3文件与MEASURE相关5文件strict mypy成功；PowerShell AST 0 error；页面UI测试5 passed。Java五模块按Surefire `tests`总数（**包含**skipped）记录：`common-security` tests=21/skipped=0、`employee-service` tests=50/skipped=20、`mq-procedure-service` tests=37/skipped=2、`es-query-service` tests=106/skipped=0、`agent-service` tests=42/skipped=3，均failures/errors=0。旧§14记录中的数字是各次当时结果，本节不回写或相加成UAT总数。

本次外部LLM、真实BGE、真实ES候选写入、真实B成对typed对照和alias切换均为0；没有12题模型回答、全量人工盲标或新版效果结论。A仍为`Not assessed`；COMPARE和MEASURE继续`In Progress`，RELEASE继续`Blocked`。真实操作前仍须核实实际部署/索引/模型快照、冻结精确预算和运行输入；完成真实测量及人工评价后再按UAT_02判定质量与发布条件。

### 14.19 B候选构建、无效比较与MEASURE未冻结准备（2026-09-30）

提交`c9b8642e9c20765814df4b3422cfa958a2c4900c`保存[B本次有限证据](../../knowledge-corpus-tools/evidence/knowledge-b-body-20260930-01/README.md)。只读核对`result.json`及source/candidate扫描结果：完整竞争池15521条、其中738条更新，候选`agent-doc-tax-policy-v6-20260930-body-b1`构建使用ES请求363/366及本地embedding批次24/24；构建终态为`built_read_only_unpublished`，线上alias写入0。`binding`、`assessment-intent`、`assessment-final`及`scan-plan`正文SHA-256均与同目录`.sha256`文件一致。以上证明候选构建及来源绑定，不证明召回收益或发布准入。

同目录`comparison-result.json`记录本次成对比较已消费，终态`not_assessed / local_execution_or_identity_failed`：typed search、query embedding、online rerank均为0，预登记10题全部未执行；比较元数据ES请求12次、本次临时alias写入4次，`ownedProcessesStopped=true`、`aliasesRemoved=true`、`proxyViolations=0`。A仍为`Not assessed`；B无盲标、排名或质量指标，本run不得补跑、续跑或改判。静态诊断发现隔离Java启动禁用Config Server却未加载必需配置目录，是待修的启动配置缺口；有限终态未保存精确异常，不能断言它就是本次失败的唯一或直接原因。COMPARE保持`In Progress`，依赖有效比较的RELEASE保持`Blocked`，候选不切线上alias。

[MEASURE本次build-only准备](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-01/README.md)仅保存当时clean HEAD的五个Maven构建及JAR hash；快照生成与服务启动的时序问题使其不作为真实测量冻结。该目录没有manifest、authorization、consumed或模型结果，外部LLM调用为0，不得把build-attestation当成已授权或已执行批次。后续最小时序修复已完成独立复评，20项直接fake测试通过且原120秒快照年龄校验未放宽。隔离launcher仅为Knowledge验证定义`readinessState`与`elasticsearch`健康group，不关闭全局数据库/ES健康；该定向检查不证明整服务或数据库健康，也不是真实启动通过证据。仍须在新的clean HEAD上重新准备和核验正式冻结，MEASURE保持`In Progress`。本节只同步新发生事实，不修改§14.1～14.18当时的结论、历史资产或UAT阈值。

### 14.20 MEASURE失败终态及B/MEASURE的non-live修复（2026-09-30）

[本次有限失败记录](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-02/README.md)绑定run `knowledge-rebuild-measure-20260930-02`、clean HEAD `d54ee293ec6517571f8a37fc616b1a7fceef19a3`及manifest SHA-256 `c10068ca11041917aaa4817f52b884caf90e0a01338872ec6b75bcf2e1f05450`。`manifest.json`、`authorization.json`、`build-attestation.json`三份冻结资产原字节保留；授权状态仍为`authorized_unconsumed`，但失败run不复用、不补跑或续跑。launcher报告三项自有隔离Spring服务完成目标健康、端口归属、登录和完整b2快照前检后才读取进程级模型密钥；这些前检没有持久化可独立复核的运行快照，不能升级为完整真实集成通过证据。

runner进入`run_once`时，`OneShotLedger.__init__`因`agent-runtime/tests/uat/results`父目录不存在且`mkdir(parents=False)`抛出`FileNotFoundError`，发生在Runtime创建、任何case、reserve或consume之前。[执行者有限失败记录](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-02/executor-failure.json)依据实际traceback及冻结源码控制流记`failed_unconsumed / invalid_run`，并记录12题全部未执行、模型/typed search/query embedding/online rerank/Business/retry/resume均0；该记录不是runner自动journal。无consumed或journal文件；自有服务停止、目标端口释放，临时日志与快照已清理。人工rubric、Functional/Safety完整验收、召回和回答均`Not assessed`，不将0调用或部分启动前检当作有效效果测量。

故障后仅在non-live范围修正严格共享结果父目录的prepare、缺目录静态拒绝和PowerShell pre-ledger有限失败fallback；run子目录仍须独占。定向测试23 passed、corpus环境与配置下3个helper的strict mypy、compileall、PowerShell AST 0 error及`git diff --check`通过；独立范围复评未发现新Blocker/Major。该结论不等于整体代码评审、真实启动复测或新版UAT通过。B原比较仍`Not assessed`、A仍未评价，B候选只读未发布，线上alias未切换；COMPARE/MEASURE保持`In Progress`，RELEASE保持`Blocked`。本节只记新发生事实，不回写§14.1～14.19、历史资产或既有阈值。

MEASURE目录前检修复本地提交为`da6f098771a4fa2c50e59b54bf1590e5d0a727a0`，五项有限冻结及失败资产提交为`f250ffcd76ef29e27800e63830089e248617e8c7`。本轮另复核manifest中13项冻结Git blob和5项本地JAR SHA-256，以及manifest/authorization/build三者绑定，均一致；27项历史与当前追踪测试通过。上述完整性核查不补造已清理的运行快照、调用journal或人评。

B启动配置的后续修复本地提交`a7c610e6b518d6b50f5c36fe87d3ad40efff15c4`只在non-live验证：从同一冻结archive加载`application.yml`、`application-datasource.yml`、`application-es.yml`，在构建证明和Profile fingerprint绑定三者hash，缺失或漂移在alias操作前拒绝。B专用就绪group仅含`readinessState`；保留各臂既有六次Profile元数据校验、PID、物理路径、代理权限及冻结预算，不借用MEASURE允许的ES健康请求，也不关闭全局DB/ES健康。B runner/transport/comparator定向fake共81 passed，runner以corpus项目配置执行显式`mypy --strict`成功，两个改动文件compileall及差异检查通过；独立源码复评未发现本修复范围的新Blocker/Major/Minor。没有新的服务启动、ES/BGE/模型调用；不将修复通过当作旧B重跑授权、真实启动通过或质量改善。

本轮状态同步经两轮独立定向文档复评：首轮发现一项Minor，即概要中的“0检索/下游调用”可能误读为启动前ES请求也为0；修正为模型、typed检索等执行调用，并排除启动前只读元数据前检，复评关闭。未发现新Blocker/Major。P3严格校验0 error/0 warning、三份当前文档58个本地链接均可解析；8份状态文档及本次失败资产的JWT/密钥模式扫描0命中。以上均为文档与有限资产检查，不替代真实验收。

### 14.21 新独立验证批次的准备（2026-09-30）

维护者明确恢复目标并授权新的独立验证批次：先不读取模型密钥进行真实启动预检，通过后重新冻结B比较与12题MEASURE，正式题目、gold、阈值及调用上限沿用已确认版本。起始HEAD为`037b41335675d17d6b857c8b5f7dbfb9b5f3534f`，分支`codex_0915`且工作树干净。原B和MEASURE失败run不复用，其冻结资产、终态和证明局限保持不变。

当前工具缺少启动only模式以及跨run绑定既有只读候选的入口。L2_01_01 v3.9 §18.4.2已定向补齐内部合同；作者内审和未参与起草执行单元复评先定位旧构建来源闭环S1、元数据分账S2，修正后本切片S0/S1/未处理S2为0。工具准备仍须完成直接fake、类型、AST及代码复评；本文不预记真实预检或新批次通过。不新增Gate、候选索引或公开合同；A仍Not assessed，COMPARE/MEASURE仍In Progress，RELEASE仍Blocked。

### 14.22 新MEASURE元数据计数纠正（2026-09-30）

工具源码复核发现`_alias_check`每次实际发送alias与index definition两个GET，12题前后共24次检查对应48次HTTP；§14.21采用的“case 24 + Profile 6 + health 18 = 48”分账错误。主执行者承认并暂停受影响正式预算改动，维护者随后明确授权新批次元数据上限72（case 48 + Profile 6 + health最多18）。L2_01_01 v3.10 §18.4.2据此修正；启动预检独立48、正式freeze binding2及前/后完整快照各67的边界保持。必须在发送前计实际attempt并以硬上限拒绝超额，不删除安全核查、假造计数或回写旧run。模型36、typed search48、query embedding12、rerank24不增加；此文档纠正及工具准备不证明真实预检、测量或发布通过。

作者内审后，由同一任务内未参与起草的执行单元读取L2本节、P3、UAT_02及架构索引完成定向复评，S0=0、S1=0、未处理S2=0。后续代码复核须直接核查双GET经受控代理逐attempt计数，不把`aliasChecks`检查次数与HTTP次数相加冒充实测。

### 14.23 新工具复评与B无推理启动（2026-09-30）

本地提交`4b540e5b48bdc39e7ef1d571880cfde31d366675`仅修改私有验证工具及直接测试：B新run绑定旧构建Git来源、独立扫描attempt/terminal和完整记录身份；模型快照前后核验不执行推理；MEASURE受控ES代理在发送前按实际HTTP计数，启动only不读模型密钥，启动前后核验代码、构建及配置hash。两组工具分别由未参与相应修改的执行单元定向复评；B入口复制目录绕过Major已修复，最终Blocker/Major及未处理Minor均0。复评只覆盖工具源码与fake，不证明生产效果。

本轮直接验证：B五文件fake初轮138 passed，目录修复后local runner 42 passed，复评定向2 passed；模型身份fake 7 passed。MEASURE harness 32 passed；8个私有Python源文件strict mypy成功，目录修复后runner strict复查成功；两份PowerShell AST 0 error、compileall和差异检查通过。这些有重叠的定向结果不相加为测试总数。额外探索性地对旧B测试整文件执行strict曾失败（88项，主要为原有未标注fixture），不在当前配置的源码检查范围；未删除断言或扩展无关测试重写，正式私有源码strict与实际pytest均通过。

[B独立无推理启动预检](../../knowledge-corpus-tools/evidence/knowledge-b-startup-20260930-01/README.md)绑定上述clean HEAD，终态`ready`：元数据ES HTTP 30/30、临时alias写4/4、两臂就绪请求5/1；模型、typed/physical search、embedding、rerank、JWT HTTP、retry/resume均0。两个自有Java进程停止、四个目标端口无监听、临时alias移除，生产alias未切换。没有读取模型密钥；旧run和历史资产不变。此证据只证明冻结配置下的两臂服务启动及清理，B成对对照、MEASURE启动及12题、人评和发布仍未完成。工作包状态不变。

### 14.24 MEASURE独立启动失败（2026-09-30）

[新启动有限证据](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-03/README.md)绑定`a03486e653a69c434ca18fd5cec943e0aa243881`。五模块clean构建成功后，独立启动在`proxy_start`端口归属检查处终止，`startup_preflight_failed`，现场错误`knowledge.measure.port_owner_mismatch`。模型、embedding、rerank均0，未显式读取模型密钥；绑定前检记录2个元数据HTTP attempt，代理计数未取得，保持null而非补造0。自有进程报告停止，现场核查五个隔离端口无监听。此目录没有正式manifest/authorization/case journal，失败不自动复跑。继续只做根因核查与fake修复，不因此取消可独立推进的B比较；COMPARE/MEASURE仍In Progress、RELEASE仍Blocked，12题真实测量、维护者人工评价及新版UAT均未完成。

本地synthetic进程核实Windows虚拟环境redirector父PID与实际Python子PID不同，且子进程仍使用项目venv。后续私有launcher修复严格绑定父子关系、基础可执行文件、模块角色及创建时间，正式runner传入实际proxy监听PID，未监听子进程亦纳入可核实的清理，无法核实则清理状态失败而非假称退出。另只读核对本地Spring Boot 3.5.10源码，健康请求为`/_cluster/health/`；代理仅新增这一精确等价路径并与原路径共用预算，其他路径/参数/写操作仍拒绝。独立复评确认惰性进程对象的PID复用Major，已通过捕获时固定句柄及创建时间比对关闭，范围内无未解决Blocker/Major；测试基础Python路径从目标venv配置读取，不引入安装路径硬依赖。直接harness 34 passed、受影响Python源strict mypy、compileall、PowerShell AST 0 error及差异检查通过；这些仅为non-live修复验证，不构成新的启动通过或真实批次授权。

### 14.25 B既有候选承接的后验失败及请求见证纠偏（2026-09-30）

本地提交`7e3e7d601310ab4204e1f0a8ec98452ba742bed5`保存§14.24所述MEASURE私有启动修复，未复跑启动。提交`a6f83f7f941eedecaccb21fc8354608e0e23408c`补齐离线B复核辅助工具及合法空law路径的评分处理：无标签输出Not assessed，拒绝外来/null标签及与intent不一致的frozen HEAD；空law双路只有均合法零命中时才允许无rerank，非空缺stage仍拒绝。直接fake 69 passed；先前使用`--follow-imports=silent`的探索性类型检查不作为全链证明，随后以corpus项目venv、双源码MYPYPATH及项目配置执行未隐藏import的显式strict mypy，两源文件检查成功，compileall及差异检查通过。独立定向代码复评无未解决Blocker/Major；工具不能凭失败批次补造blind pool或运行归属。

[新B承接有限失败证据](../../knowledge-corpus-tools/evidence/knowledge-b-reuse-20260930-01/README.md)绑定clean HEAD `a6f83f7f941eedecaccb21fc8354608e0e23408c`。两臂完整只读扫描各64次、各15521记录，ID/content hash文件与旧构建Git对应blob字节一致，所有源身份和指纹回链通过；不重建、不写正文、不重算语料向量。正式10题全部执行，typed search=44、query embedding=10、online rerank=22、元数据ES HTTP=30、临时alias写=4；预扫描128次独立分账，付费/retry/resume/线上alias切换均0。两臂进程停止、临时alias移除、proxy violations=0，现场核查四个隔离端口无监听；候选仍只读未发布。

唯一终态为`not_assessed / runtime_provenance_missing`。失败资产未保存双臂请求见证、traces或准入receipt，故不能核查具体触发的后验条件、生成有效blind pool或补算质量。纯离线核查确认Java `Map.of`跨进程键序可不同，而冻结代理以原始JSON字节hash比较请求；同语义不同键序会被误拒，是已证实静态缺陷和本批的强候选原因，**不是本批实际触发条件的确证**。旧/新失败run均不重跑、不补判，A仍Not assessed；COMPARE/MEASURE仍In Progress，RELEASE仍Blocked，12题真实模型与维护者人评未完成。

L2_01_01 v3.11针对该内部缺陷先澄清双hash合同并完成作者内审及未参与起草执行单元定向设计复评；GET摘要歧义S2已关闭，S0/S1/未处理S2为0。原始字节hash保留，规范JSON hash只解决对象键序/空白差异，不放宽路径、授权、次数、索引或清理核查；新的证明形状不补算旧见证。后续只做直接non-live修复验证，不自动启动第三次B或新的MEASURE冻结/真实调用。

有限失败资产已本地提交`0f7466fa17312fa66f6d65cbd94000b870011cbf`，11个原始JSON及说明未改变运行终态；源/候选ID映射blob与旧Git资产完全相同。内部双hash修复本地提交`1c0d6d211135b335ff4b47ab256a165ce2fbde38`，限四个B私有源码、三个直接测试及L2_01_01合同，不改生产查询、Prompt、权限、索引正文或历史资产。同一任务内未参与实现的执行单元初检发现数字float舍入/下溢与receipt条目形状两个缺口，最小修复后分别核验数字词面差异、畸形有限拒绝、严格JSON负例及非法请求backend零调用；定向复评无未解决Blocker/Major。此结论只证明私有工具修复，不证明新真实启动、比较或质量通过。

主执行者实际验证：在`agent-runtime`目录以项目venv执行`pytest tests/evaluation/knowledge/test_rebuild_b_comparator.py tests/evaluation/knowledge/test_rebuild_b_local_transport.py tests/evaluation/knowledge/test_rebuild_b_local_runner.py tests/evaluation/knowledge/test_rebuild_b_review.py -q`，131 passed。首次未指定源码路径时因venv已安装包缺`intent_contracts`产生collection错误；随后仅为该验证进程显式设置`PYTHONPATH=D:/codex/agent-runtime/src;D:/codex/knowledge-corpus-tools/src;D:/codex/agent-runtime`，纠正导入基线后得到上述通过结果，没有安装或修改全局环境、删除断言或跳过测试。两项元数据守卫定向测试`test_formal_proxy_counts_each_alias_get_and_rejects_seventy_third_metadata_attempt`、`test_formal_proxy_records_failed_metadata_attempt_before_backend_error`另得2 passed，实际计数保留且第73次拒绝；72仅为正式MEASURE运行上限，不是新批次授权。corpus项目venv配合双源码`MYPYPATH`及corpus项目配置执行显式strict mypy，四个受影响源码成功，未用`--follow-imports=silent`；七个受影响源码/测试compileall成功。

文档/追踪有限检查：P3与L2严格校验各0 error/0 warning，四份当前文档69条本地链接无断裂，Business/原Knowledge追踪兼容12 passed；新增有限资产及四份文档敏感模式扫描无命中，Git差异检查通过。本轮未修改生产源码或Java，未重复全量Python/Maven、真实Spring全链、索引发布或人工质量评价；这些不得从本轮定向检查推定通过。收口现场只读检查九个本次隔离端口无监听，未停止用户服务。以上修复提交和状态同步均仅本地保存，不push、不部署；下一批真实执行需要独立决策，当前目标仍未全部完成。

### 14.26 私有工具有限失败及清理边界修复（2026-09-30）

本轮起始clean HEAD为`b109799c1e87f3af7fa0d609146b20bd839bea27`。静态复核发现MEASURE正式成功路径未核实自有进程实际停止即进入后验和成功写入，Java强制停止后亦缺有界等待。本地提交`13f9458cd69f6f18f588a85582a30f843975ba6f`改为使用已核实并固定的进程对象句柄执行Kill及最多5秒等待；退出检查、停止异常或超时均保守标为清理未知。成功路径必须先通过`Test-OwnedProcessesStopped`；失败路径保留代理可用时的有限计数及实际清理结论，不按裸PID重新查找并终止进程。正式成功result形状及运行预算不变。

B后验拒绝原先只有泛化原因，且消费后的最终JAR读取异常可能绕过有限终态。本地提交`eb7d56171db761ac2ddbdd1fab6620dac670d3a6`保留全部原准入守卫，补充固定allowlist诊断、执行phase、已有receipt和有界双hash请求见证。失败证据明确为`local_unadmitted_diagnostic`，不保存traces、不生成blind pool、不评分，不能当作有效比较。终态落盘失败单独报告已消费及实际计数，不误报preflight失败或声称证据已保存。独立代码复核另以纯mock复现ES client构造异常发生在消费后却无终态；修复将创建及关闭纳入显式有限生命周期，关闭失败亦阻断准入和盲标池。原成功终态结构不变；外来异常文本不持久化。

验证只覆盖私有工具及直接测试。主执行者用§14.25相同项目venv和进程级`PYTHONPATH`执行四份B定向测试，148 passed；随后客户端边界增量修复后，重新执行`pytest tests/evaluation/knowledge/test_rebuild_b_local_runner.py -q`，最终runner 50 passed。两者有重叠，不相加，也不把148项称为客户端修复后的整组重跑。MEASURE实现执行单元在最终源码上执行`pytest tests/uat/test_knowledge_rebuild_measure_harness.py -q`，36 passed、0 skipped；主执行者另核验两项新增清理测试，2 passed、34 deselected。corpus项目venv、双源码`MYPYPATH`及项目配置下，对B comparator/runner显式`mypy --strict`检查成功（2源文件，未隐藏import）；5个受影响Python源码/测试compileall成功，PowerShell AST 0 error，Git差异检查通过。

同一任务内未参与对应实现的执行单元直接核对L2合同、源码和负例并执行定向测试；客户端异常Major修复后复评，范围内无未解决Blocker/Major，未报告待处理Minor。MEASURE定向复评还用纯内存进程mock确认Kill及HasExited异常失败关闭。本轮没有新增设计语义或生产链路修改，不改Java、公共DTO、Prompt、读取/出域权限、索引或alias，也不修改任何历史运行资产。

本轮真实ES、BGE及外部模型调用均0，未读取模型密钥、未启停真实服务、未冻结或复跑新批次。新MEASURE元数据72、模型36、typed search48、query embedding12、rerank24的上限保持不变；预算纠正不是追加运行许可。A仍Not assessed；历史B后验失败无法因新诊断补回缺失见证或改判，MEASURE12题、人工评价及新版完整UAT仍未执行完成。Done=9、In Progress=2（COMPARE/MEASURE）、Blocked=1（RELEASE）保持；后续实际验证必须另作独立执行决策。以上仅本地提交，不push、不部署，不重复宣称§14.18全量Python/Maven或真实集成在本轮通过。

### 14.27 新独立启动预检失败及Java选择修复（2026-10-02）

维护者再次明确授权“新独立验证批次，先无付费启动预检，通过后重新冻结B对照和12题MEASURE，沿用预算、gold及阈值，不复用失败”。起始`codex_0915` HEAD为`7f0eacb54824b45eb20fe19e0ba177ec5609b19d`，工作树干净；9200、8908、8909已有监听，九个计划隔离端口未占用。未停止既有用户服务，也未读取模型密钥。

[本次B启动有限证据](../../knowledge-corpus-tools/evidence/knowledge-b-startup-20261002-01/README.md)记录唯一终态`not_ready / java_readiness / java_exited`。冻结archive的离线Maven构建成功，`-DskipTests`不作为测试通过证明；Java在就绪检查前退出。实际ES元数据HTTP12/30、随机临时alias写4/4、两臂readiness请求1/0；typed/physical search、query embedding、rerank、paid、JWT HTTP、retry/resume均0，proxy violations为0。自有Java进程已停止、临时alias移除，结束后核查九个隔离端口无监听，线上alias未切换。四份原始JSON创建后保持字节及hash不变。

本批按失败停止条件终止，未执行比较题目、两臂全记录新扫描或正式B冻结；MEASURE本次构建、启动预检、正式冻结、授权和12题均未进入。不能用此前成功的启动预检替代当前组合证明，不能将失败目录复用、补跑或续跑。模型预算未使用不代表可以自动重开批次；题目、gold、阈值及所有正式预算不变。

只读核实确认当前PATH的`java`是Oracle Java `1.8.0_503`，`JAVA_HOME`是JDK `25.0.2`，项目`serviceCenter/pom.xml`要求25。旧runner在隔离子进程原样传递PATH并使用裸`java`，Maven则使用`JAVA_HOME`；编译与启动Java选择不一致已证实，Java8不能运行该项目产物。未保存Java原始stderr，故不补造具体JVM异常栈或排除修复后可能出现的其他启动问题。

本地提交`11c87c5565cec83b9c7ca0f43330b1bea0f0608b`保存本次有限失败资产，并只修复B私有runner及直接测试：从绝对`JAVA_HOME/bin/java.exe`选择Java，白名单环境下有界核验25；startup在alias操作前、正式比较在消费前失败关闭，并对两臂显式使用同一可执行文件。Profile launch模板默认字面量仍保持稳定，不改Prompt、生产组合根、公共DTO、读取/出域、索引正文或历史资产。MEASURE launcher已明确使用并检查`JAVA_HOME/bin/java.exe`，本次不修改其代码。

直接non-live验证在项目venv及§14.25所列进程级`PYTHONPATH`下执行：`pytest tests/evaluation/knowledge/test_rebuild_b_local_runner.py -q`最终61 passed；随后一次运行B comparator、local transport、local runner、review四文件及`tests/uat/test_current_traceability.py`、`tests/uat/test_knowledge_traceability.py`，175 passed。这两个结果重叠，不相加为总数；历史追踪兼容通过不等于重新执行Business或原Knowledge UAT。首次新增测试fixture不符合原alias规则，按既有严格身份格式修正后通过，没有放宽validator或删除断言。corpus项目venv、双源码`MYPYPATH`及项目配置执行runner显式`mypy --strict`成功，两个受影响Python文件compileall成功。

作者自审后，同一任务内未参与修改的只读执行单元核查L2 §18.4.2、源码、负例及原始有限JSON；修复范围内未发现未解决Blocker/Major/Minor。评审者没有重跑主执行者的61项测试，该独立源码复核不冒充外部人员评审、真实启动成功或质量通过。当前只同步P3/UAT/索引的授权及执行状态，不改工作包DAG、验收条件或设计合同。

文档状态切片另经同一只读执行单元复核，无确认S0/S1/S2。主执行者执行P3严格校验，0 error/0 warning；三份当前文档62条本地链接及v3.21引用核对通过，10个目标文件敏感模式扫描无命中，Git差异检查通过。历史构建来源10份资产的当前SHA-256与冻结输入逐项相同，新启动4份JSON的SHA-256与README清单逐项相同。只核实本次依赖资产，不冒充全库历史资产重新扫描。

本轮未重复全量Python/Maven回归、Spring真实全链、真实模型测量、人工评价或发布；没有这些项目的新通过结论。A仍Not assessed，COMPARE/MEASURE仍In Progress、RELEASE仍Blocked，整体目标未完成。后续只能在新的独立执行决策下使用新目录及新冻结，不能继续本次失败run。本轮提交仅本地保存，不push、不部署。

### 14.28 修复后新授权的独立无付费预检（2026-10-02）

维护者明确再次授权使用修复后HEAD的新批次，先无付费预检，通过后新冻B/MEASURE，沿用预算、gold及阈值，不复用失败目录。起始`codex_0915` HEAD `35d108ecfcf4e3563b09b99844e1333a83c4db59`干净；九个隔离端口未占用，既有9200/8908/8909服务未停止。

[B新预检](../../knowledge-corpus-tools/evidence/knowledge-b-startup-20261002-02/README.md)终态`ready / complete`；元数据HTTP30/30、随机临时alias写4/4、baseline/candidate readiness3/1；typed/physical search、模型、embedding、rerank、JWT HTTP、retry/resume均0，proxy violations0。自有进程停止、临时alias移除，四个B端口现场无监听。有限资产本地提交`6e81264d89721afe1c631b544827d07e5e212343`；只读执行单元另核四JSON/README hash与源码预算/清理一致，不重跑服务。该成功仅证明启动，尚未执行B题目、全记录新扫描或质量评价。

[MEASURE新预检](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20261002-01/README.md)从clean `6e81264d`完成五模块版本化clean构建（`-DskipTests`），然后无付费启动在`es_ready`超时；有限终态`startup_preflight_failed`，shell为`knowledge.measure.readiness_timeout`。元数据HTTP48/48，typed search/model/embedding/rerank均0，proxy violations0，`runtimeKeyRead=false`。原始结果`ownedProcessesStopped=false`保持不变，不能补改为true；退出后五个端口无监听且CIM未发现相应目标角色，只作为后续有限观察。服务日志按既有边界删除，没有具体健康响应可补证，不推断唯一根因。

本次MEASURE预检已停止，没有正式manifest、authorization或12题执行；不自动重启、续跑或创建追加批次。B通过自己的预检，且按§6/7的直接依赖不依赖MEASURE，继续独立的新扫描及正式对照，不以MEASURE失败取消其授权，不以B成功替代MEASURE启动证明。两者计数分别保存，生产alias未切换，所有历史运行原字节不改；A仍Not assessed、COMPARE/MEASURE在制、RELEASE受阻。预检证据和工具在正式冻结前完成本地提交，后续冻结后不修改tracked文件。

### 14.29 新B正式对照后验拒绝及non-live最小修复（2026-10-02）

[新B有限证据](../../knowledge-corpus-tools/evidence/knowledge-b-reuse-20261002-01/README.md)本地提交`ad8515d816e97b033aead931c0ebb08769dc2c55`，冻结clean HEAD `ebd8dfd2bf8aee40ff764347fb4ed10206044f55`。新全记录只读扫描各64次、各15521记录，两份ID/content hash映射与原构建Git对应blob完全相同；不重建索引或语料向量。正式10题全部调用，typed search44、query embedding10、online rerank22、元数据HTTP30、随机临时alias写4；预扫描128次另账。全部44个搜索POST见证HTTP200；paid/retry/resume均0，未读取模型密钥，生产alias未切换。

终态`not_assessed / runtime_provenance_missing`，phase`postflight`，固定诊断`canonical_requests_mismatch`：两臂各22个POST的规范hash多重集合不一致。自有进程停止、临时alias移除、proxy violations0，结束后四个B端口无监听。无traces、无blind pool，不能计算质量指标，不能把完成调用改为有效比较；原始JSON字节不改、不补证、不复跑。

只读源码及新增测试复现确定性缺陷：Profile冻结时`Map.copyOf(sourceFields)`不保证跨JVM迭代次序，服务将该次序直接写成`_source.includes`数组。本地修复提交`3f642db283458da37847a4d210f9665bc696384e`只让字段投影去重后升序，字段集合、query/filter/vector、分页、授权、解码及Python规范hash守卫不变。修前定向9项中新增2项失败；修后Maven reactor实跑es-query-service108、common-security21全部通过，0失败/0跳过；B comparator/transport/runner/reuse/review直接non-live 183 passed。有限见证没有请求正文，此缺陷与本批差异相符但不证明唯一根因；修复尚未作新真实对照，不能据此改判。

同一任务内未参与修改的只读执行单元核查当前L2、两个Java文件、新B原始JSON/11项hash及三文档状态，定向代码与状态复评未发现未解决Blocker/Major/Minor或S0/S1/S2；没有重跑主执行者测试，不冒充外部人员或效果评价。P3严格校验0 error/0 warning，三文档65条本地链接无断裂，Business/原Knowledge追踪兼容12 passed；有限资产及文档敏感模式扫描无命中，历史资产和公共DTO未修改。

MEASURE保持§14.28的启动失败终态，具体ES健康超时根因未知；其原始清理false不改。A仍Not assessed、COMPARE/MEASURE仍In Progress、RELEASE仍Blocked；所有gold、rubric、阈值、预算及12包DAG不变。本轮未重复全量Python、其他Java模块或真实Spring全链，没有人工评价或发布。后续真实执行必须另作独立决策，修复和有限证据仅本地提交，不push、不部署。

### 14.30 MEASURE就绪检查有限诊断补齐（2026-10-02）

起始clean HEAD为`8425e58c2f4bc3115391eca4c5c6311a3053eade`。源码确认已有专用`knowledge-validation`健康组，包含`readinessState,elasticsearch`，未把独立MySQL健康作为本查询前置；旧预检没有健康HTTP响应证据，仍不能确定超时根因。本地提交`0ef99ecf14dfb79889f8d1c3d541bb84e2f3483d`只补齐私有launcher观测：记录固定端点角色、尝试上限/次数、HTTP状态计数、传输失败次数、白名单健康状态及固定终态；最多解析4096字节响应，只接受对象根，不保存URI、响应正文、details或异常文本。HTTP200及自有进程归属准入、轮询/ES预算、快照鲜度及密钥读取门禁均不变，诊断不是新的就绪判断或追加运行授权。

项目venv、进程级双源码`PYTHONPATH`下执行`pytest tests/uat/test_knowledge_rebuild_measure_harness.py tests/uat/test_knowledge_rebuild_measure_fixture.py -q`，最终53 passed、0 skipped；根数组负例曾发现PowerShell展开及宽类型匹配问题，修复后保留持久回归。设置`MYPYPATH=D:/codex/agent-runtime/src;D:/codex/knowledge-corpus-tools/src`后直接测试显式`mypy --strict`通过（1源文件，未隐藏导入）；初次缺少源码路径的检查错误解析旧site-package，不作为最终源码检查结果。compileall通过、PowerShell AST 0 error。未参与修改的同一任务执行单元直接复核L2、源码及负例，未发现未解决Blocker/Major/Minor；主执行者另核关键证据，不冒充外部人员或真实集成评审。

状态同步经同一只读执行单元定向复核，无实质状态问题；P3严格校验0 error/0 warning，三文档65条本地链接无断裂，Business/原Knowledge追踪兼容12 passed，敏感差异扫描无命中、Git差异检查通过。冻结12题fixture SHA-256与原值一致，三个已消费运行目录的Git字节差异为0。本轮真实ES/typed/model/embedding/rerank请求均0，未读取模型密钥、启停服务或另行冻结，没有全量Python/Maven、真实UAT或人工评价。历史B与MEASURE资产字节及终态不变，不能从新诊断补造旧响应或改判。Done=9、In Progress=2、Blocked=1及全部gold、阈值、预算、DAG不变；下一次真实执行须新独立决策，不复用已消费目录。本次只本地提交，不push、不部署。

后续收口复核（同日）：在代码HEAD `03f52734f07a62d3aa282da8d0216cfda8364081`上执行正式入口 `agent-runtime/scripts/run-nonlive-regression.ps1 -PythonExecutable C:/Python312/python.exe`，Transaction host/preflight 14 passed；全量non-live 5639 passed、28 opt-in skipped、0 failed，耗时709.83秒，另有1条LangGraph依赖弃用警告。执行子进程置空模型密钥并关闭live开关，不读取原密钥，不执行真实模型或索引验证。P3当前工作包表及Ready队列的四处旧失败引用同步到§14.28～14.30；这仅修正当前状态入口，不改写历史结论、gold、预算、DAG或工作包状态。该回归包含新版直接测试及历史追踪兼容，不代替真实12题、人工评价或发布；本次未重跑Maven，未新建运行批次或切换alias。

### 14.31 启动与清理修复后继续新独立验证（2026-10-03）

维护者确认启动与清理问题已修复，要求继续当前目标。起始clean分支`codex_0915` HEAD `f01540da1b3fced7881821a73703191f84059e3d`；从通过预检时的`2c2d468173101a41206eeb5f7a54bd2e4ed52db2`到此HEAD只增加有限证据，运行源码未再变化，12题fixture SHA-256仍为`04a437d215ab242ea5e69eed95d109f47cf617135778f4d2cf5a13f6cddce26a`。

[MEASURE新无付费预检](../../agent-runtime/tests/uat/knowledge-rebuild-startup-diagnostic-20261003-02/README.md)原始终态`startup_preflight_passed`，元数据9（派生绑定2、Profile6、健康1），typed/model/embedding/rerank及outbound violations均0，login1、runtimeKeyRead=false、ownedProcessesStopped=true。三个指定JSON及绑定源码、配置、服务/依赖JAR的hash与现值一致。同一任务内未参与修复的只读执行单元核查源码、当前L2/UAT、原始证据和PowerShell AST，定向复核无确认Blocker/Major；未重跑旁路诊断的93项测试，不冒充外部人员或质量评价。

修复使用同一venv及严格绑定的基础`pythonw.exe`无控制台启动共享proxy及无推理Runtime，不按conhost名称放行，身份、日志排空和清理失败关闭保留。正式付费Runtime仍由venv `python.exe`执行runner内嵌创建；预检与正式流程不同，启动通过不能证明付费12题成功。正式执行仍需当前clean HEAD的新构建、manifest/authorization和120秒内快照。

[B新无推理预检](../../knowledge-corpus-tools/evidence/knowledge-b-startup-20261003-01/README.md)在起始HEAD执行一次，终态`ready / complete`：元数据30、临时alias写4、两臂readiness3/1，其余typed/physical search、query embedding、rerank、paid、JWT HTTP、retry/resume均0。自有Java停止、临时alias移除、proxy violations0；四个B端口退出后无监听。冻结archive构建使用`-DskipTests`，不作为Maven测试证明；原始四JSON保持不变。

本阶段未读取模型密钥、执行比较题目或12题，未改索引正文、生产alias、权限或历史资产；用户9200/8908/8909服务保留。A仍Not assessed、COMPARE/MEASURE仍In Progress、RELEASE仍Blocked。新授权只承接既定预算/gold/阈值，不复用旧失败批次；当前窗口并发修改条件在正式质量执行前另行核实。仅本地提交，不push；本阶段未重复全量Python/Maven、真实UAT或人工评价。

### 14.32 新独立B完整执行与质量边界（2026-10-03）

维护者确认本次B／MEASURE窗口内本人和其他任务不会修改目标索引或切换相关alias。在分支`codex_0915`、HEAD `781690c0a932a50fb898918d699b2c18ac41647d`执行[新B有限对照](../../knowledge-corpus-tools/evidence/knowledge-b-reuse-20261003-01/README.md)，不复用历史失败run。新双臂扫描各64次、各15521记录；正式10题typed44、query embedding10、rerank22、只读元数据30、临时alias写4、paid/retry/resume均0。终态`completed_awaiting_blind_labels / local_verified`，两个自有Java进程停止、两个隔离alias移除、proxy violations0，退出后四个B端口无监听；生产alias未切换，用户基础服务未停止。冻结archive打包使用`-DskipTests`，不记Maven测试通过。

严格离线review核验来源及原始终态，生成未填写的215项盲标模板。机械评分只使用已冻结必要来源和排名：基线/候选宏平均recall@20均0.85，核心及保留题覆盖逐题未退化，未出现评分器检查的keyword/law域顺序混杂；median时延约0.83653/0.83961秒，候选未超过基线110%。主指标没有严格提高，不能据此发布；人工precision及完整B质量仍Not assessed，不代填215项标签或修改gold。A保持Not assessed，不补跑、不追加对照。COMPARE因人工证据仍缺保持In Progress，RELEASE保持Blocked；不存在合格候选时保留旧绑定，后续按§7记录未发布，不伪装为Done。

唯一MEASURE批次选择现行b2索引及意图12/Summary9/minimal-v1组合；不是候选b1的回答证明。须先将本次有限终态/文档收口提交，再从clean HEAD新构建并冻结12题、manifest/authorization及72次正式元数据预算；36模型/48typed/12embedding/24rerank/gold/阈值不变。本节没有12题或真人回答评价的新通过结论。原始result、见证及历史证据保持不变；仅本地提交，不push或部署。

本次运行后定向检查：严格P3校验0 error/0 warning，三份状态文档及README的68条本地链接无断裂，`test_rebuild_b_review.py`与两份历史追踪兼容测试共26 passed（55.41秒）；敏感模式扫描和Git差异检查通过。未改源码或历史资产、未机械重复全量Python/Maven。另一未参与执行的只读单元核查原始证据、旧Git来源10文件、两臂请求/模型/排名见证及新状态diff，定向复核无确认Blocker/Major；机械指标和空模板均与严格离线入口输出相等。该复核不冒充外部人员或真人相关性/回答评价。

### 14.33 新独立MEASURE有限失败终态（2026-10-03）

§14.32的B证据及状态已本地提交为`0e9e47345def6db376f4b2e9af481d445d8d707c`。从该clean HEAD新构建并冻结`knowledge-rebuild-measure-20261003-01`，reference为`UAT_02:KNOWLEDGE_REBUILD_MEASURE_20261003_01`，manifest SHA-256为`47dee2d00fdd980fb0280c269b5f390d4ba3febc9bfc7bdcd4dcf69190d5fcd8`。真实绑定为现行b2、deepseek-flash、意图12/Summary9/minimal-v1，沿用12题/gold/阈值及36模型/48typed/12embedding/24rerank/72正式元数据上限。维护者已确认本次窗口无其他相关索引/alias修改；不复用旧失败目录或预算。

版本化launcher仅执行一次。启动、身份及新鲜快照前检通过后开始模型调用；完成001～004，第005题在Summary传输完成后触发`case_technical_failure`，exit code=1。原始failure为`failed_consumed`、completedCases=4，按执行完整性口径为`invalid_run`；006～012未执行，没有measurement或成功result。本次实际模型13、typed8、query embedding4、rerank4；58行journal中的29个started都有terminal completed，但传输完成不等于输出/引用/公开结果合同通过。

第001/002题HTTP200 success，必要来源进入top20、分别3/1条引用；这不是人工回答通过。003题HTTP200 no_result且small_2022未进入top20，与冻结success不同；004题HTTP422 unsupported、`core.no_supported_capability_candidate`，与冻结no_result不同。005题未保留公开响应或errorCode，不能从最后一次Summary完成推定具体解码、引用或回传根因，不通过重跑补证。四条公开加工结果仅在受控本地目录供人评，不提交引文正文或原始模型/完整服务响应。

原始代理见证为live_proxy：正式ES元数据27、typed8、health1、alias12、indexDefinition10、proxyViolations0；共10次题前/后身份核查，每次2个HTTP。freeze绑定2和全快照前检预算67分账；失败后没有完整postflight或快照postflight，不宣称全记录前后证明闭合。ownedProcessesStopped=true、cleanupIssues为空，退出后五个隔离端口无监听；未停止用户9200/8908/8909，未切生产alias。运行后27项冻结asset hash匹配、无tracked源码改动；自动retry/resume、Business及旧answer均0。

有限证据与原始hash见[本次交接](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20261003-01/README.md)。原始资产保持append-only，本次只追加README及当前状态同步，不补造成功终态或人工评分。功能/安全完整UAT、召回和回答整批评价均未完成；B主指标未改善，RELEASE继续Blocked、现行b2保持。本批停止，不使用剩余额度继续调用；后续可先做无付费诊断，真实复测须新的独立决定，不自动准备下一批。

本次运行后已有定向non-live：`test_knowledge_rebuild_measure_fixture.py`与`test_knowledge_rebuild_measure_harness.py`共95 passed（69.22秒）。构建使用skipTests，不记为Java测试；源码未改，不机械重复全量回归。当前引用同时纠正UAT版本和§12旧比较状态的元数据漂移，不改变设计、DAG、用例、gold、阈值或预算。

当前文档严格校验0 error/0 warning，三份状态文档及本次README共70条本地链接无断裂，有限JSON/JSONL按真实ledger格式配对核验、敏感模式及Git差异检查通过。另一未参与执行或编辑的只读单元独立核对原始8文件hash、freeze与fixture、预算/消费/停机源码及v3.27差异，无确认Blocker/Major；它未重跑真实调用或测试，不冒充外部人员、完整代码评审、人工回答质量或发布验收。本节的hash与传输证据不能补足第005题响应及整批postflight缺口。

### 14.34 MEASURE失败响应的有限观测修复（2026-10-03）

起始clean HEAD为`fa6a9f190f923ba6accb9346270d7b400ccf5053`。只读核实确认私有runner在公共响应校验失败时直接停止，未保留该题的HTTP状态或有限公开错误分类。仅修复当前runner和直接测试：新失败记录可附`failedCase`，保存冻结case身份、有限HTTP状态、JSON形态、白名单公开状态/错误码和关联/能力匹配布尔值；未知文本仅记固定unknown，不保存问句、回答、引文、原始响应、异常信息或凭据。原失败终态、消费及停止逻辑不变，launcher仍以失败资产是否存在判断，不增加重试、续跑或真实运行授权。

六种fake反例覆盖技术失败、异常字段、非法JSON、非对象响应、关联不匹配与连接失败，均在首题停止；真实HTTP由测试守卫禁止。MEASURE fixture/harness及Summary9 contract/stage四文件共124 passed（71.18秒）；类型注解修正后两文件strict mypy通过、compileall通过，新增六反例复跑6 passed。这些计数有重叠，不相加。工具修复只对后续另获授权的新冻结生效，不能恢复或补写§14.33第005题响应，不能证明实际Summary、引用或回传根因已修复。

实现本地提交`587a61eb847c0001071d4ef537f298c0ff02350c`。作者自审后，未参与修改的只读执行单元定向检查源码、launcher消费者、原始终态及三文档状态，未发现确认缺陷；另独立执行六新增反例和两项消费/零发送测试，8 passed（1.89秒），与上述回归重叠。其禁用插件自动加载的命令有一条asyncio_mode配置未识别警告，不影响这八项使用asyncio.run的测试；未独立重跑124项、mypy或compileall，不称完整设计/代码评审、真人评价或真实UAT。主执行者严格P3校验0 error/0 warning、三文档69条本地链接通过；原运行8份文件与起始Git字节一致，27项冻结资产中26项当前字节不变，受本轮修改的runner按原冻结HEAD及仓库checkout换行恢复并匹配原hash。没有把当前新工具伪称为旧运行使用的工具。

本轮没有模型、ES、embedding、rerank或真实服务操作，不创建新批次，不切alias、不发布、不push；历史原始文件和绑定的冻结Git版本保持不变。COMPARE/MEASURE仍In Progress、RELEASE仍Blocked，现行b2保持；缺少人评、有效完整测量与候选主指标改善，整体目标未完成。后续决策应分别处理已有B盲标材料、已消费的无效MEASURE及是否继续质量实验，不自动复用余额或追加候选。

### 14.35 已封存来源损失定位及部分人评准备（2026-10-03）

起始clean HEAD为`af9ac4a75a6a618c0da89912e1ca6fd40e10d899`。[局部复核材料](../../knowledge-corpus-tools/evidence/knowledge-rebuild-review-20261003-01/README.md)只离线读取§14.32的10题traces、两臂完整身份清单与§14.33的冻结必要来源。两臂各16个题—必要来源组合，均缺2项：KM-003的small_2022、KM-012的lease_real在两臂扫描中具有精确document/chunk/正文hash，但未进入初始keyword/vector前20；没有必要来源先进入初始候选再因融合、重排或final20截断丢失。该定位不是新测量、人工precision或MEASURE第003题搜索轨迹重建；尚不能区分Profile过滤/权限、查询匹配与原路径排名/候选窗口，不能直接据此调整topK、Prompt或向量。

已在既有受控本地review目录准备四题人工核对说明，配合原公开加工结果供维护者阅读，不提交引文正文。执行者对001/002提出四项判据的初步建议，正式确认仍由维护者完成；003未返回所需期限，004未编造内容但公开状态不符合冻结no_result，不计用例通过。未填写正式rubric或215项B盲标；005具体技术根因仍不可验证，006～012未执行。局部人评即使完成也不能使整批invalid_run变成完整12题验收通过。

本轮未读取模型密钥，没有网络、ES、模型、embedding、rerank或服务操作，不新增/续跑批次，不修改gold、阈值、预算、历史原始资产或12包DAG。COMPARE/MEASURE仍In Progress、RELEASE仍Blocked，候选主指标未改善、现行b2保持，整体目标未完成；本次只本地提交，不push、不部署。

### 14.36 独立有限元数据诊断及联合机关词法修正（2026-10-03）

起始clean `codex_0915` HEAD为`a1ba290e8b2d78da71d46bc1f39018be502c7347`。维护者另行精确授权一次最多4次ES只读GET，分别为索引身份前后核查和small_2022/lease_real各一次有限元数据；[新诊断记录](../../knowledge-corpus-tools/evidence/knowledge-rebuild-review-20261003-01/current-metadata-probe.json)保存实际4次attempt，均HTTP200、前后UUID一致。没有读取正文或向量，没有模型、BGE、typed search、写入、alias或服务操作，retry/resume=0。该4次授权已耗尽，结果只诊断当前状态，不补写历史B/MEASURE字段。

两条记录当前channel均为仓库Profile允许的财税文件；此观察不等于完整ACL、出域或历史字段核验。small_2022当前完整文号以空格连接两个机关，冻结第003题以顿号表达；原私有词法只保留末机关，不能使该完整元数据获得可选boost，确认一个软信号覆盖缺口，但不能据此解释全部top20损失。lease_real的文号存在，原第012题没有指定它；其检索匹配、授权或窗口原因仍未知，不以gold向原问注入文号。

先按L2_01_01 §9.8/DR-KRET-035补齐通用联合机关词法，完成两轮作者内审、未参与起草执行单元的定向只读设计评审及L2严格校验，再修改`DocumentNumberQuery`和两份直接Java测试。保留全部显式机关，最多4片段、总机关码点≤48；空片段/单字/超限整信号关闭，不从末机关补匹配。原queryText、单次keyword、category、固定boost、limit、开关、vector、权限顺序及零重试不变；未改Prompt、模型任务、gold、topK、公共DTO、mapping、索引或部署绑定。

实际non-live命令及结果：

- `serviceCenter/mvnw.cmd -o -f es-query-service/pom.xml '-Dtest=DocumentNumberQueryTest,KnowledgeDocumentNumberSearchTest' test`：原测试46项通过；新增纯函数测试在旧源码上10项失败，证明会检出末机关截取；新增服务测试另有一处合成Profile字段名错误，已按真实fixture纠正，未修改生产mapper或放宽断言。
- `serviceCenter/mvnw.cmd -o -f es-query-service/pom.xml test`（Java25.0.2，执行子进程直接置空模型密钥）：123 passed，0 failure/error/skipped，13.217秒；包括文号49项、服务形状/单次fake HTTP 12项，以及mapping、读取授权、Servlet安全、类型化响应和隔离查询。存在现有Mockito动态attach及JVM共享警告，不隐瞒为无警告。
- `agent-runtime/.venv/Scripts/python.exe -m pytest -q tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py tests/evaluation/knowledge/test_live_p5_candidate_{01,02,04,05,06,07}_history.py`（实际命令逐文件展开、禁用插件自动加载）：26 passed（10.76秒），有1条asyncio_mode未识别配置警告。只证明原Business/Knowledge追踪和六份历史运行兼容，不把旧37项Passed搬到新UAT_02。

上述检查无外部推理或真实typed检索；本地fake HTTP不计为真实ES请求。8份MEASURE原始资产及原B result/source-id-map共10项SHA保持不变，新元数据只保存4个来源字段，没有正文、向量或凭据。Python/Runtime/启动脚本没有修改，未机械重复全量Python、mypy、Spring Runtime E2E或其他模块Maven，也未以这些未执行项冒称本轮通过。

另一未参与修改的执行单元按设计定向核对三份Java源码/测试、真实fixture字段映射及调用方，未发现确认缺陷；独立使用本地JShell检查接近1024码点、多片段、无年号和64个联合机关并发输入，无HTTP或服务操作。它读取现有Surefire报告而未独立重跑Maven；结论仅覆盖本切片，不称整系统代码评审、外部人工评价、真实质量或新版UAT通过。作者复核、独立设计与代码核查均未放宽引用、授权、阈值或历史证据。

COMPARE/MEASURE仍In Progress、RELEASE仍Blocked；B两臂recall仍0.85、215项盲标仍待维护者，MEASURE仍failed_consumed/invalid_run，不补跑或使用余额。第005题的公开响应缺失仍阻止具体技术根因判断，006～012未执行。本修正只提供本地源码/non-live证据，不证明当前服务已升级、召回改善或完整UAT通过；新真实诊断、比较、测量及发布须相应独立决定，不自动开始。

### 14.37 已完成四题的维护者人工结论（2026-10-03）

维护者先确认003、004不能通过，在阅读本对话展示的001、002实际`answerSummary`及来源后，明确确认001、002通过。[独立人工结论记录](../../knowledge-corpus-tools/evidence/knowledge-rebuild-review-20261003-01/maintainer-case-acceptance-20261003-01.json)绑定原manifest、cases及failure的SHA-256，仅保存维护者的整题决定和反馈摘录，不保存引文正文。记录起点为clean `codex_0915` HEAD `978704ab6d52cc8a72ffd5100a03a77c090c38c2`。

| 已完成题 | 维护者整题结论 |
|---|---|
| UAT-KM-001 | Passed |
| UAT-KM-002 | Passed |
| UAT-KM-003 | Failed |
| UAT-KM-004 | Failed |

维护者未单列四项rubric分数，本次不补造分项布尔值；上述明确整题决定照实保留，不要求重复确认。第005题技术失败、006～012未执行，整批仍`failed_consumed / invalid_run`，不以四题局部评价关闭MEASURE或宣称完整新版UAT通过。B的215项候选相关性盲标是另一项评价，仍未提供；两臂recall相同、主指标未改善，COMPARE仍In Progress、RELEASE仍Blocked。

本次仅追加人工结论及当前状态，不修改原运行资产、gold、阈值、预算、工作包DAG或代码/配置；没有模型、ES、embedding、rerank及服务操作，不补跑、不发布、不push。历史§14.33～14.36保留其发生时的证据状态，以本节承接新的人工反馈。

### 14.38 动作选择职责补齐、v5接线与non-live复评（2026-10-03）

起始clean `codex_0915` HEAD为`d059a072b83669daabc31a1eb61f57f536e992ef`。维护者接受此前最小建议并授权继续：只修订L1_00/L2_00_02动作选择职责、使用独立新任务版本实施与non-live验证，不授权新的真实模型、ES/BGE、服务或批次。第004题原始结果只证明selector返回unsupported，不能证明模型内部的确切原因；本轮修正的是已确认的合同缺口，不把假设包装成实际模型根因。

L1_00 v3.2 §4.1/CR-AD-006与L2_00_02 v3.4 §6.3/DR-MODEL-112明确：selector按请求操作与安全catalog职责选择，Knowledge范围内的查找、解释和依据判断不因标题/年份陌生、虚构或过时而提前拒绝；资料存在性、时效、条件与证据充分性留给已授权Knowledge链路。禁止本地强制选路、纠正问题、承诺命中或生成查询条件；exact decoder、guard、预算及失败关闭均不变。

独立`action_selector_v5.py`复用v4输入 framing与严格输出协议，但同时绑定definition及request的独立v5版本/Prompt，不改v4闭包或历史源码。`LocalModelCompositionRoot.build`增加私有显式definition接缝，错task/input类型在创建Provider客户端前失败；默认仍v4。当前`main.py`仅在Knowledge enabled时选v5，disabled与Business v7不变，不新增环境开关。未来MEASURE工具严格绑定v5任务/Prompt并保留v4依赖资产，按固定路径取hash，不接受旧manifest、缺v5资产或旧Prompt冒充新冻结；本轮没有实际创建冻结、authorization或结果目录。

设计增量执行两轮作者内审、一轮未参与起草执行单元的独立定向设计评审及一次S2修复复核；修复helper资产位置耦合与绑定说明后S0/S1/未处理S2均0。另一独立执行单元核查关键源码、调用方、测试与严格冻结规则并执行non-live检查；原Minor要求错definition在真实Provider分支也证明零资源，已用合成测试密钥和禁止客户端factory补齐STUB/DEEPSEEK各反例，复评无未关闭Blocker/Major/Minor。它不是外部人工UAT评价，也不以作者总结代替源码核查。

实际验证（均无真实推理或目标服务操作，测试HTTP为fake）：

- `agent-runtime/scripts/run-nonlive-regression.ps1 -PythonExecutable D:/codex/agent-runtime/.venv/Scripts/python.exe`：正式临时隔离安装入口，Transaction host/preflight **14 passed**；全量收集5735项，**5707 passed / 28 opt-in skipped / 0 failed**，878.41秒，有1条LangChain依赖的PendingDeprecationWarning。跳过项未执行、不记为真实UAT通过；这套全量收集后增加的test-only反例由下一项单独覆盖，计数不相加冒称一次新全量。
- `python -m pytest -q tests/contract/model/test_action_selection_v5.py tests/integration/knowledge/test_minimal_current_root.py`（子进程模型密钥置空、PYTHONPATH仅指向当前src）：最终**42 passed**，10.75秒；包括v4兼容、v5 exact输出、错definition零客户端、当前enabled任务版本、fake不存在资料no_result、unsupported/非法输出/Provider超时或失败零下游、disabled保留v4构造及无Knowledge依赖。
- `python -m mypy src`：Success，153个source文件；`python -m compileall -q src`及本轮修改的测试/helper文件通过。未改Java或PowerShell，未重复Maven或AST，不将既往执行误称本轮新验证。

初次定向收集受本地旧安装包影响，改为子进程src路径后继续；一处新增测试使用了不存在的枚举，按真实合同修正。随后172项定向检查中171通过、1个新增fake空结果断言错误：现公开reason是`no_candidate`而不是`no_retrieval_hit`，已改为精确既有对象断言，未改生产reason或放宽校验。disabled构造测试初稿错误地期待空catalog发起模型请求，实际原合同在空catalog时零I/O失败关闭；调整为核对默认v4构造，不为错误期望修改生产行为。后续完整隔离回归和最终42项均通过，不隐瞒这些失败与修正。

既有索引/Profile及读取/出域配置、旧v4/Business v7、12题dataset及历史B/MEASURE运行资产相对起始Git未改；原manifest、cases、failure及B比较result四项SHA-256核验通过。新工具不是旧冻结批次运行过的版本，旧资产仍按各自frozen HEAD追溯。L1架构、L2详细设计及P3三个strict校验器均0错误0警告，五份修改文档96条本地链接通过，工作包直接依赖和状态计数未变。没有新模型、ES、embedding、rerank调用、服务启动、alias切换或发布；没有修改gold、阈值、预算、公共DTO、安全策略或12包DAG。本轮仅本地提交，不push或部署。

COMPARE/MEASURE仍In Progress，RELEASE仍Blocked：B recall相同没有收益、215项盲标仍缺；004仍Failed，005根因未知、006～012未执行，整批仍invalid_run。v5机械证据不证明004真实改善或完整新版37/37/12题通过。下一次真实验证须另行作独立决定，不能复用原目录、余额或以本节恢复授权；整体目标未完成。

### 14.39 验证可靠性与检索诊断的定向设计（2026-10-03）

起始clean `codex_0915` HEAD为`62532b5bf1cb93b0811260da1873313baa7103f1`。维护者同意此前推荐内容继续推进：先解决正式验证路径的可复现性及检索损失定位，再比较是否需要在线表达/有限补检；本轮只完成六份文档增量，不实施代码，不启动新真实批次。

L1_01 v3.7 §4.7/KQ-AD-029/030选择保留当前LangGraph顶层路由及固定Knowledge pipeline；内部拆图不是召回优化的自动前提。流程L2 v3.7 §20定义同正式runner的无付费演练、单一预算推导、失败attempt记账、有限取证及owned清理。检索L2 v3.13 §9.9定义原文/过滤/初召回/融合/重排/Evidence的损失归属及unknown边界；grep只作离线来源定位，不进入Runtime。受限查询表达、最多一次补检与LangGraph内部分步仅为后续比较项；Deep Agents、父单元补取和图谱不进入当前主线。没有改变现原问、域、次数、公共DTO、索引、读取/出域或引用合同。

UAT_02 v3.34 §5.6/6.4区分无付费演练与真实验收、候选采用与不采用：明确必要正向条件不满足时，允许独立作“不采用”的决策，不为否决继续强制补齐不会改变决定的标签；未知precision/usefulness仍未评。原正向阈值、gold、分母和历史结果不改；不自动关闭整个COMPARE、A或RELEASE。

新增`WP-KVERIFY-DRYRUN-01`和`WP-KRETRIEVAL-DIAGNOSE-01`，分别只直接依赖已Done的COMPOSE及RETRIEVAL，14包/14直接边无环。两包技术Ready、未实施，不互相阻塞，不增加编号Gate；原9 Done、COMPARE/MEASURE In Progress及RELEASE Blocked保持。后续真实调用必须重新独立决定和冻结，不能使用已消费批次或本节恢复历史预算。

两轮作者内审分别检查安全/执行与召回归因、追踪/直接依赖及状态保真；strict初检发现新追踪表头/编号定义不完整、Ready声明的字面兼容要求，已补齐实际映射，未修改校验器或降低检查。一个未参与起草的独立只读执行单元直接核查REQ、最小plan/stage、正式runner/ledger/launcher及原始小型终态/指标，发现一项S2：新增六列追踪行误入三列责任表。已移回正确主矩阵，复核本次六份增量符合，未处理S0/S1/S2均0。不是外部人工UAT，也不是全套设计/代码重新审查。

实际检查：L1架构strict、两份L2 strict及P3 strict均0错误/0警告；六文档106条本地链接存在，fence完整；14包/14边无环且Ready前置均Done；新增行敏感模式扫描和`git diff --check`通过。MEASURE manifest/cases/failure及B comparison-result四项SHA-256与原README一致。只改本轮六份当前Markdown，代码/测试/配置/历史资产未改；模型、ES、embedding、rerank及服务操作均0。未执行Python/Maven功能回归或真实UAT，因为未改实现；文档检查不证明新包实施或召回提升。本轮只本地提交，不push或部署。

下一步优先实施`WP-KVERIFY-DRYRUN-01`；纯离线`WP-KRETRIEVAL-DIAGNOSE-01`可独立推进。诊断完成后再选择最小检索修正，不立即增加框架、循环、topK或付费候选。整体剩余实施/验收目标仍未完成。

### 14.40 DRYRUN本包完成证据（2026-10-03）

起始clean `codex_0915` HEAD为`a1a77655617935456eb10246559589f7bdbcc2fa`。维护者明确要求继续新演练包；本轮仅实施DR-KFLOW-401～403的验证工具、合成测试、代码复评及状态同步，不自动启动DIAGNOSE或任何真实批次。代码/测试提交为`f32e84be46f2201054db7e4c56d73d3154c4e3b2`，本地`codex_0915`、未推送。

| 规则 | 实现与直接验证 | 证明范围 |
|---|---|---|
| DR-KFLOW-401 | runner私有`_NonLivePorts`与合成身份/hash前检；`test_knowledge_rebuild_dryrun.py`通过实际`run_once`、当前root、ASGI、decoder/validator/ledger及checkpoint完整执行12题 | 同正式控制流的纯内存依赖演练；合成Spring桥不是实际Java服务或真实协议证据，fake资产不能进入live入口 |
| DR-KFLOW-402 | 冻结`MeasurementPlan/PLAN`由任务、题、域及路径推导；prepare/runner/startup/launcher共用，未来冻结包含新模块hash；发送前attempt、失败不退回、越限拒绝测试 | 预算仍为12题/模型36/typed48/embedding12/rerank24，正式metadata72、startup48；合成预热及健康计数不冒充效果，旧manifest不改 |
| DR-KFLOW-403 | 白名单reason/stage/errorSource、未执行清单、独占append-only写入、有界server关闭及最终owned清理；CLI取消安全分类、实际launcher生命周期/PID复用动态反例 | 启动部分失败、中途非200/malformed/超时/拒绝/非法引用/题前后快照漂移、checkpoint/failure写失败及cleanup超时均可失败关闭；无任意异常文本或后续请求 |

12题合成正向的实际账本为model36、typed24、embedding12、rerank12、24次身份检查/48次内存metadata读取；每题一个Runtime调用，全部客户端关闭，生成的仅是`non_live`/`liveConsumable=false`合成消费和结果，不生成真实授权。模型、目标ES、BGE及Business真实调用均0，未读取真实模型密钥、未操作服务/索引/alias。合成问题不替代已冻结12题gold或真实回答评价。

正式代码初评直接核查源码和合成故障，发现两项中等问题：题前快照异常丢失已知原因/题号，CLI取消可越过`except Exception`泄漏原始文本。已跟踪有限stage及当前题号、保留未发送题为未执行，显式捕获取消/中断并输出固定非零分类；独立执行单元复评和最后预算/文档对照复核均通过，本包未解决Blocker/Major/Minor为0。另按真实公开合同修正可空citation元数据的review投影，不放宽原文/引用validator；server无界关闭改为有界等待，已退出父进程不再枚举复用PID，最终cleanup失败不报成功。主执行者完成两轮定向自查，不能把自查当独立评审或人工UAT。

本轮实际验证（命令在`agent-runtime`执行）：

- `./scripts/run-nonlive-regression.ps1 -PythonExecutable D:/codex/agent-runtime/.venv/Scripts/python.exe`：Transaction冻结host/preflight **14 passed**；正式隔离全量 **5733 passed / 28 opt-in skipped / 0 failed / 1 warning**，895.73秒。此全量在最后代码评审修复前启动，最终受影响工具随后另作下列完整定向回归，不将未进入原收集的新增反例算入全量数字。
- 临时进程`PYTHONPATH=src`后执行`python -m pytest tests/uat/test_knowledge_rebuild_dryrun.py tests/uat/test_knowledge_rebuild_measure_harness.py tests/uat/test_knowledge_rebuild_measure_fixture.py -q`：最终 **128 passed**，82.38秒；其中新演练27项。独立复评另实跑6项，6 passed / 21 deselected。
- `python -m mypy --strict src`：153个source文件无问题；临时`MYPYPATH=src`后对runner、prepare、startup、budget执行`python -m mypy --strict --follow-imports=silent ...`：4个文件无问题。`python -m compileall -q src tests/uat`与改动launcher的PowerShell AST通过。直接使用旧venv安装包曾导致收集/类型导入失败，正确限定当前src后通过，未忽略错误或修改断言掩盖。
- 文档L2 strict与P3 strict均0错误/0警告；本轮四文档本地链接与fence、版本及14包/14边无环检查通过。有限敏感模式扫描、工作区及暂存`diff --check`通过。
- 原MEASURE manifest/cases/failure及B comparison-result四项SHA-256与本包起始记录一致；其余历史资产无Git差异，正式隔离回归中的历史完整性检查保持通过。本轮未修改生产src、公共DTO、配置、dataset/gold/阈值或历史结果。

未执行Maven、实际Spring服务全链、真实ES/BGE/model或新UAT：本包未改Java及线上实现，测试中的Spring桥与launcher资源皆为合成替身，不能据此证明真实依赖就绪。测试运行产生的临时合成结果不作为正式MEASURE evidence提交；代码、可复现测试和本节有限验证记录构成本包交付。本地文档提交单独收口，不push或部署。

DRYRUN在上述non-live范围Done；DIAGNOSE仍Ready且未启动，COMPARE/MEASURE仍In Progress，RELEASE仍Blocked。既有B主指标未改善及MEASURE invalid_run终态不变，005旧根因仍未知，不按本轮fake异常重新归因。下一步实施`WP-KRETRIEVAL-DIAGNOSE-01`，先基于封存traces定位原文/过滤/召回/融合/重排/Evidence损失，再决定最小改进；不得立即复跑MEASURE、追加候选或启用线上grep/Deep Agents。整体Knowledge剩余实施和验收目标仍未完成。

### 14.41 封存B的有限不采用决策与排名损失复核（2026-10-03）

起始clean `codex_0915` HEAD为`59c627276c11a732631e91ee3483e0d8d371c1e9`。继续整体目标时，只读重放既有B/MEASURE有限资产及当前验收合同；不实施DIAGNOSE工具、不操作当前库、不启动批次或使用旧预算。沿用UAT_02 §6.4已批准的有限否决规则，当前B候选**不采用，保留现行b2**；这项决定独立于尚未评价的precision/usefulness，不关闭整个COMPARE、A、MEASURE或RELEASE。

实际运行现有`rebuild_b_review`的`_frozen_spec`、`_completed_run`、`review(labels_raw=None)`和`score_comparison(labels=None)`，通过冻结Git来源、双臂扫描/映射、Java见证、预算及请求见证的一致性检查，再重算10题/16个必要来源组合。此检查不独立重建当时进程或第三方并发，不构成新的真实执行证明。宏平均recall仍为0.85/0.85、215项盲标均未填、precision仍null，原评分仍`not_assessed`。按必要采用条件“recall必须严格提高”，该候选已不能通过；不需要为这一否决补齐不会改变结论的215项标签。若后续单独研究噪声，仍需真实人工标签，不能由执行者或模型代填。

本次新增的逐阶段观察（只比较相同document/chunk/content hash的排名，不解释为相关性评分）：

| 封存B题号 | 两臂向量前20及最终候选变化 | 必要来源最终排名及影响 |
|---|---|---|
| 001 | vector共同14项，final20共同14项 | living/food_lodging/lodging仍分别4/2/1；必要覆盖不变 |
| 002 | vector共同18项，final20共同18项 | lodging仍为1；必要覆盖不变 |
| 012 | vector共同8项，final20共同13项 | lodging的vector排名1→8、RRF排名2→15，rerank/final仍为1；lease_real两路均未进入前20 |
| 003/005/006/007/008/009/011 | 其余7题的keyword/vector/rerank和final20排名均相同 | 16个题—必要来源组合的final排名全部未变；003的small_2022仍两路未召回 |

所以“向量输入发生变化”不等于“核心证据覆盖提高”；当前B改变了部分竞争候选，没有解决两个已知必要来源的初召回缺口。不能由此断言所有表示策略无效，也不能把缺失归为rerank或Evidence：缺失来源未进入这些阶段。完整源身份库存可证明两个精确来源存在，旧trace仍没有目标记录当时的完整过滤/授权判定和窗口外排名；词法、向量、过滤与窗口之间的根因仍unknown。§14.36的独立当前元数据观察只证明其当时诊断范围，不回填为旧B证据。

MEASURE 005仍无可追溯的公开错误响应，具体技术根因不可验证；001/002的维护者Passed、003/004 Failed和整批invalid_run保持不变。本轮只读排名不重建MEASURE搜索轨迹，也不把验证工具修复证明扩成旧005根因已修复。

另一未参与文档起草的只读执行单元直接读取原始trace、冻结映射和评分源码，并独立运行上述四个既有函数、按MEASURE来源重算交集/排名，10题及16项来源与上表一致，P3决定的定向复核无确认问题；这不是完整代码评审、真人标签或回答评价。主执行者另检查三份状态文档76条本地链接及fence、P3 strict（0错误/0警告）、版本引用、有限敏感模式与Git差异；四项历史MEASURE/B关键文件hash不变，其余历史资产及代码/测试/配置无Git差异。本轮未改可执行文件，未重复全量Python/Maven或真实UAT；只在内存计算，不追加运行结果或修改盲标模板，只作目标文档本地提交。

下一步仍为纯离线`WP-KRETRIEVAL-DIAGNOSE-01`的实现交接；新工具须明确区分缺stage与确认未命中，并只输出有限身份/hash/阶段。只有诊断得到足够证据，才从L2_01_01 §9.9选择最小修正；不能直接加topK、补检、grep在线工具或Deep Agents。新真实诊断、测量和发布仍需各自精确范围及有效授权，不恢复已消费批次。本轮状态仍为10 Done/2 In Progress/1 Ready/1 Blocked，整体目标未完成。

### 14.42 DIAGNOSE有限离线范围完成（2026-10-03）

起始clean `codex_0915` HEAD为`74d285f0c6acf6816a7770f73528e18f3bf33d6e`。继续总目标时落实DR-KRET-401～403的纯离线诊断及决策交接；代码/测试提交为`9f43baa9625a65ee0f5fd226ac4d51f48293346d`，仅本地提交、未推送。不启动服务、连接现库或读取模型密钥，不恢复任何失败批次或预算。

[诊断入口](../../agent-runtime/tests/evaluation/knowledge/rebuild_retrieval_diagnose.py)复用`rebuild_b_review.load_completed`的冻结Git、来源清单、attempt/result及盲标池严格准入；原评审入口仍使用同一验证，不改变旧评分或补标签。诊断额外校验冻结plan的域/path、各路top20、RRF成员、重排输入及final20范围，非法记录失败关闭而非截断。通用纯函数明确区分`missing_record`、`no_hit`和`hit`，未知过滤、ACL或根因不填成失败结论。报告只输出有限身份/hash、阶段排名及原trace位置，不保存正文、向量、问题、凭据或原始响应。

`locate_literals`只对上游明确批准、hash相符的有限内存公开来源作字面定位：最多30项来源、每项64KiB、16个预先确定的词、每词128字符、总返回上限32项；只返回词序号和连续span，不返回词或正文，不读目录、执行shell或接收正则。其验证仅使用公开合成fixture，不宣称已扫描实际全库或能代替授权/语义召回证明。

严格重放既有完整B（result SHA-256 `50a03b7dc8cb8e2667c0bc509346e4db12f4fc6c5ceee953ed8dbd39ac21a934`），10题/16个必要来源出现项、双臂共32条；两域按冻结binding共用同一物理库存，两份完整15,521项映射均保留。32条身份/hash均在相应库存存在，28条进入final20。原Evidence/回答未记录的阶段保持缺记录；库存存在不等于完整ACL、category或出域获准。

| 来源/题目 | 两臂可确认损失 | 不可确认及下一最小选择 |
|---|---|---|
| UAT-KM-003 / small_2022 | 来源存在，keyword/vector top20均无；RRF/重排/final20未取得它 | 只能定位初召回之前或窗口内，不能直接归因过滤、词法、向量或窗口。§14.36通用联合机关词法修正已有non-live证明，下一步优先比较其有限隔离typed收益，不把当前源码修正反写成旧运行根因或已部署收益 |
| UAT-KM-012 / lease_real | 来源存在，两路top20均无；不是被rerank或Evidence丢弃 | 原问无文号，不能注入gold文号。先补足有限过滤/初召回观测；没有窗口外排名证明，不直接加topK、改写、补检或框架 |
| 其余必要来源 | 共28条进入final20，包括RRF低位经rerank恢复的来源 | 不以RRF低位单独认定丢失；没有Evidence/回答trace或人工标签，不声称充分性或usefulness通过 |

沿用§14.41有限否决：当前B不采用、保留b2；原recall两臂0.85、precision=null、215项未标及历史Not assessed均不变。未知不自动选择新的在线方案；当前原问、域集合、search/embedding/rerank上限和minimal配置不动。不实施在线grep、父单元读取、Deep Agents、图谱或循环补检。

本轮实际验证（工作目录`agent-runtime`，`PYTHONPATH=src;.`，禁用插件自动加载并显式加载现有`pytest_asyncio.plugin`）：

- `python -m pytest -p pytest_asyncio.plugin -q tests/evaluation/knowledge/test_rebuild_retrieval_diagnose.py tests/evaluation/knowledge/test_rebuild_b_review.py tests/evaluation/knowledge/test_rebuild_b_comparator.py`：最终125 passed，59.48秒；含42项直接诊断及既有B读取/评分/失败关闭回归。
- `python -m pytest -p pytest_asyncio.plugin -q tests/unit/knowledge/retrieval/test_minimal_stage.py tests/uat/test_current_traceability.py tests/uat/test_knowledge_traceability.py`及六份`test_live_p5_candidate_{01,02,04,05,06,07}_history.py`（实际逐文件展开）：93 passed，9.19秒；原问/单次路径/零fallback与历史Business、Knowledge追踪兼容，不是本轮真实UAT。
- `python -m mypy --strict src`：153文件通过；`python -m mypy --strict --follow-imports=silent`检查本轮两份工具：2文件通过。三份修改Python文件的`compileall -q`通过。
- 首轮扩大回归命令漏显式加载异步插件，56项async用例不能执行；纠正命令后全部通过，未修改测试/断言或忽略失败。新诊断早期错误地以canonical sidecar reader读取pretty-printed冻结fixture，直接测试检出，改为经原严格准入及hash绑定的fixture解析，未修改旧fixture或放宽原准入。

作者定向自查后，一个未参与修改的独立执行单元直接核查原设计、冻结源码及两份完整映射，发现一项P2：第21位候选/非法path可被误当合法阶段。补齐冻结窗口/path/成员校验与10项反证后复评无新缺陷；审查者独立复现完整入口拒绝并运行42项新测试通过（5.29秒）。该评审只覆盖离线切片，不是全仓或外部人工UAT。没有更改生产源代码/配置、公共DTO、模型任务、gold、阈值、历史资产或索引；不机械重复Java/Maven、Spring真实E2E、PowerShell AST或完整隔离Python回归，上轮DRYRUN全量证据保持原范围。

四份文档同步的独立定向复核无确认问题，不重新批准全部设计。P3与L2严格校验各0错误/0警告，85条本地文件链接无缺失；新增文档行的有限凭据模式扫描无发现，四项B/MEASURE关键资产SHA-256均与封存值一致，Git差异检查通过。链接检查不代替所有章节语义复核，有限敏感模式扫描也不宣称能穷尽所有秘密格式。

DIAGNOSE在可定位报告、明确unknown及有限决策交接范围Done。当前11 Done/2 In Progress/0 Ready/1 Blocked、14包/14直接边保持无环；COMPARE、MEASURE未完成，RELEASE仍Blocked。新的非付费检索诊断或实际词法收益比较仍须独立冻结精确范围、预算及运行条件，不消耗旧4GET或旧B/MEASURE余额。未获有效新范围前停止真实执行；完整质量、12题测量、人评及发布未满足，整体目标不标完成。

### 14.43 同现行索引的独立有限词法诊断（2026-10-04）

维护者确认一次独立、无付费的旧/当前`DocumentNumberQuery`比较及窗口内无其他索引/alias修改；不继承旧4GET、B或MEASURE余额。起始HEAD `3c2f6a97ef2497f15198227ce3e9f2bd240c6f69`，仅实现[私有诊断入口](../../agent-runtime/tests/evaluation/knowledge/rebuild_lexical_probe.py)及直接测试，本地提交`1630138d55476fbfe8d59805618b6dcb8a38fc48`后冻结干净代码。原生产源码、任务、配置、公共DTO、gold及阈值不变。

[本次manifest](../../knowledge-corpus-tools/evidence/knowledge-lexical-probe-20261004-01/manifest.json) SHA-256 `6cb0cd6159a018f58b540ddbffe6a333e5eebde1c9959086170a859e2c96dbe4`绑定上述提交、原题001/002/003/012和必要来源。两臂使用同一当前archive/YAML/现行b2索引，仅旧臂替换来自`a1ba290e8b2d78da71d46bc1f39018be502c7347`的helper。先离线Maven双构建及独立`javac`检查真实Java `buildSearchBody`，四题物理请求与固定投影精确相同后消费授权；build使用`-DskipTests`，不计Maven测试通过。

运行使用两台本次owned隔离es-query Java及loopback白名单代理，沿用现行typed接口、正常只读alias、内存VIEWER用户JWT和严格Python响应解码。代理只放行固定元数据及逐题唯一keyword查询，发送前journal记账；gold仅用于离线来源核对，不进入查询。禁止cluster health、物理写入、B专用alias及失败后重试。正文、HMAC、JWT和原始响应只驻留内存，不进入有限证据。

[结果](../../knowledge-corpus-tools/evidence/knowledge-lexical-probe-20261004-01/result.json) SHA-256 `84c68b3eb4f460e90a018f9dafb96353f6bfb0a0a9f4a663377095e87f3b8358`：唯一终态`completed`、reason=null，typed8/物理search8/ES元数据18/本地readiness4（上限40）；模型/embedding/rerank/索引及alias写入均0，retry/resume禁用，proxy violations0，owned进程和代理清理true。38项journal、8份case投影与结果逐项一致；退出后19221/19222/19321/19322均无监听。该目录不可续跑。

前后alias目标/空flags、索引UUID `jJ5Ww3LCRWWycfDkUZvmdw`、mapping SHA均相同；两臂Profile启动也分别核验两域共用的物理binding。本轮没有全记录扫描，`fullRecordFingerprint=not_observed`，不能继承旧fingerprint作当前全库证明；内容一致性依赖维护者确认的排他窗口及已命中来源hash核对。

| 原题 | 旧helper keyword top20 | 当前helper keyword top20 | 有限解释 |
|---|---|---|---|
| UAT-KM-001 | living第7、food_lodging第1、lodging第2 | 相同 | 完整top20的身份/hash/顺序相同，没有观察到回退 |
| UAT-KM-002 | lodging第1 | 相同 | 完整top20相同，没有观察到回退 |
| UAT-KM-003 | small_2022未命中 | small_2022第1 | 当前联合机关文号软匹配有局部收益，不反写旧失败根因或用例结果 |
| UAT-KM-012 | lodging及lease_real均未命中 | 相同 | 完整keyword top20相同；未测vector、融合、rerank及回答，窗口外排名和过滤原因仍未知 |

本轮实际验证（`agent-runtime`，临时`PYTHONPATH/MYPYPATH=src;../knowledge-corpus-tools/src`）：

- `python -m pytest -q --tb=short tests/evaluation/knowledge/test_rebuild_lexical_probe.py`：最终66 passed，3.17秒，包含硬预算、非法路由、响应边界、单次消费、半包、未启动线程、失败清理、迟到违规及CLI反证。
- `python -m pytest -q --tb=short tests/evaluation/knowledge/test_rebuild_lexical_probe.py tests/evaluation/knowledge/test_rebuild_retrieval_diagnose.py tests/evaluation/knowledge/test_rebuild_b_local_transport.py tests/evaluation/knowledge/test_rebuild_b_local_runner.py tests/contract/knowledge/test_es_adapter.py`：203 passed，61.94秒。
- `python -m mypy src tests/evaluation/knowledge/rebuild_lexical_probe.py`：154 source files通过，仓库strict配置生效；两份新增Python文件`compileall -q`通过。
- 实际离线双构建和真实Java投影检查通过。先前源码启动的类加载及Windows输出编码问题均在真实预算消费前检出，改为独立编译和显式UTF-8输出后通过；没有用放宽投影断言解决。真实执行中相应预检再次通过。

未参与实现的独立执行单元直接读源码和设计，初审指出清理顺序、实际`documentNo`映射、Actuator媒体类型、CLI退出码等问题；复评补充迟到代理违规和未启动线程清理。修复后无剩余Blocker/Major，审查者独立运行16项定向fake通过（50 deselected），未冒称独立执行真实双构建。真实有限证据复核确认38条journal、160项候选及全部目标来源与结果一致；三份状态文档定向复核S0/S1/未处理S2均0，不重新批准全部设计。

主执行者另实跑`tests/uat/test_current_traceability.py`与`tests/uat/test_knowledge_traceability.py`：12 passed，0.20秒；六份`test_live_p5_candidate_{01,02,04,05,06,07}_history.py`（逐文件展开）：14 passed，7.53秒。原MEASURE manifest/cases/failure及B comparison-result四项SHA-256与封存值一致，其他历史资产无Git差异。P3 strict检查0错误/0警告，三份文档80条本地链接及fence通过；有限资产凭据/正文/向量模式扫描未发现禁止内容，不宣称扫描穷尽所有秘密格式。Git范围与差异检查通过，只本地提交，不push。本轮未重复全量Python/Maven、Spring全链、PowerShell AST或历史付费UAT；这些没有新增通过结论。

本次只证明同现行索引、原问、固定keyword窗口下的局部helper收益；不采用旧B候选、不关闭COMPARE/MEASURE/RELEASE，不把003原人工Failed改判Passed。下一步优先解决MEASURE仍缺的当前版本有效终态及回答评价；任何新批次均需独立范围、冻结、预算和授权，不能借本次非付费诊断增加模型调用。012应先保留初召回缺口及unknown，再决定是否需要新的有限过滤/窗口观测，不直接加topK、补检、grep或Deep Agents。

### 14.44 原005解释路径的正式runner合成补证（2026-10-04）

从clean `codex_0915` HEAD `b1907ba137d9d4b1d34d1d45390fbf08518a9a4e`只读复核。独立审查确认旧005的模型transport已完成不等于引用/回答校验通过；旧failure未记录具体公开错误，根因仍unknown。现runner已有白名单失败取证，无证据支持更改生产或猜测旧失败原因；但原12题合成演练均为lookup，不能证明005 explanation已经过正式runner＋生产ASGI。

仅在[演练测试](../../agent-runtime/tests/uat/test_knowledge_rebuild_dryrun.py)新增005原问的explanation正向和非法quote反例，本地提交`e91e3a64996d556e3063f87259cb07f6bf693fd4`。原公开问题只读复用；来源、正文/hash及验证义务明确为synthetic，不沿用software gold，不评价真实召回或回答充分性。正常路径实际经过当前root、意图12、Summary9、typed decoder、Evidence/引用validator、账本、公开投影及清理。负向仅替换quote，保留合法非空claim与存在的ref，确实触发生产连续子串校验；005记录有限`knowledge.summary_failure/downstream`、停止006～012、无成功终态、无标记泄漏并清理所有owned内存client。两项均不可作为真实UAT或旧005根因证明。

本轮实际验证（`agent-runtime`，临时`PYTHONPATH/MYPYPATH=src;../knowledge-corpus-tools/src`）：

- `python -m pytest tests/uat/test_knowledge_rebuild_dryrun.py -k 'original_005 or 005_explanation' -q`：最终2 passed / 27 deselected，2.01秒。
- `python -m pytest tests/uat/test_knowledge_rebuild_dryrun.py tests/uat/test_knowledge_rebuild_measure_harness.py tests/integration/knowledge/test_minimal_current_root.py -q`：154 passed，96.45秒。独立审查者另运行新增及直接相关no-network反例：21 passed / 107 deselected，9.93秒，复评无确认缺陷。
- `python -m mypy src`：153 source files通过；`python -m mypy --follow-imports=silent tests/uat/test_knowledge_rebuild_dryrun.py`：该测试文件strict检查通过；该文件`compileall -q`通过。扩大为`mypy src tests/uat/test_knowledge_rebuild_dryrun.py`仍因未修改的导入辅助文件`test_minimal_current_root.py`报27项既有类型错误，未声称此扩大检查通过，也未以放宽仓库配置或无关改写掩盖。

作者自查及独立只读复评完成；没有修改生产代码、Java、任务、运行配置、固定题/gold/阈值或历史资产。本轮没有真实模型/ES/BGE/Business调用、服务操作或新授权消费；临时合成结果不作为正式MEASURE资产提交。固定fixture及原B result、MEASURE manifest/cases/failure的SHA-256与起始值一致，其余历史无Git差异。未重复全量Python、Maven、真实Spring E2E或付费UAT，原证明范围保持。P3 strict为0错误/0警告，三份文档81条本地链接、fence、有限秘密模式和Git差异检查通过。独立审查直接核对旧attempts/failure、当前测试及三文档，增量状态同步结论符合，无确认S0/S1/S2；不是全部设计或上线重新批准。

DRYRUN仍仅non-live范围Done，14包/14边及11 Done、2 In Progress、1 Blocked不变。COMPARE未完成，MEASURE仍invalid_run且005旧根因未知，RELEASE不具备准入。下一步需要新的独立精确测量决策及冻结、有效完整终态和维护者人工评价；不复用旧授权、不补题、不自行追加真实批次，也不以更多合成测试冒充整体目标完成。

### 14.45 发布alias的确定守卫补齐（2026-10-04）

起始clean `codex_0915` HEAD `f03f1be1f95bde1f804e3721a3c064b3a8809273`。独立只读核查确认现有[release.py](../../knowledge-corpus-tools/src/knowledge_corpus_tools/release.py)只保留alias目标名称、仅拒绝候选持有同名alias、忽略`_aliases`成功回执；这不足以落实L2_01_01 DR-KRET-025及§12.6的候选无alias、现行空flags和`acknowledged=true/errors=false`合同。本轮只修复既有工具的这些确定守卫，不新建发布框架。IMPL-KRET-020及候选构建切片中的“旧release.py不改”限定对应切片，不是RELEASE的全局禁改；其旧冻结版本仍通过原HEAD追溯。

- 前后读取都校验完整alias绑定，批准的StageA空flags `{}`必须精确保持；filter/routing/write-index等漂移拒绝，候选存在任何alias均在写入前拒绝。
- 单次原子remove/add及`switch`签名、ReleaseState、CLI保持；严格检查布尔回执，切后再核目标UUID。不明确回执或切后漂移只失败，不重试、不自动补偿写、不记录成功。真实操作仍依赖排他窗口，未把这些前后检查冒称跨请求CAS。
- 一次成功switch现在需要6次元数据GET和1次alias POST；后续真实发布/回滚预算须按实际调用冻结，不能借用旧工具计数或以本轮fake授权写入。

新增[test_release_guard.py](../../knowledge-corpus-tools/tests/test_release_guard.py)覆盖前置flags、候选残留alias、错误/缺失/非布尔回执、切后flags/UUID/目标漂移及单次原子成功。既有[test_contracts.py](../../knowledge-corpus-tools/tests/test_contracts.py)的成功fixture同步批准的空flags及完整回执，并新增原子动作精确断言；未删除或放宽原断言。

实际验证：

- 工具目录 `python -m pytest tests/test_release_guard.py tests/test_contracts.py -k 'alias_switch or release' -q`：25项fake通过；`python -m pytest -o addopts= -q`：555 passed，10.93秒。
- `python -m mypy --strict src/knowledge_corpus_tools/release.py`：1文件通过；默认`python -m mypy`无法按安装包定位缺少py.typed的包，改用现有源码入口 `python -m mypy --strict src/knowledge_corpus_tools`：28文件通过，没有修改配置或放宽类型检查。
- `python -m compileall -q src tests/test_release_guard.py`及Git差异检查通过。未重复Agent全量Python、Java/Maven、Spring E2E或真实发布/UAT；本轮没有修改这些链路。

未参与实现的独立执行单元直接核对L2、源码diff、CLI与新旧反例，并另运行同25项目标fake，复评无确认Blocker/Major或其他待修缺陷。此结论仅批准守卫增量，不重新批准整个设计或上线。固定12题、原B comparison result和MEASURE failure的hash保持；正文、索引、alias、运行配置、任务、gold、阈值、历史资产未修改，没有真实模型/ES/BGE/Business调用或服务操作。

14包/14边、11 Done、2 In Progress、1 Blocked保持。RELEASE仍缺合格候选、质量/安全和部署回滚证据；COMPARE/MEASURE仍按原终态及§9.1等待相应独立决策，不由本轮守卫或更多fake转为Done。
