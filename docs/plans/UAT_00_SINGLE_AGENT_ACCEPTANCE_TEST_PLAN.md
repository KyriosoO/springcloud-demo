# [UAT_00] 单体 Agent 第一批验收测试计划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | UAT_00 |
| 当前版本 | v0.4 |
| 状态 | Reviewed |
| 更新日期 | 2026-08-24 |
| 范围 | 公共接入冒烟、Employee、Transaction、结构化查询阶段收口 |
| 前置计划 | [`P3_00`](P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md) v1.25 |
| 当前执行状态 | Blocked：Business QueryPlan 代码和 `GATE-UAT-006` 未完成 |

## 2. 验收目标

第一批 UAT 证明：

1. 公共接入的认证、严格 JSON、有限失败和单动作约束正确；
2. Employee/Transaction 成功查询必须由真实 LLM 生成包含 `domain/action/arguments` 的受限 QueryPlan；
3. 本地仅按代码/配置校验、绑定并调用对应 Adapter；
4. 业务服务执行最终授权和 SQL/ES；
5. 模型失败或计划非法时无 Resolver、Knowledge、另一域或数据库/ES 旁路；
6. 结果模型出域保持关闭，本批只验收规划模型调用。

Knowledge 查询 UAT 不在本批，待结构化查询收口后单独执行。

## 3. 当前事实与执行阻断

QueryPlan 合同、模型任务、两域 definition/config 与 Runtime non-live 候选已有实现；system E2E、真实集成和 UAT 尚未完成。旧 resolver/ID-only UAT fixture 与 evidence 只作为历史审计资产，不得执行为当前用例或满足本版本门禁；无审计价值的旧可执行测试由 P3 清理。

开始成功场景前必须满足：

- P3 `WP-BQ-PLAN-CONTRACT-01`、`WP-BQ-MODEL-QUERYPLAN-01`、两域包、Runtime cutover 和 non-live E2E 均 Done；
- `GATE-065` 真实集成和 `GATE-066` 唯一链路已关闭；
- `GATE-UAT-006` 绑定 UAT HEAD、task/prompt/catalog/config snapshot、用例、账号/数据、模型和最大调用预算；
- 默认配置仍为 stub/动作 disabled；UAT 通过显式 opt-in 启用。

## 4. UAT 唯一运行链

```text
UAT question
  → agent-service auth / strict JSON
  → agent-runtime Business Guard
  → real LLM business-query-plan-v1
  → exact decode + config validation + protected value binding
  → agent-core single action
  → Employee or Transaction Adapter
  → existing business service final authorization/query
  → local deterministic result
```

认证/strict JSON/输入安全可在模型前拒绝；除此之外，Employee/Transaction 语义成功或不支持判定不得绕过 LLM。

## 5. 环境与数据边界

### 5.1 配置

- 显式 `AGENT_MODEL_PROVIDER=deepseek` 仅用于 Employee/Transaction live UAT；
- QueryPlan task/version、prompt、catalog/config snapshot 和代码 HEAD 冻结；
- answer generation、Business result egress、Knowledge fallback、自动重试均关闭；
- Employee/Transaction action 显式启用，其他业务 action 不注册；
- 所有服务使用受控本地/隔离端口并记录 PID；不得停止维护者管理的进程。

### 5.2 凭证与数据

- `LLM_API_KEY`、JWT、员工标识、Transaction 查询值只驻留进程内存；
- Employee 使用维护者确认的测试标识或独立 synthetic fixture，禁止写入文档/evidence/log；
- Transaction 使用只读、已确认存在的有限查询值；禁止持久化原始 rows；
- evidence 只记录 case ID、snapshot/hash、有限状态、调用计数、结果字段存在性和零泄漏结论。

## 6. 工作项与顺序

| UAT ID | 内容 | 直接依赖 | 状态 |
|---|---|---|---|
| `UAT-PUBLIC-01` | 公共接入冒烟 | `GATE-UAT-006`、P3 non-live E2E | Blocked |
| `UAT-EMP-01` | Employee LLM QueryPlan UAT | `UAT-PUBLIC-01`、P3 live integration | Blocked |
| `UAT-TXN-01` | Transaction LLM QueryPlan UAT | `UAT-PUBLIC-01`、P3 live integration | Blocked |
| `UAT-STRUCTURED-CLOSE-01` | Access/Core/plan/config/JWT/单动作/禁止旁路回归与阶段结论 | `UAT-EMP-01`,`UAT-TXN-01` | Blocked |

