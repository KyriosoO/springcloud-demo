# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 1 |
| 依据文档数量 | 1 |
| 评审代码范围 | agent-api、agent-adapter-api、agent-service、agent-adapter-document、es-query-api、es-query-service、SQL、pom |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 修正后通过 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `docs/design/P2_V2/04_BM25_exact_phrase_dense_vector_RRF_rerank检索能力_L2实施详细设计_v2.0.md` | detailed_design | 1 | 是 | 已读取 | 作为本轮唯一主依据文档 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | 04 详设第 8、10.1、11.3 章 | BM25、exact、phrase、dense_vector 输出 channel/rank/score/hitFields/chunkId/documentId/indexAlias | `DocumentRetrievalMapper`、`HybridSearchMerger`、`HybridSearchHit` | 已修正 |
| DOC-C-002 | 04 详设第 10.3、14 章 | RRF 只按通道内 rank 和 profile 权重融合，同分按 bestRank、channelCount、documentId、chunkId 稳定排序 | `HybridSearchMerger` | 已修正 |
| DOC-C-003 | 04 详设第 10.4 章 | document-level 去重键包含 indexAlias、profileVersion、permissionEvidenceId、documentId | `HybridSearchMerger` | 已修正 |
| DOC-C-004 | 04 详设第 10.5、13、15、18 章 | Java rerank 在 RRF/去重后执行，成功或失败都应记录 rerankStatus/rerankSkippedReason | `DocumentCapabilityHandler` | 已修正 |
| DOC-C-005 | 04 详设第 8、15 章 | rerank 不新增候选、不绕过 ACL、不接收全文，不改变 citationId | `DocumentCapabilityHandler.safeRerankInput`、`mergeRerankResult` | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|---|
| CR-001 | high | functional_correctness/design_consistency | `es-query-service/.../HybridSearchMerger.java` | DOC-C-002 | RRF 排序在 rrfScore 后使用 ES 原始 maxScore 作为二级排序，而详设要求使用 bestRank、channelCount 等稳定 tie-breaker | 跨通道排序会被不可比的 ES 原始分影响，违背 RRF 融合语义 | 已修复 |
| CR-002 | high | implementation_completeness/security | `es-query-service/.../HybridSearchMerger.java`、`HybridSearchHit.java` | DOC-C-001、DOC-C-003 | 融合命中未携带 indexAlias/profileVersion/permissionEvidenceId，去重键也只按 documentId | 无法显式保证不同 alias/profile/权限证据候选不被合并 | 已修复 |
| CR-003 | medium | implementation_completeness/observability | `agent-adapter-document/.../DocumentRetrievalMapper.java`、`HybridSearchMerger.java` | DOC-C-001 | BM25/exact/phrase 查询未设置命名查询，merger 无法稳定填充 hitFields 诊断 | 命中字段诊断不可用，影响 gold query 和召回分析 | 已修复 |
| CR-004 | medium | implementation_completeness/observability | `agent-service/.../DocumentCapabilityHandler.java` | DOC-C-004 | Java handler rerank 成功、禁用、空候选或异常降级后未覆盖 diagnostics，仍可能保留 ES 侧 `NOT_REQUESTED` | 启用 rerank 时诊断与真实执行状态不一致 | 已修复 |
| CR-005 | medium | test_coverage | `HybridSearchMergerTest.java`、`DocumentCapabilityHandlerTest.java` | DOC-C-002、DOC-C-003、DOC-C-004 | 缺少 RRF tie-breaker、hitFields、冻结上下文、rerank 诊断回归测试 | 后续容易回归为按 ES score 排序或丢失 rerank 状态 | 已修复 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| 无 | - | - | - | 未发现阻断性文档问题 | - | - |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | `HybridSearchMerger.java` | RRF 排序改为 rrfScore、bestRank、channelCount、documentId、chunkId；候选 key 和 dedup key 纳入 indexAlias/profileVersion/permissionEvidenceId | CR-001、CR-002 | 已修复 |
| 1 | `HybridSearchHit.java` | 增加 indexAlias、profileVersion、permissionEvidenceId 字段 | CR-002 | 已修复 |
| 1 | `DocumentRetrievalMapper.java` | BM25/exact/phrase DSL 增加 `_name`，支持 ES `matched_queries` 回填 hitFields | CR-003 | 已修复 |
| 1 | `DocumentCapabilityHandler.java` | rerank 启用、禁用、空候选、空结果、异常降级时更新 diagnostics | CR-004 | 已修复 |
| 1 | `HybridSearchMergerTest.java`、`DocumentCapabilityHandlerTest.java` | 补充 RRF tie-breaker、matched_queries、冻结上下文和 rerank 诊断测试 | CR-005 | 已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `mvn -pl agent-api,agent-adapter-api,agent-service,agent-adapter-document,es-query-api,es-query-service -DskipTests compile` | 未执行 | 当前仓库无顶层聚合 POM，`-pl` reactor 命令不适用；按模块 POM 执行替代验证 |
| 1 | `mvn -pl agent-api,agent-adapter-api,agent-service,agent-adapter-document,es-query-api,es-query-service test` | 未执行 | 同上 |
| 1 | `mvn -f es-query-api/pom.xml -DskipTests install` | 通过 | 安装更新后的 `HybridSearchHit` 本地快照供下游模块解析 |
| 1 | `mvn -f es-query-service/pom.xml "-Dtest=HybridSearchMergerTest,EsDocumentServiceTest" "-DfailIfNoTests=false" test` | 通过 | 24 个测试通过 |
| 1 | `mvn -f agent-adapter-document/pom.xml "-Dtest=DocumentRetrievalMapperTest,DocumentEvidenceMapperTest" "-DfailIfNoTests=false" test` | 通过 | 9 个测试通过 |
| 1 | `mvn -f agent-service/pom.xml "-Dtest=DocumentCapabilityHandlerTest" "-DfailIfNoTests=false" test` | 通过 | 18 个测试通过 |
| 1 | `git diff --check` | 通过 | 无空白错误 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | 未执行全仓库回归 | 本轮按 04 变更点执行最小相关模块测试 | 发布前按 CI 执行完整回归 |
| RISK-002 | medium | ES `matched_queries` 依赖查询命名和 ES 返回行为 | 当前已在 DSL 中加入 `_name` 并在 merger 中读取，但实际 ES 版本行为仍需集成环境确认 | 在 P2_V2 08 gold query 验证中加入 hitFields 诊断断言 |
| RISK-003 | low | 本地 Maven SNAPSHOT 被更新 | 为让独立模块解析到最新 `es-query-api`，执行了本地 `install` | CI 中应按模块顺序构建，避免旧 SNAPSHOT |

## 9. 结论

最终结论：修正后通过。

说明：
- 04 详设要求的 BM25/exact/phrase/dense_vector 多通道、N 路 RRF 稳定融合、document-level 去重、hitFields 诊断和 Java 侧 rerank 诊断已完成代码对齐。
- 本轮未修改 SQL、依赖版本、设计文档正文，未 commit、未 push、未创建 PR。
