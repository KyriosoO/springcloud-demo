# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix（批量模式，第 10/15 份，严格串行） |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 评审代码范围 | `agent-service` Document Profile/Policy 资产、选择/冻结投影、Validator/Handler/Provider/Result 资源消费；`agent-adapter-api` typed Document contract；相关配置与测试 |
| 是否修改代码 | 是 |
| 验证结果 | 定向测试及四目标模块 reactor 全部通过；未执行真实 Provider、远程配置 reload 和生产环境授权 recheck |
| 最终结论 | 有条件通过；5 项 Profile/有效预算一致性问题已修复，主文档中的验收命令和实施状态表述仍需另行修订 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 读取结果 | 备注 |
|---|---|---:|---|---|
| `02_文档Profile与有效资源预算_L2实施详细设计_v3.0.md` | detailed_design | 0 | 已完整读取 | 当前主文档 |
| `00_P2_V3文档能力统一设计总览_L2实施详细设计_v3.0.md`、`01_文档语料与索引生命周期_L2实施详细设计_v3.0.md`、`03_文档ACL与受保护过滤_L2实施详细设计_v3.0.md`、`04_统一文档检索编排_L2实施详细设计_v3.0.md`、`06_DocumentProvider治理_L2实施详细设计_v3.0.md`、`07_文档能力验证发布回滚审计与撤权_L2实施详细设计_v3.0.md` | related_design | 1 | 已读取相关边界 | Profile/Corpus/ACL/Provider 所有权与同源 limit 消费 |
| `P1_V2/02_AgentProfile与Policy治理_L2实施详细设计_v2.0.md`～`P1_V2/06_原子迁移扩展验证与清理门禁_L2实施详细设计_v2.0.md` | related_design | 1 | 已读取相关边界 | exact parent、typed contribution、freeze/recheck 与原子候选 |
| `../Agent契约与规划架构设计_v1.0.md`、`../Agent能力执行内核架构设计_v1.0.md`、`../Agent元数据与上下文安全架构设计_v1.0.md` | architecture | 2 | 已读取相关约束 | 强类型契约、执行上下文、权限 currentness |
| `../Agent目标架构总览_v1.0.md` | architecture | 3 | 已读取相关约束 | L0 总体边界 |

## 3. 文档约束追踪

| 约束编号 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|
| DOC-C-001 | Profile 的 domain/materialType 必须在候选构建期形成 canonical CorpusKey 闭包 | `DocumentRetrievalProfile`、`DocumentProfileAssets` | 修复后符合 |
| DOC-C-002 | OPTIONAL+0 禁用后的通道不再消费候选预算；REQUIRED+0 失败封闭 | `DocumentPlanningProfileProjector` | 修复后符合 |
| DOC-C-003 | Runtime 具体检索模式和 context 必须来自唯一冻结投影 | `DocumentPlanValidator`、`DocumentExecutionProfileProjection` | 修复后符合 |
| DOC-C-004 | ANSWER generated 与 SUMMARIZE summary 使用各自 typed dimension，Provider 不得交叉叠加 | Validator、Handler、generation candidate、provider adapter | 修复后符合 |
| DOC-C-005 | Validator/Handler/Provider/Result 使用同一 `DOCUMENT_RESOURCE_LIMIT_V1`，不得回读 `AgentProperties` | Document 执行链与静态扫描 | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|
| CR-001 | high | projection_budget | `DocumentPlanningProfileProjector.java` | DENSE_VECTOR 因 OPTIONAL+0 被移除后，仍无条件校验 `vectorCandidateCount`；BM25 未启用时亦同 | 未实际启用的通道可导致合法 Planning 被错误拒绝 | 仅对最终启用通道校验对应 per-channel candidate 上限；新增回归测试 |
| CR-002 | high | strategy_drift | `DocumentPlanValidator.java` | ANSWER/SUMMARIZE context 固定为 `1/1`，忽略冻结 `DocumentContextPolicy` | Profile digest 与实际 Adapter 命令不一致，配置变更不生效 | 从 final profile projection 投影 before/after chunks；保留 typed maxContextChars |
| CR-003 | medium | execution_mode | `DocumentPlanValidator.java` | retrieval mode 仅由 embedding policy 推断，未按最终启用 BM25/DENSE_VECTOR 集合确定 | 关键字单通道可被记录为 HYBRID，影响 Provider 调用判断和观测语义 | 按最终通道确定 KEYWORD/VECTOR/HYBRID；增加 Validator 回归测试 |
| CR-004 | high | dimension_mixing | `DocumentPlanValidator.java`、`DocumentCapabilityHandler.java`、`DocumentGeneratedTextCandidateFactory.java`、`DocumentProviderAdapterClient.java` | SUMMARIZE 的文本同时受 `maxGeneratedChars` 和 `maxSummaryChars` 约束 | 当 generated dimension 为 0/更小时，合法摘要被拒绝；违背同一 Contract 中 operation-specific dimension 语义 | SUMMARIZE 使用 summary chars，ANSWER 使用 generated chars；summary bullets/citation 仍独立受限 |
| CR-005 | medium | candidate_validation | `DocumentRetrievalProfile.java` | Profile 允许大写 domain/materialType，但 `DocumentCorpusKey` 仅接受 lowercase canonical identifier | 错误配置直到 selection 才失败，无法在 immutable candidate 构建时整体拒绝 | Profile 构造期使用与 DCK-1 一致的 canonical identifier 规则；新增负向测试 |

