# 设计文档品审报告

## 1. 审查结论

- 结论：通过
- 是否阻断继续串行评审：否；P1_V2/00～06 与 P2_V3/00～07 逐文档评审已完成
- 是否阻断编码：是；目标文档已通过品审，但全集仍为 In Review，尚未由用户确认 Approved，且模块重命名、DPW-1、服务身份、配置/凭据与旧路径删除尚未取得 M0 实施授权
- 审查类型：cross_layer
- 目标文档：`docs/design/P2_V3/06_文档CapabilityLocalProvider端口_L2实施详细设计_v3.0.md`
- 上级文档：Agent目标架构总览、契约与规划L1、能力执行内核L1、元数据与上下文安全L1
- 直接前置：P1_V2/02～06、P2_V3/00～05
- 关联文档：P2_V3/01～05、07
- 实际审查轮次：3
- 主要风险摘要：四类Provider契约/部署/凭据分裂、Runtime rewrite侵入、隐藏retry与第二endpoint、业务request携带设施选择、Map wire、Provider输出修复、current-scope外发许可、07 activation、deadline/cancel、两跳attempt与P1 metadata含义均已修复；最终S0=0、S1=0

## 2. 文档识别结果

- 识别文档类型：L2 Document capability-local Provider policy、port、wire、client、adapter与operational gate详细设计
- 识别依据：文档定义四类operation request/outcome、共享外发decision、DPW-1、Document Provider Adapter、07 activation消费、失败/取消/迁移/验证门禁
- 文档状态：In Review；用户已授权修改目标文档并执行最多5轮评审-修复
- 是否包含修改历史：是，已记录3轮实质评审-修复
- 是否存在上级文档：是，四份当前L0/L1为只读权威
- 是否存在关联文档缺失：否；07待按串行顺序承接activation、quality和rollout owner

## 3. 审查范围

| 序号 | 文档/实现 | 类型 | 是否已读取 | 作用 |
|---:|---|---|---:|---|
| 1 | P2_V3/06 | 目标L2 | 是，全文 | 评审并重写四类Provider唯一基础设施链 |
| 2 | 四份当前L0/L1 | 上级架构 | 是，相关章节 | 核对capability-local port、ExecutionScope、Result Security、上下文最小化与Multi Agent演进边界 |
| 3 | P1_V2/02～06 | 直接前置 | 是，相关章节 | 核对operation context/outcome/metadata、typed limits、deadline/cancel和原子迁移 |
| 4 | P2_V3/01～05、07 | 同层关联 | 是，边界章节 | 核对embedding binding、feature/limit、Safe candidate、Provider输入/输出及activation/rollout所有权 |
| 5 | P2/P2_V2 Provider专题 | 历史来源 | 是，按主题核对 | 验证有效规则已合并；历史文档仅保留provenance |
| 6 | 当前rewrite/embedding/rerank/generation port/client/adapter/config | 当前实现 | 是，相关类/字段 | 识别Runtime调用、fallback endpoint、Map/业务对象、输出修复与三种部署路径差异 |

## 4. S0 阻断问题

复审后未发现遗留S0。已关闭5项：

| 序号 | 原位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | 原四类client | rewrite经Runtime、embedding/rerank直连vendor、generation经独立adapter | 凭据、retry、availability、审计和取消边界分裂，无法原子迁移 | 收敛为单一Document Provider Adapter，四固定internal endpoint，原模块原子重命名 |
| 2 | 原operation contract | request未内嵌P1 context，返回业务结果/异常 | deadline/cancel/limit/attempt不能由统一client boundary证明 | 四个typed request内嵌context与policy reference，统一返回P1 outcome/metadata |
| 3 | 原generation adapter | Provider构造trusted candidate、修复citation并截断文本 | 不可信响应越过05 candidate/citation/limit owner | 06只返回strict untrusted payload，不排序、截断、别名化或构造候选 |
| 4 | 原外发规则 | Safe/minimal input被误当成current Policy/Permission允许外发 | 撤权、高敏Corpus或目的不允许时仍可能发送正文 | 唯一current-scope outbound decision，04/05只做operation-specific all-or-none投影 |
| 5 | 原可用性设计 | disable/rollback没有HTTP write前current snapshot gate | 已禁用Provider仍可能收到敏感请求 | 06消费07唯一immutable activation snapshot，write前双检、响应后复核与in-flight abort |

