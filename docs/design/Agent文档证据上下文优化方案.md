# Agent 文档证据上下文优化方案

> 文档治理结论：本文已由 `docs/design/P2_V3/00～07` 完整承接，状态为 `Deprecated`。本文仅保留历史设计背景和追溯信息，不再作为实现前置、补充规则或冲突仲裁依据。

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | Agent 文档证据上下文优化方案 |
| 文档路径 | `docs/design/Agent文档证据上下文优化方案.md` |
| 文档层级 | L2 专项实施设计 |
| 文档状态 | Deprecated |
| 当前版本 | v1.2 |
| 最后更新日期 | 2026-07-13 |
| 适用代码基线 | `389b72b6162edfdb4385c8a77bebf56bfb3e2608` |
| 适用范围 | 当前单 Agent 的 Document capability 检索、证据打包、生成候选和结果安全投影 |
| 上级文档 | `Agent目标架构总览_v1.0.md`、`Agent能力执行内核架构设计_v1.0.md`、`Agent元数据与上下文安全架构设计_v1.0.md` |
| 关联文档 | `Agent契约与规划架构设计_v1.0.md` |
| 替代文档 | `docs/design/P2_V3/00_P2_V3文档能力统一设计总览_L2实施详细设计_v3.0.md`、`docs/design/P2_V3/01～07` |
| 是否可作为实现依据 | 否；当前 Document capability 实施只读取 L0/L1、P1_V2 和 P2_V3 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-13 | 全文 | 对齐单 Agent 目标架构并预留 Multi-Agent 安全演进 seam | 补充文档层级、上级边界、预算所有权、生成式候选安全、ACL/溯源、deadline/取消、兼容删除、实现与测试落点 |
| 2 | 2026-07-13 | 文档信息、状态说明、第 15～18 节 | 文档治理复审发现本文已被 P2_V3 完整承接，继续保留 In Review 会形成第二实施权威 | 将状态改为 Deprecated，增加替代文档导航，把代码、契约和索引核验项移交 P1_V2/P2_V3，并补充归档评审与任务完成摘要 |

## 3. 文档状态说明

| 状态 | 含义 | 是否可作为开发依据 |
|---|---|---:|
| Draft | 草稿，尚未完成完整评审 | 否 |
| In Review | 评审修订中，内容可能继续调整 | 否 |
| Approved | 已评审通过，可作为实现依据 | 是 |
| Implementing | 已进入实现阶段 | 是 |
| Implemented | 已完成实现并与设计对齐 | 是 |
| Deprecated | 已废弃 | 否 |

当前状态：Deprecated。本文不得作为当前实现依据；历史设计意图与当前 P2_V3 冲突时，以 `P2_V3/00` 的权威矩阵及对应专题为准。

## 4. 目标与非目标

本节及后续主体内容作为历史设计背景保留，用于解释 P2_V3 的来源，不再独立约束当前实现。

### 4.1 目标

在不改变现有 Document capability 对外响应 ContractRef 的前提下，提升税务政策类问答的召回、生成和引用体验：

1. LLM 只获得已授权、可追溯、噪声受控的证据输入。
2. 前端引用展示尽量是完整句子或完整段落。
3. 召回入口保持足够宽，生成入口和展示出口分别受独立有效预算约束。
4. 生成文本必须以类型化候选进入统一 Result Security Boundary，不得作为 Handler 自由文本直出。
5. 当前设计保持单 Agent，不创建 ResultRef、RunScope、TaskRunner 或 Multi-Agent 状态。

### 4.2 非目标

- 不修改 Route/Plan Runtime 协议和共享 Prompt。
- 不把证据上下文保存为 Capability Context、Context View 或未来 ResultRef。
- 不通过特殊前缀或字符串兼容隐藏 citationId 结构问题。
- 不保留旧配置、旧索引字段或双路径作为目标态兼容方案。
- 不改变 `agent.html` 或现有响应字段结构；`citationText` 仍映射到现有 `snippet`。

## 5. 上级架构约束与边界

