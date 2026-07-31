# [L2_01_01] 单体 Agent Knowledge 检索与本地模型接入详细设计 L2

> 文档层级：L2
> 文档状态：Draft

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent Knowledge 检索与本地模型接入详细设计 |
| 文档标识 | `SA-L2-KNOWLEDGE-RETRIEVAL-001` |
| 文档编号 | `L2_01_01` |
| 文档路径 | `docs/design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Draft |
| 当前版本 | v0.1 |
| 日期 | 2026-07-31 |
| 适用范围 | Python `agent-runtime` 内 Knowledge Retrieval Stage/Adapter、ES 类型化只读消费、BGE-M3 Embedding、BAAI/bge-reranker-v2-m3 Rerank、多路召回融合及排序候选契约；必要的 `es-query-api/es-query-service` 最小公开接口改造设计 |
| 上位文档 | [`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v0.2 Approved；`KQ-GATE-001` Closed |
| 直接输入 | [`L2_01_00`](L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) v0.2 Approved；[`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4 Approved |
| 后续消费方 | 规划中的 `L2_01_02` Knowledge 证据、出域、摘要与效果验证 |
| 外部契约 | `es-query-api`/`es-query-service`；Elasticsearch `9200`；BGE-M3 `8908`；BAAI/bge-reranker-v2-m3 `8909`；`auth-service/common-security` 用户 JWT/Authority |
| 实现基线 | 目标 `agent-runtime` 不存在；`es-query-service` 只有原始 DSL/向量查询并返回原始 JSON，未提供 Knowledge 类型化候选、读取授权和稳定失败契约 |
| 当前环境证据 | `.tmp/chinatax-v2/build_manifest.json` 记录税务索引历史快照及 1024 维 BGE-M3；2026-07-31 点测 `9200/8908/8909` 均拒绝连接，不构成当前可用证据 |
| 是否可作为实现依据 | 否 |
| 实施依据说明 | 本文完成内部自检后仍需独立评审，并关闭对应 `KQ-GATE-002` 切片实施门禁 |
| 当前允许范围 | 文档评审、契约样例推演、只读基线核实和不访问真实服务的 fake 验证设计 |
| 当前禁止动作 | 修改 Agent/ES/安全代码、配置、测试或公开契约；启用真实 ES/BGE；返回未授权候选正文；关闭 `KQ-GATE-002`/`SA-GATE-003` |
| 修改权限 | 本轮仅获授权新建第三批 L2 及原子同步直接文档索引；代码、契约和运行环境只读 |

> 本文将“Agent 检索编排”与“ES 物理查询”分开：Python Adapter 负责多路执行、融合、Rerank 和统一候选；`es-query-service` 只负责受控域映射、读取授权和类型化只读召回。本文不实施证据出域或 DeepSeek 摘要。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-31 | 全文 | 第三批 L2 依序编写 | 新建 Knowledge Retrieval/ES/BGE 详细设计，固定责任、类型契约、融合/Rerank、权限前置、失败语义、实现落点与门禁 |
| 2 | 2026-07-31 | 1/4/7/9～15 章 | 第 1 轮内部自检 | 修复详细设计结构关键词、追踪 ID 映射、依赖禁令、失败/安全/事务/数据生命周期覆盖、建议新增路径标识和实施依据字段 |
| 3 | 2026-07-31 | 4/8/9/11/15 章 | 第 2 轮内部自检 | 收紧候选字段空值、策略引用、Rerank 全覆盖与最终截断语义，并消除 Embedding 与候选 BGE Rerank 授权时序歧义 |
| 4 | 2026-07-31 | 8/10/12～16 章 | 第 3 轮内部自检 | 对齐 401 的 stage 有限错误映射，固定正文哈希语义和端点级重复键检测，并完成实现前可验证性收口 |
| 5 | 2026-07-31 | 6/12/13 章 | 第三批原子一致性同步 | 展开已存在及建议新增的 Java 类/测试完整路径；不改变三轮内审结论或设计语义 |

## 3. 背景、目标与范围

### 3.1 背景与问题

`L2_01_00` 已生成最多四个 `logical_domain_id + keyword/vector` 计划项，但故意不定义物理索引、BGE 协议、候选或融合算法。当前 `es-query-service` 允许调用方传入物理索引和原始 DSL/向量字段，返回 Elasticsearch 原始 JSON，且 Knowledge 查询未经用户读取授权。若 Python 直接依赖该接口，会泄露物理资源、让模型间接控制 DSL，并使未授权正文先进入 Agent/BGE。

### 3.2 目标与验收行为

| 需求编号 | 目标或可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-KRET-001` | 只消费代码绑定的两个逻辑域和两条路径 | 任意请求不含物理索引、DSL、字段名或 URL；未知域/路径在连网前拒绝 | L1_01 7.3/8.1；L2_01_00 8.3/9.6 |
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
| `REQ-KRET-001`,`CON-KRET-001` | ES 边界 | `DR-KRET-001`、`DR-KRET-002` | Python Adapter/ES API | 受控请求/typed response | `IMPL-KRET-001/007/008` | `TEST-KRET-001/006` | `VAL-KRET-001/003` |
| `REQ-KRET-002`,`CON-KRET-002`,`CON-KRET-007` | 读取授权 | `DR-KRET-003`、`DR-KRET-004`、`DR-KRET-012` | ES 读取权威/业务安全边界 | JWT→Authority→domain decision | `IMPL-KRET-009/010` | `TEST-KRET-002/007` | `VAL-KRET-003/005` |
| `REQ-KRET-003`,`CON-KRET-003` | 召回 | `DR-KRET-005`、`DR-KRET-006` | retrieval stage/ES service | 统一候选 | `IMPL-KRET-002/003/008` | `TEST-KRET-003/006` | `VAL-KRET-001/003` |
| `REQ-KRET-004` | Embedding | `DR-KRET-005`、`DR-KRET-009` | BGE embedding adapter | 1024 维向量 | `IMPL-KRET-004` | `TEST-KRET-004` | `VAL-KRET-002/004` |
| `REQ-KRET-005` | 融合/Rerank | `DR-KRET-006`、`DR-KRET-007` | fusion/rerank adapter | ranked batch | `IMPL-KRET-003/005` | `TEST-KRET-003/005` | `VAL-KRET-001/004` |
| `REQ-KRET-006`,`CON-KRET-005` | 失败/coverage | `DR-KRET-010`、`DR-KRET-012` | retrieval stage | typed result/coverage | `IMPL-KRET-001/002` | `TEST-KRET-008` | `VAL-KRET-001` |
| `REQ-KRET-007`,`CON-KRET-004` | 运行约束 | `DR-KRET-008`、`DR-KRET-009` | stage/各 client | deadline/cancel/no retry | `IMPL-KRET-002/004/005/006` | `TEST-KRET-009` | `VAL-KRET-001/004` |
| `REQ-KRET-008`,`CON-KRET-006` | 下游候选 | `DR-KRET-011` | retrieval stage | opaque ranked batch | `IMPL-KRET-001/003` | `TEST-KRET-010` | `VAL-KRET-001` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文责任 | 对方责任 | 交互契约 | 所有权 | 权限 |
|---|---|---|---|---|---|---|
| `L2_01_00` | parent/direct input | 消费 plan/context，返回 stage result | 问题、域、计划和部分成功判定 | `KnowledgeRetrievalStage.execute` | 流程状态 | 只读 |
| `es-query-service` | external provider | 定义最小 Knowledge 消费契约 | 域映射、授权、ES 只读查询、typed candidate | `POST /es/knowledge/search` | 物理索引/读取决定 | 设计；代码只读 |
| Elasticsearch | infrastructure | 不直接访问 | 候选存储/检索 | 只由 ES service 消费 | index/alias | 只读证据 |
| BGE-M3 | local provider | 定义查询 embedding 消费 | 生成向量 | `POST /embed` | 模型运行 | 只读证据 |
| BGE Rerank | local provider | 定义候选重排消费 | 返回索引/分数 | `POST /rerank` | 模型运行 | 只读证据 |
| `auth-service/common-security` | security authority | 仅消费角色/Authority 观察契约 | JWT 签发、验签与映射 | `role`→`ROLE_ADMIN/VIEWER` | 身份/角色 | 只读 |
| `L2_01_02` | downstream | 提供排序候选与策略引用 | 证据裁剪、出域、摘要 | `RankedKnowledgeBatch` | 证据/出域 | 待建 |

## 6. 当前实现基线与最小改造

### 6.1 已核实事实

| 状态 | 路径/证据 | 事实 | 设计影响 |
|---|---|---|---|
| 已存在 | `es-query-service/src/main/java/com/dylan/esquery/controller/EsQueryController.java` | `/es/indexes/{index}/search` 接受原始 DSL；`vector-search` 接受字段/向量 | Agent 不得复用为目标契约 |
| 已存在 | `es-query-service/src/main/java/com/dylan/esquery/service/EsDocumentService.java` | 返回 ES 原始 JSON，开放物理索引和字段 | 需新增狭契约，不全面重构 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/service/EmployeeEmbeddingService.java` | BGE 本地契约为 `/embed` + `texts`，校验向量维度 | 作为迁移证据，不作 Agent 基线 |
| 已存在 | `.tmp/chinatax-v2/build_manifest.json` | 历史 alias `agent-doc-tax-policy-v2-read`、`domain=tax_policy`、BGE-M3 1024 维、13003 chunks | 只是快照，真实集成须重新核实 |
| 已存在 | `.tmp/chinatax-v2/train.parquet` | 源字段含 `title/channel/content/document_number/effect_level/...` | 可推导域分类候选，不证明 ES 当前 mapping |
| 缺失 | 当前 Java/security | Knowledge typed DTO、候选正文前读取决定、role converter | 真实集成失败关闭 |
| 待确认 | 本地端口 | 2026-07-31 `9200/8908/8909` 未运行，Rerank 线上请求/响应未点测 | 不阻塞 fake 设计；阻塞 `SA-GATE-003` |

### 6.2 根因

Knowledge 原有索引资产是实验性数据资产，`es-query-service` 则是通用 ES 工具边界；两者没有形成“用户授权后的 Knowledge 类型化候选”服务契约。本文不新增 `knowledge-service`，而是在 `es-query-service` 中收紧其已有检索能力的 Knowledge 专用只读入口。

### 6.3 最小变更方案

| 变更项 | 必要性 | 复用 | 不采用方案 |
|---|---|---|---|
| Python `knowledge/retrieval` 子包 | 承载跨提供方组合且不污染 Capability | L2_01_00 stage Protocol | 不把 ES/BGE 细节写入建议新增的 `capability.py` |
| ES Knowledge typed endpoint | 隐藏索引/DSL，强制授权前置 | 现有 RestClient/ObjectMapper | 不让 Python 消费原始 DSL endpoint |
| Embedding/Rerank 独立 Port | 本地模型契约和测试缝隙 | 已确认的 BGE-M3 实例 | 不引入通用模型框架 |
| 确定 RRF + 一次 Rerank | 满足多路召回与稳定排序 | 计划路径顺序 | 不引入可配置排序脚本/权重平台 |

## 7. 责任、分层与依赖

### 7.1 责任分解

| 组件 | 状态 | 唯一职责 | 明确不负责 | 输入/输出 |
|---|---|---|---|---|
| `DefaultKnowledgeRetrievalStage` | 建议新增 | 按 plan 和预算组合召回、融合、Rerank | 问题改写、读规则、证据出域 | plan/context→stage result |
| `KnowledgeSearchPort` | 建议新增 | 类型化只读候选边界 | URL/DSL/物理域暴露 | search request→path result |
| `EsKnowledgeSearchAdapter` | 建议新增 | JWT 原样透传和 ES typed DTO 转换 | 本地授权、融合/Rerank | typed request→candidate tuple |
| `BgeM3EmbeddingAdapter` | 建议新增 | 一次查询向量生成/校验 | 文档向量建索引 | text→1024-vector |
| `ReciprocalRankFusion` | 建议新增 | 身份去重和确定 RRF | 语义评分 | path candidates→fused |
| `BgeRerankAdapter` | 建议新增 | 一次有界候选重排 | 决定证据出域 | query+fused→ranked |
| `KnowledgeSearchController/Service` | 建议新增 | 授权后生成类型候选 | Agent 融合、Rerank、证据 | HTTP DTO→typed response |
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

ES 授权、物理映射和查询与索引一起变化，放在 Java 提供方；多路预算、融合与 Rerank 随 Agent 检索语义变化，放在 Python Adapter。两者仅共享类型化候选 HTTP 契约，避免将 `es-query-service` 扩展为 Agent 编排器。

## 8. 核心契约

### 8.1 Python 内部类型

| 类型 | 必填字段 | 不变量 |
|---|---|---|
| `KnowledgePathRequest` | `logical_domain_id,path,query_text,query_vector,candidate_limit` | path 仅 keyword/vector；keyword 无 vector，vector 恰有 1024 个 finite float |
| `AuthorizedKnowledgeCandidate` | `document_id,chunk_id,domain_id,title,content,source_url,document_number,written_date,material_type,source_rank,content_sha256,read_policy_version,policy_ref,index_snapshot_id` | 可空来源字段也必须显式存在；字符串 NFC/长度有界；不含 embedding、ES score、ACL 正文或 JWT |
| `PathRetrievalResult` | tagged `candidates/no_result/forbidden/timeout/failure` | 失败不携带候选/自由错误 |
| `FusedCandidate` | `candidate,domain_ids,path_ranks,rrf_score` | domain/path 有序去重；RRF 只依赖 rank |
| `RankedKnowledgeCandidate` | `candidate,domain_ids,rerank_score,rank` | rank 从 1 连续；score finite |
| `RankedKnowledgeBatch` | `candidates,profile_version,index_snapshot_ids` | 非空、最多 20；快照 ID 有序去重 |

所有 Python 数据类使用 `@dataclass(frozen=True, slots=True, kw_only=True)`，tuple 深冻结；不使用可变 dict 作为跨层候选契约。

### 8.2 Knowledge 类型化 HTTP 请求

`POST /es/knowledge/search`，`Authorization: Bearer <original-user-jwt>`，`Content-Type: application/json`：

```json
{
  "schemaVersion": 1,
  "logicalDomainId": "tax.policy",
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
| `path` | 仅 `keyword/vector` |
| `queryText` | keyword 必填，NFC 1～1024 code points；vector 必须为 null |
| `queryVector` | vector 必填且精确 1024 个 finite JSON number；keyword 必须 null |
| `limit` | 5～20，与 plan 一致 |

拒绝未知/重复 JSON key、额外字段、非 UTF-8、超 128 KiB body。请求不接受 index、alias、field、DSL、filter、sort、host、model 或 ACL。

### 8.3 HTTP 响应

```json
{
  "schemaVersion": 1,
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

- 200 表示查询已授权且契约可判定；空 candidates 表示 no-result。
- 400 仅表示类型请求非法；401 表示 token 认证失败；403 表示经验证 token 的 role/domain 被拒绝或不可判定。
- 429 映射 rate-limited；5xx 映射 provider failure；不解析错误 body。
- 响应上限 2 MiB；每候选 content 最多 4096 code points、title 256、ID 256、URL 1024；最多 20 条。
- 顶层字段和每个候选字段均必须存在；拒绝未知/重复字段，重复键检测必须限定在新增 Knowledge 请求/响应解码边界，不改变现有通用端点。`sourceUrl/documentNumber/writtenDate` 可为 JSON null，其余字段非 null；`writtenDate` 非空时必须符合 ISO 8601 日历日期（如 `2025-01-01`），`content` 不得为空。
- `contentSha256` 精确等于返回候选 `content` 经 NFC 后 UTF-8 字节的 SHA-256 小写十六进制；content 超限时提供方返回契约失败，不静默截断后重算哈希。
- `policyRef` 是 `L2_01_02` 消费的必填 opaque ID，不表示出域允许；缺失或空白属于 `invalid_provider_result`。当前索引未证明具备该字段，因此真实集成保持关闭。

### 8.4 物理域映射

ES 服务端以冻结 `KnowledgeSearchProfile` 映射逻辑域，不接受请求选择：

| 逻辑域 | 受控读 alias | 分类意图 | 当前证据 |
|---|---|---|---|
| `tax.policy` | `agent-doc-tax-policy-v2-read` | 税务通知、公告、政策、解读等非法律类别 | alias 仅由历史 manifest 证明；实际 mapping/filter 待 `SA-GATE-003` 核实 |
| `tax.law` | 同一受控 alias | `channel/effect_level` 归一化为法律、行政法规或司法解释 | 源 parquet 字段存在；ES 字段名/mapping 待核实 |

两域不使用两套索引；映射仅为同一税务资料库的受控过滤视图。若不能证明分类完备、互斥/重叠规则和 alias 快照，该域不就绪，不回退为全索引搜索。

### 8.5 读取授权契约

v1 税务知识只允许经验证用户 token 且 Authority 集精确非空、全部属于 `ROLE_ADMIN/ROLE_VIEWER`。含未知 Authority、role 缺失/空白/类型错误、service token 或策略版本不可验证时整个请求 403，ES 调用为 0。

`tax-public-authenticated-v1` 是首批整库同质读取策略的建议版本，不是聊天确认即可生效的事实。`SA-GATE-003` 关闭前必须有索引快照证据证明所有文档均属该读取策略；若任一文档需异质 ACL，v1 整库绑定不得启用，必须先扩展权威契约。

## 9. 详细功能与处理流程

### 9.1 设计规则

| 规则编号 | 规则 | 责任主体 | 触发 | 效果 |
|---|---|---|---|---|
| `DR-KRET-001` | Capability 只调用 `KnowledgeRetrievalStage`，不引用提供方 DTO | Capability/Port | stage 调用 | 依赖单向 |
| `DR-KRET-002` | ES API 不接收物理资源/DSL，服务端代码绑定域/path 映射 | ES API/service | HTTP 请求 | 无动态 ES |
| `DR-KRET-003` | 认证、Authority 和域读决定在构造 ES 请求前完成 | ES guard | 每路请求 | 未授权正文零暴露 |
| `DR-KRET-004` | Python 不解析 role/ACL，只透传 opaque user token 并信任 typed allow/deny | Python adapter | 出站 | 权威不重复 |
| `DR-KRET-005` | 所有 vector path 共享一次 BGE-M3 embedding，维度/数值非法时 vector paths 统一失败 | embedding adapter | 计划含 vector | 最多一次 embedding |
| `DR-KRET-006` | 路径候选以 `(document_id,chunk_id)` 去重，RRF `sum(1/(60+rank))` | fusion | 召回结束 | 确定 fused candidates |
| `DR-KRET-007` | fused 候选仅调用一次 Rerank；结果索引完整唯一，排序为 rerank score desc、RRF desc、candidate ID asc | rerank/stage | fused 非空 | 稳定 top 20 |
| `DR-KRET-008` | 四路召回并发但共享 stage 绝对截止；取消后 await 清理并丢弃迟到结果 | stage | execute | 不超预算 |
| `DR-KRET-009` | 无 retry/cache/fallback index；子预算为 embedding 3s、单路 ES 5s、rerank 5s 与剩余预算较小值 | clients/stage | 依赖调用 | 避免重试乘法 |
| `DR-KRET-010` | stage 返回路径精确分区的 coverage，不自行判定部分成功 | stage | 汇总 | L2_01_00 唯一判定 |
| `DR-KRET-011` | batch 含证据身份/哈希/策略引用，不含出域 allow/deny 结论 | candidate contract | stage success | 下游可复核 |
| `DR-KRET-012` | 未知字段、非法候选、读决定不可验证、Rerank 非法结果均失败关闭并不携带原始响应 | 各边界 | 校验失败 | typed failure |

### 9.2 正常流程

1. 校验 plan 恰覆盖已选域的 keyword/vector，数量 2 或 4。
2. 冻结 stage deadline，如剩余≤100ms 直接 timeout，连网为 0。
3. plan 含 vector 时调用一次 BGE-M3，校验 1024 个 finite value。
4. 为每个 plan item 生成 typed ES 请求，以同一用户 JWT 并发调用。
5. ES service 先校验 token/Authority/domain policy，然后解析受控映射并查询 ES，仅返回 typed candidate。
6. 对成功路径按服务端 rank 构造 RRF；不跨路径比较 ES score。
7. fused 为空时返回 no-result coverage；否则使用查询和最多 80 个有界 content 调用一次 Rerank，`top_n` 必须等于本次 fused 候选数 `N`。
8. 校验 Rerank 完整索引并稳定排序，取前 20，统计每域候选数和 coverage。
9. 返回 `RetrievalStageSuccess(batch, coverage)`，Capability 只透传 batch 到 evidence stage。

### 9.3 RRF、去重与 Rerank 精确规则

- 路径顺序继承 plan ordinal；每路候选先校验 `sourceRank=1..N` 连续且身份唯一。
- 同一 chunk 在多路/多域出现时只保留一份正文；标题、正文、hash 或快照冲突即 `invalid_provider_result`，不任选一份。
- `rrf_score = Σ 1/(60+source_rank)`；不支持配置权重，避免个人验证项目引入调参平台。
- Rerank 请求候选按 `rrf_score desc, chunk_id asc` 编号 0..N-1，`top_n=N`。响应必须恰覆盖全部索引，不允许丢失、重复、越界或非 finite score；最终 batch 再截断为前 20 条。
- 最终排序先按 Rerank score，并以 RRF/chunk ID 打破平局；不使用供应商返回顺序作隐式 tie-breaker。

### 9.4 BGE 协议

Embedding 继承已核实的本地契约：

```json
POST http://127.0.0.1:8908/embed
{"texts":["查询文本"]}

200 {"dim":1024,"vectors":[[0.1,0.2]]}
```

Rerank 使用建议提供方契约，真实点测前不视为已存在：

```json
POST http://127.0.0.1:8909/rerank
{"model":"BAAI/bge-reranker-v2-m3","query":"...","documents":["..."],"top_n":1}

200 {"results":[{"index":0,"score":0.99}]}
```

Adapter 不含 API key，base URL 必须为组合根中冻结的 loopback HTTP 地址；不跟随重定向，不允许请求改 host/model。实际服务若与建议 Rerank wire contract 不同，只能修改 provider Adapter 与契约测试，不能改变统一候选或 stage 语义。

## 10. 失败、取消与安全

### 10.1 失败类型与调用方可见错误码矩阵

| 触发 | path/stage 结果 | 公共 stage code | 可重试 | 载荷 |
|---|---|---|---:|---|
| ES 边界返回 401 | path `failure` | `read_decision_unverifiable` | 否 | 无；正常情况下无效身份应已由核心在调用前拒绝 |
| role/domain 明确拒绝 | `forbidden` | `domain_forbidden` | 否 | 无 |
| 读权权威不可验证/失败 | `failure` | `read_authority_failure` | 否 | 无 |
| ES 无命中 | `no_result` | 无 | 否 | 空 candidates |
| 单路 ES/BGE timeout | path `timeout` | `retrieval_timeout` | 否 | 无 |
| 单路 ES 或 embedding 失败 | path `failure` | `retrieval_failure` | 否 | 无 |
| Rerank timeout | stage timeout | `rerank_timeout` | 否 | 无 |
| Rerank/候选结构非法 | stage failure | `invalid_provider_result` | 否 | 丢弃候选 |

任一已选整域 403 立即取消其他路径并返回 forbidden；读决定不可验证不得降为 no-result。部分路径技术失败时，stage 仍返回精确 coverage，是否继续仅由 `L2_01_00` 映射。

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
| `AGENT_KNOWLEDGE_EMBEDDING_BASE_URL` | `http://127.0.0.1:8908` | 仅 loopback，冻结 |
| `AGENT_KNOWLEDGE_RERANK_BASE_URL` | `http://127.0.0.1:8909` | 仅 loopback，冻结 |
| `AGENT_KNOWLEDGE_EMBEDDING_DIM` | `1024` | 必须 1024 |
| `AGENT_KNOWLEDGE_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | 精确值，不允许请求覆盖 |
| `AGENT_KNOWLEDGE_FINAL_CANDIDATES` | `20` | 3～20；只控制完整 Rerank 后的 batch 截断，不改变 `top_n=N` |

未知 `AGENT_KNOWLEDGE_ES_/EMBEDDING_/RERANK_` 前缀键启动失败。URL 不含凭证；JWT 仅来自请求 context。

### 11.2 Java 提供方配置

`es.query.knowledge` 建议包含 `enabled/profile-version/read-policy-version/domains.*.read-alias/category-filter/keyword-fields/vector-field/max-candidates/max-content-chars`。这些键只能在 ES 服务端冻结，Agent 请求不能覆盖。任一启用域缺 alias/filter/field/policy/version 则 ES 服务 readiness=false。

### 11.3 发布与回滚

- 先以 fake ES/BGE 完成 Python 契约，再在隔离环境部署 Java typed endpoint。
- 新 endpoint 不修改现有 generic endpoint 的 wire contract；对 Agent 客户端只暴露新 endpoint。
- 回滚时置 `AGENT_KNOWLEDGE_ENABLED=false` 并重启 Runtime；不回退为原始 DSL 调用。
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
| `IMPL-KRET-008` | 建议新增 | Java API/service | `es-query-api/src/main/java/com/dylan/esquery/api/knowledge/KnowledgeSearchRequest.java`、`KnowledgeSearchResponse.java`、`KnowledgeSearchCandidate.java`；`es-query-service/src/main/java/com/dylan/esquery/controller/KnowledgeSearchController.java` | request/response/candidate DTO；`search`；端点限定的 strict JSON deserializer | 新增狭只读契约 | 原契约不满足且不能影响通用端点 | `DR-KRET-002/005/012` |
| `IMPL-KRET-009` | 建议新增 | Java security | `es-query-service/src/main/java/com/dylan/esquery/service/KnowledgeReadAccessGuard.java` | `authorize` | 查询前 role/domain 读决定 | 正文前授权 | `DR-KRET-003/004/012` |
| `IMPL-KRET-010` | 建议新增 | Java retrieval | `es-query-service/src/main/java/com/dylan/esquery/service/KnowledgeSearchService.java` | `search` | 受控 mapping/DSL/typed candidate | 隐藏 ES | `DR-KRET-002/003/005/012` |
| `IMPL-KRET-011` | 建议新增 | Java config | `es-query-service/src/main/java/com/dylan/esquery/config/KnowledgeSearchProperties.java` | `es.query.knowledge.*` | 冻结域映射/上限 | 防请求选物理资源 | `DR-KRET-002/003/012` |

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
| `KnowledgeSearchController` | `ResponseEntity<KnowledgeSearchResponse> search(Authentication authentication, @Valid @RequestBody KnowledgeSearchRequest request)` | 已验证 Authentication + strict DTO | 200 typed；400/401/403/429/5xx | 只调 service |
| `KnowledgeReadAccessGuard` | `KnowledgeReadDecision authorize(Authentication authentication, String logicalDomainId)` | user token、有限 Authority、冻结 domain | allow decision；拒绝抛类型异常 | 无 ES 读；service |
| `KnowledgeSearchService` | `KnowledgeSearchResponse search(KnowledgeSearchRequest request, KnowledgeReadDecision decision)` | allow decision 与 domain 精确一致 | typed response；原始 ES 异常不穿透 | 一次只读 ES；controller |
| `KnowledgeSearchProperties` | `void afterPropertiesSet()` | 两域映射、字段、上限、版本 | 非法则阻止启动 | readiness |

## 13. 测试与验证设计

### 13.1 测试矩阵

| 测试编号 | 规则 | 层级 | 建议路径/用例 | 关键断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-KRET-001` | `DR-KRET-001/002` | Architecture/Unit | 建议新增：`agent-runtime/tests/architecture/test_knowledge_retrieval_boundaries.py` | Capability 无 HTTP/ES/BGE import；请求无物理资源 | 边界泄漏 |
| `TEST-KRET-002` | `DR-KRET-003/004` | Java Unit | 建议新增：`es-query-service/src/test/java/com/dylan/esquery/service/KnowledgeReadAccessGuardTest.java` | ADMIN/VIEWER allow；token/role/domain 非法 401/403、ES=0 | 未授权调用 ES |
| `TEST-KRET-003` | `DR-KRET-006/007` | Python Unit | 建议新增：`tests/unit/knowledge/retrieval/test_fusion.py` | RRF 公式、去重、冲突拒绝、tie-break 精确 | 顺序漂移/任选冲突 |
| `TEST-KRET-004` | `DR-KRET-005/009/012` | Contract | 建议新增：`tests/contract/knowledge/test_bge_embedding.py` | 一次调用、请求精确、维度/数值/超时负向 | 非法向量被接纳 |
| `TEST-KRET-005` | `DR-KRET-007/009/012` | Contract | 建议新增：`tests/contract/knowledge/test_bge_rerank.py` | model/query/documents/top_n=N；完整索引、finite score、超时 | 丢索引仍成功 |
| `TEST-KRET-006` | `DR-KRET-002/005/012` | Java Contract | 建议新增：`es-query-service/src/test/java/com/dylan/esquery/controller/KnowledgeSearchControllerContractTest.java` | strict DTO/response；域/path/大小/字段；无 raw JSON | 动态 DSL/未知字段 |
| `TEST-KRET-007` | `DR-KRET-003/004/012` | Integration with spies | 建议新增：`tests/integration/knowledge/test_authorization_before_content.py` | 拒绝/不可验证时 ES body/BGE/stage batch 均 0 | 正文先于授权 |
| `TEST-KRET-008` | `DR-KRET-010/012` | Parameterized Unit | 建议新增：`tests/unit/knowledge/retrieval/test_failure_coverage.py` | 四路状态精确分区；forbidden/读权失败优先 | 失败变 no_result |
| `TEST-KRET-009` | `DR-KRET-008/009` | Async Unit | 建议新增：`tests/unit/knowledge/retrieval/test_deadline_cancellation.py` | 子预算、最多调用数、取消 await、无 retry/迟到结果 | 后台继续/调用乘法 |
| `TEST-KRET-010` | `DR-KRET-011/012` | Contract | 建议新增：`tests/contract/knowledge/test_ranked_batch.py` | batch 身份/hash/policy/snapshot 完整；无 JWT/ACL/egress decision | 下游无法复核或越权决策 |

### 13.2 验证命令

| 验证编号 | 命令/步骤 | 范围 | 预期 | 当前状态 |
|---|---|---|---|---|
| `VAL-KRET-001` | `python -m pytest tests/unit/knowledge/retrieval tests/architecture/test_knowledge_retrieval_boundaries.py -q` | Python 纯逻辑/边界 | 全通过 | 未执行：代码不存在 |
| `VAL-KRET-002` | `python -m pytest tests/contract/knowledge/test_bge_embedding.py tests/contract/knowledge/test_bge_rerank.py -q` | 本地模型 wire contract | fake 先通过，opt-in 实例后记录真实证据 | 未执行 |
| `VAL-KRET-003` | `mvn -pl es-query-api,es-query-service -am test` | Java DTO/service/security/contract | 全通过 | 未执行：未授权代码 |
| `VAL-KRET-004` | opt-in 点测 `9200/8908/8909` 及维度/mapping/超时 | 真实检索 | 契约、维度、顺序均一致 | 2026-07-31 端口未运行 |
| `VAL-KRET-005` | ADMIN/VIEWER/missing/unknown/malformed/service-token 跨服务矩阵 | 授权先于正文 | allow 时 typed candidates；deny 时 ES/BGE=0 | 未执行；Authority 契约缺失 |

## 14. 风险、门禁与授权

### 14.1 风险与待确认

| 编号 | 类型 | 证据缺口/风险 | 触发 | 影响 | 处置 | 阻塞性 |
|---|---|---|---|---|---|---|
| `RISK-KRET-001` | 物理映射 | 当前 ES mapping 和 alias 快照未在线核实 | 真实检索 | 域错分/查询失败 | 门禁前导出 mapping/alias/count 证据 | 阻塞真实集成 |
| `RISK-KRET-002` | 读权 | 索引无已证明的同质读策略标记 | 返回正文 | 未授权泄露 | v1 只在整库同质证据后启用 | 阻塞真实集成 |
| `RISK-KRET-003` | Rerank 契约 | 8909 wire contract 未点测 | 实例调用 | Adapter 不兼容 | 隔离 PoC 后只修 provider Adapter 设计 | 阻塞真实 Rerank |
| `RISK-KRET-004` | 候选大小 | 80×4096 chars 可压力 Rerank | 双域全命中 | 延迟/内存 | 候选/正文/字节上限和 5s 超时 | 不阻塞 fake；需实测 |
| `RISK-KRET-005` | 效果 | 固定 RRF 参数和 Rerank topN 尚未代表最优效果 | P5 | 召回/答案质量不足 | `L2_01_02/SA-GATE-007` 评估，不在本文建调参平台 | 不阻塞链路设计 |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威 | 责任方 | 最晚阶段 | 验证方法 | 状态 | 未关闭允许/禁止 | 替代路径 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `KQ-GATE-002` | `slice_implementation` | `L2_01_01` 检索代码切片 | 实施 Python/Java 目标代码 | 本文独立评审通过、实施触点/测试/回滚明确、获得代码授权；涉及新公开契约另行确认 | 本文评审证据+授权 | 项目维护者/ES 提供方 | P3 前 | 独立评审+实施授权 | Open | 允许文档/fake；禁止目标代码和完成声明 | in-memory ES/BGE fakes |
| `SA-GATE-003` | `integration` | Knowledge 真实 ES/BGE | 启用真实 retrieval stage | typed endpoint、授权前置、物理映射、同质读策略、BGE 维度/Rerank 契约和负向测试全部通过 | ES mapping/manifest、Authority、provider PoC | 维护者/ES/BGE/安全方 | P4 前 | `VAL-KRET-003/004/005` | Open | 允许 fake；禁止真实正文进 Agent/BGE | synthetic candidates |

### 14.3 需要后续授权的动作

- 新增 `es-query-api` Knowledge DTO 和 `es-query-service` endpoint/security/service/config/test。
- 新增 Python Agent 代码、配置、测试及依赖。
- 真实访问 ES/BGE、修改公开契约、索引 mapping/reindex/alias 或 role converter。

## 15. 内部自检记录（作者内审）

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-31 | 0 | 5 | 6 | 11 | 0 | 结构、追踪、条件章节和建议新增证据已修复；严格校验首次清零 |
| 2 | 2026-07-31 | 0 | 2 | 2 | 4 | 0 | Rerank 全覆盖与候选空值/策略契约已对齐，无遗留 Major |
| 3 | 2026-07-31 | 0 | 0 | 3 | 3 | 0 | 错误映射、哈希和 scoped JSON 校验已收口，达到 Draft 内审停止条件 |

## 16. 实施前检查

- [x] 范围内 REQ/CON 已映射 DR、IMPL、TEST 和 VAL。
- [x] Python/Java/API/安全实施剖面和责任边界已区分。
- [x] 物理索引/DSL 不进入 Agent 契约，读取授权先于正文。
- [x] 多路召回、RRF、Rerank、截止、取消和失败语义明确。
- [x] 已存在、建议新增和待确认证据已分离。
- [x] 三轮作者内审已完成且无遗留 Blocker/Major。
- [x] `validate_detailed_design.py --strict` 通过。
- [ ] 独立评审和 `KQ-GATE-002` 实施授权完成。

## 17. 当前结论

本文当前为 Draft，只能支持详细设计评审和 fake 契约推演。真实 ES/BGE 检索、税务正文返回和目标代码实施均保持禁止，直至对应切片和集成门禁关闭。
