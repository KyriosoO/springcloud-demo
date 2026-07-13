# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：是；目标文档已通过品审，但 P1_V2/P2_V3 全集仍为 In Review，尚未由用户确认 Approved，且 P1_V2/06 M0 实施授权未完成
- 审查类型：cross_layer
- 目标文档：`docs/design/P1_V2/04_Adapter与DomainMetadata治理_L2实施详细设计_v2.0.md`
- 上级文档：L0、契约与规划 L1、能力执行内核 L1、元数据与上下文安全 L1
- 关联文档：P1_V2/00、01、02、03、05、06，P2_V3/04
- 实际审查轮次：3
- 主要风险摘要：Validator 绕过请求级投影、Registration/availability 双来源、Domain resource limits 多源、execution projection/binding TOCTOU、Prompt/Java 事实副本和新增 Domain 门禁缺失均已修复；当前无 S0/S1 遗留

## 2. 文档识别结果

- 识别文档类型：L2 实施详细设计
- 识别依据：文档定义 Canonical Catalog、Adapter SPI/Registration、availability、投影、Binding、排序、配置、实现与验证落点
- 文档状态：In Review；用户已授权修改目标文档
- 是否包含修订历史：是，已补齐位置、原因、内容并追加本轮记录
- 是否存在上级文档：是，四份 L0/L1 作为只读权威基线
- 是否存在关联文档缺失：否；本轮未修改上级或关联文档

## 3. 审查范围

| 序号 | 文档/代码 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---:|---|
| 1 | `P1_V2/04` | 目标 L2 | 是，全文 | 评审并修复 Adapter/Domain Metadata 详细设计 |
| 2 | L0 与三份单 Agent L1 | 上级架构 | 是，相关章节 | 核对 CHAT-only、Catalog、Registration、availability、投影、Binding 和扩展不变量 |
| 3 | `P1_V2/00～03、05、06`、`P2_V3/04` | 关联 L2 | 是，相关边界 | 核对 Core 时序、授权 evidence、typed limits、原子迁移和文档检索边界 |
| 4 | Domain metadata、Capability Validator、Adapter、Prompt、employee/transaction 当前 Java/配置/测试 | 实现基线 | 是，相关文件 | 校验权威类型、事实副本、接口签名和当前偏差 |

## 4. S0 阻断问题

复审后未发现遗留 S0。首轮关闭 1 项：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 10、19 节及当前实现对照 | 未要求删除 `DomainCatalogView`，Query/Aggregate/Document Validator 与 filter helper 可绕过请求级 `ExecutionValidationProjection` 直接读取完整 Catalog | Validator 可区分“字段不存在/存在但无权限”，并使用未按当前 ExecutionScope 收紧的 operator/function，形成权限信息泄漏和执行越权旁路 | 已删除该设计入口；Validator/helper 只消费 `ExecutionFieldRule`/Projection，启动引用改走通用 reference gate |

## 5. S1 严重问题

