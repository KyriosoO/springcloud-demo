# 基于当前 agent-runtime OpenAPI 自动生成，请勿手工编辑。
# 来源：agent-api/src/main/resources/openapi/agent-runtime-openapi.json
# source_sha256: 8847a95fff529ed23f576612556d2954fbb88da011241ba42597cc9daa395dc5
# 生成器：scripts/generate_contract_models.py

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel


class GroupByField(RootModel[Optional[str]]):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    root: Optional[str] = Field(None, description='分组字段列表', min_length=1)


class AgentDomainMode(str, Enum):
    none = 'NONE'
    optional = 'OPTIONAL'
    required = 'REQUIRED'


class AgentFieldType(str, Enum):
    string = 'STRING'
    decimal = 'DECIMAL'
    instant = 'INSTANT'


class AgentOperator(str, Enum):
    eq = 'EQ'
    contains = 'CONTAINS'
    contains_any = 'CONTAINS_ANY'
    starts_with = 'STARTS_WITH'
    starts_with_any = 'STARTS_WITH_ANY'
    in_ = 'IN'
    gt = 'GT'
    lt = 'LT'


class AgentPlanKind(str, Enum):
    query = 'QUERY'
    aggregate = 'AGGREGATE'
    document = 'DOCUMENT'


class Direction(str, Enum):
    """
    排序方向：ASC 或 DESC
    """

    asc = 'ASC'
    desc = 'DESC'


class AgentSortSpec(BaseModel):
    """
    QUERY 明细结果排序规格
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    direction: Direction = Field(..., description='排序方向：ASC 或 DESC')
    field: str = Field(..., description='canonical 字段名', min_length=1)


class PlanKind(str, Enum):
    """
    Agent Plan 结构类型
    """

    aggregate = 'AGGREGATE'


class AggregateFunction(str, Enum):
    count = 'COUNT'
    sum = 'SUM'
    avg = 'AVG'
    min = 'MIN'
    max = 'MAX'


class AggregateMetricSpec(BaseModel):
    """
    聚合指标规格
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    alias: str = Field(
        ..., description='指标别名，结果集中使用，必须唯一', max_length=50, min_length=0
    )
    field: Optional[str] = Field(None, description='目标字段名，COUNT 时为 null')
    function: AggregateFunction


class Direction1(str, Enum):
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
    direction: Direction1 = Field(..., description='排序方向')
    field: str = Field(
        ..., description='排序字段名，来自 groupByFields 或 metric alias', min_length=1
    )


class ArgType(str, Enum):
    """
    ClarificationArgs 子类型
    """

    capability_choices = 'CAPABILITY_CHOICES'


class CapabilityChoiceArgs(BaseModel):
    """
    capability 候选列表
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    arg_type: Literal['CAPABILITY_CHOICES'] = Field(
        ..., alias='argType', description='ClarificationArgs 子类型'
    )
    capability_ids: List[str] = Field(
        ...,
        alias='capabilityIds',
        description='候选 capabilityId 列表（2～20，去重）',
        max_length=20,
        min_length=2,
    )


class ClarificationArgType(str, Enum):
    capability_choices = 'CAPABILITY_CHOICES'
    domain_choices = 'DOMAIN_CHOICES'
    field_choices = 'FIELD_CHOICES'
    field_forbidden = 'FIELD_FORBIDDEN'
    value_choices = 'VALUE_CHOICES'


class ClarificationReasonCode(str, Enum):
    capability_ambiguous = 'CAPABILITY_AMBIGUOUS'
    domain_required = 'DOMAIN_REQUIRED'
    domain_ambiguous = 'DOMAIN_AMBIGUOUS'
    field_required = 'FIELD_REQUIRED'
    field_forbidden = 'FIELD_FORBIDDEN'
    value_required = 'VALUE_REQUIRED'
    value_ambiguous = 'VALUE_AMBIGUOUS'


class OutcomeType(str, Enum):
    """
    Runtime Outcome 类型 discriminator
    """

    clarification = 'CLARIFICATION'


class PlanKind1(str, Enum):
    """
    Agent Plan 结构类型
    """

    document = 'DOCUMENT'


class FailurePolicy(str, Enum):
    """
    文档生成失败后的处理策略
    """

    fallback_extractive = 'FALLBACK_EXTRACTIVE'
    refuse = 'REFUSE'


class DocumentGenerationOptions(BaseModel):
    """
    文档生成式回答和总结选项
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    enabled: Optional[bool] = Field(None, description='是否请求生成式回答或总结')
    failure_policy: Optional[FailurePolicy] = Field(
        None, alias='failurePolicy', description='文档生成失败后的处理策略'
    )
    max_output_chars: Optional[int] = Field(
        None, alias='maxOutputChars', description='最大输出字符数', ge=1
    )


