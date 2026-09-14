# [UAT_02] Knowledge 新设计验收计划

## 1. 文档信息与权威

| 项目 | 内容 |
|---|---|
| 当前版本 | v3.0 |
| 文档状态 | Reviewed |
| 日期 | 2026-09-14 |
| 文档身份 | 新计划首版；不继承旧UAT_01状态、预算或执行授权 |
| 设计依据 | [L1_01](../design/L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md) §4.5/4.6；三份Knowledge L2 v3.1批准合同，引用迁移已复核 |
| 流程合同 | [L2_01_00](../design/L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md) §8/19 |
| 检索/资料合同 | [L2_01_01](../design/L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md) §9/18 |
| Evidence/回答合同 | [L2_01_02](../design/L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md) §9/19 |
| 实施入口 | [P3_01](P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md) v3.0；只负责包、直接依赖及操作准入 |
| 当前验收状态 | 全部新方案用例Not executed；Functional/Safety Not evaluated，Retrieval/Answer evidence missing，资料验证未执行 |
| 修改历史 | 2026-09-14，从旧UAT_01 §5的风险身份、§15/16的已批准新方法承接；不改设计阈值 |

## 2. 范围与结果纪律

本计划仅治理在线12/8/minimal-v1与资料组织两条新主线；图谱、记忆、多轮、旧候选推进及Business重新验收不属于关键路径。Business继续由[UAT_00维护基线](UAT_00_SINGLE_AGENT_ACCEPTANCE_TEST_PLAN.md)管理，Knowledge变化不得重开无关Business用例，也不得掩盖共享合同回退。

五类验收分别记录：功能、安全、召回、回答、资料质量与发布回滚。最后一类只用于资料主线。文档Reviewed与任何一种验收通过无关；Not evaluated/Not executed是计划状态，不新增公开API或历史result枚举。

本轮不生成追踪JSON、不读取模型密钥、不调用服务或推理。后续真实运行必须有新独立授权、明确版本与预算；旧run、Gate及余额全部不可复用。技术失败按预先冻结协议停止，质量不达标如实记录，不自动新candidate。

## 3. 37个稳定功能/安全风险的目标版本映射

原37个ID保留风险身份，而非沿用原Passed。尤其RW组在新设计下验证“原意保护/非法意图/超时零下游”，不要求新链路继续生成改写文本；EV组使用Summary8模式义务，不把旧多证明集合强制输入带回来。下表预期来自批准L2，仅实现后新证据可关闭。

