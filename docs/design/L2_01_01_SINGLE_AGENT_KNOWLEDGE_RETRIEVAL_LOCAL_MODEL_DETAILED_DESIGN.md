# [L2_01_01] 单体 Agent Knowledge 检索与本地模型接入详细设计 L2

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Knowledge 检索与本地模型接入详细设计 |
| 文档标识 | `SA-L2-KNOWLEDGE-RETRIEVAL-001` |
| 文档编号 | `L2_01_01` |
| 文档路径 | `docs/design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 当前版本 | v0.2 |
| 日期 | 2026-08-01 |
| 适用范围 | Python `agent-runtime` 内 Knowledge Retrieval Stage/Adapter、ES 类型化只读消费、BGE-M3 Embedding、BAAI/bge-reranker-v2-m3 Rerank、多路召回融合及排序候选契约；必要的 `es-query-api/es-query-service` 最小公开接口改造设计 |
| 上位文档 | [`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v0.3 Approved；`KQ-GATE-001` Closed |
| 直接输入 | [`L2_01_00`](L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) v0.3 Approved；[`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4 Approved |
| 后续消费方 | [`L2_01_02`](L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) v0.2 Approved；`RankedKnowledgeBatch` 消费兼容检查通过 |
| 外部契约 | `es-query-api`/`es-query-service`；Elasticsearch `9200`；BGE-M3 `8908`；BAAI/bge-reranker-v2-m3 `8909`；`auth-service/common-security` 用户 JWT/Authority |
| 实现基线 | 目标 `agent-runtime` 不存在；`es-query-service` 只有原始 DSL/向量查询并返回原始 JSON，未提供 Knowledge 类型化候选、读取授权和稳定失败契约 |
| 当前环境证据 | `.tmp/chinatax-v2/build_manifest.json` 记录税务索引历史快照及 1024 维 BGE-M3；2026-07-31 只读点测确认 ES `9200`、Embedding `8908`、Rerank `8909` 在线，Embedding 返回 1024 维，Rerank 返回已确认模型的 `model/results[index,text,score]`；目标 typed ES 入口、授权、Profile/快照和自动化负向契约仍未实现或验证 |
| 是否可作为实现依据 | 否 |
| 评审状态 | 五轮独立评审—修复—复核已通过，`REV-KRET-001`～`REV-KRET-020` 全部关闭；L2_01_02 下游消费兼容检查无新增 S0/S1/S2 |
| 实施依据说明 | 本文设计已 Approved；仍须由项目维护者另行关闭本切片 `KQ-GATE-002` 后才能实施代码 |
| 当前允许范围 | 文档评审、契约样例推演、只读基线核实和不访问真实服务的 fake 验证设计 |
| 当前禁止动作 | 修改 Agent/ES/安全代码、配置、测试或公开契约；启用真实 ES/BGE；返回未授权候选正文；关闭 `KQ-GATE-002`/`SA-GATE-003` |
| 修改权限 | 本轮已授权第四批 L2 评审修复、必要关联文档原子同步及 Git commit/push；代码、配置、Schema、运行环境和公开契约实现仍只读 |

> 本文将“Agent 检索编排”与“ES 物理查询”分开：Python Adapter 负责逻辑域到稳定检索 Profile 的代码绑定映射、多路执行、融合、Rerank 和统一候选；`es-query-service` 独占 Profile 到物理资源的解析、读取授权和类型化只读召回。Profile 不是索引/别名且不能由模型或调用请求任意指定。本文不实施证据出域或 DeepSeek 摘要。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-31 | 全文 | 第三批 L2 依序编写 | 新建 Knowledge Retrieval/ES/BGE 详细设计，固定责任、类型契约、融合/Rerank、权限前置、失败语义、实现落点与门禁 |
| 2 | 2026-07-31 | 1/4/7/9～15 章 | 第 1 轮内部自检 | 修复详细设计结构关键词、追踪 ID 映射、依赖禁令、失败/安全/事务/数据生命周期覆盖、建议新增路径标识和实施依据字段 |
| 3 | 2026-07-31 | 4/8/9/11/15 章 | 第 2 轮内部自检 | 收紧候选字段空值、策略引用、Rerank 全覆盖与最终截断语义，并消除 Embedding 与候选 BGE Rerank 授权时序歧义 |
| 4 | 2026-07-31 | 8/10/12～16 章 | 第 3 轮内部自检 | 对齐 401 的 stage 有限错误映射，固定正文哈希语义和端点级重复键检测，并完成实现前可验证性收口 |
| 5 | 2026-07-31 | 6/12/13 章 | 第三批原子一致性同步 | 展开已存在及建议新增的 Java 类/测试完整路径；不改变三轮内审结论或设计语义 |
| 6 | 2026-07-31 | 1、3～14、17 章及上位文档 | 独立评审第 1 轮修复 | 引入两级 Profile 映射并原子补正 REQ/L0/L1；补齐 ES 服务安全/校验依赖、端点级严格 JSON、读取决定、HTTP 失败分类、物理查询/快照和跨路径一致性契约，关闭 `REV-KRET-001`～`REV-KRET-006` |
| 7 | 2026-07-31 | 8、10、12～17 章 | 独立评审第 2 轮修复 | 增加仅保护新端点且保留旧端点行为的双 SecurityFilterChain，闭合媒体类型与全部 HTTP 状态映射，并补齐 Java DTO/读取决定字段类型，关闭 `REV-KRET-007`～`REV-KRET-009` |
| 8 | 2026-07-31 | 8、11～14、16～17 章 | 独立评审第 3 轮修复 | 固定安全链对统一 role converter 的显式消费、两链 CSRF 兼容语义；将 snapshot 改为启动重算校验并诚实声明无运行期轮询，关闭 `REV-KRET-010`～`REV-KRET-012` |
| 9 | 2026-07-31 | 8、10～14、16～17 章 | 独立评审第 4 轮修复 | 固定 enabled 启动失败边界、把 body-limit filter 放入认证授权链之后，并补齐三类 Provider 的原始字节/压缩/Content-Type 上限，关闭 `REV-KRET-013`～`REV-KRET-016` |
| 10 | 2026-07-31 | 1～2、6、9、12～18 章 | 独立评审第 5 轮修复与终审 | 补齐 `PathRank/PathCandidateSet/RerankScore` 强类型、异常落点及仓库根目录可执行的测试路径/命令；依据实时只读点测固化 Rerank 请求和 `model/text` 回显关联，并将响应上限对齐合法最大候选；全量复核无新增未关闭 S0/S1/S2，文档转为 v0.2 Approved，关闭 `REV-KRET-017`～`020`，实施及真实集成门禁保持 Open |
| 11 | 2026-08-01 | 1～2、6、8、16～18 章 | 第四批下游契约状态原子同步 | 同步 `L2_01_00` v0.3 与 `L2_01_02` v0.2 Approved；复核 `RankedKnowledgeBatch` 候选身份、正文 hash、策略引用、读取策略和快照字段可被 Evidence Stage 无扩展消费，未修改检索契约或开放门禁 |

## 3. 背景、目标与范围

### 3.1 背景与问题

`L2_01_00` 已生成最多四个 `logical_domain_id + keyword/vector` 计划项，但故意不定义物理索引、BGE 协议、候选或融合算法。当前 `es-query-service` 允许调用方传入物理索引和原始 DSL/向量字段，返回 Elasticsearch 原始 JSON，且 Knowledge 查询未经用户读取授权。若 Python 直接依赖该接口，会泄露物理资源、让模型间接控制 DSL，并使未授权正文先进入 Agent/BGE。

### 3.2 目标与验收行为

| 需求编号 | 目标或可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-KRET-001` | 只消费代码绑定的两个逻辑域、稳定检索 Profile 和两条路径 | 任意请求不含物理索引、DSL、字段名或 URL；未知/不匹配的域、Profile、路径在 ES 查询前拒绝 | REQ_00 v1.3 CFG-01/02；L1_01 v0.3 6.3/7.3；L2_01_00 8.3/9.6 |
| `REQ-KRET-002` | 用户读取授权早于候选正文返回和 Rerank | 缺失/未知/混合角色、策略不可验证或权威失败时，正文、BGE Rerank 和 Agent batch 均为零 | L1_01 7.4/9.2/10.1 |
| `REQ-KRET-003` | keyword/vector 多路召回输出统一候选 | 每路状态类型化；候选字段、身份、顺序和大小稳定；原始 ES JSON 不进入 Capability | REQ_00 FR-02；L1_01 8.2/8.5 |
| `REQ-KRET-004` | 向量查询使用本地 BGE-M3 | `POST /embed` 只接收一条受控查询；返回值数量、维度 1024、finite 数值不符即该路失败 | 用户确认模型/8908；L1_01 8.3 |
| `REQ-KRET-005` | 使用确定 RRF 去重融合和本地 Rerank | 同一输入得到同一顺序；Rerank 结果索引完整、唯一、有界；Rerank 失败不生成肯定结果 | REQ_00 FR-02；L1_01 8.4 |
| `REQ-KRET-006` | 单路故障可追踪且不伪装完整成功 | 成功/no-result/失败路径精确分区；是否允许部分继续由 L2_01_00 阈值判定 | L1_01 `KQ-AD-009`；L2_01_00 `DR-KFLOW-007/008` |
| `REQ-KRET-007` | 检索有统一截止、取消和资源上限 | stage 不延长 20s 外层预算；无自动重试、持久化或迟到结果接纳 | L1_01 9.3；L2_01_00 12.2 |
| `REQ-KRET-008` | 为 `L2_01_02` 提供稳定证据候选身份 | 排序 batch 只含已授权片段、源身份、内容哈希、策略引用和快照版本，不决定出域 | L1_01 8.6/13.3 |

### 3.3 范围内

- Python Retrieval Stage、ES/Embedding/Rerank Port 与 Adapter、RRF 融合、去重和统一候选 batch。
- `es-query-api/service` 面向 Knowledge 的最小类型化只读契约设计，以及读取决定早于正文的执行点。
- `tax.policy`/`tax.law` 到受控读别名的服务端映射。
- BGE-M3 `8908` 和 BAAI/bge-reranker-v2-m3 `8909` 消费契约、运行上限与失败语义。

### 3.4 范围外

- 文档录入、切片、建索引、alias 切换、索引管理和全面重构 `es-query-service`。
- 问题改写、逻辑域选择和跨阶段终态；已归 `L2_01_00`。
- 证据出域、Prompt、DeepSeek 调用、摘要与效果指标；归 `L2_01_02/L2_00_02`。
- Employee/Transaction 结构化查询。

### 3.5 非目标

- 不引入通用搜索 DSL、动态索引选择、检索算子插件或策略脚本。
- 不在 Python 重新判定文档读权，不以候选删字段替代读取授权。
- 不在首期引入缓存、自动重试、熔断或分布式任务。

### 3.6 实施剖面

| 剖面 | 适用性 | 说明 |
|---|---|---|
| Python | 适用 | Retrieval Stage、Port/Adapter、候选、融合、Rerank、配置和测试 |
| Java/API | 适用 | Knowledge 类型化只读 DTO、Controller/Service、受控域映射和授权执行点 |
| Elasticsearch | 适用 | 只读 alias/字段契约核实；不执行建索引和迁移 |
| 安全 | 适用 | 用户 JWT、Authority、域读策略、候选正文前授权 |
| 持久化/事务 | 不适用 | 全链只读且请求级，不新增状态 |

## 4. 上位约束

| 约束编号 | 上位位置 | 约束 | 本设计落实 | 偏离 |
|---|---|---|---|---|
| `CON-KRET-001` | L1_01 6/8.1 | Knowledge Capability 通过 Port 依赖检索，提供方细节不向上泄漏 | `DR-KRET-001`、`DR-KRET-002` | 无 |
| `CON-KRET-002` | L1_01 7.4/10.1 | 当前用户读取授权早于候选正文和候选 BGE Rerank；查询 Embedding 不接收候选正文 | `DR-KRET-003`、`DR-KRET-004` | 无 |
| `CON-KRET-003` | L1_01 8.2～8.5 | 多路召回、统一候选、去重融合和 Rerank | `DR-KRET-005`、`DR-KRET-006`、`DR-KRET-007` | 无 |
| `CON-KRET-004` | L2_01_00 9.6/12.2 | 消费最多四个逻辑计划项，不延长 20s 检索预算 | `DR-KRET-008`、`DR-KRET-009` | 无 |
| `CON-KRET-005` | L2_01_00 10.1 | 返回有限 stage result/coverage，由流程判定部分成功 | `DR-KRET-010` | 无 |
| `CON-KRET-006` | L1_01 13.3 | 不拥有读取规则、证据出域或 DeepSeek 契约 | `DR-KRET-002`、`DR-KRET-004`、`DR-KRET-011` | 无 |
| `CON-KRET-007` | REQ_00 SEC-03/04 | 缺失或不可验证权限失败关闭 | `DR-KRET-003`、`DR-KRET-004`、`DR-KRET-012` | 无 |

### 4.1 端到端追踪矩阵

| REQ/CON | 切片 | 设计规则 | 责任主体 | 契约/数据影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-KRET-001`,`CON-KRET-001` | ES 边界 | `DR-KRET-001`、`DR-KRET-002` | Python Adapter/ES API | Profile 请求/typed response | `IMPL-KRET-001/007/008/011/012/013` | `TEST-KRET-001/006/011` | `VAL-KRET-001/003` |
| `REQ-KRET-002`,`CON-KRET-002`,`CON-KRET-007` | 读取授权 | `DR-KRET-003`、`DR-KRET-004`、`DR-KRET-012` | ES 读取权威/业务安全边界 | JWT→Authority→typed decision | `IMPL-KRET-009/010/012/013` | `TEST-KRET-002/007/011` | `VAL-KRET-003/005` |
| `REQ-KRET-003`,`CON-KRET-003` | 召回 | `DR-KRET-005`、`DR-KRET-006` | retrieval stage/ES service | 统一候选 | `IMPL-KRET-002/003/008/010/011` | `TEST-KRET-003/006/011` | `VAL-KRET-001/003` |
| `REQ-KRET-004` | Embedding | `DR-KRET-005`、`DR-KRET-009` | BGE embedding adapter | 1024 维向量 | `IMPL-KRET-004` | `TEST-KRET-004` | `VAL-KRET-002/004` |
| `REQ-KRET-005` | 融合/Rerank | `DR-KRET-006`、`DR-KRET-007` | fusion/rerank adapter | ranked batch | `IMPL-KRET-003/005` | `TEST-KRET-003/005` | `VAL-KRET-001/004` |
| `REQ-KRET-006`,`CON-KRET-005` | 失败/coverage | `DR-KRET-010`、`DR-KRET-012` | retrieval stage | typed result/coverage | `IMPL-KRET-001/002` | `TEST-KRET-008` | `VAL-KRET-001` |
| `REQ-KRET-007`,`CON-KRET-004` | 运行约束 | `DR-KRET-008`、`DR-KRET-009` | stage/各 client | deadline/cancel/no retry | `IMPL-KRET-002/004/005/006` | `TEST-KRET-009` | `VAL-KRET-001/004` |
| `REQ-KRET-008`,`CON-KRET-006` | 下游候选 | `DR-KRET-011` | retrieval stage | opaque ranked batch | `IMPL-KRET-001/003` | `TEST-KRET-010` | `VAL-KRET-001` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文责任 | 对方责任 | 交互契约 | 所有权 | 权限 |
|---|---|---|---|---|---|---|
| `L2_01_00` | parent/direct input | 消费 plan/context，返回 stage result | 问题、域、计划和部分成功判定 | `KnowledgeRetrievalStage.execute` | 流程状态 | 只读 |
| `es-query-service` | external provider | 定义最小 Knowledge 消费契约 | Profile→物理资源映射、授权、ES 只读查询、typed candidate | `POST /es/knowledge/search` | 物理索引/读取决定 | 设计；代码只读 |
| Elasticsearch | infrastructure | 不直接访问 | 候选存储/检索 | 只由 ES service 消费 | index/alias | 只读证据 |
| BGE-M3 | local provider | 定义查询 embedding 消费 | 生成向量 | `POST /embed` | 模型运行 | 只读证据 |
| BGE Rerank | local provider | 定义候选重排消费 | 返回索引/分数 | `POST /rerank` | 模型运行 | 只读证据 |
| `auth-service/common-security` | security authority | 仅消费角色/Authority 观察契约 | JWT 签发、验签与映射 | `role`→`ROLE_ADMIN/VIEWER` | 身份/角色 | 只读 |
| `L2_01_02` v0.2 Approved | downstream | 提供排序候选与策略引用 | 证据裁剪、出域、摘要 | `RankedKnowledgeBatch` | 证据/出域 | 消费兼容检查通过；实现/出域门禁 Open |

## 6. 当前实现基线与最小改造

### 6.1 已核实事实

| 状态 | 路径/证据 | 事实 | 设计影响 |
|---|---|---|---|
| 已存在 | `es-query-service/src/main/java/com/dylan/esquery/controller/EsQueryController.java` | `/es/indexes/{index}/search` 接受原始 DSL；`vector-search` 接受字段/向量 | Agent 不得复用为目标契约 |
| 已存在 | `es-query-service/src/main/java/com/dylan/esquery/service/EsDocumentService.java` | 返回 ES 原始 JSON，开放物理索引和字段 | 需新增狭契约，不全面重构 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/service/EmployeeEmbeddingService.java` | BGE 本地契约为 `/embed` + `texts`，校验向量维度 | 作为迁移证据，不作 Agent 基线 |
| 已存在 | `.tmp/chinatax-v2/build_manifest.json` | 历史 alias `agent-doc-tax-policy-v2-read`、`domain=tax_policy`、BGE-M3 1024 维、13003 chunks | 只是快照，真实集成须重新核实 |
| 已存在 | `.tmp/chinatax-v2/train.parquet` | 源字段含 `title/channel/content/document_number/effect_level/...` | 可推导域分类候选，不证明 ES 当前 mapping |
| 缺失 | 当前 Java/security | Knowledge typed DTO、候选正文前读取决定；`es-query-service/pom.xml` 也未依赖 `common-security`/validation，统一 role converter 尚不存在 | Java 切片需新增显式依赖与端点装配；真实集成仍失败关闭 |
| 已存在（运行证据） | `9200/8908/8909` 只读 HTTP 点测 | ES 9.4.1 返回 200 且税务索引在线；Embedding OpenAPI 描述及 embed 端点可用并返回一组 1024 维向量；Rerank OpenAPI 描述及 rerank 端点可用，返回 `model` 及 `results[index,text,score]` | 证明基础服务和最小 wire 当前可用；不证明 typed ES 入口、授权、Profile/快照、上限/超时负向契约或真实链路已闭环，`SA-GATE-003` 保持 Open |

### 6.2 根因

Knowledge 原有索引资产是实验性数据资产，`es-query-service` 则是通用 ES 工具边界；两者没有形成“用户授权后的 Knowledge 类型化候选”服务契约。本文不新增 `knowledge-service`，而是在 `es-query-service` 中收紧其已有检索能力的 Knowledge 专用只读入口。

### 6.3 最小变更方案

| 变更项 | 必要性 | 复用 | 不采用方案 |
|---|---|---|---|
| Python `knowledge/retrieval` 子包 | 承载跨提供方组合且不污染 Capability | L2_01_00 stage Protocol | 不把 ES/BGE 细节写入建议新增的 `capability.py` |
| ES Knowledge typed endpoint | 只接受稳定 Profile 并隐藏索引/DSL，强制授权前置 | 现有 RestClient/ObjectMapper；现有 `BoundedRequestBodyFilter` | 不让 Python 消费原始 DSL endpoint |
| Embedding/Rerank 独立 Port | 本地模型契约和测试缝隙 | 已确认的 BGE-M3 实例 | 不引入通用模型框架 |
| 确定 RRF + 一次 Rerank | 满足多路召回与稳定排序 | 计划路径顺序 | 不引入可配置排序脚本/权重平台 |

## 7. 责任、分层与依赖

### 7.1 责任分解

| 组件 | 状态 | 唯一职责 | 明确不负责 | 输入/输出 |
|---|---|---|---|---|
| `DefaultKnowledgeRetrievalStage` | 建议新增 | 按 plan 和预算组合召回、融合、Rerank | 问题改写、读规则、证据出域 | plan/context→stage result |
| `KnowledgeSearchPort` | 建议新增 | 类型化只读候选边界 | URL/DSL/物理域暴露 | search request→path result |
| `EsKnowledgeSearchAdapter` | 建议新增 | 代码绑定域→Profile、JWT 原样透传和 ES typed DTO 转换 | 物理映射、本地授权、融合/Rerank | typed request→candidate tuple |
| `BgeM3EmbeddingAdapter` | 建议新增 | 一次查询向量生成/校验 | 文档向量建索引 | text→1024-vector |
| `ReciprocalRankFusion` | 建议新增 | 身份去重和确定 RRF | 语义评分 | path candidates→fused |
| `BgeRerankAdapter` | 建议新增 | 一次有界候选重排 | 决定证据出域 | query+fused→ranked |
| `KnowledgeSearchController/Service` | 建议新增 | 严格解码、验证域/Profile 对、授权后生成类型候选 | Agent 融合、Rerank、证据 | HTTP bytes/DTO→typed response |
| `KnowledgeReadAccessGuard` | 建议新增 | 在查询前获取可追踪读取决定 | 发放角色、出域判定 | authentication+domain→decision |

### 7.2 依赖方向

```text
KnowledgeQueryCapability
  -> KnowledgeRetrievalStage (Port)
     -> KnowledgeSearchPort -> EsKnowledgeSearchAdapter -> es-query-service -> Elasticsearch
     -> EmbeddingPort -> BgeM3EmbeddingAdapter -> 8908
     -> CandidateFusion (pure)
     -> RerankPort -> BgeRerankAdapter -> 8909
  -> opaque RankedKnowledgeBatch -> KnowledgeEvidenceStage
```

禁止依赖与绕过路径：Capability 不得直接导入 HTTP/ES/BGE DTO；Python 不得直连 `9200`；`es-query-service` 不得调用 Rerank/DeepSeek；Rerank 不得取得 JWT；证据阶段不得回读 ES 原始响应。

### 7.3 内聚与最小耦合

Python Adapter 只冻结 `logical_domain_id → retrieval_profile_id`，该映射随 Agent 允许域变化；ES 授权、`profile_id → alias/field/filter` 物理映射和查询随索引变化，放在 Java 提供方。两者仅共享稳定 Profile 和类型化候选 HTTP 契约，既避免重复物理配置，也避免将 `es-query-service` 扩展为 Agent 编排器。

## 8. 核心契约

### 8.1 Python 内部类型

| 类型 | 必填字段 | 不变量 |
|---|---|---|
| `KnowledgePathRequest` | `logical_domain_id,retrieval_profile_id,path,query_text,query_vector,candidate_limit` | Profile 由 Adapter 代码映射且与 domain 精确配对；path 仅 keyword/vector；keyword 无 vector，vector 恰有 1024 个 finite float |
| `AuthorizedKnowledgeCandidate` | `document_id,chunk_id,domain_id,title,content,source_url,document_number,written_date,material_type,source_rank,content_sha256,read_policy_version,policy_ref,index_snapshot_id` | 可空来源字段也必须显式存在；字符串 NFC/长度有界；不含 embedding、ES score、ACL 正文或 JWT |
| `PathRetrievalResult` | tagged `candidates/no_result/forbidden/timeout/failure`；成功分支含 `logical_domain_id,retrieval_profile_id,path,profile_version,index_snapshot_id,read_policy_version,truncated,candidates` | forbidden 无原因自由文本；timeout 仅 `retrieval_timeout`；failure 仅 `read_decision_unverifiable/read_authority_failure/retrieval_failure/invalid_provider_result`；失败不携带候选 |
| `PathRank` | `logical_domain_id,path,rank` | domain/path 来自 plan；rank≥1；用于不可变 tuple，不用 dict |
| `PathCandidateSet` | `logical_domain_id,retrieval_profile_id,path,profile_version,index_snapshot_id,read_policy_version,truncated,candidates` | 仅由合法 `PathRetrievalResult.candidates` 构造；候选 rank 连续 |
| `FusedCandidate` | `candidate,domain_ids,path_ranks: tuple[PathRank,...],rrf_score` | domain/path 按 plan 有序去重；RRF 只依赖 rank |
| `RerankScore` | `candidate_index,score` | index 在 0..N-1 且唯一；score finite；响应恰覆盖 N |
| `RankedKnowledgeCandidate` | `candidate,domain_ids,rerank_score,rank` | rank 从 1 连续；score finite |
| `RankedKnowledgeBatch` | `candidates,profile_version,index_snapshot_ids` | 非空、最多 20；快照 ID 有序去重 |

所有 Python 数据类使用 `@dataclass(frozen=True, slots=True, kw_only=True)`，tuple 深冻结；不使用可变 dict 作为跨层候选契约。

### 8.2 Knowledge 类型化 HTTP 请求

`POST /es/knowledge/search`，`Authorization: Bearer <original-user-jwt>`，`Content-Type: application/json`：

```json
{
  "schemaVersion": 1,
  "logicalDomainId": "tax.policy",
  "retrievalProfileId": "tax-policy-v1",
  "path": "keyword",
  "queryText": "受控检索文本",
  "queryVector": null,
  "limit": 20
}
```

| 字段 | 约束 |
|---|---|
| `schemaVersion` | 必须精确为 1 |
| `logicalDomainId` | 仅 `tax.policy/tax.law` |
| `retrievalProfileId` | Adapter 代码绑定：`tax.policy→tax-policy-v1`、`tax.law→tax-law-v1`；不能来自模型、用户输入或通用配置自由值 |
| `path` | 仅 `keyword/vector` |
| `queryText` | keyword 必填，NFC 1～1024 code points；vector 必须为 null |
| `queryVector` | vector 必填且精确 1024 个 finite JSON number；keyword 必须 null |
| `limit` | 5～20，与 plan 一致 |

拒绝未知/重复 JSON key、额外字段、尾随 token、非 UTF-8 或超 128 KiB body；`@PostMapping(consumes=application/json)` 使非 `application/json` 返回 415。请求不接受 index、alias、field、DSL、filter、sort、host、model 或 ACL；域/Profile 不匹配返回 400，且授权守卫和 ES 调用均为 0。

Java API DTO 使用 record/不可变对象，字段类型固定如下；Bean Validation 只负责普通字段约束，path-dependent 互斥和 domain/Profile 配对由 Codec 后的确定性请求校验器完成：

| DTO | 字段与 Java 类型 | Null/集合语义 |
|---|---|---|
| `KnowledgeSearchRequest` | `int schemaVersion`、`String logicalDomainId`、`String retrievalProfileId`、`String path`、`String queryText`、`List<Double> queryVector`、`int limit` | keyword 时 queryText 非空/queryVector=null；vector 反之；List 防御复制 |
| `KnowledgeSearchResponse` | `int schemaVersion`、`String logicalDomainId`、`String retrievalProfileId`、`String path`、`String profileVersion`、`String indexSnapshotId`、`String readPolicyVersion`、`boolean truncated`、`List<KnowledgeSearchCandidate> candidates` | 顶层均非 null；candidates 非 null、防御复制、0～20 |
| `KnowledgeSearchCandidate` | `String documentId`、`String chunkId`、`String logicalDomainId`、`String title`、`String content`、`String sourceUrl`、`String documentNumber`、`LocalDate writtenDate`、`String materialType`、`int sourceRank`、`String contentSha256`、`String policyRef` | 仅 sourceUrl/documentNumber/writtenDate 可 null；其余按 8.3 边界 |

### 8.3 HTTP 响应

```json
{
  "schemaVersion": 1,
  "logicalDomainId": "tax.policy",
  "retrievalProfileId": "tax-policy-v1",
  "path": "keyword",
  "profileVersion": "tax-knowledge-search-v1",
  "indexSnapshotId": "opaque-snapshot-id",
  "readPolicyVersion": "tax-public-authenticated-v1",
  "truncated": false,
  "candidates": [
    {
      "documentId": "tax-...",
      "chunkId": "tax-...#d0001",
      "logicalDomainId": "tax.policy",
      "title": "...",
      "content": "...",
      "sourceUrl": "/zcfgk/...",
      "documentNumber": "...",
      "writtenDate": "2025-01-01",
      "materialType": "tax_policy",
      "sourceRank": 1,
      "contentSha256": "64-lower-hex",
      "policyRef": "opaque-document-policy-ref"
    }
  ]
}
```

- 200 表示查询已授权且契约可判定；空 candidates 表示 no-result。顶层 domain/Profile/path 必须精确回显请求，`profileVersion` 必须等于 Adapter 启动快照允许值。
- 400 表示 JSON/字段/域-Profile-path 请求非法，415 表示媒体类型非法；这两类对已通过本地校验的 Adapter 均映射 `invalid_provider_result`。401 仅表示 token 缺失、认证失败或 token 类型不是 user；403 仅表示已验证 user token 的 role/domain **明确拒绝**。
- 429 映射 `retrieval_failure`；503 保留给读取权威缺失、策略版本不可验证或读取权威不可用并映射 `read_authority_failure`；504 映射 `retrieval_timeout`；其余 5xx 和 404/405/406/其他未列状态映射 `retrieval_failure`。204 或 200 非法/空 body 映射 `invalid_provider_result`。Python 只按状态码映射，不解析错误 body。
- ES 响应要求 `Content-Type: application/json`、`Content-Encoding` 缺失或 `identity`；以流式聚合前原始字节计上限 2 MiB。每候选 content 最多 4096 code points、title 256、ID 256、URL 1024；最多 20 条。
- 顶层字段和每个候选字段均必须存在；Python 响应 Codec 拒绝未知/重复字段和尾随 token。Java 请求重复键检测、UTF-8 解码和未知字段拒绝只限定在新增 Knowledge Controller 的 byte[]→DTO Codec，不改变现有通用端点。`sourceUrl/documentNumber/writtenDate` 可为 JSON null，其余字段非 null；`writtenDate` 非空时必须符合 ISO 8601 日历日期（如 `2025-01-01`），`content` 不得为空。
- `contentSha256` 精确等于返回候选 `content` 经 NFC 后 UTF-8 字节的 SHA-256 小写十六进制；content 超限时提供方返回契约失败，不静默截断后重算哈希。
- `policyRef` 是 `L2_01_02` 消费的必填 opaque ID，不表示出域允许；缺失或空白属于 `invalid_provider_result`。当前索引未证明具备该字段，因此真实集成保持关闭。

### 8.4 两级 Profile 与物理域映射

Adapter 先以冻结代码定义把逻辑域映射为稳定 Profile；ES 服务端再以同名冻结 `KnowledgeSearchProfile` 将 Profile 解析为物理资源。请求必须同时携带 domain/Profile 供提供方校验，不能携带或覆盖物理值：

| 逻辑域 | Adapter Profile | ES 提供方受控读 alias | 分类意图 | 当前证据 |
|---|---|---|---|---|
| `tax.policy` | `tax-policy-v1` | `agent-doc-tax-policy-v2-read` | 税务通知、公告、政策、解读等非法律类别 | alias 仅由历史 manifest 证明；实际 mapping/filter 待 `SA-GATE-003` 核实 |
| `tax.law` | `tax-law-v1` | 同一受控 alias | `channel/effect_level` 归一化为法律、行政法规或司法解释 | 源 parquet 字段存在；ES 字段名/mapping 待核实 |

两域不使用两套索引；Profile 是同一税务资料库的两个受控过滤视图，不是物理别名。Adapter 不保存 alias/字段/filter；ES 服务不接受未知 Profile，也不允许同一 Profile 在启动快照中指向多个 domain。若不能证明分类完备、互斥/重叠规则和 alias 快照，该 Profile 不就绪，不回退为全索引搜索。

### 8.5 读取授权契约

v1 税务知识只允许经验证 user token 且 Authority 集精确非空、全部属于 `ROLE_ADMIN/ROLE_VIEWER`。含未知 Authority 或 role 缺失/空白/类型错误时是明确 403；token 缺失/无效或 `token_type!=user` 为 401；策略版本、Profile 或读取权威不可验证时为 503。三类路径的 ES 调用均为 0，且不得互相降级。

`tax-public-authenticated-v1` 是首批整库同质读取策略的建议版本，不是聊天确认即可生效的事实。`SA-GATE-003` 关闭前必须有索引快照证据证明所有文档均属该读取策略；若任一文档需异质 ACL，v1 整库绑定不得启用，必须先扩展权威契约。

允许分支生成不可变 Java record `KnowledgeReadDecision(String logicalDomainId, String retrievalProfileId, String profileVersion, String readPolicyVersion, String decisionId)`；`decisionId` 为本请求内随机 opaque ID，只用于 ES service 内部追踪，不返回 Agent。Service 必须校验 decision 的 domain/Profile 与请求完全一致后才构造 ES 请求；Guard 不返回 subject、JWT、Authority 集或正文。

### 8.6 ES 查询、快照与候选映射

`KnowledgeSearchProfile` 每项必须在启动时冻结：`profile-id`、唯一 `logical-domain-id`、`profile-version`、`read-policy-version`、`read-alias`、唯一预期 concrete index/UUID、`mapping-version`、预期 `index-snapshot-id`、分类字段及有限允许值、keyword 字段元组、vector 字段、候选源字段映射、`max-candidates=20`、`max-content-chars=4096`。未知键、重复 domain/Profile、写别名、alias 多目标、预期 index/UUID 不匹配、必填字段缺失或 mapping 类型不兼容使 Knowledge endpoint readiness=false；通用 ES 端点不因此改变契约。

- keyword：Service 内部生成 `bool.filter` 的 Profile 分类条件与 `multi_match` 查询，仅使用冻结 keyword 字段；请求 `size=limit+1`、`track_total_hits=false`，只取允许的 `_source` 字段。
- vector：Service 内部生成现有 RestClient 支持的 `knn`，字段固定为 Profile vector 字段，`k=limit+1`，`num_candidates=min(100,max(20,5*(limit+1)))`，并应用同一 Profile 分类 filter；不接受调用方 DSL/field/filter。
- 两路均先拒绝非 finite `_score`、缺失/未知 source 字段、重复 `(documentId,chunkId)`、domain/Profile 不一致和超限正文；再按 `_score desc,chunkId asc` 确定性排序，截取前 `limit` 并赋 `sourceRank=1..N`。ES `_score` 不返回 Agent。
- `truncated=true` 当且仅当验证后的第 `limit+1` 条存在；否则为 false。`contentSha256` 由 Service 对返回 content 的 NFC UTF-8 字节计算；`policyRef` 必须来自 Profile 指定的源字段，不能由 role/read policy 推导。
- `indexSnapshotId = sha256(profileId + "\n" + concreteIndexName + "\n" + indexUuid + "\n" + profileVersion + "\n" + mappingVersion)` 的 64 位小写十六进制。启用启动时 Service 从 ES 只读解析 alias/index UUID，按上述 UTF-8 字节精确重算并与配置预期值比较；不相等则 Knowledge endpoint 不就绪。首期不做运行期轮询，因此真实启用前必须以权限/流程证明该 alias 只指向不可变只读快照；任何 alias/index/mapping 变更必须先停用、更新 Profile 并重启，不能声称运行期自动发现漂移。

## 9. 详细功能与处理流程

### 9.1 设计规则

| 规则编号 | 规则 | 责任主体 | 触发 | 效果 |
|---|---|---|---|---|
| `DR-KRET-001` | Capability 只调用 `KnowledgeRetrievalStage`，不引用提供方 DTO | Capability/Port | stage 调用 | 依赖单向 |
| `DR-KRET-002` | Adapter 代码绑定 domain→Profile；ES API 不接收物理资源/DSL，服务端强类型配置独占 Profile→alias/field/filter 映射并校验 domain/Profile 配对 | Adapter/ES API/service | HTTP 请求 | 两级单一权威、无动态 ES |
| `DR-KRET-003` | 认证、Authority 和域读决定在构造 ES 请求前完成 | ES guard | 每路请求 | 未授权正文零暴露 |
| `DR-KRET-004` | Python 不解析 role/ACL，只透传 opaque user token 并信任 typed allow/deny | Python adapter | 出站 | 权威不重复 |
| `DR-KRET-005` | 所有 vector path 共享一次 BGE-M3 embedding，维度/数值非法时 vector paths 统一失败 | embedding adapter | 计划含 vector | 最多一次 embedding |
| `DR-KRET-006` | 路径候选以 `(document_id,chunk_id)` 去重，RRF `sum(1/(60+rank))` | fusion | 召回结束 | 确定 fused candidates |
| `DR-KRET-007` | fused 候选仅调用一次 Rerank；结果索引完整唯一，排序为 rerank score desc、RRF desc、candidate ID asc | rerank/stage | fused 非空 | 稳定 top 20 |
| `DR-KRET-008` | 四路召回并发但共享 stage 绝对截止；取消后 await 清理并丢弃迟到结果 | stage | execute | 不超预算 |
| `DR-KRET-009` | 无 retry/cache/fallback index；子预算为 embedding 3s、单路 ES 5s、rerank 5s 与剩余预算较小值 | clients/stage | 依赖调用 | 避免重试乘法 |
| `DR-KRET-010` | stage 返回路径精确分区的 coverage，不自行判定部分成功 | stage | 汇总 | L2_01_00 唯一判定 |
| `DR-KRET-011` | batch 含证据身份/哈希/策略引用，不含出域 allow/deny 结论 | candidate contract | stage success | 下游可复核 |
| `DR-KRET-012` | 未知/重复字段、非法候选、Profile/快照漂移、读决定不可验证、Rerank 非法结果均失败关闭并不携带原始响应 | 各边界 | 校验失败 | typed failure |

### 9.2 正常流程

1. 校验 plan 恰覆盖已选域的 keyword/vector，数量 2 或 4。
2. 冻结 stage deadline，如剩余≤100ms 直接 timeout，连网为 0。
3. plan 含 vector 时调用一次 BGE-M3，校验 1024 个 finite value。
4. Adapter 从冻结映射取得每个 domain 的 Profile，为每个 plan item 生成 typed ES 请求，以同一用户 JWT 并发调用；Profile 不可由 plan 或模型覆盖。
5. ES service 先严格解码并校验 domain/Profile/path，再校验 token/Authority/domain policy，然后解析 Profile 的受控物理映射并查询 ES，仅返回 typed candidate。
6. 对成功路径按服务端 rank 构造 RRF；不跨路径比较 ES score。
7. fused 为空时返回 no-result coverage；否则使用查询和最多 80 个有界 content 调用一次 Rerank，`top_n` 必须等于本次 fused 候选数 `N`。
8. 校验 Rerank 完整索引并稳定排序，取前 20，统计每域候选数和 coverage。
9. 返回 `RetrievalStageSuccess(batch, coverage)`，Capability 只透传 batch 到 evidence stage。

### 9.3 RRF、去重与 Rerank 精确规则

- 路径顺序继承 plan ordinal；每路候选先校验 `sourceRank=1..N` 连续且身份唯一。
- 同一 chunk 在多路/多域出现时只保留一份正文；除 `logicalDomainId/sourceRank` 外，标题、正文、来源字段、material type、hash、读取策略版本、policyRef 或快照任一冲突即 `invalid_provider_result`，不任选一份。
- `rrf_score = Σ 1/(60+source_rank)`；不支持配置权重，避免个人验证项目引入调参平台。
- Rerank 请求候选按 `rrf_score desc, chunk_id asc` 编号 0..N-1，`top_n=N`。响应必须恰覆盖全部索引，不允许丢失、重复、越界或非 finite score；最终 batch 再截断为前 20 条。
- 最终排序先按 Rerank score，并以 RRF/chunk ID 打破平局；不使用供应商返回顺序作隐式 tie-breaker。
- 所有成功路径的 `schemaVersion/profileVersion` 必须一致并属于启动快照，顶层 domain/Profile/path 必须回显请求；每项顶层 `readPolicyVersion/indexSnapshotId` 注入其候选。任一不一致丢弃全部 path 结果；batch 的 `index_snapshot_ids` 按 plan 首次出现顺序去重。

### 9.4 BGE 协议

Embedding 继承已核实的本地契约：

```json
POST http://127.0.0.1:8908/embed
{"texts":["查询文本"]}

200 {"dim":1024,"vectors":[[0.1,0.2]]}
```

Rerank 使用 2026-07-31 已只读点测的本地提供方契约：

```json
POST http://127.0.0.1:8909/rerank
{"query":"...","documents":["..."],"top_n":1,"normalize":true}

200 {"model":"BAAI/bge-reranker-v2-m3","results":[{"index":0,"text":"...","score":0.99}]}
```

Adapter 不含 API key，base URL 必须为组合根中冻结的 loopback HTTP 地址；发送 `Accept-Encoding: identity`，拒绝非 JSON/非 identity 响应，不跟随重定向，不允许请求改 host/model。Embedding 请求只发送精确字段 `texts`，响应只接受 `dim/vectors`；Rerank 请求以 UTF-8、紧凑 JSON、`ensure_ascii=false` 只发送 `query/documents/top_n/normalize=true`，不发送服务 OpenAPI 未声明的 `model`。Rerank 响应顶层只接受 `model/results`，`model` 必须等于冻结配置；每个 result 只接受 `index/text/score`，`index` 完整唯一、`text` 必须与 `documents[index]` UTF-8 字符串精确一致，验证后只构造 `RerankScore(index,score)` 并立即丢弃回显文本。Embedding 请求/响应原始字节上限分别为 8 KiB/64 KiB，Rerank 请求/响应均为 2 MiB；在完整聚合或 JSON 解码前流式计数并超限失败。2 MiB 用于覆盖当前 80×4096 code points 的紧凑 UTF-8 请求及提供方回显预算，仍须以自动化边界测试证明；超限时失败关闭。服务契约漂移时只能修改 provider Adapter 与契约测试，不能改变统一候选或 stage 语义。

## 10. 失败、取消与安全

### 10.1 失败类型与调用方可见错误码矩阵

| 触发 | path/stage 结果 | 公共 stage code | 可重试 | 载荷 |
|---|---|---|---:|---|
| ES 边界返回 401 | path `failure` | `read_decision_unverifiable` | 否 | 无；正常情况下无效身份应已由核心在调用前拒绝 |
| HTTP 403：role/domain 明确拒绝 | `forbidden` | `domain_forbidden` | 否 | 无 |
| 读权权威不可验证/失败 | `failure` | `read_authority_failure` | 否 | 无 |
| ES 无命中 | `no_result` | 无 | 否 | 空 candidates |
| 单路 ES/BGE timeout | path `timeout` | `retrieval_timeout` | 否 | 无 |
| HTTP 400/415 或 200/204 响应契约非法 | path `failure` | `invalid_provider_result` | 否 | 丢弃响应 |
| HTTP 429/404/405/406/其余 5xx/未列状态、单路 ES 或 embedding 失败 | path `failure` | `retrieval_failure` | 否 | 无 |
| Rerank timeout | stage timeout | `rerank_timeout` | 否 | 无 |
| Rerank/候选结构非法 | stage failure | `invalid_provider_result` | 否 | 丢弃候选 |

HTTP 状态映射以 8.3 和本表为唯一权威：401→`read_decision_unverifiable`，403→`domain_forbidden`，503→`read_authority_failure`，504→`retrieval_timeout`；禁止把 403 的明确拒绝与 503 的不可验证合并。任一已选整域 403 立即取消其他路径并返回 forbidden；读决定不可验证不得降为 no-result。部分路径技术失败时，stage 仍返回精确 coverage，是否继续仅由 `L2_01_00` 映射。

### 10.2 截止与并发

- stage 使用 `asyncio.timeout_at(stage_deadline)`，各 client 只接受计算后剩余秒数，不自建总超时。
- embedding 在 ES vector path 之前一次完成；ES path 使用有界 task group 并发，最多 4 个 task。
- 一个 task 异常必须先转 typed path failure，不能使 task group 泄漏原始异常。
- 外层 `CancelledError` 清理后继续传播；取消/超时后不得进入融合、Rerank 或 batch 构造。

### 10.3 日志与指标

允许：correlation ID、domain/path、有限状态、候选数、截断标记、profile/policy version、耗时。

禁止：JWT、subject、查询、向量、document/chunk ID、标题/正文、ES/BGE 原始响应、异常 message/stack。
候选计数可以是指标值，domain/path/status 可作低基数标签；任何文档身份不做标签。

### 10.4 事务边界与一致性

全链只读，不开启跨 ES、Embedding、Rerank 的事务。一次 stage 以进入时冻结的 plan、profile version 和 ES 返回的 `indexSnapshotId` 为请求级一致性边界；不同路径快照不一致时保留各自 snapshot ID 供下游复核，不伪造全局快照。取消、超时或提供方非法响应后不提交 batch，不接纳迟到结果。

### 10.5 权限与审计

读取授权的唯一执行权威是 `es-query-service`。Agent 只透传原始用户 JWT，并以有限状态记录授权结果；日志不得形成正文、身份或 token 的旁路审计副本。拒绝或不可验证决策必须能通过 correlation ID、逻辑域、策略版本和有限错误码追踪，但不得记录查询或候选内容。

## 11. 配置、启动校验与回滚

### 11.1 Python 配置

| 键 | 默认 | 代码上限/校验 |
|---|---|---|
| `AGENT_KNOWLEDGE_ES_BASE_URL` | 无 | 启用时必填受控 `http/https` origin，禁 path/query/fragment/userinfo |
| `AGENT_KNOWLEDGE_PROFILE_VERSION` | `tax-knowledge-search-v1` | 精确代码允许值；响应必须匹配 |
| `AGENT_KNOWLEDGE_EMBEDDING_BASE_URL` | `http://127.0.0.1:8908` | 仅 loopback，冻结 |
| `AGENT_KNOWLEDGE_RERANK_BASE_URL` | `http://127.0.0.1:8909` | 仅 loopback，冻结 |
| `AGENT_KNOWLEDGE_EMBEDDING_DIM` | `1024` | 必须 1024 |
| `AGENT_KNOWLEDGE_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | 仅用于校验响应 `model`，不作为请求字段且不允许请求覆盖 |
| `AGENT_KNOWLEDGE_FINAL_CANDIDATES` | `20` | 3～20；只控制完整 Rerank 后的 batch 截断，不改变 `top_n=N` |

domain→Profile 对由 `EsKnowledgeSearchAdapter` 代码定义固定为 `tax.policy→tax-policy-v1`、`tax.law→tax-law-v1`，不提供环境变量覆盖。未知 `AGENT_KNOWLEDGE_ES_/EMBEDDING_/RERANK_/PROFILE_` 前缀键启动失败。URL 不含凭证；JWT 仅来自请求 context。

### 11.2 Java 提供方配置

`es.query.knowledge` 建议包含 `enabled/profiles.<profile-id>.logical-domain-id/profile-version/read-policy-version/read-alias/expected-index-name/expected-index-uuid/mapping-version/index-snapshot-id/category-field/category-values/keyword-fields/vector-field/source-fields.*/max-candidates/max-content-chars`。这些键只能在 ES 服务端冻结，Agent 请求不能覆盖。任一启用 Profile 缺映射、版本、快照或字段，或启动只读核实不一致，则 Knowledge endpoint readiness=false。

`enabled=false` 时不创建 Controller、Knowledge SecurityFilterChain、远程 Profile 校验或 Knowledge ES client，fallback chain 仍保持既有端点行为。`enabled=true` 时任一静态/远程 Profile 校验失败，或容器缺少统一安全契约提供的 `@Qualifier("userRoleJwtAuthenticationConverter") Converter<Jwt, AbstractAuthenticationToken>`，均使本次 `es-query-service` 进程启动失败；不带半有效 Knowledge endpoint 继续，也不回退 Spring 默认 scope converter。该失败可能同时使既有 ES 端点不可用，因此发布前必须先在隔离实例验证，回滚为 `enabled=false` 后重启。本文只定义 converter 的消费名称、类型和可观察 Authority，不修改 `common-security` 提供方实现。

### 11.3 发布与回滚

- 先以 fake ES/BGE 完成 Python 契约，再在隔离环境部署 Java typed endpoint。
- 新 endpoint 不修改现有 generic endpoint 的 wire contract；对 Agent 客户端只暴露新 endpoint。
- `enabled=true` 的配置、安全依赖或远程 Profile 核实失败会阻止共享 `es-query-service` 进程启动；必须在隔离实例验证通过后切换，避免影响既有通用端点。
- 回滚时置 `AGENT_KNOWLEDGE_ENABLED=false` 并重启 Runtime；不回退为原始 DSL 调用。
- Provider 侧回滚同时置 `es.query.knowledge.enabled=false` 并重启 `es-query-service`；两侧任一未关闭都视为 Knowledge 不可用。
- 任何 alias/mapping 不符只保持 fake，不自动切换其他索引。

### 11.4 数据生命周期与迁移回滚

本文不新增数据库、队列或持久化表。plan、向量、路径结果和候选只存活于单次请求，结束后释放；日志不保存正文。索引 mapping、reindex 和 alias 切换属于范围外，若后续需要迁移，必须以独立设计和回滚证据控制，不能由本切片隐式执行。当前回滚只停用 Agent retrieval stage，不删除或改写现有 ES 数据。

## 12. 实现落点与边界签名

### 12.1 落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置 | 责任 | 必要性 | 规则 |
|---|---|---|---|---|---|---|---|
| `IMPL-KRET-001` | 建议新增 | Python contracts | `agent-runtime/src/agent_runtime/knowledge/retrieval/contracts.py` | candidate/path/batch/result/Port Protocol | 稳定检索语义 | 隔离提供方 | `DR-KRET-001/010/011/012` |
| `IMPL-KRET-002` | 建议新增 | Python stage | `agent-runtime/src/agent_runtime/knowledge/retrieval/stage.py` | `DefaultKnowledgeRetrievalStage` | 组合并发/预算/结果 | 不污染 Capability | `DR-KRET-005/008/009/010` |
| `IMPL-KRET-003` | 建议新增 | Python pure logic | `agent-runtime/src/agent_runtime/knowledge/retrieval/fusion.py` | `ReciprocalRankFusion` | 去重/RRF/稳定顺序 | 可独立测试 | `DR-KRET-006/007/011` |
| `IMPL-KRET-004` | 建议新增 | Python provider | `agent-runtime/src/agent_runtime/knowledge/retrieval/bge_embedding.py` | `BgeM3EmbeddingAdapter` | `/embed` 消费与 1024 维校验 | vector path | `DR-KRET-005/008/009/012` |
| `IMPL-KRET-005` | 建议新增 | Python provider | `agent-runtime/src/agent_runtime/knowledge/retrieval/bge_rerank.py` | `BgeRerankAdapter` | `/rerank` 一次重排 | 统一排序 | `DR-KRET-007/008/009/012` |
| `IMPL-KRET-006` | 建议新增 | Python HTTP | `agent-runtime/src/agent_runtime/knowledge/retrieval/http.py` | bounded no-redirect client | 共享超时/字节上限 | 避免漂移 | `DR-KRET-008/009/012` |
| `IMPL-KRET-007` | 建议新增 | Python ES adapter | `agent-runtime/src/agent_runtime/knowledge/retrieval/es_adapter.py` | `EsKnowledgeSearchAdapter` | typed HTTP/JWT 转换 | 不解析 role | `DR-KRET-002/003/004/012` |
| `IMPL-KRET-008` | 建议新增 | Java API/controller | `es-query-api/src/main/java/com/dylan/esquery/api/knowledge/KnowledgeSearchRequest.java`、`KnowledgeSearchResponse.java`、`KnowledgeSearchCandidate.java`；`es-query-service/src/main/java/com/dylan/esquery/controller/KnowledgeSearchController.java` | request/response/candidate DTO；byte[] `search` | 新增狭只读契约 | 原契约不满足且不能影响通用端点 | `DR-KRET-002/005/012` |
| `IMPL-KRET-009` | 建议新增 | Java security | `es-query-service/src/main/java/com/dylan/esquery/service/KnowledgeReadAccessGuard.java`、`KnowledgeReadDecision.java` | `authorize`、不可变 allow decision | 查询前 user/Authority/domain/Profile 读决定 | 正文前授权 | `DR-KRET-003/004/012` |
| `IMPL-KRET-010` | 建议新增 | Java retrieval | `es-query-service/src/main/java/com/dylan/esquery/service/KnowledgeSearchService.java` | `search` | 受控 mapping/DSL/typed candidate | 隐藏 ES | `DR-KRET-002/003/005/012` |
| `IMPL-KRET-011` | 建议新增 | Java config | `es-query-service/src/main/java/com/dylan/esquery/config/KnowledgeSearchProperties.java` | `es.query.knowledge.*` | 冻结域映射/上限 | 防请求选物理资源 | `DR-KRET-002/003/012` |
| `IMPL-KRET-012` | 建议新增 | Java web/security boundary | `es-query-service/src/main/java/com/dylan/esquery/web/KnowledgeSearchJsonCodec.java`、`KnowledgeSearchWebConfiguration.java`、`KnowledgeSearchSecurityConfiguration.java`、`KnowledgeSearchExceptionHandler.java`、`KnowledgeSearchExceptions.java` | `decodeRequest`、128 KiB filter bean、两条有序 SecurityFilterChain、有限异常/状态映射 | endpoint-scoped strict JSON/字节/认证/错误边界 | Knowledge chain 仅匹配 `/es/knowledge/**` 并在授权后执行 body filter；fallback chain 保持现有端点访问语义 | `DR-KRET-002/003/012` |
| `IMPL-KRET-013` | 建议修改 | Java build/bootstrap | `es-query-service/pom.xml`；`es-query-service/src/main/java/com/dylan/esquery/EsQueryServiceApplication.java`；`es-query-service/src/main/resources/application.yml` | 增加仓库内 `common-security` 与 validation 依赖、启用 `KnowledgeSearchProperties`、`enabled=false` 默认 | Authentication/校验/配置类可编译且默认不暴露新端点 | 不修改共享 role converter；不得依赖 auto-config 的全局 anyRequest authenticated | `DR-KRET-003/009/012` |

### 12.2 Python 边界关键签名

| 路径/符号 | 建议签名 | 校验与输出 | 异步/副作用 | 直接消费方 |
|---|---|---|---|---|
| `retrieval.contracts.KnowledgeSearchPort.search` | `async def search(self, *, request: KnowledgePathRequest, context: KnowledgeRetrievalContext, timeout_s: float) -> PathRetrievalResult` | 严格 plan/context/timeout；有限 tagged result | 一次 HTTP | stage |
| `retrieval.contracts.EmbeddingPort.embed` | `async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]` | 1～1024 chars；精确 1024 finite | 一次 HTTP | stage |
| `retrieval.contracts.RerankPort.rerank` | `async def rerank(self, *, query: str, candidates: tuple[AuthorizedKnowledgeCandidate, ...], timeout_s: float) -> tuple[RerankScore, ...]` | 1～80 candidates；完整唯一索引 | 一次 HTTP | stage |
| `retrieval.fusion.ReciprocalRankFusion.fuse` | `def fuse(self, results: tuple[PathCandidateSet, ...]) -> tuple[FusedCandidate, ...]` | rank 连续、身份/正文冲突拒绝 | 纯函数 | stage |
| `retrieval.stage.DefaultKnowledgeRetrievalStage.execute` | `async def execute(self, *, plan: KnowledgeRetrievalPlan, context: KnowledgeRetrievalContext, timeout_s: float) -> RetrievalStageResult[RankedKnowledgeBatch]` | 精确 coverage；异常不穿透 | 最多 1 embed+4 ES+1 rerank | Capability |

### 12.3 Java 边界关键签名

| 路径/类 | 建议方法 | 入参 | 返回/错误 | 副作用/消费方 |
|---|---|---|---|---|
| `KnowledgeSearchJsonCodec` | `KnowledgeSearchRequest decodeRequest(byte[] body)` | ≤128 KiB、严格 UTF-8、duplicate detection、unknown/trailing 拒绝，再执行 Bean Validation | 合法 DTO；非法抛 `KnowledgeInvalidRequestException`→400 | 纯解码；controller |
| `KnowledgeSearchController` | `ResponseEntity<KnowledgeSearchResponse> search(Authentication authentication, @RequestBody byte[] body)` | `@PostMapping(consumes=application/json,produces=application/json)`；security filter 已认证；codec 解码后只调 guard/service | 200 typed；400/401/403/415/429/502/503/504 | 一次 service；不直接访问 ES |
| `KnowledgeReadAccessGuard` | `KnowledgeReadDecision authorize(Authentication authentication, String logicalDomainId, String retrievalProfileId)` | principal 为 user JWT、有限 Authority、冻结 domain/Profile/policy | allow decision；明确拒绝→403，不可验证→503 | 无 ES 读；service |
| `KnowledgeSearchService` | `KnowledgeSearchResponse search(KnowledgeSearchRequest request, KnowledgeReadDecision decision)` | allow decision 与 domain 精确一致 | typed response；原始 ES 异常不穿透 | 一次只读 ES；controller |
| `KnowledgeSearchProperties` | `KnowledgeSearchProfile requireProfile(String logicalDomainId, String retrievalProfileId)`；`void afterPropertiesSet()` | 两级映射、字段、上限、版本、snapshot；精确 domain/Profile 查找 | 未知对抛类型异常；非法配置阻止 Knowledge endpoint readiness | guard/service |
| `KnowledgeSearchWebConfiguration` | `BoundedRequestBodyFilter knowledgeSearchBodyLimitFilter()` | 精确 path `/es/knowledge/search`、128 KiB；只作为普通 bean，不全局注册 | 供 Knowledge security chain 使用 | 无独立 Servlet 注册 |
| `KnowledgeSearchSecurityConfiguration` | `SecurityFilterChain knowledgeSearchSecurityFilterChain(HttpSecurity http, @Qualifier("userRoleJwtAuthenticationConverter") Converter<Jwt, AbstractAuthenticationToken> converter, BoundedRequestBodyFilter bodyFilter)`；`SecurityFilterChain existingEndpointsSecurityFilterChain(HttpSecurity http)` | `@Order(1)` 且 `enabled=true`：仅 `/es/knowledge/**`，两链均显式禁用 CSRF；Knowledge 链使用指定 converter+JWT/authenticated，并以 `addFilterAfter(bodyFilter, AuthorizationFilter.class)` 使 401/403 先于 body 校验；`@Order(2)` 对其他端点 permitAll 并保留显式 management guard | 缺失/无效 JWT 401；converter/配置缺失启用启动失败；现有 POST/PUT/DELETE 不因 CSRF/全局认证改变 | Spring Security；不得在此复制 role claim converter |

## 13. 测试与验证设计

### 13.1 测试矩阵

| 测试编号 | 规则 | 层级 | 建议路径/用例 | 关键断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-KRET-001` | `DR-KRET-001/002` | Architecture/Unit | 建议新增：`agent-runtime/tests/architecture/test_knowledge_retrieval_boundaries.py` | Capability 无 HTTP/ES/BGE import；Adapter 的 domain→Profile 对固定；请求无物理资源且模型不能覆盖 Profile | 边界泄漏 |
| `TEST-KRET-002` | `DR-KRET-003/004` | Java Unit | 建议新增：`es-query-service/src/test/java/com/dylan/esquery/service/KnowledgeReadAccessGuardTest.java` | ADMIN/VIEWER allow；unknown/mixed/empty Authority 与 domain/Profile 不匹配 403；权威/策略不可验证 503；ES=0 | 未授权调用 ES或拒绝/故障混义 |
| `TEST-KRET-003` | `DR-KRET-006/007` | Python Unit | 建议新增：`agent-runtime/tests/unit/knowledge/retrieval/test_fusion.py` | RRF 公式、所有证据/策略/快照字段冲突拒绝、Profile 一致、tie-break 精确 | 顺序漂移/任选冲突 |
| `TEST-KRET-004` | `DR-KRET-005/009/012` | Contract | 建议新增：`agent-runtime/tests/contract/knowledge/test_bge_embedding.py` | 一次调用、请求精确、维度/数值/超时、非 JSON/压缩/请求响应字节上限负向 | 非法向量或超限 body 被接纳 |
| `TEST-KRET-005` | `DR-KRET-007/009/012` | Contract | 建议新增：`agent-runtime/tests/contract/knowledge/test_bge_rerank.py` | 请求精确为 query/documents/top_n=N/normalize=true 且无 model；响应 model 精确、index 完整、text 与 documents[index] 精确关联、score finite；未知/重复字段、超时、非 JSON/压缩及 2 MiB/2 MiB 请求响应边界 | 错配回显、丢索引或超限 body 仍成功 |
| `TEST-KRET-006` | `DR-KRET-002/005/012` | Java Contract | 建议新增：`es-query-service/src/test/java/com/dylan/esquery/controller/KnowledgeSearchControllerContractTest.java` | 有效 JWT 下非 UTF-8、duplicate/unknown/trailing、超 128 KiB、域/Profile 不匹配均 400/ES=0；媒体类型错误 415；缺 JWT 的同类请求先返回 401；严格 typed response、无 raw JSON | strict/认证优先级不可实现或动态 DSL进入 |
| `TEST-KRET-007` | `DR-KRET-003/004/012` | Integration with spies | 建议新增：`agent-runtime/tests/integration/knowledge/test_authorization_before_content.py` | 401/403/503 分区；拒绝/不可验证时 ES body/BGE/stage batch 均 0 | 正文先于授权或错误混义 |
| `TEST-KRET-008` | `DR-KRET-010/012` | Parameterized Unit | 建议新增：`agent-runtime/tests/unit/knowledge/retrieval/test_failure_coverage.py` | 四路状态精确分区；forbidden/读权失败优先 | 失败变 no_result |
| `TEST-KRET-009` | `DR-KRET-008/009` | Async Unit | 建议新增：`agent-runtime/tests/unit/knowledge/retrieval/test_deadline_cancellation.py` | 子预算、最多调用数、取消 await、无 retry/迟到结果 | 后台继续/调用乘法 |
| `TEST-KRET-010` | `DR-KRET-011/012` | Contract | 建议新增：`agent-runtime/tests/contract/knowledge/test_ranked_batch.py` | batch 身份/hash/policy/snapshot 完整；无 JWT/ACL/egress decision | 下游无法复核或越权决策 |
| `TEST-KRET-011` | `DR-KRET-002/003/005/012` | Java Unit/Integration | 建议新增：`es-query-service/src/test/java/com/dylan/esquery/service/KnowledgeSearchServiceTest.java`、`es-query-service/src/test/java/com/dylan/esquery/config/KnowledgeSearchPropertiesTest.java`、`es-query-service/src/test/java/com/dylan/esquery/controller/KnowledgeSearchSecurityCompatibilityTest.java` | keyword/KNN 只由 Profile 构造；limit+1/truncated/rank/hash 精确；alias 多目标、UUID/mapping/snapshot 漂移不就绪；Knowledge 无 JWT 401，现有 search/management 入口仍保持原安全语义 | 物理映射漂移、快照伪造或安全依赖改变旧契约 |

### 13.2 验证命令

| 验证编号 | 命令/步骤 | 范围 | 预期 | 当前状态 |
|---|---|---|---|---|
| `VAL-KRET-001` | `python -m pytest agent-runtime/tests/unit/knowledge/retrieval agent-runtime/tests/architecture/test_knowledge_retrieval_boundaries.py -q` | Python 纯逻辑/边界 | 全通过 | 未执行：目标代码/测试不存在 |
| `VAL-KRET-002` | `python -m pytest agent-runtime/tests/contract/knowledge/test_bge_embedding.py agent-runtime/tests/contract/knowledge/test_bge_rerank.py -q` | 本地模型 wire contract | fake 先通过，opt-in 实例后记录真实证据 | 自动化测试未执行：目标测试不存在；2026-07-31 已用合成文本手工点测当前实例，Embedding 1×1024、Rerank 模型/索引/文本/分数均符合 9.4 当前契约 |
| `VAL-KRET-003` | `mvn -f serviceCenter/pom.xml -pl :common-security,:es-query-api,:es-query-service -am test` | Java DTO/service/security/web/config/contract及共享依赖兼容 | 全通过 | 2026-07-31 现有基线回归 `BUILD SUCCESS`（common-security 15、es-query-service 14 项测试通过；es-query-api 无测试）；本文建议新增的 Knowledge DTO/service/security/contract 测试尚未实现，门禁保持 Open |
| `VAL-KRET-004` | opt-in 点测 `9200/8908/8909` 及维度/mapping/超时 | 真实检索 | 契约、维度、顺序均一致 | 部分完成：2026-07-31 三端口在线，ES 9.4.1/税务索引、Embedding 1024 维和 Rerank 两文档顺序已核实；typed endpoint、alias/Profile/UUID/mapping/snapshot、授权、上限与超时仍未验证 |
| `VAL-KRET-005` | ADMIN/VIEWER/missing/unknown/malformed/service-token 跨服务矩阵 | 授权先于正文 | allow 时 typed candidates；deny 时 ES/BGE=0 | 未执行；Authority 契约缺失 |

## 14. 风险、门禁与授权

### 14.1 风险与待确认

| 编号 | 类型 | 证据缺口/风险 | 触发 | 影响 | 处置 | 阻塞性 |
|---|---|---|---|---|---|---|
| `RISK-KRET-001` | 物理映射 | 当前 ES mapping、alias 单目标、index UUID 和不可变快照未在线核实；首期无运行期轮询 | 真实检索或运行中外部原地写入 | 域错分、snapshot 标识过期或查询失败 | 门禁前导出 alias/index UUID/mapping/count 证据并与 Profile snapshot 对齐；只读权限和变更前停用/重启 | 阻塞真实集成；外部绕过流程写入是剩余风险 |
| `RISK-KRET-002` | 读权 | 索引无已证明的同质读策略标记 | 返回正文 | 未授权泄露 | v1 只在整库同质证据后启用 | 阻塞真实集成 |
| `RISK-KRET-003` | Rerank 契约 | 当前 OpenAPI 未声明 200 响应 schema；手工点测确认会回显 model/text，但自动化 exact-field、文本关联、2 MiB 边界、超时和漂移测试尚不存在 | Provider 升级或大候选调用 | Adapter 不兼容、错配分数或合法大响应被误拒 | 9.4 精确解码/关联后丢弃回显；实施时先完成 fake 与 opt-in 契约测试 | 阻塞真实 Rerank，不阻塞设计/基线点测 |
| `RISK-KRET-004` | 候选大小 | 80×4096 chars 可压力 Rerank | 双域全命中 | 延迟/内存 | 候选/正文/字节上限和 5s 超时 | 不阻塞 fake；需实测 |
| `RISK-KRET-005` | 效果 | 固定 RRF 参数和 Rerank topN 尚未代表最优效果 | P5 | 召回/答案质量不足 | `L2_01_02/SA-GATE-007` 评估，不在本文建调参平台 | 不阻塞链路设计 |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威 | 责任方 | 最晚阶段 | 验证方法 | 状态 | 未关闭允许/禁止 | 替代路径 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `KQ-GATE-002` | `slice_implementation` | `L2_01_01` 检索代码切片 | 实施 Python/Java 目标代码 | 本文独立评审通过、实施触点/测试/回滚明确、获得代码授权；新增 `es-query-api` 公开契约和 `es-query-service` 依赖/端点须由对应提供方明确授权 | 本文评审证据+授权 | 项目维护者/ES 提供方 | P3 前 | 独立评审+实施授权 | Open | 允许文档/fake；禁止目标代码、依赖/端点变更和完成声明 | in-memory ES/BGE fakes |
| `SA-GATE-003` | `integration` | Knowledge 真实 ES/BGE | 启用真实 retrieval stage | typed endpoint、授权前置、物理映射、同质读策略、BGE 维度/Rerank 契约和负向测试全部通过 | ES mapping/manifest、Authority、provider PoC | 维护者/ES/BGE/安全方 | P4 前 | `VAL-KRET-003/004/005` | Open | 允许 fake；禁止真实正文进 Agent/BGE | synthetic candidates |

### 14.3 需要后续授权的动作

- 新增 `es-query-api` Knowledge DTO 和 `es-query-service` endpoint/security/service/config/test；修改其 `pom.xml`/bootstrap 以复用仓库内 `common-security` 与 validation。
- 新增 Python Agent 代码、配置、测试及依赖。
- 真实访问 ES/BGE、修改公开契约、索引 mapping/reindex/alias 或 role converter。

## 15. 内部自检记录（作者内审）

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-31 | 0 | 5 | 6 | 11 | 0 | 结构、追踪、条件章节和建议新增证据已修复；严格校验首次清零 |
| 2 | 2026-07-31 | 0 | 2 | 2 | 4 | 0 | Rerank 全覆盖与候选空值/策略契约已对齐，无遗留 Major |
| 3 | 2026-07-31 | 0 | 0 | 3 | 3 | 0 | 错误映射、哈希和 scoped JSON 校验已收口，达到 Draft 内审停止条件 |

## 16. 独立正式评审记录

### 16.1 第 1 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-KRET-001` | S1 | REQ/L0/L1 将物理映射归 Adapter，本文又归 ES 服务，形成重复权威且无法同时满足“请求不含物理资源” | 原子引入 domain→Profile→physical 两级映射并同步 REQ_00 v1.3、L0_00 v0.5、L1_01 v0.3 | Closed |
| `REV-KRET-002` | S1 | 当前 ES 服务未依赖安全/validation，文档也未列 POM/bootstrap/默认禁用触点，所列 Authentication/@Valid 方案不能直接落地 | 增加 `IMPL-KRET-013`，固定仓库内安全依赖、validation、properties 装配和默认禁用；共享 role converter 仍受集成门禁控制 | Closed |
| `REV-KRET-003` | S1 | typed Controller 参数无法证明 endpoint-scoped duplicate/non-UTF-8/body-limit 约束，且无 Codec/filter/错误处理落点 | 改为 byte[] Controller + 独立 strict Codec + 路径限定 `BoundedRequestBodyFilter`，补齐签名和负向测试 | Closed |
| `REV-KRET-004` | S1 | 403 同时表示明确拒绝和策略不可验证，Python 又不解析错误 body，无法满足上位失败可区分约束 | 固定 401/403/503/504 独占语义及有限 path 映射，补齐 `KnowledgeReadDecision` | Closed |
| `REV-KRET-005` | S1 | 未定义 Profile 字段、keyword/KNN 生成、候选排序、truncated、hash 与 snapshot 来源，Java provider 切片仍不可直接实现 | 增加 8.6 的强类型 Profile、内部查询、候选映射和不可变快照规则及测试 | Closed |
| `REV-KRET-006` | S2 | 跨路径仅比较标题/正文/hash/快照，未校验 Profile 回显、策略/来源字段和 batch 单一 profile version | 扩大冲突集合，固定顶层回显/版本一致和 snapshot 去重顺序 | Closed |

### 16.2 第 2 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-KRET-007` | S1 | 仅增加 `common-security` 依赖会触发默认 `anyRequest().authenticated()`，使既有通用 ES 端点无意变为需 JWT，与“新端点不改变旧契约”冲突 | 增加两条有序 SecurityFilterChain：Knowledge 专用认证链与保留既有行为的 fallback 链，并增加兼容测试 | Closed |
| `REV-KRET-008` | S1 | 非 JSON 媒体类型实际由 Spring 返回 415，且 400/415/204/未列状态没有完整 Python 映射，Adapter 可能产生自由解释 | 固定 Controller consumes/produces 及全部状态穷尽映射；本地合法请求收到 400/415 视为 provider contract invalid | Closed |
| `REV-KRET-009` | S2 | Java DTO 和 `KnowledgeReadDecision` 只有 JSON 示例/字段名，没有 Java 类型、nullability 与集合冻结语义 | 补齐三类 API DTO 和读取决定的具体 Java 类型、null/集合约束 | Closed |

### 16.3 第 3 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-KRET-010` | S1 | 两条 SecurityFilterChain 未固定 CSRF 和统一 converter 装配；fallback 即使 permitAll 也可能令既有写/查 POST 因 CSRF 403，Knowledge 还可能静默使用默认 scope converter | 两链显式关闭 CSRF；Knowledge 链在 enabled 时强制注入具名统一 role converter，缺失启动失败 | Closed |
| `REV-KRET-011` | S1 | 文档宣称 alias/原地写入会让 readiness=false，但首期未设计轮询，运行中变更无法自动发现，snapshot 追踪可能虚假 | 将保证收窄为启用启动核实；运行中以只读权限、变更前停用和重启控制，并登记剩余风险 | Closed |
| `REV-KRET-012` | S2 | snapshot hash 使用 mapping version 但 Profile 未定义该配置，预期值与计算值的权威关系不清 | 增加 mapping-version，固定 UTF-8 拼接/hash 算法，并要求启动重算与预期值相等 | Closed |

### 16.4 第 4 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-KRET-013` | S1 | properties 校验、converter 和远程 Profile 失败有时写 readiness=false、有时写启动失败，且共享服务没有独立 endpoint readiness 生命周期 | 固定 disabled 不创建 Knowledge 组件；enabled 任一依赖失败使共享进程启动失败，并补充隔离验证与双侧回滚 | Closed |
| `REV-KRET-014` | S1 | body-limit 作为独立 Servlet filter 时顺序不确定，未认证超限请求可能先返回 400，无法保证认证优先级 | 不全局注册；作为 bean 加入 Knowledge SecurityFilterChain 的 AuthorizationFilter 之后，负向测试固定 401 优先 | Closed |
| `REV-KRET-015` | S2 | ES/BGE HTTP 只写候选/字符上限，未限制响应 Content-Type、压缩和聚合前字节，存在响应放大与解码歧义 | 三类 Provider 统一 identity/JSON，固定请求响应原始字节上限和流式计数 | Closed |
| `REV-KRET-016` | S2 | Provider 侧 enabled 回滚缺失，只关闭 Runtime 仍可能留下半配置共享服务 | 增加 Agent/Provider 双侧独立禁用与重启回滚边界 | Closed |

### 16.5 第 5 轮冻结发现、修复与终审

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 状态 |
|---|---|---|---|---|
| `REV-KRET-017` | S2 | `PathRank`、`PathCandidateSet`、`RerankScore` 已被公共签名引用但未定义字段，融合/Rerank 实现仍可能分叉为可变 dict 或供应商顺序 | 补充三个不可变内部类型、字段与索引/顺序不变量 | Closed |
| `REV-KRET-018` | S2 | `KnowledgeInvalidRequestException` 等有限异常已有映射语义但没有实现文件落点 | 增加 `KnowledgeSearchExceptions.java`，由 exception handler 穷尽映射且不暴露 message | Closed |
| `REV-KRET-019` | S1 | Java 验证命令未指定仓库聚合 POM，Python 命令/测试落点也未从仓库根目录定位 `agent-runtime`；现有命令和部分路径不可复现 | 固定 Maven 聚合 POM/artifactId 选择器，统一 Python 命令及全部建议测试路径为 `agent-runtime/tests/...`，并执行现有 Java 基线回归 | Closed |
| `REV-KRET-020` | S1 | 实时 Rerank wire 会回显顶层 model 和逐项 text，原示例/测试未固定关联；原 256 KiB 响应上限也小于 80×4096 字符合法回显的可能大小 | 请求对齐 OpenAPI 并显式 normalize；严格验证 model、index、text 与输入关联后丢弃 text；Rerank 响应上限调为 2 MiB 并补边界测试 | Closed |

修复后重新从 REQ/L0/L1 两级映射、L2_01_00 stage 接缝、Python/Java 类型、严格 HTTP、JWT/Authority、ES 查询与 snapshot、BGE、融合/Rerank、截止取消、配置、发布回滚、测试追踪和门禁全量复核；未发现新的未关闭 S0/S1/S2，`REV-KRET-001`～`REV-KRET-020` 全部关闭。评审结论为 Approved；该结论不关闭 `KQ-GATE-002` 或 `SA-GATE-003`。

### 16.6 L2_01_02 下游消费兼容检查

针对 `L2_01_02` v0.2 重新核对 `RankedKnowledgeCandidate(candidate,domain_ids,rerank_score,rank)`、嵌套 `AuthorizedKnowledgeCandidate`、`profile_version/index_snapshot_ids`、NFC 正文 hash、`read_policy_version` 和 opaque `policy_ref`。Evidence Stage 只复核、选择并投影这些既有字段，不要求本契约增加出域决定、模型引用或摘要字段，也不把 `policyRef` 误作允许决定；未发现新的 S0/S1/S2。本文保持 v0.2 Approved，检索实施与真实集成门禁不变。

## 17. 实施前检查

- [x] 范围内 REQ/CON 已映射 DR、IMPL、TEST 和 VAL。
- [x] Python/Java/API/安全实施剖面和责任边界已区分。
- [x] 物理索引/DSL 不进入 Agent 契约，读取授权先于正文。
- [x] 多路召回、RRF、Rerank、截止、取消和失败语义明确。
- [x] 已存在、建议新增和待确认证据已分离。
- [x] 三轮作者内审已完成且无遗留 Blocker/Major。
- [x] 五轮独立评审—修复—复核已完成，全部 S0/S1/S2 关闭。
- [x] `validate_detailed_design.py --strict` 终态复跑通过：0 errors、0 warnings（2026-08-01）。
- [ ] 用户另行授权实施并关闭 `KQ-GATE-002`；设计通过不自动关闭门禁。

## 18. 当前结论

本文 v0.2 已完成五轮独立评审—修复—复核并 Approved，且 `L2_01_02` 下游消费兼容检查通过，可作为 `L2_01_01` 检索切片的详细设计基线；但“设计可实施”不等于“已获代码实施授权”。`KQ-GATE-002`、`SA-GATE-003` 均保持 Open，目标代码、真实 ES/BGE、税务正文返回和统一 role converter 联调仍禁止。
