# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 评审代码范围 | `agent-service` Domain Metadata 候选构建/校验/架构门禁，`agent-runtime` 通用规划提示词，生产 YAML，以及直接相关 Adapter 与测试 |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 通过；5 项元数据完整性、歧义消除、通用内核隔离和发布门禁问题已修复 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `04_Adapter与DomainMetadata治理_L2实施详细设计_v2.0.md` | detailed_design | 0 | 是 | 已完整读取 | 当前主文档 |
| `01_Agent契约生成与治理_L2实施详细设计_v2.0.md` | related_design | 1 | 否 | 已读取相关边界 | canonical contract 与 digest 稳定性 |
| `03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md` | related_design | 1 | 否 | 已读取相关边界 | Metadata currentness 与授权投影 |
| `05_有效资源预算与CapabilityLocalPort收敛_L2实施详细设计_v2.0.md` | related_design | 1 | 否 | 已读取相关边界 | domain facts 与 resource limits 分离 |
| `../Agent元数据与上下文安全架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | L1 元数据单一事实源 |
| `../Agent能力执行内核架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | L1 typed port 与通用内核边界 |
| `../Agent目标架构总览_v1.0.md` | architecture | 3 | 否 | 已读取相关约束 | L0 总体边界 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | 第 7、10.2、11 节 | Domain Metadata 候选必须完整校验字段 shape、operator/type、function/type 和 role coverage，失败不得发布 | `DomainMetadataPropertiesValidator` | 修复后符合 |
| DOC-C-002 | 第 7.1、10.2 节 | domain/field alias 必须无歧义，canonical 事实唯一 | validator、生产 `agent-service.yml` | 修复后符合 |
| DOC-C-003 | 第 5、8、13 节 | 通用 Route/Plan/Core 不得内嵌生产 domain/field 事实，事实只能来自当前 Domain Catalog 投影 | 三类 planning prompt、架构测试 | 修复后符合 |
| DOC-C-004 | 第 5.2、13、19 节 | Adapter 不得自报 fields/operators/functions；Domain Metadata 不得重新承载资源预算 | `DomainMetadataArchitectureTest` | 修复后符合 |
| DOC-C-005 | 第 10.1、15、19 节 | 生产 YAML 必须通过与启动候选相同的 builder/gate；catalog 与 registration 变更需同步版本 | `DomainMetadataPropertiesValidatorTest`、生产 YAML | 修复后符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|---|
| CR-001 | high | metadata_validation | `DomainMetadataPropertiesValidator.java` | 第 10.2、11 节 | 候选 gate 未校验 aggregate function/type，也未校验 maxLength/precision/scale 与字段类型关系 | 非法 SUM/AVG/COUNT 或字段 shape 可进入 current catalog，失败延迟到执行期 | 增加 function/type 和字段 shape fail-close 校验及负向测试 |
| CR-002 | high | canonical_ambiguity | validator、`agent-service.yml` | 第 7.1、10.2 节 | 只去重单个 alias 列表，未阻止同一 alias 指向多个 domain/field；生产 `literature` 的“片段”同时指向 section/snippet | 自然语言映射结果不唯一，可能将过滤条件落到错误字段 | 增加域级/字段级 alias ownership 校验；将 section alias 改为“小节” |
| CR-003 | medium | implicit_coupling | 三类 planning prompt | 第 5、8、13 节 | QUERY/AGGREGATE/DOCUMENT 示例内嵌 `amount`、`transType`、`sourceType` 等生产字段，DOCUMENT 规则还固定假定 title 字段 | 通用 Planner 隐式耦合当前生产 domain，新域/裁权后仍可能生成不存在或未授权字段 | 改为抽象占位字段并声明必须以请求 `domainSchema` 为准；title 规则改为 schema 驱动 |
| CR-004 | medium | release_gate_gap | `DomainMetadataPropertiesValidatorTest.java` | 第 15、19 节 | 测试仅验证手工构造的 synthetic fixture，没有把生产 YAML 绑定后送入实际候选 builder | 生产配置的 alias 冲突、registration coverage 或类型错误可绕过测试，到启动/热加载才暴露 | 增加生产 YAML 与运行时相同 Binder + builder 的发布门禁，断言 6 个 domain/8 个 registration |
| CR-005 | medium | architecture_gate_gap | `DomainMetadataArchitectureTest.java`、`test_planning.py` | 第 13、19 节 | 缺少 Adapter 自报、预算回流、domain 分支、prompt 生产事实的自动化门禁 | 后续扩展容易重新形成双事实源或在通用内核加入领域分支 | 增加 Java/Python 架构测试；保留通用 synthetic fixture，避免通过缩窄测试数据转移原测试意图 |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | medium | 当前主文档第 10.3、11.2、12 节 | 版本可比较性未定义 | 文档要求 catalog/registration version 单调递增并拒绝回退，但未定义版本格式、比较算法、持久化基线及跨实例并发发布规则 | 当前代码只能拒绝“同版本不同 digest”，无法可靠判断任意字符串版本是否回退；擅自增加比较器会创造新公共约定 | 获得文档修改授权后定义可比较版本（建议单调序列或时间戳语法）、持久化 current 基线和 CAS 发布语义，再实现 rollback gate |

