package com.dylan.documentgeneration.model;

import java.util.List;
import java.util.Set;

public record EvidenceContextPackage(
        String requestId,
        DocumentPlanOperation operation,
        String queryText,
        List<DocumentEvidenceContextItem> evidenceItems,
        Set<String> citationIds,
        DocumentContextBudget budget,
        String digest) {
}
