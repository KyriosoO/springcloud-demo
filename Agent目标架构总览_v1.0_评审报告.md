# 设计文档品审报告

## 1. 审查结论

- 结论：不通过（以“最终扩展为 Multi-Agent”为验收目标）
- 是否阻断后续编码：是，阻断 D06/Multi-Agent 详细设计与实现；不因本报告中的 S0 直接阻断 D01～D05 单 Agent 基础工作，但 D03 前必须解决本文列出的文档型生成能力 S1 冲突
- 审查类型：cross_layer
- 目标文档：
  - `docs/design/Agent目标架构总览_v1.0.md`
  - `docs/design/Agent能力执行内核架构设计_v1.0.md`
  - `docs/design/Agent契约与规划架构设计_v1.0.md`
  - `docs/design/Agent文档证据上下文优化方案.md`
  - `docs/design/Agent元数据与上下文安全架构设计_v1.0.md`
- 关联文档：仓库级协作约束、当前 Git 基线和目标文档引用关系；未扩大到修改或评审其他设计文档
- 实际审查轮次：1
- 主要风险摘要：前三份单 Agent L1 与 L0 的主链总体一致，核心运行时分层没有明显需要删除的多余服务层；当前不通过的主要原因是 Multi-Agent 权威 L1 缺失、文档型生成能力与输出信任模型未闭合、专项方案保留旧配置兼容并形成独立预算事实、以及当前仓库无法解析文档声明的代码基线 `472373e`。

## 2. 文档识别结果

- 识别文档类型：1 份 L0 架构总览、3 份 L1 分域架构设计、1 份未标级的 L2/实施型专项方案，整体属于跨层级一致性审查
- 识别依据：前四份架构文档明确声明 L0/L1、权威关系、职责与下位交付；`Agent文档证据上下文优化方案.md` 直接列配置、类、索引字段和运行参数，内容粒度属于实施设计或优化记录
- 文档状态：L0 标为“权威架构基线”，三份 L1 标为“架构基线（已评审）”；专项方案未声明状态
- 是否包含修订历史：5 份文档均没有规范修订历史表
- 是否存在上级文档：三份 L1 存在 L0；专项方案未声明上级架构、适用代码基线和替代关系
- 是否存在关联文档缺失：是。L0 明确把 `Multi-Agent协调与任务架构设计_v1.0.md` 设为 Coordinator、TaskRunner、ResultRef、Run/Task/Attempt 等唯一负责文档，但当前 `docs/design` 下不存在该文件

## 3. 审查范围

| 序号 | 文档 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---|---|
| 1 | `Agent目标架构总览_v1.0.md` | L0 目标架构 | 是，全文 | 全局边界、事实源、扩展不变量、Multi-Agent 顶层边界 |
| 2 | `Agent能力执行内核架构设计_v1.0.md` | L1 架构 | 是，全文 | Registration、Lifecycle、Core、Validator、Handler、Invocation |
| 3 | `Agent契约与规划架构设计_v1.0.md` | L1 架构 | 是，全文 | Java/Runtime 契约、Route/Plan、Planning、Prompt、repair |
| 4 | `Agent文档证据上下文优化方案.md` | 混合/L2 专项方案 | 是，全文 | 文档证据检索、生成上下文、引用展示与配置 |
| 5 | `Agent元数据与上下文安全架构设计_v1.0.md` | L1 架构 | 是，全文 | Profile、Policy、Authorization、Catalog、Domain metadata、Context |
| 6 | 当前 Git 基线与目标文件状态 | 关联证据 | 是 | 验证文档声明的代码基线和本轮是否改动目标文档 |

审查重点：架构边界、模块职责、单一事实来源、跨文档契约、冗余层级、Multi-Agent 可扩展性、权限与数据安全、deadline/取消/恢复、文档治理。

## 4. S0 阻断问题

