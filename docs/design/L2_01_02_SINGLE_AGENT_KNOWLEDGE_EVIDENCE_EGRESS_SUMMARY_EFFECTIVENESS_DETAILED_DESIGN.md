# [L2_01_02] 单体 Agent Knowledge 证据、出域、摘要与效果验证详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_02` |
| 当前版本 | v1.9 |
| 日期 | 2026-08-28 |
| 权威范围 | 证据完整性/选择、三层出域、KnowledgeSummaryTaskV1～V4、抽取式校验、本地结果和 P5 效果验证 |
| 上位文档 | [`L1_01` v1.8](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 来源文档 | [L2_01_02 v0.34 归档版](历史文档/2026-08-21-v0-baseline/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) |
| 实施状态 | Evidence/Policy、生产接线、功能 UAT、Summary V4 与效果口径 v2 已完成 non-live 实施和评审；candidate-05 保持 `partially_effective`，candidate-06 已完成非 live 冻结并等待精确授权 |

## 2. 阅读导航与变更记录

重点：第 7 节证据、第 8 节三层策略、第 9 节摘要校验、第 13 节 P5、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立证据与效果稳定基线 | 删除多代 candidate/Gate 流水，保留当前 v2 任务、不可变证据规则、正式 P5 方法和 `ineffective` 结论 |
| v1.1 | 2026-08-21 | 代码对照评审修复 | 将 Gateway 非超时异常收敛为有限 summary failure，并补充对应反证测试 |
| v1.2 | 2026-08-26 | 功能/效果验收分离与优化准备 | 固化 candidate-04 诊断维度、最小优化条件、新候选冻结和真实 outbound 授权边界 |
| v1.3 | 2026-08-26 | candidate-04 只读诊断落地 | 固化诊断指标与根因，新增 Summary v3 覆盖指令；不改 validator、检索参数、数据集或历史资产 |
| v1.4 | 2026-08-26 | 优化与候选收口 | 如实同步 Summary v3 已实施、candidate-05 已冻结及正式效果调用仍受 `GATE-072` 阻断 |
| v1.5 | 2026-08-26 | 效果 UAT 收口 | 固化 candidate-05 的 append-only 证据、Q1/Q2 通过、Q3/Q4 未通过及 `partially_effective` 结论 |
| v1.6 | 2026-08-28 | Summary 版本与状态纠偏 | 明确 Summary V3 是当前生产任务、V1/V2 仅为历史兼容，并修复实现清单和当前风险结论漂移 |
| v1.7 | 2026-08-28 | candidate-05 根因与评估口径修复 | 新增 Summary V4 多域直接证据覆盖和效果口径 v2；阈值、安全 Gate、validator、数据集、gold 与历史资产不变 |
| v1.8 | 2026-08-28 | 最小优化实施同步 | Summary V4、效果口径 v2、生产单绑定和 live/stub 统一 evaluator 已通过 non-live |
| v1.9 | 2026-08-28 | candidate-06 非 live 冻结 | 冻结新 run、92 项资产、manifest、预算、历史哈希与失败关闭；真实执行仍受 `GATE-077` 约束 |

## 3. 目标与范围

### 3.1 目标

只使用本次请求中已授权、完整性可证且允许外发的知识片段生成可引用摘要；模型输出必须是原文连续子串并通过确定性校验。效果验证复用同一生产 Capability，不建立第二套流程，并允许如实得出未达标结论。

### 3.2 范围内

- ranked candidate 完整性复核和确定性证据选择；
- Evidence Bundle、coverage、source 和 question trace；
- 全局规则∩逻辑域默认策略∩文档级收紧策略；
- Knowledge Summary V1～V3 历史兼容与 V4 当前生产任务；
- evidence ref、quote 子串、引用唯一性、结果大小和本地领域结果；
- representative v2、primary/rewrite_ablation、指标、人工 rubric、严格结果 Schema 和明确结论。

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

| 约束编号 | 来源与约束 |
|---|---|
| `CON-KEV-001` | `L0_00 SA-C-009/011/018/021` |
| `CON-KEV-002` | `L1_01`：用户可读不等于模型可见，未分类/冲突失败关闭 |
| `CON-KEV-003` | `L2_01_01`：输入候选已读取授权并绑定 Profile/index/read-policy snapshot |
| `CON-KEV-004` | `L2_00_02`：模型是不可信 Provider，任务版本与 transport 分离 |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-KEV-001`、`CON-KEV-003` | `DR-KEV-001`、`DR-KEV-002`、`DR-KEV-003` | `IMPL-KEV-001`、`IMPL-KEV-002` | `TEST-KEV-001`、`TEST-KEV-002` | `VAL-KEV-001` |
| `REQ-KEV-002`、`CON-KEV-001`、`CON-KEV-002` | `DR-KEV-004`、`DR-KEV-005`、`DR-KEV-006` | `IMPL-KEV-003`、`IMPL-KEV-004` | `TEST-KEV-003`、`TEST-KEV-004` | `VAL-KEV-002` |
| `REQ-KEV-003`、`CON-KEV-004` | `DR-KEV-007`、`DR-KEV-008`、`DR-KEV-009`、`DR-KEV-016`、`DR-KEV-017` | `IMPL-KEV-005`、`IMPL-KEV-006` | `TEST-KEV-005`、`TEST-KEV-006` | `VAL-KEV-003` |
| `REQ-KEV-004` | `DR-KEV-010`、`DR-KEV-011`、`DR-KEV-012`、`DR-KEV-018` | `IMPL-KEV-007`、`IMPL-KEV-008` | `TEST-KEV-007`、`TEST-KEV-008`、`TEST-KEV-010` | `VAL-KEV-004`、`VAL-KEV-006` |
| `REQ-KEV-005`、`REQ-KEV-006` | `DR-KEV-013`、`DR-KEV-014`、`DR-KEV-015`、`DR-KEV-019` | `IMPL-KEV-009` | `TEST-KEV-009`、`TEST-KEV-010`、`TEST-KEV-011` | `VAL-KEV-005`、`VAL-KEV-006` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Integrity Verifier | candidate/snapshot/hash/授权元数据一致性 | 首次业务授权 |
| Evidence Selector | 有界、确定性选择和 coverage | 模型出域决定 |
| Policy Catalog | 文档策略 artifact 的严格加载和版本快照 | 修改策略权威数据 |
| Egress Decider | 三层只收紧交集和最小 summary input | 模型 HTTP/效果评价 |
| Summary Task V2/V3 | 固定 Prompt、JSON request/response task version；v3 增加独立子问题覆盖指令 | 放宽 validator |
| Extractive Validator | ref 唯一、quote 子串、大小和本地结果 | 语义扩写或模型纠错 |
| Evidence Stage | fresh Guard→verify→select→policy→model→validate 顺序 | 检索、Core answer |
| P5 Harness | 复用生产 Capability，采集有限阶段/指标/人工 rubric | 在线流程、gold 回填 |

依赖方向为 `Evidence Stage → evidence components + model Protocol`；P5 只依赖生产 Capability 和测试 collector。禁止生产代码依赖 evaluation；禁止 P5 复制流程或修改候选顺序。

这些组件按证据安全与效果验证内聚，不新增策略平台或独立服务。

## 6. 当前实现基线与最小变更

当前已有完整 Evidence contracts、integrity verifier、selector、代码绑定策略目录、三层 decider、summary v1/v2/v3、extractive validator、Stage、representative v1/v2、严格 P5 loader/runner/Schema 和 append-only 历史测试；生产组合根当前使用 v3。

Evidence Stage 必须在模型 Gateway 边界吸收非取消、非超时异常并映射为 `summary_failure`，不得让 Provider 异常细节越过 Stage 或退化为 Core 内部异常。

启用 Knowledge 的当前生产组合根只注册 `KnowledgeSummaryTaskV4`，不能并行注册两代任务。V1～V3 和历史 evidence 保持字节级兼容。candidate-04 是历史有效 run 且结论为 `ineffective`；candidate-05 是最新有效 run，安全 Gate 通过、Q1/Q2 通过、Q3/Q4 未通过，结论为 `partially_effective`。不得为改善结论修改既有 evidence、gold、阈值或 validator；后续效果结论必须建立新 run。

## 7. 证据构建与选择

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KEV-001` | 逐 candidate 验证 content SHA-256、domain、Profile/index/read-policy snapshot 和当前计划成员 |
| `DR-KEV-002` | evidence ID 由 document/chunk/content hash 确定性生成，不使用模型 ref 或可变排名 |
| `DR-KEV-003` | 选择按 rerank 顺序、领域覆盖和固定 limits 确定，证据不足返回 no_result，不调用 summary |
| `DR-KEV-004` | 新鲜 Question Guard 拒绝优先，拒绝时 verify/select/policy/model 调用均为 0 |
| `DR-KEV-005` | 出域集合为全局规则∩所有相关域策略∩文档策略，任何 deny/缺失/冲突拒绝 |
| `DR-KEV-006` | 每次允许决定绑定 policy catalog、authority/export/source revision、文档策略和 index snapshot fingerprint |
| `DR-KEV-007` | Summary V2～V4 使用请求级 `e1..e8`，Prompt 强制 ref 两两不同且 quote 为连续原文 |
| `DR-KEV-008` | validator 不信任模型：unknown/duplicate ref、空/超长/控制字符/非子串 quote 均拒绝 |
| `DR-KEV-009` | 本地领域结果只由 validator 构造，包含抽取式摘要点、引用和 coverage；Core answer 不再调用模型 |
| `DR-KEV-010` | P5 primary 与 rewrite_ablation 每 case 各执行一次同一 Capability，除 rewriter 外完全相同 |
| `DR-KEV-011` | P5 数据集/gold/snapshot/版本/身份和阶段必须冻结；无效 run 不计算结论 |
| `DR-KEV-012` | 有效 run 按固定 Q1～Q4 与安全阈值得出 effective/partially_effective/ineffective，不改判 |
| `DR-KEV-013` | 功能 UAT 与效果 UAT 独立；功能通过不关闭效果达标，`ineffective` 有效 run 不改判 |
| `DR-KEV-014` | 后续优化必须由最新不可变有效候选的有限指标/逐 case 分布支持，形成新 Prompt/config/selection/Harness 版本；不得改变历史、gold、validator 或阈值 |
| `DR-KEV-015` | 新效果候选必须冻结 task/Prompt/code/Profile/index/policy/dataset/provenance、预算和 append-only Schema；精确授权前模型 outbound 为 0 |
| `DR-KEV-016` | Summary v3 在不改 parser/validator/Schema 的前提下，要求对可由不同证据独立回答的条件、日期、税率和主体类型逐项覆盖；最多 5 个唯一 ref，单条证据足够时不增加冗余引用 |
| `DR-KEV-017` | Summary V4 继承 V3 全部安全约束；问题含多个独立要点或 evidence 跨多个适用逻辑域时，每个有直接证据的要点/域至少采用一个非重复 ref，任一显式要点或适用域缺少直接证据则输出 `insufficient_evidence`，禁止部分肯定回答 |
| `DR-KEV-018` | 效果口径 v2 仅从 summary completion 分母排除必须零模型调用的 `security_negative`；普通无结果、证据不足、失败和超时仍计入。answerable 的显式 `gold_issue` 从 faithfulness/usefulness 模型质量分母排除并单独计数；质量可评样本不足原 answerable 集合的 90% 时整次 run 无效 |
| `DR-KEV-019` | candidate-06 必须冻结 Summary V4、效果口径 v2 实现和测试哈希；Q1～Q4 阈值、安全 Gate、dataset/gold、人工 rubric 枚举和 append-only 历史合同均不变 |

### 7.2 完整性复核

`EvidenceIntegrityVerifier.verify(input)` 检查：

- ranked batch 与 selected domains/coverage 一致；
- candidate identity 唯一且属于本次检索结果；
- content hash 重算一致；
- domain IDs、profile/index/read-policy snapshot 完整且与 batch 集合一致；
- policy ref、source 元数据和文本满足类型/长度限制。

失败统一进入 `evidence_failure`，不把损坏候选降级为可用子集。

### 7.3 选择与 Bundle

Selector 最多选择 8 条证据，优先保持 rerank 顺序并覆盖选中域；构造 `QuestionEvidenceTrace`、`EvidenceCoverage`、`KnowledgeEvidenceBundle`。若 answerability 所需域/最小证据不满足，返回 `insufficient_evidence`。

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

只发送 Guard 最小化问题、coverage 两个布尔值和最多 8 条 `SummaryEvidenceInput(evidence_ref, content, optional metadata)`；不发送 JWT、subject、内部 document ID、content hash、策略细节、Profile、index 或原始 Provider 响应。

## 9. Knowledge Summary V2～V4 接口契约设计与确定性校验

### 9.1 输出 Schema

允许两种 exact JSON：

```json
{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"原文连续片段"}]}
```

```json
{"outcome":"insufficient_evidence","points":[]}
```

answer 最多 5 点；每个 `evidence_ref` 只能使用一次。V2 强化模型可见的唯一性指令；V3 增加独立条件/子问题逐项覆盖。V4 进一步读取 payload 中已允许的 `domain_ids`：对于问题显式要求的独立要点以及 evidence 中存在直接支持的每个适用逻辑域，必须各选择一个非重复 ref；若任一显式要点或适用域没有直接证据，返回 `insufficient_evidence`，不得只回答其中一部分。单条证据完整覆盖全部问题时仍只使用一个 ref。V4 继续复用 V1 parser 和原 validator，公共 Stage/Core/HTTP/Schema、最多 5 点、原文连续子串及模型出域字段均不变。

### 9.2 Validator

校验顺序：outcome/points 组合→点数→ref 存在→ref 唯一→quote NFC→非空→≤quote limit→无控制字符→是对应 content 的连续子串→answer/result bytes 上限。

内部诊断 reason 仅用于测试/受控诊断：`outcome_points_mismatch`、`point_count_invalid`、`unknown_evidence_ref`、`duplicate_evidence_ref`、`quote_empty`、`quote_too_long`、`quote_control_character`、`quote_not_substring`、`answer_too_large`、`result_too_large`。公共调用方只看到 `knowledge.summary_failure`，不看到内容或诊断分支。

### 9.3 本地结果

Validator 构造 `summaryType=extractive_evidence`、`answerSummary`、points（quote+citation）和 coverage。citation 使用本地 evidence ID、domain、title/source/document metadata；模型不能提供或修改这些可信引用字段。

## 10. Evidence Stage 核心流程、错误分类与调用方可见语义

```text
question denied flag / fresh Guard
  → integrity verify
  → deterministic select
  → three-layer egress decide
  → require matching ModelCallContext
  → current summary task within deadline (target V4)
  → strict parse + extractive validate
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
| 合法抽取式结果 | `success` | 1 |

不自动 retry/resume；失败不调用 Core answer，也不返回模型原文本。

## 11. 权限、安全、审计与一致性

- Fresh Guard 与三层策略均必须允许；任何拒绝短路后续模型调用。
- Evidence 只在请求内存使用；JWT、API key、subject、正文、quote、Prompt 和原响应不持久化到运行日志/有限 evidence。
- 日志记录阶段、有限 reason、证据/域数量、policy fingerprint、状态、耗时和调用计数；不记录正文或策略详细值。
- deadline/cancellation 传播；取消后不接受迟到摘要。
- 无数据库事务；策略目录随 Runtime 生命周期冻结，运行中不热更新。

## 12. 配置、发布与回滚

- `KnowledgeEvidenceLimits.v1()` 代码绑定证据数、quote、payload 和结果上限；配置不能放宽。
- 策略目录 artifact 随代码发布，启动严格加载；内容变化必须新 version/export/source revision 并重跑快照/出域测试。
- 当前生产实现已唯一绑定独立 Summary V4；V1～V3 保留历史兼容、冻结资产验证与可追溯回滚责任。回滚优先禁用 Knowledge；若显式恢复已验证旧任务绑定，必须形成新配置快照，不改写任何既有 task 源码和历史 evidence。
- 禁用 Knowledge action 可完全停止真实检索/出域；无数据迁移。

## 13. P5 效果验证设计与当前结论

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

### 13.5 当前有效结论

当前 candidate-04：52 个 Capability 成对执行完整，实际付费 rewrite 22 + summary 36=58，retry/core answer=0，安全 Gate 通过；Q2 通过，Q1/Q3/Q4 未全部满足，正式结论 `ineffective`。这证明初步效果验证已完成且当前效果未达标，不授权声称效果达标。

权威结果：`agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/result.json`；有限证据：`agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/evidence.json`。后续改进必须新 dataset/task/run version，保持当前结果 append-only。

当前 candidate-05：52 个 Capability 成对执行完整，实际付费 rewrite 22 + summary 22=44，retry/core answer=0，安全 Gate 通过；Q1、Q2 通过，Q3、Q4 未通过，正式结论为 `partially_effective`。domain exact match=0.8636、rerank recall@10=0.9643、required evidence coverage=0.7024、summary valid completion=0.8462、faithfulness=0.9286、usefulness=0.7143。权威结果 SHA-256=`a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb`；该结论不得改述为整体效果达标。

### 13.6 历史候选只读诊断合同

诊断输入只允许读取指定历史候选的冻结 result/evidence、代表性数据集元数据、gold 引用和现有有限阶段结果；不得修改或重新执行该 run。输出必须至少包含：

- Q1：domain exact match、primary/ablation rerank recall delta 与 regression；
- Q2：keyword/vector path hit、fusion/rerank recall@10 与 MRR@10；
- Q3：required evidence coverage、faithfulness、gold_issue/coverage reason；
- Q4：summary valid completion、usefulness、no_result/insufficient_evidence/downstream_failure 分布；
- 每个根因的分类、受影响 case 数、证据强度和最小可改接缝。

诊断产物不得保存 question、正文、quote、原始模型响应、JWT 或策略明文。若有限历史结果不足以证明某根因，应标记 `insufficient_diagnostic_evidence`，不能凭推测修改生产算法。

### 13.7 candidate-05 诊断、最小优化与 candidate-06 准备

允许的新版本接缝仅限 Prompt、域安全描述、Retrieval Profile 逻辑参数、RRF/rerank 有界参数、Evidence 选择或 evaluation Harness。选择优化时必须满足：

1. 直接对应诊断中的失败指标或 case 分布；
2. 不修改 typed HTTP、公共 Stage/Core/HTTP、读取/出域权限或 extractive validator；
3. fake/历史反证证明不会降低安全 Gate；
4. 新旧版本可并存，历史 source/hash 可继续验证；
5. 变更无法由授权范围解决时停止，不为关闭效果门禁降低阈值。

candidate-06 已在功能 UAT Passed、candidate-05 根因明确、Summary V4/效果口径 v2 non-live 通过后完成准备。run ID=`knowledge-p5-live-v3-20260828-candidate-06`，manifest SHA-256=`7f54ddff600726d364edee6f7c6939d99c52aa5b533ac309d98887b6e8cc51b8`，authorization reference=`P3_00:GATE-077`，最大付费请求数=78。manifest 绑定 representative dataset/provenance、primary/rewrite_ablation、任务/Prompt/source、evaluator source/tests、域/Profile/全部 index snapshot、BGE、policy/evidence、candidate-01～05 历史 hash、首个 outbound 消费、retry/resume=0 和失败关闭，共 92 项资产。准备阶段未读取 `LLM_API_KEY`、未产生 outbound；正式执行仍由独立 `GATE-077` 精确授权。

正式授权记录是用户精确授权后生成的运行资产，不进入 manifest 的源码/配置资产集合，避免形成“授权文件必须先进入 frozen HEAD、而其内容又依赖该 HEAD”的循环。执行时仅允许该 candidate-06 授权记录作为唯一未跟踪文件；必须经严格 JSON 校验并同时绑定 frozen HEAD、manifest SHA-256、run/reference/budget/dataset/live 标志，launcher 参数、授权记录与运行时读取结果任一不一致都失败关闭；任何其他 staged、modified 或 untracked 项仍按 dirty source 失败关闭。授权记录在首次 outbound 前由既有 consumed marker 消费，运行后与结果一并作为 append-only 证据保存。

candidate-05 已按 frozen HEAD=`63bc30baa68948a35840b650c0deb39d1e312efa`、manifest SHA-256=`41997c6d41f3109b178844c9b74799bb59c869ae06ec23aca66bea1a6f1e278c` 唯一执行；authorization、paid journal、phase checkpoints、result、evidence 和 launcher evidence 均作为 append-only 资产保存。历史 candidate-01～04 保持不可变。

本次只读诊断已形成可复现产物 `candidate_04_effect_diagnosis.v1.json`：domain exact match=0.5909、rerank recall@10=0.9405、required evidence coverage=0.4643、summary valid completion=0.6923，Q1/Q3/Q4 未通过。9 个域不一致 case 中，5 个政策问题被全域扩大、1 个明确法律问题被弱政策词扩大、1 个混合问题漏选法律；另 2 个虚构文件 case 的“期望零域”属于数据/gold 口径，不由 Selector 猜测真实性。由此只批准域目录 v2 和 Summary v3；不批准修改 RRF/rerank、validator、数据集或 gold。

candidate-05 的只读诊断产物为 `candidate_05_effect_diagnosis.v1.json`，绑定 result SHA-256=`a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb`：

- 4 个 `security_negative` 正确零 Summary 调用，却被历史 completion 分母计为失败，导致安全兼容理论上限为 22/26=0.8462；因此批准效果口径 v2 的分母修复；
- 1 个 answerable case 在 fusion/rerank/required evidence coverage 均为 1.0 时被人工明确标为 `gold_issue`，证明其失败不能归因于模型质量；因此只批准带 90% 数据质量 Gate 的显式排除，不修改该 case/gold；
- 3 个 mixed case 因 coverage 不足而不 useful，其中 2 个 rerank recall=1.0 但只采用 1 条 evidence，且对照 mixed case 能采用 2 条，证明 Summary 多域/多要点覆盖指令不足；因此批准 Summary V4；
- 另 1 个 mixed case 的 fusion/rerank recall 仅 0.5，现阶段证据不足以批准 RRF/rerank/Profile 调参。先验证 Summary-only 变更，仍失败再单独诊断检索；
- 不批准修改 validator、权限、出域策略、dataset/gold、Q1～Q4 阈值或历史候选。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-KEV-001` | `agent-runtime/src/agent_runtime/knowledge/evidence/builder.py`：integrity verifier、selector |
| `IMPL-KEV-002` | `agent-runtime/src/agent_runtime/knowledge/evidence/contracts.py`：Evidence/Bundle/limits/types |
| `IMPL-KEV-003` | `agent-runtime/src/agent_runtime/knowledge/evidence/catalog.py`：strict catalog、fingerprint |
| `IMPL-KEV-004` | `agent-runtime/src/agent_runtime/knowledge/evidence/policy.py`：`KnowledgeEvidenceEgressDecider.decide` |
| `IMPL-KEV-005` | 已新增 `agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v4.py` 与 `KnowledgeSummaryTaskV4.definition`，并由生产组合根唯一绑定；V1～V3 源码和历史绑定保持不可变 |
| `IMPL-KEV-006` | `agent-runtime/src/agent_runtime/knowledge/evidence/summary_validation.py`、`agent-runtime/src/agent_runtime/knowledge/evidence/stage.py` |
| `IMPL-KEV-007` | `agent-runtime/tests/evaluation/knowledge/contracts.py`、`executor.py`、`live_executor.py` |
| `IMPL-KEV-008` | `agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl`、`live_contracts.py`、result schemas |
| `IMPL-KEV-009` | `agent-runtime/tests/evaluation/knowledge`：candidate-04/05 有限诊断、效果口径 v2、版本化优化反证与 candidate-06 preparation/history tests |

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
| `TEST-KEV-008` | candidate-04 post-consumption/history 哈希和 `ineffective` 结论不可变 |
| `TEST-KEV-009` | candidate-04 指标/分布诊断 Schema、敏感字段禁止和历史 hash |
| `TEST-KEV-010` | candidate-05 只读诊断重算、效果口径 v2 分母/数据质量 Gate、安全负例零调用、普通失败仍入分母及历史哈希 |
| `TEST-KEV-011` | Summary V4 fake 回归、安全 Gate 反证、candidate-06 manifest/预算/首 outbound/失败关闭及 candidate-01～05 历史哈希 |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-KEV-001` | Evidence integrity/selection 定向测试通过 |
| `VAL-KEV-002` | 三层策略目录、出域零调用和 snapshot tests 通过 |
| `VAL-KEV-003` | Summary V4、validator、Stage、历史 V1～V3 hash 和 non-live 回归通过 |
| `VAL-KEV-004` | representative v2、candidate-04 的 52 对/58 paid/安全/人工 rubric/严格 Schema 与历史 `ineffective` 结果持续通过不可变校验 |
| `VAL-KEV-005` | 功能 UAT 与效果结论分离、诊断可复现、candidate-05 唯一执行有效且结论为 `partially_effective` |
| `VAL-KEV-006` | 效果口径 v2 保留安全零调用和失败分母，Summary V4 覆盖多域直接证据，candidate-06 non-live 资产完整且无 outbound |

## 16. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 可读即外发 | 跳过三层策略 | 独立 egress decision + 零调用测试 | 否 |
| 伪引用 | 模型改写/拼接 quote | exact substring + local citation construction | 否 |
| 重复引用 | 多点复用同一 ref | 当前版本 Prompt + validator 不放宽 | 否 |
| 策略/快照漂移 | 新文档或 index snapshot | fingerprint/full membership；新切片重验 | 否；真实外发需重新授权 |
| 效果结论失真 | 删除失败、改 gold/阈值 | 冻结数据/Schema/append-only result | 否 |
| 当前效果不足 | candidate-05 的 Q3/Q4 未达标 | 保留 `partially_effective`，后续只允许基于新版本和新候选改进 | 不阻塞学习基线，但阻塞“效果达标”声明 |

## 17. 实施依据

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前 v1.9 可作为 Evidence/Policy/Summary、功能/效果 UAT 分离、诊断和后续版本化改进依据 |
| 当前允许实施范围 | 当前证据链、三层策略、Summary V4、效果口径 v2、extractive validator、功能 UAT、candidate-05 只读诊断与 candidate-06 non-live 准备 |
| 当前禁止动作 | 改写历史数据/evidence/结论、放宽 validator、未经新授权真实调用、宣称效果达标 |
| 回滚单位 | Evidence components + policy catalog + summary task binding；P5 历史结果永不回滚覆盖 |

## 18. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 证据、三层策略、summary v2 历史兼容契约和追踪一致 | Passed |
| 内审 2 | 安全、错误分类、P5 有效性和 candidate-04 历史 `ineffective` 结论一致 | Passed |
| 内审 3 | 真实落点、测试、当前证据引用和历史隔离检查通过 | Passed |
| 独立评审 | 未发现 S0/S1/S2；证据、三层出域、Summary v2、P5 方法与冻结结论一致 | Passed |
| v1.2 聚焦评审 | 功能/效果分离、历史不可变、诊断证据、优化边界和 GATE-072 授权无环；无 S0/S1/未处理 S2 | Passed |
| v1.3 内审 1 | 诊断指标、历史不可变和最小优化映射 | Passed |
| v1.3 内审 2 | v3 与 v2 parser/validator/公共契约兼容、域选择职责 | Passed |
| v1.3 内审 3 | candidate-05 依赖、GATE-072 无环和个人项目最小治理 | Passed |
| v1.3 独立评审 | 无 S0/S1/未处理 S2；只批准域目录 v2 和 Summary v3 | Passed |
| v1.6 三轮内审与独立复评 | V3 当前生产、V1/V2 历史兼容、candidate-04/05 结论及后续新候选门禁一致；无 S0/S1/未处理 S2 | Passed |
| v1.7 三轮内审与独立评审 | candidate-05 分母/归因冲突、Summary V4、多候选历史隔离和 candidate-06 门禁无环；无 S0/S1/未处理 S2 | Passed |
| v1.9 三轮内审与独立评审 | 首轮修复范围节仍称 V3 当前生产一项 S2；代码评审修复授权文件与 clean HEAD 循环、授权记录未强绑定实际 HEAD/manifest 两项 Major，复评确认 candidate-06 92项绑定、唯一运行授权资产、V4/效果口径 v2、历史不可变和 GATE-077 无环；无 S0/S1/未处理 S2 | Passed |

- 当前版本：v1.9。
- 文档状态：Approved。
- candidate-04 历史结论为 `ineffective`；candidate-05 当前结论为 `partially_effective`，两者均不得重写或改判。
