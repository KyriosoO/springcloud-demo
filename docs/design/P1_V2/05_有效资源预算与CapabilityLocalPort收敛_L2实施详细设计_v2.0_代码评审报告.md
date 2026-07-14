# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 评审代码范围 | `agent-adapter-api` operation/limit SPI，`agent-service` resource resolver、Authorization freeze/recheck、metadata bootstrap/startup gate、Core/Document Handler/Result Security 及直接相关测试 |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 通过；4 项执行期限额复检、摘要完整性、启动闭合和 typed outcome 绑定问题已修复 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 读取结果 | 备注 |
|---|---|---:|---|---|
| `05_有效资源预算与CapabilityLocalPort收敛_L2实施详细设计_v2.0.md` | detailed_design | 0 | 已完整读取 | 当前主文档 |
| `02_可信执行内核与Invocation生命周期_L2实施详细设计_v2.0.md` | related_design | 1 | 已读取相关边界 | Core、deadline/cancellation、finalization |
| `03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md` | related_design | 1 | 已读取相关边界 | Snapshot/recheck/Result Security |
| `04_Adapter与DomainMetadata治理_L2实施详细设计_v2.0.md` | related_design | 1 | 已读取相关边界 | Adapter typed operation context |
| `06_原子迁移扩展验证与清理门禁_L2实施详细设计_v2.0.md` | related_design | 1 | 已读取相关边界 | 原子启动与清理门禁 |
| `../Agent能力执行内核架构设计_v1.0.md` | architecture | 2 | 已读取相关约束 | L1 主要依据 |
| `../Agent元数据与上下文安全架构设计_v1.0.md` | architecture | 2 | 已读取相关约束 | L1 metadata/authorization 依据 |
| `../Agent目标架构总览_v1.0.md` | architecture | 3 | 已读取相关约束 | L0 |

## 3. 文档约束追踪

| 约束编号 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|
| DOC-C-001 | Definition/Profile/Policy/Permission/Request 单调求交，Execution recheck 只能同值或更严格 | `CapabilityResourceLimitResolver`、`AuthorizationExecutionPortImpl` | 修复后符合 |
| DOC-C-002 | Snapshot、Validator、Handler、Provider、Result Security 使用同一 ContractRef/digest/binding | `ExecutionScope`、operation context、outcome gate、Result Security | 修复后符合 |
| DOC-C-003 | metadata bundle/currentness 摘要必须绑定预算与 typed limits | `DefaultAgentMetadataBootstrap` | 修复后符合 |
| DOC-C-004 | 所有 Capability 的 Profile/Policy contribution 必须在启动时闭合，不能延迟到执行期 | `AgentMetadataResourceLimitStartupGate` | 修复后符合 |
| DOC-C-005 | typed outcome 必须本地权威、attempt 为 0/1、终态一致、success 与 operation/limits 精确绑定 | `CapabilityOperationMetadata/Failure/Outcomes`、`DocumentCapabilityHandler` | 修复后符合 |
| DOC-C-006 | Planning Budget、Capability Resource Limit、absolute deadline、Provider operational cap 分层 | Profile/Policy/Execution/Provider 配置与架构扫描 | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|
| CR-001 | high | authorization_resource_recheck | `AuthorizationExecutionPortImpl.java` | 权限复检后直接把 `snapshot.resourceLimits()` 放入 ExecutionScope，未重新应用 exact-version Profile/Policy contribution，也没有形成单调证明 | 执行前发生资源上限收紧时仍可按旧上限调用 Provider/返回结果 | 新增 resolver `recheck`：以冻结值为不可放大 baseline，重新求交当前 exact-version Profile/Policy；缺失/type mismatch fail closed，保留 request narrowing 与 binding identity |
| CR-002 | high | evidence_integrity | `DefaultAgentMetadataBootstrap.java` | bundle digest 未包含 Planning Budget、Profile/Policy typed resource values 与 evidenceRef | 配置资源限额变化可保持相同 bundle digest，currentness/audit 无法识别事实变化 | 改为版本化 length-prefixed canonical 摘要，纳入预算、排序后的 contribution、contract canonical digest 和 evidenceRef |
| CR-003 | medium | startup_gate | metadata/security configuration | Capability Registry 仅校验 declaration/consumer，未校验所有 Profile/Policy 是否为每个注册 capability 的 ContractRef/type 提供 contribution | 新 capability 或新 contract 可启动成功，到 freeze 时才失败，形成半闭合组合 | 新增 `AgentMetadataResourceLimitStartupGate`，启动时对全部 Definition × Profile/Policy 做 typed require，任一缺失拒绝启动 |
| CR-004 | high | operation_binding | `CapabilityOperationMetadata.java`、`CapabilityOperationFailure.java`、`DocumentCapabilityHandler.java` | success outcome 只取 candidate，未统一核对 operationId/type/limit reference；metadata 允许 success 同时声明 deadline/cancel touched，failure code 与 termination 可矛盾 | 错绑、迟到或终态伪造的 Provider 候选可能进入 Handler/Result Security | 新增共享 `CapabilityOperationOutcomes.requireBoundSuccess`；Handler 四类调用统一过门禁；构造期强制 success/终态与 failure code/termination 一致 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | medium | 当前主文档第 10.2、10.6 节 | Permission typed contribution 演进契约不足 | 文档要求 Permission 形成 contract-specific typed value，但当前 `UserPermission` 公共事实没有资源限额字段，也未定义 capability-specific adapter 的输入/注册协议 | 当前实现只能以已冻结值作为执行复检中的 Permission 中性上界；安全上不放大，但无法表达“权限服务仅收紧资源值” | 经文档与公共契约授权后，定义 Permission resource claim/adaptor registry、version/currentness 和缺省中性证明；本次不擅自扩展公共 auth DTO |
| DOC-002 | medium | 当前主文档第 10.13、23～24 节 | Reload 状态描述超前 | 文档声明 metadata reload 的 resource candidate gate 已实施；仓库中的 `AgentMetadataReloader` 仅有测试 seam，未作为生产 bean 装配，也未接入新增 resource gate | 若未来直接启用现有 reloader，candidate 只校验 domain refs，资源 contribution 闭合仍可能漏检 | 在授权启用 reload 前先把 startup gate 抽为 candidate validator，并与 Contract Registry/Capability Registration 组成同一发布 bundle；当前生产启动路径已闭合 |

