# B 独立启动预检（2026-09-30）

本目录只记录一次无推理启动预检，不是 B 质量对照，不复用或改判旧失败 run。

- run：`knowledge-b-startup-20260930-01`
- frozen HEAD：`4b540e5b48bdc39e7ef1d571880cfde31d366675`
- 结果：`ready`；两个自有 Java 进程已停止，四个目标端口无监听，临时只读 alias 已移除。
- ES 元数据 HTTP：30/30；临时 alias 写操作：4/4；两臂就绪请求：5、1（各上限60）。生产 alias 未切换。
- typed search、physical search、query embedding、rerank、paid、JWT HTTP、retry、resume：均0；proxy violations：0。
- 仅使用冻结 Git 来源和离线构建；不读取 `LLM_API_KEY`。不能据此宣布 UAT、召回、回答或发布通过。

复核命令：

```powershell
Get-FileHash -Algorithm SHA256 D:/codex/knowledge-corpus-tools/evidence/knowledge-b-startup-20260930-01/*.json
```

| 文件 | SHA-256 |
|---|---|
| startup-input.json | d338c5a7139799da5f492b81b12482f07f15f8a861b15c1e83bf87e264c4a77d |
| startup-attempt.json | c78da28e1a2c218f0d2d1be57eb31926870054782e65cc8ed200def781fea044 |
| startup-java-attestation.json | 2b35ed19a55d0058d60fc3052e4c2ef174e48e90b02571beb35bcd12aa1bcdc8 |
| startup-result.json | acd1512ef4989951f8442c6189dd4b4553f40e77703649b8cff91742537a3008 |
