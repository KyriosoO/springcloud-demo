# P3_01 历史记录附件

本附件仅保存整理前记录，不是当前设计、计划、验收状态或操作授权。旧记录中的“当前”“本轮”仅适用于当时上下文，不恢复预算、授权或已取消目标，不改判历史结果。

- 原文路径：`docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md`
- 冻结提交：`fed67329bf427ce233bc0e0262dc4859304ad3e5`
- 原文件 SHA-256：`26aaf3f056168f05729e221b0ff991a97cdcbb47f68906ece06d45145a7d3f68`
- 整理日期：2026-10-06
- 当前权威：[P3_01](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md)

历史片段保持原文；附件与源文件同目录，原相对链接不改写。完整整理前文件可从冻结提交恢复。新增锚点只用于旧编号定位。

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
| 50 | 2026-10-04 | §9.1/14.46 | 维护者选择推荐的文号全链对照准备路线 | v3.42完成独立私有草案和内存生产Stage重放；不继承旧B协议或授权，不连接ES/BGE，不冻结真实批次，原包状态与阈值不变 |
| 51 | 2026-10-04 | §14.47 | 本次新库存与真实发送计数不能复用旧工具假设 | v3.43新增新指纹扫描、发送前计数和Java投影hash守卫的fake准备；预算只作条件预测，真实装配、冻结及授权仍未完成，包状态和验收判据不变 |
| 52 | 2026-10-04 | §14.48 | 发送守卫的期望hash须来自实际Java而不是合成DSL | v3.44完成同源码双臂离线编译和22项实际keyword投影；不启动服务，不增加真实操作权限，完整运行装配和质量判断仍未完成 |
| 53 | 2026-10-04 | §14.49 | 发送前计数及失败回执需要可持久化且不泄露异常的接缝 | v3.45新增有限append-only attempt writer与故障反例，仅在合成临时目录验证；不创建实际运行资产，不以caller清理报告证明真实资源已释放 |
| 54 | 2026-10-04 | §14.50 | 离线投影的JAR需保留至owned清理，正式Stage需同路径装配 | v3.46新增精确产物lease、自有资源句柄及计数Adapter/生产Stage双臂装配；仅fake验证，不自动启动服务或获得真实执行授权 |
| 55 | 2026-10-04 | §14.51 | 自有代理需要限定实际ES路径、请求边界及失败清理 | v3.47补齐固定元数据和物理search代理、无隐藏发送守卫及有界连接清理；只有fake/non-live证明，不创建真实批次或改变质量结论 |
| 56 | 2026-10-04 | §14.52 | 启动、预热、生产Stage及清理需使用同一产物与计数器 | v3.48新增统一私有装配与失败反例；只验证non-live生命周期，不核实现场快照或授权，不改变工作包及质量状态 |
| 57 | 2026-10-04 | §14.53 | 全库存读取需发送前记账，后验不能放在日志封存之后 | v3.49复用scanner补齐三元数据与全记录前后核验、封存前postcheck及冻结响应绑定；仅non-live，不新建真实运行或授权资产 |
| 58 | 2026-10-04 | §14.54 | 模型身份检查不得混入HTTP计数或仅信任caller标签 | v3.50补齐现有模型probe、实际产物/配置/catalog冻结及同journal非HTTP计数；仅fake验证，独立授权消费与总入口未完成 |
| 59 | 2026-10-04 | §14.55 | 准备、授权一致性、一次消费、前后验与清理须串行闭合 | v3.51补齐私有外层和固定消费守卫；仅fake验证，不自签授权，不改变质量、历史或发布状态 |
| 60 | 2026-10-04 | §14.56 | fake产物不能替代实际Java构建及请求投影 | v3.52实际离线构建两臂并核对11个域请求，准备下一独立只读范围；不扩展工具、不执行真实操作、不改变包或质量状态 |
| 61 | 2026-10-04 | §14.57 | 维护者精确授权独立无付费准备 | v3.53完成67次ES只读及8次Docker身份操作，封存现场有限证据；不执行正式对照、推理或发布，不改变原包及验收状态 |
| 62 | 2026-10-06 | §1/14.58 | 独立成对执行前置身份核验失败 | v3.54如实封存一次消费后的失败及4次身份探针，HTTP/推理均0；补私有有限失败阶段诊断，不修改历史运行，不补跑，不改变质量及包状态 |
| 63 | 2026-10-06 | §1/3/14.59 | 现行职责、历史兼容及验证冻结顺序收口 | v3.55记录静态12/9装配、准备到执行的纯身份转换和局部重复检查合并；UAT不再复制执行流水，原包、质量和历史终态不变 |

<a id="record-14-1"></a>

### 14.1 CONTRACT完成证据（2026-09-15）

`WP-KREBUILD-CONTRACT-01`已完成，代码提交`21983d8332ebddda31b8cc8a98afad9a26734416`，交付`intent_contracts.py`、`intent_task_v12.py`及三份直接unit/contract/fake Gateway测试。当前核查起点`7b98da62be6c86eae593bf4e4d9c2e9228bc781b`的五份文件与该提交无差异；本轮重新执行直接测试255 passed。原实施轮次另有Knowledge及防回退、strict mypy、compileall证据，本处不冒充本轮全量执行。

独立内部合同不改变旧task11/Summary7/quality-v3生产绑定，也不证明新链路或真实UAT通过。完成状态仅适用于本包TEST/VAL-KFLOW-201；RETRIEVAL和EVIDENCE的直接技术前置已满足。

<a id="record-14-2"></a>

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

<a id="record-14-3"></a>

### 14.3 NORMALIZE启动证据与未闭合条件（2026-09-24）

本地`codex_0915`提交`96cf200c5cc9009a8e587ef75de179a6ddeb6fb6`新增离线`normalization_v2.py`与15项直接测试；严格v2侧车、来源断言、不可变身份claim、原始资产hash、父附件/修订关系、规范解析源span及结构可信状态均有合成正反例。它不接入旧解析、索引构建或在线查询，旧DOCX乱序和扁平表格不被标为已验证。独立只读代码对照复评的阻断/高风险问题已修复，最终Blocker=0、High=0；该评审不证明真实来源或资料效果。

Python3.12隔离环境执行`python -B -m pytest -p no:cacheprovider --basetemp <唯一工作区临时目录> --tb=short tests -q`，`knowledge-corpus-tools`全包306项通过；直接`tests/test_normalization_v2.py`为15项通过。`mypy --strict src/knowledge_corpus_tools/normalization_v2.py`与`compileall -q -f`通过。对一份既有官方附件执行只读抽样：本地文件SHA-256、旧asset manifest及旧parsed record hash相同，父文档ID一致；这是有限历史资产交叉核对，不等于新v2全量来源清单或当前官网复核。截至2026-09-24，当时尚须对冻结来源记录、完整父清单及结构证明作人工核验，关闭`VAL-KRET-301`后才能将本包标Done、解除`DEP-KORG-002`；后续有限核验与边界见§14.4。未知`aging/channel`映射保持unknown，不补造时效或文档类型。本轮没有模型调用、索引/alias写入或在线父单元补取。

先前§13自检记录中的L0_00、L1_00旧版引用欠账，已在另获明确授权后由本地提交`c7f69edc37e41fc4a087e6b24839740db3e664a8`精确修正五处元数据；原复评当时的范围结论保留，不冒称该复评已覆盖后续修改。

<a id="record-14-4"></a>

### 14.4 NORMALIZE有限来源核验与关闭边界（2026-09-28）

只读复核冻结`corpus_audit.v3.jsonl`：5597条、5597个唯一`documentId`，文件SHA-256为`ccdbfbe9983925f937421f31e0717387368416389c636a752544b3c2a506d272`，与既有summary一致。candidate-08的1份官网HTML与4份附件共5项，原始bytes SHA-256及字节数均与既有asset manifest一致，均指向清单中的同一父ID；官网当前页面的标题、文号和四个附件链接与保存的HTML及manifest对应。两个标称`.docx`的附件实际为旧`.doc`字节，原manifest已标`format_mismatch=true`。核对的是全父身份清单的唯一性和这5份有限资产的来源/父子关系，不是逐篇证明5597项的官网可达性、时效或正文完整性。

旧解析记录的749个块序号连续，但`quality=accepted`不构成原文件结构或顺序的独立证明；原DOCX及扁平表格仍为`unverified/review_required`。§14.3当时提出的“结构证明”在本包只能核对其有无并准确记录可信状态，不能要求把无证明资产提升为`verified`；缺证明的内容仍阻断对应候选发布。据此只关闭NORMALIZE的离线合同、fixture及`VAL-KRET-301`有限来源核对部分，解除`DEP-KORG-002/003`。尚未为真实语料批量生成v2 sidecar，也未修改索引/alias；这些不是本包Done的含义，由后续COMPARE/RELEASE按各自范围验证。

<a id="record-14-5"></a>

### 14.5 CHUNK离线实现、验证与复评（2026-09-28）

新增`chunking_v2.py`及`parse_asset_v2`接缝，保持旧parser/chunker和在线链路不变。v2对同一原始bytes先核资产SHA再解析；DOCX保留段落/表格交错顺序，HTML/PDF/DOCX仅在有限可靠边界识别章、节和条。结构单元以同版本源span、parser及hash派生稳定身份；chunk内容必须逐字等于规范解析源的连续子串，条号从原文核对，扁平表格的`tableId`不冒充可信定位。单元完整性与chunk覆盖独立记录；超长无安全边界、短块、表格关系未知及疑似无空格标题均显式保守处理，受影响结果不可发布；无在线父单元补取。

本轮使用隔离Python 3.12环境执行`tests/test_parsing_v2.py tests/test_chunking_v2.py`共21项通过；`knowledge-corpus-tools/tests`全包327项通过；两份修改源码严格mypy与compileall通过。独立只读代码评审初轮发现条号未绑定原文、v2资产hash未校验及真实解析层级缺口，修复并补反例后复评Blocker=0、Major=0。接受Minor=1：无空格“第…节”也可能是普通引用句，首期统一`review_required`并待人工核对，不用猜测标题来换取表面覆盖；测试覆盖此保守路径。评审是同一任务内另一只读执行单元，不冒充外部人员。此处只证明离线代码/fixture合同，未执行真实资料重切、embedding、索引发布、在线UAT或效果测量。

<a id="record-14-6"></a>

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

<a id="record-14-7"></a>

### 14.7 COMPOSE补证及COMPARE只读前检（2026-09-29）

§14.6是v3.4当时的阶段快照；以下是之后的新增证据，不改写该次5332项Python全量或Java模块测试计数。Spring→当前Runtime的non-live测试仍执行16个合成case，新增每案有限`typedSearches`域/路径/Profile和调用计数：政策、法律各keyword/vector两路，双域共四路；拒绝读取案Summary与Business调用0、公开result缺失且三条合成正文不出现在响应、运行日志或有限evidence。测试适配器逐请求核对用户JWT透传，不记录令牌；请求级`ContextVar`与双请求事件屏障反例避免并发串案，有限证据校验器拒绝把错误域路径标为`passed`。定向Python `agent-runtime/tests/system_e2e/test_knowledge_nonlive_runtime.py`为3 passed，定向Java `AgentKnowledgeNonLiveE2ETest`为1测试方法/16合成case通过；`policy_missing`已有独立未绑定文档策略反例，另行定向执行1 passed。受影响测试代码经同目标内另一只读执行单元复评，Blocker/Major为0；其复评不代替真实服务集成或效果评价。

因此COMPOSE只按§5/12的**仓库接线与non-live范围**关闭。UAT_02 v3.5的37项风险中36项具有该阶段直接证据，EV006解释/适用性实质充分性由MEASURE的真实输出与维护者人工rubric判定；当前root→真实es-query-service typed整链及实际部署仍Not assessed，Functional/Safety总体不得标Passed。MEASURE虽因直接依赖满足而转Ready，人工gold/冻结绑定未完成前仍不得启动付费调用。

COMPARE的独立只读执行单元对预登记4份附件核对原始SHA后仅在内存执行v2解析/切片：旧738个chunk对应新100个；这4份样本的有序block文本/hash/种类和parser版本与冻结旧解析相同，不代表其他资料亦如此。按历史b2总量15521估算，A候选构建器上限为ES HTTP 375、写操作838、embedding批次4，低于代码硬限；**这只是历史基数预算预估，不是当前索引冻结或候选构建**。四份v2输出均`publishable=false`，因结构单元缺独立顺序/结构证明，第一份还有4个`review_required`歧义单元。不得伪造`proofRef`或把附件局部收益外推为正文、law或全类型改善。真实A/B前还须解决结构复核、分别冻结≤24题A/B原文gold与阈值、当前索引UUID/全量fingerprint和逐记录旧向量来源；本次BGE推理、ES候选/alias写入及LLM请求均为0。COMPARE继续In Progress，RELEASE继续Blocked。

<a id="record-14-8"></a>

### 14.8 当前root→真实typed单域只读接线预检（2026-09-29）

新增显式opt-in测试`agent-runtime/tests/system_e2e/test_knowledge_current_root_real_typed_optin.py`（本地提交`e6c8f1a2`）：先核对v2运行绑定、policy只读alias唯一目标、索引UUID和mapping，再用本轮构建的es-query-service JAR在`127.0.0.1:19201`启动自有隔离进程；`JAVA_HOME`固定Java 25，随机短期HMAC/JWT只供该进程及当前请求使用。当前`build_runtime`由stub配置与固定fake任务输出驱动，单域`tax.policy`的keyword/vector各向真实typed接口POST一次且均返回200；本地embedding调用1次，rerank上限1次，Business调用0，外部LLM调用0。HTTP客户端已关闭，自有Java进程停止且端口释放；索引、alias及正文均未写入。最终opt-in用例1 passed、单文件strict mypy与compileall通过；默认未显式启用时1 skipped。同目标内另一只读执行单元复评本测试Blocker/Major/未处理Minor均0。

首次启动诊断曾使随机临时HMAC值出现在pytest回溯中；该值仅属已退出的隔离进程，现已失效。测试随后将敏感值移出contextmanager参数、使用脱敏repr、关闭局部变量展示、只输出固定诊断码并在finally扫描临时日志；修复后复评和最终用例均通过。中途一次启动成功但只见1条typed路径，未按通过记录；加入有限路径/状态计数后，最终断言keyword和vector各一次。该预检只证明当前root的单域只读接线，不证明Spring全链、真实模型、Evidence/回答质量、两域权限矩阵、实际部署或新版UAT完成。COMPARE的结构证明、A/B gold及阈值仍缺；MEASURE的12题必要来源、人工rubric和冻结组合仍未确认，故没有读取`LLM_API_KEY`或启动付费批次。

<a id="record-14-9"></a>

### 14.9 12题草案原文定位与时效数据边界（只读，未冻结）

按UAT_02 §5.3固定风险类别整理12题候选问句：其中8题的拟定必要来源在当前policy alias目标`agent-doc-tax-policy-v5-20260907-vector-b2`（UUID `jJ5Ww3LCRWWycfDkUZvmdw`）可定位到具体chunk；其中2016年附件的3个拟用chunk可按当前`content`复算索引`contentHash`，其余8个拟用旧库存chunk的该字段与当前正文直接SHA-256不一致，历史字段口径尚未证实，不能称已按现行正文合同核对。当前typed服务会依据返回的`content`重新计算`contentSha256`，Runtime再校验；旧索引字段差异不直接证明在线Evidence失败，也不能替代原文人工核验。维护者尚未确认任何新gold、逐条相关性标签、完整预期或A/B阈值，故这只是审阅草案，不能据8/12定位启动MEASURE、补算指标或称人工验收已完成。官方政策法规库页面的有限核对支持公告原文期限、资源税法条号、增值税法第十/三十八条等短定位；2016年附件本轮仅有既存官方附件manifest及索引片段，官方DOCX直读未成功，不记为已完成独立原文复核。

时效前检发现一项明确字段错误：当前索引中《中华人民共和国增值税法》的`effectiveDate=2024-12-25`对应成文日期，而官网第三十八条写明2026-01-01施行。公告2022年第13号和2023年第6号原文执行期限均至2024-12-31，但索引`status=ACTIVE`、`validityStatus=UNKNOWN`且`expiryDate`为空；这些字段不足以判断今日效力，也不能把原期限自动推成后续政策结论。当前在线typed响应仅有`writtenDate`等已定义字段，本次不原地修现行索引；使用上述资料冻结时效题gold或构建/发布候选前，须核对官方现行状态与来源断言，按L2_01_01 §18的版本化资料合同修正候选并另行验证。不能据索引`ACTIVE`或错误`effectiveDate`生成肯定适用结论。COMPARE、MEASURE和RELEASE状态保持§5所列未完成。

<a id="record-14-10"></a>

### 14.10 COMPARE旧DOC节标题解析定向修复（2026-09-29）

四份candidate-08原始`.doc`附件的字节数及SHA-256与冻结manifest一致，当前解析重放的block数分别为342/149/187/60。首份附件ordinal 51、58、103、109为“第×节”标题，但冻结旧解析将其标为`paragraph`；根因是`.doc`的`parse_asset_v2`路径未启用已有的有界节标题识别。提交`ebede2ba`仅在v2路径启用该识别并将新输出的parserVersion改为`0.2.1+sections-v2`，历史`parse_asset`及冻结manifest的`0.2.1+structure-v1`不变。四份原件只读重解析后block数不变，首份上述四处均为`heading`；合成定向测试10 passed、`knowledge-corpus-tools`全包429 passed、受影响文件strict mypy通过，另一只读执行单元的定点代码复核无Blocker/Major/Minor。

这些结果只证明已提取文本的节标题分类及v1兼容，不证明原始Word表格、全文顺序或遗漏。隔离Word COM空实例虽设置禁宏、禁链接更新和只读预期，但退出未能立即确认清理；因此未打开任何原件或副本，最终确认Word进程为0、原件hash及目录不变。四份附件仍缺独立、可审计的原文顺序/结构证明，不能仅凭重解析一致性或补造proofRef改为`publishable=true`。该次记录时COMPARE仍In Progress；A/B人工gold、阈值、当前索引冻结及旧向量逐记录溯源尚未完成。本次解析修复与原件复核未写ES、未调用BGE或外部LLM、未切换alias。

