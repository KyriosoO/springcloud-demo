package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;

import java.time.Instant;

/** ACL authority scope/candidate currentness 的封闭决定。 */
public record DocumentAclCurrentnessDecision(
        DocumentCurrentnessOutcome outcome,
        String authorityVersion,
        String permissionVersion,
        String decisionVersion,
        Instant checkedAt,
        Instant validUntil,
        String reasonCode,
        CapabilityOperationMetadata metadata) {
    public DocumentAclCurrentnessDecision {
        if (outcome == null || metadata == null || checkedAt == null || validUntil == null
                || reasonCode == null || reasonCode.isBlank() || decisionVersion == null || decisionVersion.isBlank()) {
            throw new IllegalArgumentException("ACL currentness decision must be complete");
        }
        if (validUntil.isBefore(checkedAt)) throw new IllegalArgumentException("currentness validUntil is invalid");
    }
}
