# 文档ACL与索引模型_L2实施详细设计_交接文件

## 1. 交接目标

在新窗口中开始编写：

`docs/design/P2/文档ACL与索引模型_L2实施详细设计_v1.0.md`

目标文档应作为 Agent 文档型检索、生成式问答与总结能力进入联调、灰度和生产启用前的前置详细设计，重点补齐文档 ACL、索引 mapping、索引字段模型、权限过滤契约、录入写入契约、重建回滚和验证门禁。

## 2. 当前结论

当前已具备直接开始 L2 详细设计的条件，不需要先重做 Agent L1 架构设计。

判断依据：

1. 既有 Agent 文档型检索与生成式问答 L2 已明确：文档上传、清洗、切分、索引构建、文档级 ACL 权威源属于 Agent 执行链路外部前置项。
2. Agent 侧实现已具备对接点：`VectorSearchRequest.filterDsl`、`HybridSearchRequest.filters`、`HybridSearchHit`、`AdapterDocumentEvidence`、`DocumentEvidenceContextPacker`、`DocumentResultSecurityProjector`。
3. 当前阻塞生产启用的问题集中在下游 ACL、ES mapping、证据脱敏和索引构建闭环，而不是 Agent 侧生成式能力本身。
4. 新设计可以作为独立 P2 L2 文档，不必修改已完成的 Agent 生成式问答详细设计。

## 3. 必读依据文档

| 路径 | 用途 |
|---|---|
| `docs/design/P2/Agent文档型检索与总结能力_L2实施详细设计_v1.0.md` | 文档检索首版能力、抽取式 fallback、基础 evidence 契约 |
| `docs/design/P2/Agent文档型检索与总结能力_设计文档品审报告.md` | 首版风险，尤其是下游 ACL、索引字段、queryVector 来源 |
| `docs/design/P2/Agent文档型生成式问答与总结能力_L2实施详细设计_v1.0.md` | 生成式问答与总结能力对 ACL、mapping、证据上下文的依赖 |
| `docs/design/P2/Agent文档型生成式问答与总结能力_设计文档品审报告.md` | 明确 provider、ACL、ES mapping 不阻断编码但阻断联调、灰度、生产启用 |
| `docs/design/Agent元数据与上下文安全架构设计_v1.0.md` | Agent 权限、授权快照、ResultSecurity、Context 安全边界 |
| `docs/design/Agent能力执行内核架构设计_v1.0.md` | ExecutionCore、Handler、Adapter、ResultSecurity 的职责边界 |

## 4. 代码现状参考

| 模块 | 参考点 |
|---|---|
| `es-query-api` | `VectorSearchRequest.filterDsl`、`HybridSearchRequest.filters`、`HybridSearchHit`、`HybridSearchResponse` |
| `es-query-service` | `EsDocumentService.vectorSearchBody`、`keywordSearchBody`、`hybridSearch`、`HybridSearchMerger` |
| `agent-adapter-api` | `DocumentRetrievalRequest`、`AdapterDocumentEvidence`、`AdapterDocumentResult` |
| `agent-adapter-document` | `DocumentRetrievalMapper`、`DocumentEvidenceMapper`、`DocumentSearchClient` |
| `agent-service` | `DocumentCapabilityHandler`、`DocumentEvidencePreSecurityFilter`、`DocumentEvidenceContextPacker`、`DocumentResultSecurityProjector` |

## 5. 设计范围建议

### 5.1 范围内

1. 文档 ACL 权威模型：tenant、corpus、document、section、chunk 的可见性和继承规则。
2. ACL 表达与索引字段：`aclRef`、`visibility`、`tenantId`、`departmentIds`、`roleIds`、`userIds`、`attributes` 等字段是否入 ES。
3. ES index mapping：keyword、text、dense_vector、metadata、context window、chunk 定位字段。
4. 文档切分与索引模型：`documentId`、`chunkId`、`chunkIndex`、`charStart`、`charEnd`、`content`、`snippet`、`contextBefore`、`contextAfter`。
5. 权限过滤契约：Agent/adapter/es-query 如何生成和传递 filter DSL，哪些字段允许出现在 DSL。
6. 录入写入契约：资料录入、清洗、脱敏、embedding、写 ES 时必须写入哪些字段。
7. 权限变更处理：撤权、授权变更、文档删除、重建、增量更新、索引版本切换。
8. 安全与审计：不记录 JWT、完整 ACL 表达式、原始全文、queryVector、prompt、LLM 原始响应。
9. 验证门禁：mapping 校验、ACL 正反例、撤权延迟、hybrid/vector 查询权限过滤、LLM 输入授权证明。

### 5.2 范围外

1. 不重写 Agent 文档型检索或生成式问答能力。
2. 不修改 Runtime route/plan 职责。
3. 不在 Agent 侧持久化文档全文或文档 ACL 权威表。
4. 不实现完整文档平台 UI。
5. 不直接启用生产开关。
6. 不引入 rerank 或长文档异步任务，除非另行授权。

## 6. 关键设计判断

1. ACL 应在检索阶段 fail closed，不能只依赖 Agent ResultSecurity 事后过滤。
2. LLM 输入必须只来自已授权、已脱敏、已裁剪的 chunk。
3. `es-query-service` 可以消费 ACL filter DSL，但不应生成 Agent 权限结论。
4. `agent-service` 可基于当前 `ExecutionScope` 和文档域规则生成受控 filter，但不应持有 documentId 级 ACL 权威表。
5. 文档录入必须在 chunk 级写入足够的权限与定位元数据，否则后续 hybrid/vector 检索无法证明证据来源安全。
6. 权限撤销后必须有明确策略：实时 ACL filter、索引重建、版本切换或组合方案。

