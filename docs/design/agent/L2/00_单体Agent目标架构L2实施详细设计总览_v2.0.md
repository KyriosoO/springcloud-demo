# 单体 Agent 目标架构 L2 实施详细设计总览 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档标识 | `AGENT-L2-00` |
| 文档层级 | L2 实施总览（跨专题协调，不替代 01～05） |
| 文档状态 | In Review |
| 内部结论 | Ready for Implementation Review（本总览内部评审结论；不代表已批准实施） |
| 当前版本 | v2.0 |
| 适用基线 | `AGENT-L0-001`、`AGENT-APP-L1-001`、`AGENT-RETRIEVAL-L1-001` v2.0 |
| 维护责任角色 | L2 实施协调负责人（具体人员由项目治理指定） |
| 上位文档 | L0 v2.0、两个 L1 v2.0；冲突时按 L0→对应 L1→专题 L2 的权威顺序处理 |
| 目的 | 给出完整 L2 分解、实施顺序、共同约束和验收追踪 |

## 2. 修改历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v2.0 | 2026-07-22 | 以官方 Python LangGraph 受限 StateGraph 和五个专题覆盖首阶段能力，删除旧双编排/迁移/持久状态专题。 |
| v2.0-r1 | 2026-07-22 | 补齐治理身份，明确专题权威，并将首个 PoC 改为 01/02/03 最小纵切协同交付。 |
| v2.0-r2 | 2026-07-22 | 补齐仓库级 Java/Python 实施目录、入口签名和专题权威映射；明确不新增 Java Agent 编排。 |
| v2.0-r3 | 2026-07-23 | 完成本次串行五轮评审：收紧实施准入措辞、补 Gateway 无重试约束，并闭合总览实现落点与追踪。 |
| v2.0-r4 | 2026-07-23 | 删除重复的 Java/Python 方法签名和路径合同，将总览收敛为专题所有者、阶段、依赖与门禁索引。 |
| v2.0-r5 | 2026-07-23 | 原子同步本轮评审：统一 Auth facade 单次解析与“规划上界→能力有效授权”两阶段安全流。 |
| v2.0-r6 | 2026-07-23 | 同步 Employee 适配边界：03 阶段 A 新增独立无状态 `agent-employee-adapter`，复用 Employee ES Search；不改变 LangGraph 单编排权威。 |

## 3. 设计目标与范围

目标是给出精简且完整的 LangGraph L2 交付图。本文只协调共同约束、依赖和门禁；01～05 分别拥有各自字段、流程、落点和测试语义，本文不得以总览表格覆盖专题设计。范围外包括代码实现、旧项目迁移、Java 主编排、多 Agent、模型自主 Tool 循环、动态节点、checkpointer/持久记忆、人工中断恢复和生产审批。

## 4. 当前实现基线、关联资源与责任边界

当前 P1 已形成 Python LangGraph `agent-service` 与 Auth/Gateway/Employee 临时实现；本次将 Employee 域内 Agent 专属 QUERY 迁移到独立`agent-employee-adapter`。`employee-service`既有 ES Search/Vector 能力已由单测验证，真实 ES 互操作和历史索引完整性仍未验证。L0/L1 决定边界，专题 L2 冻结合同；Auth、业务服务、检索和模型继续拥有各自资源。

## 5. 模块职责、依赖方向与调用边界

01 提供 API、类型化 state 和固定图，02 提供确定性安全节点，03/04 实现能力节点，05 独立提供检索/索引合同。依赖方向为`api -> graph -> 02 + 03/04 -> Python clients -> Auth/Adapter/检索/模型端点`；Employee 固定为`agent-service -> agent-employee-adapter -> employee-service -> es-query-service`。Adapter 只做协议与安全转换，禁止反向依赖图、Java 编排旁路、持有 Graph State 或绕过 Validator。

内聚与耦合判断：Graph、权限交集、Employee 协议适配、业务数据和检索原子能力分别由单一所有者承担；新增 Adapter 保护真实跨语言/安全边界，不复制业务查询或编排规则，因此没有形成循环依赖或第二状态权威。

## 6. L2 责任分解

