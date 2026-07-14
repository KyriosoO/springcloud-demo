# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix |
| 最大循环次数 | 5 |
| 实际执行轮次 | 2 |
| 依据文档数量 | 8 |
| 评审代码范围 | `agent-service` Metadata/Profile/Policy/Permission、两阶段授权、Context、Result Security、Query Context、SQL，以及 `common-security` secret material 边界和直接相关测试 |
| 是否修改代码 | 是 |
| 验证结果 | 通过 |
| 最终结论 | 通过；6 项授权、安全投影、Context 一致性和密钥生命周期问题已修复 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 是否必需 | 读取结果 | 备注 |
|---|---|---:|---|---|---|
| `03_元数据授权Context与ResultSecurity_L2实施详细设计_v2.0.md` | detailed_design | 0 | 是 | 已完整读取 | 当前主文档 |
| `01_Agent契约生成与治理_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取相关边界 | ContractRef、Runtime operation metadata |
| `02_可信执行内核与Invocation生命周期_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取相关边界 | Core、finalization、Context participant |
| `05_有效资源预算与CapabilityLocalPort收敛_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取相关边界 | typed resource limits |
| `06_原子迁移扩展验证与清理门禁_L2实施详细设计_v2.0.md` | detailed_design | 1 | 否 | 已读取相关边界 | SQL、迁移与清理门禁 |
| `../Agent元数据与上下文安全架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | 主要 L1 依据 |
| `../Agent能力执行内核架构设计_v1.0.md` | architecture | 2 | 否 | 已读取相关约束 | Execution/Result Security 边界 |
| `../Agent目标架构总览_v1.0.md` | architecture | 3 | 否 | 已读取相关约束 | L0 |

## 3. 文档约束追踪

| 约束编号 | 来源文档 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|---|
| DOC-C-001 | 第 10.2～10.3 节 | Route/Plan 前的授权 evidence 必须保持 current；canonical digest 使用版本化、长度前缀和稳定排序 | `AuthorizationPlanningPortImpl`、`PlanningAuthorizationEvidence` | 修复后符合 |
| DOC-C-002 | 第 10.6、12.2 节 | Context absent/expired baseline 与已有记录必须以 CAS 区分；`readable=0` 不可重新开放 | `ContextBoundary`、`ContextRecordMapper`、`MyBatisContextRepository` | 修复后符合 |
| DOC-C-003 | 第 12.1 节 | Context DDL 必须包含审计时间、复合索引、CHECK 和稳定清理边界 | `ContextRecordRow`、`agent-p0.sql`、mapper/repository | 修复后符合 |
| DOC-C-004 | 第 10.8 节 | Document 结果必须进行字段裁剪、Mask、引用/currentness/limits 校验，且不得返回原始候选 | `DocumentResultSecurityProjector` | 修复后符合 |
| DOC-C-005 | 第 5.1、10.10 节 | JWT 与 Agent payload key material 用途隔离，临时明文材料用后清除 | `SecretPropertiesValidator`、secret key providers | 修复后符合 |
| DOC-C-006 | 第 10.7 节 | Query Context 只能按当前权限继承，合并后重新校验 | `QueryMergeEngine`、Query validators、Context runtime view | 符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 依据文档 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|---|
| CR-001 | high | authorization_currentness | `AuthorizationPlanningPortImpl.java` | 第 10.3 节 | `assertCurrent` 只校验 metadata/domain，未重新读取并比对 current Permission evidence | Planning capture 后撤权仍可能继续 Route/Plan，甚至发起外部调用 | 增加权限权威源重读和 evidence id/version 精确比对 |
| CR-002 | high | context_concurrency | `ContextBoundary.java`、`ContextRecordMapper.java` | 第 10.6、12.2 节 | 更新 CAS 未限制 `readable=1`；未消费 Context 时可能以后读到的当前版本作为 baseline，覆盖并发写或复活退役记录 | 造成丢失更新、Conversation 退役记录重新可读 | CAS 增加 `readable=1`；拒绝 live-unconsumed 和 retired baseline，仅允许 expired readable baseline |
| CR-003 | medium | schema_resource_control | `agent-p0.sql`、`ContextRecordRow.java`、`MyBatisContextRepository.java` | 第 12、16 节 | DDL 缺 `created_at`、复合索引和 CHECK；清理批次无硬上限且删除顺序不稳定 | 审计字段缺失；错误配置可能放大锁持有和不可重复清理 | 补齐字段/约束/索引；稳定排序；batch 限制为 1～1000 |
| CR-004 | high | data_leakage | `DocumentResultSecurityProjector.java` | 第 10.8 节 | 只过滤 caller filters，未裁剪 hit/citation metadata 与 sorts，并原地修改后返回 raw candidate | 未授权 title/source/snippet/URI 可能外泄；后续链路仍持有被修改候选 | 改为新建安全结果，统一裁剪/Mask hit、citation 和 sorts；原始候选保持不变 |
| CR-005 | medium | evidence_integrity | `PlanningAuthorizationEvidence.java` | 第 10.3 节 | digest 使用分隔符拼接，且未绑定 planning scope、external-processing evidence、deadline 等关键事实 | 字段包含分隔符时 canonical 不唯一；scope 篡改不能被摘要检出 | 改为 `PAE-1`、UTF-8 length-prefixed、集合稳定排序，并绑定完整 planning 安全范围 |
| CR-006 | medium | secret_lifecycle | `SecretPropertiesValidator.java`、`ConfigSecretMaterialProvider.java`、两类 key provider | 第 5.1、10.10 节 | 未拒绝 JWT/payload 共享 locator/value；decode 和 key 构造临时字节未清除 | 配置误用可打破用途隔离；敏感材料在堆中保留时间过长 | 增加跨用途校验；临时数组 `finally` 清零并销毁一次性 `SecretMaterial` |

