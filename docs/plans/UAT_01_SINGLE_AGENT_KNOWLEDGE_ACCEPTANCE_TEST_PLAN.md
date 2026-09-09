# [UAT_01] 单体 Agent Knowledge 查询验收测试计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `UAT_01` |
| 当前版本 | v1.35 |
| 文档状态 | Reviewed |
| 日期 | 2026-09-09 |
| 适用范围 | `knowledge.query` 的生产接线、功能/效果验收，以及 Knowledge 阶段 A 语料完整性专项验收 |
| 上位依据 | `L1_00` v3.5、`L1_01` v1.21、`L2_01_00` v1.27、`L2_01_01` v2.15、`L2_01_02` v1.24、`P3_00` v2.59；§14.39为run-12历史终态，§14.40治理新的分层计分，不改旧case/gold/结果 |
| 历史边界 | candidate-01～07 的既有 manifest/authorization/consumed/journal/result/evidence/failure 均保持不可变；candidate-07 为 `failed_unconsumed` |

本计划是 Knowledge 功能/效果验收、candidate 身份、效果结论和阶段 A 语料专项验收的唯一计划权威；P3 是工作包与 Gate 状态唯一权威，evidence 是运行文件与哈希唯一权威。`UAT_00` 只治理公共接入与 Employee/Transaction。v1.14 新增不依赖外部 LLM 的阶段 A 14 项语料 UAT；v1.15 明确来源不可达不等于正文缺失，且未核验 P0/目标 P1 只能阻塞发布门禁；v1.16～v1.17 保留早期证据并完成严格合同复评；v1.18 以结构化 legacy DOC 和 a4 修复条款关系；v1.19 以最终工具源码一致的 Stage A corpus candidate-08/a5、UAT/release attempt-05 作为最终 14/14 权威证据。既有 37 项功能 UAT、效果状态及 Knowledge 效果 candidate-01～07 历史运行资产保持不变。

v1.25记录独立V5验证的明确授权及§14.10版本绑定；保持原10例/顺序/gold及失败即停止规则，不改变验收判据或历史结果。

v1.27记录§14.13的质量策略V2验证要求及最新恢复授权；不改变原用例/gold或历史终态，真实批次仍需fake通过及版本/预算冻结。

v1.28按用户批准增加§14.18：累计E2E21、模型60，一次独立七例与三项证据受限复用。原10例全部验收责任不变，不能将复用记录冒充本批真实调用。

v1.29只增加§14.21新内部需求合同的验收设计；不更改任何原case/gold、历史结果、额度或再运行权限。

## 2. 目标、非目标与结论口径

功能 UAT 验证生产链路、权限、安全、失败关闭、证据可追踪和组件隔离；效果 UAT 验证域选择、召回、融合、重排、证据覆盖、摘要有效性和人工 usefulness。两类结论独立：

- Functional：`Passed` / `Failed`；
- Effectiveness：`Effective` / `Partially effective` / `Ineffective` / `Invalid run`；当前任务版本尚无有效测量时，使用独立的 `evidenceStatus=missing` 表达，不新增效果结论枚举。

功能通过不代表效果达标。一次有效、完整且安全 Gate 通过的运行关闭“效果已测量”责任，其效果等级必须如实记录；`effective` 是质量目标而非项目硬关闭条件。`invalid_run` 不形成有效测量，且不得自动重跑或创建新 candidate。阶段 A 允许离线处理官方正文/附件、新建候选索引并在独立发布门禁后切换既有只读 alias；不改变公共 DTO、角色、出域权限、在线流程或阶段 B 检索算法。

## 3. 被验收的生产链路