Employee 与 Transaction 可在公共冒烟后独立执行；阶段收口等待两者完成。

## 7. 公共接入冒烟

| Case | 输入/前置 | 期望 | 模型/业务调用 |
|---|---|---|---|
| `PUB-001` | missing JWT | `unauthenticated` | plan=0，Employee/Txn=0 |
| `PUB-002` | malformed/unknown auth | `unauthenticated/forbidden` | 0/0 |
| `PUB-003` | extra JSON field/duplicate key/wrong content type/oversize | `invalid_argument` | 0/0 |
| `PUB-004` | default stub + 合格 Business 问题 | 固定 model failure，失败关闭 | plan stub attempt≤1，业务=0 |
| `PUB-005` | fake planner exact unsupported（non-live） | `unsupported` | fake plan=1，业务=0 |
| `PUB-006` | fake planner 产生第二 action/跨域 plan | `invalid_argument` | Core/业务=0 |

公共冒烟不以 stub 生成成功 QueryPlan；stub 的验收目标只是证明默认环境不误执行。

## 8. Employee UAT

### 8.1 支持场景

| Case | 问题类型 | QueryPlan 断言 | 服务/结果断言 |
|---|---|---|---|
| `EMP-001` | 查询一个已存在测试员工详情 | `employee/employee.detail`；argument 为 `value_ref` | planning=1、detail=1、success；标识不出域 |
| `EMP-002` | 同义表达的单员工详情 | 同上 | 仅一次 detail；字段投影正确 |
| `EMP-003` | ADMIN 用户 | 同上 | 业务服务最终允许 |
| `EMP-004` | VIEWER 用户 | 同上 | 按业务 guard 当前矩阵最终允许 |

### 8.2 失败与缺口

| Case | 问题/前置 | 期望 | 调用断言 |
|---|---|---|---|
| `EMP-005` | “帮我查看上海的员工” | `unsupported`；记录现有通用 ES 搜索缺少最终角色授权与受限响应契约 | plan=1，detail/list/ES=0 |
| `EMP-006` | 模型输出 literal employee ID | `invalid_argument` | Employee=0 |
| `EMP-007` | ref 缺失/跨请求 | `invalid_argument` | Employee=0 |
| `EMP-008` | 业务服务拒绝角色 | `forbidden` | plan=1，detail=1，不改义 |
| `EMP-009` | 模型 timeout/schema invalid | `timeout/invalid_argument` | Employee/Knowledge/Transaction=0 |

敏感扫描必须证明模型输入/输出捕获、日志和 evidence 均不含 Employee 标识/JWT/原始响应。

## 9. Transaction UAT

### 9.1 支持场景

| Case | 问题类型 | QueryPlan 断言 | 服务/结果断言 |
|---|---|---|---|
| `TXN-001` | 按交易类型精确查询 | `transaction.search/trans_type` | plan=1、search=1、page=1 |
| `TXN-002` | 按类型包含查询 | `trans_type_contains` | contains 安全字符、search=1 |
| `TXN-003` | 精确金额 | canonical decimal string | wire JSON number、Java BigDecimal、无舍入 |
| `TXN-004` | 金额开区间 | `amount_gt/amount_lt` 且 gt<lt | search=1、边界正确 |
| `TXN-005` | size + 有限排序 | size≤50、sort≤2/allowlist | response page/size/totalExact 保真 |
| `TXN-006` | ADMIN/VIEWER | 相同计划合同 | 业务服务最终授权矩阵正确 |

### 9.2 失败

| Case | 问题/计划 | 期望 | 调用断言 |
|---|---|---|---|
| `TXN-007` | Date 条件 | `unsupported` | search/其他 endpoint=0 |
| `TXN-008` | 聚合/detail/write | `unsupported` | search/其他 endpoint=0 |
| `TXN-009` | float/scale>2/互斥金额/空条件 | `invalid_argument` | search=0 |
| `TXN-010` | sort/page 超界、物理键或 SQL/DSL/URL 形态文本 literal | `invalid_argument/unsupported` | search=0 |
| `TXN-011` | 模型 failure/schema invalid | 固定失败 | Transaction/Employee/Knowledge=0 |
| `TXN-012` | 业务 forbidden/no result | `forbidden/no_result` | search=1，状态不改义 |

## 10. 结构化查询阶段收口

必须回归：

