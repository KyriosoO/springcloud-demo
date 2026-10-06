# Knowledge成对资料对照的专项协议（2026-10-06）

本附件保留当前成对B质量归因所需的专用合同，仅用于需要两臂比较的实验；不是普通功能、安全或单臂测量的前置，不是生产适配层。当前候选构建、读取授权与发布边界仍由L2_01_01正文管理。

来源提交：`81760c4dac6eb6d565fac226955e09161aee3740`。以下原文保留其限定语境，不构成新的运行授权；旧路径、样本和预算只约束所绑定批次，不能自动继承到新运行。冻结顺序为先完成代码与工具修复、无付费预检及输入意图登记，再在实际候选存在后冻结UUID/快照、精确预算与运行绑定，最后执行批准批次；消费后不续跑或改写原证据。

<a id="protocol-1"></a>

## protocol-1 成对B构建冻结、隔离typed及请求见证协议

来源：`L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md` §18.4.1。

真实B的Profile与评价输入采用两阶段、append-only绑定：构建前冻结`assessment intent`，包含已确认的题目、必要来源、阈值、模式/域/计划、源索引及baseline两域实际快照、候选名称/mapping、两域Profile固定参数和预算；**不包含尚不存在的候选UUID或候选快照**。`CandidateSpec`、源扫描及builder只绑定该intent的规范hash。候选构建并按本节后验验证UUID、mapping、数量、全库fingerprint及ID映射后，从真实候选UUID按`KnowledgeProfileVerifier.snapshot(profileId,indexName,indexUuid,profileVersion,mappingVersion)`相同算法分别推导policy和law快照，写入新的最终assessment；最终assessment必须回链intent、builder结果及双臂只读扫描hash，题目、gold、阈值、查询计划及所有构建前可确定字段须与intent规范字节一致，不能事后改写。不得填占位hash、预猜UUID、覆盖intent或借真实结果调整gold。

`assessment intent`还必须精确绑定源b2候选的历史[binding.json](../../knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/binding.json)、[result.json](../../knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/result.json)路径及各自SHA-256。真实B构建入口在写入一次性`attempt`之前，从冻结HEAD读取这两份Git blob，核对旧构建result对binding的hash回链、源索引名称/UUID/全记录fingerprint/数量、旧表示版本和完整模型快照hash；仅凭当前索引名称或模型名称不构成旧向量来源证明。冻结文件被自算hash改写、来源不匹配或执行源码存在未跟踪/未提交变更时，首次ES/BGE构建调用必须为0。fake可使用合成来源测试合同，但不得产生真实B合格结论。

真实成对typed验证为基线和候选各创建一个随机独占、固定指向其索引的隔离只读alias，并分别启动由本次运行拥有的Java实例。两个实例使用相同的查询、category和ACL Profile参数；各臂的alias、预期物理索引名称/UUID、按intent分别冻结的mappingVersion/mapping SHA，以及据此计算的policy/law快照可以不同，不得把候选mapping误写成基线版本。启动前核实每个alias**仅**指向最终assessment指定的物理索引及UUID、mapping，启动时由`KnowledgeProfileVerifier`复核索引身份和Profile快照；现有Verifier不核完整alias flags，filter/routing等由B入口另行严格核验。仅在这两个隔离B实例中，内部查询目标固定为已核验的`expectedIndexName`，不得由用户请求、模型或公共DTO提供；生产实例默认仍查询`readAlias`，不得启用该隔离模式。私有固定目标开关默认关闭；只有版本化B launcher持有本次run绑定、独占alias和隔离进程归属证据时才可启用，缺任一证据则不启动typed比较。这样每次typed查询含零命中都以冻结物理索引为目标，不通过请求前后大量ES管理读取或`profile=true`改变110%时延口径。须用测试证明默认alias、非法隔离配置拒绝、零命中固定物理请求路径，以及两模式除目标路径外相同的查询体、授权、候选解码和失败语义；隔离模式不证明线上alias路径、发布或回滚，后者仍由DR-KRET-032及RELEASE独立验证。

每臂运行前后只读核验alias完整目标/flags及绑定索引UUID、mapping，并核对每个typed响应的静态Profile快照；静态快照不能独自证明物理归属，实际请求路径及服务隔离开关也须在有限证据中核实。本次独占窗口不得并行删除/重建索引或切换隔离alias；若无法确认这些前提，或运行中任一物理归属、快照、策略漂移，固定10题分母的整批B记`Not assessed`，记录实际调用并停止后续调用，不根据局部结果放行。两个alias仅各创建和移除一次，不为按题交替切换alias；alias写上限为4，元数据只读及typed上限按题/路径在intent中逐项精确冻结，不能借用DR-KRET-032的阶段A示例预算。按题交替只切换请求目标Java实例。清理仅限本次精确拥有的两个alias，归属异常时不清理他人资源。

B内部请求见证同时保留`request_sha256`（收到的原始UTF-8字节）和`canonical_request_sha256`（严格解析后的规范JSON），不保存请求正文。POST搜索转发前须拒绝非法UTF-8/JSON、重复对象键、非有限数及非对象根；规范化仅递归排序对象键和统一JSON序列化空白，保留数组顺序、字符串、数值类型及值，不规范化中文、条件、operator或向量内容。原始字节原样转发；GET只允许既有空body，两hash均为`SHA-256(b"")`的64位小写十六进制摘要，不使用null或空字符串。双臂相同请求按每臂22条POST规范hash的多重集合核对，原始hash只作字节身份见证，不要求跨JVM对象键序相等。路径、次数、授权、Profile、索引快照、清理及预算的其他准入条件不变。receipt及离线复核只接受有该双hash完整见证的新版本内部证明；缺规范hash的旧证据不能补算或升级为通过。严格解析失败须下游零调用并形成有限违规计数，不吞异常或以空hash通过。

数值保留必须覆盖高精度小数及极小指数，不能先经二进制float舍入或下溢，再生成规范hash。内部规范编码保留JSON数字词面；例如`1.0000000000000001`与`1.0`、`1e-999`与`0.0`不能视为相同请求。该约束不放宽非有限数或现有服务合法输入边界，也不要求将数字不同写法判为同一请求。

候选与基线共享Profile代码、ACL、category/keyword配置及查询参数；两臂的mappingVersion/mapping SHA按intent分别冻结，两域共用的**物理索引名称/UUID不同**，所以candidate的`tax.policy`与`tax.law`两个`indexSnapshotId`都须与各自baseline值不同。law不变性由全记录clone/CAS后验、law记录原文/向量/ACL及配置相等、逐阶段检索对照证明，不能以两臂law快照hash相等作断言。现有内部工具若仍要求构建前候选快照或law快照相等，只能完成fake组件验证；修订对应版本化内部冻结/比较合同并通过评审前，真实B、盲标和发布均不得启动。
