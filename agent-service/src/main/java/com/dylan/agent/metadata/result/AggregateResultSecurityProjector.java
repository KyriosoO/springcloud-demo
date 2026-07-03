package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentAggregateRow;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

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
    public FilteredResult<AggregateAgentResultPayload> filter(AggregateAgentResultPayload candidate, ExecutionScope scope) {
        String domain = candidate.getAggregateResult() == null ? null : candidate.getAggregateResult().getDomain();
        requireDomainWhenData(domain, hasFieldBearingData(candidate));
        AggregateAgentResultPayload filtered = new AggregateAgentResultPayload(
                filterAggregate(domain, candidate.getAggregateResult(), scope));
        return new FilteredResult<>(filtered, "聚合完成", "聚合结果已按当前执行范围过滤和脱敏");
    }

    private AgentAggregateResult filterAggregate(
            String domain,
            AgentAggregateResult source,
            ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        AgentAggregateResult target = new AgentAggregateResult();
        target.setDomain(source.getDomain());
        target.setGroupByFields(maskingSupport.filterFields(domain, source.getGroupByFields(), scope));
        target.setMetricAliases(copyList(source.getMetricAliases()));
        target.setRows(source.getRows() == null ? null : source.getRows().stream()
                .map(row -> filterRow(domain, row, scope))
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

    private static boolean hasFieldBearingData(AggregateAgentResultPayload candidate) {
        AgentAggregateResult result = candidate.getAggregateResult();
        return result != null
                && (hasItems(result.getGroupByFields()) || hasGroups(result.getRows()));
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
}
