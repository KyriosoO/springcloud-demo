# 单体 Agent 应用与能力架构 L1 v2.0

- 文档层级：L1
- 文档状态：In Review

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档层级 | L1 |
| 文档状态 | In Review |
| 内部结论 | Ready for Implementation（内部三轮审查通过） |
| 上位文档 | `单体Agent智能体总体架构_L0_v2.0.md` |
| 文档范围 | 单体 `agent-service` 的入口、规划、安全编排和三类能力 |
| 边界外 | Auth、业务服务、检索/索引内部实现、原始文档、模型供应商平台 |

## 2. 修订历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v2.0 | 2026-07-22 | 以单 Python LangGraph 部署单元重建能力架构，禁止 Java/Python 双编排。 |

## 3. 架构目标与非目标

目标是以受限 `StateGraph` 和最少模块形成 QUERY、AGGREGATE、DOCUMENT 完整纵切。非目标包括 Java 主编排、第二 Agent Runtime、多 Agent、checkpointer/持久记忆、人工中断恢复、通用插件框架和模型直接 Tool 调用。

## 4. 上位约束映射

| L0 约束 | 本 L1 落实 |
|---|---|
| AD-01、AD-02 | 一个 Python LangGraph 部署单元、同步请求内类型化状态、无 checkpointer |
| AD-03、AD-04、AD-05、AD-13 | 固定图、模型提议、确定性节点校验、权限只收紧、封闭输出与 tracing 边界 |
| AD-06、AD-07、AD-08 | 上游数据所有权、DOCUMENT/检索责任分离、检索前过滤 |
| AD-09、AD-10、AD-11、AD-12 | 单一 deadline/retry 所有者、严格合同、状态不夸大、按证据演进 |
| ADR-01、ADR-02、ADR-03、ADR-05、ADR-06 | Python LangGraph 单运行时、受限图、确定性准入、单项目和 Java-only 备选门禁 |

## 5. 核心职责与职责边界

Agent 是一个 Python 模块化单体，不是 Java/Python 服务集合。官方 LangGraph `StateGraph`是唯一编排和状态流转权威；所有请求在同一进程中完成“鉴权—规划—校验—单能力执行—结果安全”。模型没有 Tool/网络凭据，不能直接调用业务或检索服务；只有确定性节点可以访问上游 Client。

### 5.1 模块职责

| 组件 | 责任 | 禁止承担 |
|---|---|---|
| `api` | FastAPI/Pydantic 入口 DTO、认证材料、HTTP 映射 | 图路由、权限推导 |
| `graph.builder` | 固定节点/条件边、compile 与调用 | 动态节点、模型生成边 |
| `AgentState` | 请求级类型化最小状态 | JWT/secret/Prompt/完整上游正文长期驻留 |
| `auth_context`/`result_security` | Auth 交集、输入/输出投影 | 身份/RBAC 所有权 |
| `plan` | 最小上下文调用模型，产生候选计划 | 执行业务调用 |
| `validate`/`route` | 确定性白名单校验和唯一能力分支 | 自动修补未知字段 |
| `query`/`aggregate` | 受控上游调用和结果投影 | 互调、模型计算指标 |
| `document` 子图 | retrieve/evidence/generate/citation 固定链 | 索引实现、原文所有权 |
| `ModelClient` | 单一获准端点的超时、认证和响应解析 | 目标动态切换、业务调用 |
| 上游 Clients | Python 到 Java Auth/业务/检索的窄 HTTP 合同 | 授权放宽、跨域聚合 |
| `AuditRecorder` | 安全摘要、耗时、结果码 | 请求正文、Prompt、密钥 |

建议包结构：

```text
agent_service/
├─ api/
├─ graph/{state.py,builder.py,nodes/}
├─ planning/
├─ capabilities/{query,aggregate,document}/
├─ clients/{auth,business,retrieval,model}/
├─ security/
└─ observability/
```

### 5.2 依赖方向与禁止绕过

- `api` 只调用已编译 Graph，不直接调用节点或上游 Client；
- `graph` 依赖 planning/capabilities/security 端口并决定唯一控制流；
- 能力包依赖自己的 Validator 和上游 Client，不相互调用；
- `clients` 不得反向依赖 `api`、`graph` 或其他 Client；
- 不建立独立 `agent-api`、`agent-adapter-*`、`agent-runtime` 或 `document-provider-adapter` 项目；
- 不建立 Java 主编排或 LangGraph 旁路；共享 DTO 只有出现第二个真实 Python 消费方后才抽取公共包。

