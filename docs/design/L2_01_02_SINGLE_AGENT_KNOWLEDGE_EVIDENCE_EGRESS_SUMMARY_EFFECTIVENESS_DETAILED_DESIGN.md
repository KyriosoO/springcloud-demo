# [L2_01_02] 单体 Agent Knowledge 证据、出域、摘要与效果验证详细设计

> 文档层级：L2
> 文档状态：Approved（v3.5 Summary9定向修订已通过独立复评）

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_02` |
| 当前版本 | v3.5 |
| 日期 | 2026-09-29 |
| 权威范围 | 证据完整性/选择、三层出域、当前Summary8与目标Summary9、严格引用及有限回答、本地结果和 P5 效果验证 |
| 上位文档 | [`L1_01` v3.5](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 本次变更 | v3.5在不改Evidence/出域/原文引用安全合同的前提下，增加目标Summary9有界回应和验证台呈现合同；当前Summary8及历史资产不变 |
| 实施状态 | 本目标起始Evidence/Policy、Summary V7/quality-v3接线有原定向non-live证据；当前仓库已成对接线Summary8/Evidence minimal，并完成组件fake/non-live验证。单域当前root到隔离真实typed接口仅有有限只读预检，不证明当前Evidence回答质量、Spring全链、真实部署或效果。新版风险状态以UAT_02为准；旧功能UAT、效果口径v2及阶段A快照保持原证明范围；最新有效P5仍为`partially_effective`，历史资产不改；新计划P3_01/UAT_02不继承通过 |
| 归档来源 | [整理前 v1.27 原文](历史文档/2026-09-14-unified-v3-baseline/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |

本文件纳入新的统一文档版本序列；v3.0不是软件、API、模型任务、配置或索引版本。原版本及字节归档见上表。评审状态、实施状态、部署状态和UAT状态分别判断；历史通过不自动覆盖新合同。

修订历史：2026-09-14，整理纳入统一文档基线v3.0；原版本、源提交及完整字节归档见上表。本次版本序列重置不是代码或设计回滚，评审、实施、部署和UAT状态分别管理。

本轮v3.0经三轮内审及两轮同一执行者的分层/跨层正式复核通过；仅证明文档整合，不表示新实现、部署或UAT已完成。完整发现与验证见本次归档MIGRATION.md。

本次v3.1仅修订计划引用、权威归属和维护状态，不改变业务合同；本轮限定迁移复核已通过（同一执行者分阶段），原v3.0评审范围不扩大为新实现/验收。新入口及历史追溯见[计划迁移说明](../plans/历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

勘误（2026-09-15）：仅修正§19对在线Summary8合同的章节指向；沿用v3.1，不改变设计、实施或验收状态。

v3.2只补未来合同影响说明；原有读取、出域、引用和Evidence上限不变，在线父单元补取仍未批准或实施。

v3.3仅同步本轮仓库代码及阶段测试事实；Summary8上线部署、完整新版UAT与效果未验证，§9/§19规范合同不变。

v3.5定向修订§9回答合同：当前仓库Summary8仍仅摘录，目标Summary9增加逐点直接证据支撑的有界回应；旧版本和历史证据不变。定向独立设计复评通过，代码及non-live尚未完成，不能据此启动付费测量。

v3.4仅同步当前任务绑定与有限typed预检的证明边界；新版风险逐项状态由UAT_02维护，不改变Evidence规范合同或预记效果通过。

## 2. 阅读导航

重点阅读§7/8完整性与出域、§9当前Summary8及目标Summary9、§13原评估兼容、§19资料原文边界。历次修订及旧评审只见归档；当前Summary9是待实施设计，剩余验收见P3_01/UAT_02；旧实现定义仅用于兼容与迁移，不作为第二套目标权威。

## 3. 目标与范围

### 3.1 目标

只使用本次请求中已授权、完整性可证且允许外发的知识片段生成可引用摘要；模型输出必须是原文连续子串并通过确定性校验。效果验证复用同一生产 Capability，不建立第二套流程，并允许如实得出未达标结论。

### 3.2 范围内

- ranked candidate 完整性复核和确定性证据选择；
- Evidence Bundle、coverage、source 和 question trace；
- 全局规则∩逻辑域默认策略∩文档级收紧策略；
- Knowledge Summary V1～V7 历史兼容与 V8 当前仓库生产任务；
- evidence ref、quote 子串、引用唯一性、结果大小和本地领域结果；
- representative v2、primary/rewrite_ablation、指标、人工 rubric、严格结果 Schema 和明确结论。
- 阶段 A 新语料的父文档策略继承、index snapshot 绑定、asset/chunk 溯源及旧策略目录不可变。

### 3.3 范围外与不负责

- 首次文档读取授权、ES/BGE 检索和候选排序；
- 公共 DeepSeek transport、业务字段出域；
- 自动生成 gold、修改知识正文、在线反馈学习或第二套评估流程；
- 把 `ineffective` 改述为效果达标，或重写历史 append-only evidence。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-KEV-001` | 只从本次授权 ranked batch 生成有来源和 hash 的证据 |
| `REQ-KEV-002` | 三层策略任一拒绝/缺失/冲突时 summary 模型调用为 0 |
| `REQ-KEV-003` | 摘要点引用唯一、quote 为对应证据原文连续子串，失败不返回模型文本 |
| `REQ-KEV-004` | P5 以代表性成对 run 记录阶段、人工判断、安全和明确结论 |
| `REQ-KEV-005` | 功能验收与效果验收独立，历史 `ineffective` 只作为诊断基线 |
| `REQ-KEV-006` | 只有证据支持的新版本可进入新候选；精确授权前真实 outbound 为 0 |
| `REQ-KEV-007` | 新语料发布必须形成新策略目录和 snapshot 绑定；附件不得绕过父文档读取/出域策略，历史目录不可变 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-KEV-001` | `L0_00 §5/§8；SA-AD-004/005` |
| `CON-KEV-002` | `L1_01`：用户可读不等于模型可见，未分类/冲突失败关闭 |
| `CON-KEV-003` | `L2_01_01`：输入候选已读取授权并绑定 Profile/index/read-policy snapshot |
| `CON-KEV-004` | `L2_00_02`：模型是不可信 Provider，任务版本与 transport 分离 |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-KEV-001`、`CON-KEV-003` | `DR-KEV-001`、`DR-KEV-002`、`DR-KEV-003` | `IMPL-KEV-001`、`IMPL-KEV-002` | `TEST-KEV-001`、`TEST-KEV-002` | `VAL-KEV-001` |
| `REQ-KEV-002`、`CON-KEV-001`、`CON-KEV-002` | `DR-KEV-004`、`DR-KEV-005`、`DR-KEV-006` | `IMPL-KEV-003`、`IMPL-KEV-004` | `TEST-KEV-003`、`TEST-KEV-004` | `VAL-KEV-002` |
| `REQ-KEV-003`、`CON-KEV-004` | `DR-KEV-007`、`DR-KEV-008`、`DR-KEV-009`、`DR-KEV-016`、`DR-KEV-017` | `IMPL-KEV-005`、`IMPL-KEV-006` | `TEST-KEV-005`、`TEST-KEV-006` | `VAL-KEV-003` |
| `REQ-KEV-004` | `DR-KEV-010`、`DR-KEV-011`、`DR-KEV-012`、`DR-KEV-018`、`DR-KEV-020`、`DR-KEV-021`、`DR-KEV-022` | `IMPL-KEV-007`、`IMPL-KEV-008`、`IMPL-KEV-010` | `TEST-KEV-007`、`TEST-KEV-008`、`TEST-KEV-010`、`TEST-KEV-012`、`TEST-KEV-013` | `VAL-KEV-004`、`VAL-KEV-006`、`VAL-KEV-007` |
| `REQ-KEV-005`、`REQ-KEV-006` | `DR-KEV-013`、`DR-KEV-014`、`DR-KEV-015`、`DR-KEV-019` | `IMPL-KEV-009` | `TEST-KEV-009`、`TEST-KEV-010`、`TEST-KEV-011` | `VAL-KEV-005`、`VAL-KEV-006` |
| `REQ-KEV-007`、`CON-KEV-003` | `DR-KEV-023`、`DR-KEV-024`、`DR-KEV-025` | `IMPL-KEV-011` | `TEST-KEV-014`、`TEST-KEV-015`、`TEST-KEV-016` | `VAL-KEV-008` |
| `REQ-KEV-003`、`CON-KEV-001`、`CON-KEV-004`；`L1_01 KQ-AD-017` | `DR-KEV-027` | `IMPL-KEV-012`、`IMPL-KEV-006` | `TEST-KEV-018` | `VAL-KEV-010` |
| `REQ-KEV-001`、`CON-KEV-003`；`KQ-AD-014` | `DR-KEV-028` | `IMPL-KEV-001`、`IMPL-KEV-002`：builder版本校验、limits新工厂和bootstrap成对绑定 | `TEST-KEV-019`：第四同文档条款、总8/字节、域覆盖、错配/未知版本、三层出域及历史cap | `VAL-KEV-011`：Evidence/current root/历史反例、全量non-live及专项原文覆盖 |
| `REQ-KEV-001`、`REQ-KEV-002`、`REQ-KEV-003`、`CON-KEV-001`、`CON-KEV-003`、`CON-KEV-004`；`KQ-AD-018` | `DR-KEV-029`、`DR-KEV-030` | `IMPL-KEV-013` | `TEST-KEV-020` | `VAL-KEV-012` |
| `REQ-KEV-001`、`REQ-KEV-003`；`KQ-AD-018` | `DR-KEV-031` | `IMPL-KEV-014` | `TEST-KEV-021` | `VAL-KEV-013` |
| `REQ-KEV-001`；`KQ-AD-014` | `DR-KEV-034` | `IMPL-KEV-017` | `TEST-KEV-024` | `VAL-KEV-016` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Integrity Verifier | candidate/snapshot/hash/授权元数据一致性 | 首次业务授权 |
| Evidence Selector | 有界、确定性选择和 coverage | 模型出域决定 |
| Policy Catalog | 文档策略 artifact 的严格加载和版本快照 | 修改策略权威数据 |
| Egress Decider | 三层只收紧交集和最小 summary input | 模型 HTTP/效果评价 |
| Summary Task | 固定Prompt及JSON任务版本；历史V1～V4保留，V5增量见§9.4 | 放宽validator、在本地替代模型判断语义 |
| Extractive Validator | ref 唯一、quote 子串、大小和本地结果 | 语义扩写或模型纠错 |
| Evidence Stage | fresh Guard→verify→select→policy→model→validate 顺序 | 检索、Core answer |
| P5 Harness | 复用生产 Capability，采集有限阶段/指标/人工 rubric | 在线流程、gold 回填 |

