package com.dylan.agent.api.response;

/** 响应中的聚合结果排序参数。 */
public class AgentAggregateOrderParameter {

    private String field;
    private String direction;

    public AgentAggregateOrderParameter() {
    }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
}