复审后未发现遗留 S1。评审-修复循环关闭 10 项：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 10.2、11 节 | Registration 设计为 `adapterId/domainId/roles/beanType/version/enabled` | role/domain 绑定不唯一，`enabled` 与动态 availability 形成第二事实源 | 已冻结一项一 role/domain 的静态 Registration，删除 roles/enabled |
| 2 | 原第 10.2、11 节 | `portType` 与 role→typed port 映射、逐项 Catalog version 与 bundle 根版本重复 | 配置可声明互相矛盾的类型/版本，增加无意义校验层 | 已由 role 派生 port type、由 static bundle 绑定 Catalog，逐项配置不再接受这两个字段 |
| 3 | 原第 10.3、12、19 节 | 未明确删除当前 `CanonicalRoleCapability/ExecutionValidationProjection` 的 `maxPageSize/maxResultRows` | Catalog、AgentProperties、ExecutionScope 与 P1_V2/05 typed limits 多源计算 | 已从 Domain 模型/配置/Projection 删除散预算，Validator 只读 typed limits |
| 4 | 原第 10.5、13 节 | 把 metadata/registration/health 当作同一可刷新状态，未区分静态事实和请求级 availability | 健康变化可能反写 Catalog 或使无关 Domain 的 Invocation 全部失效 | 已拆 `DomainMetadataStaticBundle` 与 `AdapterAvailabilityResolver`，evidence 只绑定本次评估 key |
| 5 | 原第 10.4、11 节及当前实现对照 | `executionProjection` 与 `bind` 分两次读取，且 Binding 未冻结同一 availability evidence | reload/health 变化时 Validator 与 Handler 可能消费不同版本，产生 TOCTOU | 已改为一次 `DomainMetadataPort.resolveExecution` 原子返回 projection/binding |
| 6 | 原第 10.4～10.5 节 | Port 使用 `planSchema(agentId,profileId,planningEvidence)` 概括签名，边界可能重新读取 Profile/Policy/Permission | metadata 边界重复授权计算并形成不同 evidence | 已冻结完整 scope/evidence/deadline 接口，并明确不重复读取授权源 |
| 7 | 原第 10.3、14 节 | Catalog digest/reload 只有原则描述，无 canonical form、同版本不同 digest、CAS 并发语义 | 配置重排、并发 reload 和版本复用无法可靠审计/拒绝 | 已补 DCF-1 SHA-256、static bundle CAS、version reuse 拒绝与 currentness 规则 |
| 8 | 原第 10.6～10.10、19 节 | 清理清单未覆盖 Prompt 真实字段示例、Default bootstrap 专用遍历、Validator internal 依赖和 Adapter 自报禁令 | 历史事实副本继续影响 Runtime 或新增 Domain 仍需改共享代码 | 已补逐路径删除/保留矩阵与 architecture gate |
| 9 | 原第 10.11、19～20 节 | 新 Domain 验证仅写“D05 architecture test”，无 fixture、禁止依赖/字符串/domain switch 的可执行断言 | 无法证明新增 Domain 不修改 Planning/Core/Handler/Validator | 已定义 `sample_domain` fixture 与四类无侵入扫描门禁 |
| 10 | 原第 10.6～10.10 节 | QUERY 排序未区分用户排序与内部 tie-breaker，downstream 白名单又被称为“漂移副本” | Context 回显可能伪造用户输入，或错误删除下游服务的必要防御 | 已明确用户排序 canonical 保存、内部稳定 tie-breaker 不回显；保留下游自主白名单并用 coverage test 约束子集 |

## 6. S2 一般问题

复审后未发现遗留 S2。首轮关闭 1 项：原实现路径使用概括目录、修改历史字段不足，未列出配置删除和最小命令；现已补齐具体路径、动作、测试矩阵、验收命令与完整修订历史。

## 7. S3 建议优化

暂无当前必须修改的 S3。实现时可在不改变接口契约的前提下统一 metadata/availability 指标名称和受控 reason code。

## 8. 架构设计审查结果

