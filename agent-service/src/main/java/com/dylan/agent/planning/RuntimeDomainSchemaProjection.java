package com.dylan.agent.planning;

import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.runtime.RuntimeDomainSchema;
import com.dylan.agent.api.runtime.RuntimeFieldSchema;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.DomainView;

/**
 * 从 D04 Canonical Catalog 构造旧 Runtime 领域 Schema。
 * 只暴露字段名、别名、类型、operator、聚合函数白名单，不暴露角色和脱敏规则。
 */
@Component
public class RuntimeDomainSchemaProjection {

    private final AgentProperties properties;
    private final DomainCatalogView domainCatalogView;

    public RuntimeDomainSchemaProjection(AgentProperties properties,
                                       DomainCatalogView domainCatalogView) {
        this.properties = properties;
        this.domainCatalogView = domainCatalogView;
    }

    /** 为单个 domain 创建 RuntimeDomainSchema。 */
    public RuntimeDomainSchema create(String domain) {
        return buildSchema(domainCatalogView.requireDomain(domain, AdapterRole.QUERYABLE));
    }

    /** 为所有已配置 domain 创建 RuntimeDomainSchema 列表。 */
    public List<RuntimeDomainSchema> createAll() {
        return domainCatalogView.domains().stream()
                .map(domain -> domainCatalogView.requireDomain(domain, AdapterRole.QUERYABLE))
                .map(this::buildSchema)
                .toList();
    }

    private RuntimeDomainSchema buildSchema(DomainView queryDomain) {
        String domain = queryDomain.domain();
        RuntimeDomainSchema schema = new RuntimeDomainSchema();
        schema.setDomain(domain);
        schema.setAliases(queryDomain.aliases());
        schema.setDefaultSelectFields(queryDomain.defaultSelectFields());
        schema.setMaxFilters(properties.getQuery().getMaxFilters());
        schema.setDefaultSize(properties.getQuery().getDefaultSize());
        schema.setMaxSize(properties.getQuery().getMaxSize());
        schema.setMaxResultWindow(properties.getQuery().getMaxResultWindow());

        List<RuntimeFieldSchema> fieldSchemas = new ArrayList<>();
        DomainView aggregateDomain = domainCatalogView.findDomain(domain, AdapterRole.AGGREGATABLE).orElse(null);
        for (String fieldName : queryDomain.capabilityFields().stream().sorted().toList()) {
            var fp = queryDomain.requireField(fieldName);
            RuntimeFieldSchema fs = new RuntimeFieldSchema();
            fs.setName(fieldName);
            fs.setAliases(fp.definition().aliases());
            fs.setType(fp.type());
            fs.setFormatHint(fp.valueFormat());
            fs.setOperators(new ArrayList<>(fp.operators()));
            fs.setSupportedAggregateFunctions(resolveAggregateFunctions(aggregateDomain, fieldName));
            fieldSchemas.add(fs);
        }
        schema.setFields(fieldSchemas);
        return schema;
    }

    private List<AggregateFunction> resolveAggregateFunctions(DomainView aggregateDomain, String fieldName) {
        if (aggregateDomain == null || !aggregateDomain.capabilityFields().contains(fieldName)) {
            return null;
        }
        var functions = aggregateDomain.requireField(fieldName).functions();
        return functions.isEmpty() ? List.of() : functions.stream().sorted().toList();
    }
}