| Case | 风险/输入类别 | 目标通过条件 | 设计要求 | 后续验证方式与所需证据 | 当前状态 |
|---|---|---|---|---|---|
| `UAT-K-PUB-001` | ADMIN 合法税务问题 | 选择且只执行 `knowledge.query` | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring→Runtime non-live E2E；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Not executed |
| `UAT-K-PUB-002` | VIEWER 合法税务问题 | 读取授权通过并返回受控结果 | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring→Runtime + Java security；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Not executed |
| `UAT-K-PUB-003` | denied/missing/malformed/service-token | 确定性 401/403；未授权正文和 summary 调用为 0 | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring/security matrix；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Not executed |
| `UAT-K-PUB-004` | duplicate key、null、未知字段、超界问题 | 严格 JSON/输入失败，Runtime/Provider 调用为 0 | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Spring contract；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Not executed |
| `UAT-K-PUB-005` | unsupported 非知识问题 | 不执行 Knowledge/Business | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | 当前对象图 E2E；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Not executed |
| `UAT-K-PUB-006` | 第二动作或跨域 fallback 诱导 | 只允许一个顶层动作；无 fallback | L1_00；L2_01_00 DR-KFLOW-204/205；既有Spring安全契约 | Core/Runtime E2E；Spring→Runtime当前目标root non-live / Java安全矩阵；精确状态和调用计数 | Not executed |
| `UAT-K-RW-001` | 时间、主体、否定、法条等受保护约束 | 意图12只识别模式/域/terminal；安全原Q保留时间、主体、否定、法条且逐阶段相同，不生成改写文本 | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Not executed |
| `UAT-K-RW-002` | 模型返回非法候选 | 意图非法形状/候选/未知字段失败关闭；检索、embedding、rerank、Summary均0；不使用原问fallback | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Not executed |
| `UAT-K-RW-003` | rewrite timeout/provider failure | 意图模型timeout/provider failure按L2_01_00 §8.3映射；不进入检索或fallback | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Not executed |
| `UAT-K-RW-004` | 敏感或控制字符输入 | 进入模型前拒绝；意图/Summary调用0，控制字符规则不放宽 | L2_01_00 DR-KFLOW-201/202 | TEST-KFLOW-201，精确decoder/Guard/fake模型及零下游证据 | Not executed |
| `UAT-K-DOM-001` | 税务政策问题 | 仅 `tax.policy` | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Not executed |
| `UAT-K-DOM-002` | 税收法律/法条问题 | 仅 `tax.law` | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Not executed |
| `UAT-K-DOM-003` | 政策与法律混合问题 | 稳定选择两个域，按目录顺序执行 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Not executed |
| `UAT-K-DOM-004` | 普通零域问题 | `no_result/no_matching_domain`，检索和摘要为 0 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Not executed |
| `UAT-K-DOM-005` | 问题出域拒绝且同时零域 | 策略拒绝优先于普通零域 | L2_01_00 DR-KFLOW-201～203 | TEST-KFLOW-201/202，预选域顺序/unsupported/deny反例及计数 | Not executed |
| `UAT-K-RET-001` | keyword path | typed 请求，不含 index/field/DSL；候选授权后返回 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-RET-002` | vector path | BGE-M3 exact 1024 维；JWT/身份不进入 BGE | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-RET-003` | 多域×双路径 | 每个 plan item 一次；同 query embedding 至多一次 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-RET-004` | 重复候选与 RRF | 按 `(documentId, chunkId)` 去重、稳定融合 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-RET-005` | rerank | 输入仅授权候选；输出一一覆盖且稳定截断 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-RET-006` | 单路技术失败 | 仅在 coverage 与每域最小候选满足时部分继续 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-RET-007` | 全路径失败或快照冲突 | `downstream_failure`，Evidence/summary 为 0 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-RET-008` | 整域禁止或授权权威失败 | 安全失败优先，其他路径成功不得掩盖 | L2_01_01 DR-KRET-201～204；L2_01_00 DR-KFLOW-203 | TEST-KRET-201～203；typed contract、fake路径/融合/rerank、Java读取授权 | Not executed |
| `UAT-K-EV-001` | candidate hash/domain/snapshot/policy ref 完整 | 生成确定性 Evidence Bundle | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-EV-002` | 完整性冲突或缺失 | `evidence_failure`，Summary调用0；前置selector/意图调用单列 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-EV-003` | 全局∩域∩文档策略允许 | 仅最小 payload 进入当前 Summary task | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-EV-004` | 未分类、策略缺失/冲突或文档收紧拒绝 | `model_egress_denied`，summary 调用 0 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-EV-005` | 证据覆盖不足 | `no_result/insufficient_evidence`，不生成肯定回答 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-EV-006` | 合法抽取摘要（各原任务版本按冻结证据） | Summary8按lookup/explanation/applicability执行L2_01_02 §9.2/9.3；lookup不强加适用性证明，解释/适用性按各自义务；ref唯一且quote为授权正文连续子串，不伪造coverage | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-EV-007` | unknown/duplicate ref 或非子串 quote | `knowledge.summary_failure`，不返回模型原文 | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-EV-008` | summary timeout/provider/schema failure | 固定 timeout/downstream failure，无 retry/resume | L2_01_02 DR-KEV-201～205 | TEST-KEV-201～203；Evidence/模型精确输出/出域/引用反例 | Not executed |
| `UAT-K-ISO-001` | Knowledge 请求 | Employee/Transaction 调用 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Not executed |
| `UAT-K-ISO-002` | Business 失败 | Knowledge 调用 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Not executed |
| `UAT-K-ISO-003` | `AGENT_KNOWLEDGE_ENABLED=false` | 不注册动作、不创建 Knowledge client、不要求配置 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Not executed |
| `UAT-K-ISO-004` | 取消/关闭 | 未开始阶段调用 0，所有 owned Knowledge HTTP client 被关闭一次 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Not executed |
| `UAT-K-ISO-005` | 日志与有限 evidence 扫描 | JWT、正文、原始 Prompt/响应、物理 ES 信息均为 0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Not executed |
| `UAT-K-ISO-006` | enabled + 生产 stub / 测试显式 fake | 显式enabled + 生产stub按当前启动合同失败；测试显式fake复用生产装配，意图12/Summary8唯一且外部outbound=0 | L2_01_00 DR-KFLOW-204/205；L2_01_02 DR-KEV-204 | TEST-KFLOW-203/TEST-KEV-203；root/取消关闭/日志/Business隔离 | Not executed |


