# 单体 Agent 智能体总体架构 L0 v2.0

- 文档层级：L0
- 文档状态：In Review

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档层级 | L0 |
| 文档状态 | In Review |
| 内部结论 | Ready for Implementation（内部三轮审查通过） |
| 日期 | 2026-07-22 |
| 文档范围 | 新单 Agent 的系统目标、权威边界、质量属性和下位设计约束 |
| 不代表 | 已实现、正式批准、目标系统质量通过或生产放行 |

## 2. 修订历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v2.0 | 2026-07-22 | 删除旧项目基线后以官方 Python LangGraph 重建精简单 Agent，移除双编排、持久执行状态和迁移治理。 |

## 3. 架构目标与非目标

### 3.1 目标与成功标准

建设一个面向内部用户的单 Agent 入口，以自然语言完成三类能力：

- `QUERY`：按受控条件查询员工、交易等业务数据；
- `AGGREGATE`：按受控维度和指标聚合业务数据；
- `DOCUMENT`：在获准语料库中检索证据并回答或总结，返回可核验引用。

首阶段优先形成可验证的端到端能力，不建设通用 Agent 平台。成功标准是：三类能力各有真实上游合同、确定性节点、失败路径测试和可观察结果；模型不能越过 LangGraph 中的授权、计划准入与结果安全节点直接访问数据。

### 3.2 范围内

- 单一同步对话入口、意图识别、结构化计划、能力路由和统一响应；
- 用户身份与权限上界消费、Agent 能力/字段/语料库策略、结果再投影；
- 业务查询/聚合编排和 DOCUMENT 检索问答；
- 模型访问、超时、错误、审计、指标和最小质量门禁；
- 检索与索引基础设施的查询、写入、重建和回滚边界。

### 3.3 非目标

- 多 Agent、自治任务网络、插件市场或通用工作流引擎；
- Java 主编排加 Python LangGraph Runtime 的双编排/双状态权威；
- 首阶段异步执行、持久化 invocation、租约、恢复、回调或 exactly-once；
- Agent 自建 IAM、业务主数据、文档主存储、通用 DLP 或模型网关；
- 未经需求证明的向量检索、重排、复杂融合、文档级 ACL 或多写者索引控制面。

## 4. 能力版图、系统分解与权威边界

```text
用户/调用方
    │ HTTPS + JWT
    ▼
网关 ──► 单体 agent-service（后续新增，一个 Python LangGraph 部署单元）
              ├─► auth-service：身份/RBAC 上界
              ├─► employee-service、mq-procedure-service：业务查询/聚合
              ├─► es-query-service：检索与索引原子能力
              └─► 获准模型端点：规划、回答、总结
                         ▲
文档源/业务服务 ──索引写入─┘
```

| 资产 | 唯一所有者 | Agent 权限 |
|---|---|---|
| 身份、角色、权限码 | `auth-service` | 读取上界，不复制身份权威 |
| 员工/交易主数据 | 对应业务服务 | 调用稳定 API，不直连数据库 |
| 原始文档与版本 | 文档源 | 读取获准内容，不把 ES 当源数据 |
| 索引和检索实现 | `es-query-service` | 提交受控查询/写入，不拼接原生 DSL |
| 能力、字段、语料库策略 | Agent | 在 Auth 上界内进一步收紧 |
| 模型输入和输出 | Agent | 最小投影、严格校验，不作为授权事实 |

## 5. 组件关系与顶层调用链

### 5.1 Agent 应用

后续仅新增一个 Python `agent-service` 项目，以官方 `langgraph` 的 `StateGraph` 作为唯一编排运行时，以 ASGI HTTP 层（建议 FastAPI）暴露入口。内部按 Python 包分层，而不是拆成 Java 主服务、Python Runtime、API/Adapter 子项目：