| 编号 | 文档 | 实施结果 |
|---|---|---|
| 01 | 入口规划与可信执行 | 一个可鉴权、可超时、可审计的同步 StateGraph、类型化 state 与确定性计划准入 |
| 02 | 权限上下文与模型安全 | Auth 上界交集、最小模型投影、模型/结果安全 |
| 03 | 业务查询与聚合能力 | QUERY/AGGREGATE 的字段合同、上游映射和负向测试 |
| 04 | DOCUMENT 检索问答能力 | 获准检索、证据选择、回答/摘要、引用校验和拒答 |
| 05 | 检索与索引基础设施 | 搜索、幂等索引、重建、Alias 切换和效果验证 |

该分解覆盖首阶段完整能力，不再为跨运行时契约、迁移隔离、持久生命周期、Provider 独立服务、发布证据平台分别建 L2。

## 7. 共同实现基线与最小必要性

- 后续新建一个 Python `agent-service` 项目；官方 `langgraph` 是唯一编排运行时，FastAPI/Pydantic/httpx 是建议实现依赖，本轮不安装生产依赖。
- HTTP JSON 和 Graph 输入/输出使用 Pydantic/显式类型、封闭枚举和未知字段拒绝；内部 `AgentState` 显式类型化。
- 所有请求带 `requestId` 和绝对 deadline；不得在超时后后台继续。
- 所有上游通过窄 Client/Port 调用，不直连数据库，不透传原生 DSL。
- 日志、指标和审计禁止正文、Prompt、响应原文、JWT、密钥和完整权限表达式。
- 权限与审计设计统一由 02 提供：API 以服务身份调用 Auth facade 一次，由 Auth 验证用户 JWT 并解析上界；`auth_context`形成规划授权上界，计划通过后由`authorize`结合资源事实形成能力有效授权，`result_security`收口输出；第三方 State tracing 默认关闭。
- 图只允许固定节点/条件边；顶层图及任何独立编译的嵌套图使用`checkpointer=False`，不使用或继承 thread 持久状态，不使用动态节点或模型自主 Tool 循环。

## 8. 核心流程与建议实施顺序

1. **PoC 合同冻结**：先由 01 冻结图/State/错误，02 冻结服务认证与结果安全，03 冻结一个 QUERY 域的最小上游映射；三者只冻结支撑 PoC 的最小合同。
2. **01+02+03 最小纵切 PoC**：协同实现`AUTH -> PLAN -> VALIDATE -> AUTHORIZE -> QUERY/CLARIFY -> SAFE_RESPONSE/RESULT_SECURITY`，验证非法计划或资源事实缺失时零上游调用、deadline/迟到结果、Python→Spring 认证和错误映射。
3. **01/02 完整骨架**：补齐 API、固定图、Graph State、计划 Schema/Validator、安全投影、ModelClient 与脱敏审计。
4. **03 阶段 A**：只实现`EMPLOYEE QUERY`严格合同；通过纵切后再评审阶段 B 的`TRANSACTION AGGREGATE`。`EMPLOYEE AGGREGATE`和`TRANSACTION QUERY`没有独立需求前不冻结实现合同。
5. **05 阶段 A**：先实现 Search 只读纵切；阶段 B 在首个权威源合同批准后实现该源所需的最小版本化 Index；阶段 C 只在快照/游标/删除或静默证明合同成立后设计并实现 Rebuild/Cancel/Rollback。
6. **04 DOCUMENT**：在 02 与 05 阶段 A 合同稳定后接入证据问答和总结。
7. **端到端门禁**：只对当前阶段已授权的能力执行真实上游集成、安全负向、效果、超时和回滚测试；后续阶段不得借用前一阶段结论。

每一步保持主干可编译；不得先搭建通用框架再等待能力接入。

| 专题 | 发布前置 | 回滚边界 | 禁止的“降级” |
|---|---|---|---|
| 01/02 | PoC、认证合同、固定图和安全负向通过 | 关闭 Agent 入口路由或恢复上一部署/配置 | 启用 Java 编排旁路、跳过 Auth/Validator/result_security |
| 03 | 单域 QUERY 合同通过后按能力/域启用 | 关闭对应能力/域，保留安全拒绝 | 模型自行拼接查询、直连数据库或扩大字段 |
| 05 | 新索引验证与观察门禁通过 | Alias 回切 previous，保留失败任务证据 | Agent 直连 ES、切到未验证索引或跳过检索前过滤 |
| 04 | 02/05 与供应商/效果门禁通过 | 关闭 DOCUMENT，QUERY/AGGREGATE 不受影响 | 无证据生成、无引用回答或宽检索 |

