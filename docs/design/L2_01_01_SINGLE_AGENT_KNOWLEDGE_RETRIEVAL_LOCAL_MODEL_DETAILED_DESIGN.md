# [L2_01_01] 单体 Agent Knowledge 检索与本地模型接入详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_01` |
| 当前版本 | v3.0 |
| 日期 | 2026-09-14 |
| 权威范围 | Knowledge typed retrieval、两级 Profile、读取授权、本地 BGE，以及阶段 A 离线语料审计、资产处理、候选索引和受控发布 |
| 上位文档 | [`L1_01` v3.0](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 本次整理 | 统一文档基线v3.0；整合有效合同，归档历史过程；不改变代码、任务、配置或索引版本 |
| 实施状态 | 在线 typed retrieval、Java Provider、本地模型及阶段 A 离线语料流水线、结构化 legacy DOC 解析、candidate a5、alias 发布/回滚均已验证；具体状态由 P3/UAT_01 管理 |
| 归档来源 | [整理前 v2.21 原文](历史文档/2026-09-14-unified-v3-baseline/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md)；[完整性清单](../历史文档/2026-09-14-unified-v3-baseline/README.md) |

本文件纳入新的统一文档版本序列；v3.0不是软件、API、模型任务、配置或索引版本。原版本及字节归档见上表。评审状态、实施状态、部署状态和UAT状态分别判断；历史通过不自动覆盖新合同。

修订历史：2026-09-14，整理纳入统一文档基线v3.0；原版本、源提交及完整字节归档见上表。本次版本序列重置不是代码或设计回滚，评审、实施、部署和UAT状态分别管理。

本轮v3.0经三轮内审及两轮同一执行者的分层/跨层正式复核通过；仅证明文档整合，不表示新实现、部署或UAT已完成。完整发现与验证见本次归档MIGRATION.md。

## 2. 阅读导航

重点阅读§7/8公开typed/授权、§9目标检索、§12既有语料发布、§18资料组织合同。历次修订及旧评审只见归档；本v3.0整合已有有效合同，不新增能力。Knowledge新合同明确标记待实施，旧实现定义仅用于兼容与迁移，不作为第二套目标权威。

## 3. 目标与范围

### 3.1 目标

把关键词/向量检索、本地 embedding 和 rerank 封装在有限类型化边界后；Agent 只能提交逻辑域、stable Profile、路径、文本/向量和 limit，不能看到或控制索引、字段、DSL；正文只有读取授权成功后才返回。

### 3.2 范围内

- Python typed batch、并发 path 执行、RRF、去重和 rerank；
- ES Knowledge 专用 endpoint、DTO、严格 JSON、Profile/物理资源映射和读取授权；
- BGE-M3 embedding（8908）与 BAAI/bge-reranker-v2-m3（8909）HTTP 契约；
- 快照一致性、失败分类、超时、取消、配置和测试。
- 独立离线工具的全量盘点、受控下载、解析/OCR、结构化切片、embedding、候选索引和受控 alias 发布。

### 3.3 范围外与不负责

- 问题改写、域选择、证据、出域、摘要和 P5；
- 在线文档录入、用户上传和通用内容管理；
- 图谱、新语料导入、未评审的索引发布，以及公共DTO或权限扩张；§12.8仅为追加授权的政策向量表示增量；
- 知识图谱或新的在线服务；
- 通用 ES endpoint 的行为变化；
- 角色分配、模型训练、生产级重试/缓存/熔断。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-KRET-001` | 每个逻辑域执行 keyword+vector typed path，并返回统一授权候选 |
| `REQ-KRET-002` | Agent 不可指定物理索引、字段、过滤或 DSL |
| `REQ-KRET-003` | 读取授权先于正文返回，拒绝/权威失败不可被其他路径成功掩盖 |
| `REQ-KRET-004` | RRF 和 rerank 稳定、有界、可解释，快照不一致失败关闭 |
| `REQ-KRET-005` | Knowledge client 仅在 enabled 时创建，并由顶层 Runtime 在失败、取消和关闭时完整释放 |
| `REQ-KRET-006` | 官方正文/附件可追溯、不可变、可重放解析；失败资产隔离且不进入候选索引 |
| `REQ-KRET-007` | 只创建新候选索引，发布门禁后原子切换只读 alias，失败恢复精确旧目标 |
| `REQ-KRET-008` | 新索引同步 Profile、逻辑 snapshot 和文档出域绑定，保持读取授权与 Evidence 合同 |
| `REQ-KRET-009` | 审计分别陈述现行索引库存与官方来源可达性；来源不可达不得被改写成正文缺失或自动降级到非权威来源 |
| `REQ-KQUALITY-002` | 引用REQ_00：在既有合同内分别验证召回/融合/重排/Evidence损失，禁止gold、case ID或特定题目参与在线排序 |
| `REQ-KCORPUS-001` | 引用上位 REQ_00：官方来源、不可变 asset、三层审计事实和来源不可达不推断正文缺失 |
| `REQ-KCORPUS-002` | 引用上位 REQ_00：HTML/PDF/Office/表格/OCR 受控解析与不合格资产隔离 |
| `REQ-KCORPUS-003` | 引用上位 REQ_00：版本化 manifest、稳定关系、时效和父文档策略继承不得扩权 |
| `REQ-KCORPUS-004` | 引用上位 REQ_00：只创建候选索引，物理映射及 alias 发布由 es-query-service 边界治理 |
| `REQ-KCORPUS-005` | 引用上位 REQ_00：P0 全部、目标 P1、P2 全量盘点及阶段 B 分离的有限完成范围 |
| `REQ-KCORPUS-006` | 引用上位 REQ_00：发布前完整性、授权、Evidence、原子回滚和历史不可变 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-KRET-001` | `L0_00 §3/§5；SA-AD-004/006` |
| `CON-KRET-002` | `L1_01`：域→Profile 属于 Adapter，Profile→物理资源属于 es-query-service |
| `CON-KRET-003` | `L2_01_00`：输入是有序有限 Retrieval Plan，输出需精确 coverage |
| `CON-KRET-004` | 本地模型固定 BGE-M3 1024 维与 BAAI/bge-reranker-v2-m3 |
| `CON-KRET-005` | `REQ-KCORPUS-001～006`：P0 全部、目标 P1 全部、P2 全量盘点和有限处理 |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-KRET-001`、`CON-KRET-003` | `DR-KRET-001`、`DR-KRET-002`、`DR-KRET-003` | `IMPL-KRET-001`、`IMPL-KRET-002` | `TEST-KRET-001`、`TEST-KRET-002` | `VAL-KRET-001` |
| `REQ-KRET-002`、`CON-KRET-002` | `DR-KRET-004`、`DR-KRET-005` | `IMPL-KRET-003`、`IMPL-KRET-004` | `TEST-KRET-003`、`TEST-KRET-004` | `VAL-KRET-002` |
| `REQ-KRET-003`、`CON-KRET-001` | `DR-KRET-006`、`DR-KRET-007` | `IMPL-KRET-005`、`IMPL-KRET-006` | `TEST-KRET-005`、`TEST-KRET-006` | `VAL-KRET-003` |
| `REQ-KRET-004`、`CON-KRET-004` | `DR-KRET-008`、`DR-KRET-009`、`DR-KRET-010` | `IMPL-KRET-007`、`IMPL-KRET-008` | `TEST-KRET-007`、`TEST-KRET-008` | `VAL-KRET-004` |
| `REQ-KRET-005` | `DR-KRET-011`、`DR-KRET-012` | `IMPL-KRET-009` | `TEST-KRET-009` | `VAL-KRET-005` |
| `REQ-KRET-004`、`CON-KRET-004` | `DR-KRET-033` | `IMPL-KRET-021` | `TEST-KRET-028` | `VAL-KRET-014` |
| `REQ-KRET-003/004`、`CON-KRET-004` | `DR-KRET-034` | `IMPL-KRET-022` | `TEST-KRET-029` | `VAL-KRET-015` |
| `REQ-KRET-001/002/003/004`、`CON-KRET-002`；上位`REQ-KQUALITY-002` | `DR-KRET-035` | `IMPL-KRET-023` | `TEST-KRET-030` | `VAL-KRET-016` |
| `REQ-KRET-003/004`、`CON-KRET-004`；`REQ-KQUALITY-002` | `DR-KRET-036` | `IMPL-KRET-024` | `TEST-KRET-031` | `VAL-KRET-017` |
| `REQ-KRET-006`、`REQ-KRET-009`、`REQ-KCORPUS-001`、`REQ-KCORPUS-002`、`REQ-KCORPUS-003`、`REQ-KCORPUS-005`、`CON-KRET-005` | `DR-KRET-013`、`DR-KRET-014`、`DR-KRET-015`、`DR-KRET-016`、`DR-KRET-017`、`DR-KRET-018`、`DR-KRET-019`、`DR-KRET-020`、`DR-KRET-026` | `IMPL-KRET-010`、`IMPL-KRET-011`、`IMPL-KRET-012`、`IMPL-KRET-013` | `TEST-KRET-010`、`TEST-KRET-011`、`TEST-KRET-012`、`TEST-KRET-013`、`TEST-KRET-014`、`TEST-KRET-015`、`TEST-KRET-016`、`TEST-KRET-021` | `VAL-KRET-006` |
| `REQ-KRET-007`、`REQ-KRET-008`、`REQ-KCORPUS-004`、`REQ-KCORPUS-006` | `DR-KRET-021`、`DR-KRET-022`、`DR-KRET-023`、`DR-KRET-024`、`DR-KRET-025` | `IMPL-KRET-014`、`IMPL-KRET-015`、`IMPL-KRET-016` | `TEST-KRET-017`、`TEST-KRET-018`、`TEST-KRET-019`、`TEST-KRET-020` | `VAL-KRET-007` |
| `REQ-KRET-004`、`REQ-KRET-006`、`REQ-KRET-008`、`CON-KRET-004`；`KQ-AD-019` | `DR-KRET-030` | `IMPL-KRET-018` | `TEST-KRET-025` | `VAL-KRET-011` |
| `REQ-KRET-007/008`、`REQ-KCORPUS-003/004/006`；`KQ-AD-019` | `DR-KRET-031` | `IMPL-KRET-019` | `TEST-KRET-026` | `VAL-KRET-012` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| Retrieval Stage | 并发执行计划、融合、rerank、coverage | 改写、域选择、证据策略 |
| ES Adapter | typed HTTP、strict codec、候选标准化 | 物理 Profile 内容和读取规则 |
| Embedding Adapter | 文本→固定维度向量 | ES 检索、域策略 |
| Rerank Adapter | 有界 query/candidate→有序分数 | 新增候选、授权 |
| RRF | 跨路径去重与基于 rank 的融合 | 比较原始异构分数 |
| es-query-service endpoint | DTO、Profile、授权、ES 查询、候选映射 | Agent 查询策略、摘要 |
| Read Guard | 当前主体对 Profile/正文的读取允许 | 文档模型出域 |
| Offline Corpus Tool | 审计、获取、解析、切片、embedding、候选写入和发布命令 | 用户请求、在线域选择/排序、权限判断、公共 API |
| Asset Workspace | 保存不可变原始资产、解析产物、隔离件与 manifest | 作为在线正文服务或 Git 大文件仓库 |
| Release Controller | 校验候选、精确记录 alias 旧目标、原子切换和回滚 | 删除旧索引、放宽 Profile/读取/出域策略 |

依赖方向为 `Knowledge Capability → Retrieval Protocol ← Python adapters → typed Knowledge endpoint → ES`。禁止 Agent 调用通用 ES DSL endpoint；禁止 es-query-service 反向依赖 Agent；禁止本地模型接收未授权正文。

拆分按协议和物理资源权威形成稳定契约，不新增 knowledge-service 或通用检索平台。

## 6. 当前实现基线与迁移

最小变更原则：本轮仅整合已批准合同与迁移边界，不新增实现、依赖或质量策略。当前实现与待实施目标分别标识；不能将旧验证移作新合同通过。

现代码仍为quality-v3，保留既有typed HTTP、BGE、来源/授权、阶段A发布及向量表示能力。目标§9替换需求驱动重排、锚点、配额和跨查询分数策略，§18为尚未实施的资料组织合同；本轮不改实现、配置、索引或alias。已发布快照与历史效果只在原UAT范围有效，仓库绑定不等于部署证明。

## 7. Python 与 HTTP 接口契约设计

### 7.1 设计规则目录

| 规则编号 | 规则 |
|---|---|
| `DR-KRET-001` | 每个 plan item 精确执行一次；vector 路径先 embedding 再 typed ES search |
| `DR-KRET-002` | path 结果只允许 candidates/no_result/forbidden/timeout/failure；failure 进一步限定为读取决定不可验证、读取权威失败、检索失败或 provider 响应非法，HTTP 429 收敛为检索失败 |
| `DR-KRET-003` | coverage 必须记录每个计划 path 的唯一终态和每域 candidate count |
| `DR-KRET-004` | HTTP 请求只含 schemaVersion/domain/profile/path/queryText/queryVector?/limit |
| `DR-KRET-005` | Profile→alias/index/fields/filter/source mapping 只在 es-query-service 配置中解析 |
| `DR-KRET-006` | Read Guard 在 Service 查询和正文返回前完成；用户 JWT 透传且不回退服务身份 |
| `DR-KRET-007` | 任何返回候选均携带授权/快照/策略所需元数据且严格解码 |
| `DR-KRET-008` | RRF 使用 `1/(60+rank)`，按 `(documentId, chunkId)` 去重并检测内容冲突 |
| `DR-KRET-009` | rerank 只处理融合后的有界授权候选；分数非有限、重复、缺失或越界失败 |
| `DR-KRET-010` | 同一逻辑域/Profile 的所有成功 path 必须返回一致的 profileVersion、indexSnapshotId、readPolicyVersion；不同域可各有一个冻结 snapshot，任一域内不一致失败关闭 |
| `DR-KRET-011` | 生产组合根只为 es-query-service、Embedding、Rerank 三个已验证 origin 创建 bounded client；Capability/Stage 不拥有 client 生命周期 |
| `DR-KRET-012` | disabled 时 client 创建次数为 0；所有非资源校验先于 client 创建；已装配 Runtime 取消或关闭时所有 owned client 至多关闭一次且尽力全部释放 |
| `DR-KRET-013` | 离线来源只允许版本化政府域 allowlist，redirect 每跳复核并拒绝私网/IP literal/异常 URL |
| `DR-KRET-014` | 下载必须校验 HTTP、大小、MIME、signature 和单资产上限；默认不重试，不执行附件内容 |
| `DR-KRET-015` | OOXML/ZIP 先执行路径、条目数、解压量、单文件、压缩比、加密与嵌套压缩安全校验 |
| `DR-KRET-016` | HTML/PDF/DOC/DOCX/XLS/XLSX 使用固定 parser；必要 OCR 必须标记页码与质量状态 |
| `DR-KRET-017` | 表格保留 sheet/table、行列顺序、合并关系和单元格文本，禁止执行公式/宏/外部连接 |
| `DR-KRET-018` | 解析输出是绑定原 asset hash 的不可变 ordered blocks；空白、截断、损坏或不合格资产隔离 |
| `DR-KRET-019` | 标题/章节/条款/表格感知切片必须稳定、有界、可重放并检测 identity 冲突 |
| `DR-KRET-020` | 附件沿用父 document 读取/出域边界；新官方父文档只能显式复用既有同域 policy 且不得扩权 |
| `DR-KRET-021` | embedding 仅调用当前 loopback BGE，输出必须恰好 1024 个有限数，失败 chunk 不写入 |
| `DR-KRET-022` | 候选必须是精确命名的新索引，拒绝现行目标、已存在索引和非 allowlist 名称 |
| `DR-KRET-023` | mapping v2 只增加内部溯源字段，保持现有 typed source fields 与公共 DTO 不变 |
| `DR-KRET-024` | 发布生成新 policy/law snapshot 与当前 catalog；全成员、Profile、UUID、mapping/hash 一致后才可生效 |
| `DR-KRET-025` | alias 以精确旧目标为前置执行原子切换、冒烟、原子回滚演练和最终切换；不删除旧索引 |
| `DR-KRET-030` | §12.8纯构造同记录title/section/content的版本化向量输入，严格类型/大小/哈希，原文和既有builder不变，不执行I/O |
| `DR-KRET-031` | §12.9只克隆精确只读源，替换policy受控附件的embedding和独立表示元数据；全记录原文/权限及其余向量保持，失败封存不发布 |
| `DR-KRET-033` | §9.6启动期一次合成重排预热，失败不启动新的Knowledge调用方；不重试用户请求、不放宽在线deadline |
| `DR-KRET-034` | §9.7仅以现有授权候选的正文、标题、文号和成文日期评分；派生表示不是Evidence，当前根固定单一版本，失败不回退正文评分 |
| `DR-KRET-035` | §9.8可关闭的有界文号词法/空格等价软匹配，固定category和单次keyword请求；未知标识不猜测、ES失败不重试、公共DTO和索引不变 |
| `DR-KRET-036` | 旧测试侧离线窗口诊断编号保留，完整方法见归档；不是目标窗口/阈值的实施要求，新表示对照按DR-KRET-306/307 |
| `DR-KRET-026` | 审计把索引库存、来源可达性和正文完整性作为三个独立状态；非 200/网络失败只产生有限 source status，不推断正文缺失，不自动重试或转用非权威来源 |

### 7.2 Python 内部类型

`KnowledgePathRequest`：logical domain、retrieval profile、path、query text、optional vector、limit。`AuthorizedKnowledgeCandidate`：document/chunk ID、domain、title/content/source metadata、source rank、content SHA-256、policy ref、profile/index/read-policy snapshot metadata。

`RankedKnowledgeBatch`仍只包含最终有序候选、统一profile version与snapshot集合。阶段B排序版本显式记录在内部配置；内部候选可增加可信`retrieval_anchor`标记（默认false保持旧显式装配兼容），不能接受模型/HTTP注入。连续rank代表最终确定性顺序，不再宣称全局BGE分数降序。path truncated表示窗口边界，不代表物理语料全覆盖。

### 7.3 Knowledge HTTP 请求

`POST /es/knowledge/search`

```json
{
  "schemaVersion": 1,
  "logicalDomainId": "tax.policy",
  "retrievalProfileId": "tax.policy.keyword.v1",
  "path": "keyword",
  "queryText": "...",
  "queryVector": null,
  "limit": 20
}
```

- keyword：`queryVector=null`；vector：维度 exact 1024 且值有限。
- 未知字段、重复 key、错误类型、超界文本/limit、路径与 vector 组合错误均 400。
- 请求不得出现 index、alias、field、filter、DSL、source fields 或管理选项。

### 7.4 HTTP 响应

响应含 schema/domain/profile/path、`profileVersion`、`indexSnapshotId`、`readPolicyVersion`、truncated 和 candidates。candidate 字段固定为 document/chunk/domain/title/content/source URL/document number/written date/material type/source rank/content hash/policy ref。

额外字段、重复候选、sourceRank 非 1..n、domain/profile/path 回显不一致、hash 格式错误、正文/文本超界均为 invalid provider result。

## 8. 两级 Profile、读取授权与 ES

### 8.1 两级映射

```text
Agent: logicalDomainId + path → retrievalProfileId
es-query-service: retrievalProfileId → read alias/index snapshot/fields/category filter/source mapping
```

Agent 只持有 stable Profile ID 和 expected profile version=`tax-knowledge-search-v1`。Java `KnowledgeSearchProperties.requireProfile(domain, profile)` 必须同时匹配 domain/profile、version、read policy、alias/index UUID/mapping/index snapshot 和字段目录。

### 8.2 启动验证

当 endpoint enabled 时，`KnowledgeProfileVerifier.afterSingletonsInstantiated()` 对配置 Profile 与 ES read alias 的当前 index name/UUID/mapping metadata 做只读验证；不匹配则服务不 ready/启动失败，不自动修改 alias 或 mapping。

### 8.3 读取授权

`KnowledgeReadAccessGuard.authorize(authentication, logicalDomainId, profile)`：

- 只接受 user token 的 `ROLE_ADMIN/ROLE_VIEWER`；
- 生成有限 `KnowledgeReadDecision`，绑定 domain/profile/read-policy version；
- missing/malformed/service token→401，角色不足→403，权威不可用→503/有限错误；
- 只有允许决定才调用 ES 并返回正文。

读取权限不等于模型出域权限；`policyRef` 仅供 Evidence 阶段进一步收紧。

### 8.4 ES 查询

Service只根据冻结Profile构造keyword/vector query，附加category filter与_source allowlist，limit≤20。两种路径都必须显式设置ES `size=limit+1`；vector同时设置`k=limit+1`，num_candidates保持原上限100。返回额外一条仅供truncated计算，最多映射limit条。修复当前vector缺少size导致默认少返与truncated假阴性，不扩大请求/响应DTO、Profile上限或索引能力。

## 9. 最小检索策略（新设计，未实施）

依据REQ-KQ-204/205及KQ-AD-021/022/024；本节整合原§18目标，替代归档原§9.1～9.4、DR-KRET-027～029/037的旧质量编排，不替代typed请求、授权、快照/完整性、单次调用、取消或阶段A离线合同。旧实现和诊断保持原证明范围；本设计不迁移索引。

### 9.1 有界检索与确定性排名

`DR-KRET-201`：只消费L2_01_00 §8通过校验的knowledge-minimal-v1计划。每域keyword、vector各一次，全部使用同一安全原问Q；只在请求内计算一次1024维有限向量，由两域复用。每路limit=20；ES既有多取一项仅用于truncated标记，不扩大返回窗口。至多4次search/1次embedding，无兜底轮询或额外文档读取。固定Profile/alias/服务DTO、Java文号开关及当前映射不变。

每个非空域对该域已授权候选按既有identity去重/RRF（k=60）排序，最多40项；相同identity跨路径或域存在内容/hash/策略冲突时全请求失败，不选择更高分版本。源身份、路径、域和快照一直保留，不允许先按分数过滤后跳过完整性检查。

`DR-KRET-202`：每个非空域调用一次现有RerankPort，query=Q、≤40项，按目录顺序串行，最多2次、总≤80项评分；不再按模型requirements/focus重复评分。沿用当前authorized-body-first-metadata-v1输入表示及本地512token窗口，未声称能看到完整长正文；原候选正文不可被评分文本替换。

域内按rerank分降序→RRF降序→chunk_id→document_id确定性排列。严格检查候选索引全集/唯一、有限分数及当前适配器归一化合同。域间按固定目录次序round-robin，每次取下一未见identity，重复项合并其已核验域来源，直到20项或队列耗尽；不比较不同域池裸分、不添加keyword首位/证明锚点、文档配额或特定ID加分。轮转仅保留域进入窗口的机会，不代表该域首位相关或充分。

新策略不调用现有quality-v3需求标签逻辑，也不把旧coverage_anchor补成true。拟新增`agent-runtime/src/agent_runtime/knowledge/retrieval/minimal_ranking.py`，复用fusion与RerankPort；旧quality_ranking*.py保持历史调用方，后续单独查引用再清理。

### 9.2 失败、预算和生命周期

`DR-KRET-203`：所有选中域读取拒绝遵循现有安全优先，取消未完成分支并join；不得继续用另一个域掩盖拒绝。完整性或快照冲突不降级为partial。普通技术单路失败仅按既有coverage/每域候选与总候选最小阈值判断是否继续；全路失败、必要域无成功路径、rerank非法/失败为downstream_failure，Summary0。只有完整成功且候选全空才能no_candidate。部分继续保留failedPaths及retrievalComplete=false，不追加路径。

请求retrieval总deadline20秒、每个HTTP阶段≤5秒；每次启动前检查剩余时间，超时/取消后不接收迟到结果，不启动下一域/阶段；retry=0。owned search/embedding/rerank client仍由Runtime关闭，不增加新连接池或跨请求向量缓存。合成预热与在线预算分开，不能把真实冷启动超时改判检索无结果。

### 9.3 索引、向量及评分策略的比较边界

`DR-KRET-204`：首期原问策略在现有binding v2指定的语料/向量配置上建立新基线，不认为body-only或context向量天然更优。仓库binding证明预期配置，不证明运行实例实际alias；后续真实测量前只读核对UUID、Profile和policy快照。代码、模型、向量/语料、服务部署四类基线独立记录；一类变化不能由另一类Git回滚自动完成。

后续比较body-only/context、query改写、窗口或阈值时，每次只改变一个变量。使用同一公开原文身份/hash、切片、候选评价集合、模型配置、读取策略；同模型同参数下比较必要来源Recall/MRR、噪声及Evidence覆盖。若索引不同，先证明两者只有预定向量表示不同，不能混入语料补齐或mapping变更；做不到则不称因果比较。保持已发布索引只读，不自动重建或切alias。任何需要实际索引/模型迁移的后续实验须另获明确目标授权，不在本实施首期隐含执行。

### 9.4 实施追踪与回滚

#### 新设计编号定义

| 需求编号 | 规则编号 | 实现编号 | 测试编号 | 验证编号 | 定义位置与状态 |
|---|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KRET-201、DR-KRET-202、DR-KRET-203、DR-KRET-204 | IMPL-KRET-201、IMPL-KRET-202、IMPL-KRET-203 | TEST-KRET-201、TEST-KRET-202、TEST-KRET-203 | VAL-KRET-201、VAL-KRET-202、VAL-KRET-203 | 需求定义见REQ_00 §5.2；本节前述条款和下表逐项展开；全部待实施验证 |

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KRET-201 | IMPL-KRET-201：retrieval/stage.py读取新计划；es_adapter.py、bge_embedding.py端口复用、不改公共DTO | TEST-KRET-201：原问一致、最多4search/1embedding、只启用域、授权/快照拒绝和零后续 | VAL-KRET-201：unit/contract/fake集成 |
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KRET-202、DR-KRET-203 | IMPL-KRET-202：minimal_ranking.py、stage.py；provider.py继续当前BGE表示 | TEST-KRET-202：同分、跨域重复/冲突、无需求锚点、≤2rerank/80评分、失败/超时/取消、无gold导入 | VAL-KRET-202：定向、类型及current-root回归 |
| REQ-KQ-201、REQ-KQ-202、REQ-KQ-203、REQ-KQ-204、REQ-KQ-205 | DR-KRET-204 | IMPL-KRET-203：后续tests/evaluation/knowledge中的独立同池比较及有限快照记录；本目标无代码资产 | TEST-KRET-203：不同语料/配置不得成对计分、缺标注为null、历史hash不变 | VAL-KRET-203：离线反例及后续只读服务验证，不能由fake证明真实召回 |

仅Knowledge成对代码绑定迁移；检索部署前需功能、安全、typed Java及Business防回退通过。回滚为禁用Knowledge或恢复整套相容的代码/任务/配置绑定；不更改索引/alias，旧StageA原文及发布回滚证据保持不变。取消父配额/锚点/0.5为质量策略重新设计，不放宽读取授权、源完整性或原文引用；保留噪声和必要来源排在top20之外的效果风险，按UAT_01 §15验证。


### 9.5 BGE-M3 Embedding

- endpoint 默认 loopback `http://127.0.0.1:8908`；
- 目标输入仅通过安全校验的原问题Q，UTF-8/字节有界；旧实现使用对应冻结rewrite文本；
- 输出 exact 1024 个有限 float，禁止 NaN/Infinity/字符串 coercion；
- 每个请求的同一 query 可在请求内复用一次向量，不跨请求缓存。


### 9.6 本地重排启动预热（DR-KRET-033；增量评审通过，实施状态见P3）

端口与`/health`正常只证明服务可达。冷实例模型/GPU初始化可能使首次推理超过在线5秒，不能据此提高在线时限、删除候选或增加查询重试。采用一次显式启动检查，不建设定时探针、缓存或额外在线流程。

- **触发与所有权**：serviceCenter在显式启用Knowledge时、Python环境准备完成后且启动新的服务进程前执行；`PlanOnly`及Knowledge disabled不调用。`SkipInfrastructureCheck`仅跳过TCP盘点，不跳过推理预热。手工启动/本地验证入口使用同一独立工具。Runtime在线对象图不导入它，不自动预热、不改变ready公共响应。
- **固定输入与端点**：仅向loopback `127.0.0.1:8909/rerank`发送一次POST，40条各4096字符的代码内合成文本、固定非业务query、`top_n=40`、`normalize=true`。不访问ES/embedding/LLM/业务服务，不读Key/JWT/问题/正文；不允许endpoint或输入参数覆盖。
- **边界**：启动预热绝对时限30秒，响应上限2MiB，不使用环境代理、重定向或重试；严格校验200、JSON/identity、UTF-8、无重复/未知key、模型名、完整40项唯一整数index（拒绝bool）、精确合成text回显和有限数值score（拒绝bool）。任何失败关闭连接、返回非零退出码，启动器不启动新的服务。该30秒只属于运维合成检查，在线rerank仍5秒、stage仍20秒。
- **观测与失效**：只输出有限status、耗时、数量、contract判定；不输出响应或环境。单操作人启动窗口，不承诺其他客户端并发下的性能SLA；检查后BGE被重启/换模型则原就绪证据失效。下游在客户端超时后可能继续计算，工具不再次请求，也不停止用户拥有的BGE进程。
- **兼容与验证**：不新增配置项/依赖、修改模型服务或公共DTO；仅新增运维工具并接入启动脚本。fake覆盖错模型、重复/缺失index、非法数值、超限、错误状态/类型、超时及零重试；实际冷实例验证与当前服务检查分别记录，不把合成预热计为UAT或原文排序通过。新诊断的启动预算单列rerank=1，不能偷偷注入已冻结或已消费的历史runner，也不赋予重跑失败case或追加付费批次的权限。


### 9.7 授权上下文评分表示（DR-KRET-034；已实施，验证证据见P3）

已召回短条款在单独评分时可能缺少同文档语境；有限配对依据由P3/UAT管理。采用固定`authorized-body-first-metadata-v1`，保留既有评分表示，不改原文、final20、Evidence8或检索窗口；目标排名由§9.1决定，不沿用旧需求锚点。表示仅用于本地BGE评分，不是新正文，也不证明法律适用性。

1. 输入只来自Stage已通过读取授权、快照及完整性校验的`AuthorizedKnowledgeCandidate`。先放原始content，再依次追加非空title、document_number、written_date，行标签固定为`文档标题：`、`文号：`、`成文日期（非生效日期）：`，日期ISO。content≤4096且不截断；title/document_number各≤256，总表示≤4700字符。无元数据时只保留原文；不补值、不读私有section/邻居/URL、不生成摘要或事实。标题/日期仍是不可信来源信息，不能用成文日期判断有效/废止；模型512 token窗口不变，长文可能看不到尾部元数据。
2. 新`ContextualBgeRerankAdapter`一次调用现有`/rerank`，query不变、documents为上述表示、top_n等于候选数、normalize=true；候选数1..40。沿既有5秒/2MiB/取消合同，检查JSON无重复/额外key、模型名、完整唯一整数index、派生表示exact echo和有限score；错误、超时、取消均失败，不重新以raw评分。不得伪造响应text或改candidate.content/hash来复用旧校验。
3. 返回仍为`tuple[RerankScore,...]`；ranker、候选及SHA、Evidence正文和外部模型载荷仍为原授权对象。观测继续隐藏rerank query/documents，只保留计数，不把新元数据加入公开诊断。目标按§9.1每个非空域一次，共≤2次/80个评分；旧实现每需求≤4次/160评分仅归档兼容，不进入目标计划。不得运行在线实验双臂或额外模型。
4. 旧`bge_rerank.py`承担历史兼容，字节不改。`LocalKnowledgeRetrievalFactory.build`新增内部参数`rerank_input_version`，省略时保持`raw-content-v1`供既有显式历史/测试调用；仅接受该值和新版本，其余在transport调用前拒绝。components.rerank类型改为既有RerankPort。`main.build_runtime`在enabled分支显式选新版本，disabled仍零资源；无环境/请求切换、自动后备或第二生产链路。版本常量及文件SHA进入后续运行快照，旧manifest不能证明新表示。
5. 当前根non-live、HTTP和类型回归通过后才可采用。新旧Adapter独立保留必要协议校验以保护冻结源，不建设通用转换框架。回滚部署此前完整代码或禁用Knowledge，不改policy/index/alias、历史或读取权限。当前原文数据不足以表达的语义仍须失败关闭。

`TEST-KRET-029`：单次HTTP、格式/边界、wrong echo/model/index/score、重复JSON、取消/超时、原文/hash不变、拒绝零BGE、当前根唯一绑定、旧factory默认和未知版本拒绝、观测无正文或元数据；合成输入下与已测实验表示/分数一致。实验代码不得成为生产依赖。真实Rewrite/Summary、引用及usefulness仍独立验收。


### 9.8 文号元数据软匹配（DR-KRET-035；代码及仓库live Profile已配置，部署须另核实）

**根因和方案选择**：现有`documentNo`为keyword，完整元数据可定位但与问题空格表示不一致；整句multi_match追加该字段不能解决此缺口。只改Prompt不能补齐服务字段行为；只扩大窗口增加噪声和成本；立即新增归一字段/候选索引涉及全记录迁移。优先采用可关闭的服务内部`document-number-whitespace-v1`，原文/向量/索引不动。若此方案在有限语法、错误机关反证或真实耗时上不能通过，则停止启用，另行评审规范化元数据候选索引，不继续堆叠规则。

1. **责任**：`KnowledgeSearchService`在既有读取决策核验后、一次keyword ES请求内构造可选文号加分子句。输入仍为当前`queryText`；只做文件标识词法及固定物理映射，不选择domain、action、query、requirement，不补用户条件、法律事实或模型计划。Agent/Rewrite/公共DTO不知道物理字段和表达式；向量路径完全不变。
2. **有限词法**：仅接受完整`机关〔YYYY〕N号`、`机关[YYYY]N号`、`机关公告YYYY年第N号`。输入沿公开合同≤1024 Unicode码点；机关由汉字/ASCII字母及ASCII或全角空格构成，去空格后2..48字符；年份4位ASCII数字、编号1..12位，保留大小写、前导零、成对括号种类及地域机关。允许从机关开头剥离一次明确查阅前缀（与当前Guard的请/帮我/麻烦、分别/同时、查询/查找/检索/查阅/查看/对比/比较同一有限语法）；不做同义机关推断，不从超长机关末尾截取一个短机关。
3. **列举**：完整文号后紧邻`、/和/与/或/以及`及可选空格时，下一项若只有同一格式的`YYYY年第N号`或`〔YYYY〕N号/[YYYY]N号`，只继承紧邻的完整机关和公告标记，年份/编号必须显式存在。不同完整机关分别保留；不跨句、跨任意文字借用机关，不补年份、不去掉地域。稳定去重后最多4项，单项规范形式≤80字符；任何已识别项超限则整项额外匹配关闭，不截取前4项。无法识别的简写不继承，已独立识别的完整项可保留软匹配，原全文始终保留所有条件。该行为不证明所有文号或问题已理解；最终仍由原问题及引用校验控制。

   **完整标识边界补充**：一个完整文号已经结束时，其结束位置是后续独立完整文号扫描的合法起点。因此两个完整文号只以ASCII/全角空格分隔（去空格后直接相邻）也应分别识别；后项必须自己含完整机关及年号，不从前项借机关。实现将搜索区域起点移至已消费位置，让前项末字不再参与后项的负向边界判断；不得对任意汉字位置逐字符重试，以免从超长或错误机关中抽取后缀。已有紧邻连接词简写规则不扩展：空格/逗号不能用于简写继承，夹有任意说明文字时不推断后面的机关；词法无法正确识别的部分仍只依靠原全文查询，不新增请求或fallback。作用域仍为`DocumentNumberQuery.patterns(String)`与直接测试，公共DTO、调用方、Profile开关、boost及regex上限不变。此局部修正已实施并通过non-live验证，不证明真实模型曾输出这种表达或全部双文号问题已解决；未以本地编译冒称运行中服务已升级。
4. **ES形状**：将已验证的字符逐一转义，以`[ 　]*`连接，只允许空格差异，不生成通配`.*`或接受用户正则。每项表达式≤900字符，`flags=NONE`、`case_insensitive=false`、`max_determinized_states=256`；只使用Profile的`source-fields.document-number`。元数据项OR合并为一个constant_score子句，固定boost=100；它与原multi_match按should/minimum_should_match=1合并，category过滤始终在最外层。不是文号硬过滤：提到某文件的跨域查询仍可返回同域其他相关原文。该固定加分不是相关性或法律有效性证明，也不保证任意索引的首位；不得配置任意权重、gold、case ID或目标文档ID。
5. **配置与启动**：Profile私有服务布尔`document-number-matching`的类型默认仍为false且初始化后冻结。开启时Verifier要求document-number字段为keyword/constant_keyword，不能显式`index=false`或设置normalizer（避免大小写等隐式等价）；旧false Profile保持原mapping兼容。隔离typed同快照对照、完整相关性及非文号/错误机关反证完成后，当前`application-knowledge-live.yml`仅对tax-policy-v1显式设为true；tax-law-v1及普通application.yml默认disabled行为不变。启用依据、运行部署和回滚状态由P3/UAT管理，不能以fake或代码配置变更冒称运行中服务已升级。索引snapshot仍标识同一物理内容，源码和配置hash共同标识检索行为，不伪称旧manifest证明新查询。
6. **失败和运维**：未知词法只是不采用可选信号，不是失败后再查；已发ES请求失败沿原异常映射，不能移除子句重试或扩大域。集群禁止昂贵查询时regex会失败，不自动修改集群设置；启用前必须在当前环境测量。现有请求/响应大小、超时、limit+1哨兵、最终top20及返回字段不变；无额外HTTP、缓存、线程、依赖和日志。关闭开关/部署原代码即回滚，不写alias/index或旧资产。

`TEST-KRET-030`：合成不同机关/年号/括号/前导零、单/多文号、紧邻简写、非紧邻不继承、查阅前缀、歧义/超限/注入、不可变/并发；启用/禁用/无文号/vector查询形状、category不可绕过、单次HTTP、授权失败零调用、ES拒绝零重试、mapping不兼容启动拒绝和冻结开关。不能仅断言生成了字符串，需验证目标匹配与错误机关不匹配。

边界增补用例：同/不同机关两个完整文号以空格、全角空格或零间距相邻，两个目标均匹配；混合legacy/announcement、四项及第五项超限；第二项超长机关不得后缀命中；完整文号后裸年号/任意文字加简写仍不继承。服务测试检查同一keyword请求中两个正确metadata OR项及原multi_match/category保留，而非仅验证纯函数数量。先证明旧代码失败，再实施修正并执行上述Java合同/授权回归、当前Python历史与UAT追踪；不以合成测试代替真实效果。

`VAL-KRET-016`：先新Java纯函数/查询形状/mapping/安全测试，再相关Maven与当前Python基线/历史回归；随后保持原24题/gold/index，执行预先绑定源码和开关的隔离typed对照，文号召回增益与非文号回退分别报告。原相关性分级按整理前L2_01_02 §13.8追溯；目标四维比较由当前L2_01_02 §9.4及UAT_01 §15治理，未标注Precision/nDCG仍为null；本切片不证明整体效果或放行付费运行。

接受限制：标识词法不是机关知识库，不能证明任意前缀、别名或法律身份；同一文号很多chunk仍可能占满窗口，此增量不承诺多文档Evidence完整。精确标识可选加分不参与合法性、时效或摘要充分性判定。已知缺口和错误机关/长文号/非文号反证必须进入对照，而不是为此追加循环Gate或逐题规则。

## 10. 并发、核心处理流程、错误分类与一致性

目标使用§9.1/9.2；旧quality-v3的每需求重排不进入新主线。授权、失败与生命周期不变。

- Stage为每个计划item建立有界任务；对唯一原Q执行embedding（最多1次）再并发执行最多4次search，query→vector请求内映射，禁止错用第一域向量。所有路径完成并通过授权优先级检查后，按目录顺序串行执行每域最多1次rerank（共≤2次），每次调用前检查剩余deadline，不延长阶段时限；任何技术/授权失败不触发新域/新query。
- cancellation/deadline 传播到全部 transport；任一并发 path 异常或阶段失败时取消并 join 未完成任务。
- 整域 forbidden/authority failure 是安全失败，不能用另一 path/domain 的 success 降级。
- rate limit、timeout、provider failure 是技术失败，由 L2_01_00 coverage 规则决定是否部分继续。
- Profile/index snapshot 在所有成功 path 间必须一致；任何成员缺失或冲突使整批失败。
- 无重试、resume、跨请求 cache 或数据库事务；候选只驻留请求内存。
- 三个 origin 使用独立 bounded `httpx.AsyncClient`；它们由顶层 Runtime lifecycle 统一关闭。关闭一个资源失败不能阻止尝试关闭其余 Knowledge/Business/model 资源。

## 11. 权限、安全、审计与日志

- JWT 只在 ES Knowledge Client outbound header 中揭示；BGE 不接收 JWT、用户身份或文档策略。
- BGE rerank 接收已授权的有限正文，这是本地 loopback 处理，不是外部模型出域。
- 日志只记录域/profile/path、snapshot ID、候选数、truncated、失败类别和耗时；不得记录 JWT、query、vector、正文、标题或原始响应。
- Java endpoint 使用专用 SecurityFilterChain；原通用 ES endpoint 认证/授权和错误行为不变。

## 12. 配置、数据生命周期、发布与回滚

| Python 配置 | 固定/边界 |
|---|---|
| ES base URL | Knowledge enabled 时必需；合法 origin |
| profile version | exact `tax-knowledge-search-v1` |
| embedding/rerank URL | loopback only，默认 8908/8909 |
| embedding dimension | exact 1024 |
| rerank model | exact `BAAI/bge-reranker-v2-m3` |
| final candidates | 3..20；阶段 B 还须≥2×已启用域数，否则启动失败，不能由运行时静默裁掉锚点 |

Java endpoint 默认 disabled；启用时全部 Profile 必须完整并通过 alias/index snapshot 校验。在线请求不修改 mapping、alias、索引或正文；阶段 A 的离线发布只能在本节定义的精确候选和发布门禁内执行。在线回滚仍可禁用 endpoint/Knowledge action；语料回滚恢复 alias 的精确旧目标，不迁移 Agent 数据。

Python Runtime 的 Knowledge 开关与 Java endpoint 开关独立：Python disabled 不要求 Java 就绪；Python enabled 只在本地启动校验通过后 ready，运行时 Java 503/授权权威失败仍按 typed failure 失败关闭，不回退通用 ES endpoint。

### 12.1 离线工具与 workspace

`knowledge-corpus-tools` 是项目级 Python CLI，不是生产服务，不注册 `knowledge.query`，也不被 `agent-runtime` 导入。所有有状态命令必须显式接收一个已解析的绝对 workspace；生产运行不得隐含使用仓库目录、用户主目录或全局临时目录。workspace 固定分区：`raw/` 保存不可变原始资产，`parsed/` 保存规范解析结果，`manifests/` 保存严格 JSON/JSONL，`quarantine/` 保存失败件和有限原因，`runs/` 保存候选构建及发布记录。Git 只保存代码、Schema、hash、有限报告和小型合规 fixture。

### 12.2 审计与 asset manifest

每个文档审计项必须包含稳定 `documentId`、文号/标题/机关、发布/生效/失效日期、逻辑域、官方来源、正文状态、附件清单、父子关系、当前索引覆盖、Profile/index 版本、优先级和有限失败原因。审计分为三个互不替代的事实层：

1. **现行索引库存**：只依据只读 ES 导出记录文档/片段、已有正文长度、embedding 和当前来源元数据；
2. **官方来源可达性**：只记录规范 URL、最终 URL、HTTP/网络有限状态和核验时间；`403/404/timeout` 不等于正文缺失；
3. **正文及附件完整性**：只有官方页面或官方附件实际可读，或已有不可变官方 asset 可校验时，才判断正文为空、截断、仅附件名、附件清单和解析质量。

P0/P1 优先级必须来自版本化人工清单及对应问题/有效政策依据，不能以标题关键字命中数量直接充当最终分级。审计运行必须在首个外部请求前冻结“ES 页、父页面、附件”各自预算，并把种子文档计入父页面预算；预算超限形成 `budget_exhausted`，不得通过事后扩大同一运行预算改写结果。

每个附件 asset 包含：

```text
assetId = "ka-" + sha256(NFC(finalOfficialUrl))[0:24]
assetVersion = sha256(rawBytes)
```

还必须保存初始/最终 URL、HTTP 状态、MIME、扩展名、字节数、抓取时间、父 `documentId`、文件名、解析/OCR/表格状态和人工核验标记。相同 URL+hash 重放不得新增资产；相同 URL 内容变化必须产生新版本，禁止覆盖旧字节。manifest 使用 exact-key Schema、UTF-8、NFC、重复键拒绝、有限字符串和枚举。

### 12.3 下载与文件安全

`DR-KRET-013`：来源 host 必须在版本化政府域 allowlist，HTTPS 优先；每次重定向最多 3 跳并重新验证 scheme/host，拒绝用户信息、IP literal、私网/本地地址、非 80/443 端口、片段和异常规范化 URL。

官方旧 URL 遇到 WAF、迁移、下线或其他不可达状态时，不自动重试、不搜索并抓取第三方副本。P0/P1 允许新增一个人工核验的官方替代 URL，但 manifest 必须同时保存旧 URL、替代 URL、官方同源/机关证明、核验人和核验时间；替代来源仍须通过同一 allowlist、redirect、MIME、hash 和下载预算。不能证明官方性的资产保持 `source_unverified`，不得下载、解析或索引。

`DR-KRET-014`：单资产默认上限 50 MiB、连接/读取总时限有界且默认不重试；状态非 200、空 body、声明/实际大小超界、类型/签名冲突均失败。允许类型仅 HTML、PDF、DOC/DOCX、XLS/XLSX；不得执行宏、脚本、外链对象或嵌入程序。

`DR-KRET-015`：OOXML/ZIP 在解析前检查规范路径、文件数≤1000、解压总量≤100 MiB、单文件≤50 MiB、总压缩比≤100；拒绝绝对路径、盘符、`..`、重复规范路径、加密和嵌套压缩包。

### 12.4 解析、OCR、表格和切片

`DR-KRET-016`：HTML 仅提取正文和附件链接；PDF/DOC/DOCX/XLS/XLSX 分别由固定版本 parser 处理。原生文本不足时，PDF 页面可以进入受控 OCR；OCR 输出必须携带 `ocrApplied=true`、页码和 `ocrConfidenceStatus=accepted/review_required/rejected`，后两者不得自动索引。

`DR-KRET-017`：表格保留 sheet/table、行列顺序、合并关系和单元格文本，转换为确定性行列表示；脚注、章节标题和条款序号不得静默丢弃。公式只读取缓存显示值或公式文本，不执行公式、宏或数据连接。

`DR-KRET-018`：解析结果为不可变 `ParsedDocument`，包含 ordered blocks（heading/paragraph/clause/table/page boundary）、parser/version、原 asset hash 和有限质量指标。空白、仅附件名但附件未解析、截断、损坏或质量不合格进入 quarantine。

`DR-KRET-019`：结构感知切片优先按标题→章节→条款→表格行组边界，正文 chunk 最大 1600 code points、重叠最大 160；表格不跨表拼接。chunk ID 为 parent document、asset version、结构路径、ordinal 和规范正文的 SHA-256 派生值，重放稳定且检测碰撞。

`DR-KRET-020`：附件片段继续使用已核验父 `documentId` 进入现有读取/出域合同，但以独立 `assetId/assetVersion/relationType=attachment/sectionPath/clauseId/tableId` 保存来源。现有父文档策略缺失、冲突或不允许该 snapshot 时不得索引附件；全新官方父文档必须由 asset manifest 显式选择一个既有、同域且不扩权的 policy，经过全成员校验后才能进入新目录。继承或新增绑定只能保持同等或更严权限，不得新建 policy/disposition 或扩大字段上限。

### 12.5 embedding 与候选索引

`DR-KRET-021`：embedding 只调用当前 loopback BGE `/embed`，输入是通过质量门禁的规范 chunk 文本；响应必须恰好 1024 个有限数。失败 chunk 不写入候选，且不重试。

`DR-KRET-022`：构建目标必须是精确命名的新索引，格式 `agent-doc-tax-policy-v<major>-<yyyymmdd>-corpus-a<revision>`；拒绝当前 alias 目标、任何已存在索引和非 allowlist 名称。候选先复制当前已发布文档，再幂等 upsert 新的受控 chunk；同 ID 不同内容为冲突并停止。

`DR-KRET-023`：mapping v2 兼容现有 typed source fields，并新增仅供溯源的内部字段 `assetId/assetVersion/assetSha256/assetKind/parentDocumentId/parentAssetId/relationType/sectionPath/clauseId/tableId/parserVersion/ocrApplied/ocrConfidenceStatus/sourceFinalUrl/sourceFetchedAt`；这些字段不加入公共 DTO 或 Agent 请求。构建 manifest 记录 mapping、parser、chunker、embedding、文档/附件/条款/片段数量和规范 fingerprint。

### 12.6 Profile、出域策略和发布

`DR-KRET-024`：候选发布必须生成新的 policy/law snapshot 和新的模型出域目录资源。旧目录文件和 loader 保持可校验；新目录对现有文档保留原 policy/disposition/字段上限，只增加与所属逻辑域对应的新 snapshot。附件沿用父 `documentId`；全新官方父文档只能显式绑定既有同域 policy，二者均不得绕过目录全成员校验。目录 hash、Profile index name/UUID/mapping/snapshot 与服务启动绑定必须同时更新。

`DR-KRET-025`：发布门禁只阻塞线上读取alias生效，不阻塞已批准的下载、解析、候选构建及DR-KRET-032隔离验证。线上切换前必须校验alias当前目标等于记录的旧索引且候选无alias（临时验证alias已移除）；用单次 `_aliases` 原子remove/add切换。切换后执行typed keyword/vector、读取拒绝、Evidence和回归冒烟；失败以精确前置检查原子恢复旧目标。发布前可在隔离alias上演练候选→旧目标→候选及相应Profile重启；线上实际发布仍需验证新绑定生效并保留精确旧绑定回滚路径。阶段A不删除任何旧索引。

`DR-KRET-032`：候选typed验证属于离线运维/测试，不是第二条在线查询链路。新增工具只可管理`agent-knowledge-validation-<32位小写随机hex>`临时alias；每次生成新名称，创建前必须不存在，且与线上alias不同。输入显式绑定source/candidate名称、UUID及当前线上alias目标，两个索引必须write-blocked；只用`is_write_index=false`，不得加filter/routing或更新文档、mapping、索引设置。Java仍执行真实`KnowledgeProfileVerifier`，隔离服务通过进程环境接收临时alias、精确候选及新policy/law快照；alias名称不参与既有snapshot哈希算法，不得关闭验证器或绕过typed endpoint。

实施切片：建议新增`knowledge-corpus-tools/src/knowledge_corpus_tools/validation_alias.py`，同步context manager拥有临时alias的创建、候选/源切换及finally移除；入口参数为已校验固定绑定和本地HTTP client，不接受任意ES动作。每次写入前重新检查索引UUID/write-block、线上alias精确目标和临时alias归属；响应不明时不重试，仅只读确认并在归属仍明确时清理本次临时alias。其他进程改变归属或线上绑定时停止写入并报告有限冲突，禁止“恢复”他人的修改。`_aliases`只保证单次动作原子，不冒称读取检查与写入跨请求CAS；本地一次性运维窗口禁止并行发布，随机独占名称避免测试相互争用。

当前ES9.4.1管理响应按官方`IndicesAliasesResponse`核对：成功需要`acknowledged=true`、`errors=false`，再验证alias实际目标；`errors=true`或结果不明不可当成功。现行StageA alias的空flags `{}`按冻结基线精确保持，不要求补写flags；仅本次临时alias强制`is_write_index=false`。该差异不修改旧alias或索引写保护。来源：[ES9.4.1响应实现](https://github.com/elastic/elasticsearch/blob/v9.4.1/server/src/main/java/org/elasticsearch/action/admin/indices/alias/IndicesAliasesResponse.java)。

建议新增版本化测试launcher，显式读取pending binding/catalog及其预期SHA，使用固定loopback端口启动本次owned auth/es-query进程；ADMIN来自真实auth，VIEWER/UNKNOWN/service-token可用同一随机HMAC在内存签发。不得读取模型Key、启动模型任务或复用冻结launcher的硬编码线上绑定。只测既有`/es/knowledge/search`：policy/law keyword/vector、ADMIN/VIEWER允许及UNKNOWN/missing/malformed/service-token拒绝，响应经现行Python Adapter严格解码、实际正文hash与catalog成员/Evidence引用校验；合成引用校验不计为真实摘要或quality-v3端到端通过。只保留有限状态、计数、hash，不保存JWT/原文/向量。HTTP使用trust_env=false、无redirect/retry、响应大小/次数/timeout硬上限。

finally先停止且核实本次Popen PID，再关闭、扫描并删除本次精确临时日志，最后按归属检查移除临时alias；任一清理失败使验证失败并明确残留，不影响线上alias、不删除索引。初始建议预算：模型0、typed search≤24、embedding≤6、rerank0、alias写≤4（创建/两次演练/删除）、ES管理读取≤40；readiness仅health，可有限等待。真实验证失败后先诊断，不自动重新执行同批。脚本/fake测试须覆盖端口冲突零启动、UUID/别名漂移零写入、拒绝响应零正文、清理/超时/不明写入，以及线上绑定和历史文件不变。

### 12.7 入口门禁、发布门禁与完成边界

- 入口门禁：设计评审通过、官方来源/P0-P2 范围、显式 workspace、解析工具版本、下载/存储/索引操作预算和精确回滚目标齐全；只阻塞首次持久下载和候选写入。
- 发布门禁：P0 全部、目标 P1 全部、P2 清单，解析/OCR/表格质量、空正文/孤立附件为零、candidate mapping/count/fingerprint、隔离typed keyword/vector、读取/出域/Evidence、全量回归及隔离回滚演练通过；只阻塞线上alias切换，不阻塞DR-KRET-032临时验证alias。任一P0或目标P1仍为`source_unreachable/source_unverified`时保持发布门禁Open，但不阻塞已评审流水线和其他候选资产处理。
- 阶段 A 不以最终 `knowledge.query` topK 命中为通过条件。直接 typed retrieval 已证明新增原文存在、可读、可引用，但用户端仍失败时，记录阶段 B 的域选择/Rewrite/排序缺口，不在本阶段调参或增加 fallback。

### 12.8 派生向量输入（DR-KRET-030；已评审，纯函数实施切片）

本增量只实现离线纯函数，不创建client、不接收用户问题、不执行下载、ES/BGE调用或发布。新模块不得改写旧Stage A的`indexing.py`和历史构建资产。DR-KRET-021正文向量仍解释旧发布结果；新表示只作为后续候选构建输入，不悄悄替换当前向量。

固定版本`policy-title-section-body-v1`，函数`build_vector_representation`输入为keyword-only `content: str, title: str = "", section: str = ""`。调用者只能从同一已授权源记录取三字段；构造器不接受dict、parent查找、question、gold或时间参数。以下规则固定在代码，配置不可放宽：

1. content为非空且非全空白的UTF-8字符串，至多4096字符；title/section各至多512字符，可为空。拒绝非str、NUL、非法Unicode；不清洗、不截断、不规范化原文，ContractError只使用`vector_input_type_invalid`、`vector_input_text_invalid`、`vector_input_limit_exceeded`，不含输入值或原始异常。
2. 顺序取title、section，删除空字符串、与content完全相同及完全重复的项；不strip、不做模糊去重、不从邻近片段推断章节。按`"\n".join(保留元数据 + [content])`生成输入，整体UTF-8至多16384字节，超限拒绝，不降级截断或默默忽略条件。
3. 返回frozen `VectorRepresentation`，含固定version、text、content_sha256和input_sha256；两哈希分别计算原content和最终输入的精确UTF-8字节。text不进入repr；本对象只用于内存中的本地embedding请求，不直接序列化到日志/evidence或返回Agent。
4. 库存contentHash可能属于历史导入的不同口径，不能据此改写content或覆写旧hash。实际引用继续由Java对原文重新计算SHA-256；候选构建需独立保存实际body哈希与输入哈希的来源绑定，保留旧字段。附件已有精确body SHA校验不放宽。
5. 构造器没有读取授权决策权，也不能证明元数据真实性；接入者须保证来源及权限。最终引用仍只指向原content；标题/章节作为检索上下文不能替代缺少的原文证明。

上述字符/字节上限只是纯输入合同，不等于实际BGE tokenizer的token上限。候选接入前必须对冻结tokenizer及服务max_length做无截断预检，不能用维度正确掩盖服务截断；过长记录须保留源记录并阻止受影响候选发布，不能静默截断、删除或跳过后宣称全量完成。此检查属于后续构建合同，不在纯函数中引入模型/Tokenizer生产依赖。

候选构建/发布未包含在本纯函数实施依据内：需先冻结实际BGE模型快照及输入版本、精确源UUID/只读状态、policy范围、全记录保留与law向量不变、无重复ID、mapping及策略快照、失败隔离和原alias回滚目标，再按既有生命周期设计补齐新构建器的具体合同并评审。对照排名改善不是发布门槛的替代，特别不能只比较gold子集、忽略整个候选库竞争或原保留问题退化。

### 12.9 限定附件候选构建（DR-KRET-031；真实集成修复切片）

继承KQ-AD-019、REQ-KCORPUS-003/004/006。在线根、查询窗口、正文、条款、ACL/出域与公共DTO不变；旧`indexing.py`/`release.py`及历史资产不改。该切片只产出没有alias的只读候选，不包含alias生效、策略目录迁移或新的付费运行。

**选择范围**：以当前Java `application-knowledge-live.yml`的tax.policy类别集合与`assetKind=attachment`交集为唯一选择器，不使用gold、case、文档ID、问题或动态排名。未选中记录（含全部law）原样克隆。命中的附件还必须满足`relationType=attachment_chunk`、独立asset/parent身份存在、旧contentHash等于实际原文SHA、现有ACL元数据非空；任一异常使整批停止，不跳过该记录。预期总数、policy数、附件数由一次只读盘点绑定，不作为代码硬编码。

`vector_candidate.py`：同步`build_policy_vector_candidate(spec, *, client, prepare_vectors)`是离线入口；client由调用者创建/关闭，base URL只允许HTTP loopback origin，`trust_env=false`，无redirect/retry。构建器验证origin、环境代理禁用、redirect和有限timeout后才允许调用；真实驱动只能使用无显式proxy、retries=0的本地HTTPTransport，不得安装记录原文的event hook。不可从用户HTTP请求调用。frozen `VectorCandidateSpec`绑定源索引、UUID、mapping SHA、全记录fingerprint、精确计数、candidate名称、model snapshot SHA。candidate仅允许`agent-doc-tax-policy-v<major>-<yyyymmdd>-vector-b<revision>`，拒绝源/已存在索引、空/非法路径。源必须write-blocked、green且非数据流；现行alias保持原完整映射。配置仅传已核实绑定，不允许修改类别/operator或mapping任意字段。HTTP总上限400（含失败封存的预留1次），单响应≤16MiB；connect/read/write/pool各阶段timeout≤30秒，流式读取每块后检查请求已耗时，超过30秒即停止。同步HTTP阶段timeout不冒充从DNS到最后字节的绝对wall-time上限；只使用已核实的本地服务，不增加后台超时线程或自动重试。超限停止，不输出响应正文。

**准备与无写入前置**：全源按唯一chunkId排序读取（每页≤250、总≤20000），拒绝重复_id/chunkId、分页不完整、超时、分片失败和缺向量。向量必须1024个非bool有限数字，非零且可表示float32。逐条记录`SHA256(canonical JSON [_id, _source去embedding] + float32向量字节)`，排序后形成全记录fingerprint；保留字段的canonical JSON不做NFC/trim或其他变换。源全部记录校验及三项计数/mapping/UUID/fingerprint匹配后，才构造待替换输入。

`prepare_vectors`是调用者拥有的有界本地模型接缝：入参为有序tuple的`VectorRepresentation`，返回等长tuple向量。真实驱动必须先核对实际模型、tokenizer、服务源码、容器/镜像及max_length快照，并对全部输入做无截断token预检；任一输入超限则embedding和候选写入均0。一次准备最多1000条/32条一批，无自动重试；首尾模型身份须相同，原文、向量和JWT不落盘。仅health、假的token计数或手填hash不能批准真实构建。新候选工具不引入Tokenizer/模型运行依赖，由既有受控本地模型环境执行该前置。prepare失败、响应形状/维度/有限数错误均发生在clone之前。

**构建与核对**：

1. 准备后再次核对源UUID/mapping/write block及alias；再次确认目标不存在。通过ES原生`_clone`复制全部记录和已有向量，不使用全库重编码或_source重建。保持副本数，不携带alias，不修改source设置；先按下一项绑定确认回执/UUID再等待候选分片就绪（有界30秒），不以clone已受理冒充完成。
2. clone回执必须`acknowledged=true`、`index`精确等于候选名、`shards_acknowledged`为bool（false不冒充就绪）；收到确认后立即只读获取并固定非源的新UUID，再等待green，并再次核对UUID。ES 9.4.1在主分片启动后会删除`index.resize.source`，它不是永久来源合同；若name/uuid仍存在则逐个严格匹配源，未知子字段或格式异常仍拒绝。没有临时标记时，只有本进程取得的精确成功回执或已固定UUID才允许继续识别目标。完整扫描候选，初始fingerprint必须与源相同；没有alias、全记录一致及写保护初态通过后才允许取消候选write block。克隆操作及只读验证失败不重发clone，不删除候选或源。
3. 仅在候选增加4个keyword溯源字段：`vectorRepresentationVersion`、`vectorInputSha256`、`vectorModelSnapshotSha256`、`vectorBodySha256`；更新mapping `_meta.mapping_version`为`agent-knowledge-tax-v3-policy-context-v1`，其他mapping及ANN参数原样保留。字段已经存在或冲突即拒绝，不覆盖历史表示。使用partial update，仅写embedding与4字段，不使用script/upsert；每批≤32、每条绑定候选scan所得seq_no/primary_term，任一冲突/部分失败停止，不重试。
4. 完成后先refresh并write-block候选，再完整扫描核对：所有_id/chunkId、数量、原始非向量字段保持；非目标向量按float32逐字节相同；目标向量等于准备结果的float32表示且4个新字段精确匹配。原有contentHash/indexVersion/source/ACL等不改写，实际新物理版本由新index UUID/mapping与build evidence表达。完整成功前不可标记built。
5. 最后核对源UUID/mapping/write block/alias未漂移。返回有限frozen结果（目标UUID、数量、源/候选fingerprint、模型/输入版本、调用次数）；调用者使用exclusive新路径保存有限结果及失败状态，禁止保存源正文、原始响应或向量。不将本结果套用旧BuildManifest或旧语料UAT。

**失败、并发与恢复**：无重试/resume，名称存在即拒绝重入；源只读加首尾绑定、目标CAS保护并发，不能声称跨ES事务。已确认candidate归属和UUID后，失败清理仅尝试将该候选write-block；清理失败须显式报`candidate_seal_failed`，不得覆盖原失败或声称已封存。clone网络结果不明时仅允许只读探查：如果尚有完整且精确的临时name/uuid来源对，可据此固定新UUID后封存；标记已经消失且没有成功回执或既有UUID时，不凭名称/内容相似猜测归属，不进行清理写入。目标初始write-block提供停止后的保守保护；后续只读核查可另存有限补充证据，不能改写原失败终态。不中止或删除不属于本次的进程/索引。HTTP/JSON/schema错误只输出有限阶段/原因，不保留原始异常链及请求/正文。KeyboardInterrupt/取消也执行同一有限封存，随后向上取消。

来源：[ES 9.4.1 ResizeSourceIndexSettingsUpdater](https://github.com/elastic/elasticsearch/blob/v9.4.1/server/src/main/java/org/elasticsearch/cluster/routing/allocation/ResizeSourceIndexSettingsUpdater.java)。建议最小修改既有`_Build.run/candidate/seal_on_failure`和其fake：正常响应模拟临时来源删除；覆盖确认回执字段缺失/错误、来源部分存在或不符、确认后UUID替换、不明结果无来源时零写入，以及初始全记录不符仍禁止更新。保留原CAS、全字段/非目标向量对照和alias零写入，不以跳过来源校验代替归属证明。该修复不需要新的公共DTO、持久索引字段、锁服务或Gate。

**验证/发布边界**：用mock HTTP证明所有写路径只指向candidate、clone全记录保持、异常/并发/重入/响应篡改拒绝；真实构建前冻结模型与源绑定，真实构建后须验证新索引ANN及typed检索。构建通过不代表核心P0或阶段B通过。alias发布仍需§12.6的新policy/law快照、全成员策略、typed授权/Evidence/回归及精确回滚验证；这些动作不属于本构建函数。参考[ES clone合同](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-indices-clone)和[向量_source及精度合同](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector)，保留源段并用float32验证避免误称可恢复旧double输入。

## 13. 实现落点清单

保留组件和历史兼容编号见本节；新在线追踪见§9.4、新资料追踪见§18.5。旧实验落点不能作为目标策略已实施证明。

### 13.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-KRET-001` | `agent-runtime/src/agent_runtime/knowledge/retrieval/contracts.py`、`agent-runtime/src/agent_runtime/knowledge/retrieval/stage.py` |
| `IMPL-KRET-002` | `agent-runtime/src/agent_runtime/knowledge/retrieval/provider.py`：factory/components |
| `IMPL-KRET-003` | `agent-runtime/src/agent_runtime/knowledge/retrieval/es_adapter.py`：`EsKnowledgeSearchAdapter.search` |
| `IMPL-KRET-004` | `es-query-api/src/main/java/com/dylan/esquery/api/knowledge/KnowledgeSearchRequest.java`、`KnowledgeSearchResponse.java`、`KnowledgeSearchCandidate.java` |
| `IMPL-KRET-005` | `es-query-service/src/main/java/com/dylan/esquery/service/KnowledgeReadAccessGuard.java` |
| `IMPL-KRET-006` | `es-query-service/src/main/java/com/dylan/esquery/controller/KnowledgeSearchController.java`、`service/KnowledgeSearchService.java` |
| `IMPL-KRET-007` | `agent-runtime/src/agent_runtime/knowledge/retrieval/fusion.py`、`bge_rerank.py`、`bge_embedding.py` |
| `IMPL-KRET-008` | `agent-runtime/src/agent_runtime/knowledge/retrieval/settings.py`、Java `KnowledgeSearchProperties.java`/`KnowledgeProfileVerifier.java` |
| `IMPL-KRET-009` | `agent-runtime/src/agent_runtime/knowledge/retrieval/http.py`、`agent-runtime/src/agent_runtime/bootstrap.py`：三个固定 client、transport 与 owned lifecycle |
| `IMPL-KRET-010` | 已有 `knowledge-corpus-tools` 项目的 audit/contracts/schema modules：ES/官方来源只读盘点和 strict manifests |
| `IMPL-KRET-011` | 已有 `knowledge-corpus-tools` 项目的 acquire/safety modules：官方域、redirect、大小、MIME/signature 与 immutable asset store |
| `IMPL-KRET-012` | 已有 `knowledge-corpus-tools` 项目的 parsers/ocr modules：HTML/PDF/DOC/DOCX/XLS/XLSX、表格和 OCR |
| `IMPL-KRET-013` | 已有 `knowledge-corpus-tools` 项目的 chunking module：结构块、稳定 chunk、关系和质量隔离 |
| `IMPL-KRET-014` | 已有 `knowledge-corpus-tools` 项目的 embedding/indexing modules：BGE 1024 维、候选 mapping、复制和幂等写入 |
| `IMPL-KRET-015` | 已有 `knowledge-corpus-tools` 项目的 release module：候选校验、alias 原子切换、冒烟、回滚和发布 journal |
| `IMPL-KRET-016` | 新版本 Knowledge egress catalog、`application-knowledge-live.yml`/`serviceCenter` binding：新 snapshot 严格绑定，旧 catalog/历史证据不变 |
| `IMPL-KRET-018` | 新增 `knowledge-corpus-tools/src/knowledge_corpus_tools/vector_representation.py`：DR-KRET-030纯表示，不接入当前builder |
| `IMPL-KRET-019` | `knowledge-corpus-tools/src/knowledge_corpus_tools/vector_candidate.py`：§12.9同步builder/spec/有限结果及HTTP错误边界；只拥有新候选写入，不负责模型加载或发布 |
| `IMPL-KRET-020` | 建议新增`validation_alias.py`及版本化typed验证launcher：DR-KRET-032仅临时alias/隔离服务/有限证据；旧release.py、冻结launcher及在线Runtime不变 |
| `IMPL-KRET-021` | `serviceCenter/warmup-knowledge-reranker.py`同步CLI（固定输入/端点，无参数覆盖；有限JSON stdout和退出码），由`run-all-services.ps1`在启动循环前调用；非live工具可显式执行，不修改历史launcher；实施证据见[整理前P3 §20.53](../plans/历史文档/2026-09-14-unified-v3-baseline/P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) |
| `IMPL-KRET-022` | 新增`knowledge/retrieval/bge_rerank_context.py`纯格式器/ContextualBgeRerankAdapter；provider.py内部版本参数、main.py显式绑定；旧bge_rerank.py不改 |
| `IMPL-KRET-023` | 已新增`es-query-service/.../service/DocumentNumberQuery.java`包内纯函数；KnowledgeSearchService keyword构造、KnowledgeSearchProperties冻结布尔及KnowledgeProfileVerifier条件校验已接入；公共es-query-api、原配置默认和Python不变，验证与启用状态见P3/UAT |
| `IMPL-KRET-024` | 建议新增§9.8测试侧宿主与本地worker；复用只读来源与纯计分，生产对象图不引用 |

### 13.2 关键签名

```python
class KnowledgeSearchPort(Protocol):
    async def search(
        self,
        *,
        request: KnowledgePathRequest,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> PathRetrievalResult: ...

class EmbeddingPort(Protocol):
    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]: ...

class RerankPort(Protocol):
    async def rerank(
        self,
        *,
        query: str,
        candidates: tuple[AuthorizedKnowledgeCandidate, ...],
        timeout_s: float,
    ) -> tuple[RerankScore, ...]: ...
```

```java
ResponseEntity<KnowledgeSearchResponse> search(
    Authentication authentication,
    byte[] body)

KnowledgeSearchResponse search(
    KnowledgeSearchRequest request,
    KnowledgeReadDecision decision)
```

## 14. 测试与验证设计

保留组件和历史兼容编号见本节；新在线追踪见§9.4、新资料追踪见§18.5。旧实验落点不能作为目标策略已实施证明。

### 14.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-KRET-001` | typed path/result/batch 不变量：`agent-runtime/tests/contract/knowledge/test_ranked_batch.py` |
| `TEST-KRET-002` | 并发 plan、coverage、取消和单次 embedding：Knowledge retrieval stage tests |
| `TEST-KRET-003` | ES Adapter 请求无物理字段、严格响应：`test_es_adapter.py` |
| `TEST-KRET-004` | Java strict JSON/DTO/Profile：`KnowledgeSearchJsonCodecTest.java`、`KnowledgeSearchPropertiesTest.java` |
| `TEST-KRET-005` | ADMIN/VIEWER 与 unknown/missing/service-token：`KnowledgeReadAccessGuardTest.java` |
| `TEST-KRET-006` | endpoint security、正文前授权和原端点兼容：`KnowledgeSearchSecurityIntegrationTest.java`、Controller tests |
| `TEST-KRET-007` | RRF rank、去重、冲突、稳定 tie；BGE contracts：`test_bge_embedding.py`、`test_bge_rerank.py` |
| `TEST-KRET-008` | Profile/index snapshot 一致性和真实冻结链回归 |
| `TEST-KRET-009` | disabled 零 client、enabled 三 client、校验先于创建、取消/关闭幂等与日志零泄漏 |
| `TEST-KRET-010` | audit/asset/build/release manifest exact Schema、重复键/NFC/大小/枚举/哈希正反例 |
| `TEST-KRET-011` | 官方 URL、逐跳 redirect、MIME/signature、大小、超时、重复和内容变化 |
| `TEST-KRET-012` | PDF、DOC/DOCX、XLS/XLSX、HTML、表格、损坏/空白/仅附件名及 deterministic fixtures |
| `TEST-KRET-013` | 扫描 PDF OCR accepted/review/rejected、页码、无 OCR 冒充和日志无正文 |
| `TEST-KRET-014` | ZIP 路径穿越、盘符、重复路径、文件数/体积/压缩比及嵌套压缩拒绝 |
| `TEST-KRET-015` | 父文档—附件—条款—片段、日期/validity、稳定 chunk 顺序/边界/碰撞 |
| `TEST-KRET-016` | 解析失败 quarantine，质量不合格/策略缺失时 candidate 写入次数为 0 |
| `TEST-KRET-017` | embedding 维度/有限值/零重试、候选新索引 allowlist、当前索引零写入、幂等与冲突 |
| `TEST-KRET-018` | mapping/source compatibility、Profile/UUID/snapshot 与新 egress catalog strict binding；旧 catalog/hash 不变 |
| `TEST-KRET-019` | alias 前置目标、原子 switch、切后失败 rollback、回滚演练和不删除旧索引 |
| `TEST-KRET-020` | 阶段 A 14 项 UAT：直接 typed keyword/vector、授权、Evidence 连续子串、P0 酒店住宿证据及阶段 B 归因 |
| `TEST-KRET-021` | 审计三层状态、403/404/timeout 不推断正文缺失、种子计入预算、人工官方替代映射及非权威来源拒绝 |
| `TEST-KRET-025` | 新增 `knowledge-corpus-tools/tests/test_vector_representation.py`：精确输入/哈希、去重顺序、空值/类型/大小/UTF-8边界、原文与repr隔离、不可变、无网络/在线调用方 |
| `TEST-KRET-027` | 建议新增`knowledge-corpus-tools/tests/test_validation_alias.py`及版本化launcher fake：精确UUID/只读/alias、冲突/超时/不明写入、有限预算、finally/进程/日志；真实typed矩阵另存有限结果，不以mock替代 |
| `TEST-KRET-028` | `agent-runtime/tests/system_e2e/test_knowledge_reranker_warmup.py`：固定合成40项、严格响应、绝对deadline、超限、client关闭/零重试及启动顺序/disabled/PlanOnly；不调用真实服务 |
| `TEST-KRET-029` | §9.6表示/单次HTTP/原文所有权/失败关闭、factory版本及生产根fake/Spring E2E；不得替代真实UAT |
| `TEST-KRET-030` | §9.7文号词法/安全正则/同请求查询形状、单次HTTP、mapping和默认/冻结反证；原case/gold不变 |
| `TEST-KRET-031` | §9.8来源/缓存hash、token预算、唯一有界worker、输出/异常/独占记录、零重试和同池指标；不得外推完整UAT |
| `TEST-KRET-026` | `knowledge-corpus-tools/tests/test_vector_candidate.py`：混合policy/law全记录保留、只替换附件、输入/源漂移/预算/重复/错维度零写入、clone回执/临时来源删除/UUID替换/不明结果/失败封存、CAS冲突、逐条后置比较、alias零写入、无敏感错误及旧builder保护；直接local preparation/runner测试验证真实环境接缝及token超限零clone |

### 14.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-KRET-001` | Python retrieval 单元/契约/fake 集成通过 |
| `VAL-KRET-002` | Java DTO/Profile/strict JSON/原端点兼容 Maven 测试通过 |
| `VAL-KRET-003` | 读取授权矩阵、正文零泄漏和安全失败优先测试通过 |
| `VAL-KRET-004` | strict mypy、compileall、Profile/索引快照成员检查和受控真实只读检索证据一致 |
| `VAL-KRET-005` | 当前生产组合根的 typed path 调用计数、业务零调用和 owned client 生命周期测试通过 |
| `VAL-KRET-006` | P0/P1/P2 审计、资产/解析/OCR/表格/chunk 质量与 quarantine 检查通过 |
| `VAL-KRET-007` | 新候选索引、策略/Profile 快照、typed 检索、读取/Evidence、alias 切换/回滚和防回退回归通过 |
| `VAL-KRET-011` | 纯构造器定向测试、离线工具回归、strict mypy/compileall、旧文件与历史哈希、代码对照复核；不代表候选索引或真实UAT通过 |
| `VAL-KRET-012` | 在工具目录运行`python -m pytest tests/test_vector_candidate.py`及全部工具测试、strict mypy/compileall、代码对照评审；真实源/模型/token绑定、候选全记录对照及有限evidence另行执行，不用fake批准发布 |
| `VAL-KRET-013` | 在工具目录运行新增`tests/test_validation_alias.py`和launcher fake、工具全量/mypy/compileall，再执行版本化隔离typed验证；`TEST-KRET-027`覆盖DR-KRET-032归属/预算/拒绝/清理，真实结果与fake分离，未完成全回归/发布不得关闭主工作包 |
| `VAL-KRET-014` | 新预热定向pytest、Python编译/类型、PowerShell AST及PlanOnly通过；真实固定合成调用另存有限结果。在线5秒/20秒合同及Business/Knowledge回归不变；预热不是阶段B UAT证据 |
| `VAL-KRET-015` | 新表示unit/HTTP/factory/current root、strict mypy/compileall、正式隔离non-live全量、历史hash及安全投影；后续运行绑定新表示/源码，真实端到端另行验收 |
| `VAL-KRET-016` | Java新增定向测试及Knowledge Maven、Python基线/历史回归、只读同快照typed对照；fake不能替代召回增益或正式UAT |
| `VAL-KRET-017` | 新宿主/worker fake与现有相关性/历史回归、compileall；按UAT固定协议执行一次非付费窗口对照并核验清理，生产变更仍未批准 |

## 15. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 物理资源泄漏 | Agent 传 index/DSL | typed DTO + Profile 映射 | 否 |
| 未授权正文 | 先查询后授权 | Guard-before-search/return | 否 |
| 异构分数误比 | 直接混合 ES score | rank-based RRF | 否 |
| 快照混合 | 多域 path 指向不同 snapshot | 完整 snapshot 集一致性 | 否 |
| 索引/模型变化 | mapping、alias、维度或服务协议变化 | 启动验证+契约回归 | 需重新验证，不阻塞当前依据 |
| 非官方或重定向劫持 | 来源链接跳到未知域、IP 或私网 | 每跳 allowlist + 最终 URL 记录 | 停止该 asset |
| 解析静默丢失 | 扫描件、表格、脚注或仅附件名 | 类型 parser + OCR/表格质量状态 + quarantine | 停止 P0/P1 发布 |
| 候选覆盖现行索引 | 名称/alias 目标错误 | exact candidate allowlist + 当前目标拒绝 + 无 delete | 拒绝构建和发布 |
| 新快照策略缺失 | Profile 已切换但 egress binding 未迁移 | 新版本 catalog + full membership + 启动/冒烟校验 | 拒绝发布 |

## 16. 实施依据

| 项目 | 判定 |
|---|---|
| 是否可作为实现依据 | 按范围可用：§9最小检索与§18资料合同可作为后续授权实施依据；非实现完成声明 |
| 当前实现 | typed读取/授权、BGE、quality-v3与原阶段A已实现，原验证范围见P3/UAT；运行实例未在本轮核实 |
| 当前允许实施范围 | 后续独立授权后：DR-KRET-201～204及301～307，按P3在线和资料两条直接依赖推进 |
| 当前禁止动作 | 本轮仅文档；禁止代码、模型、运行配置、公共DTO、权限或索引操作 |
| 回滚 | 后续在线按相容代码/任务/配置整体恢复或禁用；索引/alias回滚另按§12/18精确绑定 |

## 17. v3.0评审记录

本轮仅整理文档，不继承旧评审。内审及正式分层、跨层复核的实际问题与结论见[整理记录](../历史文档/2026-09-14-unified-v3-baseline/MIGRATION.md)。整理前评审原样保存在归档；本轮为同一执行者分阶段复核，不冒充外部独立人员评审。

## 18. 资料组织、结构切片与检索表示（新设计，未实施）

本节依据REQ-KCORPUS-001～006、REQ-KQ-201～205和L1_01 §4.6。定向细化§12的离线职责；§18在线首期固定索引的设计不变。新标准化及chunker采用新版本，不修改旧parser/chunker/manifest或现行索引。事实及样本见P3 §22；字段名称均为拟议离线内部合同，不是公共DTO扩展。

### 18.1 来源层与标准化合同

`DR-KRET-301`：复用workspace的raw/parsed/manifests区，新增版本化sidecar `corpus-document-v2`，不建立生产数据库。先以已有合法本地资产重放；资料缺失记录缺口，不自动下载。严格JSON：重复键、未知键、错误类型拒绝；schemaVersion固定，字符串有界，未知为null或空tuple，不填猜测值；不可执行表达式/URL模板。原始11字段、源行身份和规范化结果分别保存，不覆盖来源值。

| 内部部分 | 字段及规则 |
|---|---|
| identity | 保留现documentId及父/附件ID；sourceKind为dataset/official/curated；sourceRecordId、sourceSnapshot、assetId/version按来源选填。不得以行号、标题、文号单独作为全局身份；重复身份异内容为冲突 |
| source | 数据集repo+revision、采集时间、原始/最终URL、原始行/资产hash、许可声明引用；官方发布者另记。相对URL只按已核实官方base解析，不能凭HF链接认证官方性 |
| metadata | title、documentNumber、channelRaw、documentType、effectLevelRaw、taxTypes、labelsRaw、topics、issuers、applicableRegions、applicableSubjects；逐字段带origin=source/manual_verified/inferred/unknown、sourceRef和observedAt。首期禁止自动生成inferred值，主题与适用主体分开 |
| temporal | writtenDate、publishedDate、effectiveFrom、effectiveTo、validityRaw、validityStatus、statusVerifiedAt、snapshotAt；日期ISO日或null，核验时间带时区；每个非空派生日期有sourceRef/原文span或官方显式元数据依据 |
| relations | parentDocumentId、parentAssetId、relationType、revises/replaces（可空）；关系必须有来源，循环/悬空/身份冲突拒绝新记录；不据同标题自动建修订关系 |
| provenance | rawSha256、normalizedSha256、normalizerVersion及hashScope；hash为64位小写hex。原始附件hash按bytes；标准化hash按版本规定的UTF-8 canonical JSON；不混用库存contentHash |

集合保留源顺序、精确去重、NFC规范化仅作用于标准化字段，不改raw。源字段为数组时逐项保留；字符串分隔只能采用来源已确认的分隔符，不按任意标点猜标签。documentType采用law/regulation/policy/interpretation/other/unknown；channel与effectLevel各保留原值及独立映射版本，不能互相代填。税种允许多值，主题/地域/适用主体缺依据则unknown；未知分类不改变ACL或排除资料。单元数据字符串≤512 code points、标签集合每维≤32项、sourceRef≤2048；超限保留raw并标review_required，不截断后入候选。正文不适用元数据长度限制，由既有资产/解析预算治理。

确定性合同：schemaVersion=2、normalizerVersion=`corpus-normalizer-v2`；normalizedSha256计算sidecar除自身normalizedSha256字段外的全部规范内容，JSON键排序、数组保留语义顺序、紧凑分隔、ensure_ascii=false、禁止NaN/Infinity，按UTF-8取SHA-256。source断言时间由冻结输入提供，不能由重放时钟补写；处理时间仅放外部run manifest，不参与内容对象。原始附件hash始终按原bytes；源行只有规范JSON可得时另标rawHashScope=source_record_canonical_json_v1，不冒称下载文件字节hash。相同来源断言/版本重放必须同hash；新官方核验或内容变化生成新断言版本，不覆盖旧sidecar。

`DR-KRET-302`：snapshotAt只表示来源快照；statusVerifiedAt必须来自实际核验，不从爬取时间补成当前。validityStatus为active/partially_invalid/repealed/pending/unknown，保留validityRaw及映射版本；历史ACTIVE/PENDING只是当时断言。成文日期不得填effectiveFrom；无依据的旧effectiveDate只记legacy_raw，不能迁为可信时间。部分失效只描述文档整体，条款默认unknown，须有明确废止/修订原文才建立条款有效区间；生效/失效先后矛盾进入review_required。父文档日期、状态不得无条件复制为附件独立事实：可以记录inherited_context和parent来源，但不宣称附件单独核实。

只读核实发现某官方页面状态变化，应新增一次来源断言，不改旧snapshot。当前问题可返回未知时效资料作为查阅线索，但不得据此给出现行适用肯定结论；历史问题按明确期间核实，不能一律排除已废止文件。首期这些规则只用于离线核验/评估；在线缺少对应公共字段，不能宣称已支持时间过滤。

### 18.2 身份、原文位置与结构切片

`DR-KRET-303`：建立三个不同的hash作用域：原始资产bytes；规范解析源文本/ordered blocks；chunk精确可引用content。另有embeddingInputSha256，不能替代body hash。保留旧contentHash及其已知口径；未知标legacy_unknown，不重写旧字段或宣称数据损坏。Java对返回content重新计算的SHA继续治理在线完整性。

位置合同采用`sourceTextVersion/sourceTextSha256/spanUnit=unicode_code_point/spanScope=parsed_source/start/end`，半开区间且0≤start<end≤源长度；content必须等于该规范解析源中的连续子串。PDF页、表格行列和blockId作为独立定位辅助，不冒称code point等于原始文件byte或页坐标。旧charStart=0只视为chunk_local，不能伪装全篇位置。解析时的空白/表格转换有版本记录；无法还原源跨度的旧记录保持unverified，不凭chunk序号反推。

原文层保留不可变的规范解析文本、ordered blocks和源asset hash；chunk引用该源而不是拼装的模型上下文。重放使用既有ID派生规则，输入包含新chunkerVersion和源版本，避免覆盖旧chunk；重复转载可通过规范正文hash建equivalent_content关系，但保留各自发布来源、权限、时效和版本。正文相同也不得合并不同授权/时效文档。父文档、附件身份不因重切片改变。

最小可重放源构造为`parsed-source-v2`：按已验证ParsedDocument.blocks原顺序，把每个精确block.text用一个LF连接；不trim/NFC/合并空白、不改变块内字符，记录每个blockOrdinal及其起止位置、parser/asset版本。新增分隔符属于规范解析表示，不冒称下载原文件字节。原始11字段的大正文只保留不可变源引用与hash，不在sidecar复制第二套正文。索引构建前须验证每个输出span与该源逐字相等；没有原有ParsedDocument或原文不能生成verified全篇位置，只能标待源补证，不从旧片段拼回“完整原文”。

关系核验使用已冻结的全父身份清单而非仅30个抽样集合，避免把样本外合法父文档误报孤立。relation source缺失和真正悬空分别记录。侧车标准化失败是单记录review_required；任何相关范围的覆盖验收保持未完成，不自动扩大到全库重新治理。

`DR-KRET-304`：拟议`knowledge-structure-chunker-v2`以已有ParsedDocument为输入，先确定章节/条款栈，再在同一最小结构单元内顺序打包相邻块；不再每个paragraph无条件独立成chunk。标题/条号短块附着后续正文，活动条款路径可传给子块，但仅路径继承、不声称每片包含完整条款。原文只有两字符且无后续正文时保持源记录并标short_unresolved，不能丢弃后称覆盖完整。

- 配置首个对照候选沿用最大1600 code points、重叠最多160作为硬上限；不是最优值断言。优先自然边界、保持连续span，不设置“至少40字符才合格”的盲目删除规则。
- 不跨asset、条款、表格、不同读取/出域范围打包。列表主句、适用条件、否定、例外及脚注优先同片；超限按段/句分开并标split_context_required，父关系辅助定位不自动多读正文。边界切割仍无法保全的单元进入review_required，不能截断或删除后发布。
- overlap只在同一结构单元内按完整句/块后缀复用，≤160且小于chunk长度；无合法边界时取0，不剪半句凑数。保留source span用于重复诊断；在线仍使用既有identity去重，不默认新增去重算法。
- 表格保存表头、行列/合并单元及脚注关联；行组可做独立连续源跨度。重复表头只能放入检索context，不注入quote正文；单独行没有表头不能当充分依据。扁平化后无法恢复列关系时标table_structure_unknown，不能根据数值位置猜表格或编造tableId。
- 目录条目与正文结构分开标记navigation/content/unknown，仅来源明确才分类；不凭相同条号误认正文。当前没有在线role过滤，后续是否排除导航项须在固定样本验证后另定，不暗中扩展DTO。

输出为frozen chunk记录：既有document/asset/ordinal/content/hash，加source span、section/clause/table定位、structureStatus和contextRefs；未知定位可空但不得标verified。父关系完整不等于跨条款回答充分。质量未过的受影响单元保留隔离记录，并使其覆盖验收未完成，不能用跳过数量美化结果。

### 18.3 分类消费与向量表示

`DR-KRET-305`：分类先保存在sidecar；需要ES消费时，由既有离线候选工具与es-query-service共同评审有限mapping/快照迁移。不按每个taxType/channel拆索引，不复制同文到多个分类库；独立索引只有隔离、生命周期、规模或同条件收益证据才能提出。现有channel→逻辑域映射保留，不用effectLevel推导相关性、用标签推导纳税人或用时效推导授权。

| 用途 | 现行/首期表示 | 后续可比较项及限制 |
|---|---|---|
| keyword | 现title/content/section及既有文号接缝 | 只比较可信结构字段的收录，不能同时修改查询权重和切片后归因到向量 |
| embedding | 原文body与已实现title/section/body表示均保留原版本 | body-only；可信title+section+body；有限可信classification+body三候选。分类不得含推断事实、当前问题或gold |
| rerank | 已授权正文优先，加有限title/文号/成文日期；当前512token窗口 | 保持该表示用于首轮切片/向量比较；不随向量试验偷偷调整重排窗口 |
| Evidence/quote | 精确原文content及其实际hash | 不使用拼接标题、重复表头或推断标签作为正文；连续子串/引用合同不变 |

`DR-KRET-306`：每次构建记录模型repo/revision或artifact hash、tokenizer hash、服务源码/配置版本、维度、最大token数、输入表示版本及input/body hash。向量字段有值只能证明覆盖，不能证明模型一致、数值有限或未截断；旧记录缺版本不能用当前服务型号回填历史事实。先使用已有构建manifest补证，无法逐记录证明则legacy_unknown，并如实限制对照结论。

输入预检必须按实际固定tokenizer计数，包含特殊token、标题、章节及分类开销；字符/UTF-8字节上限是独立约束。超长不静默截断、不借rerank窗口缩小原文；先在既有结构边界重切，仍不可表示则隔离并阻塞受影响范围。重切会改变实验变量，必须归入切片实验，不能继续声称纯向量表示对照。元数据最多512 code points且整体仍须满足实际token限额；不可用大量标签挤掉正文。模型/长度/维度未知则新embedding实验Blocked，本轮不得加载模型或执行推理。

### 18.4 迁移、验证与回滚

`DR-KRET-307`：先实现无网络标准化及结构回放，人工确认有限scope；再冻结新旧源manifest及chunk集合。纯向量对照固定切片、正文、ACL、模型与查询；重切片对照固定父文档/asset版本及原文预期span，评价身份不得仍用旧chunkId。分类和时效不能凭补齐率证明准确。实验预算与停止条件见UAT_01 §16；不自动创建效果candidate。

仅在另获实施/写索引授权后，使用现有离线候选工具创建新版本索引；当前索引和旧资产不变。先保留全库未受影响记录，逐项列清迁移/隔离/未处理数量及原因；不得遗漏law或无分类数据。变更集合、mapping、向量、策略目录/快照均精确绑定，既有DR-KRET-024/025/032控制隔离typed验证与原子发布。新来源/新chunk必须满足原读取及出域策略，不因父关系扩权。发布前验证旧目标、候选完整性、功能/安全/资料覆盖和保留题不退化；失败按成套相容绑定恢复，不删除旧索引。Git回滚不等于数据回滚。

“有限scope”指本次重规范化/重切片/表示变更及人工审计集合，不是仅保留这些文档作为搜索库；未受影响的全库竞争记录须原样保留并验证fingerprint。保留旧记录不代表已按新标准逐条认证，legacy_unknown/source_unverified仍需在结果中披露；不能把旧curated改称新官方gold。只对变更集合执行新准入，安全/快照及候选全记录保留检查仍覆盖全库，不扩大到重新采集全部历史资料。原预期依据无法核实的题单列source_gap，质量值为null且注明不具评价条件；保留在计划总数和数据缺口统计，不伪造Recall=0/1或悄悄删除。质量分母、有效/未评估数量必须同时披露。

### 18.5 实施追踪（均为后续义务）

以下编号在本节定义，规则语义为§18.1～18.4；实现/测试/验证的具体含义在后续追踪表展开，并不表示代码已经存在。

#### 新设计编号定义

| 规则编号 | 实现编号 | 测试编号 | 验证编号 |
|---|---|---|---|
| DR-KRET-301、DR-KRET-302、DR-KRET-303、DR-KRET-304、DR-KRET-305、DR-KRET-306、DR-KRET-307 | IMPL-KRET-301、IMPL-KRET-302、IMPL-KRET-303、IMPL-KRET-304 | TEST-KRET-301、TEST-KRET-302、TEST-KRET-303、TEST-KRET-304 | VAL-KRET-301、VAL-KRET-302、VAL-KRET-303、VAL-KRET-304 |

#### 资料设计追踪

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-KCORPUS-001/003、KQ-AD-025/026 | DR-KRET-301、DR-KRET-302 | IMPL-KRET-301：拟新增knowledge_corpus_tools/normalization_v2.py及严格sidecar Schema；复用audit/models/source清单 | TEST-KRET-301：11字段、缺失/多值、来源冲突、日期同值/部分失效/未知及相对URL | VAL-KRET-301：纯单元/契约、人工来源对照；不调用模型 |
| REQ-KCORPUS-002/003、KQ-AD-027 | DR-KRET-303、DR-KRET-304 | IMPL-KRET-302：拟新增chunking_v2.py/位置记录，复用ParsedDocument；旧chunking.py不覆盖 | TEST-KRET-302：句/条款/表格/脚注、短块、overlap、连续span、身份/hash稳定及冲突 | VAL-KRET-302：固定公开/合规fixture重放、字节/跨度及人工结构审计 |
| REQ-KCORPUS-003/004、KQ-AD-026/027 | DR-KRET-305、DR-KRET-306 | IMPL-KRET-303：独立表示/无截断预检及已有manifest补证；不改线上Profile | TEST-KRET-303：三表示、token/字符/字节边界、推断标签拒绝、legacy_unknown | VAL-KRET-303：纯构造与tokenizer验证后另授权有限BGE对照 |
| REQ-KCORPUS-005/006、KQ-AD-028 | DR-KRET-307 | IMPL-KRET-304：现vector_candidate/validation_alias/release接缝的显式新版本迁移计划及测试，不自动覆写冻结实现 | TEST-KRET-304：全记录保留、映射/策略错配、预算/中断/回滚及不改现行索引 | VAL-KRET-304：fake→另授权隔离typed→另授权发布；UAT-KORG各项 |

本节不授权上述实施。本轮只验证设计可实施性与文档一致性；未读取模型凭据、重算向量或修改任何索引。
