# [UAT_01] 单体 Agent Knowledge 查询验收测试计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `UAT_01` |
| 当前版本 | v1.3 |
| 文档状态 | Reviewed |
| 日期 | 2026-08-26 |
| 适用范围 | `knowledge.query` 的生产接线、功能型验收、效果诊断与后续效果型验收 |
| 上位依据 | `L1_00` v2.6、`L1_01` v1.4、`L2_01_00` v1.5、`L2_01_01` v1.4、`L2_01_02` v1.5、`P3_00` v2.20 |
| 历史边界 | candidate-04 及其 manifest/authorization/journal/result/evidence/hash 保持不可变，正式结论仍为 `ineffective` |

本计划是 Knowledge 专用验收权威；`UAT_00` 继续只治理公共接入与 Employee/Transaction，不用其 Business 结果代替 Knowledge 验收。

## 2. 目标、非目标与结论口径

功能 UAT 验证生产链路、权限、安全、失败关闭、证据可追踪和组件隔离；效果 UAT 验证域选择、召回、融合、重排、证据覆盖、摘要有效性和人工 usefulness。两类结论独立：

- Functional：`Passed` / `Failed`；
- Effectiveness：`Effective` / `Partially effective` / `Ineffective` / `Invalid run` / `Not run`。

功能通过不代表效果达标。有效但 `ineffective` 的运行只能证明效果被有效测量，不能改判为达标。当前阶段不修改知识正文、ES mapping/alias/index、公共 DTO、角色或出域权限，也不建立第二套在线流程。

## 3. 被验收的生产链路

```text
Spring 公共接入与认证
  → Python Runtime / 单动作选择 knowledge.query
  → Question Guard / KnowledgeRewriteTaskV1
  → tax.policy / tax.law 逻辑域与 Retrieval Plan
  → es-query-service typed Knowledge endpoint / 最终读取授权
  → keyword + vector / RRF / BGE rerank
  → Evidence 完整性、选择与三层出域交集
  → KnowledgeSummaryTaskV3 / 独立子问题证据覆盖、引用唯一性与原文连续子串校验
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
| `UAT-K-EV-003` | 全局∩域∩文档策略允许 | 仅最小 payload 进入 summary v3 |
| `UAT-K-EV-004` | 未分类、策略缺失/冲突或文档收紧拒绝 | `model_egress_denied`，summary 调用 0 |
| `UAT-K-EV-005` | 证据覆盖不足 | `no_result/insufficient_evidence`，不生成肯定回答 |
| `UAT-K-EV-006` | 合法 summary v3 | 独立子问题使用最小充分证据，ref 唯一、quote 为对应授权正文连续子串 |
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

上述 37 个 case 已通过 `knowledge_uat_traceability.v1.json` 追踪到实际自动化或等价有限证据；当前 Spring→Runtime 16 场景 E2E 实际执行且未 skip。允许按风险用 fake Model、Java Security、Python contract 和现有不可变只读证据组合验收，不机械要求全部 case 进行真实 LLM 调用。

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

当前可复现诊断：domain exact match=0.5909、rerank recall@10=0.9405、required evidence coverage=0.4643、summary valid completion=0.6923。证据支持域目录 v2 与 Summary v3；不支持修改 RRF/rerank、validator、dataset/gold。两个虚构文件 case 的零域期望保留为数据/gold 事项，不要求生产 Selector 猜测文件真实性。

### 7.3 最小优化与版本规则

只有被证据支持的 Prompt、逻辑域安全描述、Retrieval Profile 逻辑参数、RRF/rerank 参数、Evidence 选择或 Harness 才能新版本化；不得改历史 case/gold、放宽 validator、修改正文/index/mapping/alias、扩大授权或降低阈值改判。

### 7.4 新候选准备

新候选必须在功能 UAT Passed、根因明确、新版本 non-live 回归通过后冻结。准备资产至少包含新 run ID、manifest 与 SHA-256、authorization reference、case/variant 数、精确最大模型调用数、任务/Prompt/代码/Profile/index/策略快照、首个 outbound 消费规则、retry/resume=0、append-only Schema 和失败关闭测试。

candidate-05 已按 frozen HEAD=`63bc30baa68948a35840b650c0deb39d1e312efa` 唯一执行：run ID=`knowledge-p5-live-v2-20260826-candidate-05`，manifest SHA-256=`41997c6d41f3109b178844c9b74799bb59c869ae06ec23aca66bea1a6f1e278c`，26 case × 2 variant；52 个 Capability 成对完整，实际付费 rewrite22+summary22=44，retry/resume/core answer=0。安全 Gate 通过，Q1/Q2 通过、Q3/Q4 未通过，Effectiveness=`Partially effective`。

GATE-072 授权已消费，不得重跑、补跑或续跑。未来效果调用必须建立新版本、新候选和新的精确授权。

## 8. 门禁与状态

| 门禁 | 控制内容 | 关闭条件 | 当前状态 |
|---|---|---|---|
| `GATE-071` | Knowledge 当前设计基线 | L1/L2/P3/UAT_01 三轮内审及独立评审通过 | Closed |
| `GATE-UAT-008` | 功能型 Knowledge UAT | 37/37 case 有严格追踪、关键 16 场景 E2E 实际通过、状态一致 | Closed |
| `GATE-072` | 新效果 UAT outbound | candidate-05 唯一运行有效完成并形成 append-only result/evidence | Closed |

`GATE-072` 已消费并关闭，只证明本次效果被有效测量；`Partially effective` 不等于整体效果达标。

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
