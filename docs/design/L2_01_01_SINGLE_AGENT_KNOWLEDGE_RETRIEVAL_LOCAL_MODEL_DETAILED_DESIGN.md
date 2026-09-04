# [L2_01_01] 单体 Agent Knowledge 检索与本地模型接入详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_01_01` |
| 当前版本 | v2.7 |
| 日期 | 2026-09-04 |
| 权威范围 | Knowledge typed retrieval、两级 Profile、读取授权、本地 BGE，以及阶段 A 离线语料审计、资产处理、候选索引和受控发布 |
| 上位文档 | [`L1_01` v1.17](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) |
| 来源文档 | [L2_01_01 v0.8 归档版](历史文档/2026-08-21-v0-baseline/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) |
| 实施状态 | 在线 typed retrieval、Java Provider、本地模型及阶段 A 离线语料流水线、结构化 legacy DOC 解析、candidate a5、alias 发布/回滚均已验证；具体状态由 P3/UAT_01 管理 |

## 2. 阅读导航与变更记录

重点：第 7 节 typed contract、第 8 节两级映射/授权、第 9 节 RRF/rerank、第 13 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.0 | 2026-08-21 | 建立检索基础设施稳定基线 | 删除真实联调流水，突出 Agent/ES 边界、授权前置、统一候选、快照和本地模型契约 |
| v1.1 | 2026-08-21 | 代码对照评审修复 | 补强并发失败清理、同 Profile 快照一致性，并校正 path 失败分类、rerank 上限和 batch 字段说明 |
| v1.2 | 2026-08-26 | 生产接线与生命周期 | 明确三固定 origin client 的创建、所有权、失败清理、关闭及 non-live 调用计数 |
| v1.3 | 2026-08-26 | 实施状态收口 | 如实同步 typed Provider、读取授权、RRF/rerank 与三个 owned client 已通过 Python/Java 验证 |
| v1.4 | 2026-08-26 | 效果 UAT 证据同步 | 记录真实效果运行对检索链路的验证，不改变 typed contract、Profile 或排序算法 |
| v1.5 | 2026-08-28 | 依赖与实现依据纠偏 | 同步 L1 当前版本并校正本文可实施版本；typed contract、Profile 与排序算法不变 |
| v1.6 | 2026-08-28 | 上位效果设计同步 | 同步上位效果诊断结论；检索合同、Profile、RRF/rerank 实现及当前参数均不改变 |
| v1.7 | 2026-08-28 | 上位实施状态同步 | 同步 L1/L2 当前版本与 Summary V4 non-live 状态；检索合同、Profile、RRF/rerank 实现及参数不变 |
| v1.9 | 2026-08-28 | 稳定权威纠偏 | 移除候选运行状态，只保留 typed retrieval、Profile、授权、RRF/rerank 和 client 生命周期合同 |
| v2.0 | 2026-09-02 | 阶段 A 语料生命周期 | 新增官方来源审计、不可变 asset、PDF/Office/OCR/表格解析、结构切片、候选索引、Profile/策略快照发布与 alias 回滚合同；在线 typed DTO 和排序算法不变 |
| v2.1 | 2026-09-02 | 审计事实边界修复 | 将索引库存与官方页面可达性拆分；禁止由 403/404 推断正文缺失；补充官方替代来源人工绑定、精确预算计数和不可达来源对发布门禁的影响 |
| v2.2 | 2026-09-02 | 阶段 A 实施收口 | 同步 audit v3、官方附件解析、31个新chunk、candidate a2、14/14专项 UAT 和原子 alias 发布/回滚验证，不改变在线排序算法 |
| v2.3 | 2026-09-03 | 正式代码/数据复评修复 | 锁定审计文件哈希复算、chunk 内容哈希、处理计数闭合、workspace 路径归属和发布 journal 前置检查；以修复后的 UAT attempt-02 作为最终验收证据，attempt-01 原样保留 |
| v2.4 | 2026-09-03 | 条款关系完整性修复 | 正式复核发现 legacy DOC 整体扁平化导致条款关系缺失；改为保留 heading/clause/page/table 边界的结构化解析，生成 candidate a4 并以 UAT attempt-04 完成发布复评 |
| v2.5 | 2026-09-03 | 批次隔离与源码可复现收口 | 单资产网络失败和损坏 Office/PDF 容器统一形成有限失败并隔离；因 a4 构建早于该修复，以最终工具源码重建等价内容 candidate a5，并以 UAT attempt-05 和发布 attempt-05 收口 |

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
- 阶段 B 之外的图谱、新语料/索引发布，以及公共DTO或权限扩张；
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
| `REQ-KCORPUS-001` | 引用上位 REQ_00：官方来源、不可变 asset、三层审计事实和来源不可达不推断正文缺失 |
| `REQ-KCORPUS-002` | 引用上位 REQ_00：HTML/PDF/Office/表格/OCR 受控解析与不合格资产隔离 |
| `REQ-KCORPUS-003` | 引用上位 REQ_00：版本化 manifest、稳定关系、时效和父文档策略继承不得扩权 |
| `REQ-KCORPUS-004` | 引用上位 REQ_00：只创建候选索引，物理映射及 alias 发布由 es-query-service 边界治理 |
| `REQ-KCORPUS-005` | 引用上位 REQ_00：P0 全部、目标 P1、P2 全量盘点及阶段 B 分离的有限完成范围 |
| `REQ-KCORPUS-006` | 引用上位 REQ_00：发布前完整性、授权、Evidence、原子回滚和历史不可变 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-KRET-001` | `L0_00 SA-C-003/007/011/016/017` |
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
| `REQ-KRET-006`、`REQ-KRET-009`、`REQ-KCORPUS-001`、`REQ-KCORPUS-002`、`REQ-KCORPUS-003`、`REQ-KCORPUS-005`、`CON-KRET-005` | `DR-KRET-013`、`DR-KRET-014`、`DR-KRET-015`、`DR-KRET-016`、`DR-KRET-017`、`DR-KRET-018`、`DR-KRET-019`、`DR-KRET-020`、`DR-KRET-026` | `IMPL-KRET-010`、`IMPL-KRET-011`、`IMPL-KRET-012`、`IMPL-KRET-013` | `TEST-KRET-010`、`TEST-KRET-011`、`TEST-KRET-012`、`TEST-KRET-013`、`TEST-KRET-014`、`TEST-KRET-015`、`TEST-KRET-016`、`TEST-KRET-021` | `VAL-KRET-006` |
| `REQ-KRET-007`、`REQ-KRET-008`、`REQ-KCORPUS-004`、`REQ-KCORPUS-006` | `DR-KRET-021`、`DR-KRET-022`、`DR-KRET-023`、`DR-KRET-024`、`DR-KRET-025` | `IMPL-KRET-014`、`IMPL-KRET-015`、`IMPL-KRET-016` | `TEST-KRET-017`、`TEST-KRET-018`、`TEST-KRET-019`、`TEST-KRET-020` | `VAL-KRET-007` |

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

## 6. 当前实现基线与最小变更

Python 端已有 typed contracts、bounded HTTP、ES/BGE adapters、并发 stage、RRF 和 rerank；Java 端已有 `es-query-api` DTO、专用 `/es/knowledge/search`、endpoint-scoped Security、Profile 配置/启动验证、读取 Guard 和 Service。并发 path 的异常路径必须取消并等待尚未结束的 sibling 调用；同一 Profile 的成功 path 必须返回一致的 profile/index/read-policy snapshot。

通用 `EsQueryController` 原有端点保持兼容且不得被 Agent 使用。Knowledge endpoint 默认 disabled；目标启用需要冻结 Profile 与真实授权配置。

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

## 9. 本地模型、RRF 与 rerank

### 9.1 BGE-M3 Embedding

- endpoint 默认 loopback `http://127.0.0.1:8908`；
- 输入仅当前 rewrite 文本，UTF-8/字节有界；
- 输出 exact 1024 个有限 float，禁止 NaN/Infinity/字符串 coercion；
- 每个请求的同一 query 可在请求内复用一次向量，不跨请求缓存。

