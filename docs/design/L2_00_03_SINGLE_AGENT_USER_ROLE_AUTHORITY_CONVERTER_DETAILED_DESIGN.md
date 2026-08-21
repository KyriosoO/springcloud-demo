# [L2_00_03] 单体 Agent 用户角色 Authority Converter 详细设计

> 文档层级：L2
> 文档状态：Approved

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | `L2_00_03` |
| 当前版本 | v1.1 |
| 日期 | 2026-08-21 |
| 权威范围 | `common-security` 中用户 JWT `role` claim 到 Servlet/Reactive Authority 的唯一转换契约与具名 Bean |
| 上位文档 | [`L1_00` v1.0](L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md) |
| 来源文档 | [L2_00_03 v0.4 归档版](历史文档/2026-08-21-v0-baseline/L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md) |
| 实施状态 | 共享 Converter、自动配置及三 Provider 消费已实现并验证；未生产生效 |

## 2. 阅读导航与变更记录

重点：第 6 节输入/输出契约、第 7 节规则、第 8 节消费方式、第 11 节实现落点。

| 版本 | 日期 | 变更原因 | 变更内容 |
|---|---|---|---|
| v1.1 | 2026-08-21 | 代码评审发现验证命令不能从仓库根执行 | 改为以 `serviceCenter/pom.xml` 为聚合入口并使用实际 artifactId 选择器；补强严格 claim 负向验证，不改变安全契约 |
| v1.0 | 2026-08-21 | 建立共享安全契约新基线 | 删除实施门禁流水，明确当前严格大写角色列表、具名 Bean、fail-closed 和业务服务最终授权关系 |

## 3. 目标与范围

### 3.1 目标

让 Servlet 与 Reactive Provider 对同一用户 JWT 得到完全一致、有限且可覆盖的 Authority，消除各服务自行解析角色造成的大小写、前缀和 token 类型漂移。

### 3.2 范围内

- `role` claim 结构和值域；
- 用户 token 前置校验；
- `ADMIN/VIEWER` → `ROLE_ADMIN/ROLE_VIEWER`；
- Servlet/Reactive 具名 Converter Bean；
- Provider SecurityFilterChain 的显式消费和覆盖规则。

### 3.3 范围外与不负责

- `auth-service` 用户、角色分配或 JWT 签发策略；
- Employee/Transaction/Knowledge 动作授权和数据可见性；
- Agent Adapter 本地角色判断；
- 角色层级、动态权限、ACL、数据库迁移或生产部署。

## 4. 上位约束与追踪

### 4.1 需求与约束定义

| 需求编号 | 验收行为 |
|---|---|
| `REQ-AUTH-001` | 同一合法用户 JWT 在 Servlet/Reactive 产生相同 Authority 集合 |
| `REQ-AUTH-002` | 非用户 token、缺失/错误/未知 role fail closed |
| `REQ-AUTH-003` | Provider 通过稳定 Bean 名显式引用，业务域仍执行最终授权 |

| 约束编号 | 来源与约束 |
|---|---|
| `CON-AUTH-001` | `L0_00 SA-C-004/007`：用户 JWT 必需，业务服务最终授权 |
| `CON-AUTH-002` | `L1_00`：共享 Converter 是 role→Authority 唯一权威 |
| `CON-AUTH-003` | 当前 `auth-service` 签发 `role` 为大写字符串列表，允许值只有 `ADMIN/VIEWER` |

### 4.2 端到端追踪矩阵

| REQ/CON | 设计规则 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|
| `REQ-AUTH-001`、`CON-AUTH-002` | `DR-AUTH-001`、`DR-AUTH-002` | `IMPL-AUTH-001`、`IMPL-AUTH-002` | `TEST-AUTH-001`、`TEST-AUTH-002` | `VAL-AUTH-001` |
| `REQ-AUTH-002`、`CON-AUTH-003` | `DR-AUTH-003`、`DR-AUTH-004`、`DR-AUTH-005` | `IMPL-AUTH-001` | `TEST-AUTH-003`、`TEST-AUTH-004` | `VAL-AUTH-002` |
| `REQ-AUTH-003`、`CON-AUTH-001` | `DR-AUTH-006`、`DR-AUTH-007` | `IMPL-AUTH-002`、`IMPL-AUTH-003` | `TEST-AUTH-005`、`TEST-AUTH-006` | `VAL-AUTH-003` |

