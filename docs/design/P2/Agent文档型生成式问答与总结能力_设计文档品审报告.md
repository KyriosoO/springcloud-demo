# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：否
- 审查类型：detailed
- 目标文档：`docs/design/P2/Agent文档型生成式问答与总结能力_L2实施详细设计_v1.0.md`
- 关联文档：`docs/design/Agent目标架构总览_v1.0.md`；`docs/design/Agent契约与规划架构设计_v1.0.md`；`docs/design/Agent能力执行内核架构设计_v1.0.md`；`docs/design/Agent元数据与上下文安全架构设计_v1.0.md`；`docs/design/P2/Agent文档型检索与总结能力_L2实施详细设计_v1.0.md`；`docs/design/P2/Agent文档型检索与总结能力_设计文档品审报告.md`；`AGENTS.md`
- 实际审查轮次：2
- 主要风险摘要：未发现 S0/S1；provider、ACL、ES mapping、RRF 质量和 runtime 生成职责变更均已作为非编码阻断风险记录。

## 2. 文档识别结果

- 识别文档类型：详细设计文档
- 识别依据：文档包含 Java/Python/API/配置/测试落点、方法签名、DTO 字段、状态流转、异常处理、权限审计、测试矩阵和实施对齐检查。
- 文档状态：Approved
- 是否包含修订历史：是
- 是否存在上级文档：是
- 是否存在关联文档缺失：`AGENTS.md` 在仓库根目录未发现实体文件；本轮使用用户在对话中提供的 AGENTS 规则作为协作约束，不影响核心设计判断。

## 3. 审查范围

| 序号 | 文档 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---|---|
| 1 | `docs/design/P2/Agent文档型生成式问答与总结能力_L2实施详细设计_v1.0.md` | 目标文档 | 是 | 被审查和修订的 L2 详细设计 |
| 2 | `docs/design/Agent目标架构总览_v1.0.md` | 关联文档 | 是 | L0 capability、Runtime、契约和安全边界 |
| 3 | `docs/design/Agent契约与规划架构设计_v1.0.md` | 关联文档 | 是 | Java/OpenAPI/Python 契约与规划边界 |
| 4 | `docs/design/Agent能力执行内核架构设计_v1.0.md` | 关联文档 | 是 | ExecutionCore、Handler、ResultSecurity 边界 |
| 5 | `docs/design/Agent元数据与上下文安全架构设计_v1.0.md` | 关联文档 | 是 | Profile、Policy、Context、权限和审计边界 |
| 6 | `docs/design/P2/Agent文档型检索与总结能力_L2实施详细设计_v1.0.md` | 关联文档 | 是 | 文档检索首版能力和抽取式 fallback 基线 |
| 7 | `docs/design/P2/Agent文档型检索与总结能力_设计文档品审报告.md` | 关联文档 | 是 | 首版设计风险 R1/R2/R5 继承依据 |
| 8 | `AGENTS.md` | 关联文档 | 否 | 仓库实体文件缺失；使用用户对话提供规则 |

## 4. S0 阻断问题

未发现 S0 阻断问题。

## 5. S1 严重问题

未发现 S1 严重问题。

## 6. S2 一般问题

未发现未修复的 S2 一般问题。

已修复的 S2 问题如下：

| 序号 | 位置 | 问题 | 风险 | 修改建议 |
|---:|---|---|---|---|
| 1 | 第 1、3、24 章 | 文档仍为 `Draft`，但本轮品审通过后应同步状态 | 后续实施方可能误判文档尚不能作为编码依据 | 将文档状态同步为 `Approved`，并保留生产启用前确认项 |
| 2 | 第 11.1 节 | hybrid search 接口缺少请求头、权限输入、审计和幂等约束 | 实施时可能误透传用户凭据或记录 queryVector/DSL | 补充接口约束表 |
| 3 | 第 19.1 节 | 生成链路的 request/result/context/budget DTO 落点不够完整 | 编码时可能只实现端口类，缺少稳定内部契约 | 补充 `DocumentEmbeddingRequest`、`EvidenceContextPackage`、`DocumentGenerationResult` 等 DTO |
| 4 | 第 19.4 节 | `DocumentCapabilityHandlerTest` 路径与当前仓库结构不一致 | 可能新建重复测试类或绕开既有 ExecutionCore 测试路径 | 修正为 `agent-service/src/test/java/com/dylan/agent/kernel/core/DocumentCapabilityHandlerTest.java` |

