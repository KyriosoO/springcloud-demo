# [P3_01] Knowledge 新设计实施计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档标识 | P3_01 |
| 文档类型 | 设计驱动实施计划 |
| 当前版本 | v3.0 |
| 文档状态 | Reviewed |
| 日期 | 2026-09-14 |
| 目标计划路径 | docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md |
| 适用范围 | 已批准Knowledge在线重建、资料组织与检索表示两条主线 |
| 非范围 | Business重新设计、图谱、记忆、多轮、旧候选推进 |
| 权威顺序 | 用户范围 → 仓库规则 → REQ/L0/L1/公共契约 → Knowledge L2 → 当前实现证据 → 本计划 |
| 实施授权 | 本轮只迁移文档；Ready 不等于实施授权，不授予代码、服务、数据、索引或推理权限 |
| 计划执行状态 | 仅两项来源设计Done；其余新实现/测量/发布未执行 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-09-14 | 全文 | 旧综合计划退出当前推进权威 | 新文档首版v3.0，承接已批准设计，不继承旧计划通过结论、Gate或预算 |

## 3. 来源清单与当前基线

| 资源 | 角色 | 层级 | 状态/版本 | 权威范围 | 是否读取 | 置信度 |
|---|---|---|---|---|---|---|
| [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) | 目标架构 | L1 | v3.1 / Approved | §4.5/4.6最小链路与资料组织 | 是 | 已批准设计，不证明实施 |
| [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) | 流程详细合同 | L2 | v3.1 / Approved | §8、§19，DR-KFLOW-201～205/301～303 | 是 | 实施权威 |
| [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) | 检索与资料合同 | L2 | v3.1 / Approved | §9、§18，DR-KRET-201～204/301～307 | 是 | 实施权威 |
| [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) | Evidence/回答合同 | L2 | v3.1 / Approved | §9、§19，DR-KEV-201～205/301～304 | 是 | 实施权威 |
| [UAT_02](UAT_02_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 当前验收 | 计划 | v3.0 / Reviewed | 新功能/安全/召回/回答及资料验证 | 是 | 未执行 |
| [UAT_00](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | Business维护基线 | 验收 | v3.1 / Reviewed | 固定35风险与Employee15类扩展，原证据范围 | 是 | 历史等价复用，不是本轮UAT |
| [旧P3_00快照](历史文档/2026-09-14-knowledge-plan-handoff/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) | 承接与历史事实 | 归档 | v3.0 / 原状态保留 | §21/22新设计交接，其余旧执行不继承 | 是 | 冻结提交/原资产可追溯 |

起始代码提交为`8ae32c50a567850c67b4d1e726304934ab07162c`；源码事实为11/7/quality-v3，默认Knowledge disabled。目标12/8/knowledge-minimal-v1及资料新版本尚未实施。仓库配置不是部署证明；本轮不启动服务或读取模型密钥。历史审计与运行状态见[迁移清单](历史文档/2026-09-14-knowledge-plan-handoff/README.md)，不复制到新计划作为新验证结果。

## 4. 计划原则与范围

两条主线分别由三份Knowledge L2定义；本计划不新增DR或修改算法、公共DTO、授权及失败语义。旧ROADMAP不再是前置，不新增替代路线图。原文、安全组件和阶段A成果保留职责；内部旧实验的清理只在后续授权COMPOSE中确认调用方、冻结源可追溯后进行。

Online：合同 → 检索/证据并行 → 成对接线 → 测量。
Corpus：标准化 → 切片/表示并行 → 对照 → 受控发布。
两条主线没有彼此真实UAT前置；COMPARE需选择一套冻结在线实现，可用现有相容实现，不要求先完成MEASURE。新公共父读取、时效/分类DTO或权限变更不是当前隐含交付。

## 5. 工作包清单

来源设计Done承接原审查范围，不表示本轮重做设计；验证列为后续完成条件，除来源设计外均未执行。

| 工作包 ID | 名称 | 来源设计 | 范围 | 直接依赖 | 入口门禁 | 交付物 | 验证 | 回滚边界 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| WP-KREBUILD-DESIGN-01 | DESIGN | L2_01_00 §8 DR-KFLOW-201～205 | 已批准在线设计/分类决策；不重新设计 | - | - | 设计来源与实施边界 | 内审≤3、分层/跨层正式复核、结构/追踪/DAG/范围检查通过；文档提交推送 | 只文档diff，不回滚历史；无服务/模型 | Done |
| WP-KREBUILD-CONTRACT-01 | CONTRACT | L2_01_00 §8 DR-KFLOW-201/202 | 内部意图合同及task12 | WP-KREBUILD-DESIGN-01 | - | 内部schema3/精确decoder/task | TEST-KFLOW-201；Model schema子集、错误/取消/敏感0outbound；mypy/compileall；代码对照复核 | 后续代码授权；新增独立类型/task，暂不切root | Ready |
| WP-KREBUILD-RETRIEVAL-01 | RETRIEVAL | L2_01_00 §8 DR-KFLOW-203；L2_01_01 §9 DR-KRET-201～204 | 原Q双路、域内融合/重排与有界配置 | WP-KREBUILD-CONTRACT-01 | - | planning/semantic_planner/ranking/config最小策略 | TEST/VAL-KRET-201～203，数量/顺序/Q一致、部分/全失败、同域拒绝；无网络fake | 本地fake；独立strategy，旧prod不变；无索引写入 | Blocked |
| WP-KREBUILD-EVIDENCE-01 | EVIDENCE | L2_01_02 §9 DR-KEV-201～205 | minimal Evidence和Summary8 | WP-KREBUILD-CONTRACT-01 | - | mode input、evidence selector、serializer、summary_task_v8.py/decoder | TEST/VAL-KEV-201～203；完整性先验证、预算、deny0、引用/未知coverage拒绝；模型fake | 与RETRIEVAL可并行；旧Prompt/serializer不改 | Blocked |
| WP-KREBUILD-COMPOSE-01 | COMPOSE | L2_01_00 §8 DR-KFLOW-204/205；L2_01_02 §9 | 唯一root迁移与历史隔离 | WP-KREBUILD-RETRIEVAL-01、WP-KREBUILD-EVIDENCE-01 | - | bootstrap/capability/任务目录；受影响37风险新版验证 | current-root、Spring E2E、37功能重新逐case、Business35关键防退、Java安全/类型/non-live、正式代码评审；Blocker/Major0 | 后续代码/测试权限；不用live作基础代码包完成前置；禁用Knowledge或整套恢复相容发布 | Blocked |
| WP-KREBUILD-MEASURE-01 | MEASURE | L2_01_02 §9 DR-KEV-205；UAT_02 §5 | 固定12题及一次独立测量 | WP-KREBUILD-COMPOSE-01 | - | 新版本问题/来源/预算绑定、有限结果及真人评价 | 人工gold/语料就绪、新独立授权、版本绑定及预算预检；按预置判据分类，真实失败停止；未达标不写Passed | 需只读服务/模型与真人评价授权；无自动候选循环，不回滚索引；结果append-only | Blocked |
| WP-KORG-DESIGN-01 | DESIGN | L1_01 §4.6；L2_01_01 §18；L2_01_00/02 §19 | 已批准资料组织设计；有限审计只作事实基线 | - | - | 设计来源、样本边界及资料方案 | 三轮内审、两轮正式复核、文档验证通过；以包含本节的目标提交推送成功为Git收口证明 | 只文档；不动服务/模型/索引 | Done |
| WP-KORG-NORMALIZE-01 | NORMALIZE | L2_01_01 §18 DR-KRET-301～303；L2_01_02 §19 DR-KEV-301；L2_01_00 §19 DR-KFLOW-301/302 | 标准化与可追溯sidecar | WP-KORG-DESIGN-01 | - | normalization_v2.py/来源位置Schema/fixture | TEST-KRET-301、hash/span反例、来源人工核对；纯单元/契约/mypy/compileall；旧源保留 | 仅技术Ready，需代码/测试及有限资产读取新授权；sidecar追加，不迁现索引 | Ready |
| WP-KORG-CHUNK-01 | CHUNK | L2_01_01 §18 DR-KRET-304 | 结构边界与连续span回放 | WP-KORG-NORMALIZE-01 | - | chunking_v2.py及表格/否定/例外fixture | TEST-KRET-302；条件/否定/表格/短块/长条款均可追溯；不静默遗漏 | 需代码/测试；新版本并存，旧chunker不覆盖；不依赖BGE或线上UAT | Blocked |
| WP-KORG-REPRESENT-01 | REPRESENT | L2_01_01 §18 DR-KRET-305/306 | 独立检索表示及token前检 | WP-KORG-NORMALIZE-01 | - | 表示构造/model manifest/tokenizer验证 | TEST-KRET-303；明确实际长度单位/版本，无截断；旧未知不回填 | 需代码/配置/本地固定tokenizer资源权限；无推理的纯构造可先完成，与CHUNK并行 | Blocked |
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

本计划不新增编号门禁，也不继承旧Gate。包的完成条件和外部操作授权按§5/8控制：设计输入允许技术Ready；COMPOSE以non-live、契约、类型及代码评审完成，不以真实效果作其反向前置；MEASURE与COMPARE仅完成有限测量。COMPARE即使记录测量完成，只要预置质量/完整性/安全/回滚条件未满足，RELEASE仍Blocked，不得仅凭前置Done自动发布。实际启动实施时维护者核实相应独立授权；本轮文档权限不包含任何实施权限。

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
| 2 | WP-KREBUILD-CONTRACT-01 | Ready | 无技术前置阻塞；后续操作须独立授权 | 可单独启动的最小实现切片 |
| 3 | WP-KREBUILD-RETRIEVAL-01 | Blocked | WP-KREBUILD-CONTRACT-01 | 等待直接前置；发布还需§7/8证据 |
| 4 | WP-KREBUILD-EVIDENCE-01 | Blocked | WP-KREBUILD-CONTRACT-01 | 等待直接前置；发布还需§7/8证据 |
| 5 | WP-KREBUILD-COMPOSE-01 | Blocked | WP-KREBUILD-RETRIEVAL-01、WP-KREBUILD-EVIDENCE-01 | 等待直接前置；发布还需§7/8证据 |
| 6 | WP-KREBUILD-MEASURE-01 | Blocked | WP-KREBUILD-COMPOSE-01 | 等待直接前置；发布还需§7/8证据 |
| 7 | WP-KORG-DESIGN-01 | Done | 无技术前置阻塞；后续操作须独立授权 | 来源设计已完成，非新实现 |
| 8 | WP-KORG-NORMALIZE-01 | Ready | 无技术前置阻塞；后续操作须独立授权 | 可单独启动的最小实现切片 |
| 9 | WP-KORG-CHUNK-01 | Blocked | WP-KORG-NORMALIZE-01 | 等待直接前置；发布还需§7/8证据 |
| 10 | WP-KORG-REPRESENT-01 | Blocked | WP-KORG-NORMALIZE-01 | 等待直接前置；发布还需§7/8证据 |
| 11 | WP-KORG-COMPARE-01 | Blocked | WP-KORG-CHUNK-01、WP-KORG-REPRESENT-01 | 等待直接前置；发布还需§7/8证据 |
| 12 | WP-KORG-RELEASE-01 | Blocked | WP-KORG-COMPARE-01 | 等待直接前置；发布还需§7/8证据 |

## 10. 实施交接

以下“允许动作”仅界定后续目标范围，不是本轮授权。源码/文件名若为拟议落点须先引用检查，不覆盖既有同名文件；各包严格沿用来源L2，不扩展公共能力。

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
| WP-KORG-CHUNK-01 | 结构边界与连续span回放 | 无第二链路/无越权/不覆盖历史；真实外部资源仅独立授权后 | 既有离线语料chunk模块及tests，新版本并存 | L2_01_01 §18 DR-KRET-304 | TEST-KRET-302 | 不继承旧Gate；见§7/8 | implement-from-detailed-design；code-review-against-docs |
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
| WP-KREBUILD-CONTRACT-01 | DR-KFLOW-201/202 | IMPL-KFLOW-201 | TEST-KFLOW-201 | VAL-KFLOW-201 | Ready |
| WP-KREBUILD-RETRIEVAL-01 | DR-KFLOW-203；DR-KRET-201～204 | IMPL-KFLOW-202；IMPL-KRET-201～203 | TEST-KFLOW-202；TEST-KRET-201～203 | VAL-KFLOW-202；VAL-KRET-201～203 | Blocked |
| WP-KREBUILD-EVIDENCE-01 | DR-KEV-201～205 | IMPL-KEV-201～203 | TEST-KEV-201～203 | VAL-KEV-201～203 | Blocked |
| WP-KREBUILD-COMPOSE-01 | DR-KFLOW-204/205；DR-KEV-204 | IMPL-KFLOW-202/203；IMPL-KEV-203 | TEST-KFLOW-202/203；TEST-KEV-203；原37风险新版映射 | VAL-KFLOW-202/203；VAL-KEV-202/203；UAT_02 §3 | Blocked |
| WP-KREBUILD-MEASURE-01 | DR-KEV-205；DR-KRET-204 | IMPL-KEV-203；IMPL-KRET-203 | UAT-KM-001～012 | VAL-KEV-203；VAL-KRET-203；UAT_02 §5 | Blocked |
| WP-KORG-DESIGN-01 | 设计输入；REQ-KCORPUS-001～006 | 已批准三L2资料章节，不新增代码 | 原资料设计复核 | 原有限审计与文档验证 | Done |
| WP-KORG-NORMALIZE-01 | DR-KRET-301～303；DR-KEV-301；DR-KFLOW-301/302 | IMPL-KRET-301/302；IMPL-KEV-301；IMPL-KFLOW-301/302 | TEST-KRET-301/302；TEST-KEV-301；TEST-KFLOW-301/302 | VAL-KRET-301；VAL-KEV-301；VAL-KFLOW-301/302；UAT-KORG-001～004/009 | Ready |
| WP-KORG-CHUNK-01 | DR-KRET-303/304；DR-KEV-302/303 | IMPL-KRET-302；IMPL-KEV-302 | TEST-KRET-302；TEST-KEV-302 | VAL-KRET-302；VAL-KEV-302；UAT-KORG-005/006/008 | Blocked |
| WP-KORG-REPRESENT-01 | DR-KRET-305/306；DR-KEV-302/303 | IMPL-KRET-303；IMPL-KEV-302 | TEST-KRET-303；TEST-KEV-302 | VAL-KRET-303；VAL-KEV-302；UAT-KORG-003/007/008 | Blocked |
| WP-KORG-COMPARE-01 | DR-KRET-307；DR-KEV-304 | IMPL-KRET-304；IMPL-KEV-303 | TEST-KRET-304；TEST-KEV-303；UAT-KORG-001～012 | VAL-KRET-304；VAL-KEV-303；UAT_02 §6 | Blocked |
| WP-KORG-RELEASE-01 | DR-KFLOW-303；DR-KRET-307；DR-KEV-302/303 | IMPL-KFLOW-303；IMPL-KRET-304；IMPL-KEV-302 | TEST-KFLOW-303；TEST-KRET-304；TEST-KEV-302 | VAL-KFLOW-303；VAL-KRET-304；VAL-KEV-302；UAT-KORG-012 | Blocked |

## 13. 自检记录

文档审查与实施验证分开；本节只维护新计划实际文档复核结论。本轮三轮内审及两轮同一执行者分阶段正式复核完成，最终S0/S1/未处理S2均0；记录由本次[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)集中承载；不得把源设计旧轮次写成本轮轮次。

## 14. 当前结论

来源设计Done=2；Ready=2（CONTRACT、NORMALIZE）；Blocked=8；In Progress=0。只完成文档承接，不实施新代码，不测量效果，不发布数据。技术上可从任一Ready主线申请新的实施目标；本目标提交推送后停止。