<a id="record-14-11"></a>

### 14.11 COMPARE旧向量溯源与原件结构复核（2026-09-29，只读）

在当前write-blocked的b2目标（UUID `jJ5Ww3LCRWWycfDkUZvmdw`）中，按预登记的四个附件assetId有限查询，旧chunk共738条（342/149/187/60），无超时或失败分片。逐记录核对身份、asset版本和SHA-256；`vectorRepresentationVersion=policy-title-section-body-v1`、`vectorModelSnapshotSha256`与旧构建快照相符，按当前`content`及冻结旧表示算法分别复算正文、`vectorBodySha256`和`vectorInputSha256`，738条均一致。因此这四份附件的**旧向量逐记录来源前检**已有结果，不能仅因“只有全局快照”标为`legacy_unknown`；当前有限只读计数为15521，但此次未读取全库向量或计算全记录fingerprint，也未冻结完整当次模型快照和精确候选预算，不能据此启动真实A/B。

四份`.doc`原件的字节数与SHA-256再次匹配既有manifest；机器未找到独立的DOC结构解析器，重复当前`legacy_doc`路径及官方HTML旁证均不能证明原件表格、顺序和无遗漏，四份v2结果仍为`publishable=false`。在不补造`proofRef`的前提下，A的当前样本不准入；B可按事前登记的“原只读索引同chunk基线”规则独立准备，但人工gold、质量主指标及噪声/时延容忍值、当前全库fingerprint、当次同模型快照和精确预算未冻结前，仍不得运行BGE、写候选或声称对照完成。COMPARE为In Progress，MEASURE仅技术Ready，RELEASE为Blocked；本次只读核查未调用BGE/外部LLM或写ES。

<a id="record-14-12"></a>

### 14.12 COMPARE旧DOC原生段落与完整性前检（2026-09-29，未放行候选）

提交`39fa0322`只调整`parse_asset_v2`的`.doc`路径：固定`legacy-doc==0.2.1`，在提取前严格核验完整piece table、CP/FC边界及解码，再区分原生段落结束`\r`与段内手动换行`\x0b`；新`parserVersion=0.2.1+native-paragraphs-v2`。旧`parse_asset`与冻结manifest不改。对既有四份SHA绑定附件只读重放，v2 blocks为342/149/179/60，分别与隔离Apache POI HWPF 5.5.1辅助解析的非空段落数一致；第三份旧187个行块中的两组段内换行恢复为179个原生段落。五处段落hash差异经原始Word字段边界核查，均为8个非显示`HYPERLINK`代码/URL被既有清洗规则移除，8处中文显示文字仍保留；该有限样本中未发现有效正文因本修复丢失。

首次代码复核发现底层库会静默跳过越界piece、公开提取与v2复核可能共同漏字；新增v2专用严格预检及内存篡改负测后，独立复评该范围Blocker/Major/Minor均为0。实际复跑`knowledge-corpus-tools`全包440 passed、strict mypy 23 files成功；四原件原始SHA/字节数保持不变，第三份仅在内存篡改第二PCD时明确失败关闭。隔离解析辅助工具仍在忽略的临时目录，不构成持久独立`proofRef`。四份`parsed_source_v2`的order/structure仍为`unverified`，A的受影响候选仍`publishable=false`；人工gold、A/B主指标及噪声/时延容忍值也未冻结，故COMPARE保持In Progress、MEASURE仅技术Ready、RELEASE保持Blocked。本轮没有BGE/外部LLM请求、ES写入或alias切换。

<a id="record-14-13"></a>

### 14.13 COMPARE全库只读指纹与单变量边界复核（2026-09-29，未启动真实对照）

以仓库现有受限scanner只读扫描当前write-blocked的`agent-doc-tax-policy-v5-20260907-vector-b2`：read alias `agent-doc-tax-policy-v2-read`唯一指向UUID `jJ5Ww3LCRWWycfDkUZvmdw`，mapping SHA-256为`1c2ab9b48ae5b3fcd37b91fec883b6141d3616b2331cdf3a430ea4500a40db82`。69次ES只读HTTP完整扫描15521条及其1024维向量，每页≤250、单响应≤16 MiB；含向量全记录fingerprint为`fb285fc5e5e838fbccb2025f24c0f4472802b8beb7190247cefc9a2978b9a17d`，与冻结b2构建result一致。扫描前后definition、alias和计数不变，ES写入0；这是当前只读前检，不是新候选`CandidateSpec`的正式冻结或质量收益。

A原预登记四份附件的旧b2块数为342/149/187/60，第三份经当前v2原生段落解析为179块；直接用旧b2对当前v2产物会同时改变parser与chunker，不符合UAT_02 §6.1的A单变量判据。本轮隔离HWPF交叉核对仅证明v2提取文本的有限段落对应，尚不足以给四份旧解析源的完整顺序及结构出具持久独立`proofRef`；旧`accepted`及hash不能替代该证明。因此A保持Not assessed/未执行，不按效果失败记录，也不创建额外parser基线或缩小预登记样本来凑通过。若后续能对同一解析源独立证明完整结构并使`chunking_v2.publishable=true`，才重新核对A准入及两候选预算；否则B可按原b2同chunk/正文基线独立准备。

B所需的四附件738条旧向量模型、表示、正文和输入hash逐记录前检见§14.11，全库指纹前检已补齐；仍须维护者确认B精确范围、gold、主指标及噪声/时延容忍值，随后把当次source/alias/mapping、精确`update_ids`和表示binding冻结到正式spec，核对完整当前模型/tokenizer快照与旧快照的同一性并做无截断预检，按最终范围冻结精确调用及写入预算。若仍只替换738条且总数不变，工具公式给出的ES HTTP≤366、BGE batch≤24、写操作738仅为条件性上限，不是已批准的正式运行预算。本轮无BGE/外部LLM、ES写入、alias切换；COMPARE保持In Progress，MEASURE仅技术Ready，RELEASE保持Blocked。

<a id="record-14-14"></a>

### 14.14 COMPARE模型快照及旧DOC结构只读复核（2026-09-29，未冻结对照）

当前运行的`bge-m3-service`容器ID与冻结b2 `binding.json`相同。仓库快照探针只读核对容器、服务、实现、依赖及11个模型文件：旧完整快照SHA-256为`bb701284a410cc88e80816bea0f40c0420fd501ed30f879cd290802c5835b4ec`，当前为`8bfbd88036db6b21263f4927ad093a9e8995e28c4c4f08d94657e98d5deb6d96`；逐字段唯一差异是`container.started`由`2026-09-07T00:48:23.858361985Z`变为`2026-09-28T09:59:52.377452626Z`。四个tokenizer文件的映射hash均为`83715342856e72d33ecc6e5732eefccb01ba21ae1127ca4dd91160860e2f48d7`。这符合L2_01_01 §18.4.1允许的同模型快照差异，仅解除该项只读前检疑点；真实tokenizer无截断、正式spec、人工gold与预算仍未完成。

四份原件SHA/字节与manifest一致，冻结旧解析与旧`parse_asset`重放逐字段相等。隔离HWPF核对均无原生表格；非空原生段落为342/149/179/60，第三份旧187块多出的8块对应两段内的手动换行。当前辅助核对删除空白/控制字符后比较全文顺序，不能充当逐codepoint的持久独立证明。首份旧解析还将ordinal 51、58、103、109四个“第×节”标为`paragraph`并停留在旧章节路径；原件对应段虽无专用标题style，但均居中、首run加粗，与邻近正文格式不同。`chunking_v2`对此类块强制`review_required`。因此不能把旧解析标成结构已验证，也不能靠补`proofRef`放行现有A样本；A保持Not assessed。B可独立准备，但不得跳过§14.13的人工确认与正式冻结。本次没有BGE推理、外部LLM、ES写入或alias切换，COMPARE/MEASURE/RELEASE状态不变。

<a id="record-14-15"></a>

### 14.15 B表示接缝与待冻结条件（2026-09-29）

`L2_01_01` v3.7 §18.4.1 的源绑定及keyword混杂规则已完成定向内审及独立复评（S0/S1/未处理S2均为0）：B模式从同一次已核验的完整源扫描，按预登记`update_ids`确定性重建`body-only-v2`表示；外来表示tuple不能代替源记录，不能为此增加一遍ES读取或持久化正文。内部BGE准备接缝已在本地提交`a5f84f37`，构建器同源重建已在本地提交`9b5a45a2`；后者的48项定向fake及受影响文件strict mypy通过，独立定点代码复核无Blocker/Major/Minor。以上均不包含真实BGE、ES写入或typed对照。一次性入口、正式`CandidateSpec`仍待实施与冻结，不能据此关闭COMPARE。

维护者已确认先把A保留`Not assessed`、按当前b2相同chunk/正文优先准备B；12题草案的问句与必要来源按已批准的措辞调整作为后续冻结输入，既有UAT阈值保持不变。B的事前质量判据确认为必要来源宏平均`recall@20`严格提高、`precision@20`不低于基线、同机同条件median检索时延不超过基线的110%，且核心及保留题覆盖不退化。最终运行仍需逐题人工核实返回候选相关性、精确spec/预算和执行时快照；未取得这些证据时指标为`Not assessed`，不把草案确认说成真实对照完成。独立复核又发现CAS向量更新可能改变Lucene文档状态，B须核对keyword top20及UAT_02 §6.1的盲标、聚合、计时和混杂停止条件；否则不能归因或发布。另发现现有Summary8仅能摘录，不能完成已确认适用性题的有限明确回应；真实模型测量必须待上位回答设计修订、复评及non-live验证后重新冻结，本节不预记任何UAT或发布结果。

<a id="record-14-16"></a>

### 14.16 Summary9当前接线及B冻结设计复核（2026-09-29）

维护者授权REQ_00 §5.2、L0_00 §3、L1_01、L2_00_02及Knowledge L2中仅涉及“有引用有限判断”的最小修订；目标仍禁止无依据适用性肯定、放宽原文引用或改变公共DTO字段。设计提交`10f2f42c`经定向跨层复评S0/S1/未处理S2均为0。运行时取消传播修复提交`c1b886a8`，当前唯一root接线intent12/Summary9/minimal-v1及验证台逐点同屏引用提交`e58f4837`；Summary9独立任务输出经严格Schema、模式、逐点quote/ref/claim配对和连续原文校验。定向fake/non-live、Node展示测试及agent-service Maven均通过；正式隔离Runtime全量为5437 passed、28 opt-in skipped、0 failed。代码对照设计的独立只读复评Blocker/Major/Minor均0。上述机械验证不证明模型真实claim的语义忠实、12题人工usefulness或新版37/37功能UAT；Spring目标12/9全链及实际部署也未记录通过。

`mvnw.cmd -q '-Dtest=AgentKnowledgeNonLiveE2ETest' test`在agent-service当次通过：Spring→当前Runtime执行16个合成case，Runtime fake断言Summary9任务版本，含lookup成功、读取/出域拒绝、引用非法及技术失败；它未覆盖解释/适用性有限claim的Spring端到端语义，不代表真实模型或索引。

`L2_01_01` v3.8、`UAT_02` v3.10已对真实B的两阶段冻结、候选UUID后验绑定、双域物理快照和固定物理查询设计完成定向复评（S0/S1/S2均0）。es-query-service隔离查询接缝已在`codex_0915`本地提交`1ba93bb8`，默认仍走alias；固定物理路径仅在专用隔离配置下启用。es-query-service及common-security当次Maven分别106、21 tests，0失败/错误/跳过；源b2历史build绑定、自算hash篡改拒绝及候选比较器仅有未提交的fake/单元代码。尚无受控双Java实例launcher、运行归属和alias完整flags的前后证据，未创建真实候选或执行真实typed B，因此COMPARE仍In Progress、RELEASE仍Blocked。§14.9～14.15保留各次发生时的状态，不作为本节当前状态的替代权威。

<a id="record-14-17"></a>

### 14.17 当前B冻结工具与Summary9三模式合成验证（2026-09-29）

本地提交`dd73d130`补齐B源绑定、候选规格及比较输入的严格冻结工具。定向corpus测试23项、比较器测试50项通过；比较器fake只能产生`Not assessed / synthetic_only`，缺少隔离Java实例及物理查询归属证明时，真实模式在首次typed查询前失败关闭。此提交没有创建真实候选索引、执行BGE推理或ES对照；真实双实例launcher、运行前后alias完整flags/UUID/mapping及请求目标证明仍待完成。B的盲标和真实指标均未评价，COMPARE保持In Progress。

Spring→Runtime新增lookup以外的explanation、applicability合成场景后，`AgentKnowledgeNonLiveE2ETest`所调用的18个合成case均通过，验证`summaryType=cited_limited_answer`、逐点quote与citation配对及有限claim在公开结果中的结构；没有真实模型、BGE或索引调用，也不证明claim忠实度。维护者对12题回答的人工评价仍未开始，MEASURE保持In Progress。§14.16记录其发生时的16案与未提交工具状态；本节记录当前增量，不改写既往执行结果。

<a id="record-14-18"></a>

### 14.18 一次性B/MEASURE工具提交与non-live回归（2026-09-30）

本地提交`631cc47c4e19ccc17861cc4aba5349a8097282e7`补齐B两阶段准备/冻结、候选接缝、双臂隔离typed比较及MEASURE一次性launcher。B工具核对冻结Git blob、源b2回链、全源ID映射、候选UUID/mapping/fingerprint、两臂Profile/ACL/物理路径和查询体，并对预算、取消及失败终态关闭；MEASURE工具只在既定12题、快照和预算前检通过后允许执行。维护者已确认B独占运行窗口要求，但这一确认及fake验证都不是一次真实窗口或真实对照的证据。新工具尚未消费真实B/MEASURE运行，不据此关闭工作包。

本轮实际验证记录：正式`agent-runtime`隔离non-live回归5481 passed、28 opt-in skipped、0 failed；Transaction host/preflight 14 passed；`knowledge-corpus-tools`全包525用例、退出码0；B定向fake 76 passed、MEASURE定向fake 18 passed；Runtime源码strict mypy检查152个文件成功，B相关3文件与MEASURE相关5文件strict mypy成功；PowerShell AST 0 error；页面UI测试5 passed。Java五模块按Surefire `tests`总数（**包含**skipped）记录：`common-security` tests=21/skipped=0、`employee-service` tests=50/skipped=20、`mq-procedure-service` tests=37/skipped=2、`es-query-service` tests=106/skipped=0、`agent-service` tests=42/skipped=3，均failures/errors=0。旧§14记录中的数字是各次当时结果，本节不回写或相加成UAT总数。

本次外部LLM、真实BGE、真实ES候选写入、真实B成对typed对照和alias切换均为0；没有12题模型回答、全量人工盲标或新版效果结论。A仍为`Not assessed`；COMPARE和MEASURE继续`In Progress`，RELEASE继续`Blocked`。真实操作前仍须核实实际部署/索引/模型快照、冻结精确预算和运行输入；完成真实测量及人工评价后再按UAT_02判定质量与发布条件。

<a id="record-14-19"></a>

### 14.19 B候选构建、无效比较与MEASURE未冻结准备（2026-09-30）

提交`c9b8642e9c20765814df4b3422cfa958a2c4900c`保存[B本次有限证据](../../knowledge-corpus-tools/evidence/knowledge-b-body-20260930-01/README.md)。只读核对`result.json`及source/candidate扫描结果：完整竞争池15521条、其中738条更新，候选`agent-doc-tax-policy-v6-20260930-body-b1`构建使用ES请求363/366及本地embedding批次24/24；构建终态为`built_read_only_unpublished`，线上alias写入0。`binding`、`assessment-intent`、`assessment-final`及`scan-plan`正文SHA-256均与同目录`.sha256`文件一致。以上证明候选构建及来源绑定，不证明召回收益或发布准入。

同目录`comparison-result.json`记录本次成对比较已消费，终态`not_assessed / local_execution_or_identity_failed`：typed search、query embedding、online rerank均为0，预登记10题全部未执行；比较元数据ES请求12次、本次临时alias写入4次，`ownedProcessesStopped=true`、`aliasesRemoved=true`、`proxyViolations=0`。A仍为`Not assessed`；B无盲标、排名或质量指标，本run不得补跑、续跑或改判。静态诊断发现隔离Java启动禁用Config Server却未加载必需配置目录，是待修的启动配置缺口；有限终态未保存精确异常，不能断言它就是本次失败的唯一或直接原因。COMPARE保持`In Progress`，依赖有效比较的RELEASE保持`Blocked`，候选不切线上alias。

[MEASURE本次build-only准备](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-01/README.md)仅保存当时clean HEAD的五个Maven构建及JAR hash；快照生成与服务启动的时序问题使其不作为真实测量冻结。该目录没有manifest、authorization、consumed或模型结果，外部LLM调用为0，不得把build-attestation当成已授权或已执行批次。后续最小时序修复已完成独立复评，20项直接fake测试通过且原120秒快照年龄校验未放宽。隔离launcher仅为Knowledge验证定义`readinessState`与`elasticsearch`健康group，不关闭全局数据库/ES健康；该定向检查不证明整服务或数据库健康，也不是真实启动通过证据。仍须在新的clean HEAD上重新准备和核验正式冻结，MEASURE保持`In Progress`。本节只同步新发生事实，不修改§14.1～14.18当时的结论、历史资产或UAT阈值。

<a id="record-14-20"></a>

### 14.20 MEASURE失败终态及B/MEASURE的non-live修复（2026-09-30）

[本次有限失败记录](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-02/README.md)绑定run `knowledge-rebuild-measure-20260930-02`、clean HEAD `d54ee293ec6517571f8a37fc616b1a7fceef19a3`及manifest SHA-256 `c10068ca11041917aaa4817f52b884caf90e0a01338872ec6b75bcf2e1f05450`。`manifest.json`、`authorization.json`、`build-attestation.json`三份冻结资产原字节保留；授权状态仍为`authorized_unconsumed`，但失败run不复用、不补跑或续跑。launcher报告三项自有隔离Spring服务完成目标健康、端口归属、登录和完整b2快照前检后才读取进程级模型密钥；这些前检没有持久化可独立复核的运行快照，不能升级为完整真实集成通过证据。

