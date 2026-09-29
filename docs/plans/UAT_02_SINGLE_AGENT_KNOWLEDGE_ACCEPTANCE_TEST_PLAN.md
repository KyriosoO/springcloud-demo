# [UAT_02] Knowledge 新设计验收计划

## 1. 文档信息与权威

| 项目 | 内容 |
|---|---|
| 当前版本 | v3.7 |
| 文档状态 | v3.7 Reviewed（权威版本引用同步；不代表UAT通过） |
| 日期 | 2026-09-29 |
| 文档身份 | 新计划首版；不继承旧UAT_01状态、预算或执行授权 |
| 设计依据 | [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v3.4 §4.5/4.6；Knowledge流程与Evidence L2 v3.4，检索/资料L2_01_01 v3.6批准合同；组件及离线实施进度以P3_01为准，不等于新版UAT已执行 |
| 流程合同 | [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) §8/19 |
| 检索/资料合同 | [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) §9/18 |
| Evidence/回答合同 | [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) §9/19 |
| 实施入口 | [P3_01](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md) v3.7；只负责包、直接依赖及操作准入 |
| 当前验收状态 | 37项风险中36项有当前目标 fake/non-live 直接证据、1项 partial/evidence missing；整体 Functional/Safety 未通过；当前root单域真实typed只读接线有有限预检，Spring全链、12题人工/效果与发布均Not assessed |
| 修改历史 | 2026-09-14，从旧UAT_01 §5的风险身份、§15/16的已批准新方法承接；不改设计阈值 |

勘误（2026-09-15）：v3.0内澄清§6.3资料缺口与安全/执行失败的停止范围，沿用§6.1及来源L2的未知状态规则；不修改用例、阈值、预算或验收状态。

v3.1补充结构单元、段落/表格顺序和父子关系的后续验收方法；未执行UAT，不改变历史case结果或当前模型/索引预算。

v3.2仅同步当前组件与离线工作包的实施状态；用例、判据和全部新版UAT未执行的结论不变。

v3.3澄清本次有限实施授权与旧计划创建时的禁令边界，并为A/B对照增加逐记录向量来源及新chunk类型化读取前检；不改变阈值或预记通过。初轮独立只读跨层评审及按发现复评后达到S0/S1/未处理S2均0；其后新增同一容器重启快照差异的单变量判据经定向复评，元数据S2已修正。设计评审通过不预记验收通过。

v3.4仅按当前代码与本轮实跑测试同步§3的37项 fake/non-live 风险证据及6项缺口，不改case身份、阈值或历史结论。31项“Fake/non-live verified”只指所列断言已运行，绝非新版37/37 UAT Passed；隔离单域typed预检不替代当前root全链、12题模型效果、维护者人工评价及发布证据。

v3.4同一目标内独立只读复评核对37行状态、12项资料用例、19个链接及引用的测试函数；先发现两处S2版本/状态措辞并最小修正，复评后S0/S1/未处理S2均为0。此评审只确认计划表述和阶段证据边界，不冒充外部人员、真实UAT或人工效果评价。

v3.5补录Spring→当前Runtime fake typed逐案域/路径/Profile和调用次数、读取拒绝零Summary及三条合成正文零公开泄漏；现有未绑定文档策略反例也已定位。五项由partial转为fake/non-live阶段已验证，EV006仍待真实回答与人工评价。v3.4当时的31/6记录保留为历史阶段快照，不改判真实集成或整体UAT。

v3.6仅补录P3_01 §14.8当前root到隔离真实typed接口的单域只读接线预检：固定fake任务输出、policy keyword/vector各1次HTTP 200、embedding 1次、Business和外部LLM各0；不改变37项阶段状态，不证明Spring全链、真实模型选域、Evidence充分性或新版UAT通过。首次诊断的短期测试HMAC回溯泄漏已在测试工具中修复并复评，原临时值失效；有限诊断不保存JWT或原始响应。

v3.7仅同步P3_01实施入口版本；37项风险、12题待冻结状态、资料验收判据及UAT结论均不变。

v3.7内补记2016年官方附件的只读原件定位和BGE同模型快照复核；原始结构证明、人工gold、质量阈值和真实对照仍未完成，不改变任何UAT状态。

## 2. 范围与结果纪律

本计划仅治理在线12/8/minimal-v1与资料组织两条新主线；图谱、记忆、多轮、旧候选推进及Business重新验收不属于关键路径。Business继续由[UAT_00维护基线](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md)管理，Knowledge变化不得重开无关Business用例，也不得掩盖共享合同回退。

五类验收分别记录：功能、安全、召回、回答、资料质量与发布回滚。最后一类只用于资料主线。文档Reviewed与任何一种验收通过无关；Not evaluated/Not executed是计划状态，不新增公开API或历史result枚举。

本计划创建及v3.2状态同步时没有生成新版追踪JSON、读取模型密钥、调用服务或推理。当前独立目标已授权一次有界真实测量与两项有限资料对照；执行仍须满足本计划的人工gold确认、冻结绑定、精确预算和停止条件。旧run、Gate及余额全部不可复用。技术失败按预先冻结协议停止，质量不达标如实记录，不自动新candidate。

## 3. 37个稳定功能/安全风险的目标版本映射

原37个ID保留风险身份，而非沿用原Passed。尤其RW组在新设计下验证“原意保护/非法意图/超时零下游”，不要求新链路继续生成改写文本；EV组使用Summary8模式义务，不把旧多证明集合强制输入带回来。下表“Fake/non-live verified”只表示列明的当前阶段断言已通过；“Partial/evidence missing”不冒充通过。隔离typed授权反例及当前root单域真实typed只读接线已有有限预检，Spring全链、人工和发布证明仍Not assessed。

| Case | 风险/输入类别 | 目标通过条件 | 设计要求 | 后续验证方式与所需证据 | 当前状态 |
|---|---|---|---|---|---|
| `UAT-K-PUB-001` | ADMIN 合法税务问题 | 选择且只执行 `knowledge.query` | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring→Runtime non-live E2E；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Fake/non-live verified：J `[k-nonlive-policy-admin]`，200/success/单Knowledge动作 |
| `UAT-K-PUB-002` | VIEWER 合法税务问题 | 读取授权通过并返回受控结果 | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring→Runtime + Java security；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Fake/non-live verified：J `[k-nonlive-law-viewer]`；P3_01 §14.6隔离VIEWER `tax.law` keyword typed预检200/5候选，但当前root接入该真实服务未验证 |
| `UAT-K-PUB-003` | denied/missing/malformed/service-token | 确定性 401/403；未授权正文和 summary 调用为 0 | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring/security matrix；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Fake/non-live verified：J `[k-nonlive-read-denied]` 403、summary=0、Business=0、公开result缺失且三条合成正文不出现在响应/日志/有限evidence；S `missingInvalidAndServiceTokensUseSafe401EnvelopeWithoutRuntime` 入口0；P3_01 §14.6隔离typed缺失/畸形/service各401、未知角色403。当前root→真实typed整链与真实资料零泄漏仍Not assessed |
| `UAT-K-PUB-004` | duplicate key、null、未知字段、超界问题 | 严格 JSON/输入失败，Runtime/Provider 调用为 0 | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring contract；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Fake/non-live verified：S `unknownFieldWrongMediaTypeAndOversizedBodyFailBeforeRuntime`、`duplicateNullAndMalformedJsonFailBeforeRuntime`，Runtime0 |
| `UAT-K-PUB-005` | unsupported 非知识问题 | 不执行 Knowledge/Business | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | 当前对象图 E2E；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Fake/non-live verified：UG `test_current_root_guard_allowed_non_capability_question_is_unsupported_without_downstream`，Guard允许的问题经fake selector返回`agent_unsupported`，公开unsupported且Knowledge/Business下游0；真实模型选路与Spring逐案未验证 |
| `UAT-K-PUB-006` | 第二动作或跨域 fallback 诱导 | 只允许一个顶层动作；无 fallback | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Core/Runtime E2E；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Fake/non-live verified：J `[k-nonlive-second-action]` 非法第二动作下游0，KR `test_business_failure_does_not_call_enabled_knowledge`、UG `test_current_root_knowledge_failure_never_falls_back_to_business` 双向隔离；真实模型选路未验证 |
| `UAT-K-RW-001` | 时间、主体、否定、法条等受保护约束 | 意图12只识别模式/域/terminal；安全原Q保留时间、主体、否定、法条且逐阶段相同，不生成改写文本 | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Fake/non-live verified：KR `test_current_root_preserves_original_question_and_mode_through_summary[lookup/explanation/applicability]`、UG `test_current_root_preserves_article_and_negation_in_each_typed_search_and_summary`，年/主体/否定/法条/税率原Q到意图、keyword、embedding、rerank、Summary一致；真实模型理解未验证 |
| `UAT-K-RW-002` | 模型返回非法候选 | 意图非法形状/候选/未知字段失败关闭；检索、embedding、rerank、Summary均0；不使用原问fallback | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Fake/non-live verified：KR `test_terminal_or_invalid_intent_has_zero_knowledge_downstream[invalid]`，非法额外字段后Knowledge IO0 |
| `UAT-K-RW-003` | rewrite timeout/provider failure | 意图模型timeout/provider failure按L2_01_00 §8.3映射；不进入检索或fallback | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Fake/non-live verified：KR `test_current_root_intent_failure_stops_before_all_knowledge_io[PROVIDER_TIMEOUT/PROVIDER_FAILURE]`，公开映射且检索/Summary0 |
| `UAT-K-RW-004` | 敏感或控制字符输入 | 进入模型前拒绝；意图/Summary调用0，控制字符规则不放宽 | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Fake/non-live verified：J `[k-nonlive-sensitive]`、IC `test_invalid_question_fails_without_truncation_or_echo[control]`、UG `test_current_root_control_or_unclassified_question_never_calls_model_or_knowledge`，当前根控制字符/零宽字符在动作选择前拒绝且模型、Knowledge、Business下游0 |
| `UAT-K-DOM-001` | 税务政策问题 | 仅 `tax.policy` | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：PL `test_plan_freezes_original_question_catalog_profiles_and_budgets[policy]`、J `[k-nonlive-policy-admin]` 逐案typed `tax.policy` keyword/vector各1，search=2/embed=1/rerank=1；P3_01 §14.8当前root固定fake意图→隔离真实typed单域keyword/vector各1且200。真实模型选域及Spring全链仍Not assessed |
| `UAT-K-DOM-002` | 税收法律/法条问题 | 仅 `tax.law` | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：PL `test_plan_freezes_original_question_catalog_profiles_and_budgets[law]`、J `[k-nonlive-law-viewer]` 逐案typed `tax.law` keyword/vector各1，search=2/embed=1/rerank=1；真实模型选域及当前root→真实typed仍Not assessed |
| `UAT-K-DOM-003` | 政策与法律混合问题 | 稳定选择两个域，按目录顺序执行 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：PL `test_plan_freezes_original_question_catalog_profiles_and_budgets[both]`、R `test_two_domain_maximum_budget_original_q_serial_rerank_and_round_robin`、J `[k-nonlive-multi-domain]` 两域keyword/vector各1且search=4/embed=1/rerank=2；J按多重集合断言路径，目录顺序由PL/R断言；真实模型选域及当前root→真实typed仍Not assessed |
| `UAT-K-DOM-004` | 普通零域问题 | `no_result/no_matching_domain`，检索和摘要为 0 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：KR `test_terminal_or_invalid_intent_has_zero_knowledge_downstream[unsupported]`，公开reason及Knowledge IO0 |
| `UAT-K-DOM-005` | 问题出域拒绝且同时零域 | 策略拒绝优先于普通零域 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：KR `test_sensitive_question_overrides_hypothetical_zero_domain_intent`，敏感输入在意图模型前拒绝；假定零域输出不执行 |
| `UAT-K-RET-001` | keyword path | typed 请求，不含 index/field/DSL；候选授权后返回 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake/non-live verified：RA `test_current_typed_protocol_and_jwt_only_to_read_authority[200]` exact typed键/无DSL；P3_01 §14.6隔离`tax.law` keyword typed预检200/5候选/ES search+1，§14.8当前root `tax.policy` keyword只读请求200；仍不证明Spring全链或真实模型效果 |
| `UAT-K-RET-002` | vector path | BGE-M3 exact 1024 维；JWT/身份不进入 BGE | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_invalid_embedding_stops_before_search`、RA `test_current_typed_protocol_and_jwt_only_to_read_authority[200]`，1024维/JWT隔离；P3_01 §14.8当前root本地embedding 1次、真实typed `tax.policy` vector请求200，仅为单域接线证据 |
| `UAT-K-RET-003` | 多域×双路径 | 每个 plan item 一次；同 query embedding 至多一次 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_two_domain_maximum_budget_original_q_serial_rerank_and_round_robin`，4 search/1 embedding/2 rerank |
| `UAT-K-RET-004` | 重复候选与 RRF | 按 `(documentId, chunkId)` 去重、稳定融合 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_cross_domain_duplicate_merges_all_provenance_without_rerank_anchors`，身份去重/来源合并 |
| `UAT-K-RET-005` | rerank | 输入仅授权候选；输出一一覆盖且稳定截断 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_invalid_rerank_never_starts_second_domain`，非法结果停止；RA `[200]` 授权候选 |
| `UAT-K-RET-006` | 单路技术失败 | 仅在 coverage 与每域最小候选满足时部分继续 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_partial_requires_minimum_and_successful_candidate_path_in_each_domain[1/2/3]`、`test_partial_missing_entire_domain_never_uses_other_domain` |
| `UAT-K-RET-007` | 全路径失败或快照冲突 | `downstream_failure`，Evidence/summary 为 0 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake/non-live verified：R `test_all_failed_is_not_no_result[FAILURE/TIMEOUT]`、`test_empty_response_snapshot_conflict_also_fails_closed`；J `[k-nonlive-all-paths-fail]` search&gt;0/Summary0；Evidence不进入由当前flow短路源码确认 |
| `UAT-K-RET-008` | 整域禁止或授权权威失败 | 安全失败优先，其他路径成功不得掩盖 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_authorization_failure_cancels_and_joins_pending_paths[FORBIDDEN/READ_DECISION_UNVERIFIABLE/READ_AUTHORITY_FAILURE]`；P3_01 §14.6仅验证隔离typed未知角色403，整域跨路径拒绝的当前root真实全链仍Not assessed |
| `UAT-K-EV-001` | candidate hash/domain/snapshot/policy ref 完整 | 生成确定性 Evidence Bundle | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Fake verified：E `test_complete_ranked_batch_is_verified_before_any_selection`、`test_domain_opportunity_then_global_fill_preserves_rank_and_fourth_same_document` |
| `UAT-K-EV-002` | 完整性冲突或缺失 | `evidence_failure`，Summary调用0；前置selector/意图调用单列 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Fake verified：E `test_complete_ranked_batch_is_verified_before_any_selection[late_hash/snapshot/rank_from_failed_path/rank_from_no_result_path]`、EI `test_minimal_pre_summary_failures_are_closed_with_zero_model_calls[bad_hash]` |
| `UAT-K-EV-003` | 全局∩域∩文档策略允许 | 仅最小 payload 进入当前 Summary task | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Fake verified：EI `test_minimal_stage_uses_mode_projection_and_local_citation_without_extra_fields`，仅最小字段出域 |
| `UAT-K-EV-004` | 未分类、策略缺失/冲突或文档收紧拒绝 | `model_egress_denied`，summary 调用 0 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Fake/non-live verified：EI `test_minimal_pre_summary_failures_are_closed_with_zero_model_calls[policy_deny/policy_missing]` 中 `policy_missing` 将候选文档改为目录未绑定身份并断言Summary0/无结果；`test_selected_policy_deny_does_not_fallback_to_allowed_later_candidate`，UG `test_minimal_evidence_policy_conflict_denies_before_summary`；真实索引的未分类策略覆盖仍Not assessed |
| `UAT-K-EV-005` | 证据覆盖不足 | `no_result/insufficient_evidence`，不生成肯定回答 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Fake verified：E `test_missing_selected_domain_is_insufficient_even_when_other_domain_has_evidence`、KR `test_current_root_model_insufficient_is_public_no_result_without_answer`，公开reason/固定非肯定文本 |
| `UAT-K-EV-006` | 合法抽取摘要（各原任务版本按冻结证据） | Summary8按lookup/explanation/applicability执行L2_01_02 §9.2/9.3；lookup不强加适用性证明，解释/适用性按各自义务；ref唯一且quote为授权正文连续子串，不伪造coverage | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Partial/evidence missing：SC `test_v8_exact_schema_only_request_and_explicit_mode_serializer`、EI `test_minimal_stage_uses_mode_projection_and_local_citation_without_extra_fields` 仅合同/引用；解释与适用性实质充分性待真实与人工评价 |
| `UAT-K-EV-007` | unknown/duplicate ref 或非子串 quote | `knowledge.summary_failure`，不返回模型原文 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Fake verified：EI `test_minimal_summary_failure_matrix_has_one_call_and_no_model_text[duplicate_ref/unknown_ref/stitched_quote]` |
| `UAT-K-EV-008` | summary timeout/provider/schema failure | 固定 timeout/downstream failure，无 retry/resume | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Fake verified：EI `test_minimal_summary_timeout_or_cancel_releases_single_call[False/True]`、`test_minimal_summary_failure_matrix_has_one_call_and_no_model_text[failure]` |
| `UAT-K-ISO-001` | Knowledge 请求 | Employee/Transaction 调用 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：KR `test_knowledge_request_never_calls_employee_or_transaction_http`，两个Business HTTP transport各0调用 |
| `UAT-K-ISO-002` | Business 失败 | Knowledge 调用 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：KR `test_business_failure_does_not_call_enabled_knowledge`，同根Knowledge enabled而其HTTP路径0 |
| `UAT-K-ISO-003` | `AGENT_KNOWLEDGE_ENABLED=false` | 不注册动作、不创建 Knowledge client、不要求配置 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：PR `test_disabled_knowledge_registers_descriptor_without_tasks_stages_or_clients`、KR `test_disabled_current_root_does_not_create_knowledge_client` |
| `UAT-K-ISO-004` | 取消/关闭 | 未开始阶段调用 0，所有 owned Knowledge HTTP client 被关闭一次 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：KR `test_current_root_cancellation_aborts_summary_and_closes_clients`，取消后不继续、连续两次aclose各owned client仅关闭一次 |
| `UAT-K-ISO-005` | 日志与有限 evidence 扫描 | JWT、正文、原始 Prompt/响应、物理 ES 信息均为 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Spring non-live verified：J 生成当次`runtime.log`/`evidence.json`并扫描synthetic JWT、正文、Prompt/响应特征及物理ES字段/路径为0；真实部署日志Not assessed |
| `UAT-K-ISO-006` | enabled + 生产 stub / 测试显式 fake | 显式enabled + 生产stub按当前启动合同失败；测试显式fake复用生产装配，意图12/Summary8唯一且外部outbound=0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake/non-live verified：KR `test_enabled_current_root_stub_without_fake_rejects_before_client_allocation`、`test_current_root_reaches_intent12_summary8_once_and_closes_owned_clients`；J外部模型outbound0 |


证据简称均指当前目标源码而非历史Passed：`J`=[Spring Knowledge non-live E2E](../../agent-service/src/test/java/com/dylan/agent/service/e2e/AgentKnowledgeNonLiveE2ETest.java) 的 `verifiesSpringToCurrentKnowledgeCompositionWithFiniteFailureSemantics`（方括号内为caseId）；`S`=[Spring安全契约](../../agent-service/src/test/java/com/dylan/agent/service/security/AgentSecurityContractTest.java)；`KR`=[当前生产组合根测试](../../agent-runtime/tests/integration/knowledge/test_minimal_current_root.py)；`UG`=[当前根UAT缺口反例](../../agent-runtime/tests/integration/knowledge/test_minimal_uat_gap_cases.py)；`IC`=[意图输入契约](../../agent-runtime/tests/unit/knowledge/test_intent_contracts.py)；`PL`=[最小计划测试](../../agent-runtime/tests/unit/knowledge/test_minimal_retrieval_plan.py)；`R`=[检索阶段测试](../../agent-runtime/tests/unit/knowledge/retrieval/test_minimal_stage.py)；`RA`=[typed适配fake测试](../../agent-runtime/tests/integration/knowledge/test_minimal_retrieval_adapters.py)；`E`=[Evidence选择测试](../../agent-runtime/tests/unit/knowledge/evidence/test_minimal_selection.py)；`EI`=[Evidence阶段测试](../../agent-runtime/tests/integration/knowledge/test_minimal_evidence_stage.py)；`SC`=[Summary8合同测试](../../agent-runtime/tests/contract/knowledge/test_summary_task_v8.py)；`PR`=[Provider注册测试](../../agent-runtime/tests/contract/knowledge/test_provider_registration.py)。本轮九个已定位Python文件同一命令执行 `pytest -q` 为228 passed（其中`KR`19项）；新增`UG`文件定向执行12 passed，已覆盖的正式全量回归计数另按§14.6实际结果记录；`J` 1个测试方法执行16个synthetic case，`mvn.cmd -q '-Dtest=AgentKnowledgeNonLiveE2ETest' test` 的Surefire为1 run/0失败/0错误/0跳过。`S` 的入口断言属另行现有Java合同测试，不因本次单独Spring E2E而记为同一命令重跑。全部fake均无真实模型HTTP请求。

当前逐案计数为36项 `Fake/non-live verified`、1项 `Partial/evidence missing`（EV006）；前者并非完整新版UAT Passed。Spring→Runtime的16个合成case现逐案断言typed域/路径/Profile及调用次数；测试证据使用请求级隔离，严格校验器拒绝错误域仍标`passed`，并发双请求反例通过。隔离Java typed单域读取与入口拒绝有P3_01 §14.6有限预检，当前root单域真实typed keyword/vector只读接线另有§14.8预检；Spring全链、实际BGE/候选ES对照、12题端到端及维护者人工相关/充分/忠实/usefulness、发布冒烟仍Not assessed，不能用单测、合成日志或有限接线代替。受控inspection响应的请求投影不属于普通日志/有限持久evidence；本轮未改变该公共诊断合同。功能与安全必需用例尚未100%完成。

全部用例须记录目标代码/task/config/模型与数据绑定、断言及有限调用数；37风险不等于37次付费调用，确定性反例使用fake/契约。角色矩阵在接入和业务读取两个拒绝位置分别取证；summary阶段零调用不等于前置selector从未调用，应记录各阶段计数。

## 4. 原证据与当前要求的关系

| 原资产 | 适用范围 | 新计划使用方式 | 不允许的推论 |
|---|---|---|---|
| [旧UAT_01完整快照](历史文档/2026-09-14-knowledge-plan-handoff/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 原37风险及各冻结任务/配置的功能证据、历史效果、当时待执行安排 | §3复用风险身份；§5/6承接已批准方法 | 原Passed不等于12/8已执行 |
| knowledge_uat_traceability.v1.json及原loader | 原authority UAT_01 v1.21及Summary4证明边界 | 保持字节和原始依据；后续新版本追踪另作实现 | 不改authority来制造新验收通过 |
| 历史P5/代表性run/人工rubric | 各自冻结HEAD、模型、语料及协议；有效与无效结果分开 | 只作历史对照；具体事实回到归档及原evidence | 不拼题、不改判、不证明当前源码11/7或目标12/8 |
| 阶段A正文/附件/发布资产 | 当时有限语料完整性、检索与回滚 | 复用数据来源及安全风险，不重做既有发布 | 不证明新chunk/向量表示已经更优 |

历史引用必须按原冻结提交和原路径读取；归档内部链接原样保存，当前计划不将其相对路径解释为当前权威。详见[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

## 5. 新设计的四维验收方法与阶段性证据

### 5.1 证明范围与版本隔离

当前仓库的唯一Knowledge生产组合根已接入意图12、Summary8及knowledge-minimal-v1，§3所列fake/Spring non-live证据仅证明其对应断言；实际部署的代码、Profile、索引和策略绑定仍须另行核实，不能据此宣称已发布或真实效果达标。历史37功能用例、P5、阶段A、阶段B和人工run-07均只证明自己的冻结范围；P5最近有效partially_effective不代表目标12/8效果达标，run-07失败亦不覆盖更早有效测量。不得把不同批次的通过题相加为新版全套通过。

v3.0计划创建时的基线为Functional/Safety Not evaluated、Retrieval/Answer evidence missing；v3.4当时把37案中的31项登记为fake/non-live阶段验证，6项partial/evidence missing；v3.5补证后分别为36项与1项，Functional/Safety整体仍不能判Passed。隔离typed单域只读预检不构成真实召回质量或回答效果测量，这两项、人工评价及发布仍Not assessed。后续实际运行沿用既有Passed/Failed及四类Effectiveness结论，新增维度留在当前验收记录，不改历史result Schema。v3.0创建时未创建JSON追踪或候选、读取凭据或执行测试服务/LLM；当前目标的有限执行须遵循§2、§5.4、§6.1的冻结及停止条件，工作包状态由P3_01 §5治理。

旧37个case稳定ID保持，COMPOSE已建立§3所列部分新版本fake证据，旧证据不重写；问题改写相关用例保留“原意保护/非法规划/超时0下游”的风险目标，不能把新方案没有rewrite当删测理由。新12/8准入矩阵为TEST-KFLOW-201～203、TEST-KRET-201～203、TEST-KEV-201～203及原37项的明确等价映射，缺口未执行/未评价不称37/37新版本通过。

### 5.2 四维判据及阶段损失

| 维度 | 验证内容/方法 | 通过条件 | 不证明什么 |
|---|---|---|---|
| 功能 | fake实际生产root及Spring入口、精确意图/模式、原Q一致、路径与调用上限、失败映射、并发/取消/关闭；37风险逐case | 必需用例100%通过，无skip冒充；非法/模型失败下游0；不支持问题无第二动作 | 不证明真实LLM理解准确、原文库充足或usefulness |
| 安全 | Java读取角色/拒绝位置、Guard0model、三层出域0Summary、identity/hash/ref/连续子串/唯一性、日志脱敏及Business隔离 | 必需边界100%通过，任一越权/泄露/伪造引用为硬失败；不能被效果平均抵消 | 合法引用不等于回答充分或现行适用 |
| 召回 | 在人工确认必要来源存在的冻结池，记录域选择→keyword/vector→RRF→rerank→final20→Evidence8的来源覆盖、MRR与噪声 | 12题中至少8题预置为search且有可核实必要来源，三种模式均须覆盖；无命中/前置澄清题不放入召回分母；可验证题最终必要来源宏平均recall@20≥0.80、precision@20≥0.40，核心已确认必要来源不能全丢；实际分母/空池明确 | 缺资料不算排序失败；命中不等于可回答；未做同条件A/B不称较旧方案提升 |
| 回答 | 对原问题逐项核对相关、充分、忠实与usefulness；执行者可准备原文，最终真实评价由维护者独立于待测模型确认 | 12题全纳入；每题四项true才通过，≥10题通过；所有applicability题不得有无依据肯定结论，当前适用/历史有效混淆为硬失败 | 结构有效率不能冒称忠实度；“不足/澄清”只在预置预期如此时算正确 |

这些是**新需求基线的预置目标**，不是降低或重算旧P5 Q1～Q4；旧结论不变。阈值是个人验证项目的有限初始选择，仍需业务维护者在gold冻结前确认可用语料和问题含义；不能在看到新结果后降低。无法确认上述至少8题及三种模式的来源池时，即使P3_01中的MEASURE技术依赖已满足、标为Ready，首次真实执行仍受阻，不得自动删除case、补造gold或调用模型“找答案”。功能与安全合格可完成COMPOSE基础实施，未达到召回/回答目标不得宣称质量达标或擅自发布为优化成功。

每题在各阶段报告必要source/block集合覆盖及排名；候选ID仅诊断使用，不进入在线排序。相同父文档不同必要条款不能只因父ID命中就算全部覆盖。precision@20分母为实际返回候选数（0记0），由人工相关标注计算；每题必要来源缺一部分按比例计recall，宏平均只取预先核实可检索池，另报全部12题含缺料的覆盖率。MRR按首个相关必要来源排名，未命中0；Evidence recall另列，不以rerank数值分代替。没有人工原文/相关性标注时这些指标为not_assessed，不自动算0或Passed。

### 5.3 固定代表类别与先验预期

先设计12个内容case（每类4题），后续MEASURE准备阶段由维护者结合实际公开语料填写精确问句、必要source/block/hash、相关性标签、允许答案和不足/澄清预期，并在任何真实模型调用前冻结。不得单为住宿题、当前失败或gold ID写在线特判；不要求住宿资料缺失时也给肯定税率。

| 新Case | 模式/输入类型 | 预期与主要风险 |
|---|---|---|
| UAT-KM-001 | lookup，指定文号/附件 | 找到原文摘录与来源；不因缺纳税人条件阻断资料查找 |
| UAT-KM-002 | lookup，同义服务表达（可含住宿） | 检索相关资料而非擅自判税率；检索表示不足如实记录 |
| UAT-KM-003 | lookup，历史期间资料 | 可返回历史条文，不把它称为现行适用 |
| UAT-KM-004 | lookup，语料中确无对应条款 | 预置无命中/不足；不能返回无关片段冒充答案 |
| UAT-KM-005 | explanation，单域定义 | 直接摘录覆盖明确问题；不做无来源自由改写 |
| UAT-KM-006 | explanation，两个显式子问题 | 必要证据齐全才回答；缺一项不能部分肯定 |
| UAT-KM-007 | explanation，法律+政策 | 一次选双域、独立读取、最终证据覆盖；无失败扩域 |
| UAT-KM-008 | explanation，否定/税率/日期条件 | 原Q逐阶段不变，引用不得与显式条件冲突 |
| UAT-KM-009 | applicability，明确主体/期间/方法 | 只给直接适用条件及规则原文，不靠用户分类假设推导 |
| UAT-KM-010 | applicability，必要条件缺失 | 前置clarification_required，检索/Summary0；固定提示可用但不承诺动态问题 |
| UAT-KM-011 | applicability，当前与历史边界 | 无直接时效依据时不足，writtenDate不当生效日期 |
| UAT-KM-012 | applicability，类似分类边界 | 没有直接分类桥接/冲突未解决则不足，不以词面相似肯定 |

截至P3_01 §14.9，仅形成供维护者审阅的12题精确问句与来源定位草案，未冻结任何gold：当时索引中8题有拟定必要来源chunk定位，官方网页只做有限条款核对，2016年附件原件尚未独立直读。增值税法索引`effectiveDate`误填成文日、两份小微公告的原文期限与索引空`expiryDate`不能直接推出今日效力，详见P3_01 §14.9。维护者仍须逐题确认原文范围、相关性标签、适用期间、允许回答与不足/澄清预期，并确认§5.2及§6.1质量阈值；此草案不改变§5.4首次真实模型调用前的冻结条件。

后续只读核对已按官方页面快照与asset manifest的SHA-256定位2016年原始附件；官网链接以`.docx`结尾，实际字节为OLE `.doc`。隔离HWPF对KM-001/002拟用的生活服务、餐饮住宿服务和住宿服务原文段落作了独立定位，三条当前索引chunk与原件单段逐字相符；这只纠正上段当时“未独立直读”的证据状态，不证明全文结构、现行适用性或12题gold已获维护者确认。原件结构及BGE快照的其余边界见P3_01 §14.14。

上述内容题可用公开、非敏感问题。功能/安全额外反例不必付费：未知域/模式/重复键；输出terminal组合；>1024长度；单/双域DENIED；policy缺失/冲突；坏hash；重复ref/非子串；少一路/全失败；模型超时；并发取消；disabled0依赖；Business不fallback。至少一个37风险case对应每项新DR，不以只测12题代替安全矩阵。

### 5.4 固定变量、预算与停止条件

先完成COMPOSE的non-live。当前独立目标已授予一次有界真实批次；执行前仍须冻结代码/两task及Prompt hash、模型实际版本、minimal配置、Profile与索引/ACL快照、12题gold/顺序、调用预算和人工rubric。仓库绑定不等于运行绑定，必须先只读核实；运行中快照不符立即终止，不自行改alias或数据。

建议首期仅一次12题端到端测量，上限12 E2E、36模型HTTP（selector/意图/Summary合计）、48 typed search、12 query embedding、24 online rerank；维持每请求≤3/4/1/2，startup预热独立事前列明、不得计入效果请求，不能凭空增加预算。无Business/旧answer、无自动retry/resume，无失败后追加或补题。实际terminal较早时只消耗已产生调用，不为凑预算补齐。

技术/协议/安全失败停止该批，保留有限append-only终态及未执行清单，先fake诊断；不能称完整测量。正常no_result/clarification或人工判据不通过是有效测量输出，在安全合同仍成立时按预定顺序继续一次批次，最终如实分类，不修改预期。需要新批次只能作为新目标/新授权，本设计不预授予。

同条件对比可优先使用无外部LLM的固定候选池重放，各阶段损失可归因；若没有同索引/模型/条件的旧有效结果，不得拼接历史数据算增益。当前目标授权的A/B资料对照分别遵守§6.1与L2_01_01 §18.4.1，不与在线方案简化混为同一变量；任何额外实验或超出当前限额的语料/索引写入均须新目标及授权。

### 5.5 证据、人评和有限收口

每题运行记录只保存caseId、模式类别、预期/实际域、各阶段有限ID/排名、调用数、有限status/reason、安全结论、自动结果及人工四项；不保存真实用户敏感问题、完整知识/模型响应、凭据或个人信息。为可复现性，人工编写并核实无敏感值的公开测试问句、来源/block定位/hash、相关性标签及预期可以且必须作为版本化测试数据集冻结；运行记录引用caseId/hash，不重复保存问题或正文。公开fixture须明确来源许可，诊断不能把ID/gold反馈在线策略。

最终分别报告Functional、Safety、Retrieval、Answer。完整且安全的测量中，召回/回答均达标为effective，仅一维达标为partially_effective，两维均未达标为ineffective；执行合同不完整或安全失败为invalid_run。人工未评为not_assessed/evidence missing，不能先宣布有效质量等级，也不能由执行者/待测模型代填维护者结论。完整但质量未达标可记录测量完成，质量风险保持Open，不能用历史P5替代。本次设计完成不要求新测量，也不允许预记结果。

核心来源题预置为KM-001/005/009，任一在确认有原文的情况下最终必要来源覆盖为0即召回失败，不由宏平均掩盖。回答四项含义固定为：回应原问题、覆盖预期义务、没有无依据断言、对用户查阅或补条件有用；对预置不足/澄清题，评价正确拒绝/提示，不虚构quote或当作成功肯定答案。

评审与验证记录由P3_01 §13集中维护；不另建审批流水。新UAT JSON/Schema/loader实现只属于后续授权COMPOSE/MEASURE，当前追踪资产字节不变。

## 6. 资料组织与检索表示验收方法（设计，未执行）

依据L1_01 §4.6、L2_01_01 §18、L2_01_00/02 §19，实施由P3_01 §5独占。该补充不重做阶段A、不修改原37项功能或历史效果结果；既有来源/样本审计及后续NORMALIZE包的有限只读来源核对各有明确证明范围，均不构成UAT执行。所有下列用例状态为Designed / Not executed，不创建新traceability、gold或candidate文件。

### 6.1 四维判据与有限实验

1. 数据质量：逐字段来源可查、日期语义正确、版本/父子关系可解析；正文跨度/表格/脚注不静默丢失。填充率和准确率分列；未知可存在，但不能把核心预期依据的未知问题标为已完成。
2. 功能与安全：唯一typed链路、读取先于正文处理、三层出域、身份/hash/ref/连续子串/唯一性、取消/关闭及Business不回退；任何越权/伪造/不明写入为失败，不能用质量均值抵消。
3. 召回质量：必要原文来源Recall、MRR/排名、噪声及Evidence覆盖；分别报告keyword/vector、融合、rerank、Evidence损失，不以“有命中”代替完整依据。
4. 回答质量：问题回应、条件/期间、原文充分性、忠实性与人工usefulness；合法引用不等于充分。没有模型调用或人工评审时为Not assessed，不由离线统计推出改善。

未来每个对照协议先冻结≤30父文档的变更/人工核验范围和代表问题（建议≤24，覆盖多税种、长短/附件/表格、现行/历史/未知、查找/解释/适用性和无命中反例）；不要只选原审计暴露问题或住宿单题。搜索池保留完整基线和未受影响竞争文档，不能仅搜30篇后外推全库收益。人工预先固定来源、必要条款/连续span和预期不足/澄清，不由待测模型自评。原文无法核实的题标source_gap，质量指标null；保留在计划总数/数据缺口中，单列可评估质量分母及未评估数，不能强计Recall=0/1或事后删除。

当前`rechunk_candidate_v1.py`的A构建器仅支持预登记的`tax.policy`附件重切；law、正文及其他类别仍须作为未变竞争记录全量保留。这个实现边界不改变上表跨类别评价要求：若预登记的A变更样本包含正文或law，先判为工具范围不匹配，不静默跳过、不把附件样本收益外推到其他资料类型。B须在冻结的同一chunk集合上单独比较表示。人工gold、质量主指标、噪声与时延容忍值确认前，不启动真实BGE/ES对照。

对照分两个独立问题：A只改chunker，固定原始/规范解析源hash、问题、模型、检索配置及权限，向量输入类型不变；B只改向量表示，固定A选定或原有同一chunk集合及精确body hash、模型/服务和所有在线参数。参与变化的每条旧记录必须逐条证明原向量模型、表示版本，并按旧chunk正文及其冻结表示算法重算验证旧输入hash与正文hash；A中新旧chunk的正文及输入hash不必相等，B的chunk和正文hash必须相同。旧/新完整模型运行快照可仅因同一容器重启的`started`时间不同而hash不同，但剔除这一个字段后的容器及模型内容须规范字节相等，并分别记录两份原始hash和差异；其他漂移阻断同模型对照。只有全局快照或向量形状的记录标记`legacy_unknown`，其依赖题不可归入单变量收益分母，预登记核心依赖它则停止相应对照。未受影响的全库竞争记录可维持原样，不补造其向量来源。新chunk写入前须对完整`_source`通过现有Java typed读取投影边界前检，保持ACL、来源、原文hash和完整竞争池。更换切片时gold用稳定document/asset/source span，不用旧chunkId强求一一对应；同时变化parser、语料或模型时不能宣称单变量实验。

结构前置先在不调用模型/ES的fixture上验证：文档类型、实际条款/章节结构与解析可信度共同决定条款型/章节型/通用型策略；DOCX段落和表格交错顺序必须与源一致，扁平表格不能冒称表头/单位/备注完整。每个verified结构单元必须有稳定的不可变`documentVersionId`、`unitId`、连续原文span和可重算hash；有上级结构单元时`parentUnitId`须指同版本且span包含该单元，无上级时为null。`parentDocumentId`仅是附件来源关系。短条单chunk、长条多chunk均能从不可变源恢复完整原文；单元完整性与chunk覆盖分开判定，子chunk未覆盖全部可引用内容blocks时不得发布受影响候选或宣称检索覆盖完整。乱序、悬空、跨版本或循环关系不得标单元完整。若parser变化是必要前置，先固定新旧解析产物并单独报告源/结构质量差异；不能把parser+chunker同时变化的结果宣称为纯切片收益。

body、title/section/body、可信分类/body至多3种表示，先用纯构造/token统计筛除不合法项；每轮只比较基线与一个预选候选，不因失败扩成无限网格搜索。每次真实实验冻结run、代码/索引UUID/全记录变更清单、模型/tokenizer/表示/Prompt、case顺序、人工rubric、每个阶段调用预算及停止条件；本计划不授予任何调用或索引写预算。若有模型，统计selector/意图/Summary全部HTTP，不复用旧额度；无模型阶段仍须限定ES/BGE总量和候选数量。

建议质量判据在执行前由维护者确认并固化：核心有充分原文的题必要来源覆盖不得为0；成对核心覆盖和保留集覆盖不得退化，至少一个预先选择的质量主指标改善且噪声/时延不突破预定容忍值，才考虑发布。指标阈值/容忍值未冻结则实验Blocked，不允许看到结果后降低。小样本只作局部决策依据，不声称统计显著或全库收益。数据/功能安全全部达标但质量无提升可以结束测量，不能使RELEASE自动Ready。

### 6.2 用例追踪

| UAT case | 风险与设计映射 | 后续验证方法/预期证据 | 通过条件 |
|---|---|---|---|
| UAT-KORG-001 | 源字段丢失/补造；DR-KRET-301、DR-KEV-301 | 11字段fixture、HF原行/官方/curated对照、hash自身排除及重放时钟反例 | 原值可追溯，未知不补造，许可/来源分离，同输入hash稳定 |
| UAT-KORG-002 | 日期错填/陈旧；DR-KRET-302、DR-KEV-304 | 成文≠生效、pending变更、部分失效、历史/未知反例 | 不把成文填生效，不据文档整体状态认定条款；查阅与适用性分开 |
| UAT-KORG-003 | 分类等同授权/相关性；DR-KRET-305 | 多标签/缺标签/机关/法律效力及channel映射契约 | 不按推断标签扩权或无条件排除，不引入分类分库 |
| UAT-KORG-004 | 同题名误合并/关系丢失；DR-KRET-303 | 同标题不同版本、转载、附件父关系、`unitId/parentUnitId`冲突重放 | 稳定源身份/hashScope，父文档与父结构单元不混用；同版本包含关系可解析，旧记录不覆盖 |
| UAT-KORG-005 | 条号/条件/例外过碎；DR-KRET-303/304 | 条款型/章节型/通用型选择、短条单chunk与长条多chunk、否定/例外/列表/脚注fixture+人工核对 | 完整单元按源span/hash可恢复、chunk仍为连续原文；跨单元不伪造，无法保全显式隔离 |
| UAT-KORG-006 | 表格扁平与目录误认；DR-KRET-304 | DOCX段表交错、表格表头/单位/备注/页/目录样本；对现有扁平化结果作反例 | 保持源顺序，无猜造单元格/条款；重复表头不是quote，未知结构不标完整 |
| UAT-KORG-007 | 字符/token混同与截断；DR-KRET-306 | 固定tokenizer精确长度、三表示、长输入和版本缺失 | 特殊token计入，超长关闭；维度exists不代替模型/输入来源证明 |
| UAT-KORG-008 | 派生上下文冒充原文；DR-KEV-302、DR-KEV-303 | keyword/vector/rerank/Evidence表示对照；非法标题/表头quote | 原content不变，hash作用域一致，拼接/跨片引用拒绝 |
| UAT-KORG-009 | 读取/出域/父关系越权；DR-KFLOW-301、DR-KFLOW-302 | Java typed权限、Python策略/敏感0调用、默认disabled fake；检查当前无父正文补取 | 现公共合同不变，子chunk可读不推出父单元可读/可出域，未授权正文不进入后续阶段/模型，Business不回退 |
| UAT-KORG-010 | 分段/向量收益混淆；DR-KRET-307 | 冻结父/asset/span、完整竞争池、逐记录旧向量来源、新chunk typed投影，单变量逐阶段排名及source_gap反例 | 无gold特判/删题；`legacy_unknown`不可冒充同条件对照；Recall/MRR/噪声与Evidence分列，null/分母可核 |
| UAT-KORG-011 | 合法引用却无法回答；DR-KEV-304 | 三模式多税种/期间代表题，人工原文与usefulness；模型仅在当前有限批次且gold已确认后调用，超范围另授权 | 足够与不足分别判断，时效未知不肯定，不由模型自评 |
| UAT-KORG-012 | 发布错配/无法回滚；DR-KFLOW-303、DR-KRET-307 | fake故障→当前授权及条件满足后的隔离typed/alias回滚→发布冒烟 | 旧索引/资产不改，全记录变更可核，Profile/catalog匹配，恢复相容旧绑定 |

001～008可先以纯离线fixture完成；009的fake与真实typed证据分开；010的BGE/ES、011的模型/人工回答、012的发布验证均须符合当前目标的有限授权、人工确认及各自前置门槛，超范围再单独授权。不把单测代替真实集成。图谱、记忆和多轮不参与验收。

在线父单元补取不属于当前UAT-KORG的通过条件。若未来单独批准，应先冻结新typed/候选`content`语义、逐单元读取与出域授权、同版本/深度1/≤8单元和既有Evidence预算、请求数/超时/取消及失败映射，再增加直接相关用例：未找到、未授权、技术失败、预算不足、循环/悬空/错版本、必要例外/定义缺失；安全拒绝必须零未授权正文与零模型出域，不完整时不得给出完整肯定答案。未通过合同评审前，这些是待评估风险，不计为当前已实施或已执行UAT。

### 6.3 报告与停止

逐case记录来源类别、原文身份/hash、变量、验证方式、有限结果、缺口及执行状态；不保存真实敏感问句、完整正文、JWT或原始模型响应。原文人工阅读限定既有批准资料，证据只记录必要定位与hash。固定问题集中的合规非敏感问题可用于后续版本化测试，不能与禁止保存真实敏感输入混淆。

数据质量、Functional、Safety、Retrieval、Answer分别报告；本次均不预记通过。停止范围按§6.1及L2_01_01 §18、L2_01_02 §19区分：

- 已登记的业务分类/时效未知（不含出域策略未分类）、旧表示或hash口径的`legacy_unknown`、旧库存的`source_unverified`及非核心题的`source_gap`，保留标记和原证明边界，不自动停止未受影响的既定验证。未知来源不得作为新的官方gold或适用性证明；变更资产未满足来源准入时隔离、不写入候选，不能据此绕过安全检查。`source_gap`题保留在计划总数及缺口统计，质量值为null，单列可评估分母与未评估数，不事后删题或补造来源。
- 核心预期依据无法核实，阻塞依赖该依据的对照、质量结论及发布；可继续不受影响的已授权离线验证，但不得减少核心要求、降低阈值或把不完整实验标为完成。
- 读取/出域权限不明或失败、出域策略未分类/缺失、当前处理内容的身份/hash完整性冲突、非法引用、模型/服务错误、快照错配、预算耗尽或执行记录不完整，停止该批实验，在继续外部调用、候选写入或发布前失败关闭。保留有限终态及未执行清单，使用fake诊断；不得以单条未知元数据为由放宽这些安全及执行停止条件，也不自动补跑、续跑或创建新candidate。

质量未提升只给出风险和是否保留基线的决策，不恢复被取消目标。以上区分不新增公开状态，不修改§5.4的在线测量停止合同，不将部分验证冒充完整UAT。

## 7. 后续执行与当前结论

在线由P3_01的CONTRACT/RETRIEVAL/EVIDENCE→COMPOSE→MEASURE推进；资料由NORMALIZE→CHUNK/REPRESENT→COMPARE→RELEASE推进。前置不足只阻塞对应阶段，真实测量不是基础实现反向依赖；资料对照不依赖在线MEASURE，需自行冻结相容在线基线。

后续逐case报告：版本与设计、风险、预期、实际测试/有限证据、执行状态、通过或失败原因、未验证范围；旧证据引用不能替代新执行。当前37项风险中36项已有fake/non-live阶段证据，EV006仍为partial/evidence missing，完整功能与安全UAT尚未完成；12个UAT-KM内容题和12个UAT-KORG资料用例仍待执行，精确内容题与gold仍由后续准备阶段冻结。本次没有新的UAT通过结论。

v3.0迁移时的文档评审与验证见[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)；该轮只做权威承接，不修改算法、数据或阈值，且当时所有验收执行状态为Not executed。当前目标的阶段性功能/安全证据按§3记录，不反向改写迁移时结论。
