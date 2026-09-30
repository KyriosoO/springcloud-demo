# 一次真实测量准入失败：首次调用前终止

run `knowledge-rebuild-measure-20260930-02` 绑定 clean HEAD `d54ee293ec6517571f8a37fc616b1a7fceef19a3`、manifest SHA-256 `c10068ca11041917aaa4817f52b884caf90e0a01338872ec6b75bcf2e1f05450`，12题、意图12/Summary9/deepseek-flash及 b2 15521条记录。授权和冻结文件原字节保留。

版本化launcher启动三项隔离Spring服务并通过目标健康、端口归属、登录及完整快照准入，随后读取进程级模型密钥。runner进入`run_once`，但结果父目录`agent-runtime/tests/uat/results`不存在；`OneShotLedger.__init__`的`mkdir(parents=False)`抛出`FileNotFoundError`，发生在任何Runtime创建、case请求、consume或reserve之前。三项自有服务已由finally停止，四个目标端口均无listener。没有模型或业务响应、正文或向量转储。

`executor-failure.json`是执行者依据实际traceback、冻结源码控制流、缺失的consumed/journal和清理后端口核查形成的有限终态记录，**不是runner自动产物或调用journal**。模型、typed search、query embedding、online rerank及Business调用均0；12题均未执行，Effectiveness=`invalid_run`，Functional/召回/回答/人工rubric均未评价。密钥和JWT没有持久化；临时日志与快照由launcher清理，未保留可独立复核的运行快照文件。

本批停止，不复用仍写作`authorized_unconsumed`的冻结授权，不补跑或续跑，不创建额外真实批次。后续结果父目录前置和pre-ledger有限失败修复只进行non-live验证。B比较仍Not assessed，候选只读未发布，现行alias不切换，RELEASE受阻。
