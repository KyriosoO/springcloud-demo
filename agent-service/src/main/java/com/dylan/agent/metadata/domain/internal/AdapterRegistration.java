package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;

import java.util.Objects;

/** 一个 adapter role/domain 与一个 typed port bean 之间的静态 D04 binding。 */
public record AdapterRegistration(
        String registrationId,
        AdapterRole role,
        String domain,
        Class<? extends AgentAdapterPort> portType,
        String portBeanName,
        String catalogVersion,
        String registrationVersion) {

    public AdapterRegistration {
        registrationId = CanonicalFieldDefinition.requireNonBlank(registrationId, "registrationId");
        Objects.requireNonNull(role, "role must not be null");
        domain = CanonicalFieldDefinition.requireNonBlank(domain, "domain");
        Objects.requireNonNull(portType, "portType must not be null");
        portBeanName = CanonicalFieldDefinition.requireNonBlank(portBeanName, "portBeanName");
        catalogVersion = CanonicalFieldDefinition.requireNonBlank(catalogVersion, "catalogVersion");
        registrationVersion = CanonicalFieldDefinition.requireNonBlank(registrationVersion, "registrationVersion");
    }
}