所有开关默认关闭且只能收紧能力，不得改变 Auth 上界、服务身份、错误封套或数据所有权。回滚不修改上游业务事实；回滚演练和配置恢复由对应专题的测试/验证项证明。

## 9. 共同状态、数据生命周期与错误分类

首阶段以`checkpointer=False`显式禁用 LangGraph checkpointer，不持久化执行状态。请求内节点用于显式控制流与指标：

```text
API -> AUTH FACADE（单次用户验签与上界解析）
START -> AUTH_CONTEXT -> PLAN -> VALIDATE -> AUTHORIZE -> QUERY|AGGREGATE|DOCUMENT
                                  ├--------------------> CLARIFY|REJECT
DOCUMENT -> RETRIEVE -> EVIDENCE_GATE -> GENERATE -> CITATION_GATE
所有成功分支 -> RESULT_SECURITY -> END
CLARIFY|REJECT|安全失败 -> SAFE_RESPONSE -> RESULT_SECURITY -> END
```

节点名不是外部 API，也不需要数据库表。`SAFE_RESPONSE`只能写白名单原因码、模板标识和受限参数，所有 Graph 输出统一经过`RESULT_SECURITY`。并发终止由同一异步请求、deadline 检查和 HTTP Client 取消处理。禁用 checkpointer 时不得宣称恢复、持久记忆、time travel 或人工审批能力。

Agent Graph/API 统一错误码：`INVALID_REQUEST`、`UNAUTHORIZED`、`FORBIDDEN`、`UNSUPPORTED`、`UPSTREAM_UNAVAILABLE`、`TIMEOUT`、`MODEL_OUTPUT_INVALID`、`EVIDENCE_INSUFFICIENT`、`INTERNAL_ERROR`。CLARIFY 是 HTTP 200 的受限`CLARIFICATION`结果，不使用第二套错误语义。外部 4xx/5xx 映射由 01 冻结，03/04 只能补充安全`reasonCode`，不能暴露上游正文。L2-05 当前只冻结独立 Search 基础设施合同；Index/Rebuild 的版本冲突、批量结果和任务状态须在阶段 B/C 修订后定义。只有 04 的 Retrieval Client 负责把 Search 失败映射为 Agent 错误，禁止总览强行抹平基础设施语义。

## 10. 测试与验证设计

| 层级 | 必须验证 |
|---|---|
| 单元 | DTO 严格解析、计划白名单、权限交集、结果投影、引用校验、超时预算 |
| 合同 | Auth、员工、交易、ES、模型请求/响应和错误映射 |
| 集成 | 三类能力成功/拒绝/超时/上游失败；真实 Spring 安全链 |
| 架构 | 包依赖、无数据库直连、无模型 Tool、无旧模块依赖 |
| 效果 | 固定问题集的计划准确率、QUERY/AGGREGATE 结果正确率、DOCUMENT Recall/引用/拒答 |
| 运行 | 指标、脱敏审计、容量、配置失败关闭、回滚 |

## 11. 端到端追踪矩阵