## 7. S3 建议优化

暂无未处理的 S3 建议优化。

## 8. 架构设计审查结果

不适用。目标文档识别为详细设计文档。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | 继承 capabilityId、planKind、Runtime 不可信、Java 契约源、ExecutionCore 和 ResultSecurity 边界 |
| 文件路径 | 通过 | 已列出 Java、Python、配置、OpenAPI、fixture、测试路径 |
| 类与方法 | 通过 | 已列出新增/修改类、方法名、入参和返回类型 |
| 入参与返回类型 | 通过 | 核心 DTO、Port、Mapper、Handler、Projector 均已明确 |
| 接口契约 | 通过 | 已补齐 hybrid search 的 method、URI、body、header、错误、幂等、权限和审计约束 |
| 数据结构 | 通过 | 覆盖 `HybridSearchHit`、`EvidenceContextPackage`、`DocumentGenerationResult`、`CitationVerificationResult` |
| 校验逻辑 | 通过 | 覆盖 retrieval/generation options、向量维度、预算、citation、deadline |
| 异常处理 | 通过 | 覆盖 embedding、ES、LLM、citation、deadline 和降级策略 |
| 状态流转 | 通过 | 覆盖 `DISABLED/SKIPPED/EMBEDDING_FAILED/PACKED/GENERATING/SUCCEEDED/FALLBACK/FAILED` |
| 数据库设计 | 通过 | 明确首版不新增表和 migration；后续 generation trace 需另起设计 |
| 缓存与消息 | 通过 | 首版不引入缓存、消息或异步任务 |
| 权限、审计、幂等、风控 | 通过 | LLM 输入前过滤、输出后引用校验和 ResultSecurity 二次过滤闭环 |
| 测试设计 | 通过 | 覆盖 es-query、adapter、service、runtime、contract、安全、UI 和 drift |
| 可编码性 | 通过 | 第 19、20 章足以支撑后续实施拆分和代码评审 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 生成式问答与总结被限制在文档能力横向扩展范围内 |
| 架构到详细设计一致性 | 通过 | 未改变 Runtime、ExecutionCore、ResultSecurity 和 Context 所有权 |
| 接口契约一致性 | 通过 | Java DTO 仍为 OpenAPI/Python 生成源 |
| 代码结构一致性 | 通过 | 落点与当前 `agent-*`、`es-query-*` 模块结构一致；已修正测试路径 |
| 权限与审计一致性 | 通过 | 不向 LLM/provider 发送未授权 evidence、权限表达式、JWT 或 queryVector 原值日志 |
| 一致性模型一致性 | 通过 | 不新增持久化状态，仍依赖 Invocation finalization 原子闭环 |
| 风控策略一致性 | 通过 | 默认关闭、fail closed、降级和回滚策略明确 |
| 测试范围一致性 | 通过 | 覆盖契约、异常、安全、降级和回归 |

## 11. 是否建议进入后续阶段

- 是否建议进入详细设计：已完成
- 是否建议进入编码实现：是
- 是否建议先修订架构设计：否
- 是否建议先修订详细设计：否
- 是否需要用户确认：无需为编码开始额外确认；联调、灰度和生产启用前需确认 provider、ACL、ES mapping。

## 12. 用户确认项

暂无需要用户确认的问题。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 建议修改内容 | 是否阻断 |
|---:|---|---|---|---|
| 1 | S2 | 第 1、3、24 章 | 同步文档状态为 `Approved`，明确可作为编码依据 | 否 |
| 2 | S2 | 第 11.1 节 | 补齐 hybrid search header、权限、审计、幂等、错误响应约束 | 否 |
| 3 | S2 | 第 19.1 节 | 补齐生成链路内部 DTO 和预算对象落点 | 否 |
| 4 | S2 | 第 19.4 节 | 修正 `DocumentCapabilityHandlerTest` 路径 | 否 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-06 | 初审 / 修正 | 4 | 4 | 无 S0/S1；R1-R6 为非编码阻断风险 |
| 2 | 2026-07-06 | 复审 | 0 | 0 | 无 S0/S1 |

## 15. 最终结论

目标详细设计文档通过品审，不阻断后续编码。文档已同步为 `Approved`，第 19 章和第 20 章可作为后续实施与验证依据。

当前最需要优先关注的不是继续改设计，而是在实施前保持生成式能力默认关闭；在联调、灰度或生产启用前完成 embedding provider、LLM provider、下游 ACL 和 ES mapping 的确认。
