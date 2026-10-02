# 健康状态解析修复后的独立启动诊断

日期：2026-10-02。范围仅为健康状态解析修复及一次新的无付费隔离启动诊断，不执行 B 对照、正式 MEASURE 或 UAT。

## 修复与验证

- 分支：`codex_0915`；诊断 HEAD：`9c365ee2505bddff3ad5e64512c75246dff8ae28`。
- `Get-FiniteHealthStatus` 新增字节数组支持：先检查 4096 字节上限，再严格 UTF-8 解码；字符串边界、固定状态白名单和 HTTP 200 就绪条件保持不变。
- 直接相关 harness 回归：`62 passed in 39.26s`；两种 HTTP MIME、本地模拟 503、非法 UTF-8、超长内容、信息不持久化和原失败守卫均覆盖。
- PowerShell AST 检查和 `git diff --check` 通过。该验证属于定向 non-live，自审不是独立评审。
- 首次 pytest 因缺少源码 PYTHONPATH 在收集阶段失败，加入 runtime/corpus 源目录后上述回归通过。prepare 首次从仓库根目录调用找不到 tests 模块，改为 runtime 工作目录后构建成功。这两次都未进入实际启动或 ES 请求。
- prepare 使用 `-DskipTests` 构建成功，不代表 Maven 测试已执行或通过。

## 本次唯一启动终态

- 启动 ID：`codex-knowledge-measure-startup-4cd569a6f17c4e52a6b9778b7c037871`。
- `startup_preflight_failed / es_ready`；健康请求 40 次全部 HTTP 503，健康状态 40 次全部 `DOWN`，传输失败 0。
- 元数据 ES HTTP 48；typed search、外部模型、embedding、rerank 均 0；proxy violations 0；runtimeKeyRead=false。
- 未创建正式测量授权，未读取模型密钥，未执行第二次启动，没有续跑历史批次。
- 原结果的 `ownedProcessesStopped=false` 保持原样；结束后的额外观察显示目标端口 18090、19201、19202、19203、19313 无监听，相关 Java/Python 服务进程计数 0。后验检查不改写原始清理结论。

## 已定位的失败原因

运行中只读观察本次受控临时 ES 日志，提取固定布尔标记，不保存原始日志、错误全文或响应正文：

- `Elasticsearch health check failed`：存在。
- `ElasticsearchReactiveHealthIndicator`：存在。
- `Missing [X-Elastic-Product] header`：存在。
- 连接拒绝、SocketTimeout、JSON 映射异常：本次固定标记未发现；未发现不等于排除所有其他问题。

当前 `MeasureEsProxy.forward` 仅返回 HTTP 状态、Content-Type 和正文；其 Handler 仅发送 Content-Type 与 Content-Length，确实没有转发 `X-Elastic-Product`。

本地安装的 Elasticsearch Java 8.18.8 源码 `ElasticsearchTransportBase.checkProductHeader` 在 HTTP 200 时检查该头；缺失时抛出上述固定错误。Spring Boot 3.5.10 的 Reactive health indicator 使用该官方类型化客户端访问 cluster health。实际日志与代码相互印证：客户端因代理响应缺少产品标识头而拒绝健康响应，导致健康状态 DOWN、外部健康接口 503。

因此，本次已定位的是测量工具代理的 ES 协议透明性缺陷；没有证据据此认定知识正文、向量、索引 mapping 或召回设计损坏。未另行读取上游响应头，不能假称已核对真实上游 header 值。

## 最小后续修复建议（本次未实施）

只在私有测试代理中受限转发上游实际返回的 `X-Elastic-Product`；不伪造头，不关闭客户端产品校验，不关闭 Elasticsearch health，不放宽路径白名单或请求预算。补充本地 HTTP 测试，覆盖正确头、缺失头、异常头及禁止转发其他响应头。通过后，再以新的独立诊断核实启动是否就绪；不能续跑本次失败批次。

本次没有修改权威设计或计划，没有进入付费验证，没有推送或修改索引、alias。健康投影代码修复已本地提交；本次有限诊断资产单独收口。

## 原始运行产物 SHA-256

| 文件 | SHA-256 |
|---|---|
| build-attestation.json | 564eee5e9cada2778ba62e5d96b05d0168598f5049c8d1cfa55266327b918a0b |
| startup-input.json | 6afeba86f7db794b673abaee7f68434a07bf873d3314557199fd9fd09922a257 |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | 178cd2e8a03a02baa2a888164142dd9750156f27883936a47d6d6af47658fd8a |

上述运行产物从本次拥有且身份核实的临时目录复制，复制后逐文件 hash 相等；旧批次和其字节不变。
