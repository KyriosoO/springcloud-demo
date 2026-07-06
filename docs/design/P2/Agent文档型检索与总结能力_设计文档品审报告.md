# Agent文档型检索与总结能力_设计文档品审报告

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 报告版本 | v1.0 |
| 评审日期 | 2026-07-06 |
| 评审类型 | auto |
| 目标文档 | `docs/design/P2/Agent文档型检索与总结能力_L2实施详细设计_v1.0.md` |
| 输出文档 | `docs/design/P2/Agent文档型检索与总结能力_设计文档品审报告.md` |
| 允许修改目标文档 | 是 |
| 允许修改关联文档 | 否 |
| 实际修改关联文档 | 否 |

## 2. 评审范围

| 文档 | 用途 | 是否修改 |
|---|---|---:|
| `docs/design/P2/Agent文档型检索与总结能力_L2实施详细设计_v1.0.md` | 目标 L2 详细设计 | 是 |
| `docs/design/Agent目标架构总览_v1.0.md` | L0 capability-first、Runtime 不可信、ResultSecurity 边界约束 | 否 |
| `docs/design/Agent契约与规划架构设计_v1.0.md` | Java 契约源、Route/Plan、Prompt 和 generated model 约束 | 否 |
| `docs/design/Agent能力执行内核架构设计_v1.0.md` | ExecutionCore、Validator、Handler、ResultSecurity 调用链约束 | 否 |
| `docs/design/Agent元数据与上下文安全架构设计_v1.0.md` | Profile/Policy/Permission/Domain/Context/ResultSecurity 安全边界 | 否 |

## 3. 评审结论

结论：有条件通过。

目标文档经过 2 轮正式品审-修正循环后，未发现 S0/S1 阻塞问题。文档可以作为 Agent 侧编码输入，但 `R1` 下游文档 ACL 契约和 `R2` 向量查询输入来源在联调、灰度或生产启用前必须确认；在确认前应保持 `agent.document.enabled=false` 或使用 mock/stub 进行 Agent 侧开发。

不建议修改关联 L0/L1 文档。当前问题均可在 P2 L2 实施详细设计内通过横向扩展约束收敛，不需要扩大文档修改范围。

## 4. 阻塞判定

| 阻塞项 | 判定 |
|---|---|
| 是否存在 S0 | 否 |
| 是否存在未修复 S1 | 否 |
| 是否需要修改 L0/L1 | 否 |
| 是否需要停止目标文档修改 | 否 |
| 是否可进入 Agent 侧编码 | 是 |
| 是否可直接生产启用 | 否，需先确认下游 ACL、索引字段和向量输入来源 |

## 5. 严重级别统计

| 阶段 | S0 | S1 | S2 | S3 | 说明 |
|---|---:|---:|---:|---:|---|
| 第 1 轮发现 | 0 | 2 | 2 | 1 | 发现 5 个问题，其中 4 个影响实施闭环或安全边界 |
| 第 1 轮修正后 | 0 | 0 | 0 | 0 | 已修正目标文档正文 |
| 第 2 轮复审 | 0 | 0 | 0 | 0 | 未发现新的阻塞问题 |

## 6. 主要问题与处理结果

