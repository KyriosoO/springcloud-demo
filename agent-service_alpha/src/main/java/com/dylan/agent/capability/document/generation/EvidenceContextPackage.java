package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.plan.DocumentPlanOperation;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/** ECP-1：仅在 agent-service 内存存在的可信生成证据包。 */
public record EvidenceContextPackage(
        String packageId,
        String invocationId,
        String requestCorrelationId,
        String capabilityId,
        DocumentPlanOperation operation,
        DocumentCorpusKey corpusKey,
        String profileProjectionDigest,
        ResourceLimitReference resourceLimitReference,
        ContractRef outputContract,
        String authorizationBindingDigest,
        String aclEvidenceDigest,
        String targetBindingDigest,
        String protectedFilterDigest,
        String providerOutboundPolicyDigest,
        List<GenerationEvidencePackageItem> items,
        DocumentEvidenceUsage usage,
        String canonicalDigest) {
    public EvidenceContextPackage {
        items = List.copyOf(items == null ? List.of() : items);
        if (packageId == null || !packageId.matches("ECP-[0-9a-f]{24}")
                || invocationId == null || requestCorrelationId == null || capabilityId == null
                || operation == null || corpusKey == null || resourceLimitReference == null
                || outputContract == null || usage == null || canonicalDigest == null
                || !canonicalDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("evidence context package incomplete");
        }
    }

    public Set<String> citationIds() {
        return items.stream().map(GenerationEvidencePackageItem::citationId)
                .collect(Collectors.toUnmodifiableSet());
    }
}