全部用例须记录目标代码/task/config/模型与数据绑定、断言及有限调用数；37风险不等于37次付费调用，确定性反例使用fake/契约。角色矩阵在接入和业务读取两个拒绝位置分别取证；summary阶段零调用不等于前置selector从未调用，应记录各阶段计数。

## 4. 原证据与当前要求的关系

| 原资产 | 适用范围 | 新计划使用方式 | 不允许的推论 |
|---|---|---|---|
| [旧UAT_01完整快照](历史文档/2026-09-14-knowledge-plan-handoff/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md) | 原37风险及各冻结任务/配置的功能证据、历史效果、当时待执行安排 | §3复用风险身份；§5/6承接已批准方法 | 原Passed不等于12/8已执行 |
| knowledge_uat_traceability.v1.json及原loader | 原authority UAT_01 v1.21及Summary4证明边界 | 保持字节和原始依据；后续新版本追踪另作实现 | 不改authority来制造新验收通过 |
| 历史P5/代表性run/人工rubric | 各自冻结HEAD、模型、语料及协议；有效与无效结果分开 | 只作历史对照；具体事实回到归档及原evidence | 不拼题、不改判、不证明当前源码11/7或目标12/8 |
| 阶段A正文/附件/发布资产 | 当时有限语料完整性、检索与回滚 | 复用数据来源及安全风险，不重做既有发布 | 不证明新chunk/向量表示已经更优 |

历史引用必须按原冻结提交和原路径读取；归档内部链接原样保存，当前计划不将其相对路径解释为当前权威。详见[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)。

## 5. 新设计的四维验收方法（仅设计，未执行）

### 5.1 证明范围与版本隔离

当前源码11/7/v3，拟议12/8/knowledge-minimal-v1尚未实施。历史37功能用例、P5、阶段A、阶段B和人工run-07均只证明自己的冻结范围；P5最近有效partially_effective不代表现有V11或新V12效果达标，run-07失败亦不覆盖更早有效测量。不得把不同批次的通过题相加为新版全套通过。

新基线状态：Functional=Not evaluated（不是新增运行结果枚举，只是计划执行状态）；Safety=Not evaluated；Retrieval/Answer evidence=missing。后续实际运行沿用既有Passed/Failed及四类Effectiveness结论，新增维度留在当前验收记录，不改历史result Schema。本轮只承接已批准方法并复核追踪，不创建JSON追踪或候选、不读取凭据、不执行测试服务/LLM；P3_01 §5管工作包及授权。

旧37个case稳定ID保持，后续COMPOSE对受影响项建立新版本证据，旧证据不重写；问题改写相关用例保留“原意保护/非法规划/超时0下游”的风险目标，不能把新方案没有rewrite当删测理由。新12/8准入矩阵为TEST-KFLOW-201～203、TEST-KRET-201～203、TEST-KEV-201～203及原37项的明确等价映射，未经映射/执行不称37/37新版本通过。

### 5.2 四维判据及阶段损失

