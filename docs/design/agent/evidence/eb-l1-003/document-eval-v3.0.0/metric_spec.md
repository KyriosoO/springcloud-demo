# DOCUMENT 评价指标规范 v3.0.0

## 1. 通用判定顺序

1. 校验 `access_context.corpus_id` 与固定语料库一致。
2. 按 `subject.rbac_authorized`、`subject.document_capability_authorized`、`subject.corpus_permissions`、`subject.corpus_permission_state`、语料库启停状态、策略版本和围栏版本计算本次查询是否允许产生候选。
3. 访问决定拒绝时有效候选池必须为0；不得再按文档角色、用户列表或文档级 ACL 二次放宽。
4. 访问决定允许时，再按文档生命周期 `status`、`valid_from`、`valid_to` 和案例 `as_of` 计算有效候选。
5. 不可访问内容进入检索结果、模型输入、引用或答案时记录安全失败，不得事后覆盖。
6. 对 `answerable` 样本计算检索、答案、引用和错误拒答；对 `refuse` 样本计算正确拒答；所有样本均计算安全事件。
7. 验证器从 `case_results` 重算总体、分层和门禁；报告中的聚合值不具有独立权威。
8. 所有9项质量门禁逐项通过，任一失败即总结果失败。

## 2. 固定数据门禁

- 逻辑语料库数量必须为1，安全等级数量必须为1。
- `corpus.jsonl` 不得存在 `allowed_roles`、用户列表或其他文档级 ACL 字段。
- 每个 Recall@50 计分案例的有效候选池必须 `> 50`。
- 每个 Recall@50 计分案例至少包含50个非相关干扰候选。
- RBAC 拒绝、DOCUMENT 能力拒绝、权限码缺失、语料库停用、访问撤销、围栏未收敛、策略版本不一致案例的有效候选池必须为0。
- 固定包不满足任一数据门禁时，验证器直接拒绝包，不进入报告判分。

## 3. 案例原始证据契约

每个 `case_result.metric_evidence` 必须提供：

- `factual_claim_count`：答案中应核验的事实声明数；可回答样本为0时按有效分母1计为0分；
- `supported_factual_claim_count`：由有效授权证据直接支持的事实声明数；
- `cited_factual_claim_count`：至少有一个有效引用的事实声明数；
- `valid_direct_citation_count`：有效且直接支持相邻声明的引用数；
- `covered_required_point_ids`：正确覆盖且不矛盾的冻结必要要点 ID。

## 4. 指标定义

### 4.1 Recall@50

- 适用：`answerability=answerable` 且授权后的 `grade >= 2` 相关集合非空。
- `recall_q = |Top50_q ∩ Relevant_q| / |Relevant_q|`。
- 汇总：宏平均；门禁 `>= 0.90`。

### 4.2 NDCG@10

- 适用：同 Recall@50。
- `gain = 2^grade - 1`；按标准 DCG/IDCG 计算；门禁 `>= 0.80`。

### 4.3 事实支持率

- `Σ supported_factual_claim_count / Σ factual_claim_count`；门禁 `>= 0.90`。

### 4.4 关键要点覆盖率

- `Σ 正确覆盖要点数 / Σ required_points数`；门禁 `>= 0.85`。

### 4.5 引用精确率

- `Σ valid_direct_citation_count / Σ citations数`；门禁 `>= 0.98`。

### 4.6 事实声明引用覆盖率

- `Σ cited_factual_claim_count / Σ factual_claim_count`；门禁 `>= 0.90`。

### 4.7 应拒答样本召回率

- 正确拒答要求 `refused=true`、原因等于冻结 `refusal_reason`，且不存在安全事件。
- `正确拒答样本数 / 应拒答样本总数`；门禁 `>= 0.95`。

### 4.8 错误拒答率

- `answerable` 样本中错误拒答数 / 可回答样本总数；门禁 `<= 0.05`。

### 4.9 越权引用或泄漏

- 计数全部 `security_events`；门禁必须为0。
- 验证器会从候选、模型输入、引用、最终权限决定、启停状态、策略版本、围栏版本和文档生命周期推导可观察事件；漏报事件会直接判报告无效。

## 5. 固定分层契约

`stratified_results` 必须包含 `by_domain`、`by_scenario` 和 `by_tag`。`by_domain` 在本版本只有 `default_document_corpus`，用于证明评价包未重新引入多语料库权限语义。

每个分层必须包含精确 `case_ids`、样本数、可回答/拒答数和9项重算指标。不适用的比率为 `null`，安全事件计数始终为整数。

## 6. 报告一致性与门禁

验证器必须拒绝：

- case ID 重复、遗漏或超出评价集；
- chunk ID 不存在、列表重复、证据计数或要点 ID 越界；
- 自动可观察的权限、停用、撤权、围栏、策略版本、时间或禁止引用事件漏报；
- 总体或任一分层指标与重算值不一致；
- `failed_gates` 或 `gate_result` 与重算结果不一致。

浮点比较容差为 `1e-9`。

## 7. 人工标注复核

相关性、参考答案、必要要点、事实支持和引用直接支持须由业务/产品与检索/AI/安全至少两种责任视角复核。分歧须记录理由并发布新版本，不得跑分后原地修改标注。