- Access 认证、strict JSON、deadline/cancel；
- Business Guard slotting 和并发隔离；
- model task/prompt/catalog/config snapshot 一致；
- QueryPlan exact decode、业务 validator、binder、既有 argument validator；
- Core action latch、handler/Adapter 唯一；
- JWT 仅透传业务服务、最终权限在域内；
- Employee GET/no-body、Transaction POST/ExactDecimal 跨语言合同；
- model failure/illegal plan 下 Resolver、ID-only 补参、Knowledge、另一域和 DB/ES 直连均不可达；
- answer model/Business result egress 调用为0；
- 日志、evidence 和临时文件零敏感泄漏。

阶段结论只能是 `passed`、`failed` 或 `blocked`，并列出逐 case 状态和未关闭缺口。Employee 筛选保持已知 unsupported 不算缺陷；现有通用 ES 端点不能因具备字段能力而绕过最终角色授权或受限契约。若需求要扩大，退出 UAT 并回到业务接口与设计授权。

## 11. 调用预算与一次性授权

非 live 准备阶段使用 fake transport，模型真实调用为0。正式 UAT 前由 launcher 根据冻结用例计算精确最大规划调用数：每个进入 Business 语义处理的 case 最多1次；认证/strict JSON/输入策略拒绝为0；自动 retry/resume=0。

授权必须绑定：frozen HEAD、run ID、manifest SHA-256、model/task/prompt/catalog/config snapshots、case IDs、最大 DeepSeek 调用数、Employee detail 上限、Transaction search 上限和 authorization reference。首个 outbound 后授权耗尽；失败不补跑。

## 12. Evidence 与通过标准

有限 evidence 至少包含：

- run/manifest/authorization/hash 绑定；
- case ID、预期/实际有限状态；
- validated domain/action/argument key/type（不含值）；
- planning/Core/Employee/Transaction/Knowledge/answer 调用整数；
- config snapshot、task version、终态与耗时区间；
- JWT/标识/业务值/model raw/log leak 计数均为0；
- 服务 PID/清理有限结论。

通过标准：

1. 所有必测 case 终态符合预期；
2. 每个支持的业务 case planning=1、对应业务 endpoint=1、Core=1；
3. 每个失败/不支持 case 的后续计数符合第7～9章；
4. 任何 case 的 Resolver、另一业务域、Knowledge fallback、answer model 均为0；
5. 权限、Decimal、跨语言、snapshot、单动作和零泄漏全部通过；
6. 无测试通过依赖放宽 validator、删除断言或改变既有业务接口。

## 13. 停止条件与回滚

出现以下任一条件立即停止：manifest/hash 不一致、真实调用预算不可证明、需要新业务接口/DTO/DB/依赖/扩权、敏感值进入模型/日志/evidence、产生第二动作或 fallback、服务进程归属不明。

回滚：停止且仅停止 UAT 启动并核实 PID 的进程；删除扫描后的临时原始日志；恢复默认 stub 和 action disabled；保留 append-only 有限失败证据；不修改业务数据或历史 evidence。

## 14. 执行结论与评审

| 阶段 | 重点 | 结果 |
|---|---|---|
| 内审1 | 公共→Employee→Transaction→收口顺序与预算 | 补齐前置门禁、调用断言和 evidence，修复后通过 |
| 内审2 | default stub、unsupported 与失败关闭 | 明确 stub 仅证明失败关闭，修复后通过 |
| 内审3 | 两域跨语言、权限、接口缺口与无环性 | Employee ES 复用条件如实记录；P3/UAT 门禁分属清晰，修复后通过 |
| 独立评审 R1～R3 | UAT 与跨层一致性 | 补齐物理表达式文本负例与 unsupported 上位合同；R3 无发现，通过 |
| v0.4 内审1 | 当前状态与旧用例隔离 | 区分 Runtime non-live 候选与尚未完成的 system/live/UAT |
| v0.4 内审2 | 历史 fixture/evidence | 保留旧资产但禁止执行为本版本证据；不删除冻结文件 |
| v0.4 内审3 | 门禁、预算、DAG | 清理不关闭 live/UAT 门禁，不改变一次性授权和调用预算 |
| v0.4 独立评审 R1～R3 | 旧用例不可执行与历史资产保留 | 补充 launcher 清理、冻结 fixture 只读边界后，R3 无发现 |

当前：`GATE-UAT-006` Open，四个 UAT 工作项均 Blocked。只有 P3 新工作包实施和受控 live 集成完成后，才可申请正式 UAT 执行授权。