runner进入`run_once`时，`OneShotLedger.__init__`因`agent-runtime/tests/uat/results`父目录不存在且`mkdir(parents=False)`抛出`FileNotFoundError`，发生在Runtime创建、任何case、reserve或consume之前。[执行者有限失败记录](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-02/executor-failure.json)依据实际traceback及冻结源码控制流记`failed_unconsumed / invalid_run`，并记录12题全部未执行、模型/typed search/query embedding/online rerank/Business/retry/resume均0；该记录不是runner自动journal。无consumed或journal文件；自有服务停止、目标端口释放，临时日志与快照已清理。人工rubric、Functional/Safety完整验收、召回和回答均`Not assessed`，不将0调用或部分启动前检当作有效效果测量。

故障后仅在non-live范围修正严格共享结果父目录的prepare、缺目录静态拒绝和PowerShell pre-ledger有限失败fallback；run子目录仍须独占。定向测试23 passed、corpus环境与配置下3个helper的strict mypy、compileall、PowerShell AST 0 error及`git diff --check`通过；独立范围复评未发现新Blocker/Major。该结论不等于整体代码评审、真实启动复测或新版UAT通过。B原比较仍`Not assessed`、A仍未评价，B候选只读未发布，线上alias未切换；COMPARE/MEASURE保持`In Progress`，RELEASE保持`Blocked`。本节只记新发生事实，不回写§14.1～14.19、历史资产或既有阈值。

MEASURE目录前检修复本地提交为`da6f098771a4fa2c50e59b54bf1590e5d0a727a0`，五项有限冻结及失败资产提交为`f250ffcd76ef29e27800e63830089e248617e8c7`。本轮另复核manifest中13项冻结Git blob和5项本地JAR SHA-256，以及manifest/authorization/build三者绑定，均一致；27项历史与当前追踪测试通过。上述完整性核查不补造已清理的运行快照、调用journal或人评。

B启动配置的后续修复本地提交`a7c610e6b518d6b50f5c36fe87d3ad40efff15c4`只在non-live验证：从同一冻结archive加载`application.yml`、`application-datasource.yml`、`application-es.yml`，在构建证明和Profile fingerprint绑定三者hash，缺失或漂移在alias操作前拒绝。B专用就绪group仅含`readinessState`；保留各臂既有六次Profile元数据校验、PID、物理路径、代理权限及冻结预算，不借用MEASURE允许的ES健康请求，也不关闭全局DB/ES健康。B runner/transport/comparator定向fake共81 passed，runner以corpus项目配置执行显式`mypy --strict`成功，两个改动文件compileall及差异检查通过；独立源码复评未发现本修复范围的新Blocker/Major/Minor。没有新的服务启动、ES/BGE/模型调用；不将修复通过当作旧B重跑授权、真实启动通过或质量改善。

本轮状态同步经两轮独立定向文档复评：首轮发现一项Minor，即概要中的“0检索/下游调用”可能误读为启动前ES请求也为0；修正为模型、typed检索等执行调用，并排除启动前只读元数据前检，复评关闭。未发现新Blocker/Major。P3严格校验0 error/0 warning、三份当前文档58个本地链接均可解析；8份状态文档及本次失败资产的JWT/密钥模式扫描0命中。以上均为文档与有限资产检查，不替代真实验收。

<a id="record-14-21"></a>

### 14.21 新独立验证批次的准备（2026-09-30）

维护者明确恢复目标并授权新的独立验证批次：先不读取模型密钥进行真实启动预检，通过后重新冻结B比较与12题MEASURE，正式题目、gold、阈值及调用上限沿用已确认版本。起始HEAD为`037b41335675d17d6b857c8b5f7dbfb9b5f3534f`，分支`codex_0915`且工作树干净。原B和MEASURE失败run不复用，其冻结资产、终态和证明局限保持不变。

当前工具缺少启动only模式以及跨run绑定既有只读候选的入口。L2_01_01 v3.9 §18.4.2已定向补齐内部合同；作者内审和未参与起草执行单元复评先定位旧构建来源闭环S1、元数据分账S2，修正后本切片S0/S1/未处理S2为0。工具准备仍须完成直接fake、类型、AST及代码复评；本文不预记真实预检或新批次通过。不新增Gate、候选索引或公开合同；A仍Not assessed，COMPARE/MEASURE仍In Progress，RELEASE仍Blocked。

<a id="record-14-22"></a>

### 14.22 新MEASURE元数据计数纠正（2026-09-30）

工具源码复核发现`_alias_check`每次实际发送alias与index definition两个GET，12题前后共24次检查对应48次HTTP；§14.21采用的“case 24 + Profile 6 + health 18 = 48”分账错误。主执行者承认并暂停受影响正式预算改动，维护者随后明确授权新批次元数据上限72（case 48 + Profile 6 + health最多18）。L2_01_01 v3.10 §18.4.2据此修正；启动预检独立48、正式freeze binding2及前/后完整快照各67的边界保持。必须在发送前计实际attempt并以硬上限拒绝超额，不删除安全核查、假造计数或回写旧run。模型36、typed search48、query embedding12、rerank24不增加；此文档纠正及工具准备不证明真实预检、测量或发布通过。

作者内审后，由同一任务内未参与起草的执行单元读取L2本节、P3、UAT_02及架构索引完成定向复评，S0=0、S1=0、未处理S2=0。后续代码复核须直接核查双GET经受控代理逐attempt计数，不把`aliasChecks`检查次数与HTTP次数相加冒充实测。

<a id="record-14-23"></a>

### 14.23 新工具复评与B无推理启动（2026-09-30）

本地提交`4b540e5b48bdc39e7ef1d571880cfde31d366675`仅修改私有验证工具及直接测试：B新run绑定旧构建Git来源、独立扫描attempt/terminal和完整记录身份；模型快照前后核验不执行推理；MEASURE受控ES代理在发送前按实际HTTP计数，启动only不读模型密钥，启动前后核验代码、构建及配置hash。两组工具分别由未参与相应修改的执行单元定向复评；B入口复制目录绕过Major已修复，最终Blocker/Major及未处理Minor均0。复评只覆盖工具源码与fake，不证明生产效果。

本轮直接验证：B五文件fake初轮138 passed，目录修复后local runner 42 passed，复评定向2 passed；模型身份fake 7 passed。MEASURE harness 32 passed；8个私有Python源文件strict mypy成功，目录修复后runner strict复查成功；两份PowerShell AST 0 error、compileall和差异检查通过。这些有重叠的定向结果不相加为测试总数。额外探索性地对旧B测试整文件执行strict曾失败（88项，主要为原有未标注fixture），不在当前配置的源码检查范围；未删除断言或扩展无关测试重写，正式私有源码strict与实际pytest均通过。

[B独立无推理启动预检](../../knowledge-corpus-tools/evidence/knowledge-b-startup-20260930-01/README.md)绑定上述clean HEAD，终态`ready`：元数据ES HTTP 30/30、临时alias写4/4、两臂就绪请求5/1；模型、typed/physical search、embedding、rerank、JWT HTTP、retry/resume均0。两个自有Java进程停止、四个目标端口无监听、临时alias移除，生产alias未切换。没有读取模型密钥；旧run和历史资产不变。此证据只证明冻结配置下的两臂服务启动及清理，B成对对照、MEASURE启动及12题、人评和发布仍未完成。工作包状态不变。

<a id="record-14-24"></a>

### 14.24 MEASURE独立启动失败（2026-09-30）

[新启动有限证据](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20260930-03/README.md)绑定`a03486e653a69c434ca18fd5cec943e0aa243881`。五模块clean构建成功后，独立启动在`proxy_start`端口归属检查处终止，`startup_preflight_failed`，现场错误`knowledge.measure.port_owner_mismatch`。模型、embedding、rerank均0，未显式读取模型密钥；绑定前检记录2个元数据HTTP attempt，代理计数未取得，保持null而非补造0。自有进程报告停止，现场核查五个隔离端口无监听。此目录没有正式manifest/authorization/case journal，失败不自动复跑。继续只做根因核查与fake修复，不因此取消可独立推进的B比较；COMPARE/MEASURE仍In Progress、RELEASE仍Blocked，12题真实测量、维护者人工评价及新版UAT均未完成。

本地synthetic进程核实Windows虚拟环境redirector父PID与实际Python子PID不同，且子进程仍使用项目venv。后续私有launcher修复严格绑定父子关系、基础可执行文件、模块角色及创建时间，正式runner传入实际proxy监听PID，未监听子进程亦纳入可核实的清理，无法核实则清理状态失败而非假称退出。另只读核对本地Spring Boot 3.5.10源码，健康请求为`/_cluster/health/`；代理仅新增这一精确等价路径并与原路径共用预算，其他路径/参数/写操作仍拒绝。独立复评确认惰性进程对象的PID复用Major，已通过捕获时固定句柄及创建时间比对关闭，范围内无未解决Blocker/Major；测试基础Python路径从目标venv配置读取，不引入安装路径硬依赖。直接harness 34 passed、受影响Python源strict mypy、compileall、PowerShell AST 0 error及差异检查通过；这些仅为non-live修复验证，不构成新的启动通过或真实批次授权。

<a id="record-14-25"></a>

### 14.25 B既有候选承接的后验失败及请求见证纠偏（2026-09-30）

本地提交`7e3e7d601310ab4204e1f0a8ec98452ba742bed5`保存§14.24所述MEASURE私有启动修复，未复跑启动。提交`a6f83f7f941eedecaccb21fc8354608e0e23408c`补齐离线B复核辅助工具及合法空law路径的评分处理：无标签输出Not assessed，拒绝外来/null标签及与intent不一致的frozen HEAD；空law双路只有均合法零命中时才允许无rerank，非空缺stage仍拒绝。直接fake 69 passed；先前使用`--follow-imports=silent`的探索性类型检查不作为全链证明，随后以corpus项目venv、双源码MYPYPATH及项目配置执行未隐藏import的显式strict mypy，两源文件检查成功，compileall及差异检查通过。独立定向代码复评无未解决Blocker/Major；工具不能凭失败批次补造blind pool或运行归属。

[新B承接有限失败证据](../../knowledge-corpus-tools/evidence/knowledge-b-reuse-20260930-01/README.md)绑定clean HEAD `a6f83f7f941eedecaccb21fc8354608e0e23408c`。两臂完整只读扫描各64次、各15521记录，ID/content hash文件与旧构建Git对应blob字节一致，所有源身份和指纹回链通过；不重建、不写正文、不重算语料向量。正式10题全部执行，typed search=44、query embedding=10、online rerank=22、元数据ES HTTP=30、临时alias写=4；预扫描128次独立分账，付费/retry/resume/线上alias切换均0。两臂进程停止、临时alias移除、proxy violations=0，现场核查四个隔离端口无监听；候选仍只读未发布。

唯一终态为`not_assessed / runtime_provenance_missing`。失败资产未保存双臂请求见证、traces或准入receipt，故不能核查具体触发的后验条件、生成有效blind pool或补算质量。纯离线核查确认Java `Map.of`跨进程键序可不同，而冻结代理以原始JSON字节hash比较请求；同语义不同键序会被误拒，是已证实静态缺陷和本批的强候选原因，**不是本批实际触发条件的确证**。旧/新失败run均不重跑、不补判，A仍Not assessed；COMPARE/MEASURE仍In Progress，RELEASE仍Blocked，12题真实模型与维护者人评未完成。

L2_01_01 v3.11针对该内部缺陷先澄清双hash合同并完成作者内审及未参与起草执行单元定向设计复评；GET摘要歧义S2已关闭，S0/S1/未处理S2为0。原始字节hash保留，规范JSON hash只解决对象键序/空白差异，不放宽路径、授权、次数、索引或清理核查；新的证明形状不补算旧见证。后续只做直接non-live修复验证，不自动启动第三次B或新的MEASURE冻结/真实调用。

有限失败资产已本地提交`0f7466fa17312fa66f6d65cbd94000b870011cbf`，11个原始JSON及说明未改变运行终态；源/候选ID映射blob与旧Git资产完全相同。内部双hash修复本地提交`1c0d6d211135b335ff4b47ab256a165ce2fbde38`，限四个B私有源码、三个直接测试及L2_01_01合同，不改生产查询、Prompt、权限、索引正文或历史资产。同一任务内未参与实现的执行单元初检发现数字float舍入/下溢与receipt条目形状两个缺口，最小修复后分别核验数字词面差异、畸形有限拒绝、严格JSON负例及非法请求backend零调用；定向复评无未解决Blocker/Major。此结论只证明私有工具修复，不证明新真实启动、比较或质量通过。

主执行者实际验证：在`agent-runtime`目录以项目venv执行`pytest tests/evaluation/knowledge/test_rebuild_b_comparator.py tests/evaluation/knowledge/test_rebuild_b_local_transport.py tests/evaluation/knowledge/test_rebuild_b_local_runner.py tests/evaluation/knowledge/test_rebuild_b_review.py -q`，131 passed。首次未指定源码路径时因venv已安装包缺`intent_contracts`产生collection错误；随后仅为该验证进程显式设置`PYTHONPATH=D:/codex/agent-runtime/src;D:/codex/knowledge-corpus-tools/src;D:/codex/agent-runtime`，纠正导入基线后得到上述通过结果，没有安装或修改全局环境、删除断言或跳过测试。两项元数据守卫定向测试`test_formal_proxy_counts_each_alias_get_and_rejects_seventy_third_metadata_attempt`、`test_formal_proxy_records_failed_metadata_attempt_before_backend_error`另得2 passed，实际计数保留且第73次拒绝；72仅为正式MEASURE运行上限，不是新批次授权。corpus项目venv配合双源码`MYPYPATH`及corpus项目配置执行显式strict mypy，四个受影响源码成功，未用`--follow-imports=silent`；七个受影响源码/测试compileall成功。

文档/追踪有限检查：P3与L2严格校验各0 error/0 warning，四份当前文档69条本地链接无断裂，Business/原Knowledge追踪兼容12 passed；新增有限资产及四份文档敏感模式扫描无命中，Git差异检查通过。本轮未修改生产源码或Java，未重复全量Python/Maven、真实Spring全链、索引发布或人工质量评价；这些不得从本轮定向检查推定通过。收口现场只读检查九个本次隔离端口无监听，未停止用户服务。以上修复提交和状态同步均仅本地保存，不push、不部署；下一批真实执行需要独立决策，当前目标仍未全部完成。

<a id="record-14-26"></a>

### 14.26 私有工具有限失败及清理边界修复（2026-09-30）

本轮起始clean HEAD为`b109799c1e87f3af7fa0d609146b20bd839bea27`。静态复核发现MEASURE正式成功路径未核实自有进程实际停止即进入后验和成功写入，Java强制停止后亦缺有界等待。本地提交`13f9458cd69f6f18f588a85582a30f843975ba6f`改为使用已核实并固定的进程对象句柄执行Kill及最多5秒等待；退出检查、停止异常或超时均保守标为清理未知。成功路径必须先通过`Test-OwnedProcessesStopped`；失败路径保留代理可用时的有限计数及实际清理结论，不按裸PID重新查找并终止进程。正式成功result形状及运行预算不变。

B后验拒绝原先只有泛化原因，且消费后的最终JAR读取异常可能绕过有限终态。本地提交`eb7d56171db761ac2ddbdd1fab6620dac670d3a6`保留全部原准入守卫，补充固定allowlist诊断、执行phase、已有receipt和有界双hash请求见证。失败证据明确为`local_unadmitted_diagnostic`，不保存traces、不生成blind pool、不评分，不能当作有效比较。终态落盘失败单独报告已消费及实际计数，不误报preflight失败或声称证据已保存。独立代码复核另以纯mock复现ES client构造异常发生在消费后却无终态；修复将创建及关闭纳入显式有限生命周期，关闭失败亦阻断准入和盲标池。原成功终态结构不变；外来异常文本不持久化。

验证只覆盖私有工具及直接测试。主执行者用§14.25相同项目venv和进程级`PYTHONPATH`执行四份B定向测试，148 passed；随后客户端边界增量修复后，重新执行`pytest tests/evaluation/knowledge/test_rebuild_b_local_runner.py -q`，最终runner 50 passed。两者有重叠，不相加，也不把148项称为客户端修复后的整组重跑。MEASURE实现执行单元在最终源码上执行`pytest tests/uat/test_knowledge_rebuild_measure_harness.py -q`，36 passed、0 skipped；主执行者另核验两项新增清理测试，2 passed、34 deselected。corpus项目venv、双源码`MYPYPATH`及项目配置下，对B comparator/runner显式`mypy --strict`检查成功（2源文件，未隐藏import）；5个受影响Python源码/测试compileall成功，PowerShell AST 0 error，Git差异检查通过。

同一任务内未参与对应实现的执行单元直接核对L2合同、源码和负例并执行定向测试；客户端异常Major修复后复评，范围内无未解决Blocker/Major，未报告待处理Minor。MEASURE定向复评还用纯内存进程mock确认Kill及HasExited异常失败关闭。本轮没有新增设计语义或生产链路修改，不改Java、公共DTO、Prompt、读取/出域权限、索引或alias，也不修改任何历史运行资产。

本轮真实ES、BGE及外部模型调用均0，未读取模型密钥、未启停真实服务、未冻结或复跑新批次。新MEASURE元数据72、模型36、typed search48、query embedding12、rerank24的上限保持不变；预算纠正不是追加运行许可。A仍Not assessed；历史B后验失败无法因新诊断补回缺失见证或改判，MEASURE12题、人工评价及新版完整UAT仍未执行完成。Done=9、In Progress=2（COMPARE/MEASURE）、Blocked=1（RELEASE）保持；后续实际验证必须另作独立执行决策。以上仅本地提交，不push、不部署，不重复宣称§14.18全量Python/Maven或真实集成在本轮通过。

<a id="record-14-27"></a>

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

<a id="record-14-28"></a>

### 14.28 修复后新授权的独立无付费预检（2026-10-02）

维护者明确再次授权使用修复后HEAD的新批次，先无付费预检，通过后新冻B/MEASURE，沿用预算、gold及阈值，不复用失败目录。起始`codex_0915` HEAD `35d108ecfcf4e3563b09b99844e1333a83c4db59`干净；九个隔离端口未占用，既有9200/8908/8909服务未停止。

