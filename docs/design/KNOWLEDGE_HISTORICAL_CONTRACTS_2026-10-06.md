# Knowledge历史合同及单批验证协议

本附件保存从当前设计分离的原文，只解释当时合同和批次，不是当前实施前置、状态权威或新授权；历史终态与资产不修改。

- 来源提交：`3d75bc7bedcc83a896b0951d95b11efdf18c53d1`
- 来源：L2_01_02原§13；L2_01_01原§18.4.2至§18.5之前。
- 整理日期：2026-10-06；完整来源及字节可通过该提交恢复。

<a id="historical-p5"></a>

## 13. 既有P5评估合同与兼容边界

### 13.1 数据与执行

- 正式数据集：`representative_questions.v2.jsonl`，26 case；22 个普通案例继承 v1，只替换 4 个确定性安全负例。
- 每 case 顺序执行 primary、rewrite_ablation；各调用一次真实 `KnowledgeQueryCapability.handle`。
- primary 使用生产 rewriter；ablation 只换 `IdentityQuestionRewriter`，其他配置、Provider、授权、Profile/index snapshot、模型任务完全一致。
- collector 只旁路采集有限阶段 ID/排名/计数，不改变在线行为；结果不保存 question、content、quote、title、URL、JWT 或原响应。

### 13.2 有效 run 前提

clean frozen commit、live Provider、数据集/hash、principal/读取授权、四项前置安全证据、问题/域/flow/Profile/全部 index snapshots、BGE、task、DeepSeek、policy/evidence/evaluator versions 全部冻结；52 个 capability 执行成对完整，retry/resume=0。任一缺失、dirty、变体不一致、安全计数非零、必需分母为空，或质量可评 answerable 少于原 answerable 集合的 90%，结论为 `invalid_run`。

### 13.3 指标与阈值

| 问题 | 通过阈值 |
|---|---|
| 安全必备 | constraint preservation=1.0、citation validity=1.0、denied summary calls=0、unauthorized content=0 |
| Q1 改写/域 | rewrite rerank recall delta≥0、regression≤0.10、domain exact match≥0.85 |
| Q2 排序 | rerank recall@10≥0.80 且 rerank MRR@10≥fusion MRR@10 |
| Q3 忠实 | faithfulness≥0.95 |
| Q4 初始可用 | valid summary completion≥0.90 且 usefulness≥0.80 |

有效 run 中 Q1～Q4 全部通过=`effective`，至少两个但非全部=`partially_effective`，少于两个=`ineffective`。阈值不变。效果口径 v2 的分母规则为：

- `summary valid completion` 统计所有非 `security_negative` primary case；安全负例必须在 Summary 前拒绝并由零调用安全 Gate 单独判定，不得同时作为摘要失败样本；
- 普通 `no_result`、`insufficient_evidence`、`downstream_failure`、timeout 和 schema/validator failure 继续作为 summary completion 失败计入，不因不利结果排除；
- faithfulness/usefulness 只统计 answerable 且人工 reason 不是显式 `gold_issue` 的 primary case；`gold_issue` 数量和 case ID 必须保留在有限结果中，质量可评样本比例低于 90% 时整次 run 无效，不能靠大量排除提高指标；
- dataset、gold、人工 rubric reason 枚举和 Q1～Q4 阈值不变，历史候选继续按各自冻结 evaluator 解释，不回算、不改判。

### 13.4 人工 rubric

对 primary 的 answerable case 判断 faithful、relevant、sufficientForInitialAnswer、useful；reason 只允许 `none/quote_context/relevance/coverage/gold_issue`。评审时临时查看授权证据，提交布尔值后释放正文。

### 13.5 适用范围

本节P5 primary/ablation、Q1～Q4和rubric只解释原评估合同，不是过渡12/8或当前12/9测量方法或继续运行授权。历史诊断、优化准备及可选准入流水见整理前归档；原结果不得重算改判。当前目标四维方法见§9.4及UAT_02 §5，最新有效结果与最新执行分开。KQ历史效果不外推至新任务。


