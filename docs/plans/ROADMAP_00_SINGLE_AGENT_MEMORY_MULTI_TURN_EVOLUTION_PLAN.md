# [ROADMAP_00] 单体 Agent 记忆与多轮会话演进规划

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档编号 | ROADMAP_00 |
| 当前版本 | v0.1 |
| 文档状态 | Draft |
| 更新时间 | 2026-09-01 |
| 规划性质 | 后续能力路线图，不是当前实施计划、完成声明或代码授权 |
| 来源 | 当前已评审的单体 Agent 架构、Business QueryPlan、Knowledge 查询设计，以及本次提出的四项后续改进方向 |
| 适用范围 | 短期记忆、长期记忆、多轮会话、结构化查询条件演进、分页续查、Knowledge 多轮查询 |

本规划只记录后续方向、依赖、边界和建议验收顺序。进入实施前，仍需先形成对应需求和 L0/L1/L2 设计，并重新计算 P3 工作包与 UAT；本文不得作为“已经实现”的证据。

## 2. 方向判断

四项方向整体合理，能够在当前单请求、单动作查询能力之上形成自然的下一阶段演进，但不宜按原始列举顺序一次性建设全部能力。

| 方向 | 判断 | 关键调整 |
|---|---|---|
| 短期记忆、长期记忆、多轮会话 | 合理 | 先建立会话合同和短期记忆；长期记忆不是其他三项的前置条件，应在隐私、删除和过期规则明确后单独实施 |
| 结构化查询条件合并、清除 | 合理且价值高 | 不合并历史自然语言或未校验模型输出；只对上一轮已验证的 canonical QueryPlan 应用受限 PlanDelta，再完整校验 |
| 结构化查询翻页 | 合理且确定性较高 | 翻页必须绑定同一用户、会话、domain/action、过滤条件、排序、page size 和配置快照；条件变化后页码重置 |
| Knowledge 多轮会话 | 合理 | 每轮必须重新执行读取授权、检索、Evidence 和引用校验；历史上下文只能帮助消歧，不能替代本轮证据 |

推荐优先级为：

```text
会话合同与短期记忆
→ Business 条件合并/清除
→ Business 翻页
→ Knowledge 多轮
→ 跨能力多轮 UAT
→ 可选长期记忆
```

## 3. 规划目标与非目标

### 3.1 目标

1. 为同一已认证用户建立有界、可过期、可清除的多轮会话。
2. 在不绕过 LLM QueryPlan 和本地严格校验的前提下，支持 Business 查询条件增补、替换和清除。
3. 支持 Employee/Transaction 结果列表的上一页、下一页、首页和指定页等受控续查。
4. 支持 Knowledge 对省略、指代和追问的上下文理解，同时保持每轮独立授权和证据闭环。
5. 在短期能力稳定后，按明确的用户授权保存少量稳定偏好或长期事实。
6. 保持单轮只有一个顶层动作，不因多轮会话引入跨域 fallback 或隐式第二动作。

### 3.2 非目标

1. 不建设通用记忆平台、知识图谱、事件溯源平台或多 Agent 协作系统。
2. 不把完整聊天记录、业务结果列表、JWT、员工标识、交易数据、知识正文或原始模型响应写入长期记忆。
3. 不允许模型直接修改服务器中的会话状态；模型只能提出受限逻辑意图或 PlanDelta，由本地代码校验后提交。
4. 不允许复用上一轮业务授权结果替代本轮业务服务最终授权。
5. 不允许历史 Evidence 替代本轮 Knowledge 检索、读取授权和引用校验。
6. 不通过回放历史业务响应实现翻页，不在 Agent 侧缓存完整结果集并二次过滤。
7. 不因多轮能力恢复 Local Resolver、ID-only 补参、跨域 fallback 或多动作执行。

## 4. 统一会话与记忆分层

### 4.1 会话标识

Spring 接入层负责接收或创建不透明 `conversation_id`，并将其与当前认证主体、请求 ID、correlation ID 一并传给 Runtime。Runtime 不信任客户端提供的用户归属信息，必须使用服务端认证上下文绑定会话。

同一 `conversation_id` 不能跨用户、跨认证主体或跨安全上下文复用。身份变化、权限变化、会话过期或显式新建会话时，不继承上一会话的查询状态。

### 4.2 短期记忆

短期记忆只在会话有效期内保存完成下一轮所需的最小状态：

- 最近若干轮的有限意图摘要，不保存无限原始对话；
- 最近一次成功且已验证的 Business canonical QueryPlan；
- domain、action、配置 snapshot、分页和排序状态；
- 最近一次有限结果元数据，例如 page、size、total、hasNext，不保存完整业务结果；
- Knowledge 当前主题、有限实体、上一轮 evidence_ref 和引用元数据；
- 会话版本、最后更新时间和过期时间。

