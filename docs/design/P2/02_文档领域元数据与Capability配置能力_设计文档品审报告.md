# 02_文档领域元数据与 Capability 配置能力设计文档品审报告

## 1. 审查结论

| 项目 | 结论 |
|---|---|
| 审查对象 | `docs/design/P2/02_文档领域元数据与Capability配置能力_L2实施详细设计_v1.0.md` |
| 审查类型 | auto |
| 最大轮次 | 5 |
| 实际轮次 | 2 |
| 是否发现 S0 | 否 |
| 是否仍存在 S1 | 否 |
| 是否允许进入后续实现 | 是，允许进入本地编码闭环 |
| 是否允许生产启用 | 否，需在实现阶段关闭索引映射、权限投影、Profile/Policy 装配和漂移校验风险后再启用 |

本次审查结论为 **通过**。目标文档经修订后，已补齐 P2 小于 02 的关联基线，字段类型、证据字段、文档 adapter 索引映射与配置落点均与当前仓库和 01 设计保持一致，可作为本地编码与验证依据。

## 2. 文档识别结果

| 类型 | 文档 |
|---|---|
| 目标文档 | `docs/design/P2/02_文档领域元数据与Capability配置能力_L2实施详细设计_v1.0.md` |
| 上级 L1 文档 | `docs/design/Agent目标架构总览_v1.0.md` |
| 上级 L1 文档 | `docs/design/Agent能力执行内核架构设计_v1.0.md` |
| 上级 L1 文档 | `docs/design/Agent元数据与上下文安全架构设计_v1.0.md` |
| P2 前序设计 | `docs/design/P2/00_文档能力目标模式与实施路线图_L2实施详细设计_v1.0.md` |
| P2 前序报告 | `docs/design/P2/00_文档能力目标模式与实施路线图_设计文档品审报告.md` |
| P2 前序设计 | `docs/design/P2/01_文档语料接入与索引治理能力_L2实施详细设计_v1.0.md` |
| P2 前序报告 | `docs/design/P2/01_文档语料接入与索引治理能力_设计文档品审报告.md` |

P1 关联 L2 文档纳入一致性审查范围，但本次不修改：

| P1 关联文档 |
|---|
| `docs/design/P1/D01_Agent契约生成与治理_L2实施详细设计_v1.0.md` |
| `docs/design/P1/D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md` |
| `docs/design/P1/D02_01_Capability注册与可信执行内核_L2_v1.0.md` |
| `docs/design/P1/D02_02_Invocation生命周期与持久化_L2_v1.0.md` |
| `docs/design/P1/D02_03_元数据授权与Context安全_L2_v1.0.md` |
| `docs/design/P1/D03_01_UserPermissionAuthority权限权威源契约说明_L2_v1.0.md` |
| `docs/design/P1/D03_02_Capability v2实施落地清单_L2_v1.0.md` |
| `docs/design/P1/D03_Capability v2跨服务原子切换_L2实施详细设计_v1.0.md` |
| `docs/design/P1/D04_Agent Adapter与Domain Metadata收敛_L2实施详细设计_v1.0.md` |
| `docs/design/P1/D05_Capability扩展验证与遗留清理_L2实施详细设计_v1.0.md` |
| `docs/design/P1/Agent_ResultSecurity值级Mask脱敏接入_L2实施详细设计_v1.0.md` |
| `docs/design/P1/Agent与业务域白名单排序能力_L2实施详细设计_v1.0.md` |
| `docs/design/P1/Agent多轮分页与权限拒绝提示修复_L2实施详细设计_v1.0.md` |
| `docs/design/P1/统一密钥管理与多注入源支持_L2实施详细设计_v1.0.md` |

## 3. 审查范围

| 范围 | 审查内容 | 是否修改 |
|---|---|---|
| 目标文档结构 | 文档信息、范围、约束、接口、数据、实现清单、测试、风险、完成摘要 | 是 |
| L1 架构一致性 | Capability 注册、Domain Metadata、权限与上下文安全、能力执行内核边界 | 否 |
| P1 L2 一致性 | Capability v2、UserPermissionAuthority、Adapter 与 Domain Metadata 收敛、契约生成治理 | 否 |
| P2 前序一致性 | 00 目标模式、01 文档语料接入与索引治理 | 否 |
| 当前仓库代码契约 | Java 枚举、配置类、adapter 索引解析、证据字段映射、Python 生成契约 | 否 |

本次仅允许修改目标文档与本审查报告；未修改 L1、P1 或 P2 前序关联文档。

## 4. S0 阻塞问题

| 编号 | 问题 | 结论 |
|---|---|---|
| S0-001 | 是否存在无法继续评审或无法作为实现依据的问题 | 未发现 |

