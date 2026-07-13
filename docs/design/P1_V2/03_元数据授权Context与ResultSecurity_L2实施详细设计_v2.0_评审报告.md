# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断后续编码：是；目标文档已通过品审，但 P1_V2/P2_V3 全集仍为 In Review，尚未由用户确认 Approved，且 P1_V2/06 M0 实施授权未完成
- 审查类型：cross_layer
- 目标文档：`docs/design/P1_V2/03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md`
- 上级文档：L0、契约与规划 L1、能力执行内核 L1、元数据与上下文安全 L1
- 关联文档：P1_V2/00、01、02、04、05、06，P2_V3/03
- 实际审查轮次：3
- 主要风险摘要：Context 错误时序/平行状态机、Catalog 缺失、授权与资源限额不同源、伪 CAS、Mask/Query 枚举冲突和 secret 引用泄漏均已修复；当前无 S0/S1 遗留

## 2. 文档识别结果

- 识别文档类型：L2 实施详细设计
- 识别依据：文档定义 Profile/Policy/Catalog/Authorization、Context、Result Security、secret、数据结构、配置和实现门禁
- 文档状态：In Review；用户已授权修改目标文档
- 是否包含修订历史：是，已补齐位置、原因、内容并追加本轮记录
- 是否存在上级文档：是，四份 L0/L1 作为只读权威基线
- 是否存在关联文档缺失：否；本轮未修改上级或关联文档

## 3. 审查范围

| 序号 | 文档/代码 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---:|---|
| 1 | `P1_V2/03` | 目标 L2 | 是，全文 | 评审并修复 metadata/security/context 详细设计 |
| 2 | L0 与三份单 Agent L1 | 上级架构 | 是，相关章节 | 核对 CHAT-only、Catalog、Snapshot、Context、limits 和 Result Security 不变量 |
| 3 | `P1_V2/00、01、02、04～06` | 关联 L2 | 是，相关边界 | 核对所有权和原子迁移边界 |
| 4 | Profile/Policy/Auth/Context/Result/secret/Query 当前 Java 与 SQL | 实现基线 | 是，相关文件 | 校验 Java 权威枚举、方法、字段、CAS 和配置偏差 |

## 4. S0 阻断问题

复审后未发现遗留 S0。首轮关闭 2 项：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 9、10.5 节 | 把 Context 读取/投影放在 Execution authorization 之后并直接指向 Handler | 绕过“Route 后、Plan 前加载”和 Context Snapshot currentness 模型 | 已重排为 Route→Registration→Planning Context→Snapshot→Plan；Core 只复检，不重载 |
| 2 | 原第 10.5、13 节 | 为 Context 建立 ACTIVE/PENDING/FINALIZED/DISCARDED/RETIRED 状态机，并让 Context participant 提交/废弃候选 | 与 Invocation Lifecycle 形成第二终结协调者和半提交状态 | 已删除平行状态机；candidate 仅内存存在，只有 Lifecycle SUCCESS 事务写权威记录 |

## 5. S1 严重问题

复审后未发现遗留 S1。评审-修复循环关闭 11 项：

