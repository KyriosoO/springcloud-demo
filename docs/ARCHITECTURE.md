# 架构文档索引

本仓库的 Agent 目标架构以 `docs/design/agent/` 为唯一现行入口。历史 `agent-*`、`document-*`、P1/P2 设计、迁移报告和评审证据已退出目标基线，不得作为实现依据。

## 现行入口

- [Agent 设计文档导航](design/agent/README.md)
- [单体 Agent 总体架构 L0](design/agent/单体Agent智能体总体架构_L0_v2.0.md)
- [Agent 应用与能力架构 L1](design/agent/单体Agent应用与能力架构_L1_v2.0.md)
- [检索与索引基础设施架构 L1](design/agent/检索与索引基础设施架构_L1_v2.0.md)

## 权威边界

- 新 Agent 是后续待实现的单一 Python LangGraph 部署单元；当前仓库没有可复用的 Agent 目标实现。
- `auth-service`、业务服务、`es-query-*`、网关和通用组件是上游或基础设施，不属于 Agent 内部模块。
- 文档状态只表示设计成熟度，不表示代码已实现、质量已验证或允许生产发布。