| 序号 | 位置 | 问题 | 风险 | 修改建议 |
|---:|---|---|---|---|
| 1 | `Agent目标架构总览_v1.0.md` 第 10 节、第 13.1 节（482～532、588～595）；三份 L1 的“不负责内容”和 Multi-Agent 复用章节 | Multi-Agent 终态的唯一权威 L1 被声明但不存在。L0 只给出方向性骨架，并明确把 Coordinator、CoordinationPlanner、Run/Task/Attempt、Task Graph、claim/lease/retry、ResultRef、部分成功、Run 终态和 typed response 交给缺失文档定义。当前 5 份文档因此不能形成 Multi-Agent 闭环。 | 无法验证 Task Graph 状态机、调度并发、幂等/重试、租约丢失、依赖释放、结果传播、委派授权、部分成功和 Run 终结是否一致；直接进入 D06 会迫使详细设计或代码自行补架构决策，形成下位文档侵入上位边界。 | 在 D06 前先编写并评审 `Multi-Agent协调与任务架构设计_v1.0.md`。至少冻结：Run/Task/Attempt 状态机，控制/数据依赖，CoordinationPlanner 不可信输出校验，claim/lease/CAS/retry/cancel，ResultRef owner/schema/TTL/原子提交，Delegation 与稳定主体，partial-success 规则，资源预算/最大深度/扇出/并发，typed response，以及它与 Lifecycle/Task State Boundary 的事务归属。 |

## 5. S1 严重问题

| 序号 | 位置 | 问题 | 风险 | 修改建议 |
|---:|---|---|---|---|
| 1 | `Agent文档证据上下文优化方案.md` 第 1～2 节（5～32）；`Agent能力执行内核架构设计_v1.0.md` 第 13.1～13.2 节（805～829）；`Agent元数据与上下文安全架构设计_v1.0.md` 第 8.5 节（449～457） | 文档专项方案要求 LLM 使用证据生成内容，但执行内核要求 summary/message 只能从过滤后的结构化结果和安全模板生成或重建，并明确“不信任 Handler 自由文本”。专项方案没有定义“LLM 生成候选文本”如何成为可验证的 typed output，也没有定义 generation port 属于何种受信边界。 | 文档回答/摘要能力要么无法满足上位架构，要么实现时绕过 output ContractRef、citation 绑定、字段过滤和 mask。进入 Multi-Agent 后，该自由文本还可能经 ResultRef 或汇总链放大泄漏和幻觉风险。 | 先在上位 L1 明确一种口径：推荐新增“类型化生成候选（text + citation bindings + authorized evidence refs + generation metadata）”，由 capability-specific 但受统一 Result Security Boundary 管理的 projector 校验证据归属、引用完整性、输出预算和 fallback/refuse，校验后才形成最终文本；同时明确 generation/embedding/rerank port 不是 Planning Runtime，不得绕过 absolute deadline、取消、凭据和审计边界。若不接受该扩展，则专项方案只能改为确定性模板输出。此项需要修改上位文档，必须另行授权。 |
| 2 | `Agent文档证据上下文优化方案.md` 第 2、4 节（16～24、64～90）；`Agent元数据与上下文安全架构设计_v1.0.md` 第 6.1、7.1、8.2 节（300～307、336～355、413～425） | `max-generation-evidence-count`、`max-display-citation-count`、`max-summary-document-count` 被直接定义为 capability 配置并分别由 Handler、ResultSecurityProjector、Validator 消费，但没有说明它们是 Definition 固有约束、Profile 组合上限、Policy 部署上限还是请求级限制，也没有纳入 Authorization Snapshot/Effective Scope 的最严交集。 | 配置成为 Profile/Policy/Authorization 之外的第二预算或安全事实源；不同组件可能使用不同值，导致 Validator 放行、Handler 截断和安全投影不一致。Multi-Agent 多 Task 并发时还会失去 Run/Task 总预算约束。 | 为每个预算标注唯一所有者和计算公式。例如：固有结构上限归 Definition/ContractRef，Agent 行为上限归 Profile，部署与安全上限归 Policy，请求值只能收紧；最终 `effectiveLimit = min(definition, profile, policy, request, run/task budget)`，并把实际值绑定到 Snapshot/Execution Context。专项文档只保留推荐实例值，不再定义权威规则。 |
| 3 | `Agent文档证据上下文优化方案.md` 第 2 节（24、32、44～46）；`Agent目标架构总览_v1.0.md` 文档前提和非目标（7、70、116）及第 13.2 节（624） | 专项方案保留旧参数绑定、旧字段/旧索引兼容路径并以“生产别名切换”为语境；L0 则明确系统未投产、不承担旧契约/配置/数据库兼容，并要求 D03 纵向原子切换和旧路径删除。专项方案没有状态、适用阶段或到期条件，因此两套前提同时有效。 | D03 可能遗留兼容 setter、旧字段 fallback 和双索引语义，违反单一事实来源与原子切换；后续维护者无法判断哪些兼容逻辑必须删除。 | 明确专项方案是“历史已实施记录”“D03 前临时过渡”或“目标 L2”。若作为目标设计，删除旧配置/旧索引兼容；若必须临时保留，单列到期阶段、删除清单和不得进入 D03 最终态的门禁。 |
| 4 | `Agent能力执行内核架构设计_v1.0.md` 第 8.3、10.1、14.1、14.3 节（431～450、578～589、890、974～990） | 架构把“同一个 `ExecutablePlanningResult` 实例”作为安全不变量，同时 checkpoint 不保存完整 Raw Plan，崩溃后只允许终结失败。Java 对象实例身份属于进程内实现细节，不是可持久、可跨 worker 验证的架构身份。 | 单 Agent 同进程可运行，但 Multi-Agent claim/lease、worker 重启或未来进程拆分时无法恢复已规划 Attempt；只能重新规划并产生非确定性、额外成本和重复外部调用。若开发者误把对象身份换成字段复制，又会绕过原设计的绑定保护。 | 把不变量改为“同一 Attempt 内不可替换的 planning artifact/opaque handle”，明确其 identity、canonical digest、Registration/version/correlation 绑定及是否持久化。D06 必须明确选择：Attempt 崩溃后一律新 Attempt 重规划，或持久化可验证 artifact 后恢复；不要把 JVM object identity 写成跨阶段架构契约。 |
| 5 | `Agent文档证据上下文优化方案.md` 第 2～5 节（32、44～60、83～108）；`Agent元数据与上下文安全架构设计_v1.0.md` 第 8.5、18.1、18.4 节 | 专项方案定义 `before/after-chunks`、`citationText`、`generationText`、`embeddingText`，但只在验证口径中提到 ACL 泄漏，没有在设计中规定：上下文窗口必须同文档且同授权范围、进入 LLM 前必须先做候选级安全投影、派生文本必须绑定精确来源 span、引用展示不得引用窗口外文本。 | 相邻 chunk 或富化文本可能把未授权内容带入生成输入；检索命中可能来自 `embeddingText/generationText` 中无法由 `citationId` 精确证明的内容；Multi-Agent 汇总和 ResultRef 传播会扩大影响。 | 增加前置安全与溯源不变量：先 ACL/字段级过滤再扩展/打包；窗口不得跨 document/security boundary；每个派生文本保存 source chunk/span 列表；citation 必须指向实际支持文本；`embeddingText` 只用于召回解释，不作为可展示证据；增加跨 ACL 邻接 chunk、派生文本命中但主 chunk 不命中的失败测试。 |
| 6 | 四份 L0/L1 文档头部的“适用代码基线”（L0 5；执行 L1 7；契约 L1 6；元数据 L1 7） | 文档共同声明适用 `472373e` 及其“后续同源提交”，但当前仓库无法解析对象 `472373e`，且“后续同源提交”没有可判定边界。 | 已评审架构无法与当前代码建立可复现关联；后续任意提交都可能被误认为仍在已评审基线内，文档结论失去时效性。 | 改为当前仓库可解析的完整 commit SHA，并记录评审日期；如涉及多个独立仓库/模块，分别列出 repo + commit。删除“及其后续同源提交”，后续变更通过影响分析和修订历史更新适用基线。 |