### 9.2 RRF

按计划稳定顺序处理 path candidate set。每条 path 的 source rank 必须连续 1..n；候选 identity 为 `(document_id, chunk_id)`。同 identity 若除 domain/source rank 外内容不一致，返回 `knowledge.candidate_conflict`；否则合并 domain IDs/path ranks，累加 `1/(60+rank)`。

排序键：RRF 降序、chunk ID、首次出现顺序。原始 ES/BGE 分数不跨路径直接比较。

### 9.3 BGE Rerank

- endpoint 默认 loopback `http://127.0.0.1:8909`，model exact `BAAI/bge-reranker-v2-m3`；
- 阶段 B每个选中域用其唯一query与该域去重融合候选执行一次rerank，单域≤40条，两域合计≤80；同一identity若确实在两域召回，可分别参与两次域内排序，但不得新增另一域未召回的候选，总次数仍不超过原始路径条数80。每个rerank返回索引/正文/分数必须完整一致，不比较不同query的裸分数；最终按域内rank轮转填充。每域最多一次rerank，无失败重试。
- 输出必须一一覆盖候选且索引唯一，score 有限；
- 阶段 B目标采用确定性锚点保留：每个计划域选择“该域keyword结果首位”和“该域rerank首位”；同identity去重，按目录域序、keyword锚点、rerank锚点生成≤4条保留前缀，余下项按本节定义的keyword/rerank交错序列在目录域序轮转填充到final_candidates。所有锚点必须来自本次已授权候选，不使用内容规则/gold/文档特判。配置final_candidates不足保留前缀时启动失败，不能静默丢弃域。

