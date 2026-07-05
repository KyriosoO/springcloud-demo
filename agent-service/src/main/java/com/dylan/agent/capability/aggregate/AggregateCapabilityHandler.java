package com.dylan.agent.capability.aggregate;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.response.AgentAggregateMetricParameter;
import com.dylan.agent.api.response.AgentAggregateOrderParameter;
import com.dylan.agent.api.response.AgentAggregateParameters;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentAggregateRow;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Kernel AGGREGATE 处理器：只执行已校验计划，授权、绑定、结果安全和 Context 审批由 ExecutionCore 统一处理。 */
@Component
public class AggregateCapabilityHandler
        implements CapabilityHandler<ValidatedAggregatePlan, AggregateAgentResultPayload> {

    @Override
    public HandlerResult<AggregateAgentResultPayload> execute(
            ValidatedAggregatePlan plan,
            ExecutionContext context) {
        AggregatableAdapter adapter = context.requireAdapter(AggregatableAdapter.class);
        AdapterAggregateResult adapterResult = adapter.aggregate(plan.aggregate());
        AggregateAgentResultPayload payload = new AggregateAgentResultPayload(
                toAggregateParameters(plan),
                toKernelAggregateResult(plan, adapterResult));
        return HandlerResult.of(payload, List.of(toKernelContextWrite(plan)));
    }

    private static AgentAggregateParameters toAggregateParameters(ValidatedAggregatePlan plan) {
        AgentAggregateParameters parameters = new AgentAggregateParameters();
        parameters.setDomain(plan.domain().orElseThrow());
        parameters.setFilters(plan.aggregate().getFilters().stream()
                .map(AggregateCapabilityHandler::toFilterParameter)
                .toList());
        parameters.setMetrics(plan.aggregate().getMetrics().stream()
                .map(AggregateCapabilityHandler::toMetricParameter)
                .toList());
        parameters.setGroupByFields(plan.aggregate().getGroupByFields());
        parameters.setOrderBy(plan.aggregate().getOrderBy().stream()
                .map(AggregateCapabilityHandler::toOrderParameter)
                .toList());
        parameters.setMaxRows(plan.aggregate().getMaxRows());
        return parameters;
    }

    private static AgentAggregateResult toKernelAggregateResult(
            ValidatedAggregatePlan plan,
            AdapterAggregateResult adapterResult) {
        AgentAggregateResult result = new AgentAggregateResult();
        result.setDomain(plan.domain().orElseThrow());
        result.setGroupByFields(plan.aggregate().getGroupByFields());
        result.setMetricAliases(plan.aggregate().getMetrics().stream()
                .map(ValidatedAggregateMetric::getAlias)
                .toList());
        result.setRows(adapterResult.getRows().stream()
                .map(row -> toKernelAggregateRow(plan, row))
                .toList());
        result.setPartial(adapterResult.isPartial());
        return result;
    }

    private static AgentAggregateRow toKernelAggregateRow(
            ValidatedAggregatePlan plan,
            Map<String, Object> source) {
        Map<String, Object> groups = new LinkedHashMap<>();
        for (String field : plan.aggregate().getGroupByFields()) {
            if (source.containsKey(field)) {
                groups.put(field, source.get(field));
            }
        }
        Map<String, Object> metrics = new LinkedHashMap<>();
        for (ValidatedAggregateMetric metric : plan.aggregate().getMetrics()) {
            if (source.containsKey(metric.getAlias())) {
                metrics.put(metric.getAlias(), source.get(metric.getAlias()));
            }
        }
        AgentAggregateRow row = new AgentAggregateRow();
        row.setGroups(groups);
        row.setMetrics(metrics);
        return row;
    }

    private static ContextWriteCandidate toKernelContextWrite(ValidatedAggregatePlan plan) {
        return new ContextWriteCandidate(
                RuntimeContextType.AGGREGATE,
                AgentExecutionContracts.AGGREGATE_CONTEXT,
                new AggregateCapabilityContextPayload(
                        plan.aggregate().getFilters().stream()
                                .map(AggregateCapabilityHandler::toKernelAgentFilter)
                                .toList(),
                        plan.aggregate().getMetrics().stream()
                                .map(AggregateCapabilityHandler::toKernelMetricSpec)
                                .toList(),
                        plan.aggregate().getGroupByFields(),
                        plan.aggregate().getOrderBy(),
                        plan.aggregate().getMaxRows()));
    }

    private static AgentFilter toKernelAgentFilter(ValidatedFilter filter) {
        AgentFilter agentFilter = new AgentFilter();
        agentFilter.setField(filter.getField());
        agentFilter.setOperator(filter.getOperator());
        agentFilter.setValue(filter.getValue());
        agentFilter.setValues(filter.getValues());
        return agentFilter;
    }

    private static AgentQueryFilterParameter toFilterParameter(ValidatedFilter filter) {
        AgentQueryFilterParameter parameter = new AgentQueryFilterParameter();
        parameter.setField(filter.getField());
        parameter.setOperator(filter.getOperator());
        parameter.setValue(filter.getValue());
        parameter.setValues(filter.getValues().isEmpty() ? null : filter.getValues());
        return parameter;
    }

    private static AggregateMetricSpec toKernelMetricSpec(ValidatedAggregateMetric metric) {
        AggregateMetricSpec spec = new AggregateMetricSpec();
        spec.setAlias(metric.getAlias());
        spec.setFunction(metric.getFunction());
        spec.setField(metric.getField());
        return spec;
    }

    private static AgentAggregateMetricParameter toMetricParameter(ValidatedAggregateMetric metric) {
        AgentAggregateMetricParameter parameter = new AgentAggregateMetricParameter();
        parameter.setAlias(metric.getAlias());
        parameter.setFunction(metric.getFunction());
        parameter.setField(metric.getField());
        return parameter;
    }

    private static AgentAggregateOrderParameter toOrderParameter(com.dylan.agent.api.plan.AggregateOrderSpec order) {
        AgentAggregateOrderParameter parameter = new AgentAggregateOrderParameter();
        parameter.setField(order.getField());
        parameter.setDirection(order.getDirection());
        return parameter;
    }
}
