package com.dylan.agent.capability.querypreview;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.QueryPreviewResult;
import com.dylan.agent.api.response.QueryPreviewResultPayload;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.handler.HandlerResult;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class QueryPreviewCapabilityHandler
        implements CapabilityHandler<ValidatedQueryPreviewPlan, QueryPreviewResultPayload> {

    @Override
    public HandlerResult<QueryPreviewResultPayload> execute(
            ValidatedQueryPreviewPlan plan,
            ExecutionContext context) {
        QueryableAdapter adapter = context.requireAdapter(QueryableAdapter.class);
        AdapterQueryResult adapterResult = adapter.query(plan.query());
        QueryPreviewResultPayload payload = new QueryPreviewResultPayload(
                toQueryParameters(plan),
                toPreviewResult(plan, adapterResult));
        return HandlerResult.of(payload);
    }

    private static AgentQueryParameters toQueryParameters(ValidatedQueryPreviewPlan plan) {
        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain(plan.domain().orElseThrow());
        parameters.setFilters(plan.query().getFilters().stream()
                .map(QueryPreviewCapabilityHandler::toFilterParameter)
                .toList());
        parameters.setSelectFields(plan.previewFields());
        parameters.setPage(1);
        parameters.setSize(plan.previewSize());
        return parameters;
    }

    private static AgentQueryFilterParameter toFilterParameter(ValidatedFilter filter) {
        AgentQueryFilterParameter parameter = new AgentQueryFilterParameter();
        parameter.setField(filter.getField());
        parameter.setOperator(filter.getOperator());
        parameter.setValue(filter.getValue());
        parameter.setValues(filter.getValues().isEmpty() ? null : filter.getValues());
        return parameter;
    }

    private static QueryPreviewResult toPreviewResult(
            ValidatedQueryPreviewPlan plan,
        AdapterQueryResult adapterResult) {
        QueryPreviewResult result = new QueryPreviewResult();
        result.setColumns(plan.previewFields());
        result.setSampleRows(sampleRows(plan, adapterResult));
        result.setTotalEstimate(adapterResult.getTotal());
        result.setTotalExact(adapterResult.isTotalExact());
        result.setPreviewSize(plan.previewSize());
        return result;
    }

    private static List<Map<String, Object>> sampleRows(
            ValidatedQueryPreviewPlan plan,
            AdapterQueryResult adapterResult) {
        return adapterResult.getRows().stream()
                .limit(plan.previewSize())
                .map(row -> filterRow(row, plan.previewFields()))
                .toList();
    }

    private static Map<String, Object> filterRow(Map<String, Object> row, List<String> previewFields) {
        Map<String, Object> filtered = new LinkedHashMap<>();
        for (String field : previewFields) {
            if (row.containsKey(field)) {
                filtered.put(field, row.get(field));
            }
        }
        return filtered;
    }
}
