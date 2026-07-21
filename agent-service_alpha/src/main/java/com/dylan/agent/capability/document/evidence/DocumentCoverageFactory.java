package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;

import java.util.List;
import java.util.Objects;

/** 仅使用caller-known scope与最终visible evidence计算coverage。 */
public final class DocumentCoverageFactory {
    public DocumentCoverageDraft create(ValidatedDocumentPlan plan, List<AclBoundDocumentHit> evidence,
                                        boolean retrievalTruncated, boolean selectionTruncated) {
        boolean known = plan.parameters().operation() == DocumentPlanOperation.SUMMARIZE
                && plan.parameters().summaryScope() != null
                && plan.parameters().summaryScope().getDocumentIds() != null
                && !plan.parameters().summaryScope().getDocumentIds().isEmpty();
        int requested = known ? (int) plan.parameters().summaryScope().getDocumentIds().stream()
                .filter(Objects::nonNull).map(String::trim).filter(value -> !value.isBlank()).distinct().count() : 0;
        int covered = (int) evidence.stream().map(hit -> hit.identity().sourceIdentity()).distinct().count();
        return new DocumentCoverageDraft(requested, known, covered, evidence.size(),
                retrievalTruncated || selectionTruncated);
    }
}