## 6. 核心数据流与状态模型

```text
START
  -> auth_context
  -> plan (model)
  -> validate (deterministic)
  -> QUERY | AGGREGATE | DOCUMENT | CLARIFY | REJECT
  -> result_security / safe_response
  -> END
```

API 边界先验证 Bearer JWT，只把`trusted_identity`写入初始 State；原始 token 不进入图。`AgentState`是显式类型化、请求级、最小化状态，只含`request_id/deadline_at/trusted_identity/effective_authorization/plan_candidate/validated_plan/selected_capability/query_result/aggregate_result/search_hits/evidence_package/model_output/secured_result/error`。能力专属字段是互斥 optional 类型，通用节点不得写入；`error`只允许安全错误码，不保存异常正文。节点只返回自己拥有的局部更新。JWT、密钥、Prompt 模板、HTTP Client 和完整原文不进入 state。首阶段 graph compile 不传 checkpointer，不创建 thread/checkpoint/execution 表，不提供跨请求记忆或恢复；进程中断或 deadline 到期即失败，任何迟到响应被丢弃。

图 compile 时使用封闭 input/output schema；output 只暴露`request_id/secured_result/safe_error`。LangSmith 或任何第三方 State/Prompt tracing 默认关闭，只有完成字段级脱敏、数据处理审批和泄漏测试后才可另行启用。

## 7. 能力路由与计划边界

模型输出只允许以下结果：

| 类型 | 含义 | 确定性路由行为 |
|---|---|---|
| `QUERY` | 受控查询 | 交给 Query Validator |
| `AGGREGATE` | 受控聚合 | 交给 Aggregate Validator |
| `DOCUMENT` | 检索回答/总结 | 交给 Document Validator |
| `CLARIFY` | 信息不足 | 返回封闭澄清问题，不调用上游 |
| `REJECT` | 不支持或风险过高 | 返回安全原因码 |

计划必须声明 `schemaVersion/capability/domain/intent` 及能力专属载荷。未知 capability、domain、字段、操作符、函数、排序、语料库或额外字段全部拒绝。`validate`节点不把非法计划“尽量修复”为可执行计划；仅允许正规化大小写、空白和已声明别名。

## 8. 权限与数据流

1. 身份来自已验证 JWT，不接收请求体中的 subject/tenant 作为权威。
2. Auth 返回权限码、能力/域上界和有效期；Agent 策略映射到字段、操作符、函数、语料库。
3. 规划前按最小范围投影可用能力与元数据；不发送令牌、完整权限表达式、隐藏字段或数据样本。
4. 执行前使用同一请求内的当前快照校验；若 Auth 事实已过期则重新解析一次，否则拒绝。
5. 返回前按当前规则再投影。QUERY/AGGREGATE 原始结果不进入模型。
6. DOCUMENT 仅把召回后仍获准的证据片段发送给模型，回答必须通过引用校验。

## 9. 关联 L1 与协作边界

关联 L1“检索与索引基础设施架构”只提供 Search/Index/Rebuild 稳定契约；本 L1 负责语料库选择、证据选择、生成和引用。双方通过 L2 04/05 的 SearchRequest/SearchHit 合同协作，任何一侧不得反向依赖对方内部实现。

## 10. 上游合同策略

| 上游 | Agent 使用方式 | 兼容要求 |
|---|---|---|
| `auth-service` | 内部权限解析，短超时、无正缓存 | 加字段可兼容；缺少必需安全事实时失败关闭 |
| `employee-service` | 查询/计数等只读 API | DTO 显式版本；不得直接依赖其数据库模型 |
| `mq-procedure-service` | 交易查询/聚合只读 API | 写接口不属于首阶段 Agent 能力 |
| `es-query-service` | 受控检索请求和索引任务查询 | Agent 不传原生 ES DSL 或物理索引名 |
| 模型端点 | 规划、DOCUMENT 回答/总结 | OpenAI-compatible 只是线协议，不代表质量/合规通过 |

