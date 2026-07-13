# P1_V2 单 Agent 内核完整基线总览 L2 实施详细设计 v2.0

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档状态 | In Review |
| 设计层级 | L2 实施详细设计总览 |
| 文档路径 | `docs/design/P1_V2/00_P1_V2单Agent内核收敛总览_L2实施详细设计_v2.0.md` |
| 适用代码基线 | `816e2c855574da5326379128bfb3e230241d2fe3` |
| 适用范围 | 当前单 Agent 的契约、可信执行、元数据安全、Adapter、资源边界和迁移门禁 |
| 上级文档 | `Agent目标架构总览_v1.0.md`、`Agent能力执行内核架构设计_v1.0.md`、`Agent契约与规划架构设计_v1.0.md`、`Agent元数据与上下文安全架构设计_v1.0.md` |
| 阅读策略 | 后续只读 L0/L1 + P1_V2；P1 旧文件仅为历史来源，不再作为前置或补充规范 |
| 是否可作为实现依据 | 否；P1_V2/00～06 全集评审已完成且 S0/S1=0，但仍为 In Review；经用户确认 Approved 并完成 P1_V2/06 M0 实施授权后方可实施 |

## 2. 修订历史

| 版本 | 日期 | 位置 | 修改原因 | 修改内容 |
|---|---|---|---|---|
| v2.0-a | 2026-07-13 | 全文 | 建立增量收敛草案 | 修正 CHAT-only、Planning identity、资源与端口边界 |
| v2.0-b | 2026-07-13 | 全文 | 降低旧 P1 阅读和比对成本 | 将全部 14 份 P1 内容合并到 01～06，P1_V2 改为自包含权威基线，新增完整覆盖矩阵和阅读顺序 |
| v2.0-c | 2026-07-13 | 第 6、13、14 节 | 对齐已评审 L0/L1 并消除冗余状态语义 | 统一 Effective Capability Resource Limits 权威公式；明确仅 Invocation 使用持久状态机，Context 使用版本 CAS，metadata/limits/artifact 使用不可变版本或 digest；漂移只终止当前 Invocation |
| v2.0-d | 2026-07-13 | 第 1、3、22、24 节 | P1_V2/P2_V3 全集终检同步基线与终态 | 对齐统一代码基线和评审记录，标记 P1_V2 全集评审已完成，保留 In Review 与 M0 实施边界；不新增评审轮次，不改变 S0/S1 结论 |

## 3. 文档状态说明

当前状态：**In Review**。P1_V2/00～06 全集评审已完成且 S0/S1=0，但评审完成不等于用户批准或实施授权。旧 P1 的 Implemented/Approved 只描述历史实现或当时结论，不能覆盖 P1_V2；未经用户确认不得自动标记 Approved。

## 4. 背景与目标

P1 曾按问题和阶段拆成 14 份文档，存在同一契约分布在主设计、补丁设计和收敛设计中的情况。新 L0/L1 又调整了单 Agent 与未来 Multi-agent 的边界。本文将仍然有效的设计、必要修正和实施门禁完整收进 P1_V2，使后续设计、编码和评审不再需要逐份比对 P1。

目标是形成稳定但不过度实现的单 Agent 内核：当前只有 CHAT/ConversationScope；共享接口避免绑定会话实体；为未来 owner/delegation/execution locality 保留中立 seam，但不创建 Run/Task/Attempt、Coordinator 或子 Agent 协议。

## 5. 设计范围

### 5.1 范围内

- Java/Python 契约生成和 drift 治理。
- Capability 注册、计划校验、可信执行、Invocation 生命周期与持久化。
- Profile、Policy、授权、Context、Result Security、统一密钥。
- Adapter SPI、canonical domain metadata、白名单排序。
- effective resource limits 与 capability-local provider ports。
- Capability v2 原子切换、权限权威源、扩展验证、遗留清理。

### 5.2 范围外