阶段B域内填充在锚点之后使用两个有限序列：keyword source rank（并列chunkId）与rerank排序（分数、RRF、chunkId）。按相同offset先keyword后rerank交错，以documentId/chunkId去重；跳过已保留锚点后，在域之间每轮取一个尚未输出项。一个域没有keyword候选时仅使用rerank序列。不得让重复锚点或重复候选占用另一个域的轮转名额；任何候选只能来自该域本次授权召回。RRF计算、两个序列各自排名、最多4个锚点、final20及Evidence8不变。此为确定性排名融合，不使用gold、答案、问题ID、文档ID特判或新增内容信号。

## 10. 并发、核心处理流程、错误分类与一致性

- Stage为每个计划item建立有界任务；先按唯一query执行embedding（最多2次）再并发执行最多4次search，query→vector请求内映射，禁止错用第一域向量。所有路径完成并通过授权优先级检查后，按目录顺序串行执行每域最多1次rerank（共≤2次），每次调用前检查剩余deadline，不延长阶段时限；任何技术/授权失败不触发新域/新query。
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

`DR-KRET-025`：发布门禁只阻塞 alias 生效，不阻塞已批准的下载、解析和候选构建。切换前必须校验 alias 当前目标等于记录的旧索引且候选无 alias；用单次 `_aliases` 原子 remove/add 切换。切换后执行 typed keyword/vector、读取拒绝、Evidence 和回归冒烟；失败用同样精确前置检查原子恢复旧目标。回滚演练必须先切候选、验证、切回旧目标并验证；最终发布需再次切至候选。阶段 A 不删除任何旧索引。

### 12.7 入口门禁、发布门禁与完成边界

- 入口门禁：设计评审通过、官方来源/P0-P2 范围、显式 workspace、解析工具版本、下载/存储/索引操作预算和精确回滚目标齐全；只阻塞首次持久下载和候选写入。
- 发布门禁：P0 全部、目标 P1 全部、P2 清单，解析/OCR/表格质量、空正文/孤立附件为零、candidate mapping/count/fingerprint、typed keyword/vector、读取/出域/Evidence、全量回归及回滚演练通过；只阻塞 alias 切换。任一 P0 或目标 P1 仍为 `source_unreachable/source_unverified` 时保持发布门禁 Open，但不阻塞已评审流水线和其他候选资产处理。
- 阶段 A 不以最终 `knowledge.query` topK 命中为通过条件。直接 typed retrieval 已证明新增原文存在、可读、可引用，但用户端仍失败时，记录阶段 B 的域选择/Rewrite/排序缺口，不在本阶段调参或增加 fallback。