| 序号 | 位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原第 10 节 | 缺少 L1 明确要求的 Capability Catalog/Available Snapshot 算法 | capability 可见性只能由实现者自行发明 | 已补通用交集公式、Domain Mode、稳定投影和无散预算字段 |
| 2 | 原第 10.1～10.2 节 | Profile 包含 policyRef/enabledDomains，Policy/Scope 保留散 page/result budget 和 delegation 配置 | 静态事实重复、limits 多源、提前固化 future 配置 | 已按所有权拆分 PlanningBudget 与 typed resource contributions，当前只保留 CHAT_ALL 中性 seam |
| 3 | 原第 10.3、11 节 | Execution authorize 输入/签名错误，Snapshot 缺 Owner/Scope/correlation/limits 等关键绑定 | Core 无法证明当前复检与 Planning 同源 | 已冻结 Snapshot/ExecutionScope 字段和 `recheck(snapshot,handle)` 契约 |
| 4 | 当前实现对照 | `PlanningAuthorizationEvidence` 使用 `Objects.hash` 作为安全 digest | 碰撞和不稳定编码会削弱 artifact/Snapshot 完整性绑定 | 已要求版本化 canonical form + SHA-256，禁止 hashCode/序列化顺序 |
| 5 | 原第 10.8、14 节 | 授权/metadata 漂移后直接“重新规划” | 可能在同一 Invocation 混入新证据并自动重试 | 已限定当前 Invocation fail closed，只有新 Invocation 可重新规划 |
| 6 | 原第 10.5、12、14 节 | Context 数据仅写“至少保存”，CAS 无 SQL 条件；当前实现 SELECT 后无条件 upsert | 并发写会丢失更新，文档不可直接编码 | 已补完整字段、索引/CHECK、insert-if-absent 与 conditional update 语义 |
| 7 | 原第 10.7、11 节 | Result Security 未显式接收 output ContractRef/同一 limits，Generated Text Candidate 校验不闭合 | projector 可各自读取配置或放过自由文本 | 已补 `secure(...,scope,limits)`、ContractRef、evidence/citation/预算门禁 |
| 8 | 原第 10.7 节 | 文档使用 FULL/PARTIAL/HASH，与 Java `MaskType` 冲突 | 配置/代码形成第二枚举，Mask 行为不可预测 | 已统一为 NONE/ID_CARD/MOBILE/EMAIL/ADDRESS + FieldMaskerRegistry |
| 9 | 原第 10.9～10.10 节 | `SecretKeyRef` 携带 configValue，JWT/payload active key 与 Context TTL 存在重复配置，保留无 provider 的 EXTERNAL | Secret 可能被复制/打印，purpose 可能串用，配置漂移 | 已改纯引用、purpose/key material 隔离、单一配置来源并删除空 source |
| 10 | 原第 11、12、19 节 | 方法、字段、路径使用概括/省略号，缺少完整 DDL、落点和并发测试 | 仍需回查旧文档或按经验补设计 | 已冻结接口、字段、路径、动作、配置和测试矩阵 |
| 11 | 第二轮第 10.7 节 | 错误新增 `QueryContextMode.NEW`，并把未显式 page 解释为自动 +1 | 与 Java 权威枚举/历史合并契约冲突，改变分页语义 | 已收敛为 REPLACE/MERGE；页码缺省继承，下一页由 Runtime 显式建议后 Java 校验 |

## 6. S2 一般问题

复审后未发现遗留 S2。原“修改历史”字段不足，已统一为完整修订历史；普通日志与安全审计边界也已分开，避免 raw userId/tenantId 进入应用日志。

## 7. S3 建议优化

暂无当前必须修改的 S3。实现时可在不改变契约的前提下统一 metrics 命名和错误模板文案。

## 8. 架构设计审查结果