| 上位约束 | L2 | 验收证据 |
|---|---|---|
| AD-01/AD-02/AD-03/AD-09/AD-10/AD-13/AD-14 | 01 | Graph State、拓扑、计划、超时、封闭输出、服务 Client 边界和无 checkpointer 测试 |
| AD-04/AD-05/AD-11/AD-13/AD-14 | 02 | 权限、服务身份、出站白名单和模型安全负向测试 |
| AD-03/AD-06/AD-09/AD-10/AD-14 | 03 | 上游合同、服务 Client、映射与结果正确性测试 |
| AD-04/AD-05/AD-07/AD-08/AD-09/AD-10/AD-12/AD-13/AD-14 | 04 | 能力资源授权、检索前过滤、引用、拒答、deadline 和泄漏效果集 |
| AD-05/AD-06/AD-07/AD-08/AD-09/AD-10/AD-11/AD-12/AD-13/AD-14 | 05 | 索引一致性、严格合同、安全、日志和 Recall 测试 |
| ADR-01/ADR-02/ADR-03/ADR-05/ADR-06 | 01/02/03/04 | Python LangGraph 单运行时、受限图、确定性安全和 Java-only 备选门禁 |
| ADR-04 | 04/05 | 独立检索边界与关键词优先的效果门禁 |

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-00-01 / CON-00-01 | DR-00-01 受限 StateGraph 与五专题完整覆盖、责任不重叠 | IMPL-00-01 01～05 L2 | TEST-00-01 文档清单、上下位 ID 和职责覆盖检查 | VAL-00-01 三类能力均可追踪且无旁路 |
| REQ-00-02 / CON-00-02 | DR-00-02 首个 PoC 由 01/02/03 最小合同与纵切共同交付 | IMPL-00-02 01/02/03 PoC 落点 | TEST-00-02 PoC 前置、非法计划零上游、认证/错误/deadline 集成 | VAL-00-02 PoC 证据齐全后才扩展能力 |
| REQ-00-03 / CON-00-03 | DR-00-03 专题开关只收紧，回滚不引入旁路或宽降级 | IMPL-00-03 01～05 发布/配置/回滚落点 | TEST-00-03 回滚矩阵与禁止路径检查 | VAL-00-03 回滚后上位安全/所有权不变量不变 |

## 12. 风险、待确认事项与变更控制

以下变化必须回到 L0/L1 评估，不能只改 L2：引入 Java 主编排或第二 Agent Runtime、checkpointer/持久记忆、异步恢复、人工中断、多 Agent、动态节点、模型直接 Tool 调用、Agent 直连业务数据库、检索所有权转移、文档级 ACL、多供应商动态路由。

字段、类名、测试夹具和不改变上位边界的超时默认值可在相应 L2 内修订；公共接口或上游合同变化还需检查所有调用方和兼容性。

## 13. 交付协调索引

本文只提供协调句柄，不定义路径、类、方法、字段或完整 DTO；全部实现合同以对应专题 L2 为唯一权威。

| 协调句柄 | 所有者 | 当前阶段结果 | 前置门禁 | 不在本文定义 |
|---|---|---|---|---|
| COORD-00-01 | L2-01 | Gateway 入口与 Python 固定图骨架 | 路由无重试、Graph 拓扑和错误合同评审 | Java/Python 签名与文件布局 |
| COORD-00-02 | L2-02 | Auth 单次解析、规划上界、能力有效授权、安全投影、模型和审计边界 | Auth/服务 keyset、资源事实、委托调用凭据和审计策略评审 | Auth DTO、claims、key provider 与函数签名 |
| COORD-00-03 | L2-03 阶段 A | `EMPLOYEE QUERY`最小纵切 | 严格只读合同、单租户事实和安全负向 | 其他域/能力合同 |
| COORD-00-04 | L2-03 阶段 B | `TRANSACTION AGGREGATE`候选交付 | 阶段 A 通过且 Transaction 专用合同重新评审 | `EMPLOYEE AGGREGATE`、`TRANSACTION QUERY` |
| COORD-00-05 | L2-05 | 阶段 A Search；后续按源合同逐阶段增加 Index/Rebuild | Search 合同；首源合同；快照/游标/删除证明 | 未来阶段方法、状态机和完整模型 |
| COORD-00-06 | L2-04 | DOCUMENT 检索问答 | L2-02 与 L2-05 Search、供应商和质量门禁 | 检索基础设施实现 |

- `IMPL-00-01`：01～05 的阶段化交付集合；每个具体类型和签名只在专题 L2 定义。
- `IMPL-00-02`：首个 PoC 仅实现 01/02 与 03 阶段 A 的最小链路`AUTH -> PLAN -> VALIDATE -> AUTHORIZE -> QUERY|CLARIFY -> RESULT_SECURITY`。
- `IMPL-00-03`：发布、配置和回滚仍由对应专题拥有；总览不新增运行模块、公共 DTO 或安全合同。

