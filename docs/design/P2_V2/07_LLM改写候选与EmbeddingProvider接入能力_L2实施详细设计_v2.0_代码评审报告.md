# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 依据文档数量 | 1 |
| 评审代码范围 | agent-api、agent-adapter-api、agent-service、agent-adapter-document、es-query-api、es-query-service、SQL、pom |
| 是否修改代码 | 是 |
| 验证结果 | 通过；根目录 `-pl` 命令因无 root pom 不适用，已执行等价模块级验证 |
| 最终结论 | 有剩余风险；Java 侧已对齐 07，agent-runtime endpoint 不在本轮 code_scope 内 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `docs/design/P2_V2/07_LLM改写候选与EmbeddingProvider接入能力_L2实施详细设计_v2.0.md` | detailed_design | 1 | 是 | 已读取 | 本轮主依据 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-071 | 8、10.2、15 | Runtime 只返回 rewrite candidates，不能返回 DSL/filter/indexAlias/profile/ACL/topK/sort | `RuntimeDocumentQueryRewriteClient`、`RewriteCandidateNormalizer` | 已修复 |
| DOC-C-072 | 10.1、19.1 | Java 侧规则抽取文号、日期、机关、税种等可信关键词 | `DocumentRuleExtractor`、`DocumentCapabilityHandler` | 已修复 |
| DOC-C-073 | 10.3 | Java 对 Runtime 候选做长度、字符、去重和禁止字段校验 | `RewriteCandidateNormalizer` | 已修复 |
| DOC-C-074 | 10.4、11.3 | EmbeddingProvider 接收 normalized query variants、provider/model/timeout，并校验维度和模型 | `DocumentEmbeddingRequest`、`HttpDocumentEmbeddingClient`、`DocumentCapabilityHandler` | 已修复 |
| DOC-C-075 | 7、10.4 | profile 绑定 embeddingField/provider/model/dims | `RetrievalProfileProperties`、`DocumentRetrievalProfileResolver`、`DocumentHybridOptions` | 已修复 |
| DOC-C-076 | 6、8、15 | LLM/Embedding 失败不影响 BM25/exact/phrase，权限和 ACL 不下放给 provider | `DocumentCapabilityHandler`、rewrite/embedding tests | 已修复 |
| DOC-C-077 | 19.2 | Runtime Python 侧 document rewrite endpoint | `agent-runtime/**` | 未验证；本轮 code_scope 未包含 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|---|
| CR-071 | high | implementation_completeness | `DocumentCapabilityHandler.java` | DOC-C-071~073 | 执行前未构建 Java 可信 ruleKeywords 和 Runtime rewriteCandidates，检索请求中的两类字段为空 | exact/phrase 召回无法利用规则关键词和安全改写候选 | 已修复 |
| CR-072 | high | security / architecture_boundary | 缺少 rewrite 端口与 client | DOC-C-071 | Runtime 改写边界没有 Java client 和禁止字段拒绝机制 | Runtime 输出可能被误当成可信执行信息 | 已修复 Java client；Runtime endpoint 剩余 |
| CR-073 | medium | api_contract_consistency | `DocumentEmbeddingRequest.java`、`HttpDocumentEmbeddingClient.java` | DOC-C-074 | Embedding 请求只传单一 queryText，未表达 query variants/provider/expected model/dims | 不支持多候选向量输入和请求级 fail-closed 校验 | 已修复 |
| CR-074 | medium | design_consistency | `DocumentHybridOptions.java`、`DocumentRetrievalProfileResolver.java` | DOC-C-075 | profile 只能冻结 embeddingField，无法承载 provider/model/dims | 多资料类型无法按 profile 使用不同向量模型和维度 | 已修复 |
| CR-075 | medium | test_coverage | 多处测试 | 20 | 缺少 rewrite 禁止字段、embedding dims mismatch、Handler 降级与 query variants 流转测试 | 安全边界和降级路径容易回归 | 已修复 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| 无 | - | - | - | 未发现阻断性文档问题 | - | - |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | `agent-service/src/main/java/com/dylan/agent/capability/document/rewrite/**` | 新增 rewrite 端口、禁用实现、Runtime client、DTO、normalizer、QueryVariants | CR-071、CR-072 | 已修复 |
| 1 | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentRuleExtractor.java` | 新增 Java 规则抽取，覆盖文号、日期、机关、税种关键词 | CR-071 | 已修复 |
| 1 | `DocumentCapabilityHandler.java` | 执行期构建 query variants，rewrite 失败降级，embedding 使用 query variants | CR-071、CR-076 | 已修复 |
| 1 | `DocumentEmbeddingRequest.java`、`HttpDocumentEmbeddingClient.java` | 增加 queryVariants/provider/expectedModel/expectedDimension，并在 client 内校验模型和维度 | CR-073 | 已修复 |
| 1 | `AgentProperties.java`、`AgentPropertiesValidator.java` | 增加 `agent.document.rewrite.*` 和 embedding provider 校验 | CR-072、CR-073 | 已修复 |
| 2 | `DocumentHybridOptions.java`、`DocumentRetrievalProfileResolver.java`、`AgentProperties.java` | profile 冻结 embedding provider/model/dimension，并进入 profileVersion 摘要 | CR-074 | 已修复 |
| 2 | 相关测试 | 新增/更新 rewrite、embedding、profile、Handler、配置校验测试 | CR-075 | 已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `mvn -pl agent-api,agent-adapter-api,agent-service,agent-adapter-document,es-query-api,es-query-service -DskipTests compile` | 不适用 | 当前仓库根目录无 root pom，Maven reactor 找不到模块 |
| 1 | `mvn -f agent-service/pom.xml "-Dtest=RewriteCandidateNormalizerTest,RuntimeDocumentQueryRewriteClientTest,HttpDocumentEmbeddingClientTest,DocumentCapabilityHandlerTest,AgentPropertiesValidatorTest" "-DfailIfNoTests=false" test` | 通过 | 44 tests，0 failures |
| 2 | `mvn -f agent-adapter-api/pom.xml -DskipTests install` | 通过 | 刷新本地 SNAPSHOT，供非聚合模块编译使用 |
| 2 | `mvn -f agent-service/pom.xml "-Dtest=DocumentRetrievalProfileResolverTest,RewriteCandidateNormalizerTest,RuntimeDocumentQueryRewriteClientTest,HttpDocumentEmbeddingClientTest,DocumentCapabilityHandlerTest,AgentPropertiesValidatorTest" "-DfailIfNoTests=false" test` | 通过 | 50 tests，0 failures |
| 2 | 模块级 compile loop：`agent-api`、`agent-adapter-api`、`agent-service`、`agent-adapter-document`、`es-query-api`、`es-query-service` | 通过 | 逐模块 `mvn -q -f <module>/pom.xml -DskipTests compile` |
| 2 | 模块级 test loop：同上 6 个模块 | 通过 | 逐模块 `mvn -q -f <module>/pom.xml test` |
| 2 | `git diff --check` | 通过 | 仅提示 `AgentProperties.java`、`AgentPropertiesValidator.java` 下次 Git 触碰时 CRLF 将替换为 LF |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-071 | medium | Runtime Python rewrite endpoint 尚未实现 | 本轮 code_scope 未包含 `agent-runtime/**`，仅完成 Java client 和契约拒绝逻辑 | 后续单独授权 `agent-runtime` 后实现 `/runtime/v1/document/rewrite` 并补契约测试 |
| RISK-072 | low | 生产配置未显式启用 rewrite | `config-service/**` 不在本轮 code_scope；当前 Java 默认关闭 rewrite | 灰度启用前补充 `agent.document.rewrite.*` 配置并联调 Runtime endpoint |
| RISK-073 | low | 非聚合仓库需要先安装本地 SNAPSHOT | 根目录无 root pom，公共 contract 变更后 `agent-service` 需使用最新 `agent-adapter-api` | 后续可使用已有聚合入口或先执行 `agent-adapter-api install` |

## 9. 结论

最终结论：
- Java 侧通过，仍有 Runtime endpoint 剩余风险。

说明：
- 已完成 07 详设在授权代码范围内的 Java 统一边界、rewrite 候选归一化、profile 级 embedding 配置、EmbeddingProvider 请求级校验和降级路径。
- 未修改设计文档本体，未 commit，未 push，未创建 PR。
