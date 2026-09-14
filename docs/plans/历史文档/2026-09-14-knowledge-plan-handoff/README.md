# 2026-09-14 旧计划归档与Knowledge新计划承接

## 1. 起始基线与归档规则

起始提交：`8ae32c50a567850c67b4d1e726304934ab07162c`；分支codex，与当时origin/codex一致，工作树干净。当前四份计划均v3.0。已有2026-09-14-unified-v3-baseline副本为更早版本，hash均不同，因此本目录仅新增四份当前精确快照。

归档只代表起始提交内容，不是当前设计/实施/验收权威。归档内部版本、状态、相对链接逐字保留；其链接应按原路径在起始提交解析，必要时使用`git show <冻结提交>:<原路径>`，不能按归档所在目录误判失效。更早冻结运行继续使用各自HEAD，而不是统一改用本次HEAD。

| 原路径 | 原版本 | 本目录归档 | SHA-256 | 整理后定位 |
|---|---|---|---|---|
| docs/plans/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md | v3.0 | [P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md](P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) | 8f8b96177bf3da69cfbbfdd53410eae2c1f76f1bd77fe117272f00bc5824144d | 退出当前权威；正文仅归档 |
| docs/plans/ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md | v3.0 | [ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md](ROADMAP_01_SINGLE_AGENT_KNOWLEDGE_CORPUS_RETRIEVAL_GRAPH_EVOLUTION_PLAN.md) | a7245f616b6e091e21bba244d7f9646f9ed4178d24f1bc1fe209d3881a348a70 | 退出当前权威；正文仅归档 |
| docs/plans/UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md | v3.0 | [UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) | d7ed101074be84ee5cc6dcc5c30366f58df7f545075a5b8b5aadeda532f5cec9 | 当前UAT_00 v3.1保留维护基线 |
| docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md | v3.0 | [UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md](UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | aeda6c3683d7c7b1175ab4391af767c91d8d28bf116b35d6b07002047a899b40 | 退出当前权威；正文仅归档 |

快照由原文件逐字复制且SHA-256校验；不覆盖已有历史，不移动任何运行manifest/authorization/consumed/journal/result/evidence。新实施与验收计划首版v3.0；只发生实际引用/定位修改的现行文档独立升v3.1。

## 2. 内容承接与唯一入口

| 原内容 | 有效性/原状态 | 处理与新位置 | 证据边界 |
|---|---|---|---|
| ROADMAP_01旧阶段A/B/C/D安排 | 阶段A原成果保留；旧B目标取消；图谱等未实施 | 完整归档，无替代ROADMAP | 不作为新计划前置，不取消尚未决策事项 |
| P3_00 §21在线重建 | 已批准设计，6包2类新实施状态 | [P3_01](../../P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md) §3～12 | DESIGN Done，CONTRACT Ready，余4Blocked；非实施授权 |
| P3_00 §22资料组织 | 已批准设计及一次有限审计 | P3_01 §3～12；审计事实留原快照/更早原包 | DESIGN Done，NORMALIZE Ready，余4Blocked；无收益实测 |
| P3_00其余完成/失败/延期/取消 | 原终态不改判 | 本节下表及完整归档 | 非新目标完成证明 |
| UAT_01 §5的37个风险身份 | 原冻结合同的功能证明 | [UAT_02](../../UAT_02_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) §3 | 新版本全部Not executed；RW/EV按批准新合同映射 |
| UAT_01 §15在线四维方法 | 已批准、未执行 | UAT_02 §5；12个UAT-KM编号及原阈值保留 | 不继承旧通过或预算 |
| UAT_01 §16资料验收方法 | 已批准、未执行 | UAT_02 §6；12个UAT-KORG编号保留 | 数据/功能/安全/召回/回答分开，发布非自动 |
| UAT_01原功能/P5/阶段A/B/人工运行 | 只对各自冻结范围有效 | 完整归档及原运行资产 | 有效/无效和最新执行分开，不重算不复用授权 |
| UAT_00固定35风险及Employee15类扩展 | 原证明范围保留 | [UAT_00](../../UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md) v3.1维护基线 | 18真实+17等价风险；扩展独立，不称本轮UAT |

原P3主表73包：55 Done、4 Deferred、2 Ready、12 Blocked。承接12包后，新P3为2 Done、2 Ready、8 Blocked；剩余61包全部列明，不因归档消失。原登记中未发现非Knowledge未完成项；这不是全仓状态审计。下表是迁移时的静态身份映射，不是新的执行总账。

| 原工作包ID | 原职责 | 原状态 | 处置 |
|---|---|---|---|
| WP-BQ-FILTER-CONTRACT-02 | 公共 filters QueryPlan 合同 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-FIELD-CONFIG-02 | 统一字段级 JSON 配置 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-MODEL-CATALOG-02 | filters 模型目录与 Prompt | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-EMP-SEARCH-ADAPTER-02 | Employee 条件搜索 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-EMP-SEMANTIC-ADAPTER-02 | Employee 语义搜索 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-EMP-ES-AUTH-02 | Employee ES 最终读取授权 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-TXN-SEARCH-EXT-02 | Transaction Date/金额/分页扩展 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-TXN-DATE-WIRE-COMPAT-03 | Transaction 生产 Date 响应兼容 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-RUNTIME-CUTOVER-02 | 三动作生产组合根切换 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-EMP-DETAIL-RETIRE-02 | Employee detail 退役核实 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-NONLIVE-E2E-02 | 三动作 non-live E2E | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-CONTROLLED-LIVE-02 | 受控模型与业务联调 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-TXN-TEXT-POLICY-COMPAT-03 | Transaction 按 operator 区分文本安全策略 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-MODEL-INTENT-COMPLETENESS-03 | Model 完整意图与不可表达组合收紧 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-UAT-HANDOFF-02 | 正式 UAT 环境与交接 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-COMPLETION-CLOSURE-04 | 当前 35 用例证据与实现收口 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-K-BASELINE-03 | Knowledge 设计与 UAT 基线 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-RUNTIME-WIRING-03 | Knowledge 默认关闭生产接线 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-SPRING-NONLIVE-E2E-03 | Spring→Runtime Knowledge non-live E2E | Done | 原完成范围归档；不是新设计通过 |
| WP-K-FUNCTIONAL-UAT-03 | Knowledge 功能 UAT | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-DIAG-03 | candidate-04 只读效果诊断 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-OPT-03 | 最小效果改进 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-CANDIDATE-05-PREP | 新效果候选非 live 准备 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-LIVE-05 | 新效果 UAT | Done | 原完成范围归档；不是新设计通过 |
| WP-K-CLOSURE-03 | Knowledge 正式代码评审与状态收口 | Done | 原完成范围归档；不是新设计通过 |
| WP-DOC-CONSISTENCY-06 | 七项文档事实与依赖纠偏 | Done | 原完成范围归档；不是新设计通过 |
| WP-PY-REGRESSION-REPRO-06 | Python 正式全量入口可复现 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-DIAG-06 | candidate-05 只读效果根因复核 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-OPT-06 | Knowledge 最小效果优化 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-CANDIDATE-06-PREP | 新效果候选非 live 冻结 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-LIVE-06 | candidate-06 效果 UAT | Deferred | 旧执行已终止，未完成事实保留，不恢复预算 |
| WP-K-EFFECT-HARNESS-CLOSURE-07 | candidate-06 历史闭环与 Harness 修复 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-CANDIDATE-07-PREP | 全新效果候选 non-live 冻结 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-EFFECT-LIVE-07 | 全新候选效果 UAT | Deferred | 旧执行已终止，未完成事实保留，不恢复预算 |
| WP-K-EFFECT-PREFLIGHT-CLOSURE-08 | 效果 Harness 状态合同修复 | Done | 原完成范围归档；不是新设计通过 |
| WP-DESIGN-IMPLEMENTATION-AUDIT-08 | 全部当前设计落实审计 | Done | 原完成范围归档；不是新设计通过 |
| WP-SEVEN-ITEM-CLOSURE-06 | 最终验证与评审收口 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-UAT-TRACE-CLOSURE-09 | Knowledge UAT 追踪资产纠偏与有限收口 | Done | 原完成范围归档；不是新设计通过 |
| WP-K-REWRITE-SCHEMA-11 | Knowledge Rewrite 精确输出合同与验证台展示 | Done | 原完成范围归档；不是新设计通过 |
| WP-EMP-NL-DESIGN-10 | Employee 自然语言扩展方案与设计 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-BQ-MULTIVALUE-CONTRACT-10 | Business 多值 QueryPlan 公共合同 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-EMP-NL-QUERY-10 | Employee 自然语言查询实现 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-EMP-NL-UAT-10 | Employee 自然语言扩展受控 UAT | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-EMP-NL-CLOSURE-10 | Employee 自然语言扩展最终收口 | Done | 原完成范围归档；Business维护验收由UAT_00保留 |
| WP-KCORPUS-AUDIT-01 | 正文及附件只读审计 | Done | 原完成范围归档；不是新设计通过 |
| WP-KCORPUS-DESIGN-01 | 阶段 A 语料生命周期设计 | Done | 原完成范围归档；不是新设计通过 |
| WP-KCORPUS-PIPELINE-01 | 版本化语料处理流水线 | Done | 原完成范围归档；不是新设计通过 |
| WP-KCORPUS-INDEX-01 | 候选索引与策略/Profile 快照 | Done | 原完成范围归档；不是新设计通过 |
| WP-KCORPUS-UAT-01 | 阶段 A 直接检索 UAT | Done | 原完成范围归档；不是新设计通过 |
| WP-KCORPUS-RELEASE-01 | alias 发布、回滚演练与收口 | Done | 原完成范围归档；不是新设计通过 |
| WP-KRETRIEVAL-DIAG-01 | 阶段 B 根因诊断 | Done | 原完成范围归档；不是新设计通过 |
| WP-KRETRIEVAL-DESIGN-01 | 阶段 B 设计 | Done | 原完成范围归档；不是新设计通过 |
| WP-KRETRIEVAL-IMPLEMENT-01 | 阶段 B 实施 | Done | 原完成范围归档；不是新设计通过 |
| WP-KRETRIEVAL-NONLIVE-01 | 阶段 B 回归 | Done | 原完成范围归档；不是新设计通过 |
| WP-KRETRIEVAL-UAT-01 | 阶段 B 专项 UAT | Deferred | 旧执行已终止，未完成事实保留，不恢复预算 |
| WP-KRETRIEVAL-QUALITY-01 | 阶段 B 质量收口 | Deferred | 旧执行已终止，未完成事实保留，不恢复预算 |
| WP-KREBUILD-DESIGN-01 | DESIGN | Done | 迁入P3_01 §5，原ID与状态保留 |
| WP-KREBUILD-CONTRACT-01 | CONTRACT | Ready | 迁入P3_01 §5，原ID与状态保留 |
| WP-KREBUILD-RETRIEVAL-01 | RETRIEVAL | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KREBUILD-EVIDENCE-01 | EVIDENCE | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KREBUILD-COMPOSE-01 | COMPOSE | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KREBUILD-MEASURE-01 | MEASURE | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KORG-DESIGN-01 | DESIGN | Done | 迁入P3_01 §5，原ID与状态保留 |
| WP-KORG-NORMALIZE-01 | NORMALIZE | Ready | 迁入P3_01 §5，原ID与状态保留 |
| WP-KORG-CHUNK-01 | CHUNK | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KORG-REPRESENT-01 | REPRESENT | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KORG-COMPARE-01 | COMPARE | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KORG-RELEASE-01 | RELEASE | Blocked | 迁入P3_01 §5，原ID与状态保留 |
| WP-KCORPUS-ATTACHMENT-01 | 正文及附件版本化补齐 | Done | 原完成范围归档；不是新设计通过 |
| WP-KGRAPH-CONTRACT-01 | 轻量图谱合同实现与只读接口 | Blocked | 历史Blocked；退出当前关键路径，未来待决策，不取消不完成 |
| WP-KGRAPH-BUILD-01 | 版本化关系数据构建 | Blocked | 历史Blocked；退出当前关键路径，未来待决策，不取消不完成 |
| WP-KHYBRID-RETRIEVAL-01 | 图谱导航与原文检索联合 | Blocked | 历史Blocked；退出当前关键路径，未来待决策，不取消不完成 |
| WP-KNOWLEDGE-UAT-02 | 语料、检索与图谱联合 UAT | Blocked | 历史Blocked；退出当前关键路径，未来待决策，不取消不完成 |


## 3. 机器追踪兼容决策

- Business JSON及loader保留UAT_00 v1.24原验证依据；Knowledge JSON及loader保留UAT_01 v1.21及原任务证明范围。它们不是新文档版本号锁步器。
- 六份representative run/human run历史测试用`git show <各自HEAD>:docs/plans/UAT_01_...`验证原字节，不读取当前计划作历史真值。
- 旧representative/diagnostic的prepare工具仍含旧UAT路径，作用是旧批次manifest收集；旧目标已取消，本目标不恢复其prepare/execute。它们不是当前计划读取接口，不能作为保留旧权威正文的理由。本轮不修改这些代码，也不运行旧付费launcher。
- 当前新计划不复用旧JSON或历史运行Passed；后续COMPOSE/MEASURE才在另行授权下建立新追踪版本。
- 全仓引用检查后，当前文档引用按当前/历史/Business用途分别迁移。没有确认的现行硬读取依赖，旧ROADMAP/P3/UAT_01路径不保留占位正文；新旧入口由本清单和ARCHITECTURE说明。
- 兼容测试仅验证本次迁移相关的原证据可追溯和loader合同，不证明新方案已经实现或UAT通过。

## 4. 文档评审记录

范围为本次归档、计划承接及直接引用/状态迁移；业务、权限、模型输出、检索与索引合同不重新设计。以下均为同一执行者分阶段复核，不是外部独立人员评审。

| 阶段 | 检查与实际发现 | 处理结果 |
|---|---|---|
| 内审1：内容与状态 | 旧主表73包中除了12个承接包，还有4个Deferred旧运行及4个Blocked图谱/联合验收；不能归档后清空 | 完整73项迁移映射；旧终态不改判，图谱未来待决策；Business另保留维护入口 |
| 内审2：权威与追踪 | 37风险的RW/EV旧任务语义不能照抄为12/8通过；旧UAT路径存在历史代码引用；当前文档显式版本引用有传递依赖 | 按已批准L2映射新预期、全部Not executed；核实历史测试git show冻结源；取消工具不恢复；只同步显式引用所需版本 |
| 内审3：DAG与验证 | 严格计划校验要求固定Ready标题、明确Ready不等于授权、空门禁表和资源行单工作包；普通Python入口未安装源码包 | 最小格式修复，无新增实际门禁/审批；同一解释器进程内显式加入src后112项兼容检查通过，不安装依赖、不改配置 |
| 正式复核1：分层与跨层 | S0=0、S1=0，3项S2：P3稳定IMPL/TEST/VAL及资料接缝DR追踪不够明确；Evidence失败“模型0”未区分已执行前置；人评完成时点表述含混 | 补齐28个目标DR到包和原L2追踪ID；Summary0与前置计数分开；gold/预算在调用前，人评在运行后结论前 |
| 正式复核2：修复后重查 | 复核承接状态/28DR、原设计ID与Business合同保全、单向12边、三项退出及唯一新入口、历史源/JSON不变 | S0=0、S1=0、未处理S2=0；限定文档迁移通过。新计划Reviewed，当前设计引用修订Approved；不表示代码、部署或新UAT完成 |

没有核心设计冲突或必须调整代码/测试才能迁移的依赖。所有14份设计都有显式上/下位版本引用链，因此发生元数据传递更新；实际业务段落只改当前/历史计划归属与入口，不是为统一外观升级全套。原v3.0及更早审查结论保留其原范围。

## 5. 实际验证与边界

| 检查/命令 | 本轮实际结果 | 证明范围 |
|---|---|---|
| Get-FileHash / git hash-object对四份归档 | 4/4匹配起始SHA-256；Git过滤前后对象相同 | 原字节保存，后续checkout可核 |
| 内联只读迁移检查（Python，数据为本清单hash/原表） | 当前链接存在；73包身份/状态完整；新12包依赖/状态与原值一致；Business §5/6/7/12及35证据行不变；37+12+12风险/类别ID保留 | 文档承接，无新UAT执行 |
| 内联版本/ID检查（Python + git show起始提交） | 当前链接显式版本一致；REQ/CON/DR/IMPL/TEST/VAL原ID保全；28个目标DR均在新P3追踪 | 权威引用及来源覆盖 |
| validate_implementation_plan.py --file docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md --strict | 修复格式后 errors=0、warnings=0；12包12边无环 | 计划结构/依赖/Ready/资源检查 |
| validate_architecture_doc.py --file 各L0/L1 --root D:/codex --strict | 4/4 strict_valid=true、errors/warnings=0 | 结构/引用检查，非真实效果 |
| validate_detailed_design.py --file 各L2 --root D:/codex --strict | 10/10 strict_valid=true、errors/warnings=0 | 结构/追踪/引用检查，非实施验证 |
| 定向pytest（精确命令见下） | 112 passed；1条既有LangChainPendingDeprecationWarning | 原Business/Knowledge追踪及6组冻结运行兼容，不是重新UAT |
| Git范围、diff --check及有限密钥/JWT模式扫描 | 仅授权Markdown/本次归档；无代码/测试/JSON/config或既有历史资产差异；格式及扫描通过 | 新增/修改内容安全边界，不等于全仓安全审计 |

在D:/codex/agent-runtime执行的通过命令：

```powershell
python -B -c "import sys; sys.path.insert(0, 'src'); import pytest; raise SystemExit(pytest.main(['-p','no:cacheprovider','-q','tests/uat/test_current_traceability.py','tests/uat/test_knowledge_traceability.py','tests/uat/test_historical_v1_assets.py','tests/system_e2e/test_knowledge_representative_run_01_history.py','tests/system_e2e/test_knowledge_representative_run_02_history.py','tests/system_e2e/test_knowledge_representative_run_03_history.py','tests/system_e2e/test_knowledge_representative_human_run_05_history.py','tests/system_e2e/test_knowledge_representative_human_run_06_history.py','tests/system_e2e/test_knowledge_representative_human_run_07_history.py']))"
```

首次直接`python -B -m pytest …`出现3个收集错误（ModuleNotFoundError: agent_runtime），不是断言失败；正式通过命令只为该进程指定源码搜索路径。未修改冻结测试、未放宽断言、未新增永久环境设置。既有LangChain未来allowed_objects默认值警告本轮不改代码，不影响112项通过结论。

未执行：全量Python/Maven、真实Spring/业务服务回归、新Knowledge功能/效果UAT、模型/BGE推理、运行部署/索引验证；纯文档迁移不要求这些动作，也不把它们记为Passed。现有生产/效果风险仍归原证据和后续新计划，当前新方案全部待实施/验证。

提交前分别检查`git status --short`、`git diff --check`、`git diff --cached --name-only`及完整暂存差异；归档暂存内容另以原始hash逐字核对。只提交授权文档，正常推送当前codex分支；不强推/改写历史。最终提交与推送结果以Git记录和交付报告为准，本文不自引用最终提交SHA。
