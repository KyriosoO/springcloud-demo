package com.dylan.agent.capability.aggregate;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.plan.AggregateOrderSpec;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;

/** AGGREGATE Kernel 计划校验器：只接收 D01 强类型 AggregateAgentPlan，不再兼容旧生成包装结构。 */
@Component
public class AggregatePlanValidator
        implements CapabilityPlanValidator<AggregateAgentPlan, ValidatedAggregatePlan> {

    static final String KERNEL_CAPABILITY_ID = "aggregate.compute";

    private final AgentProperties properties;
    private final FilterNormalizer filterNormalizer;
    private final FieldConstraintValidator fieldConstraintValidator;

    @Autowired
    public AggregatePlanValidator(
            AgentProperties properties,
            FilterNormalizer filterNormalizer,
            FieldConstraintValidator fieldConstraintValidator) {
        this.properties = properties;
        this.filterNormalizer = filterNormalizer;
        this.fieldConstraintValidator = fieldConstraintValidator;
    }

    @Override
    public ValidatedAggregatePlan validate(AggregateAgentPlan rawPlan, ExecutionValidationContext context) {
        Objects.requireNonNull(rawPlan, "rawPlan must not be null");
        Objects.requireNonNull(context, "context must not be null");
        if (!KERNEL_CAPABILITY_ID.equals(context.capabilityId())) {
            throw new IllegalArgumentException("capabilityId mismatch");
        }
        String domain = context.domainProjection().domain()
                .orElseThrow(() -> new IllegalArgumentException("AGGREGATE requires domain projection"));
        AgentAggregateSpec aggregate = Objects.requireNonNull(rawPlan.getAggregate(), "aggregate must not be null");
        List<ValidatedAggregateMetric> metrics = toValidatedMetrics(aggregate.getMetrics(), context);
        if (metrics.isEmpty()) {
            throw new IllegalArgumentException("aggregate metrics must not be empty");
        }
        List<ValidatedFilter> filters = filterNormalizer.normalizeAll(
                aggregate.getFilters(), context.domainProjection().fieldRules());
        QueryPlanValidator.validateKernelFilters(filters, context);
        if (!filters.isEmpty()) {
            fieldConstraintValidator.validateFinalQuery(filters, context.domainProjection().fieldRules());
        }
        List<String> groupByFields =
                aggregate.getGroupByFields() == null ? List.of() : List.copyOf(aggregate.getGroupByFields());
        validateKernelGroupByFields(groupByFields, context);
        validateKernelOrderBy(aggregate.getOrderBy(), groupByFields, metrics);
        int maxRows = aggregate.getMaxRows() == null ? defaultKernelMaxRows(context) : aggregate.getMaxRows();
        int maxAllowedRows = maxKernelRows(context);
        if (maxRows <= 0 || maxRows > maxAllowedRows) {
            throw new IllegalArgumentException("invalid aggregate maxRows");
        }
        return new ValidatedAggregatePlan(
                KERNEL_CAPABILITY_ID,
                domain,
                new ValidatedAggregateQuery(
                        filters,
                        metrics,
                        groupByFields,
                        aggregate.getOrderBy(),
                        maxRows));
    }

    private static List<ValidatedAggregateMetric> toValidatedMetrics(
            List<AggregateMetricSpec> metrics,
            ExecutionValidationContext context) {
        if (metrics == null) {
            return List.of();
        }
        LinkedHashSet<String> aliases = new LinkedHashSet<>();
        return metrics.stream()
                .map(metric -> {
                    if (metric == null
                            || metric.getAlias() == null || metric.getAlias().isBlank()
                            || metric.getFunction() == null) {
                        throw new IllegalArgumentException("invalid aggregate metric");
                    }
                    String alias = metric.getAlias().trim();
                    if (!aliases.add(alias)) {
                        throw new IllegalArgumentException("duplicate aggregate metric alias");
                    }
                    if (metric.getFunction() != AggregateFunction.COUNT) {
                        ExecutionFieldRule rule = requireFieldRule(metric.getField(), context);
                        if (!rule.allowedFunctions().contains(metric.getFunction())) {
                            throw new IllegalArgumentException(
                                    "aggregate function not allowed for field "
                                            + metric.getField() + ": " + metric.getFunction());
                        }
                    }
                    return new ValidatedAggregateMetric(alias, metric.getFunction(), metric.getField());
                })
                .toList();
    }

    private static ExecutionFieldRule requireFieldRule(
            String field,
            ExecutionValidationContext context) {
        if (field == null || field.isBlank()) {
            throw new IllegalArgumentException("aggregate field must not be blank");
        }
        ExecutionFieldRule rule = context.domainProjection().fieldRules().get(field.trim());
        if (rule == null) {
            throw new IllegalArgumentException("unknown field in execution projection: " + field);
        }
        return rule;
    }

    private static void validateKernelGroupByFields(
            List<String> groupByFields,
            ExecutionValidationContext context) {
        for (String field : groupByFields) {
            requireFieldRule(field, context);
        }
    }

    private static void validateKernelOrderBy(
            List<AggregateOrderSpec> orderBy,
            List<String> groupByFields,
            List<ValidatedAggregateMetric> metrics) {
        if (orderBy == null) {
            return;
        }
        Set<String> allowed = new LinkedHashSet<>(groupByFields);
        for (ValidatedAggregateMetric metric : metrics) {
            allowed.add(metric.getAlias());
        }
        for (AggregateOrderSpec order : orderBy) {
            if (order == null || order.getField() == null || order.getField().isBlank()) {
                throw new IllegalArgumentException("orderBy field must not be blank");
            }
            if (!allowed.contains(order.getField())) {
                throw new IllegalArgumentException("orderBy field is not a group field or metric alias: "
                        + order.getField());
            }
        }
    }

    private int defaultKernelMaxRows(ExecutionValidationContext context) {
        int configuredDefault = properties.getAggregate().getDefaultMaxRows();
        int maxRows = maxKernelRows(context);
        return maxRows > 0 ? Math.min(configuredDefault, maxRows) : 0;
    }

    private int maxKernelRows(ExecutionValidationContext context) {
        return com.dylan.agent.kernel.resource.StandardResourceLimits
                .require(context.executionScope()).maxResultRows();
    }
}