class DocumentPlanOperation(str, Enum):
    """
    文档能力操作类型
    """

    search = 'SEARCH'
    answer = 'ANSWER'
    summarize = 'SUMMARIZE'


class RetrievalMode(str, Enum):
    """
    文档检索模式
    """

    keyword = 'KEYWORD'
    vector = 'VECTOR'
    hybrid = 'HYBRID'


class DocumentRetrievalOptions(BaseModel):
    """
    文档检索选项
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    keyword_k: Optional[int] = Field(
        None, alias='keywordK', description='关键词召回候选数', ge=1
    )
    material_type: Optional[str] = Field(
        None, alias='materialType', description='资料类型，例如 policy、notice、faq'
    )
    num_candidates: Optional[int] = Field(
        None, alias='numCandidates', description='向量召回候选池大小', ge=1
    )
    page: Optional[int] = Field(None, description='页码，从 1 开始', ge=1)
    rerank_enabled: Optional[bool] = Field(
        None,
        alias='rerankEnabled',
        description='请求级 rerank 启用建议，最终由 Java profile 配置裁剪',
    )
    retrieval_channels: Optional[List[Optional[str]]] = Field(
        None,
        alias='retrievalChannels',
        description='召回通道列表，例如 BM25、EXACT、PHRASE、DENSE_VECTOR',
    )
    retrieval_mode: Optional[RetrievalMode] = Field(
        None, alias='retrievalMode', description='文档检索模式'
    )
    retrieval_profile: Optional[str] = Field(
        None,
        alias='retrievalProfile',
        description='检索 profile 标识，由 Java 侧校验并冻结',
    )
    rrf_k: Optional[int] = Field(None, alias='rrfK', description='RRF 平滑常量', ge=1)
    size: Optional[int] = Field(None, description='每页大小', ge=1)
    top_k: Optional[int] = Field(None, alias='topK', description='证据条数上限', ge=1)
    vector_k: Optional[int] = Field(
        None, alias='vectorK', description='向量召回候选数', ge=1
    )


class DocumentSummaryScope(BaseModel):
    """
    文档总结范围
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    document_ids: Optional[List[Optional[str]]] = Field(
        None,
        alias='documentIds',
        description='限定文档 ID 列表',
        max_length=20,
        min_length=0,
    )
    max_summary_chars: Optional[int] = Field(
        None, alias='maxSummaryChars', description='最大摘要字符数', ge=1
    )
    section_hints: Optional[List[Optional[str]]] = Field(
        None, alias='sectionHints', description='章节提示', max_length=10, min_length=0
    )
    time_range: Optional[str] = Field(
        None, alias='timeRange', description='时间范围表达式'
    )


class ArgType1(str, Enum):
    """
    ClarificationArgs 子类型
    """

    domain_choices = 'DOMAIN_CHOICES'


class DomainChoiceArgs(BaseModel):
    """
    domain 候选列表
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    arg_type: Literal['DOMAIN_CHOICES'] = Field(
        ..., alias='argType', description='ClarificationArgs 子类型'
    )
    domains: List[str] = Field(
        ..., description='候选 domain 列表（1～20，去重）', max_length=20, min_length=1
    )


class OutcomeType1(str, Enum):
    """
    Runtime Outcome 类型 discriminator
    """

    executable = 'EXECUTABLE'


class ArgType2(str, Enum):
    """
    ClarificationArgs 子类型
    """

    field_choices = 'FIELD_CHOICES'


class FieldChoiceArgs(BaseModel):
    """
    字段候选列表
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    arg_type: Literal['FIELD_CHOICES'] = Field(
        ..., alias='argType', description='ClarificationArgs 子类型'
    )
    fields: List[str] = Field(
        ..., description='候选字段列表（1～50，去重）', max_length=50, min_length=1
    )