现存接口只能作为实施期勘察输入。若其字段或错误语义不能支撑 L2，不得在 Agent 内猜测；应先获得对应上游合同变更授权。

## 11. 超时、重试与错误

- 请求使用绝对 `deadline`，默认值和最大值由配置给定；下游超时不得超过剩余预算。
- Auth、模型和只读上游仅在“请求未发送或明确幂等”时最多重试一次；写入和未知发送结果不重试。
- 错误封套至少区分：`INVALID_REQUEST`、`UNAUTHORIZED`、`FORBIDDEN`、`CLARIFICATION_REQUIRED`、`UNSUPPORTED`、`UPSTREAM_UNAVAILABLE`、`TIMEOUT`、`MODEL_OUTPUT_INVALID`、`INTERNAL_ERROR`。
- 外部响应不暴露类名、堆栈、Prompt、上游正文或策略细节；内部审计记录安全原因码和 correlation id。

## 12. 架构决策

| 编号 | 决策 | 依据 |
|---|---|---|
| APP-DEC-01 | 官方 Python LangGraph 是单一部署/编排单元 | 绿地期先冻结图和状态合同；Java 服务保持外部上游 |
| APP-DEC-02 | 受限同步 StateGraph、请求级类型化状态、无 checkpointer | 利用显式分支，暂不承担恢复/记忆/人工审批复杂度 |
| APP-DEC-03 | 模型提议、确定性节点准入 | 隔离非确定性与数据访问权限 |
| APP-DEC-04 | 三个显式能力包 | 边界清晰且不引入通用插件框架 |
| APP-DEC-05 | 业务结果不回送模型 | 防止数值改写、泄漏和不必要成本 |
| APP-DEC-06 | DOCUMENT 由 Agent 编排 | 回答需要结合授权、证据和模型，检索服务只提供原子能力 |
| APP-DEC-07 | 单个 `ModelClient` 端口 | 首阶段没有多供应商动态路由需求 |
| APP-DEC-08 | 合同先在本项目定义 | 只有真实复用出现后再抽取，避免空 API 项目 |
| APP-DEC-09 | LangGraph4j 仅为硬性 Java-only 备选 | 独立社区依赖，必须重新评估成熟度、API 差异和运维风险 |

## 13. 可观测性与风险门禁

必须度量请求数、节点/分支分布、澄清/拒绝率、计划校验失败率、各上游耗时、超时率、DOCUMENT 无证据率和引用校验失败率。日志只记录摘要和数量；图拓扑快照必须纳入回归，防止新增旁路边。

实现前先完成`AUTH -> PLAN -> QUERY/CLARIFY -> RESULT_SECURITY` PoC，验证类型化状态、非法计划不触发上游、deadline/迟到结果以及 Python 到 Spring 上游的认证/错误映射。实现就绪门禁还包括 L2 字段合同、图拓扑测试和上游合同测试。生产门禁：安全负向、真实模型效果、供应商数据处理批准、容量/超时和回滚全部完成；PoC 与文档审查不能代替这些门禁。

## 14. 下位 L2 详细设计交付约束与追踪

| L2 | 覆盖 |
|---|---|
| 01 入口规划与可信执行 | AD-01/02/03/09/10；APP-DEC-01/02/03/09 |
| 02 权限上下文与模型安全 | AD-04/05/11；APP-DEC-05/07 |
| 03 业务查询与聚合 | AD-03/06/09；APP-DEC-04 |
| 04 DOCUMENT 检索问答 | AD-05/07/08/12；APP-DEC-06 |

下位 L2 必须给出严格 Graph State/DTO、固定节点/边、失败语义、实现落点和自动测试，不得引入 Java 编排旁路、第二 Agent 部署单元、动态 Tool 循环、通用插件系统或 checkpointer；公共上游合同变化必须先获得对应范围授权。

官方接口依据：`StateGraph`节点读写共享 state，条件边负责有限路由，图须 compile 后执行；checkpointer 是持久化、跨交互记忆和故障恢复的前提。本设计不配置 checkpointer：<https://reference.langchain.com/python/langgraph/graph/state/StateGraph>、<https://docs.langchain.com/oss/python/langgraph/persistence>。

## 15. 三轮内部审查

三轮结果及修订项记录于[内部审查记录](内部审查记录_v2.0.md)，结论不等于正式批准或实现验证。
