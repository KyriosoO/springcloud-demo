# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：否。可进入本地编码、mock/stub 联调和契约测试；真实联调、灰度和生产启用仍被 ACL 权威源、身份字段、embedding 维度、撤权 SLA 和 RebuildTask 持久化确认项阻断。
- 审查类型：auto，实际按详细设计 + 跨层级一致性审查执行
- 目标文档：`D:\codex\docs\design\P2\文档ACL与索引模型_L2实施详细设计_v1.0.md`
- 关联文档：见第 3 节
- 实际审查轮次：2 轮正式 design-doc-review；第 1 轮发现并修复 7 项问题，第 2 轮复审通过
- 主要风险摘要：文档内部已无 S0/S1；剩余风险均为外部契约或启用门禁，不要求修改 L0/L1 或既有 P2 文档。

## 2. 文档识别结果

- 识别文档类型：详细设计文档，且涉及跨层级一致性审查
- 识别依据：目标文档包含文档状态、修改历史、上级约束、关联边界、ACL/mapping/filter/接口/数据/状态/幂等/权限/测试/实现落点/风险/评审记录/实施对齐检查。
- 文档状态：Approved
- 是否包含修订历史：是
- 是否存在上级文档：是
- 是否存在关联文档缺失：未发现

## 3. 审查范围

| 序号 | 文档 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---|---|
| 1 | `D:\codex\docs\design\P2\文档ACL与索引模型_L2实施详细设计_v1.0.md` | 目标文档 | 是 | 本次品审和修订对象 |
| 2 | `D:\codex\docs\design\P2\文档ACL与索引模型_L2实施详细设计_交接文件.md` | 关联文档 | 是 | 任务范围、目标文档和关联文档来源 |
| 3 | `D:\codex\docs\design\P2\Agent文档型检索与总结能力_L2实施详细设计_v1.0.md` | 关联文档 | 是 | 文档检索、抽取式总结、ResultSecurity 和 Context 边界 |
| 4 | `D:\codex\docs\design\P2\Agent文档型检索与总结能力_设计文档品审报告.md` | 关联文档 | 是 | 下游 ACL、索引字段、queryVector 风险基线 |
| 5 | `D:\codex\docs\design\P2\Agent文档型生成式问答与总结能力_L2实施详细设计_v1.0.md` | 关联文档 | 是 | hybrid/vector、LLM 输入、引用校验依赖 |
| 6 | `D:\codex\docs\design\P2\Agent文档型生成式问答与总结能力_设计文档品审报告.md` | 关联文档 | 是 | provider、ACL、ES mapping 启用阻断项 |
| 7 | `D:\codex\docs\design\Agent目标架构总览_v1.0.md` | 上级文档 | 是 | Runtime 不可信、Agent Service 安全边界 |
| 8 | `D:\codex\docs\design\Agent能力执行内核架构设计_v1.0.md` | 上级文档 | 是 | ExecutionCore、Handler、Adapter、ResultSecurity 边界 |
| 9 | `D:\codex\docs\design\Agent元数据与上下文安全架构设计_v1.0.md` | 上级文档 | 是 | Profile/Policy/Permission/Context/ResultSecurity 安全约束 |

## 4. S0 阻断问题

未发现 S0 阻断问题。

## 5. S1 严重问题

未发现 S1 严重问题。

## 6. S2 一般问题

未发现未修复的 S2 一般问题。

已在第 1 轮修复的问题：