| 维度 | 验证内容/方法 | 通过条件 | 不证明什么 |
|---|---|---|---|
| 功能 | fake实际生产root及Spring入口、精确意图/模式、原Q一致、路径与调用上限、失败映射、并发/取消/关闭；37风险逐case | 必需用例100%通过，无skip冒充；非法/模型失败下游0；不支持问题无第二动作 | 不证明真实LLM理解准确、原文库充足或usefulness |
| 安全 | Java读取角色/拒绝位置、Guard0model、三层出域0Summary、identity/hash/ref/连续子串/唯一性、日志脱敏及Business隔离 | 必需边界100%通过，任一越权/泄露/伪造引用为硬失败；不能被效果平均抵消 | 合法引用不等于回答充分或现行适用 |
| 召回 | 在人工确认必要来源存在的冻结池，记录域选择→keyword/vector→RRF→rerank→final20→Evidence8的来源覆盖、MRR与噪声 | 12题中至少8题预置为search且有可核实必要来源，三种模式均须覆盖；无命中/前置澄清题不放入召回分母；可验证题最终必要来源宏平均recall@20≥0.80、precision@20≥0.40，核心已确认必要来源不能全丢；实际分母/空池明确 | 缺资料不算排序失败；命中不等于可回答；未做同条件A/B不称较旧方案提升 |
| 回答 | 对原问题逐项核对相关、充分、忠实与usefulness；执行者可准备原文，最终真实评价由维护者独立于待测模型确认 | 12题全纳入；每题四项true才通过，≥10题通过；所有applicability题不得有无依据肯定结论，当前适用/历史有效混淆为硬失败 | 结构有效率不能冒称忠实度；“不足/澄清”只在预置预期如此时算正确 |

这些是**新需求基线的预置目标**，不是降低或重算旧P5 Q1～Q4；旧结论不变。阈值是个人验证项目的有限初始选择，仍需业务维护者在gold冻结前确认可用语料和问题含义；不能在看到新结果后降低。无法确认上述至少8题及三种模式的来源池时MEASURE处于Blocked，不自动删除case/补造gold或调用模型“找答案”。功能与安全合格可完成COMPOSE基础实施，未达到召回/回答目标不得宣称质量达标或擅自发布为优化成功。

每题在各阶段报告必要source/block集合覆盖及排名；候选ID仅诊断使用，不进入在线排序。相同父文档不同必要条款不能只因父ID命中就算全部覆盖。precision@20分母为实际返回候选数（0记0），由人工相关标注计算；每题必要来源缺一部分按比例计recall，宏平均只取预先核实可检索池，另报全部12题含缺料的覆盖率。MRR按首个相关必要来源排名，未命中0；Evidence recall另列，不以rerank数值分代替。没有人工原文/相关性标注时这些指标为not_assessed，不自动算0或Passed。

### 5.3 固定代表类别与先验预期

先设计12个内容case（每类4题），后续MEASURE准备阶段由维护者结合实际公开语料填写精确问句、必要source/block/hash、相关性标签、允许答案和不足/澄清预期，并在任何真实模型调用前冻结。不得单为住宿题、当前失败或gold ID写在线特判；不要求住宿资料缺失时也给肯定税率。

| 新Case | 模式/输入类型 | 预期与主要风险 |
|---|---|---|
| UAT-KM-001 | lookup，指定文号/附件 | 找到原文摘录与来源；不因缺纳税人条件阻断资料查找 |
| UAT-KM-002 | lookup，同义服务表达（可含住宿） | 检索相关资料而非擅自判税率；检索表示不足如实记录 |
| UAT-KM-003 | lookup，历史期间资料 | 可返回历史条文，不把它称为现行适用 |
| UAT-KM-004 | lookup，语料中确无对应条款 | 预置无命中/不足；不能返回无关片段冒充答案 |
| UAT-KM-005 | explanation，单域定义 | 直接摘录覆盖明确问题；不做无来源自由改写 |
| UAT-KM-006 | explanation，两个显式子问题 | 必要证据齐全才回答；缺一项不能部分肯定 |
| UAT-KM-007 | explanation，法律+政策 | 一次选双域、独立读取、最终证据覆盖；无失败扩域 |
| UAT-KM-008 | explanation，否定/税率/日期条件 | 原Q逐阶段不变，引用不得与显式条件冲突 |
| UAT-KM-009 | applicability，明确主体/期间/方法 | 只给直接适用条件及规则原文，不靠用户分类假设推导 |
| UAT-KM-010 | applicability，必要条件缺失 | 前置clarification_required，检索/Summary0；固定提示可用但不承诺动态问题 |
| UAT-KM-011 | applicability，当前与历史边界 | 无直接时效依据时不足，writtenDate不当生效日期 |
| UAT-KM-012 | applicability，类似分类边界 | 没有直接分类桥接/冲突未解决则不足，不以词面相似肯定 |

