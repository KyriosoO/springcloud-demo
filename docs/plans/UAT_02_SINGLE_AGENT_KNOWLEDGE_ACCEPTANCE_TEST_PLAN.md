# [UAT_02] Knowledge 新设计验收计划

## 1. 文档信息与权威

| 项目 | 内容 |
|---|---|
| 当前版本 | v3.55 |
| 文档状态 | Reviewed（第二步验收分工、失败影响范围及运行前置同步已定向复评；未新增验收通过） |
| 日期 | 2026-10-07 |
| 文档身份 | 新计划首版；不继承旧UAT_01状态、预算或执行授权 |
| 设计依据 | [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v3.9 §4.5～4.7；L2_01_00 v3.12 §8/20、L2_01_01 v3.19 §9/18、Evidence L2 v3.10 §9；本轮同步现行验收职责，风险、gold、阈值及原证明范围不扩大 |
| 流程合同 | [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) §8/19 |
| 检索/资料合同 | [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) §9/18 |
| Evidence/回答合同 | [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) §9/19 |
| 动作选择合同 | [L1_00](../design/L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v3.3 §4.1；[L2_00_02](../design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v3.5 §6.3；按能力职责选择，不预判资料存在性；仅non-live证明 |
| 实施入口 | [P3_01](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md) v3.57；只负责包、直接依赖及操作准入 |
| 当前验收状态 | 仓库目标root已接线12/9/minimal-v1，机械non-live与Spring合成证据保持原范围。P3_01 §14.32新B正式10题协议完整，两臂recall@20均0.85、主指标未改善；215项盲标未完成，precision及整体质量Not assessed，候选不发布。§14.33唯一新MEASURE使用现行b2，完成4题后005技术失败，failed_consumed / invalid_run且已停止；§14.37维护者确认001/002 Passed、003/004 Failed，006～012未执行、不补跑。37项风险机械证据不代替新版37/37功能UAT，整体Functional/Safety、召回、回答及发布未通过 |
| 修改历史 | 2026-09-14，从旧UAT_01 §5的风险身份、§15/16的已批准新方法承接；不改设计阈值 |

当前结论及历史编号索引见[P3_01 §14](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md#14-当前结论)；历次执行原文见[P3历史附件](P3_01_EXECUTION_HISTORY_2026-10-06.md)及Git历史。本计划不再逐轮复制执行流水。原风险身份、判据、原始证据和未完成状态保持，文档整理不重新执行或改判UAT。v3.0迁移依据见[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

## 2. 范围与结果纪律

本计划治理当前仓库目标意图12/Summary9/minimal-v1及资料组织两条主线。原12/8及更早结果仅保留各自证明范围，不要求现行链路兼容旧任务。图谱、记忆、多轮、旧候选推进及Business重新验收不属于关键路径；Business继续由[UAT_00维护基线](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md)管理，Knowledge变化不得重开无关Business用例，也不得掩盖共享合同回退。

五类验收分别记录：功能、安全、召回、回答、资料质量与发布回滚。最后一类只用于资料主线。文档Reviewed与任何一种验收通过无关；Not evaluated/Not executed是计划状态，不新增公开API或历史result枚举。

本轮只整理文档，不提供代码、服务、模型、ES/BGE或发布授权。先前批次的消费和终态由P3_01 §14及原资产追溯；没有未执行额度可以据本计划自动续用。后续操作按§5.4/§6.1的适用前置及独立有效授权执行，不自动新candidate。

## 3. 37个稳定功能/安全风险的目标版本映射

原37个ID保留风险身份，而非沿用原Passed。尤其RW组在新设计下验证“原意保护/非法意图/超时零下游”，不要求新链路继续生成改写文本；EV组把原Summary8阶段证据与现已接线的Summary9有界回应义务分开，不把旧多证明集合强制输入带回来。下表“Fake/non-live verified”只表示列明的当前阶段断言已通过；“Partial/evidence missing”不冒充通过。隔离typed授权反例及当前root单域真实typed只读接线已有有限预检，Spring→Runtime当前Summary9合成三模式及失败链已复跑；真实typed全链、人工和发布证明仍Not assessed。

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
| `UAT-K-DOM-001` | 税务政策问题 | 仅 `tax.policy` | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：PL `test_plan_freezes_original_question_catalog_profiles_and_budgets[policy]`、J `[k-nonlive-policy-admin]` 逐案typed `tax.policy` keyword/vector各1，search=2/embed=1/rerank=1；P3_01 §14.8当前root固定fake意图→隔离真实typed单域keyword/vector各1且200。真实模型选域及Spring→真实typed全链仍Not assessed |
| `UAT-K-DOM-002` | 税收法律/法条问题 | 仅 `tax.law` | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：PL `test_plan_freezes_original_question_catalog_profiles_and_budgets[law]`、J `[k-nonlive-law-viewer]` 逐案typed `tax.law` keyword/vector各1，search=2/embed=1/rerank=1；真实模型选域及当前root→真实typed仍Not assessed |
| `UAT-K-DOM-003` | 政策与法律混合问题 | 稳定选择两个域，按目录顺序执行 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：PL `test_plan_freezes_original_question_catalog_profiles_and_budgets[both]`、R `test_two_domain_maximum_budget_original_q_serial_rerank_and_round_robin`、J `[k-nonlive-multi-domain]` 两域keyword/vector各1且search=4/embed=1/rerank=2；J按多重集合断言路径，目录顺序由PL/R断言；真实模型选域及当前root→真实typed仍Not assessed |
| `UAT-K-DOM-004` | 普通零域问题 | `no_result/no_matching_domain`，检索和摘要为 0 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：KR `test_terminal_or_invalid_intent_has_zero_knowledge_downstream[unsupported]`，公开reason及Knowledge IO0 |
| `UAT-K-DOM-005` | 问题出域拒绝且同时零域 | 策略拒绝优先于普通零域 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Fake/non-live verified：KR `test_sensitive_question_overrides_hypothetical_zero_domain_intent`，敏感输入在意图模型前拒绝；假定零域输出不执行 |
| `UAT-K-RET-001` | keyword path | typed 请求，不含 index/field/DSL；候选授权后返回 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake/non-live verified：RA `test_current_typed_protocol_and_jwt_only_to_read_authority[200]` exact typed键/无DSL；P3_01 §14.6隔离`tax.law` keyword typed预检200/5候选/ES search+1，§14.8当前root `tax.policy` keyword只读请求200；仍不证明Spring→真实typed全链或真实模型效果 |
| `UAT-K-RET-002` | vector path | BGE-M3 exact 1024 维；JWT/身份不进入 BGE | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_invalid_embedding_stops_before_search`、RA `test_current_typed_protocol_and_jwt_only_to_read_authority[200]`，1024维/JWT隔离；P3_01 §14.8当前root本地embedding 1次、真实typed `tax.policy` vector请求200，仅为单域接线证据 |
| `UAT-K-RET-003` | 多域×双路径 | 每个 plan item 一次；同 query embedding 至多一次 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_two_domain_maximum_budget_original_q_serial_rerank_and_round_robin`，4 search/1 embedding/2 rerank |
| `UAT-K-RET-004` | 重复候选与 RRF | 按 `(documentId, chunkId)` 去重、稳定融合 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_cross_domain_duplicate_merges_all_provenance_without_rerank_anchors`，身份去重/来源合并 |
| `UAT-K-RET-005` | rerank | 输入仅授权候选；输出一一覆盖且稳定截断 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_invalid_rerank_never_starts_second_domain`，非法结果停止；RA `[200]` 授权候选 |
| `UAT-K-RET-006` | 单路技术失败 | 仅在 coverage 与每域最小候选满足时部分继续 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_partial_requires_minimum_and_successful_candidate_path_in_each_domain[1/2/3]`、`test_partial_missing_entire_domain_never_uses_other_domain` |
| `UAT-K-RET-007` | 全路径失败或快照冲突 | `downstream_failure`，Evidence/summary 为 0 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake/non-live verified：R `test_all_failed_is_not_no_result[FAILURE/TIMEOUT]`、`test_empty_response_snapshot_conflict_also_fails_closed`；J `[k-nonlive-all-paths-fail]` search&gt;0/Summary0；Evidence不进入由当前flow短路源码确认 |
| `UAT-K-RET-008` | 整域禁止或授权权威失败 | 安全失败优先，其他路径成功不得掩盖 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Fake verified：R `test_authorization_failure_cancels_and_joins_pending_paths[FORBIDDEN/READ_DECISION_UNVERIFIABLE/READ_AUTHORITY_FAILURE]`；P3_01 §14.6仅验证隔离typed未知角色403，整域跨路径拒绝的当前root真实全链仍Not assessed |
| `UAT-K-EV-001` | candidate hash/domain/snapshot/policy ref 完整 | 生成确定性 Evidence Bundle | L2_01_02 DR-KEV-201/204/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/出域/引用反例 | Fake verified：E `test_complete_ranked_batch_is_verified_before_any_selection`、`test_domain_opportunity_then_global_fill_preserves_rank_and_fourth_same_document` |
| `UAT-K-EV-002` | 完整性冲突或缺失 | `evidence_failure`，Summary调用0；前置selector/意图调用单列 | L2_01_02 DR-KEV-201/204/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/出域/引用反例 | Fake verified：E `test_complete_ranked_batch_is_verified_before_any_selection[late_hash/snapshot/rank_from_failed_path/rank_from_no_result_path]`、EI `test_minimal_pre_summary_failures_are_closed_with_zero_model_calls[bad_hash]` |
| `UAT-K-EV-003` | 全局∩域∩文档策略允许 | 仅最小 payload 进入当前 Summary task | L2_01_02 DR-KEV-201/204/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/出域/引用反例 | Fake verified：EI `test_minimal_stage_uses_mode_projection_and_local_citation_without_extra_fields`，仅最小字段出域 |
| `UAT-K-EV-004` | 未分类、策略缺失/冲突或文档收紧拒绝 | `model_egress_denied`，summary 调用 0 | L2_01_02 DR-KEV-201/204/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/出域/引用反例 | Fake/non-live verified：EI `test_minimal_pre_summary_failures_are_closed_with_zero_model_calls[policy_deny/policy_missing]` 中 `policy_missing` 将候选文档改为目录未绑定身份并断言Summary0/无结果；`test_selected_policy_deny_does_not_fallback_to_allowed_later_candidate`，UG `test_minimal_evidence_policy_conflict_denies_before_summary`；真实索引的未分类策略覆盖仍Not assessed |
| `UAT-K-EV-005` | 证据覆盖不足 | `no_result/insufficient_evidence`，不生成肯定回答 | L2_01_02 DR-KEV-201/204/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/出域/引用反例 | Fake verified：E `test_missing_selected_domain_is_insufficient_even_when_other_domain_has_evidence`、KR `test_current_root_model_insufficient_is_public_no_result_without_answer`，公开reason/固定非肯定文本 |
| `UAT-K-EV-006` | 有据回答（各原任务版本按冻结证据） | 原Summary8仅摘录；当前仓库Summary9 lookup保持摘录、解释/适用性逐点有限回应，`answerSummary`第n段对应`points[n]`原文quote/citation；ref唯一、quote为授权正文连续子串，不伪造coverage或语义证明 | L2_01_02 DR-KEV-201/204/205/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/claim模式/出域/引用及时间、否定、分类反例 | Partial/evidence missing：Summary9合同、stage、当前root、页面配对及Spring合成三模式/失败路径的fake/non-live已通过；001/002 lookup整题已获维护者Passed（P3_01 §14.37），其余模式、真实typed全链及完整回答评价仍未完成，不能判整项Passed |
| `UAT-K-EV-007` | unknown/duplicate ref 或非子串 quote | `knowledge.summary_failure`，不返回模型原文 | L2_01_02 DR-KEV-201/204/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/出域/引用反例 | Fake verified：EI `test_minimal_summary_failure_matrix_has_one_call_and_no_model_text[duplicate_ref/unknown_ref/stitched_quote]` |
| `UAT-K-EV-008` | summary timeout/provider/schema failure | 固定 timeout/downstream failure，无 retry/resume | L2_01_02 DR-KEV-201/204/206 | TEST-KEV-201/203/204；Evidence/模型精确输出/出域/引用反例 | Fake verified：EI `test_minimal_summary_timeout_or_cancel_releases_single_call[False/True]`、`test_minimal_summary_failure_matrix_has_one_call_and_no_model_text[failure]` |
| `UAT-K-ISO-001` | Knowledge 请求 | Employee/Transaction 调用 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：KR `test_knowledge_request_never_calls_employee_or_transaction_http`，两个Business HTTP transport各0调用 |
| `UAT-K-ISO-002` | Business 失败 | Knowledge 调用 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：KR `test_business_failure_does_not_call_enabled_knowledge`，同根Knowledge enabled而其HTTP路径0 |
| `UAT-K-ISO-003` | `AGENT_KNOWLEDGE_ENABLED=false` | 不注册动作、不创建 Knowledge client、不要求配置 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：PR `test_disabled_knowledge_registers_descriptor_without_tasks_stages_or_clients`、KR `test_disabled_current_root_does_not_create_knowledge_client` |
| `UAT-K-ISO-004` | 取消/关闭 | 未开始阶段调用 0，所有 owned Knowledge HTTP client 被关闭一次 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake verified：KR `test_current_root_cancellation_aborts_summary_and_closes_clients`，取消后不继续、连续两次aclose各owned client仅关闭一次 |
| `UAT-K-ISO-005` | 日志与有限 evidence 扫描 | JWT、正文、原始 Prompt/响应、物理 ES 信息均为 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Spring non-live verified：J 生成当次`runtime.log`/`evidence.json`并扫描synthetic JWT、正文、Prompt/响应特征及物理ES字段/路径为0；真实部署日志Not assessed |
| `UAT-K-ISO-006` | enabled + 生产 stub / 测试显式 fake | 显式enabled + 生产stub按当前启动合同失败；测试显式fake复用生产装配，意图12/Summary9唯一且外部outbound=0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Fake/non-live verified：KR `test_enabled_current_root_stub_without_fake_rejects_before_client_allocation`、`test_current_root_reaches_intent12_summary9_once_and_closes_owned_clients`；J外部模型outbound0（Spring合成链证据仍须区分其版本） |


证据简称是定位入口，实际证明范围须核对记录绑定的提交与版本，文件当前存在不代表本轮已重跑：`J`=[Spring Knowledge non-live E2E](../../agent-service/src/test/java/com/dylan/agent/service/e2e/AgentKnowledgeNonLiveE2ETest.java) 的 `verifiesSpringToCurrentKnowledgeCompositionWithFiniteFailureSemantics`（方括号内为caseId）；`S`=[Spring安全契约](../../agent-service/src/test/java/com/dylan/agent/service/security/AgentSecurityContractTest.java)；`KR`=[当前生产组合根测试](../../agent-runtime/tests/integration/knowledge/test_minimal_current_root.py)；`UG`=[当前根UAT缺口反例](../../agent-runtime/tests/integration/knowledge/test_minimal_uat_gap_cases.py)；`IC`=[意图输入契约](../../agent-runtime/tests/unit/knowledge/test_intent_contracts.py)；`PL`=[最小计划测试](../../agent-runtime/tests/unit/knowledge/test_minimal_retrieval_plan.py)；`R`=[检索阶段测试](../../agent-runtime/tests/unit/knowledge/retrieval/test_minimal_stage.py)；`RA`=[typed适配fake测试](../../agent-runtime/tests/integration/knowledge/test_minimal_retrieval_adapters.py)；`E`=[Evidence选择测试](../../agent-runtime/tests/unit/knowledge/evidence/test_minimal_selection.py)；`EI`=[Evidence阶段测试](../../agent-runtime/tests/integration/knowledge/test_minimal_evidence_stage.py)；`PR`=[Provider注册测试](../../agent-runtime/tests/contract/knowledge/test_provider_registration.py)。

历次执行数量、原Summary8测试入口与版本演进见[整理前记录](P3_01_EXECUTION_HISTORY_2026-10-06.md#step2-uat-history)；不作为每次验收必须重跑的历史组合。

当前逐案登记保持36项 `Fake/non-live verified`、1项 `Partial/evidence missing`（EV006），不改判为37/37 Passed。表中真实typed、部署或人工语义缺口按其对应维度承接，不要求每个确定性风险重复付费执行。EV006包含两种证明：Summary9结构、模式、引用和失败关闭由当前组件/生产根及Spring合成用例验证；原文是否充分支持真实回答由§5的人工评价验证。后者未完成不否定前者已有断言，也不能据前者宣布EV006整体或回答质量通过。

接入认证、Java读取授权和Spring→Runtime→typed跨服务接线属于真实集成核验；fake不能替代实际协议/授权部署。需要的角色、域和路径按§3未验证边界列出，真实模型语义不作为这些确定性接口断言的前置。模型可用性只证明连通，不证明质量。受控inspection投影不是普通日志或有限持久evidence，公共诊断合同不变。

全部用例须记录目标代码/task/config/模型与数据绑定、断言及有限调用数；37风险不等于37次付费调用，确定性反例使用fake/契约。角色矩阵在接入和业务读取两个拒绝位置分别取证；summary阶段零调用不等于前置selector从未调用，应记录各阶段计数。

## 4. 原证据与当前要求的关系

| 原资产 | 适用范围 | 新计划使用方式 | 不允许的推论 |
|---|---|---|---|
| [旧UAT_01完整快照](历史文档/2026-09-14-knowledge-plan-handoff/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 原37风险及各冻结任务/配置的功能证据、历史效果、当时待执行安排 | §3复用风险身份；§5/6承接已批准方法 | 原Passed不等于现行12/9已执行 |
| knowledge_uat_traceability.v1.json及原loader | 原authority UAT_01 v1.21及Summary4证明边界 | 保持字节和原始依据；后续新版本追踪另作实现 | 不改authority来制造新验收通过 |
| 历史P5/代表性run/人工rubric | 各自冻结HEAD、模型、语料及协议；有效与无效结果分开 | 只作历史对照；具体事实回到归档及原evidence | 不拼题、不改判、不证明现行12/9/minimal-v1 |
| 阶段A正文/附件/发布资产 | 当时有限语料完整性、检索与回滚 | 复用数据来源及安全风险，不重做既有发布 | 不证明新chunk/向量表示已经更优 |

历史引用必须按原冻结提交和原路径读取；归档内部链接原样保存，当前计划不将其相对路径解释为当前权威。详见[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

## 5. 新设计的四维验收方法与阶段性证据

### 5.1 证明范围与版本隔离

当前仓库唯一Knowledge生产组合根为意图12、Summary9及knowledge-minimal-v1。功能、安全、真实集成、召回、回答及发布分别给出结论：不同测试可以覆盖同一目标版本的不同确定性风险，但须说明版本差异及适用性；不得拼接不同真实测量批次的成功题，制造一套完整的效果结果。现行部署仍须核实实际代码、Profile、索引和策略，仓库接线不是部署证明。历史P5、阶段A/B和原12/8证据只按各自冻结范围使用。

本轮没有新增测试、真实调用或人工标注，保持§3和§7的现有状态。功能/安全通过须完成对应必需断言及其实际跨服务证据，不能因真实效果批次中断自动全部改判Failed，也不能省略尚未验证的真实集成。召回/回答按§5.2独立评价；未执行、未评价分别保留，不改历史result Schema。

Summary9定向non-live已验证公开`summaryType`语义与验证台呈现：`cited_limited_answer`的第n段回答同屏对应第n点原文quote/citation，明确标为“有限回答／原文依据”；lookup仍为原文摘录。页面未把模型claim单独标成“证据摘要”，使用`textContent`且新增Node测试覆盖XSS边界。该前端断言只验证展示和结构对应，不替代维护者的语义评价。

37个稳定ID及风险保持；COMPOSE维护TEST-KFLOW-201～203、TEST-KRET-201～203、TEST-KEV-201/203/204的现行映射。检索表示固定使用build_minimal及context装配，不以旧工厂版本分支或旧24题作为普通功能/安全回归前置。真实模型的选域、理解和回答充分性进入质量评价，确定性故障注入继续使用fake/契约；公开引用合法性不替代人工语义判断。

### 5.2 四维判据及阶段损失

| 维度 | 验证内容/方法 | 通过条件 | 不证明什么 |
|---|---|---|---|
| 功能 | fake实际生产root及Spring入口、精确意图/模式、原Q一致、路径与调用上限、失败映射、并发/取消/关闭；37风险逐case | 必需用例100%通过，无skip冒充；非法/模型失败下游0；不支持问题无第二动作 | 不证明真实LLM理解准确、原文库充足或usefulness |
| 安全 | Java读取角色/拒绝位置、Guard0model、三层出域0Summary、identity/hash/ref/连续子串/唯一性、日志脱敏及Business隔离 | 必需边界100%通过，任一越权/泄露/伪造引用为硬失败；不能被效果平均抵消 | 合法引用不等于回答充分或现行适用 |
| 召回 | 在人工确认必要来源存在的冻结池，记录域选择→keyword/vector→RRF→rerank→final20→Evidence8的来源覆盖、MRR与噪声 | 12题中至少8题预置为search且有可核实必要来源，三种模式均须覆盖；无命中/前置澄清题不放入召回分母；可验证题最终必要来源宏平均recall@20≥0.80、precision@20≥0.40，核心已确认必要来源不能全丢；实际分母/空池明确 | 缺资料不算排序失败；命中不等于可回答；未做同条件A/B不称较旧方案提升 |
| 回答 | 对原问题逐项核对相关、充分、忠实与usefulness；执行者可准备原文，最终真实评价由维护者独立于待测模型确认 | 12题全纳入；每题四项true才通过，≥10题通过；所有applicability题不得有无依据肯定结论，当前适用/历史有效混淆为硬失败 | 结构有效率不能冒称忠实度；“不足/澄清”只在预置预期如此时算正确 |

这些是**新需求基线的预置目标**，不是降低或重算旧P5 Q1～Q4；旧结论不变。阈值是个人验证项目的有限初始选择，维护者此前已确认草案问句、必要来源及既有阈值作为后续冻结输入；仍需在实际运行前核对最终代码/资料快照和回答合同，不能在看到新结果后降低。无法确认上述至少8题及三种模式的来源池时，即使P3_01中的MEASURE技术依赖已满足、标为Ready，首次真实执行仍受阻，不得自动删除case、补造gold或调用模型“找答案”。功能与安全合格可完成COMPOSE基础实施，未达到召回/回答目标不得宣称质量达标或擅自发布为优化成功。

每题在各阶段报告必要source/block集合覆盖及排名；候选ID仅诊断使用，不进入在线排序。相同父文档不同必要条款不能只因父ID命中就算全部覆盖。precision@20分母为实际返回候选数（0记0），由人工相关标注计算；每题必要来源缺一部分按比例计recall，宏平均只取预先核实可检索池，另报全部12题含缺料的覆盖率。MRR按首个相关必要来源排名，未命中0；Evidence recall另列，不以rerank数值分代替。没有人工原文/相关性标注时这些指标为not_assessed，不自动算0或Passed。

### 5.3 固定代表类别与先验预期

先设计12个内容case（每类4题），后续MEASURE准备阶段由维护者结合实际公开语料填写精确问句、必要source/block/hash、相关性标签、允许答案和不足/澄清预期，并在任何真实模型调用前冻结。不得单为住宿题、当前失败或gold ID写在线特判；不要求住宿资料缺失时也给肯定税率。

| 新Case | 模式/输入类型 | 预期与主要风险 |
|---|---|---|
| UAT-KM-001 | lookup，指定文号/附件 | 找到原文摘录与来源；不因缺纳税人条件阻断资料查找 |
| UAT-KM-002 | lookup，同义服务表达（可含住宿） | 检索相关资料而非擅自判税率；检索表示不足如实记录 |
| UAT-KM-003 | lookup，历史期间资料 | 可返回历史条文，不把它称为现行适用 |
| UAT-KM-004 | lookup，语料中确无对应条款 | 预置无命中/不足；不能返回无关片段冒充答案 |
| UAT-KM-005 | explanation，单域定义 | 直接原文支撑的有限解释覆盖明确问题；不做无来源自由改写 |
| UAT-KM-006 | explanation，两个显式子问题 | 两项必要证据齐全且逐点回应才回答；缺一项不能部分肯定 |
| UAT-KM-007 | explanation，法律+政策 | 一次选双域、独立读取、逐点解释具体界定的来源；无失败扩域 |
| UAT-KM-008 | explanation，否定/税率/日期条件 | 原Q逐阶段不变，以原文有引用地回应“是否所有”，不得忽略例外或施行日期 |
| UAT-KM-009 | applicability，明确主体/期间/方法 | 仅按题述事实及指定条款给有引用的条件式判断；无条件“已符合/可享优惠”属回答硬失败，不靠用户分类假设推导 |
| UAT-KM-010 | applicability，必要条件缺失 | 前置clarification_required，检索/Summary0；固定提示可用但不承诺动态问题 |
| UAT-KM-011 | applicability，当前与历史边界 | 有直接施行原文时须条件式回应不能直接用未来法判断题述过去交易，不推定当期税率；无直接时效依据时不足，writtenDate不当生效日期 |
| UAT-KM-012 | applicability，类似分类边界 | 没有直接分类桥接/冲突未解决则不足，不以词面相似肯定 |

12题精确问题、原文定位及维护者确认过程见[P3历史§14.9～17](P3_01_EXECUTION_HISTORY_2026-10-06.md#record-14-9)。已确认的解释类措辞、KM-012公共税务语义前缀、必要来源及阈值保持；Summary8不能完成有限判断的冲突已由当前Summary9合同及non-live接线处理，不再作为待实施前置。冻结前仍须核对这些既定输入与拟测版本、资料快照相容；不能看到结果后改变考点、gold或阈值。必要来源清单不代替全部返回候选的人工相关性标注。

上述内容题可用公开、非敏感问题。功能/安全额外反例不必付费：未知域/模式/重复键；输出terminal组合；>1024长度；单/双域DENIED；policy缺失/冲突；坏hash；重复ref/非子串；少一路/全失败；模型超时；并发取消；disabled0依赖；Business不fallback。至少一个37风险case对应每项新DR，不以只测12题代替安全矩阵。

### 5.4 固定变量、预算与停止条件

COMPOSE和Summary9定向non-live保持原证明范围；两次MEASURE失败及局部人评见P3_01 §14.20/33/37，均不可复跑、续跑或补证。本节定义后续验收方法，不恢复已消费授权。

按[L2_01_01 §18.4.2](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md#1842-验证准备与执行冻结边界dr-kret-307)执行：预先登记问题/gold/阈值及操作范围 → 在有权限和分项预算时完成无付费启动就绪 → 采集当前代码/配置/任务/模型/策略/索引身份 → 核对准备材料相容性 → 最终冻结运行身份、精确预算及停止条件 → 正式preflight/执行/postflight。预登记问题/gold不因启动或结果改变；不得预猜候选UUID，也不得用准备快照代替启动后的当前实例。正式窗口内身份仍exact，漂移停止；冻结后执行源码变化不得继续消费原授权。

现行12题方案的端到端上限保持12 E2E、36模型HTTP（selector/意图/Summary合计）、48 typed search、12 query embedding、24 online rerank；维持每请求≤3/4/1/2，startup预热独立事前列明、不得计入效果请求，不能凭空增加预算。无Business/旧answer、无自动retry/resume，无失败后追加或补题。实际terminal较早时只消耗已产生调用，不为凑预算补齐。

技术/协议/安全失败仍按当前L2及正式runner停止该批，保留有限append-only终态及未执行清单，先fake诊断；不能称完整测量。正常no_result/clarification或人工判据不通过是测量输出，在安全及执行合同成立时按冻结顺序完成批次，不改预期。在线单路技术失败能否部分继续由L2_01_01 DR-KRET-203判断；这不等于MEASURE工具获准在批次技术失败后继续发下一题。

| 触发情形 | 请求/批次处理 | 对其他验证的影响 |
|---|---|---|
| fake/契约用例预置的拒绝、超时或非法输出 | 按预期验证零后续、错误映射和资源释放；符合断言可判该风险测试通过 | 不触发真实批次，也不把正确拒绝当安全缺陷 |
| 真实测量的正常无结果、澄清或质量不达标 | 依冻结预期记录；可继续既定题序 | 只影响对应质量判据，不据此重开无关功能/安全断言 |
| 真实测量的非预期技术/协议错误，或安全、身份、预算、证据完整性失败 | 当前请求失败关闭；现行批次停止，保留有限终态，后续调用0 | 该批不能称完整有效测量；独立既有证据保持原范围，有证据表明共享缺陷时才重开受影响风险 |
| 启动/准备失败、只读身份尚未确认 | 不冻结为可消费运行、不进入正式测量；报告已发生的准备操作 | 不等于产品功能或召回不合格；不反向重做无关组件验证 |

**未生效建议**：独立题目技术失败后是否可以记Failed并继续，尚需同步L2_01_00 §20、L2_01_02 §9.4及runner/测试；只改本计划不能启用。旧批次停止规则、终态及不补跑要求不变，下一步不得先改测试期待继续再补设计。

同条件对比可优先使用无外部LLM的固定候选池重放，各阶段损失可归因；若没有同索引/模型/条件的旧有效结果，不得拼接历史数据算增益。当前目标授权的A/B资料对照分别遵守§6.1与L2_01_01 §18.4.1，不与在线方案简化混为同一变量；任何额外实验或超出当前限额的语料/索引写入均须新目标及授权。

### 5.5 证据、人评和有限收口

每题运行记录只保存caseId、模式类别、预期/实际域、各阶段有限ID/排名、调用数、有限status/reason、安全结论、自动结果及人工四项；不保存真实用户敏感问题、完整知识/模型响应、凭据或个人信息。为可复现性，人工编写并核实无敏感值的公开测试问句、来源/block定位/hash、相关性标签及预期可以且必须作为版本化测试数据集冻结；运行记录引用caseId/hash，不重复保存问题或正文。公开fixture须明确来源许可，诊断不能把ID/gold反馈在线策略。

最终分别报告Functional、Safety、Retrieval、Answer。完整且安全的测量中，召回/回答均达标为effective，仅一维达标为partially_effective，两维均未达标为ineffective；执行合同不完整或安全失败为invalid_run。人工未评为not_assessed/evidence missing，不能先宣布有效质量等级，也不能由执行者/待测模型代填维护者结论。完整但质量未达标可记录测量完成，质量风险保持Open，不能用历史P5替代。本次设计完成不要求新测量，也不允许预记结果。

核心来源题预置为KM-001/005/009，任一在确认有原文的情况下最终必要来源覆盖为0即召回失败，不由宏平均掩盖。回答四项含义固定为：回应原问题、覆盖预期义务、没有无依据断言、对用户查阅或补条件有用；对预置不足/澄清题，评价正确拒绝/提示，不虚构quote或当作成功肯定答案。

评审与验证记录由P3_01 §13集中维护；不另建审批流水。新UAT JSON/Schema/loader实现只属于后续授权COMPOSE/MEASURE，当前追踪资产字节不变。

### 5.6 正式路径无付费演练与失败取证

依据L2_01_00 §20。后续重新测量前先证明同一正式runner控制流的12题合成完整运行、前检拒绝、中途失败、取证异常、预算边界和owned清理；startup健康检查或静态字符串断言不能替代。全部真实模型/目标ES/BGE/Business为0，测试身份与live授权严格不可混用。断言必须能阻止错预算、漏checkpoint、继续下一题、错误终态及终止用户进程；仅输出有限分类和计数，不保存敏感载荷。

本节是MEASURE首次真实调用前的技术证据，不阻塞独立的离线诊断，也不是新增审批Gate。演练Passed只表示验证工具的相应non-live可靠性；Functional/Safety/真实部署/答案充分性仍按原用例及§5.4/5.5分别判断。现有真实预算、12题、gold、四项rubric、技术/协议/安全失败停止整批和invalid_run规则不变。局部题目证据保留原用途，不能拼成完整有效测量；旧失败批次不复跑、不补证、不改判。

现有DRYRUN完成证据及005解释正反例见P3_01 §14.40/44，不重复保存执行流水。后续只在runner、预算、装配或清理路径变化时重跑受影响反例；无新变化不机械重演全部历史批次。必须验证同一正式控制流，不能另做简化runner冒充。现有演练不证明真实Java部署、服务协议或语义质量，原005真实失败根因仍unknown。

## 6. 资料组织与检索表示验收方法（设计与阶段证据，尚未完整验收）

依据L1_01 §4.6、L2_01_01 §18、L2_01_00/02 §19，实施由P3_01 §5独占。该补充不重做阶段A、不修改原37项功能或历史效果结果；既有来源/样本审计及NORMALIZE包的有限只读来源核对各有明确证明范围。UAT-KORG-010已有B候选构建和身份扫描的局部真实证据；P3_01 §14.32的新10题对照协议完整并保存traces/215项盲标池，必要来源recall未改善、人工盲标仍缺，001～012没有完整通过结论。旧失败比较不补证或改判，本计划不创建新的traceability、gold或候选。

### 6.1 四维判据与有限实验

1. 数据质量：逐字段来源可查、日期语义正确、版本/父子关系可解析；正文跨度/表格/脚注不静默丢失。填充率和准确率分列；未知可存在，但不能把核心预期依据的未知问题标为已完成。
2. 功能与安全：唯一typed链路、读取先于正文处理、三层出域、身份/hash/ref/连续子串/唯一性、取消/关闭及Business不回退；任何越权/伪造/不明写入为失败，不能用质量均值抵消。
3. 召回质量：必要原文来源Recall、MRR/排名、噪声及Evidence覆盖；分别报告keyword/vector、融合、rerank、Evidence损失，不以“有命中”代替完整依据。
4. 回答质量：问题回应、条件/期间、原文充分性、忠实性与人工usefulness；合法引用不等于充分。没有模型调用或人工评审时为Not assessed，不由离线统计推出改善。

未来每个对照协议先冻结≤30父文档的变更/人工核验范围和代表问题（建议≤24，覆盖多税种、长短/附件/表格、现行/历史/未知、查找/解释/适用性和无命中反例）；不要只选原审计暴露问题或住宿单题。搜索池保留完整基线和未受影响竞争文档，不能仅搜30篇后外推全库收益。人工预先固定来源、必要条款/连续span和预期不足/澄清，不由待测模型自评。原文无法核实的题标source_gap，质量指标null；保留在计划总数/数据缺口中，单列可评估质量分母及未评估数，不能强计Recall=0/1或事后删除。

当前`rechunk_candidate_v1.py`的A构建器仅支持预登记的`tax.policy`附件重切；law、正文及其他类别仍须作为未变竞争记录全量保留。这个实现边界不改变上表跨类别评价要求：若预登记的A变更样本包含正文或law，先判为工具范围不匹配，不静默跳过、不把附件样本收益外推到其他资料类型。B须在冻结的同一chunk集合上单独比较表示。维护者已确认B必要来源、主指标和噪声/时延容忍值；P3_01 §14.32的新独立对照通过执行协议准入，recall未改善且盲标未完成，不能宣称收益或启动发布。历史准入失败比较保持原终态。

对照分两个独立问题：A只改chunker，固定原始/规范解析源hash、问题、模型、检索配置及权限，向量输入类型不变；B只改向量表示，固定A选定或原有同一chunk集合及精确body hash、模型/服务和所有在线参数。参与变化的每条旧记录必须逐条证明原向量模型、表示版本，并按旧chunk正文及其冻结表示算法重算验证旧输入hash与正文hash；A中新旧chunk的正文及输入hash不必相等，B的chunk和正文hash必须相同。旧/新完整模型运行快照可仅因同一容器重启的`started`时间不同而hash不同，但剔除这一个字段后的容器及模型内容须规范字节相等，并分别记录两份原始hash和差异；其他漂移阻断同模型对照。只有全局快照或向量形状的记录标记`legacy_unknown`，其依赖题不可归入单变量收益分母，预登记核心依赖它则停止相应对照。未受影响的全库竞争记录可维持原样，不补造其向量来源。新chunk写入前须对完整`_source`通过现有Java typed读取投影边界前检，保持ACL、来源、原文hash和完整竞争池。更换切片时gold用稳定document/asset/source span，不用旧chunkId强求一一对应；同时变化parser、语料或模型时不能宣称单变量实验。

结构前置先在不调用模型/ES的fixture上验证：文档类型、实际条款/章节结构与解析可信度共同决定条款型/章节型/通用型策略；DOCX段落和表格交错顺序必须与源一致，扁平表格不能冒称表头/单位/备注完整。每个verified结构单元必须有稳定的不可变`documentVersionId`、`unitId`、连续原文span和可重算hash；有上级结构单元时`parentUnitId`须指同版本且span包含该单元，无上级时为null。`parentDocumentId`仅是附件来源关系。短条单chunk、长条多chunk均能从不可变源恢复完整原文；单元完整性与chunk覆盖分开判定，子chunk未覆盖全部可引用内容blocks时不得发布受影响候选或宣称检索覆盖完整。乱序、悬空、跨版本或循环关系不得标单元完整。若parser变化是必要前置，先固定新旧解析产物并单独报告源/结构质量差异；不能把parser+chunker同时变化的结果宣称为纯切片收益。

body、title/section/body、可信分类/body至多3种表示，先用纯构造/token统计筛除不合法项；每轮只比较基线与一个预选候选，不因失败扩成无限网格搜索。每次真实实验冻结run、代码/索引UUID/全记录变更清单、模型/tokenizer/表示/Prompt、case顺序、人工rubric、每个阶段调用预算及停止条件；本计划不授予任何调用或索引写预算。若有模型，统计selector/意图/Summary全部HTTP，不复用旧额度；无模型阶段仍须限定ES/BGE总量和候选数量。

建议质量判据在执行前由维护者确认并固化：核心有充分原文的题必要来源覆盖不得为0；成对核心覆盖和保留集覆盖不得退化，至少一个预先选择的质量主指标改善且噪声/时延不突破预定容忍值，才考虑发布。指标阈值/容忍值未冻结则实验Blocked，不允许看到结果后降低。小样本只作局部决策依据，不声称统计显著或全库收益。数据/功能安全全部达标但质量无提升可以结束测量，不能使RELEASE自动Ready。

既定B质量判据保持：固定同一chunk/正文及在线配置，必要来源宏平均`recall@20`严格提高，`precision@20`不低于基线，同机同条件median检索时延不高于基线110%，核心及保留题逐题覆盖不退化。这些是该有限B方案的采用判据，不是所有功能验收的通用门槛。A仍Not assessed；B当前不采用及各历史失败终态由P3_01 §14统一追溯，不补跑或改判。

B的同一成对分母固定为预登记的10个`retrievalDenominator=true`题；每题把全部必要来源（KM-007含policy和law）计算`recall@20`，两臂分别取题级宏平均。每题`precision@20`为人工判为直接关联任一显式子问题的final20候选数除以**实际返回候选数**，返回0个则记0，再分别取10题宏平均。对同题两臂final20按`(caseId, documentId, chunkId, contentSha256)`合并成隐藏臂身份的盲标池，最多400个题—候选判断；所有返回候选均须人工标注，必要来源清单不是全部相关候选。任一标签缺失时，两臂precision及B通过结论为`Not assessed`，不以未标候选为不相关或从分母删除。核心及保留题的必要来源题级覆盖逐题不得低于基线，不用平均值掩盖单题退化。

成对B的构建意图、源向量溯源、候选实际UUID、隔离typed目标、请求见证、独占窗口、keyword不变性和时延归因，统一引用[L2专项协议](../design/KNOWLEDGE_EXPERIMENT_PROTOCOL_2026-10-06.md#protocol-1)及L2_01_01 §18.4.1，不在UAT复制执行器合同。适用时必须满足全部相关条件，不能因移出正文而跳过检查；启动后的正式身份冻结另按§5.4执行。其原b2路径、10题和alias写4等精确参数只约束绑定批次，普通单臂或功能/安全验证不继承；新操作须按实际范围计算并冻结预算。

B的时延口径保持：逐题自首个typed请求至final20排序完成，排除共享embedding、启动、预热、构建、元数据核验及人工标注；两臂交替顺序事前固定、各取10题median。逐题/域核对keyword有序ID及事前并列规则，分别报告keyword→vector→RRF→rerank→final20损失；无法解释且影响候选/来源覆盖的keyword变化记confounded / Not assessed，不把Lucene变化自动当作可忽略噪声，不以调gold或事后调参归因收益。

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
| UAT-KORG-011 | 合法引用却无法回答；DR-KEV-304 | 三模式多税种/期间代表题，人工原文与usefulness；模型仅在独立有效授权且gold已确认后调用，超范围另授权 | 足够与不足分别判断，时效未知不肯定，不由模型自评 |
| UAT-KORG-012 | 发布错配/无法回滚；DR-KFLOW-303、DR-KRET-307 | fake故障→独立授权且条件满足后的隔离typed/alias回滚→发布冒烟 | 旧索引/资产不改，全记录变更可核，Profile/catalog匹配，恢复相容旧绑定 |

001～008可先以纯离线fixture完成；009的fake与真实typed证据分开；010的BGE/ES、011的模型/人工回答、012的发布验证均须符合对应操作的有效授权、人工确认及各自前置门槛，超范围再单独授权。不把单测代替真实集成。图谱、记忆和多轮不参与验收。

在线父单元补取不属于当前UAT-KORG的通过条件。若未来单独批准，应先冻结新typed/候选`content`语义、逐单元读取与出域授权、同版本/深度1/≤8单元和既有Evidence预算、请求数/超时/取消及失败映射，再增加直接相关用例：未找到、未授权、技术失败、预算不足、循环/悬空/错版本、必要例外/定义缺失；安全拒绝必须零未授权正文与零模型出域，不完整时不得给出完整肯定答案。未通过合同评审前，这些是待评估风险，不计为当前已实施或已执行UAT。

### 6.3 报告与停止

逐case记录来源类别、原文身份/hash、变量、验证方式、有限结果、缺口及执行状态；不保存真实敏感问句、完整正文、JWT或原始模型响应。原文人工阅读限定既有批准资料，证据只记录必要定位与hash。固定问题集中的合规非敏感问题可用于后续版本化测试，不能与禁止保存真实敏感输入混淆。

数据质量、Functional、Safety、Retrieval、Answer分别报告；本次均不预记通过。停止范围按§6.1及L2_01_01 §18、L2_01_02 §19区分：

- 已登记的业务分类/时效未知（不含出域策略未分类）、旧表示或hash口径的`legacy_unknown`、旧库存的`source_unverified`及非核心题的`source_gap`，保留标记和原证明边界，不自动停止未受影响的既定验证。未知来源不得作为新的官方gold或适用性证明；变更资产未满足来源准入时隔离、不写入候选，不能据此绕过安全检查。`source_gap`题保留在计划总数及缺口统计，质量值为null，单列可评估分母与未评估数，不事后删题或补造来源。
- 核心预期依据无法核实，阻塞依赖该依据的对照、质量结论及发布；可继续不受影响的已授权离线验证，但不得减少核心要求、降低阈值或把不完整实验标为完成。
- 读取/出域权限不明或失败、出域策略未分类/缺失、当前处理内容的身份/hash完整性冲突、非法引用、模型/服务错误、快照错配、预算耗尽或执行记录不完整，停止该批实验，在继续外部调用、候选写入或发布前失败关闭。保留有限终态及未执行清单，使用fake诊断；不得以单条未知元数据为由放宽这些安全及执行停止条件，也不自动补跑、续跑或创建新candidate。

质量未提升只给出风险和是否保留基线的决策，不恢复被取消目标。以上区分不新增公开状态，不修改§5.4的在线测量停止合同，不将部分验证冒充完整UAT。

### 6.4 损失诊断与不采用候选的有限收口

依据L2_01_01 §9.9。先用既有冻结库存/trace逐来源定位，再判断是否需要新的有限读取。确认原文存在但两路top20均无时，只记初召回损失；过滤、词法、向量或窗口原因缺证据仍unknown。固定窗口之外的诊断不能由最终排名倒推，不由grep命中证明语义召回已解决。每项新增真实操作均须新范围、预算和授权，本节不允许复跑B/MEASURE。

**采用与不采用的证据量可以不同**：有效且完整的既有对照中，只要一项预先冻结的必要采用条件明确不满足，例如主指标没有严格改善，即可决定“不采用、保留基线”，不必仅为这个否决决定补齐其他不会改变决定的人工标注。未评价的precision、usefulness等仍记Not assessed/null，不能写成通过。若主指标计算、执行完整性或归因证据不足，只能作“证据不足，未采用”，不能虚构质量不达标。允许完成独立的有限决策交接，但不自动把整个COMPARE或完整UAT标Done。

该规则不降低任何正向采用/发布阈值，不删题、不换gold、不缩分母、不放宽安全。要采用候选，§6.1全部正向判据及标注仍必须满足。当前B主指标没有改善，P3_01 §14.41已据严格离线验真及封存排名作出有限“不采用、保留b2”决定；原result中的not_assessed、precision=null、盲标缺口和历史终态保持原样。不补评、不改判，也不因否决候选关闭整个COMPARE、A或RELEASE。

诊断的逐次调用、有限收益和未知根因见P3_01 §14.42/43；不在本计划重复执行详证，也不由局部词法收益改判原用例或整体质量。

## 7. 后续执行与当前结论

在线由P3_01的CONTRACT/RETRIEVAL/EVIDENCE→COMPOSE→MEASURE推进；资料由NORMALIZE→CHUNK/REPRESENT→COMPARE→RELEASE推进。前置不足只阻塞对应阶段，真实测量不是基础实现反向依赖；资料对照不依赖在线MEASURE，需自行冻结相容在线基线。

当前37项风险中36项已有fake/non-live阶段证据，EV006仍为partial/evidence missing，完整功能与安全UAT尚未完成；12项UAT-KORG资料用例仍未形成完整通过证据。逐case保留设计/风险、预期、证据、状态、失败原因和未验证范围，旧证据不能替代新执行。

- B对照：[P3_01 §14.32/41](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md)，协议完整但主指标未改善，不采用候选、保留现行b2；未评指标及原result不补改，A仍未评价。
- MEASURE：[P3_01 §14.33/37](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md)，001/002人工Passed、003/004 Failed，005技术失败，006～012未执行；整批invalid_run且不补跑，局部评价不代表整体质量通过。
- 工具与诊断：[P3_01 §14.40～58](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md)，DRYRUN/DIAGNOSE仅完成限定范围；独立词法诊断有局部收益，但后续成对执行前置失败，未形成新的有效质量测量。各次预算、hash及终态只在原证据/P3维护。
- 本轮文档同步：按已批准现行职责修正来源版本、Summary9交接、验收分工与操作前置。未修改代码、测试或运行协议，不授予真实批次/发布许可，不改变上述运行结论。

后续独立执行须按检索L2的现行冻结顺序，在启动就绪后取得当前完整身份、核对与准备模型同一性，再冻结正式预期；正式pre/post仍exact，不忽略窗口内重启。不降低§5/6采用及回答条件。COMPARE/MEASURE未完成、RELEASE受阻，完整新版UAT未通过。
