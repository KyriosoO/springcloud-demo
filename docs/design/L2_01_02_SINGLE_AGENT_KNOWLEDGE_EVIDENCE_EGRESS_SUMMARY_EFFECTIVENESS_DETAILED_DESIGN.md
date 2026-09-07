# [L2_01_02] 单体 Agent Knowledge 证据、出域、摘要与效果验证详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_02` |
| 当前版本 | v1.21 |
| 日期 | 2026-09-07 |
| 权威范围 | 证据完整性/选择、三层出域、KnowledgeSummaryTaskV1～V6（V6为当前生产绑定）、抽取式校验、本地结果和 P5 效果验证 |
| 上位文档 | [`L1_01` v1.20](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 本次增量 | DR-KEV-029/030已实施并成对接线，生产Summary6/quality-v3；组件与完整对象图non-live证据归P3 §20.39～20.40，真实效果待验证 |
| 来源文档 | [L2_01_02 v0.34 归档版](历史文档/2026-08-21-v0-baseline/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) |
| 实施状态 | Evidence/Policy、Summary V6/quality-v3生产接线及non-live已完成；旧功能UAT、效果口径v2及阶段A快照保持原证明范围。新版真实效果未验证、完整专项未通过；最新有效P5仍为`partially_effective`，具体候选、门禁和证据由UAT_01/P3/evidence管理 |

## 2. 阅读导航与变更记录

重点：第 7 节证据、第 8 节三层策略、第 9 节摘要校验、第 13 节 P5、第 14 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.21 | 2026-09-07 | 引用合法与问题覆盖缺少可核对关联 | 设计需求锚点预算及Summary6严格coverage，保留旧任务/输入序列化/抽取validator，公共结果与出域权限不改 |
| v1.20 | 2026-09-04 | 同一规范性文件的必要第四条款可能被文档配额排除 | DR-KEV-028与quality_v2()取消独立父文档配额，保持总8/32KB、域覆盖、出域和引用限制，历史V1不改 |
| v1.19 | 2026-09-04 | 用户确认分类上下文证明要求后恢复执行 | 新增DR-KEV-027及Summary V5实施/测试映射；保留V4、公共Schema、validator和gold，区分指令合同验证与真实语义效果 |
| v1.0 | 2026-08-21 | 建立证据与效果稳定基线 | 保留证据、策略、摘要、严格校验和正式 P5 方法 |
| v1.12 | 2026-08-28 | 效果收口与 Harness 状态合同纠偏 | 移除多代候选/Gate/哈希流水；明确有效测量与效果等级分离，并拆分准备态和授权后 live 预检 |
| v1.13 | 2026-09-02 | 阶段 A Evidence 兼容 | 冻结新索引 snapshot 与版本化文档策略目录迁移规则；附件沿用父文档读取/出域策略并保留 asset/chunk 溯源，既有 Summary/validator 不变 |
| v1.14 | 2026-09-02 | 阶段 A Evidence 收口 | 同步 catalog v2/current loader、5600 文档全成员校验、candidate a2 snapshot 与14/14专项 UAT；catalog v1和历史 evidence 不变 |
| v1.15 | 2026-09-03 | 阶段 A 当前快照迁移 | 将 candidate a4 的 policy/law snapshot 追加到现行 catalog v2，保留所有旧 snapshot；5600 文档全成员、读取授权和 Evidence 连续子串合同复评通过 |
| v1.16 | 2026-09-03 | 阶段 A 最终快照迁移 | 将 candidate a5 的 policy/law snapshot 追加到现行 catalog v2 并作为当前启动绑定；candidate a4 与更早 snapshot 继续保留，5600 文档全成员及 Evidence 合同不变 |

## 3. 目标与范围

### 3.1 目标

只使用本次请求中已授权、完整性可证且允许外发的知识片段生成可引用摘要；模型输出必须是原文连续子串并通过确定性校验。效果验证复用同一生产 Capability，不建立第二套流程，并允许如实得出未达标结论。

### 3.2 范围内

- ranked candidate 完整性复核和确定性证据选择；
- Evidence Bundle、coverage、source 和 question trace；
- 全局规则∩逻辑域默认策略∩文档级收紧策略；
- Knowledge Summary V1～V5 历史兼容与 V6 当前生产任务；
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
| `REQ-KEV-004` | `DR-KEV-010`、`DR-KEV-011`、`DR-KEV-012`、`DR-KEV-018`、`DR-KEV-020`、`DR-KEV-021`、`DR-KEV-022` | `IMPL-KEV-007`、`IMPL-KEV-008`、`IMPL-KEV-010` | `TEST-KEV-007`、`TEST-KEV-008`、`TEST-KEV-010`、`TEST-KEV-012`、`TEST-KEV-013` | `VAL-KEV-004`、`VAL-KEV-006`、`VAL-KEV-007` |
| `REQ-KEV-005`、`REQ-KEV-006` | `DR-KEV-013`、`DR-KEV-014`、`DR-KEV-015`、`DR-KEV-019` | `IMPL-KEV-009` | `TEST-KEV-009`、`TEST-KEV-010`、`TEST-KEV-011` | `VAL-KEV-005`、`VAL-KEV-006` |
| `REQ-KEV-007`、`CON-KEV-003` | `DR-KEV-023`、`DR-KEV-024`、`DR-KEV-025` | `IMPL-KEV-011` | `TEST-KEV-014`、`TEST-KEV-015`、`TEST-KEV-016` | `VAL-KEV-008` |
| `REQ-KEV-003`、`CON-KEV-001`、`CON-KEV-004`；`L1_01 KQ-AD-017` | `DR-KEV-027` | `IMPL-KEV-012`、`IMPL-KEV-006` | `TEST-KEV-018` | `VAL-KEV-010` |
| `REQ-KEV-001`、`CON-KEV-003`；`KQ-AD-014` | `DR-KEV-028` | `IMPL-KEV-001`、`IMPL-KEV-002`：builder版本校验、limits新工厂和bootstrap成对绑定 | `TEST-KEV-019`：第四同文档条款、总8/字节、域覆盖、错配/未知版本、三层出域及历史cap | `VAL-KEV-011`：Evidence/current root/历史反例、全量non-live及专项原文覆盖 |
| `REQ-KEV-001`、`REQ-KEV-002`、`REQ-KEV-003`、`CON-KEV-001`、`CON-KEV-003`、`CON-KEV-004`；`KQ-AD-018` | `DR-KEV-029`、`DR-KEV-030` | `IMPL-KEV-013` | `TEST-KEV-020` | `VAL-KEV-012` |

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

## 6. 当前实现基线与最小变更

当前已有Evidence contracts、integrity verifier、selector、三层decider、Summary V1～V6、需求coverage validator、extractive validator、Stage和历史P5工具；生产组合根当前唯一使用V6。V1～V5及历史P5合同保持原证明范围。

Evidence Stage 必须在模型 Gateway 边界吸收非取消、非超时异常并映射为 `summary_failure`，不得让 Provider 异常细节越过 Stage 或退化为 Core 内部异常。

启用Knowledge的当前生产组合根只注册`KnowledgeSummaryTaskV6`，不能并行注册两代任务。V1～V5和历史evidence保持字节级兼容。最新有效P5效果等级为`partially_effective`，不代表当前V6效果；不得修改既有evidence、gold、阈值或validator。运行身份、历史结论和哈希由UAT_01/evidence管理。

## 7. 证据构建与选择

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KEV-001` | 逐 candidate 验证 content SHA-256、domain、Profile/index/read-policy snapshot 和当前计划成员 |
| `DR-KEV-002` | evidence ID 由 document/chunk/content hash 确定性生成，不使用模型 ref 或可变排名 |
| `DR-KEV-003` | 按版本化可信锚点、领域覆盖及最终确定性排序选Evidence；最多8条/32768bytes不变；V2不设独立父文档配额，V1每文档3条、legacy每文档2条；缺少必需域或证据返回no_result且summary0 |
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
| `DR-KEV-019` | 每次新效果运行必须冻结当前批准的Summary任务版本（当前V6）、效果口径 v2 实现和测试哈希；Q1～Q4 阈值、安全 Gate、dataset/gold、人工 rubric 枚举和 append-only 历史合同均不变 |
| `DR-KEV-020` | live bootstrap 必须输出本次候选精确允许的运行时工作树条目；启动前和结果写入前的最终快照检查必须复用同一 allowlist，仅忽略当前 output 目录与该候选唯一未跟踪 authorization 记录。任何其他 staged、modified、untracked 条目或 HEAD 变化仍失败关闭；已消费候选不得通过修复后重跑 |
| `DR-KEV-021` | 准备态测试可以断言正式 authorization/result 不存在，但只能在授权记录创建前执行；live launcher 已要求严格 authorization 存在后，不得再次运行任何“authorization 必须不存在”的准备态断言。授权后预检只校验绑定、冻结资产、预算、安全和历史不可变 |
| `DR-KEV-022` | 一次合同有效且完整的效果运行关闭“效果已测量”责任，四类效果等级是输出；`effective` 是质量改进目标而非项目硬关闭条件。非 effective 不自动创建新候选，`invalid_run` 表示未形成测量且只能作为新的独立目标处理 |
| `DR-KEV-023` | 阶段 A 附件 chunk 使用父 `documentId` 参与现有 policy resolve，并保留独立 asset/version/relation 定位；父绑定缺失、policyRef 冲突或 snapshot 不允许时 Evidence 构造失败且 summary 调用为 0 |
| `DR-KEV-024` | 新发布必须使用新文件名和 catalog/export/source revision/hash；旧 `egress-policy-catalog.json` 及其 loader/hash 保持可验证，新目录只保留原 disposition/allowed fields/content limit，并增加对应新逻辑 snapshot |
| `DR-KEV-025` | 候选 alias 生效前必须对所有候选 `documentId + policyRef + indexSnapshotId` 做全成员检查；发布后抽样构造 Evidence 并通过连续子串 validator，不得用 Profile 切换掩盖策略缺口 |
| `DR-KEV-027` | §9.4新Summary V5要求原文支持相关显式分类上下文，最小充分引用与既有硬边界不变；语义由模型理解、本地只验证完整性，fake不能证明真实效果 |
| `DR-KEV-028` | §7.3及文末V2：取消独立父文档配额，版本/limits匹配，保留域覆盖、总8/32768bytes、三层出域与引用校验 |
| `DR-KEV-029` | §9.5已实施需求锚点完整性、同预算选择及包含需求的实际出域载荷计量 |
| `DR-KEV-030` | §9.5已实施Summary6类型及coverage精确合同，源/域/引文绑定后仍执行旧抽取validator |

### 7.2 完整性复核

`EvidenceIntegrityVerifier.verify(input)` 检查：

- ranked batch 与 selected domains/coverage 一致；
- candidate identity 唯一且属于本次检索结果；
- content hash 重算一致；
- domain IDs、profile/index/read-policy snapshot 完整且与 batch 集合一致；
- policy ref、source 元数据和文本满足类型/长度限制。

失败统一进入 `evidence_failure`，不把损坏候选降级为可用子集。

### 7.3 选择与 Bundle

Selector最多选择8条证据，先按最终rank选择可信retrieval_anchor（V2≤选中域数，V1≤2×选中域数），再补足每个selected domain，最后按最终rank填充。同一identity只使用一次；V2不因parent document相同额外排除第四条及后续相关条款，仍受总8条和32768bytes限制。预算无法保留必需域/锚点时返回insufficient_evidence，不能静默丢失必需项后肯定回答。普通填充候选超字节限制时跳过该项并继续尝试后续更小候选，扫描最多20条；full才停止。三层出域仍在选择后独立执行，拒绝不靠替换文档绕过。构造QuestionEvidenceTrace时使用原问题而非改写词作为回答范围。

本节V2历史增量将V2计划与 `KnowledgeEvidenceLimits.quality_v2()`成对注入；当前V3成对合同见§9.5；该内部工厂只把max_per_document设为总数上限8，其余limit完全复用v1。这表示取消额外文档配额，不是增加总Evidence或出域预算。旧quality_v1()仍为3、v1()仍为2，均保留历史测试；不修改Summary任务。测试必须证明同文档第四条按rank入选、第九条仍不入选、必需域/锚点不丢失、字节及全部出域和引用限制不变。错误相关性/必要条款排在前8之外仍是效果风险，不能据此自动扩容、添加行业规则或宣称语义完整。

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

### 9.4 Summary V5分类上下文证明增量

`DR-KEV-027`依据KQ-AD-017：新任务继承V4全部安全及多要点规则，并明确以下语义顺序：

1. 依据原问题识别所问对象、定义及与答案相关的显式分类归属；不能把问题中的归属直接当事实，也不展开无关分类或行业背景。
2. 在本次允许的Evidence中分别寻找直接支持；分类清单须保留足以识别类别与成员关系的连续上下文，不能只摘孤立关键词证明归属。
3. 一段连续原文若同时支持全部要点，使用一个ref；分散在不同Evidence时使用多个不同ref。不得为了凑双引用增加冗余点。
4. 证据缺失、冲突、只有模型常识可补充，或在总5点/每点512字符/唯一ref约束下无法完整证明时，输出exact `insufficient_evidence`。同一ref内多个不连续片段不能拼接、重复引用或通过扩展长度绕过。

实现仅新增`knowledge/evidence/summary_task_v5.py::KnowledgeSummaryTaskV5.definition()`，用V4公开definition/build_request复用严格输入和parser，通过不可变替换仅更新`task_version="5"`及Prompt。不导入旧私有helper、不修改V1～V4源码。输入类型及双层预算不变：序列化Evidence输入JSON为32768bytes/1～8条，Model任务外层max_input_bytes为49152；输出1536tokens、任务timeout和取消传播不变。固定SystemInstruction仍满足Model层既有8192bytes上限。该V5增量当时的`bootstrap.KnowledgeCompositionRoot`只绑定Rewrite6与Summary5；当前成对绑定见§9.5，并拒绝旧Summary装配；无环境开关或请求内版本fallback。disabled不创建任务/client。

validator仍仅按§9.2验证，合法单引用不会被本地语义规则拒绝；`coverage`仍为输入检索覆盖，不等于最终答案覆盖。不新增公共DTO、模型payload字段、模型复核调用、行业词面分支或检索/出域调整。单靠Prompt/fake不能证明模型遵循语义，真实专项缺口继续由P3/UAT_01管理。

测试分两层：non-live验证Prompt要求、输入/parser预算不变、单/多引用合法性、重复/未知/拼接引用拒绝、insufficient/model failure/timeout/cancel及下游计数、唯一生产绑定和旧源码hash；真实UAT在新的未消费授权后按冻结问题与原双条款判据验证，不修改失败case/gold，不以fake语义结果冒充通过。历史运行测试只在测试作用域加载冻结旧根，生产守卫不得放开。回滚优先禁用Knowledge；如恢复旧绑定，回退对应源码和新配置快照，不能改历史或单请求切换。

### 9.5 需求锚点与Summary V6覆盖合同（已实施并接线，真实效果待验证）

`DR-KEV-029`承接DR-KFLOW-024及DR-KRET-029：Evidence完整性先校验请求需求、quality-v3、候选requirement_ids和所属域。每个需求ID最多落在一个候选；V3锚点总数≤4，标记和coverage_anchor一致；错误ID/域/重复映射为evidence_failure，Summary0。合法计划某需求无候选、预算装不下必需锚点时返回insufficient_evidence、Summary0，不伪造技术失败或丢弃需求。最终先按rank保留全部需求锚点，再按既有顺序填充；必须覆盖全部请求需求及选中域，仍最多8证据/32768bytes、每父文档≤总8。

`KnowledgeEvidenceLimits.quality_v3()`新内部工厂的六个数值与quality_v2相同；它表达同预算的新策略，不以工厂对象identity判断配对。配对由代码quality_version、Summary definition版本/输入类型、需求存在性共同校验。Verifier把已验证标签传到`VerifiedKnowledgeCandidate`，Selector消费后不把候选标签当作模型证据或蕴含结论；bundle可继续使用既有字段，需求沿EvidenceInput在同请求保存。旧quality和输入默认均不改变。

预算必须包括**最终模型payload的全部需求及JSON结构**：V3 Selector计算最大候选投影时，在既有可见元数据上加入固定schema_version=2及请求requirements；每次try_add和最终检查使用同一新增V6规范序列化函数。三层策略返回的实际字段只能比最大投影更少，Stage在模型前再次校验真实payload≤32768bytes。不得只计算正文而漏算需求，不得截断正文/focus或提高预算。必需项超限为insufficient，普通填充项可按原规则跳过；policy拒绝仍优先于生成，不能换文档绕过。

`DR-KEV-030`新增`KnowledgeSummaryTaskV6`（task_id=knowledge_summary、version=6）：继承V5的抽取、分类上下文及无常识/无部分回答语义，但使用独立精确输入/输出。新`KnowledgeRequirementSummaryInput`为既有`KnowledgeSummaryInput`的frozen/slots内部子类型，增加不可变requirements；原基类**不增加字段**，防止旧`summary_input_json(asdict(...))`改变历史载荷。Stage仅在已允许policy.summary_input上构造该子类型，schema_version=2，requirements严格等于本次EvidenceInput；旧任务不能消费此子类型。新序列化器只发送原允许投影及需求ID/kind/domain/focus，不发送候选标签、内部源ID/hash/策略/JWT。domain为问题计划的逻辑域，不绕过文档DOMAIN_IDS可见性；即使文档域字段被策略省略，本地仍可用已授权bundle核对归域，不把该字段再补发给模型。

V6 exact输出为以下二者之一：

```json
{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"原文连续片段"}],"coverage":[{"requirement_id":"r1","evidence_refs":["e1"]}]}
```

```json
{"outcome":"insufficient_evidence","points":[],"coverage":[]}
```

answer仍1～5个唯一point，quote仍≤512；coverage为1～4个exact对象，每个需求一项，refs为1～5个唯一e1..e8。每一引用须出现在points；所有points必须被至少一个coverage引用；相同point可证明多个需求，不重复输出同一ref的多个point。覆盖映射只声明“这些**实际输出的quote**合起来直接证明该需求”，不能使用未引用全文/邻接条款证明。需求按输入顺序输出，不增删、改写或另选较容易的需求。任一需求缺少直接证据、冲突或预算内无法完整证明，必须输出insufficient，而不是少填coverage。

新内部`KnowledgeRequirementSummaryOutput`继承原输出并增加`tuple[SummaryRequirementCoverage,...]`；旧输出基类/parser不改。新exact decoder拒绝未知/重复键、null、错误类型、错误outcome组合和非法ref形状。新增`RequirementCoverageValidator.validate(output, requirements, summary_input, bundle) -> KnowledgeSummaryOutput`为同步、零I/O边界：核对需求tuple与实际输入一致，ID顺序/全集、refs去重/集合相等、实际policy模型输入的eN到bundle evidenceId/片段/hash/content对应，以及每个ref的bundle域包含需求域。未知/错源/错域/缺项为既有INVALID_SUMMARY；成功后构造原`KnowledgeSummaryOutput`交给**原封不动的ExtractiveSummaryValidator**验证唯一引用、NFC/子串、长度、结果预算和本地citation。insufficient的空列表合法，经原validator进入既有no_result；不能将非法coverage静默改成合法insufficient。

V6使用同一ModelGateway一次Summary调用，不增加复核模型；模型输入上限32KiB、任务外层49152bytes、输出1536tokens、任务15秒和系统指令8192bytes不变。Stage仍fresh Guard→verify→select→policy→context→model→coverage→extractive→result，不复制流程；版本错配在Summary前失败，取消不吞掉、不重试。新definition.input_type必须精确为KnowledgeRequirementSummaryInput，build_request接受既有基类泛型并显式检查实际新子类型，parse_response返回新输出子类型；ModelGateway现有type(input) is definition.input_type检查不变。Stage消费输出时也检查新子类型，不能为了绕过类型检查作不受检cast或把JSON塞入原question/evidence字段。旧任务收到新子类型、V6收到旧基类均在模型outbound前INPUT_DENIED。公开HTTP结果结构、coverage检索含义、错误码和Spring DTO不变。

本地只能验证**声明完整且引用来自所需域**，不能证明quote蕴含需求，也不能修复Rewrite错误识别lookup/applicability或漏掉实际问题。这些属于模型与原文UAT责任；不能把r1..rN齐全当作语义通过。检索anchor也不构成自动coverage。现有来源对应验收工具仍只在离线评分后使用gold，不能被在线validator导入。

验收兼容接缝：既有测试专用stage-b-citation-binding-v1只接受schema_version=1，保持源码及原测试不变。已新增测试专用`tests/system_e2e/knowledge_stage_b_citation_check_v2.py`，版本stage-b-citation-binding-v2；入口必须精确接受KnowledgeRequirementSummaryInput/schema2，先拒绝错误类型、bool/schema、非法需求基础形状，再把**同一实际policy投影**的question/coverage/evidence原样构成原基类schema1，只为复用V1已有零I/O来源对应算法。转换不得取回被policy删除的字段、换正文/引用、加载历史模型输入或凭quote反推来源；不忽略V1任何来源校验。它仅评价来源/预定原文，与生产coverage validator及人工语义评分分开；requirements不是gold，不能据此改验收必要条款。版本2须有真实新输入经该投影仍能拒绝同文错源、错chunk/篡改metadata的fake当前根测试；未接入新执行合同前不能声称新真实UAT已具备该校验。不得直接放宽V1的schema1检查接受任意版本。

`IMPL-KEV-013`（已实施）：新增`evidence/summary_task_v6.py`及`evidence/requirement_validation.py`；内部类型置于evidence/contracts.py，源需求类型仅引用knowledge/contracts.py；builder消费候选标签并使用新payload预算函数；stage对V3在同一流程执行新类型构造及coverage validator；bootstrap全套单绑定。policy目录、decider授权算法、旧Summary1～5源码/序列化函数、summary_validation.py、公共DTO及历史数据保持不变。

`TEST-KEV-020`（已实现`tests/contract/knowledge/test_summary_task_v6.py`、`tests/unit/knowledge/evidence/test_requirement_coverage.py`及当前根集成）：同域不同需求首位/重复anchor去重、4需求/8证据/32KiB包含需求开销、空需求错配、漏ID/增ID/重复ID/错域/错ref/同文不同来源、point未被使用、仅全文含答案而quote不支持的语义保留反例；合法一引文覆盖多需求、多来源联合支持、insufficient、非法/超时/取消、三层拒绝Summary0、旧输入序列化/任务hash不变。对语义反例不伪称本地能自动识别，人工原文评分应判失败。`VAL-KEV-012`要求新合同与生产对象图fake、现有子串/权限/Knowledge/Business历史全量、类型和Spring回归；新真实效果仍待有权限的独立验证，不复用已消费运行。

## 10. Evidence Stage 核心流程、错误分类与调用方可见语义

```text
question denied flag / fresh Guard
  → integrity verify
  → deterministic select
  → three-layer egress decide
  → require matching ModelCallContext
  → current summary task within deadline (current V5)
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

