package com.dylan.agent.api.context;

import java.util.List;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;

/** DOCUMENT 类型的 context payload，只保存最小引用状态。 */
public record DocumentCapabilityContextPayload(
        String operation,
        String domain,
        String queryText,
        List<AgentFilter> filters,
        List<String> citationIds,
        int topK) implements CapabilityContextPayload {

    public DocumentCapabilityContextPayload {
        filters = List.copyOf(filters == null ? List.of() : filters);
        citationIds = List.copyOf(citationIds == null ? List.of() : citationIds);
        if (topK <= 0) {
            throw new IllegalArgumentException("topK must be positive");
        }
    }

    @Override
    public RuntimeContextType contextType() {
        return RuntimeContextType.DOCUMENT;
    }
}
