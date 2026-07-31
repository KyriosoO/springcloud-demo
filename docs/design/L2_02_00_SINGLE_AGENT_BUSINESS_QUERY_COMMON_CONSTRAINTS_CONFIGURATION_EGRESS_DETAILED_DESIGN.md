# [L2_02_00] 单体 Agent 业务查询公共约束、配置与出域详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent 业务查询公共约束、配置与出域详细设计 |
| 文档标识 | `SA-L2-BUSINESS-COMMON-001` |
| 文档编号 | `L2_02_00` |
| 文档路径 | `docs/design/L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 五轮独立评审—修复—复核及第三批聚焦一致性复核已通过，`REV-BQCOM-001`～`022` 全部关闭 |
| 当前版本 | v0.3 |
| 日期 | 2026-07-31 |
| 适用范围 | Python `agent-runtime` 内 Employee/Transaction Adapter 共用的代码绑定动作原语、强类型配置收紧、用户 JWT 透传、统一 Authority 外部契约消费语义、类型化业务结果、最小有效用户结果、字段交集、有限转换、模型安全载荷、事实绑定、失败矩阵、组合根与公共测试替身 |
| 上位文档 | [`REQ_00`](../REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md) v1.3；[`L0_00`](L0_00_SINGLE_AGENT_ARCHITECTURE.md) v0.5；[`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.2（已评审/已通过，`BQ-GATE-001` 已关闭） |
| 直接依赖 | [`L2_00_01`](L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md) v0.4（Approved）的能力 API、JWT wrapper 和公共结果；[`L2_00_02`](L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md) v0.4（Approved）的 safe payload/grounding 接缝 |
| 下位/后续契约 | [`L2_02_01`](L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v0.3 Approved；[`L2_02_02`](L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v0.2 Approved |
| 外部契约 | `auth-service` 用户 JWT；`common-security` role→Authority；`employee-service`、`mq-procedure-service` 公开只读查询契约 |
| 实现基线 | 目标 `agent-runtime` 业务公共模块及两个 Adapter 均不存在；当前 JWT 已签发 `role` 集合，统一 Authority 映射和两域动作级最终授权尚未具备 |
| 是否可作为实现依据 | 否，本文设计已 Approved，但本切片 `BQ-GATE-002` 尚未获得实施授权并保持 Open；真实业务授权/出域门禁也仍为 Open |
| 当前允许实施范围 | 本文编写、自检、合成 DTO/字段/权限矩阵和不访问真实服务的公共 fake 推演 |
| 当前禁止动作 | 创建或修改 Agent/Java 代码、配置、测试、公共契约；新增业务接口；启用真实 Employee/Transaction；发送真实业务数据到 DeepSeek；关闭任何门禁 |
| 修改权限 | 本轮用户已授权第三批 L2 评审与必要直接关联文档原子同步，并授权 Git commit/push；代码、配置、Schema、外部契约和真实调用未获授权 |
| 维护责任人 | 项目维护者（个人开发者，姓名未在需求中指定） |

> 本文只定义两个业务域可以复用的无业务字段语义原语，不列出 Employee/Transaction 精确动作、端点、请求/响应字段或业务授权实现。公共原语不得演化为动态 HTTP Adapter、权限引擎或字段脚本平台。

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 执行第二批 L2 详细设计 | 创建业务动作/配置/结果/字段/出域公共结构，固定 JWT 无兜底、Authority 消费前提、有限转换、事实载荷、失败矩阵、组合根和实现/测试落点 |
| 2 | 2026-07-25 | 4～13、16～18 | 作者第 1 轮自检修复 | 收回共享安全提供方实现所有权，明确业务服务最终授权与响应可见性，补齐最小有效用户结果、业务文本数据隔离、回答事实绑定和配置失败关闭 |
| 3 | 2026-07-25 | 8、11、13～14、17～19 | 作者第 2～3 轮自检与严格校验修复 | 将 common domain ID 改为 provider 代码绑定而非硬编码两域，修正 transform 强类型输入，补齐 fact source、策略/配置快照及 denied 结果组合；严格校验通过 |
| 4 | 2026-07-25 | 1、5、8～16 | 独立评审第 1 轮修复 | 同步已批准直接依赖，消除动作身份双重权威，固化受控 HTTP 出站、有限下游失败和统一 grounding 接口 |
| 5 | 2026-07-25 | 7～9、12～14、18 | 独立评审第 2 轮修复 | 补齐 mapper/codec/normalizer/handler 的精确协议，以同一绝对截止覆盖调用与解析，固定配置快照及 client 原子创建/清理 |
| 6 | 2026-07-25 | 8、11～14、18 | 独立评审第 3 轮修复 | 固定 grounding 句段/token 算法和强类型转换，直接返回核心 egress 结果，删除当前不可达的模型专用失败分支并补齐全局策略 |
| 7 | 2026-07-25 | 8～10、12～14、18 | 独立评审第 4 轮修复 | 固定 records/user result JSON 和字节上限，消除 Authority 401/403 歧义，并把非 2xx 解释收归公共状态映射 |
| 8 | 2026-07-25 | 7～8、11、13～14、18～20 | 独立评审第 5 轮修复与终审 | 修正 grounding 重叠 token，固定动作约束/required 单一权威和 provider/support 接口；全量复核后批准设计，实施门禁保持 Open |
| 9 | 2026-07-31 | 1、5 | 第三批 L2 状态原子同步 | 将两个域 L2 更新为 v0.1 Draft/三轮内审完成；不改变公共设计、Approved 状态或开放门禁 |
| 10 | 2026-07-31 | 8.2/8.5/9.1/13/18～20 | Transaction 第4轮发现触发的聚焦一致性修订 | `decode_success` 显式接收同一次强类型 wire request，支持并发安全的请求—响应回显/结果上限校验；关闭 `REV-BQCOM-022`，保持 Approved 和所有实施/集成门禁 Open |
| 11 | 2026-07-31 | 1、5、18～20 | 第三批 L2 终审状态原子同步 | 同步 `REQ_00` v1.3、`L0_00` v0.5，并将 Employee/Transaction 更新为 v0.3/v0.2 Approved；确认两份域设计均显式消费 v0.3 codec 请求关联契约，所有实施/Provider/真实集成/出域门禁保持 Open |

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
| `REQ-BQCOM-009` | 失败状态和调用方可见语义稳定 | `401/403/no_result/invalid_argument/timeout/downstream_failure` 不混淆；模型拒绝保留有效本地结果，business common 不误发 `model_egress_denied`；原始错误不外泄 | REQ_00 异常要求；L1_02 7.7 |
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
| `REQ-BQCOM-003`、`CON-BQCOM-003` | JWT/业务调用 | `DR-BQCOM-003`、`DR-BQCOM-005` | outbound client、域 Adapter | Authorization header/一次调用 | `IMPL-BQCOM-003/014` | `TEST-BQCOM-003/009` | `VAL-BQCOM-002/005` |
| `REQ-BQCOM-004`、`CON-BQCOM-004` | Authority 消费 | `DR-BQCOM-004` | 外部安全权威/业务服务 | role claim→Authority 观察结果 | `IMPL-BQCOM-012` | `TEST-BQCOM-004` | `VAL-BQCOM-005` |
| `REQ-BQCOM-005`、`CON-BQCOM-005` | 响应/用户结果 | `DR-BQCOM-006`、`DR-BQCOM-007` | response mapper、projector | no_result/valid user result | `IMPL-BQCOM-004/005/014` | `TEST-BQCOM-005/006` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-006`、`CON-BQCOM-006` | 字段出域 | `DR-BQCOM-008`、`DR-BQCOM-009`、`DR-BQCOM-010`、`DR-BQCOM-018` | field registry、projector | 用户视图/safe payload | `IMPL-BQCOM-005/006/007` | `TEST-BQCOM-006/007` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-007` | 有限转换 | `DR-BQCOM-009` | transform registry | 转换值/拒绝 | `IMPL-BQCOM-006` | `TEST-BQCOM-007` | `VAL-BQCOM-002` |
| `REQ-BQCOM-008`、`CON-BQCOM-007` | 事实绑定 | `DR-BQCOM-010`、`DR-BQCOM-011` | safe payload、grounding policy | fact ID/候选回答 | `IMPL-BQCOM-007/008` | `TEST-BQCOM-008/012` | `VAL-BQCOM-003` |
| `REQ-BQCOM-009`、`CON-BQCOM-008` | 失败 | `DR-BQCOM-012` | client/mapper/handler | 公共 status/code/source | `IMPL-BQCOM-004/009/014` | `TEST-BQCOM-009` | `VAL-BQCOM-002/003` |
| `REQ-BQCOM-010`、`CON-BQCOM-011` | 模型输入负向场景 | `DR-BQCOM-017` | business fixture、L2_00_02 | 问题分类/零调用 | `IMPL-BQCOM-013` | `TEST-BQCOM-013` | `VAL-BQCOM-003` |
| `REQ-BQCOM-011`、`CON-BQCOM-009` | 生命周期 | `DR-BQCOM-014` | handler/client | 请求内只读状态 | `IMPL-BQCOM-003/009/014` | `TEST-BQCOM-009/010` | `VAL-BQCOM-003` |
| `CON-BQCOM-010` | 所有权边界 | `DR-BQCOM-015`、`DR-BQCOM-016` | common module、外部提供方 | 无越权实现 | `IMPL-BQCOM-010/012` | `TEST-BQCOM-004/011` | `VAL-BQCOM-003/005` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 交互契约 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|---|
| L1_02 v0.2 | parent | 细化公共 L2 唯一范围 | 架构边界、域隔离、门禁 | 业务查询公共语义 | 上位权威 | 只读 |
| L2_00_01 v0.4 | direct dependency | 消费 handler/context/result | 核心、注册、公共不变量 | `CapabilityResult`/JWT wrapper | 执行上下文 | 只读，Approved |
| L2_00_02 v0.4 | peer/direct dependency | 提供 business safe payload/grounding policy | Provider、通用 JSON output、失败映射 | facts envelope | 模型调用状态 | 只读，Approved |
| `auth-service` | external authority | 记录消费假设/测试场景 | 用户角色分配、JWT 签发 | `role` claim | 用户/角色 | 只读 |
| `common-security` | external authority | 记录 Authority 可观察要求和差距 | role→GrantedAuthority 统一映射 | Spring Security Authentication | 角色映射 | 只读；本文不设计修改 |
| `employee-service` | external/domain authority | 不定义具体动作 | Employee 最终授权和响应可见性 | 域 L2 固化 | Employee 数据/权限 | 只读 |
| `mq-procedure-service` | external/domain authority | 不定义具体动作 | Transaction 最终授权和响应可见性 | 域 L2 固化 | Transaction 数据/权限 | 只读 |
| L2_02_01 v0.3 / L2_02_02 v0.2 Approved | child designs | 提供公共原语 | 分别实例化动作、字段、端点、客户端和权限测试 | code-bound definition | 域动作/配置 | 五轮独立评审通过；实施/Provider/真实集成/出域门禁 Open |

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
| `BusinessRequestMapper` / `BusinessWireCodec` | 建议新增 Protocol | 把强类型输入与冻结设置映射为域 wire request，再编码/严格解码受控 HTTP | 动态 URL、网络、授权 | input/settings↔bounded HTTP |
| `BusinessResponseNormalizer` | 建议新增 Protocol | 把一个域响应映射为 tagged result | HTTP/角色/模型 | wire response→service result |
| `BoundBusinessActionHandler` | 建议新增 | 按固定顺序组合一个 definition、settings、client 和投影器 | 动作发现、另一域语义、重试 | typed input+context→capability result |
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
| `DR-BQCOM-001` | 每个业务动作以冻结 `CapabilityDescriptor.capability_id/api_version` 作为唯一身份/版本权威，并由域代码绑定一个只读外部契约、强类型输入/响应/记录和字段目录；common 不动态创建动作 | 域 definition/provider | 启动 | 有限可审计动作 |
| `DR-BQCOM-002` | 设置只允许在代码 definition 的适用维度和上限内取子集/更小值；未声明维度出现配置即失败 | settings validator | 启动 | 配置不能扩权 |
| `DR-BQCOM-003` | outbound client 只接受 `OpaqueUserToken` 显式 reveal 后设置单一 Authorization header；缺失/空 token 零网络调用且无 service fallback | HTTP client、handler | 调用前 | 用户身份原样透传 |
| `DR-BQCOM-004` | Agent 只消费外部 role→Authority 可观察契约：role claim 是已验证非空集合，`ADMIN/VIEWER` 分别形成 `ROLE_ADMIN/ROLE_VIEWER`；缺失/空白/未知/错误失败关闭；用户名不是规则 | 外部安全权威、业务集成测试 | 业务入口认证 | 业务服务获得统一 Authority |
| `DR-BQCOM-005` | 业务服务是动作和成功响应数据可见性的最终授权点；Adapter 只在已授权 2xx 类型化响应上继续收紧 | 业务服务、域 Adapter | 外部调用 | 投影不替代授权 |
| `DR-BQCOM-006` | `no_result` 只能由域 definition 绑定的明确无数据语义产生；401/403/timeout/invalid response/投影后空值均不能转 no_result | response normalizer | 响应映射 | 状态真实 |
| `DR-BQCOM-007` | 每个动作以唯一的非空 `required_user_field_ids` 声明最小用户结果；已有记录却无法满足时返回 downstream_failure，禁止空 success | definition、user projector | 用户结果投影 | 最小有效结果 |
| `DR-BQCOM-008` | 用户字段=实际授权响应字段∩代码 user 字段∩配置 user 字段；模型字段再交集代码 model candidate、配置 model 字段和全局规则 | field projectors | 成功响应 | 两个不同视图 |
| `DR-BQCOM-009` | 转换固定六个枚举、代码实现、类型严格；配置只可为字段选择 definition 明示允许项，失败时该模型载荷整体拒绝 | transform registry | 字段投影 | 模型前完成转换 |
| `DR-BQCOM-010` | safe payload 使用 `schema_version=1` 和有界 facts；业务文本只作为 JSON value，fact ID/record ref 为请求内序号，不含原始控制指令 | egress projector | 出域允许 | 结构化最小载荷 |
| `DR-BQCOM-011` | 回答按固定分隔符切成句段；除两个精确非事实前缀外每段必须携带 `[fact-NNNN]`，used IDs、标记和受保护 token 均须由该段引用 facts 支持，unsupported claims 为空；任一不确定整体拒绝 | grounding policy | 模型候选返回 | 无依据回答丢弃 |
| `DR-BQCOM-012` | 外部状态先映射为有限 `BusinessServiceFailureKind`，再穷尽映射固定公共 code；原始错误 message/body/header/stack 不进入公共结果、日志或模型 | client、normalizer、handler | 失败 | 稳定 code/source |
| `DR-BQCOM-013` | 任一已启用动作配置、definition、字段/转换引用或必需依赖无效时整个 Runtime 不就绪；禁用动作不建客户端 | composition root | 启动 | 不运行半有效动作 |
| `DR-BQCOM-014` | 每个动作最多一次业务 HTTP；以核心绝对截止与动作上限的较小值包住连接、发送、流式读取和解析；受控 host、响应聚合前字节上限、取消和资源关闭失败关闭；无自动 retry/replay/换身份/换动作 | handler/client | 每请求 | 只读且有界 |
| `DR-BQCOM-015` | common 只提供原语和 Protocol，域 provider 显式实例化；模拟第三域只新增 fixture/provider，不修改 core/common/已有 Adapter | composition root | 扩展 | 无动态插件平台 |
| `DR-BQCOM-016` | 本文不定义或修改 `auth-service/common-security` 私有实现、域端点/字段/授权方法；只记录消费差距和证据 | 文档/测试边界 | 设计/联调 | 权威不越界 |
| `DR-BQCOM-017` | 业务敏感问题类别与合成场景提供给 L2_00_02，实际 allow/deny 仍由全局 `QuestionEgressGuard` 决定 | fixture、模型测试 | 动作选择前 | 不复制输入策略 |
| `DR-BQCOM-018` | 本期业务动作都必须生成可返回的最小 `BusinessUserResult`；模型字段为空、全局禁用、冲突或转换失败时返回 `success + denied` 与本地受控结果，回答模型零调用；业务 common 不生成 `model_egress_denied` | egress projector、域 definition | 出域判定 | 本地/外发分离 |

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
| `descriptor` | `CapabilityDescriptor` | 是 | 唯一动作身份/版本权威；`capability_id` 为 canonical ID、`api_version=1`、`kind=query`，提交核心注册 |
| `domain_id` | `BusinessDomainId` | 是 | 代码绑定 newtype，值匹配 `^[a-z][a-z0-9_]{0,31}$`；首批生产值为 `employee/transaction`，不复用 capability canonical ID 语法且不能由模型或配置创建 |
| `service_key` | `BusinessServiceKey` | 是 | provider 代码绑定且在组合根解析为一个受控 base endpoint；配置不能为动作选择 host |
| `argument_validator` | `CapabilityArgumentValidator[TInput]` | 是 | 模型 JSON→强类型输入 |
| `request_mapper` | `BusinessRequestMapper[TInput,TWireRequest]` | 是 | `(TInput, BusinessActionSettings)`→`TWireRequest`；必须执行分页/时间/过滤/排序收紧，不接受动态 URL |
| `wire_codec` | `BusinessWireCodec[TWireRequest,TWireResponse]` | 是 | wire request→受控 HTTP；同一次 wire request+2xx bounded body→严格 typed wire response |
| `response_normalizer` | `BusinessResponseNormalizer[...]` | 是 | wire→tagged result |
| `http_status_semantics` | `BusinessHttpStatusSemantics` | 是 | 代码冻结 204/400/404 的有限契约语义；其他状态不可配置 |
| `applicable_dimensions` | `frozenset[ConstraintDimension]` | 是 | 配置可出现的有限维度 |
| `filter_field_ids_by_code` | `frozenset[str]` | 是 | 请求过滤字段代码上限；可为空，不要求同时为结果字段 |
| `sort_field_ids_by_code` | `frozenset[str]` | 是 | 请求排序字段代码上限；可为空，不要求同时为结果字段 |
| `field_definitions` | tuple | 是 | 非空、ID 唯一、代码绑定 extractor/type/classification |
| `required_user_field_ids` | `tuple[str,...]` | 是 | 唯一 required 权威；非空、唯一，且均为 code user-visible field |
| `answer_mode` | `structured_only/model_assisted` | 是 | 代码决定，不由配置放宽 |
| `contract_limits` | `BusinessContractLimits` | 是 | 代码冻结的数值/字节上限；配置只能降低 |

配置、日志、safe payload 和域 handler 一律以 `descriptor.capability_id/api_version` 取动作身份与版本，不得复制 `action_id/contract_version` 字段。`structured_only` 与
`model_assisted` 都必须先形成可直接返回用户的最小结果；后者仅允许再生成可选摘要，不得
把模型变成唯一可读结果。definition 不能包含角色白名单；允许角色由业务服务实现并按上位
确认的 `admin/viewer` 验证。

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
| `timeout_ms` | int | 100～动作 `max_timeout_ms`；调用时仍取请求绝对剩余预算的较小值 |

`BusinessContractLimits` 精确包含
`max_page_size/max_result_count/max_time_range_days: int | None`、
`max_timeout_ms: int` 和 `max_request_bytes: int`。非空数值分别必须处于
1～1000、1～1000、1～3660；timeout 为 100～60000ms，request 为 1024～65536 bytes。
某数值维度只有在 `applicable_dimensions` 声明时才能非空，已声明维度必须有代码上限。
settings 对应值必须≤代码上限；filter/sort settings 分别只能是
`filter_field_ids_by_code/sort_field_ids_by_code` 的子集。

每个 `user_result_field_id` 必须恰有一个唯一 user transform selection；每个
`model_field_id` 必须恰有一个唯一 model transform selection，且该 field 同时存在于 user
集合。缺失、重复或额外 selection 均启动失败，禁止以隐式 identity 填补。配置源的精确
环境键由域 L2 随 descriptor ID 固化；common 只拥有上述字段及验证算法。禁止使用任意
mapping 透传未声明配置。

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
| `allowed_user_transforms` | 有限枚举子集 |
| `allowed_model_transforms` | 有限枚举子集 |
| `enum_values` | 仅 enum 类型可有，代码冻结 |

`unknown`、`credential_or_secret` 和 `free_text_sensitive` 的模型候选必须为 false。其他分类是否允许由域 L2逐字段确认，不能由分类名称自动放行。

### 8.5 请求、响应与公共 Protocol

所有类型使用 `@dataclass(frozen=True, slots=True, kw_only=True)` 或冻结 `Protocol`
输入；tuple/只读 mapping 在构造时深复制并冻结。

| 类型 | 精确字段/方法 | 不变量 |
|---|---|---|
| `BusinessHttpRequest` | `method: Literal["GET","POST"]`；`relative_path: str`；`query: tuple[tuple[str,str], ...]`；`json_body: JsonObject \| None` | path 以单个 `/` 开头且不得含 scheme/host/fragment、`..` 或反斜线；query key 唯一且排序，name/value 各≤256 UTF-8 bytes；GET body 必须空；POST body 使用 canonical JSON 且≤definition request 上限；除 client 注入的 Authorization/Accept/Content-Type 外不接受任意 header |
| `BoundedBusinessHttpResponse` | `status_code: int`；`content_type: str \| None`；`body: bytes \| None` | status 100～599；非 2xx 和 204 的 body 恒为 `None`；其他 2xx 只接受 `application/json`（参数可忽略）；body 已在聚合前受全局上限约束 |
| `BusinessTransportFailure` | `kind: timeout/response_too_large/tls_or_connect/protocol` | 不携带 URL、异常、message、header 或 body；`CancelledError` 不转换为该类型，清理后原样传播 |
| `BusinessRequestMapper[TInput,TWireRequest]` | `def map(self, input: TInput, settings: BusinessActionSettings) -> TWireRequest` | 纯函数；验证并收紧分页/时间/过滤/排序；只抛有限 `InvalidBusinessArguments`，不得访问网络或读取配置 |
| `BusinessWireCodec[TWireRequest,TWireResponse]` | `def encode(self, request: TWireRequest) -> BusinessHttpRequest`；`def decode_success(self, *, request: TWireRequest, response: BoundedBusinessHttpResponse) -> TWireResponse` | 代码绑定 method/path；decode 显式接收当前调用栈中完成 encode 的同一冻结 request，只接受2xx，执行请求—响应回显/上限校验、严格 UTF-8、JSON unique keys、顶层类型和 unknown-field 策略；只抛有限 `InvalidBusinessWireRequest/Response`，不得把 request 保存为 codec 可变实例状态 |
| `BusinessResponseNormalizer[TWireResponse,TRecord]` | `def normalize_success(self, response: TWireResponse) -> BusinessServiceResult[TRecord]` | 纯函数；输入只来自已解码 2xx；可生成 records/no_result/invalid_response，不能解释 4xx/5xx；不得读取 HTTP client、JWT 或配置 |

`BusinessHttpStatusSemantics` 只有三个 bool：
`http_204_is_no_result`、`http_400_is_invalid_argument`、
`http_404_is_no_result`，默认均为 false，且只能由域 definition 代码固定。配置不能更改；
204 声明为 no-result 时返回该结果，未声明则为 invalid response；未声明的 400/404 与所有
409/422/429/5xx 分别按 12.1 固定矩阵映射。公共
`map_business_http_status(response, semantics)` 在 codec 前执行：除 204 外的其他 2xx
返回 `None` 表示继续解码；204、401/403/429/5xx 和声明/未声明的 400/404 穷尽返回固定
`BusinessServiceResult`，其他 1xx/3xx/4xx 返回
`downstream_failure/unavailable`。域 codec/normalizer 不得看到或覆盖非 2xx 状态。

## 9. 详细功能与核心处理流程

### 9.1 固定执行顺序

```text
1. 核心校验候选、参数，由同一注册项 validator 生成 TInput 并 claim 单动作
2. BoundBusinessActionHandler 校验 context/token/cancel/deadline
3. request_mapper 使用冻结 settings 收紧分页/时间/过滤/排序并生成 TWireRequest
4. wire_codec 生成一个 code-bound BusinessHttpRequest
5. UserJwtBusinessHttpClient 发出至多一个请求并流式产生 bounded response
6. common status mapper 对非 2xx 直接产生固定结果；只有 2xx 连同当前调用栈的同一 `TWireRequest` 进入 wire_codec 严格解码
7. response_normalizer 只把 2xx typed wire response 映射为 BusinessServiceResult
8. user projector 形成最小有效 BusinessUserResult
9. egress projector 计算模型字段交集并执行有限转换
10. handler 构造合法 CapabilityResult
```

步骤 2～7 位于同一个动作 `call_deadline` 控制域：异步 I/O 使用
`asyncio.timeout_at(call_deadline)`，每个同步有界转换前后检查取消和
`loop.time() < call_deadline`；任何超时/取消后不得继续解码、投影或接纳结果。步骤 7
之前不能构造用户/模型字段，步骤 8 不能把投影当作业务授权，步骤 9 不能回看原始 wire
response。

### 9.2 类型化业务结果

`BusinessServiceResult[TRecord]` 是有限 tagged union；失败分支只携带
`BusinessServiceFailureKind`，不得携带域自定义字符串 code、原始 HTTP body 或异常：

| kind | 必填 | 禁止 | 公共映射 |
|---|---|---|---|
| `records` | 非空 typed records、受控分页/覆盖元数据 | failure/raw response | 进入 user projection |
| `no_result` | 确认契约允许的空元数据 | records/failure | `no_result` |
| `invalid_argument` | `failure_kind=invalid_argument` | records/body/code | `invalid_argument/business.invalid_arguments` |
| `unauthenticated` | `failure_kind=unauthenticated` | records/body/code | `unauthenticated/business.downstream_unauthenticated` |
| `forbidden` | `failure_kind=forbidden` | records/body/code | `forbidden/business.downstream_forbidden` |
| `timeout` | `failure_kind=timeout` | records/body/code | `timeout/business.downstream_timeout` |
| `downstream_failure` | `failure_kind=rate_limited/invalid_response/unavailable` | records/body/code | 穷尽映射 `business.rate_limited/business.invalid_response/business.downstream_failure` |

具体 variant 为泛型 `BusinessRecordsResult`（字段
`records: tuple[TRecord,...]`、`coverage: BusinessResultCoverage`）、
`BusinessNoResult`（字段 `coverage: BusinessResultCoverage`）和
`BusinessFailureResult`（字段 `kind: BusinessServiceFailureKind`）；union 不使用可空字段模拟 variant。
`BusinessResultCoverage` 精确含 `returned_count: int`、`truncated: bool`、
`total_count: int | None`：records 的 returned count 必须等于 tuple 长度且≥1；no-result
必须为 0/false 且 total count 只能为 0/None；若 total count 非空，必须≥returned count。
不得携带 cursor、原始页对象或业务主键。

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

`BusinessUserResult` 是冻结 typed intermediate，精确包含
`capability_id: str`、非空 `records: tuple[BusinessUserRecord,...]` 和
`coverage: BusinessResultCoverage`。每个 `BusinessUserRecord` 含请求内连续
`record_ref=record-[0-9]{4}` 及非空、按 field definition 顺序冻结的
`fields: tuple[BusinessUserField,...]`；field 只含 `field_id` 与已完成 user transform 的
`JsonScalar value`，`None` 表示缺失并被省略，不能进入结果。

`to_domain_result()` 按固定结构输出核心 `JsonObject`：

```json
{
  "schema_version": 1,
  "capability_id": "namespace.action",
  "records": [
    {
      "record_ref": "record-0001",
      "fields": {
        "code-bound-field-id": "safe-local-value"
      }
    }
  ],
  "coverage": {
    "returned_count": 1,
    "truncated": false,
    "total_count": null
  }
}
```

key 和 records/fields 顺序按上述规则固定，canonical UTF-8 JSON 必须≤冻结
`max_user_result_bytes` 且该上限在启动时≤核心
`CoreRuntimeSettings.max_domain_result_bytes`；超界返回
`downstream_failure/business.user_result_too_large`，不得把超界值交给核心后再变成
`core.invalid_result`。模型载荷只能从 typed `BusinessUserResult` 生成，不能从序列化后的
mapping 反向遍历。

### 9.4 事务与一致性边界

本流程不写数据库、消息、索引或缓存，不适用跨资源事务、补偿、CAS 或分布式锁。单请求一致性来自冻结 action definition/settings、一次 HTTP 调用、不可变 typed result 和取消/截止后拒绝迟到结果。重复用户请求是新查询，不承诺跨请求快照一致、幂等结果或自动去重。

## 10. JWT、Authority 与业务最终授权

### 10.1 用户 JWT 客户端原则

- client 方法必须显式接收 `OpaqueUserToken`，不能读取进程全局 token 或创建 service token。
- `reveal_for_outbound()` 只在 header 构造的最小作用域调用一次；值只进入 `Authorization: Bearer ...`。
- token 不进入 body、query、URL、异常、repr、指标或日志。
- 缺 token/非法 context 时在创建 HTTP request 前返回 `unauthenticated/business.missing_user_token`。
- 每个动作一次请求、无 retry；重定向关闭，防 token 转发到非代码绑定 host。
- 每个已启用域创建一个 lifespan-scoped `httpx.AsyncClient`：base endpoint 来自该
  `BusinessServiceKey` 的冻结启动配置，只允许 `http/https`、非空 host、可选固定端口，
  禁止 user-info/query/fragment；production profile 必须使用 HTTPS，loopback
  development profile 才可显式允许 HTTP。
- client 固定 `trust_env=False`、`follow_redirects=False`、`http2=False`、
  `verify=True`（HTTPS）、`Accept-Encoding: identity`，transport retries=0；不得读取
  `HTTP_PROXY/HTTPS_PROXY/SSL_CERT_FILE` 等环境隐式扩大出站或信任边界。
- `BusinessHttpRequest` 只含代码定义的 `GET/POST`、以 `/` 开头且无 scheme/host 的相对
  path、排序后的受控 query 和有界 JSON body；path/method 只由域 definition/codec
  提供，模型参数和配置不得覆盖。
- handler 计算
  `call_deadline=min(context.deadline_monotonic, loop.time()+settings.timeout_ms/1000)`；
  剩余≤100ms 时零连接。client 用同一个 `asyncio.timeout_at(call_deadline)` 包住连接、
  发送、2xx 流式读取、解码和 typed parsing，不得为各阶段重置相对 timeout。
- 收到 headers 后先判 status：非 2xx 不读取正文；2xx 仅按 raw bytes 流式累计，读取
  `max_response_bytes+1` 即停止并失败，不能先 `response.aread()` 后校验。所有正常、
  超时、超界、取消和异常路径均关闭 response；Runtime shutdown 的
  `CancelledError` 原样传播。
- client 由组合根创建并在 Runtime lifespan 关闭；禁用域不创建。任何 URL/host、
  token 或响应正文不得进入异常、日志或指标。

### 10.2 role→Authority 消费契约

业务查询的目标可观察语义：

| JWT role claim | 统一映射预期 | 业务服务结果 |
|---|---|---|
| `["ADMIN"]` | `ROLE_ADMIN` | Employee/Transaction 首批动作允许 |
| `["VIEWER"]` | `ROLE_VIEWER` | Employee/Transaction 首批动作允许 |
| `["ADMIN","VIEWER"]` | 两个去重 Authority | 允许，不因顺序变化 |
| 已验证 user token，但 role 缺失/null/空集合/含空白元素 | 不产生允许 Authority | HTTP 403；受保护业务方法/数据访问 0 |
| 已验证 user token，但 role 是字符串、嵌套对象或含非字符串 | 格式错误且不宽松转换 | HTTP 403；受保护业务方法/数据访问 0 |
| 已验证 user token，但含未知 role、大小写漂移或已知+未知混合 | 整个 role 集合拒绝，不保留其中已知 Authority | HTTP 403；受保护业务方法/数据访问 0 |
| token 缺失、签名/有效期失败或 `token_type!=user` | 不形成有效 user Authentication | HTTP 401；受保护业务方法/数据访问 0 |

这是一份消费和集成验收预期，不是本文对 `common-security` 私有类或 converter 实现的定义。`dylan` 通过 JWT 中的 ADMIN 获权，用户名本身不得出现在 Adapter、业务服务授权规则或配置中。

### 10.3 最终授权与响应可见性

业务服务必须在实际动作入口：

1. 重新验证 JWT 签名、有效期和 `token_type=user`。
2. 消费统一 Authority，并允许首批 `ROLE_ADMIN/ROLE_VIEWER`。
3. 按 10.2 区分 token 认证失败 401 与已验证 user token 的 role/Authority 拒绝 403；
   security filter/受保护业务方法和数据访问 spies 必须证明拒绝路径的领域调用为零。
4. 保证 2xx 响应记录、字段和数据范围符合当前用户的本域可见性契约。

Adapter 不解析 role、不维护允许角色、不补做行/字段授权。只要第 4 点没有提供方契约和测试证据，真实动作必须保持禁用，即使 Adapter 能删除字段也不能关闭门禁。

## 11. 字段交集、有限转换与模型出域

### 11.1 模型字段交集

`GlobalBusinessEgressPolicy` 是从 12.2 冻结设置构造的代码类型，精确包含：
`enabled: bool`、`policy_version: Literal["business-egress-v1"]`、
`always_denied_classes: frozenset[DataClass]`（固定含
`credential_or_secret/free_text_sensitive/unknown`）以及
`max_safe_facts/max_safe_payload_bytes/max_text_value_chars/max_fields_per_record`。
配置只能关闭出域或降低四个上限，不能删除 always-denied class、增加分类或更改版本。
其他 data class 也不会因未在 always-denied 集合中自动允许，仍须通过 definition、
settings 和字段 transform 的全部交集。

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
| `identity_scalar` | exact bool/int | 同类型 | `type(value) is bool`，或 `type(value) is int` 且绝对值≤`2^53-1`；不接受 string/float/bool-as-int | 拒绝整个 safe payload |
| `bounded_text` | exact string | string | NFC 后 1～全局 Unicode code-point 上限；拒绝全部 C0/C1 控制符（包括换行/制表）及 Bidi override/isolate；字段必须代码标记 model text allowed | 同上 |
| `mask_keep_last4` | exact string | string | NFC、无控制/Bidi 字符、5～256 Unicode code point；输出固定 `"***"`+末 4 个 code point；字段代码还须约束原始 identifier 字符集 | 同上 |
| `date_only` | exact `date` 或 `datetime` | ISO 公历日期字符串（四位年、两位月、两位日） | `datetime` 取其原有 offset/naive 表示的 `.date()`，不转换时区、不接受 string | 同上 |
| `decimal_2` | exact `Decimal` | string | finite，`ROUND_HALF_UP` 到 2 位并固定两位小数；禁止 string、binary float、NaN/Infinity | 同上 |
| `enum_code` | string enum | string | 必须精确位于字段代码 allowlist | 同上 |

`FieldTransformSelection` 只有 `field_id: str` 和
`transform_id: BusinessFieldTransform`，同一视图内 field ID 唯一，不提供参数。
不提供 `drop`、脚本、正则替换、表达式、动态模板或任意参数；字段不出域通过集合排除完成。
转换后的值重新执行类型、长度、JSON 深度和 payload 字节校验。

### 11.3 模型安全载荷

```json
{
  "schema_version": 1,
  "policy_version": "business-egress-v1",
  "config_snapshot_id": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
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

`BusinessAnswerGroundingPolicy` 精确实现 `L2_00_02` 的
`AnswerGroundingPolicy.validate(input: GroundingInput) -> GroundingDecision`；
只从 `input.safe_payload` 和 `input.candidate` 读取下列内容，并至少执行：

1. 先验证 payload schema/version/action，fact ID 精确匹配
   `fact-[0-9]{4}` 且按连续 `fact-0001..N` 排列；`used_fact_ids` 非空、去重并全部存在。
2. 不改写 answer；按从左到右扫描，在 `.?!。！？;；\n` 后结束一个句段，尾部非空文本
   也形成句段；每段只去除首尾 Unicode whitespace，空段忽略。
3. fact marker 只接受精确 `\[fact-[0-9]{4}\]`；全 answer marker 的去重集合必须与
   `used_fact_ids` 精确相同，且每个被引用 ID 至少出现一次。
4. 除精确等于 `查询结果：` 或 `根据可用数据：` 的句段外，每个非空句段至少含一个
   marker；marker 必须引用本 payload fact。前缀比较不做模糊、包含或大小写转换。
5. 使用同一个 `extract_protected_tokens(text)` 分别处理句段（先移除 marker span）和其引用
   facts 的 canonical display text。display text 固定为：bool 的小写 JSON
   `true/false`、int 的十进制、decimal/date/enum/identifier/text 的已转换 string。
   tokenizer 按“`***`+后续恰好 4 个 `isalnum()`/`_`/`-` code point 的掩码标识 →
   `[0-9]{4}-[0-9]{2}-[0-9]{2}` 日期 → 有符号十进制/百分数 → ASCII token
   `[A-Za-z0-9][A-Za-z0-9_.:%+-]{0,127}`”顺序扫描；每次命中先占用 span，后续规则不得
   在已占 span 内重复提取。每个句段 token 必须存在于该段引用 facts 的 token 并集。
   system instruction 要求枚举、日期、数值和标识使用 canonical 形式，不允许同义改写。
6. `unsupported_claims` 必须为空；该字段为空不能替代第 1～5 步。
7. 若 `coverage.truncated=true`，对 answer 做 NFKC+casefold 的仅校验副本，出现
   `全部/唯一/完整/没有其他/all/only/complete/no other` 任一固定短语即拒绝。
8. 任一 schema、句段、marker、token、coverage 检查异常或不确定，丢弃整个候选并由
   L2_00_02 映射 `invalid_output`；不得局部裁剪或修改后返回。

该规则能确定性验证引用与受保护 token，但仍不能证明任意自然语言逻辑等价或中文自由
文本实体未被补造。因此域 L2 应优先允许枚举、日期、数值、短标签等可验证字段，并为
允许的回答形态提供合成正/负例；`free_text_sensitive` 默认禁止外发。超出该能力边界时
返回结构化本地结果，不把此规则描述为事实正确性证明。

### 11.5 出域判定

| 条件 | `CapabilityResult` |
|---|---|
| 用户结果有效、answer mode=structured_only | `success + not_applicable`，返回本地结构化结果 |
| 用户结果有效、模型允许且 facts 非空 | `success + allowed`，safe payload 非空 |
| 用户结果有效、全局禁用/字段全拒绝/冲突/转换失败 | `success + denied`，保留本地结果，回答模型零调用 |
| 业务无数据 | `no_result + not_applicable` |

策略不确定时不得使用 `not_applicable` 伪装允许；`not_applicable` 只用于 code-bound structured-only 动作。

`BusinessEgressProjector` 直接返回核心 `ModelEgressResult`，不再定义第二套
`BusinessEgressProjection`。`success + denied` 必须使用
`ModelEgressResult(disposition=denied, policy_version=business-egress-v1,
safe_payload=None, reason_code=<有限枚举>)` 且 `failure=None`；reason code 仅允许
`egress_disabled/no_model_fields/policy_conflict/transform_failed/payload_limit`。由于所有
启用业务动作都必须先形成可返回的最小用户结果，business common 本期不得构造
`model_egress_denied`；未来若出现模型专用动作，必须先修改上位/L2 契约，不能用配置开启。

## 12. 失败、配置、安全与观测

### 12.1 错误码与调用方可见语义

| 触发 | 公共 status | failure code | source | 网络调用 |
|---|---|---|---|---:|
| arguments/配置边界非法 | `invalid_argument` | `business.invalid_arguments` | capability | 0 |
| user token/context 缺失 | `unauthenticated` | `business.missing_user_token` | capability | 0 |
| 业务 HTTP 401 | `unauthenticated` | `business.downstream_unauthenticated` | downstream | 1 |
| 业务 HTTP 403 | `forbidden` | `business.downstream_forbidden` | downstream | 1 |
| 明确契约 no data | `no_result` | 无 | 无 | 1 |
| HTTP 400 且域 definition 代码声明该状态就是用户参数错误 | `invalid_argument` | `business.invalid_arguments` | downstream | 1 |
| 未知 400/409/422、429、5xx、连接错误 | `downstream_failure` | `business.downstream_failure` 或 `business.rate_limited` | downstream | 1 |
| client deadline | `timeout` | `business.downstream_timeout` | downstream | 1 |
| 2xx body/字段/类型/大小非法 | `downstream_failure` | `business.invalid_response` | downstream | 1 |
| 有 record 但最小用户结果失败 | `downstream_failure` | `business.minimum_user_result_not_met` | capability | 1 |
| 有效投影超过冻结 user-result 字节上限 | `downstream_failure` | `business.user_result_too_large` | capability | 1 |
| 模型字段拒绝/转换失败且本地结果有效 | `success` | 无 | 无 | 回答模型 0 |

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
| `AGENT_BUSINESS_MAX_USER_RESULT_BYTES` | `262144` | 16384～262144，且≤核心 `max_domain_result_bytes` | 重启；只能降低；交叉约束失败则不就绪 |

`business-egress-v1` 是代码策略版本，不由环境覆盖。每动作设置由域 L2 定义精确键；全部设置与 action definitions 归一化后计算非敏感 `snapshot_id`，运行期只读。

`BusinessConfigurationSource` 是启动期冻结 DTO，只含：
`global_settings: BusinessGlobalSettings`、
`actions: tuple[RawBusinessActionSettings, ...]` 和
`service_bindings: tuple[BusinessServiceBinding, ...]`。域 provider 负责把域 L2 固定的
精确环境键解析为该 DTO；未知键、重复 action/service key、缺失启用动作设置、空字符串、
非十进制整数或宽松 bool 均启动失败，禁止把 `os.environ` 或任意 mapping 传入 validator。

`BusinessConfigurationSnapshot` 包含已验证 global settings、按
`descriptor.capability_id` ASCII 排序的 action settings、按 service key 排序且已验证的
service bindings 和完整 64 位小写 SHA-256 `snapshot_id`。哈希输入是上述数据及
descriptor ID/api version、字段/转换 ID 的 canonical JSON（UTF-8、对象 key 排序、tuple
保持已定义顺序、无空白）；允许包含无 user-info 的 canonical endpoint，但不得包含 JWT、
API key、subject、问题或运行期值。日志只记录 snapshot 前 12 位，safe payload 使用完整
snapshot ID；同一输入必须得到相同 ID，任一生效设置/definition/binding 变化必须改变 ID。

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

1. 由 Employee/Transaction provider 分别提供代码 action definitions，并把各自精确环境键严格解析为 `BusinessConfigurationSource`。
2. 公共 validator 对全局设置、service bindings 和全部动作执行身份、配置子集、必需字段、转换、契约版本和依赖校验，生成一个冻结 snapshot。
3. 某一启用动作或域配置无效时，整个 Runtime readiness=false；不静默保留另一域形成半有效部署。
4. 全域禁用是合法状态：不创建业务客户端、不注册业务动作，但不影响 Knowledge/core 独立验证。
5. 按排序 service key 为有效启用域创建 client，再为每个动作创建
   `BoundBusinessActionHandler` 并显式提交核心 registry；任一步失败时按创建逆序
   `aclose()` 已建 client，注册表不得冻结，readiness=false。
6. common module 不扫描模块、不读取 entry point、不自动发现第三方 Adapter。

Runtime shutdown 先停止接纳新请求并等待/取消既有 scope，再对每个 business client
恰好 `aclose()` 一次；关闭失败只记录安全枚举，不把 Runtime 重新标为 ready。client 不在
`BusinessSupportFactory.build` 中创建，使纯配置校验、全域禁用和失败回滚都无需网络资源。

`BusinessDomainProvider` 是域 L2 必须实现的公共 Protocol：

```python
class BusinessDomainProvider(Protocol):
    def domain_id(self) -> BusinessDomainId: ...
    def definitions(
        self,
    ) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]: ...
    def configuration_fragment(self) -> BusinessConfigurationFragment: ...
```

provider 在构造时只接收本域强类型启动 settings；`configuration_fragment()` 只投影本域
已知 action settings 和唯一 service binding，不接收/返回 `os.environ` 或任意 mapping，
不创建 client、不注册能力。组合根按 `domain_id` ASCII 排序 provider；空/重复 domain、
definition 的 domain 不匹配、跨 provider 重复 descriptor/service key 或 fragment 引用
其他域均启动失败。

`BusinessSupportSnapshot` 精确包含冻结 `global_settings`、
按 capability ID 排序的
`actions: tuple[BoundBusinessActionSupport,...]`（每项只有 definition+validated settings）、
按 service key 排序的 `service_bindings` 和 `snapshot_id`；不含 client、JWT、handler、
环境对象或可变 registry。组合根仅从该 snapshot 为 enabled action 创建 client/handler/
`CapabilityRegistrationCandidate`，禁用 action 只保留校验证据而不产生 registration。

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
| `IMPL-BQCOM-010` | 建议新增 | Python provider support | `agent-runtime/src/agent_runtime/business/provider.py` | `BusinessDomainProvider`、`BusinessSupportSnapshot`、`BusinessSupportFactory` | 聚合域 definition/config 并提供冻结原语 | 不扫描、不创建 client、不自动注册动作 | `DR-BQCOM-013/015/016` |
| `IMPL-BQCOM-011` | 建议新增 | Python composition | `agent-runtime/src/agent_runtime/bootstrap.py` | 显式接收 Employee/Transaction providers | 组合根接入 | 可扩展不侵入 core | `DR-BQCOM-013/015` |
| `IMPL-BQCOM-012` | 建议新增 | Contract fixture | `agent-runtime/tests/contract/business/authority_expectations.json` | role/Authority/allow-deny 场景 | 外部安全消费证据 | 不定义 Java 实现 | `DR-BQCOM-004/016` |
| `IMPL-BQCOM-013` | 建议新增 | Security fixture | `agent-runtime/tests/fixtures/business_sensitive_questions.json` | 合成敏感问题类别 | 给 L2_00_02 负向测试 | 防遗漏问题出域 | `DR-BQCOM-017` |
| `IMPL-BQCOM-014` | 建议新增 | Python handler | `agent-runtime/src/agent_runtime/business/handler.py` | `BoundBusinessActionHandler` | 固定 mapper→codec→client→normalizer→projection 顺序和绝对截止 | 防两个域复制/漂移调用语义 | `DR-BQCOM-003/005/006/007/012/014/015/018` |

### 13.3 Python 边界关键签名

| 路径/符号 | 建议签名 | 输入与校验 | 输出/错误 | 副作用/消费者 |
|---|---|---|---|---|
| 建议新增：`business.settings.BusinessSettingsValidator.validate` | `def validate(self, definitions: Sequence[BusinessActionDefinition[Any,Any,Any,Any]], raw: BusinessConfigurationSource, *, core_max_domain_result_bytes: int) -> BusinessConfigurationSnapshot` | descriptor/domain/service ID、维度/子集/上限/required fields/transform/binding/依赖、user≤core bytes 及 canonical snapshot | 冻结 snapshot；配置错误只含稳定 code | 无 I/O；composition root |
| 建议新增：`business.contracts.BusinessRequestMapper.map` | `def map(self, input: TInput, settings: BusinessActionSettings) -> TWireRequest` | input 已由本 definition validator 产生；settings 属于同一 snapshot/action；执行域约束收紧 | typed wire request；有限 `InvalidBusinessArguments` | 纯函数；bound handler |
| 建议新增：`business.contracts.BusinessWireCodec.encode/decode_success` | `def encode(self, request: TWireRequest) -> BusinessHttpRequest`；`def decode_success(self, *, request: TWireRequest, response: BoundedBusinessHttpResponse) -> TWireResponse` | 8.5 的 path/method/query/body；decode 只接受2xx并校验当前冻结 request 对应的回显/结果边界、content-type/strict JSON | typed request/response；有限 wire error | 纯函数；bound handler按同一调用栈传参，不共享请求期状态 |
| 建议新增：`business.result_mapping.map_business_http_status` | `def map_business_http_status(response: BoundedBusinessHttpResponse, semantics: BusinessHttpStatusSemantics) -> BusinessServiceResult[Never] | None` | 穷尽 1xx～5xx；semantics 来自 definition | 2xx 为 None；非2xx为固定 tagged result | 纯函数；codec 前唯一状态解释点 |
| 建议新增：`business.contracts.BusinessResponseNormalizer.normalize_success` | `def normalize_success(self, response: TWireResponse) -> BusinessServiceResult[TRecord]` | 同一动作已解码 2xx wire response | records/no_result/invalid_response；不携带自定义 code/body | 纯函数；bound handler |
| 建议新增：`business.http_client.UserJwtBusinessHttpClient.execute` | `async def execute(self, *, request: BusinessHttpRequest, user_token: OpaqueUserToken, call_deadline: float, cancellation: CancellationSignal) -> BoundedBusinessHttpResponse` | request 仅含受控相对路径；token 非空；绝对 deadline、取消、聚合前 raw body 上限；client 已绑定 service key/base endpoint | 任一 HTTP status 返回 bounded response（非 2xx body 恒空）；超时/超界/连接/协议为有限 typed transport failure | 一个绝对 timeout 内至多一次 HTTP、无 retry；所有路径关闭 response；域 client |
| 建议新增：`business.http_client.UserJwtBusinessHttpClient.aclose` | `async def aclose(self) -> None` | 可重复调用但底层 client 只关闭一次；关闭后 execute 固定失败 | 无业务结果；关闭错误只转安全内部枚举 | Runtime lifespan |
| 建议新增：`business.handler.BoundBusinessActionHandler.handle` | `async def handle(self, input: TInput, context: CapabilityExecutionContext) -> CapabilityResult` | 构造时绑定同一 definition/settings/client/projectors；校验 context、token、cancel、绝对 deadline | 按 9.1/11.5/12.1 返回合法公共结果；未知异常留给 core，`CancelledError` 传播 | 每次至多一个 HTTP 和一个 answer-safe payload；core registry |
| 建议新增：`business.user_projection.BusinessUserResultProjector.project` | `def project(self, *, definition: BusinessActionDefinition[...,TRecord], settings: BusinessActionSettings, result: BusinessRecordsResult[TRecord], max_user_result_bytes: int) -> BusinessUserResult` | 只迭代 definition、apply user transforms、required invariant、固定 JSON/bytes | 冻结 user result；失败 typed code | 纯函数；域 handler |
| 建议新增：`business.contracts.BusinessUserResult.to_domain_result` | `def to_domain_result(self) -> JsonObject` | 已在构造时验证 schema、顺序和 canonical bytes | 新建深冻结固定 JSON；不暴露 typed record | 纯函数；bound handler/core |
| 建议新增：`business.transforms.BusinessTransformRegistry.apply` | `def apply(self, *, transform_id: BusinessFieldTransform, definition: BusinessFieldDefinition[TRecord,TValue], value: TValue) -> JsonScalar` | 保留字段强类型，校验类型/字段 allowlist/全局上限；Decimal/date 不先降为 JSON | canonical safe JSON scalar；失败不含原值 | 纯函数；两个 projectors |
| 建议新增：`business.egress.BusinessEgressProjector.project` | `def project(self, *, definition: BusinessActionDefinition[Any,Any,Any,Any], settings: BusinessActionSettings, user_result: BusinessUserResult, policy: GlobalBusinessEgressPolicy, config_snapshot_id: str) -> ModelEgressResult` | 字段交集、转换、facts/bytes/count；snapshot ID 必须来自同一冻结 support | 核心定义的 allowed/denied/not_applicable 与 payload，不定义重复结果类型 | 纯函数；域 handler |
| 建议新增：`business.grounding.BusinessAnswerGroundingPolicy.validate` | `def validate(self, input: GroundingInput) -> GroundingDecision` | capability ID 必须等于 payload presentation action；只读 minimized question、safe payload、已共同校验的 `CandidateAnswer`；schema/fact/marker/token/coverage | accepted 或有限 reason；异常/未知 reason 失败关闭，不能改写候选 | 纯函数；`L2_00_02 GroundingPolicyRegistry` |
| 建议新增：`business.provider.BusinessDomainProvider` | `def domain_id(self) -> BusinessDomainId`；`def definitions(self) -> tuple[BusinessActionDefinition[Any,Any,Any,Any], ...]`；`def configuration_fragment(self) -> BusinessConfigurationFragment` | provider 已由域强类型 settings 构造；返回值须同域且冻结 | 有限定义/配置；非法 provider 阻止启动 | 不创建 client/registration；composition root |
| 建议新增：`business.provider.BusinessSupportFactory.build` | `def build(self, *, definitions: Sequence[BusinessActionDefinition[Any,Any,Any,Any]], config: BusinessConfigurationSource, core_max_domain_result_bytes: int) -> BusinessSupportSnapshot` | 全部启动不变量、service binding 唯一性、user≤core bytes 和 snapshot 算法 | 冻结 support 或启动失败 | 创建无外部连接对象；composition root |

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
| `TEST-BQCOM-001` | 建议新增 | `DR-BQCOM-001/015` | Unit/Contract | `agent-runtime/tests/unit/business/test_action_definition.py` | 两个 fake 域、descriptor/domain/service 重复/错配、filter/sort/contract limit 边界、required 空/重复/不可见、动态端点 | definition 冻结；身份/required/代码上限单一权威；common 无域字段；动作唯一 | 双重权威、动态 action/URL 或域耦合 |
| `TEST-BQCOM-002` | 建议新增 | `DR-BQCOM-002/013` | Unit | `agent-runtime/tests/unit/business/test_settings.py` | 各维度边界±1、未知/重复 filter/sort 字段、删除 required、user/model transform 缺失/重复/额外、重复 service/action、快照顺序置换/单值变化 | 只允许代码子集/更小值；每字段恰一 transform；任一 enabled 错误不就绪；canonical 输入同值同 ID、任一生效值变化必改 ID | 配置扩权、隐式 transform、半有效启动或快照不确定 |
| `TEST-BQCOM-003` | 建议新增 | `DR-BQCOM-003/014` | Unit/HTTP | `agent-runtime/tests/unit/business/test_user_jwt_http_client.py` | 缺 token、fake service token provider、恶意 base/path、proxy env、redirect、非2xx大正文、2xx limit±1、timeout/cancel/close | 缺 token调用0；只有原 user JWT header；无 retry/redirect/env proxy；非2xx正文读取0；聚合前上限；所有路径关闭且 aclose 一次 | service fallback、SSRF/token 泄露、多调用或资源泄漏 |
| `TEST-BQCOM-004` | 建议新增 | `DR-BQCOM-004/005/016` | Cross-service Contract | `agent-runtime/tests/contract/business/test_authority_consumption.py` | 10.2 全矩阵；含已知+未知混合 role、无效 token；安全边界/业务/DAO spies | ADMIN/VIEWER 允许；token 认证失败401；已验证 token 的缺失/未知/格式错 role 403且领域调用0；Adapter 不解析 role | 401/403、混合 role 或 Adapter 白名单漂移 |
| `TEST-BQCOM-005` | 建议新增 | `DR-BQCOM-006/012` | Unit | `agent-runtime/tests/unit/business/test_service_result_mapping.py` | 1xx～5xx 分区、204/400/404 semantics true/false、其他2xx records/empty、401/403/429/5xx/timeout/unknown body | common status mapper 穷尽；不继续解码的 status codec调用0；204/404 未确认不得变 no_result；无域自定义公共 code | 域解释状态、401/403混淆、无界 code 或失败变 no_result |
| `TEST-BQCOM-006` | 建议新增 | `DR-BQCOM-007/008` | Unit | `agent-runtime/tests/unit/business/test_user_projection.py` | records/coverage不变量、连续 ref、字段顺序/额外/缺 required、canonical bytes limit±1、core limit小于业务设置 | 固定 JSON；extra零进入；必需/超界失败 downstream；core交叉约束启动失败；不制造 no_result/空 success | 宽字段、core invalid result 或状态漂移 |
| `TEST-BQCOM-007` | 建议新增 | `DR-BQCOM-008/009/018` | Unit | `agent-runtime/tests/unit/business/test_egress_projection.py` | 字段交集；六转换逐一测试 exact type、边界±1、string/float/bool-as-int、控制/Bidi、naive/aware datetime、Decimal rounding；payload超界/global disabled | model⊂user；转换输出精确；未知/类型错/转换失败模型调用0且本地结果保留；只返回核心 `ModelEgressResult` | 原始字段外发、宽松强转或重复结果类型 |
| `TEST-BQCOM-008` | 建议新增 | `DR-BQCOM-010/011` | Unit | `agent-runtime/tests/unit/business/test_grounding.py` | marker ID/连续性/重复/集合、每种句末/尾段、两个精确前缀、跨句引用、掩码ID/负数/日期的重叠 span、text 内 ASCII token、unsupported、truncated 禁词 | 同一 tokenizer 生成 fact/answer token；span 不重复提取；无依据或不确定候选整体拒绝；合法 canonical 引用通过 | 掩码/负数误拒、只核 fact ID、模糊前缀或未核本句事实 token |
| `TEST-BQCOM-009` | 建议新增 | `DR-BQCOM-003/012/014` | Integration with fake server | `agent-runtime/tests/integration/business/test_failure_and_cancellation.py` | mapper/codec/client/normalizer spy、两个并发请求交错响应、请求回显不匹配、解析跨 deadline、迟到 body、断连、敏感异常、重复请求、启动中途失败 | 固定调用顺序；decode每次取得当前调用栈同一冻结wire request且无codec可变请求状态；回显不匹配失败；当前请求一次调用；解析超时/取消后丢弃；已建client逆序关闭；日志无敏感值 | 并发串响应、后台结果、半冻结registry、资源或原始异常泄露 |
| `TEST-BQCOM-010` | 建议新增 | `DR-BQCOM-013/014` | Architecture | `agent-runtime/tests/architecture/test_business_common_boundaries.py` | import graph、dependency/storage/retry scan | common 无域/SDK/DB/message/role auth；无 retry | 动态平台、持久化或反向依赖 |
| `TEST-BQCOM-011` | 建议新增 | `DR-BQCOM-001/015` | Extensibility | `agent-runtime/tests/contract/business/test_fake_third_domain.py` | 新增 test-only `sample.read` definition/provider；provider 顺序置换、跨域 fragment/重复 service；全域禁用 | 只新增 fixture/provider；snapshot 顺序稳定；错配启动失败；禁用无 client/registration；core/common/已有域源不改 | 扩展要求改 core/common 或 provider 泄漏域 |
| `TEST-BQCOM-012` | 建议新增 | `DR-BQCOM-010/011` | Model integration with spy | `agent-runtime/tests/integration/business/test_business_text_is_data.py` | fact text 含注入语句、模型越界回答 | 不触发工具/第二动作/权限变化；越界答案拒绝 | 文本影响控制语义 |
| `TEST-BQCOM-013` | 建议新增 | `DR-BQCOM-017` | Security contract | `agent-runtime/tests/contract/business/test_sensitive_question_scenarios.py` | 12.3 合成问题+model spy | 每个敏感类别 transport 0；generic case只通过输入闸门不等于授权 | 具体标识或凭证外发 |

### 14.2 关键权限与出域场景

| 场景 | 业务 HTTP | 用户结果 | 回答模型 | 公共结果 |
|---|---:|---|---:|---|
| 缺 user JWT | 0 | 无 | 0 | unauthenticated |
| ADMIN/VIEWER 且业务允许 | 1 | 按字段交集 | 0或1 | success/no_result |
| 已验证 user token 但 unknown/missing/malformed role | 1 到达安全边界，受保护业务方法/数据访问0 | 无 | 0 | forbidden |
| token 缺失/签名或有效期失败/非 user token | 缺 token 时0；其他无效 token 为1并止于安全边界 | 无 | 0 | unauthenticated |
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
| `VAL-BQCOM-005` | 当前/未来 Java 提供方、真实有效配置和角色 token 可用 | `mvn -pl common-security,employee-service,mq-procedure-service -am test`，再执行两域允许/拒绝/响应可见性集成矩阵 | 证明外部 Authority 与最终授权，不由 Python测试替代 | ADMIN/VIEWER 允许；token 认证失败401；已验证 token 的 role 拒绝403且领域调用0；成功数据范围符合契约 | 未执行：提供方设计/实现未授权且当前缺口存在 |

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
| `RISK-BQCOM-001` | 直接依赖 | L2_00_01 v0.4、L2_00_02 v0.4 已 Approved，但目标代码尚不存在 | P3 实施 | 实现仍可能偏离已批准契约 | 实施时按版本锁定做 contract tests | 不阻塞本文评审；受 `BQ-GATE-002` 控制 |
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

- 在明确实施授权后关闭 `BQ-GATE-002`；本文评审与状态变更已在本轮完成。
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

## 18. 独立正式评审记录

### 18.1 第 1 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-BQCOM-001` | S2 | 直接依赖仍记录为 In Review/Draft，且风险错误声称依赖未完成，可能让实施使用过期契约或误判阻塞原因 | 同步 L2_00_01/L2_00_02 v0.4 Approved，并把未实施与设计状态分离 | Closed（第 2 轮） |
| `REV-BQCOM-002` | S1 | definition 同时保存 action/contract 与 descriptor ID/version，且 domain ID 误用 core canonical 语法，存在注册、配置和审计身份漂移 | 以 descriptor 为唯一动作权威；domain/service key 使用独立代码绑定类型和语法 | Closed（第 2 轮） |
| `REV-BQCOM-003` | S1 | HTTP 客户端只有相对 timeout/redirect 说明，未固定 host、环境代理、流式聚合前上限、绝对截止和关闭责任 | 增加 service-key 绑定、HTTPX 安全配置、绝对 deadline、流式 raw-byte 上限及 lifespan 关闭规则 | Closed（第 2 轮） |
| `REV-BQCOM-004` | S1 | tagged failure 携带域自定义 code，公共结果可能出现无界错误码并与固定状态矩阵漂移 | 改为有限 `BusinessServiceFailureKind` 并穷尽映射固定公共 code | Closed（第 2 轮） |
| `REV-BQCOM-005` | S1 | business grounding 使用拆散参数签名，与 L2_00_02 已批准 `GroundingInput` 接口不兼容 | 精确实现 `AnswerGroundingPolicy.validate(GroundingInput)` 并只消费共同候选契约 | Closed（第 2 轮） |

首轮修复不构成评审通过，不关闭 `BQ-GATE-002`、真实业务授权或真实数据出域门禁。

### 18.2 第 2 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-BQCOM-006` | S1 | action definition 只有泛化 callable，缺 mapper/codec/normalizer 的精确方法与 HTTP DTO，两个域无法实现相同边界 | 增加冻结请求/响应类型及三个 Protocol 的完整输入、输出和有限错误 | Closed（第 3 轮） |
| `REV-BQCOM-007` | S1 | 固定流程要求配置收紧输入，但既有 request mapper 未接收 settings，实施可能跳过分页/时间/过滤/排序约束 | 固定 `map(TInput, BusinessActionSettings)`，并在 definition/handler 流程中作为唯一 wire request 入口 | Closed（第 3 轮） |
| `REV-BQCOM-008` | S1 | client 绝对 timeout 结束后仍可能在无截止保护下 decode/normalize，迟到或昂贵解析可进入投影 | 增加通用 bound handler，以同一绝对截止和阶段前后检查覆盖 mapper 至 normalizer | Closed（第 3 轮） |
| `REV-BQCOM-009` | S2 | configuration source、canonical snapshot 字段与哈希规则未定义，重启/顺序变化可能产生不一致审计身份 | 固化 source/snapshot DTO、严格解析、canonical JSON、SHA-256 和敏感字段排除 | Closed（第 3 轮） |
| `REV-BQCOM-010` | S2 | 组合根只说创建 client，未定义中途失败和 shutdown 的回收顺序，可能泄漏连接或冻结半有效 registry | 固化按 service key 创建、失败逆序关闭、未冻结 registry 和 shutdown 恰好关闭一次 | Closed（第 3 轮） |

第二轮修复仍不构成评审通过；下一轮须从 grounding 可判定性、字段转换和结果契约重新全量检查。

### 18.3 第 3 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-BQCOM-011` | S1 | “事实句”和 token 只有目标描述，没有句段、marker、canonical token 或 truncated 词表算法，grounding 测试无法避免各自解释 | 固定句段扫描、两个精确前缀、marker 集合、逐句 token 和 completeness 禁词算法 | Closed（第 4 轮） |
| `REV-BQCOM-012` | S1 | date/decimal 转换接受 string 且 bool 可被当成 int，破坏 field definition 的强类型边界；文本/标识控制字符也未闭合 | 六转换改为 exact type，固定整数范围、Unicode 控制/Bidi、date/datetime 和 Decimal 算法 | Closed（第 4 轮） |
| `REV-BQCOM-013` | S1 | projector 返回未定义的第二套 `BusinessEgressProjection`，同时“本地结果不可返回”在当前 required user result/answer mode 下不可达 | 直接返回核心 `ModelEgressResult`；明确两个 answer mode 都可本地返回，business common 不生成 `model_egress_denied` | Closed（第 4 轮） |
| `REV-BQCOM-014` | S2 | Global policy 只有名称且示例 snapshot 不符合已定义 SHA-256，实施可能自创分类放行或快照格式 | 固定 policy 字段、永久拒绝分类和只收紧上限；示例改为 64 位十六进制 snapshot | Closed（第 4 轮） |

第三轮修复仍不关闭任何门禁；自然语言 grounding 的剩余能力边界继续作为显式风险，不将结构校验夸大为语义证明。

### 18.4 第 4 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-BQCOM-015` | S1 | `AuthorizedRecordBatch` 未定义，用户结果也没有字段/coverage/JSON 结构，无法证明最小结果与核心 domain result 一致 | 固定三个 service-result variant、coverage 不变量、user record 和 `to_domain_result()` JSON | Closed（第 5 轮） |
| `REV-BQCOM-016` | S1 | role 缺失/未知/格式错误只写“拒绝”，调用方可能在 401/403 间漂移，且混合已知+未知 role 可能部分放行 | 固定 token 认证失败401；已验证 user token 的 role 集异常整体403；领域调用均为0 | Closed（第 5 轮） |
| `REV-BQCOM-017` | S1 | user result 只写“有界”，没有与核心 `max_domain_result_bytes` 交叉校验，可能让业务成功最终变为 `core.invalid_result` | 增加业务 user-result 上限、启动交叉约束、canonical 计数和固定超界失败 | Closed（第 5 轮） |
| `REV-BQCOM-018` | S1 | codec/normalizer 仍接收所有 HTTP status，域实现可把 401/403/404 等解释成不同结果，破坏公共失败矩阵 | 增加 codec 前 common status mapper；域 codec/normalizer 只处理 2xx | Closed（第 5 轮） |

第四轮修复仍为待终审状态；严格校验和发现关闭记录均不提前替代第 5 轮全量复评。

### 18.5 第 5 轮冻结发现、修复与终审

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-BQCOM-019` | S1 | tokenizer 会在 `***1234` 和 `-12.30` 已命中值内再次提取 `1234/12.30`，导致合法 grounding 被误拒；fact text 与 answer 也未使用同一 token 化算法 | 固定同一 tokenizer、canonical display text、掩码优先级和已占 span 不重复提取 | Closed（第 5 轮修复后全量复核） |
| `REV-BQCOM-020` | S1 | filter/sort 的代码允许集合和 204 无正文语义不存在，contract limits 未定义，required 同时由 action tuple/field flag 表达，配置/结果无法确定性验证 | 增加 filter/sort 集合、精确 limits 与 204/400/404 semantics；required 只保留 action tuple；每个所选字段强制恰一 transform | Closed（第 5 轮修复后全量复核） |
| `REV-BQCOM-021` | S2 | 组合根提到域 provider 和 support snapshot，却没有公共方法/字段契约，子 L2 可能各自创建 client 或直接注册动作 | 固定 `BusinessDomainProvider` 三方法、fragment 同域约束、support snapshot 字段及 client/registration 禁项 | Closed（第 5 轮修复后全量复核） |

修复后重新从上位约束、身份/配置单一权威、JWT/Authority、HTTP 出站、状态/结果、
字段/转换、safe payload/grounding、绝对截止、组合根、实现签名、测试和开放门禁全量
复核；未发现新的 S0/S1/S2，`REV-BQCOM-001`～`021` 全部关闭。评审结论为 Approved，
设计具备实施就绪条件，但 `BQ-GATE-002` 仍为 Open，因此当前不构成代码实施授权；本结论
也不证明共享安全、两域最终授权、真实业务接口或真实数据出域已经具备。

### 18.6 第三批聚焦一致性复核

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-BQCOM-022` | S1 | Transaction 必须验证响应 page/size/records 没有超过当前请求及配置收紧值，但 v0.2 `decode_success(response)` 无原请求参数；若 codec 以实例字段保存“上次请求”，并发响应会串扰并可能接纳越界结果 | 将公共签名改为 `decode_success(*, request, response)`；bound handler 在同一调用栈传递冻结 `TWireRequest`，禁止 codec 请求期可变状态，并补充交错并发/回显不匹配测试 | Closed（聚焦修复后复核） |

聚焦修复只扩大纯函数的显式输入，不改变动作身份、HTTP 请求、状态矩阵、授权、出域、调用次数或公开业务契约。重新复核 `BusinessActionDefinition`、mapper/codec/handler 顺序、绝对截止、并发隔离、Employee/Transaction 适配点和测试追踪后未发现新的 S0/S1/S2，故本文保持 Approved；`BQ-GATE-002` 及全部真实业务/出域门禁保持 Open。

## 19. 实施前检查

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
- [x] 五轮独立正式评审及第三批聚焦一致性复核已关闭全部 S0/S1/S2。
- [ ] 用户另行授权实施并关闭本切片 `BQ-GATE-002`。

## 20. 当前结论

- 本文版本：v0.3。
- 文档状态：Approved。
- 评审状态：五轮独立评审及聚焦一致性复核通过，`REV-BQCOM-001`～`022` 全部关闭。
- 实施状态：未实施。
- 生效状态：未生效。
- 是否可作为实现依据：否；设计已具备实施就绪条件，但 `BQ-GATE-002`、`SA-GATE-004/005/006` 均为 Open。
- 确定性文档校验：已通过，0 errors、0 warnings；不替代独立正式评审或外部权限证据。
- 当前只允许文档、合成契约和 fake 推演；不允许修改共享安全/业务服务、启用真实动作或外发真实业务数据。
