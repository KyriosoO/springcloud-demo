# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：否
- 审查类型：auto，识别为详细设计文档，并执行跨层级一致性核验
- 目标文档：`docs/design/P2/07_LLM与EmbeddingProvider接入能力_L2实施详细设计_v1.0.md`
- 关联文档：L1 架构设计文档、`docs/design/P1` 下现存全部 L2 详细设计文档、P2 下编号小于 07 的 00/01/02/03/04/05/06 详设及对应品审报告、当前仓库相关 Java 契约与实现骨架
- 实际审查轮次：2
- 主要风险摘要：初审发现 9 个 S1 和 3 个 S2。S1 集中在 P2 前序基线不完整、provider 内部 HTTP 契约不完整、Java 字段与文档不一致、provider 认证和密钥边界不清、model/dimension 启动门禁不足、deadline/header/迟到响应控制不足、敏感日志和 provider 输入安全不足、08 生产发布门禁混淆、测试无法直接指导编码；S2 为状态命名容易误解为公共枚举、外部 vendor API key 边界不清、配置校验职责落点不够精确。目标文档已修复，复审未发现遗留 S0/S1。

## 2. 文档识别结果

- 识别文档类型：详细设计文档
- 识别依据：文档标题为 L2 实施详细设计，包含实现落点清单、测试设计、API/契约、数据模型、状态流转、风险与完成摘要。
- 文档状态：Draft
- 是否包含修订历史：是，已追加 2026-07-07 品审修订记录。
- 是否存在上级文档：是，目标文档引用 4 份 L1 架构设计文档。
- 是否存在关联文档缺失：否。修订后已覆盖 P1 L2 关联文档集合，以及 P2 下编号小于 07 的 00/01/02/03/04/05/06 详设和品审报告。

## 3. 审查范围

| 序号 | 文档 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---|---|
| 1 | `docs/design/P2/07_LLM与EmbeddingProvider接入能力_L2实施详细设计_v1.0.md` | 目标文档 | 是 | 本次品审与修订对象 |
| 2 | `docs/design/Agent目标架构总览_v1.0.md` | L1 上级文档 | 是，关键约束核验 | 核验 Agent 总体边界 |
| 3 | `docs/design/Agent能力执行内核架构设计_v1.0.md` | L1 上级文档 | 是，关键约束核验 | 核验 Handler/Adapter/Core/ResultSecurity/deadline 边界 |
| 4 | `docs/design/Agent契约与规划架构设计_v1.0.md` | L1 上级文档 | 是，关键约束核验 | 核验 Java 契约源、Runtime 不可信和公共 OpenAPI 边界 |
| 5 | `docs/design/Agent元数据与上下文安全架构设计_v1.0.md` | L1 上级文档 | 是，关键约束核验 | 核验权限、Context、ResultSecurity 和凭据不外传边界 |
| 6 | `docs/design/P1` 下现存全部 L2 详细设计文档 | P1 关联文档 | 是，目录与关键约束核验 | 核验 D01-D05、统一密钥、ResultSecurity、安全专项和主链门禁 |
| 7 | `docs/design/P2/00_*` 详设及品审报告 | P2 前置文档 | 是 | 核验能力路线图和进入编码门禁 |
| 8 | `docs/design/P2/01_*` 详设及品审报告 | P2 前置文档 | 是 | 核验 chunk schema、embedding/model/dimension 与 alias validation 风险 |
| 9 | `docs/design/P2/02_*` 详设及品审报告 | P2 前置文档 | 是 | 核验 domain metadata、证据字段和 adapter registration |
| 10 | `docs/design/P2/03_*` 详设及品审报告 | P2 前置文档 | 是 | 核验 ACL scope/filter、fail closed 和 ResultSecurity 继承 |
| 11 | `docs/design/P2/04_*` 详设及品审报告 | P2 前置文档 | 是 | 核验 VECTOR/HYBRID、dimension mismatch、metadata 安全和降级诊断 |
| 12 | `docs/design/P2/05_*` 详设及品审报告 | P2 前置文档 | 是 | 核验 `citationBindings`、evidence package、inline citation 和 provider 输入安全 |
| 13 | `docs/design/P2/06_*` 详设及品审报告 | P2 前置文档 | 是 | 核验摘要 generation、fallback/refuse、coverage 和 provider 生产门禁 |
| 14 | `agent-api`、`agent-service`、`common-security` 相关 Java 类 | 仓库契约/代码结构 | 是，关键文件核验 | 核验 DTO、HTTP client、配置、服务 token、validator、handler 和测试落点 |