```text
Spring 公共接入与认证
  → Python Runtime / 单动作选择 knowledge.query
  → Question Guard / KnowledgeRewriteTaskV2
  → tax.policy / tax.law 逻辑域与 Retrieval Plan
  → es-query-service typed Knowledge endpoint / 最终读取授权
  → keyword + vector / RRF / BGE rerank
  → Evidence 完整性、选择与三层出域交集
  → 当前生产 KnowledgeSummaryTaskV4（每个效果候选另行冻结其 task/Prompt 快照）
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
| `UAT-K-RW-002` | 模型返回非法候选 | 当前V3失败关闭，检索/embedding/rerank/summary均0；旧fallback仅作历史合同，不作当前通过证据 |
| `UAT-K-RW-003` | rewrite timeout/provider failure | 当前V3返回timeout/downstream_failure，不进入检索且无原问题fallback |
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
| `UAT-K-EV-006` | 合法当前Summary（V5） | 独立子问题和适用逻辑域使用最小充分直接证据；缺少任一显式要点/域时 insufficient；ref 唯一、quote 为对应授权正文连续子串 |
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

## 6. 功能 UAT 通过条件

上述 37 个 case 已通过 `knowledge_uat_traceability.v2.json` 追踪到实际自动化或等价有限证据；schema v2 同时校验 candidate-05 最新有效 `partially_effective`、candidate-07 最新执行 `invalid_run / failed_unconsumed` 以及该追踪基线的Summary V4 `Evidence missing`，但不修改历史运行文件；它不代表当前任务版本，当前V5接线与新增证明义务另见§14.9及P3 §20.17。当前 Spring→Runtime 16 场景 E2E 实际执行且未 skip。允许按风险用 fake Model、Java Security、Python contract 和现有不可变只读证据组合验收，不机械要求全部 case 进行真实 LLM 调用。

功能结论为 Passed 还要求：

- 默认 disabled 与 enabled 唯一注册测试通过；
- Knowledge/Core/Business 回归通过；
- es-query-service typed endpoint、读取权限及原通用端点兼容测试通过；
- strict mypy、compileall、Maven、历史 hash 和敏感扫描通过；
- P3/UAT 状态与证据一致。

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

### 7.4 候选准备与当前运行事实

新候选必须在功能 UAT Passed、根因明确、新版本 non-live 回归通过后冻结。准备资产至少包含新 run ID、manifest 与 SHA-256、authorization reference、case/variant 数、精确最大模型调用数、任务/Prompt/代码/Profile/index/策略快照、首个 outbound 消费规则、retry/resume=0、append-only Schema 和失败关闭测试。准备态测试可以要求正式 authorization/result 不存在，但正式 authorization 创建后不得被 live launcher 再次执行。

candidate-05 已按 frozen HEAD=`63bc30baa68948a35840b650c0deb39d1e312efa` 唯一执行：run ID=`knowledge-p5-live-v2-20260826-candidate-05`，manifest SHA-256=`41997c6d41f3109b178844c9b74799bb59c869ae06ec23aca66bea1a6f1e278c`，26 case × 2 variant；52 个 Capability 成对完整，实际付费 rewrite22+summary22=44，retry/resume/core answer=0。安全 Gate 通过，Q1/Q2 通过、Q3/Q4 未通过，Effectiveness=`Partially effective`。

GATE-072 授权已消费，不得重跑、补跑或续跑。candidate-06 也已按 frozen HEAD=`4f304fab0b52339dbbc8c75cf58ed123d88f8b02` 消费 `GATE-077`：52 个 capability 变体完成、44 次付费请求全部终态完成、retry/core answer=0，但结果在最终快照检查时因合法未跟踪 authorization 未被排除而以 `snapshot_changed` 失败。该运行不形成效果结论，不得重跑、补跑、续跑或复用授权；其 authorization、consumed、paid journal、phase checkpoints 和 failure 必须 append-only 保存。

后续必须先完成共享工作树 allowlist 的 non-live 修复和 candidate-06 历史校验，再冻结全新候选。新候选必须重新绑定 frozen HEAD、manifest SHA-256、run/reference/budget/dataset，并在新的精确授权前保持 outbound=0。

candidate-07 绑定 frozen HEAD=`e4ba0c6c5909bb04bbcd0206085e95952b2350a3`、run ID=`knowledge-p5-live-v4-20260828-candidate-07`、manifest SHA-256=`af545166b37a33899d6f1d7830c09472df8cc2fe45047fea242ecc524bfc2211`、authorization reference=`P3_00:GATE-079` 和最多78次预算。正式 authorization SHA-256=`47575441f1c9123facc19ad32210375cb919174c0260c6fc0e612740abf07a06` 创建后，launcher 的授权后预检又执行 `test_candidate_07_prepared_assets_contain_no_secret_or_live_result`，该准备态测试断言 authorization 不存在，形成不可同时满足的合同。运行在任何服务启动或模型 outbound 前以 `failed_unconsumed` 停止：model/paid/answer/business/retry/resume 均为0；有限 failure SHA-256=`919fa1480b2ad3c7144559a3f10746ded7e0d069beae0977e0a7222e771d32d6`。该运行的 Effectiveness=`Invalid run`，不改变最新有效 `Partially effective` 结论，不得重跑、补跑、续跑或自动创建 candidate-08。

消费后闭环保持上述三项资产字节不变：preparation 从 frozen HEAD 校验准备态，history 测试锁定三项精确哈希、100项资产、唯一 failure 和0调用计数；launcher 后续版本仅修正 preflight 状态合同，不赋予 candidate-07 再次执行资格。

## 8. 状态权威与有限收口

工作包和 Gate 的状态只在 P3 维护，本计划不复制 Gate 表。当前 UAT 结论为：Functional=`Passed`（37/37）；latest valid Effectiveness=`Partially effective`；candidate-07=`Invalid run / failed_unconsumed`。有效但非 effective 的运行证明效果已被测量，不等于整体效果达标；无效运行只证明该次执行合同未形成测量，也不自动触发新候选。

## 9. 回滚与失败处理

- 生产回滚：设置 `AGENT_KNOWLEDGE_ENABLED=false` 并重启，Business 三动作不变；
- 功能失败：先判断实现、Harness、环境、设计或过度门禁，不删除测试或放宽安全规则；
- 效果失败：保留新 run append-only 证据，如实分类，不补跑或改判；
- 需要正文、mapping/index、公共接口或权限变化时停止并申请追加授权。

## 10. 评审记录

| 轮次 | 范围 | 结论 |
|---|---|---|
| 内审 1 | 功能/效果分离、case 完整性、唯一链路 | Passed |
| 内审 2 | 权限、出域、失败优先级、历史不可变 | Passed |
| 内审 3 | DAG、证据口径、过度设计与跨文档链接 | Passed |
| 独立评审 | 无 S0/S1/未处理 S2；可作为 Knowledge 验收依据 | Passed |
| v1.1 三轮内审 | 37 case 追踪、诊断到优化映射、历史边界与 GATE-072 无环 | Passed |
| v1.1 独立评审 | 无 S0/S1/未处理 S2；功能已通过，效果仍为 `ineffective` | Passed |
| v1.2 状态与代码评审同步 | 37/37 功能追踪、candidate-04 `ineffective`、candidate-05 非 live 冻结及 `GATE-072` Open 一致；正式代码评审无 Blocker/Major | Passed |
| v1.3 效果 UAT 收口 | candidate-05 绑定、44 次 paid journal、592 项阶段事件、安全 Gate、人工 rubric、`partially_effective` 结论和历史不可变一致 | Passed |
| v1.4 七项收口计划同步与独立复评 | candidate-04/05 历史分离、当前 Summary v3、Python 正式入口前置及 candidate-06 新授权门禁无环；无未处理 S2 | Passed |
| v1.6 三轮内审与独立评审 | candidate-05 分母/归因冲突、Summary V4、效果口径 v2 和 candidate-06 精确授权边界；无 S0/S1/未处理 S2 | Passed |
| v1.7 实施状态复核 | Summary V4 生产单绑定、效果口径 v2、全量/E2E/类型/历史回归证据与 `GATE-075` 状态一致；无 S0/S1/未处理 S2 | Passed |
| v1.8 candidate-06 准备复核 | run/manifest/reference/预算、92项资产、首 outbound 消费、失败关闭和历史哈希一致；未创建正式授权或 outbound | Passed |
| v1.9 candidate-06 消费后评审 | 失败事实、44 次付费终态、592 阶段记录、最终 allowlist 缺口、历史不可变及新候选授权无环；无 S0/S1/未处理 S2 | Passed |
| v1.11 三轮内审 | candidate-07 终态、功能/效果分离、UAT/P3/evidence 权威边界、历史不可变及无新候选检查完成；修复 P3 摘要状态与关闭循环 | Passed |
| v1.11 独立评审 | 37 个功能用例、最新有效效果、candidate-07 无效测量及跨层引用一致；S0=0、S1=0、未处理 S2=0 | Passed |
| v1.12 三轮内审 | 当前 authority、35/37 case、最新有效/最新执行/当前版本三层状态、历史哈希和 P3 DAG 完成三轮核对；第 1 轮修复 P3 状态与依赖，第 2～3 轮无新增问题 | Passed |
| v1.12 独立评审与复评 | 第 1 轮修复多余 `Not run` 效果枚举；复评确认四类效果结论与 `evidenceStatus=missing` 职责分离，S0=0、S1=0、未处理 S2=0 | Passed |
| v1.13 Rewrite V2 聚焦评审 | 精确 JSON 合同、V1 历史不可变、功能 non-live 证据和当前任务组合效果证据缺口分离；S0=0、S1=0、未处理 S2=0 | Passed |

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

## 12. 评审记录

| 轮次 | 范围 | 结论 |
|---|---|---|
| 内审 1～3 | 语料 UAT/在线功能/效果职责分离、14 case、P0/P1/P2、权限/Evidence、阶段 B 和图谱边界 | Passed |
| 独立评审 | 用例与 REQ-KCORPUS、DR-KRET/KEV、P3 GATE-083/084 一致；S0=0、S1=0、未处理 S2=0 | Passed |
| v1.15 聚焦内审 | 明确 `source_unreachable/source_unverified` 只表示来源核验阻塞，不等于正文缺失；P0/目标P1未核验时发布 Gate 保持 Open | Passed |
| v1.15 独立评审与复评 | 复核14项专项与REQ/L1/L2/P3：来源不可达不冒充正文缺失，P0/目标P1未核验只阻塞发布，阶段B/topK不进入本阶段；S0=0、S1=0、未处理S2=0 | Passed |
| v1.17 正式代码/数据评审首轮 | 发现 attempt-01 的 PDF 用例绑定 live manifest，而 P0 live asset 均为 Word；时效和当前税法也未在同次运行直接断言 | Fixed |
| v1.17 复评 | attempt-02 在同次运行直接验证 native PDF parser、candidate ACTIVE/EXPIRED、tax.law 当前税法、精确 alias、酒店住宿分类与税率原文；14/14 Passed，S0/Blocker=0、S1/Major=0、未处理 S2/Minor=0 | Passed |
| v1.18 正式代码/数据评审首轮 | 发现已发布 a2 对 4 个 legacy DOC 整体扁平化，条款引用为 0；attempt-03 另暴露 `old_index` 结果元数据仍指向初始基线 | Fixed |
| v1.18 复评 | candidate a4 含 738 个附件 chunk、55 个条款引用且无孤立附件；attempt-04 记录真实前序 a2，并验证当前 snapshot、14/14 Passed，S0/Blocker=0、S1/Major=0、未处理 S2/Minor=0 | Passed |
| v1.19 正式代码/数据评审首轮 | 发现单资产网络/损坏容器异常未统一隔离，且 a4 构建源码哈希早于最终修复，不能作为最终源码可复现发布证明 | Fixed |
| v1.19 复评 | candidate a5 以最终工具源码重建相同规范化内容，UAT attempt-05 14/14 Passed，a4→a5→a4→a5 发布/回滚演练成功；S0/Blocker=0、S1/Major=0、未处理 S2/Minor=0 | Passed |

## 13. v1.19 阶段 A 执行结论

- 规范 UAT ID 为 `UAT-KCORPUS-A-01～14`，与 strict Schema、launcher 和有限 evidence 一致；早期文档中的 `UAT-KC-A-*` 仅为编号漂移，不代表用例失败。
- build run=`knowledge-corpus-stage-a-v1-20260903-candidate-08`；最终 UAT run=`knowledge-corpus-stage-a-uat-v1-20260903-attempt-05`；candidate=`agent-doc-tax-policy-v4-20260903-corpus-a5`，UUID=`SurWRSglRd6ZRddEBWy2Sw`。
- 14/14 Passed；model outbound=0，Business call=0；keyword/vector 直接 typed 检索、读取拒绝和 Evidence 合同均通过。
- attempt-01 有限结果 SHA-256=`5659904b75a211ed6f046509783a53679af2bb499df590c4713f1fbc7c1fb21b`，attempt-02 有限结果 SHA-256=`24332d732058f04ad01ea431f42e8432819d99ecaca0533b33038bca931502bd`，均保持字节不变。attempt-03 虽通过行为断言，但结果中的前序索引仍错误指向初始基线，不能作为最终发布追踪；attempt-04 保留为 a4 有效中间证据。最终 attempt-05 有限结果 SHA-256=`ad86ae89b48e0c96426cbadddef526d391e6b61214a254bba90049286afc162a`；同次运行验证 738 个附件 chunk、55 个条款引用、ACTIVE/EXPIRED、`tax.law/tax-law-v1`、精确 alias、酒店住宿分类与税率原文。
- 首次使用最终用户问句进行向量断言时发现目标附件位于 rank 59，alias 已立即回滚；该失败属于阶段 B 改写/排序边界，不改写为阶段 A 失败。改用直接原文检索语义后通过，最终发布仍执行完整切换→回滚→再发布三次原子操作。
- 阶段 B 输入固定为 `domain_selection`、`query_rewrite`、`ranking`、`failure_semantics`；本轮未修改在线算法、Prompt、topK 或 fallback。
- 既有 Knowledge Functional 37/37、Business 35/35 与历史 candidate/evidence 保持不变。

## 14. 阶段 B 独立专项验收（真实首例失败，未收口）

保持原37项功能用例、阶段 A 14项语料证据及历史 P5 效果结论不变。阶段 B 使用新的测试/运行命名空间，不能覆盖旧 evidence，也不依赖图谱。核心 P0 必须满足预先冻结的条件；整体 effective 不作为无限重跑理由，核心功能也不得被该原则豁免。

| Case | 输入/风险 | 预期与验证方式 |
|---|---|---|
| UAT-KB-001 | 酒店行业的住宿费用，适用哪种税率？ | 缺少决定适用税率的条件时明确询问，不默认为一般纳税人；fake及真实 |
| UAT-KB-002 | 一般纳税人采用一般计税方法，2026年提供住宿服务适用何种增值税税率？ | P0：授权原文同时证明服务分类和当期适用规则，有连续引用；真实 |
| UAT-KB-003 | 住宿服务与不动产租赁的分类有什么区别？ | P0：两类区别由实际原文支持，不能混成同一类；真实 |
| UAT-KB-004 | 住宿服务的政策分类和增值税法的税率规定是什么？ | P0：检索前一次计划两域，证据涵盖分类及法条；真实 |
| UAT-KB-005 | 小规模纳税人提供住宿服务，未指定期间和计税条件 | 不补造期间；澄清或明确证据不足，不返回无条件确定税率；fake及真实 |
| UAT-KB-006 | 2016年一般纳税人按一般计税提供住宿服务 | P0：保留2016，不拿2026税法冒充当期规则；真实 |
| UAT-KB-007 | 日期、数字、否定、征收率与税率 | 同索引固定改写反例；丢失/新增显式条件拒绝，检索0；fake |
| UAT-KB-008 | policy单域、law单域、双域、无关问题 | 域一次确定；不无条件广播、不失败扩域；fake及真实保留问题 |
| UAT-KB-009 | 单路技术失败 | 按批准 coverage 条件返回部分或失败，绝不宣称全面完成；fake |
| UAT-KB-010 | 全路径失败、非法响应、超时 | downstream_failure/timeout，不是no_result；fake |
| UAT-KB-011 | 成功检索零命中、有候选但证据不足 | 不同有限 reason/固定用户文本，摘要调用按阶段计数；fake |
| UAT-KB-012 | 双域中任一整域拒绝、角色矩阵 | 拒绝优先、被拒正文零暴露，summary0；fake+Java安全链 |
| UAT-KB-013 | 三层出域拒绝、敏感输入 | 前者summary0，后者全部模型0；fake |
| UAT-KB-014 | 非法引用、非连续子串、重复ref | 严格拒绝，不放宽validator；fake |
| UAT-KB-015 | 酒店问题多种措辞 | 与对应P0相同显式条件/证据目标，不用逐句特判；真实 |
| UAT-KB-016 | 软件产品即征即退等非酒店保留问题 | 预冻结原文核对、必要条件和无回退；真实 |
| UAT-KB-017 | 候选预算、并发、取消、client关闭 | 最多2域4search2embedding2rerank、无重试和无第二动作；fake |
| UAT-KB-018 | vector窗口、稳定融合、锚点和字节预算 | 20+1探针正确截断；跨域分数不直接比较；Evidence有界/不足失败关闭；Java+Python |

真实执行清单在 non-live 通过后从上述场景确定，初始累计上限20个端到端请求、60次模型 HTTP；用户随后仅将E2E累计上限调整为21，当前执行协议见§14.18（selection/rewrite/summary均计入模型预算）。该清单必须包含核心P0、措辞变体及非酒店保留样本；错误注入不浪费付费请求。单请求硬上限3次模型、4search、2embedding、2rerank；模型/search/embedding/rerank累计上限仍60/80/40/40。实际请求更少时同步收紧。不得通过额外预跑消耗未记录模型请求。

执行前冻结 commit、run ID、case/预期、人工原文核对的gold、任务/Prompt、配置/alias/UUID/策略快照及预算。人工gold必须记录来源标识、内容哈希和必要条款位置；不能由待测模型评分或仅用正文关键词旗标替代。只把可证明适用的原文作为标准，缺失条件不得推断。

对比基线与新实现使用相同索引、预定问题及gold。分别报告域准确性、各路径排名/截断、融合和rerank排名、Evidence覆盖、有效摘要、引用与人工usefulness；没有实际模型基线时明确标注，只比较可复现的离线阶段，不伪造端到端提升。基线诊断JSONL由P3 §20引用。

新 V3 的澄清/unsupported/非法输出与失败不回退原问题。合法 search 中原问题始终保留为摘要边界。时效未知不是当前有效；现有公共 DTO 缺少完整效力信息，无法证明时不得肯定回答，也不因此扩展 DTO/语料/索引。

首个真实失败停止该批并保留有限状态、调用计数和已完成case；不得补跑、续跑或创建额外付费候选。未执行与失败分别记录；其余授权内 fake/评审可继续，但核心P0缺证据则阶段B保持未完成。只保存安全摘要、引用标识/哈希和有限指标，不持久化原始模型响应、JWT或未授权正文。

### 14.1 已冻结批次及验证规则

`tests/system_e2e/knowledge_stage_b_cases.py` 固定10个真实case：KB-001、015a、004、002、003、005、006、015b、016、008；执行顺序先澄清和单域定义，再双域及复杂期间，任一失败停止后续。总预算收紧为10端到端、30模型、40search、20embedding、20rerank；Business/answer/retry/resume均0，错误注入留在fake测试。当前该批已经消费并因首例失败停止，不能再次执行；终态见§14.2。

`knowledge_stage_b_uat.py prepare` 在工作树干净后绑定提交、任务3/4、配置、a5索引UUID、所有实现及Java可执行资产SHA、case和原文gold。仅`execute`读取模型Key，真实认证及Spring入口调用当前生产Runtime，不使用评估专用在线分支。gold仅在结果产生后判定，不参与域、query、排序或Evidence。必要原文同时检查模型Evidence内容hash和最终已校验引用内的精确条款，不以只命中同文档代替正确回答；2026用例另需生效条款。

原文rubric由本轮逐条读取已发布材料核对后固定；属于自动化辅助的原文核对，不代表外部税务专家批准。框架自动执行精确条款/域/状态rubric，不让待测模型自评分；实际usefulness需在最终结果中独立、如实评述。准备烟测为真实auth→Spring→stub Runtime，unsupported=422；没有模型或Knowledge请求，不冒充专项UAT。

### 14.2 真实专项结果与未执行项

历史批次`knowledge-stage-b-uat-v1-20260904-run-01`的绑定、五项hash、调用账及代码评审问题见P3_00 §20.6～20.7。原始有限资产位于`agent-runtime/tests/system_e2e/knowledge_stage_b_run_01/`；历史校验从冻结提交读取源文件，不以当前修改后的源码冒充运行基线。后续独立批次见§14.5，不覆盖本节历史结论。

| 冻结顺序 | Case | 验证目标 | 真实结果 |
|---|---|---|---|
| 1 | UAT-KB-001 | 住宿费用适用判断缺条件，应澄清且零检索 | Failed：实际success，两域检索、1条law引用；不符合冻结预期 |
| 2 | UAT-KB-015a | 生活服务中的住宿定义 | Not executed：首例失败停止 |
| 3 | UAT-KB-004 | 政策分类与法律规则共同取证 | Not executed：同上 |
| 4 | UAT-KB-002 | 2026一般纳税人、一般计税 | Not executed：同上 |
| 5 | UAT-KB-003 | 住宿与不动产租赁区别 | Not executed：同上 |
| 6 | UAT-KB-005 | 小规模纳税人缺期间澄清 | Not executed：同上 |
| 7 | UAT-KB-006 | 2016历史期间 | Not executed：同上 |
| 8 | UAT-KB-015b | 明确条件的不同措辞 | Not executed：同上 |
| 9 | UAT-KB-016 | 非酒店软件政策回归 | Not executed：同上 |
| 10 | UAT-KB-008 | 单law域具体法条 | Not executed：同上 |

实际1次端到端、3次模型、4次search、2次embedding、2次rerank，Business/retry/resume为0。模型三个任务均succeeded不能代替UAT通过；本次不是invalid_run，批次终态为failed。已停止owned进程、关闭clients并扫描删除临时原始日志，没有续跑或额外付费候选。冻结result单case e2e误记0的显示问题由顶层总数1和唯一case行校正解释，原资产不修改。

### 14.3 non-live 风险证据与验收结论

以下路径均相对`agent-runtime/`。本轮正式隔离回归实际通过，精确总数只在P3_00记录；fake仅证明合同/控制流，不能覆盖§14.2未通过的模型语义效果。

| UAT风险 | 当前自动化证据 | 结论边界 |
|---|---|---|
| KB-001/005/007：澄清、非法改写、日期/比例单位/否定 | `tests/unit/knowledge/test_semantic_planner.py`；`tests/integration/knowledge/test_stage_b_production.py` | 通用守卫和零调用通过；run-01真实澄清失败，run-02首例通过见§14.5，不外推其他措辞 |
| KB-008/012/017：域、拒绝、无fallback、并发取消 | `tests/unit/knowledge/retrieval/test_quality_ranking.py`；`tests/unit/knowledge/retrieval/test_stage.py`；当前Spring Knowledge E2E及Java安全链 | 控制流/授权通过；不代表未执行真实单域/双域case通过 |
| KB-009/010/011：部分/全部失败、零命中、coverage完整性 | `tests/integration/knowledge/test_stage_b_production.py`；`tests/unit/knowledge/retrieval/test_stage.py` | reason、失败优先级、路径集合和零调用断言通过 |
| KB-013/014：出域、敏感输入、引用 | `tests/unit/knowledge/evidence/test_builder_policy.py`；`tests/unit/knowledge/evidence/test_summary_validation_reasons.py`；当前Knowledge功能追踪 | 既有出域/引用校验保持，不证明最终语义完整 |
| KB-018：窗口、排序、锚点、Evidence预算 | `tests/unit/knowledge/retrieval/test_quality_ranking.py`；Java `KnowledgeSearchServiceTest` | 有界合同通过；真实必要分类条款未入Evidence，质量风险仍开放 |
| KB-002/003/004/006/015/016：核心条款与措辞覆盖 | `knowledge_stage_b_diagnosis.v1.jsonl`及local_validation v1～v7；§14.2真实结果 | 同快照离线诊断存在；尚无本批对应真实成功证据 |

run-01时点阶段B专项Functional=Failed（KB-001），安全控制和non-live回归通过，整体Effectiveness未完成测量，不给出effective或整体改善结论；当前独立批次结论见§14.5。最新有效历史P5等级仍独立为partially_effective；阶段A14项、既有Knowledge37项和Business35项功能追踪不被新专项覆盖或改判。

住宿定义从policy keyword rank19经过域融合rank34、rerank rank31后未入最终20/Evidence8。有限排名重放与真实final20一致，完整身份序列中该条款位于48；该次排除发生在Evidence配额处理之前，不支持通过放宽配额关闭问题。KB-001的冻结预期本身是澄清且零检索，没有requiredGold；错误分支中的条款丢失只作为独立质量风险，不把其余9个未执行用例改判为失败。v7人工聚焦query可使住宿定义/生活服务总类入Evidence，但不能冒充真实模型或本批端到端改善；law规则进入Evidence且引用合法也不能证明适用条件充分。没有保留原始模型响应或改写文本，因此不推断未记录的最终具体税率文案或唯一根因，也没有独立专家usefulness评分。复核命令及边界见P3_00 §20.9。

run-01终止时不新增付费运行。后续方案先做非live根因/合同复核，真正的模型效果确认须独立授权，不能复用该批剩余预算；随后获得的授权及独立结果见§14.5。

### 14.4 失败后的非live修复边界

L2_01_00 v1.18批准DR-KFLOW-019：仅用新Rewrite V4 Prompt纠正“具体主体”过窄前提，区分适用判断与资料查阅，保留V3严格合同。V4现已实施；同一生产根的指令绑定、精确解码、旧V3拒绝装配与澄清零调用已经non-live验证，执行账见P3_00 §20.8。当前固定功能追踪的任务元数据已同步V4，37个case及风险预期不变；不得把fake选择clarification当成真实模型已修复。§14.2的V3失败终态、冻结case及gold不变，该批其他9例始终未执行。新授权之前V4真实效果为Evidence missing；当前有限真实证据及仍未完成事项见§14.5。

### 14.5 新授权V4独立验证

用户随后明确授权新的独立批次；授权账和硬预算见P3_00 §20.10。run-02复用§14.1原10例及顺序/gold，不改判或重启run-01；新版本入口重新冻结代码、Prompt、配置/索引及预算，从首例验证V4。单批最多10端到端/30模型，计入原目标累计20/60上限；真实失败后立即停止，不补跑或自动追加第三批。新增任务版本核对、澄清零下游和单case e2e计数验证，不改变原验收阈值。

本批已执行并停止，绑定与六项资产hash见P3_00 §20.11；当前结果如下：

| 顺序 | Case | 真实结论 | 有限证据 |
|---|---|---|---|
| 1 | UAT-KB-001 | Passed | HTTP200/no_result/clarification_required；selection及Rewrite4成功，2模型且检索/摘要0 |
| 2 | UAT-KB-015a | Failed | HTTP502/downstream_failure；Rewrite4 invalid_output，2模型且检索0，未验证必要条款 |
| 3 | UAT-KB-004 | Not executed | 第二例失败停止，不能推断跨域取证通过 |
| 4 | UAT-KB-002 | Not executed | 同上，未验证2026一般纳税人场景 |
| 5 | UAT-KB-003 | Not executed | 同上，未验证住宿/租赁区别 |
| 6 | UAT-KB-005 | Not executed | 同上，未验证缺期间澄清 |
| 7 | UAT-KB-006 | Not executed | 同上，未验证历史期间 |
| 8 | UAT-KB-015b | Not executed | 同上，未验证不同措辞 |
| 9 | UAT-KB-016 | Not executed | 同上，未验证非酒店保留问题 |
| 10 | UAT-KB-008 | Not executed | 同上，未验证单law域法条 |

有限资产为`agent-runtime/tests/system_e2e/knowledge_stage_b_run_02/`，由`test_knowledge_stage_b_run_02_history.py`校验；manifest Schema2和结果Schema1分别冻结，所有runtime资产append-only。实际2端到端/4模型，search/embedding/rerank/Business/answer/retry/resume为0；两批合计3端到端/7模型/4search/2embedding/2rerank。cleanup全部通过，不保留原始响应，不再次读取模型Key。

该批终止时专项Functional=Failed（KB-015a），安全停止生效；KB-001精确反例获得真实通过，但完整效果、必要Evidence覆盖和usefulness尚未验证，不声明整体effective。`invalid_output`未记录具体decoder分支，不能断言是某字段、截断或Prompt错误；result中`taskBindingValid=false`是完整成功任务链未满足，不是V4版本错绑。既有阶段A/Knowledge37/Business35结论及历史P5不改判。该批不允许续跑；随后新授权的独立诊断批次见§14.6。

### 14.6 独立run-03与有限失败诊断协议

用户已授权“先补齐有限失败诊断，再准备并执行一次重新冻结的独立验证批次，仍受原累计调用上限约束”。本次仅新增版本化测试入口，不修改L2_01_00 §8/12的生产行为、公共DTO、Prompt、任务版本、decoder或validator。实现约束编号为KB-DIAG-001，代码落点为`tests/system_e2e/knowledge_stage_b_uat_v3.py`及直接诊断模块/测试，运行授权账由P3 §20.13唯一治理。

1. 原10例的顺序、问题、gold、阈值、任务4/4及Prompt hash不变；run-03是新独立批次，不覆盖run-01/02。manifest Schema3绑定当前干净HEAD、源码/可执行资产、索引/配置、两个旧批全部hash及实际调用数、输出目录、诊断版本和累计预算。不得凭剩余预算启动第四批。
2. 保留旧结果Schema1语义；新case有限扩展`modelFailures`最多3项，每项仅含taskId、taskVersion、stage、reason。taskId/version只允许当前三个任务；stage只允许provider、task_decoder、gateway。reason只允许代码固定枚举，不保存异常自由文本、JSON键/值、正文、问题、响应、JWT或密钥。
3. provider诊断只在真实transport抛出既有异常之后映射：严格JSON、响应头/大小、响应模型/envelope、finish reason、tool/usage、transport/timeout/cancel及unknown有限类别；不保存实际model名称或finish值。Rewrite任务诊断只在原decoder已经拒绝后，在内存区分response形状、JSON结构、顶层合同、outcome、queries、missing_conditions或未分类合同失败，不改变原拒绝结果。
4. instrumentation仅在单一CLI进程作用域运行，原transport/decoder仍是唯一接受判定。返回值、原异常、请求和调用数保持不变；未知诊断映射为有限fallback，不能把失败改为通过或触发第二请求。不得为记录诊断吞掉取消。每case重置诊断，request-context隔离，finally恢复绑定和释放client。
5. 在结果写入前校验有限字段/枚举/数量；实际未捕获的失败只允许依据现有observation.failureKind写gateway类别。成功任务无失败条目；不得根据历史结果臆造run-02具体原因。
6. prepare/check-environment不读取模型Key。真实执行前必须完成fake等价性、故障分类、超限/未知值、请求隔离、绑定恢复、历史hash和累计预算测试。check-environment只执行原有认证→stub公共入口烟测，模型/Knowledge调用0。首个失败停止本批，所有未执行case单独列出；旧批完整字节不变。

本次诊断不增加生产在线流程或新的门禁，不把可观测性改进冒充KB-015a语义已修复。设计协议评审记录、测试结果和真实执行状态在P3 §20.13后续追加。

### 14.7 run-03独立批次终态

本批按§14.6执行一次并因第二例失败停止，frozen HEAD、预算、六项不可变hash和有限根因矩阵见P3 §20.14，原始有限文件位于`agent-runtime/tests/system_e2e/knowledge_stage_b_run_03/`。与run-02不同，本批selection/Rewrite4/Summary4全部succeeded、modelFailures为空；不能回溯解释run-02格式错误或宣称其稳定修复。

| 顺序 | Case | 结果 | 有限证据 |
|---|---|---|---|
| 1 | UAT-KB-001 | Passed | 澄清，HTTP200/no_result，2模型且所有检索/摘要0 |
| 2 | UAT-KB-015a | Failed | 期望单policy，实际policy+law；lodging引用true、living引用false，1条引用；HTTP200/success不等于UAT通过 |
| 3 | UAT-KB-004 | Not executed | 第二例失败停止 |
| 4 | UAT-KB-002 | Not executed | 同上 |
| 5 | UAT-KB-003 | Not executed | 同上 |
| 6 | UAT-KB-005 | Not executed | 同上 |
| 7 | UAT-KB-006 | Not executed | 同上 |
| 8 | UAT-KB-015b | Not executed | 同上 |
| 9 | UAT-KB-016 | Not executed | 同上 |
| 10 | UAT-KB-008 | Not executed | 同上 |

实际2端到端/5模型/4search/2embedding/2rerank，三批累计5/12/8/4/4，Business/answer/retry/resume0。两项必要原文均已进入summary输入（Evidence第2/4项）；本例排除语料缺失和topK截断作为直接损失点。选域过宽及最终覆盖未满足冻结rubric，专项Functional=Failed、整体Effectiveness仍未完成测量。现有证据不支持盲改检索窗口或继续付费试错，也不得事后降低该case的gold要求。客户端、owned进程、临时原始日志清理通过；无run-04，不复用剩余名义预算。既有35/37固定功能与阶段A验收不改判。

### 14.8 后续非live修复的证明范围

L2_01_00 DR-KFLOW-020新增Rewrite V5最小必要域指令；当前任务切换/测试状态见P3 §20.15。需要验证单policy、单law、真正双域，以及非酒店表达、澄清、unknown/disabled域、模型失败和无fallback。不改上述10个case、gold、顺序、阈值或run-01～03资产。fake只证明指令和执行边界，不证明LLM语义通过；V5真实效果状态为Evidence missing，不能继承V4任何成功结果。Summary V4必要条款覆盖另行核查，历史failed保持failed。当前未授权新真实批次，不生成新manifest或读取模型凭据。

### 14.9 Summary V5 分类上下文证明验证

用户确认保留原问句与双条款判据，由L1_01 KQ-AD-017及L2_01_02 DR-KEV-027明确分类上下文也需原文支持。不得删减KB-015a的requiredGold，或把原Failed改判为通过。新任务不强制双引用：单一连续片段若能完整证明定义与分类，允许单引用；分散证据需不同ref，缺失/冲突或超过既有边界则insufficient。

non-live覆盖：V4→V5仅version/Prompt改变；显式分类与定义、非分类单要点、单/多ref、无关类别不展开、缺失/冲突/唯一ref限制；非法引用、模型异常/超时、出域拒绝和取消的既有失败语义不变。使用合成输入和fake证明任务/调用边界，不能证明LLM语义或替代逐case真实结果。

当前Summary V5已实施，合同、当前生产根、Spring E2E及失败边界non-live回归通过，效果仍为Evidence missing；最新有效P5仍是历史partially_effective，旧Summary V4缺口和run-01～03终态保持原貌。既有37项功能追踪的Passed不外推为新增分类语义效果已通过，v2追踪文件仍是其原版本基线而非当前任务的测量。没有新manifest、run-04或模型调用授权。实际实施、测试、评审和Git状态见P3 §20.17。

### 14.10 新授权V5独立验证

§14.9之后用户明确授权准备并执行一次新独立V5批次，授权账见P3 §20.18。沿用§14.1的原10例、顺序、问题、人工原文gold和全部判据，前三批结果不变。新入口绑定selection-v4/Rewrite5/Summary5及当前Prompt，manifest Schema4保存前三批全部hash/实际预算；仍按失败即停止、未执行单列、无重试/续跑。KB-DIAG-001有限诊断Schema字段/原因枚举不变，诊断版本v2仅将允许任务版本更新为当前5/5，旧诊断源文件保持不可变并在CLI作用域适配。

先证明当前生产根与任务绑定、Prompt请求哈希、累计预算、防复用、原异常/取消透传、上下文恢复及原gold判定等价，再冻结执行。不得把版本升级当成真实效果已通过；新增结果形成前，核心P0及整体专项仍未收口。原37/35功能追踪、阶段A及历史P5结论保持独立。

### 14.11 run-04独立V5批次终态

本节是§14.10的实际结果，取代§14.8/14.9尚无V5真实证据的时点说明，不修改任何历史执行结论。frozen HEAD、六项hash、调用预算、有限诊断及评审见P3 §20.19；归档为`agent-runtime/tests/system_e2e/knowledge_stage_b_run_04/`。沿用§14.1原10例，未改变gold或通过条件。

| 顺序 | Case | 结果 | 有限判据 | 模型/search/embedding/rerank |
|---|---|---|---|---|
| 1 | UAT-KB-001 | Passed | HTTP200/no_result、clarification_required，所有检索与摘要0 | 2/0/0/0 |
| 2 | UAT-KB-015a | Passed | 仅policy，lodging与living两条原文校验true，2条引用 | 3/2/1/1 |
| 3 | UAT-KB-004 | Failed | 双域正确，但仅law_rate校验true，lodging/living均false；HTTP200/success不等于通过 | 3/4/2/2 |
| 4 | UAT-KB-002 | Not executed | 第三例失败停止 | 0/0/0/0 |
| 5 | UAT-KB-003 | Not executed | 同上 | 0/0/0/0 |
| 6 | UAT-KB-005 | Not executed | 同上 | 0/0/0/0 |
| 7 | UAT-KB-006 | Not executed | 同上 | 0/0/0/0 |
| 8 | UAT-KB-015b | Not executed | 同上 | 0/0/0/0 |
| 9 | UAT-KB-016 | Not executed | 同上 | 0/0/0/0 |
| 10 | UAT-KB-008 | Not executed | 同上 | 0/0/0/0 |

专项Functional=Failed；完整专项Effectiveness未测完，不赋予effective/partially_effective等级。前三批加本批累计8端到端/20模型/14search/7embedding/7rerank，Business/answer/retry/resume0；本批自身为3/8/6/3/3，授权已终止，不续用剩余预算或自动创建run-05。

本次KB-015a证明V5可在原问句下正确单域并提供定义/分类证据，不证明其他表达稳定通过。KB-004中两项分类原文已在policy keyword第3/8名；living在域内rerank第28并未进入final20，lodging进入final第9但未进入Evidence8，Summary输入缺少两项必要原文。不能再将该例解释成单纯Summary格式错误、原文不存在或未选择policy；也不能由有限hash证据还原未保存的模型文本或归因全部落选原因。

安全与执行边界：实际任务为selection-v4/Rewrite5/Summary5，全部succeeded，无模型失败诊断条目；clients、owned进程、原始临时日志和敏感扫描均通过。通过的结构/引用/域校验不等于完整语义验收，核心覆盖仍待处理。原37项Knowledge功能、35项Business功能、阶段A及历史P5最新有效partially_effective保持其原证明范围；不因这2项通过宣称阶段B完成。

### 14.12 Rewrite V6 非live证明范围

L2_01_00 DR-KFLOW-021已通过三轮内审与只读设计复评，当前生产绑定切换为Rewrite6/Summary5。该切片只调整每域表达的背景归属，不修改排序、锚点、Evidence配额、Summary、decoder或既有Guard。non-live使用合成双域/单域计划，证明各域表达原样进入keyword/embedding/rerank、原问题进入Summary、既有显式条件偏差和非法结构继续零下游调用；非酒店与明确限定本域税种的表达同样保留。

这些测试不证明LLM能够可靠判断子问归属，不能继承run-04两例成功，也不能关闭KB-004及其他未执行用例。V6真实效果为Evidence missing；原10例、顺序、gold、四批不可变结果、历史37/35功能追踪与Stage A保持原范围。新付费运行未获授权；不创建run-05、不读取模型凭据、不执行outbound。配额设计和核心P0覆盖仍未关闭，当前实施/测试/评审证据见P3 §20.22。

### 14.13 质量策略V2专项验证

本节记录§14.12之后的恢复授权，不改变过去未获授权的事实。拟用Rewrite6/Summary5及quality-v2执行当前生产根：每域语义首位、域内rerank轮转、同父条款不额外限3；总Evidence8/32768bytes、最终20、5points/512quote不变。设计和实现状态由P3 §20.23治理。

non-live必须覆盖：关键词第一名但语义低位不强制入选、同域顺序/跨域轮转/重复identity不占位、同文档第四条按rank保留及第九条总数拒绝、字节/域覆盖/策略拒绝summary0、V1/legacy限额不变、内部版本一致及未知/错配失败关闭；匿名合成与固定历史候选只证明算法合同，不作为真实模型效果。

真实专项仍保留§14.1原10例、顺序、判据和gold；不得以域覆盖替代定义/分类/税率原文的逐项判定。恢复授权仅允许通过设计、fake、代码复核及当前快照冻结后的一次独立批次，上限10 E2E/30模型/40search/20embedding/20rerank，累计仍受原20/60/80/40/40约束；失败即停，旧批不续跑、不自动建立后续批次。准备前无新manifest/结果，效果仍Evidence missing；真实请求/排名诊断只保留已批准有限字段，不保存query、正文、原模型响应或JWT。

当前进展：V2已实施，生产根fake、排序/选择边界、调用次数、配额错配Summary零调用及新run-05 runner的fake验证通过；实际命令结果归P3 §20.24。新批尚未冻结或执行：环境预检曾失败，单独服务启动/清理复核成功，但Git持久化句柄占用及Transaction测试容器验证尚未解除。没有manifest、consumed或模型outbound，不把预检错误标成新效果结论，也不重置既有四批预算。最新已执行专项仍为§14.11的2通过/1失败/7未执行；当前V2效果为Evidence missing，Stage B仍未完成。37/35功能追踪和Stage A保持原证明范围，不继承为新增真实专项通过。

2026-09-07恢复核实：上述环境阻塞已解除；Transaction容器测试和独立Spring→Runtime无模型预检通过，有限原失败资产仍保留。当前NONLIVE/UAT执行状态以P3 §20.25为准。只允许既有授权的一次run-05，任务Rewrite6/Summary5和quality-v2，不改变原10例/顺序/gold；实际freeze和结果产生前仍为Evidence missing。

### 14.14 run-05质量V2专项终态

2026-09-07按§14.13执行，冻结与7项资产hash见P3 §20.26；归档`agent-runtime/tests/system_e2e/knowledge_stage_b_run_05/`。原10例、顺序、gold和安全/效果判据未改；先前环境失败及本次恢复预检分别保留。

| 顺序 | Case | 实际结果 | 模型/search/embedding/rerank |
|---|---|---|---|
| 1 | UAT-KB-001 | Passed：HTTP200/no_result、clarification_required；无检索及Summary | 2/0/0/0 |
| 2 | UAT-KB-015a | Failed：HTTP504/timeout；policy选择正确，keyword20条，但排序未完成，无Evidence/Summary | 2/1/1/1 |
| 3 | UAT-KB-004 | Not executed：第二例失败停止 | 0/0/0/0 |
| 4 | UAT-KB-002 | Not executed：同上 | 0/0/0/0 |
| 5 | UAT-KB-003 | Not executed：同上 | 0/0/0/0 |
| 6 | UAT-KB-005 | Not executed：同上 | 0/0/0/0 |
| 7 | UAT-KB-006 | Not executed：同上 | 0/0/0/0 |
| 8 | UAT-KB-015b | Not executed：同上 | 0/0/0/0 |
| 9 | UAT-KB-016 | Not executed：同上 | 0/0/0/0 |
| 10 | UAT-KB-008 | Not executed：同上 | 0/0/0/0 |

本批2端到端/4模型/1search/1embedding/1rerank，五批累计10/24/15/8/8，Business/answer/retry/resume0。全部模型任务为selection-v4/Rewrite6且succeeded，未调用Summary5；第二例taskBindingValid=false是缺少预期Summary而非用了旧任务。quality绑定正确不等于排序结果已验证。

安全/清理检查通过；返回timeout而非“未找到结果”，没有重试、续跑或第六批。专项Functional=Failed；完整Effectiveness未测完，V2必要Evidence覆盖仍Evidence missing，不继承run-04成功结论。原37项Knowledge功能、35项Business功能及阶段A结果不改判。下一步应先查明本地BGE推理在既有限时内的可用性，不能以health=200直接判定性能就绪；本目标不自动重新冻结或付费验证。

### 14.15 run-06新独立验证授权与证明范围

2026-09-07用户明确批准新的独立批次；授权及累计预算见P3 §20.28。§14.14的run-05终态保持不变，P3 §20.27两次合成本地诊断仅证明当前有限负载可用，不证明原超时根因。新批保持§14.1原10例、顺序、人工原文gold及全部判据，任务Rewrite6/Summary5和quality-v2不变，不调整窗口、超时、Prompt或安全边界。

版本化runner只新增无正文的下游操作/状态/HTTP状态码/耗时投影，以便区分新运行的依赖故障；诊断不能替代必要条款覆盖或把HTTP成功当作UAT通过。单批最多10端到端/30模型/40search/20embedding/20rerank，五批累计与本批合计仍受原预算限制，Business/answer/retry/resume0；首例失败即停止，不自动建立run-07。准备及fake通过不等于真实通过，当前仍为run-05的1通过/1失败/8未执行及V2效果Evidence missing。37/35既有功能追踪、Stage A和历史P5保持各自原证明范围。

### 14.16 run-06真实专项终态

冻结提交、manifest、六项SHA和诊断见P3 §20.29。本节取代§14.15准备状态，不覆盖过去五批结果。全部沿用原10例/顺序/gold：

| 顺序 | Case | 实际结果 | 模型/search/embedding/rerank |
|---|---|---|---|
| 1 | UAT-KB-001 | Passed：缺条件澄清；检索及Summary0 | 2/0/0/0 |
| 2 | UAT-KB-015a | Passed：单policy；lodging/living均true，2条引用 | 3/2/1/1 |
| 3 | UAT-KB-004 | Passed：policy+law；lodging/living/law_rate均true，3条引用 | 3/4/2/2 |
| 4 | UAT-KB-002 | Failed：HTTP502/downstream_failure；Rewrite模型succeeded，本地检索计划未形成 | 2/0/0/0 |
| 5 | UAT-KB-003 | Not executed：第四例失败停止 | 0/0/0/0 |
| 6 | UAT-KB-005 | Not executed：同上 | 0/0/0/0 |
| 7 | UAT-KB-006 | Not executed：同上 | 0/0/0/0 |
| 8 | UAT-KB-015b | Not executed：同上 | 0/0/0/0 |
| 9 | UAT-KB-016 | Not executed：同上 | 0/0/0/0 |
| 10 | UAT-KB-008 | Not executed：同上 | 0/0/0/0 |

本批4端到端/10模型/6search/3embedding/3rerank，六批累计14/34/21/11/11，Business/answer/retry/resume0。原跨域必要证据反例本次通过，但第四例及六个未执行用例未通过；专项Functional=Failed，完整Effectiveness未测完，不赋予effective/partially_effective等级。安全和owned资源清理通过，run-06授权已终止，不自动建立run-07。

第四例无下游操作，不能归因于此次BGE/ES；模型任务完成不等于本地语义校验通过。P3记录的中文词素/数字顺序误拒绝只由独立fake反例证实，不冒充历史模型输出。后续非live修复不得修改原问题、gold或本批失败资产，也不能复用本批剩余预算。原35/37功能追踪及阶段A继续保留原证明范围。

### 14.17 类别词保护纠偏的验收边界

L2_01_00 DR-KFLOW-023已纠正已有税务类别词的数值误识别。新增non-live已证明完整条件下年份前置可通过，类别遗漏/补造、实际数字/比例/日期/否定改变仍拒绝且下游0；没有通过交换多个真实数字、修改UAT原问题或gold取得通过。此处只同步设计依据和反例验证方式，原10例及逐项判据不变，不增加付费额度或新批次。设计/实施及完整验证状态归P3 §20.30/20.31，run-06结果与未测量风险不变；不把新Guard的fake成功冒充KB-002真实通过。

### 14.18 独立七例验证及历史成功证据受限复用

本节依据用户精确批准和P3 §20.33，取代先前禁止新批的当前执行状态，不修改任何旧批终态。新入口版本7仅治理测试运行，不升级Rewrite6、Summary5、quality-v2或生产合同。本协议已完成三轮内审及分离编辑阶段的只读设计评审，允许非live实施；付费执行仍须本节全部冻结和验证前置满足，不能以文档批准代替实际预检。

1. 固定本批7例：原10例后七项KB-002、003、005、006、015b、016、008，顺序、问题、预期域、原文gold和判据逐字不变。KB-001/015a/004引用run-06通过记录，其余失败及未执行不删、不改判。只有七例本批全部通过、复用前提成立和安全/回归/评审通过，才可形成“原10例均有有效证据”的联合验收；不称为本批执行10例或新版本同批10/10。
2. run-06复用证据绑定其frozen HEAD及result SHA-256 `20254e46db4c86d6b666b365ec0ecfdf6d260947ebe36288bb71b6440dc14897`，三项原记录必须passed。§14.17 Guard修复的限定兼容依据见P3 §20.32；只批准在该精确切片无其他生产变化下复用，不推断任意未来版本兼容。
3. 新manifest Schema7保留既有字段并增加`reusedEvidence`：源run/HEAD/result hash、三项case ID及兼容规则版本。必须绑定六批全部原始hash/调用账、当前clean HEAD和源/可执行资产、新7例、完整原gold、单批/累计预算、任务/Prompt、quality及配置/索引快照。拒绝未知字段、重复JSON key、非有限数、错类型、重复/额外/缺失case、错误次序、旧限额及已有终态资产；整数不得接受bool或小数等值代换。
4. 复用校验必须比较当前manifest与run-06的environment/indexBinding/taskVersions/promptHashes/gold/evaluation、可执行资产和所有生产/服务/安全配置源。只允许DR-KFLOW-023批准的bootstrap、semantic_planner、新tax_question_semantics三文件差异，并要求其等于已审提交`550b012ad390463816372054d1c87f5877209f40`版本。其他差异、原hash错误或运行时alias/UUID变化均在新模型outbound前失败关闭；不能通过更新历史hash或忽略漂移使复用生效。
5. 累计最大21 E2E/60模型/80search/40embedding/40rerank；本批7/21/28/14/14。模型包含selection、Rewrite、Summary所有HTTP尝试，复用历史调用只计旧账一次。单case3模型/4search/2embedding/2rerank不变；禁Business/answer，retry/resume0。新独立CLI仅执行七例，不给生产请求传入case/gold或替换在线检索。
6. 保留原append-only evidence/result Schema及下游有限诊断，run-07 result只包含本批实际case、调用数和未执行项。三项复用由manifest/联合追踪表达，不伪造模型输出/当前调用。预算耗尽、首例或后续任一失败都停止整批，清理owned进程/client/原始日志；不自动建run-08。新增manifest和环境预检均不读取模型Key，仅execute在验证冻结后允许读取。
7. non-live必须验证七例顺序/原判据、三项复用来源和漂移拒绝、累计21/60硬上限、重复消费拒绝、旧模块绑定恢复、Prompt/任务一致、其他endpoint零调用及失败停止。执行前完成当前生产根回归、历史hash与无模型Spring/auth烟测；真实安全及效果分别报告。若复用前提失效或本批失败，整体专项保持未完成，不把既有35/37功能追踪当作本专项通过。

### 14.19 run-07唯一终态及联合追踪

2026-09-07执行`knowledge-stage-b-uat-v7-20260907-run-07`，冻结和六项SHA见P3 §20.34及`tests/system_e2e/knowledge_stage_b_run_07/`。本节取代§14.18的待执行状态，不覆盖协议或旧失败。复用的代码/配置/任务/索引/可执行资产前提已通过，但本批首例失败，因此未形成原10例联合验收通过。

| Case | 证据来源 | 最终状态 | 模型/search/embedding/rerank |
|---|---|---|---|
| UAT-KB-001 | run-06成功，受限兼容复用 | Passed，仅原运行证据 | 本批0/0/0/0 |
| UAT-KB-015a | 同上 | Passed，仅原运行证据 | 本批0/0/0/0 |
| UAT-KB-004 | 同上 | Passed，仅原运行证据 | 本批0/0/0/0 |
| UAT-KB-002 | run-07首例 | Failed：只选law；只覆盖law_rate，缺lodging/law_effective | 3/2/1/1 |
| UAT-KB-003 | run-07 | Not executed，首例失败停止 | 0/0/0/0 |
| UAT-KB-005 | run-07 | Not executed，同上 | 0/0/0/0 |
| UAT-KB-006 | run-07 | Not executed，同上 | 0/0/0/0 |
| UAT-KB-015b | run-07 | Not executed，同上 | 0/0/0/0 |
| UAT-KB-016 | run-07 | Not executed，同上 | 0/0/0/0 |
| UAT-KB-008 | run-07 | Not executed，同上 | 0/0/0/0 |

本批1 E2E/3模型/2search/1embedding/1rerank；累计15/37/23/12/12，未超修订上限21/60/80/40/40。Business/answer/retry/resume0，任务及quality绑定有效；model/provider与全部下游均成功，不代表所需证明完整。law_effective已在向量12位、最终重排15位，但没有进入8条Evidence；lodging所属policy根本未选。该逐阶段有限证据支持规划和Evidence覆盖缺口，不支持“知识库不存在相关资料”或“本次服务超时”。不保存或重建模型原响应/最终原文答案。

安全与owned资源清理通过；本批result=failed、Functional专项Failed，完整Effectiveness未测完，不宣布effective或partially_effective，不把当前HTTP200当作UAT通过。既有37项Knowledge、35项Business功能追踪和历史P5结论不变。本批已终止，不补跑、不续跑、不自动run-08；下一步先按P3的非live设计诊断建议处理必要证据责任，不能通过变更gold、放宽validator、无条件双域或扩大topK改判本次结果。

### 14.20 来源对应校验的非live证据边界

§14.1的必要原文必须是最终quote**实际引用**的来源，不能仅因该原文存在于Summary输入且包含相同句子就判为通过。P3 §20.35记录冻结评分器的合成错源反例，以及新增`stage-b-citation-binding-v1`校验器和生产对象图fake验证。新校验使用当前请求已验证bundle、实际政策过滤后的Summary输入和公开citation，核对引用ID对应的片段标识、内容hash及连续引文；不根据quote反建引用，不把gold送入在线链路，不调整原case/gold或通过阈值。

本工具只提供来源对应和必要条款的有限检查，不代替域/任务/调用预算/安全/usefulness评分，尚未接入任何真实执行器，也不授权新的模型调用。历史结果不含重新验证所需的完整引用对应信息，因此不重放、不重新评分、不宣称历史结果均已通过新检查；既有通过记录只保留原证明范围，run-07失败及六项未执行保持不变。后续若采用该校验，须显式绑定新版本化执行合同，不能复用已消费的run-07。当前专项仍未完成。

### 14.21 必要证据合同增量验收（non-live已验证，真实专项未执行）

新设计依据KQ-AD-018、DR-KFLOW-024、DR-KRET-029、DR-KEV-029/030。当前生产已绑定Rewrite7/Summary6/quality-v3，完整对象图fake及Spring non-live证据见P3 §20.40；旧37项功能、35项Business、原10例及全部gold保留，不把旧通过迁移成新版效果通过。本节没有新run/manifest或执行授权。

| 风险 | non-live验收要求 | 真实效果要求 |
|---|---|---|
| 遗漏分类/规则/时效 | applicability缺任一角色拒绝且search0；lookup不被强制三角色；需求域精确等于查询域 | 维持原问题/原gold，人工检查模型类型与必要域是否正确，不能按模型自报需求删减gold |
| 同域多项证明被前8截掉 | 匿名合成同域规则与时效在各需求重排首位时均保留；未知标签/预算不足失败关闭 | 在同一索引快照比较必要原文召回→融合→需求重排→Evidence位置；不调gold和阈值 |
| 合法单引用冒充完整证明 | 缺coverage/漏ID/错域/point未用拒绝；一条quote确能覆盖多项时允许复用同一point | 引用必须实际证明全部原问题要求；本地齐全检查不替代人工蕴含和usefulness |
| 错源评分 | 按L2_01_02 §9.5新增来源绑定v2的Schema2适配，复用v1来源算法但不修改v1；fake验证实际policy输入和错源反例，gold仅在结果后评分 | 新执行器必须冻结适配及算法版本；历史不重评分，不把v1直接用于Schema2 |
| 调用/数据预算 | ≤2域、4search、2embedding、4rerank/160评分、3外部模型任务；8Evidence/32KiB含需求、5points/512quote，20秒检索deadline不变 | 未来独立预算须明确新本地重排上限，不改已消费批次旧≤2rerank合同 |
| 安全/兼容 | 敏感focus/非法计划零检索，读取拒绝BGE0，出域拒绝Summary0；无fallback；旧任务输入字节不变 | 权限/策略/索引不扩张，拒绝与技术失败不伪装无结果 |

必须保留与酒店无关的lookup、单域多需求、真正双域、缺少用户条件、明确期间/否定、同文不同片段、出域收紧及取消用例。模型若将适用判断误报为lookup或用不蕴含需求的quote填满coverage，机械验证可能通过，语义UAT仍须失败，不允许把新Schema作为自我评分器。新任务最大输出tokens变化须进入未来费用快照，不能因模型HTTP次数不变宣称费用完全不变。

新任务/质量策略会使§14.18/14.19三项旧成功证据的同版本复用前提不再成立；仍保留其历史Passed，但新版本不能自动按“三旧+七新”合算通过。新的真实验证如获授权，需对原十例重新作版本影响覆盖安排，不能据此删例、改gold或自动创建批次。

本增量设计/代码/non-live评审通过只允许继续安全实施与测试。真实专项仍Deferred、最新run-07仍Failed且其他六项未执行；没有读取Key、启动服务、调用模型/ES/BGE或新增候选的动作。剩余总预算不等于新批次授权，后续真实执行必须另有明确的未消费绑定与停止规则。

### 14.22 原十例新版完整验证协议

2026-09-07用户明确批准准备、冻结并执行一次run-08。本节仅更新执行合同，继承§14.21及L2_01_02 §9.5来源对应/语义判据，不调整生产实现或原问题/gold。旧三例不复用为新版通过；历史所有终态不变。

1. 唯一新run为`knowledge-stage-b-uat-v8-20260907-run-08`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-08`。原`knowledge_stage_b_cases.py`十例按原顺序完整执行，首个失败停止；不补跑、续跑或自动run-09。
2. 本批上限E2E/model/search/embedding/rerank=10/30/40/20/40，累计上限25/67/80/40/52；历史实际15/37/23/12/12逐文件校验后计账。单case最多3/4/2/4次对应模型/检索/embedding/rerank；Business、answer、retry、resume均0。两澄清、八完整成功预计28模型，只是预算推导，实际按HTTP尝试记录。
3. 新Schema8 manifest绑定clean HEAD、原十例及gold、七批hash/计数、所有目标源码/测试、Java可执行资产、配置/索引binding、任务selection-v4/Rewrite7/Summary6、Prompt hash、输出tokens512/1536/1536、quality-v3和citation-binding-v2。禁`reusedEvidence`。原始manifest独占创建；运行前验证完整资产集合而非只验证剩余条目，拒绝未知/重复key、bool/float冒充整数、删减资产/用例及任何漂移。
4. prepare/check-environment不读Key；非live与代码复核通过后，冻结manifest并独占生成authorization.json，绑定HEAD/run/reference/manifest SHA/dataset SHA/本批及累计预算/live=true。仅execute在校验后读进程Key。准备目录位于target；所有预检均精确检查目录允许文件，不以Git忽略状态放过重跑。已有evidence/journal/consumed/result拒绝执行。一次性本地启动和readiness不产生模型调用，不改变alias。
5. 复用既有Spring→当前生产Runtime、真实auth与typed Knowledge生命周期，不复制在线流程。测试进程在同请求内只读捕获已验证bundle及实际policy过滤后的`KnowledgeRequirementSummaryInput`，序列化必须等于实际Summary HTTP输入；不保存正文/需求focus/响应。结果后调用来源绑定v2，并同时验证原域/原gold、原有限reason、任务序列、quality与调用数。wrong-citation不得用池中其他相同quote补证；结构coverage不能替代原文语义/usefulness。
6. consumed在首次模型HTTP尝试前独占写入；每次模型调用先同步journal，硬预算在发送前检查。失败停整批，保留有限result/evidence/未执行清单。证据只保存case ID、状态/reason枚举、任务/版本、调用计数、源hash/排名、来源绑定及逐gold布尔值；禁问题、focus、quote、原始响应、JWT/Key。HTTP状态不能代替验收结论。只终止本次Popen对象对应进程并确认退出，关闭client，扫描删除临时原始日志。
7. fake覆盖新输入实际绑定、错源、旧Schema拒绝、全部十例顺序、原判据、不复用旧成功、累计预算、每case第5次rerank拒绝、任务/Prompt/tokens漂移、重复消费、目录/资产漂移和退出恢复。真实前冻结测试结果及绑定；真实失败后仅分析/non-live，不再创建付费批次。专项全部十例、核心P0、来源/语义/安全/清理均通过才可关闭；否则如实Failed/Not executed，保留整体未完成。

