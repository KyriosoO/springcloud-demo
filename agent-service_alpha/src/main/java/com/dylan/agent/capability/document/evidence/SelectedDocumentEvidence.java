package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;

import java.util.List;

/** 04顺序不变的public-visible稳定前缀。 */
public record SelectedDocumentEvidence(
        List<AclBoundDocumentHit> items,
        int evidenceChars,
        boolean truncated) {
    public SelectedDocumentEvidence { items = List.copyOf(items); }
}
