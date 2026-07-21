package com.dylan.agent.adapter.api.document;

import java.util.List;
import java.util.Optional;

/** 检索用规范化查询；original 始终为 variant 0。 */
public record DocumentPreparedQuery(
        String normalizedOriginal,
        List<String> ruleKeywords,
        List<String> rewriteCandidates,
        Optional<DocumentQueryEmbedding> embedding) {
    public DocumentPreparedQuery {
        if (normalizedOriginal == null || normalizedOriginal.isBlank()) {
            throw new IllegalArgumentException("normalizedOriginal required");
        }
        ruleKeywords = List.copyOf(ruleKeywords == null ? List.of() : ruleKeywords);
        rewriteCandidates = List.copyOf(rewriteCandidates == null ? List.of() : rewriteCandidates);
        embedding = embedding == null ? Optional.empty() : embedding;
    }
}