| 序号 | 位置 | 问题 | 风险 | 修改建议 |
|---:|---|---|---|---|
| 1 | 第 10.4、19.1 节 | `DocumentRetrievalRequest` 新增 `aclScope` 未说明构造兼容策略 | 可能破坏当前 `DocumentPlanValidator`、测试和既有调用方编译 | 明确保留现有构造签名，新增重载或 `withAclScope` |
| 2 | 第 10.4、11.2、19.1 节 | keyword/hybrid 过滤合并算法不够具体 | hybrid keyword 分支可能继续忽略 `HybridSearchRequest.filters`，导致 ACL 只作用于 vector | 明确 `bool.must` 只放全文查询，业务 filter 与 ACL filter 合并到 `bool.filter`，keyword/vector 共用 `request.filters` |
| 3 | 第 10.3、10.4、19.3 节 | `es-query-service` 作为通用服务时缺少文档索引识别策略 | 对非文档索引强制 ACL filter 会破坏通用兼容；不强制又无法关闭文档安全缺口 | 新增 `DocumentIndexPolicy` 和 `es-query.document-index-prefixes` |
| 4 | 第 10.5、12.2、19.1、20.2 节 | 只定义 mapping 校验，缺少 bulk/rebuild 文档必填字段校验 | ES mapping 不强制必填，半成品 chunk 可能进入 ACTIVE 索引 | 新增 `DocumentChunkSchemaValidator` 和对应测试 |
| 5 | 第 10.6、11.3、19.1、20.2 节 | alias 切换和回滚缺少具体实现落点 | full rebuild 成功后谁切 alias、如何回滚、如何防止切半成品索引不清楚 | 新增 `EsIndexAliasService`、`AliasSwitchRequest`、受控接口和测试 |
| 6 | 第 10.2、13.1 节 | `status` 必填字段枚举未包含 `REVOKED`，与状态流转表不一致 | 实现方可能把撤权 tombstone 当成未知状态或无法校验 | 补齐 `ACTIVE/REVOKED/DELETED/EXPIRED/BLOCKED` |
| 7 | 第 10.2、10.4 节 | `visibility` 取值和条件字段未冻结 | `USER/DEPARTMENT/ROLE/ATTRIBUTE` 无对应投影时可能被错误索引 | 新增 `visibility/status/chunkAclOverride` 枚举与条件规则 |

## 7. S3 建议优化

暂无 S3 建议优化。

## 8. 架构设计审查结果

不适用。目标文档不是架构设计文档。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | 未改变 Runtime 不可信、Agent Service 安全边界、ExecutionCore 主流程、ResultSecurity 和 Context 所有权 |
| 文件路径 | 通过 | Java、配置、脚本、测试路径均已列出 |
| 类与方法 | 通过 | 已补齐 ACL scope、filter factory、schema validator、index policy、alias service 等实现落点 |
| 入参与返回类型 | 通过 | 关键 DTO、Port、Service、Controller、Validator 的入参与返回类型已明确 |
| 接口契约 | 通过 | 覆盖 ACL projection、search/vector/hybrid、bulk/rebuild、alias switch/rollback |
| 数据结构 | 通过 | 覆盖 ACL 安全投影、ES chunk 文档、mapping、visibility/status 枚举 |
| 校验逻辑 | 通过 | 覆盖 ACL filter、document index guard、mapping、chunk schema、alias 前置条件 |
| 异常处理 | 通过 | ACL 不可用、filter 缺失、mapping 不匹配、重建失败均 fail closed |
| 状态流转 | 通过 | 覆盖文档索引生命周期、RebuildTask 状态和非法状态流转 |
| 数据库设计 | 通过 | 明确不新增 Agent 数据库表；RebuildTask 持久化为生产启用确认项 |
| 缓存与消息 | 通过 | 不引入 Agent 侧缓存；撤权和索引更新按最终一致 + SLA 门禁处理 |
| 权限、审计、幂等、风控 | 通过 | 检索阶段 ACL filter + ResultSecurity 二次过滤闭环，日志和指标禁用敏感高基数字段 |
| 测试设计 | 通过 | 单测、契约、脚本和人工门禁覆盖核心路径 |
| 可编码性 | 通过 | 可作为本地编码、mock/stub 联调和契约测试基线 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 目标文档仅补齐交接文件授权的 ACL、索引、filter、重建回滚和验证门禁 |
| 架构到详细设计一致性 | 通过 | 未把 ACL 权威表、文档全文、JWT、完整权限表达式或 ES DSL 下放到 Runtime |
| 接口契约一致性 | 通过 | 与现有 `VectorSearchRequest.filterDsl`、`HybridSearchRequest.filters`、`RebuildRequest.indexDefinition` 等代码现状对齐 |
| 代码结构一致性 | 通过 | 实现落点匹配当前 `agent-service`、`agent-adapter-document`、`agent-adapter-api`、`es-query-api`、`es-query-service` 模块 |
| 权限与审计一致性 | 通过 | 保持 capability/domain/field 权限由 Agent 复检，document/chunk ACL 由安全投影和 ES filter 保障 |
| 一致性模型一致性 | 通过 | Agent 本地事务不扩大到 ES 或文档平台，索引与 ACL 采用最终一致并设置撤权 SLA |
| 风控策略一致性 | 通过 | 缺失 ACL、mapping 漂移、撤权超 SLA、hybrid/vector 无 filter 均阻断启用 |
| 测试范围一致性 | 通过 | 与既有 P2 文档的 provider、ACL、mapping 启用门禁一致 |