上述内容题可用公开、非敏感问题。功能/安全额外反例不必付费：未知域/模式/重复键；输出terminal组合；>1024长度；单/双域DENIED；policy缺失/冲突；坏hash；重复ref/非子串；少一路/全失败；模型超时；并发取消；disabled0依赖；Business不fallback。至少一个37风险case对应每项新DR，不以只测12题代替安全矩阵。

### 5.4 固定变量、预算与停止条件（非执行授权）

首期先完成COMPOSE的non-live。再在新的独立授权下，冻结代码/两task及Prompt hash、模型实际版本、minimal配置、Profile与索引/ACL快照、12题gold/顺序、调用预算和人工rubric。仓库绑定不等于运行绑定，必须先只读核实；运行中快照不符立即终止，不自行改alias或数据。

建议首期仅一次12题端到端测量，上限12 E2E、36模型HTTP（selector/意图/Summary合计）、48 typed search、12 query embedding、24 online rerank；维持每请求≤3/4/1/2，startup预热独立事前列明、不得计入效果请求，不能凭空增加预算。无Business/旧answer、无自动retry/resume，无失败后追加或补题。实际terminal较早时只消耗已产生调用，不为凑预算补齐。

技术/协议/安全失败停止该批，保留有限append-only终态及未执行清单，先fake诊断；不能称完整测量。正常no_result/clarification或人工判据不通过是有效测量输出，在安全合同仍成立时按预定顺序继续一次批次，最终如实分类，不修改预期。需要新批次只能作为新目标/新授权，本设计不预授予。

同条件对比可优先使用无外部LLM的固定候选池重放，各阶段损失可归因；若没有同索引/模型/条件的旧有效结果，不得拼接历史数据算增益。之后若要比较原问/改写或正文/上下文向量，必须另立单变量实验及预算，不与首期简化同时变更；语料/索引写入另授权，不属于本实施计划。

### 5.5 证据、人评和有限收口

每题运行记录只保存caseId、模式类别、预期/实际域、各阶段有限ID/排名、调用数、有限status/reason、安全结论、自动结果及人工四项；不保存真实用户敏感问题、完整知识/模型响应、凭据或个人信息。为可复现性，人工编写并核实无敏感值的公开测试问句、来源/block定位/hash、相关性标签及预期可以且必须作为版本化测试数据集冻结；运行记录引用caseId/hash，不重复保存问题或正文。公开fixture须明确来源许可，诊断不能把ID/gold反馈在线策略。

最终分别报告Functional、Safety、Retrieval、Answer。完整且安全的测量中，召回/回答均达标为effective，仅一维达标为partially_effective，两维均未达标为ineffective；执行合同不完整或安全失败为invalid_run。人工未评为not_assessed/evidence missing，不能先宣布有效质量等级，也不能由执行者/待测模型代填维护者结论。完整但质量未达标可记录测量完成，质量风险保持Open，不能用历史P5替代。本次设计完成不要求新测量，也不允许预记结果。

核心来源题预置为KM-001/005/009，任一在确认有原文的情况下最终必要来源覆盖为0即召回失败，不由宏平均掩盖。回答四项含义固定为：回应原问题、覆盖预期义务、没有无依据断言、对用户查阅或补条件有用；对预置不足/澄清题，评价正确拒绝/提示，不虚构quote或当作成功肯定答案。

评审与验证记录由P3_01 §13集中维护；不另建审批流水。新UAT JSON/Schema/loader实现只属于后续授权COMPOSE/MEASURE，当前追踪资产字节不变。

## 6. 资料组织与检索表示验收方法（设计，未执行）

依据L1_01 §4.6、L2_01_01 §18、L2_01_00/02 §19，实施由P3_01 §5独占。该补充不重做阶段A、不修改原37项功能或历史效果结果；来源/样本审计仅是先前冻结范围的事实，本轮不再次读取数据，不把抽样当作UAT执行。所有下列用例状态为Designed / Not executed，不创建新traceability、gold或candidate文件。