## 5. 关联资源与责任边界

| 组件 | 唯一职责 | 不负责 |
|---|---|---|
| `SecurityTokenUtils` | 判断 JWT 是否为受支持 user token | 角色映射、动作授权 |
| `UserRoleJwtAuthenticationConverter` | 严格 role claim→有限 Authority | token 验签、业务允许判断 |
| AutoConfiguration | 暴露两个稳定具名 Bean 和可覆盖接缝 | 强迫任意服务采用该 Converter |
| Provider Security chain | 显式选择 Converter 并保护具体 endpoint | 改写共享映射规则 |
| 业务 Controller/Service | `ROLE_*` 最终动作授权与响应可见性 | 解析原始 role claim |

依赖方向为 `Provider security → common-security Converter → Spring Security/JWT`。禁止 Converter 依赖 Employee、Transaction、Knowledge 或 Agent；禁止 Adapter 复制映射。

共享模块是映射语义的内聚位置；不新增独立授权服务或权限数据库。

## 6. 当前实现基线与核心契约

### 6.1 当前实现

- `UserRoleJwtAuthenticationConverter` 实现 Servlet `Converter<Jwt, AbstractAuthenticationToken>`。
- `UserRoleAuthorityAutoConfiguration` 暴露 Servlet 与 Reactive 两个具名 Bean。
- Employee、Transaction、Knowledge Provider 的专用 Security 配置已显式注入对应 Bean。
- 单元、自动配置、Servlet/Reactive 集成和角色矩阵测试已存在。

不需要代码变更；新文档精确描述当前严格契约，而不是旧版可能出现的宽松大小写/前缀兼容表述。最小变更原则是仅在 claim 契约或 Spring 消费方式发生不兼容变化时修改共享 Converter；新增第二套角色解析抽象没有必要性。

### 6.2 输入 claim

| 项目 | 契约 |
|---|---|
| token 类型 | 必须由 `SecurityTokenUtils.isUserToken(jwt)` 判定为用户 token |
| claim 名 | exact `role` |
| claim 类型 | 非空 JSON array / Java `List<?>` |
| 元素类型 | 全部必须为 string |
| 允许值 | exact uppercase `ADMIN`、`VIEWER` |
| 重复值 | 归并为一个 Authority |
| 未知/混合非法值 | 整个 Authority 集合为空，不部分接受 |

### 6.3 输出 Authority

| 输入 | 输出顺序 |
|---|---|
| `["ADMIN"]` | `ROLE_ADMIN` |
| `["VIEWER"]` | `ROLE_VIEWER` |
| `["ADMIN","VIEWER"]` 或反序 | `ROLE_ADMIN`,`ROLE_VIEWER` |
| 缺失、空、非列表、非字符串、未知、`ROLE_ADMIN`、小写 | 空集合 |
| 非用户 token | `OAuth2AuthenticationException(invalid_token)` |

Converter 不隐式 trim、改大小写、补 `ROLE_` 前缀或接受字符串单值。调用方如需不同签发格式，必须先修改签发契约并进行跨服务兼容评审。

## 7. 详细功能与设计规则