| 编号 | 级别 | 问题 | 风险 | 处理结果 |
|---|---|---|---|---|
| DDR-001 | S1 | Handler 与 ResultSecurity 对最终 `answerText/summaryText` 的责任边界不一致 | Handler 可能基于未过滤 evidence 生成自然语言，绕过结果权限过滤 | 已修正。目标文档明确 Handler 只产出候选结果，最终答案和摘要由 `DocumentResultSecurityProjector` 基于过滤后 evidence 生成或确认 |
| DDR-002 | S1 | 默认启用策略与 `agent.document.enabled=false` 冲突 | 文档 capability 可能被静态加入默认 Profile/Policy，导致下游 ACL 未就绪时暴露能力 | 已修正。目标文档要求默认关闭，`DefaultAgentMetadataBootstrap` 按配置动态追加 capability/context，依赖缺失时 fail closed |
| DDR-003 | S2 | `DOCUMENT_RETRIEVABLE` 的 Domain Metadata 配置形态和 role limit 策略不够具体 | 实施时可能被现有非 `QUERYABLE` 分支误判为 aggregate，导致 page size、sort fields 和 projection 错误 | 已修正。目标文档补充 company_policy 示例配置、字段白名单、sort/operator、`AdapterRoleLimitPolicy` 和测试要求 |
| DDR-004 | S2 | 下游 `DocumentSearchClient` HTTP 契约粒度不足 | Adapter 对 URI、Header、请求体、错误映射理解不一致，可能泄漏 body 或错误降级 | 已修正。目标文档补充 `POST /es/indexes/{index}/search` 与 `/vector-search` 的请求、响应和错误映射 |
| DDR-005 | S3 | 部分章节仍使用“默认项”“摘要投影”等旧措辞 | 读者可能误解 Profile/Policy 默认打开或只保护摘要不保护答案 | 已修正为“可配置启用项”和“答案/摘要投影” |

## 7. 架构一致性评审

| 维度 | 结论 | 依据 |
|---|---|---|
| capabilityId 与 planKind | 通过 | 文档保持 `document.search`、`document.answer`、`document.summarize` 为 capability 主键，`DOCUMENT` 仅作为 Plan 结构类型 |
| Runtime 边界 | 通过 | Runtime 只产出 `DocumentAgentPlan`，不生成答案、摘要、citation、ES DSL、权限表达式 |
| ExecutionCore 侵入 | 通过 | 文档要求新增 Registration、Validator、Handler、Adapter、Projector，不修改核心执行算法 |
| ResultSecurity 边界 | 通过 | 最终自然语言输出必须基于过滤后 evidence 生成或确认 |
| Context 最小化 | 通过 | Context 只保存 corpus、queryText、filters、topK、citationIds，不保存正文、snippet、权限表达式或 ES DSL |

## 8. 契约与接口评审

| 维度 | 结论 |
|---|---|
| Java 契约源 | 通过，新增 DTO、sealed union、OpenAPI、generated model 的生成链路完整 |
| Chat API 兼容 | 通过，不新增 `AgentChatResponse` 顶层字段，通过 `resultKind=DOCUMENT` 扩展 |
| Adapter SPI | 通过，新增 `DocumentRetrievableAdapter` 不影响 `QueryableAdapter`、`AggregatableAdapter` |
| 下游 HTTP | 通过，已补充 URI、Header、Body、响应映射和错误映射 |
| UI 契约 | 通过，要求渲染 summary、answer、citations 和空证据状态 |

## 9. 权限与安全评审

| 维度 | 结论 |
|---|---|
| capability/domain/field 权限 | 通过，由 Profile、Policy、Permission、Domain projection 和 Execution 当前复检共同收紧 |
| documentId 级 ACL | 有条件通过，ACL 权威源在下游文档服务；Agent 侧不持有 ACL 表达式 |
| 自然语言越权 | 通过，最终 answer/summary 只由 ResultSecurity 基于过滤后证据生成或确认 |
| 日志与审计 | 通过，禁止记录 snippet、answerText、summaryText、Token、ACL 表达式、ES DSL、query vector 全文 |
| 默认启用 | 通过，默认关闭且依赖缺失 fail closed |

## 10. 数据、状态与一致性评审

| 维度 | 结论 |
|---|---|
| Agent 数据表 | 通过，首版不新增 Agent 业务表 |
| 下游索引字段 | 通过，已列出 `corpusId/documentId/chunkId/title/sourceUri/aclRef/contentSnippet/embedding` 等要求 |
| 幂等 | 通过，检索为只读，ResultSecurity 同输入确定输出，Context 写入复用既有审批 |
| 事务边界 | 通过，不扩大 Agent 本地事务，结果和 Context 仍由 Invocation 生命周期终结 |
| Deadline/取消 | 通过，要求下游调用服从 Invocation absolute deadline，迟到结果不得提交 |

