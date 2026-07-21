package com.dylan.agent.capability.document.governance.emergency;

import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;

public record DocumentEmergencyGateEvidence(
        String evidenceId,
        DocumentEmergencyRolloutBinding rolloutBinding,
        List<DocumentEmergencyGateTargetBinding> orderedTargets,
        String emergencyViewVersion,
        DocumentEmergencyGateStatus status,
        Instant issuedAt,
        Instant validUntil,
        DocumentEvidenceSignature signature,
        String canonicalDigest) {
    public DocumentEmergencyGateEvidence {
        digest(evidenceId, "evidenceId");
        Objects.requireNonNull(rolloutBinding, "rolloutBinding must not be null");
        orderedTargets = List.copyOf(Objects.requireNonNull(orderedTargets, "orderedTargets must not be null"));
        if (orderedTargets.isEmpty() || orderedTargets.size() > 200
                || new HashSet<>(orderedTargets).size() != orderedTargets.size()
                || !orderedTargets.equals(orderedTargets.stream().sorted().toList())) {
            throw new IllegalArgumentException("orderedTargets must be a non-empty sorted unique list");
        }
        if (emergencyViewVersion == null || !emergencyViewVersion.matches("[A-Za-z0-9._-]{1,128}")) {
            throw new IllegalArgumentException("emergencyViewVersion must be a safe identifier");
        }
        Objects.requireNonNull(status, "status must not be null");
        Objects.requireNonNull(issuedAt, "issuedAt must not be null");
        Objects.requireNonNull(validUntil, "validUntil must not be null");
        if (validUntil.isBefore(issuedAt)) throw new IllegalArgumentException("validUntil precedes issuedAt");
        Objects.requireNonNull(signature, "signature must not be null");
        digest(canonicalDigest, "canonicalDigest");
    }

    private static void digest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be SHA-256 hex");
        }
    }
}
