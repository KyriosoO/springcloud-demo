# [L2_01_00] 单体 Agent Knowledge 查询流程与配置详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Knowledge 查询流程与配置详细设计 |
| 文档标识 | `SA-L2-KNOWLEDGE-FLOW-001` |
| 文档编号 | `L2_01_00` |
| 文档路径 | `docs/design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Draft |
| 当前版本 | v0.1 |
| 日期 | 2026-07-25 |
| 适用范围 | Python `agent-runtime` 内唯一 `knowledge.query` 能力的参数契约、请求级流程状态、问题改写、首批逻辑知识域、域选择、检索计划、跨域失败优先级、配置与组合根 |
| 上位文档 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v1.2；[`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v0.4；[`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v0.2（已评审/已通过，`KQ-GATE-001` 已关闭） |
| 直接依赖 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4（In Review）的能力 API、`original_question` 与公共结果；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v0.1 Draft 的受控结构化模型任务 |
| 下位/后续契约 | 规划中的 `L2_01_01` Knowledge 检索与本地模型接入；规划中的 `L2_01_02` Knowledge 证据、出域、摘要与效果验证 |
| 实现基线 | 当前工作区不存在目标 `agent-runtime`、Knowledge Capability、Knowledge Adapter 或目标 Python 测试；既有 `es-query-*` 与历史 Agent 代码只作为迁移输入，不是目标实现基线 |
| 是否可作为实现依据 | 否，本文尚未独立评审，`L2_00_01` v0.4 针对性复评及本切片 `KQ-GATE-002` 均为 Open |
| 当前允许实施范围 | 本文编写、自检、契约样例和使用内存 fake stage 的隔离推演 |
| 当前禁止动作 | 创建或修改目标代码、配置、测试、ES/BGE/DeepSeek 公共契约；启用真实知识链路；关闭实施、集成或效果门禁 |
| 修改权限 | 本轮用户已授权第二批 L2 与必要直接关联文档原子同步，并授权 Git commit/push；代码、配置、Schema、外部契约和真实数据调用未获授权 |
| 维护责任人 | 项目维护者（个人开发者，姓名未在需求中指定） |

> 本文只拥有 Knowledge 单动作内部的流程与配置，不拥有物理索引、ES/BGE 协议、统一候选字段、证据出域字段或摘要事实校验。新文档默认保持 Draft；作者自检和严格校验不构成 Approved、实现授权或真实链路可用证据。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 执行第二批 L2 详细设计 | 创建 `knowledge.query` 空参数动作、原始问题同源消费、问题改写、税务政策/税务法律两域、确定性域选择、检索计划、失败优先级、配置、组合根和实现/测试追踪 |
| 2 | 2026-07-25 | 1、4、8～10、13～17 | 作者第 1 轮自检修复 | 将原始问题来源收敛到 `CapabilityExecutionContext.original_question`，把物理检索/候选/证据字段留给后续 L2，并补齐阶段协议、部分成功阈值、失败映射与门禁 |
| 3 | 2026-07-25 | 7、9、12、14、17～19 | 作者第 2～3 轮自检与严格校验修复 | 明确禁止反向依赖、错误码/一致性/安全审计术语，固定非税问题仍按 L1 顺序只改写一次，补充安全 `ModelCallContext` 投影，并将候选/部分成功配置改为只能从代码上限收紧 |

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
| `REQ-KFLOW-002`、`CON-KFLOW-002` | 问题改写 | `DR-KFLOW-002`、`DR-KFLOW-003` | rewriter、semantic guard | 原问题/改写请求状态 | `IMPL-KFLOW-002/004` | `TEST-KFLOW-002/009` | `VAL-KFLOW-002/003` |
| `REQ-KFLOW-003`、`CON-KFLOW-003` | 域目录/选择 | `DR-KFLOW-004`、`DR-KFLOW-005` | catalog、selector | 两域冻结快照 | `IMPL-KFLOW-003/005` | `TEST-KFLOW-003/007` | `VAL-KFLOW-002/003` |
| `REQ-KFLOW-004`、`CON-KFLOW-004` | 检索计划 | `DR-KFLOW-006` | plan builder | 最多四个逻辑意图 | `IMPL-KFLOW-006` | `TEST-KFLOW-004` | `VAL-KFLOW-002` |
| `REQ-KFLOW-005`、`CON-KFLOW-005` | 阶段聚合 | `DR-KFLOW-007`、`DR-KFLOW-008`、`DR-KFLOW-014` | Capability | coverage/公共终态 | `IMPL-KFLOW-001/007` | `TEST-KFLOW-005/006` | `VAL-KFLOW-002/003` |
| `REQ-KFLOW-006`、`CON-KFLOW-006` | 启动配置 | `DR-KFLOW-009` | settings、provider | 冻结配置/就绪 | `IMPL-KFLOW-003/009` | `TEST-KFLOW-007/008` | `VAL-KFLOW-002/004` |
| `REQ-KFLOW-007`、`CON-KFLOW-007` | 请求状态 | `DR-KFLOW-010` | Capability | handler 局部状态 | `IMPL-KFLOW-001/007` | `TEST-KFLOW-005/009` | `VAL-KFLOW-003` |
| `REQ-KFLOW-008`、`CON-KFLOW-009` | stage 接缝 | `DR-KFLOW-012`、`DR-KFLOW-013` | flow、后续 L2 | 泛型 batch 不被流程解释 | `IMPL-KFLOW-001/007/009` | `TEST-KFLOW-005/010` | `VAL-KFLOW-003/005` |
| `REQ-KFLOW-009`、`CON-KFLOW-008` | 预算/取消 | `DR-KFLOW-011` | Capability、stage | 子预算/取消 | `IMPL-KFLOW-004/007` | `TEST-KFLOW-009` | `VAL-KFLOW-003` |
| `CON-KFLOW-010` | 公共结果 | `DR-KFLOW-014` | Capability | 合法 status/egress/failure | `IMPL-KFLOW-001/007` | `TEST-KFLOW-001/006` | `VAL-KFLOW-002/003` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 交互契约 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|---|
| L1_01 v0.2 | parent | 细化 `L2_01_00` 唯一范围 | 定义 Knowledge 架构边界与门禁 | `knowledge.query`、五阶段语义 | 上位权威 | 只读 |
| L2_00_01 v0.4 | direct dependency | 消费能力 API、`original_question` 和结果契约 | 核心执行、注册、图状态和公共结果不变量 | `CapabilityHandler` | 公共执行上下文 | 本轮仅已授权原子补正；当前 In Review |
| L2_00_02 v0.1 | direct dependency | 定义 Knowledge 改写任务的领域输入/输出校验 | Provider、问题输入闸门和供应商错误 | `BoundedStructuredModelGateway` | 模型调用状态 | 只读 |
| 规划中的 L2_01_01 | downstream provider | 定义检索计划消费和 coverage 控制语义 | ES/BGE、候选、融合、重排、读取授权 | `KnowledgeRetrievalStage[TBatch]` | 排序候选 batch | 只读，尚未创建 |
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
| `FACT-KFLOW-001` | 已存在（文档） | L1_01 v0.2 已评审通过并关闭 L2 编写门禁 | 允许创建本文，不授权代码 |
| `FACT-KFLOW-002` | 已存在（文档） | L2_00_01 v0.4 已补充 handler 可读的 `original_question`，但待针对性复评 | 本文可以形成 Draft；实施仍阻塞 |
| `FACT-KFLOW-003` | 已存在（文档） | L2_00_02 定义受控结构化模型任务和 `deepseek-v4-pro` Provider 边界 | 本文不重复供应商协议 |
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
  → BoundedStructuredModelGateway        ← L2_00_02 实现
```

禁止依赖、禁止绕过和反向依赖规则：

- `agent-core` 导入 `agent_runtime.knowledge`。
- Knowledge 导入 DeepSeek DTO、ES DSL、物理索引或 BGE HTTP DTO。
- Retrieval stage 调用 Evidence stage，或 Evidence stage反向选择域。
- 模型/配置生成新的 capability ID、logical domain ID 或 retrieval path。

### 7.3 内聚与耦合判断

问题改写、域选择和检索计划共同决定“查什么、查哪些逻辑范围”，因此内聚在 Knowledge Capability；物理检索与证据出域具有独立协议/安全权威，保留为两个 stage 接缝。核心只看到统一 handler，后续改变融合算法、ES 接口或证据策略不会修改核心及本流程的动作契约。只设置两个必需接缝，避免把每一步抽象为独立服务或通用工作流平台。

## 8. 公共类型、动作与请求状态

### 8.1 设计规则目录

| 规则编号 | 规则 | 责任主体 | 触发条件 | 输出/状态效果 |
|---|---|---|---|---|
| `DR-KFLOW-001` | v1 只注册 canonical ID `knowledge.query`，argument Schema 精确为空对象且 `additionalProperties=false` | provider、validator | 启动/候选校验 | 模型只选择动作，不能回填问题/域/路径 |
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
| `DR-KFLOW-012` | 本流程只依赖 `KnowledgeRetrievalStage[TBatch]` 与 `KnowledgeEvidenceStage[TBatch]`；不解释 `TBatch` 内容，不调用下游内部 Port | Capability | 装配/执行 | 后续 L2 可独立实现 |
| `DR-KFLOW-013` | 下游 stage 只能返回有限 typed result；原始异常、ES/BGE/模型响应不得穿透 | stage、Capability | stage 完成 | 固定失败映射 |
| `DR-KFLOW-014` | Capability 只构造 L2_00_01 允许的 status/egress/failure 组合；前置无匹配域为 `no_result + not_applicable`，技术失败无领域载荷 | Capability | 终止 | 核心无需领域推导 |

### 8.2 `knowledge.query` 动作契约

| 项目 | 精确设计 |
|---|---|
| `capability_id` | `knowledge.query` |
| `kind` | `knowledge` |
| `contract_version` | `1` |
| arguments | 精确 `{}`；任一属性均 `invalid_argument/knowledge.arguments_not_empty` |
| 原始问题 | `CapabilityExecutionContext.original_question`；不位于 arguments |
| handler | `KnowledgeQueryCapability.handle` |
| 下游副作用 | 只读；0～1 次改写模型 stage、1 次检索 stage、0～1 次证据 stage |

空参数不是缺少设计，而是明确阻止动作选择模型控制原问题、域、路径、候选数量、物理资源或 Provider。后续若需要用户显式过滤条件，必须由新的上位需求和动作契约版本定义，不能向 v1 任意加字段。

### 8.3 逻辑域目录

| domain ID | 稳定语义 | 必需税务锚点 | 分类词示例 | 代码顺序 |
|---|---|---|---|---:|
| `tax.policy` | 税务机关公告、通知、规范性文件、执行口径、优惠政策及政策解释 | `税/税务/税收/纳税/增值税/所得税/发票` 等有限代码词表至少一个 | `政策/公告/通知/优惠/指引/口径/征管/实施` | 10 |
| `tax.law` | 税收相关法律、行政法规、司法解释及法定条文 | 同左税务锚点至少一个 | `法律/法规/条例/司法解释/法条/第…条/违法/处罚` | 20 |

分类词只是 v1 可验证路由规则，不声明真实文档已经完成物理归类。一个问题可以同时选择两域；一份物理文档是否属于某域由 L2_01_01 的受控映射证明。配置不得修改词表、描述、顺序或 domain ID。

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
| `ProtectedConstraintSet` | `numbers`、`dates`、`document_numbers`、`article_refs`、`negations`，均为有界 tuple[str] | 从原问题确定性提取；不记录全文 |
| `RewriteCandidate` | `text`、`source=model/original_fallback`、`ordinal` | NFC、非空、≤`max_retrieval_query_chars`、保护约束完整 |
| `RewriteResult` | `original_question`、`selected_query`、`candidates`、`mode`、`model_policy_version`、`question_egress_denied` | 原问题与 context 精确相同；selected 必须来自 candidates |
| `DomainSelection` | `selected_domain_ids`、`catalog_version`、`reason_codes` | ID 已注册/启用、无重复、按目录顺序、≤2 |
| `RetrievalPlanItem` | `logical_domain_id`、`path`、`query_text`、`candidate_limit`、`ordinal` | path 仅 keyword/vector；无物理字段 |
| `KnowledgeRetrievalPlan` | `items`、`selected_domain_ids`、`config_version` | 每个域恰有两项；最多 4 项 |
| `RetrievalCoverage` | `successful_paths`、`no_result_paths`、`failed_paths`、`candidate_count_by_domain`、`complete` | 仅有限 path/status/count；不含正文或原始异常 |
| `KnowledgeExecutionState[TBatch]` | `stage`、`rewrite`、`domains`、`plan`、`retrieval_result`、`started_monotonic` | handler 私有不可变快照；可选字段只能在对应阶段后出现 |

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

- 阿拉伯/中文数字、百分比和金额片段。
- 年/月/日、日期区间及“以前/以后/期间”。
- 文号、`第…条/款/项` 等法律定位。
- `不/未/不得/禁止/免税/除外/仅/至少/至多/超过/低于` 等否定与边界词。

模型候选必须逐项保留提取出的稳定文本片段。该检查不能证明完整语义等价，因此只作为必要条件；候选若引入新的日期、数字、文号、否定或逻辑域外实体，也判定 `semantic_drift`。首期不引入第二模型做语义判定，避免以另一个不可信输出证明第一个输出。

### 9.3 受控模型任务

Knowledge 定义代码绑定任务 `knowledge.question.rewrite.v1`，通过 L2_00_02 的 gateway 执行一次：

```text
input:
  original_question: str
  max_candidates: int (1..3)

output:
  candidates: tuple[str, ...] (1..3)
```

Prompt 只要求生成保持主体、时间、条件、否定、文号和法律语义的检索表达，不要求回答问题，不接收候选文档、JWT、物理域或 Provider 参数。gateway 的通用问题输入闸门仍先于 DeepSeek 调用。

rewriter 只能从执行上下文确定性投影 `ModelCallContext(request_id, correlation_id, deadline_monotonic)`；不得把 `CapabilityExecutionContext` 整体、subject 或 token 交给 gateway。投影失败按内部配置错误终止，不以缺失字段调用模型。

### 9.4 候选选择与回退

1. 按 provider 返回顺序校验候选。
2. 去除与前序候选规范化后完全相同的重复项。
3. 选择首个通过保护约束且不超长的候选。
4. 无合法候选时，只有 `allow_original_fallback=true` 且规范化原问题不超过检索查询上限，才使用 `original_fallback`。
5. 输入闸门拒绝时允许本地原问题回退，但必须设置 `question_egress_denied=true`；这不允许后续把问题或证据发送模型。
6. Provider timeout/failure/invalid output 可按同一规则回退，不进行第二次模型调用。
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
        context: CapabilityExecutionContext,
        timeout_s: float,
    ) -> RetrievalStageResult[TBatch]: ...

