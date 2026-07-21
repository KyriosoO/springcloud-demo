package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.adapter.api.operation.CapabilityOperationRequest;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;

import java.util.Objects;

/** 绑定 current ExecutionScope 的文档 ACL authority 请求。 */
public record DocumentAclScopeRequest(
        CapabilityOperationContext operationContext,
        String registrationIdentity,
        ExecutionSubjectRef subjectRef,
        DocumentCorpusKey corpusKey,
        DocumentPlanOperation operation,
        PermissionEvidenceReference permissionEvidence,
        String profileProjectionDigest) implements CapabilityOperationRequest {

    public DocumentAclScopeRequest {
        Objects.requireNonNull(operationContext, "operationContext must not be null");
        registrationIdentity = requireText(registrationIdentity, "registrationIdentity");
        Objects.requireNonNull(subjectRef, "subjectRef must not be null");
        Objects.requireNonNull(corpusKey, "corpusKey must not be null");
        Objects.requireNonNull(operation, "operation must not be null");
        Objects.requireNonNull(permissionEvidence, "permissionEvidence must not be null");
        profileProjectionDigest = requireDigest(profileProjectionDigest, "profileProjectionDigest");
        var limitReference = operationContext.resourceLimits().reference();
        if (!operationContext.invocationId().equals(limitReference.invocationId())
                || !registrationIdentity.equals(limitReference.registrationIdentity())) {
            throw new IllegalArgumentException("ACL request does not match resource limit binding");
        }
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
        return value.trim();
    }

    private static String requireDigest(String value, String name) {
        String normalized = requireText(value, name);
        if (!normalized.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256 hex");
        }
        return normalized;
    }
}