## 6. 修改摘要

| 轮次 | 修改范围 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | Metadata candidate gate | 增加字段 shape、function/type、domain/field alias 唯一性校验 | CR-001、CR-002 | 已修复 |
| 1 | 生产配置 | 消除 `literature` alias 冲突；catalog、全局 registration 和 8 个 registration version 同步升级至 `2026-07-14` | CR-002 | 已修复 |
| 1 | 通用 Planner | 移除生产字段硬编码，所有示例和 title 选择改为 `domainSchema` 驱动 | CR-003 | 已修复 |
| 1 | 发布与架构测试 | 增加生产 YAML 候选 gate、Adapter/预算/domain branch/prompt leakage 门禁 | CR-004、CR-005 | 已修复 |
| 2 | 回归修正 | 首轮跨模块测试发现通用 fixture 被过度缩窄；恢复 synthetic 通用字段，仅让新增生产 YAML 测试承担真实配置覆盖职责 | CR-005 | 已闭合，451 个 `agent-service` 测试通过 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `... -Dtest=DomainMetadataPropertiesValidatorTest,DomainMetadataArchitectureTest,EmployeeAdapterMetadataCoverageTest,TransactionAdapterMetadataCoverageTest ... test` | 通过 | 15 passed |
| 1 | `python -m pytest tests/test_planning.py -q` | 通过 | 22 passed；1 个既有 Starlette 弃用告警 |
| 1 | `... -pl :agent-adapter-api,:agent-service,:agent-adapter-employee,:agent-adapter-transaction,:transaction-api,:mq-procedure-service -am test` | 未通过 | 新缩窄的 synthetic fixture 造成 17 个通用 FilterNormalizer/FieldConstraint 测试失败；据此恢复 fixture，未削弱断言 |
| 2 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-service -am test` | 通过 | Reactor BUILD SUCCESS；`agent-service` 451 passed |
| 2 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-adapter-api,:agent-service,:agent-adapter-employee,:agent-adapter-transaction,:transaction-api,:mq-procedure-service -am test` | 通过 | 15 模块 Reactor BUILD SUCCESS；`mq-procedure-service` 与 `agent-service` 均通过 |
| 2 | `python -m pytest tests/test_contracts.py tests/test_planning.py -q` | 通过 | 54 passed；1 个既有 Starlette 弃用告警 |
| 2 | `python agent-runtime/scripts/check_contract_drift.py` | 通过 | active Python codegen 可重复且 provenance 有效 |
| 2 | `rg -n 'amount|transType|sourceType|contactAddress' agent-runtime/app/prompts` | 通过 | 无匹配 |
| 2 | `git diff --check` | 通过 | 无空白错误；仅既有 CRLF/LF 转换告警 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 触发场景 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | 多实例发布时仍不能证明版本严格单调 | 使用不可比较字符串版本、旧实例晚到发布或回滚配置时 | 先修订 DOC-001，再增加持久化 current version + digest CAS 与并发/回退测试；当前不建议自行发明版本排序规则 |
| RISK-002 | low | Maven 测试存在 Mockito 动态 agent 的未来 JDK 兼容告警 | 升级到默认禁止动态 agent 的未来 JDK | 依赖治理时统一配置 Mockito agent；本次不新增生产依赖 |
| RISK-003 | low | Python 测试存在 Starlette `httpx` 适配层弃用告警 | 后续升级 Starlette/httpx 测试依赖 | 在测试依赖升级任务中处理；与本次 metadata 治理无直接关系 |

## 9. 结论

最终结论：
- 通过。

说明：
- 5 项代码问题均在授权范围内以最小修改闭合，第二轮完整回归通过。
- 未修改主详细设计、L0/L1 或关联文档；版本单调语义问题仅记录，等待文档修改授权。
- 未引入生产依赖，未修改公共 HTTP 契约，未执行提交或推送。