### 14.23 run-08有限失败结果

唯一执行`knowledge-stage-b-uat-v8-20260907-run-08`，frozen HEAD=`1fbd62aeebc01af0951ddcd62281be589f6eba6a`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-08`。360项源码/258项可执行资产，selection-v4/Rewrite7/Summary6、quality-v3、citation-binding-v2；原十例/gold与阶段A索引快照不变。七项原始资产保存在`agent-runtime/tests/system_e2e/knowledge_stage_b_run_08/`，相对target原文件逐字复制并复核SHA，无覆盖历史。

| 资产 | SHA-256 |
|---|---|
| manifest.json | `73a7fc36587211e211dbae43006207a33e8cc2e34ce6a4d97bfad44db3f5a210` |
| authorization.json | `0c153370e01d2b9f2f9c6f93d6d3846cde17b9f6720be9f27ef300217292476e` |
| consumed.json | `970a66e09b02294dbedeefb3c50ca2ef8ba4e9f2daa4265f83be61125537ea32` |
| journal.jsonl | `a5f25a7738064498fcdf9208b3113eccdfb884aead88d5ab0984fe206f67bae9` |
| result.json | `cdef650dd3aa78247b98073770635e659bfd92403cffaa3867523feba26253c9` |
| evidence.jsonl | `f39f15495a1c0bc6557bccfe98102cc345d1238e19304836bc464fb8d29ed9cc` |
| environment.jsonl | `2d2c1e39beec6b038ef0b1b4dd727afab69fd0cf7ca44a4c8ac4fad608b9c15f` |

| case | 新版结果 | 实际模型/search/embedding/rerank | 结论依据 |
|---|---|---|---|
| UAT-KB-001 | Failed | 2/4/2/2 | 预期澄清且零检索；实际双域search，Summary在outbound前被执行器拦截，HTTP502 |
| UAT-KB-015a | Not executed | 0/0/0/0 | 首例失败停止，不复用旧版Passed |
| UAT-KB-004 | Not executed | 0/0/0/0 | 同上 |
| UAT-KB-002 | Not executed | 0/0/0/0 | 分类、规则、时效核心P0仍未被新版本验证 |
| UAT-KB-003 | Not executed | 0/0/0/0 | 首例失败停止 |
| UAT-KB-005 | Not executed | 0/0/0/0 | 首例失败停止 |
| UAT-KB-006 | Not executed | 0/0/0/0 | 首例失败停止 |
| UAT-KB-015b | Not executed | 0/0/0/0 | 首例失败停止 |
| UAT-KB-016 | Not executed | 0/0/0/0 | 首例失败停止 |
| UAT-KB-008 | Not executed | 0/0/0/0 | 首例失败停止 |

真实调用共1 E2E、2外部模型、4search、2embedding、2rerank；没有Summary HTTP尝试，Business/answer/retry/resume0。累计16/39/27/14/14，未超本次授权；授权已消费且停止，不自动run-09。source绑定和语义/usefulness仅在有最终引文时才有证明价值，本批无引文，不能把澄清分支默认citationBindingValid=true解释为引用通过。

功能结论：原37功能追踪保留其既有non-live证据；阶段B专项Failed。效果结论：本批未形成完整效果测量，九例和Summary6真实效果尚未验证；不得称为effective或将旧成功自动迁移。安全/运行约束：未超预算、禁止动作0、owned进程退出/client关闭、日志扫描清理通过；但缺条件case零检索这一功能断言失败。P3 §20.43治理工作包和缺口，历史P5 candidate与阶段A终态不变。

### 14.24 澄清规则恢复与向量结构诊断的证明范围

依据L2_01_00 §8.6，当前生产代码已绑定Rewrite8/Summary6/quality-v3；V8只恢复被V7遗漏的澄清优先指令，五字段decoder、原十例/gold和通过标准不变。定向fake及当前根验证通过，不代表真实模型正确选择意图；本版本真实效果仍Evidence missing。§14.23保持唯一最新执行终态，不补跑、不复用剩余预算、不新建run-09。

用户另授权政策库ES向量存储结构调整，本次只读ANN/精确检索对照及其限制见P3 §20.45。索引和alias没有变更，结构候选尚未实施或发布。这些离线排名证据不能代替Spring端到端或核心P0通过；未来方案必须保持原文/引用、共享law范围、权限及旧索引可回滚，先做有限非付费对照，不自动追加模型批次。原35/37功能追踪不回退，阶段B专项仍未完成。

### 14.25 政策向量输入对照的验收限制

全库三臂对照见P3 §20.46：对同一13,909条policy、五个公开固定问题及原人工gold，标题/现有章节/原文表示改善定义和分类边界召回，但历史税率问题必要原文仍不齐于前20。只证明离线表示的候选价值，不证明新索引ANN、读取/出域快照、当前需求排序、Summary或Spring端到端通过；不调整原case、gold或阈值。

DR-KRET-030纯构造器的测试即使通过，索引结构发布及阶段B专项仍待验证。库存向量输入/模型来源未核实时，不把全部重编码差异归因为存储损坏。未执行新模型请求，不建立run-09，§14.23失败终态及原35/37追踪保持原证明范围。用户结构授权允许继续候选方案，但不许可用局部排名替代缺条件零调用或完整适用性证明。

后续738附件限定对照保留其余基线向量和全部源记录，避免新增token截断；历史税率原文排名18、住宿定义33，其他改善与保留项见P3 §20.46。此结果支持最小候选方案而非全库重编码，仍不能关闭完整必要证据或阶段B UAT。

### 14.26 候选构建与发布准备的证据边界

P3 §20.48已记录真实b2候选构建及同窗口ANN对照：五个固定问题的必要原文均进入keyword/vector合并候选池。历史税率问题由keyword第2名提供住宿定义、vector第18名提供税率；不能把向量单路定义排名33继续解释为整个候选池缺证据。上述旧离线对照保留其当时证明范围，不改写原结果。

P3 §20.49进一步完成候选全部记录fingerprint核对、新policy/law快照和5600份文档目录的离线准备；当前Runtime严格validator已验证新旧绑定与未知快照拒绝，策略及字段上限不变。候选和新目录均未启用，现行alias、catalog resource、服务启动binding未改。没有新增模型调用、Java typed UAT、rerank/Evidence或Spring端到端结果；这些步骤仍须各自的实际证据。

因此，原35/37功能追踪保留既有证据，§14.23仍是阶段B最新真实失败终态；Rewrite8/Summary6/quality-v3在新向量候选上的完整专项UAT仍未完成。不得用离线目录校验替代读取授权或最终必要证据、引用与usefulness，也不得自动创建run-09。

### 14.27 候选真实类型化检索的有限证明

P3 §20.50记录隔离typed验证，前三次预检/环境/响应合同失败保持原始结果，第四次16/16组合通过：policy/law各自ADMIN/VIEWER的keyword/vector允许，UNKNOWN拒绝403，service/malformed/missing拒绝401且无正文。当前Java ProfileVerifier及Python strict decoder、正文hash、新旧目录策略边界、Evidence连续子串与引用唯一性实际通过；服务进程、原始日志和临时alias清理通过，线上alias及当前resource/binding未修改。

这是候选检索、授权及Evidence兼容证据，不是新增功能/效果UAT：本地embedding2次、外部模型0；选证使用v1兼容限制及合成原文引用，未执行quality-v3排序或真实Summary。真实回滚演练、线上发布和新候选上的原十例专项仍未完成。四项原始hash及调用计数由evidence/P3维护，不在此复制动态测试总数。

原35/37功能追踪保持既有证明范围；§14.23仍是阶段B最新付费执行失败终态，当前Rewrite8/Summary6整体效果仍Evidence missing。不能用16项typed允许/拒绝组合替代核心P0适用性、澄清零检索、最终必要证据覆盖或usefulness；不改变gold/阈值，不自动run-09。

### 14.28 政策向量发布后的验收边界

P3 §20.51/20.52记录候选→旧索引→候选的真实隔离回滚（三段共24项检查）及随后线上alias到b2的受控发布。发布前全记录fingerprint/mapping通过，发布后16项真实typed允许/拒绝和Evidence兼容通过；新目录、Profile快照和serviceCenter启动binding一致，旧索引、旧目录和全部历史证据保持。失败演练01因Python缺Runtime依赖停止，02及发布结果分开保存，不覆盖失败结果。

本次没有外部模型或新的效果候选。存储结构发布和读取/出域兼容已经验证，但使用v1兼容选证和合成原文引用的检查不证明quality-v3需求排序、Rewrite8澄清或Summary6语义覆盖。原十例阶段B专项仍按§14.23 Failed/Not executed记录，未改变gold、阈值和通过条件；原35/37功能追踪保留其既有证据，不声称重新执行了真实功能UAT。

当前生产读取目标和精确证据归P3/evidence维护，本计划不重复记录运行hash和动态测试总数。后续验证必须绑定新索引及当前任务版本；不复用已消费run-08或自动创建付费run-09。阶段B尚未全部完成。

### 14.29 新快照排序诊断与启动预热的证明边界

P3 §20.53记录当前quality-v3真实本地诊断：首个手工计划的两路候选返回并融合，但首个rerank超时，后续停止；没有新Rewrite/Summary或付费模型调用，不改写§14.23正式UAT终态。独立合成冷实例复现health正常后的首次推理超过在线时限，支持DR-KRET-033启动期单次预热；它不扩大在线deadline、检索窗口或任何验收阈值。

合成预热属于启动前置，不是UAT case，不证明原问题意图、原文相关性、必要证据、引用或usefulness；新执行入口必须单列本地启动调用预算，不能注入历史冻结runner或借此恢复失败批次。当前原十例新版专项仍未完成，原35/37功能追踪维持其既有证据范围；不创建run-09，不将本地环境修复冒充效果达标。

### 14.30 当前排序/Evidence独立本地测量

P3 §20.54记录预热修复后基于当前b2和quality-v3的八个固定手工计划测量；没有模型Rewrite、Summary或新付费UAT。015a、004、002、015b、016、008保留原定全部来源；003的rent、006的historical_rate已被召回，但经需求重排和最终窗口后丢失。两者必须继续记为必要来源覆盖缺口，不因Selector结构sufficient、policy允许或其余六例保留而改判。只读tokenizer检查已排除这两份短条款的512 token截断；上下文表示是否改善尚待独立比较，不能据此直接修改在线算法。

该诊断不改变原十例/gold、001/005澄清预期、§14.23正式失败结果和原35/37追踪。正式当前版本专项仍未完成；本地测量只缩小根因范围，不证明LLM意图、最终引文或usefulness。具体调用数、原始hash、验证命令及后续工作归P3/evidence；不恢复旧批次或自动创建run-09。

### 14.31 授权上下文评分表示的验收边界（v1.33）

P3 §20.55的固定八例配对采用相同候选/查询/模型/窗口，正文对照与授权元数据表示各一次评分；后者经现有ranker/Selector/policy实际保留8/8预定原文，003 rent进入Evidence2、006 historical_rate进入Evidence6，原六例无回退。该局部证据支持L2_01_01 DR-KRET-034，但不是原十例端到端UAT通过，也没有测量当前Rewrite8/Summary6或人工usefulness。

新生产表示为`authorized-body-first-metadata-v1`；后续正式运行快照必须同时冻结表示版本、源码、当前任务与b2/policy快照。non-live验证必须证明单需求仅一次BGE、没有实验raw+context双调用、原文/引用不被派生文本替换、默认disabled及错误失败关闭不回退。新旧版本不得混称同一效果测量；§14.23正式失败、历史资产和原case/gold不变。该验收补充不新增付费额度或运行许可；新线上实现通过后仍须完成原澄清、模型规划、Summary引用及usefulness责任。

上述生产绑定、严格HTTP反证、当前完整对象图及Spring→Runtime non-live验证现已通过，实际命令和结果见P3 §20.55；不是待实施设计，也不是完整真实UAT。原35/37追踪及历史效果结论保留原证明范围，当前Rewrite8/Summary6完整专项仍未完成。没有新付费请求、run-09或旧运行续跑。

### 14.32 当前生产版本的独立十例执行协议（v1.34）

2026-09-08用户明确批准上一轮提出的独立完整十例及预算。只授权`knowledge-stage-b-uat-v9-20260908-run-09`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-09`；不恢复run-08，不自动run-10。§14.22～14.31禁止自动新批次的历史叙述保持当时范围，本节是这一次执行的新依据。