短期记忆采用有界 TTL、最大轮数和最大字节数。首阶段优先使用 Runtime 内存实现，不引入 Redis 或新数据库；只有单进程验证稳定且出现明确跨实例需求时，再评估外部存储。

### 4.3 长期记忆

长期记忆不是短期会话的延长版，只允许保存用户主动确认的稳定信息，例如展示偏好、默认 page size 或明确订阅的知识主题。每条长期记忆必须具备：

- 明确来源和用户确认；
- 所属用户和作用域；
- 类型、版本、创建时间和过期时间；
- 查询、更新、删除和全部清除能力；
- 敏感分类和默认拒绝策略；
- 不再适用时的失效机制。

长期记忆禁止保存 JWT、API Key、员工/交易标识、原始问题中的敏感值、Business QueryPlan slot 值、完整业务结果、知识正文、原始模型请求或响应。首阶段不得为了长期记忆引入向量数据库；只有确有语义检索需求和数据治理方案时再评估。

## 5. Business 多轮查询状态

### 5.1 基本原则

Business 多轮不重新解释历史原始问题，也不直接拼接历史模型 JSON。唯一可继承对象是上一轮已经通过 decoder、配置、validator 和 protected value binder 校验的 canonical QueryPlan 状态。

新一轮仍由 LLM 理解用户意图，但输出应区分：

- `new_query`：建立全新 QueryPlan；
- `refine_query`：对当前 QueryPlan 提交受限 PlanDelta；
- `clear_query`：清除指定条件或全部条件；
- `page_query`：在当前查询状态上执行受控分页操作；
- `unsupported`：上下文不足、目标不明确或当前合同不可表达。

本地系统负责校验和应用状态变更，模型不得获得可执行状态写权限。

### 5.2 条件合并

建议引入受限、强类型 `BusinessQueryPlanDelta`，只表达逻辑变化，不携带 SQL、ES DSL、endpoint 或物理字段。允许的最小操作为：

- 新增一个过滤条件；
- 替换指定逻辑字段的条件；
- 删除指定逻辑字段或指定 operator 的条件；
- 清空全部过滤条件；
- 更新允许的分页和排序参数。

应用 Delta 后必须重新执行完整字段/operator、组合、slot、分页、排序和配置 snapshot 校验。任何非法 Delta 都失败关闭，且业务调用为 0。

示例：

```text
用户：查询上海的员工
状态：employee.search，contact_address contains 上海，page=1

用户：再限定姓杨
Delta：新增 chinese_name prefix protected-ref(slot-1)
结果：两个条件 AND，page 重置为 1

用户：不限制地区了
Delta：删除 contact_address 条件
结果：保留姓氏条件，page 重置为 1
```

### 5.3 清除规则

1. “清除地区条件”只能删除逻辑字段 `contact_address`，不得按文本猜测并修改其他字段。
2. “重新查询”“换一个查询”建立新 QueryPlan，不继承旧过滤条件。
3. domain 或 action 变化时默认建立新活动查询上下文，不跨域合并条件。
4. 省略对象且存在多个候选条件时必须澄清或返回 unsupported，不得猜测。
5. protected slot 随请求结束失效；需要继承敏感条件时只能使用短期会话中的受保护状态句柄，不能把明文重新发送给模型。

## 6. Business 翻页机制

翻页是当前 canonical QueryPlan 的受控续查，不是结果缓存回放。建议支持：

- `next`：下一页；
- `previous`：上一页；
- `first`：首页；
- `goto`：指定合法页码；
- 可选的 `resize`：在配置允许范围内调整 page size，并回到首页。

翻页前必须验证：

1. 会话属于当前认证主体。
2. 最近一次成功动作是可分页的 `employee.search` 或 `transaction.search`。
3. domain、action、filters、sorts、page size 和配置 snapshot 未变化。
4. `next` 只有在 `hasNext=true` 或 total 能证明存在下一页时执行。
5. 页码和 page size 未超出代码及配置上限。
6. 每一页仍只调用一次原业务 endpoint，并由业务服务重新执行最终授权。

条件、排序或 page size 发生变化时页码必须重置为首页。`employee.semantic_search` 是否支持稳定翻页需要单独核实现有 vectorSearch 合同；在服务不能提供稳定排序和 offset 语义时，保持 unsupported，不得由客户端缓存或切片模拟。

示例：

```text
用户：查询上海的员工
→ employee.search page=1

用户：下一页
→ LLM/会话控制识别 page_query(next)
→ 本地复用已验证 filters/sorts/size，仅将 page 更新为 2
→ 重新校验并调用同一 Employee search endpoint
```

## 7. Knowledge 多轮会话

### 7.1 目标行为

Knowledge 多轮主要处理省略、指代和范围细化，例如：