[B新预检](../../knowledge-corpus-tools/evidence/knowledge-b-startup-20261002-02/README.md)终态`ready / complete`；元数据HTTP30/30、随机临时alias写4/4、baseline/candidate readiness3/1；typed/physical search、模型、embedding、rerank、JWT HTTP、retry/resume均0，proxy violations0。自有进程停止、临时alias移除，四个B端口现场无监听。有限资产本地提交`6e81264d89721afe1c631b544827d07e5e212343`；只读执行单元另核四JSON/README hash与源码预算/清理一致，不重跑服务。该成功仅证明启动，尚未执行B题目、全记录新扫描或质量评价。

[MEASURE新预检](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20261002-01/README.md)从clean `6e81264d`完成五模块版本化clean构建（`-DskipTests`），然后无付费启动在`es_ready`超时；有限终态`startup_preflight_failed`，shell为`knowledge.measure.readiness_timeout`。元数据HTTP48/48，typed search/model/embedding/rerank均0，proxy violations0，`runtimeKeyRead=false`。原始结果`ownedProcessesStopped=false`保持不变，不能补改为true；退出后五个端口无监听且CIM未发现相应目标角色，只作为后续有限观察。服务日志按既有边界删除，没有具体健康响应可补证，不推断唯一根因。

本次MEASURE预检已停止，没有正式manifest、authorization或12题执行；不自动重启、续跑或创建追加批次。B通过自己的预检，且按§6/7的直接依赖不依赖MEASURE，继续独立的新扫描及正式对照，不以MEASURE失败取消其授权，不以B成功替代MEASURE启动证明。两者计数分别保存，生产alias未切换，所有历史运行原字节不改；A仍Not assessed、COMPARE/MEASURE在制、RELEASE受阻。预检证据和工具在正式冻结前完成本地提交，后续冻结后不修改tracked文件。

<a id="record-14-29"></a>

### 14.29 新B正式对照后验拒绝及non-live最小修复（2026-10-02）

[新B有限证据](../../knowledge-corpus-tools/evidence/knowledge-b-reuse-20261002-01/README.md)本地提交`ad8515d816e97b033aead931c0ebb08769dc2c55`，冻结clean HEAD `ebd8dfd2bf8aee40ff764347fb4ed10206044f55`。新全记录只读扫描各64次、各15521记录，两份ID/content hash映射与原构建Git对应blob完全相同；不重建索引或语料向量。正式10题全部调用，typed search44、query embedding10、online rerank22、元数据HTTP30、随机临时alias写4；预扫描128次另账。全部44个搜索POST见证HTTP200；paid/retry/resume均0，未读取模型密钥，生产alias未切换。

终态`not_assessed / runtime_provenance_missing`，phase`postflight`，固定诊断`canonical_requests_mismatch`：两臂各22个POST的规范hash多重集合不一致。自有进程停止、临时alias移除、proxy violations0，结束后四个B端口无监听。无traces、无blind pool，不能计算质量指标，不能把完成调用改为有效比较；原始JSON字节不改、不补证、不复跑。

只读源码及新增测试复现确定性缺陷：Profile冻结时`Map.copyOf(sourceFields)`不保证跨JVM迭代次序，服务将该次序直接写成`_source.includes`数组。本地修复提交`3f642db283458da37847a4d210f9665bc696384e`只让字段投影去重后升序，字段集合、query/filter/vector、分页、授权、解码及Python规范hash守卫不变。修前定向9项中新增2项失败；修后Maven reactor实跑es-query-service108、common-security21全部通过，0失败/0跳过；B comparator/transport/runner/reuse/review直接non-live 183 passed。有限见证没有请求正文，此缺陷与本批差异相符但不证明唯一根因；修复尚未作新真实对照，不能据此改判。

同一任务内未参与修改的只读执行单元核查当前L2、两个Java文件、新B原始JSON/11项hash及三文档状态，定向代码与状态复评未发现未解决Blocker/Major/Minor或S0/S1/S2；没有重跑主执行者测试，不冒充外部人员或效果评价。P3严格校验0 error/0 warning，三文档65条本地链接无断裂，Business/原Knowledge追踪兼容12 passed；有限资产及文档敏感模式扫描无命中，历史资产和公共DTO未修改。

MEASURE保持§14.28的启动失败终态，具体ES健康超时根因未知；其原始清理false不改。A仍Not assessed、COMPARE/MEASURE仍In Progress、RELEASE仍Blocked；所有gold、rubric、阈值、预算及12包DAG不变。本轮未重复全量Python、其他Java模块或真实Spring全链，没有人工评价或发布。后续真实执行必须另作独立决策，修复和有限证据仅本地提交，不push、不部署。

<a id="record-14-30"></a>

### 14.30 MEASURE就绪检查有限诊断补齐（2026-10-02）

起始clean HEAD为`8425e58c2f4bc3115391eca4c5c6311a3053eade`。源码确认已有专用`knowledge-validation`健康组，包含`readinessState,elasticsearch`，未把独立MySQL健康作为本查询前置；旧预检没有健康HTTP响应证据，仍不能确定超时根因。本地提交`0ef99ecf14dfb79889f8d1c3d541bb84e2f3483d`只补齐私有launcher观测：记录固定端点角色、尝试上限/次数、HTTP状态计数、传输失败次数、白名单健康状态及固定终态；最多解析4096字节响应，只接受对象根，不保存URI、响应正文、details或异常文本。HTTP200及自有进程归属准入、轮询/ES预算、快照鲜度及密钥读取门禁均不变，诊断不是新的就绪判断或追加运行授权。

项目venv、进程级双源码`PYTHONPATH`下执行`pytest tests/uat/test_knowledge_rebuild_measure_harness.py tests/uat/test_knowledge_rebuild_measure_fixture.py -q`，最终53 passed、0 skipped；根数组负例曾发现PowerShell展开及宽类型匹配问题，修复后保留持久回归。设置`MYPYPATH=D:/codex/agent-runtime/src;D:/codex/knowledge-corpus-tools/src`后直接测试显式`mypy --strict`通过（1源文件，未隐藏导入）；初次缺少源码路径的检查错误解析旧site-package，不作为最终源码检查结果。compileall通过、PowerShell AST 0 error。未参与修改的同一任务执行单元直接复核L2、源码及负例，未发现未解决Blocker/Major/Minor；主执行者另核关键证据，不冒充外部人员或真实集成评审。

状态同步经同一只读执行单元定向复核，无实质状态问题；P3严格校验0 error/0 warning，三文档65条本地链接无断裂，Business/原Knowledge追踪兼容12 passed，敏感差异扫描无命中、Git差异检查通过。冻结12题fixture SHA-256与原值一致，三个已消费运行目录的Git字节差异为0。本轮真实ES/typed/model/embedding/rerank请求均0，未读取模型密钥、启停服务或另行冻结，没有全量Python/Maven、真实UAT或人工评价。历史B与MEASURE资产字节及终态不变，不能从新诊断补造旧响应或改判。Done=9、In Progress=2、Blocked=1及全部gold、阈值、预算、DAG不变；下一次真实执行须新独立决策，不复用已消费目录。本次只本地提交，不push、不部署。

后续收口复核（同日）：在代码HEAD `03f52734f07a62d3aa282da8d0216cfda8364081`上执行正式入口 `agent-runtime/scripts/run-nonlive-regression.ps1 -PythonExecutable C:/Python312/python.exe`，Transaction host/preflight 14 passed；全量non-live 5639 passed、28 opt-in skipped、0 failed，耗时709.83秒，另有1条LangGraph依赖弃用警告。执行子进程置空模型密钥并关闭live开关，不读取原密钥，不执行真实模型或索引验证。P3当前工作包表及Ready队列的四处旧失败引用同步到§14.28～14.30；这仅修正当前状态入口，不改写历史结论、gold、预算、DAG或工作包状态。该回归包含新版直接测试及历史追踪兼容，不代替真实12题、人工评价或发布；本次未重跑Maven，未新建运行批次或切换alias。

<a id="record-14-31"></a>

### 14.31 启动与清理修复后继续新独立验证（2026-10-03）

维护者确认启动与清理问题已修复，要求继续当前目标。起始clean分支`codex_0915` HEAD `f01540da1b3fced7881821a73703191f84059e3d`；从通过预检时的`2c2d468173101a41206eeb5f7a54bd2e4ed52db2`到此HEAD只增加有限证据，运行源码未再变化，12题fixture SHA-256仍为`04a437d215ab242ea5e69eed95d109f47cf617135778f4d2cf5a13f6cddce26a`。

[MEASURE新无付费预检](../../agent-runtime/tests/uat/knowledge-rebuild-startup-diagnostic-20261003-02/README.md)原始终态`startup_preflight_passed`，元数据9（派生绑定2、Profile6、健康1），typed/model/embedding/rerank及outbound violations均0，login1、runtimeKeyRead=false、ownedProcessesStopped=true。三个指定JSON及绑定源码、配置、服务/依赖JAR的hash与现值一致。同一任务内未参与修复的只读执行单元核查源码、当前L2/UAT、原始证据和PowerShell AST，定向复核无确认Blocker/Major；未重跑旁路诊断的93项测试，不冒充外部人员或质量评价。

修复使用同一venv及严格绑定的基础`pythonw.exe`无控制台启动共享proxy及无推理Runtime，不按conhost名称放行，身份、日志排空和清理失败关闭保留。正式付费Runtime仍由venv `python.exe`执行runner内嵌创建；预检与正式流程不同，启动通过不能证明付费12题成功。正式执行仍需当前clean HEAD的新构建、manifest/authorization和120秒内快照。

[B新无推理预检](../../knowledge-corpus-tools/evidence/knowledge-b-startup-20261003-01/README.md)在起始HEAD执行一次，终态`ready / complete`：元数据30、临时alias写4、两臂readiness3/1，其余typed/physical search、query embedding、rerank、paid、JWT HTTP、retry/resume均0。自有Java停止、临时alias移除、proxy violations0；四个B端口退出后无监听。冻结archive构建使用`-DskipTests`，不作为Maven测试证明；原始四JSON保持不变。

本阶段未读取模型密钥、执行比较题目或12题，未改索引正文、生产alias、权限或历史资产；用户9200/8908/8909服务保留。A仍Not assessed、COMPARE/MEASURE仍In Progress、RELEASE仍Blocked。新授权只承接既定预算/gold/阈值，不复用旧失败批次；当前窗口并发修改条件在正式质量执行前另行核实。仅本地提交，不push；本阶段未重复全量Python/Maven、真实UAT或人工评价。

<a id="record-14-32"></a>

### 14.32 新独立B完整执行与质量边界（2026-10-03）

维护者确认本次B／MEASURE窗口内本人和其他任务不会修改目标索引或切换相关alias。在分支`codex_0915`、HEAD `781690c0a932a50fb898918d699b2c18ac41647d`执行[新B有限对照](../../knowledge-corpus-tools/evidence/knowledge-b-reuse-20261003-01/README.md)，不复用历史失败run。新双臂扫描各64次、各15521记录；正式10题typed44、query embedding10、rerank22、只读元数据30、临时alias写4、paid/retry/resume均0。终态`completed_awaiting_blind_labels / local_verified`，两个自有Java进程停止、两个隔离alias移除、proxy violations0，退出后四个B端口无监听；生产alias未切换，用户基础服务未停止。冻结archive打包使用`-DskipTests`，不记Maven测试通过。

严格离线review核验来源及原始终态，生成未填写的215项盲标模板。机械评分只使用已冻结必要来源和排名：基线/候选宏平均recall@20均0.85，核心及保留题覆盖逐题未退化，未出现评分器检查的keyword/law域顺序混杂；median时延约0.83653/0.83961秒，候选未超过基线110%。主指标没有严格提高，不能据此发布；人工precision及完整B质量仍Not assessed，不代填215项标签或修改gold。A保持Not assessed，不补跑、不追加对照。COMPARE因人工证据仍缺保持In Progress，RELEASE保持Blocked；不存在合格候选时保留旧绑定，后续按§7记录未发布，不伪装为Done。

唯一MEASURE批次选择现行b2索引及意图12/Summary9/minimal-v1组合；不是候选b1的回答证明。须先将本次有限终态/文档收口提交，再从clean HEAD新构建并冻结12题、manifest/authorization及72次正式元数据预算；36模型/48typed/12embedding/24rerank/gold/阈值不变。本节没有12题或真人回答评价的新通过结论。原始result、见证及历史证据保持不变；仅本地提交，不push或部署。

本次运行后定向检查：严格P3校验0 error/0 warning，三份状态文档及README的68条本地链接无断裂，`test_rebuild_b_review.py`与两份历史追踪兼容测试共26 passed（55.41秒）；敏感模式扫描和Git差异检查通过。未改源码或历史资产、未机械重复全量Python/Maven。另一未参与执行的只读单元核查原始证据、旧Git来源10文件、两臂请求/模型/排名见证及新状态diff，定向复核无确认Blocker/Major；机械指标和空模板均与严格离线入口输出相等。该复核不冒充外部人员或真人相关性/回答评价。

<a id="record-14-33"></a>

### 14.33 新独立MEASURE有限失败终态（2026-10-03）

§14.32的B证据及状态已本地提交为`0e9e47345def6db376f4b2e9af481d445d8d707c`。从该clean HEAD新构建并冻结`knowledge-rebuild-measure-20261003-01`，reference为`UAT_02:KNOWLEDGE_REBUILD_MEASURE_20261003_01`，manifest SHA-256为`47dee2d00fdd980fb0280c269b5f390d4ba3febc9bfc7bdcd4dcf69190d5fcd8`。真实绑定为现行b2、deepseek-flash、意图12/Summary9/minimal-v1，沿用12题/gold/阈值及36模型/48typed/12embedding/24rerank/72正式元数据上限。维护者已确认本次窗口无其他相关索引/alias修改；不复用旧失败目录或预算。

版本化launcher仅执行一次。启动、身份及新鲜快照前检通过后开始模型调用；完成001～004，第005题在Summary传输完成后触发`case_technical_failure`，exit code=1。原始failure为`failed_consumed`、completedCases=4，按执行完整性口径为`invalid_run`；006～012未执行，没有measurement或成功result。本次实际模型13、typed8、query embedding4、rerank4；58行journal中的29个started都有terminal completed，但传输完成不等于输出/引用/公开结果合同通过。

第001/002题HTTP200 success，必要来源进入top20、分别3/1条引用；这不是人工回答通过。003题HTTP200 no_result且small_2022未进入top20，与冻结success不同；004题HTTP422 unsupported、`core.no_supported_capability_candidate`，与冻结no_result不同。005题未保留公开响应或errorCode，不能从最后一次Summary完成推定具体解码、引用或回传根因，不通过重跑补证。四条公开加工结果仅在受控本地目录供人评，不提交引文正文或原始模型/完整服务响应。

原始代理见证为live_proxy：正式ES元数据27、typed8、health1、alias12、indexDefinition10、proxyViolations0；共10次题前/后身份核查，每次2个HTTP。freeze绑定2和全快照前检预算67分账；失败后没有完整postflight或快照postflight，不宣称全记录前后证明闭合。ownedProcessesStopped=true、cleanupIssues为空，退出后五个隔离端口无监听；未停止用户9200/8908/8909，未切生产alias。运行后27项冻结asset hash匹配、无tracked源码改动；自动retry/resume、Business及旧answer均0。

有限证据与原始hash见[本次交接](../../agent-runtime/tests/uat/knowledge-rebuild-measure-20261003-01/README.md)。原始资产保持append-only，本次只追加README及当前状态同步，不补造成功终态或人工评分。功能/安全完整UAT、召回和回答整批评价均未完成；B主指标未改善，RELEASE继续Blocked、现行b2保持。本批停止，不使用剩余额度继续调用；后续可先做无付费诊断，真实复测须新的独立决定，不自动准备下一批。

本次运行后已有定向non-live：`test_knowledge_rebuild_measure_fixture.py`与`test_knowledge_rebuild_measure_harness.py`共95 passed（69.22秒）。构建使用skipTests，不记为Java测试；源码未改，不机械重复全量回归。当前引用同时纠正UAT版本和§12旧比较状态的元数据漂移，不改变设计、DAG、用例、gold、阈值或预算。

当前文档严格校验0 error/0 warning，三份状态文档及本次README共70条本地链接无断裂，有限JSON/JSONL按真实ledger格式配对核验、敏感模式及Git差异检查通过。另一未参与执行或编辑的只读单元独立核对原始8文件hash、freeze与fixture、预算/消费/停机源码及v3.27差异，无确认Blocker/Major；它未重跑真实调用或测试，不冒充外部人员、完整代码评审、人工回答质量或发布验收。本节的hash与传输证据不能补足第005题响应及整批postflight缺口。

<a id="record-14-34"></a>

### 14.34 MEASURE失败响应的有限观测修复（2026-10-03）

起始clean HEAD为`fa6a9f190f923ba6accb9346270d7b400ccf5053`。只读核实确认私有runner在公共响应校验失败时直接停止，未保留该题的HTTP状态或有限公开错误分类。仅修复当前runner和直接测试：新失败记录可附`failedCase`，保存冻结case身份、有限HTTP状态、JSON形态、白名单公开状态/错误码和关联/能力匹配布尔值；未知文本仅记固定unknown，不保存问句、回答、引文、原始响应、异常信息或凭据。原失败终态、消费及停止逻辑不变，launcher仍以失败资产是否存在判断，不增加重试、续跑或真实运行授权。

六种fake反例覆盖技术失败、异常字段、非法JSON、非对象响应、关联不匹配与连接失败，均在首题停止；真实HTTP由测试守卫禁止。MEASURE fixture/harness及Summary9 contract/stage四文件共124 passed（71.18秒）；类型注解修正后两文件strict mypy通过、compileall通过，新增六反例复跑6 passed。这些计数有重叠，不相加。工具修复只对后续另获授权的新冻结生效，不能恢复或补写§14.33第005题响应，不能证明实际Summary、引用或回传根因已修复。