- `KnowledgeEvidenceLimits.v1()/quality_v1()/quality_v2()/quality_v3()`按计划版本代码绑定配额；总8/32768bytes、quote及结果上限不变。当前V3只用匹配的quality_v3工厂，历史V2仍配quality_v2，配置不能扩大总预算。
- 策略目录 artifact 随代码发布并严格加载；内容变化必须创建新资源、新 version/export/source revision/hash 并重跑全成员和出域测试。旧资源、常量及历史 manifest 继续独立可验证，不得原位改写。
- 当前生产实现唯一绑定Summary V6；V1～V5保留历史兼容、冻结资产验证与可追溯回滚责任。回滚优先禁用Knowledge；若显式恢复旧任务绑定，必须整套配对并形成新配置快照，不改写既有task源码和历史evidence。
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

### 13.5 当前有效结论与收口语义

当前最新有效效果等级为 `partially_effective`：安全 Gate 已通过，但并非 Q1～Q4 全部达标。该高层结论可供架构和设计判断使用；候选 ID、调用次数、逐项指标、manifest、证据路径与 SHA-256 只由 UAT_01/evidence 保存，不在 L2 复制。

一次合同有效、数据完整且安全 Gate 通过的 P5 运行即完成“效果已测量”。`effective`、`partially_effective`、`ineffective` 是测量输出，不作为反复创建候选的项目硬门禁。`invalid_run` 不形成效果测量，只能记录为失败终态；是否重新准备必须作为新的独立目标明确决策，不能自动重跑、补跑或续跑。

