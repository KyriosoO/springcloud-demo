package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;

/** 形成 DAE-1 exact binding，禁止 raw scope principals 进入 evidence。 */
public final class DocumentAclExecutionEvidenceFactory {
    public DocumentAclExecutionEvidence create(
            DocumentAclScopeRequest request,
            DocumentAclScopeSnapshot scope,
            CapabilityOperationMetadata metadata) {
        var context = request.operationContext();
        var limitReference = context.resourceLimits().reference();
        if (!scope.permissionVersion().equals(request.permissionEvidence().permissionVersion())
                || !metadata.operationId().equals(context.operationId())
                || !metadata.operationType().equals(context.operationType())
                || !metadata.resourceLimitReference().equals(limitReference)
                || metadata.termination() != com.dylan.agent.adapter.api.operation.CapabilityOperationTermination.SUCCEEDED) {
            throw new IllegalArgumentException("ACL evidence source binding mismatch");
        }
        String metadataDigest = DocumentAclCanonicalDigests.digest("DOM-1",
                metadata.operationId(), metadata.operationType().value(),
                Integer.toString(metadata.providerAttempts()), metadata.termination().name(),
                metadata.resourceLimitReference().canonicalDigest(), metadata.diagnosticId(),
                Boolean.toString(metadata.limitTouched()), Boolean.toString(metadata.deadlineTouched()),
                Boolean.toString(metadata.cancellationObserved()));
        String canonicalDigest = DocumentAclCanonicalDigests.digest("DAE-1",
                context.invocationId(), context.requestCorrelationId(), request.registrationIdentity(),
                request.subjectRef().type(), request.subjectRef().id(),
                request.corpusKey().domain(), request.corpusKey().materialType(), request.operation().name(),
                request.permissionEvidence().evidenceId(), request.permissionEvidence().permissionVersion(),
                scope.authorityVersion(), scope.locallyComputedCanonicalDigest(), metadataDigest,
                request.profileProjectionDigest(), limitReference.canonicalDigest(),
                scope.issuedAt().toString(), scope.expiresAt().toString());
        return new DocumentAclExecutionEvidence(
                context.invocationId(), context.requestCorrelationId(), request.registrationIdentity(),
                request.subjectRef(), request.corpusKey(), request.operation(), request.permissionEvidence(),
                scope.authorityVersion(), scope.locallyComputedCanonicalDigest(), metadataDigest,
                request.profileProjectionDigest(), limitReference, scope.issuedAt(), scope.expiresAt(),
                canonicalDigest);
    }
}