## 13. 实现落点清单

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
| `IMPL-KRET-010` | 新建 `knowledge-corpus-tools` 项目的 audit/contracts/schema modules：ES/官方来源只读盘点和 strict manifests |
| `IMPL-KRET-011` | 新建 `knowledge-corpus-tools` 项目的 acquire/safety modules：官方域、redirect、大小、MIME/signature 与 immutable asset store |
| `IMPL-KRET-012` | 新建 `knowledge-corpus-tools` 项目的 parsers/ocr modules：HTML/PDF/DOC/DOCX/XLS/XLSX、表格和 OCR |
| `IMPL-KRET-013` | 新建 `knowledge-corpus-tools` 项目的 chunking module：结构块、稳定 chunk、关系和质量隔离 |
| `IMPL-KRET-014` | 新建 `knowledge-corpus-tools` 项目的 embedding/indexing modules：BGE 1024 维、候选 mapping、复制和幂等写入 |
| `IMPL-KRET-015` | 新建 `knowledge-corpus-tools` 项目的 release module：候选校验、alias 原子切换、冒烟、回滚和发布 journal |
| `IMPL-KRET-016` | 新版本 Knowledge egress catalog、`application-knowledge-live.yml`/`serviceCenter` binding：新 snapshot 严格绑定，旧 catalog/历史证据不变 |

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

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，本次增量已完成三轮内审和独立复评，允许目标内实施；真实UAT与正式代码评审尚未完成 |
| 当前允许实施范围 | 既有 typed endpoint/Profile/授权，以及官方语料审计、版本化处理、新候选索引和门禁后 alias 发布 |
| 当前禁止动作 | Agent/请求发起 ES 管理、原地覆盖/删除索引、未授权正文、未评审阶段 B 算法、图谱、公共接口变化或未冻结/超预算真实模型出域 |
| 回滚单位 | 在线 retrieval 配置；离线 candidate 整体停用；alias 原子恢复精确旧目标；原始资产和历史证据不覆盖 |

