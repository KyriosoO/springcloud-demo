# Agent文档型生成式问答与总结能力_代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 依据文档数量 | 2 |
| 评审代码范围 | `es-query-api/**`、`es-query-service/**`、`agent-api/**`、`agent-adapter-api/**`、`agent-adapter-document/**`、`agent-service/**`、`agent-runtime/**` |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 通过；本轮发现的可自动修复问题已修复 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `docs/design/P2/Agent文档型生成式问答与总结能力_L2实施详细设计_v1.0.md` | detailed_design | 1 | 是 | 已读取 | 作为主要代码符合性依据 |
| `docs/design/P2/Agent文档型生成式问答与总结能力_设计文档品审报告.md` | other | 2 | 否 | 已读取 | 作为设计品审结论和剩余风险依据 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | L2 详细设计第 8、9、10 章 | `es-query-service` 只做检索和 RRF 融合，不生成 queryVector，不调用 LLM | `es-query-service/src/main/java/com/dylan/esquery/service/EsDocumentService.java`、`HybridSearchMerger.java` | 符合 |
| DOC-C-002 | L2 详细设计第 10、12 章 | `agent-service` 负责 queryVector、证据上下文打包、LLM 生成、引用校验和安全投影 | `DocumentCapabilityHandler.java`、`embedding/**`、`generation/**`、`DocumentResultSecurityProjector.java` | 符合 |
| DOC-C-003 | L2 详细设计第 11、15 章 | LLM 输入只允许使用已授权、已裁剪证据；最终输出必须经过 ResultSecurity | `DocumentEvidencePreSecurityFilter.java`、`DocumentEvidenceContextPacker.java`、`DocumentResultSecurityProjector.java` | 符合首版边界；ACL/脱敏权威源仍属生产前风险 |
| DOC-C-004 | L2 详细设计第 15 章 | `answerText/summaryText/summaryBullets` 需要截断，不能绕过输出预算 | `DocumentResultSecurityProjector.java` | 本轮已修复 |
| DOC-C-005 | L2 详细设计第 15 章 | 每条 `summaryBullets` 至少包含一个合法 citation，失败时降级或拒答 | `DocumentResultSecurityProjector.java` | 本轮已修复 |
| DOC-C-006 | L2 详细设计第 20 章 | 覆盖 hybrid、generation、citation、安全和 drift 验证 | Java Maven 测试、runtime pytest、contract drift | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 建议处理 |
|---|---|---|---|---|---|---|---|
| CR-007 | medium | design_consistency / security | `agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java` | L2 第 15 章 | 生成式 `answerText/summaryText/summaryBullets` 复用 snippet 的 `maxSnippetChars` 截断逻辑，而不是生成输出预算 | 长回答或摘要会被片段预算误截断，生成能力退化；同时 summary bullets 未显式走生成输出预算 | 已修复：新增 `truncateGeneratedText`，生成式文本使用 `agent.document.generation.max-output-chars` |
| CR-008 | medium | citation_verification / implementation_completeness | `agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java` | L2 第 15 章 | citation 校验只要求候选文本集合整体存在合法 citation，未要求每条 summary bullet 各自包含合法 citation | 无引用 bullet 可能进入最终摘要，削弱证据绑定总结能力 | 已修复：逐条校验每个非空候选文本和 bullet，缺少 citation 或引用不存在时降级 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| 无 | - | - | - | 未发现阻断性文档问题 | - | - |

## 6. 修改摘要

| 轮次 | 修改文件 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | `agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java` | 生成式回答、摘要正文、摘要 bullet 改用 generation output budget 截断 | CR-007 | 已修复 |
| 1 | `agent-service/src/test/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjectorTest.java` | 增加“生成文本不被 snippet 预算误截断”的回归测试 | CR-007 | 已修复 |
| 2 | `agent-service/src/main/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjector.java` | citation 校验改为逐条候选文本校验；每条 summary bullet 必须包含合法 citation | CR-008 | 已修复 |
| 2 | `agent-service/src/test/java/com/dylan/agent/metadata/result/DocumentResultSecurityProjectorTest.java` | 增加“summary bullet 无 citation 时降级”的回归测试 | CR-008 | 已修复 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `cd serviceCenter; .\mvnw -pl ../agent-service -am -Dtest=DocumentResultSecurityProjectorTest "-Dsurefire.failIfNoSpecifiedTests=false" test` | 失败后修正并通过 | 首次失败为测试期望字符数错误；修正后 5 tests 通过 |
| 2 | `cd serviceCenter; .\mvnw -pl ../agent-service -am -Dtest=DocumentResultSecurityProjectorTest "-Dsurefire.failIfNoSpecifiedTests=false" test` | 通过 | 6 tests 通过 |
| 2 | `cd serviceCenter; .\mvnw -pl ../es-query-api,../es-query-service -am test` | 通过 | 11 tests 通过 |
| 2 | `cd serviceCenter; .\mvnw -pl ../agent-api,../agent-adapter-api,../agent-adapter-document,../agent-service -am test` | 通过 | 378 tests 通过 |
| 2 | `cd agent-runtime; .\.venv\Scripts\python.exe -m pytest tests\test_contracts.py tests\test_planning.py tests\test_prompt_contract.py` | 通过 | 63 passed，1 个既有 StarletteDeprecationWarning |
| 2 | `cd agent-runtime; .\.venv\Scripts\python.exe scripts\check_contract_drift.py` | 通过 | active Python codegen reproducible |
| 2 | `git diff --check` | 通过 | 仅提示部分文件 CRLF 将被 Git 转换为 LF |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | provider 未真实联调 | embedding provider、LLM provider endpoint/model/schema/timeout 未确认 | 生产启用前完成 provider 契约 mock 或真实 provider 集成测试 |
| RISK-002 | medium | 下游 ACL 与脱敏权威源未闭环 | 文档级 ACL、ES mapping 和下游返回证据脱敏仍是设计中列出的生产前确认项 | 灰度前完成 ACL、mapping、脱敏联调验收 |
| RISK-003 | low | citation 逐句语义覆盖仍依赖 LLM 结构化绑定质量 | 当前安全投影校验 citation id 存在性和每条 bullet 有引用，不能证明自然语言事实完全等价于证据 | 后续可引入更强 claim-level verifier 或 rerank/grounding 检查 |

## 9. 结论

最终结论：通过。

说明：
- 本轮未发现 blocker/high 问题。
- 本轮发现的 2 个 medium 问题均已在授权范围内修复并通过验证。
- 未修改设计文档、架构文档、README 或依赖版本。