依赖方向为 `Evidence Stage → evidence components + model Protocol`；P5 只依赖生产 Capability 和测试 collector。禁止生产代码依赖 evaluation；禁止 P5 复制流程或修改候选顺序。

这些组件按证据安全与效果验证内聚，不新增策略平台或独立服务。

## 6. 当前实现基线与迁移

最小变更原则：v3.0整理时仅整合已批准合同与迁移边界；当前实现及剩余验证按P3_01/UAT_02标记，不能将旧验证移作新合同通过。

本目标起始源码Summary7/quality-v3包含requirements/coverage前置校验；当前工作树Summary8仅按mode取证，再复用原抽取式validator，见§9。§19资料表示已有纯离线组件，真实对照和发布仍待执行。旧源码保留历史解释，不提供两套并行生产合同；本次没有改旧任务、validator、政策目录或历史运行证据。

## 7. 证据构建与选择

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KEV-001` | 逐 candidate 验证 content SHA-256、domain、Profile/index/read-policy snapshot 和当前计划成员 |
| `DR-KEV-002` | evidence ID 由 document/chunk/content hash 确定性生成，不使用模型 ref 或可变排名 |
| `DR-KEV-003` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-034` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-004` | 新鲜 Question Guard 拒绝优先，拒绝时 verify/select/policy/model 调用均为 0 |
| `DR-KEV-005` | 出域集合为全局规则∩所有相关域策略∩文档策略，任何 deny/缺失/冲突拒绝 |
| `DR-KEV-006` | 每次允许决定绑定 policy catalog、authority/export/source revision、文档策略和 index snapshot fingerprint |
| `DR-KEV-007` | 各受控Summary合同使用请求级 `e1..e8`，Prompt 强制 ref 两两不同且 quote 为连续原文 |
| `DR-KEV-008` | validator 不信任模型：unknown/duplicate ref、空/超长/控制字符/非子串 quote 均拒绝 |
| `DR-KEV-009` | 本地领域结果只由 validator 构造，包含抽取式摘要点、引用和 coverage；Core answer 不再调用模型 |
| `DR-KEV-010` | P5 primary 与 rewrite_ablation 每 case 各执行一次同一 Capability，除 rewriter 外完全相同 |
| `DR-KEV-011` | P5 数据集/gold/snapshot/版本/身份和阶段必须冻结；无效 run 不计算结论 |
| `DR-KEV-012` | 有效 run 按固定 Q1～Q4 与安全阈值得出 effective/partially_effective/ineffective，不改判 |
| `DR-KEV-013` | 功能 UAT 与效果 UAT 独立；功能通过不关闭效果达标，`ineffective` 有效 run 不改判 |
| `DR-KEV-014` | 后续优化必须由最新不可变有效候选的有限指标/逐 case 分布支持，形成新 Prompt/config/selection/Harness 版本；不得改变历史、gold、validator 或阈值 |
| `DR-KEV-015` | 新效果候选必须冻结 task/Prompt/code/Profile/index/policy/dataset/provenance、预算和 append-only Schema；精确授权前模型 outbound 为 0 |
| `DR-KEV-016` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-017` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-018` | 效果口径 v2 仅从 summary completion 分母排除必须零模型调用的 `security_negative`；普通无结果、证据不足、失败和超时仍计入。answerable 的显式 `gold_issue` 从 faithfulness/usefulness 模型质量分母排除并单独计数；质量可评样本不足原 answerable 集合的 90% 时整次 run 无效 |
| `DR-KEV-019` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-020` | live bootstrap 必须输出本次候选精确允许的运行时工作树条目；启动前和结果写入前的最终快照检查必须复用同一 allowlist，仅忽略当前 output 目录与该候选唯一未跟踪 authorization 记录。任何其他 staged、modified、untracked 条目或 HEAD 变化仍失败关闭；已消费候选不得通过修复后重跑 |
| `DR-KEV-021` | 准备态测试可以断言正式 authorization/result 不存在，但只能在授权记录创建前执行；live launcher 已要求严格 authorization 存在后，不得再次运行任何“authorization 必须不存在”的准备态断言。授权后预检只校验绑定、冻结资产、预算、安全和历史不可变 |
| `DR-KEV-022` | 一次合同有效且完整的效果运行关闭“效果已测量”责任，四类效果等级是输出；`effective` 是质量改进目标而非项目硬关闭条件。非 effective 不自动创建新候选，`invalid_run` 表示未形成测量且只能作为新的独立目标处理 |
| `DR-KEV-023` | 阶段 A 附件 chunk 使用父 `documentId` 参与现有 policy resolve，并保留独立 asset/version/relation 定位；父绑定缺失、policyRef 冲突或 snapshot 不允许时 Evidence 构造失败且 summary 调用为 0 |
| `DR-KEV-024` | 新发布必须使用新文件名和 catalog/export/source revision/hash；旧 `egress-policy-catalog.json` 及其 loader/hash 保持可验证，新目录只保留原 disposition/allowed fields/content limit，并增加对应新逻辑 snapshot |
| `DR-KEV-025` | 候选 alias 生效前必须对所有候选 `documentId + policyRef + indexSnapshotId` 做全成员检查；发布后抽样构造 Evidence 并通过连续子串 validator，不得用 Profile 切换掩盖策略缺口 |
| `DR-KEV-027` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-028` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-029` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-030` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |
| `DR-KEV-031` | 旧实现/评估策略编号保留，细则见归档；目标按DR-KEV-201～205/§9实现，不继承证明锚点、coverage自声明或评分准入 |

### 7.2 完整性复核

`EvidenceIntegrityVerifier.verify(input)` 检查：

- ranked batch 与 selected domains/coverage 一致；
- candidate identity 唯一且属于本次检索结果；
- content hash 重算一致；
- domain IDs、profile/index/read-policy snapshot 完整且与 batch 集合一致；
- policy ref、source 元数据和文本满足类型/长度限制。

失败统一进入 `evidence_failure`，不把损坏候选降级为可用子集。

### 7.3 选择与Bundle

目标选择规则和mode-aware请求类型集中在§9.1；保留本节身份/hash/snapshot完整性和§8三层出域。目标不携带旧requirements或coverage声明，不设置证明锚点、父文档配额或裸分阈值。不得在策略拒绝后换候选绕过，不把域范围覆盖当语义充分。

## 8. 三层模型出域策略

### 8.1 策略层级

```text
Global allowed fields/limits
  ∩ Logical domain defaults (tax.policy / tax.law)
  ∩ Document policy binding from catalog