### 6.1 四维判据与有限实验

1. 数据质量：逐字段来源可查、日期语义正确、版本/父子关系可解析；正文跨度/表格/脚注不静默丢失。填充率和准确率分列；未知可存在，但不能把核心预期依据的未知问题标为已完成。
2. 功能与安全：唯一typed链路、读取先于正文处理、三层出域、身份/hash/ref/连续子串/唯一性、取消/关闭及Business不回退；任何越权/伪造/不明写入为失败，不能用质量均值抵消。
3. 召回质量：必要原文来源Recall、MRR/排名、噪声及Evidence覆盖；分别报告keyword/vector、融合、rerank、Evidence损失，不以“有命中”代替完整依据。
4. 回答质量：问题回应、条件/期间、原文充分性、忠实性与人工usefulness；合法引用不等于充分。没有模型调用或人工评审时为Not assessed，不由离线统计推出改善。

未来每个对照协议先冻结≤30父文档的变更/人工核验范围和代表问题（建议≤24，覆盖多税种、长短/附件/表格、现行/历史/未知、查找/解释/适用性和无命中反例）；不要只选原审计暴露问题或住宿单题。搜索池保留完整基线和未受影响竞争文档，不能仅搜30篇后外推全库收益。人工预先固定来源、必要条款/连续span和预期不足/澄清，不由待测模型自评。原文无法核实的题标source_gap，质量指标null；保留在计划总数/数据缺口中，单列可评估质量分母及未评估数，不能强计Recall=0/1或事后删除。

对照分两个独立问题：A只改chunker，固定原始/规范解析源hash、问题、模型、检索配置及权限，向量输入类型不变；B只改向量表示，固定A选定或原有同一chunk集合及精确body hash、模型/服务和所有在线参数。更换切片时gold用稳定document/asset/source span，不用旧chunkId强求一一对应；同时变化parser、语料或模型时不能宣称单变量实验。

body、title/section/body、可信分类/body至多3种表示，先用纯构造/token统计筛除不合法项；每轮只比较基线与一个预选候选，不因失败扩成无限网格搜索。每次真实实验冻结run、代码/索引UUID/全记录变更清单、模型/tokenizer/表示/Prompt、case顺序、人工rubric、每个阶段调用预算及停止条件；本计划不授予任何调用或索引写预算。若有模型，统计selector/意图/Summary全部HTTP，不复用旧额度；无模型阶段仍须限定ES/BGE总量和候选数量。

建议质量判据在执行前由维护者确认并固化：核心有充分原文的题必要来源覆盖不得为0；成对核心覆盖和保留集覆盖不得退化，至少一个预先选择的质量主指标改善且噪声/时延不突破预定容忍值，才考虑发布。指标阈值/容忍值未冻结则实验Blocked，不允许看到结果后降低。小样本只作局部决策依据，不声称统计显著或全库收益。数据/功能安全全部达标但质量无提升可以结束测量，不能使RELEASE自动Ready。

### 6.2 用例追踪

