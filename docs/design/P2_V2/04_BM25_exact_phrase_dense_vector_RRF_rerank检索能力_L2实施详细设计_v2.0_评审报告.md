# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：否
- 审查类型：auto
- 目标文档：`docs/design/P2_V2/04_BM25_exact_phrase_dense_vector_RRF_rerank检索能力_L2实施详细设计_v2.0.md`
- 关联文档：P2 04、P2_V2 01/02/03/07/08/09、`HybridSearchRequest`、`HybridSearchMerger`
- 实际审查轮次：3
- 主要风险摘要：初审发现总体流程中出现未落地的 `QueryRewriteNormalizer` 和独立 `DocumentDedupMerger` 命名；已修复为 `DocumentQueryPreparationService` 与 `HybridSearchMerger`。本次串行复审未发现新增问题。

## 2. 文档识别结果

- 识别文档类型：详细设计文档
- 识别依据：包含召回通道、RRF 公式、去重、rerank、接口、实现落点和测试设计。
- 文档状态：Approved
- 是否包含修订历史：是
- 是否存在上级文档：是
- 是否存在关联文档缺失：否

## 3. 审查范围

| 序号 | 文档 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---|---|
| 1 | `04_BM25_exact_phrase_dense_vector_RRF_rerank检索能力_L2实施详细设计_v2.0.md` | 目标文档 | 是 | 主审查对象 |
| 2 | `P2/04_关键词向量混合检索能力_L2实施详细设计_v1.0.md` | 关联文档 | 是 | hybrid/RRF 基线 |
| 3 | P2_V2 01/02/03/07/08/09 | 关联文档 | 是 | mapping、profile、权限、provider、验证和总编排 |
| 4 | `es-query-api`/`es-query-service` hybrid 模型 | 代码结构 | 是 | 只读核对实现落点 |

## 4. S0 阻断问题

未发现 S0 阻断问题。

## 5. S1 严重问题

未发现 S1 严重问题。

## 6. S2 一般问题

未发现 S2 一般问题。

## 7. S3 建议优化

暂无 S3 建议优化。

## 8. 架构设计审查结果

不适用。本文为 L2 实施详细设计。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | 在旧 keyword/vector hybrid 基础上扩展多通道 |
| 文件路径 | 通过 | adapter、es-query、rerank port、测试路径明确 |
| 类与方法 | 通过 | `HybridSearchRequest`、`HybridSearchMerger`、`DocumentCapabilityHandler.applyRerankIfEnabled` 清楚 |
| 入参与返回类型 | 通过 | request/hit/diagnostics 字段明确 |
| 接口契约 | 通过 | 扩展 hybrid request/response，不下放 Runtime DSL |
| 数据结构 | 通过 | channel、rank、RRF、dedup、rerank 诊断字段完整 |
| 校验逻辑 | 通过 | 缺 vector、通道失败、rerank 失败均有降级或 fail closed 规则 |
| 异常处理 | 通过 | rerank 超时/异常降级到 RRF |
| 状态流转 | 通过 | query prepared 到 final projected 完整 |
| 数据库设计 | 不适用 | 不新增表 |
| 缓存与消息 | 不适用 | 不涉及缓存和消息 |
| 权限、审计、幂等、风控 | 通过 | 所有通道同 ACL filter，审计不记录全文 |
| 测试设计 | 通过 | 覆盖 RRF、去重、mapper、rerank 和权限测试 |
| 可编码性 | 通过 | 可指导多路召回、融合和 rerank 实现 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 满足 BM25/exact/phrase/dense_vector + RRF + rerank 目标 |
| 架构到详细设计一致性 | 通过 | rerank 位于 Java handler，不进入 ES 服务 |
| 接口契约一致性 | 通过 | 与 P2_V2 09 的 hybrid channels 方向一致 |
| 代码结构一致性 | 通过 | 对齐现有 `HybridSearchMerger` 扩展方向 |
| 权限与审计一致性 | 通过 | 通道共享 ACL filter |
| 一致性模型一致性 | 通过 | alias/profile/queryVector 下排序稳定 |
| 风控策略一致性 | 通过 | optional channel 可降级，required channel fail closed |
| 测试范围一致性 | 通过 | gold query 和权限测试已覆盖 |

## 11. 是否建议进入后续阶段

- 是否建议进入详细设计：已处于详细设计阶段
- 是否建议进入编码实现：是
- 是否建议先修订架构设计：否
- 是否建议先修订详细设计：否
- 是否需要用户确认：否

## 12. 用户确认项

暂无需要用户确认的问题。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 建议修改内容 | 是否阻断 |
|---:|---|---|---|---|
| 1 | S2 | 第 9 章 | 将 `QueryRewriteNormalizer` 统一为 `DocumentQueryPreparationService` | 否，已修复 |
| 2 | S2 | 第 9 章 | 明确文档级去重由 `HybridSearchMerger` 承担 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-09 | 初审/修正 | 2 | 2 | 0 |
| 2 | 2026-07-09 | 复审 | 0 | 0 | 0 |
| 3 | 2026-07-09 | 串行复审 | 0 | 0 | 0 |

## 15. 最终结论

文档通过品审，不阻断后续编码。多通道召回、RRF、document-level 去重、rerank 和诊断字段设计完整，且与 Java 权威和 Runtime 不可信边界一致。