1. `api`：HTTP DTO、错误封套、认证入口；
2. `graph`：类型化 `AgentState`、固定节点、条件边和图构建；
3. `planning`：模型调用、计划解析和确定性校验；
4. `capabilities.query|aggregate|document`：三类能力节点；
5. `clients`：Auth、Java 业务服务、检索和模型客户端；
6. `security`：授权交集、输入/输出投影；
7. `observability`：指标、结构化审计和脱敏日志。

模块依赖只允许 `api -> graph -> planning/capabilities/security -> clients`；`clients`不得反向依赖图节点，安全节点不得由能力或外部 Client 绕过。

### 5.2 检索与索引基础设施

检索保持 Agent 外部独立边界。首阶段只要求关键词检索、受控过滤、批量写入、删除、全量/增量重建和任务查询。是否启用向量召回、重排或专用管理面，必须由质量数据或多写者需求触发。

## 6. 全局数据流、状态管理与一致性

首版主图固定为：

```text
START -> auth_context -> plan -> validate
  -> QUERY | AGGREGATE | DOCUMENT | CLARIFY | REJECT

DOCUMENT -> retrieve -> evidence_gate -> generate_or_summary -> citation_gate

所有成功路径 -> result_security -> END
CLARIFY/REJECT/安全失败 -> safe_response -> END
```

`auth_context`、`validate`、三类上游调用、`evidence_gate`、`citation_gate`和`result_security`都是确定性节点；模型节点仅为`plan`与DOCUMENT生成/总结。一个请求只进入一个能力分支，不支持模型自主 Tool 循环、动态节点或多 Agent。

## 7. 架构原则与全局不变量

| 编号 | 不可违反的约束 |
|---|---|
| AD-01 | 官方 Python LangGraph 是唯一 Agent 编排运行时和唯一 Agent 部署单元；禁止 Java 主编排 + Python Runtime。 |
| AD-02 | 首阶段请求同步完成，`StateGraph.compile()`不配置 checkpointer；不得宣称持久记忆、恢复或人工中断能力。 |
| AD-03 | 图结构固定且受限；模型只提议结构化计划，确定性 validate 节点是执行准入唯一权威。 |
| AD-04 | Auth 给出上界，Agent 与资源事实只做交集；事实缺失、过期或冲突时失败关闭。 |
| AD-05 | 模型输入最小披露，模型/检索输出均不可信，最终响应必须再次校验和投影。 |
| AD-06 | Agent 不直连上游数据库，不复制业务主数据，不承担上游事务。 |
| AD-07 | DOCUMENT 编排归 Agent；搜索/索引原子能力归检索基础设施，原始文档归文档源。 |
| AD-08 | 权限过滤必须在召回前进入检索条件；召回后再过滤不能替代该约束。 |
| AD-09 | 每个超时/重试策略只有一个所有者；写操作默认不重试。 |
| AD-10 | 公共合同使用显式版本、封闭枚举和未知字段拒绝；L0 不冻结字段级 Schema。 |
| AD-11 | 不以旧项目、旧报告、合成 PoC 或连通性证明推导目标实现已通过。 |
| AD-12 | 多 Agent、异步恢复、向量/重排、细粒度 ACL 等扩展须以明确需求和度量触发。 |
| AD-13 | 原始 JWT、服务密钥、Prompt、上游正文不得进入 Graph State 或外部 tracing；Graph 输出必须由封闭 output schema 限定。 |

## 8. 质量属性与验证口径

| 属性 | 首阶段目标 | 验证方式 |
|---|---|---|
| 安全 | 越权计划、未知字段、过期权限、无引用回答全部失败关闭 | 单元/合同/集成负向测试 |
| 正确性 | 计划到上游请求可确定映射；聚合结果不由模型计算 | 固定夹具和真实上游合同测试 |
| 性能 | 同步请求有绝对 deadline；各依赖预算之和不超过总预算 | 超时/取消测试和指标 |
| 可用性 | 依赖失败返回类型化错误，不静默切换更宽路径 | 故障注入和错误映射测试 |
| 可维护性 | 一个 Python 部署单元、一个固定图、三个能力包、少量稳定 Client | 图拓扑快照和包依赖测试 |
| 可审计 | requestId、主体摘要、能力、上游、策略版本、结果码可关联 | 审计字段测试；正文不落日志 |

