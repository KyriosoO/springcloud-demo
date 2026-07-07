package com.dylan.agent.capability.document.generation;

import com.dylan.agent.api.response.GroundingStatus;

import java.util.List;
import java.util.Set;

/** 校验 LLM 生成文本只引用本次证据包中的 citation。 */
public class DocumentCitationVerifier {

    public CitationVerificationResult verify(
            DocumentGenerationResult result,
            EvidenceContextPackage context) {
        if (context.citationIds().isEmpty()) {
            return new CitationVerificationResult(GroundingStatus.NO_EVIDENCE, 0, List.of(), "NO_EVIDENCE");
        }
        List<CitationBinding> bindings = result.citationBindings() == null ? List.of() : result.citationBindings();
        List<String> referencedCitationIds = bindings.stream()
                .flatMap(binding -> (binding.citationIds() == null ? List.<String>of() : binding.citationIds()).stream())
                .map(citationId -> citationId == null ? "" : citationId.trim())
                .toList();
        if (referencedCitationIds.isEmpty()) {
            return new CitationVerificationResult(GroundingStatus.PARTIAL, 0, List.of(), "NO_BINDINGS");
        }
        Set<String> allowed = context.citationIds();
        List<String> invalid = referencedCitationIds.stream()
                .filter(citationId -> citationId.isBlank() || !allowed.contains(citationId))
                .distinct()
                .toList();
        if (!invalid.isEmpty()) {
            return new CitationVerificationResult(GroundingStatus.UNVERIFIED, invalid.size(), invalid, "INVALID_CITATION");
        }
        return new CitationVerificationResult(GroundingStatus.VERIFIED, 0, List.of(), null);
    }
}
