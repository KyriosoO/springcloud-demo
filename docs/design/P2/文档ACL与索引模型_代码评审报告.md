# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 6 |
| 实际执行轮次 | 5 |
| 依据文档数量 | 1 |
| 评审代码范围 | agent-adapter-api、agent-adapter-document、agent-service、es-query-api、es-query-service |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 本地闭环通过，仍有联调风险 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| D:/codex/docs/design/P2/文档ACL与索引模型_L2实施详细设计_v1.0.md | detailed_design | 1 | 是 | 已读取 | 作为本次代码评审主依据 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | 第 10.4.2 节 | `DocumentRetrievalRequest` 保留旧构造，新增 `aclScope/withAclScope` | agent-adapter-api | 符合 |
| DOC-C-002 | 第 10.4.2-10.4.4 节 | keyword/vector/hybrid 必须合并业务 filter 与 ACL filter，缺失时 fail closed | agent-adapter-document、es-query-service | 符合 |
| DOC-C-003 | 第 10.2、10.3 节 | 文档索引 mapping 必须具备 ACL、chunk、定位和向量字段校验 | es-query-service | 已修复后符合 |
| DOC-C-004 | 第 10.5、19 章 | 文档索引重建提交前校验 sourceUrl、idField、indexDefinition、batchSize | es-query-service | 已修复后符合 |
| DOC-C-005 | 第 14、19 章 | alias 切换需校验任务成功、targetIndex、expectedPreviousIndex、validationDigest | es-query-service | 本地闭环符合，真实 ACL 正反例验证待联调 |
| DOC-C-006 | 第 17、18 章 | 不输出 ACL DSL、ES DSL、queryVector、完整 metadata 或全文到响应/上下文 | agent-service、agent-adapter-document | 符合 |
| DOC-C-007 | 第 17.2 节 | ACL filter 复杂度超限应 fail closed | agent-adapter-document | 已修复后符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 建议处理 |
|---|---|---|---|---|---|---|---|
| CR-001 | high | implementation_completeness | es-query-service/src/main/java/com/dylan/esquery/service/EsIndexAliasService.java | 第 14、19 章 | `validationDigest` 只校验非空，没有和重建验证结果或任务记录比对 | 无法证明新索引已通过本地门禁，alias 仍可能切到未验证索引 | 已补本地验证状态和 digest 比对闭环；真实 ACL 正反例验证仍待联调 |
| CR-002 | medium | error_handling | agent-service/src/main/java/com/dylan/agent/capability/document/acl/HttpDocumentAclScopeClient.java | 第 10.4.4 节 | ACL scope HTTP 请求用 `Map.of` 承载可空字段，缺失时隐式 NPE | fail closed 原因不可控、排障困难 | 已修复为显式字段校验 |
| CR-003 | medium | implementation_completeness | es-query-service/src/main/java/com/dylan/esquery/service/DocumentIndexDefinitionValidator.java | 第 10.2 节 | mapping 校验遗漏 `departmentIds/roleIds/userIds/attributeKeys` | 部门/角色/用户/属性 ACL filter 依赖字段可能缺失 | 已修复 |
| CR-004 | medium | implementation_completeness | es-query-service/src/main/java/com/dylan/esquery/service/IndexRebuildService.java | 第 19 章 | 文档重建的 `idField/indexDefinition/batchSize` 没有提交前同步校验 | 调用方先收到 ACCEPTED，随后异步失败 | 已修复 |
| CR-005 | medium | performance/security | agent-adapter-document/src/main/java/com/dylan/agent/adapter/document/DocumentAclFilterFactory.java | 第 17.2 节 | ACL 可见性投影未限制 terms 数量 | 过大 filter 可能拖慢 ES 或绕过 ACL authority 压缩策略 | 已修复 |
| CR-006 | medium | transaction_consistency | es-query-service/src/main/java/com/dylan/esquery/service/EsIndexAliasService.java | 第 14 章 | alias 不存在时仍允许带 `expectedPreviousIndex` 的切换继续 add alias | 绕过上一索引匹配保护 | 已修复 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | medium | 文档ACL与索引模型_L2实施详细设计_v1.0.md | 配置键不一致 | 文档写 `es-query.document-index-prefixes`，仓库配置属性实际为 `es.query.document-index-prefixes` | 按文档配置会无法绑定 | 后续修正文档，不建议改代码前缀 |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | HttpDocumentAclScopeClient、DocumentAclScopePortTest、DocumentAclFilterFactoryTest | ACL HTTP 请求显式校验必填字段，补 ACL 过期/缺字段测试 | CR-002 | 已修复 |
| 2 | DocumentIndexDefinitionValidator、DocumentIndexDefinitionValidatorTest | mapping 必填字段补充 ACL 投影字段 | CR-003 | 已修复 |
| 3 | IndexRebuildService、IndexRebuildServiceTest | 重建提交前同步校验文档索引必填参数和 batchSize | CR-004 | 已修复 |
| 4 | DocumentAclFilterFactory、DocumentAclFilterFactoryTest | 增加 ACL 可见性投影 128 terms 上限 | CR-005 | 已修复 |
| 5 | EsIndexAliasService、EsIndexAliasServiceTest | alias 缺失时拒绝 expectedPreviousIndex 切换 | CR-006 | 已修复 |
| 6 | RebuildTask、RebuildTaskRepository、DocumentIndexValidationService、IndexRebuildService、EsIndexAliasService | 重建成功后写回本地验证状态和 digest，alias 切换/回滚必须比对任务 digest | CR-001 | 本地闭环已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 最终 | mvn -q -f D:/codex/serviceCenter/pom.xml -pl ../agent-adapter-api -am -Dtest=DocumentRetrievalRequestTest test | 通过 | API 请求兼容测试通过 |
| 最终 | mvn -q -f D:/codex/serviceCenter/pom.xml -pl ../agent-adapter-document -am -Dtest=DocumentAclFilterFactoryTest,DocumentRetrievalMapperTest,DocumentAgentAdapterTest test | 通过 | ACL filter、DSL 映射、adapter fail closed 测试通过 |
| 最终 | mvn -q -f D:/codex/serviceCenter/pom.xml -pl ../es-query-service -am -Dtest=EsDocumentServiceTest,DocumentIndexDefinitionValidatorTest,DocumentIndexPolicyTest,DocumentChunkSchemaValidatorTest,EsIndexAliasServiceTest,IndexRebuildServiceTest test | 通过 | ES 文档索引、重建、alias 测试通过 |
| 最终 | mvn -q -f D:/codex/serviceCenter/pom.xml -pl ../agent-service -am -Dtest=DocumentAclScopePortTest,DocumentCapabilityHandlerTest,DocumentResultSecurityProjectorTest test | 通过 | Agent 文档能力 ACL scope、Handler、ResultSecurity 测试通过 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | alias 已不能基于任意非空 validationDigest 切换，但 digest 仍是本地任务摘要 | 本地闭环尚未包含真实 ACL 正反例和真实 ES 查询验证 | 联调阶段把 ACL 正反例、mapping 查询、vector/hybrid 查询验证纳入 digest 输入 |
| RISK-002 | medium | 未执行真实 ES/ACL 服务集成验证 | 本轮仅执行单元级和局部契约测试 | 联调环境补 ACL 正反例、vector/hybrid、alias 回滚演练 |
| RISK-003 | medium | 设计文档配置键与代码配置前缀不一致 | 文档写法与 `EsQueryProperties(prefix="es.query")` 不一致 | 修改设计文档配置键 |

## 9. 结论

最终结论：本地闭环通过，仍有联调风险。

说明：
- 本轮已补 `RebuildTask.validationStatus/validationDigest`，重建成功后生成本地 digest，alias 切换和回滚必须比对任务 digest。
- 当前 digest 仍是本地任务摘要，不等价于真实 ACL 正反例和真实 ES 查询验证结果。
