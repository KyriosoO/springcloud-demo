package com.dylan.agent.capability.document.governance.emergency;

import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;

public record DocumentEmergencyGateEvidenceIssueRequest(
        DocumentEmergencyRolloutBinding rolloutBinding,
        List<DocumentEmergencyTargetRef> orderedTargets,
        Instant deadline) {
    public DocumentEmergencyGateEvidenceIssueRequest {
        Objects.requireNonNull(rolloutBinding, "rolloutBinding must not be null");
        orderedTargets = List.copyOf(Objects.requireNonNull(orderedTargets, "orderedTargets must not be null"));
        if (orderedTargets.isEmpty() || orderedTargets.size() > 200
                || new HashSet<>(orderedTargets).size() != orderedTargets.size()) {
            throw new IllegalArgumentException("orderedTargets must be a non-empty unique list");
        }
        Objects.requireNonNull(deadline, "deadline must not be null");
    }
    @com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}
}