1. **范围及预算**：原`knowledge_stage_b_cases.py`十例、顺序、人工gold及来源绑定v2通过标准均不变。两例澄清必须2次模型且零检索；其余八例最多3次模型、4search、2embedding、4rerank。整批E2E/model/search/embedding/在线rerank上限10/28/32/16/32；另允许一次启动合成rerank，单列上限1，实际本地rerank合计最多33。逐文件核对前八批累计16/39/27/14/14；累计上限26/67/80/40/52（含本次启动rerank）。不把此前非UAT本地诊断混入正式预算，不隐藏其既有记录。Business、answer、retry、resume均0。
2. **冻结**：新Schema9 manifest独占创建，冻结clean HEAD、原dataset、全部源码/测试与Java可执行资产、八批hash/计数、当前v2 runtime binding/b2索引UUID/alias/mapping/policy/law快照、catalog、BGE容器/镜像身份、selection-v4/Rewrite8/Summary6及Prompt/tokens、quality-v3、citation-binding-v2、`authorized-body-first-metadata-v1`和预热源码。重新枚举全资产集比较，禁止删项、未知/重复key和整数类型漂移；保留历史v1文件真实hash但不得把它当作本次服务配置。
3. **最小测试接缝**：新增版本化runner及直接fake测试，复用既有Spring→当前main、真实auth、owned服务和有限结果生命周期。只在新测试上下文把历史服务helper的固定binding读取重定向到已存在的v2文件，其他路径不变，退出必恢复；不改历史文件、生产src、公开DTO或ES。新只读观察器跟踪当前ContextualBgeRerankAdapter，原方法只调用一次；不执行raw/context双臂，也不将gold输入在线处理。
4. **环境前置**：prepare不读取Key。check-environment独占生成startup及environment有限资产；按现有合成工具只预热一次，失败停止，不重试。核对模型身份、只读索引绑定及health，然后真实auth+Spring+stub冒烟，模型/Knowledge调用0。执行前必须验证该次预热成功、client关闭、environment四项通过、索引/模型身份未变；执行过程中不再预热。预热尝试计数先落盘，进程中断不能获得第二次尝试。
5. **授权及消费**：仅生成精确HEAD/run/reference/manifest SHA/dataset/预算/live绑定的authorization；运行目录仅允许manifest/startup/environment/authorization规定文件。已有consumed/journal/evidence/result或失败startup禁止执行。首次模型HTTP前独占consumed、每次HTTP前fsync journal并检查任务/Prompt/输入/预算，付费请求只在execute读取进程Key后发生。失败停止整批，不补跑任何case；保留有限失败及未执行清单。未到模型即失败也不自动重用该批。
6. **证据与判定**：复用实际bundle及policy过滤后的Summary input捕获和来源绑定v2，仍核对原域、澄清、必要原文、引用及语义/usefulness，不以HTTP200、结构coverage或手工计划8/8代替。仅记录caseID、有限状态/reason、任务/版本、调用数、来源hash/排名和布尔判据；禁止问题、focus、quote、元数据正文、原始模型/业务响应、Key/JWT。前后只读索引/模型校验、owned PID退出及原始日志扫描删除必须通过。
7. **准入与关闭**：三轮内审、分离的正式只读设计复评通过后实施runner；fake覆盖预算、完整资产/历史/当前绑定、旧observer不可冒充、预热失败/重复、模型漂移、重复消费、错源、十例顺序和patch恢复。代码复核及non-live通过后提交、冻结再执行。十例、核心P0、来源/语义、安全及清理实际通过才关闭专项；首个失败则Failed，其余Not executed，阶段B保持未完成。原35/37功能证据与历史效果等级不被本协议改判。

