# [P3_01] Knowledge 新设计实施计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档标识 | P3_01 |
| 文档类型 | 设计驱动实施计划 |
| 当前版本 | v3.20 |
| 文档状态 | Reviewed（B比较无有效测量；MEASURE冻结批次在首次模型调用前失败；发布未完成） |
| 日期 | 2026-09-30 |
| 目标计划路径 | docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md |
| 适用范围 | 已批准Knowledge在线重建、资料组织与检索表示两条主线 |
| 非范围 | Business重新设计、图谱、记忆、多轮、旧候选推进 |
| 权威顺序 | 用户范围 → 仓库规则 → REQ/L0/L1/公共契约 → Knowledge L2 → 当前实现证据 → 本计划 |
| 实施授权 | Ready 不等于实施授权。当前目标已授权基础实施、有限资料对照与条件发布；此前另行授权无LLM启动预检后新冻B/12题测量、复用既有只读候选，并批准新MEASURE元数据72次（§14.22）。该B承接批次已消费并失败，MEASURE独立启动亦失败且未形成新的正式冻结；旧/新失败run均不可复用、补跑或续跑。本轮继续最小non-live修复、证据保护及状态收口；后续是否准备另一新批次须另作明确决策，本文不是滚动运行许可。不重建候选或扩大预算，在线父单元补取与超范围操作未获授权 |
| 计划执行状态 | Done=9（两项来源设计、CONTRACT、RETRIEVAL、EVIDENCE、COMPOSE、NORMALIZE、CHUNK、REPRESENT）；In Progress=2（COMPARE、MEASURE）；Ready=0；Blocked=1（RELEASE）。B候选只读未发布；新承接比较执行全部10题后因后验归属准入失败记Not assessed，没有有效质量或盲标证明。MEASURE首次正式批次在ledger前失败，后续独立启动也失败，12题仍未执行。人工评价、发布及新版完整UAT未完成，逐批计数见§14 |

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

## 3. 来源清单与当前基线

