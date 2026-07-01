package com.dylan.agent.capability.query;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.QueryContextMode;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedQueryPlan;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.config.AgentProperties.DomainProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;

/** QUERY plan 校验器。将 Runtime 原始 AgentPlan 校验为 ValidatedQueryPlan，复用 FilterNormalizer、FieldConstraintValidator、QueryMergeEngine 等底层组件，保持现有 filter/MERGE/pagination 语义。 */
@Component
public class QueryPlanValidator {

    private final AgentProperties properties;
    private final FilterNormalizer filterNormalizer;
    private final FieldConstraintValidator fieldConstraintValidator;
    private final QueryMergeEngine queryMergeEngine;

    public QueryPlanValidator(
            AgentProperties properties,
            FilterNormalizer filterNormalizer,
            FieldConstraintValidator fieldConstraintValidator,
            QueryMergeEngine queryMergeEngine) {
        this.properties = properties;
        this.filterNormalizer = filterNormalizer;
        this.fieldConstraintValidator = fieldConstraintValidator;
        this.queryMergeEngine = queryMergeEngine;
    }

    /** 将 Runtime 原始 QUERY plan 校验为 ValidatedQueryPlan，执行 filter 规范化、MERGE 合并、selectFields/pagination 校验。 */
    public ValidatedQueryPlan validate(CapabilityValidationContext context) {
        PlanGenerateResponse response = context.planResponse();
        AgentPlan plan = response.getPlan();
        RuntimeQueryContext previousQuery = context.previousQuery();

        if (plan.getIntent() != AgentIntent.QUERY) {
            throw new AgentPlanValidationException("Plan intent 必须为 QUERY。");
        }

        AgentQuerySpec query = requireQuery(plan);
        DomainProperties dp = requireDomain(plan.getDomain());

        QueryContextMode mode = query.getContextMode() != null
                ? query.getContextMode() : QueryContextMode.REPLACE;
        Set<String> removeFields = normalizeRemoveFields(query.getRemoveFields(), dp);

        List<ValidatedFilter> finalFilters;
        List<String> selectFields;
        int page;
        int size;

        if (mode == QueryContextMode.MERGE) {
            requireMergeContext(plan, previousQuery);

            List<ValidatedFilter> previousFilters =
                    normalizePreviousFilters(previousQuery, dp);
            fieldConstraintValidator.validateFinalQuery(previousFilters, dp);

            List<ValidatedFilter> changes =
                    filterNormalizer.normalizeAll(query.getFilters(), dp);
            fieldConstraintValidator.validateChanges(changes, removeFields);

            finalFilters = queryMergeEngine.merge(
                    previousFilters, changes, removeFields);

            selectFields = resolveMergedSelectFields(query, previousQuery, dp);

            boolean criteriaChanged = !changes.isEmpty() || !removeFields.isEmpty();
            page = resolveMergedPage(query, previousQuery, criteriaChanged);
            size = resolveMergedSize(query, previousQuery);
        } else {
            if (!removeFields.isEmpty()) {
                throw new AgentPlanValidationException("REPLACE QUERY 不允许 removeFields。");
            }

            List<ValidatedFilter> changes =
                    filterNormalizer.normalizeAll(query.getFilters(), dp);
            fieldConstraintValidator.validateChanges(changes, removeFields);

            if (changes.isEmpty()) {
                throw new AgentPlanValidationException("QUERY Plan 至少需要一个过滤条件。");
            }

            finalFilters = changes;
            selectFields = normalizeSelectFields(query.getSelectFields(), dp);
            page = query.getPage() != null ? query.getPage() : 1;
            size = query.getSize() != null
                    ? query.getSize() : properties.getQuery().getDefaultSize();
        }

        fieldConstraintValidator.validateFinalQuery(finalFilters, dp);

        if (finalFilters.size() > properties.getQuery().getMaxFilters()) {
            throw new AgentPlanValidationException(
                    "过滤条件数量超过上限 " + properties.getQuery().getMaxFilters());
        }
        validatePagination(page, size);

        return new ValidatedQueryPlan(plan.getDomain(),
                new ValidatedQuery(finalFilters, selectFields, page, size));
    }

    private DomainProperties requireDomain(String domain) {
        if (domain == null || domain.isBlank()) {
            throw new AgentPlanValidationException("domain 不能为空。");
        }
        DomainProperties dp = properties.getDomains().get(domain);
        if (dp == null) {
            throw new AgentPlanValidationException("不支持的 domain: " + domain);
        }
        return dp;
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
            RuntimeQueryContext previousQuery, DomainProperties dp) {
        try {
            return filterNormalizer.normalizeAll(previousQuery.getFilters(), dp);
        } catch (AgentPlanValidationException e) {
            throw new AgentPlanValidationException(
                    "上一轮查询上下文不合法：" + e.getMessage());
        }
    }

    private List<String> resolveMergedSelectFields(
            AgentQuerySpec query, RuntimeQueryContext previousQuery, DomainProperties dp) {
        if (query.getSelectFields() == null || query.getSelectFields().isEmpty()) {
            return normalizeSelectFields(previousQuery.getSelectFields(), dp);
        }
        return normalizeSelectFields(query.getSelectFields(), dp);
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

    private Set<String> normalizeRemoveFields(List<String> fields, DomainProperties dp) {
        if (fields == null || fields.isEmpty()) {
            return Set.of();
        }
        Set<String> allowed = dp.getFields().keySet();
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

    private List<String> normalizeSelectFields(List<String> fields, DomainProperties dp) {
        if (fields == null || fields.isEmpty()) {
            return dp.getDefaultSelectFields();
        }
        if (fields.size() > 10) {
            throw new AgentPlanValidationException("selectFields 最多 10 个。");
        }
        Set<String> allowed = dp.getFields().keySet();
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
                ? dp.getDefaultSelectFields()
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
}