| UAT case | 风险与设计映射 | 后续验证方法/预期证据 | 通过条件 |
|---|---|---|---|
| UAT-KORG-001 | 源字段丢失/补造；DR-KRET-301、DR-KEV-301 | 11字段fixture、HF原行/官方/curated对照、hash自身排除及重放时钟反例 | 原值可追溯，未知不补造，许可/来源分离，同输入hash稳定 |
| UAT-KORG-002 | 日期错填/陈旧；DR-KRET-302、DR-KEV-304 | 成文≠生效、pending变更、部分失效、历史/未知反例 | 不把成文填生效，不据文档整体状态认定条款；查阅与适用性分开 |
| UAT-KORG-003 | 分类等同授权/相关性；DR-KRET-305 | 多标签/缺标签/机关/法律效力及channel映射契约 | 不按推断标签扩权或无条件排除，不引入分类分库 |
| UAT-KORG-004 | 同题名误合并/关系丢失；DR-KRET-303 | 同标题不同版本、转载、附件父关系与冲突重放 | 稳定源身份/hashScope，关系有来源且可解析，旧记录不覆盖 |
| UAT-KORG-005 | 条号/条件/例外过碎；DR-KRET-304 | 长短条款、否定/例外/列表/脚注结构fixture+人工核对 | 相邻合法打包，内容为连续span；跨单元不伪造，无法保全显式隔离 |
| UAT-KORG-006 | 表格扁平与目录误认；DR-KRET-304 | 已有表格/页/目录样本，不重做OCR；表头/行关联人工核对 | 无猜造单元格/条款；重复表头不是quote；未知结构不标完整 |
| UAT-KORG-007 | 字符/token混同与截断；DR-KRET-306 | 固定tokenizer精确长度、三表示、长输入和版本缺失 | 特殊token计入，超长关闭；维度exists不代替模型/输入来源证明 |
| UAT-KORG-008 | 派生上下文冒充原文；DR-KEV-302、DR-KEV-303 | keyword/vector/rerank/Evidence表示对照；非法标题/表头quote | 原content不变，hash作用域一致，拼接/跨片引用拒绝 |
| UAT-KORG-009 | 读取/出域/父关系越权；DR-KFLOW-301、DR-KFLOW-302 | Java typed权限、Python策略/敏感0调用、默认disabled fake | 现公共合同不变，未授权正文不进入后续阶段/模型，Business不回退 |
| UAT-KORG-010 | 分段/向量收益混淆；DR-KRET-307 | 冻结父/asset/span、完整竞争池，单变量逐阶段排名及source_gap反例 | 无gold特判/删题；Recall/MRR/噪声与Evidence分列，null/分母可核 |
| UAT-KORG-011 | 合法引用却无法回答；DR-KEV-304 | 三模式多税种/期间代表题，人工原文与usefulness；必要时另授权模型 | 足够与不足分别判断，时效未知不肯定，不由模型自评 |
| UAT-KORG-012 | 发布错配/无法回滚；DR-KFLOW-303、DR-KRET-307 | fake故障→另授权隔离typed/alias回滚→发布冒烟 | 旧索引/资产不改，全记录变更可核，Profile/catalog匹配，恢复相容旧绑定 |

001～008可先以纯离线fixture完成；009的fake与真实typed证据分开；010的BGE/ES、011的模型/人工回答、012的发布验证均须后续资源授权，不把单测代替真实集成。图谱、记忆和多轮不参与验收。

### 6.3 报告与停止

逐case记录来源类别、原文身份/hash、变量、验证方式、有限结果、缺口及执行状态；不保存真实敏感问句、完整正文、JWT或原始模型响应。原文人工阅读限定既有批准资料，证据只记录必要定位与hash。固定问题集中的合规非敏感问题可用于后续版本化测试，不能与禁止保存真实敏感输入混淆。

数据质量、Functional、Safety、Retrieval、Answer分别报告；本次均不预记通过。任何来源不明、权限/引用失败、模型/服务错误、预算耗尽或结果不完整先停当前实验，保留有限终态；用fake诊断，不自动补跑或新candidate。质量未提升只给出风险和是否保留基线的决策，不恢复被取消目标。

## 7. 后续执行与当前结论

在线由P3_01的CONTRACT/RETRIEVAL/EVIDENCE→COMPOSE→MEASURE推进；资料由NORMALIZE→CHUNK/REPRESENT→COMPARE→RELEASE推进。前置不足只阻塞对应阶段，真实测量不是基础实现反向依赖；资料对照不依赖在线MEASURE，需自行冻结相容在线基线。

后续逐case报告：版本与设计、风险、预期、实际测试/有限证据、执行状态、通过或失败原因、未验证范围；旧证据引用不能替代新执行。37风险、12个UAT-KM类别、12个UAT-KORG类别均待执行，精确内容题与gold仍由后续准备阶段冻结。本次没有新的UAT通过结论。

本轮文档评审与验证见[迁移说明](历史文档/2026-09-14-knowledge-plan-handoff/README.md)。只做权威承接，不修改算法、数据或阈值；本轮迁移评审已通过（同一执行者分阶段复核），所有验收执行状态仍为Not executed。
