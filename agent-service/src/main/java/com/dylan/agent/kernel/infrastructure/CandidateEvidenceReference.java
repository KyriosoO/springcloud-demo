package com.dylan.agent.kernel.infrastructure;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;

/** 生成文本候选所引用的、已授权证据的最小安全引用。 */
public record CandidateEvidenceReference(
        String evidenceRefId,
        ContractRef evidenceContract,
        String authorizationBindingDigest,
        String ownerScopeDigest) {

    public CandidateEvidenceReference {
        evidenceRefId = requireNonBlank(evidenceRefId, "evidenceRefId");
        Objects.requireNonNull(evidenceContract, "evidenceContract must not be null");
        authorizationBindingDigest = requireDigest(
                authorizationBindingDigest, "authorizationBindingDigest");
        ownerScopeDigest = requireDigest(ownerScopeDigest, "ownerScopeDigest");
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }

    private static String requireDigest(String value, String name) {
        String normalized = requireNonBlank(value, name);
        if (!normalized.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256 hex");
        }
        return normalized;
    }
}