## 6. 修改摘要

| 轮次 | 修改范围 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | Resource resolver/Authorization | 新增 execution recheck 单调求交并统一注入 resolver bean | CR-001 | 已修复 |
| 1 | Metadata bootstrap | bundle digest 纳入 Planning Budget 与 typed contribution canonical digest | CR-002 | 已修复 |
| 1 | Operation SPI/Handler | success binding gate、metadata/termination 不变量、Document 四类 operation 接入 | CR-004 | 已修复 |
| 2 | Startup composition | 增加 Definition × Profile/Policy contribution 全量闭合门禁及负向测试 | CR-003 | 已修复 |
| 2 | 全范围复审 | 全量 Java 回归、旧路径扫描、契约漂移与 diff 检查 | CR-001～CR-004 | 未发现新增可处理问题 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `... -Dtest=CapabilityOperationOutcomeTest,CapabilityResourceLimitResolverTest,AuthorizationExecutionPortTest,AgentMetadataProductionBootstrapTest,DocumentCapabilityHandlerTest ... test` | 通过 | 10 passed |
| 2 | `... -Dtest=AgentMetadataResourceLimitStartupGateTest,AgentMetadataSecurityConfigurationTest ... test` | 通过 | 2 passed |
| 2 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-service -am test` | 通过 | Reactor BUILD SUCCESS；`agent-service` 454 passed；`agent-adapter-api` 9 passed |
| 2 | `rg -n 'ExecutionBudget|RuntimeDocumentQueryRewriteClient|/runtime/v1/document/rewrite' agent-service/src/main/java agent-runtime/app` | 通过 | 无旧执行预算或 Runtime rewrite 生产路径匹配 |
| 2 | `python agent-runtime/scripts/check_contract_drift.py` | 通过 | active Python codegen 可重复且 provenance 有效 |
| 2 | `git diff --check` | 通过 | 无空白错误；仅既有 CRLF/LF 转换告警 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 触发场景 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | Permission 不能提供 contract-specific 数值收紧 | 权限系统未来按用户/租户返回更严格 rows/bytes/evidence 上限 | 先解决 DOC-001，再补 current Permission contribution 与 execution recheck 收紧测试 |
| RISK-002 | medium | Reload candidate 尚未复用启动资源门禁 | 未来把 `AgentMetadataReloader` 装配为生产入口 | 启用前完成 DOC-002；当前不要把测试 seam 直接暴露为管理接口 |
| RISK-003 | low | Mockito 动态 agent 存在未来 JDK 兼容告警 | 升级到默认禁止动态 agent 的未来 JDK | 依赖治理时统一配置 Mockito agent，本次不新增生产依赖 |

## 9. 结论

最终结论：
- 通过。

说明：
- 4 项代码问题已在两轮评审—修复中闭合，完整 Java 回归、旧路径扫描和契约漂移检查均通过。
- 未修改主详细设计、L0/L1 或关联文档；Permission typed claim 与生产 reload 的文档/演进问题仅记录，未越权扩展公共契约。
- 未执行提交、推送或远程操作。