| 规则编号 | 规则 |
|---|---|
| `DR-AUTH-001` | Servlet Converter 是映射算法唯一实现，Reactive 只适配其结果 |
| `DR-AUTH-002` | Authority 输出顺序固定 ADMIN 后 VIEWER，重复角色不重复输出 |
| `DR-AUTH-003` | 非用户 token 抛 `invalid_token`，不得变成普通匿名或空角色继续访问 |
| `DR-AUTH-004` | role 结构或任一元素非法时返回空集合，禁止部分容错 |
| `DR-AUTH-005` | 仅 exact `ADMIN/VIEWER`，不 trim、不改大小写、不接受已有前缀 |
| `DR-AUTH-006` | Bean 名固定为 `userRoleJwtAuthenticationConverter` 与 `reactiveUserRoleJwtAuthenticationConverter` |
| `DR-AUTH-007` | Provider 必须显式把具名 Bean 配置给对应 Resource Server；最终授权仍由 endpoint/业务服务执行 |

### 7.1 正常流程

```text
JWT 已验签
  → SecurityTokenUtils.isUserToken
  → 读取 role List
  → 完整结构和值域校验
  → 去重并按 ADMIN/VIEWER 固定顺序输出 ROLE_*
  → Provider SecurityFilterChain
  → endpoint 最终授权
```

### 7.2 失败类型与调用方可见语义

| 失败类型 | Converter 结果 | Provider 可见语义 |
|---|---|---|
| 非用户 token | `OAuth2AuthenticationException` | 401 |
| role 缺失/空/类型错误/未知 | authenticated token + 空 Authority | 受保护动作 403 |
| JWT 验签/过期失败 | Converter 前失败 | 401 |
| Bean 缺失或错误绑定 | Context/集成测试失败 | 启动或测试失败，不宽松回退 |

## 8. Bean、依赖与覆盖设计

```java
@Bean(name = "userRoleJwtAuthenticationConverter")
@ConditionalOnMissingBean(name = "userRoleJwtAuthenticationConverter")
Converter<Jwt, AbstractAuthenticationToken> userRoleJwtAuthenticationConverter()

@Bean(name = "reactiveUserRoleJwtAuthenticationConverter")
@ConditionalOnMissingBean(name = "reactiveUserRoleJwtAuthenticationConverter")
Converter<Jwt, Mono<AbstractAuthenticationToken>> reactiveUserRoleJwtAuthenticationConverter(
    @Qualifier("userRoleJwtAuthenticationConverter")
    Converter<Jwt, AbstractAuthenticationToken> delegate)
```

覆盖只能使用同名 Bean，且覆盖实现必须通过同一契约测试；否则可能造成三 Provider 语义分裂。普通默认 Resource Server 自动配置不等价于显式消费本 Converter。

## 9. 权限、安全、审计与数据生命周期

- Converter 只处理已验证 JWT claims，不记录完整 claims、JWT、subject 或角色原始值。
- 拒绝原因可用有限类别统计，但不得用日志输出 token。
- Converter 无共享可变状态、无缓存、无数据库事务、无重试；线程安全依赖纯转换。
- Bean 生命周期随 Spring Context；角色数据不持久化，无迁移。
- `dylan` 是用户而非角色；该用户当前由 auth-service 分配 `ADMIN`，不在 Converter 写用户特例。

## 10. 配置、兼容、发布与回滚

- claim 名和值域是代码契约，不通过业务配置扩展。
- 发布必须同时验证 auth-service 签发 fixture 和 Servlet/Reactive Provider 消费。
- 新角色或新 claim 结构属于公共安全契约变化，需要调用方清单、兼容方案和明确授权。
- 回滚以 `common-security` 版本与 Provider Security 配置共同回滚；不能只回滚一个 Provider。

## 11. 实现落点清单

### 11.1 实现编号定义

| 实现编号 | 路径与关键入口 |
|---|---|
| `IMPL-AUTH-001` | `common-security/src/main/java/com/dylan/common/security/UserRoleJwtAuthenticationConverter.java`：`convert(Jwt)` |
| `IMPL-AUTH-002` | `common-security/src/main/java/com/dylan/common/security/UserRoleAuthorityAutoConfiguration.java`：两个具名 Bean |
| `IMPL-AUTH-003` | `employee-service/.../EmployeeDetailSecurityConfiguration.java`、`mq-procedure-service/.../TransactionSearchSecurityConfiguration.java`、`es-query-service/.../KnowledgeSearchConfiguration.java` |

