package com.dylan.agent.capability.query;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;

/** QUERY Kernel 计划校验器：只接收 D01 强类型 QueryAgentPlan，不再兼容旧生成包装结构。 */
@Component
public class QueryPlanValidator
        implements CapabilityPlanValidator<QueryAgentPlan, ValidatedQueryPlan> {

    static final String KERNEL_CAPABILITY_ID = "query.search";

    private final AgentProperties properties;
    private final FilterNormalizer filterNormalizer;
    private final FieldConstraintValidator fieldConstraintValidator;
    private final QueryMergeEngine queryMergeEngine;
    private final DomainCatalogView domainCatalogView;

    public QueryPlanValidator(
            AgentProperties properties,
            FilterNormalizer filterNormalizer,
            FieldConstraintValidator fieldConstraintValidator,
            QueryMergeEngine queryMergeEngine,
            DomainCatalogView domainCatalogView) {
        this.properties = properties;
        this.filterNormalizer = filterNormalizer;
        this.fieldConstraintValidator = fieldConstraintValidator;
        this.queryMergeEngine = queryMergeEngine;
        this.domainCatalogView = domainCatalogView;
    }

    @Override
    public ValidatedQueryPlan validate(QueryAgentPlan rawPlan, ExecutionValidationContext context) {
        Objects.requireNonNull(rawPlan, "rawPlan must not be null");
        Objects.requireNonNull(context, "context must not be null");
        if (!KERNEL_CAPABILITY_ID.equals(context.capabilityId())) {
            throw new IllegalArgumentException("capabilityId mismatch");
        }
        String domain = context.domainProjection().domain()
                .orElseThrow(() -> new IllegalArgumentException("QUERY requires domain projection"));
        AgentQuerySpec query = Objects.requireNonNull(rawPlan.getQuery(), "query must not be null");
        List<ValidatedFilter> filters = toValidatedFilters(query.getFilters());
        if (filters.isEmpty()) {
            throw new IllegalArgumentException("query filters must not be empty");
        }
        validateKernelFilters(filters, context);
        List<String> selectFields = normalizeKernelSelectFields(query.getSelectFields(), context);
        validateKernelSelectFields(selectFields, context);
        int page = query.getPage() == null ? 1 : query.getPage();
        int size = query.getSize() == null ? defaultKernelPageSize(context) : query.getSize();
        int maxPageSize = maxKernelPageSize(context);
        if (page <= 0 || size <= 0 || size > maxPageSize) {
            throw new IllegalArgumentException("invalid query pagination");
        }
        return new ValidatedQueryPlan(
                KERNEL_CAPABILITY_ID,
                domain,
                new ValidatedQuery(filters, selectFields, page, size));
    }

    public static List<ValidatedFilter> toValidatedFilters(List<AgentFilter> filters) {
        if (filters == null) {
            return List.of();
        }
        return filters.stream()
                .map(filter -> {
                    if (filter == null
                            || filter.getField() == null || filter.getField().isBlank()
                            || filter.getOperator() == null) {
                        throw new IllegalArgumentException("invalid query filter");
                    }
                    return new ValidatedFilter(
                            filter.getField().trim(),
                            filter.getOperator(),
                            filter.getValue(),
                            filter.getValues());
                })
                .toList();
    }

    public static void validateKernelFilters(
            List<ValidatedFilter> filters,
            ExecutionValidationContext context) {
        for (ValidatedFilter filter : filters) {
            ExecutionFieldRule rule = requireFieldRule(filter.getField(), context);
            if (!rule.allowedOperators().contains(filter.getOperator())) {
                throw new IllegalArgumentException(
                        "operator not allowed for field " + filter.getField() + ": " + filter.getOperator());
            }
        }
    }

    private static ExecutionFieldRule requireFieldRule(
            String field,
            ExecutionValidationContext context) {
        ExecutionFieldRule rule = context.domainProjection().fieldRules().get(field);
        if (rule == null) {
            throw new IllegalArgumentException("unknown field in execution projection: " + field);
        }
        return rule;
    }

    private static List<String> normalizeKernelSelectFields(
            List<String> fields,
            ExecutionValidationContext context) {
        if (fields == null || fields.isEmpty()) {
            return context.domainProjection().defaultSelectFields();
        }
        LinkedHashSet<String> normalized = new LinkedHashSet<>();
        for (String field : fields) {
            if (field == null || field.isBlank()) {
                throw new IllegalArgumentException("selectFields must not contain blank values");
            }
            normalized.add(field.trim());
        }
        return List.copyOf(normalized);
    }

    private static void validateKernelSelectFields(
            List<String> selectFields,
            ExecutionValidationContext context) {
        for (String field : selectFields) {
            requireFieldRule(field, context);
        }
    }

    private int defaultKernelPageSize(ExecutionValidationContext context) {
        int configuredDefault = properties.getQuery().getDefaultSize();
        int maxPageSize = maxKernelPageSize(context);
        return maxPageSize > 0 ? Math.min(configuredDefault, maxPageSize) : 0;
    }

    private int maxKernelPageSize(ExecutionValidationContext context) {
        int configuredMax = properties.getQuery().getMaxSize();
        int projectionMax = context.domainProjection().maxPageSize();
        int scopeMaxRows = context.executionScope().maxResultRows();

        int max = configuredMax;
        max = Math.min(max, projectionMax);
        max = Math.min(max, scopeMaxRows);
        return max;
    }
}