### 14.33 run-09实际终态与未完成责任

§14.32的一次性授权已经执行并消费，run-09为本阶段最新真实执行，终态Failed。精确冻结、八项原始资产及SHA由evidence/P3 §20.56.2维护；本文只记录用例、效果结论和证明范围。既有run-01～08及P5 candidate结论不变，不续跑、不自动run-10。

| 原用例 | 本批状态 | model/search/embedding/在线rerank | 实际证据或未执行原因 |
|---|---|---|---|
| UAT-KB-001 | Passed | 2/0/0/0 | 当前Rewrite8正确澄清；HTTP200/no_result/clarification_required，零检索。 |
| UAT-KB-015a | Failed | 2/0/0/0 | Rewrite8 invalid_output；HTTP502/downstream_failure，未产生检索、Summary或有效引用。 |
| UAT-KB-004 | Not executed | 0/0/0/0 | 首个失败停止整批。 |
| UAT-KB-002 | Not executed | 0/0/0/0 | 核心分类/规则/时效仍须当前版本真实验证。 |
| UAT-KB-003 | Not executed | 0/0/0/0 | 首个失败停止，不用此前本地8/8配对冒充。 |
| UAT-KB-005 | Not executed | 0/0/0/0 | 另一澄清用例未执行，不能从001外推通过。 |
| UAT-KB-006 | Not executed | 0/0/0/0 | 首个失败停止。 |
| UAT-KB-015b | Not executed | 0/0/0/0 | 首个失败停止。 |
| UAT-KB-016 | Not executed | 0/0/0/0 | 首个失败停止。 |
| UAT-KB-008 | Not executed | 0/0/0/0 | 首个失败停止。 |

