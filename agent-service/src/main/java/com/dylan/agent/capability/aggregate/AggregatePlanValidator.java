package com.dylan.agent.capability.aggregate;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AggregateOrderSpec;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.config.AgentProperties.DomainProperties;
import com.dylan.agent.config.AgentProperties.FieldProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;

/** AGGREGATE plan 校验器。将 Runtime 原始 AgentPlan 校验为 ValidatedAggregatePlan。 */
@Component
public class AggregatePlanValidator
        implements CapabilityPlanValidator<AggregateAgentPlan, ValidatedAggregatePlan> {

    static final String KERNEL_CAPABILITY_ID = "aggregate.compute";

    private final AgentProperties properties;
    private final FilterNormalizer filterNormalizer;
    private final FieldConstraintValidator fieldConstraintValidator;
    private final AggregatableAdapterRegistry aggregateAdapterRegistry;

    @Autowired
    public AggregatePlanValidator(
            AgentProperties properties,
            FilterNormalizer filterNormalizer,
            FieldConstraintValidator fieldConstraintValidator,
            AggregatableAdapterRegistry aggregateAdapterRegistry) {
        this.properties = properties;
        this.filterNormalizer = filterNormalizer;
        this.fieldConstraintValidator = fieldConstraintValidator;
        this.aggregateAdapterRegistry = aggregateAdapterRegistry;
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
        List<ValidatedFilter> filters = QueryPlanValidator.toValidatedFilters(aggregate.getFilters());
        QueryPlanValidator.validateKernelFilters(filters, context);
        List<String> groupByFields =
                aggregate.getGroupByFields() == null ? List.of() : List.copyOf(aggregate.getGroupByFields());
        validateKernelGroupByFields(groupByFields, context);
        validateKernelOrderBy(aggregate.getOrderBy(), groupByFields, metrics);
        int maxRows = aggregate.getMaxRows() == null ? defaultKernelMaxRows(context) : aggregate.getMaxRows();
        int maxAllowedRows = context.domainProjection().maxResultRows();
        if (maxRows <= 0 || (maxAllowedRows > 0 && maxRows > maxAllowedRows)) {
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

    public com.dylan.agent.capability.model.ValidatedAggregatePlan validate(CapabilityValidationContext context) {
        AgentPlan plan = context.planResponse().getPlan();

        if (plan.getIntent() != AgentIntent.AGGREGATE) {
            throw new AgentPlanValidationException("Plan intent 必须为 AGGREGATE。");
        }

        String domain = plan.getDomain();
        if (domain == null || domain.isBlank()) {
            throw new AgentPlanValidationException("AGGREGATE Plan 缺少 domain。");
        }
        DomainProperties dp = properties.getDomains().get(domain);
        if (dp == null) {
            throw new AgentPlanValidationException("不支持的 domain: " + domain);
        }
        Set<String> adapterAggregateFields = aggregateAdapterRegistry != null
                ? aggregateAdapterRegistry.supportedAggregateFields(domain)
                : dp.getFields().keySet();

        AgentAggregateSpec aggregate = plan.getAggregate();
        if (aggregate == null) {
            throw new AgentPlanValidationException("AGGREGATE Plan 缺少 aggregate 字段。");
        }
        if (plan.getQuery() != null) {
            throw new AgentPlanValidationException("AGGREGATE Plan 不能同时携带 query。");
        }
        if (plan.getClarify() != null) {
            throw new AgentPlanValidationException("AGGREGATE Plan 不能同时携带 clarify。");
        }

        var aggConfig = properties.getAggregate();

        List<AggregateMetricSpec> metrics = aggregate.getMetrics();
        if (metrics == null || metrics.isEmpty()) {
            throw new AgentPlanValidationException("AGGREGATE Plan 至少需要一个 metric。");
        }
        if (metrics.size() > aggConfig.getMaxMetrics()) {
            throw new AgentPlanValidationException("metrics 数量超过上限 " + aggConfig.getMaxMetrics());
        }

        Set<String> aliasSet = new LinkedHashSet<>();
        for (AggregateMetricSpec m : metrics) {
            String alias = m.getAlias();
            if (alias == null || alias.isBlank()) {
                throw new AgentPlanValidationException("metric alias 不能为空。");
            }
            if (alias.length() > 50) {
                throw new AgentPlanValidationException("metric alias 长度不能超过 50。");
            }
            if (!aliasSet.add(alias)) {
                throw new AgentPlanValidationException("metric alias 重复: " + alias);
            }
            AggregateFunction func = m.getFunction();
            if (func == null) {
                throw new AgentPlanValidationException("metric function 不能为空。");
            }
            String field = m.getField();
            if (func == AggregateFunction.COUNT) {
                if (field != null && !field.isBlank()) {
                    throw new AgentPlanValidationException("COUNT 不允许指定 field。");
                }
            } else {
                if (field == null || field.isBlank()) {
                    throw new AgentPlanValidationException(func + " 必须指定 field。");
                }
                FieldProperties fp = dp.getFields().get(field);
                if (fp == null) {
                    throw new AgentPlanValidationException("不支持的 metric field: " + field);
                }
                if (func == AggregateFunction.SUM || func == AggregateFunction.AVG) {
                    if (fp.getType() != AgentFieldType.DECIMAL) {
                        throw new AgentPlanValidationException(func + " 只能用于 DECIMAL 字段，当前字段类型: " + fp.getType());
                    }
                }
                if (func == AggregateFunction.MIN || func == AggregateFunction.MAX) {
                    if (fp.getType() != AgentFieldType.DECIMAL && fp.getType() != AgentFieldType.INSTANT) {
                        throw new AgentPlanValidationException(func + " 只能用于 DECIMAL 或 INSTANT 字段");
                    }
                }
                if (!adapterAggregateFields.contains(field)) {
                    throw new AgentPlanValidationException("Adapter 不支持 metric field: " + field);
                }
                if (aggregateAdapterRegistry != null
                        && !aggregateAdapterRegistry.getRequired(domain).supportedFunctions(field).contains(func)) {
                    throw new AgentPlanValidationException(
                            "Adapter 不支持 metric function " + func + " on field: " + field);
                }
            }
        }

        List<AgentFilter> rawFilters = aggregate.getFilters() != null ? aggregate.getFilters() : List.of();
        List<ValidatedFilter> normalizedFilters = filterNormalizer.normalizeAll(rawFilters, dp);
        if (!normalizedFilters.isEmpty()) {
            fieldConstraintValidator.validateFinalQuery(normalizedFilters, dp);
        }

        List<String> groupByFields = aggregate.getGroupByFields();
        if (groupByFields != null && !groupByFields.isEmpty()) {
            if (groupByFields.size() > aggConfig.getMaxGroupFields()) {
                throw new AgentPlanValidationException("groupByFields 数量超过上限 " + aggConfig.getMaxGroupFields());
            }
            for (String gf : groupByFields) {
                if (gf == null || gf.isBlank() || !dp.getFields().containsKey(gf)) {
                    throw new AgentPlanValidationException("不支持的 groupBy field: " + gf);
                }
                if (!adapterAggregateFields.contains(gf)) {
                    throw new AgentPlanValidationException("Adapter 不支持 groupBy field: " + gf);
                }
            }
        }

        int maxRows = aggregate.getMaxRows() != null
                ? aggregate.getMaxRows() : aggConfig.getDefaultMaxRows();
        if (maxRows < 1 || maxRows > aggConfig.getMaxMaxRows()) {
            throw new AgentPlanValidationException(
                    "maxRows 必须在 1～" + aggConfig.getMaxMaxRows() + " 之间。");
        }

        List<ValidatedAggregateMetric> validatedMetrics = metrics.stream()
                .map(m -> new ValidatedAggregateMetric(m.getAlias(), m.getFunction(), m.getField()))
                .toList();

        List<AggregateOrderSpec> orderBy = aggregate.getOrderBy();
        if (orderBy != null) {
            Set<String> validOrderFields = new LinkedHashSet<>();
            validOrderFields.addAll(groupByFields != null ? groupByFields : List.of());
            for (ValidatedAggregateMetric vm : validatedMetrics) {
                validOrderFields.add(vm.getAlias());
            }
            for (AggregateOrderSpec o : orderBy) {
                if (o.getField() == null || o.getField().isBlank()) {
                    throw new AgentPlanValidationException("orderBy field 不能为空。");
                }
                if (o.getDirection() == null || (!o.getDirection().equals("ASC") && !o.getDirection().equals("DESC"))) {
                    throw new AgentPlanValidationException("orderBy direction 必须为 ASC 或 DESC。");
                }
                if (!validOrderFields.contains(o.getField())) {
                    throw new AgentPlanValidationException(
                            "orderBy field '" + o.getField() + "' 不在 groupByFields 或 metric alias 中。");
                }
            }
        }

        return new com.dylan.agent.capability.model.ValidatedAggregatePlan(domain,
                new ValidatedAggregateQuery(normalizedFilters, validatedMetrics,
                        groupByFields != null ? List.copyOf(groupByFields) : List.of(),
                        orderBy,
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

    private static int defaultKernelMaxRows(ExecutionValidationContext context) {
        return context.domainProjection().maxResultRows() > 0
                ? Math.min(100, context.domainProjection().maxResultRows())
                : 100;
    }
}
