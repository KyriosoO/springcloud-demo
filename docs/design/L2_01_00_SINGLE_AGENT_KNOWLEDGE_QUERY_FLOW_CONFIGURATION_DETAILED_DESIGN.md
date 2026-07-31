# [L2_01_00] 单体 Agent Knowledge 查询流程与配置详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Knowledge 查询流程与配置详细设计 |
| 文档标识 | `SA-L2-KNOWLEDGE-FLOW-001` |
| 文档编号 | `L2_01_00` |
| 文档路径 | `docs/design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 五轮独立评审通过，`REV-KFLOW-001`～`021` 全部关闭 |
| 当前版本 | v0.2 |
| 日期 | 2026-07-25 |
| 适用范围 | Python `agent-runtime` 内唯一 `knowledge.query` 能力的参数契约、请求级流程状态、问题改写、首批逻辑知识域、域选择、检索计划、跨域失败优先级、配置与组合根 |
| 上位文档 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v1.3；[`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v0.5；[`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v0.3（已评审/已通过，`KQ-GATE-001` 已关闭） |
| 直接依赖 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4（Approved）的能力 API、`original_question` 与公共结果；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v0.4（Approved）的输入闸门、模型上下文与受控结构化任务 |
| 下位/后续契约 | [`L2_01_01`](L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) v0.2 Approved；规划中的 `L2_01_02` Knowledge 证据、出域、摘要与效果验证 |
| 实现基线 | 当前工作区不存在目标 `agent-runtime`、Knowledge Capability、Knowledge Adapter 或目标 Python 测试；既有 `es-query-*` 与历史 Agent 代码只作为迁移输入，不是目标实现基线 |
| 是否可作为实现依据 | 否 |
| 当前允许实施范围 | 本文编写、自检、契约样例和使用内存 fake stage 的隔离推演 |
| 当前禁止动作 | 创建或修改目标代码、配置、测试、ES/BGE/DeepSeek 公共契约；启用真实知识链路；关闭实施、集成或效果门禁 |
| 修改权限 | 本轮用户已授权第三批 L2 评审与必要直接关联文档原子同步，并授权 Git commit/push；代码、配置、Schema、外部契约和真实数据调用未获授权 |
| 维护责任人 | 项目维护者（个人开发者，姓名未在需求中指定） |

> 本文只拥有 Knowledge 单动作内部的流程与配置，不拥有物理索引、ES/BGE 协议、统一候选字段、证据出域字段或摘要事实校验。v0.2 的 Approved 来自五轮独立评审；它不构成实现授权或真实链路可用证据。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 执行第二批 L2 详细设计 | 创建 `knowledge.query` 空参数动作、原始问题同源消费、问题改写、税务政策/税务法律两域、确定性域选择、检索计划、失败优先级、配置、组合根和实现/测试追踪 |
| 2 | 2026-07-25 | 1、4、8～10、13～17 | 作者第 1 轮自检修复 | 将原始问题来源收敛到 `CapabilityExecutionContext.original_question`，把物理检索/候选/证据字段留给后续 L2，并补齐阶段协议、部分成功阈值、失败映射与门禁 |
| 3 | 2026-07-25 | 7、9、12、14、17～19 | 作者第 2～3 轮自检与严格校验修复 | 明确禁止反向依赖、错误码/一致性/安全审计术语，固定非税问题仍按 L1 顺序只改写一次，补充安全 `ModelCallContext` 投影，并将候选/部分成功配置改为只能从代码上限收紧 |
| 4 | 2026-07-25 | 1、5、7～14、16～20 | 独立评审第 1 轮修复 | 同步直接依赖 Approved 状态；引入最小 retrieval/evidence context、显式问题出域判定和 typed evidence result；对齐模型 task/context 契约，闭合域词表/匹配、依赖禁令和 Provider 签名 |
| 5 | 2026-07-25 | 8～14、18～20 | 独立评审第 2 轮修复 | 补齐 rewrite/stage tagged union、有限失败码和公共映射；以绝对 phase deadline 强制子预算；冻结保护项提取、目录/配置版本及集合上限 |
| 6 | 2026-07-25 | 8.2、10.2～10.3、11.3、12.1、13～14、18～20 | 独立评审第 3 轮修复 | 对齐核心 descriptor；闭合 coverage 完备分区和无存在性泄漏语义；固定环境解析；消除 Knowledge task 与 model registry 装配歧义 |
| 7 | 2026-07-25 | 8.3～8.4、12.1、13.3、14、18～20 | 独立评审第 4 轮修复 | 补齐逻辑域允许路径与默认出域策略引用；修正部分成功阈值依赖校验；增加 retrieval 唯一公共映射签名 |
| 8 | 2026-07-25 | 1～20 | 独立评审第 5 轮终审 | 全量复核无新增 S0/S1/S2，关闭 `REV-KFLOW-001`～`021`，版本升为 v0.2、状态改为 Approved；实施与真实链路门禁保持 Open |
| 9 | 2026-07-25 | 1、14 | 第二批 L2 终审状态原子同步 | 明确当前 Approved 评审依据，并同步跨 L2 人工验证状态；不改变 Knowledge 流程契约或开放门禁 |
| 10 | 2026-07-31 | 1、5、14、18、20 | 第三批 L2 状态原子同步 | 将 `L2_01_01` 更新为 v0.1 Draft/三轮内审完成，保留 `L2_01_02` 未创建及全部实施/集成门禁 Open；不改变本文 Approved 设计语义 |
| 11 | 2026-07-31 | 1、5、14、18、20 | 第三批 L2 终审状态原子同步 | 将上位引用同步为 `REQ_00` v1.3、`L0_00` v0.5、`L1_01` v0.3，并将 `L2_01_01` 更新为 v0.2 Approved/五轮评审通过；确认两级 Profile 映射不改变本文只生成逻辑域检索计划的边界，全部实施/集成门禁保持 Open |

## 3. 背景、目标与范围

### 3.1 背景与问题

L1_01 已确定知识查询必须在一个 `knowledge.query` 动作内完成问题改写、多域、多路召回与重排、证据化摘要，但当前目标 Python 工程尚不存在。若直接实现，容易出现以下问题：

1. 把动作选择模型返回的文本误当成原始问题，无法验证改写是否保持原意。
2. 把 ES 索引或任意配置值当作逻辑知识域，导致业务语义与基础设施绑定。
3. 把“多域”“多路”拆成多个 Agent 动作，破坏核心单动作约束。
4. 由不同下游失败临时决定最终状态，造成 `forbidden`、技术失败和 `no_result` 相互覆盖。
5. 让配置增加域、路径或协议，而不是只收紧代码绑定能力。

### 3.2 目标与验收行为

| 需求编号 | 目标或用户可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-KFLOW-001` | Knowledge 对核心只暴露一个稳定只读动作 | 注册表只出现 `knowledge.query`；问题改写、域选择和多路检索不增加动作次数 | REQ_00 FR-02/FR-06；L1_01 `SA-C-002` |
| `REQ-KFLOW-002` | 问题改写保留权威原问题及关键法律语义 | handler 只从执行上下文取得原问题；候选数量/长度受限；数字、日期、文号、条款和否定约束不丢失 | REQ_00 FR-02；L1_01 7.1～7.2 |
| `REQ-KFLOW-003` | 首批具备可验证的单域和多域选择 | 代码绑定 `tax.policy`、`tax.law`；测试覆盖各单域、双域、零域、禁用域和非法域 | L1_01 7.3、13.1 |
| `REQ-KFLOW-004` | 每个已选域形成有限关键词与向量检索计划 | 同一动作最多 2 域×2 路径；计划不含物理索引、DSL、URL、模型地址或任意过滤表达式 | L1_01 7.4、9.1 |
| `REQ-KFLOW-005` | 跨域与跨路径失败具有固定优先级 | 整域拒绝、读取判定不可验证、整体失败、无结果和部分成功不能相互伪装；组合矩阵可参数化验证 | L1_01 9.2 |
| `REQ-KFLOW-006` | 配置只能启停或收紧代码绑定能力 | 未知域、重复域、越界阈值、缺必需路径或半有效依赖均阻止 Runtime readiness | REQ_00 CFG-01～04；L1_01 6.3 |
| `REQ-KFLOW-007` | Knowledge 流程状态只存在于当前 handler 调用 | 不进入 LangGraph state、checkpoint、cache、数据库或日志正文；请求结束后无残留 | L1_01 8、9.3 |
| `REQ-KFLOW-008` | 后续检索/证据实现可替换而不侵入核心或本流程 | 本流程只依赖两个窄 stage Protocol；fake 与真实 stage 使用同一输入输出，不要求核心识别 Knowledge | REQ_00 EXT-01/02；L1_01 `SA-C-010/014` |
| `REQ-KFLOW-009` | 总预算、取消和模型调用保持有界 | 改写最多一次模型调用；每阶段有子预算；取消/截止后不安排下一阶段；本流程不自动重试 | L1_01 10.3；L2_00_01 `DR-CORE-009` |

### 3.3 范围内

- `knowledge.query` 描述、空参数 Schema、强类型 validator 和 handler。
- 原始问题同源消费、确定性规范化、受控改写候选、语义约束检查和原问题回退。
- `tax.policy`、`tax.law` 两个逻辑域的语义目录、启用快照和确定性选择规则。
- 关键词/向量检索意图、计划顺序、数量和部分成功充分性配置。
- 请求级内部阶段状态、阶段 Protocol、调用顺序、超时/取消及公共失败映射。
- Knowledge 配置加载、启动校验、组合根注册和模型无关测试替身。

### 3.4 范围外

- 逻辑域到 ES 索引/只读别名/字段的映射、ES 请求、统一候选、Embedding/Rerank Provider、融合/去重/重排算法；归 `L2_01_01`。
- 文档读取权威的提供方协议及候选正文返回前的授权实现；归 `L2_01_01` 与对应提供方契约。
- 证据字段、三层出域策略、模型安全载荷、摘要 Prompt、事实锚定和 P5 效果指标；归 `L2_01_02`。
- DeepSeek URL、凭证、HTTP DTO、通用输入闸门和 Provider 错误；归 `L2_00_02`。
- Spring 接入、JWT 验签、外部/内部 HTTP；归 `L2_00_00`。
- 文档录入、索引写入、聚合查询、业务查询、写操作、Multi-Agent、持久记忆和生产级韧性平台。

### 3.5 适用技术剖面

| 剖面 | 适用性 | 说明 |
|---|---|---|
| Python | 适用 | Knowledge 流程、契约、配置和测试均为建议新增 Python 模块 |
| Java/外部 HTTP | 不适用 | 本文不新增 Java 类、方法或 HTTP 字段；跨进程入口由 `L2_00_00` 定义 |
| 配置 | 适用 | Python 启动环境加载、强类型校验、冻结、重启生效 |
| 状态/并发 | 适用 | 单请求阶段状态、截止时间、取消和迟到结果丢弃；无共享可变领域状态 |
| 权限/敏感数据 | 适用 | 原始问题、用户 JWT、逻辑域及下游读取授权边界必须隔离 |
| 数据库/索引/消息 | 不适用 | 本文不新增持久化或修改 ES；只产生逻辑检索计划 |
| 测试 | 适用 | 单元、契约、架构及 fake stage 集成测试 |
| 发布/回滚 | 适用 | 能力默认禁用，配置错误不就绪，无数据迁移 |

### 3.6 完成判定

本文达到“可进入独立正式评审”的条件为：

1. 所有范围内 REQ/CON 均追踪到设计规则、实现落点、测试和验证。
2. 原始问题、改写候选、逻辑域、计划、阶段结果和公共状态字段明确。
3. 单域、多域、零域、禁用/非法域及全部跨域失败优先级可确定性推演。
4. 物理检索、候选和证据字段没有被本文越权定义。
5. Python 公共类型和边界关键函数具备建议路径、签名、输入、输出、错误、异步及消费者。
6. 作者自检无遗留 Blocker/Major，严格文档校验 0 errors、0 warnings。

## 4. 上位约束与追踪关系

### 4.1 约束映射

| 约束编号 | 上位文档/契约位置 | 约束内容 | 本设计落实方式 | 偏离情况 |
|---|---|---|---|---|
| `CON-KFLOW-001` | L1_01 `SA-C-001/002/019` | 一个逻辑 Agent、一个 Knowledge 动作，内部阶段不取得图编排权 | `DR-KFLOW-001`、`DR-KFLOW-012` | 无 |
| `CON-KFLOW-002` | L1_01 7.1～7.2；L2_00_01 v0.4 | 原始问题与改写关联，原问题不能由模型候选重建 | `DR-KFLOW-002`、`DR-KFLOW-003` | 无 |
| `CON-KFLOW-003` | L1_01 7.3 | 域只能来自已注册且启用的逻辑域目录 | `DR-KFLOW-004`、`DR-KFLOW-005` | 无 |
| `CON-KFLOW-004` | L1_01 7.4～7.5 | 每域至少关键词/向量两路，禁止暴露物理资源和 DSL | `DR-KFLOW-006` | 无 |
| `CON-KFLOW-005` | L1_01 9.2 | 读取拒绝/不可验证/技术失败/无结果及部分成功必须区分 | `DR-KFLOW-007`、`DR-KFLOW-008` | 无 |
| `CON-KFLOW-006` | L1_01 `SA-C-006`、6.3 | 配置只能启停/收紧，不能增加域、协议或授权 | `DR-KFLOW-009` | 无 |
| `CON-KFLOW-007` | L1_01 8、9.3 | 状态请求内、只读、无持久化或副作用 | `DR-KFLOW-010` | 无 |
| `CON-KFLOW-008` | L1_01 10.3 | 子预算有界、取消后停止新增工作、不实现重试平台 | `DR-KFLOW-011` | 无 |
| `CON-KFLOW-009` | L1_01 13.3 | 本文决定何时调用检索/模型，不定义提供方协议 | `DR-KFLOW-012`、`DR-KFLOW-013` | 无 |
| `CON-KFLOW-010` | L2_00_01 8.7 | 返回公共 `CapabilityResult` 合法组合，不让核心推导领域语义 | `DR-KFLOW-014` | 无 |

### 4.2 端到端追踪矩阵

| REQ/CON | 适用阶段/模块切片 | 设计规则 | 责任主体 | 契约/数据/状态影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-KFLOW-001`、`CON-KFLOW-001` | 能力注册/执行 | `DR-KFLOW-001`、`DR-KFLOW-012` | Capability、provider | 一个空参数动作 | `IMPL-KFLOW-001/008/009` | `TEST-KFLOW-001/008` | `VAL-KFLOW-002/003` |
| `REQ-KFLOW-002`、`CON-KFLOW-002` | 问题改写 | `DR-KFLOW-002`、`DR-KFLOW-003` | rewriter、semantic guard | 原问题/改写请求状态 | `IMPL-KFLOW-002/004/011` | `TEST-KFLOW-002/009` | `VAL-KFLOW-002/003` |
| `REQ-KFLOW-003`、`CON-KFLOW-003` | 域目录/选择 | `DR-KFLOW-004`、`DR-KFLOW-005` | catalog、selector | 两域冻结快照 | `IMPL-KFLOW-003/005` | `TEST-KFLOW-003/007` | `VAL-KFLOW-002/003` |
| `REQ-KFLOW-004`、`CON-KFLOW-004` | 检索计划 | `DR-KFLOW-006` | plan builder | 最多四个逻辑意图 | `IMPL-KFLOW-006` | `TEST-KFLOW-004` | `VAL-KFLOW-002` |
| `REQ-KFLOW-005`、`CON-KFLOW-005` | 阶段聚合 | `DR-KFLOW-007`、`DR-KFLOW-008`、`DR-KFLOW-014` | Capability | coverage/公共终态 | `IMPL-KFLOW-001/007` | `TEST-KFLOW-005/006` | `VAL-KFLOW-002/003` |
| `REQ-KFLOW-006`、`CON-KFLOW-006` | 启动配置 | `DR-KFLOW-009` | settings、provider | 冻结配置/就绪 | `IMPL-KFLOW-003/009` | `TEST-KFLOW-007/008` | `VAL-KFLOW-002/004` |
| `REQ-KFLOW-007`、`CON-KFLOW-007` | 请求状态 | `DR-KFLOW-010` | Capability | handler 局部状态 | `IMPL-KFLOW-001/007/011` | `TEST-KFLOW-005/009` | `VAL-KFLOW-003` |
| `REQ-KFLOW-008`、`CON-KFLOW-009` | stage 接缝 | `DR-KFLOW-012`、`DR-KFLOW-013` | flow、后续 L2 | 泛型 batch 不被流程解释，JWT 只到 retrieval | `IMPL-KFLOW-001/007/009/011` | `TEST-KFLOW-005/010` | `VAL-KFLOW-003/005` |
| `REQ-KFLOW-009`、`CON-KFLOW-008` | 预算/取消 | `DR-KFLOW-011` | Capability、stage | 子预算/取消 | `IMPL-KFLOW-004/007` | `TEST-KFLOW-009` | `VAL-KFLOW-003` |
| `CON-KFLOW-010` | 公共结果 | `DR-KFLOW-014` | Capability | 合法 status/egress/failure | `IMPL-KFLOW-001/007` | `TEST-KFLOW-001/006` | `VAL-KFLOW-002/003` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 交互契约 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|---|
| L1_01 v0.3 | parent | 细化 `L2_01_00` 唯一范围 | 定义 Knowledge 架构边界与门禁 | `knowledge.query`、五阶段语义 | 上位权威 | 只读 |
| L2_00_01 v0.4 Approved | direct dependency | 消费能力 API、`original_question` 和公共结果契约 | 核心执行、注册、图状态和公共结果不变量 | `CapabilityHandler` | 公共执行上下文 | 只读 |
| L2_00_02 v0.4 Approved | direct dependency | 定义 Knowledge 改写任务输入/输出，先消费全局问题闸门和安全模型上下文 | Provider、问题输入策略和供应商错误 | `QuestionEgressGuard`、`ModelCallContextAccessor`、`BoundedStructuredModelGateway` | 模型调用状态 | 本轮仅已授权消费契约原子补正 |
| L2_01_01 v0.2 Approved | downstream provider | 定义检索计划消费和 coverage 控制语义 | ES/BGE、候选、融合、重排、读取授权 | `KnowledgeRetrievalStage[TBatch]` | 排序候选 batch | 只读；五轮独立评审通过，实施/集成门禁 Open |
| 规划中的 L2_01_02 | downstream provider | 定义证据 stage 调用时机与输入控制语义 | 证据、三层出域、摘要和最终领域结果 | `KnowledgeEvidenceStage[TBatch]` | 证据/模型安全载荷 | 只读，尚未创建 |
| `es-query-service`/本地 BGE | external provider | 不定义或直接调用 | 提供类型化只读检索和本地模型能力 | 由 L2_01_01 固化 | 提供方资源 | 只读 |

### 5.1 唯一责任边界

| 所有者 | 拥有 | 不拥有 |
|---|---|---|
| `KnowledgeQueryCapability` | 单动作内部阶段顺序、原问题、域选择、计划、失败优先级 | LangGraph 图推进、第二动作、物理检索、证据字段 |
| `KnowledgeQuestionRewriter` | 改写候选与语义约束 | 通用 DeepSeek HTTP、领域选择、答案摘要 |
| `LogicalDomainCatalog` | 稳定逻辑域语义、顺序和代码绑定匹配规则 | 物理索引、文档归属事实 |
| `KnowledgeRetrievalStage` 实现 | 规划中的 L2_01_01 范围 | 本文不解释其 batch |
| `KnowledgeEvidenceStage` 实现 | 规划中的 L2_01_02 范围 | 本文不构造 safe payload 或摘要 |
| `agent-core` | 一次动作和公共结果校验 | 不识别 Knowledge 阶段或域 |

## 6. 当前实现基线与最小变更方案

### 6.1 已核实事实

| 事实编号 | 状态 | 事实 | 证据与影响 |
|---|---|---|---|
| `FACT-KFLOW-001` | 已存在（文档） | L1_01 v0.2 五轮评审通过，v0.3 针对性复核通过并保持 L2 编写门禁关闭 | 允许创建本文，不授权代码 |
| `FACT-KFLOW-002` | 已存在（文档） | L2_00_01 v0.4 已补充 handler 可读的 `original_question` 并完成针对性复评，状态 Approved | 本文可稳定消费；不代表代码存在 |
| `FACT-KFLOW-003` | 已存在（文档） | L2_00_02 v0.4 Approved 定义问题闸门、安全模型上下文、受控结构化任务和 `deepseek-v4-pro` Provider 边界 | 本文不重复供应商协议，只定义 Knowledge task |
| `FACT-KFLOW-004` | 未具备 | 目标 `agent-runtime` 与 Knowledge Python 模块/测试不存在 | 所有实现落点均为建议新增 |
| `FACT-KFLOW-005` | 待确认 | 首批真实 ES 内容如何稳定映射到 `tax.policy`/`tax.law` 尚未由提供方契约证明 | 不影响逻辑域/流程设计；阻塞真实检索，由 L2_01_01 关闭 |

### 6.2 当前问题与设计根因

根因不是“缺少一个 Knowledge 服务”，而是当前没有一个同时满足核心单动作契约和 Knowledge 内部多阶段语义的进程内能力实现。新增独立服务会重复身份、状态和故障边界；把流程写进核心则会使新增能力侵入现有代码。

### 6.3 最小变更方案

| 变更项 | 必要性 | 复用内容 | 新增/修改原因 | 不采用的方案及原因 |
|---|---|---|---|---|
| 新增一个 Knowledge Capability 模块 | 必须 | L2_00_01 handler/registry | 承载一个动作内的领域流程 | 不新增 `knowledge-service`：当前只有一个消费者和同进程状态，独立服务增加无必要边界 |
| 使用空动作参数 | 必须 | `CapabilityExecutionContext.original_question` | 防模型重建或篡改原问题 | 不把 question 放入模型 arguments：无法证明其与入站值相同 |
| 代码绑定两域与确定性选择 | 必须 | L1 首批税务范围 | 首批可测试、无任意域 | 不让模型/配置创建域；不把 ES 索引当域 |
| 两个 stage Protocol | 必须 | Capability handler | 隔离后续检索与证据实现 | 不建立通用工作流引擎或插件系统 |
| 启动环境强类型配置 | 必须 | L2_00_00 Python 配置方式 | 启停与收紧需可重复 | 不支持热更新、任意 YAML 类名/脚本或动态 Prompt |

## 7. 职责、分层与依赖设计

### 7.1 责任分解

| 组件/类型 | 状态 | 唯一职责 | 明确不负责 | 输入/输出 |
|---|---|---|---|---|
| `KnowledgeQueryArguments` | 建议新增 | 表达 v1 空参数动作 | 原问题、域、物理查询 | `{}`→冻结空值对象 |
| `LogicalKnowledgeDomain`/`LogicalDomainCatalog` | 建议新增 | 固化域语义、匹配词和稳定顺序 | ES 映射、读取授权 | 代码目录→启用视图 |
| `KnowledgeSettings` | 建议新增 | 加载、校验、冻结收紧型配置 | 创建域/Provider | 环境映射→设置 |
| `QuestionSemanticGuard` | 建议新增 | 提取并验证不可丢失约束 | 语言理解或事实判断 | 原问题/候选→判定 |
| `KnowledgeQuestionRewriter` | 建议新增 | 调用受控模型任务并选择候选/回退 | DeepSeek HTTP、域选择 | 原问题→`RewriteResult` |
| `DeterministicDomainSelector` | 建议新增 | 从启用目录选择 0～2 域 | 物理映射、模型调用 | 原问题+目录→域选择 |
| `KnowledgeRetrievalPlanBuilder` | 建议新增 | 生成关键词/向量逻辑计划 | 执行检索、融合重排 | rewrite+域→plan |
| `KnowledgeQueryCapability` | 建议新增 | 依次协调 rewrite/select/plan/retrieve/evidence，映射公共结果 | 图编排、Provider 协议 | 空参数+context→`CapabilityResult` |
| `KnowledgeCapabilityProvider` | 建议新增 | 产生唯一注册候选并执行启动校验 | 动态发现、热替换 | settings/dependencies→registration |

### 7.2 依赖方向

```text
agent-core
  → CapabilityHandler / CapabilityExecutionContext
    → KnowledgeQueryCapability
      → QuestionRewriter
      → LogicalDomainSelector
      → RetrievalPlanBuilder
      → KnowledgeRetrievalStage[TBatch]  ← L2_01_01 实现
      → KnowledgeEvidenceStage[TBatch]   ← L2_01_02 实现

KnowledgeQuestionRewriter
  → QuestionEgressGuard
  → ModelCallContextAccessor
  → BoundedStructuredModelGateway        ← L2_00_02 实现
```

以下依赖、绕过和反向依赖行为均明确禁止：

- `agent-core` 不得导入 `agent_runtime.knowledge`。
- Knowledge 不得导入 DeepSeek DTO、ES DSL、物理索引或 BGE HTTP DTO。
- Retrieval stage 不得调用 Evidence stage，Evidence stage 也不得反向选择域。
- 模型或配置不得生成新的 capability ID、logical domain ID 或 retrieval path。

### 7.3 内聚与耦合判断

问题改写、域选择和检索计划共同决定“查什么、查哪些逻辑范围”，因此内聚在 Knowledge Capability；物理检索与证据出域具有独立协议/安全权威，保留为两个 stage 接缝。核心只看到统一 handler，后续改变融合算法、ES 接口或证据策略不会修改核心及本流程的动作契约。只设置两个必需接缝，避免把每一步抽象为独立服务或通用工作流平台。

## 8. 公共类型、动作与请求状态

### 8.1 设计规则目录

| 规则编号 | 规则 | 责任主体 | 触发条件 | 输出/状态效果 |
|---|---|---|---|---|
| `DR-KFLOW-001` | v1 只注册 8.2 的完整 descriptor：canonical ID `knowledge.query`、`api_version=1`、`kind=query` 和精确空对象 Schema；alias 不可执行 | provider、validator | 启动/候选校验 | 模型只选择动作，不能回填问题/域/路径 |
| `DR-KFLOW-002` | handler 只把 `context.original_question` 作为原问题权威；动作参数、模型输出和配置均不能覆盖 | Capability | 动作开始 | 原问题同源可追踪 |
| `DR-KFLOW-003` | 改写最多产生 3 个候选；确定性验证长度、控制符和保护约束；无合法候选时仅按配置回退经验证原问题 | rewriter、guard | 改写 | 不采纳语义漂移候选 |
| `DR-KFLOW-004` | 逻辑域目录代码绑定为 `tax.policy`、`tax.law`，配置只能启用其子集 | catalog、settings | 启动 | 无任意域 |
| `DR-KFLOW-005` | v1 域选择是确定性纯函数：先确认税务锚点，再按政策/法律词选择；只有通用税务锚点时选择全部已启用域 | selector | 改写后 | 0～2 个稳定域 |
| `DR-KFLOW-006` | 每个已选域固定生成 `keyword`、`vector` 两个计划项，按目录顺序和路径顺序冻结；计划不含物理资源 | plan builder | 域选择非空 | 最多 4 个检索意图 |
| `DR-KFLOW-007` | 任一已选整域 `forbidden` 终止整个动作；读取判定不可验证、读取权威失败、整域全路径技术失败或 Rerank 失败不能降为 `no_result` | Capability | retrieval stage 返回 | 安全/技术失败优先 |
| `DR-KFLOW-008` | 单路技术失败仅在每个已选域至少一条成功路径、每域至少 1 个候选、总候选不少于配置阈值且 Rerank 有效时继续；必须标记 `coverage.complete=false` 和有限失败路径 | Capability、retrieval stage | 部分失败 | 有界部分成功 |
| `DR-KFLOW-009` | 设置启动加载并冻结；未知/重复域、缺任一必需路径、阈值扩权、依赖缺失均阻止 Runtime readiness | settings、provider | 启动 | 无半有效能力 |
| `DR-KFLOW-010` | `KnowledgeExecutionState` 只在 handler 栈内以不可变快照推进，不进入 LangGraph state、日志正文或持久化 | Capability | 每请求 | 请求结束即释放 |
| `DR-KFLOW-011` | 改写、检索和证据 stage 使用固定子预算；每阶段前后检查取消/总 deadline；不自动 retry、replay 或换域 | Capability | 每阶段 | 迟到结果不接纳 |
| `DR-KFLOW-012` | 本流程只依赖 `KnowledgeRetrievalStage[TBatch]` 与 `KnowledgeEvidenceStage[TBatch]`；分别传入最小 context，不解释 `TBatch` 内容，不调用下游内部 Port | Capability | 装配/执行 | JWT 仅进入读取 stage，后续 L2 可独立实现 |
| `DR-KFLOW-013` | 下游 stage 只能返回有限 typed result；Evidence stage 不得直接构造公共 `CapabilityResult`，原始异常、ES/BGE/模型响应不得穿透 | stage、Capability | stage 完成 | 固定失败映射与唯一公共结果所有者 |
| `DR-KFLOW-014` | Capability 是 `CapabilityResult` 的唯一 Knowledge 构造者，只产生 L2_00_01 允许的 status/egress/failure 组合；前置无匹配域为 `no_result + not_applicable`，技术失败无领域载荷 | Capability | 终止 | 核心无需领域推导 |

### 8.2 `knowledge.query` 动作契约

| 项目 | 精确设计 |
|---|---|
| `capability_id` | `knowledge.query` |
| `api_version` | `1` |
| `kind` | `query` |
| `display_name` | `知识查询` |
| `description` | `查询税务政策与税收法律知识；只读且不执行聚合或写操作` |
| `aliases` | `知识查询`、`税务政策查询`、`税务法律查询`；仅供模型理解，不能执行 alias |
| `argument_schema` | 精确 `{"type":"object","properties":{},"required":[],"additionalProperties":false}` |
| arguments | 精确 `{}`；任一属性均 `invalid_argument/knowledge.arguments_not_empty` |
| 原始问题 | `CapabilityExecutionContext.original_question`；不位于 arguments |
| handler | `KnowledgeQueryCapability.handle` |
| 下游副作用 | 只读；0～1 次改写模型 stage、1 次检索 stage、0～1 次证据 stage |

空参数不是缺少设计，而是明确阻止动作选择模型控制原问题、域、路径、候选数量、物理资源或 Provider。后续若需要用户显式过滤条件，必须由新的上位需求和动作契约版本定义，不能向 v1 任意加字段。

### 8.3 逻辑域目录

| domain ID | display name | 稳定语义 | 必需税务锚点 | 分类规则 | allowed paths | default egress policy ref | 代码顺序 |
|---|---|---|---|---|---|---|---:|
| `tax.policy` | `税务政策` | 税务机关公告、通知、规范性文件、执行口径、优惠政策及政策解释 | 8.3.1 税务锚点至少一个 | 8.3.1 政策分类词至少一个 | `keyword`,`vector` | `knowledge.egress.tax_policy.v1` | 10 |
| `tax.law` | `税收法律` | 税收相关法律、行政法规、司法解释及法定条文 | 同左税务锚点至少一个 | 8.3.1 法律分类词或条款表达式至少一个 | `keyword`,`vector` | `knowledge.egress.tax_law.v1` | 20 |

分类词只是 v1 可验证路由规则，不声明真实文档已经完成物理归类。一个问题可以同时选择两域；一份物理文档是否属于某域由 L2_01_01 的受控映射证明。配置不得修改词表、描述、顺序或 domain ID。

#### 8.3.1 v1 精确词表与匹配

- 税务锚点 tuple 固定为：`税`、`税务`、`税收`、`纳税`、`增值税`、`所得税`、
  `企业所得税`、`个人所得税`、`发票`。
- 政策分类词 tuple 固定为：`政策`、`公告`、`通知`、`优惠`、`指引`、`口径`、
  `征管`、`实施`。
- 法律分类词 tuple 固定为：`法律`、`法规`、`条例`、`司法解释`、`法条`、`违法`、
  `处罚`；条款表达式固定为
  `第[零〇一二三四五六七八九十百千万0-9]{1,12}(条|款|项)`。
- selector 对 9.1 规范化后的权威原问题执行 Unicode code point 字面子串匹配，并执行
  上述一条有界条款表达式；不分词、不做同义词扩展、模糊匹配或模型补充。短词命中不覆盖
  长词命中，命中集合只用于布尔分类；政策与法律同时命中时两类都保留。
- 词表或表达式变化属于代码/设计变更，必须更新目录版本、fixture 和评审，不能通过环境配置
  热增补。

选择规则按顺序执行：

1. 无任一税务锚点：选择空集合，返回 `no_result/knowledge.no_matching_domain`，检索 stage 调用为零。
2. 同时命中政策和法律分类词：选择两域中已启用者。
3. 仅命中一类：选择对应已启用域。
4. 只有通用税务锚点：选择全部已启用域。
5. 规则应选域但该域被禁用，且无其他启用匹配域：按已启用快照返回零域，不探测被禁用域。

### 8.4 请求级类型与状态

| 类型 | 字段 | 不变量 |
|---|---|---|
| `KnowledgeQueryArguments` | 无字段 | 冻结、不可扩展 |
| `LogicalKnowledgeDomain` | `domain_id`、`display_name`、`order`、`anchor_terms`、`classifier_terms`、可选 `classifier_pattern`、`allowed_paths`、`default_egress_policy_ref` | 全部代码绑定并冻结；两个域均恰有 keyword/vector；policy ref 只是 L2_01_02 解析的 opaque ID，本文不定义策略内容 |
| `ProtectedConstraintSet` | `numbers`、`dates`、`document_numbers`、`article_refs`、`negations`，均为 tuple[str] | 同一 matcher 按源文本顺序提取并保留重复；每类≤32、合计≤64、单项≤128 code points，超界拒绝原问题而不截断 |
| `RewriteCandidateValidation` | `accepted: bool`、拒绝时 `reason: empty/control/too_long/missing_constraint/introduced_constraint` | 不携带候选或缺失片段；accepted 与 reason 互斥 |
| `RewriteCandidate` | `text`、`source=model/original_fallback`、`ordinal` | NFC、非空、≤`max_retrieval_query_chars`、保护约束完整 |
| `RewriteResult` | `original_question`、`selected_query`、`candidates`、`mode`、`question_policy_version`、`question_egress_denied` | 原问题与 context 精确相同；selected 必须来自 candidates；denied 只来源于显式 guard 决定 |
| `RewriteStageResult` | `success/question_denied/input_invalid/timeout/failure` 有限 tagged union | success 仅含 rewrite；question_denied 仅含 policy version/reason；其他失败只含有限 kind，不含输入/异常 |
| `DomainSelection` | `selected_domain_ids`、`catalog_version`、`reason_codes` | ID 已注册/启用、无重复、按目录顺序、≤2 |
| `RetrievalPlanItem` | `logical_domain_id`、`path`、`query_text`、`candidate_limit`、`ordinal` | path 仅 keyword/vector；无物理字段 |
| `KnowledgeRetrievalPlan` | `items`、`selected_domain_ids`、`config_version` | 每个域恰有两项；最多 4 项 |
| `RetrievalCoverage` | `successful_paths`、`no_result_paths`、`failed_paths`、`candidate_count_by_domain`、`complete` | 仅有限 path/status/count；不含正文或原始异常 |
| `RetrievalDecision[TBatch]` | `continue_to_evidence/terminal`；前者只含 opaque batch+coverage，后者只含 `CapabilityResult` | `map_retrieval_result` 私有返回；两 variant 互斥，不进入日志/state/public contract |
| `KnowledgeRetrievalContext` | `request_id`、`correlation_id`、`subject`、`user_token: OpaqueUserToken`、`deadline_monotonic`、`cancellation` | 从执行上下文一次性冻结投影；不含原问题；仅 retrieval stage 可见 |
| `KnowledgeEvidenceContext` | `request_id`、`correlation_id`、`subject`、`deadline_monotonic`、`cancellation` | 从同一执行上下文冻结投影；不含 JWT/原问题；仅 evidence stage 可见 |
| `KnowledgeExecutionState[TBatch]` | `stage`、`rewrite`、`domains`、`plan`、`retrieval_result`、`started_monotonic` | handler 私有不可变快照；可选字段只能在对应阶段后出现 |

`catalog_version` 固定为 `tax-domain-catalog-v1`；`config_version` 固定为
`knowledge-flow-config-v1`，表示配置 schema/上限语义而非秘密配置值。二者都是代码常量，
词表、字段或校验语义变化必须升版。请求状态中的 reason/path/stage code 均为本文列出的
有限枚举，不接受配置或下游自由字符串。

`KnowledgeExecutionStage` 固定为：

```text
accepted → rewritten → domains_selected → planned
         → retrieved → evidence_completed → returned
```

任何阶段可终止为公共结果；不能回退、循环或重入。`TBatch` 只由 retrieval stage 产生并原样交给 evidence stage，Capability 不读取、序列化或记录它。

事务与一致性边界：Knowledge 是无写入、无数据库事务的只读流程，不适用跨资源事务、补偿或幂等存储；单请求一致性只由冻结配置快照、不可变阶段状态、核心一次性动作 latch 和截止后拒绝迟到结果保证。不同请求之间不承诺索引快照、模型输出或排序结果强一致。

## 9. 问题改写详细设计

### 9.1 输入与确定性规范化

输入必须与 `context.original_question` 精确相同。规范化只用于生成检索表达：

- Unicode 转 NFC。
- 去除首尾空白；连续空白折叠为单个空格。
- 拒绝 NUL、不可接受控制字符及规范化后空值。
- 不删除标点、数字、百分比、日期、文号、条款、否定和范围词。
- 原问题仍保留在请求状态中；日志不记录原文或改写全文。

### 9.2 保护约束

`QuestionSemanticGuard` 使用代码绑定有限规则提取：

- 数字：ASCII 整数/小数后可紧跟 `%/元/万元/亿元`，或最长 24 位中文数字后可紧跟同一单位。
- 日期：`YYYY年M月D日`、`YYYY-M-D`、`YYYY/M/D`、`YYYY.M.D` 以及其中明确出现的
  `以前/以后/期间/起/止/截至`。
- 文号：最长 24 个非空白、非中文句读前缀，后接 `〔YYYY〕N号` 或 `[YYYY]N号`。
- 条款：8.3.1 的 `第…条/款/项` 表达式。
- 否定/边界词精确 tuple：`不`、`未`、`不得`、`禁止`、`免税`、`除外`、`仅`、
  `至少`、`至多`、`超过`、`低于`。

#### 9.2.1 提取与比较算法

1. 对 9.1 的 NFC 文本按上述五类 matcher 左到右扫描；同类重叠时选择起点更早者，同一起点
   选择 code point 更长者，完全相同则按 matcher 声明顺序；不同类别可以保留同一片段。
2. 每类保留出现顺序和重复项，不大小写折叠、不把中文数字换算成阿拉伯数字；任一单项、
   分类数或合计数超 8.4 上限即 `invalid_question`，不得截断后继续。
3. 对候选用完全相同的 matcher 重新提取。五类 tuple 必须分别与原问题 tuple 精确相等；
   少一项为 `missing_constraint`，多一项或值/顺序改变为 `introduced_constraint`。
4. 候选字符上限按 Unicode code point 计算；控制字符、空值和超界分别返回有限 reason，
   决定中不保留候选正文或命中片段。

模型候选必须逐项保留提取出的稳定文本片段。该检查不能证明完整语义等价，因此只作为必要
条件；候选五类 tuple 任一不与原问题精确相等即判定 `semantic_drift`。
首期不声明具备通用实体识别能力，也不使用未定义的“域外实体”判断；不引入第二模型做语义
判定，避免以另一个不可信输出证明第一个输出。

### 9.3 受控模型任务

Knowledge 定义代码绑定类 `KnowledgeRewriteTaskV1`，在 L2_00_02 的冻结 registry 中使用
精确键 `(ModelTaskId.knowledge_rewrite, task_version="1")`，通过 gateway 执行一次：

```text
input:
  minimized_question: str
  max_candidates: int (1..3)

output:
  candidates: tuple[str, ...] (1..3)
```

`KnowledgeRewriteInput` 是冻结 dataclass，只含
`minimized_question: str` 与 `max_candidates: int`；问题按 Unicode code point
1～4096 且 canonical task input ≤16384 bytes，max_candidates 必须等于冻结 settings 的
1～3 值。`KnowledgeRewriteOutput` 是冻结 dataclass，只含
`candidates: tuple[str,...]`；Provider JSON 必须精确为
`{"candidates":[...]}`，拒绝额外/重复 key、非字符串、空数组、超过 max_candidates、
单项超过 1024 code points 或控制字符。task 固定
`prompt_version=knowledge-rewrite-prompt-v1`、timeout=8s、max output tokens=512；
Knowledge settings 只能进一步降低候选数/查询字符数，不能替换 Prompt 或 schema。

Prompt 只要求生成保持主体、时间、条件、否定、文号和法律语义的检索表达，不要求回答问题，
不接收候选文档、JWT、物理域或 Provider 参数。rewriter 先显式调用 L2_00_02 的同一个
`QuestionEgressGuard.evaluate(original_question)`：denied 时记录安全策略版本和有限原因、
gateway 调用为 0；allowed 时只把 decision 中的 `minimized_question` 放入 task input。
gateway 自身仍执行注册 task、完整请求大小、预算和 Provider 边界，不信任调用方绕过。

rewriter 不接收 `CapabilityExecutionContext`；它只从注入的
`ModelCallContextAccessor.require_current()` 取得已经由 L2_00_02 外层 invoker 绑定的
`ModelCallContext`。accessor 缺失时 guard/gateway 调用均为 0 并以内部配置错误终止；
不得在 Knowledge 再投影、复制或持有 subject/token。

### 9.4 候选选择与回退

1. 按 provider 返回顺序校验候选。
2. 去除与前序候选规范化后完全相同的重复项。
3. 选择首个通过保护约束且不超长的候选。
4. 无合法候选时，只有 `allow_original_fallback=true` 且规范化原问题不超过检索查询上限，才使用 `original_fallback`。
5. 只有显式 `QuestionEgressDecision.denied` 才允许在本地原问题回退时设置
   `question_egress_denied=true`，并保留其 `policy_version`；这不允许后续把问题或证据发送模型。
6. guard allowed 后的 gateway `input_denied` 表示 task/request 输入边界失败，不得伪装成问题
   策略拒绝；Provider timeout/failure/invalid output 或该输入失败可按同一长度规则回退，
   `question_egress_denied=false`，不进行第二次模型调用。
7. 无法回退时按 12.2 映射公共失败。

## 10. 检索计划与阶段协作

### 10.1 计划生成

对每个已选域按以下固定顺序生成：

```text
domain order: tax.policy → tax.law
path order:   keyword → vector
```

两路使用同一 `selected_query` 和配置收紧后的 `per_path_candidate_limit`。计划只表达意图；Embedding 如何产生向量、关键词如何查询、候选如何融合和 Rerank 均由 L2_01_01 决定。

### 10.2 stage Protocol

```python
class KnowledgeRetrievalStage(Protocol[TBatch]):
    async def execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> RetrievalStageResult[TBatch]: ...

class KnowledgeEvidenceStage(Protocol[TBatch]):
    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[TBatch],
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult: ...
```

`RetrievalStageResult` 是有限 tagged union：

| kind | 必填字段 | 禁止字段 | Capability 行为 |
|---|---|---|---|
| `success` | `batch`、`coverage` | failure | 校验 coverage 后进入 evidence stage |
| `no_result` | `coverage` | batch/failure | 返回 `no_result + not_applicable` |
| `forbidden` | `stage_code=domain_forbidden` | batch/coverage/正文 | 返回固定 `forbidden/knowledge.domain_forbidden` |
| `timeout` | `stage_code=read_authority_timeout/retrieval_timeout/rerank_timeout` | batch/coverage/正文 | 映射固定 timeout code |
| `downstream_failure` | `stage_code=read_decision_unverifiable/read_authority_failure/retrieval_failure/rerank_failure/invalid_provider_result` | batch/coverage/正文 | 映射固定 downstream code |

`RetrievalCoverage.failed_paths[*].failure_kind` 只允许 `timeout/downstream_failure`，path
只允许已计划的 domain+`keyword/vector` 组合且无重复；授权拒绝、判定不可验证、读取权威
失败和 Rerank 失败不能放入 failed_paths 伪装为部分成功。stage code 由 enum 类型表达，
Capability 不接收下游提供的公共 failure code/source 或自由文本。

Coverage 校验必须满足：

1. `successful_paths`、`no_result_paths`、`failed_paths` 对 plan 中每个 domain/path 形成
   无重复、无遗漏、无额外项的精确分区。
2. `candidate_count_by_domain` 的 key 精确等于 `selected_domain_ids`，值为 Rerank 后合法
   batch 中该域候选数，范围 0～`2 * per_path_candidate_limit`；Capability 不读取 opaque
   batch，计数与 batch 一致性由 L2_01_01 provider contract test 证明。
3. `complete=true` 当且仅当 `failed_paths` 为空；成功 batch 至少一个域计数大于 0，Rerank
   已成功，允许某已选域的两条合法路径均为 no_result。
4. `complete=false` 当且仅当 `failed_paths` 非空且 10.3 六项部分成功条件全部成立。
5. `RetrievalStageResult.no_result` 只允许 `failed_paths` 为空、所有域计数为 0、Rerank
   不需要调用或以空输入确定性跳过；对用户不得区分“无命中”和“候选经读取过滤后为空”。
6. 任一不变量不满足均丢弃 batch/coverage，返回
   `internal_failure/knowledge.invalid_stage_result`，不得尝试猜测或修补。

`KnowledgeEvidenceInput[TBatch]` 只含 `original_question`、`selected_query`、
`selected_domain_ids`、`coverage`、`question_policy_version`、
`question_egress_denied` 和 opaque `batch`。当 `question_egress_denied=true` 时，
Evidence stage 可以构造本地受控结果，但任何摘要/回答模型调用必须为 0；该 flag 不得由
Evidence stage 清除或覆盖。其证据字段及具体出域行为由 L2_01_02 固化。

`EvidenceStageResult` 是 Knowledge 专用有限 tagged union，不能直接返回公共
`CapabilityResult`：

| kind | 必填字段 | 禁止字段 | Capability 映射 |
|---|---|---|---|
| `success` | 冻结 `domain_result`、合法 `ModelEgressResult`；仅 egress allowed 时有 `safe_payload` | failure | 校验 L2_00_01 success 组合后构造公共 `success` |
| `no_result` | `reason=insufficient_evidence/no_candidate`、可选非敏感 coverage metadata | safe payload/failure | 构造公共 `no_result + not_applicable` |
| `model_egress_denied` | `policy_version`、`reason_code=question_denied/global_denied/domain_denied/document_denied/policy_missing/policy_conflict`、可选受控本地结果 | safe payload | 构造固定 `model_egress_denied + denied` |
| `forbidden` | `stage_code=evidence_read_forbidden` | domain result/safe payload | 构造固定公共 `forbidden` |
| `timeout` | `stage_code=evidence_timeout/summary_timeout` | domain result/safe payload | 映射固定 timeout code |
| `downstream_failure` | `stage_code=evidence_failure/summary_failure/invalid_summary` | domain result/safe payload | 映射固定 downstream code |

Evidence stage 返回未知 kind、字段组合、越界 JSON，或在
`question_egress_denied=true` 时返回 allowed/safe payload，Capability 必须丢弃全部载荷并
构造 `internal_failure/knowledge.invalid_stage_result`；不得让 stage 选择公共状态或透传
自己的 `FailureDetail`。

### 10.3 部分成功充分性

技术性单路失败只有同时满足以下条件才可进入 evidence stage：

1. 没有整域 `forbidden`、读取判定不可验证或读取权威失败。
2. 每个已选域至少一条检索路径成功完成。
3. 每个已选域至少返回 1 个已授权候选。
4. 去重后总候选数不少于 `min_partial_candidates`，默认 3。
5. L2_01_01 已成功完成 Rerank 并返回合法 batch。
6. `coverage.complete=false`，`failed_paths` 只含 domain/path/有限 failure kind，不含异常正文。

任一条件不满足则使用 `timeout` 或 `downstream_failure`，不得转 `no_result`。某域两路都成功但无候选不是技术失败；其他域有候选时可继续，并保持 `coverage.complete=true`。

## 11. 详细功能与核心处理流程、失败优先级及公共结果

### 11.1 主流程

1. 核心完成候选公共校验和单动作 claim。
2. validator 确认 arguments 精确为空对象。
3. handler 校验 context、取消、deadline 与 `original_question`。
4. 问题改写并形成 `RewriteResult`。
5. 仅基于权威原问题和启用目录执行确定性域选择。
6. 零域时直接返回受控 `no_result`，任何检索/证据调用为零。
7. 构建冻结 `KnowledgeRetrievalPlan`。
8. 在剩余预算内调用一次 retrieval stage。
9. 按固定失败优先级和部分成功阈值校验 stage result。
10. 合法 success 时分别投影无 JWT 的 evidence context，并在剩余预算内调用一次 evidence stage。
11. 校验 `EvidenceStageResult`，由 Capability 唯一映射为合法 `CapabilityResult` 并返回核心。

### 11.2 失败优先级

同一请求观察到多个信号时按下列顺序决定，不允许由完成先后覆盖：

1. `runtime_shutdown`：传播 `CancelledError`，不构造普通结果。
2. 客户端取消或总 deadline 耗尽：`timeout/knowledge.request_cancelled` 或 `knowledge.deadline_exhausted`。
3. 无效身份/上下文：`unauthenticated/knowledge.invalid_context`。
4. 参数或原问题非法：`invalid_argument/knowledge.invalid_question`。
5. 任一已选整域明确拒绝：`forbidden/knowledge.domain_forbidden`。
6. 读取判定不可验证、读取权威非超时失败、整体检索或 Rerank 失败：`downstream_failure`。
7. 读取权威/检索/Rerank 超时：`timeout`；若同一聚合同时存在 timeout 与非超时技术失败，选择 `timeout`，并只记录有限阶段码。
8. 合法执行后无候选/无匹配域/后续证据不足：`no_result`。
9. 满足完整或部分成功条件：进入 evidence stage，由 L2_01_02 决定最终 `success/no_result/model_egress_denied/downstream_failure`。

### 11.3 阶段错误码与调用方可见语义

| 触发 | 公共 status | failure code | source | egress |
|---|---|---|---|---|
| arguments 非空 | `invalid_argument` | `knowledge.arguments_not_empty` | capability | not_applicable |
| 原问题非法 | `invalid_argument` | `knowledge.invalid_question` | capability | not_applicable |
| 全局问题闸门拒绝且不可本地回退 | `model_egress_denied` | `knowledge.rewrite_input_denied` | policy | denied，使用 guard 决定中的策略版本 |
| guard allowed 后模型 task/request 输入边界拒绝且不可回退 | `internal_failure` | `knowledge.rewrite_task_rejected` | capability | not_applicable |
| 改写 timeout 且不可回退 | `timeout` | `knowledge.rewrite_timeout` | downstream | not_applicable |
| 改写 provider/invalid output 且不可回退 | `downstream_failure` | `knowledge.rewrite_failure` | downstream | not_applicable |
| 无匹配启用域 | `no_result` | 无 | 无 | not_applicable |
| 整域拒绝 | `forbidden` | `knowledge.domain_forbidden` | downstream | not_applicable |
| 读取判定不可验证 | `downstream_failure` | `knowledge.read_decision_unverifiable` | downstream | not_applicable |
| 读取权威非超时失败 | `downstream_failure` | `knowledge.read_authority_failure` | downstream | not_applicable |
| 读取权威超时 | `timeout` | `knowledge.read_authority_timeout` | downstream | not_applicable |
| retrieval/Rerank timeout | `timeout` | `knowledge.retrieval_timeout` | downstream | not_applicable |
| retrieval/Rerank 非超时失败 | `downstream_failure` | `knowledge.retrieval_failure` | downstream | not_applicable |
| evidence 复核明确读取拒绝 | `forbidden` | `knowledge.evidence_read_forbidden` | downstream | not_applicable |
| evidence/summary timeout | `timeout` | `knowledge.evidence_timeout`/`knowledge.summary_timeout` | downstream | not_applicable |
| evidence/summary 非超时失败或摘要非法 | `downstream_failure` | `knowledge.evidence_failure`/`knowledge.summary_failure` | downstream | not_applicable |
| evidence 出域拒绝 | `model_egress_denied` | `knowledge.evidence_egress_denied` | policy | denied，使用 evidence policy version |
| stage result 结构非法 | `internal_failure` | `knowledge.invalid_stage_result` | capability | not_applicable |

`no_result` 可携带的用户结果只允许
`reason=no_matching_domain/no_candidate/insufficient_evidence`、已选择逻辑域 ID 和
`coverageComplete`。Retrieval/Evidence 内部不得向该结果编码“曾命中但用户不可读”；
无命中与全部候选在提供方边界被读取过滤后为空必须同为 `no_candidate`，不得包含问题、
匹配词、被禁用/不可读域、候选身份、内部策略或技术失败。

## 12. 配置、预算、安全与观测

### 12.1 强类型配置

| 环境变量 | 默认 | 允许范围 | 收紧/扩权判断 | 生效 |
|---|---:|---|---|---|
| `AGENT_KNOWLEDGE_ENABLED` | `false` | `true/false` | 只启停固定能力 | 重启 |
| `AGENT_KNOWLEDGE_ENABLED_DOMAINS` | 空 | 仅 `tax.policy,tax.law` 的无重复子集 | 未知值扩权，启动失败 | 重启 |
| `AGENT_KNOWLEDGE_REWRITE_MAX_CANDIDATES` | `3` | 1～3 | 只能降低 | 重启 |
| `AGENT_KNOWLEDGE_ALLOW_ORIGINAL_FALLBACK` | `true` | `true/false` | false 更严格 | 重启 |
| `AGENT_KNOWLEDGE_MAX_RETRIEVAL_QUERY_CHARS` | `1024` | 128～1024 | 只能降低代码上限 | 重启 |
| `AGENT_KNOWLEDGE_PER_PATH_CANDIDATES` | `20` | 5～20 | 只能从代码上限降低 | 重启 |
| `AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES` | `3` | 3～20，且不得大于 `AGENT_KNOWLEDGE_PER_PATH_CANDIDATES` | 只能提高；保证单域仅一条成功路径时仍存在理论达标可能 | 重启 |
| `AGENT_KNOWLEDGE_REWRITE_TIMEOUT_MS` | `8000` | 1000～8000 | 不得扩大 | 重启 |
| `AGENT_KNOWLEDGE_RETRIEVAL_TIMEOUT_MS` | `20000` | 3000～20000 | 不得扩大 | 重启 |
| `AGENT_KNOWLEDGE_EVIDENCE_TIMEOUT_MS` | `15000` | 3000～15000 | 不得扩大 | 重启 |

启用能力时必须恰有至少一个有效域；首批真实多域验收配置必须同时启用两域。v1 必需路径固定为 keyword/vector，配置不提供关闭其中一路的开关。任何启用域缺 retrieval/evidence stage 或域策略引用时整个 Runtime 不就绪，不静默只注册剩余域。

解析规则固定如下：

- bool 只接受 ASCII 小写 `true/false`；整数只接受无正负号、无前导/尾随空白的十进制数字，
  再执行表中范围校验。
- enabled domains 以英文逗号分隔；每项必须精确为代码绑定 ID，不 trim、不接受空项、重复、
  大小写变体或尾逗号。解析为集合后始终按 catalog order 投影，配置顺序不进入运行语义。
- 未设置使用默认值；设置为空字符串不是“未设置”。除 enabled domains 在能力 disabled 时
  允许默认空值外，其他显式空值均启动失败；enabled=true 且域为空同样失败。
- `KnowledgeSettings.from_env` 只读取上述精确 key，但发现任何未知
  `AGENT_KNOWLEDGE_` 前缀 key 时启动失败；其他系统环境变量不参与判断。
- 无论 capability 是否 disabled，所有显式 Knowledge 配置都必须解析/校验，不能借 disabled
  隐藏拼写或越界值；校验后的 settings 深冻结且不热更新。

### 12.2 预算、取消与调用上限

| 阶段 | 最大调用数 | 子预算 | 失败后 |
|---|---:|---:|---|
| rewrite model task | 1 | 8s | 可本地回退或受控终止；不 retry |
| deterministic domain/plan | 本地纯函数 | 合计 50ms 目标 | 超时视为 internal failure |
| retrieval stage | 1 | 20s | 按 typed result 终止；不由 flow retry |
| evidence stage | 1 | 15s | 按其 typed `CapabilityResult` 返回；不由 flow retry |

每次调用的实际 timeout 是阶段上限与总 deadline 剩余值的较小者。剩余不足 100ms 时不发起下一调用。检索 stage 内部多路并发、Embedding/Rerank 子预算由 L2_01_01 负责，但不得延长本流程传入的 20s。

Capability 在每个异步阶段开始前使用同一 event-loop 单调时钟冻结：

```text
phaseDeadline =
  min(context.deadline_monotonic - 100ms,
      nowMonotonic + configuredPhaseTimeout)
timeout_s = phaseDeadline - nowMonotonic
```

`phaseDeadline <= now` 时 stage 调用为 0，并按当前阶段返回 timeout。Capability 必须用
`asyncio.timeout_at(phaseDeadline)`（或具有同一绝对语义的实现）包住完整 rewrite/retrieval/
evidence await；`timeout_s` 只是供下游继续细分预算，不能替代外层强制截止。phase timeout
会取消并 await 当前 stage task，丢弃迟到结果且不安排下一阶段；外层
`CancelledError`、尤其 `runtime_shutdown` 必须在清理后继续传播，不能被 phase timeout
转换。同步 domain selection/plan builder 的 50ms 是有界输入上的验收上限：调用前后检查
单调时钟，超限结果不接纳并返回 `internal_failure/knowledge.local_stage_overrun`，不为此
引入线程池或后台任务。

### 12.3 权限、安全与审计设计

- 缺少 user token/subject 的上下文在任何模型、检索或证据调用前失败。
- Capability 从完整执行上下文分别冻结投影 `KnowledgeRetrievalContext` 与
  `KnowledgeEvidenceContext`；原始 JWT 只存在于前者并只传给 retrieval stage，不得传给
  rewriter、evidence stage、域选择器或本地 BGE。
- 原问题进入 rewrite gateway 前仍经过 L2_00_02 输入闸门。
- 逻辑域 ID 可进入安全日志；匹配词、问题和改写正文不得进入。
- 本文不能以角色、域配置或本地规则替代文档读取权威。
- `question_egress_denied=true` 必须随 `KnowledgeEvidenceInput` 传入 evidence stage，只允许
  本地流程继续；evidence result 若携带 allowed/safe payload 视为非法 stage result，防止后续
  模型调用绕过拒绝。

### 12.4 日志、指标与审计

允许记录：

- request/correlation ID、`knowledge.query`、配置/目录版本。
- 选中逻辑域 ID、阶段、rewrite mode、耗时和有限终态。
- 每域/路径候选数量、coverage complete、有限失败路径。

禁止记录：

- JWT/API Key、subject 原文、原问题、改写候选、模型 Prompt/响应。
- 查询向量、候选/证据正文、文档 ID、ES 响应、异常 message/stack。

建议指标：

| 指标 | 有界标签 | 含义 |
|---|---|---|
| `agent_knowledge_stage_duration_seconds` | stage、outcome | 各阶段耗时 |
| `agent_knowledge_domain_selection_total` | selection=`none/single/multi` | 域选择分布 |
| `agent_knowledge_rewrite_total` | mode=`model/original_fallback/failure` | 改写路径 |
| `agent_knowledge_coverage_total` | complete=`true/false` | 覆盖完整性 |
| `agent_knowledge_result_total` | status | 公共终态 |

## 13. 组合根、实现落点与关键签名

### 13.1 组合根

启动顺序固定：

1. 加载并校验 `KnowledgeSettings`。
2. 构建代码绑定 `LogicalDomainCatalog`，投影启用域快照。
3. 能力禁用时返回 disabled registration，不创建外部客户端。
4. 能力启用时先由 `KnowledgeRewriteTaskV1.definition()` 创建纯、冻结、无客户端的
   `ModelTaskDefinition`；顶层 `agent_runtime.bootstrap` 把它与 L2_00_02 的 action/answer
   task 组成代码显式 tuple，再一次性构建/冻结 model task registry 和 gateway。model 公共
   模块不得反向导入 Knowledge，配置也不能追加 task。
5. registry 冻结后，校验至少一个域、两条必需路径、阈值，以及 guard、model context
   accessor、structured gateway、retrieval stage、evidence stage 均已显式注入。
6. 创建 semantic guard、rewriter、context projector、selector、plan builder 和 Capability。
7. 创建唯一 `KnowledgeCapabilityProvider` 并交给 L2_00_01 组合根冻结注册。
8. 任一步失败时 Runtime readiness=false；不带半有效 Knowledge 接收请求。

disabled 路径在第 3 步终止，不创建 Knowledge task definition、rewriter、stage 或客户端；
但 L2_00_02 为动作选择/回答所需的公共 model 组件是否存在由其自身设置决定。该顺序保持
“Knowledge 定义领域 task、model 层拥有 registry/gateway、顶层组合根显式装配”三项所有权，
不存在 model→Knowledge 反向依赖。

### 13.2 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置项 | 责任 | 必要性 | 设计规则 |
|---|---|---|---|---|---|---|---|
| `IMPL-KFLOW-001` | 建议新增 | Python contract | `agent-runtime/src/agent_runtime/knowledge/contracts.py` | arguments、domain/rewrite/plan/coverage/stage Protocol 与 tagged result | 稳定流程契约 | 防领域/Provider 对象泄漏 | `DR-KFLOW-001/002/006/012/013/014` |
| `IMPL-KFLOW-002` | 建议新增 | Python semantic guard | `agent-runtime/src/agent_runtime/knowledge/question_semantics.py` | `ProtectedConstraintSet`、`QuestionSemanticGuard` | 改写必要语义校验 | 防数字/时间/否定漂移 | `DR-KFLOW-002/003` |
| `IMPL-KFLOW-003` | 建议新增 | Python catalog/config | `agent-runtime/src/agent_runtime/knowledge/catalog.py`、`agent-runtime/src/agent_runtime/knowledge/settings.py` | 两域目录、`KnowledgeSettings` | 代码绑定域和收紧配置 | 防任意域/半配置 | `DR-KFLOW-004/005/009` |
| `IMPL-KFLOW-004` | 建议新增 | Python rewrite | `agent-runtime/src/agent_runtime/knowledge/rewrite.py` | `KnowledgeQuestionRewriter`、task definition | 模型改写/本地回退 | 承接问题改写 | `DR-KFLOW-002/003/011/013` |
| `IMPL-KFLOW-005` | 建议新增 | Python selector | `agent-runtime/src/agent_runtime/knowledge/domain_selection.py` | `DeterministicDomainSelector` | 稳定选择 0～2 域 | 可验证多域 | `DR-KFLOW-004/005` |
| `IMPL-KFLOW-006` | 建议新增 | Python planning | `agent-runtime/src/agent_runtime/knowledge/planning.py` | `KnowledgeRetrievalPlanBuilder` | 生成逻辑两路计划 | 隔离物理检索 | `DR-KFLOW-006/009` |
| `IMPL-KFLOW-007` | 建议新增 | Python capability | `agent-runtime/src/agent_runtime/knowledge/capability.py` | validator、`KnowledgeQueryCapability` | 阶段协调、失败优先级、公共结果 | 单动作完整流程 | `DR-KFLOW-001/002/007/008/010/011/012/013/014` |
| `IMPL-KFLOW-008` | 建议新增 | Python provider | `agent-runtime/src/agent_runtime/knowledge/provider.py` | `KnowledgeCapabilityProvider` | 唯一 registration | 显式能力接入 | `DR-KFLOW-001/004/009/012` |
| `IMPL-KFLOW-009` | 建议新增 | Python composition | `agent-runtime/src/agent_runtime/bootstrap.py` | 显式注入 Knowledge provider/stages | 组合根接入 | 新能力不侵入 core | `DR-KFLOW-009/012` |
| `IMPL-KFLOW-010` | 建议新增 | Python error | `agent-runtime/src/agent_runtime/knowledge/errors.py` | 有限内部异常/映射 | 不泄露下游异常 | `DR-KFLOW-007/013/014` |
| `IMPL-KFLOW-011` | 建议新增 | Python context projection | `agent-runtime/src/agent_runtime/knowledge/context.py` | retrieval/evidence context 与纯投影函数 | JWT 仅进入读取 stage | 防完整 context 泄漏到模型/证据 | `DR-KFLOW-002/010/012/014` |

### 13.3 Python 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| 建议新增：`knowledge.settings.KnowledgeSettings.from_env` | `@classmethod def from_env(cls, env: Mapping[str, str]) -> Self` | 精确解析 12.1；未知域/重复/越界拒绝 | 冻结 settings；抛仅含 code 的 `KnowledgeConfigurationError` | 只读 env；composition root |
| 建议新增：`knowledge.catalog.build_tax_domain_catalog` | `def build_tax_domain_catalog() -> LogicalDomainCatalog` | 无运行输入；代码常量全量自校验 | 冻结两域目录；重复/非法 ID 为启动错误 | 无 I/O；provider/selector |
| 建议新增：`knowledge.capability.KnowledgeArgumentValidator.validate` | `def validate(self, arguments: JsonObject) -> KnowledgeQueryArguments` | 只接受精确空对象 | 冻结空参数；非空抛 `InvalidCapabilityArguments` | 无 I/O；core registry |
| 建议新增：`knowledge.question_semantics.QuestionSemanticGuard.extract` | `def extract(self, original_question: str) -> ProtectedConstraintSet` | 9.2.1 同一 matcher、code point/分类/合计上限 | 冻结有序约束 tuple；非法/超界问题为仅含 code 的 typed error | 纯函数；rewriter |
| 建议新增：同上 `validate_candidate` | `def validate_candidate(self, *, candidate: str, constraints: ProtectedConstraintSet, max_chars: int) -> RewriteCandidateValidation` | 同一 matcher、Unicode code point 长度、控制符、五类 tuple 精确相等 | accepted 或 8.4 有限 reason，不携带文本 | 纯函数；rewriter |
| 建议新增：`knowledge.rewrite.KnowledgeQuestionRewriter.rewrite` | `async def rewrite(self, *, original_question: str, timeout_s: float) -> RewriteStageResult` | guard 决定、model context accessor、固定 `(knowledge_rewrite,\"1\")` task、候选/回退 | success 或 question_denied/input_invalid/timeout/failure；不传播 Provider 异常 | 至多一次模型调用；Capability |
| 建议新增：`knowledge.rewrite.KnowledgeRewriteTaskV1.definition` | `@staticmethod def definition() -> ModelTaskDefinition[KnowledgeRewriteInput, KnowledgeRewriteOutput]` | 无运行输入；固定 task ID/version、Prompt、strict DTO、输入/token/timeout 上限 | 冻结 definition；静态自校验失败阻止启动 | 纯函数；顶层 model task registry |
| 建议新增：`knowledge.domain_selection.DeterministicDomainSelector.select` | `def select(self, *, original_question: str, enabled_domains: tuple[LogicalKnowledgeDomain, ...]) -> DomainSelection` | 税务锚点、有限分类词、启用快照 | 冻结 0～2 域 | 纯函数；Capability |
| 建议新增：`knowledge.planning.KnowledgeRetrievalPlanBuilder.build` | `def build(self, *, rewrite: RewriteResult, domains: DomainSelection, settings: KnowledgeSettings) -> KnowledgeRetrievalPlan` | 非空域、query/limit、固定路径 | 冻结最多四项 plan；非法内部状态抛 typed error | 纯函数；Capability |
| 建议新增：`knowledge.context.to_retrieval_context` | `def to_retrieval_context(context: CapabilityExecutionContext) -> KnowledgeRetrievalContext` | 校验 user subject/token、ID、deadline/cancellation；不复制原问题 | 冻结含 opaque token 的最小读取 context；非法抛有限 context error | 纯函数；Capability→retrieval stage |
| 建议新增：`knowledge.context.to_evidence_context` | `def to_evidence_context(context: CapabilityExecutionContext) -> KnowledgeEvidenceContext` | 校验 subject、ID、deadline/cancellation；明确排除 token/original question | 冻结无 JWT evidence context；非法抛有限 context error | 纯函数；Capability→evidence stage |
| 建议新增：`knowledge.capability.compute_phase_deadline` | `def compute_phase_deadline(*, now_monotonic: float, request_deadline: float, phase_timeout_s: float, reserve_s: float = 0.1) -> float` | 全部 finite 且正值；使用同一 loop clock | 返回 12.2 绝对截止；已耗尽抛有限 phase-timeout | 纯函数；Capability 每阶段 |
| 建议新增：`knowledge.contracts.KnowledgeRetrievalStage.execute` | `async def execute(self, *, plan: KnowledgeRetrievalPlan, context: KnowledgeRetrievalContext, timeout_s: float) -> RetrievalStageResult[TBatch]` | plan/context 冻结且剩余预算有效 | 10.2 有限 result；异常不得穿透 | 一次只读 retrieval stage；Capability |
| 建议新增：`knowledge.contracts.KnowledgeEvidenceStage.build_result` | `async def build_result(self, *, input: KnowledgeEvidenceInput[TBatch], context: KnowledgeEvidenceContext, timeout_s: float) -> EvidenceStageResult` | input/context 冻结；denied flag 不可清除；无 JWT | 10.2 有限 result；不得构造 `CapabilityResult` | 一次 evidence stage；Capability |
| 建议新增：`knowledge.capability.KnowledgeQueryCapability.map_retrieval_result` | `def map_retrieval_result(self, *, result: RetrievalStageResult[TBatch], plan: KnowledgeRetrievalPlan) -> RetrievalDecision[TBatch]` | 严格校验 kind/stage_code、coverage 精确分区、计数和 partial 条件；不读取 batch | `continue_to_evidence(batch, coverage)` 或固定公共终止 `CapabilityResult`；非法时丢弃载荷并返回 `knowledge.invalid_stage_result` | 纯映射；`handle` |
| 建议新增：`knowledge.capability.KnowledgeQueryCapability.map_evidence_result` | `def map_evidence_result(self, *, result: EvidenceStageResult, question_egress_denied: bool) -> CapabilityResult` | 严格校验 10.2 union、JSON 上限、egress 组合与 denied flag | 仅返回 11.3 固定公共组合；非法时丢弃载荷并返回 `knowledge.invalid_stage_result` | 纯映射；`handle` |
| 建议新增：`knowledge.capability.KnowledgeQueryCapability.handle` | `async def handle(self, input: KnowledgeQueryArguments, context: CapabilityExecutionContext) -> CapabilityResult` | 固定顺序、stage result/coverage/总 deadline | 合法公共结果；runtime shutdown cancel 传播 | 至多 1 rewrite、1 retrieval、1 evidence stage；core |
| 建议新增：`knowledge.provider.KnowledgeCapabilityProvider.registrations` | `def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]` | 启动设置和依赖已冻结；返回值精确符合核心 Provider Protocol | 精确一个 enabled/disabled candidate | 无运行 I/O；core composition root |

## 14. 测试与验证设计

### 14.1 测试定义

| 测试编号 | 状态 | 设计规则 | 层级 | 建议路径/用例 | Fixture、动作 | 关键断言 | 失败信号 |
|---|---|---|---|---|---|---|---|
| `TEST-KFLOW-001` | 建议新增 | `DR-KFLOW-001/002/014` | Unit/Contract | `agent-runtime/tests/unit/knowledge/test_capability_contract.py` | 8.2 精确 descriptor/schema、空/非空 arguments、context 原问题 | 与核心字段逐项一致：api_version=1、kind=query、固定展示字段；只注册一个 ID；空参数成功校验；handler 读取 context 原问题 | kind/version 漂移、question/域进入 arguments 或非法公共组合 |
| `TEST-KFLOW-002` | 建议新增 | `DR-KFLOW-002/003` | Unit | `agent-runtime/tests/unit/knowledge/test_rewrite.py` | 五类 matcher 的重叠/重复/每类与合计边界±1、数字/日期/文号/条款/否定、超长；guard denied、gateway input_denied/timeout/failure | 五类 tuple 不精确相等即拒绝；超界原问题不截断；最多 3 候选；只有 guard denied 设置 flag/策略版本且 gateway=0；其他失败可回退但 flag=false；模型调用≤1 | matcher 漂移、丢保护项仍采纳、input_denied 混义、静默截断或 retry |
| `TEST-KFLOW-003` | 建议新增 | `DR-KFLOW-004/005` | Unit | `agent-runtime/tests/unit/knowledge/test_domain_selection.py` | 精确词表每项、条款 regex 边界/超长、重叠短长词、政策、法律、混合、通用税务、非税、禁用域 | 字面匹配/单域/双域/零域结果及顺序精确；未知域无法出现 | 实现自增同义词、模型/配置创建域或索引名进入结果 |
| `TEST-KFLOW-004` | 建议新增 | `DR-KFLOW-006` | Unit | `agent-runtime/tests/unit/knowledge/test_planning.py` | 1/2 域、候选上限边界 | 每域两路、顺序稳定、最多 4 项、无物理字段 | 缺路径、重复项、DSL/URL/索引字段 |
| `TEST-KFLOW-005` | 建议新增 | `DR-KFLOW-007/008/010/012/014` | Integration with fakes | `agent-runtime/tests/integration/knowledge/test_flow_with_fake_stages.py` | plan 全路径的完整/遗漏/重复/额外/三集合重叠 coverage；generic opaque batch、部分/no-result/denied evidence；不可读过滤为空与真实空结果 | `map_retrieval_result` coverage 精确分区及 complete iff；两类空结果向用户均为 `no_candidate` 且结构相同；opaque batch 只透传；Capability 唯一映射；denied 下 summary=0；无持久状态 | 存在性泄漏、flow 读取 batch、stage 直接返回公共结果、出域拒绝后调用模型或部分失败伪完整 |
| `TEST-KFLOW-006` | 建议新增 | `DR-KFLOW-007/008/013/014` | Parameterized Unit | `agent-runtime/tests/unit/knowledge/test_failure_priority.py` | 所有 retrieval/evidence stage_code、forbidden/unverifiable/timeout/failure/no-result 的笛卡尔代表集、自由 code/source 注入 | 固定优先级和公共映射；stage 不能选择公共 code/source；失败无载荷 | forbidden 被覆盖、自由错误穿透或失败变 no_result |
| `TEST-KFLOW-007` | 建议新增 | `DR-KFLOW-004/009` | Unit | `agent-runtime/tests/unit/knowledge/test_settings_and_catalog.py` | 每个 bool/int 边界；partial threshold 与 per-path 的交叉边界；domain 空项/重复/顺序/大小写/尾逗号；未知前缀 key；缺/重复 path/policy ref；disabled 下非法值 | 非法配置/目录均不就绪；threshold≤per-path；合法配置按 catalog order 冻结；两域 path/policy ref/版本精确 | 宽松解析、不可达 partial 配置、缺策略接缝、disabled 隐藏错误或配置扩权 |
| `TEST-KFLOW-008` | 建议新增 | `DR-KFLOW-001/009/012` | Contract | `agent-runtime/tests/contract/knowledge/test_provider_registration.py` | disabled、1 域、2 域 provider；task-definition/model-registry/core-registry fakes | 精确一个 candidate；disabled 不建 task/client/stage；enabled 先冻结唯一 rewrite task 再建 gateway/provider；model 公共模块无 Knowledge import | 循环装配、动态扫描、重复 task、多个动作或缺依赖仍就绪 |
| `TEST-KFLOW-009` | 建议新增 | `DR-KFLOW-002/010/011/012` | Async Unit/Log | `agent-runtime/tests/unit/knowledge/test_deadline_cancellation_logging.py` | 可控 loop clock、忽略 timeout_s 的阻塞 stage、phase 边界±1、外层取消；sentinel token/subject/question 与 spies/caplog | 绝对 phase deadline 强制取消并 await；reserve 不被占用；runtime cancel 传播；rewriter 只读 model accessor；token 只到 retrieval context；evidence context 无 token，原问题只从 typed input 取得；日志无正文 | 仅传 timeout、后台继续、完整 context 泄漏、迟到结果或敏感日志 |
| `TEST-KFLOW-010` | 建议新增 | `DR-KFLOW-012/013` | Architecture | `agent-runtime/tests/architecture/test_knowledge_boundaries.py` | AST/import/signature 检查 | core 无 knowledge import；Knowledge 仅导入 neutral model contract/guard/accessor，无 DeepSeek/ES/BGE DTO；Capability 不访问 batch 字段，stage 不返回 `CapabilityResult` | 依赖反转、Provider 类型泄漏、公共映射权泄漏或通用工作流引擎 |

### 14.2 关键场景

| 场景 | rewrite Provider 调用 | retrieval 调用 | evidence 调用 | 结果 |
|---|---:|---:|---:|---|
| arguments 非空 | 0 | 0 | 0 | `invalid_argument` |
| 改写成功、政策单域 | 1 | 1（plan 2 项） | 1 | 由 evidence stage 决定 |
| 通用税务问题、双域 | 1 | 1（plan 4 项） | 1 | 由 evidence stage 决定 |
| 非税问题、零域 | 1（输入闸门拒绝时 transport 为 0） | 0 | 0 | 按 L1 固定顺序在改写后选择零域并返回 `no_result` |
| 改写 Provider 失败且可回退 | 1 | 1 | 视检索结果 | mode=`original_fallback` |
| 全局问题闸门拒绝且不可回退 | 0 | 0 | 0 | `model_egress_denied` |
| guard allowed 后 gateway input_denied 且不可回退 | 0 | 0 | 0 | `internal_failure`；不得标记 question egress denied |
| 任一整域 forbidden | 1 | 1 | 0 | `forbidden` |
| 单路失败且满足充分性 | 1 | 1 | 1 | coverage incomplete，不能伪完整 |
| 某已选域全部路径技术失败 | 1 | 1 | 0 | `timeout/downstream_failure` |
| 全部合法路径无候选 | 1 | 1 | 0 | `no_result` |

### 14.3 验证定义

| 验证编号 | 工作目录/前置 | 命令或人工步骤 | 验证范围与充分性 | 预期结果 | 当前执行状态 |
|---|---|---|---|---|---|
| `VAL-KFLOW-001` | `D:\codex`；本文和 validator 可读 | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md --root D:\codex --strict` | 只证明结构、追踪、引用和质量规则，不替代语义评审 | 0 errors、0 warnings | 已执行：0 errors、0 warnings（2026-07-25） |
| `VAL-KFLOW-002` | 未来 `D:\codex\agent-runtime`；Knowledge unit/contract tests 已创建 | `python -m pytest tests/unit/knowledge tests/contract/knowledge -q` | 证明动作、改写、域、计划、配置和失败矩阵 | 全部通过 | 未执行：代码/测试不存在且未授权 |
| `VAL-KFLOW-003` | 未来 `D:\codex\agent-runtime`；fake stages/architecture tests 已创建 | `python -m pytest tests/integration/knowledge tests/architecture/test_knowledge_boundaries.py -q` | 证明 stage 接缝、请求状态、取消和依赖方向；不证明真实 ES/BGE/DeepSeek | 全部通过 | 未执行：代码/测试不存在且未授权 |
| `VAL-KFLOW-004` | 未来 Python 工程和设置加载器已创建 | `python -m compileall -q src tests`、`python -m mypy --strict src tests`、`python -m pip check` | 证明签名、泛型 stage 和依赖一致；须与行为测试联合 | 三条无错误 | 未执行：工程不存在 |
| `VAL-KFLOW-005` | 本文、L2_00_01 v0.4、L2_00_02 v0.4、后续两份 L2 草案/评审证据 | 人工核对原问题同源、问题闸门、stage 类型、责任防重叠和门禁 | 证明跨 L2 语义未漂移，不替代真实集成 | 无未关闭 S0/S1 后方可申请切片实施 | 部分完成：本文、两个直接依赖及 L2_01_01 v0.2 均 Approved；L2_01_02 尚未创建，真实检索/证据契约仍未验证 |

## 15. 发布、迁移与回滚

- 本文建议模块均为新增，不修改数据库、索引、消息或既有业务接口。
- 能力默认 `AGENT_KNOWLEDGE_ENABLED=false`；P3 先用内存 fake retrieval/evidence stages 验证流程。
- 真实启用前必须完成 L2_01_01/L2_01_02 的直接依赖和相应集成门禁，不能以 fake 成功替代。
- 配置或依赖无效时 Runtime 不就绪；不得自动降为只有一个随机域或只有一条检索路径。
- 回滚优先禁用固定 capability 并重启 Runtime；若回滚代码，回退 Knowledge 模块和组合根装配即可，无数据回滚。
- v1 动作参数保持空对象；未来新增字段视为契约变化，需兼容分析和重新评审。

## 16. 风险、待确认事项与门禁

### 16.1 风险与待确认事项

| 编号 | 类型 | 证据缺口或风险 | 触发场景 | 影响 | 建议 | 是否阻塞/需授权 |
|---|---|---|---|---|---|---|
| `RISK-KFLOW-001` | 直接依赖 | L2_00_01 v0.4 `original_question` 与 L2_00_02 v0.4 问题闸门消费契约已复评关闭，但目标代码尚不存在 | 进入代码实施 | 实现仍可能偏离已批准签名 | 以两份 Approved L2、架构测试和 contract tests 联合验证 | 不阻塞本文；仍受 `KQ-GATE-002` |
| `RISK-KFLOW-002` | 域映射 | 真实税务内容是否能稳定映射为两域尚未证明 | P4 真实检索 | 逻辑域与物理数据不一致 | L2_01_01 核实元数据/只读映射；否则仅用受控测试域证明多域机制 | 不阻塞本文；阻塞真实两域声明 |
| `RISK-KFLOW-003` | 规则精度 | 代码词表可能对口语或交叉法规误选域 | P5 真实问题集 | 召回不足或多查 | 以阶段指标评估；需要时替换 `DomainSelector`，不修改 core | 不阻塞首版设计；阻塞效果达标结论 |
| `RISK-KFLOW-004` | 改写语义 | 有限保护项不能证明完整语义等价 | 复杂法律问句 | 检索偏离 | 始终保留原问题、无合法候选回退/失败、P5 对照评估 | 阻塞效果结论，不阻塞 fake 实现 |
| `RISK-KFLOW-005` | 下游契约 | Retrieval/Evidence stage 的具体 batch 尚由后续 L2 定义 | 端到端实现 | 类型或 failure 漂移 | 本文只透传泛型 batch；跨 L2 评审后联调 | 不阻塞本文流程切片；阻塞端到端 |
| `RISK-KFLOW-006` | 预算 | 8/20/15 秒尚无真实链路耗时证据 | P4 联调 | 误超时或余量浪费 | 保持硬上限，采集指标后在上位允许范围内收紧 | 不阻塞设计；阻塞性能结论 |
| `RISK-KFLOW-007` | 信息泄露 | no_result/coverage 暴露禁用域或不可读文档存在性 | 权限过滤或配置变化 | 推断知识存在 | 用户结果统一 `no_candidate`；只输出由问题确定的选中域与安全枚举；整域拒绝无领域载荷 | 阻塞实施测试 |

### 16.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威来源 | 责任方 | 最晚阶段 | 验证者与方法 | 状态 | 未关闭时允许/禁止动作 | 模拟或替代路径 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `KQ-GATE-001` | design_decomposition | L1_01→本文 | 编写本文 | L1_01 v0.2 五轮评审通过，v0.3 针对性复核保持关闭 | L1_01 14.2 | 项目维护者/独立评审方 | 本文前 | 核对评审记录 | Closed | 允许本文；不授权代码 | 不适用 |
| `KQ-GATE-002` | slice_implementation | 本文唯一负责的 Knowledge flow/config 切片 | 创建目标 Capability、配置、目录、改写/选择/计划代码与测试 | 本文独立评审通过；L2_00_01 v0.4 与 L2_00_02 v0.4 均 Approved；契约/测试/回滚明确；用户明确实施授权 | 本文评审、两份直接依赖状态、追踪矩阵 | 项目维护者 | P3 flow 实施前 | 独立设计评审和验证清单 | Open | 允许文档/fake 契约推演；禁止目标代码实施和完成声明 | 内存 fake stage 设计 |
| `CR-GATE-003` | integration | 原问题进入 DeepSeek 改写 | 外发可能敏感的用户问题 | L2_00_02 输入分类、最小化、零调用负向测试通过 | 模型 L2/Provider 契约 | 项目维护者/模型方 | 首次真实改写联调前 | model spy/负向测试 | Open | 只允许本地 rewrite fake 或非敏感授权 PoC；禁止敏感外发 | 原问题本地回退 |
| `SA-GATE-003` | integration | 真实 retrieval stage | 接入真实 ES/BGE | L2_01_01 契约、读取授权、模型兼容和负向测试通过 | L2_01_01/提供方 | 项目维护者/提供方 | P4 | 契约/集成测试 | Open | 本文可用 fake；禁止真实检索 | 内存统一候选 batch |
| `SA-GATE-006` | integration | 真实 evidence stage 模型输入 | 外发真实知识证据 | L2_01_02 三层策略、文档元数据和零调用测试通过 | L2_01_02/策略权威 | 项目维护者/模型方 | P4 | 出域矩阵/model spy | Open | 本文只透传 fake batch；禁止真实证据外发 | 合成安全证据 |

### 16.3 需要后续授权的动作

- 关闭本切片 `KQ-GATE-002`（`REV-L2-010` 已在直接依赖评审中关闭）。
- 创建或修改任何 `agent-runtime` 代码、配置、测试或依赖。
- 修改 `es-query-service`、BGE、DeepSeek、OpenAPI 或其他外部契约。
- 使用真实用户问题、真实知识正文或付费模型调用做联调。

## 17. 内部自检记录

作者自检只用于改善 Draft，不构成独立评审、Approved、实现授权或门禁关闭证据。

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-25 | 1 | 3 | 3 | 7 | 无 | 修复原问题权威缺口、L2 职责重叠、部分成功阈值、空参数动作、阶段结果和配置扩权问题 |
| 2 | 2026-07-25 | 0 | 1 | 2 | 3 | 无 | 修复配置降低部分成功阈值的扩权风险，统一 failure code/source 与门禁状态 |
| 3 | 2026-07-25 | 0 | 1 | 3 | 4 | 无 | 固定非税请求流程顺序、补充安全模型上下文投影和校验器要求的明确边界术语；严格校验通过 |

## 18. 独立正式评审记录

### 18.1 第 1 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-KFLOW-001` | S1 | rewrite/evidence Protocol 接收完整 `CapabilityExecutionContext`，但安全章节又规定 JWT 只能进入 retrieval，最小权限边界不可实现 | rewriter 改用 model accessor；分别投影含 token 的 retrieval context 与无 token 的 evidence context | Closed（第 2 轮） |
| `REV-KFLOW-002` | S1 | `question_egress_denied` 只留在 `RewriteResult`，未传给 Evidence stage，后续摘要可能绕过问题输入拒绝 | flag 与策略版本进入 Evidence input，denied 下 allowed/safe payload 视为非法且模型调用为 0 | Closed（第 2 轮） |
| `REV-KFLOW-003` | S1 | gateway `input_denied` 也可能来自请求超界，不能作为问题策略拒绝证据，且 denied 决定缺消费方所需策略版本 | 原子补正 L2_00_02 v0.4；Knowledge 显式调用 guard，只有其 denied 才设置 flag | Closed（第 2 轮） |
| `REV-KFLOW-004` | S1 | Evidence stage 直接返回公共 `CapabilityResult`，与 Knowledge Capability 唯一映射公共结果的责任冲突 | 改为有限 `EvidenceStageResult`，Capability 校验并唯一构造公共结果 | Closed（第 2 轮） |
| `REV-KFLOW-005` | S1 | Knowledge task 名称和自行投影 `ModelCallContext` 与已批准 L2_00_02 的枚举 task/accessor 契约不一致 | 固定 `(knowledge_rewrite,\"1\")`，显式使用 guard 与 `ModelCallContextAccessor` | Closed（第 2 轮） |
| `REV-KFLOW-006` | S1 | 逻辑域只给“示例/等”词表且 `semantic_drift` 引用未定义的域外实体识别，无法产生一致实现 | 固化 v1 词表、条款 regex、字面匹配和保护项集合判定，明确不声明通用实体识别 | Closed（第 2 轮） |
| `REV-KFLOW-007` | S2 | “禁止依赖”列表用肯定句写成 `agent-core` 导入 Knowledge，可能被误读为所需依赖 | 每项改为明确“不得”约束 | Closed（第 2 轮） |
| `REV-KFLOW-008` | S2 | Knowledge Provider 签名缺少完整 Protocol 对齐，typed candidate 返回可能与核心 invariant generic 不兼容 | 改为核心规定的 `tuple[CapabilityRegistrationCandidate[Any], ...]` 完整签名 | Closed（第 2 轮） |
| `REV-KFLOW-009` | S2 | 直接依赖仍标为 In Review/Draft，风险和门禁继续引用已关闭 `REV-L2-010` | 同步 L2_00_01 v0.4、L2_00_02 v0.4 Approved 状态和门禁证据 | Closed（第 2 轮） |

首轮修复不构成评审通过，不关闭 `KQ-GATE-002` 或任何真实模型、检索、证据门禁。

### 18.2 第 2 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-KFLOW-010` | S1 | `RewriteStageResult`、候选判定和多个 stage 输出缺少完整 variant/字段，调用方需猜测失败与载荷组合 | 补齐 rewrite/validation/evidence/retrieval 有限 union、字段互斥与关键映射函数 | Closed（第 3 轮） |
| `REV-KFLOW-011` | S1 | Retrieval/Evidence 可返回自己的 `failure(code/source)`，仍可越过 Capability 选择公共失败语义 | 改为有限 stage code，由 Capability 唯一映射固定公共 code/source | Closed（第 3 轮） |
| `REV-KFLOW-012` | S1 | 子预算只通过 `timeout_s` 传给 stage，违反协议的 stage 可占满总预算并绕过 8/20/15 秒边界 | 增加单调绝对 phase deadline、`asyncio.timeout_at`、取消回收和响应预留 | Closed（第 3 轮） |
| `REV-KFLOW-013` | S2 | 保护项 matcher/数量、目录版本和配置版本只有概念描述，无法稳定比较候选或追踪快照 | 固化五类提取/比较算法、数量上限和两个版本常量 | Closed（第 3 轮） |

第二轮修复仍不构成评审通过，不授权任何目标代码、真实检索或模型调用。

### 18.3 第 3 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-KFLOW-014` | S1 | descriptor 使用核心不存在的 `kind=knowledge`/`contract_version` 且缺展示/alias 精确值，注册必然失败或实现分叉 | 对齐 `api_version=1`、`kind=query` 和完整 descriptor/空 Schema | Closed（第 4 轮） |
| `REV-KFLOW-015` | S1 | coverage 未要求全部计划路径恰好归入一个集合，遗漏/重复路径仍可能被接纳为完整或部分成功 | 增加精确分区、计数、complete iff、no_result 与非法结果规则 | Closed（第 4 轮） |
| `REV-KFLOW-016` | S1 | 用户结果 `no_authorized_candidate` 会证明存在不可读文档，违反候选过滤的防存在性泄漏要求 | 对外统一 `no_candidate`，真实空与读取过滤为空必须同形 | Closed（第 4 轮） |
| `REV-KFLOW-017` | S2 | bool/int/domain/env 前缀解析未固化，宽松 trim/大小写/disabled 忽略可造成配置漂移 | 固定精确解析、未知前缀失败、disabled 仍校验和 catalog order | Closed（第 4 轮） |
| `REV-KFLOW-018` | S1 | Knowledge 定义 task 而 model gateway 冻结 registry，但组合根未规定谁先构造，可能形成 model→Knowledge 反向依赖或漏注册 | Knowledge 提供纯 definition，顶层组合根显式合并后冻结 gateway，再构造 rewriter/provider | Closed（第 4 轮） |

第三轮修复不关闭 `KQ-GATE-002`；下一轮必须从全文重新检查，而非只确认新增文本存在。

### 18.4 第 4 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-KFLOW-019` | S1 | L1 要求逻辑域目录持有 allowed paths 和默认出域策略引用，本文目录却未定义，Evidence stage 无稳定策略接缝 | 两域分别固化 keyword/vector 与 opaque policy ref，并加入目录类型/启动校验 | Closed（第 5 轮） |
| `REV-KFLOW-020` | S2 | partial threshold 可高于单域仅一条成功路径的理论候选上限，配置合法却永远无法部分成功 | 增加 `min_partial_candidates <= per_path_candidates` 交叉校验 | Closed（第 5 轮） |
| `REV-KFLOW-021` | S2 | retrieval stage code 有限但没有对应唯一映射函数签名，Capability 实现仍可能分散映射 | 增加 `map_retrieval_result` 精确签名和测试入口 | Closed（第 5 轮） |

第四轮修复仍不构成通过；第 5 轮须全量复核并只在无新增 S0/S1/S2 时终审。

### 18.5 第 5 轮终审结论

第 5 轮从需求追踪、单动作边界、descriptor、原问题/模型输入、JWT 最小传播、逻辑域、
rewrite/stage 类型、coverage/失败优先级、绝对预算、配置/组合根、实现签名和测试反证重新
全量检查；未发现新的 S0/S1/S2，`REV-KFLOW-001`～`021` 全部关闭。本文 Approved，
设计已具备 flow/config 切片的实施就绪条件；但 `KQ-GATE-002` 未关闭，检索 L2_01_01
仍为 Draft 且证据 L2_01_02 尚未创建，不能据此实施目标代码、启用真实链路或声明效果达标。

## 19. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] `knowledge.query` 动作、空参数、原问题来源和公共结果组合明确。
- [x] 两个逻辑域、单域/多域/零域规则和物理映射非职责明确。
- [x] 改写输入、输出、保护约束、回退和失败语义明确。
- [x] 检索计划、stage Protocol、泛型 batch 和部分成功阈值明确。
- [x] Python 模块、关键函数、输入/输出、异步、错误、副作用和消费者明确。
- [x] 配置默认值、范围、扩权判定、启动失败和重启生效明确。
- [x] 权限、敏感数据、日志、预算、取消、无重试/无持久化明确。
- [x] 开放门禁均具有控制动作、证据、责任方、最晚阶段和替代路径。
- [x] 作者自检无遗留 Blocker/Major。
- [x] `validate_detailed_design.py --strict` 已通过；该结果仅是确定性文档证据。
- [x] 独立正式评审已关闭全部 S0/S1/S2。
- [ ] 本切片 `KQ-GATE-002` 已在另行实施授权后关闭。

## 20. 当前结论

- 本文版本：v0.2。
- 文档状态：Approved。
- 评审状态：五轮独立评审通过，`REV-KFLOW-001`～`021` 全部 Closed。
- 实施状态：未实施。
- 生效状态：未生效。
- 是否可作为实现依据：否；设计已实施就绪，但本切片 `KQ-GATE-002` 为 Open 且本轮未获目标代码/测试实施授权。
- 确定性文档校验：已通过，0 errors、0 warnings；不替代独立正式评审。
- 当前只允许文档、自检和 fake 契约推演；不允许创建目标代码、启用真实检索或把真实问题/证据发送外部模型。