class ArgType3(str, Enum):
    """
    ClarificationArgs 子类型
    """

    field_forbidden = 'FIELD_FORBIDDEN'


class FieldForbiddenArgs(BaseModel):
    """
    字段禁止访问
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    arg_type: Literal['FIELD_FORBIDDEN'] = Field(
        ..., alias='argType', description='ClarificationArgs 子类型'
    )
    field: str = Field(
        ..., description='用户请求但当前不可访问的字段或字段描述', min_length=1
    )


class ContractVersion(str, Enum):
    """
    唯一 contract generation 版本
    """

    field_1_0_0 = '1.0.0'


class PlanKind2(str, Enum):
    """
    Agent Plan 结构类型
    """

    query = 'QUERY'


class QueryContextMode(str, Enum):
    replace = 'REPLACE'
    merge = 'MERGE'


class OutcomeType2(str, Enum):
    """
    Runtime Outcome 类型 discriminator
    """

    decision = 'DECISION'


class ContextType(str, Enum):
    """
    上下文类型
    """

    aggregate = 'AGGREGATE'


class RuntimeCapabilityRoutingDescriptor(BaseModel):
    """
    Capability Routing Descriptor 请求投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    allowed_domains: List[str] = Field(
        ...,
        alias='allowedDomains',
        description='当前请求允许的 domain 标识，去重。NONE 时为空，REQUIRED 时非空',
    )
    applicability: List[str] = Field(
        ..., description='适用条件，最多 20 项', max_length=20, min_length=0
    )
    capability_id: str = Field(
        ...,
        alias='capabilityId',
        description='capability 稳定标识',
        max_length=128,
        min_length=1,
    )
    description: str = Field(
        ..., description='面向模型的能力描述', max_length=1000, min_length=1
    )
    domain_mode: AgentDomainMode = Field(..., alias='domainMode')
    exclusions: List[str] = Field(
        ..., description='排除条件，最多 20 项', max_length=20, min_length=0
    )
    plan_kind: AgentPlanKind = Field(..., alias='planKind')


class RuntimeContextType(str, Enum):
    query = 'QUERY'
    aggregate = 'AGGREGATE'
    document = 'DOCUMENT'


class ContextType1(str, Enum):
    """
    上下文类型
    """

    document = 'DOCUMENT'


class RuntimeDomainFieldSchema(BaseModel):
    """
    Domain 字段投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    aggregate_functions: List[AggregateFunction] = Field(
        ...,
        alias='aggregateFunctions',
        description='支持的聚合函数，空列表表示仅 COUNT',
    )
    aliases: List[str] = Field(..., description='字段别名')
    field: str = Field(..., description='字段名', min_length=1)
    format_hint: Optional[str] = Field(
        None,
        alias='formatHint',
        description='安全格式说明（仅格式，不含凭据或转义语义）',
    )
    operators: List[AgentOperator] = Field(
        ..., description='允许的 operator', min_length=1
    )
    type: AgentFieldType


class RuntimeDomainRoutingProjection(BaseModel):
    """
    Route 阶段 domain 投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    aliases: List[str] = Field(..., description='domain 别名')
    description: str = Field(..., description='domain 描述', min_length=1)
    domain: str = Field(..., description='domain 标识', min_length=1)


