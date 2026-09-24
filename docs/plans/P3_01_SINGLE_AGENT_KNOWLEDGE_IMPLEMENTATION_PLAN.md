# [P3_01] Knowledge 新设计实施计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档标识 | P3_01 |
| 文档类型 | 设计驱动实施计划 |
| 当前版本 | v3.1 |
| 文档状态 | Reviewed |
| 日期 | 2026-09-24 |
| 目标计划路径 | docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md |
| 适用范围 | 已批准Knowledge在线重建、资料组织与检索表示两条主线 |
| 非范围 | Business重新设计、图谱、记忆、多轮、旧候选推进 |
| 权威顺序 | 用户范围 → 仓库规则 → REQ/L0/L1/公共契约 → Knowledge L2 → 当前实现证据 → 本计划 |
| 实施授权 | Ready 不等于实施授权。CONTRACT与RETRIEVAL已有独立授权及完成证据；NORMALIZE本轮获代码/测试与有限只读来源核对授权，不包含CHUNK、索引、服务或模型操作 |
| 计划执行状态 | Done=4（两项来源设计、CONTRACT、RETRIEVAL）；Ready=1；In Progress=1（NORMALIZE）；Blocked=6；生产接线/新UAT未执行 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-09-14 | 全文 | 旧综合计划退出当前推进权威 | 新文档首版v3.0，承接已批准设计，不继承旧计划通过结论、Gate或预算 |
| 2 | 2026-09-15 | §7/12/13 | 跨阶段VAL可能被误读为早期包的全部前置 | v3.0内澄清各验证部分及后续承接包；工作包、直接依赖、状态和验收标准不变 |
| 3 | 2026-09-15 | §1/3/5/7/9/10/12/14 | 按包推进实际实施 | v3.0状态更新：核实CONTRACT提交、完成RETRIEVAL组件与non-live；设计、12条直接依赖及验收判据不变 |
| 4 | 2026-09-24 | §1/3～5/9/10/12～14 | 资料结构单元设计补齐 | v3.1承接L1/L2 v3.2：把解析顺序、稳定unit/span及策略选择分配到NORMALIZE/CHUNK；在线补取仍未授权，12包/12边与既有Done状态不变 |
| 5 | 2026-09-24 | §1/5/9/12～14 | 启动NORMALIZE并修复范围外旧版引用 | v3.1内仅同步执行事实：NORMALIZE离线基础代码及测试已本地提交，真实来源验收待补；L0/L1_00五处Knowledge版本引用已另获授权修正 |

## 3. 来源清单与当前基线