## 6. S2 一般问题

| 序号 | 位置 | 问题 | 风险 | 修改建议 |
|---:|---|---|---|---|
| 1 | L0 第 7 节（309～415）、执行 L1 第 14 节（865～990）、契约 L1 第 7.4 节（501～588）、元数据 L1 第 15 节（809～934）；L0 第 13.1、15 节（595、660） | 四份文档重复维护完整调用链、失败分支、deadline、扩展不变量和验收条目，与“一个概念只能由一个 L1 完整定义，其他文档引用”的维护规则不完全一致。运行时没有多余服务层，但文档层存在明显重复。 | 同一节点或顺序调整需要同步 3～4 处，容易产生隐性漂移；“都已评审”会掩盖未来差异。 | L0 只保留顶层骨架；契约 L1 只展开 Route/Plan 子链；执行 L1 只展开 checkpoint/Core/finalization 子链；元数据 L1 只展开授权、Context、Binding 和 filtering 参与点。其他位置引用 owner 章节和 AD/EK/CP/MS 编号。 |
| 2 | 四份 L0/L1 末尾的“最终跨文档评审结论”（L0 667；执行 L1 1331；契约 L1 1227；元数据 L1 1303）及所有文档头部 | 文档以正文永久声明“无未决冲突”，但没有评审人、轮次、输入版本和修订历史；专项方案甚至没有状态。该声明还与当前不可解析的代码基线并存。 | 评审结论无法审计，也会随文档后续编辑自动失真。 | 增加修订历史和独立评审记录，记录 commit、文档 hash、评审人/日期/结论/遗留项；正文只保留当前状态引用，不永久写“无冲突”。 |
| 3 | L0 第 13.2 节及三份 L1 的交付顺序 | 交付标识按 `D01 → D02 → D04 → D03 → D05 → D06` 执行，编号与拓扑顺序不一致。文档虽解释 D01～D06 是阶段，但持续重复非单调顺序。 | 计划、自动化门禁和沟通容易误按数字排序，导致 D03 在 D04 前被误启动。 | 在尚未形成大量外部依赖时重编号；若不能重编号，增加唯一 `stageOrder`/前置矩阵，并在所有文档只引用一处权威顺序，不再重复 ASCII 链。 |
| 4 | `Agent文档证据上下文优化方案.md` 全文，尤其标题、第 2 节和第 4 节 | 专项方案混合目标、类级改动、配置、索引迁移和运行参数，但没有 L0/L1/L2 层级；“证据上下文”也没有与架构中的 `Capability Context`、`Context Snapshot`、`Context View`、未来 `ResultRef` 明确区分。 | 后续设计可能把临时 LLM evidence payload 当作可持久化 Capability Context，或误以为该专项方案可以改变上位安全边界。 | 将其定位为 Document capability 的 L2/实施记录，声明上位文档与适用阶段；把 `DocumentEvidenceContextPacker` 产物明确命名为 invocation-local generation evidence payload，禁止持久化、继承或替代 Context/ResultRef。 |
| 5 | `Agent元数据与上下文安全架构设计_v1.0.md` 第 8.1～8.4、20.1 节（401～447、1144～1155） | Multi-Agent 后台授权依赖稳定 Execution Subject/Run Owner Reference 和 User Permission evidence/version，但外部 IAM 合约被排除在本文之外，当前文档集没有给出最小跨服务契约。 | 用户禁用、租户迁移、权限源无单调版本、服务身份与用户身份混用时，Task 重试和 Execution 复检行为无法确定。 | 在 Multi-Agent L1 中定义 IAM port 的最小语义：稳定 subject/tenant、evidence version 或不可变 proof reference、撤权可见性、主体失效、超时/不可用 fail-closed、审计关联；不要求修改外部 IAM 内部模型。 |

