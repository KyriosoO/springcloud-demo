# Agent 架构设计文档 v1.6 修订补丁

> 适用文件：`docs/design/agent架构设计文档_v1.5.md`  
> 目的：依据当前仓库实现边界与人工确认意见，对架构文档中容易产生歧义或与业务实现不一致的部分进行定向修订。  
> 说明：本文件为补丁式修订说明，避免在未全量重排原长文档前误删既有详细设计内容。

---

## 1. Gateway 路由说明修订

原文中关于 `/agent/**` 的描述保留，但应明确：

```text
/agent/** 路由由 gateway-service 的 Java 路由配置类 GatewayRouter 维护；
application.yml 中仅保留 discovery locator 等通用配置，不以 YAML routes 作为 Agent 路由唯一事实源。
```

建议替换 2.2 调用关系后的说明为：

```text
说明：gateway-service 对 `/agent/**` 的转发以 Java 配置类 GatewayRouter 为准；
若 application.yml 中未出现显式 routes，不代表 `/agent/**` 未配置。
GatewayRouter 应将 `/agent/**` 转发至 `lb://agent-service` 或等价目标，并保留 JWT/Cookie 认证信息透传。
```

---

## 2. DIRECT_UPDATE 边界修订

保留 `DIRECT_UPDATE`，但补充边界：

```text
Agent 只定义执行模式与 Adapter 能力契约，不管理业务域内部如何实现 update。
某个业务域是否在 update 内部创建变更申请、走本地审批、调用 workflow 或同步落库，属于业务域自治范围。

但从 Agent 视角，只有 Adapter 确认其调用的目标入口具备“同步 update 语义”时，才可将该能力声明为 DIRECT_UPDATE。
如果目标入口只是受理请求、返回申请号、返回流程号或异步提交号，Adapter 必须通过 AgentExecutionResult.status
明确返回 SUBMITTED / PENDING_APPROVAL，不得向用户表达为已完成修改。
```

建议将 `ExecutionMode.DIRECT_UPDATE` 说明改为：

```text
DIRECT_UPDATE：调用业务域 Adapter 暴露的同步 update 能力。Agent 不关心业务域内部实现方式，
但 Adapter 必须保证该入口对 Agent 呈现的是同步 update 语义；如业务域仅返回受理号、申请号或流程号，
应返回对应 ExecutionStatus，不得误报为 SUCCEEDED。
```

---

## 3. EmployeeAgentFeignClient 补齐 operator 参数

原文：

```java
@PutMapping("/employees/{idCardNo}")
Object update(@PathVariable String idCardNo, @RequestBody Object request);

@PostMapping("/employees")
Object create(@RequestBody Object request);
```

应改为：

```java
@PutMapping("/employees/{idCardNo}")
Object update(@PathVariable String idCardNo,
              @RequestBody Object request,
              @RequestParam("operator") String operator);

@PostMapping("/employees")
Object create(@RequestBody Object request,
              @RequestParam("operator") String operator);
```

补充说明：

```text
operator 必须由 AgentUserContext.userId 注入，Python 不输出 operator，用户文本中的操作者描述不得覆盖当前登录用户。
```

---

## 4. employee 字段必须与业务域模型对齐

删除文档示例中的 `name` 字段，改为业务域真实模型字段 `chineseName`。

建议 employee 字段示例改为：

```yaml
fields:
  chineseName:
    show: true
    queryable: true
    writable: false
    exportable: true
    masked: false
    risk-level: LOW
    allowed-operators: [EQ, CONTAINS]

  position:
    show: true
    queryable: true
    writable: true
    exportable: true
    masked: false
    direct-update-allowed: false
    workflow-required: true
    risk-level: MEDIUM
    max-affected: 20
    allowed-actions: [SET, CLEAR]
    allowed-operators: [EQ, CONTAINS, IN]

  idCardNo:
    show: false
    queryable: true
    writable: false
    exportable: false
    masked: true
    mask-type: ID_CARD
    risk-level: HIGH
    allowed-operators: [EQ]
```

补充原则：

```text
Agent 字段名必须与业务域模型或业务域对 Agent 暴露的契约字段对齐。
文档不引入通用字段映射层，不在 Python 侧维护字段映射。
如果业务域需要字段别名、ES 字段名、数据库列名映射，应由业务域 Adapter 或业务服务内部自行处理。
```

---

## 5. 聚合权限修订

不新增 `FieldUsage.AGGREGATE_GROUP / AGGREGATE_METRIC`，P0 阶段聚合权限与查询权限复用。

但需补充规则：

```text
聚合 filters 使用 QUERY 权限校验。
groupBy 字段会作为聚合 bucket key 返回给用户，因此不能完全不控制；P0 要求 groupBy 字段必须 queryable=true 且 show=true。
metric 字段会以聚合值形式返回；P0 可复用 queryable=true 作为是否允许参与聚合指标计算的准入条件。
如后续需要区分“可查询条件”和“可聚合指标”，再引入 aggregatable 或 FieldUsage.AGGREGATE。
```

对应 transaction 配置示例建议改为：

```yaml
transaction:
  enabled: true
  display-name: 交易域
  roles:
    agent:viewer:
      allow-intents: [QUERY, AGGREGATE, EXPORT, SUMMARY]
    agent:admin:
      allow-intents: [QUERY, UPDATE, AGGREGATE, EXPORT, BUSINESS_SUBMIT, SUMMARY]

  fields:
    transId:
      show: true
      queryable: true
      writable: false
      exportable: true
      risk-level: LOW
      allowed-operators: [EQ, IN]

    transType:
      show: true
      queryable: true
      writable: true
      exportable: true
      direct-update-allowed: true
      risk-level: MEDIUM
      allowed-actions: [SET]
      allowed-operators: [EQ, IN]

    transDate:
      show: true
      queryable: true
      writable: false
      exportable: true
      risk-level: LOW
      allowed-operators: [EQ, GTE, LTE, BETWEEN]

    amount:
      show: true
      queryable: true
      writable: false
      exportable: true
      masked: true
      mask-type: AMOUNT
      risk-level: HIGH
      allowed-operators: [EQ, GTE, LTE, BETWEEN]
```

---

## 6. AgentPlan 与分页边界修订

不在 `AgentPlan` 顶层新增 `page/from/size/sort` 字段。

补充说明：

```text
AgentPlan 是自然语言目标计划，不直接等同于下游查询请求 DTO。
分页、默认 size、最大 size、下一页 offset、排序等属于查询执行选项，由 Java 编排层、MemoryContext、领域 Adapter 或 PlanMapper 在转成业务查询请求时处理。

P0 中：
1. AgentQueryResult 保留 offset、size、hasMore。
2. MemoryService 保存上一轮查询 offset、size、hasMore 与原始查询条件。
3. 用户表达“下一页”“后 10 条”时，Python 可生成 useLastResult=true 或 targetType=LAST_RESULT 的计划；Java 根据上一轮结构化查询上下文计算下一次查询参数。
4. 如确需承载用户显式页码，可暂放入 AgentPlan.context.queryOptions，不提升为 AgentPlan 顶层强类型字段。
```

---

## 7. roles 配置绑定结构修订

采用方案 A，去掉 `AgentRoleProperties` 包装，直接使用：

```java
public class AgentDomainProperties {
    private Boolean enabled;
    private String displayName;
    private Map<String, AgentFieldProperties> fields;
    private AgentRiskProperties risk;
    private Map<String, RolePolicyProperties> roles;
    private Map<AgentWorkflowAction, WorkflowActionProperties> workflowActions;
}
```

删除或不再使用：

```java
public class AgentRoleProperties {
    private Map<String, RolePolicyProperties> policies;
}
```

YAML 保持当前结构：

```yaml
roles:
  agent:viewer:
    allow-intents: [QUERY, AGGREGATE, EXPORT, SUMMARY]
  agent:admin:
    allow-intents: [QUERY, UPDATE, AGGREGATE, EXPORT, BUSINESS_SUBMIT, SUMMARY]
    max-update-affected: 20
```

---

## 8. 查询结果归一化边界修订

不在 Agent 核心层新增 `EmployeeSearchResultMapper`。

补充说明：

```text
Agent 核心只要求 QueryableAdapter.query() 返回 AgentQueryResult。
下游 employee-service、es-query-service 或 transaction-service 返回何种 DTO/JSON，属于业务域 Adapter 的适配职责。

因此，结果归一化应放在 adapter.employee / adapter.transaction 包内，作为 Adapter 私有实现细节；
不得在 agent-core 中出现 EmployeeSearchResultMapper 这类绑定具体业务域的组件。
```

建议在 `EmployeeAgentAdapter.query()` 说明中补充：

```text
如果 employee-service 返回 ES 原始 JSON 字符串，EmployeeAgentAdapter 在 adapter.employee 内部完成最小归一化，提取 rows、total、offset、size、hasMore，并返回 AgentQueryResult。
该转换属于 Adapter 边界适配，不属于 Agent 核心业务侵入。
```

---

## 9. transaction 聚合 metrics 清洗逻辑位置

清洗逻辑放在 `TransactionPlanMapper.toAggregateRequest()`。

补充说明：

```text
AgentPlan 中的 aggregate.metrics 使用强类型 AgentMetric；
transaction 现有 AggregateRequest.metrics 使用字符串格式，例如 SUM:amount、AVG:amount、COUNT。

二者之间的转换属于 transaction Adapter 对下游接口的适配逻辑，应在 TransactionPlanMapper.toAggregateRequest() 中完成，
不放在 Python，不放在 Agent 核心校验层，也不要求 mq-procedure-service 理解 AgentMetric。
```

建议补充转换规则：

```java
private String toMetricString(AgentMetric metric) {
    String function = metric.getFunction().toUpperCase(Locale.ROOT);
    if ("COUNT".equals(function)) {
        return "COUNT";
    }
    return function + ":" + metric.getField();
}
```

同时补充校验规则：

```text
PlanValidationService / FieldPolicyEvaluator 负责校验 metric.function 是否属于允许集合，metric.field 是否是当前 domain 已配置字段。
TransactionPlanMapper 只做格式清洗和适配；如遇到非法 function 或缺失 field，应抛出 AdapterRequestMappingException 或等价异常。
```

---

## 10. 文档版本修订

建议将原文件重命名为：

```text
docs/design/agent架构设计文档_v1.6.md
```

正文头部保留：

```text
目标版本：P0 设计版 v1.6
```

删除或改写原文中的：

```text
文件名保留历史版本号，正文目标版本以本行声明为准。
```

改为：

```text
文件名、正文目标版本和修订说明必须保持一致。
```