未发现 S0 阻塞问题。

## 5. S1 严重问题

| 编号 | 问题 | 风险 | 修复状态 |
|---|---|---|---|
| S1-001 | 字段配置示例使用 `DATE`、`INTEGER`，但当前 `AgentFieldType` 仅支持 `STRING`、`DECIMAL`、`INSTANT` | 实现阶段会被 `DomainMetadataPropertiesValidator` 拒绝，导致文档 domain 无法启动或测试误导 | 已修复为 `INSTANT` 与 `DECIMAL` |
| S1-002 | 证据字段使用 `contentSnippet`，与 01 设计和 `DocumentEvidenceMapper` 的 `snippet/content` 映射不一致 | 检索证据进入回答链路时字段丢失，影响证据绑定回答和摘要能力 | 已统一为 `snippet`，保留 `content` 作为正文字段 |
| S1-003 | adapter 索引配置落点写到 `agent-adapter-document/src/main/resources/application.yml`，但当前 adapter 模块无 resources，且运行配置落在 agent-service | 配置不会生效，生产可能继续使用隐式 `indexPrefix + domain` 方式访问错误索引 | 已改为 `agent-service/src/main/resources/application.yml`，并要求新增 `index-by-domain` fail-closed |

复审后 S1 均已关闭。

## 6. S2 重要问题

| 编号 | 问题 | 风险 | 修复状态 |
|---|---|---|---|
| S2-001 | 关联文档未完整纳入 P2 小于 02 的 00/01 设计与品审报告 | 02 的目标模式、前序索引治理结论无法形成可追溯基线 | 已补齐关联文档与第 7 章边界 |
| S2-002 | 目标文档对 adapter bean 风险表述过度保守，未区分 bean 存在性与索引映射实现风险 | 实施侧可能误判阻塞点，把已存在的 Spring bean 当作未知前提 | 已改为当前 bean 可由 agent-service 扫描，剩余风险聚焦索引映射、配置和测试 |

复审后 S2 均已关闭。

## 7. S3 一般问题

| 编号 | 问题 | 影响 | 修复状态 |
|---|---|---|---|
| S3-001 | 审查报告产物未列入目标文档实现落点 | 影响本次品审可追溯性 | 已补入目标文档第 19、23、24 章 |

复审后 S3 已关闭。

## 8. 架构审查

| 审查项 | 结论 | 依据 |
|---|---|---|
| Capability 边界 | 通过 | 02 聚焦文档 domain metadata、Capability 配置、默认启用策略，不侵入 03 权限感知检索、04 混合检索、05 回答、06 摘要 |
| Domain Metadata 权责 | 通过 | 元数据仅描述字段、操作符、排序、默认选择字段，不承载 ES index 细节 |
| Adapter 职责 | 通过 | ES read alias 解析归属 `agent.document-adapter.index-by-domain`，由 adapter 配置处理 |
| 权限边界 | 通过 | 02 只声明 Profile/Policy/UserPermission 投影和注册，不绕过 P1 权限权威源 |
| 上下文安全 | 通过 | 02 不扩大 prompt 注入面，不引入正文越权直传规则 |
| 生产启用门禁 | 有条件通过 | 必须在实现阶段验证 domain 配置、index 映射、权限投影和漂移检查后再启用 |

## 9. 详细设计审查

| 审查项 | 初审结论 | 修复后结论 |
|---|---|---|
| 文档信息与关联文档 | P2 前序关联不完整 | 已补齐 P2 00/01 与对应品审报告 |
| 三类文档 domain 字段 | 存在不支持字段类型 | 已改为当前仓库支持的 `STRING/DECIMAL/INSTANT` |
| Evidence 字段契约 | `contentSnippet` 与前序设计和代码不一致 | 已统一为 `snippet/content` |
| 配置项落点 | adapter 模块 resources 路径不成立 | 已改为 agent-service 运行配置 |
| 索引映射策略 | 隐式 `indexPrefix + domain` 风险未写成强约束 | 已明确 `index-by-domain` 优先且缺失 fail-closed |
| 测试设计 | 缺少不支持字段类型和索引映射回归测试 | 已补充针对性测试项 |
| 风险说明 | adapter bean 存在性判断不准确 | 已调整为实现风险而非前提阻塞 |

## 10. 跨层一致性

