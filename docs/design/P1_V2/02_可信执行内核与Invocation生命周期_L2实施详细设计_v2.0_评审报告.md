# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：是；目标文档已通过品审，但 P1_V2/P2_V3 全集仍为 In Review，尚未由用户确认 Approved，且 P1_V2/06 M0 实施授权未完成
- 审查类型：cross_layer
- 目标文档：`docs/design/P1_V2/02_可信执行内核与Invocation生命周期_L2实施详细设计_v2.0.md`
- 上级文档：L0、契约与规划 L1、能力执行内核 L1、元数据与上下文安全 L1
- 关联文档：P1_V2/00、01、03、04、05、06
- 实际审查轮次：3
- 主要风险摘要：Lifecycle/Core 权责倒置、Handler 输入越界、限额冻结点、恢复成功补写风险和持久化契约缺口均已修复；当前无 S0/S1 遗留

## 2. 文档识别结果

- 识别文档类型：L2 实施详细设计
- 识别依据：文档定义 Capability Registration、可信执行 Core、Invocation Lifecycle、checkpoint、终结事务、恢复、数据结构和实现落点
- 文档状态：In Review；用户已授权修改目标文档
- 是否包含修订历史：是，已统一为“修订历史”并追加本轮记录
- 是否存在上级文档：是，四份 L0/L1 已作为只读权威基线
- 是否存在关联文档缺失：否；本轮未修改任何关联文档

## 3. 审查范围

| 序号 | 文档/代码 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---:|---|
| 1 | `P1_V2/02` | 目标 L2 | 是，全文 | 审查并修复 Registration/Core/Lifecycle/Persistence 设计 |
| 2 | L0 与三份单 Agent L1 | 上级架构 | 是，相关章节 | 核对当前 CHAT-only、执行主链、授权/Context/limits 和恢复不变量 |
| 3 | `P1_V2/00、01、03～06` | 关联 L2 | 是，边界和相关条款 | 核对职责归属，不修改关联文档 |
| 4 | `agent-p0.sql`、Start/Lifecycle/Core/Registration 当前实现 | 实现基线 | 是，相关文件 | 校验字段、方法和目标偏差，避免不可编码设计 |

## 4. S0 阻断问题

复审后未发现遗留 S0。首轮发现并修复 1 项：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 10.0 节 | 把 Context 读取、Effective Limits 冻结、checkpoint 和 finalization participants 全部放入 Core，且顺序与 L1 相反 | 实现会形成第二生命周期协调者，绕过 Planning snapshot 与 Lifecycle 事务边界 | 已改为 Start→Planning→Lifecycle checkpoint→Core→Lifecycle finalization 的唯一主链；Core 只做复检、验证、执行和候选安全处理 |

## 5. S1 严重问题

复审后未发现遗留 S1。评审-修复循环共关闭 6 项 S1：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 10.0 节 | Handler 被描述为接收 `ExecutionCommand` | Handler 可读取 Raw Plan/Snapshot，破坏 Raw→Validated Plan 类型桥 | 已限定 Handler 只接收 Validated Plan + 最小 Execution Context |
| 2 | 原第 10.0、10.5 节 | Core “获取 registration snapshot”，暗示执行期重查 Registry | Planning 绑定可能被二次路由或替换 | 已限定只校验 PlanningResult 携带的同一 Resolved Registration，禁止查询 Registry |
| 3 | 原第 10.0 节 | Definition 增加幂等分类和 finalization participants | 把请求级/事务级策略侵入静态能力事实源 | 已收敛为 L1 冻结的 Definition 字段集合 |
| 4 | 原第 10.8 节 | Recovery 允许“恢复 finalization” | 崩溃后可能补写 SUCCESS/Context 或重复业务执行 | 已限定只原子终结 Invocation+Turn 为 FAILED/CANCELLED，不补成功、不重执行 |
| 5 | 原第 10.8～14、19～20 节 | 缺少可编码的 lifecycle 方法、Invocation 字段、CAS/commit-unknown、终结原子单元和测试契约 | 实现者仍需回查旧文档或自行发明一致性规则 | 已补齐接口、数据字典、状态机、事务规则、落点与验证矩阵 |
| 6 | 第二轮拟议修复 | 曾拟把 correlation 扩为客户端幂等键并引入新 Start union | 会越界修改 P1_V2/01/HTTP 公共契约，增加无授权抽象 | 已收回；当前 correlation 仅为服务端唯一关联标识，网络重试创建新 Invocation，写操作另行 ADR |

## 6. S2 一般问题

复审后未发现遗留 S2。首轮关闭 2 项：

| 序号 | 位置 | 问题 | 修复结果 |
|---:|---|---|---|
| 1 | 第 2 节 | “修改历史”未准确表达版本修订，缺少本轮记录 | 已改为“修订历史”并追加位置、原因和内容 |
| 2 | 多处 | 使用 D03/D06 历史阶段名描述未来责任 | 非历史记录处已改为当前 P1_V2 或 future Multi-Agent，避免把未评审设计当现成契约 |

## 7. S3 建议优化