## 4. S0 阻断问题

未发现 S0 阻断问题。

## 5. S1 严重问题

| 序号 | 位置 | 问题 | 风险 | 修改建议 |
|---:|---|---|---|---|
| 1 | 第 1、7 章 | 关联文档只显式写到 P2 06，未完整覆盖 P2 下编号小于 07 的 00-06 详设及品审报告 | 后续实现可能漏掉 01 model/dimension、03 ACL、04 VECTOR/HYBRID、05/06 generation 安全结论 | 已补齐 P2 00-06 详设及品审报告，并保留 P1 L2 集合边界 |
| 2 | 第 10、11 章 | Provider HTTP API 只笼统描述 RestClient，未明确 `/embeddings`、`/document-generation` 的 headers、body、response 和错误处理 | 无法直接编码或编写 contract/mock 测试 | 已补充内部 HTTP 契约、request/response 字段、header、deadline 和异常脱敏规则 |
| 3 | 第 10、11、12、19 章 | 文档字段与当前 Java 不一致：embedding 误称 `invocationId`，generation 误写 `citationIds` | 后续会实现错误 DTO 或 provider 响应字段，导致编译/契约漂移 | 已改为 `DocumentEmbeddingRequest.requestId` 和 `DocumentGenerationResult.citationBindings` |
| 4 | 第 10.4、10.5、11、12、19 章 | Generation 请求缺少 requestId/model 传递设计 | HTTP client 无法写 `X-Agent-Request-Id`，provider 可能使用隐式默认模型 | 已要求 `DocumentGenerationRequest` 补充 `requestId` 与 `model` |
| 5 | 第 6、8、10.6、15、19、20、21 章 | provider 认证和 P1 密钥边界不清，仅写“统一密钥注入” | 可能转发用户 JWT，或把外部厂商 API key 偷偷塞进 JWT/payload secret purpose | 已明确首版只支持内部 provider + `ServiceTokenProvider`，新增 `DocumentProviderAuthHeaderProvider` 与 scope 门禁；外部 vendor key 另行授权 |
| 6 | 第 8、10.2、10.4、14、20、21、23 章 | model 只写“建议必填”，dimension/model 与索引一致性门禁不足 | provider 默认模型变化或索引维度不匹配会污染 VECTOR/HYBRID 结果 | 已改为 enabled=true 时 model 必填，返回模型和维度必须校验，不一致 fail closed |
| 7 | 第 8、10.8、13、19、20、23 章 | deadline/header/迟到响应处理不足 | provider 调用可能超出 invocation 生命周期，迟到结果覆盖终态 | 已补充调用前 deadline 检查、header/body 传递、迟到响应丢弃和测试 |
| 8 | 第 10.9、15、18、19、20、21 章 | 日志脱敏和 provider 输入安全边界不足 | evidence、queryVector、Authorization、sourceUri token 或 ACL 字段可能进入日志/provider | 已补充禁止记录项、safe evidence 输入、异常脱敏和测试门禁 |
| 9 | 第 1、3、7、17、21、24 章 | 07 本地编码闭环与 08 生产发布门禁混淆 | 可能在未完成回滚、审计、撤权验证前宣称真实 provider 可生产 | 已将 08 定位为后续生产发布依赖，07 只承担本地接入与 contract/mock 闭环 |

