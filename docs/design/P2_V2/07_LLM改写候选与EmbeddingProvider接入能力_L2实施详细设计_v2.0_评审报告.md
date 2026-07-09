# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：否
- 审查类型：auto
- 目标文档：`docs/design/P2_V2/07_LLM改写候选与EmbeddingProvider接入能力_L2实施详细设计_v2.0.md`
- 关联文档：P2 07、P2_V2 02/03/04/08/09、Runtime 契约生成模型、`DocumentEmbeddingPort`
- 实际审查轮次：3
- 主要风险摘要：初审发现 rewrite client/normalizer 以“同目录”描述，Runtime endpoint 仍为“实现阶段确认”，不利于后续编码追踪；已补齐建议路径和替代路径记录要求。本次串行复审未发现新增问题。

## 2. 文档识别结果

- 识别文档类型：详细设计文档
- 识别依据：包含 Runtime 请求/响应、EmbeddingProvider 请求、实现落点、测试设计和安全边界。
- 文档状态：Approved
- 是否包含修订历史：是
- 是否存在上级文档：是
- 是否存在关联文档缺失：否

## 3. 审查范围

| 序号 | 文档 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---|---|
| 1 | `07_LLM改写候选与EmbeddingProvider接入能力_L2实施详细设计_v2.0.md` | 目标文档 | 是 | 主审查对象 |
| 2 | `P2/07_LLM与EmbeddingProvider接入能力_L2实施详细设计_v1.0.md` | 关联文档 | 是 | provider 接入基线 |
| 3 | P2_V2 02/03/04/08/09 | 关联文档 | 是 | profile、权限、召回、验证和总编排 |
| 4 | Runtime/Embedding 相关代码结构 | 代码结构 | 是 | 只读核对落点 |

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
| 上级设计承接 | 通过 | Runtime 只返回候选，Java 仍为执行权威 |
| 文件路径 | 通过 | Java rewrite、normalizer、embedding port 和 Runtime 建议路径明确 |
| 类与方法 | 通过 | `DocumentQueryRewritePort`、`RewriteCandidateNormalizer`、`DocumentEmbeddingPort` 等清楚 |
| 入参与返回类型 | 通过 | rewrite/embedding request 和 response 字段明确 |
| 接口契约 | 通过 | 禁止 DSL/filter/alias/profile/topK/sort 字段 |
| 数据结构 | 通过 | queryDigest、rewriteCandidateDigest、embeddingDims 等诊断字段明确 |
| 校验逻辑 | 通过 | 候选长度、重复、禁止字段、dims/model/profile 均校验 |
| 异常处理 | 通过 | LLM/embedding 失败均可降级 |
| 状态流转 | 通过 | rule extraction、rewrite、embedding、variants ready 清楚 |
| 数据库设计 | 不适用 | 不新增表 |
| 缓存与消息 | 通过 | 仅允许不含权限数据的短期缓存 |
| 权限、审计、幂等、风控 | 通过 | Provider 请求不携带 ACL 明细，不记录完整 query |
| 测试设计 | 通过 | 单测、契约、安全、观测测试覆盖 |
| 可编码性 | 通过 | 可指导 Runtime rewrite 和 EmbeddingProvider 接入 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 满足 Runtime 只做 LLM 改写候选的目标 |
| 架构到详细设计一致性 | 通过 | 未把 DSL/filter/index/profile 下放 Runtime |
| 接口契约一致性 | 通过 | Runtime 和 Java 契约边界明确 |
| 代码结构一致性 | 通过 | Java port 和 generated model 更新路径明确 |
| 权限与审计一致性 | 通过 | 不传权限全集和文档全文 |
| 一致性模型一致性 | 通过 | query variants 在单次请求内冻结 |
| 风控策略一致性 | 通过 | 禁止字段丢弃并记录 reason |
| 测试范围一致性 | 通过 | 覆盖失败降级和 prompt injection |

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
| 1 | S2 | 第 19 章 | 补齐 rewrite client、normalizer 和 Runtime endpoint 建议路径 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-09 | 初审/修正 | 1 | 1 | 0 |
| 2 | 2026-07-09 | 复审 | 0 | 0 | 0 |
| 3 | 2026-07-09 | 串行复审 | 0 | 0 | 0 |

## 15. 最终结论

文档通过品审，不阻断后续编码。Runtime 不可信边界、Java 候选归一化、EmbeddingProvider 维度校验和失败降级均已闭合。
