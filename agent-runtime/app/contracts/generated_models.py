# Auto-generated from agent-api OpenAPI spec. DO NOT EDIT.
# Source: agent-api/src/main/resources/openapi/agent-runtime-openapi.json
# Regenerate: cd agent-runtime && python scripts/generate_contract_models.py

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, conint, constr

class AgentCapabilityExecutionMode(str, Enum):
    """
    Capability 执行模式
    """

    immediate = 'IMMEDIATE'

class AgentIntent(str, Enum):
    """
    Agent 顶层意图：QUERY（查询）、CLARIFY（反问澄清）、AGGREGATE（聚合分析）
    """

    query = 'QUERY'
    QUERY = query  # noqa: E221
    clarify = 'CLARIFY'
    CLARIFY = clarify  # noqa: E221
    aggregate = 'AGGREGATE'
    AGGREGATE = aggregate  # noqa: E221

class AgentCapabilityRiskLevel(str, Enum):
    """
    Capability 风险等级
    """

    read_only = 'READ_ONLY'

class AgentErrorCode(str, Enum):
    """
    Agent 统一错误码
    """

    agent_invalid_request = 'AGENT_INVALID_REQUEST'
    agent_conversation_not_found = 'AGENT_CONVERSATION_NOT_FOUND'
    agent_intent_forbidden = 'AGENT_INTENT_FORBIDDEN'
    agent_field_forbidden = 'AGENT_FIELD_FORBIDDEN'
    agent_operator_forbidden = 'AGENT_OPERATOR_FORBIDDEN'
    agent_plan_invalid = 'AGENT_PLAN_INVALID'
    agent_runtime_unavailable = 'AGENT_RUNTIME_UNAVAILABLE'
    agent_query_failed = 'AGENT_QUERY_FAILED'
    agent_internal_error = 'AGENT_INTERNAL_ERROR'

class AgentFieldType(str, Enum):
    """
    字段数据类型：STRING（字符串）、DECIMAL（数值）、INSTANT（时间戳）
    """

    string = 'STRING'
    STRING = string  # noqa: E221
    decimal = 'DECIMAL'
    DECIMAL = decimal  # noqa: E221
    instant = 'INSTANT'
    INSTANT = instant  # noqa: E221

class AgentOperator(str, Enum):
    """
    查询操作符：EQ/CONTAINS/STARTS_WITH（单值）、IN/CONTAINS_ANY/STARTS_WITH_ANY（多值）、GT/LT（范围）
    """

    eq = 'EQ'
    EQ = eq  # noqa: E221
    contains = 'CONTAINS'
    CONTAINS = contains  # noqa: E221
    contains_any = 'CONTAINS_ANY'
    CONTAINS_ANY = contains_any  # noqa: E221
    starts_with = 'STARTS_WITH'
    STARTS_WITH = starts_with  # noqa: E221
    starts_with_any = 'STARTS_WITH_ANY'
    STARTS_WITH_ANY = starts_with_any  # noqa: E221
    in_ = 'IN'
    IN = in_  # noqa: E221
    gt = 'GT'
    GT = gt  # noqa: E221
    lt = 'LT'
    LT = lt  # noqa: E221