暂无需要当前修改的 S3。代码实施时可在不改变设计的前提下统一中英文类型命名和 metrics 枚举。

## 8. 架构设计审查结果

不适用；目标是 L2 详细设计。L0/L1 仅作为只读架构基线，本轮没有发现必须先修改上级文档的问题。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | Lifecycle、Core、Registration、Context/Authorization/limits 边界已对齐 |
| 文件路径 | 通过 | Java/SQL/测试落点均为现有或明确目标路径 |
| 类与方法 | 通过 | start/checkpoint/executeAndFinalize/finalize/recover 和 Registration 类型桥已明确 |
| 入参与返回类型 | 通过 | ExecutionCommand 单一事实源、Validated Plan Handle 和 Finalized Result 边界明确 |
| 接口契约 | 通过 | 不修改外部 HTTP；未把 correlation 越权扩展为客户端幂等键 |
| 数据结构 | 通过 | Invocation 完整字段、空值时点、索引、CHECK 和 result 表语义已补齐 |
| 校验逻辑 | 通过 | identity、authorization、Context currentness、binding、limits、output/context 均 fail closed |
| 异常处理 | 通过 | rollback、commit unknown、CAS loser 和 recovery 行为明确 |
| 状态流转 | 通过 | 只有 Invocation 持久化状态机；checkpoint 不新增状态 |
| 数据库设计 | 通过 | 当前 CHAT/CONVERSATION 约束和本地原子终结边界可编码 |
| 缓存与消息 | 通过 | 不新增消息/outbox；写操作留独立 ADR |
| 权限、审计、幂等、风控 | 通过 | snapshots 只存安全引用；currentness 复检；当前重试语义明确 |
| 测试设计 | 通过 | 正向、负向、并发、事务未知结果、恢复和架构门禁均覆盖 |
| 可编码性 | 通过 | 不再依赖旧 D02 文档补齐关键算法或数据契约 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 当前只实现单 Agent CHAT，future Multi-Agent 不创建空壳 |
| 架构到详细设计一致性 | 通过 | 主链顺序和职责与 L0/L1 一致 |
| 接口契约一致性 | 通过 | ExecutionCommand 与 Registration 类型桥保持单一事实源 |
| 代码结构一致性 | 有条件通过 | 当前代码仍有 RunScope/TASK 和 schema 偏差，由 P1_V2/06 原子迁移关闭 |
| 权限与审计一致性 | 通过 | Authorization Snapshot 冻结 limits，Core 只复检；审计不存正文 |
| 一致性模型一致性 | 通过 | 本地事务、CAS、权威重读和失败恢复语义完整 |
| 风控策略一致性 | 通过 | deadline/cancellation、未知结果和迟到候选均 fail closed |
| 测试范围一致性 | 通过 | L1 验收项已映射到第 19～20 节 |

## 11. 是否建议进入后续阶段

- 是否建议继续评审下一份 L2：是
- 是否建议进入编码实现：否；须等待 P1_V2 全套评审、状态确认及用户后续授权
- 是否建议先修订架构设计：否
- 是否建议先修订关联文档：否
- 是否需要用户确认：当前无需新增确认

## 12. 用户确认项

暂无。未来若要为 Agent Chat 增加客户端幂等键，因涉及公共请求契约，必须另行取得授权并同步 P1_V2/01；本轮明确不修改。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 修订内容 | 是否阻断 |
|---:|---|---|---|---:|
| 1 | S0 | 第 9～10 节 | 恢复 Lifecycle→checkpoint→Core→finalization 权威主链 | 是，已修复 |
| 2 | S1 | 第 10 节 | 收敛 Definition/Registration/Validator/Handler/Core 边界 | 是，已修复 |
| 3 | S1 | 第 10.8、12～14 节 | 补齐原子开始、CAS、commit-unknown、终结事务与失败恢复 | 是，已修复 |
| 4 | S1 | 第 11、19～20 节 | 补齐可编码方法、数据和测试落点 | 是，已修复 |
| 5 | S1 | 第二轮修复 | 删除未经授权的客户端幂等契约扩展 | 是，已修复 |
| 6 | S2 | 第 2、5～17 节 | 修正修订历史和过期阶段命名 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | 初审并修正 | 8（S0=1、S1=5、S2=2） | 8 | 0 |
| 2 | 2026-07-13 | 跨层复核拟议修复 | 1（S1=1） | 1 | 0 |
| 3 | 2026-07-13 | L0/L1、关联边界与 Markdown 静态复审 | 0 | 0 | 0 |

## 15. 最终结论

> 全集终态注记（2026-07-13）：本文保留该文档逐轮评审的时点记录；P1_V2/00～06 与 P2_V3/00～07 全集评审现已完成且 S0/S1=0。当前实施状态和授权边界以目标文档第 1、3、23、24 节为准，本文不构成 Approved 或 M0 授权。

文档通过品审，不阻断继续串行评审 `P1_V2/03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md`。本次执行 3 轮；最终 S0、S1 均为 0。当前代码与目标设计的偏差仍由 P1_V2/06 原子迁移门禁关闭，P1_V2 全套评审完成前不进入编码。
