# [L2_00_02] 单体 Agent DeepSeek 模型接入与受控生成详细设计 L2

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 单体 Agent DeepSeek 模型接入与受控生成详细设计 |
| 文档编号 | `L2_00_02` |
| 文档路径 | `docs/design/L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md` |
| 文档层级 | L2 详细设计 |
| 文档状态 | Approved |
| 评审状态 | 历史评审、Runtime 与问题出域结论保持；v0.23 已完成 Transaction answer v2 candidate-02 全新 non-live 冻结、定向/相关回归及代码对照设计复核，无未关闭blocker/high/medium。`GATE-055`关闭；真实 Employee/Transaction 结果出域继续分别受`GATE-024/026/SA-GATE-006`约束 |
| 当前版本 | v0.23 |
| 日期 | 2026-08-17 |
| 适用范围 | DeepSeek Provider、用户问题输入闸门、selection-only 能力 ID 选择、受控回答生成、模型预算/失败/观测 |
| 上位文档 | `REQ_00`、`L0_00`、`L1_00` |
| 直接依赖 | `L2_00_01` v0.11（Approved；Provider-neutral ID/Core 边界不变）的 `CapabilitySelectionNode` ID-only 契约、能力描述、混合裁决和结果隔离；`L2_00_00` v0.7（Approved）的 Runtime 子截止与取消 |
| 关联文档 | `L1_01` v0.4、`L1_02` v0.4、`L2_01_00` v0.7、`L2_02_00` v0.44、`L2_02_01` v0.44、`L2_02_02` v0.15 |
| 外部契约 | DeepSeek OpenAI-compatible 正式 `/chat/completions`、`deepseek-v4-pro`、JSON Output；Tool Calls 仅作为 v1～v3 历史证据保留 |
| 实现基线 | `agent-runtime/model` 已存在 Provider-neutral 契约、输入闸门、代码绑定 task/gateway/grounding、ContextVar 装饰器及 `DeepSeekChatTransport`；`LocalModelCompositionRoot` 已支持默认 `stub` 与显式 `deepseek` 两种装配，后者创建并独占一个进程级 client，向 Runtime 注入 ID-only selector、answer generator 与 `ModelContext` binding，并由 Runtime lifespan 幂等关闭。candidate-01 失败历史与 candidate-02 30/30 通过证据保持 append-only；本轮只使用 fake transport，未读取 `LLM_API_KEY`、未产生真实 outbound |
| 是否可作为实现依据 | 按范围可用；`WP-MODEL-RUNTIME-01` 已按 v0.15 设计完成受控实现和验证，`GATE-020/SA-GATE-002` 已按限定 Runtime 切片关闭；该结论不授权目标环境启用 `deepseek` 或任何真实数据出域 |
| 实施依据说明 | `WP-MODEL-LOCAL-01`、隔离 `WP-MODEL-POC-01`、`WP-MODEL-ACTION-V4-LOCAL-01`、`WP-MODEL-ACTION-POC-04` 与 `WP-MODEL-RUNTIME-01` 已完成；`WP-MODEL-ACTION-POC-02/03` 继续作为失败历史。默认 provider 仍为 `stub`；显式 `deepseek` 只证明装配路径存在，不代表目标环境已启用或真实知识/业务结果可出域 |
| 当前允许实施范围 | `WP-BUSINESS-ANSWER-V2-LOCAL-01`、Employee candidate-04及Transaction candidate-02 non-live准备均已完成，`GATE-053/054/055`关闭；两域下一步只能以各自冻结run/manifest/auth另行精确申请`GATE-024/026`。当前不得读取密钥、产生outbound或复用旧候选 |
| 当前禁止动作 | 修改 answer v1、`CandidateAnswer`、parser、grounding validator、公共 Core/HTTP/Stage 契约、领域参数/字段/授权，改写任何历史 manifest/evidence，默认启用 `deepseek`，或复用 Employee candidate-03、Transaction candidate-01 的旧源码绑定执行 live |
| 修改权限 | 用户目标模式授权为关闭 P3 门禁执行必要的聚焦设计修订、评审与实现；本轮文档和 non-live 代码可修改，真实 Transaction 外发仍须冻结 run/manifest 后按 `GATE-026` 精确执行 |

## 2. 修改历史

| 序号 | 日期 | 位置 | 修改原因 | 修改内容 |
|---:|---|---|---|---|
| 1 | 2026-07-25 | 全文 | 第二批 L2 详细设计 | 创建 DeepSeek 接入、模型输入治理、动作选择、受控回答及实现测试落点 |
| 2 | 2026-07-25 | 7.4、8.2～8.3、12.2、13、17 | 作者第 1 轮自检修复 | 删除官方正式契约未列出的 `parallel_tool_calls` 字段，补充内聚/耦合依据、JSON Output 参数和建议修改路径标记 |
| 3 | 2026-07-25 | 1、2、17～18 | 原子同步 `L2_00_01` v0.4 契约状态 | 更新直接依赖版本/评审状态；模型节点仍只消费 graph wrapper 投影的窄问题输入，不读取 Capability 执行上下文，本文设计规则不变 |
| 4 | 2026-07-25 | 14、18～19 | 本批次收口校验 | 执行严格文档校验并记录 0 errors、0 warnings；状态仍为 Draft，不替代独立评审或真实模型 PoC |
| 5 | 2026-07-25 | 1～16、18～20 | 独立评审第 1 轮修复 | 以运行入口外层装饰器绑定安全模型上下文；增加绝对总截止、流式响应上限和 HTTPX 出域配置；补齐 task/DTO/grounding/JSON 契约、复合敏感分类、完整请求预算、Provider 响应兼容及 action/answer 双路径 PoC 门禁 |
| 6 | 2026-07-25 | 3.4、4、7.5、8.5、13～14、18～20 | 独立评审第 2 轮修复 | 补齐 15 条权威设计规则、Runtime 子截止术语、可配置响应上限、非 200 零正文读取和 answer PoC 独立追踪 |
| 7 | 2026-07-25 | 7.2～7.3、9.1、11～14、18～20 | 独立评审第 3 轮修复 | 增加 Provider-neutral transport 端口与精确响应模型，封装 DeepSeek DTO；明确 Knowledge task 超时继承及 PoC 单 case 下限 |
| 8 | 2026-07-25 | 7.3、10.2、12.1、12.3、13.1、18～20 | 独立评审第 4 轮修复 | 精确化 neutral request/tool/context 字段，统一设置类名和失败映射签名，修正 stub client 生命周期及 readiness 所有权 |
| 9 | 2026-07-25 | 1～20 | 独立评审第 5 轮终审 | 全量复核无新增 S0/S1/S2，关闭 `REV-MODEL-001`～`020`，版本升为 v0.3、状态改为 Approved；所有实施/PoC/真实数据门禁保持 Open |
| 10 | 2026-07-25 | 1、7.3、8.1、13.1、14、18、20 | `L2_01_00` 消费契约针对性补正 | `QuestionEgressDecision` 在 allowed/denied 两类决定中均返回代码绑定策略版本，使 Knowledge 能先显式判定问题出域；不改变 `ModelProviderFailureKind`、Provider、节点决定或门禁 |
| 11 | 2026-07-25 | 1 | 第二批 L2 终审状态原子同步 | 明确五轮评审及针对性复评的统一状态；不改变模型契约、实施/PoC/出域门禁或运行事实 |
| 12 | 2026-08-01 | 1～2、6、13～16、19～20 | `WP-MODEL-LOCAL-01` 实施完成后的原子证据同步 | 记录本地 stub 模型边界、97 项模型相关测试及全量 158 项回归、严格类型/依赖验证和 1 轮代码对照设计评审；关闭 `CR-GATE-002`、版本升为 v0.5；真实 transport、PoC、敏感问题与真实数据门禁保持 Open |
| 13 | 2026-08-03 | 1～2、6、12～16、19～20 | `WP-MODEL-POC-01` 实施与 live 证据原子同步 | 记录隔离 transport、httpx 依赖、严格 fake/secret/预算测试和 append-only PoC 结果；30 次 action 中 29 次结构有效、6 次 answer 全部结构/grounding 有效，故工作包执行完成但 `SA-GATE-002` 继续 Open，Runtime 组合根保持 stub-only |
| 14 | 2026-08-06 | 1～2、8.2、13～16、19～20 | `WP-MODEL-RUNTIME-01/GATE-020` 前置修复、PoC 与失败关闭同步 | 将 action 代码绑定指令最小收紧并升为 `action-selection-v2`；非 live 125 项通过后只执行一次固定 30 次 action PoC，结果 23/30 结构/预期有效且 Transaction 三 case 为 0/3、2/3、0/3；保留 append-only 失败证据，`SA-GATE-002` 保持 Open，未实施 Runtime wiring |
| 15 | 2026-08-07 | 1～20 章 | 将动作模型契约改为 selection-only v3：全部工具执行参数固定空对象，只返回实际注册 capability ID；业务参数完全退出模型职责 | 与 L0 v0.6、L1_00 v0.3、L2_00_01 v0.6 对齐，消除 v2 参数幻觉失败面；历史 evidence 不覆盖、不改判 |
| 16 | 2026-08-07 | 1～2、13～16、19～20 | `WP-MODEL-ACTION-POC-02` 非 live 实施证据原子同步 | `IMPL-MODEL-007/008/018` 的 v3 空参数投影、ID-only selector、actual-ID fixture、严格 manifest/hash 与 one-shot Harness 已实现；`VAL-MODEL-006` 23 passed、完整 Runtime 回归 534 passed/6 skipped、strict mypy 238 files 通过。冻结候选 manifest 后仍未调用 DeepSeek，工作包保持 Blocked，`GATE-035/GATE-020/SA-GATE-002` 保持 Open |
| 17 | 2026-08-07 | 1～16、19～20 | v3 一次性 PoC 失败后的 v4 契约修订 | 固化 v3 30/30 已完成但 17/30 结构、3/30 预期的 append-only 失败证据及已消费授权；动作选择改为正式端点 JSON Output 的精确 `capability_id` envelope，新增独立 v4 非 live/PoC 门禁，保持 ID-only 中立契约、Core、Resolver、领域参数和默认 stub 不变 |
| 18 | 2026-08-07 | 1～2、6～16、18～20 | v4 JSON Output 独立聚焦评审修复 | 唯一化模型可见 catalog/envelope/hash、Provider wire 和 exact decoder；收紧模型安全展示元数据与失败映射；以 v3 manifest/hash + Git 来源提交冻结历史 provenance；确认门禁 DAG 无环且 `GATE-036` 仅满足评审子条件 |
| 19 | 2026-08-07 | 1～2、13～16、18～20 | `WP-MODEL-ACTION-V4-LOCAL-01` 限定实施、验证与代码对照设计复核 | 实现模型安全 catalog、no-tools JSON Output、exact ID decoder、语义有效 v4 fixture、严格 manifest/Harness/Schema、单员工详情通用意图窄放行及具体标识零调用；修复结果 Schema 阈值自校验缺口，冻结未消费候选 manifest；`VAL-MODEL-008`、完整回归、strict mypy、compileall 与代码对照设计复核通过，关闭 `GATE-036`；不调用 DeepSeek、不接 Runtime |
| 20 | 2026-08-10 | 1～2、7.5、8.2、13～16、19～20 | candidate-01 一次性 PoC 失败后的 fixture 语义修订 | 固化30/30结构、27/30聚合但 `transaction_fields=0/3` 的 append-only 失败证据及已消费授权；确认“字段说明”超出 `transaction.search` 的执行语义，不修改模型契约或阈值；设计版本化 corrected fixture、candidate-01 Git provenance、candidate-02 非 live/付费门禁和新 run/manifest，旧结果不得重判 |
| 21 | 2026-08-10 | 1～2、13～20 | `WP-MODEL-ACTION-POC-04` corrected 非 live 实施与代码对照设计复核 | 新增 `action_selection_v4_2.json`、历史/current 严格 case/文件集合、candidate-01 commit provenance 与 candidate-02 manifest；46项精确测试、161项模型相关、564 passed/6 live skipped全量回归、strict mypy 239 files、compileall及代码复核通过。`VAL-MODEL-010`完成；`GATE-038/020/SA-GATE-002`保持Open，未读取key或产生真实outbound |
| 22 | 2026-08-10 | 1～2、13～16、18～20 | `WP-MODEL-ACTION-POC-04` candidate-02 一次性 live PoC 与门禁状态同步 | 绑定run/manifest/hash执行恰好30次：结构、预期、arguments空均30/30，逐case均3/3，真实业务执行0；严格结果和consumed哈希已复核，`VAL-MODEL-011`通过并关闭`GATE-038`。不实施Runtime wiring，`GATE-020/SA-GATE-002`继续Open |
| 23 | 2026-08-12 | 1～2、12～16、19～20 | `WP-MODEL-RUNTIME-01` 受控装配、验证与代码对照设计复核 | 默认 `stub` 不变；显式 `deepseek` 装配复用既有 transport/selector/answer/context，新增 client 所有权、幂等关闭和 lifespan 接缝；复核补齐answer组合根与无效参数在client分配前失败测试。168项模型定向、570项全量非live、241文件strict mypy与compileall通过；关闭`GATE-020/SA-GATE-002`，`CR-GATE-003/SA-GATE-006`及领域出域门禁保持Open |
| 24 | 2026-08-12 | 1～2、8、10、13～16、19～20 章及 Knowledge/Business L2 | 问题出域非 live 安全证据补齐与门禁关闭 | 使既有业务敏感 fixture 精确命中全局类别并由 `TEST-BQCOM-013` 消费；新增 Employee 姓名、Transaction 金额、Knowledge rewrite→Evidence 传播及 fresh Guard 零 transport 证据。172项模型/安全定向、578项全量非live、243文件strict mypy与compileall通过；`CR-GATE-003`仅按问题输入安全前置关闭，真实数据出域与目标环境启用仍禁止 |
| 25 | 2026-08-14 | 1～4、8、13～16、18～20章及Business/Transaction L2、P3_00 | `GATE-026` 问题策略前置聚焦修订 | 现有 Guard 将无具体值的 Transaction 结果说明问题判为 `unknown_input`，导致真实结果出域候选必然零调用；设计 `question-egress-v2`，仅窄放行单条交易结果的类型/金额通用说明，敏感类别继续优先拒绝。历史策略和 evidence 不改写，non-live实现与新候选须经独立评审；live仍受`GATE-026` |
| 26 | 2026-08-14 | v0.18增量及Business/Transaction/P3追踪 | 三轮聚焦独立评审—修复 | 第1轮确认deny优先与exact fullmatch；第2轮收紧live查询值为进程内存输入且历史v1从冻结提交验证；第3轮复核Provider-neutral ID、公共决定、失败语义及门禁无环，无未关闭S0/S1/S2；只授权non-live实现 |
| 27 | 2026-08-14 | 1～4、8、13～16、18～20章及Business/Transaction L2、P3_00 | `WP-TXN-EGRESS-CANDIDATE-01-PREP`实施、冻结与代码对照设计复核 | 实现exact `question-egress-v2`、具体值/敏感/unknown零调用、历史PoC哈希兼容，并以fake transport验证1次search/30次answer、type/amount精确facts及Decimal grounding；冻结run `transaction-egress-v1-20260814-candidate-01`、manifest SHA-256 `dba4610cc0e578e65c45b49b288ce9d4b74b90eea9f9d05609e7935dd2feac44`和`P3_00:GATE-026`；真实调用为0，`GATE-026/SA-GATE-006`保持Open |
| 28 | 2026-08-17 | 1～4、8.3、13～20章及Business/Employee/Transaction L2、P3_00 | Employee candidate-03失败后的Business Answer v2聚焦设计 | 归档`failed_consumed`、30/30 `invalid_output`及五项SHA；确认模型可见v1指令未表达validator要求的行内fact marker。新增独立`answer-generation-v2`，仅强化模型输出约束并切换生产组合根；v1、parser、validator、公共契约和历史资产保持不可变。Employee candidate-03与Transaction candidate-01均退役为历史绑定，后继必须新建候选 |
| 29 | 2026-08-17 | 1～4、8.3、13～20章及Business/Employee/Transaction L2、P3_00 | `WP-BUSINESS-ANSWER-V2-LOCAL-01`实施、历史兼容与门禁闭环 | 新增独立`answer_generator_v2.py`并使生产组合根唯一装配`answer-generation-v2`；v1 DTO/parser、grounding、公共契约及历史资产不变。20项核心定向与67项完整相关定向通过；全量non-live 1024 passed/23 skipped/1既有历史deselect，strict mypy 354 files及compileall通过；代码对照设计复核无blocker/high/medium，真实outbound=0，关闭`GATE-053` |
| 30 | 2026-08-17 | 1～2、13～20章及Business/Employee L2、P3_00 | `WP-EMP-EGRESS-CANDIDATE-04-PREP/GATE-054` non-live闭环 | 全新candidate-04冻结当前`answer-generation-v2`与Runtime bootstrap，复用3/1/1+detail1+answer30和严格grounding边界；三轮内审、23项定向、405项Employee/Business回归、全量non-live 1047 passed/24 skipped/1既有历史deselect、strict mypy、compileall、AST、Java disabled及代码复核通过。manifest SHA-256=`b2de9dce219fa8de1bba4e96b68951ad51b46407d8c5b91240a23531ab4328eb`，未读取密钥或产生outbound；关闭`GATE-054`，`GATE-024`保持Open |
| 31 | 2026-08-17 | 1～2、13～20章及Business/Transaction L2、P3_00 | `WP-TXN-EGRESS-CANDIDATE-02-PREP/GATE-055` non-live闭环 | 全新candidate-02冻结当前`answer-generation-v2`与Runtime bootstrap，复用1次search、30次answer、精确Decimal及严格grounding边界；candidate定向22 passed/1 live skipped、Transaction/Business 169 passed/3 skipped、strict mypy 110 files、compileall、AST、历史hash与代码复核通过。manifest SHA-256=`527845915ad15aa6f24fe59ed31885dcd3fef245109e7cee820217a86cbafa9c`，未读取密钥或产生outbound；关闭`GATE-055`，`GATE-026`保持Open |

## 3. 背景、目标与范围

### 3.1 背景与问题

`L1_00` 已选择 DeepSeek `deepseek-v4-pro`，但模型是外部、不可信且具有数据出域效应的依赖。模型既不能直接取得完整 Agent state，也不能凭自然语言返回值绕过能力注册、参数校验或领域出域决策。本 L2 需要把供应商协议限制在 Provider 内，并在每次模型调用前执行可验证的输入闸门，在返回后执行结构、事实和边界校验。

### 3.2 目标与验收行为

