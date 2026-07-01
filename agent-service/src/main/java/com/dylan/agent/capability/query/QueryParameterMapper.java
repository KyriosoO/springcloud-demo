package com.dylan.agent.capability.query;

import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.capability.model.ValidatedQueryPlan;

/** 包级私有映射器，将 ValidatedQueryPlan 转换为 AgentQueryParameters（响应 DTO）。 */
final class QueryParameterMapper {

    private QueryParameterMapper() {
    }

    static AgentQueryParameters toQueryParameters(ValidatedQueryPlan plan) {
        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain(plan.domain());
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
        parameters.setPage(plan.query().getPage());
        parameters.setSize(plan.query().getSize());
        return parameters;
    }
}
