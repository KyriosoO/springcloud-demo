package com.dylan.agent.capability.query;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.QueryContextMode;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.DomainView;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;
import com.dylan.agent.adapter.api.AdapterRole;

/** QUERY plan 校验器。将 Runtime 原始 AgentPlan 校验为 ValidatedQueryPlan，复用 FilterNormalizer、FieldConstraintValidator、QueryMergeEngine 等底层组件，保持现有 filter/MERGE/pagination 语义。 */
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

    /** 将 Runtime 原始 QUERY plan 校验为 ValidatedQueryPlan，执行 filter 规范化、MERGE 合并、selectFields/pagination 校验。 */
    public com.dylan.agent.capability.model.ValidatedQueryPlan validate(CapabilityValidationContext context) {
        PlanGenerateResponse response = context.planResponse();
        AgentPlan plan = response.getPlan();
        RuntimeQueryContext previousQuery = context.previousQuery();

        if (plan.getIntent() != AgentIntent.QUERY) {
            throw new AgentPlanValidationException("Plan intent 必须为 QUERY。");
        }

        AgentQuerySpec query = requireQuery(plan);
        DomainView domain = requireDomain(plan.getDomain());

        QueryContextMode mode = query.getContextMode() != null
                ? query.getContextMode() : QueryContextMode.REPLACE;
        Set<String> removeFields = normalizeRemoveFields(query.getRemoveFields(), domain);

        List<ValidatedFilter> finalFilters;
        List<String> selectFields;
        int page;
        int size;

        if (mode == QueryContextMode.MERGE) {
            requireMergeContext(plan, previousQuery);

            List<ValidatedFilter> previousFilters =
                    normalizePreviousFilters(previousQuery, domain);
            fieldConstraintValidator.validateFinalQuery(previousFilters, domain);

            List<ValidatedFilter> changes =
                    filterNormalizer.normalizeAll(query.getFilters(), domain);
            fieldConstraintValidator.validateChanges(changes, removeFields);

            finalFilters = queryMergeEngine.merge(
                    previousFilters, changes, removeFields);

            selectFields = resolveMergedSelectFields(query, previousQuery, domain);

            boolean criteriaChanged = !changes.isEmpty() || !removeFields.isEmpty();
            page = resolveMergedPage(query, previousQuery, criteriaChanged);
            size = resolveMergedSize(query, previousQuery);
        } else {
            if (!removeFields.isEmpty()) {
                throw new AgentPlanValidationException("REPLACE QUERY 不允许 removeFields。");
            }

            List<ValidatedFilter> changes =
                    filterNormalizer.normalizeAll(query.getFilters(), domain);
            fieldConstraintValidator.validateChanges(changes, removeFields);

            if (changes.isEmpty()) {
                throw new AgentPlanValidationException("QUERY Plan 至少需要一个过滤条件。");
            }

            finalFilters = changes;
            selectFields = normalizeSelectFields(query.getSelectFields(), domain);
            page = query.getPage() != null ? query.getPage() : 1;
            size = query.getSize() != null
                    ? query.getSize() : properties.getQuery().getDefaultSize();
        }

        fieldConstraintValidator.validateFinalQuery(finalFilters, domain);

        if (finalFilters.size() > properties.getQuery().getMaxFilters()) {
            throw new AgentPlanValidationException(
                    "过滤条件数量超过上限 " + properties.getQuery().getMaxFilters());
        }
        validatePagination(page, size);

        return new com.dylan.agent.capability.model.ValidatedQueryPlan(plan.getDomain(),
                new ValidatedQuery(finalFilters, selectFields, page, size));
    }

    private DomainView requireDomain(String domain) {
        if (domain == null || domain.isBlank()) {
            throw new AgentPlanValidationException("domain 不能为空。");
        }
        try {
            return domainCatalogView.requireDomain(domain, AdapterRole.QUERYABLE);
        } catch (IllegalArgumentException ex) {
            throw new AgentPlanValidationException("不支持的 domain: " + domain);
        }
    }

    private AgentQuerySpec requireQuery(AgentPlan plan) {
        AgentQuerySpec query = plan.getQuery();
        if (query == null) {
            throw new AgentPlanValidationException("QUERY Plan 缺少 query 字段。");
        }
        if (plan.getClarify() != null) {
            throw new AgentPlanValidationException("QUERY Plan 不能同时携带 clarify。");
        }
        if (plan.getAggregate() != null) {
            throw new AgentPlanValidationException("QUERY Plan 不能同时携带 aggregate。");
        }
        return query;
    }

    private void requireMergeContext(AgentPlan plan, RuntimeQueryContext previousQuery) {
        if (previousQuery == null || !plan.getDomain().equals(previousQuery.getDomain())) {
            throw new AgentPlanValidationException("MERGE QUERY 缺少可用的上一轮查询上下文。");
        }
    }

    private List<ValidatedFilter> normalizePreviousFilters(
            RuntimeQueryContext previousQuery, DomainView domain) {
        try {
            return filterNormalizer.normalizeAll(previousQuery.getFilters(), domain);
        } catch (AgentPlanValidationException e) {
            throw new AgentPlanValidationException(
                    "上一轮查询上下文不合法：" + e.getMessage());
        }
    }

    private List<String> resolveMergedSelectFields(
            AgentQuerySpec query, RuntimeQueryContext previousQuery, DomainView domain) {
        if (query.getSelectFields() == null || query.getSelectFields().isEmpty()) {
            return normalizeSelectFields(previousQuery.getSelectFields(), domain);
        }
        return normalizeSelectFields(query.getSelectFields(), domain);
    }

    private int resolveMergedPage(
            AgentQuerySpec query, RuntimeQueryContext previousQuery, boolean criteriaChanged) {
        if (criteriaChanged) {
            return 1;
        }
        return query.getPage() != null ? query.getPage() : previousQuery.getPage();
    }

    private int resolveMergedSize(AgentQuerySpec query, RuntimeQueryContext previousQuery) {
        return query.getSize() != null ? query.getSize() : previousQuery.getSize();
    }

    private Set<String> normalizeRemoveFields(List<String> fields, DomainView domain) {
        if (fields == null || fields.isEmpty()) {
            return Set.of();
        }
        Set<String> allowed = domain.capabilityFields();
        Set<String> result = new LinkedHashSet<>();
        for (String field : fields) {
            if (field == null || field.isBlank()) {
                throw new AgentPlanValidationException("removeFields 不能包含空字段。");
            }
            String normalized = field.trim();
            if (!allowed.contains(normalized)) {
                throw new AgentPlanValidationException("removeFields 包含未知字段: " + normalized);
            }
            result.add(normalized);
        }
        return result;
    }

    private List<String> normalizeSelectFields(List<String> fields, DomainView domain) {
        if (fields == null || fields.isEmpty()) {
            return domain.defaultSelectFields();
        }
        if (fields.size() > 10) {
            throw new AgentPlanValidationException("selectFields 最多 10 个。");
        }
        Set<String> allowed = domain.capabilityFields();
        Set<String> result = new LinkedHashSet<>();
        for (String field : fields) {
            if (field != null && !field.isBlank()) {
                String normalized = field.trim();
                if (!allowed.contains(normalized)) {
                    throw new AgentPlanValidationException("未知 selectField: " + normalized);
                }
                result.add(normalized);
            }
        }
        return result.isEmpty()
                ? domain.defaultSelectFields()
                : List.copyOf(result);
    }

    private void validatePagination(int page, int size) {
        if (page < 1) {
            throw new AgentPlanValidationException("page 必须 >= 1。");
        }
        if (size < 1 || size > properties.getQuery().getMaxSize()) {
            throw new AgentPlanValidationException(
                    "size 必须在 1～" + properties.getQuery().getMaxSize() + " 之间。");
        }
        long from;
        try {
            from = Math.multiplyExact((long) page - 1, size);
        } catch (ArithmeticException e) {
            throw new AgentPlanValidationException("分页偏移计算溢出。");
        }
        if (from + size > properties.getQuery().getMaxResultWindow()) {
            throw new AgentPlanValidationException(
                    "分页范围超出上限 " + properties.getQuery().getMaxResultWindow());
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
