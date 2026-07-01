package com.dylan.agent.capability.aggregate;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentAggregateRow;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.runtime.RuntimeAggregateContext;
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
import com.dylan.agent.result.AggregateResultProcessor;
import com.dylan.agent.security.AgentPermissionService;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** AGGREGATE 意图的能力处理器。validate() 委托 AggregatePlanValidator，execute() 依次执行：权限校验 → Adapter 查找 → 聚合执行 → 结果处理 → 消息构建 → 上下文持久化。 */
@Component
public class AggregateCapabilityHandler
        implements AgentCapabilityHandler<com.dylan.agent.capability.model.ValidatedAggregatePlan>,
        com.dylan.agent.kernel.handler.CapabilityHandler<ValidatedAggregatePlan, AggregateAgentResultPayload> {

    private final AggregatePlanValidator aggregatePlanValidator;
    private final AgentPermissionService permissionService;
    private final AdapterPortResolver adapterPortResolver;
    private final AggregateResultProcessor resultProcessor;

    public AggregateCapabilityHandler(
            AggregatePlanValidator aggregatePlanValidator,
            AgentPermissionService permissionService,
            AdapterPortResolver adapterPortResolver,
            AggregateResultProcessor resultProcessor) {
        this.aggregatePlanValidator = aggregatePlanValidator;
        this.permissionService = permissionService;
        this.adapterPortResolver = adapterPortResolver;
        this.resultProcessor = resultProcessor;
    }

    @Override
    public AgentIntent intent() {
        return AgentIntent.AGGREGATE;
    }

    @Override
    public AgentCapabilityRiskLevel riskLevel() {
        return AgentCapabilityRiskLevel.READ_ONLY;
    }

    @Override
    public com.dylan.agent.capability.model.ValidatedAggregatePlan validate(CapabilityValidationContext context) {
        return aggregatePlanValidator.validate(context);
    }

    @Override
    public CapabilityExecutionResult execute(
            CapabilityExecutionContext context,
            com.dylan.agent.capability.model.ValidatedAggregatePlan plan) {

        permissionService.checkAggregate(
                context.userContext(),
                plan.domain(),
                plan.aggregate());

        AggregatableAdapter adapter =
                adapterPortResolver.require(AdapterRole.AGGREGATABLE, plan.domain(), AggregatableAdapter.class);

        AdapterAggregateResult rawResult;
        try {
            rawResult = adapter.aggregate(plan.aggregate());
        } catch (AgentAdapterException e) {
            throw new AgentQueryException(e.getSafeMessage(), e);
        }

        AgentAggregateResult safeResult = resultProcessor.process(
                rawResult,
                plan.aggregate(),
                context.userContext(),
                plan.domain());

        RuntimeAggregateContext aggCtx = toRuntimeAggregateContext(
                context.turnId(), plan);

        return CapabilityExecutionResult.aggregateResult(
                AggregateMessages.success(safeResult),
                safeResult,
                aggCtx);
    }

    @Override
    public HandlerResult<AggregateAgentResultPayload> execute(
            ValidatedAggregatePlan plan,
            ExecutionContext context) {
        AggregatableAdapter adapter = context.requireAdapter(AggregatableAdapter.class);
        AdapterAggregateResult adapterResult = adapter.aggregate(plan.aggregate());
        AggregateAgentResultPayload payload =
                new AggregateAgentResultPayload(toKernelAggregateResult(plan, adapterResult));
        return HandlerResult.of(payload, List.of(toKernelContextWrite(plan)));
    }

    private static RuntimeAggregateContext toRuntimeAggregateContext(
            String sourceTurnId,
            com.dylan.agent.capability.model.ValidatedAggregatePlan plan) {
        RuntimeAggregateContext ctx = new RuntimeAggregateContext();
        ctx.setSourceTurnId(sourceTurnId);
        ctx.setDomain(plan.domain());
        ctx.setFilters(plan.aggregate().getFilters().stream()
                .map(f -> {
                    AgentFilter af = new AgentFilter();
                    af.setField(f.getField());
                    af.setOperator(f.getOperator());
                    af.setValue(f.getValue());
                    af.setValues(f.getValues().isEmpty() ? null : f.getValues());
                    return af;
                })
                .toList());
        ctx.setMetrics(plan.aggregate().getMetrics().stream()
                .map(m -> {
                    AggregateMetricSpec spec = new AggregateMetricSpec();
                    spec.setAlias(m.getAlias());
                    spec.setFunction(m.getFunction());
                    spec.setField(m.getField());
                    return spec;
                })
                .toList());
        ctx.setGroupByFields(plan.aggregate().getGroupByFields());
        ctx.setMaxRows(plan.aggregate().getMaxRows());
        return ctx;
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

    private static AggregateMetricSpec toKernelMetricSpec(ValidatedAggregateMetric metric) {
        AggregateMetricSpec spec = new AggregateMetricSpec();
        spec.setAlias(metric.getAlias());
        spec.setFunction(metric.getFunction());
        spec.setField(metric.getField());
        return spec;
    }
}
