# [P3_01] Knowledge 新设计实施计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档标识 | P3_01 |
| 文档类型 | 设计驱动实施计划 |
| 当前版本 | v3.56 |
| 文档状态 | Reviewed（现行职责/历史兼容与冻结顺序的限定增量已复评；原工作包及验收状态保持） |
| 日期 | 2026-10-06 |
| 目标计划路径 | docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md |
| 适用范围 | 已批准Knowledge在线重建、资料组织与检索表示两条主线 |
| 非范围 | Business重新设计、图谱、记忆、多轮、旧候选推进 |
| 权威顺序 | 用户范围 → 仓库规则 → REQ/L0/L1/公共契约 → Knowledge L2 → 当前实现证据 → 本计划 |
| 实施授权 | Ready不等于实施授权。本轮仅授权现行/历史职责隔离、冻结顺序、局部重复检查及文档流水的收口，执行证据见§14.59；无真实服务、模型、ES或BGE操作许可，不推送。历史消费、终态和原范围由§14对应记录追溯，不可复用旧run或余额；未来真实执行须独立精确范围及有效授权，gold/阈值及在线父读取禁令保持 |
| 计划执行状态 | Done=11（含DRYRUN、DIAGNOSE）；In Progress=2（COMPARE、MEASURE）；Ready=0；Blocked=1（RELEASE），共14包/14直接边。原Done证明范围保持；两项新包仅工具non-live及离线诊断完成，不证明效果。B主指标未改善、precision未评；MEASURE完成4题后005技术失败，001/002人工Passed、003/004 Failed，整批仍invalid_run。保留现行b2，不发布/追加实验 |

## 2. 修改历史

历次修改原文见[历史附件](P3_01_EXECUTION_HISTORY_2026-10-06.md)；本次v3.56仅分离历史记录，工作包、依赖、验收及授权边界不变。

## 3. 来源清单与当前基线