class AgentFilter(BaseModel):
    """
    查询过滤条件。多值操作符使用 values，单值/范围操作符使用 value
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    field: constr(min_length=1) = Field(..., description='字段名')
    operator: AgentOperator = Field(
        ...,
        description='查询操作符：EQ/CONTAINS/STARTS_WITH（单值）、IN/CONTAINS_ANY/STARTS_WITH_ANY（多值）、GT/LT（范围）',
    )
    value: Optional[str] = Field(None, description='单值/范围操作符的值')
    values: Optional[List[Optional[str]]] = Field(
        None, description='多值操作符的值列表'
    )

class PlanVersion(str, Enum):
    """
    契约版本号
    """

    field_1_0 = '1.0'

class QueryContextMode(str, Enum):
    """
    查询上下文模式：REPLACE（独立新查询）或 MERGE（在上轮结果上增量修改）
    """

    replace = 'REPLACE'
    REPLACE = replace  # noqa: E221
    merge = 'MERGE'
    MERGE = merge  # noqa: E221

class AgentQuerySpec(BaseModel):
    """
    QUERY 计划的查询规格，描述过滤条件、返回字段和分页参数
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    context_mode: Optional[QueryContextMode] = Field(
        None,
        alias='contextMode',
        description='查询上下文模式：REPLACE（独立新查询）或 MERGE（在上轮结果上增量修改）',
    )
    filters: Optional[List[AgentFilter]] = Field(
        None, description='过滤条件列表', max_length=5, min_length=0
    )
    page: Optional[conint(ge=1)] = Field(None, description='分页页码，从 1 开始')
    remove_fields: Optional[List[Optional[str]]] = Field(
        None,
        alias='removeFields',
        description='待移除的字段列表（MERGE 模式使用）',
        max_length=5,
        min_length=0,
    )
    select_fields: Optional[List[Optional[str]]] = Field(
        None,
        alias='selectFields',
        description='指定返回字段列表，最多 10 个',
        max_length=10,
        min_length=0,
    )
    size: Optional[conint(ge=1)] = Field(None, description='每页大小，1~100')

class AgentResponseType(str, Enum):
    """
    Agent 聊天响应类型
    """

    result = 'RESULT'
    RESULT = result  # noqa: E221
    clarify = 'CLARIFY'
    CLARIFY = clarify  # noqa: E221
    error = 'ERROR'
    ERROR = error  # noqa: E221

class AggregateFunction(str, Enum):
    """
    聚合函数：COUNT（计数）、SUM（求和）、AVG（平均值）、MIN（最小值）、MAX（最大值）
    """

    count = 'COUNT'
    COUNT = count  # noqa: E221
    sum = 'SUM'
    SUM = sum  # noqa: E221
    avg = 'AVG'
    AVG = avg  # noqa: E221
    min = 'MIN'
    MIN = min  # noqa: E221
    max = 'MAX'
    MAX = max  # noqa: E221

class AggregateMetricSpec(BaseModel):
    """
    聚合指标规格
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    alias: constr(min_length=0, max_length=50) = Field(
        ..., description='指标别名，结果集中使用，必须唯一'
    )
    field: Optional[str] = Field(None, description='目标字段名，COUNT 时为 null')
    function: AggregateFunction = Field(
        ...,
        description='聚合函数：COUNT（计数）、SUM（求和）、AVG（平均值）、MIN（最小值）、MAX（最大值）',
    )

class Direction(str, Enum):
    """
    排序方向
    """

    asc = 'ASC'
    desc = 'DESC'

class AggregateOrderSpec(BaseModel):
    """
    聚合结果排序规格
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    direction: Direction = Field(..., description='排序方向')
    field: constr(min_length=1) = Field(
        ..., description='排序字段名，来自 groupByFields 或 metric alias'
    )

class CapabilityContextSpec(BaseModel):
    """
    Capability 上下文读写声明
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    reads: Optional[List[str]] = Field(
        None, description='读取的上下文键，例如 previousQuery'
    )
    writes: Optional[List[str]] = Field(
        None,
        description='写入的上下文键，例如 RuntimeQueryContext、RuntimeAggregateContext',
    )

class CapabilityContractRef(BaseModel):
    """
    Capability 输入/输出契约引用
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    schema_: constr(min_length=1) = Field(
        ...,
        alias='schema',
        description='契约逻辑名，例如 AgentPlan.query、AgentPlan.aggregate、ClarifySpec、AgentQueryResult、AgentAggregateResult',
    )
    version: constr(min_length=1) = Field(..., description='契约版本号')

class CapabilityDomainScope(BaseModel):
    """
    Capability 在单个 domain 上的可用范围
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    domain: constr(min_length=1) = Field(
        ..., description='业务域，例如 employee、transaction'
    )
    enabled: bool = Field(..., description='当前 capability 在该 domain 是否可用')
    reason_code: Optional[str] = Field(
        None, alias='reasonCode', description='不可用原因或状态原因，当前仅用于后续扩展'
    )

class ClarifySpec(BaseModel):
    """
    CLARIFY 计划的追问规格
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    question: constr(min_length=1, max_length=500) = Field(
        ..., description='反问问题文本，1~500 字符'
    )

