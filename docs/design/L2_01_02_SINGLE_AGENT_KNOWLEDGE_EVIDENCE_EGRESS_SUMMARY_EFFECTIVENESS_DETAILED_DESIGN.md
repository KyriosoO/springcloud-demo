# [L2_01_02] 单体 Agent Knowledge 证据、出域、摘要与效果验证详细设计

> 文档层级：L2
> 文档状态：Approved（仅步骤一职责收敛定向复评；实施、部署与UAT证明范围不扩大）

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_02` |
| 当前版本 | v3.10 |
| 日期 | 2026-10-06 |
| 权威范围 | 证据完整性/选择、三层出域、当前Summary9及历史任务追溯、严格引用及有限回答、本地结果和 P5 历史效果验证边界 |
| 上位文档 | [`L1_01` v3.9](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 本次变更 | v3.10补齐历史分离、Summary9现行职责与追踪；当前安全、输入输出和验收证明范围不变 |
| 实施状态 | 本目标起始Evidence/Policy、Summary V7/quality-v3接线有原定向non-live证据；当前仓库已接线Summary9/Evidence minimal，组件fake/non-live及Spring→Runtime合成三模式、失败分支已验证。单域当前root到隔离真实typed接口仅有有限只读预检，不证明真实模型、完整新版UAT、实际部署或回答效果。新版风险状态以UAT_02为准；旧功能UAT、效果口径v2及阶段A快照保持原证明范围；最新有效P5仍为`partially_effective`，历史资产不改；新计划P3_01/UAT_02不继承通过 |
| 归档来源 | [整理前 v1.27 原文](历史文档/2026-09-14-unified-v3-baseline/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |

本文件纳入新的统一文档版本序列；v3.0不是软件、API、模型任务、配置或索引版本。原版本及字节归档见上表。评审状态、实施状态、部署状态和UAT状态分别判断；历史通过不自动覆盖新合同。

修改历史：历次修订与评审原文见[历史附件](L2_01_02_REVISION_HISTORY_2026-10-06.md)。本次仅作历史分离及引用整理，不改变规范合同。附件不构成当前合同、状态或授权；当前合同以正文为准，实施及验收分别以P3_01/UAT_02为准。

## 2. 阅读导航

重点阅读§7/8完整性与出域、§9当前Summary9、§13历史评估入口、§19资料原文边界。历次修订及旧评审只见归档；当前Summary9已在仓库接线，真实质量与完整新版UAT仍见P3_01/UAT_02；旧实现定义仅用于历史解释和迁移，不要求现行运行时保留旧任务兼容，不作为第二套目标权威。

## 3. 目标与范围

### 3.1 目标

只使用本次请求中已授权、完整性可证且允许外发的知识片段生成可引用结果；每点quote必须是原文连续子串并通过确定性校验，解释/适用性claim仅能作直接原文支持的有界回应。效果验证复用同一生产 Capability，不建立第二套流程，并允许如实得出未达标结论。

### 3.2 范围内

- ranked candidate 完整性复核和确定性证据选择；
- Evidence Bundle、coverage、source 和 question trace；
- 全局规则∩逻辑域默认策略∩文档级收紧策略；
- Knowledge Summary V9当前仓库任务；V1～V8仅作历史解释；
- evidence ref、quote 子串、引用唯一性、结果大小和本地领域结果；
- 当前验收的指标、人工rubric、严格结果Schema及明确结论；representative v2和primary/rewrite_ablation只解释历史合同，不是当前运行前置。
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
| `REQ-KEV-004` | 现行分维度验收记录阶段、人工判断、安全和明确结论；原P5只作历史追溯 |
| `REQ-KEV-005` | 功能验收与效果验收独立，历史 `ineffective` 只作为诊断基线 |
| `REQ-KEV-006` | 只有证据支持的新版本可进入新候选；精确授权前真实 outbound 为 0 |
| `REQ-KEV-007` | 新语料发布必须形成新策略目录和 snapshot 绑定；附件不得绕过父文档读取/出域策略，历史目录不可变 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-KEV-001` | `L0_00 §5/§8；SA-AD-004/005` |
| `CON-KEV-002` | `L1_01`：用户可读不等于模型可见，未分类/冲突失败关闭 |
| `CON-KEV-003` | `L2_01_01`：输入候选已读取授权并绑定 Profile/index/read-policy snapshot |
| `CON-KEV-004` | `L2_00_02`：模型是不可信 Provider，任务版本与 transport 分离 |

