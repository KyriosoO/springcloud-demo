package com.dylan.agent.adapter;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.exception.AgentPlanValidationException;

/** 聚合 Adapter 注册中心，按 domain 查找 AggregatableAdapter。镜像 QueryableAdapterRegistry 设计。 */
@Component
public class AggregatableAdapterRegistry {

    private final Map<String, AggregatableAdapter> adapters;

    public AggregatableAdapterRegistry(List<AggregatableAdapter> adapterList) {
        Map<String, AggregatableAdapter> map = new HashMap<>();
        for (AggregatableAdapter a : adapterList) {
            if (a.domain() == null || a.domain().isBlank()) {
                throw new IllegalStateException("AggregatableAdapter domain must not be blank");
            }
            if (!a.domain().equals(a.domain().toLowerCase())) {
                throw new IllegalStateException(
                        "AggregatableAdapter domain must be lowercase: " + a.domain());
            }
            Set<String> fields = a.supportedAggregateFields();
            if (fields == null || fields.isEmpty()) {
                throw new IllegalStateException(
                        "AggregatableAdapter " + a.domain()
                        + " supportedAggregateFields must not be null or empty");
            }
            if (map.put(a.domain(), a) != null) {
                throw new IllegalStateException("Duplicate AggregatableAdapter domain: " + a.domain());
            }
        }
        this.adapters = Map.copyOf(map);
    }

    public AggregatableAdapter getRequired(String domain) {
        AggregatableAdapter adapter = adapters.get(domain);
        if (adapter == null) {
            throw new AgentPlanValidationException("不支持的聚合 domain: " + domain);
        }
        return adapter;
    }

    public Set<String> domains() {
        return adapters.keySet();
    }

    public Set<String> supportedAggregateFields(String domain) {
        AggregatableAdapter adapter = adapters.get(domain);
        if (adapter == null) {
            throw new AgentPlanValidationException("不支持的聚合 domain: " + domain);
        }
        return adapter.supportedAggregateFields();
    }
}