class RuntimeDomainSchema(BaseModel):
    """
    Domain Schema 投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    default_select_fields: List[str] = Field(
        ..., alias='defaultSelectFields', description='默认展示字段'
    )
    default_size: Optional[int] = Field(
        None, alias='defaultSize', description='默认 page size', ge=1
    )
    domain: str = Field(..., description='domain 标识', min_length=1)
    fields: List[RuntimeDomainFieldSchema] = Field(
        ..., description='字段列表，field 唯一'
    )
    max_size: Optional[int] = Field(
        None, alias='maxSize', description='最大 page size', ge=1
    )
    sort_fields: List[str] = Field(
        ..., alias='sortFields', description='当前授权可用于 QUERY 排序的字段'
    )


class RuntimeErrorCode(str, Enum):
    contract_invalid = 'CONTRACT_INVALID'
    authentication_failed = 'AUTHENTICATION_FAILED'
    provider_unavailable = 'PROVIDER_UNAVAILABLE'
    deadline_exceeded = 'DEADLINE_EXCEEDED'
    output_repair_exhausted = 'OUTPUT_REPAIR_EXHAUSTED'
    internal_error = 'INTERNAL_ERROR'


class RuntimeOperationType(str, Enum):
    route = 'ROUTE'
    plan = 'PLAN'


class RuntimeOutcomeType(str, Enum):
    decision = 'DECISION'
    executable = 'EXECUTABLE'
    clarification = 'CLARIFICATION'


class Instruction(RootModel[str]):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    root: str = Field(
        ..., description='行为指令列表，最多 20 项', max_length=500, min_length=1
    )


class RuntimeProfileBehaviorProjection(BaseModel):
    """
    Profile 行为投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    instructions: List[Instruction] = Field(
        ..., description='行为指令列表，最多 20 项', max_length=20, min_length=0
    )
    locale: Optional[str] = Field(None, description='locale（BCP-47），可为 null')


class ContextType2(str, Enum):
    """
    上下文类型
    """

    query = 'QUERY'


class RuntimeTerminationReason(str, Enum):
    completed = 'COMPLETED'
    clarification = 'CLARIFICATION'
    validation_rejected = 'VALIDATION_REJECTED'
    repair_exhausted = 'REPAIR_EXHAUSTED'
    deadline_exceeded = 'DEADLINE_EXCEEDED'
    cancelled = 'CANCELLED'
    provider_unavailable = 'PROVIDER_UNAVAILABLE'
    authentication_rejected = 'AUTHENTICATION_REJECTED'
    internal_error = 'INTERNAL_ERROR'


class RuntimeTurnRole(str, Enum):
    user = 'USER'
    assistant = 'ASSISTANT'


class ArgType4(str, Enum):
    """
    ClarificationArgs 子类型
    """

    value_choices = 'VALUE_CHOICES'


class ValueChoiceArgs(BaseModel):
    """
    值候选列表
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    arg_type: Literal['VALUE_CHOICES'] = Field(
        ..., alias='argType', description='ClarificationArgs 子类型'
    )
    field: str = Field(..., description='目标字段名', min_length=1)
    values: List[str] = Field(
        ...,
        description='候选值列表（0～50，VALUE_REQUIRED 允许空列表）',
        max_length=50,
        min_length=0,
    )


class AgentFilter(BaseModel):
    """
    查询过滤条件。多值操作符使用 values，单值/范围操作符使用 value
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    field: str = Field(..., description='字段名', min_length=1)
    operator: AgentOperator
    value: Optional[str] = Field(None, description='单值/范围操作符的值')
    values: Optional[List[Optional[str]]] = Field(
        None, description='多值操作符的值列表'
    )


class AgentQuerySpec(BaseModel):
    """
    QUERY 计划的查询规格，描述过滤条件、返回字段和分页参数
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    context_mode: Optional[QueryContextMode] = Field(None, alias='contextMode')
    filters: Optional[List[AgentFilter]] = Field(
        None, description='过滤条件列表', max_length=5, min_length=0
    )
    page: Optional[int] = Field(None, description='分页页码，从 1 开始', ge=1)
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
    size: Optional[int] = Field(None, description='每页大小，1~100', ge=1)
    sorts: Optional[List[AgentSortSpec]] = Field(
        None, description='明细查询排序列表，最多 2 个', max_length=2, min_length=0
    )


class QueryAgentPlan(BaseModel):
    """
    QUERY Plan 子类型
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    plan_kind: Literal['QUERY'] = Field(
        ..., alias='planKind', description='Agent Plan 结构类型'
    )
    query: AgentQuerySpec