- Multi-agent L1/L2、Run/Task/Attempt、Task Graph、claim/lease/retry。
- P2 文档能力业务细节；其设计在 P2_V3。
- 本轮代码、SQL、配置实际修改。
- 修改 L0/L1 或 P1/P2/P2_V2 历史正文。

## 6. 上级文档约束

| 约束 | P1_V2 落地 |
|---|---|
| 当前单 Agent，未来可演进 | 中立 identity/owner/ref 接口；只实现 CHAT concrete type |
| Java 为执行与安全真值源 | Runtime 只生成 Route/Plan，权限、校验、执行、Context、结果安全均在 Java |
| 契约可追踪 | Java DTO -> OpenAPI -> generated Python + fixtures + drift gate |
| 规划与执行隔离 | logical PlanningArtifactIdentity + ExecutionScope currentness |
| 资源单调收紧 | Authorization/metadata 边界按 Definition/Profile/Policy/Permission/optional Delegation/Request 单调求交并冻结到 Authorization Snapshot；执行各边界消费同一或可证明更严格的 Effective Capability Resource Limits |
| 领域扩展不侵入内核 | role adapter + canonical metadata + registration + core-no-diff test |

## 7. 文档关系与阅读顺序

| 顺序 | 文档 | 唯一负责 |
|---:|---|---|
| 1 | 01 Agent 契约生成与治理 | 公共契约、OpenAPI、Python 生成、fixtures、drift |
| 2 | 02 可信执行内核与 Invocation 生命周期 | Registration、Validator、Core、artifact identity、checkpoint、终态 |
| 3 | 03 元数据、授权、Context 与 Result Security | Profile/Policy/Auth/Context/密钥/Mask/分页安全 |
| 4 | 04 Adapter 与 Domain Metadata 治理 | SPI、注册、canonical metadata、白名单排序 |
| 5 | 05 有效资源预算与 Capability-local Port | typed effective limits、deadline/cancel/retry、provider candidate |
| 6 | 06 原子迁移、扩展验证与清理门禁 | Capability v2 切换、权威源、迁移批次、代表性扩展和退出门禁 |

实施某主题时读取 00 + 对应主题文档及其明确列出的 P1_V2 依赖；不得把旧 P1 当成缺失章节的补充来源。

## 8. 设计边界与约束

1. 01～06 共同构成一个基线，编号不是实施优先级替代品。
2. 每一概念只有一个权威文档；其他文档只引用，不复制第二套字段或算法。
3. 历史来源保留 provenance，不再形成规范依赖。
4. 公开契约、DDL、跨服务接口变更在编码前仍按项目规则单独确认。
5. P1_V2 的文档完成不等于代码已对齐，实施状态单独管理。

## 9. 总体设计

```text
Entry -> Invocation/Lifecycle -> Route/Plan Runtime
     -> Planning Artifact -> Authorization/Metadata Projection
     -> Capability Registry/Validator -> Execution Core
     -> Capability Handler -> Adapter / Capability-local Provider
     -> Context Candidate + Raw Result -> Result Security -> Finalization
```

横切治理：ContractRef、effective resource limits、deadline/cancellation、audit、idempotency、typed failure、core-no-diff extension gate。

## 10. 详细功能设计

### 10.1 旧 P1 完整承接矩阵