class KnowledgeEvidenceStage(Protocol[TBatch]):
    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[TBatch],
        context: CapabilityExecutionContext,
        timeout_s: float,
    ) -> CapabilityResult: ...
```

`RetrievalStageResult` 是有限 tagged union：

| kind | 必填字段 | 禁止字段 | Capability 行为 |
|---|---|---|---|
| `success` | `batch`、`coverage` | failure | 校验 coverage 后进入 evidence stage |
| `no_result` | `coverage` | batch/failure | 返回 `no_result + not_applicable` |
| `forbidden` | `failure(code/source)` | batch/正文 | 返回 `forbidden` |
| `timeout` | `failure(code/source)` | batch/正文 | 返回 `timeout` |
| `downstream_failure` | `failure(code/source)` | batch/正文 | 返回 `downstream_failure` |

`KnowledgeEvidenceInput[TBatch]` 只含 `original_question`、`selected_query`、`selected_domain_ids`、`coverage` 和 opaque `batch`。其证据字段及出域行为由 L2_01_02 固化。

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
10. 合法 success 时在剩余预算内调用一次 evidence stage。
11. 校验 evidence stage 返回的 `CapabilityResult` 合法组合并返回核心。

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
| 改写输入拒绝且不可本地回退 | `model_egress_denied` | `knowledge.rewrite_input_denied` | policy | denied，使用模型输入策略版本 |
| 改写 timeout 且不可回退 | `timeout` | `knowledge.rewrite_timeout` | downstream | not_applicable |
| 改写 provider/invalid output 且不可回退 | `downstream_failure` | `knowledge.rewrite_failure` | downstream | not_applicable |
| 无匹配启用域 | `no_result` | 无 | 无 | not_applicable |
| 整域拒绝 | `forbidden` | `knowledge.domain_forbidden` | downstream | not_applicable |
| 读取判定不可验证 | `downstream_failure` | `knowledge.read_decision_unverifiable` | downstream | not_applicable |
| retrieval/Rerank timeout | `timeout` | `knowledge.retrieval_timeout` | downstream | not_applicable |
| retrieval/Rerank 非超时失败 | `downstream_failure` | `knowledge.retrieval_failure` | downstream | not_applicable |
| stage result 结构非法 | `internal_failure` | `knowledge.invalid_stage_result` | capability | not_applicable |

`no_result` 可携带的用户结果只允许 `reason=no_matching_domain/no_authorized_candidate/insufficient_evidence`、已选择逻辑域 ID 和 `coverageComplete`；不得包含问题、匹配词、被禁用/不可读域、候选身份、内部策略或技术失败。

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
| `AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES` | `3` | 3～20 | 只能提高；不得大于当前计划理论最大候选数 | 重启 |
| `AGENT_KNOWLEDGE_REWRITE_TIMEOUT_MS` | `8000` | 1000～8000 | 不得扩大 | 重启 |
| `AGENT_KNOWLEDGE_RETRIEVAL_TIMEOUT_MS` | `20000` | 3000～20000 | 不得扩大 | 重启 |
| `AGENT_KNOWLEDGE_EVIDENCE_TIMEOUT_MS` | `15000` | 3000～15000 | 不得扩大 | 重启 |

启用能力时必须恰有至少一个有效域；首批真实多域验收配置必须同时启用两域。v1 必需路径固定为 keyword/vector，配置不提供关闭其中一路的开关。任何启用域缺 retrieval/evidence stage 或域策略引用时整个 Runtime 不就绪，不静默只注册剩余域。

### 12.2 预算、取消与调用上限

| 阶段 | 最大调用数 | 子预算 | 失败后 |
|---|---:|---:|---|
| rewrite model task | 1 | 8s | 可本地回退或受控终止；不 retry |
| deterministic domain/plan | 本地纯函数 | 合计 50ms 目标 | 超时视为 internal failure |
| retrieval stage | 1 | 20s | 按 typed result 终止；不由 flow retry |
| evidence stage | 1 | 15s | 按其 typed `CapabilityResult` 返回；不由 flow retry |

每次调用的实际 timeout 是阶段上限与总 deadline 剩余值的较小者。剩余不足 100ms 时不发起下一调用。检索 stage 内部多路并发、Embedding/Rerank 子预算由 L2_01_01 负责，但不得延长本流程传入的 20s。

### 12.3 权限、安全与审计设计

- 缺少 user token/subject 的上下文在任何模型、检索或证据调用前失败。
- 原始 JWT 只传给 retrieval stage；不得传给 rewrite gateway、域选择器或本地 BGE。
- 原问题进入 rewrite gateway 前仍经过 L2_00_02 输入闸门。
- 逻辑域 ID 可进入安全日志；匹配词、问题和改写正文不得进入。
- 本文不能以角色、域配置或本地规则替代文档读取权威。
- `question_egress_denied=true` 只允许本地流程继续，不允许后续模型调用绕过拒绝。

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
4. 能力启用时校验至少一个域、两条必需路径、阈值和三项 stage 依赖。
5. 创建 semantic guard、rewriter、selector、plan builder 和 Capability。
6. 创建唯一 `KnowledgeCapabilityProvider` 并交给 L2_00_01 组合根冻结注册。
7. 任一步失败时 Runtime readiness=false；不带半有效 Knowledge 接收请求。

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

### 13.3 Python 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| 建议新增：`knowledge.settings.KnowledgeSettings.from_env` | `@classmethod def from_env(cls, env: Mapping[str, str]) -> Self` | 精确解析 12.1；未知域/重复/越界拒绝 | 冻结 settings；抛仅含 code 的 `KnowledgeConfigurationError` | 只读 env；composition root |
| 建议新增：`knowledge.catalog.build_tax_domain_catalog` | `def build_tax_domain_catalog() -> LogicalDomainCatalog` | 无运行输入；代码常量全量自校验 | 冻结两域目录；重复/非法 ID 为启动错误 | 无 I/O；provider/selector |
| 建议新增：`knowledge.capability.KnowledgeArgumentValidator.validate` | `def validate(self, arguments: JsonObject) -> KnowledgeQueryArguments` | 只接受精确空对象 | 冻结空参数；非空抛 `InvalidCapabilityArguments` | 无 I/O；core registry |
| 建议新增：`knowledge.question_semantics.QuestionSemanticGuard.extract` | `def extract(self, original_question: str) -> ProtectedConstraintSet` | NFC、控制符、数量上限 | 冻结约束集；非法问题为 typed error | 纯函数；rewriter |
| 建议新增：同上 `validate_candidate` | `def validate_candidate(self, *, candidate: str, constraints: ProtectedConstraintSet, max_chars: int) -> RewriteCandidateValidation` | 长度、控制符、缺失/新增保护项 | accepted 或有限 reason | 纯函数；rewriter |
| 建议新增：`knowledge.rewrite.KnowledgeQuestionRewriter.rewrite` | `async def rewrite(self, *, original_question: str, context: CapabilityExecutionContext, timeout_s: float) -> RewriteStageResult` | 原问题同源、gateway task、候选/回退 | success 或 input_denied/timeout/failure；不传播 Provider 异常 | 至多一次模型调用；Capability |
| 建议新增：`knowledge.domain_selection.DeterministicDomainSelector.select` | `def select(self, *, original_question: str, enabled_domains: tuple[LogicalKnowledgeDomain, ...]) -> DomainSelection` | 税务锚点、有限分类词、启用快照 | 冻结 0～2 域 | 纯函数；Capability |
| 建议新增：`knowledge.planning.KnowledgeRetrievalPlanBuilder.build` | `def build(self, *, rewrite: RewriteResult, domains: DomainSelection, settings: KnowledgeSettings) -> KnowledgeRetrievalPlan` | 非空域、query/limit、固定路径 | 冻结最多四项 plan；非法内部状态抛 typed error | 纯函数；Capability |
| 建议新增：`knowledge.capability.KnowledgeQueryCapability.handle` | `async def handle(self, input: KnowledgeQueryArguments, context: CapabilityExecutionContext) -> CapabilityResult` | 固定顺序、stage result/coverage/总 deadline | 合法公共结果；runtime shutdown cancel 传播 | 至多 1 rewrite、1 retrieval、1 evidence stage；core |
| 建议新增：`knowledge.provider.KnowledgeCapabilityProvider.registrations` | `def registrations(self) -> tuple[CapabilityRegistrationCandidate[KnowledgeQueryArguments], ...]` | 启动设置和依赖已冻结 | 精确一个 enabled/disabled candidate | 无运行 I/O；core composition root |

## 14. 测试与验证设计

### 14.1 测试定义

| 测试编号 | 状态 | 设计规则 | 层级 | 建议路径/用例 | Fixture、动作 | 关键断言 | 失败信号 |
|---|---|---|---|---|---|---|---|
| `TEST-KFLOW-001` | 建议新增 | `DR-KFLOW-001/002/014` | Unit/Contract | `agent-runtime/tests/unit/knowledge/test_capability_contract.py` | descriptor、空/非空 arguments、context 原问题 | 只注册一个 ID；空参数成功校验；handler 读取 context 原问题 | question/域进入 arguments 或非法公共组合 |
| `TEST-KFLOW-002` | 建议新增 | `DR-KFLOW-002/003` | Unit | `agent-runtime/tests/unit/knowledge/test_rewrite.py` | 数字、日期、文号、条款、否定、重复、超长、Provider failure fixtures | 语义漂移候选拒绝；最多 3 个；合法回退；模型调用≤1 | 丢保护项仍采纳、静默截断或 retry |
| `TEST-KFLOW-003` | 建议新增 | `DR-KFLOW-004/005` | Unit | `agent-runtime/tests/unit/knowledge/test_domain_selection.py` | 政策、法律、混合、通用税务、非税、禁用域 | 单域/双域/零域结果及顺序精确；未知域无法出现 | 模型/配置创建域或索引名进入结果 |
| `TEST-KFLOW-004` | 建议新增 | `DR-KFLOW-006` | Unit | `agent-runtime/tests/unit/knowledge/test_planning.py` | 1/2 域、候选上限边界 | 每域两路、顺序稳定、最多 4 项、无物理字段 | 缺路径、重复项、DSL/URL/索引字段 |
| `TEST-KFLOW-005` | 建议新增 | `DR-KFLOW-007/008/010/012/014` | Integration with fakes | `agent-runtime/tests/integration/knowledge/test_flow_with_fake_stages.py` | generic opaque batch、完整/部分/no-result stage | opaque batch 只透传；单动作；部分阈值/coverage 正确；无持久状态 | flow 读取 batch、第二动作、部分失败伪完整 |
| `TEST-KFLOW-006` | 建议新增 | `DR-KFLOW-007/008/013/014` | Parameterized Unit | `agent-runtime/tests/unit/knowledge/test_failure_priority.py` | forbidden/unverifiable/timeout/failure/no-result 的笛卡尔代表集 | 固定优先级、typed code/source、失败无载荷 | forbidden 被其他域成功覆盖或失败变 no_result |
| `TEST-KFLOW-007` | 建议新增 | `DR-KFLOW-004/009` | Unit | `agent-runtime/tests/unit/knowledge/test_settings_and_catalog.py` | 空/重复/未知域、边界±1、启用但缺 stage | 非法配置不就绪；合法配置冻结 | 半有效启动或配置扩权 |
| `TEST-KFLOW-008` | 建议新增 | `DR-KFLOW-001/009/012` | Contract | `agent-runtime/tests/contract/knowledge/test_provider_registration.py` | disabled、1 域、2 域 provider；core registry fake | 精确一个 candidate；disabled 不建客户端；enabled 可冻结 | 动态扫描、多个动作或缺依赖仍就绪 |
| `TEST-KFLOW-009` | 建议新增 | `DR-KFLOW-002/010/011` | Unit/Log | `agent-runtime/tests/unit/knowledge/test_deadline_cancellation_logging.py` | stage future 与取消/deadline 竞态；caplog 注入敏感文本 | 取消/超时后不调下一 stage；迟到丢弃；日志无问题/JWT/正文 | 后台继续、结果接纳或敏感泄露 |
| `TEST-KFLOW-010` | 建议新增 | `DR-KFLOW-012/013` | Architecture | `agent-runtime/tests/architecture/test_knowledge_boundaries.py` | AST/import/signature 检查 | core 无 knowledge import；Knowledge 无 DeepSeek/ES/BGE DTO；Capability 不访问 batch 字段 | 依赖反转、Provider 类型泄漏或通用工作流引擎 |

### 14.2 关键场景

| 场景 | rewrite 调用 | retrieval 调用 | evidence 调用 | 结果 |
|---|---:|---:|---:|---|
| arguments 非空 | 0 | 0 | 0 | `invalid_argument` |
| 改写成功、政策单域 | 1 | 1（plan 2 项） | 1 | 由 evidence stage 决定 |
| 通用税务问题、双域 | 1 | 1（plan 4 项） | 1 | 由 evidence stage 决定 |
| 非税问题、零域 | 1（输入闸门拒绝时 transport 为 0） | 0 | 0 | 按 L1 固定顺序在改写后选择零域并返回 `no_result` |
| 改写 Provider 失败且可回退 | 1 | 1 | 视检索结果 | mode=`original_fallback` |
| 改写输入拒绝且不可回退 | 0 | 0 | 0 | `model_egress_denied` |
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
| `VAL-KFLOW-005` | 本文、L2_00_01 v0.4、后续两份 L2 草案/评审证据 | 人工核对原问题同源、stage 类型、责任防重叠和门禁 | 证明跨 L2 语义未漂移，不替代真实集成 | 无未关闭 S0/S1 后方可申请切片实施 | 未执行：后续 L2 尚未创建，本文未独立评审 |

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
| `RISK-KFLOW-001` | 直接依赖 | L2_00_01 v0.4 `original_question` 补正尚未针对性复评 | 进入代码实施 | handler 输入可能再次漂移 | 先关闭 `REV-L2-010` | 阻塞本切片实施 |
| `RISK-KFLOW-002` | 域映射 | 真实税务内容是否能稳定映射为两域尚未证明 | P4 真实检索 | 逻辑域与物理数据不一致 | L2_01_01 核实元数据/只读映射；否则仅用受控测试域证明多域机制 | 不阻塞本文；阻塞真实两域声明 |
| `RISK-KFLOW-003` | 规则精度 | 代码词表可能对口语或交叉法规误选域 | P5 真实问题集 | 召回不足或多查 | 以阶段指标评估；需要时替换 `DomainSelector`，不修改 core | 不阻塞首版设计；阻塞效果达标结论 |
| `RISK-KFLOW-004` | 改写语义 | 有限保护项不能证明完整语义等价 | 复杂法律问句 | 检索偏离 | 始终保留原问题、无合法候选回退/失败、P5 对照评估 | 阻塞效果结论，不阻塞 fake 实现 |
| `RISK-KFLOW-005` | 下游契约 | Retrieval/Evidence stage 的具体 batch 尚由后续 L2 定义 | 端到端实现 | 类型或 failure 漂移 | 本文只透传泛型 batch；跨 L2 评审后联调 | 不阻塞本文流程切片；阻塞端到端 |
| `RISK-KFLOW-006` | 预算 | 8/20/15 秒尚无真实链路耗时证据 | P4 联调 | 误超时或余量浪费 | 保持硬上限，采集指标后在上位允许范围内收紧 | 不阻塞设计；阻塞性能结论 |
| `RISK-KFLOW-007` | 信息泄露 | no_result/coverage 暴露禁用或不可读域存在性 | 权限拒绝或配置变化 | 推断知识存在 | 只输出选中域和安全枚举；整域拒绝不返回其他域结果 | 阻塞实施测试 |

### 16.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威来源 | 责任方 | 最晚阶段 | 验证者与方法 | 状态 | 未关闭时允许/禁止动作 | 模拟或替代路径 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `KQ-GATE-001` | design_decomposition | L1_01→本文 | 编写本文 | L1_01 v0.2 五轮评审通过 | L1_01 14.2 | 项目维护者/独立评审方 | 本文前 | 核对评审记录 | Closed | 允许本文；不授权代码 | 不适用 |
| `KQ-GATE-002` | slice_implementation | 本文唯一负责的 Knowledge flow/config 切片 | 创建目标 Capability、配置、目录、改写/选择/计划代码与测试 | 本文独立评审通过；L2_00_01 v0.4 复评关闭；契约/测试/回滚明确；用户明确实施授权 | 本文评审、`REV-L2-010`、追踪矩阵 | 项目维护者 | P3 flow 实施前 | 独立设计评审和验证清单 | Open | 允许文档/fake 契约推演；禁止目标代码实施和完成声明 | 内存 fake stage 设计 |
| `CR-GATE-003` | integration | 原问题进入 DeepSeek 改写 | 外发可能敏感的用户问题 | L2_00_02 输入分类、最小化、零调用负向测试通过 | 模型 L2/Provider 契约 | 项目维护者/模型方 | 首次真实改写联调前 | model spy/负向测试 | Open | 只允许本地 rewrite fake 或非敏感授权 PoC；禁止敏感外发 | 原问题本地回退 |
| `SA-GATE-003` | integration | 真实 retrieval stage | 接入真实 ES/BGE | L2_01_01 契约、读取授权、模型兼容和负向测试通过 | L2_01_01/提供方 | 项目维护者/提供方 | P4 | 契约/集成测试 | Open | 本文可用 fake；禁止真实检索 | 内存统一候选 batch |
| `SA-GATE-006` | integration | 真实 evidence stage 模型输入 | 外发真实知识证据 | L2_01_02 三层策略、文档元数据和零调用测试通过 | L2_01_02/策略权威 | 项目维护者/模型方 | P4 | 出域矩阵/model spy | Open | 本文只透传 fake batch；禁止真实证据外发 | 合成安全证据 |

### 16.3 需要后续授权的动作

- 对本文执行独立正式评审并变更状态。
- 关闭 `REV-L2-010` 与本切片 `KQ-GATE-002`。
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

## 18. 实施前检查

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
- [ ] 独立正式评审通过并关闭本切片 `KQ-GATE-002`。

## 19. 当前结论

- 本文版本：v0.1。
- 文档状态：Draft。
- 评审状态：未执行独立正式评审。
- 实施状态：未实施。
- 生效状态：未生效。
- 是否可作为实现依据：否；`REV-L2-010` 和本切片 `KQ-GATE-002` 均为 Open。
- 确定性文档校验：已通过，0 errors、0 warnings；不替代独立正式评审。
- 当前只允许文档、自检和 fake 契约推演；不允许创建目标代码、启用真实检索或把真实问题/证据发送外部模型。
