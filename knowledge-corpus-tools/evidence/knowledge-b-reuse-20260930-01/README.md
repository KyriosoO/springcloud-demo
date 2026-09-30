# B既有候选承接：有限失败终态

本目录绑定`codex_0915`冻结提交`a6f83f7f941eedecaccb21fc8354608e0e23408c`，run为`knowledge-b-reuse-20260930-01`。终态为 **`not_assessed / runtime_provenance_missing`**，不证明召回收益、质量达标或发布准入。已消费，不补跑、不续跑、不改判。

## 实际执行与边界

- 版本化入口：`agent-runtime/scripts/run-knowledge-b-comparison-v1.ps1`，依次使用`-PrepareReuse`与一次`-ExecuteOnce`；端口19211/19212、19311/19312。
- 两臂只读全记录扫描各64次ES请求，完整竞争池各15521条；UUID、mapping、fingerprint及ID/content hash与不可变旧构建来源一致。复用已有只读候选，不重建、不重算语料向量、不写正文。
- 10题全部执行；typed search=44、query embedding=10、online rerank=22，正式元数据ES HTTP=30、临时alias写=4。预扫描128次单独分账，不混入正式比较30次。
- 付费模型、retry、resume、线上alias切换均0。模型身份前后hash均为`b8dd942d15e24c741845dd2300a6e28f8c23501ab2256a04a26c1959b7d1b9a1`。
- 后验归属准入失败，进程停止、隔离alias移除、proxy violations=0；现场核查四个隔离端口均无监听。生产alias未切换，候选保持只读未发布。
- 失败终态未保存双臂请求见证、阶段traces或准入receipt，因此不能复算排名、形成盲标池或判定实际触发的后验断言。不得从其他临时内容补造本次证明。

## 静态诊断，不是本批实际原因定论

冻结Java查询构造使用`Map.of`，独立JVM的对象键序可以不同；冻结代理对原始JSON字节取hash，而准入要求两臂hash多重集合相等。纯离线反例证明语义相同、键序不同会被错误拒绝，是可复现的内部校验缺陷。本目录缺少实际请求见证，故不能断定本次正是该断言失败。后续修复只验证新工具，不能补判本次结果。

## 索引身份

| 项目 | baseline | candidate |
|---|---|---|
| 索引 | `agent-doc-tax-policy-v5-20260907-vector-b2` | `agent-doc-tax-policy-v6-20260930-body-b1` |
| UUID | `jJ5Ww3LCRWWycfDkUZvmdw` | `g4eIYXTkQQik49TaOqJZ6A` |
| 全记录fingerprint | `fb285fc5e5e838fbccb2025f24c0f4472802b8beb7190247cefc9a2978b9a17d` | `e9ccca316b295fa8ca258034dd8fd625517586c3b462ba5274d5d44e98f51691` |

旧构建来源为提交`c9b8642e9c20765814df4b3422cfa958a2c4900c`下`knowledge-corpus-tools/evidence/knowledge-b-body-20260930-01`；逐文件hash见`reuse-intent.json`。两份新ID映射与旧Git对应blob字节一致，仅保存身份和hash，不保存正文或向量。

## 有限资产SHA-256

| 文件 | SHA-256 |
|---|---|
| candidate-id-mapping.json | `3930b68b10adc1a367190b2b4562c650e091a693b049b301553bab57f9c22350` |
| candidate-scan-result.json | `f538bd4f31c03680f2a79dda90b1b1f33bb6bc7fc5cf7eb16513e9597aebda10` |
| comparison-attempt.json | `1e203517d76f3848dada633b3312f6ebf9748c8905f70e109dfbb98d875acb52` |
| comparison-java-attestation.json | `edfeec5d0ce1a952f625712b85b6c38914cdb342a06fc00f86e7f5a8c5f61507` |
| comparison-result.json | `e3a93577be0649c1e85db9746a74c2f97f7029cfd272379a7d0a76bf8194c536` |
| reuse-final.json | `81a71063321045f5dbb7ebf8a2de7856687b56ff2129ca635f8f5463e5587061` |
| reuse-intent.json | `c4bda9d5e36f3558e6b68d7db8e42d2c6bd3de91cba75aa0ce97b7cdd29069de` |
| reuse-scan-attempt.json | `3bd7e08ab3d0d77e4f6206ef22c9f3c32ae39fe319d806e83ade96e45a9c1943` |
| reuse-scan-terminal.json | `8e020507f695d723f6e4fe9a1fefdacc5d4afe3d113eaa72ddc5e2079d7c876d` |
| source-id-mapping.json | `e2178b1ee9f13ce840e1a1b878cc7778e554ab1319eecb7e73b0ed1baa5a6f96` |
| source-scan-result.json | `d603059015efb3c5db6b7c2107b60f46ed96d6bf670943fbafddf239e6d87ffc` |

以上11份运行资产原字节保留。本文为执行后交接说明，不是补造的运行见证或重新授权。