### 4.2 现行端到端追踪矩阵

旧版本映射见[原端到端追踪矩阵](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-34)。下表继承稳定需求及必要边界，当前模式/任务以专门章节为准；映射不声明本轮已执行运行验证。

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-KEV-001`、`CON-KEV-003` | `DR-KEV-001`、`DR-KEV-002` | `IMPL-KEV-201`、`IMPL-KEV-001`、`IMPL-KEV-002` | `TEST-KEV-001`、`TEST-KEV-002` | `VAL-KEV-001` |
| `REQ-KEV-002`、`CON-KEV-001`、`CON-KEV-002` | `DR-KEV-004`、`DR-KEV-005`、`DR-KEV-006` | `IMPL-KEV-003`、`IMPL-KEV-004` | `TEST-KEV-003`、`TEST-KEV-004` | `VAL-KEV-002` |
| `REQ-KEV-003`、`CON-KEV-004` | `DR-KEV-007`、`DR-KEV-008`、`DR-KEV-009` | `IMPL-KEV-204`、`IMPL-KEV-006` | `TEST-KEV-006` | `VAL-KEV-003` |
| `REQ-KEV-004`、`REQ-KEV-005`、`REQ-KEV-006` | `DR-KEV-013`、`DR-KEV-014`、`DR-KEV-015`、`DR-KEV-022` | `IMPL-KEV-203` | `TEST-KEV-203` | `VAL-KEV-203` |
| `REQ-KEV-007` | `DR-KEV-023`、`DR-KEV-024`、`DR-KEV-025` | `IMPL-KEV-011` | `TEST-KEV-014`、`TEST-KEV-015`、`TEST-KEV-016` | `VAL-KEV-008` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Integrity Verifier | candidate/snapshot/hash/授权元数据一致性 | 首次业务授权 |
| Evidence Selector | 有界、确定性选择和 coverage | 模型出域决定 |
| Policy Catalog | 文档策略 artifact 的严格加载和版本快照 | 修改策略权威数据 |
| Egress Decider | 三层只收紧交集和最小 summary input | 模型 HTTP/效果评价 |
| Summary Task | 现行Summary9精确任务、逐点quote及有限claim；旧任务仅作历史追溯 | 放宽validator、在本地替代模型判断语义 |
| Extractive Validator | ref 唯一、quote 子串、大小和本地结果 | 语义扩写或模型纠错 |
| Evidence Stage | fresh Guard→verify→select→policy→model→validate 顺序 | 检索、Core answer |
| 验证Harness | 复用现行生产Capability，采集有限阶段/指标及人工rubric | 复制在线流程、gold回填或执行旧P5 |

依赖方向为 `Evidence Stage → evidence components + model Protocol`；验证Harness只依赖生产Capability和测试collector。禁止生产代码依赖 evaluation；禁止验证Harness复制流程或修改候选顺序。

这些组件按证据安全与效果验证内聚，不新增策略平台或独立服务。

## 6. 当前实现基线与迁移

最小变更原则：v3.0整理时仅整合已批准合同与迁移边界；当前实现及剩余验证按P3_01/UAT_02标记，不能将旧验证移作新合同通过。

当前仓库按§9接线Summary9的有引用有限回应，真实语义质量仍未验证。§19资料表示已有纯离线组件，真实对照和发布仍待执行。旧源码保留历史解释，不提供两套并行生产合同；本次没有改旧任务、validator、政策目录或历史运行证据。

## 7. 证据构建与选择

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KEV-001` | 逐 candidate 验证 content SHA-256、domain、Profile/index/read-policy snapshot 和当前计划成员 |
| `DR-KEV-002` | evidence ID 由 document/chunk/content hash 确定性生成，不使用模型 ref 或可变排名 |
| `DR-KEV-004` | 新鲜 Question Guard 拒绝优先，拒绝时 verify/select/policy/model 调用均为 0 |
| `DR-KEV-005` | 出域集合为全局规则∩所有相关域策略∩文档策略，任何 deny/缺失/冲突拒绝 |
| `DR-KEV-006` | 每次允许决定绑定 policy catalog、authority/export/source revision、文档策略和 index snapshot fingerprint |
| `DR-KEV-007` | 各受控Summary合同使用请求级 `e1..e8`，Prompt 强制 ref 两两不同且 quote 为连续原文 |
| `DR-KEV-008` | validator 不信任模型：unknown/duplicate ref、空/超长/控制字符/非子串 quote 均拒绝 |
| `DR-KEV-009` | 本地领域结果只由 validator 构造，包含抽取式摘要点、引用和 coverage；Core answer 不再调用模型 |
| `DR-KEV-013` | 功能 UAT 与效果 UAT 独立；功能通过不关闭效果达标，`ineffective` 有效 run 不改判 |
| `DR-KEV-014` | 优化依据须为与变更相关的当前诊断或对照证据，不强制继承旧候选流水；方案、gold和验收条件事前确定，历史不改判，不通过放宽安全validator提高结果 |
| `DR-KEV-015` | 新效果候选必须冻结 task/Prompt/code/Profile/index/policy/dataset/provenance、预算和 append-only Schema；精确授权前模型 outbound 为 0 |
| `DR-KEV-022` | 一次合同有效且完整的效果运行关闭“效果已测量”责任，四类效果等级是输出；`effective` 是质量改进目标而非项目硬关闭条件。非 effective 不自动创建新候选，`invalid_run` 表示未形成测量且只能作为新的独立目标处理 |
| `DR-KEV-023` | 阶段 A 附件 chunk 使用父 `documentId` 参与现有 policy resolve，并保留独立 asset/version/relation 定位；父绑定缺失、policyRef 冲突或 snapshot 不允许时 Evidence 构造失败且 summary 调用为 0 |
| `DR-KEV-024` | 新发布必须使用新文件名和 catalog/export/source revision/hash；旧 `egress-policy-catalog.json` 及其 loader/hash 保持可验证，新目录只保留原 disposition/allowed fields/content limit，并增加对应新逻辑 snapshot |
| `DR-KEV-025` | 候选 alias 生效前必须对所有候选 `documentId + policyRef + indexSnapshotId` 做全成员检查；发布后抽样构造 Evidence 并通过连续子串 validator，不得用 Profile 切换掩盖策略缺口 |


