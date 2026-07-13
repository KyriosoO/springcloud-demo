# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断继续串行评审：否；P1_V2/00～06 与 P2_V3/00～07 逐文档评审已完成
- 是否阻断编码：是；目标文档已通过品审，但全集仍为 In Review，尚未由用户确认 Approved，且 P1_V2 M2/M3、公共请求字段与配置原子切换尚未取得 M0 实施授权
- 审查类型：cross_layer
- 目标文档：`docs/design/P2_V3/02_文档Profile与有效资源预算_L2实施详细设计_v3.0.md`
- 上级文档：Agent 目标架构总览、契约与规划 L1、能力执行内核 L1、元数据与上下文安全 L1
- 直接前置：P1_V2/01～06、P2_V3/00～01
- 关联文档：P2_V3/03～07
- 实际审查轮次：5
- 主要风险摘要：Profile/index/provider/rollout 越界、独立 currentness、第二 Execution Config、资源/operational cap 混层、parent/child 双预算、选择/贡献环、双 projection 与 Execution requiredness 信息损失均已修复；目标文档无 S0/S1 遗留

## 2. 文档识别结果

- 识别文档类型：L2 Document Profile、Planning 安全投影与 capability resource contract 详细设计
- 识别依据：文档定义 exact Profile child asset、选择/投影/Raw Plan binding、`DocumentResourceLimit`、contribution adapters、配置迁移、实现落点和测试门禁
- 文档状态：In Review；用户已授权修改目标文档并执行最多 5 轮评审-修复
- 是否包含修改历史：是，已记录 5 轮实质评审-修复
- 是否存在上级文档：是，四份当前 L0/L1 为只读权威
- 是否存在关联文档缺失：否；04 的旧 `profileVersion/indexAlias/model` 请求结构已登记为后续串行目标，不反向放宽本文边界

## 3. 审查范围

| 序号 | 文档/实现 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---:|---|
| 1 | P2_V3/02 | 目标 L2 | 是，全文 | 评审并重写 Profile、Planning 投影和有效资源预算 |
| 2 | 四份当前 L0/L1 | 上级架构 | 是，相关章节 | 核对单 Agent、Future Multi-Agent、Runtime/Java 权威、Core/metadata 安全边界 |
| 3 | P1_V2/01～06 | 直接前置 | 是，相关章节 | 核对 ContractRef、PAI-1、exact Profile/Policy、单 Contract resolver、原子迁移 |
| 4 | P2_V3/00～01、03～07 | 同层关联 | 是，边界章节 | 核对 CorpusKey/alias、ACL、安全候选、编排、evidence/provider/rollout 所有权 |
| 5 | P2/02、P2_V2/02 及旧专题预算 | 历史来源 | 是，按主题核对 | 验证有效 Profile/预算内容已承接；未修改历史文档 |
| 6 | `AgentProfileDefinition`、`EffectiveProfile`、`AgentMetadataBundle`、`AgentPolicySnapshot` | 当前 metadata 实现 | 是 | 验证当前代码尚无目标 typed contribution/child evidence seam |
| 7 | 当前 `DocumentRetrievalProfile/Resolver`、`AgentProperties`、document handlers/providers/config | 当前 Document 实现 | 是，相关文件 | 识别 alias/provider/model/dimension/散预算混合和迁移落点 |

## 4. S0 阻断问题

复审后未发现遗留 S0。已关闭 6 项：

| 序号 | 原位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原 10.5～10.7 | Profile/limits 解析边界晚于 Runtime Plan，Runtime echo 可参与选择 | 不可信 Plan 反向成为授权/Profile/resource 输入 | 固定 capture→Route→Java selection→P1 freeze→projector→Runtime Plan |
| 2 | 原 10.7/11 | 新建 `ResolvedDocumentExecutionConfig` 并让 Validator/Handler/Projector 持有 | 侵入 P1 fixed Context，形成第二执行配置/状态事实源 | 删除该对象；Raw Plan 本地绑定，Validated Plan 仅带最小 execution projection |
| 3 | 原 10.5/13 | Document Profile 自建 profileVersion/reload snapshot/currentness | 与 exact AgentProfile/Policy currentness 分裂，Execution 无法证明同一版本 | 改为 parent exact ref 的 immutable child asset；无 latest/active/currentness API |
| 4 | 原 10.7 | request partial narrowing 未定义如何形成完整 P1 contribution | 用 0/MAX/null 会意外禁用或放大，P1 resolver 无法证明单调 | 以 pre-request upper bound 填未提供叶子，P1 resolver 独立重算并复核 |
| 5 | 第二轮 | selected child Profile 自带 `profileUpperBound` | 与 P1 parent typed PROFILE contribution 重复并形成先选择还是先贡献的环 | 数值只保留在 parent contribution；child asset 仅含策略并由 evidenceRef 引用 |
| 6 | 第四轮 | 总体图仍把 contribution 放在 selection 后，eligibility 又产生第二 projection | 实现可按两条时序或两个 projection 任取其一，PAI/Validator 绑定失真 | 重排为 capture contributions→selection→freeze→单次 projector；assembler 显式接收 final projection |