class RuntimeAggregateContext(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    domain: Optional[str] = None
    filters: Optional[List[AgentFilter]] = None
    group_by_fields: Optional[List[str]] = Field(None, alias='groupByFields')
    max_rows: Optional[conint(ge=1)] = Field(None, alias='maxRows')
    metrics: Optional[List[AggregateMetricSpec]] = None
    source_turn_id: Optional[str] = Field(None, alias='sourceTurnId')

class RuntimeErrorResponse(BaseModel):
    """
    Runtime 错误响应
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    code: constr(min_length=1) = Field(..., description='错误码')
    message: constr(min_length=1) = Field(..., description='错误消息')
    request_id: Optional[str] = Field(
        None, alias='requestId', description='关联的请求 ID'
    )

class RuntimeFieldSchema(BaseModel):
    """
    字段 schema，包含别名、允许操作符、数据类型和聚合函数白名单
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    aliases: Optional[List[Optional[str]]] = Field(None, description='字段别名')
    format_hint: Optional[str] = Field(
        None,
        alias='formatHint',
        description='格式提示（如 ISO-8601 datetime with timezone）',
    )
    name: constr(min_length=1) = Field(..., description='字段名')
    operators: List[AgentOperator] = Field(..., description='允许的操作符列表')
    supported_aggregate_functions: Optional[List[AggregateFunction]] = Field(
        None,
        alias='supportedAggregateFunctions',
        description='支持的聚合函数列表。null 表示无 adapter（不应推断为完全允许），[] 表示仅允许 COUNT',
    )
    type: AgentFieldType = Field(
        ...,
        description='字段数据类型：STRING（字符串）、DECIMAL（数值）、INSTANT（时间戳）',
    )

class RuntimeQueryContext(BaseModel):
    """
    上轮成功查询的上下文，传递回 Runtime 用于 MERGE 判断
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    domain: constr(min_length=1) = Field(..., description='查询域')
    filters: Optional[List[AgentFilter]] = Field(None, description='上轮过滤条件')
    page: Optional[conint(ge=1)] = Field(None, description='上轮页码')
    select_fields: Optional[List[Optional[str]]] = Field(
        None, alias='selectFields', description='上轮返回字段'
    )
    size: Optional[conint(ge=1)] = Field(None, description='上轮分页大小')
    source_turn_id: constr(min_length=1) = Field(
        ..., alias='sourceTurnId', description='来源 turn ID'
    )

class RuntimeRole(str, Enum):
    """
    对话角色：USER 或 ASSISTANT
    """

    user = 'USER'
    USER = user  # noqa: E221
    assistant = 'ASSISTANT'
    ASSISTANT = assistant  # noqa: E221

class RuntimeTurn(BaseModel):
    """
    对话轮次摘要
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    content: constr(min_length=1) = Field(..., description='内容文本')
    role: RuntimeRole = Field(..., description='对话角色：USER 或 ASSISTANT')

class AgentAggregateSpec(BaseModel):
    """
    AGGREGATE 计划的聚合规格
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    filters: Optional[List[AgentFilter]] = Field(
        None, description='预聚合过滤条件列表', max_length=5, min_length=0
    )
    group_by_fields: Optional[List[Optional[str]]] = Field(
        None,
        alias='groupByFields',
        description='分组字段列表',
        max_length=2,
        min_length=0,
    )
    max_rows: Optional[conint(ge=1, le=100)] = Field(
        None, alias='maxRows', description='全局最多返回行数上限'
    )
    metrics: List[AggregateMetricSpec] = Field(
        ..., description='聚合指标列表，至少 1 个', max_length=5, min_length=0
    )
    order_by: Optional[List[AggregateOrderSpec]] = Field(
        None,
        alias='orderBy',
        description='结果排序列表，field 必须来自 groupByFields 或 metric alias',
    )

class AgentCapabilityDescriptor(BaseModel):
    """
    Agent capability descriptor
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    capability_id: constr(min_length=1) = Field(
        ..., alias='capabilityId', description='稳定能力 ID，例如 query.search'
    )
    context: CapabilityContextSpec
    description: constr(min_length=1) = Field(..., description='能力说明')
    display_name: constr(min_length=1) = Field(
        ..., alias='displayName', description='给 Runtime/prompt 使用的短名称'
    )
    domain_scopes: List[CapabilityDomainScope] = Field(
        ...,
        alias='domainScopes',
        description='支持的 domain scope。不绑定 domain 的能力使用空列表，例如 clarify.ask',
    )
    enabled: bool = Field(..., description='是否当前可用')
    execution_mode: AgentCapabilityExecutionMode = Field(
        ..., alias='executionMode', description='Capability 执行模式'
    )
    input_contract: CapabilityContractRef = Field(..., alias='inputContract')
    intent: AgentIntent = Field(
        ...,
        description='Agent 顶层意图：QUERY（查询）、CLARIFY（反问澄清）、AGGREGATE（聚合分析）',
    )
    output_contract: CapabilityContractRef = Field(..., alias='outputContract')
    permissions: Optional[List[Optional[str]]] = Field(
        None, description='权限说明，不下发具体角色'
    )
    risk_level: AgentCapabilityRiskLevel = Field(
        ..., alias='riskLevel', description='Capability 风险等级'
    )

class AgentPlan(BaseModel):
    """
    Runtime 输出的候选结构化计划
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    aggregate: Optional[AgentAggregateSpec] = None
    clarify: Optional[ClarifySpec] = None
    domain: Optional[str] = Field(None, description='目标业务域')
    intent: AgentIntent = Field(
        ...,
        description='Agent 顶层意图：QUERY（查询）、CLARIFY（反问澄清）、AGGREGATE（聚合分析）',
    )
    plan_version: PlanVersion = Field(
        ..., alias='planVersion', description='契约版本号'
    )
    query: Optional[AgentQuerySpec] = None

class PlanGenerateResponse(BaseModel):
    """
    Runtime plan 生成响应
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    plan: Optional[AgentPlan] = None
    request_id: constr(min_length=1) = Field(
        ..., alias='requestId', description='请求 ID'
    )

class RuntimeDomainSchema(BaseModel):
    """
    域 schema 定义，包含字段列表、默认展示字段和分页/过滤上限
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    aliases: Optional[List[Optional[str]]] = Field(None, description='域别名列表')
    default_select_fields: Optional[List[Optional[str]]] = Field(
        None, alias='defaultSelectFields', description='默认展示字段'
    )
    default_size: Optional[int] = Field(
        None, alias='defaultSize', description='默认分页大小'
    )
    domain: constr(min_length=1) = Field(..., description='域标识')
    fields: List[RuntimeFieldSchema] = Field(
        ..., description='字段 schema 列表', min_length=1
    )
    max_filters: Optional[int] = Field(
        None, alias='maxFilters', description='最大过滤条件数'
    )
    max_result_window: Optional[int] = Field(
        None, alias='maxResultWindow', description='最大结果窗口'
    )
    max_size: Optional[int] = Field(None, alias='maxSize', description='最大分页大小')

class PlanGenerateRequest(BaseModel):
    """
    发送给 Runtime 的 plan 生成请求
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    capabilities: List[AgentCapabilityDescriptor] = Field(
        ..., description='当前请求可用的 Agent capability 列表'
    )
    domain_schemas: List[RuntimeDomainSchema] = Field(
        ...,
        alias='domainSchemas',
        description='领域 schema 列表',
        max_length=2147483647,
        min_length=1,
    )
    message: constr(min_length=1) = Field(..., description='用户消息文本')
    previous_query: Optional[RuntimeQueryContext] = Field(None, alias='previousQuery')
    recent_turns: Optional[List[RuntimeTurn]] = Field(
        None,
        alias='recentTurns',
        description='最近对话轮次（最多 6 轮）',
        max_length=6,
        min_length=0,
    )
    request_id: constr(min_length=1) = Field(
        ..., alias='requestId', description='请求 ID'
    )
