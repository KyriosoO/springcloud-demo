package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.AgentAggregateMetricParameter;
import com.dylan.agent.api.response.AgentAggregateOrderParameter;
import com.dylan.agent.api.response.AgentAggregateParameters;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentAggregateRow;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit;

import java.util.LinkedHashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 聚合结果投影器，对 group 字段执行过滤和可选脱敏，metric 默认保留。 */
public final class AggregateResultSecurityProjector implements ResultSecurityProjector<AggregateAgentResultPayload> {

    private final ResultValueMaskingSupport maskingSupport;

    public AggregateResultSecurityProjector(ResultValueMaskingSupport maskingSupport) {
        this.maskingSupport = Objects.requireNonNull(maskingSupport, "maskingSupport must not be null");
    }

    @Override
    public ContractRef supports() { return AgentExecutionContracts.AGGREGATE_RESULT; }

    @Override
    public Class<AggregateAgentResultPayload> payloadType() { return AggregateAgentResultPayload.class; }

    @Override
    public FilteredResult<AggregateAgentResultPayload> filter(
            AggregateAgentResultPayload candidate,
            ExecutionScope scope,
            EffectiveCapabilityResourceLimits limits) {
        int maxRows = limits.require(
                AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                StandardCapabilityResourceLimit.class).maxResultRows();
        String domain = resolveDomain(candidate);
        requireDomainWhenData(domain, hasFieldBearingData(candidate));
        AggregateAgentResultPayload filtered = new AggregateAgentResultPayload(
                filterParameters(domain, candidate.getAggregateParameters(), scope),
                filterAggregate(domain, candidate.getAggregateResult(), scope, maxRows));
        return new FilteredResult<>(filtered, "聚合完成", "聚合结果已按当前执行范围过滤和脱敏");
    }

    private AgentAggregateParameters filterParameters(
            String domain,
            AgentAggregateParameters source,
            ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        AgentAggregateParameters target = new AgentAggregateParameters();
        target.setDomain(source.getDomain() == null || source.getDomain().isBlank() ? domain : source.getDomain());
        target.setFilters(source.getFilters() == null ? null : source.getFilters().stream()
                .map(filter -> maskingSupport.filterAndMaskFilter(domain, filter, scope))
                .filter(Objects::nonNull)
                .toList());
        target.setGroupByFields(maskingSupport.filterFields(domain, source.getGroupByFields(), scope));
        target.setMetrics(filterMetrics(domain, source.getMetrics(), scope));
        target.setOrderBy(filterOrderBy(source.getOrderBy(), target.getGroupByFields(), target.getMetrics()));
        target.setMaxRows(source.getMaxRows());
        return target;
    }

    private AgentAggregateResult filterAggregate(
            String domain,
            AgentAggregateResult source,
            ExecutionScope scope,
            int maxRows) {
        if (source == null) {
            return null;
        }
        AgentAggregateResult target = new AgentAggregateResult();
        target.setDomain(source.getDomain());
        target.setGroupByFields(maskingSupport.filterFields(domain, source.getGroupByFields(), scope));
        target.setMetricAliases(copyList(source.getMetricAliases()));
        target.setRows(source.getRows() == null ? null : source.getRows().stream()
                .map(row -> filterRow(domain, row, scope))
                .limit(maxRows)
                .toList());
        target.setPartial(source.isPartial());
        return target;
    }

    private AgentAggregateRow filterRow(
            String domain,
            AgentAggregateRow source,
            ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        AgentAggregateRow target = new AgentAggregateRow();
        target.setGroups(maskingSupport.filterAndMaskRow(domain, source.getGroups(), scope));
        target.setMetrics(copyMap(source.getMetrics()));
        return target;
    }

    private List<AgentAggregateMetricParameter> filterMetrics(
            String domain,
            List<AgentAggregateMetricParameter> metrics,
            ExecutionScope scope) {
        if (metrics == null) {
            return null;
        }
        Set<String> allowedFields = null;
        if (metrics.stream().anyMatch(metric -> metric != null && metric.getFunction() != AggregateFunction.COUNT)) {
            allowedFields = maskingSupport.allowedFields(domain, scope);
        }
        Set<String> resolvedAllowedFields = allowedFields;
        return metrics.stream()
                .filter(metric -> metric != null
                        && (metric.getFunction() == AggregateFunction.COUNT
                        || metric.getField() != null && resolvedAllowedFields != null
                        && resolvedAllowedFields.contains(metric.getField())))
                .map(metric -> {
                    AgentAggregateMetricParameter target = new AgentAggregateMetricParameter();
                    target.setAlias(metric.getAlias());
                    target.setFunction(metric.getFunction());
                    target.setField(metric.getField());
                    return target;
                })
                .toList();
    }

    private static List<AgentAggregateOrderParameter> filterOrderBy(
            List<AgentAggregateOrderParameter> orderBy,
            List<String> groupByFields,
            List<AgentAggregateMetricParameter> metrics) {
        if (orderBy == null) {
            return null;
        }
        Set<String> allowed = new LinkedHashSet<>();
        if (groupByFields != null) {
            allowed.addAll(groupByFields);
        }
        if (metrics != null) {
            metrics.stream()
                    .map(AgentAggregateMetricParameter::getAlias)
                    .filter(Objects::nonNull)
                    .forEach(allowed::add);
        }
        return orderBy.stream()
                .filter(order -> order != null && allowed.contains(order.getField()))
                .map(order -> {
                    AgentAggregateOrderParameter target = new AgentAggregateOrderParameter();
                    target.setField(order.getField());
                    target.setDirection(order.getDirection());
                    return target;
                })
                .toList();
    }

    private static boolean hasFieldBearingData(AggregateAgentResultPayload candidate) {
        AgentAggregateParameters parameters = candidate.getAggregateParameters();
        AgentAggregateResult result = candidate.getAggregateResult();
        return parameters != null
                && (hasItems(parameters.getFilters())
                || hasItems(parameters.getGroupByFields())
                || hasFieldMetrics(parameters.getMetrics()))
                || result != null
                && (hasItems(result.getGroupByFields()) || hasGroups(result.getRows()));
    }

    private static boolean hasFieldMetrics(List<AgentAggregateMetricParameter> metrics) {
        return metrics != null && metrics.stream()
                .anyMatch(metric -> metric != null && metric.getField() != null && !metric.getField().isBlank());
    }

    private static boolean hasGroups(List<AgentAggregateRow> rows) {
        return rows != null && rows.stream()
                .map(row -> row == null ? null : row.getGroups())
                .anyMatch(groups -> groups != null && !groups.isEmpty());
    }

    private static boolean hasItems(List<?> values) {
        return values != null && !values.isEmpty();
    }

    private static <T> List<T> copyList(List<T> source) {
        return source == null ? null : List.copyOf(source);
    }

    private static Map<String, Object> copyMap(Map<String, Object> source) {
        return source == null ? null : new LinkedHashMap<>(source);
    }

    private static void requireDomainWhenData(String domain, boolean hasFieldBearingData) {
        if (hasFieldBearingData && (domain == null || domain.trim().isEmpty())) {
            throw new IllegalStateException("aggregate result payload missing domain");
        }
    }

    private static String resolveDomain(AggregateAgentResultPayload candidate) {
        if (candidate.getAggregateParameters() != null
                && candidate.getAggregateParameters().getDomain() != null
                && !candidate.getAggregateParameters().getDomain().isBlank()) {
            return candidate.getAggregateParameters().getDomain();
        }
        return candidate.getAggregateResult() == null ? null : candidate.getAggregateResult().getDomain();
    }
}