Java 不新增 `AgentGraph`、Planner、LangGraph4j 或 Java 状态机。实施中如发现必须由 Java 承担 Agent 编排，或后续阶段需要改变上位所有权，应停止并回到 L0/L1 重新决策。

## 14. 五轮逐文档评审

本总览历史五轮评审结果见 `../内部审查记录_v2.0.md`。结论仅表示跨专题分解、依赖、PoC 与回滚门禁已具备进入实现评审的条件；只有实现评审和相应前置门禁通过后才可按阶段实施，不替代专题 L2、代码符合性评审或生产审批。后续变更按风险执行最多三轮自检和一次跨层回归，不再固定每文档五轮。

### 14.1 内部自检记录

| 轮次 | 日期 | S0 | S1 | S2 | 本轮处理 | 结论 |
|---:|---|---:|---:|---:|---|---|
| 1 | 2026-07-22 | 0 | 1 | 2 | 修正 PoC 跨专题前置并补治理身份 | 已修复 |
| 2 | 2026-07-22 | 0 | 1 | 1 | 限定 Agent/检索错误所有权并修正依赖语义 | 已修复 |
| 3 | 2026-07-22 | 0 | 1 | 0 | 增加专题发布与回滚矩阵 | 已修复 |
| 4 | 2026-07-22 | 0 | 1 | 0 | 补齐跨专题需求、设计、测试和验证闭环 | 已修复 |
| 5 | 2026-07-22 | 0 | 0 | 1 | 同步五轮治理口径并执行严格校验 | 通过 |

### 14.2 本次实施落点增补自检

| 轮次 | 检查重点 | 发现与处置 | 结论 |
|---:|---|---|---|
| A | 仓库基线与语言边界 | 核实 Python Agent 尚不存在；Java 仅落网关/Auth/业务/检索，不新增 Java 编排 | 通过 |
| B | 专题权威与追踪 | 将总览改为仓库级索引，完整签名仍由 01～05 分别拥有 | 通过 |
| C | 路径、状态与严格校验 | 完整路径、四类状态和 IMPL 追踪一致；严格校验 0 warning | 通过 |

### 14.3 2026-07-23 串行五轮评审记录

| 轮次 | 评审重点 | 冻结发现 | 原子修订与复核 | 本轮结论 |
|---:|---|---|---|---|
| 1 | 权威、状态与准入语义 | `L2-00-R1-01`（S1）：`In Review`与`Ready for Implementation`并列，可能被误读为已批准实施 | 改为`Ready for Implementation Review`，并同步 L0、两个 L1 和内部审查汇总；状态均保持`In Review` | 已修复 |
| 2 | 入口合同、超时与重试所有权 | `L2-00-R2-01`（S1）：总览未阻止新 Agent 路由复用`GatewayRouter`现有三次重试 | 在当前 `COORD-00-01` 对应的 L2-01 中明确`/api/agent/**`必须优先于既有`/api/**`且不得复用 Gateway retry，并绑定测试落点 | 已修复 |
| 3 | 状态、错误、安全与回滚 | 无 S0/S1/S2；`checkpointer=False`、统一安全终态、迟到结果丢弃和能力开关回滚边界一致 | 全文复核，无需修改 | 通过 |
| 4 | 实现落点、测试与追踪 | `L2-00-R4-01`（S1）：新增 Java/Python IMPL 项未逐项映射 DR/TEST/VAL，且压缩式 AD 编号不利于机器追踪 | 为所有 Java/Python 实现落点增加总览追踪，展开 AD/ADR 标识；追踪脚本四类缺口均为 0 | 已修复 |
| 5 | 治理、引用与实现评审就绪度 | 无 S0/S1/S2；状态、修订历史、上位约束、专题权威和未执行门禁一致 | 严格结构校验 0 error/0 warning；结论为可进入实现评审，不代表实施或生产批准 | 通过 |

本次停止原因：达到用户指定的 5 轮上限，且第 5 轮无遗留 S0/S1/S2。当前文档状态保持`In Review`；实现就绪判断为`ready`，其含义仅为可进入实现评审。