<a id="historical-startup-protocol"></a>

#### 18.4.2 独立启动预检与既有候选承接（细化DR-KRET-307）

旧B比较及MEASURE已有失败终态，不复用其run、授权或已消费目录。维护者曾另行授权新的独立验证批次，题目、gold、阈值、B正式预算及MEASURE模型/typed/推理预算不变；随后明确批准仅将新MEASURE正式只读元数据上限纠正为72。该授权及运行终态以P3_01为准，不是本合同授予的滚动运行许可。技术顺序仍为先完成不读取模型密钥、不进行模型或BGE推理的真实启动预检，再冻结正式比较和测量。以下仅是内部验证工具合同，不新增公共接口、查询能力或生产服务。

- **启动预检**：新目录、新run ID绑定当前干净`codex_0915` HEAD及实际JAR/配置hash；复用正式启动参数、端口归属、Profile核验与清理逻辑，不调用题目、ledger或比较器。B两臂最多30次ES元数据请求、4次本次随机隐藏alias添加/移除、每臂60次本地readiness检查；typed search、embedding、rerank、外部模型和JWT请求均为0。代理必须拒绝search，不能通过给正常比较的search额度来伪称零调用。预检允许的临时alias不是线上发布alias，清理只能移除仍能核实本次归属的对象。MEASURE预检使用clean HEAD构建证明和既有批准索引绑定，在临时目录派生启动输入，验证三Spring及Runtime生命周期；Runtime仅使用合成非空密钥且只请求健康端点，不读取真实密钥、运行case或形成正式authorization。ES全记录前检上限仍为67次，启动元数据、健康轮询和登录分别计数；不把这些隐藏为测量调用。预检失败保存有限阶段/原因、退出码、hash、实际计数及PID/alias清理状态，不保存原始服务输出、密钥、JWT、正文或向量。成功只能证明启动和绑定可用，不代表功能、质量或发布通过。
- **既有只读候选的新批次绑定**：只复用已成功构建且保持write-block的候选，不重建、不写正文、不重算语料向量。旧构建binding/result/完整ID扫描作为不可变Git来源证明，保留原run、HEAD及字节；新run通过原路径、提交和SHA引用，而不是改写旧sidecar或伪造新builder result。新当前HEAD绑定新的运行配置、两域Profile、题目、计划和预算。执行前重新只读核验两臂UUID、mapping、write-block、全记录fingerprint、数量及ID/content hash一致性；每臂扫描上限为`1 + ceil(recordCount/250)`，现15521条对应64次。旧源证明与新扫描有任何不符即零typed/推理调用。新的内部准入分支必须同时验证旧构建来源与新扫描/配置绑定，不放宽旧v1准入或修改冻结资产；旧比较结果无论成功或失败均不作为新质量证明。
- **正式执行**：预检有限证据和工具先完成验证与本地提交；之后建立新冻结，冻结后tracked文件不得变化。B仍只执行既定10题（44 typed search、10 query embedding、22 rerank、30元数据、4临时alias写上限，paid/retry/resume=0）；MEASURE仍只执行既定12题（36模型、48 typed search、12 embedding、24 rerank上限）。运行前身份或预算不满足时不进入case；运行中技术/安全/快照失败形成唯一有限终态并停止，不自动补跑、续跑或新增批次。独立预检及新扫描的计数单列，不算成旧run的续跑，也不冒充正式质量结果。

MEASURE启动预检不要求重复全记录扫描，只核验启动身份；派生binding最多2次ES元数据、Profile启动最多6次、ES健康请求最多40次，独立启动元数据上限48，必须有实际计数/受限转发证明，不把无法观测的次数记为0。正式freeze的binding2次及服务就绪后的全记录快照67次分别执行，120秒鲜度不变。

