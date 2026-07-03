package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.List;
import java.util.Map;
import java.util.Objects;

/** 查询结果投影器，统一执行字段裁剪和值级脱敏。 */
public final class QueryResultSecurityProjector implements ResultSecurityProjector<QueryAgentResultPayload> {

    private final ResultValueMaskingSupport maskingSupport;

    public QueryResultSecurityProjector(ResultValueMaskingSupport maskingSupport) {
        this.maskingSupport = Objects.requireNonNull(maskingSupport, "maskingSupport must not be null");
    }

    @Override
    public ContractRef supports() { return AgentExecutionContracts.QUERY_RESULT; }

    @Override
    public Class<QueryAgentResultPayload> payloadType() { return QueryAgentResultPayload.class; }

    @Override
    public FilteredResult<QueryAgentResultPayload> filter(QueryAgentResultPayload candidate, ExecutionScope scope) {
        String domain = candidate.getQueryParameters() == null ? null : candidate.getQueryParameters().getDomain();
        requireDomainWhenData(domain, hasFieldBearingData(candidate));
        QueryAgentResultPayload filtered = new QueryAgentResultPayload(
                filterParameters(domain, candidate.getQueryParameters(), scope),
                filterResult(domain, candidate.getQueryResult(), scope));
        return new FilteredResult<>(filtered, "查询完成", "查询结果已按当前执行范围过滤和脱敏");
    }

    private AgentQueryParameters filterParameters(
            String domain,
            AgentQueryParameters source,
            ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        AgentQueryParameters target = new AgentQueryParameters();
        target.setDomain(source.getDomain());
        target.setFilters(source.getFilters() == null ? null : source.getFilters().stream()
                .map(filter -> maskingSupport.filterAndMaskFilter(domain, filter, scope))
                .filter(Objects::nonNull)
                .toList());
        target.setSelectFields(maskingSupport.filterFields(domain, source.getSelectFields(), scope));
        target.setPage(source.getPage());
        target.setSize(source.getSize());
        return target;
    }

    private AgentQueryResult filterResult(
            String domain,
            AgentQueryResult source,
            ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        AgentQueryResult target = new AgentQueryResult();
        target.setColumns(maskingSupport.filterFields(domain, source.getColumns(), scope));
        target.setRows(source.getRows() == null ? null : source.getRows().stream()
                .map(row -> maskingSupport.filterAndMaskRow(domain, row, scope))
                .toList());
        target.setTotal(source.getTotal());
        target.setTotalExact(source.isTotalExact());
        target.setPage(source.getPage());
        target.setSize(source.getSize());
        return target;
    }

    private static boolean hasFieldBearingData(QueryAgentResultPayload candidate) {
        AgentQueryParameters parameters = candidate.getQueryParameters();
        AgentQueryResult result = candidate.getQueryResult();
        return parameters != null
                && (hasItems(parameters.getSelectFields()) || hasItems(parameters.getFilters()))
                || result != null
                && (hasItems(result.getColumns()) || hasRows(result.getRows()));
    }

    private static boolean hasRows(List<Map<String, Object>> rows) {
        return rows != null && rows.stream().anyMatch(row -> row != null && !row.isEmpty());
    }

    private static boolean hasItems(List<?> values) {
        return values != null && !values.isEmpty();
    }

    private static void requireDomainWhenData(String domain, boolean hasFieldBearingData) {
        if (hasFieldBearingData && (domain == null || domain.trim().isEmpty())) {
            throw new IllegalStateException("query result payload missing domain");
        }
    }
}