历史编号原定义见[历史Evidence/P5规则目录](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-2)；这些编号不复用，也不作为现行实施或全量兼容回归要求。
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

当前模型payload只包含Guard允许的原问题、代码持有的query_mode、检索coverage及最多8条策略交集允许的Evidence投影；精确形状与预算由§9.1治理。JWT、subject、内部ID/hash、Profile/index、策略详情及原始Provider响应不得出域。历史serializer只按冻结版本追溯，不要求当前载荷承载旧requirements。

## 9. 按查询模式取证与验收（组件及工作树接线已实施；真实充分性待评价）

依据REQ-KQ-201～205及KQ-AD-020～024。本节为首期目标合同，替代整理前§7.3、§9.4～9.6及§13.9的强制requirements/coverage锚点和0.5质量准入；当前§8三层出域、§7完整性与§9.6抽取validator继续保留。历史任务1～7、P5的Q1～Q4/evaluator、局部实验结果不修改。旧合同仍适用于冻结运行，不要求新生产链路维持其全部策略。本轮组件与仓库接线已完成，未因此获得真实回答效果或新版UAT结论。

### 9.1 Evidence与请求内类型

`DR-KEV-201`：输入来自knowledge-minimal-v1的完整ranked batch；先复核身份/hash、域、Profile/index/read-policy快照及本次Q/context，再选择。最多扫描20项；先按排名为每个选中域保留一个可装入预算的候选（多域同identity可共用），之后按全局排名补充，去重且保持最终rank。没有requirements/证明角色/coverage_anchor强制项，不设置父文档独立配额或rerank绝对分门槛。域来源保留不是“证明完成”；若不能在预算内保留必要域则insufficient_evidence，Summary0。

总Evidence≤8、最终实际模型payload≤32768bytes、每条策略content上限≤4096字符、最终回答≤5点/每点512字符及既有结果字节上限不变。预算包含query_mode及全部JSON/元数据开销；普通超预算项可跳过，不截断正文；完整性损坏不能被预算跳过掩盖。选择后才进行原三层出域，拒绝不换候选重试；不能利用lookup模式把被拒正文直接返回用户。