不适用；目标为 L2 详细设计。未发现必须先修改 L0/L1 的架构阻塞项。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 通过 | Profile/Policy/Catalog/Authorization/Context/Result Security 责任完整 |
| 文件路径 | 通过 | Java、SQL、配置、脚本和测试路径均明确，无省略号 |
| 类与方法 | 通过 | capture/assertCurrent/freeze/recheck/load/revalidate/approve/persist/secure/CAS 均明确 |
| 入参与返回类型 | 通过 | Snapshot/Scope/Context/limits/Result 类型边界完整 |
| 接口契约 | 通过 | Java 权威 Query/Mask 枚举一致；不修改外部 HTTP |
| 数据结构 | 通过 | Context 完整字段、空值、索引、CHECK、protected payload 结构明确 |
| 校验逻辑 | 通过 | currentness、ContractRef、digest、limits、mask、citation 全部 fail closed |
| 异常处理 | 通过 | authority/crypto/CAS/unknown commit/cleanup 安全语义完整 |
| 状态流转 | 通过 | 无 Context 第二状态机；只保留 readable/TTL/CAS 与不可变 Snapshot |
| 数据库设计 | 通过 | 真实数据库原子 insert/update CAS，不使用无条件 upsert |
| 缓存与消息 | 通过 | 只缓存 immutable bundle；当前不新增 Permission cache/outbox |
| 权限、审计、幂等、风控 | 通过 | 当前复检、最小审计、purpose 隔离、重放/冲突规则明确 |
| 测试设计 | 通过 | 正向、负向、并发、事务、crypto、枚举和架构门禁完整 |
| 可编码性 | 通过 | 无需回查四份旧 P1 文档补关键设计 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 通过 | 当前单 Agent/ConversationScope，future Multi-Agent 无空壳 |
| 架构到详细设计一致性 | 通过 | L1 第 21.3 节要求的 Profile/Catalog/Snapshot/Context/Result/limits 均承接 |
| 接口契约一致性 | 通过 | Java QueryContextMode/MaskType/ContractRef 为唯一结构来源 |
| 代码结构一致性 | 有条件通过 | 当前代码仍有散预算、Delegation 配置、Envelope、伪 CAS 和重复 secret 字段，P1_V2/06 原子迁移关闭 |
| 权限与审计一致性 | 通过 | Snapshot 与 current recheck 同源，日志/审计分层且不存正文 |
| 一致性模型一致性 | 通过 | Context CAS 加入 P1_V2/02 本地 finalization 原子单元 |
| 风控策略一致性 | 通过 | limits 只收紧，漂移/crypto/ACL/unknown structure fail closed |
| 测试范围一致性 | 通过 | L1 验收项均有直接测试或 architecture gate |

## 11. 是否建议进入后续阶段

- 是否建议继续评审下一份 L2：是
- 是否建议进入编码实现：否；等待 P1_V2 全套评审和用户后续授权
- 是否建议先修订架构设计：否
- 是否建议先修订关联文档：否；P1_V2/05 的 typed resource 细节将在其自身评审中验证
- 是否需要用户确认：当前无需新增确认

## 12. 用户确认项

暂无。本设计涉及 Context DDL 和 common-security 内部 secret 契约的实施切换；实际编码前仍须按用户规则取得相应公共结构/数据库变更授权，本轮仅修改已授权目标文档。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 修订内容 | 是否阻断 |
|---:|---|---|---|---:|
| 1 | S0 | 第 9～10、13～14 节 | 恢复 Planning Context 与 Lifecycle 唯一终结边界 | 是，已修复 |
| 2 | S1 | 第 10.1～10.4 节 | 补齐 Profile/Policy/Authorization/Catalog/limits/digest | 是，已修复 |
| 3 | S1 | 第 10.5～14 节 | 补齐 Snapshot、原子 CAS、无状态候选与事务未知结果 | 是，已修复 |
| 4 | S1 | 第 10.7～10.10 节 | 对齐 Query/Mask Java 枚举、Result Security 和 secret purpose | 是，已修复 |
| 5 | S1 | 第 11～20 节 | 冻结接口、DDL、路径、配置和验证矩阵 | 是，已修复 |
| 6 | S2 | 第 2、15、18 节 | 完善修订历史、日志审计与指标低基数边界 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | 初审并修正 | 13（S0=2、S1=10、S2=1） | 13 | 0 |
| 2 | 2026-07-13 | Java 权威契约复核 | 1（S1=1） | 1 | 0 |
| 3 | 2026-07-13 | L0/L1、关联边界与 Markdown 静态终审 | 0 | 0 | 0 |

## 15. 最终结论

> 全集终态注记（2026-07-13）：本文保留该文档逐轮评审的时点记录；P1_V2/00～06 与 P2_V3/00～07 全集评审现已完成且 S0/S1=0。当前实施状态和授权边界以目标文档第 1、3、23、24 节为准，本文不构成 Approved 或 M0 授权。

文档通过品审，不阻断继续串行评审 `P1_V2/04_Adapter与DomainMetadata治理_L2实施详细设计_v2.0.md`。本次执行 3 轮；最终 S0、S1 均为 0。当前实现偏差必须由 P1_V2/06 原子迁移门禁统一关闭，禁止先发布半套安全链。
