# 无控制台 Python 启动修复与通过的独立启动预检

日期：2026-10-03。范围仅为私有 launcher 修复、直接验证及一次新的无付费启动预检；不执行 B、MEASURE、效果 UAT 或发布。

## 根因和修复

前一轮原始结果记录 proxy 的直属 console_host 子进程因 executable_mismatch 导致清理失败，旧结果保持不变。本轮纯本地测试进一步证实：当前 Windows 虚拟环境的 python.exe 即使通过 CreateNoWindow 启动，仍会出现 conhost 子进程，因此未采用该失败方案，不删除相关断言。

最终使用同一虚拟环境 `.venv/Scripts/pythonw.exe` 启动 proxy 和预检 Runtime，并严格绑定 pyvenv.cfg 所指基础 Python 目录中的 pythonw.exe。启动使用 ProcessStartInfo、CreateNoWindow、UseShellExecute=false 和逐项 ArgumentList，不经 shell 拼接参数。

- 保留现有角色、模块参数、工作目录和虚拟环境隔离，子进程 LLM_API_KEY 为空。
- 两路输出异步直接写入本次临时日志；清理等待各排空任务最多5秒并关闭流。排空失败形成固定原因并保持清理失败，不忽略日志或吞掉失败。
- 子进程身份、PID/创建时间、监听归属、未知进程拒绝、Kill 范围、超时和失败关闭保持原约束；没有按 conhost 名称放行。
- Windows 环境需具备同一虚拟环境及基础安装的 pythonw.exe；缺少时在启动前失败关闭，不回退到已知有控制台问题的方式。
- 不修改生产 Query、公共合同、角色、索引、alias、知识正文或主目标状态。

## 实际验证

- 分支 `codex_0915`，起始工作树干净；修复提交 `2c2d468173101a41206eeb5f7a54bd2e4ed52db2`。
- 命令：在明确当前源码 PYTHONPATH 的隔离环境中运行 `python -m pytest tests/uat/test_knowledge_rebuild_measure_harness.py -q --tb=short`，结果 `93 passed in 70.43s`。
- 新成功反例覆盖无控制台、proxy/runtime两角色、带空格及中文参数、真实虚拟环境 prefix、合成密钥未继承、各256KiB stdout/stderr、子进程身份核实及重复清理。
- 日志排空任务故障测试继续失败关闭，并核实流关闭；原有身份、安全、产品头、健康解析及预算反例均通过。
- strict mypy 1文件、compileall、PowerShell AST、diff及暂存差异检查通过。这是定向验证及作者自审，不是独立评审或全量 Python/Maven 回归。
- 用版本化 prepare build 对上述干净 HEAD 生成新构建证明；构建使用 `-DskipTests`，不代表 Maven 测试通过。

## 本次唯一预检终态

- 启动 ID：`codex-knowledge-measure-startup-fb6c9c03f0e74f6a958c5180714b3a10`。
- 原始终态 `startup_preflight_passed`，exitCode=0，stage=complete，`ownedProcessesStopped=true`。
- `metadataEsHttp=9`：派生启动绑定2次、Profile6次、健康1次，未超过48次独立启动上限。
- typed search、模型、embedding、rerank及outboundViolations均为0；loginRequests=1，`runtimeKeyRead=false`。
- Runtime正常关闭marker、清理、日志敏感检查及冻结资产检查通过。结束后只读检查18090、19201、19202、19203、19313无监听。
- 未读取真实模型密钥，没有自动重试、恢复旧批次、执行题目、正式冻结或改变旧失败终态。

通过仅证明当前修复组合的启动、绑定和清理生命周期可用，不证明召回、回答、真实UAT或发布达标。主目标后续仍需根据其授权和冻结规则独立推进 B 与 MEASURE，本旁路诊断不自动执行这些步骤。

## 有限原始资产完整性

| 文件 | SHA-256 |
|---|---|
| build-attestation.json | 1fe8457c9747d7cc3062fac6f579e7b40717fa902d6d8c1284d55ee4fbedf114 |
| startup-input.json | 03fd81d2301138e81588e86de82793cfe365b6086fdfd34bbe3dcce52767f989 |
| startup-metadata-attempts.jsonl | 9478b53494661056bf9bc054684b09b9c6cf9314586b676b0fb0cf1f058e6008 |
| startup-result.json | a76330cbad472fcae6377bd5c0288d9da52e9208ba5e50da3e6e6fddcb6e72c6 |

输入、attempt和结果从本次明确身份的临时目录复制，逐文件hash相等。未提交日志、密钥、JWT、正文、向量或模型响应；历史证据未修改。只作本地提交，不推送。