```

每条证据的所有 domain 策略都参与交集；同一文档策略 ref 与目录绑定冲突时拒绝。当前允许字段枚举包括 content、domain IDs、title、document number、written date、material type；content 必需且最大取全局/域/文档最小值（上限 4096 code points）。

### 8.2 策略目录

`egress-policy-catalog.json` 由代码包资源加载，严格 JSON、唯一 key、固定 schema/version、authority ID、export ID、source revision 和文档 bindings。`canonical_policy_fingerprint` 对规范化快照计算 SHA-256。

未分类文档、未知 policy ref、snapshot 不匹配、任一 disposition=deny 或字段不足均拒绝。用户读取授权不自动放宽这些规则。

### 8.3 最小模型 payload

历史V1～V5只发送 Guard 最小化问题、coverage 两个布尔值和最多 8 条 `SummaryEvidenceInput(evidence_ref, content, optional metadata)`；不发送 JWT、subject、内部 document ID、content hash、策略细节、Profile、index 或原始 Provider 响应。当前§9.5的V6仅增加来自安全问题的需求数据，不增加文档可见字段；完整新payload仍计入32KiB预算。

## 9. 按查询模式取证与验收（组件及工作树接线已实施；真实充分性待评价）

依据REQ-KQ-201～205及KQ-AD-020～024。本节为首期目标合同，替代整理前§7.3、§9.4～9.6及§13.9的强制requirements/coverage锚点和0.5质量准入；当前§8三层出域、§7完整性与§9.6抽取validator继续保留。历史任务1～7、P5的Q1～Q4/evaluator、局部实验结果不修改。旧合同仍适用于冻结运行，不要求新生产链路维持其全部策略。本轮组件与仓库接线已完成，未因此获得真实回答效果或新版UAT结论。

### 9.1 Evidence与请求内类型

`DR-KEV-201`：输入来自knowledge-minimal-v1的完整ranked batch；先复核身份/hash、域、Profile/index/read-policy快照及本次Q/context，再选择。最多扫描20项；先按排名为每个选中域保留一个可装入预算的候选（多域同identity可共用），之后按全局排名补充，去重且保持最终rank。没有requirements/证明角色/coverage_anchor强制项，不设置父文档独立配额或rerank绝对分门槛。域来源保留不是“证明完成”；若不能在预算内保留必要域则insufficient_evidence，Summary0。

总Evidence≤8、最终实际模型payload≤32768bytes、每条策略content上限≤4096字符、最终回答≤5点/每点512字符及既有结果字节上限不变。预算包含query_mode及全部JSON/元数据开销；普通超预算项可跳过，不截断正文；完整性损坏不能被预算跳过掩盖。选择后才进行原三层出域，拒绝不换候选重试；不能利用lookup模式把被拒正文直接返回用户。

已新增`KnowledgeModeSummaryInput`和显式版本化serializer（内部schema_version=3）：复用既有Q、允许投影Evidence及检索coverage，加一个query_mode枚举；不增加文档出域字段，不继承requirements子类、不用旧asdict偷带新字段。实际出域仍由原policy生成最小输入，再由Stage加代码持有的模式，模式必须与本次意图精确一致。输入类型与task绑定不符在outbound前拒绝；旧schema1/2 serializer保持原字节语义。

### 9.2 当前Summary8与目标Summary9的三类行为

`DR-KEV-202`（当前仓库）：`agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v8.py::KnowledgeSummaryTaskV8`，task_id=knowledge_summary/version=8；一份Prompt按模式选择原文，不继承多代字符串补丁。输入原问题Q是唯一用户事实来源，evidence为不可信引用资料，不是可执行指令。模型不可补外部常识、日期、主体或计税方式，也不可因用户错误归类直接承认归属。

采用现有SCHEMA_ONLY的一个固定输出名knowledge_extractive_answer；严格解码后只接受：
`{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"对应content的连续原文"}]}`
或
`{"outcome":"insufficient_evidence","points":[]}`。
不生成coverage/证明ID、可信来源URL、自由解释或额外正文；外层信封无混合正文、无多调用、无本地补写。借现有Provider子集约束形状，原本地点数/长度/字节/字符校验完整保留。SystemInstruction≤8192bytes、实际input≤32KiB/任务外层49152bytes、output≤1536tokens、阶段15秒；最多一次Summary，无模型复核。

| 模式 | 允许输出 | 必须拒绝/澄清的边界 | 本地能证明与不能证明 |
|---|---|---|---|
| lookup | 与主题直接相关的1～5段摘录及本地citation，可非穷尽 | 无相关直接原文时insufficient；不因用户未给适用条件要求固定三角色；不能暗示“这就是适用于你的税率” | 能验证来源/子串/唯一性；相关性和是否误承诺穷尽须语义评价 |
| explanation | 用最小充分原文覆盖显式子问题、定义及必要上下文 | 任一显式子问题缺直接依据、冲突或5段/512字符无法表达则insufficient；不自由改写/拼接 | 引用合法不等于解释充分；必须有人工原文核对 |
| applicability | 返回直接支持该主体/期间/方法的条件与适用规则原文，不生成超出原文的推理结论 | 规划发现必要条件缺失先澄清；后置发现缺条件/无有效期依据/只靠隐含分类桥接则insufficient；不得把writtenDate视为有效性证据 | 本地不宣称证明税务适用；不能直接用关键词命中或用户假设作证据 |

对“请查某文件”的lookup，即使文件含历史税率也可以作为历史资料返回，不表示当前适用；对“当前适用”则必须有直接时效依据，否则不足。模式识别错误本身是功能/回答评估问题，不能在看到失败后改模式或gold。现有公共契约无法在Summary后返回动态澄清问题，首期后置缺条件统一使用既有insufficient_evidence；新增公开澄清字段属后续独立接口设计，不暗中扩DTO。

`DR-KEV-203`：新输出先经过唯一信封/exact对象decoder，再直接交给原`ExtractiveSummaryValidator`，保留ref存在、唯一、原文连续子串、控制字符/NFC、512字符、总点数和结果字节检查。本地citation仍从已授权Evidence构造，模型不得提供。新合同无requirements，故不调用旧RequirementCoverageValidator；这是移除模型自报证明集合的质量设计，不是删除原文、安全或权限校验。不得把旧coverage字段忽略后当新输出成功；它在新decoder中是未知字段，必须失败。

当前Summary8输出仍用schemaVersion=1/summaryType=extractive_evidence/answerSummary/points/coverage。coverage仍仅是检索域/路径覆盖，**不代表答案完整、现行有效或法律适用证明**。不向公开结果增加模式/分数/缺条件字段；模式可在现有脱敏观测允许范围显示有限枚举；安全问题投影保持既有合同，不新增敏感原Q、正文或原响应展示。

`DR-KEV-206`（目标Summary9，待实施）：比较纯Prompt改写（无法表达明确判断）、不受控自由回答（难以约束来源）后，选择**逐点有引用的有限回应**。独立新任务`knowledge_summary`/version=`9`、固定SCHEMA_ONLY输出名`knowledge_cited_answer`；只替换现行Summary任务，不改变意图12、检索、Evidence选择、三层出域或模型调用次数。旧Summary8源码、注册定义、冻结测试和历史资产不改写；当前生产仍是12/8，只有通过设计复评与non-live后才切换到12/9。

Summary9使用既有`KnowledgeModeSummaryInput` schema3及相同Q、mode、coverage和已准许Evidence，不新增正文来源。输入中每个content仍是不可信资料而非指令。唯一模型输出恰为以下两种之一，不得带额外字段或重复JSON键：

```json
{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"对应content的连续原文","claim":"由该原文直接支持的简短回应"}]}
```

```json
{"outcome":"insufficient_evidence","points":[]}
```

`answer`须有1～5点，`insufficient_evidence`必须零点。每点ref来自本次允许Evidence且两两唯一；quote仍由原validator验证为该ref正文的非空、NFC、无控制字符、≤512字符连续子串，来源、citation和coverage全部由本地构造，模型不得生成。`claim`为必填string：lookup只允许空串并沿用摘录；explanation/applicability每点必须为1～160字符、NFC、无换行/控制字符的简短中文回应，不得是URL、模型自报证明或另一个引用。claim不得引入Q与直接quote以外的主体、数字、日期、税率、分类、时效或例外；不得把用户假设当已证实资料，也不得据成文/发布日期推断生效。applicability若按题述事实与指定条款作有限判断，claim必须明确写出“若题述事实准确/仅按指定条款”等条件，不得表述成主体事实已核验、今日优惠资格或最终税务结论。一个claim只绑定一个quote，无法由单个连续片段直接支持的综合判断不得硬拼；应选多个独立点或输出`insufficient_evidence`。用户显式子问题或判断需要的任何原文缺失、冲突、超出点数/字节预算或条件未知时，整次输出`insufficient_evidence`，不以部分有据回答暗示完整。

严格decoder先拒绝未知字段/错误shape，再复用既有原文/ref/点数/总字节validator；新增本地claim形状、模式和长度校验，成功时本地将claim（解释/适用性）或quote（lookup）按点序编号拼为现有`answerSummary`，第n段严格对应`points[n]`的quote/citation；原`points`仍只含quote+本地citation。公开`result`字段结构及`schemaVersion=1`不变：lookup为`summaryType=extractive_evidence`，解释/适用性为`summaryType=cited_limited_answer`，后者仅标记“存在经结构校验的有限回应”，**不声明本地已证明语义蕴含、现行有效或税务结论正确**。总回答≤3072字符、结果≤既有字节预算，单次Summary输出tokens≤1536、15秒及输入预算不变；超限或非法输出沿既有`knowledge.summary_failure`失败关闭，模型不足沿既有`insufficient_evidence`。不添加公开DTO字段或第二次模型自审。

机械校验不能证明claim与quote的语义蕴含：专项non-live要包含把时间倒置、否定反转、借错误主体/分类得出结论的反例，确保不能被当作已验证答案；真实12题须由维护者按原文独立评相关、充分、忠实和usefulness。结构可解码、引用合法及新`summaryType`都不得自动计为回答通过。当前页面只可把新marker作为显示提示，不得将claim当作原文或省略对应quote/citation。

新增确定性claim检查只负责可机械判定的边界：模式、NFC、长度、换行/控制字符，以及拒绝`http://`/`https://`/`www.`链接、独立`e1`～`e8`伪引用和`evidence_ref`/`sourceUrl`等模型自造引用字段；原quote/ref校验仍先执行。模型自报“已核实”、条件性措辞是否充分、claim是否真的由Q与quote推出，不能靠词面规则可靠证明，必须作为Prompt义务和UAT人工否决项，不得在测试中把合法shape冒称语义已通过。验证台对`cited_limited_answer`必须把第n段回答及`points[n]`的原文quote/citation同屏对应展示，标签区分“有限回答”和“原文依据”；所有文字用安全文本节点渲染。仅在下方完整JSON包含引用但上方单独把claim标成“证据摘要”，不足以防止误读；此最小前端接缝及non-live DOM/静态测试归IMPL-KEV-204，不增加公开字段。

