package com.dylan.agent.api.response;

import java.util.List;

import com.dylan.agent.api.enums.AgentOperator;

/** 响应中的单个过滤条件参数，透传给前端展示当前查询条件。 */
public class AgentQueryFilterParameter {

    private String field;
    private AgentOperator operator;
    private String value;
    private List<String> values;

    public AgentQueryFilterParameter() {
    }

    public String getField() {
        return field;
    }

    public void setField(String field) {
        this.field = field;
    }

    public AgentOperator getOperator() {
        return operator;
    }

    public void setOperator(AgentOperator operator) {
        this.operator = operator;
    }

    public String getValue() {
        return value;
    }

    public void setValue(String value) {
        this.value = value;
    }

    public List<String> getValues() {
        return values;
    }

    public void setValues(List<String> values) {
        this.values = values;
    }
}