| 需求编号 | 目标或可观察行为 | 验收标准 | 来源 |
|---|---|---|---|
| `REQ-MODEL-001` | 通过唯一 Provider 接入 `deepseek-v4-pro` | 供应商 DTO、URL、错误码不进入 graph/core/能力契约 | `SA-C-014`、`CR-AD-005` |
| `REQ-MODEL-002` | 用户问题在首次外发前分类和最小化 | denied/unknown 时 DeepSeek 调用为 0，返回 `input_denied` | `CR-GATE-003` |
| `REQ-MODEL-003` | 只能从冻结能力描述选择一个 canonical capability ID | 模型只接收安全 descriptor 目录并返回精确 JSON `{"capability_id":"<canonical-id\|agent_unsupported>"}`；未知/额外字段、tool call、prose 或非法 ID 均拒绝；模型不构造 `ActionCandidate` | `FR-06`、`L2_00_01` 8.6.1/11.1 |
| `REQ-MODEL-004` | 领域结果只有在明确允许且存在 safe payload 时进入模型 | Provider 接口不接受 `domain_result`；拒绝/缺失时回答模型调用为 0 | `SA-C-009/018` |
| `REQ-MODEL-005` | 候选回答受结构和事实约束 | 回答只接纳已注册 grounding policy 验证的候选；无依据内容失败关闭 | `REQ_00` 9、`L1_02` 7.6 |
| `REQ-MODEL-006` | 模型失败与无结果区分 | timeout、provider failure、invalid output 分别映射既定 `ModelNodeFailureKind` | `L2_00_01` 11.1 |
| `REQ-MODEL-007` | 模型调用受统一总预算和本地资源上限约束 | 单调用取 use-case 上限与请求剩余预算较小值；无自动重试 | `CR-AD-004/005` |
| `REQ-MODEL-008` | 凭证安全且配置失败关闭 | 真实 Provider 启用时缺少 `LLM_API_KEY` 启动失败；日志/状态不含密钥 | `L1_00` 5.2、10.2 |
| `REQ-MODEL-009` | Knowledge 可复用公共结构化生成传输而不泄漏供应商协议 | Knowledge 自有 typed port/Prompt 经代码绑定 task 调用 transport | `L1_01` 7.8 |
| `REQ-MODEL-010` | 模型契约可用性有独立 PoC 证据 | v3 与 v4 candidate-01 失败证据不得补跑、改判或用于通过结论；使用实际 Runtime capability ID、经 descriptor 语义复核并独立冻结的 corrected v4 用例达到 14.4 门槛且 answer 历史证据仍有效后，才可关闭 P3 `GATE-020` 开始受控 wiring；组合根/生命周期回归通过后才可申请关闭 `SA-GATE-002` | `GATE-020`、`GATE-036/037/038`、`SA-GATE-002` |
| `REQ-MODEL-011` | Employee/Transaction 执行参数不进入模型请求或响应契约 | tool schema、system instruction、DTO、结果和 evidence 均不含 `employee_identifier`、Transaction 条件或 descriptor 执行 Schema；本地 Resolver 路径模型调用为零 | L0 `SA-C-022`；L1_00 `CR-AD-009` |
| `REQ-MODEL-012` | 为 Transaction 真实结果回答提供不含具体值的最小问题批准路径 | 仅“单条交易结果的交易类型和金额通用说明”有限句式可分类为 `GENERIC_BUSINESS`；交易号、具体金额、账户、JWT、凭证、注入文本、控制字符、额外语义和所有 unknown 继续拒绝且 transport=0 | P3_00 `GATE-026`；L2_02_02 `SA-GATE-006` |
| `REQ-MODEL-013` | Business answer模型可见契约必须与既有确定性grounding引用语法一致 | `answer-generation-v2`明确要求每个非空事实片段包含`[fact-NNNN]`，marker集合与去重`used_fact_ids`集合相等且仅引用输入facts；不符合时继续由既有grounding失败关闭 | Employee candidate-03失败证据；`L2_02_00 DR-BQCOM-039` |

### 3.3 范围内

- `deepseek-v4-pro`、正式 `https://api.deepseek.com/chat/completions` 与 Bearer 凭证映射。
- Provider-neutral structured transport、DeepSeek HTTP adapter 和有限 use-case 定义。
- 用户问题敏感分类、确定性最小化、允许/拒绝决定和零调用语义。
- `CapabilitySelectionNode` 的 DeepSeek 实现、descriptor→安全有界目录投影及 JSON `capability_id` 校验。
- `AnswerGenerationNode` 的 DeepSeek 实现、safe payload 前置条件、结构化回答和 grounding policy 接缝。
- Knowledge 问题改写/摘要未来复用的代码绑定 structured task 机制；不定义其领域 Prompt。
- 超时、并发、token/byte 预算、错误映射、日志指标、凭证和 PoC。

### 3.4 范围外

- LangGraph state、wrapper 路由、公共状态映射；归 `L2_00_01`。
- Spring→Python 协议、接入硬截止与传给 Python 的 Runtime 子截止；归 `L2_00_00`。
- Knowledge 的改写语义、域、检索、证据、出域策略和摘要 Prompt。
- Employee/Transaction 字段分类、转换、safe payload 和业务事实规则。
- 读取/业务授权、角色白名单或业务接口。
- 模型微调、代理切换、多 Provider 自动降级、缓存、批处理、流式输出。
- 生产级配额平台、成本系统或自动重试框架。

### 3.5 适用技术剖面

| 剖面 | 适用 | 本文落实 |
|---|---|---|
| Python | 是 | Protocol/dataclass、httpx async client、Provider adapter、typed wrapper、测试 |
| 外部 HTTP/API | 是 | DeepSeek request/response、错误、超时、兼容与 PoC |
| LLM Prompt/Schema | 是 | 代码绑定系统指令；v4 action 使用安全目录与 JSON Output，历史 v1～v3 Tool Calls 仅作不可变证据；所有输出本地严格校验 |
| 安全/出域 | 是 | 问题输入闸门、领域 safe payload 前置条件、凭证和日志 |
| Java | 否 | Spring 只传播总预算；本文不新增 Java 模型客户端 |
| 持久化/迁移 | 否 | 模型请求/响应不持久化，不新增数据库或缓存 |

## 4. 上位约束与追踪关系

### 4.1 约束映射

| 约束编号 | 来源 | 约束 | 落实 | 偏离 |
|---|---|---|---|---|
| `CON-MODEL-001` | `L1_00` `CR-AD-005` | DeepSeek 置于模型端口后 | `DR-MODEL-001/002` | 无 |
| `CON-MODEL-002` | `L2_00_01` 11.1 | 模型节点只返回窄决定 | `DR-MODEL-006/009` | 无 |
| `CON-MODEL-003` | `L2_00_01` 8.2/8.6 | descriptor/候选供应商无关且核心复验 | `DR-MODEL-005/006` | 无 |
| `CON-MODEL-004` | `L1_00` 7.3 | 只有 allowed + safe payload 可生成回答 | `DR-MODEL-008` | 无 |
| `CON-MODEL-005` | `L1_00` 10.2 | 用户问题首次外发必须过闸门 | `DR-MODEL-003/004` | 无 |
| `CON-MODEL-006` | `L1_00` 10.1 | 默认不自动重试模型传输 | `DR-MODEL-011` | 无 |
| `CON-MODEL-007` | `L2_00_00` 11 | 消费同一请求的 Runtime 子截止剩余预算，不自行恢复接入层预留时间 | `DR-MODEL-010` | 无 |
| `CON-MODEL-008` | `L1_01`/`L1_02` | 领域拥有 Prompt/出域/事实规则 | `DR-MODEL-007/009` | 无 |
| `CON-MODEL-009` | `L1_00` 5.2 | `LLM_API_KEY` 外置且不泄露 | `DR-MODEL-012` | 无 |
| `CON-MODEL-010` | `SA-GATE-002/006` | 文档/接口核实不能替代 PoC 或真实数据授权 | `DR-MODEL-013/014` | 无 |
| `CON-MODEL-011` | L0 `SA-C-022`、`L2_00_01` `DR-CORE-016/017` | 模型只负责能力 ID；执行 Schema 与业务参数不进入模型；最终候选由混合节点构造 | `DR-MODEL-005/006/016/017` | 无 |
| `CON-MODEL-012` | `CR-GATE-003` 已按敏感/unknown 零调用关闭；`GATE-026` 仍Open | 新增允许项不得改变 deny 优先级或把具体 Transaction 值变成问题允许条件；策略语义变化必须升版，历史 `question-egress-v1` 证据保持不可变 | `DR-MODEL-018` | 无 |
| `CON-MODEL-013` | `CandidateAnswer`、`BusinessAnswerGroundingPolicy`、answer v1及全部历史candidate/evidence不可变 | v2只能新增独立代码绑定task并在生产组合根唯一注册；复用v1 DTO/parser和现有validator，不得放宽接受规则、增加公共字段或把旧candidate改绑到新源码 | `DR-MODEL-019` | 无 |

### 4.2 端到端追踪矩阵

| REQ/CON | 模块切片 | 设计规则 | 责任主体 | 契约/状态影响 | 实现落点 | 测试 | 验证 |
|---|---|---|---|---|---|---|---|
| `REQ-MODEL-001`、`CON-MODEL-001` | Provider | `DR-MODEL-001`、`DR-MODEL-002` | model/deepseek | 供应商隔离 | `IMPL-MODEL-001`、`IMPL-MODEL-006` | `TEST-MODEL-001` | `VAL-MODEL-002` |
| `REQ-MODEL-002`、`CON-MODEL-005` | 输入闸门 | `DR-MODEL-003`、`DR-MODEL-004` | input guard | question decision | `IMPL-MODEL-003`、`IMPL-MODEL-004` | `TEST-MODEL-002`、`TEST-MODEL-003` | `VAL-MODEL-002` |
| `REQ-MODEL-003`、`REQ-MODEL-011`、`CON-MODEL-003`、`CON-MODEL-011` | 能力选择 | `DR-MODEL-005`、`DR-MODEL-006`、`DR-MODEL-016`、`DR-MODEL-017` | capability selector | catalog + JSON ID→canonical ID | `IMPL-MODEL-007`、`IMPL-MODEL-008`、`IMPL-MODEL-019`、`IMPL-MODEL-020` | `TEST-MODEL-004`、`TEST-MODEL-014/015` | `VAL-MODEL-003`、`VAL-MODEL-008/010/011` |
| `REQ-MODEL-004`、`CON-MODEL-004` | 回答前置 | `DR-MODEL-008` | answer generator | safe payload only | `IMPL-MODEL-009` | `TEST-MODEL-005` | `VAL-MODEL-003` |
| `REQ-MODEL-005`、`CON-MODEL-008` | 回答校验 | `DR-MODEL-007`、`DR-MODEL-009` | grounding registry | typed policy | `IMPL-MODEL-005`、`IMPL-MODEL-010` | `TEST-MODEL-006` | `VAL-MODEL-003` |
| `REQ-MODEL-006`、`CON-MODEL-002` | 失败映射 | `DR-MODEL-015` | Provider wrappers | failure kind | `IMPL-MODEL-006`、`IMPL-MODEL-011` | `TEST-MODEL-007` | `VAL-MODEL-002` |
| `REQ-MODEL-007`、`CON-MODEL-006`、`CON-MODEL-007` | 预算 | `DR-MODEL-010`、`DR-MODEL-011` | gateway | deadline/concurrency | `IMPL-MODEL-002`、`IMPL-MODEL-006` | `TEST-MODEL-008` | `VAL-MODEL-002` |
| `REQ-MODEL-008`、`CON-MODEL-009` | 凭证 | `DR-MODEL-012` | settings/client | secret lifetime | `IMPL-MODEL-002`、`IMPL-MODEL-006` | `TEST-MODEL-009` | `VAL-MODEL-004` |
| `REQ-MODEL-009`、`CON-MODEL-008` | Knowledge 扩展 | `DR-MODEL-007` | structured gateway | code-bound tasks | `IMPL-MODEL-005` | `TEST-MODEL-010` | `VAL-MODEL-003` |
| `REQ-MODEL-010`、`CON-MODEL-010` | PoC/门禁 | `DR-MODEL-013`、`DR-MODEL-014`、`DR-MODEL-016`、`DR-MODEL-017` | live PoC | 合成输入与 append-only 历史/当前证据 | `IMPL-MODEL-012`、`IMPL-MODEL-017`～`020` | `TEST-MODEL-011`～`015` | `VAL-MODEL-005`～`011` |
| `REQ-MODEL-012`、`CON-MODEL-012` | Transaction通用结果问题窄放行 | `DR-MODEL-018` | question policy/input guard | `question-egress-v2` allow/deny决定；公共决定结构不变 | `IMPL-MODEL-021` | `TEST-MODEL-018` | `VAL-MODEL-014` |
| `REQ-MODEL-013`、`CON-MODEL-013` | Business answer v2模型可见引用契约 | `DR-MODEL-019` | model/deepseek task与Runtime组合根 | 只升task version和system instruction；`CandidateAnswer`/parser/grounding/HTTP不变 | `IMPL-MODEL-022` | `TEST-MODEL-019` | `VAL-MODEL-015` |

## 5. 关联资源与责任边界

| 资源 | 角色 | 本文职责 | 对方职责 | 契约 | 修改权限 |
|---|---|---|---|---|---|
| `REQ_00`、`L0_00`、`L1_00` | parent | 下沉模型细节 | 规定范围、边界、门禁 | 上位约束 | 只读 |
| `L2_00_01` | peer/direct dependency | 实现其 `CapabilitySelectionNode` 与 `AnswerGenerationNode` | 定义窄输入/决定、混合裁决和公共映射 | Python Protocol | 只读 |
| `L2_00_00` | peer | 消费 deadline/context | 定义总预算与跨进程请求 | 执行 scope | 只读 |
| Knowledge L2 | peer | 提供结构化传输和全局输入闸门 | 定义改写/摘要 Prompt、证据与 grounding | typed task adapter | 只读 |
| 业务查询 L2 | peer | 提供全局输入/回答 Provider | 定义字段、safe payload 与事实规则 | grounding policy | 只读 |
| DeepSeek API | external_contract | 严格适配与错误转换 | 提供模型 API | HTTPS JSON | 外部只读 |
| `LLM_API_KEY` | implementation baseline | 只读取并包装 | OS 环境提供 | secret string | 只读，不输出 |

官方证据：