```text
用户：当前增值税税率是多少？
用户：小规模纳税人呢？
用户：这个规定什么时候生效？
```

后续轮次可以使用短期会话中的主题、有限实体和引用元数据帮助构造本轮独立问题，但必须重新执行完整 Knowledge 流程。

### 7.2 每轮不变量

1. 每轮重新执行问题安全检查和必要的问题改写。
2. 每轮重新选择逻辑域并执行 Retrieval Plan。
3. 每轮重新通过 es-query-service 执行读取授权。
4. 每轮重新完成 keyword/vector、RRF、rerank 和 Evidence 选择。
5. 每轮重新计算三层模型出域交集。
6. 每轮 Summary 引用只能绑定本轮授权 Evidence。
7. 历史 evidence_ref 只能帮助消歧或建立检索线索，不能直接成为本轮答案证据。
8. 上下文不足或指代不唯一时返回 clarification/unsupported，不得编造指代对象。
9. Knowledge 与 Business 继续互不 fallback。

### 7.3 上下文最小化

发送给模型的上下文应为代码生成的有限结构，而不是完整对话回放。建议只包含：

- 当前用户问题；
- 最近主题的有限安全摘要；
- 允许的逻辑域；
- 必要的历史引用标识，不含未授权正文；
- 明确的“不得仅依据历史答案作答”约束。

若上下文可能包含敏感内容、过期政策或权限已变化，应清除对应上下文并按单轮新问题处理。

## 8. 一致性、并发与安全边界

1. 会话状态使用单调 `conversation_version`；并发请求必须进行 compare-and-set 或同会话串行化，防止丢失更新。
2. 只有业务调用成功并通过响应合同后，才提交新的查询状态；失败、取消和超时不覆盖最后成功状态。
3. PlanDelta 应用与状态提交必须是一个原子会话操作，但不与下游业务事务合并。
4. 会话过期、显式清除、退出登录或认证主体变化时删除短期状态。
5. 日志只记录 conversation ID 的不可逆有限标识、版本、动作、状态和错误枚举，不记录问题正文、slot 值、JWT、原始计划或业务结果。
6. 前端只能展示当前请求允许的结构化诊断；历史上下文视图必须经过相同脱敏，不得成为读取会话敏感状态的旁路。
7. 会话状态损坏、版本冲突、配置 snapshot 不兼容或字段已经停用时失败关闭，要求用户重新发起查询。

## 9. 分阶段工作包

| 顺序 | 工作包 | 目标 | 主要交付物 | 直接依赖 | 建议状态 |
|---|---|---|---|---|---|
| 1 | `WP-MT-CONTRACT-01` | 建立会话、Turn、短期记忆和状态版本合同 | REQ/L0/L1/L2、跨 Spring/Python 合同、威胁边界 | 当前单轮基线 | Proposed |
| 2 | `WP-MT-SESSION-RUNTIME-01` | 实现有界短期会话和并发控制 | conversation API、内存 store、TTL/clear、隔离测试 | `WP-MT-CONTRACT-01` | Proposed |
| 3 | `WP-MT-BQ-DELTA-01` | 实现 Business 条件合并、替换和清除 | PlanDelta、validator、state reducer、fake E2E | `WP-MT-SESSION-RUNTIME-01` | Proposed |
| 4 | `WP-MT-BQ-PAGING-01` | 实现结构化查询受控翻页 | PageIntent、稳定查询指纹、翻页校验与 UAT | `WP-MT-BQ-DELTA-01` | Proposed |
| 5 | `WP-MT-KNOWLEDGE-01` | 实现 Knowledge 追问、指代和上下文消歧 | Knowledge context、每轮重检索/授权/引用测试 | `WP-MT-SESSION-RUNTIME-01` | Proposed |
| 6 | `WP-MT-SYSTEM-UAT-01` | 完成跨域多轮、隔离、并发、清除和生命周期验收 | Business/Knowledge 多轮 UAT 与回归 | 3、4、5 | Proposed |
| 7 | `WP-MT-LONG-MEMORY-01` | 在短期会话稳定后实现可选长期记忆 | opt-in 类型、持久化方案、查看/删除/过期和安全 UAT | `WP-MT-SYSTEM-UAT-01` | Deferred |

工作包 3 和 5 可在公共会话合同完成后独立推进；工作包 4 依赖条件状态已经稳定。长期记忆明确后置，不阻塞 Business/Knowledge 多轮能力。

## 10. 最小门禁与验收建议

本项目为个人学习与验证项目，建议只设置与风险直接对应的有限门禁：