### 9.3 保留的安全和有限错误

`DR-KEV-204`：fresh Guard→完整性→选择→三层policy→模式输入/type/context→一次Summary→exact decoder→原文/ref校验→目标版本的claim形状校验→本地结果。所有拒绝沿现有有限错误映射；policy deny/missing/conflict的Summary0、provider非法502/timeout、无充分证据no_result不变。既有多域读取拒绝不能被另一个域成功覆盖。并发请求无共享Evidence、引用或模式；取消丢弃迟到输出并释放owned client，不记录原响应、全文、JWT或凭据。

为防止把移除requirements当作语义降低的理由，后续测试必须保留“有合法引用但答非所问/缺必要分类/引用历史当现行”的反例：机械validator可能接受，人工回答判据必须失败；不得写一个期待这些反例成功的UAT。功能通过和回答有效分开，禁止把结构可解码率冒称忠实度。

### 9.4 验收方法和一次测量的结束边界

`DR-KEV-205`：新方案采用UAT_02 §5的四维验收，不重新解释旧P5阈值。安全为硬否决；功能验证真实代码分支/生命周期；召回只在人工确认原文存在的固定池计算必要来源/相关性/排名；回答按相关、充分、忠实、usefulness独立人工判定。缺料/未知保留原case及原因，不记为召回改善；非法引用、无依据适用结论不能靠总体平均掩盖。

