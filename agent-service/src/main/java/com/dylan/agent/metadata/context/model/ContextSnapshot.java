package com.dylan.agent.metadata.context.model;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.InvocationScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/** Planning/Core 消费的请求本地 typed context snapshot。 */
public final class ContextSnapshot {

    private final String contextId;
    private final String requestCorrelationId;
    private final ContextRecordKey recordKey;
    private final String sourceCapabilityId;
    private final String sourceInvocationId;
    private final Optional<String> sourceDomain;
    private final ContractRef storedContractRef;
    private final ContractRef effectiveContractRef;
    private final long recordVersion;
    private final Instant expiresAt;
    private final String profileEvidenceRef;
    private final String policyEvidenceRef;
    private final String permissionEvidenceRef;
    private final Optional<String> delegationEvidenceRef;
    private final ExpectedContextVersion expectedWriteVersion;
    private final CapabilityContextPayload payload;

    public ContextSnapshot(String contextId,
                           String requestCorrelationId,
                           ContextRecordKey recordKey,
                           String sourceCapabilityId,
                           String sourceInvocationId,
                           String sourceDomain,
                           ContractRef storedContractRef,
                           ContractRef effectiveContractRef,
                           long recordVersion,
                           Instant expiresAt,
                           String profileEvidenceRef,
                           String policyEvidenceRef,
                           String permissionEvidenceRef,
                           String delegationEvidenceRef,
                           ExpectedContextVersion expectedWriteVersion,
                           CapabilityContextPayload payload) {
        this.contextId = requireNonBlank(contextId, "contextId");
        this.requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        this.recordKey = Objects.requireNonNull(recordKey, "recordKey must not be null");
        this.sourceCapabilityId = requireNonBlank(sourceCapabilityId, "sourceCapabilityId");
        this.sourceInvocationId = requireNonBlank(sourceInvocationId, "sourceInvocationId");
        this.sourceDomain = Optional.ofNullable(sourceDomain)
                .map(value -> requireNonBlank(value, "sourceDomain"));
        this.storedContractRef = Objects.requireNonNull(storedContractRef);
        this.effectiveContractRef = Objects.requireNonNull(effectiveContractRef);
        if (recordVersion < 0) {
            throw new IllegalArgumentException("recordVersion must be non-negative");
        }
        this.recordVersion = recordVersion;
        this.expiresAt = Objects.requireNonNull(expiresAt);
        this.profileEvidenceRef = requireNonBlank(profileEvidenceRef, "profileEvidenceRef");
        this.policyEvidenceRef = requireNonBlank(policyEvidenceRef, "policyEvidenceRef");
        this.permissionEvidenceRef = requireNonBlank(permissionEvidenceRef, "permissionEvidenceRef");
        this.delegationEvidenceRef = Optional.ofNullable(delegationEvidenceRef)
                .map(value -> requireNonBlank(value, "delegationEvidenceRef"));
        this.expectedWriteVersion = Objects.requireNonNull(
                expectedWriteVersion, "expectedWriteVersion must not be null");
        this.payload = Objects.requireNonNull(payload);
        if (payload.contextType() != recordKey.contextType()) {
            throw new IllegalArgumentException("payload contextType mismatch");
        }
        if (expectedWriteVersion instanceof ExpectedContextVersion.ExpectedVersion existing
                && existing.recordVersion() != recordVersion) {
            throw new IllegalArgumentException("expectedWriteVersion must match recordVersion");
        }
    }

    public String contextId() { return contextId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public ContextRecordKey recordKey() { return recordKey; }
    public ContextOwnerRef owner() { return recordKey.owner(); }
    public InvocationScope scope() { return recordKey.scope(); }
    public RuntimeContextType contextType() { return recordKey.contextType(); }
    public String sourceCapabilityId() { return sourceCapabilityId; }
    public String sourceInvocationId() { return sourceInvocationId; }
    public Optional<String> sourceDomain() { return sourceDomain; }
    public ContractRef storedContractRef() { return storedContractRef; }
    public ContractRef effectiveContractRef() { return effectiveContractRef; }
    public long recordVersion() { return recordVersion; }
    public Instant expiresAt() { return expiresAt; }
    public String profileEvidenceRef() { return profileEvidenceRef; }
    public String policyEvidenceRef() { return policyEvidenceRef; }
    public String permissionEvidenceRef() { return permissionEvidenceRef; }
    public Optional<String> delegationEvidenceRef() { return delegationEvidenceRef; }
    public ExpectedContextVersion expectedWriteVersion() { return expectedWriteVersion; }
    public CapabilityContextPayload payload() { return payload; }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