## 5. S1 严重问题

复审后未发现遗留S1。已关闭14项：

| 序号 | 原位置 | 问题 | 风险 | 修复结果 |
|---:|---|---|---|---|
| 1 | embedding client | 404/405后切第二endpoint并平均多向量 | 一次operation产生多attempt且改变04语义 | 单endpoint/单attempt/单向量；不平均、截断、补零 |
| 2 | rerank request | 携带retrievalProfile与完整Adapter result | 设施层获得不必要业务/安全对象 | closed candidate ID、最小文本与typed provider field scalar |
| 3 | generation request | 携带query/model/完整ECP/散预算 | caller可选择设施且Provider看见超范围数据 | 仅05 provider-safe projection与closed instruction/output shape |
| 4 | shared policy | decision漏authorization、limit和field rule闭包 | 相同input不能证明来自current scope与同一预算 | DPO-1绑定authorization/policy/permission/profile/limit/field rule/validUntil |
| 5 | activation owner | 07 snapshot携带endpoint选择 | rollout层侵入06 composition和网络路由 | 07只发布operation/provider/contract state；06固定operation→endpoint |
| 6 | wire payload | 使用Map/Object/JsonNode或自由type discriminator | unknown字段、类型漂移和反序列化绕过 | 四个编译期参数化DPW请求/响应与operation-specific strict parser |
| 7 | deadline | adapter算法要求deadline但wire未传 | adapter可超出Invocation截止时间继续处理/计费 | request携带并摘要绑定absoluteDeadlineEpochMillis，不得延长 |
| 8 | activation binding | request只带provider digest，未证明adapter观察同一snapshot | 同binding的旧/新rollout可能被混用 | request绑定expected activation digest，success回显observed digest |
| 9 | failure wire | adapter失败未定义受控协议 | agent只能解析HTTP message或vendor状态猜P1 failure | 新增closed DPW error与adapter failure code，agent本地验证并映射P1 |
| 10 | Provider identity | P1 metadata provider一度被内部adapter身份替代 | 业务审计失去逻辑vendor/model，attempt语义混乱 | metadata使用07可信逻辑Provider；adapter服务/部署身份单列 |
| 11 | attempt/retry | 两跳可能各自retry，P1 attempts含义不明 | 实际多次外发被隐藏 | 一个逻辑operation 0/1；两跳各0/1且分别审计，SDK/mesh/redirect关闭 |
| 12 | duplicate write | operationId重放未检测 | 同实例短窗内可能重复计费/外发 | bounded replay guard拒绝重复，不宣称集群exactly-once |
| 13 | cancellation | 本地signal不可wire且断连未必终止vendor | cancel后仍处理敏感正文 | agent abort internal exchange，adapter必须使用可abort vendor transport；能力不明时阻塞生产 |
| 14 | 配置 | feature/业务预算/provider/model/URL/credential混在AgentProperties | 多源扩大预算或启用Provider | agent只留internal operational config；vendor配置/secret归adapter，activation归07 |

## 6. S2 一般问题

复审后未发现遗留S2。已关闭4项：

