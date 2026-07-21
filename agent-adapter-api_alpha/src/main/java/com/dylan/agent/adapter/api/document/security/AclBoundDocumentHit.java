package com.dylan.agent.adapter.api.document.security;

import com.dylan.agent.adapter.api.document.DocumentCandidateIdentity;
import com.dylan.agent.adapter.api.document.DocumentCandidateSecurityBinding;

import java.math.BigDecimal;
import java.util.List;

/** 通过 es-query 算法前校验及 Adapter 跨服务复核的不可变 hit。 */
public record AclBoundDocumentHit(
        String candidateId,
        DocumentCandidateIdentity identity,
        String title,
        String sourceType,
        String section,
        Integer page,
        String sourceUri,
        String snippet,
        String content,
        String citationText,
        String generationText,
        List<String> contextBefore,
        List<String> contextAfter,
        Integer charStart,
        Integer charEnd,
        BigDecimal score,
        BigDecimal rrfScore,
        List<String> retrievalChannels,
        List<String> safeFieldNames,
        DocumentCandidateSecurityBinding securityBinding) {
    public AclBoundDocumentHit {
        if (candidateId == null || candidateId.isBlank() || identity == null || securityBinding == null) {
            throw new IllegalArgumentException("ACL-bound hit identity/security binding must be complete");
        }
        contextBefore = List.copyOf(contextBefore == null ? List.of() : contextBefore);
        contextAfter = List.copyOf(contextAfter == null ? List.of() : contextAfter);
        retrievalChannels = List.copyOf(retrievalChannels == null ? List.of() : retrievalChannels);
        safeFieldNames = List.copyOf(safeFieldNames == null ? List.of() : safeFieldNames);
    }
}