实现本地提交`587a61eb847c0001071d4ef537f298c0ff02350c`。作者自审后，未参与修改的只读执行单元定向检查源码、launcher消费者、原始终态及三文档状态，未发现确认缺陷；另独立执行六新增反例和两项消费/零发送测试，8 passed（1.89秒），与上述回归重叠。其禁用插件自动加载的命令有一条asyncio_mode配置未识别警告，不影响这八项使用asyncio.run的测试；未独立重跑124项、mypy或compileall，不称完整设计/代码评审、真人评价或真实UAT。主执行者严格P3校验0 error/0 warning、三文档69条本地链接通过；原运行8份文件与起始Git字节一致，27项冻结资产中26项当前字节不变，受本轮修改的runner按原冻结HEAD及仓库checkout换行恢复并匹配原hash。没有把当前新工具伪称为旧运行使用的工具。

本轮没有模型、ES、embedding、rerank或真实服务操作，不创建新批次，不切alias、不发布、不push；历史原始文件和绑定的冻结Git版本保持不变。COMPARE/MEASURE仍In Progress、RELEASE仍Blocked，现行b2保持；缺少人评、有效完整测量与候选主指标改善，整体目标未完成。后续决策应分别处理已有B盲标材料、已消费的无效MEASURE及是否继续质量实验，不自动复用余额或追加候选。

<a id="record-14-35"></a>

### 14.35 已封存来源损失定位及部分人评准备（2026-10-03）

起始clean HEAD为`af9ac4a75a6a618c0da89912e1ca6fd40e10d899`。[局部复核材料](../../knowledge-corpus-tools/evidence/knowledge-rebuild-review-20261003-01/README.md)只离线读取§14.32的10题traces、两臂完整身份清单与§14.33的冻结必要来源。两臂各16个题—必要来源组合，均缺2项：KM-003的small_2022、KM-012的lease_real在两臂扫描中具有精确document/chunk/正文hash，但未进入初始keyword/vector前20；没有必要来源先进入初始候选再因融合、重排或final20截断丢失。该定位不是新测量、人工precision或MEASURE第003题搜索轨迹重建；尚不能区分Profile过滤/权限、查询匹配与原路径排名/候选窗口，不能直接据此调整topK、Prompt或向量。

已在既有受控本地review目录准备四题人工核对说明，配合原公开加工结果供维护者阅读，不提交引文正文。执行者对001/002提出四项判据的初步建议，正式确认仍由维护者完成；003未返回所需期限，004未编造内容但公开状态不符合冻结no_result，不计用例通过。未填写正式rubric或215项B盲标；005具体技术根因仍不可验证，006～012未执行。局部人评即使完成也不能使整批invalid_run变成完整12题验收通过。

本轮未读取模型密钥，没有网络、ES、模型、embedding、rerank或服务操作，不新增/续跑批次，不修改gold、阈值、预算、历史原始资产或12包DAG。COMPARE/MEASURE仍In Progress、RELEASE仍Blocked，候选主指标未改善、现行b2保持，整体目标未完成；本次只本地提交，不push、不部署。

<a id="record-14-36"></a>

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

<a id="record-14-37"></a>

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

<a id="record-14-38"></a>

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

<a id="record-14-39"></a>

### 14.39 验证可靠性与检索诊断的定向设计（2026-10-03）

起始clean `codex_0915` HEAD为`62532b5bf1cb93b0811260da1873313baa7103f1`。维护者同意此前推荐内容继续推进：先解决正式验证路径的可复现性及检索损失定位，再比较是否需要在线表达/有限补检；本轮只完成六份文档增量，不实施代码，不启动新真实批次。

L1_01 v3.7 §4.7/KQ-AD-029/030选择保留当前LangGraph顶层路由及固定Knowledge pipeline；内部拆图不是召回优化的自动前提。流程L2 v3.7 §20定义同正式runner的无付费演练、单一预算推导、失败attempt记账、有限取证及owned清理。检索L2 v3.13 §9.9定义原文/过滤/初召回/融合/重排/Evidence的损失归属及unknown边界；grep只作离线来源定位，不进入Runtime。受限查询表达、最多一次补检与LangGraph内部分步仅为后续比较项；Deep Agents、父单元补取和图谱不进入当前主线。没有改变现原问、域、次数、公共DTO、索引、读取/出域或引用合同。

UAT_02 v3.34 §5.6/6.4区分无付费演练与真实验收、候选采用与不采用：明确必要正向条件不满足时，允许独立作“不采用”的决策，不为否决继续强制补齐不会改变决定的标签；未知precision/usefulness仍未评。原正向阈值、gold、分母和历史结果不改；不自动关闭整个COMPARE、A或RELEASE。

新增`WP-KVERIFY-DRYRUN-01`和`WP-KRETRIEVAL-DIAGNOSE-01`，分别只直接依赖已Done的COMPOSE及RETRIEVAL，14包/14直接边无环。两包技术Ready、未实施，不互相阻塞，不增加编号Gate；原9 Done、COMPARE/MEASURE In Progress及RELEASE Blocked保持。后续真实调用必须重新独立决定和冻结，不能使用已消费批次或本节恢复历史预算。

两轮作者内审分别检查安全/执行与召回归因、追踪/直接依赖及状态保真；strict初检发现新追踪表头/编号定义不完整、Ready声明的字面兼容要求，已补齐实际映射，未修改校验器或降低检查。一个未参与起草的独立只读执行单元直接核查REQ、最小plan/stage、正式runner/ledger/launcher及原始小型终态/指标，发现一项S2：新增六列追踪行误入三列责任表。已移回正确主矩阵，复核本次六份增量符合，未处理S0/S1/S2均0。不是外部人工UAT，也不是全套设计/代码重新审查。

实际检查：L1架构strict、两份L2 strict及P3 strict均0错误/0警告；六文档106条本地链接存在，fence完整；14包/14边无环且Ready前置均Done；新增行敏感模式扫描和`git diff --check`通过。MEASURE manifest/cases/failure及B comparison-result四项SHA-256与原README一致。只改本轮六份当前Markdown，代码/测试/配置/历史资产未改；模型、ES、embedding、rerank及服务操作均0。未执行Python/Maven功能回归或真实UAT，因为未改实现；文档检查不证明新包实施或召回提升。本轮只本地提交，不push或部署。

下一步优先实施`WP-KVERIFY-DRYRUN-01`；纯离线`WP-KRETRIEVAL-DIAGNOSE-01`可独立推进。诊断完成后再选择最小检索修正，不立即增加框架、循环、topK或付费候选。整体剩余实施/验收目标仍未完成。

<a id="record-14-40"></a>

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

<a id="record-14-41"></a>

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

<a id="record-14-42"></a>

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

<a id="record-14-43"></a>

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

<a id="record-14-44"></a>

### 14.44 原005解释路径的正式runner合成补证（2026-10-04）

从clean `codex_0915` HEAD `b1907ba137d9d4b1d34d1d45390fbf08518a9a4e`只读复核。独立审查确认旧005的模型transport已完成不等于引用/回答校验通过；旧failure未记录具体公开错误，根因仍unknown。现runner已有白名单失败取证，无证据支持更改生产或猜测旧失败原因；但原12题合成演练均为lookup，不能证明005 explanation已经过正式runner＋生产ASGI。

仅在[演练测试](../../agent-runtime/tests/uat/test_knowledge_rebuild_dryrun.py)新增005原问的explanation正向和非法quote反例，本地提交`e91e3a64996d556e3063f87259cb07f6bf693fd4`。原公开问题只读复用；来源、正文/hash及验证义务明确为synthetic，不沿用software gold，不评价真实召回或回答充分性。正常路径实际经过当前root、意图12、Summary9、typed decoder、Evidence/引用validator、账本、公开投影及清理。负向仅替换quote，保留合法非空claim与存在的ref，确实触发生产连续子串校验；005记录有限`knowledge.summary_failure/downstream`、停止006～012、无成功终态、无标记泄漏并清理所有owned内存client。两项均不可作为真实UAT或旧005根因证明。

本轮实际验证（`agent-runtime`，临时`PYTHONPATH/MYPYPATH=src;../knowledge-corpus-tools/src`）：

- `python -m pytest tests/uat/test_knowledge_rebuild_dryrun.py -k 'original_005 or 005_explanation' -q`：最终2 passed / 27 deselected，2.01秒。
- `python -m pytest tests/uat/test_knowledge_rebuild_dryrun.py tests/uat/test_knowledge_rebuild_measure_harness.py tests/integration/knowledge/test_minimal_current_root.py -q`：154 passed，96.45秒。独立审查者另运行新增及直接相关no-network反例：21 passed / 107 deselected，9.93秒，复评无确认缺陷。
- `python -m mypy src`：153 source files通过；`python -m mypy --follow-imports=silent tests/uat/test_knowledge_rebuild_dryrun.py`：该测试文件strict检查通过；该文件`compileall -q`通过。扩大为`mypy src tests/uat/test_knowledge_rebuild_dryrun.py`仍因未修改的导入辅助文件`test_minimal_current_root.py`报27项既有类型错误，未声称此扩大检查通过，也未以放宽仓库配置或无关改写掩盖。

作者自查及独立只读复评完成；没有修改生产代码、Java、任务、运行配置、固定题/gold/阈值或历史资产。本轮没有真实模型/ES/BGE/Business调用、服务操作或新授权消费；临时合成结果不作为正式MEASURE资产提交。固定fixture及原B result、MEASURE manifest/cases/failure的SHA-256与起始值一致，其余历史无Git差异。未重复全量Python、Maven、真实Spring E2E或付费UAT，原证明范围保持。P3 strict为0错误/0警告，三份文档81条本地链接、fence、有限秘密模式和Git差异检查通过。独立审查直接核对旧attempts/failure、当前测试及三文档，增量状态同步结论符合，无确认S0/S1/S2；不是全部设计或上线重新批准。

DRYRUN仍仅non-live范围Done，14包/14边及11 Done、2 In Progress、1 Blocked不变。COMPARE未完成，MEASURE仍invalid_run且005旧根因未知，RELEASE不具备准入。下一步需要新的独立精确测量决策及冻结、有效完整终态和维护者人工评价；不复用旧授权、不补题、不自行追加真实批次，也不以更多合成测试冒充整体目标完成。

<a id="record-14-45"></a>

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

<a id="record-14-46"></a>

### 14.46 文号全检索链的私有草案及non-live验证（2026-10-04）

起始clean `codex_0915` HEAD `0395537d59dba225575c8bd7fa9f800217c2e5f9`。依据维护者对§9.1推荐路线的选择，新增[私有协议与重放入口](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_comparison.py)及[直接测试](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_comparison.py)。本切片落实DR-KRET-204/401/403的独立同池、分阶段、有界对照准备，不新建工作包、Gate或公共合同；不是第三项已获授权A/B，不替代A或MEASURE。

- 草案硬绑定现有12题fixture SHA-256 `04a437d215ab242ea5e69eed95d109f47cf617135778f4d2cf5a13f6cddce26a`，从中选择全部10个召回评价题及11个域单元；原问题、域、gold和阈值不改。当前HEAD与旧helper源HEAD之间的Java主源码、契约、依赖和启动配置范围仅允许`DocumentNumberQuery.java`差异；本地`--preview`实际核查通过。没有编译或启动新服务，源码核查不代表实际部署核查。
- 两臂使用同一b2完整竞争池的目标范围、同问题/计划和共享query vector；允许policy keyword因helper改变，vector和law路径必须一致。原文、来源元数据、snapshot/readPolicy及共用候选评分漂移拒绝，RRF/域内重排/final20直接调用或重放核对当前生产组件，不另造在线算法。
- 所有演练端口仅接受内存数据，没有HTTP/推理/进程启动回调。假调用上限为typed44、共享embedding10、rerank22；失败计attempt、停止并保留有限completed/unexecuted，session不能resume。取消后Stage child已收回。输出只含case/身份/hash/阶段排序及有限数值，不含正文、向量、令牌；演练计分固定`Not assessed`，precision/真实时延为null，不能成为采用或发布证明。
- CLI只提供`--preview`，状态`non_live_only`、`realExecutionAllowed=false`、`runId=null`；不创建manifest/authorization/consumed或正式result。旧B比较器、四题词法探针、冻结fixture及历史目录不修改。

真实准备仍未完成：新的完整库存前后核验、当前实际Profile/读取/出域策略与本地模型快照、物理请求见证、额外元数据/全库读取/启动健康检查及预热的**完整精确预算**、自有服务与代理清理、排他窗口和独立运行授权。预览不继承fixture或旧运行的全库fingerprint。后续应先补齐无付费执行器及其fake反例，汇总完整预算和冻结材料供一次确认；没有精确授权不执行真实读取或推理。MEASURE仍单独治理，不在本准备切片中读取密钥。

本轮实际验证（`agent-runtime`，源码路径临时注入并恢复，没有安装或修改依赖）：

- 新增直接fake单测39 passed；独立审查者另实跑同39项，0.38秒。
- `python -m pytest tests/evaluation/knowledge/test_rebuild_document_number_comparison.py tests/evaluation/knowledge/test_rebuild_b_comparator.py tests/evaluation/knowledge/test_rebuild_lexical_probe.py tests/unit/knowledge/retrieval/test_minimal_stage.py tests/unit/knowledge/retrieval/test_minimal_ranking.py tests/unit/knowledge/retrieval/test_fusion.py tests/unit/knowledge/test_minimal_retrieval_plan.py -q`：296 passed，6.54秒，使用临时`PYTHONPATH=src;../knowledge-corpus-tools/src`。
- 临时`MYPYPATH=src`下 `python -m mypy --strict src tests/evaluation/knowledge/rebuild_document_number_comparison.py`：154 source files通过；两份新增文件`compileall -q`通过。初次默认安装包定位缺模块，继而发现复用旧B工具类型会拖入不相关语料解析依赖；新协议改用隔离私有记录，最终无放宽检查、无新增依赖。不声称初次命令通过。
- 本地源码`python -m tests.evaluation.knowledge.rebuild_document_number_comparison --preview`通过，只输出草案/未满足前置及计数推导，不执行真实freeze。

独立执行单元未参与实现，直接核对设计、源码差异和全部反例，代码增量复评无确认Blocker/Major；随后独立核查三文档、fixture hash、包/边状态及原始验证输出，文档增量定向复核符合，未发现需修改的实质问题。仅限私有准备增量，不证明新真实批次已具备执行条件。P3严格校验0 errors/0 warnings，三文档86条本地链接及代码围栏检查通过；本轮核查的fixture、旧B result和MEASURE failure哈希保持。P3/UAT/索引状态同步和Git收口只本地进行，不push。

14包/14边及11 Done、2 In Progress、1 Blocked保持。A仍Not assessed，B仍不采用，MEASURE仍原invalid_run且不补跑，RELEASE仍Blocked；37风险、12资料用例及12题真实评价均不由本轮fake关闭。没有真实模型、ES、BGE、Business、服务启停或索引/alias写入。

<a id="record-14-47"></a>

### 14.47 新快照及发送边界的独立私有准备（2026-10-04）

起始clean `codex_0915` HEAD `f397efea525fde778d120708c656c946fa2988ad`，承接§14.46同b2完整竞争池、十题/十一域单元、旧/当前helper唯一变量的准备范围。新增四份私有工具/测试，不修改生产Java/Python、运行配置、gold、历史工具或运行资产：

| 缺口 | 本轮实现 | 证明边界 |
|---|---|---|
| 旧scanner输入旧fingerprint，不能取得本次新库存 | [新快照读取器](../../knowledge-corpus-tools/src/knowledge_corpus_tools/document_number_snapshot_v1.py)及[测试](../../knowledge-corpus-tools/tests/test_document_number_snapshot_v1.py)：caller-owned client，一次definition＋ceil(N/250)次全记录读取，严格身份/mapping/写保护/顺序/数量/1024向量核验，计算新fingerprint，只返回ID/正文hash | 全竞争池包含law及无分类记录；不继承旧fingerprint，不读取实际ES。固定httpx版本的client门禁排除auth、cookies、hooks、mounts、未知transport及重试，异常不保留原始响应或异常链 |
| 旧计数/成功回执不能证明失败attempt已消耗 | [发送边界接缝](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_transport.py)及[测试](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_transport.py)：委托现有production adapters，先reserve后send，typed及物理两个HTTP跳分别计数，失败/取消不返还、禁止重复，终态后拒绝新发送；原始bytes不重写 | ledger目前仅内存，未成为正式append-only运行journal；caller/delegate真实装配和生命周期尚未完成。JSON/HTTP/正文上限拒绝与有限receipt有fake反例，不能据此称真实协议有效 |
| 格式合法的文号不等于冻结helper实际输出 | physical gate继续检查scope/DSL，并要求case/arm各域的独立期望keyword规范hash全等；添加、移除或错误机关信号均在发送前拒绝 | 本轮期望hash是合成fixture；未来真实hash必须由冻结Java源码/配置的离线实际投影产生并证明来源，不可从捕获请求反算期望。vector严格保持共享向量，law禁止文号信号 |

预算工具只给出条件预测，不授予操作权限：**若**目标是同一物理索引、N=15521且按拟定启动形状，则独立fresh capture为67次ES，冻结前后扫描/元数据/物理检索为190次ES，合计ES上限257、所有HTTP跳上限378（含typed44、query embedding10、rerank22、预热rerank1、Java健康40、BGE健康4）。N只是声明输入，尚未现场核实；这些数字不是本次实际计数或已批准冻结预算，不替代旧B/MEASURE预算。实际索引/alias/Profile/策略/模型身份、Java投影、启动形状和非HTTP快照操作须在下一切片完成后统一冻结确认，不能将未列出的调用藏入这些行。

下一步仍是完成自有Java/proxy/client的真实装配协议、有限元数据与模型快照、停止/append-only journal/清理及其fake验证，再汇总一次精确运行材料；当前入口无真实execute授权资产，不启动服务、不连接ES/BGE、不读取模型密钥。此准备不是第三项A/B，不替代MEASURE、人工评价或RELEASE。14包/14边、11 Done/2 In Progress/1 Blocked、A未评/B不采用/MEASURE原invalid_run均不变。

独立初审发现两项中等问题：未绑定文号实际投影、caller client多轮认证可产生隐藏发送；首次复评又实证显式transport proxy可以绕过loopback要求。分别最小修复并增加零发送反例，第二次复评直接核对源码与三份文档diff，并独立执行6项client反例，全部确认问题关闭。自审另补有限异常无原始context、响应大小/媒体及失败后停新发送；不以自审冒充独立评审。最终仅此私有准备增量无未处理Blocker/Major，不判断全目标或真实运行就绪。

