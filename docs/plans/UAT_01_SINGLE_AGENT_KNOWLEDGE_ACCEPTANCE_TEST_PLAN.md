# [UAT_01] 单体 Agent Knowledge 查询验收测试计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `UAT_01` |
| 当前版本 | v1.22 |
| 文档状态 | Reviewed |
| 日期 | 2026-09-04 |
| 适用范围 | `knowledge.query` 的生产接线、功能/效果验收，以及 Knowledge 阶段 A 语料完整性专项验收 |
| 上位依据 | `L1_00` v3.5、`L1_01` v1.17、`L2_01_00` v1.18、`L2_01_01` v2.7、`L2_01_02` v1.18、`P3_00` v2.44；阶段 B 设计评审通过，新增运行协议评审及实施/UAT状态另记 |
| 历史边界 | candidate-01～07 的既有 manifest/authorization/consumed/journal/result/evidence/failure 均保持不可变；candidate-07 为 `failed_unconsumed` |

本计划是 Knowledge 功能/效果验收、candidate 身份、效果结论和阶段 A 语料专项验收的唯一计划权威；P3 是工作包与 Gate 状态唯一权威，evidence 是运行文件与哈希唯一权威。`UAT_00` 只治理公共接入与 Employee/Transaction。v1.14 新增不依赖外部 LLM 的阶段 A 14 项语料 UAT；v1.15 明确来源不可达不等于正文缺失，且未核验 P0/目标 P1 只能阻塞发布门禁；v1.16～v1.17 保留早期证据并完成严格合同复评；v1.18 以结构化 legacy DOC 和 a4 修复条款关系；v1.19 以最终工具源码一致的 Stage A corpus candidate-08/a5、UAT/release attempt-05 作为最终 14/14 权威证据。既有 37 项功能 UAT、效果状态及 Knowledge 效果 candidate-01～07 历史运行资产保持不变。

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
| `UAT-K-EV-006` | 合法 Summary V4 | 独立子问题和适用逻辑域使用最小充分直接证据；缺少任一显式要点/域时 insufficient；ref 唯一、quote 为对应授权正文连续子串 |
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

上述 37 个 case 已通过 `knowledge_uat_traceability.v2.json` 追踪到实际自动化或等价有限证据；schema v2 同时校验 candidate-05 最新有效 `partially_effective`、candidate-07 最新执行 `invalid_run / failed_unconsumed` 以及 Summary V4 `Evidence missing`，但不修改历史运行文件。当前 Spring→Runtime 16 场景 E2E 实际执行且未 skip。允许按风险用 fake Model、Java Security、Python contract 和现有不可变只读证据组合验收，不机械要求全部 case 进行真实 LLM 调用。

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

真实执行清单在 non-live 通过后从上述场景确定，最多20个端到端请求、总计60次模型 HTTP（selection/rewrite/summary 均计入）。该清单必须包含核心P0、措辞变体及非酒店保留样本；错误注入不浪费付费请求。单请求硬上限3次模型、4search、2embedding、2rerank；全批对应上限60/80/40/40。实际请求更少时同步收紧。不得通过额外预跑消耗未记录模型请求。

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
