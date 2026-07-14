package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.DocumentCandidateIdentity;
import com.dylan.agent.adapter.api.document.DocumentCandidateSecurityBinding;

/** ECP 内部可信证据项；Provider 投影不得携带 identity/security sidecar。 */
public record GenerationEvidencePackageItem(
        String citationId,
        String candidateId,
        DocumentCandidateIdentity identity,
        String outboundTitle,
        String outboundSection,
        Integer outboundPage,
        String outboundText,
        DocumentCandidateSecurityBinding securityBinding) {
    public GenerationEvidencePackageItem {
        if (citationId == null || !citationId.matches("C[1-9][0-9]*")
                || candidateId == null || candidateId.isBlank() || identity == null
                || outboundText == null || outboundText.isBlank() || securityBinding == null) {
            throw new IllegalArgumentException("generation evidence package item incomplete");
        }
    }
}