## 9. 风险与演进触发器

| 风险 | 当前控制 | 何时演进 |
|---|---|---|
| 模型计划不稳定 | 小 Schema、低温度、严格校验、澄清 | 真实失败样本证明需更多策略 |
| 同步超时 | 限制结果量/上下文、绝对 deadline | 明确长任务需求后设计异步 L2 |
| 关键词召回不足 | 引用质量集和无证据拒答 | Recall/答案质量未达标再引入向量/重排 |
| 上游合同不齐 | 实现前合同基线门禁 | 先修上游合同，不在 Agent 内猜测 |
| 供应商/模型不合规 | 目标白名单和数据分级 | 合规、合同和效果证据齐全后启用 |
| LangGraph 版本/依赖风险 | 锁定兼容版本、图拓扑与状态合同测试 | 升级前跑完整图回归；不使用未需要的高级能力 |
| 仓库硬性 Java-only 约束 | 实现前 PoC 验证部署与安全合同 | 只有约束被证实才评估 LangGraph4j；其为独立社区项目，成熟度另审 |

## 10. 关键架构决策

| 决策 | 结论 | 主要取舍 |
|---|---|---|
| ADR-01 运行时 | 官方 Python LangGraph 是唯一 Agent 编排/部署单元 | 绿地期直接冻结图与状态合同，避免后续重写；Java 服务保持外部上游 |
| ADR-02 图能力 | 受限同步 StateGraph、请求内类型化状态、无 checkpointer | 使用显式分支但不提前引入恢复、记忆和人工审批复杂度 |
| ADR-03 模型权限 | 模型提议，确定性节点准入 | 牺牲部分自治性，换取稳定合同和失败关闭 |
| ADR-04 检索 | 独立 `es-query-*`，首阶段关键词优先 | 保留可演进边界，不提前承担向量/融合复杂度 |
| ADR-05 模块组织 | 一个项目内按能力包分层 | 避免空 API/Adapter 服务，出现真实复用再抽取 |
| ADR-06 Java 备选 | 仅当硬性 Java-only 约束被验证后评估 LangGraph4j | 它不是官方 Python LangGraph，依赖成熟度与能力差异需单独 PoC/评审 |

## 11. 下位 L1 治理与实施顺序

两个 L1 分别细化 Agent 应用与检索基础设施；L2 按 `01 安全入口/规划 -> 02 权限/模型 -> 03 QUERY/AGGREGATE -> 05 检索基础设施 -> 04 DOCUMENT` 实现和联调。L2 可补字段、类和测试落点，但不得放宽 AD-01～AD-13。

两个下位 L1 必须分别治理 LangGraph Agent 应用与检索基础设施，不得相互重定义所有权；L1 只能收紧本 L0，不得自行引入 Java 主编排、第二 Agent 运行时、checkpointer、异步恢复或模型 Tool 权限。

实现前首个 PoC 固定为 `AUTH -> PLAN -> QUERY/CLARIFY -> RESULT_SECURITY`，验证类型化状态、非法计划不触发上游、deadline/迟到结果、Python 到 Spring 上游的服务认证与错误映射。PoC 通过仍不等于目标系统质量或生产批准。

官方设计依据：LangGraph `StateGraph`以共享 state 连接节点并在 compile 后执行；持久化、跨交互记忆和故障恢复依赖 checkpointer。本首版显式不配置 checkpointer，避免把框架可选能力误写为已具备能力：<https://reference.langchain.com/python/langgraph/graph/state/StateGraph>、<https://docs.langchain.com/oss/python/langgraph/persistence>。

## 12. 三轮内部审查

三轮结果及修订项统一记录于[内部审查记录](内部审查记录_v2.0.md)。结论仅为内部实现就绪，不替代独立正式评审。
