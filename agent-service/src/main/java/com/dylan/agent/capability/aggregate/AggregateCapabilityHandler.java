package com.dylan.agent.capability.aggregate;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.runtime.RuntimeAggregateContext;
import com.dylan.agent.capability.AgentCapabilityHandler;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedAggregatePlan;
import com.dylan.agent.exception.AgentQueryException;
import com.dylan.agent.result.AggregateResultProcessor;
import com.dylan.agent.security.AgentPermissionService;

/** AGGREGATE 意图的能力处理器。validate() 委托 AggregatePlanValidator，execute() 依次执行：权限校验 → Adapter 查找 → 聚合执行 → 结果处理 → 消息构建 → 上下文持久化。 */
@Component
public class AggregateCapabilityHandler
        implements AgentCapabilityHandler<ValidatedAggregatePlan> {

    private final AggregatePlanValidator aggregatePlanValidator;
    private final AgentPermissionService permissionService;
    private final AggregatableAdapterRegistry adapterRegistry;
    private final AggregateResultProcessor resultProcessor;

    public AggregateCapabilityHandler(
            AggregatePlanValidator aggregatePlanValidator,
            AgentPermissionService permissionService,
            AggregatableAdapterRegistry adapterRegistry,
            AggregateResultProcessor resultProcessor) {
        this.aggregatePlanValidator = aggregatePlanValidator;
        this.permissionService = permissionService;
        this.adapterRegistry = adapterRegistry;
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
    public ValidatedAggregatePlan validate(CapabilityValidationContext context) {
        return aggregatePlanValidator.validate(context);
    }

    @Override
    public CapabilityExecutionResult execute(
            CapabilityExecutionContext context,
            ValidatedAggregatePlan plan) {

        permissionService.checkAggregate(
                context.userContext(),
                plan.domain(),
                plan.aggregate());

        AggregatableAdapter adapter =
                adapterRegistry.getRequired(plan.domain());

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

    private static RuntimeAggregateContext toRuntimeAggregateContext(
            String sourceTurnId,
            ValidatedAggregatePlan plan) {
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
}