不适用；目标为 L2 详细设计。未发现必须先修改 L0/L1 的架构阻塞项。第二轮发现的静态事实与动态 health 混层已经在目标 L2 内按 L1 约束修复，不需要扩大文档修改范围。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | L1 第 10、11、19、21.4 节要求均有对应接口/门禁 |
| 唯一事实源 | 通过 | config input -> static bundle；无 DB/远程 Registry/Adapter self-report |
| 文件路径 | 通过 | API、service、adapter、runtime Prompt、config、下游与测试路径明确 |
| 类与方法 | 通过 | Catalog/Registration/candidate/store/availability/projection/resolve 均冻结 |
| 入参与返回类型 | 通过 | Planning/Execution scope、evidence、deadline、typed port/result 完整 |
| 接口契约 | 通过 | AdapterRole Java 权威；Registration 无重复 port type/catalog version |
| 数据结构 | 通过 | 无新增表；static evidence 与 request availability evidence 分离 |
| 校验逻辑 | 通过 | 引用闭合、type/coverage、currentness、排序和下游二次校验 fail closed |
| 异常处理 | 通过 | reload candidate 拒绝保留旧静态事实；health unknown 仅使相关 key 不可用 |
| 并发一致性 | 通过 | static bundle CAS；execution projection/binding 单次原子解析 |
| 权限与风控 | 通过 | Validator 不再直读完整 Catalog；availability 不授予权限 |
| 资源限额 | 通过 | Domain 模型/Projection 无散预算，统一 P1_V2/05 typed limits |
| 测试设计 | 通过 | 正向、负向、并发、Prompt、downstream、扩展和架构门禁完整 |
| 可编码性 | 通过 | 无需回查 P1/D04 或旧排序文档补关键设计 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 当前单 Agent/ConversationScope；future Multi-Agent 无空壳字段/服务 |
| 架构到详细设计一致性 | 通过 | Canonical Catalog、Registration、availability、四类投影与一次 Binding 完整承接 |
| 接口契约一致性 | 通过 | Runtime Route 无 field schema；Plan/Execution 按 scope 逐级收紧 |
| 代码结构一致性 | 有条件通过 | 当前代码仍有 DomainCatalogView、散预算、分次 bind、重复 Registration 字段和 Prompt 实例；由 P1_V2/06 原子迁移关闭 |
| 权限与审计一致性 | 通过 | Catalog/health 不授权；审计只存安全引用，日志不泄漏字段存在性/物理映射 |
| 一致性模型一致性 | 通过 | static metadata CAS 与 request health currentness 分离，避免全局无关失效 |
| 下游契约一致性 | 通过 | Agent Catalog 是 Agent 事实源，下游 FIELD_MAP/SEARCHABLE_FIELDS 保持服务边界权威 |
| 扩展性一致性 | 通过 | 新 Domain 只增加数据/Adapter/Registration/Policy/下游依赖/装配 |

## 11. 是否建议进入后续阶段

- 是否建议继续评审下一份 L2：是
- 是否建议进入编码实现：否；等待 P1_V2/P2_V3 全套串行评审和用户后续授权
- 是否建议先修订架构设计：否
- 是否建议先修订关联文档：否；P1_V2/05 的 typed limit 细节将在其自身评审中验证
- 是否需要用户确认：当前无需新增确认

## 12. 用户确认项

暂无。本轮只修改用户已授权的目标 L2 和评审报告。P1_V2/06 实施若需要改变 `transaction-api` 既有公共字段/语义，仍须按用户规则在编码前单独取得公共契约变更授权。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 修订内容 | 是否阻断 |
|---:|---|---|---|---:|
| 1 | S0 | 第 10.7～10.9、19～20 节 | 删除 Validator 直读 Catalog，统一请求级安全投影 | 是，已修复 |
| 2 | S1 | 第 10.3～10.6 节 | 收敛静态 Registration、去重复类型/版本并拆动态 availability | 是，已修复 |
| 3 | S1 | 第 10.2、10.7、12、19 节 | 删除 Domain 散预算，统一 typed limits | 是，已修复 |
| 4 | S1 | 第 10.7～10.8、13～14 节 | 原子解析 projection/binding，补 currentness/CAS | 是，已修复 |
| 5 | S1 | 第 10.10～10.13、19～20 节 | 闭合排序、下游防御、事实副本清理和新 Domain 门禁 | 是，已修复 |
| 6 | S2 | 第 2、19～20、22 节 | 完善修订历史、路径、命令和评审记录 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | 初审并修正 | 10（S0=1、S1=8、S2=1） | 10 | 0 |
| 2 | 2026-07-13 | 冗余与静态/动态边界复核 | 2（S1=2） | 2 | 0 |
| 3 | 2026-07-13 | L0/L1、关联边界、Java 权威类型与 Markdown 静态终审 | 0 | 0 | 0 |

## 15. 最终结论

> 全集终态注记（2026-07-13）：本文保留该文档逐轮评审的时点记录；P1_V2/00～06 与 P2_V3/00～07 全集评审现已完成且 S0/S1=0。当前实施状态和授权边界以目标文档第 1、3、23、24 节为准，本文不构成 Approved 或 M0 授权。

文档通过品审，不阻断继续串行评审 `P1_V2/05_有效资源预算与CapabilityLocalPort收敛_L2实施详细设计_v2.0.md`。本次执行 3 轮；最终 S0、S1 均为 0。当前代码偏差必须由 P1_V2/06 原子迁移统一关闭，禁止先删除旧 Catalog View/散预算而未同时接入 Projection 与 typed limits。