| 上级约束 | 本文落实方式 |
|---|---|
| Handler 只接收 Validated Plan | `DocumentPlanValidator` 完成 scope、数量、字段和预算校验后，Handler 才检索和生成 |
| Runtime 是 Planning Runtime | Document generation/embedding/rerank 使用 capability-local infrastructure port，不调用或复用 Route/Plan Runtime |
| 全链共享 absolute deadline | 检索、上下文打包、generation port 和结果投影只消费 `ExecutionContext.absoluteDeadline` 剩余预算 |
| 输出必须类型化并经过安全边界 | LLM 结果作为 Generated Text Candidate，绑定 citation/evidence 和 generation metadata 后进入 `DocumentResultSecurityProjector` |
| 结果预算只能收紧 | 配置值是部署级上限，最终有效值取 Definition/Profile/Policy/Permission/Request 的最严交集 |
| Context 与 ResultRef 不能混用 | `DocumentEvidenceContextPacker` 产物只在当前 Invocation 内存活，不持久化、不跨 Invocation 继承 |
| 当前不实施 Multi-Agent | 本文不增加 Run/Task/Attempt、ResultRef、Delegation 或 Task 状态 |

## 6. 设计范围

### 6.1 范围内

- Document evidence 三类数量预算；
- `citationText`、`generationText`、`embeddingText` 的用途和来源约束；
- generation 前置安全投影；
- 上下文窗口边界；
- 类型化生成候选和最终结果安全投影；
- 索引构建、检索 DSL、配置和验证口径。

### 6.2 范围外

- Capability Context 持久化；
- Multi-Agent ResultRef 和 Task 间证据传递；
- Agent Runtime Route/Plan Prompt；
- 新的 API/UI 响应字段；
- 生产索引别名切换操作本身；
- 写操作、审批、人工确认和工作流。

## 7. 预算所有权与计算规则

三个参数表达不同阶段的部署级上限：

| 参数 | 默认建议 | 作用 | 唯一消费阶段 |
|---|---:|---|---|
| `max-generation-evidence-count` | 5 | 最终进入 LLM 生成上下文的证据条数上限 | Handler 生成前选择 |
| `max-display-citation-count` | 12 | 安全投影后可展示引用条数上限 | Result Security |
| `max-summary-document-count` | 12 | SUMMARIZE 自选 documentIds 数量上限 | Plan Validator |

配置值不能授予权限，也不能独立成为安全事实。最终有效值必须按上级架构统一收紧：

```text
effective limit
  = min(
      Definition / ContractRef intrinsic limit,
      Effective Profile limit,
      applicable Policy limit,
      current Permission / data scope limit,
      request-declared narrowing limit,
      deployment configuration limit
    )
```

`DocumentPlanValidator`、`DocumentCapabilityHandler` 和 `DocumentResultSecurityProjector` 必须消费同一 Execution Validation/Execution Scope 中冻结的有效预算，不能分别只读取 `AgentProperties` 后形成互相不一致的结论。配置为 0 或有效交集为空时 fail closed，不得自动提升为 1。

目标态删除旧参数 `agent.document.evidence-selection.max-evidence-count` 的兼容 setter/binding。若当前代码仍存在，该逻辑只能作为 D03 前迁移残留，必须进入删除清单，不属于本文目标设计。

## 8. 派生证据字段与溯源

索引构建脚本可新增三个派生字段，但不得替代源 chunk：

| 字段 | 用途 | 是否替代 chunk 原文 | 溯源要求 |
|---|---|---:|---|
| `citationText` | 前端引用展示，尽量完整句子 | 否 | 绑定实际支持文本的 source chunk/span；不得展示 span 外内容 |
| `generationText` | LLM 生成上下文，尽量完整句子/段落 | 否 | 保存组成它的 source chunk/span 列表，且全部通过同一 ACL 投影 |
| `embeddingText` | embedding 模型富化输入 | 否 | 记录构造来源；只用于召回解释，不直接作为可展示证据 |

必须保留源 `chunkId`、`chunkIndex`、`charStart`、`charEnd`。`--reshape-chunks` 只用于离线数据实验，不是当前目标索引切换路径。

检索 DSL 可以使用 `citationText`、`generationText` 参与 BM25/PHRASE，但命中后仍必须回到源 chunk/span 构造可引用证据。若命中只来自派生文本而无法映射到授权 source span，则该 hit 不得进入 generation 或 citation。

## 9. ACL、上下文窗口与生成前安全

运行链路必须满足以下顺序：

```text
authorized retrieval request
  → retrieval with ACL filter
  → candidate-level security projection
  → same-document/same-security-boundary context expansion
  → effective generation evidence limit
  → DocumentEvidenceContextPacker
  → capability-local DocumentGenerationPort
  → typed Generated Text Candidate
  → DocumentResultSecurityProjector
  → final response
```

约束：

