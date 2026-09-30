# 构建准备：未冻结、未执行

本目录只保存 clean HEAD `c9b8642e9c20765814df4b3422cfa958a2c4900c` 的五个 Maven 构建命令及 JAR hash。构建后静态复评发现 launcher 的快照生成早于服务启动，可能超过 120 秒有效期；因此该准备不再冻结为真实运行。

没有 manifest、authorization、consumed、模型调用或效果结果。旧 build-attestation 字节保留；修复及定向验证后从新的 clean HEAD 准备同一目标尚未执行的一次测量，不属于付费重试或补跑。