省略号路径在上一行仅表示各模块完整 `src/main/java` 包路径，不作为文件引用；精确文件名在仓库中唯一。

### 11.2 关键签名

```java
public final class UserRoleJwtAuthenticationConverter
        implements Converter<Jwt, AbstractAuthenticationToken> {
    public AbstractAuthenticationToken convert(Jwt jwt);
}
```

## 12. 测试与验证设计

### 12.1 测试编号定义

| 测试编号 | 场景与路径 |
|---|---|
| `TEST-AUTH-001` | 全部合法角色组合、顺序与去重：`common-security/src/test/java/com/dylan/common/security/UserRoleJwtAuthenticationConverterTest.java` |
| `TEST-AUTH-002` | Servlet/Reactive Bean 等价与覆盖：`UserRoleAuthorityAutoConfigurationTest.java` |
| `TEST-AUTH-003` | 非用户 token、缺失/空/非列表/非字符串/未知/小写/前缀负向 |
| `TEST-AUTH-004` | 混合合法+非法元素不得部分授权 |
| `TEST-AUTH-005` | Employee/Knowledge Servlet Security 集成允许/拒绝矩阵 |
| `TEST-AUTH-006` | Transaction Reactive Security 集成允许/拒绝矩阵 |

### 12.2 验证编号定义

| 验证编号 | 判定 |
|---|---|
| `VAL-AUTH-001` | 仓库根执行 `mvn -f serviceCenter/pom.xml -pl :auth-service,:common-security -am test` 通过，签发 claim 与两个 Bean 语义一致 |
| `VAL-AUTH-002` | 全部非法 claim fail closed，service token 为 401，零部分授权 |
| `VAL-AUTH-003` | 仓库根执行 `mvn -f serviceCenter/pom.xml -pl :common-security,:employee-service,:mq-procedure-service,:es-query-service -am test`，定向 Security、拒绝零调用与 fallback 兼容测试通过 |

## 13. 风险与保护条件

| 风险 | 触发 | 控制 | 是否阻塞/需授权 |
|---|---|---|---|
| 签发格式漂移 | auth-service 改成小写/字符串 | 跨服务 fixture 和严格失败 | 否；变更需授权 |
| Reactive 分叉 | 单独实现映射 | 适配 Servlet delegate | 否 |
| 覆盖 Bean 放宽 | 应用提供同名宽松实现 | 自动配置覆盖测试+Provider 矩阵 | 否 |
| 把角色映射当最终授权 | 只校验认证不保护动作 | Provider endpoint guard | 否 |
| 新角色 | 直接加入 Converter | 先评审公共契约和业务域影响 | 需授权但不阻塞当前依据 |

## 14. 实施依据

| 项目 | 结论 |
|---|---|
| 是否可作为实现依据 | 是，当前 v1.1 可作为共享 Authority Converter 及 Provider 消费代码评审依据 |
| 当前允许实施范围 | common-security Converter/AutoConfiguration、三 Provider 显式绑定和测试 |
| 当前禁止动作 | 新角色、用户特例、auth-service 签发变更、业务授权迁移和生产生效 |
| 回滚单位 | common-security 与所有显式消费 Provider 的兼容版本 |

## 15. 三轮内部自检与独立评审记录

| 轮次 | 检查重点 | 结论 |
|---|---|---|
| 内审 1 | claim 契约、唯一权威、来源和追踪一致 | Passed |
| 内审 2 | fail-closed、Servlet/Reactive 覆盖和兼容一致 | Passed |
| 内审 3 | 最小必要性、真实落点、测试和可读性检查通过 | Passed |
| 独立评审 | 未发现 S0/S1/S2；claim、Bean、Servlet/Reactive 适配与 Provider 消费契约一致 | Passed |

- 当前版本：v1.1。
- 文档状态：Approved。
- 新版本不继承旧版评审流水；历史文档只作为来源。