1. `before/after-chunks` 只能在同一 documentId、tenant/owner、ACL scope 和索引版本内扩展。
2. 上下文扩展不得跨文档、跨 materialType、跨安全分类或跨授权边界。
3. generation port 只接收候选级安全投影后的证据；不得接收未过滤 `_source`、JWT、完整 Authorization Snapshot 或 mask 规则。
4. `DocumentEvidenceContextPacker` 输出是 invocation-local generation evidence payload，不是 Capability Context、Context View 或 ResultRef。
5. 任何一个组成 span 被撤权、缺失或无法验证时，删除对应派生证据；必需证据不足时按 generation failure policy 降级或拒答。

## 10. 类型化生成候选与结果安全

generation port 的返回结果必须以类型化候选表达，至少包含：

- candidate text；
- generation status；
- 引用到本次已授权 evidence 集合的 citation bindings；
- generation operation metadata；
- effective input/output budget reference；
- invocation/request correlation。

`DocumentResultSecurityProjector` 在形成最终 `answerText`、`summaryText` 或 `summaryBullets` 前必须：

1. 校验 candidate 类型与 Document output ContractRef。
2. 逐条校验 citation binding 存在且属于本次已授权 evidence。
3. 删除引用已撤权、已过滤或 provenance 不完整的候选文本。
4. 应用字段权限、mask、display citation 数量和生成输出大小限制。
5. 对缺引用、越权引用、超预算或 generation metadata 不完整的候选执行 fallback/refuse，不得把自由文本直接返回。
6. `citationText` 仅在通过上述校验后映射到响应字段 `snippet`。

## 11. Deadline、取消、失败与重试

- 检索、context expansion、generation、projector 共用当前 Invocation absolute deadline。
- `DocumentGenerationPort`、embedding/rerank port 不得获得独立完整超时。
- 不允许 Client、Handler、HTTP Client 或 provider SDK 对生成调用执行不可见自动重试。
- cancellation/deadline 生效后，迟到生成结果不得进入 final response 或 Context write。
- generation 失败按类型化 failure policy 执行 fallback/refuse；fallback 内容仍必须来自过滤后的结构化结果和安全模板。
- 索引字段缺失、provenance 不完整或 ACL 无法确认时 fail closed，不回退到未验证的 `content + before/after` 拼接。

## 12. 推荐运行参数

以下值只是部署级推荐上限，不是权限或 ContractRef 事实：

```yaml
agent:
  document:
    retrieval:
      default-size: 5
      answer-candidate-size: 30
      summarize-candidate-size: 30
      max-size: 30
    evidence-selection:
      max-generation-evidence-count: 5
      max-display-citation-count: 12
      max-summary-document-count: 12
      strategy: SCORE_GROUP_TOP
      score-groups: 3
      min-top-group-size: 1
    context-window:
      enabled: true
      before-chunks: 5
      after-chunks: 5
    generation:
      max-context-chars: 12000
      max-evidence-chars: 1600
```

当前保留窗口 5 作为既有推荐值，但启用前必须满足第 9 节的同文档、同 ACL 和 provenance 门禁。重建索引并确认 `generationText` 覆盖率、引用准确度和召回质量稳定后，才允许通过受控配置评审将 `before/after-chunks` 收紧到 1～2；任何放大同样必须先通过容量和权限测试。

## 13. 实现落点清单

### 13.1 Java 实现落点