## 11. 可实施性评审

| 模块 | 结论 |
|---|---|
| `agent-api` | 可实施，契约、结果、Context DTO 和生成物路径明确 |
| `agent-service` | 可实施，Registration、Validator、Handler、ResultSecurity、配置和 metadata 改造点明确 |
| `agent-adapter-api` | 可实施，新增 AdapterRole 与 Document Adapter SPI 明确 |
| `agent-adapter-document` | 可实施，但下游 ACL 和向量输入来源需联调前确认 |
| `agent-runtime` | 可实施，新增 `document_system.md`，Route 继续 descriptor-driven |
| UI | 可实施，`agent.html` 渲染分支和字段明确 |

## 12. 测试评审

| 测试层级 | 结论 |
|---|---|
| 契约测试 | 已要求覆盖 `DOCUMENT` discriminator、fixture、OpenAPI、generated model |
| Runtime 测试 | 已要求覆盖 document planning、prompt contract、contract drift |
| Kernel 测试 | 已要求覆盖 Validator、Handler、Capability extension |
| ResultSecurity 测试 | 已要求覆盖过滤无权字段、删除无引用句、基于过滤后 evidence 生成最终文本 |
| Metadata 测试 | 已要求覆盖 `DOCUMENT_RETRIEVABLE` role、role limit kind、默认关闭和依赖缺失 fail closed |
| Adapter 测试 | 已要求覆盖下游异常不泄漏 body、ACL 不可用 fail closed |

## 13. 剩余风险

| 编号 | 风险 | 等级 | 是否阻塞编码 | 阻塞点 |
|---|---|---|---:|---|
| R1 | 下游文档服务 documentId 级 ACL 过滤未在当前 Agent 代码中验证 | 高 | 否 | 阻塞联调、灰度和生产启用 |
| R2 | queryText 到 queryVector 的输入来源未确认 | 中 | 否 | 阻塞 vector channel 启用，不阻塞关键词检索 |
| R3 | 现有 `DomainMetadataPortImpl` 二分 max size 逻辑需要代码改造 | 中 | 否 | 需按 L2 实施并测试 |
| R4 | Route Prompt 仍需从硬编码 query/aggregate 规则收敛为 descriptor-driven | 中 | 否 | 需按 L2 实施并测试 |
| R5 | Abstractive LLM 总结不在首版 Agent 边界内 | 中 | 否 | 如纳入范围需另起 L1/ADR |
| R6 | P1 D05 品审报告引用未在仓库发现 | 低 | 否 | 正式评审时补齐或删除引用 |

## 14. 评审-修正循环记录

| 轮次 | 动作 | 结论 | 修改目标文档 | 修改关联文档 |
|---:|---|---|---:|---:|
| 1 | 审查目标文档与 L0/L1 约束 | 发现 2 个 S1、2 个 S2、1 个 S3 | 是 | 否 |
| 1 | 修正目标文档 | 修复 ResultSecurity、默认启用、metadata、下游 HTTP 契约和措辞问题 | 是 | 否 |
| 2 | 复审修正后目标文档 | 未发现 S0/S1；剩余为已记录风险 | 否 | 否 |

## 15. 建议处理

1. 进入 Agent 侧编码前，按目标文档第 19、20 章拆分实施任务和最小验证命令。
2. 编码阶段保持 `agent.document.enabled=false` 默认值，用 mock/stub 完成 Agent 内部闭环。
3. 联调前确认下游文档 ACL、索引字段和 queryVector 来源。
4. 若要纳入文档录入、索引构建、文档权限权威源或 abstractive LLM 总结，应另行授权并先补 L1/ADR。
