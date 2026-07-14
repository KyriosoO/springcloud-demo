package com.dylan.agent.api.response;

/** 仅供 Result Security 本地复核的候选 identity/security binding，不参与公共 JSON。 */
public record DocumentResultCandidateSecurityEvidence(
        String candidateId,
        String documentId,
        String documentVersion,
        String chunkId,
        int chunkIndex,
        String protectedFilterDigest,
        String aclEvidenceDigest,
        String aclRef,
        String aclVersion,
        String manifestDigest,
        String attestationDigest,
        String profileProjectionDigest,
        String resourceLimitDigest) {
}