## 5. 文档问题清单

| 编号 | 级别 | 文档位置 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|
| DOC-001 | medium | 第 20.2 节 | 验证命令不可复现 | 仓库根目录不存在 `mvnw.cmd`；实际 wrapper 位于 `serviceCenter/mvnw.cmd`，且从 `serviceCenter` reactor 使用 artifactId selector 才可稳定执行 | 原命令在仓库根目录直接失败 | 经文档修改授权后统一改为 `serviceCenter/mvnw.cmd -f serviceCenter/pom.xml -pl :... -am test` 或注明工作目录 |
| DOC-002 | low | 第 20.2、23、24 节 | 状态表述冲突 | 文档标记 Implemented、声称本地实现和验证完成，但验收段仍写“本次文档评审不声称代码测试已通过” | 审计者无法判断验证声明对应设计评审还是实施验收 | 经授权拆分“设计评审历史”与“当前实现验证状态”，引用可复现报告 |

## 6. 修改摘要

| 轮次 | 修改范围 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | Profile/投影/Validator | canonical Corpus 标识、按最终通道校验预算、由冻结投影确定 mode/context | CR-001、CR-002、CR-003、CR-005 | 已修复 |
| 1 | generation/Provider 资源消费 | 分离 ANSWER generated 与 SUMMARIZE summary 字符预算 | CR-004 | 已修复 |
| 2 | 测试、reactor、静态门禁 | 增加 3 个负向/投影测试，执行定向与四目标模块回归、旧路径和 properties 读取扫描 | CR-001～CR-005 | 未发现新增可处理代码问题 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 2 | Maven 定向：`DocumentPlanningArtifactAssemblerTest,DocumentProfileCanonicalizerTest,DocumentPlanValidatorTest,DocumentGeneratedTextCandidateFactoryTest` | 通过 | 15 tests，0 failure/error |
| 2 | `serviceCenter/mvnw.cmd` reactor：`:agent-adapter-api,:agent-service,:agent-adapter-document,:document-provider-adapter -am test` | 通过 | 11 模块 SUCCESS；`agent-service` 466、`agent-api` 47、`agent-adapter-api` 9、`agent-adapter-document` 4 tests，其他模块亦通过 |
| 2 | 主文档第 19.3/20.2 节四组精确 `rg` 扫描 | 通过 | 旧 ExecutionConfig/stage limit/profile alias-provider/runtime rewrite 与三个消费者 `AgentProperties` 均零命中 |
| 2 | `git diff --check -- agent-service` | 通过 | 无空白错误；仅报告仓库既有 CRLF/LF 提示 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 触发场景 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | 未做真实 Config Server candidate reload 与并发权限 recheck | Profile/Policy/Permission 同时更新、Permission 收紧或 evidence 过期 | 在 07 发布门禁环境执行 reload 原子性、同值/收紧/扩大 recheck 场景 |
| RISK-002 | medium | 未以真实 Document Provider 验证 ANSWER/SUMMARIZE 各维度边界 | Provider 返回恰好/超过 generated、summary chars/bullets/citation 边界 | 增加 adapter contract 集成与边界故障注入；本轮 Java 内部回归已通过 |
| RISK-003 | low | Mockito 动态 agent 存在未来 JDK 兼容警告 | 后续 JDK 默认禁止动态 agent | 独立测试基础设施任务中配置显式 Mockito agent |

## 9. 结论

- 有条件通过。
- 5 项 Profile canonical、冻结策略、通道预算与 operation-specific output dimension 问题已在两轮评审—修复中闭合；定向测试、11 模块 reactor 和精确静态门禁通过。
- 主详细设计、关联文档及 L0/L1 架构正文未修改；DOC-001、DOC-002 仅记录，等待单独文档修改授权。
- 未执行生产配置发布、真实 Provider/ES 调用、数据库操作、提交、推送或远端操作。
