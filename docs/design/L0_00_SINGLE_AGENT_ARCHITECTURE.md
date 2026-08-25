# [L0_00] 单体 Agent 总体架构

> 文档层级：L0
> 文档状态：Approved

## 1. 文档信息、修订历史与来源

| 项目 | 内容 |
|---|---|
| 当前版本 | v2.0 |
| 更新时间 | 2026-08-25 |
| 上位需求 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v2.0 |
| 权威范围 | 系统边界、部署组件、分域、顶层调用链、全局安全和下位 L1 治理 |
| 当前实现 | Knowledge 基线、新版 filters/config/三动作 Adapter/组合根及 Employee ES 端点级角色转换均已实施并通过 non-live；成功 live/UAT 未完成 |
| 归档来源 | [v1.5 已评审旧版](历史文档/L0_00_SINGLE_AGENT_ARCHITECTURE_v1.5.md)；当前代码和既有接口 |

修订历史：本文件为新建大版本权威基线；旧版本仅作为归档来源，不继承过程记录。

## 2. 架构目标、非目标与架构原则

目标是用最小可靠设计实现一个逻辑 Agent，保留 Knowledge、Employee、Transaction 三个能力域；优先满足可理解、可验证、权限隔离、敏感数据保护和失败关闭。非目标包括业务写入、聚合、多 Agent、规则平台、业务数据库直连、新业务公开接口和产品级审批或证据平台。

架构原则与全局不变量：LangGraph 是唯一编排权威；Core 每请求只执行一个已验证 Action；LLM 只生成受限逻辑 QueryPlan；配置只能收紧代码和业务接口；业务服务负责最终授权与数据访问；Knowledge 和 Business 独立，不互相 fallback。

## 3. 系统分解与组件关系

| 边界 | 组件 | 唯一核心职责 | 不负责 |
|---|---|---|---|
| 接入治理 | Java `agent-service` | 认证、严格请求合同、转发和请求上下文 | 编排、业务角色授权、SQL/ES |
| 编排运行 | Python `agent-runtime` / LangGraph | 单请求状态、模型规划、能力注册与执行 | 业务数据库访问、替代业务授权 |
| Knowledge | 既有 Knowledge Capability/Adapter | 独立问题改写、检索、证据与摘要 | Business 回退或业务查询 |
| Employee | Employee Adapter + `employee-service` | ES 条件查询或语义查询；服务完成最终授权 | Agent 直连 ES、两接口拼装 |
| Transaction | Transaction Adapter + `mq-procedure-service` | 固定 search 列表查询；服务完成最终授权与 SQL | Agent 直连数据库、聚合或写入 |

Spring 与 Python 是两个进程、一个逻辑 Agent；现有 auth-service 提供用户身份，业务数据和索引始终归属业务服务。依赖方向为 `Access → Runtime/Model → Business validation → Core/Adapter → 业务服务`。

## 4. 唯一顶层调用链

```text
用户问题 → 输入安全闸门与 request-local protected slots
→ LLM 基于最小化问题生成 QueryPlan(domain, action, arguments)
→ provider response 解码 → 业务 filters/config/slot 校验与绑定
→ 一个 ActionCandidate → 一个固定 Adapter/endpoint
→ 业务服务最终授权 → ES / 向量 / SQL → 受控列表结果
```

Employee 目标动作是 `employee.search` 与 `employee.semantic_search`；Transaction 目标动作是 `transaction.search`。`employee.detail` 仅为待核实迁移的既有动作，不是新目标列表链路。禁止 Local Resolver、ID-only 补参、跨域或 Knowledge fallback、普通/语义互相 fallback、第二业务调用，以及模型接触物理 SQL/ES/endpoint。

## 5. 权限、数据流与一致性

模型仅获得代码生成的模型安全目录和请求级 protected slot 引用；用户 JWT、真实标识、详细地址、完整业务响应、索引与数据库细节不出域。结果用户可见性和模型可见性独立执行默认拒绝交集；未知字段、敏感内容及策略冲突失败关闭。

Employee 两个现有 ES endpoint 已在 Controller 执行业务域读取守卫，但必须由端点级安全链显式绑定既有共享 JWT role converter；现有 detail 和其他 endpoint 行为不得改变，业务服务仍拥有最终授权。Transaction 既有 service 已执行读取授权。字段 `workBaseSi/workBaseAf` 不属于当前有效能力；员工地点仅使用 `contact_address → contactAddress`。

请求状态、slots、JWT、不可变配置 snapshot 和取消信号限定在单请求生命周期；业务 SQL/ES、数据事务和最终一致性由业务服务维护，Agent 不新增事务、缓存平台或数据同步机制。

## 6. 关键架构决策

| 决策 | 结论 | 影响 |
|---|---|---|
| `SA-AD-001` | Business 唯一路径必须经过 LLM filters QueryPlan、本地验证和一次 Adapter 调用 | 禁止 Resolver、补参及跨域 fallback |
| `SA-AD-002` | Employee 复用既有 search/vector-search，Transaction 复用既有 search | 不新增业务 endpoint/DTO |
| `SA-AD-003` | 统一字段级 JSON 配置只能收紧代码与服务合同 | 无配置中心和动态规则引擎 |
| `SA-AD-004` | 业务服务最终授权；受保护输入和结果模型出域分离 | Employee ES 守卫需单独补齐 |
| `SA-AD-005` | Knowledge 独立保留，旧 Business 证据不能证明新动作 | 明确当前实现与目标差距 |

## 7. 下位 L1 分域治理

| L1 | 权威责任 | 本次状态 |
|---|---|---|
| [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v2.0 | Runtime、LangGraph、Model Port、Core、Registry、组合根与单动作 | 新生产组合根与三动作 non-live 已实施，成功真实联调待完成 |
| [`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v1.0 | Knowledge 问题改写、检索、证据和摘要 | 保持既有权威，不做语义修改 |
| [`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v2.2 | Business fields/config、Employee/Transaction Adapter、端点级角色转换与最终授权 | 三动作和 Employee 真实 Servlet 过滤链 non-live 已实施；成功受控联调待完成 |

## 8. 质量属性、风险与当前结论

安全优先于可用性：非法计划、模型失败、配置失配、敏感 slot 和不支持条件均失败关闭；调用计数应证明每请求最多一次模型规划和一个业务动作。保留请求级取消与确定性数值/时间合同，但不引入高可用框架、复杂重试、分布式事务或独立监控平台。

主要风险：Employee ES endpoint-scoped 共享 converter 和读取守卫必须维持真实过滤链矩阵及历史 fallback 兼容；ES 原始 hits、受保护值和 Date/Decimal 必须维持当前已验证合同；workBase 字段数据无效且仅通过未配置自然不可达。non-live 和过滤链测试通过不等于成功受控真实联调或 UAT 完成。
