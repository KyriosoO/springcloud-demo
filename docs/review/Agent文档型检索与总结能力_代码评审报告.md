# Agent文档型检索与总结能力 代码评审报告

## 1. 执行摘要

| 项目 | 结论 |
| --- | --- |
| 评审模式 | review_and_fix |
| 评审轮次 | 2 |
| 依据文档 | `docs/design/P2/Agent文档型检索与总结能力_L2实施详细设计_v1.0.md` |
| 补充依据 | `docs/design/P2/Agent文档型检索与总结能力_设计文档品审报告.md` |
| 总体结论 | 通过。已修复发现的可处理问题，复审未发现新的中高风险可自动修复问题 |
| 是否修改设计文档 | 否 |
| 是否扩大到生产启用 | 否，`agent.document.enabled` 默认仍为 `false` |

## 2. 文档依据清单

| 文档 | 角色 | 使用方式 |
| --- | --- | --- |
| `Agent文档型检索与总结能力_L2实施详细设计_v1.0.md` | detailed_design | 校验契约、能力注册、Validator、Handler、Adapter、ResultSecurity、Context、默认关闭和测试要求 |
| `Agent文档型检索与总结能力_设计文档品审报告.md` | other | 确认 R1/R2 不阻断 Agent 侧编码，但阻断联调、灰度和生产启用 |

## 3. 文档约束追踪

| 约束 | 代码落点 | 评审结论 |
| --- | --- | --- |
| 新增 `document.search`、`document.answer`、`document.summarize`，`DOCUMENT` 仅作为 Plan 结构类型 | `agent-api`、`agent-runtime`、`agent-service/capability/document` | 已实现 |
| Runtime 只生成 `DocumentAgentPlan`，不生成答案、摘要、citation、ES DSL 或权限表达式 | `agent-runtime/app/prompts/document_system.md`、`runtime_planning.py` | 已实现并有测试覆盖 |
| Java Validator 必须复检 capability、domain、filter/sort、topK、summaryScope、citationRequired | `DocumentPlanValidator` | 已修复并补测 |
| Handler 只产出候选结果和最小 Context，最终文本由 ResultSecurity 生成 | `DocumentCapabilityHandler`、`DocumentResultSecurityProjector` | 已修复 Context citation fallback |
| Adapter 新增 `DocumentRetrievableAdapter`，不侵入 query/aggregate adapter | `agent-adapter-api`、`agent-adapter-document` | 已实现 |
| 默认关闭；启用时缺少文档 metadata/registration 必须 fail closed | `DefaultAgentMetadataBootstrap` | 已修复并补测 |

## 4. 代码问题清单

| 编号 | 级别 | 问题 | 修复结果 |
| --- | --- | --- | --- |
| CR-001 | High | `DocumentPlanValidator` 将文档证据上限从 0 强行提升为 1，且使用 `max-size` 而非 `max-evidence-count` 约束 `topK/size` | 已修复为配置、domain projection、execution scope 的最小交集；0 预算直接拒绝 |
| CR-002 | High | 文档 filter 未经过 `FilterNormalizer`，可能绕过 value/values 形态、类型、长度和通配符校验 | 已改为使用 `FilterNormalizer.normalizeAll`，并复用字段约束校验 |
| CR-003 | Medium | `SUMMARIZE.summaryScope.maxSummaryChars/documentIds` 未在 Java Validator 复检配置上限 | 已增加 summary scope 约束 |
| CR-004 | Medium | Adapter 将 `CONTAINS_ANY`、`STARTS_WITH_ANY` 映射为 `terms`，丢失文本包含/前缀语义 | 已改为 `bool.should` + `match/prefix` |
| CR-005 | Medium | Adapter 只返回 hits 时，响应会生成 citations，但 Context `citationIds` 为空 | 已统一引用 fallback，Context 保存实际 citation ids |
| CR-006 | Medium | `agent.document.enabled=true` 时默认 Profile/Policy 可加入文档能力，但缺少 `DOCUMENT_RETRIEVABLE` metadata/registration 未启动失败 | 已增加 metadata bootstrap fail-closed 门禁 |

## 5. 文档问题清单

未发现阻断当前代码评审和修复的新增设计文档问题。既有 R1/R2 仍按品审报告处理：下游文档 ACL 和 queryVector 来源未确认前，不得联调、灰度或生产启用。

## 6. 修改摘要

| 范围 | 修改 |
| --- | --- |
| Validator | `DocumentPlanValidator` 使用 `FilterNormalizer`，修正 evidence 上限、0 预算、summary scope 校验 |
| Handler | `DocumentCapabilityHandler` 统一 hits/citations fallback，Context 写入实际 citation ids |
| Adapter | `DocumentRetrievalMapper` 修正多值文本 DSL 映射 |
| Metadata | `DefaultAgentMetadataBootstrap` 增加文档能力启用门禁 |
| Tests | 新增/调整文档 validator、handler、adapter mapper、metadata bootstrap 和测试辅助 |

## 7. 验证结果

| 命令 | 结果 |
| --- | --- |
| `.\mvnw -pl ../agent-api,../agent-adapter-api,../agent-adapter-document,../agent-service -am test` | 通过，365 tests |
| `cd ..\agent-runtime; .\.venv\Scripts\python.exe -m pytest tests\test_contracts.py tests\test_planning.py tests\test_prompt_contract.py` | 通过，61 passed，1 个既有 deprecation warning |
| `cd ..\agent-runtime; .\.venv\Scripts\python.exe scripts\check_contract_drift.py` | 通过，active Python codegen 可复现 |

## 8. 剩余风险

| 风险 | 等级 | 处理 |
| --- | --- | --- |
| 下游文档服务 documentId 级 ACL 未在当前 Agent 代码中验证 | High | 不阻断 Agent 侧代码；阻断联调、灰度和生产启用 |
| queryText 到 queryVector 的输入来源未确认 | Medium | vector channel 首版保持未启用；关键词检索路径可测试 |
| 文档 domain metadata 未配置生产 corpus | Medium | 默认关闭；启用前必须补充 `DOCUMENT_RETRIEVABLE` metadata 和 adapter registration |

## 9. 结论

本轮代码评审-修复循环完成。当前实现满足 L2 文档定义的 Agent 侧文档检索、问答、摘录式总结横向扩展边界；未修改上级架构文档或 L2 设计文档；未启用生产开关。剩余风险均属于下游 ACL、queryVector 来源和生产 corpus 配置确认范围。