## 7. S3 建议优化

| 序号 | 位置 | 建议 | 价值 |
|---:|---|---|---|
| 1 | L0 与各 L1 | 增加一张“事实源—请求级投影—消费者—禁止反向写入”的跨文档索引表，只放引用，不复制定义。 | 降低 Available Capability、Snapshot、View、Schema、Binding 等概念的理解成本。 |
| 2 | Multi-Agent 前置验收 | 增加架构级场景矩阵：worker 崩溃、lease 丢失、取消与成功竞争、权限撤销、ResultRef 提交失败、依赖 Task 部分成功、deadline 耗尽、Coordinator 重启。 | 在写 L2 前验证状态所有权和 CAS/事务边界是否闭环。 |
| 3 | ADR 治理 | 为“只读能力不恢复已规划执行”“Planning artifact 是否持久化”“Coordinator 是否保持进程内”“生成式文本安全模型”分别建立 ADR。 | 把当前隐含取舍变成可审计、可演进的决策，避免通过代码旁路改变架构。 |

## 8. 架构设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 架构目标 | 不通过 | 单 Agent capability-first 目标清晰，但 Multi-Agent 最终目标缺少唯一负责 L1 |
| 系统边界 | 有条件通过 | Java/Runtime/Adapter/Business Service 边界清晰；generation/embedding 等 capability-local 外部端口未纳入统一模型 |
| 模块职责 | 有条件通过 | Planning/Lifecycle/Core、Registry/Catalog、Profile/Policy 的拆分合理，不建议为“简化层级”合并；专项方案职责归属不清 |
| 依赖方向 | 通过 | 核心四文档保持 Runtime 不可信、Adapter 不反向依赖 agent-service、业务服务为数据权威 |
| 技术选型 | 有条件通过 | Java 单向契约生成合理；PlanningResult 对象实例身份属于过度实现化约束 |
| 一致性模型 | 不通过 | 单 Agent 本地事务/CAS 较完整；Multi-Agent Run/Task/Attempt/ResultRef 一致性模型尚未定义 |
| 幂等与补偿 | 不通过 | 单 Agent 只读恢复边界明确；Multi-Agent claim/lease/retry、ResultRef 原子性和部分成功未闭合 |
| 权限与审计 | 有条件通过 | Snapshot + 当前复检主链一致；后台主体/IAM 最小契约和证据上下文前置安全不足 |
| 非功能需求 | 不通过 | absolute deadline 较完整，但 Multi-Agent 并发、扇出、成本、背压、资源配额和调度公平性缺失 |
| 风险与取舍 | 有条件通过 | 多处写明 fail closed 和不提前拆微服务；关键取舍没有 ADR，专项方案兼容前提冲突 |