以上 S1 均已在目标文档中修复，复审未发现遗留 S1。

## 6. S2 一般问题

| 序号 | 位置 | 问题 | 风险 | 修改建议 |
|---:|---|---|---|---|
| 1 | 第 13 章 | `PROVIDER_DISABLED`、`GENERATION_SUCCEEDED` 等状态容易被误解为新增公共 enum | 可能导致实现新增错误状态或与 `DocumentGenerationStatus` 冲突 | 已改为内部日志/指标状态，并明确 generation 用户可见状态仍用现有 enum |
| 2 | 第 19、20 章 | 服务 token scope 校验职责落点不够具体 | `AgentPropertiesValidator` 本身不读取 `ServiceTokenProperties`，实现会出现职责不清 | 已新增 `DocumentProviderSecurityValidator` 落点和测试 |
| 3 | 第 20 章 | 集成测试路径写成“新增”，缺少 provider auth、脱敏、deadline、model 断言 | 测试无法覆盖主要 provider 风险 | 已补齐具体测试类、路径和核心断言 |

以上 S2 均已修复。

## 7. S3 建议优化

暂无 S3 建议优化。

## 8. 架构设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 架构目标 | 不适用 | 目标文档为 L2 详细设计，不重新定义 L1 架构目标 |
| 系统边界 | 通过 | 修订后 provider 是 document capability 内部依赖，不成为新 domain 或权限事实源 |
| 模块职责 | 通过 | Handler 编排，HTTP client 调 provider，Verifier/Projector 做最终安全，ServiceTokenProvider 负责内部认证 |
| 依赖方向 | 通过 | 保持 Java 契约源、Runtime/provider 不可信、ResultSecurity 后置收口 |
| 技术选型 | 通过 | 复用现有 RestClient、ServiceTokenProvider、document port 和 Java record |
| 一致性模型 | 通过 | provider 不写数据库，model/dimension 与索引一致性作为生产门禁 |
| 幂等与补偿 | 通过 | provider 失败通过 fail closed、降级、fallback/refuse 处理 |
| 权限与审计 | 通过 | 不转发用户 JWT，不发送权限表达式，日志不记录 token/evidence/vector |
| 非功能需求 | 通过 | 补充 timeout、deadline、异常脱敏、指标和告警 |
| 风险与取舍 | 通过 | 外部 vendor API key 明确为需另行授权的扩展，不污染首版范围 |

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | 已承接 L1、P1、P2 00-06 约束 |
| 文件路径 | 通过 | 实现和测试路径已具体到模块/类 |
| 类与方法 | 通过 | 已列出 Properties、Validator、Configuration、AuthHeaderProvider、HTTP Client、Handler、DTO |
| 入参与返回类型 | 通过 | request/response 字段已对齐当前 Java，并明确 requestId/model 待补 |
| 接口契约 | 通过 | 内部 provider HTTP API 已明确，公共 OpenAPI 边界清楚 |
| 数据结构 | 通过 | `DocumentEmbeddingRequest/Result`、`DocumentGenerationRequest/Result`、`CitationBinding` 已明确 |
| 校验逻辑 | 通过 | enabled 配置、model、dimension、scope、deadline、response body 均有校验要求 |
| 异常处理 | 通过 | 非 2xx、空 body、timeout、模型/维度不匹配、invalid citation 均覆盖 |
| 状态流转 | 通过 | provider 内部状态与 `DocumentGenerationStatus` 分层清楚 |
| 数据库设计 | 不适用 | 本文不新增数据库结构 |
| 缓存与消息 | 不适用 | 本文不新增缓存或消息机制 |
| 权限、审计、幂等、风控 | 通过 | 服务 token、scope、日志脱敏、model/dimension、deadline 均覆盖 |
| 测试设计 | 通过 | 已补充 validator、auth、HTTP client、handler、contract/mock 和脱敏测试 |
| 可编码性 | 通过 | 可进入 07 本地编码与测试闭环 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 支撑文档检索、回答、摘要所需 embedding/generation provider 接入 |
| 架构到详细设计一致性 | 通过 | 未改变 L1 的 Java 契约源、Runtime/provider 不可信、ResultSecurity 边界 |
| 接口契约一致性 | 通过 | provider 内部契约不进入公共 OpenAPI；如公开需走 D01 |
| 代码结构一致性 | 通过 | 目标类与当前仓库结构一致，新增类位置明确 |
| 权限与审计一致性 | 通过 | 复用服务 token，不转发用户 JWT，不泄漏 token/evidence/vector |
| 一致性模型一致性 | 通过 | provider 不写库，失败由本次 invocation 内处理 |
| 风控策略一致性 | 通过 | VECTOR fail closed、HYBRID 降级、generation fallback/refuse、08 生产门禁明确 |
| 测试范围一致性 | 通过 | 测试清单覆盖主要安全、契约、配置和失败路径 |