| 资源 | 角色 | 层级 | 状态/版本 | 权威范围 | 是否读取 | 置信度 |
|---|---|---|---|---|---|---|
| [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | 目标架构 | L1 | v3.2 / Approved | §4.5/4.6最小链路与资料组织 | 是 | 已批准设计，不证明实施 |
| [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | 流程详细合同 | L2 | v3.2 / Approved | §8、§19，DR-KFLOW-201～205/301～303 | 是 | 实施权威；在线补取未批准 |
| [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | 检索与资料合同 | L2 | v3.2 / Approved | §9、§18，DR-KRET-201～204/301～307 | 是 | 实施权威；结构单元待实施 |
| [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | Evidence/回答合同 | L2 | v3.2 / Approved | §9、§19，DR-KEV-201～205/301～304 | 是 | 实施权威；父正文不自动成为Evidence |
| [UAT_02](UAT_02_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 当前验收 | 计划 | v3.1 / Reviewed | 新功能/安全/召回/回答及资料验证 | 是 | 未执行 |
| [UAT_00](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | Business维护基线 | 验收 | v3.1 / Reviewed | 固定35风险与Employee15类扩展，原证据范围 | 是 | 历史等价复用，不是本轮UAT |
| [旧P3_00快照](历史文档/2026-09-14-knowledge-plan-handoff/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) | 承接与历史事实 | 归档 | v3.0 / 原状态保留 | §21/22新设计交接，其余旧执行不继承 | 是 | 冻结提交/原资产可追溯 |

起始代码提交为`8ae32c50a567850c67b4d1e726304934ab07162c`；源码事实为11/7/quality-v3，默认Knowledge disabled。task12内部合同已独立实施（§14.1），未进入生产root；Summary8、minimal检索及资料新版本按各包状态承接。仓库配置不是部署证明；本轮不启动服务或读取模型密钥。历史审计与运行状态见[迁移清单](历史文档/2026-09-14-knowledge-plan-handoff/README.md)，不复制到新计划作为新验证结果。

## 4. 计划原则与范围

两条主线分别由三份Knowledge L2定义；本计划不新增DR或修改算法、公共DTO、授权及失败语义。旧ROADMAP不再是前置，不新增替代路线图。原文、安全组件和阶段A成果保留职责；内部旧实验的清理只在后续授权COMPOSE中确认调用方、冻结源可追溯后进行。

Online：合同 → 检索/证据并行 → 成对接线 → 测量。
Corpus：标准化 → 切片/表示并行 → 对照 → 受控发布。
两条主线没有彼此真实UAT前置；COMPARE需选择一套冻结在线实现，可用现有相容实现，不要求先完成MEASURE。新公共父读取、时效/分类DTO或权限变更不是当前隐含交付。

资料结构单元补充沿用现有DAG：NORMALIZE提供来源/版本、规范解析源与结构可信状态的严格记录；CHUNK先修复受影响解析器的段落/表格交错顺序，再生成完整结构单元、连续chunk span及稳定关系；REPRESENT可独立以固定的已验证旧chunk fixture验证表示构造，新的结构chunk与表示集成留给同时依赖CHUNK/REPRESENT的COMPARE。当前typed合同禁止在线父正文补取；未来若确需补取，先单独评审公共合同、安全与预算，不并入EVIDENCE、COMPOSE或本轮资料包的Done判据。

## 5. 工作包清单

来源设计Done承接原审查范围，不表示本轮重做全部设计；v3.2结构单元补充另作本轮文档评审与本地提交，不能把原DESIGN包的历史推送证明改写为本轮推送。验证列为后续完成条件，除来源设计及已完成CONTRACT/RETRIEVAL外均未执行。

| 工作包 ID | 名称 | 来源设计 | 范围 | 直接依赖 | 入口门禁 | 交付物 | 验证 | 回滚边界 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| WP-KREBUILD-DESIGN-01 | DESIGN | L2_01_00 §8 DR-KFLOW-201～205 | 已批准在线设计/分类决策；不重新设计 | - | - | 设计来源与实施边界 | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | 只文档diff，不回滚历史；无服务/模型 | Done |
| WP-KREBUILD-CONTRACT-01 | CONTRACT | L2_01_00 §8 DR-KFLOW-201/202 | 内部意图合同及task12 | WP-KREBUILD-DESIGN-01 | - | 内部schema3/精确decoder/task | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | 后续代码授权；新增独立类型/task，暂不切root | Done |
| WP-KREBUILD-RETRIEVAL-01 | RETRIEVAL | L2_01_00 §8 DR-KFLOW-203；L2_01_01 §9 DR-KRET-201～204 | 原Q双路、域内融合/重排与有界配置 | WP-KREBUILD-CONTRACT-01 | - | planning/semantic_planner/ranking/config最小策略 | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | 本地fake；独立strategy，旧prod不变；无索引写入 | Done |
| WP-KREBUILD-EVIDENCE-01 | EVIDENCE | L2_01_02 §9 DR-KEV-201～205 | minimal Evidence和Summary8 | WP-KREBUILD-CONTRACT-01 | - | mode input、evidence selector、serializer、summary_task_v8.py/decoder | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | 与RETRIEVAL可并行；旧Prompt/serializer不改 | Ready |
| WP-KREBUILD-COMPOSE-01 | COMPOSE | L2_01_00 §8 DR-KFLOW-204/205；L2_01_02 §9 | 唯一root迁移与历史隔离 | WP-KREBUILD-RETRIEVAL-01、WP-KREBUILD-EVIDENCE-01 | - | bootstrap/capability/任务目录；受影响37风险新版验证 | current-root、Spring E2E、37功能重新逐case、Business35关键防退、Java安全/类型/non-live、正式代码评审；Blocker/Major0 | 后续代码/测试权限；不用live作基础代码包完成前置；禁用Knowledge或整套恢复相容发布 | Blocked |
| WP-KREBUILD-MEASURE-01 | MEASURE | L2_01_02 §9 DR-KEV-205；UAT_02 §5 | 固定12题及一次独立测量 | WP-KREBUILD-COMPOSE-01 | - | 新版本问题/来源/预算绑定、有限结果及真人评价 | 人工gold/语料就绪、新独立授权、版本绑定及预算预检；按预置判据分类，真实失败停止；未达标不写Passed | 需只读服务/模型与真人评价授权；无自动候选循环，不回滚索引；结果append-only | Blocked |
| WP-KORG-DESIGN-01 | DESIGN | L1_01 §4.6；L2_01_01 §18；L2_01_00/02 §19 | 已批准资料组织设计；本轮仅补结构单元与补取边界，不重判原完成证据 | - | - | 设计来源、样本边界及资料方案 | 原设计的内审/复核/文档及Git证明维持原范围；v3.2补充须单独评审和本地提交，不冒称新代码或推送 | 只文档；不动服务/模型/索引 | Done |
| WP-KORG-NORMALIZE-01 | NORMALIZE | L2_01_01 §18 DR-KRET-301～303；L2_01_02 §19 DR-KEV-301；L2_01_00 §19 DR-KFLOW-301/302 | 标准化、不可变源版本及结构可信状态记录；不把现有DOCX乱序产物标verified | WP-KORG-DESIGN-01 | - | normalization_v2.py/来源位置Schema/fixture | TEST-KRET-301、hash/span及不可靠顺序反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | 离线基础与测试已提交；真实来源及完整父清单人工核验未闭合；sidecar追加，不迁现索引 | In Progress |
| WP-KORG-CHUNK-01 | CHUNK | L2_01_01 §18 DR-KRET-303/304 | 最小修复受影响DOCX解析顺序，建立结构单元身份、同版本父子关系与连续chunk span | WP-KORG-NORMALIZE-01 | - | parser顺序接缝/chunking_v2.py及段表交错、短长条、表格/否定/例外fixture | TEST-KRET-302；完整单元可按源span恢复且hash一致，跨版本/悬空/乱序失败关闭，不静默遗漏 | 需代码/测试；新版本并存，旧chunker不覆盖；不依赖BGE或线上UAT | Blocked |
| WP-KORG-REPRESENT-01 | REPRESENT | L2_01_01 §18 DR-KRET-305/306 | 独立检索表示及token前检；不把父单元或派生表头当可引用正文 | WP-KORG-NORMALIZE-01 | - | 表示构造/model manifest/tokenizer验证 | TEST-KRET-303；明确实际长度单位/版本，无截断、body/input hash独立；旧未知不回填 | 需代码/配置/本地固定tokenizer资源权限；无推理的纯构造可先完成，与CHUNK并行 | Blocked |
| WP-KORG-COMPARE-01 | COMPARE | L2_01_01 §18 DR-KRET-307；L2_01_02 §19 DR-KEV-304；UAT_02 §6 | 单变量有限对照 | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | - | scope/原文gold/排名损失/四维报告 | fake/类型→人工原文→另授权BGE及只读typed；逐阶段损失、保留题、安全与停止规则 | 需独立索引候选/BGE/只读服务/必要模型预算授权；同源切片与表示分轮；不切线上alias | Blocked |
| WP-KORG-RELEASE-01 | RELEASE | L2_01_00 §19 DR-KFLOW-303；L2_01_02 §19 DR-KEV-302/303 | 选定候选兼容发布 | WP-KORG-COMPARE-01 | - | 策略/Profile一致性、精确旧绑定、回滚与冒烟证据 | 预置收益与不退化条件通过、完整性/安全/关键回归、隔离回滚；无证据不得发布 | 需新索引/受控部署/alias写授权；精确旧绑定与原子回滚；不删旧索引 | Blocked |

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

本计划不新增编号门禁，也不继承旧Gate。包的完成条件和外部操作授权按§5/8控制：设计输入允许技术Ready；COMPOSE以non-live、契约、类型及代码评审完成，不以真实效果作其反向前置；MEASURE与COMPARE仅完成有限测量。COMPARE即使记录测量完成，只要预置质量/完整性/安全/回滚条件未满足，RELEASE仍Blocked，不得仅凭前置Done自动发布。实际启动实施时维护者核实相应独立授权；本轮实际授权见文首；其他工作包不因此自动获得实施或外部调用权限。

§5/12中的VAL是来源设计的验证集合，不是该ID全部阶段均须在每个引用包完成。跨阶段部分按§12分工承接；后续包的真实测量或发布验证不得反向阻塞早期组件包，也不得因组件包Done而被标为已通过。

## 8. 外部资源与事实

| 资源 ID | 工作包 | 资源/事实 | 提供方 | 开始准备 | 必须完成 | 产物/引用 | 缺失影响 |
|---|---|---|---|---|---|---|---|
| EXT-KNEW-001 | WP-KREBUILD-CONTRACT-01 | 代码/测试及有限fixture读取授权；可复现本地环境 | 项目维护者/实施者 | 开始相应包之前 | 首次代码/测试修改前 | 新目标范围及non-live命令 | 无授权不得实施，技术Ready不变 |
| EXT-KNEW-007 | WP-KORG-NORMALIZE-01 | 资料代码/测试及有限fixture读取授权；同一目标可一并授权，不增加审批层 | 项目维护者/实施者 | 开始相应包之前 | 首次代码/测试修改前 | 新目标范围及non-live命令 | 无授权不得实施，技术Ready不变 |
| EXT-KNEW-002 | WP-KREBUILD-COMPOSE-01 | 隔离Spring/Runtime/Java安全测试环境与当前生产root | 维护者/实施者 | 相关实现并行时 | 接线验收前 | 测试版本、无live边界及失败/取消证据 | COMPOSE不能记Done |
| EXT-KNEW-003 | WP-KREBUILD-MEASURE-01 | 12题人工gold/必要来源、版本绑定、只读服务/模型预算及真人评价 | 维护者提供原文与人评；实施者受控执行 | COMPOSE期间可准备 | gold/预算在首调用前；结果人评在测量后、效果结论前 | UAT_02 §5，独立授权 | 停止真实执行/不分类质量达标 |
| EXT-KNEW-004 | WP-KORG-REPRESENT-01 | 固定tokenizer/model manifest及有限离线资源权限 | 模型资源维护者 | NORMALIZE期间可准备 | 表示长度验收前 | DR-KRET-306，版本和单位证明 | 不得猜测token上限或补造旧表示来源 |
| EXT-KNEW-005 | WP-KORG-COMPARE-01 | 有限source/gold、完整竞争池、候选索引/BGE/typed及必要模型预算 | 维护者/实施者 | CHUNK/REPRESENT期间可准备 | 真实实验前 | UAT_02 §6预置协议和独立操作授权 | 不实验、不补跑、不继承旧候选 |
| EXT-KNEW-006 | WP-KORG-RELEASE-01 | 通过的质量/安全证据、精确旧索引与策略绑定、隔离回滚、受控部署/alias授权 | 数据与服务维护者 | COMPARE期间准备 | 候选生效前 | DR-KFLOW-303/DR-KEV-302/303 | 未就绪不发布；原数据/旧索引不删除 |

## 9. Ready 队列与执行建议

| 顺序 | 工作包 | 判定 | 未关闭依赖/门禁 | 选择理由 |
|---|---|---|---|---|
| 1 | WP-KREBUILD-DESIGN-01 | Done | 无技术前置阻塞；后续操作须独立授权 | 来源设计已完成，非新实现 |
| 2 | WP-KREBUILD-CONTRACT-01 | Done | 无；提交及复核见§14.1 | 内部组件已验证；生产接线待COMPOSE |
| 3 | WP-KREBUILD-RETRIEVAL-01 | Done | 无；提交及验证见§14.2 | 新策略独立验证，生产接线待COMPOSE |
| 4 | WP-KREBUILD-EVIDENCE-01 | Ready | 无；CONTRACT已Done | 后续独立实施，不自动启动 |
| 5 | WP-KREBUILD-COMPOSE-01 | Blocked | WP-KREBUILD-EVIDENCE-01 | RETRIEVAL已完成；尚待Evidence/Summary8，未切生产 |
| 6 | WP-KREBUILD-MEASURE-01 | Blocked | WP-KREBUILD-COMPOSE-01 | 等待直接前置；发布还需§7/8证据 |
| 7 | WP-KORG-DESIGN-01 | Done | 无技术前置阻塞；后续操作须独立授权 | 来源设计已完成，非新实现 |
| 8 | WP-KORG-NORMALIZE-01 | In Progress | 真实来源及完整父清单人工核验待补 | 离线版本/来源/结构可信基础已提交；不声称已有切片或父单元读取 |
| 9 | WP-KORG-CHUNK-01 | Blocked | WP-KORG-NORMALIZE-01 | 等待直接前置；发布还需§7/8证据 |
| 10 | WP-KORG-REPRESENT-01 | Blocked | WP-KORG-NORMALIZE-01 | 等待直接前置；发布还需§7/8证据 |
| 11 | WP-KORG-COMPARE-01 | Blocked | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | 等待直接前置；发布还需§7/8证据 |
| 12 | WP-KORG-RELEASE-01 | Blocked | WP-KORG-COMPARE-01 | 等待直接前置；发布还需§7/8证据 |

## 10. 实施交接

以下“允许动作”仅界定后续目标范围，不是对所有工作包的一次性实施授权。源码/文件名若为拟议落点须先引用检查，不覆盖既有同名文件；各包严格沿用来源L2，不扩展公共能力。

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
| RISK-KNEW-001 | WP-KREBUILD-COMPOSE-01 | compatibility | 只切换一个task或保留旧quality强制输入 | 新旧合同错配 | 12/8/minimal整体绑定、当前root及历史隔离验证；禁用或整套相容恢复 | 实施者 |
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
| WP-KREBUILD-EVIDENCE-01 | DR-KEV-201～205 | IMPL-KEV-201～203 | TEST-KEV-201～203 | VAL-KEV-201～203 | Ready |
| WP-KREBUILD-COMPOSE-01 | DR-KFLOW-204/205；DR-KEV-204 | IMPL-KFLOW-202/203；IMPL-KEV-203 | TEST-KFLOW-202/203；TEST-KEV-203；原37风险新版映射 | VAL-KFLOW-202/203；VAL-KEV-202/203；UAT_02 §3 | Blocked |
| WP-KREBUILD-MEASURE-01 | DR-KEV-205；DR-KRET-204 | IMPL-KEV-203；IMPL-KRET-203 | UAT-KM-001～012 | VAL-KEV-203；VAL-KRET-203；UAT_02 §5 | Blocked |
| WP-KORG-DESIGN-01 | 设计输入；REQ-KCORPUS-001～006 | 已批准三L2资料章节，不新增代码 | 原资料设计复核 | 原有限审计与文档验证 | Done |
| WP-KORG-NORMALIZE-01 | DR-KRET-301/302及303的来源版本前提；DR-KEV-301；DR-KFLOW-301/302 | IMPL-KRET-301；IMPL-KEV-301；IMPL-KFLOW-301/302 | TEST-KRET-301；TEST-KEV-301；TEST-KFLOW-301/302 | VAL-KRET-301；VAL-KEV-301；VAL-KFLOW-301/302的离线/来源部分；UAT-KORG-001～004/009仅来源身份、附件关系与fake授权部分 | In Progress |
| WP-KORG-CHUNK-01 | DR-KRET-303/304；DR-KEV-302/303 | IMPL-KRET-302；IMPL-KEV-302 | TEST-KRET-302；TEST-KEV-302 | VAL-KRET-302；VAL-KEV-302的结构/span部分；UAT-KORG-004的unit父子关系、005/006/008 | Blocked |
| WP-KORG-REPRESENT-01 | DR-KRET-305/306；DR-KEV-302/303 | IMPL-KRET-303；IMPL-KEV-302 | TEST-KRET-303；TEST-KEV-302 | VAL-KRET-303；VAL-KEV-302；UAT-KORG-003/007/008 | Blocked |
| WP-KORG-COMPARE-01 | DR-KRET-307；DR-KEV-304 | IMPL-KRET-304；IMPL-KEV-303 | TEST-KRET-304；TEST-KEV-303；UAT-KORG-001～012 | VAL-KRET-304；VAL-KEV-303；UAT_02 §6 | Blocked |
| WP-KORG-RELEASE-01 | DR-KFLOW-303；DR-KRET-307；DR-KEV-302/303 | IMPL-KFLOW-303；IMPL-KRET-304；IMPL-KEV-302 | TEST-KFLOW-303；TEST-KRET-304；TEST-KEV-302 | VAL-KFLOW-303；VAL-KRET-304；VAL-KEV-302；UAT-KORG-012 | Blocked |

跨阶段验证按以下责任切片执行，不新增VAL、工作包或门禁。实际验证记录注明已执行部分、结果及未执行部分的承接包；不得将部分通过写成整个VAL或整套UAT通过。

| 本包/相关验证集合 | 本包完成所需部分 | 后续承接，不作为本包反向前置 |
|---|---|---|
| RETRIEVAL：VAL-KFLOW-202、VAL-KRET-201～203；EVIDENCE：VAL-KEV-201～203 | 新组件的定向单元/契约、fake集成、类型及安全反例；含原问/数量/失败优先级、Evidence/引用和离线计分反例 | current-root/Spring及成对接线回归由COMPOSE承担；真实召回、摘要效果和人工评价由MEASURE承担 |
| COMPOSE：VAL-KFLOW-202/203、VAL-KEV-202/203、UAT_02 §3 | 目标生产对象图的non-live接线、Spring/Java安全、37风险新版证据及相关历史/Business防回退；保留§5代码评审完成条件 | VAL-KEV-203的有限真实/人工评价由MEASURE承担；non-live通过不证明真实效果 |
| NORMALIZE：VAL-KRET-301、VAL-KEV-301、VAL-KFLOW-301/302；CHUNK：VAL-KRET-302、VAL-KEV-302 | 各自有限fixture的来源/字段/关系或结构/span验证；CHUNK另证DOCX源顺序、unit完整性与chunk集合覆盖分离、保守/复核分流及人工结构核对；对应契约/fake安全反例，仅验证各自变更范围 | UAT-KORG-009的真实typed部分及VAL-KEV-302的候选只读证明由COMPARE承担，发布绑定验证由RELEASE承担 |
| REPRESENT：VAL-KRET-303、VAL-KEV-302 | 纯表示构造、固定tokenizer长度/版本、无截断及派生上下文不能成为quote的unit/contract/fake验证 | VAL-KRET-303的BGE对照及VAL-KEV-302的真实typed部分由COMPARE承担；不以推理服务就绪作为纯构造包完成条件 |
| COMPARE：VAL-KRET-304、VAL-KEV-303、UAT_02 §6；RELEASE：VAL-KFLOW-303、VAL-KRET-304、UAT-KORG-012 | COMPARE完成预先冻结协议内的fake、人工原文及另授权BGE/隔离typed对照；涉及回答质量时另满足模型/人工评价条件，未评维度明确记录 | 线上alias/部署、选定候选发布绑定及发布回滚由RELEASE承担；COMPARE的fake回滚不代替RELEASE真实发布验证，测量完成不自动满足发布质量条件 |

## 13. 自检记录

文档审查与实施验证分开；本节只维护新计划实际文档复核结论。2026-09-14计划迁移的三轮内审及两轮同一执行者分阶段正式复核完成，最终S0/S1/未处理S2均0；记录由当次[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)集中承载；不得把源设计旧轮次写成本轮轮次。

2026-09-15限定澄清完成一轮自检、措辞补齐及复核（同一执行者，非整套设计重新评审）：REV-P3-001的跨阶段VAL分工、REV-P3-002的资料缺口/安全停止边界、REV-P3-003的四处L2章节指向均已处理。P3及三份L2严格校验零错误/警告；12包/12直接边、状态、37+12+12用例、阈值/预算及设计追踪编号保持不变，36个本地链接可解析。仅五份当前文档本地修改，历史资产/代码/测试/配置未改；未执行实现、UAT或Git提交推送。

2026-09-24结构单元补充执行两轮内审：第一轮核对文档类型、解析顺序、unit/content版本和可恢复span，修正根单元可无`parentUnitId`及版本身份；第二轮核对在线授权/引用、unit完整性与chunk覆盖、保守切片分流、P3直接依赖及UAT边界，修正缺块不得发布和解析异常必须复核的条件。随后由同一Codex任务内未参与起草的只读执行单元进行分层/跨层复评，目标七文档范围内S0=0、S1=0、未处理S2=0；该复评不冒充外部人员评审，也不证明新设计已实施。L0_00第78行及L1_00第13、94～96行中的Knowledge文档版本引用仍为v3.1，属本轮未授权文档的元数据欠账，接受为范围外S2并明确需另获这两份文档的引用修订授权；不得声称全套跨层版本引用已完全同步。

## 14. 当前结论

当前Done=4（两项来源设计、CONTRACT、RETRIEVAL）；Ready=1（EVIDENCE）；Blocked=6；In Progress=1（NORMALIZE）。NORMALIZE离线代码与测试已完成，但真实来源及完整父清单人工核验未闭合；在其完成前，`WP-KORG-CHUNK-01`仍Blocked。在线`WP-KREBUILD-EVIDENCE-01`保持Ready、可独立推进。本轮不切生产root、不执行新UAT。

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

Python3.12隔离环境执行`python -B -m pytest -p no:cacheprovider --basetemp <唯一工作区临时目录> --tb=short tests -q`，`knowledge-corpus-tools`全包306项通过；直接`tests/test_normalization_v2.py`为15项通过。`mypy --strict src/knowledge_corpus_tools/normalization_v2.py`与`compileall -q -f`通过。对一份既有官方附件执行只读抽样：本地文件SHA-256、旧asset manifest及旧parsed record hash相同，父文档ID一致；这是有限历史资产交叉核对，不等于新v2全量来源清单或当前官网复核。尚须对冻结来源记录、完整父清单及结构证明作人工核验，关闭`VAL-KRET-301`后才能将本包标Done、解除`DEP-KORG-002`。未知`aging/channel`映射保持unknown，不补造时效或文档类型。本轮没有模型调用、索引/alias写入或在线父单元补取。

先前§13自检记录中的L0_00、L1_00旧版引用欠账，已在另获明确授权后由本地提交`c7f69edc37e41fc4a087e6b24839740db3e664a8`精确修正五处元数据；原复评当时的范围结论保留，不冒称该复评已覆盖后续修改。
