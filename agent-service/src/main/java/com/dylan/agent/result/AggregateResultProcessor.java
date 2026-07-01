package com.dylan.agent.result;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentAggregateRow;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.FieldPolicy;
import com.dylan.agent.security.AgentPermissionService;

/** 聚合结果处理器：display 权限检查 + 脱敏 + 安全响应构造。参照 AgentResultProcessor 模式。 */
@Component
public class AggregateResultProcessor {

    private final AgentPermissionService permissionService;
    private final FieldMaskerRegistry maskerRegistry;

    public AggregateResultProcessor(AgentPermissionService permissionService, FieldMaskerRegistry maskerRegistry) {
        this.permissionService = permissionService;
        this.maskerRegistry = maskerRegistry;
    }

    /** 处理聚合结果：逐行检查 groupBy/metric 的 display 权限并脱敏 metric 值。 */
    public AgentAggregateResult process(AdapterAggregateResult rawResult, ValidatedAggregateQuery query,
                                         AgentUserContext userContext, String domain) {
        List<AgentAggregateRow> safeRows = new ArrayList<>();
        for (Map<String, Object> row : rawResult.getRows()) {
            safeRows.add(processRow(row, query, userContext, domain));
        }

        List<String> metricAliases = query.getMetrics().stream()
                .map(ValidatedAggregateMetric::getAlias)
                .toList();

        AgentAggregateResult result = new AgentAggregateResult();
        result.setDomain(domain);
        result.setGroupByFields(query.getGroupByFields());
        result.setMetricAliases(metricAliases);
        result.setRows(safeRows);
        result.setPartial(rawResult.isPartial());
        return result;
    }

    private AgentAggregateRow processRow(Map<String, Object> row, ValidatedAggregateQuery query,
                                          AgentUserContext userContext, String domain) {
        Map<String, Object> safeGroups = new LinkedHashMap<>();
        Map<String, Object> safeMetrics = new LinkedHashMap<>();

        for (String field : query.getGroupByFields()) {
            Object value = row.get(field);
            FieldPolicy policy = permissionService.getDisplayPolicy(userContext, domain, field);
            if (userContext.getRoles().stream().noneMatch(r -> policy.getDisplayRoles().contains(r))) {
                safeGroups.put(field, "***");
            } else {
                safeGroups.put(field, sanitizeScalar(value));
            }
        }

        for (ValidatedAggregateMetric metric : query.getMetrics()) {
            String alias = metric.getAlias();
            Object value = row.get(alias);
            if (metric.getFunction() == AggregateFunction.COUNT && metric.getField() == null) {
                safeMetrics.put(alias, sanitizeScalar(value));
                continue;
            }
            FieldPolicy policy = permissionService.getDisplayPolicy(userContext, domain, metric.getField());
            if (userContext.getRoles().stream().noneMatch(r -> policy.getDisplayRoles().contains(r))) {
                safeMetrics.put(alias, "***");
            } else {
                Object sanitized = sanitizeScalar(value);
                Object masked = maskerRegistry.mask(policy.getMaskType(), sanitized);
                safeMetrics.put(alias, masked);
            }
        }

        AgentAggregateRow aggregateRow = new AgentAggregateRow();
        aggregateRow.setGroups(safeGroups);
        aggregateRow.setMetrics(safeMetrics);
        return aggregateRow;
    }

    private Object sanitizeScalar(Object value) {
        if (value == null) return null;
        if (value instanceof String || value instanceof Number || value instanceof Boolean) {
            return value;
        }
        return null;
    }
}