- [DeepSeek 首次 API 调用](https://api-docs.deepseek.com/)列出 `https://api.deepseek.com` 与 `deepseek-v4-pro`。
- [Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion)定义 tool calls、JSON output、finish reason 和响应结构，并明确工具参数仍需调用方校验。
- [JSON Output 指南](https://api-docs.deepseek.com/guides/json_mode/)提示需显式 JSON 指令，且响应可能为空。
- [Tool Calls 指南](https://api-docs.deepseek.com/guides/tool_calls/)将 strict 模式标记为 Beta 并要求使用 `/beta` 基地址；本文不采用该扩展。
- [错误码](https://api-docs.deepseek.com/quick_start/error_codes/)定义 400/401/402/422/429/500/503；本文均不把它们视为业务无结果。
- 2026-07-25 使用环境中的 `LLM_API_KEY` 对 `/models` 做只读调用，返回 `deepseek-v4-pro`；未输出密钥，未执行生成调用。

## 6. 当前实现基线与最小变更方案

### 6.1 已核实事实

1. `LLM_API_KEY` 在当前进程 OS 环境存在；2026-08-01 只核实存在性，未输出值，也未发起生成调用。
2. `agent-runtime/src/agent_runtime/model` 已实现 Provider-neutral 契约、输入闸门、代码绑定 task/gateway/grounding、ContextVar 装饰器、DeepSeek DTO/节点纯投影；`agent-runtime/src/agent_runtime/bootstrap.py` 只允许本地组合根使用 `stub` provider 和注入的 fake transport。
3. `L2_00_01` v0.5 的既有 Core 已实现；v0.6 将模型接缝收窄为 `CapabilitySelectionInput/Decision`，并由混合节点独占最终 `ActionCandidate` 构造。Core/graph 继续不导入 DeepSeek/httpx DTO。
4. 2026-08-03 模型/fake/架构相关测试 118 项、全量 Runtime 327 项通过；`mypy --strict` 与 `compileall` 通过。当前已安装环境的 `pip check` 因既存依赖版本偏差和缺少 `inflect` 未通过，不能宣称依赖环境完全一致。
5. `DeepSeekChatTransport`、`httpx==0.28.1`、opt-in PoC runner 和 append-only 结果已存在，且 `/models` 对当前凭证确认 `deepseek-v4-pro` 可用。v3 run `action-selection-v3-20260807-candidate-01` 已按绑定授权完成恰好 30 次请求：17/30 结构有效、3/30 命中预期、仅 unsupported case 达到 3/3，真实业务调用为 0；结果文件 SHA-256 为 `1947D17872FDBA8FF9DEFEFC3E2D0F282CB1552FFCFA2D491D67C7EF3C360E0A`，消费标记 SHA-256 为 `D60298139EBD2D3FA1E8EE53D823AAAA410812C5EA47A97117CD670B8FEB98E3`。该结果失败且授权已耗尽，不得补跑、续跑或改判。
6. 历史 Agent/ES 代码不构成目标模型实现基线。

### 6.2 最小变更方案

| 变更 | 必要性 | 选择 | 不采用 |
|---|---|---|---|
| Provider-neutral structured gateway | 多场景共用传输且隔离供应商 | 代码绑定有限 task | 允许调用方传任意 Prompt/schema，会形成通用模型执行平台 |
| DeepSeek async HTTP client | LangGraph 异步与取消 | `httpx.AsyncClient`、正式 endpoint、non-stream | SDK 会引入供应商/兼容层行为且仍需自定义校验；本期直接 HTTP 更透明 |
| 能力选择 JSON Output | 只需要从实际启用 descriptor 中选择 ID；v3 证明空参数 Tool Calls 在当前正式端点不稳定 | 投影安全 descriptor 目录，`response_format=json_object`，只接纳精确单字段 `capability_id` envelope，并在本地按本次目录复验 | 继续空参数 Tool Calls 会重复已证实失败；Beta strict 需要 `/beta` 且扩大外部契约；宽松解析/丢弃参数会掩盖异常 |
| 回答 JSON Output | 校验 answer 与事实引用 | 结构化 envelope + grounding policy | 直接接纳自然语言 content 无法验证 |
| thinking disabled | 避免 reasoning_content、多轮和高延迟 | 所有本期 task 禁用 | 默认 thinking 增加协议和预算复杂度 |
| zero automatic retry | 避免重复收费和预算放大 | 一次传输失败即 typed failure | Provider 内隐式重试会绕过 LangGraph 决策 |

## 7. 职责、依赖与公共类型

### 7.1 责任分解

| 组件 | 状态 | 唯一职责 | 明确不负责 |
|---|---|---|---|
| `QuestionEgressGuard` | 已存在 | 问题分类、最小化和允许/拒绝 | 动作选择、业务授权 |
| `StructuredModelGateway` | 已存在 | 执行代码绑定 task、预算/并发/共同校验 | 领域 Prompt/事实规则 |
| `DeepSeekChatTransport` | 已存在（隔离，未接 Runtime） | HTTP、凭证、供应商 DTO 和错误转换 | graph state、领域结果 |
| `DeepSeekCapabilitySelector` | v3 已存在；v4 待修改 | descriptor→安全有界目录、精确 JSON 响应→canonical ID 窄决定 | 参数生成、核心授权/执行 |
| `DeepSeekAnswerGenerator` | 已存在（fake/历史 PoC） | safe payload→结构化回答候选 | 领域出域策略计算 |
| `GroundingPolicyRegistry` | 已存在 | 按 canonical capability ID 取得代码绑定验证器 | 动态插件、角色或字段配置 |
| 领域 grounding policy | Knowledge/Business 本地实现已存在；真实出域待门禁 | 验证候选回答仅使用本域事实 | Provider 协议 |

### 7.2 依赖方向

```text
L2_00_01 CapabilitySelectionNode / AnswerGenerationNode
  ← DeepSeekCapabilitySelector / DeepSeekAnswerGenerator
      → QuestionEgressGuard
      → StructuredModelGateway
          → StructuredModelTransport
              ← DeepSeekChatTransport

DeepSeekAnswerGenerator
  → GroundingPolicyRegistry
      ← Knowledge / Business code-bound grounding policies
```

- core/graph state 不导入 DeepSeek/httpx/provider DTO。
- `DeepSeekChatTransport` 不导入 capability handler、domain result 或 LangGraph Runtime。
- 领域模块只依赖 provider-neutral task/grounding Protocol，不依赖 DeepSeek request/response。
- question、safe payload、Prompt 和 model response 仅存在当前调用栈，不进入持久化或共享 state。

### 7.3 公共类型

| 类型 | 字段/语义 |
|---|---|
| `QuestionDataClass` | `public_knowledge/generic_business/personal_identifier/employee_identifier/transaction_identifier/financial_account/contact/credential_or_secret/instruction_injection/free_text_sensitive/unknown`；分类器内部返回非空 `frozenset`，不是单值覆盖 |
| `QuestionEgressDecision` | `disposition: allowed/denied`、两类均必填 `policy_version`；allowed 仅增加 `minimized_question`，denied 仅增加 `reason_code`；互斥；不得携带原问题或分类命中片段 |
| `ModelTaskId` | `action_selection/answer_generation/knowledge_rewrite/knowledge_summary`；有限代码枚举 |
| `ModelCallContext` | `request_id: str`、`correlation_id: str`、`deadline_monotonic: float`；冻结；不含 JWT/subject/role |
| `ModelTaskDefinition[TInput,TOutput]` | `task_id`、`task_version`、`input_type`、`max_input_bytes`、`timeout_ms`、`max_output_tokens`、代码绑定 `build_request/parse_response`；冻结且只由组合根注册 |
| `StructuredToolDefinition` | `name: str`、`description: str`、`arguments_schema: FrozenJsonObject`；冻结、`additionalProperties=false`，不含 Provider tool ID/type/index |
| `StructuredModelRequest` | `task_id: ModelTaskId`、`task_version: str`、`system_instruction: str`、`user_payload_json: str`、`tools: tuple[StructuredToolDefinition,...]`、`tool_mode: none/required`、`output_mode: tool_calls/json_object`、`max_output_tokens: int`；冻结且只能由注册 task factory 构造 |
| `StructuredToolCall` | `name`、`arguments_json`；不含 Provider tool ID/type/index，arguments 尚未做 task schema 校验 |
| `StructuredModelResponse` | `finish_kind: tool_calls/stop`、`content: str \| None`、`tool_calls: tuple[StructuredToolCall,...]`、`usage_total_tokens: int \| None`；均为严格校验后的 Provider-neutral 字段，不含 raw JSON、reasoning content、model 或供应商 DTO |
| `CandidateAnswer` | `answer`、去重 `used_fact_ids`、空 `unsupported_claims`；从严格 JSON Output 解析，不含供应商对象 |
| `GroundingInput` | canonical capability ID、已允许的 minimized question、深冻结 safe payload、`CandidateAnswer` |
| `GroundingDecision` | `accepted: bool`、拒绝时有限 reason enum；不转换答案、不携带原始异常 |

`StructuredModelRequest` 构造器不对任意调用方公开；运行时只通过 `ModelTaskDefinition.build_request` 创建。task definition tuple 在组合根显式绑定并冻结，配置不能增加 Prompt、schema、class 或 endpoint。

### 7.4 内聚与耦合判断

共同传输、凭证、预算和供应商错误聚合在 `StructuredModelGateway`/`DeepSeekChatTransport`，因为它们只因模型提供方或通用调用规则变化；问题分类由输入安全策略拥有，领域 Prompt、safe payload 与事实验证仍由对应能力拥有。`GroundingPolicyRegistry` 只保护“公共回答生成必须取得领域验证器”这一稳定边界，不实现领域字段规则。该分解避免 Provider 依赖业务 DTO，也避免各能力复制 DeepSeek 协议；新增 task 仍需代码和设计，不演化为动态 Prompt 平台。

### 7.5 设计规则目录

| 设计规则 | 权威规则 |
|---|---|
| `DR-MODEL-001` | graph/core/能力只依赖 Provider-neutral 模型端口；DeepSeek/httpx DTO 只能存在于 model/deepseek adapter，模型上下文由不侵入 core 的同签名运行入口装饰器绑定。 |
| `DR-MODEL-002` | DeepSeek transport 固定正式 HTTPS endpoint、`deepseek-v4-pro`、禁用 thinking/stream、严格请求/响应 DTO 与 JSON 兼容边界；调用方不得传入 model、URL、header 或供应商扩展字段。 |
| `DR-MODEL-003` | 用户问题首次外发前必须由有限、版本化、确定性的分类器收集全部类别；任何 deny 命中优先，未明确允许即 unknown 并失败关闭。 |
| `DR-MODEL-004` | denied/unknown 问题、缺失 safe payload 或缺失领域策略时 Provider 调用必须为 0；允许输入只能使用确定性最小化结果，拒绝决定不得保留原文。 |
| `DR-MODEL-005` | 能力选择只能把冻结 `CapabilityDescriptor` 的 canonical ID、display name、经模型安全文本校验的 description、aliases 按 ID 排序投影为 `{"capabilities":[...]}`；再与 minimized question 组成独立请求 envelope。目录必须另含固定 `agent_unsupported`，禁止读取、复制或摘要执行 `argument_schema`，禁止包含 URL、角色、物理资源、wire/执行参数名或具体查询值。catalog hash 只覆盖 canonical catalog object，不覆盖问题。 |
| `DR-MODEL-006` | action v4 请求必须使用正式 `/chat/completions`、`response_format={"type":"json_object"}`、neutral `tools=()`/`tool_mode=none`，Provider wire 必须省略 `tools/tool_choice`，并禁用 thinking；模型输出只接纳结构精确的单对象单字段 `{"capability_id":"..."}`，值必须属于本次目录或 `agent_unsupported`。JSON 根前后仅允许 JSON whitespace，不要求模型字节等于 canonical 序列化；空 content、未知/额外字段、重复 key、tool call、prose、非法 ID 均为 `invalid_output`；输出只转换为 `CapabilitySelectionDecision`，不得构造 `ActionCandidate`。 |
| `DR-MODEL-007` | task、Prompt、输入/输出 schema 与 grounding policy 必须由代码绑定并在组合根冻结；领域拥有其 Prompt、safe payload 与语义规则，公共层不得演化为动态 Prompt 平台。 |
| `DR-MODEL-008` | 回答生成仅接收已允许问题和领域显式 safe payload；不得接收完整 domain result、JWT、角色、下游地址或授权策略。 |
| `DR-MODEL-009` | 回答候选必须通过严格 JSON 结构、fact ID 子集与 capability 专属 deterministic grounding policy；任何未知字段、未支持主张或验证异常均丢弃全文。 |
| `DR-MODEL-010` | permit、连接池等待、网络、keep-alive、流式读取、解析和校验共享一个不晚于 Runtime 子截止的绝对截止，并受完整请求、响应、token 与并发上限约束。 |
| `DR-MODEL-011` | Provider 传输、HTTP transport 与 wrapper 自动重试均为 0；模型调用不缓存、不重放，未来语义重试只能由 LangGraph 在同一请求预算内显式设计。 |
| `DR-MODEL-012` | `LLM_API_KEY` 只在启动期读取并最小生命周期 reveal；client 禁止环境代理、redirect 和隐式 retry，日志、健康状态、异常及对象表示不得包含 secret 或内容正文。 |
| `DR-MODEL-013` | 官方契约核实、本地替身测试与真实 DeepSeek action/answer PoC 是不同证据；只有经单独授权的合成非敏感 PoC 达到固定门槛，才可申请关闭可行性门禁。 |
| `DR-MODEL-014` | 设计批准不关闭实施、敏感问题或真实领域数据门禁；未分类、策略缺失/冲突和证据不足均失败关闭，任何门禁状态只由其规定证据改变。 |
| `DR-MODEL-015` | 所有 Provider HTTP、transport、parse、finish reason、model 与 grounding 失败必须穷尽映射为有限 failure kind；不得携带响应正文、异常消息、Prompt 或供应商 DTO。 |
| `DR-MODEL-016` | 新 action task 版本固定为 `action-selection-v4`；v1/v2/v3 及 v4 candidate-01 的 fixture、manifest、消费标记与 result/evidence 都是 append-only 历史资产，不得覆盖、补跑、续跑、改判或用于关闭后继门禁。v3 执行源码身份由 manifest 内文件哈希和 Git 提交 `f6274b2b21420d2b2b3d0f4b693978fa4526ef57` 冻结；v4 candidate-01 源码身份由 manifest 内文件哈希和 Git 提交 `cd8007e58bbeca902bec722eb98bbfbf8fe7c55f` 冻结。当前工作树可为 corrected v4 fixture 正常演进，但历史校验必须读取对应提交/既有哈希，不能反向要求当前文件保持历史 bytes，也不能改写旧 manifest/result/consumed。v4 不使用 Beta endpoint 或 strict Tool Calls。 |
| `DR-MODEL-017` | v4 PoC 必须使用 Runtime 实际 descriptor ID `knowledge.query/employee.detail/transaction.search`，以独立版本化 fixture 固定 10 个非敏感、语义与 descriptor 一致且无歧义的 synthetic case×3；`transaction.search` 只表示执行受控交易查询，不表示字段字典/接口帮助，“交易记录允许哪些字段”必须作为近域 `agent_unsupported`，并由一个独立的、输入闸门允许且明确表达交易查询意图的正向 case 保持 Transaction 三 case 覆盖。首次请求前冻结 case、模型可见 capability catalog、system instruction 与相关实现文件哈希。中立决定/evidence 只保存有限 ID/有效性，不保存完整问题、raw response、业务参数或执行 Schema；达到 14.4 全部门槛后才可进入 Runtime wiring。 |
| `DR-MODEL-018` | `question-egress-v2` 只能在现有 deny 检测全部执行后，把规范化且完整匹配“概述/说明/总结单条交易结果的交易类型和金额”的有限中文句式归为既有 `GENERIC_BUSINESS`；不得新增公共枚举或放宽为 substring/模糊匹配。句式包含具体数字、交易标识、账户、联系方式、凭证、注入文本、控制字符、额外子句或未识别文本时继续按 sensitive/unknown 失败关闭。策略版本由 `QUESTION_EGRESS_POLICY_VERSION` 升为 `question-egress-v2`；历史 manifest/evidence 继续以原哈希/冻结提交验证，不能要求当前策略文件保持 v1 bytes。该批准只满足 `GATE-026` 问题输入前置，不授权真实结果外发。 |
| `DR-MODEL-019` | 新建独立`answer-generation-v2` task，复用v1的`AnswerGenerationInput`、请求user payload投影、严格response parser和`CandidateAnswer`。v2 system instruction必须同时明确：输出仍精确为`answer/used_fact_ids/unsupported_claims`三字段；每个非空事实片段含至少一个输入fact对应的行内`[fact-NNNN]`；marker不得未知或重复失配；`used_fact_ids`必须去重且集合精确等于answer中的marker；`unsupported_claims=[]`；示例必须同时展示行内marker和相同ID数组。生产组合根只注册v2，v1源码字节、公共DTO/parser、`BusinessAnswerGroundingPolicy`接受规则、领域safe payload、历史manifest/evidence均不得修改。组合根变化使旧领域candidate的current-source绑定失效：Employee candidate-03已消费失败、Transaction candidate-01虽未消费但均只能作为历史，不得复用其authorization执行live。 |

## 8. 详细功能与流程设计

### 8.1 问题输入闸门

校验顺序：

1. 必须是已由 `L2_00_01` 限制的非空字符串。
2. Unicode NFC、去首尾空白、连续空白折叠；不删除否定、时间、数字或标点。
3. 在最小化前以有限检测器收集全部命中类别；拒绝 NUL、不可见控制符、疑似
   JWT/API key/private key/password、Prompt/角色覆盖指令，以及个人、员工、交易、金融账户、
   联系方式和自由文本敏感模式。
4. 分类结果是非空集合；任何 deny 类别命中都优先于
   `public_knowledge/generic_business`，不得以后匹配覆盖前命中。没有明确 allow 类别时加入
   `unknown` 并拒绝。
5. 只有分类集合是 `{public_knowledge}`、`{generic_business}` 或二者组合，且
   `generic_business` 满足代码注册的非敏感句式时才允许；任何其他组合均拒绝。
6. allowed 返回最小化问题和策略版本 `question-egress-v1`；denied 返回同一代码绑定策略版本
   和有限 reason code，但不返回问题副本、命中类别或片段。调用方必须先检查 disposition，
   不得因为取得 policy version 而读取不存在的 minimized question。

首期允许示例：

- “增值税小规模纳税人的现行政策是什么”
- “查询员工列表支持哪些条件”
- “查询交易记录支持哪些时间范围”

首期拒绝示例：

- 含完整/疑似身份证、手机号、银行卡、账户、JWT、API key。
- 含具体员工编号、交易号且规则尚未提供可验证的本地占位/恢复机制。
- 无法确认是否公开或可能包含自由文本敏感内容的问题。

该分类是外发控制，不是业务动作授权。拒绝时 `CapabilitySelectionDecision.failure(kind=input_denied)`，由混合节点和核心 wrapper 映射 `model_egress_denied/model.input_denied`，DeepSeek transport 调用计数必须为 0。Employee/Transaction 的本地 Resolver 路径不调用本闸门之后的 DeepSeek selector。

### 8.2 动作选择

#### 8.2.1 selection-only capability catalog 投影

每个启用 `CapabilityDescriptor` 按 canonical capability ID 升序投影一个模型可见目录项，固定 `agent_unsupported` 排在最后。`capability catalog` 的唯一 canonical 对象是 `{"capabilities":[...]}`；以下完整对象是 action task 的 user payload envelope，`question` 不属于 catalog，也不进入 catalog hash：

```json
{
  "capabilities": [
    {
      "capability_id": "knowledge.query",
      "display_name": "Knowledge Query",
      "description": "查询已注册知识域并返回有证据的答案",
      "aliases": ["knowledge", "tax policy"]
    },
    {
      "capability_id": "agent_unsupported",
      "display_name": "Unsupported",
      "description": "当前能力目录不能处理该问题",
      "aliases": []
    }
  ],
  "question": "<minimized>"
}
```

- 目录项只允许 canonical ID、display name、description、aliases；ID 必须精确服从 `L2_00_01` canonical 语法并与冻结 descriptor 相同，aliases NFC 后去重排序，业务 capability 不得占用保留值 `agent_unsupported`。
- display name、description、aliases 是能力域拥有的模型可见展示元数据，不是任意业务文档。投影前必须 NFC 规范化并执行代码绑定 `model-catalog-text-v1`：拒绝控制字符、URI/物理资源、角色/Authority、secret 模式、类/方法/DSL 片段、snake_case/camelCase wire 或执行参数名及具体标识/金额等查询值；允许“单个员工详情”“交易查询”“不支持聚合/写入”等不携带参数名和值的动作语义。当前 `employee.detail` 描述中的 `employee_identifier` 不合格，v4 非 live 工作包只能把该展示文本最小改为安全语义，不得修改 capability ID、`argument_schema`、validator、Resolver 或 handler。
- descriptor 执行 `argument_schema` 不得被 projector 读取、复制、摘要，也不得影响 DeepSeek request bytes 或 catalog hash。任一目录字段违反安全文本策略、ID/保留值/唯一性或字段上限时，返回 `CapabilitySelectionDecision.failure(invalid_output)` 且 transport=0；不得映射为 `input_denied` 或用户问题出域拒绝。
- 能力数上限 32，加一个 fixed unsupported。catalog 先 canonical UTF-8 序列化；再与 minimized question 组成上例 envelope，并以 action task 的 65536-byte `max_input_bytes` 对完整 envelope 统一计数。不得把 catalog 和 question 分别各允许 65536 bytes。PoC catalog hash 精确覆盖 canonical `{"capabilities":[...]}`，不包含 question、完整 Prompt envelope、API key 或 Provider response。
- v4 fixture 必须与 descriptor 语义一致：`employee.detail` 只使用“按单个员工标识查询详情”类无真实标识问题，不得再用“员工列表/列表字段/列表条件”等超出 descriptor 的问题；Transaction 和 Knowledge 同样不得用能力描述不支持的语义人为制造预期标签。candidate-01 的 `transaction_fields` 问题“交易记录允许哪些字段？”属于字段字典/接口帮助，不是 `transaction.search` 执行动作，corrected fixture 必须将其作为近域 `agent_unsupported`；同时用新 case `transaction_query_items`/“查看交易记录支持哪些查询项？”补足 `transaction.search` 正向覆盖。该修正不得追溯重判 candidate-01，也不得通过扩展 descriptor、Prompt 或输入闸门让旧 gold 变成正确。

DeepSeek request 使用：

- `model=deepseek-v4-pro`
- 正式 `https://api.deepseek.com/chat/completions`
- `stream=false`
- `thinking={"type":"disabled"}`
- `temperature=0`
- Provider-neutral `tools=()`、`tool_mode=none`；投影到 DeepSeek JSON body 时必须省略 `tools` 与 `tool_choice` 两个 key，不编码为 `[]`、`null` 或字符串 `none`
- `response_format={"type":"json_object"}`
- system message 为代码常量 `action-selection-v4`，显式包含 `json` 和唯一允许的输出示例 `{"capability_id":"knowledge.query"}`；要求只返回目录中的一个 ID 或 `agent_unsupported`，禁止生成查询条件、标识、金额、分页、排序、执行工具、虚构 ID、额外字段或 prose。
- user message 是上述 envelope 的 canonical UTF-8 JSON；字段顺序不作为语义，但用于请求/manifest 哈希的本地序列化必须采用项目既有 canonical JSON 规则。

不采用 DeepSeek Beta strict Tool Calls：该方案需要切换 `/beta` 并改变当前正式外部契约。标准 JSON Output 只能保证 JSON 语法，不能保证字段或枚举语义，且官方提示可能返回空 content，因此本地精确校验与独立 live PoC 仍是必须门禁。

#### 8.2.2 输出校验

| 响应 | 决定 |
|---|---|
| `finish_reason=stop`、tool calls 缺失/空，content 是结构精确单对象、唯一字段 `capability_id`，且值属于本次 capability catalog | `candidate(capability_id)`；混合节点决定是否绑定 `{}` 或要求本地参数 |
| content 是精确 `{"capability_id":"agent_unsupported"}` | `unsupported` |
| 非 `stop`、空 content、重复 key、顶层非 object、缺失/额外字段、非字符串/未知 ID、tool call、JSON 外非空白 prose、非法/越界内容 | `failure(invalid_output)` |
| Provider timeout/failure | 对应 failure |

JSON ID 只是能力选择，不授予执行权，也不携带执行参数。`L2_00_01` 混合节点只为精确空执行 Schema 动作绑定 `{}`；模型选中非空执行 Schema 动作时固定返回 `core.local_arguments_required`，不得调用 validator 或 handler。

exact decoder 顺序固定为：先验证 `finish_reason=stop` 且 tool calls 缺失/空；再要求 content 非空并在 task 输出上限内；随后使用 unique-key parser 读取一个 JSON 根对象，JSON 根前后可有标准 JSON whitespace 但不得有其他字节；最后要求 key 集精确等于 `{capability_id}`、值是未 trim/case-fold/alias-resolve 的原始 string，并与本次 catalog canonical ID 集或 `agent_unsupported` 精确比较。模型输出不要求等于本地 canonical JSON 字节表示，避免把合法 JSON 空白/成员格式差异误判为协议漂移。

### 8.3 受控回答生成

前置条件由核心 route 保证且本实现防御性复核：

- `capability_id` 是 canonical ID。
- `safe_payload` 非空、≤65536 bytes、深度≤8、单集合≤256。
- 问题再次经过同一 `QuestionEgressGuard`；若拒绝，回答生成 transport 调用为 0。
- `GroundingPolicyRegistry` 中存在该 capability 的 policy；缺失失败关闭为 `invalid_output`，不得使用通用宽松 policy。

safe payload 必须由领域 L2 提供最小 envelope：

| 字段 | 必填 | 语义 |
|---|---:|---|
| `schema_version` | 是 | 当前 1 |
| `facts` | 是 | 有界 fact object；每项有稳定 `fact_id` 和结构化 value/source |
| `presentation` | 否 | 领域允许的格式提示，不得含系统指令 |
| `coverage` | 否 | 截断/部分覆盖元数据 |

Provider request 将固定 system instruction 与 user JSON 分离；领域文本只作为 JSON value，不拼入 system instruction。JSON Output 目标：

```json
{
  "answer": "候选事实一[fact-0001]；候选事实二[fact-0002]。",
  "used_fact_ids": ["fact-0001", "fact-0002"],
  "unsupported_claims": []
}
```

请求必须显式设置 `response_format={"type":"json_object"}`，system instruction 必须包含 JSON 输出要求和固定结构示例，并设置 task 的 `max_tokens`；生产task version固定为`answer-generation-v2`。每个非空事实片段必须带输入fact对应的行内`[fact-NNNN]`，`used_fact_ids`去重集合必须与answer marker集合相等；空 content、`finish_reason=length`、未知marker、marker/数组失配均失败关闭。

接纳顺序：

1. HTTP/JSON/finish reason 有效，content 非空且只有一个 JSON object；重复 key、未知顶层字段和类型宽松转换均拒绝。
2. `answer` 1～4096 字符；禁止控制符、工具/URL/角色/策略指令输出。
3. `used_fact_ids` 是 1～256 项的去重字符串数组，单项 1～128 ASCII 字符且全部存在于
   safe payload；`unsupported_claims` 必须是空数组。
4. capability 对应 grounding policy 验证实体、数字、状态、关系、引用和 coverage 表达。
5. 全部通过才返回 `AnswerGenerationDecision(answer)`；否则丢弃全文并返回 `invalid_output`。

模型声称引用 fact ID 不能替代语义验证。领域 policy 是事实校验权威；本文只定义调用前置、共同结构与失败关闭。

### 8.4 Knowledge 结构化任务复用

`knowledge_rewrite` 与 `knowledge_summary` 只能由 Knowledge 模块定义的 typed adapter 调用 `StructuredModelGateway`：

- Knowledge 拥有输入 DTO、Prompt、输出 DTO、语义保持/证据验证。
- 本文拥有 Provider request、凭证、共同预算、JSON parsing 和失败映射。
- task definition 必须在组合根代码绑定；配置不能提供任意 Prompt/schema。
- `knowledge_rewrite` 仍须先通过 `QuestionEgressGuard`。
- `knowledge_summary` 仍须收到领域已允许的 evidence safe payload；真实证据受 `SA-GATE-006`。

### 8.5 Provider 请求与响应

请求固定 `POST https://api.deepseek.com/chat/completions`、`Content-Type: application/json`、`Authorization: Bearer <LLM_API_KEY>`。不使用 beta base URL、streaming、prefix/FIM、文件、任意代理地址或调用方提供的 model 参数。

响应共同校验：

- 进入响应上下文后先检查 HTTP status；只有精确 200 才允许读取 body。408/504 直接映射
  `provider_timeout`，其余任意非 200 直接映射 `provider_failure`；错误正文不得读取、解析或记录，
  response 必须在退出上下文时关闭。
- HTTP 200 的媒体类型必须为 JSON，body ≤冻结设置 `max_response_bytes`（默认 262144）。
- 使用流式读取并在累计第 `max_response_bytes + 1` 个 raw byte 时立即关闭响应；不得先调用
  `response.aread()/response.json()` 再检查大小。请求固定 `Accept-Encoding: identity`，
  非 identity Content-Encoding 拒绝。
- `choices` 正好 1 项。
- `finish_reason` 只允许 task 预期的 `tool_calls` 或 `stop`；`length/content_filter/insufficient_system_resource/null` 均失败。
- response `model` 当前必须精确为 `deepseek-v4-pro`；任何别名或新值均失败关闭并需变更评审。
- UTF-8 和 JSON 解析严格拒绝重复 key、非有限 number 与顶层非 object。对 Provider
  top-level、`usage` 新增但未消费的字段允许忽略；`object/model/choices/finish_reason/message`
  及实际消费的 tool/content 字段必须严格类型化，未知枚举失败关闭。模型生成的
  `function.arguments` 和 JSON Output 对象始终 `extra=forbid`。
- reasoning content 不读取、不返回、不持久化。
- usage 仅记录总 token 数值指标，不绑定 user/request 标签，不作为事实。

## 9. 接口与模型契约设计

### 9.1 Provider-neutral Protocol

```python
class StructuredModelGateway(Protocol):
    async def generate(
        self,
        *,
        definition: ModelTaskDefinition[TInput, TOutput],
        input: TInput,
        context: ModelCallContext,
    ) -> ModelTaskResult[TOutput]: ...

class StructuredModelTransport(Protocol):
    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse: ...
```

`ModelTaskResult` 只能是 `success(output)` 或 `failure(ModelProviderFailureKind)`；failure kind 固定为 `input_denied/provider_timeout/provider_failure/invalid_output`。它不携带异常 message、HTTP body、Prompt 或供应商 DTO。

`BoundedStructuredModelGateway` 只依赖 `StructuredModelTransport`。`DeepSeekChatTransport`
在 adapter 内把 `StructuredModelRequest` 投影为私有 `DeepSeekRequest`，完成 canonical
序列化、HTTP 和响应 DTO 校验后，再投影为 `StructuredModelResponse`；公共 gateway、
task definition 和领域代码均不得导入 `model.deepseek.dto`。Provider 响应中的 model、
object、choice index、finish reason 等只用于 adapter 校验，不穿过 transport 端口。

### 9.2 `L2_00_01` Protocol 实现

```python
class DeepSeekCapabilitySelector:
    async def __call__(
        self,
        input: CapabilitySelectionInput,
    ) -> CapabilitySelectionDecision: ...

class DeepSeekAnswerGenerator:
    async def __call__(
        self,
        input: AnswerGenerationInput,
    ) -> AnswerGenerationDecision: ...
```

二者不接收 `Runtime`、scope、JWT、domain result 或整个 state。请求上下文/截止时间由
模型模块的 `ModelContextBindingRuntimeInvoker` 外层装饰器提供：该装饰器实现
`L2_00_01` 的 `AgentRuntimeInvoker` 公共调用边界，顶层组合根先取得
`L2_00_01` 的原始 `AgentRuntimeInvoker`，再用装饰器包裹；装饰器保持完全相同的
`ainvoke(question, scope)` 签名，只从 `scope.context` 投影
requestId/correlationId/deadline 到 `ModelCallContext`，设置模型模块私有
`ContextVar`，委托原 invoker，并在 `finally` reset。`agent-core`、graph wrapper 和原
`AgentRuntimeInvoker` 不导入 model 包也不作任何修改。

`DeepSeekCapabilitySelector/AnswerGenerator` 只调用只读
`ModelCallContextAccessor.require_current()`；缺失上下文时 transport 调用为 0 并返回
`invalid_output`。child task 只在当前结构化调用栈内创建并必须 join/cancel；不得把
ContextVar 用于图状态、跨请求缓存或领域数据。并发测试必须证明两个请求 context 不串扰，
也必须证明装饰器退出后 accessor 失败关闭。

### 9.3 错误映射

| 触发 | `ModelNodeFailureKind` | 重试 | 安全观测 |
|---|---|---:|---|
| 输入闸门 denied/unknown | `input_denied` | 否 | policy reason enum |
| v4 descriptor/catalog ID、保留值、模型安全文本、唯一性或 catalog 自身边界非法 | `invalid_output`，transport=0 | 否 | `catalog_invalid` |
| v4 catalog 合法，但与当前 minimized question 组成的 task envelope 或完整动态请求超界 | `input_denied`，transport=0 | 否 | `request_too_large` |
| connect/read/overall timeout、截止耗尽 | `provider_timeout` | 否 | phase + duration |
| HTTP 408/504 或本地绝对截止、任一 HTTPX timeout | `provider_timeout` | 否 | phase + duration |
| 其他任意非 200 HTTP、2xx≠200、3xx、连接重置/DNS/TLS/协议错误 | `provider_failure` | 否 | status/transport class |
| 空 content、非法 JSON/tool、多个 choices、finish reason 非法 | `invalid_output` | 否 | stable parse reason |
| 响应超界、model 不匹配、grounding 拒绝 | `invalid_output` | 否 | stable validation reason |

Provider response/error body、exception message 和 Prompt 不进入 `ModelNodeFailure`。`401/402` 表示运维/账户问题，仍不得回退其他模型或服务。

## 10. 权限、安全、审计与出域

### 10.1 调用前置矩阵

| 调用 | 用户问题闸门 | 领域 safe payload | 领域 policy | 真实数据门禁 |
|---|---|---|---|---|
| action selection | 必须 allowed | 不适用 | 不适用 | `CR-GATE-003` 控制敏感问题 |
| Knowledge rewrite | 必须 allowed | 不适用 | Knowledge 改写校验 | `CR-GATE-003` |
| final answer | 必须 allowed | 必须存在 | capability grounding policy 必须存在 | `SA-GATE-006` |
| Knowledge summary | 必须 allowed | 必须是允许证据 | Knowledge evidence policy | `SA-GATE-006` |

任何一个前置条件缺失时 Provider 调用为 0。模型不能读取 JWT、角色、业务授权规则、物理索引、下游 URL、完整 domain result 或策略正文。

### 10.2 凭证

- `LLM_API_KEY` 是唯一目标环境键；实现不回退 `DEEPSEEK_API_KEY`、配置文件明文或默认值。
- 仅 `ModelSettings.from_env` 在启动期读取，包装为 `ModelApiKey`；`repr/str` 固定 `<redacted>`。
- 真实 Provider 模式缺失/空白 key 时 Runtime 启动失败；stub 模式不读取 key。
- key 仅在创建 Authorization header 时显式 reveal；不得进入 dataclass equality/hash、异常、metrics 或 health。

### 10.3 最小审计

安全事件仅记录：correlationId、taskId、model 常量、policyVersion、decision、failure kind/reason enum、耗时、input/output byte bucket、token usage bucket。question、Prompt、tools schema、safe payload、answer、subject、JWT 和 API key 均不记录。

## 11. 状态、并发、一致性与资源预算

### 11.1 调用预算

| Task | 默认超时上限 | max output tokens | 最大输入 bytes | 说明 |
|---|---:|---:|---:|---|
| `action_selection` | 8s | 512 | 65536 | descriptor + minimized question |
| `knowledge_rewrite` | 8s | 512 | 16384 | 具体上限可由 Knowledge 收紧 |
| `answer_generation` | 15s | 1024 | 65536 | safe payload + minimized question |
| `knowledge_summary` | 15s | 1536 | 65536 | 具体证据上限由 Knowledge 收紧 |

`knowledge_rewrite` 复用 `AGENT_MODEL_ACTION_TIMEOUT_MS`，`knowledge_summary` 复用
`AGENT_MODEL_ANSWER_TIMEOUT_MS`；Knowledge 的代码绑定 task definition 只能在上述冻结值内
收紧，不能通过领域配置扩大。首期不增加同义超时配置项。

单次调用先冻结：

```text
callDeadline =
  min(nowMonotonic + taskTimeout, requestDeadlineMonotonic - 250ms)
```

`callDeadline <= now` 时不获取 permit、不创建 HTTP 请求并返回 `provider_timeout`。获取
全局并发 permit、连接池等待、连接、写入、DeepSeek keep-alive/推理、流式读取、JSON/输出
校验全部包含在同一个 `asyncio.timeout_at(callDeadline)` 内；不得为各阶段重新获得完整
task timeout。HTTPX connect/pool/read/write timeout 仅作为更小的阶段保护，其中 connect
≤2s、pool≤1s，其余不超过调用剩余量；DeepSeek 返回空行 keep-alive 不能延长绝对截止。

全局模型并发默认 4、允许 1～8；超限不排无界队列，若无法在 `callDeadline` 前获得 permit
则 `provider_timeout`。取得 permit 后任意退出路径均在 `finally` exactly-once 释放；超时或
取消关闭 response stream，迟到 bytes/结果不接纳。

### 11.2 重试与幂等

- Provider、httpx transport 和 wrapper 自动重试次数固定为 0。
- 模型调用有成本且非幂等；同一请求不会因 429/5xx/timeout 自动重发。
- 语义性再次询问只能由 LangGraph 在未来明确设计并受同一总预算控制；本期图不包含该边。
- 不缓存问题、响应或 Prompt，不持久化 usage。

### 11.3 Context 隔离

`ModelCallContext` 在 `AgentRuntimeInvoker.ainvoke` 外层设置，在 `finally` reset。取消后不接受结果；runtime shutdown 的 `CancelledError` 继续向上，不转成普通 Provider failure。任何后台 task 必须在请求结束前 join/cancel，不得持有 context 继续调用。

## 12. 配置、依赖与组合根

### 12.1 配置

| Key/环境 | 默认 | 校验 | 变更 |
|---|---|---|---|
| `AGENT_MODEL_PROVIDER` | `stub`（P3 前） | `stub/deepseek`；真实部署显式 deepseek | 重启 |
| `LLM_API_KEY` | 无 | deepseek 模式必填 | 重启 |
| `AGENT_MODEL_BASE_URL` | 不开放 | 代码常量 `https://api.deepseek.com` | 修改需评审 |
| `AGENT_MODEL_NAME` | 不开放 | 代码常量 `deepseek-v4-pro` | 修改需评审 |
| `AGENT_MODEL_MAX_CONCURRENCY` | 4 | 1～8 | 重启 |
| `AGENT_MODEL_ACTION_TIMEOUT_MS` | 8000 | 1000～15000 | 重启 |
| `AGENT_MODEL_ANSWER_TIMEOUT_MS` | 15000 | 3000～30000 | 重启 |
| `AGENT_MODEL_MAX_REQUEST_BYTES` | 131072 | 65536～262144 | 重启 |
| `AGENT_MODEL_MAX_RESPONSE_BYTES` | 262144 | 16384～524288 | 重启 |

`stub` 是显式本地测试实现，不得在真实链路伪装成 DeepSeek 成功。stub 模式可以在本地对象图
有效时满足 `L2_00_00` 的 Runtime readiness，但 readiness HTTP 契约不得由本文增加字段；
仅启动日志/指标可报告安全枚举 `modelProvider=stub`，验收不得据此声明真实模型已实现。

### 12.2 依赖

已在 `agent-runtime/pyproject.toml` 锁定 `httpx==0.28.1`；不得依赖 OpenAI SDK、LangChain model wrapper 或自动 retry 包作为首期 Provider 必需依赖。使用直接 HTTP 是为了明确 request body、timeout、response size 和错误映射，不是建立自研通用 SDK。

### 12.3 组合根

1. 加载并校验 `ModelSettings`。
2. 仅当 provider=`deepseek` 时读取 `LLM_API_KEY` 并创建一个进程级 `httpx.AsyncClient`：
   `base_url=https://api.deepseek.com`、
   `verify=True`、`trust_env=False`、`follow_redirects=False`、`http2=False`，
   `AsyncHTTPTransport(retries=0)`，连接池上限等于模型并发，默认 Header 固定
   `Accept=application/json`、`Accept-Encoding=identity`；stub 模式不读取 key、不创建
   HTTP client 或 DeepSeek transport。
3. 创建 `QuestionEgressGuard`，并按 provider 创建 `DeepSeekChatTransport` 或纯本地 stub。
4. 创建有限 `ModelTaskDefinition` tuple 并冻结。
5. 创建 grounding policy registry；只有当前启用且可能产生 safe payload 的 capability 均有 policy 时才就绪。
6. 将 `DeepSeekCapabilitySelector`（或同契约本地 stub）、`DeepSeekAnswerGenerator` 及业务组合根提供的显式 `local_action_resolvers` 注入 `RuntimeCompositionRoot.build`；Runtime root 负责构造混合节点，模型 root 不读取或修改 Resolver。
7. 用 `ModelContextBindingRuntimeInvoker` 包裹核心 invoker 后交给 HTTP ingress；Runtime
   lifespan 关闭时必须 `await AsyncClient.aclose()`，并在关闭后拒绝新调用。

组合根可以知道具体 Provider，graph/core/领域流程不得知道。

任务表中的“最大输入 bytes”限制完整 task user payload canonical JSON；v4 action 的 catalog 与
question 属于同一个 envelope，不得分别获得完整配额。该上限不含 system instruction、历史 tools
和 Provider envelope。`ModelTaskDefinition.build_request` 后必须对完整
`DeepSeekRequest` 做 canonical UTF-8 序列化并执行
`AGENT_MODEL_MAX_REQUEST_BYTES=131072` 上限；system instruction 单项≤8192 bytes、tools
总量≤65536 bytes。任何静态 prompt/历史 tool 集在启动校验中已使最坏请求超界则不就绪；
v4 catalog 自身非法/超界按 9.3 的 `invalid_output` 且零调用，合法 catalog 与当前问题组成的
动态 task/full request 超界时 Provider 调用为 0 并返回 `input_denied`。

## 13. 实现落点清单

| 实现编号 | 状态 | 类型 | 路径 | 符号/配置 | 责任 | 设计规则 |
|---|---|---|---|---|---|---|
| `IMPL-MODEL-001` | 已存在（本地切片） | Python contract | `agent-runtime/src/agent_runtime/model/contracts.py` | enums、decisions、task/gateway/transport/grounding Protocol | Provider-neutral 契约 | `DR-MODEL-001/007/009/015` |
| `IMPL-MODEL-002` | 已存在（本地配置） | Python config | `agent-runtime/src/agent_runtime/model/settings.py` | `ModelSettings`、`ModelApiKey` | 配置/凭证/预算；未创建 HTTP client | `DR-MODEL-010/012` |
| `IMPL-MODEL-003` | 已存在 | Python policy | `agent-runtime/src/agent_runtime/model/input_guard.py` | `QuestionEgressGuard.evaluate` | 分类与最小化 | `DR-MODEL-003/004` |
| `IMPL-MODEL-004` | 已存在 | Python policy data | `agent-runtime/src/agent_runtime/model/question_policy.py` | finite detectors、`question-egress-v1` | 代码绑定全局规则 | `DR-MODEL-003/014` |
| `IMPL-MODEL-005` | 已存在（本地切片） | Python gateway | `agent-runtime/src/agent_runtime/model/gateway.py` | `BoundedStructuredModelGateway`、task registry；grounding registry 位于 `agent-runtime/src/agent_runtime/model/grounding.py` | 有界任务与领域接缝 | `DR-MODEL-007/009/010/011` |
| `IMPL-MODEL-006` | 已存在（受控装配；默认未启用） | Python adapter | `agent-runtime/src/agent_runtime/model/deepseek/transport.py` | `DeepSeekChatTransport.complete`、`build_deepseek_http_client` | HTTPS/DTO/error；仅显式 `deepseek` 配置由模型组合根创建 | `DR-MODEL-002/010/011/012/015` |
| `IMPL-MODEL-007` | 已存在（v4 非 live 已验证；v3 来源由 manifest/hash + Git 提交冻结） | Python projection | `agent-runtime/src/agent_runtime/model/deepseek/tools.py` | `project_capability_catalog`、`model-catalog-text-v1` | descriptor 模型安全展示字段→有界 canonical catalog；禁止读取执行 Schema；当前工作树可演进但不得改写 v3 资产/来源认定 | `DR-MODEL-005/016` |
| `IMPL-MODEL-008` | 已存在（v4 已受控装配；默认 stub） | Python node implementation | `agent-runtime/src/agent_runtime/model/deepseek/action_selector.py` | `DeepSeekCapabilitySelector.__call__`、代码绑定 `action-selection-v4` | JSON ID exact decoder→能力 ID 决定；默认 Runtime 无真实调用 | `DR-MODEL-003/005/006/016` |
| `IMPL-MODEL-009` | 已存在（fake transport 验证） | Python node implementation | `agent-runtime/src/agent_runtime/model/deepseek/answer_generator.py` | `DeepSeekAnswerGenerator.__call__` | safe payload 回答；无真实调用 | `DR-MODEL-004/008/009` |
| `IMPL-MODEL-010` | 已存在 | Python validation | `agent-runtime/src/agent_runtime/model/grounding.py` | `GroundingPolicyRegistry.require` | code-bound grounding | `DR-MODEL-007/009` |
| `IMPL-MODEL-011` | 已存在（纯映射） | Python mapping | `agent-runtime/src/agent_runtime/model/deepseek/errors.py` | `map_deepseek_failure` | 有限失败转换；不含 HTTP body/exception | `DR-MODEL-015` |
| `IMPL-MODEL-012` | 已存在（历史 v1/v2） | PoC test/evidence | `agent-runtime/tests/poc/test_deepseek_action_selection_live.py`、`tests/poc/results` | 历史 10 case×3 与 append-only 记录 | v1/v2 均未达标，只作历史证据 | `DR-MODEL-013/014/016` |
| `IMPL-MODEL-013` | 已存在 | Python build | `agent-runtime/pyproject.toml` | `httpx==0.28.1` | Provider 运行依赖 | `DR-MODEL-002` |
| `IMPL-MODEL-014` | 已存在（Runtime wiring 已验证） | composition | `agent-runtime/src/agent_runtime/bootstrap.py` | `LocalModelCompositionRoot`、`LocalModelComponents`、settings、selector、answer generator、policies、client lifecycle | 默认 `stub` 使用显式本地 transport；仅显式 `deepseek` 创建并独占一个 client/transport；不侵入 Core | `DR-MODEL-001/007/012/014` |
| `IMPL-MODEL-015` | 已存在（含关闭接缝） | Python request context/lifecycle | `agent-runtime/src/agent_runtime/model/context.py`、`agent-runtime/src/agent_runtime/api/app.py` | private ContextVar、accessor、`ModelContextBindingRuntimeInvoker.ainvoke/aclose`、Runtime lifespan | 安全元数据绑定、取消传播、幂等关闭及关闭后拒绝新调用；HTTP/OpenAPI 契约不变 | `DR-MODEL-001/010/012` |
| `IMPL-MODEL-016` | 已存在（无 HTTP） | Python Provider DTO/JSON | `agent-runtime/src/agent_runtime/model/deepseek/dto.py`、`json_codec.py` | request/response typed projection、unique-key JSON、严格 UTF-8/大小边界；流式 HTTP 读取仍归 `IMPL-MODEL-006` | 严格 Provider 数据边界 | `DR-MODEL-002/009/015` |
| `IMPL-MODEL-017` | 已存在（PoC 通过） | PoC test | `agent-runtime/tests/poc/test_deepseek_answer_generation_live.py` | 3 个固定 synthetic safe payload×2 次；append-only 通过记录 | 6/6 结构与 deterministic grounding 有效；不单独关闭 `SA-GATE-002` | `DR-MODEL-013/014` |
| `IMPL-MODEL-018` | 已存在（v3 历史失败） | PoC harness/fixture/evidence | `agent-runtime/tests/poc/test_deepseek_action_selection_live.py`、`agent-runtime/tests/poc/fixtures/action_selection_v3.json`、v3 manifest/consumed/result | `action-selection-v3` 绑定 run 已完成 30 次；append-only 结果为 17/30 结构、3/30 预期、0 真实业务调用 | 不覆盖、不补跑、不续跑、不改判；不得接 Runtime | `DR-MODEL-013/014/016` |
| `IMPL-MODEL-019` | 已存在（v4 candidate-01 历史失败） | v4 contract/descriptor metadata/fixture/PoC assets | `agent-runtime/tests/contract/model/test_action_selection.py`、现有 PoC harness/strict Schema、`agent-runtime/tests/poc/fixtures/action_selection_v4.json`、candidate-01 manifest/consumed/result；Employee descriptor 仅删除模型不应见的 wire 名 | JSON ID envelope、10 case×3、catalog/system/实现哈希、one-shot 调用计数和 append-only evidence；candidate-01 已完成30次并失败，旧 fixture/manifest/result/consumed 均只读 | `WP-MODEL-ACTION-V4-LOCAL-01` 非 live 已完成；`WP-MODEL-ACTION-POC-03` 作为失败历史，不得补跑、改判或复用 `GATE-037` | `DR-MODEL-005/013/014/016/017` |
| `IMPL-MODEL-020` | 已存在（corrected v4 live PoC 已通过） | versioned fixture/provenance/manifest/test/evidence assets | `agent-runtime/tests/poc/fixtures/action_selection_v4_2.json`、`agent-runtime/tests/poc/contracts.py`、`agent-runtime/tests/poc/fixtures.py`、`agent-runtime/tests/unit/model/test_deepseek_poc_harness.py`、candidate-02 manifest/consumed 与 `agent-runtime/tests/poc/results/action_selection-20260810T120158644883Z.json`；`IMPL-MODEL-019` 资产未覆盖 | corrected fixture与candidate-01 provenance保持；candidate-02 manifest SHA-256 `9ec90a3f8a874308fb6a0a8c580ea8adae037f39bbf430717dfc6f58d531a494` 已消费且30次完整通过，result/consumed SHA-256分别为`f9d48b4cf4f8427b42deee2ebb23e6c646de0552e4dec929acbad55e253a910b`、`64478b36c68afba51fd4eb69b11dc1c6d31e412f45ddb87fbbe3ab7babf48fba` | `VAL-MODEL-010/011` 已完成；禁止重跑，后继 wiring 已以独立 fake-only 证据关闭 `GATE-020` | `DR-MODEL-013/014/016/017` |
| `IMPL-MODEL-021` | 建议修改 | Python policy/tests | `agent-runtime/src/agent_runtime/model/question_policy.py`、`agent-runtime/tests/unit/model/test_input_guard.py`及直接零调用/历史兼容测试 | `_GENERIC_TRANSACTION_RESULT`、`QUESTION_EGRESS_POLICY_VERSION` | exact通用问题allow、deny优先、公共决定类型不变 | `DR-MODEL-003/004/018` |
| `IMPL-MODEL-022` | 已完成 | Python task/composition/tests | `agent-runtime/src/agent_runtime/model/deepseek/answer_generator_v2.py`；最小修改`agent-runtime/src/agent_runtime/bootstrap.py`；直接契约、组合根及历史兼容测试 | `build_answer_generation_v2_task_definition`、`answer-generation-v2` | 复用v1 DTO/parser，只强化模型可见marker约束并使生产组合根唯一使用v2 | `DR-MODEL-007/009/019` |

### 13.1 边界关键函数签名

| 路径/符号 | 建议签名 | 输入/校验 | 输出/错误 | 副作用/调用方 |
|---|---|---|---|---|
| `QuestionEgressGuard.evaluate` | `def evaluate(self, question: str) -> QuestionEgressDecision` | NFC、长度、控制符、有限类别；纯函数 | 两类均含策略版本；allowed 含最小问题，denied 含有限 reason；不抛原文异常 | 无；selector/answer/Knowledge task |
| `ModelTaskDefinition.build_request` | `def build_request(self, input: TIn) -> StructuredModelRequest` | `type(input) is input_type`，canonical input bytes≤task 上限；definition 来自冻结 registry | 返回冻结 Provider-neutral request；非法/超界为 typed input denial，不含输入正文 | 纯函数；gateway |
| `ModelTaskDefinition.parse_response` | `def parse_response(self, response: StructuredModelResponse) -> TOut` | 仅接收已通过共同 Provider 校验的 response；task-specific exact schema | 返回冻结 typed output；空/额外字段/越界抛无正文 `InvalidModelOutput` | 纯函数；gateway |
| `BoundedStructuredModelGateway.generate` | `async def generate(self, *, definition: ModelTaskDefinition[TIn,TOut], input: TIn, context: ModelCallContext) -> ModelTaskResult[TOut]` | task 必须来自冻结 registry；预算/permit | typed result；不传播供应商异常 | 获取并发 permit，一次 transport |
| `DeepSeekChatTransport.complete` | `async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse` | request 只能由冻结 task definition 构造；adapter 内投影私有 `DeepSeekRequest` 并校验 canonical body≤完整请求上限；固定 URL/model；deadline 为当前 loop 单调值 | 流式≤响应上限、严格 JSON/type/model 校验后返回 Provider-neutral response；typed transport exception | 一个绝对 timeout 内一次 HTTPS；无 retry；stream 在 finally 关闭 |
| `project_capability_catalog` | `def project_capability_catalog(descriptors: tuple[CapabilityDescriptor, ...]) -> FrozenJsonObject` | 非空、≤32；只读取 ID/display/description/aliases；按 `model-catalog-text-v1` 校验并排序/去重/校验保留 ID；执行 Schema 不参与投影 | 精确 `{"capabilities":[...]}` 深冻结 catalog；重复、非法、安全文本或 catalog 自身超界抛无正文 `InvalidCapabilityCatalog`，selector 固定映射 `invalid_output` 且 transport=0 | 纯函数；capability selector/PoC manifest |
| `DeepSeekCapabilitySelector.__call__` | `async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision` | question guard、descriptor/catalog 限制；task=`action-selection-v4`；JSON exact decoder | candidate ID/unsupported/failure；无 arguments，不写 graph state | 至多一次模型调用 |
| `DeepSeekAnswerGenerator.__call__` | `async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision` | question guard、safe payload、policy、大小 | answer/failure；丢弃未验证全文 | 至多一次模型调用 |
| `GroundingPolicyRegistry.require` | `def require(self, capability_id: str) -> AnswerGroundingPolicy` | canonical ID，registry 冻结 | policy；缺失 `MissingGroundingPolicy` 由 generator 转 invalid_output | 无；answer generator |
| `AnswerGroundingPolicy.validate` | `def validate(self, input: GroundingInput) -> GroundingDecision` | 只读 minimized question、safe payload 和已做共同结构校验的候选；不得访问 Provider/JWT/下游 | accepted 或有限拒绝原因；异常/未知原因失败关闭，不能改写候选答案 | 纯函数；answer generator |
| `LocalModelCompositionRoot.build` | `def build(*, settings: ModelSettings, transport: StructuredModelTransport | None = None, grounding_policies: Mapping[str, AnswerGroundingPolicy], ...) -> LocalModelComponents` | `stub` 必须显式传入本地 transport；`deepseek` 禁止调用方注入 transport并由根创建唯一 client；重复 task 启动失败 | 返回 selector、answer generator、context accessor、gateway及私有生命周期所有权 | 组合根唯一装配；默认不读取key/不创建HTTP client |
| `LocalModelComponents.bind_runtime` | `def bind_runtime(self, runtime: AgentRuntimeInvoker) -> ModelContextBindingRuntimeInvoker` | 核心 invoker 已完成能力/Resolver装配 | 返回绑定相同模型组件与生命周期的外层 invoker | HTTP ingress 持有并在 lifespan 关闭 |
| `ModelContextBindingRuntimeInvoker.ainvoke` | `async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome` | 与 delegate 精确同签名；只投影 request/correlation/deadline | 设置私有 context、await delegate、finally reset；保持 delegate outcome/cancel | 每请求绑定一次；HTTP ingress |
| `ModelContextBindingRuntimeInvoker.aclose` | `async def aclose(self) -> None` | 可并发/重复调用；关闭开始后不再接纳新调用 | 幂等等待受管 client 关闭；关闭后 `ainvoke` 固定抛 `model.runtime_closed` | Runtime lifespan；不改变HTTP协议 |
| `ModelCallContextAccessor.require_current` | `def require_current(self) -> ModelCallContext` | 当前 task 必须处于 binding invoker 调用栈 | 返回冻结安全上下文；缺失抛无正文 `MissingModelCallContext` | 只读；两个模型节点/Knowledge task |
| `parse_unique_json_object` | `def parse_unique_json_object(raw: bytes | str, *, max_bytes: int, max_depth: int, max_items: int) -> FrozenJsonObject` | UTF-8、字节、深度、集合、finite number；拒绝重复 key/顶层非 object | 深冻结对象或 `InvalidModelOutput` | 无；Provider/tool/JSON Output parser |
| `map_deepseek_failure` | `def map_deepseek_failure(failure: DeepSeekTransportFailure) -> ModelProviderFailureKind` | `failure` 是 adapter 私有冻结值，仅含有限 category、可空 status/phase；不得含异常对象、message 或 body | timeout/408/504→`provider_timeout`；其他 HTTP/transport→`provider_failure`；parse/schema/model/size→`invalid_output`；未知 category 失败关闭为 `provider_failure` | 纯函数；transport/gateway |
| `ModelSettings.from_env` | `@classmethod def from_env(cls, env: Mapping[str, str]) -> Self` | provider enum、key、预算和常量 | 冻结 settings；非法配置阻止启动 | 只在启动读取 env |

私有 JSON parsing、header 构造和字符串规范化函数可由实现决定，但不得改变上述输入、失败、重试、出域和日志不变量。

### 13.2 Provider DTO 精确边界

`DeepSeekRequest` 由 transport 内部 frozen DTO 表示，字段全集固定为：

| 字段 | 值/类型 | 约束 |
|---|---|---|
| `model` | string | 精确 `deepseek-v4-pro` |
| `messages` | tuple | 正好一条 system 和一条 user；content 非空；user content 是 canonical JSON |
| `thinking` | object | 精确 `{"type":"disabled"}` |
| `stream` | bool | false |
| `temperature` | number | 0 |
| `max_tokens` | int | 来自冻结 task definition |
| `tools` | tuple/absent | Provider-neutral v4 request 固定空 tuple，DeepSeek wire 必须省略该 key；仅历史 v1～v3 请求使用 1～33 个有限 function tool |
| `tool_choice` | string/absent | v4 DeepSeek wire 必须省略该 key；历史 tools 存在时精确 `required` |
| `response_format` | object/null | v4 action selection 与其他 JSON task 精确 `{"type":"json_object"}` |

禁止 `user/user_id`、调用方 model/base URL、proxy、stream options、reasoning effort、
任意 stop、额外 headers 或未列字段。上述 DTO 由 `DeepSeekChatTransport` 从
`StructuredModelRequest` 内部投影，绝不作为 transport 入参或返回类型。`DeepSeekResponse` 只投影
`object/model/choices[0].index/finish_reason/message.content/message.tool_calls/usage.total_tokens`；
`object` 必须为 `chat.completion`、choice index 必须为 0。未消费的安全新增 top-level/usage
字段可忽略但不得进入其他层，所有消费字段按 8.5 严格校验；随后只构造 7.3 的
`StructuredModelResponse`。

## 14. 测试与验证设计

### 14.1 测试定义

| 测试编号 | 设计规则 | 层级 | 建议路径 | 核心断言 | 失败信号 |
|---|---|---|---|---|---|
| `TEST-MODEL-001` | `DR-MODEL-001/002` | Architecture/Unit | `agent-runtime/tests/architecture/test_model_dependencies.py` | core/graph/能力/公共 gateway 无 DeepSeek/httpx DTO 依赖；transport 端口只收发 neutral DTO | 供应商泄漏 |
| `TEST-MODEL-002` | `DR-MODEL-003` | Unit | `agent-runtime/tests/unit/model/test_input_guard.py` | 每个类别、边界和 NFC 行为确定；两类决定策略版本相同；denied 不保留原文且访问 minimized question 失败 | 敏感样例 allowed、拒绝决定缺策略版本或携带原文 |
| `TEST-MODEL-003` | `DR-MODEL-004` | Unit | `agent-runtime/tests/unit/model/test_zero_call.py` | question denied/unknown 时 transport spy=0 | 先调用后拒绝 |
| `TEST-MODEL-004` | `DR-MODEL-005/006/016` | Contract | `agent-runtime/tests/contract/model/test_action_selection.py` | descriptors 输入置换后仍按 canonical ID 形成稳定 catalog；catalog hash 仅覆盖 `capabilities`，完整 envelope 统一计数；模型安全文本拒绝 `employee_identifier` 等 wire 名；Provider body 省略 `tools/tool_choice` 且含 JSON Output；结构精确单字段合法 ID→中立决定，JSON whitespace 可接受，空/未知/额外/重复字段、tool call、prose→invalid | 执行 Schema/业务参数进入请求、catalog/hash/预算漂移、wire 有多种编码、宽松解析，或模型输出直接成为 ActionCandidate |
| `TEST-MODEL-005` | `DR-MODEL-008` | Unit | `agent-runtime/tests/unit/model/test_answer_preconditions.py` | 缺/空/超界 safe payload、缺 policy、question denied 均零调用 | domain result 或拒绝载荷外发 |
| `TEST-MODEL-006` | `DR-MODEL-007/009` | Contract | `agent-runtime/tests/contract/model/test_grounded_answer.py` | fact ID 子集、unsupported 为空、领域 policy 通过才接纳 | 无依据实体/数字被返回 |
| `TEST-MODEL-007` | `DR-MODEL-015` | Unit | `agent-runtime/tests/unit/model/test_deepseek_error_mapping.py` | 全 HTTP/transport/parse/finish reason 到固定 kind；无正文 | 错误映射为 no_result 或泄露 |
| `TEST-MODEL-008` | `DR-MODEL-010/011` | Async Unit | `agent-runtime/tests/unit/model/test_budget_concurrency.py`、`test_context.py` | 较小 deadline、有界 permit/等待、零 retry、取消不接纳晚到结果、请求上下文不串扰 | 超预算、多次调用或 context 泄漏 |
| `TEST-MODEL-009` | `DR-MODEL-012` | Unit/Log | `agent-runtime/tests/unit/model/test_credentials.py` | key 缺失启动失败；stub 不读取 key；repr/配置无 key | secret 出现在可观察输出 |
| `TEST-MODEL-010` | `DR-MODEL-007` | Contract | `agent-runtime/tests/contract/model/test_code_bound_tasks.py` | 未注册 task/prompt/schema/config class 均不可调用 | 任意 task 被执行 |
| `TEST-MODEL-011` | `DR-MODEL-013/014` | Opt-in PoC | 已存在：`agent-runtime/tests/poc/test_deepseek_action_selection_live.py` | 仅合成非敏感 descriptors/questions；记录结构与语义指标 | 任一真实/敏感数据进入 PoC |
| `TEST-MODEL-012` | `DR-MODEL-013/014` | Opt-in PoC | 已存在：`agent-runtime/tests/poc/test_deepseek_answer_generation_live.py` | 3 组合成 safe payload 各 2 次；严格 JSON 与 grounding 历史证据满足 14.4 第 8 项 | 未验证候选公开或真实数据进入 PoC |
| `TEST-MODEL-013` | `DR-MODEL-013/016` | Contract/History | 已存在：v3 manifest/consumed/result strict Schema 与校验测试；增加只读 provenance 审计 | v3 绑定 run 恰好 30 次且 conclusion=failed；17/30 结构、3/30 预期、授权已消费；固定三类 artifact hash，并确认 manifest 所列源码 bytes 可由 Git 提交 `f6274b2b21420d2b2b3d0f4b693978fa4526ef57` 重建；不要求当前工作树等于 v3 hash | 覆盖、补跑、续跑、改判 v3、复用 `GATE-035`，或把 v4 工作树变化误报为 v3 evidence 被修改 |
| `TEST-MODEL-014` | `DR-MODEL-005/006/016/017` | Contract/Architecture | 建议修改现有 `test_action_selection.py`、`test_model_dependencies.py`、PoC manifest/结果严格校验测试；建议新增 v4 fixture | task version=v4；独立 v4 fixture 使用实际三 ID且问题语义与 descriptor 一致；request/evidence 无业务参数；Provider wire 唯一；catalog/system/fixture/实现哈希、30 个唯一 case/run 和 one-shot 授权消费严格；实现满足 `CapabilitySelectionNode` 且不构造 `ActionCandidate` | v3 tool 契约残留、超域/歧义 fixture、模型层导入 Resolver/业务参数、证据漂移或覆盖历史 evidence |
| `TEST-MODEL-015` | `DR-MODEL-013/014/016/017` | Contract/History | 已修改 `agent-runtime/tests/unit/model/test_deepseek_poc_harness.py`、PoC contracts/fixture loader；已新增 `action_selection_v4_2.json`、candidate-02 manifest/consumed/result | candidate-01 manifest/result/consumed 哈希与失败指标不可变，manifest 所列实现 bytes 可从 commit `cd8007e58bbeca902bec722eb98bbfbf8fe7c55f` 重建；corrected fixture 精确保持3个 Knowledge、3个 Employee、3个 Transaction 正向和1个近域 unsupported；candidate-02执行前验证未消费且HTTP=0，执行后验证manifest仍匹配冻结输入、consumed/result哈希不可变、30个唯一记录及全部通过指标 | 追溯改写历史证据、把字段帮助当执行动作、正向分布漂移、current/historical 文件集合混用、重复消费 candidate-02、结果指标或数据最小化回归 |
| `TEST-MODEL-016` | `DR-MODEL-001/007/010/012/015` | Integration/Lifecycle | 已新增 `agent-runtime/tests/integration/model/test_runtime_composition.py`，已修改 `tests/integration/test_health_and_startup.py`、`tests/unit/model/test_context.py` | fake client仅构建一次；action与grounded answer共享受管transport和请求上下文；503固定映射；并发context不串扰、取消传播；lifespan幂等关闭且关闭后拒绝新调用；默认stub不变 | 创建多个非受管client、遗漏answer装配、context串扰、关闭后继续调用、异常泄露或真实outbound |
| `TEST-MODEL-017` | `DR-MODEL-003/004/014` | Security Contract/Integration | `agent-runtime/tests/contract/business/test_sensitive_question_scenarios.py`、`tests/integration/knowledge/test_question_egress.py`、`test_evidence_stage.py` | 业务 fixture 精确命中有限类别；Employee 姓名/Transaction 金额 unknown 失败关闭；selector/answer/rewrite/summary fake transport 为0；公开 Knowledge 只以最小化问题到 fake gateway | fixture 未消费、敏感/unknown 问题进入 transport、Knowledge denied 状态未传到 Evidence，或 generic guard 被误当业务授权 |
| `TEST-MODEL-018` | `DR-MODEL-003/004/018` | Unit/Contract/History | 建议修改`tests/unit/model/test_input_guard.py`并增加Transaction candidate直接测试；必要时把已消费候选的prepared测试改为从其冻结提交验证资产 | 三个有限通用句式allowed且返回`question-egress-v2`最小问题；具体交易号/金额/账户/凭证/注入/额外文本均denied且transport=0；Employee/Knowledge既有allow和全部deny保持；历史manifest/evidence字节与指标不变 | 模糊放行、deny优先级倒置、策略升版导致历史测试错误要求当前源码等于旧hash |
| `TEST-MODEL-019` | 已新增并通过；`DR-MODEL-007/009/019` | Contract/Composition/History | `tests/contract/model/test_answer_generation_v2.py`及Runtime组合根、Employee/Transaction/Knowledge历史candidate兼容测试 | task version=v2；system instruction精确要求行内marker与ID集合一致；同一fake response经v1 parser得到相同`CandidateAnswer`；带marker候选通过Business grounding，v1式无marker候选被既有validator拒绝；默认stub不变；answer v1源码SHA和历史evidence字节不变；旧candidate按冻结提交而非当前bootstrap验证 | 20项核心定向、67项完整相关定向及全量non-live回归通过；未放宽validator、改变公共DTO/parser或复用旧candidate |

### 14.1.1 共享 Fixture 与动作要求

| 测试组 | Fixture/setup | 执行动作 | 必须断言 |
|---|---|---|---|
| input/zero-call | 含复合 allow+deny、Unicode 变体、凭证、注入指令的表驱动问题；计数 transport | 分别调用 selector、answer、rewrite guard | 任一 deny 命中优先；denied decision 不含原文；transport=0 |
| HTTP/budget | `httpx.MockTransport`/本地 chunked ASGI server、可控 loop clock、阻塞 semaphore、持续空行 keep-alive、边界±1 body | 通过真实 gateway/transport 调用一次 | 同一绝对截止覆盖 permit 和 stream；第 max+1 byte 中止；stream/client/permit 全释放；HTTP 次数≤1 |
| context | 两个并发 scope 使用不同 request/correlation/deadline，另有无 binder 调用和取消路径 | 经 `ModelContextBindingRuntimeInvoker` 进入 selector/answer | 两请求不串扰；退出后 accessor 缺失；取消传播；core invoker 无 model import |
| Provider contract | 固定 request capture；重复 key、未知 enum、额外 model-output 字段、2xx≠200/3xx/任意 4xx/5xx、压缩响应 | 构造 request、流式解析并映射 | v4 body 必须省略 `tools/tool_choice` 且 `response_format` 精确；model 只接受固定值；生成对象 extra 拒绝；Provider 新 top-level 仅忽略；错误无正文 |
| grounding | 代码绑定 policy、含未支持数字/实体/关系/coverage 的候选与 safe payload | `DeepSeekAnswerGenerator` 共同校验后调用 policy | 只有 policy accepted 返回 answer；policy 不得转换文本；拒绝时丢弃全文 |
| secret/lifecycle | sentinel key、代理环境变量、日志 capture、关闭中的 client | 构建/调用/关闭组合根 | `trust_env=False`，无代理请求；key 不出现；只创建一个 client；shutdown aclose 后拒绝调用 |
| live PoC | 版本化 corrected v4 action fixture 的 10 个语义有效、非敏感合成问题×3，预期只取 `knowledge.query/employee.detail/transaction.search/agent_unsupported`；answer 继续引用独立 3×2 历史通过证据 | 先校验冻结 candidate-02 manifest，再仅以绑定该 manifest 的新 `GATE-038` 单次授权执行；首个 outbound 后授权即耗尽，不得补跑、续跑、复用任何历史授权或覆盖旧结果 | 哈希一致且恰好 30 个一一对应的终态记录时分别计算 JSON 结构/ID 一致/逐 case 指标；任一 tool call、业务参数字段、真实数据、少执行、重复记录或失败均不关闭门禁 |

### 14.2 负向场景来源

- Knowledge：否定、时间条件、法律适用范围被改写或回答改变。
- Employee：身份证、电话、账户、员工编号、指令性自由文本。
- Transaction：交易号、账户、金额组合、写入/聚合诱导。
- 通用：JWT/API key、Prompt injection、未知/额外/重复 JSON 字段、tool call、JSON 外 prose、超界 JSON、空 content、`finish_reason=length`。

`L2_02_00` 负责把业务类别实例化为稳定 fixtures；本文负责这些 fixtures 到 question guard/Provider spy 的共同断言。

### 14.3 selection-only v3 历史失败证据

1. `GATE-035` 绑定 run ID `action-selection-v3-20260807-candidate-01` 与 manifest SHA-256 `fdcbe2a29ab6729e412ba58d7b85c4b7baf68e83ebad4e23da66a7d8008ee635`；首个 outbound 后授权已耗尽。
2. 该 run 恰好完成 30/30 次请求，结果为结构有效 17/30、预期匹配 3/30、arguments 精确空 17/30；仅 `unsupported_traffic_law` 达到 3/3，真实业务调用为 0，结论为 `failed`。
3. append-only 结果为 `agent-runtime/tests/poc/results/action_selection-20260807T133851985471Z.json`，SHA-256 `1947D17872FDBA8FF9DEFEFC3E2D0F282CB1552FFCFA2D491D67C7EF3C360E0A`；消费标记 SHA-256 `D60298139EBD2D3FA1E8EE53D823AAAA410812C5EA47A97117CD670B8FEB98E3`。
4. manifest 所列实现文件当前 hash 与历史值一致，且完整来源已提交为 Git commit `f6274b2b21420d2b2b3d0f4b693978fa4526ef57`。旧 manifest 不增加 `source_commit` 字段，避免破坏其 SHA；该提交引用只作为外部 provenance 补充。v4 可以修改当前工作树，但历史审计必须从该 commit 读取源码并与 manifest hash 对照，不能拿当前文件变化要求改写旧 manifest/result/consumed。
5. v3 不能关闭 `GATE-020/SA-GATE-002`，不得补跑、续跑、复用授权、选择性剔除失败 case、降低分母或改判为通过；其冻结证据只用于失败事实和原因追踪。

### 14.4 selection-only v4 JSON ID PoC 历史与门槛

#### 14.4.1 candidate-01 不可变失败证据

1. `GATE-037` 绑定 run ID `action-selection-v4-20260807-candidate-01` 与 manifest SHA-256 `af290a91cc58a989ff700a1a95685f8d1efeeea0f17828e36b12e28de08adfbe`；该一次性入口已在首次 outbound 后耗尽。
2. 该 run 恰好完成30/30次请求，结构有效30/30、预期聚合27/30、arguments 为空30/30、真实业务调用0；但 `transaction_fields` 为0/3，违反每 case 至少2/3，结论必须保持 `failed`。
3. append-only result 为 `agent-runtime/tests/poc/results/action_selection-20260810T100832615726Z.json`，SHA-256 `462f7be1140bbd2edee56df97faaacf87422d6a002080edcbeef796e7d1dcdd0`；consumed marker SHA-256 `b394ca5239af5cbe17181581763983b7ae824f62fd16fff845b8970f2f45e10c`。
4. candidate-01 manifest 所列实现文件由 Git commit `cd8007e58bbeca902bec722eb98bbfbf8fe7c55f` 提供历史 bytes；后续 fixture/Harness 演进必须从该提交重建并对照 manifest hash，不得要求当前工作树回退，也不得修改旧 manifest/result/consumed。
5. “交易记录允许哪些字段？”请求字段字典/接口帮助，超出 `transaction.search` 的执行查询语义；这解释了 fixture 预期错误，但不改变 candidate-01 的历史 gold 或失败结论。

#### 14.4.2 corrected candidate-02 门槛

新的付费 PoC 仅可在 corrected 非 live 资产验证通过且用户另行以新 run ID/manifest 打开 `GATE-038` 后执行：

1. 使用独立版本化 `action-selection-v4` corrected fixture：实际 ID `knowledge.query`、`employee.detail`、`transaction.search` 与 `agent_unsupported`，共10个合成、非敏感、无真实标识/业务/知识数据的问题；每题独立3次，共恰好30次。固定保持3个 Knowledge、3个 Employee、3个 Transaction 正向和1个近域 unsupported。
2. 旧 `transaction_fields` 问题“交易记录允许哪些字段？”改名为 `unsupported_transaction_fields` 并预期 `agent_unsupported`；以 `transaction_query_items`/“查看交易记录支持哪些查询项？”替换旧的远域交通法规 unsupported case，预期 `transaction.search`。不得修改 descriptor、Prompt、输入闸门、decoder 或门槛来适配旧 gold。
3. 首次 outbound 前产生新冻结 run manifest，至少包含唯一 run ID、UTC、model、task version、授权引用、`authorized_call_limit=30`、按序 case manifest SHA-256、system instruction SHA-256、模型可见 canonical `{"capabilities":[...]}` SHA-256、相关 v4 实现文件集合及内容 SHA-256；实现文件集合必须覆盖 catalog/text policy、selector/exact decoder、DeepSeek request projection/DTO、JSON codec 和 v4 Harness/Schema。哈希使用 canonical UTF-8 JSON；question、API key、完整 Prompt envelope 和 Provider response 不进入 catalog hash。任一哈希不一致时 HTTP=0。
4. `GATE-038` 是新的候选一次性入口：首个 outbound 后授权即耗尽。通过结果必须有恰好30个 outbound 和30个按 `(case_id,repetition=1..3)` 唯一对应的终态记录；提前终止、少执行、重复/缺失记录或新运行均须新增门禁、run 和授权，不得补跑、续跑、重试或复用任何历史授权。
5. 结构有效率必须100%：每次必须 `finish_reason=stop`、tool calls 缺失/空，并只允许结构精确的 JSON 单对象单字段 `capability_id`，值属于冻结目录或 `agent_unsupported`；JSON 根前后标准 whitespace 可接受但不做 trim/case-fold/alias 映射，tool call、空 content、额外/重复字段、业务参数、raw response 或 prose 均判失败。
6. 预期 capability ID/unsupported 聚合一致率至少90%（≥27/30），且每个 case 至少2/3；任一 case 低于单项下限或聚合未达标均不能进入 Runtime wiring。
7. PoC 只验证 `CapabilitySelectionDecision`，不得进入混合节点、Core validator 或 handler；模型生成 arguments、未注册动作、动态 URL/DSL/类名和真实系统实际执行次数均为0。
8. 结果只记录模型、时间、`action-selection-v4`、manifest/hash、case ID、repetition、有限 decision/validity/failure/耗时，不持久化完整问题、raw Provider 内容或任何业务执行参数；fixture、manifest/result/consumed 全部 append-only。
9. answer generation 不重跑，继续引用2026-08-03的3 case×2通过证据；JSON 结构与 deterministic grounding 证据须在 Runtime wiring 前重新通过非 live 回归。

该门槛只证明 selection-only 能力 ID 选择可行性；本地 Resolver、Core 执行、知识/业务效果、权限或真实数据出域由其他证据证明。

### 14.5 验证定义

| 验证编号 | 工作目录/前置 | 命令/步骤 | 预期 | 当前状态 |
|---|---|---|---|---|
| `VAL-MODEL-001` | `D:\codex` | `python C:\Users\zhoud\.agents\skills\detailed-design-document\scripts\validate_detailed_design.py --file D:\codex\docs\design\L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md --root D:\codex --strict` | 0 errors、0 warnings；不替代评审/PoC | 已执行：0 errors、0 warnings（2026-08-01，v0.5） |
| `VAL-MODEL-002` | `agent-runtime` 隔离环境 | `python -m pytest tests/unit/model -q` | input、DTO/失败、预算、context、secret、transport/harness 测试通过 | 2026-08-06 `action-selection-v2` 直接契约/Harness 11 passed、1 live skipped；扩展 model/架构集合 125 passed |
| `VAL-MODEL-003` | `agent-runtime` 隔离环境 | `python -m pytest tests/contract/model tests/architecture/test_model_dependencies.py -q` | 节点/领域/依赖契约通过 | 2026-08-06 已由 125 项扩展 model/架构验证覆盖；Runtime wiring 条件未成立，组合根/生命周期实现与相应验证未执行 |
| `VAL-MODEL-004` | 当前环境/实现测试 | 检查 `LLM_API_KEY` 存在性但不输出值；运行 secret/config tests | 环境存在且无泄露 | 2026-08-03 凭证存在、`/models`=200 且模型可用；117 个相关源码/fixture/result 文件密钥扫描为 0；环境级 `pip check` 因既存安装版本偏差未通过，不作为本工作包通过证据 |
| `VAL-MODEL-005` | `CR-GATE-002` 已授权 PoC harness 代码，且每次运行另有明确付费调用授权；仅非敏感 case | 历史 action 与 answer 分别使用独立 opt-in 测试；不得以一次授权追加或补跑 | 历史 action 30 次 + answer 6 次固定门槛 | 2026-08-06 只执行获授权的 v2 action 测试一次：30/30 完成，23/30 结构有效、23/30 预期匹配；`transaction_conditions=0/3`、`transaction_fields=2/3`、`transaction_filters=0/3`，结果 `failed`。append-only 证据 `tests/poc/results/action_selection-20260806T143608408097Z.json`，SHA-256 `CEA40317FD29280AD53AB45D613C290C35C1039039B1B07D9F4D080AC45E658E`；answer 未重跑，继续引用 2026-08-03 的 6/6 证据；综合未通过 |
| `VAL-MODEL-006` | `D:\codex\agent-runtime`；`IMPL-MODEL-007/008/018` v3 非 live 完成 | `python -m pytest tests/contract/model/test_action_selection.py tests/architecture/test_model_dependencies.py tests/unit/model/test_deepseek_poc_harness.py -q` | v3 空 Schema、ID-only、actual descriptor、manifest/hash、one-shot 预算、append-only 与依赖边界通过 | 2026-08-07 live 前已执行：23 passed；完整回归 534 passed/6 skipped、strict mypy 238 files 通过。该结果只证明 v3 harness/边界，不证明 live 可用；live 后测试中对“候选 manifest 未消费”的旧前置断言不应继续作为当前通过条件 |
| `VAL-MODEL-007` | `VAL-MODEL-006` 历史前置和一次性 `GATE-035` | 已按绑定 manifest 完成 v3 10 case×3；核对 result/consumed hash、30 个唯一记录、0 retry 和真实调用为 0 | 历史阈值为结构30/30、预期≥27/30、每 case≥2/3 | 2026-08-07 已执行且失败：30/30 完成，结构17/30、预期3/30、arguments空17/30，仅 unsupported 3/3；result SHA-256 `1947D17872FDBA8FF9DEFEFC3E2D0F282CB1552FFCFA2D491D67C7EF3C360E0A`，consumed SHA-256 `D60298139EBD2D3FA1E8EE53D823AAAA410812C5EA47A97117CD670B8FEB98E3`；`GATE-035` 已消费但未通过 |
| `VAL-MODEL-008` | `GATE-036` 关闭且 `WP-MODEL-ACTION-V4-LOCAL-01` 获代码授权 | `python -m pytest tests/contract/model/test_action_selection.py tests/architecture/test_model_dependencies.py tests/unit/model/test_deepseek_poc_harness.py -q`；完整相关回归与 strict mypy | v4 catalog/envelope/hash 稳定、模型安全文本与执行 Schema 零可达、Provider wire 唯一、JSON exact decoder、语义有效 fixture、新 manifest/hash/one-shot 通过；v3 artifact hash 和来源 commit 可核且不依赖当前工作树 bytes | 2026-08-07 已执行：精确验证 45 passed；补充输入闸门/零调用/Provider 契约定向集合 88 passed；完整 Runtime 回归 520 passed/4 live skipped；strict mypy 239 files、compileall、manifest 重验和 diff check 通过。候选 manifest SHA-256 `af290a91cc58a989ff700a1a95685f8d1efeeea0f17828e36b12e28de08adfbe`，未消费 |
| `VAL-MODEL-009` | `VAL-MODEL-008` 通过且项目维护者以 candidate-01 manifest 单独打开 `P3_00 GATE-037` | 已校验 manifest 后固定 v4 10 case×3 一次性执行；0 retry、不得补跑/续跑；核对30个唯一记录与 evidence hash | exact JSON 结构30/30、预期≥27/30、每 case≥2/3，tool call/业务参数/真实系统调用为0；授权仅消费一次 | 2026-08-10 已执行且失败：结构30/30、预期27/30、arguments空30/30、真实业务调用0，但 `transaction_fields=0/3`；result/consumed SHA-256 分别为 `462f7be1140bbd2edee56df97faaacf87422d6a002080edcbeef796e7d1dcdd0`、`b394ca5239af5cbe17181581763983b7ae824f62fd16fff845b8970f2f45e10c`；`GATE-037` 已消费但未通过 |
| `VAL-MODEL-010` | 本文 corrected fixture 修订通过聚焦评审；不得读取 `LLM_API_KEY` | 新增 versioned corrected fixture；从 commit `cd8007e58bbeca902bec722eb98bbfbf8fe7c55f` 重建 candidate-01 provenance；生成 candidate-02 manifest；执行 Schema/hash/分层/输入闸门/未消费/零调用测试 | 历史资产不变；corrected 3/3/3/1 分布和语义通过；candidate-02 manifest 自重算一致、无 consumed/result、HTTP=0 | 2026-08-10 已完成：精确46 passed；模型相关161 passed；全量564 passed/6 live skipped；strict mypy 239 files、compileall、manifest自重算与代码对照设计复核通过。candidate-02 manifest SHA-256 `9ec90a3f8a874308fb6a0a8c580ea8adae037f39bbf430717dfc6f58d531a494`，未消费；未读取 `LLM_API_KEY`、未产生真实 outbound |
| `VAL-MODEL-011` | `VAL-MODEL-010` 通过且项目维护者以 candidate-02 run ID/manifest 单独打开 `P3_00 GATE-038`；`LLM_API_KEY` 可用 | 固定 corrected 10 case×3 一次性执行；0 retry、不得补跑/续跑；严格校验30个唯一记录与新 evidence hash | exact JSON 结构30/30、预期≥27/30、每 case≥2/3，tool call/业务参数/真实系统调用为0；授权仅消费一次 | 2026-08-10 已执行并通过：30/30完成、结构30/30、预期30/30、逐case均3/3、arguments空30/30、真实业务执行0；result SHA-256 `f9d48b4cf4f8427b42deee2ebb23e6c646de0552e4dec929acbad55e253a910b`，consumed SHA-256 `64478b36c68afba51fd4eb69b11dc1c6d31e412f45ddb87fbbe3ab7babf48fba`；`GATE-038` Closed，禁止重跑 |
| `VAL-MODEL-012` | `GATE-038` 已关闭且项目维护者授权 `WP-MODEL-RUNTIME-01`；所有live开关显式为0 | 模型定向 `pytest`；全量非live `pytest -q`；`python -m mypy src tests --strict`；`python -m compileall -q src tests`；代码对照设计复核 | action/answer/context/client生命周期与失败映射通过；默认stub；0真实调用；无公共契约变化；无未关闭blocker/high/medium | 2026-08-12 已执行：模型定向168 passed；全量570 passed/6 live skipped；strict mypy 241 files、compileall、diff check通过；代码复核补齐answer组合根与client分配前失败证据后无遗留。`GATE-020/SA-GATE-002`按Runtime切片关闭，目标环境deepseek与真实数据出域未启用 |
| `VAL-MODEL-013` | `D:\codex\agent-runtime`；全部 live opt-in 显式为0 | `python -m pytest tests/unit/model tests/contract/model tests/architecture/test_model_dependencies.py tests/contract/business/test_sensitive_question_scenarios.py tests/integration/knowledge/test_question_egress.py tests/integration/knowledge/test_evidence_stage.py -q`；全量 `pytest -q`；strict mypy；compileall；代码对照设计复核 | 分类/最小化、业务/Knowledge fixture、denied/unknown 零 transport、generic 仅输入允许及全量非 live 回归通过；无生产策略/公共契约变化 | 2026-08-12 已执行：172 passed；全量578 passed/6 live skipped；strict mypy 243 files、compileall通过；两轮复核修正 fixture 分类、测试耦合/类型与域场景覆盖后无遗留 blocker/high/medium；未读取key、未产生真实 outbound |
| `VAL-MODEL-014` | `D:\codex\agent-runtime`；全部live开关为0 | Transaction通用问题定向、全部input guard/零调用、历史manifest重建、Transaction/Business相关回归、strict mypy、compileall与代码对照设计复核 | v2仅扩大有限通用句式；敏感/unknown零调用、旧域行为和历史证据均保持 | 实施后记录；未通过前不得准备或执行`GATE-026` live |
| `VAL-MODEL-015` | `D:\codex\agent-runtime`；全部live开关为0且未读取`LLM_API_KEY` | v2精确契约、grounding正反例、组合根唯一注册、default stub、Employee/Transaction/Knowledge历史SHA、相关回归、strict mypy、compileall与代码对照设计复核 | 20项核心定向、67项完整相关定向、全量non-live 1024 passed/23 skipped/1既有历史deselect；strict mypy 354 files、compileall通过；公共契约/validator/v1/history无变化，真实outbound=0 | 通过；关闭本地`GATE-053`，不关闭任何业务live/完成门禁 |

## 15. 发布、迁移与回滚

- 模型模块为新增 Python 代码，无数据迁移。
- P3 默认 `AGENT_MODEL_PROVIDER=stub`，只验证模型无关图和本地契约；不得声称真实 DeepSeek 完成。
- `SA-GATE-002` 已按 Runtime 实现切片关闭，但目标环境切换为 `deepseek` 仍需独立运行动作授权，并须在 `CR-GATE-003/SA-GATE-006` 及对应领域出域门禁满足后重启形成新冻结快照。
- 回滚优先切回 stub/禁用模型相关能力并重启；对外必须返回明确模型不可用/出域拒绝，不得伪造回答。
- Provider request/response 契约破坏性变化需同步 transport、所有 task adapter 和测试；不能用宽松 JSON parser 临时兼容。
- 不保存模型响应，因此回滚无数据补偿；在途请求失败且不重放。

## 16. 风险、待确认事项与门禁

### 16.1 风险

| 编号 | 类型 | 风险/证据缺口 | 触发 | 影响 | 控制 | 阻塞 |
|---|---|---|---|---|---|---|
| `RISK-MODEL-001` | 可行性/评估语义 | v1～v4 candidate-01均未满足各自门槛；corrected candidate-02已30/30通过，但只覆盖冻结的10个合成问题 | Provider、模型版本、catalog或fixture后续漂移 | ID误选、非法结构或以过期证据启用目标环境 | 全部历史与candidate-02证据append-only；当前wiring持续执行非live契约；任一Provider/model/catalog变化重新设计新门禁和新run，不复用`GATE-038` | 项目维护者/模型提供方 |
| `RISK-MODEL-002` | 输入分类 | 有限规则漏识别敏感文本 | 复杂业务问题 | 问题泄露 | unknown 默认拒绝、业务 fixtures、零调用 | `CR-GATE-003` |
| `RISK-MODEL-003` | 事实 | 模型虚构但引用合法 fact ID | 回答生成 | 错误事实 | 领域 grounding policy；无法验证则丢弃 | `SA-GATE-006` |
| `RISK-MODEL-004` | 外部变更 | DeepSeek API/model 行为变化 | 模型升级 | 解析/质量漂移 | 固定 model/task version、contract test/PoC | 模型升级时 |
| `RISK-MODEL-005` | 成本/延迟 | 大 payload 或 retry 放大 | 多阶段 Knowledge | 超时/成本 | 预算、零 retry、并发 4 | 不阻塞设计 |
| `RISK-MODEL-006` | context | `ContextVar` 未 reset 或后台 task 泄漏 | 并发/取消 | 请求串扰 | finally reset、并发/取消测试、Core 无 model import 架构测试 | 本地切片已验证；真实 Runtime 装配仍由 `WP-MODEL-RUNTIME-01` 回归 |
| `RISK-MODEL-007` | 领域依赖 | Grounding policy 尚由后续 L2 提供 | 启用真实 capability | 无法安全回答 | policy 缺失启动/调用失败关闭 | 对应能力真实模型 |
| `RISK-MODEL-008` | 输入策略扩大 | Transaction通用说明正则被改成包含匹配、接受额外子句或未先执行deny检测 | 问题含具体交易值、账户、凭证或注入文本 | 敏感问题随真实结果共同出域 | exact fullmatch、deny优先、策略升版、零调用负向矩阵和历史manifest兼容测试 | `GATE-026/SA-GATE-006` |
| `RISK-MODEL-009` | 模型输出约束漂移 | system instruction示例未展示validator要求的行内marker，或task升级后旧candidate仍按current source执行 | 模型持续返回结构合法但grounding必拒绝的答案，或冻结证据与实际代码身份不一致 | 付费调用全部失效、错误关闭门禁 | 独立v2 task、marker/ID契约测试、组合根唯一注册、v1/history精确hash、领域新candidate重新冻结 | `GATE-053/054/055` |

### 16.2 阶段门禁

| 门禁 ID | 类型 | 阶段/模块切片 | 控制动作 | 关闭条件 | 状态 | 未关闭允许/禁止 |
|---|---|---|---|---|---|---|
| `CR-GATE-001` | design_decomposition | P2 / `L2_00_02` 设计 | 编写本文 | L1_00 已评审 | Closed | 允许文档，不授权代码 |
| `CR-GATE-002` | slice_implementation | P3 / `WP-MODEL-LOCAL-01` | 创建模型公共代码与本地 stub 测试 | 本文和依赖 L2 已评审可实施、用户授权、本地限定测试和代码对照设计评审通过 | Closed | 本地 stub 切片已完成；不授权真实 transport、PoC 或 Runtime live 装配 |
| `SA-GATE-002` | slice_implementation_completion | P3/P4 / `WP-MODEL-ACTION-V4-LOCAL-01`、`WP-MODEL-ACTION-POC-03` 历史、`WP-MODEL-ACTION-POC-04`、`WP-MODEL-RUNTIME-01` | 声明真实模型 Runtime 切片完成或在目标环境显式启用 DeepSeek | 混合解析/业务 Resolver、v4 非 live 与 candidate-01 历史 provenance 验证通过；corrected candidate-02 按14.4达到全部门槛；answer 6/6；P3 `GATE-020` 已关闭并完成受控 wiring；预算/失败/secret/组合根/生命周期回归通过；项目维护者确认 | Closed（2026-08-12；只关闭受控 Runtime 实现切片） | 允许维护默认stub与显式deepseek装配代码；目标环境启用、真实知识/业务数据出域及任何新增付费调用仍须独立授权并受`CR-GATE-003/SA-GATE-006`和领域门禁约束 |
| `CR-GATE-003` | integration | P4 / 用户问题进入 DeepSeek | 敏感用户问题进入 DeepSeek | 问题类别、最小化、业务/知识 fixtures、denied/unknown 零调用均通过 | Closed（2026-08-12；仅问题输入安全前置） | 允许通过 Guard 的最小非敏感问题进入另行授权的后继模型工作包；具体敏感/unknown 问题仍失败关闭，Employee/Transaction 本地 Resolver 路径继续模型零调用；不授权真实领域数据出域或目标环境启用 |
| `SA-GATE-006` | integration | P4 / Knowledge、Employee、Transaction 结果出域 | 真实知识证据/业务结果进入 DeepSeek | 领域出域、grounding、未分类/冲突失败关闭、零调用证据 | Open | 只允许合成 safe payload |

### 16.3 需要后续授权

- `WP-MODEL-ACTION-POC-04` 已按绑定授权完成且 `GATE-038` Closed；candidate-02 evidence只能用于其固定契约可行性，不授权重跑或追加模型调用。
- `WP-MODEL-RUNTIME-01` 已在默认stub、fake transport、无新增live调用下完成；后继真实数据出域、默认/目标环境启用仍须独立工作包和门禁授权。
- 发送敏感用户问题、真实知识证据或真实业务结果。
- 改用 beta endpoint、其他模型、SDK、代理 URL、自动 retry 或动态 Prompt。
- 关闭任一实施/集成门禁。

## 17. 内部自检记录

| 轮次 | 日期 | Blocker | Major | Minor | 已修复 | 遗留 | 停止原因 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | 2026-07-25 | 0 | 1 | 2 | 3 | PoC/领域 policy 属开放门禁 | 修复非权威 Provider 字段、内聚依据、JSON Output 与路径标记 |
| 2 | 2026-07-25 | 0 | 0 | 0 | 0 | PoC/领域 policy 属开放门禁 | 完整 rubric 复核无目标内材料缺口，进入严格校验 |

作者自检不构成正式批准、真实模型可用证明或门禁关闭。

## 18. 独立正式评审记录

### 18.1 第 1 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-001` | S1 | 文档让已批准核心 `AgentRuntimeInvoker` 直接设置 model ContextVar，却未在核心契约中定义，形成隐式侵入 | 改为 model 包外层同签名装饰器，核心/graph 不导入 model | Closed（第 2 轮） |
| `REV-MODEL-002` | S1 | HTTPX read timeout 是“等待下一块”超时，DeepSeek keep-alive 可持续重置；响应上限也未保证在聚合前执行 | 增加单一 `asyncio.timeout_at`、流式 raw byte 上限和所有退出路径关闭 | Closed（第 2 轮） |
| `REV-MODEL-003` | S1 | HTTPX 默认信任代理/证书环境且 client 关闭责任未固化，外部模型出域路径可被环境扩大 | 固定 `trust_env=False`、verify、无 redirect/HTTP2、retries=0、identity encoding 和 lifespan aclose | Closed（第 2 轮） |
| `REV-MODEL-004` | S1 | task definition、Provider DTO、JSON parser 和 grounding policy 缺少输入输出签名，无法直接实现或做跨模块契约测试 | 补齐公共类型、边界函数、Provider DTO 字段全集与直接消费者 | Closed（第 2 轮） |
| `REV-MODEL-005` | S1 | 单值问题分类未定义复合 allow+deny 优先级，后匹配可能覆盖敏感命中 | 改为类别集合且任一 deny 优先，加入 instruction injection 和复合 fixtures | Closed（第 2 轮） |
| `REV-MODEL-006` | S1 | task input、tools 与完整 HTTP request 共用 65536 表述，无法证明最终请求有界 | 分离 canonical task input、prompt/tools 和 131072-byte 完整 request 上限 | Closed（第 2 轮） |
| `REV-MODEL-007` | S1 | Provider 非 200、model allowlist、重复 JSON key、未知字段兼容策略和模型输出 extra 语义未闭合 | 固定 catch-all 状态、精确 model、unique-key JSON、Provider 新增字段与生成对象不同兼容规则 | Closed（第 2 轮） |
| `REV-MODEL-008` | S1 | `SA-GATE-002` 一边禁止真实 Provider 实现、一边要求用它做 PoC，且 PoC 仅覆盖 action、不覆盖 JSON answer | 允许经双重授权的隔离 harness，禁止 Runtime wiring；门槛增加 6 次合成 answer PoC | Closed（第 2 轮） |
| `REV-MODEL-009` | S2 | 测试表只有断言，缺少关键 fake、时钟、并发和执行动作，不能证明负向测试不会假阳性 | 增加共享 fixture/setup/action/资源释放矩阵 | Closed（第 2 轮） |

首轮修复不构成评审通过，不关闭任何实施、PoC 或真实数据门禁，也未使用
`LLM_API_KEY` 发起生成调用。

### 18.2 第 2 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-010` | S1 | `DR-MODEL-001`～`015` 只被追踪表引用却没有权威规则定义，实施者无法判断散落正文与规则 ID 的确定关系 | 增加 7.5 设计规则目录，并保持每条规则到 IMPL/TEST/VAL 的既有追踪 | Closed（第 3 轮） |
| `REV-MODEL-011` | S1 | answer PoC 已成为 `SA-GATE-002` 关闭条件，但实现/测试追踪仍只列 action 文件，可能在缺少 answer 证据时误关门禁 | 增加 `IMPL-MODEL-017`、`TEST-MODEL-012`，同步 REQ 追踪、fixture 与验证命令 | Closed（第 3 轮） |
| `REV-MODEL-012` | S1 | 配置允许调整 response bytes，但响应流程硬编码 262144/262145，配置改变后会出现两个权威上限 | 统一引用冻结 `max_response_bytes`，保留 262144 仅作为默认值 | Closed（第 3 轮） |
| `REV-MODEL-013` | S2 | 本文仍把模型预算称为“同一硬截止”，与 `L2_00_00` 已批准的接入硬截止/Runtime 子截止二级预算不一致 | 改为消费 Runtime 子截止且不得恢复接入预留 | Closed（第 3 轮） |
| `REV-MODEL-014` | S1 | 非 200 响应虽有失败映射，却未规定错误正文是否读取，可能绕过 body 上限并把外部正文带入解析/日志 | 固化先判 status、非 200 零正文读取并关闭 response | Closed（第 3 轮） |

第二轮修复仍不构成评审通过，也不授权目标代码、真实 Provider wiring 或任何生成调用。

### 18.3 第 3 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-015` | S1 | 公共 task 构造 `StructuredModelRequest`，但 transport 签名收发 `DeepSeekRequest/Response`，会迫使公共 gateway 依赖供应商 DTO，与 Provider-neutral 目标冲突 | 增加 `StructuredModelTransport`，只收发 neutral DTO；DeepSeek adapter 内部完成双向投影 | Closed（第 4 轮） |
| `REV-MODEL-016` | S2 | `knowledge_rewrite/summary` 有默认超时但配置只列 action/answer，实施者可能自创两套配置或使用无界默认 | 明确分别复用 action/answer timeout，领域只能代码级收紧且本期不新增配置 | Closed（第 4 轮） |
| `REV-MODEL-017` | S2 | action PoC 只有 90% 聚合门槛，一个 case 持续误选仍可能整体达标 | 增加每 case 至少 2/3 符合预期的下限 | Closed（第 4 轮） |

第三轮修复仍不关闭实施、PoC 或真实数据门禁；下一轮须重新检查全部规则和跨边界契约，
不能只验证本轮三处文本存在。

### 18.4 第 4 轮冻结发现与修复

| 发现 ID | 严重度 | 冻结证据与影响 | 修复 | 当前状态 |
|---|---|---|---|---|
| `REV-MODEL-018` | S1 | neutral request/tool 仍只有概念字段，没有精确类型与有限模式，两个 adapter 可产生不兼容结构 | 固化 `StructuredToolDefinition`、`StructuredModelRequest`、context 的字段类型和有限枚举 | Closed（第 5 轮） |
| `REV-MODEL-019` | S2 | 凭证章节使用不存在的 `DeepSeekSettings`，且 `map_deepseek_failure` 落点没有边界签名 | 统一为 `ModelSettings`，增加有限私有 failure 入参与穷尽返回签名 | Closed（第 5 轮） |
| `REV-MODEL-020` | S2 | 组合根步骤让 stub 也创建 DeepSeek client，且 readiness detail 试图增加 `L2_00_00` 所有的 HTTP 契约字段 | stub 不读取 key/不创建 client；readiness 只复用既有语义，安全枚举移至日志/指标 | Closed（第 5 轮） |

第四轮修复仍为待复评状态；不以字段补齐或严格校验结果提前判定通过。

### 18.5 第 5 轮终审结论

第 5 轮从上位约束、职责/依赖、neutral/DeepSeek DTO、输入与证据出域、绝对截止、
失败映射、配置生命周期、实现签名、负向测试和门禁证据重新全量检查；未发现新的
S0/S1/S2，`REV-MODEL-001`～`020` 全部关闭。评审结论为 Approved/设计已具备实施就绪
条件，但在 `CR-GATE-002` 关闭前不构成当前实施依据；这不证明真实 DeepSeek 生成、
Tool Calls/JSON Output 质量或真实领域数据出域已经通过。

### 18.6 Knowledge 消费契约针对性复评

`L2_01_00` 首轮评审发现 Knowledge 不能把 gateway 的通用 `input_denied` 等同于“问题出域
拒绝”，因为完整模型请求超界也使用该 failure kind。冻结发现 `REV-MODEL-021`（S1）后，
本文采用最小修复：不扩大 `ModelTaskResult`，只让既有 `QuestionEgressDecision` 的 denied
分支也携带安全策略版本；Knowledge 在调用 gateway 前显式使用同一个 guard，从而只有
guard denied 才设置 `question_egress_denied`，后续 gateway input denial 仍按任务输入失败
处理。针对性复评确认 selector/answer 既有行为、Provider DTO、failure kind 和全部门禁均
未变化，`REV-MODEL-021` Closed；本文保持 Approved。

### 18.7 v0.8 selection-only 评审批次

| 阶段 | 审计 ID | 本文重点 | 结论 |
|---|---|---|---|
| 三轮作者内审 | `AR-HYBRID-01～03` | ID-only 中立契约、空参数 tool 投影、v3 task/fixture/证据与历史 append-only 边界 | 修复后无遗留 Blocker/Major，严格校验通过 |
| 五轮独立评审 | `FR-HYBRID-01～05` | canonical tool 顺序与碰撞；执行 Schema 零可达；manifest/hash 防漂移；one-shot 30 次授权；PoC、wiring、完成门禁无环 | 新增发现均已关闭，无未关闭 S0/S1/S2；未发起 v3 调用、未开放 `GATE-020/035` 或 `SA-GATE-002` |

逐轮冻结发现与原子修复摘要见 `P3_00` 13.18；本批次不覆盖或重写 v1/v2 历史 evidence，也不构成付费调用或 Runtime wiring 授权。

### 18.8 v0.10 v4 作者聚焦自检

| 自检项 | 结论 |
|---|---|
| v3 证据真实性与不可变性 | 已核对 result/consumed 文件、run ID、manifest SHA、30 次记录与两项文件 SHA；失败结论及已耗尽授权固定，不允许补跑或改判 |
| 最小契约变化 | 仅把 DeepSeek action 编码从空参数 Tool Calls 改为标准 JSON Output 的 ID envelope；`CapabilitySelectionDecision`、Resolver、最终候选、Core 和领域参数不变 |
| 外部契约 | 继续正式 `/chat/completions`；不采用需要 `/beta` 的 strict Tool Calls，不新增 SDK、重试或动态 Prompt |
| 安全与失败关闭 | capability catalog 只读安全 descriptor 字段；执行 Schema、业务参数、真实问题/数据仍零可达；空 content、未知/额外字段、tool call 和 prose 全部拒绝 |
| 评审状态 | 作者自检不等于独立正式评审；`GATE-036` 保持 Open，v4 代码和付费 PoC 均未授权 |

### 18.9 v0.11 v4 独立聚焦评审

| 轮次 | 冻结发现 | 修复与复核 | 结论 |
|---:|---|---|---|
| 1 | `REV-V4-002`（S1）：安全目录可能原样外发 wire 参数名，且 catalog/envelope/hash/配额边界不唯一；`REV-V4-003`（S1）：`tools/tool_choice` wire 与 exact decoder 不唯一；`REV-V4-004`（S1）：v3“代码 append-only”与修改同名工作树冲突；`REV-V4-005`（S1）：非法 catalog 的失败语义不唯一；`REV-V4-006`（S2）：组件/依赖状态混有立项期表述 | 固化 `model-catalog-text-v1`、catalog 与 envelope 分界、单一配额和 hash；Provider body 省略 tools keys，明确结构 exact/JSON whitespace；以不可变 artifact/hash + Git 来源提交冻结 v3；非法 catalog 固定 `invalid_output`/零调用；更新当前状态 | 待第 2 轮复核 |
| 2 | 重新检查 Provider-neutral ID、Provider wire、unique-key decoder、失败映射、v3 provenance、v4 manifest 和 P3 依赖/门禁 | 未发现新的 S0/S1/S2；`REV-V4-002～006` Closed；P3 依赖保持 v4 non-live → v4 PoC → wiring → 完成声明，无反向依赖 | 聚焦评审通过；不创建代码/fixture/manifest，不读取 key、不调用 DeepSeek；`GATE-036` 仅满足评审子条件 |

本轮同时核对 DeepSeek 官方 JSON Output 约束：请求使用 `response_format={"type":"json_object"}`，Prompt 显式要求 JSON 并给出示例，且本地必须处理空 content；Tool Calls strict 仍需 Beta base URL，因此 v4 继续采用正式 endpoint/no-tools JSON Output。官方能力只保证 JSON 语法，不替代本地字段、枚举和目录成员校验。

### 18.10 v0.13 candidate-01 失败后的作者聚焦自检

| 自检项 | 结论 |
|---|---|
| 历史证据不可变性 | candidate-01 的 manifest/result/consumed、30次计数、30/30结构、27/30聚合、`transaction_fields=0/3` 和 `failed` 结论均按现有 bytes 固定；后续只通过 commit `cd8007e58bbeca902bec722eb98bbfbf8fe7c55f` 审计历史实现，不修改旧文件 |
| 语义根因与最小变更 | `transaction.search` 是执行型受控查询，不提供字段字典/接口帮助；只版本化 fixture、历史 provenance、candidate-02 manifest/Harness/test，不修改 Prompt、descriptor、question guard、decoder、Resolver、Core、handler 或门槛 |
| 覆盖与失败语义 | corrected fixture 固定3个 Knowledge、3个 Employee、3个 Transaction 正向和1个近域 `agent_unsupported`；旧字段问题不追溯重判，candidate-02 的任一结构、聚合或单 case 下限失败仍整体失败 |
| 门禁无环性 | `WP-MODEL-ACTION-V4-LOCAL-01` → `WP-MODEL-ACTION-POC-04` → `WP-MODEL-RUNTIME-01`；`GATE-038` 只控制新的付费 PoC，`GATE-020` 只消费通过证据后控制 wiring；历史 `WP-MODEL-ACTION-POC-03/GATE-037` 不再作为后继依赖 |
| 授权边界 | 本轮只允许文档和非 live 资产；不读取 `LLM_API_KEY`、不产生 outbound、不关闭 `GATE-038/020/SA-GATE-002`。作者自检不替代独立聚焦评审 |

### 18.11 v0.13 candidate-01 失败后的独立聚焦复评

| 检查项 | 证据 | 结论 |
|---|---|---|
| 历史失败不可追溯改判 | candidate-01 result 保持 `failed`，30/30结构、27/30聚合、`transaction_fields=0/3`；manifest/result/consumed 三类资产均有固定 SHA-256，`GATE-037` 只表示一次性入口已消费 | 符合 |
| corrected fixture 与 descriptor 语义 | `transaction.search` descriptor 只承诺受控查询；输出字段帮助固定为近域 unsupported，查询条件类表述只用于 selection-only 能力族识别；3/3/3/1分布、阈值和最终 Resolver/validator 权威均未改变 | 符合 |
| 历史 provenance | 独立从 Git commit `cd8007e58bbeca902bec722eb98bbfbf8fe7c55f` 读取 candidate-01 manifest 列出的15个实现文件并重算 SHA-256，15/15一致；不要求当前工作树回退 | 符合 |
| 门禁与授权无环 | P3 依赖为 v4 local→candidate-02→Runtime；`GATE-038` 只控制新付费 PoC，`GATE-020` 只在 PoC 通过后控制 wiring，非 live 结果不能反向关闭任一门禁 | 符合 |

本次为限定问题的独立聚焦复评，无执行阻断、无 S0/S1/S2；结论只允许实施 `IMPL-MODEL-020/VAL-MODEL-010` 非 live 子步骤，不构成 candidate-02 付费调用、Runtime wiring、模型出域或完成声明授权。

### 18.12 v0.14 corrected 非 live 代码对照设计复核

| 对照项 | 实现/验证证据 | 结论 |
|---|---|---|
| 历史证据与来源 | candidate-01 manifest/result/consumed 三个固定 SHA-256 均通过；从 commit `cd8007e58bbeca902bec722eb98bbfbf8fe7c55f` 重建15个实现文件，15/15与旧 manifest一致 | 符合 |
| corrected fixture 与边界 | 新 fixture 精确3个Knowledge、3个Employee、3个Transaction正向和1个近域unsupported；旧字段问题和新查询项问题的ID/预期固定；全部问题通过现有输入闸门，未修改生产model/descriptor/guard/decoder/Core/Resolver/handler | 符合 |
| candidate-02 严格冻结 | run `action-selection-v4-20260810-candidate-02`、authorization reference `P3_00:GATE-038`、30次上限和15个current实现哈希写入append-only manifest；SHA-256 `9ec90a3f8a874308fb6a0a8c580ea8adae037f39bbf430717dfc6f58d531a494`，无consumed/result | 符合 |
| 非 live 与回归 | 精确46 passed、模型相关161 passed、全量564 passed/6 live skipped、strict mypy 239 files、compileall通过；两个DeepSeek live opt-in均显式禁用 | 符合 |

代码对照设计复核无可操作缺陷；`VAL-MODEL-010`完成。该结论只覆盖非 live 子步骤，`WP-MODEL-ACTION-POC-04`整体仍受 `GATE-038` 阻断。

### 18.13 v0.15 candidate-02 live 证据复核

| 复核项 | 证据 | 结论 |
|---|---|---|
| 一次性授权与不可重放 | run、manifest SHA-256与`P3_00:GATE-038`精确匹配；consumed marker在执行前append-only创建，SHA-256为`64478b36c68afba51fd4eb69b11dc1c6d31e412f45ddb87fbbe3ab7babf48fba` | 符合；授权已耗尽，禁止重跑/补跑/续跑 |
| 计数与阈值 | 唯一结果`action_selection-20260810T120158644883Z.json`严格Schema通过；30个唯一`(case_id,repetition)`记录，结构/预期/arguments空均30/30，逐case均3/3 | `VAL-MODEL-011`通过 |
| 边界与数据最小化 | `invalid_execution_count=0`、真实业务执行0；result无question/raw response/JWT/API key/员工或交易标识/金额字段 | 符合 |
| 后继门禁 | `GATE-038`只控制本次付费PoC；Runtime仍stub-only，`GATE-020/SA-GATE-002/CR-GATE-003/SA-GATE-006`未被本证据关闭 | 符合 |

本轮为实施证据与门禁状态复核，没有修改生产模型代码、Prompt、descriptor、输入闸门、decoder、Core、Resolver或handler；不构成独立正式代码评审或Runtime wiring授权。

### 18.14 v0.19 Transaction 问题策略与候选实现代码对照设计复核

`question_policy.py`仅以fullmatch新增三类无具体值的单条Transaction结果说明，敏感类别仍先行拒绝，具体金额、交易号、账户、凭证、注入、控制字符、额外语义与unknown均在模型前失败关闭。历史Action PoC改为校验冻结manifest/evidence哈希，不再用当前源码重建历史快照，未修改任何历史字节。

fake candidate复用生产answer generator与grounding；直接回归253 passed/2 live skipped，全量non-live 913 passed/18 skipped，strict mypy 321 files、compileall通过。未读取`LLM_API_KEY`，真实Transaction/DeepSeek调用均为0；未发现S0/S1/S2代码对照偏差。

### 18.15 v0.20 Business Answer v2聚焦独立设计评审

| 复核项 | 证据与判断 | 结论 |
|---|---|---|
| 根因与最小修复位置 | Employee candidate-03已形成30个模型终态但有效回答0，均为`invalid_output`；现有v1 system instruction只要求返回`used_fact_ids`，示例没有行内`[fact-NNNN]`，而既有Business grounding明确要求每个事实片段带marker且marker集合等于ID数组 | 根因位于模型可见输出约束，不在Employee数据、授权、transport、parser或validator；不建议放宽validator |
| 公共契约与兼容性 | v2复用v1 input DTO、user payload、response parser与`CandidateAnswer`，只替换task version/system instruction；Core/HTTP/Stage、字段矩阵、领域参数和失败枚举不变 | Provider-neutral边界与调用方二进制/JSON语义不变；回滚只需组合根恢复v1+stub |
| 历史不可变性 | answer v1源码、Employee candidate-03五项证据及Transaction candidate-01 manifest/auth保持字节不变；组合根演进不得反向要求当前bootstrap继续等于旧manifest | Employee candidate-03为`failed_consumed`历史；Transaction candidate-01虽未消费但current-source身份已过期，二者均不得live复用 |
| 门禁无环性 | 本地v2、Employee candidate-04与Transaction candidate-02均已完成；两域prepared候选只单向进入各自live工作包 | `GATE-053/054/055`已关闭；`GATE-024/026`只控制各自真实外发，未形成Blocked反向依赖 |

聚焦评审未发现未关闭S0/S1/S2。批准按`IMPL-MODEL-022/TEST-MODEL-019/VAL-MODEL-015`实施fake-only本地切片；不授权任何真实模型或业务调用。

## 19. 实施前检查

- [x] 所有范围内 REQ/CON 已映射到 DR。
- [x] 所有重要 DR 已映射到 IMPL、TEST 和 VAL。
- [x] Provider-neutral 与 DeepSeek-specific 路径、关键函数、输入/输出/失败已明确。
- [x] capability ID selection、混合候选构造、业务参数解析、answer generation 和 Knowledge task 的所有权不重叠。
- [x] 问题输入、领域 safe payload、凭证和日志均失败关闭。
- [x] timeout、并发、token/byte、retry 和取消边界明确。
- [x] PoC 与真实数据门禁未被 `/models` 核实替代。
- [x] `validate_detailed_design.py --strict` 已通过，结果为 0 errors、0 warnings。
- [x] 历史 Approved 范围的独立评审已关闭全部 S0/S1/S2；不包含 v0.10 v4 增量。
- [x] v0.8 selection-only 修订已完成 `AR-HYBRID-01～03` 与 `FR-HYBRID-01～05`；v0.9 已补充 v3 非 live 实现，v0.10 已如实记录一次性 v3 失败证据并形成 v4 设计增量。
- [x] `CR-GATE-002` 已按 `WP-MODEL-LOCAL-01` 关闭，本地限定实现、97 项模型相关测试、158 项全量回归和代码对照设计评审通过。
- [x] v0.11 v4 增量已完成独立聚焦复评，无未关闭 S0/S1/S2；v0.12 已按授权完成非 live 实施、`VAL-MODEL-008` 和代码对照设计复核，`GATE-036` Closed。
- [x] `WP-MODEL-ACTION-POC-04/VAL-MODEL-010/011` 已完成；candidate-02按绑定授权恰好执行30次并满足全部聚合/逐case/零参数/零业务执行门槛，`GATE-038` Closed且禁止重跑。
- [x] P3 `GATE-020` 已取得项目维护者对 Runtime wiring 代码与fake生命周期测试的单独授权，并按完整实施证据关闭。
- [x] `WP-MODEL-RUNTIME-01` 已在默认 stub、fake transport、无新增 live 调用下完成组合根/生命周期回归，并据此关闭 `SA-GATE-002` 的 Runtime 实现切片。
- [x] `TEST/VAL-MODEL-017/013` 已补齐 Knowledge/Business 问题 fixture、最小化、denied/unknown 传播与 selector/answer/rewrite/summary 零 transport 证据，`CR-GATE-003` 仅按问题输入安全前置关闭。
- [x] `DR-MODEL-018/IMPL-MODEL-021/TEST-MODEL-018/VAL-MODEL-014` 已完成：`question-egress-v2` exact allow、具体值/敏感/unknown零调用、历史哈希兼容和candidate fake回归通过；真实外发仍受`GATE-026`。
- [x] `DR-MODEL-019/IMPL-MODEL-022/TEST-MODEL-019/VAL-MODEL-015` 已实施验证：独立answer v2、生产组合根、严格grounding正反例和冻结历史兼容均通过，`GATE-053`关闭；旧candidate仍只作历史。

## 20. 当前结论

本文升为 v0.23；历史 Approved 范围和证据继续有效且不被重写。独立`answer-generation-v2`继续只强化marker与`used_fact_ids`集合一致性，v1、公共`CandidateAnswer`、parser、validator和历史资产保持不可变。Employee candidate-04与Transaction candidate-02已分别以全新run/manifest/auth绑定answer v2/current bootstrap并通过fake/static/disabled验证，`GATE-054/055`关闭；Transaction manifest SHA-256=`527845915ad15aa6f24fe59ed31885dcd3fef245109e7cee820217a86cbafa9c`。该结论不授权真实模型外发，两域仍受`GATE-024/026/SA-GATE-006`。`question-egress-v2`的Transaction通用结果说明窄放行仍有效；具体值、敏感类别和unknown继续失败关闭。v3 已按一次性授权失败；v4
candidate-01 也已完成30次，虽达到结构30/30和聚合预期27/30，但 `transaction_fields=0/3`，
因此明确失败且不得补跑或改判。根因是该 fixture 把字段字典/接口帮助错误标为查询执行动作，
不是 Prompt、descriptor、decoder、Resolver 或 Core 缺陷。本文仅设计版本化 corrected fixture、
candidate-01 Git provenance、candidate-02 manifest 与非 live 验证：旧字段问题改为近域
`agent_unsupported`，另以明确交易查询意图维持3个 Transaction 正向 case；不修改能力契约、
输入闸门或既有门槛。上述 corrected 非 live 资产已通过 `VAL-MODEL-010` 与代码对照设计复核，
candidate-02 manifest SHA-256 为 `9ec90a3f8a874308fb6a0a8c580ea8adae037f39bbf430717dfc6f58d531a494`，
已按`GATE-038`完成恰好30次并以结构30/30、预期30/30、逐case均3/3、arguments空30/30、
真实业务执行0通过；result/consumed两项append-only哈希已复核。`WP-MODEL-ACTION-POC-04` Done，
`GATE-038` Closed且禁止重跑。在此基础上，`WP-MODEL-RUNTIME-01` 已将既有 transport、ID-only
selector、answer generator 与 `ModelContext` 受控装配到 Runtime：默认 provider 仍为 `stub`，
仅显式 `deepseek` 配置创建一个受管 client，lifespan 幂等关闭并在关闭后拒绝新调用；无效组合根参数在client分配前失败。168项模型定向、
570项全量非live、241文件strict mypy、compileall及代码对照设计复核通过，`GATE-020` 与
`SA-GATE-002` 按 Runtime 实现切片关闭。其后 `TEST/VAL-MODEL-017/013` 以 fake-only 证据验证问题分类、最小化、
业务/Knowledge fixtures 以及 denied/unknown 在 selector/answer/rewrite/summary 的零 transport；172项定向、
578项全量非live、243文件strict mypy与compileall通过，故 `CR-GATE-003` 仅按问题输入安全前置关闭。
`SA-GATE-006`及真实数据出域门禁保持 Open；本版本只关闭fake-only的`WP-BUSINESS-ANSWER-V2-LOCAL-01/GATE-053`，禁止重跑旧candidate、追加付费调用、目标环境启用、具体敏感问题或真实知识/业务数据出域。