## 17. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | 两级 Profile、接口契约、来源与追踪一致 | Passed |
| 内审 2 | 授权、错误分类、快照、本地模型和并发一致 | Passed |
| 内审 3 | 真实落点、测试、兼容、链接和可读性检查通过 | Passed |
| 独立评审 | `REV-L2-01-01-001` 已修复；typed retrieval、两级 Profile、读取授权、RRF/rerank 与实现复核通过 | Passed |
| v1.2 聚焦评审与复评 | 前置纯校验替代半成品异步清理后，fixed origin、disabled 惰性、owned client、授权/快照失败关闭通过；无 S0/S1/未处理 S2 | Passed |
| v1.5 三轮内审与独立复评 | 当前版本、上位依赖和实现依据已同步；retrieval/Profile/授权合同未改变，无 S0/S1/未处理 S2 | Passed |
| v1.6 聚焦内审与独立评审 | 上位证据不足以批准检索调参；typed contract/Profile/排序不变；无 S0/S1/未处理 S2 | Passed |
| v1.9 聚焦内审与独立评审 | typed retrieval、Profile/物理资源边界、授权及运行状态下沉核对通过；S0=0、S1=0、未处理 S2=0 | Passed |
| v2.0 内审 1～3 | 在线/离线隔离、asset/解析/chunk/策略快照、候选零覆盖、门禁无环、回滚和非阶段 B 边界检查通过 | Passed |
| v2.0 独立评审 | 阶段 A 合同、实现落点和跨层边界复核；S0=0、S1=0、未处理 S2=0 | Passed |
| v2.1 内审 1 | 发现审计 v1 将来源不可达与正文缺失混淆、P0 关键字分级过宽、种子文档未计入父页面预算；已拆分三层事实、改为人工 P0/P1 清单并补齐预算语义 | Fixed |
| v2.1 内审 2～3 | 复核官方替代来源、无重试/无第三方降级、入口/发布 Gate、在线合同和阶段 B 边界 | Passed |
| v2.1 独立评审与复评 | 首轮修复 `REQ-KCORPUS-001～006` 逐项定义/追踪及 Audit/Design/Pipeline DAG；复评确认三层审计事实、官方替代来源、预算、候选零覆盖、alias回滚和历史不可变，S0=0、S1=0、未处理 S2=0 | Passed |
| v2.2 代码/数据/索引对照评审首轮 | 受控来源、immutable asset、parser/OCR/table/chunk、candidate/policy full-membership、typed retrieval、alias三步演练及旧索引保护通过；复核发现 UAT attempt-01 的 PDF/时效证据映射不足，以及审计哈希、内容哈希、计数闭合、workspace 路径和 journal 前置保护需要收紧 | Fixed |
| v2.3 复评 | 上述合同和测试均完成最小修复；UAT attempt-02 重新执行 14/14，通过同次运行直接验证 PDF parser、ACTIVE/EXPIRED、tax.law 当前税法 typed retrieval、alias 精确绑定及酒店住宿两类原文；Blocker=0、Major=0，未处理 Minor=0 | Passed |
| v2.4 正式代码/数据评审首轮 | 发现 4 个官方 legacy DOC 虽有约 75 个“第…条”词面，但候选条款引用为 0；整体扁平化不满足 `DR-KRET-017～020/023` | Fixed |
| v2.4 复评 | structured legacy DOC parser 形成 749 个有序 block、738 个 chunk 和 55 个条款引用；candidate a4、Profile/catalog 新快照、14/14 UAT attempt-04 与三步 alias 演练通过，Blocker=0、Major=0、未处理 Minor=0 | Passed |
| v2.5 复评 | 新增 timeout、非法 Content-Length 和损坏容器有限失败测试；candidate a5 的工具源码 SHA、15521 chunk、5600 document、738 个新 chunk、55 个条款引用、14/14 UAT attempt-05 与 a4→a5→a4→a5 演练一致，Blocker=0、Major=0、未处理 Minor=0 | Passed |

- 当前版本：v2.7。
- 文档状态：Approved；本次实施校准三轮内审和独立复评通过，记录归 P3_00 §20.4，尚不代表实施完成。
- 新版本不继承旧版联调/Gate 流水；历史证据只支撑“当前冻结切片已验证”。

## 阶段 B 增量实施追踪

| 来源 | 设计 | 实现落点 | 测试 | 验证 |
|---|---|---|---|
| `REQ-KQUALITY-001～004`；`KQ-AD-013～016` | `DR-KRET-027` | es-query-service KnowledgeSearchService.buildSearchBody；knowledge/retrieval/stage.py / contracts.py；bootstrap 策略绑定 | `TEST-KRET-022`：两路径size=limit+1和truncated、域内rerank/跨域round-robin、keyword/语义锚点、同分确定性、2/4/2调用上限、取消/授权/快照反证 | `VAL-KRET-008`：Java查询合同、Pythonretrieval fake与同索引本地有限对照、UAT_01 §14、历史回归 |

上述编号定义本轮新增验证，不继承已有 Passed。新生产策略为 `knowledge-retrieval-quality-v1`，显式由生产组合根选用；旧调用默认保持 legacy，历史任务/证据不修改。UAT 使用独立阶段 B 命名空间，验收标准和执行状态归 UAT_01/P3。

`DR-KRET-027`：既有 typed vector/keyword 窗口必须实际执行；每个预选域使用其自己的检索表达和授权候选作一次 rerank，最多2次且总候选≤80。每域 keyword 首位与 rerank 首位去重后作为锚点，随后按域内稳定排名 round-robin 填充；不比较不同 query 的原始分数，不用文档ID/gold/case加分。策略版本进入运行快照，不修改 Profile/alias/索引。
