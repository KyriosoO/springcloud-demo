# [UAT_01] 单体 Agent Knowledge 查询验收测试计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `UAT_01` |
| 当前版本 | v1.12 |
| 文档状态 | Reviewed |
| 日期 | 2026-08-28 |
| 适用范围 | `knowledge.query` 的生产接线、功能型验收、效果诊断与后续效果型验收 |
| 上位依据 | `L1_00` v3.1、`L1_01` v1.9、`L2_01_00` v1.10、`L2_01_01` v1.9、`L2_01_02` v1.12、`P3_00` v2.29 |
| 历史边界 | candidate-01～07 的既有 manifest/authorization/consumed/journal/result/evidence/failure 均保持不可变；candidate-07 为 `failed_unconsumed` |

本计划是 Knowledge 功能/效果验收、candidate 身份和效果结论的唯一计划权威；P3 是工作包与 Gate 状态唯一权威，evidence 是运行文件与哈希唯一权威。`UAT_00` 只治理公共接入与 Employee/Transaction。v1.12 将当前机器可校验追踪资产升级为 schema v2，分别绑定最新有效效果、最新执行终态和当前 Summary 版本证据状态；candidate-01～07 的历史运行资产保持字节不变。

## 2. 目标、非目标与结论口径

功能 UAT 验证生产链路、权限、安全、失败关闭、证据可追踪和组件隔离；效果 UAT 验证域选择、召回、融合、重排、证据覆盖、摘要有效性和人工 usefulness。两类结论独立：

- Functional：`Passed` / `Failed`；
- Effectiveness：`Effective` / `Partially effective` / `Ineffective` / `Invalid run`；当前任务版本尚无有效测量时，使用独立的 `evidenceStatus=missing` 表达，不新增效果结论枚举。

功能通过不代表效果达标。一次有效、完整且安全 Gate 通过的运行关闭“效果已测量”责任，其效果等级必须如实记录；`effective` 是质量目标而非项目硬关闭条件。`invalid_run` 不形成有效测量，且不得自动重跑或创建新 candidate。当前阶段不修改知识正文、ES mapping/alias/index、公共 DTO、角色或出域权限，也不建立第二套在线流程。

## 3. 被验收的生产链路

```text
Spring 公共接入与认证
  → Python Runtime / 单动作选择 knowledge.query
  → Question Guard / KnowledgeRewriteTaskV1
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
| `UAT-K-RW-002` | 模型返回非法候选 | 仅在设计允许且原问题安全时回退原问题，否则失败关闭 |
| `UAT-K-RW-003` | rewrite timeout/provider failure | 固定失败语义，不进入检索或按已评审原问题回退规则执行 |
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
