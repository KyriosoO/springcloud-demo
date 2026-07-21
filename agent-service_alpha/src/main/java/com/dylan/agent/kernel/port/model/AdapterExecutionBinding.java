package com.dylan.agent.kernel.port.model;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.metadata.domain.port.CanonicalRoleCapabilityRef;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Instant;
import java.util.Objects;

/**
 * Metadata 边界按 Adapter Role + authorized domain + 当前可用性
 * 一次解析的请求级不可变 Adapter port 绑定。
 */
public final class AdapterExecutionBinding {

    private final AdapterRole adapterRole;
    private final String domain;
    private final Class<? extends AgentAdapterPort> portType;
    private final AgentAdapterPort port;
    private final String registrationId;
    private final String adapterRegistrationVersion;
    private final CanonicalRoleCapabilityRef capabilityRef;
    private final DomainMetadataEvidence metadataEvidence;
    private final Instant resolvedAt;

    public AdapterExecutionBinding(AdapterRole adapterRole,
                                   String domain,
                                   Class<? extends AgentAdapterPort> portType,
                                   AgentAdapterPort port,
                                   String registrationId,
                                   String adapterRegistrationVersion,
                                   CanonicalRoleCapabilityRef capabilityRef,
                                   DomainMetadataEvidence metadataEvidence,
                                   Instant resolvedAt) {
        this.adapterRole = Objects.requireNonNull(adapterRole);
        this.domain = Objects.requireNonNull(domain);
        this.portType = Objects.requireNonNull(portType);
        this.port = Objects.requireNonNull(port);
        this.registrationId = requireText(registrationId, "registrationId");
        this.adapterRegistrationVersion = requireText(adapterRegistrationVersion, "adapterRegistrationVersion");
        this.capabilityRef = Objects.requireNonNull(capabilityRef);
        this.metadataEvidence = Objects.requireNonNull(metadataEvidence);
        this.resolvedAt = Objects.requireNonNull(resolvedAt);
        if (!portType.isInstance(port)) {
            throw new IllegalArgumentException("port does not implement declared portType");
        }
        if (!adapterRole.equals(capabilityRef.role()) || !domain.equals(capabilityRef.domain())) {
            throw new IllegalArgumentException("binding/capability reference mismatch");
        }
        if (!capabilityRef.catalogVersion().equals(metadataEvidence.catalogVersion())
                || !capabilityRef.catalogDigest().equals(metadataEvidence.staticEvidence().catalogDigest())
                || !adapterRegistrationVersion.equals(metadataEvidence.adapterRegistrationVersion())) {
            throw new IllegalArgumentException("binding/metadata evidence mismatch");
        }
    }

    public AdapterRole adapterRole() { return adapterRole; }
    public String domain() { return domain; }
    public Class<? extends AgentAdapterPort> portType() { return portType; }
    public String registrationId() { return registrationId; }
    public String adapterRegistrationVersion() { return adapterRegistrationVersion; }
    public CanonicalRoleCapabilityRef capabilityRef() { return capabilityRef; }
    public DomainMetadataEvidence metadataEvidence() { return metadataEvidence; }
    public Instant resolvedAt() { return resolvedAt; }

    public <P extends AgentAdapterPort> P requirePort(Class<P> expectedType) {
        Objects.requireNonNull(expectedType, "expectedType must not be null");
        if (!portType.equals(expectedType) || !expectedType.isInstance(port)) {
            throw new IllegalArgumentException("requested adapter port type does not match binding");
        }
        return expectedType.cast(port);
    }

    private static String requireText(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
