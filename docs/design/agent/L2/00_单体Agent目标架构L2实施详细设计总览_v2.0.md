# 单体 Agent 目标架构 L2 实施详细设计总览 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档状态 | In Review |
| 内部结论 | Ready for Implementation（内部三轮审查通过） |
| 上位文档 | L0 v2.0、两个 L1 v2.0 |
| 目的 | 给出完整 L2 分解、实施顺序、共同约束和验收追踪 |

## 2. 修改历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v2.0 | 2026-07-22 | 以官方 Python LangGraph 受限 StateGraph 和五个专题覆盖首阶段能力，删除旧双编排/迁移/持久状态专题。 |

## 3. 设计目标与范围

目标是给出精简且完整的 LangGraph L2 交付图。范围外包括代码实现、旧项目迁移、Java 主编排、多 Agent、模型自主 Tool 循环、动态节点、checkpointer/持久记忆、人工中断恢复和生产审批。

## 4. 当前实现基线、关联资源与责任边界

当前 Agent/document 项目已删除，新 Python LangGraph `agent-service` 尚不存在；`es-query-*` 仅保留基础设施路径且能力未验证。L0/L1 决定边界，L2 只补实施合同；Auth、Java 业务服务、检索和模型各自拥有上游资源，任何 L2 不得越权修改其公共合同。

## 5. 模块职责、依赖方向与调用边界

01 提供 API、类型化 state 和固定图，02 提供确定性安全节点，03/04 实现能力节点，05 独立提供检索/索引合同。每个专题围绕一个稳定责任内聚，避免 Graph 与上游实现耦合。依赖方向为 `api -> graph -> 02 + 03/04 -> Python clients -> Java 上游`，04 通过稳定 Search DTO 调用 05；禁止反向依赖图、Java 编排旁路或绕过 Validator。

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
- 权限与审计设计统一由 02 提供：API 验证 JWT、auth_context 解析上界、result_security 收口输出；第三方 State tracing 默认关闭。
- 图只允许固定节点/条件边；compile 不配置 checkpointer，不使用 thread 持久状态、动态节点或模型自主 Tool 循环。

## 8. 核心流程与建议实施顺序

1. **01 PoC/骨架**：先实现`AUTH -> PLAN -> QUERY/CLARIFY -> RESULT_SECURITY`，再补 API、deadline、固定图、Graph State、模型计划 Schema 与 Validator。
2. **02 安全**：Auth Client、权限交集、规划输入投影、ModelClient、结果安全。
3. **03 业务能力**：先接一个 QUERY 域，再补 AGGREGATE 与第二个域，形成可验证纵切。
4. **05 检索基础设施**：确认当前 `es-query-*` 基线，补合同、关键词搜索、索引和重建。
5. **04 DOCUMENT**：在 02/05 合同稳定后接入证据问答和总结。
6. **端到端门禁**：三类能力真实上游集成、安全负向、效果、超时和回滚测试。

每一步保持主干可编译；不得先搭建通用框架再等待能力接入。

## 9. 共同状态、数据生命周期与错误分类

首阶段不配置 LangGraph checkpointer，不持久化执行状态。请求内节点用于显式控制流与指标：

```text
START -> AUTH_CONTEXT -> PLAN -> VALIDATE -> QUERY|AGGREGATE|DOCUMENT
                                  ├-------> CLARIFY|REJECT
DOCUMENT -> RETRIEVE -> EVIDENCE_GATE -> GENERATE -> CITATION_GATE
所有成功分支 -> RESULT_SECURITY -> END
```

节点名不是外部 API，也不需要数据库表。并发终止由同一异步请求、deadline 检查和 HTTP Client 取消处理。未配置 checkpointer 时不得宣称恢复、持久记忆、time travel 或人工审批能力。

统一错误码：`INVALID_REQUEST`、`UNAUTHORIZED`、`FORBIDDEN`、`CLARIFICATION_REQUIRED`、`UNSUPPORTED`、`UPSTREAM_UNAVAILABLE`、`TIMEOUT`、`MODEL_OUTPUT_INVALID`、`EVIDENCE_INSUFFICIENT`、`INTERNAL_ERROR`。外部 4xx/5xx 映射在 01 冻结；各能力只能补充安全 `reasonCode`，不能暴露上游正文。

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
| AD-01/02/03/09/10 | 01 | Graph State、拓扑、计划、超时、无 checkpointer 测试 |
| AD-04/05/11 | 02 | 权限和模型安全负向测试 |
| AD-03/06/09 | 03 | 上游合同、映射与结果正确性测试 |
| AD-05/07/08/12 | 04 | 检索前过滤、引用和拒答效果集 |
| AD-07/08/12 | 05 | 索引一致性、安全和 Recall 测试 |
| ADR-01、ADR-02、ADR-03、ADR-05、ADR-06 | 01/02/03/04 | Python LangGraph 单运行时、受限图、确定性安全和 Java-only 备选门禁 |
| ADR-04 | 04/05 | 独立检索边界与关键词优先的效果门禁 |

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| REQ-00-01 / CON-00-01 | DR-00-01 受限 StateGraph 与五专题完整覆盖 | IMPL-00-01 01～05 L2 | TEST-00-01 拓扑/状态/结构检查 | VAL-00-01 三类能力均可追踪且无旁路 |

## 12. 风险、待确认事项与变更控制

以下变化必须回到 L0/L1 评估，不能只改 L2：引入 Java 主编排或第二 Agent Runtime、checkpointer/持久记忆、异步恢复、人工中断、多 Agent、动态节点、模型直接 Tool 调用、Agent 直连业务数据库、检索所有权转移、文档级 ACL、多供应商动态路由。

字段、类名、测试夹具和不改变上位边界的超时默认值可在相应 L2 内修订；公共接口或上游合同变化还需检查所有调用方和兼容性。

## 13. 实施落点清单

IMPL-00-01 是 01～05 文档定义的建议新增代码/合同落点集合；总览不新增第六类运行模块。每个落点必须在对应 L2 的 REQ/DR/TEST/VAL 闭环后实施。

## 14. 内部评审记录

本总览与 01～05 一并完成三轮内部审查，结果见 `../内部审查记录_v2.0.md`。审查不包含代码符合性或生产审批。