正式MEASURE每case前后各执行一次完整身份检查，每次保留`/_alias/<readAlias>`与`/<expectedIndex>`两个GET，分别核验alias唯一目标/flags与索引UUID/mapping/write-block。12题对应24次检查、最多48次HTTP，而不是24次HTTP；加Profile启动6次及至多18次ES健康HTTP，新正式元数据总上限为72。每个实际HTTP attempt在发送前计数并受硬上限控制，包括失败请求；不以完成题数推算部分失败的实际次数。启动Java侧上限24与case侧上限48分账，合计不得超过72；先等待自有端口再执行有限健康检查，不以120轮未计数请求替代。此精确授权只适用于新冻结，不回写旧manifest的48字面量或旧终态，也不改变36模型、48 typed search、12 embedding、24 rerank的正式上限。

既有候选来源闭环必须包含旧构建intent、scan-plan、binding、attempt、result、两臂scan result/full map和assessment-final；按旧提交、原路径及逐文件SHA验证其完整准入，不仅验证result摘要。旧builderRunId/oldHead与新comparisonRunId/newHead明确分开。新10题、必要来源、计划、阈值及fixture与维护者已确认版本逐项/规范hash相等，当前配置hash独立新冻。复用路径的构建ES/BGE/write预算均为0；两臂新扫描各64次与正式比较预算独立分账，旧builderBudget只作为历史事实，不能当作新写入授权。

实施落点为现有B runner/transport、候选冻结工具及MEASURE prepare/launcher的私有接缝，避免复制一套在线链路。直接fake测试至少覆盖：预检禁止模型密钥读取及所有推理/search；新目录重用拒绝；配置/JAR漂移零启动；临时alias归属/清理；旧Git来源hash或原run漂移；新扫描UUID/fingerprint/ID不符零调用；正式批次不可续跑；有限失败证据及自有PID清理。对应验证为直接pytest、strict mypy、PowerShell AST和当前文档追踪；正式运行事实仍由P3_01/UAT_02记录。

v3.9本切片完成作者内审和同一任务内未参与起草的执行单元定向复评；先发现旧构建来源链不完整描述的S1及预检/正式元数据预算分账S2并修正，复评结论仅覆盖本内部验证切片，不代表正式真实运行或UAT通过。

v3.10计数纠正经同一任务内未参与起草的执行单元核对本节及P3/UAT/架构索引，S0=0、S1=0、未处理S2=0。工具仍须用实际HTTP attempt及失败负例证明预算守卫；该评审不证明真实启动、效果测量或发布通过。

v3.11作者内审及同一任务内未参与起草的执行单元定向源码/设计复评，先关闭GET双hash表示不明确的S2，复评S0=0、S1=0、未处理S2=0。结论只批准内部见证合同和状态修正，不补判已消费B、不证明新工具实施或真实质量通过。

#### 准备到执行的身份冻结顺序

先完成授权范围内的启动就绪，再采集当前完整身份并冻结执行预期；不能直接用旧准备快照的容器启动时间代替当前运行实例。私有纯本地`freeze_execution_identity(prepared, current)`核对两份完整capture的规范材料和hash、static/策略/Docker绑定精确相等，只按§18.4已批准的同模型规则允许embedding/rerank容器`started`差异，其余模型、代码、依赖和容器字段均须相同。它返回当前完整capture，保留旧准备材料、不回填旧hash；材料同一性不证明现场采集、就绪或授权，由可信调用方提供这些前置。

正式IdentitySession的pre/post仍与该当前capture精确相等；正式窗口内重启或漂移仍停止，不引入宽松模式、重试或追加probe。旧执行器、授权及失败终态不修改；本合同只支持后续独立且重新冻结的范围，不自动启动新批次。纯只读身份探针检查Python及其实际导入所需httpx/pydantic锁定版本；模型容器内部依赖仍按完整快照核验。解析/构建CLI的完整corpus依赖锁保持，不由探针的收缩豁免解析器环境。
