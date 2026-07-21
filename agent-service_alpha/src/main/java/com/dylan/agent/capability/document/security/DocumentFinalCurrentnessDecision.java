package com.dylan.agent.capability.document.security;

import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.capability.document.acl.DocumentCurrentnessOutcome;

import java.time.Instant;

/** 只对 exact candidate set 和紧邻 Result Security 有效的短效决定。 */
public record DocumentFinalCurrentnessDecision(
        DocumentCurrentnessOutcome outcome,
        String invocationId,
        String operationId,
        String permissionVersion,
        String candidateSetDigest,
        String authorizationBindingDigest,
        ResourceLimitReference resourceLimitReference,
        String aclDecisionVersion,
        String emergencyViewVersion,
        Instant checkedAt,
        Instant validUntil,
        String decisionDigest,
        DocumentSecurityReasonCode reasonCode) {
    public DocumentFinalCurrentnessDecision {
        if (outcome == null || resourceLimitReference == null || checkedAt == null || validUntil == null
                || reasonCode == null) throw new IllegalArgumentException("final currentness decision is incomplete");
        requireText(invocationId, "invocationId");
        requireText(operationId, "operationId");
        requireText(permissionVersion, "permissionVersion");
        requireDigest(candidateSetDigest, "candidateSetDigest");
        requireDigest(authorizationBindingDigest, "authorizationBindingDigest");
        requireDigest(decisionDigest, "decisionDigest");
    }
    private static void requireText(String value,String name){if(value==null||value.isBlank())throw new IllegalArgumentException(name+" must not be blank");}
    private static void requireDigest(String value,String name){if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(name+" must be SHA-256 hex");}
}
