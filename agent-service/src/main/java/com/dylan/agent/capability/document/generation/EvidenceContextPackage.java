package com.dylan.agent.capability.document.generation;

import com.dylan.agent.api.plan.DocumentPlanOperation;

import java.util.List;
import java.util.Set;

/** LLM 生成输入证据包。 */
public record EvidenceContextPackage(
        String requestId,
        DocumentPlanOperation operation,
        String queryText,
        List<DocumentEvidenceContextItem> evidenceItems,
        Set<String> citationIds,
        DocumentContextBudget budget,
        String digest) {
}