## 9. 详细设计审查结果

`Agent文档证据上下文优化方案.md` 实际属于混合/L2 专项设计，因此补充以下判断：

| 检查项 | 结论 | 说明 |
|---|---|---|
| 上级设计承接 | 不通过 | 未声明上级 L0/L1、适用阶段和替代关系 |
| 文件路径 | 不通过 | 仅给类名和一个脚本名，没有完整路径/模块归属 |
| 类与方法 | 有条件通过 | 指定 Handler/Validator/Projector/Packer，但未给方法级接口 |
| 入参与返回类型 | 不通过 | `citationText/generationText/embeddingText` 缺类型、可空性、长度和来源 span 合约 |
| 接口契约 | 不通过 | 未说明 generation port、索引 API、错误码和响应 ContractRef |
| 数据结构 | 有条件通过 | 给出派生字段意图，但 provenance/ACL/schema version 不完整 |
| 校验逻辑 | 有条件通过 | 有数量和验证口径，缺 Effective Scope 最严交集和跨 ACL 窗口校验 |
| 异常处理 | 不通过 | 未定义 LLM/索引/上下文窗口失败、fallback/refuse、取消和迟到结果 |
| 状态流转 | 不适用 | 本文不应自行定义 Invocation 状态，但需引用 Lifecycle 终结语义 |
| 数据库设计 | 不适用 | 涉及 ES mapping/alias，不涉及 Agent DB；仍需明确索引迁移和回滚边界 |
| 缓存与消息 | 不适用 | 未涉及 |
| 权限、审计、幂等、风控 | 不通过 | 只有 ACL 泄漏验证项，没有设计级前置安全与审计闭环 |
| 测试设计 | 有条件通过 | 有验证方向和 gold query，但缺失败、取消、权限撤销、跨边界窗口、derived text provenance 测试 |
| 可编码性 | 有条件通过 | 可以指导局部改动，但不能作为新目标架构下的直接编码依据 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| 需求到架构一致性 | 不适用 | 未提供独立需求文档；以用户“最终扩展为 Multi-Agent”为最高目标 |
| 架构到详细设计一致性 | 不通过 | 文档专项方案与兼容策略、预算所有权、生成式输出信任模型不一致 |
| 接口契约一致性 | 有条件通过 | 三份核心 L1 的 Route/Plan/PlanningResult/Execution 边界一致；专项方案缺 ContractRef 与 generation port 契约 |
| 代码结构一致性 | 无法完整确认 | 当前仓库存在对应 Document capability 类和配置，但文档声明的 `472373e` 无法解析，不能声称基线一致 |
| 权限与审计一致性 | 有条件通过 | 核心 L1 一致；证据生成前置安全和后台 IAM 契约未闭合 |
| 一致性模型一致性 | 有条件通过 | 单 Agent 一致；Multi-Agent 缺失 |
| 风控策略一致性 | 不通过 | Multi-Agent 资源/部分成功/结果传播策略缺失；生成式文本安全模型冲突 |
| 测试范围一致性 | 有条件通过 | L1 给出验收原则，专项方案和 Multi-Agent 场景测试不足 |

## 11. 是否建议进入后续阶段

