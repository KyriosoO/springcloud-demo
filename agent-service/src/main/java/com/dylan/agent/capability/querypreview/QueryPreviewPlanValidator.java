package com.dylan.agent.capability.querypreview;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import org.springframework.stereotype.Component;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;

/** query.preview 校验器：复用 QUERYABLE domain 投影，只收敛字段和分页窗口。 */
@Component
public class QueryPreviewPlanValidator
        implements CapabilityPlanValidator<QueryAgentPlan, ValidatedQueryPreviewPlan> {

    public static final String KERNEL_CAPABILITY_ID = "query.preview";

    private final AgentProperties properties;

    public QueryPreviewPlanValidator(AgentProperties properties) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
    }

    @Override
    public ValidatedQueryPreviewPlan validate(QueryAgentPlan rawPlan, ExecutionValidationContext context) {
        Objects.requireNonNull(rawPlan, "rawPlan must not be null");
        Objects.requireNonNull(context, "context must not be null");
        if (!KERNEL_CAPABILITY_ID.equals(context.capabilityId())) {
            throw new IllegalArgumentException("capabilityId mismatch");
        }
        String domain = context.domainProjection().domain()
                .orElseThrow(() -> new IllegalArgumentException("QUERY_PREVIEW requires domain projection"));
        AgentQuerySpec query = Objects.requireNonNull(rawPlan.getQuery(), "query must not be null");
        List<ValidatedFilter> filters = QueryPlanValidator.toValidatedFilters(query.getFilters());
        var sorts = QueryPlanValidator.toValidatedSorts(query.getSorts());
        if (filters.isEmpty()) {
            throw new IllegalArgumentException("query preview filters must not be empty");
        }
        QueryPlanValidator.validateKernelFilters(filters, context);
        QueryPlanValidator.validateKernelSorts(sorts, context);
        List<String> previewFields = normalizePreviewFields(query.getSelectFields(), context);
        int previewSize = previewSize(query, context);
        ValidatedQuery previewQuery = toPreviewQuery(filters, previewFields, sorts, previewSize);
        return new ValidatedQueryPreviewPlan(
                KERNEL_CAPABILITY_ID,
                domain,
                previewQuery,
                previewFields,
                previewSize);
    }

    private static List<String> normalizePreviewFields(
            List<String> fields,
            ExecutionValidationContext context) {
        List<String> source = fields == null || fields.isEmpty()
                ? context.domainProjection().defaultSelectFields()
                : fields;
        LinkedHashSet<String> normalized = new LinkedHashSet<>();
        for (String field : source) {
            if (field == null || field.isBlank()) {
                throw new IllegalArgumentException("preview fields must not contain blank values");
            }
            String normalizedField = field.trim();
            requireFieldRule(normalizedField, context);
            normalized.add(normalizedField);
        }
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("preview fields must not be empty");
        }
        return List.copyOf(normalized);
    }

    private int previewSize(AgentQuerySpec query, ExecutionValidationContext context) {
        int page = query.getPage() == null ? 1 : query.getPage();
        if (page != 1) {
            throw new IllegalArgumentException("query preview only supports first page");
        }
        int max = maxPreviewSize(context);
        int size = query.getSize() == null ? max : query.getSize();
        if (size <= 0 || size > max) {
            throw new IllegalArgumentException("invalid query preview size");
        }
        return size;
    }

    private int maxPreviewSize(ExecutionValidationContext context) {
        int max = properties.getQuery().getDefaultSize();
        max = Math.min(max, context.domainProjection().maxPageSize());
        max = Math.min(max, context.executionScope().maxResultRows());
        return max;
    }

    private static ValidatedQuery toPreviewQuery(
            List<ValidatedFilter> filters,
            List<String> previewFields,
            List<com.dylan.agent.adapter.api.query.ValidatedSort> sorts,
            int previewSize) {
        return new ValidatedQuery(filters, previewFields, sorts, 1, previewSize);
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
}
