package com.dylan.agent.capability.query;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.util.List;

/** Kernel QUERY 处理器：只执行已校验计划，不再承载旧 intent 路由、权限判定或结果脱敏职责。 */
@Component
public class QueryCapabilityHandler implements CapabilityHandler<ValidatedQueryPlan, QueryAgentResultPayload> {

    @Override
    public HandlerResult<QueryAgentResultPayload> execute(
            ValidatedQueryPlan plan,
            ExecutionContext context) {
        QueryableAdapter adapter = context.requireAdapter(QueryableAdapter.class);
        AdapterQueryResult adapterResult = adapter.query(plan.query());
        QueryAgentResultPayload payload = new QueryAgentResultPayload(
                QueryParameterMapper.toQueryParameters(plan),
                toKernelQueryResult(plan, adapterResult));
        return HandlerResult.of(payload, List.of(toKernelContextWrite(plan, adapterResult)));
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

    private static ContextWriteCandidate toKernelContextWrite(
            ValidatedQueryPlan plan,
            AdapterQueryResult adapterResult) {
        return new ContextWriteCandidate(
                RuntimeContextType.QUERY,
                AgentExecutionContracts.QUERY_CONTEXT,
                new QueryCapabilityContextPayload(
                        plan.query().getFilters().stream()
                                .map(QueryCapabilityHandler::toKernelAgentFilter)
                                .toList(),
                        plan.query().getSelectFields(),
                        QueryPlanValidator.toAgentSortSpecs(plan.query().getSorts()),
                        plan.query().getPage(),
                        plan.query().getSize(),
                        adapterResult.getTotal(),
                        adapterResult.isTotalExact(),
                        totalPages(adapterResult)));
    }

    private static Integer totalPages(AdapterQueryResult adapterResult) {
        if (!adapterResult.isTotalExact()) {
            return null;
        }
        int size = adapterResult.getSize();
        if (size <= 0) {
            return null;
        }
        return Math.max(1, (int) Math.ceil((double) adapterResult.getTotal() / (double) size));
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
