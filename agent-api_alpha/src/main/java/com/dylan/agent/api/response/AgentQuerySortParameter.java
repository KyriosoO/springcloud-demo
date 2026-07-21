package com.dylan.agent.api.response;

/** 响应中的 QUERY 排序参数回显。 */
public class AgentQuerySortParameter {

    private String field;
    private String direction;

    public AgentQuerySortParameter() {
    }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
}
