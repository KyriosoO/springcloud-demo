# 代码评审报告

## 1. 执行摘要

| 项目 | 内容 |
|---|---|
| 评审模式 | review_and_fix（批量模式，第 14/15 份，严格串行） |
| 最大循环次数 | 5 |
| 实际执行轮次 | 4 |
| 评审代码范围 | `agent-adapter-api` Provider typed contract；`agent-service` 四类 LocalPort、outbound policy、binding/deadline/cancel/wire client；`document-provider-adapter` 固定端点、激活、重放防护、输入/输出边界；配置与相关测试 |
| 是否修改代码 | 是 |
| 验证结果 | 定向 17 tests 与 11 模块 reactor 通过；`agent-service` 479 tests、`agent-api` 47 tests；静态边界检查通过 |
| 最终结论 | 有条件通过；当前 in-repo strict wire、typed binding、0/1 attempt、大小/时限边界和故障分类已闭合，真实 Provider 与在途取消仍是生产门禁 |

## 2. 文档依据清单

| 文档 | 角色 | 优先级 | 读取结果 | 备注 |
|---|---|---:|---|---|
| `06_文档CapabilityLocalProvider端口_L2实施详细设计_v3.0.md` | detailed_design | 0 | 已完整读取 | 当前主文档 |
| P2_V3 `00`～`05`、`07` 及 P1_V2 相关设计 | related_design | 1 | 已读取相关边界 | typed budget、ACL/evidence、LocalPort、currentness、发布回滚 |
| `../Agent契约与规划架构设计_v1.0.md`、`../Agent能力执行内核架构设计_v1.0.md`、`../Agent元数据与上下文安全架构设计_v1.0.md` | architecture | 2 | 已读取相关约束 | typed contract、单 Handler、本地策略决定、Result Security |
| `../Agent目标架构总览_v1.0.md` | architecture | 3 | 已读取相关约束 | Agent 内核边界、Adapter 隔离与最小出站 |

## 3. 文档约束追踪

| 约束编号 | 约束内容 | 对应代码位置 | 评审结果 |
|---|---|---|---|
| DOC-C-001 | rewrite/embedding/rerank/generation 仅经四个 fixed endpoint 和唯一 Adapter Client，0/1 attempt、无 retry/fallback | `DocumentProviderAdapterClient`、`DocumentProviderController` | 符合 |
| DOC-C-002 | 出站必须绑定 operation、deadline、activation、provider、policy 与 typed input，响应按同一绑定复核 | binder/reference verifier、wire request/response、activation snapshot | 修复后符合 |
| DOC-C-003 | wire payload 必须 typed，language/embedding binding 不得为自由字符串或不受信 sidecar | `DocumentLanguage`、`DocumentEmbeddingBindingReference`、Provider DTO | 修复后符合 |
| DOC-C-004 | deadline/cancel、请求/响应字节、items/text/dimension 等边界在调用前后 fail closed | agent client、request size filter、operation service/properties | 修复后符合；在途主动 abort 见剩余风险 |
| DOC-C-005 | 仅 strict generation success 可发布供结果链消费的 Provider binding | `DocumentProviderOperationBindingRegistry`、generation response validation | 修复后符合 |

## 4. 代码问题清单

