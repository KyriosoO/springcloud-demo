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
| 最终结论 | 通过，存在集成级剩余风险 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `docs/design/P2_V2/08_gold_query验证回滚审计观测与撤权保障能力_L2实施详细设计_v2.0.md` | detailed_design | 1 | 是 | 已读取 | 文档状态为 Approved，可作为实现依据 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-081 | 08 第 8、10、11、14 章 | alias 切换前必须通过 schema、ACL、gold query 命中率和 rollback dry-run；validation report 包含 `profileVersion`、`goldSetVersion`、`indexAlias`、门禁结果和阻断原因 | `es-query-service/src/main/java/com/dylan/esquery/service/DocumentIndexValidationService.java`、`DocumentIndexValidationReport.java`、`DocumentRetrievalValidationRequest.java` | 符合 |
| DOC-C-082 | 08 第 10、14 章 | validation report 幂等口径必须基于 `indexVersion + profileVersion + goldSetVersion` | `es-query-service/src/main/java/com/dylan/esquery/service/DocumentIndexValidationReport.java` | 符合 |
| DOC-C-083 | 08 第 10、15 章 | 权限漏出、deny/revoked gold query 命中必须阻断上线 | `DocumentIndexValidationService.java`、`DocumentIndexValidationServiceTest.java` | 符合 |
| DOC-C-084 | 08 第 14、15 章 | alias switch/rollback 必须带 expected current，审计包含 `profileVersion`、`indexAlias`、`goldSetVersion`、validation report 追踪字段 | `es-query-api/src/main/java/com/dylan/esquery/api/model/AliasSwitchRequest.java`、`EsIndexAliasService.java`、`AliasOperationAudit.java`、`PersistentAliasOperationAuditRepository.java`、`V3__add_document_alias_gold_validation_fields.sql` | 符合 |
| DOC-C-085 | 08 第 10、18、19 章 | 记录 channel、RRF/dedup、rerank 诊断指标，不记录全文、ACL 明细或 provider prompt | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentObservabilitySupport.java`、`DocumentCapabilityHandler.java` | 符合 |
| DOC-C-086 | 08 第 19、20 章 | 补充 validation、alias 门禁、观测指标相关单元测试 | `DocumentIndexValidationServiceTest.java`、`EsIndexAliasServiceTest.java`、`PersistentAliasOperationAuditRepositoryTest.java`、`DocumentObservabilitySupportTest.java`、`PersistentRebuildTaskRepositoryTest.java` | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 建议处理 |
|---|---|---|---|---|---|---|---|
| CR-081 | high | implementation_completeness | `es-query-service/src/main/java/com/dylan/esquery/service/DocumentIndexValidationService.java` | DOC-C-081、DOC-C-083 | 原实现只有本地 rebuild 成功校验，缺少 gold query、profileVersion、ACL、rollback dry-run 和 TopK 命中率门禁 | ES v2 alias 可能在质量或权限验证不足时被切换 | 已新增 `validateDocumentIndex`、`DocumentRetrievalValidationRequest`、`DocumentGoldQueryCase` 和阻断原因判定 |
| CR-082 | high | api_contract_consistency | `es-query-api/src/main/java/com/dylan/esquery/api/model/AliasSwitchRequest.java`、`es-query-service/src/main/java/com/dylan/esquery/service/EsIndexAliasService.java` | DOC-C-084 | alias 切换请求和服务校验缺少 `goldSetVersion`、`validationReportId`，无法证明切换对应哪一次 gold query 验证 | 灰度切换和回滚审计链路不完整，问题定位和追责困难 | 已新增字段并在 alias 服务入口强制非空校验 |
| CR-083 | medium | security | `es-query-service/src/main/java/com/dylan/esquery/service/AliasOperationAudit.java`、`PersistentAliasOperationAuditRepository.java` | DOC-C-084、DOC-C-085 | alias 审计未持久化 gold query 样本集版本和 validation report 摘要字段 | 回滚和审计只能看到 profile/index，不能追踪质量门禁证据 | 已扩展审计 record、Repository SQL 和 V3 迁移 |
| CR-084 | medium | observability | `agent-service/src/main/java/com/dylan/agent/capability/document/DocumentObservabilitySupport.java` | DOC-C-085 | 文档检索观测只记录基础成功失败，缺少多通道命中、dedup、rerank 诊断指标 | 线上无法判断 RRF/rerank 或通道空召回导致的质量回退 | 已新增 `recordRetrievalDiagnostics` 并由 `DocumentCapabilityHandler` 写入摘要指标 |
| CR-085 | medium | test_coverage | 多个测试类 | DOC-C-086 | 缺少 gold query 门禁、alias 新字段、审计字段和观测指标测试 | 后续修改容易破坏 08 关键门禁而不被发现 | 已补充对应单元测试和迁移检查 |
| CR-086 | medium | transaction_consistency | `DocumentIndexValidationReport.java` | DOC-C-082 | 第一轮实现中 validation report id 使用 `taskId`，且 digest 直接使用 `Map.toString()` | 同一 `indexVersion/profileVersion/goldSetVersion` 可能因任务 ID 或 Map 顺序生成不同追踪口径 | 第二轮已改为 `indexVersion + profileVersion + goldSetVersion`，并对 metrics 按 key 稳定排序 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| 无 | - | - | - | 未发现阻断性文档问题 | - | - |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | `DocumentIndexValidationService.java`、`DocumentIndexValidationReport.java`、`DocumentRetrievalValidationRequest.java`、`DocumentGoldQueryCase.java` | 增加 gold query/profile/schema/ACL/rollback/TopK 门禁和 validation report 字段 | CR-081、CR-083 | 已修复 |
| 1 | `AliasSwitchRequest.java`、`EsIndexAliasService.java`、`AliasOperationAudit.java`、`PersistentAliasOperationAuditRepository.java`、`V3__add_document_alias_gold_validation_fields.sql` | 增加 alias 切换必填验证字段、审计字段和数据库迁移 | CR-082、CR-083 | 已修复 |
| 1 | `DocumentObservabilitySupport.java`、`DocumentCapabilityHandler.java`、`DocumentObservabilitySupportTest.java` | 增加 channel hit、dedup reduction、rerank status 摘要指标 | CR-084、CR-085 | 已修复 |
| 1 | `DocumentIndexValidationServiceTest.java`、`EsIndexAliasServiceTest.java`、`PersistentAliasOperationAuditRepositoryTest.java`、`PersistentRebuildTaskRepositoryTest.java` | 补充 gold query、权限漏出、alias 新字段、审计持久化和迁移测试 | CR-085 | 已修复 |
| 2 | `DocumentIndexValidationReport.java`、`DocumentIndexValidationServiceTest.java` | 修正 validation report 幂等键和 metrics 稳定摘要，并补充单元测试 | CR-086 | 已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `mvn -q -f es-query-api/pom.xml -DskipTests install` | 通过 | 更新 `AliasSwitchRequest` 公共契约到本地仓库 |
| 1 | `mvn -q -f agent-api/pom.xml -DskipTests install` | 通过 | 安装公共 API 模块 |
| 1 | `mvn -q -f agent-adapter-api/pom.xml -DskipTests install` | 通过 | 安装文档适配器公共契约模块 |
| 1 | `mvn -q -f es-query-service/pom.xml "-Dtest=DocumentIndexValidationServiceTest,EsIndexAliasServiceTest,PersistentAliasOperationAuditRepositoryTest,PersistentRebuildTaskRepositoryTest,IndexRebuildServiceTest" "-DfailIfNoTests=false" test` | 通过 | 验证 validation、alias、审计持久化和迁移相关用例 |
| 1 | `mvn -q -f agent-service/pom.xml "-Dtest=DocumentObservabilitySupportTest,DocumentCapabilityHandlerTest,DocumentRevocationGuardTest" "-DfailIfNoTests=false" test` | 通过 | 验证观测指标、文档检索处理链路和撤权 guard 相关用例 |
| 1 | 六模块逐个执行 `mvn -q -f <module>/pom.xml -DskipTests compile` | 通过 | 覆盖 `agent-api`、`agent-adapter-api`、`agent-service`、`agent-adapter-document`、`es-query-api`、`es-query-service` |
| 1 | 六模块逐个执行 `mvn -q -f <module>/pom.xml test` | 通过 | 六个模块测试通过 |
| 2 | `mvn -q -f es-query-service/pom.xml "-Dtest=DocumentIndexValidationServiceTest,EsIndexAliasServiceTest,PersistentAliasOperationAuditRepositoryTest,PersistentRebuildTaskRepositoryTest,IndexRebuildServiceTest" "-DfailIfNoTests=false" test` | 通过 | 验证幂等键和稳定 digest 修复 |
| 2 | 六模块逐个执行 `mvn -q -f <module>/pom.xml -DskipTests compile` | 通过 | 第二轮修复后编译通过 |
| 2 | 六模块逐个执行 `mvn -q -f <module>/pom.xml test` | 通过 | 第二轮修复后六模块测试通过 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-081 | medium | 当前 gold query 门禁接收验证结果对象，尚未接入真实 ES 查询执行器和 fixture 批跑流程 | 08 设计允许首版样本以 fixture 管理，但本轮在代码范围内优先实现 Java 门禁、审计和测试闭环 | 后续在 ES v2 索引灰度环境补充 fixture 读取、批量执行和报告归档 |
| RISK-082 | medium | 真实 alias rollback dry-run 仍依赖外部调用方传入 `rollbackDryRunReady` | 本轮实现阻断字段和审计追踪，未新增完整 dry-run 执行器 | 后续将 rollback dry-run 执行结果纳入 validation request 构造链路 |
| RISK-083 | low | 观测指标只记录摘要指标，未记录完整 per-case 诊断明细 | 08 明确禁止记录正文、ACL 明细或 provider prompt，当前实现选择低敏摘要指标 | 如需深度诊断，应在安全脱敏和采样开关下扩展 case 级报告 |

## 9. 结论

最终结论：
- 通过。

说明：
- 本轮已按 08 详细设计补齐 gold query 门禁、alias 切换追踪字段、审计持久化、channel/RRF/rerank 摘要观测和最小测试。
- 未发现阻断性文档问题。
- 剩余风险主要是集成级 gold query 批跑和真实 ES 灰度环境验证，不影响当前 Java 门禁与契约实现的评审结论。
