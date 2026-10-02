# 一次独立、无付费启动诊断

日期：2026-10-02。仅诊断启动，不执行 B 对照或正式 MEASURE。

## 基线与执行

- 分支：`codex_0915`。
- HEAD：`3536f687520ca2bf3d7d47104be3fc06373f1b65`。
- 启动 ID：`codex-knowledge-measure-startup-d725d15e61ff4131807752090aa60a12`。
- 通过当前版本化 prepare 工具构建所需 JAR；使用 `-DskipTests`，构建成功不代表 Maven 测试通过。
- 只执行一次版本化 launcher 的 `-StartupPreflightOnly`。未创建正式测量授权，未读取模型密钥，未重新运行失败批次。
- 四份 JSON/JSONL 是本次独立运行的有限原始产物；复制后逐文件核对 SHA-256，不修改运行终态。

## 已证实结果

- 终态：`startup_preflight_failed`，阶段：`es_ready`。
- 隔离健康接口 40 次均返回 HTTP 503；传输失败为 0。因此已复现的是健康检查未通过，不是无法建立 HTTP 连接。
- ES 元数据请求：48；typed search、model、embedding、rerank：均为 0；proxy violations：0。
- 原始结果的 `ownedProcessesStopped=false` 保持不变。运行结束后另行检查，目标端口 18090、19201、19202、19203、19313 无监听，也未发现本次相关 Java/Python 服务进程。后续观察不能改写原始清理字段。
- 未停止原有依赖服务，未执行第二次启动。

## 诊断投影缺陷与剩余不确定性

当前 launcher 的 `Get-FiniteHealthStatus` 只接受字符串 `Content`。纯本地模拟 HTTP 503、正文 `{"status":"DOWN"}` 的检查得到：

| Content-Type | PowerShell Content 类型 | 当前投影 |
|---|---|---|
| application/vnd.spring-boot.actuator.v3+json | System.Byte[] | unavailable |
| application/json | System.String | DOWN |

这证明健康状态投影遗漏了字节数组响应。实际运行没有保存响应 MIME 或正文，所以不能将模拟结果冒充实际响应内容的确认。

该缺陷不产生 HTTP 503，也不改变就绪判断（就绪仍要求 HTTP 200）。实际 503 对应哪个健康组件、何种内部原因，本次仍未确认；不能据此宣布 ES 索引或召回有问题。

下一步建议：最小修复有限健康状态投影，支持受限 UTF-8 字节数组并保留大小上限及状态白名单，补充真实响应形状的 non-live 回归；之后如需再次启动，应作为新的独立诊断，不能续跑本次。此处仅提出建议，没有修改源代码。

## 完整性

| 文件 | SHA-256 |
|---|---|
| build-attestation.json | 03a5cf8d39087da1815e0c6b0a93c5caa65fce0aa504d5d97daaf1dce0509e46 |
| startup-input.json | 524b06427a47da50253bfecefcd9dca9e8404f3b32c3dc09629da4d7f623f47a |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | cdabc6e3ba0b958c22c27eca6de8b00edf0e0d8c60a024727dd4464ed30186367 |

没有修改 tracked 代码、配置、权威文档或历史运行资产；本目录未提交、未推送。大型日志、响应正文、密钥、JWT 和向量均不在本诊断证据中。
