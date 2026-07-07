# 07 LLM 与 EmbeddingProvider 接入能力代码评审报告

## 1. 执行摘要

| 项目 | 结果 |
| --- | --- |
| 目标设计文档 | `docs/design/P2/07_LLM与EmbeddingProvider接入能力_L2实施详细设计_v1.0.md` |
| 执行模式 | review_and_fix |
| 最大轮次 | 5 |
| 实际轮次 | 1 |
| 停止原因 | 修复并复审后未发现新的可自动修复问题 |
| 结论 | Provider 默认禁用、启用配置校验、服务 token scope、requestId/model/deadline 传递、Evidence 安全打包和 model/dimension fail closed 基本符合 P2 07；本轮修复 provider HTTP 异常链可能泄漏原始响应体的问题。 |

## 2. 文档依据与追踪关系

| 依据 | 关键约束 | 代码落点 | 评审结论 |
| --- | --- | --- | --- |
| P2 07 第 8、10.6、15 章 | Provider 默认禁用；启用时只使用服务 token，不转发用户 JWT；缺 scope fail closed | `AgentProperties`、`AgentPropertiesValidator`、`DocumentProviderSecurityValidator`、`DocumentProviderAuthHeaderProvider`、`application.yml` | 已满足 |
| P2 07 第 10.2、10.3、12、13 章 | Embedding 请求携带 requestId/model/deadline；返回向量有限数值、模型和维度不匹配 fail closed | `DocumentEmbeddingRequest`、`HttpDocumentEmbeddingClient`、`DocumentCapabilityHandler` | 已满足 |
| P2 07 第 10.4、10.5、12、13 章 | Generation 请求携带 requestId/model/deadline；输出为候选并经引用校验 | `DocumentGenerationRequest`、`HttpDocumentGenerationClient`、`DocumentCapabilityHandler`、`DocumentCitationVerifier` | 已满足 |
| P2 07 第 10.8 章 | deadline 调用前后校验，迟到响应丢弃 | `HttpDocumentEmbeddingClient`、`HttpDocumentGenerationClient`、`DocumentCapabilityHandler` | 基本满足；动态缩短网络 read timeout 未验证 |
| P2 07 第 10.9、15、18 章 | 异常和日志不得包含 Authorization、token、原始响应 body、完整 evidence、queryVector | `HttpDocumentEmbeddingClient`、`HttpDocumentGenerationClient`、`DocumentEvidenceContextPacker`、相关测试 | 已修复异常链泄漏风险 |
| P1 统一密钥管理 | 服务 token 和配置脱敏复用公共安全能力 | `common-security`、`DocumentProviderAuthHeaderProvider` | 已对齐，未新增 vendor API key 密钥用途 |
| D01 契约治理 | provider 内部 HTTP API 不进入 Runtime 公共 OpenAPI | agent-service 内部 DTO/HTTP client | 已对齐 |

## 3. 问题表

| ID | 级别 | 状态 | 问题 | 依据 | 修改 |
| --- | --- | --- | --- | --- | --- |
| CR-P2-07-001 | High | 已修复 | `HttpDocumentEmbeddingClient` 和 `HttpDocumentGenerationClient` 捕获 provider 调用异常时把原始 `RestClientException` 作为 cause 挂出。若上层记录完整异常栈，Spring 异常可能携带 provider 原始响应体，进而泄漏 evidence、token 或 queryVector。 | P2 07 第 10.3、10.5、10.9、15 章要求 provider 异常脱敏且不得包含原始响应 body/token/evidence。 | 改为抛固定脱敏 `IllegalStateException`，不保留原始 cause；补充测试断言 `hasNoCause()`。 |

## 4. 修改摘要

| 文件 | 修改内容 |
| --- | --- |
| `agent-service/src/main/java/com/dylan/agent/capability/document/embedding/HttpDocumentEmbeddingClient.java` | provider 调用失败时不再携带原始 cause，只返回固定脱敏异常消息。 |
| `agent-service/src/main/java/com/dylan/agent/capability/document/generation/HttpDocumentGenerationClient.java` | provider 调用失败时不再携带原始 cause，只返回固定脱敏异常消息。 |
| `agent-service/src/test/java/com/dylan/agent/capability/document/embedding/HttpDocumentEmbeddingClientTest.java` | 补充失败路径断言，确保异常 cause 为空，避免响应体通过异常链泄漏。 |
| `agent-service/src/test/java/com/dylan/agent/capability/document/generation/HttpDocumentGenerationClientTest.java` | 补充失败路径和 deadline 失败断言，确保异常 cause 为空。 |

## 5. 验证结果

| 命令 | 工作目录 | 结果 |
| --- | --- | --- |
| `mvn -pl ../agent-service -am "-Dtest=HttpDocumentEmbeddingClientTest,HttpDocumentGenerationClientTest,DocumentProviderAuthHeaderProviderTest,DocumentProviderSecurityValidatorTest,AgentPropertiesValidatorTest" "-Dsurefire.failIfNoSpecifiedTests=false" test` | `D:\codex\serviceCenter` | 通过；17 tests，0 failures，0 errors |
| `mvn -q -DskipTests compile` | `D:\codex\serviceCenter` | 通过 |
| `mvn test` | `D:\codex\serviceCenter` | 通过；Reactor 28 个模块成功，agent-service 428 tests，0 failures，0 errors |
| `git diff --check` | `D:\codex` | 通过 |

## 6. 未验证项与剩余风险

| 风险 | 说明 | 建议 |
| --- | --- | --- |
| 真实 provider 服务契约未联调 | 本轮使用 mock HTTP server 验证 agent-service 请求头、body 和脱敏异常；未连接真实 embedding/generation provider。 | 上线前补充 mock provider 端到端或契约测试，覆盖非 2xx、超时、空 body、model/dimension mismatch。 |
| 网络 read timeout 未动态缩短到剩余 deadline | 当前实现执行调用前/调用后 deadline 校验并传递 `X-Agent-Deadline`，但 RestClient read timeout 是配置级上限；如果 provider 忽略 deadline 且外层剩余预算小于配置 timeout，线程可能等到配置 read timeout 后才失败。 | 后续如要求强 deadline 网络上限，需要引入 per-request timeout factory 或在剩余预算不足时提前 fail closed。 |
| Provider 指标/告警未闭环 | P2 07 设计了调用数、失败率、model mismatch、dimension mismatch、fallback/refuse 等观测项；本轮只验证日志/异常脱敏和功能契约。 | P2 08 或生产门禁阶段补齐 Micrometer 指标和告警验证。 |
| 外部 vendor API key 不在本轮范围 | P2 07 明确首版只接内部 provider 服务 token；未设计或验证外部厂商 API key、Vault/KMS SDK、供应商 SDK。 | 如需直连外部厂商，先补 P1 密钥用途和 vendor credential 设计，再编码。 |
