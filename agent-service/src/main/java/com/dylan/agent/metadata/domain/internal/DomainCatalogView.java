package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/**
 * 面向 D03 完成前旧校验器的只读 D04 Catalog 视图。
 */
public final class DomainCatalogView {

    private final DomainMetadataStore store;

    public DomainCatalogView(DomainMetadataStore store) {
        this.store = Objects.requireNonNull(store);
    }

    public List<String> domains() {
        return store.current().catalog().domainIds();
    }

    public boolean containsDomain(String domain) {
        return store.current().catalog().findDomain(domain).isPresent();
    }

    public DomainView requireDomain(String domain, AdapterRole role) {
        CanonicalDomainDefinition definition = store.current().catalog().requireDomain(domain);
        CanonicalRoleCapability capability = definition.roleCapabilities().get(role);
        if (capability == null) {
            throw new IllegalArgumentException("domain does not support role: " + domain + "/" + role);
        }
        return new DomainView(definition, capability);
    }

    public Optional<DomainView> findDomain(String domain, AdapterRole role) {
        return store.current().catalog().findDomain(domain)
                .map(definition -> {
                    CanonicalRoleCapability capability = definition.roleCapabilities().get(role);
                    return capability == null ? null : new DomainView(definition, capability);
                });
    }

    public record DomainView(
            CanonicalDomainDefinition definition,
            CanonicalRoleCapability capability) {

        public DomainView {
            Objects.requireNonNull(definition);
            Objects.requireNonNull(capability);
        }

        public String domain() { return definition.domain(); }
        public List<String> aliases() { return definition.aliases(); }
        public Map<String, CanonicalFieldDefinition> fields() { return definition.fields(); }
        public List<String> defaultSelectFields() {
            return definition.defaultSelectFieldsByRole().getOrDefault(capability.role(), List.of());
        }
        public Set<String> capabilityFields() { return capability.fields(); }
        public FieldView requireField(String field) {
            CanonicalFieldDefinition definition = fields().get(field);
            if (definition == null || !capability.fields().contains(field)) {
                throw new IllegalArgumentException("unknown field: " + field);
            }
            return new FieldView(this, definition);
        }
    }

    public record FieldView(
            DomainView domain,
            CanonicalFieldDefinition definition) {

        public String field() { return definition.field(); }
        public AgentFieldType type() { return definition.type(); }
        public Set<AgentOperator> operators() {
            return domain.capability().operatorsByField().getOrDefault(field(), Set.of());
        }
        public Set<AggregateFunction> functions() {
            return domain.capability().functionsByField().getOrDefault(field(), Set.of());
        }
        public Integer precision() { return definition.precision().orElse(null); }
        public Integer scale() { return definition.scale().orElse(null); }
        public String valueFormat() { return definition.valueFormat().orElse(null); }
        public CanonicalFieldRef ref() { return new CanonicalFieldRef(domain.domain(), field()); }
    }
}
