package com.dylan.agent.capability.query;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.enums.QueryContextMode;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.core.KernelExecutionException;
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
        QueryContextMode contextMode = query.getContextMode() == null
                ? QueryContextMode.REPLACE
                : query.getContextMode();
        BoundQuery boundQuery = bindQuery(query, context, domain, contextMode);
        List<ValidatedFilter> filters = boundQuery.filters();
        validateKernelFilters(filters, context, domain);
        List<String> selectFields = boundQuery.selectFields();
        validateKernelSelectFields(selectFields, context, domain);
        int page = boundQuery.page();
        int size = boundQuery.size();
        int maxPageSize = maxKernelPageSize(context);
        if (page <= 0 || size <= 0 || size > maxPageSize) {
            throw new IllegalArgumentException("invalid query pagination");
        }
        validateKnownPageBounds(page, boundQuery.previous());
        fieldConstraintValidator.validateFinalQuery(
                filters,
                domainCatalogView.requireDomain(domain, AdapterRole.QUERYABLE));
        return new ValidatedQueryPlan(
                KERNEL_CAPABILITY_ID,
                domain,
                new ValidatedQuery(filters, selectFields, page, size));
    }

    private BoundQuery bindQuery(
            AgentQuerySpec query,
            ExecutionValidationContext context,
            String domain,
            QueryContextMode contextMode) {
        if (contextMode == QueryContextMode.REPLACE) {
            List<ValidatedFilter> filters = toValidatedFilters(query.getFilters());
            if (filters.isEmpty()) {
                throw new IllegalArgumentException("query filters must not be empty");
            }
            return new BoundQuery(
                    filters,
                    normalizeKernelSelectFields(query.getSelectFields(), context),
                    query.getPage() == null ? 1 : query.getPage(),
                    query.getSize() == null ? defaultKernelPageSize(context) : query.getSize(),
                    null);
        }

        QueryCapabilityContextPayload previous = previousQueryContext(context);
        List<ValidatedFilter> previousFilters = toValidatedFilters(previous.filters());
        List<ValidatedFilter> changes = toValidatedFilters(query.getFilters());
        Set<String> removeFields = normalizeRemoveFields(query.getRemoveFields());
        validateKernelFilters(changes, context, domain);
        validateKernelRemoveFields(removeFields, context, domain);
        fieldConstraintValidator.validateChanges(changes, removeFields);
        List<ValidatedFilter> merged = queryMergeEngine.merge(previousFilters, changes, removeFields);
        if (merged.isEmpty()) {
            throw new KernelExecutionException(
                    KernelErrorCode.PLAN_VALIDATION_FAILED,
                    "当前查询条件为空，请重新说明查询条件。");
        }
        List<String> selectFields = query.getSelectFields() == null || query.getSelectFields().isEmpty()
                ? previous.selectFields()
                : normalizeKernelSelectFields(query.getSelectFields(), context);
        int page = query.getPage() == null ? previous.page() : query.getPage();
        int size = query.getSize() == null ? previous.size() : query.getSize();
        return new BoundQuery(merged, selectFields, page, size, previous);
    }

    private QueryCapabilityContextPayload previousQueryContext(ExecutionValidationContext context) {
        return context.contextSnapshots().stream()
                .filter(snapshot -> snapshot.contextType() == RuntimeContextType.QUERY)
                .map(snapshot -> snapshot.payload())
                .filter(QueryCapabilityContextPayload.class::isInstance)
                .map(QueryCapabilityContextPayload.class::cast)
                .findFirst()
                .orElseThrow(() -> new KernelExecutionException(
                        KernelErrorCode.PLAN_VALIDATION_FAILED,
                        "请先完成一次查询后再继续翻页或修改条件。"));
    }

    private static Set<String> normalizeRemoveFields(List<String> removeFields) {
        if (removeFields == null || removeFields.isEmpty()) {
            return Set.of();
        }
        return removeFields.stream()
                .map(field -> {
                    if (field == null || field.isBlank()) {
                        throw new IllegalArgumentException("removeFields must not contain blank values");
                    }
                    return field.trim();
                })
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }

    private void validateKnownPageBounds(
            int page,
            QueryCapabilityContextPayload previous) {
        if (previous == null
                || !Boolean.TRUE.equals(previous.totalExact())
                || previous.totalPages() == null) {
            return;
        }
        if (page > previous.totalPages()) {
            throw new KernelExecutionException(
                    KernelErrorCode.PLAN_VALIDATION_FAILED,
                    "请求页码超过当前结果总页数，请调整页码后重试。");
        }
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

    private void validateKernelFilters(
            List<ValidatedFilter> filters,
            ExecutionValidationContext context,
            String domain) {
        for (ValidatedFilter filter : filters) {
            ExecutionFieldRule rule = requireFieldRule(filter.getField(), context, domain);
            if (!rule.allowedOperators().contains(filter.getOperator())) {
                throw new IllegalArgumentException(
                        "operator not allowed for field " + filter.getField() + ": " + filter.getOperator());
            }
        }
    }

    private void validateKernelRemoveFields(
            Set<String> fields,
            ExecutionValidationContext context,
            String domain) {
        for (String field : fields) {
            requireFieldRule(field, context, domain);
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

    private ExecutionFieldRule requireFieldRule(
            String field,
            ExecutionValidationContext context,
            String domain) {
        ExecutionFieldRule rule = context.domainProjection().fieldRules().get(field);
        if (rule != null) {
            return rule;
        }
        if (fieldExistsInCatalog(domain, field)) {
            throw new KernelExecutionException(
                    KernelErrorCode.FIELD_FORBIDDEN,
                    "没有权限访问请求的字段，请调整字段后重试。");
        }
        throw new IllegalArgumentException("unknown field in execution projection: " + field);
    }

    private boolean fieldExistsInCatalog(String domain, String field) {
        return domainCatalogView.findDomain(domain, AdapterRole.QUERYABLE)
                .map(view -> view.fields().containsKey(field))
                .orElse(false);
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

    private void validateKernelSelectFields(
            List<String> selectFields,
            ExecutionValidationContext context,
            String domain) {
        for (String field : selectFields) {
            requireFieldRule(field, context, domain);
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

    private record BoundQuery(
            List<ValidatedFilter> filters,
            List<String> selectFields,
            int page,
            int size,
            QueryCapabilityContextPayload previous) {
    }
}