- 是否建议进入详细设计：单 Agent D01～D05 可按既有门禁继续；不建议进入 D06/Multi-Agent 详细设计
- 是否建议进入编码实现：不建议直接按当前 5 份文档实现 Multi-Agent；文档型生成能力在 D03 前也应先消除 S1 冲突
- 是否建议先修订架构设计：是，先补 Multi-Agent L1，并修订生成式输出、外部生成端口和 planning artifact 身份边界
- 是否建议先修订详细设计：是，随后把 `Agent文档证据上下文优化方案.md` 重新定位为受 L0/L1 约束的 L2/历史实施记录
- 是否需要用户确认：是，涉及修改上位 L0/L1 和专项方案，当前未获授权，本轮未修改

## 12. 用户确认项

| 序号 | 确认问题 | 影响范围 | 建议选项 |
|---:|---|---|---|
| 1 | 是否授权新增 `Multi-Agent协调与任务架构设计_v1.0.md` 并将其作为 D06 前置架构基线 | L0 引用关系、三份 L1 seam、未来 D06 | 建议授权，先完成架构设计再做详细设计 |
| 2 | 文档型 LLM 生成文本是否作为正式 capability 输出保留 | 执行内核输出信任模型、Result Security、Document capability | 建议保留，但必须定义 typed generated candidate + evidence/citation security projector |
| 3 | 专项方案中的旧配置/旧索引兼容是否只属于历史过渡 | `Agent文档证据上下文优化方案.md`、D03 删除边界 | 建议标记历史或在 D03 删除，不进入目标架构 |
| 4 | Multi-Agent 首版是否明确限定为只读、同 Agent DB、Attempt 崩溃后重新规划 | Run/Task/Attempt 恢复、写操作、部署边界 | 建议首版明确限定，并为后续写操作/跨进程恢复保留 ADR 门禁 |

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 建议修改内容 | 是否阻断 |
|---:|---|---|---|---|
| 1 | S0 | 新增 Multi-Agent L1 | 补齐 Coordinator/Task/ResultRef/状态与可靠性闭环 | 是，阻断 D06 |
| 2 | S1 | 执行内核 L1 + 元数据安全 L1 | 定义生成式候选文本、证据绑定和安全投影边界 | 是，阻断相关 capability 的目标态切换 |
| 3 | S1 | 元数据安全 L1 + 专项方案 | 统一 evidence/display/summary 预算的事实所有权与最严交集 | 是，阻断专项方案作为目标态依据 |
| 4 | S1 | 专项方案 | 消除或限定旧配置/旧索引兼容，声明文档状态和上级关系 | 是，阻断 D03 最终态 |
| 5 | S1 | 执行内核 L1 + Multi-Agent L1 | 用 attempt-scoped artifact identity 替代 JVM 实例身份 | 是，阻断可恢复/可调度 Multi-Agent 设计 |
| 6 | S1 | 专项方案 | 增加 generation 前置 ACL、窗口边界和 provenance 合约 | 是，阻断安全验收 |
| 7 | S1 | 四份 L0/L1 头部 | 更新为当前可解析的精确代码 commit | 否，但阻断“已验证当前代码一致”的结论 |
| 8 | S2 | 四份 L0/L1 | 去除重复全链，按 owner 文档引用 | 否 |
| 9 | S2 | 全部文档 | 增加修订历史、评审记录、状态和替代关系 | 否 |
| 10 | S2 | L0 交付顺序 | 修正非单调编号或增加唯一 stageOrder | 否 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | 初审，仅评审不修改目标文档 | 15（S0 1、S1 6、S2 5、S3 3） | 0 | 15 |

## 15. 最终结论

这 5 份文档不能作为“Multi-Agent 最终目标架构已闭合”的通过基线。L0 与三份单 Agent L1 的主要职责边界、依赖方向、授权复检、Context 时序和原子终结设计总体一致，`Capability Registry`/`Capability Catalog`、`Profile`/`Policy`、`Context Snapshot`/`Context View` 等拆分有明确事实源或信任边界依据，不建议仅为减少类或层级而合并。

当前最优先事项不是继续增加 L2 或编码，而是补齐 Multi-Agent 权威 L1，并先解决 Document capability 的生成式输出与统一安全边界冲突。`Agent文档证据上下文优化方案.md` 应降级/重定位为受上位架构约束的 L2 或历史实施记录，不能继续与 L0/L1 并列作为目标架构事实源。本轮未修改任何目标文档或代码，只新增本评审报告。