本批2次E2E、4次付费模型；另有一次独立启动合成rerank，不属于上述case或效果证据。Summary、Business、answer、retry、resume为0；调用未超预算。前后绑定、进程/client关闭、日志扫描清理通过，没有任何索引或alias修改。

模型原始响应按安全合同未保存；invalid_output不能确定具体字段、provider响应或finish原因。015a未生成实际Summary输入，input_binding_missing和必要原文false是上游停止的后果，不能推断新向量索引、排序或引文校验已失败。非live合成lookup计划通过严格解析，其他非法形状均拒绝；fake只验证合同，不补齐真实用例。

验收结论：原35/37功能证据保持其既有证明范围；阶段B专项Failed，当前Rewrite8仅001获得本批通过证据，Summary6及完整原十例效果仍Evidence missing，不能宣称effective或阶段B完成。诊断/工作包状态见P3；历史章节中的“未创建run-09”保留当时语境，本节是最新执行权威。后续只能先做有依据的非付费诊断，不把剩余额度视作新批次授权。

### 14.34 持续授权下的单次Rewrite诊断

2026-09-09用户明确授权完成目标所需权限、后续无需逐项请求。本节替代§14.33仅允许非付费工作的后续限制，不改变run-09及此前结果、预算、终态或重用禁令。持续授权不表示无限循环：先执行独立`knowledge-rewrite-diagnostic-v1-20260909-01`，reference=`UAT_01:14.34`，只有原UAT-KB-015a的安全公开问题、当前Rewrite8和既有ModelGateway/DeepSeek transport；最多1次模型HTTP，selection/Summary/ES/embedding/rerank/Business/answer/E2E/retry/resume全0。诊断不是正式UAT、不能关闭原十例。

