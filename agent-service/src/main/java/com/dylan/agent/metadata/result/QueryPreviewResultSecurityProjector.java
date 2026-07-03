package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.QueryPreviewResult;
import com.dylan.agent.api.response.QueryPreviewResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.List;
import java.util.Map;
import java.util.Objects;

/** query.preview 结果投影器，复用统一 helper 执行字段裁剪和值级脱敏。 */
public final class QueryPreviewResultSecurityProjector
        implements ResultSecurityProjector<QueryPreviewResultPayload> {

    private final ResultValueMaskingSupport maskingSupport;

    public QueryPreviewResultSecurityProjector(ResultValueMaskingSupport maskingSupport) {
        this.maskingSupport = Objects.requireNonNull(maskingSupport, "maskingSupport must not be null");
    }

    @Override
    public ContractRef supports() {
        return AgentExecutionContracts.QUERY_PREVIEW_RESULT;
    }

    @Override
    public Class<QueryPreviewResultPayload> payloadType() {
        return QueryPreviewResultPayload.class;
    }

    @Override
    public FilteredResult<QueryPreviewResultPayload> filter(QueryPreviewResultPayload candidate, ExecutionScope scope) {
        String domain = candidate.getQueryParameters() == null ? null : candidate.getQueryParameters().getDomain();
        requireDomainWhenData(domain, hasFieldBearingData(candidate));
        QueryPreviewResultPayload filtered = new QueryPreviewResultPayload(
                filterParameters(domain, candidate.getQueryParameters(), scope),
                filterPreview(domain, candidate.getPreviewResult(), scope));
        return new FilteredResult<>(filtered, "查询预览完成", "查询预览结果已按当前执行范围过滤和脱敏");
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

    private QueryPreviewResult filterPreview(
            String domain,
            QueryPreviewResult source,
            ExecutionScope scope) {
        if (source == null) {
            return null;
        }
        QueryPreviewResult target = new QueryPreviewResult();
        target.setColumns(maskingSupport.filterFields(domain, source.getColumns(), scope));
        target.setSampleRows(source.getSampleRows() == null ? null : source.getSampleRows().stream()
                .map(row -> maskingSupport.filterAndMaskRow(domain, row, scope))
                .toList());
        target.setTotalEstimate(source.getTotalEstimate());
        target.setTotalExact(source.isTotalExact());
        target.setPreviewSize(source.getPreviewSize());
        return target;
    }

    private static boolean hasFieldBearingData(QueryPreviewResultPayload candidate) {
        AgentQueryParameters parameters = candidate.getQueryParameters();
        QueryPreviewResult result = candidate.getPreviewResult();
        return parameters != null
                && (hasItems(parameters.getSelectFields()) || hasItems(parameters.getFilters()))
                || result != null
                && (hasItems(result.getColumns()) || hasRows(result.getSampleRows()));
    }

    private static boolean hasRows(List<Map<String, Object>> rows) {
        return rows != null && rows.stream().anyMatch(row -> row != null && !row.isEmpty());
    }

    private static boolean hasItems(List<?> values) {
        return values != null && !values.isEmpty();
    }

    private static void requireDomainWhenData(String domain, boolean hasFieldBearingData) {
        if (hasFieldBearingData && (domain == null || domain.trim().isEmpty())) {
            throw new IllegalStateException("query preview result payload missing domain");
        }
    }
}