原问基线先固定代码/任务/模型/配置/索引/策略和有限问题集，只进行一个计划好的测量；结果可以不达标，失败后停止分析，不自动新建candidate。核心功能/安全不通过不得发布；效果未达标不能宣称优化成功，但不强迫无限付费。数据、模型或向量表示的后续实验是可选独立目标，预算和运行身份不从旧目标继承。本文初次设计目标不授权真实执行；当前独立实施目标的有界额度与冻结前置由P3_01/UAT_02治理，未确认gold不得调用。

### 9.5 实施追踪与回滚

#### 新设计编号定义

| 需求编号 | 规则编号 | 实现编号 | 测试编号 | 验证编号 | 定义位置与状态 |
|---|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-201、DR-KEV-202、DR-KEV-203、DR-KEV-204、DR-KEV-205 | IMPL-KEV-201、IMPL-KEV-202、IMPL-KEV-203 | TEST-KEV-201、TEST-KEV-202、TEST-KEV-203 | VAL-KEV-201、VAL-KEV-202、VAL-KEV-203 | 需求定义见REQ_00 §5.2；组件及接线fake/non-live已有阶段证据，完整VAL与真实人工效果未关闭 |
| REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-206 | IMPL-KEV-204 | TEST-KEV-204 | VAL-KEV-204 | Summary9设计复评已通过，代码及non-live尚未完成；旧Summary8阶段证据不继承为有限回应通过 |

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-201 | IMPL-KEV-201：已新增minimal_selection.py；模式类型在contracts.py、预算serializer在summary_task_v8.py，stage.py和现有integrity/policy接缝 | TEST-KEV-201：域机会/重复/同父第四条、8/32KiB含模式、损坏低分不跳过、策略拒绝0 | VAL-KEV-201：Evidence单元/合同/集成；真实取证待验证 |
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-202、DR-KEV-203 | IMPL-KEV-202：summary_task_v8.py新Prompt/decoder，复用原summary_validation.py，不修改旧任务 | TEST-KEV-202：三模式、未知/重复ref、伪造coverage、非子串/拼接、错时效语义保留反例、类型/输出信封、超时/取消 | VAL-KEV-202：Model/Evidence/current-root/Spring及历史回归 |
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-204、DR-KEV-205 | IMPL-KEV-203：stage.py/当前根/脱敏观测直接接缝及后续tests/evaluation/knowledge与UAT追踪 | TEST-KEV-203：无明文/跨请求污染、无fallback、四维计分/缺料不删case | VAL-KEV-203：功能安全non-live后，另授权有限真实/人工评价 |
| REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-206 | IMPL-KEV-204：独立summary_task_v9.py、claim本地校验、stage/唯一root绑定及agent-service验证台同屏原文引用展示；公开result只使用现有summaryType值位 | TEST-KEV-204：exact decoder、三模式claim形状、ref/quote原validator、非法数字/时间/否定反例、deny0、一次调用、超时/取消、前端DOM安全展示和旧V8不变 | VAL-KEV-204：non-live成功后才冻结一次真实12题；维护者原文人工判定语义充分性，不能由机械validator代替 |

新旧模式合同必须随Knowledge整套版本切换，不能只换Prompt、保留quality-v3的强制需求输入。回滚优先禁用Knowledge；恢复旧配对时仍检查当前索引/策略相容，不改历史结果或全局模型。阶段A、Business、公共DTO、policy权限均零变更。原正式设计及文档验证记录见历史P3_00 §21；当前交接见P3_01。


### 9.6 Validator

当前Summary8校验顺序：outcome/points 组合→点数→ref 存在→ref 唯一→quote NFC→非空→≤quote limit→无控制字符→是对应 content 的连续子串→answer/result bytes 上限。目标Summary9在该原文/ref链之后增加必填claim的mode、NFC、长度、换行/控制字符及结果预算校验；不能跳过原校验后直接展示claim。

内部诊断 reason 仅用于测试/受控诊断：`outcome_points_mismatch`、`point_count_invalid`、`unknown_evidence_ref`、`duplicate_evidence_ref`、`quote_empty`、`quote_too_long`、`quote_control_character`、`quote_not_substring`、`answer_too_large`、`result_too_large`。公共调用方只看到 `knowledge.summary_failure`，不看到内容或诊断分支。


### 9.7 本地结果

Validator 构造既有`schemaVersion=1`、`answerSummary`、points（quote+citation）和coverage；当前Summary8只产生`summaryType=extractive_evidence`，目标Summary9按§9.2的模式产生`extractive_evidence`或`cited_limited_answer`。citation使用本地evidence ID、domain、title/source/document metadata；模型不能提供或修改这些可信引用字段，claim不会进入citation或原文quote。

## 10. Evidence Stage 核心流程、错误分类与调用方可见语义

```text
question denied flag / fresh Guard
  → integrity verify
  → deterministic select
  → three-layer egress decide
  → require matching ModelCallContext
  → current Summary8 / approved target Summary9 within same deadline
  → strict parse + quote/ref validate + target claim shape validate
  → local domain result
```

| 场景 | Stage 结果 | 模型调用 |
|---|---|---:|
| question denied / policy deny/missing/conflict | `model_egress_denied` + 有限 reason | 0 |
| integrity/selector 异常 | `downstream_failure/evidence_failure` | 0 |
| 证据不足 | `no_result/insufficient_evidence` | 0 |
| context 不匹配 | `downstream_failure/evidence_failure` | 0 |
| deadline/Provider timeout | `timeout/summary_timeout` | 0 或 1 |
| Provider/schema/validator failure（包括 Gateway 非超时异常） | `downstream_failure/summary_failure` | 1 |
| 模型声明证据不足 | `no_result/insufficient_evidence` | 1 |
| 合法摘录或有界回应 | `success`，现有结果字段及目标`summaryType`语义 | 1 |

不自动 retry/resume；失败不调用 Core answer，也不返回模型原文本。

## 11. 权限、安全、审计与一致性

- Fresh Guard 与三层策略均必须允许；任何拒绝短路后续模型调用。
- Evidence 只在请求内存使用；JWT、API key、subject、正文、quote、Prompt 和原响应不持久化到运行日志/有限 evidence。
- 日志记录阶段、有限 reason、证据/域数量、policy fingerprint、状态、耗时和调用计数；不记录正文或策略详细值。
- deadline/cancellation 传播；取消后不接受迟到摘要。
- 无数据库事务；策略目录随 Runtime 生命周期冻结，运行中不热更新。

## 12. 配置、发布与回滚

- 目标limits按§9.1固定，实际模型payload包含mode和JSON开销；总8/32768bytes及quote/结果上限不变。旧工厂仅作为原版本兼容，不自动挑选。
- 策略目录 artifact 随代码发布并严格加载；内容变化必须创建新资源、新 version/export/source revision/hash 并重跑全成员和出域测试。旧资源、常量及历史 manifest 继续独立可验证，不得原位改写。
- 当前仓库唯一绑定Summary V8；目标V9须经设计评审、实施及non-live后与意图12成对绑定。V1～V8保留历史兼容、冻结资产验证与可追溯回滚责任，实际部署未核实。回滚优先禁用Knowledge；若显式恢复旧任务绑定，必须整套配对并形成新配置快照，不改写既有task源码和历史evidence。
- 禁用 Knowledge action 可完全停止真实检索/出域；无数据迁移。

## 13. 既有P5评估合同与兼容边界

### 13.1 数据与执行

