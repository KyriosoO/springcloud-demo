package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import java.util.Objects;

/** 一个 adapter role/domain 与一个 typed port bean 之间的静态 D04 binding。 */
public record AdapterRegistration(
        String registrationId,
        AdapterRole role,
        String domain,
        String portBeanName,
        String registrationVersion) {

    public AdapterRegistration {
        registrationId = CanonicalFieldDefinition.requireNonBlank(registrationId, "registrationId");
        Objects.requireNonNull(role, "role must not be null");
        domain = CanonicalFieldDefinition.requireNonBlank(domain, "domain");
        portBeanName = CanonicalFieldDefinition.requireNonBlank(portBeanName, "portBeanName");
        registrationVersion = CanonicalFieldDefinition.requireNonBlank(registrationVersion, "registrationVersion");
    }
}
