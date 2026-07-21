package com.dylan.agent.kernel.infrastructure;

import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/** Provider 生成文本候选与 Invocation、证据及资源限额的不可变安全绑定。 */
public record CandidateSecurityBinding(
        String invocationId,
        String requestCorrelationId,
        ContractRef outputContract,
        ResourceLimitReference resourceLimitReference,
        List<CandidateEvidenceReference> evidenceRefs,
        List<CandidateCitationReference> citationRefs,
        CapabilityOperationMetadata operationMetadata) {

    public CandidateSecurityBinding {
        invocationId = requireNonBlank(invocationId, "invocationId");
        requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        Objects.requireNonNull(outputContract, "outputContract must not be null");
        Objects.requireNonNull(resourceLimitReference, "resourceLimitReference must not be null");
        evidenceRefs = List.copyOf(Objects.requireNonNull(evidenceRefs, "evidenceRefs must not be null"));
        citationRefs = List.copyOf(Objects.requireNonNull(citationRefs, "citationRefs must not be null"));
        Objects.requireNonNull(operationMetadata, "operationMetadata must not be null");

        Set<String> evidenceIds = new HashSet<>();
        for (CandidateEvidenceReference evidence : evidenceRefs) {
            if (!evidenceIds.add(evidence.evidenceRefId())) {
                throw new IllegalArgumentException("duplicate evidenceRefId: " + evidence.evidenceRefId());
            }
        }
        Set<String> citationIds = new HashSet<>();
        for (CandidateCitationReference citation : citationRefs) {
            if (!citationIds.add(citation.citationId())) {
                throw new IllegalArgumentException("duplicate citationId: " + citation.citationId());
            }
            if (!evidenceIds.contains(citation.evidenceRefId())) {
                throw new IllegalArgumentException(
                        "citation references unknown evidence: " + citation.evidenceRefId());
            }
        }
        if (!operationMetadata.resourceLimitReference().equals(resourceLimitReference)) {
            throw new IllegalArgumentException("operation metadata resource limit binding mismatch");
        }
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