执行前提交并冻结clean HEAD、Runtime源码及直接测试工具hash、原case文件、任务/Prompt/输入hash、模型及预算；manifest不得包含Key。独占目录、consumed及journal在HTTP尝试前持久化；同目录失败或成功都不能重入。Key仅execute读取进程变量，原问题先经QuestionEgressGuard；调用只用原模型/端点/1536tokens/8秒，不修改当前生产decoder或请求。原输出仅驻留内存，成功只记录有限outcome及数量，失败只记录phase/code/cause及throwSite枚举。

throwSite仅允许当前冻结parser/validator的已知代码对象及静态行号映射到固定枚举，用于区分字段形状、枚举、ID/域关系、角色完整性；不读取frame locals/globals、异常消息/args、源文件路径、模型JSON或正文，不重新解析或放宽响应。未知位置统一unknown，最多8层cause/32帧，无任意类名/路径输出。离开作用域恢复原观察hook，关闭client；错误分类不得改变原ModelTaskResult。直接fake必须覆盖恶意异常、未知位置、零网络/重复执行拒绝、HTTP次数、超时/取消及清理。

三轮内审已分别完成：①只诊断不执行后续检索、不把合成或单任务成功当E2E；②复用原parser只旁观固定异常位置、禁止原文和任意traceback输出；③固定1次请求、独占持久化及无重试、失败后先分析和fake。分离编辑后的设计对照复评基于L2_01_00 §8.5/8.6/10.1及现行Gateway错误合同：本诊断接缝可实施，S0/S1/未处理S2为0；不是外部独立人员批准或阶段B通过。无需修改生产L2合同或新增门禁。

诊断后仅按已确认原因作最小修复，设计语义变化先修订并完成原评审流程。恢复正式专项前重新固定当前版本、原用例/gold/快照与调用预算，并核算本次新增诊断；沿用本次持续授权，不再要求用户逐批重复批准，但执行器必须有有界预算且每个批次只执行一次。失败停止后不得机械补跑，必须有改变下一行动的根因及修复证据；不放宽字段、权限、引用或原验收标准。

### 14.35 单任务测量后的完整链路验证

§14.34一次真实Rewrite8成功（search、1查询、1要求，模型1，其余0），原始响应未保存。它没有重现run-09失败，也不能证明其原因已经修复或完整UAT通过。故不猜测性修改Prompt、parser、索引或验收断言；下一行动改变为在完整当前对象图中接入已通过fake的有限错误观察，失败时能确定阶段/固定抛出位置，而不是继续得到没有诊断价值的通用invalid_output。