## 11. 是否建议进入后续阶段

- 是否建议进入详细设计：已完成。
- 是否建议进入编码实现：是，限本地编码、mock/stub 联调和契约测试。
- 是否建议先修订架构设计：否。
- 是否建议先修订详细设计：否。
- 是否需要用户确认：若要开始代码实施、修改关联/上级文档、或进入真实联调/灰度/生产启用，需要用户明确授权。

## 12. 用户确认项

| 序号 | 确认问题 | 影响范围 | 建议选项 |
|---:|---|---|---|
| 1 | `DocumentAclScopePort` 对接现有权限系统还是文档 ACL 服务 | ACL filter 输入来源、HTTP client 配置和错误映射 | 先以 Port + mock 实现，真实联调前冻结外部服务归属 |
| 2 | `tenantId/userId/departmentIds/roleIds/attributeKeys` 权威字段命名 | ACL 投影字段、mapping、sourceUrl 响应和测试 fixture | 真实联调前由身份/权限负责人冻结字段 |
| 3 | embedding 模型与 dense_vector 维度 | mapping、provider 校验、vector/hybrid 启用 | keyword-only 先实施，provider 确认后新建物理索引 |
| 4 | 撤权 SLA 与超时关闭策略 | 灰度、生产启用和告警阈值 | 灰度前冻结 SLA，并完成撤权演练 |
| 5 | RebuildTask 是否生产持久化 | 重建任务可恢复性和 alias 切换审计 | 生产启用前确认持久化表或外部任务系统 |

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 建议修改内容 | 是否阻断 |
|---:|---|---|---|---|
| 1 | S2 | 第 10.4、19.1 节 | 保留 `DocumentRetrievalRequest` 构造兼容并新增 `withAclScope` 语义 | 否，已修复 |
| 2 | S2 | 第 10.4、11.2、19.1 节 | 明确 keyword/hybrid filter 合并算法 | 否，已修复 |
| 3 | S2 | 第 10.3、10.4、19.3 节 | 增加 `DocumentIndexPolicy` 和文档索引前缀配置 | 否，已修复 |
| 4 | S2 | 第 10.5、12.2、19.1、20.2 节 | 增加 `DocumentChunkSchemaValidator` | 否，已修复 |
| 5 | S2 | 第 10.6、11.3、19.1、20.2 节 | 增加 alias 切换/回滚实现落点 | 否，已修复 |
| 6 | S2 | 第 10.2、13.1 节 | 统一 `status` 枚举和撤权状态 | 否，已修复 |
| 7 | S2 | 第 10.2、10.4 节 | 冻结 `visibility` 条件字段规则 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-06 | 初审 / 修正 | 7 | 7 | 无 S0/S1 |
| 2 | 2026-07-06 | 复审 | 0 | 0 | 仅剩外部启用确认项 |

## 15. 最终结论

目标详细设计文档通过品审，已同步为 `Approved`。本次品审未发现需要修改上级文档、关联文档或代码的问题，也未发现阻断本地编码和契约测试的 S0/S1 问题。

后续可以按目标文档第 19、20 章进入本地实现和验证。真实联调、灰度或生产启用前，必须先关闭 ACL 权威源、身份字段命名、embedding 维度、撤权 SLA、RebuildTask 持久化和真实索引门禁风险。
