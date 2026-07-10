# Agent 文档证据上下文优化方案

## 1. 目标

在不改变现有 document 能力对外响应契约的前提下，提升税务政策类问答的召回、生成和引用体验：

1. LLM 获得更完整、噪声更低的证据上下文。
2. 前端引用展示尽量是完整句子或完整段落。
3. 召回入口保持足够宽，生成入口保持足够窄。
4. 不通过特殊前缀兼容隐藏 citationId 结构问题。

## 2. 两阶段方案

### 第一阶段：参数拆分与证据文本链路

将原先单一的 `agent.document.evidence-selection.max-evidence-count` 拆成三个语义独立参数：

| 参数 | 默认建议 | 作用 |
| --- | ---: | --- |
| `max-generation-evidence-count` | 5 | 最终进入 LLM 生成上下文的证据条数 |
| `max-display-citation-count` | 12 | 前端可展示、结果安全投影后保留的引用条数 |
| `max-summary-document-count` | 12 | SUMMARIZE 自选 documentIds 的数量上限 |

旧参数 `max-evidence-count` 保留兼容绑定：如果旧配置仍存在，会同时设置上述三个预算。

运行链路调整：

1. `DocumentCapabilityHandler` 生成阶段只使用 `max-generation-evidence-count`。
2. `DocumentResultSecurityProjector` 结果投影只使用 `max-display-citation-count`。
3. `DocumentPlanValidator` 摘要 scope 校验只使用 `max-summary-document-count`。
4. `citationText` 映射到现有响应字段 `snippet`，避免改动 `agent.html`。
5. `generationText` 优先进入 `DocumentEvidenceContextPacker`，没有该字段时兼容旧的 `content + before/after` 拼接。

### 第二阶段：索引与向量文本结构调整

索引构建脚本新增三个派生字段：

| 字段 | 用途 | 是否替代 chunk 原文 |
| --- | --- | --- |
| `citationText` | 前端引用展示，尽量完整句子 | 否 |
| `generationText` | LLM 生成上下文，尽量完整句子/段落 | 否 |
| `embeddingText` | 实际送入 embedding 模型的富化文本 | 否 |

默认索引构建策略保留源 `chunkId`、`chunkIndex`、`charStart`、`charEnd`，只新增派生文本字段。`build_chinatax_dataopt_index.py` 只有在显式传入 `--reshape-chunks` 时才会重切 chunk；该模式仅用于数据实验，不建议直接作为生产别名切换候选。

检索 DSL 同步将 `citationText`、`generationText` 加入 BM25/PHRASE 字段集合；老索引缺失这些字段时 ES 查询兼容。

## 3. 关于 chunk 准确度

如果“按句子/段落边界”直接改变 chunk 切分边界，确实可能影响 chunk 准确度，主要风险是：

1. 原文位置 `charStart/charEnd` 失真。
2. 一个 chunk 中混入上下文扩展内容，导致 citationId 指向范围不清。
3. 向量召回命中的语义单元和展示引用不一致。

当前默认方案不采用这种做法。当前实现只新增派生字段：

1. `content` 仍是主检索 chunk。
2. `citationText/generationText` 从同一 chunk 内容裁剪到句末，或在旧索引兼容路径中由上下文窗口拼接。
3. `embeddingText` 记录富化后的向量输入，避免 embedding 输入不可追溯；运行查询时会从 `_source` 排除，不透传到 agent-service。

因此，准确度风险主要转移为“派生文本是否过短或过长”，不会直接破坏 chunk 主边界。

## 4. 推荐运行参数

当前推荐配置：

```yaml
agent:
  document:
    retrieval:
      default-size: 5
      answer-candidate-size: 30
      summarize-candidate-size: 30
      max-size: 30
    evidence-selection:
      max-generation-evidence-count: 5
      max-display-citation-count: 12
      max-summary-document-count: 12
      strategy: SCORE_GROUP_TOP
      score-groups: 3
      min-top-group-size: 1
    context-window:
      enabled: true
      before-chunks: 5
      after-chunks: 5
    generation:
      max-context-chars: 12000
      max-evidence-chars: 1600
```

后续重建索引并确认 `generationText` 覆盖率稳定后，可以把 `context-window.before/after-chunks` 从 5 下调到 1 到 2，减少重复上下文。

## 5. 验证口径

第一阶段验证：

1. 配置绑定：新参数可绑定，旧参数兼容。
2. 生成上下文：LLM 证据条数按 `max-generation-evidence-count` 截断。
3. 展示引用：前端引用按 `max-display-citation-count` 截断。
4. 引用展示文本：`citationText` 优先进入响应 `snippet`。

第二阶段验证：

1. 索引 dry-run：确认新字段可生成。
2. 文本质量抽样：比较旧 `snippet` 和新 `citationText` 的完整句比例。
3. gold query：新索引别名切换前跑 TopK 命中率和 ACL 泄漏验证。
4. 线上回归问题：至少覆盖“增值税有哪些税率？”、“小规模纳税人征收率是多少？”、“企业所得税有哪些税率？”。
