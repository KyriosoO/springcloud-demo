# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 依据文档数量 | 1 |
| 评审代码范围 | 本地未提交代码 |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 有剩余风险 |

说明：第 2 轮曾尝试将两个 query.preview 单测移动到 D05 表格所列 package，验证发现这会要求扩大 `kernel.core` 包内构造器可见性；该尝试已撤回，不进入最终修改。

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| docs/design/D05_Capability扩展验证与遗留清理_L2实施详细设计_v1.0.md | detailed_design | 1 | 是 | 已读取 | 作为本次唯一评审依据 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | D05 第 5.1、8.7 | 新增 capability 不修改核心主流程、Runtime API、generated model | D05 禁止文件静态 diff | 符合 |
| DOC-C-002 | D05 第 6.1、6.6.1 | 新增 `QueryPreviewResultPayload` / `QueryPreviewResult` 并纳入 result union | agent-api/src/main/java/com/dylan/agent/api/response | 已修复并符合 |
| DOC-C-003 | D05 第 6.2、6.6.2 | 新增 `query.preview` registration，planKind=QUERY，输出 contract 为 `QUERY_PREVIEW_RESULT` | agent-service/src/main/java/com/dylan/agent/capability/querypreview | 符合 |
| DOC-C-004 | D05 第 6.6.2 | Validator 必须 fail closed：capability、field、operator、page、size 均受限 | QueryPreviewPlanValidator + 单测 | 已修复并符合 |
| DOC-C-005 | D05 第 6.6.2 | Handler 调用 `QueryableAdapter`，不写 Context，并限制预览字段和行数 | QueryPreviewCapabilityHandler + 单测 | 已修复并符合 |
| DOC-C-006 | D05 第 4、5.2、10 | `query.preview` 支持全部已授权 `QUERYABLE` domain，不新增 capability-domain allowlist | CapabilityCatalogTest、AuthorizationPlanningPortTest、DefaultAgentMetadataBootstrap | 已修复并符合 |
| DOC-C-007 | D05 第 6.3 | auth-service 投影增加 `query.preview`，narrow 不扩大权限 | AgentPermissionProjectionService + 单测 | 符合 |
| DOC-C-008 | D05 第 6.4、8.6 | Runtime prompt 不出现 `query.preview` 固定分支，不改 `runtime_api.py` / generated model | agent-runtime tests + 静态搜索 | 符合 |
| DOC-C-009 | D05 第 8.6 | 不恢复旧 intent/v1 路径，不新增 D06 概念 | 静态搜索 | 符合 |
| DOC-C-010 | D05 第 8、11 | 执行 Maven、Runtime、静态门禁和 diff/status 收口 | 验证命令 | 已执行 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 建议处理 |
|---|---|---|---|---|---|---|---|
| CR-001 | medium | api_contract_consistency | agent-api/src/main/java/com/dylan/agent/api/response/QueryPreviewResult.java | D05 第 6.6.1 | `totalEstimate`、`totalExact`、`previewSize` 使用 primitive，且缺少全参构造器 | 与 D05 指定字段形态不一致，新 payload nullability 不清晰 | 已改为 `Long`、`Boolean`、`Integer` 并补全参构造器 |
| CR-002 | medium | implementation_completeness | agent-service/src/main/java/com/dylan/agent/capability/querypreview/ValidatedQueryPreviewPlan.java | D05 第 6.6.2 | 构造器未断言 query selectFields/page/size 与 previewFields/previewSize 一致 | 非 validator 来源的构造路径可能形成不一致 validated plan | 已补 fail-fast 断言 |
| CR-003 | medium | functional_correctness / security | agent-service/src/main/java/com/dylan/agent/capability/querypreview/QueryPreviewCapabilityHandler.java | D05 第 4、6.2、6.6.2 | Handler 依赖 adapter 按 selectFields/size 返回，没有二次裁剪样例行 | 若 adapter 返回额外授权字段或超量行，候选 payload 会带入多余数据 | 已按 previewFields 裁剪、按 previewSize limit |
| CR-004 | medium | test_coverage | agent-service/src/test/java/com/dylan/agent/kernel/core/QueryPreviewPlanValidatorTest.java | D05 第 6.6.4 | 缺少 capability mismatch、operator 拒绝、size 超预算、ValidatedPlan 构造一致性测试 | fail closed 行为容易退化但测试不报错 | 已补测试 |
| CR-005 | medium | test_coverage / design_consistency | agent-service/src/test/java/com/dylan/agent/metadata/CapabilityCatalogTest.java、AuthorizationPlanningPortTest.java | D05 第 4、10 | 缺少 `query.preview` 经 Profile/Policy/UserPermission/D04 `QUERYABLE` 交集进入 available capability 的测试 | “支持所有已授权 QUERYABLE domain”可能只停留在默认配置 | 已补 employee/transaction 覆盖和权限不扩大覆盖 |
| CR-006 | low | coding_standards / document_traceability | agent-service/src/test/java/com/dylan/agent/kernel/core/QueryPreviewPlanValidatorTest.java、QueryPreviewCapabilityHandlerTest.java | D05 第 6.6.4 | 两个测试类未放在 D05 表格列出的 `com.dylan.agent.capability.querypreview` 包 | 影响文档到测试的路径追踪，不影响生产行为 | 不建议修改；移动测试会迫使扩大 `kernel.core` 包内构造器可见性，得不偿失 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | low | D05 第 6.6.4 | 测试包路径与现有可见性不匹配 | D05 表格把 validator/handler 单测归入 capability 包，但测试需要直接构造 package-private `ExecutionContext` / `ExecutionValidationContext` | 若强行按文档路径落测试，会扩大 core 测试支撑类可见性 | 保留当前测试包；后续若要严格对齐文档，应先设计测试工厂而不是放开生产构造器 |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | QueryPreviewResult.java | 调整字段 wrapper 类型，补全参构造器 | CR-001 | 已修复 |
| 1 | ValidatedQueryPreviewPlan.java | 增加 selectFields/page/size 一致性断言 | CR-002 | 已修复 |
| 1 | QueryPreviewCapabilityHandler.java | 对 adapter 返回样例行按 previewFields/previewSize 二次裁剪 | CR-003 | 已修复 |
| 1 | QueryPreviewPlanValidatorTest.java、QueryPreviewCapabilityHandlerTest.java | 补齐 fail closed 与裁剪测试 | CR-004、CR-003 | 已修复 |
| 1 | CapabilityCatalogTest.java、AuthorizationPlanningPortTest.java、MetadataTestSupport.java | 补齐 `query.preview` 交集与多 QUERYABLE domain 测试夹具 | CR-005 | 已修复 |
| 2 | QueryPreviewPlanValidatorTest.java、QueryPreviewCapabilityHandlerTest.java | 尝试移动到 capability 包后发现需扩大 core 构造器可见性，已撤回 | CR-006 | 不建议修改 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `.\mvnw.cmd test --batch-mode` | 失败后已修复 | 首次失败原因是 `Long` setter 测试仍传 `int` 字面量；修正为 `1L` 后重跑通过 |
| 1 | `.\mvnw.cmd test --batch-mode` | 通过 | 27 个 Maven 模块 BUILD SUCCESS，agent-service 测试 288 个通过 |
| 1 | `.\mvnw.cmd -q -DskipTests compile` | 通过 | 编译通过 |
| 1 | `.\.venv\Scripts\python.exe scripts\check_contract_drift.py` | 通过 | active Python codegen 可重复，provenance 有效 |
| 1 | `.\.venv\Scripts\python.exe -m pytest -q` | 通过 | 60 passed，1 个 StarletteDeprecationWarning |
| 1 | D05 静态门禁 | 通过 | 核心禁止文件无 diff；Prompt/API/generated/application.yml 无 `query.preview`；旧协议搜索为空；D06 概念新增行为空；unchecked 仅命中 `TypedRegistrationInvoker` |
| 2 | `.\mvnw.cmd test --batch-mode` | 失败后撤回 | 测试移动到 capability 包后无法访问 package-private core 构造器；已撤回该低级调整 |
| 2 | `.\mvnw.cmd test --batch-mode` | 通过 | 撤回后全量 Maven 测试通过 |
| 2 | `.\mvnw.cmd -q -DskipTests compile` | 通过 | 编译通过 |
| 2 | `git diff --check` | 通过 | 无空白错误 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | 值级 mask/脱敏仍未接入 ResultSecurity projector | 当前实现完成字段级裁剪；`com.dylan.agent.mask` 仍未接入统一 ResultSecurity 链路。若只给 `query.preview` 单独接入，会形成第二套脱敏路径 | 按 D02_03/D03 统一安全边界设计，把 mask fact 接入 `ExecutionScope` 后统一改造 Query/Aggregate/Preview projector |
| RISK-002 | low | UI/API smoke 未执行 | 本次执行了 contract、Runtime pytest、Maven 和静态门禁，但未启动前后端做浏览器 smoke | 发布前按 D05 第 11 条补充 UI/API smoke，确认 `QUERY_PREVIEW` 可展示或安全降级 |
| RISK-003 | low | 测试包路径与 D05 表格不完全一致 | 保持 `kernel.core` 包是为了访问包内构造器，不扩大生产 API | 后续若需要路径完全对齐，优先新增测试工厂或 builder，而不是放开构造器 |

## 9. 结论

最终结论：
- D05 自动修复范围内通过。
- 仍有剩余风险：值级 mask/脱敏策略和 UI/API smoke 需要单独处理，不建议在本次代码评审中静默扩大安全策略或启动环境范围。

说明：
- 本次没有修改 D05 禁止的核心主流程文件、Runtime API、generated model、Prompt 和 D04 metadata 配置。
- 本次没有 commit、push、创建分支或 PR。