## 5. S1 严重问题

复审后未发现遗留 S1。已关闭 13 项：

| 序号 | 原位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原 5.1/10.1 | Profile 保存 indexAlias/schemaVersion | 与 01 Corpus Catalog 双权威，Profile 变更迫使索引耦合 | Profile 只保存 materialType/CorpusKey allowlist；alias/schema 归 01 |
| 2 | 原 10.1/10.6 | Profile 保存 provider/model/dimension | Provider transport 与 index manifest/策略混层 | provider/model 归 06，vector dimension 精确事实归 01 manifest |
| 3 | 原 10.1/10.6 | Profile 保存 qualityGate | 02 与 07 同时决定发布 | quality/Gold/rollout 全归 07；02 只输出 safe refs/digests |
| 4 | 原 10.2 | `maxProviderAttempts` 和四个 stage `Duration` 进入业务 limit | 授权预算、deadline 与 operational cap 混层，可产生 retry/timeout 多权威 | Document limit 只保留业务数量/字符/字节；attempt/timeout 归 P1/06 |
| 5 | 原 10.6 | `domain -> materialType -> profileName` 唯一键 | materialType 可能尚待 Plan 选择，Profile 无法稳定 Pre-Plan 解析 | 改为 domain/profileName；profile 含 allowed materialTypes，最终 Plan 选一个 CorpusKey |
| 6 | 原 10.8 | default 依赖 materialType 自动猜 Profile | 同一请求可随配置顺序选择不同 Profile | explicit 精确选择；缺省只允许 domain 唯一 default；失败不回退 |
| 7 | 原 10.2～10.3 | limit 扁平且混集合/boolean/Duration，维度和 0 语义不完整 | contract property、strictness、consumer coverage 无法证明 | 冻结单 Contract、4 个值分组、20 个稳定 dimension、逐叶 min/strictness/digest |
| 8 | 原 10.7 | caller 可禁 provider/channel，未区分策略与数值收窄 | set intersection 与数值 intersection 混成第二 contract 语义 | set/feature 进入 final projection；numeric narrowing 单独形成 REQUEST contribution |
| 9 | 第三轮 | Policy child ref/capture 时序不清 | resolver 可能读取 current Policy 或在 freeze 后重选 | Policy typed contribution/evidence 在 capture 固定；selection 只读 exact captured ref |
| 10 | 第三轮 | `DocumentExecutionProfileProjection` 未定义具体字段 | Handler 可能回读 Profile/config 或携带 alias/权限正文 | 冻结单 Corpus、具体 channels/algorithm/features/fields 的最小 projection |
| 11 | 第三轮 | feature policy 与 0 limit 语义未联合 | positive limit 被误当权限，required+0 运行时才异常 | 双门禁：policy 允许且 capacity>0；required+0 Pre-Plan 拒绝，optional+0 禁用 |
| 12 | 原 19/20 | 实现路径、consumer dimension 和配置迁移泛化 | 无法执行原子迁移，易残留 Handler/Projector 散预算 | 补 exact module/package/class、配置所有权、静态零残留和测试矩阵 |
| 13 | 第五轮 | Execution projection 将四类 feature 压成 boolean 且遗漏 requiredChannels | Handler 无法区分 required failure 与 optional degradation，只能回读 Profile 或自建策略副本 | 新增 requiredChannels；四类 feature 保留 closed policy，OPTIONAL+0 才转 DISABLED，REQUIRED+0 仍在 Planning 拒绝 |

## 6. S2 一般问题

复审后未发现遗留 S2。已关闭 3 项：

