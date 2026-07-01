package com.dylan.agent.planning;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.runtime.RuntimeDomainSchema;
import com.dylan.agent.api.runtime.RuntimeFieldSchema;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.config.AgentProperties.DomainProperties;
import com.dylan.agent.config.AgentProperties.FieldProperties;

/**
 * 从 AgentProperties 和 AggregatableAdapterRegistry 构造 Runtime 领域 Schema。
 * 只暴露字段名、别名、类型、operator、聚合函数白名单，不暴露角色和脱敏规则。
 */
@Component
public class RuntimeDomainSchemaFactory {

    private final AgentProperties properties;
    private final AggregatableAdapterRegistry aggregateAdapterRegistry;

    public RuntimeDomainSchemaFactory(AgentProperties properties,
                                       AggregatableAdapterRegistry aggregateAdapterRegistry) {
        this.properties = properties;
        this.aggregateAdapterRegistry = aggregateAdapterRegistry;
    }

    /** 为单个 domain 创建 RuntimeDomainSchema。 */
    public RuntimeDomainSchema create(String domain) {
        DomainProperties dp = properties.getDomains().get(domain);
        if (dp == null) {
            throw new IllegalArgumentException("Unknown domain: " + domain);
        }
        return buildSchema(domain, dp);
    }

    /** 为所有已配置 domain 创建 RuntimeDomainSchema 列表。 */
    public List<RuntimeDomainSchema> createAll() {
        return properties.getDomains().entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> buildSchema(entry.getKey(), entry.getValue()))
                .toList();
    }

    private RuntimeDomainSchema buildSchema(String domain, DomainProperties dp) {
        RuntimeDomainSchema schema = new RuntimeDomainSchema();
        schema.setDomain(domain);
        schema.setAliases(dp.getAliases() != null ? dp.getAliases() : List.of());
        schema.setDefaultSelectFields(dp.getDefaultSelectFields());
        schema.setMaxFilters(properties.getQuery().getMaxFilters());
        schema.setDefaultSize(properties.getQuery().getDefaultSize());
        schema.setMaxSize(properties.getQuery().getMaxSize());
        schema.setMaxResultWindow(properties.getQuery().getMaxResultWindow());

        List<RuntimeFieldSchema> fieldSchemas = new ArrayList<>();
        for (var entry : dp.getFields().entrySet()) {
            String fieldName = entry.getKey();
            FieldProperties fp = entry.getValue();
            RuntimeFieldSchema fs = new RuntimeFieldSchema();
            fs.setName(fieldName);
            fs.setAliases(fp.getAliases());
            fs.setType(fp.getType());
            fs.setFormatHint(fp.getFormatHint());
            fs.setOperators(new ArrayList<>(fp.getOperators()));
            fs.setSupportedAggregateFunctions(resolveAggregateFunctions(domain, fieldName));
            fieldSchemas.add(fs);
        }
        schema.setFields(fieldSchemas);
        return schema;
    }

    private List<AggregateFunction> resolveAggregateFunctions(String domain, String fieldName) {
        if (aggregateAdapterRegistry == null || !aggregateAdapterRegistry.domains().contains(domain)) {
            return null;
        }
        var adapter = aggregateAdapterRegistry.getRequired(domain);
        if (adapter.supportedAggregateFields().contains(fieldName)) {
            return adapter.supportedFunctions(fieldName).isEmpty()
                    ? List.of()
                    : new ArrayList<>(adapter.supportedFunctions(fieldName));
        }
        return List.of();
    }
}
