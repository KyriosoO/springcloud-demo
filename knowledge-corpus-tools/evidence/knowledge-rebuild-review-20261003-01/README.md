# 已封存结果的局部复核准备

§1～3材料从clean `codex_0915` HEAD `af9ac4a75a6a618c0da89912e1ca6fd40e10d899`开始，仅离线读取已存在的有限证据；不是新候选、重新测量、补跑或维护者人评。该离线复核没有网络、模型、ES、embedding、rerank或服务操作，不修改原始B/MEASURE资产、gold、阈值及预算。之后另获一次有限只读授权的当前元数据诊断见§4，两者证明范围分开。

## 1. 必要来源损失定位

[source-loss-localization.json](source-loss-localization.json)绑定[原B结果](../knowledge-b-reuse-20261003-01/comparison-result.json)及[MEASURE冻结清单](../../../agent-runtime/tests/uat/knowledge-rebuild-measure-20261003-01/manifest.json)。按10题的冻结必要来源检查16个题—来源组合，每臂缺失2项，均在keyword/vector召回窗口之前或之内未进入；没有必要来源在已进入初始候选后才因融合/重排/最终截断丢失。此计数是按既定chunk及精确正文hash定位，不是全候选相关性或人工precision。

| 题号 | 缺失来源 | 两臂完整扫描 | 两臂初始keyword/vector前20 | 后续阶段 |
|---|---|---|---|---|
| KM-003 | small_2022：2022年第13号公告第三条 | 精确document/chunk/content hash均存在 | 均未命中 | fused、reranked、final20均无该来源 |
| KM-012 | lease_real：不动产租赁依据 | 精确document/chunk/content hash均存在 | 均未命中 | fused、reranked、final20均无该来源 |

这排除了“目标chunk根本不在两臂扫描清单”和“仅在后续重排/摘要中丢掉这两个chunk”的解释；**不能**凭此区分Profile过滤/权限、查询匹配、原路径排名或top20窗口。没有超出窗口的排名、目标chunk的实际过滤判定或全部候选正文，因此不能直接断言扩大topK、修改向量或Prompt就能修复。

下一项诊断应先核对目标记录的可检索字段和既有Profile过滤、固定queryText及请求映射，再决定是否需要另行批准的有限只读探针；不进行新真实调用。B两臂recall均0.85、215项盲标未完成、主指标未改善的原结论保持不变。

## 2. 已完成四题的评价准备

已在既有受控本地review目录创建`partial-review.md`，与`public-review.jsonl`同目录，仅帮助维护者阅读，不提交引文正文或加工答案。001/002各自覆盖已冻结的资料查找义务，执行者建议待维护者确认；003未返回所需执行期限，004未编造内容但状态与冻结no_result不同，不能把安全拒绝等同于用例通过。

此材料没有填写正式rubric或215项盲标。第005题仍不可定位具体技术根因，006～012没有执行结果。即使前四题取得人工确认，MEASURE仍为invalid_run，不能变成完整12题通过；不得续跑、复用额度或据此发布。

## 3. 边界

COMPARE/MEASURE仍未完成，RELEASE仍不能执行。来源清单可证明记录存在，不证明当前部署、任意外部并发或权限可读；本材料只引用封存运行，不连接当前索引。原始B结果与MEASURE冻结清单的SHA-256见JSON绑定，复核时须同时校验原始来源及两臂扫描清单。不保存知识正文、向量、凭据、原始模型或完整服务响应。

## 4. 独立的当前元数据诊断

维护者在2026-10-03另行明确授权一次最多4次ES只读GET：索引身份前后核查各一次，两条目标记录各读取一次有限元数据；不读取正文/向量、不调用模型/BGE/typed search、不写索引或alias、不复跑B/MEASURE。执行起点为clean `codex_0915` HEAD `a1ba290e8b2d78da71d46bc1f39018be502c7347`。[current-metadata-probe.json](current-metadata-probe.json)记录4次实际attempt，均HTTP 200；前后UUID一致。该精确授权已用尽，不作为后续真实查询许可。

- 两条记录的`channel`都是`财税文件`，位于当前仓库tax-policy Profile允许集合内；仅排除当前category字面不匹配，未核验完整读取ACL、出域策略或正文hash。
- `small_2022`当前`documentNo`为`财政部 税务总局公告2022年第13号`；冻结第003题使用联合机关顿号。对原源码的离线精确匹配检查确认，旧规则只提取后一个机关，无法使这份完整文号获得可选metadata boost。这是已证实的软信号表示差异，不是对整个初始召回损失的充分解释。
- `lease_real`当前`documentNo`为`财税〔2016〕36号`。第012题未指定这个文号，不能以已知gold替换原问或向在线查询注入文号；其查询匹配与原窗口排序原因仍未核实。

本诊断不把当前元数据回填为历史运行字段，不复算或改变原recall、人评、MEASURE技术失败原因及invalid_run，不修改题目/gold或阈值。修正先在L2_01_01 v3.12 §9.8补齐通用联合机关词法并完成定向评审，再实施私有helper和两份直接测试。Java模块123项及Python历史/追踪26项通过，未参与修改的执行单元完成定向代码核查，无确认缺陷；详细命令、失败测试先行证明和验证限制见[P3_01 §14.36](../../../docs/plans/P3_01_SINGLE_AGENT_KNOWLEDGE_IMPLEMENTATION_PLAN.md)。未重新测量、发布或升级运行中的服务，不把这些non-live计数解释为新UAT通过。