| 序号 | 原位置 | 问题 | 修复结果 |
|---:|---|---|---|
| 1 | 文档信息 | 把五份设计文件都称为 L0/L1，代码基线过旧 | 改为四份当前 L0/L1；证据优化方案仅为历史/关联来源；基线对齐 P2_V3 |
| 2 | 原 10.1/10.6 | profileVersion 使用未限定摘要或短截断实现 | 冻结 `DPROFILE-1`、稳定排序和完整 SHA-256 lowercase hex |
| 3 | 原 22～24 | 首轮直接写“通过”，未反映实际评审问题 | 记录每轮发现/修复，最终明确 4 轮与 S0/S1=0 |

## 7. S3 建议优化

暂无当前必须修改的 S3。不建议现在为 Profile 建数据库、独立配置服务、通用自由 Map extension 或 future Delegation/Run/Task 字段；这些会扩大单 Agent 阶段的层级和状态复杂度。

## 8. 架构设计审查结果

不适用；目标是 L2 详细设计。未发现必须修改 L0/L1 或 P1_V2 的遗留阻塞项。本文以 parent typed contribution 的 evidenceRef 引用 capability-specific child asset，不向 `AgentProfileDefinition`、`AgentPolicySnapshot` 或 P1 Core 增加 Document 专用字段，符合“当前单 Agent、未来 Multi-Agent 无大重构”的架构目标。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| Profile authority | 通过 | exact AgentProfile parent + immutable strategy child；无 independent latest/currentness |
| Selection | 通过 | Route 后、freeze 前 deterministic 选择；explicit/default/materialType/Policy 规则闭合 |
| Planning projection | 通过 | freeze 后单次 projector；不进 Runtime wire；assembler 绑定 final projection |
| Execution projection | 通过 | 单 Corpus、enabled/required channels、closed feature policies、算法/fields；无 alias/provider/权限正文 |
| Resource type | 通过 | Spring-free `DocumentResourceLimit`，4 个值分组、20 个稳定叶子 |
| Contract | 通过 | 单 ContractRef、validate/min/strictness/canonical digest 和 0 语义完整 |
| Contributions | 通过 | Definition + 三必需 source + optional Request；parent/child 无双预算 |
| Resolver/currentness | 通过 | P1 resolver 唯一求交/freeze/recheck；同值或更严格，否则 fail closed |
| Consumer closure | 通过 | Definition/Validator/Handler/Adapter/四 Provider/Result Security dimension coverage 完整 |
| 配置所有权 | 通过 | Profile、Corpus、ACL、Provider、rollout 和业务 limit 已有唯一归属 |
| 实现可执行性 | 通过 | exact 路径、迁移动作、架构门禁、测试和命令已列出 |
| Multi-Agent seam | 通过 | future source 仅由 P1 扩展 contribution/binding；Document contract/consumer 不变 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| L0/L1 | 通过 | Java 权威、Runtime 非授权、Core 无 Document 特例、exact metadata/currentness 一致 |
| P1_V2/01 | 通过 | 不增加 Runtime Plan wire；ContractRef/canonical/PAI-1 规则闭合 |
| P1_V2/02/03 | 通过 | 不增加第二 Context/Artifact；使用 exact Profile/Policy/Permission evidence 和 currentness |
| P1_V2/05 | 通过 | 单 Capability 单 Contract、三必需 source、optional Request、P1 唯一 resolver |
| P1_V2/06 | 通过 | P1 M2/M3、public contract/config 原子切换作为实施前置，未宣称可直接编码 |
| P2_V3/00 | 通过 | Pre-Plan Profile、server Raw Plan binding、01/02/03/05/06/07 所有权一致 |
| P2_V3/01 | 通过 | Profile 只产生 bounded CorpusKey；不拥有 alias/schema/physical target |
| P2_V3/03 | 待对齐 | 后续需消费同一 limits/profile/corpus binding，不把 ACL scope 当 resource contribution |
| P2_V3/04 | 已对齐边界 | 关联复审已要求 Validated Plan + CorpusKey/target binding，并据 requiredChannels/feature policy执行 closed failure matrix；04 仍在自身评审循环 |
| P2_V3/05/06 | 基本一致 | 已要求同一 ResourceLimitReference、Result Security 不读 AgentProperties、Provider request 不含 alias/profile；详细内容待后续串行评审 |
| P2_V3/07 | 基本一致 | 只引用 profileVersion/limit digest 做报告/change evidence；quality/rollout 不回流 Profile |
| 当前代码 | 有条件通过 | migration 差异已准确登记，不宣称 Implemented |

