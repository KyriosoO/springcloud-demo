# [UAT_01] 单体 Agent Knowledge 查询验收测试计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `UAT_01` |
| 当前版本 | v3.0 |
| 文档状态 | Reviewed |
| 日期 | 2026-09-14 |
| 适用范围 | Knowledge已有功能/效果及阶段A证据的原范围，新设计四维验收方法；本轮不执行新UAT |
| 上位依据 | L1_00 v3.0、L1_01 v3.0、L2_00_02 v3.0、L2_01_00 v3.0、L2_01_01 v3.0、L2_01_02 v3.0、P3_00 v3.0；§15在线新设计、§16资料表示验收方法；历史批次按冻结版本解释 |
| 历史边界 | candidate-01～07 的既有 manifest/authorization/consumed/journal/result/evidence/failure 均保持不可变；candidate-07 为 `failed_unconsumed` |
| 归档来源 | [整理前 v1.50 原文](历史文档/2026-09-14-unified-v3-baseline/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |

本计划是Knowledge验收的唯一计划权威；P3治理工作包和Gate，原evidence治理运行事实。v3.0不重跑、不改判、不恢复历史授权。

修订历史：2026-09-14，整理纳入统一文档基线v3.0；原版本、源提交及完整字节归档见上表。本次版本序列重置不是代码或设计回滚，评审、实施、部署和UAT状态分别管理。

本轮v3.0经三轮内审及两轮同一执行者的分层/跨层正式复核通过；仅证明文档整合，不表示新实现、部署或UAT已完成。完整发现与验证见本次归档MIGRATION.md。

## 2. 目标、非目标与结论口径

当前范围：旧阶段B优化目标已取消，§14索引的所有历史批次及授权仅保留原时点，不可恢复/补跑；旧失败及未执行项不改判。新§15只设计验收，12/8/minimal-v1未实施、Functional未重新验证、效果Evidence missing。本轮不读取模型凭据、创建候选或运行服务。

功能 UAT 验证生产链路、权限、安全、失败关闭、证据可追踪和组件隔离；效果 UAT 验证域选择、召回、融合、重排、证据覆盖、摘要有效性和人工 usefulness。两类结论独立：

- Functional：`Passed` / `Failed`；
- Effectiveness：`Effective` / `Partially effective` / `Ineffective` / `Invalid run`；当前任务版本尚无有效测量时，使用独立的 `evidenceStatus=missing` 表达，不新增效果结论枚举。

功能通过不代表效果达标。一次有效、完整且安全 Gate 通过的运行关闭“效果已测量”责任，其效果等级必须如实记录；`effective` 是质量目标而非项目硬关闭条件。`invalid_run` 不形成有效测量，且不得自动重跑或创建新 candidate。阶段 A 允许离线处理官方正文/附件、新建候选索引并在独立发布门禁后切换既有只读 alias；不改变公共 DTO、角色、出域权限、在线流程或阶段 B 检索算法。

## 3. 被验收的生产链路

```text
Spring 公共接入与认证
  → Python Runtime / 单动作选择 knowledge.query
  → Question Guard / 当前源码 KnowledgeRewriteTaskV11（阶段 B；旧运行各自绑定历史版本）
  → tax.policy / tax.law 逻辑域与 Retrieval Plan
  → es-query-service typed Knowledge endpoint / 最终读取授权
  → keyword + vector / RRF / BGE rerank
  → Evidence 完整性、选择与三层出域交集
  → 当前生产 KnowledgeSummaryTaskV7（阶段 B；既有功能/效果证据仍绑定其原任务版本）
  → 多要点与适用逻辑域直接证据覆盖、引用唯一性与原文连续子串校验
  → 受控 Knowledge 结果
```

禁止 Knowledge 与 Business 相互 fallback、Agent 访问 ES 物理资源、模型生成 DSL/index/URL、单请求第二动作以及未经授权正文进入外部模型。

## 4. 环境、身份与证据规则

### 4.1 环境分层

| 层级 | Provider | 用途 | 是否付费 |
|---|---|---|---:|
| L0 | 全部 fake/stub | 单元、契约、失败注入 | 否 |
| L1 | Spring + 当前生产 Runtime 对象图 + fake Model/Knowledge Provider | 功能 UAT 主证据 | 否 |
| L2 | 真实 es-query-service/ES/BGE，模型仍为受控 fake | 只读检索契约与权限补充证据 | 否 |
| L3 | 冻结数据/配置/代码 + 真实模型 | 效果 UAT | 是，必须另行精确授权 |

### 4.2 身份矩阵

- `ADMIN`、`VIEWER`：允许的 Knowledge typed read；
- denied role：认证成功但无 Knowledge 读取权限，期望 403；
- missing/malformed/service-token：在 Spring 或业务读取权威的既定边界失败；
- JWT、subject、正文、Prompt 和模型原响应不得写入普通日志或有限 evidence。

### 4.3 每 case 追踪

每个 case 必须记录 `caseId → 风险 → 验证方式 → 自动化测试/有限 evidence → 实际结果 → 状态`。历史证据只在其冻结范围内复用；没有等价证据的 case 不得标记 Passed。

## 5. 功能 UAT 用例

### 5.1 公共接入与动作隔离

| Case | 风险与输入类别 | 预期 | 验证方式 |
|---|---|---|---|
| `UAT-K-PUB-001` | ADMIN 合法税务问题 | 选择且只执行 `knowledge.query` | Spring→Runtime non-live E2E |
| `UAT-K-PUB-002` | VIEWER 合法税务问题 | 读取授权通过并返回受控结果 | Spring→Runtime + Java security |
| `UAT-K-PUB-003` | denied/missing/malformed/service-token | 确定性 401/403；未授权正文和 summary 调用为 0 | Spring/security matrix |
| `UAT-K-PUB-004` | duplicate key、null、未知字段、超界问题 | 严格 JSON/输入失败，Runtime/Provider 调用为 0 | Spring contract |
| `UAT-K-PUB-005` | unsupported 非知识问题 | 不执行 Knowledge/Business | 当前对象图 E2E |
| `UAT-K-PUB-006` | 第二动作或跨域 fallback 诱导 | 只允许一个顶层动作；无 fallback | Core/Runtime E2E |

### 5.2 问题安全与改写

| Case | 场景 | 预期 |
|---|---|---|
| `UAT-K-RW-001` | 时间、主体、否定、法条等受保护约束 | rewrite 保留约束 |
| `UAT-K-RW-002` | 模型返回非法候选 | 原改写版本的失败关闭合同（目标语义映射见§6）失败关闭，检索/embedding/rerank/summary均0；旧fallback仅作历史合同，不作当前通过证据 |
| `UAT-K-RW-003` | rewrite timeout/provider failure | 原改写版本的失败关闭合同（目标语义映射见§6）返回timeout/downstream_failure，不进入检索且无原问题fallback |
| `UAT-K-RW-004` | 敏感或控制字符输入 | rewrite/summary 模型调用均为 0 |

### 5.3 逻辑域与失败优先级

| Case | 场景 | 预期 |
|---|---|---|
| `UAT-K-DOM-001` | 税务政策问题 | 仅 `tax.policy` |
| `UAT-K-DOM-002` | 税收法律/法条问题 | 仅 `tax.law` |
| `UAT-K-DOM-003` | 政策与法律混合问题 | 稳定选择两个域，按目录顺序执行 |
| `UAT-K-DOM-004` | 普通零域问题 | `no_result/no_matching_domain`，检索和摘要为 0 |
| `UAT-K-DOM-005` | 问题出域拒绝且同时零域 | 策略拒绝优先于普通零域 |

### 5.4 检索、融合与重排

| Case | 场景 | 预期 |
|---|---|---|
| `UAT-K-RET-001` | keyword path | typed 请求，不含 index/field/DSL；候选授权后返回 |
| `UAT-K-RET-002` | vector path | BGE-M3 exact 1024 维；JWT/身份不进入 BGE |
| `UAT-K-RET-003` | 多域×双路径 | 每个 plan item 一次；同 query embedding 至多一次 |
| `UAT-K-RET-004` | 重复候选与 RRF | 按 `(documentId, chunkId)` 去重、稳定融合 |
| `UAT-K-RET-005` | rerank | 输入仅授权候选；输出一一覆盖且稳定截断 |
| `UAT-K-RET-006` | 单路技术失败 | 仅在 coverage 与每域最小候选满足时部分继续 |
| `UAT-K-RET-007` | 全路径失败或快照冲突 | `downstream_failure`，Evidence/summary 为 0 |
| `UAT-K-RET-008` | 整域禁止或授权权威失败 | 安全失败优先，其他路径成功不得掩盖 |

### 5.5 Evidence、出域与摘要

| Case | 场景 | 预期 |
|---|---|---|
| `UAT-K-EV-001` | candidate hash/domain/snapshot/policy ref 完整 | 生成确定性 Evidence Bundle |
| `UAT-K-EV-002` | 完整性冲突或缺失 | `evidence_failure`，模型调用 0 |
| `UAT-K-EV-003` | 全局∩域∩文档策略允许 | 仅最小 payload 进入当前 Summary task |
| `UAT-K-EV-004` | 未分类、策略缺失/冲突或文档收紧拒绝 | `model_egress_denied`，summary 调用 0 |
| `UAT-K-EV-005` | 证据覆盖不足 | `no_result/insufficient_evidence`，不生成肯定回答 |
| `UAT-K-EV-006` | 合法抽取摘要（各原任务版本按冻结证据） | 独立子问题和适用逻辑域使用最小充分直接证据；缺少任一显式要点/域时 insufficient；ref 唯一、quote 为对应授权正文连续子串 |
| `UAT-K-EV-007` | unknown/duplicate ref 或非子串 quote | `knowledge.summary_failure`，不返回模型原文 |
| `UAT-K-EV-008` | summary timeout/provider/schema failure | 固定 timeout/downstream failure，无 retry/resume |

### 5.6 生命周期、隔离与观测

| Case | 场景 | 预期 |
|---|---|---|
| `UAT-K-ISO-001` | Knowledge 请求 | Employee/Transaction 调用 0 |
| `UAT-K-ISO-002` | Business 失败 | Knowledge 调用 0 |
| `UAT-K-ISO-003` | `AGENT_KNOWLEDGE_ENABLED=false` | 不注册动作、不创建 Knowledge client、不要求配置 |
| `UAT-K-ISO-004` | 取消/关闭 | 未开始阶段调用 0，所有 owned Knowledge HTTP client 被关闭一次 |
| `UAT-K-ISO-005` | 日志与有限 evidence 扫描 | JWT、正文、原始 Prompt/响应、物理 ES 信息均为 0 |
| `UAT-K-ISO-006` | enabled + 生产 stub / 测试显式 fake | 前者启动失败；后者使用同一装配函数且外部 outbound=0 |

## 6. 功能证据适用与新基线兼容

原37项通过由knowledge_uat_traceability.v2.json及原测试证明，其authority字面为UAT_01 v1.21，是不可改写的原验证依据；它记录Summary V4基线，不代表源码11/7或拟议12/8全套通过。历史v1追踪绑定UAT_01 v1.1，同样只读保留。新计划权威为本v3.0文档，二者通过下表关联而非伪造新JSON。

| 稳定case | 原验证依据 | v3.0要求与可复用范围 | 新版尚需验证 |
|---|---|---|---|
| UAT-K-PUB-001～006、UAT-K-ISO-001～006 | v1.21追踪的Spring/Core/隔离/生命周期 | 对应§5公共与隔离风险；原合同未变的安全证据仍有效 | COMPOSE在12/8实际对象图重验调用次数、取消、disabled，不能只靠旧运行 |
| UAT-K-RW-001～004、UAT-K-DOM-001～005 | 原Rewrite安全/选域/失败用例，具体行为按冻结task | 风险ID不删；目标改为安全Q不变、意图精确解码、一次选域、终态合法组合 | 原改写文本保留/原问fallback或词面零域规则不继承；TEST-KFLOW-201～203须新证据 |
| UAT-K-RET-001～008 | 原typed/BGE/RRF/拒绝证据 | 公共读取与完整性合同保留；原排名仅原策略有效 | 原Q、每域重排、稳定合并和预算按TEST-KRET-201～203重验 |
| UAT-K-EV-001～008 | 原Evidence/三层出域/抽取与V4证据 | ref/hash/连续子串/权限的反例保留，不把旧coverage当新规则 | 新mode/请求schema3/Summary8/无证明锚点按TEST-KEV-201～203重验 |

旧37项的Functional=Passed仅标原冻结范围。新12/8 Functional与Safety为Not evaluated，尚未实施；源码11/7有局部non-live和失败批次，未取得当前完整37项新证据。TEST/loader继续检验原authority，不修改JSON或断言；文档版本改号不构成运行证据升级。

新组合收口须逐项映射并实际执行生产对象图fake、Spring、安全及相关回归；无skip冒充通过。新功能/安全通过不等于真实召回或回答通过。

## 7. 效果诊断与效果 UAT

### 7.1 不可变基线

candidate-04 是有效 P5 run：安全 Gate 通过，Q2 通过，Q1/Q3/Q4 未达标，结论 `ineffective`。所有历史文件及哈希不可修改、补跑、续跑、重试或改判。

### 7.2 诊断输出

只读诊断至少输出：domain exact match、keyword/vector path hit、fusion/rerank recall 与 MRR、required evidence coverage、summary valid completion、faithfulness、usefulness，以及 gold_issue/no_result/insufficient_evidence/downstream_failure 分布。每项根因按问题集/gold、rewrite、域、文档结构、召回、embedding、RRF、rerank、Evidence、策略、Prompt、validator 或环境分类，并标注证据强度。

candidate-04 的历史诊断保持：domain exact match=0.5909、rerank recall@10=0.9405、required evidence coverage=0.4643、summary valid completion=0.6923，证据只支持域目录 v2 与 Summary V3。candidate-05 的新只读诊断绑定 result SHA-256=`a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb`，确认 4 个安全负例导致历史 completion 分母理论上限 22/26、1 个 answerable `gold_issue` 归因冲突，以及 3 个 mixed coverage 失败。由此批准 Summary V4 与效果口径 v2；不支持修改 RRF/rerank、validator、dataset/gold、权限或阈值。

### 7.3 最小优化与版本规则

只有被证据支持的 Prompt、逻辑域安全描述、Retrieval Profile 逻辑参数、RRF/rerank 参数、Evidence 选择或 Harness 才能新版本化；不得改历史 case/gold、放宽 validator、修改正文/index/mapping/alias、扩大授权或降低阈值改判。

效果口径 v2 下的后续独立运行必须满足：

- summary completion 只排除按设计必须零调用的 `security_negative`；普通无结果、证据不足、技术失败、超时和校验失败仍作为失败计入；
- faithfulness/usefulness 只排除人工明确的 answerable `gold_issue`，同时保留 count/case ID；质量可评 answerable 少于原集合 90% 时整次 run 为 `Invalid run`；
- Q3≥0.95、Q4 completion≥0.90/usefulness≥0.80 以及全部安全 Gate 不变；
- 历史 candidate-04/05 继续按冻结 evaluator 解释，不重算或改判。

### 7.4 历史效果终态

| 运行 | 原结论与证据范围 | 当前解释 |
|---|---|---|
| candidate-04 | 有效P5、ineffective；Q2通过，Q1/Q3/Q4未通过 | 历史诊断，不是最新有效结果 |
| candidate-05 | 最新有效P5，partially_effective；Q1/Q2通过、Q3/Q4失败、安全通过 | 只证明原任务/数据/索引；result SHA-256 a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb |
| candidate-06 | 已消费后snapshot_changed，无有效效果；44次paid | 不续跑，不改判 |
| candidate-07 | failed_unconsumed / invalid_run；模型/业务0 | 不替代最新有效P5；Summary V4有效测量仍缺失 |

完整run、HEAD、manifest/授权/journal/failure/hash及消费规则见[整理前§7](历史文档/2026-09-14-unified-v3-baseline/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md)和对应原资产。新设计采用§15，不继续旧P5候选；既有指标阈值/分母及历史结果均不改变。

## 8. 状态权威与有限收口

| 范围 | 结论 | 不可外推部分 |
|---|---|---|
| 原37功能用例 | 原冻结范围Passed | 非当前源码或12/8重验 |
| 原阶段A14项 | 原发布范围Passed | 非全库分类/时效准确、非当前在线召回通过 |
| 最新有效P5 | partially_effective | 非effective，非Summary V4/7/8效果证明 |
| candidate-07 | invalid_run / failed_unconsumed | 无有效测量、不可补跑 |
| 旧阶段B/最近人工批次 | 未整体通过；目标取消 | 不拼接旧通过为新版10/10 |
| 新12/8及资料方案 | Designed / Not executed；效果Evidence missing | 本轮只有文档整理与兼容检查 |

工作包/Gate只见P3；本计划记录验收维度，不把历史成功、文档Approved或新版本号当效果提升。

## 9. 回滚与失败处理

- 生产回滚：设置 `AGENT_KNOWLEDGE_ENABLED=false` 并重启，Business 三动作不变；
- 功能失败：先判断实现、Harness、环境、设计或过度门禁，不删除测试或放宽安全规则；
- 效果失败：保留新 run append-only 证据，如实分类，不补跑或改判；
- 需要正文、mapping/index、公共接口或权限变化时停止并申请追加授权。

## 10. v3.0评审与实施边界

本轮为文档整合评审，不是代码实施或真实UAT。内审、分层及跨层正式复核的实际发现、处理与验证统一记录于[本次整理记录](../历史文档/2026-09-14-unified-v3-baseline/MIGRATION.md)；整理前评审原样保存在归档。当前评审状态以文档信息为准。

## 11. 阶段 A 正文及附件完整性专项 UAT

阶段 A 只验收“语料存在、可读、可检索、可追溯和可引用”，不把用户问题经 Domain/Rewrite/RRF/rerank 后是否进入最终 topK 作为通过条件。所有用例使用现有 typed Knowledge endpoint、读取授权和 Evidence 组件；模型 outbound=0，图谱调用=0，Business 调用=0。

| Case | 风险 | 验证行为 | 通过条件 |
|---|---|---|---|
| `UAT-KCORPUS-A-01` | 页面正文被截断 | 页面正文完整且无附件依赖 | expected 原文可由 keyword 检索并与 asset/hash 对应 |
| `UAT-KCORPUS-A-02` | 页面只列附件名 | PDF 附件正文进入候选 | PDF chunk 可检索、父文档/asset 可追溯 |
| `UAT-KCORPUS-A-03` | Office 附件丢失 | DOC/DOCX 正文进入候选 | 原文可检索且 parser/version/hash 完整 |
| `UAT-KCORPUS-A-04` | 表格语义丢失 | XLS/XLSX 或文档表格保留行列 | 单元格内容可检索，sheet/table/row 顺序可追溯 |
| `UAT-KCORPUS-A-05` | 扫描件空文本 | 必要 OCR 产生带状态文本 | accepted OCR 可检索；review/rejected 不索引 |
| `UAT-KCORPUS-A-06` | 父子关系孤立 | 父文档导航到附件/条款/chunk | 全关系可解析，无孤立附件 |
| `UAT-KCORPUS-A-07` | 当前/历史混淆 | 生效、失效、废止元数据 | 当前有效与历史材料可确定性区分 |
| `UAT-KCORPUS-A-08` | 关键词路径不覆盖附件 | direct typed keyword | 新增附件原文至少一个目标片段命中 |
| `UAT-KCORPUS-A-09` | 向量路径未构建 | direct typed vector | 1024 维向量有效且目标片段可召回 |
| `UAT-KCORPUS-A-10` | 未授权正文泄漏 | denied JWT/read decision | ES 正文、Agent、BGE 和 Evidence 均为零暴露 |
| `UAT-KCORPUS-A-11` | 新快照不能构造证据 | 当前策略目录 + candidate | Evidence 引用存在、唯一且 quote 为连续子串 |
| `UAT-KCORPUS-A-12` | 阶段 A 暗含图谱依赖 | 图谱不存在 | 全部语料验证继续完成，图谱调用为 0 |
| `UAT-KCORPUS-A-13` | 酒店住宿税率缺少直接依据 | 官方服务分类附件 + 当前有效税率原文 | “住宿服务”分类和适用税率规则均存在、可读、可检索、可引用 |
| `UAT-KCORPUS-A-14` | 阶段 B 缺口被误归因 | 直接 typed 命中但最终 topK 可失败 | 阶段 A 通过；用户端失败单独记录为域选择/改写/排序输入，不调参、不 fallback |

专项 UAT 逐 case 保存有限追踪：`caseId → frozen candidate/index/profile/policy snapshot → asset/chunk hash → keyword/vector/read/evidence 状态 → result`。不得保存完整正文、向量、JWT 或原始业务响应。`UAT-KCORPUS-A-13` 不预设纳税人类型、计税方法或问题日期；它只证明回答所需分类原文和当前税率规则可供后续链路使用，不在阶段 A 生成税务结论。

发布 Gate 只有在 14 项均通过、P0 全部和目标 P1 全部完成、P2 清单存在、alias 回滚演练及既有 37 项功能 UAT/35 项 Business UAT 防回退通过后才能关闭。若仅最终在线 topK 失败而直接 typed 检索通过，`UAT-KCORPUS-A-14` 必须形成阶段 B issue，而不是重开资产完整性用例。

## 12. 历史评审追溯

阶段A原评审及其发现保留在整理前归档，原证明范围不变；本次文档复核统一见§10。

## 13. v1.19 阶段 A 执行结论

- 规范 UAT ID 为 `UAT-KCORPUS-A-01～14`，与 strict Schema、launcher 和有限 evidence 一致；早期文档中的 `UAT-KC-A-*` 仅为编号漂移，不代表用例失败。
- build run=`knowledge-corpus-stage-a-v1-20260903-candidate-08`；最终 UAT run=`knowledge-corpus-stage-a-uat-v1-20260903-attempt-05`；candidate=`agent-doc-tax-policy-v4-20260903-corpus-a5`，UUID=`SurWRSglRd6ZRddEBWy2Sw`。
- 14/14 Passed；model outbound=0，Business call=0；keyword/vector 直接 typed 检索、读取拒绝和 Evidence 合同均通过。
- attempt-01 有限结果 SHA-256=`5659904b75a211ed6f046509783a53679af2bb499df590c4713f1fbc7c1fb21b`，attempt-02 有限结果 SHA-256=`24332d732058f04ad01ea431f42e8432819d99ecaca0533b33038bca931502bd`，均保持字节不变。attempt-03 虽通过行为断言，但结果中的前序索引仍错误指向初始基线，不能作为最终发布追踪；attempt-04 保留为 a4 有效中间证据。最终 attempt-05 有限结果 SHA-256=`ad86ae89b48e0c96426cbadddef526d391e6b61214a254bba90049286afc162a`；同次运行验证 738 个附件 chunk、55 个条款引用、ACTIVE/EXPIRED、`tax.law/tax-law-v1`、精确 alias、酒店住宿分类与税率原文。
- 首次使用最终用户问句进行向量断言时发现目标附件位于 rank 59，alias 已立即回滚；该失败属于阶段 B 改写/排序边界，不改写为阶段 A 失败。改用直接原文检索语义后通过，最终发布仍执行完整切换→回滚→再发布三次原子操作。
- 阶段 B 输入固定为 `domain_selection`、`query_rewrite`、`ranking`、`failure_semantics`；本轮未修改在线算法、Prompt、topK 或 fallback。
- 既有 Knowledge Functional 37/37、Business 35/35 与历史 candidate/evidence 保持不变。

## 14. 已取消阶段B的验收追溯

旧专项已取消，失败、未执行、人工未评和全部消费终态原样保留。完整case/gold、批次顺序、调用数及验证引用见[整理前§14](历史文档/2026-09-14-unified-v3-baseline/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md)及原有限evidence，不再提供“继续/下一候选”操作指令。

最后人工批次knowledge_representative_human_run_07为1通过、1失败、8未执行，5次模型；这是原记录，不是本轮执行。有限证据只支持结构/域合同处失败，未保存原响应不能推断更细原因。它不是完整有效效果测量，也不覆盖candidate-05的有效P5结论。

原UAT-KB-001～018及其KRB问题身份不复用，编号映射指向原§14的完整用例/问题清单。原字面要求/阈值只用于解释对应运行；新目标采用§15的三模式/四维验收，资料采用§16。旧目标未完成由P3保留Deferred（取消），不宣布通过，不自动再建候选。

## 15. 新设计的四维验收方法（仅设计，未执行）

### 15.1 证明范围与版本隔离

当前源码11/7/v3，拟议12/8/knowledge-minimal-v1尚未实施。历史37功能用例、P5、阶段A、阶段B和人工run-07均只证明自己的冻结范围；P5最近有效partially_effective不代表现有V11或新V12效果达标，run-07失败亦不覆盖更早有效测量。不得把不同批次的通过题相加为新版全套通过。

新基线状态：Functional=Not evaluated（不是新增运行结果枚举，只是计划执行状态）；Safety=Not evaluated；Retrieval/Answer evidence=missing。后续实际运行沿用既有Passed/Failed及四类Effectiveness结论，新增维度留在当前验收记录，不改历史result Schema。本轮只完成方法评审，不创建JSON追踪或候选、不读取凭据、不执行测试服务/LLM；P3 §21管工作包及授权。

旧37个case稳定ID保持，后续COMPOSE对受影响项建立新版本证据，旧证据不重写；问题改写相关用例保留“原意保护/非法规划/超时0下游”的风险目标，不能把新方案没有rewrite当删测理由。新12/8准入矩阵为TEST-KFLOW-201～203、TEST-KRET-201～203、TEST-KEV-201～203及原37项的明确等价映射，未经映射/执行不称37/37新版本通过。

### 15.2 四维判据及阶段损失

| 维度 | 验证内容/方法 | 通过条件 | 不证明什么 |
|---|---|---|---|
| 功能 | fake实际生产root及Spring入口、精确意图/模式、原Q一致、路径与调用上限、失败映射、并发/取消/关闭；37风险逐case | 必需用例100%通过，无skip冒充；非法/模型失败下游0；不支持问题无第二动作 | 不证明真实LLM理解准确、原文库充足或usefulness |
| 安全 | Java读取角色/拒绝位置、Guard0model、三层出域0Summary、identity/hash/ref/连续子串/唯一性、日志脱敏及Business隔离 | 必需边界100%通过，任一越权/泄露/伪造引用为硬失败；不能被效果平均抵消 | 合法引用不等于回答充分或现行适用 |
| 召回 | 在人工确认必要来源存在的冻结池，记录域选择→keyword/vector→RRF→rerank→final20→Evidence8的来源覆盖、MRR与噪声 | 12题中至少8题预置为search且有可核实必要来源，三种模式均须覆盖；无命中/前置澄清题不放入召回分母；可验证题最终必要来源宏平均recall@20≥0.80、precision@20≥0.40，核心已确认必要来源不能全丢；实际分母/空池明确 | 缺资料不算排序失败；命中不等于可回答；未做同条件A/B不称较旧方案提升 |
| 回答 | 对原问题逐项核对相关、充分、忠实与usefulness；执行者可准备原文，最终真实评价由维护者独立于待测模型确认 | 12题全纳入；每题四项true才通过，≥10题通过；所有applicability题不得有无依据肯定结论，当前适用/历史有效混淆为硬失败 | 结构有效率不能冒称忠实度；“不足/澄清”只在预置预期如此时算正确 |

这些是**新需求基线的预置目标**，不是降低或重算旧P5 Q1～Q4；旧结论不变。阈值是个人验证项目的有限初始选择，仍需业务维护者在gold冻结前确认可用语料和问题含义；不能在看到新结果后降低。无法确认上述至少8题及三种模式的来源池时MEASURE处于Blocked，不自动删除case/补造gold或调用模型“找答案”。功能与安全合格可完成COMPOSE基础实施，未达到召回/回答目标不得宣称质量达标或擅自发布为优化成功。

每题在各阶段报告必要source/block集合覆盖及排名；候选ID仅诊断使用，不进入在线排序。相同父文档不同必要条款不能只因父ID命中就算全部覆盖。precision@20分母为实际返回候选数（0记0），由人工相关标注计算；每题必要来源缺一部分按比例计recall，宏平均只取预先核实可检索池，另报全部12题含缺料的覆盖率。MRR按首个相关必要来源排名，未命中0；Evidence recall另列，不以rerank数值分代替。没有人工原文/相关性标注时这些指标为not_assessed，不自动算0或Passed。

### 15.3 固定代表类别与先验预期

先设计12个内容case（每类4题），后续MEASURE准备阶段由维护者结合实际公开语料填写精确问句、必要source/block/hash、相关性标签、允许答案和不足/澄清预期，并在任何真实模型调用前冻结。不得单为住宿题、当前失败或gold ID写在线特判；不要求住宿资料缺失时也给肯定税率。

| 新Case | 模式/输入类型 | 预期与主要风险 |
|---|---|---|
| UAT-KM-001 | lookup，指定文号/附件 | 找到原文摘录与来源；不因缺纳税人条件阻断资料查找 |
| UAT-KM-002 | lookup，同义服务表达（可含住宿） | 检索相关资料而非擅自判税率；检索表示不足如实记录 |
| UAT-KM-003 | lookup，历史期间资料 | 可返回历史条文，不把它称为现行适用 |
| UAT-KM-004 | lookup，语料中确无对应条款 | 预置无命中/不足；不能返回无关片段冒充答案 |
| UAT-KM-005 | explanation，单域定义 | 直接摘录覆盖明确问题；不做无来源自由改写 |
| UAT-KM-006 | explanation，两个显式子问题 | 必要证据齐全才回答；缺一项不能部分肯定 |
| UAT-KM-007 | explanation，法律+政策 | 一次选双域、独立读取、最终证据覆盖；无失败扩域 |
| UAT-KM-008 | explanation，否定/税率/日期条件 | 原Q逐阶段不变，引用不得与显式条件冲突 |
| UAT-KM-009 | applicability，明确主体/期间/方法 | 只给直接适用条件及规则原文，不靠用户分类假设推导 |
| UAT-KM-010 | applicability，必要条件缺失 | 前置clarification_required，检索/Summary0；固定提示可用但不承诺动态问题 |
| UAT-KM-011 | applicability，当前与历史边界 | 无直接时效依据时不足，writtenDate不当生效日期 |
| UAT-KM-012 | applicability，类似分类边界 | 没有直接分类桥接/冲突未解决则不足，不以词面相似肯定 |

上述内容题可用公开、非敏感问题。功能/安全额外反例不必付费：未知域/模式/重复键；输出terminal组合；>1024长度；单/双域DENIED；policy缺失/冲突；坏hash；重复ref/非子串；少一路/全失败；模型超时；并发取消；disabled0依赖；Business不fallback。至少一个37风险case对应每项新DR，不以只测12题代替安全矩阵。

### 15.4 固定变量、预算与停止条件（非执行授权）

首期先完成COMPOSE的non-live。再在新的独立授权下，冻结代码/两task及Prompt hash、模型实际版本、minimal配置、Profile与索引/ACL快照、12题gold/顺序、调用预算和人工rubric。仓库绑定不等于运行绑定，必须先只读核实；运行中快照不符立即终止，不自行改alias或数据。

建议首期仅一次12题端到端测量，上限12 E2E、36模型HTTP（selector/意图/Summary合计）、48 typed search、12 query embedding、24 online rerank；维持每请求≤3/4/1/2，startup预热独立事前列明、不得计入效果请求，不能凭空增加预算。无Business/旧answer、无自动retry/resume，无失败后追加或补题。实际terminal较早时只消耗已产生调用，不为凑预算补齐。

技术/协议/安全失败停止该批，保留有限append-only终态及未执行清单，先fake诊断；不能称完整测量。正常no_result/clarification或人工判据不通过是有效测量输出，在安全合同仍成立时按预定顺序继续一次批次，最终如实分类，不修改预期。需要新批次只能作为新目标/新授权，本设计不预授予。

同条件对比可优先使用无外部LLM的固定候选池重放，各阶段损失可归因；若没有同索引/模型/条件的旧有效结果，不得拼接历史数据算增益。之后若要比较原问/改写或正文/上下文向量，必须另立单变量实验及预算，不与首期简化同时变更；语料/索引写入另授权，不属于本实施计划。

### 15.5 证据、人评和有限收口

每题运行记录只保存caseId、模式类别、预期/实际域、各阶段有限ID/排名、调用数、有限status/reason、安全结论、自动结果及人工四项；不保存真实用户敏感问题、完整知识/模型响应、凭据或个人信息。为可复现性，人工编写并核实无敏感值的公开测试问句、来源/block定位/hash、相关性标签及预期可以且必须作为版本化测试数据集冻结；运行记录引用caseId/hash，不重复保存问题或正文。公开fixture须明确来源许可，诊断不能把ID/gold反馈在线策略。

最终分别报告Functional、Safety、Retrieval、Answer。完整且安全的测量中，召回/回答均达标为effective，仅一维达标为partially_effective，两维均未达标为ineffective；执行合同不完整或安全失败为invalid_run。人工未评为not_assessed/evidence missing，不能先宣布有效质量等级，也不能由执行者/待测模型代填维护者结论。完整但质量未达标可记录测量完成，质量风险保持Open，不能用历史P5替代。本次设计完成不要求新测量，也不允许预记结果。

核心来源题预置为KM-001/005/009，任一在确认有原文的情况下最终必要来源覆盖为0即召回失败，不由宏平均掩盖。回答四项含义固定为：回应原问题、覆盖预期义务、没有无依据断言、对用户查阅或补条件有用；对预置不足/澄清题，评价正确拒绝/提示，不虚构quote或当作成功肯定答案。

评审与验证记录由P3 §21.5集中维护；不另建审批流水。新UAT JSON/Schema/loader实现只属于后续授权COMPOSE/MEASURE，当前追踪资产字节不变。

## 16. 资料组织与检索表示验收方法（设计，未执行）

依据L1_01 §4.6、L2_01_01 §18、L2_01_00/02 §19，实施由P3 §22独占。该补充不重做阶段A、不修改原37项功能或历史效果结果；本轮只有有限来源/样本审计，不把抽样当作UAT执行。所有下列用例状态为Designed / Not executed，不创建新traceability、gold或candidate文件。

### 16.1 四维判据与有限实验

1. 数据质量：逐字段来源可查、日期语义正确、版本/父子关系可解析；正文跨度/表格/脚注不静默丢失。填充率和准确率分列；未知可存在，但不能把核心预期依据的未知问题标为已完成。
2. 功能与安全：唯一typed链路、读取先于正文处理、三层出域、身份/hash/ref/连续子串/唯一性、取消/关闭及Business不回退；任何越权/伪造/不明写入为失败，不能用质量均值抵消。
3. 召回质量：必要原文来源Recall、MRR/排名、噪声及Evidence覆盖；分别报告keyword/vector、融合、rerank、Evidence损失，不以“有命中”代替完整依据。
4. 回答质量：问题回应、条件/期间、原文充分性、忠实性与人工usefulness；合法引用不等于充分。没有模型调用或人工评审时为Not assessed，不由离线统计推出改善。

未来每个对照协议先冻结≤30父文档的变更/人工核验范围和代表问题（建议≤24，覆盖多税种、长短/附件/表格、现行/历史/未知、查找/解释/适用性和无命中反例）；不要只选本轮暴露问题或住宿单题。搜索池保留完整基线和未受影响竞争文档，不能仅搜30篇后外推全库收益。人工预先固定来源、必要条款/连续span和预期不足/澄清，不由待测模型自评。原文无法核实的题标source_gap，质量指标null；保留在计划总数/数据缺口中，单列可评估质量分母及未评估数，不能强计Recall=0/1或事后删除。

对照分两个独立问题：A只改chunker，固定原始/规范解析源hash、问题、模型、检索配置及权限，向量输入类型不变；B只改向量表示，固定A选定或原有同一chunk集合及精确body hash、模型/服务和所有在线参数。更换切片时gold用稳定document/asset/source span，不用旧chunkId强求一一对应；同时变化parser、语料或模型时不能宣称单变量实验。

body、title/section/body、可信分类/body至多3种表示，先用纯构造/token统计筛除不合法项；每轮只比较基线与一个预选候选，不因失败扩成无限网格搜索。每次真实实验冻结run、代码/索引UUID/全记录变更清单、模型/tokenizer/表示/Prompt、case顺序、人工rubric、每个阶段调用预算及停止条件；本计划不授予任何调用或索引写预算。若有模型，统计selector/意图/Summary全部HTTP，不复用旧额度；无模型阶段仍须限定ES/BGE总量和候选数量。

建议质量判据在执行前由维护者确认并固化：核心有充分原文的题必要来源覆盖不得为0；成对核心覆盖和保留集覆盖不得退化，至少一个预先选择的质量主指标改善且噪声/时延不突破预定容忍值，才考虑发布。指标阈值/容忍值未冻结则实验Blocked，不允许看到结果后降低。小样本只作局部决策依据，不声称统计显著或全库收益。数据/功能安全全部达标但质量无提升可以结束测量，不能使RELEASE自动Ready。

### 16.2 用例追踪

| UAT case | 风险与设计映射 | 后续验证方法/预期证据 | 通过条件 |
|---|---|---|---|
| UAT-KORG-001 | 源字段丢失/补造；DR-KRET-301、DR-KEV-301 | 11字段fixture、HF原行/官方/curated对照、hash自身排除及重放时钟反例 | 原值可追溯，未知不补造，许可/来源分离，同输入hash稳定 |
| UAT-KORG-002 | 日期错填/陈旧；DR-KRET-302、DR-KEV-304 | 成文≠生效、pending变更、部分失效、历史/未知反例 | 不把成文填生效，不据文档整体状态认定条款；查阅与适用性分开 |
| UAT-KORG-003 | 分类等同授权/相关性；DR-KRET-305 | 多标签/缺标签/机关/法律效力及channel映射契约 | 不按推断标签扩权或无条件排除，不引入分类分库 |
| UAT-KORG-004 | 同题名误合并/关系丢失；DR-KRET-303 | 同标题不同版本、转载、附件父关系与冲突重放 | 稳定源身份/hashScope，关系有来源且可解析，旧记录不覆盖 |
| UAT-KORG-005 | 条号/条件/例外过碎；DR-KRET-304 | 长短条款、否定/例外/列表/脚注结构fixture+人工核对 | 相邻合法打包，内容为连续span；跨单元不伪造，无法保全显式隔离 |
| UAT-KORG-006 | 表格扁平与目录误认；DR-KRET-304 | 已有表格/页/目录样本，不重做OCR；表头/行关联人工核对 | 无猜造单元格/条款；重复表头不是quote；未知结构不标完整 |
| UAT-KORG-007 | 字符/token混同与截断；DR-KRET-306 | 固定tokenizer精确长度、三表示、长输入和版本缺失 | 特殊token计入，超长关闭；维度exists不代替模型/输入来源证明 |
| UAT-KORG-008 | 派生上下文冒充原文；DR-KEV-302、DR-KEV-303 | keyword/vector/rerank/Evidence表示对照；非法标题/表头quote | 原content不变，hash作用域一致，拼接/跨片引用拒绝 |
| UAT-KORG-009 | 读取/出域/父关系越权；DR-KFLOW-301、DR-KFLOW-302 | Java typed权限、Python策略/敏感0调用、默认disabled fake | 现公共合同不变，未授权正文不进入后续阶段/模型，Business不回退 |
| UAT-KORG-010 | 分段/向量收益混淆；DR-KRET-307 | 冻结父/asset/span、完整竞争池，单变量逐阶段排名及source_gap反例 | 无gold特判/删题；Recall/MRR/噪声与Evidence分列，null/分母可核 |
| UAT-KORG-011 | 合法引用却无法回答；DR-KEV-304 | 三模式多税种/期间代表题，人工原文与usefulness；必要时另授权模型 | 足够与不足分别判断，时效未知不肯定，不由模型自评 |
| UAT-KORG-012 | 发布错配/无法回滚；DR-KFLOW-303、DR-KRET-307 | fake故障→另授权隔离typed/alias回滚→发布冒烟 | 旧索引/资产不改，全记录变更可核，Profile/catalog匹配，恢复相容旧绑定 |

001～008可先以纯离线fixture完成；009的fake与真实typed证据分开；010的BGE/ES、011的模型/人工回答、012的发布验证均须后续资源授权，不把单测代替真实集成。图谱、记忆和多轮不参与验收。

### 16.3 报告与停止

逐case记录来源类别、原文身份/hash、变量、验证方式、有限结果、缺口及执行状态；不保存真实敏感问句、完整正文、JWT或原始模型响应。原文人工阅读限定既有批准资料，证据只记录必要定位与hash。固定问题集中的合规非敏感问题可用于后续版本化测试，不能与禁止保存真实敏感输入混淆。

数据质量、Functional、Safety、Retrieval、Answer分别报告；本次均不预记通过。任何来源不明、权限/引用失败、模型/服务错误、预算耗尽或结果不完整先停当前实验，保留有限终态；用fake诊断，不自动补跑或新candidate。质量未提升只给出风险和是否保留基线的决策，不恢复被取消目标。