| 序号 | 路径 | 类/接口 | 方法 | 入参 | 返回 | 修改内容 |
|---:|---|---|---|---|---|---|
| 1 | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentPlanValidator.java` | `DocumentPlanValidator` | `validate` | `DocumentAgentPlan rawPlan, ExecutionValidationContext context` | `ValidatedDocumentPlan` | 使用统一有效预算校验 summary document scope，0/空交集 fail closed |
| 2 | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentCapabilityHandler.java` | `DocumentCapabilityHandler` | `execute(ValidatedDocumentPlan plan, ExecutionContext context)`；`applyGenerationIfEnabled(ValidatedDocumentPlan plan, DocumentRetrievalRequest retrievalRequest, AdapterDocumentResult adapterResult, AgentDocumentResult result, ExecutionContext context)`；`selectGenerationEvidence(List<AdapterDocumentEvidence> evidence)` | 见方法签名 | `HandlerResult<DocumentAgentResultPayload>`；`void`；`List<AdapterDocumentEvidence>` | 只使用已授权证据与统一 generation limit，传播 deadline/cancellation |
| 3 | `agent-service/src/main/java/com/dylan/agent/capability/document/generation/DocumentEvidenceContextPacker.java` | `DocumentEvidenceContextPacker` | `pack` | `DocumentContextPackRequest request` | `EvidenceContextPackage` | 校验 source span、同文档/同 ACL 边界并生成 invocation-local payload |
| 4 | `agent-service/src/main/java/com/dylan/agent/capability/document/generation/DocumentGenerationPort.java` | `DocumentGenerationPort` | `generate` | `DocumentGenerationRequest request` | `DocumentGenerationResult` | 返回类型化 candidate、citation bindings、operation metadata，遵守 deadline |
| 5 | `agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java` | `DocumentResultSecurityProjector` | `filter` | `DocumentAgentResultPayload candidate, ExecutionScope scope` | `FilteredResult<DocumentAgentResultPayload>` | 校验生成候选、逐条 citation、撤权、预算、mask 和 fallback/refuse |
| 6 | `agent-adapter-document/src/main/java/com/dylan/agent/adapter/document/DocumentRetrievalMapper.java` | `DocumentRetrievalMapper` | `toSearchDsl(DocumentRetrievalRequest request)`；`toHybridRequest(DocumentRetrievalRequest request)` | `DocumentRetrievalRequest request` | `String`；`HybridSearchRequest` | 派生字段命中必须可回溯授权 source span；继续合并 ACL filter |
| 7 | `agent-service/src/main/java/com/dylan/agent/config/AgentProperties.java` | `EvidenceSelectionProperties` | `setMaxEvidenceCount(int maxEvidenceCount)`；`getMaxGenerationEvidenceCount()`；`getMaxDisplayCitationCount()`；`getMaxSummaryDocumentCount()` | `int maxEvidenceCount`；getter 无入参 | `void`；三个 getter 均返回 `int` | 删除旧 `max-evidence-count` 兼容 setter；三个新参数仅作为部署上限 |

### 13.2 脚本与配置落点

| 序号 | 路径 | 类型 | 参数/配置项 | 修改内容 |
|---:|---|---|---|---|
| 1 | `scripts/chinatax_v2/build_chinatax_dataopt_index.py` | 索引构建脚本 | `citationText`、`generationText`、`embeddingText`、`--reshape-chunks` | 生成派生字段和 provenance；`--reshape-chunks` 保持实验模式 |
| 2 | `agent-service/src/main/resources/application.yml` | 配置 | `agent.document.evidence-selection.*`、`context-window.*`、`generation.*` | 删除旧参数，保留三个独立部署上限；窗口值保持既有建议并受 ACL/provenance 门禁约束 |

### 13.3 测试落点

| 序号 | 路径 | 测试目标 |
|---:|---|---|
| 1 | `agent-service/src/test/java/com/dylan/agent/capability/document/DocumentPlanValidatorTest.java` | effective summary limit、0 预算、请求只能收紧 |
| 2 | `agent-service/src/test/java/com/dylan/agent/kernel/core/DocumentCapabilityHandlerTest.java` | generation 前安全证据、deadline/cancellation、无不可见重试 |
| 3 | `agent-service/src/test/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjectorTest.java` | 逐条 citation、越权/撤权 evidence、生成输出预算、fallback/refuse |
| 4 | `agent-service/src/test/java/com/dylan/agent/config/AgentPropertiesValidatorTest.java` | 三个新参数绑定、旧参数拒绝、上下限关系 |
| 5 | `agent-adapter-document/src/test/java/com/dylan/agent/adapter/document/DocumentRetrievalMapperTest.java` | ACL filter 始终存在、派生字段命中、source span 可回溯 |

## 14. 验证口径

1. 配置：三个新参数可绑定；旧 `max-evidence-count` 不再接受。
2. 预算：Validator、Handler、Result Security 使用同一有效预算证据，请求只能收紧。
3. 生成输入：LLM 证据条数按有效 `max-generation-evidence-count` 截断，且全部通过候选级安全投影。
4. 上下文窗口：覆盖同文档相邻 chunk，以及跨文档、跨 ACL、跨 tenant 被拒绝。
5. 引用展示：`citationText` 仅在 provenance 与权限校验后进入 `snippet`。
6. 生成输出：每个 answer/summary/bullet 均引用本次授权 evidence；缺失或越权时 fallback/refuse。
7. deadline：生成和检索使用同一 absolute deadline，取消后迟到结果不能返回。
8. 索引 dry-run：确认派生字段和 source span/provenance 可重复生成。
9. gold query：索引切换前执行 TopK、完整句比例、citation span 准确度和 ACL 泄漏测试。
10. 回归问题至少覆盖“增值税有哪些税率？”、“小规模纳税人征收率是多少？”、“企业所得税有哪些税率？”。