| 门禁 | 关闭条件 |
|---|---|
| `GATE-MT-01` 会话合同 | Spring/Python 会话合同、主体隔离、TTL、清除、并发和失败语义完成评审 |
| `GATE-MT-02` 短期记忆 | 同用户连续轮次可复现；跨用户、过期、取消、并发冲突均失败关闭或确定性处理 |
| `GATE-MT-03` Business 状态 | 条件新增/替换/删除/清空和分页均通过 canonical plan 再校验；非法变化业务调用为 0 |
| `GATE-MT-04` Knowledge 多轮 | 追问可消歧，每轮重新检索、授权、Evidence 和引用；历史证据不可直接复用 |
| `GATE-MT-05` 长期记忆 | 用户 opt-in、查看、删除、过期、分类和零敏感持久化全部验证；无明确需求可保持 Deferred |

不建议为每个自然语言表达、每个字段或每个页码建立独立门禁，也不需要 candidate/manifest 式付费治理，除非后续确实执行新的受控真实模型评估。

## 11. 建议 UAT 场景

### 11.1 Business

1. “查询上海员工”→“再限定姓杨”→“取消地区限制”。
2. “查询金额大于100的交易”→“再限制交易类型”→“清除金额条件”。
3. 查询成功后“下一页”→“上一页”→“回到第一页”。
4. 条件变化后页码自动回到第一页。
5. 无活动查询时请求“下一页”返回 unsupported，不调用业务服务。
6. Employee 会话切换到 Transaction 时不继承 Employee 条件。
7. 非法字段、非法 operator、过期 slot、跨会话引用和版本冲突均下游零调用。
8. 每一页业务服务重新授权，拒绝后不推进会话版本。

### 11.2 Knowledge

1. 税率问题→纳税人类型追问→生效时间追问。
2. policy→law 相关追问，重新选择逻辑域。
3. 指代唯一时正确补足上下文；存在两个候选主题时澄清或 unsupported。
4. 上一轮有 Evidence、本轮权限撤销时拒绝，不复用历史正文。
5. 新一轮检索无结果时返回 no_result/insufficient_evidence，不回放历史答案。
6. 敏感问题不进入模型，Business/Knowledge 均无 fallback。

### 11.3 长期记忆

1. 用户显式保存、查看、修改和删除展示偏好。
2. 未经确认的信息不得写入长期记忆。
3. 过期、退出登录、账号切换和全部清除行为可验证。
4. 敏感字段、业务结果、JWT、原始对话和模型响应零持久化。

## 12. 主要风险与处理原则

| 风险 | 触发场景 | 处理原则 |
|---|---|---|
| 条件漂移 | LLM 遗漏或误删历史条件 | 只接受 typed Delta；本地应用后重新完整校验并展示有限变更摘要 |
| 敏感值泄漏 | 历史问题或 slot 明文进入模型/日志 | request/session scoped protected handle；模型只见引用，日志零明文 |
| 跨用户串话 | conversation ID 被另一用户复用 | 服务端主体绑定，不匹配即拒绝并清除可疑上下文 |
| 并发覆盖 | 同会话两个请求同时修改状态 | conversation version + CAS/串行化；冲突不静默覆盖 |
| 翻页不稳定 | 排序缺失或数据变化 | 要求稳定排序和查询指纹；服务不支持时保持 unsupported |
| 知识过期 | 历史答案或 Evidence 被直接复用 | 每轮重新检索、授权和引用；历史只用于有限消歧 |
| 长期记忆失控 | 自动保存所有对话 | opt-in、类型白名单、TTL、查看/删除；默认关闭 |
| 过度设计 | 初期即引入外部记忆平台 | 先用进程内有界 store 验证能力，按真实需求再扩展 |

## 13. 后续设计与实施入口

进入代码实施前，建议按以下顺序建立权威设计：

```text
REQ：新增多轮会话、记忆、状态修改和验收需求
→ L0：补充会话边界、数据生命周期和安全原则
→ L1 Core：会话编排、状态所有权、并发与生命周期
→ L1 Business：QueryPlanDelta、分页和跨域隔离
→ L1 Knowledge：上下文消歧、每轮检索/授权/Evidence
→ L2：Spring/Python 合同、store、validator、binder、分页、Knowledge context
→ P3：按本路线图拆分工作包和有限门禁
→ UAT：新增独立多轮会话验收计划
```

首个实施目标应限定为“单进程短期会话 + Business 条件合并/清除的 non-live 验证”，不应同时引入长期存储、Knowledge 多轮和跨实例一致性。完成最小闭环后，再按工作包依赖逐步扩展。

## 14. 当前结论

四项改进方向均保留，但按风险和依赖重新排序：

1. 先做会话合同与短期记忆。
2. 再做结构化查询条件合并、清除和翻页。
3. Knowledge 多轮与 Business 多轮共享会话基础，但保持独立领域状态和每轮授权。
4. 长期记忆最后实施，默认关闭且只保存用户明确确认的非敏感稳定信息。

当前状态统一为 `Proposed/Deferred`，不存在已实施、已验证或 UAT 已通过的声明。