### 13.6 历史运行只读诊断合同

诊断输入只允许读取指定历史候选的冻结 result/evidence、代表性数据集元数据、gold 引用和现有有限阶段结果；不得修改或重新执行该 run。输出必须至少包含：

- Q1：domain exact match、primary/ablation rerank recall delta 与 regression；
- Q2：keyword/vector path hit、fusion/rerank recall@10 与 MRR@10；
- Q3：required evidence coverage、faithfulness、gold_issue/coverage reason；
- Q4：summary valid completion、usefulness、no_result/insufficient_evidence/downstream_failure 分布；
- 每个根因的分类、受影响 case 数、证据强度和最小可改接缝。

诊断产物不得保存 question、正文、quote、原始模型响应、JWT 或策略明文。若有限历史结果不足以证明某根因，应标记 `insufficient_diagnostic_evidence`，不能凭推测修改生产算法。

### 13.7 最小优化与新运行准备

允许的新版本接缝仅限 Prompt、域安全描述、Retrieval Profile 逻辑参数、RRF/rerank 有界参数、Evidence 选择或 evaluation Harness。选择优化时必须满足：

1. 直接对应诊断中的失败指标或 case 分布；
2. 不修改 typed HTTP、公共 Core/HTTP、读取/出域权限或 extractive validator；KQ-AD-018/§9.5单独批准后可演进Knowledge请求内Stage数据与模型任务合同，三个Stage Protocol方法签名不变，不涉及Java/HTTP公共DTO；此前“不改公共Stage”的局部Prompt优化边界不能被解释为禁止已授权的内部计划演进，也不授权外部接口扩张；
3. fake/历史反证证明不会降低安全 Gate；
4. 新旧版本可并存，历史 source/hash 可继续验证；
5. 变更无法由授权范围解决时停止，不为关闭效果门禁降低阈值。