- 正式数据集：`representative_questions.v2.jsonl`，26 case；22 个普通案例继承 v1，只替换 4 个确定性安全负例。
- 每 case 顺序执行 primary、rewrite_ablation；各调用一次真实 `KnowledgeQueryCapability.handle`。
- primary 使用生产 rewriter；ablation 只换 `IdentityQuestionRewriter`，其他配置、Provider、授权、Profile/index snapshot、模型任务完全一致。
- collector 只旁路采集有限阶段 ID/排名/计数，不改变在线行为；结果不保存 question、content、quote、title、URL、JWT 或原响应。

### 13.2 有效 run 前提

clean frozen commit、live Provider、数据集/hash、principal/读取授权、四项前置安全证据、问题/域/flow/Profile/全部 index snapshots、BGE、task、DeepSeek、policy/evidence/evaluator versions 全部冻结；52 个 capability 执行成对完整，retry/resume=0。任一缺失、dirty、变体不一致、安全计数非零、必需分母为空，或质量可评 answerable 少于原 answerable 集合的 90%，结论为 `invalid_run`。

### 13.3 指标与阈值

| 问题 | 通过阈值 |
|---|---|
| 安全必备 | constraint preservation=1.0、citation validity=1.0、denied summary calls=0、unauthorized content=0 |
| Q1 改写/域 | rewrite rerank recall delta≥0、regression≤0.10、domain exact match≥0.85 |
| Q2 排序 | rerank recall@10≥0.80 且 rerank MRR@10≥fusion MRR@10 |
| Q3 忠实 | faithfulness≥0.95 |
| Q4 初始可用 | valid summary completion≥0.90 且 usefulness≥0.80 |

有效 run 中 Q1～Q4 全部通过=`effective`，至少两个但非全部=`partially_effective`，少于两个=`ineffective`。阈值不变。效果口径 v2 的分母规则为：

- `summary valid completion` 统计所有非 `security_negative` primary case；安全负例必须在 Summary 前拒绝并由零调用安全 Gate 单独判定，不得同时作为摘要失败样本；
- 普通 `no_result`、`insufficient_evidence`、`downstream_failure`、timeout 和 schema/validator failure 继续作为 summary completion 失败计入，不因不利结果排除；
- faithfulness/usefulness 只统计 answerable 且人工 reason 不是显式 `gold_issue` 的 primary case；`gold_issue` 数量和 case ID 必须保留在有限结果中，质量可评样本比例低于 90% 时整次 run 无效，不能靠大量排除提高指标；
- dataset、gold、人工 rubric reason 枚举和 Q1～Q4 阈值不变，历史候选继续按各自冻结 evaluator 解释，不回算、不改判。

### 13.4 人工 rubric

对 primary 的 answerable case 判断 faithful、relevant、sufficientForInitialAnswer、useful；reason 只允许 `none/quote_context/relevance/coverage/gold_issue`。评审时临时查看授权证据，提交布尔值后释放正文。

### 13.5 适用范围

本节P5 primary/ablation、Q1～Q4和rubric只解释原评估合同，不是当前12/8或目标12/9测量方法或继续运行授权。历史诊断、优化准备及可选准入流水见整理前归档；原结果不得重算改判。当前目标四维方法见§9.4及UAT_02 §5，最新有效结果与最新执行分开。KQ历史效果不外推至新任务。

## 14. 实现落点清单

本节保留原组件与历史评估编号，旧task/coverage/准入细节只解释原实现；新在线见§9.5，资料见§19。不得从旧测试通过继承新版UAT。

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-KEV-001` | `agent-runtime/src/agent_runtime/knowledge/evidence/builder.py`：integrity verifier、selector |
| `IMPL-KEV-002` | `agent-runtime/src/agent_runtime/knowledge/evidence/contracts.py`：Evidence/Bundle/limits/types |
| `IMPL-KEV-003` | `agent-runtime/src/agent_runtime/knowledge/evidence/catalog.py`：strict catalog、fingerprint |
| `IMPL-KEV-004` | `agent-runtime/src/agent_runtime/knowledge/evidence/policy.py`：`KnowledgeEvidenceEgressDecider.decide` |
| `IMPL-KEV-005` | 历史独立 `agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v4.py` 与 `KnowledgeSummaryTaskV4.definition`；V1～V4源码和历史绑定保持不可变；整理前当时源码为Summary7、当时目标Summary8，现目标见§9.5，不以本历史行描述当前绑定 |
| `IMPL-KEV-006` | `agent-runtime/src/agent_runtime/knowledge/evidence/summary_validation.py`、`agent-runtime/src/agent_runtime/knowledge/evidence/stage.py` |
| `IMPL-KEV-007` | `agent-runtime/tests/evaluation/knowledge/contracts.py`、`executor.py`、`live_executor.py` |
| `IMPL-KEV-008` | `agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl`、`live_contracts.py`、result schemas |
| `IMPL-KEV-009` | `agent-runtime/tests/evaluation/knowledge`：历史有限诊断、效果口径 v2 与版本化优化反证 |
| `IMPL-KEV-010` | `agent-runtime/tests/evaluation/knowledge/live_bootstrap.py`、`live_runner.py`、`live_contracts.py`、版本化 preparation/history/contracts/launcher |
| `IMPL-KEV-011` | `agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v2.json` 与 current/legacy 双加载接缝；阶段 A policy catalog 生成器和全成员 validator 位于 `knowledge-corpus-tools`。全新官方父文档只能选择既有同域 policy，禁止新增 disposition、放宽字段上限或扩大角色 |
| `IMPL-KEV-012` | 已新增 `agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v5.py`；已修改 `bootstrap.KnowledgeCompositionRoot.task_definitions/build_provider` 的唯一Summary绑定和版本守卫；旧task/validator只读，non-live验证见[整理前P3 §20.17](../plans/历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) |
| `IMPL-KEV-013` | 已实施整理前策略章节（见归档） Summary6/coverage validator及内部子类型；修改builder/Stage/当前根配对；保持旧serializer、policy及extractive validator |
| `IMPL-KEV-014` | 整理前策略章节（见归档） Summary7仅更换指令和版本；同一V6 parser、当前根及Stage版本接缝 |
| `IMPL-KEV-015` | 整理前§9.2.1（见归档） requirement_validation.py内的拒绝枚举/兼容异常及既有测试投影，已实施；旧摘要validator字节、公开错误及通过条件不变 |
| `IMPL-KEV-016` | 整理前策略章节（见归档）测试侧分层检索计分纯函数，已实施；不进入生产排序或历史判据 |
| `IMPL-KEV-017` | 已新增`knowledge/evidence/admission.py::ScoreAwareEvidenceSelector`及bootstrap.py内部版本参数；当前main显式绑定，复用Stage既有selector注入，旧builder和内部legacy默认不变 |

### 14.2 关键签名

```python
class KnowledgeEvidenceEgressDecider:
    def decide(
        self,
        *,
        bundle: KnowledgeEvidenceBundle,
        catalog: KnowledgeEgressPolicyCatalog,
    ) -> EvidencePolicyDecision: ...

class ExtractiveSummaryValidator:
    def validate(
        self,
        *,
        output: KnowledgeSummaryOutput,
        bundle: KnowledgeEvidenceBundle,
        limits: KnowledgeEvidenceLimits,
    ) -> SummaryValidationResult: ...

class DefaultKnowledgeEvidenceStage:
    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[RankedKnowledgeBatch],
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult: ...

@dataclass(frozen=True, slots=True)
class EffectMetricPopulation:
    summary_cases: tuple[EvaluatedCase, ...]
    quality_cases: tuple[EvaluatedCase, ...]
    answerable_count: int
    answerable_gold_issue_count: int

    @property
    def quality_coverage_rate(self) -> float: ...

    @property
    def valid(self) -> bool: ...