class RuntimeAggregateContextView(BaseModel):
    """
    AGGREGATE context 投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    context_type: Literal['AGGREGATE'] = Field(
        ..., alias='contextType', description='上下文类型'
    )
    filters: List[AgentFilter] = Field(..., description='上轮聚合过滤条件')
    group_by_fields: List[str] = Field(
        ..., alias='groupByFields', description='上轮分组字段'
    )
    max_rows: int = Field(..., alias='maxRows', description='上轮 maxRows', ge=1)
    metrics: List[AggregateMetricSpec] = Field(
        ..., description='上轮聚合指标', max_length=2147483647, min_length=1
    )
    order_by: List[AggregateOrderSpec] = Field(
        ..., alias='orderBy', description='上轮聚合结果排序条件'
    )
    source_invocation_id: str = Field(
        ...,
        alias='sourceInvocationId',
        description='来源 Invocation 标识',
        min_length=1,
    )


class RuntimeDocumentContextView(BaseModel):
    """
    DOCUMENT context 投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    citation_ids: List[str] = Field(..., alias='citationIds', description='上轮引用 ID')
    context_type: Literal['DOCUMENT'] = Field(
        ..., alias='contextType', description='上下文类型'
    )
    domain: Optional[str] = Field(None, description='上轮文档 domain')
    filters: List[AgentFilter] = Field(..., description='上轮文档过滤条件')
    operation: Optional[str] = Field(None, description='上轮文档操作')
    query_text: Optional[str] = Field(
        None, alias='queryText', description='上轮文档查询文本'
    )
    source_invocation_id: str = Field(
        ...,
        alias='sourceInvocationId',
        description='来源 Invocation 标识',
        min_length=1,
    )
    top_k: Optional[int] = Field(None, alias='topK', description='上轮 topK', ge=1)


class RuntimeOperationMetadata(BaseModel):
    """
    Runtime 操作元数据
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    deadline_reached: bool = Field(
        ..., alias='deadlineReached', description='deadline 是否已到期'
    )
    operation: RuntimeOperationType
    provider_attempts: int = Field(
        ..., alias='providerAttempts', description='provider 调用总数', ge=0
    )
    repair_attempts: int = Field(
        ..., alias='repairAttempts', description='repair 调用次数', ge=0
    )
    repair_duration_ms: int = Field(
        ..., alias='repairDurationMs', description='repair 累计耗时 (ms)', ge=0
    )
    repair_limit_reached: bool = Field(
        ..., alias='repairLimitReached', description='是否达到 repair 上限'
    )
    termination_reason: RuntimeTerminationReason = Field(..., alias='terminationReason')
    total_duration_ms: int = Field(
        ..., alias='totalDurationMs', description='操作总耗时 (ms)', ge=0
    )


class RuntimeQueryContextView(BaseModel):
    """
    QUERY context 投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    context_type: Literal['QUERY'] = Field(
        ..., alias='contextType', description='上下文类型'
    )
    filters: List[AgentFilter] = Field(..., description='上轮查询过滤条件')
    page: int = Field(..., description='上轮 page', ge=1)
    select_fields: List[str] = Field(
        ..., alias='selectFields', description='上轮查询展示字段'
    )
    size: int = Field(..., description='上轮 size', ge=1)
    sorts: List[AgentSortSpec] = Field(..., description='上轮查询排序条件')
    source_invocation_id: str = Field(
        ...,
        alias='sourceInvocationId',
        description='来源 Invocation 标识',
        min_length=1,
    )
    total: Optional[int] = Field(
        None, description='上轮查询总数；仅 totalExact=true 时可用于精确分页', ge=0
    )
    total_exact: Optional[bool] = Field(
        None, alias='totalExact', description='上轮查询总数是否精确'
    )
    total_pages: Optional[int] = Field(
        None,
        alias='totalPages',
        description='上轮查询总页数；仅 totalExact=true 时可用于末页计算',
        ge=1,
    )


