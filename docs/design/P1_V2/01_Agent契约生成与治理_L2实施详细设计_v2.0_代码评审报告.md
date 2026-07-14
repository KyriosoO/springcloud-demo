# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 1 |
| 依据文档数量 | 8 |
| 评审代码范围 | `agent-api` Runtime 契约、OpenAPI/fixtures、`agent-runtime` generated models/Route/Plan HTTP 边界、`agent-service` Runtime client 与 Planning outcome 校验、直接相关测试和生成脚本 |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 通过；4 项契约/安全问题已修复，无剩余可处理问题 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `01_Agent契约生成与治理_L2实施详细设计_v2.0.md` | detailed_design | 0 | 是 | 已读取 | 当前主文档 |
| `02_可信执行内核与Invocation生命周期_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取边界 | Planning/Execution 消费方 |
| `03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取边界 | Context/Result 契约消费方 |
| `04_Adapter与DomainMetadata治理_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取边界 | Domain 投影消费方 |
| `../Agent契约与规划架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | 主要 L1 |
| `../Agent能力执行内核架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | 执行边界 L1 |
| `../Agent元数据与上下文安全架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | 安全边界 L1 |
| `../Agent目标架构总览_v1.0.md` | architecture | 3 | 否 | 已读取相关约束 | L0 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | 第 6、8、10.1 节 | Java 是跨服务结构唯一源，ContractRef 不得绑定类名或对象地址 | `agent-api/.../contract/**`、`AgentExecutionContracts`、`ContractRef` | 符合 |
| DOC-C-002 | 第 10.2、10.4、10.5 节 | Route/Plan 必须回显同一 requestId；不匹配必须拒绝 | `agent-runtime/app/core/runtime_planning.py`、`AgentRuntimeClient`、Route/Plan validator | 修复后符合 |
| DOC-C-003 | 第 10.2.1 节 | Runtime metadata 必填、非负，且 `repairAttempts <= max(providerAttempts-1,0)` | `RuntimeOperationMetadata.java`、Python candidate parser、Java HTTP/Planning 边界 | 修复后符合 |
| DOC-C-004 | 第 10.6、11 节 | 400/401/422/500/503/504 均返回统一 typed `RuntimeErrorResponse` | `agent-runtime/app/main.py`、`AgentRuntimeClient.java` | 修复后符合 |
| DOC-C-005 | 第 10.8～10.10 节 | OpenAPI/fixtures/generated Python 单向生成且 drift 可重复 | OpenAPI factory、fixtures、生成脚本、`generated_models.py`、drift 脚本 | 符合 |
| DOC-C-006 | 第 11、15、18 节 | Runtime 只暴露 Route/Plan，错误和日志不得泄露 prompt、请求正文或 provider body | `runtime_api.py`、`main.py`、`llm_client.py` | 修复后符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|---|
| CR-001 | high | api_contract_consistency | `agent-runtime/app/core/runtime_planning.py`、`test_planning.py` | 第 10.2.1、10.5 节 | Plan 候选的错误 requestId 被静默覆盖，测试把放宽行为固化为期望；Route 则正确拒绝 | 迟到或错误候选可能被重新绑定到当前请求，破坏关联审计和 fail-closed 语义 | 已删除改写逻辑，并将测试改为拒绝不匹配 requestId |
| CR-002 | medium | api_contract_consistency | `RuntimeOperationMetadata.java`、`AgentRuntimeClient.java`、Planning validators | 第 10.2.1 节 | Java HTTP 边界仅校验 operation；错误响应缺失 metadata 或不可能的 repair/provider 计数组合仍会被接受 | 不可信 Runtime 遥测可能进入 Planning 审计，导致契约漂移和错误判断 | 已增加组合不变量校验，并在 Runtime parser、Java client、validator 和 audit 边界统一调用 |
| CR-003 | medium | error_handling | `agent-runtime/app/main.py` | 第 10.6、11 节 | 未捕获异常没有统一 500 handler | 默认 FastAPI 500 body 不满足 `RuntimeErrorResponse` 契约，Java 侧只能按协议错误处理 | 已增加安全的 `500 INTERNAL_ERROR` typed handler 和测试 |
| CR-004 | high | security | `agent-runtime/app/main.py`、`test_runtime_api.py` | 第 15、18 节 | 请求校验异常把包含原始 `input` 的 errors 和异常栈写入日志 | 非法请求中的用户正文或敏感额外字段可能落日志 | 已仅保留错误类型、位置和安全消息；未知异常仅记录异常类型，新增不泄露测试 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | medium | 当前主文档第 20 节 | 验证命令不可执行 | `-pl agent-api` 无法选择聚合 POM 中路径为 `../agent-api` 的 reactor 项目 | 文档最小命令无法从仓库根目录复现 | 后续获得文档修改授权后改为 `-pl :agent-api` 或明确工作目录/模块路径 |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | `agent-runtime/app/core/runtime_planning.py`、`tests/test_planning.py` | Plan requestId fail closed；Runtime metadata 组合校验 | CR-001、CR-002 | 已修复 |
| 1 | `agent-api/.../RuntimeOperationMetadata.java` | 增加统一字段及组合不变量校验 | CR-002 | 已修复 |
| 1 | `agent-service/.../AgentRuntimeClient.java`、Route/Plan validators、`PlanningOperationAudit.java` | 在成功、错误、Planning 和审计边界拒绝无效 metadata | CR-002 | 已修复 |
| 1 | `agent-runtime/app/main.py`、`tests/test_runtime_api.py` | 增加 typed 500；清理输入值和未知异常日志泄露 | CR-003、CR-004 | 已修复 |
| 1 | `AgentRuntimeClientContractTest.java` | 增加缺失 metadata 与非法计数的负向契约测试 | CR-002 | 已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `python -m pytest agent-runtime/tests/test_planning.py agent-runtime/tests/test_contracts.py` | 最终通过 | 53 passed；初次运行发现 repair 测试夹具依赖旧 requestId 改写，修正夹具后通过 |
| 1 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-service -am '-Dtest=AgentRuntimeClientContractTest,RouteOutcomeValidatorTest,PlanOutcomeValidatorTest' '-Dsurefire.failIfNoSpecifiedTests=false' test` | 最终通过 | 14 passed；初次有效运行发现测试构造器未真正删除 metadata，修正测试数据后通过 |
| 1 | `python -m pytest agent-runtime/tests` | 通过 | 89 passed，1 项第三方 Starlette/httpx 弃用告警 |
| 1 | `python agent-runtime/scripts/check_contract_drift.py` | 通过 | generated Python 可重复且 provenance 有效 |
| 1 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-api -am test` | 通过 | 47 passed，OpenAPI/fixtures/architecture tests 全部通过 |
| 1 | `git diff --check` | 通过 | 无空白错误 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | low | Python generated model本身不能表达跨字段算术关系 | OpenAPI/Pydantic 生成链不能直接表达 `repairAttempts <= providerAttempts-1` | 当前 Runtime parser 与 Java 消费边界均已强制校验；若新增直接 generated-model 消费者，必须复用同一边界校验 |
| RISK-002 | low | TestClient 第三方弃用告警 | Starlette 当前通过旧 httpx 兼容层工作 | 在依赖统一升级时处理，不为本次契约修复新增生产依赖 |

## 9. 结论

最终结论：
- 通过。

说明：
- 4 项问题均已在第一轮完成修复并通过再评审。
- 修复没有新增或删除 wire 字段，没有手工修改 generated model，也没有扩大到 Kernel、权限或业务 Adapter 行为。