| 序号 | 原位置 | 问题 | 修复结果 |
|---:|---|---|---|
| 1 | 文档信息 | 旧基线、来源和实施授权条件不统一 | 对齐P2_V3基线、权威上级和M0原子实施门禁 |
| 2 | 模块命名 | generation adapter开始承载rewrite但名称仍是单operation | 原子重命名为Document专用provider adapter，不新增通用跨capability平台 |
| 3 | 数据/状态 | 缺少正文、snapshot、in-flight、replay/audit生命周期边界 | 补内存/非持久化/受限审计和唯一current state规则 |
| 4 | 落点/测试 | 缺exact类型、路径、删除项和两跳验证 | 补adapter-api/agent-service/provider-adapter落点、零残留与contract/竞态/安全测试 |

## 7. S3 建议优化

暂无当前必须修改的S3。不建议增加通用Provider平台、万能`execute(Object)`、跨Invocation响应cache、集群exactly-once存储、Provider fallback router、跨child batch/ECP拼接或第二activation状态机；这些设计超出当前单智能体需求并扩大未来迁移面。

## 8. 架构设计审查结果

不适用；目标是L2详细设计。未发现必须修改L0/L1或P1_V2的遗留阻塞项。设计保持Provider port为Document capability-local leaf，Planning Runtime、Capability Registry、Domain Adapter Registry、Result Security和Multi Agent coordinator均未被06侵入。

## 9. 详细设计审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| Operation contract | 通过 | 四类typed request内嵌context/policy reference，success/failure均返回P1 outcome/metadata |
| Outbound policy | 通过 | DPO-1唯一解释current scope；04/05只做最小投影 |
| Rewrite/embedding/rerank/generation | 通过 | operation-specific input/payload/validator闭合，无业务对象或设施选择反向进入 |
| Provider binding | 通过 | 逻辑Provider、adapter身份/部署、vendor contract、template/model digest职责分离 |
| Activation | 通过 | 07唯一发布，06只读；固定endpoint归06 composition |
| DPW-1 | 通过 | typed generic、deadline/activation/provider/input digest、strict success/error互斥 |
| Attempt/deadline/cancel | 通过 | 逻辑0/1，两跳真实0/1，无retry/redirect；absolute deadline与abort/late语义完整 |
| Failure mapping | 通过 | closed adapter cause仅作证据，P1 failure/termination/metadata由agent本地构造 |
| 数据与安全 | 通过 | 无正文持久化，secret/vendor body/raw exception不跨边界；strict bytes/schema/field cap |
| 配置与发布 | 通过 | business policy/limit、operational config、vendor secret与activation owner分离 |
| 可实施性 | 通过 | exact模块、类、接口、迁移顺序、零残留、测试与readiness门禁完整 |

## 10. 跨层级一致性审查结果

| 检查项 | 结论 | 说明 |
|---|---|---|
| L0/L1 | 通过 | capability-local Provider、Java权威、Result Security和单Agent演进边界一致 |
| P1_V2/02～03 | 通过 | current ExecutionScope/Mask只在shared decision解释，wire不复制JWT/Scope；结果仍经03/P1安全边界 |
| P1_V2/05 | 通过 | typed context/limits、ProviderSafeIdentity、0/1 attempt、deadline/cancel/late/failure语义一致 |
| P1_V2/06 | 通过 | 模块/contract/config/旧路径均继续受M0原子Release Unit约束 |
| P2_V3/01～03 | 通过 | embedding binding、feature/limit、Safe candidate与final currentness所有权不被06重算 |
| P2_V3/04 | 通过 | rewrite/embedding/rerank input/fallback归04；06共享policy和设施执行 |
| P2_V3/05 | 通过 | generation provider-safe input/untrusted payload归contract；candidate/citation/fallback仍归05 |
| P2_V3/07 | 待串行修订 | 必须承接唯一activation发布、quality/capacity/data-sharing/rollback与两跳证据；不得选择endpoint或拥有port算法 |
| 当前代码 | 有条件通过 | migration gap已登记，不宣称现有三套调用路径符合目标设计 |

## 11. 是否建议进入后续阶段