本轮实际验证（各项目venv；临时源码路径只作用于执行子进程，没有安装或修改依赖）：

- `agent-runtime`：`python -m pytest tests/evaluation/knowledge/test_rebuild_document_number_transport.py tests/evaluation/knowledge/test_rebuild_document_number_comparison.py tests/evaluation/knowledge/test_rebuild_b_local_transport.py tests/evaluation/knowledge/test_rebuild_lexical_probe.py tests/unit/knowledge/retrieval/test_minimal_stage.py tests/unit/knowledge/retrieval/test_http.py tests/unit/knowledge/retrieval/test_bge_rerank_context.py tests/contract/knowledge/test_es_adapter.py tests/contract/knowledge/test_bge_embedding.py tests/contract/knowledge/test_bge_rerank.py -o addopts='' -q`：**292 passed，11.16秒**，包括实际production adapters＋Stage的十题双臂合成send边界集成，不是实际Java服务。
- `knowledge-corpus-tools`：`python -m pytest tests/test_document_number_snapshot_v1.py tests/test_b_id_mapping_v1.py tests/test_rechunk_candidate_v1.py -o addopts='' -q`：**146 passed，4.10秒**。首次修复回归中一个旧fake缺JSON媒体头、一个Auth测试注解与httpx类型不符；补正确fixture/header和Generator类型后通过，没有删断言或放宽守卫。
- Agent `python -m mypy --strict src tests/evaluation/knowledge/rebuild_document_number_transport.py`：154 source files通过；语料工具 `python -m mypy --strict src/knowledge_corpus_tools/document_number_snapshot_v1.py tests/test_document_number_snapshot_v1.py`：2 source files通过；四新增文件`compileall -q`通过。
- P3 strict：0 errors/0 warnings；三文档链接/fence/版本、14包/14边及状态保全检查、历史fixture与封存B/MEASURE关键hash、范围和有限敏感扫描、工作树与暂存diff检查通过。未执行全量Python/Maven、真实索引读取、Java离线投影、服务或UAT，这些不由上述fake替代。

本轮只本地提交，不push/部署。真实模型、ES、BGE、Business、服务启停及索引/alias写入均0；没有创建新run/授权/consumed/result。现行绑定和历史证明范围不变，完整目标仍未完成。

<a id="record-14-48"></a>

### 14.48 实际Java离线投影及构建一致性（2026-10-04）

起始clean `codex_0915` HEAD `260a709fb3a594f3b9029c177e08e766be3c91ce`。新增[私有离线投影工具](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_projection.py)、[同package Java inspector](../../agent-runtime/tests/evaluation/knowledge/DocumentNumberProjection.java)和[直接测试](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_projection.py)，补齐§14.47的期望keyword hash来源；不修改生产源码、Profile、gold或历史探针，也不新建运行授权资产。

两臂取同一Git archive，旧臂仅替换固定旧提交的`DocumentNumberQuery.java`。在独立临时目录中用同一Java25、Maven离线构建，`-DskipTests`明确不作为Maven测试通过；编译时间戳固定为源提交时间`1791082199`。Maven直接由已核验的Java运行classworlds launcher，不经过Windows cmd再启动Java；只继承有限工具环境，不继承模型密钥或Java/Maven注入选项。解包先拒绝设备名、尾点/空格、控制字符、路径穿越、链接及Windows大小写重复，再进行排他写入；临时构建目录结束后删除，仓库已有target不触碰。

Inspector仅从各自JAR加载冻结live YAML、实际`KnowledgeSearchService.buildSearchBody`和所带Jackson，分别绑定policy与law Profile，不创建RestClient、Spring上下文或服务。问题从固定fixture派生，通过有界stdin输入，stdout在子进程返回后校验大小；Python只核查case/域/请求形状并计算保留数字字面值的规范hash，不实现文号正则或重新生成DSL。YAML中的索引占位符没有从环境补值，**此证明不涵盖完整启动校验、部署实例或当前索引**。

最终实际离线执行通过（源HEAD同起始HEAD；工具为本轮新增内容，不视为真实批次冻结）：

| 检查 | 有限结果 |
|---|---|
| 投影范围 | 两臂各11项keyword，即10题/11域单元，总22项；原问题、case顺序、gold与阈值保持 |
| 构建唯一变量 | 非helper class fingerprint `e6b72c120942f503a862c8c2ad15bdbf2325bcaaa7d53e9db310b043707d1690`、依赖JAR fingerprint `535871781868d0a400eaa538aaae57af7b9cdd2448b25f10349bcd40e479a2d2`以及配置字节两臂全等，helper class不同 |
| 请求差异 | 规范hash仅003/policy与007/policy不同；其余9个域单元相同，所有law相同。原始Map序列化顺序可以不同，不能用raw hash差异误判语义改变 |
| 有限证明绑定 | source archive SHA `4d9b9aea17b464d6d15afd04ffe0b7df8b86f489cdaed694b449a0e48a9dd78f`；最终工具SHA `1f69f41dd48e690551fde8207af66b5ffb82c58ea47b30864db93d71810d5c1a`；22行及构建proof规范汇总SHA `591975fadb2a59c5effa43463c91438621200734dec8900beb24323e663d8d24` |
| 证明边界 | 只确认实际Java投影来源及单变量构建一致性，不判断召回、排序、答案或发布质量；真实发送时仍须绑定新的冻结HEAD和实际实例 |

首次实际构建触发`offline_pair_drift`，未保存分项hash，不能断言其唯一原因；两臂固定构建时间戳后严格相同比对通过，没有放宽指纹或内容要求。独立评审确认一个Windows设备/别名解包缺口，修复并添加写入前拒绝反例；初始backslash测试也揭示ZIP读取会规范化名称，现核对`orig_filename`，不修改断言来掩盖问题。最终定向独立代码复评无未关闭实质问题；独立审查者另运行49项fake通过，未重复实际Java构建。

本轮实际验证：

- `agent-runtime`使用§14.47列明的292项集合，在其命令文件列表前追加`tests/evaluation/knowledge/test_rebuild_document_number_projection.py`，仍用`-o addopts='' -q`：**341 passed，13.94秒**；直接新文件49项包含两域/身份/字节/环境/异常/解包反例。
- 临时源码类型路径下`python -m mypy --strict src tests/evaluation/knowledge/rebuild_document_number_projection.py`：154 source files通过；新Python工具及测试`compileall -q`通过。
- `python -B -m tests.evaluation.knowledge.rebuild_document_number_projection --offline-project`：实际双臂离线编译及22投影通过；Windows门禁修复后再次完整执行通过，临时目录清理。该构建跳过测试，不等于Maven单测或Spring/typed集成验证。
- 未参与起草的只读执行单元直接核对三份文档差异、当前源码和原始有限验证输出，定向文档复评符合，无已确认实质缺陷；这不是外部人工评价或整体验收。P3 strict为0错误/0警告，三文档93条本地链接及fence、版本、14包/14边及状态保全通过；四项历史关键hash与起始Git字节一致，有限凭据扫描和Git差异检查通过。未执行全量Python/Maven、真实typed/ES/BGE/模型或UAT。

下一步补齐自有Java/proxy/client运行装配、正式append-only journal与停止/清理、模型/策略和库存快照及完整精确冻结材料。§14.47的257/378仍只是条件预测，未获得真实执行额度；本轮无模型密钥读取、真实API调用、服务启停或索引/alias操作，不创建run/authorization/consumed/result。14包/14边、11 Done/2 In Progress/1 Blocked、A未评/B不采用/旧MEASURE invalid_run与人工结论不变；完整目标未完成，只做本地Git收口，不push。

<a id="record-14-49"></a>

### 14.49 有限attempt日志与失败持久化接缝（2026-10-04）

起始clean `codex_0915` HEAD `c9e685b354e2d33fce65e7199021a0ad19e1cbf8`。新增[私有日志工具](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_journal.py)及[直接测试](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_journal.py)，为既有发送计数器增加可选checkpoint；无实际执行入口，不修改生产代码、配置、题目或历史资产。

同一ledger顺序锁内先计attempt、排他写入有限checkpoint并flush/fsync，成功后才允许delegate发送。写入失败不返还额度、停止新发送；回执失败保留pending，不假记completed。目录及文件必须新建，旧文件、半行及漂移日志不能续写；日志仅保存绑定hash、有限类别、计数和状态，不接收正文、向量、凭据或原始异常。文件身份、大小及有限完整hash核验已有漂移反例；另设单行、行数及总量硬上限，未单独执行其触边测试。

`JournalBinding`只表达caller提供的身份；它不验证或授予运行授权。全部测试使用`synthetic_non_live`及pytest临时目录，没有创建正式run、authorization、consumed或result。`seal_cleanup`先停止新发送、要求在途回执完成，保存**caller自报**清理字段并明确`cleanupVerifiedByJournal=false`；其成功不证明Java/proxy/client/端口已经释放，不是UAT终态或发布许可。实际资源归属核查和清理仍由后续owned executor承担。

独立初审发现创建后fstat失败遗漏句柄关闭、body与关闭双失败可在traceback展示原异常两项问题；已最小修复并新增3个反例，保留失败目录、不重开或覆盖。复评直接核对源码和测试，确认两项关闭，无阻止本次non-live准备收口的新问题。异常链抑制只指格式化traceback不展示原异常，不宣称所有场景的`__context__`都为空；此评审不是实际运行或整体目标验收。

实际验证：直接journal/transport/projection **128 passed，1.29秒**，独立复评另实跑同集合128 passed、1.38秒；§14.48的341项集合追加日志测试并禁止pytest缓存后，**374 passed，13.59秒**；临时双源码类型路径下`python -m mypy --strict src tests/evaluation/knowledge/rebuild_document_number_journal.py tests/evaluation/knowledge/rebuild_document_number_transport.py`为155源文件通过，三份直接Python文件compileall通过。没有重复实际Java离线编译、全量Python/Maven或真实UAT。

独立文档复评发现硬上限的反例表述超出实际测试，已修正并披露未执行触边；修后定向复评符合，无其他未处理问题。P3严格校验0错误/0警告，三文档95条本地链接及围栏通过；四项历史关键hash保持，有限凭据扫描无匹配，目标差异和暂存检查通过。校验及评审只覆盖本增量，不证明真实资源、当前部署或质量达标。

下一步仍须补齐自有Java/proxy/client装配与实际清理证明、现场模型/策略和新库存快照、完整精确预算及独立授权。当前writer只是可复用的持久化接缝，未与真实执行生命周期装配；§14.47的257/378仍仅条件预测。14包/14边、11 Done/2 In Progress/1 Blocked、A未评/B不采用/旧MEASURE invalid_run及人工结论不变，不由新增fake或日志转为Done。本轮只本地提交，不push。

<a id="record-14-50"></a>

### 14.50 同产物lease、自有资源与生产Stage装配（2026-10-04）

起始clean `codex_0915` HEAD `130e27addcceae9b739a83d16fdff0b368ac4f9e`。按§9.1已选择的私有non-live准备范围，扩展[离线投影工具](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_projection.py)，新增[owned资源工具](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_owned.py)和[生产Stage装配](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_stage.py)；没有修改生产源码、配置、gold、阈值或历史资产，也没有建立实际run/authorization/consumed/result。

- 同一次构建和投影的JAR通过lease保持有效，运行前核验产物hash及冻结配置；资源未证明释放则保留唯一临时构建目录，禁止删除正在使用的JAR。兼容离线preview仍在退出成功后才报告目录已删除，本轮未重新执行真实Maven构建。
- owned工具立即登记实际Popen句柄、caller自有代理和HTTP client；清理只停止登记的句柄，不以端口PID当作关闭授权。部分启动失败、监听者漂移、取消、客户端/代理/端口清理失败和journal写失败均有合成反例；这些测试不能证明当前实际服务已清理。
- 新装配直接使用正式ES/BGE Adapter和`MinimalKnowledgeRetrievalStage`，不是调用synthetic `ReplaySession`。固定10题/11域、双臂交替顺序和每题一次共享embedding，捕获keyword/vector/RRF/rerank/final20；保留严格DTO、原文hash、域授权及单变量校验。有限trace不保存正文、向量、JWT或原始异常，质量仍`Not assessed`。Stage时延范围明确不包含共享embedding，尚非真实时延比较证据。

独立预审指出标准Base64密钥与Java解码不一致、临时目录删除双失败可泄露异常链两项问题，已最小修复。新工具接收48字节随机材料并标准Base64编码，同一原始材料供后续JWT签名；不读取模型密钥。独立纯fake双失败注入确认traceback不展示主体或删除异常，owned直接测试17 passed、0.67秒。Stage复评另外确认HTTP200非法DTO后仍可能继续未发送peer、共享embedding缺少总耗时截止；已在非成功path DTO后立即停止ledger，复用生产`_bounded`的3秒绝对deadline及迟到检查，新增三项反例。作者自查另补共享embedding阶段的signal取消监听，不以自审冒充独立评审。

本轮相关回归`python -B -m pytest`（`-o addopts='' -q -p no:cacheprovider`）：六份`test_rebuild_document_number_{stage,owned,projection,comparison,transport,journal}.py`及minimal_stage/minimal_ranking/fusion/http/bge_rerank_context五份unit，最终**308 passed，12.60秒**；ES/BGE三份契约及旧b_local_transport/lexical_probe五份直接兼容测试另**104 passed，11.81秒**。首次合成验证117 passed/1 failed为测试使用不存在的取消枚举，改用既有`CLIENT_DISCONNECT`后通过，没有修改生产合同或放宽断言。临时`PYTHONPATH/MYPYPATH`指向两项目源码，`mypy --strict src`及projection/owned/stage/comparison四工具为157源文件通过；七份直接Python文件compileall通过。未执行全量Python/Maven、实际服务、ES/BGE/模型或真实UAT。

独立Stage复评实际运行非法DTO停peer、绝对超时、吞取消后的迟到结果及调用中signal取消四项反例，**4 passed / 9 deselected，0.51秒**，两项问题关闭；相邻owned/projection及纯trace提取无新增已确认问题。该限定代码评审无未关闭Blocker/Major，不代表真实执行、整体质量或发布批准。独立文档复评核对三份实际diff、相关源码、版本状态及证明范围，未发现需修复的问题；只将本增量转为Reviewed，不批准真实执行或整体目标完成。P3严格校验0错误/0警告，三文档98条本地链接与围栏通过，四项历史关键hash保持。

尚需同一总执行器的真实受限代理/启动健康检查、现场模型和策略快照、fresh库存前后核验、完整精确冻结与独立授权；当前接缝没有live CLI或默认连接，不等于完整真实生命周期已经验证。257/378仍仅条件预测。14包/14边、11 Done/2 In Progress/1 Blocked、A未评/B不采用/旧MEASURE invalid_run及人工结论保持，本轮仅本地提交、不push。

<a id="record-14-51"></a>

### 14.51 只读物理代理及发送边界复评（2026-10-04）

起始clean `codex_0915` HEAD `2d7dfe12eddc23017e1542244b1fea2b86fbcf63`。新增[私有物理代理](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_proxy.py)及[直接测试](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_proxy.py)，复用同一ledger、Java实际投影hash及production Stage；没有真实CLI、默认连接、密钥读取或运行授权资产。

- 每臂仅允许两个冻结Profile的6次元数据GET，逐路径响应规范hash须与caller提供的当次冻结值全等；随后按草案顺序绑定case，只接受固定alias的POST search。keyword要求匹配独立Java投影，vector要求匹配共享向量，原始bytes不重写。调用前计attempt，失败停止两臂新发送；keyword/vector的backend I/O不被代理锁串行化。
- 请求长度、重复Content-Length、Transfer-Encoding、部分正文及超时失败关闭；响应产品/媒体/编码、长度及总时限有界。仅关闭登记的本代理连接、线程及server；backend client由caller拥有。原始正文、向量和异常只在内存处理，不进入有限日志。
- 单次发送守卫移入[轻量私有模块](../../knowledge-corpus-tools/src/knowledge_corpus_tools/http_client_safety.py)，避免Agent venv因间接导入语料解析器而要求bs4；旧snapshot导入位置保持兼容，未安装依赖。独立评审确认并关闭3项问题：默认client.params可改变竞争池；BaseHTTPRequestHandler吞掉请求行/头超时而不停止ledger；`.`/`..`名称经HTTP规范化越出固定路径。新增零实际发送、超时停批及名称构造反例，另拒绝`_all`而保留合法隐藏名称。

本轮实际验证：

- Agent `python -B -m pytest`：七份`test_rebuild_document_number_{proxy,stage,owned,projection,comparison,transport,journal}.py`加minimal_stage/minimal_ranking/fusion/http/bge_rerank_context五份unit，使用`-o addopts='' -q -p no:cacheprovider --tb=short`，最终**352 passed，21.10秒**。包含两臂十题44次合成物理请求、生产Stage及同ledger装配，未启动Java或真实HTTP server，不冒充真实清理、集成或质量证据。
- Corpus `python -B -m pytest tests/test_document_number_snapshot_v1.py -o addopts='' -q -p no:cacheprovider`：**96 passed，3.79秒**；默认routing参数拒绝与旧scanner反例保持。临时双源码路径下Agent `mypy --strict src`及proxy/owned/stage/projection/comparison五工具：**158源文件通过**；七份本轮Python文件compileall通过。
- 首次收集暴露bs4间接依赖，首次类型检查有5项新工具类型问题，均已修复；合并测试曾因测试网络守卫误拦Windows asyncio内部socketpair而出现级联失败，改为拦截实际native HTTP发送及服务入口后通过。未删除断言、放宽行为或隐藏初次失败；本轮没有全量Python/Maven、实际ES/BGE/模型、服务或UAT执行。
- 未参与编写的只读执行单元直接核对源码和反例，实跑参数/请求边界9项及名称2项后确认3项关闭；本私有增量无未关闭Blocker/Major，不批准真实运行或整体质量。

独立文档复核直接核对三份实际diff、相关源码和转交的原始验证输出，确认版本、证明范围与原状态一致，无需修复；只将本增量转为Reviewed。P3严格校验0错误/0警告，本轮四项历史关键hash保持，代码差异与文档链接/围栏检查通过，不以文档复评代替未执行的全量回归或真实验收。

