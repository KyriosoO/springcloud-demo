package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.QueryPreviewResult;
import com.dylan.agent.api.response.QueryPreviewResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** query.preview 结果投影器，按执行范围保留允许展示的预览字段。 */
public final class QueryPreviewResultSecurityProjector
        implements ResultSecurityProjector<QueryPreviewResultPayload> {

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
        Set<String> allowedFields = domain == null ? Set.of() : scope.allowedFields().getOrDefault(domain, Set.of());
        QueryPreviewResultPayload filtered = new QueryPreviewResultPayload(
                filterParameters(candidate.getQueryParameters(), allowedFields),
                filterPreview(candidate.getPreviewResult(), allowedFields));
        return new FilteredResult<>(filtered, "查询预览完成", "查询预览结果已按当前执行范围过滤");
    }

    private static AgentQueryParameters filterParameters(
            AgentQueryParameters source,
            Set<String> allowedFields) {
        if (source == null) {
            return null;
        }
        AgentQueryParameters target = new AgentQueryParameters();
        target.setDomain(source.getDomain());
        target.setFilters(source.getFilters() == null ? null : source.getFilters().stream()
                .filter(filter -> allowedFields.contains(filter.getField()))
                .map(QueryPreviewResultSecurityProjector::copyFilter)
                .toList());
        target.setSelectFields(filterFields(source.getSelectFields(), allowedFields));
        target.setPage(source.getPage());
        target.setSize(source.getSize());
        return target;
    }

    private static AgentQueryFilterParameter copyFilter(AgentQueryFilterParameter source) {
        AgentQueryFilterParameter target = new AgentQueryFilterParameter();
        target.setField(source.getField());
        target.setOperator(source.getOperator());
        target.setValue(source.getValue());
        target.setValues(source.getValues());
        return target;
    }

    private static QueryPreviewResult filterPreview(
            QueryPreviewResult source,
            Set<String> allowedFields) {
        if (source == null) {
            return null;
        }
        QueryPreviewResult target = new QueryPreviewResult();
        target.setColumns(filterFields(source.getColumns(), allowedFields));
        target.setSampleRows(source.getSampleRows() == null ? null : source.getSampleRows().stream()
                .map(row -> filterRow(row, allowedFields))
                .toList());
        target.setTotalEstimate(source.getTotalEstimate());
        target.setTotalExact(source.isTotalExact());
        target.setPreviewSize(source.getPreviewSize());
        return target;
    }

    private static List<String> filterFields(List<String> fields, Set<String> allowedFields) {
        if (fields == null) {
            return null;
        }
        return fields.stream()
                .filter(allowedFields::contains)
                .toList();
    }

    private static Map<String, Object> filterRow(Map<String, Object> row, Set<String> allowedFields) {
        Map<String, Object> filtered = new LinkedHashMap<>();
        row.forEach((field, value) -> {
            if (allowedFields.contains(field)) {
                filtered.put(field, value);
            }
        });
        return filtered;
    }
}