| 编号 | 级别 | 类型 | 文件 | 问题描述 | 影响 | 处理结果 |
|---|---|---|---|---|---|---|
| CR-001 | high | contract_drift | `DocumentRewriteInputProjection`、`DocumentUntrustedEmbeddingPayload` | language 与 embedding binding 使用自由字符串，且未证明 embedding binding 属于当前激活 Provider | 非法语言或伪造模型绑定可穿过 typed 边界 | 新增 `DocumentLanguage`；embedding payload 改用 typed binding，并校验 dimension 与 active template/model digest |
| CR-002 | high | trust_publication | `DocumentProviderAdapterClient` | 通用 invoke 成功即发布 operation binding，rewrite/embedding/rerank 或 generation 后置校验失败也可留下可信 sidecar | 无效或错误 operation 可能被后续 Result Security 当作可信 generation binding | 取消通用发布，仅在 generation strict payload 全部校验成功后发布；增加失败不发布回归用例 |
| CR-003 | high | resource_limit_bypass | agent client、Adapter properties/service/filter | agent 未限制序列化请求/响应字节；Adapter 未在反序列化前限制原始请求体，也缺少 items/text/dimension/deadline horizon operational cap | 大包、深层 JSON 或超范围 typed payload 可造成资源耗尽，恶意内部调用可绕过 agent 侧限制 | agent 增加 request/response byte cap、stream constraints；Adapter 增加 Content-Length 前置门禁与 operation-specific caps |
| CR-004 | high | deadline_boundary | `DocumentProviderAdapterClient`、`DocumentProviderOperationService` | 剩余 deadline 可能短于固定 connect+read 上限，Adapter 也接受任意远期 deadline | 调用可在 Invocation deadline 后仍占用连接/Provider 资源 | agent 在剩余时间不足完整交换上限时 0-attempt 拒绝；Adapter 限制 stage horizon，调用前后复核 deadline |
| CR-005 | high | failure_semantics | `DocumentProviderAdapterClient` | 所有 `RestClientException` 都映射为 `PROVIDER_FAILED`，连接不可达和传输超时无法区分 | fallback/audit/告警基于错误 failure code 做出错误判断 | `ResourceAccessException` 单独分类为 `PROVIDER_TIMEOUT` 或 `PROVIDER_UNAVAILABLE`，并保持 cancel/deadline 后置优先级 |
| CR-006 | medium | replay_key_collision | `DocumentProviderReplayGuard` | 重放键使用分隔符字符串拼接 | 输入包含分隔符时存在不同 tuple 合并为同一 key 的风险 | 改为 typed `ReplayKey` record |
| CR-007 | medium | invalid_vendor_response | `DocumentProviderOperationService` | vendor 的 `IllegalArgumentException` 被通用 runtime 捕获并归为失败，且 embedding 输出 binding 未与 active provider digest 闭合 | 非法 Provider payload 的审计分类不准确，错误绑定可能返回 agent | 单独映射 `VENDOR_INVALID_RESPONSE`；四类 payload 增加严格结构/数量/绑定校验 |

## 5. 文档问题清单

| 编号 | 级别 | 文档位置 | 问题类型 | 问题描述 | 影响 | 建议 |
|---|---|---|---|---|---|---|
| DOC-001 | medium | 8.4 rerank contract | implementation_contract_drift | 文档定义 rerank item 含 `fields` 与 typed scalars，当前 DTO 仅含 `candidateId/title/snippet`，且现有上游没有可证明的 scalar 权威来源 | 真实 Provider 若按文档实现完整 fields contract，会与当前 wire 不兼容 | 先在关联 Profile/field-view 文档明确 scalar 来源和 allowlist，再授权同步扩展 DTO、投影与 contract tests |
| DOC-002 | medium | 13、18、20 节 | completion_state_conflict | 文档状态写“已实现”，但同文档又将真实 vendor、断连/超时/在途 cancel 与 fault injection 列为生产阻断项 | 容易把 in-repo contract 完成误判为 production ready | 授权后将状态拆为 contract implemented / production blocked，并列明启用前证据 |
| DOC-003 | low | 19.3、20.4 节 | acceptance_command_drift | 推荐命令从仓库根引用不存在的 `./mvnw.cmd`，且 module selector 未使用 reactor artifactId 形式 | 验收命令不能原样复现 | 授权后统一为在 `serviceCenter` 执行 `./mvnw.cmd -pl :artifactId ...` 或显式 `-f` |

## 6. 修改摘要