已新增`KnowledgeModeSummaryInput`和显式版本化serializer（内部schema_version=3）：复用既有Q、允许投影Evidence及检索coverage，加一个query_mode枚举；不增加文档出域字段，不继承requirements子类、不用旧asdict偷带新字段。实际出域仍由原policy生成最小输入，再由Stage加代码持有的模式，模式必须与本次意图精确一致。输入类型与task绑定不符在outbound前拒绝；旧schema1/2 serializer保持原字节语义。

### 9.2 当前Summary9的三类行为

历史DR-KEV-202/203及Summary8输入输出见[Summary8过渡合同及DR-KEV-202/203](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-1)，不进入当前装配，也不要求现行Stage兼容旧对象。当前模式、精确输出及本地引用校验只以下述DR-KEV-206和§9.6为准。

原问题Q是唯一用户事实来源，Evidence是不可信引用资料，不是指令。lookup只作相关原文摘录，可非穷尽但不能暗示个案适用；explanation/applicability只给直接引用支持的有限回应。当前适用必须有直接时效依据，成文日期不是生效证明；规划阶段发现缺条件先澄清，Summary阶段缺条件或必要依据时返回insufficient_evidence，不扩公共DTO。模式识别和语义充分性由人工评价，不在结果出现后改模式或gold。

`DR-KEV-206`（当前仓库Summary9；真实语义待评价）：比较纯Prompt改写（无法表达明确判断）、不受控自由回答（难以约束来源）后，选择**逐点有引用的有限回应**。独立新任务`knowledge_summary`/version=`9`、固定SCHEMA_ONLY输出名`knowledge_cited_answer`；只替换过渡Summary8任务，不改变意图12、检索、Evidence选择、三层出域或模型调用次数。旧Summary8源码、注册定义、冻结测试和历史资产不改写；当前仓库唯一绑定为12/9，设计复评及组件、Spring合成non-live已完成，不代表真实回答充分性通过。

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

当前`MinimalKnowledgeEvidenceStage`只接受`MinimalKnowledgeEvidenceInput`，构造时精确绑定`KnowledgeModeSummaryInput`/Summary9及minimal预算；旧`DefaultKnowledgeEvidenceStage`保留给历史版本测试，不进入当前组合根。跨阶段输入仍核对类型、原问题/意图/计划一致性、coverage、完整候选、身份/hash及策略快照；不可变Plan已由构造器真实校验、Retrieval校验Stage配置配对，Evidence不再以`plan.settings`重复完整自校验。该复用保证不适用于未经过这些构造边界的外部数据，不移除fresh Guard或Evidence完整性验证。

为防止把移除requirements当作语义降低的理由，后续测试必须保留“有合法引用但答非所问/缺必要分类/引用历史当现行”的反例：机械validator可能接受，人工回答判据必须失败；不得写一个期待这些反例成功的UAT。功能通过和回答有效分开，禁止把结构可解码率冒称忠实度。

### 9.4 验收方法和一次测量的结束边界

`DR-KEV-205`：新方案采用UAT_02 §5的四维验收，不重新解释旧P5阈值。安全为硬否决；功能验证真实代码分支/生命周期；召回只在人工确认原文存在的固定池计算必要来源/相关性/排名；回答按相关、充分、忠实、usefulness独立人工判定。缺料/未知保留原case及原因，不记为召回改善；非法引用、无依据适用结论不能靠总体平均掩盖。

原问基线先固定代码/任务/模型/配置/索引/策略和有限问题集，只进行一个计划好的测量；结果可以不达标，失败后停止分析，不自动新建candidate。核心功能/安全不通过不得发布；效果未达标不能宣称优化成功，但不强迫无限付费。数据、模型或向量表示的后续实验是可选独立目标，预算和运行身份不从旧目标继承。本文初次设计目标不授权真实执行；当前独立实施目标的有界额度与冻结前置由P3_01/UAT_02治理，未确认gold不得调用。

### 9.5 实施追踪与回滚

#### 新设计编号定义