新运行准备必须冻结 representative dataset/provenance、primary/rewrite_ablation、任务/Prompt/source、evaluator source/tests、域/Profile/index snapshot、BGE、policy/evidence、既有历史哈希、首个 outbound 消费、retry/resume=0 和失败关闭。正式 authorization 是运行资产，不进入其所绑定的 frozen source 集合；它必须严格绑定 frozen HEAD、manifest、run/reference/budget/dataset/live 标志并作为唯一允许的未跟踪运行文件。

准备态测试和授权后 live 预检必须分阶段：准备态可证明 authorization/result 尚不存在；正式 authorization 创建后，launcher 只能执行绑定、冻结资产、预算、安全、历史和 fail-closed 校验，不能再次执行“authorization 必须不存在”的断言。任何运行失败均按是否已发生首次 outbound 区分 `failed_unconsumed` 或 `failed_consumed`，形成有限 append-only 证据后停止。

## 14. 实现落点清单

### 14.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-KEV-001` | `agent-runtime/src/agent_runtime/knowledge/evidence/builder.py`：integrity verifier、selector |
| `IMPL-KEV-002` | `agent-runtime/src/agent_runtime/knowledge/evidence/contracts.py`：Evidence/Bundle/limits/types |
| `IMPL-KEV-003` | `agent-runtime/src/agent_runtime/knowledge/evidence/catalog.py`：strict catalog、fingerprint |
| `IMPL-KEV-004` | `agent-runtime/src/agent_runtime/knowledge/evidence/policy.py`：`KnowledgeEvidenceEgressDecider.decide` |
| `IMPL-KEV-005` | 历史独立 `agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v4.py` 与 `KnowledgeSummaryTaskV4.definition`；V1～V4 源码和历史绑定保持不可变，当前唯一生产绑定见 `IMPL-KEV-012` |
| `IMPL-KEV-006` | `agent-runtime/src/agent_runtime/knowledge/evidence/summary_validation.py`、`agent-runtime/src/agent_runtime/knowledge/evidence/stage.py` |
| `IMPL-KEV-007` | `agent-runtime/tests/evaluation/knowledge/contracts.py`、`executor.py`、`live_executor.py` |
| `IMPL-KEV-008` | `agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl`、`live_contracts.py`、result schemas |
| `IMPL-KEV-009` | `agent-runtime/tests/evaluation/knowledge`：历史有限诊断、效果口径 v2 与版本化优化反证 |
| `IMPL-KEV-010` | `agent-runtime/tests/evaluation/knowledge/live_bootstrap.py`、`live_runner.py`、`live_contracts.py`、版本化 preparation/history/contracts/launcher |
| `IMPL-KEV-011` | `agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v2.json` 与 current/legacy 双加载接缝；阶段 A policy catalog 生成器和全成员 validator 位于 `knowledge-corpus-tools`。全新官方父文档只能选择既有同域 policy，禁止新增 disposition、放宽字段上限或扩大角色 |
| `IMPL-KEV-012` | 已新增 `agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v5.py`；已修改 `bootstrap.KnowledgeCompositionRoot.task_definitions/build_provider` 的唯一Summary绑定和版本守卫；旧task/validator只读，non-live验证见P3 §20.17 |
| `IMPL-KEV-013` | 已实施§9.5 Summary6/coverage validator及内部子类型；修改builder/Stage/当前根配对；保持旧serializer、policy及extractive validator |

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
| `TEST-KEV-020` | §9.5需求标签、完整/不足、coverage错源/错域/漏项、预算与出域、精确输入类型及旧序列化；合成反例不冒充语义效果 |

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
| `VAL-KEV-012` | §9.5新合同、当前根fake、历史/类型/全量Knowledge与Business、Spring回归及来源对应验收；不复用旧效果Passed |

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

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，DR-KEV-029/030已评审实施，成对接线及non-live通过；整体真实UAT仍未完成，见P3 §20.40 |
| 当前允许实施范围 | §9.5需求选择/新载荷/覆盖validator及测试专用Schema2来源适配；保留旧V1～V5和安全算法。已消费真实授权不复用，剩余总预算不构成新批次权限 |
| 当前禁止动作 | 改写历史资产、自动重跑/补跑/续跑、放宽 validator/权限/阈值、未经新独立目标精确授权真实调用、宣称效果已 effective |
| 回滚单位 | Evidence components + policy catalog + summary task binding；P5 历史结果永不回滚覆盖 |

