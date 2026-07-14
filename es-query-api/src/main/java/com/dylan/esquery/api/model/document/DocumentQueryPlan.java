package com.dylan.esquery.api.model.document;

import java.util.List;
import java.util.Optional;

/** typed query plan；不接受 DSL/Map。 */
public record DocumentQueryPlan(
        String normalizedOriginal,
        List<String> ruleKeywords,
        List<String> rewriteCandidates,
        Optional<DocumentQueryEmbeddingDto> embedding) {
    public DocumentQueryPlan {
        if(normalizedOriginal==null||normalizedOriginal.isBlank())throw new IllegalArgumentException("normalizedOriginal required");
        ruleKeywords=List.copyOf(ruleKeywords==null?List.of():ruleKeywords);
        rewriteCandidates=List.copyOf(rewriteCandidates==null?List.of():rewriteCandidates);
        embedding=embedding==null?Optional.empty():embedding;
    }
}
