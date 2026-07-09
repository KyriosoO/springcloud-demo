# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 依据文档数量 | 1 |
| 评审代码范围 | `agent-api/**`、`agent-adapter-api/**`、`agent-service/**`、`agent-adapter-document/**`、`es-query-api/**`、`es-query-service/**`、`**/*.sql`、`pom.xml`、`*/pom.xml` |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 通过 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `docs/design/P2_V2/02_资料域资料类型Profile配置能力_L2实施详细设计_v2.0.md` | detailed_design | 1 | 是 | 已读取 | Approved，可作为实现依据 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | 02 详设第 4、6、8 章 | Domain Metadata 是字段事实源，profile 只承载检索策略，不下放 Runtime 权威 | `AgentProperties`、`AgentPropertiesValidator`、`DocumentPlanValidator` | 符合 |
| DOC-C-002 | 02 详设第 10、11、12 章 | profile 配置支持 `domain + materialTypes + retrievalProfile + indexAlias + channels + weights + RRF + dedup + rerank` | `AgentProperties.RetrievalProfileProperties` | 符合 |
| DOC-C-003 | 02 详设第 10.1、10.2、12 章 | `profileVersion` 不人工配置，由 Java 派生并写入冻结快照 | `DocumentRetrievalProfileResolver`、`DocumentRetrievalProfile` | 符合 |
| DOC-C-004 | 02 详设第 10.2、13、17 章 | profile 解析必须 fail closed；显式 profile 要求 domain 匹配，materialType 要求在 allowlist 内 | `DocumentRetrievalProfileResolver` | 符合 |
| DOC-C-005 | 02 详设第 10.3、19、20 章 | 启动校验 profile、domain、materialTypes、indexAlias、通道、参数上限和 rerank 配置 | `AgentPropertiesValidator` | 符合 |
| DOC-C-006 | 02 详设第 19、20 章 | `DocumentPlanValidator` 将 profile snapshot 注入 `DocumentRetrievalRequest` | `DocumentPlanValidatorTest` | 符合 |
| DOC-C-007 | 02 详设第 20 章 | 契约测试覆盖 `DocumentRetrievalOptions` 可选字段兼容 | `agent-runtime-openapi.json`、OpenAPI 契约测试 | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 建议处理 |
|---|---|---|---|---|---|---|---|
| CR-001 | high | implementation_completeness | `AgentProperties.java` | DOC-C-002、DOC-C-003 | profile 配置仍使用单值 `materialType`，且保留人工配置 `profileVersion` | 无法表达一个 profile 绑定多个资料类型，且破坏 Java 派生版本规则 | 改为 `materialTypes`，移除人工配置版本字段 |
| CR-002 | high | functional_correctness | `DocumentRetrievalProfileResolver.java` | DOC-C-004 | 无 profile 时回退 legacy 默认值，空资料类型配置可近似通配，显式 profile/materialType 边界不够强 | 配置缺失不会 fail closed，可能路由到非预期 profile | 去除 legacy fallback，严格按 domain、materialTypes、requestedProfile 解析 |
| CR-003 | medium | design_consistency | `AgentPropertiesValidator.java` | DOC-C-005 | 启动校验缺少 materialTypes、重复 domain/materialType、参数上限、domain role 校验 | 错误 profile 可能到运行期才失败 | 补充启动 fail-closed 校验 |
| CR-004 | medium | test_coverage | `DocumentRetrievalProfileResolverTest.java`、`DocumentPlanValidatorTest.java`、`AgentPropertiesValidatorTest.java` | DOC-C-004、DOC-C-005、DOC-C-006 | 缺少 resolver 单测和新 profile 配置失败路径覆盖 | 关键路由规则易回退 | 新增/更新单元测试 |
| CR-005 | medium | api_contract_consistency | `agent-runtime-openapi.json` | DOC-C-007 | Active Runtime OpenAPI 快照未包含当前 `DocumentRetrievalOptions` 中的 profile 字段 | 六模块测试失败，Runtime 契约快照与代码不一致 | 通过显式更新参数重新生成契约快照 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| 无 | - | - | - | 未发现阻断性文档问题 | - | - |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | `AgentProperties.java` | 将 profile 配置从单值 `materialType` 升级为 `materialTypes`，移除人工配置 `profileVersion` | CR-001 | 已修复 |
| 1 | `DocumentRetrievalProfileResolver.java` | 严格解析 domain/materialType/profile，去除 legacy fallback，基于 profile 内容摘要派生 `profileVersion` | CR-002 | 已修复 |
| 1 | `AgentPropertiesValidator.java` | 增加 materialTypes、重复路由、domain role、通道权重、候选数、RRF、dedup、rerank 上限校验 | CR-003 | 已修复 |
| 1 | `DocumentRetrievalProfileResolverTest.java`、`DocumentPlanValidatorTest.java`、`AgentPropertiesValidatorTest.java` | 新增 resolver 测试并更新 profile snapshot、启动校验测试 | CR-004 | 已修复 |
| 2 | `agent-runtime-openapi.json` | 显式同步 Active Runtime OpenAPI 契约快照 | CR-005 | 已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `mvn -pl ../agent-service test "-Dtest=DocumentRetrievalProfileResolverTest,DocumentPlanValidatorTest,AgentPropertiesValidatorTest"` | 失败 | 单独编译 `agent-service` 时使用本地仓库旧版上游 artifact，缺少当前工作区 DTO；改用 reactor `-am` 处理 |
| 1 | `mvn -pl ../agent-service -am test "-Dtest=DocumentRetrievalProfileResolverTest,DocumentPlanValidatorTest,AgentPropertiesValidatorTest" "-DfailIfNoTests=false" "-Dsurefire.failIfNoSpecifiedTests=false"` | 通过 | 相关 42 个测试通过 |
| 1 | `mvn -pl ../agent-api,../agent-adapter-api,../agent-service,../agent-adapter-document,../es-query-api,../es-query-service -DskipTests compile` | 通过 | 六模块编译通过 |
| 1 | `mvn -pl ../agent-api,../agent-adapter-api,../agent-service,../agent-adapter-document,../es-query-api,../es-query-service test` | 失败 | 首次失败于 `agent-api` Active Runtime OpenAPI drift，属于契约快照未同步 |
| 2 | `mvn -pl ../agent-api test "-Dtest=AgentRuntimeContractOpenApiGenerationTest#shouldMatchCommittedActiveArtifact" "-Dagent.contract.update=true"` | 通过 | 契约快照已显式更新 |
| 2 | `mvn -pl ../agent-api,../agent-adapter-api,../agent-service,../agent-adapter-document,../es-query-api,../es-query-service test` | 通过 | 六模块 598 个测试通过 |
| 2 | `git diff --check` | 通过 | 未发现 whitespace error；PowerShell 输出 CRLF/LF 提示，不影响检查结果 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | low | 直接升级会拒绝旧 `agent.document.retrieval-profiles.*.material-type` 配置 | 本轮按用户确认选择不保留旧配置兼容 | 部署前同步配置仓库为 `material-types` |
| RISK-002 | low | `profileVersion` 当前使用内容摘要，不包含外部配置中心 reload 序号 | 当前代码未提供统一 reload sequence 输入 | 后续若接入配置热更新事件，可将 reload sequence 纳入摘要输入 |

## 9. 结论

最终结论：
- 通过。

说明：
- 02 详设要求的资料域/资料类型 profile 配置、Java 派生 `profileVersion`、解析 fail-closed、启动校验和单次请求快照注入均已对齐。
- 本轮未修改设计文档本体，报告按技能规则落盘到同目录。