## 5. 文档问题清单

| 编号 | 级别 | 文档 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | medium | 当前主文档第 12.1 节 | 数据字典不一致 | 文档定义 `contract_schema/contract_version`，实际唯一 ContractRef 需保存 `contract_namespace/contract_name/contract_version` | 按文档建表会丢失 ContractRef 的 namespace/name 分解语义 | 获得文档修改授权后，以当前三字段 ContractRef 映射修正文档 |
| DOC-002 | medium | 当前主文档第 10.5、19.3、20 节 | 实体/测试覆盖描述偏差 | 文档要求 `ContextRecordEntity` 固定含 createdAt/updatedAt，但当前仅 persistence row/DDL 持有；`ContextRepositoryIT`、`ContextFinalizationIT` 只是 Noop/类存在性断言，且默认 Surefire 不执行 `*IT` | 容易误判真实 MySQL CAS、回滚与审计字段映射已有集成覆盖 | 获得文档修改授权后明确时间字段的分层归属，并把真实数据库 IT 纳入 Failsafe/Testcontainers 门禁 |

## 6. 修改摘要

| 轮次 | 修改范围 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | Planning authorization | Permission currentness 复检；`PAE-1` canonical digest | CR-001、CR-005 | 已修复 |
| 1 | Context repository/SQL | 防复活 CAS、live/retired baseline 拒绝、DDL/row/cleanup 约束 | CR-002、CR-003 | 已修复 |
| 1 | Document Result Security | 非破坏性结果复制、字段裁剪/Mask、sorts 过滤 | CR-004 | 已修复 |
| 1 | common-security/agent payload keys | 用途隔离校验与临时密钥材料清零 | CR-006 | 已修复 |
| 2 | 上述全部范围 | 再评审、专项回归、完整 reactor 回归和契约漂移检查 | CR-001～CR-006 | 未发现新增可处理问题 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1 | `... -Dtest=AuthorizationPlanningPortTest,ContextBoundaryTest,MyBatisContextRepositoryTest,InvocationSchemaTest ... test` | 通过 | 22 passed |
| 1 | `... -Dtest=SecretPropertiesValidatorTest,SecretMaterialJwtKeyProviderTest,PayloadKeyProviderTest,AgentMetadataSecurityConfigurationTest ... test` | 通过 | 13 passed |
| 1 | `... -Dtest=AuthorizationPlanningPortTest,DocumentResultSecurityProjectorTest ... test` | 通过 | 15 passed |
| 2 | `.\serviceCenter\mvnw.cmd -f serviceCenter/pom.xml -pl :agent-service -am test` | 通过 | Reactor BUILD SUCCESS；`agent-service` 445 passed |
| 2 | `python agent-runtime/scripts/check_contract_drift.py` | 通过 | active Python codegen 可重复且 provenance 有效 |
| 2 | `git diff --check` | 通过 | 无空白错误；仅 CRLF/LF 转换告警 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 原因 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | medium | Context 并发 CAS、事务整体回滚和 `readable=0` 防复活未在真实 MySQL 双事务中验证 | 现有 `*IT` 不是数据库集成测试，默认测试生命周期也不执行它们 | 在发布门禁补 MySQL/Testcontainers + Failsafe，覆盖并发 absent/version、退役、部分写失败回滚 |
| RISK-002 | low | `ContextRecordEntity` 不公开 createdAt/updatedAt，当前审计时间只存在于 SQL/Row | 当前业务算法不消费时间字段，但与文档声明的实体 shape 不完全一致 | 先明确领域实体是否需要时间审计读取，再经文档授权决定是否扩展，当前不建议为形式一致扩大代码 |
| RISK-003 | low | Maven 测试存在 Mockito 动态 agent 的未来 JDK 兼容告警 | 当前 JDK 仍允许 Byte Buddy 动态加载，本次测试均通过 | 依赖治理时统一配置 Mockito agent；本次不引入生产依赖 |

## 9. 结论

最终结论：
- 通过。

说明：
- 6 项代码问题均在授权范围内完成最小修复，并在第二轮复核中闭合。
- 未修改主详细设计、L0/L1 或关联文档；两项文档问题仅记录在本报告。
- 未引入生产依赖，未修改公共 HTTP 契约，未执行提交或推送。