## 18. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| v1.12 内审 1～3 | 效果测量/等级分离、preparation/live preflight 状态合同、历史不可变、门禁无环和无权限扩张检查完成；修复两项计划状态矛盾 | Passed |
| v1.14 对照复评 | catalog v2/current loader、5600 文档 full-membership、旧 catalog 精确哈希、读取授权、Evidence连续子串及14/14专项 UAT一致；S0=0、S1=0、未处理S2=0 | Passed |
| v1.15 对照复评 | candidate a4 新 policy/law snapshot 分别覆盖 5463/137 个文档，目录与索引 5600 个 document 全成员一致；旧 catalog/snapshot 保留，S0=0、S1=0、未处理 S2=0 | Passed |
| v1.16 对照复评 | candidate a5 新 policy/law snapshot 分别覆盖 5463/137 个文档，目录与索引 5600 个 document 全成员一致；a4 及旧 catalog/snapshot 保留，读取授权和 Evidence 连续子串复核通过，S0=0、S1=0、未处理 S2=0 | Passed |
| v1.12 独立评审 | Summary V4、效果口径 v2、candidate-07 无效测量及 DR-KEV-021/022 与当前代码/计划边界一致；S0=0、S1=0、未处理 S2=0 | Passed |
| v1.13 内审 1～3与独立评审 | 附件父策略继承、新旧目录隔离、snapshot 全成员、Evidence 连续子串和无权限扩张检查通过；S0=0、S1=0、未处理 S2=0 | Passed |