## 11. 是否建议进入后续阶段

- 是否建议进入详细设计：已处于详细设计阶段
- 是否建议进入编码实现：是，建议进入 07 本地编码与测试闭环
- 是否建议先修订架构设计：否
- 是否建议先修订详细设计：否，当前修订后已满足进入编码条件
- 是否需要用户确认：暂无；若要直接接外部 vendor API key、修改 P1 密钥用途、公开 provider OpenAPI、扩大到 08 生产发布门禁或修改上级文档，需要另行授权

## 12. 用户确认项

暂无需要用户确认的问题。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 建议修改内容 | 是否阻断 |
|---:|---|---|---|---|
| 1 | S1 | 第 1、7 章 | 补齐 P2 00-06 详设及对应品审报告作为关联基线 | 是，已修复 |
| 2 | S1 | 第 10、11 章 | 补全 provider 内部 HTTP 契约 | 是，已修复 |
| 3 | S1 | 第 10、11、12、19 章 | 字段对齐 `requestId` 与 `citationBindings` | 是，已修复 |
| 4 | S1 | 第 10.4、10.5、11、12、19 章 | `DocumentGenerationRequest` 补充 requestId/model | 是，已修复 |
| 5 | S1 | 第 6、8、10.6、15、19、20、21 章 | 明确服务 token 认证和外部 vendor key 边界 | 是，已修复 |
| 6 | S1 | 第 8、10.2、10.4、14、20、21、23 章 | model/dimension 启动和响应校验 | 是，已修复 |
| 7 | S1 | 第 8、10.8、13、19、20、23 章 | 补充 deadline/header/迟到响应处理 | 是，已修复 |
| 8 | S1 | 第 10.9、15、18、19、20、21 章 | 补充日志脱敏和 provider 输入安全 | 是，已修复 |
| 9 | S1 | 第 1、3、7、17、21、24 章 | 区分 07 本地闭环与 08 生产发布门禁 | 是，已修复 |
| 10 | S2 | 第 13 章 | provider 状态改为内部日志/指标状态 | 否，已修复 |
| 11 | S2 | 第 19、20 章 | 新增 `DocumentProviderSecurityValidator` 落点 | 否，已修复 |
| 12 | S2 | 第 20 章 | 补全测试路径和断言 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-07 | 初审 | 12 | 0 | 9 个 S1，3 个 S2 |
| 2 | 2026-07-07 | 修正与复审 | 0 | 12 | 无 S0/S1/S2 遗留 |

## 15. 最终结论

目标文档通过品审，不阻断后续编码。修订后，07 已能作为 LLM / Embedding Provider 接入能力的本地编码依据；真实 provider 的生产发布、回滚、审计、撤权验证仍必须等待 08 门禁闭合。下一步建议按第 19、20 章进入代码实现与最小相关测试闭环。
