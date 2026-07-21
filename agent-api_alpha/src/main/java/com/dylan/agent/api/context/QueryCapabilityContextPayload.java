package com.dylan.agent.api.context;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentSortSpec;

import java.util.List;

/** QUERY 类型的 context payload。 */
public record QueryCapabilityContextPayload(
        List<AgentFilter> filters,
        List<String> selectFields,
        List<AgentSortSpec> sorts,
        int page,
        int size,
        Long total,
        Boolean totalExact,
        Integer totalPages) implements CapabilityContextPayload {

    public QueryCapabilityContextPayload(
            List<AgentFilter> filters,
            List<String> selectFields,
            int page,
            int size) {
        this(filters, selectFields, List.of(), page, size, null, null, null);
    }

    public QueryCapabilityContextPayload(
            List<AgentFilter> filters,
            List<String> selectFields,
            int page,
            int size,
            Long total,
            Boolean totalExact,
            Integer totalPages) {
        this(filters, selectFields, List.of(), page, size, total, totalExact, totalPages);
    }

    public QueryCapabilityContextPayload {
        filters = List.copyOf(filters == null ? List.of() : filters);
        selectFields = List.copyOf(selectFields == null ? List.of() : selectFields);
        sorts = List.copyOf(sorts == null ? List.of() : sorts);
        if (page <= 0) {
            throw new IllegalArgumentException("page must be positive");
        }
        if (size <= 0) {
            throw new IllegalArgumentException("size must be positive");
        }
        if (total != null && total < 0) {
            throw new IllegalArgumentException("total must not be negative");
        }
        if (totalPages != null && totalPages <= 0) {
            throw new IllegalArgumentException("totalPages must be positive");
        }
    }

    @Override
    public RuntimeContextType contextType() {
        return RuntimeContextType.QUERY;
    }
}