- 当前版本：v1.21；DR-KEV-029/030已评审实施及成对接线，当前生产V6；真实效果待验证。
- 文档状态：Approved；DR-KEV-027/028三轮内审和只读独立复评通过，允许本切片非live实施；记录归P3_00 §20.17，不代表真实效果通过。
- 最新有效效果等级为 `partially_effective`；历史运行身份和原结论由 UAT_01/evidence 维护，均不得重写或改判。

## 阶段 B 增量实施追踪

| 来源 | 设计 | 实现落点 | 测试 | 验证 |
|---|---|---|---|
| `REQ-KQUALITY-001～004`；`KQ-AD-013～016` | `DR-KEV-026` | knowledge/evidence/builder.py；stage注入质量策略limits；policy/SummaryV4合同不扩张 | `TEST-KEV-017`：锚点必需覆盖、质量同文档3/legacy同文档2/总8/字节边界、全选中域、超大非必需项跳过、出域拒绝summary0、Summary原问及引用validator不变 | `VAL-KEV-009`：Evidence单元/契约/集成、当前生产根和UAT_01阶段B；历史37项功能和P5原结论不外推 |

DR-KEV-026治理历史V1；v1.20目标为下述V2，在设计复评前不得实施。旧调用默认保持legacy，历史任务/证据不修改。UAT使用独立阶段B命名空间，验收标准和执行状态归UAT_01/P3。