## 7. 待决策问题

| 编号 | 问题 | 建议默认决策 |
|---:|---|---|
| D1 | ACL 权威源属于现有权限系统、文档平台还是独立 ACL 服务 | 设计为外部文档 ACL 权威源，Agent 只消费授权投影或 filter 输入 |
| D2 | ACL 粒度到 document 还是 chunk | 首版支持 document 级继承到 chunk，预留 chunk override |
| D3 | ES 中保存 ACL 展开字段还是 `aclRef` 后实时查权 | 首版建议保存可检索的安全投影字段，同时保留 `aclRef` 追溯 |
| D4 | 权限变更后如何处理旧索引 | 首版要求版本化重建或增量更新，并定义撤权最大延迟 |
| D5 | 向量检索如何保证 ACL 过滤 | KNN query 必须带 filter；无 filter 或 ACL 不可用时 fail closed |
| D6 | 脱敏发生在录入阶段还是检索返回阶段 | 建议录入阶段生成可展示 snippet，同时检索返回前再做安全裁剪 |

## 8. 建议文档结构

1. 文档元信息与状态。
2. 背景与目标。
3. 设计范围与非目标。
4. 上级约束与关联文档。
5. 总体架构。
6. 文档 ACL 权威模型。
7. 文档、section、chunk 数据模型。
8. ES index mapping 设计。
9. 向量字段与 embedding 元数据设计。
10. ACL filter DSL 契约。
11. 文档录入与索引构建写入契约。
12. 权限变更、删除、重建和回滚。
13. 与 Agent / adapter / es-query 的接口边界。
14. 安全、审计与日志。
15. 异常处理与 fail closed 策略。
16. 幂等、并发与一致性。
17. 性能与容量。
18. 配置与灰度开关。
19. 实施落点。
20. 测试设计。
21. 风险与待确认事项。
22. 评审记录。
23. 实施对齐检查清单。
24. 完成摘要。

## 9. 新窗口建议启动提示

可在新窗口中直接使用以下请求：

```text
[$detailed-design-document](C:\Users\zhoud\.agents\skills\detailed-design-document\SKILL.md) 基于当前仓库现状、既有 Agent 文档型检索与生成式问答设计，以及 docs/design/P2/文档ACL与索引模型_L2实施详细设计_交接文件.md，开始编写 docs/design/P2/文档ACL与索引模型_L2实施详细设计_v1.0.md，并执行评审-修复循环，最多6轮。
```

若需要结构化参数，可使用以下关键参数：

```yaml
task: detailed_design_document
operation: generate
review_type: auto
target_doc: docs/design/P2/文档ACL与索引模型_L2实施详细设计_v1.0.md
output_doc: docs/design/P2/文档ACL与索引模型_L2实施详细设计_v1.0.md
source_docs:
  - docs/design/P2/文档ACL与索引模型_L2实施详细设计_交接文件.md
  - docs/design/P2/Agent文档型检索与总结能力_L2实施详细设计_v1.0.md
  - docs/design/P2/Agent文档型检索与总结能力_设计文档品审报告.md
  - docs/design/P2/Agent文档型生成式问答与总结能力_L2实施详细设计_v1.0.md
  - docs/design/P2/Agent文档型生成式问答与总结能力_设计文档品审报告.md
parent_docs:
  - docs/design/Agent目标架构总览_v1.0.md
  - docs/design/Agent能力执行内核架构设计_v1.0.md
  - docs/design/Agent元数据与上下文安全架构设计_v1.0.md
document:
  name: 文档ACL与索引模型_L2实施详细设计
  status: Draft
  version: v1.0
  created_date: "2026-07-06"
  updated_date: "2026-07-06"
  output_language: zh-CN
scope:
  in_scope:
    - 文档 ACL 权威模型
    - 文档与 chunk 索引字段模型
    - ES mapping 与 dense_vector 字段
    - ACL filter DSL 契约
    - 资料录入写入契约
    - 权限变更、索引重建、删除、回滚
    - 与 Agent / adapter / es-query 的接口边界
    - 安全、审计、测试与生产启用门禁
  out_of_scope:
    - 不实现完整文档平台 UI
    - 不修改 Runtime route/plan 职责
    - 不把文档 ACL 权威表放入 agent-service
    - 不启用生产开关
permissions:
  allow_create_output_doc: true
  allow_modify_target_doc: true
  allow_modify_parent_docs: false
  allow_modify_related_docs: false
  allow_modify_code: false
  allow_modify_tests: false
  allow_modify_config: false
review_policy:
  enabled: true
  review_rounds: 6
  stop_when_no_issues: true
output_requirements:
  include_document_status: true
  include_modification_history: true
  include_parent_doc_constraints: true
  include_related_doc_boundaries: true
  include_implementation_touchpoints: true
  include_review_records: true
  include_remaining_risks: true
  include_completion_summary: true
```

## 10. 完成标准

目标 L2 文档完成后，应至少能支撑以下问题进入编码或联调：

1. 一个用户请求如何转换为 ES ACL filter。
2. 一个 chunk 如何表达可见范围和来源定位。
3. 权限撤销后旧索引如何失效或更新。
4. LLM 输入如何证明只来自授权 chunk。
5. ES mapping 如何同时支持 keyword、vector、hybrid。
6. ACL 服务不可用或 filter 缺失时如何 fail closed。
7. 资料录入、索引构建、重建、回滚分别由哪些模块负责。