元数据hash由caller提供，不自动证明其来源、现场时效或授权有效。尚需统一外层执行器、受控启动健康检查、现场模型/Profile/策略快照、fresh库存前后扫描及完整精确冻结和独立授权；代理源码存在不等于真实生命周期已经证明。257/378仍仅条件预测。没有模型、ES、BGE或Business实际调用、服务启停及索引/alias写入，也没有新run/authorization/consumed/result。14包/14边、11 Done/2 In Progress/1 Blocked、A未评/B不采用/旧MEASURE invalid_run及人工结论保持；只本地Git收口，不push，完整目标未完成。

<a id="record-14-52"></a>

### 14.52 自有启动、预热及Stage统一装配（2026-10-04）

起始clean `codex_0915` HEAD `c7ad68dcb7bee592f56c855029165939c614d680`。新增[私有统一装配](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_runtime.py)和[直接测试](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_runtime.py)，把既有同产物lease、owned资源、物理代理、journal和生产Stage接在一起；没有live CLI、默认执行、快照采集、授权核验或发布入口。

- 代理先登记再启动；进程创建取得Popen后立即登记，先于就绪检查及后续资源获取。原生端口等待有30秒总期限，不发送HTTP、不停止未知服务；确认自有PID后，每臂只发送一次计数的readiness健康GET。失败不轮询重试，不执行题目。两臂12次Profile元数据仍由实际代理计数，不由健康检查代替。
- 复用版本化预热工具的合成40段payload及严格decoder，不调用其自建client入口；预热单独计一次`prewarmRerank`，30秒绝对期限不覆盖正式Stage的5秒调用边界。原始回复只驻留内存，不进入journal。每次typed发送前重核自有PID及固定origin，模型发送也核client；认证、cookies、params、hooks、redirect及隐含retry均不得改变一次attempt的含义。
- 技术/协议失败停止新发送，取消时先排空子任务，再保护并完成owned清理；清理未知不能返回成功capture或释放构建目录。输出仍为有限Stage轨迹和清理报告，`quality_assessment=Not assessed`、`release_allowed=false`。

独立源码复核发现：健康provider吞掉work-task取消并返回UP时，旧接缝仍可能发出第二臂健康及预热。已在发送前和响应接受前检查当前task的取消状态，新增首health吞取消的反例：只保留1次取消回执，后续health/预热/Stage为0，pending=0，owned资源清理。复核者未参与编写，直接检查源码并运行7项取消/期限反例，**7 passed / 27 deselected，6.38秒**；确认该缺陷关闭，本私有增量无未关闭Blocker/Major。文档的进程登记顺序措辞一并修正，三份实际diff的状态及证明边界复核后转为Reviewed，不批准真实执行或整体质量。

修后实际验证：八份`test_rebuild_document_number_{runtime,proxy,stage,owned,projection,comparison,transport,journal}.py`、五份生产检索unit及预热工具测试，Agent `python -B -m pytest -o addopts='' -q -p no:cacheprovider --tb=short`合计**413 passed，47.01秒**；包括十题双臂44次合成typed/physical、共享embedding10、rerank22、健康2及预热1，均非真实调用。双源码路径下`mypy --strict src`及六份直接工具**159源文件通过**；新增两文件compileall通过。首次直接测试发现健康/预热client origin检查缺口，已补固定端口反例；首次单文件类型检查因遗漏Agent src路径产生import/stub错误，改用实际项目路径和完整src，不忽略import或安装新依赖。修前412项通过不替代此次取消修复后的结果。P3严格校验、103链接/围栏、14包状态、四项历史关键hash及差异检查通过；未执行全量Python/Maven或真实UAT。

本增量只完成启动至清理的私有装配，尚未接入新鲜库存前后核验、现场模型/Profile/读取与出域策略快照及精确授权核验；caller元数据hash仍不能自证来源或时效。后续先形成完整独立冻结与预算材料，不把条件预测257/378当授权，不自行发起真实ES/BGE或MEASURE。没有服务启停、模型密钥读取、实际HTTP、索引/alias写入或新运行资产；14包/14边、11 Done/2 In Progress/1 Blocked和原质量/人工结论保持，完整目标未完成。

<a id="record-14-53"></a>

### 14.53 全库存发送计数、现场绑定及封存前后验接缝（2026-10-04）

起始clean `codex_0915` HEAD `d9284241474ddb8d84576468e4902e221dcf98cd`。新增[私有库存接缝](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_inventory.py)及[直接测试](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_inventory.py)，扩展现有scanner与owned/runtime/Stage，不修改生产代码、配置、任务、gold、阈值或历史资产。没有CLI、默认client、运行目录或授权生成入口。

- 复用全记录scanner，definition及每页读取均在实际HTTP之前通过同一ledger checkpoint；传输、状态、JSON或完整性失败停止新发送，不扫描结束后补记。每次发送重核client与固定origin，禁止中途cookies/params/auth/hook/重试漂移。回执写入失败保留pending，不能假称已有完整证据。
- `preparation`采集alias、settings、mapping和完整竞争池；`pre/post`各一次，必须与本次准备捕获全等。核实唯一alias目标及完整flags（无filter/routing、无未知字段）、UUID、mapping hash/version、写保护、数量、全记录元数据/正文/向量fingerprint，以及固定必要来源的精确正文hash。law及未分类记录不被抽样或删除；只返回ID/hash清单和有限摘要，完整正文/向量不落盘。该捕获不证明排他窗口、人工gold或实际操作权限。
- `capture_async`取消时先停止新发送，即使停止checkpoint写入失败，也保存有限失败、持续排空并读取同步worker结果，再允许关闭借用client；已经取消时不创建worker。阶段锁只允许成功前验之后开始后验；重入先保留拒绝状态并停账，最后一页的迟到结果也不得成功提交。全库存有限ID清单沿用16MiB上限，不误套typed DTO的2MiB上限；两种上限不互相放宽。
- runtime原finally会停止ledger并封存journal，因此后验接在Stage成功之后、同一owned清理之前；后验失败或取消不得返回成功capture，也不重开日志。capture分别保留Stage边界计数与含后验的最终计数，避免隐藏后验消耗。
- owned启动参数及typed响应复用同一`ReadBinding.profile_snapshot`公式；每条成功/零命中响应均需匹配该域预期snapshot和冻结读取策略，不能只验证两臂相互一致。错误共同snapshot在online rerank或第二臂前失败关闭。纯Stage内存演练可不提供binding，owned路径必须提供；缺现场来源及独立授权仍不能执行真实操作。

当前HTTP调用图的预算推导（不是实际数量或批准额度）：全库每次`1+ceil(N/250)`；正式前后各一次、外层元数据6加Profile启动12、typed/physical各44、共享embedding10、rerank22、预热1、readiness每臂1，BGE健康HTTP0。若N=15521，正式执行HTTP上限269；另加独立准备的64次scan及3次元数据则合计336，ES仍为257。§14.47的378保留为当时预测，不改写历史预算；模型/PID/文件快照等非HTTP操作、实际N及全部前置必须另行冻结，不把本推导当完整授权。

本轮实际验证使用corpus项目venv和临时双源码/Agent路径，未安装依赖：

- 九份私有document-number测试、五份生产检索unit及预热工具：`python -B -m pytest -o addopts='' -q -p no:cacheprovider --tb=short`，最终修后**457 passed，76.11秒**。含postcheck封存顺序、失败/取消清理、共同错误snapshot、分页cookie漂移、完整law/无分类竞争池、超2MiB有限清单及三项评审反例。修前454项及第一轮修后四文件109项，只保留各自当时范围，不替代最终回归。
- corpus原`test_document_number_snapshot_v1.py`和`test_b_id_mapping_v1.py`：**99 passed，3.58秒**；与上一组范围不同，不相加冒称全量回归。
- `mypy --strict src`、七份直接私有工具及scanner：最终修后**161源文件通过**；七个修改源码/测试compileall通过。首次合并检查23失败/48通过，原因是新Mock响应被httpx预消费，不符合生产`iter_raw`；仅改fixture为ByteStream，未放宽生产传输或断言。评审补修首次出现括号SyntaxError、collection中止，修正后定向与最终回归通过；失败检查不记通过。

独立子代理只读增量评审发现停止记录写失败时未排空worker、并发后验越过未完成前验两项可靠性缺陷；第一轮修复后复评又证实最后一页停账仍返回迟到成功。两轮最小修复及直接反例后，最终定向复评未发现新的确认缺陷，三项均关闭；评审者另实际运行14项子集、24项未选，3.76秒，全部通过。本结论只覆盖本次私有工具及三份文档增量，不批准真实运行或整项目验收。P3严格检查0错误/0警告、三文档105本地链接及围栏、四项历史关键hash及diff检查通过；未执行全量Python/Maven或真实UAT。

现场模型/Profile配置/出域策略证据及独立run、授权有效窗口、消费守卫和外层总执行入口仍未完成；真实快照本轮没有采集，工具支持不等于现场已验证。没有模型密钥读取、实际服务/HTTP、索引或alias操作；原14包/14边、11 Done/2 In Progress/1 Blocked、A未评、B不采用及MEASURE原invalid_run保持，完整目标未完成。

<a id="record-14-54"></a>

### 14.54 现场身份私有接缝与独立非HTTP计数（2026-10-04）

新增[身份接缝](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_identity.py)及[直接反例](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_identity.py)，只复用现有只读模型采集、投影产物、实际配置和catalog；没有CLI、默认Docker provider、授权签发或真实执行入口，不修改线上检索与回答。

- 模型采集复用`capture_model_identity`，每阶段恰好2次inspect、2次只读exec。采集前检查现有Python/项目依赖锁；完整两个container ID及embedding模型hash由未来外层明确绑定，不从旧B资产或当前端口猜测。Docker可执行文件固定路径/hash，每次检查重核；命令显式指定获准的本地named pipe或unix socket，不继承远程context，不推理、不读取模型密钥。
- 静态材料实际核对冻结HEAD及tracked clean、同lease双JAR及共享类/依赖、两域Profile、冻结live YAML和三份共享配置、Java程序hash、加载的当前catalog和模型采集源码。运行配置按真实helper返回的目录与hash共同核对，不能用相同版本名替代；catalog身份仅证明资源不漂移，不证明新增读取或出域许可，也不等于Evidence/Summary测试。
- `preparation`或有序`pre/post`各只能尝试一次；expected静态漂移在第一个Docker操作前拒绝。四次probe前将命令/输入hash写入同一append-only journal的独立非HTTPledger；失败不返还、不重试，不保存原始命令参数或进程输出。异步取消停止新操作并排空同步worker，即使停止checkpoint失败也不遗留worker；迟到及并发重入不能提交成功捕获。
- 统一runtime在创建自有资源前要求pre4/post0；Stage后、清理封存前要求pre4/post4。遗漏或失败后验不得返回成功；日志封存前必须无在途非HTTP回执。两类ledger拥有独立停止状态，不声称同文件自动成为跨类别并发总闸；未来外层必须按前置、执行、后验顺序传播失败，不能忽略失败继续进入另一阶段。

若真实准备和正式前后核验各一次，模型身份上限推导为4＋8＝12次本地进程操作，独立于§14.53的269/336 HTTP推导；Git、文件、PID及服务生命周期仍须在完整冻结材料中分别列明。本轮仅使用合成进程/HTTP提供者，未做现场采集，推导不是批准额度或实测计数。

本轮实际验证使用corpus项目venv及临时双源码路径，未安装依赖：十份`test_rebuild_document_number_*.py`及minimal_stage/minimal_ranking/http/fusion/bge_rerank_context五份生产unit，`python -B -m pytest -o addopts='' -q -p no:cacheprovider --tb=short`，**466 passed，91.93秒**；另有既有warmup及模型身份工具两份测试**34 passed，0.20秒**，不相加冒称全量。`mypy --strict src`及identity/journal/runtime/inventory四工具**157源文件通过**。首次收集循环导入、首次类型检查配置helper返回tuple错配均真实失败；修复导入边界、解包及精确shared hash后通过，测试mock同步真实接口形状，未删除断言或放宽行为。

独立只读评审直接检查源码、现有设计和反例，证实上述tuple错配并复核修复、早期静态漂移拒绝及串行runtime接缝。评审者实际重跑identity＋journal **65 passed，5.47秒**和runtime新增身份集成子集 **4 passed、40未选，16.91秒**，本增量无未关闭Blocker/Major；不批准真实Docker、服务、推理、独立授权或整体UAT。未执行全量Python/Maven及真实效果测量。

旧A/B/MEASURE结论、gold/阈值、14包/14边和11 Done/2 In Progress/1 Blocked均保持。独立授权引用、原子消费及外层总入口仍未完成，不恢复旧许可或新建真实运行资产；不能宣布COMPARE、MEASURE、功能/效果UAT或RELEASE完成。

<a id="record-14-55"></a>

### 14.55 独立范围消费与私有串行入口（2026-10-04）

新增[私有串行入口](../../agent-runtime/tests/evaluation/knowledge/rebuild_document_number_runner.py)及[直接反例](../../agent-runtime/tests/evaluation/knowledge/test_rebuild_document_number_runner.py)，复用前节的库存、身份、Stage、日志和owned清理，不新增Gate、线上检索分支或评分权威。本轮只有合成临时资产和fake资源，没有CLI、默认确认方、默认进程提供者或真实授权签发。

- RunScope把新run、准备/正式阶段、HEAD、协议/投影、索引及模型目标、静态材料、前置捕获、HTTP/非HTTP上限、端口和排他有效窗口绑定为精确材料。外部可信调用方必须核实维护者的新精确确认及排他条件，再提供绑定材料hash、reference和决策记录hash的receipt。模块只检查一致性，不能证明人类确认来源；approved=true、任意引用字符串或自算hash均不能自行授权。当前尚无实际确认方、新正式grant或现场冻结材料。
- 准备与正式使用不同的新run及确认：准备只允许库存/身份捕获，正式必须带完整捕获并再次前后核对。正式消费位置固定为仓库agent-runtime/tests/uat/results/document-number-comparison下的run标记和日志；仅合成范围可指定测试临时根。独占创建、完整写入、flush/fsync后才允许第一个受限操作。已有目录/标记、路径别名、短写和持久化失败均拒绝，残留标记不删除、不重试，不以换目录恢复机会。
- 每次HTTP或模型probe边界以及proxy/Java启动前检查窗口与取消状态，不依赖watcher及时调度。代理先登记归属再检查/启动；前验必须实际返回成功捕获，不能仅凭pre计数进入执行。Stage成功后，在原日志封存前完成身份与库存后验，失败即停，不执行补证式后验、不切域或Capability。
- 两类ledger分别停止，首个停止checkpoint失败也不妨碍第二类停止、排空worker和关闭client。正式库存client转交同一owned生命周期，准备/早期失败由外层关闭；拒绝非精确HTTP客户端前先接管可识别句柄。取消及迟到结果不返回成功；拒绝发生在已预留checkpoint时保留pending和有限失败，不能编造完成回执。清理/封存失败也不宣布成功。

真实调用仍为零。若未来独立准备和正式前后各一次、现场N确为15521，准备HTTP67及身份probe4，正式HTTP269及身份probe8，合计HTTP336及非HTTP身份12；只是条件上限，不是批准额度、实测数量或已有授权。Git/文件/产物及PID/归属核查分别按冻结范围管理。输出仅为捕获与有限attempt证据，质量Not assessed、releaseAllowed=false，不替代人工评价、MEASURE或发布。

本轮实际验证（corpus venv、临时双源码/Agent路径，不安装依赖）：

- 十一份test_rebuild_document_number_*.py及minimal_stage/minimal_ranking/http/fusion/bge_rerank_context五份生产unit：python -B -m pytest -o addopts='' -q -p no:cacheprovider --tb=short，最终修后**501 passed，97.37秒**；新入口直接**35 passed，11.42秒**，不与前一集合相加。含精确材料拒绝、并发一次消费、短写/fsync失败保留标记、阶段失败、后验封存、停止失败、重复取消排空、逐次窗口/取消检查及完整fake Stage。
- mypy --strict src：**153源文件通过**；四份直接工具mypy --strict --follow-imports=silent：**4文件通过**，保留strict目标检查，不把未修改导入模块列作本轮验证。五份修改Python compileall通过。首次扩大导入检查报28项（含新入口4项及既有语料解析依赖/类型问题），修复本轮问题后分开检查；不修改类型配置或安装依赖，不声称扩大检查通过。首次直接测试24通过/2失败为fixture取消参数与ledger故障注入错配，修正后通过；首次扩大回归因unit路径缺retrieval未执行，核实后才得到501项结果。
- 独立子代理实际源码与反例复核发现proxy窗口检查、拒绝客户端句柄遗漏、worker取消检查三项缺陷，最小修复并补反例后最终复评**35 passed，11.19秒**，本轮私有工具无未关闭Blocker/Major；不是外部人员验收或真实运行批准。四项历史关键hash及diff检查通过；未执行全量Python/Maven、实际Java重建或真实效果UAT。

独立外层与消费守卫的private/fake实施范围已补齐，但可信确认来源、实际新run/grant、现场准备及冻结、完整盲标和新的合法测量仍未完成。现行b2、旧A/B/MEASURE终态、gold/阈值及14包/14边、11 Done/2 In Progress/1 Blocked不变；不得宣布COMPARE、MEASURE、整体UAT或RELEASE完成。下一步先整理新的精确准备/执行材料并核实相应授权，不复用失败批次或旧许可。

文档内审与独立增量复评核查实际差异，修正P3来源表的UAT版本及补录本次修改映射后，无剩余确认问题；109本地链接、围栏、版本和P3严格检查0错误/0警告通过。Reviewed仅指本增量，不改变历史验收、运行授权或全目标状态。

<a id="record-14-56"></a>

### 14.56 实际离线Java投影与下一准备范围（2026-10-04）