| 层级 | 一致性检查 | 结论 |
|---|---|---|
| L1 目标架构 | 文档能力仍通过 Capability/Adapter/Domain Metadata 进入执行内核 | 一致 |
| L1 执行内核 | 02 不改变 Invocation 生命周期与 Capability v2 原子切换边界 | 一致 |
| L1 元数据安全 | 02 使用 Domain Metadata 与 UserPermission 投影，不自建权限权威源 | 一致 |
| P1 Capability 契约 | 新增文档 capabilities 需进入 Profile/Policy/UserPermission 配置闭环 | 一致，待实现验证 |
| P1 Adapter 收敛 | 文档 adapter 使用 `DOCUMENT_RETRIEVABLE` 角色并接入端口治理 | 一致 |
| P2 00 | 三类目标模式为公司政策、知识库、文学文献 | 一致 |
| P2 01 | 字段、chunk、snippet、index alias 规则需复用 01 语料治理结论 | 修复后一致 |
| 当前代码 | `AgentFieldType`、`DocumentEvidenceMapper`、`DocumentAdapterProperties` 与设计对齐 | 修复后一致，但仍需编码补齐 `indexByDomain` |

## 11. 是否建议进入后续阶段

| 后续阶段 | 建议 | 前提 |
|---|---|---|
| 本地编码 | 建议进入 | 按 02 修订后的字段类型、配置路径、索引映射规则实现 |
| 本地测试闭环 | 建议进入 | 增加 domain metadata validator、document adapter index mapping、默认 profile/policy/user permission 投影测试 |
| 生产启用 | 暂不建议 | 需完成真实三类 domain 配置、索引 alias 配置、权限投影、漂移检测和回滚策略验证 |

## 12. 用户确认项

| 编号 | 确认项 | 建议 |
|---|---|---|
| UC-001 | 三类文档 domain 命名是否固定为 `company_policy`、`knowledge_base`、`literature` | 建议沿用 02 文档命名，避免后续 03-06 反复改动 |
| UC-002 | 生产索引 alias 命名是否由运维/配置提供 | 建议实现只消费 `index-by-domain`，不在代码内固化生产 alias |
| UC-003 | 文学文献字段中 `publishedAt` 是否必须精确到日期还是允许 datetime | 当前仓库只支持 `INSTANT`，建议统一按带时区 datetime 入库；仅展示层再格式化日期 |

以上确认项不阻塞本地编码，但会影响生产配置与验收样例。

## 13. 修订建议汇总

| 编号 | 修订位置 | 修订内容 | 状态 |
|---|---|---|---|
| R-001 | 第 1、7 章 | 补齐 P2 00/01 及品审报告作为关联基线 | 已完成 |
| R-002 | 第 10、12 章 | 将不支持的 `DATE/INTEGER` 改为 `INSTANT/DECIMAL` | 已完成 |
| R-003 | 第 10、12 章 | 将 `contentSnippet` 统一为 `snippet`，并保留 `content` 字段 | 已完成 |
| R-004 | 第 11、17、19 章 | 明确 `agent.document-adapter.index-by-domain` 配置与 fail-closed 规则 | 已完成 |
| R-005 | 第 19、20 章 | 补充 adapter index mapping 和字段类型校验测试 | 已完成 |
| R-006 | 第 21、24 章 | 将阻塞状态改为允许本地编码、生产启用前关闭风险 | 已完成 |
| R-007 | 第 19、23、24 章 | 增加本品审报告产物 | 已完成 |

## 14. 复审记录

| 轮次 | 日期 | 审查动作 | 发现问题数 | 未关闭问题数 | 结论 |
|---|---|---|---:|---:|---|
| 1 | 2026-07-06 | 初审目标文档、L1、P1、P2 00/01 与当前代码契约 | 6 | 6 | 需修复后复审 |
| 2 | 2026-07-06 | 复审修订后的字段、配置、索引映射、测试和风险章节 | 0 | 0 | 通过 |

本次审查-修复-复审循环未超过用户指定的 5 轮上限。

## 15. 最终结论

`02_文档领域元数据与Capability配置能力_L2实施详细设计_v1.0.md` 修复后满足以下条件：

1. 与 L1 架构的 Capability 执行、元数据安全、权限边界保持一致。
2. 与 P1 Capability v2、UserPermissionAuthority、Adapter/Domain Metadata 收敛设计保持一致。
3. 与 P2 00 目标模式和 P2 01 语料接入、索引治理设计保持一致。
4. 与当前仓库 `AgentFieldType`、`DocumentEvidenceMapper`、`DocumentAdapterProperties`、`DocumentAgentAdapter` 的真实契约保持一致。
5. 已明确实现阶段必须补齐 `index-by-domain` 映射、缺失配置 fail-closed、Profile/Policy/UserPermission 投影与漂移测试。

最终结论：**通过**。建议下一步进入 02 对应本地编码与测试闭环；生产启用需等待实现验证结果。