| 需求编号 | 规则编号 | 实现编号 | 测试编号 | 验证编号 | 定义位置与状态 |
|---|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-201、DR-KEV-204、DR-KEV-205、DR-KEV-206 | IMPL-KEV-201、IMPL-KEV-203、IMPL-KEV-204 | TEST-KEV-201、TEST-KEV-203、TEST-KEV-204 | VAL-KEV-201、VAL-KEV-203、VAL-KEV-204 | 需求定义见REQ_00 §5.2；组件及接线fake/non-live已有阶段证据，完整VAL与真实人工效果未关闭 |

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-201 | IMPL-KEV-201：已新增minimal_selection.py；模式类型在contracts.py、预算serializer在summary_task_v8.py，minimal_stage.py和现有integrity/policy接缝 | TEST-KEV-201：域机会/重复/同父第四条、8/32KiB含模式、损坏低分不跳过、策略拒绝0 | VAL-KEV-201：Evidence单元/合同/集成；真实取证待验证 |
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-204、DR-KEV-205 | IMPL-KEV-203：minimal_stage.py/当前根/脱敏观测直接接缝及后续tests/evaluation/knowledge与UAT追踪 | TEST-KEV-203：无明文/跨请求污染、无fallback、四维计分/缺料不删case | VAL-KEV-203：功能安全non-live后，另授权有限真实/人工评价 |
| REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KEV-206 | IMPL-KEV-204：独立summary_task_v9.py、cited_summary_validation.py的claim校验、minimal_stage.py/唯一root绑定及agent-service验证台同屏原文引用展示；公开result只使用现有summaryType值位 | TEST-KEV-204：exact decoder、三模式claim形状、ref/quote原validator、非法数字/时间/否定反例、deny0、一次调用、超时/取消、前端DOM安全展示和旧V8不变 | VAL-KEV-204：non-live成功后才冻结一次真实12题；维护者原文人工判定语义充分性，不能由机械validator代替 |

新旧模式合同必须随Knowledge整套版本切换，不能只换Prompt、保留quality-v3的强制需求输入。回滚优先禁用Knowledge；恢复旧配对时仍检查当前索引/策略相容，不改历史结果或全局模型。阶段A、Business、公共DTO、policy权限均零变更。原正式设计及文档验证记录见历史P3_00 §21；当前交接见P3_01。


### 9.6 Validator

原Summary8校验顺序：outcome/points 组合→点数→ref 存在→ref 唯一→quote NFC→非空→≤quote limit→无控制字符→是对应 content 的连续子串→answer/result bytes 上限。当前Summary9在该原文/ref链之后增加必填claim的mode、NFC、长度、换行/控制字符及结果预算校验；不能跳过原校验后直接展示claim。

内部诊断 reason 仅用于测试/受控诊断：`outcome_points_mismatch`、`point_count_invalid`、`unknown_evidence_ref`、`duplicate_evidence_ref`、`quote_empty`、`quote_too_long`、`quote_control_character`、`quote_not_substring`、`answer_too_large`、`result_too_large`。公共调用方只看到 `knowledge.summary_failure`，不看到内容或诊断分支。


### 9.7 本地结果

Validator 构造既有`schemaVersion=1`、`answerSummary`、points（quote+citation）和coverage；历史Summary8只产生`summaryType=extractive_evidence`，当前Summary9按§9.2的模式产生`extractive_evidence`或`cited_limited_answer`。citation使用本地evidence ID、domain、title/source/document metadata；模型不能提供或修改这些可信引用字段，claim不会进入citation或原文quote。

## 10. Evidence Stage 核心流程、错误分类与调用方可见语义

