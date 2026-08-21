# [L2_00_03] 单体 Agent 用户角色 Authority Converter 详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_00_03` |
| 文档名称 | 单体 Agent 用户角色 Authority Converter 详细设计 L2 |
| 文档层级 | L2 详细设计 |
| 版本 | v0.4 |
| 文档状态 | Approved |
| 日期 | 2026-08-20 |
| 上位文档 | [`L1_00`](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) v0.2（已评审/已通过；治理本文） |
| 关联架构 | [`L1_01`](L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) v0.3、[`L1_02`](L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md) v0.2 |
| 直接输入 | `auth-service` 用户 JWT claim 契约；[`L2_01_01`](L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) v0.6；[`L2_02_00`](L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md) v0.5；[`L2_02_01`](L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v0.5；[`L2_02_02`](L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md) v0.6 |
| 适用范围 | `auth-service` 用户 JWT 的 `token_type`、`role` claim；`common-security` Servlet/Reactive Authority 转换；显式选择该转换器的 Knowledge、Employee、Transaction Provider 入口 |
| 不包含 | 改变角色分配、用户名授权、全局替换现有 Resource Server 默认转换器、业务域资源/字段授权、目标部署或生产生效门禁关闭 |
| 当前实现事实 | 共享 Converter、自动配置和三个 Provider 的 endpoint-scoped opt-in 已完成五轮针对性代码对照复核—修改；`AUTH-GATE-001` 已按本地证据关闭，`AUTH-GATE-002` 已按组合式真实 JWT 证据关闭；该事实不等于目标部署或生产生效 |
| 是否可作为实现依据 | 是 |
| 实施依据说明 | 可作为共享 Converter、Provider opt-in 和当前受控配置真实 JWT 角色语义的维护依据；目标部署/生产生效仍须满足 `AUTH-GATE-003` 及各域发布门禁 |
| 当前允许实施范围 | 不新增共享 Authority 功能；仅允许在另行授权后维护既有 Converter、复核 Provider 自身契约，或执行受 `AUTH-GATE-003`/领域门禁控制的目标环境核验，不得改变公开契约或角色范围 |
| 当前允许动作 | 本地静态检查、单元/契约/非 live 集成测试、代码对照设计复核；在既有公开契约内修复不一致项须另行取得代码修改授权 |
| 当前禁止动作 | 改变 `auth-service` 角色分配或 JWT wire；全局替换默认 Converter；关闭真实集成/发布门禁；修改数据库结构；扩大业务动作、角色或字段契约 |

> 本文固定共享“已验证用户 JWT claim → 有限 Authority”语义，不把业务域最终授权搬入 `common-security`。`auth-service` 是用户与角色分配权威；`common-security` 是 claim 词法校验与 Authority 映射权威；各 Provider 仍在目标入口和本域 Guard 执行最终动作授权。

## 2. 修改历史

| 版本 | 日期 | 位置 | 原因 | 变更 |
|---|---|---|---|---|
| v0.1 | 2026-08-03 | 全文 | 统一 Authority Converter 阻断三个 Provider 实施 | 固定 Servlet/Reactive 具名 Bean、严格角色语义、Provider opt-in 边界和实施触点 |
| v0.2 | 2026-08-03 | 1～15 章及相关治理文档 | 五轮独立评审—修复 | 按当前仓库重建实现基线，补齐消费者/覆盖契约、实现状态、测试追踪、阶段门禁和运行属性，原子同步 L0/L1/相关 L2/P3/索引；第 5 轮无剩余 S0/S1/S2，状态置为 Approved |
| v0.3 | 2026-08-03 | 1、2、5、14、15 章及 P3 | 五轮针对性代码对照复核—修改后的状态同步 | 收紧原始 claim 类型，补齐发行、Servlet/Reactive 委托、Provider opt-in、拒绝零调用和敏感信息测试；`VAL-AUTH-001/002` 通过并关闭 `AUTH-GATE-001`，真实集成与发布门禁保持 Open |
| v0.4 | 2026-08-20 | 1～2、5、13～15章及相关治理文档 | 真实JWT证据与门禁状态聚焦同步 | 采用生产者映射、三Provider按角色语义消费及负向矩阵的组合证据关闭当前受控配置`AUTH-GATE-002`；`AUTH-GATE-003`继续Open，不改变角色、Converter、Provider或历史证据 |

## 3. 背景、目标与范围

### 3.1 背景与根因

`auth-service` 已在用户 JWT 中输出精确字符串 `token_type=user` 与数组型 `role` claim。Spring Security 默认 JWT 转换只处理 scope，不能稳定产生 `ROLE_ADMIN`、`ROLE_VIEWER`。如果三个 Provider 分别解析 claim，会形成重复安全权威，并可能对未知角色、混合角色或大小写漂移采取不同策略。

当前仓库已经形成共享 Converter 和三个 Provider 的候选实现。本次详细设计正式评审的目标不是为代码补写合理性，而是固定唯一契约、核对当前实现事实、暴露不一致并为后续真实 JWT 集成提供可验证门禁。

### 3.2 目标与验收行为

| 需求 ID | 目标或可观察行为 | 验收标准 |
|---|---|---|
| `REQ-AUTH-001` | 合法用户 token 的有限角色确定性映射 | `ADMIN`、`VIEWER` 或两者组合分别产生精确 `ROLE_ADMIN`、`ROLE_VIEWER`；去重且顺序稳定 |
| `REQ-AUTH-002` | Servlet 与 Reactive 使用同一映射权威 | Reactive 只适配基础 Converter；相同 JWT 的 Authority 和失败类别一致 |
| `REQ-AUTH-003` | Provider 精确、显式消费稳定 Bean | 三个目标 endpoint 使用固定 Bean 名称；非目标 endpoint 保持原安全链 |
| `REQ-AUTH-004` | 非法 token 类型与非法角色失败关闭 | 非 user token 为认证失败；非法 role 不产生 Authority；目标入口在领域调用前返回 401/403 |
| `REQ-AUTH-005` | 业务域保留最终动作授权 | Converter 不按用户名、资源或字段授权；Provider Guard 不重新解析 role claim |

### 3.3 范围内

- `token_type`、`role` 的严格输入契约及 Authority 输出契约。
- `common-security` Servlet/Reactive 具名 Bean 与自动配置边界。
- Knowledge、Employee、Transaction 目标 endpoint 的显式 opt-in 与最终动作 Guard 协作。
- 本地单元、自动配置、Provider 安全链、拒绝零调用和 fallback 兼容验证。

### 3.4 范围外与非目标

- 角色管理界面、动态角色字典、租户/资源 ACL、字段可见性和数据库授权。
- 改变现有 JWT 字段、角色分配或 `auth-service` 用户配置。
- 将严格用户角色 Converter 全局应用到 service-token 或非 Agent 入口。
- 建设权限中心、独立审计平台、缓存、重试或生产级高可用机制。

## 4. 上位约束与追踪关系

### 4.1 约束映射

| 约束 ID | 权威来源 | 约束 | 本文落实 | 偏离 |
|---|---|---|---|---|
| `CON-AUTH-001` | `L1_00` 3.4、7.2、8、10.2 | JWT 签发、角色分配与 Authority 映射归 `auth-service/common-security`；Agent 不成为权限权威 | `DR-AUTH-001/004/005` | 无 |
| `CON-AUTH-002` | `L2_02_00` 角色与最终授权约束 | 首批 Provider 只消费 `ROLE_ADMIN/ROLE_VIEWER`；未知和大小写漂移失败关闭 | `DR-AUTH-002/003/007` | 无 |
| `CON-AUTH-003` | `L2_01_01` `IMPL-KRET-012` | Knowledge Servlet 消费 Bean 名称固定为 `userRoleJwtAuthenticationConverter` | `DR-AUTH-004/006` | 无 |
| `CON-AUTH-004` | `L2_02_01/02` 最终授权约束 | Employee/Transaction 业务服务执行最终角色授权，Agent Adapter 不判定角色 | `DR-AUTH-006/007` | 无 |
| `CON-AUTH-005` | 用户 2026-08-03 授权 | Servlet/Reactive 映射统一，Bean 名称稳定；不得扩大业务权限或公开契约 | `DR-AUTH-004/005/009` | 无 |

### 4.2 端到端追踪矩阵

| REQ/CON | 模块切片 | 设计规则 | 责任主体 | 契约/状态影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-AUTH-001`,`CON-AUTH-002` | claim 生产与映射 | `DR-AUTH-001/002/003` | `auth-service`、`common-security` | 集合型 role JWT 只读；生成请求级 Authority | `IMPL-AUTH-001/002` | `TEST-AUTH-000/001/002/003` | `VAL-AUTH-001` |
| `REQ-AUTH-002/003`,`CON-AUTH-003` | 自动配置 | `DR-AUTH-004/009` | `common-security` | 两个具名 Bean；无持久状态 | `IMPL-AUTH-003/004` | `TEST-AUTH-004/005` | `VAL-AUTH-001` |
| `REQ-AUTH-003/004`,`CON-AUTH-003/004` | Provider opt-in | `DR-AUTH-005/006/008` | Provider Security Chain | 目标入口 401/403；拒绝零领域调用 | `IMPL-AUTH-005/006/007` | `TEST-AUTH-006/007/008` | `VAL-AUTH-002` |
| `REQ-AUTH-005`,`CON-AUTH-001/004` | 最终动作授权 | `DR-AUTH-007` | Provider Guard | 只消费 Authentication Authority | `IMPL-AUTH-008/009/010` | `TEST-AUTH-009` | `VAL-AUTH-002` |
| `REQ-AUTH-004`,`CON-AUTH-005` | 兼容与运行 | `DR-AUTH-005/008/010` | `common-security` 与 Provider | 非目标入口不变；无重试/状态 | `IMPL-AUTH-003～010` | `TEST-AUTH-005/006/007/008` | `VAL-AUTH-001/002` |

## 5. 当前实现基线与最小变更

### 5.1 已核实实现事实

- `auth-service/src/main/java/com/dylan/authcenter/service/JwtService.java` 已签发 `token_type=user` 和数组型 `role`；`auth-users.yml` 当前将 `admin/dylan` 配为 `ADMIN`、`viewer_t` 配为 `VIEWER`。`AuthControllerTest` 已直接绑定该配置并验证三名用户的原始字符串 `token_type` 与数组型 `role` wire。
- `common-security` 已存在并验证 `UserRoleJwtAuthenticationConverter`、`UserRoleAuthorityAutoConfiguration` 和自动配置导入项；用户 token 只接受原始字符串 `token_type=user`，role 只接受非空 `List`，非法或混合值失败关闭，Reactive Bean 仅委托 Servlet Bean。
- `es-query-service`、`employee-service`、`mq-procedure-service` 已分别在 Knowledge、Employee detail、Transaction search 的 endpoint-scoped 安全链中显式注入对应具名 Bean。
- 三个 Provider Guard 均从 `Authentication#getAuthorities()` 做最终动作检查，不重新解析原始 `role`；其中 Knowledge 额外拒绝有限集合之外的 Authority。
- 三个 Provider 的安全测试已覆盖共享具名 Bean、ADMIN/VIEWER 允许、非法角色 403、service/missing token 401、拒绝零领域调用和敏感值不进入本地响应/捕获日志。
- `VAL-AUTH-001` 的 `auth-service/common-security` 回归 26 项通过，`VAL-AUTH-002` 的 `common-security/es-query-service/employee-service/mq-procedure-service` 回归 125 项通过；当前证据仍为本地代码和合成 JWT，不包含 `auth-service` 真实签发 token 经网络到三个 Provider 的集成证据。

### 5.2 当前差距

1. 共享 Converter 与三个 Provider opt-in 已完成五轮针对性代码对照复核—修改；`TEST-AUTH-000/002/003/005/010` 缺口已处理，`VAL-AUTH-001/002` 通过，`AUTH-GATE-001` 已关闭。
2. 当前受控配置的真实 JWT 角色语义已由组合证据闭环：`auth-service` 证明 admin/dylan/viewer_t 的角色签发，Employee/Transaction 证明实际三用户 token 消费，Knowledge 证明实际 ADMIN/VIEWER 角色消费，三个 Provider 均覆盖 invalid/service-token、拒绝零调用与日志脱敏；`AUTH-GATE-002` 已关闭。
3. 三个 Provider 当前实现/受控集成均已完成；目标部署配置、Bean来源、未授权覆盖与生产生效仍由 `AUTH-GATE-003` 及各业务域发布门禁控制。历史停止记录仅作审计，不再代表当前阻断。

### 5.3 最小方案及未采用方案

| 方案 | 结论 | 理由 |
|---|---|---|
| 共享一个严格基础 Converter，Reactive 仅适配它，Provider 显式 opt-in | 采用 | 一处拥有词法映射，兼容 Servlet/Reactive，且不改变默认链 |
| 三个 Provider 各自解析 `role` | 不采用 | 重复安全权威，失败语义容易漂移 |
| 全局替换默认 Resource Server Converter | 不采用 | 会改变 service token 和非目标端点，影响范围过大 |
| 在 Agent Adapter 判断角色 | 禁止 | 违反业务服务最终授权边界 |
| 新建动态角色配置或权限中心 | 不采用 | 本期角色有限，属于过度设计 |

本次文档修订不授权代码、JWT wire、数据库或公开 API 变更。

## 6. 关联资源、责任与依赖边界

### 6.1 关联资源与责任边界

| 资源 | 角色 | 本文使用方式 | 对方权威 | 数据/状态所有权 | 修改权限 |
|---|---|---|---|---|---|
| `L1_00` | parent | 约束 JWT/Authority 所有权和 Agent 非职责 | 核心运行与入口身份边界 | 不持有用户角色 | 本次仅授权原子同步 L2 清单/状态，不重构架构 |
| `auth-service` JWT 代码/配置 | external contract | 只读确认 `token_type`、`role` wire 和首批用户角色 | 用户、角色分配与 JWT 签发 | 用户/角色事实 | 只读 |
| `L2_01_01` | peer consumer | 固定 Knowledge Servlet Bean 名称和启用失败语义 | Knowledge typed endpoint 与读授权 | Knowledge Profile/读决定 | 仅原子同步 Converter 前置事实 |
| `L2_02_00/01/02` | peer consumers | 固定有限 Authority 与业务域最终授权边界 | Business 配置、Employee/Transaction 动作与字段可见性 | 业务数据/动作权限 | 仅原子同步 Converter 前置事实 |
| `common-security` 代码/测试 | implementation/test evidence | 核对路径、签名、映射与自动配置 | 当前实现事实，不反向覆盖设计权威 | 请求级 Authentication | 只读 |
| 三个 Provider 代码/测试 | implementation/test evidence | 核对 opt-in、Guard 和 fallback | 各 Provider 最终动作授权 | 本域请求/数据 | 只读 |

### 6.2 责任分解

| 组件 | 唯一责任 | 明确不负责 | 输入/输出 |
|---|---|---|---|
| `auth-service` | 用户认证、角色分配、签发用户 JWT | Spring Authority 映射、业务动作授权 | 用户事实 → 已签名 JWT |
| Resource Server/JWT Decoder | 验证签名、有效期和基础 token | 角色映射、业务动作授权 | Bearer token → 已验证 `Jwt` 或 401 |
| `UserRoleJwtAuthenticationConverter` | 验证 `token_type=user` 并把有限 `role` 映射为 Authority | 用户目录、资源/字段权限、HTTP 路由 | `Jwt` → `AbstractAuthenticationToken` 或认证异常 |
| `UserRoleAuthorityAutoConfiguration` | 发布两个稳定名称并复用同一基础 Converter | 自动修改任一安全链 | Bean 定义；无请求状态 |
| Provider Security Chain | 仅在目标 endpoint 选择具名 Converter，并在 Controller 前执行角色门槛 | 复制 role 解析、改变 fallback 链 | HTTP/JWT → allow、401 或 403 |
| Provider Guard | 对已认证用户执行本域最终动作授权 | 修正、补全或猜测角色 claim | `Authentication` → allow 或本域 403 |

### 6.3 依赖方向与禁止路径

```text
auth-service JWT
  → Provider Resource Server/JwtDecoder
      → common-security UserRoleJwtAuthenticationConverter
          → Provider endpoint-scoped Security Chain
              → Provider Guard
                  → Service/Mapper/ES
```

- `common-security` 不依赖任何 Provider、Agent Runtime 或业务数据模块。
- Provider 只依赖具名 Bean 的 Spring `Converter` 契约和有限 Authority 字符串；不得调用 `auth-service` 查询用户角色。
- Agent Adapter 只透传原始用户 JWT，不依赖 Converter 实现，也不根据角色预授权。
- Converter、Security Chain 和 Guard 均不得形成重试、缓存或第二套身份状态。
- 禁止依赖方向包括：`common-security → Provider/Agent`、Provider Guard → `auth-service` 用户目录、Agent Adapter → Converter 实现。
- 禁止绕过路径包括：Provider 自行解析 role、目标入口回退默认 scope Converter、Controller 在专用安全链前调用 Service/Mapper/ES、Agent 预判角色后替代业务域授权。
- 不允许通过回调、反向依赖或共享可变角色集合形成第二套映射权威。

### 6.4 单一权威与覆盖规则

允许同名 Bean 覆盖仅用于 Spring 应用显式提供等价实现；它不是扩展角色或改变失败语义的通道。覆盖实现必须完整满足 `DR-AUTH-001～005/009` 并通过同一共享契约测试和三个 Provider 安全链测试。任何不同名称的第二套用户角色 Converter、同名但语义不等价的覆盖、Provider 自行解析 role，均视为不受支持配置并必须失败关闭或阻止发布。

当前仓库未发现三个 Provider 定义同名覆盖 Bean；它们均消费 `common-security` 自动配置产生的候选。

### 6.5 内聚与耦合判断

角色词法校验、有限枚举和 Authority 构造聚合在 `common-security`，因为三类 Provider 需要完全相同的输入语义；具体 endpoint、资源、动作和字段权限继续留在各 Provider，避免共享模块成为业务权限中心。Provider 依赖 Spring `Converter` 和 Authority 字符串这一窄契约，不依赖用户目录或 Converter 私有实现。新增两个具名 Bean 是保护 Servlet/Reactive 共享语义和测试接缝所需的最小抽象，不引入动态角色配置、远程权限查询或额外服务。

## 7. 核心契约

### 7.1 输入 claim

| claim | 允许值 | 失败语义 |
|---|---|---|
| `token_type` | 精确字符串 `user` | 缺失、非字符串、非 `user` 或大小写漂移：认证失败，目标入口 HTTP 401 |
| `role` | 非空 JSON array；每项仅允许精确字符串 `ADMIN`、`VIEWER` | 缺失、null、空数组、字符串、嵌套值、空白、类型错误、未知、大小写漂移或已知与未知混合：不产生任何 Authority，目标入口 HTTP 403 |
| `sub` | 由已验证 JWT 提供 | 不参与角色判断；不得按 `admin`、`dylan`、`viewer_t` 等用户名授权 |

JWT 签名、有效期和基础 token 验证先于 Converter；Converter 不重复验签，也不接受未经 Resource Server 验证的外部输入。

### 7.2 输出 Authority

| role 集合 | Authority 集合 |
|---|---|
| `ADMIN` | `ROLE_ADMIN` |
| `VIEWER` | `ROLE_VIEWER` |
| `ADMIN, VIEWER`，任意顺序或重复 | `ROLE_ADMIN, ROLE_VIEWER`，去重且固定顺序 |

Converter 不保留默认 scope Authority，不接受字符串型、逗号分隔或嵌套 role，不补齐默认角色。任一非法 role 项使完整 Authority 集为空，不能只保留已知角色。

### 7.3 具名 Bean 与覆盖契约

| Bean 名称 | 精确类型 | 消费方 | 覆盖约束 |
|---|---|---|---|
| `userRoleJwtAuthenticationConverter` | `Converter<Jwt, AbstractAuthenticationToken>` | Servlet SecurityFilterChain | 仅允许语义完全等价的显式 Bean；必须通过共享契约测试 |
| `reactiveUserRoleJwtAuthenticationConverter` | `Converter<Jwt, Mono<AbstractAuthenticationToken>>` | Reactive SecurityWebFilterChain | 必须适配上述基础 Bean，不得复制映射规则 |

Bean 缺失、类型不兼容或同名覆盖未通过契约验证时，不得启用目标 Provider；禁止回退 Spring 默认 scope Converter。

### 7.4 接口与契约设计

本文不新增或修改 HTTP endpoint、请求/响应 DTO、OpenAPI、数据库或跨语言 wire。唯一共享代码契约是两个具名 Spring Bean 及其 `Converter` 泛型类型；JWT wire 由 `auth-service` 既有 `token_type`/`role` claim 产生。401/403 继续由 Spring Security 和各 Provider 既有异常边界形成，本文不规定新的错误正文或错误码。任何改变 claim 名称/类型、Bean 名称/类型、有限角色或 HTTP 类别的修改均是不兼容变更，必须同步 `auth-service`、三个 Provider、测试和本文并重新评审。

## 8. 详细功能与设计规则

| 规则 ID | 规则 | 责任主体 | 外部可观察结果 |
|---|---|---|---|
| `DR-AUTH-001` | 先精确验证 `token_type=user`，失败抛 `OAuth2AuthenticationException`，不得降为匿名角色 | 基础 Converter | 目标入口 401，领域调用为 0 |
| `DR-AUTH-002` | role 仅在“非空数组且每项属于有限枚举”时产生 Authority；任一非法项令完整集合为空 | 基础 Converter | 目标入口 403，领域调用为 0 |
| `DR-AUTH-003` | Authority 去重并固定 ADMIN 后 VIEWER；不保留 scope Authority | 基础 Converter | 相同角色集合结果确定 |
| `DR-AUTH-004` | 自动配置提供两个稳定名称；Reactive 通过 `ReactiveJwtAuthenticationConverterAdapter` 复用基础 Bean | 自动配置 | Servlet/Reactive 语义相同 |
| `DR-AUTH-005` | 仓库默认 Servlet/Reactive Resource Server 链不得自动切换为严格 Converter | 自动配置/Provider | 非目标端点安全语义保持原状 |
| `DR-AUTH-006` | Knowledge、Employee、Transaction 只在各自目标 endpoint 的高优先级安全链显式选择具名 Bean | Provider Security Chain | 目标入口按有限角色收紧 |
| `DR-AUTH-007` | Provider Guard 只从 `Authentication#getAuthorities()` 判断本域动作，不读取或重新解析原始 role；可复核 `token_type=user` | Provider Guard | 本域最终允许或 403 |
| `DR-AUTH-008` | 401/403 时目标 Controller、Service、Mapper、ES 调用均为 0；错误体不得包含 token、claim、用户名或业务正文 | Provider 安全边界 | 失败关闭且无敏感泄漏 |
| `DR-AUTH-009` | 同名覆盖必须与基础契约语义等价并通过共享/Provider 契约测试；不同名第二套映射和语义漂移禁止发布 | 应用组合根/维护者 | 未验证覆盖不得生效 |
| `DR-AUTH-010` | 转换纯内存、无持久状态、无远程调用、无重试；异常不得转换为允许结果 | 基础 Converter | 每次请求独立、失败终止 |

## 9. 核心流程与失败终态

### 9.1 正常流程

1. Resource Server 验证 JWT 签名、有效期和基本格式；失败返回 401。
2. 目标 endpoint 的专用安全链调用具名 Converter。
3. Converter 精确验证 `token_type=user`。
4. Converter 严格校验完整 role 集并产生有限 Authority。
5. 安全链执行 `hasAnyAuthority("ROLE_ADMIN", "ROLE_VIEWER")`。
6. Controller 进入后，本域 Guard 对同一 `Authentication` 执行最终动作检查；允许后才调用 Service/Mapper/ES。

### 9.2 失败终态

| 失败类型 | 触发条件 | 内部表示 | HTTP | 下游调用 | 重试/状态影响 |
|---|---|---|---:|---:|---|
| JWT 缺失、签名或有效期失败 | Resource Server 验证失败 | OAuth2 认证失败 | 401 | 0 | 不重试；无状态 |
| 非 user token | `token_type` 缺失、类型错、非 user | `OAuth2AuthenticationException` | 401 | 0 | 不重试；无状态 |
| 角色无效 | role 缺失、类型错、空、未知、大小写或混合未知 | 空 Authority | 403 | 0 | 不重试；无状态 |
| 目标动作拒绝 | 有限 Authority 通过 Converter，但本域 Guard 拒绝 | 本域 forbidden | 403 | Guard 后调用为 0 | 不重试；无状态 |
| Bean 装配无效 | 目标 Provider 启用但 Bean 缺失/类型不符 | Spring 启动失败 | 无运行态响应 | 0 | 修复配置并重启；禁止默认 Converter 回退 |

Converter 不处理下游 4xx/5xx，不产生业务成功结果，也不改变 Controller 错误契约。调用方只能依赖 HTTP 类别，不依赖包含 claim 的错误正文。

## 10. 实现落点与关键签名

| 实现 ID | 状态 | 类型 | 路径与符号 | 输入/输出与责任 | 直接消费者 | 规则 |
|---|---|---|---|---|---|---|
| `IMPL-AUTH-001` | 已存在 | JWT 生产者 | `auth-service/src/main/java/com/dylan/authcenter/service/JwtService.java`；`String generateToken(String userId)` | 从 `UserService` 读取角色并签发集合型 `role`、`token_type=user`；本文只读消费 | 三个 Provider Resource Server | `DR-AUTH-001/002` |
| `IMPL-AUTH-002` | 已存在 | Java Converter | `common-security/src/main/java/com/dylan/common/security/UserRoleJwtAuthenticationConverter.java`；`public AbstractAuthenticationToken convert(Jwt jwt)` | 同步、无远程调用；返回 `JwtAuthenticationToken` 或抛认证异常；非法 role 返回空 Authority | Servlet Bean、Reactive Adapter | `DR-AUTH-001/002/003/010` |
| `IMPL-AUTH-003` | 已存在 | Java 自动配置 | `common-security/src/main/java/com/dylan/common/security/UserRoleAuthorityAutoConfiguration.java`；`Converter<Jwt,AbstractAuthenticationToken> userRoleJwtAuthenticationConverter()`、`Converter<Jwt,Mono<AbstractAuthenticationToken>> reactiveUserRoleJwtAuthenticationConverter(...)` | 发布两个具名 Bean；Reactive 适配基础 Bean；不注册安全链 | 三个 Provider 配置 | `DR-AUTH-004/005/009` |
| `IMPL-AUTH-004` | 已存在 | 自动配置注册源 | `common-security/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` | 注册 `UserRoleAuthorityAutoConfiguration`；无配置键 | Spring Boot 应用上下文 | `DR-AUTH-004/005` |
| `IMPL-AUTH-005` | 已存在 | Servlet SecurityFilterChain | `es-query-service/src/main/java/com/dylan/esquery/config/KnowledgeSearchConfiguration.java`；`knowledgeSearchSecurityFilterChain(...)` | `/es/knowledge/**` 启用时注入 `userRoleJwtAuthenticationConverter` | Knowledge Controller | `DR-AUTH-006/008` |
| `IMPL-AUTH-006` | 已存在 | Servlet SecurityFilterChain | `employee-service/src/main/java/com/dylan/employee/security/EmployeeDetailSecurityConfiguration.java`；`employeeDetailSecurityFilterChain(...)` | 仅 GET Employee detail 匹配器注入 Servlet Bean；fallback 链保持原行为 | Employee Controller | `DR-AUTH-005/006/008` |
| `IMPL-AUTH-007` | 已存在 | Reactive SecurityWebFilterChain | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/TransactionSearchSecurityConfiguration.java`；`transactionSearchSecurityWebFilterChain(...)` | 仅 `POST /txn/search` 注入 Reactive Bean；fallback 链保持原行为 | Transaction Controller | `DR-AUTH-005/006/008` |
| `IMPL-AUTH-008` | 已存在 | Knowledge Guard | `es-query-service/src/main/java/com/dylan/esquery/service/KnowledgeReadAccessGuard.java`；`KnowledgeReadDecision authorize(Authentication,String,String)` | 复核 user/有限 Authority 与知识 Profile；不重解析 role | Knowledge Service | `DR-AUTH-007/008` |
| `IMPL-AUTH-009` | 已存在 | Employee Guard | `employee-service/src/main/java/com/dylan/employee/security/CapabilityAccessGuard.java`；`void requireEmployeeRead(Authentication)` | 复核 user 和 Employee read Authority | Employee Controller | `DR-AUTH-007/008` |
| `IMPL-AUTH-010` | 已存在 | Transaction Guard | `mq-procedure-service/src/main/java/com/dylan/mqprocedureserver/security/CapabilityAccessGuard.java`；`void requireTransactionRead(Authentication)` | 复核 user 和 Transaction read Authority | Transaction Controller | `DR-AUTH-007/008` |

普通私有解析辅助方法不构成共享契约；只要保持“完整集合严格校验、无状态、无副作用”不变量，不在本文冻结其签名。

## 11. 配置、运行属性、兼容与回滚

### 11.1 配置和启动

- 本设计不增加配置键；允许角色是代码级有限枚举，不能由环境变量扩大。
- 自动配置新增 Bean 本身不改变 endpoint；只有专用安全链显式注入后目标入口才收紧。
- Provider 启用而具名 Bean 缺失或类型不兼容时必须启动失败，不得回退默认 scope Converter。
- KRET 的 `enabled=false` 保持 Knowledge endpoint 不创建；Employee/Transaction 回滚需回退对应专用安全链并重新部署。

### 11.2 数据、状态、并发与韧性适用性

| 维度 | 结论 |
|---|---|
| 数据与迁移 | 不适用：Converter 不创建、读取或迁移数据库数据，不修改 JWT 持久化结构 |
| 状态与并发 | 请求级无状态；只使用局部变量和不可变 Authority 结果，无共享可变状态、锁或事务 |
| 超时与取消 | 不适用：无 I/O 或异步工作；Reactive Bean 仅包装同步结果 |
| 重试、幂等与补偿 | 不适用：纯转换失败即终止；任何层不得重试或补偿认证/授权拒绝 |
| 性能与容量 | 常量级有限角色遍历；不设置独立 SLO、缓存或限流，受 Provider 入口治理 |
| 降级 | 不允许把默认 scope Converter、服务身份或宽松角色过滤作为降级 |

### 11.3 数据生命周期与迁移设计

不适用：本文只读取单次请求中的已验证 JWT，并创建同请求生命周期的 `Authentication`/Authority 集；不创建数据库、缓存、文件或消息，不改变 `auth-service` 的用户/角色持久化结构，也没有迁移、回填、保留、删除或回滚数据动作。Provider 业务数据所有权保持不变。

### 11.4 兼容与回滚

- 现有默认安全链和 service-token 语义保持不变；三个目标 endpoint 的行为属于显式收紧。
- 回滚顺序：先禁用 Agent/Knowledge 真实调用，再回退目标 Provider 专用链，最后才移除共享 Bean。
- 回滚不得改用 Agent 侧角色判断，也不得把 401/403 改为允许结果。
- 若替换共享实现，所有消费者必须在同一版本窗口通过共享与 Provider 契约测试；不支持混合语义版本。

## 12. 权限、审计、日志与敏感信息

- 主体来自已验证 JWT；Converter 只判断 `token_type` 与完整 role 集，不按用户名授权。
- 资源和动作由 Provider endpoint/Guard 拥有；字段与数据范围仍由业务域或知识读取策略拥有。
- Converter 不输出 token、claim、subject 或原始 role，不单独记录请求日志或审计事件。
- 如 Provider 现有日志记录该请求，只允许 endpoint、允许/拒绝类别、现有 correlation ID 和必要耗时；不得记录 JWT、subject、role 原值或业务正文。本文不要求新增日志依赖或独立审计事件。
- 共享 Converter 不单独发审计事件，避免一次拒绝被重复记录；Provider HTTP 安全边界与本域 Guard 分别保留既有访问/域内拒绝证据。

## 13. 测试与验证设计

### 13.1 测试设计

| 测试 ID | 状态 | 路径/用例 | 设计规则 | 测试意图与关键断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-AUTH-000` | 建议修改 | `auth-service/src/test/java/com/dylan/authcenter/controller/AuthControllerTest.java` | `DR-AUTH-001/002` 的输入前提 | 保留 admin/viewer_t 断言并补充 dylan；解码后 `token_type=user`、`role` 为精确数组值 | 角色遗漏、字符串化、大小写或用户配置/wire 漂移 |
| `TEST-AUTH-001` | 已存在 | `common-security/src/test/java/com/dylan/common/security/UserRoleJwtAuthenticationConverterTest.java#mapsFiniteRolesWithStableOrderAndDeduplication` | `DR-AUTH-002/003` | ADMIN、VIEWER、双角色、乱序、重复得到精确有序 Authority | Authority 缺失、多余、重复或顺序漂移 |
| `TEST-AUTH-002` | 建议修改 | 同文件 `invalidRoleClaimFailsClosedWithNoAuthorities` | `DR-AUTH-002` | 已覆盖缺失、空、字符串、嵌套、空白、大小写和混合未知；补齐数值/布尔元素 | 任一非法输入产生 Authority |
| `TEST-AUTH-003` | 建议修改 | 同文件 `nonUserTokenIsAnAuthenticationFailure` | `DR-AUTH-001` | 已覆盖缺失、service、大小写；补齐非字符串 claim | 返回 Authentication 或其他宽松结果 |
| `TEST-AUTH-004` | 已存在 | `common-security/src/test/java/com/dylan/common/security/UserRoleAuthorityAutoConfigurationTest.java` | `DR-AUTH-004` | 两个 Bean 名称存在且相同 JWT 语义一致 | Bean 缺失、重复规则或结果不同 |
| `TEST-AUTH-005` | 建议新增 | `common-security` 自动配置测试与三个 Provider 应用上下文检查 | `DR-AUTH-005/009` | 验证等价覆盖约束、当前组合根无未授权同名覆盖 | 未验证覆盖进入启用 Provider |
| `TEST-AUTH-006` | 已存在 | `es-query-service/src/test/java/com/dylan/esquery/config/KnowledgeSearchSecurityIntegrationTest.java` | `DR-AUTH-006/008` | ADMIN/VIEWER allow；invalid role/service token 在 Controller 前拒绝；fallback 不变 | 未授权进入 Controller/ES 或非目标端点改变 |
| `TEST-AUTH-007` | 已存在 | `employee-service/src/test/java/com/dylan/employee/security/EmployeeDetailSecurityIntegrationTest.java` | `DR-AUTH-005/006/008` | 详情入口允许矩阵、拒绝零 Service 调用、fallback 兼容 | 角色绕过或非目标端点改变 |
| `TEST-AUTH-008` | 已存在 | `mq-procedure-service/src/test/java/com/dylan/mqprocedureserver/security/TransactionSearchSecurityIntegrationTest.java` | `DR-AUTH-005/006/008` | search 允许矩阵、拒绝零 Service 调用、aggregate fallback 兼容 | 角色绕过或 fallback 改义 |
| `TEST-AUTH-009` | 已存在 | `KnowledgeReadAccessGuardTest`、Employee/Transaction `CapabilityAccessGuardTest` | `DR-AUTH-007/008` | Guard 只消费 Authentication，允许有限角色、拒绝 service/无 Authority | Guard 重解析 role、扩大动作或拒绝后调用领域层 |
| `TEST-AUTH-010` | 建议修改 | 三个 Provider Security Integration Test | `DR-AUTH-008` | 对 401/403 响应及捕获日志断言不含 token、subject、role 原值、用户名或业务正文 | 任一敏感值出现在响应或日志 |

`TEST-AUTH-005` 是发布前组合根/契约验证要求；当前无独立“覆盖 Bean”自动化测试，因此不能作为已关闭的发布证据。

### 13.2 验证命令

| 验证 ID | 工作目录与命令 | 证明范围 | 预期结果 |
|---|---|---|---|
| `VAL-AUTH-001` | 仓库根：`mvn -f serviceCenter/pom.xml -pl :auth-service,:common-security -am test` | JWT 生产 claim、基础映射、Bean 名称、Servlet/Reactive 一致性 | BUILD SUCCESS，相关测试零失败 |
| `VAL-AUTH-002` | 仓库根：`mvn -f serviceCenter/pom.xml -pl :common-security,:es-query-service,:employee-service,:mq-procedure-service -am test` | 三个 Provider opt-in、Guard、拒绝零调用与 fallback 兼容 | BUILD SUCCESS，相关测试零失败 |
| `VAL-AUTH-003` | P4受控隔离环境的组合验证：`auth-service`发行测试证明admin/dylan→ADMIN、viewer_t→VIEWER；Employee/Transaction使用实际admin/dylan/viewer_t JWT；Knowledge使用实际ADMIN/VIEWER JWT；三个Provider均覆盖unknown/missing/malformed/service-token | 真实claim wire、验签、共享Bean装配、角色等价消费、401/403/allow、拒绝零领域调用和日志脱敏 | 已通过：授权由role而非username决定；无需为同一ADMIN语义在每个Provider重复dylan调用。证据分别由`WP-KRET-REAL-01`、`WP-EMP-REAL-01`、`WP-TXN-REAL-01`及auth-service发行测试提供 |

## 14. 风险与阶段门禁

### 14.1 风险

| 风险 ID | 触发 | 影响 | 控制 | 阻塞范围 |
|---|---|---|---|---|
| `RISK-AUTH-001` | 默认链全局启用严格 Converter | service token 或非目标入口被误拒 | `DR-AUTH-005`、fallback 兼容测试 | 发布 |
| `RISK-AUTH-002` | 已知+未知 role 被部分保留 | 未定义角色获得目标动作访问 | `DR-AUTH-002`、负向测试整体拒绝 | 实现/发布 |
| `RISK-AUTH-003` | Servlet/Reactive 两套解析 | 角色语义漂移 | Reactive 只适配基础 Bean | 实现 |
| `RISK-AUTH-004` | 同名 Bean 覆盖但未验证等价语义 | Provider 之间出现不同权限结果 | `DR-AUTH-009`、共享契约与组合根测试 | 发布 |
| `RISK-AUTH-005` | 局部或合成 JWT 证据被外推为目标部署已生效 | 错误宣称生产/等效环境角色链闭环 | `AUTH-GATE-002`仅按当前受控组合证据关闭；`AUTH-GATE-003`保持Open并要求目标环境Bean/配置核验 | 集成/发布 |

### 14.2 阶段门禁

| 门禁 ID | 类型 | 适用阶段/模块切片 | 控制动作 | 关闭条件与证据 | 责任方/提供方 | 最晚阶段 | 验证者与方法 | 状态 | 未关闭时允许/禁止 | 替代路径 |
|---|---|---|---|---|---|---|---|---|---|---|
| `AUTH-GATE-001` | `closure` | P3 共享 Converter/Provider opt-in 本地实现证据 | 声明现有候选与已批准设计一致并关闭本地实现记录 | 本文 Approved；五轮针对性代码对照复核—修改完成；`TEST-AUTH-000/002/003/005/010` 缺口已处理；`VAL-AUTH-001` 26 项、`VAL-AUTH-002` 125 项通过 | 项目维护者/安全方 | 关闭 KRET/Employee/Transaction Provider 本地实现记录前 | 代码评审方按 `DR-AUTH-001～010` 复核 | Closed | 只证明共享 Converter 与三个 opt-in 的本地 implementation-verified；不得据此声明真实 JWT 或部署生效 | 当前候选代码与合成 JWT |
| `AUTH-GATE-002` | `integration` | P4 真实用户 JWT | 证明共享role语义被三个Provider以真实`auth-service` token一致消费 | `VAL-AUTH-003`组合证据通过：生产者证明admin/dylan/viewer_t映射；Employee/Transaction覆盖实际三用户token；Knowledge覆盖实际ADMIN/VIEWER；三Provider负向、零调用和日志脱敏通过 | auth-service/三个 Provider | 首次真实 Provider 联调前 | 项目维护者按角色等价关系复核版本化证据 | Closed（2026-08-20） | 只证明当前受控配置真实JWT角色语义；不得据此声明目标部署/生产生效 | `Jwt` test fixture |
| `AUTH-GATE-003` | `release_effective` | 部署/生效 | 声明共享 Converter 在目标环境有效 | `AUTH-GATE-002` Closed；部署配置/Bean 来源/无未授权覆盖检查；三个 Provider 各自发布门禁关闭 | 项目维护者/部署环境 | 生产或等效环境启用前 | 部署核验与启动日志/配置快照 | Open | 允许本地候选；禁止生产生效声明 | 无 |

这些门禁只控制共享角色映射和三个目标入口的消费证据，不替代 Knowledge、Employee、Transaction 各自的数据可见性、公开契约、真实 ES/数据库或模型出域门禁。

## 15. 评审记录与当前结论

### 15.1 独立评审—修复循环

| 轮次 | 日期 | S0 | S1 | S2 | 冻结发现与处置 | 结果 |
|---:|---|---:|---:|---:|---|---|
| 1 | 2026-08-03 | 0 | 4 | 2 | 冻结并修复 `REV-AUTH-001`～`REV-AUTH-006`：当前基线/状态矛盾、门禁不完整、覆盖/消费契约模糊、实现测试触点不足、上位登记缺失、运行属性未说明 | 待第 2 轮复评 |
| 2 | 2026-08-03 | 0 | 2 | 5 | 修复 `REV-AUTH-007`～`REV-AUTH-013`：拆分设计批准与实现验证，补齐资源/禁止路径/内聚、接口和数据不适用说明、测试状态及严格校验字段 | 待第 3 轮复评 |
| 3 | 2026-08-03 | 0 | 1 | 2 | 修复 `REV-AUTH-014`～`REV-AUTH-016`：纳入 JWT 生产端验证，标记 dylan、非字符串 claim、覆盖 Bean 与敏感信息断言缺口，保持本地实现关闭门禁 Open | 待第 4 轮复评 |
| 4 | 2026-08-03 | 0 | 2 | 1 | 修复 `REV-AUTH-017`～`REV-AUTH-019`：将本文纳入 `L1_00` 下位治理，原子同步各层当前 Converter 事实与索引计数；历史停止记录及业务域/真实集成门禁不变 | 待第 5 轮终审 |
| 5 | 2026-08-03 | 0 | 0 | 1 | 对完整 v0.2、上位约束、关联 L2、P3 状态、实现触点、测试追踪和三阶段门禁进行终审；修复实施依据判定值不符合严格校验枚举的元数据问题，复验无剩余问题 | 评审通过，Approved |

### 15.2 针对性代码对照复核—修改记录

> 以下为实施后的自复核循环，不作为独立设计评审。修改范围仅限共享 Converter 及其发行/装配/Provider 安全测试，没有改变公开契约、角色范围、数据库或部署。

| 轮次 | 日期 | Blocker | High | Medium | 冻结发现与处置 | 验证结果 |
|---:|---|---:|---:|---:|---|---|
| 1 | 2026-08-03 | 0 | 0 | 3 | 原始 `token_type` 被转换式读取、role 接受任意 `Collection`、发行测试未覆盖 dylan/原始 wire；改为原始严格类型并补齐测试 | `auth-service/common-security` 回归通过 |
| 2 | 2026-08-03 | 0 | 0 | 1 | 缺少等价 Servlet 覆盖后 Reactive 单一委托及三个 Provider 未覆盖共享 Bean 的证据；补齐组合根测试 | 4 个定向测试类共 15 项通过 |
| 3 | 2026-08-03 | 0 | 0 | 1 | Provider 拒绝路径未证明 missing token、零下游调用及敏感信息不进入响应/日志；补齐三个安全链测试 | 3 个 Provider 定向测试类共 13 项通过 |
| 4 | 2026-08-03 | 0 | 0 | 1 | `AuthControllerTest` 复制用户配置存在漂移风险；改为直接绑定 `auth-users.yml` | Auth 发行测试 6 项通过 |
| 5 | 2026-08-03 | 0 | 0 | 0 | 对 `DR-AUTH-001～010`、角色解析唯一归属、Bean 名称、Guard 输入、文档哈希及工作区差异终检 | `VAL-AUTH-001` 26 项、`VAL-AUTH-002` 125 项及 `git diff --check` 通过 |

### 15.3 当前结论

本文 v0.4 为 Approved；五轮独立设计评审和五轮针对性代码对照复核结论不变。共享 Converter、自动配置与三个 Provider opt-in 的本地实现已经验证，`AUTH-GATE-001` Closed；`VAL-AUTH-003` 的组合式受控真实 JWT 证据证明生产者角色映射与三个 Provider 的角色等价消费、负向零调用及日志安全，`AUTH-GATE-002` Closed。`AUTH-GATE-003`继续Open，只允许在目标环境核验部署配置、Bean来源、未授权覆盖和各Provider发布状态后声明生效。该组合关闭不扩大角色、接口、数据可见性或业务最终授权，也不允许复用历史token/run作为新授权。