def derive_effect_metric_population(
    cases: tuple[EvaluatedCase, ...],
) -> EffectMetricPopulation: ...

def compute_metrics(
    cases: tuple[EvaluatedCase, ...],
    *,
    population: EffectMetricPopulation | None = None,
) -> EvaluationMetrics: ...

def classify_conclusion(
    *,
    metrics: EvaluationMetrics,
    safety: SafetyGateResult,
    snapshot: EvaluationSystemSnapshot,
    population: EffectMetricPopulation,
) -> Literal["effective", "partially_effective", "ineffective", "invalid_run"]: ...
```

`EffectMetricPopulation` 是 evaluation/Harness 内部合同，不进入生产 Runtime 或公共结果 DTO。`summary_cases` 只排除 `security_negative`；`quality_cases` 只包含 answerable 且人工 reason 非 `gold_issue` 的 primary case。live 与 stub runner 必须调用同一派生函数，并在分类结论前验证 `population.valid`；不得各自复制分母逻辑。caseResults 已携带 case ID 与人工 reason，故结果 Schema 无需为本次口径纠偏扩张。

## 15. 测试与验证设计

本节保留原组件与历史评估编号，旧task/coverage/准入细节只解释原实现；新在线见§9.5，资料见§19。不得从旧测试通过继承新版UAT。

### 15.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-KEV-001` | hash/snapshot/domain/policy ref 完整性和冲突：Evidence unit tests |
| `TEST-KEV-002` | 选择顺序、域覆盖、证据不足和 limits |
| `TEST-KEV-003` | 三层 allow/deny/missing/conflict 和模型零调用 |
| `TEST-KEV-004` | fresh Guard、context mismatch、timeout/cancel/failure 矩阵 |
| `TEST-KEV-005` | V1～V4 task、exact JSON、多要点/多域覆盖、缺证据退回 insufficient 和重复 ref；V1～V3 源码哈希保持不变 |
| `TEST-KEV-006` | quote 子串、控制字符、大小、引用和本地结果 |
| `TEST-KEV-007` | dataset/hash/loader、成对 executor、指标/Schema/invalid run：`agent-runtime/tests/evaluation/knowledge` |
| `TEST-KEV-008` | 历史 post-consumption/result/evidence 哈希和原效果结论不可变 |
| `TEST-KEV-009` | 历史指标/分布诊断 Schema、敏感字段禁止和历史 hash |
| `TEST-KEV-010` | 效果口径 v2 分母/数据质量 Gate、安全负例零调用、普通失败仍入分母及历史哈希 |
| `TEST-KEV-011` | Summary V4 fake 回归、安全 Gate 反证、manifest/预算/首 outbound/失败关闭及历史哈希 |
| `TEST-KEV-012` | authorization/consumed/journal/checkpoint/failure 精确哈希；启动前与结束时 allowlist 一致；额外 staged/modified/untracked 或 HEAD 变化继续失败关闭；历史运行不得重用 |
| `TEST-KEV-013` | 准备态 absence assertions 不进入授权后 live preflight；授权后预检接受唯一严格 authorization，并继续拒绝缺失、错绑及额外工作树变化 |
| `TEST-KEV-014` | 新 catalog exact Schema/hash/export/source revision、旧 catalog/hash 字节不变 |
| `TEST-KEV-015` | 附件 chunk 父 policy 继承、未知父/错 snapshot/冲突拒绝和 summary 零调用 |
| `TEST-KEV-016` | 候选全成员 policy 检查、发布后 Evidence/引用连续子串及历史 candidate 回归 |
| `TEST-KEV-018` | 新增 `tests/contract/knowledge/test_summary_task_v5.py` 与当前生产根集成测试；复用 `tests/unit/knowledge/evidence/test_summary_proof_boundaries.py`、stage失败矩阵；历史run-01～03和任务hash保持不可变 |
| `TEST-KEV-019` | V2匿名同父第四条入选、第九条拒绝、byte预算、必需域/锚点、错误版本/limits在summary前拒绝、legacy2/V1三条与policy/validator不变 |
| `TEST-KEV-020` | 整理前策略章节（见归档）需求标签、完整/不足、coverage错源/错域/漏项、预算与出域、精确输入类型及旧序列化；合成反例不冒充语义效果 |
| `TEST-KEV-021` | 整理前策略章节（见归档）单来源完整、多来源联合证明同一需求、定义不足、Prompt/decoder identity及当前根 |
| `TEST-KEV-022` | 整理前§9.2.1（见归档）覆盖拒绝的明确原因、深栈/恶意异常无数据访问、公开失败及成功行为不变 |
| `TEST-KEV-023` | 整理前策略章节（见归档）检索/回答分离、等价依据、缺料/未知/null、分级完整性、严格预算及有限证据复算 |
| `TEST-KEV-024` | `tests/unit/knowledge/test_evidence_admission.py`、`tests/integration/knowledge/test_evidence_admission_stage.py`、`test_evidence_admission_composition.py`及`tests/evaluation/knowledge/test_evidence_admission_rank_replay.py`：整理前策略章节（见归档）保序筛选、锚点/限额/严格输入、安全与legacy兼容；固定实际排序的开发/留出验证不冒充完整相关性 |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-KEV-001` | Evidence integrity/selection 定向测试通过 |
| `VAL-KEV-002` | 三层策略目录、出域零调用和 snapshot tests 通过 |
| `VAL-KEV-003` | Summary V4、validator、Stage、历史 V1～V3 hash 和 non-live 回归通过 |
| `VAL-KEV-004` | representative v2、历史成对运行、安全/人工 rubric/严格 Schema 与原效果结果持续通过不可变校验 |
| `VAL-KEV-005` | 功能 UAT 与效果结论分离、诊断可复现、最新有效效果等级如实记录为 `partially_effective` |
| `VAL-KEV-006` | 效果口径 v2 保留安全零调用和失败分母，Summary V4 覆盖多域直接证据，non-live 资产完整且无 outbound |
| `VAL-KEV-007` | 历史失败运行保持 append-only；Harness 前后快照复用唯一 allowlist，准备态和授权后预检不冲突且不放宽其他工作树变化 |
| `VAL-KEV-008` | 阶段 A 新索引的文档策略、snapshot 和 Evidence 兼容通过，旧策略目录与历史 evidence 哈希不变 |
| `VAL-KEV-010` | V5合同/生产根/Stage失败及历史回归、strict mypy、compileall通过；真实分类证明效果单独记为Evidence missing，不由non-live关闭 |
| `VAL-KEV-011` | 新V2选择/当前根与旧反例同时通过，strict mypy/全量non-live/历史hash通过；真实原文覆盖必须单独执行专项 |
| `VAL-KEV-012` | 整理前策略章节（见归档）新合同、当前根fake、历史/类型/全量Knowledge与Business、Spring回归及来源对应验收；不复用旧效果Passed |
| `VAL-KEV-013` | 整理前策略章节（见归档）定向、类型、Spring、隔离全量与不改gold的原十例专项；Prompt测试不替代真实效果 |
| `VAL-KEV-014` | 整理前§9.2.1（见归档）拒绝分类、恶意输入、成功/公开映射及Knowledge相关回归、类型检查 |
| `VAL-KEV-015` | 整理前策略章节（见归档）必要依据、相关性标注和有限历史复算；区分给定计划、真实规划与摘要结论 |
| `VAL-KEV-016` | 新selector/Stage/root定向pytest、strict mypy、compileall、Knowledge/Business/Core及历史回归；同池Evidence覆盖和相关性验证后才能考虑生产生效 |

## 16. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 可读即外发 | 跳过三层策略 | 独立 egress decision + 零调用测试 | 否 |
| 伪引用 | 模型改写/拼接 quote | exact substring + local citation construction | 否 |
| 重复引用 | 多点复用同一 ref | 当前版本 Prompt + validator 不放宽 | 否 |
| 策略/快照漂移 | 新文档或 index snapshot | fingerprint/full membership；新切片重验 | 否；真实外发需重新授权 |
| 效果结论失真 | 删除失败、改 gold/阈值 | 冻结数据/Schema/append-only result | 否 |
| 当前效果不足 | 最新有效运行的 Q3/Q4 未达标 | 保留 `partially_effective`；后续改进作为独立质量目标 | 不阻塞学习基线，但禁止“效果已 effective”声明 |
| live 状态合同冲突 | 授权后预检再次执行准备态 absence assertion | 分离准备态测试与授权后 live preflight；失败运行历史化 | 使该次测量无效，不自动触发新运行 |

## 17. 实施依据

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：§9组件已在当前工作树接线，完整验证和效果仍按P3_01/UAT_02推进 |
| 现行实现 | 起始Summary7及原Evidence保留原证明范围；当前工作树绑定Summary8/minimal Evidence，旧任务/P5按冻结版本解释 |
| 当前允许实施范围 | 当前独立目标按授权推进DR-KEV-201～205、301～304的剩余验证；真实测量须先冻结gold与预算 |
| 本轮权限 | 当前独立目标允许目标内代码、测试和文档及有界验证；不扩大公共合同、权限或历史运行资产 |
| 当前禁止动作 | 旧授权续用、重新消费候选、绕过完整性/出域/引用校验或声明整体效果通过 |
| 回滚单位 | 相容的Provider、Evidence实现、成对任务与配置；优先禁用Knowledge，旧证据不可改 |

## 18. v3.0评审记录

本轮仅整理文档，不继承旧评审。内审及正式分层、跨层复核的实际问题与结论见[整理记录](../历史文档/2026-09-14-unified-v3-baseline/MIGRATION.md)。整理前评审原样保存在归档；本轮为同一执行者分阶段复核，不冒充外部独立人员评审。

## 19. 资料表示与原文证据边界（部分离线组件已实施）

依据KQ-AD-025～028及L2_01_01 §18；§9当前Summary8已在仓库接线、目标Summary9待实施，真实验收未完成。本节不更改现有Evidence/Policy/引用validator、旧任务版本或公共返回字段。

`DR-KEV-301`：source dataset是采集/分发来源，官方URL才是发布来源线索，两者都不自动证明当前效力或读取/出域许可。仅有curated名称、标题或模型摘要而缺少可核查来源的材料，不能作为新的官方gold或适用性证明。保留既有库存和历史证据；新迁移范围须标source_unverified并补人工来源核验，不能借新的分类标签把未知资料认证为官方。许可声明需保留来源，不把数据卡声明扩成商业再分发授权。

`DR-KEV-302`：可引用content与检索context分别治理。标题、章节路径、父说明和重复表头可帮助检索，但不构成原文quote；只能引用实际已授权content的连续子串。跨chunk、跨表头/行或跨条款拼接不是连续原文，不得为了覆盖完整而放宽校验。需要多个片段时仍受既有唯一ref/条数/字节预算；当前公共合同无法表达完整表格或额外父读取时，返回既有不足边界并记录限制，不隐含新接口。

`DR-KEV-303`：库存contentHash、原始asset hash、标准化源hash、chunk body hash和embedding input hash含义不同。Java对实际content生成的hash仍是在线输入完整性依据，不能改用元数据hash或新向量hash。重切片后使用新chunk identity，原evidence与旧snapshot保持可追溯；新策略目录仅迁移相容身份/快照且不扩权。未知旧hash口径不等于篡改，也不能用于证明精确原文相同。

`DR-KEV-304`：成文日期仅作来源信息；当前源快照的active/pending不能替代当前核验。文档部分失效不证明某条款有效或失效；未知不是有效，也不是自动禁止查阅。资料查找允许受控返回相关原文线索；适用性肯定结论仍需明确期间、主体及直接规则证据。来源元数据未进入现有DTO时，不能在Prompt/结果中伪装已知；新时效展示/过滤另作公共合同评审。人工评估须把“片段引用合法”和“条件/期间有依据”分别评分。

`DR-KEV-302`的补充边界：离线完整结构单元可用于核对chunk是否遗漏条件、定义、例外或表头，但其存在不是在线Evidence，也不自动允许读取或外发。当前候选`content`仍是经授权返回的原文片段；派生标题/路径、重复表头和未取得的父单元均不能被引用。若未来另行批准受控补取，新增每个原文跨度须分别具备同版本来源、读取授权、完整性/hash和三层出域决策；模型只得到策略交集允许的有限内容，引用须指向实际返回、唯一且连续的原文片段。子块可读不推出父条款或附件可读；多span不能伪装为一个连续quote。必要定义/例外未取得、拒绝或预算不足时，不能只凭命中子块给出完整肯定回答。补取产生的正文仍计入既有Evidence/模型输入预算，不因此放宽条数、字节或validator；未批准的公共合同与失败映射详见L2_01_00 §19。

### 19.1 实施追踪（未执行）

#### 新设计编号定义

| 规则编号 | 实现编号 | 测试编号 | 验证编号 |
|---|---|---|---|
| DR-KEV-301、DR-KEV-302、DR-KEV-303、DR-KEV-304 | IMPL-KEV-301、IMPL-KEV-302、IMPL-KEV-303 | TEST-KEV-301、TEST-KEV-302、TEST-KEV-303 | VAL-KEV-301、VAL-KEV-302、VAL-KEV-303 |

#### 资料证据追踪

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-KEV-001、REQ-KEV-007、CON-KEV-003、KQ-AD-025/028 | DR-KEV-301 | IMPL-KEV-301：来源sidecar与后续人工gold准入；保留现policy/integrity | TEST-KEV-301：dataset/official/curated分离、来源未知及越权父关系 | VAL-KEV-301：来源人工核查及安全反例 |
| REQ-KEV-001、REQ-KEV-003、REQ-KEV-007、KQ-AD-027/028 | DR-KEV-302、DR-KEV-303 | IMPL-KEV-302：既有Evidence identity/substring测试补齐新chunk回放；不改validator | TEST-KEV-302：派生标题/表头不是quote、拼接拒绝、不同hash作用域及旧snapshot | VAL-KEV-302：unit/contract/fake及后续typed只读证明 |
| REQ-KQ-201/203/205、KQ-AD-026 | DR-KEV-304 | IMPL-KEV-303：后续UAT-KORG时效/充分性人工核对；不新增模型字段 | TEST-KEV-303：未知/部分失效、成文与生效不同、当前/历史期及合法却不充分引用 | VAL-KEV-303：功能安全与回答质量分列，不用模型自评代替人工 |

这些验证中的组件fake/non-live阶段已执行，具体范围见P3_01 §14.6～14.8与UAT_02 §3；当前root到隔离真实typed接口的单域只读预检不证明真实摘要、人工充分性或效果UAT，不得从设计条目推断通过。原完整设计评审与文档验证见历史P3_00 §22；后续验收由P3_01/UAT_02记录。
