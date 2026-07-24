# 架构文档索引

本仓库新的 Agent 设计以已确认需求为当前需求基线。原 `docs/design/agent/` 下的旧 Agent 设计已退出当前工作区，不得作为新设计或实现依据。

## 当前有效文档

- [单体 Agent 查询能力建设需求说明](SINGLE_AGENT_QUERY_REQUIREMENTS.md)（v1.2，已确认）
- [单体 Agent 查询能力 L0 总体架构设计](design/SINGLE_AGENT_ARCHITECTURE.md)（v0.4，已评审、有条件通过、`SA-GATE-001` 已关闭、未实施、未生效）
- [单体 Agent 核心与运行架构 L1](design/SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md)（v0.2，已评审、已通过、未实施、未生效；`CR-GATE-001` 已关闭）

## 架构文档状态

- L0 总体架构：v0.3 五轮独立评审及 v0.4 针对性复核均无剩余 S0/S1，项目维护者已完成确认，`SA-GATE-001` 已关闭；v0.4 是当前三份 L1 的编写基线。
- L1 领域或模块架构：核心与运行 L1 v0.2 已完成五轮评审并通过，明确 Spring 接入治理、LangGraph 唯一编排、确定性核心、差异化能力处理器形态、能力契约/注册、模型输入/结果出域边界及 DeepSeek 模型端口；Knowledge L1 和业务查询 L1 待创建。
- L2 详细设计：尚未建立；核心与运行 L1 的 `CR-GATE-001` 已关闭，可开始其治理的三份 L2，但对应 L2 评审、`CR-GATE-002/003`、`SA-GATE-002/006` 和实现/集成证据仍未完成。
- 已删除的旧 L0、L1、L2 文档及历史 Agent 实现不得反向提升为当前架构权威。

## 权威边界

- 当前权威顺序为：已确认需求 → 新 L0 → 新 L1 → 新 L2 → 实现与验证证据。
- 当前 L0 已确认一个逻辑 Agent、Spring 接入治理进程、Python LangGraph 唯一编排运行时、DeepSeek `deepseek-v4-pro` 及本地 BGE 检索模型边界；具体接口、运行参数和实现仍由 L1/L2 治理。
- 核心与运行 L1 v0.2 是其权威范围内的 L2 编写基线，不改变 L0 状态，也不代表内部协议已定版、模型 PoC 已通过、实现已完成或真实数据允许进入外部模型。
- `auth-service`、`employee-service`、`mq-procedure-service`、`es-query-*`、网关、配置中心和通用组件可作为现状核实对象，但其既有实现不自动构成新 Agent 的目标架构。
- 文档状态、代码实现状态、验证状态和发布状态相互独立，不得以其中一项替代其他项。