- 是否建议继续评审下一份L2：是，进入`P2_V3/07_文档能力验证发布回滚审计与撤权_L2实施详细设计_v3.0.md`
- 是否建议进入编码实现：否；先完成07串行评审与P2_V3整体一致性复核，并取得M0原子实施授权
- 是否建议先修订架构设计：否
- 是否建议先修订关联文档：是，仅按既定顺序修订07；05的旧模块名已在其授权第5轮终态内同步为06冻结名称
- 是否需要用户确认：当前文档评审阶段无需新增确认

## 12. 用户确认项

当前无新增文档修改确认项。实施前必须单独确认：

1. `document-generation-adapter`到`document-provider-adapter`的模块、artifact、application、service discovery与部署原子重命名；
2. `agent-adapter-api`四类request/payload、DPW-1 success/error和P1 operation contract原子切换；
3. Runtime rewrite与agent-service direct embedding/rerank vendor client、旧endpoint和散配置删除；
4. service identity、credential、secret、internal route与vendor连接迁移；
5. 07 activation/rollback/readiness发布源及生产Provider/data-sharing启用；
6. commit、push、PR或生产发布。

## 13. 修订建议汇总

| 序号 | 优先级 | 目标位置 | 修订内容 | 是否阻断 |
|---:|---|---|---|---:|
| 1 | S0 | 4～10.7 | 四类operation contract、共享外发policy、trusted/untrusted和唯一部署链 | 是，已修复 |
| 2 | S0 | 10.8～10.17 | activation、DPW-1、deadline/cancel、attempt、失败、配置/凭据边界 | 是，已修复 |
| 3 | S1 | 10.2～10.9 | DPO-1、Provider/adapter身份、deadline/activation digest、closed error wire | 是，已修复 |
| 4 | S1 | 10.10～16 | 两跳算法、strict validator、replay、metadata与审计/容量 | 是，已修复 |
| 5 | S1 | 17～21 | 原子迁移、零残留、测试、readiness与风险门禁 | 是，已修复 |
| 6 | S2 | 1～3、22～24 | 文档元数据、真实轮次、检查清单和完成摘要 | 否，已修复 |

## 14. 复审记录

| 轮次 | 日期 | 操作 | 发现问题数 | 修复问题数 | 剩余问题 |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-13 | L0/L1、P1、00～05、历史来源与当前实现交叉初审并整体重写 | 20（S0=5、S1=12、S2=3） | 20 | 0 |
| 2 | 2026-07-13 | outbound decision、activation owner、typed wire、两跳attempt/identity与replay复审 | 6（S0=0、S1=5、S2=1） | 6 | 0 |
| 3 | 2026-07-13 | DPW deadline/activation/failure可执行性与P1 Provider metadata终审 | 4（S0=0、S1=4、S2=0） | 4 | 0 |

## 15. 最终结论

> 全集终态注记（2026-07-13）：本文保留该文档逐轮评审的时点记录；P1_V2/00～06 与 P2_V3/00～07 全集评审现已完成且 S0/S1=0。当前实施状态和授权边界以目标文档第 1、3、23、24 节为准，本文不构成 Approved 或 M0 授权。

目标文档通过品审，不阻断继续串行评审`P2_V3/07_文档能力验证发布回滚审计与撤权_L2实施详细设计_v3.0.md`。本次执行3轮，最终S0=0、S1=0。设计已形成“04/05 current-scope outbound decision与最小input→内嵌P1 context/policy reference的typed operation→06绑定07 ACTIVE snapshot→携带absolute deadline/activation/provider digest的DPW-1逻辑Provider operation→Document Provider Adapter单次vendor attempt→strict untrusted payload/closed error→04/05本地候选/fallback→03/P1安全结果”的唯一链。内部adapter身份不替代P1逻辑Provider，隐藏retry、第二endpoint、输出修复和散配置均被禁止；Multi Agent只复用未来独立child Invocation，不预建coordinator或共享内容状态。未完成07与P2_V3整体复核并取得M0原子实施授权前，不得实施半套模块/contract迁移。
