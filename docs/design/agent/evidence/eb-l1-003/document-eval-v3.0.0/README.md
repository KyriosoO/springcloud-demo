# DOCUMENT 固定评价包 v3.0.0-synthetic

## 1. 基线信息

| 项目 | 内容 |
|---|---|
| 评价包 ID | `EB-L1-003-DOCUMENT-EVAL` |
| 数据集版本 | `3.0.0-synthetic` |
| 报告格式版本 | `3.0.0` |
| 来源版本 | `2.0.0-synthetic`；内容样例经权限语义归一化并扩充候选池 |
| 冻结日期 | 2026-07-17 |
| 基线状态 | `frozen_for_architecture_review` |
| 数据性质 | 100% 人工模拟；不含真实个人数据、客户数据、订单、交易或内部制度原文 |
| 生产验收状态 | 未批准；实际目标制品跑分和生产阈值验收仍由 DOCUMENT L2 承接 |

## 2. RET-O-09 对齐范围

本版本用于关闭 `RET-O-09` 中“形成固定评价包”的前置项：

1. 全部语料归入唯一逻辑语料库 `document-default`，统一为 `internal` 安全等级。
2. 删除文档级 `allowed_roles`，首期不启用文档级 ACL。
3. 冻结 Java Agent 组合 RBAC、DOCUMENT 能力和 `DOCUMENT_CORPUS_READ` 语料库权限后的最终访问输入；检索评价只执行该决定，不推断角色关系。
4. 增加 RBAC 拒绝、DOCUMENT 能力拒绝、语料库权限缺失、语料库停用、访问撤销、围栏未收敛和策略版本不一致的失败关闭案例。
5. 无权限类案例的有效候选池必须为0，任何候选进入检索结果或模型输入均形成安全事件。
6. 每个 Recall@50 计分案例的有效候选池均大于50，且至少包含50个非相关干扰项。

本包不等于目标系统已经实跑，也不关闭 `RET-O-09` 的“系统质量放行前完成实跑”后置项。

## 3. 权限与围栏模型

评价案例通过 `subject` 和 `access_context` 冻结最终执行输入：

- `rbac_authorized`：授权域给出的 RBAC 上界是否允许；
- `document_capability_authorized`：Agent 的 DOCUMENT 能力是否允许；
- `corpus_permissions`：最终有效语料库权限码集合；
- `corpus_permission_state`：语料库权限是否已撤销；
- `corpus_enabled`：语料库是否启用；
- `required_policy_version` / `observed_policy_version`：权限策略版本一致性；
- `required_fence_version` / `observed_fence_version`：撤权/停用围栏可见性。

任一上界拒绝、权限码缺失、权限已撤销、语料库停用、策略版本不一致或围栏未收敛时，检索必须在候选产生前失败关闭。

## 4. 文件清单

| 文件 | 用途 |
|---|---|
| `manifest.json` | 版本、单语料库权限基线、数量和门禁 |
| `corpus.jsonl` | 114个固定语料块，其中54个为候选池干扰项 |
| `evaluation_cases.jsonl` | 30个问题、qrel、答案、引用及权限/围栏案例 |
| `metric_spec.md` | 9项质量指标、候选池和失败关闭规则 |
| `report_schema.json` | 3.0.0 报告 Schema |
| `validate_evaluation_report.py` | 包语义、报告重算和安全事件验证器 |
| `self_test.py` | 构造 Oracle 报告并验证防伪和泄漏拒绝能力 |
| `derive_v3_dataset.py` | 从 v2 确定性派生 v3 数据的溯源工具 |
| `validation_report.json` | 包完整性及验证器自测结果；不代表系统跑分 |
| `CHANGELOG.md` | 版本变更历史 |
| `SHA256SUMS` | 冻结文件的 SHA-256 校验值 |

## 5. 验证命令

```powershell
python validate_evaluation_report.py --check-pack
python self_test.py
python validate_evaluation_report.py --report <evaluation-report.json>
```

第一条命令验证固定包、单语料库权限语义、候选池和哈希；第二条命令验证实际运行报告。退出码0表示通过，退出码1表示无效。

## 6. 使用约束

1. 运行报告必须记录数据集、报告 Schema、被测制品、模型及检索配置版本。
2. 权限和围栏必须在产生检索候选及模型输入前执行，禁止召回后删除越权结果来掩盖泄漏。
3. 参考答案不得拼入被测模型 Prompt。
4. 所有9项质量门禁逐项判定，禁止以加权总分抵消。
5. 冻结目录禁止原地修改；后续语义变化必须创建新版本目录。
6. `derive_v3_dataset.py` 仅用于溯源；运行后必须重新评审并刷新 `SHA256SUMS`，不能把重新生成结果自动视为已冻结版本。

## 7. 版本规则

- 错别字且不改变语义、Schema或标注：递增 PATCH。
- 新增兼容样本、语料或可选诊断字段：递增 MINOR。
- 修改指标、权限、既有标注，或对报告生产者引入不兼容要求：递增 MAJOR。

## 8. 责任与复核

评价包由 Dylan 管理。业务/产品负责参考答案与必要要点，检索负责相关性等级，安全负责权限、围栏和泄漏标注，AI负责答案与引用判定。验证器只能证明报告与冻结契约一致，不能声明目标系统达到生产质量。