| 轮次 | 修改范围 | 修改内容 | 对应问题 | 结果 |
|---:|---|---|---|---|
| 1 | Provider typed contract | language enum、typed embedding binding、active digest/dimension 复核 | CR-001 | contract tests 通过 |
| 2 | Agent wire/binding | request/response bytes、strict parser、deadline fail-closed、仅 generation strict success 发布 binding | CR-002、CR-003、CR-004 | 定向 client/handler tests 通过 |
| 3 | Adapter operation boundary | horizon、items/text/total/dimension/payload cap，vendor invalid response 分类，typed replay key | CR-003、CR-004、CR-006、CR-007 | Adapter service 6 tests 通过 |
| 4 | 原始 HTTP 与传输异常 | 反序列化前 request size filter；timeout/unavailable 精确分类及回归测试 | CR-003、CR-005 | 定向 17 tests 与全 reactor 通过 |

## 7. 验证结果

| 轮次 | 命令 | 结果 | 摘要 |
|---:|---|---|---|
| 1～4 | `serviceCenter/mvnw.cmd -pl :agent-adapter-api,:agent-service,:document-provider-adapter -am -Dtest=DocumentProviderContractValidationTest,DocumentProviderOutboundPolicyReferenceVerifierTest,DocumentProviderOperationServiceTest,DocumentProviderRequestSizeFilterTest,DocumentProviderAdapterClientTest,DocumentCapabilityHandlerTest -Dsurefire.failIfNoSpecifiedTests=false test` | 通过 | 17 tests；typed contract、binding、byte/deadline、transport classification、Adapter operational cap |
| 4 | `serviceCenter/mvnw.cmd -pl :agent-adapter-api,:agent-service,:document-provider-adapter -am test` | 通过 | 11 模块 SUCCESS；`agent-service` 479 tests、`agent-api` 47 tests、`agent-adapter-api` 11 tests |
| 4 | runtime rewrite / embedding fallback / generation repair、旧 endpoint、Provider wire Map/JsonNode/raw generic 静态扫描 | 通过 | legacy runtime/fallback/repair 与旧 endpoint 零命中；命中的 `Object` 仅用于内部 canonical digest/operation-specific validator，不是 wire payload |
| 4 | `git diff --check -- agent-adapter-api agent-service document-provider-adapter config-service` | 通过 | 无空白错误；仅仓库既有 CRLF/LF 提示 |

## 8. 剩余风险

| 编号 | 级别 | 风险 | 触发场景 | 后续建议 |
|---|---|---|---|---|
| RISK-001 | high | 当前同步 `RestClient` 只能在调用前后观测 cancel/deadline，不能证明在途取消信号会立即 abort socket/vendor 请求；每请求动态 timeout 也仅以固定 connect+read 上限 fail closed 近似 | 用户在慢 Provider 调用过程中取消，或 deadline 在请求在途时到期 | 生产启用前选定支持 cancellation/abort 的真实 transport/vendor client，增加断连、读超时、cancel 与 late-result fault injection |
| RISK-002 | high | 仓库仍使用 `UnavailableDocumentVendorClient`，没有真实 rewrite/embedding/rerank/generation vendor wire 与 deployment 验证 | 打开任一真实 Provider activation | 保持默认禁用；在 07 发布门禁补齐真实 vendor contract、错误 payload、超时、回滚证据后再启用 |
| RISK-003 | medium | request size filter 对 Provider endpoint 拒绝 chunked/未知 Content-Length；这是安全收紧但会影响不发送 Content-Length 的合法调用方 | 新增非当前 agent client 的内部调用方使用 chunked body | 将“必须提供 bounded Content-Length”写入内部调用契约并加入兼容性测试，或引入真正的流式计数 wrapper |
| RISK-004 | low | Mockito/ByteBuddy 动态 agent 在未来 JDK 将默认禁止 | 升级到禁止 dynamic agent loading 的 JDK | 后续在测试构建中按 Mockito 建议显式配置 javaagent |

## 9. 结论

- 有条件通过。
- 7 项代码问题均已修复；typed wire、operation/provider binding、0/1 attempt、字节/时限/激活边界、失败分类与 Adapter operational defense 已通过定向和 reactor 验证。
- 真实 Provider、在途取消/动态 timeout 与完整 rerank fields contract 仍未闭合；在这些生产门禁完成前不得将“contract implemented”解释为“production ready”。
- 未修改主文档、关联文档或 L0/L1 架构文档；未执行生产发布、提交、推送或远端操作。