| P1 历史文件 | P1_V2 权威承接 | 处理结论 |
|---|---|---|
| `D01_Agent契约生成与治理...` | 01 | 完整合并并修正契约治理 |
| `D02_00_CapabilityKernel实施总览与集成门禁...` | 02、06 | Kernel 主链归 02，集成门禁归 06 |
| `D02_01_Capability注册与可信执行内核...` | 02 | 完整合并；引用同一性改为逻辑 identity |
| `D02_02_Invocation生命周期与持久化...` | 02 | 完整合并；移除提前 TASK concrete type |
| `D02_03_元数据授权与Context安全...` | 03 | 完整合并 |
| `统一密钥管理与多注入源支持...` | 03 | 合并为安全基础设施章节 |
| `Agent_ResultSecurity值级Mask脱敏接入...` | 03 | 合并到统一 Result Security projector 链 |
| `Agent多轮分页与权限拒绝提示修复...` | 03 | 合并为 Query Context 与安全拒绝语义 |
| `D04_Agent Adapter与Domain Metadata收敛...` | 04 | 完整合并 |
| `Agent与业务域白名单排序能力...` | 04 | 合并为 QUERY role metadata 能力 |
| `D03_01_UserPermissionAuthority权限权威源契约说明...` | 03、06 | 接口语义归 03，跨服务切换门禁归 06 |
| `D03_02_Capability v2实施落地清单...` | 06 | 完整合并为实施文件/调用链清单 |
| `D03_Capability v2跨服务原子切换...` | 06 | 完整合并为原子批次与回滚边界 |
| `D05_Capability扩展验证与遗留清理...` | 06 | 完整合并为代表性扩展与 core-no-diff 门禁 |

### 10.2 权威冲突规则

L0/L1 > P1_V2/00 > P1_V2 专题文档。专题间冲突按“契约 01、安全 03、领域 04、资源 05、迁移 06”的所有权判断；无法判断时停止实施并回到评审，不引用旧 P1 仲裁。

### 10.3 状态与归档规则

旧 P1 不删除、不重写、不要求继续阅读。P1_V2 Approved 后可在独立索引中标记历史来源已被替代，但本轮未获授权修改旧目录，因此仅在新总览声明。

### 10.4 历史来源文件登记

以下 14 个文件均已由 10.1 矩阵承接，登记仅用于自动覆盖校验：

- `统一密钥管理与多注入源支持_L2实施详细设计_v1.0.md`
- `Agent_ResultSecurity值级Mask脱敏接入_L2实施详细设计_v1.0.md`
- `Agent多轮分页与权限拒绝提示修复_L2实施详细设计_v1.0.md`
- `Agent与业务域白名单排序能力_L2实施详细设计_v1.0.md`
- `D01_Agent契约生成与治理_L2实施详细设计_v1.0.md`
- `D02_00_CapabilityKernel实施总览与集成门禁_L2_v1.0.md`
- `D02_01_Capability注册与可信执行内核_L2_v1.0.md`
- `D02_02_Invocation生命周期与持久化_L2_v1.0.md`
- `D02_03_元数据授权与Context安全_L2_v1.0.md`
- `D03_01_UserPermissionAuthority权限权威源契约说明_L2_v1.0.md`
- `D03_02_Capability v2实施落地清单_L2_v1.0.md`
- `D03_Capability v2跨服务原子切换_L2实施详细设计_v1.0.md`
- `D04_Agent Adapter与Domain Metadata收敛_L2实施详细设计_v1.0.md`
- `D05_Capability扩展验证与遗留清理_L2实施详细设计_v1.0.md`

## 11. 接口设计

总览不重复专题签名。公共契约见 01；Kernel/Lifecycle 见 02；安全端口见 03；Adapter/Metadata 见 04；资源/provider 见 05；跨服务变更清单见 06。

## 12. 数据设计

数据所有权分为：01 的公共 DTO/ContractRef、02 的 Invocation/checkpoint、03 的 Context/protected payload、04 的 immutable metadata snapshot、05 的 resource/candidate value object。不得创建跨所有权的万能 Context 或 Map payload。

## 13. 状态流转设计

当前只有 Invocation 维护 PROCESSING/COMPLETED/FAILED/CANCELLED 持久状态机。Context 使用独立 record version、TTL 和 CAS；metadata snapshot、Planning Artifact、Effective Capability Resource Limits 与 provider operation metadata 使用不可变 version/identity/digest 关联，不新增持久状态枚举。Multi-agent 状态不得提前加入当前枚举。

## 14. 幂等、事务与一致性设计