class RuntimeTurnProjection(BaseModel):
    """
    Runtime turn 投影
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    content: str = Field(
        ..., description='过滤后的会话文本', max_length=4000, min_length=1
    )
    role: RuntimeTurnRole


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
    group_by_fields: Optional[List[Optional[GroupByField]]] = Field(
        None,
        alias='groupByFields',
        description='分组字段列表',
        max_length=2,
        min_length=0,
    )
    max_rows: Optional[int] = Field(
        None, alias='maxRows', description='全局最多返回行数上限', ge=1, le=100
    )
    metrics: List[AggregateMetricSpec] = Field(
        ..., description='聚合指标列表，至少 1 个', max_length=5, min_length=0
    )
    order_by: Optional[List[AggregateOrderSpec]] = Field(
        None,
        alias='orderBy',
        description='结果排序列表，field 必须来自 groupByFields 或 metric alias',
    )


class AgentDocumentSpec(BaseModel):
    """
    DOCUMENT 计划的文档检索、问答和总结规格
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    citation_required: Optional[bool] = Field(
        None,
        alias='citationRequired',
        description='是否要求引用；ANSWER/SUMMARIZE 固定为 true',
    )
    filters: Optional[List[AgentFilter]] = Field(
        None, description='文档过滤条件', max_length=10, min_length=0
    )
    generation_options: Optional[DocumentGenerationOptions] = Field(
        None, alias='generationOptions'
    )
    operation: DocumentPlanOperation
    query_text: str = Field(
        ...,
        alias='queryText',
        description='用户查询或总结目标',
        max_length=500,
        min_length=0,
    )
    retrieval_options: Optional[DocumentRetrievalOptions] = Field(
        None, alias='retrievalOptions'
    )
    sorts: Optional[List[AgentSortSpec]] = Field(
        None, description='文档排序条件', max_length=3, min_length=0
    )
    summary_scope: Optional[DocumentSummaryScope] = Field(None, alias='summaryScope')


class AggregateAgentPlan(BaseModel):
    """
    AGGREGATE Plan 子类型
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    aggregate: AgentAggregateSpec
    plan_kind: Literal['AGGREGATE'] = Field(
        ..., alias='planKind', description='Agent Plan 结构类型'
    )


class ClarificationRequired(BaseModel):
    """
    澄清请求
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    args: Union[
        CapabilityChoiceArgs,
        DomainChoiceArgs,
        FieldChoiceArgs,
        FieldForbiddenArgs,
        ValueChoiceArgs,
    ] = Field(..., description='ClarificationArgs 联合类型', discriminator='arg_type')
    metadata: RuntimeOperationMetadata
    outcome_type: Literal['CLARIFICATION'] = Field(
        ..., alias='outcomeType', description='Runtime Outcome 类型 discriminator'
    )
    reason_code: ClarificationReasonCode = Field(..., alias='reasonCode')
    request_id: str = Field(
        ..., alias='requestId', description='请求关联标识', min_length=1
    )


class DocumentAgentPlan(BaseModel):
    """
    DOCUMENT Plan 子类型
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    document: AgentDocumentSpec
    plan_kind: Literal['DOCUMENT'] = Field(
        ..., alias='planKind', description='Agent Plan 结构类型'
    )


class RouteDecision(BaseModel):
    """
    Route 决策
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    capability_id: str = Field(
        ..., alias='capabilityId', description='选定的 capabilityId', min_length=1
    )
    domain: Optional[str] = Field(None, description='候选 domain，NONE/OPTIONAL 时可空')
    metadata: RuntimeOperationMetadata
    outcome_type: Literal['DECISION'] = Field(
        ..., alias='outcomeType', description='Runtime Outcome 类型 discriminator'
    )
    request_id: str = Field(
        ..., alias='requestId', description='请求关联标识', min_length=1
    )


class RouteOutcome(RootModel[Union[RouteDecision, ClarificationRequired]]):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    root: Union[RouteDecision, ClarificationRequired] = Field(
        ..., description='Route Outcome 联合类型', discriminator='outcome_type'
    )