| 资源 | 角色 | 层级 | 状态/版本 | 权威范围 | 是否读取 | 置信度 |
|---|---|---|---|---|---|---|
| [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | 目标架构 | L1 | v3.6 / Approved | §4.5/4.6最小链路与资料组织、目标有限回答 | 是 | Summary9定向设计已复评，不证明真实效果 |
| [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | 流程详细合同 | L2 | v3.6 / Approved | §8、§19，DR-KFLOW-201～205/301～303 | 是 | Summary9已按目标绑定完成仓库non-live；在线补取未批准 |
| [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | 检索与资料合同 | L2 | v3.11 / Approved | §9、§18，DR-KRET-201～204/301～307 | 是 | B内部双hash请求同一性已定向复评；MEASURE元数据72保持，设计与fake不代替真实运行或质量证据 |
| [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | Evidence/回答合同 | L2 | v3.6 / Approved | §9、§19，DR-KEV-201～206/301～304 | 是 | Summary9三模式Spring合成链已验证；真人语义效果未评价；父正文不自动成为Evidence |
| [UAT_02](UAT_02_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 当前验收 | 计划 | v3.20 / Reviewed | 新功能/安全/召回/回答及资料验证 | 是 | 新B虽执行全部题，后验准入失败仍无有效测量；MEASURE12题、人评及发布未通过 |
| [UAT_00](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | Business维护基线 | 验收 | v3.1 / Reviewed | 固定35风险与Employee15类扩展，原证据范围 | 是 | 历史等价复用，不是本轮UAT |
| [旧P3_00快照](历史文档/2026-09-14-knowledge-plan-handoff/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) | 承接与历史事实 | 归档 | v3.0 / 原状态保留 | §21/22新设计交接，其余旧执行不继承 | 是 | 冻结提交/原资产可追溯 |

原计划建立时的起始代码提交为`8ae32c50a567850c67b4d1e726304934ab07162c`；本次独立目标起点为`2e27086150360bda87ef09e319a2569a2246c07b`，当时仓库生产root绑定11/7/quality-v3，默认Knowledge disabled。当前仓库已成对接线intent12/Summary9/minimal-v1并保持disabled缺省；原12/8组件及COMPOSE的non-live证明按§14.6～14.7记录，Summary9定向证据见§14.16～14.17，工具与回归见§14.18，B有限终态及首次MEASURE准备边界见§14.19，本次MEASURE失败终态见§14.20，单域当前root真实typed只读接线的有限预检见§14.8。COMPOSE Done只指仓库组合根、Spring fake与安全回归；Spring→Runtime Summary9合成三模式及失败链已验证，实际部署和效果仍待后续验证。仓库配置不是实际部署证明；首次正式冻结不构成有效测量，后续必须另行决定是否准备新目标和新批次，不复用失败run。历史审计与运行状态见[迁移清单](历史文档/2026-09-14-knowledge-plan-handoff/README.md)，不复制到新计划作为新验证结果。

## 4. 计划原则与范围

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
| WP-KREBUILD-MEASURE-01 | MEASURE | L2_01_02 §9 DR-KEV-205/206；UAT_02 §5 | 固定12题及一次独立测量；Summary9最小回答接缝已完成 | WP-KREBUILD-COMPOSE-01 | - | Summary9独立任务/严格解码/原文及claim校验/唯一root及验证台同屏引用展示，继而新版本问题/来源/预算绑定、有限结果及真人评价 | REQ→L0/L1→L2设计复评及Summary9定向non-live已通过；§14.20首次正式批次及§14.24独立启动均失败，仍无12题执行及真人评价；技术失败停止 | In Progress仅表示回答接缝与工具已实施；目录/PID/健康路径修复只有non-live证明，旧失败目录均不可复用、续跑或改判；Done包历史范围不改写 | In Progress |
| WP-KORG-DESIGN-01 | DESIGN | L1_01 §4.6；L2_01_01 §18；L2_01_00/02 §19 | 已批准资料组织设计；本轮仅补结构单元与补取边界，不重判原完成证据 | - | - | 设计来源、样本边界及资料方案 | 原设计的内审/复核/文档及Git证明维持原范围；v3.2补充须单独评审和本地提交，不冒称新代码或推送 | 只文档；不动服务/模型/索引 | Done |
| WP-KORG-NORMALIZE-01 | NORMALIZE | L2_01_01 §18 DR-KRET-301～303；L2_01_02 §19 DR-KEV-301；L2_01_00 §19 DR-KFLOW-301/302 | 标准化、不可变源版本及结构可信状态记录；不把现有DOCX乱序产物标verified | WP-KORG-DESIGN-01 | - | normalization_v2.py/来源位置Schema/fixture | TEST-KRET-301、hash/span及不可靠顺序反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | 本包代码与有限来源核对见§14.3/14.4；未批量生成真实v2 sidecar或迁现索引 | Done |
| WP-KORG-CHUNK-01 | CHUNK | L2_01_01 §18 DR-KRET-303/304 | 最小修复受影响DOCX解析顺序，建立结构单元身份、同版本父子关系与连续chunk span | WP-KORG-NORMALIZE-01 | - | parser顺序接缝/chunking_v2.py及段表交错、短长条、表格/否定/例外fixture | TEST-KRET-302；完整单元可按源span恢复且hash一致，跨版本/悬空/乱序失败关闭，不静默遗漏 | 本包离线代码、fixture和复评见§14.5；旧chunker不覆盖，真实资料重切/发布待后续包 | Done |
| WP-KORG-REPRESENT-01 | REPRESENT | L2_01_01 §18 DR-KRET-305/306 | 独立检索表示及token前检；不把父单元或派生表头当可引用正文 | WP-KORG-NORMALIZE-01 | - | 表示构造/model manifest/tokenizer验证 | TEST-KRET-303；明确实际长度单位/版本，无截断、body/input hash独立；旧未知不回填 | 纯构造、固定tokenizer与直接证据见§14.6；无推理或索引写入 | Done |
| WP-KORG-COMPARE-01 | COMPARE | L2_01_01 §18 DR-KRET-307；L2_01_02 §19 DR-KEV-304；UAT_02 §6 | 单变量有限对照 | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | - | 独立新版离线候选构建器、完整竞争池、scope/原文gold/排名损失/四维报告 | fake/类型→逐记录旧向量溯源及人工原文→有限BGE/候选/只读typed；逐阶段损失、keyword漂移归因、人工盲标及停止规则 | A保持Not assessed；B候选只读未发布。旧比较首题前失败（§14.19），新承接比较10题全部调用后后验准入失败（§14.25），均无有效排名/盲标/质量结论；不补跑、不切线上alias | In Progress |
| WP-KORG-RELEASE-01 | RELEASE | L2_01_00 §19 DR-KFLOW-303；L2_01_02 §19 DR-KEV-302/303 | 选定候选兼容发布 | WP-KORG-COMPARE-01 | - | 策略/Profile一致性、精确旧绑定、回滚与冒烟证据 | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；无证据不得发布 | 当前目标仅在条件满足后授权新索引/受控部署/alias写入；生效前仍须核实精确旧绑定与原子回滚；不删旧索引 | Blocked |

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

共12包、12条直接边，无跨主线强制边。原WP/DEP身份保留，不复用退出编号；推荐执行顺序不是新增依赖。

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
| 6 | WP-KREBUILD-MEASURE-01 | In Progress | 无未完成直接依赖；首次正式批次ledger前失败，后续独立启动端口归属失败，修复仅non-live通过 | 两个失败run均不可复用；12题未执行，人工评价未开始，启动前元数据单列。不由修复通过推断真实测量完成或自动重启批次 |
| 7 | WP-KORG-DESIGN-01 | Done | 无技术前置阻塞；后续操作须独立授权 | 来源设计已完成，非新实现 |
| 8 | WP-KORG-NORMALIZE-01 | Done | 无；有限来源核验见§14.4 | 离线版本/来源/结构可信合同完成；不声称全库v2转换或父单元读取 |
| 9 | WP-KORG-CHUNK-01 | Done | 无；代码及复评见§14.5 | v2离线切片合同完成；真实资料重切和候选发布仍未执行 |
| 10 | WP-KORG-REPRESENT-01 | Done | 无；纯构造及tokenizer验证见§14.6 | 不冒称真实向量效果或候选构建已通过 |
| 11 | WP-KORG-COMPARE-01 | In Progress | B候选只读未发布；新承接比较10题后验归属准入失败，缺有效traces/盲标及质量对照 | 直接前置已Done；A为Not assessed，旧/新失败终态不可续跑/改判；后续是否另建冻结批次须独立决定，不以完成调用数代替COMPARE完成 |
| 12 | WP-KORG-RELEASE-01 | Blocked | WP-KORG-COMPARE-01 | 等待直接前置；发布还需§7/8证据 |

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
| WP-KREBUILD-MEASURE-01 | DR-KEV-205/206；DR-KRET-204 | IMPL-KEV-203；IMPL-KRET-203 | UAT-KM-001～012 | VAL-KEV-203；VAL-KRET-203；UAT_02 §5 | In Progress：Summary9仓库接线及三模式Spring合成non-live已完成；正式批次ledger前失败、后续独立启动失败，12题及人工语义评价仍未完成；失败run不复用，修复仅non-live验证 |
| WP-KORG-DESIGN-01 | 设计输入；REQ-KCORPUS-001～006 | 已批准三L2资料章节，不新增代码 | 原资料设计复核 | 原有限审计与文档验证 | Done |
| WP-KORG-NORMALIZE-01 | DR-KRET-301/302及303的来源版本前提；DR-KEV-301；DR-KFLOW-301/302 | IMPL-KRET-301；IMPL-KEV-301；IMPL-KFLOW-301/302 | TEST-KRET-301；TEST-KEV-301；TEST-KFLOW-301/302 | VAL-KRET-301；VAL-KEV-301；VAL-KFLOW-301/302的离线/来源部分；UAT-KORG-001～004/009仅来源身份、附件关系与fake授权部分 | Done；仅本包离线/有限来源部分 |
| WP-KORG-CHUNK-01 | DR-KRET-303/304；DR-KEV-302/303 | IMPL-KRET-302；IMPL-KEV-302 | TEST-KRET-302；TEST-KEV-302 | VAL-KRET-302；VAL-KEV-302的结构/span部分；UAT-KORG-004的unit父子关系、005/006/008 | Done；仅本包fixture/结构部分 |
| WP-KORG-REPRESENT-01 | DR-KRET-305/306；DR-KEV-302/303 | IMPL-KRET-303；IMPL-KEV-302 | TEST-KRET-303；TEST-KEV-302 | VAL-KRET-303；VAL-KEV-302；UAT-KORG-003/007/008 | Done；仅纯构造/固定tokenizer |
| WP-KORG-COMPARE-01 | DR-KRET-307；DR-KEV-304 | IMPL-KRET-304；IMPL-KEV-303 | TEST-KRET-304；TEST-KEV-303；UAT-KORG-001～012 | VAL-KRET-304；VAL-KEV-303；UAT_02 §6 | In Progress；B候选只读未发布，新比较10题执行后not_assessed，typed44/embed10/rerank22；缺有效traces/盲标/质量结论 |
| WP-KORG-RELEASE-01 | DR-KFLOW-303；DR-KRET-307；DR-KEV-302/303 | IMPL-KFLOW-303；IMPL-KRET-304；IMPL-KEV-302 | TEST-KFLOW-303；TEST-KRET-304；TEST-KEV-302 | VAL-KFLOW-303；VAL-KRET-304；VAL-KEV-302；UAT-KORG-012 | Blocked |

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

当前Done=9（两项来源设计、CONTRACT、RETRIEVAL、EVIDENCE、COMPOSE、NORMALIZE、CHUNK、REPRESENT）；In Progress=2（COMPARE、MEASURE）；Ready=0；Blocked=1（RELEASE）。NORMALIZE/CHUNK旧有限证据见§14.4～14.5，当前阶段证据见§14.6～14.25。当前仓库root接线12/9/minimal-v1；Summary9机械non-live与代码复评已通过，但旧12/8与新12/9证据不能拼接为新版37/37。Spring→Runtime Summary9合成三模式及有限失败路径已通过；当前root→隔离es-query-service单域keyword/vector只读接线仅有有限预检，真实typed全链及实际部署未核实。B候选只读未发布，新承接比较10题全部调用后后验归属准入失败，仍无有效traces、盲标或质量结果；MEASURE首次正式批次ledger前失败、后续独立启动失败，12题及人工评价未执行。后续工具修复仅有non-live证明；没有发布，不能宣称新版UAT完成。

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