Start/checkpoint/Context 分别使用 correlation、checkpoint identity/不可变绑定和 version CAS；外部 adapter/provider 不进入本地事务。Planning artifact、authorization、metadata 和 effective limits 以不可变 identity/digest 绑定；任一漂移使当前 Invocation fail closed，只有新的 Invocation 才能重新规划，不在当前执行链内隐式重试或替换证据。

## 15. 权限、风控与审计设计

所有外部调用前 assert current；所有原始结果出内核前安全投影。审计使用稳定 ID、version、digest、decision/reason，不保存 Token、密钥、完整 prompt、原始敏感 payload。

## 16. 性能与容量设计

只缓存版本化不可变快照；权限缓存受撤权窗口约束。资源限制由 05 冻结，任何 capability 不得绕过 effective limits 自行扩大 timeout、tokens、topK 或 payload。

## 17. 兼容性与扩展性设计

新增 capability/domain/provider 通过 registration、metadata、typed contract 和 local port 扩展；代表性扩展必须证明 Kernel Core 无差异。未来 Multi-agent 复用 invocation/artifact/authorization/operation seam，新增具体 owner/task 协议而非修改当前业务 capability。

## 18. 日志、监控与告警

统一 correlation/invocation/capability/domain/contract/version/reason 标签规范；禁止高基数正文。专题指标在 01～06 定义，06 负责 release gate 汇总。

## 19. 实现落点清单

| 文档 | 主要模块 |
|---|---|
| 01 | `agent-api`、`agent-runtime/contracts`、契约脚本/fixtures |
| 02 | `agent-service/invocation`、`planning`、`kernel`、`lifecycle` |
| 03 | `agent-service/metadata`、`common-security`、`auth-service` |
| 04 | `agent-adapter-api`、domain adapters、domain metadata、transaction API/service |
| 05 | capability handlers/local ports/provider adapters |
| 06 | 跨模块原子变更、SQL/config/scripts/tests |

## 20. 测试设计

验证顺序：契约 drift -> 单元 -> architecture/core-no-diff -> repository/adapter contract -> 直接集成 -> 编译 -> 静态文档覆盖。每个专题的失败路径和恢复路径不得被只测 happy path 替代。

## 21. 风险与待确认事项

| 风险 | 影响 | 处理 |
|---|---|---|
| 新基线与当前代码有偏差 | 不能直接宣称 Implemented | 06 维护原子迁移和对齐矩阵 |
| 公开契约/DDL/跨服务接口 | 影响调用者和数据 | 实施前单独确认 |
| 旧文档仍可被搜索到 | 误用历史规则 | 新任务入口统一指向本总览，不再列旧文件为前置 |
| Multi-agent seam 过度设计 | 当前复杂度上升 | 只保留中立引用，不实现具体 Task/Run 模型 |

## 22. 评审记录

| 轮次 | 日期 | 结论 | 说明 |
|---:|---|---|---|
| 1 | 2026-07-13 | 有条件通过 | 完成增量收敛，仍依赖旧 P1 阅读 |
| 2 | 2026-07-13 | 通过 | 已将 14 份旧设计完整映射并合并到 01～06；全集一致性验证完成且 S0/S1=0，文档仍保持 In Review，等待用户 Approved 与 M0 实施授权 |

## 23. 实施对齐检查

- [x] 每份旧 P1 有且只有明确的 P1_V2 承接位置。
- [x] 新基线不再要求阅读旧 P1。
- [x] 当前单 Agent 与未来 Multi-agent seam 边界明确。
- [x] 接口、数据、安全、扩展和迁移专题完整。
- [ ] 全部文档静态校验和交叉引用复核完成。
- [ ] 用户确认 Approved。

## 24. 任务完成摘要

P1_V2 已从增量修订集调整为 00～06 的自包含单 Agent 内核基线。后续可只阅读 L0/L1 与 P1_V2，不再逐份比对 P1。00～06 全集评审已完成且 S0/S1=0；当前状态仍为 **In Review**，等待用户 Approved 与 M0 实施授权。
