# [L2_01_02] 单体 Agent Knowledge 证据、出域、摘要与效果验证详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_02` |
| 当前版本 | v1.1 |
| 日期 | 2026-08-21 |
| 权威范围 | 证据完整性/选择、三层出域、KnowledgeSummaryTaskV2、抽取式校验、本地结果和 P5 效果验证 |
| 上位文档 | [`L1_01` v1.0](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 来源文档 | [L2_01_02 v0.34 归档版](历史文档/2026-08-21-v0-baseline/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) |
| 实施状态 | Evidence/Policy/Summary v2 与真实 Knowledge 出域已验证；P5 有效 run 已完成且结论 `ineffective`；未生产生效 |

## 2. 阅读导航与变更记录

重点：第 7 节证据、第 8 节三层策略、第 9 节摘要校验、第 13 节 P5、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立证据与效果稳定基线 | 删除多代 candidate/Gate 流水，保留当前 v2 任务、不可变证据规则、正式 P5 方法和 `ineffective` 结论 |
| v1.1 | 2026-08-21 | 代码对照评审修复 | 将 Gateway 非超时异常收敛为有限 summary failure，并补充对应反证测试 |

## 3. 目标与范围

### 3.1 目标

只使用本次请求中已授权、完整性可证且允许外发的知识片段生成可引用摘要；模型输出必须是原文连续子串并通过确定性校验。效果验证复用同一生产 Capability，不建立第二套流程，并允许如实得出未达标结论。

### 3.2 范围内

- ranked candidate 完整性复核和确定性证据选择；
- Evidence Bundle、coverage、source 和 question trace；
- 全局规则∩逻辑域默认策略∩文档级收紧策略；
- Knowledge summary v1 兼容与 v2 生产任务；
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
| `REQ-KEV-003`、`CON-KEV-004` | `DR-KEV-007`、`DR-KEV-008`、`DR-KEV-009` | `IMPL-KEV-005`、`IMPL-KEV-006` | `TEST-KEV-005`、`TEST-KEV-006` | `VAL-KEV-003` |
| `REQ-KEV-004` | `DR-KEV-010`、`DR-KEV-011`、`DR-KEV-012` | `IMPL-KEV-007`、`IMPL-KEV-008` | `TEST-KEV-007`、`TEST-KEV-008` | `VAL-KEV-004` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Integrity Verifier | candidate/snapshot/hash/授权元数据一致性 | 首次业务授权 |
| Evidence Selector | 有界、确定性选择和 coverage | 模型出域决定 |
| Policy Catalog | 文档策略 artifact 的严格加载和版本快照 | 修改策略权威数据 |
| Egress Decider | 三层只收紧交集和最小 summary input | 模型 HTTP/效果评价 |
| Summary Task V2 | 固定 Prompt、JSON request/response task version | 放宽 validator |
| Extractive Validator | ref 唯一、quote 子串、大小和本地结果 | 语义扩写或模型纠错 |
| Evidence Stage | fresh Guard→verify→select→policy→model→validate 顺序 | 检索、Core answer |
| P5 Harness | 复用生产 Capability，采集有限阶段/指标/人工 rubric | 在线流程、gold 回填 |

依赖方向为 `Evidence Stage → evidence components + model Protocol`；P5 只依赖生产 Capability 和测试 collector。禁止生产代码依赖 evaluation；禁止 P5 复制流程或修改候选顺序。

这些组件按证据安全与效果验证内聚，不新增策略平台或独立服务。

## 6. 当前实现基线与最小变更

当前已有完整 Evidence contracts、integrity verifier、selector、代码绑定策略目录、三层 decider、summary v1/v2、extractive validator、Stage、representative v1/v2、严格 P5 loader/runner/Schema 和 append-only 历史测试。

Evidence Stage 必须在模型 Gateway 边界吸收非取消、非超时异常并映射为 `summary_failure`，不得让 Provider 异常细节越过 Stage 或退化为 Core 内部异常。

任何启用 Knowledge 的运行组合根只注册 `KnowledgeSummaryTaskV2`；默认包入口尚未装配 Knowledge Provider。v1 和历史 evidence 保持字节级兼容。当前 P5 candidate-04 是有效 run，安全 Gate 通过，但 Q1/Q3/Q4 未达标，结论为 `ineffective`。不建议为改善结论修改现有 evidence、gold、阈值或 validator；后续改进必须新版本、新 run。

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
| `DR-KEV-007` | summary v2 使用请求级 `e1..e8`，Prompt 强制 ref 两两不同且 quote 为连续原文 |
| `DR-KEV-008` | validator 不信任模型：unknown/duplicate ref、空/超长/控制字符/非子串 quote 均拒绝 |
| `DR-KEV-009` | 本地领域结果只由 validator 构造，包含抽取式摘要点、引用和 coverage；Core answer 不再调用模型 |
| `DR-KEV-010` | P5 primary 与 rewrite_ablation 每 case 各执行一次同一 Capability，除 rewriter 外完全相同 |
| `DR-KEV-011` | P5 数据集/gold/snapshot/版本/身份和阶段必须冻结；无效 run 不计算结论 |
| `DR-KEV-012` | 有效 run 按固定 Q1～Q4 与安全阈值得出 effective/partially_effective/ineffective，不改判 |

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

## 9. Knowledge Summary v2 接口契约设计与确定性校验

### 9.1 输出 Schema

允许两种 exact JSON：

```json
{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"原文连续片段"}]}
```

```json
{"outcome":"insufficient_evidence","points":[]}
```

answer 最多 5 点；每个 `evidence_ref` 只能使用一次。v2 只强化模型可见的唯一性指令，复用 v1 parser 和原 validator，公共 Stage/Core/HTTP 契约不变。

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
  → summary v2 within deadline
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
- summary task version 当前生产为 `2`；回滚只能把组合根显式切回 v1+stub，不改写 v1/v2 源码和历史 evidence。
- 禁用 Knowledge action 可完全停止真实检索/出域；无数据迁移。

## 13. P5 效果验证设计与当前结论

### 13.1 数据与执行

- 正式数据集：`representative_questions.v2.jsonl`，26 case；22 个普通案例继承 v1，只替换 4 个确定性安全负例。
- 每 case 顺序执行 primary、rewrite_ablation；各调用一次真实 `KnowledgeQueryCapability.handle`。
- primary 使用生产 rewriter；ablation 只换 `IdentityQuestionRewriter`，其他配置、Provider、授权、Profile/index snapshot、模型任务完全一致。
- collector 只旁路采集有限阶段 ID/排名/计数，不改变在线行为；结果不保存 question、content、quote、title、URL、JWT 或原响应。

### 13.2 有效 run 前提

clean frozen commit、live Provider、数据集/hash、principal/读取授权、四项前置安全证据、问题/域/flow/Profile/全部 index snapshots、BGE、task、DeepSeek、policy/evidence versions 全部冻结；52 个 capability 执行成对完整，retry/resume=0。任一缺失、dirty、变体不一致、安全计数非零或必需分母为空，结论为 `invalid_run`。

### 13.3 指标与阈值

| 问题 | 通过阈值 |
|---|---|
| 安全必备 | constraint preservation=1.0、citation validity=1.0、denied summary calls=0、unauthorized content=0 |
| Q1 改写/域 | rewrite rerank recall delta≥0、regression≤0.10、domain exact match≥0.85 |
| Q2 排序 | rerank recall@10≥0.80 且 rerank MRR@10≥fusion MRR@10 |
| Q3 忠实 | faithfulness≥0.95 |
| Q4 初始可用 | valid summary completion≥0.90 且 usefulness≥0.80 |

有效 run 中 Q1～Q4 全部通过=`effective`，至少两个但非全部=`partially_effective`，少于两个=`ineffective`。未达标项和 timeout/failure/no_result 均保留在分母规则内，不删除或改判。

### 13.4 人工 rubric

对 primary 的 answerable case 判断 faithful、relevant、sufficientForInitialAnswer、useful；reason 只允许 `none/quote_context/relevance/coverage/gold_issue`。评审时临时查看授权证据，提交布尔值后释放正文。

### 13.5 当前有效结论

当前 candidate-04：52 个 Capability 成对执行完整，实际付费 rewrite 22 + summary 36=58，retry/core answer=0，安全 Gate 通过；Q2 通过，Q1/Q3/Q4 未全部满足，正式结论 `ineffective`。这证明初步效果验证已完成且当前效果未达标，不授权声称效果达标。

权威结果：`agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/result.json`；有限证据：同目录 `evidence.json`。后续改进必须新 dataset/task/run version，保持当前结果 append-only。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-KEV-001` | `agent-runtime/src/agent_runtime/knowledge/evidence/builder.py`：integrity verifier、selector |
| `IMPL-KEV-002` | `agent-runtime/src/agent_runtime/knowledge/evidence/contracts.py`：Evidence/Bundle/limits/types |
| `IMPL-KEV-003` | `agent-runtime/src/agent_runtime/knowledge/evidence/catalog.py`：strict catalog、fingerprint |
| `IMPL-KEV-004` | `agent-runtime/src/agent_runtime/knowledge/evidence/policy.py`：`KnowledgeEvidenceEgressDecider.decide` |
| `IMPL-KEV-005` | `agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v2.py`：`KnowledgeSummaryTaskV2.definition` |
| `IMPL-KEV-006` | `agent-runtime/src/agent_runtime/knowledge/evidence/summary_validation.py`、`agent-runtime/src/agent_runtime/knowledge/evidence/stage.py` |
| `IMPL-KEV-007` | `agent-runtime/tests/evaluation/knowledge/contracts.py`、`executor.py`、`live_executor.py` |
| `IMPL-KEV-008` | `agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl`、`live_contracts.py`、result schemas |

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
```

## 15. 测试与验证设计

### 15.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-KEV-001` | hash/snapshot/domain/policy ref 完整性和冲突：Evidence unit tests |
| `TEST-KEV-002` | 选择顺序、域覆盖、证据不足和 limits |
| `TEST-KEV-003` | 三层 allow/deny/missing/conflict 和模型零调用 |
| `TEST-KEV-004` | fresh Guard、context mismatch、timeout/cancel/failure 矩阵 |
| `TEST-KEV-005` | v1/v2 task、exact JSON 和重复 ref：`agent-runtime/tests/contract/knowledge/test_summary_task_v2.py` |
| `TEST-KEV-006` | quote 子串、控制字符、大小、引用和本地结果 |
| `TEST-KEV-007` | dataset/hash/loader、成对 executor、指标/Schema/invalid run：`agent-runtime/tests/evaluation/knowledge` |
| `TEST-KEV-008` | candidate-04 post-consumption/history 哈希和 `ineffective` 结论不可变 |

### 15.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-KEV-001` | Evidence integrity/selection 定向测试通过 |
| `VAL-KEV-002` | 三层策略目录、出域零调用和 snapshot tests 通过 |
| `VAL-KEV-003` | summary v2、validator、Stage、历史 v1 hash 和非 live 回归通过 |
| `VAL-KEV-004` | representative v2、52 对/58 paid/安全/人工 rubric/严格 Schema 与当前 `ineffective` 结果持续通过历史校验 |

## 16. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 可读即外发 | 跳过三层策略 | 独立 egress decision + 零调用测试 | 否 |
| 伪引用 | 模型改写/拼接 quote | exact substring + local citation construction | 否 |
| 重复引用 | 多点复用同一 ref | v2 Prompt + validator 不放宽 | 否 |
| 策略/快照漂移 | 新文档或 index snapshot | fingerprint/full membership；新切片重验 | 否；真实外发需重新授权 |
| 效果结论失真 | 删除失败、改 gold/阈值 | 冻结数据/Schema/append-only result | 否 |
| 当前效果不足 | Q1/Q3/Q4 未达标 | 保留 `ineffective`，后续版本化改进 | 不阻塞学习基线，但阻塞“效果达标”声明 |

## 17. 实施依据

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前 v1.1 可作为 Evidence/Policy/Summary/P5 代码评审和后续版本化改进依据 |
| 当前允许实施范围 | 当前证据链、三层策略、summary v2、extractive validator、P5 非 live/history 验证 |
| 当前禁止动作 | 改写历史数据/evidence/结论、放宽 validator、未经新授权真实调用、宣称效果达标 |
| 回滚单位 | Evidence components + policy catalog + summary task binding；P5 历史结果永不回滚覆盖 |

## 18. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 证据、三层策略、summary v2 契约和追踪一致 | Passed |
| 内审 2 | 安全、错误分类、P5 有效性和 `ineffective` 结论一致 | Passed |
| 内审 3 | 真实落点、测试、当前证据引用和历史隔离检查通过 | Passed |
| 独立评审 | 未发现 S0/S1/S2；证据、三层出域、Summary v2、P5 方法与冻结结论一致 | Passed |

- 当前版本：v1.1。
- 文档状态：Approved。
- 当前 P5 结论为 `ineffective`；不得因新基线重写而改变。