## 15. 历史风险与权威承接

以下事项仍可能是实施风险，但不再作为本文转 `Approved` 的条件；其设计所有权和验收门禁已经移交当前权威文档。

| 序号 | 历史事项 | 风险 | 当前权威承接 | 对本文状态的影响 |
|---:|---|---|---|---|
| 1 | 旧配置 setter、旧索引 fallback 与预算双路径清理 | 多源配置可能产生不一致预算 | `P1_V2/05～06`、`P2_V3/02`、`P2_V3/07` | 无；本文已 Deprecated |
| 2 | `DocumentGenerationResult`、citation bindings 和 operation metadata | 未验证生成文本可能缺少可信证据绑定 | `P2_V3/05` 定义 provider-independent contract 与安全绑定；`P2_V3/06` 实现 capability-local port/client | 无；按 P2_V3 实施和验收 |
| 3 | 派生字段 provenance、citation span 与索引切换 | 溯源不完整可能造成错误引用或 ACL 泄漏 | `P2_V3/01`、`P2_V3/03`、`P2_V3/05`、`P2_V3/07` | 无；仍阻断不满足门禁的索引切换 |
| 4 | Future Multi-Agent ResultRef 承载 Document typed result | 提前固化可能侵入当前单 Agent 边界 | 未来 `Multi-Agent协调与任务架构设计_v1.0.md` | 无；当前不得提前实现 |

## 16. 评审记录

| 轮次 | 日期 | 评审结论 | 发现问题数 | 修正问题数 | 遗留问题 | 说明 |
|---:|---|---|---:|---:|---|---|
| 1 | 2026-07-13 | 有条件通过（历史时点） | 6 | 6 | 3 个实施对齐阻塞项 | 当时计划在代码与索引验证后转 Approved；该路径已由第 2 轮归档评审终止 |
| 2 | 2026-07-13 | 归档通过 | 1 | 1 | 0 | 复审确认本文已被 P2_V3/00～07 完整承接；消除 In Review 与当前权威矩阵冲突，转为 Deprecated 并移交实施验收项 |

## 17. 历史实施对齐检查（非当前验收依据）

本表仅保留原设计关注点与当前承接位置，不用于判断当前实现是否符合 P2_V3。

| 检查项 | 历史设计要求 | 当前权威位置 | 当前结论 | 说明 |
|---|---|---|---|---|
| 预算唯一性 | 三阶段使用同一有效预算证据 | `P1_V2/05～06`、`P2_V3/02/04/05` | 已移交 | 由当前文档的 typed limits 与门禁核验 |
| 生成候选安全 | 类型化 candidate + citation/evidence 校验 | `P2_V3/05～06` | 已移交 | 由 05 定义安全合同、06 实现不可信 Provider port/client |
| ACL 窗口 | 同文档、同 ACL、同 tenant 扩展 | `P2_V3/03～05` | 已移交 | 跨边界测试仍是当前实施门禁 |
| 兼容删除 | 不保留旧参数和旧索引 fallback | `P1_V2/06`、`P2_V3/07` | 已移交 | 在原子迁移和发布门禁中验证 |
| Multi-Agent 范围 | 不创建 TASK/ResultRef 空壳 | L0/L1、未来 Multi-Agent L1 | 已移交 | 当前仍只实现 CHAT/ConversationScope |

## 18. 任务完成摘要

| 项目 | 内容 |
|---|---|
| 目标文档 | `docs/design/Agent文档证据上下文优化方案.md` |
| 文档状态 | Deprecated |
| 是否可作为实现依据 | 否；使用 L0/L1、P1_V2 和 P2_V3 |
| 本次评审轮次 | 1 |
| 主要修改内容 | 拆分设计评审与实施验收语义；依据 P2_V3 权威矩阵将本文归档，补充替代导航和验收项承接位置 |
| 是否已追加修改历史 | 是 |
| 是否已补充实现落点清单 | 原落点仅作历史保留；当前落点以 P2_V3 为准 |
| 是否存在文档治理阻塞问题 | 否 |
| 是否存在遗留实施风险 | 是；由 P1_V2/P2_V3 的实施与发布门禁管理 |
| 是否需要用户进一步授权 | 否 |
| 建议下一步 | 后续 Document capability 评审、编码和验收只读取 `P2_V3/00～07`，不回查本文补充规则 |