## 11. 是否建议进入后续阶段

- 是否建议继续评审下一份 L2：是，返回并继续 P2_V3/04 当前评审循环
- 是否建议进入编码实现：否；先完成 P2_V3/03～07 串行评审，并取得 P1_V2/06 M0 与 M2/M3 前置确认
- 是否建议先修订架构设计：否
- 是否建议先修订关联文档：是，继续修订 04～07；不得修改 L0/L1、P1_V2；02 已用第 5 轮完成必要关联闭合
- 是否需要用户确认：当前文档评审阶段无需新增确认

## 12. 用户确认项

当前无新增文档修改确认项。实施前必须单独确认：

1. public request 是否增加 requestedProfile/materialType/numeric narrowing 及 Java/OpenAPI/Python/fixtures 原子变更；
2. `AgentProperties` 与 `application-agent-document.yml` 的新旧 Profile/预算配置一次切换；
3. P1_V2 typed contribution/evidence/candidate closure seam 已实现并可供 P2 使用；
4. 公共/跨模块 ContractRef 与生成产物变更；
5. commit、push、PR 或发布。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 修订内容 | 是否阻断 |
|---:|---|---|---|---:|
| 1 | S0 | 9、10.1、10.3、10.9 | exact parent child evidence、capture→selection→freeze 无环时序、P1 唯一 resolver | 是，已修复 |
| 2 | S0 | 10.5～10.6 | 删除第二 Execution Config，冻结 single final projection/Raw Plan/PAI binding | 是，已修复 |
| 3 | S0 | 10.9 | 完整 REQUEST materialization 与 P1 independent strictness proof | 是，已修复 |
| 4 | S1 | 5～8、10.2、10.12 | 拆分 Profile/index/provider/ACL/rollout/operational cap 所有权 | 是，已修复 |
| 5 | S1 | 10.7～10.11 | 单 Contract、20 dimensions、双门禁、consumer closure | 是，已修复 |
| 6 | S1 | 19～20 | exact 实现路径、配置删除、架构和测试门禁 | 是，已修复 |
| 7 | S2 | 1～2、10.4、22～24 | 修正文档元数据、完整 canonical version 和真实复审记录 | 否，已修复 |
| 8 | S1 | 10.6、10.8、19～24 | Execution projection 保留 requiredChannels 与 closed feature policies | 是，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | L0/L1、P1、P2_V3/00/01 和当前实现交叉初审并整体重写 | 15（S0=4、S1=8、S2=3） | 15 | 0 |
| 2 | 2026-07-13 | parent contribution/child Profile source 复审 | 1（S0=1） | 1 | 0 |
| 3 | 2026-07-13 | Policy evidence、Execution projection、feature/limit 联合语义复审 | 3（S1=3） | 3 | 0 |
| 4 | 2026-07-13 | 全局时序与 single final projection 终审 | 2（S0=1、S1=1） | 2 | 0 |
| 5 | 2026-07-13 | P2_V3/04 关联复审触发 Execution requiredness 闭合 | 1（S1=1） | 1 | 0 |

## 15. 最终结论

> 全集终态注记（2026-07-13）：本文保留该文档逐轮评审的时点记录；P1_V2/00～06 与 P2_V3/00～07 全集评审现已完成且 S0/S1=0。当前实施状态和授权边界以目标文档第 1、3、23、24 节为准，本文不构成 Approved 或 M0 授权。

目标文档通过品审，不阻断返回并继续 `P2_V3/04_统一文档检索编排_L2实施详细设计_v3.0.md`。本次执行 5 轮，最终 S0=0、S1=0。Execution projection 已保留 requiredChannels 与 REQUIRED/OPTIONAL/DISABLED，Handler 无需回读 Profile 或自建失败策略。当前代码仍使用带 alias/provider/model/dimension 的旧 `DocumentRetrievalProfile/Resolver` 和散落 `AgentProperties`；这些是已登记的迁移差异，不是已通过的实现。未完成 P1_V2 M2/M3、公共契约授权和 P1_V2/06 原子切换前不得编码或激活半套配置。