| 资源 | 角色 | 层级 | 状态/版本 | 权威范围 | 是否读取 | 置信度 |
|---|---|---|---|---|---|---|
| [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | 目标架构 | L1 | v3.7 / Approved | §4.5/4.6原合同保持；§4.7新增验证/诊断决策 | 是 | 本轮增量已独立定向核查，不证明真实效果 |
| [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | 流程详细合同 | L2 | v3.10 / Approved | §8/19现行静态绑定、§20 DR-KFLOW-401～403 | 是 | 当前类与历史类隔离的限定修订已复评；原演练non-live证明范围不扩大 |
| [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | 检索与资料合同 | L2 | v3.16 / Approved | §9/18冻结顺序、§9.9 DR-KRET-401～403 | 是 | 准备同模型核对与正式当前实例exact分开的限定修订已复评；旧批次、预算及在线补检禁令不变 |
| [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | Evidence/回答合同 | L2 | v3.8 / Approved | §9、§19，DR-KEV-201～206/301～304 | 是 | 当前Stage只绑定Summary9的限定修订已复评；原回答/安全及有限人工结论不变 |
| [L1_00](../design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) | 共享动作选择职责 | L1 | v3.2 / Approved | §4.1按能力职责选择，不预判资料存在性 | 是 | 本轮增量定向独立复评；Business与历史v4不变 |
| [L2_00_02](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) | 模型任务及绑定合同 | L2 | v3.4 / Approved | §6.3、DR-MODEL-112动作选择v5 | 是 | 本轮增量已实施并有non-live证明，不表示实际部署或真实效果 |
| [UAT_02](UAT_02_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 当前验收 | 计划 | v3.54 / Reviewed | 原功能/安全/召回/回答及资料判据，§5.6/6.4演练/诊断与不采用边界 | 是 | 证据入口整理已复评，不重复执行流水；完整质量及发布未通过 |
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

维护者已选择推荐路线，授权本轮**私有协议与non-live验证准备**，交付见§14.46。该确认解决本地准备的范围选择，不是新的真实ES/BGE、MEASURE或发布授权。下一个实际操作阶段仍需完整预算、运行快照及独立授权；未由44次物理search的推导值假定其他ES请求为0。

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

当前Done=11（两项来源设计、CONTRACT、RETRIEVAL、EVIDENCE、COMPOSE、NORMALIZE、CHUNK、REPRESENT、DRYRUN、DIAGNOSE）；In Progress=2（COMPARE、MEASURE）；Ready=0；Blocked=1（RELEASE），各阶段证据见本节历史记录索引。DRYRUN只证明正式验证工具的non-live可靠性，DIAGNOSE只证明有限离线损失诊断，二者不是新真实批次或检索质量证明。仓库Knowledge enabled root接线selector v5/12/9/minimal-v1，disabled保持v4；v5仅有non-live证明（§14.38），不反向替换旧批次的selector v4。Summary9机械non-live与代码复评、Spring合成三模式及有限失败路径已通过，但旧12/8与新12/9证据不能拼接为新版37/37。单域只读预检和最新四题的有限端到端记录不证明完整两域链路、常规生产部署或新版UAT通过。最新B（§14.32）10题协议完整且保存traces，双臂recall@20均0.85、主指标未改善，215项人工盲标仍缺、precision为null；§14.41已作不采用决定，A仍Not assessed，候选只读未发布。最新MEASURE（§14.33）完成001～004后005技术失败，模型13/typed8/embedding4/rerank4，整批failed_consumed / invalid_run；§14.37维护者确认001/002 Passed、003/004 Failed，005根因仍未知、006～012未执行。各旧失败批次保持原终态，不补跑、续跑或复用余额。另获授权的§14.43词法诊断确认003必要来源由旧keyword top20无命中提升至当前第1，001/002/012的keyword top20完全相同；012仍缺两项必要来源，不能证明双路、回答或整体质量提升。观测与动作选择修复仍只具non-live证明。保留现行b2，没有合格候选或发布完成证据，完整测量与新版UAT尚未完成。

### 历史记录索引

下列旧编号仅用于证据追溯，不是当前操作授权；历史原文及原相对链接保留在同目录附件。

| 原编号 | 历史记录 |
|---|---|
| §14.1 | [CONTRACT完成证据（2026-09-15）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-1) |
| §14.2 | [RETRIEVAL完成证据（2026-09-15）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-2) |
| §14.3 | [NORMALIZE启动证据与未闭合条件（2026-09-24）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-3) |
| §14.4 | [NORMALIZE有限来源核验与关闭边界（2026-09-28）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-4) |
| §14.5 | [CHUNK离线实现、验证与复评（2026-09-28）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-5) |
| §14.6 | [本目标的阶段实施、验证及未关闭条件（2026-09-29）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-6) |
| §14.7 | [COMPOSE补证及COMPARE只读前检（2026-09-29）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-7) |
| §14.8 | [当前root→真实typed单域只读接线预检（2026-09-29）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-8) |
| §14.9 | [12题草案原文定位与时效数据边界（只读，未冻结）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-9) |
| §14.10 | [COMPARE旧DOC节标题解析定向修复（2026-09-29）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-10) |
| §14.11 | [COMPARE旧向量溯源与原件结构复核（2026-09-29，只读）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-11) |
| §14.12 | [COMPARE旧DOC原生段落与完整性前检（2026-09-29，未放行候选）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-12) |
| §14.13 | [COMPARE全库只读指纹与单变量边界复核（2026-09-29，未启动真实对照）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-13) |
| §14.14 | [COMPARE模型快照及旧DOC结构只读复核（2026-09-29，未冻结对照）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-14) |
| §14.15 | [B表示接缝与待冻结条件（2026-09-29）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-15) |
| §14.16 | [Summary9当前接线及B冻结设计复核（2026-09-29）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-16) |
| §14.17 | [当前B冻结工具与Summary9三模式合成验证（2026-09-29）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-17) |
| §14.18 | [一次性B/MEASURE工具提交与non-live回归（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-18) |
| §14.19 | [B候选构建、无效比较与MEASURE未冻结准备（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-19) |
| §14.20 | [MEASURE失败终态及B/MEASURE的non-live修复（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-20) |
| §14.21 | [新独立验证批次的准备（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-21) |
| §14.22 | [新MEASURE元数据计数纠正（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-22) |
| §14.23 | [新工具复评与B无推理启动（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-23) |
| §14.24 | [MEASURE独立启动失败（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-24) |
| §14.25 | [B既有候选承接的后验失败及请求见证纠偏（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-25) |
| §14.26 | [私有工具有限失败及清理边界修复（2026-09-30）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-26) |
| §14.27 | [新独立启动预检失败及Java选择修复（2026-10-02）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-27) |
| §14.28 | [修复后新授权的独立无付费预检（2026-10-02）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-28) |
| §14.29 | [新B正式对照后验拒绝及non-live最小修复（2026-10-02）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-29) |
| §14.30 | [MEASURE就绪检查有限诊断补齐（2026-10-02）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-30) |
| §14.31 | [启动与清理修复后继续新独立验证（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-31) |
| §14.32 | [新独立B完整执行与质量边界（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-32) |
| §14.33 | [新独立MEASURE有限失败终态（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-33) |
| §14.34 | [MEASURE失败响应的有限观测修复（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-34) |
| §14.35 | [已封存来源损失定位及部分人评准备（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-35) |
| §14.36 | [独立有限元数据诊断及联合机关词法修正（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-36) |
| §14.37 | [已完成四题的维护者人工结论（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-37) |
| §14.38 | [动作选择职责补齐、v5接线与non-live复评（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-38) |
| §14.39 | [验证可靠性与检索诊断的定向设计（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-39) |
| §14.40 | [DRYRUN本包完成证据（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-40) |
| §14.41 | [封存B的有限不采用决策与排名损失复核（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-41) |
| §14.42 | [DIAGNOSE有限离线范围完成（2026-10-03）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-42) |
| §14.43 | [同现行索引的独立有限词法诊断（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-43) |
| §14.44 | [原005解释路径的正式runner合成补证（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-44) |
| §14.45 | [发布alias的确定守卫补齐（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-45) |
| §14.46 | [文号全检索链的私有草案及non-live验证（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-46) |
| §14.47 | [新快照及发送边界的独立私有准备（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-47) |
| §14.48 | [实际Java离线投影及构建一致性（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-48) |
| §14.49 | [有限attempt日志与失败持久化接缝（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-49) |
| §14.50 | [同产物lease、自有资源与生产Stage装配（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-50) |
| §14.51 | [只读物理代理及发送边界复评（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-51) |
| §14.52 | [自有启动、预热及Stage统一装配（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-52) |
| §14.53 | [全库存发送计数、现场绑定及封存前后验接缝（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-53) |
| §14.54 | [现场身份私有接缝与独立非HTTP计数（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-54) |
| §14.55 | [独立范围消费与私有串行入口（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-55) |
| §14.56 | [实际离线Java投影与下一准备范围（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-56) |
| §14.57 | [独立无付费准备终态（2026-10-04）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-57) |
| §14.58 | [独立成对执行前置失败及有限诊断修复（2026-10-06）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-58) |
| §14.59 | [现行职责、历史兼容与验证冻结顺序收口（2026-10-06）](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-59) |
