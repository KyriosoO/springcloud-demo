package com.dylan.agent.model;

import java.util.Set;

import com.dylan.agent.api.enums.AgentOperator;

/**
 * 字段级权限策略，来自配置。
 */
public class FieldPolicy {

    private final String field;
    private final Set<AgentOperator> operators;
    private final Set<String> filterRoles;
    private final Set<String> displayRoles;
    private final MaskType maskType;

    public FieldPolicy(String field, Set<AgentOperator> operators, Set<String> filterRoles,
                       Set<String> displayRoles, MaskType maskType) {
        this.field = field;
        this.operators = Set.copyOf(operators);
        this.filterRoles = Set.copyOf(filterRoles);
        this.displayRoles = Set.copyOf(displayRoles);
        this.maskType = maskType;
    }

    public String getField() { return field; }
    public Set<AgentOperator> getOperators() { return operators; }
    public Set<String> getFilterRoles() { return filterRoles; }
    public Set<String> getDisplayRoles() { return displayRoles; }
    public MaskType getMaskType() { return maskType; }
}
