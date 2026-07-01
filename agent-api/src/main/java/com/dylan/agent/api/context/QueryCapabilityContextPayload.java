package com.dylan.agent.api.context;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;

import java.util.List;

/** QUERY context payload. */
public record QueryCapabilityContextPayload(
        List<AgentFilter> filters,
        List<String> selectFields,
        int page,
        int size) implements CapabilityContextPayload {

    public QueryCapabilityContextPayload {
        filters = List.copyOf(filters == null ? List.of() : filters);
        selectFields = List.copyOf(selectFields == null ? List.of() : selectFields);
        if (page <= 0) {
            throw new IllegalArgumentException("page must be positive");
        }
        if (size <= 0) {
            throw new IllegalArgumentException("size must be positive");
        }
    }

    @Override
    public RuntimeContextType contextType() {
        return RuntimeContextType.QUERY;
    }
}
