# 单体 Agent 应用与能力架构 L1 v2.0

- 文档层级：L1
- 文档状态：In Review

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档标识 | `AGENT-APP-L1-001` |
| 文档层级 | L1 |
| 文档状态 | In Review |
| 内部结论 | Ready for Implementation Review（内部评审结论；不代表已批准实施） |
| 当前版本 | v2.0 |
| 适用基线 | `AGENT-L0-001` v2.0；目标代码与外部合同仍待 PoC/实施核验 |
| 维护责任角色 | Agent 应用架构负责人（具体人员由项目治理指定） |
| 上位文档 | `单体Agent智能体总体架构_L0_v2.0.md` |
| 关联 L1 | `检索与索引基础设施架构_L1_v2.0.md` |
| 治理的 L2 | 01 入口规划与可信执行、02 权限上下文与模型安全、03 业务查询与聚合、04 DOCUMENT 检索问答 |
| 文档范围 | 单体 `agent-service` 的入口、规划、安全编排和三类能力 |
| 边界外 | Auth、业务服务、检索/索引内部实现、原始文档、模型供应商平台 |

## 2. 修订历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v2.0 | 2026-07-22 | 以单 Python LangGraph 部署单元重建能力架构，禁止 Java/Python 双编排。 |
| v2.0-r1 | 2026-07-22 | 补齐治理身份，并明确 L2 总览由 L0 管理、本文只治理 01～04。 |
| v2.0-r2 | 2026-07-22 | 冻结确定性 CLARIFY、服务认证与上游凭据边界。 |
| v2.0-r3 | 2026-07-22 | 固定 Client 为唯一重试责任方并禁止图/入口重试。 |
| v2.0-r4 | 2026-07-22 | 补齐零容忍门禁和 AD/APP 到 01～04 的完整约束分配。 |
| v2.0-r5 | 2026-07-22 | 完成逐文档五轮治理与严格架构回归。 |
| v2.0-r6 | 2026-07-23 | 由六份 L2 串行复审触发原子同步：将内部就绪语义限定为进入实现评审，不表示已批准实施。 |
| v2.0-r7 | 2026-07-23 | 按最小必要原则移除包结构和完整 State 字段清单，L1 只保留逻辑职责、状态不变量与下位门禁。 |
| v2.0-r8 | 2026-07-23 | 原子同步本轮评审：明确 Auth facade 在图前单次解析，区分规划授权上界与能力有效授权，并校正阶段 A 实施范围。 |

## 3. 架构目标与非目标

目标是以受限 `StateGraph` 和最少模块承载 QUERY、AGGREGATE、DOCUMENT 目标能力集；当前阶段 A 只形成 `EMPLOYEE QUERY` 最小纵切，其他能力按上游合同与质量门禁逐步进入。非目标包括 Java 主编排、第二 Agent Runtime、多 Agent、checkpointer/持久记忆、人工中断恢复、通用插件框架和模型直接 Tool 调用。

## 4. 上位约束映射

| L0 约束 | 本 L1 落实 |
|---|---|
| AD-01、AD-02 | 一个 Python LangGraph 部署单元、同步请求内类型化状态、无 checkpointer |
| AD-03、AD-04、AD-05、AD-13、AD-14 | 固定图、模型提议、确定性节点校验、权限只收紧、封闭输出、服务身份/用户事实分离与出站白名单 |
| AD-06、AD-07、AD-08 | 上游数据所有权、DOCUMENT/检索责任分离、检索前过滤 |
| AD-09、AD-10、AD-11、AD-12 | 单一 deadline/retry 所有者、严格合同、状态不夸大、按证据演进 |
| ADR-01、ADR-02、ADR-03、ADR-05、ADR-06 | Python LangGraph 单运行时、受限图、确定性准入、单项目和 Java-only 备选门禁 |

## 5. 核心职责与职责边界

Agent 是一个 Python 模块化单体，不是 Java/Python 服务集合。官方 LangGraph `StateGraph`是唯一编排和状态流转权威；所有请求在同一进程中完成“鉴权—规划—校验—单能力执行—结果安全”。模型没有 Tool/网络凭据，不能直接调用业务或检索服务；只有确定性节点可以访问上游 Client。

### 5.1 模块职责

| 组件 | 责任 | 禁止承担 |
|---|---|---|
| 入口边界 | 严格请求/响应合同、认证材料接收和 HTTP 映射 | 图路由、权限推导 |
| 图编排 | 固定节点/条件边、请求内状态流转和唯一能力分支 | 动态节点、模型生成边、跨请求恢复 |
| 请求状态 | 请求级类型化最小状态；DOCUMENT 可短暂持有经授权、限量证据片段 | JWT/secret/Prompt/完整文档、未投影响应、持久驻留 |
| 安全边界 | Auth 上界交集、输入/输出投影和返回前重验 | 身份/RBAC 所有权 |
| 规划与准入 | 最小上下文规划、确定性白名单校验 | 执行业务调用、自动修补未知字段 |
| QUERY/AGGREGATE | 受控上游调用和结果投影 | 能力互调、模型计算业务指标 |
| DOCUMENT | retrieve/evidence/generate/citation 固定链 | 索引实现、原文所有权 |
| 外部访问 | 通过获准的模型/Auth/业务/检索窄合同访问上游 | 动态目标切换、授权放宽、跨域聚合 |
| 可观测性 | 安全摘要、耗时、结果码和健康状态 | 请求正文、Prompt、密钥 |