class RouteRequest(BaseModel):
    """
    Route 请求
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    absolute_deadline: AwareDatetime = Field(
        ..., alias='absoluteDeadline', description='绝对 deadline（ISO-8601）'
    )
    capabilities: List[RuntimeCapabilityRoutingDescriptor] = Field(
        ...,
        description='当前可用 capability 投影，非空，capabilityId 唯一',
        max_length=2147483647,
        min_length=1,
    )
    contract_version: ContractVersion = Field(
        ..., alias='contractVersion', description='唯一 contract generation 版本'
    )
    domains: List[RuntimeDomainRoutingProjection] = Field(
        ..., description='Route 阶段 domain 投影，domain 唯一'
    )
    history: List[RuntimeTurnProjection] = Field(
        ..., description='历史 turn 投影，最多 20 条', max_length=20, min_length=0
    )
    message: str = Field(..., description='用户消息', max_length=8000, min_length=1)
    profile_behavior: RuntimeProfileBehaviorProjection = Field(
        ..., alias='profileBehavior'
    )
    repair_limit: int = Field(
        ...,
        alias='repairLimit',
        description='repair 上限 [0,3]，部署策略可进一步收紧',
        ge=0,
        le=3,
    )
    request_id: str = Field(
        ...,
        alias='requestId',
        description='不透明请求标识',
        max_length=128,
        min_length=1,
    )


class RuntimeErrorResponse(BaseModel):
    """
    Runtime 错误响应
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    code: RuntimeErrorCode
    diagnostic_id: str = Field(
        ..., alias='diagnosticId', description='不透明诊断标识', min_length=1
    )
    message: str = Field(..., description='安全固定摘要', min_length=1)
    metadata: RuntimeOperationMetadata
    request_id: Optional[str] = Field(
        None, alias='requestId', description='请求标识（可空：仅请求解析后可得）'
    )


class ExecutablePlan(BaseModel):
    """
    可执行 plan outcome
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    metadata: RuntimeOperationMetadata
    outcome_type: Literal['EXECUTABLE'] = Field(
        ..., alias='outcomeType', description='Runtime Outcome 类型 discriminator'
    )
    plan: Union[QueryAgentPlan, AggregateAgentPlan, DocumentAgentPlan] = Field(
        ..., description='Agent Plan 联合类型', discriminator='plan_kind'
    )
    request_id: str = Field(
        ..., alias='requestId', description='请求关联标识', min_length=1
    )


class PlanOutcome(RootModel[Union[ExecutablePlan, ClarificationRequired]]):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    root: Union[ExecutablePlan, ClarificationRequired] = Field(
        ..., description='Plan Outcome 联合类型', discriminator='outcome_type'
    )


class PlanRequest(BaseModel):
    """
    Plan 请求
    """

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
    )
    absolute_deadline: AwareDatetime = Field(
        ...,
        alias='absoluteDeadline',
        description='绝对 deadline（与 Route 相同且不可延长）',
    )
    capability: RuntimeCapabilityRoutingDescriptor
    capability_id: str = Field(
        ...,
        alias='capabilityId',
        description='Java 已校验的 capabilityId',
        min_length=1,
    )
    context_views: List[
        Union[
            RuntimeQueryContextView,
            RuntimeAggregateContextView,
            RuntimeDocumentContextView,
        ]
    ] = Field(
        ..., alias='contextViews', description='Context View 列表，contextType 唯一'
    )
    contract_version: ContractVersion = Field(
        ..., alias='contractVersion', description='唯一 contract generation 版本'
    )
    domain: Optional[str] = Field(None, description='已选 domain，NONE 时必为空')
    domain_schema: Optional[RuntimeDomainSchema] = Field(None, alias='domainSchema')
    history: List[RuntimeTurnProjection] = Field(
        ..., description='历史 turn 投影，最多 20 条', max_length=20, min_length=0
    )
    input_schema_ref: str = Field(
        ...,
        alias='inputSchemaRef',
        description='输入 schema 引用（JSON Pointer）',
        min_length=1,
    )
    message: str = Field(..., description='用户消息', max_length=8000, min_length=1)
    plan_kind: AgentPlanKind = Field(..., alias='planKind')
    repair_limit: int = Field(
        ..., alias='repairLimit', description='repair 上限 [0,3]', ge=0, le=3
    )
    request_id: str = Field(
        ...,
        alias='requestId',
        description='请求关联标识（与 Route 同一次 invocation）',
        min_length=1,
    )
