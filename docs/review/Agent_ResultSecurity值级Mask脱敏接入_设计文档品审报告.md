# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：否
- 审查类型：detailed
- 目标文档：`docs/design/Agent_ResultSecurity值级Mask脱敏接入_L2实施详细设计_v1.0.md`
- 关联文档：用户提供的上级架构、D01-D05 详细设计、D03_01 权限契约、D04 metadata 收敛文档、`.agents/AGENTS.md`
- 实际审查轮次：2
- 主要风险摘要：初审发现 3 个 S1 和 2 个 S2，均已在目标文档内修订；复审未发现 S0/S1 剩余问题。

## 2. 文档识别结果

- 识别文档类型：详细设计文档
- 识别依据：文档包含实施范围、Java 路径、类、方法、参数、返回值、配置落点、异常处理、测试设计和实施顺序。
- 文档状态：Draft
- 是否包含修订历史：是，且本次修订已追加第 2 条记录。
- 是否存在上级文档：是。
- 是否存在关联文档缺失：用户输入的 `AGENTS.md` 在仓库根目录不存在，已解析到 `.agents/AGENTS.md`；未发现阻断。

## 3. 审查范围

| 序号 | 文档 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---|---|
| 1 | `docs/design/Agent_ResultSecurity值级Mask脱敏接入_L2实施详细设计_v1.0.md` | 目标文档 | 是 | 本次详细设计品审与修订对象 |
| 2 | `docs/design/D02_03_元数据授权与Context安全_L2_v1.0.md` | 上级详细设计 | 是 | 校验 `DomainSecurityConstraints`、`AuthorizationSnapshot`、`ExecutionScope`、`ResultSecurity` 边界 |
| 3 | `docs/design/D03_Capability v2跨服务原子切换_L2实施详细设计_v1.0.md` | 关联详细设计 | 是 | 校验 ResultSecurity 在 finalization/API 前的唯一边界 |
| 4 | `docs/design/D04_Agent Adapter与Domain Metadata收敛_L2实施详细设计_v1.0.md` | 关联详细设计 | 是 | 校验 D04 只承担 metadata/reference validation，不承担 mask 决策 |
| 5 | `docs/design/D05_Capability扩展验证与遗留清理_L2实施详细设计_v1.0.md` | 关联详细设计 | 是 | 校验 preview 不新增第二套 ResultSecurity 路径 |
| 6 | 其他用户列出的架构与 D01-D03_02 文档 | 关联文档 | 已定位并按关键约束核对 | 校验文档路径、边界与后续实施范围 |
| 7 | `.agents/AGENTS.md` | 工程约束 | 是 | 校验文档修改边界与输出要求 |

## 4. S0 阻断问题

未发现 S0 阻断问题。

## 5. S1 严重问题

初审发现的 S1 已全部修复，复审未发现 S1 严重问题。

| 序号 | 位置 | 问题 | 风险 | 修改建议 | 状态 |
|---:|---|---|---|---|---|
| 1 | 10.1、12.1 | 只说明从 `DomainSecurityConstraints` 读取 `requiredMask`，未明确 `filterAllowed/displayAllowed/allowedOperators/allowedFunctions` 不得被忽略 | 可能导致实现只接入 mask，却绕开 D02_03 中 Policy 作为部署级 deny/intersection 上限的父文档约束 | 明确 `fieldAccess` 必须同时按 Policy 非 mask 字段约束收紧字段权限、操作符和函数 | 已修复 |
| 2 | 12.4 | `maskValue` 返回 `Object`，但 `AgentQueryFilterParameter.value/values` 是 `String`/`List<String>`，filter 值脱敏缺少可编译的返回类型规则 | 实施时容易出现类型不匹配，或绕过 filter value/values 脱敏 | 增加 `maskStringValue(...)`，规定 `Objects.toString(masked, null)` 归一为 `String` | 已修复 |
| 3 | 16 | payload 缺少 domain 时写成“空字段集合或 fail closed 由测试固定” | ResultSecurity 是安全边界，缺失 domain 的处理不能留给测试临时决定；可能导致无法定位 `domain.field` 时返回未裁剪数据 | 明确只要 payload 含字段承载数据且无法解析 domain 就 fail closed；完全空 payload 可返回空安全结果 | 已修复 |

## 6. S2 一般问题

初审发现的 S2 已全部修复，复审未发现剩余 S2 一般问题。

| 序号 | 位置 | 问题 | 风险 | 修改建议 | 状态 |
|---:|---|---|---|---|---|
| 1 | 10.2 | `fieldMasks` 对 `NONE` 写入策略先说“可以选择”，再说“应采用稀疏 map” | 实施者可能出现两种语义，影响审计和测试断言稳定性 | 明确 `fieldMasks` 只写入非 `NONE` mask，缺省按 `NONE` 处理 | 已修复 |
| 2 | 13 | 配置设计只说“不新增配置 key”，但未列出策略事实路径和默认 bootstrap/reload 落点 | 后续实施难以判断 requiredMask 在哪里配置和验收 | 增加默认策略种子、运行态策略事实路径、reload 校验输入说明 | 已修复 |

