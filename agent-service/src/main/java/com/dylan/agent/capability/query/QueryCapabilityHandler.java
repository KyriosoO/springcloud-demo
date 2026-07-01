package com.dylan.agent.capability.query;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.capability.AgentCapabilityHandler;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.exception.AgentQueryException;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import com.dylan.agent.metadata.domain.internal.AdapterPortResolver;
import com.dylan.agent.result.AgentResultProcessor;
import com.dylan.agent.security.AgentPermissionService;

import java.util.List;

/** QUERY 意图的能力处理器。validate() 委托 QueryPlanValidator，execute() 依次执行：权限校验 → Adapter 查找 → 查询执行 → 结果处理 → 消息构建 → 上下文持久化。Adapter 异常包装为 AgentQueryException。 */
@Component
public class QueryCapabilityHandler
        implements AgentCapabilityHandler<com.dylan.agent.capability.model.ValidatedQueryPlan>,
        com.dylan.agent.kernel.handler.CapabilityHandler<ValidatedQueryPlan, QueryAgentResultPayload> {

    private final QueryPlanValidator queryPlanValidator;
    private final AgentPermissionService permissionService;
    private final AdapterPortResolver adapterPortResolver;
    private final AgentResultProcessor resultProcessor;

    public QueryCapabilityHandler(
            QueryPlanValidator queryPlanValidator,
            AgentPermissionService permissionService,
            AdapterPortResolver adapterPortResolver,
            AgentResultProcessor resultProcessor) {
        this.queryPlanValidator = queryPlanValidator;
        this.permissionService = permissionService;
        this.adapterPortResolver = adapterPortResolver;
        this.resultProcessor = resultProcessor;
    }

    @Override
    public AgentIntent intent() {
        return AgentIntent.QUERY;
    }

    @Override
    public AgentCapabilityRiskLevel riskLevel() {
        return AgentCapabilityRiskLevel.READ_ONLY;
    }

    @Override
    public com.dylan.agent.capability.model.ValidatedQueryPlan validate(CapabilityValidationContext context) {
        return queryPlanValidator.validate(context);
    }

    @Override
    public CapabilityExecutionResult execute(
            CapabilityExecutionContext context,
            com.dylan.agent.capability.model.ValidatedQueryPlan plan) {

        permissionService.checkQuery(
                context.userContext(),
                plan.domain(),
                plan.query());

        QueryableAdapter adapter =
                adapterPortResolver.require(AdapterRole.QUERYABLE, plan.domain(), QueryableAdapter.class);

        AdapterQueryResult rawResult;
        try {
            rawResult = adapter.query(plan.query());
        } catch (AgentAdapterException e) {
            throw new AgentQueryException(e.getSafeMessage(), e);
        }

        AgentQueryResult safeResult = resultProcessor.process(
                rawResult,
                plan.query(),
                context.userContext(),
                plan.domain());

        String message = QueryMessages.buildSuccessMessage(safeResult);

        return CapabilityExecutionResult.queryResult(
                message,
                QueryParameterMapper.toQueryParameters(plan),
                safeResult,
                QueryRuntimeContextFactory.toRuntimeQueryContext(
                        context.turnId(),
                        plan));
    }

    @Override
    public HandlerResult<QueryAgentResultPayload> execute(
            ValidatedQueryPlan plan,
            ExecutionContext context) {
        QueryableAdapter adapter = context.requireAdapter(QueryableAdapter.class);
        AdapterQueryResult adapterResult = adapter.query(plan.query());
        QueryAgentResultPayload payload = new QueryAgentResultPayload(
                QueryParameterMapper.toQueryParameters(plan),
                toKernelQueryResult(plan, adapterResult));
        return HandlerResult.of(payload, List.of(toKernelContextWrite(plan)));
    }

    private static AgentQueryResult toKernelQueryResult(
            ValidatedQueryPlan plan,
            AdapterQueryResult adapterResult) {
        AgentQueryResult result = new AgentQueryResult();
        result.setColumns(plan.query().getSelectFields());
        result.setRows(adapterResult.getRows());
        result.setTotal(adapterResult.getTotal());
        result.setTotalExact(adapterResult.isTotalExact());
        result.setPage(adapterResult.getPage());
        result.setSize(adapterResult.getSize());
        return result;
    }

    private static ContextWriteCandidate toKernelContextWrite(ValidatedQueryPlan plan) {
        return new ContextWriteCandidate(
                RuntimeContextType.QUERY,
                AgentExecutionContracts.QUERY_CONTEXT,
                new QueryCapabilityContextPayload(
                        plan.query().getFilters().stream()
                                .map(QueryCapabilityHandler::toKernelAgentFilter)
                                .toList(),
                        plan.query().getSelectFields(),
                        plan.query().getPage(),
                        plan.query().getSize()));
    }

    private static AgentFilter toKernelAgentFilter(ValidatedFilter filter) {
        AgentFilter agentFilter = new AgentFilter();
        agentFilter.setField(filter.getField());
        agentFilter.setOperator(filter.getOperator());
        agentFilter.setValue(filter.getValue());
        agentFilter.setValues(filter.getValues());
        return agentFilter;
    }
}
