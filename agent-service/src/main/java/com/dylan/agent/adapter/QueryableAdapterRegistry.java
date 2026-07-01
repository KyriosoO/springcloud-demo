package com.dylan.agent.adapter;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.exception.AgentPlanValidationException;

/**
 * Adapter 注册中心，按 domain 查找对应的 QueryableAdapter。
 */
@Component
public class QueryableAdapterRegistry {

    private final Map<String, QueryableAdapter> adapters;

    public QueryableAdapterRegistry(List<QueryableAdapter> adapterList) {
        Map<String, QueryableAdapter> map = new HashMap<>();
        for (QueryableAdapter a : adapterList) {
            if (a.domain() == null || a.domain().isBlank()) {
                throw new IllegalStateException("QueryableAdapter domain must not be blank");
            }
            if (!a.domain().equals(a.domain().toLowerCase())) {
                throw new IllegalStateException("QueryableAdapter domain must be lowercase: " + a.domain());
            }
            Set<String> fields = a.supportedFields();
            if (fields == null || fields.isEmpty()) {
                throw new IllegalStateException(
                        "QueryableAdapter " + a.domain() + " supportedFields must not be null or empty");
            }
            for (String field : fields) {
                if (field == null || field.isBlank()) {
                    throw new IllegalStateException(
                            "QueryableAdapter " + a.domain() + " supportedFields contains null or blank");
                }
            }
            if (map.put(a.domain(), a) != null) {
                throw new IllegalStateException("Duplicate QueryableAdapter domain: " + a.domain());
            }
        }
        if (map.isEmpty()) {
            throw new IllegalStateException("至少需要一个 QueryableAdapter 实现。");
        }
        this.adapters = Map.copyOf(map);
    }

    /** 按 domain 查找 Adapter，不存在时抛异常。 */
    public QueryableAdapter getRequired(String domain) {
        QueryableAdapter adapter = adapters.get(domain);
        if (adapter == null) {
            throw new AgentPlanValidationException("不支持的 domain: " + domain);
        }
        return adapter;
    }

    /** 返回所有已注册的 domain 集合。 */
    public Set<String> domains() {
        return adapters.keySet();
    }

    /** 返回指定 domain 的 Adapter 支持的字段集合。 */
    public Set<String> supportedFields(String domain) {
        QueryableAdapter adapter = adapters.get(domain);
        if (adapter == null) {
            throw new AgentPlanValidationException("不支持的 domain: " + domain);
        }
        return adapter.supportedFields();
    }
}
