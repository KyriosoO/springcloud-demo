package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AggregateFunction;

/** 响应中的单个聚合指标参数，透传给前端展示当前聚合计划。 */
public class AgentAggregateMetricParameter {

    private String alias;
    private AggregateFunction function;
    private String field;

    public AgentAggregateMetricParameter() {
    }

    public String getAlias() { return alias; }
    public void setAlias(String alias) { this.alias = alias; }
    public AggregateFunction getFunction() { return function; }
    public void setFunction(AggregateFunction function) { this.function = function; }
    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
}
