package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference;
import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.kernel.infrastructure.CandidateSecurityBinding;
import com.dylan.agent.kernel.infrastructure.GeneratedTextCandidate;

import java.util.List;
import java.util.Objects;

/** 仅在 Invocation 内存中存在的可信文档生成候选。 */
public record DocumentGeneratedTextCandidate(
        DocumentPlanOperation operation,
        DocumentGeneratedContent content,
        List<String> citedIds,
        String evidencePackageDigest,
        ResourceLimitReference resourceLimitReference,
        String authorizationBindingDigest,
        CapabilityOperationMetadata operationMetadata,
        DocumentProviderBindingReference providerBinding,
        CandidateSecurityBinding securityBinding) implements GeneratedTextCandidate {
    public DocumentGeneratedTextCandidate {
        Objects.requireNonNull(operation, "operation must not be null");
        Objects.requireNonNull(content, "content must not be null");
        citedIds = List.copyOf(Objects.requireNonNull(citedIds, "citedIds must not be null"));
        if (evidencePackageDigest == null || !evidencePackageDigest.matches("[0-9a-f]{64}")
                || authorizationBindingDigest == null
                || !authorizationBindingDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("generated candidate digest binding invalid");
        }
        Objects.requireNonNull(resourceLimitReference, "resourceLimitReference must not be null");
        Objects.requireNonNull(operationMetadata, "operationMetadata must not be null");
        Objects.requireNonNull(providerBinding, "providerBinding must not be null");
        Objects.requireNonNull(securityBinding, "securityBinding must not be null");
        if (!resourceLimitReference.equals(securityBinding.resourceLimitReference())
                || !operationMetadata.equals(securityBinding.operationMetadata())
                || !providerBinding.provider().equals(operationMetadata.provider())
                || !providerBinding.operationType().equals(operationMetadata.operationType())) {
            throw new IllegalArgumentException("generated candidate trusted binding mismatch");
        }
    }
}