基于本次持续授权，固定独立`knowledge-stage-b-uat-v10-20260909-run-10`、reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-10`。只执行一次原十例，顺序、gold、来源绑定v2及通过条件完全沿用§14.32。当前Rewrite8/Summary6/quality-v3/context和b2不变；上限E2E/model/search/embedding/在线rerank=10/28/32/16/32，启动合成rerank另1。前九批累计18/43/27/14/15，合并上限28/71/59/30/48（rerank含启动）；独立诊断1次模型另列，因此包括该诊断的模型历史合计上限72。Business/answer/retry/resume=0。此协议不是恢复任何旧运行或授权无限追加候选。

复用版本化v9的独占prepare→单次warmup/environment→authorize→execute、源码/可执行资产/索引/模型前后绑定、真实auth/Spring、日志扫描及owned PID退出。不复制生产流程、不改公共Schema。新manifest记录全部九批历史及单任务诊断hash；新错误观察仅在当前测试Runtime作用域将原异常投影为有限phase/code/cause/throwSite，附当前caseId和任务枚举，最多每case3项，原回调仍一次，取消/退出恢复；不读取任何原始模型响应、frame局部值或异常消息。其余有限result结构不变，首个失败停止整批，未执行项保持未执行。

三轮内审依次核实：①单任务成功不能填补十例缺口，旧失败不可变；②观察器不增加模型调用、不改decoder或下游路径，未知异常只记unknown；③预算/消费、原gold、服务清理和前后绑定完整，不增加Gate/设计版本或重复全量平台。与编辑分离的正式只读复核按照L2既有错误边界、§14.32及上述有限观察合同通过，S0/S1/未处理S2=0；这是同一执行者分阶段审查，不声称外部独立人员批准。只允许新runner/直接fake/有限证据实施，生产代码不因单次成功作无依据改动。正式十例及核心P0通过前，阶段B保持未完成。

### 14.36 Java启动环境纠正，不重用失败预检

run-10预检完成一次本地rerank预热后，三个隔离Java服务均报UnsupportedClassVersionError；当前PATH为Java8而class/JAR为Java25。无模型Key读取、无付费请求、无UAT case、无业务检索；owned进程及原始日志已清理。保留原manifest/startup/environment，不为未执行批次伪造consumed或result，也不在该目录重试。

相同持续授权下新`knowledge-stage-b-uat-v11-20260909-run-11`、reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-11`只修复测试子进程Java选择：固定已安装JDK25、先验证major版本和PATH解析，再执行任何预热/服务启动；将java.exe SHA及版本加入manifest，每次前置及末尾验证一致。只修改子进程环境，退出恢复，不改全局变量、不安装依赖、不改变生产或历史runner。其余沿用§14.35原十例及10/28/32/16/32+启动1预算，模型累计上限仍71（独立诊断另1），本地rerank累计上限49，新增1是run-10已发生预热而非遗漏调用。

三轮聚焦内审分别核查环境因果、预热前版本失败关闭、旧目录不重用及累计计数；分离编辑后的只读设计复核确认这是现有启动合同实现缺陷而非检索/公共接口设计变化，S0/S1/未处理S2=0。新增薄启动器和direct fake后方可提交冻结执行；不再重复上位设计改版或建立新Gate，不把环境修复当UAT通过。

### 14.37 完整链路中的摘要遗漏与最小修订

run-11按§14.36一次执行，终态Failed/consumed；001通过澄清（model2，其余0），015a失败（model3/search2/embedding1/在线rerank1）。015a的动作选择、Rewrite8、Summary6均成功，返回HTTP200/1point，但只引用下位定义，未引用问题明确要求的上位分类关系。必要的两份原文均在实际授权Summary输入内（最终Evidence第1和第4位），有限判据为lodging=true、living=false、required_source_not_cited；不能据此归因为语料或召回缺失，也不能把HTTP200当通过。004、002、003、005、006、015b、016、008均Not executed，首个失败后停止。

实际E2E/model/search/embedding/在线rerank=2/5/2/1/1；另启动rerank1，Business/answer/retry/resume=0。前后索引/模型身份、owned服务关闭及原始日志删除通过。八个原始文件逐字节归档于`tests/system_e2e/knowledge_stage_b_run_11/`，绑定与hash见P3/evidence；禁止复用。此前十批、单次Rewrite诊断及既有功能35/37证据结论不变。

只新增Summary7通用指令，要求定义与问题显式分类关系都由实际quote支持，一个requirement可引用多点，但一段已充分时不强求多ref；当前先按L2_01_02 §9.6和L2_01_00 §8.7完成设计复核再实施。Rewrite8、输入输出合同、decoder、validator、索引、排序及原十例gold保持不变。先定向/fake、当前根/Spring和全量验证及代码复评，随后依据持续授权冻结新版本的有界完整专项。已结束批次不重用；测试通过不代表真实效果达标，当前专项仍未完成。

### 14.38 Summary7修订后的有界专项

在§14.34持续授权内，新`knowledge-stage-b-uat-v12-20260909-run-12`，reference=`P3_00:WP-KRETRIEVAL-UAT-01/run-12`，只验证已修订的Summary7，不恢复run-11。原十例/顺序/gold/来源判据不变，Rewrite8/quality-v3、b2和本地模型绑定不变；单批E2E/model/search/embedding/在线rerank上限仍10/28/32/16/32，启动rerank单列1。前序正式已用20/48/29/15/18（最后一项含三次启动），本批后累计上限30/76/61/31/51；独立Rewrite诊断1次模型另列，全部模型合计上限77。Business/answer/retry/resume=0，首个失败停止，其余未执行。

版本化薄runner复用v11的JDK预检、服务、消费、有限观察、原判据及清理，仅替换当前任务/Prompt绑定并加入run-11精确历史hash和累计数。prepare/check-environment不读Key，源码/可执行资产/当前索引及任务快照完整冻结；先完成当前根7实际wire捕获、预算、旧版/未知Prompt拒绝、历史哈希和patch恢复fake，再提交冻结执行。三轮内审及与编辑分离的只读复评核对了实际摘要根因、仅任务版本改动、单批/累计预算和原失败关闭；允许该测试接缝实施，不增加Gate、不宣称阶段B已通过或外部人员评审。仍按实际结果决定专项关闭，禁止机械追加无根因的付费运行。

### 14.39 run-12终态与后置校验诊断边界

§14.38已一次执行并消费，终态Failed。001为Passed（澄清、model2、零检索）；015a为Failed（HTTP502/downstream_failure、model3/search4/embedding1/在线rerank2），其余原八例Not executed。三项模型任务均成功解码，但未返回有效points；必要上下位原文仍在实际Summary输入中（第1/7位）。本次计划选择tax.policy和tax.law，与仅问政策分类的预期不符；这是已观察到的域语义偏差，不表示由失败触发fallback。不能据模型任务成功就认为后置覆盖、引用或原文校验已通过。

本批E2E/model/search/embedding/在线rerank为2/5/4/1/2，启动rerank另1；累计正式22/53/33/16/21（含四次启动rerank），独立Rewrite诊断model1另列，全部已知模型54。预算未超；前后绑定、owned进程/client退出和原始日志扫描删除均通过。八个原始资产逐字节归档于`tests/system_e2e/knowledge_stage_b_run_12/`，完整hash由历史校验测试维护。禁止重用本批；未准备run-13。

现有有限结果没有保留生产Evidence后置校验的拒绝枚举，citation_invalid是无有效points时的验收结论，不能反推出真实quote、coverage域关系、重复引用或子串的哪一项错误。模型原始响应按合同销毁，不能恢复或补造旧运行诊断。先在test-only新增纯函数有限投影并用合成数据验证：只接受精确InvalidSummary类型、已定义reason枚举、当前两个validator代码对象和预先审定的静态抛出分支；最多检查32个frame的代码身份/行号，输出有限phase/reason/branch，绝不读取locals/globals、异常消息、任意路径、模型文本或quote。未知类型全部unknown；未知位置的phase/branch为unknown，只保留已核实的reason枚举。不重新解析或再次调用validator，无IO、Key、网络、全局hook或生产注册。

聚焦三轮内审分别核实：①旧终态及诊断不确定性，不能伪造旧原因；②精确类型/固定枚举/零原文及原validator不变；③纯函数无资源副作用、合成反证和历史hash，不新增Gate或付费批次。与编辑分离的只读设计复核对照L2现有失败关闭与有限证据边界，通过该non-live工具切片，S0/S1/未处理S2=0；同一执行者分阶段复核，不声称外部独立人员审查。当前不猜测性增加Rewrite9/Summary8、不修改索引或gold；该工具不接线执行新真实批次，也不能关闭专项。后续真实诊断须先明确最小场景、只读观察接线和有限预算，并在现有持续授权下重新冻结；不得自动补跑本批。

### 14.40 检索准确性优先的分层专项验收

用户2026-09-09明确整体召回准确率优先，资料录入问题不要求住宿费单题一定通过。本节取代原“所有历史固定来源/摘要判据共同充当唯一质量门槛”的后续执行方式，但不覆盖任何历史case、gold或失败结论，也不允许把已存在但漏召回的资料称为未录入。

| 维度 | 判定依据 | 当前证据限制 |
|---|---|---|
| 语料 | 人工核实present/missing/unknown及必要原文；不足保留清单和数量 | 来源不可达不等于正文缺失；不得删除难题隐藏分母 |
| 检索主目标 | 同语料/问题集的Recall@k、MRR、Evidence覆盖；完整人工分级时P@k/nDCG | 八个旧手工计划仅局部证据，不证明真实Rewrite或整体准确率 |
| 运行与安全 | 授权、出域、引用、有限调用、失败类型、零越权 | 502不能计为正常无结果，也不能自动把已召回的资料指标归零 |
| 回答质量 | 正文支持、无编造、覆盖和有引用；与检索分列 | 不要求资料缺失单题肯定回答；当前摘要失败仍记录并修复 |

采用L2_01_02 §13.8指标合同。先新增零I/O计分工具并对既有有限证据只读复算；保留原chunk/sha判据作为固定来源回归，不把新指标解释为原run通过。只有预先人工确认的等价来源才能加入新标注，不能从答案或模型自评生成gold。缺少完整相关性标注时P@k/nDCG为null，不能从必要条款覆盖率推导准确率。

后续代表集目标为20～30个问题，包含政策定义/法条/文号、期间、同义表达、单/多域、非住宿保留题及真实语料缺口；至少三分之一为不参与调参的留出题。问题、原文、标注、分组、旧/新配置/索引和通过标准在新测量前冻结。指标及各组不得出现未解释回退；具体数值阈值在基线核实后、优化前写明。本节不宣布该问题集已准备或已执行。

本次只改内部拒绝原因及测试投影、指标；不读取Key、不创建run-13、不重跑历史。未来真实执行仍先完成有效观察、case与实际剩余预算核算；不得以新增计分工具自动获得另一整批付费额度，也不得用新算法给旧run补造缺失的后置原因。§14.39的行号探针由稳定枚举投影替代，源历史仍可从当时Git读取。

冻结兼容补充：L2_01_02 v1.24将新覆盖原因放在requirement_validation.py的独立枚举/兼容异常子类中，旧summary_validation.py、原十种枚举及历史哈希断言不变；投影只接受两个明确的异常类型。新诊断不会改变旧运行的失败分类，也不新增公共输出字段。

本次`test_historical_retrieval_separation.py`只读核对哈希后完成分层复算，结论如下；这不是新的真实UAT，也不是对原失败重新判定：

| 既有有限证据 | 可证明的检索结果 | 必须保留的限制/原结论 |
|---|---|---|
| run-11 / UAT-KB-015a | 必要两来源位于Evidence第1/4位，Recall@20=1、MRR=1、Evidence coverage=1 | 原Failed：HTTP200但遗漏必要分类引用；检索到不等于回答充分 |
| run-12 / UAT-KB-015a | 必要两来源位于Evidence第1/7位，Recall@20=1、MRR=1、Evidence coverage=1 | 原Failed：HTTP502；实际后置拒绝原因未保存，另有已观察到的多选域偏差 |
| 既有quality-v3-context八题手工计划probe | 每题必要来源Recall@20和Evidence coverage均为1 | 非真实Rewrite、无Summary、非功能/效果UAT；不得当作整体准确率 |

三组均没有完整人工相关性分级，Precision@20/nDCG@20为null，不得以必要来源命中推导精确率。原文件SHA、字节、Failed和未执行状态保持不变；测试结果及命令由P3最终验证记录治理。本轮新增模型/真实检索调用均为0；代表集与留出集整体测量仍未完成。
