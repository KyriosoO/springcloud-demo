package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;

import java.util.Objects;
import java.util.Set;

import org.springframework.context.ApplicationContext;

/** Resolves old pre-D03 handlers through D04 AdapterRegistration, not adapter self-reported metadata. */
public final class AdapterPortResolver {

    private final DomainMetadataStore store;
    private final ApplicationContext applicationContext;

    public AdapterPortResolver(DomainMetadataStore store, ApplicationContext applicationContext) {
        this.store = Objects.requireNonNull(store);
        this.applicationContext = Objects.requireNonNull(applicationContext);
    }

    public Set<String> domains(AdapterRole role) {
        return store.current().registrations().domains(role);
    }

    public <T extends AgentAdapterPort> T require(AdapterRole role, String domain, Class<T> type) {
        AdapterRegistration registration = store.current().registrations().require(role, domain);
        if (!type.equals(registration.portType())) {
            throw new IllegalStateException("registered port type mismatch for " + role + "/" + domain);
        }
        return applicationContext.getBean(registration.portBeanName(), type);
    }
}
