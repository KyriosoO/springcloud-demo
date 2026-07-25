# [L2_02_00] 单体 Agent 业务查询公共约束、配置与出域详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent 业务查询公共约束、配置与出域详细设计 |
| 文档标识 | `SA-L2-BUSINESS-COMMON-001` |
| 文档编号 | `L2_02_00` |
| 文档路径 | `docs/design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Draft |
| 当前版本 | v0.1 |
| 日期 | 2026-07-25 |
| 适用范围 | Python `agent-runtime` 内 Employee/Transaction Adapter 共用的代码绑定动作原语、强类型配置收紧、用户 JWT 透传、统一 Authority 外部契约消费语义、类型化业务结果、最小有效用户结果、字段交集、有限转换、模型安全载荷、事实绑定、失败矩阵、组合根与公共测试替身 |
| 上位文档 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v1.2；[`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v0.4；[`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.2（已评审/已通过，`BQ-GATE-001` 已关闭） |
| 直接依赖 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4（In Review）的能力 API、JWT wrapper 和公共结果；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v0.1 Draft 的 safe payload/grounding 接缝 |
| 下位/后续契约 | 规划中的 `L2_02_01` Employee Adapter 与业务授权联调；规划中的 `L2_02_02` Transaction Adapter 与业务授权联调 |
| 外部契约 | `auth-service` 用户 JWT；`common-security` role→Authority；`employee-service`、`mq-procedure-service` 公开只读查询契约 |
| 实现基线 | 目标 `agent-runtime` 业务公共模块及两个 Adapter 均不存在；当前 JWT 已签发 `role` 集合，统一 Authority 映射和两域动作级最终授权尚未具备 |
| 是否可作为实现依据 | 否，本文尚未独立评审，直接依赖与本切片 `BQ-GATE-002` 均未关闭，真实业务授权/出域门禁保持 Open |
| 当前允许实施范围 | 本文编写、自检、合成 DTO/字段/权限矩阵和不访问真实服务的公共 fake 推演 |
| 当前禁止动作 | 创建或修改 Agent/Java 代码、配置、测试、公共契约；新增业务接口；启用真实 Employee/Transaction；发送真实业务数据到 DeepSeek；关闭任何门禁 |
| 修改权限 | 本轮用户已授权第二批 L2 与必要直接关联文档原子同步，并授权 Git commit/push；代码、配置、Schema、外部契约和真实调用未获授权 |
| 维护责任人 | 项目维护者（个人开发者，姓名未在需求中指定） |

> 本文只定义两个业务域可以复用的无业务字段语义原语，不列出 Employee/Transaction 精确动作、端点、请求/响应字段或业务授权实现。公共原语不得演化为动态 HTTP Adapter、权限引擎或字段脚本平台。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 执行第二批 L2 详细设计 | 创建业务动作/配置/结果/字段/出域公共结构，固定 JWT 无兜底、Authority 消费前提、有限转换、事实载荷、失败矩阵、组合根和实现/测试落点 |
| 2 | 2026-07-25 | 4～13、16～18 | 作者第 1 轮自检修复 | 收回共享安全提供方实现所有权，明确业务服务最终授权与响应可见性，补齐最小有效用户结果、业务文本数据隔离、回答事实绑定和配置失败关闭 |
| 3 | 2026-07-25 | 8、11、13～14、17～19 | 作者第 2～3 轮自检与严格校验修复 | 将 common domain ID 改为 provider 代码绑定而非硬编码两域，修正 transform 强类型输入，补齐 fact source、策略/配置快照及 denied 结果组合；严格校验通过 |

## 3. 背景、目标与范围

### 3.1 背景与问题

L1_02 已确定 Employee、Transaction 使用两个独立 Python Adapter，直接作为能力处理器注册；业务服务拥有最终角色授权，Adapter 只透传用户 JWT、收紧参数/字段并构造模型安全载荷。当前缺少一套公共但不含域业务语义的实现级规则，容易导致：

1. 两个 Adapter 各自定义 JWT 透传、错误状态和字段出域，产生契约漂移。
2. 复用现有服务令牌兜底，绕过用户身份和业务域审计主体。
3. 把 Adapter 字段投影误当成业务服务行级/字段级授权。
4. 配置增加动作、URL、字段或转换逻辑，演化为动态执行平台。
5. 已存在记录经字段删除后被误报为 `no_result` 或空 `success`。
6. 业务字符串被模型当作指令，或回答补造安全载荷外的实体、数值和状态。

### 3.2 目标与验收行为

| 需求编号 | 目标或用户可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-BQCOM-001` | 两域使用同一公共动作/结果骨架但保持域隔离 | 公共模块无 Employee/Transaction 字段或端点；两个域用代码定义实例化；模拟第三域不修改 core/现有 Adapter | REQ_00 EXT-01/02；L1_02 6、13 |
| `REQ-BQCOM-002` | 配置只能启停和收紧已确认动作 | 未知动作/字段/维度/转换、扩大上限、删除必需用户字段均在启动时失败 | REQ_00 CFG-01～04；L1_02 6.3 |
| `REQ-BQCOM-003` | 每次业务调用只透传当前原始用户 JWT | 缺 JWT、非 user context 或 token 为空时业务调用为零；不存在服务 token/固定管理员兜底 | REQ_00 SEC-01/02；L1_02 7.3 |
| `REQ-BQCOM-004` | 角色由统一安全契约映射并由业务服务最终验证 | `ADMIN/VIEWER` 消费场景形成预期 Authority；缺失/空白/未知/格式错误拒绝；Adapter 不读取 role 作授权 | REQ_00 SEC-03/04；L0 `SA-FACT-015` |
| `REQ-BQCOM-005` | 业务无结果、已有记录和契约失败保持真实语义 | `no_result` 只来自确认后的业务无数据语义；存在记录但必需用户字段缺失返回 `downstream_failure` | L1_02 7.5 |
| `REQ-BQCOM-006` | 用户结果和模型字段按多重交集失败关闭 | 未声明/未分类/额外/冲突字段不进入视图；模型字段必为用户结果字段子集 | L0 `SA-C-020`；L1_02 7.6 |
| `REQ-BQCOM-007` | 有限转换在模型调用前由代码执行 | 配置只能选择有限枚举；类型不匹配/转换失败时 safe payload 不存在且回答模型零调用 | REQ_00 CFG-03；L1_02 `BQ-AD-007` |
| `REQ-BQCOM-008` | 业务回答的肯定事实可追踪到本次安全载荷 | 每条回答语句带 fact 引用；引用存在且数字/日期/枚举/标识值来自事实；否则候选答案丢弃 | L1_02 7.6、10.2 |
| `REQ-BQCOM-009` | 失败状态和调用方可见语义稳定 | `401/403/no_result/invalid_argument/timeout/downstream_failure/model_egress_denied` 不混淆，原始错误不外泄 | REQ_00 异常要求；L1_02 7.7 |
| `REQ-BQCOM-010` | 业务敏感问题提供给全局输入闸门验证 | Employee/Transaction 标识、个人标识、账户、联系方式、凭证和敏感自由文本场景均有零调用测试 | L1_02 10.1；`CR-GATE-003` |
| `REQ-BQCOM-011` | 公共业务查询无持久化、无重试和写副作用 | 每个动作最多一次业务调用；取消/超时后不接纳结果；无 cache/database/message/replay | L1_02 9.3、10.3 |

### 3.3 范围内

- 业务动作定义、适用约束维度、强类型收紧设置和启动快照。
- 类型化业务调用结果、受控用户结果、最小有效结果不变量和公共失败映射。
- 用户 JWT 专用只读 HTTP 客户端原则、取消/超时/响应大小和零服务身份兜底。
- role→Authority 的业务查询消费假设、现状差距和端到端联调矩阵。
- 字段分类、用户/模型字段交集、代码有限转换、safe payload 和 grounding policy。
- 业务敏感问题类别、日志/审计、组合根、模拟第三域和公共测试替身。

### 3.4 范围外

- Employee/Transaction 精确动作 ID、端点、输入 DTO、结果字段、分页/时间上限、字段分类实例和方法授权；归各域 L2。
- 修改 `auth-service` 用户/角色、JWT 公共契约或 `common-security` 转换实现；需要时由其权威另行设计并获授权。
- 修改 `employee-service`、`mq-procedure-service` 接口、守卫、方法授权或响应数据可见性；归域 L2/提供方设计并受门禁控制。
- DeepSeek HTTP、Prompt 通用结构、Provider 失败、全局问题输入策略；归 `L2_00_02`。
- Knowledge、聚合、跨域组合、写入、审批、消息提交、索引管理、Multi-Agent 和生产级韧性平台。

### 3.5 适用技术剖面

| 剖面 | 适用性 | 说明 |
|---|---|---|
| Python | 适用 | 公共动作、设置、HTTP/JWT、投影、转换、事实及测试原语 |
| Java | 只读消费边界适用 | 本文记录当前 Java 触点和可观察 Authority 契约，不设计提供方私有实现或修改类 |
| HTTP/API | 适用 | Python→业务服务单次只读调用的通用安全/失败规则；精确路径归域 L2 |
| 配置 | 适用 | 全局出域硬限制和每动作收紧型设置；启动冻结 |
| 权限/审计 | 适用 | 用户 JWT、Authority、业务最终授权、字段最小化和日志禁项 |
| 状态/一致性 | 适用 | 单请求只读状态、一次调用、取消和迟到丢弃；无跨资源事务 |
| 数据库/消息/索引 | 不适用 | Adapter 不直接访问或写入这些资源 |
| 测试 | 适用 | Python 单元/契约/架构、Java 外部契约证据和跨服务集成矩阵 |

### 3.6 完成判定

本文达到“可进入独立正式评审”的条件为：

1. 公共结构不含两个域的具体业务字段/端点，且域 L2 可直接实例化。
2. 配置交集、最小有效用户结果、转换枚举和 safe payload 字段完整。
3. JWT/Authority 消费边界、当前差距、失败关闭和联调证据明确。
4. Python 公共类型和边界函数具有建议路径、签名、输入/输出、异步、错误和消费者。
5. Java 当前触点与“本文不修改”的边界明确。
6. 全部 REQ/CON 追踪完整，作者自检无 Blocker/Major，严格校验 0 errors、0 warnings。

## 4. 上位约束与追踪关系

### 4.1 约束映射

| 约束编号 | 上位文档/契约位置 | 约束内容 | 本设计落实方式 | 偏离情况 |
|---|---|---|---|---|
| `CON-BQCOM-001` | L1_02 `BQ-AD-001/002/003` | 两个独立 Adapter、代码绑定有限动作、一个动作映射一个只读契约 | `DR-BQCOM-001`、`DR-BQCOM-015` | 无 |
| `CON-BQCOM-002` | L1_02 6.3、7.2 | 配置只能收紧动作、参数、结果和模型字段 | `DR-BQCOM-002`、`DR-BQCOM-013` | 无 |
| `CON-BQCOM-003` | L1_02 7.3～7.4 | 原始用户 JWT 透传，无服务身份回退，业务服务最终授权 | `DR-BQCOM-003`、`DR-BQCOM-004`、`DR-BQCOM-005` | 无 |
| `CON-BQCOM-004` | L0 `SA-FACT-015`；L1_02 7.4 | 首批共同允许语义角色 `admin/viewer`，统一 Authority 映射归外部权威 | `DR-BQCOM-004` | 无 |
| `CON-BQCOM-005` | L1_02 7.5 | no_result 与已有记录、字段投影和契约失败分离 | `DR-BQCOM-006`、`DR-BQCOM-007` | 无 |
| `CON-BQCOM-006` | L0 `SA-C-020`；L1_02 7.6 | 模型字段为多重交集，未知默认拒绝，转换模型前执行 | `DR-BQCOM-008`、`DR-BQCOM-009`、`DR-BQCOM-010` | 无 |
| `CON-BQCOM-007` | L1_02 7.6；L2_00_02 8.3 | 业务文本是数据，回答事实绑定 safe payload | `DR-BQCOM-010`、`DR-BQCOM-011` | 无 |
| `CON-BQCOM-008` | L1_02 7.7、9.2 | 公共失败稳定且不泄露原始错误 | `DR-BQCOM-012` | 无 |
| `CON-BQCOM-009` | L1_02 8、9.3、10.3 | 无持久化/重试/写入，服从总预算和取消 | `DR-BQCOM-014` | 无 |
| `CON-BQCOM-010` | L1_02 13.3 | 公共 L2 不拥有域字段/端点或共享安全实现 | `DR-BQCOM-015`、`DR-BQCOM-016` | 无 |
| `CON-BQCOM-011` | L1_02 10.1 | 提供业务敏感问题场景但不复制全局输入策略 | `DR-BQCOM-017` | 无 |

### 4.2 端到端追踪矩阵

| REQ/CON | 模块切片 | 设计规则 | 责任主体 | 契约/状态影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-BQCOM-001`、`CON-BQCOM-001` | 公共动作/扩展 | `DR-BQCOM-001`、`DR-BQCOM-015` | business common、域 provider | 代码定义/无动态 Adapter | `IMPL-BQCOM-001/010/011` | `TEST-BQCOM-001/011` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-002`、`CON-BQCOM-002` | 配置 | `DR-BQCOM-002`、`DR-BQCOM-013` | settings validator | 冻结动作快照 | `IMPL-BQCOM-002/009` | `TEST-BQCOM-002/010` | `VAL-BQCOM-002/004` |
| `REQ-BQCOM-003`、`CON-BQCOM-003` | JWT/业务调用 | `DR-BQCOM-003`、`DR-BQCOM-005` | outbound client、域 Adapter | Authorization header/一次调用 | `IMPL-BQCOM-003` | `TEST-BQCOM-003/009` | `VAL-BQCOM-002/005` |
| `REQ-BQCOM-004`、`CON-BQCOM-004` | Authority 消费 | `DR-BQCOM-004` | 外部安全权威/业务服务 | role claim→Authority 观察结果 | `IMPL-BQCOM-012` | `TEST-BQCOM-004` | `VAL-BQCOM-005` |
| `REQ-BQCOM-005`、`CON-BQCOM-005` | 响应/用户结果 | `DR-BQCOM-006`、`DR-BQCOM-007` | response mapper、projector | no_result/valid user result | `IMPL-BQCOM-004/005` | `TEST-BQCOM-005/006` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-006`、`CON-BQCOM-006` | 字段出域 | `DR-BQCOM-008`、`DR-BQCOM-009`、`DR-BQCOM-010`、`DR-BQCOM-018` | field registry、projector | 用户视图/safe payload | `IMPL-BQCOM-005/006/007` | `TEST-BQCOM-006/007` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-007` | 有限转换 | `DR-BQCOM-009` | transform registry | 转换值/拒绝 | `IMPL-BQCOM-006` | `TEST-BQCOM-007` | `VAL-BQCOM-002` |
| `REQ-BQCOM-008`、`CON-BQCOM-007` | 事实绑定 | `DR-BQCOM-010`、`DR-BQCOM-011` | safe payload、grounding policy | fact ID/候选回答 | `IMPL-BQCOM-007/008` | `TEST-BQCOM-008/012` | `VAL-BQCOM-003` |
| `REQ-BQCOM-009`、`CON-BQCOM-008` | 失败 | `DR-BQCOM-012` | client/mapper/handler | 公共 status/code/source | `IMPL-BQCOM-004/009` | `TEST-BQCOM-009` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-010`、`CON-BQCOM-011` | 模型输入负向场景 | `DR-BQCOM-017` | business fixture、L2_00_02 | 问题分类/零调用 | `IMPL-BQCOM-013` | `TEST-BQCOM-013` | `VAL-BQCOM-003` |
| `REQ-BQCOM-011`、`CON-BQCOM-009` | 生命周期 | `DR-BQCOM-014` | handler/client | 请求内只读状态 | `IMPL-BQCOM-003/009` | `TEST-BQCOM-009/010` | `VAL-BQCOM-003` |
| `CON-BQCOM-010` | 所有权边界 | `DR-BQCOM-015`、`DR-BQCOM-016` | common module、外部提供方 | 无越权实现 | `IMPL-BQCOM-010/012` | `TEST-BQCOM-004/011` | `VAL-BQCOM-003/005` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 交互契约 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|---|
| L1_02 v0.2 | parent | 细化公共 L2 唯一范围 | 架构边界、域隔离、门禁 | 业务查询公共语义 | 上位权威 | 只读 |
| L2_00_01 v0.4 | direct dependency | 消费 handler/context/result | 核心、注册、公共不变量 | `CapabilityResult`/JWT wrapper | 执行上下文 | 只读，当前 In Review |
| L2_00_02 v0.1 | peer/direct dependency | 提供 business safe payload/grounding policy | Provider、通用 JSON output、失败映射 | facts envelope | 模型调用状态 | 只读 |
| `auth-service` | external authority | 记录消费假设/测试场景 | 用户角色分配、JWT 签发 | `role` claim | 用户/角色 | 只读 |
| `common-security` | external authority | 记录 Authority 可观察要求和差距 | role→GrantedAuthority 统一映射 | Spring Security Authentication | 角色映射 | 只读；本文不设计修改 |
| `employee-service` | external/domain authority | 不定义具体动作 | Employee 最终授权和响应可见性 | 域 L2 固化 | Employee 数据/权限 | 只读 |
| `mq-procedure-service` | external/domain authority | 不定义具体动作 | Transaction 最终授权和响应可见性 | 域 L2 固化 | Transaction 数据/权限 | 只读 |
| 规划中的 L2_02_01/02 | child designs | 提供公共原语 | 分别实例化动作、字段、端点、客户端和权限测试 | code-bound definition | 域动作/配置 | 尚未创建 |

### 5.1 当前 Java 触点（只读事实）

| 状态 | 路径/符号 | 已核实行为 | 本文判断 |
|---|---|---|---|
| 已存在 | `auth-service/src/main/java/com/dylan/authcenter/service/JwtService.java` `String generateToken(String userId)` | JWT 包含 `sub/iat/exp/token_type=user/role`，role 来自用户服务集合 | 可复用声明来源；不修改 |
| 已存在 | `auth-service/src/main/resources/auth-users.yml` | admin→ADMIN、dylan→ADMIN、viewer_t→VIEWER | 用户分配与确认范围一致；不是运行时 Authority 证据 |
| 已存在 | `common-security/src/main/java/com/dylan/common/security/ResourceServerSecurityAutoConfiguration.java`、`common-security/src/main/java/com/dylan/common/security/ReactiveResourceServerSecurityAutoConfiguration.java` | 默认只要求 authenticated，未配置 role converter | `SA-GATE-004/005` 差距；本文不定义提供方类改造 |
| 已存在 | `common-security/src/main/java/com/dylan/common/security/FeignTokenRelayAutoConfiguration.java` | 缺用户 JWT 时可回退 service token | 不得复用于 Agent 用户查询客户端 |
| 已存在 | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java` `void requireUser(Authentication)` | 只校验 user token | 未满足角色最终授权 |
| 已存在 | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java` `void requireUser(Authentication)` | 只校验 user token | 未满足角色最终授权 |

上述精确文件已在当前仓库核实；本文不据此授权 Java 变更。若后续需要修改共享安全或业务服务，域 L2 必须记录精确文件、方法、契约影响并取得单独授权。

## 6. 当前实现基线与最小变更方案

### 6.1 差距与根因

| 维度 | 当前状态 | 设计根因 | 本文处理 |
|---|---|---|---|
| Python Adapter | 不存在 | 无公共业务查询原语 | 建议新增最小 common module |
| JWT 透传 | Java 通用客户端存在 service fallback | 通用服务调用与用户查询语义不同 | Python 专用用户 JWT 客户端，缺失零调用 |
| Authority | claim 已签发、converter 未具备 | 声明权威与执行权威未闭环 | 只定义消费预期/联调矩阵，真实动作禁用 |
| 结果 | 两域语义不同 | 原始 DTO 不能成为 Agent 契约 | 公共 tagged result + 域实例 |
| 字段出域 | 未建立 | 用户可见与模型可见未分离 | 两次投影、有限转换和 facts |
| 回答事实 | 无领域 grounding | 模型引用 fact ID 仍可能补造 | 业务 grounding policy |

### 6.2 最小变更方案与方案对比

| 变更项 | 必要性 | 复用内容 | 不采用的方案及原因 |
|---|---|---|---|
| 建议新增 `agent_runtime.business` 公共原语 | 两域共同语义只实现一次 | L2_00_01 能力 API | 不建设通用动态 Adapter：会把 URL/DTO/权限配置化 |
| 两域各自代码定义 | 保持域字段/契约所有权 | 公共 generic 类型 | 不把 Employee/Transaction 放进统一动作表 |
| Python 专用 user-JWT client | 禁止 service fallback | `OpaqueUserToken` | 不复用 Java Feign interceptor；它允许服务身份兜底且不在 Python |
| 字段定义+配置交集 | 只收紧且可测试 | 业务授权响应 | 不使用脚本/表达式/JSONPath；无法审计且可扩权 |
| 六个有限转换 | 覆盖首期基本最小化 | Python 标准库/Decimal | 不引入规则引擎或通用脱敏库 |
| 结构化 facts+grounding | 防业务文本控制模型/补造事实 | L2_00_02 envelope | 不让模型自行脱敏或解释原始响应 |

## 7. 职责、分层与依赖设计

### 7.1 责任分解

| 组件/类型 | 状态 | 唯一职责 | 明确不负责 | 输入/输出 |
|---|---|---|---|---|
| `BusinessActionDefinition[...]` | 建议新增 | 代码绑定动作、类型、维度、字段和契约上限 | 动态端点/角色/脚本 | 定义→冻结动作 |
| `BusinessActionSettings` | 建议新增 | 表达配置收紧值 | 新动作/字段/权限 | 配置源→有效设置 |
| `BusinessFieldDefinition` | 建议新增 | 字段 ID、类型、分类、提取器和允许转换 | 业务服务授权 | typed record→field |
| `BusinessResponseNormalizer` | 建议新增 Protocol | 把一个域响应映射为 tagged result | HTTP/角色/模型 | wire response→service result |
| `BusinessUserResultProjector` | 建议新增 | 形成最小有效本地用户视图 | no_result 判定、业务授权 | authorized records→user result |
| `BusinessEgressProjector` | 建议新增 | 计算交集、转换并构造 facts | 调用模型、Prompt | user result→egress |
| `BusinessTransformRegistry` | 建议新增 | 六个代码转换 | 配置脚本/动态参数 | typed value→safe value |
| `BusinessAnswerGroundingPolicy` | 建议新增 | 校验 fact 引用和事实 token | Provider/通用 JSON parsing | payload+candidate→decision |
| `UserJwtBusinessHttpClient` | 建议新增 | 单次只读请求、JWT header、预算/响应上限 | 选择动作、服务 token、域 DTO | request spec→bounded response |
| 域 Adapter | 后续建议新增 | 组合上述原语并实现具体 handler | 另一域、Knowledge、最终授权 | typed args+context→result |

### 7.2 依赖方向

```text
agent-core
  → agent-capability-api
    ← agent-employee-adapter
       → agent_runtime.business common primitives
       → employee-service public read contract
    ← agent-transaction-adapter
       → agent_runtime.business common primitives
       → mq-procedure-service public read contract

agent_runtime.business egress
  → L2_00_01 ModelEgressResult / safe payload
  → L2_00_02 AnswerGroundingPolicy seam
```

禁止依赖、禁止绕过和反向依赖规则：

- common 模块不得导入 Employee/Transaction DTO、URL、字段或角色实现。
- 两个 Adapter 不得互相导入，不得导入业务服务内部 Mapper/Repository/ES 客户端。
- core、LangGraph、模型 Provider 不得导入域字段配置。
- Adapter 不得解析 role 后决定调用；不得绕过业务服务直接访问数据。
- 业务服务不得依赖 Agent action、safe payload 或模型结构。
- 配置不得指定 Python 类、函数、URL path、HTTP method、SQL、DSL、JSONPath 或转换参数对象。

### 7.3 内聚与耦合判断

JWT 无兜底、配置交集、结果状态、有限转换和 facts envelope 是两个域完全相同的安全/契约语义，因此集中在 common module；动作、字段、端点和授权入口只因各业务域变化，留在域 Adapter。common 只提供代码原语，不保存动作实例或运行期全局可变注册表，避免成为第三个业务域权威。

## 8. 公共类型、动作定义与配置

### 8.1 设计规则目录

| 规则编号 | 规则 | 责任主体 | 触发条件 | 输出/状态效果 |
|---|---|---|---|---|
| `DR-BQCOM-001` | 每个业务动作由域代码定义稳定 ID、一个只读外部契约、强类型输入/响应/记录和字段目录；common 不动态创建动作 | 域 definition/provider | 启动 | 有限可审计动作 |
| `DR-BQCOM-002` | 设置只允许在代码 definition 的适用维度和上限内取子集/更小值；未声明维度出现配置即失败 | settings validator | 启动 | 配置不能扩权 |
| `DR-BQCOM-003` | outbound client 只接受 `OpaqueUserToken` 显式 reveal 后设置单一 Authorization header；缺失/空 token 零网络调用且无 service fallback | HTTP client、handler | 调用前 | 用户身份原样透传 |
| `DR-BQCOM-004` | Agent 只消费外部 role→Authority 可观察契约：role claim 是已验证非空集合，`ADMIN/VIEWER` 分别形成 `ROLE_ADMIN/ROLE_VIEWER`；缺失/空白/未知/错误失败关闭；用户名不是规则 | 外部安全权威、业务集成测试 | 业务入口认证 | 业务服务获得统一 Authority |
| `DR-BQCOM-005` | 业务服务是动作和成功响应数据可见性的最终授权点；Adapter 只在已授权 2xx 类型化响应上继续收紧 | 业务服务、域 Adapter | 外部调用 | 投影不替代授权 |
| `DR-BQCOM-006` | `no_result` 只能由域 definition 绑定的明确无数据语义产生；401/403/timeout/invalid response/投影后空值均不能转 no_result | response normalizer | 响应映射 | 状态真实 |
| `DR-BQCOM-007` | 每个动作声明非空 required user fields 或等价 invariant；已有记录却无法满足时返回 downstream_failure，禁止空 success | definition、user projector | 用户结果投影 | 最小有效结果 |
| `DR-BQCOM-008` | 用户字段=实际授权响应字段∩代码 user 字段∩配置 user 字段；模型字段再交集代码 model candidate、配置 model 字段和全局规则 | field projectors | 成功响应 | 两个不同视图 |
| `DR-BQCOM-009` | 转换固定六个枚举、代码实现、类型严格；配置只可为字段选择 definition 明示允许项，失败时该模型载荷整体拒绝 | transform registry | 字段投影 | 模型前完成转换 |
| `DR-BQCOM-010` | safe payload 使用 `schema_version=1` 和有界 facts；业务文本只作为 JSON value，fact ID/record ref 为请求内序号，不含原始控制指令 | egress projector | 出域允许 | 结构化最小载荷 |
| `DR-BQCOM-011` | 回答每个事实句必须携带 `[fact-NNNN]` 标记；used IDs、标记、数字/日期/枚举/标识 token 均须由 payload 支持，unsupported claims 必须为空 | grounding policy | 模型候选返回 | 无依据回答丢弃 |
| `DR-BQCOM-012` | 外部状态按固定矩阵映射；原始错误 message/body/header/stack 不进入公共结果、日志或模型 | client、normalizer、handler | 失败 | 稳定 code/source |
| `DR-BQCOM-013` | 任一已启用动作配置、definition、字段/转换引用或必需依赖无效时整个 Runtime 不就绪；禁用动作不建客户端 | composition root | 启动 | 不运行半有效动作 |
| `DR-BQCOM-014` | 每个动作最多一次业务 HTTP；无自动 retry/replay/换身份/换动作；状态只在 handler 栈内，取消/截止后丢弃迟到响应 | handler/client | 每请求 | 只读且有界 |
| `DR-BQCOM-015` | common 只提供原语和 Protocol，域 provider 显式实例化；模拟第三域只新增 fixture/provider，不修改 core/common/已有 Adapter | composition root | 扩展 | 无动态插件平台 |
| `DR-BQCOM-016` | 本文不定义或修改 `auth-service/common-security` 私有实现、域端点/字段/授权方法；只记录消费差距和证据 | 文档/测试边界 | 设计/联调 | 权威不越界 |
| `DR-BQCOM-017` | 业务敏感问题类别与合成场景提供给 L2_00_02，实际 allow/deny 仍由全局 `QuestionEgressGuard` 决定 | fixture、模型测试 | 动作选择前 | 不复制输入策略 |
| `DR-BQCOM-018` | 有效用户结果但模型字段为空、全局禁用、冲突或转换失败时返回 `success + denied` 与本地受控结果，回答模型零调用；本地结果本身不可返回时才使用 `model_egress_denied` | egress projector、域 definition | 出域判定 | 本地/外发分离 |

### 8.2 代码绑定动作定义

```python
BusinessActionDefinition[
    TInput,
    TWireRequest,
    TWireResponse,
    TRecord,
]
```

| 字段 | 类型 | 必填 | 语义 |
|---|---|---:|---|
| `action_id` | `str` | 是 | 域命名空间稳定 ID；精确值归域 L2 |
| `domain_id` | `str` | 是 | 由 provider 代码绑定并满足 canonical ID 语法；首批生产值为 `employee/transaction`，非模型或配置创建 |
| `contract_version` | `int` | 是 | 当前动作契约版本 |
| `descriptor` | `CapabilityDescriptor` | 是 | 提交核心注册 |
| `argument_validator` | `CapabilityArgumentValidator[TInput]` | 是 | 模型 JSON→强类型输入 |
| `request_mapper` | callable | 是 | `TInput`→`TWireRequest`；不接受动态 URL |
| `response_normalizer` | `BusinessResponseNormalizer[...]` | 是 | wire→tagged result |
| `applicable_dimensions` | `frozenset[ConstraintDimension]` | 是 | 配置可出现的有限维度 |
| `field_definitions` | tuple | 是 | 非空、ID 唯一、代码绑定 extractor/type/classification |
| `required_user_field_ids` | tuple | 是 | 非空或绑定等价 invariant |
| `answer_mode` | `structured_only/model_assisted` | 是 | 代码决定，不由配置放宽 |
| `max_contract_limits` | frozen value | 是 | 配置只能降低 |

definition 不能包含角色白名单；允许角色由业务服务实现并按上位确认的 `admin/viewer` 验证。

### 8.3 强类型动作设置

| 字段 | 类型 | 约束 |
|---|---|---|
| `enabled` | bool | 只启停代码存在动作 |
| `max_page_size` | int/None | 仅适用维度可设置；1～代码上限 |
| `max_result_count` | int/None | 同上 |
| `max_time_range_days` | int/None | 同上 |
| `allowed_filter_field_ids` | tuple[str]/None | 代码允许集合的子集 |
| `allowed_sort_field_ids` | tuple[str]/None | 代码允许集合的子集 |
| `user_result_field_ids` | tuple[str] | 代码 user 字段子集且保留 required invariant |
| `model_field_ids` | tuple[str] | user fields 与代码 model candidates 的子集 |
| `user_transforms` | tuple[`FieldTransformSelection`] | 字段允许枚举之一 |
| `model_transforms` | tuple[`FieldTransformSelection`] | 同上；模型前执行 |
| `timeout_ms` | int | 1～动作代码上限且小于请求剩余预算 |

配置源的精确环境键由域 L2 随动作 ID 固化；common 只拥有上述字段及验证算法。禁止使用任意 mapping 透传未声明配置。

### 8.4 字段定义与分类

`BusinessFieldDefinition[TRecord, TValue]` 至少包含：

| 字段 | 语义 |
|---|---|
| `field_id` | 域代码绑定稳定 ID，不是 JSONPath |
| `value_type` | `boolean/integer/decimal/date/datetime/enum/text/identifier` |
| `data_class` | `public/business_internal/personal_identifier/employee_identifier/transaction_identifier/financial_account/financial_value/contact/credential_or_secret/free_text_sensitive/unknown` |
| `extractor` | 代码函数，从 typed record 取值；配置不能指定 |
| `user_visible_by_code` | 业务服务授权后 Agent 本地视图的代码上限 |
| `model_candidate_by_code` | 默认 false；是否可进入后续交集 |
| `required_for_user_result` | 是否构成最小有效结果 |
| `allowed_user_transforms` | 有限枚举子集 |
| `allowed_model_transforms` | 有限枚举子集 |
| `enum_values` | 仅 enum 类型可有，代码冻结 |

`unknown`、`credential_or_secret` 和 `free_text_sensitive` 的模型候选必须为 false。其他分类是否允许由域 L2逐字段确认，不能由分类名称自动放行。

## 9. 详细功能与核心处理流程

### 9.1 固定执行顺序

```text
1. 核心校验候选、参数并 claim 单动作
2. 域 validator 生成强类型 TInput
3. 动作设置再次收紧分页/时间/过滤/排序
4. 校验 CapabilityExecutionContext 与 user token
5. request_mapper 构造一个 code-bound 只读请求
6. UserJwtBusinessHttpClient 发出至多一个请求
7. response_normalizer 映射 typed BusinessServiceResult
8. user projector 形成最小有效 BusinessUserResult
9. egress projector 计算模型字段交集并执行有限转换
10. handler 构造合法 CapabilityResult
```

步骤 7 之前不能构造用户/模型字段，步骤 8 不能把投影当作业务授权，步骤 9 不能回看原始 wire response。

### 9.2 类型化业务结果

`BusinessServiceResult[TRecord]` 是有限 tagged union：

| kind | 必填 | 禁止 | 公共映射 |
|---|---|---|---|
| `records` | 非空 typed records、受控分页/覆盖元数据 | failure/raw response | 进入 user projection |
| `no_result` | 确认契约允许的空元数据 | records/failure | `no_result` |
| `invalid_argument` | code | records/body | `invalid_argument` |
| `unauthenticated` | code | records/body | `unauthenticated` |
| `forbidden` | code | records/body | `forbidden` |
| `timeout` | code | records/body | `timeout` |
| `downstream_failure` | code | records/body | `downstream_failure` |

unknown JSON fields、超界 body、类型错误、缺必需 wire 字段或业务 2xx 未满足契约均为 `downstream_failure/business.invalid_response`。域 L2 可根据已确认契约选择“拒绝未知字段”或“显式忽略且不进入 typed record”；首期默认严格拒绝，放宽需域 L2 证明兼容性且仍保证未知字段零投影。

### 9.3 用户结果投影

```text
用户结果字段
  = 本次授权响应中实际存在的已声明字段
    ∩ definition.user_visible_by_code
    ∩ settings.user_result_field_ids
```

投影顺序：

1. 只迭代 definition 字段，不反射/遍历原始 DTO 全部属性。
2. 对每条 record 按 definition 顺序提取。
3. 应用配置选择且代码允许的 user transform。
4. 验证 required fields/等价 invariant。
5. 构造有界 `BusinessUserResult`，保留分页、截断和覆盖语义。

已有 record 在步骤 3/4 后无法形成最小有效结果时返回 `downstream_failure/business.minimum_user_result_not_met`；不能变为 `no_result` 或空 `success`。

### 9.4 事务与一致性边界

本流程不写数据库、消息、索引或缓存，不适用跨资源事务、补偿、CAS 或分布式锁。单请求一致性来自冻结 action definition/settings、一次 HTTP 调用、不可变 typed result 和取消/截止后拒绝迟到结果。重复用户请求是新查询，不承诺跨请求快照一致、幂等结果或自动去重。

## 10. JWT、Authority 与业务最终授权

### 10.1 用户 JWT 客户端原则

- client 方法必须显式接收 `OpaqueUserToken`，不能读取进程全局 token 或创建 service token。
- `reveal_for_outbound()` 只在 header 构造的最小作用域调用一次；值只进入 `Authorization: Bearer ...`。
- token 不进入 body、query、URL、异常、repr、指标或日志。
- 缺 token/非法 context 时在创建 HTTP request 前返回 `unauthenticated/business.missing_user_token`。
- 每个动作一次请求、无 retry；重定向关闭，防 token 转发到非代码绑定 host。
- base service endpoint 来自启动配置与代码 service key；path/method 只由域 action definition 提供。

### 10.2 role→Authority 消费契约

业务查询的目标可观察语义：

| JWT role claim | 统一映射预期 | 业务服务结果 |
|---|---|---|
| `["ADMIN"]` | `ROLE_ADMIN` | Employee/Transaction 首批动作允许 |
| `["VIEWER"]` | `ROLE_VIEWER` | Employee/Transaction 首批动作允许 |
| `["ADMIN","VIEWER"]` | 两个去重 Authority | 允许，不因顺序变化 |
| 缺失/null/空集合/空白元素 | 无有效 Authentication/Authority | 拒绝，业务方法不执行 |
| 字符串而非集合、嵌套对象、非字符串 | 格式错误 | 拒绝 |
| 未知 role 或大小写漂移 | 不产生宽松 Authority | 整个业务查询失败关闭 |

这是一份消费和集成验收预期，不是本文对 `common-security` 私有类或 converter 实现的定义。`dylan` 通过 JWT 中的 ADMIN 获权，用户名本身不得出现在 Adapter、业务服务授权规则或配置中。

### 10.3 最终授权与响应可见性

业务服务必须在实际动作入口：

1. 重新验证 JWT 签名、有效期和 `token_type=user`。
2. 消费统一 Authority，并允许首批 `ROLE_ADMIN/ROLE_VIEWER`。
3. 对其他/缺失/错误 Authority 返回 403，方法和数据访问调用为零。
4. 保证 2xx 响应记录、字段和数据范围符合当前用户的本域可见性契约。

Adapter 不解析 role、不维护允许角色、不补做行/字段授权。只要第 4 点没有提供方契约和测试证据，真实动作必须保持禁用，即使 Adapter 能删除字段也不能关闭门禁。

## 11. 字段交集、有限转换与模型出域

### 11.1 模型字段交集

```text
模型字段
  = 本次授权响应中实际存在的已声明字段
    ∩ definition.user_visible_by_code
    ∩ settings.user_result_field_ids
    ∩ definition.model_candidate_by_code
    ∩ settings.model_field_ids
    ∩ GlobalBusinessEgressPolicy
```

任一未分类、unknown、额外、策略缺失或冲突字段被拒绝。模型字段必须是最终用户结果字段的子集；不得从原始 wire response 重新取值。

### 11.2 有限转换枚举

| transform ID | 输入 | 输出 | 精确规则 | 失败 |
|---|---|---|---|---|
| `identity_scalar` | bool/int | 同类型 | 仅有限整数和布尔；不接受 string/float | 拒绝整个 safe payload |
| `bounded_text` | string | string | NFC、无控制符、1～全局上限；字段必须代码标记 model text allowed | 同上 |
| `mask_keep_last4` | string | string | 至少 5 个 Unicode code point；输出固定 `"***"`+末 4 位 | 同上 |
| `date_only` | date/datetime/严格 ISO string | ISO 公历日期字符串（四位年、两位月、两位日） | 不推断缺失时区、不改日期 | 同上 |
| `decimal_2` | `Decimal`/canonical decimal string | string | `ROUND_HALF_UP` 到 2 位；禁止 binary float、NaN/Infinity | 同上 |
| `enum_code` | string enum | string | 必须精确位于字段代码 allowlist | 同上 |

不提供 `drop`、脚本、正则替换、表达式、动态模板或任意参数；字段不出域通过集合排除完成。转换后的值重新执行类型、长度、JSON 深度和 payload 字节校验。

### 11.3 模型安全载荷

```json
{
  "schema_version": 1,
  "policy_version": "business-egress-v1",
  "config_snapshot_id": "non-sensitive-snapshot-id",
  "facts": [
    {
      "fact_id": "fact-0001",
      "value_type": "enum",
      "value": "ACTIVE",
      "transform_id": "enum_code",
      "source": {
        "record_ref": "record-0001",
        "field_id": "code-bound-field-id"
      }
    }
  ],
  "presentation": {
    "mode": "business_facts",
    "action_id": "code-bound-action-id"
  },
  "coverage": {
    "truncated": false
  }
}
```

约束：

- `fact_id`、`record_ref` 按请求内稳定顺序生成，不由值哈希，不包含真实主键。
- facts 顺序按 record 再 field definition 顺序，最多 `max_safe_facts`。
- `source.record_ref` 是请求内序号，`source.field_id` 必须在 action definition；value 已转换。
- `policy_version` 固定为代码策略版本，`config_snapshot_id` 来自非敏感规范化配置哈希；不得由模型或动作参数覆盖。
- `presentation` 只能含有限枚举和 action ID，不含 Prompt/指令。
- 原始业务 ID 只有经域字段定义、交集和转换后才能作为普通 fact value。
- safe payload 不包含 JWT、role、subject、URL、HTTP 状态、原始响应、异常或配置正文。
- 当前请求绑定由同一调用栈、`ModelCallContext` 和请求内 fact/record 序号保证；不得为此把 request ID 或 subject 写入 safe payload。

### 11.4 业务文本隔离与事实绑定

L2_00_02 仍使用固定 system instruction 与 user JSON 分离。业务 `bounded_text` 值一律视为不可信数据，即使包含“忽略规则”“调用工具”“显示更多字段”等文本也不能改变动作、权限、Prompt 或调用链。

`BusinessAnswerGroundingPolicy` 至少执行：

1. `used_fact_ids` 非空、去重且全部存在。
2. answer 中出现的 `[fact-NNNN]` 标记集合与 `used_fact_ids` 精确相同。
3. 每个事实性句子至少一个 fact 标记；只允许有限固定非事实前缀无标记。
4. answer 中所有数字、日期、百分比、枚举和标识 token 必须出现在该句引用 facts 的 canonical transformed values 中。
5. `unsupported_claims` 必须为空。
6. coverage.truncated=true 时回答不得声称“全部、唯一、完整、没有其他”等完整性结论。
7. 任一检查失败，丢弃整个候选回答并由 L2_00_02 映射 `invalid_output`；不得局部裁剪后返回。

该规则仍不能证明任意自然语言逻辑等价，因此域 L2 应优先允许枚举、日期、数值、短标签等可验证字段；`free_text_sensitive` 默认禁止外发。

### 11.5 出域判定

| 条件 | `CapabilityResult` |
|---|---|
| 用户结果有效、answer mode=structured_only | `success + not_applicable`，返回本地结构化结果 |
| 用户结果有效、模型允许且 facts 非空 | `success + allowed`，safe payload 非空 |
| 用户结果有效、全局禁用/字段全拒绝/冲突/转换失败 | `success + denied`，保留本地结果，回答模型零调用 |
| 本地结果本身未获准返回且模型也拒绝 | `model_egress_denied + denied`，LangGraph 丢弃领域结果 |
| 业务无数据 | `no_result + not_applicable` |

策略不确定时不得使用 `not_applicable` 伪装允许；`not_applicable` 只用于 code-bound structured-only 动作。

`success + denied` 必须使用 `ModelEgressResult(disposition=denied, policy_version=business-egress-v1, safe_payload=None, reason_code=<有限枚举>)` 且 `failure=None`。reason code 仅允许 `egress_disabled/no_model_fields/policy_conflict/transform_failed/payload_limit`。`model_egress_denied` 分支除同一 denied 结果外还必须带 `FailureDetail(code=business.egress_denied, source=policy)`，并由核心丢弃领域结果。

## 12. 失败、配置、安全与观测

### 12.1 错误码与调用方可见语义

| 触发 | 公共 status | failure code | source | 网络调用 |
|---|---|---|---|---:|
| arguments/配置边界非法 | `invalid_argument` | 域代码定义的 `*.invalid_arguments` | capability | 0 |
| user token/context 缺失 | `unauthenticated` | `business.missing_user_token` | capability | 0 |
| 业务 HTTP 401 | `unauthenticated` | `business.downstream_unauthenticated` | downstream | 1 |
| 业务 HTTP 403 | `forbidden` | `business.downstream_forbidden` | downstream | 1 |
| 明确契约 no data | `no_result` | 无 | 无 | 1 |
| HTTP 400 且域契约可证明为用户参数 | `invalid_argument` | 域有限 code | downstream | 1 |
| 未知 400/409/422、429、5xx、连接错误 | `downstream_failure` | `business.downstream_failure` 或 `business.rate_limited` | downstream | 1 |
| client deadline | `timeout` | `business.downstream_timeout` | downstream | 1 |
| 2xx body/字段/类型/大小非法 | `downstream_failure` | `business.invalid_response` | downstream | 1 |
| 有 record 但最小用户结果失败 | `downstream_failure` | `business.minimum_user_result_not_met` | capability | 1 |
| 模型字段拒绝/转换失败且本地结果有效 | `success` | 无 | 无 | 回答模型 0 |
| egress policy 缺失且本地结果不可返回 | `model_egress_denied` | `business.egress_denied` | policy | 回答模型 0 |

原始错误正文、业务 response、header、URL query、堆栈和敏感字段不得进入 `FailureDetail` 或普通日志。HTTP 404 是否是 no_result 必须由域公开契约明确；未确认时按 downstream failure。

### 12.2 全局公共配置

| 环境变量 | 默认 | 允许范围 | 生效/失败 |
|---|---:|---|---|
| `AGENT_BUSINESS_EGRESS_ENABLED` | `false` | true/false | 重启；false 时所有模型载荷 denied |
| `AGENT_BUSINESS_MAX_SAFE_FACTS` | `20` | 1～20 | 重启；只能降低 |
| `AGENT_BUSINESS_MAX_SAFE_PAYLOAD_BYTES` | `32768` | 4096～32768 | 重启；只能降低 |
| `AGENT_BUSINESS_MAX_TEXT_VALUE_CHARS` | `256` | 32～256 | 重启；只能降低 |
| `AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES` | `1048576` | 65536～1048576 | 重启；只能降低 |
| `AGENT_BUSINESS_MAX_FIELDS_PER_RECORD` | `32` | 1～32 | 重启；只能降低 |

`business-egress-v1` 是代码策略版本，不由环境覆盖。每动作设置由域 L2 定义精确键；全部设置与 action definitions 归一化后计算非敏感 `snapshot_id`，运行期只读。

### 12.3 业务敏感问题类别

向 L2_00_02 提供以下合成负向类别；不包含真实用户数据：

| 类别 | 代表性形态 | 预期 |
|---|---|---|
| `personal_identifier` | 校验合法的合成身份证/证件号 | DeepSeek transport 0 |
| `employee_identifier` | 合成员工编号与具体姓名组合 | transport 0，除非未来建立可验证最小化规则 |
| `transaction_identifier` | 合成交易/订单/消息 ID | transport 0 |
| `financial_account` | 合成银行卡/账户号 | transport 0 |
| `contact` | 合成手机号、邮箱或详细地址 | transport 0 |
| `credential_or_secret` | 密码、JWT、API key 形态 | transport 0 |
| `free_text_sensitive` | 含未分类个人/交易自由文本 | unknown/denied，transport 0 |
| `generic_business` | “查询员工列表支持哪些条件”等无具体实体问题 | 可进入全局允许判定，但不授予业务动作权限 |

### 12.4 权限、安全与审计设计

- 入口认证、role 映射、业务最终授权、Agent 字段收紧是连续但不同的控制点，不能互相替代。
- Adapter 不持有角色白名单或用户名例外；`admin/viewer` 只出现在外部契约测试预期。
- 业务 2xx 在真实集成门禁关闭前不能被假定为已满足响应数据可见性。
- 全局 egress disabled 是默认；未知字段/分类/策略/转换失败全部拒绝。
- 禁止日志：JWT/API key、subject/用户名、原始问题、身份证/员工/交易/账户/联系方式、完整响应、safe payload、模型回答和异常正文。
- 允许审计元数据：correlation/request ID、domain/action、config/policy version、阶段、status、HTTP status 类别、记录/字段/fact 数量、egress disposition、耗时。

### 12.5 状态、并发、容量与韧性

- 所有 action definition/settings/field registry 在启动时冻结；请求内只创建 typed input/result/view/payload。
- 每动作一次 HTTP；无 retry、熔断、缓存兜底、跨域降级或 service identity 切换。
- client timeout 取动作上限和总剩余 deadline 的较小值；剩余≤100ms 不连接。
- 取消后停止读取/解析响应，迟到结果不进入 user result 或 safe payload。
- 本文保留 client/handler 装饰接缝，未来韧性设计可包装一次调用，但必须由独立 L2 固定所有者、预算和重复语义。

### 12.6 可观测性

建议指标：

| 指标 | 有界标签 |
|---|---|
| `agent_business_action_total` | domain、action、status |
| `agent_business_http_duration_seconds` | domain、action、outcome |
| `agent_business_projection_total` | domain、action、projection=`user/model`、outcome |
| `agent_business_egress_total` | domain、action、disposition |
| `agent_business_grounding_total` | domain、action、outcome |

不得以 user/subject、字段 ID、业务值、URL、error message 作为指标标签。

## 13. 组合根、实现落点与关键签名

### 13.1 组合根与启动选择

1. 加载 `BusinessGlobalSettings` 并冻结。
2. 由 Employee/Transaction provider 分别提供代码 action definitions 和原始 action config。
3. 公共 validator 对全部启用动作执行配置子集、必需字段、转换、契约版本和依赖校验。
4. 某一启用动作或域配置无效时，整个 Runtime readiness=false；不静默保留另一域形成半有效部署。
5. 全域禁用是合法状态：不创建业务客户端、不注册业务动作，但不影响 Knowledge/core 独立验证。
6. 对有效启用动作创建域 client/handler 并显式提交核心 registry。
7. common module 不扫描模块、不读取 entry point、不自动发现第三方 Adapter。

### 13.2 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置项 | 责任 | 必要性 | 设计规则 |
|---|---|---|---|---|---|---|---|
| `IMPL-BQCOM-001` | 建议新增 | Python contracts | `agent-runtime/src/agent_runtime/business/contracts.py` | action/field/settings/service result/user result/fact 类型和 Protocol | 公共稳定语义 | 防两域漂移 | `DR-BQCOM-001/005/006/007/010/012/015` |
| `IMPL-BQCOM-002` | 建议新增 | Python config | `agent-runtime/src/agent_runtime/business/settings.py` | global settings、action settings validator、snapshot | 配置只收紧 | 防动态/半有效配置 | `DR-BQCOM-002/013` |
| `IMPL-BQCOM-003` | 建议新增 | Python HTTP/JWT | `agent-runtime/src/agent_runtime/business/http_client.py` | `UserJwtBusinessHttpClient`、bounded response | JWT 单次只读调用 | 禁 service fallback | `DR-BQCOM-003/005/012/014` |
| `IMPL-BQCOM-004` | 建议新增 | Python result | `agent-runtime/src/agent_runtime/business/result_mapping.py` | tagged result 校验/公共失败映射 | 状态真实性 | 区分 no_result/失败 | `DR-BQCOM-006/007/012` |
| `IMPL-BQCOM-005` | 建议新增 | Python projection | `agent-runtime/src/agent_runtime/business/user_projection.py` | `BusinessUserResultProjector` | 用户字段交集/最小结果 | 防空 success | `DR-BQCOM-005/007/008` |
| `IMPL-BQCOM-006` | 建议新增 | Python transform | `agent-runtime/src/agent_runtime/business/transforms.py` | enum、`BusinessTransformRegistry` | 六个有限转换 | 模型前最小化 | `DR-BQCOM-009` |
| `IMPL-BQCOM-007` | 建议新增 | Python egress | `agent-runtime/src/agent_runtime/business/egress.py` | `BusinessEgressProjector` | 模型交集/facts/决定 | 默认拒绝 | `DR-BQCOM-008/009/010/018` |
| `IMPL-BQCOM-008` | 建议新增 | Python grounding | `agent-runtime/src/agent_runtime/business/grounding.py` | `BusinessAnswerGroundingPolicy` | 事实/coverage 验证 | 防无依据回答 | `DR-BQCOM-010/011` |
| `IMPL-BQCOM-009` | 建议新增 | Python validation | `agent-runtime/src/agent_runtime/business/validation.py` | definition/settings/result validators、finite errors | 启动/运行失败关闭 | 集中无业务语义不变量 | `DR-BQCOM-002/006/007/012/013` |
| `IMPL-BQCOM-010` | 建议新增 | Python provider support | `agent-runtime/src/agent_runtime/business/provider.py` | `BusinessSupportFactory` | 向域 provider 提供冻结原语 | 不自动注册动作 | `DR-BQCOM-013/015/016` |
| `IMPL-BQCOM-011` | 建议新增 | Python composition | `agent-runtime/src/agent_runtime/bootstrap.py` | 显式接收 Employee/Transaction providers | 组合根接入 | 可扩展不侵入 core | `DR-BQCOM-013/015` |
| `IMPL-BQCOM-012` | 建议新增 | Contract fixture | `agent-runtime/tests/contract/business/authority_expectations.json` | role/Authority/allow-deny 场景 | 外部安全消费证据 | 不定义 Java 实现 | `DR-BQCOM-004/016` |
| `IMPL-BQCOM-013` | 建议新增 | Security fixture | `agent-runtime/tests/fixtures/business_sensitive_questions.json` | 合成敏感问题类别 | 给 L2_00_02 负向测试 | 防遗漏问题出域 | `DR-BQCOM-017` |

### 13.3 Python 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| 建议新增：`business.settings.BusinessSettingsValidator.validate` | `def validate(self, definitions: Sequence[BusinessActionDefinition[Any,Any,Any,Any]], raw: BusinessConfigurationSource) -> BusinessConfigurationSnapshot` | ID/维度/子集/上限/required fields/transform/依赖 | 冻结 snapshot；配置错误只含稳定 code | 无 I/O；composition root |
| 建议新增：`business.http_client.UserJwtBusinessHttpClient.execute` | `async def execute(self, *, request: BusinessHttpRequest, user_token: OpaqueUserToken, timeout_s: float, cancellation: CancellationSignal) -> BoundedBusinessHttpResponse` | code-bound endpoint/method、token/timeout/body 上限、redirect off | bounded response 或 typed transport failure | 一次 HTTP、无 retry；域 client |
| 建议新增：`business.user_projection.BusinessUserResultProjector.project` | `def project(self, *, definition: BusinessActionDefinition[...,TRecord], settings: BusinessActionSettings, result: AuthorizedRecordBatch[TRecord]) -> BusinessUserResult` | 只迭代 definition、apply user transforms、required invariant | 冻结 user result；失败 typed code | 纯函数；域 handler |
| 建议新增：`business.transforms.BusinessTransformRegistry.apply` | `def apply(self, *, transform_id: BusinessFieldTransform, definition: BusinessFieldDefinition[TRecord,TValue], value: TValue) -> JsonScalar` | 保留字段强类型，校验类型/字段 allowlist/全局上限；Decimal/date 不先降为 JSON | canonical safe JSON scalar；失败不含原值 | 纯函数；两个 projectors |
| 建议新增：`business.egress.BusinessEgressProjector.project` | `def project(self, *, definition: BusinessActionDefinition[Any,Any,Any,Any], settings: BusinessActionSettings, user_result: BusinessUserResult, policy: GlobalBusinessEgressPolicy) -> BusinessEgressProjection` | 字段交集、转换、facts/bytes/count | allowed/denied/not_applicable 与 payload | 纯函数；域 handler |
| 建议新增：`business.grounding.BusinessAnswerGroundingPolicy.validate` | `def validate(self, *, safe_payload: JsonObject, answer: str, used_fact_ids: tuple[str, ...], unsupported_claims: tuple[str, ...]) -> GroundingDecision` | schema/fact/marker/token/coverage | accepted 或有限 reason | 纯函数；L2_00_02 registry |
| 建议新增：`business.provider.BusinessSupportFactory.build` | `def build(self, *, global_settings: BusinessGlobalSettings, definitions: Sequence[BusinessActionDefinition[Any,Any,Any,Any]], config: BusinessConfigurationSource) -> BusinessSupportSnapshot` | 全部启动不变量 | 冻结 support 或启动失败 | 创建无外部连接对象；domain providers |

### 13.4 Java 边界关键方法适用性

本文不建议新增或修改 Java 方法，因为共享安全和业务授权实现不属于当前授权范围。后续提供方设计必须至少覆盖：

- JWT decoder/converter 如何把 `role` 集合映射为 Authority。
- Employee/Transaction 精确动作入口如何验证 `ROLE_ADMIN/ROLE_VIEWER`。
- 允许/拒绝时业务方法和数据访问调用次数。
- 2xx 响应数据可见性契约。

精确 Java 类路径/方法由 `L2_02_01/02` 或经授权的共享安全详细设计在核实实现后定义，本文只以 5.1 已存在触点和 10.2 可观察行为作为消费依据。

## 14. 测试与验证设计

### 14.1 测试定义

| 测试编号 | 状态 | 设计规则 | 层级 | 建议路径/用例 | Fixture、动作 | 关键断言 | 失败信号 |
|---|---|---|---|---|---|---|---|
| `TEST-BQCOM-001` | 建议新增 | `DR-BQCOM-001/015` | Unit/Contract | `agent-runtime/tests/unit/business/test_action_definition.py` | 两个 fake 域、重复/动态字段/端点 | definition 冻结；common 无域字段；动作唯一 | 动态 action/URL 或域耦合 |
| `TEST-BQCOM-002` | 建议新增 | `DR-BQCOM-002/013` | Unit | `agent-runtime/tests/unit/business/test_settings.py` | 各维度边界±1、未知/重复字段、删除 required、非法 transform | 只允许子集/更小值；任一 enabled 错误不就绪 | 配置扩权或半有效启动 |
| `TEST-BQCOM-003` | 建议新增 | `DR-BQCOM-003/014` | Unit/HTTP | `agent-runtime/tests/unit/business/test_user_jwt_http_client.py` | 缺 token、fake service token provider、redirect、timeout、cancel | 缺 token调用0；只有原 user JWT header；无 retry/redirect | service fallback、token 泄露或多调用 |
| `TEST-BQCOM-004` | 建议新增 | `DR-BQCOM-004/005/016` | Cross-service Contract | `agent-runtime/tests/contract/business/test_authority_consumption.py` | 10.2 全矩阵；业务服务 spies | ADMIN/VIEWER 允许，缺失/未知/格式错拒绝且业务方法0；Adapter 不解析 role | Authority 漂移或 Adapter 白名单 |
| `TEST-BQCOM-005` | 建议新增 | `DR-BQCOM-006/012` | Unit | `agent-runtime/tests/unit/business/test_service_result_mapping.py` | 2xx records/empty、401/403/404/400/429/5xx/timeout/unknown body | 状态矩阵精确；404 未确认不变 no_result | 401/403混淆或失败变 no_result |
| `TEST-BQCOM-006` | 建议新增 | `DR-BQCOM-007/008` | Unit | `agent-runtime/tests/unit/business/test_user_projection.py` | records、额外字段、缺 required、投影后空 | extra零进入；必需失败 downstream；不制造 no_result/空 success | 宽字段或状态漂移 |
| `TEST-BQCOM-007` | 建议新增 | `DR-BQCOM-008/009/018` | Unit | `agent-runtime/tests/unit/business/test_egress_projection.py` | 字段交集、六转换、类型错、payload超界、global disabled | model⊂user；未知/转换失败模型调用0；本地结果保留 | 原始字段外发或模型自行脱敏 |
| `TEST-BQCOM-008` | 建议新增 | `DR-BQCOM-010/011` | Unit | `agent-runtime/tests/unit/business/test_grounding.py` | fact markers、数字/日期/enum/ID、unsupported、truncated | 无依据候选整体拒绝；合法引用通过 | 只核 fact ID 不核事实 token |
| `TEST-BQCOM-009` | 建议新增 | `DR-BQCOM-003/012/014` | Integration with fake server | `agent-runtime/tests/integration/business/test_failure_and_cancellation.py` | 迟到 body、断连、敏感异常、重复请求 | 当前请求一次调用；取消后丢弃；日志无敏感值 | 后台结果或原始异常泄露 |
| `TEST-BQCOM-010` | 建议新增 | `DR-BQCOM-013/014` | Architecture | `agent-runtime/tests/architecture/test_business_common_boundaries.py` | import graph、dependency/storage/retry scan | common 无域/SDK/DB/message/role auth；无 retry | 动态平台、持久化或反向依赖 |
| `TEST-BQCOM-011` | 建议新增 | `DR-BQCOM-001/015` | Extensibility | `agent-runtime/tests/contract/business/test_fake_third_domain.py` | 新增 test-only `sample.read` definition/provider | 只新增 fixture/provider；core/common/已有域源不改 | 扩展要求改 core/common |
| `TEST-BQCOM-012` | 建议新增 | `DR-BQCOM-010/011` | Model integration with spy | `agent-runtime/tests/integration/business/test_business_text_is_data.py` | fact text 含注入语句、模型越界回答 | 不触发工具/第二动作/权限变化；越界答案拒绝 | 文本影响控制语义 |
| `TEST-BQCOM-013` | 建议新增 | `DR-BQCOM-017` | Security contract | `agent-runtime/tests/contract/business/test_sensitive_question_scenarios.py` | 12.3 合成问题+model spy | 每个敏感类别 transport 0；generic case只通过输入闸门不等于授权 | 具体标识或凭证外发 |

### 14.2 关键权限与出域场景

| 场景 | 业务 HTTP | 用户结果 | 回答模型 | 公共结果 |
|---|---:|---|---:|---|
| 缺 user JWT | 0 | 无 | 0 | unauthenticated |
| ADMIN/VIEWER 且业务允许 | 1 | 按字段交集 | 0或1 | success/no_result |
| unknown/missing role | 1 到达业务入口，业务方法/数据访问0 | 无 | 0 | forbidden/unauthenticated（按外部契约） |
| 业务 403 | 1 | 无 | 0 | forbidden |
| records 存在但 required field 缺失 | 1 | 无 | 0 | downstream_failure |
| 用户结果有效、egress disabled | 1 | 有 | 0 | success+denied |
| 业务文本含指令 | 1 | 受控 | 至多1 | 只能作为 fact；越界回答 invalid_output |

### 14.3 验证定义

| 验证编号 | 工作目录/前置 | 命令或人工步骤 | 验证范围与充分性 | 预期结果 | 当前执行状态 |
|---|---|---|---|---|---|
| `VAL-BQCOM-001` | `D:\codex`；本文/validator 可读 | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md --root D:\codex --strict` | 只证明文档结构、追踪、引用和质量规则 | 0 errors、0 warnings | 已执行：0 errors、0 warnings（2026-07-25） |
| `VAL-BQCOM-002` | 未来 `D:\codex\agent-runtime`；common unit tests 已创建 | `python -m pytest tests/unit/business -q` | 证明配置、结果、字段、转换和 grounding 纯逻辑 | 全部通过 | 未执行：代码/测试不存在且未授权 |
| `VAL-BQCOM-003` | 未来 `D:\codex\agent-runtime`；contract/integration/architecture tests 已创建 | `python -m pytest tests/contract/business tests/integration/business tests/architecture/test_business_common_boundaries.py -q` | 证明 JWT、扩展、模型/文本隔离和边界；不证明真实业务授权 | 全部通过 | 未执行：代码/测试不存在且未授权 |
| `VAL-BQCOM-004` | 未来 Python 工程 | `python -m compileall -q src tests`、`python -m mypy --strict src tests`、`python -m pip check` | 证明泛型/签名/依赖一致，须与行为测试联合 | 三条无错误 | 未执行：工程不存在 |
| `VAL-BQCOM-005` | 当前/未来 Java 提供方、真实有效配置和角色 token 可用 | `mvn -pl common-security,employee-service,mq-procedure-service -am test`，再执行两域允许/拒绝/响应可见性集成矩阵 | 证明外部 Authority 与最终授权，不由 Python测试替代 | ADMIN/VIEWER 允许，其余拒绝；成功数据范围符合契约 | 未执行：提供方设计/实现未授权且当前缺口存在 |

## 15. 发布、迁移与回滚

- common 模块和两个 Adapter 均为新增；本文不产生数据库、索引、消息或业务数据迁移。
- 全局业务模型出域默认关闭；两个真实业务域动作默认禁用，先用合成 fake 实现公共切片。
- 域 L2 完成前只允许 test-only fake definitions，不得把候选端点或字段写成已确认事实。
- Authority/业务最终授权证据未完成时，真实动作即使客户端可达也必须保持禁用。
- 回滚优先禁用对应域动作并重启 Runtime；出域不确定时回滚为 `AGENT_BUSINESS_EGRESS_ENABLED=false`。
- 若共享安全/业务契约后续变化，必须同步提供方、域 Adapter、配置和 consumer/provider tests；不能只以配置兼容。
- 无持久业务状态，回滚不需要数据补偿；在途请求明确失败，不自动续跑。

## 16. 风险、待确认事项与门禁

### 16.1 风险与待确认事项

| 编号 | 类型 | 证据缺口或风险 | 触发场景 | 影响 | 建议 | 是否阻塞/需授权 |
|---|---|---|---|---|---|---|
| `RISK-BQCOM-001` | 直接依赖 | L2_00_01 v0.4 与 L2_00_02 均未独立完成本轮评审 | P3 实施 | 公共 context/result/grounding 漂移 | 先完成直接依赖复评/评审 | 阻塞本切片实施 |
| `RISK-BQCOM-002` | Authority | 当前无统一 role converter，有效运行配置未证明 | 真实业务调用 | ADMIN/VIEWER误拒绝或越权 | 外部权威设计并做端到端矩阵 | 阻塞真实两域 |
| `RISK-BQCOM-003` | 最终授权 | 当前守卫只校验 user token，部分接口可能无专用守卫 | 真实启用 | 任意认证用户访问数据 | 域 L2/业务服务补齐方法授权和响应可见性 | 阻塞真实两域 |
| `RISK-BQCOM-004` | 服务身份 | 误复用 Feign fallback 或未来 Python通用 client | 缺 user context | 绕过用户权限 | 专用 client 和服务 token 零调用测试 | 阻塞实施测试 |
| `RISK-BQCOM-005` | 字段分类 | 精确字段/转换尚未由域 L2确认 | 真实业务结果外发 | 敏感数据泄露 | 保持 global egress off，域逐字段确认 | 阻塞真实出域 |
| `RISK-BQCOM-006` | 自然语言验证 | fact marker/token 校验不能证明复杂关系完全正确 | 模型总结多记录关系 | 仍可能语义过度概括 | 域 L2限制字段/回答模板，失败使用结构化结果 | 阻塞效果结论；不阻塞公共 fake |
| `RISK-BQCOM-007` | 兼容性 | strict unknown-field 可能因提供方新增字段失败 | 业务服务兼容扩展 | Agent downstream failure | 域 L2选择严格拒绝或显式忽略并做契约测试 | 不阻塞本文；域 L2必须选择 |
| `RISK-BQCOM-008` | 过度抽象 | common generic 被扩展为动态 Adapter | 新第三域需求 | 责任/安全边界丢失 | 保持代码 definition+显式 provider；架构测试 | 阻塞相关变更评审 |

### 16.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 证据/权威来源 | 责任方 | 最晚阶段 | 验证者与方法 | 状态 | 未关闭时允许/禁止动作 | 模拟或替代路径 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BQ-GATE-001` | design_decomposition | L1_02→本文 | 编写本文 | L1_02 v0.2 五轮评审通过 | L1_02 14.2 | 项目维护者/独立评审方 | 本文前 | 核对评审记录 | Closed | 允许本文；不授权代码 | 不适用 |
| `BQ-GATE-002` | slice_implementation | 本文 business common 代码/测试切片 | 创建 common contracts/settings/client/projection/grounding 代码和测试 | 本文独立评审可实施；直接依赖稳定；用户明确实施授权 | 本文评审与追踪 | 项目维护者 | P3 common 实施前 | 独立设计评审 | Open | 允许文档/fake推演；禁止目标代码实施/完成声明 | 合成纯函数样例 |
| `CR-GATE-003` | integration | 业务敏感问题进入 DeepSeek | 发送具体身份/交易/账户问题 | L2_00_02 输入策略及 12.3 全部零调用场景通过 | 模型 L2/Provider spy | 项目维护者/模型方 | 首次敏感问题联调前 | 负向测试 | Open | 只允许本地 selector/fake；禁止敏感外发 | generic synthetic question |
| `SA-GATE-004` | integration | Employee 真实动作 | 启用 Employee | 动作/接口/字段确认；Authority、ADMIN/VIEWER、响应可见性和契约测试通过 | auth/common-security/employee/L2_02_01 | 项目维护者/提供方 | Employee P4 | 跨服务矩阵 | Open | 公共/Employee fake 可继续；禁止真实动作 | fake employee provider |
| `SA-GATE-005` | integration | Transaction 真实动作 | 启用 Transaction | 动作/接口/字段确认；Authority、ADMIN/VIEWER、聚合写入不可达和契约测试通过 | auth/common-security/transaction/L2_02_02 | 项目维护者/提供方 | Transaction P4 | 跨服务矩阵 | Open | 公共/Transaction fake 可继续；禁止真实动作 | fake transaction provider |
| `SA-GATE-006` | integration | 真实业务结果进入 DeepSeek | 外发 Employee/Transaction 数据 | 字段交集、有限转换、facts/grounding、未分类/冲突关闭和模型零调用通过 | 三份业务 L2、L2_00_02 | 项目维护者/域/模型方 | 首次真实数据外发前 | field matrix/model spy | Open | 允许合成 facts；禁止真实业务载荷 | synthetic safe payload |

### 16.3 需要后续授权的动作

- 对本文执行独立正式评审、状态变更或关闭 `BQ-GATE-002`。
- 创建/修改任何 Agent Python 代码、配置、测试或依赖。
- 修改 `auth-service`、`common-security`、Employee/Transaction Java 类、配置、测试或公共契约。
- 确认并实现两个域精确动作、字段、端点及角色方法授权。
- 使用真实用户 JWT、真实业务数据或外部模型联调。

## 17. 内部自检记录

作者自检只用于改善 Draft，不构成独立评审、Approved、实施授权或门禁关闭证据。

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-25 | 0 | 4 | 4 | 8 | 无 | 修复共享安全权威越界、投影替代授权、空成功、服务 token 兜底、动态配置和业务文本指令风险 |
| 2 | 2026-07-25 | 0 | 2 | 2 | 4 | 无 | 固定六个转换、facts/marker grounding、半有效 Runtime 启动策略和外部 Authority 消费边界 |
| 3 | 2026-07-25 | 0 | 2 | 2 | 4 | 无 | 修复 domain 扩展耦合、transform 类型丢失及 safe payload 对齐问题，固定 denied 组合；严格校验通过 |

## 18. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] 公共类型不含 Employee/Transaction 精确字段、端点或业务规则。
- [x] 动作 definition、配置维度、最小有效用户结果和状态语义明确。
- [x] JWT 原样透传、零服务身份兜底、Authority 消费和业务最终授权边界明确。
- [x] 用户/模型字段交集、六个转换、facts envelope 和 grounding 明确。
- [x] Python 模块、关键函数、输入输出、错误、副作用和消费者明确。
- [x] Java 当前类/方法触点与本文不修改边界明确。
- [x] 配置默认值、上限、启动失败、冻结和回滚明确。
- [x] 权限、安全、审计、取消、无重试/无持久化和外部门禁明确。
- [x] 作者自检无遗留 Blocker/Major。
- [x] `validate_detailed_design.py --strict` 已通过；该结果仅是确定性文档证据。
- [ ] 独立正式评审通过并关闭本切片 `BQ-GATE-002`。

## 19. 当前结论

- 本文版本：v0.1。
- 文档状态：Draft。
- 评审状态：未执行独立正式评审。
- 实施状态：未实施。
- 生效状态：未生效。
- 是否可作为实现依据：否；`BQ-GATE-002`、`SA-GATE-004/005/006` 均为 Open。
- 确定性文档校验：已通过，0 errors、0 warnings；不替代独立正式评审或外部权限证据。
- 当前只允许文档、合成契约和 fake 推演；不允许修改共享安全/业务服务、启用真实动作或外发真实业务数据。