## 7. S3 建议优化

| 序号 | 位置 | 建议 | 价值 |
|---:|---|---|---|
| 1 | 后续实施报告 | 编码完成后补充一份 code-review-against-docs 报告，验证 `FieldMaskerRegistry` 生产调用点是否只集中在 `metadata/result` helper | 防止实现阶段重新引入双脱敏路径 |

## 8. 架构设计审查结果

不适用。本次目标文档为详细设计文档。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | 已承接 D02_03 的 Policy/UserPermission/Snapshot/ExecutionScope/ResultSecurity 边界。 |
| 文件路径 | 通过 | Java、测试、配置装配、静态门禁路径已列出。 |
| 类与方法 | 通过 | 已列出 `AuthorizationPlanningPortImpl`、`AuthorizationSnapshot`、`ExecutionScope`、projector、`ResultValueMaskingSupport` 等类与方法。 |
| 入参与返回类型 | 通过 | 本次补齐 filter 字符串值脱敏的 `String` 返回类型。 |
| 接口契约 | 通过 | 明确不修改 auth-service、D03_01、D04、前端 DTO、Runtime Prompt。 |
| 数据结构 | 通过 | 明确 `fieldMasks` 的 `domain.field -> MaskType` 语义。 |
| 校验逻辑 | 通过 | 明确 Policy 非 mask 约束、MaskType、FieldMasker、字段引用校验。 |
| 异常处理 | 通过 | 明确 masker 异常、缺失 domain、Snapshot/ExecutionScope 非法字段的 fail closed。 |
| 状态流转 | 通过 | Planning → Snapshot → ExecutionScope → ResultSecurity → SecuredResult → Finalization/API 链路完整。 |
| 数据库设计 | 通过 | 明确不新增数据库结构。 |
| 缓存与消息 | 通过 | 未新增缓存、消息或异步机制。 |
| 权限、审计、幂等、风控 | 通过 | Policy 只能收紧，未授权字段删除，Snapshot 记录 mask fact。 |
| 测试设计 | 通过 | 覆盖授权规划、执行复检、ResultSecurity projector、装配与架构门禁。 |
| 可编码性 | 通过 | 复审后关键边界、类型、配置落点和异常策略已可指导编码。 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 不适用 | 本次未提供独立需求文档。 |
| 架构到详细设计一致性 | 通过 | 未发现目标文档改变上级 ResultSecurity、Authorization、D04、D03_01 边界。 |
| 接口契约一致性 | 通过 | 不修改外部 DTO/API，避免跨服务契约扩张。 |
| 代码结构一致性 | 通过 | 文件路径与现有模块结构匹配；新增 helper 位于 `metadata/result`。 |
| 权限与审计一致性 | 通过 | 修订后补齐 `DomainSecurityConstraints` 非 mask 约束不得被忽略。 |
| 一致性模型一致性 | 通过 | Execution 阶段不重算 active Policy，避免混合版本证据。 |
| 风控策略一致性 | 通过 | 缺失 domain、masker 异常、权限复检失败均 fail closed。 |
| 测试范围一致性 | 通过 | 测试设计覆盖核心链路和失败路径。 |

## 11. 是否建议进入后续阶段

- 是否建议进入详细设计：已完成。
- 是否建议进入编码实现：是。
- 是否建议先修订架构设计：否。
- 是否建议先修订详细设计：否。
- 是否需要用户确认：否。

## 12. 用户确认项

暂无需要用户确认的问题。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 建议修改内容 | 是否阻断 |
|---:|---|---|---|---|
| 1 | S1 | 10.1、12.1 | 明确 Policy 非 mask 字段约束也必须参与 `fieldAccess` 收紧 | 是，已修复 |
| 2 | S1 | 12.4 | 增加 filter 字符串值脱敏返回类型规则 | 是，已修复 |
| 3 | S1 | 16 | 明确缺失 domain 的 fail closed 策略 | 是，已修复 |
| 4 | S2 | 10.2 | 统一 `fieldMasks` 稀疏 map 规则 | 否，已修复 |
| 5 | S2 | 13 | 补齐配置与策略事实落点 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-03 | 初审 | 5 | 0 | 5 |
| 2 | 2026-07-03 | 修正并复审 | 0 | 5 | 0 |

## 15. 最终结论

目标文档通过本次设计品审，不阻断后续编码实现。本次仅修改目标详细设计文档，未修改任何关联文档、代码、测试或配置。

后续建议直接进入实现阶段，并在实现完成后按本报告和目标文档第 19、21 节执行代码对文档一致性评审，重点验证 `AuthorizationSnapshot.fieldMasks`、`ExecutionScope.fieldMasks`、`ResultValueMaskingSupport`、三类 `ResultSecurityProjector` 和 Spring 装配是否全部落地。
