package com.dylan.agent.capability.query;

import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.AgentQuerySortParameter;

/** 包级私有映射器，将 Kernel 已校验查询计划转换为 AgentQueryParameters（响应 DTO）。 */
final class QueryParameterMapper {

    private QueryParameterMapper() {
    }

    static AgentQueryParameters toQueryParameters(ValidatedQueryPlan plan) {
        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain(plan.domain().orElseThrow());
        parameters.setFilters(plan.query().getFilters().stream()
                .map(filter -> {
                    AgentQueryFilterParameter parameter =
                            new AgentQueryFilterParameter();
                    parameter.setField(filter.getField());
                    parameter.setOperator(filter.getOperator());
                    parameter.setValue(filter.getValue());
                    parameter.setValues(filter.getValues().isEmpty()
                            ? null : filter.getValues());
                    return parameter;
                })
                .toList());
        parameters.setSelectFields(plan.query().getSelectFields());
        parameters.setSorts(plan.query().getSorts().stream()
                .map(sort -> {
                    AgentQuerySortParameter parameter = new AgentQuerySortParameter();
                    parameter.setField(sort.getField());
                    parameter.setDirection(sort.getDirection());
                    return parameter;
                })
                .toList());
        parameters.setPage(plan.query().getPage());
        parameters.setSize(plan.query().getSize());
        return parameters;
    }
}