```text
question denied flag / fresh Guard
  → integrity verify
  → deterministic select
  → three-layer egress decide
  → require matching ModelCallContext
  → current Summary9 within same deadline
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

- 目标limits按§9.1固定，实际模型payload包含mode和JSON开销；总8/32768bytes及quote/结果上限不变。旧工厂不参与当前生产装配；保留历史源码不构成动态选择或兼容要求。
- 策略目录 artifact 随代码发布并严格加载；内容变化必须创建新资源、新 version/export/source revision/hash 并重跑全成员和出域测试。旧资源、常量及历史 manifest 继续独立可验证，不得原位改写。
- 当前仓库唯一绑定Summary V9/意图12，设计评审、实施及组件/Spring合成non-live已完成；V1～V8源码与冻结资产保留历史可核查性，不要求当前运行时兼容旧版本或执行旧候选，实际部署未核实。回滚优先禁用Knowledge；若显式恢复旧任务绑定，必须整套配对并形成新配置快照，不改写既有task源码和历史evidence。
- 禁用 Knowledge action 可完全停止真实检索/出域；无数据迁移。

## 13. 历史P5评估入口

原26题primary/ablation、Q1～Q4阈值、分母及人工rubric原文见[历史合同附件](KNOWLEDGE_HISTORICAL_CONTRACTS_2026-10-06.md#historical-p5)。原运行只能按其冻结提交、数据及evaluator解释，不重算、不改判、不续跑。

本节不授予运行许可，也不要求intent12/Summary9/minimal链路兼容旧P5执行器。当前四维验收方法见§9.4及UAT_02；功能、安全、真实集成、效果和发布结论分别治理，不继承历史Passed。稳定历史DR/IMPL/TEST编号保留用于追溯，不转化为当前实施前置。

## 14. 当前实现落点与责任

现行专用实现与追踪由§9.5及§19.1唯一维护。共享完整性、策略和引用组件如下；不按旧任务版本再建立兼容链。

| 实现编号 | 路径与职责 |
|---|---|
| `IMPL-KEV-001` | `agent-runtime/src/agent_runtime/knowledge/evidence/minimal_selection.py`：`MinimalEvidenceIntegrityVerifier`、`MinimalEvidenceSelector`；旧builder.py只按实际共享函数或冻结历史追溯 |
| `IMPL-KEV-002` | `agent-runtime/src/agent_runtime/knowledge/evidence/contracts.py`：Evidence/Bundle/limits/types |
| `IMPL-KEV-003` | `agent-runtime/src/agent_runtime/knowledge/evidence/catalog.py`：strict catalog、fingerprint |
| `IMPL-KEV-004` | `agent-runtime/src/agent_runtime/knowledge/evidence/policy.py`：`KnowledgeEvidenceEgressDecider.decide` |
| `IMPL-KEV-006` | 原文校验复用`agent-runtime/src/agent_runtime/knowledge/evidence/summary_validation.py`；历史Stage为`agent-runtime/src/agent_runtime/knowledge/evidence/stage.py`，当前Stage为`agent-runtime/src/agent_runtime/knowledge/evidence/minimal_stage.py` |
| `IMPL-KEV-011` | `agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v2.json` 与 当前目录加载接缝；旧目录独立追溯；阶段 A policy catalog 生成器和全成员 validator 位于 `knowledge-corpus-tools`。全新官方父文档只能选择既有同域 policy，禁止新增 disposition、放宽字段上限或扩大角色 |

策略决定只由KnowledgeEvidenceEgressDecider负责；引用校验复用ExtractiveSummaryValidator；当前Stage是minimal_stage.py的MinimalKnowledgeEvidenceStage，输入为MinimalKnowledgeEvidenceInput。旧Stage、P5分母函数与旧Summary签名不是现行调用合同，原编号及签名见[旧Evidence实现、测试、评估签名及结论追踪](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-3)。

## 15. 当前测试与验证要求

当前风险及落点按§9.5/§19.1和UAT_02追踪：完整性损坏整批失败、fresh Guard拒绝零后续、三层出域交集、未知/重复ref及非连续quote拒绝、三模式claim形状、超时取消、当前唯一根和disabled零依赖。

这些边界的unit/contract/non-live验证不替代真实集成、回答充分性或发布。只有变更影响仍有有效调用方的共享组件时才承担相应兼容回归；不要求为维护当前任务逐个运行所有历史Prompt/P5组合。旧TEST/VAL定义及原Passed见[旧Evidence实现、测试、评估签名及结论追踪](KNOWLEDGE_LEGACY_DESIGN_2026-10-06.md#history-3)，不继承至当前验收。



### 当前共享边界的测试编号

| 测试编号 | 场景 |
|---|---|
| `TEST-KEV-001` | 现行integrity的hash/snapshot/domain/policy ref及冲突 |
| `TEST-KEV-002` | minimal选择顺序、域机会、Evidence总预算与不足 |
| `TEST-KEV-003` | 三层allow/deny/missing/conflict、拒绝零模型 |
| `TEST-KEV-004` | fresh Guard、context mismatch、timeout/cancel/failure |
| `TEST-KEV-006` | quote连续子串、唯一ref、控制字符、大小及可信citation |
| `TEST-KEV-008` | 历史结果原hash及终态不变；不重新执行旧批次 |
| `TEST-KEV-014` | 新catalog严格Schema、export/source revision及历史字节不变 |
| `TEST-KEV-015` | 附件父policy、错snapshot/未知父/冲突拒绝及summary零调用 |
| `TEST-KEV-016` | 新候选全成员policy及发布后Evidence/引用校验 |

| 验证编号 | 方法与证明边界 |
|---|---|
| `VAL-KEV-001` | 现行integrity/minimal选择组件验证 |
| `VAL-KEV-002` | 三层策略、出域零调用和snapshot验证 |
| `VAL-KEV-003` | Summary9、CitedSummaryValidator及复用原文引用校验的non-live验证 |
| `VAL-KEV-008` | 资料发布的策略与Evidence验证；fake不能替代真实发布 |

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
| 现行实现 | 起始Summary7及原Evidence保留原证明范围；当前仓库绑定Summary9/minimal Evidence，过渡Summary8及旧任务/P5按冻结版本解释 |
| 当前允许实施范围 | 当前独立目标按授权推进DR-KEV-201～205、301～304的剩余验证；真实测量须先冻结gold与预算 |
| 本轮权限 | 当前独立目标允许目标内代码、测试和文档及有界验证；不扩大公共合同、权限或历史运行资产 |
| 当前禁止动作 | 旧授权续用、重新消费候选、绕过完整性/出域/引用校验或声明整体效果通过 |
| 回滚单位 | 相容的Provider、Evidence实现、成对任务与配置；优先禁用Knowledge，旧证据不可改 |

## 18. 评审记录与范围

原v3.0整理评审见归档，不是本轮结论。本轮仅评审历史分离、现行职责和追踪收敛；不重新批准代码、真实质量、部署或运行。

## 19. 资料表示与原文证据边界（部分离线组件已实施）

依据KQ-AD-025～028及L2_01_01 §18；§9当前Summary9已在仓库接线，真实验收仍未完成。本节不更改现有Evidence/Policy/引用validator、旧任务版本或公共返回字段。

`DR-KEV-301`：source dataset是采集/分发来源，官方URL才是发布来源线索，两者都不自动证明当前效力或读取/出域许可。仅有curated名称、标题或模型摘要而缺少可核查来源的材料，不能作为新的官方gold或适用性证明。保留既有库存和历史证据；新迁移范围须标source_unverified并补人工来源核验，不能借新的分类标签把未知资料认证为官方。许可声明需保留来源，不把数据卡声明扩成商业再分发授权。

`DR-KEV-302`：可引用content与检索context分别治理。标题、章节路径、父说明和重复表头可帮助检索，但不构成原文quote；只能引用实际已授权content的连续子串。跨chunk、跨表头/行或跨条款拼接不是连续原文，不得为了覆盖完整而放宽校验。需要多个片段时仍受既有唯一ref/条数/字节预算；当前公共合同无法表达完整表格或额外父读取时，返回既有不足边界并记录限制，不隐含新接口。

`DR-KEV-303`：库存contentHash、原始asset hash、标准化源hash、chunk body hash和embedding input hash含义不同。Java对实际content生成的hash仍是在线输入完整性依据，不能改用元数据hash或新向量hash。重切片后使用新chunk identity，原evidence与旧snapshot保持可追溯；新策略目录仅迁移相容身份/快照且不扩权。未知旧hash口径不等于篡改，也不能用于证明精确原文相同。

`DR-KEV-304`：成文日期仅作来源信息；当前源快照的active/pending不能替代当前核验。文档部分失效不证明某条款有效或失效；未知不是有效，也不是自动禁止查阅。资料查找允许受控返回相关原文线索；适用性肯定结论仍需明确期间、主体及直接规则证据。来源元数据未进入现有DTO时，不能在Prompt/结果中伪装已知；新时效展示/过滤另作公共合同评审。人工评估须把“片段引用合法”和“条件/期间有依据”分别评分。

`DR-KEV-302`的补充边界：离线完整结构单元可用于核对chunk是否遗漏条件、定义、例外或表头，但其存在不是在线Evidence，也不自动允许读取或外发。当前候选`content`仍是经授权返回的原文片段；派生标题/路径、重复表头和未取得的父单元均不能被引用。若未来另行批准受控补取，新增每个原文跨度须分别具备同版本来源、读取授权、完整性/hash和三层出域决策；模型只得到策略交集允许的有限内容，引用须指向实际返回、唯一且连续的原文片段。子块可读不推出父条款或附件可读；多span不能伪装为一个连续quote。必要定义/例外未取得、拒绝或预算不足时，不能只凭命中子块给出完整肯定回答。补取产生的正文仍计入既有Evidence/模型输入预算，不因此放宽条数、字节或validator；未批准的公共合同与失败映射详见L2_01_00 §19。

### 19.1 实施追踪与证据范围

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