`DR-KEV-026`：只有本地可信排序阶段可设置锚点；外部 DTO/模型不可注入。保留全部锚点及所有选中域的 Evidence 覆盖，同时满足质量策略每文档3/总8/32768字节上限；无法同时满足时返回 insufficient_evidence，不丢必需项来换表面成功。历史 legacy batch 默认无锚点，继续原选择语义。

`DR-KEV-028`：V2沿用verify→select→policy→model→validate，按§7.3取消额外父文档配额，计划quality_version必须与limits工厂匹配；V2错配或未知版本在summary前作为evidence_failure拒绝。只有可信本地rerank首位可设置V2锚点，每个非空域最多一个、重复identity去重，最终数量≤域数；完整性校验、域覆盖、同identity唯一、32768bytes、8条/5points/512quote、三层出域均不变。父文档策略仍逐条适用，绝不因同父复用而跳过授权/出域检查。quality_v2仅用于当前根；legacy和V1原限额/测试保持原语义。

版本化取舍不是放宽安全validator：每文档3条是降低内容集中度的质量启发式，会在单份规范包含多个必要条款时造成已证实的损失；移除其独立限制仍有总条数及字节界。错误高排名和单文档集中风险必须由真实专项如实记录。所有新反例用匿名合成正文，不用gold参与在线选择；V2已实施并通过non-live边界验证；真实专项未测量，不能提前声称效果通过。