在干净`codex_0915`提交`e1b775e6acfb34fa2d20ada7f00dc48a8250aad3`，使用corpus项目venv及临时双源码/Agent路径，实际执行：`python -B -m tests.evaluation.knowledge.rebuild_document_number_projection --offline-project`。工具从该提交导出两份临时源码，旧臂仅替换`DocumentNumberQuery.java`为`a1ba290e8b2d78da71d46bc1f39018be502c7347`中的文件；Java25启动Maven `--offline --batch-mode -pl :es-query-service -am -DskipTests package`，再调用真实package-private请求构造器。命令成功、临时构建目录已由工具清理；未修改当前target、启动服务或执行Maven测试。Java编译/请求投影不是实际ES检索、召回改善或UAT证明。

实际产物核验：

| 项目 | 结果 |
|---|---|
| 两臂共同配置hash | `717e4acc8bd82602af2cdced623175582dfe7a980290df3baab1910d2d8e7df5` |
| 两臂共同业务类hash（排除helper） | `e6b72c120942f503a862c8c2ad15bdbf2325bcaaa7d53e9db310b043707d1690` |
| 两臂共同依赖hash | `fa11861749f7ce80a1711e790e95ea391a437bbbcf38b55995c4cd3702da17e1` |
| 旧臂JAR hash | `fd99d37d03ab31b63dadcfa989f4e663233ed52039940f9cfa376d94caf7edb7` |
| 当前臂JAR hash | `9afb543a5782558b9043804858c6569fb905b35a781c5135cef232e79117fe3a` |
| 原始源码helper hash | 旧`9eb7f0889f17e75568d7112d0355a69142d52f109f240df151366a64e8b97550`；当前`90b4c5c88d071f9e31dee557996d3b804752d953bead6a2dd699c54cc8ff43ff` |
| 11个域单元规范请求投影 | 仅003 policy、007 policy不同；其余9个相同，全部law单元相同 |

上述hash只绑定本次已清理的离线产物及起始提交，不作为后续JAR租约、当前部署、正式冻结或新操作许可。后续实际准备必须在其HEAD重新构建、核验并保持同一产物租约；不以本节历史hash替代新现场捕获。

下一步只提出**一次独立无付费准备**，不立即执行、不再扩展私有工具或重做已通过fake回归。拟议最小范围如下，须维护者明确确认后才能操作：

- 目标为现行b2的既有只读alias `agent-doc-tax-policy-v2-read`；预期索引`agent-doc-tax-policy-v5-20260907-vector-b2`、UUID `jJ5Ww3LCRWWycfDkUZvmdw`、mapping hash `1c2ab9b48ae5b3fcd37b91fec883b6141d3616b2331cdf3a430ea4500a40db82`及N=15521仅从旧证据取得，**当前尚未观察**。不吻合则停止，不自行换目标或扩大记录/调用额度。
- 本地ES `http://127.0.0.1:9200`最多67次HTTP：3次有限元数据＋1次全扫描身份检查＋最多63个250条分页；只用于当前完整竞争池fingerprint/身份核实，不做相关性search、typed检索、写入或alias切换。保存有限身份、hash和记录清单，不保存完整正文/向量。
- 固定Docker可执行文件`C:/Program Files/Docker/Docker/resources/bin/docker.exe`，本次本地文件SHA-256=`575b19fdc3cc3054714e6cbe92bcf86b708cc5dc46ad5e75bfd7591220de86fe`；显式本机named pipe。最多8次只读进程操作：分别按publish=8908/8909过滤定位及取完整ID共4次；将唯一实际ID显式绑定后，使用既有2次inspect＋2次只读模型文件hash探针共4次。定位/模型不符、非唯一、超时或失败即停止；不执行模型推理、容器启动/重启或远程Docker发现。不能从旧容器或端口宣称模型身份已验证。
- 新run/reference、有效排他窗口及精确材料需绑定实际确认，准备期和随后正式执行使用独立身份；不能把本节提议自签为grant。正式全链对照、MEASURE、服务启动、预热和推理**不在这次准备提议内**；准备结果用于形成后续精确范围，不复用任何失败批次。

本轮真实模型/ES/BGE/Docker/服务操作均0；只执行离线Java/Maven构建与本地文件/Git读取。旧A/B/MEASURE、人工结论、gold、阈值、14包/14边与11 Done/2 In Progress/1 Blocked保持。尚缺新的精确只读准备确认及现场捕获，不能关闭COMPARE、MEASURE或RELEASE。

文档内审及独立子代理增量复核直接检查三文档diff与投影/身份/库存/预算源码，无需修正的实质问题。表中执行结果与转交的实际工具输出一致；评审者未重新执行构建或独立重算已清理JAR的字节hash，不冒称独立执行验收。109本地链接/围栏、P3严格检查0错误/0警告、4项历史关键hash及差异敏感模式检查通过；没有代码、测试、配置、历史运行资产改动。Reviewed仅指本轮记录和提议边界，不批准真实准备或质量验收。

<a id="record-14-57"></a>

### 14.57 独立无付费准备终态（2026-10-04）

维护者对§14.56及对话中的精确准备范围确认“授权，继续推进”。执行绑定干净`codex_0915` HEAD `27b18191449b3641a0951fc7e142922d720b2b1b`，新run `knowledge-document-number-20261004-01`，reference `P3_01:14.56-preparation`；排他窗口确认及UTC有效期限记录在新authorization中，不继承任何旧批次。一次性编排仅复用既有投影、身份探针及库存扫描器，不新增生产入口或Gate。源码复核修正provider关键字参数、消费写入失败分类及独立清理后，执行AST、依赖锁检查和独立增量复评，再进行真实准备。

| 项目 | 实际结果 |
|---|---|
| 终态 | `prepared`，授权已消费；不补跑、不续跑 |
| ES只读HTTP | 67：元数据3＋完整扫描64（身份1＋分页63）；相关性search、typed search均0 |
| Docker只读进程 | 8：唯一容器定位4＋既有模型身份probe4；模型推理0 |
| 完整竞争池 | 15521条；alias、索引UUID、mapping及写保护与授权预期相符，全部固定必要来源身份/hash存在 |
| 完整source fingerprint | `fb285fc5e5e838fbccb2025f24c0f4472802b8beb7190247cefc9a2978b9a17d` |
| 有限库存SHA-256 | `e2178b1ee9f13ce840e1a1b878cc7778e554ab1319eecb7e73b0ed1baa5a6f96`；只含身份/hash，无正文或向量 |
| 实际模型身份SHA-256 | `b8dd942d15e24c741845dd2300a6e28f8c23501ab2256a04a26c1959b7d1b9a1`；读取模型文件核验，不做推理 |
| 清理 | journal已封存，HTTP/定位/身份pending均0；客户端关闭，离线临时构建lease已释放，无服务/proxy启动 |
| 禁止操作 | 模型/BGE推理、服务启停、索引/alias写入、MEASURE、retry/resume均0；未读取模型密钥 |

有限证据见[准备result](../../agent-runtime/tests/uat/results/document-number-comparison/runs/knowledge-document-number-20261004-01/result.json)，SHA-256=`28b5acea2e57267f17eeaefeb14b4263360c4a17d05d27910c1b652f70ada340`。同目录保留授权、append-only attempts、实际投影、模型身份、有限库存和一次性执行源码；固定consumed在其独立目录保留，不覆盖旧资产。两臂本次共同业务类/配置/依赖一致，仅003/007 policy规范请求不同，全部law相同；实际JAR hash以本次projection为准，不复用§14.56已清理产物。

该准备只证明当次现场身份和完整竞争池，不证明召回改善、回答、37项整体Functional/Safety、COMPARE/MEASURE或发布通过。A未评价、B不采用、原人工001/002 Passed与003/004 Failed、MEASURE invalid_run、11 Done/2 In Progress/1 Blocked保持。

下一步形成文号helper全链成对对照的独立精确冻结与执行范围：保留原10个召回题、11域单元、gold/阈值和完整b2，仅比较旧/当前helper，不创建索引、不调用LLM、不重跑旧B/MEASURE。正式前后库存及模型身份复核必须计入其独立预算；本次准备不授予服务、推理或正式对照许可。后续HEAD变化时重新核对离线产物/静态身份与准备材料的兼容，不能将旧JAR或旧静态hash当作新部署身份；不为状态文档提交机械追加没有决策价值的准备全扫描。尚未执行该正式对照或MEASURE，当前本轮授权已耗尽。

本轮独立子代理源码复核发现并关闭三处一次性编排问题；执行后独立重算授权、脚本、captures、identity、inventory及projection的规范hash，核对156条journal、完整回执与字段边界，再对三份文档作定向复评，修正两处版本/修改历史遗漏后通过。评审未再次访问ES/Docker或重算已清理JAR；因不持久化正文/向量，不能从有限身份清单独立重建全source fingerprint，不扩大证明范围。主执行者本地资产交叉验证、110条链接/围栏、4项历史关键hash、P3严格检查0错误/0警告及git diff检查通过。该轮没有生产源码、测试、配置或历史资产修改；未执行pytest全量、Maven测试、真实质量UAT或发布，离线Maven仅构建并跳过测试。

<a id="record-14-58"></a>

### 14.58 独立成对执行前置失败及有限诊断修复（2026-10-06）

维护者确认§14.57后提出的精确范围：HTTP≤269、模型身份只读探针≤8，最多两臂owned Java/proxy，LLM/索引/alias写入/retry/resume均0，并确认排他窗口。新run `knowledge-document-number-20261006-01`，reference `P3_01:14.57-execution`，冻结clean `codex_0915` HEAD `89bf287738c64e28645cbfb8e199f96d63f242c9`。§14.57捕获仅作为expected基线，不冒充本次现场观察。

第一次本地预检在消费及任何受限操作之前发现Docker.exe文件hash改变，停止且0调用。只读本地核实新文件为29.8.2、Authenticode Valid / Docker Inc；本次冻结使用新SHA-256 `f71e5a9fe6a8db10c7296ad6fdf0c1d7d79634e644d7ec1e8a2c18d7dcb52d21`，该预检事实记录在decision，不修改旧准备资产。实际离线双臂Java/Maven构建通过，仅helper差异；一次性范围随后正式消费。

| 项目 | 实际结果 |
|---|---|
| 唯一终态 | `failed_consumed`，reason=`runner_attempt_failed`；不可补跑、续跑或复用余量 |
| 模型身份探针 | pre=4、post=0；4次只读进程均有completed回执，不证明collector已成功形成身份 |
| HTTP与case | 全部HTTP分类0、case=0；未进入ES库存、Java/proxy启动、BGE推理或检索 |
| 禁止操作 | 付费模型、Business、索引/alias写入、retry/resume均0；未读取模型密钥 |
| 有限证据 | 12条连续journal、授权、decision、expected快照、实际离线projection、执行源码及result；没有observed identity或comparison |
| 清理边界 | journal封存；客户端关闭，未启动服务/proxy；离线lease已成功退出。reportedCleanup是执行方报告，不冒充journal独立资源证明 |
| 质量与发布 | `Not assessed`、releaseAllowed=false；前置技术失败不是召回质量失败 |

证据见[独立执行result](../../agent-runtime/tests/uat/results/document-number-comparison/runs/knowledge-document-number-20261006-01/result.json)，SHA-256 `d3ec355103f899cfe19c5a8f4b84b49153d450ae62aa962b7ae3de0fa06ce89c`；同目录保留实际冻结执行源码，不用后续修复替换。独立只读复核确认hash链、计数、封存及资产边界一致。

离线诊断：两批4项command摘要及collector源码相同，两个exec输入摘要均不同；输入仅含StartedAt和固定模型文件清单，因此有依据推断两个容器的启动时间均改变。相同container ID不证明完整运行身份仍相同；这不是模型文件变化的证明。当前封存证据无法确定第一处异常究竟发生于collector、静态复检、材料构造还是expected比对，不声称已查明唯一根因，也不补写旧结果。

针对实际诊断缺口，最小修改既有IdentitySession及runner的私有字段，保留固定失败阶段；只有规范捕获完成后才保存observed供owner诊断，不能把它当作accepted身份。失败前清除上次成功capture；非active非法阶段拒绝也清除残留，并发拒绝不覆盖正在工作的capture。仍精确比对、失败关闭、一次消费及零重试；不记录原始异常、provider输出或正文，不新增框架、probe或线上行为。新字段只经fake验证，本次冻结执行器不具备这些后加字段，故不能反向补证。

修后直接identity/runner两文件 **68 passed，14.84秒**；`mypy --strict`检查完整Agent src及两个直接工具 **155源文件通过**；四个修改源码/测试compileall通过。第一次68项通过只证明修前范围；独立复审发现非法阶段保留旧成功capture后，最小修复并重跑上述68项。没有放宽断言或真实复跑。未执行全量Python/Maven回归、真实效果UAT或发布；本轮离线Maven跳过测试。

独立子代理未参与改动，定向源码复审及修后14项fake通过，确认诊断残留缺陷关闭；有限资产及三份文档定向复评通过，修正文档来源表的旧UAT版本遗漏。Reviewed只覆盖本增量，不批准整体质量。P3严格检查0错误/0警告、111本地链接及围栏、4项历史关键hash和diff检查通过。外层7份临时副本逐字节核对与正式run一致后清理，正式资产完整保留。

有限失败资产已本地提交为`0e8ccb64`，未推送；诊断及本次状态同步由后续本地提交承接，不改本次frozen HEAD。

原14包/14边、11 Done/2 In Progress/1 Blocked、A未评价、B不采用、MEASURE invalid_run及001/002人工Passed、003/004 Failed保持。下一真实步骤需独立范围和有效授权，先取得与当前运行实例相符的模型身份，再绑定新的成对执行；保留完整库存前后核验和质量阈值，不重复本批、不忽略StartedAt或弱化exact expected。本轮已用尽独立消费机会，不能以剩余预算自动执行新准备或MEASURE。

<a id="record-14-59"></a>

### 14.59 现行职责、历史兼容与验证冻结顺序收口（2026-10-06）

维护者授权按定向评审建议进行最小收口。起始clean `codex_0915` HEAD为`d1abbee8c6c87f46c55e4d1587bcb46b25d9c157`；本轮只修改当前内部代码、直接测试及三份Knowledge L2/P3/UAT/架构索引，不执行真实服务、ES、Docker或模型操作，不读取密钥，不推送。

| 处理项 | 实施及证明范围 |
|---|---|
| 现行职责与历史兼容 | 当前组合根静态绑定`MinimalKnowledgeQueryCapability`和`MinimalKnowledgeEvidenceStage`，意图12/模式输入/Summary9使用精确类型；原`capability.py`及`evidence/stage.py`保留历史调用、字节不变。只复用无版本分派的ports、bindings、deadline和结果构造，不新增路由器、包装器或继承适配层 |
| 冻结顺序 | 授权范围内启动就绪→实际当前capture→`freeze_execution_identity(prepared,current)`→冻结→正式pre/post完整精确比较。新纯函数只允许既有同模型规则中的`started`准备期差异，static、Docker及其余模型/容器字段精确；返回完整current，不能证明采集来源、就绪或授权，不产生额外probe |
| 局部重复检查 | 移除Evidence对不可变Plan按自身settings的重复完整重验；Plan构造与Retrieval的实际配置配对检查仍在，Evidence的问题/模式/coverage/batch/来源hash/策略及引用边界保留。身份helper只锁其实际导入的Python/httpx/pydantic，旧corpus CLI全量环境锁和完整模型快照不变 |
| 文档职责 | UAT只保留风险、判据、当前结论及证据入口，不再重复版本和逐轮执行流水；实施授权摘要指向本轮范围和历史记录。三份L2增量定向复评通过，Approved不表示真实质量验收通过 |

实际验证（均为本地/non-live；重复覆盖的多次执行不相加）：

- Agent主执行者：设置进程级`PYTHONPATH=D:/codex/agent-runtime/src`后，`python -m pytest tests/unit tests/integration/knowledge tests/integration/business tests/integration/test_core_graph_with_stubs.py --ignore-glob='**/test_real_*.py' -q`：**1785 passed，165.55秒**，覆盖当前/历史Knowledge、共享Core及Business/Employee/Transaction单测；显式排除真实Knowledge用例，不冒充真实集成/UAT。
- 在线实现定向验证：当前root/Summary9/风险接线、Summary9 contract及README要求的HTTP/startup **80 passed**；历史Evidence/Summary8/冻结根 **140 passed**，旧production/admission/v11/Summary2/4 **59 passed**。在线独立评审另执行六个直接测试文件 **192 passed**，只读穷举92组有限kind/code映射，与旧minimal分支一致。
- 身份工具独立评审：corpus项目venv、双src路径下identity/runner **110 passed，16.70秒**；`knowledge-corpus-tools/tests/test_b_model_identity_v1.py` **11 passed**，包括准备期可允许差异与正式pre/post漂移拒绝。旧CLI和runner执行语义不变。
- `python -m mypy src`：**155源文件通过**；两个身份工具及corpus身份模块的定向strict mypy、相关源码compileall和`git diff --check`通过。首次辅助检查读到陈旧site-packages或缺失源码类型路径后，以显式源码PYTHONPATH/MYPYPATH纠正；未安装依赖、弱化断言或更改锁。

内审一轮聚焦职责、冻结与安全边界；两名未参与相应实现的子代理分别核查另一组的源码/测试及设计增量，一轮代码交叉复评均无确认缺陷。主执行者核对关键源码及实际验证输出，不把作者自审称为独立评审。三份L2严格检查及P3严格/DAG检查均0错误/0警告；136条本地链接、围栏、旧DR/UAT编号及版本入口核查通过，37项功能风险表与HEAD换行归一后相同。原Evidence文档裸`executor.py`引用警告通过补全真实路径修正，没有更改历史文件。增量敏感模式及diff检查通过。

四项历史关键资产与HEAD blob一致、SHA-256可核查；没有历史运行、任务内容、公共DTO、权限、配置或索引变更。未执行Maven/真实质量UAT/发布，本轮无Java修改；non-live通过不证明召回改善。原14包/14边、11 Done/2 In Progress/1 Blocked、A未评价、B不采用、MEASURE invalid_run及四题人工结论保持，COMPARE/MEASURE未关闭、RELEASE仍Blocked。本轮变更由本次本地提交承接，不改写旧冻结HEAD。

下一步先形成新独立文号全链成对对照的精确范围，使用修后代码及启动就绪后的完整当前身份；预算、排他窗口和授权需有效绑定后才执行。不得复用失败run，不能把本轮纯工具转换当作现场预检或真实执行许可。