具体包、文件、类、方法和 DTO 由 L2-01～04 冻结；本 L1 不建立第二套实现结构权威。

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
  -> authorize (deterministic)
  -> QUERY | AGGREGATE | DOCUMENT
  -> CLARIFY | REJECT
  -> result_security | safe_response -> result_security
  -> END
```

API 边界先以 Agent 服务身份调用 Auth facade 一次，由 Auth 验证用户 Bearer token 并返回绑定同一主体的身份与权限上界；原始 token 不进入图。`auth_context`只将该上界与 Agent 策略求交，形成供规划/计划校验使用的只收紧上界；`authorize`在计划确定后再结合请求目的和能力专属资源事实形成有效授权，缺失或冲突时不得调用业务、检索或模型上游。请求状态只保存当前请求的控制、规划授权上界、有效授权、计划、能力结果和安全终态；能力专属状态互斥，通用节点不得越权写入，错误只保存安全原因码。JWT、密钥、Prompt 模板、HTTP Client、完整文档和未投影上游响应不得进入 State；仅 DOCUMENT 可在预算内短暂持有经授权证据。具体字段、类型和 output schema 由 L2-01/02 定义。

首阶段顶层图及任何独立编译的嵌套图均使用`checkpointer=False`，不创建跨请求执行状态，不提供记忆或恢复；进程中断、deadline 到期或取消即失败，迟到结果丢弃。第三方 State/Prompt tracing 默认关闭，只有完成字段级脱敏、数据处理审批和泄漏测试后才可另行启用。

## 7. 能力路由与计划边界

模型输出只允许以下结果：

| 类型 | 含义 | 确定性路由行为 |
|---|---|---|
| `QUERY` | 受控查询 | 交给 Query Validator |
| `AGGREGATE` | 受控聚合 | 交给 Aggregate Validator |
| `DOCUMENT` | 检索回答/总结 | 交给 Document Validator |
| `CLARIFY` | 信息不足 | 模型只提议原因码、缺失槽位和选项键；`safe_response`按服务端模板形成受限澄清问题，不复制模型自由文本、不调用上游，再经`result_security`输出 |
| `REJECT` | 不支持或风险过高 | `safe_response`返回安全原因码，再经`result_security`输出 |

计划必须声明 `schemaVersion/capability/domain/intent` 及能力专属载荷。未知 capability、domain、字段、操作符、函数、排序、语料库或额外字段全部拒绝。`validate`节点不把非法计划“尽量修复”为可执行计划；仅允许正规化大小写、空白和已声明别名。

## 8. 权限与数据流

1. 身份来自 Auth facade 对用户 JWT 的验签结果，不接收请求体或网关注入的 subject/tenant 作为权威。
2. Auth 返回权限码、能力/域上界和有效期；Agent 策略先形成规划授权上界，能力专属资源事实只在计划确定后参与有效授权。
3. 规划前按最小范围投影可用能力与元数据；不发送令牌、完整权限表达式、隐藏字段或数据样本。
4. 执行前使用同一请求内的当前快照、已校验目的和资源事实形成有效授权；若 Auth 事实已过期则拒绝，不在图内携带原始 token 重新解析。
5. 返回前按当前规则再投影。QUERY/AGGREGATE 原始结果不进入模型。
6. DOCUMENT 仅把召回后仍获准的证据片段发送给模型，回答必须通过引用校验。

## 9. 关联 L1 与协作边界

关联 L1“检索与索引基础设施架构”当前只提供阶段 A Search 稳定契约；Index/Rebuild 须在来源合同具备后修订对应 L2，不能作为当前依赖。本 L1 负责语料库选择、证据选择、生成和引用。双方当前只通过 L2 04/05 的 SearchRequest/SearchHit 合同协作，任何一侧不得反向依赖对方内部实现。

## 10. 上游合同策略

| 上游 | Agent 使用方式 | 兼容要求 |
|---|---|---|
| `auth-service` | 内部权限解析，短超时、无正缓存 | 加字段可兼容；缺少必需安全事实时失败关闭 |
| `employee-service` | 查询/计数等只读 API | DTO 显式版本；不得直接依赖其数据库模型 |
| `mq-procedure-service` | 后续交易查询/聚合只读 API | 阶段 B 合同未冻结；写接口不属于 Agent 目标能力 |
| `es-query-service` | 受控检索请求和索引任务查询 | Agent 不传原生 ES DSL 或物理索引名 |
| 模型端点 | 规划、DOCUMENT 回答/总结 | OpenAI-compatible 只是线协议，不代表质量/合规通过 |

现存接口只能作为实施期勘察输入。若其字段或错误语义不能支撑 L2，不得在 Agent 内猜测；应先获得对应上游合同变更授权。

每个上游 Client 必须分别拥有目标白名单、协议/证书校验、服务凭据装配、绝对 deadline 和错误翻译；禁止跟随到未获准主机的重定向。用户 subject/tenant/权限事实与服务凭据分离传递，不能用`X-USER-ID`等可伪造头代替 Auth 合同，也不能把用户 Bearer token 当作 Agent 服务身份。模型节点不接触 Client 或任何凭据。

## 11. 超时、重试与错误

- 请求使用绝对 `deadline`，默认值和最大值由配置给定；下游超时不得超过剩余预算。
- HTTP 入口、整图和 Graph 节点不自动重试，也不配置全局 LangGraph retry policy；每个依赖的重试唯一归对应 Client 所有。
- Auth、模型和只读上游 Client 仅在“请求未发送或明确允许重放”且剩余 deadline 足够时最多重试一次；写入、未知发送结果、校验失败和整个请求不重试。
- 客户端断开或 deadline 到期后取消图和未完成远调；迟到结果不得更新 State、输出响应或触发新的调用，取消/超时以安全原因码进入统一终态。
- 错误封套至少区分：`INVALID_REQUEST`、`UNAUTHORIZED`、`FORBIDDEN`、`UNSUPPORTED`、`UPSTREAM_UNAVAILABLE`、`TIMEOUT`、`MODEL_OUTPUT_INVALID`、`INTERNAL_ERROR`。需要补充信息时统一返回 HTTP 200 的受限`CLARIFICATION`结果，不同时定义为错误码。
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

首阶段不可妥协门禁：非法/越权计划触发上游调用数为 0；单请求执行多个能力分支数为 0；未经过`result_security`的 Graph 输出数为 0；日志/trace 中 JWT、密钥、Prompt、上游正文和完整权限表达式泄漏数为 0。延迟、容量、澄清率和 DOCUMENT 效果阈值由 L2 夹具/配置在对应能力上线前冻结，未冻结不得进入生产门禁。

实现前先完成`AUTH -> PLAN -> VALIDATE -> AUTHORIZE -> QUERY/CLARIFY -> RESULT_SECURITY` PoC，验证类型化状态、非法计划或资源事实缺失时不触发上游、deadline/迟到结果以及 Python 到 Spring 上游的认证/错误映射。实现就绪门禁还包括 L2 字段合同、图拓扑测试和上游合同测试。生产门禁：安全负向、真实模型效果、供应商数据处理批准、容量/超时和回滚全部完成；PoC 与文档审查不能代替这些门禁。

## 14. 下位 L2 详细设计交付约束与追踪

`L2/00_单体Agent目标架构L2实施详细设计总览_v2.0.md`由 L0 用于协调两个 L1 的共同实施顺序，不由本 L1 单独重定义；本 L1 的直接下位交付是 01～04，L2-05 由检索与索引基础设施 L1 治理。

| L2 | 覆盖 |
|---|---|
| 01 入口规划与可信执行 | AD-01/02/03/09/10/13/14；APP-DEC-01/02/03/08/09 |
| 02 权限上下文与模型安全 | AD-04/05/11/13/14；APP-DEC-05/07 |
| 03 业务查询与聚合 | AD-03/06/09/10/14；APP-DEC-04/08 |
| 04 DOCUMENT 检索问答 | AD-04/05/07/08/09/10/12/13/14；APP-DEC-06/08 |

下位 L2 必须给出严格 Graph State/DTO、固定节点/边、失败语义、实现落点和自动测试，不得引入 Java 编排旁路、第二 Agent 部署单元、动态 Tool 循环、通用插件系统或 checkpointer；公共上游合同变化必须先获得对应范围授权。

官方接口依据：`StateGraph`节点读写共享 state，条件边负责有限路由，图须 compile 后执行；checkpointer 是持久化、跨交互记忆和故障恢复的前提。本设计以`checkpointer=False`禁止当前图使用或继承 checkpointer：<https://reference.langchain.com/python/langgraph/graph/state/StateGraph/compile>、<https://docs.langchain.com/oss/python/langgraph/persistence>。

## 15. 五轮逐文档评审

本文件五轮结果及修订项记录于[内部审查记录](内部审查记录_v2.0.md)。结论仅表示该 L1 足以治理 01～04 的详细设计和分阶段实现计划，不等于正式批准、代码符合性验证或生产放行。

### 15.1 内部自检记录

| 轮次 | 日期 | S0 | S1 | S2 | 本轮处理 | 结论 |
|---:|---|---:|---:|---:|---|---|
| 1 | 2026-07-22 | 0 | 1 | 2 | 补治理身份并校正 L2 总览/01～04 治理关系 | 已修复 |
| 2 | 2026-07-22 | 0 | 2 | 0 | 冻结确定性澄清、服务认证和凭据边界 | 已修复 |
| 3 | 2026-07-22 | 0 | 1 | 0 | 固定 Client 唯一重试责任 | 已修复 |
| 4 | 2026-07-22 | 0 | 2 | 1 | 补零容忍门禁与下位约束/追踪 | 已修复 |
| 5 | 2026-07-22 | 0 | 0 | 0 | 回归图边界、能力互斥和越界声明 | 通过 |
